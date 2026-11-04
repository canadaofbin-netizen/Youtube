"""
ALL ABOUT BRAIN — Source-Conditioned 1:1 Reenactment Engine & Non-Infringement Gate (Rule R67 / RQ1–RQ5).

Architecture (6-Stage Zero-Pixel-Copy Reenactment Pipeline):
  Stage 1 (`extract_source_edl`):
      Quarantines source video strictly inside `/tmp/aab_reenact/<slug>/` (outside `WORKSPACE_ROOT`),
      decomposes shot boundaries, optical-flow camera motion, spatial blocking zones, and stores ONLY
      non-pixel geometric descriptors + 64-bit `dHash` digests + SHA-256 5-gram transcript hashes in
      `03_visuals/source_edl.json` (and `<dossier>/08_reenactment_edl.json`).
  Stage 2 (`sanitize_structural_frames`):
      In `/tmp/aab_reenact/<slug>/guides/`, masks/inpaints copyrighted wall posters (e.g. cartoon decals)
      and VHS burn-in captions, replaces human skin/head regions with smooth neutral matte-white porcelain
      mannequin silhouettes while preserving chair angles, wardrobe tones, floor props, and pose vectors,
      and expands `4:3 -> 9:16` (`720x1280`) high-key studio framing without black bars.
  Stage 3 (`translate_porcelain_keyframes`):
      Uses native Google Flow `0-credit` `Image` mode (`Nano Banana 2.1`, `x4` batch per prompt,
      `generate_flow_image_batch`) with `(structural_guide.png, master_cast_or_env.png)` (`<= 2` ingredients)
      to synthesize 100% newly generated `porcelain_cinematic_v7` (`R66`) reference keyframes in
      `03_visuals/reference_images/`, auto-selecting the highest-scoring `Q1..Q7` + `RQ2` candidate,
      registering `flow_image_generation` provenance, and rendering a repo-safe schematic vs porcelain
      comparison sheet (`03_visuals/reenactment_comparison_sheet.png`, zero raw source pixels).
  Stage 4 & 5 (`produce_reenactment_clips` & `validate_reenactment_non_infringement`):
      Generates `~78%` source-conditioned lab choreography clips + `>= 20%` (`~22%`) original `R66`
      Contained Living 4-Color 3D Brain / `hstack` mechanism cuts in Google Flow, purges `/tmp/aab_reenact`,
      and enforces `RQ1–RQ5` in `05_assembly/reenactment_qa_report.json`.
"""

from __future__ import annotations

import asyncio
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
    BRAIN_SETTINGS,
    DEFAULT_REENACT_IMAGE_BACKEND,
    DIORAMA_TARGET_CUT_MIN,
    DOSSIERS_DIR,
    FLOW_ZERO_CREDIT_IMAGE_BATCH_COUNT,
    PORCELAIN_V7_LONG_TAKE_MAX_SEC,
    PORCELAIN_V7_MIN_CUT_SEC,
    PORCELAIN_V7_STYLE_PROFILE,
    PORCELAIN_V7_TARGET_CLIP_MAX,
    PROJECTS_DIR,
    REF_IMAGES_DIRNAME,
    REENACT_BRAIN_RATIO_MIN,
    REENACT_COMPARISON_SHEET_FILENAME,
    REENACT_COMPOSITION_MATCH_MIN,
    REENACT_EDL_FILENAME,
    REENACT_IMAGE_BACKENDS,
    REENACT_LAB_RATIO_TARGET,
    REENACT_MAX_TRANSCRIPT_5GRAM_OVERLAP,
    REENACT_MIN_DHASH_DISTANCE,
    REENACT_QA_REPORT_FILENAME,
    REENACT_QUARANTINE_ROOT,
    WORKSPACE_ROOT,
    YUNET_FACE_MODEL_PATH,
)
from pipeline.reference_image_qa import (
    _dhash_64,
    _hamming_hex,
    build_reference_image_specs,
    inspect_single_reference_image,
    register_reference_image,
    write_reference_image_specs,
)

import threading

BANNED_SOURCE_BRAND_TOKENS: tuple[str, ...] = (
    "tweety",
    "winnie the pooh",
    "pooh bear",
    "looney tunes",
    "disney",
    "warner bros",
)

_DETECTOR_TLS = threading.local()


def _extract_youtube_id(url_or_id: str) -> str:
    raw = str(url_or_id or "").strip()
    if not raw:
        return ""
    for pat in (
        r"(?:v=|youtu\.be/|/shorts/|/embed/)([A-Za-z0-9_-]{11})",
        r"^([A-Za-z0-9_-]{11})$",
    ):
        m = re.search(pat, raw)
        if m:
            return m.group(1)
    return ""


def _parse_ts_sec(token: str) -> float | None:
    s = str(token or "").strip()
    if not s:
        return None
    parts = s.split(":")
    try:
        if len(parts) == 1:
            return max(0.0, float(parts[0]))
        if len(parts) == 2:
            return max(0.0, int(parts[0]) * 60.0 + float(parts[1]))
        if len(parts) == 3:
            return max(0.0, int(parts[0]) * 3600.0 + int(parts[1]) * 60.0 + float(parts[2]))
    except ValueError:
        return None
    return None


def _parse_section_window(section: str | None) -> tuple[float, float] | None:
    raw = str(section or "").strip().lstrip("*")
    if not raw or "-" not in raw:
        return None
    lhs, rhs = raw.split("-", 1)
    t0 = _parse_ts_sec(lhs)
    t1 = _parse_ts_sec(rhs)
    if t0 is None or t1 is None or t1 <= t0:
        return None
    return (round(t0, 2), round(t1, 2))


def detect_human_faces_yunet(
    bgr: np.ndarray,
    score_threshold: float = 0.42,
) -> list[tuple[int, int, int, int, float]]:
    """
    Detects human faces on both color and B&W (1920s–1960s 16mm grayscale) frames using bundled
    OpenCV Zoo Apache-2.0 `face_detection_yunet_2023mar.onnx` (plus Haar fallback if unavailable).
    Returns `[(x, y, w, h, score), ...]` in original image pixel coordinates.
    """
    if bgr is None or bgr.size == 0:
        return []
    h, w = bgr.shape[:2]
    if h < 16 or w < 16:
        return []

    max_dim = max(h, w)
    if max_dim > 640:
        scale = 640.0 / float(max_dim)
    elif max_dim < 240:
        scale = 320.0 / float(max_dim)
    else:
        scale = 1.0
    in_w = max(32, int(round(w * scale)))
    in_h = max(32, int(round(h * scale)))
    resized = cv2.resize(bgr, (in_w, in_h), interpolation=cv2.INTER_LINEAR) if scale != 1.0 else bgr.copy()

    hsv_r = cv2.cvtColor(resized, cv2.COLOR_BGR2HSV)
    is_bw = float(np.median(hsv_r[:, :, 1])) < 24.0
    probe_frames: list[np.ndarray] = [resized]
    if is_bw:
        gray_r = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
        clahe = cv2.createCLAHE(clipLimit=2.2, tileGridSize=(8, 8)).apply(gray_r)
        probe_frames.append(cv2.cvtColor(clahe, cv2.COLOR_GRAY2BGR))

    boxes_raw: list[tuple[int, int, int, int, float]] = []
    model_path = Path(YUNET_FACE_MODEL_PATH)
    if model_path.exists():
        det = getattr(_DETECTOR_TLS, "yunet", None)
        if det is None:
            try:
                det = cv2.FaceDetectorYN.create(
                    str(model_path),
                    "",
                    (in_w, in_h),
                    float(score_threshold),
                    0.3,
                    5000,
                )
                _DETECTOR_TLS.yunet = det
            except Exception:
                det = None
                _DETECTOR_TLS.yunet = False
        if det:
            det.setScoreThreshold(float(score_threshold))
            det.setInputSize((in_w, in_h))
            for pf in probe_frames:
                try:
                    _, faces = det.detect(pf)
                except Exception:
                    faces = None
                if faces is not None and len(faces) > 0:
                    for row in faces:
                        fx, fy, fw, fh = float(row[0]), float(row[1]), float(row[2]), float(row[3])
                        sc = float(row[-1])
                        if fw >= 8 and fh >= 8 and sc >= score_threshold:
                            boxes_raw.append(
                                (
                                    int(round(fx / scale)),
                                    int(round(fy / scale)),
                                    int(round(fw / scale)),
                                    int(round(fh / scale)),
                                    round(sc, 4),
                                )
                            )

    if not boxes_raw and is_bw:
        gray_orig = cv2.equalizeHist(cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY))
        haar_dir = getattr(cv2.data, "haarcascades", "")
        if haar_dir:
            frontal = getattr(_DETECTOR_TLS, "haar_frontal", None)
            if frontal is None:
                p_f = Path(haar_dir) / "haarcascade_frontalface_default.xml"
                frontal = cv2.CascadeClassifier(str(p_f)) if p_f.exists() else False
                _DETECTOR_TLS.haar_frontal = frontal
            profile = getattr(_DETECTOR_TLS, "haar_profile", None)
            if profile is None:
                p_p = Path(haar_dir) / "haarcascade_profileface.xml"
                profile = cv2.CascadeClassifier(str(p_p)) if p_p.exists() else False
                _DETECTOR_TLS.haar_profile = profile
            for casc in (frontal, profile):
                if casc:
                    rects = casc.detectMultiScale(gray_orig, scaleFactor=1.12, minNeighbors=5, minSize=(22, 22))
                    for rx, ry, rw, rh in rects if rects is not None else []:
                        boxes_raw.append(
                            (
                                int(round(rx / scale)),
                                int(round(ry / scale)),
                                int(round(rw / scale)),
                                int(round(rh / scale)),
                                0.50,
                            )
                        )

    boxes_raw.sort(key=lambda b: b[4], reverse=True)
    deduped: list[tuple[int, int, int, int, float]] = []
    for bx, by, bw_box, bh_box, bsc in boxes_raw:
        x0 = max(0, min(w - 1, bx))
        y0 = max(0, min(h - 1, by))
        x1 = max(x0 + 1, min(w, bx + bw_box))
        y1 = max(y0 + 1, min(h, by + bh_box))
        keep = True
        for ex, ey, ew, eh, _ in deduped:
            ix0, iy0 = max(x0, ex), max(y0, ey)
            ix1, iy1 = min(x1, ex + ew), min(y1, ey + eh)
            inter = max(0, ix1 - ix0) * max(0, iy1 - iy0)
            union = max(1, (x1 - x0) * (y1 - y0) + ew * eh - inter)
            if (inter / float(union)) > 0.45:
                keep = False
                break
        if keep:
            deduped.append((x0, y0, x1 - x0, y1 - y0, bsc))
    return deduped


