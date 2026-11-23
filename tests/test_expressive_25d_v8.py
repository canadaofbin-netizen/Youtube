"""
Comprehensive test suite for Schema v8 `expressive_25d_v8` / `shorts_expressive_v8` (Rule R68):
- SSOT constant & rule parity (`pipeline/config.py` <-> `.agents/rules/production_constants.md`) + Stage 1 preflight QA
- Profile resolution (`is_expressive_v8_plan`, `resolve_diorama_v7_style_profile`, `resolve_shorts_format_profile`, range helpers)
- 6-Master Reference Anchor Bible (`ensure_expressive_v8_reference_pack`, `populate_expressive_v8_reference_contract`, `inspect_reference_image_pack` Q1..Q10)
- YuNet 2.5D ink face allowance vs real flesh face rejection (`detect_non_porcelain_human_faces_yunet(..., allow_expressive_2d_ink=True)`)
- `ExpressiveV8PromptComposer`, `[0..70%]` zero-brain-CG rule, `[70..85%]` `expressive_xray_brain` crystal-dome reveal, single `Mini-Cortex` cameo, `diegetic_text_allowlist`, and negative boundary guards
- Rule R68 title/description packaging (`4..8` words, `<= 55` chars, `0` hashtags, `omit_experiment_nicknames`)
- `expressive_us_v8` prosody, `0%` melodic BGM + `-30 dBFS` stereo room air + procedural gap foley + `-14.0 LUFS` audio master, `102pt` `#FFE600` `MarginV=521` ASS subtitles, 6-frame `xfade` `dissolve_6f` assembly, `DQ1..DQ12` + `DQ_CAMEO_single_minicortex`, `VideoAutopsyEngine.inspect_project`, and read-only `StudioUploader.audit_v8_channel_readiness`
"""

from __future__ import annotations

import copy
import json
import math
import subprocess
import wave
from pathlib import Path
from typing import Any

import cv2
import imageio_ffmpeg
import numpy as np
import pytest

from pipeline import config as cfg
from pipeline.depiction_rules import ExpressiveV8PromptComposer, validate_expressive_v8_scene
from pipeline.diorama_assembler import (
    assemble_diorama_project,
    build_v7_dynamic_edl,
    generate_diorama_ass_subtitles,
    generate_diorama_audio_master,
)
from pipeline.dynamic_episode_qa import (
    compile_episode_qa_contract,
    verify_final_mp4_against_contract,
    verify_pre_flow_contract,
)
from pipeline.flow_diorama_sharded_worker import inspect_diorama_clip_cv
from pipeline.flow_prompt_builder import (
    build_diorama_v7_prompts,
    validate_diorama_v7_prompts,
    write_flow_prompts_json,
)
from pipeline.porcelain_anchor_pack import (
    ensure_expressive_v8_reference_pack,
    populate_expressive_v8_reference_contract,
)
from pipeline.prompt_quality_v5 import validate_production_diorama_v6
from pipeline.prosody import plan_sentence_prosody
from pipeline.publish import (
    build_expressive_v8_pinned_comment,
    render_editorial_description,
    validate_expressive_v8_title,
)
from pipeline.qa_gates import run_intent_content_qa, run_preflight_qa
from pipeline.reference_image_qa import inspect_reference_image_pack
from pipeline.source_reenactment import detect_non_porcelain_human_faces_yunet
from pipeline.studio.uploader import StudioUploader
from pipeline.video_autopsy import VideoAutopsyEngine

ROOT = cfg.WORKSPACE_ROOT


