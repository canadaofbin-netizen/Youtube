"""
Rule R78-M / R78-H / R78-V Regression Suite:
  - Functional terminology in anatomy_map.py ("Emotional Center", "Reality-Checker")
  - Brain simulator cool matte silver (#B8C0C7, B > G > R, zero #DFDDD7 warm ivory),
    dual material_modes ("xray_glass", "cool_matte_silver_31"), 1p/3p camera plans,
    clip_start = 0.0015, and SQ6 dark-void luma acceptance
  - Uncrossed r78m_dual fountain-pen callouts, callout_enabled=False suppression,
    non-crossing X clamp, vertical safe band, and DQ10 header detection
  - ElevenLabs v4 R78-V 5-tone (tag, stability, style) settings & legacy cache preservation
  - Acoustic P11_siren_5tone_f0_range F0 semitone span & lift-vs-drop gate
  - AGENTS.md <= 78 lines & < 10,240 bytes with R78-M/H/V documented
"""

from __future__ import annotations

import json
import wave
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

import pipeline.config as cfg
from pipeline import (
    anatomy_label_overlay as alo,
    anatomy_map,
    brain_simulator_blender as bsb,
    dynamic_episode_qa as dq,
    elevenlabs_tts as el,
    prosody as pr,
)


def _write_pcm_wav(path: Path, samples: np.ndarray, sr: int = 16000) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pcm_i16 = np.clip(samples * 32767.0, -32768, 32767).astype(np.int16)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(pcm_i16.tobytes())


def _harmonic_tone(freqs_hz: list[float], dur_sec: float, sr: int = 16000) -> np.ndarray:
    n = int(round(dur_sec * sr))
    t = np.linspace(0.0, dur_sec, n, endpoint=False)
    f_inst = np.interp(np.linspace(0.0, 1.0, n), np.linspace(0.0, 1.0, len(freqs_hz)), freqs_hz)
    phase = 2.0 * np.pi * np.cumsum(f_inst) / float(sr)
    sig = 0.42 * np.sin(phase) + 0.14 * np.sin(2.0 * phase)
    env = np.minimum(1.0, np.minimum(t / 0.03, (dur_sec - t) / 0.03))
    return (sig * np.clip(env, 0.0, 1.0)).astype(np.float32)


def test_r78_anatomy_map_functional_names() -> None:
    assert anatomy_map.ANATOMY_SCREEN_ANCHORS["amygdala"]["short_role"] == "Emotional Center"
    assert anatomy_map.ANATOMY_SCREEN_ANCHORS["prefrontal cortex"]["short_role"] == "Reality-Checker"
    assert anatomy_map.ANATOMY_SCREEN_ANCHORS["ventromedial prefrontal cortex"]["short_role"] == "Reality-Checker"


