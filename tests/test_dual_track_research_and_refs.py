"""
Regression & edge-case tests for the Dual-Track Research & Reference Conditioning architecture:
  - 4-Gate `evaluate_media_reenactment_suitability` (B&W 16mm exemption, dark void, blocked channels,
    flat 2D slide/cartoon, unwindowed long documentary)
  - Generalized `sanitize_structural_frame_bgr` & `detect_human_faces_yunet` (B&W corner preservation vs
    high-chroma wall decal masking, 9:16 720x1280 output without black bars)
  - Dynamic `validate_reenactment_non_infringement` (no hardcoded Ainsworth names/IDs)
  - `normalize_scene_prop` (`name` vs `item`), multi-role `cast_lock_entries` (Schema v7 flat vs Schema v5 `wardrobe`)
  - Track B `populate_porcelain_reference_contract`, `build_reference_image_specs`, selective `reference_image`
    binding (`~55-68%`), `strict_room_continuity`, and `inspect_reference_image_pack` `require_review` defaults
  - `write_flow_prompts_json` direct write when target dir already contains `visual_plan.json`
"""

from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np

from pipeline.config import YUNET_FACE_MODEL_PATH
from pipeline.flow_prompt_builder import build_flow_prompts, write_flow_prompts_json
from pipeline.porcelain_anchor_pack import (
    populate_porcelain_reference_contract,
    sanitize_porcelain_contract_text,
)
from pipeline.prompt_quality_v5 import validate_scene_state_continuity
from pipeline.reference_image_qa import (
    build_reference_image_specs,
    inspect_reference_image_pack,
    register_reference_image,
    write_reference_image_specs,
)
from pipeline.research_dossier import (
    evaluate_media_reenactment_suitability,
    normalize_scene_prop,
)
from pipeline.scene_blueprint import cast_lock_entries
from pipeline.source_reenactment import (
    detect_human_faces_yunet,
    sanitize_structural_frame_bgr,
    validate_reenactment_non_infringement,
)


def _write_keyframes(kf_dir: Path, frames: list[np.ndarray]) -> None:
    kf_dir.mkdir(parents=True, exist_ok=True)
    for idx, frm in enumerate(frames, start=1):
        cv2.imwrite(str(kf_dir / f"kf_{idx:03d}.jpg"), frm)


def test_bundled_yunet_face_model_exists_and_handles_empty_or_bw_input() -> None:
    assert Path(YUNET_FACE_MODEL_PATH).exists(), "Bundled YuNet ONNX model must exist in pipeline/assets/models/"
    assert detect_human_faces_yunet(np.zeros((0, 0, 3), dtype=np.uint8)) == []
    assert detect_human_faces_yunet(np.zeros((8, 8, 3), dtype=np.uint8)) == []

    # Clean B&W laboratory grid without faces should not crash and returns a valid list
    rng = np.random.default_rng(42)
    bw = np.clip(185 + rng.normal(0, 9, size=(360, 480)), 0, 255).astype(np.uint8)
    bw_bgr = cv2.cvtColor(bw, cv2.COLOR_GRAY2BGR)
    res = detect_human_faces_yunet(bw_bgr)
    assert isinstance(res, list)