def _write_test_mp4(mp4_path: Path, frames_bgr: list[np.ndarray], fps: int = 24) -> Path:
    h, w = frames_bgr[0].shape[:2]
    raw_avi = mp4_path.with_suffix(".avi")
    vw = cv2.VideoWriter(str(raw_avi), cv2.VideoWriter_fourcc(*"MJPG"), float(fps), (w, h))
    for frm in frames_bgr:
        vw.write(frm)
    vw.release()

    ff = imageio_ffmpeg.get_ffmpeg_exe()
    subprocess.run(
        [
            ff,
            "-y",
            "-i",
            str(raw_avi),
            "-c:v",
            "libx264",
            "-crf",
            "12",
            "-pix_fmt",
            "yuv420p",
            str(mp4_path),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    raw_avi.unlink(missing_ok=True)
    return mp4_path


def _sample_v8_sentences() -> list[str]:
    return [
        "At three in the morning, your eyes snap wide open!",
        "Yet back home, you sleep right through loud street sirens.",
        "Stop blaming a stiff hotel pillow for ruining night one.",
        "Your buddy laughs and blames that late airport espresso cup.",
        "Inside a dark sleep booth, glowing sensors tracked two straight nights.",
        "Night one looked completely calm across the right half.",
        "Wait, what was the other half doing in the dark?",
        "Deep rest dropped fast on the left while the right slept.",
        "Soft hallway beeps woke sleepers three times faster, like a tripwire.",
        "Dolphins and wild ducks use that exact trick on open water.",
        "Your body treats every strange hotel room like an unsafe camp.",
        "Even a quiet elevator chime keeps that hidden watchman alert.",
        "You try counting sheep, but the left side refuses rest.",
        "You see, your default mode network, your daydream network, stays on guard.",
        "Crimson sparks light your auditory cortex, your sound center, all night.",
        "Every faint corridor creak pings straight through that open channel.",
        "Dawn finally breaks as you rub your heavy tired eyelids.",
        "By night two in that same bed, the alarm stands down.",
        "Both sides sink into deep waves once the room feels safe.",
        "Tonight in a new bed, half your head stands guard while half dreams.",
    ]


def _sample_v8_visual_plan(sentences: list[str]) -> dict[str, Any]:
    clips: list[dict[str, Any]] = []
    grammars = [
        "expressive_vinyl_world",       # 1
        "expressive_split_contrast",    # 2
        "expressive_vinyl_world",       # 3
        "expressive_vinyl_world",       # 4 (foil)
        "expressive_hands_closeup",     # 5
        "expressive_vinyl_world",       # 6
        "expressive_vinyl_world",       # 7 (pivot)
        "expressive_hands_closeup",     # 8
        "expressive_vinyl_world",       # 9
        "expressive_literal_analogy",   # 10 (cameo)
        "expressive_vinyl_world",       # 11
        "expressive_vinyl_world",       # 12
        "expressive_vinyl_world",       # 13
        "expressive_xray_brain",        # 14 (13.5/20 = 67.5% in [60%, 85%])
        "expressive_xray_brain",        # 15 (14.5/20 = 72.5% in [60%, 85%])
        "expressive_hands_closeup",     # 16
        "expressive_vinyl_world",       # 17
        "expressive_vinyl_world",       # 18
        "expressive_vinyl_world",       # 19
        "expressive_vinyl_world",       # 20
    ]

    cam_cycle = [
        "dolly_zoom_vertigo",
        "orbital_3d_arc_sweep",
        "pan_right",
        "gentle_push_in",
        "crane_swoop_dive",
        "pan_left",
        "fpv_3d_flight",
        "locked_tripod",
        "whip_pan_occlusion",
        "orbital_3d_arc_sweep",
        "gentle_push_in",
        "tilt_up",
        "clean_pullback_reveal",
        "portal_dive_flight",
        "orbital_3d_arc_sweep",
        "crane_swoop_dive",
        "pan_left",
        "fpv_3d_flight",
        "clean_pullback_reveal",
        "gentle_push_in",
    ]

    loc_map = {
        1: ("hotel_room_3am", "dim 3 AM hotel room with a glowing bedside alarm clock and crisp linen bed"),
        2: ("hotel_room_3am", "dim 3 AM hotel room with a glowing bedside alarm clock and crisp linen bed"),
        3: ("hotel_room_3am", "dim 3 AM hotel room with a glowing bedside alarm clock and crisp linen bed"),
        4: ("hotel_room_3am", "dim 3 AM hotel room with a glowing bedside alarm clock and crisp linen bed"),
        5: ("brown_sleep_lab", "warm miniature sleep laboratory with sensor leads and glass observation window"),
        6: ("brown_sleep_lab", "warm miniature sleep laboratory with sensor leads and glass observation window"),
        7: ("lab_monitor_gallery", "dim observation console booth overlooking illuminated wave monitors"),
        8: ("lab_monitor_gallery", "dim observation console booth overlooking illuminated wave monitors"),
        9: ("hotel_corridor_night", "long carpeted hotel hallway with brass room doors and warm sconce lamps"),
        10: ("coastal_wave_diorama", "open moonlit coastal water diorama beside a brass nightstand lamp"),
        11: ("hotel_room_3am", "dim 3 AM hotel room with a glowing bedside alarm clock and crisp linen bed"),
        12: ("hotel_room_3am", "dim 3 AM hotel room with a glowing bedside alarm clock and crisp linen bed"),
        13: ("hotel_room_3am", "dim 3 AM hotel room with a glowing bedside alarm clock and crisp linen bed"),
        14: ("hotel_room_3am", "dim 3 AM hotel room opening into a glowing 4-color crystal-dome brain view"),
        15: ("hotel_room_3am", "dim 3 AM hotel room opening into a glowing 4-color crystal-dome brain view"),
        16: ("airport_coffee_gate", "bright miniature airport boarding lounge with espresso counter and rolling luggage"),
        17: ("airport_coffee_gate", "bright miniature airport boarding lounge with espresso counter and rolling luggage"),
        18: ("morning_hotel_balcony", "sunlit open-air hotel balcony overlooking miniature city rooftops at dawn"),
        19: ("morning_hotel_balcony", "sunlit open-air hotel balcony overlooking miniature city rooftops at dawn"),
        20: ("morning_hotel_balcony", "sunlit open-air hotel balcony overlooking miniature city rooftops at dawn"),
    }

    for idx, (_sent, g, cam) in enumerate(zip(sentences, grammars, cam_cycle), start=1):
        act_no = min(6, ((idx - 1) * 6) // len(sentences) + 1)
        loc_id, env_desc = loc_map[idx]
        spec: dict[str, Any] = {
            "clip_number": idx,
            "sentence_index": idx,
            "act": act_no,
            "grammar": g,
            "camera_move": cam,
            "location_id": loc_id,
            "environment": env_desc,
            "cast": "a matte-white 2.5D vinyl traveler in navy pajama sleeves and slippers with minimalist 2D ink eyes",
            "action": "jolts upright and grips crisp hotel sheets as a brass hallway handle clicks",
            "consequence": "wide 2D ink eyes lock onto the glowing bedside clock",
        }
        if idx == 1:
            spec["diegetic_text_allowlist"] = ["03:00"]
            spec["consequence"] = "wide 2D ink eyes lock onto the glowing 03:00 bedside clock"
        if idx == 4:
            spec["voice_role"] = "foil"
            spec["cast"] = "a skeptical matte-white 2.5D vinyl friend in a tan jacket holding a paper coffee cup"
            spec["action"] = "waves and tilts a cardboard espresso cup dismissively beside a luggage cart"
            spec["consequence"] = "raised ink eyebrow smirks in casual disbelief"
        if idx == 9:
            spec["analogy_object"] = "a taut brass tripwire string snapping a tiny bell across the hotel carpet"
            spec["action"] = "steps forward and taps a taut brass tripwire bell beside the door threshold"
        if idx == 10:
            spec["cameo_easter_egg"] = True
            spec["analogy_object"] = "a miniature porcelain dolphin and wild duck gliding half-asleep on open water"
            spec["action"] = "glides and turns smoothly across a moonlit water tray while Mini-Cortex peeks from the lamp base"
        if g == "expressive_xray_brain":
            spec["brain_region"] = "left default mode network and auditory cortex"
            spec["action"] = (
                "inside the crystal-dome cranium, bounded 4-color 3D brain pathways pulse crimson-amber "
                "across the left hemisphere while the right hemisphere glows calm cyan"
            )
            spec["consequence"] = "amber auditory relay arcs flash and sweep cleanly inside the crystal dome"
            spec["transition_to_next"] = "dissolve_8f"
        clips.append(spec)

    return {
        "schema": cfg.PROMPT_SCHEMA_VERSION_V8,
        "profile": "neuro_diorama",
        "style_profile": cfg.EXPRESSIVE_25D_V8_STYLE_PROFILE,
        "format_profile": cfg.SHORTS_EXPRESSIVE_V8_PROFILE,
        "prosody_mode": cfg.EXPRESSIVE_V8_PROSODY_MODE,
        "voice_preset": "emma_v7",
        "foil_voice_preset": "foil_v8",
        "core_reveal_sentence_index": 14,
        "zero_clip_reuse": True,
        "title": "Your Brain's 3 AM Night Watch",
        "dossier": "v2_sleep_first_night_hemisphere_watch",
        "doi": "10.1016/j.cub.2016.02.063",
        "omit_experiment_nicknames": ["first-night effect", "first night effect"],
        "thumbnail": {
            "hook_text": "HALF AWAKE",
            "cover_sentence_index": 1,
        },
        "clips": clips,
    }


def test_v8_ssot_constants_and_profile_helpers() -> None:
    constants_md = (ROOT / ".agents" / "rules" / "production_constants.md").read_text(encoding="utf-8")
    required = (
        "PROMPT_SCHEMA_VERSION_V8",
        "EXPRESSIVE_25D_V8_STYLE_PROFILE",
        "SHORTS_EXPRESSIVE_V8_PROFILE",
        "SHORTS_EXPRESSIVE_V8_DURATION_MIN_SEC",
        "SHORTS_EXPRESSIVE_V8_DURATION_MAX_SEC",
        "SHORTS_EXPRESSIVE_V8_WORD_COUNT_MIN",
        "SHORTS_EXPRESSIVE_V8_WORD_COUNT_MAX",
        "EXPRESSIVE_V8_CLIP_COUNT_MIN",
        "EXPRESSIVE_V8_CLIP_COUNT_MAX",
        "EXPRESSIVE_V8_CAMERA_MOVES",
        "EXPRESSIVE_V8_SUBTITLE_FONT_SIZE",
        "EXPRESSIVE_V8_SUBTITLE_MARGIN_V",
        "EXPRESSIVE_V8_TARGET_LUFS",
        "EXPRESSIVE_V8_DISSOLVE_FRAMES",
        "EXPRESSIVE_V8_CORE_REVEAL_MAX_SENTENCE",
        "EXPRESSIVE_V8_CORE_REVEAL_MAX_SEC",
        "EXPRESSIVE_V8_OPENING_QUESTION_MAX_WORDS",
        "EXPRESSIVE_V8_OPENING_EMPATHY_MAX_WORDS",
        "EXPRESSIVE_V8_MAX_MYTH_FLIPS",
        "EXPRESSIVE_V8_ADVISORY_PIVOT_MARKERS",
        "SHORTS_EXPRESSIVE_V8_SENTENCE_WORDS_MAX",
        "SHORTS_EXPRESSIVE_V8_SENTENCE_COUNT_TARGET",
        "R68_TITLE_WORD_RANGE",
        "R68_TITLE_MAX_CHARS",
        "R68_DESCRIPTION_HASHTAG_COUNT",
    )
    for name in required:
        assert hasattr(cfg, name), f"Missing {name} in pipeline/config.py"
        assert name in constants_md, f"Missing {name} in production_constants.md"

    s1 = run_preflight_qa(require_live_cdp=False)
    assert s1["passed"] is True, f"Stage 1 preflight QA failed: {s1}"

    # Verify default v7 remains intact while v8 resolves cleanly
    assert cfg.DEFAULT_DIORAMA_STYLE_PROFILE == "porcelain_cinematic_v7"
    assert cfg.is_expressive_v8_plan({"schema": 8}) is True
    assert cfg.is_expressive_v8_plan({"style_profile": "expressive_25d_v8"}) is True
    assert cfg.is_expressive_v8_plan({"format_profile": "shorts_expressive_v8"}) is True
    assert cfg.is_expressive_v8_plan({"schema": 7, "style_profile": "porcelain_cinematic_v7"}) is False
    assert cfg.is_porcelain_v7_plan({"schema": 8, "style_profile": "expressive_25d_v8"}) is False

    assert cfg.shorts_duration_range_for_profile("shorts_expressive_v8") == (61.5, 88.0)
    assert cfg.shorts_duration_range_for_profile(
        "shorts_expressive_v8", project_id="v8_ep04_patient_sm_fearless_amygdala"
    ) == (61.5, 120.0)
    assert cfg.word_count_range_for_profile("shorts_expressive_v8") == (145, 420)
    assert cfg.clip_count_range_for_profile("shorts_expressive_v8") == (15, 36)


def test_v8_six_master_reference_pack_and_q1_q10(tmp_path: Path) -> None:
    proj_dir = tmp_path / "v8_ref_pack_proj"
    (proj_dir / "03_visuals").mkdir(parents=True)
    sents = _sample_v8_sentences()
    vp = _sample_v8_visual_plan(sents)
    vp = populate_expressive_v8_reference_contract(vp)
    (proj_dir / "03_visuals" / "visual_plan.json").write_text(json.dumps(vp, indent=2), encoding="utf-8")

    # Verify cameo clip 10 gets 2-chip attachment (primary + secondary Mini-Cortex sheet)
    clip_10 = vp["clips"][9]
    assert clip_10["cameo_easter_egg"] is True
    assert str(clip_10.get("secondary_reference_image") or "").endswith("cameo_opt3_sheet.png")

    pack_res = ensure_expressive_v8_reference_pack(proj_dir)
    assert pack_res["cv_pre_generation_ready"] is True, f"Reference pack CV not ready: {pack_res}"
    assert pack_res["status"] == "REVIEW_PENDING"
    assert pack_res["total_images"] == 6
    # Sign Gate 1 review as @Research per Rule R85
    sem_p = proj_dir / "03_visuals" / "reference_images" / "reference_semantic_review.json"
    sem_doc = json.loads(sem_p.read_text(encoding="utf-8"))
    sem_doc["reviewer"] = "@Research"
    for idx_r, (rid, r_ent) in enumerate(sem_doc["images"].items()):
        r_ent["checks"] = {k: True for k in (r_ent.get("checks") or {})}
        r_ent["note"] = f"Verified master v8 anchor #{idx_r + 1} ({rid}) with clean bald 2.5D vinyl / 4-color brain fidelity."
    sem_p.write_text(json.dumps(sem_doc, indent=2), encoding="utf-8")
    qa_rep = inspect_reference_image_pack(proj_dir, save_report=True)
    assert qa_rep["all_passed"] is True, f"Reference pack QA failed: {qa_rep}"
    assert qa_rep["total_existing"] == 6


def test_yunet_25d_ink_face_vs_real_flesh_rejection() -> None:
    # 1. Neutral matte-white 2.5D vinyl sheet must have zero non-porcelain human face detections when allow_expressive_2d_ink=True
    master_png = ROOT / "BCI_Shorts_Channel" / "reference_style_anchors" / "expressive_25d_v8_refs" / "expressive_conflict_master.png"
    img = cv2.imread(str(master_png))
    assert img is not None
    dets = detect_non_porcelain_human_faces_yunet(img, allow_expressive_2d_ink=True)
    assert dets == [], f"Unexpected non-porcelain face dets on expressive_conflict_master: {dets}"

    # 2. If we tint the matte-white faces into realistic peach human skin (BGR ~ [120, 158, 215]), YuNet must catch it!
    flesh_img = img.copy()
    hsv = cv2.cvtColor(flesh_img, cv2.COLOR_BGR2HSV)
    white_mask = (hsv[:, :, 1] <= 55) & (hsv[:, :, 2] >= 145)
    flesh_img[white_mask] = np.array([120, 158, 215], dtype=np.uint8)
    flesh_dets = detect_non_porcelain_human_faces_yunet(flesh_img, allow_expressive_2d_ink=True)
    assert len(flesh_dets) > 0, "Expected YuNet to flag peach-flesh-tinted face"


def test_v8_prompt_builder_contract_and_negative_guards(tmp_path: Path) -> None:
    sents = _sample_v8_sentences()
    vp = populate_expressive_v8_reference_contract(_sample_v8_visual_plan(sents))
    prompts = build_diorama_v7_prompts(vp, sents)
    assert len(prompts) == 20

    v_issues = validate_diorama_v7_prompts(prompts, vp)
    assert v_issues == [], f"Unexpected v8 prompt validation issues: {v_issues}"

    p_dir = tmp_path / "v8_prompt_proj"
    (p_dir / "02_script").mkdir(parents=True)
    (p_dir / "03_visuals").mkdir(parents=True)
    script_doc = {
        "schema": 8,
        "style_profile": "expressive_25d_v8",
        "format_profile": "shorts_expressive_v8",
        "opening_mode": "action",
        "core_reveal_sentence_index": 14,
        "title": vp["title"],
        "doi": vp["doi"],
        "foil_sentence_indices": [4],
        "sentences": sents,
    }
    (p_dir / "02_script" / "script.json").write_text(json.dumps(script_doc, indent=2), encoding="utf-8")
    (p_dir / "03_visuals" / "visual_plan.json").write_text(json.dumps(vp, indent=2), encoding="utf-8")
    write_flow_prompts_json(p_dir, prompts)

    prod_issues = validate_production_diorama_v6(vp, sents, prompts, script_doc=script_doc)
    assert prod_issues == [], f"validate_production_diorama_v6 failed: {prod_issues}"

    contract = compile_episode_qa_contract(vp, sents, prompts, script_doc=script_doc)
    assert contract["style_profile"] == "expressive_25d_v8"
    pre_issues = verify_pre_flow_contract(vp, sents, prompts, script_doc=script_doc)
    assert pre_issues == [], f"verify_pre_flow_contract failed: {pre_issues}"

    # Negative 1: Brain grammar before 55% timeline mark (clip 4 of 20 = 17.5%) must fail!
    bad_vp_early_brain = copy.deepcopy(vp)
    bad_vp_early_brain["clips"][3]["grammar"] = "expressive_xray_brain"
    bad_prompts_1 = build_diorama_v7_prompts(bad_vp_early_brain, sents)
    issues_1 = validate_diorama_v7_prompts(bad_prompts_1, bad_vp_early_brain)
    assert any("55%" in x or "premature 3D brain reveal" in x or "expressive_xray_brain" in x for x in issues_1), f"Expected early brain rejection, got: {issues_1}"

    # Negative 2: Zero cameo_easter_egg cuts must fail!
    bad_vp_no_cameo = copy.deepcopy(vp)
    for c in bad_vp_no_cameo["clips"]:
        c.pop("cameo_easter_egg", None)
        if c.get("grammar") == "expressive_cameo_world":
            c["grammar"] = "expressive_vinyl_world"
    bad_prompts_2 = build_diorama_v7_prompts(bad_vp_no_cameo, sents)
    issues_2 = validate_diorama_v7_prompts(bad_prompts_2, bad_vp_no_cameo)
    assert any("cameo" in x.lower() for x in issues_2), f"Expected missing cameo rejection, got: {issues_2}"

    # Negative 3: >2 tokens in diegetic_text_allowlist must fail!
    bad_vp_allow = copy.deepcopy(vp)
    bad_vp_allow["clips"][0]["diegetic_text_allowlist"] = ["03:00", "HOTEL", "ALARM"]
    bad_prompts_3 = build_diorama_v7_prompts(bad_vp_allow, sents)
    issues_3 = validate_diorama_v7_prompts(bad_prompts_3, bad_vp_allow)
    assert any("diegetic_text_allowlist" in x for x in issues_3), f"Expected allowlist cap rejection, got: {issues_3}"

    # Negative 4: Forbidden 'smooth featureless' token in expressive_25d_v8 scene must fail!
    scene_errs = validate_expressive_v8_scene(
        "smooth featureless mannequin head",
        grammar="expressive_vinyl_world",
    )
    assert any("smooth featureless" in e for e in scene_errs)


def test_r68_packaging_metadata_and_negative_cases() -> None:
    title = "Your Brain's 3 AM Night Watch"
    assert validate_expressive_v8_title(title) == []
    desc = render_editorial_description(
        title=title,
        doi_or_url="10.1016/j.cub.2016.02.063",
        source_summary="Tamaki & Sasaki (2016, Current Biology) tested 35 sleepers on the first-night effect.",
        hashtags=[],
        zero_hashtags=True,
        omit_nicknames=["first-night effect", "first night effect"],
    )
    assert "#" not in title
    assert "#" not in desc
    assert "first-night effect" not in desc.lower()
    pinned = build_expressive_v8_pinned_comment(
        doi="10.1016/j.cub.2016.02.063",
        debate_question="Pack your own pillowcase or let your left brain guard? #Shorts",
    )
    assert "#" not in pinned
    assert "doi.org" not in pinned
    assert "10.1016/" not in pinned
    pinned_frozen = build_expressive_v8_pinned_comment(
        doi="10.1016/j.cub.2016.02.063",
        debate_question="Pack your own pillowcase or let your left brain guard? #Shorts",
        include_doi=True,
    )
    assert "https://doi.org/10.1016/j.cub.2016.02.063" in pinned_frozen

    # Negative checks: hashtag leak, too short/long title, Hangul characters
    assert validate_expressive_v8_title("Brain Watch #Shorts") != []
    assert validate_expressive_v8_title("Too Short") != []
    assert validate_expressive_v8_title("One Two Three Four Five Six Seven Eight Nine") != []
    assert validate_expressive_v8_title("뇌과학 호텔 수면 비밀 공개") != []


@pytest.mark.slow
def test_v8_prosody_audio_ass_xfade_assembly_and_autopsy_e2e(tmp_path: Path) -> None:
    sents = _sample_v8_sentences()
    vp = populate_expressive_v8_reference_contract(_sample_v8_visual_plan(sents))
    prosody_plan = plan_sentence_prosody(sents, None, "expressive_us_v8")
    assert len(prosody_plan) == len(sents)
    # Pivot sentence ('Wait, what...') must have positive gap_before_sec >= 0.24s
    assert float(prosody_plan[6]["gap_before_sec"]) >= 0.24

    p_dir = tmp_path / "v8_e2e_synth_test_proj"
    for sub in ("02_script", "03_visuals/flow_native_clips", "04_audio", "05_assembly", "06_publish"):
        (p_dir / sub).mkdir(parents=True, exist_ok=True)

    script_doc = {
        "schema": 8,
        "style_profile": "expressive_25d_v8",
        "format_profile": "shorts_expressive_v8",
        "prosody_mode": "expressive_us_v8",
        "opening_mode": "action",
        "core_reveal_sentence_index": 14,
        "title": vp["title"],
        "doi": vp["doi"],
        "foil_sentence_indices": [4],
        "sentences": sents,
    }
    (p_dir / "02_script" / "script.json").write_text(json.dumps(script_doc, indent=2), encoding="utf-8")
    (p_dir / "03_visuals" / "visual_plan.json").write_text(json.dumps(vp, indent=2), encoding="utf-8")
    ensure_expressive_v8_reference_pack(p_dir)
    prompts = build_diorama_v7_prompts(vp, sents)
    write_flow_prompts_json(p_dir, prompts)

    # Synthesize deterministic 48kHz per-sentence PCM lines with 3-gear rhythm (~64s total >= 61.5s, Cut 1 <= 1.50s, CV >= 0.18)
    sr = 48000
    dur_cycle = [
        1.10, 2.25, 2.05, 2.35, 2.30, 2.20, 2.15, 4.05, 2.85, 3.65,
        2.55, 3.90, 2.75, 4.15, 3.80, 2.60, 3.75, 2.80, 3.95, 3.15,
    ]
    line_pcms: list[np.ndarray] = []
    for idx, _sent in enumerate(sents, start=1):
        dur_s = dur_cycle[idx - 1]
        n_samp = int(round(dur_s * sr))
        t_arr = np.arange(n_samp, dtype=np.float32) / float(sr)
        f0 = 135.0 if idx == 4 else 195.0  # clip 4 = foil voice
        env = 0.32 * (0.68 + 0.32 * np.sin(2.0 * math.pi * 3.4 * t_arr))
        sig = (env * (0.65 * np.sin(2.0 * math.pi * f0 * t_arr) + 0.25 * np.sin(2.0 * math.pi * 2.0 * f0 * t_arr))).astype(np.float32)
        line_pcms.append(sig)

    # Generate 20 textured moving 540x960 test clips (scaled to 1080x1920 during assembly) + provenance receipt
    import hashlib

    rng = np.random.default_rng(808)
    grain_pool = rng.integers(-8, 9, size=(20, 480, 270, 3), dtype=np.int16)
    prov_clips: list[dict[str, Any]] = []
    for idx in range(1, 21):
        frames: list[np.ndarray] = []
        base_col = np.array([62 + (idx * 7) % 85, 92 + (idx * 9) % 78, 128 + (idx * 11) % 82], dtype=np.int16)
        for f_i in range(24 * 6):  # 6.0s @ 24fps
            canvas = np.clip(base_col + grain_pool[(f_i + idx) % 20], 24, 240).astype(np.uint8)
            cx = 70 + int((f_i * 3 + idx * 9) % 130)
            cy = 150 + int((f_i * 2 + idx * 11) % 120)
            # Matte-white 2.5D character silhouette with dark 2D ink outline
            cv2.circle(canvas, (cx, cy), 38, (238, 240, 242), -1)
            cv2.circle(canvas, (cx, cy), 38, (22, 22, 24), 3)
            cv2.rectangle(canvas, (cx - 32, cy + 38), (cx + 32, cy + 125), (65, 85, 140), -1)
            if idx in (14, 15):
                # 4-color crystal-dome brain motif (crimson + amber + cyan, zero neon green)
                cv2.ellipse(canvas, (135, 190), (58, 44), 0, 0, 180, (55, 45, 220), -1)
                cv2.ellipse(canvas, (135, 190), (58, 44), 0, 180, 360, (225, 190, 40), -1)
                cv2.circle(canvas, (120, 180), 14, (35, 165, 245), -1)
            frames.append(canvas)
        c_path = p_dir / "03_visuals" / "flow_native_clips" / f"clip_{idx}.mp4"
        _write_test_mp4(c_path, frames, fps=24)
        c_sha = hashlib.sha256(c_path.read_bytes()).hexdigest()
        prov_clips.append(
            {
                "clip_index": idx,
                "clip_file": f"clip_{idx}.mp4",
                "sha256": c_sha,
                "duration_sec": 6.0,
                "reference_attached": True,
                "project_url": "https://labs.google/fx/tools/flow/project/test-v8-room",
                "target_id": f"target_v8_{idx}",
            }
        )

    prov_doc = {
        "project_id": p_dir.name,
        "reference_attachment_enforced": True,
        "clips": prov_clips,
    }
    (p_dir / "03_visuals" / "flow_provenance_receipt.json").write_text(json.dumps(prov_doc, indent=2), encoding="utf-8")

    # Verify inspect_diorama_clip_cv passes on expressive_xray_brain test clip
    cv_brain = inspect_diorama_clip_cv(
        p_dir / "03_visuals" / "flow_native_clips" / "clip_14.mp4",
        "expressive_xray_brain",
        style_profile="expressive_25d_v8",
    )
    assert cv_brain["passed"] is True, f"inspect_diorama_clip_cv failed on expressive_xray_brain: {cv_brain}"

    asm_out = assemble_diorama_project(
        p_dir,
        force_rebuild=True,
        align_whisper=False,
        pre_synthesized_lines=line_pcms,
        prosody_mode="expressive_us_v8",
        voice_preset="emma_v7",
        run_posthoc_qa=False,
    )
    final_mp4 = Path(asm_out["final_mp4"])
    assert final_mp4.exists() and final_mp4.stat().st_size > 100_000

    edl = json.loads((p_dir / "05_assembly" / "edit_decision_list.json").read_text(encoding="utf-8"))
    assert edl["style_profile"] == "expressive_25d_v8"
    assert edl["cut_count"] == 20
    assert any(str(c.get("transition_to_next") or "").startswith("dissolve_") for c in edl["cuts"])

    ass_path = p_dir / "04_audio" / "subtitles.ass"
    ass_txt = ass_path.read_text(encoding="utf-8")
    assert f"Style: Default,{cfg.DIORAMA_V7_SUBTITLE_FONT_NAME},{cfg.EXPRESSIVE_V8_SUBTITLE_FONT_SIZE}" in ass_txt
    assert f",{cfg.EXPRESSIVE_V8_SUBTITLE_MARGIN_V},1" in ass_txt
    assert "00E6FF" not in ass_txt.upper()
    assert "&H00FFFFFF" in ass_txt.upper()
    assert "\nDialogue: 3," not in ass_txt  # zero ChapterHeadline dialogue events in v8!

    audio_master = p_dir / "04_audio" / "audio_master.wav"
    assert audio_master.exists() and audio_master.stat().st_size > 200_000

    # Create 3 distinct thumbnails for DQ12
    for v_k, col in (("A", (30, 50, 190)), ("B", (180, 130, 30)), ("C", (50, 160, 90))):
        th = np.full((1920, 1080, 3), col, dtype=np.uint8)
        cv2.circle(th, (540, 860), 260, (242, 242, 245), -1)
        cv2.imwrite(str(p_dir / "06_publish" / f"thumbnail_var_{v_k}.png"), th)

    contract = compile_episode_qa_contract(vp, sents, prompts, script_doc=script_doc)
    (p_dir / "03_visuals" / "episode_qa_contract.json").write_text(json.dumps(contract, indent=2), encoding="utf-8")
    dq_rep = verify_final_mp4_against_contract(p_dir, contract=contract, save_report=True)
    assert dq_rep["schema"] == 8
    assert dq_rep["style_profile"] == "expressive_25d_v8"
    assert dq_rep["gates"]["DQ_CAMEO_single_minicortex"]["passed"] is True
    assert dq_rep["passed"] is True, f"verify_final_mp4_against_contract failed: {json.dumps(dq_rep, indent=2)}"

    # Verify frame drift between EDL total_frames and xfade-assembled MP4 is <= 2 frames!
    vid_metrics = VideoAutopsyEngine.inspect_video_stream(final_mp4, expected_duration_sec=edl["total_duration_sec"])
    assert abs(int(vid_metrics["decoded_frame_count"]) - int(edl["total_frames"])) <= 2

    # Verify Stage 3 MediaIntegrityValidator resolves shorts_expressive_v8 duration range (55..89.5s) instead of 140..179s
    from pipeline.media_integrity import MediaIntegrityValidator

    mi_probe = MediaIntegrityValidator.validate_video_file(
        final_mp4,
        min_size_bytes=10_000,
        require_30s_shorts=True,
        check_motion=False,
        check_audio=True,
    )
    assert mi_probe["passed_integrity"] is True, f"MediaIntegrityValidator failed on v8 final_mp4: {mi_probe}"

    # Verify read-only Studio readiness audit mutates nothing and detects published live proof
    readiness = StudioUploader.audit_v8_channel_readiness()
    assert readiness["live_mutation_applied"] is False
    assert readiness["channel_art_readiness"]["live_channel_art_replaced"] is True
    assert (
        readiness["channel_art_readiness"]["live_published_proof"]
        == "artifacts_archive/01_YouTube_CEO/channel_art_and_cast/youtube_live_published_proof.jpg"
    )
    assert len(readiness["channel_art_readiness"]["avatar_drafts_staged"]) >= 1
    assert len(readiness["channel_art_readiness"]["banner_drafts_staged"]) >= 1


def test_regression_yunet_multitone_cool_and_bw_human_faces_rejected() -> None:
    from pipeline.source_reenactment import detect_human_faces_yunet

    master_png = ROOT / "BCI_Shorts_Channel" / "reference_style_anchors" / "expressive_25d_v8_refs" / "expressive_conflict_master.png"
    img = cv2.imread(str(master_png))
    assert img is not None
    boxes = detect_human_faces_yunet(img)
    assert len(boxes) >= 1

    tones = {
        "nat_caucasian": [132, 156, 202],
        "east_asian": [138, 170, 208],
        "olive_tan": [112, 148, 192],
        "brown_human": [88, 118, 162],
        "cool_blue_human": [195, 155, 130],
    }
    for tone_name, bgr in tones.items():
        tinted = img.copy()
        for bx, by, bw, bh, _ in boxes:
            roi = tinted[max(0, by) : by + bh, max(0, bx) : bx + bw].astype(np.float32)
            lum = cv2.cvtColor(roi.astype(np.uint8), cv2.COLOR_BGR2GRAY).astype(np.float32) / 240.0
            non_ink = lum >= 0.30
            for ch_i in range(3):
                roi[:, :, ch_i][non_ink] = np.clip(lum[non_ink] * bgr[ch_i], 0, 255)
            tinted[max(0, by) : by + bh, max(0, bx) : bx + bw] = roi.astype(np.uint8)
        dets = detect_non_porcelain_human_faces_yunet(tinted, allow_expressive_2d_ink=True)
        assert len(dets) >= 1, f"Expected YuNet to flag {tone_name} human face, got {dets}"

    # Grayscale B&W archival human face must also be rejected
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    white_mask = (hsv[:, :, 1] <= 55) & (hsv[:, :, 2] >= 145)
    bw_gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    bw_gray[white_mask] = np.clip(bw_gray[white_mask].astype(np.float32) * 0.62, 95, 165).astype(np.uint8)
    bw_bgr = cv2.cvtColor(bw_gray, cv2.COLOR_GRAY2BGR)
    assert len(detect_non_porcelain_human_faces_yunet(bw_bgr, allow_expressive_2d_ink=True)) >= 1

    # Warm 2700K tungsten-lit cream-white and amber-lamp-lit 2.5D vinyl faces must NOT false-positive
    warm_vinyl = img.copy()
    warm_vinyl[white_mask] = np.array([205, 228, 245], dtype=np.uint8)
    assert detect_non_porcelain_human_faces_yunet(warm_vinyl, allow_expressive_2d_ink=True) == []

    amber_lamp_vinyl = img.copy()
    amber_lamp_vinyl[white_mask] = np.array([145, 212, 232], dtype=np.uint8)
    assert detect_non_porcelain_human_faces_yunet(amber_lamp_vinyl, allow_expressive_2d_ink=True) == []

    # Soft-focus / blurred Caucasian human face in frame must still be flagged
    blurred_human = img.copy()
    for bx, by, bw, bh, _ in boxes:
        roi = blurred_human[max(0, by) : by + bh, max(0, bx) : bx + bw].astype(np.float32)
        lum = cv2.cvtColor(roi.astype(np.uint8), cv2.COLOR_BGR2GRAY).astype(np.float32) / 240.0
        non_ink = lum >= 0.30
        for ch_i, c_val in enumerate([132, 156, 202]):
            roi[:, :, ch_i][non_ink] = np.clip(lum[non_ink] * c_val, 0, 255)
        blurred_human[max(0, by) : by + bh, max(0, bx) : bx + bw] = roi.astype(np.uint8)
    blurred_human = cv2.GaussianBlur(blurred_human, (9, 9), 2.5)
    assert len(detect_non_porcelain_human_faces_yunet(blurred_human, allow_expressive_2d_ink=True)) >= 1


def test_regression_r68_preserves_verbatim_citations_and_blocks_spoken_nicknames() -> None:
    from pipeline.diorama_batch_orchestrator import _default_metadata_from_script_and_dossier
    from pipeline.prompt_quality_v5 import validate_script_spine_v8
    from pipeline.publish import render_editorial_description

    meta = _default_metadata_from_script_and_dossier(
        project_id="v8_pilot_01_sleep_first_night_watch",
        pillar="brain_health",
        slug="v2_sleep_first_night_hemisphere_watch",
        script_doc={
            "schema": 8,
            "style_profile": "expressive_25d_v8",
            "format_profile": "shorts_expressive_v8",
            "title": "Your Brain's 3 AM Night Watch",
            "doi": "10.1016/j.cub.2016.02.063",
            "omit_experiment_nicknames": ["first-night effect", "first night effect"],
            "debate_question": "Do you pack your own pillowcase or let half your brain stand watch?",
            "sentences": _sample_v8_sentences(),
        },
    )
    desc = meta["description"]
    assert desc.endswith("\n\n#shorts")
    assert "#" not in desc.removesuffix("#shorts")
    assert meta["hashtags"] == ["#shorts"]
    assert "tags" in meta and "shorts" in meta["tags"]
    prose_part, _, bib_part = desc.partition("Primary Peer-Reviewed Sources:")
    assert bib_part, "Expected Primary Peer-Reviewed Sources bibliography block"
    assert "first-night effect" not in prose_part.lower()
    assert "First-Night Effect in Humans" in bib_part
    assert "THE FIRST NIGHT EFFECT" in bib_part

    rendered = render_editorial_description(
        title="Your Brain's 3 AM Night Watch",
        doi_or_url="10.1016/j.cub.2016.02.063",
        source_summary="Why the First-Night Effect happens.\n\nPrimary Peer-Reviewed Sources:\n- Tamaki (2016). First-Night Effect in Humans.",
        hashtags=[],
        zero_hashtags=True,
        omit_nicknames=["first-night effect"],
    )
    r_prose, _, r_bib = rendered.partition("Primary Peer-Reviewed Sources:")
    assert "first-night effect" not in r_prose.lower()
    assert "First-Night Effect in Humans." in r_bib

    # Spoken lines containing omitted academic experiment nicknames must fail validate_script_spine_v8
    bad_sents = list(_sample_v8_sentences())
    bad_sents[4] = "Sleep scientists call this famous phenomenon the first-night effect across two nights."
    spine_issues = validate_script_spine_v8(
        bad_sents,
        script_doc={
            "opening_mode": "action",
            "foil_sentence_indices": [4],
            "omit_experiment_nicknames": ["first-night effect", "first night effect"],
        },
    )
    assert any("omitted experiment nickname" in x for x in spine_issues), f"Expected omitted nickname violation, got: {spine_issues}"


def test_regression_cli_check_auto_dubbing_and_publish_pinned_comment_file(tmp_path: Path) -> None:
    import sys

    from pipeline.publish import PublishStage
    from pipeline.storage import ProjectStorage

    proc = subprocess.run(
        [sys.executable, "-X", "utf8", "main.py", "studio-settings", "--check-auto-dubbing", "--dry-run"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=True,
    )
    payload = json.loads(proc.stdout)
    assert payload["auto_dubbing_check"]["checked"] is True
    assert payload["auto_dubbing_check"]["live_studio_mutated"] is False

    storage = ProjectStorage("v8_test_publish_pin", projects_dir=tmp_path)
    sents = _sample_v8_sentences()
    vp = _sample_v8_visual_plan(sents)
    storage.save_json(
        "02_script",
        "script.json",
        {
            "schema": 8,
            "style_profile": "expressive_25d_v8",
            "format_profile": "shorts_expressive_v8",
            "title": vp["title"],
            "doi": vp["doi"],
            "debate_question": "Do you pack your own pillowcase or let half your brain stand watch?",
            "omit_experiment_nicknames": ["first-night effect"],
            "sentences": sents,
        },
    )
    storage.save_json("03_visuals", "visual_plan.json", vp)
    src_img = tmp_path / "src_thumb.png"
    cv2.imwrite(str(src_img), np.full((1920, 1080, 3), (40, 65, 130), dtype=np.uint8))

    pub = PublishStage(storage)
    pub.run(
        title=vp["title"],
        hashtags=["#Shorts"],
        doi=vp["doi"],
        source_summary="Tamaki et al. (2016) scanned 35 sleepers across two nights.",
        thumbnail_source_img=src_img,
    )
    pin_file = storage.get_stage_dir("06_publish") / "pinned_comment.txt"
    assert pin_file.exists(), "PublishStage.run must write 06_publish/pinned_comment.txt"
    pin_txt = pin_file.read_text(encoding="utf-8").strip()
    assert "doi.org" not in pin_txt
    assert pin_txt == "Do you pack your own pillowcase or let half your brain stand watch?"
    assert "#" not in pin_txt
    saved_meta = storage.load_json("06_publish", "metadata.json")
    assert saved_meta["hashtags"] == ["#shorts"]
    assert saved_meta["description"].endswith("\n\n#shorts")
    assert "#" not in saved_meta["description"].removesuffix("#shorts")
    assert "tags" in saved_meta and "shorts" in saved_meta["tags"]
    assert saved_meta["ai_content_declaration"] is True
    assert "doi.org" not in saved_meta["description"]


def test_regression_v8_scene_anchor_synthesis_track_a_and_cross_location_gate() -> None:
    sents = _sample_v8_sentences()

    # 1. Un-mutated v8 plan with expressive_split_contrast / expressive_character_action / expressive_macro_prop builds & validates cleanly
    raw_vp = _sample_v8_visual_plan(sents)
    raw_prompts = build_diorama_v7_prompts(raw_vp, sents)
    assert validate_diorama_v7_prompts(raw_prompts, raw_vp) == []

    # 2. synthesize_scene_anchors=True builds single-scene 9:16 anchors instead of binding multi-panel sheets directly, and preserves track_a
    track_a_vp = copy.deepcopy(raw_vp)
    track_a_vp["reenactment_track"] = "track_a"
    populated = populate_expressive_v8_reference_contract(track_a_vp, synthesize_scene_anchors=True)
    assert populated["reenactment_track"] == "track_a"
    anchor_files = {a["filename"] for a in populated.get("reference_anchors") or []}
    assert "ref_cameo_9x16.png" in anchor_files
    assert "ref_xray_brain_9x16.png" in anchor_files
    assert any(f.startswith("ref_loc_") for f in anchor_files)
    for c in populated["clips"]:
        assert not str(c.get("reference_image") or "").endswith("species_opt1_sheet.png")
        assert not str(c.get("reference_image") or "").endswith("xray_brain75_master.png")

    # 3. Cross-location reference_image leak & non-brain xray_brain leak are caught by validate_production_diorama_v6 on v8
    bad_vp = copy.deepcopy(populated)
    bad_vp["clips"][0]["location_id"] = "brown_sleep_lab"  # clip 1 still binds hotel_room_3am anchor!
    bad_vp["clips"][1]["reference_image"] = "03_visuals/reference_images/ref_xray_brain_9x16.png"
    bad_prompts = build_diorama_v7_prompts(bad_vp, sents)
    leak_issues = validate_production_diorama_v6(bad_vp, sents, bad_prompts)
    assert any("cross-location prop/room leak" in x for x in leak_issues), f"Expected cross-location leak error: {leak_issues}"
    assert any("non-brain clip binds cutaway brain reference" in x for x in leak_issues), f"Expected brain ref leak error: {leak_issues}"


def test_regression_v8_edl_6_transitions_room_tone_rms_foley_and_recut(tmp_path: Path) -> None:
    import inspect
    from pipeline.diorama_assembler import recut_diorama_cuts

    # 1. Default strips ghosting alpha dissolves to hard cuts; explicit allow_alpha_dissolves=True preserves all 6
    sents = _sample_v8_sentences()
    vp = _sample_v8_visual_plan(sents)
    canonical_6 = list(cfg.EXPRESSIVE_V8_TRANSITION_TYPES)
    for i, c in enumerate(vp["clips"]):
        c["transition_to_next"] = canonical_6[i % len(canonical_6)]
    timings = [
        {"sentence_index": i + 1, "start_sec": i * 4.0, "end_sec": (i + 1) * 4.0, "text": s}
        for i, s in enumerate(sents)
    ]
    clip_files = [tmp_path / f"clip_{i}.mp4" for i in range(1, len(sents) + 1)]
    edl_crisp = build_v7_dynamic_edl(vp, timings, clip_files, speech_end_sec=64.0, total_duration_sec=64.2)
    assert not any("dissolve" in str(c["transition_out"]) for c in edl_crisp["cuts"])
    vp_opt_in = copy.deepcopy(vp)
    vp_opt_in["allow_alpha_dissolves"] = True
    edl = build_v7_dynamic_edl(vp_opt_in, timings, clip_files, speech_end_sec=64.0, total_duration_sec=64.2)
    observed_tr = {c["transition_out"] for c in edl["cuts"]}
    assert set(canonical_6).issubset(observed_tr), f"Missing canonical transitions in opt-in EDL: {observed_tr}"

    # 2. Room-tone RMS (~-30 dBFS) & outgoing-cut transition foley lookup
    sr = 48000
    master_wav = tmp_path / "master_test.wav"
    t = np.arange(sr * 8, dtype=np.float32) / float(sr)
    # Two spoken segments [0.2..3.6s] and [4.2..7.6s] with a clean breath gap [3.65..4.15s]
    pcm = np.zeros_like(t)
    mask_speech = ((t >= 0.2) & (t < 3.6)) | ((t >= 4.2) & (t < 7.6))
    pcm[mask_speech] = (0.22 * np.sin(2.0 * math.pi * 185.0 * t[mask_speech])).astype(np.float32)

    test_edl = {
        "style_profile": "expressive_25d_v8",
        "gap_windows": [[3.65, 4.15]],
        "cuts": [
            {"cut_index": 1, "out_start_sec": 0.0, "out_end_sec": 3.85, "grammar": "expressive_vinyl_world", "transition_out": "action_impact_cut"},
            {"cut_index": 2, "out_start_sec": 3.85, "out_end_sec": 8.00, "grammar": "expressive_vinyl_world", "transition_out": "daisy_chain_bridge"},
        ],
    }
    generate_diorama_audio_master(master_wav, pcm, sr, 7.60, test_edl)
    with wave.open(str(master_wav), "rb") as rf:
        raw_m = np.frombuffer(rf.readframes(rf.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0
        st_m = raw_m.reshape(-1, rf.getnchannels())

    # Tail window [7.62..7.82s] has zero speech & monotonic -18 dBFS climax BGM + -30 dBFS room tone
    room_win = st_m[int(7.62 * sr) : int(7.82 * sr)]
    room_rms_db = 20.0 * math.log10(max(1e-7, float(np.sqrt(np.mean(room_win * room_win)))))
    room_peak_db = 20.0 * math.log10(max(1e-7, float(np.max(np.abs(room_win)))))
    assert -28.0 <= room_rms_db <= -14.0, f"Expected monotonic climax BGM+room RMS near -18 dBFS, got {room_rms_db:.2f} dBFS"

    # Outgoing-cut gap window [3.84..3.96s] must synthesize 'thud' from outgoing cut #1 ('action_impact_cut', NOT cut #2 'daisy_chain_bridge')
    assert test_edl.get("placed_foley") and test_edl["placed_foley"][0]["cue"] == "thud"
    gap_win = st_m[int(3.84 * sr) : int(3.96 * sr)]
    gap_peak_db = 20.0 * math.log10(max(1e-7, float(np.max(np.abs(gap_win)))))
    early_bg_win = st_m[int(0.02 * sr) : int(0.16 * sr)]
    early_bg_peak_db = 20.0 * math.log10(max(1e-7, float(np.max(np.abs(early_bg_win)))))
    assert gap_peak_db > early_bg_peak_db + 3.0, f"Expected outgoing-cut thud transient peak ({gap_peak_db:.2f} dB vs early bg {early_bg_peak_db:.2f} dB)"

    # 3. recut_diorama_cuts source explicitly guards expressive_25d_v8 from lowpoly_pastel_v7 washout & delegates dissolve_6f
    recut_src = inspect.getsource(recut_diorama_cuts)
    assert "is_expressive_v8_plan(edl)" in recut_src
    assert "dissolve_6f" in recut_src

    # 4. Q4 reference_image_qa allows cameo_anchor prop tabletop with warm walnut wood background when YuNet finds zero human faces
    from pipeline.reference_image_qa import inspect_single_reference_image

    cameo_png = tmp_path / "warm_cameo_test.png"
    rng_c = np.random.default_rng(42)
    # Warm walnut wood background (BGR ~ [65, 110, 165]) + bright miniature 4-color Mini-Cortex & porcelain prop details
    canvas_c = np.clip(np.array([65, 110, 165], dtype=np.int16) + rng_c.integers(-22, 23, size=(1920, 1080, 3)), 15, 240).astype(np.uint8)
    cv2.circle(canvas_c, (360, 1020), 150, (240, 240, 244), -1)
    cv2.circle(canvas_c, (720, 1080), 95, (235, 195, 45), -1)
    cv2.circle(canvas_c, (720, 1020), 65, (65, 55, 225), -1)
    cv2.imwrite(str(cameo_png), canvas_c)
    q_res = inspect_single_reference_image(
        cameo_png,
        {
            "ref_id": "warm_cameo_test",
            "filename": "warm_cameo_test.png",
            "category": "clip_keyframe_anchor",
            "role": "cameo_anchor",
            "setting": "real_env",
            "style_profile": "expressive_25d_v8",
            "schema_version": 8,
        },
    )
    assert "Q4_porcelain_cast_fidelity" not in (q_res.get("failed_axes") or []), f"Expected cameo_anchor Q4 pass: {q_res}"

    # 5. _submit_diorama_prompt_zero_credit keeps secondary_reference_image multi-panel ingredient sheets out of Veo 3.1 Lite End Frame slot
    from pipeline.flow_diorama_sharded_worker import _submit_diorama_prompt_zero_credit

    sub_src = inspect.getsource(_submit_diorama_prompt_zero_credit)
    assert "end_ref_is_secondary_ingredient" in sub_src
    assert "not end_ref_is_secondary_ingredient" in sub_src


def test_dossier_seed_expressive_25d_v8_cli_and_overwrite_guard(tmp_path: Path) -> None:
    import sys

    from pipeline import research_dossier as rd

    dossiers_root = tmp_path / "research_dossiers"
    slug = "v8_seed_parity_case"

    subprocess.run(
        [
            sys.executable,
            "-X",
            "utf8",
            "main.py",
            "dossier",
            "init",
            "--slug",
            slug,
            "--root",
            str(dossiers_root),
            "--topic",
            "Hemisphere Night Watch",
            "--pillar",
            "brain_health",
            "--everyday-domain",
            "sleep",
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=True,
    )

    src_path = dossiers_root / slug / "01_sources.json"
    src_doc = json.loads(src_path.read_text(encoding="utf-8"))
    src_doc["sources"] = [
        {
            "type": "primary",
            "doi": "10.1016/j.cub.2016.02.063",
            "title": "Night Watch in One Brain Hemisphere during Sleep",
        }
    ]
    src_path.write_text(json.dumps(src_doc, indent=2), encoding="utf-8")

    # 1. write_draft=False returns Schema 8 payload in memory without creating diorama_v8_expressive/
    mem_only = rd.diorama_seed_from_dossier(
        slug,
        root=dossiers_root,
        style_profile="expressive_25d_v8",
        write_draft=False,
    )
    assert mem_only["schema"] == 8
    assert mem_only["style_profile"] == "expressive_25d_v8"
    assert mem_only["shorts_format_profile"] == "shorts_expressive_v8"
    assert mem_only["prosody_mode"] == "expressive_us_v8"
    assert mem_only["voice_preset"] == "elevenlabs_v4"
    assert mem_only["foil_voice_preset"] == "elevenlabs_v4_male"
    assert mem_only["foil_sentence_indices"] == []
    assert not (dossiers_root / slug / "diorama_v8_expressive").exists()

    # 2. CLI `main.py dossier seed --style-profile expressive_25d_v8` writes diorama_v8_expressive/{visual_plan.json,script.json}
    proc = subprocess.run(
        [
            sys.executable,
            "-X",
            "utf8",
            "main.py",
            "dossier",
            "seed",
            "--slug",
            slug,
            "--root",
            str(dossiers_root),
            "--style-profile",
            "expressive_25d_v8",
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=True,
    )
    cli_seed = json.loads(proc.stdout)
    assert cli_seed["schema"] == 8
    assert cli_seed["style_profile"] == "expressive_25d_v8"
    assert cli_seed["shorts_format_profile"] == "shorts_expressive_v8"
    assert cli_seed["prosody_mode"] == "expressive_us_v8"
    assert cli_seed["voice_preset"] == "elevenlabs_v4"
    assert cli_seed["foil_voice_preset"] == "elevenlabs_v4_male"
    assert cli_seed["foil_sentence_indices"] == []
    assert cli_seed["doi"] == "10.1016/j.cub.2016.02.063"
    assert len(cli_seed.get("reference_anchors") or []) >= 2

    draft_dir = dossiers_root / slug / "diorama_v8_expressive"
    vp_file = draft_dir / "visual_plan.json"
    sc_file = draft_dir / "script.json"
    assert vp_file.is_file()
    assert sc_file.is_file()
    sc_disk = json.loads(sc_file.read_text(encoding="utf-8"))
    assert sc_disk["shorts_format_profile"] == "shorts_expressive_v8"
    assert sc_disk["prosody_mode"] == "expressive_us_v8"
    assert sc_disk["voice_preset"] == "elevenlabs_v4"
    assert sc_disk["foil_voice_preset"] == "elevenlabs_v4_male"
    assert sc_disk["foil_sentence_indices"] == []
    assert sc_disk["pillar"] == "brain_health"
    assert sc_disk["everyday_domain"] == "sleep"

    # 3. Overwrite guard preserves authored files when overwrite=False, refreshes via CLI `--overwrite`
    sc_disk["title"] = "Custom Authored V8 Title"
    sc_file.write_text(json.dumps(sc_disk, indent=2), encoding="utf-8")
    rd.diorama_seed_from_dossier(slug, root=dossiers_root, style_profile="expressive_25d_v8", overwrite=False)
    assert json.loads(sc_file.read_text(encoding="utf-8"))["title"] == "Custom Authored V8 Title"
    subprocess.run(
        [
            sys.executable,
            "-X",
            "utf8",
            "main.py",
            "dossier",
            "seed",
            "--slug",
            slug,
            "--root",
            str(dossiers_root),
            "--style-profile",
            "expressive_25d_v8",
            "--overwrite",
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=True,
    )
    assert json.loads(sc_file.read_text(encoding="utf-8"))["title"] == "Hemisphere Night Watch"

    # 4. Long slug (>36 chars): location_id must NOT truncate away from default_location_id, and seeded_placeholder
    #    anchors must yield cleanly to synthesize_scene_anchors=True once clips are authored.
    long_slug = "v2_sleep_first_night_hemisphere_watch_extended_case_study"
    assert len(long_slug) > 36
    rd.init_dossier(
        long_slug,
        "Extended Night Watch Case",
        pillar="brain_health",
        visual_mode="HYBRID",
        root=dossiers_root,
        everyday_domain="sleep",
    )
    long_seed = rd.diorama_seed_from_dossier(long_slug, root=dossiers_root, style_profile="expressive_25d_v8")
    assert len(long_seed["default_location_id"]) > 36
    loc_anc = next(a for a in long_seed["reference_anchors"] if a["role"] == "reenactment")
    assert loc_anc["location_id"] == long_seed["default_location_id"]
    assert loc_anc["seeded_placeholder"] is True

    sents = _sample_v8_sentences()
    authored_plan = _sample_v8_visual_plan(sents)
    long_seed["clips"] = copy.deepcopy(authored_plan["clips"])
    rebound = populate_expressive_v8_reference_contract(long_seed, synthesize_scene_anchors=True)
    assert all(not a.get("seeded_placeholder") for a in rebound["reference_anchors"])
    cameo_anc = next(a for a in rebound["reference_anchors"] if a["role"] == "cameo_anchor")
    xray_anc = next(a for a in rebound["reference_anchors"] if a["category"] == "brain_anchor")
    assert cameo_anc["clip_number"] == 10
    assert xray_anc["clip_number"] == 14


def test_empty_v8_seed_stub_does_not_hijack_authored_v7_draft(tmp_path: Path, monkeypatch) -> None:
    import pipeline.storage as storage_mod
    from pipeline import diorama_batch_orchestrator as dbo
    from pipeline import research_dossier as rd

    dossiers_root = tmp_path / "dossiers"
    projects_root = tmp_path / "projects"
    dossiers_root.mkdir(parents=True)
    projects_root.mkdir(parents=True)
    slug = "test_coexisting_v7_and_seeded_v8"
    rd.init_dossier(slug, "Coexisting Drafts Case", pillar="cognitive_illusions", root=dossiers_root)

    # Seed an empty v8 stub (sentences=[], clips=[]) alongside an authored v7 porcelain draft
    rd.diorama_seed_from_dossier(slug, root=dossiers_root, style_profile="expressive_25d_v8")
    v7_dir = dossiers_root / slug / "diorama_v7_porcelain"
    v7_dir.mkdir(parents=True, exist_ok=True)
    v7_sents = [f"Sentence number {i} tests visual tabletop geometry in the bright studio." for i in range(1, 21)]
    v7_sents[0] = "Your eyes swear both tabletops differ wildly in length!"
    v7_sents[1] = "Yet a plain brass ruler proves every edge matches to the millimeter."
    v7_sents[2] = "In 1990 at Stanford, Roger Shepard drew two tables that fooled vision scientists."
    (v7_dir / "script.json").write_text(
        json.dumps(
            {
                "schema": 7,
                "profile": "neuro_diorama",
                "style_profile": "porcelain_cinematic_v7",
                "prosody_mode": "dynamic_us_v7",
                "voice_preset": "emma_v7",
                "title": "Two Identical Tables That Fool Every Eye",
                "sentences": v7_sents,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    v7_clips = [
        {
            "clip_number": i,
            "sentence_index": i,
            "end_sentence_index": i,
            "act": min(6, ((i - 1) * 6) // 20 + 1),
            "grammar": "porcelain_reenactment_world",
            "camera_move": "gentle_push_in" if i % 2 else "locked_tripod",
            "environment": "bright Stanford drafting studio with two wooden tables",
            "action": "places a brass ruler across the left wooden tabletop",
            "consequence": "the brass markings align edge to edge across the surface",
        }
        for i in range(1, 21)
    ]
    (v7_dir / "visual_plan.json").write_text(
        json.dumps(
            {
                "schema": 7,
                "profile": "neuro_diorama",
                "style_profile": "porcelain_cinematic_v7",
                "dossier": slug,
                "clips": v7_clips,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(rd, "dossier_dir", lambda s, root=None: (root or dossiers_root) / str(s))
    monkeypatch.setattr(dbo, "PROJECTS_DIR", projects_root)
    monkeypatch.setattr(storage_mod, "PROJECTS_DIR", projects_root)
    monkeypatch.setattr(cfg, "PROJECTS_DIR", projects_root)

    synced_dir = dbo.sync_project_from_dossier_diorama(
        {"project_id": "proj_coexist_test", "slug": slug, "pillar": "cognitive_illusions"}
    )
    assert synced_dir == projects_root / "proj_coexist_test"
    manifest = json.loads((synced_dir / "00_project_manifest.json").read_text(encoding="utf-8"))
    assert manifest["style_profile"] == "porcelain_cinematic_v7"
    assert manifest["schema_version"] == 7

    # And if draft_subdir="diorama_v8_expressive" IS explicitly requested, it honors the explicit pin (and fails empty-clips build as expected)
    with pytest.raises(ValueError, match="expressive_25d_v8"):
        dbo.sync_project_from_dossier_diorama(
            {
                "project_id": "proj_coexist_v8_pin",
                "slug": slug,
                "pillar": "cognitive_illusions",
                "draft_subdir": "diorama_v8_expressive",
            }
        )


def test_studio_readiness_dynamic_proof_and_auto_dubbing_mock_live_cdp(tmp_path: Path, monkeypatch) -> None:
    import sys
    from contextlib import asynccontextmanager

    import pipeline.cdp_tab_lease as tab_lease_mod
    from pipeline.studio.config import CHANNEL_ID, STUDIO_SETTINGS_SELECTORS
    from pipeline.studio.uploader import StudioUploader

    # 1. Dynamic proof check: absent -> False, 0-byte -> False, corrupt non-image bytes -> False, valid JPEG/PNG -> True
    art_dir = tmp_path / "artifacts_archive" / "01_YouTube_CEO" / "channel_art_and_cast"
    art_dir.mkdir(parents=True, exist_ok=True)
    r_missing = StudioUploader.audit_v8_channel_readiness(workspace_root=tmp_path)
    assert r_missing["channel_art_readiness"]["live_channel_art_replaced"] is False
    assert r_missing["channel_art_readiness"]["live_published_proof"] is None

    proof = art_dir / "youtube_live_published_proof.jpg"
    proof.write_bytes(b"")
    assert StudioUploader.audit_v8_channel_readiness(workspace_root=tmp_path)["channel_art_readiness"]["live_channel_art_replaced"] is False

    proof.write_bytes(b"todo_not_a_real_image_header")
    assert StudioUploader.audit_v8_channel_readiness(workspace_root=tmp_path)["channel_art_readiness"]["live_channel_art_replaced"] is False

    proof.write_bytes(b"\x89PNG\r\n\x1a\nverified_png_payload")
    assert StudioUploader.audit_v8_channel_readiness(workspace_root=tmp_path)["channel_art_readiness"]["live_channel_art_replaced"] is True

    proof.write_bytes(b"\xff\xd8\xff\xe0verified_jpeg_payload")
    r_present = StudioUploader.audit_v8_channel_readiness(workspace_root=tmp_path)
    assert r_present["channel_art_readiness"]["live_channel_art_replaced"] is True
    assert (
        r_present["channel_art_readiness"]["live_published_proof"]
        == "artifacts_archive/01_YouTube_CEO/channel_art_and_cast/youtube_live_published_proof.jpg"
    )

    # 2. Offline dry-run auto-dubbing inspection (API + CLI subprocess)
    uploader = StudioUploader(cdp_port=9222)
    dry_res = uploader.inspect_auto_dubbing_settings(dry_run=True)
    assert dry_res["checked"] is True
    assert dry_res["dry_run"] is True
    assert dry_res["live_dom_inspected"] is False
    assert dry_res["live_studio_mutated"] is False

    cli_dry = subprocess.run(
        [sys.executable, "-X", "utf8", "main.py", "studio-settings", "--check-auto-dubbing", "--dry-run"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=True,
    )
    cli_dry_doc = json.loads(cli_dry.stdout)
    assert cli_dry_doc["live_mutation_applied"] is False
    assert cli_dry_doc["auto_dubbing_check"]["dry_run"] is True
    assert cli_dry_doc["auto_dubbing_check"]["live_dom_inspected"] is False
    assert cli_dry_doc["auto_dubbing_check"]["live_studio_mutated"] is False

    # 3. Mocked live CDP read-only inspection (verifies background lease, Cancel close, zero Save click,
    #    primary-vs-review control priority, and fail-loud navigation guard that still clicks Cancel & closes tab)
    lease_events: dict[str, object] = {"closed": False, "clicks": [], "sends": [], "eval_calls": 0}
    state: dict[str, Any] = {
        "url": f"https://studio.youtube.com/channel/{CHANNEL_ID}",
        "fail_adv_wait": False,
        "chan_controls": [
            {
                "tag": "ytcp-button",
                "id": "translations-settings-container",
                "name": "",
                "test_id": "",
                "label": "Automatic dubbing Automatically translates your audio tracks into different languages. Enable",
                "action_button": "Enable",
                "checked": False,
                "disabled": False,
            }
        ],
    }

    class _FakeCDPClient:
        def __init__(self, channel_url: str) -> None:
            self.channel_url = channel_url
            self._scan_count = 0

        async def send(self, method: str, params=None, timeout_sec: float = 30.0):
            lease_events["sends"].append((method, params))  # type: ignore[union-attr]
            return {}

        async def wait_for_element(self, selectors, timeout_sec: float = 10.0):
            if state["fail_adv_wait"] and selectors == STUDIO_SETTINGS_SELECTORS["uploads_advanced_subtab"]:
                return False
            return selectors[0] if isinstance(selectors, list) else str(selectors)

        async def click(self, selectors) -> bool:
            lease_events["clicks"].append(selectors)  # type: ignore[union-attr]
            return True

        async def eval(self, expression: str):
            lease_events["eval_calls"] = int(lease_events["eval_calls"]) + 1  # type: ignore[arg-type]
            if expression == "location.href":
                return self.channel_url
            if "document.querySelector('a[href*=" in expression:
                return CHANNEL_ID in self.channel_url
            if "#entity-name" in expression:
                return "ALL ABOUT BRAIN" if CHANNEL_ID in self.channel_url else "Wrong Channel"
            if "dialogFound" in expression:
                self._scan_count += 1
                if self._scan_count == 1:
                    return {
                        "dialogFound": True,
                        "audioLanguage": "English (United States)",
                        "metadataLanguage": "English (United States)",
                        "category": "Science and technology",
                        "saveButtonEnabled": False,
                        "controls": [],
                        "visibleSectionLabels": ["Video language", "Title and description language"],
                    }
                return {
                    "dialogFound": True,
                    "audioLanguage": "",
                    "metadataLanguage": "",
                    "category": "",
                    "saveButtonEnabled": False,
                    "controls": list(state["chan_controls"]),
                    "visibleSectionLabels": ["Automatic dubbing"],
                }
            if "ytcp-settings-dialog" in expression:
                return True
            return None

    @asynccontextmanager
    async def _fake_leased_tab(initial_url="about:blank", *, purpose="cdp_worker", cdp_port=9222, cdp_host="127.0.0.1", background=True, **kwargs):
        lease_events["initial_url"] = initial_url
        lease_events["purpose"] = purpose
        lease_events["background"] = background
        lease_events["closed"] = False
        try:
            yield _FakeCDPClient(state["url"]), "FAKE_TARGET_9222", "owner_test"
        finally:
            lease_events["closed"] = True

    async def _fake_focus_emulation(client) -> bool:
        lease_events["focus_emulated"] = True
        return True

    monkeypatch.setattr(tab_lease_mod, "leased_cdp_tab", _fake_leased_tab)
    monkeypatch.setattr(tab_lease_mod, "enable_background_focus_emulation", _fake_focus_emulation)
    monkeypatch.setattr(tab_lease_mod, "get_tab_lease", lambda target_id, cdp_port=9222: None)

    live_res = uploader.inspect_auto_dubbing_settings(dry_run=False)
    assert lease_events["background"] is True
    assert lease_events["purpose"] == "studio_check_auto_dubbing"
    assert lease_events["focus_emulated"] is True
    assert lease_events["closed"] is True
    assert STUDIO_SETTINGS_SELECTORS["settings_save_button"] not in lease_events["clicks"]  # type: ignore[operator]
    assert STUDIO_SETTINGS_SELECTORS["settings_cancel_button"] in lease_events["clicks"]  # type: ignore[operator]
    assert live_res["live_dom_inspected"] is True
    assert live_res["live_studio_mutated"] is False
    assert live_res["settings_dialog_closed"] is True
    assert live_res["dialog_closed_via_cancel"] is True
    assert live_res["leased_tab_closed"] is True
    assert live_res["audio_language"] == "English (United States)"
    assert live_res["metadata_language"] == "English (United States)"
    assert live_res["auto_dubbing_control_present"] is True
    assert live_res["auto_dubbing_checked"] is False
    assert live_res["channel_auto_dubbing_checked"] is False
    assert live_res["controls"][0]["action_button"] == "Enable"

    # Secondary 'Manually review dubbed audio' = False must not shadow primary 'Allow automatic dubbing' = True
    state["chan_controls"] = [
        {
            "tag": "ytcp-checkbox-lit",
            "id": "manual-review-dubbing",
            "name": "",
            "test_id": "",
            "label": "Manually review dubbed audio before publishing",
            "checked": False,
            "disabled": False,
        },
        {
            "tag": "ytcp-checkbox-lit",
            "id": "allow-automatic-dubbing",
            "name": "",
            "test_id": "",
            "label": "Allow automatic dubbing",
            "checked": True,
            "disabled": False,
        },
    ]
    opted_res = uploader.inspect_auto_dubbing_settings(dry_run=False)
    assert opted_res["auto_dubbing_checked"] is True
    assert opted_res["channel_auto_dubbing_checked"] is True

    # Error-path boundary 1: missing Advanced settings subtab must raise RuntimeError (never return empty bogus telemetry)
    # while STILL closing ytcp-settings-dialog via Cancel and releasing the leased tab!
    lease_events["clicks"] = []
    state["fail_adv_wait"] = True
    with pytest.raises(RuntimeError, match="Advanced settings subtab"):
        uploader.inspect_auto_dubbing_settings(dry_run=False)
    assert STUDIO_SETTINGS_SELECTORS["settings_cancel_button"] in lease_events["clicks"]  # type: ignore[operator]
    assert lease_events["closed"] is True
    state["fail_adv_wait"] = False

    # Error-path boundary 2: wrong channel in Studio session must abort before opening Settings and still release leased tab
    state["url"] = "https://studio.youtube.com/channel/UC_WRONG_ACCOUNT_000"
    with pytest.raises(RuntimeError, match="not ALL ABOUT BRAIN"):
        uploader.inspect_auto_dubbing_settings(dry_run=False)
    assert lease_events["closed"] is True


def test_r68_agents_and_skill_docs_sync_and_compactness() -> None:
    import re as _re

    agents_md = ROOT / ".agents" / "AGENTS.md"
    rules_dir = ROOT / ".agents" / "rules"
    script_skill = ROOT / ".agents" / "skills" / "youtube-script" / "SKILL.md"
    produce_skill = ROOT / ".agents" / "skills" / "youtube-produce" / "SKILL.md"
    studio_skill = ROOT / ".agents" / "skills" / "youtube-studio" / "SKILL.md"

    agents_txt = agents_md.read_text(encoding="utf-8")
    assert len(agents_txt.splitlines()) <= 60
    assert 3_000 <= len(agents_md.read_bytes()) <= 6_500
    assert "R68" in agents_txt
    assert "expressive_25d_v8" in agents_txt
    assert "elevenlabs_v4" in agents_txt

    rules_txt = "\n".join(
        (rules_dir / fn).read_text(encoding="utf-8")
        for fn in (
            "diorama_assembly_subtitles_rules.md",
            "episode_qa_triage_rules.md",
            "thumbnail_r65_rules.md",
            "archival_reenactment_rules.md",
            "data_stamp_charts_rules.md",
            "real_world_drone_refs_rules.md",
            "hook_pacing_beatcard_rules.md",
            "arrows_callouts_motion_rules.md",
            "youtube_studio_operations.md",
        )
    )
    assert 'DEFAULT_DIORAMA_STYLE_PROFILE="porcelain_cinematic_v7"' in rules_txt
    r68_section = rules_txt
    for token in (
        "expressive_25d_v8",
        "shorts_expressive_v8",
        "61.5–88.0s",
        "18–28",
        "EXPRESSIVE_V8_CAMEO_COUNT_PER_EPISODE = 0",
        "expressive_us_v8",
        "elevenlabs_v4",
        "MarginV = EXPRESSIVE_V8_SUBTITLE_MARGIN_V = 510",
        "82pt",
        "EXPRESSIVE_V8_OUTRO_TAIL_SEC = 0.20",
        "studio-settings --check-auto-dubbing",
    ):
        assert token in r68_section, f"Missing {token!r} in active R68 split rules"
    assert "AvaMultilingualNeural" not in r68_section

    # Every UPPER_SNAKE constant named in R68 must actually exist in pipeline/config.py (blocks hallucinated constant names)
    for const_sym in set(_re.findall(r"\b(?:EXPRESSIVE|SHORTS_EXPRESSIVE|PROMPT_SCHEMA_VERSION|R68)_[A-Z0-9_]+\b", r68_section)):
        assert hasattr(cfg, const_sym), f"R68 docs reference non-existent config constant {const_sym!r}"

    script_txt = script_skill.read_text(encoding="utf-8")
    produce_txt = produce_skill.read_text(encoding="utf-8")
    studio_txt = studio_skill.read_text(encoding="utf-8")
    assert "R68" in script_txt
    assert "R68" in produce_txt
    assert "--check-auto-dubbing" in studio_txt
    assert "elevenlabs_v4" in script_txt
    assert "elevenlabs_v4" in produce_txt
    assert "AvaMultilingualNeural" not in produce_txt
    for tr_name in cfg.EXPRESSIVE_V8_TRANSITION_TYPES:
        assert tr_name in r68_section, f"Missing transition {tr_name!r} in neuro_diorama_rules.md"
        assert tr_name in script_txt, f"Missing transition {tr_name!r} in youtube-script/SKILL.md"
    for gr_name in cfg.EXPRESSIVE_V8_VISUAL_GRAMMARS:
        assert gr_name in script_txt, f"Missing grammar {gr_name!r} in youtube-script/SKILL.md"


def test_v8_boost_andrew_clauses_rising_bgm_daisy_keyframes_and_camera_bridges(tmp_path: Path) -> None:
    from pipeline.prosody import crossfade_clause_pcms, plan_expressive_v8_clauses
    from pipeline.voice_fallback import _trim_waveform_silences_and_breaths, resolve_diorama_voice_preset

    # 1. Voice preset resolution: untagged v8 & v7 -> elevenlabs_v4 default; explicit el_researcher_v4 preserved
    v8_id, v8_preset = resolve_diorama_voice_preset(None, {"style_profile": "expressive_25d_v8"})
    v7_id, v7_preset = resolve_diorama_voice_preset(None, {"style_profile": "porcelain_cinematic_v7"})
    explicit_r_id, explicit_r_preset = resolve_diorama_voice_preset("el_researcher_v4", {"style_profile": "expressive_25d_v8"})
    assert v8_id == "elevenlabs_v4"
    assert v8_preset["elevenlabs_voice_id"] == "CwhRBWXzGAHq8TQ4Fs17"
    assert v8_preset["pitch"] == "+0Hz"
    assert v7_id == "elevenlabs_v4"
    assert explicit_r_id == "el_researcher_v4"
    assert explicit_r_preset["elevenlabs_voice_id"] == "tnSpp4vdxKPjI9w0GnoV"

    # 2. Multi-turn single-<prosody> clause planner & 20ms click-free raised-cosine crossfade + edge cases
    assert plan_expressive_v8_clauses("", "+16%", "+16Hz") == []
    single_cl = plan_expressive_v8_clauses("Short line!", "+16%", "+16Hz")
    assert len(single_cl) == 1 and single_cl[0]["text"].endswith("!")
    pivot_cl = plan_expressive_v8_clauses(
        "Wait, why did the left half stay wide awake all night?",
        "+16%",
        "+16Hz",
    )
    assert len(pivot_cl) == 2
    assert pivot_cl[0]["rate"] != pivot_cl[1]["rate"]

    dash_cl = plan_expressive_v8_clauses(
        "Night one looked peaceful on paper — then the hidden alarm fired fast!",
        "+16%",
        "+16Hz",
    )
    assert len(dash_cl) == 2 and dash_cl[1]["text"].endswith("!")

    sr = 48000
    assert crossfade_clause_pcms([], sr=sr).size == 0
    tiny = np.ones(12, dtype=np.float32) * 0.2
    assert len(crossfade_clause_pcms([tiny], sr=sr)) == 12
    c1 = np.full(int(0.40 * sr), 0.45, dtype=np.float32)
    c2 = np.full(int(0.40 * sr), -0.45, dtype=np.float32)
    xf = crossfade_clause_pcms([c1, c2], sr=sr, crossfade_sec=0.020)
    assert len(xf) == len(c1) + len(c2) - int(round(0.020 * sr))
    max_step = float(np.max(np.abs(np.diff(xf))))
    assert max_step < 0.01, f"Expected click-free raised-cosine crossfade (<0.01 step), got {max_step:.4f}"

    # 3. 0.000s immediate speech onset trim on expressive_25d_v8
    padded = np.concatenate([np.zeros(int(0.18 * sr), dtype=np.float32), 0.35 * np.sin(2.0 * math.pi * 180.0 * (np.arange(sr) / sr)).astype(np.float32)])
    trimmed_v8, _ = _trim_waveform_silences_and_breaths(padded, sr, lead_pad_sec=0.0)
    first_voiced_idx = int(np.argmax(np.abs(trimmed_v8) > 0.02))
    assert first_voiced_idx / float(sr) <= 0.015, f"Expected immediate 0.000s onset, got {first_voiced_idx / float(sr):.4f}s"

    # 4. Documentary ducked BGM (-21.5 dBFS under speech, lifts in breath gaps) & narrow/center-focused stereo
    dur_bgm_s = 16.0
    t_b = np.arange(int(dur_bgm_s * sr), dtype=np.float32) / float(sr)
    pcm_b = np.zeros_like(t_b)
    voiced_m = ((t_b >= 1.2) & (t_b < 4.5)) | ((t_b >= 6.0) & (t_b < 11.5))
    pcm_b[voiced_m] = (0.24 * np.sin(2.0 * math.pi * 170.0 * t_b[voiced_m])).astype(np.float32)
    edl_b = {"style_profile": "expressive_25d_v8", "cuts": []}
    wav_b = tmp_path / "rising_bgm_test.wav"
    generate_diorama_audio_master(wav_b, pcm_b, sr, 15.80, edl_b)
    with wave.open(str(wav_b), "rb") as wf:
        st_b = (np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0).reshape(-1, 2)
    early_gap_rms = 20.0 * math.log10(max(1e-7, float(np.sqrt(np.mean(np.square(st_b[int(0.10 * sr) : int(1.05 * sr)]))))))
    tail_gap_rms = 20.0 * math.log10(max(1e-7, float(np.sqrt(np.mean(np.square(st_b[int(12.20 * sr) : int(13.80 * sr)]))))))
    assert -28.0 <= early_gap_rms <= -14.0 and -28.0 <= tail_gap_rms <= -14.0
    assert abs(tail_gap_rms - early_gap_rms) <= 3.0, f"Expected steady non-siren documentary BGM, got {early_gap_rms:.2f} vs {tail_gap_rms:.2f}"
    lr_corr = float(np.corrcoef(st_b[:, 0], st_b[:, 1])[0, 1])
    assert 0.85 <= lr_corr < 0.9999, f"Expected center-focused yet decorrelated stereo BGM, got corr={lr_corr:.5f}"

    # 5. Daisy-chain 9:16 3D keyframes & cross-location safety
    sents = _sample_v8_sentences()
    raw_vp = _sample_v8_visual_plan(sents)
    raw_vp.pop("voice_preset", None)
    daisy_vp = populate_expressive_v8_reference_contract(raw_vp, daisy_chain_keyframes=True)
    assert daisy_vp["daisy_chain_keyframes"] is True
    end_bound = [c for c in daisy_vp["clips"] if c.get("end_reference_image")]
    assert len(end_bound) >= 7, f"Expected >=7 same-space daisy-chained Start+End cuts, got {len(end_bound)}"
    # Cross-location cut 4 (hotel_room_3am) -> cut 5 (brown_sleep_lab) must NOT bind cross-room end_reference_image
    assert not daisy_vp["clips"][3].get("end_reference_image")
    # Cameo cut 10 must NEVER bind cameo_opt3_sheet.png in end_reference_image
    assert not daisy_vp["clips"][9].get("end_reference_image")
    daisy_prompts = build_diorama_v7_prompts(daisy_vp, sents)
    assert validate_production_diorama_v6(
        daisy_vp,
        sents,
        daisy_prompts,
        script_doc={"opening_mode": "action", "core_reveal_sentence_index": 14, "foil_sentence_indices": [4]},
    ) == []


@pytest.mark.slow
def test_slow_v8_30fps_camera_bridges_spike_suppression(tmp_path: Path) -> None:
    sents = _sample_v8_sentences()
    sr = 48000
    # Native 30fps assembly + portal_crash_zoom_10f / whip_pan_blur_8f / dissolve_8f spike suppression
    p30 = tmp_path / "v8_30fps_cam_bridge_proj"
    for sub in ("02_script", "03_visuals/flow_native_clips", "04_audio", "05_assembly", "06_publish"):
        (p30 / sub).mkdir(parents=True, exist_ok=True)
    vp30 = _sample_v8_visual_plan(sents)
    vp30.pop("voice_preset", None)
    tr_cycle = ["portal_crash_zoom_10f", "whip_pan_blur_8f", "dissolve_8f", "daisy_chain_bridge"]
    for i_c, c_spec in enumerate(vp30["clips"]):
        c_spec["transition_to_next"] = "action_impact_cut" if i_c == 0 else tr_cycle[i_c % len(tr_cycle)]
        if i_c in (3, 7, 11):
            c_spec["end_reference_image"] = "03_visuals/reference_images/species_opt1_sheet.png"
    vp30 = populate_expressive_v8_reference_contract(vp30)
    sc30 = {
        "schema": 8,
        "style_profile": "expressive_25d_v8",
        "format_profile": "shorts_expressive_v8",
        "prosody_mode": "expressive_us_v8",
        "opening_mode": "action",
        "core_reveal_sentence_index": 14,
        "title": vp30["title"],
        "doi": vp30["doi"],
        "foil_sentence_indices": [4, 7, 12],
        "sentences": sents,
    }
    (p30 / "02_script" / "script.json").write_text(json.dumps(sc30, indent=2), encoding="utf-8")
    (p30 / "03_visuals" / "visual_plan.json").write_text(json.dumps(vp30, indent=2), encoding="utf-8")
    ensure_expressive_v8_reference_pack(p30)
    write_flow_prompts_json(p30, build_diorama_v7_prompts(vp30, sents))

    rng30 = np.random.default_rng(3030)
    grain30 = rng30.integers(-7, 8, size=(20, 480, 270, 3), dtype=np.int16)
    for idx in range(1, 21):
        frames30: list[np.ndarray] = []
        base_c = np.array([58 + (idx * 29) % 130, 82 + (idx * 37) % 120, 115 + (idx * 41) % 125], dtype=np.int16)
        for f_i in range(24 * 6):
            cv_im = np.clip(base_c + grain30[(f_i + idx) % 20], 20, 240).astype(np.uint8)
            cx = int(round(135.0 + 52.0 * math.sin(2.0 * math.pi * f_i / 96.0 + idx * 0.75)))
            cy = int(round(205.0 + 48.0 * math.cos(2.0 * math.pi * f_i / 120.0 + idx * 0.55)))
            cv2.circle(cv_im, (cx, cy), 38, (240, 240, 244), -1)
            cv2.circle(cv_im, (cx, cy), 38, (22, 22, 24), 3)
            frames30.append(cv_im)
        _write_test_mp4(p30 / "03_visuals" / "flow_native_clips" / f"clip_{idx}.mp4", frames30, fps=24)

    dur_cycle30 = [
        1.15, 2.25, 2.10, 2.35, 2.30, 2.20, 2.15, 4.00, 2.90, 3.60,
        2.60, 3.85, 2.75, 4.10, 3.75, 2.65, 3.70, 2.85, 3.90, 3.15,
    ]
    line_pcms30: list[np.ndarray] = []
    for idx_l, d_s in enumerate(dur_cycle30, start=1):
        t_l = np.arange(int(round(d_s * sr)), dtype=np.float32) / float(sr)
        f0_l = 132.0 if idx_l in (4, 7, 12) else 178.0
        env_l = 0.32 * (0.66 + 0.34 * np.sin(2.0 * math.pi * 3.5 * t_l))
        sig_l = (env_l * (0.65 * np.sin(2.0 * math.pi * f0_l * t_l) + 0.25 * np.sin(2.0 * math.pi * 2.0 * f0_l * t_l))).astype(np.float32)
        line_pcms30.append(sig_l)
    out30 = assemble_diorama_project(
        p30,
        force_rebuild=True,
        align_whisper=False,
        pre_synthesized_lines=line_pcms30,
        prosody_mode="expressive_us_v8",
        run_posthoc_qa=False,
    )
    edl30 = json.loads((p30 / "05_assembly" / "edit_decision_list.json").read_text(encoding="utf-8"))
    assert edl30["fps"] == 30
    assert edl30["edl_mode"] == "v8_expressive_dynamic_30fps"
    assert any(c.get("v8_curve_ramp") is True for c in edl30["cuts"])

    cap30 = cv2.VideoCapture(out30["final_mp4"])
    assert abs(float(cap30.get(cv2.CAP_PROP_FPS)) - 30.0) <= 0.25
    grays30: list[np.ndarray] = []
    while True:
        ok_f, frm_f = cap30.read()
        if not ok_f:
            break
        # Measure upper scene ROI (above Track-V2 MarginV=521 subtitle band)
        grays30.append(cv2.cvtColor(cv2.resize(frm_f[:1180, :], (135, 165)), cv2.COLOR_BGR2GRAY).astype(np.float32))
    cap30.release()
    assert abs(len(grays30) - int(edl30["total_frames"])) <= 2
    maes30 = [float(np.mean(np.abs(grays30[i] - grays30[i - 1]))) for i in range(1, len(grays30))]
    hard_spikes = 0
    for i_m, m_v in enumerate(maes30):
        win_m = [maes30[j] for j in range(max(0, i_m - 12), min(len(maes30), i_m + 13)) if abs(j - i_m) > 2]
        med_m = float(np.median(win_m)) if win_m else 1.0
        if m_v >= 18.0 and (m_v / max(0.5, med_m)) >= 8.0:
            hard_spikes += 1
    assert hard_spikes <= 1, f"Expected <=1 intentional action_impact_cut hard spike across 15 cut boundaries, got {hard_spikes}"


def test_v8_video_frames_start_end_uploader_and_packets_contract(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import asyncio
    import pipeline.flow_ingredients as fi_mod
    from pipeline.scene_blueprint import write_project_blueprint_and_packets

    start_png = tmp_path / "hotel_bed_eye_3am_9x16.png"
    end_png = tmp_path / "hotel_bed_overhead_9x16.png"
    missing_png = tmp_path / "does_not_exist.png"
    start_png.write_bytes(b"\x89PNG\r\n\x1a\nstart")
    end_png.write_bytes(b"\x89PNG\r\n\x1a\nend")

    calls: list[tuple[str, str]] = []
    chip_state = {"count": 0}

    async def _fake_set_mode(_client: Any, use_frames: bool = True) -> bool:
        calls.append(("mode", "VIDEO_FRAMES" if use_frames else "VIDEO_REFERENCES"))
        return True

    async def _fake_clear(_client: Any) -> bool:
        chip_state["count"] = 0
        calls.append(("clear", ""))
        return True

    async def _fake_attach_slot(
        _client: Any,
        slot_label: str,
        file_path: Path,
        uploaded_cache: set[str] | None = None,
    ) -> bool:
        if not Path(file_path).exists():
            return False
        calls.append((slot_label, Path(file_path).name))
        chip_state["count"] += 1
        if uploaded_cache is not None:
            uploaded_cache.add(Path(file_path).name)
        return True

    async def _fake_count_chips(_client: Any) -> int:
        return int(chip_state["count"])

    monkeypatch.setattr(fi_mod, "set_flow_video_input_mode", _fake_set_mode)
    monkeypatch.setattr(fi_mod, "clear_prompt_ingredients", _fake_clear)
    monkeypatch.setattr(fi_mod, "attach_frame_slot_by_name", _fake_attach_slot)
    monkeypatch.setattr(fi_mod, "count_chips", _fake_count_chips)

    # 1. Dual Start + End keyframe slot attachment in VIDEO_FRAMES mode
    res_dual = asyncio.run(fi_mod.upload_start_end_frames_to_flow(object(), start_png, end_png, use_frames_mode=True))
    assert res_dual == {
        "start_attached": True,
        "end_attached": True,
        "chip_count": 2,
        "input_mode": "VIDEO_FRAMES",
    }
    assert ("Start", start_png.name) in calls
    assert ("End", end_png.name) in calls

    # 2. Identical Start == End path must NOT attach duplicate End slot
    res_same = asyncio.run(fi_mod.upload_start_end_frames_to_flow(object(), start_png, start_png, use_frames_mode=True))
    assert res_same["start_attached"] is True
    assert res_same["end_attached"] is False
    assert res_same["chip_count"] == 1

    # 3. Missing Start path fails gracefully with 0 chips and skips End slot
    res_missing = asyncio.run(fi_mod.upload_start_end_frames_to_flow(object(), missing_png, end_png, use_frames_mode=True))
    assert res_missing == {
        "start_attached": False,
        "end_attached": False,
        "chip_count": 0,
        "input_mode": "VIDEO_FRAMES",
    }

    # 4. Schema v8 packets generation unpacks write_episode_qa_contract tuple cleanly
    pkt_proj = tmp_path / "v8_packets_proj"
    for sub in ("02_script", "03_visuals"):
        (pkt_proj / sub).mkdir(parents=True, exist_ok=True)
    sents = _sample_v8_sentences()
    vp = populate_expressive_v8_reference_contract(_sample_v8_visual_plan(sents), daisy_chain_keyframes=True)
    (pkt_proj / "02_script" / "script.json").write_text(json.dumps({"schema": 8, "sentences": sents}, indent=2), encoding="utf-8")
    (pkt_proj / "03_visuals" / "visual_plan.json").write_text(json.dumps(vp, indent=2), encoding="utf-8")
    dossier_dir = ROOT / "BCI_Shorts_Channel" / "research_dossiers" / "v2_sleep_first_night_hemisphere_watch"
    pkt_res = write_project_blueprint_and_packets(pkt_proj, dossier_dir=dossier_dir)
    assert pkt_res["packets"] == len(sents)
    assert pkt_res["qa_contract_clips"] == len(sents)
    assert pkt_res["blueprint_issues"] == []


def test_regression_reviewer_orphan_tab_reap_and_sharded_cleanup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import io
    import pipeline.cdp_tab_lease as lease_mod

    monkeypatch.setenv("AAB_LOCKS_DIR", str(tmp_path))

    closed_targets: list[str] = []

    class _FakeResp(io.BytesIO):
        def __enter__(self) -> "_FakeResp":
            return self

        def __exit__(self, *_a: Any) -> None:
            self.close()

    def _fake_urlopen(url: str, timeout: float = 3.0) -> _FakeResp:
        if "/json/list" in url:
            tabs = [
                {"id": "ORPHAN_DEAD_PID_TAB", "type": "page", "url": "https://flow.google.com/project/dead-room", "title": "Google Flow – AAB_v8_test"},
                {"id": "EXTRA_SHARD_TAB", "type": "page", "url": "https://flow.google.com/project/shard-room", "title": "Google Flow – AAB_v8_test"},
                {"id": "USER_PERSONAL_TAB", "type": "page", "url": "https://moodle.ucl.ac.uk/my/", "title": "UCL Moodle"},
                {"id": "USER_FLOW_TAB", "type": "page", "url": "https://flow.google.com/project/user-room", "title": "User Flow"},
            ]
            return _FakeResp(json.dumps(tabs).encode("utf-8"))
        if "/json/close/" in url:
            tid = url.rsplit("/", 1)[-1]
            closed_targets.append(tid)
            return _FakeResp(b"Target is closing")
        raise RuntimeError(f"Unexpected URL: {url}")

    monkeypatch.setattr(lease_mod.urllib.request, "urlopen", _fake_urlopen)

    reg = {
        "schema": 1,
        "leases": {
            "ORPHAN_DEAD_PID_TAB": {
                "target_id": "ORPHAN_DEAD_PID_TAB",
                "pid": 99999991,
                "pid_start_ticks": 12345,
                "cdp_port": 9222,
                "purpose": "flow_shard_v8_test",
                "url": "https://flow.google.com/project/dead-room",
                "created_by_pipeline": True,
                "acquired_at": 1000.0,
                "heartbeat_at": 1000.0,
            },
            "USER_FLOW_TAB": {
                "target_id": "USER_FLOW_TAB",
                "pid": 99999992,
                "pid_start_ticks": 12345,
                "cdp_port": 9222,
                "purpose": "adopt",
                "url": "https://flow.google.com/project/user-room",
                "created_by_pipeline": False,
                "acquired_at": 1000.0,
                "heartbeat_at": 1000.0,
            },
        },
        "orphan_pipeline_tabs": {},
    }
    lease_mod.get_cdp_leases_path().write_text(json.dumps(reg, indent=2), encoding="utf-8")

    reaped = lease_mod.reap_orphan_pipeline_tabs(
        cdp_port=9222,
        extra_pipeline_tab_ids=["EXTRA_SHARD_TAB", "USER_PERSONAL_TAB"],
        project_id="v8_test",
    )
    assert "ORPHAN_DEAD_PID_TAB" in reaped
    assert "EXTRA_SHARD_TAB" in reaped
    assert "USER_PERSONAL_TAB" not in reaped, "Must never close non-Flow personal user tabs even if passed in extra_pipeline_tab_ids"
    assert "USER_FLOW_TAB" not in reaped, "Must never close tabs where created_by_pipeline is False"
    assert set(closed_targets) == {"ORPHAN_DEAD_PID_TAB", "EXTRA_SHARD_TAB"}


def test_regression_reviewer_worker_zero_credit_veo_lite_before_teardown(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import asyncio
    import pipeline.flow_diorama_sharded_worker as worker_mod

    start_png = tmp_path / "start_9x16.png"
    end_png = tmp_path / "end_9x16.png"
    start_png.write_bytes(b"\x89PNG\r\n\x1a\nstart")
    end_png.write_bytes(b"\x89PNG\r\n\x1a\nend")

    state = {
        "family": "veo_3_1_fast",  # Simulate Flow defaulting back to paid model when VIDEO_FRAMES mode toggles
        "warn": True,
        "chips": 0,
        "submitted": False,
        "cleared_after_dual": 0,
    }

    class _FakeClient:
        async def eval(self, expr: str) -> Any:
            if "prompt-warning-button" in expr and "exhausted" in expr:
                return {"exhausted": state["warn"], "has_warning_btn": state["warn"]}
            if "Boolean(document.querySelector('button.prompt-warning-button'))" in expr:
                return state["warn"]
            if "cdk-overlay-pane" in expr:
                return False
            if "flow-generate-icon-button" in expr and "ProseMirror" in expr:
                return True
            if "ed.focus()" in expr and "InputEvent" not in expr:
                return True
            if "InputEvent" in expr:
                state["ed_len"] = 24
                return True
            if "listener_invoked" in expr:
                state["submitted"] = True
                state["ed_len"] = 0
                return {"action": "listener_invoked", "x": 100, "y": 100}
            if ".trim().length" in expr:
                return state.get("ed_len", 0)
            return None

        async def send(self, *_args: Any, **_kwargs: Any) -> dict[str, Any]:
            return {}

    async def _fake_sleep(_s: float) -> None:
        return None

    async def _fake_cfg_engine(_c: Any, **_kw: Any) -> dict[str, Any]:
        state["family"] = "veo_3_1_lite_low_priority"
        state["warn"] = False
        return {"flow_model": worker_mod.FLOW_ZERO_CREDIT_MODEL, "credit_tier": "zero_credit_fallback"}

    async def _fake_upload_start_end(_c: Any, start_frame: Path, end_frame: Path | None = None, **_kw: Any) -> dict[str, Any]:
        # Toggling VIDEO_FRAMES in live Flow resets dropdown to a paid model until _configure_zero_credit_veo_lite runs!
        state["chips"] = 2 if end_frame else 1
        state["family"] = "veo_3_1_fast"
        state["warn"] = True
        return {"start_attached": True, "end_attached": bool(end_frame), "chip_count": state["chips"], "input_mode": "VIDEO_FRAMES"}

    async def _fake_cfg_lite(_c: Any, **_kw: Any) -> bool:
        state["family"] = "veo_3_1_lite_low_priority"
        state["warn"] = False
        return True

    async def _fake_select_model(_c: Any, _m: str) -> bool:
        return True

    async def _fake_read_fam(_c: Any) -> str:
        return str(state["family"])

    async def _fake_count_chips(_c: Any) -> int:
        return int(state["chips"])

    async def _fake_clear(_c: Any) -> bool:
        if state["chips"] == 2:
            state["cleared_after_dual"] += 1
        state["chips"] = 0
        return True

    async def _noop_async(*_a: Any, **_kw: Any) -> bool:
        return True

    monkeypatch.setattr(worker_mod.asyncio, "sleep", _fake_sleep)
    monkeypatch.setattr(worker_mod, "_configure_diorama_tab_engine", _fake_cfg_engine)
    monkeypatch.setattr(worker_mod, "upload_start_end_frames_to_flow", _fake_upload_start_end)
    monkeypatch.setattr(worker_mod, "_configure_zero_credit_veo_lite", _fake_cfg_lite)
    monkeypatch.setattr(worker_mod, "select_flow_video_model", _fake_select_model)
    monkeypatch.setattr(worker_mod, "read_active_flow_model_family", _fake_read_fam)
    monkeypatch.setattr(worker_mod, "count_chips", _fake_count_chips)
    monkeypatch.setattr(worker_mod, "clear_prompt_ingredients", _fake_clear)
    monkeypatch.setattr(worker_mod, "enable_background_focus_emulation", _noop_async)
    monkeypatch.setattr(worker_mod, "set_flow_video_input_mode", _noop_async)
    monkeypatch.setattr(worker_mod, "press_escape", _noop_async)

    ref_state: dict[str, Any] = {"lite_supports_dual_ref": True}
    meta_out: dict[str, Any] = {}
    ok = asyncio.run(
        worker_mod._submit_diorama_prompt_zero_credit(
            _FakeClient(),
            "Smooth 3D camera push from Start keyframe to End keyframe.",
            short_ref_path=start_png,
            ref_state=ref_state,
            engine_mode="zero-credit",
            submission_meta_out=meta_out,
            end_ref_path=end_png,
        )
    )
    assert ok is True
    assert state["cleared_after_dual"] == 0, "Must configure 0-credit Veo Lite BEFORE tearing down dual Start+End VIDEO_FRAMES"
    assert ref_state["lite_supports_dual_ref"] is True
    assert meta_out["input_mode"] == "VIDEO_FRAMES"
    assert meta_out["end_reference_attached"] is True
    assert meta_out["attached_chip_count"] == 2


@pytest.mark.slow
def test_regression_reviewer_daisy_chain_exact_keyframe_handoff_vs_dissolve_fallback(tmp_path: Path) -> None:
    p_dir = tmp_path / "v8_daisy_handoff_proj"
    for sub in ("02_script", "03_visuals/flow_native_clips", "04_audio", "05_assembly"):
        (p_dir / sub).mkdir(parents=True, exist_ok=True)

    n_clips = 20
    sents = [f"Night watch line {i}!" if i == 1 else f"Night watch sentence {i}." for i in range(1, n_clips + 1)]
    clips_spec: list[dict[str, Any]] = []
    for i in range(1, n_clips + 1):
        clips_spec.append(
            {
                "clip_index": i,
                "sentence_index": i,
                "act": min(6, ((i - 1) // 4) + 1),
                "grammar": "expressive_vinyl_world",
                "location_id": "hotel_room",
                "transition_to_next": "daisy_chain_bridge" if i in (1, 2) else "dissolve_8f",
                "spoken_narration": sents[i - 1],
            }
        )
    vp = {
        "schema": 8,
        "style_profile": "expressive_25d_v8",
        "format_profile": "shorts_expressive_v8",
        "title": "Your Brain's 3 AM Night Watch",
        "doi": "10.1016/j.cub.2016.02.063",
        "clips": clips_spec,
    }
    (p_dir / "02_script" / "script.json").write_text(
        json.dumps({"schema": 8, "style_profile": "expressive_25d_v8", "format_profile": "shorts_expressive_v8", "sentences": sents}, indent=2),
        encoding="utf-8",
    )
    (p_dir / "03_visuals" / "visual_plan.json").write_text(json.dumps(vp, indent=2), encoding="utf-8")

    # Clip 1 ramps brightness 40 -> 150 (shared K_2 keyframe = 150)
    # Clip 2 starts at exact shared keyframe 150 -> 190 (so End(1) == Start(2), MAE ~ 0!)
    # Clip 3 starts at mismatched 45 -> 95 (so End(2)=190 != Start(3)=45, MAE > 100 -> must fallback to 8f dissolve!)
    n_f = 30 * 5
    f_c1: list[np.ndarray] = []
    f_c2: list[np.ndarray] = []
    f_c3: list[np.ndarray] = []
    for i in range(n_f):
        im1 = np.full((480, 270, 3), int(round(40 + 110 * (i / (n_f - 1)))), dtype=np.uint8)
        im2 = np.full((480, 270, 3), int(round(150 + 40 * (i / (n_f - 1)))), dtype=np.uint8)
        im3 = np.full((480, 270, 3), int(round(45 + 50 * (i / (n_f - 1)))), dtype=np.uint8)
        cx_m = int(round(135.0 + 36.0 * math.sin(2.0 * math.pi * i / 45.0)))
        cv2.circle(im1, (cx_m, 260), 26, (240, 240, 244), -1)
        cv2.circle(im2, (cx_m, 260), 26, (240, 240, 244), -1)
        cv2.circle(im3, (cx_m, 260), 26, (240, 240, 244), -1)
        f_c1.append(im1)
        f_c2.append(im2)
        f_c3.append(im3)
    _write_test_mp4(p_dir / "03_visuals" / "flow_native_clips" / "clip_1.mp4", f_c1, fps=30)
    _write_test_mp4(p_dir / "03_visuals" / "flow_native_clips" / "clip_2.mp4", f_c2, fps=30)
    for rest_i in range(3, n_clips + 1):
        _write_test_mp4(p_dir / "03_visuals" / "flow_native_clips" / f"clip_{rest_i}.mp4", f_c3, fps=30)

    sr = 48000
    t_sp = np.arange(int(2.90 * sr), dtype=np.float32) / float(sr)
    env_sp = 0.32 * (0.66 + 0.34 * np.sin(2.0 * math.pi * 3.5 * t_sp))
    sig_sp = (env_sp * (0.65 * np.sin(2.0 * math.pi * 178.0 * t_sp) + 0.25 * np.sin(2.0 * math.pi * 356.0 * t_sp))).astype(np.float32)
    line_pcms = [sig_sp.copy() for _ in range(n_clips)]
    asm = assemble_diorama_project(
        p_dir,
        force_rebuild=True,
        align_whisper=False,
        pre_synthesized_lines=line_pcms,
        prosody_mode="expressive_us_v8",
        run_posthoc_qa=False,
    )
    edl = json.loads((p_dir / "05_assembly" / "edit_decision_list.json").read_text(encoding="utf-8"))
    cut1_end_f = int(round(float(edl["cuts"][0]["out_end_sec"]) * 30))
    cut2_end_f = int(round(float(edl["cuts"][1]["out_end_sec"]) * 30))

    cap = cv2.VideoCapture(asm["final_mp4"])
    upper_means: list[float] = []
    while True:
        ok_r, frm = cap.read()
        if not ok_r:
            break
        upper_means.append(float(np.mean(frm[:400, :])))
    cap.release()

    # Boundary 1->2 (matched keyframe): step across cut1_end_f-1 -> cut1_end_f is near-zero (<5 gray levels, exact handoff!)
    step_1_2 = abs(upper_means[cut1_end_f] - upper_means[cut1_end_f - 1])
    assert step_1_2 < 5.0, f"Expected seamless keyframe handoff at Cut 1->2 (<5.0 gray step), got {step_1_2:.2f}"

    # Boundary 2->3 (mismatched keyframe): fallback 8-frame dissolve spreads the 145-level jump smoothly (<35 per frame, not a 145 hard jump!)
    window_steps_2_3 = [
        abs(upper_means[k] - upper_means[k - 1])
        for k in range(max(1, cut2_end_f - 3), min(len(upper_means), cut2_end_f + 10))
    ]
    assert max(window_steps_2_3) < 35.0, f"Expected 8f dissolve fallback on mismatched daisy_chain_bridge (<35/frame), got {max(window_steps_2_3):.2f}"


def test_regression_reviewer_yunet_capped_human_face_and_kokoro_v8_native_gears(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from pipeline.source_reenactment import detect_human_faces_yunet
    import pipeline.voice_fallback as vf_mod

    # 1. White-surgical-cap human faces (pale, caucasian, olive, cool-lit) MUST be caught even under allow_expressive_2d_ink=True
    master_png = ROOT / "BCI_Shorts_Channel" / "reference_style_anchors" / "expressive_25d_v8_refs" / "expressive_conflict_master.png"
    img = cv2.imread(str(master_png))
    assert img is not None
    assert detect_non_porcelain_human_faces_yunet(img, allow_expressive_2d_ink=True) == []
    boxes = detect_human_faces_yunet(img)
    assert len(boxes) >= 1

    for skin_name, skin_bgr in (
        ("pale_human_white_cap", [175, 192, 224]),
        ("caucasian_white_cap", [132, 156, 202]),
        ("olive_white_cap", [112, 148, 192]),
        ("cool_lit_white_cap", [195, 155, 130]),
    ):
        capped = img.copy()
        for bx, by, bw, bh, _ in boxes:
            # Keep top 38% pure matte-white surgical/EEG cap; tint only lower 62% as flesh skin!
            y_split = max(0, by + int(bh * 0.38))
            roi = capped[y_split : by + bh, max(0, bx) : bx + bw].astype(np.float32)
            lum = cv2.cvtColor(roi.astype(np.uint8), cv2.COLOR_BGR2GRAY).astype(np.float32) / 240.0
            non_ink = lum >= 0.30
            for ch_i in range(3):
                roi[:, :, ch_i][non_ink] = np.clip(lum[non_ink] * skin_bgr[ch_i], 0, 255)
            capped[y_split : by + bh, max(0, bx) : bx + bw] = roi.astype(np.uint8)
        dets_cap = detect_non_porcelain_human_faces_yunet(capped, allow_expressive_2d_ink=True)
        assert len(dets_cap) >= 1, f"Expected YuNet to flag {skin_name}, got {dets_cap}"

    # 2. Offline test stub on expressive_25d_v8 synthesizes per-gear speeds natively (wsola_factor == 1.0)
    stub_calls: list[tuple[str, float]] = []

    def _fake_stub_pcm(
        text: str,
        sr: int = 48000,
        target_tempo: float = 1.0,
        seed_idx: int = 1,
    ) -> np.ndarray:
        norm = vf_mod.to_expressive_tts_text(text)
        stub_calls.append((norm, float(target_tempo)))
        t = np.arange(int(3.8 * sr), dtype=np.float32) / float(sr)
        return (0.30 * np.sin(2.0 * math.pi * 175.0 * t)).astype(np.float32)

    monkeypatch.setattr(vf_mod, "_synthesize_test_stub_pcm", _fake_stub_pcm)

    kokoro_proj = tmp_path / "kokoro_v8_proj"
    for sub in ("03_visuals", "04_audio"):
        (kokoro_proj / sub).mkdir(parents=True, exist_ok=True)
    (kokoro_proj / "03_visuals" / "visual_plan.json").write_text(
        json.dumps({"style_profile": "expressive_25d_v8", "format_profile": "shorts_expressive_v8"}, indent=2),
        encoding="utf-8",
    )
    sents_k = [
        "Three in the morning in a strange hotel bed!",
        "Yet why did one half of the brain stay wide awake?",
    ] + [f"Sentence number {k} continues the story." for k in range(3, 17)]
    res_k = vf_mod.synthesize_continuous_diorama_track(
        kokoro_proj,
        sents_k,
        align_whisper=False,
        script_doc={"style_profile": "expressive_25d_v8", "format_profile": "shorts_expressive_v8"},
        prosody_mode="expressive_us_v8",
        allow_test_stub=True,
    )
    assert res_k["report"]["engine"] == "test_stub"
    pros_rep_k = json.loads((kokoro_proj / "04_audio" / "prosody_report.json").read_text(encoding="utf-8"))
    assert pros_rep_k["native_gear_synthesis"] is True
    assert stub_calls[0][0].endswith("!"), f"Expected '!' preserved in v8 text, got {stub_calls[0][0]!r}"
    assert len({spd for _, spd in stub_calls}) >= 2, f"Expected distinct per-gear tempos, got {stub_calls[:4]}"
    assert all(abs(float(t["wsola_factor"]) - 1.0) < 1e-6 for t in pros_rep_k["sentences"])


def test_regression_reviewer_kb_sync_preserves_archived_packs_and_offloaded_episodes(tmp_path: Path) -> None:
    from pipeline.asset_manifest import build_asset_manifest
    from pipeline.knowledge_hub import sync_all_projects_to_knowledge_base

    projects_root = tmp_path / "projects"
    kb_dir = tmp_path / "knowledge_base"
    packs_dir = kb_dir / "reusable_packs"
    tel_dir = kb_dir / "telemetry"
    packs_dir.mkdir(parents=True, exist_ok=True)
    tel_dir.mkdir(parents=True, exist_ok=True)

    # Seed historical off-disk entries in telemetry/episodes_index.jsonl and reusable_packs/*.json
    prior_ep = {"project_id": "diorama_01_offdisk", "archived_off_disk": True, "style_profile": "porcelain_cinematic_v7"}
    (tel_dir / "episodes_index.jsonl").write_text(json.dumps(prior_ep) + "\n", encoding="utf-8")
    (packs_dir / "brain_models_registry.json").write_text(
        json.dumps({"count": 1, "brain_models": [{"project_id": "diorama_01_offdisk", "clip_index": 3, "grammar": "porcelain_living_brain"}]}, indent=2),
        encoding="utf-8",
    )

    # Create an on-disk archived episode whose .mp4 was offloaded (only posthoc_semantic_qa_report.json remains) + a v8 episode
    arch_p = projects_root / "diorama_08_archived_on_disk"
    for sub in ("02_script", "03_visuals", "05_assembly"):
        (arch_p / sub).mkdir(parents=True, exist_ok=True)
    (arch_p / "02_script" / "script.json").write_text(json.dumps({"title": "Archived Ep", "sentences": ["Line one."]}, indent=2), encoding="utf-8")
    (arch_p / "03_visuals" / "visual_plan.json").write_text(
        json.dumps(
            {
                "style_profile": "porcelain_cinematic_v7",
                "clips": [{"clip_number": 1, "act": 1, "grammar": "porcelain_living_brain", "brain_region": "thalamus", "location_id": "sleep_lab"}],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (arch_p / "03_visuals" / "flow_all_in_one_prompts.json").write_text(
        json.dumps({"clips": [{"clip_number": 1, "grammar": "porcelain_living_brain", "prompt": "Porcelain cutaway."}]}, indent=2),
        encoding="utf-8",
    )
    (arch_p / "03_visuals" / "flow_prompts.json").write_text(
        json.dumps([{"index": 1, "grammar": "porcelain_living_brain", "prompt": "Porcelain cutaway."}], indent=2),
        encoding="utf-8",
    )
    (arch_p / "05_assembly" / "posthoc_semantic_qa_report.json").write_text(
        json.dumps(
            {
                "passed": True,
                "clip_coverage_pct": 100.0,
                "cuts": [{"cut_index": 1, "clip_index": 1, "act": 1, "grammar": "porcelain_living_brain", "passed": True, "clarity_score": 97.2}],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    # Seed prior asset_manifest.json with clip SHA-256 before offload
    (arch_p / "05_assembly" / "asset_manifest.json").write_text(
        json.dumps({"assets": [{"clip_number": 1, "sha256": "deadbeef" * 8}]}, indent=2),
        encoding="utf-8",
    )
    rebuilt_manifest = build_asset_manifest(arch_p, write_library=False)
    assert len(rebuilt_manifest["assets"]) == 1 and rebuilt_manifest["assets"][0]["sha256"] == "deadbeef" * 8

    # Create a live expressive_25d_v8 project with expressive_xray_brain
    v8_p = projects_root / "v8_test_ep"
    for sub in ("02_script", "03_visuals", "05_assembly"):
        (v8_p / sub).mkdir(parents=True, exist_ok=True)
    (v8_p / "02_script" / "script.json").write_text(json.dumps({"title": "V8 Ep", "sentences": ["Night watch!"]}, indent=2), encoding="utf-8")
    (v8_p / "03_visuals" / "visual_plan.json").write_text(
        json.dumps(
            {
                "style_profile": "expressive_25d_v8",
                "clips": [{"clip_number": 1, "act": 3, "grammar": "expressive_xray_brain", "brain_region": "left hemisphere", "location_id": "hotel_3am"}],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (v8_p / "03_visuals" / "flow_all_in_one_prompts.json").write_text(
        json.dumps({"clips": [{"clip_number": 1, "grammar": "expressive_xray_brain", "prompt": "Crystal X-Ray brain."}]}, indent=2),
        encoding="utf-8",
    )
    (v8_p / "03_visuals" / "flow_prompts.json").write_text(
        json.dumps([{"index": 1, "grammar": "expressive_xray_brain", "prompt": "Crystal X-Ray brain."}], indent=2),
        encoding="utf-8",
    )
    (v8_p / "05_assembly" / "final_shorts_1080x1920.mp4").write_bytes(b"mp4bytes")
    (v8_p / "05_assembly" / "posthoc_semantic_qa_report.json").write_text(
        json.dumps(
            {
                "passed": True,
                "clip_coverage_pct": 100.0,
                "cuts": [{"cut_index": 1, "clip_index": 1, "act": 3, "grammar": "expressive_xray_brain", "passed": True, "clarity_score": 96.4}],
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    stats = sync_all_projects_to_knowledge_base(projects_dir=projects_root, kb_dir=kb_dir, run_missing_posthoc=False)
    assert stats["analytics"]["episodes_indexed"] == 3  # off-disk + archived-on-disk + live-v8
    brains = json.loads((packs_dir / "brain_models_registry.json").read_text(encoding="utf-8"))["brain_models"]
    brain_pids = {b["project_id"] for b in brains}
    assert {"diorama_01_offdisk", "diorama_08_archived_on_disk", "v8_test_ep"}.issubset(brain_pids)


def test_fast_v8_raw_cut_cache_reuse_and_recut(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from pipeline.diorama_assembler import recut_diorama_cuts
    from pipeline.media_integrity import MediaIntegrityValidator

    monkeypatch.setattr(cfg, "EXPRESSIVE_V8_CLIP_COUNT_RANGE", (4, 26))
    orig_val = MediaIntegrityValidator.validate_video_asset
    monkeypatch.setattr(
        MediaIntegrityValidator,
        "validate_video_asset",
        staticmethod(
            lambda path, asset_type="final_shorts", strict=True, **_kw: orig_val(
                path,
                asset_type=asset_type,
                strict=strict,
                min_size_bytes=10_000,
                min_duration_sec=2.0,
                max_duration_sec=25.0,
                check_motion=False,
                check_audio=False,
            )
        ),
    )

    p_dir = tmp_path / "v8_fast_cache_proj"
    for sub in ("02_script", "03_visuals/flow_native_clips", "04_audio", "05_assembly", "06_publish"):
        (p_dir / sub).mkdir(parents=True, exist_ok=True)
    sents = [
        "Three AM in a dark hotel room!",
        "Yet one half of your brain stays awake.",
        "Wait, why does it scan every sound?",
        "Your night watch never clocks out.",
    ]
    trs = ["portal_crash_zoom_10f", "whip_pan_blur_8f", "dissolve_8f", "none"]
    clips_spec = [
        {
            "clip_index": i,
            "sentence_index": i,
            "act": i,
            "grammar": "expressive_vinyl_world",
            "location_id": "hotel_3am",
            "transition_to_next": trs[i - 1],
            "spoken_narration": sents[i - 1],
        }
        for i in range(1, 5)
    ]
    vp = {
        "schema": 8,
        "style_profile": "expressive_25d_v8",
        "format_profile": "shorts_expressive_v8",
        "title": "Your Brain's 3 AM Watch",
        "doi": "10.1016/j.cub.2016.02.063",
        "clips": clips_spec,
    }
    (p_dir / "02_script" / "script.json").write_text(
        json.dumps({"schema": 8, "style_profile": "expressive_25d_v8", "format_profile": "shorts_expressive_v8", "sentences": sents}, indent=2),
        encoding="utf-8",
    )
    (p_dir / "03_visuals" / "visual_plan.json").write_text(json.dumps(vp, indent=2), encoding="utf-8")

    for idx in range(1, 5):
        frames = []
        for f_i in range(48):  # 2.0s @ 24fps
            im = np.full((320, 180, 3), 45 + idx * 25, dtype=np.uint8)
            cv2.circle(im, (90 + (f_i % 25), 150), 22, (240, 240, 244), -1)
            frames.append(im)
        _write_test_mp4(p_dir / "03_visuals" / "flow_native_clips" / f"clip_{idx}.mp4", frames, fps=24)

    sr = 48000
    t = np.arange(int(1.15 * sr), dtype=np.float32) / float(sr)
    sig = (0.28 * np.sin(2.0 * math.pi * 180.0 * t)).astype(np.float32)
    out1 = assemble_diorama_project(
        p_dir,
        force_rebuild=True,
        align_whisper=False,
        pre_synthesized_lines=[sig.copy() for _ in range(4)],
        prosody_mode="expressive_us_v8",
        run_posthoc_qa=False,
    )
    assert out1["raw_segment_cache_misses"] == 4
    assert out1["raw_segment_cache_hits"] == 0
    final_mp4_1 = p_dir / "05_assembly" / "final_shorts_1080x1920.mp4"
    cap1 = cv2.VideoCapture(str(final_mp4_1))
    try:
        fps1 = float(cap1.get(cv2.CAP_PROP_FPS) or 30.0)
        vframes1 = int(cap1.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    finally:
        cap1.release()
    vid_dur_1 = vframes1 / max(1.0, fps1)
    assert abs(vid_dur_1 - float(out1["duration_sec"])) <= 0.15, (
        f"C1 regression: video duration {vid_dur_1:.3f}s != container/audio duration {out1['duration_sec']:.3f}s"
    )

    # Replace ONLY clip_2.mp4 -> Cuts 1, 3, 4 must hit raw_v8 cache (3 hits, 1 miss)!
    frames_new = []
    for f_i in range(48):
        im = np.full((320, 180, 3), 185, dtype=np.uint8)
        cv2.rectangle(im, (40 + (f_i % 20), 110), (130, 200), (30, 30, 35), -1)
        frames_new.append(im)
    _write_test_mp4(p_dir / "03_visuals" / "flow_native_clips" / "clip_2.mp4", frames_new, fps=24)

    out2 = recut_diorama_cuts(p_dir, [2])
    assert out2["recut_cuts"] == [2]
    assert out2["raw_segment_cache_hits"] == 3
    assert out2["raw_segment_cache_misses"] == 1
    cap2 = cv2.VideoCapture(str(final_mp4_1))
    try:
        fps2 = float(cap2.get(cv2.CAP_PROP_FPS) or 30.0)
        vframes2 = int(cap2.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    finally:
        cap2.release()
    vid_dur_2 = vframes2 / max(1.0, fps2)
    assert abs(vid_dur_2 - float(out2["duration_sec"])) <= 0.15, (
        f"C1 regression after recut: video duration {vid_dur_2:.3f}s != container/audio duration {out2['duration_sec']:.3f}s"
    )


def test_fast_pre_assembly_audio_prosody_gate_catches_word_drop(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import pipeline.prosody as pros_mod
    import pipeline.voice_fallback as vf_mod
    from pipeline.media_integrity import MediaIntegrityValidator

    monkeypatch.setattr(cfg, "EXPRESSIVE_V8_CLIP_COUNT_RANGE", (4, 26))
    orig_val = MediaIntegrityValidator.validate_video_asset
    monkeypatch.setattr(
        MediaIntegrityValidator,
        "validate_video_asset",
        staticmethod(
            lambda path, asset_type="final_shorts", strict=True, **_kw: orig_val(
                path,
                asset_type=asset_type,
                strict=strict,
                min_size_bytes=10_000,
                min_duration_sec=2.0,
                max_duration_sec=25.0,
                check_motion=False,
                check_audio=False,
            )
        ),
    )

    p_dir = tmp_path / "v8_pre_audio_gate_proj"
    for sub in ("02_script", "03_visuals/flow_native_clips", "04_audio", "05_assembly", "06_publish"):
        (p_dir / sub).mkdir(parents=True, exist_ok=True)
    sents = [
        "Three AM in a dark hotel room!",
        "That hemisphere was standing night watch.",
        "Wait, why did it scan every sound?",
        "Your night watch never clocks out.",
    ]
    vp = {
        "schema": 8,
        "style_profile": "expressive_25d_v8",
        "format_profile": "shorts_expressive_v8",
        "title": "Your Brain's 3 AM Watch",
        "doi": "10.1016/j.cub.2016.02.063",
        "clips": [
            {"clip_index": i, "sentence_index": i, "act": i, "grammar": "expressive_vinyl_world", "transition_to_next": "dissolve_8f", "spoken_narration": sents[i - 1]}
            for i in range(1, 5)
        ],
    }
    (p_dir / "02_script" / "script.json").write_text(
        json.dumps({"schema": 8, "style_profile": "expressive_25d_v8", "format_profile": "shorts_expressive_v8", "sentences": sents}, indent=2),
        encoding="utf-8",
    )
    (p_dir / "03_visuals" / "visual_plan.json").write_text(json.dumps(vp, indent=2), encoding="utf-8")
    for idx in range(1, 5):
        frames = [np.full((320, 180, 3), 60 + idx * 20, dtype=np.uint8) for _ in range(48)]
        _write_test_mp4(p_dir / "03_visuals" / "flow_native_clips" / f"clip_{idx}.mp4", frames, fps=24)

    sr = 48000
    t = np.arange(int(1.15 * sr), dtype=np.float32) / float(sr)
    sig = (0.28 * np.sin(2.0 * math.pi * 185.0 * t)).astype(np.float32)
    retried_clip_nos: list[int] = []

    def _fake_stub_retry(text: str, seed_idx: int = 0, **_kw: Any) -> np.ndarray:
        retried_clip_nos.append(int(seed_idx))
        return sig.copy()

    monkeypatch.setattr(vf_mod, "_synthesize_test_stub_pcm", _fake_stub_retry)
    gate_calls = {"n": 0}

    def _fake_eval_prosody(_p_dir: Path, **_kw: Any) -> dict[str, Any]:
        gate_calls["n"] += 1
        if gate_calls["n"] == 1:
            return {"passed": False, "gates": {"P6_asr_by_gear": {"passed": False, "low_sentences_lt_0_80": [2]}}}
        return {"passed": True, "gates": {"P6_asr_by_gear": {"passed": True, "low_sentences_lt_0_80": []}}}

    monkeypatch.setattr(pros_mod, "evaluate_prosody_gates_on_audio", _fake_eval_prosody)
    out = assemble_diorama_project(
        p_dir,
        force_rebuild=True,
        align_whisper=True,
        pre_synthesized_lines=[sig.copy() for _ in range(4)],
        prosody_mode="expressive_us_v8",
        run_posthoc_qa=False,
    )
    assert out["pre_assembly_prosody_retried_sentences"] == [2]
    assert retried_clip_nos == [2]


def test_fast_zero_credit_governor_and_strict_video_frames_no_downgrade(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import asyncio
    import pipeline.flow_diorama_sharded_worker as fw_mod
    import pipeline.flow_ingredients as fi_mod
    from pipeline.source_reenactment import extract_dq8_scene_roi

    # 1. Safe anti-cooldown batch plan caps 0-credit concurrency to 2 tabs x x1 output
    assert fw_mod.compute_zero_credit_batch_plan(18, 5, anti_cooldown_safe=True) == (2, 1)
    assert fw_mod.compute_zero_credit_batch_plan(2, 5, anti_cooldown_safe=True) == (1, 1)

    # 2. Governor steps 2 -> 1 on 'unusual activity' penalty and recovers 1 -> 2 after 3 clean renders
    gov = fw_mod.ZeroCreditCooldownGovernor(initial_slot_cap=2, jitter_range_sec=(0.0, 0.0), penalty_quiet_sec=75.0, recovery_streak=3, rng_seed=7)
    assert gov.active_slot_cap == 2
    pause_1 = gov.record_penalty(now_mono=100.0)
    assert pause_1 == 75.0 and gov.active_slot_cap == 1
    gov.record_clean_render()
    gov.record_clean_render()
    assert gov.active_slot_cap == 1
    gov.record_clean_render()
    assert gov.active_slot_cap == 2 and gov.cooldown_hits == 0

    # 3. Strict Fail-Closed VIDEO_FRAMES: never downgrades to single-chip VIDEO_REFERENCES when end_ref_path is set
    start_p = tmp_path / "start.png"
    end_p = tmp_path / "end.png"
    cv2.imwrite(str(start_p), np.full((160, 90, 3), 210, dtype=np.uint8))
    cv2.imwrite(str(end_p), np.full((160, 90, 3), 180, dtype=np.uint8))

    class _FakeClient:
        async def eval(self, js: str) -> Any:
            if "generating will use 0 credits" in js.lower() or "veo 3.1" in js.lower():
                return {"credit_banner": False, "zero_credit": True}
            return {}

        async def send(self, *_a: Any, **_kw: Any) -> dict[str, Any]:
            return {}

    async def _fake_cfg_engine(_c: Any, **_kw: Any) -> dict[str, Any]:
        return {"flow_model": fw_mod.FLOW_ZERO_CREDIT_MODEL, "credit_tier": "zero_credit_fallback"}

    async def _fake_upload_fail(*_a: Any, **_kw: Any) -> dict[str, Any]:
        return {"start_attached": True, "end_attached": False, "chip_count": 1, "input_mode": "VIDEO_REFERENCES"}

    async def _noop_async(*_a: Any, **_kw: Any) -> Any:
        return True

    orig_sleep = asyncio.sleep

    async def _fast_sleep(_s: float, result: Any = None) -> Any:
        return await orig_sleep(0, result=result)

    monkeypatch.setattr(fw_mod.asyncio, "sleep", _fast_sleep)
    monkeypatch.setattr(fw_mod, "_configure_diorama_tab_engine", _fake_cfg_engine)
    monkeypatch.setattr(fw_mod, "upload_start_end_frames_to_flow", _fake_upload_fail)
    monkeypatch.setattr(fw_mod, "_configure_zero_credit_veo_lite", _noop_async)
    monkeypatch.setattr(fw_mod, "select_flow_video_model", _noop_async)
    monkeypatch.setattr(fw_mod, "read_active_flow_model_family", lambda _c: asyncio.sleep(0, result="veo_3_1_lite_low_priority"))
    monkeypatch.setattr(fw_mod, "count_chips", lambda _c: asyncio.sleep(0, result=1))
    monkeypatch.setattr(fw_mod, "read_active_flow_input_mode", lambda _c: asyncio.sleep(0, result="VIDEO_REFERENCES"))
    monkeypatch.setattr(fw_mod, "clear_prompt_ingredients", _noop_async)
    monkeypatch.setattr(fw_mod, "enable_background_focus_emulation", _noop_async)
    monkeypatch.setattr(fw_mod, "set_flow_video_input_mode", _noop_async)
    monkeypatch.setattr(fw_mod, "press_escape", _noop_async)

    ref_state: dict[str, Any] = {}
    sub_meta: dict[str, Any] = {}
    ok = asyncio.run(
        fw_mod._submit_diorama_prompt_zero_credit(
            _FakeClient(),
            "Smooth 2.5D vinyl room scene.",
            start_p,
            ref_state,
            engine_mode="zero-credit",
            submission_meta_out=sub_meta,
            end_ref_path=end_p,
            end_ref_is_secondary_ingredient=False,
        )
    )
    assert ok is False
    assert ref_state.get("lite_supports_dual_ref", True) is not False

    # 4. DQ8 ROI parity between 720p Flow clip and 1080p assembled frame
    frm_720 = np.zeros((1280, 720, 3), dtype=np.uint8)
    roi_from_720 = extract_dq8_scene_roi(frm_720, is_expressive_v8=True)
    frm_1080 = np.zeros((1920, 1080, 3), dtype=np.uint8)
    roi_from_1080 = extract_dq8_scene_roi(frm_1080, is_expressive_v8=True)
    assert roi_from_720.shape == roi_from_1080.shape == (int(1920 * 0.94), int(1080 * 0.98) - int(1080 * 0.02), 3)


def test_fast_incremental_kb_sync_skips_unchanged_projects(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import pipeline.knowledge_hub as kh_mod

    projects_root = tmp_path / "projects"
    kb_dir = tmp_path / "knowledge_base"
    ep = projects_root / "v8_inc_ep"
    for sub in ("02_script", "03_visuals", "05_assembly"):
        (ep / sub).mkdir(parents=True, exist_ok=True)
    (ep / "02_script" / "script.json").write_text(json.dumps({"title": "Inc Ep", "sentences": ["Watch!"]}, indent=2), encoding="utf-8")
    (ep / "03_visuals" / "visual_plan.json").write_text(
        json.dumps({"style_profile": "expressive_25d_v8", "clips": [{"clip_number": 1, "act": 1, "grammar": "expressive_vinyl_world"}]}, indent=2),
        encoding="utf-8",
    )
    (ep / "03_visuals" / "flow_all_in_one_prompts.json").write_text(
        json.dumps({"clips": [{"clip_number": 1, "grammar": "expressive_vinyl_world", "prompt": "Vinyl room."}]}, indent=2),
        encoding="utf-8",
    )
    (ep / "05_assembly" / "final_shorts_1080x1920.mp4").write_bytes(b"mp4data")
    (ep / "05_assembly" / "posthoc_semantic_qa_report.json").write_text(
        json.dumps({"passed": True, "cuts": [{"cut_index": 1, "clip_index": 1, "act": 1, "grammar": "expressive_vinyl_world", "passed": True, "clarity_score": 97.0}]}, indent=2),
        encoding="utf-8",
    )

    s1 = kh_mod.sync_all_projects_to_knowledge_base(projects_dir=projects_root, kb_dir=kb_dir)
    assert s1["newly_synced_projects"] == ["v8_inc_ep"]
    assert s1["unchanged_cached_projects"] == []

    sync_calls: list[str] = []
    orig_sync_one = kh_mod.sync_project_to_knowledge_base

    def _spy_sync_one(p_arg: Any, *args: Any, **kwargs: Any) -> dict[str, Any]:
        sync_calls.append(Path(p_arg).name)
        return orig_sync_one(p_arg, *args, **kwargs)

    monkeypatch.setattr(kh_mod, "sync_project_to_knowledge_base", _spy_sync_one)
    s2 = kh_mod.sync_all_projects_to_knowledge_base(projects_dir=projects_root, kb_dir=kb_dir)
    assert s2["newly_synced_projects"] == []
    assert s2["unchanged_cached_projects"] == ["v8_inc_ep"]
    assert sync_calls == []

    s3 = kh_mod.sync_all_projects_to_knowledge_base(projects_dir=projects_root, kb_dir=kb_dir, full_rescan=True)
    assert s3["newly_synced_projects"] == ["v8_inc_ep"]
    assert sync_calls == ["v8_inc_ep"]


def test_v8_single_narrator_emma_default_dq13_hygiene_and_posthoc_spoken_provenance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from pipeline.posthoc_semantic_qa import extract_cut_intent_specs, render_posthoc_viewer_strips
    from pipeline.prompt_quality_v5 import validate_script_spine_v8

    sents = _sample_v8_sentences()

    # 1. Foil-free single-narrator v8 script passes validate_script_spine_v8 when EXPRESSIVE_V8_REQUIRE_FOIL is False
    assert cfg.EXPRESSIVE_V8_VOICE_PRESET == "elevenlabs_v4"
    assert cfg.EXPRESSIVE_V8_FOIL_SENTENCE_RANGE == (0, 0)
    assert cfg.EXPRESSIVE_V8_REQUIRE_FOIL is False
    assert cfg.EXPRESSIVE_V8_BGM_START_DBFS == -25.0
    assert cfg.EXPRESSIVE_V8_BGM_PEAK_DBFS == -18.0
    assert cfg.EXPRESSIVE_V8_BGM_TAIL_DBFS == -18.0
    assert validate_script_spine_v8(sents, script_doc={"opening_mode": "action", "core_reveal_sentence_index": 14, "foil_sentence_indices": []}) == []

    # Invalid speaker role / length mismatch still rejected even when foil is optional
    bad_role_issues = validate_script_spine_v8(
        sents,
        script_doc={"opening_mode": "action", "sentence_speakers": ["narrator"] * (len(sents) - 1) + ["alien"]},
    )
    assert any("invalid speaker role" in x for x in bad_role_issues)
    bad_len_issues = validate_script_spine_v8(
        sents,
        script_doc={"opening_mode": "action", "sentence_speakers": ["narrator", "narrator"]},
    )
    assert any("length" in x for x in bad_len_issues)

    # Enabling EXPRESSIVE_V8_REQUIRE_FOIL enforces >=1 character/foil sentence
    monkeypatch.setattr(cfg, "EXPRESSIVE_V8_REQUIRE_FOIL", True)
    req_issues = validate_script_spine_v8(sents, script_doc={"opening_mode": "action", "foil_sentence_indices": []})
    assert any("multi-role dialogue requires >= 1" in x for x in req_issues)
    monkeypatch.setattr(cfg, "EXPRESSIVE_V8_REQUIRE_FOIL", False)

    # 2. Daisy-chain transition auto-population respects EXPRESSIVE_V8_MAX_STYLED_TRANSITIONS <= 4
    vp_raw = _sample_v8_visual_plan(sents)
    for c_it in vp_raw["clips"]:
        c_it.pop("transition_to_next", None)
    vp_hyg = populate_expressive_v8_reference_contract(vp_raw, daisy_chain_keyframes=True)
    styled_set = {
        "dissolve_6f",
        "dissolve_8f",
        "portal_crash_zoom_10f",
        "whip_pan_blur_8f",
        "occlusion_wipe",
        "split_screen_wipe",
        "match_cut_bridge",
    }
    styled_cnt = sum(1 for c_it in vp_hyg["clips"][:-1] if c_it.get("transition_to_next") in styled_set)
    assert styled_cnt <= cfg.EXPRESSIVE_V8_MAX_STYLED_TRANSITIONS

    # 3. Post-hoc QA prefers synthesized voice_report.json sentence_spans over stale script.json & stamps MP4 SHA
    ep_dir = tmp_path / "v8_posthoc_prov_ep"
    for sub in ("02_script", "03_visuals", "04_audio", "05_assembly"):
        (ep_dir / sub).mkdir(parents=True, exist_ok=True)
    (ep_dir / "02_script" / "script.json").write_text(
        json.dumps({"schema": 8, "style_profile": "expressive_25d_v8", "sentences": ["Stale whale line."]}, indent=2),
        encoding="utf-8",
    )
    (ep_dir / "03_visuals" / "visual_plan.json").write_text(
        json.dumps(
            {
                "schema": 8,
                "style_profile": "expressive_25d_v8",
                "clips": [{"clip_number": 1, "sentence_index": 1, "act": 1, "grammar": "expressive_vinyl_world"}],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (ep_dir / "04_audio" / "voice_report.json").write_text(
        json.dumps(
            {
                "engine": "edge_tts",
                "voice": "en-US-EmmaMultilingualNeural",
                "sentence_spans": [{"sentence_index": 1, "start_sec": 0.0, "end_sec": 2.5, "text": "Fresh dolphin line."}],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (ep_dir / "05_assembly" / "edit_decision_list.json").write_text(
        json.dumps(
            {
                "schema": 8,
                "style_profile": "expressive_25d_v8",
                "cuts": [
                    {
                        "cut_index": 1,
                        "clip_index": 1,
                        "act": 1,
                        "sentence_index": 1,
                        "end_sentence_index": 1,
                        "out_start_sec": 0.0,
                        "out_end_sec": 2.5,
                        "duration_sec": 2.5,
                        "src_start_sec": 0.1,
                        "src_end_sec": 2.6,
                        "grammar": "expressive_vinyl_world",
                        "camera_move": "gentle_push_in",
                    }
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    cuts_sp, _ctx = extract_cut_intent_specs(ep_dir, final_mp4_duration_sec=2.5)
    assert len(cuts_sp) == 1
    assert cuts_sp[0]["spoken_narration"] == "Fresh dolphin line."

    dummy_thumb = np.full((220, 124, 3), 120, dtype=np.uint8)
    sheets = render_posthoc_viewer_strips(
        cut_reports=[
            {
                "cut_index": 1,
                "clip_index": 1,
                "act": 1,
                "grammar": "expressive_vinyl_world",
                "camera_move": "gentle_push_in",
                "out_start_sec": 0.0,
                "out_end_sec": 2.5,
                "passed": True,
                "clarity_score": 95.0,
                "spoken_narration": cuts_sp[0]["spoken_narration"],
                "intended_scene": "Dolphin ornament beside brass lamp",
                "defects": [],
                "remediation": "none",
                "sub_scores": {
                    "visual_legibility": 96.0,
                    "action_and_camera": 94.0,
                    "temporal_coherence": 95.0,
                    "intent_grammar_alignment": 95.0,
                    "composition_and_sync": 95.0,
                },
                "metrics": {
                    "sharpness_laplacian": 80.0,
                    "edge_density": 0.04,
                    "fg_bg_contrast_de": 18.0,
                    "mean_motion_diff": 4.2,
                    "p95_motion_diff": 9.1,
                    "max_step_hist_jump": 0.08,
                },
            }
        ],
        sample_thumbs_by_cut={1: [dummy_thumb, dummy_thumb, dummy_thumb]},
        out_dir=ep_dir / "05_assembly" / "posthoc_viewer_strips",
        final_mp4_sha256="abcdef0123456789" * 4,
        evaluated_at_utc="2026-11-08T11:00:00Z",
    )
    assert len(sheets) == 1 and Path(sheets[0]).is_file()
    sheet_im = cv2.imread(sheets[0])
    assert sheet_im is not None
    # Top-right header ROI must carry rendered provenance text pixels above background (24,28,36)
    hdr_roi = sheet_im[8:40, 960:1330]
    assert float(np.max(hdr_roi)) > 160.0

    # 4. Single-narrator v8 TTS synthesis never calls foil Steffan and writes foil_voice=None (+0Hz Emma)
    import pipeline.voice_fallback as vf_mod

    called_voices: list[tuple[str, str]] = []

    def _fake_edge_acts(
        clean_sents: list[str],
        script_doc: dict[str, Any] | None,
        sr: int,
        cache_dir: Path,
        voice: str,
        rate: str,
        pitch: str = "+0Hz",
        **_kwargs: Any,
    ) -> list[np.ndarray]:
        called_voices.append((voice, pitch))
        t_v = np.arange(int(3.6 * sr), dtype=np.float32) / float(sr)
        sig_v = (0.28 * np.sin(2.0 * math.pi * 190.0 * t_v)).astype(np.float32)
        return [sig_v.copy() for _ in clean_sents]

    import pipeline.elevenlabs_tts as el_mod

    def _fake_el_episode(clean_sents_in: list[str], *, voice_id: str, sr: int = 48000, **_kwargs: Any) -> dict[str, Any]:
        called_voices.append((voice_id, "+0Hz"))
        t_v = np.arange(int(3.6 * sr), dtype=np.float32) / float(sr)
        sig_v = (0.28 * np.sin(2.0 * math.pi * 190.0 * t_v)).astype(np.float32)
        return {
            "pcms": [sig_v.copy() for _ in clean_sents_in],
            "voice_id": voice_id,
            "word_timestamps_by_idx": {},
            "characters_used": 0,
            "script_characters": sum(len(s) for s in clean_sents_in),
            "model_id": "eleven_v4",
            "output_format": "mp3_44100_192",
            "request_ids": [],
            "used_voices_by_idx": {idx + 1: voice_id for idx in range(len(clean_sents_in))},
        }

    monkeypatch.setattr(el_mod, "synthesize_elevenlabs_v4_episode", _fake_el_episode)
    single_tts_proj = tmp_path / "v8_emma_single_tts_proj"
    for sub in ("03_visuals", "04_audio"):
        (single_tts_proj / sub).mkdir(parents=True, exist_ok=True)
    (single_tts_proj / "03_visuals" / "visual_plan.json").write_text(
        json.dumps({"style_profile": "expressive_25d_v8", "format_profile": "shorts_expressive_v8"}, indent=2),
        encoding="utf-8",
    )
    tts_res = vf_mod.synthesize_continuous_diorama_track(
        single_tts_proj,
        sents,
        align_whisper=False,
        script_doc={
            "style_profile": "expressive_25d_v8",
            "format_profile": "shorts_expressive_v8",
            "voice_preset": "el_researcher_v4",
            "foil_sentence_indices": [],
        },
        prosody_mode="expressive_us_v8",
    )
    vr_single = tts_res["report"]
    assert vr_single["voice"] == "tnSpp4vdxKPjI9w0GnoV"
    assert vr_single["voice_preset"] == "el_researcher_v4"
    assert vr_single["pitch"] == "+0Hz"
    assert vr_single["foil_voice"] is None
    assert vr_single["foil_voice_preset"] is None
    assert vr_single["foil_sentence_indices"] == []
    assert all(sp["speaker"] == "narrator" for sp in vr_single["sentence_spans"])
    assert all(v == "tnSpp4vdxKPjI9w0GnoV" for v, _ in called_voices)

    # 5. Direct DQ13_transition_hygiene checks: >4 styled transitions, >6f alpha dissolve, and MP4 ghost blend fail!
    dq_proj = tmp_path / "v8_dq13_unit_proj"
    for sub in ("02_script", "03_visuals", "04_audio", "05_assembly", "06_publish"):
        (dq_proj / sub).mkdir(parents=True, exist_ok=True)
    dq_vp = populate_expressive_v8_reference_contract(_sample_v8_visual_plan(sents), daisy_chain_keyframes=True)
    dq_sc = {
        "schema": 8,
        "style_profile": "expressive_25d_v8",
        "format_profile": "shorts_expressive_v8",
        "foil_sentence_indices": [],
        "sentences": sents,
    }
    (dq_proj / "02_script" / "script.json").write_text(json.dumps(dq_sc, indent=2), encoding="utf-8")
    (dq_proj / "03_visuals" / "visual_plan.json").write_text(json.dumps(dq_vp, indent=2), encoding="utf-8")
    dq_prompts = build_diorama_v7_prompts(dq_vp, sents)
    dq_contract = compile_episode_qa_contract(dq_vp, sents, dq_prompts, script_doc=dq_sc)

    # Build a small 30fps MP4 (clean hard cuts vs ghost alpha blend at Cut 1->2 boundary t=2.00s)
    fps_dq = 30
    total_f_dq = fps_dq * 16  # 16s across 8 cuts (2.0s each) for fast decode
    cuts_dq = [
        {
            "cut_index": i_c,
            "clip_index": i_c,
            "act": min(6, i_c),
            "sentence_index": i_c,
            "end_sentence_index": i_c,
            "out_start_sec": round((i_c - 1) * 2.0, 3),
            "out_end_sec": round(i_c * 2.0, 3),
            "duration_sec": 2.0,
            "src_start_sec": 0.1,
            "src_end_sec": 2.1,
            "grammar": "expressive_cameo_world" if i_c == 5 else ("expressive_xray_brain" if i_c == 7 else "expressive_vinyl_world"),
            "cameo_easter_egg": (i_c == 5),
            "camera_move": "gentle_push_in",
            "transition_out": "portal_crash_zoom_10f" if i_c == 6 else "hard",
            "mode": "single",
        }
        for i_c in range(1, 9)
    ]
    (dq_proj / "04_audio" / "voice_report.json").write_text(
        json.dumps({"engine": "edge_tts", "active_speech_ratio": 0.90, "true_rms_voiced_ratio": 0.86}, indent=2),
        encoding="utf-8",
    )
    (dq_proj / "04_audio" / "subtitles.ass").write_text("[Events]\n", encoding="utf-8")

    # Clean frames: Cut 1 dark cool (45), Cut 2 bright warm (185), sharp non-ghosted boundary at f=60 (t=2.00s)
    clean_frames: list[np.ndarray] = []
    for f_k in range(total_f_dq):
        val = 45 if f_k < 60 else (185 if f_k < 120 else 95)
        im_k = np.full((320, 180, 3), val, dtype=np.uint8)
        cv2.circle(im_k, (90 + (f_k % 20), 140), 20, (235, 235, 240), -1)
        clean_frames.append(im_k)
    _write_test_mp4(dq_proj / "05_assembly" / "final_shorts_1080x1920.mp4", clean_frames, fps=fps_dq)

    edl_clean = {
        "schema": 8,
        "style_profile": "expressive_25d_v8",
        "fps": fps_dq,
        "total_duration_sec": 16.0,
        "speech_end_sec": 15.8,
        "max_clip_reuse": 1,
        "cuts": cuts_dq,
    }
    (dq_proj / "05_assembly" / "edit_decision_list.json").write_text(json.dumps(edl_clean, indent=2), encoding="utf-8")
    rep_clean = verify_final_mp4_against_contract(dq_proj, contract=dq_contract, save_report=False)
    assert rep_clean["gates"]["DQ13_transition_hygiene"]["passed"] is True

    # Negative A: >50% alpha dissolves on an 8-cut EDL (5 > 4) must fail DQ13
    edl_over = copy.deepcopy(edl_clean)
    for k_ov in range(5):
        edl_over["cuts"][k_ov]["transition_out"] = "dissolve_8f"
    (dq_proj / "05_assembly" / "edit_decision_list.json").write_text(json.dumps(edl_over, indent=2), encoding="utf-8")
    rep_over = verify_final_mp4_against_contract(dq_proj, contract=dq_contract, save_report=False)
    assert rep_over["gates"]["DQ13_transition_hygiene"]["passed"] is False
    assert len(rep_over["gates"]["DQ13_transition_hygiene"]["alpha_fade_cuts"]) == 5

    # Negative B: 20f alpha dissolve (> EXPRESSIVE_V8_MAX_ALPHA_DISSOLVE_FRAMES=15) must fail DQ13
    edl_alpha20 = copy.deepcopy(edl_clean)
    edl_alpha20["cuts"][0]["transition_out"] = "dissolve_20f"
    (dq_proj / "05_assembly" / "edit_decision_list.json").write_text(json.dumps(edl_alpha20, indent=2), encoding="utf-8")
    rep_alpha20 = verify_final_mp4_against_contract(dq_proj, contract=dq_contract, save_report=False)
    assert rep_alpha20["gates"]["DQ13_transition_hygiene"]["passed"] is False
    assert rep_alpha20["gates"]["DQ13_transition_hygiene"]["max_alpha_fade_frames"] == 20

    # Negative C: Sustained full-frame alpha ghost blend in decoded MP4 around Cut 1->2 (t=2.00s, frames 53..60) must fail DQ13!
    ghost_frames = [im.copy() for im in clean_frames]
    f_pre_ref = clean_frames[46].astype(np.float32)
    f_post_ref = clean_frames[70].astype(np.float32)
    for idx_g, f_g in enumerate(range(52, 62)):
        alpha_g = 0.75 - 0.05 * idx_g  # linear 75%..30% full-frame double exposure!
        ghost_frames[f_g] = np.clip(alpha_g * f_pre_ref + (1.0 - alpha_g) * f_post_ref, 0, 255).astype(np.uint8)
    _write_test_mp4(dq_proj / "05_assembly" / "final_shorts_1080x1920.mp4", ghost_frames, fps=fps_dq)
    (dq_proj / "05_assembly" / "edit_decision_list.json").write_text(json.dumps(edl_clean, indent=2), encoding="utf-8")
    rep_ghost = verify_final_mp4_against_contract(dq_proj, contract=dq_contract, save_report=False)
    assert rep_ghost["gates"]["DQ13_transition_hygiene"]["passed"] is False
    assert 1 in rep_ghost["gates"]["DQ13_transition_hygiene"]["ghost_blend_cuts"]


def test_v8_prompt_builder_keyframe_chain_hard_transition_and_9_cameras(tmp_path: Path) -> None:
    import shutil

    from pipeline.depiction_rules import EXPRESSIVE_V8_CAMERA_DESCRIPTORS, EXPRESSIVE_V8_TRANSITION_CLAUSES
    from pipeline.reference_image_qa import build_and_verify_project_reference_pack, register_reference_image

    sents = _sample_v8_sentences()

    # 1. Every camera move in EXPRESSIVE_V8_CAMERA_MOVES and transition in EXPRESSIVE_V8_TRANSITION_TYPES is mapped & valid
    assert set(cfg.EXPRESSIVE_V8_CAMERA_MOVES) == set(EXPRESSIVE_V8_CAMERA_DESCRIPTORS.keys())
    assert set(cfg.EXPRESSIVE_V8_TRANSITION_TYPES) == set(EXPRESSIVE_V8_TRANSITION_CLAUSES.keys())

    vp_all = _sample_v8_visual_plan(sents)
    all_cams = list(cfg.EXPRESSIVE_V8_CAMERA_MOVES)
    all_trans = list(cfg.EXPRESSIVE_V8_TRANSITION_TYPES)
    for idx0, c_spec in enumerate(vp_all["clips"]):
        cam_pick = all_cams[(idx0 + 5) % len(all_cams)]
        c_spec["camera_move"] = "dolly_zoom_vertigo" if idx0 == 0 and cam_pick == "locked_tripod" else cam_pick
        c_spec["transition_to_next"] = "hard" if idx0 in (0, 1, 19) else all_trans[idx0 % len(all_trans)]
    vp_all = populate_expressive_v8_reference_contract(vp_all)
    prompts_all = build_diorama_v7_prompts(vp_all, sents)
    assert prompts_all[0]["transition_out"] == "hard"
    assert prompts_all[1]["transition_out"] == "hard"
    # Single-anchor non-cameo clips use 1-chip VIDEO_REFERENCES mode (matching flow_diorama_sharded_worker)
    assert prompts_all[0]["flow_input_mode"] == "VIDEO_REFERENCES"
    assert prompts_all[0]["keyframe_chain_mode"] == "single_reference_anchor"
    # Clean 'hard' cut must NOT inject any styled transition clause into Veo prompt
    for tc_phrase in EXPRESSIVE_V8_TRANSITION_CLAUSES.values():
        assert tc_phrase.lower() not in prompts_all[0]["prompt"].lower()
    assert validate_diorama_v7_prompts(prompts_all, vp_all) == []

    # 2. Continuous Start+End VIDEO_FRAMES keyframe chain + portal_to_brain room->X-Ray dome zoom-in + Brain->Brain handoff + DQ13
    vp_portal = _sample_v8_visual_plan(sents)
    for c_s in vp_portal["clips"]:
        c_s.pop("transition_to_next", None)
    # Clip 14 (index 13) opens the crystal X-Ray dome from hotel_room_3am Start Frame -> ref_xray_brain_9x16 End Frame
    vp_portal["clips"][13]["portal_to_brain"] = True
    vp_portal = populate_expressive_v8_reference_contract(vp_portal, daisy_chain_keyframes=True)
    prompts_portal = build_diorama_v7_prompts(vp_portal, sents)

    c13_room_p = prompts_portal[12]
    c14_portal_p = prompts_portal[13]
    c15_brain_p = prompts_portal[14]
    c10_cameo = prompts_portal[9]
    assert c14_portal_p["portal_to_brain"] is True
    assert c14_portal_p["flow_input_mode"] == "VIDEO_FRAMES"
    assert c14_portal_p["keyframe_chain_mode"] == "portal_zoom_to_xray_brain"
    assert c14_portal_p["full_trajectory_span"] is True
    assert "kf_14_hotel_room_3am" in str(c14_portal_p["reference_image"])
    assert str(c14_portal_p["end_reference_image"]).endswith("ref_xray_brain_9x16.png")
    assert c14_portal_p["start_anchor_id"].startswith("kf_14_hotel_room_3am")
    assert c14_portal_p["end_anchor_id"] == "ref_xray_brain_9x16"
    from pipeline.depiction_rules import FLOW_CAMERA_HARDWARE_NEGATIVE_GUARD

    assert "3d" in c14_portal_p["prompt"].lower() and "crystal" in c14_portal_p["prompt"].lower()
    assert FLOW_CAMERA_HARDWARE_NEGATIVE_GUARD in c14_portal_p["prompt"]
    c14_core = c14_portal_p["prompt"].replace(FLOW_CAMERA_HARDWARE_NEGATIVE_GUARD, "").strip()
    assert 30 <= len(c14_core.split()) <= cfg.PROMPT_SCENE_WORDS_MAX
    # Preceding room clip 13 seamlessly daisy-chains its End Frame into clip 14's room Start Frame!
    assert c13_room_p["end_reference_image"] == c14_portal_p["reference_image"]
    assert c13_room_p["transition_out"] == "daisy_chain_bridge"
    # Following brain clip 15 seamlessly starts from clip 14's X-Ray End Frame -> ref_xray_brain_2_9x16 End Frame!
    assert c14_portal_p["end_reference_image"] == c15_brain_p["reference_image"]
    assert str(c15_brain_p["end_reference_image"]).endswith("ref_xray_brain_2_9x16.png")
    assert c15_brain_p["flow_input_mode"] == "VIDEO_FRAMES"
    assert c15_brain_p["keyframe_chain_mode"] == "start_end_interpolation"
    assert c14_portal_p["transition_out"] == "daisy_chain_bridge"
    # Cameo clip 10 uses 2-chip VIDEO_REFERENCES mode and never binds end_reference_image
    assert c10_cameo["flow_input_mode"] == "VIDEO_REFERENCES"
    assert c10_cameo["keyframe_chain_mode"] == "dual_reference_ingredients"
    assert not c10_cameo.get("end_reference_image")

    sc_portal = {
        "schema": 8,
        "style_profile": "expressive_25d_v8",
        "format_profile": "shorts_expressive_v8",
        "opening_mode": "action",
        "core_reveal_sentence_index": 14,
        "foil_sentence_indices": [],
        "sentences": sents,
    }
    assert validate_diorama_v7_prompts(prompts_portal, vp_portal) == []
    assert validate_production_diorama_v6(vp_portal, sents, prompts_portal, script_doc=sc_portal) == []
    assert verify_pre_flow_contract(vp_portal, sents, prompts_portal, script_doc=sc_portal) == []

    # Verify vp_portal passes DQ13_transition_hygiene end-to-end (<=4 styled transitions, <=6f alpha dissolve)
    portal_proj = tmp_path / "v8_portal_dq13_proj"
    for sub in ("02_script", "03_visuals", "04_audio", "05_assembly", "06_publish"):
        (portal_proj / sub).mkdir(parents=True, exist_ok=True)
    (portal_proj / "02_script" / "script.json").write_text(json.dumps(sc_portal, indent=2), encoding="utf-8")
    (portal_proj / "03_visuals" / "visual_plan.json").write_text(json.dumps(vp_portal, indent=2), encoding="utf-8")
    (portal_proj / "04_audio" / "voice_report.json").write_text(
        json.dumps({"engine": "edge_tts", "active_speech_ratio": 0.90, "true_rms_voiced_ratio": 0.86}, indent=2),
        encoding="utf-8",
    )
    (portal_proj / "04_audio" / "subtitles.ass").write_text("[Events]\n", encoding="utf-8")
    portal_contract = compile_episode_qa_contract(vp_portal, sents, prompts_portal, script_doc=sc_portal)
    portal_cuts = [
        {
            "cut_index": idx_k,
            "clip_index": idx_k,
            "act": int(p_k["act"]),
            "sentence_index": idx_k,
            "end_sentence_index": idx_k,
            "out_start_sec": round((idx_k - 1) * 2.0, 3),
            "out_end_sec": round(idx_k * 2.0, 3),
            "duration_sec": 2.0,
            "src_start_sec": 0.1,
            "src_end_sec": 2.1,
            "grammar": p_k["grammar"],
            "cameo_easter_egg": bool(p_k["cameo_easter_egg"]),
            "camera_move": p_k["camera_move"],
            "transition_out": ("hard" if idx_k == len(prompts_portal) else p_k["transition_out"]),
            "reference_image": p_k.get("reference_image"),
            "end_reference_image": p_k.get("end_reference_image"),
            "mode": "single",
        }
        for idx_k, p_k in enumerate(prompts_portal, start=1)
    ]
    portal_frames = [
        np.full((320, 180, 3), 50 + ((f_idx // 60) * 11) % 160, dtype=np.uint8)
        for f_idx in range(30 * 2 * len(prompts_portal))
    ]
    _write_test_mp4(portal_proj / "05_assembly" / "final_shorts_1080x1920.mp4", portal_frames, fps=30)
    (portal_proj / "05_assembly" / "edit_decision_list.json").write_text(
        json.dumps(
            {
                "schema": 8,
                "style_profile": "expressive_25d_v8",
                "fps": 30,
                "total_duration_sec": round(2.0 * len(prompts_portal), 3),
                "speech_end_sec": round(2.0 * len(prompts_portal) - 0.2, 3),
                "max_clip_reuse": 1,
                "cuts": portal_cuts,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    rep_portal_dq = verify_final_mp4_against_contract(portal_proj, contract=portal_contract, save_report=False)
    assert rep_portal_dq["gates"]["DQ13_transition_hygiene"]["passed"] is True, rep_portal_dq["gates"]["DQ13_transition_hygiene"]
    assert rep_portal_dq["gates"]["DQ13_transition_hygiene"]["styled_transition_count"] <= cfg.EXPRESSIVE_V8_MAX_STYLED_TRANSITIONS
    assert rep_portal_dq["gates"]["DQ13_transition_hygiene"]["max_alpha_fade_frames"] <= cfg.EXPRESSIVE_V8_MAX_ALPHA_DISSOLVE_FRAMES

    # 2b. Non-daisy portal_to_brain modes (master-only & synthesize_scene_anchors=True) never leak multi-panel sheets into Start/End
    vp_portal_master = _sample_v8_visual_plan(sents)
    vp_portal_master["clips"][13]["portal_to_brain"] = True
    vp_portal_master = populate_expressive_v8_reference_contract(vp_portal_master)
    prompts_portal_master = build_diorama_v7_prompts(vp_portal_master, sents)
    assert str(prompts_portal_master[13]["reference_image"]).endswith("expressive_conflict_master.png")
    assert str(prompts_portal_master[13]["end_reference_image"]).endswith("xray_brain75_master.png")
    assert validate_diorama_v7_prompts(prompts_portal_master, vp_portal_master) == []

    vp_portal_synth = _sample_v8_visual_plan(sents)
    vp_portal_synth["clips"][13]["portal_to_brain"] = True
    vp_portal_synth["clips"][13]["location_id"] = "sleep_lab_portal_booth"
    vp_portal_synth = populate_expressive_v8_reference_contract(vp_portal_synth, synthesize_scene_anchors=True)
    prompts_portal_synth = build_diorama_v7_prompts(vp_portal_synth, sents)
    assert str(prompts_portal_synth[13]["reference_image"]).endswith("ref_loc_sleep_lab_portal_booth_9x16.png")
    assert str(prompts_portal_synth[13]["end_reference_image"]).endswith("ref_xray_brain_9x16.png")
    assert validate_diorama_v7_prompts(prompts_portal_synth, vp_portal_synth) == []

    # 3. allow_early_brain_override parity between validate_diorama_v7_prompts and verify_pre_flow_contract
    vp_early = copy.deepcopy(vp_portal)
    vp_early["clips"][3]["grammar"] = "expressive_xray_brain"
    vp_early["clips"][3]["brain_clip"] = True
    vp_early["clips"][3]["portal_to_brain"] = True
    vp_early["clips"][3]["end_reference_image"] = "03_visuals/reference_images/ref_xray_brain_9x16.png"
    vp_early["clips"][3]["action"] = (
        "inside the transparent crystal-dome cranium, bounded 4-color 3D brain pathways glow warm amber "
        "across the left hemisphere while the right hemisphere rests in calm cyan"
    )
    prompts_early = build_diorama_v7_prompts(vp_early, sents)
    # Blocked by default when allow_early_brain_override is False/omitted
    assert any("premature 3D brain reveal" in x for x in validate_diorama_v7_prompts(prompts_early, vp_early))
    # Allowed cleanly when allow_early_brain_override=True (while keeping >=1 brain clip in [60-85%])
    vp_early["allow_early_brain_override"] = True
    assert validate_diorama_v7_prompts(prompts_early, vp_early) == []

    # 4. Negative keyframe-chain guards: duplicate Start==End, missing Start, VIDEO_REFERENCES+End conflict, and multi-panel Start/End sheets
    bad_dup = copy.deepcopy(prompts_portal)
    bad_dup[0]["end_reference_image"] = bad_dup[0]["reference_image"]
    dup_errs = validate_diorama_v7_prompts(bad_dup, vp_portal)
    assert any("duplicates start reference_image" in x for x in dup_errs), dup_errs

    bad_nostart = copy.deepcopy(prompts_portal)
    bad_nostart[0]["reference_image"] = None
    bad_nostart[0]["end_reference_image"] = "03_visuals/reference_images/kf_02_hotel_room_3am_medium_9x16.png"
    nostart_errs = validate_diorama_v7_prompts(bad_nostart, vp_portal)
    assert any("requires a non-empty start reference_image" in x for x in nostart_errs), nostart_errs

    bad_conflict = copy.deepcopy(prompts_portal)
    bad_conflict[9]["end_reference_image"] = "03_visuals/reference_images/kf_11_hotel_room_3am_wide_9x16.png"
    conflict_errs = validate_diorama_v7_prompts(bad_conflict, vp_portal)
    assert any("mutually exclusive" in x for x in conflict_errs), conflict_errs

    bad_cameo_end = copy.deepcopy(prompts_portal)
    bad_cameo_end[0]["end_reference_image"] = "03_visuals/reference_images/cameo_opt3_sheet.png"
    cameo_end_errs = validate_diorama_v7_prompts(bad_cameo_end, vp_portal)
    assert any("cameo turnaround sheet" in x for x in cameo_end_errs), cameo_end_errs

    bad_species_start = copy.deepcopy(prompts_portal)
    bad_species_start[13]["reference_image"] = "03_visuals/reference_images/species_opt1_sheet.png"
    species_start_errs = validate_diorama_v7_prompts(bad_species_start, vp_portal)
    assert any("start reference_image" in x and "turnaround/cast sheet" in x for x in species_start_errs), species_start_errs

    bad_cast_end = copy.deepcopy(prompts_portal)
    bad_cast_end[0]["end_reference_image"] = "03_visuals/reference_images/cast_sheet_02_clinical_historical_6roles.png"
    cast_end_errs = validate_diorama_v7_prompts(bad_cast_end, vp_portal)
    assert any("turnaround/cast sheet" in x for x in cast_end_errs), cast_end_errs

    # 5. Stale reference_image_specs.json cache invalidation when new custom anchors are added to visual_plan.json
    cache_proj = tmp_path / "v8_ref_cache_invalidation_proj"
    (cache_proj / "03_visuals").mkdir(parents=True)
    vp_cache = populate_expressive_v8_reference_contract(_sample_v8_visual_plan(sents))
    (cache_proj / "03_visuals" / "visual_plan.json").write_text(json.dumps(vp_cache, indent=2), encoding="utf-8")
    def _sign_ref_review_r85(p_root: Path) -> None:
        sem_p = p_root / "03_visuals" / "reference_images" / "reference_semantic_review.json"
        sem_doc = json.loads(sem_p.read_text(encoding="utf-8"))
        sem_doc["reviewer"] = "@Research"
        for idx_r, (rid, r_ent) in enumerate(sem_doc["images"].items()):
            r_ent["checks"] = {k: True for k in (r_ent.get("checks") or {})}
            r_ent["note"] = f"Verified anchor #{idx_r + 1} ({rid}) with clean bald 2.5D vinyl / 4-color brain fidelity."
        sem_p.write_text(json.dumps(sem_doc, indent=2), encoding="utf-8")

    res_init = ensure_expressive_v8_reference_pack(cache_proj)
    assert res_init["cached"] is False
    assert res_init["status"] == "REVIEW_PENDING"
    assert res_init["total_images"] == 6
    _sign_ref_review_r85(cache_proj)
    res_hit = ensure_expressive_v8_reference_pack(cache_proj)
    assert res_hit["cached"] is True

    # Add a new portal Start keyframe anchor to visual_plan.json (staging its PNG offline) -> must invalidate stale 6-spec cache!
    custom_fn = "kf_14_hotel_room_3am_portal_9x16.png"
    shutil.copy2(
        cache_proj / "03_visuals" / "reference_images" / "expressive_conflict_master.png",
        cache_proj / "03_visuals" / "reference_images" / custom_fn,
    )
    register_reference_image(cache_proj, custom_fn, "flow_image_generation")
    vp_cache["reference_anchors"] = [
        {
            "ref_id": "kf_14_hotel_room_3am_portal_9x16",
            "filename": custom_fn,
            "clip_number": 14,
            "frame": "start",
            "category": "clip_keyframe_anchor",
            "role": "reenactment",
            "setting": "real_env",
            "location_id": "hotel_room_3am",
            "camera_angle_tag": "eye_level_medium",
            "generation_order": 3,
            "conditioned_on": ["species_opt1_sheet"],
            "prompt": (
                "Single full-bleed vertical 9:16 3D miniature diorama scene of a dimly lit 3 AM hotel room "
                "with a clothed 2.5D matte cream-white vinyl character, bold charcoal-black 2D ink eyes, zero text."
            ),
        }
    ]
    vp_cache["clips"][13]["portal_to_brain"] = True
    (cache_proj / "03_visuals" / "visual_plan.json").write_text(json.dumps(vp_cache, indent=2), encoding="utf-8")

    res_rebuilt = ensure_expressive_v8_reference_pack(cache_proj)
    assert res_rebuilt["cached"] is False
    assert res_rebuilt["status"] == "REVIEW_PENDING"
    assert res_rebuilt["cv_pre_generation_ready"] is True
    assert res_rebuilt["total_images"] == 7
    _sign_ref_review_r85(cache_proj)
    assert inspect_reference_image_pack(cache_proj)["pre_generation_ready"] is True
    specs_after = json.loads((cache_proj / "03_visuals" / "reference_image_specs.json").read_text(encoding="utf-8"))
    assert any(s.get("filename") == custom_fn for s in specs_after["all_specs"])
    rep_rebuilt = build_and_verify_project_reference_pack(cache_proj)
    assert rep_rebuilt["total_existing"] == 7


def test_v8_narration_restructure_empathy_opening_core_reveal_and_myth_flip_cap() -> None:
    from pipeline.prompt_quality_v5 import validate_script_spine_v8, validate_script_spine_v8_report

    # 1. Old 18-sentence pilot_02 script must FAIL due to 3 repeated myth-flips (> 1)
    old_18_sents = [
        "At 3 AM in a new hotel bed, your eyes snap wide open!",
        "Yet back home, you sleep right through loud street sirens.",
        "Your pillow did not ruin night one — your skull just flipped on a night patrol.",
        "A front desk clerk shrugs and says your mattress just feels stiff.",
        "Wrong — back home, loud street sirens never wake you at all.",
        "Scientist Yuka Sasaki scanned thirty-five sleepers across two lab nights.",
        "Wait, what split right down the middle of the brain on night one?",
        "A lab assistant guessed airport jet lag ruined night one.",
        "Except only the left half of the head refused to power down.",
        "Sea whales and migrating birds use that exact trick to spot danger.",
        "Sleep labs even throw out night one data because of it.",
        "Your travel friend says hotel hallways are simply too noisy.",
        "Yet a tiny hallway creak only jolts you on night one.",
        "You see, your default mode network, your daydream network, stays awake on the left.",
        "Your auditory cortex, your sound center, fires three times faster — like a tripwire.",
        "By night two in that same bed, the left guard finally stands down.",
        "Pack your own pillowcase — or let that night watchman guard your trip?",
        "Tonight in a strange room, half your head stands guard while half dreams.",
    ]
    old_issues = validate_script_spine_v8(
        old_18_sents,
        script_doc={"opening_mode": "situation", "foil_sentence_indices": [4, 8, 12]},
    )
    assert any("myth-flip pattern repeated 3 times" in x for x in old_issues), f"Expected 3x myth-flip failure: {old_issues}"

    # 2. Benchmark-aligned 15-sentence R68 script (Action Cold-Open <=12w + Delayed Core Reveal [60-80%] + Climax Cut) must PASS with 0 issues & 0 advisories
    new_15_sents = [
        "At 3 AM in a hotel bed, your eyes snap open!",
        "Back home, you sleep right through loud street sirens.",
        "And no, it's not a stiff hotel mattress.",
        "Your friend laughs and blames that late airport espresso.",
        "Inside a dark sleep booth, sensors tracked two straight nights.",
        "On night one, the right side sank into deep, quiet sleep.",
        "But the left side? It stayed light, like a guard on watch.",
        "Play a strange beep, and that left side woke sleepers three times faster!",
        "Dolphins and wild ducks do the same on open water at night.",
        "You try counting sheep, but the left half refuses to power down.",
        "You see, a hidden network on your left side stays on guard.",
        "Your sound center keeps scanning, ready to wake you if anything shifts.",
        "By night two in the same room, the guard finally stands down.",
        "Both halves sink into deep rest once the room feels safe.",
        "Because that bad first night means half your head kept you safe.",
    ]
    new_doc = {
        "opening_mode": "action",
        "core_reveal_sentence_index": 11,
        "foil_sentence_indices": [],
        "omit_experiment_nicknames": ["First-Night Effect", "first-night effect"],
        "sentence_beats": [
            "action_open",
            "hook_promise",
            "aggro",
            "conflict",
            "evidence",
            "evidence",
            "escalation",
            "evidence",
            "evidence",
            "setback",
            "core",
            "mechanism",
            "payoff",
            "payoff",
            "climax_cut",
        ],
    }
    rep_ok = validate_script_spine_v8_report(new_15_sents, script_doc=new_doc)
    assert rep_ok["issues"] == [], f"Unexpected issues on benchmark R68 script: {rep_ok['issues']}"
    assert rep_ok["advisories"] == [], f"Unexpected advisories on benchmark R68 script: {rep_ok['advisories']}"

    # 3. Question S1 in default 'action' mode -> FAIL; with opening_mode='question' -> PASS + advisory
    q_sents = ["Ever sleep terribly your first night in a hotel?"] + new_15_sents[1:]
    q_fail = validate_script_spine_v8_report(q_sents, script_doc=new_doc)
    assert any("not a '?' question" in x for x in q_fail["issues"]), q_fail
    q_doc = dict(new_doc, opening_mode="question", sentence_beats=["question"] + new_doc["sentence_beats"][1:])
    q_pass = validate_script_spine_v8_report(q_sents, script_doc=q_doc)
    assert q_pass["issues"] == [], f"Expected optional question mode pass: {q_pass['issues']}"
    assert any("opening_mode='question'" in a for a in q_pass["advisories"]), q_pass["advisories"]

    # 4. Action S1 > 30 words, banned empathy filler ("You're not alone"), or spoken outro '?' -> FAIL
    long_action_s1 = [
        "At three in the morning inside a strange downtown hotel suite where heavy rain taps against the frosted glass window, your exhausted eyes suddenly snap wide open in total panic right beside the suitcase!"
    ] + new_15_sents[1:]
    long_action_rep = validate_script_spine_v8_report(long_action_s1, script_doc=new_doc)
    assert any("words > max 30" in x for x in long_action_rep["issues"]), long_action_rep

    filler_sents = [new_15_sents[0], "You're not alone."] + new_15_sents[2:]
    filler_rep = validate_script_spine_v8_report(filler_sents, script_doc=new_doc)
    assert any("empathy filler" in x for x in filler_rep["issues"]), filler_rep

    # Real study / university context is allowed by default (EXPRESSIVE_V8_FORBID_SPOKEN_CITATIONS=False),
    # and still blocked when EXPRESSIVE_V8_FORBID_SPOKEN_CITATIONS=True
    citation_sents = list(new_15_sents)
    citation_sents[4] = "Scientist Yuka Sasaki scanned thirty-five sleepers across two lab nights."
    cit_allowed = validate_script_spine_v8_report(citation_sents, script_doc=new_doc)
    assert not any("academic researcher/citation" in x for x in cit_allowed["issues"]), cit_allowed
    monkeypatch_prev = cfg.EXPRESSIVE_V8_FORBID_SPOKEN_CITATIONS
    try:
        cfg.EXPRESSIVE_V8_FORBID_SPOKEN_CITATIONS = True
        cit_rep = validate_script_spine_v8_report(citation_sents, script_doc=new_doc)
        assert any("academic researcher/citation" in x or "sample count" in x for x in cit_rep["issues"]), cit_rep
    finally:
        cfg.EXPRESSIVE_V8_FORBID_SPOKEN_CITATIONS = monkeypatch_prev

    outro_q_sents = new_15_sents[:-1] + ["So on your next trip, would you pack your own pillowcase?"]
    outro_q_rep = validate_script_spine_v8_report(outro_q_sents, script_doc=new_doc)
    assert any("final sentence ends with '?'" in x for x in outro_q_rep["issues"]), outro_q_rep

    # Question mode S1 > 20 words OR 3rd-person ('he/she/they') question -> FAIL
    long_s1 = [
        "Have you ever woken up completely exhausted at three in the morning on your very first night inside an unfamiliar downtown hotel suite?"
    ] + new_15_sents[1:]
    long_rep = validate_script_spine_v8_report(long_s1, script_doc=q_doc)
    assert any("words > max 20" in x for x in long_rep["issues"]), long_rep

    third_p_s1 = ["Why do they always wake up tired on their first night in a hotel?"] + new_15_sents[1:]
    third_rep = validate_script_spine_v8_report(third_p_s1, script_doc=q_doc)
    assert any("2nd person" in x for x in third_rep["issues"]), third_rep

    # 5. Premature core reveal at S4 (< 60% delayed reveal window S9..S13 for 15 sentences) -> FAIL
    early_core_doc = dict(new_doc, core_reveal_sentence_index=4)
    early_rep = validate_script_spine_v8_report(new_15_sents, script_doc=early_core_doc)
    assert any("core_reveal_sentence_index" in x and "60-80%" in x for x in early_rep["issues"]), early_rep

    # 6. Missing escalation pivot ('Wait, what' / 'But ...?') -> PASS + 1 advisory
    no_pivot_sents = list(new_15_sents)
    no_pivot_sents[6] = "The left side stayed light, like a guard on watch."
    no_piv_rep = validate_script_spine_v8_report(no_pivot_sents, script_doc=new_doc)
    assert no_piv_rep["issues"] == [], no_piv_rep
    assert len(no_piv_rep["advisories"]) == 1 and "escalation pivot" in no_piv_rep["advisories"][0], no_piv_rep








