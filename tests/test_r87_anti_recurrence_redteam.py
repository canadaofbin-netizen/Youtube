"""
Rule R87 Anti-Recurrence Red-Team Negative Regression Suite (Lock 1):
  Permanently seals 4 historical failure fixtures so `prompt-gate` / dossier seeding MUST reject them,
  and locks Protected Winners channel invariants against accidental regressions.
"""
from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
import pytest

from pipeline import config as cfg
from pipeline.dynamic_episode_qa import (
    _is_unified_brain_cut,
    verify_final_mp4_against_contract,
)
from pipeline.prompt_quality_v5 import (
    validate_production_diorama_v6,
    validate_r87_hook_contract,
    validate_r87_spatial_arrow_eligibility,
    validate_r87_turnaround_sheet_start_frame_ban,
)
from pipeline.research_dossier import diorama_seed_from_dossier, infer_spatial_arrow_eligibility


def test_lock1_a_ep10_nonspatial_sleep_pill_with_street_arrow_must_fail() -> None:
    """Fixture (a): Ep #10-style non-spatial sleep pill plan injecting spatial_3d_arrow_diorama MUST FAIL (R87-A)."""
    ep10_bad_plan = {
        "style_profile": "expressive_25d_v8",
        "project_id": "v8_ep13_sleep_pill_regression",
        "r87_mode": True,
        "spatial_arrow_eligible": False,
        "clips": [
            {
                "clip_number": 15,
                "sentence_index": 15,
                "grammar": "spatial_3d_arrow_diorama",
                "arrow_3d_mode": "dual_speed_race_lanes",
                "spatial_relay_cut": True,
                "scene": "Sunlit gray architectural stone lane with cyan and red arrows racing upward.",
            }
        ],
    }
    issues = validate_r87_spatial_arrow_eligibility(ep10_bad_plan, ep10_bad_plan["clips"])
    assert issues, "Non-spatial sleep-pill plan with spatial_3d_arrow_diorama MUST fail R87-A!"
    assert any("[r87_a_non_spatial_arrow_banned]" in x for x in issues)


def test_lock1_b_spatial_side_by_side_single_arrow_or_empty_alley_must_fail() -> None:
    """Fixture (b): Spatial topic with 'side by side' narration + single arrow OR empty gray alley MUST FAIL (R87-A)."""
    bad_spatial_plan = {
        "style_profile": "expressive_25d_v8",
        "project_id": "v8_ep14_spatial_regression",
        "r87_mode": True,
        "spatial_arrow_eligible": True,
        "clips": [
            {
                "clip_number": 17,
                "sentence_index": 1,
                "grammar": "spatial_3d_arrow_diorama",
                "arrow_3d_mode": "fixed_linear_corridor",
                "canonical_slot_id": "C01_arrow_straight_corridor",
                "scene": "Empty gray alley with one single red extruded arrow bar.",
            }
        ],
    }
    lines = ["Put both sleep conditions side by side and watch the rinse speed."]
    issues = validate_r87_spatial_arrow_eligibility(bad_spatial_plan, bad_spatial_plan["clips"], lines=lines)
    joined = "\n".join(issues)
    assert "[r87_a_empty_alley_banned]" in joined
    assert "[r87_a_single_arrow_comparison_ban]" in joined
    assert "[r87_a_missing_prop_anchor]" in joined
    assert "[r87_lock3_spatial_canonical_anchor]" in joined


def test_lock1_c_ep7_ep10_why_do_imagine_and_static_bed_desk_cut1_must_fail() -> None:
    """Fixture (c): Ep #7/#10-style 'Why do/did'/'Imagine' openers or static bed/desk Cut #1 MUST FAIL (R87-H)."""
    for bad_s01 in (
        "Why do eight hours on a sleep pill still leave your head heavy?",
        "Why did this man trust his mom on the phone yet call her fake?",
        "Imagine waking from a deep sleep in your room right now.",
    ):
        bad_plan = {
            "style_profile": "expressive_25d_v8",
            "project_id": "v8_ep13_hook_regression",
            "r87_mode": True,
            "opening_mode": "paradox_question",
            "hook_visual_mode": "mode1_daily_xray_shock",
            "hook_title_text": "PUMP MUTED?!",
            "clips": [
                {
                    "clip_number": 1,
                    "sentence_index": 1,
                    "duration_sec": 2.40,
                    "canonical_slot_id": "J02_hook_mode1_bedside_sleep_anomaly",
                    "scene": "Static sad figure sitting on the edge of a bed rubbing his temples quietly.",
                    "action": "Sits quietly on bed edge rubbing temples.",
                }
            ],
        }
        issues = validate_r87_hook_contract(
            bad_plan,
            bad_plan["clips"],
            lines=[bad_s01],
            script_doc={"r87_mode": True, "opening_mode": "paradox_question"},
        )
        joined = "\n".join(issues)
        assert "[r87_h1_cut1_static_sit_ban]" in joined, f"Static bed Cut #1 must fail for: {bad_s01}"
        assert "[r87_h2_s01_prefix_ban]" in joined, f"Banned prefix must fail for: {bad_s01}"