def test_four_gate_suitability_classifier_cases(tmp_path: Path) -> None:
    rng = np.random.default_rng(7)

    # 1. Gate 1: Blocked explainer channel -> reject_track_b_only
    r_chan = evaluate_media_reenactment_suitability(
        {
            "id": "M_ted",
            "kind": "video",
            "title": "How memory works",
            "channel": "TED-Ed",
            "url": "https://www.youtube.com/watch?v=abcd1234efg",
        }
    )
    assert r_chan["suitability"] == "reject_track_b_only"
    assert r_chan["metrics"]["gate_failed"] == 1

    # 2. Gate 1: Pre-cinema era (< 1895) historical case -> reject_track_b_only
    r_era = evaluate_media_reenactment_suitability(
        {
            "id": "M_gage",
            "kind": "video",
            "title": "Phineas Gage case overview",
            "channel": "University Archive",
            "url": "https://www.youtube.com/watch?v=gage1848xyz",
        },
        primary_year=1848,
    )
    assert r_era["suitability"] == "reject_track_b_only"
    assert r_era["metrics"]["gate_failed"] == 1

    # 3. Gate 2: Dark TED-style stage void (median dark ratio > 0.72) -> reject_track_b_only
    dark_dir = tmp_path / "dark_stage"
    dark_frames = [np.full((240, 320, 3), 12, dtype=np.uint8) for _ in range(6)]
    _write_keyframes(dark_dir / "keyframes", dark_frames)
    r_dark = evaluate_media_reenactment_suitability(
        {
            "id": "M_dark",
            "kind": "experiment_footage",
            "title": "Original stage demonstration",
            "channel": "Archive Lab",
            "url": "https://www.youtube.com/watch?v=darkstage01",
        },
        analysis_dir=dark_dir,
    )
    assert r_dark["suitability"] == "reject_track_b_only"
    assert r_dark["metrics"]["gate_failed"] == 2

    # 4. Gate 3: Flat saturated 2D cartoon / slide deck -> reject_track_b_only
    flat_dir = tmp_path / "flat_cartoon"
    flat_frame = np.zeros((256, 320, 3), dtype=np.uint8)
    flat_frame[:, :] = (40, 190, 245)  # saturated flat orange-yellow slide background
    cv2.rectangle(flat_frame, (80, 60), (240, 190), (210, 80, 40), -1)
    _write_keyframes(flat_dir / "keyframes", [flat_frame for _ in range(6)])
    r_flat = evaluate_media_reenactment_suitability(
        {
            "id": "M_flat",
            "kind": "video",
            "title": "Experiment conditioning overview",
            "channel": "Psych Lab Notes",
            "url": "https://www.youtube.com/watch?v=flatslide01",
        },
        analysis_dir=flat_dir,
    )
    assert r_flat["suitability"] == "reject_track_b_only"
    assert r_flat["metrics"]["gate_failed"] == 3

    # 5. Gate 3 B&W Exemption: 1920s-1960s 16mm grayscale archival film -> suitable_track_a
    bw_dir = tmp_path / "bw_archival"
    bw_frames: list[np.ndarray] = []
    for i in range(6):
        g = np.full((256, 320), 178, dtype=np.float32)
        # Smooth plaster wall + lab bench + subtle 16mm grain (even with large smooth regions, B&W is exempt from Gate 3)
        g[150:, :] = 118.0
        g += rng.normal(0, 2.2, size=g.shape)
        g_u8 = np.clip(g, 0, 255).astype(np.uint8)
        bw_bgr = cv2.cvtColor(g_u8, cv2.COLOR_GRAY2BGR)
        cv2.rectangle(bw_bgr, (90 + i * 3, 95), (150 + i * 3, 210), (75, 75, 75), 2)
        bw_frames.append(bw_bgr)
    _write_keyframes(bw_dir / "keyframes", bw_frames)
    r_bw = evaluate_media_reenactment_suitability(
        {
            "id": "M_pavlov",
            "kind": "archive_film",
            "title": "1926 Pavlov conditioning archival 16mm film",
            "channel": "Historical Film Archive",
            "url": "https://www.youtube.com/watch?v=axJ9CwcH9WM",
            "duration_sec": 140.0,
        },
        analysis_dir=bw_dir,
        primary_year=1927,
    )
    assert r_bw["suitability"] == "suitable_track_a"
    assert r_bw["metrics"]["is_bw_archival"] is True

    # 6. Gate 4: Long unwindowed archival video (> 600s) -> needs_section_window with recommended_section
    r_long = evaluate_media_reenactment_suitability(
        {
            "id": "M_long",
            "kind": "archive_film",
            "title": "1961 Milgram archival experiment reel",
            "channel": "University Film Archive",
            "url": "https://www.youtube.com/watch?v=milgram1961a",
            "duration_sec": 1450.0,
            "timecodes": [
                {"t": "02:10", "what": "Experimenter seats participant before shock generator"},
                {"t": "02:42", "what": "Participant presses lever switch"},
            ],
        },
        analysis_dir=bw_dir,
        primary_year=1963,
    )
    assert r_long["suitability"] == "needs_section_window"
    assert r_long["recommended_section"] is not None
    assert "-" in r_long["recommended_section"]

    # 7. Gate 1: Oral-history numbered interview clip "(55/80)" -> reject_track_b_only
    r_oral = evaluate_media_reenactment_suitability(
        {
            "id": "M_oral",
            "kind": "video",
            "title": "Eric Kandel - Learning in Aplysia (55/80)",
            "channel": "University Science Stories",
            "url": "https://www.youtube.com/watch?v=kandel55of80",
            "duration_sec": 180.0,
        }
    )
    assert r_oral["suitability"] == "reject_track_b_only"
    assert r_oral["metrics"]["gate_failed"] == 1

    # 8. Gate 4: Non-archival continuous modern monologue (high words_per_sec >= 2.1, zero archival cues) -> reject_track_b_only
    mono_dir = tmp_path / "modern_monologue"
    color_studio_frames: list[np.ndarray] = []
    for _ in range(6):
        c_base = np.zeros((256, 320, 3), dtype=np.float32)
        c_base[:, :] = (135.0, 175.0, 215.0)  # warm studio wall (HSV S > 45 -> non-B&W)
        c_base[150:, :] = (85.0, 125.0, 165.0)  # wooden desk
        c_base += rng.normal(0, 9.5, size=c_base.shape)  # natural camera texture (passes Gate 3)
        color_studio_frames.append(np.clip(c_base, 0, 255).astype(np.uint8))
    _write_keyframes(mono_dir / "keyframes", color_studio_frames)
    (mono_dir / "transcript.txt").write_text(" ".join(["neuroscience"] * 300), encoding="utf-8")
    (mono_dir / "analysis.json").write_text(
        json.dumps({"duration_sec": 120.0, "section": "*00:00-02:00"}),
        encoding="utf-8",
    )
    r_mono = evaluate_media_reenactment_suitability(
        {
            "id": "M_mono",
            "kind": "video",
            "title": "Why people overestimate their skill",
            "channel": "Campus Studio",
            "url": "https://www.youtube.com/watch?v=monologue120",
            "duration_sec": 120.0,
        },
        analysis_dir=mono_dir,
        primary_year=1999,
    )
    assert r_mono["suitability"] == "reject_track_b_only"
    assert r_mono["metrics"]["gate_failed"] == 4



