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

    # Selective binding: fullbleed + brain anchored; ALL hands closeup (even 2nd/3rd/4th) + outro unanchored!
    assert plan["clips"][0].get("reference_image")
    for hc_idx in (1, 5, 9, 13, 17):
        assert plan["clips"][hc_idx]["grammar"] == "porcelain_hands_closeup"
        assert not plan["clips"][hc_idx].get("reference_image"), f"Hands closeup clip {hc_idx + 1} must not be wide-locked"
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
    write_flow_prompts_json(proj_dir, built)

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


def test_adversarial_suitability_bw_vs_powerpoint_and_silent_subject(tmp_path: Path) -> None:
    from pipeline.research_dossier import audit_dossier_media_suitability

    rng = np.random.default_rng(99)

    # 1. Course code PowerPoint lecture ("PSY 2510 ...") -> rejected at Gate 1
    r_course = evaluate_media_reenactment_suitability(
        {
            "id": "M_course",
            "kind": "documentary",
            "title": "PSY 2510 Social Psychology: Self-Perception & Social Comparison",
            "channel": "University Media",
            "url": "https://www.youtube.com/watch?v=course2510ab",
        }
    )
    assert r_course["suitability"] == "reject_track_b_only"
    assert r_course["metrics"]["gate_failed"] == 1

    # 2. Frozen static book cover / slide (zero inter-frame motion) -> rejected at Gate 3
    static_dir = tmp_path / "static_cover"
    cover_frm = np.clip(160 + rng.normal(0, 18, (240, 320, 3)), 0, 255).astype(np.uint8)
    _write_keyframes(static_dir / "keyframes", [cover_frm.copy() for _ in range(6)])
    r_static = evaluate_media_reenactment_suitability(
        {
            "id": "M_static",
            "kind": "archive_film",
            "title": "1953 Dichotic Listening Recording",
            "channel": "Audio Archive",
            "url": "https://www.youtube.com/watch?v=staticcov01",
        },
        analysis_dir=static_dir,
    )
    assert r_static["suitability"] == "reject_track_b_only"
    assert r_static["metrics"]["gate_failed"] == 3

    # 3. Color speaker/slide on mostly grey wall (med_gray_sat >= 0.82, but p90(HSV S) > 80 and flat > 0.62) -> NOT B&W!
    fake_bw_dir = tmp_path / "color_on_grey_wall"
    fake_bw_frames: list[np.ndarray] = []
    for i in range(6):
        frm = np.full((256, 320, 3), 235, dtype=np.uint8)  # 85% flat white slide background -> med_gray_sat > 0.82
        # Saturated color corner inset (e.g. university logo + color lecturer shirt, >12% area -> p90(S) > 100)
        frm[150 : 245, 20 + i * 8 : 135 + i * 8] = (25, 95, 235)
        fake_bw_frames.append(frm)
    _write_keyframes(fake_bw_dir / "keyframes", fake_bw_frames)
    r_fake_bw = evaluate_media_reenactment_suitability(
        {
            "id": "M_fake_bw",
            "kind": "documentary",
            "title": "Memory Encoding and Retrieval pt1",
            "channel": "Campus Channel",
            "url": "https://www.youtube.com/watch?v=fakebwslide",
        },
        analysis_dir=fake_bw_dir,
    )
    assert r_fake_bw["suitability"] == "reject_track_b_only"
    assert r_fake_bw["metrics"]["is_bw_archival"] is False
    assert r_fake_bw["metrics"]["gate_failed"] == 3

    # 4. Mixed color host + B&W 16mm archival segment -> needs_section_window with clean MM:SS-MM:SS (no leading '*')
    mixed_dir = tmp_path / "mixed_host_bw"
    mixed_frames: list[np.ndarray] = []
    for i in range(6):
        g = np.clip(165 + rng.normal(0, 14, (256, 320)), 0, 255).astype(np.uint8)
        bgr = cv2.cvtColor(g, cv2.COLOR_GRAY2BGR)
        if i < 2:
            bgr[:, :] = np.clip(np.array([70, 140, 225], dtype=np.float32) + rng.normal(0, 14, (256, 320, 3)), 0, 255).astype(np.uint8)
        cv2.rectangle(bgr, (40 + i * 15, 70), (140 + i * 15, 200), (60, 60, 60), 3)
        mixed_frames.append(bgr)
    _write_keyframes(mixed_dir / "keyframes", mixed_frames)
    r_mixed = evaluate_media_reenactment_suitability(
        {
            "id": "M_mixed",
            "kind": "documentary",
            "title": "1959 Cognitive Dissonance archival segment",
            "channel": "Archive Series",
            "url": "https://www.youtube.com/watch?v=mixed1959ab",
            "duration_sec": 160.0,
            "timecodes": [{"t": "*00:35-01:25", "what": "Participant turns wooden pegs on pegboard"}],
        },
        analysis_dir=mixed_dir,
    )
    assert r_mixed["suitability"] == "needs_section_window"
    assert r_mixed["recommended_section"] is not None
    assert not r_mixed["recommended_section"].startswith("*")

    # 5. Dossier audit prefers keyframe-verified M1 (needs_section_window) over unanalyzed M2 (0 keyframes)
    dos_dir = tmp_path / "braingate_dossier"
    dos_dir.mkdir()
    (dos_dir / "dossier.json").write_text(json.dumps({"slug": "braingate_dossier", "primary_case": {"year": 2012}}), encoding="utf-8")
    (dos_dir / "01_sources.json").write_text(json.dumps({"sources": []}), encoding="utf-8")
    m1_dir = dos_dir / "media" / "M1"
    _write_keyframes(m1_dir / "keyframes", mixed_frames)
    (dos_dir / "04_media_refs.json").write_text(
        json.dumps(
            {
                "media": [
                    {
                        "id": "M1",
                        "kind": "video",
                        "title": "BrainGate clinical trial robotic arm - Nature Video",
                        "channel": "nature video",
                        "url": "https://www.youtube.com/watch?v=ogBX18maUiM",
                        "duration_sec": 260,
                        "analysis": {"local_dir": "media/M1"},
                        "timecodes": [{"t": "03:31-04:16", "what": "Participant guides robotic arm to lift thermos"}],
                    },
                    {
                        "id": "M2",
                        "kind": "video",
                        "title": "BrainGate clinical trial demonstration (2012)",
                        "channel": "University",
                        "url": "https://www.youtube.com/watch?v=unanalyzed99",
                        "timecodes": [{"t": "00:10-00:55", "what": "Robotic arm reach"}],
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    audit_res = audit_dossier_media_suitability(dos_dir, write_back=True)
    assert audit_res["reenactment_track"] == "track_a"
    assert audit_res["primary_track_a_media"]["id"] == "M1"
    assert audit_res["primary_track_a_media"]["has_keyframes_on_disk"] is True


def test_wardrobe_semicolon_classifier_plaque_sanitizer_and_track_a_rq5_wiring(tmp_path: Path, monkeypatch) -> None:
    from pipeline.depiction_rules import PromptComposer
    from pipeline.porcelain_anchor_pack import ensure_porcelain_reference_pack
    from pipeline.source_reenactment import _parse_section_window

    # 1. Anti-plaque sanitizer strips quoted chart titles & percentages while preserving word-internal apostrophes
    cleaned = sanitize_porcelain_contract_text(
        "1880 Case Subtype '86% Organ Negation | 69% Immortality' Chart (86% vs 14%) on subject's oak table"
    )
    assert "86%" not in cleaned
    assert "organ negation" not in cleaned.lower()
    assert "chart" not in cleaned.lower()
    assert "subject's" in cleaned

    # 2. Brain still prompt enforces featureless blank oval porcelain bust without sculpted eyes/nose/mouth
    brain_prompt = PromptComposer.compose_brain_still_prompt("Crimson-red insula disconnection dims cyan-blue cortex.")
    assert "zero eyes, zero nose, zero mouth, zero ears" in brain_prompt
    assert "dynamic camera progression" not in brain_prompt

    # 3. Semicolon wardrobe parsing: preserves "St. Louis", strips "Dr. Jules Cotard" / "Mademoiselle X", excludes animal sculptures
    d_cotard = tmp_path / "cotard_semicolon"
    d_cotard.mkdir()
    (d_cotard / "03_visual_reference.json").write_text(
        json.dumps(
            {
                "scenes": [
                    {
                        "id": "S1",
                        "iconic": True,
                        "wardrobe": (
                            "Dr. Jules Cotard in a dark charcoal 1880 French physician frock coat and waistcoat; "
                            "Mademoiselle X in a muted slate-grey high-collared 1880 French wool dress"
                        ),
                        "layout": {"description": "1880 Paris neurological ward"},
                        "props": [],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    plan_c = {
        "schema": 7,
        "profile": "neuro_diorama",
        "style_profile": "porcelain_cinematic_v7",
        "visual_mode": "HYBRID",
        "reenactment_track": "track_b",
        "clips": [
            {
                "index": 1,
                "grammar": "porcelain_fullbleed_world",
                "cut_role": "hook",
                "action": "Patient sits across the desk.",
                "scene_state": {"location_id": "ward", "present_cast_start": ["subject", "researcher"], "present_cast_end": ["subject", "researcher"]},
            }
        ],
    }
    populate_porcelain_reference_contract(plan_c, dossier_dir=d_cotard)
    assert "wool dress" in plan_c["cast"]["subject"]
    assert "frock coat" in plan_c["cast"]["researcher"]
    assert "cotard" not in plan_c["cast"]["researcher"].lower()
    assert "mademoiselle" not in plan_c["cast"]["subject"].lower()
    assert "shoes" in plan_c["cast"]["subject"].lower()
    assert "shoes" in plan_c["cast"]["researcher"].lower()

    d_animal = tmp_path / "st_louis_dog"
    d_animal.mkdir()
    (d_animal / "03_visual_reference.json").write_text(
        json.dumps(
            {
                "scenes": [
                    {
                        "id": "S1",
                        "iconic": True,
                        "wardrobe": (
                            "St. Louis research team in crisp white clinical coats over slate shirts; "
                            "animal subject strictly rendered as a clean articulated matte-white porcelain dog sculpture"
                        ),
                        "layout": {"description": "1967 conditioning chamber"},
                        "props": [{"name": " oak shuttle box "}],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    plan_a = {
        "schema": 7,
        "profile": "neuro_diorama",
        "style_profile": "porcelain_cinematic_v7",
        "visual_mode": "HYBRID",
        "reenactment_track": "track_a",
        "clips": [
            {
                "index": i,
                "grammar": "porcelain_living_brain" if i % 4 == 0 else "porcelain_fullbleed_world",
                "brain_mode": "frosted_glass_subcortical_xray" if i % 4 == 0 else "",
                "cut_role": "outro" if i == 44 else ("mechanism" if i % 4 == 0 else "experiment"),
                "action": "Porcelain investigator observes the chamber.",
                "scene_state": {"location_id": "chamber", "present_cast_start": ["subject", "researcher"], "present_cast_end": ["subject", "researcher"]},
            }
            for i in range(1, 45)
        ],
    }
    populate_porcelain_reference_contract(plan_a, dossier_dir=d_animal)
    assert "porcelain dog" not in plan_a["cast"]["subject"].lower()
    assert "porcelain dog" not in plan_a["cast"]["researcher"].lower()
    assert any("porcelain dog" in p.lower() for p in plan_a["environment_props"])
    assert all(str(a["scene_id"]).startswith("S") for a in plan_a["reference_anchors"])

    # Verify Track A plan compiled by populate_porcelain_reference_contract passes RQ5 (>= 0.85 blocking alignment)!
    proj_ta = tmp_path / "proj_track_a"
    (proj_ta / "02_script").mkdir(parents=True)
    (proj_ta / "03_visuals" / "reference_images").mkdir(parents=True)
    (proj_ta / "05_assembly").mkdir(parents=True)
    (proj_ta / "02_script" / "script.json").write_text(json.dumps({"sentences": ["Sentence one."] * 44}), encoding="utf-8")
    edl_ta = {
        "slug": "st_louis_dog",
        "source_reference_id": "https://www.youtube.com/watch?v=axJ9CwcH9WM",
        "source_video_id": "axJ9CwcH9WM",
        "shot_count": 4,
        "source_dhash_64_list": ["aa55aa55aa55aa55"],
        "source_5gram_sha256_list": [],
        "source_personal_names": [],
        "sanitization_verified": True,
        "shots": [
            {"shot_id": f"S0{k}", "start_sec": (k - 1) * 4.0, "end_sec": k * 4.0, "duration_sec": 4.0, "camera_motion": "locked_tripod", "active_zones": ["center_action_zone"]}
            for k in range(1, 5)
        ],
    }
    (proj_ta / "03_visuals" / "source_edl.json").write_text(json.dumps(edl_ta), encoding="utf-8")
    (proj_ta / "03_visuals" / "visual_plan.json").write_text(json.dumps(plan_a), encoding="utf-8")
    (proj_ta / "03_visuals" / "flow_all_in_one_prompts.json").write_text(
        json.dumps({"prompts": [{"index": c["index"], "prompt": c["action"]} for c in plan_a["clips"]]}),
        encoding="utf-8",
    )
    kf = np.full((1280, 720, 3), 220, dtype=np.uint8)
    cv2.line(kf, (0, 100), (720, 900), (130, 135, 140), 8)
    cv2.circle(kf, (360, 640), 90, (125, 130, 135), -1)
    cv2.imwrite(str(proj_ta / "03_visuals" / "reference_images" / "ref_anchor_01.png"), kf)
    rq_rep = validate_reenactment_non_infringement(proj_ta, require_quarantine_purged=False)
    assert rq_rep["passed"] is True, rq_rep["failed_gates"]
    assert rq_rep["gates"]["RQ5_brain_intercut_and_blocking_alignment"]["blocking_alignment_ratio"] == 1.0

    # 4. Quarantine purge guarantee even when extract_source_edl / translate raises mid-way
    assert _parse_section_window("*03:31-04:16") == (211.0, 256.0)
    lt_frame = np.full((360, 480, 3), 185, dtype=np.uint8)
    lt_frame[295:345, 55:425] = 35
    for tx in range(70, 405, 14):
        cv2.rectangle(lt_frame, (tx, 308), (tx + 8, 332), (248, 248, 248), -1)
    san_lt = sanitize_structural_frame_bgr(lt_frame)
    assert san_lt.shape == (1280, 720, 3)

    slug_q = "test_quarantine_leak_guard_slug"
    q_leak_dir = Path("/tmp/aab_reenact") / slug_q
    (d_animal / "04_media_refs.json").write_text(
        json.dumps(
            {
                "suitability_schema_version": 2,
                "reenactment_track": "track_a",
                "track_subtier": "A1a_ready_keyframes",
                "media": [
                    {
                        "id": "M1",
                        "kind": "archive_film",
                        "title": "1927 Pavlov archival film",
                        "url": "https://www.youtube.com/watch?v=axJ9CwcH9WM",
                        "reenactment_suitability": "suitable_track_a",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    plan_a["dossier_slug"] = slug_q
    (proj_ta / "03_visuals" / "visual_plan.json").write_text(json.dumps(plan_a), encoding="utf-8")

    def _boom_extract(*_args, **_kwargs):
        q_leak_dir.mkdir(parents=True, exist_ok=True)
        (q_leak_dir / "source.mp4").write_bytes(b"quarantined_bytes")
        raise RuntimeError("simulated network abort mid-download")

    def _boom_translate(*_args, **_kwargs):
        raise RuntimeError("simulated browser abort")

    import pipeline.source_reenactment as sr_mod

    monkeypatch.setattr(sr_mod, "extract_source_edl", _boom_extract)
    monkeypatch.setattr(sr_mod, "translate_porcelain_keyframes", _boom_translate)
    try:
        ensure_porcelain_reference_pack(proj_ta, dossier_dir=d_animal, force=True)
    except RuntimeError:
        pass
    assert not q_leak_dir.exists(), "Quarantine directory /tmp/aab_reenact/<slug> must ALWAYS be purged on exception!"

