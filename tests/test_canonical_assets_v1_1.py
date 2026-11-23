"""
Regression tests for the unified 85-slot Canonical Asset Library (`v1`: 42 + `v1_1`: 43):
  1. Verifies `v1/manifest.json` immutability (`42/42` SHA-256 locks, exact untouched digest).
  2. Verifies `v1_1/manifest.json` lock (`43/43` slots approved + live SHA-256 verified, 7 Rank-1 promotions, F04 Pair 1 fix).
  3. Verifies `F03a -> F03b` byte-for-byte SHA-256 daisy-chain equality.
  4. Verifies all `23` `[EXCL]` excluded outliers and unapproved backup candidates are hard-blocked.
  5. Verifies unified `85`-slot resolution + mixed `v1 + v1_1` project provenance staging, validation, and tamper detection.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from pipeline.canonical_assets import (
    CanonicalAssetError,
    compute_file_sha256,
    guard_r88_autobound_slot,
    is_retired_derivative_anchor,
    list_all_approved_canonical_slots,
    load_canonical_manifest,
    resolve_canonical_approved_slot,
    resolve_canonical_transition_pair,
    select_canonical_brain_slot,
    select_canonical_character_slot,
    select_canonical_environment_slot,
    select_canonical_layout_slot,
    select_canonical_misconception_slot,
    select_canonical_prop_slot,
    select_canonical_transition_slot,
    stage_canonical_slot_to_project,
    stage_canonical_transition_pair_to_project,
    validate_project_canonical_provenance,
)
from pipeline.config import CHANNEL_ROOT, R88_RETIRED_CARTOON_CAST_SLOTS


def test_canonical_v1_immutability_and_v1_1_43slot_sha256_lock() -> None:
    v1_doc = load_canonical_manifest(version="v1", require_approved=True)
    assert v1_doc["pre_r88_manifest_sha256"] == "c9d2e271b8134363605890c289512ebd304ba09529260265f45bcbbc844a3892"
    v1_by_id = {s["slot_id"]: s for s in v1_doc["slots"]}
    for b_sid in R88_RETIRED_CARTOON_CAST_SLOTS:
        b_slot = v1_by_id[b_sid]
        assert b_slot["status"] == "retired_r88_cartoon_face"
        assert b_slot["selectable_for_new_episodes"] is False
        res_ret = resolve_canonical_approved_slot(b_sid, version="v1", verify_sha256=True, allow_retired_r88=True)
        assert res_ret["abs_path"].is_file()
    with pytest.raises(CanonicalAssetError, match="retired under R88"):
        resolve_canonical_approved_slot("B01_base_adult_male_turnaround")

    v11_doc = load_canonical_manifest(version="v1_1", require_approved=True)
    assert v11_doc["status"] == "approved"
    assert v11_doc["sha256_locked"] is True
    slots = v11_doc["slots"]
    assert len(slots) == 43

    # Verify the 7 Rank-1 promotions + CEO F04 fix
    expected_promoted = {
        "A16_eyes_optic_nerve_to_v1_pathway": "cand_03.png",
        "A17_brain_spinal_body_descending_xray": "cand_02.png",
        "E14_night_bedroom_staged": "cand_02.png",
        "E16_urban_street_sidewalk_staged": "cand_02.png",
        "H01_padlocked_acrylic_plaster_brain_case": "cand_02.png",
        "H04_physical_red_x_over_simple_diagram_card": "cand_03.png",
        "I03_callout_safezone_brain_headroom_frame": "cand_02.png",
    }
    by_id = {s["slot_id"]: s for s in slots}
    for sid, want_fn in expected_promoted.items():
        res = resolve_canonical_approved_slot(sid, version="auto", verify_sha256=True)
        assert res["library_version"] == "v1_1"
        assert res["approved_filename"] == want_fn

    # Verify 70 active v1+v1_1 slots (27 v1 + 43 v1_1) and 85 with Zero-Deletion retired R88 slots
    active_70 = list_all_approved_canonical_slots(versions=("v1", "v1_1"), verify_sha256=True)
    assert len(active_70) == 70
    all_85 = list_all_approved_canonical_slots(versions=("v1", "v1_1"), verify_sha256=True, include_retired_r88=True)
    assert len(all_85) == 85

    # Verify F03a -> F03b daisy-chain byte equality
    f03a = resolve_canonical_transition_pair("F03a_whole_brain_to_sulcal_vessel_macro", verify_sha256=True)
    f03b = resolve_canonical_transition_pair("F03b_sulcal_vessel_macro_to_1p_tract_canyon", verify_sha256=True)
    assert f03a["end"]["sha256"] == f03b["start"]["sha256"]

    # Verify F04 CEO sponge -> thalamus+CSF Pair 1 lock
    f04 = resolve_canonical_transition_pair("F04_metaphor_prop_to_anatomy_shape_bridge", verify_sha256=True)
    assert f04["start"]["sha256"].startswith("0d36df142cac2aa4")
    assert f04["end"]["sha256"].startswith("7fc229c9af81a822")

    # Verify all 23 [EXCL] outlier files in v1_1 are hard-blocked by is_retired_derivative_anchor
    excl_blocked = 0
    for sl in slots:
        for ce in sl["candidates"]:
            if ce.get("status") == "excluded_outlier":
                excl_blocked += 1
                if sl["category"] == "F_transitions":
                    assert is_retired_derivative_anchor(f"BCI_Shorts_Channel/canonical_assets/v1_1/{ce['start_rel_path']}")
                    assert is_retired_derivative_anchor(f"BCI_Shorts_Channel/canonical_assets/v1_1/{ce['end_rel_path']}")
                else:
                    assert is_retired_derivative_anchor(f"BCI_Shorts_Channel/canonical_assets/v1_1/{ce['rel_path']}")
            elif ce.get("status") == "approved":
                if sl["category"] == "F_transitions":
                    assert not is_retired_derivative_anchor(f"BCI_Shorts_Channel/canonical_assets/v1_1/{ce['start_rel_path']}")
                    assert not is_retired_derivative_anchor(f"BCI_Shorts_Channel/canonical_assets/v1_1/{ce['end_rel_path']}")
                else:
                    assert not is_retired_derivative_anchor(f"BCI_Shorts_Channel/canonical_assets/v1_1/{ce['rel_path']}")
    assert excl_blocked == 23


def test_mixed_v1_and_v1_1_project_staging_provenance_and_tamper_guard(tmp_path: Path) -> None:
    pdir = tmp_path / "v8_ep_test_mixed_canonical"
    (pdir / "03_visuals" / "reference_images").mkdir(parents=True, exist_ok=True)
    (pdir / "00_project_manifest.json").write_text(json.dumps({"project_id": pdir.name}), encoding="utf-8")

    st_v1 = stage_canonical_slot_to_project(pdir, "A07_thalamus_brainstem_midsagittal", version="auto")
    st_v11 = stage_canonical_slot_to_project(pdir, "A15_ventricular_csf_aqueduct_cutaway", version="auto")
    st_f04 = stage_canonical_transition_pair_to_project(pdir, "F04_metaphor_prop_to_anatomy_shape_bridge")

    assert st_v1["library_version"] == "v1"
    assert st_v11["library_version"] == "v1_1"
    assert st_f04["library_version"] == "v1_1"

    audit = validate_project_canonical_provenance(pdir)
    assert audit["passed"] is True, audit
    assert audit["library_version"] == "v1+v1_1"
    assert audit["libraries_used"] == ["v1", "v1_1"]
    assert audit["locked_file_count"] == 4

    pm = json.loads((pdir / "00_project_manifest.json").read_text(encoding="utf-8"))
    assert pm["canonical_assets_lock"]["library_version"] == "v1+v1_1"
    assert "A15_ventricular_csf_aqueduct_cutaway" in pm["canonical_assets_lock"]["slots_used"]

    # Tamper detection on v1_1 staged file
    Path(st_v11["staged_path"]).write_bytes(b"tampered")
    bad_audit = validate_project_canonical_provenance(pdir)
    assert bad_audit["passed"] is False
    assert any("canonical_sha256_mismatch" in x for x in bad_audit["issues"])


def test_v1_1_selectors_and_excluded_slot_rejection() -> None:
    assert select_canonical_brain_slot(brain_region="cerebral ventricles csf") == "A15_ventricular_csf_aqueduct_cutaway"
    assert select_canonical_brain_slot(brain_region="optic nerve") == "A16_eyes_optic_nerve_to_v1_pathway"
    assert select_canonical_brain_slot(shot_scale="1p_tract_canyon") == "A13_1p_white_matter_tract_canyon"
    assert select_canonical_brain_slot(brain_region="nucleus accumbens", viewpoint="coronal_cutaway") != "A19_anterior_cingulate_amygdala_limbic_cutaway"
    assert select_canonical_brain_slot(brain_region="anterior cingulate cortex") == "A19_anterior_cingulate_amygdala_limbic_cutaway"
    assert select_canonical_environment_slot("night bedroom", staged=True) == "E14_night_bedroom_staged"
    assert select_canonical_prop_slot("amber pill bottle") == "G03_unlabeled_amber_pill_bottle_and_capsules"
    assert select_canonical_misconception_slot("padlocked acrylic brain") == "H01_padlocked_acrylic_plaster_brain_case"
    assert select_canonical_layout_slot("dark brain data stamp") == "I02_data_stamp_backdrop_dark_brain_low38"
    assert select_canonical_transition_slot("sponge metaphor bridge") == "F04_metaphor_prop_to_anatomy_shape_bridge"

    for sid in (
        select_canonical_brain_slot(brain_region="dopamine synapse"),
        select_canonical_brain_slot(brain_region="nucleus accumbens", viewpoint="coronal_cutaway"),
        select_canonical_brain_slot(brain_region="anterior cingulate cortex"),
        select_canonical_prop_slot("lightbox"),
        select_canonical_prop_slot("amber pill bottle"),
        select_canonical_misconception_slot("dormant bulb"),
        select_canonical_layout_slot("dark brain data stamp"),
        select_canonical_layout_slot("tabletop stamp"),
        select_canonical_transition_slot("window interior"),
        select_canonical_transition_slot("return real_world"),
    ):
        assert resolve_canonical_approved_slot(sid, version="auto", verify_sha256=False)["slot_id"] == sid

    with pytest.raises(CanonicalAssetError):
        resolve_canonical_approved_slot("xray_brain75_master")


def test_r88_faceless_master_bindings_and_dotted_eye_staged_guard() -> None:
    from pipeline.porcelain_anchor_pack import build_r85_canonical_master_bindings

    # 1. Under r88_faceless=True, environment & character selectors never return E*_staged cartoon-dot-eye rooms
    assert select_canonical_environment_slot("fmri suite", staged=True, r88_faceless=True) == "E02_mri_suite_empty"
    assert select_canonical_environment_slot("clinical lab", staged=True, r88_faceless=True) == "E01_laboratory_empty"
    assert select_canonical_environment_slot("kitchen", staged=True, r88_faceless=True) == "E05_kitchen_empty"
    assert select_canonical_environment_slot("night bedroom", staged=True, r88_faceless=True) == "E11_night_bedroom_empty"

    assert select_canonical_character_slot(role_hint="neuroscience lab", r88_faceless=True) == "E01_laboratory_empty"
    assert select_canonical_character_slot(role_hint="fmri scanner", r88_faceless=True) == "E02_mri_suite_empty"
    assert select_canonical_character_slot(role_hint="breakfast coffee", r88_faceless=True) == "E05_kitchen_empty"
    assert select_canonical_character_slot(role_hint="everyday figure", r88_faceless=True) == "A01_mode1_translucent_head_lateral"

    # 2. guard_r88_autobound_slot rejects every pre-R88 dotted-eye E*_staged slot under R88 auto-binding
    for bad_staged in (
        "E06_laboratory_staged",
        "E07_mri_suite_staged",
        "E08_home_doorway_staged",
        "E09_lecture_room_staged",
        "E10_kitchen_staged",
        "E14_night_bedroom_staged",
        "E15_clinic_consult_office_staged",
        "E16_urban_street_sidewalk_staged",
    ):
        with pytest.raises(CanonicalAssetError, match="dotted-eye staged slot"):
            guard_r88_autobound_slot(bad_staged, r88_faceless=True)

    # 3. R88 master bindings resolve cleanly to E01/E05/E02 empty masters with 0 E*_staged slots
    bindings = build_r85_canonical_master_bindings(
        {"style_profile": "expressive_25d_v8", "r88_mode": True, "real_environment": "sunlit fMRI suite"},
        project_id="v8_ep13_snack_reward_rewiring",
    )
    by_alias = {alias: sid for sid, alias, _ in bindings if alias}
    assert by_alias["cast_sheet_02_clinical_historical_6roles.png"] == "E01_laboratory_empty"
    assert by_alias["cast_sheet_03_everyday_lifestyle_6roles.png"] == "E05_kitchen_empty"
    assert by_alias["expressive_conflict_master.png"] == "E02_mri_suite_empty"
    assert by_alias["species_opt1_sheet.png"] == "A01_mode1_translucent_head_lateral"
    assert not any(sid.endswith("_staged") for sid, _, _ in bindings)