def test_r78m_blender_dual_material_camera_and_sq6(tmp_path: Path) -> None:
    hex_c = bsb.CLINICAL_PALETTE_HEX["cortex"]
    assert hex_c == "#B8C0C7"
    r_c, g_c, b_c = int(hex_c[1:3], 16), int(hex_c[3:5], 16), int(hex_c[5:7], 16)
    assert b_c > g_c > r_c, f"Expected cool silver-gray B > G > R, got {hex_c}"
    assert bsb.R78M_MATERIAL_MODES == ("xray_glass", "cool_matte_silver_31")

    manifest = json.loads(bsb.ATLAS_MANIFEST_PATH.read_text(encoding="utf-8"))
    tract = bsb.resolve_anatomical_tract_points("fusiform face area", "amygdala", manifest)

    p1 = bsb._plan_drone_camera_keyframes(
        {"camera_move": "1p_nerve_canyon_drone"},
        manifest,
        "fusiform face area",
        "amygdala",
        tract,
    )
    assert p1["camera_move"] == "1p_nerve_canyon_drone"
    assert p1["lens_mm"] == 32.0
    assert len(p1["eye_waypoints_m"]) == 4

    p3 = bsb._plan_drone_camera_keyframes(
        {"camera_move": "3p_region_shutdown_pullout"},
        manifest,
        "fusiform face area",
        "amygdala",
        tract,
    )
    assert p3["camera_move"] == "3p_region_shutdown_pullout"
    assert p3["lens_mm"] == 42.0
    assert len(p3["eye_waypoints_m"]) == 4

    runner_src = bsb._build_blender_runner_script(
        tmp_path / "cfg.json",
        tmp_path / "frames",
        tmp_path / "track.json",
    )
    assert "clip_start = 0.0015" in runner_src
    assert "xray_glass" in runner_src
    assert "mid_sagittal_split" in runner_src

    fake_frames = [
        {
            "anchors": {
                "start": {"x_px": 360.0 + i * 2.0, "y_px": 920.0},
                "end": {"x_px": 680.0, "y_px": 940.0},
            }
        }
        for i in range(15)
    ]
    fake_cfg = {
        "start_key": "fusiform face area",
        "end_key": "amygdala",
        "neural_state": "severed",
        "tract_pts_mm": tract,
        "anchors_mm": {
            "start": tract[0],
            "end": tract[-1],
        },
    }
    qa = bsb.evaluate_simulator_qa(
        render_cfg=fake_cfg,
        manifest=manifest,
        track_doc={"frames": fake_frames},
        pixel_stats={"mean_luma": 10.5, "max_p995_luma": 238.0, "file_size_bytes": 250000},
        width=1080,
        height=1920,
    )
    assert qa["gates"]["SQ6_zero_glow_clinical_exposure"] is True
    assert qa["passed"] is True


def test_r78m_dual_callout_uncrossed_dq10_and_suppression() -> None:
    edl = {
        "cuts": [
            {
                "cut_index": 1,
                "grammar": "brain_simulator_3d",
                "out_start_sec": 0.0,
                "out_end_sec": 4.0,
                "callout_enabled": False,
                "r78m_callout": {
                    "left_lbl": "Suppressed",
                    "right_lbl": "Target",
                    "left_xy": [280, 960],
                    "right_xy": [720, 960],
                },
            },
            {
                "cut_index": 2,
                "grammar": "brain_simulator_3d",
                "out_start_sec": 4.0,
                "out_end_sec": 8.0,
                "callout_enabled": True,
                "r78m_callout": {
                    "left_lbl": "Fusiform",
                    "right_lbl": "Amygdala",
                    "arrow": "broken",
                    "sub": "Face Match vs Emotional Center",
                    "left_xy": [760, 1290],
                    "right_xy": [220, 950],
                    "left_rgb": [72, 224, 255],
                    "right_rgb": [255, 86, 94],
                    "left_mark": "ring",
                    "right_mark": "x",
                },
            },
        ]
    }
    wins = alo.resolve_anatomy_callout_windows(edl)
    assert len(wins) == 1
    assert wins[0]["cut_index"] == 2
    assert wins[0]["callout_mode"] == "r78m_dual"

    canvas = Image.new("RGBA", (1080, 1920), (0, 0, 0, 0))
    rendered = alo._render_r78m_dual_callout_rgba(
        canvas,
        wins[0],
        t_rel=1.5,
        master_alpha=1.0,
        width=1080,
        height=1920,
        safe_x_left=48.0,
        safe_x_right=910.0,
        safe_y_top=180,
        safe_y_bot=1248,
    )
    arr = np.asarray(rendered)
    assert arr.shape == (1920, 1080, 4)
    assert not np.any(arr[:180, :, 3] > 0)
    assert not np.any(arr[1249:, :, 3] > 0)
    assert np.any(arr[180:310, 80:905, 3] > 0)

    # Composite onto dark #05080F frame & verify DQ10 header detection + margins
    bg = np.full((1920, 1080, 3), (15, 8, 5), dtype=np.uint8)
    alpha = arr[:, :, 3:4].astype(np.float32) / 255.0
    rgb_bgr = arr[:, :, [2, 1, 0]].astype(np.float32)
    comp = np.clip(bg.astype(np.float32) * (1.0 - alpha) + rgb_bgr * alpha, 0, 255).astype(np.uint8)
    w_hdr, lm, rm = dq.measure_chapter_headline_bbox(comp, min_glyph_h_px=24)
    assert w_hdr > 0, "Expected DQ10 measure_chapter_headline_bbox to detect r78m_dual header glyphs"
    assert lm >= 75 and rm >= 75 and w_hdr <= 920


