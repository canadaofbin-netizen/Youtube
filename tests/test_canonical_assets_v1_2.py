"""
Canonical Asset Library v1.2 Permanent SHA-256 Lock & Provenance Tests:
  - Verifies 14/15 user-approved v1.2 slots (15 PNG files including K06 Start+End) resolve with SHA-256 lock.
  - Verifies J04_hook_paradox_prop_split_tabletop is explicitly deferred ('deferred_flow_unusual_activity') and blocked.
  - Verifies parent v1 (42) + v1_1 (43) manifests remain 100% untouched (total 99 unified locked slots).
  - Verifies all 10 [EXCL] outliers and unapproved backup candidates in v1_2 are hard-blocked.
  - Verifies staging v1_2 anchors into a project records canonical_assets_v1_2 provenance and catches tampering.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from pipeline.canonical_assets import (
    CanonicalAssetError,
    compute_file_sha256,
    get_canonical_root,
    is_retired_derivative_anchor,
    list_all_approved_canonical_slots,
    load_canonical_manifest,
    resolve_canonical_approved_slot,
    resolve_canonical_transition_pair,
    stage_canonical_slot_to_project,
    stage_canonical_transition_pair_to_project,
    validate_project_canonical_provenance,
)
from pipeline.config import REF_IMAGE_SOURCE_CANONICAL_V1_2

EXPECTED_V1_2_USER_PICKS: dict[str, str | tuple[str, str]] = {
    "J01_hook_mode1_daily_action_xray_alert": "cand_01.png",
    "J02_hook_mode1_bedside_sleep_anomaly": "cand_03.png",
    "J03_hook_bizarre_experiment_prop_closeup": "cand_02.png",
    "J05_hook_mode2_instant_brain_shock_open": "cand_03.png",
    "J06_hook_extreme_2d_ink_shock_reaction": "cand_02.png",
    "K01_contrast_active_vs_blocked_fluid_tubes": "cand_02.png",
    "K02_contrast_squeezed_vs_stalled_sponge_basins": "cand_02.png",
    "K03_contrast_twin_tabletop_stimulus_ab": "cand_01.png",
    "K04_contrast_dual_receptor_chemical_lock_panel": "cand_03.png",
    "K05_contrast_scale_flat_vs_internal_surge_split": "cand_01.png",
    "K06_contrast_a12_dual_brain_state_transition_pair": ("cand_02_start.png", "cand_02_end.png"),
    "C01b_spatial_corridor_with_anchor_prop": "cand_01.png",
    "C02b_spatial_dual_route_prop_legend": "cand_02.png",
    "C03b_spatial_doorway_sever_with_prop": "cand_01.png",
}

EXPECTED_V1_2_EXCLUDED: tuple[tuple[str, str], ...] = (
    ("J01_hook_mode1_daily_action_xray_alert", "cand_03.png"),
    ("J03_hook_bizarre_experiment_prop_closeup", "cand_01.png"),
    ("J04_hook_paradox_prop_split_tabletop", "cand_01.png"),
    ("J04_hook_paradox_prop_split_tabletop", "cand_02.png"),
    ("J04_hook_paradox_prop_split_tabletop", "cand_03.png"),
    ("J06_hook_extreme_2d_ink_shock_reaction", "cand_03.png"),
    ("C01b_spatial_corridor_with_anchor_prop", "cand_02.png"),
    ("C02b_spatial_dual_route_prop_legend", "cand_01.png"),
    ("C02b_spatial_dual_route_prop_legend", "cand_03.png"),
    ("C03b_spatial_doorway_sever_with_prop", "cand_03.png"),
)


def test_canonical_v1_2_manifest_locked_14_of_15_and_unified_99_slots() -> None:
    doc = load_canonical_manifest(version="v1_2", require_approved=True)
    assert doc["status"] == "locked"
    assert doc["sha256_locked"] is True
    assert doc["approved_slot_count"] == 14
    assert doc["deferred_slot_count"] == 1
    assert doc["locked_file_count"] == 15
    assert doc["excluded_candidate_count"] == 10

    # Parent v1 + v1_1 SHA-256 unchanged
    v1_sha = compute_file_sha256(get_canonical_root("v1") / "manifest.json")
    v1_1_sha = compute_file_sha256(get_canonical_root("v1_1") / "manifest.json")
    assert v1_sha == doc["parent_locked_libraries"]["v1"]["manifest_sha256"]
    assert v1_1_sha == doc["parent_locked_libraries"]["v1_1"]["manifest_sha256"]

    # Active unified library = 27 + 43 + 14 = 84 slots; with 15 Zero-Deletion R88 retired = 99 slots (all SHA-256 verified)
    active_84 = list_all_approved_canonical_slots(verify_sha256=True)
    assert len(active_84) == 84
    unified = list_all_approved_canonical_slots(verify_sha256=True, include_retired_r88=True)
    assert len(unified) == 99

    # Resolve all 14 approved v1_2 slots with live SHA-256 verification
    for sid, expected_pick in EXPECTED_V1_2_USER_PICKS.items():
        if isinstance(expected_pick, tuple):
            pair = resolve_canonical_transition_pair(sid, version="v1_2", verify_sha256=True)
            assert pair["start"]["approved_filename"] == expected_pick[0]
            assert pair["end"]["approved_filename"] == expected_pick[1]
            assert pair["start"]["abs_path"].is_file()
            assert pair["end"]["abs_path"].is_file()
        else:
            res = resolve_canonical_approved_slot(sid, version="v1_2", verify_sha256=True)
            assert res["library_version"] == "v1_2"
            assert res["approved_filename"] == expected_pick
            assert res["abs_path"].is_file()


def test_canonical_v1_2_deferred_j04_and_10_excluded_outliers_blocked() -> None:
    with pytest.raises(CanonicalAssetError, match="deferred_flow_unusual_activity"):
        resolve_canonical_approved_slot("J04_hook_paradox_prop_split_tabletop", version="v1_2")

    v12_root = get_canonical_root("v1_2")
    for sid, fn in EXPECTED_V1_2_EXCLUDED:
        p = v12_root / "candidates" / sid / fn
        assert is_retired_derivative_anchor(p) is True, f"[EXCL] outlier must be blocked: {p}"

    # Unapproved backup candidates also blocked while approved Rank-1 files are allowed
    assert is_retired_derivative_anchor(v12_root / "candidates" / "J01_hook_mode1_daily_action_xray_alert" / "cand_02.png") is True
    assert is_retired_derivative_anchor(v12_root / "candidates" / "J01_hook_mode1_daily_action_xray_alert" / "cand_01.png") is False
    assert is_retired_derivative_anchor(v12_root / "candidates" / "K06_contrast_a12_dual_brain_state_transition_pair" / "cand_02_start.png") is False
    assert is_retired_derivative_anchor(v12_root / "candidates" / "K06_contrast_a12_dual_brain_state_transition_pair" / "cand_02_end.png") is False
    assert is_retired_derivative_anchor(v12_root / "candidates" / "K06_contrast_a12_dual_brain_state_transition_pair" / "cand_01_end.png") is True


def test_canonical_v1_2_stage_ep13_anchors_and_tamper_detection(tmp_path: Path) -> None:
    proj = tmp_path / "v8_ep13_stage_test"
    (proj / "03_visuals" / "reference_images").mkdir(parents=True)

    st_j01 = stage_canonical_slot_to_project(proj, "J01_hook_mode1_daily_action_xray_alert", version="v1_2")
    st_k03 = stage_canonical_slot_to_project(proj, "K03_contrast_twin_tabletop_stimulus_ab", version="v1_2")
    st_k05 = stage_canonical_slot_to_project(proj, "K05_contrast_scale_flat_vs_internal_surge_split", version="v1_2")
    st_k06 = stage_canonical_transition_pair_to_project(proj, "K06_contrast_a12_dual_brain_state_transition_pair", version="v1_2")

    assert st_j01["staged_path"].is_file()
    assert st_k03["staged_path"].is_file()
    assert st_k05["staged_path"].is_file()
    assert st_k06["start"]["staged_path"].is_file()
    assert st_k06["end"]["staged_path"].is_file()

    prov = json.loads((proj / "03_visuals" / "reference_images" / "provenance.json").read_text(encoding="utf-8"))
    assert prov[st_j01["staged_filename"]] == REF_IMAGE_SOURCE_CANONICAL_V1_2
    assert prov[st_k06["end"]["staged_filename"]] == REF_IMAGE_SOURCE_CANONICAL_V1_2

    val_ok = validate_project_canonical_provenance(proj)
    assert val_ok["passed"] is True, val_ok["issues"]
    assert val_ok["locked_file_count"] == 5

    # Tampering 1 byte of a staged v1_2 anchor must fail SHA-256 verification
    st_k03["staged_path"].write_bytes(st_k03["staged_path"].read_bytes() + b"\x00")
    val_bad = validate_project_canonical_provenance(proj)
    assert val_bad["passed"] is False
    assert any("canonical_sha256_mismatch" in i for i in val_bad["issues"])