def detect_non_porcelain_human_faces_yunet(
    bgr: np.ndarray,
    score_threshold: float = 0.62,
) -> list[tuple[int, int, int, int, float]]:
    """
    Detects real human faces (both color photorealistic flesh faces and B&W archival faces with eyes/mouth)
    via YuNet while excluding smooth featureless matte-white porcelain mannequin heads (`porcelain_r >= 0.82`)
    and low-confidence flat wooden/toy surface false positives.
    """
    raw_boxes = detect_human_faces_yunet(bgr, score_threshold=score_threshold)
    if not raw_boxes or bgr is None or bgr.size == 0:
        return []
    h, w = bgr.shape[:2]
    human_boxes: list[tuple[int, int, int, int, float]] = []
    for bx, by, bw_b, bh_b, sc in raw_boxes:
        crop = bgr[max(0, by) : min(h, by + bh_b), max(0, bx) : min(w, bx + bw_b)]
        if crop.size == 0 or crop.shape[0] < 12 or crop.shape[1] < 12:
            continue
        ch, cw = crop.shape[:2]
        inner = crop[max(0, int(ch * 0.22)) : max(1, int(ch * 0.78)), max(0, int(cw * 0.22)) : max(1, int(cw * 0.78))]
        if inner.size == 0:
            inner = crop
        hsv = cv2.cvtColor(inner, cv2.COLOR_BGR2HSV)
        ycrcb = cv2.cvtColor(inner, cv2.COLOR_BGR2YCrCb)
        porc_ratio = float(np.mean((hsv[:, :, 1] <= 55) & (hsv[:, :, 2] >= 150)))
        skin_ratio = float(
            np.mean(
                (hsv[:, :, 0] >= 4)
                & (hsv[:, :, 0] <= 22)
                & (hsv[:, :, 1] >= 48)
                & (hsv[:, :, 1] <= 170)
                & (ycrcb[:, :, 1] >= 135)
                & (ycrcb[:, :, 1] <= 178)
            )
        )
        dark_feat_ratio = float(np.mean(hsv[:, :, 2] < 70))
        lap_var = float(cv2.Laplacian(cv2.cvtColor(inner, cv2.COLOR_BGR2GRAY), cv2.CV_64F).var())
        # Smooth featureless matte-white porcelain head oval -> not a human face
        if porc_ratio >= 0.80 and skin_ratio <= 0.06 and dark_feat_ratio <= 0.035:
            continue
        # Low-confidence smooth warm prop/wood surface without eye/nostril/mouth dark features -> not a human face
        if sc < 0.70 and dark_feat_ratio < 0.022 and lap_var < 28.0:
            continue
        human_boxes.append((bx, by, bw_b, bh_b, sc))
    return human_boxes


def _resolve_ffmpeg_bin() -> str:
    sys_ff = shutil.which("ffmpeg")
    if sys_ff:
        return sys_ff
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"


def _ensure_outside_workspace(work_dir: Path) -> Path:
    resolved = work_dir.resolve()
    ws_resolved = Path(WORKSPACE_ROOT).resolve()
    if resolved == ws_resolved or ws_resolved in resolved.parents:
        raise ValueError(
            f"R67 quarantine violation: work_dir {resolved} must reside outside WORKSPACE_ROOT ({ws_resolved})"
        )
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


def _normalize_words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9']+", str(text or "").lower())


def compute_5gram_sha256_set(text_or_segments: str | list[str]) -> set[str]:
    if isinstance(text_or_segments, list):
        joined = " ".join(str(x) for x in text_or_segments)
    else:
        joined = str(text_or_segments or "")
    words = _normalize_words(joined)
    if len(words) < 5:
        return set()
    out: set[str] = set()
    for i in range(len(words) - 4):
        gram = " ".join(words[i : i + 5])
        out.add(hashlib.sha256(gram.encode("utf-8")).hexdigest()[:24])
    return out


def _classify_camera_and_zones(start_bgr: np.ndarray, end_bgr: np.ndarray) -> dict[str, Any]:
    g1 = cv2.cvtColor(cv2.resize(start_bgr, (320, 240)), cv2.COLOR_BGR2GRAY)
    g2 = cv2.cvtColor(cv2.resize(end_bgr, (320, 240)), cv2.COLOR_BGR2GRAY)
    flow = cv2.calcOpticalFlowFarneback(g1, g2, None, 0.5, 3, 15, 3, 5, 1.2, 0)
    dx = float(np.median(flow[:, :, 0]))
    dy = float(np.median(flow[:, :, 1]))
    mag = float(np.mean(np.hypot(flow[:, :, 0], flow[:, :, 1])))

    if abs(dx) < 0.35 and abs(dy) < 0.35 and mag < 1.1:
        cam_move = "locked_tripod"
    elif abs(dx) >= abs(dy):
        cam_move = "lateral_pan_right" if dx < -0.35 else "lateral_pan_left"
    else:
        cam_move = "slow_push_in" if dy < -0.35 else "gentle_tilt_down"

    edges = cv2.Canny(g1, 50, 150) > 0
    h, w = edges.shape
    zones: list[str] = []
    if float(np.mean(edges[int(h * 0.25) : int(h * 0.78), : int(w * 0.38)])) > 0.035:
        zones.append("left_foreground_zone")
    if float(np.mean(edges[int(h * 0.25) : int(h * 0.78), int(w * 0.62) :])) > 0.035:
        zones.append("right_foreground_zone")
    if float(np.mean(edges[int(h * 0.52) : int(h * 0.92), int(w * 0.25) : int(w * 0.75)])) > 0.030:
        zones.append("center_action_zone")
    if float(np.mean(edges[: int(h * 0.32), int(w * 0.20) : int(w * 0.80)])) > 0.025:
        zones.append("upper_background_zone")
    if not zones:
        zones.append("center_action_zone")

    return {
        "camera_motion": cam_move,
        "optical_flow_dx": round(dx, 3),
        "optical_flow_dy": round(dy, 3),
        "motion_magnitude": round(mag, 3),
        "active_zones": zones,
    }


def _resolve_dossier_personal_names(dossier_dir: Path | None) -> list[str]:
    if dossier_dir is None or not Path(dossier_dir).exists():
        return []
    d_dir = Path(dossier_dir)
    found: set[str] = set()
    for fname in ("dossier.json", "04_media_refs.json"):
        p = d_dir / fname
        if not p.exists():
            continue
        try:
            doc = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(doc, dict):
            for n in doc.get("source_personal_names") or []:
                if str(n).strip():
                    found.add(str(n).strip().lower())
            for m in doc.get("media") or []:
                if isinstance(m, dict):
                    for n in m.get("source_personal_names") or []:
                        if str(n).strip():
                            found.add(str(n).strip().lower())
    return sorted(found)


