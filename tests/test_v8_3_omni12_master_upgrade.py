"""
Verification suite for Schema v8.3 (`unified_v8_3_omni12_master_plan.md`):
  - Component 0: 6-Pack Translucent 3D Human Brain Reference Anchor Pack (`cand_01..cand_06`)
  - Component 1 (`C2`, `C3`, `C8`, `C9`): Omni 1.2 Flash metadata, `flow_workspace.py` 24-credit parity,
    dynamic All-Omni episode budget (`compute_dynamic_omni_episode_budget`), 720p sharpening guard,
    and 0-credit `<= 2` active shard tab enforcement.
  - Component 2 (`M1`, `M4`, `M5`): Single-Start-Frame default (`populate_expressive_v8_reference_contract`),
    `f/8` deep-focus probe lens angles, and Blender `40°` Nodal Gaze-Lock Orbit + `axial_portal_dive`.
  - Component 3 (`M2`, `M3`, `M6`, `M7`, `M8`, `M9`, `F1~F5`, `C1`, `C4`, `C5`):
    `expression_acting_lexicon.json`, `ExpressiveReactionCloseupRule`, `ExpressiveRigidPhysicsRule`,
    `validate_v83_camera_and_acting_balance`, `lock_audio_durations_onto_visual_plan`,
    `split_sentences_at_keyword_beats`, `build_dual_harvest_edl_windows`, `verify_state_swap_hist_corr`,
    `resolve_spatial_metric_stamps`, and `audit_v8_channel_readiness` `<= 120.0s` fields.
"""

from __future__ import annotations

import numpy as np

from pipeline.config import (
    EXPRESSIVE_ACTING_LEXICON_PATH,
    EXPRESSIVE_V8_RIGID_PHYSICS_GRAMMARS,
    EXPRESSIVE_V8_SINGLE_START_FRAME_DEFAULT,
    EXPRESSIVE_V8_VISUAL_GRAMMARS,
    FLOW_ENABLE_720P_LANCZOS_UNSHARP,
    FLOW_OMNI_CREDIT_COST_NO_REF,
    FLOW_OMNI_CREDIT_COST_WITH_REF,
    FLOW_PRIMARY_OMNI_MODEL_KEY,
    FLOW_PRIMARY_OMNI_MODEL_LABEL,
    TRANSLUCENT_BRAIN_V8_CANDIDATE_FILENAMES,
    TRANSLUCENT_BRAIN_V8_REFS_DIRNAME,
    WORKSPACE_ROOT,
    compute_dynamic_omni_episode_budget,
)
from pipeline.depiction_rules import (
    ExpressiveReactionCloseupRule,
    ExpressiveRigidPhysicsRule,
    format_expression_acting_clause,
    load_expression_acting_lexicon,
)
from pipeline.diorama_assembler import (
    build_dual_harvest_edl_windows,
    lock_audio_durations_onto_visual_plan,
    resolve_spatial_metric_stamps,
    split_sentences_at_keyword_beats,
    verify_state_swap_hist_corr,
)
from pipeline.flow_prompt_builder import (
    assign_hero_omni_engines,
    build_expressive_v8_prompts,
    validate_v83_camera_and_acting_balance,
)
from pipeline.flow_workspace import (
    FLOW_OMNI_CREDIT_COST_NO_REF as WS_NO_REF,
    FLOW_OMNI_CREDIT_COST_WITH_REF as WS_WITH_REF,
)
from pipeline.porcelain_anchor_pack import (
    EXPRESSIVE_V8_PREVIS_CAMERA_ANGLES,
    populate_expressive_v8_reference_contract,
)
from pipeline.previs_blender import PREVIS_CAMERA_PRESETS
from pipeline.studio.uploader import StudioUploader