def test_sanitize_structural_frame_preserves_bw_corners_and_masks_colorful_decals() -> None:
    # A. Grayscale archival frame with clean architectural shelving in top-left corner
    bw = np.full((360, 480, 3), 205, dtype=np.uint8)
    cv2.rectangle(bw, (20, 20), (85, 85), (90, 90, 90), 3)  # low-chroma B&W shelf frame
    out_bw = sanitize_structural_frame_bgr(bw, poster_boxes_norm=None, target_w=720, target_h=1280)
    assert out_bw.shape == (1280, 720, 3)
    # Zero black bars at top/bottom
    assert float(np.mean(out_bw[:80, :])) > 120.0
    assert float(np.mean(out_bw[-80:, :])) > 120.0

    # B. Color frame with bright yellow cartoon decal in upper-left corner gets masked
    col = np.full((360, 480, 3), (210, 218, 222), dtype=np.uint8)
    col[10:90, 10:90] = (0, 235, 255)  # saturated yellow decal (BGR)
    out_col = sanitize_structural_frame_bgr(col, poster_boxes_norm=None, target_w=720, target_h=1280)
    assert out_col.shape == (1280, 720, 3)
    # Center 4:3 band starts around y ~ 160..1120; check upper-left of placed band has low yellow saturation
    hsv_out = cv2.cvtColor(out_col, cv2.COLOR_BGR2HSV)
    assert float(np.max(hsv_out[200:310, 15:110, 1])) < 60.0

    # C. Pillarboxed 4:3-in-16:9 archival frame with dark bottom bench shadow -> strips side bars & lifts floor
    pb = np.zeros((360, 640, 3), dtype=np.uint8)
    pb[:, 80:560] = 175
    pb[290:, 80:560] = 38  # dark shadow bench at bottom of 16mm frame
    out_pb = sanitize_structural_frame_bgr(pb, poster_boxes_norm=None, target_w=720, target_h=1280)
    assert out_pb.shape == (1280, 720, 3)
    assert float(np.mean(out_pb[500:700, :24])) > 140.0  # black side pillarboxes removed
    assert float(np.mean(out_pb[:64, :])) > 125.0
    assert float(np.mean(out_pb[-64:, :])) > 125.0



