"""
Rule R87 Global Pipeline Test Suite:
  - R87-H1: Cut #1 hook_visual_mode, static domestic sitting ban, 1.90-2.60s ceiling,
            thumbnail <-> HookTitle/Cut #1 alignment, t=0.0s Mode 1/2 early-brain compat,
            and Lock 3 Category J / A01-A19 canonical binding.
  - R87-H2: Default opening_mode='immediate_brain_shock', banned S01 prefixes, zero '?',
            6-12 words, and prosody-qa P_R87_s01_duration <= 3.50s.
  - R87-H3: 0.00-2.20s 118pt HookTitle ASS emission (2-tone white+#FFE14A, MarginV=250, MarginR=170)
            + upgraded 82pt Default ASS (Outline=5.5, Shadow=1.5, MarginV=510, MarginR=165, 3w, #FFE600).
  - R87-A: Conditional spatial arrow eligibility (False bans spatial_3d_arrow_diorama & r80_mode=True,
           requires Category K / A12 contrast; True bans empty gray alleys & single-arrow comparison
           narration, requires miniature prop anchor & Lock 3 C01b-C03b binding).
  - Canonical v1.2 Loader: blocks candidate/unapproved manifest, resolves & verifies SHA-256 when approved,
           handles K06 start_end_transition_pair, and list_all_approved_canonical_slots skips candidate v1_2 cleanly.
  - Lock 2: Gate 1 (reference_image_qa) & Gate 2 (posthoc_semantic_qa) R87 viewer common-sense 3 booleans.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest


def _make_valid_r87_nonspatial_plan_and_script() -> tuple[dict, dict, list[str]]:
    lines = [
        "One daily pudding cup rewired healthy brains without adding one pound!",
        "In 2023 at Max Planck Cologne, forty-six volunteers ate a daily snack.",
        "Half ate rich high-fat pudding while the other half ate plain yogurt.",
        "Both snacks had identical calories and neither group gained any weight.",
        "Yet brain scans revealed a dramatic dopamine surge inside the striatum.",
        "The sweet snack literally trained the reward circuit to reject plain food.",
    ]
    script_doc = {
        "project_id": "v8_ep13_snack_rewiring_test",
        "r87_mode": True,
        "opening_mode": "immediate_brain_shock",
        "sentences": lines,
    }
    clips = [
        {
            "clip_number": 1,
            "sentence_index": 1,
            "grammar": "expressive_xray_brain",
            "duration_sec": 2.30,
            "canonical_slot_id": "J01_hook_mode1_daily_action_xray_alert",
            "reference_image": "canonical_J01_hook_mode1_daily_action_xray_alert.png",
            "scene": "Bald cream-white vinyl adult lifts a glossy chocolate pudding spoon toward mouth while translucent cranium Mode 1 cutaway brain flares solid matte amber-gold in the ventral striatum.",
            "action": "Lifts snack spoon mid-action as Mode 1 skull brain core activates.",
            "concrete_referent": "chocolate pudding spoon and ventral striatum",
        },
        {
            "clip_number": 2,
            "sentence_index": 2,
            "grammar": "expressive_exterior_establishing",
            "duration_sec": 2.40,
            "reference_image": "canonical_D01_drone_university_campus_120ft.png",
            "scene": "120ft aerial drone glides over Max Planck Cologne research campus rooftops.",
            "action": "Sweeps high above the sunlit institute quad.",
            "concrete_referent": "Max Planck campus",
        },
        {
            "clip_number": 3,
            "sentence_index": 3,
            "grammar": "expressive_split_contrast",
            "visual_proof_type": "comparison",
            "duration_sec": 2.80,
            "canonical_slot_id": "K03_contrast_twin_tabletop_stimulus_ab",
            "reference_image": "canonical_K03_contrast_twin_tabletop_stimulus_ab.png",
            "scene": "High-angle sunlit oak lab table compares glossy pudding bowl on left tray side by side with plain yogurt bowl on right tray.",
            "action": "Twin lab trays compare pudding versus plain yogurt.",
            "concrete_referent": "pudding bowl versus plain yogurt bowl",
        },
        {
            "clip_number": 4,
            "sentence_index": 4,
            "grammar": "expressive_split_contrast",
            "visual_proof_type": "comparison",
            "duration_sec": 2.70,
            "canonical_slot_id": "K05_contrast_scale_flat_vs_internal_surge_split",
            "reference_image": "canonical_K05_contrast_scale_flat_vs_internal_surge_split.png",
            "scene": "Neutral flat bathroom scale beside clear acrylic dome showing Ep #31 matte gypsum brain active amber core.",
            "action": "Flat neutral dial contrasts with active striatum core.",
            "concrete_referent": "neutral scale and brain dome",
        },
        {
            "clip_number": 5,
            "sentence_index": 5,
            "grammar": "expressive_xray_brain",
            "visual_proof_type": "comparison",
            "duration_sec": 4.80,
            "canonical_slot_id": "K06_contrast_a12_dual_brain_state_transition_pair",
            "reference_image": "canonical_K06_contrast_a12_dual_brain_state_transition_pair_start.png",
            "end_reference_image": "canonical_K06_contrast_a12_dual_brain_state_transition_pair_end.png",
            "scene": "Stacked twin Ep #31 matte gypsum 3D brains over navy void compare amber-gold striatum top brain versus charcoal-slate bottom brain.",
            "action": "Top brain striatum intensifies amber-gold while bottom brain dims.",
            "concrete_referent": "dual brain striatum contrast",
        },
    ]
    plan = {
        "schema": 8,
        "style_profile": "expressive_25d_v8",
        "project_id": "v8_ep13_snack_rewiring_test",
        "r87_mode": True,
        "r80_mode": False,
        "spatial_arrow_eligible": False,
        "contrast_visual_mode": "non_spatial_prop_and_brain",
        "opening_mode": "immediate_brain_shock",
        "hook_visual_mode": "mode1_daily_xray_shock",
        "hook_title_text": "1 SNACK\\NREWIRED IT!",
        "thumbnail": {
            "cover_sentence_index": 1,
            "top_label": "0 LB GAINED",
            "bottom_label": "BRAIN REWIRED?!",
            "hook_text": "1 SNACK REWIRED BRAIN",
        },
        "clips": clips,
    }
    return plan, script_doc, lines


def test_r87_h1_h2_valid_nonspatial_plan_passes() -> None:
    from pipeline.prompt_gate import (
        validate_r87_hook_contract,
        validate_r87_spatial_arrow_eligibility,
    )

    plan, script_doc, lines = _make_valid_r87_nonspatial_plan_and_script()
    assert validate_r87_hook_contract(plan, plan["clips"], lines=lines, script_doc=script_doc) == []
    assert validate_r87_spatial_arrow_eligibility(plan, plan["clips"], lines=lines, script_doc=script_doc) == []


def test_r87_h1_cut1_duration_thumb_mismatch_and_lock3_anchor() -> None:
    from pipeline.prompt_gate import validate_r87_hook_contract

    plan, script_doc, lines = _make_valid_r87_nonspatial_plan_and_script()
    plan["clips"][0]["duration_sec"] = 3.10
    plan["clips"][0]["canonical_slot_id"] = "E14_night_bedroom_staged"
    plan["clips"][0]["reference_image"] = "canonical_E14_night_bedroom_staged.png"
    plan["thumbnail"] = {"cover_sentence_index": 1, "bottom_label": "LONDON TAXI CAB"}
    issues = validate_r87_hook_contract(plan, plan["clips"], lines=lines, script_doc=script_doc)
    joined = "\n".join(issues)
    assert "[r87_h1_cut1_duration]" in joined
    assert "[r87_lock3_cut1_canonical_anchor]" in joined
    assert "[r87_h1_thumb_to_cut1_mismatch]" in joined


def test_r87_h2_prosody_s01_duration_ceiling(tmp_path: Path) -> None:
    from pipeline.prosody_qa import _compute_core_prosody_gates

    proj = tmp_path / "v8_ep13_prosody_test"
    (proj / "04_audio").mkdir(parents=True)
    (proj / "03_visuals").mkdir(parents=True)
    (proj / "02_script").mkdir(parents=True)

    (proj / "03_visuals" / "visual_plan.json").write_text(
        json.dumps({"style_profile": "expressive_25d_v8", "r87_mode": True}),
        encoding="utf-8",
    )
    (proj / "02_script" / "script.json").write_text(
        json.dumps({"r87_mode": True, "opening_mode": "immediate_brain_shock"}),
        encoding="utf-8",
    )
    # Slow S01 (4.10s > 3.50s) must FAIL P_R87_s01_duration
    (proj / "04_audio" / "voice_report.json").write_text(
        json.dumps(
            {
                "engine": "elevenlabs_v4",
                "sentence_spans": [
                    {"sentence_index": 1, "start_sec": 0.0, "end_sec": 4.10},
                    {"sentence_index": 2, "start_sec": 4.52, "end_sec": 7.80},
                ],
            }
        ),
        encoding="utf-8",
    )
    (proj / "04_audio" / "prosody_report.json").write_text(
        json.dumps({"prosody_mode": "expressive_v8_us", "sentences": [{"sentence_index": 1, "lead_silence_sec": 0.0}]}),
        encoding="utf-8",
    )
    _, gates_fail = _compute_core_prosody_gates(proj, asr_media_path=None, run_asr=False, include_mp4_post_gates=False)
    assert gates_fail["P_R87_s01_duration"]["passed"] is False
    assert gates_fail["P_R87_s01_duration"]["warning"] is True

    # Fast S01 (2.95s <= 3.10s) must PASS cleanly with warning=False
    (proj / "04_audio" / "voice_report.json").write_text(
        json.dumps(
            {
                "engine": "elevenlabs_v4",
                "sentence_spans": [
                    {"sentence_index": 1, "start_sec": 0.0, "end_sec": 2.95},
                    {"sentence_index": 2, "start_sec": 3.37, "end_sec": 6.40},
                ],
            }
        ),
        encoding="utf-8",
    )
    _, gates_ok = _compute_core_prosody_gates(proj, asr_media_path=None, run_asr=False, include_mp4_post_gates=False)
    assert gates_ok["P_R87_s01_duration"]["passed"] is True
    assert gates_ok["P_R87_s01_duration"]["warning"] is False


def test_r87_h3_hooktitle_and_82pt_yellow_ass_generation(tmp_path: Path) -> None:
    from pipeline.assembler import generate_diorama_ass_subtitles

    ass_p = tmp_path / "subtitles.ass"
    vp = {
        "schema": 8,
        "style_profile": "expressive_25d_v8",
        "r87_mode": True,
        "hook_title_text": "1 DAILY SNACK\\NREWIRED IT!",
    }
    edl = {"schema": 8, "fps": 30, "speech_end_sec": 12.0, "total_duration_sec": 12.2, "cuts": []}
    events = [
        (0.0, 1.1, ["One", "daily", "snack"]),
        (1.1, 2.3, ["rewired", "healthy", "brains"]),
        (2.3, 3.6, ["without", "1", "pound!"]),
    ]
    spans = [{"sentence_index": 1, "start_sec": 0.0, "end_sec": 3.6}]
    generate_diorama_ass_subtitles(ass_p, events, spans, vp, edl)
    txt = ass_p.read_text(encoding="utf-8")

    # Verify upgraded Default style: 82pt, Outline=5.5, Shadow=1.5, MarginL=80, MarginR=165, MarginV=510
    assert "Style: Default,AAB Condensed Black,82,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,5.5,1.5,2,80,165,510,1" in txt
    # Verify HookTitle style & 0.00-2.20s 2-tone white + #FFE14A (&H004AE1FF&) event with 0ms fade-in
    assert "Style: HookTitle,AAB Condensed Black,118,&H00FFFFFF,&H00FFFFFF,&H00000000,&H88000000,0,0,0,0,92,100,1,0,1,7.0,3.0,8,85,170,238,1" in txt
    assert "Dialogue: 3,0:00:00.00,0:00:02.19,HookTitle,,0,0,0,," in txt or "Dialogue: 3,0:00:00.00,0:00:02.20,HookTitle,,0,0,0,," in txt
    assert "\\fad(0,120)" in txt
    assert "&H004AE1FF&" in txt
    # Verify #FFE600 (&H0000E6FF&) single-keyword highlight on Default captions
    assert "{\\c&H0000E6FF&}" in txt
    # Mid-episode ChapterHeadline remains strictly absent
    assert ",ChapterHeadline," not in txt


def test_r87_a_spatial_eligible_true_accepts_c02b_and_blocks_legacy_c02() -> None:
    from pipeline.prompt_builder import _compose_expressive_v8_context_split_scene
    from pipeline.prompt_gate import validate_r87_spatial_arrow_eligibility

    good_plan = {
        "style_profile": "expressive_25d_v8",
        "r87_mode": True,
        "spatial_arrow_eligible": True,
        "clips": [
            {
                "clip_number": 1,
                "sentence_index": 1,
                "grammar": "spatial_3d_arrow_diorama",
                "arrow_3d_mode": "dual_route_race_lanes",
                "canonical_slot_id": "C02b_spatial_dual_route_prop_legend",
                "reference_image": "canonical_C02b_spatial_dual_route_prop_legend.png",
                "anchor_prop_a": "miniature black London cab",
                "anchor_prop_b": "miniature red double-decker bus",
                "scene": "Top-down sunlit London brick street grid comparing miniature black London cab zigzag route side by side with miniature red bus straight lane.",
                "spoken_narration": "Put taxi drivers and bus drivers side by side on London streets.",
            }
        ],
    }
    assert validate_r87_spatial_arrow_eligibility(good_plan, good_plan["clips"]) == []

    # Legacy C02 (without 'b') fails Lock 3 on R87+
    legacy_c_plan = json.loads(json.dumps(good_plan))
    legacy_c_plan["clips"][0]["canonical_slot_id"] = "C02_arrow_adaptive_zigzag"
    legacy_c_plan["clips"][0]["reference_image"] = "canonical_C02_arrow_adaptive_zigzag.png"
    issues = validate_r87_spatial_arrow_eligibility(legacy_c_plan, legacy_c_plan["clips"])
    assert any("[r87_lock3_spatial_canonical_anchor]" in i for i in issues)

    # flow_prompt_builder raises ValueError if spatial_3d_arrow_diorama is requested with spatial_arrow_eligible=False
    with pytest.raises(ValueError, match="R87-A forbids spatial_3d_arrow_diorama"):
        _compose_expressive_v8_context_split_scene(
            {"grammar": "spatial_3d_arrow_diorama", "spatial_arrow_eligible": False}
        )


def test_canonical_v1_2_loader_blocks_candidate_and_resolves_approved_pair(tmp_path: Path) -> None:
    from pipeline.canonical_assets import (
        CanonicalAssetError,
        list_all_approved_canonical_slots,
        resolve_canonical_approved_slot,
        resolve_canonical_transition_pair,
        select_canonical_arrow_slot,
        select_canonical_hook_slot,
        select_canonical_nonspatial_contrast_slot,
    )

    # Selector coverage
    assert select_canonical_hook_slot("mode1_daily_xray_shock", "sleep paralysis") == "J02_hook_mode1_bedside_sleep_anomaly"
    assert select_canonical_hook_slot("mode2_instant_brain_shock", "snack") == "J05_hook_mode2_instant_brain_shock_open"
    assert select_canonical_nonspatial_contrast_slot("pudding snack weight 0 lb scale") == "K05_contrast_scale_flat_vs_internal_surge_split"
    assert select_canonical_nonspatial_contrast_slot("gaba glycine receptor lock") == "K04_contrast_dual_receptor_chemical_lock_panel"
    assert select_canonical_arrow_slot("doorway sever", prefer_v1_2=True) == "C03b_spatial_doorway_sever_with_prop"
    assert select_canonical_arrow_slot("doorway sever", prefer_v1_2=False) == "C03_arrow_doorway_sever_gap"

    # Unapproved candidate v1_2 manifest must raise CanonicalAssetError
    v12_root = tmp_path / "v1_2"
    (v12_root / "candidates" / "J01_hook_mode1_daily_action_xray_alert").mkdir(parents=True)
    (v12_root / "candidates" / "K06_contrast_a12_dual_brain_state_transition_pair").mkdir(parents=True)
    j01_p = v12_root / "candidates" / "J01_hook_mode1_daily_action_xray_alert" / "cand_01.png"
    k06_s = v12_root / "candidates" / "K06_contrast_a12_dual_brain_state_transition_pair" / "cand_01_start.png"
    k06_e = v12_root / "candidates" / "K06_contrast_a12_dual_brain_state_transition_pair" / "cand_01_end.png"
    j01_p.write_bytes(b"PNG_J01_CAND01")
    k06_s.write_bytes(b"PNG_K06_START")
    k06_e.write_bytes(b"PNG_K06_END")
    j01_sha = hashlib.sha256(j01_p.read_bytes()).hexdigest()
    k06_s_sha = hashlib.sha256(k06_s.read_bytes()).hexdigest()
    k06_e_sha = hashlib.sha256(k06_e.read_bytes()).hexdigest()

    cand_manifest = {
        "version": "v1.2",
        "status": "candidate",
        "sha256_locked": False,
        "slots": [
            {
                "slot_id": "J01_hook_mode1_daily_action_xray_alert",
                "category": "J_hooks",
                "status": "candidate",
                "candidates": [{"filename": "cand_01.png", "status": "candidate", "sha256_locked": False}],
            }
        ],
    }
    (v12_root / "manifest.json").write_text(json.dumps(cand_manifest), encoding="utf-8")
    with pytest.raises(CanonicalAssetError, match="status='candidate'"):
        resolve_canonical_approved_slot("J01_hook_mode1_daily_action_xray_alert", version="v1_2", custom_root=v12_root)

    # Approved v1_2 manifest resolves both single slot (J01) and Start+End pair (K06) with SHA-256 verification
    appr_manifest = {
        "version": "v1.2",
        "status": "approved",
        "sha256_locked": True,
        "slots": [
            {
                "slot_id": "J01_hook_mode1_daily_action_xray_alert",
                "category": "J_hooks",
                "status": "approved",
                "approved_filename": "cand_01.png",
                "approved_rel_path": "candidates/J01_hook_mode1_daily_action_xray_alert/cand_01.png",
                "approved_sha256": j01_sha,
                "candidates": [{"filename": "cand_01.png", "status": "approved", "sha256_locked": True}],
            },
            {
                "slot_id": "K06_contrast_a12_dual_brain_state_transition_pair",
                "category": "K_nonspatial_contrast",
                "asset_type": "start_end_transition_pair",
                "status": "approved",
                "approved_start_filename": "cand_01_start.png",
                "approved_start_rel_path": "candidates/K06_contrast_a12_dual_brain_state_transition_pair/cand_01_start.png",
                "approved_start_sha256": k06_s_sha,
                "approved_end_filename": "cand_01_end.png",
                "approved_end_rel_path": "candidates/K06_contrast_a12_dual_brain_state_transition_pair/cand_01_end.png",
                "approved_end_sha256": k06_e_sha,
                "candidates": [{"filename": "cand_01_start.png", "status": "approved", "sha256_locked": True}],
            },
        ],
    }
    (v12_root / "manifest.json").write_text(json.dumps(appr_manifest), encoding="utf-8")
    r_j01 = resolve_canonical_approved_slot("J01_hook_mode1_daily_action_xray_alert", version="v1.2", custom_root=v12_root)
    assert r_j01["library_version"] == "v1_2"
    assert r_j01["sha256"] == j01_sha
    r_k06 = resolve_canonical_transition_pair("K06_contrast_a12_dual_brain_state_transition_pair", version="v1_2", custom_root=v12_root)
    assert r_k06["start"]["sha256"] == k06_s_sha
    assert r_k06["end"]["sha256"] == k06_e_sha

    # Workspace list_all_approved_canonical_slots returns 84 active slots (v1 27 + v1_1 43 + v1_2 14)
    approved_live = list_all_approved_canonical_slots(verify_sha256=False)
    assert len(approved_live) == 84


def test_r87_lock2_gate1_and_gate2_viewer_common_sense_booleans(tmp_path: Path) -> None:
    from pipeline.storage import compute_sha256
    from pipeline.posthoc_qa import validate_posthoc_semantic_review
    from pipeline.ref_qa import (
        REF_IMAGES_DIRNAME,
        REF_SEMANTIC_REVIEW_FILENAME,
        validate_semantic_review,
        write_semantic_review_template,
    )

    proj = tmp_path / "v8_ep13_lock2_test"
    ref_dir = proj / "03_visuals" / REF_IMAGES_DIRNAME
    asm_dir = proj / "05_assembly"
    ref_dir.mkdir(parents=True)
    asm_dir.mkdir(parents=True)
    (proj / "03_visuals" / "visual_plan.json").write_text(
        json.dumps({"style_profile": "expressive_25d_v8", "r87_mode": True}),
        encoding="utf-8",
    )

    # Gate 1: reference_semantic_review.json
    img1 = ref_dir / "ref_clip_01.png"
    img1.write_bytes(b"FAKE_PNG_CLIP_01")
    sha1 = compute_sha256(img1)
    specs = [{"ref_id": "ref_clip_01", "filename": "ref_clip_01.png", "clip_number": 1, "setting": "brain_void"}]
    tmpl_p = write_semantic_review_template(proj, specs)
    tmpl_doc = json.loads(tmpl_p.read_text(encoding="utf-8"))
    chk_keys = tmpl_doc["images"]["ref_clip_01"]["checks"]
    assert "silent_3s_scroll_stop" in chk_keys
    assert "narration_visual_logic_match" in chk_keys
    assert "thumbnail_to_0s_promise_kept" in chk_keys

    # Setting silent_3s_scroll_stop=False must fail Gate 1 validation (valid=False)
    tmpl_doc["reviewer"] = "@Research"
    tmpl_doc["images"]["ref_clip_01"]["image_sha256"] = sha1
    tmpl_doc["images"]["ref_clip_01"]["note"] = "Mode 1 pudding spoon cutaway shows amber striatum clearly."
    tmpl_doc["images"]["ref_clip_01"]["checks"] = {
        "realistic_brain_anatomy": True,
        "no_text_logo_or_watermark": True,
        "narration_visual_logic_match": True,
        "silent_3s_scroll_stop": False,
        "thumbnail_to_0s_promise_kept": True,
    }
    (ref_dir / REF_SEMANTIC_REVIEW_FILENAME).write_text(json.dumps(tmpl_doc), encoding="utf-8")
    g1_fail = validate_semantic_review(proj, specs)
    assert g1_fail["valid"] is False
    assert "ref_clip_01" in g1_fail["r87_common_sense_failed_ids"]

    # Setting all 3 True passes Gate 1
    tmpl_doc["images"]["ref_clip_01"]["checks"]["silent_3s_scroll_stop"] = True
    (ref_dir / REF_SEMANTIC_REVIEW_FILENAME).write_text(json.dumps(tmpl_doc), encoding="utf-8")
    g1_pass = validate_semantic_review(proj, specs)
    assert g1_pass["valid"] is True

    # Gate 2: posthoc_semantic_review.json
    rev_path = asm_dir / "posthoc_semantic_review.json"
    base_g2 = {
        "project_id": proj.name,
        "schema": "R64_posthoc_semantic_review_v1",
        "review_origin": "vlm_research_gate2",
        "reviewer": "@Research",
        "final_mp4_sha256": "abc123",
        "edl_sha256": "edl456",
        "cut_count": 1,
        "cuts": [
            {
                "cut_index": 1,
                "clip_index": 1,
                "intended_scene": "Pudding spoon Mode 1 brain hook.",
                "observed_visual_summary": "Crisp cream vinyl adult lifts glossy dessert spoon while translucent skull reveals solid matte amber striatum.",
                "auto_populated": False,
                "expresses_intended_meaning": True,
                "narration_visual_logic_match": True,
                "silent_3s_scroll_stop": True,
                "thumbnail_to_0s_promise_kept": False,
            }
        ],
    }
    rev_path.write_text(json.dumps(base_g2), encoding="utf-8")
    g2_fail = validate_posthoc_semantic_review(proj, "abc123", "edl456", 1)
    assert g2_fail["valid"] is False
    assert any("r87_viewer_common_sense_failed" in x for x in g2_fail["issues"])

    base_g2["cuts"][0]["thumbnail_to_0s_promise_kept"] = True
    rev_path.write_text(json.dumps(base_g2), encoding="utf-8")
    g2_pass = validate_posthoc_semantic_review(proj, "abc123", "edl456", 1)
    assert g2_pass["valid"] is True
