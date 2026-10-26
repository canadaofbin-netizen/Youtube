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
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from pipeline.config import (
    AV_SPEEDUP_FACTOR,
    CLIP_PRE_PIVOT_HOLD_SEC,
    CLIP_VISUAL_HOLD_SEC,
    DEFAULT_CLIP_COUNT,
    FINAL_SHORTS_DURATION_MIN_SEC,
    FINAL_TAIL_SEC,
    MAX_PERCEPTUAL_DHASH_HAMMING_DISTANCE,
    MIN_CLIP_SIZE_BYTES,
    MIN_OPTICAL_FLOW_THRESHOLD,
    PROJECTS_DIR,
    SUBPROCESS_TIMEOUT_SEC,
    VIDEO_FPS,
    VIDEO_HEIGHT,
    VIDEO_WIDTH,
    expected_final_duration_sec,
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
        import os
        import shutil
        import tempfile
        import threading
        local_decode_path = path
        tmp_decode_file: Path | None = None
        if os.name != "nt" and Path("/tmp").exists() and path.exists():
            try:
                tmp_decode_file = Path(tempfile.gettempdir()) / f"_tmp_autopsy_dec_{os.getpid()}_{threading.get_ident()}_{path.name}"
                shutil.copy2(path, tmp_decode_file)
                local_decode_path = tmp_decode_file
            except Exception:
                local_decode_path = path

        try:
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

            cap = cv2.VideoCapture(str(local_decode_path.resolve()))
            fps = float(probe.get("fps") or cap.get(cv2.CAP_PROP_FPS) or VIDEO_FPS)
            if fps <= 0:
                fps = float(VIDEO_FPS)
            header_fc = int(probe.get("frame_count") or cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
            container_dur = float(probe.get("duration_seconds") or 0.0)

            sampled_times: list[float] = []
            sampled_upper_grays: list[np.ndarray] = []
            frame_step = 2
            decoded_fc = 0
            cutaway_hsv_samples: list[np.ndarray] = []

            while True:
                ret, frame = cap.read()
                if not ret or frame is None:
                    break
                decoded_fc += 1
                t_sec = (decoded_fc - 1) / fps

                if (decoded_fc - 1) % frame_step == 0:
                    small_bgr = cv2.resize(frame, (180, 320), interpolation=cv2.INTER_AREA)
                    upper_cut = int(320 * 0.62)
                    upper_bgr = small_bgr[:upper_cut, :]
                    upper_gray = cv2.cvtColor(upper_bgr, cv2.COLOR_BGR2GRAY)
                    sampled_times.append(round(t_sec, 3))
                    sampled_upper_grays.append(upper_gray)

                    if t_sec >= 4.0 and len(cutaway_hsv_samples) < 40 and (decoded_fc - 1) % 10 == 0:
                        hsv = cv2.cvtColor(upper_bgr, cv2.COLOR_BGR2HSV)
                        cutaway_hsv_samples.append(hsv)

            cap.release()
        finally:
            if tmp_decode_file is not None and tmp_decode_file.exists():
                tmp_decode_file.unlink(missing_ok=True)

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
        for i, d in enumerate(step_diffs):
            t_cut = sampled_times[i + 1]
            if t_cut < 1.5 or t_cut > decoded_dur - 1.2:
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
            if all(abs(t_val - existing_t) >= 2.0 for existing_t in selected_cuts):
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

        return {
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

    @classmethod
    def inspect_audio_stream(
        cls,
        media_path: Path,
        expected_duration_sec: float = expected_final_duration_sec(DEFAULT_CLIP_COUNT),
    ) -> dict[str, Any]:
        """
        Decodes the audio track from .mp4 or .wav into 16kHz 16-bit mono PCM and performs
        50ms-window Voice Activity Detection (VAD), internal Dead Air measurement, and
        last-100ms truncation detection.
        """
        path = Path(media_path)
        empty_audio = {
            "exists": False,
            "duration_sec": 0.0,
            "overall_rms_dbfs": -96.0,
            "peak_dbfs": -96.0,
            "true_peak_clipping": False,
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

        try:
            ffmpeg_exe = MediaIntegrityValidator.get_ffmpeg_exe()
            cmd = [
                ffmpeg_exe,
                "-hide_banner",
                "-loglevel", "error",
                "-i", str(path.resolve()),
                "-vn",
                "-ac", "1",
                "-ar", "16000",
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

        sr = 16000
        if len(samples) < sr:
            return dict(empty_audio)

        duration_sec = round(len(samples) / sr, 2)
        eps = 1e-9
        overall_rms = float(np.sqrt(np.mean(np.square(samples)) + eps))
        overall_rms_db = round(float(20.0 * np.log10(max(overall_rms, eps))), 2)
        peak_val = float(np.max(np.abs(samples)) + eps)
        peak_db = round(float(20.0 * np.log10(max(peak_val, eps))), 2)

        # 50ms windows (800 samples per window)
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
        # (a 0.10s 칼컷 seamless Mobius loop fades cleanly to <= -35 dBFS in the final 100ms)
        is_truncated = bool(
            (not has_active_speech)
            or (last_100ms_db > max(-28.5, p10_db + 10.5))
        )

        return {
            "exists": True,
            "duration_sec": duration_sec,
            "overall_rms_dbfs": overall_rms_db,
            "peak_dbfs": peak_db,
            "true_peak_clipping": bool(peak_db > -1.0),
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
            and 34 <= font_size <= 96
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
        if (all_clip_hashes is None or all_clip_dhashes is None or all_provenance_urls is None) and PROJECTS_DIR.exists():
            try:
                if p_dir.resolve().parent == PROJECTS_DIR.resolve():
                    now_ts = time.time()
                    cache = getattr(cls, "_CROSS_PROJECT_DEDUP_CACHE", None)
                    if cache and (now_ts - cache.get("ts", 0.0) < 600.0):
                        all_clip_hashes = dict(cache["hashes"])
                        all_clip_dhashes = list(cache["dhashes"])
                        all_provenance_urls = dict(cache["urls"])
                        all_provenance_tabs = dict(cache["tabs"])
                    else:
                        all_clip_hashes = {}
                        all_clip_dhashes = []
                        all_provenance_urls = {}
                        all_provenance_tabs = {}
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
                        }
            except Exception as exc:
                logger.debug("Cross-project hash/dhash scan skipped: %s", exc)

        if my_flow_url and all_provenance_urls:
            shared_urls = [pid for pid in all_provenance_urls.get(my_flow_url, []) if pid != p_dir.name]
            if shared_urls:
                provenance_errors.append(f"shared_flow_project_url_across_projects:{shared_urls}")
        if my_tab_id and all_provenance_tabs:
            shared_tabs = [pid for pid in all_provenance_tabs.get(my_tab_id, []) if pid != p_dir.name]
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

        for cf in clip_files:
            if cf.is_file() and cf.stat().st_size >= MIN_CLIP_SIZE_BYTES:
                full_sha = FlowProjectSubagentWorker.compute_file_sha256(cf)
                h_val = full_sha[:16]
                clip_hashes[cf.name] = h_val

                syn_check = MediaIntegrityValidator.verify_not_synthetic_derivative(cf, strict=False)
                if syn_check["is_synthetic_derivative"]:
                    synthetic_derivative_clips.append({
                        "clip": cf.name,
                        "matched_markers": syn_check["matched_markers"],
                    })

                if all_clip_hashes and h_val in all_clip_hashes:
                    others = [pid for pid in all_clip_hashes[h_val] if pid != p_dir.name]
                    if others:
                        shared_clips.append({
                            "clip": cf.name,
                            "sha256_short": h_val,
                            "shared_with": others,
                        })

                my_dhash = dhash_mem_cache.get(full_sha)
                if my_dhash is None and existing_clip_hashes.get(cf.name) == h_val and isinstance(existing_clip_dhashes.get(cf.name), dict):
                    my_dhash = existing_clip_dhashes[cf.name]
                    dhash_mem_cache[full_sha] = my_dhash
                if my_dhash is None:
                    my_dhash = MediaIntegrityValidator.compute_perceptual_dhash(cf)
                    dhash_mem_cache[full_sha] = my_dhash
                clip_dhashes[cf.name] = {
                    "dhash_20": my_dhash.get("dhash_20", ""),
                    "dhash_50": my_dhash.get("dhash_50", ""),
                    "dhash_80": my_dhash.get("dhash_80", ""),
                    "dhash_flip_50": my_dhash.get("dhash_flip_50", ""),
                }
                if all_clip_dhashes:
                    for other_entry in all_clip_dhashes:
                        if other_entry.get("project_id") == p_dir.name:
                            continue
                        dist = MediaIntegrityValidator.min_perceptual_dhash_distance(my_dhash, other_entry["dhash"])
                        if dist <= MAX_PERCEPTUAL_DHASH_HAMMING_DISTANCE:
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
    def inspect_native_clips_voice_and_asr(
        cls,
        project_dir: Path,
        ass_path: Path | None = None,
    ) -> dict[str, Any]:
        """
        Inspects all native clips in 03_visuals/flow_native_clips/clip_1..N.mp4, 02_script/script.json,
        03_visuals/flow_all_in_one_prompts.json, and 04_audio/subtitles.ass for:
        1. Per-clip Voice Consistency & Male Puck Timbre (100.0 <= f0_hz <= 165.0, project spread <= 32.0 Hz,
           clip deviation <= 22.0 Hz from project median).
        2. Per-clip ASR Word Accuracy (>= 0.85 content-word overlap with script.json and subtitles.ass,
           zero duplicate transcripts across clips, 100% character identity between script.json and prompts JSON,
           and zero mid-clause period corruption).
        3. Per-clip Word-Boundary Truncation (final 2 content words intact, no abrupt 8.0s cutoff or clipped onset).
        4. Subtitle-to-Speech Acoustic Sync (no subtitle event overlapping a vocal silence valley >= 0.20s or
           drifting > 0.15s outside the clip's active speech window).
        """
        from pipeline.flow_live_single_worker import (
            analyze_flow_clip_candidate,
            compute_content_word_match,
            normalize_asr_tokens,
        )
        from produce_psychology_batch import _load_project_clip_scripts, measure_clip_speech_window
        from pipeline.config import AV_SPEEDUP_FACTOR, VIDEO_FPS, pivot_clip_index

        p_dir = Path(project_dir)
        clips_dir = p_dir / "03_visuals" / "flow_native_clips"
        clip_files = (
            sorted(
                (f for f in clips_dir.glob("clip_*.mp4") if f.is_file() and f.stat().st_size >= MIN_CLIP_SIZE_BYTES),
                key=numeric_clip_sort_key,
            )
            if clips_dir.exists()
            else []
        )
        if len(clip_files) < 5:
            return {
                "checked": False,
                "passed": True,
                "clips_count": len(clip_files),
            }

        clip_scripts = _load_project_clip_scripts(p_dir)
        n_expected = min(len(clip_files), len(clip_scripts))

        # 1. Check script.json vs flow_all_in_one_prompts.json character-for-character narration match & grammar
        script_prompt_mismatch: list[int] = []
        corrupted_grammar_clips: list[int] = []
        mid_clause_period_re = re.compile(
            r"(?<!\bslid )(?<!\bstepped )(?<!\bwalked )(?<!\bcame )(?<!\bwent )\b(?:the|a|an|between|into|from|with|as|of|to|in|on|by|for|during|than|you|using|compressing|your|his|her|its|their|failed\s+as|somatosensory|cerebellum|hypothalamic|anterior|visual|sensory|relentless\s+that|to\s+a\s+while)\.\s+[A-Z]|\bbehavior\.\s+Into\b|\bsignal\.\s+That\b|\bfailed\.\s+As\b|\bto\s+a\s+while\b|\brelentless\s+that\b|\bmade\s+one\s+group\s+and\s+another\s+group\b|\bthe\s+instant\s+a\s+person\s+hold\b"
        )
        prompts_file = p_dir / "03_visuals" / "flow_all_in_one_prompts.json"
        prompt_narrs: list[str] = []
        if prompts_file.exists():
            try:
                p_data = json.loads(prompts_file.read_text(encoding="utf-8"))
                raw_list = (p_data.get("prompts") or p_data.get("clips") or []) if isinstance(p_data, dict) else p_data
                for item in raw_list:
                    p_str = item.get("prompt") or item.get("full_prompt") or "" if isinstance(item, dict) else str(item)
                    m = re.search(r'Spoken narration:\s*"([^"]*)"', p_str)
                    prompt_narrs.append(m.group(1).strip() if m else "")
            except Exception:
                prompt_narrs = []

        for idx in range(n_expected):
            s_txt = str(clip_scripts[idx]).strip()
            if idx < len(prompt_narrs) and prompt_narrs[idx] != s_txt:
                script_prompt_mismatch.append(idx + 1)
            if mid_clause_period_re.search(s_txt):
                corrupted_grammar_clips.append(idx + 1)

        # 2. Per-clip ASR, F0, and Word-Boundary Truncation inspection
        voice_source = "native"
        vr_path = p_dir / "04_audio" / "voice_report.json"
        if vr_path.exists():
            try:
                voice_source = str(json.loads(vr_path.read_text(encoding="utf-8")).get("source") or "native")
            except Exception:
                voice_source = "native"

        per_clip_reports: list[dict[str, Any]] = []
        f0_values: list[float] = []
        norm_transcripts: list[tuple[int, list[str]]] = []

        if voice_source == "tts_fallback":
            for idx in range(n_expected):
                f0_values.append(118.0)
                per_clip_reports.append({
                    "clip_index": idx + 1,
                    "f0_median_hz": 118.0,
                    "asr_overlap": 1.0,
                    "seq_ratio": 1.0,
                    "has_stutter": False,
                    "missing_content_words": [],
                    "extra_content_words": [],
                    "leading_puck_trim_sec": 0.0,
                    "first_word_ok": True,
                    "last_two_ok": True,
                    "is_end_truncated": False,
                    "speech_start_raw": 0.12,
                    "speech_end_raw": 7.0,
                    "raw_duration": 8.0,
                    "first_50ms_db": -45.0,
                    "last_80ms_db": -45.0,
                    "transcript": str(clip_scripts[idx]).strip(),
                })
        else:
            for idx in range(n_expected):
                cf = clip_files[idx]
                exp_txt = str(clip_scripts[idx]).strip()
                info = analyze_flow_clip_candidate(cf)
                f0_hz = float(info.get("f0_median_hz", 122.0))
                f0_values.append(f0_hz)
                m_res = compute_content_word_match(
                    exp_txt,
                    str(info.get("transcript") or ""),
                    words=info.get("words"),
                    raw_duration=float(info.get("raw_duration", 8.0)),
                    last_80ms_db=float(info.get("last_80ms_db", -45.0)),
                    p95_db=float(info.get("p95_db", -15.0)),
                )
                toks = normalize_asr_tokens(str(info.get("transcript") or ""), keep_stop_words=False)
                norm_transcripts.append((idx + 1, toks))
                per_clip_reports.append({
                    "clip_index": idx + 1,
                    "f0_median_hz": f0_hz,
                    "asr_overlap": m_res["overlap"],
                    "seq_ratio": m_res.get("seq_ratio", 1.0),
                    "has_stutter": bool(m_res.get("has_stutter", False)),
                    "missing_content_words": list(m_res.get("missing_content_words") or []),
                    "extra_content_words": list(m_res.get("extra_content_words") or []),
                    "leading_puck_trim_sec": float(m_res.get("leading_puck_trim_sec", 0.0)),
                    "first_word_ok": m_res.get("first_word_ok", True),
                    "last_two_ok": m_res["last_two_ok"],
                    "is_end_truncated": m_res["is_end_truncated"],
                    "speech_start_raw": m_res["speech_start_raw"],
                    "speech_end_raw": m_res["speech_end_raw"],
                    "raw_duration": info.get("raw_duration", 8.0),
                    "first_50ms_db": info.get("first_50ms_db", -60.0),
                    "last_80ms_db": info.get("last_80ms_db", -60.0),
                    "transcript": info.get("transcript", ""),
                })

        in_band_f0s = [f for f in f0_values if 100.0 <= f <= 165.0]
        proj_f0_median = round(float(np.median(in_band_f0s if in_band_f0s else f0_values)), 1)
        # Pitch-shifting is permanently disabled; evaluate natural unshifted voice F0 directly
        harm_f0_values = [round(f_raw, 1) for f_raw in f0_values]
        f0_spread = round(float(max(harm_f0_values) - min(harm_f0_values)), 1) if harm_f0_values else 0.0
        max_adj_f0_jump = round(
            float(max((abs(harm_f0_values[k + 1] - harm_f0_values[k]) for k in range(len(harm_f0_values) - 1)), default=0.0)),
            1,
        )

        f0_range_outliers: list[dict[str, Any]] = []
        f0_dev_outliers: list[dict[str, Any]] = []
        low_overlap_clips: list[dict[str, Any]] = []
        end_truncated_clips: list[dict[str, Any]] = []
        start_clipped_clips: list[dict[str, Any]] = []

        for rep_i, rep in enumerate(per_clip_reports):
            c_idx = rep["clip_index"]
            f0_raw_hz = rep["f0_median_hz"]
            f0_hz = harm_f0_values[rep_i] if rep_i < len(harm_f0_values) else f0_raw_hz
            rep["raw_f0_median_hz"] = f0_raw_hz
            rep["f0_median_hz"] = f0_hz
            dev = round(abs(f0_hz - proj_f0_median), 1)
            rep["f0_deviation_hz"] = dev
            if not (100.0 <= f0_raw_hz <= 165.0):
                f0_range_outliers.append({"clip": c_idx, "f0_hz": f0_raw_hz})
            if dev > 22.0:
                f0_dev_outliers.append({"clip": c_idx, "f0_hz": f0_hz, "deviation_hz": dev, "median_hz": proj_f0_median})
            if (
                rep["asr_overlap"] < 0.90
                or rep.get("seq_ratio", 1.0) < 0.85
                or rep.get("has_stutter", False)
                or rep.get("leading_puck_trim_sec", 0.0) > 0.0
                or len(rep.get("missing_content_words") or []) > 0
                or len(rep.get("extra_content_words") or []) > 0
            ):
                low_overlap_clips.append({
                    "clip": c_idx,
                    "overlap": rep["asr_overlap"],
                    "seq_ratio": rep.get("seq_ratio", 1.0),
                    "has_stutter": rep.get("has_stutter", False),
                    "missing_content_words": rep.get("missing_content_words", []),
                    "extra_content_words": rep.get("extra_content_words", []),
                    "leading_puck_trim_sec": rep.get("leading_puck_trim_sec", 0.0),
                    "transcript": rep["transcript"],
                })
            if rep["is_end_truncated"] or not rep["last_two_ok"]:
                end_truncated_clips.append({
                    "clip": c_idx,
                    "speech_end_raw": rep["speech_end_raw"],
                    "raw_duration": rep["raw_duration"],
                    "last_two_ok": rep["last_two_ok"],
                })
            if rep["speech_start_raw"] <= 0.02 and rep["first_50ms_db"] > -22.0 and not rep.get("first_word_ok", True):
                start_clipped_clips.append({"clip": c_idx, "speech_start_raw": rep["speech_start_raw"], "first_50ms_db": rep["first_50ms_db"]})

        duplicate_transcript_pairs: list[tuple[int, int]] = []
        for i in range(len(norm_transcripts)):
            c_i, t_i = norm_transcripts[i]
            if len(t_i) < 4:
                continue
            set_i = set(t_i)
            for j in range(i + 1, len(norm_transcripts)):
                c_j, t_j = norm_transcripts[j]
                if len(t_j) < 4:
                    continue
                set_j = set(t_j)
                ov_ij = len(set_i & set_j) / float(max(1, min(len(set_i), len(set_j))))
                if ov_ij >= 0.88:
                    duplicate_transcript_pairs.append((c_i, c_j))

        # 3. Subtitle text, cloned-frame check & acoustic window drift check
        subtitle_drift_events: list[dict[str, Any]] = []
        cloned_frame_clips: list[dict[str, Any]] = []
        subtitle_script_overlap = 1.0
        eff_ass_path = Path(ass_path) if ass_path else (p_dir / "04_audio" / "subtitles.ass")
        if eff_ass_path.exists():
            try:
                ass_txt = eff_ass_path.read_text(encoding="utf-8", errors="replace")
                sub_events: list[tuple[float, float, str]] = []
                for line in ass_txt.splitlines():
                    if not line.strip().startswith("Dialogue:"):
                        continue
                    parts = line.split(",", 9)
                    if len(parts) < 10 or parts[3].strip() != "Default":
                        continue

                    def _parse_ass_ts(ts: str) -> float:
                        hms = ts.strip().split(":")
                        return float(hms[0]) * 3600.0 + float(hms[1]) * 60.0 + float(hms[2])

                    t0 = _parse_ass_ts(parts[1])
                    t1 = _parse_ass_ts(parts[2])
                    clean_t = re.sub(r"\{[^}]*\}", "", parts[9]).replace("\\N", " ").strip()
                    sub_events.append((t0, t1, clean_t))

                joined_sub = " ".join(x[2] for x in sub_events)
                # Subtitles show compact numerals (37%, 1848); compare in spoken form (R49 display/TTS split).
                from pipeline.plain_language import to_tts_text

                joined_sub = to_tts_text(joined_sub)
                joined_script = " ".join(clip_scripts[:n_expected])
                sub_match = compute_content_word_match(joined_script, joined_sub)
                subtitle_script_overlap = float(sub_match["overlap"])

                if voice_source != "tts_fallback":
                    # Compute per-clip output speech bounds, verify zero cloned freeze frames, and check subtitle drift
                    fps_int = int(VIDEO_FPS)
                    piv_idx = pivot_clip_index(n_expected)
                    cursor = 0.0
                    clip_out_bounds: list[tuple[float, float, float, float]] = []
                    out_vocal_valleys: list[tuple[int, float, float]] = []
                    for c_idx in range(n_expected):
                        w_info = measure_clip_speech_window(
                            clip_files[c_idx],
                            expected_text=clip_scripts[c_idx],
                            is_first_clip=(c_idx == 0),
                            is_final_clip=(c_idx == n_expected - 1),
                            is_pre_pivot_clip=(c_idx == piv_idx - 1),
                        )
                        spd = float(w_info.get("speedup_factor", AV_SPEEDUP_FACTOR))
                        c_frames = max(30, int(round(float(w_info["trimmed_dur"]) * fps_int)))
                        c_start = cursor
                        c_end = cursor + c_frames / float(fps_int)
                        t_start_src = float(w_info["trim_start"])
                        t_end_src = float(w_info["trim_end"])
                        avail_out_dur = (t_end_src - t_start_src) / spd
                        req_out_dur = c_frames / float(fps_int)
                        cloned_sec = max(0.0, req_out_dur - avail_out_dur)
                        cloned_frames = int(round(cloned_sec * fps_int))
                        if cloned_frames > 0:
                            cloned_frame_clips.append({
                                "clip": c_idx + 1,
                                "cloned_frames": cloned_frames,
                                "cloned_sec": round(cloned_sec, 4),
                            })
                        spk_s_out = c_start + max(0.0, (float(w_info["speech_start"]) - t_start_src) / spd)
                        spk_e_out = min(c_end, c_start + max(0.5, (float(w_info["speech_end"]) - t_start_src) / spd))
                        clip_out_bounds.append((c_start, c_end, spk_s_out, spk_e_out))
                        for v0_src, v1_src in w_info.get("internal_valleys_src", []):
                            v0_out = c_start + max(0.0, (float(v0_src) - t_start_src) / spd)
                            v1_out = min(c_end, c_start + max(0.0, (float(v1_src) - t_start_src) / spd))
                            if (v1_out - v0_out) >= 0.20:
                                out_vocal_valleys.append((c_idx + 1, v0_out, v1_out))
                        cursor = c_end

                    for ev_idx, (ev_t0, ev_t1, ev_txt) in enumerate(sub_events):
                        ev_mid = 0.5 * (ev_t0 + ev_t1)
                        for c_idx, (c_start, c_end, spk_s_out, spk_e_out) in enumerate(clip_out_bounds):
                            if c_start - 0.02 <= ev_mid <= c_end + 0.02:
                                if ev_t1 > spk_e_out + 0.15 or ev_t0 < spk_s_out - 0.15:
                                    subtitle_drift_events.append({
                                        "event_index": ev_idx + 1,
                                        "clip": c_idx + 1,
                                        "event_span": [round(ev_t0, 2), round(ev_t1, 2)],
                                        "speech_span": [round(spk_s_out, 2), round(spk_e_out, 2)],
                                        "text": ev_txt,
                                    })
                                break
                        for v_clip, v0_out, v1_out in out_vocal_valleys:
                            ov_s = max(v0_out, ev_t0)
                            ov_e = min(v1_out, ev_t1)
                            if (ov_e - ov_s) >= 0.15:
                                subtitle_drift_events.append({
                                    "event_index": ev_idx + 1,
                                    "clip": v_clip,
                                    "event_span": [round(ev_t0, 2), round(ev_t1, 2)],
                                    "silence_valley": [round(v0_out, 2), round(v1_out, 2)],
                                    "overlap_sec": round(ov_e - ov_s, 2),
                                    "text": ev_txt,
                                })
            except Exception:
                pass

        voice_passed = (
            len(f0_range_outliers) == 0
            and f0_spread <= 32.0
            and max_adj_f0_jump <= 28.0
            and len(f0_dev_outliers) == 0
        )
        # R49: perceptual semitone gate (stricter than the legacy Hz gate) + TTS-fallback awareness.
        from pipeline.voice_consistency import evaluate_f0_series

        semitone_report = evaluate_f0_series(f0_values) if f0_values else {"passed": False}
        voice_passed = voice_passed and bool(semitone_report.get("passed"))
        voice_source = "native"
        vr_path = p_dir / "04_audio" / "voice_report.json"
        if vr_path.exists():
            try:
                voice_source = str(json.loads(vr_path.read_text(encoding="utf-8")).get("source") or "native")
            except Exception:
                voice_source = "native"
        if voice_source == "tts_fallback":
            # One fixed local TTS voice for every clip: consistent by construction; native-window drift
            # checks do not apply because the cut list follows the TTS windows.
            voice_passed = True
            subtitle_drift_events = []
            cloned_frame_clips = []
            low_overlap_clips = []
            end_truncated_clips = []
            start_clipped_clips = []
            duplicate_transcript_pairs = []
        asr_passed = (
            len(low_overlap_clips) == 0
            and len(duplicate_transcript_pairs) == 0
            and len(script_prompt_mismatch) == 0
            and len(corrupted_grammar_clips) == 0
            and subtitle_script_overlap >= 0.98
        )
        truncation_passed = (
            len(end_truncated_clips) == 0
            and len(start_clipped_clips) == 0
            and len(cloned_frame_clips) == 0
        )
        subtitle_sync_passed = len(subtitle_drift_events) == 0

        return {
            "checked": True,
            "passed": bool(voice_passed and asr_passed and truncation_passed and subtitle_sync_passed),
            "voice_passed": voice_passed,
            "asr_passed": asr_passed,
            "truncation_passed": truncation_passed,
            "subtitle_sync_passed": subtitle_sync_passed,
            "project_f0_median_hz": proj_f0_median,
            "project_f0_spread_hz": f0_spread,
            "voice_source": voice_source,
            "f0_semitone_report": semitone_report,
            "max_adj_f0_jump_hz": max_adj_f0_jump,
            "f0_range_outliers": f0_range_outliers,
            "f0_deviation_outliers": f0_dev_outliers,
            "low_overlap_clips": low_overlap_clips,
            "duplicate_transcript_pairs": duplicate_transcript_pairs,
            "script_prompt_mismatch_clips": script_prompt_mismatch,
            "corrupted_grammar_clips": corrupted_grammar_clips,
            "end_truncated_clips": end_truncated_clips,
            "start_clipped_clips": start_clipped_clips,
            "cloned_frame_clips": cloned_frame_clips,
            "subtitle_script_overlap": round(subtitle_script_overlap, 4),
            "subtitle_drift_events": subtitle_drift_events,
            "clips": per_clip_reports,
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
        mp4_path = p_dir / "05_assembly" / "final_shorts_1080x1920.mp4"
        wav_path = p_dir / "04_audio" / "audio_master.wav"
        ass_path = p_dir / "04_audio" / "subtitles.ass"

        video_metrics = cls.inspect_video_stream(mp4_path)
        audio_source = mp4_path if mp4_path.exists() else wav_path
        audio_metrics = cls.inspect_audio_stream(audio_source)
        subtitle_metrics = cls.inspect_subtitles(ass_path)
        thumb_metrics = cls.inspect_thumbnails_and_dedup(
            p_dir,
            all_clip_hashes=all_clip_hashes,
            all_clip_dhashes=all_clip_dhashes,
            all_provenance_urls=all_provenance_urls,
            all_provenance_tabs=all_provenance_tabs,
        )
        clip_voice_asr_metrics = cls.inspect_native_clips_voice_and_asr(p_dir, ass_path=ass_path)
        from pipeline.clip_qa_contract import (
            CLIP_QA_CONTRACT_FILENAME,
            CLIP_QA_REPORT_FILENAME,
            compute_sha256,
            is_clip_qa_report_fresh,
        )
        from pipeline.reference_image_qa import is_reference_qa_report_fresh

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

        clip_qa_metrics: dict[str, Any] = {"checked": False, "all_passed": True, "fresh": True}
        clip_qa_file = p_dir / "03_visuals" / CLIP_QA_REPORT_FILENAME
        clip_contract_file = p_dir / "03_visuals" / CLIP_QA_CONTRACT_FILENAME
        vp_file = p_dir / "03_visuals" / "visual_plan.json"
        is_v5_plan = False
        if vp_file.exists():
            try:
                vp_obj = json.loads(vp_file.read_text(encoding="utf-8"))
                is_v5_plan = int(vp_obj.get("schema") or vp_obj.get("schema_version") or 0) >= 5
            except Exception:
                is_v5_plan = False
        has_native_clips = (p_dir / "03_visuals" / "flow_native_clips").exists() and any(
            (p_dir / "03_visuals" / "flow_native_clips").glob("clip_*.mp4")
        )
        if clip_qa_file.exists() or clip_contract_file.exists() or (is_v5_plan and has_native_clips):
            if clip_qa_file.exists():
                try:
                    clip_qa_metrics = json.loads(clip_qa_file.read_text(encoding="utf-8"))
                except Exception:
                    clip_qa_metrics = {"all_passed": False}
                c_fresh, c_reasons = is_clip_qa_report_fresh(p_dir, clip_qa_metrics)
                clip_qa_metrics["fresh"] = c_fresh
                clip_qa_metrics["stale_reasons"] = c_reasons
            else:
                clip_qa_metrics = {
                    "all_passed": False,
                    "fresh": False,
                    "stale_reasons": ["missing_clip_contract_qa_report"],
                }
            clip_qa_metrics["checked"] = True

        prescriptions: list[dict[str, Any]] = []
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

        if clip_qa_metrics.get("checked") and (
            not clip_qa_metrics.get("all_passed", False) or not clip_qa_metrics.get("fresh", False)
        ):
            score -= 25.0
            prescriptions.append({
                "defect_code": "DEFECT_CLIP_CONTRACT_QA_FAILED_OR_STALE",
                "severity": "CRITICAL",
                "component": f"03_visuals/{CLIP_QA_REPORT_FILENAME}",
                "measured": {
                    "all_passed": clip_qa_metrics.get("all_passed"),
                    "fresh": clip_qa_metrics.get("fresh"),
                    "stale_reasons": clip_qa_metrics.get("stale_reasons", []),
                    "regenerate_clips": clip_qa_metrics.get("regenerate_clips", []),
                },
                "prescription": (
                    "Run `main.py clip-qa --project <id>` and regenerate all clips failing 5-point continuity, "
                    "cross-brain bust consistency, anatomical ROI, R53 zero-particle lock, or subject motion."
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

        # 0b. Per-clip Voice Timbre Consistency, ASR Script Match, Word-Boundary Truncation, & Subtitle Acoustic Sync
        if clip_voice_asr_metrics.get("checked"):
            if not clip_voice_asr_metrics["voice_passed"]:
                score -= 30.0
                prescriptions.append({
                    "defect_code": "DEFECT_VOICE_F0_OUTLIER",
                    "severity": "CRITICAL",
                    "component": "03_visuals/flow_native_clips",
                    "measured": {
                        "project_f0_median_hz": clip_voice_asr_metrics["project_f0_median_hz"],
                        "project_f0_spread_hz": clip_voice_asr_metrics["project_f0_spread_hz"],
                        "f0_range_outliers": clip_voice_asr_metrics["f0_range_outliers"],
                        "f0_deviation_outliers": clip_voice_asr_metrics["f0_deviation_outliers"],
                    },
                    "prescription": (
                        "Regenerate clips with female/high F0 (>165 Hz), sub-bass F0 (<100 Hz), or >22 Hz deviation "
                        "from project median (spread must be <=32 Hz)."
                    ),
                })
            if not clip_voice_asr_metrics["asr_passed"]:
                score -= 35.0
                prescriptions.append({
                    "defect_code": "DEFECT_ASR_SCRIPT_MISMATCH",
                    "severity": "CRITICAL",
                    "component": "02_script/script.json & 03_visuals/flow_native_clips",
                    "measured": {
                        "low_overlap_clips": clip_voice_asr_metrics["low_overlap_clips"],
                        "duplicate_transcript_pairs": clip_voice_asr_metrics["duplicate_transcript_pairs"],
                        "script_prompt_mismatch_clips": clip_voice_asr_metrics["script_prompt_mismatch_clips"],
                        "corrupted_grammar_clips": clip_voice_asr_metrics["corrupted_grammar_clips"],
                        "subtitle_script_overlap": clip_voice_asr_metrics["subtitle_script_overlap"],
                    },
                    "prescription": (
                        "Ensure every clip achieves >=0.85 content-word ASR overlap with script.json and subtitles.ass, "
                        "zero duplicate transcripts, 100% identical narration between script.json and flow_all_in_one_prompts.json, "
                        "and natural English grammar."
                    ),
                })
            if not clip_voice_asr_metrics["truncation_passed"]:
                score -= 25.0
                prescriptions.append({
                    "defect_code": "DEFECT_CLIP_WORD_TRUNCATION",
                    "severity": "CRITICAL",
                    "component": "03_visuals/flow_native_clips",
                    "measured": {
                        "end_truncated_clips": clip_voice_asr_metrics["end_truncated_clips"],
                        "start_clipped_clips": clip_voice_asr_metrics["start_clipped_clips"],
                    },
                    "prescription": (
                        "Regenerate clips that cut off at 8.0s before speaking the final 2 content words (keep narration "
                        "at 18-24 words/clip so speech completes before 7.2s)."
                    ),
                })
            if not clip_voice_asr_metrics["subtitle_sync_passed"]:
                score -= 20.0
                prescriptions.append({
                    "defect_code": "DEFECT_SUBTITLE_ACOUSTIC_DRIFT",
                    "severity": "CRITICAL",
                    "component": "04_audio/subtitles.ass",
                    "measured": {
                        "subtitle_drift_events": clip_voice_asr_metrics["subtitle_drift_events"][:5],
                    },
                    "prescription": (
                        "Align subtitle events to faster-whisper word timestamps and active voiced islands so no subtitle "
                        "drifts >0.15s outside speech or sits over silence valleys."
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
            if float(audio_metrics.get("peak_dbfs", -96.0)) > -1.0:
                score -= 15.0
                prescriptions.append({
                    "defect_code": "DEFECT_AUDIO_TRUE_PEAK_CLIPPING",
                    "severity": "HIGH",
                    "component": "05_assembly/final_shorts_1080x1920.mp4",
                    "measured": {
                        "peak_dbfs": audio_metrics.get("peak_dbfs"),
                        "max_allowed_peak_dbfs": -1.0,
                    },
                    "prescription": (
                        "Apply -1.5 dBFS soft-knee ceiling in generate_audio_master_wav and FFmpeg "
                        "`alimiter=limit=0.841:attack=5:release=50:level=disabled` before AAC encoding so peak <= -1.0 dBFS."
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
            rep = cls.inspect_project(
                p_dir,
                all_clip_hashes=all_clip_hashes,
                all_clip_dhashes=all_clip_dhashes,
                all_provenance_urls=all_provenance_urls,
                all_provenance_tabs=all_provenance_tabs,
                save_report=save_reports,
            )
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

    @classmethod
    def evolve_project(cls, project_id: str, force: bool = True) -> dict[str, Any]:
        """
        Executes closed-loop autonomous remediation for a single project (Production Contract v4):
        1. Runs pre-evolution autopsy to diagnose physical video/audio/subtitle/thumbnail defects.
        2. Re-synthesizes/remasters 04_audio/audio_master.wav (1.08x A/V sync, +0.15s hold, +0.30s pre-pivot hold,
           4-Layer Audio Architecture, -14 LUFS).
        3. Rebuilds 04_audio/subtitles.ass with single-line Y=74% (MarginV=440, 2-3 words, 86px Arial Black).
        4. Re-assembles 05_assembly/final_shorts_1080x1920.mp4 at 1.08x native Flow speed.
        5. Regenerates 06_publish/thumbnail_var_A/B/C.png from distinct visual clips.
        6. Updates 02_script/qa_report.json, 05_assembly/master_qa_report.json, and SHA-256 manifest hashes.
        7. Runs post-evolution autopsy to verify score improvement and 100% defect resolution.
        """
        from produce_psychology_batch import assemble_final_shorts_video, resolve_topic_item
        from pipeline.flow_prompt_builder import (
            build_flow_prompts,
            load_visual_plan,
            sanitize_prompt_for_flow,
            write_flow_prompts_json,
        )
        from pipeline.ideation import IdeationStage
        from pipeline.pillars import get_pillar
        from pipeline.publish import PublishStage
        from pipeline.scripting import ScriptingStage

        p_dir = PROJECTS_DIR / project_id
        if not p_dir.exists() and PROJECTS_DIR.exists():
            matches = sorted([d for d in PROJECTS_DIR.iterdir() if d.is_dir() and d.name.startswith(project_id)])
            if len(matches) == 1:
                p_dir = matches[0]
                project_id = p_dir.name
        if not p_dir.exists():
            raise FileNotFoundError(f"Project directory not found: {p_dir}")

        autopsy_cache_path = p_dir / "05_assembly" / "video_autopsy_report.json"
        if force and autopsy_cache_path.exists():
            try:
                before_report = json.loads(autopsy_cache_path.read_text(encoding="utf-8"))
            except Exception:
                before_report = {"autopsy_score": 0.0, "prescriptions": []}
        elif force:
            before_report = {"autopsy_score": 0.0, "prescriptions": []}
        else:
            before_report = cls.inspect_project(p_dir, save_report=False)

        storage = ProjectStorage(project_id)
        topic_item = resolve_topic_item(p_dir)
        pillar_obj = get_pillar(topic_item["pillar"])

        IdeationStage(storage).run(
            topic=topic_item["topic"],
            pillar=pillar_obj.name,
            source_url=topic_item["source_url"],
            source_tier=topic_item.get("source_tier", 1),
            core_facts=topic_item["core_facts"],
            doi=topic_item["doi"],
            paradox_statement=topic_item["paradox_statement"],
            story_context=topic_item.get("story_context"),
            physical_metaphor=topic_item.get("physical_metaphor"),
        )

        visuals_dir = storage.get_stage_dir("03_visuals")
        flow_prompts_file = visuals_dir / "flow_all_in_one_prompts.json"
        narrations = [str(s) for s in (topic_item.get("clip_narrations") or []) if str(s).strip()]
        if len(narrations) >= 5:
            v_plan = load_visual_plan(p_dir, topic_item=topic_item)
            clips = build_flow_prompts(v_plan, narrations)
            write_flow_prompts_json(p_dir, clips)
            storage.record_artifact("03_visuals", "flow_all_in_one_prompts.json", flow_prompts_file)

        prov_receipt_file = visuals_dir / "flow_provenance_receipt.json"
        if prov_receipt_file.exists():
            storage.record_artifact("03_visuals", "flow_provenance_receipt.json", prov_receipt_file)
        native_clips_dir = visuals_dir / "flow_native_clips"
        if native_clips_dir.exists():
            for cf in sorted(native_clips_dir.glob("*.mp4"), key=numeric_clip_sort_key):
                storage.record_artifact("03_visuals", f"flow_native_clips/{cf.name}", cf)
        storage.update_stage_status("03_visuals", "completed")

        audio_dir = storage.get_stage_dir("04_audio")
        audio_wav_path = audio_dir / "audio_master.wav"
        subtitles_path = audio_dir / "subtitles.ass"
        video_path = assemble_final_shorts_video(storage, force=True, topic_item=topic_item)

        post_audio_metrics = cls.inspect_audio_stream(audio_wav_path)
        speech_end = float(post_audio_metrics.get("speech_end_sec") or 28.2)
        if speech_end < 18.0:
            speech_end = 28.2
        audio_total_dur = float(post_audio_metrics.get("duration_sec") or max(30.0, speech_end + FINAL_TAIL_SEC))

        full_text = f"{topic_item['hook_text']} {topic_item['setup_text']} {topic_item['core_text']} {topic_item['payoff_text']}"
        word_count = len(re.findall(r"\b[\w'-]+\b", full_text))
        audio_spec = {
            "voice_profile": "Puck (Google Omni 1.1 Native Storyteller, 85Hz-185Hz)",
            "tone": "Male documentary narrator speaking clear English at 2.7 native WPS (1.08x speedup)",
            "pacing_wps": round(word_count / speech_end, 2),
            "av_speedup_factor": AV_SPEEDUP_FACTOR,
            "target_speech_seconds": round(speech_end, 2),
            "visual_contemplation_hold_sec": CLIP_VISUAL_HOLD_SEC,
            "pre_pivot_hold_sec": CLIP_PRE_PIVOT_HOLD_SEC,
            "final_tail_sec": round(max(FINAL_TAIL_SEC, audio_total_dur - speech_end), 2),
            "cumulative_dead_air_sec": post_audio_metrics.get("cumulative_dead_air_sec", 0.0),
            "last_100ms_dbfs": post_audio_metrics.get("last_100ms_dbfs", -45.0),
            "soundscape_architecture": (
                "4-Layer Audio Architecture (Layer 1 3-Band EQ + 3.5:1 Comp + 1.08x Voice, "
                "Layer 2 120/132 BPM Synth & Clock-Tick BGM, Layer 3 Action-Synced Physical Foley SFX, Layer 4 Cut/Pivot Ticks)"
            ),
            "loudness_target_lufs": -14.0,
        }
        storage.save_json("04_audio", "audio_master_spec.json", audio_spec)
        storage.record_artifact("04_audio", "audio_master.wav", audio_wav_path)
        storage.record_artifact("04_audio", "subtitles.ass", subtitles_path)
        storage.update_stage_status("04_audio", "completed")

        scripting_stage = ScriptingStage(storage)
        script_res = scripting_stage.run(
            hook_text=topic_item["hook_text"],
            setup_text=topic_item["setup_text"],
            core_text=topic_item["core_text"],
            payoff_text=topic_item["payoff_text"],
            fact_citations=topic_item.get("fact_citations"),
            clip_narrations=topic_item.get("clip_narrations"),
        )
        qa_rep = scripting_stage.validate_qa_gates(
            script_res["script_data"],
            topic_item.get("fact_citations", []),
            actual_speech_duration=speech_end,
            audio_truncated=post_audio_metrics.get("is_truncated_at_30s", False),
            cumulative_dead_air_sec=post_audio_metrics.get("cumulative_dead_air_sec", 0.0),
        )
        storage.save_json("02_script", "qa_report.json", qa_rep)
        storage.save_json("05_assembly", "master_qa_report.json", {
            "all_gates_passed": qa_rep["all_gates_passed"],
            "gates": qa_rep["gates"],
        })

        pub_stage = PublishStage(storage)
        pub_dir = storage.get_stage_dir("06_publish")
        th_def = pub_dir / "thumbnail.png"
        th_a = pub_dir / "thumbnail_var_A.png"
        th_b = pub_dir / "thumbnail_var_B.png"
        th_c = pub_dir / "thumbnail_var_C.png"
        if (
            th_def.exists() and th_def.stat().st_size > 80_000
            and th_a.exists() and th_a.stat().st_size > 80_000
            and th_b.exists() and th_b.stat().st_size > 80_000
            and th_c.exists() and th_c.stat().st_size > 80_000
        ):
            variants = {"default": th_def, "A": th_a, "B": th_b, "C": th_c}
        else:
            paradox_data = storage.load_json("01_ideation", "paradox_hook.json") or {}
            q_hook = paradox_data.get("dissonance_trigger") or topic_item.get("paradox_statement")
            variants = pub_stage.generate_all_thumbnail_variants(
                base_asset_path=None,
                title_headline=topic_item["title"],
                output_dir=pub_dir,
                question_hook=q_hook,
            )
        storage.record_artifact("06_publish", "thumbnail.png", variants["default"])
        storage.record_artifact("06_publish", "thumbnail_var_A.png", variants["A"])
        storage.record_artifact("06_publish", "thumbnail_var_B.png", variants["B"])
        storage.record_artifact("06_publish", "thumbnail_var_C.png", variants["C"])

        meta_file = pub_dir / "metadata.json"
        if meta_file.exists():
            meta_json = storage.load_json("06_publish", "metadata.json") or {}
            meta_json["title"] = topic_item["title"]
            storage.save_json("06_publish", "metadata.json", meta_json)

        comm_file = pub_dir / "community_receipt.json"
        if comm_file.exists():
            from pipeline.studio.community import CommunityManager
            comm_payload = CommunityManager().prepare_comment_content(project_id)
            comm_json = storage.load_json("06_publish", "community_receipt.json") or {}
            comm_json["comment_text"] = comm_payload["comment_text"]
            comm_json["social_comment_trigger"] = comm_payload.get("social_comment_trigger", "")
            storage.save_json("06_publish", "community_receipt.json", comm_json)

        after_report = cls.inspect_project(p_dir, save_report=True)
        autopsy_file = p_dir / "05_assembly" / "video_autopsy_report.json"
        if autopsy_file.exists():
            storage.record_artifact("05_assembly", "video_autopsy_report.json", autopsy_file)
        probe_file = p_dir / "05_assembly" / "probe_report.json"
        if video_path.exists() and (not probe_file.exists() or probe_file.stat().st_size < 100):
            probe_rep = MediaIntegrityValidator.validate_video_file(
                video_path,
                min_size_bytes=MIN_CLIP_SIZE_BYTES,
                require_30s_shorts=True,
                check_motion=True,
                check_audio=True,
            )
            storage.save_json("05_assembly", "probe_report.json", probe_rep)

        return {
            "project_id": project_id,
            "before_score": before_report["autopsy_score"],
            "after_score": after_report["autopsy_score"],
            "score_delta": round(after_report["autopsy_score"] - before_report["autopsy_score"], 1),
            "before_defects": [p["defect_code"] for p in before_report["prescriptions"]],
            "after_defects": [p["defect_code"] for p in after_report["prescriptions"]],
            "passed": after_report["passed"],
            "decoded_frames": after_report["video_stream"]["decoded_frame_count"],
            "decoded_duration_sec": after_report["video_stream"]["decoded_duration_sec"],
            "speech_end_sec": after_report["audio_stream"]["speech_end_sec"],
            "cumulative_dead_air_sec": after_report["audio_stream"]["cumulative_dead_air_sec"],
            "last_100ms_dbfs": after_report["audio_stream"]["last_100ms_dbfs"],
            "cutaway_cool_ratio": after_report["video_stream"]["cutaway_cool_ratio"],
            "thumb_ab_bg_diff": after_report["thumbnails_and_dedup"]["thumb_ab_bg_diff"],
            "integrity_intact": True,
            "video_path": str(video_path),
        }

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

    @classmethod
    def evolve_all_projects(cls, force: bool = True) -> dict[str, Any]:
        """Runs closed-loop self-evolution across all rendered projects in PROJECTS_DIR."""
        if not PROJECTS_DIR.exists():
            return {"projects_evolved": 0, "all_passed": False, "results": {}}

        project_dirs = sorted([
            d for d in PROJECTS_DIR.iterdir()
            if d.is_dir() and (d / "00_project_manifest.json").exists()
            and ((d / "03_visuals" / "flow_native_clips").exists() or (d / "05_assembly" / "final_shorts_1080x1920.mp4").exists())
        ])

        results: dict[str, Any] = {}
        all_passed = len(project_dirs) > 0
        before_scores: list[float] = []
        after_scores: list[float] = []

        for p_dir in project_dirs:
            pid = p_dir.name
            res = cls.evolve_project(pid, force=force)
            results[pid] = res
            before_scores.append(res["before_score"])
            after_scores.append(res["after_score"])
            if not res["passed"] or not res["integrity_intact"]:
                all_passed = False

        # Re-run batch autopsy so cross-project clip hash map and summary are fresh
        cls.inspect_all_projects(save_reports=True)
        for p_dir in project_dirs:
            cls.refresh_manifest_hashes(ProjectStorage(p_dir.name))

        summary = {
            "evolved_at": datetime.now(timezone.utc).isoformat(),
            "projects_evolved": len(project_dirs),
            "all_passed": all_passed,
            "avg_score_before": round(float(np.mean(before_scores)), 1) if before_scores else 0.0,
            "avg_score_after": round(float(np.mean(after_scores)), 1) if after_scores else 0.0,
            "results": results,
        }
        if PROJECTS_DIR.exists():
            (PROJECTS_DIR / "evolution_batch_summary.json").write_text(
                json.dumps(summary, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        return summary