def test_reenactment_qa_uses_dynamic_personal_names_without_hardcoded_ainsworth(tmp_path: Path) -> None:
    proj = tmp_path / "reenact_pavlov_test"
    (proj / "02_script").mkdir(parents=True)
    (proj / "03_visuals" / "reference_images").mkdir(parents=True)
    (proj / "05_assembly").mkdir(parents=True)

    # Mentioning "Lisa" in a non-Ainsworth episode must NOT fail RQ3 when source_personal_names=["ivanpetrovich"]
    (proj / "02_script" / "script.json").write_text(
        json.dumps(
            {
                "sentences": [
                    "In 1927, researcher Lisa observed conditioned salivation inside the quiet laboratory chamber.",
                    "A metronome click preceded food delivery across repeated trials.",
                ]
            }
        ),
        encoding="utf-8",
    )
    edl = {
        "slug": "pavlov_dogs_conditioning",
        "source_reference_id": "https://www.youtube.com/watch?v=axJ9CwcH9WM",
        "source_video_id": "axJ9CwcH9WM",
        "shot_count": 3,
        "source_dhash_64_list": ["0000000000000000"],
        "source_5gram_sha256_list": [],
        "source_personal_names": ["ivanpetrovich"],
        "sanitization_verified": True,
        "shots": [
            {"shot_id": "S01", "start_sec": 0.0, "end_sec": 4.0, "duration_sec": 4.0, "camera_motion": "locked_tripod", "active_zones": ["center_action_zone"]},
            {"shot_id": "S02", "start_sec": 4.0, "end_sec": 8.0, "duration_sec": 4.0, "camera_motion": "locked_tripod", "active_zones": ["center_action_zone"]},
            {"shot_id": "S03", "start_sec": 8.0, "end_sec": 12.0, "duration_sec": 4.0, "camera_motion": "locked_tripod", "active_zones": ["center_action_zone"]},
        ],
    }
    (proj / "03_visuals" / "source_edl.json").write_text(json.dumps(edl), encoding="utf-8")

    # Create a high-key textured porcelain keyframe so dHash distance >= 18 from 0000000000000000
    kf = np.full((1280, 720, 3), 220, dtype=np.uint8)
    for row in range(0, 1280, 64):
        cv2.line(kf, (0, row), (720, (row + 180) % 1280), (145, 150, 155), 5)
    for col in range(0, 720, 90):
        cv2.circle(kf, (col, (col * 3) % 1200 + 40), 28, (130, 135, 140), -1)
    cv2.imwrite(str(proj / "03_visuals" / "reference_images" / "ref_s01_start.png"), kf)

    clips = []
    for i in range(1, 45):
        is_brain = i % 4 == 0  # 25% >= 20% brain ratio
        clips.append(
            {
                "index": i,
                "grammar": "porcelain_living_brain" if is_brain else "porcelain_fullbleed_world",
                "brain_mode": "frosted_glass_subcortical_xray" if is_brain else "",
                "cut_role": "mechanism" if is_brain else "experiment",
                "source_shot_id": "" if is_brain else "S01",
                "camera_motion": "locked_tripod",
                "active_zones": ["center_action_zone"],
                "action": "Porcelain researcher places an unmarked ceramic dish on the laboratory table.",
            }
        )
    (proj / "03_visuals" / "visual_plan.json").write_text(
        json.dumps({"style_profile": "porcelain_cinematic_v7", "clips": clips}),
        encoding="utf-8",
    )
    (proj / "03_visuals" / "flow_all_in_one_prompts.json").write_text(
        json.dumps({"prompts": [{"index": c["index"], "prompt": c["action"]} for c in clips]}),
        encoding="utf-8",
    )

    rep = validate_reenactment_non_infringement(proj, require_quarantine_purged=False)
    assert rep["passed"] is True, rep["failed_gates"]
    assert rep["gates"]["RQ3_zero_transcript_and_name_overlap"]["passed"] is True
    assert "qtsewnrhuhu" not in json.dumps(rep).lower()


