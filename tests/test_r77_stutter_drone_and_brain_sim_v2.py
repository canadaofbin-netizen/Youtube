from __future__ import annotations

import json
from pathlib import Path

import cv2
import imageio_ffmpeg
import numpy as np
import pytest

from pipeline import (
    anatomy_label_overlay as alo,
    config,
    depiction_rules as dr,
    diorama_assembler as da,
    plain_language as pl,
    posthoc_semantic_qa as psq,
    prompt_quality_v5 as pq5,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
SHOWCASE_A_DIR = REPO_ROOT / "BCI_Shorts_Channel/projects/v8_brain_only_capgras_showcase_r77"
EP08_V3_DIR = REPO_ROOT / "BCI_Shorts_Channel/projects/v8_ep08_capgras_imposter_delusion_r77"
EP08_R76_CLIP17 = (
    REPO_ROOT / "BCI_Shorts_Channel/projects/v8_ep08_capgras_imposter_delusion_r76/03_visuals/flow_native_clips/clip_17.mp4"
)
EP08_V1_CLIP1 = (
    REPO_ROOT / "BCI_Shorts_Channel/projects/v8_ep08_capgras_imposter_delusion/03_visuals/flow_native_clips/clip_1.mp4"
)


def _write_moving_24fps_mp4(out_path: Path, *, width: int = 360, height: int = 640, fps: float = 24.0, sec: float = 3.0) -> None:
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(out_path), fourcc, fps, (width, height))
    assert writer.isOpened(), f"VideoWriter failed for {out_path}"
    n_frames = int(round(fps * sec))
    try:
        for i in range(n_frames):
            frame = np.full((height, width, 3), 24, dtype=np.uint8)
            x0 = 20 + int((width - 100) * (i / max(1, n_frames - 1)))
            y0 = 120 + int((height - 260) * (i / max(1, n_frames - 1)))
            cv2.rectangle(frame, (x0, y0), (x0 + 64, y0 + 64), (240, 210, 80), -1)
            cv2.circle(frame, (x0 + 32, y0 + 32), 16, (40, 90, 220), -1)
            writer.write(frame)
    finally:
        writer.release()


def test_r77_select_window_clamp_and_optical_flow_upsample(tmp_path: Path) -> None:
    s0, s1 = da._select_v7_source_window(tmp_path / "dummy.mp4", 7.92, 4.50)
    assert s0 >= 0.0
    assert s1 <= 7.92
    assert (s1 - s0) == pytest.approx(4.50, abs=0.25)

    src_mp4 = tmp_path / "moving_24fps.mp4"
    _write_moving_24fps_mp4(src_mp4, fps=24.0, sec=3.0)
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    res = da._upsample_clip_window_optical_flow(ff, src_mp4, 0.10, 2.60, 30)
    assert res is not None, "Optical-flow upsampler returned None on valid moving 24fps clip"
    up_path, up_t0 = res
    assert up_path.is_file()
    assert 0.0 <= up_t0 <= 0.20

    cap = cv2.VideoCapture(str(up_path))
    try:
        up_fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
        up_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    finally:
        cap.release()
    up_dur = up_frames / max(1.0, up_fps)
    assert up_fps == pytest.approx(30.0, abs=0.5)
    assert up_frames >= 70
    assert up_dur >= 2.4

    smooth = psq.evaluate_cut_temporal_smoothness(
        up_path,
        [
            {
                "cut_index": 1,
                "out_start_sec": 0.0,
                "out_end_sec": min(2.3, up_dur - 0.05),
                "camera_move": "gentle_push_in",
                "grammar": "expressive_vinyl_world",
            }
        ],
    )
    assert 1 in smooth
    assert smooth[1]["passed"] is True, f"Optical-flow upsample had frozen frames: {smooth[1]}"
    assert smooth[1]["max_consecutive_frozen_frames"] <= 1


def test_r77_circular_lens_border_intrusion_detector() -> None:
    rng = np.random.default_rng(42)
    # Textured interior + clean full-frame texture -> not detected
    clean_frame = rng.integers(50, 210, size=(320, 180, 3), dtype=np.uint8)
    res_clean = psq.detect_circular_lens_border_intrusion([clean_frame.copy() for _ in range(4)])
    assert res_clean["detected"] is False, f"False positive on uniform textured frame: {res_clean}"

    # Textured interior + dark smooth circular bezel corners -> detected
    vignette_frame = clean_frame.copy()
    yy, xx = np.ogrid[:320, :180]
    corner_mask = ((xx - 90) ** 2 / 72**2 + (yy - 160) ** 2 / 138**2) > 1.0
    vignette_frame[corner_mask] = 6
    res_vig = psq.detect_circular_lens_border_intrusion([vignette_frame.copy() for _ in range(4)])
    assert res_vig["detected"] is True, f"Missed circular vignette border: {res_vig}"

    if EP08_R76_CLIP17.is_file() and EP08_V1_CLIP1.is_file():
        def _sample(p: Path) -> list[np.ndarray]:
            cap = cv2.VideoCapture(str(p))
            frames = []
            try:
                for idx in range(0, 120, 15):
                    cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
                    ok, f = cap.read()
                    if ok and f is not None:
                        frames.append(f)
            finally:
                cap.release()
            return frames

        assert psq.detect_circular_lens_border_intrusion(_sample(EP08_R76_CLIP17))["detected"] is True
        assert psq.detect_circular_lens_border_intrusion(_sample(EP08_V1_CLIP1))["detected"] is False


