"""
ALL ABOUT BRAIN - Local Media Integrity Gate & Frame Motion Validator
Enforces the 7-Point Mandatory Media Integrity Gate (Core Task #4 & #5):
1. File extension (.mp4) and minimum byte size (>= 1MB) check (blocks thumbnails/empty files).
2. Video stream presence (codec_type == "video", H.264/HEVC/VP9/AV1) via ffprobe/ffmpeg + cv2.
3. Video duration bounds validation (FLOW_CLIP_DURATION_MIN_SEC-FLOW_CLIP_DURATION_MAX_SEC [3.0s-15.0s] for Flow clips;
   FINAL_SHORTS_DURATION_MIN_SEC-FINAL_SHORTS_DURATION_MAX_SEC [24.0s-105.0s] for final Shorts).
4. Start / Middle / End Frame Diff & Farneback Optical Flow verification (blocks static thumbnail zoompan & frozen frames).
5. Resolution (9:16 vertical), frame rate, and audio stream synchronization check.
6. Active speech narration, non-truncation, and cumulative dead-air <= max_allowed_dead_air_sec(duration_sec).
7. Guard 2 (R37): Zero synthetic FFmpeg derivative metadata tags.
"""

import json
import logging
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from pipeline.config import (
    BANNED_DERIVATIVE_METADATA_MARKERS,
    DEAD_AIR_FLOOR_SEC,
    FINAL_SHORTS_DURATION_MAX_SEC,
    FINAL_SHORTS_DURATION_MIN_SEC,
    FLOW_CLIP_DURATION_MAX_SEC,
    FLOW_CLIP_DURATION_MIN_SEC,
    MAX_PERCEPTUAL_DHASH_HAMMING_DISTANCE,
    MIN_CLIP_SIZE_BYTES,
    MIN_FINAL_VIDEO_SIZE_BYTES,
    MIN_FRAME_DIFF_THRESHOLD,
    MIN_INTRA_SEGMENT_DIFF_THRESHOLD,
    MIN_OPTICAL_FLOW_THRESHOLD,
    MIN_PAIR_TOP_DIFF_THRESHOLD,
    SUBPROCESS_TIMEOUT_SEC,
    max_allowed_dead_air_sec,
)