def test_normalize_scene_prop_and_cast_lock_entries_dual_schema() -> None:
    p_item = normalize_scene_prop({"item": "Shock generator", "period_detail": "30-lever metal console", "physical_behavior": "switches click down"})
    p_name = normalize_scene_prop({"name": " Brass metronome ", "look": "pyramidal wood casing", "physical_behavior": "pendulum swings"})
    assert p_item is not None and p_item["name"] == "Shock generator"
    assert p_name is not None and p_name["name"] == "Brass metronome"

    # Schema v5 wardrobe dict remains supported
    v5_entries = cast_lock_entries(
        {"schema": 5, "cast": {"wardrobe": {"subject": "blue patient gown", "clinician": "white lab coat"}}}
    )
    v5_roles = {e["id"] for e in v5_entries}
    assert {"subject", "clinician"} <= v5_roles

    # Schema v7 flat multi-role cast extracts all roles (mother, stranger, subject, researcher)
    v7_entries = cast_lock_entries(
        {
            "schema": 7,
            "profile": "neuro_diorama",
            "style_profile": "porcelain_cinematic_v7",
            "cast": {
                "mother": "caregiver in sleeveless dark summer top with smooth featureless oval head",
                "stranger": "visitor in pale woven blouse with smooth featureless oval head",
                "subject": "toddler in pale cotton romper with smooth featureless oval head",
            },
        }
    )
    v7_roles = {e["id"] for e in v7_entries}
    assert v7_roles == {"mother", "stranger", "subject"}


