"""Unit and adversarial edge-case tests for Per-Video/Per-Clip QA Contract, Reference QA fixes, and Deliverable Overwatch."""
from __future__ import annotations

import json
import os
import subprocess
import time
import wave
from pathlib import Path

import cv2
import imageio_ffmpeg
import numpy as np

from pipeline.clip_qa_contract import (
    analyze_brain_anatomy_frame,
    compile_clip_qa_contract,
    compute_camera_compensated_motion,
    compute_sha256,
    compute_spatial_and_palette_continuity,
    detect_forbidden_scene_hallucinations,
    detect_r53_neon_particles,
    is_clip_qa_report_fresh,
    verify_clips_against_contract,
)
from pipeline.deliverable_overwatch import (
    render_overwatch_markdown,
    verify_phineas_gage_deliverable,
    verify_standalone_brain_deliverable,
)
from pipeline.reference_image_qa import (
    build_reference_image_specs,
    inspect_reference_image_pack,
    is_reference_qa_report_fresh,
    register_reference_image,
    validate_semantic_review,
    write_semantic_review_template,
)
from pipeline.scene_blueprint import still_frame_prompt
from pipeline.video_autopsy import VideoAutopsyEngine

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()


def _write_mp4_from_frames(
    out_path: Path,
    frames: list[np.ndarray],
    fps: int = 12,
    pad_min_bytes: int = 1_050_000,
) -> Path:
    """Encodes BGR frames to an H.264 9:16 MP4 exceeding MIN_CLIP_SIZE_BYTES (1 MB) for deterministic CV tests."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    h, w = frames[0].shape[:2]
    cmd = [
        FFMPEG,
        "-y",
        "-loglevel",
        "error",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "bgr24",
        "-s",
        f"{w}x{h}",
        "-r",
        str(fps),
        "-i",
        "-",
        "-c:v",
        "libx264",
        "-preset",
        "ultrafast",
        "-crf",
        "6",
        "-pix_fmt",
        "yuv420p",
        str(out_path),
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    assert proc.stdin is not None
    for frm in frames:
        proc.stdin.write(frm.tobytes())
    proc.stdin.close()
    rc = proc.wait()
    assert rc == 0 and out_path.exists()
    # Pad trailing MP4 free/zero box only if ultra-clean synthetic frames compressed below 260 KB
    cur_size = out_path.stat().st_size
    if cur_size < pad_min_bytes:
        extra = pad_min_bytes - cur_size + 8
        # Valid MP4 `free` atom: 4-byte big-endian length + b"free" + payload
        atom = int(extra).to_bytes(4, "big") + b"free" + (b"\x00" * (extra - 8))
        with open(out_path, "ab") as f:
            f.write(atom)
    return out_path


def _make_left_porcelain_bust_frame(
    w: int = 360,
    h: int = 640,
    with_crimson_left_eye: bool = False,
    with_green_particles: bool = False,
    coronal_symmetric: bool = False,
    face_right: bool = False,
    shift_x: int = 0,
    pulse: int = 0,
) -> np.ndarray:
    """Synthesizes a 9:16 dark-slate porcelain brain bust frame with controllable anatomy/defects."""
    rng = np.random.default_rng(42)
    # Subtle fine grain so libx264 preserves realistic texture
    img = np.full((h, w, 3), (36, 28, 24), dtype=np.uint8)
    noise = rng.integers(-3, 4, size=(h, w, 1), dtype=np.int16)
    img = np.clip(img.astype(np.int16) + noise, 0, 255).astype(np.uint8)

    if coronal_symmetric:
        # Symmetric front-facing oval head with bilateral eyes and central-bottom crimson lesion
        cv2.ellipse(img, (w // 2, int(h * 0.44)), (int(w * 0.30), int(h * 0.24)), 0, 0, 360, (226, 226, 228), -1)
        cv2.rectangle(img, (int(w * 0.36), int(h * 0.65)), (int(w * 0.64), int(h * 0.86)), (215, 215, 218), -1)
        cv2.circle(img, (int(w * 0.40), int(h * 0.44)), 14, (90, 90, 95), -1)
        cv2.circle(img, (int(w * 0.60), int(h * 0.44)), 14, (90, 90, 95), -1)
        if with_crimson_left_eye:
            # Defective central-posterior / bottom lesion outside anterior ROI
            cv2.circle(img, (int(w * 0.80), int(h * 0.60)), 22, (35, 30, 195), -1)
        return img

    cx = w // 2 + 12 + shift_x
    # Main cranium & shoulders (smooth bright-white porcelain forehead on viewer-left, gyral cutaway behind it)
    cv2.ellipse(img, (cx, int(h * 0.42)), (int(w * 0.27), int(h * 0.22)), 0, 0, 360, (232, 232, 234), -1)
    cv2.rectangle(img, (cx - int(w * 0.14), int(h * 0.60)), (cx + int(w * 0.18), int(h * 0.86)), (216, 216, 220), -1)
    # Carve anterior facial indentation below brow on viewer-left so profile clearly faces left
    cv2.rectangle(img, (0, int(h * 0.49)), (cx - int(w * 0.16), int(h * 0.78)), (36, 28, 24), -1)
    # Recessed cutaway cavity posterior to the smooth white left forehead (viewer-center-right of cranium)
    cv2.ellipse(img, (cx + int(w * 0.04), int(h * 0.37)), (int(w * 0.17), int(h * 0.13)), 0, 0, 360, (175, 178, 182), -1)
    for k in range(6):
        yk = int(h * 0.28) + k * 14
        cv2.line(img, (cx - int(w * 0.08), yk), (cx + int(w * 0.17), yk + 5), (105, 110, 118), 2)

    # Warm champagne-amber tract glow in anterior left prefrontal ROI behind left eye
    amber_v = min(255, 210 + pulse)
    cv2.ellipse(
        img,
        (cx - int(w * 0.06), int(h * 0.38)),
        (24, 15),
        -20,
        0,
        360,
        (95, min(255, 185 + pulse // 2), amber_v),
        -1,
    )
    if with_crimson_left_eye:
        # True crimson lesion strictly behind left eye in anterior ROI
        cv2.circle(img, (cx - int(w * 0.09), int(h * 0.40)), 18, (36, 32, 205), -1)

    if with_green_particles:
        for px, py in ((cx - 25, int(h * 0.32)), (cx - 4, int(h * 0.29)), (cx + 18, int(h * 0.35)), (cx - 12, int(h * 0.43)), (cx + 10, int(h * 0.41))):
            cv2.circle(img, (px, py), 3, (90, 245, 35), -1)

    if face_right:
        img = cv2.flip(img, 1)

    return img


def _make_hybrid_gage_plan() -> tuple[dict, list[str]]:
    narrations = [
        "In 1848 Phineas Gage packed blasting powder with an iron rod when a spark drove it under his left cheekbone.",
        "It flew in under his left cheekbone and out his skull, yet minutes later Gage rode upright in an ox cart.",
        "Months later in the railroad office, bosses refused his foreman job back because his impulse brake was gone.",
        "Before the blast, the intact left prefrontal cortex behind his left eye kept sudden impulses in check.",
        "Why could a man walk and speak normally right after an iron bar tore through the front of his brain?",
    ]
    plan = {
        "schema": 5,
        "dossier": "phineas_gage_iron_rod",
        "visual_mode": "HYBRID",
        "aspect": "9:16",
        "clip_count": 5,
        "target_region": "ventromedial_prefrontal_cortex",
        "real_environment": "an 1848 Vermont granite railroad cut",
        "cast": {
            "subject": "gage",
            "wardrobe": {
                "gage": "1840s white linen shirtsleeves and dark wool waistcoat",
                "boss": "dark frock coat behind an oak ledger desk",
            },
        },
        "must_have_scenes": [
            {
                "id": "S1",
                "title": "Rock Cut Blast",
                "iconic": True,
                "required_tokens": ["iron rod", "black powder"],
                "key_visual": {
                    "description": "the pointed iron rod shoots upward under his left cheekbone and out the top of his skull",
                    "must_show": ["iron|rod", "cheekbone|cheek", "skull|cranium"],
                },
            },
            {"id": "S2", "title": "Ox Cart Ride", "iconic": False},
            {"id": "S3", "title": "Railroad Office", "iconic": False},
        ],
        "brain_link": {
            "mechanism": {
                "canonical_region": "left_orbitofrontal_and_ventromedial_prefrontal_cortex",
                "state": "intact warm champagne-amber white-matter tracts behind the left eye socket, zero red lesion",
                "story_cue": "directly behind his left eye keeping impulses calm",
            },
            "conclusion": {
                "canonical_region": "left_orbitofrontal_and_ventromedial_prefrontal_cortex",
                "state": "diagonal crimson fracture path piercing behind the left eye socket through left prefrontal wiring",
                "story_cue": "iron rod trajectory behind his left eye",
            },
        },
        "shots": {
            "setup": {
                "scene_id": "S1",
                "setting": "real_env",
                "camera": "Medium vertical shot slowly pushing in",
                "environment": "1848 granite railroad rock cut in daylight",
                "action": "Porcelain Gage kneels beside the drilled rock hole, gripping and tamping a 1.1-meter tapered iron rod, then turns his head back",
                "prop_change": "A bright spark ignites black powder and the iron rod shoots upward under his left cheekbone and out his skull",
                "reaction": "Crew mannequins flinch back from the smoke",
            },
            "crisis": {
                "scene_id": "S2",
                "setting": "real_env",
                "camera": "Close view on left cheekbone wound then smoothly pulls back to wide ox cart",
                "environment": "Dirt road beside the granite quarry with a wooden ox cart",
                "action": "Porcelain Gage holds a cloth to his left cheekbone wound, then sits upright in the moving ox cart talking",
                "prop_change": "The wooden ox cart wheels roll forward along the rutted road",
                "reaction": "The driver listens in disbelief",
            },
            "pivot": {
                "scene_id": "S3",
                "setting": "real_env",
                "camera": "Tracking arc across the oak office desk",
                "environment": "1849 railroad company wood-paneled office",
                "action": "Porcelain Gage steps up holding his iron rod while the superintendent shakes his head",
                "prop_change": "The superintendent closes the heavy leather payroll ledger",
                "reaction": "A clerk steps backward",
            },
            "mechanism": {
                "scene_id": "BRAIN",
                "setting": "brain_void",
                "camera": "Slow orbit around three-quarter left porcelain bust cutaway",
                "action": "Warm champagne-amber signal flows smoothly behind the left eye socket with zero red damage",
                "prop_change": "Prefrontal fibers glow steadily",
                "reaction": "Calm regulated pathway",
            },
            "conclusion": {
                "scene_id": "BRAIN",
                "setting": "drill_down",
                "camera": "Push in toward the left orbitofrontal cutaway behind the left eye",
                "action": "Diagonal crimson fracture behind the left eye severs the left prefrontal tract",
                "prop_change": "Downstream frontal fibers dim above the crimson lesion",
                "reaction": "Severed impulse brake",
            },
        },
    }
    return plan, narrations


def test_still_frame_prompt_preserves_opening_props_without_temporal_sequence() -> None:
    plan, _ = _make_hybrid_gage_plan()
    start_p = still_frame_prompt(plan, "setup", "start")
    assert "still photograph" in start_p
    assert "gripping and tamping a 1.1-meter tapered iron rod" in start_p
    assert "then turns his head" not in start_p
    assert "pushing in" not in start_p


def test_compile_clip_qa_contract_enforces_concrete_entities_and_left_eye_anatomy(tmp_path: Path) -> None:
    plan, narrations = _make_hybrid_gage_plan()
    (tmp_path / "02_script").mkdir(parents=True)
    (tmp_path / "03_visuals").mkdir(parents=True)
    (tmp_path / "02_script" / "script.json").write_text(json.dumps({"clip_narrations": narrations}), encoding="utf-8")
    (tmp_path / "03_visuals" / "visual_plan.json").write_text(json.dumps(plan), encoding="utf-8")

    contract = compile_clip_qa_contract(tmp_path, save=True)
    assert (tmp_path / "03_visuals" / "clip_qa_contract.json").exists()
    assert contract["has_brain_clips"] is True
    assert contract["shared_brain_master_anchor"] == "ref_brain_master"
    assert contract["cross_brain_continuity_contract"]["enabled"] is True
    assert contract["cross_brain_continuity_contract"]["brain_clip_numbers"] == [4, 5]

    for c in contract["clips"]:
        assert c["required_entities"], f"clip {c['clip_number']} missing required_entities"
        assert all(ent not in {"S1", "S2", "S3", "BRAIN"} for ent in c["required_entities"])

    c2 = contract["clips"][1]
    assert c2["narration_grounding"]["requires_scale_pullback"] is True
    assert c2["conditioning_contract"]["aggregation_mode"] == "pullback_windowed"

    c4_anat = contract["clips"][3]["anatomical_contract"]
    c5_anat = contract["clips"][4]["anatomical_contract"]
    assert c4_anat["hemisphere"] == "left"
    assert c4_anat["expected_facing"] == "left"
    assert c4_anat["forbid_symmetric_coronal"] is True
    assert c4_anat["forbid_crimson_lesion"] is True
    assert c5_anat["require_crimson_lesion"] is True


def test_reference_qa_hybrid_brain_master_5pt_morph_and_semantic_antiboilerplate(tmp_path: Path) -> None:
    plan, narrations = _make_hybrid_gage_plan()
    (tmp_path / "02_script").mkdir(parents=True)
    (tmp_path / "03_visuals" / "reference_images").mkdir(parents=True)
    (tmp_path / "02_script" / "script.json").write_text(json.dumps({"clip_narrations": narrations}), encoding="utf-8")
    (tmp_path / "03_visuals" / "visual_plan.json").write_text(json.dumps(plan), encoding="utf-8")

    specs = build_reference_image_specs(plan, narrations)
    master_ids = [s["ref_id"] for s in specs["master_anchors"]]
    assert "ref_brain_master" in master_ids
    brain_clip_specs = [s for s in specs["clip_anchors"] if s["setting"] in ("brain_void", "drill_down")]
    assert len(brain_clip_specs) == 2 and all(s["conditioned_on"] == ["ref_brain_master"] for s in brain_clip_specs)
    assert all(m not in {"S1", "S2", "S3", "BRAIN"} for s in specs["all_specs"] for m in s["must_include"])

    # Pre-generation pack check: with zero native clips on disk, Q10 continuity must be None (not fake 1.0)
    pre_rep = inspect_reference_image_pack(tmp_path, save_report=True)
    q10 = pre_rep["axes_summary"]["Q10_shot_diversity_and_video_anchor_sync"]
    assert q10["video_continuity_checked"] is False
    assert q10["mean_clip_to_ref_continuity"] is None

    # Semantic review SHA-256 invalidation + anti-boilerplate note check
    five_specs = specs["all_specs"][:5]
    ref_dir = tmp_path / "03_visuals" / "reference_images"
    for s in five_specs:
        img = _make_left_porcelain_bust_frame(360, 640)
        cv2.imwrite(str(ref_dir / s["filename"]), img)
        register_reference_image(tmp_path, s["filename"], "gemini_image_generation")

    sem_path = write_semantic_review_template(tmp_path, five_specs)
    sem_data = json.loads(sem_path.read_text(encoding="utf-8"))
    for s in five_specs:
        rid = s["ref_id"]
        sem_data["images"][rid]["checks"] = {k: True for k in sem_data["images"][rid]["checks"]}
        sem_data["images"][rid]["note"] = "Identical copy-pasted rubber-stamp note"
    sem_path.write_text(json.dumps(sem_data), encoding="utf-8")

    res_boiler = validate_semantic_review(tmp_path, five_specs)
    assert len(res_boiler["boilerplate_note_ids"]) == 5
    assert len(res_boiler["failed"]) == 5

    # Give distinct notes, verify pass, then mutate 1 image on disk -> must become stale/pending!
    for idx, s in enumerate(five_specs):
        sem_data["images"][s["ref_id"]]["note"] = f"Verified specific visual landmarks for {s['ref_id']} #{idx}"
    sem_path.write_text(json.dumps(sem_data), encoding="utf-8")
    res_ok = validate_semantic_review(tmp_path, five_specs)
    assert res_ok["complete"] is True and not res_ok["failed"]

    mutated_png = ref_dir / five_specs[0]["filename"]
    cv2.imwrite(str(mutated_png), _make_left_porcelain_bust_frame(360, 640, with_crimson_left_eye=True))
    res_stale = validate_semantic_review(tmp_path, five_specs)
    assert five_specs[0]["ref_id"] in res_stale["stale_sha256_ids"]
    assert res_stale["complete"] is False


def test_r53_particle_anatomy_motion_hallucination_and_5pt_morph_detectors(tmp_path: Path) -> None:
    # 1. R53 floating green/cyan particle dot detector vs clean warm-amber brain frame
    clean_brain = _make_left_porcelain_bust_frame(360, 640, with_green_particles=False)
    dirty_brain = _make_left_porcelain_bust_frame(360, 640, with_green_particles=True)
    r_clean = detect_r53_neon_particles(clean_brain, is_brain_or_cutaway=True)
    r_dirty = detect_r53_neon_particles(dirty_brain, is_brain_or_cutaway=True)
    assert r_clean["has_particle_bleed"] is False and r_clean["floating_particle_dots"] == 0
    assert r_dirty["has_particle_bleed"] is True and r_dirty["floating_particle_dots"] >= 3

    # 2. Anatomy detector: left-facing anterior lesion vs symmetric coronal central/posterior lesion
    anat_good = analyze_brain_anatomy_frame(_make_left_porcelain_bust_frame(360, 640, with_crimson_left_eye=True))
    anat_coronal = analyze_brain_anatomy_frame(
        _make_left_porcelain_bust_frame(360, 640, with_crimson_left_eye=True, coronal_symmetric=True)
    )
    assert anat_good["facing_direction"] == "left"
    assert anat_good["crimson_centroid_norm"] is not None
    assert 0.04 <= anat_good["crimson_centroid_norm"][0] <= 0.64
    assert anat_coronal["coronal_symmetry"] >= 0.68

    # 3. Forbidden indoor red curtains + giant golden disc AND cloned duplicate researcher detectors
    stage_hallucination = np.full((640, 360, 3), (35, 35, 35), dtype=np.uint8)
    cv2.rectangle(stage_hallucination, (0, 0), (80, 460), (25, 20, 190), -1)
    cv2.rectangle(stage_hallucination, (280, 0), (360, 460), (25, 20, 190), -1)
    cv2.circle(stage_hallucination, (180, 260), 95, (30, 195, 240), -1)
    hits = detect_forbidden_scene_hallucinations([(0.5, stage_hallucination)], ["indoor_red_curtains_or_giant_golden_disc"])
    assert len(hits) == 1 and "forbidden_indoor_red_curtains_or_golden_disc" in hits[0]

    cloned_lab = np.full((640, 360, 3), (65, 65, 70), dtype=np.uint8)
    for cx_fig in (55, 180, 305):
        cv2.ellipse(cloned_lab, (cx_fig, 130), (24, 30), 0, 0, 360, (235, 235, 238), -1)
        cv2.rectangle(cloned_lab, (cx_fig - 32, 165), (cx_fig + 32, 340), (235, 235, 238), -1)
    clone_hits = detect_forbidden_scene_hallucinations([(0.95, cloned_lab)], ["cloned_duplicate_background_mannequins"])
    assert len(clone_hits) == 1 and "forbidden_cloned_duplicate_mannequins" in clone_hits[0]

    # 4. 5-point continuity catches late-clip morphing (good 0..55%, morphs to stage curtains at 75..95%)
    plan, narrations = _make_hybrid_gage_plan()
    (tmp_path / "02_script").mkdir(parents=True)
    (tmp_path / "03_visuals" / "reference_images").mkdir(parents=True)
    (tmp_path / "03_visuals" / "flow_native_clips").mkdir(parents=True)
    (tmp_path / "02_script" / "script.json").write_text(json.dumps({"clip_narrations": narrations}), encoding="utf-8")
    (tmp_path / "03_visuals" / "visual_plan.json").write_text(json.dumps(plan), encoding="utf-8")

    ref4 = _make_left_porcelain_bust_frame(360, 640, with_crimson_left_eye=False)
    cv2.imwrite(str(tmp_path / "03_visuals" / "reference_images" / "ref_brain_master.png"), ref4)
    cv2.imwrite(str(tmp_path / "03_visuals" / "reference_images" / "ref_clip_04.png"), ref4)

    # Build 24 frames: first 15 match ref4 with smooth motion, last 9 morph into red curtains/gold disc!
    morph_frames = [
        _make_left_porcelain_bust_frame(360, 640, shift_x=int(i * 1.5), pulse=i * 2) if i < 15 else stage_hallucination
        for i in range(24)
    ]
    _write_mp4_from_frames(tmp_path / "03_visuals" / "flow_native_clips" / "clip_4.mp4", morph_frames)

    # Also build clip_5 as coronal symmetric head so cross-brain continuity & coronal gate both trigger!
    coronal_frames = [
        _make_left_porcelain_bust_frame(360, 640, with_crimson_left_eye=True, coronal_symmetric=True)
        for _ in range(24)
    ]
    cv2.imwrite(
        str(tmp_path / "03_visuals" / "reference_images" / "ref_clip_05.png"),
        coronal_frames[0],
    )
    _write_mp4_from_frames(tmp_path / "03_visuals" / "flow_native_clips" / "clip_5.mp4", coronal_frames)

    rep = verify_clips_against_contract(tmp_path, save_report=True, render_strips=True)
    assert rep["all_passed"] is False
    by_num = {c["clip_number"]: c for c in rep["clips"]}
    c4_issues = " ".join(by_num[4]["issues"])
    assert "5pt_ref_continuity_low" in c4_issues or "late_clip_morph_detected" in c4_issues
    c5_issues = " ".join(by_num[5]["issues"])
    assert "anatomical_coronal_view_violation" in c5_issues
    assert rep["cross_brain_continuity"]["passed"] is False
    assert (tmp_path / "03_visuals" / "qa_contact_strips" / "clip_04_5frame_strip.png").exists()

    # Verify cryptographic SHA-256 freshness & instant invalidation on byte change
    fresh_ok, fresh_reasons = is_clip_qa_report_fresh(tmp_path)
    assert fresh_ok is True and fresh_reasons == []
    with open(tmp_path / "03_visuals" / "flow_native_clips" / "clip_4.mp4", "ab") as f:
        f.write(b"\x00\x00\x00\x08free")
    fresh_after, reasons_after = is_clip_qa_report_fresh(tmp_path)
    assert fresh_after is False and "stale_native_clips_sha256" in reasons_after


def test_camera_compensated_motion_separates_static_tableau_from_articulated_action() -> None:
    base = _make_left_porcelain_bust_frame(360, 640)
    # Completely frozen identical frames -> 0 flow
    frozen_mot = compute_camera_compensated_motion([base.copy() for _ in range(20)], fps=12.0)
    assert frozen_mot["raw_flow_mean"] < 0.05
    assert frozen_mot["residual_subject_flow_p90"] < 0.05

    # Articulated action: moving foreground iron rod / arm across stationary background
    active_frames: list[np.ndarray] = []
    for i in range(20):
        frm = base.copy()
        y_rod = 420 - i * 14
        cv2.rectangle(frm, (150, max(20, y_rod - 90)), (172, min(630, y_rod + 90)), (200, 205, 215), -1)
        active_frames.append(frm)
    act_mot = compute_camera_compensated_motion(active_frames, fps=12.0)
    assert act_mot["residual_subject_flow_p90"] >= 0.45


def test_audio_true_peak_clipping_and_deliverable_overwatch(tmp_path: Path) -> None:
    # 1. Create a 0.0 dBFS clipping MP4 and verify VideoAutopsyEngine flags DEFECT_AUDIO_TRUE_PEAK_CLIPPING
    wav_clip = tmp_path / "clipping.wav"
    sr = 44100
    t = np.linspace(0.0, 2.0, sr * 2, endpoint=False)
    samples = np.clip(np.sin(2.0 * np.pi * 220.0 * t) * 1.25, -1.0, 1.0)
    pcm16 = (samples * 32767.0).astype(np.int16)
    with wave.open(str(wav_clip), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(pcm16.tobytes())

    vid_only = _write_mp4_from_frames(
        tmp_path / "vid_only.mp4",
        [_make_left_porcelain_bust_frame(360, 640, shift_x=i, pulse=i * 3) for i in range(24)],
        fps=12,
    )
    clipping_mp4 = tmp_path / "clipping_final.mp4"
    subprocess.run(
        [
            FFMPEG,
            "-y",
            "-loglevel",
            "error",
            "-i",
            str(vid_only),
            "-i",
            str(wav_clip),
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-shortest",
            str(clipping_mp4),
        ],
        check=True,
    )
    aud_rep = VideoAutopsyEngine.inspect_audio_stream(clipping_mp4)
    assert aud_rep["peak_dbfs"] > -1.0
    assert aud_rep["true_peak_clipping"] is True

    # Now apply -1.5 dBFS limiter and confirm peak_dbfs <= -1.0!
    limited_mp4 = tmp_path / "limited_final.mp4"
    subprocess.run(
        [
            FFMPEG,
            "-y",
            "-loglevel",
            "error",
            "-i",
            str(clipping_mp4),
            "-c:v",
            "copy",
            "-af",
            "alimiter=limit=0.841:attack=5:release=50:level=disabled",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            str(limited_mp4),
        ],
        check=True,
    )
    aud_lim = VideoAutopsyEngine.inspect_audio_stream(limited_mp4)
    assert aud_lim["peak_dbfs"] <= -1.0
    assert aud_lim["true_peak_clipping"] is False

    # 2. Standalone brain deliverable overwatch: clean dynamic 8s video passes, green-particle video fails
    clean_8s = _write_mp4_from_frames(
        tmp_path / "clean_brain_8s.mp4",
        [
            _make_left_porcelain_bust_frame(
                360,
                640,
                shift_x=int(i * 1.2) - 40,
                pulse=int((i % 24) * 2),
            )
            for i in range(96)
        ],
        fps=12,
    )
    dirty_8s = _write_mp4_from_frames(
        tmp_path / "dirty_brain_8s.mp4",
        [
            _make_left_porcelain_bust_frame(
                360,
                640,
                with_green_particles=True,
                shift_x=int(i * 1.2) - 40,
            )
            for i in range(96)
        ],
        fps=12,
    )
    ov_clean = verify_standalone_brain_deliverable(clean_8s, mode="opaque_porcelain_cross_section")
    ov_dirty = verify_standalone_brain_deliverable(dirty_8s, mode="opaque_porcelain_cross_section")
    assert ov_clean["passed"] is True, ov_clean["issues"]
    assert ov_dirty["passed"] is False
    assert any("r53_chaotic_green_cyan_particles_detected" in x for x in ov_dirty["issues"])

    # 3. Deliverable C staleness check: when clip_1.mp4 is newer than final_shorts_1080x1920.mp4, overwatch flags it
    proj = tmp_path / "psych_04_phineas_gage_frontal_lobe"
    (proj / "02_script").mkdir(parents=True)
    (proj / "03_visuals" / "flow_native_clips").mkdir(parents=True)
    (proj / "05_assembly").mkdir(parents=True)
    plan, narrations = _make_hybrid_gage_plan()
    (proj / "02_script" / "script.json").write_text(json.dumps({"clip_narrations": narrations}), encoding="utf-8")
    (proj / "03_visuals" / "visual_plan.json").write_text(json.dumps(plan), encoding="utf-8")

    final_short = proj / "05_assembly" / "final_shorts_1080x1920.mp4"
    final_short.write_bytes(limited_mp4.read_bytes())
    old_t = time.time() - 120.0
    os.utime(final_short, (old_t, old_t))
    c1_mp4 = proj / "03_visuals" / "flow_native_clips" / "clip_1.mp4"
    c1_mp4.write_bytes(clean_8s.read_bytes())

    gage_ov = verify_phineas_gage_deliverable(proj, deliverable_mp4s=[final_short], save_in_project=False)
    assert gage_ov["requires_reassembly_and_sync"] is True
    assert any("stale_assembly_outdated_by_newer_clips" in x for x in gage_ov["items"]["item_9_audio_true_peak_and_fresh_assembly"]["issues"])

    md = render_overwatch_markdown(
        {
            "verified_at": "2026-10-25T17:35:00Z",
            "all_deliverables_passed": False,
            "deliverables": {
                "deliverable_a_hippocampus_cross_section": ov_dirty,
                "deliverable_b_hippocampus_translucent_3d": ov_clean,
                "deliverable_c_phineas_gage": gage_ov,
            },
        }
    )
    assert "ACTION_REQUIRED" in md and "r53_chaotic_green_cyan_particles_detected" in md


def test_behavioral_psych_10clip_and_healthy_attention_multi_region_contracts(tmp_path: Path) -> None:
    from pipeline.config import WORKSPACE_ROOT

    # 1. 10-clip BEHAVIORAL_PSYCH dossier (zero brain clips -> no ref_brain_master required)
    milgram_v5 = WORKSPACE_ROOT / "BCI_Shorts_Channel" / "research_dossiers" / "milgram_obedience_shock" / "shorts_v5"
    c_milgram = compile_clip_qa_contract(milgram_v5, dossier_dir=milgram_v5.parent, save=False)
    assert c_milgram["clip_count"] == 10
    assert c_milgram["has_brain_clips"] is False
    assert c_milgram["shared_brain_master_anchor"] is None
    assert c_milgram["cross_brain_continuity_contract"]["enabled"] is False
    assert all(len(c["required_entities"]) >= 1 for c in c_milgram["clips"])

    # 2. Multi-region healthy HYBRID dossier (`invisible_gorilla_attention`):
    # Clip 6 (`primary visual cortex`) vs Clip 7 (`parietal cortex` inhibitory gate -> NOT a physical stroke/lesion!)
    gorilla_v5 = WORKSPACE_ROOT / "BCI_Shorts_Channel" / "research_dossiers" / "invisible_gorilla_attention" / "shorts_v5"
    c_gorilla = compile_clip_qa_contract(gorilla_v5, dossier_dir=gorilla_v5.parent, save=False)
    by_num = {c["clip_number"]: c for c in c_gorilla["clips"]}
    assert by_num[6]["anatomical_contract"]["canonical_region"] == "primary visual cortex"
    assert by_num[7]["anatomical_contract"]["canonical_region"] == "parietal cortex"
    assert by_num[7]["anatomical_contract"]["require_crimson_lesion"] is False

    # 3. Right-hemisphere prefrontal lesion plan -> expected_facing == "right", left-facing bust rejected
    plan, narrations = _make_hybrid_gage_plan()
    plan["dossier"] = ""
    plan["brain_link"]["mechanism"]["canonical_region"] = "right_orbitofrontal_prefrontal_cortex"
    plan["brain_link"]["mechanism"]["state"] = "intact warm champagne-amber tracts behind the right eye socket, zero red"
    plan["brain_link"]["mechanism"]["story_cue"] = "behind his right eye"
    plan["brain_link"]["conclusion"]["canonical_region"] = "right_orbitofrontal_prefrontal_cortex"
    plan["brain_link"]["conclusion"]["state"] = "crimson stroke lesion behind his right eye severing right prefrontal cortex"
    plan["brain_link"]["conclusion"]["story_cue"] = "behind his right eye"
    plan["shots"]["mechanism"]["camera"] = "Slow orbit around three-quarter right porcelain bust cutaway"
    plan["shots"]["mechanism"]["action"] = "Warm champagne-amber signal flows smoothly behind the right eye socket with zero red damage"
    plan["shots"]["conclusion"]["camera"] = "Push in toward the right orbitofrontal cutaway behind the right eye"
    plan["shots"]["conclusion"]["action"] = "Diagonal crimson stroke lesion behind the right eye severs the right prefrontal tract"
    narrations[3] = "Before the stroke, intact wiring behind his right eye kept spatial judgment steady."
    narrations[4] = "How did a focal stroke behind his right eye sever his right prefrontal brake?"

    r_proj = tmp_path / "right_hemi_proj"
    (r_proj / "02_script").mkdir(parents=True)
    (r_proj / "03_visuals" / "flow_native_clips").mkdir(parents=True)
    (r_proj / "02_script" / "script.json").write_text(json.dumps({"clip_narrations": narrations}), encoding="utf-8")
    (r_proj / "03_visuals" / "visual_plan.json").write_text(json.dumps(plan), encoding="utf-8")

    c_right = compile_clip_qa_contract(r_proj, save=True)
    c4_anat = c_right["clips"][3]["anatomical_contract"]
    assert c4_anat["hemisphere"] == "right"
    assert c4_anat["expected_facing"] == "right"
    assert c4_anat["expected_signal_roi_norm"] == [0.34, 0.04, 0.96, 0.62]
    assert c4_anat["forbidden_roi_norm"] == [0.0, 0.0, 0.30, 1.0]

    # Left-facing bust in clip_4 must fail `anatomical_wrong_hemisphere_facing`, while right-facing bust passes
    wrong_left_frames = [_make_left_porcelain_bust_frame(360, 640, face_right=False, shift_x=i) for i in range(20)]
    _write_mp4_from_frames(r_proj / "03_visuals" / "flow_native_clips" / "clip_4.mp4", wrong_left_frames)
    rep_wrong = verify_clips_against_contract(r_proj, contract=c_right, save_report=False, render_strips=False)
    c4_res = next(c for c in rep_wrong["clips"] if c["clip_number"] == 4)
    assert any("anatomical_wrong_hemisphere_facing" in x for x in c4_res["issues"])


def test_continuity_rejects_unrelated_porcelain_scenes_and_passes_dorsal_roi_and_q5_brain(tmp_path: Path) -> None:
    from pipeline.reference_image_qa import inspect_single_reference_image

    # 1. Unrelated porcelain outdoor twilight scene vs indoor red theater curtains must score < 0.42
    twilight_coach = np.full((640, 360, 3), (62, 42, 28), dtype=np.uint8)
    cv2.rectangle(twilight_coach, (40, 360), (320, 560), (95, 88, 82), -1)
    cv2.ellipse(twilight_coach, (175, 290), (32, 48), 0, 0, 360, (225, 225, 228), -1)

    indoor_curtains = np.full((640, 360, 3), (38, 36, 36), dtype=np.uint8)
    cv2.rectangle(indoor_curtains, (0, 0), (85, 520), (25, 20, 190), -1)
    cv2.rectangle(indoor_curtains, (275, 0), (360, 520), (25, 20, 190), -1)
    cv2.circle(indoor_curtains, (180, 260), 92, (35, 195, 240), -1)

    unrelated_sc = compute_spatial_and_palette_continuity(twilight_coach, indoor_curtains, allow_interior_zoom=False)
    assert unrelated_sc["combined_score"] < 0.42

    # 2. Smooth interior push-in crop of a studio brain bust scores >= 0.55 when allow_interior_zoom=True
    brain_ref = _make_left_porcelain_bust_frame(720, 1280)
    zoom_crop = cv2.resize(brain_ref[250:840, 115:605], (720, 1280), interpolation=cv2.INTER_LINEAR)
    zoom_sc = compute_spatial_and_palette_continuity(brain_ref, zoom_crop, allow_interior_zoom=True)
    assert zoom_sc["combined_score"] >= 0.55

    # 3. Q5 in reference_image_qa passes clean studio gallery porcelain brain bust whose uniform surround has ZERO bg_edges
    rng_q5 = np.random.default_rng(7)
    yy, xx = np.mgrid[0:1280, 0:720]
    # Smooth studio gallery cyclorama gradient (zero Canny edges in surround -> bg_edges == 0.0!)
    cyclorama = np.clip(182.0 - 0.035 * yy + rng_q5.integers(-2, 3, size=(1280, 720)), 120, 215).astype(np.uint8)
    brain_q5 = np.stack([cyclorama, cyclorama, cyclorama], axis=-1)
    # Shaded matte-white porcelain bust + gyral sulci strictly inside central [cx0:cx1, cy0:cy1]
    cv2.ellipse(brain_q5, (365, 560), (195, 255), 0, 0, 360, (238, 238, 240), -1)
    cv2.ellipse(brain_q5, (405, 540), (135, 175), 0, 0, 360, (214, 212, 210), -1)
    cv2.rectangle(brain_q5, (250, 790), (490, 1020), (226, 226, 228), -1)
    for k in range(20):
        yk = 385 + k * 16
        cv2.line(brain_q5, (285, yk), (515, yk + (9 if k % 2 == 0 else -9)), (88, 92, 102), 2)
    cv2.ellipse(brain_q5, (295, 520), (36, 20), -15, 0, 360, (70, 190, 238), -1)
    brain_png = tmp_path / "ref_clip_06.png"
    cv2.imwrite(str(brain_png), brain_q5)
    q_rep = inspect_single_reference_image(
        brain_png,
        {"ref_id": "ref_clip_06", "filename": "ref_clip_06.png", "role": "step1", "scene_id": "BRAIN", "setting": "brain_void"},
        aspect="9:16",
    )
    assert q_rep["bg_edge_density"] == 0.0
    assert q_rep["axes_q1_to_q7"]["Q5_environment_and_prop_depth"] is True, q_rep
    assert q_rep["passed"] is True, q_rep

    # 4. Dorsal prefrontal signal (cy ~ 0.13) is inside left anterior prefrontal ROI [0.04, 0.04, 0.66, 0.62]
    dorsal_frame = _make_left_porcelain_bust_frame(360, 640)
    cv2.ellipse(dorsal_frame, (175, 175), (26, 14), 0, 0, 360, (80, 195, 240), -1)
    dorsal_anat = analyze_brain_anatomy_frame(dorsal_frame)
    assert dorsal_anat["amber_centroid_norm"] is not None
    cx, cy = dorsal_anat["amber_centroid_norm"]
    assert 0.04 <= cx <= 0.66 and 0.04 <= cy <= 0.62


def test_ref_brain_master_enforcement_missing_ref_and_clip_semantic_antiboilerplate(tmp_path: Path) -> None:
    from pipeline.clip_qa_contract import (
        CLIP_SEMANTIC_CHECKS,
        validate_clip_semantic_review,
        write_clip_semantic_review_template,
    )

    plan, narrations = _make_hybrid_gage_plan()
    (tmp_path / "02_script").mkdir(parents=True)
    (tmp_path / "03_visuals" / "reference_images").mkdir(parents=True)
    (tmp_path / "03_visuals" / "flow_native_clips").mkdir(parents=True)
    (tmp_path / "02_script" / "script.json").write_text(json.dumps({"clip_narrations": narrations}), encoding="utf-8")
    (tmp_path / "03_visuals" / "visual_plan.json").write_text(json.dumps(plan), encoding="utf-8")

    ref_dir = tmp_path / "03_visuals" / "reference_images"
    clips_dir = tmp_path / "03_visuals" / "flow_native_clips"

    # Left-facing ref_brain_master.png, while BOTH clip_4 and clip_5 are right-facing (pairwise match each other,
    # but violate ref_brain_master!) AND ref_clip_01.png is omitted while clip_1.mp4 exists!
    left_master = _make_left_porcelain_bust_frame(360, 640, face_right=False)
    right_bust = _make_left_porcelain_bust_frame(360, 640, face_right=True, with_crimson_left_eye=True)
    cv2.imwrite(str(ref_dir / "ref_brain_master.png"), left_master)
    cv2.imwrite(str(ref_dir / "ref_clip_04.png"), right_bust)
    cv2.imwrite(str(ref_dir / "ref_clip_05.png"), right_bust)

    for cnum in (1, 2, 3, 4, 5):
        frames = [
            _make_left_porcelain_bust_frame(360, 640, face_right=(cnum in (4, 5)), with_crimson_left_eye=(cnum == 5), shift_x=i)
            for i in range(20)
        ]
        _write_mp4_from_frames(clips_dir / f"clip_{cnum}.mp4", frames)

    rep = verify_clips_against_contract(tmp_path, save_report=True, render_strips=False)
    assert rep["all_passed"] is False
    by_clip = {c["clip_number"]: c for c in rep["clips"]}
    assert any("missing_reference_image: ref_clip_01.png" in x for x in by_clip[1]["issues"])
    cb_issues = " ".join(rep["cross_brain_continuity"]["issues"])
    assert "ref_brain_master" in cb_issues

    # Per-clip semantic review: boilerplate note across >= 4 clips rejected, distinct notes pass, clip byte edit invalidates
    sem_path = write_clip_semantic_review_template(tmp_path)
    sem_obj = json.loads(sem_path.read_text(encoding="utf-8"))
    for k in sem_obj["clips"]:
        sem_obj["clips"][k]["checks"] = {chk: True for chk in CLIP_SEMANTIC_CHECKS}
        sem_obj["clips"][k]["note"] = "Approved generic clip check note"
    sem_path.write_text(json.dumps(sem_obj), encoding="utf-8")

    v_boiler = validate_clip_semantic_review(tmp_path)
    assert len(v_boiler["boilerplate_note_clips"]) == 5
    assert v_boiler["complete"] is True and len(v_boiler["failed_clips"]) == 5

    for idx, k in enumerate(sem_obj["clips"]):
        sem_obj["clips"][k]["note"] = f"Verified specific entity & action progression for {k} beat #{idx}"
    sem_path.write_text(json.dumps(sem_obj), encoding="utf-8")
    v_ok = validate_clip_semantic_review(tmp_path)
    assert v_ok["complete"] is True and v_ok["failed_clips"] == []

    with open(clips_dir / "clip_2.mp4", "ab") as f:
        f.write(b"\x00\x00\x00\x08free")
    v_stale = validate_clip_semantic_review(tmp_path)
    assert 2 in v_stale["stale_sha256_clips"]
    assert v_stale["complete"] is False


def test_post_assembly_qa_gates_and_provenance_size_collision_and_sync_receipt(tmp_path: Path) -> None:
    import importlib.util
    from pipeline.flow_browser import FlowProjectSubagentWorker
    from pipeline.qa_gates import ExecutableQASuite
    from pipeline.reference_image_qa import build_and_verify_project_reference_pack

    proj = tmp_path / "psych_test_gates"
    (proj / "02_script").mkdir(parents=True)
    (proj / "03_visuals" / "flow_native_clips").mkdir(parents=True)
    (proj / "05_assembly").mkdir(parents=True)
    plan, narrations = _make_hybrid_gage_plan()
    (proj / "02_script" / "script.json").write_text(json.dumps({"clip_narrations": narrations}), encoding="utf-8")
    (proj / "03_visuals" / "visual_plan.json").write_text(json.dumps(plan), encoding="utf-8")

    # 1. `build_and_verify_project_reference_pack` (`ref-qa`) compiles `03_visuals/clip_qa_contract.json`
    build_and_verify_project_reference_pack(proj)
    assert (proj / "03_visuals" / "clip_qa_contract.json").exists()

    # 2. Same-byte-size clip replacement MUST fail `validate_provenance_receipt` (no st_size-only SHA-256 skip!)
    clips_dir = proj / "03_visuals" / "flow_native_clips"
    clip_shas: dict[int, tuple[str, int]] = {}
    for i in range(1, 6):
        p_mp4 = clips_dir / f"clip_{i}.mp4"
        p_mp4.write_bytes((f"authentic_stream_clip_{i}_".encode("utf-8") * 50_000)[:1_050_000])
        clip_shas[i] = (compute_sha256(p_mp4), p_mp4.stat().st_size)

    ss_dir = proj / "03_visuals" / "flow_screenshots"
    ss_dir.mkdir(parents=True, exist_ok=True)
    for fn in (
        "flow_gate_v1_prompt_approved.png",
        "flow_gate_v2_rendering_active.png",
        "flow_gate_v3_canvas_clips_ready.png",
        "flow_gate_v4_export_ready.png",
    ):
        (ss_dir / fn).write_bytes(b"\x89PNG\r\n" + b"x" * 12_000)
    (ss_dir / "visual_qa_report.json").write_text(
        json.dumps(
            {
                "gate_v1": {"status": "PASS"},
                "gate_v2": {"status": "PASS"},
                "gate_v3": {"status": "PASS"},
                "gate_v4": {"status": "PASS"},
                "gate_v5": {"status": "PASS"},
            }
        ),
        encoding="utf-8",
    )
    rcpt = {
        "project_id": proj.name,
        "worker_id": f"subagent-{proj.name}",
        "subagent_1_to_1_bound": True,
        "flow_project_url": "https://flow.google.com/project/11111111-2222-3333-4444-555555555555",
        "tab_target_id": "TARGET_TEST_12345678",
        "prompts_submitted_count": 5,
        "visual_gates_passed": True,
        "clips": [
            {
                "clip_index": i,
                "sha256": clip_shas[i][0],
                "file_size_bytes": clip_shas[i][1],
                "source_download_filename": f"flow_clip_{i}.mp4",
            }
            for i in range(1, 6)
        ],
    }
    (proj / "03_visuals" / "flow_provenance_receipt.json").write_text(json.dumps(rcpt), encoding="utf-8")
    prov_ok = FlowProjectSubagentWorker.validate_provenance_receipt(proj)
    assert prov_ok["valid"] is True, prov_ok

    # Overwrite clip_1.mp4 with DIFFERENT bytes of the EXACT SAME 1,050,000 byte size!
    (clips_dir / "clip_1.mp4").write_bytes((b"tampered_same_size_payload_" * 50_000)[:1_050_000])
    assert (clips_dir / "clip_1.mp4").stat().st_size == clip_shas[1][1]
    prov_tampered = FlowProjectSubagentWorker.validate_provenance_receipt(proj)
    assert prov_tampered["valid"] is False
    assert any("clip_1_sha256_mismatch" in e for e in prov_tampered["errors"])

    # 3. Verify `_sync_provenance_receipt` in `fix_gage_items_1_2_3_4_5_8_10.py` updates `clip_index` entries
    gage_script = Path("/home/canadaofbin/.gemini/antigravity-cli/brain/d1e733a7-11d7-4d7c-8093-c19158179c77/scratch/fix_gage_items_1_2_3_4_5_8_10.py")
    if gage_script.exists():
        spec = importlib.util.spec_from_file_location("fix_gage_v6_mod", gage_script)
        assert spec and spec.loader
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mod._sync_provenance_receipt(proj, clips_dir)
        assert FlowProjectSubagentWorker.validate_provenance_receipt(proj)["valid"] is True

    # 4. `ExecutableQASuite.run_post_assembly_gates` blocks sign-off when `clip_contract_qa_report.json` is missing
    gates_res = ExecutableQASuite.run_post_assembly_gates(proj)
    assert gates_res["passed"] is False
    assert gates_res["clip_contract_qa_ok"] is False
    assert "missing_clip_contract_qa_report" in gates_res["issues"]


def test_hardened_jump_cut_midclip_skin_porcelain_loss_left_eye_side_and_stale_semantic_gate(tmp_path: Path) -> None:
    from pipeline.clip_qa_contract import (
        CLIP_SEMANTIC_CHECKS,
        write_clip_semantic_review_template,
    )
    from pipeline.deliverable_overwatch import (
        _check_left_eye_cutaway_side,
        _verify_project_mirror_parity,
    )
    from pipeline.qa_gates import ExecutableQASuite

    # 1. Intra-clip hard jump-cut detection (`has_hard_jump_cut`) vs smooth pan
    smooth_frames = [_make_left_porcelain_bust_frame(360, 640, shift_x=i * 2) for i in range(24)]
    m_smooth = compute_camera_compensated_motion(smooth_frames, fps=12.0)
    assert m_smooth["has_hard_jump_cut"] is False

    bright_outdoor = np.full((640, 360, 3), (225, 228, 232), dtype=np.uint8)
    cv2.rectangle(bright_outdoor, (70, 140), (290, 520), (242, 242, 245), -1)
    jump_frames = [
        _make_left_porcelain_bust_frame(360, 640, shift_x=i) if i < 12 else bright_outdoor.copy()
        for i in range(24)
    ]
    m_jump = compute_camera_compensated_motion(jump_frames, fps=12.0)
    assert m_jump["has_hard_jump_cut"] is True
    assert m_jump["max_frame_step_diff"] >= 30.0

    # 2. Mid-clip `forbidden_real_human_face_or_skin` & `porcelain_cast_lost_or_cropped_out`
    flesh_frame = np.full((640, 360, 3), (45, 50, 55), dtype=np.uint8)
    # BGR (110, 140, 185) -> HSV ~ (11, 103, 185) inside human skin / warm fur window
    cv2.rectangle(flesh_frame, (95, 90), (265, 310), (110, 140, 185), -1)
    skin_hits = detect_forbidden_scene_hallucinations(
        [(0.95, flesh_frame)],
        ["real_human_face_or_skin"],
        is_brain_clip=False,
        require_porcelain_presence=True,
    )
    assert any("forbidden_real_human_face_or_skin@95pct" in h for h in skin_hits), skin_hits
    assert any("porcelain_cast_lost_or_cropped_out@95pct" in h for h in skin_hits), skin_hits

    # 3. `_check_left_eye_cutaway_side`: right-temple glow on right-facing head must FAIL; left-eye glow must PASS
    wrong_right_eye = np.full((640, 360, 3), (38, 42, 46), dtype=np.uint8)
    # Porcelain face on viewer-right (cx ~ 0.68), glowing amber cutaway on viewer-left (cx ~ 0.28)
    cv2.ellipse(wrong_right_eye, (245, 220), (52, 70), 0, 0, 360, (232, 232, 235), -1)
    cv2.circle(wrong_right_eye, (100, 195), 32, (60, 195, 245), -1)
    ok_wrong, delta_wrong = _check_left_eye_cutaway_side(wrong_right_eye)
    assert ok_wrong is False and delta_wrong < -0.10

    good_left_eye = np.full((640, 360, 3), (38, 42, 46), dtype=np.uint8)
    # Porcelain face on viewer-left/center (cx ~ 0.44), glowing amber cutaway behind left eye (cx ~ 0.48)
    cv2.ellipse(good_left_eye, (158, 220), (52, 70), 0, 0, 360, (232, 232, 235), -1)
    cv2.circle(good_left_eye, (172, 195), 28, (60, 195, 245), -1)
    ok_good, delta_good = _check_left_eye_cutaway_side(good_left_eye)
    assert ok_good is True and delta_good >= -0.10

    # 4. Stale `clip_semantic_review.json` SHA-256 blocks `verify_clips_against_contract` AND `run_post_assembly_gates`
    proj = tmp_path / "psych_stale_sem"
    (proj / "02_script").mkdir(parents=True)
    (proj / "03_visuals" / "reference_images").mkdir(parents=True)
    (proj / "03_visuals" / "flow_native_clips").mkdir(parents=True)
    (proj / "05_assembly").mkdir(parents=True)
    plan, narrations = _make_hybrid_gage_plan()
    (proj / "02_script" / "script.json").write_text(json.dumps({"clip_narrations": narrations}), encoding="utf-8")
    (proj / "03_visuals" / "visual_plan.json").write_text(json.dumps(plan), encoding="utf-8")

    ref_dir = proj / "03_visuals" / "reference_images"
    clips_dir = proj / "03_visuals" / "flow_native_clips"
    base_frm = _make_left_porcelain_bust_frame(360, 640, face_right=False)
    cv2.imwrite(str(ref_dir / "ref_brain_master.png"), base_frm)
    for cnum in range(1, 6):
        frm_c = _make_left_porcelain_bust_frame(360, 640, with_crimson_left_eye=(cnum == 5))
        cv2.imwrite(str(ref_dir / f"ref_clip_{cnum:02d}.png"), frm_c)
        _write_mp4_from_frames(
            clips_dir / f"clip_{cnum}.mp4",
            [_make_left_porcelain_bust_frame(360, 640, with_crimson_left_eye=(cnum == 5), shift_x=i * 2) for i in range(20)],
        )

    sem_path = write_clip_semantic_review_template(proj)
    sem_obj = json.loads(sem_path.read_text(encoding="utf-8"))
    for idx, k in enumerate(sem_obj["clips"]):
        sem_obj["clips"][k]["checks"] = {chk: True for chk in CLIP_SEMANTIC_CHECKS}
        sem_obj["clips"][k]["note"] = f"Specific human/agent visual review for {k} #{idx}"
    sem_path.write_text(json.dumps(sem_obj), encoding="utf-8")

    # Mutate clip_1.mp4 AFTER semantic review was signed -> stale SHA-256 must fail even when require_semantic_review=False!
    with open(clips_dir / "clip_1.mp4", "ab") as f:
        f.write(b"\x00\x00\x00\x08free")
    rep_stale = verify_clips_against_contract(proj, save_report=True, render_strips=False, require_semantic_review=False)
    assert rep_stale["all_passed"] is False
    assert 1 in rep_stale["regenerate_clips"]
    gates_stale = ExecutableQASuite.run_post_assembly_gates(proj)
    assert gates_stale["clip_contract_qa_ok"] is False
    assert any("invalid_or_stale_clip_semantic_review" in iss for iss in gates_stale["issues"])

    # 5. `_verify_project_mirror_parity` catches SHA-256 drift across SSD and mirror workspaces
    mirror = tmp_path / "psych_mirror"
    (mirror / "03_visuals" / "flow_native_clips").mkdir(parents=True)
    (mirror / "03_visuals" / "flow_native_clips" / "clip_1.mp4").write_bytes(b"different_mirror_bytes")
    parity = _verify_project_mirror_parity(proj, mirror, clip_count=5)
    assert parity["passed"] is False
    assert any("sha256_drift(03_visuals/flow_native_clips/clip_1.mp4)" in x for x in parity["issues"])