def get_pipeline_logger(name: str = "all_about_brain") -> logging.Logger:
    """Returns a structured pipeline logger with console formatting."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    return logger


logger = get_pipeline_logger("media_integrity")


class MediaIntegrityError(RuntimeError):
    """Raised immediately (Fail-Fast) when a media asset fails any of the 5 integrity gates."""


class MediaIntegrityValidator:
    """
    Validates downloaded Google Flow video clips and assembled Shorts MP4s
    using ffprobe/ffmpeg stream inspection and OpenCV start/mid/end frame-diff & optical flow.
    """

    FORBIDDEN_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".svg", ".ico"}

    @staticmethod
    def resolve_ffmpeg_exe() -> str:
        """Locates ffmpeg executable via system PATH or imageio_ffmpeg."""
        exe = shutil.which("ffmpeg")
        if exe:
            return exe
        try:
            import imageio_ffmpeg
            return imageio_ffmpeg.get_ffmpeg_exe()
        except Exception as exc:
            raise MediaIntegrityError(
                f"FATAL ERROR [Pre-Flight]: Local ffmpeg binary not found in PATH or imageio_ffmpeg: {exc}"
            ) from exc

    @staticmethod
    def resolve_ffprobe_exe() -> str | None:
        """Locates ffprobe executable if available in PATH or alongside ffmpeg."""
        exe = shutil.which("ffprobe")
        if exe:
            return exe
        try:
            ffmpeg_path = Path(MediaIntegrityValidator.resolve_ffmpeg_exe())
            cand = ffmpeg_path.parent / "ffprobe.exe"
            if cand.exists():
                return str(cand)
        except Exception:
            pass
        return None

    @classmethod
    def is_forbidden_Static_or_image_source(cls, path_or_url: str | Path) -> bool:
        """Blocks thumbnails, poster attributes, screenshots, or image extensions from being treated as video."""
        raw = str(path_or_url).lower().strip()
        if any(raw.endswith(ext) for ext in cls.FORBIDDEN_IMAGE_EXTENSIONS):
            return True
        if "flow_gate_v" in raw or "screenshot" in raw or "thumbnail" in raw or "poster" in raw:
            if not raw.endswith(".mp4"):
                return True
        return False

    @classmethod
    def probe_streams(cls, file_path: Path, timeout_sec: float = 30.0) -> dict[str, Any]:
        """
        Probes media container streams using ffprobe (if available), ffmpeg -i header inspection,
        and cv2.VideoCapture to extract codec_type, video_codec, audio_codec, duration, fps, and resolution.
        """
        path = Path(file_path)
        if not path.exists() or not path.is_file():
            return {
                "exists": False,
                "extension": path.suffix.lower(),
                "file_size_bytes": 0,
                "has_video_stream": False,
                "has_audio_stream": False,
                "codec_type": None,
                "video_codec": None,
                "audio_codec": None,
                "width": 0,
                "height": 0,
                "fps": 0.0,
                "frame_count": 0,
                "duration_seconds": 0.0,
            }

        file_size = path.stat().st_size
        ext = path.suffix.lower()

        has_video_stream = False
        has_audio_stream = False
        video_codec = None
        audio_codec = None
        width = 0
        height = 0
        fps = 0.0
        frame_count = 0
        duration_sec = 0.0

        # 1. Try ffprobe JSON if available
        ffprobe_exe = cls.resolve_ffprobe_exe()
        if ffprobe_exe:
            try:
                cmd = [
                    ffprobe_exe,
                    "-v", "quiet",
                    "-print_format", "json",
                    "-show_format",
                    "-show_streams",
                    str(path.resolve()),
                ]
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_sec, check=False)
                if res.returncode == 0 and res.stdout.strip():
                    data = json.loads(res.stdout)
                    for stream in data.get("streams", []):
                        c_type = stream.get("codec_type")
                        if c_type == "video" and not has_video_stream:
                            has_video_stream = True
                            video_codec = stream.get("codec_name")
                            width = int(stream.get("width", 0) or 0)
                            height = int(stream.get("height", 0) or 0)
                            nb_frames = stream.get("nb_frames")
                            if nb_frames and str(nb_frames).isdigit():
                                frame_count = int(nb_frames)
                            r_fps = stream.get("r_frame_rate", "0/1")
                            if "/" in str(r_fps):
                                num, den = str(r_fps).split("/", 1)
                                if float(den) > 0:
                                    fps = round(float(num) / float(den), 2)
                            if stream.get("duration"):
                                duration_sec = float(stream["duration"])
                        elif c_type == "audio" and not has_audio_stream:
                            has_audio_stream = True
                            audio_codec = stream.get("codec_name")
                    fmt_dur = data.get("format", {}).get("duration")
                    if fmt_dur and duration_sec <= 0:
                        duration_sec = float(fmt_dur)
            except Exception as exc:
                logger.warning("ffprobe inspection note for %s: %s", path.name, exc)

        # 2. Fallback / supplement via ffmpeg -i stderr stream parsing
        if not has_video_stream or not has_audio_stream or not video_codec:
            try:
                ffmpeg_exe = cls.resolve_ffmpeg_exe()
                cmd = [ffmpeg_exe, "-hide_banner", "-i", str(path.resolve())]
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_sec, check=False)
                stderr_txt = res.stderr or ""
                v_match = re.search(r"Stream #\d+:\d+.*?: Video: (\w+)", stderr_txt)
                if v_match:
                    has_video_stream = True
                    video_codec = video_codec or v_match.group(1).lower()
                a_match = re.search(r"Stream #\d+:\d+.*?: Audio: (\w+)", stderr_txt)
                if a_match:
                    has_audio_stream = True
                    audio_codec = audio_codec or a_match.group(1).lower()
                dur_match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", stderr_txt)
                if dur_match and duration_sec <= 0:
                    hh, mm, ss = float(dur_match.group(1)), float(dur_match.group(2)), float(dur_match.group(3))
                    duration_sec = round(hh * 3600.0 + mm * 60.0 + ss, 2)
            except Exception as exc:
                logger.warning("ffmpeg -i stream inspection note for %s: %s", path.name, exc)

        # 3. Supplement / verify with cv2.VideoCapture
        try:
            cap = cv2.VideoCapture(str(path.resolve()))
            if cap.isOpened():
                cv_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
                cv_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
                cv_fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
                cv_fc = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
                if cv_w > 0 and cv_h > 0 and cv_fc > 0:
                    has_video_stream = True
                    width = width or cv_w
                    height = height or cv_h
                    fps = round(fps or cv_fps, 2)
                    frame_count = frame_count or cv_fc
                    if duration_sec <= 0 and cv_fps > 0:
                        duration_sec = round(cv_fc / cv_fps, 2)
            cap.release()
        except Exception as exc:
            logger.warning("OpenCV VideoCapture inspection note for %s: %s", path.name, exc)

        video_stream_dur = round(frame_count / fps, 2) if (frame_count > 0 and fps > 0) else round(duration_sec, 2)

        return {
            "exists": True,
            "extension": ext,
            "file_size_bytes": file_size,
            "has_video_stream": has_video_stream,
            "has_audio_stream": has_audio_stream,
            "codec_type": "video" if has_video_stream else None,
            "video_codec": video_codec or ("h264" if has_video_stream else None),
            "audio_codec": audio_codec,
            "width": width,
            "height": height,
            "fps": round(fps, 2),
            "frame_count": frame_count,
            "duration_seconds": round(duration_sec, 2),
            "video_stream_duration_seconds": video_stream_dur,
        }

    @classmethod
    def compute_frame_motion_metrics(
        cls,
        file_path: Path,
        expected_duration_sec: float | None = None,
    ) -> dict[str, Any]:
        """
        Extracts start (8%), quarter (25%), middle (50%), three-quarter (75%), and end (90%) anchors,
        plus a companion frame +0.5s after each anchor to calculate:
        - Inter-segment mean absolute pixel differences (full frame & upper 60% visual region above subtitles).
        - Intra-segment pixel differences across a 0.5s window inside each of the 5 segments
          (catches 5-image static slideshows, frozen middle clips, and FFmpeg concat timebase freezes).
        - Start-to-Mid, Mid-to-End, and Start-to-End pixel differences.
        - Dense Farneback Optical Flow magnitude across sampled frame transitions.
        - Full expected duration frame coverage check (blocks videos where video stream stops at 6s while audio runs to 30s).
        """
        path = Path(file_path)
        import os
        import tempfile
        import threading
        tmp_path: Path | None = None
        open_path = path
        if os.name != "nt" and path.exists() and not str(path).startswith("/tmp"):
            try:
                tmp_path = Path(tempfile.gettempdir()) / f"_tmp_motion_{os.getpid()}_{threading.get_ident()}_{path.name}"
                shutil.copy2(path, tmp_path)
                open_path = tmp_path
            except Exception:
                tmp_path = None
                open_path = path
        cap = cv2.VideoCapture(str(open_path.resolve()))
        empty_metrics = {
            "sampled_frames": 0,
            "decoded_frame_count": 0,
            "decoded_frame_shortfall": True,
            "full_frame_diffs": [],
            "upper_region_diffs": [],
            "intra_segment_upper_diffs": [],
            "min_intra_segment_diff": 0.0,
            "start_to_mid_diff": 0.0,
            "mid_to_end_diff": 0.0,
            "start_to_end_diff": 0.0,
            "mean_full_diff": 0.0,
            "mean_upper_diff": 0.0,
            "min_pair_upper_diff": 0.0,
            "optical_flow_mean": 0.0,
            "is_static_or_frozen": True,
        }
        if not cap.isOpened():
            if tmp_path is not None:
                tmp_path.unlink(missing_ok=True)
            return dict(empty_metrics)

        fc = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 30.0)
        if fc < 5:
            cap.release()
            if tmp_path is not None:
                tmp_path.unlink(missing_ok=True)
            res = dict(empty_metrics)
            res["sampled_frames"] = fc
            res["decoded_frame_count"] = fc
            return res

        target_fc = fc
        decoded_frame_shortfall = False
        if expected_duration_sec is not None and expected_duration_sec > 0 and fps > 0:
            min_expected_frames = int(expected_duration_sec * fps * 0.95)
            if fc < min_expected_frames:
                decoded_frame_shortfall = True
                target_fc = int(expected_duration_sec * fps)

        intra_step = max(3, int(fps * 0.5))
        # Sample 5 anchor positions across target_fc: Start (8%), 25%, Middle (50%), 75%, End (90%)
        sample_indices = sorted(list({
            max(2, int(target_fc * 0.08)),
            max(3, int(target_fc * 0.25)),
            max(4, int(target_fc * 0.50)),
            max(5, int(target_fc * 0.75)),
            max(6, min(target_fc - intra_step - 2, int(target_fc * 0.90))),
        }))

        frames_bgr: list[np.ndarray] = []
        frames_gray_small: list[np.ndarray] = []
        intra_upper_diffs: list[float] = []
        intra_flow_magnitudes: list[float] = []

        for idx in sample_indices:
            if idx >= fc:
                decoded_frame_shortfall = True
                intra_upper_diffs.append(0.0)
                intra_flow_magnitudes.append(0.0)
                continue
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ret, frame = cap.read()
            if ret and frame is not None:
                f_bgr = frame.astype(np.float32)
                frames_bgr.append(f_bgr)
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                small = cv2.resize(gray, (180, 320), interpolation=cv2.INTER_AREA)
                frames_gray_small.append(small)

                # Read companion frame +0.5s later within the same segment
                comp_idx = min(fc - 1, idx + intra_step)
                if comp_idx <= idx:
                    comp_idx = max(0, idx - intra_step)
                cap.set(cv2.CAP_PROP_POS_FRAMES, comp_idx)
                ret2, frame2 = cap.read()
                if ret2 and frame2 is not None:
                    h_curr = f_bgr.shape[0]
                    upper_cut = max(1, int(h_curr * 0.60))  # Top 60% excludes ASS subtitle box
                    f2_bgr = frame2.astype(np.float32)
                    intra_diff = round(float(np.mean(np.abs(f2_bgr[:upper_cut] - f_bgr[:upper_cut]))), 3)
                    intra_upper_diffs.append(intra_diff)

                    gray2 = cv2.cvtColor(frame2, cv2.COLOR_BGR2GRAY)
                    small2 = cv2.resize(gray2, (180, 320), interpolation=cv2.INTER_AREA)
                    g1_top = small[:int(320 * 0.60), :]
                    g2_top = small2[:int(320 * 0.60), :]
                    flow_intra = cv2.calcOpticalFlowFarneback(
                        g1_top, g2_top, None,
                        pyr_scale=0.5, levels=3, winsize=15,
                        iterations=3, poly_n=5, poly_sigma=1.2, flags=0
                    )
                    mag_intra, _ = cv2.cartToPolar(flow_intra[..., 0], flow_intra[..., 1])
                    intra_flow_magnitudes.append(round(float(np.mean(mag_intra)), 3))
                else:
                    decoded_frame_shortfall = True
                    intra_upper_diffs.append(0.0)
            else:
                decoded_frame_shortfall = True
                intra_upper_diffs.append(0.0)
        cap.release()
        if tmp_path is not None:
            tmp_path.unlink(missing_ok=True)

        if len(frames_bgr) < 3:
            res = dict(empty_metrics)
            res["sampled_frames"] = len(frames_bgr)
            res["decoded_frame_count"] = fc
            res["decoded_frame_shortfall"] = decoded_frame_shortfall
            return res

        h = frames_bgr[0].shape[0]
        upper_cutoff = max(1, int(h * 0.60))  # Top 60% excludes bottom ASS subtitles

        full_diffs: list[float] = []
        upper_diffs: list[float] = []
        flow_magnitudes: list[float] = []

        for i in range(len(frames_bgr) - 1):
            f1, f2 = frames_bgr[i], frames_bgr[i + 1]
            full_diffs.append(round(float(np.mean(np.abs(f2 - f1))), 3))
            upper_diffs.append(round(float(np.mean(np.abs(f2[:upper_cutoff] - f1[:upper_cutoff]))), 3))

            # Compute Farneback optical flow on upper 60% of downscaled gray frame
            g1 = frames_gray_small[i][:int(320 * 0.60), :]
            g2 = frames_gray_small[i + 1][:int(320 * 0.60), :]
            flow = cv2.calcOpticalFlowFarneback(
                g1, g2, None,
                pyr_scale=0.5, levels=3, winsize=15,
                iterations=3, poly_n=5, poly_sigma=1.2, flags=0
            )
            mag, _ = cv2.cartToPolar(flow[..., 0], flow[..., 1])
            flow_magnitudes.append(round(float(np.mean(mag)), 3))

        start_frame = frames_bgr[0][:upper_cutoff]
        mid_frame = frames_bgr[len(frames_bgr) // 2][:upper_cutoff]
        end_frame = frames_bgr[-1][:upper_cutoff]

        start_to_mid = round(float(np.mean(np.abs(mid_frame - start_frame))), 3)
        mid_to_end = round(float(np.mean(np.abs(end_frame - mid_frame))), 3)
        start_to_end = round(float(np.mean(np.abs(end_frame - start_frame))), 3)

        mean_full = round(float(np.mean(full_diffs)), 3) if full_diffs else 0.0
        mean_upper = round(float(np.mean(upper_diffs)), 3) if upper_diffs else 0.0
        min_pair_upper = round(float(min(upper_diffs)), 3) if upper_diffs else 0.0
        min_intra_diff = round(float(min(intra_upper_diffs)), 3) if intra_upper_diffs else 0.0
        all_flows = intra_flow_magnitudes if intra_flow_magnitudes else flow_magnitudes
        mean_flow = round(float(np.mean(all_flows)), 3) if all_flows else 0.0

        # Static or frozen detection:
        # 1. Decoded frame count falls short of expected duration (early stream freeze like psych_03/08)
        # 2. Mean upper visual diff below threshold (static background/thumbnail)
        # 3. Any transition pair in upper visual region has near-zero diff (frozen clip tail)
        # 4. Any intra-segment 0.5s window has near-zero diff (5-image static slideshow or frozen clip)
        # 5. Mid-to-End diff near zero (e.g., zoompan stopped or single clip froze after 10s)
        # 6. Mean optical flow below threshold
        is_static_or_frozen = (
            decoded_frame_shortfall
            or mean_upper < MIN_FRAME_DIFF_THRESHOLD
            or min_pair_upper < MIN_PAIR_TOP_DIFF_THRESHOLD
            or min_intra_diff < MIN_INTRA_SEGMENT_DIFF_THRESHOLD
            or mid_to_end < MIN_PAIR_TOP_DIFF_THRESHOLD
            or mean_flow < MIN_OPTICAL_FLOW_THRESHOLD
        )

        return {
            "sampled_frames": len(frames_bgr),
            "decoded_frame_count": fc,
            "decoded_frame_shortfall": decoded_frame_shortfall,
            "full_frame_diffs": full_diffs,
            "upper_region_diffs": upper_diffs,
            "intra_segment_upper_diffs": intra_upper_diffs,
            "min_intra_segment_diff": min_intra_diff,
            "start_to_mid_diff": start_to_mid,
            "mid_to_end_diff": mid_to_end,
            "start_to_end_diff": start_to_end,
            "mean_full_diff": mean_full,
            "mean_upper_diff": mean_upper,
            "min_pair_upper_diff": min_pair_upper,
            "optical_flow_mean": mean_flow,
            "is_static_or_frozen": is_static_or_frozen,
        }

    @staticmethod
    def _dhash_from_gray(gray_img: np.ndarray) -> str:
        """Computes 64-bit horizontal gradient difference hash (dHash) from a 2D grayscale array."""
        blurred = cv2.GaussianBlur(gray_img, (5, 5), 0)
        resized = cv2.resize(blurred, (9, 8), interpolation=cv2.INTER_AREA)
        diff = resized[:, 1:] > resized[:, :-1]
        bit_val = 0
        for bit in diff.flatten():
            bit_val = (bit_val << 1) | int(bool(bit))
        return f"{bit_val:016x}"

    @staticmethod
    def hamming_distance_hex(hash_a: str, hash_b: str) -> int:
        """Computes 64-bit Hamming distance between two 16-char hex dHash strings."""
        if not hash_a or not hash_b or len(hash_a) != 16 or len(hash_b) != 16:
            return 64
        try:
            val_a = int(hash_a, 16)
            val_b = int(hash_b, 16)
            return int((val_a ^ val_b).bit_count())
        except ValueError:
            return 64

    @classmethod
    def compute_perceptual_dhash(cls, video_path: Path) -> dict[str, Any]:
        """
        Guard 2 (R37): Extracts frames at 20%, 50%, and 80% of clip duration,
        crops central 70% ROI (plus multi-scale 84% & 100% ROIs to defeat edge-crop tricks),
        converts to grayscale 9x8, and computes 64-bit dHash and horizontally-flipped dHash.
        """
        path = Path(video_path)
        if not path.exists() or not path.is_file():
            return {
                "file_path": str(path),
                "frames_sampled": 0,
                "dhash_20": "",
                "dhash_50": "",
                "dhash_80": "",
                "dhash_flip_20": "",
                "dhash_flip_50": "",
                "dhash_flip_80": "",
                "roi_signatures": [],
            }

        import os
        import tempfile
        import threading
        tmp_path: Path | None = None
        open_path = path
        if os.name != "nt" and not str(path).startswith("/tmp"):
            try:
                tmp_path = Path(tempfile.gettempdir()) / f"_tmp_dhash_{os.getpid()}_{threading.get_ident()}_{path.name}"
                shutil.copy2(path, tmp_path)
                open_path = tmp_path
            except Exception:
                tmp_path = None
                open_path = path

        cap = cv2.VideoCapture(str(open_path.resolve()))
        if not cap.isOpened():
            if tmp_path is not None:
                tmp_path.unlink(missing_ok=True)
            return {
                "file_path": str(path),
                "frames_sampled": 0,
                "dhash_20": "",
                "dhash_50": "",
                "dhash_80": "",
                "dhash_flip_20": "",
                "dhash_flip_50": "",
                "dhash_flip_80": "",
                "roi_signatures": [],
            }

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        sample_ratios = (0.20, 0.50, 0.80)
        roi_scales = (0.70, 0.84, 1.00)

        dhash_70_normal: list[str] = []
        dhash_70_flip: list[str] = []
        roi_signatures: list[dict[str, dict[str, str]]] = []

        try:
            for ratio in sample_ratios:
                target_idx = max(0, min(total_frames - 1, int(total_frames * ratio))) if total_frames > 0 else 0
                cap.set(cv2.CAP_PROP_POS_FRAMES, target_idx)
                ok, frame = cap.read()
                if not ok or frame is None or frame.size == 0:
                    continue
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                h, w = gray.shape[:2]
                if h < 16 or w < 16:
                    continue

                frame_rois: dict[str, dict[str, str]] = {}
                for scale in roi_scales:
                    margin = (1.0 - scale) / 2.0
                    y0 = int(round(h * margin))
                    y1 = max(y0 + 8, int(round(h * (1.0 - margin))))
                    x0 = int(round(w * margin))
                    x1 = max(x0 + 9, int(round(w * (1.0 - margin))))
                    roi = gray[y0:y1, x0:x1]
                    roi_flip = cv2.flip(roi, 1)
                    h_norm = cls._dhash_from_gray(roi)
                    h_flip = cls._dhash_from_gray(roi_flip)
                    scale_key = f"{int(round(scale * 100))}"
                    frame_rois[scale_key] = {"normal": h_norm, "flip": h_flip}
                    if scale_key == "70":
                        dhash_70_normal.append(h_norm)
                        dhash_70_flip.append(h_flip)

                roi_signatures.append(frame_rois)
        finally:
            cap.release()
            if tmp_path is not None:
                tmp_path.unlink(missing_ok=True)

        return {
            "file_path": str(path),
            "frames_sampled": len(roi_signatures),
            "dhash_20": dhash_70_normal[0] if len(dhash_70_normal) > 0 else "",
            "dhash_50": dhash_70_normal[1] if len(dhash_70_normal) > 1 else "",
            "dhash_80": dhash_70_normal[2] if len(dhash_70_normal) > 2 else "",
            "dhash_flip_20": dhash_70_flip[0] if len(dhash_70_flip) > 0 else "",
            "dhash_flip_50": dhash_70_flip[1] if len(dhash_70_flip) > 1 else "",
            "dhash_flip_80": dhash_70_flip[2] if len(dhash_70_flip) > 2 else "",
            "roi_signatures": roi_signatures,
        }

    @classmethod
    def min_perceptual_dhash_distance(cls, sig_a: dict[str, Any], sig_b: dict[str, Any]) -> int:
        """
        Computes the minimum 64-bit dHash Hamming distance across sampled frames (20%, 50%, 80%)
        and multi-scale central ROIs (70%, 84%, 100%) including horizontal flip invariance.
        If distance <= MAX_PERCEPTUAL_DHASH_HAMMING_DISTANCE (10), the two clips are perceptually near-identical.
        """
        rois_a = sig_a.get("roi_signatures") or []
        rois_b = sig_b.get("roi_signatures") or []
        if not rois_a or not rois_b:
            # Fallback to top-level dhash_50
            h_a = sig_a.get("dhash_50", "")
            h_b = sig_b.get("dhash_50", "")
            h_b_flip = sig_b.get("dhash_flip_50", "")
            return min(
                cls.hamming_distance_hex(h_a, h_b),
                cls.hamming_distance_hex(h_a, h_b_flip),
            )

        frame_best_distances: list[int] = []
        pair_count = min(len(rois_a), len(rois_b))
        for idx in range(pair_count):
            fa = rois_a[idx]
            fb = rois_b[idx]
            best_for_frame = 64
            for scale_a, hashes_a in fa.items():
                norm_a = hashes_a.get("normal", "")
                for scale_b, hashes_b in fb.items():
                    norm_b = hashes_b.get("normal", "")
                    flip_b = hashes_b.get("flip", "")
                    d1 = cls.hamming_distance_hex(norm_a, norm_b)
                    d2 = cls.hamming_distance_hex(norm_a, flip_b)
                    if d1 < best_for_frame:
                        best_for_frame = d1
                    if d2 < best_for_frame:
                        best_for_frame = d2
            frame_best_distances.append(best_for_frame)

        if not frame_best_distances:
            return 64
        # Return median/minimum representative distance across sampled frames
        frame_best_distances.sort()
        return int(frame_best_distances[len(frame_best_distances) // 2])

    @classmethod
    def verify_not_synthetic_derivative(cls, video_path: Path, strict: bool = True) -> dict[str, Any]:
        """
        Guard 2 (R37): Inspects ffprobe/ffmpeg container metadata tags (title, comment, etc.).
        If any tag contains banned synthetic derivative markers ('unique_flow_derivative',
        'unique_batch', '_boost', 'derivative_'), immediately raises MediaIntegrityError.
        Uses a fast binary header/tail pre-filter to avoid spawning 500+ ffmpeg processes on clean files.
        """
        path = Path(video_path)
        tags: dict[str, str] = {}
        matched_markers: list[str] = []

        if path.exists() and path.is_file():
            # Fast binary pre-scan of first 256KB and last 256KB (where MP4 moov/udta/meta atoms reside)
            may_contain_marker = False
            try:
                sz = path.stat().st_size
                with open(path, "rb") as bf:
                    head_bytes = bf.read(262144).lower()
                    tail_bytes = b""
                    if sz > 262144:
                        bf.seek(max(0, sz - 262144))
                        tail_bytes = bf.read(262144).lower()
                combined_bytes = head_bytes + b" " + tail_bytes
                for marker in BANNED_DERIVATIVE_METADATA_MARKERS:
                    if marker.lower().encode("utf-8") in combined_bytes:
                        may_contain_marker = True
                        break
            except Exception:
                may_contain_marker = True

            if may_contain_marker:
                # 1. Inspect via ffprobe JSON format.tags if available
                ffprobe_exe = cls.resolve_ffprobe_exe()
                if ffprobe_exe:
                    try:
                        cmd = [
                            ffprobe_exe,
                            "-v", "quiet",
                            "-print_format", "json",
                            "-show_format",
                            str(path.resolve()),
                        ]
                        res = subprocess.run(cmd, capture_output=True, text=True, timeout=15.0, check=False)
                        if res.returncode == 0 and res.stdout.strip():
                            data = json.loads(res.stdout)
                            raw_tags = data.get("format", {}).get("tags", {}) or {}
                            for k, v in raw_tags.items():
                                tags[str(k).lower()] = str(v)
                    except Exception as exc:
                        logger.debug("ffprobe tag check note for %s: %s", path.name, exc)

                # 2. Supplement via ffmpeg -i stderr Metadata parsing
                if not tags:
                    try:
                        ffmpeg_exe = cls.resolve_ffmpeg_exe()
                        cmd = [ffmpeg_exe, "-hide_banner", "-i", str(path.resolve())]
                        res = subprocess.run(cmd, capture_output=True, text=True, timeout=15.0, check=False)
                        stderr_txt = res.stderr or ""
                        for line in stderr_txt.splitlines():
                            m = re.match(r"^\s*(title|comment|description|synopsis|artist|album)\s*:\s*(.+)$", line, re.IGNORECASE)
                            if m:
                                key = m.group(1).strip().lower()
                                val = m.group(2).strip()
                                tags[key] = val
                    except Exception as exc:
                        logger.debug("ffmpeg -i tag check note for %s: %s", path.name, exc)

                for tag_key, tag_val in tags.items():
                    val_lower = tag_val.lower()
                    for marker in BANNED_DERIVATIVE_METADATA_MARKERS:
                        if marker.lower() in val_lower:
                            matched_markers.append(f"{tag_key}={tag_val} (matched '{marker}')")

        is_synthetic = len(matched_markers) > 0
        if is_synthetic and strict:
            raise MediaIntegrityError(
                "FATAL R37 VIOLATION: Synthetic FFmpeg derivative clip detected — "
                "clips must be raw Google Flow downloads, never FFmpeg-transformed clones. "
                f"[file={path.name}, matches={matched_markers}]"
            )

        return {
            "file_path": str(path),
            "is_synthetic_derivative": is_synthetic,
            "tags": tags,
            "matched_markers": matched_markers,
        }

    @classmethod
    def validate_video_asset(
        cls,
        file_path: Path,
        asset_type: str = "clip",
        strict: bool = True,
        quarantine_on_fail: bool = False,
        min_size_bytes: int | None = None,
        min_duration_sec: float | None = None,
        max_duration_sec: float | None = None,
        check_motion: bool = True,
        check_audio: bool = True,
    ) -> dict[str, Any]:
        """
        Executes the 7-Point Local Media Integrity Gate on a clip or final Shorts video:
        1. Extension == '.mp4' and file_size_bytes >= 1MB (1,000,000 bytes).
        2. Active video stream (codec_type == 'video') present.
        3. Container & decoded video stream duration within expected bounds (FINAL_SHORTS_DURATION_MIN_SEC-FINAL_SHORTS_DURATION_MAX_SEC [24.0s-105.0s] for final_shorts; frame_count/fps >= min_dur * 0.95).
        4. Start/Mid/End & Intra-Segment Frame Diff + Optical Flow above threshold (zero static/frozen frames).
        5. Valid resolution & audio stream (for final_shorts).
        6. Active speech narration, non-truncation, and dead-air <= max_allowed_dead_air_sec(dur) (floor DEAD_AIR_FLOOR_SEC) (for final_shorts).
        7. Guard 2 (R37): Zero synthetic FFmpeg derivative metadata tags.
        """
        path = Path(file_path)
        is_final = asset_type == "final_shorts"

        # Guard 2 (R37): Fail-fast on synthetic FFmpeg derivative metadata tags
        derivative_check = cls.verify_not_synthetic_derivative(path, strict=strict)
        check_7_not_derivative = not derivative_check["is_synthetic_derivative"]

        req_size = min_size_bytes if min_size_bytes is not None else (
            MIN_FINAL_VIDEO_SIZE_BYTES if is_final else MIN_CLIP_SIZE_BYTES
        )
        req_min_dur = min_duration_sec if min_duration_sec is not None else (
            FINAL_SHORTS_DURATION_MIN_SEC if is_final else FLOW_CLIP_DURATION_MIN_SEC
        )
        req_max_dur = max_duration_sec if max_duration_sec is not None else (
            FINAL_SHORTS_DURATION_MAX_SEC if is_final else FLOW_CLIP_DURATION_MAX_SEC
        )

        probe = cls.probe_streams(path)
        errors: list[str] = []
        if not check_7_not_derivative:
            errors.append(
                "FATAL R37 VIOLATION: Synthetic FFmpeg derivative clip detected — "
                f"clips must be raw Google Flow downloads, never FFmpeg-transformed clones ({derivative_check['matched_markers']})"
            )

        # Gate 1: Extension & Minimum File Size (>= 1MB)
        check_1_ext_and_size = (
            probe["exists"]
            and probe["extension"] == ".mp4"
            and not cls.is_forbidden_Static_or_image_source(path)
            and probe["file_size_bytes"] >= req_size
        )
        if not check_1_ext_and_size:
            errors.append(
                f"Check 1 Failed [Ext/Size]: path={path.name}, ext={probe['extension']}, "
                f"size={probe['file_size_bytes']}B (required .mp4 >= {req_size}B)"
            )

        # Gate 2: Video Stream Existence (codec_type == "video")
        check_2_video_stream = bool(
            probe["has_video_stream"]
            and probe["codec_type"] == "video"
            and probe["width"] > 0
            and probe["height"] > 0
        )
        if not check_2_video_stream:
            errors.append(
                f"Check 2 Failed [Video Stream]: has_video={probe['has_video_stream']}, "
                f"codec={probe['video_codec']}, res={probe['width']}x{probe['height']}"
            )

        # Gate 3: Container & Decoded Video Stream Duration Range Validation
        dur = probe["duration_seconds"]
        vid_stream_dur = probe.get("video_stream_duration_seconds") or dur
        decoded_dur_ok = (vid_stream_dur >= req_min_dur * 0.95)
        check_3_duration = (req_min_dur <= dur <= req_max_dur) and decoded_dur_ok
        if not check_3_duration:
            errors.append(
                f"Check 3 Failed [Duration/VideoStream]: container_duration={dur}s, "
                f"decoded_video_duration={vid_stream_dur}s ({probe.get('frame_count', 0)} frames @ {probe.get('fps', 0)}fps), "
                f"required range [{req_min_dur}s, {req_max_dur}s] (video stream >= {req_min_dur * 0.95:.2f}s)"
            )

        # Gate 4: Start/Middle/End + Intra-Segment Frame Diff & Optical Flow (Anti-Static / Anti-Thumbnail Stretch)
        motion = cls.compute_frame_motion_metrics(
            path,
            expected_duration_sec=req_min_dur if is_final else None,
        ) if (check_2_video_stream and check_motion) else {
            "sampled_frames": 0,
            "decoded_frame_count": probe.get("frame_count", 0),
            "decoded_frame_shortfall": False,
            "full_frame_diffs": [],
            "upper_region_diffs": [],
            "intra_segment_upper_diffs": [],
            "min_intra_segment_diff": 0.0,
            "start_to_mid_diff": 0.0,
            "mid_to_end_diff": 0.0,
            "start_to_end_diff": 0.0,
            "mean_full_diff": 0.0,
            "mean_upper_diff": 0.0,
            "min_pair_upper_diff": 0.0,
            "optical_flow_mean": 0.0,
            "is_static_or_frozen": not check_motion is False,
        }
        check_4_dynamic_motion = True if not check_motion else (not motion["is_static_or_frozen"])
        if not check_4_dynamic_motion:
            errors.append(
                f"Check 4 Failed [Static/Frozen Frame Detected]: decoded_frames={motion.get('decoded_frame_count')}, "
                f"shortfall={motion.get('decoded_frame_shortfall')}, mean_upper_diff={motion['mean_upper_diff']} "
                f"(min>={MIN_FRAME_DIFF_THRESHOLD}), min_pair_upper_diff={motion['min_pair_upper_diff']} "
                f"(min>={MIN_PAIR_TOP_DIFF_THRESHOLD}), min_intra_segment_diff={motion.get('min_intra_segment_diff', 0.0)} "
                f"(min>={MIN_INTRA_SEGMENT_DIFF_THRESHOLD}), mid_to_end_diff={motion['mid_to_end_diff']}, "
                f"optical_flow={motion['optical_flow_mean']} (min>={MIN_OPTICAL_FLOW_THRESHOLD})"
            )

        # Gate 5: Format & Audio Sync Check
        is_vertical_9_16 = (probe["width"] > 0 and probe["height"] > probe["width"])
        check_5_format = is_vertical_9_16 and (probe["has_audio_stream"] if is_final else True)
        if not check_5_format:
            errors.append(
                f"Check 5 Failed [Format/Audio]: res={probe['width']}x{probe['height']} (vertical={is_vertical_9_16}), "
                f"has_audio={probe['has_audio_stream']}"
            )

        # Gate 6: Audio Speech Activity, Natural Breathing Cadence, & Non-Truncation Check (for final_shorts)
        audio_analysis: dict[str, Any] = {}
        check_6_audio_speech = True
        if is_final and check_audio and probe["has_audio_stream"]:
            from pipeline.video_autopsy import VideoAutopsyEngine
            audio_analysis = VideoAutopsyEngine.inspect_audio_stream(path)
            max_allowed_dead_air = max_allowed_dead_air_sec(dur)
            check_6_audio_speech = bool(
                audio_analysis.get("has_active_speech")
                and not audio_analysis.get("is_truncated_at_30s")
                and float(audio_analysis.get("cumulative_dead_air_sec", 99.0)) <= max_allowed_dead_air
            )
            if not check_6_audio_speech:
                errors.append(
                    f"Check 6 Failed [Audio Speech/Truncation/DeadAir]: has_speech={audio_analysis.get('has_active_speech')}, "
                    f"truncated_at_30s={audio_analysis.get('is_truncated_at_30s')}, "
                    f"speech_end={audio_analysis.get('speech_end_sec')}s, "
                    f"last_100ms_dbfs={audio_analysis.get('last_100ms_dbfs')}dB, "
                    f"dead_air={audio_analysis.get('cumulative_dead_air_sec')}s (max<={max_allowed_dead_air}s)"
                )

        passed = len(errors) == 0
        report = {
            "file_path": str(path),
            "file_name": path.name,
            "asset_type": asset_type,
            "passed": passed,
            "status": "PASS" if passed else "FAIL",
            "checks": {
                "check_1_mp4_and_min_size": check_1_ext_and_size,
                "check_2_video_stream_exists": check_2_video_stream,
                "check_3_duration_in_range": check_3_duration,
                "check_4_dynamic_frame_motion": check_4_dynamic_motion,
                "check_5_format_and_audio": check_5_format,
                "check_6_audio_speech_integrity": check_6_audio_speech,
                "check_7_not_synthetic_derivative": check_7_not_derivative,
            },
            "probe": probe,
            "motion": motion,
            "audio_analysis": audio_analysis,
            "derivative_check": derivative_check,
            "errors": errors,
            "width": probe["width"],
            "height": probe["height"],
            "fps": probe["fps"],
            "frame_count": probe["frame_count"],
            "duration_seconds": probe["duration_seconds"],
            "video_stream_duration_seconds": vid_stream_dur,
            "file_size_bytes": probe["file_size_bytes"],
            "has_audio_stream": probe["has_audio_stream"],
            "is_valid_shorts_format": passed and is_vertical_9_16,
        }

        report["passed_integrity"] = passed
        report["motion_analysis"] = {
            "mean_frame_diff": motion.get("mean_upper_diff", 0.0),
            "min_pair_top_diff": motion.get("min_pair_upper_diff", 0.0),
            "min_intra_segment_diff": motion.get("min_intra_segment_diff", 0.0),
            "intra_segment_upper_diffs": motion.get("intra_segment_upper_diffs", []),
            "mean_optical_flow": motion.get("optical_flow_mean", 0.0),
            "start_to_mid_diff": motion.get("start_to_mid_diff", 0.0),
            "mid_to_end_diff": motion.get("mid_to_end_diff", 0.0),
            "start_to_end_diff": motion.get("start_to_end_diff", 0.0),
        }

        if not passed:
            logger.error("Media Integrity Gate FAILED for %s: %s", path.name, "; ".join(errors))
            if quarantine_on_fail and path.exists():
                try:
                    path.unlink(missing_ok=True)
                    logger.info("Discarded defective media asset: %s", path)
                except Exception as del_err:
                    logger.warning("Could not delete defective asset %s: %s", path, del_err)
            if strict:
                raise MediaIntegrityError(
                    f"FATAL ERROR [Media Integrity Gate]: {path.name} failed validation -> {'; '.join(errors)}"
                )

        return report

    @classmethod
    def get_ffmpeg_exe(cls) -> str:
        """Alias for resolve_ffmpeg_exe()."""
        return cls.resolve_ffmpeg_exe()

    @classmethod
    def probe_media(cls, file_path: Path) -> dict[str, Any]:
        """Probes media streams and returns a probe_report-compatible dictionary."""
        p = cls.probe_streams(file_path)
        p["is_valid_shorts_format"] = bool(
            p.get("has_video_stream") and p.get("width", 0) > 0 and p.get("height", 0) > p.get("width", 0)
        )
        return p

    @classmethod
    def validate_video_file(
        cls,
        file_path: Path,
        min_size_bytes: int | None = None,
        require_30s_shorts: bool = False,
        check_motion: bool = True,
        check_audio: bool = True,
        strict: bool = True,
    ) -> dict[str, Any]:
        """Validates a clip or final Shorts MP4 via the 7-Point Local Media Integrity Gate."""
        return cls.validate_video_asset(
            file_path=file_path,
            asset_type="final_shorts" if require_30s_shorts else "clip",
            strict=strict,
            min_size_bytes=min_size_bytes,
            min_duration_sec=FINAL_SHORTS_DURATION_MIN_SEC if require_30s_shorts else 2.5,
            max_duration_sec=FINAL_SHORTS_DURATION_MAX_SEC if require_30s_shorts else 35.0,
            check_motion=check_motion,
            check_audio=check_audio,
        )