def test_component0_translucent_brain_6pack_staged():
    ref_dir = WORKSPACE_ROOT / "BCI_Shorts_Channel" / "reference_style_anchors" / TRANSLUCENT_BRAIN_V8_REFS_DIRNAME
    assert ref_dir.is_dir()
    assert len(TRANSLUCENT_BRAIN_V8_CANDIDATE_FILENAMES) == 6
    for fn in TRANSLUCENT_BRAIN_V8_CANDIDATE_FILENAMES:
        p = ref_dir / fn
        assert p.is_file(), f"Missing staged translucent brain ref: {p}"
        assert p.stat().st_size > 50_000


def test_component1_omni12_and_dynamic_budget_parity():
    assert FLOW_PRIMARY_OMNI_MODEL_KEY == "macaron_cookie"
    assert FLOW_PRIMARY_OMNI_MODEL_LABEL == "Omni 1.2 Flash"
    assert WS_NO_REF == 24
    assert WS_WITH_REF == FLOW_OMNI_CREDIT_COST_WITH_REF == 24
    assert FLOW_ENABLE_720P_LANCZOS_UNSHARP is False

    # 1,000 credits -> (1000 - 20) // 24 = 40 -> all 20 clips get 'omni'
    b_full = compute_dynamic_omni_episode_budget(1000, clip_count=20)
    assert b_full["all_omni_possible"] is True
    assert b_full["max_omni_clips"] == 20

    # 260 credits -> (260 - 20) // 24 = 10 clips
    b_mid = compute_dynamic_omni_episode_budget(260, clip_count=20)
    assert b_mid["max_omni_clips"] == 10
    assert b_mid["zero_credit_fallback_clips"] == 10

    # 16 credits -> 0 omni clips (all fallback to zero-credit)
    b_low = compute_dynamic_omni_episode_budget(16, clip_count=20)
    assert b_low["max_omni_clips"] == 0
    assert b_low["zero_credit_fallback_clips"] == 20


def test_component2_single_start_frame_default_and_previs_nodal_orbit():
    assert EXPRESSIVE_V8_SINGLE_START_FRAME_DEFAULT is True
    assert "object_portal_macro" not in EXPRESSIVE_V8_PREVIS_CAMERA_ANGLES
    assert "fpv_aperture_wide" in EXPRESSIVE_V8_PREVIS_CAMERA_ANGLES
    assert "axial_portal_dive" in PREVIS_CAMERA_PRESETS
    orbit_spec = PREVIS_CAMERA_PRESETS["orbital_3d_arc_sweep"]
    assert orbit_spec["arc_deg"] == 40.0
    assert orbit_spec["gaze_lock_target"] == "head_center"

    # Verify M1 Single-Start-Frame default when v8_3_mode=True
    dummy_plan = {
        "style_profile": "expressive_25d_v8",
        "v8_3_mode": True,
        "clips": [
            {"clip_number": i, "grammar": ("expressive_xray_brain" if i == 12 else "expressive_vinyl_world"), "portal_to_brain": (i == 12)}
            for i in range(1, 19)
        ],
    }
    populated = populate_expressive_v8_reference_contract(dummy_plan, daisy_chain_keyframes=False)
    for c in populated["clips"]:
        if c.get("portal_to_brain"):
            assert c.get("end_reference_image"), "Portal clip must retain End frame"
        else:
            assert c.get("end_reference_image") is None, "Non-portal v8.3 clip must use Single-Start-Frame (End=None)"
            assert c.get("single_start_frame_lock") is True


def test_component3_acting_lexicon_and_rigid_physics_grammars():
    assert EXPRESSIVE_ACTING_LEXICON_PATH.is_file()
    lex = load_expression_acting_lexicon()
    archetypes = lex.get("expressions", lex.get("archetypes", lex))
    assert len(archetypes) == 12
    assert "expressive_reaction_closeup" in EXPRESSIVE_V8_VISUAL_GRAMMARS

    first_expr_id = next(iter(archetypes.keys()))
    clause = format_expression_acting_clause(first_expr_id, speaker_role="narrator", compact=True)
    assert "2D ink" in clause or "ink" in clause.lower()

    react_scene = ExpressiveReactionCloseupRule.compose(
        expression_id=first_expr_id,
        speaker_role="mini_cortex",
        compact=True,
    )
    assert "Bust-up close-up" in react_scene

    for rg in EXPRESSIVE_V8_RIGID_PHYSICS_GRAMMARS:
        phys_txt = ExpressiveRigidPhysicsRule.compose(rg, subject_or_structure="Subject", compact=True)
        assert len(phys_txt.split()) >= 8