def test_lock1_d_dossier_seeding_never_auto_injects_r80_on_nonspatial_dossiers(tmp_path: Path) -> None:
    """Fixture (d): Non-spatial dossier (even if legacy spatial_contrast_spec exists) MUST NOT auto-seed r80_mode=True."""
    slug = "snack_reward_nonspatial_test"
    ddir = tmp_path / slug
    ddir.mkdir(parents=True)
    (ddir / "dossier.json").write_text(
        json.dumps(
            {
                "slug": slug,
                "topic": "Daily ultraprocessed pudding snack rewires human brain dopamine reward",
                "domain": "habits",
                "visual_mode": "HYBRID",
            }
        ),
        encoding="utf-8",
    )
    (ddir / "01_sources.json").write_text(
        json.dumps({"sources": [{"type": "primary", "doi": "10.1016/j.cmet.2023.02.015"}]}),
        encoding="utf-8",
    )
    # Deliberately include legacy spatial_contrast_spec (as all 135 legacy dossiers did)
    (ddir / "03_visual_reference.json").write_text(
        json.dumps(
            {
                "scenes": [],
                "spatial_contrast_spec": {
                    "landmark_or_object_a": "Grocery aisle snack shelf",
                    "landmark_or_object_b": "Plain yogurt shelf",
                    "arrow_3d_mode": "adaptive_landmark_zigzag",
                },
            }
        ),
        encoding="utf-8",
    )
    (ddir / "05_plain_language.json").write_text(
        json.dumps({"one_sentence_story": "One daily snack rewired striatum reward without weight gain."}),
        encoding="utf-8",
    )
    (ddir / "06_brain_link.json").write_text(json.dumps({"links": []}), encoding="utf-8")

    seeded = diorama_seed_from_dossier(slug, root=tmp_path, schema_version=8, style_profile="expressive_25d_v8", write_draft=False)
    assert seeded["spatial_arrow_eligible"] is False
    assert seeded["r80_mode"] is False
    assert seeded["contrast_visual_mode"] == "non_spatial_prop_and_brain"
    assert "non_spatial_contrast_spec" in seeded
    assert "spatial_contrast_spec" not in seeded

    # Positive sanity check: true London taxi navigation dossier IS eligible
    assert infer_spatial_arrow_eligibility("Maguire 2000 London taxi driver street navigation hippocampus") is True
    assert infer_spatial_arrow_eligibility("Radvansky 2011 walking through a doorway effect event boundary") is True
    assert infer_spatial_arrow_eligibility("Hauglund 2025 zolpidem sleep pill glymphatic brain wash") is False


def test_lock1_protected_winners_channel_invariants() -> None:
    """Protected Winners Permanent Invariants: prevent silent quality regressions in config.py."""
    assert cfg.EXPRESSIVE_V8_SUBTITLE_FONT_SIZE >= 80
    assert cfg.EXPRESSIVE_V8_SUBTITLE_HIGHLIGHT_HEX.upper() != "#FFFFFF"
    assert cfg.EXPRESSIVE_V8_DEFAULT_OPENING_MODE != "paradox_question"
    assert cfg.UNMANNED_QA_SIGNOFF_DEFAULT is False
    assert cfg.FLOW_AUTO_CLEANUP_ON_SUCCESS is False


