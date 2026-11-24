"""Unit tests for Rule R79-M: Snappy 2.5D Character Motion & State-A Keyframe Lock."""
from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np

from pipeline.config import (
    EXPRESSIVE_V8_CONTEXT_SPLIT_WORDS_RANGE,
    R79M_HUMAN_CUT_MAX_MAIN_SPEED,
    is_r79m_character_motion_plan,
)
from pipeline.depiction_rules import (
    EXPRESSIVE_V8_CAMERA_DESCRIPTORS,
    EXPRESSIVE_V8_COMPACT_CAMERA_DESCRIPTORS,
    FLOW_CAMERA_HARDWARE_NEGATIVE_GUARD,
    ExpressiveReactionCloseupRule,
    ExpressiveV8PromptComposer,
    format_expression_acting_clause,
    load_expression_acting_lexicon,
    validate_expressive_v8_scene,
)
from pipeline.assembler import _select_v7_source_window
from pipeline.episode_qa import verify_final_mp4_against_contract
from pipeline.prompt_builder import _compose_expressive_v8_context_split_scene


def test_r79m_lexicon_and_camera_descriptors_are_smudge_and_warp_free() -> None:
    assert EXPRESSIVE_V8_CONTEXT_SPLIT_WORDS_RANGE == (18, 64)
    lex = load_expression_acting_lexicon()
    exprs = lex.get("expressions") or {}
    assert len(exprs) == 12
    for exp_id in exprs:
        clause = format_expression_acting_clause(exp_id, speaker_role="narrator", compact=True)
        assert "ink eyes shift" not in clause.lower()
        assert "pupils dart" not in clause.lower()
        assert "snap" in clause.lower() or "soften" in clause.lower() or "curve" in clause.lower() or "perk" in clause.lower()
        errs = validate_expressive_v8_scene(
            f"Continuous 3D perspective push-in gliding toward the subject reaction. The 2.5D young man leans back as {clause}. Silent voice track.",
            grammar="expressive_reaction_closeup",
            camera_move="gentle_push_in",
            image_conditioned=True,
        )
        assert errs == [], f"Unexpected issues for {exp_id}: {errs}"

    for desc in (
        EXPRESSIVE_V8_CAMERA_DESCRIPTORS["dolly_zoom_vertigo"],
        EXPRESSIVE_V8_COMPACT_CAMERA_DESCRIPTORS["dolly_zoom_vertigo"],
    ):
        assert "warping background depth" not in desc.lower()
        assert "straight and rigid" in desc.lower()


def test_r79m_context_split_preserves_subject_and_action_verb() -> None:
    # 1. expressive_reaction_closeup puts cast + gross-motor action first without losing verb
    spec_closeup = {
        "grammar": "expressive_reaction_closeup",
        "camera_move": "gentle_push_in",
        "environment": "bright sunlit California dining room oak table with a warm ceramic teacup and framed family portraits",
        "cast": "a clothed 2.5D matte cream-white vinyl young man in a navy jacket across from his older mother in a cardigan",
        "action": "releases his teacup, snaps his upper body sharply back against the chair backrest, and raises both hands defensively",
        "expression_id": "double_blink_shock",
    }
    scene_body = _compose_expressive_v8_context_split_scene(spec_closeup)
    full_prompt = ExpressiveV8PromptComposer.compose_clip_prompt(
        scene_body,
        grammar="expressive_reaction_closeup",
        camera_move="gentle_push_in",
        context_split=True,
    )
    core = full_prompt.replace(FLOW_CAMERA_HARDWARE_NEGATIVE_GUARD, "").strip()
    assert "releases his teacup" in core
    assert "raises both hands" in core
    assert validate_expressive_v8_scene(full_prompt, grammar="expressive_reaction_closeup", image_conditioned=True) == []

    # 2. expressive_vinyl_world with bare verb action automatically prepends concise cast subject
    spec_vinyl = {
        "grammar": "expressive_vinyl_world",
        "camera_move": "gentle_push_in",
        "cast": "a clothed 2.5D matte cream-white vinyl neurologist in a white lab coat",
        "action": "sets the framed portrait onto the wooden easel and points crisply at the flat green monitor line",
        "consequence": "the seated young man leans forward and firmly shakes his head once",
    }
    vinyl_body = _compose_expressive_v8_context_split_scene(spec_vinyl)
    assert vinyl_body.startswith("The 2.5D neurologist in a white lab coat sets")
    vinyl_prompt = ExpressiveV8PromptComposer.compose_clip_prompt(
        vinyl_body,
        grammar="expressive_vinyl_world",
        camera_move="gentle_push_in",
        context_split=True,
    )
    assert validate_expressive_v8_scene(vinyl_prompt, grammar="expressive_vinyl_world", image_conditioned=True) == []