def test_component3_camera_balance_and_edl_helpers():
    # C4 camera balance validator
    good_clips = []
    for idx in range(1, 21):
        if idx in (1, 2, 3, 4):
            cam = "fpv_dive_glide"
        elif idx in (5, 6, 7, 8):
            cam = "orbital_3d_arc_sweep"
        elif idx in (9, 10, 11, 12):
            cam = "locked_tripod"
        else:
            cam = "gentle_push_in"
        good_clips.append(
            {
                "clip_number": idx,
                "camera_move": cam,
                "grammar": "expressive_reaction_closeup" if idx == 9 else "expressive_vinyl_world",
                "portal_to_brain": (idx == 4),
            }
        )
    assert validate_v83_camera_and_acting_balance(good_clips) == []

    # Orbit + portal_to_brain collision must fail R55-B
    bad_clips = [dict(c) for c in good_clips]
    bad_clips[4]["portal_to_brain"] = True  # idx=5 has orbital_3d_arc_sweep
    errs = validate_v83_camera_and_acting_balance(bad_clips)
    assert any("orbital_3d_arc_sweep" in e and "portal_to_brain" in e for e in errs)

    # M3 Audio-Before-Flow lock
    spans = [(0.0, 3.2), (3.2, 7.1), (7.1, 11.8)]
    vp = {"clips": [{"sentence_index": 1, "end_sentence_index": 1}, {"sentence_index": 2, "end_sentence_index": 3}]}
    locked_vp = lock_audio_durations_onto_visual_plan(vp, spans, enable_extended_durations=True)
    assert locked_vp["audio_before_flow_locked"] is True
    assert locked_vp["clips"][0]["render_sec"] == 4
    assert locked_vp["clips"][1]["render_sec"] == 10
    assert locked_vp["clips"][0]["forbid_slowmo_stretch"] is True

    # M6 Sub-sentence keyword beat cutter & dual harvest windows
    beats = split_sentences_at_keyword_beats(
        [(0.0, 5.4)],
        ["The researcher promised a second marshmallow, but walked out and broke that promise."],
        target_beat_sec=2.0,
    )
    assert len(beats) >= 2
    w1, w2 = build_dual_harvest_edl_windows(8.0)
    assert w1[1] < w2[0]

    # M8 State-swap hist_corr & M9 spatial metric stamps
    grad = np.linspace(20, 220, 64, dtype=np.uint8)
    img_a = np.dstack([np.tile(grad, (64, 1)), np.tile(grad[:, None], (1, 64)), np.full((64, 64), 110, dtype=np.uint8)])
    img_b = np.clip(img_a.astype(np.int16) + 2, 0, 255).astype(np.uint8)
    swap_res = verify_state_swap_hist_corr(img_a, img_b)
    assert swap_res["passed"] is True
    stamps = resolve_spatial_metric_stamps(
        {"spatial_metric_stamps": [{"label": "4x longer", "sentence_index": 2}]},
        spans,
    )
    assert stamps[0]["label"] == "4X LONGER"
    assert stamps[0]["start_sec"] == 3.2


def test_component3_studio_inventory_120s_fields():
    rep = StudioUploader.audit_v8_channel_readiness()
    inv = rep["format_inventory_audit"]
    assert "shorts_le_89_5s_count" in inv
    assert "v8_shorts_le_120s_count" in inv
    assert "legacy_gt_120s_count" in inv
