from __future__ import annotations

import json
from pathlib import Path

import pytest

from pipeline.config import (
    DIORAMA_CLIP_COUNT_DEFAULT,
    DIORAMA_TARGET_CUT_MIN,
    DIORAMA_V7_CUT_CV_MIN,
    DIORAMA_V7_LONG_TAKE_MAX_SEC,
    DIORAMA_V7_MID_ACT_MAX_CUT_SEC,
    DIORAMA_V7_RAPID_CUT_MIN_SEC,
    PORCELAIN_V7_AVG_CUT_MAX_SEC,
    PORCELAIN_V7_AVG_CUT_MIN_SEC,
    PORCELAIN_V7_CUT_CV_MIN,
    PORCELAIN_V7_LITERAL_ANALOGY_MAX_CLIPS,
    PORCELAIN_V7_LONG_TAKE_MAX_SEC,
    PORCELAIN_V7_MAX_HOLD_SENTENCES,
    PORCELAIN_V7_MID_ACT_MAX_CUT_SEC,
    PORCELAIN_V7_MIN_CUT_SEC,
    PORCELAIN_V7_TARGET_CLIP_MAX,
    PORCELAIN_V7_TARGET_CLIP_MIN,
)
from pipeline.diorama_assembler import assemble_diorama_project, build_v7_dynamic_edl
from pipeline.plain_language import validate_number_analogy_pairing
from pipeline.prompt_quality_v5 import (
    validate_scene_state_continuity,
    validate_substantive_visual_relevance,
)


def test_porcelain_v7_documentary_pacing_constants_and_legacy_lowpoly_preservation() -> None:
    assert DIORAMA_CLIP_COUNT_DEFAULT == 48
    assert DIORAMA_TARGET_CUT_MIN == 44
    assert PORCELAIN_V7_MIN_CUT_SEC == 1.80
    assert PORCELAIN_V7_MID_ACT_MAX_CUT_SEC == 4.30
    assert PORCELAIN_V7_LONG_TAKE_MAX_SEC == 4.50
    assert PORCELAIN_V7_AVG_CUT_MIN_SEC == 2.85
    assert PORCELAIN_V7_AVG_CUT_MAX_SEC == 3.35
    assert PORCELAIN_V7_CUT_CV_MIN == 0.15
    assert PORCELAIN_V7_TARGET_CLIP_MIN == 45
    assert PORCELAIN_V7_TARGET_CLIP_MAX == 52
    assert PORCELAIN_V7_MAX_HOLD_SENTENCES == 2
    assert PORCELAIN_V7_LITERAL_ANALOGY_MAX_CLIPS == 2

    # Legacy R63 lowpoly_pastel_v7 constants remain untouched
    assert DIORAMA_V7_RAPID_CUT_MIN_SEC == 0.68
    assert DIORAMA_V7_MID_ACT_MAX_CUT_SEC == 4.60
    assert DIORAMA_V7_LONG_TAKE_MAX_SEC == 6.50
    assert DIORAMA_V7_CUT_CV_MIN == 0.36