def test_track_b_contract_compiler_and_reference_qa_defaults(tmp_path: Path) -> None:
    d_dir = tmp_path / "dossier_cotard"
    d_dir.mkdir()
    (d_dir / "03_visual_reference.json").write_text(
        json.dumps(
            {
                "scenes": [
                    {
                        "id": "S1",
                        "title": "1880 Paris neurological consultation room",
                        "iconic": True,
                        "era": "1880s Paris clinical study",
                        "wardrobe": {
                            "patient": "adult patient in a dark wool shawl over a pale linen dress",
                            "doctor": "neurologist in a tailored charcoal wool frock coat",
                        },
                        "lighting": "Bright diffused north-window daylight",
                        "layout": {
                            "room": "Bright white-plaster neurological examination room with tall shuttered windows and oak desk",
                            "positions": [
                                {"who": "subject", "where": "seated beside oak desk"},
                                {"who": "researcher", "where": "standing opposite desk"},
                            ],
                        },
                        "props": [
                            {
                                "item": "Leather case ledger",
                                "period_detail": "dark cloth-bound notebook with brass clasp",
                                "physical_behavior": "opens flat on desk",
                            },
                            {
                                "name": "Silver tuning fork",
                                "period_detail": "brushed steel examination fork",
                                "physical_behavior": "vibrates gently when tapped",
                            },
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    clips: list[dict] = []
    narrs: list[str] = []
    for idx in range(1, 21):
        act_id = min(6, ((idx - 1) // 4) + 1)
        if idx == 20:
            clips.append(
                {
                    "index": idx,
                    "act_id": 6,
                    "grammar": "porcelain_fullbleed_world",
                    "cut_role": "outro",
                    "action": "Quiet gallery-lit examination desk holds the closed bound notebook and tuning fork in stillness.",
                }
            )
        elif idx % 4 == 2:
            clips.append(
                {
                    "index": idx,
                    "act_id": act_id,
                    "grammar": "porcelain_hands_closeup",
                    "cut_role": "experiment",
                    "action": "Close-up of matte-white porcelain fingers tapping the brushed steel tuning fork against the oak desk edge.",
                    "scene_state": {
                        "location_id": "paris_exam_room",
                        "present_cast_start": ["subject", "researcher"],
                        "entering_cast": [],
                        "exiting_cast": [],
                        "present_cast_end": ["subject", "researcher"],
                    },
                }
            )
        elif idx % 4 == 3:
            clips.append(
                {
                    "index": idx,
                    "act_id": act_id,
                    "grammar": "porcelain_living_brain",
                    "brain_mode": "frosted_glass_subcortical_xray",
                    "cut_role": "mechanism",
                    "target_region": "insula and medial prefrontal cortex",
                    "action": "Inside a translucent frosted-porcelain cranium, crimson-red insular disconnection dims cyan-blue self-monitoring pathways.",
                }
            )
        elif idx == 4:
            clips.append(
                {
                    "index": idx,
                    "act_id": act_id,
                    "grammar": "porcelain_fullbleed_world",
                    "cut_role": "experiment",
                    "action": "Porcelain researcher steps back alone beside the oak desk after the patient exits.",
                    "scene_state": {
                        "location_id": "paris_exam_room",
                        "present_cast_start": ["researcher"],
                        "entering_cast": [],
                        "exiting_cast": [],
                        "present_cast_end": ["researcher"],
                    },
                }
            )
        else:
            clips.append(
                {
                    "index": idx,
                    "act_id": act_id,
                    "grammar": "porcelain_fullbleed_world",
                    "cut_role": "hook" if idx == 1 else "experiment",
                    "action": "Porcelain patient sits motionless across the oak examination desk while researcher opens a bound notebook.",
                    "scene_state": {
                        "location_id": "paris_exam_room",
                        "present_cast_start": ["subject", "researcher"],
                        "entering_cast": [],
                        "exiting_cast": [],
                        "present_cast_end": ["subject", "researcher"],
                    },
                }
            )
        narrs.append(f"Clinical observation sentence {idx} inside the neurological examination study.")

    plan = {
        "schema": 7,
        "schema_version": 7,
        "profile": "neuro_diorama",
        "style_profile": "porcelain_cinematic_v7",
        "visual_mode": "HYBRID",
        "dossier": "cotard_walking_corpse_syndrome",
        "reenactment_track": "track_b",
        "clips": clips,
    }

    populate_porcelain_reference_contract(plan, dossier_dir=d_dir)
    assert plan["strict_room_continuity"] is True
    assert "ledger" not in sanitize_porcelain_contract_text("Leather case ledger").lower()
    assert {"subject", "researcher"} <= set(plan["cast"].keys())

    # Selective binding: fullbleed + brain anchored; hands closeup + outro unanchored!
    assert plan["clips"][0].get("reference_image")
    assert not plan["clips"][1].get("reference_image")
    assert str(plan["clips"][2].get("reference_image")).endswith("ref_brain_master.png")
    assert plan["clips"][3].get("reference_image")
    assert not plan["clips"][19].get("reference_image")

    built = build_flow_prompts(plan, narrs)
    assert validate_scene_state_continuity(plan, built) == []

    # Direct write_flow_prompts_json into a draft dir containing visual_plan.json must NOT create nested 03_visuals
    draft_dir = tmp_path / "draft_dir"
    draft_dir.mkdir()
    (draft_dir / "visual_plan.json").write_text(json.dumps(plan), encoding="utf-8")
    out_prompts_p = write_flow_prompts_json(draft_dir, built)
    assert out_prompts_p == draft_dir / "flow_all_in_one_prompts.json"
    assert not (draft_dir / "03_visuals").exists()

    # Verify reference_image_specs + inspect_reference_image_pack require_review defaults
    proj_dir = tmp_path / "proj_cotard"
    (proj_dir / "03_visuals").mkdir(parents=True)
    (proj_dir / "02_script").mkdir(parents=True)
    (proj_dir / "03_visuals" / "visual_plan.json").write_text(json.dumps(plan), encoding="utf-8")
    (proj_dir / "02_script" / "script.json").write_text(json.dumps({"narrations": narrs}), encoding="utf-8")

    specs_payload = build_reference_image_specs(plan, narrs)
    all_specs = specs_payload["all_specs"]
    assert 6 <= len(all_specs) <= 9
    write_reference_image_specs(proj_dir, specs_payload)

    from pipeline.reference_image_qa import auto_populate_reference_semantic_review

    # Synthesize valid distinct 9:16 high-key textured PNGs and register provenance without semantic review file
    ref_dir = proj_dir / "03_visuals" / "reference_images"
    ref_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(42)
    for idx_s, sp in enumerate(all_specs):
        y_grid = np.linspace(115, 180, 1280, dtype=np.float32)[:, None, None]
        noise = cv2.GaussianBlur(rng.normal(0, 26, (1280, 720, 3)).astype(np.float32), (3, 3), 0.9)
        frame = np.clip(y_grid + noise, 35, 245).astype(np.uint8)
        for gx in range(80, 660, 48):
            cv2.line(frame, (gx, 90), (gx, 1180), (85, 85, 85), 2)
        for gy in range(100, 1180, 52):
            cv2.line(frame, (60, gy), (660, gy), (90, 90, 90), 2)
        frame[:70, :] = 145
        frame[1210:, :] = 145
        cx = 90 + idx_s * 34
        cy = 230 + idx_s * 42
        cv2.rectangle(frame, (cx, cy), (cx + 180 + (idx_s % 3) * 25, cy + 410), (235, 235, 235), -1)
        cv2.circle(frame, (cx + 90, cy - 60), 48 + idx_s * 2, (240, 240, 240), -1)
        prng = np.random.default_rng(2000 + idx_s)
        for _ in range(6):
            x0, y0 = int(prng.integers(60, 540)), int(prng.integers(120, 1020))
            shade = int(prng.integers(45, 125))
            cv2.rectangle(frame, (x0, y0), (x0 + int(prng.integers(45, 140)), y0 + int(prng.integers(45, 160))), (shade,) * 3, -1)
        out_png = ref_dir / sp["filename"]
        cv2.imwrite(str(out_png), frame)
        register_reference_image(proj_dir, sp["filename"], "flow_image_generation")

    # Default on neuro_diorama: require_review defaults to False -> pre_generation_ready is True on CV pass!
    rep_auto = inspect_reference_image_pack(proj_dir)
    assert rep_auto["cv_all_passed"] is True
    assert rep_auto["pre_generation_ready"] is True

    # Explicit require_review=True without review file -> cv_pre_generation_ready True, pre_generation_ready False
    rep_strict = inspect_reference_image_pack(proj_dir, require_review=True)
    assert rep_strict["cv_pre_generation_ready"] is True
    assert rep_strict["pre_generation_ready"] is False

    # Auto-populating SHA-256-bound semantic review satisfies strict require_review=True
    auto_populate_reference_semantic_review(proj_dir)
    rep_reviewed = inspect_reference_image_pack(proj_dir, require_review=True)
    assert rep_reviewed["pre_generation_ready"] is True