def test_lock1_e_r85_flow_brain_cuts_counted_in_dq_r76_unified_brain_share(tmp_path: Path) -> None:
    """Fix A1 Regression: DQ_R76_unified_brain_share MUST count R85+ Google Flow expressive_xray_brain cuts accurately (never 0%), while NOT miscounting Cut #1 J01 expressive_vinyl_world."""
    # Direct helper checks
    assert _is_unified_brain_cut({"grammar": "expressive_xray_brain", "render_engine": "google_flow"}) is True
    assert _is_unified_brain_cut({"grammar": "brain_simulator_3d", "render_engine": "blender_3d_simulator"}) is True
    assert _is_unified_brain_cut({"grammar": "expressive_vinyl_world", "brain_clip": True}) is True
    assert _is_unified_brain_cut({"grammar": "expressive_vinyl_world", "r85_brain_clip": True}) is True
    assert (
        _is_unified_brain_cut(
            {"grammar": "expressive_vinyl_world", "render_engine": "google_flow", "brain_clip": False},
            {"canonical_slot_id": "J01_hook_mode1_daily_action_xray_alert", "grammar": "expressive_vinyl_world", "brain_clip": False},
        )
        is False
    )

    # End-to-end verify_final_mp4_against_contract on an R85+/R87+ project (12.0s total, 5.4s Flow brain = 45.0%)
    proj = tmp_path / "v8_ep13_brain_share_regression"
    (proj / "02_script").mkdir(parents=True)
    (proj / "03_visuals").mkdir(parents=True)
    (proj / "04_audio").mkdir(parents=True)
    (proj / "05_assembly").mkdir(parents=True)

    mp4_p = proj / "05_assembly" / "final_shorts_1080x1920.mp4"
    vw = cv2.VideoWriter(str(mp4_p), cv2.VideoWriter_fourcc(*"mp4v"), 30.0, (270, 480))
    for fi in range(360):
        frm = np.full((480, 270, 3), (185, 195, 205), dtype=np.uint8)
        cx = 60 + (fi % 120)
        cv2.rectangle(frm, (cx, 140), (cx + 80, 340), (235, 238, 240), -1)
        vw.write(frm)
    vw.release()
    assert mp4_p.stat().st_size >= 8_192

    vp = {
        "schema": 8,
        "profile": "neuro_diorama",
        "style_profile": "expressive_25d_v8",
        "r85_mode": True,
        "r87_mode": True,
        "spatial_arrow_eligible": False,
        "hook_visual_mode": "mode1_daily_xray_shock",
        "hook_title_text": "1 SNACK\\NREWIRED IT!",
        "clips": [
            {
                "clip_number": 1,
                "sentence_index": 1,
                "grammar": "expressive_vinyl_world",
                "render_engine": "google_flow",
                "brain_clip": False,
                "camera_move": "gentle_push_in",
                "canonical_slot_id": "J01_hook_mode1_daily_action_xray_alert",
                "scene": "Bald cream-white vinyl adult lifts a chocolate pudding spoon toward mouth.",
            },
            {
                "clip_number": 2,
                "sentence_index": 2,
                "grammar": "expressive_exterior_establishing",
                "render_engine": "google_flow",
                "brain_clip": False,
                "camera_move": "drone_aerial_approach",
                "scene": "120ft aerial drone glides over Max Planck Cologne research campus rooftops.",
            },
            {
                "clip_number": 3,
                "sentence_index": 3,
                "grammar": "expressive_xray_brain",
                "render_engine": "google_flow",
                "brain_clip": True,
                "r85_brain_clip": True,
                "camera_move": "gentle_push_in",
                "brain_region": "ventral striatum",
                "scene": "Ep #31 matte silver-white 3D cutaway brain highlights the ventral striatum in solid matte amber-gold.",
            },
            *[
                {
                    "clip_number": i,
                    "sentence_index": i,
                    "grammar": "expressive_xray_brain" if i % 2 == 0 else "expressive_vinyl_world",
                    "render_engine": "google_flow",
                    "brain_clip": (i % 2 == 0),
                    "r85_brain_clip": (i % 2 == 0),
                    "camera_move": "gentle_push_in",
                    "brain_region": "ventral striatum" if i % 2 == 0 else "",
                    "scene": (
                        "Ep #31 matte silver-white 3D cutaway brain highlights the ventral striatum."
                        if i % 2 == 0
                        else "Bald cream-white vinyl adult taps a ceramic spoon on the oak lab table."
                    ),
                }
                for i in range(4, 19)
            ],
        ],
    }
    (proj / "03_visuals" / "visual_plan.json").write_text(json.dumps(vp), encoding="utf-8")
    (proj / "02_script" / "script.json").write_text(
        json.dumps(
            {
                "schema": 8,
                "style_profile": "expressive_25d_v8",
                "r85_mode": True,
                "r87_mode": True,
                "sentences": [
                    "One daily snack rewired healthy brains without adding weight!",
                    "Researchers in Cologne tracked volunteers over eight weeks.",
                    "Brain scans showed a sharp surge inside the striatum.",
                    *[f"Follow-up scan step {i} confirmed the reward shift." for i in range(4, 19)],
                ],
            }
        ),
        encoding="utf-8",
    )
    (proj / "04_audio" / "voice_report.json").write_text(
        json.dumps({"engine": "elevenlabs_v4", "speech_end_sec": 12.0}),
        encoding="utf-8",
    )
    edl = {
        "schema": 8,
        "fps": 30,
        "total_duration_sec": 12.0,
        "cuts": [
            {
                "cut_index": 1,
                "clip_index": 1,
                "sentence_index": 1,
                "grammar": "expressive_vinyl_world",
                "render_engine": "google_flow",
                "brain_clip": False,
                "camera_move": "gentle_push_in",
                "out_start_sec": 0.0,
                "out_end_sec": 2.2,
                "duration_sec": 2.2,
                "src_start_sec": 0.0,
                "src_end_sec": 2.2,
                "main_speed": 1.0,
            },
            {
                "cut_index": 2,
                "clip_index": 2,
                "sentence_index": 2,
                "grammar": "expressive_exterior_establishing",
                "render_engine": "google_flow",
                "brain_clip": False,
                "camera_move": "drone_aerial_approach",
                "out_start_sec": 2.2,
                "out_end_sec": 6.6,
                "duration_sec": 4.4,
                "src_start_sec": 0.0,
                "src_end_sec": 4.4,
                "main_speed": 1.0,
            },
            {
                "cut_index": 3,
                "clip_index": 3,
                "sentence_index": 3,
                "grammar": "expressive_xray_brain",
                "render_engine": "google_flow",
                "brain_clip": True,
                "r85_brain_clip": True,
                "camera_move": "gentle_push_in",
                "out_start_sec": 6.6,
                "out_end_sec": 12.0,
                "duration_sec": 5.4,
                "src_start_sec": 0.0,
                "src_end_sec": 5.4,
                "main_speed": 1.0,
            },
        ],
    }
    (proj / "05_assembly" / "edit_decision_list.json").write_text(json.dumps(edl), encoding="utf-8")

    rep = verify_final_mp4_against_contract(proj, run_asr_sync=False, save_report=False)
    dq_share = rep["advisory_gates"]["DQ_R76_unified_brain_share"]
    assert dq_share["brain_duration_sec"] == pytest.approx(5.4, abs=0.05)
    assert dq_share["total_duration_sec"] == pytest.approx(12.0, abs=0.05)
    assert dq_share["brain_duration_share"] == pytest.approx(0.45, abs=0.005)
    assert dq_share["passed"] is True
    # Also confirm DQ_R79_human_character_motion skips R85 Google Flow brain cut #3 cleanly
    r79_cuts = rep["advisory_gates"]["DQ_R79_human_character_motion"]["cuts"]
    assert all(int(c["clip_index"]) != 3 for c in r79_cuts)