def extract_source_edl(
    url_or_mp4: str | Path,
    slug: str,
    project_dir: Path | None = None,
    dossier_dir: Path | None = None,
    work_dir: Path | None = None,
    source_personal_names: list[str] | None = None,
    run_whisper: bool = True,
    section: str | None = None,
    scene_corr_threshold: float = 0.72,
    min_shot_sec: float = 3.0,
    sub_event_min_sec: float = 12.0,
) -> dict[str, Any]:
    """
    Stage 1: Downloads or opens the reference source video strictly inside `/tmp/aab_reenact/<slug>/`,
    segments shots, computes camera/blocking descriptors + 64-bit `dHash` digests + 5-gram SHA-256 hashes,
    and writes repo-safe `source_edl.json` (zero raw pixels or verbatim transcript text in repo).
    """
    q_dir = _ensure_outside_workspace(Path(work_dir) if work_dir else (REENACT_QUARANTINE_ROOT / slug))
    shots_dir = q_dir / "shots"
    shots_dir.mkdir(parents=True, exist_ok=True)
    src_mp4 = q_dir / "source.mp4"
    sec_bounds = _parse_section_window(section)
    ffmpeg_bin = _resolve_ffmpeg_bin()

    raw_in = str(url_or_mp4).strip()
    if Path(raw_in).exists():
        in_p = Path(raw_in).resolve()
        if sec_bounds is not None:
            subprocess.run(
                [
                    ffmpeg_bin,
                    "-y",
                    "-ss",
                    f"{sec_bounds[0]:.2f}",
                    "-to",
                    f"{sec_bounds[1]:.2f}",
                    "-i",
                    str(in_p),
                    "-c:v",
                    "libx264",
                    "-preset",
                    "ultrafast",
                    "-c:a",
                    "aac",
                    str(src_mp4),
                ],
                check=False,
                capture_output=True,
                timeout=180,
            )
        if not src_mp4.exists() and in_p != src_mp4:
            shutil.copy2(in_p, src_mp4)
    elif not src_mp4.exists():
        yt_dlp_bin = shutil.which("yt-dlp") or str(Path("/home/canadaofbin/hermes-venv/bin/yt-dlp"))
        dl_target = (q_dir / "source_full.mp4") if sec_bounds is not None else src_mp4
        cmd = [
            yt_dlp_bin,
            "--ignore-errors",
            "--no-playlist",
            "--ffmpeg-location",
            str(Path(ffmpeg_bin).parent),
            "-f",
            "mp4/best[height<=720]/best",
        ]
        if sec_bounds is not None:
            cmd += ["--download-sections", f"*{sec_bounds[0]:.2f}-{sec_bounds[1]:.2f}"]
        cmd += ["-o", str(dl_target), raw_in]
        subprocess.run(cmd, check=False, capture_output=True, text=True, timeout=180)
        if sec_bounds is not None:
            if dl_target.exists():
                # Ensure exact window: if yt-dlp returned the full untrimmed stream (p_dur >= t1*0.95),
                # seek to sec_bounds[0]; if yt-dlp already trimmed near sec_bounds[0] with keyframe pad, trim from 0.0
                probe_cap = cv2.VideoCapture(str(dl_target))
                p_fps = float(probe_cap.get(cv2.CAP_PROP_FPS) or 30.0)
                p_fc = int(probe_cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
                probe_cap.release()
                p_dur = p_fc / max(p_fps, 1.0)
                expected_dur = max(3.0, sec_bounds[1] - sec_bounds[0])
                if p_dur > (expected_dur + 3.0):
                    full_stream_returned = bool(sec_bounds[0] > 2.0 and p_dur >= sec_bounds[1] * 0.95)
                    trim_args = (
                        ["-ss", f"{sec_bounds[0]:.2f}", "-to", f"{sec_bounds[1]:.2f}"]
                        if full_stream_returned
                        else ["-ss", "0.00", "-t", f"{expected_dur:.2f}"]
                    )
                    subprocess.run(
                        [
                            ffmpeg_bin,
                            "-y",
                            *trim_args,
                            "-i",
                            str(dl_target),
                            "-c:v",
                            "libx264",
                            "-preset",
                            "ultrafast",
                            "-c:a",
                            "aac",
                            str(src_mp4),
                        ],
                        check=False,
                        capture_output=True,
                        timeout=180,
                    )
                if not src_mp4.exists():
                    shutil.move(str(dl_target), str(src_mp4))
                else:
                    dl_target.unlink(missing_ok=True)
            else:
                # Fallback without --download-sections + local ffmpeg trim
                subprocess.run(
                    [
                        yt_dlp_bin,
                        "--ignore-errors",
                        "--no-playlist",
                        "--ffmpeg-location",
                        str(Path(ffmpeg_bin).parent),
                        "-f",
                        "mp4/best[height<=720]/best",
                        "-o",
                        str(dl_target),
                        raw_in,
                    ],
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=180,
                )
                if dl_target.exists():
                    subprocess.run(
                        [
                            ffmpeg_bin,
                            "-y",
                            "-ss",
                            f"{sec_bounds[0]:.2f}",
                            "-to",
                            f"{sec_bounds[1]:.2f}",
                            "-i",
                            str(dl_target),
                            "-c:v",
                            "libx264",
                            "-preset",
                            "ultrafast",
                            "-c:a",
                            "aac",
                            str(src_mp4),
                        ],
                        check=False,
                        capture_output=True,
                        timeout=180,
                    )
                    dl_target.unlink(missing_ok=True)
        if not src_mp4.exists():
            raise FileNotFoundError(f"Failed to stage source video into quarantine: {src_mp4}")

    cap = cv2.VideoCapture(str(src_mp4))
    if not cap.isOpened():
        raise RuntimeError(f"Cannot decode quarantined source video: {src_mp4}")

    fps = float(cap.get(cv2.CAP_PROP_FPS) or 30.0)
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    duration_sec = round(frame_count / max(fps, 1.0), 2)

    # Detect shot cuts using sampled HSV+Gray histogram deltas every 0.25s
    step_frames = max(1, int(round(fps * 0.25)))
    cut_times: list[float] = [0.0]
    prev_hist: np.ndarray | None = None
    eff_min_shot = max(1.0, float(min_shot_sec))
    eff_corr_thresh = float(scene_corr_threshold)
    f_idx = 0
    while True:
        ok, frm = cap.read()
        if not ok or frm is None:
            break
        if f_idx % step_frames == 0:
            t_s = f_idx / max(fps, 1.0)
            small = cv2.resize(frm, (160, 120))
            hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)
            # Combine HSV (H,S) + V/luma histogram so B&W 16mm films segment accurately too
            hs_vec = cv2.calcHist([hsv], [0, 1], None, [12, 12], [0, 180, 0, 256]).flatten()
            v_vec = cv2.calcHist([hsv], [2], None, [32], [0, 256]).flatten()
            h_vec = np.concatenate([hs_vec, v_vec])
            norm = float(np.linalg.norm(h_vec))
            h_vec = h_vec / max(norm, 1e-6)
            if prev_hist is not None:
                corr = float(np.dot(prev_hist, h_vec))
                if (
                    corr < eff_corr_thresh
                    and (t_s - cut_times[-1]) >= eff_min_shot
                    and (duration_sec - t_s) >= max(1.5, eff_min_shot * 0.75)
                ):
                    cut_times.append(round(t_s, 2))
            prev_hist = h_vec
        f_idx += 1

    if len(cut_times) < 4 and duration_sec > 15.0:
        n_seg = min(12, max(4, int(duration_sec // max(5.0, min(15.0, duration_sec / 5.0)))))
        cut_times = [round(i * (duration_sec / n_seg), 2) for i in range(n_seg)]

    shots_meta: list[dict[str, Any]] = []
    source_dhashes: list[str] = []
    eff_sub_min = max(6.0, float(sub_event_min_sec))

    def _grab_at(sec: float) -> np.ndarray | None:
        cap.set(cv2.CAP_PROP_POS_MSEC, max(0.0, sec) * 1000.0)
        ok_g, f_g = cap.read()
        return f_g if ok_g and f_g is not None else None

    for i, t0 in enumerate(cut_times):
        t1 = cut_times[i + 1] if (i + 1) < len(cut_times) else duration_sec
        s_t = min(max(0.0, t0 + 0.35), max(0.0, duration_sec - 0.2))
        e_t = max(s_t, min(duration_sec - 0.2, t1 - 0.35))
        s_bgr = _grab_at(s_t)
        e_bgr = _grab_at(e_t)
        if s_bgr is None:
            continue
        if e_bgr is None:
            e_bgr = s_bgr.copy()
        shot_id = f"S{i + 1:02d}"
        s_png = shots_dir / f"{shot_id}_start.png"
        e_png = shots_dir / f"{shot_id}_end.png"
        cv2.imwrite(str(s_png), s_bgr)
        cv2.imwrite(str(e_png), e_bgr)

        dh_s = _dhash_64(cv2.cvtColor(s_bgr, cv2.COLOR_BGR2GRAY))
        dh_e = _dhash_64(cv2.cvtColor(e_bgr, cv2.COLOR_BGR2GRAY))
        for dh in (dh_s, dh_e):
            if dh not in source_dhashes:
                source_dhashes.append(dh)

        zone_info = _classify_camera_and_zones(s_bgr, e_bgr)
        sub_events: list[dict[str, Any]] = []
        if (t1 - t0) >= eff_sub_min:
            prev_hsv = cv2.cvtColor(s_bgr, cv2.COLOR_BGR2HSV)
            prev_sub_hist = cv2.calcHist([prev_hsv], [0, 1, 2], None, [8, 8, 16], [0, 180, 0, 256, 0, 256])
            cv2.normalize(prev_sub_hist, prev_sub_hist)
            probe_t = t0 + 6.0
            sub_idx = 0
            while probe_t < (t1 - 1.5):
                p_bgr = _grab_at(probe_t)
                if p_bgr is not None:
                    p_hsv = cv2.cvtColor(p_bgr, cv2.COLOR_BGR2HSV)
                    p_hist = cv2.calcHist([p_hsv], [0, 1, 2], None, [8, 8, 16], [0, 180, 0, 256, 0, 256])
                    cv2.normalize(p_hist, p_hist)
                    corr = float(cv2.compareHist(prev_sub_hist, p_hist, cv2.HISTCMP_CORREL))
                    if corr < 0.84:
                        sub_idx += 1
                        sub_id = f"{shot_id}_sub{sub_idx:02d}"
                        sub_png = shots_dir / f"{sub_id}.png"
                        cv2.imwrite(str(sub_png), p_bgr)
                        dh_sub = _dhash_64(cv2.cvtColor(p_bgr, cv2.COLOR_BGR2GRAY))
                        if dh_sub not in source_dhashes:
                            source_dhashes.append(dh_sub)
                        sub_events.append(
                            {
                                "sub_id": sub_id,
                                "timestamp_sec": round(probe_t, 2),
                                "hsv_corr": round(corr, 4),
                                "source_dhash_64": dh_sub,
                            }
                        )
                    prev_sub_hist = p_hist
                probe_t += 6.0

        shot_entry: dict[str, Any] = {
            "shot_id": shot_id,
            "shot_index": i + 1,
            "start_sec": round(t0, 2),
            "end_sec": round(t1, 2),
            "duration_sec": round(max(0.1, t1 - t0), 2),
            "source_start_dhash_64": dh_s,
            "source_end_dhash_64": dh_e,
            **zone_info,
        }
        if sub_events:
            shot_entry["sub_events"] = sub_events
        shots_meta.append(shot_entry)
    cap.release()

    transcript_texts: list[str] = []
    cached_analysis = q_dir / "source_analysis.json"
    if cached_analysis.exists():
        try:
            ca = json.loads(cached_analysis.read_text(encoding="utf-8"))
            for seg in ca.get("segments") or ca.get("transcript_segments") or ca.get("transcript") or []:
                if isinstance(seg, dict) and seg.get("text"):
                    transcript_texts.append(str(seg["text"]))
                elif isinstance(seg, str):
                    transcript_texts.append(seg)
        except Exception:
            pass

    if not transcript_texts and run_whisper:
        try:
            from faster_whisper import WhisperModel

            w_model = WhisperModel("base", device="cpu", compute_type="int8")
            segs, _ = w_model.transcribe(str(src_mp4), language="en")
            transcript_texts = [str(s.text).strip() for s in segs if str(s.text).strip()]
        except Exception:
            transcript_texts = []

    fivegram_hashes = sorted(compute_5gram_sha256_set(transcript_texts))
    resolved_names = (
        source_personal_names
        if source_personal_names is not None
        else _resolve_dossier_personal_names(dossier_dir)
    )
    banned_names = sorted({str(n).strip().lower() for n in resolved_names if str(n).strip()})
    yt_id = _extract_youtube_id(raw_in)
    source_video_id = yt_id if yt_id else Path(raw_in).stem

    edl_doc: dict[str, Any] = {
        "schema": "source_reenactment_edl_v1",
        "rule": "R67",
        "slug": slug,
        "source_reference_id": raw_in if raw_in.startswith("http") else Path(raw_in).name,
        "source_video_id": source_video_id,
        "extracted_at": datetime.now(timezone.utc).isoformat(),
        "source_geometry": {
            "width": width,
            "height": height,
            "fps": round(fps, 2),
            "duration_sec": duration_sec,
            "aspect_ratio": round(width / max(float(height), 1.0), 4),
        },
        "shot_count": len(shots_meta),
        "shots": shots_meta,
        "source_dhash_64_list": source_dhashes,
        "source_5gram_sha256_list": fivegram_hashes,
        "source_personal_names": banned_names,
        "sanitization_verified": False,
        "zero_raw_pixels_in_repo": True,
    }
    if sec_bounds is not None:
        edl_doc["section_window"] = str(section)
        edl_doc["section_bounds_sec"] = [sec_bounds[0], sec_bounds[1]]

    if project_dir is not None:
        vis_dir = Path(project_dir) / "03_visuals"
        vis_dir.mkdir(parents=True, exist_ok=True)
        (vis_dir / REENACT_EDL_FILENAME).write_text(
            json.dumps(edl_doc, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    if dossier_dir is not None:
        d_dir = Path(dossier_dir)
        d_dir.mkdir(parents=True, exist_ok=True)
        (d_dir / "08_reenactment_edl.json").write_text(
            json.dumps(edl_doc, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    return edl_doc


def sanitize_structural_frame_bgr(
    raw_bgr: np.ndarray,
    poster_boxes_norm: list[tuple[float, float, float, float]] | None = None,
    target_w: int = 720,
    target_h: int = 1280,
) -> np.ndarray:
    """
    Stage 2 single-frame OpenCV sanitizer:
      1. Masks explicit `poster_boxes_norm` or detected high-chroma upper-corner wall decals into neutral gallery plates.
      2. Masks bottom VHS caption strip (`y >= 0.89`) if high-frequency text edges appear.
      3. Replaces exposed human faces/skin (both color skin tones AND YuNet B&W/color face ovals) with smooth
         featureless matte-white porcelain mannequin silhouettes.
      4. Expands `4:3 -> 9:16` (`720x1280`) vertical studio framing seamlessly (zero black bars).
    """
    img = raw_bgr.copy()
    h0, w0 = img.shape[:2]
    if h0 >= 64 and w0 >= 64:
        g0 = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        max_trim_y = h0 // 4
        max_trim_x = w0 // 4
        ty0 = 0
        while ty0 < max_trim_y and float(np.mean(g0[ty0, :])) < 20.0 and float(np.percentile(g0[ty0, :], 90)) < 38.0:
            ty0 += 1
        ty1 = h0
        while (h0 - ty1) < max_trim_y and ty1 > ty0 + 32 and float(np.mean(g0[ty1 - 1, :])) < 20.0 and float(np.percentile(g0[ty1 - 1, :], 90)) < 38.0:
            ty1 -= 1
        tx0 = 0
        while tx0 < max_trim_x and float(np.mean(g0[ty0:ty1, tx0])) < 20.0 and float(np.percentile(g0[ty0:ty1, tx0], 90)) < 38.0:
            tx0 += 1
        tx1 = w0
        while (w0 - tx1) < max_trim_x and tx1 > tx0 + 32 and float(np.mean(g0[ty0:ty1, tx1 - 1])) < 20.0 and float(np.percentile(g0[ty0:ty1, tx1 - 1], 90)) < 38.0:
            tx1 -= 1
        if (ty0 > 0 or ty1 < h0 or tx0 > 0 or tx1 < w0) and (ty1 - ty0) >= h0 // 2 and (tx1 - tx0) >= w0 // 2:
            img = img[ty0:ty1, tx0:tx1].copy()

    h, w = img.shape[:2]
    hsv_init = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    med_sat = float(np.median(hsv_init[:, :, 1]))

    # 1. Conditional or explicit wall poster masking (preserves B&W / unmarked laboratory corners)
    wall_sample = img[max(0, int(h * 0.08)) : max(4, int(h * 0.24)), int(w * 0.35) : int(w * 0.65)]
    wall_med = (
        np.median(wall_sample.reshape(-1, 3), axis=0).astype(np.uint8)
        if wall_sample.size > 0
        else np.array([216, 222, 226], dtype=np.uint8)
    )
    wall_color = tuple(int(max(195, min(238, c))) for c in wall_med.tolist())

    if poster_boxes_norm is not None:
        boxes_to_mask = list(poster_boxes_norm)
    else:
        boxes_to_mask = []
        for cx0, cy0, cx1, cy1 in (
            (0.00, 0.00, 0.24, 0.34),
            (0.74, 0.00, 1.00, 0.34),
        ):
            px0, py0 = int(w * cx0), int(h * cy0)
            px1, py1 = int(w * cx1), int(h * cy1)
            patch_s = hsv_init[py0:py1, px0:px1, 1]
            if patch_s.size > 0 and float(np.mean(patch_s >= 80)) >= 0.06:
                boxes_to_mask.append((cx0, cy0, cx1, cy1))

    for x0n, y0n, x1n, y1n in boxes_to_mask:
        x0, y0 = int(w * x0n), int(h * y0n)
        x1, y1 = int(w * x1n), int(h * y1n)
        cv2.rectangle(img, (x0, y0), (x1, y1), wall_color, -1)
        pad_x, pad_y = max(4, (x1 - x0) // 7), max(4, (y1 - y0) // 7)
        if (x1 - x0) > 28 and (y1 - y0) > 28:
            cv2.rectangle(img, (x0 + pad_x, y0 + pad_y), (x1 - pad_x, y1 - pad_y), (234, 236, 238), -1)
            cv2.rectangle(img, (x0 + pad_x, y0 + pad_y), (x1 - pad_x, y1 - pad_y), (185, 190, 195), 1)

    # 2. Remove any burned-in VHS bottom caption strip or lower-third subtitle overlay (y=0.78..0.98)
    lt_y0, lt_y1 = int(h * 0.78), int(h * 0.98)
    lt_x0, lt_x1 = int(w * 0.10), int(w * 0.90)
    if lt_y1 > lt_y0 + 8 and lt_x1 > lt_x0 + 16:
        lt_band = img[lt_y0:lt_y1, lt_x0:lt_x1]
        lt_gray = cv2.cvtColor(lt_band, cv2.COLOR_BGR2GRAY)
        if (
            float(np.mean(cv2.Canny(lt_gray, 70, 170) > 0)) > 0.055
            and float(np.percentile(lt_gray, 96)) >= 205.0
            and float(np.median(lt_gray)) <= 125.0
        ):
            txt_mask = cv2.dilate((lt_gray >= 175).astype(np.uint8) * 255, np.ones((7, 13), np.uint8), iterations=1)
            blurred_lt = cv2.GaussianBlur(img[lt_y0:lt_y1, :], (35, 35), 0)
            full_lt_mask = np.zeros((lt_y1 - lt_y0, w), dtype=np.float32)
            full_lt_mask[:, lt_x0:lt_x1] = txt_mask.astype(np.float32) / 255.0
            full_lt_mask = cv2.GaussianBlur(full_lt_mask, (9, 9), 0)[:, :, None]
            img[lt_y0:lt_y1, :] = np.clip(
                img[lt_y0:lt_y1, :].astype(np.float32) * (1.0 - full_lt_mask) + blurred_lt.astype(np.float32) * full_lt_mask,
                0,
                255,
            ).astype(np.uint8)

    bot_y0 = int(h * 0.89)
    gray_bot = cv2.cvtColor(img[bot_y0:, :], cv2.COLOR_BGR2GRAY)
    if float(np.mean(cv2.Canny(gray_bot, 70, 170) > 0)) > 0.04:
        floor_strip = img[max(0, bot_y0 - max(6, int(h * 0.05))) : bot_y0, :]
        if floor_strip.size > 0:
            img[bot_y0:, :] = cv2.resize(floor_strip, (w, h - bot_y0), interpolation=cv2.INTER_LINEAR)

    # 3. Replace human faces & skin regions (YuNet B&W + color face ovals + HSV/YCrCb color skin mask)
    face_boxes = detect_human_faces_yunet(img, score_threshold=0.42)
    face_mask = np.zeros((h, w), dtype=np.uint8)
    for fx, fy, fw, fh, _fsc in face_boxes:
        cx_f = int(round(fx + fw * 0.50))
        cy_f = int(round(fy + fh * 0.48))
        ax_w = max(8, int(round(fw * 0.68)))
        ax_h = max(10, int(round(fh * 0.80)))
        cv2.ellipse(face_mask, (cx_f, cy_f), (ax_w, ax_h), 0, 0, 360, 255, -1)

    if med_sat >= 16.0:
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        ycrcb = cv2.cvtColor(img, cv2.COLOR_BGR2YCrCb)
        skin_mask = (
            (hsv[:, :, 0] <= 22)
            & (hsv[:, :, 1] >= 42)
            & (hsv[:, :, 1] <= 175)
            & (hsv[:, :, 2] >= 65)
            & (ycrcb[:, :, 1] >= 135)
            & (ycrcb[:, :, 1] <= 180)
            & (ycrcb[:, :, 2] >= 85)
            & (ycrcb[:, :, 2] <= 135)
        ).astype(np.uint8) * 255
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
        skin_mask = cv2.morphologyEx(skin_mask, cv2.MORPH_CLOSE, kernel, iterations=2)
    else:
        skin_mask = np.zeros((h, w), dtype=np.uint8)

    combined_mask = np.maximum(skin_mask, face_mask)
    combined_mask = cv2.GaussianBlur(combined_mask, (11, 11), 0)

    gray_full = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32)
    gray_smooth = cv2.GaussianBlur(gray_full, (31, 31), 0)
    # Smooth featureless matte-white oval shading (erases eye/nose/mouth high-frequency identity details)
    porcelain_luma = np.clip(214.0 + 0.08 * (gray_smooth - 128.0), 196.0, 245.0).astype(np.uint8)
    porcelain_bgr = np.stack(
        [
            porcelain_luma,
            porcelain_luma,
            np.clip(porcelain_luma.astype(np.int16) + 2, 0, 248).astype(np.uint8),
        ],
        axis=-1,
    )
    alpha = (combined_mask.astype(np.float32) / 255.0)[:, :, None]
    img = np.clip(img.astype(np.float32) * (1.0 - alpha) + porcelain_bgr.astype(np.float32) * alpha, 0, 255).astype(np.uint8)

    # 4. Expand 4:3 -> 9:16 vertical high-key studio composition (center room band + architectural ceiling & carpet floor)
    scaled_h = int(round(h * (target_w / max(float(w), 1.0))))
    scaled_h = min(target_h - 120, max(int(target_h * 0.42), scaled_h))
    mid_band = cv2.resize(img, (target_w, scaled_h), interpolation=cv2.INTER_CUBIC)
    # Neutralize residual yellow/sepia VHS cast on grayscale archival frames so guide matches neutral high-key porcelain
    if med_sat < 24.0:
        mid_g = cv2.cvtColor(mid_band, cv2.COLOR_BGR2GRAY)
        mid_band = np.stack([np.clip(mid_g.astype(np.int16) + 2, 0, 255).astype(np.uint8), mid_g, mid_g], axis=-1)

    top_pad = int(round((target_h - scaled_h) * 0.44))
    bot_pad = target_h - scaled_h - top_pad

    top_anchor = cv2.GaussianBlur(mid_band[: max(8, scaled_h // 10), :], (31, 31), 0)
    top_ext = cv2.resize(top_anchor, (target_w, top_pad), interpolation=cv2.INTER_LINEAR)
    top_w_max = 0.72 if float(np.mean(top_ext)) < 130.0 else 0.36
    top_w_min = 0.28 if float(np.mean(top_ext)) < 130.0 else 0.0
    yy_top = np.linspace(top_w_max, top_w_min, top_pad, dtype=np.float32)[:, None, None]
    studio_white = np.full_like(top_ext, (232, 236, 240), dtype=np.uint8)
    top_ext = np.clip(top_ext.astype(np.float32) * (1.0 - yy_top) + studio_white.astype(np.float32) * yy_top, 0, 255).astype(np.uint8)

    bot_anchor = cv2.GaussianBlur(mid_band[scaled_h - max(8, scaled_h // 10) :, :], (31, 31), 0)
    bot_ext = cv2.resize(bot_anchor, (target_w, bot_pad), interpolation=cv2.INTER_LINEAR)
    bot_w_min = 0.28 if float(np.mean(bot_ext)) < 120.0 else 0.0
    bot_w_max = 0.76 if float(np.mean(bot_ext)) < 120.0 else 0.28
    yy_bot = np.linspace(bot_w_min, bot_w_max, bot_pad, dtype=np.float32)[:, None, None]
    warm_carpet = np.full_like(bot_ext, (196, 206, 214), dtype=np.uint8)
    bot_ext = np.clip(bot_ext.astype(np.float32) * (1.0 - yy_bot) + warm_carpet.astype(np.float32) * yy_bot, 0, 255).astype(np.uint8)

    out_916 = np.vstack([top_ext, mid_band, bot_ext])
    for seam_y in (top_pad, top_pad + scaled_h):
        y0s, y1s = max(0, seam_y - 10), min(target_h, seam_y + 10)
        out_916[y0s:y1s, :] = cv2.GaussianBlur(out_916[y0s:y1s, :], (15, 15), 0)
    return out_916


def sanitize_structural_frames(
    work_dir: Path,
    edl_doc: dict[str, Any],
    project_dir: Path | None = None,
    dossier_dir: Path | None = None,
    poster_boxes_norm: list[tuple[float, float, float, float]] | None = None,
) -> dict[str, Any]:
    """
    Stage 2 batch sanitizer across all extracted shot `(start, end)` frames inside `/tmp/aab_reenact/<slug>/`.
    """
    q_dir = _ensure_outside_workspace(Path(work_dir))
    shots_dir = q_dir / "shots"
    guides_dir = q_dir / "guides"
    guides_dir.mkdir(parents=True, exist_ok=True)

    guide_records: list[dict[str, Any]] = []
    for sh in edl_doc.get("shots") or []:
        shot_id = str(sh.get("shot_id") or "")
        frame_targets: list[tuple[str, Path, Path]] = [
            (which, shots_dir / f"{shot_id}_{which}.png", guides_dir / f"{shot_id}_{which}_guide.png")
            for which in ("start", "end")
        ]
        for sub_idx, sub_ev in enumerate(sh.get("sub_events") or [], start=1):
            if not isinstance(sub_ev, dict):
                continue
            sub_id = str(sub_ev.get("sub_id") or f"{shot_id}_sub{sub_idx:02d}")
            frame_targets.append(
                (f"sub{sub_idx:02d}", shots_dir / f"{sub_id}.png", guides_dir / f"{sub_id}_guide.png")
            )
        for which_lbl, src_p, dst_p in frame_targets:
            if not src_p.exists():
                continue
            bgr = cv2.imread(str(src_p))
            if bgr is None:
                continue
            san = sanitize_structural_frame_bgr(bgr, poster_boxes_norm=poster_boxes_norm)
            cv2.imwrite(str(dst_p), san)
            guide_records.append(
                {
                    "shot_id": shot_id,
                    "frame": which_lbl,
                    "guide_filename": dst_p.name,
                    "guide_dhash_64": _dhash_64(cv2.cvtColor(san, cv2.COLOR_BGR2GRAY)),
                }
            )

    edl_doc["sanitization_verified"] = len(guide_records) > 0
    edl_doc["sanitized_guide_count"] = len(guide_records)
    if project_dir is not None and (Path(project_dir) / "03_visuals").exists():
        (Path(project_dir) / "03_visuals" / REENACT_EDL_FILENAME).write_text(
            json.dumps(edl_doc, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    if dossier_dir is not None and Path(dossier_dir).exists():
        (Path(dossier_dir) / "08_reenactment_edl.json").write_text(
            json.dumps(edl_doc, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    return {"guides_dir": str(guides_dir), "count": len(guide_records), "guides": guide_records}


def _normalize_generated_png_916(png_path: Path, target_w: int = 864, target_h: int = 1536) -> None:
    bgr = cv2.imread(str(png_path))
    if bgr is None or bgr.size == 0:
        return
    h, w = bgr.shape[:2]
    target_ratio = 9.0 / 16.0
    cur_ratio = float(w) / max(float(h), 1.0)
    if abs(cur_ratio - target_ratio) > 0.025:
        if cur_ratio > target_ratio:
            new_w = int(round(h * target_ratio))
            x0 = max(0, (w - new_w) // 2)
            bgr = bgr[:, x0 : x0 + new_w]
        else:
            new_h = int(round(w / target_ratio))
            y0 = max(0, (h - new_h) // 2)
            bgr = bgr[y0 : y0 + new_h, :]
    if bgr.shape[1] < 720 or bgr.shape[0] < 1280:
        bgr = cv2.resize(bgr, (target_w, target_h), interpolation=cv2.INTER_LANCZOS4)
    # Prevent black border pixels < 6.0 mean
    for strip_slice in (
        (slice(0, max(4, bgr.shape[0] // 32)), slice(None)),
        (slice(bgr.shape[0] - max(4, bgr.shape[0] // 32), bgr.shape[0]), slice(None)),
    ):
        if float(np.mean(bgr[strip_slice])) < 8.0:
            bgr[strip_slice] = np.clip(bgr[strip_slice].astype(np.int16) + 18, 12, 255).astype(np.uint8)
    cv2.imwrite(str(png_path), bgr)


def render_reenactment_comparison_sheet(
    project_dir: Path,
    edl_doc: dict[str, Any],
    specs_payload: dict[str, Any],
) -> Path:
    """
    Renders a repo-safe 1:1 blocking diagram vs generated `porcelain_cinematic_v7` keyframe contact sheet
    at `03_visuals/reenactment_comparison_sheet.png` (ZERO raw pixels from the quarantined source video).
    """
    p_dir = Path(project_dir)
    vis_dir = p_dir / "03_visuals"
    ref_dir = vis_dir / REF_IMAGES_DIRNAME
    shots_by_id = {str(s.get("shot_id")): s for s in (edl_doc.get("shots") or [])}
    is_track_a = bool(shots_by_id)

    clip_specs = [s for s in (specs_payload.get("clip_anchors") or []) if (ref_dir / str(s.get("filename"))).exists()]
    if not clip_specs:
        clip_specs = [s for s in (specs_payload.get("all_specs") or []) if (ref_dir / str(s.get("filename"))).exists()]
    selected = clip_specs[:8]
    rows = max(1, len(selected))
    cell_w, cell_h = 270, 480
    canvas = np.full((rows * (cell_h + 24) + 64, cell_w * 2 + 72, 3), (245, 247, 250), dtype=np.uint8)
    sheet_hdr = (
        f"R67 SOURCE-CONDITIONED PORCELAIN REENACTMENT SHEET ({p_dir.name})"
        if is_track_a
        else f"R66-ANCHOR SCENE-BIBLE PORCELAIN REFERENCE SHEET ({p_dir.name})"
    )
    cv2.putText(
        canvas,
        sheet_hdr,
        (20, 38),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.54,
        (28, 36, 48),
        2,
        cv2.LINE_AA,
    )

    zone_boxes = {
        "upper_background_zone": (35, 65, 235, 145, (190, 210, 225), "upper_bg"),
        "left_foreground_zone": (22, 185, 112, 330, (175, 195, 215), "left_fg"),
        "right_foreground_zone": (158, 185, 248, 330, (175, 215, 195), "right_fg"),
        "center_action_zone": (68, 290, 202, 415, (210, 195, 180), "center_prop"),
        # Legacy R67 pilot zone aliases:
        "upper_observation_mirror": (35, 65, 235, 145, (190, 210, 225), "obs_mirror"),
        "left_chair_zone": (22, 185, 112, 330, (175, 195, 215), "left_chair"),
        "right_chair_or_door_zone": (158, 185, 248, 330, (175, 215, 195), "right_door"),
        "center_floor_playmat": (68, 290, 202, 415, (210, 195, 180), "floor_mat"),
    }

    for idx, sp in enumerate(selected):
        y_off = 56 + idx * (cell_h + 24)
        # Left panel: geometric blocking blueprint vector diagram (zero raw pixels)
        diag = np.full((cell_h, cell_w, 3), (234, 238, 242), dtype=np.uint8)
        cv2.rectangle(diag, (2, 2), (cell_w - 3, cell_h - 3), (180, 188, 198), 2)
        sc_id = str(sp.get("scene_id") or "")
        sh = shots_by_id.get(sc_id, {})
        active_z = sh.get("active_zones") or (
            ["center_action_zone", "left_foreground_zone"]
            if sp.get("present_cast")
            else ["upper_background_zone", "center_action_zone"]
        )
        for z_name in active_z:
            if z_name in zone_boxes:
                zx0, zy0, zx1, zy1, zcol, zlbl = zone_boxes[z_name]
                cv2.rectangle(diag, (zx0, zy0), (zx1, zy1), zcol, -1)
                cv2.rectangle(diag, (zx0, zy0), (zx1, zy1), (95, 110, 128), 2)
                cv2.putText(diag, zlbl, (zx0 + 6, zy0 + 20), cv2.FONT_HERSHEY_SIMPLEX, 0.36, (40, 50, 65), 1)
        cv2.putText(diag, f"Ref: {sp.get('ref_id')}", (12, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.46, (25, 35, 50), 1)
        sub_lbl = (
            f"Shot: {sc_id} | Cam: {sh.get('camera_motion', 'locked')[:14]}"
            if is_track_a
            else f"Loc: {str(sp.get('location_id') or sc_id)[:18]} | Cast: {len(sp.get('present_cast') or [])}"
        )
        cv2.putText(diag, sub_lbl, (12, 48), cv2.FONT_HERSHEY_SIMPLEX, 0.36, (55, 65, 80), 1)
        foot_lbl = "Poster/Face Sanitized: YES" if is_track_a else "Scene-Bible Zero-Pixel: YES"
        cv2.putText(diag, foot_lbl, (12, cell_h - 18), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (25, 110, 55), 1)
        canvas[y_off : y_off + cell_h, 24 : 24 + cell_w] = diag

        # Right panel: generated R66 porcelain keyframe PNG
        img_p = ref_dir / str(sp.get("filename"))
        gen_bgr = cv2.imread(str(img_p))
        if gen_bgr is not None:
            thumb = cv2.resize(gen_bgr, (cell_w, cell_h), interpolation=cv2.INTER_AREA)
            canvas[y_off : y_off + cell_h, 48 + cell_w : 48 + cell_w * 2] = thumb

    out_path = vis_dir / REENACT_COMPARISON_SHEET_FILENAME
    cv2.imwrite(str(out_path), canvas)
    return out_path


async def translate_porcelain_keyframes_async(
    project_dir: Path,
    slug: str,
    work_dir: Path | None = None,
    cdp_port: int = 9222,
    only_ref_ids: set[str] | None = None,
    force: bool = False,
    backend: str = DEFAULT_REENACT_IMAGE_BACKEND,
    batch_count: int = FLOW_ZERO_CREDIT_IMAGE_BATCH_COUNT,
) -> dict[str, Any]:
    """
    Stage 3: Synthesizes `porcelain_cinematic_v7` master anchors + shot start/end reference keyframes
    primarily inside Google Flow `0-credit` `Image` mode (`Nano Banana 2.1`, `x4` batch per prompt,
    auto-selecting the highest-scoring `Q1..Q7` + `RQ2 dHash >= 18` candidate), conditioning lab keyframes
    on `(sanitized_guide.png, ref_cast_or_env.png)` (`<= 2` ingredients).
    """
    from pipeline.flow_ingredients import generate_flow_image_batch
    from pipeline.flow_live_single_worker import allocate_dedicated_flow_project_tab
    from pipeline.flow_prompt_builder import load_visual_plan
    from pipeline.gemini_web_worker import generate_gemini_image
    from pipeline.reference_image_qa import load_provenance

    eff_backend = str(backend or DEFAULT_REENACT_IMAGE_BACKEND).strip().lower()
    if eff_backend not in REENACT_IMAGE_BACKENDS:
        raise ValueError(
            f"Unsupported reenactment image backend: {backend!r} (expected one of {REENACT_IMAGE_BACKENDS})"
        )
    eff_batch = max(1, min(4, int(batch_count or FLOW_ZERO_CREDIT_IMAGE_BATCH_COUNT)))

    p_dir = Path(project_dir)
    if not p_dir.exists():
        raise FileNotFoundError(f"Project directory does not exist: {p_dir}")
    vis_dir = p_dir / "03_visuals"
    ref_dir = vis_dir / REF_IMAGES_DIRNAME
    ref_dir.mkdir(parents=True, exist_ok=True)

    plan = load_visual_plan(project_dir=p_dir)
    script_path = p_dir / "02_script" / "script.json"
    narrs: list[str] = []
    if script_path.exists():
        s_doc = json.loads(script_path.read_text(encoding="utf-8"))
        narrs = [str(x) for x in (s_doc.get("sentences") or s_doc.get("clip_narrations") or []) if str(x).strip()]

    specs_payload = build_reference_image_specs(plan, narrs)
    write_reference_image_specs(p_dir, specs_payload)

    edl_path = vis_dir / REENACT_EDL_FILENAME
    edl_doc = json.loads(edl_path.read_text(encoding="utf-8")) if edl_path.exists() else {"shots": [], "source_dhash_64_list": []}
    source_dhashes = list(edl_doc.get("source_dhash_64_list") or [])

    q_dir = Path(work_dir) if work_dir else (REENACT_QUARANTINE_ROOT / slug)
    guides_dir = q_dir / "guides"

    import urllib.request
    from pipeline.studio.whale_session import DirectCDPClient

    ordered_specs = sorted(specs_payload.get("all_specs") or [], key=lambda s: int(s.get("generation_order") or 3))
    generated: list[str] = []
    failed: list[str] = []

    opened_tab_id: str | None = None
    ws_url: str | None = None
    uploaded_cache: set[str] = set()
    seen_img_srcs: set[str] = set()
    existing_prov = load_provenance(p_dir)

    def _open_dedicated_gemini_tab() -> tuple[str, str]:
        target_url = f"http://127.0.0.1:{cdp_port}/json/new?https://gemini.google.com/images"
        try:
            req = urllib.request.Request(target_url, method="PUT")
            with urllib.request.urlopen(req, timeout=8) as r:
                info = json.loads(r.read().decode("utf-8"))
        except Exception:
            with urllib.request.urlopen(target_url, timeout=8) as r:
                info = json.loads(r.read().decode("utf-8"))
        return str(info["id"]), str(info["webSocketDebuggerUrl"])

    def _close_dedicated_worker_tab(tid: str | None) -> None:
        if not tid:
            return
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{cdp_port}/json/close/{tid}", timeout=5):
                pass
        except Exception:
            pass

    try:
        client_cm = None
        client: DirectCDPClient | None = None
        for idx_sp, spec in enumerate(ordered_specs, start=1):
            ref_id = str(spec["ref_id"])
            if only_ref_ids and ref_id not in only_ref_ids:
                continue
            out_png = ref_dir / str(spec["filename"])
            if out_png.exists() and not force:
                q_chk = inspect_single_reference_image(out_png, spec)
                min_dh = min((_hamming_hex(q_chk.get("dhash_64", ""), sdh) for sdh in source_dhashes), default=64)
                if q_chk.get("passed") and min_dh >= REENACT_MIN_DHASH_DISTANCE:
                    if out_png.name not in existing_prov:
                        prov_tag = "flow_image_generation" if eff_backend == "flow" else "gemini_image_generation"
                        register_reference_image(p_dir, out_png.name, prov_tag)
                    generated.append(ref_id)
                    print(f"[reenact-refs {idx_sp}/{len(ordered_specs)}] {ref_id}: cached_ok (dHash_min={min_dh})", flush=True)
                    continue

            # Select <= 2 conditioning PNGs
            cond_paths: list[Path] = []
            sc_id = str(spec.get("scene_id") or "")
            which = str(spec.get("frame") or "start")
            guide_cand = guides_dir / f"{sc_id}_{which}_guide.png"
            if not guide_cand.exists() and sc_id.startswith("S"):
                guide_cand = guides_dir / f"{sc_id}_start_guide.png"
            if (
                guide_cand.exists()
                and spec.get("setting") not in (*BRAIN_SETTINGS, "brain_studio")
                and not bool(spec.get("skip_structural_guide"))
            ):
                cond_paths.append(guide_cand)

            raw_cond_ids = [str(c) for c in (spec.get("conditioned_on") or []) if str(c).strip()]
            if guide_cand in cond_paths:
                # Track A R67 lock: pair [guide_png, ref_cast_*] instead of [guide_png, ref_env_master]
                raw_cond_ids = [c for c in raw_cond_ids if c.startswith("ref_cast_")] + [
                    c for c in raw_cond_ids if not c.startswith("ref_cast_")
                ]
            for cond_id in raw_cond_ids:
                if len(cond_paths) >= 2:
                    break
                cand_p = ref_dir / f"{cond_id}.png"
                if cand_p.exists() and cand_p not in cond_paths:
                    cond_paths.append(cand_p)

            base_prompt = str(spec.get("prompt") or "")
            cast_suffix = ""
            if spec.get("present_cast") is not None:
                p_list = [str(x).strip() for x in (spec.get("present_cast") or []) if str(x).strip()]
                if len(p_list) == 0:
                    cast_suffix += " The room and all chairs are completely empty with zero figures present."
                else:
                    cast_suffix += f" Exactly {len(p_list)} clothed matte-white porcelain figure(s) appear in the frame ({', '.join(p_list)})."
            if spec.get("empty_chairs_note"):
                cast_suffix += f" {str(spec['empty_chairs_note']).strip()}"
            if "no text" not in base_prompt.lower() and "zero text" not in base_prompt.lower():
                cast_suffix += " Strictly zero text, zero letters, zero numbers, zero labels, no watermark."

            if guide_cand in cond_paths:
                i2i_prefix = (
                    "Vertical 9:16 high-key architectural documentary photograph. Match the room layout, chair placement, "
                    "tabletop props, and body pose geometry of the first structural guide image, replacing every figure with "
                    "articulated matte-white porcelain mannequins with smooth featureless oval porcelain heads and period "
                    "fabric clothing (bright studio daylight, clean blank unmarked walls, zero text or labels). "
                )
                full_prompt = f"{i2i_prefix}{base_prompt}{cast_suffix}"
            else:
                cast_head_lock = (
                    ", articulated matte-white porcelain mannequins with completely smooth featureless blank white oval heads and period fabric clothing"
                    if (spec.get("present_cast") and spec.get("setting") not in (*BRAIN_SETTINGS, "brain_studio"))
                    else ""
                )
                full_prompt = (
                    f"Vertical 9:16 portrait aspect ratio (tall vertical frame, full-bleed high-key studio daylight{cast_head_lock}). {base_prompt}{cast_suffix}"
                )

            ok_this = False
            for attempt in range(3):
                try:
                    if client is None:
                        if eff_backend == "flow":
                            flow_alloc = await allocate_dedicated_flow_project_tab(cdp_port=cdp_port)
                            opened_tab_id = str(flow_alloc["tab_id"])
                            ws_url = str(flow_alloc["ws_url"])
                        else:
                            opened_tab_id, ws_url = _open_dedicated_gemini_tab()
                        client_cm = DirectCDPClient(ws_url)
                        client = await client_cm.__aenter__()
                        await client.send("Page.enable")
                        uploaded_cache.clear()
                        seen_img_srcs.clear()
                        if eff_backend == "gemini":
                            await asyncio.sleep(4.5)

                    retry_suffix = (
                        ""
                        if attempt == 0
                        else " Ensure bright high-key daylight studio exposure, crisp architectural furniture edges, smooth matte-white porcelain heads, and full-bleed 9:16 vertical composition."
                    )
                    print(
                        f"[reenact-refs {idx_sp}/{len(ordered_specs)}] Generating {ref_id} via {eff_backend}"
                        f"{f' (0-credit x{eff_batch})' if eff_backend == 'flow' else ''} "
                        f"(try {attempt + 1}/3, cond={[p.name for p in cond_paths[:2]]})...",
                        flush=True,
                    )
                    if eff_backend == "flow":
                        flow_res = await generate_flow_image_batch(
                            client=client,
                            prompt=full_prompt + retry_suffix,
                            out_path=out_png,
                            conditioning_paths=cond_paths[:2] if cond_paths else None,
                            batch_count=eff_batch,
                            aspect="9:16",
                            uploaded_cache=uploaded_cache,
                            seen_img_srcs=seen_img_srcs,
                            spec=spec,
                            source_dhashes=source_dhashes,
                            project_dir=None,
                        )
                        if not flow_res.get("ok") or not flow_res.get("saved") or not out_png.exists():
                            print(
                                f"[reenact-refs {idx_sp}/{len(ordered_specs)}] {ref_id} try {attempt + 1} Flow batch miss: {flow_res.get('reason')}",
                                flush=True,
                            )
                            continue
                        _normalize_generated_png_916(out_png)
                        q_chk = inspect_single_reference_image(out_png, spec)
                        min_dh = min((_hamming_hex(q_chk.get("dhash_64", ""), sdh) for sdh in source_dhashes), default=64)
                        if q_chk.get("passed") and min_dh >= REENACT_MIN_DHASH_DISTANCE:
                            register_reference_image(
                                p_dir,
                                out_png.name,
                                "flow_image_generation",
                            )
                            print(
                                f"[reenact-refs {idx_sp}/{len(ordered_specs)}] {ref_id}: PASSED via Flow x{eff_batch} "
                                f"(best_of={flow_res.get('candidate_count')}, cand#{int(flow_res.get('selected_index', 0)) + 1}, dHash_min={min_dh})",
                                flush=True,
                            )
                            ok_this = True
                            break
                        out_png.unlink(missing_ok=True)
                    else:
                        gen_ok = await generate_gemini_image(
                            client=client,
                            prompt=full_prompt + retry_suffix,
                            out_path=out_png,
                            conditioning_paths=cond_paths[:2] if cond_paths else None,
                            force_new_chat=(attempt > 0 or (idx_sp % 5 == 0)),
                        )
                        if not gen_ok or not out_png.exists():
                            continue
                        _normalize_generated_png_916(out_png)
                        q_chk = inspect_single_reference_image(out_png, spec)
                        min_dh = min((_hamming_hex(q_chk.get("dhash_64", ""), sdh) for sdh in source_dhashes), default=64)
                        if q_chk.get("passed") and min_dh >= REENACT_MIN_DHASH_DISTANCE:
                            register_reference_image(p_dir, out_png.name, "gemini_image_generation")
                            print(f"[reenact-refs {idx_sp}/{len(ordered_specs)}] {ref_id}: PASSED (dHash_min={min_dh})", flush=True)
                            ok_this = True
                            break
                    print(
                        f"[reenact-refs {idx_sp}/{len(ordered_specs)}] {ref_id} try {attempt + 1} QA retry: passed={q_chk.get('passed')} failed_axes={q_chk.get('failed_axes')} dHash={min_dh}",
                        flush=True,
                    )
                except Exception as tab_exc:
                    print(
                        f"[reenact-refs {idx_sp}/{len(ordered_specs)}] {ref_id} try {attempt + 1} transient CDP error ({type(tab_exc).__name__}: {tab_exc}); rotating worker tab...",
                        flush=True,
                    )
                    if client_cm is not None:
                        try:
                            await client_cm.__aexit__(None, None, None)
                        except Exception:
                            pass
                    _close_dedicated_worker_tab(opened_tab_id)
                    client_cm = None
                    client = None
                    opened_tab_id = None
                    await asyncio.sleep(2.5)
            if ok_this:
                generated.append(ref_id)
            else:
                failed.append(ref_id)
    finally:
        if client_cm is not None:
            try:
                await client_cm.__aexit__(None, None, None)
            except Exception:
                pass
        _close_dedicated_worker_tab(opened_tab_id)

    sheet_path = render_reenactment_comparison_sheet(p_dir, edl_doc, specs_payload)
    return {
        "project_id": p_dir.name,
        "slug": slug,
        "backend": eff_backend,
        "batch_count": eff_batch if eff_backend == "flow" else 1,
        "generated_count": len(generated),
        "failed_ids": failed,
        "comparison_sheet": str(sheet_path),
    }


def translate_porcelain_keyframes(
    project_dir: Path,
    slug: str,
    work_dir: Path | None = None,
    cdp_port: int = 9222,
    only_ref_ids: set[str] | None = None,
    force: bool = False,
    backend: str = DEFAULT_REENACT_IMAGE_BACKEND,
    batch_count: int = FLOW_ZERO_CREDIT_IMAGE_BATCH_COUNT,
) -> dict[str, Any]:
    return asyncio.run(
        translate_porcelain_keyframes_async(
            project_dir=project_dir,
            slug=slug,
            work_dir=work_dir,
            cdp_port=cdp_port,
            only_ref_ids=only_ref_ids,
            force=force,
            backend=backend,
            batch_count=batch_count,
        )
    )


def purge_reenactment_quarantine(slug: str | None = None) -> dict[str, Any]:
    """Deletes `/tmp/aab_reenact` (or `/tmp/aab_reenact/<slug>`) after Stage 3 keyframe translation."""
    target = (REENACT_QUARANTINE_ROOT / slug) if slug else REENACT_QUARANTINE_ROOT
    existed = target.exists()
    if existed:
        shutil.rmtree(target, ignore_errors=True)
    if slug and REENACT_QUARANTINE_ROOT.exists() and not any(REENACT_QUARANTINE_ROOT.iterdir()):
        shutil.rmtree(REENACT_QUARANTINE_ROOT, ignore_errors=True)
    return {"purged_path": str(target), "existed": existed, "quarantine_exists": REENACT_QUARANTINE_ROOT.exists()}


def validate_reenactment_non_infringement(
    project_dir: str | Path,
    dossier_dir: str | Path | None = None,
    require_quarantine_purged: bool = True,
    save_report: bool = True,
) -> dict[str, Any]:
    """
    Evaluates the 5-Axis Reenactment Non-Infringement & Fidelity Contract (`RQ1–RQ5`):
      - `RQ1_zero_raw_source_leak`: Zero raw source videos/frames in project or dossier AND `/tmp/aab_reenact` purged.
      - `RQ2_perceptual_dhash_distance`: Every reference PNG & sampled native MP4 frame has 64-bit dHash distance >= 18 from source frames.
      - `RQ3_zero_transcript_and_name_overlap`: 0.0% 5-gram SHA-256 overlap with source ASR + zero source personal names.
      - `RQ4_zero_poster_or_brand_leak`: Sanitization verified + zero banned cartoon/brand tokens in script/prompts/metadata.
      - `RQ5_brain_intercut_and_blocking_alignment`: >= 20% original R66 4-color 3D brain / hstack cuts + >= 85% source_shot_id blocking alignment.
    """
    p_dir = Path(project_dir) if Path(project_dir).is_dir() else (Path(PROJECTS_DIR) / str(project_dir))
    vis_dir = p_dir / "03_visuals"
    scr_dir = p_dir / "02_script"
    asm_dir = p_dir / "05_assembly"
    pub_dir = p_dir / "06_publish"

    vp_path = vis_dir / "visual_plan.json"
    vp = json.loads(vp_path.read_text(encoding="utf-8")) if vp_path.exists() else {}
    slug = str(vp.get("dossier_slug") or vp.get("dossier") or "")
    d_dir = Path(dossier_dir) if dossier_dir else ((Path(DOSSIERS_DIR) / slug) if slug else None)

    edl_path = vis_dir / REENACT_EDL_FILENAME
    if not edl_path.exists() and d_dir and (d_dir / "08_reenactment_edl.json").exists():
        edl_path = d_dir / "08_reenactment_edl.json"
    edl_doc = json.loads(edl_path.read_text(encoding="utf-8")) if edl_path.exists() else {}

    # --- RQ1: Zero raw source files in repo & quarantine purged ---
    leaked_files: list[str] = []
    dyn_patterns: list[str] = ["source.mp4", "source_shots_sheet", "shot_0", "shot_1"]
    for cand_vid in (
        str(edl_doc.get("source_video_id") or "").strip(),
        _extract_youtube_id(str(edl_doc.get("source_reference_id") or "")),
    ):
        low_vid = cand_vid.lower()
        if len(low_vid) >= 5 and low_vid not in dyn_patterns:
            dyn_patterns.append(low_vid)
    suspicious_patterns = tuple(dyn_patterns)
    scan_roots = [p_dir] + ([d_dir] if (d_dir and d_dir.exists()) else [])
    for root in scan_roots:
        for f in root.rglob("*"):
            if not f.is_file():
                continue
            low_name = f.name.lower()
            if any(pat in low_name for pat in suspicious_patterns):
                leaked_files.append(str(f))
    quarantine_clean = (not REENACT_QUARANTINE_ROOT.exists()) if require_quarantine_purged else True
    rq1_ok = bool(len(leaked_files) == 0 and quarantine_clean and bool(edl_doc))

    # --- RQ2: Perceptual dHash distance >= 18 against all source frames ---
    source_dhashes = [str(x) for x in (edl_doc.get("source_dhash_64_list") or []) if str(x)]
    min_ref_dhash = 64
    min_clip_dhash = 64
    checked_ref_count = 0
    checked_clip_count = 0

    ref_dir = vis_dir / REF_IMAGES_DIRNAME
    if ref_dir.exists() and source_dhashes:
        for png_f in sorted(ref_dir.glob("*.png")):
            bgr = cv2.imread(str(png_f))
            if bgr is None:
                continue
            checked_ref_count += 1
            dh = _dhash_64(cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY))
            dist = min(_hamming_hex(dh, sdh) for sdh in source_dhashes)
            min_ref_dhash = min(min_ref_dhash, dist)

    native_dir = vis_dir / "flow_native_clips"
    if native_dir.exists() and source_dhashes:
        for mp4_f in sorted(native_dir.glob("clip_*.mp4")):
            cap = cv2.VideoCapture(str(mp4_f))
            if not cap.isOpened():
                continue
            fc = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
            for frac in (0.15, 0.50, 0.85):
                cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, int(fc * frac)))
                ok_f, frm = cap.read()
                if ok_f and frm is not None:
                    dh = _dhash_64(cv2.cvtColor(frm, cv2.COLOR_BGR2GRAY))
                    dist = min(_hamming_hex(dh, sdh) for sdh in source_dhashes)
                    min_clip_dhash = min(min_clip_dhash, dist)
            cap.release()
            checked_clip_count += 1

    overall_min_dhash = min(min_ref_dhash, min_clip_dhash)
    rq2_ok = bool(
        len(source_dhashes) > 0
        and (checked_ref_count > 0 or checked_clip_count > 0)
        and overall_min_dhash >= REENACT_MIN_DHASH_DISTANCE
    )

    # --- RQ3: 0.0% 5-gram transcript overlap & zero source personal names ---
    script_path = scr_dir / "script.json"
    s_doc = json.loads(script_path.read_text(encoding="utf-8")) if script_path.exists() else {}
    sents = [
        str(x)
        for x in (s_doc.get("sentences") or s_doc.get("clip_narrations") or s_doc.get("narrations") or [])
        if str(x).strip()
    ]
    script_text = " ".join(sents) or str(s_doc.get("full_script") or "")
    script_5grams = compute_5gram_sha256_set(script_text)
    src_5grams = set(edl_doc.get("source_5gram_sha256_list") or [])
    overlap_count = len(script_5grams & src_5grams)
    overlap_ratio = round(overlap_count / max(len(script_5grams), 1), 6)

    script_words = set(_normalize_words(script_text))
    banned_names = [str(n).lower() for n in (edl_doc.get("source_personal_names") or [])]
    leaked_names = [n for n in banned_names if n in script_words]
    rq3_ok = bool(
        bool(script_text.strip())
        and overlap_ratio <= REENACT_MAX_TRANSCRIPT_5GRAM_OVERLAP
        and len(leaked_names) == 0
    )

    # --- RQ4: Zero poster/cartoon/brand leak ---
    meta_path = pub_dir / "metadata.json"
    meta_blob = meta_path.read_text(encoding="utf-8") if meta_path.exists() else ""
    prompts_path = vis_dir / "flow_all_in_one_prompts.json"
    prompts_blob = prompts_path.read_text(encoding="utf-8") if prompts_path.exists() else ""
    combined_low = f"{script_text}\n{meta_blob}\n{prompts_blob}".lower()
    brand_hits = [tok for tok in BANNED_SOURCE_BRAND_TOKENS if tok in combined_low]
    rq4_ok = bool(edl_doc.get("sanitization_verified", False) and len(brand_hits) == 0)

    # --- RQ5: >= 20% original R66 4-color 3D brain / hstack cuts & >= 85% shot blocking alignment ---
    clips = list(vp.get("clips") or [])
    total_clips = len(clips)
    brain_or_split_clips = [
        c
        for c in clips
        if isinstance(c, dict)
        and (
            str(c.get("grammar") or "") in ("porcelain_living_brain", "porcelain_data_sculpture", "lowpoly_living_brain", "lowpoly_data_sculpture")
            or bool(c.get("brain_mode"))
            or str(c.get("split_mode") or "") == "hstack"
            or str(c.get("cut_role") or "") in ("split_comparison", "split_right", "split_bottom")
        )
    ]
    lab_clips = [
        c
        for c in clips
        if isinstance(c, dict)
        and c not in brain_or_split_clips
        and str(c.get("cut_role") or "").strip().lower() != "outro"
    ]
    brain_ratio = round(len(brain_or_split_clips) / max(total_clips, 1), 4)
    valid_shot_ids = {str(s.get("shot_id")) for s in (edl_doc.get("shots") or []) if s.get("shot_id")}
    mapped_lab = [
        c for c in lab_clips if str(c.get("source_shot_id") or "") in valid_shot_ids
    ]
    blocking_alignment_ratio = round(len(mapped_lab) / max(len(lab_clips), 1), 4) if lab_clips else 0.0
    style_ok = str(vp.get("style_profile") or "") == PORCELAIN_V7_STYLE_PROFILE
    assembled_edl_path = asm_dir / "edit_decision_list.json"
    edl_pacing_ok = True
    edl_min_cut_sec: float | None = None
    edl_max_cut_sec: float | None = None
    edl_avg_cut_sec: float | None = None
    if assembled_edl_path.exists():
        try:
            asm_edl = json.loads(assembled_edl_path.read_text(encoding="utf-8"))
            asm_durs = [float(c.get("duration_sec") or 0.0) for c in (asm_edl.get("cuts") or []) if isinstance(c, dict)]
            if asm_durs:
                edl_min_cut_sec = round(min(asm_durs), 4)
                edl_max_cut_sec = round(max(asm_durs), 4)
                edl_avg_cut_sec = round(float(np.mean(asm_durs)), 4)
                edl_pacing_ok = (
                    len(asm_durs) >= DIORAMA_TARGET_CUT_MIN
                    and edl_min_cut_sec >= PORCELAIN_V7_MIN_CUT_SEC - 1e-3
                    and edl_max_cut_sec <= PORCELAIN_V7_LONG_TAKE_MAX_SEC + 1e-3
                )
        except Exception:
            edl_pacing_ok = False
    rq5_ok = bool(
        DIORAMA_TARGET_CUT_MIN <= total_clips <= PORCELAIN_V7_TARGET_CLIP_MAX
        and edl_pacing_ok
        and style_ok
        and brain_ratio >= REENACT_BRAIN_RATIO_MIN
        and blocking_alignment_ratio >= REENACT_COMPOSITION_MATCH_MIN
    )

    gates = {
        "RQ1_zero_raw_source_leak": {
            "passed": rq1_ok,
            "leaked_files": leaked_files,
            "quarantine_purged": quarantine_clean,
        },
        "RQ2_perceptual_dhash_distance": {
            "passed": rq2_ok,
            "min_required_bits": REENACT_MIN_DHASH_DISTANCE,
            "min_reference_dhash_bits": min_ref_dhash if checked_ref_count else None,
            "min_clip_dhash_bits": min_clip_dhash if checked_clip_count else None,
            "checked_reference_images": checked_ref_count,
            "checked_native_clips": checked_clip_count,
        },
        "RQ3_zero_transcript_and_name_overlap": {
            "passed": rq3_ok,
            "overlap_5gram_ratio": overlap_ratio,
            "overlap_5gram_count": overlap_count,
            "leaked_personal_names": leaked_names,
        },
        "RQ4_zero_poster_or_brand_leak": {
            "passed": rq4_ok,
            "sanitization_verified": bool(edl_doc.get("sanitization_verified", False)),
            "brand_token_hits": brand_hits,
        },
        "RQ5_brain_intercut_and_blocking_alignment": {
            "passed": rq5_ok,
            "style_profile": vp.get("style_profile"),
            "total_clips": total_clips,
            "min_clips_required": DIORAMA_TARGET_CUT_MIN,
            "max_clips_allowed": PORCELAIN_V7_TARGET_CLIP_MAX,
            "edl_pacing_ok": edl_pacing_ok,
            "edl_min_cut_sec": edl_min_cut_sec,
            "edl_max_cut_sec": edl_max_cut_sec,
            "edl_avg_cut_sec": edl_avg_cut_sec,
            "brain_or_split_clip_count": len(brain_or_split_clips),
            "brain_ratio": brain_ratio,
            "min_brain_ratio_required": REENACT_BRAIN_RATIO_MIN,
            "target_lab_ratio": REENACT_LAB_RATIO_TARGET,
            "blocking_alignment_ratio": blocking_alignment_ratio,
            "min_blocking_alignment_required": REENACT_COMPOSITION_MATCH_MIN,
        },
    }
    failed_gates = [k for k, v in gates.items() if not v["passed"]]
    report = {
        "schema": "reenactment_qa_report_v1",
        "rule": "R67",
        "project_id": p_dir.name,
        "slug": slug,
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "passed": len(failed_gates) == 0,
        "failed_gates": failed_gates,
        "gates": gates,
    }
    if save_report:
        from pipeline.storage import ProjectStorage

        asm_dir.mkdir(parents=True, exist_ok=True)
        out_rep = asm_dir / REENACT_QA_REPORT_FILENAME
        out_rep.write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        ProjectStorage.record_if_manifest_tracks_stages(p_dir, "05_assembly", REENACT_QA_REPORT_FILENAME, out_rep)
    return report
