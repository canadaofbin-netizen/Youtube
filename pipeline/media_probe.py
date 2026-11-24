"""
ALL ABOUT BRAIN - Multimodal Video & Audio Autopsy Engine & Closed-Loop Self-Evolution
Directly decodes rendered .mp4 video streams and 48kHz audio waveforms to diagnose:
  1. Visual CV Layer:
     - Actual decoded video frame count & stream duration vs container duration (24.0s-60.0s @ 30fps).
     - Frame-to-frame L1 pixel difference & hard-cut timestamp detection across 5-Angle camera progression.
     - 5-segment Farneback dense optical flow velocity curve & intra-segment freeze detection.
     - First 3s Mute-Test Hook Canny edge density & center-of-frame visual saliency ratio.
     - 3D Brain Cutaway native color temperature & 4-Point Preattentive Color Contrast verification (zero post-LUT).
     - Frame 0 <-> Final Frame Möbius loop visual histogram & structural continuity.
  2. Acoustic DSP Layer (Rule R41 Zero-Clip Vocal Envelope):
     - 50ms window RMS dBFS energy profile & active speech Voice Activity Detection (VAD).
     - Missing narration / pure drone detection (dynamic range & active speech duration).
     - Raised-cosine vocal envelope over [speech_start, speech_end] with +1.15s visual contemplation holds.
     - Last 100ms speech truncation detection & +0.45s Möbius loop tail clearance check.
  3. Cross-Project Deduplication & Thumbnail Diversity Layer:
     - SHA-256 & 64-bit perceptual dHash deduplication across 03_visuals/flow_native_clips/*.mp4.
     - Thumbnail Variant A / B / C background frame visual diversity verification (A_vs_B_bg_diff >= 15.0).
  4. Autonomous Prescription & Self-Evolution Engine:
     - Synthesizes actionable remediation prescriptions from forensic telemetry.
     - Executes closed-loop self-evolution (Rule R41 Zero-Clip Vocal Envelope + Two-Phase Dopamine Soundscape,
       speech-locked 86px Arial Black ASS subtitles + opaque pill-box HUD, 1.00x native Flow assembly, and QA sync).
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from pipeline.config import (
    AUDIO_MAX_OVERSAMPLED_TRUE_PEAK_DBTP,
    AUDIO_MAX_SIBILANCE_CREST_DB,
    AUDIO_MAX_SIBILANCE_ENERGY_RATIO,
    AUDIO_MIN_TTS_ASR_WORD_COVERAGE,
    AUDIO_SIBILANCE_BAND_HZ,
    AUDIO_SPEECH_BODY_BAND_HZ,
    AV_SPEEDUP_FACTOR,
    CLIP_PRE_PIVOT_HOLD_SEC,
    CLIP_VISUAL_HOLD_SEC,
    DEFAULT_CLIP_COUNT,
    DIORAMA_DURATION_MIN_SEC,
    DIORAMA_LUFS_TOLERANCE_LU,
    DIORAMA_MAX_CLIP_REUSE,
    DIORAMA_TARGET_CUT_MIN,
    DIORAMA_TARGET_LUFS,
    DIORAMA_V7_DURATION_MIN_SEC,
    DIORAMA_V7_TARGET_LUFS,
    EXPRESSIVE_V8_CLIP_COUNT_MIN,
    EXPRESSIVE_V8_LONG_TAKE_MAX_SEC,
    EXPRESSIVE_V8_MAX_CUT_SEC,
    EXPRESSIVE_V8_MIN_CUT_SEC,
    EXPRESSIVE_V8_TARGET_LUFS,
    FINAL_SHORTS_DURATION_MIN_SEC,
    FINAL_TAIL_SEC,
    MAX_PERCEPTUAL_DHASH_HAMMING_DISTANCE,
    MICRO_SHORT_CUT_MIN,
    MICRO_SHORT_PROFILE,
    MIN_CLIP_SIZE_BYTES,
    MIN_OPTICAL_FLOW_THRESHOLD,
    PORCELAIN_V7_LONG_TAKE_MAX_SEC,
    PORCELAIN_V7_MIN_CUT_SEC,
    PROJECTS_DIR,
    SHORTS_EXPRESSIVE_V8_PROFILE,
    SHORTS_HARD_CEILING_FRAMES,
    SHORTS_HARD_CEILING_FRAMES_V7,
    SHORTS_HARD_CEILING_SEC,
    SUBPROCESS_TIMEOUT_SEC,
    VIDEO_FPS,
    VIDEO_HEIGHT,
    VIDEO_WIDTH,
    expected_final_duration_sec,
    is_diorama_profile,
    is_diorama_v7_plan,
    is_expressive_v8_plan,
    is_porcelain_v7_plan,
    max_allowed_dead_air_sec,
)
from pipeline.media_integrity import MediaIntegrityValidator, get_pipeline_logger
from pipeline.storage import ProjectStorage, numeric_clip_sort_key

logger = get_pipeline_logger("video_autopsy")

FORBIDDEN_STAGE_LABELS = (
    "PARADOX:",
    "DILEMMA:",
    "MECHANISM:",
    "REVELATION:",
    "MÖBIUS LOOP:",
    "MOBIUS LOOP:",
)


class VideoAutopsyEngine:
    """
    Multimodal forensic inspector and closed-loop self-evolution engine for rendered Shorts MP4s.
    """

    @classmethod
    def inspect_video_stream(
        cls,
        mp4_path: Path,
        expected_duration_sec: float = expected_final_duration_sec(DEFAULT_CLIP_COUNT),
    ) -> dict[str, Any]:
        """
        Decodes the rendered .mp4 video stream frame-by-frame (sampled at 15Hz for cut/freeze analysis
        and dense pairs for Farneback optical flow) to extract physical visual telemetry.
        """
        path = Path(mp4_path)
        if not path.exists():
            return {
                "exists": False,
                "frame_count": 0,
                "decoded_frame_count": 0,
                "fps": 0.0,
                "container_duration_sec": 0.0,
                "decoded_duration_sec": 0.0,
                "has_early_stream_freeze": True,
                "min_window_upper_diff": 0.0,
                "mean_step_upper_diff": 0.0,
                "detected_cuts_sec": [],
                "cut_count": 0,
                "narrative_cut_sync_error_sec": 99.0,
                "rigid_6s_cuts": False,
                "optical_flow_segments": [],
                "optical_flow_mean": 0.0,
                "cutaway_cool_ratio": 0.0,
                "cutaway_warm_ratio": 0.0,
                "color_palette_inverted": True,
            }

        from pipeline.media_cache import (
            get_active_mp4_session,
            get_cached_json,
            put_cached_json,
            stage_local_file,
        )

        local_decode_path, mp4_sha = stage_local_file(path)
        cache_key = f"{mp4_sha}|{round(float(expected_duration_sec), 2)}"
        cached_vid = get_cached_json("autopsy_video_v1", cache_key)
        if isinstance(cached_vid, dict) and cached_vid.get("exists") is not None:
            return cached_vid

        sess = get_active_mp4_session(mp4_sha)
        if sess is not None and int(sess.get("decoded_fc") or 0) > 0:
            fps = float(sess.get("fps") or VIDEO_FPS)
            header_fc = int(sess.get("header_fc") or sess.get("decoded_fc") or 0)
            container_dur = round(header_fc / max(1.0, fps), 3)
            probe: dict[str, Any] = {
                "exists": True,
                "has_video_stream": True,
                "width": int(sess.get("width") or VIDEO_WIDTH),
                "height": int(sess.get("height") or VIDEO_HEIGHT),
                "fps": fps,
                "frame_count": header_fc,
                "duration_seconds": container_dur,
            }
        else:
            probe = MediaIntegrityValidator.probe_streams(local_decode_path)
            if not probe.get("exists") or not probe.get("has_video_stream"):
                return {
                    "exists": False,
                    "frame_count": 0,
                    "decoded_frame_count": 0,
                    "fps": 0.0,
                    "container_duration_sec": 0.0,
                    "decoded_duration_sec": 0.0,
                    "has_early_stream_freeze": True,
                    "min_window_upper_diff": 0.0,
                    "mean_step_upper_diff": 0.0,
                    "detected_cuts_sec": [],
                    "cut_count": 0,
                    "narrative_cut_sync_error_sec": 99.0,
                    "rigid_6s_cuts": False,
                    "optical_flow_segments": [],
                    "optical_flow_mean": 0.0,
                    "cutaway_cool_ratio": 0.0,
                    "cutaway_warm_ratio": 0.0,
                    "color_palette_inverted": True,
                }
            fps = float(probe.get("fps") or (sess["fps"] if sess else 0.0) or VIDEO_FPS)
            header_fc = int(probe.get("frame_count") or (sess["header_fc"] if sess else 0) or 0)
            container_dur = float(probe.get("duration_seconds") or 0.0)
        if fps <= 0:
            fps = float(VIDEO_FPS)

        sampled_times: list[float] = []
        sampled_upper_grays: list[np.ndarray] = []
        frame_step = 2
        decoded_fc = 0
        cutaway_hsv_samples: list[np.ndarray] = []
        is_long_diorama_stream = max(container_dur, expected_duration_sec) >= 120.0

        if sess is not None and sess.get("even_small_bgr"):
            decoded_fc = int(sess["decoded_fc"])
            for f_idx_even, small_bgr in sorted(sess["even_small_bgr"].items()):
                t_sec = f_idx_even / fps
                if is_long_diorama_stream:
                    upper_bgr = np.vstack([small_bgr[:182, :], small_bgr[226:298, :]])
                else:
                    upper_cut = int(320 * 0.62)
                    upper_bgr = small_bgr[:upper_cut, :]
                upper_gray = cv2.cvtColor(upper_bgr, cv2.COLOR_BGR2GRAY)
                sampled_times.append(round(t_sec, 3))
                sampled_upper_grays.append(upper_gray)
                if t_sec >= 4.0 and len(cutaway_hsv_samples) < 40 and f_idx_even % 10 == 0:
                    cutaway_hsv_samples.append(cv2.cvtColor(upper_bgr, cv2.COLOR_BGR2HSV))
        else:
            cap = cv2.VideoCapture(str(local_decode_path.resolve()))
            if header_fc <= 0:
                header_fc = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
            while True:
                ret, frame = cap.read()
                if not ret or frame is None:
                    break
                decoded_fc += 1
                t_sec = (decoded_fc - 1) / fps

                if (decoded_fc - 1) % frame_step == 0:
                    small_bgr = cv2.resize(frame, (180, 320), interpolation=cv2.INTER_AREA)
                    if is_long_diorama_stream:
                        upper_bgr = np.vstack([small_bgr[:182, :], small_bgr[226:298, :]])
                    else:
                        upper_cut = int(320 * 0.62)
                        upper_bgr = small_bgr[:upper_cut, :]
                    upper_gray = cv2.cvtColor(upper_bgr, cv2.COLOR_BGR2GRAY)
                    sampled_times.append(round(t_sec, 3))
                    sampled_upper_grays.append(upper_gray)

                    if t_sec >= 4.0 and len(cutaway_hsv_samples) < 40 and (decoded_fc - 1) % 10 == 0:
                        hsv = cv2.cvtColor(upper_bgr, cv2.COLOR_BGR2HSV)
                        cutaway_hsv_samples.append(hsv)

            cap.release()

        effective_fc = decoded_fc if decoded_fc > 0 else header_fc
        decoded_dur = round(effective_fc / fps, 2) if fps > 0 else 0.0

        # 1. Detect frame-to-frame L1 diffs & scene cuts via local-median impulse ratio + 2.0s NMS
        step_diffs: list[float] = []
        for i in range(len(sampled_upper_grays) - 1):
            d = float(np.mean(np.abs(sampled_upper_grays[i + 1].astype(np.float32) - sampled_upper_grays[i].astype(np.float32))))
            step_diffs.append(d)

        mean_step_diff = float(np.mean(step_diffs)) if step_diffs else 0.0
        median_step_diff = float(np.median(step_diffs)) if step_diffs else 0.0
        cut_thresh = max(13.5, min(mean_step_diff, median_step_diff) * 2.4)
        candidate_peaks: list[tuple[float, float]] = []
        n_diffs = len(step_diffs)
        is_long_diorama = max(container_dur, expected_duration_sec) >= 120.0
        min_edge_t = 0.40 if is_long_diorama else 1.5
        min_nms_gap = 0.40 if is_long_diorama else 2.0
        for i, d in enumerate(step_diffs):
            t_cut = sampled_times[i + 1]
            if t_cut < min_edge_t or t_cut > decoded_dur - 1.2:
                continue
            if i > 0 and step_diffs[i - 1] > d:
                continue
            if i + 1 < n_diffs and step_diffs[i + 1] >= d:
                continue
            neigh = [
                step_diffs[j]
                for j in range(max(0, i - 8), min(n_diffs, i + 9))
                if abs(j - i) >= 2
            ]
            local_med = float(np.median(neigh)) if neigh else mean_step_diff
            if (d >= cut_thresh and d >= max(8.0, local_med * 2.1)) or (d >= 18.0 and d >= max(10.0, local_med * 3.2)):
                candidate_peaks.append((d, round(t_cut, 2)))

        candidate_peaks.sort(key=lambda x: x[0], reverse=True)
        selected_cuts: list[float] = []
        for _d_val, t_val in candidate_peaks:
            if all(abs(t_val - existing_t) >= min_nms_gap for existing_t in selected_cuts):
                selected_cuts.append(t_val)
        detected_cuts = sorted(selected_cuts)

        n_cuts = len(detected_cuts)
        if n_cuts > 0 and decoded_dur > 0:
            ideal_step = decoded_dur / (n_cuts + 1)
            targets = [round(ideal_step * (k + 1), 2) for k in range(n_cuts)]
            sync_err = round(float(np.mean([abs(c - rt) for c, rt in zip(detected_cuts, targets)])), 3)
        else:
            sync_err = 99.0

        rigid_6s = False
        if len(detected_cuts) == 4:
            rigid_targets = [6.0, 12.0, 18.0, 24.0]
            if all(abs(c - rt) <= 0.25 for c, rt in zip(detected_cuts, rigid_targets)):
                rigid_6s = True

        # 2. Check for frozen 1.5s windows or truncated video stream
        window_len = max(3, int(1.5 / (frame_step / fps)))
        min_window_diff = 999.0
        if len(step_diffs) >= window_len:
            for start_i in range(0, len(step_diffs) - window_len + 1, max(1, window_len // 2)):
                w_mean = float(np.mean(step_diffs[start_i:start_i + window_len]))
                if w_mean < min_window_diff:
                    min_window_diff = w_mean
        else:
            min_window_diff = mean_step_diff

        ref_dur = container_dur if container_dur >= FINAL_SHORTS_DURATION_MIN_SEC else expected_duration_sec
        has_early_freeze = (
            decoded_dur < ref_dur * 0.95
            or effective_fc < int(ref_dur * fps * 0.95)
            or min_window_diff < 0.12
        )

        # 3. Compute 5-segment Farneback optical flow
        flow_segments: list[float] = []
        n_samples = len(sampled_upper_grays)
        if n_samples >= 10:
            seg_size = n_samples // 5
            for s_idx in range(5):
                mid_i = min(n_samples - 2, s_idx * seg_size + seg_size // 2)
                g1 = sampled_upper_grays[mid_i]
                g2 = sampled_upper_grays[min(n_samples - 1, mid_i + 2)]
                flow = cv2.calcOpticalFlowFarneback(
                    g1, g2, None,
                    pyr_scale=0.5, levels=3, winsize=15,
                    iterations=3, poly_n=5, poly_sigma=1.2, flags=0
                )
                mag, _ = cv2.cartToPolar(flow[..., 0], flow[..., 1])
                flow_segments.append(round(float(np.mean(mag)), 3))
        flow_mean = round(float(np.mean(flow_segments)), 3) if flow_segments else 0.0

        # 4. HSV Color Telemetry (Native Google Flow colors preserved without post-processing LUT distortion)
        cool_pixels = 0
        warm_pixels = 0
        for hsv_img in cutaway_hsv_samples:
            h_ch = hsv_img[..., 0]
            s_ch = hsv_img[..., 1]
            v_ch = hsv_img[..., 2]
            chromatic = (s_ch >= 30) & (v_ch >= 30)
            cool_mask = chromatic & (h_ch >= 80) & (h_ch <= 138)
            warm_mask = chromatic & ((h_ch <= 28) | (h_ch >= 165))
            cool_pixels += int(np.sum(cool_mask))
            warm_pixels += int(np.sum(warm_mask))

        total_cw = max(1, cool_pixels + warm_pixels)
        cool_ratio = round(cool_pixels / total_cw, 3)
        warm_ratio = round(warm_pixels / total_cw, 3)
        color_inverted = False

        res_video = {
            "exists": True,
            "width": probe.get("width", 0),
            "height": probe.get("height", 0),
            "fps": round(fps, 2),
            "frame_count": header_fc,
            "decoded_frame_count": effective_fc,
            "container_duration_sec": round(container_dur, 2),
            "decoded_duration_sec": decoded_dur,
            "has_early_stream_freeze": has_early_freeze,
            "min_window_upper_diff": round(min_window_diff, 3),
            "mean_step_upper_diff": round(mean_step_diff, 3),
            "detected_cuts_sec": detected_cuts,
            "cut_count": len(detected_cuts),
            "avg_clip_duration_sec": round(decoded_dur / max(1, len(detected_cuts) + 1), 2),
            "narrative_cut_sync_error_sec": sync_err,
            "rigid_6s_cuts": rigid_6s,
            "optical_flow_segments": flow_segments,
            "optical_flow_mean": flow_mean,
            "cutaway_cool_ratio": cool_ratio,
            "cutaway_warm_ratio": warm_ratio,
            "color_palette_inverted": color_inverted,
        }
        put_cached_json("autopsy_video_v1", cache_key, res_video)
        return res_video

    @classmethod
    def inspect_audio_stream(
        cls,
        media_path: Path,
        expected_duration_sec: float = expected_final_duration_sec(DEFAULT_CLIP_COUNT),
    ) -> dict[str, Any]:
        """
        Decodes the audio track from .mp4 or .wav into 24kHz 16-bit mono PCM (12kHz Nyquist) and performs:
        - 50ms-window Voice Activity Detection (VAD), internal Dead Air measurement, last-100ms truncation detection
        - Voiced-window high-frequency sibilance/harshness tear detection (4.2-9.2kHz vs 0.18-3.6kHz speech body)
        - ITU-R BS.1770 (`ebur128=peak=true`) integrated loudness (LUFS), LRA (LU), and 4x oversampled True Peak (dBTP)
        """
        path = Path(media_path)
        empty_audio = {
            "exists": False,
            "duration_sec": 0.0,
            "overall_rms_dbfs": -96.0,
            "peak_dbfs": -96.0,
            "true_peak_dbtp": None,
            "integrated_lufs": None,
            "loudness_range_lu": None,
            "true_peak_clipping": False,
            "sibilance_to_body_rms_ratio": 0.0,
            "sibilance_crest_db": 0.0,
            "sibilance_tear_detected": False,
            "noise_floor_dbfs": -96.0,
            "dynamic_range_db": 0.0,
            "has_active_speech": False,
            "active_speech_duration_sec": 0.0,
            "speech_start_sec": 0.0,
            "speech_end_sec": 0.0,
            "internal_silence_count": 0,
            "cumulative_dead_air_sec": 0.0,
            "max_pause_sec": 0.0,
            "last_100ms_dbfs": -96.0,
            "last_500ms_dbfs": -96.0,
            "is_truncated_at_30s": True,
        }
        if not path.exists():
            return dict(empty_audio)

        from pipeline.media_cache import get_cached_json, put_cached_json, stage_local_file

        local_audio_path, audio_sha = stage_local_file(path)
        aud_cache_key = f"{audio_sha}|{round(float(expected_duration_sec), 2)}"
        cached_aud = get_cached_json("autopsy_audio_v2", aud_cache_key)
        if isinstance(cached_aud, dict) and cached_aud.get("exists") is not None:
            return cached_aud

        sr = 24000
        try:
            ffmpeg_exe = MediaIntegrityValidator.get_ffmpeg_exe()
            cmd = [
                ffmpeg_exe,
                "-hide_banner",
                "-loglevel", "error",
                "-i", str(local_audio_path.resolve()),
                "-vn",
                "-ac", "1",
                "-ar", str(sr),
                "-f", "s16le",
                "pipe:1",
            ]
            res = subprocess.run(cmd, capture_output=True, timeout=30.0, check=False)
            if res.returncode != 0 or not res.stdout:
                return dict(empty_audio)
            samples = np.frombuffer(res.stdout, dtype=np.int16).astype(np.float32) / 32768.0
        except Exception as exc:
            logger.warning("Audio decode inspection note for %s: %s", path.name, exc)
            return dict(empty_audio)

        if len(samples) < sr:
            return dict(empty_audio)

        duration_sec = round(len(samples) / sr, 2)
        eps = 1e-9
        overall_rms = float(np.sqrt(np.mean(np.square(samples)) + eps))
        overall_rms_db = round(float(20.0 * np.log10(max(overall_rms, eps))), 2)
        peak_val = float(np.max(np.abs(samples)) + eps)
        peak_db = round(float(20.0 * np.log10(max(peak_val, eps))), 2)

        # 50ms windows (1200 samples per window @ 24kHz)
        win_size = int(sr * 0.05)
        n_wins = len(samples) // win_size
        trimmed = samples[:n_wins * win_size].reshape((n_wins, win_size))
        win_rms = np.sqrt(np.mean(np.square(trimmed), axis=1) + eps)
        win_db = 20.0 * np.log10(np.maximum(win_rms, eps))

        p10_db = float(np.percentile(win_db, 10))
        p95_db = float(np.percentile(win_db, 95))
        dyn_range = round(p95_db - p10_db, 2)

        # Speech threshold relative to drone floor and peak (-22dB below 95th percentile speech peak)
        speech_thresh_db = max(-38.0, min(p95_db - 22.0, p10_db + 6.0))
        is_speech_win = (win_db > speech_thresh_db) if dyn_range >= 5.5 else np.zeros_like(win_db, dtype=bool)

        active_speech_sec = round(float(np.sum(is_speech_win) * 0.05), 2)
        has_active_speech = bool(dyn_range >= 5.5 and active_speech_sec >= 10.0 and overall_rms_db > -38.0)

        speech_indices = np.where(is_speech_win)[0]
        if len(speech_indices) > 0 and has_active_speech:
            speech_start_sec = round(float(speech_indices[0] * 0.05), 2)
            speech_end_sec = round(float((speech_indices[-1] + 1) * 0.05), 2)
        else:
            speech_start_sec = 0.0
            speech_end_sec = 0.0

        # Voiced-window high-frequency harshness / sibilance tear analysis (4.2-9.2kHz vs 0.18-3.6kHz)
        sib_ratio = 0.0
        sib_crest_db = 0.0
        if len(speech_indices) > 0:
            voiced_wins = trimmed[speech_indices]
            hann = np.hanning(win_size).astype(np.float32)
            spec = np.fft.rfft(voiced_wins * hann[None, :], axis=1)
            freqs = np.fft.rfftfreq(win_size, d=1.0 / sr)
            sib_mask = (freqs >= AUDIO_SIBILANCE_BAND_HZ[0]) & (freqs <= AUDIO_SIBILANCE_BAND_HZ[1])
            body_mask = (freqs >= AUDIO_SPEECH_BODY_BAND_HZ[0]) & (freqs <= AUDIO_SPEECH_BODY_BAND_HZ[1])
            sib_spec = np.zeros_like(spec)
            sib_spec[:, sib_mask] = spec[:, sib_mask]
            body_spec = np.zeros_like(spec)
            body_spec[:, body_mask] = spec[:, body_mask]
            sib_td = np.fft.irfft(sib_spec, n=win_size, axis=1)
            body_td = np.fft.irfft(body_spec, n=win_size, axis=1)
            hf_rms = float(np.sqrt(np.mean(np.square(sib_td)) + eps))
            body_rms = float(np.sqrt(np.mean(np.square(body_td)) + eps))
            hf_peak = float(np.max(np.abs(sib_td)) + eps)
            sib_ratio = round(hf_rms / max(body_rms, 1e-6), 4)
            sib_crest_db = round(float(20.0 * np.log10(max(hf_peak, eps) / max(hf_rms, eps))), 2)
        sib_tear = bool(
            sib_ratio > AUDIO_MAX_SIBILANCE_ENERGY_RATIO
            or sib_crest_db > AUDIO_MAX_SIBILANCE_CREST_DB
        )

        # ITU-R BS.1770 integrated loudness (LUFS) & 4x oversampled True Peak (dBTP) via FFmpeg ebur128
        integrated_lufs: float | None = None
        loudness_range_lu: float | None = None
        true_peak_dbtp: float | None = None
        try:
            ebu_cmd = [
                ffmpeg_exe,
                "-hide_banner",
                "-nostats",
                "-i", str(local_audio_path.resolve()),
                "-vn",
                "-af", "ebur128=peak=true",
                "-f", "null",
                "-",
            ]
            ebu_res = subprocess.run(ebu_cmd, capture_output=True, text=True, timeout=30.0, check=False)
            stderr_txt = ebu_res.stderr or ""
            m_i = re.findall(r"I:\s*(-?\d+(?:\.\d+)?)\s*LUFS", stderr_txt)
            if m_i:
                integrated_lufs = round(float(m_i[-1]), 2)
            m_lra = re.findall(r"LRA:\s*(-?\d+(?:\.\d+)?)\s*LU", stderr_txt)
            if m_lra:
                loudness_range_lu = round(float(m_lra[-1]), 2)
            m_tp = re.findall(r"Peak:\s*(-?\d+(?:\.\d+)?)\s*dBFS", stderr_txt)
            if m_tp:
                true_peak_dbtp = round(float(m_tp[-1]), 2)
        except Exception as exc:
            logger.debug("ebur128 loudness probe skipped for %s: %s", path.name, exc)

        # Count internal non-speech gaps > 0.20s (> 4 consecutive 50ms windows) between speech_start and speech_end
        internal_silence_count = 0
        cumulative_dead_air = 0.0
        max_pause_sec = 0.0
        if has_active_speech and len(speech_indices) > 1:
            start_w = int(speech_indices[0])
            end_w = int(speech_indices[-1])
            cur_silent_run = 0
            for w_idx in range(start_w, end_w + 1):
                if not is_speech_win[w_idx]:
                    cur_silent_run += 1
                else:
                    if cur_silent_run >= 4:  # >= 0.20s pause
                        pause_dur = cur_silent_run * 0.05
                        internal_silence_count += 1
                        cumulative_dead_air += pause_dur
                        if pause_dur > max_pause_sec:
                            max_pause_sec = pause_dur
                    cur_silent_run = 0

        # Last 100ms & 500ms check for mid-sentence truncation
        last_100ms_samples = samples[max(0, len(samples) - int(sr * 0.10)):]
        last_500ms_samples = samples[max(0, len(samples) - int(sr * 0.50)):]
        last_100ms_rms = float(np.sqrt(np.mean(np.square(last_100ms_samples)) + eps))
        last_500ms_rms = float(np.sqrt(np.mean(np.square(last_500ms_samples)) + eps))
        last_100ms_db = round(float(20.0 * np.log10(max(last_100ms_rms, eps))), 2)
        last_500ms_db = round(float(20.0 * np.log10(max(last_500ms_rms, eps))), 2)

        # Speech is truncated only if the final 100ms still has un-faded vocal energy above -30 dBFS
        is_truncated = bool(
            (not has_active_speech)
            or (last_100ms_db > max(-28.5, p10_db + 10.5))
        )
        tp_clip = bool(
            peak_db > -1.0
            or (true_peak_dbtp is not None and true_peak_dbtp > AUDIO_MAX_OVERSAMPLED_TRUE_PEAK_DBTP)
        )

        res_aud = {
            "exists": True,
            "duration_sec": duration_sec,
            "overall_rms_dbfs": overall_rms_db,
            "peak_dbfs": peak_db,
            "true_peak_dbtp": true_peak_dbtp,
            "integrated_lufs": integrated_lufs,
            "loudness_range_lu": loudness_range_lu,
            "true_peak_clipping": tp_clip,
            "sibilance_to_body_rms_ratio": sib_ratio,
            "sibilance_crest_db": sib_crest_db,
            "sibilance_tear_detected": sib_tear,
            "noise_floor_dbfs": round(p10_db, 2),
            "dynamic_range_db": dyn_range,
            "has_active_speech": has_active_speech,
            "active_speech_duration_sec": active_speech_sec,
            "speech_start_sec": speech_start_sec,
            "speech_end_sec": speech_end_sec,
            "internal_silence_count": internal_silence_count,
            "cumulative_dead_air_sec": round(cumulative_dead_air, 2),
            "max_pause_sec": round(max_pause_sec, 2),
            "last_100ms_dbfs": last_100ms_db,
            "last_500ms_dbfs": last_500ms_db,
            "is_truncated_at_30s": is_truncated,
        }
        put_cached_json("autopsy_audio_v2", aud_cache_key, res_aud)
        return res_aud

    @classmethod
    def inspect_subtitles(cls, ass_path: Path) -> dict[str, Any]:
        """
        Inspects 04_audio/subtitles.ass for R16 & R43 compliance:
        - Single-line Y=74% (MarginV=440, 2-3 words) or legacy 2-line phrase-synced events (>= 10 events)
        - Zero raw stage labels (PARADOX:, DILEMMA:, MECHANISM:, REVELATION:, MÖBIUS LOOP:)
        - Dynamic 4-stage Telemetry HUD & micro-callouts.
        """
        path = Path(ass_path)
        if not path.exists():
            return {
                "exists": False,
                "dialogue_count": 0,
                "max_words_per_event": 0,
                "avg_words_per_event": 0.0,
                "has_raw_stage_labels": False,
                "default_font_size": 0,
                "margin_v": 0,
                "telemetry_hud_events": 0,
                "callout_events": 0,
                "gold_highlighted_events": 0,
                "micro_pop_events": 0,
                "is_dynamic_2line_compliant": False,
            }

        txt = path.read_text(encoding="utf-8", errors="replace")
        font_size = 46
        margin_v = 440
        style_match = re.search(r"^Style:\s*Default,[^,]+,(\d+),.*?,(\d+),1\s*$", txt, flags=re.MULTILINE)
        if style_match:
            font_size = int(style_match.group(1))
            margin_v = int(style_match.group(2))
        else:
            sm2 = re.search(r"^Style:\s*Default,[^,]+,(\d+),", txt, flags=re.MULTILINE)
            if sm2:
                font_size = int(sm2.group(1))

        dialogue_lines = [
            line for line in txt.splitlines()
            if line.strip().startswith("Dialogue:")
        ]
        phrase_events = 0
        telemetry_events = 0
        callout_events = 0
        gold_events = 0
        micro_pop_events = 0
        word_counts: list[int] = []
        has_stage_labels = False
        overlapping_events_count = 0
        unconverted_number_words_count = 0
        prev_end_sec = -1.0

        def _parse_ass_time(ts: str) -> float:
            m = re.match(r"(\d+):(\d+):([\d.]+)", ts.strip())
            if not m:
                return 0.0
            return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))

        unconverted_num_re = re.compile(
            r"\b(?:sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred|thousand)\b"
            r"|\b\d+\s+percent\b",
            flags=re.IGNORECASE,
        )

        for line in dialogue_lines:
            parts = line.split(",", 9)
            if len(parts) < 10:
                continue
            t_start = _parse_ass_time(parts[1])
            t_end = _parse_ass_time(parts[2])
            style_name = parts[3].strip()
            raw_text = parts[9]
            clean_text = re.sub(r"\{[^}]*\}", "", raw_text).replace("\\N", " ").strip()
            if any(lbl in clean_text.upper() for lbl in FORBIDDEN_STAGE_LABELS):
                has_stage_labels = True
            if style_name == "Default":
                phrase_events += 1
                if prev_end_sec > 0.0 and t_start < prev_end_sec - 0.005:
                    overlapping_events_count += 1
                prev_end_sec = max(prev_end_sec, t_end)
                if unconverted_num_re.search(clean_text):
                    unconverted_number_words_count += 1
                w_cnt = len(re.findall(r"\b[\w'-]+\b", clean_text))
                word_counts.append(w_cnt)
                if "00D7FF" in raw_text.upper():
                    gold_events += 1
                if "\\fscx110" in raw_text:
                    micro_pop_events += 1
            elif style_name == "Telemetry":
                telemetry_events += 1
            elif style_name == "Callout":
                callout_events += 1

        max_words = max(word_counts) if word_counts else 0
        avg_words = round(float(np.mean(word_counts)), 2) if word_counts else 0.0

        is_compliant = bool(
            phrase_events >= 10
            and not has_stage_labels
            and max_words <= 10
            and 34 <= font_size <= 112
            and overlapping_events_count == 0
            and unconverted_number_words_count == 0
        )

        return {
            "exists": True,
            "dialogue_count": phrase_events,
            "total_events": len(dialogue_lines),
            "max_words_per_event": max_words,
            "avg_words_per_event": avg_words,
            "has_raw_stage_labels": has_stage_labels,
            "default_font_size": font_size,
            "margin_v": margin_v,
            "telemetry_hud_events": telemetry_events,
            "callout_events": callout_events,
            "gold_highlighted_events": gold_events,
            "micro_pop_events": micro_pop_events,
            "overlapping_events_count": overlapping_events_count,
            "unconverted_number_words_count": unconverted_number_words_count,
            "is_dynamic_2line_compliant": is_compliant,
        }

    @classmethod
    def inspect_thumbnails_and_dedup(
        cls,
        project_dir: Path,
        all_clip_hashes: dict[str, list[str]] | None = None,
        all_clip_dhashes: list[dict[str, Any]] | None = None,
        all_provenance_urls: dict[str, list[str]] | None = None,
        all_provenance_tabs: dict[str, list[str]] | None = None,
    ) -> dict[str, Any]:
        """
        Inspects 06_publish/thumbnail_var_A/B/C.png for visual frame diversity across the
        central cutaway region (y=600..1300), validates 03_visuals/flow_provenance_receipt.json (Guard 1 & 6),
        and checks native clips for cross-project SHA-256 and perceptual 64-bit dHash duplication (Guard 2).
        """
        from pipeline.flow_browser import FlowProjectSubagentWorker

        p_dir = Path(project_dir)
        pub_dir = p_dir / "06_publish"
        thumb_a = pub_dir / "thumbnail_var_A.png"
        thumb_b = pub_dir / "thumbnail_var_B.png"
        thumb_c = pub_dir / "thumbnail_var_C.png"

        ab_diff = 0.0
        bc_diff = 0.0
        ac_diff = 0.0
        thumbs_exist = thumb_a.exists() and thumb_b.exists() and thumb_c.exists()

        if thumbs_exist:
            img_a = cv2.imread(str(thumb_a))
            img_b = cv2.imread(str(thumb_b))
            img_c = cv2.imread(str(thumb_c))
            if img_a is not None and img_b is not None and img_c is not None:
                if img_a.shape == img_b.shape == img_c.shape:
                    h = img_a.shape[0]
                    y0, y1 = int(h * 0.32), int(h * 0.68)  # Central region unoccluded by badges in A/B/C
                    roi_a = img_a[y0:y1, :].astype(np.float32)
                    roi_b = img_b[y0:y1, :].astype(np.float32)
                    roi_c = img_c[y0:y1, :].astype(np.float32)
                    ab_diff = round(float(np.mean(np.abs(roi_a - roi_b))), 2)
                    bc_diff = round(float(np.mean(np.abs(roi_b - roi_c))), 2)
                    ac_diff = round(float(np.mean(np.abs(roi_a - roi_c))), 2)

        thumbnails_distinct = bool(thumbs_exist and ab_diff >= 15.0 and ac_diff >= 15.0)

        # Guard 1 & Guard 6: Validate Google Flow Provenance Receipt & 1:1:1 Tab Isolation
        prov_check = FlowProjectSubagentWorker.validate_provenance_receipt(p_dir)
        provenance_errors = list(prov_check.get("errors", []))
        my_flow_url = prov_check.get("flow_project_url", "")
        my_tab_id = prov_check.get("tab_target_id", "")

        clips_dir = p_dir / "03_visuals" / "flow_native_clips"
        clip_files = (
            sorted(clips_dir.glob("*.mp4"), key=numeric_clip_sort_key)
            if clips_dir.exists()
            else []
        )
        clip_hashes: dict[str, str] = {}
        clip_dhashes: dict[str, dict[str, Any]] = {}
        shared_clips: list[dict[str, Any]] = []
        derivative_clips: list[dict[str, Any]] = []
        synthetic_derivative_clips: list[dict[str, Any]] = []

        # Build cross-project maps with in-memory cache so we do not open 100 FUSE directories on every project
        all_rebuilt_from: dict[str, str] = {}
        if (all_clip_hashes is None or all_clip_dhashes is None or all_provenance_urls is None) and PROJECTS_DIR.exists():
            try:
                if p_dir.resolve().parent == PROJECTS_DIR.resolve():
                    now_ts = time.time()
                    cache = getattr(cls, "_CROSS_PROJECT_DEDUP_CACHE", None)
                    if cache and (now_ts - cache.get("ts", 0.0) < 600.0) and ("rebuilt_from" in cache):
                        all_clip_hashes = dict(cache["hashes"])
                        all_clip_dhashes = list(cache["dhashes"])
                        all_provenance_urls = dict(cache["urls"])
                        all_provenance_tabs = dict(cache["tabs"])
                        all_rebuilt_from = dict(cache["rebuilt_from"])
                    else:
                        all_clip_hashes = {}
                        all_clip_dhashes = []
                        all_provenance_urls = {}
                        all_provenance_tabs = {}
                        all_rebuilt_from = {}
                        for other_dir in sorted(PROJECTS_DIR.iterdir()):
                            if not other_dir.is_dir():
                                continue
                            receipt_path = other_dir / "03_visuals" / "flow_provenance_receipt.json"
                            if not receipt_path.exists():
                                continue
                            try:
                                other_rcpt = json.loads(receipt_path.read_text(encoding="utf-8"))
                            except Exception:
                                continue
                            o_url = str(other_rcpt.get("flow_project_url") or "").strip()
                            o_tab = str(other_rcpt.get("tab_target_id") or "").strip()
                            o_rebuilt = str(other_rcpt.get("rebuilt_from_frozen_project") or "").strip()
                            if o_rebuilt:
                                all_rebuilt_from[other_dir.name] = o_rebuilt
                            if o_url:
                                all_provenance_urls.setdefault(o_url, []).append(other_dir.name)
                            if o_tab:
                                all_provenance_tabs.setdefault(o_tab, []).append(other_dir.name)
                            var_file = other_dir / "05_assembly" / "video_autopsy_report.json"
                            cached_dhashes = {}
                            cached_hashes = {}
                            if var_file.exists():
                                try:
                                    v_rep = json.loads(var_file.read_text(encoding="utf-8"))
                                    td_sec = v_rep.get("thumbnails_and_dedup", {})
                                    cached_dhashes = td_sec.get("clip_dhashes", {})
                                    cached_hashes = td_sec.get("clip_hashes", {})
                                except Exception:
                                    pass
                            receipt_clips = other_rcpt.get("clips", [])
                            for i, c in enumerate(receipt_clips, 1):
                                if isinstance(c, dict) and c.get("sha256"):
                                    cname = f"clip_{int(c.get('clip_index', i))}.mp4"
                                    oh_val = cached_hashes.get(cname) or str(c.get("sha256", ""))[:16]
                                    if oh_val:
                                        all_clip_hashes.setdefault(oh_val, []).append(other_dir.name)
                                    if other_dir.name != p_dir.name and cname in cached_dhashes:
                                        all_clip_dhashes.append({
                                            "project_id": other_dir.name,
                                            "clip": cname,
                                            "dhash": cached_dhashes[cname],
                                        })
                        cls._CROSS_PROJECT_DEDUP_CACHE = {
                            "ts": now_ts,
                            "hashes": dict(all_clip_hashes),
                            "dhashes": list(all_clip_dhashes),
                            "urls": dict(all_provenance_urls),
                            "tabs": dict(all_provenance_tabs),
                            "rebuilt_from": dict(all_rebuilt_from),
                        }
            except Exception as exc:
                logger.debug("Cross-project hash/dhash scan skipped: %s", exc)

        rebuilt_from = str((prov_check.get("receipt") or {}).get("rebuilt_from_frozen_project") or "").strip()
        from pipeline.config import PRE_R76_FROZEN_V8_PROJECTS, PRE_R77_FROZEN_V8_PROJECTS

        frozen_set = set(PRE_R76_FROZEN_V8_PROJECTS) | set(PRE_R77_FROZEN_V8_PROJECTS)
        if not all_rebuilt_from and (p_dir.name in frozen_set or rebuilt_from in frozen_set) and PROJECTS_DIR.exists():
            try:
                for other_dir in sorted(PROJECTS_DIR.iterdir()):
                    rp = other_dir / "03_visuals" / "flow_provenance_receipt.json"
                    if other_dir.is_dir() and rp.exists():
                        try:
                            o_rb = str(json.loads(rp.read_text(encoding="utf-8")).get("rebuilt_from_frozen_project") or "").strip()
                            if o_rb:
                                all_rebuilt_from[other_dir.name] = o_rb
                        except Exception:
                            pass
            except Exception:
                pass
        allowed_ancestors: set[str] = {p_dir.name}
        if rebuilt_from and rebuilt_from in frozen_set:
            allowed_ancestors.add(rebuilt_from)
            for pid, src in all_rebuilt_from.items():
                if src == rebuilt_from:
                    allowed_ancestors.add(pid)
        if p_dir.name in frozen_set:
            for pid, src in all_rebuilt_from.items():
                if src == p_dir.name:
                    allowed_ancestors.add(pid)

        if my_flow_url and all_provenance_urls:
            shared_urls = [
                pid for pid in all_provenance_urls.get(my_flow_url, []) if pid not in allowed_ancestors
            ]
            if shared_urls:
                provenance_errors.append(f"shared_flow_project_url_across_projects:{shared_urls}")
        if my_tab_id and all_provenance_tabs:
            shared_tabs = [
                pid for pid in all_provenance_tabs.get(my_tab_id, []) if pid not in allowed_ancestors
            ]
            if shared_tabs:
                provenance_errors.append(f"shared_tab_target_id_across_projects:{shared_tabs}")

        provenance_valid = len(provenance_errors) == 0

        my_rcpt_clips = {
            f"clip_{int(c.get('clip_index', i))}.mp4": str(c.get("sha256", ""))
            for i, c in enumerate((prov_check.get("receipt") or {}).get("clips", []), 1)
            if isinstance(c, dict) and c.get("sha256")
        }
        dhash_mem_cache = getattr(cls, "_CLIP_DHASH_MEM_CACHE", None)
        if dhash_mem_cache is None:
            dhash_mem_cache = {}
            cls._CLIP_DHASH_MEM_CACHE = dhash_mem_cache

        existing_clip_hashes: dict[str, str] = {}
        existing_clip_dhashes: dict[str, dict[str, str]] = {}
        rep_path = p_dir / "05_assembly" / "video_autopsy_report.json"
        if rep_path.exists():
            try:
                old_td = json.loads(rep_path.read_text(encoding="utf-8")).get("thumbnails_and_dedup") or {}
                existing_clip_hashes = dict(old_td.get("clip_hashes") or {})
                existing_clip_dhashes = dict(old_td.get("clip_dhashes") or {})
            except Exception:
                pass

        from pipeline.media_cache import cached_by_clip_stat, fast_file_sha256

        for cf in clip_files:
            if cf.is_file() and cf.stat().st_size >= MIN_CLIP_SIZE_BYTES:
                full_sha = fast_file_sha256(cf)
                h_val = full_sha[:16]
                clip_hashes[cf.name] = h_val

                def _probe_clip_dedup(local_cf: Path) -> dict[str, Any]:
                    sc = MediaIntegrityValidator.verify_not_synthetic_derivative(local_cf, strict=False)
                    dh = MediaIntegrityValidator.compute_perceptual_dhash(local_cf)
                    return {"syn": sc, "dhash": dh}

                dedup_info = cached_by_clip_stat(
                    cf,
                    namespace="autopsy_clip_dedup_v1",
                    compute_fn=_probe_clip_dedup,
                )
                syn_check = dedup_info["syn"]
                if syn_check["is_synthetic_derivative"]:
                    synthetic_derivative_clips.append({
                        "clip": cf.name,
                        "matched_markers": syn_check["matched_markers"],
                    })

                if all_clip_hashes and h_val in all_clip_hashes:
                    others = [pid for pid in all_clip_hashes[h_val] if pid not in allowed_ancestors]
                    if others:
                        shared_clips.append({
                            "clip": cf.name,
                            "sha256_short": h_val,
                            "shared_with": others,
                        })

                my_dhash = dedup_info["dhash"]
                dhash_mem_cache[full_sha] = my_dhash
                clip_dhashes[cf.name] = {
                    "dhash_20": my_dhash.get("dhash_20", ""),
                    "dhash_50": my_dhash.get("dhash_50", ""),
                    "dhash_80": my_dhash.get("dhash_80", ""),
                    "dhash_flip_50": my_dhash.get("dhash_flip_50", ""),
                }
                if all_clip_dhashes:
                    sim_qa_p = p_dir / "03_visuals" / "brain_simulator_clips" / f"{cf.stem}_sim_qa.json"
                    is_verified_sim_clip = False
                    if sim_qa_p.is_file():
                        try:
                            is_verified_sim_clip = bool(json.loads(sim_qa_p.read_text(encoding="utf-8")).get("passed"))
                        except Exception:
                            is_verified_sim_clip = False
                    is_my_provenance_verified_clip = bool(
                        (
                            provenance_valid
                            and my_rcpt_clips.get(cf.name, "").lower() == full_sha.lower()
                            and not syn_check["is_synthetic_derivative"]
                        )
                        or is_verified_sim_clip
                    )
                    for other_entry in all_clip_dhashes:
                        if other_entry.get("project_id") in allowed_ancestors:
                            continue
                        dist = MediaIntegrityValidator.min_perceptual_dhash_distance(my_dhash, other_entry["dhash"])
                        # If both clips are cryptographically provenance-verified from distinct Flow project URLs
                        # and have distinct SHA-256s (not shared_clips), require near-identical dHash (<= 4) before
                        # flagging a cross-project derivative false positive on flat-shaded low-poly rooms/shelves.
                        eff_dhash_thresh = 4 if is_my_provenance_verified_clip else MAX_PERCEPTUAL_DHASH_HAMMING_DISTANCE
                        if dist <= eff_dhash_thresh:
                            derivative_clips.append({
                                "clip": cf.name,
                                "matched_project": other_entry["project_id"],
                                "matched_clip": other_entry["clip"],
                                "dhash_hamming_distance": dist,
                            })
                            break

        return {
            "thumbnails_exist": thumbs_exist,
            "thumb_ab_bg_diff": ab_diff,
            "thumb_bc_bg_diff": bc_diff,
            "thumb_ac_bg_diff": ac_diff,
            "thumbnails_distinct": thumbnails_distinct,
            "native_clips_count": len(clip_hashes),
            "clip_hashes": clip_hashes,
            "clip_dhashes": clip_dhashes,
            "shared_clips_across_projects": shared_clips,
            "derivative_clips_across_projects": derivative_clips,
            "synthetic_derivative_clips": synthetic_derivative_clips,
            "provenance_receipt_valid": provenance_valid,
            "provenance_errors": provenance_errors,
            "flow_project_url": my_flow_url,
            "tab_target_id": my_tab_id,
        }


    @classmethod
    def inspect_project(
        cls,
        project_id_or_dir: str | Path,
        all_clip_hashes: dict[str, list[str]] | None = None,
        all_clip_dhashes: list[dict[str, Any]] | None = None,
        all_provenance_urls: dict[str, list[str]] | None = None,
        all_provenance_tabs: dict[str, list[str]] | None = None,
        save_report: bool = True,
    ) -> dict[str, Any]:
        """
        Executes a full multimodal forensic autopsy on a project's rendered MP4, WAV, ASS, thumbnails,
        native clip voice/ASR/truncation telemetry, and Google Flow Provenance Receipt (Guard 1, Guard 2, Guard 6),
        computes a 0-100 quality score, and generates actionable self-evolution prescriptions.
        """
        p_dir = Path(project_id_or_dir) if isinstance(project_id_or_dir, Path) else (PROJECTS_DIR / str(project_id_or_dir))
        if not p_dir.exists() and not isinstance(project_id_or_dir, Path) and PROJECTS_DIR.exists():
            matches = sorted([d for d in PROJECTS_DIR.iterdir() if d.is_dir() and d.name.startswith(str(project_id_or_dir))])
            if len(matches) == 1:
                p_dir = matches[0]
        project_id = p_dir.name
        from pipeline.assembler import verify_script_audio_freshness

        verify_script_audio_freshness(p_dir, context="autopsy")
        mp4_path = p_dir / "05_assembly" / "final_shorts_1080x1920.mp4"
        wav_path = p_dir / "04_audio" / "audio_master.wav"
        ass_path = p_dir / "04_audio" / "subtitles.ass"
        edl_path = p_dir / "05_assembly" / "edit_decision_list.json"
        vp_file = p_dir / "03_visuals" / "visual_plan.json"
        vp_obj: dict[str, Any] = {}
        if vp_file.exists():
            try:
                vp_obj = json.loads(vp_file.read_text(encoding="utf-8"))
            except Exception:
                vp_obj = {}
        is_diorama = edl_path.exists() or is_diorama_profile(vp_obj)
        is_v7_diorama = is_diorama_v7_plan(vp_obj)
        if not is_v7_diorama and edl_path.exists():
            try:
                is_v7_diorama = int(json.loads(edl_path.read_text(encoding="utf-8")).get("schema") or 6) >= 7
            except Exception:
                pass

        from pipeline.config import (
            MICRO_SHORT_PROFILE,
            SHORTS_90S_CUT_COUNT_MIN,
            SHORTS_90S_PROFILE,
            resolve_shorts_format_profile,
            shorts_duration_range_for_profile,
        )

        edl_probe_obj: dict[str, Any] = {}
        if edl_path.exists():
            try:
                edl_probe_obj = json.loads(edl_path.read_text(encoding="utf-8"))
            except Exception:
                edl_probe_obj = {}
        script_probe_obj: dict[str, Any] = {}
        script_probe_file = p_dir / "02_script" / "script.json"
        if script_probe_file.exists():
            try:
                script_probe_obj = json.loads(script_probe_file.read_text(encoding="utf-8"))
            except Exception:
                script_probe_obj = {}
        autopsy_fmt_prof = resolve_shorts_format_profile(
            vp_obj,
            script_probe_obj,
            edl_probe_obj,
            project_id=project_id,
        )
        if is_diorama and autopsy_fmt_prof in (MICRO_SHORT_PROFILE, SHORTS_90S_PROFILE, SHORTS_EXPRESSIVE_V8_PROFILE):
            diorama_min_bound, diorama_max_bound = shorts_duration_range_for_profile(
                autopsy_fmt_prof,
                project_id=project_id,
                plan=vp_obj,
                script_doc=script_probe_obj,
            )
        else:
            diorama_min_bound = DIORAMA_V7_DURATION_MIN_SEC if is_v7_diorama else DIORAMA_DURATION_MIN_SEC
            diorama_max_bound = SHORTS_HARD_CEILING_SEC

        exp_dur = diorama_min_bound if is_diorama else expected_final_duration_sec(DEFAULT_CLIP_COUNT)
        video_metrics = cls.inspect_video_stream(mp4_path, expected_duration_sec=exp_dur)
        audio_source = mp4_path if mp4_path.exists() else wav_path
        audio_metrics = cls.inspect_audio_stream(audio_source, expected_duration_sec=exp_dur)
        subtitle_metrics = cls.inspect_subtitles(ass_path)
        thumb_metrics = cls.inspect_thumbnails_and_dedup(
            p_dir,
            all_clip_hashes=all_clip_hashes,
            all_clip_dhashes=all_clip_dhashes,
            all_provenance_urls=all_provenance_urls,
            all_provenance_tabs=all_provenance_tabs,
        )
        from pipeline.ref_qa import is_reference_qa_report_fresh
        from pipeline.storage import compute_sha256

        clip_voice_asr_metrics: dict[str, Any] = {"checked": False}
        clip_qa_metrics: dict[str, Any] = {"checked": False, "all_passed": True, "fresh": True}
        ref_qa_metrics: dict[str, Any] = {"checked": False, "all_passed": True, "fresh": True, "reference_qa_score": 100.0}
        ref_dir = p_dir / "03_visuals" / "reference_images"
        ref_qa_file = ref_dir / "reference_image_qa_report.json"
        if not ref_qa_file.exists():
            alt_ref_qa = p_dir / "03_visuals" / "reference_image_qa_report.json"
            if alt_ref_qa.exists():
                ref_qa_file = alt_ref_qa
        has_ref_pngs = ref_dir.exists() and any(ref_dir.glob("*.png"))
        if ref_qa_file.exists() or has_ref_pngs:
            if ref_qa_file.exists():
                try:
                    ref_qa_metrics = json.loads(ref_qa_file.read_text(encoding="utf-8"))
                except Exception:
                    ref_qa_metrics = {"all_passed": False, "reference_qa_score": 0.0}
                fresh_ok, fresh_reasons = is_reference_qa_report_fresh(p_dir, ref_qa_metrics)
                ref_qa_metrics["fresh"] = fresh_ok
                ref_qa_metrics["stale_reasons"] = fresh_reasons
            else:
                ref_qa_metrics = {
                    "all_passed": False,
                    "fresh": False,
                    "stale_reasons": ["missing_reference_image_qa_report"],
                    "reference_qa_score": 0.0,
                }
            ref_qa_metrics["checked"] = True

        prescriptions: list[dict[str, Any]] = []
        advisory_warnings: list[dict[str, Any]] = []
        score = 100.0

        if ref_qa_metrics.get("checked") and (
            not ref_qa_metrics.get("all_passed", False) or not ref_qa_metrics.get("fresh", False)
        ):
            score -= 20.0
            prescriptions.append({
                "defect_code": "DEFECT_STALE_OR_FAILED_REFERENCE_QA",
                "severity": "HIGH",
                "component": "03_visuals/reference_images/reference_image_qa_report.json",
                "measured": {
                    "all_passed": ref_qa_metrics.get("all_passed"),
                    "fresh": ref_qa_metrics.get("fresh"),
                    "stale_reasons": ref_qa_metrics.get("stale_reasons", []),
                    "reference_qa_score": ref_qa_metrics.get("reference_qa_score", 0.0),
                },
                "prescription": (
                    "Re-run `main.py ref-qa --project <id>` after generating/updating reference images and clips "
                    "so Q1-Q11 pass with matching SHA-256 bindings."
                ),
            })

        # 0. Guard 1, Guard 2 & Guard 6 (R37): Cryptographic Flow Provenance Receipt & Anti-Derivative Check
        if not thumb_metrics["provenance_receipt_valid"] or thumb_metrics["synthetic_derivative_clips"]:
            score -= 50.0
            prescriptions.append({
                "defect_code": "missing_or_invalid_flow_provenance_receipt",
                "severity": "CRITICAL",
                "component": "03_visuals/flow_provenance_receipt.json",
                "measured": {
                    "provenance_receipt_valid": thumb_metrics["provenance_receipt_valid"],
                    "provenance_errors": thumb_metrics["provenance_errors"],
                    "synthetic_derivative_clips": thumb_metrics["synthetic_derivative_clips"],
                },
                "prescription": (
                    "Generate all 5-10 clips live in a dedicated 1:1:1 Naver Whale Google Flow tab via "
                    "FlowProjectSubagentWorker and record a cryptographic 03_visuals/flow_provenance_receipt.json."
                ),
            })

        if thumb_metrics["derivative_clips_across_projects"] or thumb_metrics["shared_clips_across_projects"]:
            score -= 40.0
            prescriptions.append({
                "defect_code": "derivative_clips_across_projects",
                "severity": "CRITICAL",
                "component": "03_visuals/flow_native_clips",
                "measured": {
                    "derivative_clips_across_projects": thumb_metrics["derivative_clips_across_projects"],
                    "shared_clips_across_projects": thumb_metrics["shared_clips_across_projects"],
                },
                "prescription": (
                    "Eliminate recycled/FFmpeg-transformed clips across projects (dHash Hamming distance <= 10). "
                    "Every project must use freshly generated, perceptually distinct Google Flow clips."
                ),
            })

        # 1. Frame & Stream Integrity (25 pts)
        if video_metrics["has_early_stream_freeze"] or video_metrics["decoded_frame_count"] < 720:
            score -= 25.0
            prescriptions.append({
                "defect_code": "DEFECT_EARLY_FRAME_FREEZE",
                "severity": "CRITICAL",
                "component": "05_assembly/final_shorts_1080x1920.mp4",
                "measured": {
                    "decoded_frames": video_metrics["decoded_frame_count"],
                    "decoded_duration_sec": video_metrics["decoded_duration_sec"],
                },
                "prescription": (
                    "Normalize per-clip PTS/FPS before trim (fps=30,setpts=PTS-STARTPTS) "
                    "to prevent mixed-timebase frame drops across the assembled Shorts timeline."
                ),
            })

        if video_metrics["cut_count"] < 3:
            score -= 10.0
            prescriptions.append({
                "defect_code": "DEFECT_MISSING_SCENE_CUTS",
                "severity": "HIGH",
                "component": "05_assembly/final_shorts_1080x1920.mp4",
                "measured": {"cut_count": video_metrics["cut_count"], "cuts": video_metrics["detected_cuts_sec"]},
                "prescription": "Re-assemble multi-clip sequence with distinct dynamic cuts across all narrative stages.",
            })
        elif video_metrics["rigid_6s_cuts"]:
            score -= 5.0
            prescriptions.append({
                "defect_code": "DEFECT_RIGID_6S_CUTS",
                "severity": "LOW",
                "component": "05_assembly/final_shorts_1080x1920.mp4",
                "measured": {"cuts": video_metrics["detected_cuts_sec"]},
                "prescription": "Distribute clip durations according to native clip speech windows instead of fixed 6.0s intervals.",
            })

        # 1b. Neuro-Diorama System v6 Duration Ceiling & Fast-Cut EDL Gates (R58/R59)
        if is_diorama:
            dec_dur = float(video_metrics.get("decoded_duration_sec") or 0.0)
            dec_fc = int(video_metrics.get("decoded_frame_count") or 0)
            is_v8_diorama = is_expressive_v8_plan(vp_obj, edl_probe_obj, script_probe_obj)
            ceil_fc = (
                SHORTS_HARD_CEILING_FRAMES
                if is_v8_diorama
                else (SHORTS_HARD_CEILING_FRAMES_V7 if is_v7_diorama else SHORTS_HARD_CEILING_FRAMES)
            )
            min_diorama_dur = diorama_min_bound
            max_diorama_dur = diorama_max_bound
            if dec_dur > max_diorama_dur or dec_fc > ceil_fc or dec_dur < min_diorama_dur * 0.96:
                score -= 30.0
                prescriptions.append({
                    "defect_code": "DEFECT_DIORAMA_DURATION_BOUNDS",
                    "severity": "CRITICAL",
                    "component": "05_assembly/final_shorts_1080x1920.mp4",
                    "measured": {"decoded_duration_sec": dec_dur, "decoded_frames": dec_fc},
                    "prescription": (
                        f"Clamp Neuro-Diorama Short strictly within [{min_diorama_dur}s, {max_diorama_dur}s] "
                        f"and <= {ceil_fc} frames so YouTube classifies it as a Short (R58/R63)."
                    ),
                })
            is_v8_diorama = is_expressive_v8_plan(vp_obj, edl_probe_obj, script_probe_obj)
            if edl_path.exists():
                try:
                    edl_obj = edl_probe_obj or json.loads(edl_path.read_text(encoding="utf-8"))
                    is_v8_diorama = is_v8_diorama or is_expressive_v8_plan(vp_obj, edl_obj, script_probe_obj)
                    from pipeline.config import (
                        EXPRESSIVE_V8_LEGACY_CLIP_COUNT_MIN,
                        BRAIN_SIM_ONLY_CLIP_COUNT_RANGE,
                        EXPRESSIVE_V8_LEGACY_INDOOR_CLIP_COUNT_RANGE,
                        EXPRESSIVE_V8_LEGACY_LONG_TAKE_MAX_SEC,
                        EXPRESSIVE_V8_LEGACY_MAX_CUT_SEC,
                        EXPRESSIVE_V8_R76_CLIP_COUNT_RANGE,
                        EXPRESSIVE_V8_R76_HUMAN_MIN_CUT_SEC,
                        EXPRESSIVE_V8_R76_MAX_CUT_SEC,
                        EXPRESSIVE_V8_SPATIAL_RELAY_MIN_CUT_SEC,
                        SHORTS_EXPRESSIVE_V8_CUT_COUNT_MIN,
                        is_brain_sim_only_plan,
                        is_r72_open_world_v8_plan,
                        is_r76_v8_plan,
                        is_r82_dual_speed_pacing_plan,
                    )
                    from pipeline.config import (
                        R82_BRAIN_MAX_CUT_SEC,
                        R82_BRAIN_MIN_CUT_SEC,
                        R82_CUT_COUNT_RANGE,
                        R82_HUMAN_MAX_CUT_SEC,
                        R82_HUMAN_MIN_CUT_SEC,
                        is_r85_flow_31_brain_plan,
                    )

                    is_brain_only_autopsy = is_v8_diorama and is_brain_sim_only_plan(vp_obj, script_probe_obj)
                    is_r85_autopsy = is_v8_diorama and is_r85_flow_31_brain_plan(
                        vp_obj,
                        script_probe_obj,
                        project_id=edl_path.parent.parent.name,
                    )
                    is_r82_autopsy = is_v8_diorama and (
                        is_r85_autopsy
                        or is_r82_dual_speed_pacing_plan(
                            vp_obj,
                            script_probe_obj,
                            project_id=edl_path.parent.parent.name,
                        )
                    )
                    is_r76_autopsy = is_v8_diorama and is_r76_v8_plan(
                        vp_obj,
                        script_probe_obj,
                        project_id=edl_path.parent.parent.name,
                    )
                    is_r72_autopsy = is_v8_diorama and is_r72_open_world_v8_plan(
                        vp_obj,
                        script_probe_obj,
                        project_id=edl_path.parent.parent.name,
                    )
                    fmt_prof = autopsy_fmt_prof
                    if fmt_prof == MICRO_SHORT_PROFILE:
                        min_edl_cuts = MICRO_SHORT_CUT_MIN
                    elif fmt_prof == SHORTS_EXPRESSIVE_V8_PROFILE or is_v8_diorama:
                        if bool((vp_obj or {}).get("allow_legacy_v8_clip_count")):
                            min_edl_cuts = EXPRESSIVE_V8_LEGACY_CLIP_COUNT_MIN
                        elif is_brain_only_autopsy:
                            min_edl_cuts = int(BRAIN_SIM_ONLY_CLIP_COUNT_RANGE[0])
                        elif is_r82_autopsy:
                            min_edl_cuts = int(R82_CUT_COUNT_RANGE[0])
                        elif is_r76_autopsy:
                            min_edl_cuts = int(EXPRESSIVE_V8_R76_CLIP_COUNT_RANGE[0])
                        elif not is_r72_autopsy:
                            min_edl_cuts = EXPRESSIVE_V8_LEGACY_INDOOR_CLIP_COUNT_RANGE[0]
                        elif dec_dur >= 55.0:
                            min_edl_cuts = SHORTS_EXPRESSIVE_V8_CUT_COUNT_MIN
                        else:
                            min_edl_cuts = EXPRESSIVE_V8_CLIP_COUNT_MIN
                    elif fmt_prof == SHORTS_90S_PROFILE:
                        min_edl_cuts = SHORTS_90S_CUT_COUNT_MIN
                    else:
                        min_edl_cuts = DIORAMA_TARGET_CUT_MIN
                    if int(edl_obj.get("cut_count") or 0) < min_edl_cuts:
                        score -= 15.0
                        prescriptions.append({
                            "defect_code": "DEFECT_DIORAMA_LOW_CUT_DENSITY",
                            "severity": "HIGH",
                            "component": "05_assembly/edit_decision_list.json",
                            "measured": {"edl_cut_count": edl_obj.get("cut_count"), "min_required": min_edl_cuts},
                            "prescription": f"Ensure NLE EDL has >= {min_edl_cuts} cuts (R58/R66.4/R72/R82).",
                        })
                    if is_v8_diorama:
                        edl_cuts_v8 = [c for c in (edl_obj.get("cuts") or []) if isinstance(c, dict)]
                        min_cut_v8 = (
                            1.40
                            if is_brain_only_autopsy
                            else (
                                float(R82_HUMAN_MIN_CUT_SEC)
                                if is_r82_autopsy
                                else (float(EXPRESSIVE_V8_R76_HUMAN_MIN_CUT_SEC) if is_r76_autopsy else float(EXPRESSIVE_V8_MIN_CUT_SEC))
                            )
                        )
                        max_single_v8 = (
                            9.50
                            if is_brain_only_autopsy
                            else (
                                float(R82_BRAIN_MAX_CUT_SEC)
                                if is_r82_autopsy
                                else (
                                    float(EXPRESSIVE_V8_R76_MAX_CUT_SEC)
                                    if is_r76_autopsy
                                    else (EXPRESSIVE_V8_MAX_CUT_SEC if is_r72_autopsy else EXPRESSIVE_V8_LEGACY_MAX_CUT_SEC)
                                )
                            )
                        )
                        max_hold_v8 = (
                            9.50
                            if is_brain_only_autopsy
                            else (
                                float(R82_BRAIN_MAX_CUT_SEC)
                                if is_r82_autopsy
                                else (
                                    float(EXPRESSIVE_V8_R76_MAX_CUT_SEC)
                                    if is_r76_autopsy
                                    else (EXPRESSIVE_V8_MAX_CUT_SEC if is_r72_autopsy else EXPRESSIVE_V8_LEGACY_LONG_TAKE_MAX_SEC)
                                )
                            )
                        )
                        bad_dur_cuts_v8 = [
                            {
                                "cut_index": c.get("cut_index"),
                                "duration_sec": round(float(c.get("duration_sec") or 0.0), 4),
                            }
                            for c in edl_cuts_v8
                            if float(c.get("duration_sec") or 0.0)
                            < (
                                (
                                    float(R82_BRAIN_MIN_CUT_SEC)
                                    if (
                                        str(c.get("grammar") or "") in ("brain_simulator_3d", "expressive_xray_brain")
                                        or str(c.get("render_engine") or "") == "blender_3d_simulator"
                                        or bool(c.get("brain_clip"))
                                    )
                                    else float(R82_HUMAN_MIN_CUT_SEC)
                                )
                                if is_r82_autopsy
                                else (
                                    float(EXPRESSIVE_V8_SPATIAL_RELAY_MIN_CUT_SEC)
                                    if (
                                        is_r76_autopsy
                                        and not is_brain_only_autopsy
                                        and (
                                            str(c.get("grammar") or "") == "spatial_3d_arrow_diorama"
                                            or bool(c.get("spatial_relay_cut"))
                                        )
                                    )
                                    else min_cut_v8
                                )
                            )
                            - 1e-3
                            or float(c.get("duration_sec") or 0.0)
                            > (
                                (
                                    float(R82_BRAIN_MAX_CUT_SEC)
                                    if (
                                        str(c.get("grammar") or "") in ("brain_simulator_3d", "expressive_xray_brain")
                                        or str(c.get("render_engine") or "") == "blender_3d_simulator"
                                        or bool(c.get("brain_clip"))
                                    )
                                    else float(R82_HUMAN_MAX_CUT_SEC)
                                )
                                if is_r82_autopsy
                                else (
                                    max_hold_v8
                                    if int(c.get("end_sentence_index") or c.get("sentence_index") or 0)
                                    > int(c.get("sentence_index") or 0)
                                    else max_single_v8
                                )
                            )
                            + 1e-3
                        ]
                        if bad_dur_cuts_v8:
                            dur_entry = {
                                "defect_code": "DEFECT_EXPRESSIVE_V8_CUT_DURATION_BOUNDS",
                                "severity": ("ADVISORY" if is_r85_autopsy else "HIGH"),
                                "tier": ("tier2_advisory_score" if is_r85_autopsy else "tier1_blocker"),
                                "component": "05_assembly/edit_decision_list.json",
                                "measured": {
                                    "out_of_bounds_cuts": bad_dur_cuts_v8[:10],
                                    "min_cut_sec": min_cut_v8,
                                    "max_cut_sec": max_single_v8,
                                },
                                "prescription": (
                                    f"Keep every expressive_25d_v8 cut within "
                                    f"[{min_cut_v8:.2f}s, {max_single_v8:.2f}s] (R68/R72/R76-P; Tier-2 advisory on R85+)."
                                ),
                            }
                            if is_r85_autopsy:
                                score -= 5.0
                                advisory_warnings.append(dur_entry)
                            else:
                                score -= 20.0
                                prescriptions.append(dur_entry)
                    elif is_porcelain_v7_plan(vp_obj, edl_obj) and fmt_prof != MICRO_SHORT_PROFILE:
                        edl_cuts = [c for c in (edl_obj.get("cuts") or []) if isinstance(c, dict)]
                        bad_dur_cuts = [
                            {
                                "cut_index": c.get("cut_index"),
                                "duration_sec": round(float(c.get("duration_sec") or 0.0), 4),
                            }
                            for c in edl_cuts
                            if float(c.get("duration_sec") or 0.0) < PORCELAIN_V7_MIN_CUT_SEC - 1e-3
                            or float(c.get("duration_sec") or 0.0) > PORCELAIN_V7_LONG_TAKE_MAX_SEC + 1e-3
                        ]
                        if bad_dur_cuts:
                            score -= 20.0
                            prescriptions.append({
                                "defect_code": "DEFECT_PORCELAIN_CUT_DURATION_BOUNDS",
                                "severity": "HIGH",
                                "component": "05_assembly/edit_decision_list.json",
                                "measured": {
                                    "out_of_bounds_cuts": bad_dur_cuts[:10],
                                    "min_cut_sec": PORCELAIN_V7_MIN_CUT_SEC,
                                    "max_cut_sec": PORCELAIN_V7_LONG_TAKE_MAX_SEC,
                                },
                                "prescription": (
                                    f"Keep every porcelain_cinematic_v7 cut strictly within "
                                    f"[{PORCELAIN_V7_MIN_CUT_SEC:.2f}s, {PORCELAIN_V7_LONG_TAKE_MAX_SEC:.2f}s] "
                                    "using same-scene multi-angle coverage instead of stagnant holds (R66.4)."
                                ),
                            })
                    planned_fc = int(edl_obj.get("total_frames") or dec_fc)
                    if abs(dec_fc - planned_fc) > 2:
                        score -= 20.0
                        prescriptions.append({
                            "defect_code": "DEFECT_DIORAMA_FRAME_DRIFT",
                            "severity": "CRITICAL",
                            "component": "05_assembly/final_shorts_1080x1920.mp4",
                            "measured": {"decoded_frames": dec_fc, "planned_edl_frames": planned_fc},
                            "prescription": "Append tpad=stop_mode=clone after fps=30 in _render_cut_segment so zero frames drop across cuts.",
                        })
                    require_zero_reuse = bool(edl_obj.get("zero_clip_reuse")) or bool(vp_obj.get("zero_clip_reuse"))
                    if require_zero_reuse:
                        appearances: dict[int, int] = {}
                        for c_entry in edl_obj.get("cuts") or []:
                            if not isinstance(c_entry, dict):
                                continue
                            if c_entry.get("clip_index") is not None:
                                k1 = int(c_entry["clip_index"])
                                appearances[k1] = appearances.get(k1, 0) + 1
                            if c_entry.get("secondary_clip_index") is not None:
                                k2 = int(c_entry["secondary_clip_index"])
                                appearances[k2] = appearances.get(k2, 0) + 1
                        max_app = max(appearances.values()) if appearances else 0
                        if max_app > DIORAMA_MAX_CLIP_REUSE:
                            reused = {k: v for k, v in appearances.items() if v > DIORAMA_MAX_CLIP_REUSE}
                            score -= 25.0
                            prescriptions.append({
                                "defect_code": "DEFECT_DIORAMA_CLIP_REUSE",
                                "severity": "CRITICAL",
                                "component": "05_assembly/edit_decision_list.json",
                                "measured": {"max_clip_reuse": max_app, "reused_clips": reused},
                                "prescription": f"Generate 1 dedicated Flow clip per cut/pane so max_clip_reuse <= {DIORAMA_MAX_CLIP_REUSE} (0% reuse, R58).",
                            })
                except Exception as exc:
                    import logging

                    logging.getLogger("video_autopsy").warning(
                        "Corrupt or unreadable edit_decision_list.json in %s: %s", p_dir.name, exc, exc_info=True
                    )
                    score -= 45.0
                    prescriptions.append({
                        "defect_code": "DEFECT_CORRUPT_DIORAMA_EDL",
                        "severity": "CRITICAL",
                        "component": "05_assembly/edit_decision_list.json",
                        "measured": {"error": str(exc)},
                        "prescription": "Re-run diorama-assemble to regenerate a valid edit_decision_list.json before QA/publish.",
                    })
            ass_check_file = p_dir / "04_audio" / "subtitles.ass"
            if ass_check_file.exists():
                try:
                    raw_ass_txt = ass_check_file.read_text(encoding="utf-8", errors="ignore")
                    split_years = re.findall(r"\b(?:18|19|20)\s+\d{2}\b", raw_ass_txt)
                    if split_years:
                        score -= 15.0
                        prescriptions.append({
                            "defect_code": "DEFECT_SUBTITLE_YEAR_SPLIT",
                            "severity": "HIGH",
                            "component": "04_audio/subtitles.ass",
                            "measured": {"split_years": split_years[:5]},
                            "prescription": "Format spoken 4-digit years as contiguous digits (e.g. '2012', never '20 12') in plain_language.to_display_text.",
                        })
                except Exception:
                    pass
            if int(subtitle_metrics.get("gold_highlighted_events") or 0) > 0 and not is_v8_diorama:
                score -= 15.0
                prescriptions.append({
                    "defect_code": "DEFECT_DIORAMA_COLORED_SUBTITLES",
                    "severity": "HIGH",
                    "component": "04_audio/subtitles.ass",
                    "measured": {"gold_highlighted_events": subtitle_metrics.get("gold_highlighted_events")},
                    "prescription": "Use 100% pure-white (#FFFFFF) single-line Default subtitles with zero color tags in neuro_diorama (R59).",
                })

        # 2. Acoustic & Speech Integrity (25 pts)
        if not audio_metrics["has_active_speech"]:
            score -= 25.0
            prescriptions.append({
                "defect_code": "DEFECT_MISSING_NARRATION",
                "severity": "CRITICAL",
                "component": "04_audio/audio_master.wav",
                "measured": {
                    "overall_rms_dbfs": audio_metrics["overall_rms_dbfs"],
                    "dynamic_range_db": audio_metrics["dynamic_range_db"],
                },
                "prescription": "Preserve native Google Flow Puck voiceover audio stream from 03_visuals/flow_native_clips/*.mp4.",
            })
        else:
            if audio_metrics["is_truncated_at_30s"]:
                score -= 15.0
                prescriptions.append({
                    "defect_code": "DEFECT_SPEECH_TRUNCATED_30S",
                    "severity": "CRITICAL",
                    "component": "04_audio/audio_master.wav",
                    "measured": {
                        "speech_end_sec": audio_metrics["speech_end_sec"],
                        "last_100ms_dbfs": audio_metrics["last_100ms_dbfs"],
                    },
                    "prescription": (
                        "Preserve full spoken narration window in each Google Flow clip with a clean tail "
                        "so final words are never clipped."
                    ),
                })
            dur_val = float(audio_metrics.get("duration_sec", 30.0))
            max_allowed = max_allowed_dead_air_sec(dur_val)
            if audio_metrics["cumulative_dead_air_sec"] > max_allowed:
                score -= 10.0
                prescriptions.append({
                    "defect_code": "DEFECT_EXCESS_DEAD_AIR",
                    "severity": "HIGH",
                    "component": "04_audio/audio_master.wav",
                    "measured": {
                        "cumulative_dead_air_sec": audio_metrics["cumulative_dead_air_sec"],
                        "internal_silence_count": audio_metrics["internal_silence_count"],
                    },
                    "prescription": "Trim empty pre/post-speech silence at clip boundaries (+0.15s hold, 400ms pre-roll trim, 1.08x A/V sync).",
                })
            if bool(audio_metrics.get("true_peak_clipping")) or float(audio_metrics.get("peak_dbfs", -96.0)) > -1.0:
                score -= 15.0
                prescriptions.append({
                    "defect_code": "DEFECT_AUDIO_TRUE_PEAK_CLIPPING",
                    "severity": "HIGH",
                    "component": "05_assembly/final_shorts_1080x1920.mp4",
                    "measured": {
                        "peak_dbfs": audio_metrics.get("peak_dbfs"),
                        "true_peak_dbtp": audio_metrics.get("true_peak_dbtp"),
                        "max_allowed_peak_dbfs": -1.0,
                        "max_allowed_true_peak_dbtp": AUDIO_MAX_OVERSAMPLED_TRUE_PEAK_DBTP,
                    },
                    "prescription": (
                        "Apply -1.5 dBFS soft-knee ceiling in generate_audio_master_wav and FFmpeg "
                        "`alimiter=limit=0.841:attack=5:release=50:level=disabled` before AAC encoding so peak <= -1.0 dBFS "
                        f"and oversampled True Peak <= {AUDIO_MAX_OVERSAMPLED_TRUE_PEAK_DBTP} dBTP."
                    ),
                })
            if bool(audio_metrics.get("sibilance_tear_detected")):
                score -= 15.0
                prescriptions.append({
                    "defect_code": "DEFECT_AUDIO_SIBILANCE_HARSHNESS",
                    "severity": "HIGH",
                    "component": "05_assembly/final_shorts_1080x1920.mp4",
                    "measured": {
                        "sibilance_to_body_rms_ratio": audio_metrics.get("sibilance_to_body_rms_ratio"),
                        "sibilance_crest_db": audio_metrics.get("sibilance_crest_db"),
                        "max_sibilance_ratio": AUDIO_MAX_SIBILANCE_ENERGY_RATIO,
                        "max_sibilance_crest_db": AUDIO_MAX_SIBILANCE_CREST_DB,
                    },
                    "prescription": (
                        "Keep TTS volume at DIORAMA_V7_TTS_VOLUME (-10%) and apply Silk Clean 6.5kHz de-esser + "
                        "11.8kHz lowpass EQ without aggressive loudness dynamic boost so 4.2-9.2kHz harshness never tears."
                    ),
                })
            int_lufs = audio_metrics.get("integrated_lufs")
            if is_diorama and int_lufs is not None:
                tgt_lufs = (
                    EXPRESSIVE_V8_TARGET_LUFS
                    if is_expressive_v8_plan(vp_obj, edl_probe_obj, script_probe_obj)
                    else (DIORAMA_V7_TARGET_LUFS if is_v7_diorama else DIORAMA_TARGET_LUFS)
                )
                if abs(float(int_lufs) - float(tgt_lufs)) > DIORAMA_LUFS_TOLERANCE_LU:
                    score -= 12.0
                    prescriptions.append({
                        "defect_code": "DEFECT_AUDIO_LUFS_OUT_OF_RANGE",
                        "severity": "HIGH",
                        "component": "05_assembly/final_shorts_1080x1920.mp4",
                        "measured": {
                            "integrated_lufs": int_lufs,
                            "target_lufs": tgt_lufs,
                            "tolerance_lu": DIORAMA_LUFS_TOLERANCE_LU,
                        },
                        "prescription": (
                            f"Normalize integrated documentary loudness within {tgt_lufs} ± {DIORAMA_LUFS_TOLERANCE_LU} LUFS "
                            "(ITU-R BS.1770 ebur128)."
                        ),
                    })

        # 3. Visual DNA & Motion Integrity (20 pts)
        if video_metrics["optical_flow_mean"] < MIN_OPTICAL_FLOW_THRESHOLD:
            score -= 5.0
            prescriptions.append({
                "defect_code": "DEFECT_LOW_OPTICAL_FLOW",
                "severity": "HIGH",
                "component": "05_assembly/final_shorts_1080x1920.mp4",
                "measured": {"optical_flow_mean": video_metrics["optical_flow_mean"]},
                "prescription": "Ensure dynamic camera motion across all Google Flow clips.",
            })

        # 4. Subtitle Typography & Layout (15 pts)
        if not subtitle_metrics["is_dynamic_2line_compliant"]:
            score -= 15.0
            prescriptions.append({
                "defect_code": "DEFECT_WALL_OF_TEXT_SUBTITLES",
                "severity": "HIGH",
                "component": "04_audio/subtitles.ass",
                "measured": {
                    "dialogue_count": subtitle_metrics["dialogue_count"],
                    "max_words_per_event": subtitle_metrics["max_words_per_event"],
                    "has_raw_stage_labels": subtitle_metrics["has_raw_stage_labels"],
                    "default_font_size": subtitle_metrics["default_font_size"],
                },
                "prescription": (
                    "Rebuild subtitles.ass into single-line speech-locked [trim_start, speech_end] events (2-3 words per event, "
                    "max 1 line, 86px Arial Black, MarginV=440)."
                ),
            })

        # 5. Thumbnail A/B/C Diversity (15 pts)
        if not thumb_metrics["thumbnails_distinct"]:
            score -= 15.0
            prescriptions.append({
                "defect_code": "DEFECT_IDENTICAL_THUMBNAIL_FRAMES",
                "severity": "MEDIUM",
                "component": "06_publish/thumbnail_var_A/B/C.png",
                "measured": {
                    "thumb_ab_bg_diff": thumb_metrics["thumb_ab_bg_diff"],
                    "thumb_ac_bg_diff": thumb_metrics["thumb_ac_bg_diff"],
                },
                "prescription": (
                    "Extract Variant A from Clip 1, Variant B from Clip 3/4, "
                    "and Variant C from final clip so A_vs_B_bg_diff >= 15.0."
                ),
            })

        final_score = round(max(0.0, score), 1)
        critical_defects = [p for p in prescriptions if p["severity"] in ("CRITICAL", "HIGH")]
        passed = (final_score >= 85.0) and (len(critical_defects) == 0)
        defect_codes = [p["defect_code"] for p in prescriptions]
        final_mp4_sha = compute_sha256(mp4_path) if mp4_path.exists() else None

        report = {
            "project_id": project_id,
            "inspected_at": datetime.now(timezone.utc).isoformat(),
            "final_mp4_sha256": final_mp4_sha,
            "autopsy_score": final_score,
            "passed": passed,
            "status": "PASS" if passed else "ACTION_REQUIRED",
            "defect_count": len(prescriptions),
            "defects": defect_codes,
            "video_stream": video_metrics,
            "audio_stream": audio_metrics,
            "subtitles": subtitle_metrics,
            "thumbnails_and_dedup": thumb_metrics,
            "clip_voice_and_asr": clip_voice_asr_metrics,
            "reference_image_qa": ref_qa_metrics,
            "clip_contract_qa": clip_qa_metrics,
            "prescriptions": prescriptions,
            "advisory_warnings": advisory_warnings,
        }

        if save_report and (p_dir / "05_assembly").exists():
            report_path = p_dir / "05_assembly" / "video_autopsy_report.json"
            report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
            if (p_dir / "00_project_manifest.json").exists() and p_dir.resolve().parent == PROJECTS_DIR.resolve():
                try:
                    ProjectStorage(project_id).record_artifact("05_assembly", "video_autopsy_report.json", report_path)
                except Exception as exc:
                    logger.debug("Could not update manifest hash for video_autopsy_report.json: %s", exc)

        return report

    @classmethod
    def inspect_all_projects(cls, save_reports: bool = True) -> dict[str, Any]:
        """
        Runs forensic video/audio autopsy across all rendered projects in PROJECTS_DIR
        and builds a cross-project clip SHA-256 + 64-bit dHash + Provenance URL deduplication map.
        """
        from pipeline.flow_browser import FlowProjectSubagentWorker

        if not PROJECTS_DIR.exists():
            return {"projects_inspected": 0, "all_passed": False, "average_score": 0.0, "projects": {}}

        project_dirs = sorted([
            d for d in PROJECTS_DIR.iterdir()
            if d.is_dir() and (d / "05_assembly" / "final_shorts_1080x1920.mp4").exists()
        ])

        all_clip_hashes: dict[str, list[str]] = {}
        all_clip_dhashes: list[dict[str, Any]] = []
        all_provenance_urls: dict[str, list[str]] = {}
        all_provenance_tabs: dict[str, list[str]] = {}

        for p_dir in project_dirs:
            prov = FlowProjectSubagentWorker.validate_provenance_receipt(p_dir)
            p_url = prov.get("flow_project_url", "")
            p_tab = prov.get("tab_target_id", "")
            if p_url:
                all_provenance_urls.setdefault(p_url, []).append(p_dir.name)
            if p_tab:
                all_provenance_tabs.setdefault(p_tab, []).append(p_dir.name)

            clips_dir = p_dir / "03_visuals" / "flow_native_clips"
            if clips_dir.exists():
                for cf in sorted(clips_dir.glob("*.mp4"), key=numeric_clip_sort_key):
                    if cf.is_file() and cf.stat().st_size >= MIN_CLIP_SIZE_BYTES:
                        h_val = hashlib.sha256(cf.read_bytes()).hexdigest()[:16]
                        all_clip_hashes.setdefault(h_val, []).append(p_dir.name)
                        all_clip_dhashes.append({
                            "project_id": p_dir.name,
                            "clip": cf.name,
                            "dhash": MediaIntegrityValidator.compute_perceptual_dhash(cf),
                        })

        results: dict[str, Any] = {}
        scores: list[float] = []
        all_passed = len(project_dirs) > 0

        for p_dir in project_dirs:
            try:
                rep = cls.inspect_project(
                    p_dir,
                    all_clip_hashes=all_clip_hashes,
                    all_clip_dhashes=all_clip_dhashes,
                    all_provenance_urls=all_provenance_urls,
                    all_provenance_tabs=all_provenance_tabs,
                    save_report=save_reports,
                )
            except RuntimeError as exc:
                rep = {
                    "project_id": p_dir.name,
                    "passed": False,
                    "autopsy_score": 0.0,
                    "error": str(exc),
                }
            results[p_dir.name] = rep
            scores.append(rep["autopsy_score"])
            if not rep["passed"]:
                all_passed = False

        avg_score = round(float(np.mean(scores)), 1) if scores else 0.0
        summary = {
            "inspected_at": datetime.now(timezone.utc).isoformat(),
            "projects_inspected": len(project_dirs),
            "all_passed": all_passed,
            "average_score": avg_score,
            "projects": results,
        }

        if save_reports and PROJECTS_DIR.exists():
            summary_path = PROJECTS_DIR / "autopsy_batch_summary.json"
            summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

        return summary


    @staticmethod
    def refresh_manifest_hashes(storage: ProjectStorage) -> None:
        """Re-computes and updates SHA-256 and byte sizes for all existing artifacts in 00_project_manifest.json."""
        manifest = storage.get_manifest()
        stages = manifest.get("stages", {})
        for stage_name, stage_info in stages.items():
            artifacts = stage_info.get("artifacts", {})
            stage_dir = storage.project_dir / stage_name
            for rel_name in list(artifacts.keys()):
                target = stage_dir / rel_name
                if target.exists() and target.is_file():
                    storage.record_artifact(stage_name, rel_name, target)
        storage.verify_integrity()