def test_r79m_validator_blocks_dangling_truncation_smudge_warp_and_verbless_human_cuts() -> None:
    # Dangling preposition truncation (`in.`)
    errs_trunc = validate_expressive_v8_scene(
        "Continuous 3D perspective push-in gliding toward the subject reaction. "
        "Bust-up close-up: the 2.5D young man sits across from his older mother in. Silent voice track.",
        grammar="expressive_reaction_closeup",
        image_conditioned=True,
    )
    assert any("[r79m_dangling_truncation]" in e for e in errs_trunc)

    # Banned smudge phrase (`ink eyes shift`)
    errs_smudge = validate_expressive_v8_scene(
        "Continuous 3D perspective push-in gliding toward the subject reaction. "
        "The 2.5D young man leans back as 2D charcoal ink eyes shift. Silent voice track.",
        grammar="expressive_reaction_closeup",
        image_conditioned=True,
    )
    assert any("[r79m_ink_smudge_ban]" in e for e in errs_smudge)

    # Banned wall-warp phrase (`warping background depth`)
    errs_warp = validate_expressive_v8_scene(
        "3D vertigo perspective push-in warping background depth behind the subject. "
        "The 2.5D young man flips the framed portrait face-down. Silent voice track.",
        grammar="expressive_vinyl_world",
        image_conditioned=True,
    )
    assert any("[r79m_wall_warp_ban]" in e for e in errs_warp)

    # Verbless mannequin description
    errs_noverb = validate_expressive_v8_scene(
        "Continuous 3D perspective push-in gliding toward the subject reaction. "
        "Bust-up close-up of a 2.5D young man in a navy jacket at an oak dining table. Silent voice track.",
        grammar="expressive_reaction_closeup",
        image_conditioned=True,
    )
    assert any("[r79m_missing_action_verb]" in e for e in errs_noverb)


def test_r79m_clause_safe_trim_never_leaves_dangling_preposition() -> None:
    overlong_body = (
        "The 2.5D young man in a navy jacket sets the framed family portrait firmly flat on the oak desk, "
        "leans back into the wooden chair, and folds both arms tightly across his chest, "
        "while crisp 2D black ink eyebrows snap into a narrow suspicious squint on the smooth matte cream-white head, "
        "and warm afternoon sunlight streams softly across the bookshelves behind the tidy clinical study in"
    )
    prompt = ExpressiveV8PromptComposer.compose_clip_prompt(
        overlong_body,
        grammar="expressive_reaction_closeup",
        camera_move="gentle_push_in",
        context_split=True,
    )
    errs = validate_expressive_v8_scene(prompt, grammar="expressive_reaction_closeup", image_conditioned=True)
    assert errs == [], f"Clause-safe trimmed prompt had validation errors: {errs}\nPrompt: {prompt}"


def test_r79m_source_window_caps_main_speed_below_ceiling(tmp_path: Path) -> None:
    assert is_r79m_character_motion_plan({"project_id": "v8_ep08_capgras_imposter_delusion_r77"}) is True
    assert is_r79m_character_motion_plan({"project_id": "v8_ep06_bedtime_todo_list_sleep"}) is False

    dummy_clip = tmp_path / "clip_3.mp4"
    # Even if full_trajectory_span is set on an 8.0s clip for a 3.53s human cut, main_speed must stay <= 1.45x
    s0, span = _select_v7_source_window(
        dummy_clip,
        clip_dur=8.0,
        out_dur=3.53,
        spec={"full_trajectory_span": True, "_r79m_snappy_human": True},
    )
    assert s0 >= 0.05
    assert span / 3.53 <= R79M_HUMAN_CUT_MAX_MAIN_SPEED + 1e-4