def test_lock1_f_turnaround_sheet_b01_b04_direct_start_frame_ban() -> None:
    """Fix A2 Regression: B01-B04 3-view character turnaround sheets MUST fail prompt-gate when bound directly as start_frame_image / VIDEO_FRAMES reference_image / canonical_slot_id without custom single-frame reference_image, while ALLOWED in conditioned_on / Ingredients and B05-B10 single-pose anchors remain ALLOWED."""
    turnaround_slots = (
        "B01_base_adult_male_turnaround",
        "B02_base_adult_female_turnaround",
        "B03_base_older_adult_turnaround",
        "B04_base_child_turnaround",
    )

    for slot in turnaround_slots:
        fname = f"canonical_{slot}.png"

        # 1. Direct reference_image with single_start_frame_lock=True -> MUST FAIL
        plan_lock = {
            "style_profile": "expressive_25d_v8",
            "r87_mode": True,
            "clips": [
                {
                    "clip_number": 6,
                    "grammar": "expressive_vinyl_world",
                    "reference_image": fname,
                    "single_start_frame_lock": True,
                    "scene": "Bald vinyl adult reaches for dessert cup.",
                }
            ],
        }
        errs_lock = validate_r87_turnaround_sheet_start_frame_ban(plan_lock)
        assert any("[r87_turnaround_sheet_start_frame_ban]" in e for e in errs_lock), f"Must fail single_start_frame_lock for {slot}: {errs_lock}"

        # 2. Direct start_frame_image -> MUST FAIL (also via validate_r87_hook_contract!)
        plan_sf = {
            "style_profile": "expressive_25d_v8",
            "r87_mode": True,
            "opening_mode": "immediate_brain_shock",
            "hook_visual_mode": "mode1_daily_xray_shock",
            "hook_title_text": "1 SNACK\\NREWIRED IT!",
            "clips": [
                {
                    "clip_number": 1,
                    "duration_sec": 2.2,
                    "canonical_slot_id": "J01_hook_mode1_daily_action_xray_alert",
                    "reference_image": "canonical_J01_hook_mode1_daily_action_xray_alert.png",
                    "scene": "Mode 1 translucent skull snack hook.",
                },
                {
                    "clip_number": 2,
                    "grammar": "expressive_vinyl_world",
                    "start_frame_image": fname,
                    "scene": "Bald vinyl adult reacts at lab table.",
                },
            ],
        }
        errs_hook = validate_r87_hook_contract(
            plan_sf,
            plan_sf["clips"],
            lines=["One daily pudding cup rewired healthy brains fast!"],
            script_doc={"r87_mode": True, "opening_mode": "immediate_brain_shock"},
        )
        assert any("[r87_turnaround_sheet_start_frame_ban]" in e for e in errs_hook), f"Must fail start_frame_image for {slot}: {errs_hook}"

        # 3. Direct reference_image with flow_input_mode='VIDEO_FRAMES' -> MUST FAIL (even on non-R87 R85/v8 plans!)
        plan_vf = {
            "style_profile": "expressive_25d_v8",
            "r85_mode": True,
            "clips": [
                {
                    "clip_number": 4,
                    "grammar": "expressive_vinyl_world",
                    "reference_image": fname,
                    "flow_input_mode": "VIDEO_FRAMES",
                    "scene": "Bald vinyl adult holds snack spoon.",
                }
            ],
        }
        errs_vf = validate_r87_turnaround_sheet_start_frame_ban(plan_vf)
        assert any("[r87_turnaround_sheet_start_frame_ban]" in e for e in errs_vf), f"Must fail VIDEO_FRAMES for {slot}: {errs_vf}"

        # 4. Direct canonical_slot_id without separate custom single-frame reference_image -> MUST FAIL
        plan_slot = {
            "style_profile": "expressive_25d_v8",
            "r87_mode": True,
            "clips": [
                {
                    "clip_number": 7,
                    "grammar": "expressive_vinyl_world",
                    "canonical_slot_id": slot,
                    "scene": "Bald vinyl adult turns toward lab monitor.",
                }
            ],
        }
        errs_slot = validate_r87_turnaround_sheet_start_frame_ban(plan_slot)
        assert any("[r87_turnaround_sheet_start_frame_ban]" in e for e in errs_slot), f"Must fail bare canonical_slot_id for {slot}: {errs_slot}"

    # Verify validate_production_diorama_v6 (prompt-gate entrypoint) emits [r87_turnaround_sheet_start_frame_ban]
    pg_plan = {
        "schema": 8,
        "profile": "neuro_diorama",
        "style_profile": "expressive_25d_v8",
        "r85_mode": True,
        "clips": [
            {
                "clip_number": 1,
                "sentence_index": 1,
                "grammar": "expressive_vinyl_world",
                "reference_image": "canonical_B01_base_adult_male_turnaround.png",
                "single_start_frame_lock": True,
                "scene": "Bald cream-white vinyl adult eats snack.",
            }
        ],
    }
    pg_issues = validate_production_diorama_v6(
        pg_plan,
        ["One daily pudding cup rewired healthy brains fast!"],
        pg_plan["clips"],
        script_doc={"schema": 8, "style_profile": "expressive_25d_v8", "r85_mode": True},
    )
    assert any("[r87_turnaround_sheet_start_frame_ban]" in e for e in pg_issues), pg_issues

    # ALLOWED cases:
    # (a) B01-B04 inside conditioned_on (with custom single-frame reference_image)
    # (b) B01 in VIDEO_REFERENCES Ingredients mode (single_start_frame_lock=False, no start_frame_image)
    # (c) Single-pose B05_expr_surprised..B10_expr_eureka bound directly as start_frame_image + single_start_frame_lock=True
    allowed_plan = {
        "style_profile": "expressive_25d_v8",
        "r87_mode": True,
        "clips": [
            {
                "clip_number": 1,
                "grammar": "expressive_vinyl_world",
                "reference_image": "ref_clip_01_single_pose.png",
                "start_frame_image": "ref_clip_01_single_pose.png",
                "single_start_frame_lock": True,
                "flow_input_mode": "VIDEO_FRAMES",
                "conditioned_on": ["B01_base_adult_male_turnaround", "B02_base_adult_female_turnaround"],
            },
            {
                "clip_number": 2,
                "grammar": "expressive_vinyl_world",
                "canonical_slot_id": "B01_base_adult_male_turnaround",
                "reference_image": "ref_clip_02_custom_single_frame.png",
                "single_start_frame_lock": True,
                "conditioned_on": ["B01_base_adult_male_turnaround"],
            },
            {
                "clip_number": 3,
                "grammar": "expressive_vinyl_world",
                "reference_image": "canonical_B01_base_adult_male_turnaround.png",
                "flow_input_mode": "VIDEO_REFERENCES",
                "single_start_frame_lock": False,
            },
            {
                "clip_number": 4,
                "grammar": "expressive_vinyl_world",
                "canonical_slot_id": "B05_expr_surprised",
                "reference_image": "canonical_B05_expr_surprised.png",
                "start_frame_image": "canonical_B05_expr_surprised.png",
                "single_start_frame_lock": True,
                "flow_input_mode": "VIDEO_FRAMES",
            },
            {
                "clip_number": 5,
                "grammar": "expressive_vinyl_world",
                "canonical_slot_id": "B10_expr_eureka",
                "reference_image": "canonical_B10_expr_eureka.png",
                "single_start_frame_lock": True,
                "flow_input_mode": "VIDEO_FRAMES",
            },
        ],
    }
    assert validate_r87_turnaround_sheet_start_frame_ban(allowed_plan) == []


