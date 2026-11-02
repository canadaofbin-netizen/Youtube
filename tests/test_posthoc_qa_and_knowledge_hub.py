"""Comprehensive tests for Rule R64 Post-Hoc Clip-by-Clip Expressive Clarity QA
(`pipeline/posthoc_semantic_qa.py`) and Rule R50-B Knowledge Hub (`pipeline/knowledge_hub.py`).

Covers:
1. Schema v7 happy-path dual-stream clarity scoring, viewer contact strips, and SHA-256 review sign-off.
2. Adversarial / edge-case detection:
   - Blurry / low-contrast washed-out cut
   - Stalled moving camera (`pan_right`) & static dead `locked_tripod`
   - Mid-cut AI morph / histogram jump
   - Identical `split_hstack` panes & missing divider
   - Missing brain lesion chroma highlight
   - Root-cause attribution (`shift_edl_source_window` vs `regenerate_flow_clip` vs `rebuild_assembly_edl_or_subtitles`)
3. Anti-boilerplate & provenance locks in `validate_posthoc_semantic_review`.
4. Classic v5 (`concat_list.txt`, no EDL) compatibility.
5. Idempotent `knowledge_hub` indexing, aggregate pack compilation, and multi-pack search.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import cv2
import imageio_ffmpeg
import numpy as np
import pytest

from pipeline import config as cfg
from pipeline.asset_manifest import build_asset_manifest, upsert_library
from pipeline.knowledge_hub import (
    ensure_knowledge_base_layout,
    query_knowledge_base,
    sync_all_projects_to_knowledge_base,
    sync_project_to_knowledge_base,
)
from pipeline.posthoc_semantic_qa import (
    init_posthoc_semantic_review_template,
    run_posthoc_semantic_qa,
    validate_posthoc_semantic_review,
)


def _write_mp4_from_frames(path: Path, frames_bgr: list[np.ndarray], fps: int = 24) -> None:
    """Encodes BGR frames into a real H.264 yuv420p MP4 via bundled ffmpeg."""
    path.parent.mkdir(parents=True, exist_ok=True)
    h, w = frames_bgr[0].shape[:2]
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    cmd = [
        ff,
        "-nostdin",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "bgr24",
        "-s",
        f"{w}x{h}",
        "-r",
        str(fps),
        "-i",
        "pipe:0",
        "-c:v",
        "libx264",
        "-preset",
        "ultrafast",
        "-crf",
        "18",
        "-pix_fmt",
        "yuv420p",
        str(path),
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    assert proc.stdin is not None
    for frm in frames_bgr:
        proc.stdin.write(frm.tobytes())
    proc.stdin.close()
    rc = proc.wait(timeout=60)
    assert rc == 0, f"ffmpeg encode failed for {path}"


def _make_pastel_world_frame(
    w: int = 540,
    h: int = 960,
    shift_x: int = 0,
    hand_offset: int = 0,
) -> np.ndarray:
    """Crisp, textured pastel low-poly style frame with clear foreground-vs-periphery separation."""
    frm = np.full((h, w, 3), (188, 198, 206), dtype=np.uint8)
    # Sky & layered geometric hills in periphery
    frm[0 : int(h * 0.28), :] = (218, 204, 186)
    for k in range(0, w + 120, 60):
        xk = (k - shift_x) % (w + 60) - 30
        pts = np.array([[xk, int(h * 0.56)], [xk + 36, int(h * 0.30)], [xk + 72, int(h * 0.56)]], dtype=np.int32)
        cv2.fillPoly(frm, [pts], (138, 162, 146))
        cv2.polylines(frm, [pts], True, (82, 102, 88), 2)
    # Textured rail bed grid
    for y_line in range(int(h * 0.26), int(h * 0.62), 28):
        cv2.line(frm, (20, y_line), (w - 20, y_line), (148, 156, 164), 1)
    # Distinct warm terracotta/slate foreground subject in center ROI
    cx = w // 2 + hand_offset
    cy = int(h * 0.42)
    cv2.rectangle(frm, (cx - 85, cy - 90), (cx + 85, cy + 90), (74, 96, 158), -1)
    cv2.rectangle(frm, (cx - 85, cy - 90), (cx + 85, cy + 90), (36, 44, 62), 3)
    cv2.line(frm, (cx - 60, cy - 70), (cx + 60, cy + 70), (225, 232, 240), 4)
    cv2.circle(frm, (cx, cy), 34, (92, 178, 218), -1)
    return frm


def _make_brain_frame(w: int = 540, h: int = 960, highlight: bool = True, rot: int = 0) -> np.ndarray:
    frm = np.full((h, w, 3), (168, 174, 180), dtype=np.uint8)
    # Studio pedestal at lower display band
    cv2.rectangle(frm, (w // 2 - 140, int(h * 0.51)), (w // 2 + 140, int(h * 0.56)), (126, 130, 136), -1)
    cx, cy = w // 2 + rot, int(h * 0.40)
    cv2.ellipse(frm, (cx, cy), (150, 118), 0, 0, 360, (234, 232, 228), -1)
    cv2.ellipse(frm, (cx, cy), (150, 118), 0, 0, 360, (86, 88, 92), 3)
    for ang in range(-60, 75, 25):
        cv2.line(frm, (cx - 105, cy + ang), (cx + 105, cy - ang // 2), (122, 125, 130), 2)
    if highlight:
        # Vivid terracotta-coral prefrontal lesion + cyan tract
        cv2.circle(frm, (cx - 52, cy - 18), 38, (56, 78, 226), -1)
        cv2.line(frm, (cx - 48, cy - 12), (cx + 62, cy + 28), (228, 186, 48), 7)
    return frm


def _make_split_hstack_frame(
    w: int = 540,
    h: int = 960,
    distinct: bool = True,
    with_divider: bool = True,
    step: int = 0,
) -> np.ndarray:
    left = _make_pastel_world_frame(w, h, shift_x=step * 5, hand_offset=step * 3)
    if distinct:
        right = _make_brain_frame(w, h, highlight=True, rot=step * 3)
    else:
        right = left.copy()
    out = np.zeros((h, w, 3), dtype=np.uint8)
    out[:, : w // 2] = left[:, w // 4 : w // 4 + w // 2]
    out[:, w // 2 :] = right[:, w // 4 : w // 4 + (w - w // 2)]
    if with_divider:
        out[:, w // 2 - 3 : w // 2 + 3] = (0, 0, 0)
    return out


def test_posthoc_qa_v7_happy_path_strips_and_review_gate(tmp_path: Path) -> None:
    p_dir = tmp_path / "ep_v7_happy"
    for sub in ("02_script", "03_visuals/flow_native_clips", "04_audio", "05_assembly"):
        (p_dir / sub).mkdir(parents=True, exist_ok=True)

    fps = 24
    # Build 4 source clips (2.5s each = 60 frames) and a 5-cut assembled MP4 (8.0s = 192 frames)
    c1_frames = [_make_pastel_world_frame(shift_x=0, hand_offset=int(18 * np.sin(i * 0.22))) for i in range(60)]
    c2_frames = [_make_pastel_world_frame(shift_x=i * 4, hand_offset=0) for i in range(60)]
    c3_frames = [_make_brain_frame(highlight=True, rot=int(14 * np.sin(i * 0.20))) for i in range(60)]
    c4_frames = [_make_pastel_world_frame(shift_x=i * 3, hand_offset=i % 9) for i in range(60)]

    for idx, frs in enumerate((c1_frames, c2_frames, c3_frames, c4_frames), start=1):
        _write_mp4_from_frames(p_dir / "03_visuals" / "flow_native_clips" / f"clip_{idx}.mp4", frs, fps=fps)

    split_frames = [_make_split_hstack_frame(distinct=True, with_divider=True, step=i) for i in range(48)]
    assembled_frames = c1_frames[:36] + c2_frames[:36] + c3_frames[:36] + split_frames[:36] + c4_frames[:48]
    assert len(assembled_frames) == 192
    _write_mp4_from_frames(p_dir / "05_assembly" / "final_shorts_1080x1920.mp4", assembled_frames, fps=fps)

    sentences = [
        "Thirteen pounds of iron shot cleanly through Phineas Gage's skull.",
        "Workers carried him across the sunlit Vermont granite railroad cut.",
        "Crimson prefrontal damage severed white-matter pathways behind his eye.",
        "Daily six-horse stagecoach structure rebuilt his frontal control.",
    ]
    (p_dir / "02_script" / "script.json").write_text(
        json.dumps(
            {
                "schema": 7,
                "profile": "neuro_diorama",
                "style_profile": "lowpoly_pastel_v7",
                "tts_rate": "+5%",
                "sentences": sentences,
            }
        ),
        encoding="utf-8",
    )
    visual_plan = {
        "schema": 7,
        "profile": "neuro_diorama",
        "style_profile": "lowpoly_pastel_v7",
        "dossier": "phineas_gage_iron_rod",
        "clips": [
            {
                "clip_number": 1,
                "sentence_index": 1,
                "act": 1,
                "grammar": "lowpoly_hands_closeup",
                "camera": "locked_tripod",
                "location_id": "vermont_rail_cut",
                "scene": "Gloved low-poly hands grip and tamp an iron bar into granite.",
            },
            {
                "clip_number": 2,
                "sentence_index": 2,
                "act": 2,
                "grammar": "lowpoly_fullbleed_world",
                "camera": "pan_right",
                "location_id": "vermont_rail_cut",
                "scene": "Railroad crew walk beside wooden carts along granite hills.",
            },
            {
                "clip_number": 3,
                "sentence_index": 3,
                "act": 3,
                "grammar": "lowpoly_matte_brain",
                "brain_mode": "matte_pastel_sagittal_cutaway",
                "brain_region": "ventromedial_prefrontal_cortex",
                "camera": "locked_tripod",
                "location_id": "pastel_brain_studio",
                "scene": "Matte low-poly sagittal brain model with coral lesion and cyan tract.",
            },
            {
                "clip_number": 4,
                "sentence_index": 4,
                "act": 6,
                "grammar": "lowpoly_fullbleed_world",
                "camera": "tilt_up",
                "location_id": "chile_coastal_road",
                "scene": "Six-horse coach glides along coastal hills under pastel sky.",
            },
        ],
    }
    (p_dir / "03_visuals" / "visual_plan.json").write_text(json.dumps(visual_plan), encoding="utf-8")
    (p_dir / "03_visuals" / "flow_all_in_one_prompts.json").write_text(
        json.dumps(
            {
                "schema_version": 7,
                "style_profile": "lowpoly_pastel_v7",
                "clips": [
                    {
                        "clip_number": c["clip_number"],
                        "grammar": c["grammar"],
                        "camera_move": c["camera"],
                        "scene": c["scene"],
                        "prompt": f"Low-poly pastel 3D: {c['scene']}",
                    }
                    for c in visual_plan["clips"]
                ],
            }
        ),
        encoding="utf-8",
    )
    edl = {
        "schema": 7,
        "fps": 24,
        "total_duration_sec": 8.0,
        "cuts": [
            {
                "cut_index": 1,
                "clip_index": 1,
                "act": 1,
                "mode": "single",
                "grammar": "lowpoly_hands_closeup",
                "camera_move": "locked_tripod",
                "sentence_indices": [1],
                "out_start_sec": 0.0,
                "out_end_sec": 1.5,
                "duration_sec": 1.5,
                "src_start_sec": 0.0,
                "src_end_sec": 1.5,
            },
            {
                "cut_index": 2,
                "clip_index": 2,
                "act": 2,
                "mode": "single",
                "grammar": "lowpoly_fullbleed_world",
                "camera_move": "pan_right",
                "sentence_indices": [2],
                "out_start_sec": 1.5,
                "out_end_sec": 3.0,
                "duration_sec": 1.5,
                "src_start_sec": 0.0,
                "src_end_sec": 1.5,
            },
            {
                "cut_index": 3,
                "clip_index": 3,
                "act": 3,
                "mode": "single",
                "grammar": "lowpoly_matte_brain",
                "camera_move": "locked_tripod",
                "sentence_indices": [3],
                "out_start_sec": 3.0,
                "out_end_sec": 4.5,
                "duration_sec": 1.5,
                "src_start_sec": 0.0,
                "src_end_sec": 1.5,
            },
            {
                "cut_index": 4,
                "clip_index": 2,
                "secondary_clip_index": 3,
                "act": 4,
                "mode": "split_hstack",
                "grammar": "lowpoly_fullbleed_world",
                "camera_move": "pan_right",
                "sentence_indices": [4],
                "out_start_sec": 4.5,
                "out_end_sec": 6.0,
                "duration_sec": 1.5,
                "src_start_sec": 0.0,
                "src_end_sec": 1.5,
            },
            {
                "cut_index": 5,
                "clip_index": 4,
                "act": 6,
                "mode": "outro",
                "grammar": "lowpoly_fullbleed_world",
                "camera_move": "tilt_up",
                "sentence_indices": [],
                "out_start_sec": 6.0,
                "out_end_sec": 8.0,
                "duration_sec": 2.0,
                "src_start_sec": 0.0,
                "src_end_sec": 2.0,
            },
        ],
    }
    (p_dir / "05_assembly" / "edit_decision_list.json").write_text(json.dumps(edl), encoding="utf-8")
    (p_dir / "04_audio" / "subtitles.ass").write_text(
        "[Events]\n"
        "Dialogue: 0,0:00:00.05,0:00:01.45,Default,,0,0,0,,13 pounds\n"
        "Dialogue: 0,0:00:01.55,0:00:02.95,Default,,0,0,0,,sunlit cut\n"
        "Dialogue: 0,0:00:03.05,0:00:04.45,Default,,0,0,0,,crimson damage\n"
        "Dialogue: 0,0:00:04.55,0:00:05.95,Default,,0,0,0,,stagecoach structure\n",
        encoding="utf-8",
    )

    rep = run_posthoc_semantic_qa(p_dir, render_strips=True, run_asr_sync=False, require_review=False)
    assert rep["passed"] is True, f"Expected happy-path R64 pass, got weak cuts: {rep['cuts']}"
    assert rep["cv_passed"] is True
    assert rep["summary"]["cut_count"] == 5
    assert rep["summary"]["weak_cut_count"] == 0
    assert rep["summary"]["mean_clarity_score"] >= cfg.POSTHOC_MIN_EPISODE_MEAN_CLARITY_SCORE
    assert len(rep["viewer_sheets"]) == 1
    sheet_im = cv2.imread(rep["viewer_sheets"][0])
    assert sheet_im is not None and sheet_im.shape[1] == 1340

    # Without review file, require_review=True must fail
    rep_unrev = run_posthoc_semantic_qa(p_dir, render_strips=False, run_asr_sync=False, require_review=True)
    assert rep_unrev["cv_passed"] is True
    assert rep_unrev["passed"] is False
    assert "missing_posthoc_semantic_review_json" in rep_unrev["semantic_review"]["issues"]

    # Auto-populated CV baseline MUST be rejected under require_review=True until human/VLM inspection
    rev_path = init_posthoc_semantic_review_template(p_dir, qa_report=rep, auto_populate_from_cv=True)
    assert rev_path.exists()
    rep_auto = run_posthoc_semantic_qa(p_dir, render_strips=False, run_asr_sync=False, require_review=True)
    assert rep_auto["passed"] is False
    assert rep_auto["semantic_review"]["valid"] is False
    assert any("auto_populated_cv_baseline_not_semantically_verified" in x for x in rep_auto["semantic_review"]["issues"])

    # Genuine per-cut visual observations + auto_populated=False satisfy anti-boilerplate + SHA-256 lock
    rev_doc = json.loads(rev_path.read_text(encoding="utf-8"))
    rev_doc["auto_populated"] = False
    rev_doc["review_origin"] = "adversarial_test_signoff"
    distinct_obs = [
        "Gloved low-poly hands clearly tamp the iron bar into the grey granite borehole.",
        "Railroad crew pans smoothly rightward beside wooden carts along pastel granite hills.",
        "Matte sagittal brain model displays vivid coral prefrontal lesion and cyan tract.",
        "Left granite rail cut and right coral prefrontal brain separated by crisp black divider.",
        "Six-horse stagecoach tilts upward along coastal hills under clean pastel sky.",
    ]
    for r_row, obs_txt in zip(rev_doc["cuts"], distinct_obs):
        r_row["auto_populated"] = False
        r_row["observed_visual_summary"] = obs_txt
        r_row["expresses_intended_meaning"] = True
    rev_path.write_text(json.dumps(rev_doc, indent=2), encoding="utf-8")

    rep_rev = run_posthoc_semantic_qa(p_dir, render_strips=False, run_asr_sync=False, require_review=True)
    assert rep_rev["passed"] is True
    assert rep_rev["semantic_review"]["valid"] is True

    # Read-only mode (save_report=False with default render_strips=None) must perform ZERO disk writes
    snap_pre = {
        f.relative_to(p_dir).as_posix(): (f.stat().st_mtime_ns, f.stat().st_size)
        for f in sorted(p_dir.rglob("*"))
        if f.is_file()
    }
    rep_ro = run_posthoc_semantic_qa(p_dir, run_asr_sync=False, require_review=True, save_report=False)
    snap_post = {
        f.relative_to(p_dir).as_posix(): (f.stat().st_mtime_ns, f.stat().st_size)
        for f in sorted(p_dir.rglob("*"))
        if f.is_file()
    }
    assert rep_ro["passed"] is True
    assert snap_pre == snap_post


def test_posthoc_qa_detects_defects_and_attributes_remediation_accurately(tmp_path: Path) -> None:
    p_dir = tmp_path / "ep_v7_defects"
    for sub in ("02_script", "03_visuals/flow_native_clips", "04_audio", "05_assembly"):
        (p_dir / sub).mkdir(parents=True, exist_ok=True)

    fps = 24
    # Cut 1 (blurry + static in [0..1.5s], BUT source clip_1 has sharp active motion in [2.0..5.0s] -> shift_edl_source_window!)
    blurry_flat = np.full((960, 540, 3), (182, 184, 186), dtype=np.uint8)
    clip1_src = [blurry_flat.copy() for _ in range(36)] + [
        _make_pastel_world_frame(shift_x=i * 5, hand_offset=i * 2) for i in range(84)
    ]
    _write_mp4_from_frames(p_dir / "03_visuals" / "flow_native_clips" / "clip_1.mp4", clip1_src, fps=fps)

    # Cut 2 (pan_right camera, completely frozen across entire source clip_2 -> regenerate_flow_clip!)
    frozen_world = _make_pastel_world_frame(shift_x=0, hand_offset=0)
    clip2_src = [frozen_world.copy() for _ in range(72)]
    _write_mp4_from_frames(p_dir / "03_visuals" / "flow_native_clips" / "clip_2.mp4", clip2_src, fps=fps)

    # Cut 3 (mid-cut AI morph/palette jump between frames -> regenerate_flow_clip)
    morph_a = _make_pastel_world_frame(shift_x=0, hand_offset=4)
    morph_b = np.zeros((960, 540, 3), dtype=np.uint8)
    morph_b[:, :] = (240, 20, 190)  # jarring magenta flash/morph
    cv2.rectangle(morph_b, (120, 260), (420, 540), (20, 250, 40), -1)
    cut3_frames = [morph_a] * 18 + [morph_b] * 18
    _write_mp4_from_frames(p_dir / "03_visuals" / "flow_native_clips" / "clip_3.mp4", cut3_frames, fps=fps)

    # Cut 4 (split_hstack with identical panes & no black divider -> rebuild_assembly_edl_or_subtitles)
    bad_split = [_make_split_hstack_frame(distinct=False, with_divider=False, step=i) for i in range(36)]
    _write_mp4_from_frames(p_dir / "03_visuals" / "flow_native_clips" / "clip_4.mp4", bad_split, fps=fps)

    # Cut 5 (brain cut expecting crimson lesion highlight, but rendered completely neutral grey)
    grey_brain = [_make_brain_frame(highlight=False, rot=int(12 * np.sin(i * 0.3))) for i in range(36)]
    _write_mp4_from_frames(p_dir / "03_visuals" / "flow_native_clips" / "clip_5.mp4", grey_brain, fps=fps)

    # Cut 6 (tilt_down starts with empty upper-center wall in [0..1.5s], while [2.0..4.5s] of clip_6 frames the sharp brain -> shift_edl_source_window!)
    empty_top_frames: list[np.ndarray] = []
    for i in range(36):
        ef = np.full((960, 540, 3), (194, 198, 204), dtype=np.uint8)
        # Subject sits way down at bottom edge (outside [0.22..0.56] upper-center focal band) while camera tilts
        by = int(960 * 0.78) - i * 2
        cv2.rectangle(ef, (140, by), (400, by + 130), (68, 92, 162), -1)
        cv2.rectangle(ef, (140, by), (400, by + 130), (30, 38, 52), 4)
        cv2.line(ef, (150, by + 40), (390, by + 90), (235, 240, 246), 4)
        empty_top_frames.append(ef)
    clip6_src = empty_top_frames + [_make_brain_frame(highlight=True, rot=int(10 * np.sin(i * 0.25))) for i in range(84)]
    _write_mp4_from_frames(p_dir / "03_visuals" / "flow_native_clips" / "clip_6.mp4", clip6_src, fps=fps)

    assembled = clip1_src[:36] + clip2_src[:36] + cut3_frames + bad_split + grey_brain + empty_top_frames
    _write_mp4_from_frames(p_dir / "05_assembly" / "final_shorts_1080x1920.mp4", assembled, fps=fps)

    (p_dir / "02_script" / "script.json").write_text(
        json.dumps(
            {
                "schema": 7,
                "profile": "neuro_diorama",
                "style_profile": "lowpoly_pastel_v7",
                "sentences": [
                    "Hands grip the heavy iron rod.",
                    "Workers pan across the granite cut.",
                    "Sudden blast shakes the quarry.",
                    "Left and right hemispheres compared side by side.",
                    "Crimson lesion severs the left prefrontal tract.",
                    "Four percent of outer cortex destroyed.",
                ],
            }
        ),
        encoding="utf-8",
    )
    (p_dir / "03_visuals" / "visual_plan.json").write_text(
        json.dumps(
            {
                "schema": 7,
                "profile": "neuro_diorama",
                "style_profile": "lowpoly_pastel_v7",
                "clips": [
                    {"clip_number": 1, "sentence_index": 1, "act": 1, "grammar": "lowpoly_hands_closeup", "camera": "locked_tripod", "scene": "Hands grip rod."},
                    {"clip_number": 2, "sentence_index": 2, "act": 2, "grammar": "lowpoly_fullbleed_world", "camera": "pan_right", "scene": "Crew walks rail cut."},
                    {"clip_number": 3, "sentence_index": 3, "act": 2, "grammar": "lowpoly_fullbleed_world", "camera": "pan_left", "scene": "Quarry ledge."},
                    {"clip_number": 4, "sentence_index": 4, "act": 3, "grammar": "lowpoly_fullbleed_world", "camera": "pan_right", "scene": "Split comparison."},
                    {"clip_number": 5, "sentence_index": 5, "act": 3, "grammar": "lowpoly_matte_brain", "camera": "locked_tripod", "scene": "Crimson lesion glow in prefrontal cortex."},
                    {"clip_number": 6, "sentence_index": 6, "act": 3, "grammar": "lowpoly_matte_brain", "camera": "tilt_down", "scene": "Coral cortical patch on frontal pole."},
                ],
            }
        ),
        encoding="utf-8",
    )
    edl = {
        "schema": 7,
        "fps": 24,
        "total_duration_sec": 9.0,
        "cuts": [
            {"cut_index": 1, "clip_index": 1, "act": 1, "mode": "single", "grammar": "lowpoly_hands_closeup", "camera_move": "locked_tripod", "sentence_indices": [1], "out_start_sec": 0.0, "out_end_sec": 1.5, "duration_sec": 1.5, "src_start_sec": 0.0, "src_end_sec": 1.5},
            {"cut_index": 2, "clip_index": 2, "act": 2, "mode": "single", "grammar": "lowpoly_fullbleed_world", "camera_move": "pan_right", "sentence_indices": [2], "out_start_sec": 1.5, "out_end_sec": 3.0, "duration_sec": 1.5, "src_start_sec": 0.0, "src_end_sec": 1.5},
            {"cut_index": 3, "clip_index": 3, "act": 2, "mode": "single", "grammar": "lowpoly_fullbleed_world", "camera_move": "pan_left", "sentence_indices": [3], "out_start_sec": 3.0, "out_end_sec": 4.5, "duration_sec": 1.5, "src_start_sec": 0.0, "src_end_sec": 1.5},
            {"cut_index": 4, "clip_index": 4, "secondary_clip_index": 4, "act": 3, "mode": "split_hstack", "grammar": "lowpoly_fullbleed_world", "camera_move": "pan_right", "sentence_indices": [4], "out_start_sec": 4.5, "out_end_sec": 6.0, "duration_sec": 1.5, "src_start_sec": 0.0, "src_end_sec": 1.5},
            {"cut_index": 5, "clip_index": 5, "act": 3, "mode": "single", "grammar": "lowpoly_matte_brain", "camera_move": "locked_tripod", "sentence_indices": [5], "out_start_sec": 6.0, "out_end_sec": 7.5, "duration_sec": 1.5, "src_start_sec": 0.0, "src_end_sec": 1.5},
            {"cut_index": 6, "clip_index": 6, "act": 3, "mode": "single", "grammar": "lowpoly_matte_brain", "camera_move": "tilt_down", "sentence_indices": [6], "out_start_sec": 7.5, "out_end_sec": 9.0, "duration_sec": 1.5, "src_start_sec": 0.0, "src_end_sec": 1.5},
        ],
    }
    (p_dir / "05_assembly" / "edit_decision_list.json").write_text(json.dumps(edl), encoding="utf-8")

    rep = run_posthoc_semantic_qa(p_dir, render_strips=False, run_asr_sync=False)
    assert rep["passed"] is False
    assert rep["summary"]["weak_cut_indices"] == [1, 2, 3, 4, 5, 6]
    shift_recs = {int(r["cut_index"]): r for r in rep["summary"]["shift_window_recommendations"]}
    assert 1 in shift_recs and 6 in shift_recs

    by_cut = {int(c["cut_index"]): c for c in rep["cuts"]}
    assert any("blurry_focus" in d for d in by_cut[1]["defects"])
    assert by_cut[1]["remediation"] == "shift_edl_source_window"
    assert by_cut[1]["recommended_src_window_sec"] is not None

    assert any("moving_camera_stalled:pan_right" in d for d in by_cut[2]["defects"])
    assert by_cut[2]["remediation"] == "regenerate_flow_clip"
    assert 2 in rep["summary"]["regenerate_clip_indices"]

    assert any("mid_cut_morph_hist_jump" in d for d in by_cut[3]["defects"])

    assert any("split_panes_visually_identical" in d for d in by_cut[4]["defects"])
    assert any("split_hstack_divider_missing" in d for d in by_cut[4]["defects"])
    assert by_cut[4]["remediation"] == "rebuild_assembly_edl_or_subtitles"

    assert any("weak_brain_lesion_or_tract_highlight" in d for d in by_cut[5]["defects"])

    assert any("empty_upper_center_focal_zone" in d for d in by_cut[6]["defects"])
    assert by_cut[6]["remediation"] == "shift_edl_source_window"
    assert by_cut[6]["recommended_src_window_sec"] is not None


def test_review_anti_boilerplate_sha256_and_rejection_propagation(tmp_path: Path) -> None:
    p_dir = tmp_path / "ep_review_guards"
    for sub in ("02_script", "03_visuals/flow_native_clips", "05_assembly"):
        (p_dir / sub).mkdir(parents=True, exist_ok=True)

    fps = 24
    clips = [[_make_pastel_world_frame(shift_x=i * (k + 2)) for i in range(36)] for k in range(4)]
    for idx, frs in enumerate(clips, start=1):
        _write_mp4_from_frames(p_dir / "03_visuals" / "flow_native_clips" / f"clip_{idx}.mp4", frs, fps=fps)
    _write_mp4_from_frames(p_dir / "05_assembly" / "final_shorts_1080x1920.mp4", sum(clips, []), fps=fps)

    (p_dir / "02_script" / "script.json").write_text(
        json.dumps({"schema": 7, "profile": "neuro_diorama", "style_profile": "lowpoly_pastel_v7", "sentences": ["S1.", "S2.", "S3.", "S4."]}),
        encoding="utf-8",
    )
    (p_dir / "03_visuals" / "visual_plan.json").write_text(
        json.dumps(
            {
                "schema": 7,
                "profile": "neuro_diorama",
                "style_profile": "lowpoly_pastel_v7",
                "clips": [
                    {"clip_number": i, "sentence_index": i, "act": 1, "grammar": "lowpoly_fullbleed_world", "camera": "pan_right", "scene": f"Scene {i}"}
                    for i in range(1, 5)
                ],
            }
        ),
        encoding="utf-8",
    )
    edl = {
        "schema": 7,
        "fps": 24,
        "total_duration_sec": 6.0,
        "cuts": [
            {
                "cut_index": i,
                "clip_index": i,
                "act": 1,
                "mode": "single",
                "grammar": "lowpoly_fullbleed_world",
                "camera_move": "pan_right",
                "sentence_indices": [i],
                "out_start_sec": (i - 1) * 1.5,
                "out_end_sec": i * 1.5,
                "duration_sec": 1.5,
                "src_start_sec": 0.0,
                "src_end_sec": 1.5,
            }
            for i in range(1, 5)
        ],
    }
    (p_dir / "05_assembly" / "edit_decision_list.json").write_text(json.dumps(edl), encoding="utf-8")

    rep = run_posthoc_semantic_qa(p_dir, render_strips=False, run_asr_sync=False)
    assert rep["cv_passed"] is True
    rev_path = init_posthoc_semantic_review_template(p_dir, qa_report=rep, auto_populate_from_cv=False)

    # 1. Blank template fails short-note & non-bool checks
    v_blank = validate_posthoc_semantic_review(p_dir, rep["final_mp4_sha256"], rep["edl_sha256"], 4)
    assert v_blank["valid"] is False
    assert any("review_notes_too_short" in x for x in v_blank["issues"])
    assert any("expresses_intended_meaning_not_bool" in x for x in v_blank["issues"])

    # 2. Copy-pasted identical notes across all 4 cuts (> POSTHOC_MAX_IDENTICAL_REVIEW_NOTES=3) rejected
    doc = json.loads(rev_path.read_text(encoding="utf-8"))
    for r in doc["cuts"]:
        r["observed_visual_summary"] = "Looks completely clear and matches the narration nicely."
        r["expresses_intended_meaning"] = True
    rev_path.write_text(json.dumps(doc), encoding="utf-8")
    v_boiler = validate_posthoc_semantic_review(p_dir, rep["final_mp4_sha256"], rep["edl_sha256"], 4)
    assert v_boiler["valid"] is False
    assert any("boilerplate_identical_review_notes" in x for x in v_boiler["issues"])

    # 3. Distinct notes, but reviewer rejects Cut #2 (`expresses_intended_meaning = False`) -> propagates consistently!
    doc["auto_populated"] = False
    for i, r in enumerate(doc["cuts"], start=1):
        r["observed_visual_summary"] = f"Unique visual observation for cut number {i} showing distinct granite props."
        r["expresses_intended_meaning"] = i != 2
    rev_path.write_text(json.dumps(doc), encoding="utf-8")
    rep_rej = run_posthoc_semantic_qa(p_dir, render_strips=False, run_asr_sync=False, require_review=True)
    assert rep_rej["passed"] is False
    assert 2 in rep_rej["summary"]["weak_cut_indices"]
    assert 2 in rep_rej["summary"]["regenerate_clip_indices"]
    rej_cut2 = {int(c["cut_index"]): c for c in rep_rej["cuts"]}[2]
    assert rej_cut2["passed"] is False
    assert "reviewer_flagged_unclear_expression" in rej_cut2["defects"]
    assert rep_rej["act_clarity_summary"]["act_1"]["weak_cuts"] == 1
    assert rep_rej["grammar_clarity_summary"]["lowpoly_fullbleed_world"]["weak_cuts"] == 1
    rej_src_by_num = {int(s["clip_number"]): s for s in rep_rej["source_clips"]}
    assert rej_src_by_num[2]["passed"] is False

    # 4. Stale MP4 SHA-256 mismatch detected AND does not poison a fresh render when require_review=False
    v_stale = validate_posthoc_semantic_review(p_dir, "deadbeef" * 8, rep["edl_sha256"], 4)
    assert v_stale["valid"] is False
    assert "stale_review_final_mp4_sha256_mismatch" in v_stale["issues"]

    doc["final_mp4_sha256"] = "deadbeef" * 8
    rev_path.write_text(json.dumps(doc), encoding="utf-8")
    rep_stale_ignored = run_posthoc_semantic_qa(p_dir, render_strips=False, run_asr_sync=False, require_review=False)
    assert rep_stale_ignored["cv_passed"] is True
    assert rep_stale_ignored["passed"] is True


def test_classic_v5_concat_fallback_and_knowledge_hub_roundtrip(tmp_path: Path) -> None:
    projects_root = tmp_path / "projects"
    kb_dir = tmp_path / "knowledge_base"
    asset_idx = tmp_path / "asset_library" / "index.jsonl"

    # Project A: Classic v5 project (no edit_decision_list.json, uses clip_narrations)
    p_v5 = projects_root / "psych_test_obedience"
    for sub in ("02_script", "03_visuals/flow_native_clips", "05_assembly"):
        (p_v5 / sub).mkdir(parents=True, exist_ok=True)
    c1 = [_make_pastel_world_frame(shift_x=i * 3) for i in range(36)]
    c2 = [_make_pastel_world_frame(shift_x=0, hand_offset=i * 2) for i in range(36)]
    _write_mp4_from_frames(p_v5 / "03_visuals" / "flow_native_clips" / "clip_1.mp4", c1, fps=24)
    _write_mp4_from_frames(p_v5 / "03_visuals" / "flow_native_clips" / "clip_2.mp4", c2, fps=24)
    _write_mp4_from_frames(p_v5 / "05_assembly" / "final_shorts_1080x1920.mp4", c1 + c2, fps=24)
    (p_v5 / "02_script" / "script.json").write_text(
        json.dumps({"clip_narrations": ["Experimenter points to switch.", "Subject presses lever."]}),
        encoding="utf-8",
    )
    (p_v5 / "03_visuals" / "visual_plan.json").write_text(
        json.dumps(
            {
                "schema_version": 5,
                "visual_mode": "BEHAVIORAL_PSYCH",
                "dossier": "milgram_obedience_shock",
                "shots": {
                    "setup": {"scene_id": "lab_room", "setting": "real_env", "shot_type": "cu", "camera": "pan_right"},
                    "symptom": {"scene_id": "shock_box", "setting": "real_env", "shot_type": "mcu", "camera": "locked_tripod"},
                },
            }
        ),
        encoding="utf-8",
    )
    (p_v5 / "03_visuals" / "flow_all_in_one_prompts.json").write_text(
        json.dumps(
            {
                "schema_version": 5,
                "clips": [
                    {"clip_number": 1, "role": "setup", "setting": "real_env", "camera_move": "pan_right", "scene": "Lab setup", "prompt": "Porcelain figure in lab"},
                    {"clip_number": 2, "role": "symptom", "setting": "real_env", "camera_move": "locked_tripod", "scene": "Shock lever", "prompt": "Hand presses switch"},
                ],
            }
        ),
        encoding="utf-8",
    )

    rep_v5 = run_posthoc_semantic_qa(p_v5, render_strips=False, run_asr_sync=False)
    assert rep_v5["summary"]["cut_count"] == 2
    assert rep_v5["passed"] is True

    manifest_v5 = build_asset_manifest(p_v5, write_library=False)
    assert manifest_v5["assets"][0]["asset_id"].endswith("_setup_cu")
    assert manifest_v5["assets"][0]["clarity_score"] is not None
    upsert_library(manifest_v5["assets"], index_path=asset_idx)

    # Project B: Schema v7 project with analogy + brain + location metadata
    p_v7 = projects_root / "gage_v7_kb_test"
    for sub in ("02_script", "03_visuals/flow_native_clips", "05_assembly"):
        (p_v7 / sub).mkdir(parents=True, exist_ok=True)
    b1 = [_make_pastel_world_frame(shift_x=i * 4) for i in range(36)]
    b2 = [_make_brain_frame(highlight=True, rot=int(12 * np.sin(i * 0.2))) for i in range(36)]
    _write_mp4_from_frames(p_v7 / "03_visuals" / "flow_native_clips" / "clip_1.mp4", b1, fps=24)
    _write_mp4_from_frames(p_v7 / "03_visuals" / "flow_native_clips" / "clip_2.mp4", b2, fps=24)
    _write_mp4_from_frames(p_v7 / "05_assembly" / "final_shorts_1080x1920.mp4", b1 + b2, fps=24)
    (p_v7 / "02_script" / "script.json").write_text(
        json.dumps(
            {
                "schema": 7,
                "profile": "neuro_diorama",
                "style_profile": "lowpoly_pastel_v7",
                "tts_rate": "+5%",
                "sentences": [
                    "Thirteen pounds of iron, heavier than a bowling ball.",
                    "Coral lesion severed the left prefrontal cortex.",
                ],
            }
        ),
        encoding="utf-8",
    )
    (p_v7 / "03_visuals" / "visual_plan.json").write_text(
        json.dumps(
            {
                "schema": 7,
                "profile": "neuro_diorama",
                "style_profile": "lowpoly_pastel_v7",
                "dossier": "phineas_gage_iron_rod",
                "clips": [
                    {"clip_number": 1, "sentence_index": 1, "act": 1, "grammar": "lowpoly_literal_analogy", "camera": "pan_right", "location_id": "bowling_scale_stage", "scene": "Bowling ball beside iron rod"},
                    {"clip_number": 2, "sentence_index": 2, "act": 3, "grammar": "lowpoly_matte_brain", "brain_mode": "matte_pastel_cortical_model", "brain_region": "ventromedial_prefrontal_cortex", "camera": "locked_tripod", "location_id": "pastel_brain_studio", "scene": "Coral lesion in prefrontal cortex"},
                ],
            }
        ),
        encoding="utf-8",
    )
    (p_v7 / "03_visuals" / "flow_all_in_one_prompts.json").write_text(
        json.dumps(
            {
                "schema_version": 7,
                "style_profile": "lowpoly_pastel_v7",
                "clips": [
                    {"clip_number": 1, "grammar": "lowpoly_literal_analogy", "camera_move": "pan_right", "scene": "Bowling ball beside iron rod", "prompt": "Low-poly bowling ball scale"},
                    {"clip_number": 2, "grammar": "lowpoly_matte_brain", "camera_move": "locked_tripod", "scene": "Coral lesion in prefrontal cortex", "prompt": "Low-poly matte prefrontal brain"},
                ],
            }
        ),
        encoding="utf-8",
    )
    (p_v7 / "03_visuals" / "episode_qa_contract.json").write_text(
        json.dumps(
            {
                "analogy_locks": [
                    {
                        "sentence_index": 1,
                        "spoken_phrase": "bowling ball",
                        "sentence": "Thirteen pounds of iron, heavier than a bowling ball.",
                        "cv_signature": "spherical_bowling_scale",
                        "bound_clip_numbers": [1],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    (p_v7 / "05_assembly" / "edit_decision_list.json").write_text(
        json.dumps(
            {
                "schema": 7,
                "fps": 24,
                "total_duration_sec": 3.0,
                "cuts": [
                    {"cut_index": 1, "clip_index": 1, "act": 1, "mode": "single", "grammar": "lowpoly_literal_analogy", "camera_move": "pan_right", "sentence_indices": [1], "out_start_sec": 0.0, "out_end_sec": 1.5, "duration_sec": 1.5, "src_start_sec": 0.0, "src_end_sec": 1.5},
                    {"cut_index": 2, "clip_index": 2, "act": 3, "mode": "single", "grammar": "lowpoly_matte_brain", "camera_move": "locked_tripod", "sentence_indices": [2], "out_start_sec": 1.5, "out_end_sec": 3.0, "duration_sec": 1.5, "src_start_sec": 0.0, "src_end_sec": 1.5},
                ],
            }
        ),
        encoding="utf-8",
    )

    sync_res = sync_all_projects_to_knowledge_base(projects_dir=projects_root, kb_dir=kb_dir, run_missing_posthoc=True)
    assert sync_res["count"] == 2
    # Idempotence: syncing again does not duplicate rows
    sync_project_to_knowledge_base(p_v7, kb_dir=kb_dir, write_asset_library=False)
    upsert_library(build_asset_manifest(p_v7, write_library=False)["assets"], index_path=asset_idx)

    paths = ensure_knowledge_base_layout(kb_dir)
    ep_lines = [ln for ln in paths["episodes_index"].read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(ep_lines) == 2

    assert len(query_knowledge_base(pack="clips", query="prefrontal", kb_dir=kb_dir, asset_index_path=asset_idx)) >= 1
    assert len(query_knowledge_base(pack="prompts", grammar="lowpoly_matte_brain", min_clarity=80.0, kb_dir=kb_dir)) == 1
    assert len(query_knowledge_base(pack="analogies", query="bowling", kb_dir=kb_dir)) == 1
    assert len(query_knowledge_base(pack="brain_models", query="prefrontal", kb_dir=kb_dir)) == 1
    assert len(query_knowledge_base(pack="locations", query="bowling_scale_stage", kb_dir=kb_dir)) == 1

    with pytest.raises(ValueError, match="Unsupported pack"):
        query_knowledge_base(pack="nonexistent_pack", kb_dir=kb_dir)


def test_unequal_concat_list_no_false_mid_cut_morph_and_empty_script_kb_telemetry(tmp_path: Path) -> None:
    """Regression test: unequal clip durations in 05_assembly/concat_list.txt + 0-byte script.json
    must NOT slice across adjacent hard cuts (causing false mid_cut_morph_hist_jump) and must still
    populate word_count, wpm, doi, and voice telemetry in knowledge_hub."""
    p_dir = tmp_path / "psych_unequal_concat"
    for sub in ("01_ideation", "02_script", "03_visuals/flow_native_clips", "04_audio", "05_assembly", "06_publish"):
        (p_dir / sub).mkdir(parents=True, exist_ok=True)
    kb_dir = tmp_path / "kb"

    fps = 24
    # Clip 1 = 1.0s (24 frames) pastel warm world; Clip 2 = 3.0s (72 frames) high-contrast magenta/cyan palette
    c1 = [_make_pastel_world_frame(shift_x=i * 4) for i in range(24)]
    c2: list[np.ndarray] = []
    for i in range(72):
        f2 = np.full((960, 540, 3), (42, 34, 48), dtype=np.uint8)
        cv2.circle(f2, (270 + int(14 * np.sin(i * 0.25)), 380), 130, (235, 190, 40), -1)
        cv2.rectangle(f2, (150, 260), (390, 500), (245, 245, 250), 3)
        c2.append(f2)
    _write_mp4_from_frames(p_dir / "03_visuals" / "flow_native_clips" / "clip_1.mp4", c1, fps=fps)
    _write_mp4_from_frames(p_dir / "03_visuals" / "flow_native_clips" / "clip_2.mp4", c2, fps=fps)
    _write_mp4_from_frames(p_dir / "05_assembly" / "final_shorts_1080x1920.mp4", c1 + c2, fps=fps)

    # 0-byte script.json & research_card.json (mirrors psych_01..03 on disk)
    (p_dir / "02_script" / "script.json").write_text("", encoding="utf-8")
    (p_dir / "01_ideation" / "research_card.json").write_text("", encoding="utf-8")

    concat_txt = (
        f"file '{(p_dir / '03_visuals' / 'flow_native_clips' / 'clip_1.mp4').as_posix()}'\n"
        "duration 1.000\n"
        f"file '{(p_dir / '03_visuals' / 'flow_native_clips' / 'clip_2.mp4').as_posix()}'\n"
        "duration 3.000\n"
    )
    (p_dir / "05_assembly" / "concat_list.txt").write_text(concat_txt, encoding="utf-8")
    (p_dir / "03_visuals" / "flow_all_in_one_prompts.json").write_text(
        json.dumps(
            {
                "schema_version": 5,
                "clips": [
                    {
                        "clip_number": 1,
                        "role": "hook",
                        "setting": "real_env",
                        "camera_move": "pan_right",
                        "scene": "Warm porcelain room",
                        "spoken_narration": "Deep brain circuits lock daily habits onto automatic pilot.",
                        "prompt": "Warm porcelain scene",
                    },
                    {
                        "clip_number": 2,
                        "role": "mechanism",
                        "setting": "brain_void",
                        "camera_move": "locked_tripod",
                        "scene": "Cyan neural hub",
                        "spoken_narration": "Basal ganglia chunk repeated actions into a single firing burst.",
                        "prompt": "Cyan hub pulse",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    (p_dir / "04_audio" / "audio_master_spec.json").write_text(
        json.dumps(
            {
                "voice_profile": "Puck (Google Omni 1.1 Native Storyteller)",
                "av_speedup_factor": 1.08,
                "target_speech_seconds": 4.0,
            }
        ),
        encoding="utf-8",
    )
    (p_dir / "06_publish" / "metadata.json").write_text(
        json.dumps(
            {
                "title": "Why Deep Brain Loops Lock Habits on Autopilot",
                "pillar": "brain_basics",
                "description": "Why Deep Brain Loops Lock Habits on Autopilot\n\nSource & Verification: 10.1038/nrn2787\n#Shorts",
            }
        ),
        encoding="utf-8",
    )

    rep = run_posthoc_semantic_qa(p_dir, render_strips=False, run_asr_sync=False)
    assert rep["passed"] is True, f"Unequal concat_list cuts caused false failure: {rep['cuts']}"
    assert rep["cuts"][0]["out_end_sec"] == pytest.approx(1.0, abs=0.05)
    assert rep["cuts"][1]["out_start_sec"] == pytest.approx(1.0, abs=0.05)
    assert all("mid_cut_morph_hist_jump" not in d for c in rep["cuts"] for d in c["defects"])
    assert rep["edl_sha256"] != ""

    sync_project_to_knowledge_base(p_dir, posthoc_report=rep, kb_dir=kb_dir, write_asset_library=False)
    paths = ensure_knowledge_base_layout(kb_dir)
    ep_row = json.loads(paths["episodes_index"].read_text(encoding="utf-8").strip())
    assert ep_row["word_count"] == 19
    assert ep_row["sentence_count"] == 2
    assert ep_row["wpm"] is not None and ep_row["wpm"] > 100.0
    assert ep_row["doi"] == "10.1038/nrn2787"
    assert ep_row["pillar"] == "brain_basics"
    assert "Puck" in str(ep_row["tts_voice"])
    assert ep_row["tts_speed"] == 1.08


def test_split_secondary_clip_attribution_and_corrupted_unused_clip_detection(tmp_path: Path) -> None:
    """Regression test: when a split_hstack cut fails because secondary_clip_index is frozen/blurry,
    remediation must blame secondary_clip_index (not healthy clip_index), and 0-byte unused clips
    must be flagged in corrupted_source_clips without crashing."""
    p_dir = tmp_path / "ep_split_secondary"
    for sub in ("02_script", "03_visuals/flow_native_clips", "05_assembly"):
        (p_dir / sub).mkdir(parents=True, exist_ok=True)

    fps = 24
    # Clip 1 = healthy moving pastel world; Clip 2 = completely flat blurry grey (broken secondary pane); Clip 3 = 0-byte corrupted file
    c1 = [_make_pastel_world_frame(shift_x=i * 5, hand_offset=i * 2) for i in range(48)]
    c2_broken = [np.full((960, 540, 3), (180, 180, 180), dtype=np.uint8) for _ in range(48)]
    _write_mp4_from_frames(p_dir / "03_visuals" / "flow_native_clips" / "clip_1.mp4", c1, fps=fps)
    _write_mp4_from_frames(p_dir / "03_visuals" / "flow_native_clips" / "clip_2.mp4", c2_broken, fps=fps)
    (p_dir / "03_visuals" / "flow_native_clips" / "clip_3.mp4").write_bytes(b"")

    # Assembled split_hstack cut: stalled pan_right (0 motion) with fine static texture so MP4 > 10KB and proper black divider
    rng = np.random.default_rng(42)
    static_sf = np.zeros((960, 540, 3), dtype=np.uint8)
    static_sf[:, :270] = np.clip(c1[0][:, 135:405].astype(np.int16) + rng.integers(-14, 15, (960, 270, 3)), 0, 255).astype(np.uint8)
    static_sf[:, 270:] = (180, 180, 180)
    static_sf[:, 267:273] = (0, 0, 0)
    split_assembled = [static_sf.copy() for _ in range(36)]
    _write_mp4_from_frames(p_dir / "05_assembly" / "final_shorts_1080x1920.mp4", split_assembled, fps=fps)

    (p_dir / "02_script" / "script.json").write_text(
        json.dumps({"schema": 7, "profile": "neuro_diorama", "style_profile": "lowpoly_pastel_v7", "sentences": ["Comparison of two pathways."]}),
        encoding="utf-8",
    )
    (p_dir / "03_visuals" / "visual_plan.json").write_text(
        json.dumps(
            {
                "schema": 7,
                "profile": "neuro_diorama",
                "style_profile": "lowpoly_pastel_v7",
                "clips": [
                    {"clip_number": 1, "sentence_index": 1, "act": 4, "grammar": "lowpoly_fullbleed_world", "camera": "pan_right", "scene": "Left healthy pathway"},
                    {"clip_number": 2, "sentence_index": 1, "act": 4, "grammar": "lowpoly_matte_brain", "camera": "pan_right", "scene": "Right damaged pathway"},
                    {"clip_number": 3, "sentence_index": 1, "act": 4, "grammar": "lowpoly_fullbleed_world", "camera": "locked_tripod", "scene": "Unused spare clip"},
                ],
            }
        ),
        encoding="utf-8",
    )
    (p_dir / "03_visuals" / "flow_all_in_one_prompts.json").write_text(
        json.dumps(
            {
                "schema_version": 7,
                "style_profile": "lowpoly_pastel_v7",
                "clips": [
                    {"clip_number": 1, "grammar": "lowpoly_fullbleed_world", "camera_move": "pan_right", "scene": "Left", "prompt": "P1"},
                    {"clip_number": 2, "grammar": "lowpoly_matte_brain", "camera_move": "pan_right", "scene": "Right", "prompt": "P2"},
                    {"clip_number": 3, "grammar": "lowpoly_fullbleed_world", "camera_move": "locked_tripod", "scene": "Spare", "prompt": "P3"},
                ],
            }
        ),
        encoding="utf-8",
    )
    edl = {
        "schema": 7,
        "fps": 24,
        "total_duration_sec": 1.5,
        "cuts": [
            {
                "cut_index": 1,
                "clip_index": 1,
                "secondary_clip_index": 2,
                "secondary_src_span": [0.25, 1.75],
                "act": 4,
                "mode": "split_hstack",
                "grammar": "lowpoly_fullbleed_world",
                "camera_move": "pan_right",
                "sentence_indices": [1],
                "out_start_sec": 0.0,
                "out_end_sec": 1.5,
                "duration_sec": 1.5,
                "src_start_sec": 0.0,
                "src_end_sec": 1.5,
            }
        ],
    }
    (p_dir / "05_assembly" / "edit_decision_list.json").write_text(json.dumps(edl), encoding="utf-8")

    rep = run_posthoc_semantic_qa(p_dir, render_strips=False, run_asr_sync=False)
    assert rep["passed"] is False
    cut1 = rep["cuts"][0]
    assert cut1["remediation"] == "regenerate_flow_clip"
    assert cut1["offending_clip_indices"] == [2]
    assert rep["summary"]["regenerate_clip_indices"] == [2]
    assert rep["summary"]["corrupted_source_clips"] == [3]
    src_by_num = {int(s["clip_number"]): s for s in rep["source_clips"]}
    assert "corrupted_or_unreadable_source_clip" in src_by_num[3]["defects"]
    assert src_by_num[3]["passed"] is False

    manifest = build_asset_manifest(p_dir, write_library=False)
    by_num = {int(a["clip_number"]): a for a in manifest["assets"]}
    assert by_num[1]["used_in_short"]["source_in_sec"] == 0.0
    assert by_num[1]["used_in_short"]["source_out_sec"] == 1.5
    assert by_num[2]["used_in_short"]["source_in_sec"] == 0.25
    assert by_num[2]["used_in_short"]["source_out_sec"] == 1.75


def test_v7_source_window_selector_skips_empty_wall_preroll_and_honors_override(tmp_path: Path) -> None:
    """Regression test: _select_v7_source_window must skip [0..1.5s] empty-wall tilt_down pre-roll
    even when bottom-edge motion is non-zero, selecting the [2.0..4.0s] focal-occupied window."""
    from pipeline.diorama_assembler import _select_v7_source_window

    clip_path = tmp_path / "tilt_down_brain.mp4"
    empty_top_frames: list[np.ndarray] = []
    for i in range(48):  # 0.0..2.0s: empty upper-center wall, moving object low at y=0.78
        ef = np.full((960, 540, 3), (194, 198, 204), dtype=np.uint8)
        by = int(960 * 0.78) - (i % 8) * 3
        cv2.rectangle(ef, (140, by), (400, by + 120), (68, 92, 162), -1)
        empty_top_frames.append(ef)
    occupied_frames = [_make_brain_frame(highlight=True, rot=int(12 * np.sin(i * 0.25))) for i in range(72)]  # 2.0..5.0s
    _write_mp4_from_frames(clip_path, empty_top_frames + occupied_frames, fps=24)

    s_start, s_span = _select_v7_source_window(clip_path, clip_dur=5.0, out_dur=1.5)
    assert s_start >= 1.85, f"Expected window selector to skip [0..2.0s] empty upper-center pre-roll, got start={s_start}"
    assert s_span == pytest.approx(1.5, abs=0.05)

    o_start, o_span = _select_v7_source_window(clip_path, clip_dur=5.0, out_dur=1.5, override_src_start_sec=2.4)
    assert o_start == pytest.approx(2.4, abs=0.05)
    assert o_span == pytest.approx(1.5, abs=0.05)


def test_posthoc_qa_multibeat_sentence_analogy_sync_does_not_flag_beat1(tmp_path: Path, monkeypatch) -> None:
    """Regression test: when a sentence ('A metal shield hid Henry's hand and yellow pencil.')
    is split across Beat 1 [0.0..1.0s] and Beat 2 [1.0..2.5s] and 'pencil' is spoken at 2.1s inside Beat 2,
    Beat 1 must NOT be falsely flagged for analogy_audio_visual_desync, whereas true desync outside [0.0..2.5s] MUST fail."""
    import pipeline.posthoc_semantic_qa as psq

    p_dir = tmp_path / "ep_multibeat_sync"
    for sub in ("02_script", "03_visuals/flow_native_clips", "04_audio", "05_assembly"):
        (p_dir / sub).mkdir(parents=True, exist_ok=True)

    c1 = [_make_pastel_world_frame(hand_offset=int(18 * np.sin(i * 0.25))) for i in range(48)]
    c2 = [_make_pastel_world_frame(hand_offset=int(18 * np.cos(i * 0.25))) for i in range(48)]
    _write_mp4_from_frames(p_dir / "03_visuals" / "flow_native_clips" / "clip_1.mp4", c1, fps=24)
    _write_mp4_from_frames(p_dir / "03_visuals" / "flow_native_clips" / "clip_2.mp4", c2, fps=24)
    _write_mp4_from_frames(p_dir / "05_assembly" / "final_shorts_1080x1920.mp4", c1[:24] + c2[:36], fps=24)

    (p_dir / "02_script" / "script.json").write_text(
        json.dumps(
            {
                "schema": 7,
                "profile": "neuro_diorama",
                "style_profile": "lowpoly_pastel_v7",
                "sentences": ["A metal shield hid Henry's hand and yellow pencil."],
            }
        ),
        encoding="utf-8",
    )
    (p_dir / "03_visuals" / "visual_plan.json").write_text(
        json.dumps(
            {
                "schema": 7,
                "profile": "neuro_diorama",
                "style_profile": "lowpoly_pastel_v7",
                "clips": [
                    {"clip_number": 1, "sentence_index": 1, "beat_index": 1, "grammar": "lowpoly_hands_closeup", "camera": "locked_tripod", "scene": "Hands latch metal shield above star."},
                    {"clip_number": 2, "sentence_index": 1, "beat_index": 2, "grammar": "lowpoly_pov_hands", "camera": "locked_tripod", "scene": "Hand grips yellow pencil under metal shield."},
                ],
            }
        ),
        encoding="utf-8",
    )
    (p_dir / "03_visuals" / "episode_qa_contract.json").write_text(
        json.dumps(
            {
                "analogy_locks": [
                    {
                        "analogy_id": "pencil",
                        "spoken_phrase": "pencil",
                        "sentence_index": 1,
                        "required_any_nouns": ["pencil"],
                        "cv_signature": None,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    (p_dir / "05_assembly" / "edit_decision_list.json").write_text(
        json.dumps(
            {
                "schema": 7,
                "fps": 24,
                "total_duration_sec": 2.5,
                "cuts": [
                    {"cut_index": 1, "clip_index": 1, "act": 5, "mode": "single", "grammar": "lowpoly_hands_closeup", "camera_move": "locked_tripod", "sentence_indices": [1], "out_start_sec": 0.0, "out_end_sec": 1.0, "duration_sec": 1.0, "src_start_sec": 0.0, "src_end_sec": 1.0},
                    {"cut_index": 2, "clip_index": 2, "act": 5, "mode": "single", "grammar": "lowpoly_pov_hands", "camera_move": "locked_tripod", "sentence_indices": [1], "out_start_sec": 1.0, "out_end_sec": 2.5, "duration_sec": 1.5, "src_start_sec": 0.0, "src_end_sec": 1.5},
                ],
            }
        ),
        encoding="utf-8",
    )
    (p_dir / "04_audio" / "subtitles.ass").write_text(
        "[Events]\nDialogue: 0,0:00:00.05,0:00:02.45,Default,,0,0,0,,yellow pencil\n",
        encoding="utf-8",
    )

    # 1. 'pencil' spoken at 2.10s (inside Beat 2 [1.0, 2.5]) -> BOTH Beat 1 and Beat 2 pass!
    monkeypatch.setattr(psq, "_asr_word_timeline_from_mp4", lambda _p: [(2.10, 2.40, "pencil")])
    rep_ok = run_posthoc_semantic_qa(p_dir, render_strips=False, run_asr_sync=True)
    assert rep_ok["passed"] is True, f"Beat 1 falsely flagged on multi-beat sentence: {rep_ok['cuts']}"

    # 2. 'pencil' spoken at 3.80s (genuinely desynced outside [0.0, 2.5]) -> MUST fail!
    monkeypatch.setattr(psq, "_asr_word_timeline_from_mp4", lambda _p: [(3.80, 4.10, "pencil")])
    rep_bad = run_posthoc_semantic_qa(p_dir, render_strips=False, run_asr_sync=True)
    assert rep_bad["passed"] is False
    assert any("analogy_audio_visual_desync" in d for c in rep_bad["cuts"] for d in c["defects"])