def test_build_v7_dynamic_edl_porcelain_no_artificial_split_and_exact_split_hstack_left_clip(tmp_path: Path) -> None:
    # 25 sentences (including a 4.90s S1, a 1.15s short S3, and a split_hstack on S2), 27 unique clips (25 primary + 1 split_right + 1 outro)
    sentence_spans = []
    cur = 0.05
    for idx in range(1, 26):
        dur = 4.90 if idx == 1 else (3.40 if idx == 2 else (1.15 if idx == 3 else 3.20))
        sentence_spans.append(
            {
                "sentence_index": idx,
                "start_sec": round(cur, 3),
                "end_sec": round(cur + dur, 3),
                "duration_sec": dur,
                "text": f"Sentence {idx} documentary narration.",
            }
        )
        cur += dur + 0.08
    speech_end_sec = round(cur, 3)
    total_duration_sec = round(speech_end_sec + 2.20, 3)

    clips_spec = []
    for idx in range(1, 26):
        clips_spec.append(
            {
                "sentence_index": idx,
                "end_sentence_index": idx,
                "act": min(6, (idx - 1) // 5 + 1),
                "grammar": "porcelain_fullbleed_world",
                "camera": "locked_tripod",
            }
        )
        if idx == 2:
            clips_spec.append(
                {
                    "sentence_index": 2,
                    "end_sentence_index": 2,
                    "cut_role": "split_right",
                    "act": 1,
                    "grammar": "porcelain_living_brain",
                    "camera": "locked_tripod",
                }
            )
    clips_spec.append({"cut_role": "outro", "act": 6, "grammar": "porcelain_fullbleed_world", "camera": "tilt_up"})

    visual_plan = {
        "schema_version": 7,
        "profile": "neuro_diorama",
        "style_profile": "porcelain_cinematic_v7",
        "split_comparisons": [
            {
                "sentence_index": 2,
                "mode": "split_hstack",
                "left_clip_index": 2,
                "right_clip_index": 3,
                "left_label": "OUTSIDE: SILENT",
                "right_label": "INSIDE: RACING",
            }
        ],
        "clips": clips_spec,
    }
    clip_files = [tmp_path / f"clip_{i}.mp4" for i in range(1, len(clips_spec) + 1)]

    edl = build_v7_dynamic_edl(
        visual_plan=visual_plan,
        sentence_spans=sentence_spans,
        clip_files=clip_files,
        speech_end_sec=speech_end_sec,
        total_duration_sec=total_duration_sec,
    )
    cuts = edl["cuts"]
    # 25 primary speech cuts (no 0.30/0.70 artificial split on 4.90s S1, no split on S2) + 1 outro = 26 cuts
    assert len(cuts) == 26
    assert all(float(c["duration_sec"]) >= PORCELAIN_V7_MIN_CUT_SEC for c in cuts)
    assert all(float(c["duration_sec"]) <= PORCELAIN_V7_LONG_TAKE_MAX_SEC for c in cuts)

    split_cuts = [c for c in cuts if c.get("mode") == "split_hstack"]
    assert len(split_cuts) == 1
    assert split_cuts[0]["clip_index"] == 2
    assert split_cuts[0]["secondary_clip_index"] == 3
    assert split_cuts[0]["sentence_index"] == 2
    assert split_cuts[0]["duration_sec"] >= 3.30


def test_substantive_visual_relevance_enforces_balanced_clip_window_and_blocks_3_sentence_holds() -> None:
    lines_50 = [f"Sentence {i} documentary statement." for i in range(1, 51)]
    too_few_clips = [
        {"sentence_index": 1, "end_sentence_index": 3, "hold_sentences": 3, "grammar": "porcelain_fullbleed_world", "scene": "porcelain figure lifts block"}
    ] + [
        {"sentence_index": i, "end_sentence_index": i, "grammar": "porcelain_fullbleed_world", "scene": "porcelain figure lifts block"}
        for i in range(4, 36)
    ] + [{"cut_role": "outro", "grammar": "porcelain_fullbleed_world", "scene": "sunlit room tilt up"}]
    issues_few = validate_substantive_visual_relevance({"clips": too_few_clips}, lines_50, too_few_clips)
    assert any("below balanced documentary floor" in x for x in issues_few), issues_few
    assert any("multi-sentence hold spans 3 sentences" in x for x in issues_few), issues_few

    too_many_clips = [
        {"sentence_index": min(50, i), "end_sentence_index": min(50, i), "grammar": "porcelain_fullbleed_world", "scene": "porcelain figure lifts block"}
        for i in range(1, 56)
    ]
    issues_many = validate_substantive_visual_relevance({"clips": too_many_clips}, lines_50, too_many_clips)
    assert any("exceeds balanced documentary ceiling" in x for x in issues_many), issues_many


def test_preserve_audio_master_missing_audio_raises_file_not_found(tmp_path: Path) -> None:
    proj = tmp_path / "missing_audio_proj"
    (proj / "02_script").mkdir(parents=True)
    (proj / "03_visuals" / "flow_native_clips").mkdir(parents=True)
    (proj / "04_audio").mkdir(parents=True)
    for i in range(1, 27):
        (proj / "03_visuals" / "flow_native_clips" / f"clip_{i}.mp4").write_bytes(b"\x00" * 1024)
    (proj / "02_script" / "script.json").write_text(
        json.dumps({"schema_version": 7, "profile": "neuro_diorama", "sentences": ["Hello world!"]}),
        encoding="utf-8",
    )
    (proj / "03_visuals" / "visual_plan.json").write_text(
        json.dumps({"schema_version": 7, "profile": "neuro_diorama", "style_profile": "porcelain_cinematic_v7", "clips": []}),
        encoding="utf-8",
    )
    with pytest.raises(FileNotFoundError, match="preserve_audio_master=True"):
        assemble_diorama_project(proj, preserve_audio_master=True)


def test_plain_language_number_analogy_exempts_everyday_units_and_enforces_technical_units() -> None:
    everyday_sentences = [
        "The key took thirty seconds for seventy percent of twelve-month babies.",
        "Each test ran twenty minutes inside a nine-foot room for three decades.",
        "Klaus Grossmann tested forty-one babies across eight parts.",
    ]
    assert validate_number_analogy_pairing(everyday_sentences) == []

    unpaired_scientific = [
        "The cortical spike arrived in 350 milliseconds across 2.4 millimeters of tissue.",
    ]
    issues = validate_number_analogy_pairing(unpaired_scientific)
    assert len(issues) == 1
    assert "350 milliseconds" in issues[0]

    paired_scientific = [
        "The cortical spike arrived in 350 milliseconds, faster than a camera blink.",
    ]
    assert validate_number_analogy_pairing(paired_scientific) == []


def test_substantive_visual_relevance_blocks_chronometers_scale_fillers_and_allows_explicit_override() -> None:
    bad_clips = [
        {
            "sentence_index": 1,
            "grammar": "porcelain_hands_closeup",
            "scene": "a porcelain hand presses a brushed-chrome stopwatch button as the sweep dial ticks",
        },
        {
            "sentence_index": 2,
            "grammar": "porcelain_literal_analogy",
            "scene": "a sunlit table comparing a sensor beside a blank postage stamp while hands unroll a brass measuring tape",
        },
        {
            "sentence_index": 3,
            "grammar": "porcelain_literal_analogy",
            "scene": "five identical miniature oak child chairs arranged side by side",
        },
        {
            "sentence_index": 4,
            "grammar": "porcelain_literal_analogy",
            "scene": "a ceramic coffee cup beside an ivory notebook",
        },
    ]
    bad_plan = {
        "schema_version": 7,
        "profile": "neuro_diorama",
        "style_profile": "porcelain_cinematic_v7",
        "split_comparisons": [{"sentence_index": 2, "mode": "split_hstack", "left_clip_index": 99, "right_clip_index": 2}],
        "clips": bad_clips,
    }
    issues = validate_substantive_visual_relevance(bad_plan, ["s1", "s2", "s3", "s4"], bad_clips)
    assert any("stopwatch" in x.lower() or "chronometer" in x.lower() for x in issues)
    assert any("measuring tape" in x.lower() or "postage stamp" in x.lower() or "miniature" in x.lower() for x in issues)
    assert any("porcelain_literal_analogy" in x for x in issues)
    assert any("left_clip_index" in x for x in issues)

    # Explicit historical chronoscope override (e.g. Benjamin Libet clock) passes cleanly
    libet_clips = [
        {
            "sentence_index": 1,
            "grammar": "porcelain_hands_closeup",
            "scene": "a porcelain volunteer watches the rotating cathode-ray stopwatch dot and presses a brass key",
        }
    ]
    libet_plan = {
        "schema_version": 7,
        "profile": "neuro_diorama",
        "style_profile": "porcelain_cinematic_v7",
        "allow_chronometer_apparatus": True,
        "clips": libet_clips,
    }
    assert validate_substantive_visual_relevance(libet_plan, ["s1"], libet_clips) == []


def test_scene_state_continuity_blocks_duplicate_entrance_ghost_ref_dual_keyframes_and_brain_leak() -> None:
    bad_plan = {
        "schema_version": 7,
        "profile": "neuro_diorama",
        "style_profile": "porcelain_cinematic_v7",
        "require_scene_state_ledger": True,
        "reference_anchors": [
            {
                "ref_id": "ref_s06_start",
                "location_id": "hopkins_playroom_1970",
                "present_cast": ["mother", "toddler", "stranger"],
            },
            {
                "ref_id": "ref_s08_start",
                "location_id": "hopkins_playroom_1970",
                "present_cast": ["mother", "toddler", "stranger"],
            },
        ],
        "clips": [
            # 1) Pre-seated stranger in ref_s06_start while stranger is entering + overlap in present_cast_start
            {
                "sentence_index": 1,
                "location_id": "hopkins_playroom_1970",
                "reference_image": "03_visuals/reference_images/ref_s06_start.png",
                "end_reference_image": "03_visuals/reference_images/ref_s08_start.png",
                "grammar": "porcelain_fullbleed_world",
                "scene_state": {
                    "location_id": "hopkins_playroom_1970",
                    "present_cast_start": ["mother", "toddler", "stranger"],
                    "entering_cast": ["stranger"],
                    "exiting_cast": [],
                    "present_cast_end": ["mother", "toddler", "stranger"],
                },
            },
            # 2) Ghost stranger in ref_s08_start when only mother + toddler should be present
            {
                "sentence_index": 2,
                "location_id": "hopkins_playroom_1970",
                "reference_image": "03_visuals/reference_images/ref_s08_start.png",
                "grammar": "porcelain_fullbleed_world",
                "scene_state": {
                    "location_id": "hopkins_playroom_1970",
                    "present_cast_start": ["mother", "toddler"],
                    "entering_cast": [],
                    "exiting_cast": [],
                    "present_cast_end": ["mother", "toddler"],
                },
            },
            # 3) Cross-location ref leak + brain_master ref on room clip
            {
                "sentence_index": 3,
                "location_id": "modern_dining_room",
                "reference_image": "03_visuals/reference_images/ref_brain_master.png",
                "end_reference_image": "03_visuals/reference_images/ref_s06_start.png",
                "grammar": "porcelain_fullbleed_world",
                "scene_state": {
                    "location_id": "modern_dining_room",
                    "present_cast_start": ["partner_a", "partner_b"],
                    "entering_cast": [],
                    "exiting_cast": [],
                    "present_cast_end": ["partner_a", "partner_b"],
                },
            },
            # 4) Missing scene_state when require_scene_state_ledger=True
            {
                "sentence_index": 4,
                "location_id": "modern_dining_room",
                "grammar": "porcelain_fullbleed_world",
            },
        ],
    }
    issues = validate_scene_state_continuity(bad_plan, bad_plan["clips"])
    assert any("already in present_cast_start" in x for x in issues)
    assert any("multiple scene keyframes" in x for x in issues)
    assert any("not in present_cast_start" in x for x in issues)
    assert any("cutaway brain reference" in x for x in issues)
    assert any("location_id=" in x for x in issues)
    assert any("missing scene_state ledger dict" in x for x in issues)

    clean_plan = {
        "schema_version": 7,
        "profile": "neuro_diorama",
        "style_profile": "porcelain_cinematic_v7",
        "require_scene_state_ledger": True,
        "reference_anchors": [
            {
                "ref_id": "ref_s01_start",
                "location_id": "hopkins_playroom_1970",
                "present_cast": ["mother", "toddler"],
            }
        ],
        "clips": [
            {
                "sentence_index": 1,
                "location_id": "hopkins_playroom_1970",
                "reference_image": "03_visuals/reference_images/ref_s01_start.png",
                "grammar": "porcelain_fullbleed_world",
                "scene_state": {
                    "location_id": "hopkins_playroom_1970",
                    "present_cast_start": ["mother", "toddler"],
                    "entering_cast": ["stranger"],
                    "exiting_cast": [],
                    "present_cast_end": ["mother", "toddler", "stranger"],
                },
            }
        ],
    }
    assert validate_scene_state_continuity(clean_plan, clean_plan["clips"]) == []


def test_scientific_volume_nano_and_frequency_units_require_everyday_analogy() -> None:
    unpaired = [
        "1 cubic millimeter of cortex holds fifty thousand synapses.",
        "Synaptic clefts span 20 nanometers while electrodes sample at 30 kilohertz under 3 teslas.",
    ]
    issues = validate_number_analogy_pairing(unpaired)
    assert len(issues) == 2

    paired = [
        "1 cubic millimeter of cortex, like a grain of sand, holds fifty thousand synapses.",
        "Synaptic clefts span 20 nanometers, thinner than soap film, sampled at 30 kilohertz.",
    ]
    assert validate_number_analogy_pairing(paired) == []


def test_raw_plan_fields_catch_sand_timer_countdown_timers_and_scale_fillers() -> None:
    raw_clips = [
        {
            "sentence_index": 1,
            "grammar": "porcelain_literal_analogy",
            "analogy_world": "a sunlit kitchen counter holding a glass sand timer",
            "comparison_action": "porcelain hands flip the sand timer upright",
        },
        {
            "sentence_index": 2,
            "grammar": "porcelain_hands_closeup",
            "attire_and_hands": "porcelain hands lining up four silver countdown timers",
            "prop_action": "hands unroll a tape measure beside a giant film reel",
            "consequence": "four empty oak chairs stand in a row",
        },
    ]
    plan = {
        "schema_version": 7,
        "profile": "neuro_diorama",
        "style_profile": "porcelain_cinematic_v7",
        "clips": raw_clips,
    }
    issues = validate_substantive_visual_relevance(plan, ["s1", "s2"], [{}, {}])
    assert any("sand timer" in x.lower() for x in issues), issues
    assert any("countdown timer" in x.lower() or "tape measure" in x.lower() for x in issues), issues


def test_cross_clip_sequential_scene_state_catches_ghost_returns_and_duplicate_reentries() -> None:
    seq_plan = {
        "schema_version": 7,
        "profile": "neuro_diorama",
        "style_profile": "porcelain_cinematic_v7",
        "require_scene_state_ledger": True,
        "strict_room_continuity": True,
        "clips": [
            {
                "sentence_index": 1,
                "location_id": "playroom",
                "grammar": "porcelain_fullbleed_world",
                "scene_state": {
                    "location_id": "playroom",
                    "present_cast_start": ["mother", "toddler", "stranger"],
                    "entering_cast": [],
                    "exiting_cast": ["stranger"],
                    "present_cast_end": ["mother", "toddler"],
                },
            },
            # Ghost return of departed stranger + duplicate re-entry of already-present mother!
            {
                "sentence_index": 2,
                "location_id": "playroom",
                "grammar": "porcelain_fullbleed_world",
                "scene_state": {
                    "location_id": "playroom",
                    "present_cast_start": ["toddler", "stranger"],
                    "entering_cast": ["mother"],
                    "exiting_cast": [],
                    "present_cast_end": ["mother", "toddler", "stranger"],
                },
            },
        ],
    }
    issues = validate_scene_state_continuity(seq_plan, seq_plan["clips"])
    assert any("reappeared in present_cast_start" in x for x in issues), issues
    assert any("already inside 'playroom'" in x for x in issues), issues

    # Explicit protocol_phase_jump allows clean multi-episode jumps
    seq_plan["clips"][1]["scene_state"] = {
        "location_id": "playroom",
        "protocol_phase_jump": True,
        "present_cast_start": ["toddler"],
        "entering_cast": ["mother"],
        "exiting_cast": [],
        "present_cast_end": ["mother", "toddler"],
    }
    assert validate_scene_state_continuity(seq_plan, seq_plan["clips"]) == []


def test_porcelain_world_rule_never_attaches_cranium_clause_to_room_sentence() -> None:
    from pipeline.depiction_rules import PorcelainWorldRule, validate_porcelain_v7_scene

    sc_explicit_oval = PorcelainWorldRule.compose(
        "a sunlit home nursery room with birch crib rails, a cream woven rug, and tall windows",
        "one clothed matte-white porcelain child with a smooth featureless white oval head in a sky-blue sweater lifts a wooden block",
    )
    first_sentence = sc_explicit_oval.split(".")[0].lower()
    assert "cranium" not in first_sentence
    assert "frosted-glass cranium" not in sc_explicit_oval.lower()
    assert validate_porcelain_v7_scene(sc_explicit_oval, grammar="porcelain_fullbleed_world", camera_move="locked_tripod") == []


def test_edge_anchored_horizontal_split_seam_detector_distinguishes_split_screen_from_interior_lines() -> None:
    import cv2
    import numpy as np
    from pipeline.flow_diorama_sharded_worker import detect_unintended_horizontal_split_seam

    # Interior shelf/panel lines (10%..90% width) -> 0.0 seam
    interior = np.full((640, 360, 3), (220, 224, 228), dtype=np.uint8)
    cv2.line(interior, (36, 280), (324, 280), (60, 70, 80), 4)
    assert detect_unintended_horizontal_split_seam(interior) < 0.20

    # True edge-to-edge 50/50 split-screen -> >= 0.95 seam
    split_frm = np.full((640, 360, 3), (232, 234, 236), dtype=np.uint8)
    split_frm[300:, :] = (145, 150, 155)
    assert detect_unintended_horizontal_split_seam(split_frm) >= 0.95


def test_reenact_extract_and_sanitize_persist_sub_event_keyframes(tmp_path: Path) -> None:
    import subprocess
    import cv2
    import imageio_ffmpeg
    import numpy as np
    from pipeline.source_reenactment import extract_source_edl, sanitize_structural_frames

    src_avi = tmp_path / "raw_src.avi"
    src_mp4 = tmp_path / "src.mp4"
    vw = cv2.VideoWriter(str(src_avi), cv2.VideoWriter_fourcc(*"MJPG"), 10.0, (320, 240))
    for fi in range(150):  # 15.0s continuous shot with smooth actor walk-in between 2.0s and 5.5s (no hard cut)
        frm = np.full((240, 320, 3), (210, 215, 220), dtype=np.uint8)
        cv2.rectangle(frm, (20, 160), (100, 220), (120, 140, 160), -1)
        alpha = min(1.0, max(0.0, (fi - 20) / 35.0))
        if alpha > 0.0:
            w_in = int(round(200 * alpha))
            cv2.rectangle(frm, (310 - w_in, 30), (310, 230), (20, 40, 195), -1)
        vw.write(frm)
    vw.release()
    subprocess.run(
        [imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-i", str(src_avi), "-c:v", "libx264", "-pix_fmt", "yuv420p", str(src_mp4)],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    q_dir = tmp_path / "quarantine"
    edl = extract_source_edl(src_mp4, slug="unit_sub_test", work_dir=q_dir, run_whisper=False)
    sub_events = [se for sh in edl["shots"] for se in (sh.get("sub_events") or [])]
    assert len(sub_events) >= 1
    sub_id = sub_events[0]["sub_id"]
    assert (q_dir / "shots" / f"{sub_id}.png").exists()

    san = sanitize_structural_frames(q_dir, edl)
    assert any(g["guide_filename"] == f"{sub_id}_guide.png" for g in san["guides"])
    assert (q_dir / "guides" / f"{sub_id}_guide.png").exists()


def test_stale_posthoc_shift_window_recommendations_ignored(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import os
    import pipeline.diorama_assembler as da

    proj = tmp_path / "stale_shift_proj"
    (proj / "02_script").mkdir(parents=True)
    (proj / "03_visuals" / "flow_native_clips").mkdir(parents=True)
    (proj / "04_audio").mkdir(parents=True)
    (proj / "05_assembly").mkdir(parents=True)

    for i in range(1, 27):
        cp = proj / "03_visuals" / "flow_native_clips" / f"clip_{i}.mp4"
        cp.write_bytes(b"\x00" * 1024)
        os.utime(cp, ns=(1_000_000_000, 1_000_000_000))

    (proj / "02_script" / "script.json").write_text(
        json.dumps({"schema_version": 7, "profile": "neuro_diorama", "sentences": ["S1!", "S2."]}),
        encoding="utf-8",
    )
    vp_path = proj / "03_visuals" / "visual_plan.json"
    vp_path.write_text(
        json.dumps(
            {
                "schema_version": 7,
                "profile": "neuro_diorama",
                "style_profile": "porcelain_cinematic_v7",
                "clips": [{"sentence_index": 1, "src_start_sec": 0.5}] + [{"sentence_index": 2} for _ in range(25)],
            }
        ),
        encoding="utf-8",
    )
    os.utime(vp_path, ns=(1_000_000_000, 1_000_000_000))

    (proj / "04_audio" / "audio_master.wav").write_bytes(b"RIFF\x00\x00\x00\x00WAVE")
    (proj / "04_audio" / "voice_report.json").write_text(
        json.dumps(
            {
                "sentence_spans": [{"index": 1, "start_sec": 0.0, "end_sec": 2.5}, {"index": 2, "start_sec": 2.5, "end_sec": 5.0}],
                "events": [],
                "speech_end_sec": 5.0,
                "total_duration_sec": 6.0,
                "sample_rate": 48000,
            }
        ),
        encoding="utf-8",
    )

    ph_path = proj / "05_assembly" / "posthoc_semantic_qa_report.json"
    ph_doc = {
        "source_clips": [{"clip_index": i} for i in range(1, 27)],
        "summary": {
            "shift_window_recommendations": [
                {"clip_index": 1, "recommended_src_window_sec": [2.0, 5.0]},  # authored src_start_sec -> ignored
                {"clip_index": 2, "recommended_src_window_sec": [1.5, 4.5]},
                {"clip_index": 3, "recommended_src_window_sec": [1.0, 4.0]},
            ]
        },
        "cuts": [],
    }
    ph_path.write_text(json.dumps(ph_doc), encoding="utf-8")
    os.utime(ph_path, ns=(2_000_000_000, 2_000_000_000))

    captured: list[Any] = []

    def _stop_at_edl(**kwargs: Any) -> dict[str, Any]:
        captured.append(kwargs.get("source_window_overrides"))
        raise RuntimeError("STOP_AFTER_EDL")

    monkeypatch.setattr(da, "build_crosscut_edl", _stop_at_edl)

    # Case 1: Fresh report matching 26 clips -> applies clips 2 & 3, skips authored clip 1
    with pytest.raises(RuntimeError, match="STOP_AFTER_EDL"):
        assemble_diorama_project(proj, preserve_audio_master=True)
    assert captured[-1] == {2: [1.5, 4.5], 3: [1.0, 4.0]}

    # Case 2: clip_2.mp4 regenerated AFTER report -> clip 2 skipped, clip 3 still applied
    os.utime(proj / "03_visuals" / "flow_native_clips" / "clip_2.mp4", ns=(3_000_000_000, 3_000_000_000))
    with pytest.raises(RuntimeError, match="STOP_AFTER_EDL"):
        assemble_diorama_project(proj, preserve_audio_master=True)
    assert captured[-1] == {3: [1.0, 4.0]}

    # Case 3: visual_plan.json edited AFTER report -> entire stale report ignored
    os.utime(vp_path, ns=(4_000_000_000, 4_000_000_000))
    with pytest.raises(RuntimeError, match="STOP_AFTER_EDL"):
        assemble_diorama_project(proj, preserve_audio_master=True)
    assert captured[-1] is None


def test_substantive_visual_relevance_blocks_disguised_timers_sandglass_diorama_and_miniature_neighborhoods() -> None:
    disguised = [
        {"sentence_index": 1, "grammar": "porcelain_hands_closeup", "prop_action": "both hands set a mechanical timer beside the wood plane"},
        {"sentence_index": 2, "grammar": "porcelain_fullbleed_world", "environment": "slate desks with brushed-silver timers"},
        {"sentence_index": 3, "grammar": "porcelain_hands_closeup", "prop_action": "hands flip an eight-minute sandglass upright"},
        {"sentence_index": 4, "grammar": "porcelain_hands_closeup", "attire_and_hands": "hands beside a small brushed-silver desk clock"},
        {"sentence_index": 5, "grammar": "porcelain_hands_closeup", "prop_action": "hands unstrap a silver wristwatch on the counter"},
        {"sentence_index": 6, "grammar": "porcelain_cutaway_section", "structure": "mechanical acoustic interval chimes on an oak plinth"},
        {"sentence_index": 7, "grammar": "porcelain_fullbleed_world", "environment": "table displaying two wooden neighborhood dioramas"},
        {"sentence_index": 8, "grammar": "porcelain_cutaway_section", "structure": "rail track linking two miniature stations"},
    ]
    issues = validate_substantive_visual_relevance({"clips": disguised}, [f"s{i}" for i in range(1, 9)], disguised)
    for idx in range(1, 9):
        assert any(x.startswith(f"clip {idx}: [filler_ban_v7]") for x in issues), (idx, issues)


def test_validate_scene_state_continuity_plan_clips_override_stale_cached_prompts() -> None:
    stale_cached = [
        {
            "clip_number": 1,
            "location_id": "playroom",
            "grammar": "porcelain_fullbleed_world",
            "scene_state": {
                "location_id": "playroom",
                "present_cast_start": ["mother"],
                "entering_cast": ["mother"],  # stale bug that was fixed in plan["clips"]
                "exiting_cast": [],
                "present_cast_end": ["mother"],
            },
        }
    ]
    plan = {
        "require_scene_state_ledger": True,
        "strict_room_continuity": True,
        "clips": [
            {
                "location_id": "playroom",
                "grammar": "porcelain_fullbleed_world",
                "scene_state": {
                    "location_id": "playroom",
                    "present_cast_start": ["mother"],
                    "entering_cast": [],
                    "exiting_cast": ["mother"],
                    "present_cast_end": [],
                },
            },
            {
                "location_id": "playroom",
                "grammar": "porcelain_fullbleed_world",
                "scene_state": {
                    "location_id": "playroom",
                    "present_cast_start": ["mother"],  # departed in clip 1 without re-entering -> must be caught even though len(stale_cached)==1!
                    "entering_cast": [],
                    "exiting_cast": [],
                    "present_cast_end": ["mother"],
                },
            },
        ],
    }
    issues = validate_scene_state_continuity(plan, stale_cached)
    assert not any(x.startswith("clip 1:") for x in issues), issues
    assert any(x.startswith("clip 2:") for x in issues), issues


def test_diorama_seed_from_dossier_uses_porcelain_48_clip_default_and_preserves_lowpoly_61() -> None:
    from pipeline.research_dossier import diorama_seed_from_dossier

    seed_porcelain = diorama_seed_from_dossier("ainsworth_strange_situation")
    assert seed_porcelain["style_profile"] == "porcelain_cinematic_v7"
    assert seed_porcelain["target_clip_count"] == DIORAMA_CLIP_COUNT_DEFAULT == 48

    seed_lowpoly = diorama_seed_from_dossier("ainsworth_strange_situation", style_profile="lowpoly_pastel_v7")
    assert seed_lowpoly["style_profile"] == "lowpoly_pastel_v7"
    assert seed_lowpoly["target_clip_count"] == 61


def test_build_v7_dynamic_edl_preserves_180_floor_and_450_ceiling_at_duration_boundaries(tmp_path: Path) -> None:
    clips_51 = [tmp_path / f"clip_{i}.mp4" for i in range(1, 52)]
    for p in clips_51:
        p.write_bytes(b"0")

    # Boundary A: 115.0s episode with 51 clips (50 speech cuts + 1 outro) and skewed sentence durations
    spans_a = []
    t = 0.0
    for s in range(1, 51):
        dt = 0.90 if s % 3 == 0 else 2.91
        spans_a.append({"sentence_index": s, "act": min(6, (s - 1) // 9 + 1), "start_sec": round(t, 3), "end_sec": round(min(112.0, t + dt), 3)})
        t = min(112.0, t + dt)
    spans_a[-1]["end_sec"] = 112.0
    vp_a = {
        "schema_version": 7,
        "style_profile": "porcelain_cinematic_v7",
        "zero_clip_reuse": True,
        "clips": [{"sentence_index": s, "end_sentence_index": s, "act": min(6, (s - 1) // 9 + 1), "grammar": "porcelain_fullbleed_world", "camera": "locked_tripod"} for s in range(1, 51)]
        + [{"cut_role": "outro", "act": 6, "grammar": "porcelain_fullbleed_world", "camera": "tilt_up"}],
    }
    edl_a = build_v7_dynamic_edl(vp_a, spans_a, clips_51, 112.0, 115.0)
    assert edl_a["min_cut_duration_sec"] >= PORCELAIN_V7_MIN_CUT_SEC
    assert edl_a["max_cut_duration_sec"] <= PORCELAIN_V7_LONG_TAKE_MAX_SEC

    # Boundary B: 178.75s episode (176.25s speech) with 44 clips (41 single-sentence speech cuts + 1 split + 1 outro)
    clips_44 = clips_51[:44]
    spans_b = []
    t = 0.0
    for s in range(1, 42):
        dt = 6.20 if s <= 5 else (176.25 - 31.0) / 36.0
        spans_b.append({"sentence_index": s, "act": min(6, (s - 1) // 7 + 1), "start_sec": round(t, 3), "end_sec": round(min(176.25, t + dt), 3)})
        t = min(176.25, t + dt)
    spans_b[-1]["end_sec"] = 176.25
    vp_b = {
        "schema_version": 7,
        "style_profile": "porcelain_cinematic_v7",
        "zero_clip_reuse": True,
        "split_comparisons": [{"sentence_index": 20, "mode": "split_hstack", "left_clip_index": 20, "right_clip_index": 21}],
        "clips": (
            [{"sentence_index": s, "end_sentence_index": s, "act": min(6, (s - 1) // 7 + 1), "grammar": "porcelain_fullbleed_world", "camera": "locked_tripod"} for s in range(1, 21)]
            + [{"sentence_index": 20, "end_sentence_index": 20, "cut_role": "split_right", "act": 3, "grammar": "porcelain_living_brain", "camera": "locked_tripod"}]
            + [{"sentence_index": s, "end_sentence_index": s, "act": min(6, (s - 1) // 7 + 1), "grammar": "porcelain_fullbleed_world", "camera": "locked_tripod"} for s in range(21, 42)]
            + [{"cut_role": "outro", "act": 6, "grammar": "porcelain_fullbleed_world", "camera": "tilt_up"}]
        ),
    }
    edl_b = build_v7_dynamic_edl(vp_b, spans_b, clips_44, 176.25, 178.75)
    assert edl_b["min_cut_duration_sec"] >= PORCELAIN_V7_MIN_CUT_SEC
    assert edl_b["max_cut_duration_sec"] <= PORCELAIN_V7_LONG_TAKE_MAX_SEC


def test_thumbnail_head_occlusion_in_hook_band_penalizes_standing_decapitation_only() -> None:
    import cv2
    import numpy as np
    from pipeline.thumbnail_studio import _has_head_occlusion_in_hook_band

    # Warm sunlit wall background
    standing = np.full((1920, 1080, 3), (175, 200, 215), dtype=np.uint8)
    # Matte-white oval porcelain head right inside y=265..415 above a camel cardigan torso
    cv2.ellipse(standing, (540, 340), (55, 68), 0, 0, 360, (238, 240, 242), -1)
    cv2.rectangle(standing, (455, 415), (625, 620), (80, 135, 185), -1)
    assert _has_head_occlusion_in_hook_band(standing, "porcelain_fullbleed_world") is True
    assert _has_head_occlusion_in_hook_band(standing, "porcelain_living_brain") is False

    # Seated figure well below hook text band (head at y=540)
    seated = np.full((1920, 1080, 3), (175, 200, 215), dtype=np.uint8)
    cv2.ellipse(seated, (540, 540), (55, 68), 0, 0, 360, (238, 240, 242), -1)
    cv2.rectangle(seated, (455, 615), (625, 820), (80, 135, 185), -1)
    assert _has_head_occlusion_in_hook_band(seated, "porcelain_fullbleed_world") is False