def test_r77_hardware_ban_and_frozen_exemptions() -> None:
    bad_issues = dr.validate_expressive_v8_scene(
        "fpv drone camera lens with visible matte camera body and viewfinder",
        grammar="expressive_vinyl_world",
        camera_move="gentle_push_in",
    )
    assert any("[r77_hardware_ban]" in msg for msg in bad_issues), f"Expected hardware ban issue, got {bad_issues}"

    radcliffe_issues = dr.validate_expressive_v8_scene(
        "two clothed matte cream-white vinyl students walking past sunlit Radcliffe Camera quadrangle",
        grammar="expressive_vinyl_world",
        camera_move="gentle_push_in",
    )
    assert not any("[r77_hardware_ban]" in msg for msg in radcliffe_issues), radcliffe_issues

    legacy_allowed = dr.validate_expressive_v8_scene(
        "fpv drone camera lens flying into the sunlit courtyard",
        grammar="expressive_vinyl_world",
        camera_move="gentle_push_in",
        allow_legacy_hardware=True,
    )
    assert not any("[r77_hardware_ban]" in msg for msg in legacy_allowed), legacy_allowed

    assert "camera lens" in dr.FLOW_CAMERA_HARDWARE_NEGATIVE_GUARD.lower()
    assert "v8_ep08_capgras_imposter_delusion" in config.PRE_R77_FROZEN_V8_PROJECTS
    assert "v8_ep08_capgras_imposter_delusion_r76" in config.PRE_R77_FROZEN_V8_PROJECTS


def test_r77_anatomy_callout_non_overlapping_leader_band() -> None:
    callout = {
        "callout_mode": "pathway_relay",
        "neural_state": "active",
        "r76_clinical_matte": True,
        "start_display_title": "Fusiform",
        "start_short_role": "Face Detector",
        "start_anchor_xy": [0.34, 0.50],
        "start_accent_rgb": [0, 212, 255],
        "end_display_title": "Amygdala",
        "end_short_role": "Emotional Center",
        "end_anchor_xy": [0.68, 0.54],
        "end_accent_rgb": [0, 212, 255],
        "pathway_subtitle": "Visual Signal -> Warmth",
    }
    rgba = alo.render_anatomy_callout_rgba_frame(callout, t_rel=1.0, total_dur=4.0)
    arr = np.asarray(rgba)
    assert arr.shape == (1920, 1080, 4)
    # Clamp safe vertical band [DATA_STAMP_Y_FRAC_RANGE[0] * 1920 .. 0.65 * 1920]
    safe_y_top = int(round(float(config.DATA_STAMP_Y_FRAC_RANGE[0]) * 1920))
    safe_y_bot = int(round(0.65 * 1920))
    assert not np.any(arr[:safe_y_top, :, 3] > 0)
    assert not np.any(arr[safe_y_bot + 1 :, :, 3] > 0)
    assert np.any(arr[safe_y_top : safe_y_bot + 1, :, 3] > 0)


def test_r77n_conversational_fk_pseudo_jargon_and_brain_sim_only_mode() -> None:
    sample_lines = [
        "Why did this man trust his mom on the phone, yet call her a fake in person?",
        "After a car crash, a patient told doctors his own mom looked like a stranger.",
        "You see, his vision spot matched her face just fine.",
        "But the crash cut the wire from that face spot to his amygdala, the warmth spot.",
        "Her voice took a separate sound wire straight to his emotion center.",
        "When that second signal landed, warm feeling came right back.",
    ]
    assert pl.fk_grade_conversational(" ".join(sample_lines)) <= config.EXPRESSIVE_V8_R77N_MAX_FK_GRADE

    bad_lines = list(sample_lines)
    bad_lines[2] = "Wait, his face part and fear hub talked right away in your head."
    plan = {
        "project_id": "test_r77n_unit",
        "profile": "neuro_diorama",
        "style_profile": "expressive_25d_v8",
        "r73_mode": True,
        "r77n_conversational_storytelling": True,
    }
    iss = pq5.validate_script_spine_v8(bad_lines, plan, plan=plan, project_id="test_r77n_unit")
    assert any("face part" in m.lower() or "fear hub" in m.lower() for m in iss), f"Expected pseudo-jargon flag, got {iss}"

    sim_only_plan = {
        "render_mode": config.BRAIN_SIM_ONLY_RENDER_MODE,
        "clips": [{"clip_number": i, "grammar": "brain_simulator_3d"} for i in range(1, 9)],
    }
    mixed_plan = {
        "render_mode": "mixed",
        "clips": [
            {"clip_number": 1, "grammar": "expressive_vinyl_world"},
            {"clip_number": 2, "grammar": "brain_simulator_3d"},
        ],
    }
    assert config.is_brain_sim_only_plan(sim_only_plan) is True
    assert config.is_brain_sim_only_plan(mixed_plan) is False

    if (SHOWCASE_A_DIR / "03_visuals/visual_plan.json").is_file():
        vp_a = json.loads((SHOWCASE_A_DIR / "03_visuals/visual_plan.json").read_text(encoding="utf-8"))
        sc_a = json.loads((SHOWCASE_A_DIR / "02_script/script.json").read_text(encoding="utf-8"))
        assert config.is_brain_sim_only_plan(vp_a) is True
        assert pl.fk_grade_conversational(" ".join(sc_a["narration_sentences"])) <= 6.5

    if (EP08_V3_DIR / "03_visuals/visual_plan.json").is_file():
        vp_b = json.loads((EP08_V3_DIR / "03_visuals/visual_plan.json").read_text(encoding="utf-8"))
        sc_b = json.loads((EP08_V3_DIR / "02_script/script.json").read_text(encoding="utf-8"))
        assert config.is_brain_sim_only_plan(vp_b) is False
        assert pl.fk_grade_conversational(" ".join(sc_b["narration_sentences"])) <= 6.5