def test_r79m_dq_gate_flags_static_human_cut_and_passes_snappy_cut(tmp_path: Path) -> None:
    p_dir = tmp_path / "v8_ep99_r79m_unit_check"
    (p_dir / "02_script").mkdir(parents=True)
    (p_dir / "03_visuals").mkdir(parents=True)
    (p_dir / "04_audio").mkdir(parents=True)
    (p_dir / "05_assembly").mkdir(parents=True)

    sents = [f"Sentence {i} about the clinical neurological case." for i in range(1, 16)]
    (p_dir / "02_script" / "script.json").write_text(
        json.dumps(
            {
                "project_id": p_dir.name,
                "style_profile": "expressive_25d_v8",
                "sentences": sents,
            }
        ),
        encoding="utf-8",
    )
    fixture_clips = [
        {
            "id": 1,
            "clip_number": 1,
            "sentence_index": 1,
            "end_sentence_index": 1,
            "grammar": "expressive_vinyl_world",
            "camera_move": "gentle_push_in",
            "cast": "a clothed 2.5D matte cream-white vinyl young man in a navy jacket",
            "action": "recoils sharply back from the oak dining table and raises both hands",
            "render_engine": "google_flow",
        }
    ] + [
        {
            "id": i,
            "clip_number": i,
            "sentence_index": i,
            "end_sentence_index": i,
            "grammar": "brain_simulator_3d",
            "camera_move": "circuit_cooperation_drone",
            "brain_clip": True,
            "scene": "Clinical 3D MNI152 brain cortex pathway pulse in clean dark studio space",
            "action": "Clinical 3D MNI152 brain cortex pathway pulse in clean dark studio space",
            "render_engine": "google_flow",
        }
        for i in range(2, 16)
    ]
    (p_dir / "03_visuals" / "visual_plan.json").write_text(
        json.dumps(
            {
                "schema": 8,
                "project_id": p_dir.name,
                "style_profile": "expressive_25d_v8",
                "r76_mode": True,
                "r79m_character_motion": True,
                "clips": fixture_clips,
            }
        ),
        encoding="utf-8",
    )
    (p_dir / "04_audio" / "voice_report.json").write_text(
        json.dumps(
            {
                "engine": "elevenlabs_v4",
                "voice_preset": "el_siren_v4",
                "total_duration_sec": 3.0,
                "sentences": [{"index": 1, "duration_sec": 3.0}],
            }
        ),
        encoding="utf-8",
    )
    (p_dir / "05_assembly" / "edit_decision_list.json").write_text(
        json.dumps(
            {
                "schema": 8,
                "style_profile": "expressive_25d_v8",
                "fps": 30,
                "total_duration_sec": 3.0,
                "cuts": [
                    {
                        "cut_index": 1,
                        "clip_index": 1,
                        "sentence_index": 1,
                        "end_sentence_index": 1,
                        "mode": "single",
                        "grammar": "expressive_vinyl_world",
                        "camera_move": "gentle_push_in",
                        "out_start_sec": 0.0,
                        "out_end_sec": 3.0,
                        "duration_sec": 3.0,
                        "src_start_sec": 0.16,
                        "src_end_sec": 3.91,
                        "main_speed": 1.25,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    mp4_p = p_dir / "05_assembly" / "final_shorts_1080x1920.mp4"
    # Render a brisk moving character rectangle across 90 frames @ 30fps (> 8192 bytes so non-synth path runs)
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    vw = cv2.VideoWriter(str(mp4_p), fourcc, 30.0, (540, 960))
    rng = np.random.default_rng(42)
    bg = rng.integers(90, 150, size=(960, 540, 3), dtype=np.uint8)
    for fi in range(90):
        frm = bg.copy()
        cx = int(170 + 180 * (fi / 89.0))
        cy = int(380 + 40 * np.sin(fi * 0.25))
        cv2.rectangle(frm, (cx - 75, cy - 150), (cx + 75, cy + 150), (240, 240, 245), -1)
        cv2.circle(frm, (cx, cy - 90), 36, (30, 40, 80), -1)
        vw.write(frm)
    vw.release()
    assert mp4_p.stat().st_size >= 8_192

    rep = verify_final_mp4_against_contract(p_dir, save_report=False, run_asr_sync=False)
    r79_gate = rep["gates"]["DQ_R79_human_character_motion"]
    assert r79_gate["passed"] is True, f"Expected active character cut to pass R79-M: {r79_gate}"
    assert r79_gate["cuts"][0]["subj_p90_px"] >= 2.0

    # Now render a frozen/static mannequin frame across 90 frames and verify DQ_R79_human_character_motion fails
    vw_static = cv2.VideoWriter(str(mp4_p), fourcc, 30.0, (540, 960))
    frm_static = bg.copy()
    cv2.rectangle(frm_static, (195, 230), (345, 530), (240, 240, 245), -1)
    for _ in range(90):
        vw_static.write(frm_static)
    vw_static.release()
    rep_static = verify_final_mp4_against_contract(p_dir, save_report=False, run_asr_sync=False)
    assert rep_static["gates"]["DQ_R79_human_character_motion"]["passed"] is False