def test_lock1_g_r82_authored_relay_to_full_brain_handoff_no_false_split(tmp_path: Path) -> None:
    """
    S11 Handoff Fix Regression (`spare_splits_r76` airtight per-sentence role accounting):
    - Exercises `verify_final_mp4_against_contract` with `is_synth_test=False` (`engine="elevenlabs_v4"`).
    - Positive: R82+ 2-cut sentence (`S11`: 1 `human_action_relay=True` `2.6s` cut + 1 full `>=4.20s`
      `expressive_xray_brain` `4.5s` cut) AND 2-cut authored relay pair (`S02`) MUST PASS with zero
      `mid-sentence splits detected`.
    - Negative: unflagged human + brain, relay + short `<4.20s` brain, brain + brain (even `>=4.20s`),
      3 cuts in 1 sentence (even with 2 authored relays + 1 full brain), unflagged human + human,
      and non-R82 (`is_r82_ep=False`) relay + brain MUST ALL FAIL with `mid-sentence splits detected`.
    """
    shared_mp4 = tmp_path / "shared_22s.mp4"
    vw = cv2.VideoWriter(str(shared_mp4), cv2.VideoWriter_fourcc(*"mp4v"), 30.0, (270, 480))
    for fi in range(660):  # 22.0s @ 30fps
        frm = np.full((480, 270, 3), (185, 195, 205), dtype=np.uint8)
        cx = 50 + (fi % 130)
        cv2.rectangle(frm, (cx, 140), (cx + 80, 340), (235, 238, 240), -1)
        vw.write(frm)
    vw.release()
    mp4_bytes = shared_mp4.read_bytes()
    assert len(mp4_bytes) >= 8_192

    def _run_handoff_case(
        case_pid: str,
        s11_specs: list[dict[str, object]],
        *,
        r82_mode: bool = True,
        r85_mode: bool = False,
        include_s02_relay_pair: bool = True,
    ) -> dict[str, object]:
        proj = tmp_path / case_pid
        (proj / "02_script").mkdir(parents=True)
        (proj / "03_visuals").mkdir(parents=True)
        (proj / "04_audio").mkdir(parents=True)
        (proj / "05_assembly").mkdir(parents=True)
        (proj / "05_assembly" / "final_shorts_1080x1920.mp4").write_bytes(mp4_bytes)

        base_specs: list[dict[str, object]] = [
            {
                "sentence_index": 1,
                "grammar": "expressive_vinyl_world",
                "render_engine": "google_flow",
                "brain_clip": False,
                "camera_move": "gentle_push_in",
                "duration_sec": 2.2 if r82_mode else 3.0,
                "canonical_slot_id": "J01_hook_mode1_daily_action_xray_alert",
                "scene": "Bald cream-white vinyl adult lifts a chocolate pudding spoon toward mouth.",
            },
        ]
        if include_s02_relay_pair:
            base_specs.extend(
                [
                    {
                        "sentence_index": 2,
                        "grammar": "expressive_exterior_establishing",
                        "render_engine": "google_flow",
                        "brain_clip": False,
                        "human_action_relay": True,
                        "camera_move": "drone_aerial_approach",
                        "duration_sec": 2.2,
                        "scene": "120ft aerial drone glides over Max Planck Cologne research campus rooftops.",
                    },
                    {
                        "sentence_index": 2,
                        "grammar": "expressive_vinyl_world",
                        "render_engine": "google_flow",
                        "brain_clip": False,
                        "human_action_relay": True,
                        "camera_move": "gentle_push_in",
                        "duration_sec": 2.2,
                        "scene": "Bald cream-white vinyl adult enters the bright laboratory corridor.",
                    },
                ]
            )
        base_specs.append(
            {
                "sentence_index": 3,
                "grammar": "expressive_xray_brain",
                "render_engine": "google_flow",
                "brain_clip": True,
                "r85_brain_clip": r85_mode,
                "camera_move": "gentle_push_in",
                "brain_region": "ventral striatum",
                "duration_sec": 4.5,
                "scene": "Ep #31 matte silver-white 3D cutaway brain highlights the ventral striatum.",
            }
        )
        all_specs = base_specs + s11_specs

        vp_clips: list[dict[str, object]] = []
        edl_cuts: list[dict[str, object]] = []
        t_cur = 0.0
        for idx, sp in enumerate(all_specs, start=1):
            dur = float(sp["duration_sec"])
            is_b = bool(sp.get("brain_clip"))
            vp_c: dict[str, object] = {
                "clip_number": idx,
                "sentence_index": int(sp["sentence_index"]),
                "grammar": str(sp["grammar"]),
                "render_engine": str(sp.get("render_engine") or "google_flow"),
                "brain_clip": is_b,
                "camera_move": str(sp.get("camera_move") or "gentle_push_in"),
                "scene": str(
                    sp.get("scene")
                    or (
                        "Ep #31 matte silver-white 3D cutaway brain highlights the synapse."
                        if is_b
                        else "Bald cream-white vinyl adult holds a ceramic spoon at the lab table."
                    )
                ),
            }
            if is_b and r85_mode:
                vp_c["r85_brain_clip"] = True
            if sp.get("brain_region"):
                vp_c["brain_region"] = sp["brain_region"]
            if sp.get("canonical_slot_id"):
                vp_c["canonical_slot_id"] = sp["canonical_slot_id"]
            if sp.get("human_action_relay"):
                vp_c["human_action_relay"] = True
            if sp.get("spatial_relay_cut"):
                vp_c["spatial_relay_cut"] = True
            vp_clips.append(vp_c)

            edl_c: dict[str, object] = {
                "cut_index": idx,
                "clip_index": idx,
                "sentence_index": int(sp["sentence_index"]),
                "grammar": str(sp["grammar"]),
                "render_engine": str(sp.get("render_engine") or "google_flow"),
                "brain_clip": is_b,
                "camera_move": str(sp.get("camera_move") or "gentle_push_in"),
                "out_start_sec": round(t_cur, 4),
                "out_end_sec": round(t_cur + dur, 4),
                "duration_sec": dur,
                "src_start_sec": 0.0,
                "src_end_sec": dur,
                "main_speed": 1.0,
            }
            if is_b and r85_mode:
                edl_c["r85_brain_clip"] = True
            if sp.get("human_action_relay"):
                edl_c["human_action_relay"] = True
            if sp.get("spatial_relay_cut"):
                edl_c["spatial_relay_cut"] = True
            edl_cuts.append(edl_c)
            t_cur += dur

        vp_doc: dict[str, object] = {
            "schema": 8,
            "project_id": case_pid,
            "profile": "neuro_diorama",
            "style_profile": "expressive_25d_v8",
            "r76_mode": not r85_mode,
            "r82_mode": r82_mode,
            "r85_mode": r85_mode,
            "r87_mode": r82_mode,
            "spatial_arrow_eligible": (not r82_mode),
            "hook_visual_mode": "mode1_daily_xray_shock",
            "hook_title_text": "1 SNACK\\NREWIRED IT!",
            "clips": vp_clips
            + [
                {
                    "clip_number": pad_i,
                    "sentence_index": min(18, pad_i),
                    "grammar": "expressive_xray_brain" if pad_i % 2 == 0 else "expressive_vinyl_world",
                    "render_engine": "google_flow",
                    "brain_clip": (pad_i % 2 == 0),
                    "r85_brain_clip": bool(r85_mode and pad_i % 2 == 0),
                    "camera_move": "gentle_push_in",
                    "brain_region": "ventral striatum" if pad_i % 2 == 0 else "",
                    "scene": (
                        "Ep #31 matte silver-white 3D cutaway brain highlights the ventral striatum."
                        if pad_i % 2 == 0
                        else "Bald cream-white vinyl adult taps a ceramic spoon on the oak lab table."
                    ),
                }
                for pad_i in range(len(vp_clips) + 1, 19)
            ],
        }
        script_doc: dict[str, object] = {
            "schema": 8,
            "project_id": case_pid,
            "style_profile": "expressive_25d_v8",
            "r76_mode": not r85_mode,
            "r82_mode": r82_mode,
            "r85_mode": r85_mode,
            "r87_mode": r82_mode,
            "sentences": [f"Sentence {i} explains the reward circuit step." for i in range(1, 19)],
        }
        (proj / "03_visuals" / "visual_plan.json").write_text(json.dumps(vp_doc), encoding="utf-8")
        (proj / "02_script" / "script.json").write_text(json.dumps(script_doc), encoding="utf-8")
        # `engine="elevenlabs_v4"` guarantees `is_synth_test=False` so `spare_splits_r76` is enforced live!
        (proj / "04_audio" / "voice_report.json").write_text(
            json.dumps({"engine": "elevenlabs_v4", "speech_end_sec": round(t_cur, 3)}),
            encoding="utf-8",
        )
        (proj / "05_assembly" / "edit_decision_list.json").write_text(
            json.dumps({"schema": 8, "fps": 30, "total_duration_sec": round(t_cur, 3), "cuts": edl_cuts}),
            encoding="utf-8",
        )
        return verify_final_mp4_against_contract(proj, run_asr_sync=False, save_report=False)

    s11_valid_handoff = [
        {
            "sentence_index": 11,
            "grammar": "expressive_vinyl_world",
            "brain_clip": False,
            "human_action_relay": True,
            "duration_sec": 2.6,
        },
        {
            "sentence_index": 11,
            "grammar": "expressive_xray_brain",
            "brain_clip": True,
            "brain_region": "ventral striatum",
            "duration_sec": 4.5,
        },
    ]

    # Positive Case: R82/R87 authored 2-cut handoff (`S11`: relay 2.6s + full brain 4.5s) + `S02` relay pair -> PASS
    rep_ok = _run_handoff_case("v8_ep13_s11_pos_r82", s11_valid_handoff, r82_mode=True, r85_mode=False)
    dq_pace_ok = rep_ok["gates"]["DQ_R76_anti_noise_pacing"]
    assert dq_pace_ok["spare_sentence_splits"] == {}, dq_pace_ok
    assert not any("mid-sentence splits detected" in v for v in dq_pace_ok["violations"]), dq_pace_ok
    assert dq_pace_ok["passed"] is True, dq_pace_ok
    assert rep_ok["gates"]["DQ_R76_unified_brain_share"]["passed"] is True, rep_ok["gates"]["DQ_R76_unified_brain_share"]

    # Positive Sanity Check (R85/R87 active mode): unified brain share counts both brain cuts accurately
    rep_r85_ok = _run_handoff_case("v8_ep13_s11_pos_r85", s11_valid_handoff, r82_mode=True, r85_mode=True)
    dq_share_r85 = rep_r85_ok["advisory_gates"]["DQ_R76_unified_brain_share"]
    assert dq_share_r85["brain_duration_sec"] == pytest.approx(9.0, abs=0.05)
    assert dq_share_r85["passed"] is True, dq_share_r85

    # Negative Case 1: Unflagged human (`human_action_relay=False`) 2.6s + 4.5s brain in S11 -> MUST FAIL
    rep_neg1 = _run_handoff_case(
        "v8_ep13_s11_neg1_unflagged_r82",
        [
            {
                "sentence_index": 11,
                "grammar": "expressive_vinyl_world",
                "brain_clip": False,
                "human_action_relay": False,
                "duration_sec": 2.6,
            },
            {
                "sentence_index": 11,
                "grammar": "expressive_xray_brain",
                "brain_clip": True,
                "brain_region": "ventral striatum",
                "duration_sec": 4.5,
            },
        ],
    )
    dq_pace_n1 = rep_neg1["gates"]["DQ_R76_anti_noise_pacing"]
    assert dq_pace_n1["passed"] is False
    assert dq_pace_n1["spare_sentence_splits"] == {11: 2}
    assert any("mid-sentence splits detected" in v for v in dq_pace_n1["violations"]), dq_pace_n1

    # Negative Case 2: `human_action_relay=True` 2.6s + short 2.5s (<4.20s) brain in S11 -> MUST FAIL both split & brain floor
    rep_neg2 = _run_handoff_case(
        "v8_ep13_s11_neg2_short_brain_r82",
        [
            {
                "sentence_index": 11,
                "grammar": "expressive_vinyl_world",
                "brain_clip": False,
                "human_action_relay": True,
                "duration_sec": 2.6,
            },
            {
                "sentence_index": 11,
                "grammar": "expressive_xray_brain",
                "brain_clip": True,
                "brain_region": "ventral striatum",
                "duration_sec": 2.5,
            },
        ],
    )
    dq_pace_n2 = rep_neg2["gates"]["DQ_R76_anti_noise_pacing"]
    assert dq_pace_n2["passed"] is False
    assert dq_pace_n2["spare_sentence_splits"] == {11: 2}
    assert any("mid-sentence splits detected" in v for v in dq_pace_n2["violations"]), dq_pace_n2
    assert any("brain floor" in v for v in dq_pace_n2["violations"]), dq_pace_n2

    # Negative Case 3: Two >=4.20s brain cuts (4.5s + 4.5s) in S11 -> MUST FAIL
    rep_neg3 = _run_handoff_case(
        "v8_ep13_s11_neg3_two_brains_r82",
        [
            {
                "sentence_index": 11,
                "grammar": "expressive_xray_brain",
                "brain_clip": True,
                "brain_region": "ventral striatum",
                "duration_sec": 4.5,
            },
            {
                "sentence_index": 11,
                "grammar": "expressive_xray_brain",
                "brain_clip": True,
                "brain_region": "ventral striatum",
                "duration_sec": 4.5,
            },
        ],
    )
    dq_pace_n3 = rep_neg3["gates"]["DQ_R76_anti_noise_pacing"]
    assert dq_pace_n3["passed"] is False
    assert dq_pace_n3["spare_sentence_splits"] == {11: 2}
    assert any("mid-sentence splits detected" in v for v in dq_pace_n3["violations"]), dq_pace_n3

    # Negative Case 4: 3 cuts in S11 (2 authored relays + 1 full brain) -> MUST FAIL
    rep_neg4 = _run_handoff_case(
        "v8_ep13_s11_neg4_three_cuts_r82",
        [
            {
                "sentence_index": 11,
                "grammar": "expressive_vinyl_world",
                "brain_clip": False,
                "human_action_relay": True,
                "duration_sec": 2.2,
            },
            {
                "sentence_index": 11,
                "grammar": "expressive_vinyl_world",
                "brain_clip": False,
                "human_action_relay": True,
                "duration_sec": 2.2,
            },
            {
                "sentence_index": 11,
                "grammar": "expressive_xray_brain",
                "brain_clip": True,
                "brain_region": "ventral striatum",
                "duration_sec": 4.5,
            },
        ],
    )
    dq_pace_n4 = rep_neg4["gates"]["DQ_R76_anti_noise_pacing"]
    assert dq_pace_n4["passed"] is False
    assert dq_pace_n4["spare_sentence_splits"] == {11: 3}
    assert any("mid-sentence splits detected" in v for v in dq_pace_n4["violations"]), dq_pace_n4

    # Negative Case 5: Unflagged human + unflagged human in S11 -> MUST FAIL
    rep_neg5 = _run_handoff_case(
        "v8_ep13_s11_neg5_two_unflagged_r82",
        [
            {
                "sentence_index": 11,
                "grammar": "expressive_vinyl_world",
                "brain_clip": False,
                "human_action_relay": False,
                "duration_sec": 2.3,
            },
            {
                "sentence_index": 11,
                "grammar": "expressive_vinyl_world",
                "brain_clip": False,
                "human_action_relay": False,
                "duration_sec": 2.3,
            },
        ],
    )
    dq_pace_n5 = rep_neg5["gates"]["DQ_R76_anti_noise_pacing"]
    assert dq_pace_n5["passed"] is False
    assert dq_pace_n5["spare_sentence_splits"] == {11: 2}
    assert any("mid-sentence splits detected" in v for v in dq_pace_n5["violations"]), dq_pace_n5

    # Negative Case 6: Non-R82 (`is_r82_ep=False`) spatial relay + full brain in S11 -> MUST FAIL
    rep_neg6 = _run_handoff_case(
        "v8_ep10_s11_neg6_non_r82_r76",
        [
            {
                "sentence_index": 11,
                "grammar": "spatial_3d_arrow_diorama",
                "brain_clip": False,
                "spatial_relay_cut": True,
                "duration_sec": 2.6,
            },
            {
                "sentence_index": 11,
                "grammar": "expressive_xray_brain",
                "brain_clip": True,
                "brain_region": "ventral striatum",
                "duration_sec": 4.5,
            },
        ],
        r82_mode=False,
        r85_mode=False,
        include_s02_relay_pair=False,
    )
    dq_pace_n6 = rep_neg6["gates"]["DQ_R76_anti_noise_pacing"]
    assert dq_pace_n6["passed"] is False
    assert dq_pace_n6["spare_sentence_splits"] == {11: 2}
    assert any("mid-sentence splits detected" in v for v in dq_pace_n6["violations"]), dq_pace_n6