def test_r78v_5tone_voice_settings_cache_and_p11_f0_gate(tmp_path: Path) -> None:
    assert el.gear_to_v4_voice_settings("brisk", 0.45, use_r78v_5tone=False) == (0.45, 0.0)
    assert el.gear_to_v4_voice_settings("surprised_lift", 0.45, use_r78v_5tone=True) == (0.32, 0.38)
    assert el.gear_to_v4_voice_settings("insider_reveal", 0.45, use_r78v_5tone=True) == (0.42, 0.25)
    assert el.gear_to_v4_voice_settings("hushed_suspense", 0.45, use_r78v_5tone=True) == (0.38, 0.30)
    assert el.gear_to_v4_voice_settings("deadpan_drop", 0.45, use_r78v_5tone=True) == (0.46, 0.22)

    sr = 16000
    s1_hi = _harmonic_tone([215.0, 265.0, 295.0], 2.0, sr=sr)
    gap = np.zeros(int(0.25 * sr), dtype=np.float32)
    s2_mid = _harmonic_tone([200.0, 220.0, 205.0], 2.0, sr=sr)
    s3_lo = _harmonic_tone([185.0, 165.0, 150.0], 2.0, sr=sr)
    pcm_rich = np.concatenate([s1_hi, gap, s2_mid, gap, s3_lo])
    spans = [
        {"sentence_index": 1, "start_sec": 0.0, "end_sec": 2.0},
        {"sentence_index": 2, "start_sec": 2.25, "end_sec": 4.25},
        {"sentence_index": 3, "start_sec": 4.5, "end_sec": 6.5},
    ]
    gears = ["surprised_lift", "insider_reveal", "deadpan_drop"]
    f0_rich = pr.extract_voiced_f0_semitones(pcm_rich, sr, spans, gears)
    assert f0_rich["f0_span_p05_p95_st"] >= cfg.PROSODY_P11_F0_SPAN_MIN_ST
    assert f0_rich["lift_vs_drop_st"] is not None
    assert f0_rich["lift_vs_drop_st"] >= cfg.PROSODY_P11_LIFT_VS_DROP_MIN_ST

    def _run_proj_p11(name: str, pcm: np.ndarray) -> dict:
        pdir = tmp_path / name
        (pdir / "02_script").mkdir(parents=True, exist_ok=True)
        (pdir / "04_audio").mkdir(parents=True, exist_ok=True)
        _write_pcm_wav(pdir / "04_audio" / "audio_master.wav", pcm, sr=sr)
        (pdir / "02_script" / "script.json").write_text(
            json.dumps(
                {
                    "project_id": name,
                    "r78v_5tone_siren": True,
                    "prosody_mode": "expressive_us_v8",
                    "voice_preset": "el_siren_v4",
                    "prosody_gears": gears,
                    "sentences": [
                        "Why did his own mother look like a total stranger?",
                        "Two pathways carry that feeling cleanly.",
                        "Her voice felt real while his brain saw a fake.",
                    ],
                }
            ),
            encoding="utf-8",
        )
        (pdir / "04_audio" / "voice_report.json").write_text(
            json.dumps(
                {
                    "engine": "elevenlabs_v4",
                    "voice_preset": "el_siren_v4",
                    "total_duration_sec": round(len(pcm) / float(sr), 3),
                    "speech_end_sec": 6.5,
                    "sentence_spans": spans,
                }
            ),
            encoding="utf-8",
        )
        (pdir / "04_audio" / "prosody_report.json").write_text(
            json.dumps(
                {
                    "prosody_mode": "expressive_us_v8",
                    "native_gear_synthesis": True,
                    "sentences": [
                        {"sentence_index": 1, "gear": "surprised_lift", "factor": 1.06, "word_count": 9},
                        {"sentence_index": 2, "gear": "insider_reveal", "factor": 1.04, "word_count": 6},
                        {"sentence_index": 3, "gear": "deadpan_drop", "factor": 0.98, "word_count": 10},
                    ],
                }
            ),
            encoding="utf-8",
        )
        return pr.evaluate_prosody_gates(pdir, run_asr=False, save_report=False)

    res_pass = _run_proj_p11("p11_pass", pcm_rich)
    assert res_pass["gates"]["P11_siren_5tone_f0_range"]["passed"] is True

    mono = _harmonic_tone([200.0, 201.0], 2.0, sr=sr)
    pcm_mono = np.concatenate([mono, gap, mono, gap, mono])
    res_fail = _run_proj_p11("p11_fail", pcm_mono)
    assert res_fail["gates"]["P11_siren_5tone_f0_range"]["passed"] is False


def test_r78v_p10_open_loop_accepts_insider_reveal_and_surprised_lift(tmp_path: Path) -> None:
    from pipeline import prosody as pr

    sr = 16000
    dur = 40.0
    pcm = _harmonic_tone([210.0, 195.0], dur, sr=sr)
    pdir = tmp_path / "p10_siren"
    (pdir / "02_script").mkdir(parents=True, exist_ok=True)
    (pdir / "04_audio").mkdir(parents=True, exist_ok=True)
    _write_pcm_wav(pdir / "04_audio" / "audio_master.wav", pcm, sr=sr)
    sents = [
        "Why would your brain swear someone is a stranger?",
        "Step one happens inside your cortex.",
        "Light races straight to the back.",
        "Then a reveal flips the switch inside.",
        "The reality checker stays offline.",
    ]
    spans = [
        {"sentence_index": 1, "start_sec": 0.0, "end_sec": 4.0, "text": sents[0]},
        {"sentence_index": 2, "start_sec": 4.2, "end_sec": 14.0, "text": sents[1]},
        {"sentence_index": 3, "start_sec": 14.2, "end_sec": 24.0, "text": sents[2]},
        {"sentence_index": 4, "start_sec": 24.2, "end_sec": 32.0, "text": sents[3]},
        {"sentence_index": 5, "start_sec": 32.2, "end_sec": 40.0, "text": sents[4]},
    ]
    gears = ["surprised_lift", "insider_reveal", "brisk", "insider_reveal", "deadpan_drop"]
    (pdir / "02_script" / "script.json").write_text(
        json.dumps(
            {
                "project_id": "p10_siren",
                "r78v_5tone_siren": True,
                "prosody_mode": "expressive_us_v8",
                "voice_preset": "el_siren_v4",
                "prosody_gears": gears,
                "sentences": sents,
            }
        ),
        encoding="utf-8",
    )
    (pdir / "04_audio" / "voice_report.json").write_text(
        json.dumps(
            {
                "engine": "elevenlabs_v4",
                "voice_preset": "el_siren_v4",
                "total_duration_sec": dur,
                "speech_end_sec": dur,
                "sentence_spans": spans,
            }
        ),
        encoding="utf-8",
    )
    (pdir / "04_audio" / "prosody_report.json").write_text(
        json.dumps(
            {
                "prosody_mode": "expressive_us_v8",
                "native_gear_synthesis": True,
                "sentences": [
                    {"sentence_index": idx + 1, "gear": g, "factor": 1.0, "word_count": 7}
                    for idx, g in enumerate(gears)
                ],
            }
        ),
        encoding="utf-8",
    )
    res = pr.evaluate_prosody_gates(pdir, run_asr=False, save_report=False)
    p10 = res["gates"]["P10_open_loop_spacing"]
    assert p10["passed"] is True
    assert p10["max_gap_sec"] <= 25.0


def test_r78_agents_md_size_and_line_budget() -> None:
    agents_md = cfg.WORKSPACE_ROOT / ".agents" / "AGENTS.md"
    raw_bytes = agents_md.read_bytes()
    txt = raw_bytes.decode("utf-8")
    assert len(txt.splitlines()) <= 60
    assert 3_000 <= len(raw_bytes) <= 6_500
    assert "R77–R81" in txt
    arrows_txt = (cfg.WORKSPACE_ROOT / ".agents" / "rules" / "arrows_callouts_motion_rules.md").read_text(encoding="utf-8")
    assert "R78-M / R78-H / R78-V" in arrows_txt
