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
      Uses native Google Flow `0-credit` `Image` mode (`Nano Banana 2.1`, `x1` first-pass / `x2` retry per prompt,
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
    FLOW_ZERO_CREDIT_IMAGE_FALLBACK_MODELS,
    FLOW_ZERO_CREDIT_IMAGE_RETRY_BATCH_COUNT,
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
    resolve_flow_image_batch_count,
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


def extract_dq8_scene_roi(frame_bgr: np.ndarray, *, is_expressive_v8: bool = False) -> np.ndarray:
    """
    Canonical DQ8 / pre-assembly clip-gate scene ROI shared 1:1 between `inspect_diorama_clip_cv`
    and post-assembly `verify_final_mp4_against_contract` so native `720x1280` Flow clips and
    assembled `1080x1920` cuts are evaluated at identical resolution and framing.
    """
    if frame_bgr is None or frame_bgr.size == 0:
        return frame_bgr
    work = frame_bgr
    h, w = work.shape[:2]
    if is_expressive_v8:
        # Normalize vertical 9:16 native 720p clips to 1080x1920 so YuNet & top-edge `by <= 12` invariants match DQ8 1:1
        if h > w and w >= 480 and (w != 1080 or h != 1920):
            work = cv2.resize(work, (1080, 1920), interpolation=cv2.INTER_LINEAR)
            h, w = 1920, 1080
        return work[0 : max(1, int(h * 0.94)), int(w * 0.02) : max(1, int(w * 0.98))]
    return work[int(h * 0.10) : max(1, int(h * 0.92)), int(w * 0.04) : max(1, int(w * 0.96))]


def detect_non_porcelain_human_faces_yunet(
    bgr: np.ndarray,
    score_threshold: float = 0.62,
    allow_expressive_2d_ink: bool = False,
) -> list[tuple[int, int, int, int, float]]:
    """
    Detects real human faces (both color photorealistic flesh faces and B&W archival faces with eyes/mouth)
    via YuNet while excluding smooth featureless matte-white porcelain mannequin heads (`porcelain_r >= 0.82`),
    matte-white 2.5D vinyl heads with bold charcoal 2D ink features (`allow_expressive_2d_ink=True`),
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
        vinyl_white_ratio = float(np.mean((hsv[:, :, 1] <= 68) & (hsv[:, :, 2] >= 120)))
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
        # Pure near-black monitor/shadow false positive (no lit facial surface at all) -> not a human face
        if float(np.mean(hsv[:, :, 2] < 68)) >= 0.88 and skin_ratio <= 0.03:
            continue
        # Matte-white / warm-cinema cream-white 2.5D vinyl head with bold 2D charcoal ink facial lines (expressive_25d_v8) -> not a human face
        if allow_expressive_2d_ink:
            head_roi = crop[
                max(0, int(ch * 0.18)) : max(1, int(ch * 0.68)),
                max(0, int(cw * 0.18)) : max(1, int(cw * 0.82)),
            ]
            if head_roi.size == 0:
                head_roi = inner
            f_hsv = cv2.cvtColor(head_roi, cv2.COLOR_BGR2HSV)
            f_ycc = cv2.cvtColor(head_roi, cv2.COLOR_BGR2YCrCb)
            non_ink = f_hsv[:, :, 2] >= 72
            non_ink_frac = float(np.mean(non_ink))
            ink_ratio = float(np.mean(f_hsv[:, :, 2] < 68))
            head_lap_var = float(cv2.Laplacian(cv2.cvtColor(head_roi, cv2.COLOR_BGR2GRAY), cv2.CV_64F).var())
            if non_ink_frac < 0.14 and (skin_ratio <= 0.04 or (non_ink_frac < 0.10 and head_lap_var < 12.0 and sc < 0.68)):
                continue
            if non_ink_frac >= 0.14:
                base_h_med = float(np.median(f_hsv[:, :, 0][non_ink]))
                base_v_med = float(np.median(f_hsv[:, :, 2][non_ink]))
                base_cr_med = float(np.median(f_ycc[:, :, 1][non_ink]))
                base_cb_med = float(np.median(f_ycc[:, :, 2][non_ink]))
                s_p95 = float(np.percentile(f_hsv[:, :, 1], 95))
                head_porc_ratio = float(np.mean((f_hsv[:, :, 1] <= 58) & (f_hsv[:, :, 2] >= 150)))
                eye_band = crop[
                    max(0, int(ch * 0.15)) : max(1, int(ch * 0.55)),
                    max(0, int(cw * 0.15)) : max(1, int(cw * 0.85)),
                ]
                ehsv = cv2.cvtColor(eye_band, cv2.COLOR_BGR2HSV) if eye_band.size > 0 else f_hsv
                cartoon_sclera = float(np.mean((ehsv[:, :, 1] <= 40) & (ehsv[:, :, 2] >= 200)))
                cartoon_ink = float(np.mean(ehsv[:, :, 2] <= 58))
                is_grayscale_archival = (s_p95 < 10.0) and (max(porc_ratio, head_porc_ratio) < 0.65)
                is_cool_lit_human = (base_cr_med < 127.0) or (base_cb_med > 128.5)
                has_giant_cartoon_eyes = (
                    cartoon_sclera >= 0.065
                    and cartoon_ink >= 0.085
                    and (max(porc_ratio, head_porc_ratio) >= 0.10 or vinyl_white_ratio >= 0.18)
                )
                is_warm_lamp_vinyl = (
                    base_v_med >= 205.0
                    and base_h_med >= 15.0
                    and base_cb_med <= 104.0
                    and base_cr_med <= 154.0
                    and ink_ratio >= 0.08
                )
                is_top_clipped_bokeh_doll = (
                    by <= 12
                    and bh_b < int(bw_b * 0.92)
                    and head_lap_var < 26.0
                    and base_cr_med <= 149.5
                )
                is_closed_eye_matte_vinyl = (
                    vinyl_white_ratio >= 0.35
                    and base_v_med >= 195.0
                    and base_cr_med <= 145.2
                    and ink_ratio >= 0.015
                )
                fh_roi = crop[: max(1, int(ch * 0.32)), int(cw * 0.15) : max(1, int(cw * 0.85))]
                fh_hsv = cv2.cvtColor(fh_roi, cv2.COLOR_BGR2HSV) if fh_roi.size > 0 else f_hsv
                forehead_vw = float(np.mean((fh_hsv[:, :, 1] <= 68) & (fh_hsv[:, :, 2] >= 125)))
                ck_roi = crop[
                    int(ch * 0.40) : max(int(ch * 0.42), int(ch * 0.62)),
                    int(cw * 0.18) : max(1, int(cw * 0.82)),
                ]
                is_capped_flesh_face = False
                if fh_roi.size > 0 and ck_roi.size > 0 and forehead_vw >= 0.12:
                    fh_ycc = cv2.cvtColor(fh_roi, cv2.COLOR_BGR2YCrCb)
                    ck_hsv = cv2.cvtColor(ck_roi, cv2.COLOR_BGR2HSV)
                    ck_ycc = cv2.cvtColor(ck_roi, cv2.COLOR_BGR2YCrCb)
                    ck_vw = float(np.mean((ck_hsv[:, :, 1] <= 48) & (ck_hsv[:, :, 2] >= 145)))
                    fh_non = fh_hsv[:, :, 2] >= 78
                    ck_non = ck_hsv[:, :, 2] >= 78
                    if ck_vw < 0.10 and np.any(fh_non) and np.any(ck_non):
                        fh_cr_med = float(np.median(fh_ycc[:, :, 1][fh_non]))
                        ck_cr_med = float(np.median(ck_ycc[:, :, 1][ck_non]))
                        ck_cb_med = float(np.median(ck_ycc[:, :, 2][ck_non]))
                        fh_s_med = float(np.median(fh_hsv[:, :, 1][fh_non]))
                        ck_s_med = float(np.median(ck_hsv[:, :, 1][ck_non]))
                        ck_h_med = float(np.median(ck_hsv[:, :, 0][ck_non]))
                        d_cr = ck_cr_med - fh_cr_med
                        if (
                            (d_cr >= 6.5 and ck_cr_med >= 141.0 and ck_h_med <= 13.5)
                            or (d_cr >= 12.0 and ck_cr_med >= 146.5)
                            or (ck_cb_med >= 136.0 and (ck_s_med - fh_s_med) >= 15.0)
                            or (ck_cb_med >= 126.0 and ck_h_med >= 95.0)
                        ):
                            is_capped_flesh_face = True
                is_bold_glasses_vinyl = (
                    ink_ratio >= 0.16
                    and (vinyl_white_ratio >= 0.12 or forehead_vw >= 0.30)
                    and base_v_med >= 135.0
                    and base_cr_med <= 148.0
                    and base_cb_med <= 118.0
                )
                is_featureless_matte_vinyl = (
                    (vinyl_white_ratio >= 0.14 or forehead_vw >= 0.20)
                    and base_v_med >= 145.0
                    and base_cr_med <= 145.2
                )
                is_shadowed_rim_vinyl = (
                    forehead_vw >= 0.09
                    and base_v_med >= 90.0
                    and base_cr_med <= 138.0
                    and ink_ratio >= 0.03
                )
                is_vinyl_25d = (
                    not is_grayscale_archival
                    and not is_cool_lit_human
                    and not is_capped_flesh_face
                    and (base_v_med >= 115.0 or is_shadowed_rim_vinyl)
                    and (
                        (base_cr_med <= 143.5 and ink_ratio >= 0.022)
                        or (base_cr_med <= 145.2 and (vinyl_white_ratio >= 0.10 or forehead_vw >= 0.30) and ink_ratio >= 0.022)
                        or (max(porc_ratio, head_porc_ratio) >= 0.40 and base_cr_med <= 141.0)
                        or has_giant_cartoon_eyes
                        or is_warm_lamp_vinyl
                        or is_top_clipped_bokeh_doll
                        or is_closed_eye_matte_vinyl
                        or is_bold_glasses_vinyl
                        or is_featureless_matte_vinyl
                        or is_shadowed_rim_vinyl
                    )
                )
                if is_vinyl_25d:
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
        ff_shim_dir = Path("/tmp/aab_ffmpeg_bin")
        ff_shim_dir.mkdir(parents=True, exist_ok=True)
        ff_shim = ff_shim_dir / "ffmpeg"
        if Path(ffmpeg_bin).exists() and not ff_shim.exists():
            try:
                ff_shim.symlink_to(Path(ffmpeg_bin).resolve())
            except OSError:
                pass
        ff_loc_dir = str(ff_shim_dir) if ff_shim.exists() else str(Path(ffmpeg_bin).parent)
        dl_target = (q_dir / "source_full.mp4") if sec_bounds is not None else src_mp4
        cmd = [
            yt_dlp_bin,
            "--ignore-errors",
            "--no-playlist",
            "--ffmpeg-location",
            ff_loc_dir,
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


def resolve_keyframe_conditioning_and_prompt(
    spec: dict[str, Any],
    plan: dict[str, Any],
    guides_dir: Path,
    ref_dir: Path,
) -> tuple[list[Path], str, bool]:
    """
    Resolves `<= 2` conditioning PNG paths (`[guide_or_previs_png, cast_or_style_sheet_png]`)
    and composes the Flow `Image` translation prompt, supporting both R67 sanitized structural
    guides AND Phase 5.5 3D Workbench Previs PNGs (`previs_guide_png` + `color_role_legend`).
    Returns `(cond_paths, full_prompt, has_structural_or_previs_guide)`.
    """
    from pipeline.config import (
        EXPRESSIVE_25D_V8_STYLE_PROFILE,
        PORCELAIN_V7_STYLE_PROFILE,
        PROMPT_SCHEMA_VERSION_V8,
        is_expressive_v8_plan,
    )
    from pipeline.previs_blender import format_previs_color_mapping_prompt

    cond_paths: list[Path] = []
    sc_id = str(spec.get("scene_id") or "")
    which = str(spec.get("frame") or "start")
    is_brain_setting = spec.get("setting") in (*BRAIN_SETTINGS, "brain_studio")

    # 1. Check explicit or directory-discovered 3D Previs PNG first, then Track A structural guide
    previs_cand: Path | None = None
    explicit_pv = str(spec.get("previs_guide_png") or "").strip()
    if explicit_pv:
        p_exp = Path(explicit_pv)
        if p_exp.is_file():
            previs_cand = p_exp
    if previs_cand is None and sc_id:
        for pv_name in (f"{sc_id}_{which}_previs.png", f"{sc_id}_start_previs.png"):
            cand_pv = guides_dir / pv_name
            if cand_pv.is_file():
                previs_cand = cand_pv
                break

    is_previs_guide = False
    guide_cand = guides_dir / f"{sc_id}_{which}_guide.png"
    if not guide_cand.exists() and sc_id.startswith("S"):
        guide_cand = guides_dir / f"{sc_id}_start_guide.png"

    if previs_cand is not None and not is_brain_setting and not bool(spec.get("skip_structural_guide")):
        cond_paths.append(previs_cand)
        is_previs_guide = True
    elif guide_cand.exists() and not is_brain_setting and not bool(spec.get("skip_structural_guide")):
        cond_paths.append(guide_cand)

    has_guide_cond = len(cond_paths) > 0

    raw_cond_ids = [str(c) for c in (spec.get("conditioned_on") or []) if str(c).strip()]
    if has_guide_cond:
        # Pair [guide_or_previs_png, character_sheet] strictly <= 2 attachments
        preferred_cast = [
            c for c in raw_cond_ids if c.startswith(("ref_cast_", "species_opt1", "ref_turnaround"))
        ]
        others = [c for c in raw_cond_ids if c not in preferred_cast]
        raw_cond_ids = preferred_cast + others

    is_v8_anchor = is_expressive_v8_plan(plan) or str(spec.get("style_profile") or "") == EXPRESSIVE_25D_V8_STYLE_PROFILE
    if is_v8_anchor:
        spec.setdefault("style_profile", EXPRESSIVE_25D_V8_STYLE_PROFILE)
        spec.setdefault("schema_version", PROMPT_SCHEMA_VERSION_V8)

    # Rule R72-R: Resolve quarantined Wikimedia real-world structural guide if tagged on spec
    real_guide_cand: Path | None = None
    rw_tid = str(spec.get("real_world_target_id") or "").strip()
    r72_stage = str(spec.get("r72_relay_stage") or "").strip().upper()
    if rw_tid and not is_brain_setting:
        from pipeline.real_world_reference_builder import resolve_quarantined_real_guide_path

        proj_name = ref_dir.parent.parent.name if ref_dir.parent.name == "03_visuals" else str((plan or {}).get("project_id") or "")
        if proj_name:
            real_guide_cand = resolve_quarantined_real_guide_path(proj_name, rw_tid)

    r74_stage = str(spec.get("r74_relay_stage") or "").strip().upper()
    is_r85_brain = bool(spec.get("r85_brain_clip"))
    explicit_canonical_slot = str(spec.get("canonical_slot_id") or "").strip()
    # For R85 Ep #31 6-Scale Brain & canonical-bound anchors: slot #1 = approved SHA-locked canonical_assets/v1 slot (or Start frame for End specs), slot #2 = offscreen cutaway/MNI152 guide
    if is_r85_brain or explicit_canonical_slot:
        from pipeline.canonical_assets import (
            CanonicalAssetError,
            is_retired_derivative_anchor,
            resolve_canonical_approved_slot,
            select_canonical_brain_slot,
            stage_canonical_slot_to_project,
        )

        for bad_c in raw_cond_ids:
            if is_retired_derivative_anchor(bad_c):
                raise CanonicalAssetError(
                    f"Keyframe '{spec.get('ref_id')}' conditioned_on retired derivative anchor '{bad_c}'"
                )

        cond_paths.clear()
        is_previs_guide = False
        p_dir_can = ref_dir.parent.parent if ref_dir.parent.name == "03_visuals" else None

        # Preserve Start->End keyframe chaining when generating an End keyframe conditioned on its Start keyframe in ref_dir
        if str(spec.get("frame") or "").strip().lower() == "end" and raw_cond_ids:
            first_c = str(raw_cond_ids[0]).strip()
            first_fn = first_c if first_c.lower().endswith((".png", ".jpg", ".jpeg")) else f"{first_c}.png"
            start_cand_p = ref_dir / first_fn
            if start_cand_p.is_file() and not is_retired_derivative_anchor(first_fn):
                cond_paths.append(start_cand_p)

        if not cond_paths:
            slot_to_use = explicit_canonical_slot or select_canonical_brain_slot(
                brain_region=str(spec.get("brain_region") or ""),
                viewpoint=str(spec.get("viewpoint") or ""),
                mode=str(spec.get("r85_brain_mode") or ""),
                shot_scale=str(spec.get("r85_shot_scale") or ""),
                neural_state=str(spec.get("neural_state") or ""),
                side_by_side=bool(spec.get("side_by_side_brain_compare")),
            )
            slot_frame = str(spec.get("canonical_slot_frame") or "single").strip().lower()
            if p_dir_can is not None and p_dir_can.is_dir():
                staged_can = stage_canonical_slot_to_project(
                    p_dir_can,
                    slot_to_use,
                    version="auto",
                    frame=slot_frame,
                )
                cond_paths.append(Path(staged_can["staged_path"]))
            else:
                res_can = resolve_canonical_approved_slot(
                    slot_to_use,
                    version="auto",
                    frame=slot_frame,
                    verify_sha256=True,
                )
                cond_paths.append(Path(res_can["abs_path"]))

        proj_name_r85 = ref_dir.parent.parent.name if ref_dir.parent.name == "03_visuals" else str((plan or {}).get("project_id") or "")
        runtime_guide_entry: dict[str, Any] = {}
        if proj_name_r85:
            rt_map_p = Path(f"/tmp/aab_real_refs/{proj_name_r85}/r85_brain_guide_map.json")
            if rt_map_p.is_file():
                try:
                    runtime_guide_entry = (json.loads(rt_map_p.read_text(encoding="utf-8")) or {}).get(str(spec.get("ref_id") or ""), {})
                except Exception:
                    runtime_guide_entry = {}
        for g_key in ("structural_guide_path", "mni152_offscreen_guide"):
            g_raw = str(spec.get(g_key) or runtime_guide_entry.get(g_key) or "").strip()
            if g_raw and len(cond_paths) < 2:
                gp = Path(g_raw)
                if gp.is_file() and gp not in cond_paths:
                    cond_paths.append(gp)
                    has_guide_cond = True
                    break
        if len(cond_paths) < 2 and is_r85_brain:
            # Optional secondary local or canonical reference (never retired derivative)
            for cond_id in raw_cond_ids:
                if len(cond_paths) >= 2:
                    break
                cname = cond_id if cond_id.lower().endswith((".png", ".jpg", ".jpeg")) else f"{cond_id}.png"
                cand_p = ref_dir / cname
                if cand_p.is_file() and cand_p not in cond_paths and not is_retired_derivative_anchor(cname):
                    cond_paths.append(cand_p)
    # For K1/K2 relay stages or R74 B1 macro neural anchors, resolve conditioned_on (K0/K1 or B0 in ref_dir) FIRST!
    elif r72_stage in ("K1", "K2") or r74_stage == "B1":
        cond_paths.clear()
        is_previs_guide = False
        for cond_id in raw_cond_ids:
            if len(cond_paths) >= 2:
                break
            cname = cond_id if cond_id.lower().endswith((".png", ".jpg", ".jpeg")) else f"{cond_id}.png"
            cand_p = ref_dir / cname
            if cand_p.exists() and cand_p not in cond_paths:
                cond_paths.append(cand_p)
        if real_guide_cand is not None and len(cond_paths) < 2 and real_guide_cand not in cond_paths:
            cond_paths.append(real_guide_cand)
        if previs_cand is not None and len(cond_paths) < 2 and previs_cand not in cond_paths:
            cond_paths.append(previs_cand)
    else:
        if real_guide_cand is not None and not bool(spec.get("skip_structural_guide")):
            # Real-world guide takes primary slot #1; previs or character sheet takes slot #2
            cond_paths = [real_guide_cand] + [p for p in cond_paths if p != real_guide_cand][:1]
            is_previs_guide = False
            has_guide_cond = True
        for cond_id in raw_cond_ids:
            if len(cond_paths) >= 2:
                break
            cname = cond_id if cond_id.lower().endswith((".png", ".jpg", ".jpeg")) else f"{cond_id}.png"
            cand_p = ref_dir / cname
            if cand_p.exists() and cand_p not in cond_paths:
                cond_paths.append(cand_p)

    base_prompt = str(spec.get("prompt") or "")
    allow_toks = [str(t).strip() for t in (spec.get("diegetic_text_allowlist") or []) if str(t).strip()]
    cast_suffix = ""
    if spec.get("present_cast") is not None and not is_brain_setting:
        p_list = [str(x).strip() for x in (spec.get("present_cast") or []) if str(x).strip()]
        if len(p_list) == 0:
            if real_guide_cand is not None or r72_stage in ("K0", "K1"):
                cast_suffix += " No close-up foreground portrait figures block the architecture."
            else:
                cast_suffix += " The room and all chairs are completely empty with zero figures present."
        elif is_v8_anchor:
            cast_suffix += f" Present in frame: {', '.join(p_list)}."
        else:
            cast_suffix += f" Exactly {len(p_list)} clothed matte-white porcelain figure(s) appear in the frame ({', '.join(p_list)})."
    if spec.get("empty_chairs_note"):
        cast_suffix += f" {str(spec['empty_chairs_note']).strip()}"
    if "no text" not in base_prompt.lower() and "zero text" not in base_prompt.lower():
        if allow_toks:
            q_allow = ", ".join(f"'{t}'" for t in allow_toks[:2])
            cast_suffix += f" Crisp physical prop stencil displays {q_allow} only; zero other text, letters, or watermarks."
        else:
            cast_suffix += " Strictly zero text, zero letters, zero numbers, zero labels, no watermark."

    if is_r85_brain:
        from pipeline.config import R85_BRAIN_ANTI_VFX_NEGATIVE_CLAUSE

        r85_mode_lead = str(spec.get("r85_brain_mode") or "").strip().lower()
        r85_scale_lead = str(spec.get("r85_shot_scale") or "").strip().lower()
        if r85_mode_lead == "mode1_xray_translucent_head" or r85_scale_lead == "xray_head_dive":
            brain_cond_lead = (
                "Vertical 9:16 full-bleed 3D neuroanatomy render in genuine Episode #31 Mode 1 X-Ray style over solid flat dark navy void (#040711), "
                "large hero framing filling 85% to 92% of the horizontal 9:16 width. "
                "Match the smooth bright pearl-gray glossy mannequin head-and-shoulders bust (#C4CBD2 to #E4E8EC, never dark or black glass) and clear "
                "see-through transparent upper glass cranium cleanly enclosing the full interior almost-white matte gypsum-plaster 3D brain (#DCDFE3 to "
                "#F0F3F6) with an organic tree-like branching network of thick opaque sky-blue (#27D8FF) 3D blood-vessel tubes spreading naturally over "
                "the brain surface (never outlining every sulcal groove) from the first reference image. "
            )
        else:
            guide_clause = (
                "while following the exact surgical cutaway viewpoint and anatomical position of the second reference guide (render zero text, zero pointer lines, zero labels). "
                if len(cond_paths) >= 2
                else "in clean hero full-bleed 3D neuroanatomical perspective filling 85% to 92% of the horizontal 9:16 width. "
            )
            brain_cond_lead = (
                "Vertical 9:16 full-bleed 3D neuroanatomy render in genuine Episode #31 Mode 2 style over solid flat dark navy void (#040711), "
                "large hero framing filling 85% to 92% of the horizontal 9:16 width under unified bright top-left 45-degree studio keylight. "
                "Match the almost-white bright cool matte sculpted gypsum-plaster cortical gyri (#DCDFE3 to #F0F3F6, ultra-low saturation matte chalk "
                "texture, strictly zero blue steel tint, zero wet cortical gloss) and the organic tree-like branching network of thick round opaque sky-blue "
                "(#27D8FF to #58E4FF) 3D cylindrical blood-vessel tubes with crisp glossy rim highlights spreading naturally OVER the cortical surface "
                f"(never outlining or tracing every sulcal fold like a contour wireframe) from the first reference image, {guide_clause}"
            )
        anti_vfx_tail = (
            ""
            if R85_BRAIN_ANTI_VFX_NEGATIVE_CLAUSE.lower() in base_prompt.lower()
            else f" {R85_BRAIN_ANTI_VFX_NEGATIVE_CLAUSE}."
        )
        full_prompt = f"{brain_cond_lead}{base_prompt}{cast_suffix}{anti_vfx_tail}"
    elif is_brain_setting and (is_v8_anchor or r74_stage in ("B0", "B1")):
        brain_cond_lead = (
            "Vertical 9:16 full-bleed medical-grade 3D translucent borosilicate crystal-glass neuroanatomy photograph in a deep midnight-navy chamber (#050811). "
            "Preserve the exact frosted borosilicate crystal-glass cortical surface refraction and 4-color optical-glass internal glow from the primary brain reference image "
            + (
                "while zooming deep inside the parted glass cortical ribs to match the close-up macro subcortical framing of the 3D layout guide (replace any solid matte previs marker sphere with luminous sculpted optical glass). "
                if r74_stage == "B1"
                else "in clean full-brain 3D perspective. "
            )
        )
        full_prompt = f"{brain_cond_lead}{base_prompt}{cast_suffix}"
    elif is_previs_guide:
        eff_legend = spec.get("color_role_legend")
        if not eff_legend and isinstance(plan, dict):
            c_idx_pv = int(spec.get("clip_number") or 0)
            p_clips_pv = plan.get("clips") if isinstance(plan.get("clips"), list) else []
            if 1 <= c_idx_pv <= len(p_clips_pv) and isinstance(p_clips_pv[c_idx_pv - 1], dict):
                pv_d = p_clips_pv[c_idx_pv - 1].get("previs")
                if isinstance(pv_d, dict) and pv_d.get("color_role_legend"):
                    eff_legend = pv_d["color_role_legend"]
            if not eff_legend and sc_id:
                for cp_it in p_clips_pv:
                    if isinstance(cp_it, dict) and str(cp_it.get("scene_id") or "") == sc_id:
                        pv_d = cp_it.get("previs")
                        if isinstance(pv_d, dict) and pv_d.get("color_role_legend"):
                            eff_legend = pv_d["color_role_legend"]
                            break
        pv_lead = format_previs_color_mapping_prompt(
            eff_legend,
            style_profile=EXPRESSIVE_25D_V8_STYLE_PROFILE if is_v8_anchor else PORCELAIN_V7_STYLE_PROFILE,
            has_character_sheet=(len(cond_paths) >= 2),
        )
        full_prompt = f"{pv_lead} {base_prompt}{cast_suffix}".strip()
    elif is_v8_anchor and (real_guide_cand is not None or r72_stage in ("K0", "K1", "K2")):
        if r72_stage == "K2":
            arch_lead = (
                "Vertical 9:16 full-bleed stylized 3D architectural cutaway miniature diorama photograph. "
                "Preserve the exact exterior building architecture from the first reference image while slicing open "
                "a clean geometric section of the front facade wall to reveal the warm illuminated interior laboratory. "
            )
        else:
            arch_lead = (
                "Vertical 9:16 full-bleed stylized 3D cinematic miniature diorama photograph. "
                "Match the real-world architectural silhouette, roof/dome profile, column/window rhythm, and masonry/prop "
                "palette of the reference guide while rendering every surface from scratch in tactile miniature 3D materials. "
            )
        full_prompt = f"{arch_lead}{base_prompt}{cast_suffix}"
    elif is_v8_anchor:
        from pipeline.config import is_r88_faceless_cast_plan

        is_r88 = is_r88_faceless_cast_plan(plan) or bool(spec.get("r88_mode"))
        is_zero_people_spec = (
            spec.get("present_cast") == []
            or "zero people" in base_prompt.lower()
            or "zero figures" in base_prompt.lower()
        )
        if cond_paths:
            if is_zero_people_spec:
                cond_lead = (
                    "Match the warm miniature 3D lighting, oak/ceramic material palette, and clean tabletop composition "
                    "of the reference image with strictly zero people, zero dolls, zero mannequins, and zero hands in frame. "
                )
            elif is_r88:
                cond_lead = (
                    "Match the R88 faceless architectural porcelain diorama aesthetic of the reference image "
                    "(smooth featureless matte-white #F5F2EB architectural porcelain figure with a pure smooth blank "
                    "unprinted oval head silhouette, four-fingered matte-white porcelain hands, tailored 3D matte woven clothing). "
                )
            else:
                cond_lead = (
                    "Match the exact 2.5D character species from the reference sheet (smooth earless noseless hairless matte cream-white vinyl oval head, bold charcoal-black 2D cartoon ink eyes eyebrows and mouth, four-fingered matte cream-white vinyl hands, tailored 3D woven fabric clothing). "
                )
        else:
            cond_lead = ""
        full_prompt = (
            f"Vertical 9:16 full-bleed stylized 3D cinematic miniature diorama photograph. {cond_lead}{base_prompt}{cast_suffix}"
        )
    elif has_guide_cond:
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
            if (spec.get("present_cast") and not is_brain_setting)
            else ""
        )
        full_prompt = (
            f"Vertical 9:16 portrait aspect ratio (tall vertical frame, full-bleed high-key studio daylight{cast_head_lock}). {base_prompt}{cast_suffix}"
        )

    return cond_paths[:2], full_prompt, has_guide_cond


async def translate_porcelain_keyframes_async(
    project_dir: Path,
    slug: str,
    work_dir: Path | None = None,
    cdp_port: int = 9222,
    only_ref_ids: set[str] | None = None,
    force: bool = False,
    backend: str = DEFAULT_REENACT_IMAGE_BACKEND,
    batch_count: int | None = None,
    retry_batch_count: int = FLOW_ZERO_CREDIT_IMAGE_RETRY_BATCH_COUNT,
) -> dict[str, Any]:
    """
    Stage 3: Synthesizes `porcelain_cinematic_v7` master anchors + shot start/end reference keyframes
    exclusively inside Google Flow `0-credit` `Image` mode (`Nano Banana 2.1`, `x1` first-pass / `x2` retry per prompt,
    auto-selecting the highest-scoring `Q1..Q7` + `RQ2 dHash >= 18` candidate), conditioning lab keyframes
    on `(sanitized_guide.png, ref_cast_or_env.png)` (`<= 2` ingredients).
    """
    from pipeline.flow_ingredients import generate_flow_image_batch
    from pipeline.flow_live_single_worker import allocate_dedicated_flow_project_tab
    from pipeline.flow_prompt_builder import load_visual_plan
    from pipeline.reference_image_qa import load_provenance

    eff_backend = str(backend or DEFAULT_REENACT_IMAGE_BACKEND).strip().lower()
    if eff_backend not in REENACT_IMAGE_BACKENDS:
        raise ValueError(
            f"Unsupported reenactment image backend: {backend!r} (expected one of {REENACT_IMAGE_BACKENDS})"
        )
    first_pass_batch = resolve_flow_image_batch_count(
        batch_count,
        is_retry=False,
        force=force,
        retry_batch_count=retry_batch_count,
    )
    eff_retry_batch = resolve_flow_image_batch_count(
        batch_count,
        is_retry=True,
        force=force,
        retry_batch_count=retry_batch_count,
    )

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
    from pipeline.config import REAL_WORLD_REFS_MANIFEST_FILENAME
    rw_manifest_path = vis_dir / REAL_WORLD_REFS_MANIFEST_FILENAME
    if rw_manifest_path.exists():
        try:
            rw_doc = json.loads(rw_manifest_path.read_text(encoding="utf-8"))
            for rdh in rw_doc.get("raw_dhash64_list") or []:
                if str(rdh).strip() and str(rdh).strip() not in source_dhashes:
                    source_dhashes.append(str(rdh).strip())
        except Exception:
            pass

    q_dir = Path(work_dir) if work_dir else (REENACT_QUARANTINE_ROOT / slug)
    guides_dir = q_dir / "guides"

    import urllib.request
    from pipeline.studio.whale_session import DirectCDPClient

    ordered_specs = sorted(specs_payload.get("all_specs") or [], key=lambda s: int(s.get("generation_order") or 3))
    generated: list[str] = []
    failed: list[str] = []

    opened_tab_id: str | None = None
    opened_lease_owner: str | None = None
    opened_project_urls: list[str] = []
    ws_url: str | None = None
    uploaded_cache: set[str] = set()
    seen_img_srcs: set[str] = set()
    existing_prov = load_provenance(p_dir)

    from pipeline.cdp_tab_lease import enable_background_focus_emulation, release_and_close_leased_tab
    from pipeline.config import (
        EXPRESSIVE_25D_V8_STYLE_PROFILE,
        FLOW_AUTO_CLEANUP_ON_SUCCESS,
        PROMPT_SCHEMA_VERSION_V8,
        is_expressive_v8_plan,
    )
    from pipeline.flow_workspace import (
        clean_flow_workspace_async,
        format_flow_room_name,
        rename_active_flow_project,
    )

    def _close_dedicated_worker_tab(tid: str | None, owner_id: str | None = None) -> None:
        if not tid:
            return
        release_and_close_leased_tab(tid, owner_id=owner_id, cdp_port=cdp_port)

    unusual_activity_halted = False
    halt_reason = ""
    try:
        client_cm = None
        client: DirectCDPClient | None = None
        fallback_models = list(FLOW_ZERO_CREDIT_IMAGE_FALLBACK_MODELS)
        rl_models: set[str] = set()
        for idx_sp, spec in enumerate(ordered_specs, start=1):
            ref_id = str(spec["ref_id"])
            if only_ref_ids and ref_id not in only_ref_ids:
                continue
            if unusual_activity_halted or not [m for m in fallback_models if m not in rl_models]:
                failed.append(ref_id)
                continue
            out_png = ref_dir / str(spec["filename"])
            if out_png.exists() and not force:
                q_chk = inspect_single_reference_image(out_png, spec)
                min_dh = min((_hamming_hex(q_chk.get("dhash_64", ""), sdh) for sdh in source_dhashes), default=64)
                if q_chk.get("passed") and min_dh >= REENACT_MIN_DHASH_DISTANCE:
                    if existing_prov.get(out_png.name) != "flow_image_generation":
                        register_reference_image(p_dir, out_png.name, "flow_image_generation")
                    generated.append(ref_id)
                    print(f"[reenact-refs {idx_sp}/{len(ordered_specs)}] {ref_id}: cached_ok (dHash_min={min_dh})", flush=True)
                    continue

            sc_id = str(spec.get("scene_id") or "")
            which = str(spec.get("frame") or "start")
            guide_cand = guides_dir / f"{sc_id}_{which}_guide.png"
            if not guide_cand.exists() and sc_id.startswith("S"):
                guide_cand = guides_dir / f"{sc_id}_start_guide.png"
            is_v8_anchor = is_expressive_v8_plan(plan) or str(spec.get("style_profile") or "") == EXPRESSIVE_25D_V8_STYLE_PROFILE
            cond_paths, full_prompt, has_guide_cond = resolve_keyframe_conditioning_and_prompt(
                spec=spec,
                plan=plan,
                guides_dir=guides_dir,
                ref_dir=ref_dir,
            )
            has_guide_cond = bool(has_guide_cond or (guide_cand in cond_paths))

            ok_this = False
            for attempt in range(3):
                avail_models = [m for m in fallback_models if m not in rl_models]
                if unusual_activity_halted or not avail_models:
                    print(
                        f"[reenact-refs {idx_sp}/{len(ordered_specs)}] ABORTING remaining batch: "
                        f"{halt_reason or f'all official 0-credit Flow image models ({fallback_models}) hit usage limit!'}",
                        flush=True,
                    )
                    break
                active_img_model = avail_models[0]
                attempt_batch = resolve_flow_image_batch_count(
                    batch_count,
                    is_retry=(attempt > 0),
                    force=force,
                    retry_batch_count=retry_batch_count,
                )
                try:
                    if client is None:
                        import inspect as _inspect_sr
                        _sr_sig = _inspect_sr.signature(allocate_dedicated_flow_project_tab)
                        _sr_kwargs: dict[str, Any] = {"cdp_port": cdp_port}
                        if "project_id" in _sr_sig.parameters:
                            _sr_kwargs["project_id"] = p_dir.name
                        if "existing_project_url" in _sr_sig.parameters and opened_project_urls:
                            _sr_kwargs["existing_project_url"] = opened_project_urls[0]
                        flow_alloc = await allocate_dedicated_flow_project_tab(**_sr_kwargs)
                        opened_tab_id = str(flow_alloc["tab_id"])
                        opened_lease_owner = flow_alloc.get("lease_owner_id")
                        proj_u = str(flow_alloc.get("project_url") or "")
                        if proj_u and proj_u not in opened_project_urls:
                            opened_project_urls.append(proj_u)
                        ws_url = str(flow_alloc["ws_url"])
                        client_cm = DirectCDPClient(ws_url)
                        client = await client_cm.__aenter__()
                        await enable_background_focus_emulation(client)
                        await client.send("Page.enable")
                        await rename_active_flow_project(client, format_flow_room_name(p_dir.name, role="episode"))
                        uploaded_cache.clear()
                        seen_img_srcs.clear()

                    if attempt == 0:
                        retry_suffix = ""
                    elif bool(spec.get("r85_brain_clip")):
                        retry_suffix = (
                            " Ensure full-bleed 9:16 genuine Episode #31 almost-white matte gypsum-plaster 3D brain (#DCDFE3-#ECEFF2, ultra-low saturation, zero blue tint) "
                            "with thick opaque sky-blue (#27D8FF) cylindrical tubes tucked inside sulcal grooves over solid flat #040711 dark navy void, "
                            "zero glow, zero neon, zero particles, zero sparks, zero light beams, zero smoke, zero human skin, zero text, and zero labels."
                        )
                    elif is_v8_anchor and (spec.get("category") == "brain_anchor" or spec.get("r74_relay_stage")):
                        retry_suffix = (
                            " Ensure full-bleed 9:16 vertical 3D translucent borosilicate crystal-glass neuroanatomy framing "
                            "in a deep midnight-navy chamber (#050811) with luminous sculpted optical-glass subcortical structures, "
                            "zero mannequin head, zero face, zero wet biological tissue, and zero text."
                        )
                    elif is_v8_anchor and (spec.get("real_world_target_id") or spec.get("r72_relay_stage")):
                        retry_suffix = (
                            " Ensure full-bleed 9:16 vertical miniature architectural framing, crisp sunlit daylight "
                            "and tactile 3D brick/stone/timber texture, zero human faces, zero text, and zero watermarks."
                        )
                    elif is_v8_anchor:
                        from pipeline.config import is_r88_faceless_cast_plan

                        _sp_prompt_low = str(spec.get("prompt") or "").lower()
                        _sp_zero_people = (
                            (spec.get("present_cast") == [])
                            or ("zero people" in _sp_prompt_low)
                            or ("zero figures" in _sp_prompt_low)
                        )
                        if _sp_zero_people:
                            retry_suffix = (
                                " Ensure full-bleed 9:16 vertical miniature tabletop framing, crisp natural daylight, "
                                "tactile 3D ceramic/wood/glass materials, and strictly zero people, zero dolls, zero hands, zero text, and zero numbers."
                            )
                        elif is_r88_faceless_cast_plan(plan) or bool(spec.get("r88_mode")):
                            retry_suffix = (
                                " Ensure full-bleed 9:16 vertical R88 faceless architectural porcelain framing, "
                                "crisp cinema key-and-rim miniature lighting, smooth featureless matte-white architectural "
                                "porcelain oval head silhouette (pure smooth blank surface), and tailored 3D matte woven fabric clothing."
                            )
                        else:
                            retry_suffix = (
                                " Ensure full-bleed 9:16 vertical framing, crisp cinema key-and-rim miniature lighting, "
                                "smooth earless noseless matte cream-white vinyl oval head with bold black 2D cartoon ink eyes and mouth, "
                                "and tailored 3D woven fabric clothing."
                            )
                    else:
                        retry_suffix = (
                            " Ensure bright high-key daylight studio exposure, razor-sharp f/8 deep architectural focus "
                            "from foreground to background (zero shallow portrait bokeh blur), crisp woven fabric texture "
                            "and articulated porcelain joint seams, smooth matte-white porcelain heads, and full-bleed 9:16 vertical composition."
                        )
                    eff_cond = [] if (attempt >= 2 and not has_guide_cond) else cond_paths[:2]
                    print(
                        f"[reenact-refs {idx_sp}/{len(ordered_specs)}] Generating {ref_id} via flow"
                        f" ({active_img_model}, 0-credit x{attempt_batch}) (try {attempt + 1}/3, cond={[p.name for p in eff_cond]})...",
                        flush=True,
                    )
                    flow_res = await generate_flow_image_batch(
                        client=client,
                        prompt=full_prompt + retry_suffix,
                        out_path=out_png,
                        conditioning_paths=eff_cond if eff_cond else None,
                        batch_count=attempt_batch,
                        aspect="9:16",
                        uploaded_cache=uploaded_cache,
                        seen_img_srcs=seen_img_srcs,
                        spec=spec,
                        source_dhashes=source_dhashes,
                        project_dir=None,
                        image_model=active_img_model,
                    )
                    if not flow_res.get("ok") or not flow_res.get("saved") or not out_png.exists():
                        miss_reason = str(flow_res.get("reason") or "")
                        print(
                            f"[reenact-refs {idx_sp}/{len(ordered_specs)}] {ref_id} try {attempt + 1} Flow batch miss: {miss_reason} ({active_img_model})",
                            flush=True,
                        )
                        if miss_reason == "flow_unusual_activity_blocked":
                            rl_models.update(fallback_models)
                            unusual_activity_halted = True
                            halt_reason = miss_reason
                            try:
                                import base64 as _b64

                                _shot_res = await client.send("Page.captureScreenshot", {"format": "png"})
                                if _shot_res and _shot_res.get("data"):
                                    _cap_path = vis_dir / "flow_unusual_activity_capture.png"
                                    _cap_path.write_bytes(_b64.b64decode(_shot_res["data"]))
                                    print(f"[reenact-refs {idx_sp}/{len(ordered_specs)}] Saved Flow warning screenshot: {_cap_path}", flush=True)
                            except Exception:
                                pass
                            print(
                                f"[reenact-refs {idx_sp}/{len(ordered_specs)}] HARD HALT ({miss_reason}): "
                                f"Google Flow unusual activity detected on {active_img_model}; "
                                "halting entire batch immediately (0 retries, 0 model hopping).",
                                flush=True,
                            )
                            break
                        if miss_reason == "flow_usage_limit_reached":
                            rl_models.add(active_img_model)
                            next_avail = [m for m in fallback_models if m not in rl_models]
                            if next_avail:
                                print(
                                    f"[reenact-refs {idx_sp}/{len(ordered_specs)}] {active_img_model} hit Flow usage limit -> switching cleanly to official 0-credit model '{next_avail[0]}'...",
                                    flush=True,
                                )
                                continue
                            print(
                                f"[reenact-refs {idx_sp}/{len(ordered_specs)}] ALL official 0-credit Flow image models exhausted ({fallback_models}); halting immediately to avoid rate-limit hammering.",
                                flush=True,
                            )
                            break
                        if "no_flow_images_rendered" in miss_reason:
                            if client_cm is not None:
                                try:
                                    await client_cm.__aexit__(None, None, None)
                                except Exception:
                                    pass
                            _close_dedicated_worker_tab(opened_tab_id, opened_lease_owner)
                            client_cm = None
                            client = None
                            opened_tab_id = None
                            opened_lease_owner = None
                            await asyncio.sleep(2.0)
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
                            f"[reenact-refs {idx_sp}/{len(ordered_specs)}] {ref_id}: PASSED via Flow x{attempt_batch} "
                            f"(best_of={flow_res.get('candidate_count')}, cand#{int(flow_res.get('selected_index', 0)) + 1}, dHash_min={min_dh})",
                            flush=True,
                        )
                        ok_this = True
                        break
                    out_png.unlink(missing_ok=True)
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
                    _close_dedicated_worker_tab(opened_tab_id, opened_lease_owner)
                    client_cm = None
                    client = None
                    opened_tab_id = None
                    opened_lease_owner = None
                    await asyncio.sleep(2.5)
            if ok_this:
                generated.append(ref_id)
            else:
                failed.append(ref_id)
            if unusual_activity_halted:
                for rem_spec in ordered_specs[idx_sp:]:
                    rem_id = str(rem_spec["ref_id"])
                    if only_ref_ids and rem_id not in only_ref_ids:
                        continue
                    failed.append(rem_id)
                break
    finally:
        if client_cm is not None:
            try:
                await client_cm.__aexit__(None, None, None)
            except Exception:
                pass
        _close_dedicated_worker_tab(opened_tab_id, opened_lease_owner)
        if not failed and FLOW_AUTO_CLEANUP_ON_SUCCESS and opened_project_urls:
            try:
                await clean_flow_workspace_async(
                    cdp_port=cdp_port,
                    temp_project_id=p_dir.name,
                    project_urls=opened_project_urls,
                    clean_local_temp=True,
                )
            except Exception as exc:
                import logging

                logging.getLogger("source_reenactment").warning(
                    "Post-reenactment Flow workspace cleanup warning for %s: %s", p_dir.name, exc, exc_info=True
                )

    sheet_path = render_reenactment_comparison_sheet(p_dir, edl_doc, specs_payload)
    return {
        "project_id": p_dir.name,
        "slug": slug,
        "backend": eff_backend,
        "batch_count": first_pass_batch if eff_backend == "flow" else 1,
        "retry_batch_count": eff_retry_batch if eff_backend == "flow" else 1,
        "generated_count": len(generated),
        "failed_ids": failed,
        "unusual_activity_halted": unusual_activity_halted,
        "halted_reason": halt_reason,
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
    batch_count: int | None = None,
    retry_batch_count: int = FLOW_ZERO_CREDIT_IMAGE_RETRY_BATCH_COUNT,
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
            retry_batch_count=retry_batch_count,
        )
    )


def purge_reenactment_quarantine(
    slug: str | None = None,
    *,
    allow_all: bool = False,
    cdp_port: int = 9222,
) -> dict[str, Any]:
    """Deletes `/tmp/aab_reenact/<slug>` after Stage 3 keyframe translation (or all when `allow_all=True` with 0 active leases)."""
    clean_slug = str(slug or "").strip()
    if clean_slug:
        if "/" in clean_slug or "\\" in clean_slug or ".." in clean_slug or clean_slug in (".", ".."):
            raise ValueError(f"Invalid reenactment quarantine slug: {slug!r}")
        target = REENACT_QUARANTINE_ROOT / clean_slug
    else:
        if not allow_all:
            raise ValueError(
                "purge_reenactment_quarantine requires a non-empty episode slug "
                "(pass allow_all=True only for standalone maintenance)"
            )
        from pipeline.cdp_tab_lease import list_active_tab_leases

        active = list_active_tab_leases(cdp_port=cdp_port)
        if active:
            raise RuntimeError(
                f"Refusing allow_all quarantine purge while {len(active)} active CDP tab lease(s) exist"
            )
        target = REENACT_QUARANTINE_ROOT
    existed = target.exists()
    if existed:
        shutil.rmtree(target, ignore_errors=True)
    if clean_slug and REENACT_QUARANTINE_ROOT.exists():
        try:
            if not any(REENACT_QUARANTINE_ROOT.iterdir()):
                shutil.rmtree(REENACT_QUARANTINE_ROOT, ignore_errors=True)
        except OSError:
            pass
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
    if require_quarantine_purged:
        quarantine_clean = (
            not (REENACT_QUARANTINE_ROOT / slug).exists()
            if slug
            else not REENACT_QUARANTINE_ROOT.exists()
        )
    else:
        quarantine_clean = True
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
    from pipeline.config import (
        MICRO_SHORT_CUT_MAX,
        MICRO_SHORT_CUT_MIN,
        MICRO_SHORT_PROFILE,
        EXPRESSIVE_V8_CLIP_COUNT_MAX,
        EXPRESSIVE_V8_CLIP_COUNT_MIN,
        SHORTS_90S_CLIP_COUNT_MAX,
        SHORTS_90S_CLIP_COUNT_MIN,
        SHORTS_90S_CUT_COUNT_MIN,
        SHORTS_90S_PROFILE,
        SHORTS_EXPRESSIVE_V8_PROFILE,
        resolve_shorts_format_profile,
    )

    asm_edl_for_fmt: dict[str, Any] = {}
    if assembled_edl_path.exists():
        try:
            asm_edl_for_fmt = json.loads(assembled_edl_path.read_text(encoding="utf-8"))
        except Exception:
            asm_edl_for_fmt = {}
    rq5_fmt = resolve_shorts_format_profile(
        vp,
        s_doc,
        asm_edl_for_fmt,
        {"sentences": sents, "clips": clips},
        project_id=asm_dir.parent.name,
    )
    if rq5_fmt == MICRO_SHORT_PROFILE:
        rq5_min_clips = MICRO_SHORT_CUT_MIN
        rq5_max_clips = MICRO_SHORT_CUT_MAX + 4
        rq5_min_cuts = MICRO_SHORT_CUT_MIN
    elif rq5_fmt == SHORTS_EXPRESSIVE_V8_PROFILE:
        rq5_min_clips = EXPRESSIVE_V8_CLIP_COUNT_MIN
        rq5_max_clips = EXPRESSIVE_V8_CLIP_COUNT_MAX
        rq5_min_cuts = EXPRESSIVE_V8_CLIP_COUNT_MIN
    elif rq5_fmt == SHORTS_90S_PROFILE:
        rq5_min_clips = SHORTS_90S_CLIP_COUNT_MIN
        rq5_max_clips = SHORTS_90S_CLIP_COUNT_MAX
        rq5_min_cuts = SHORTS_90S_CUT_COUNT_MIN
    else:
        rq5_min_clips = DIORAMA_TARGET_CUT_MIN
        rq5_max_clips = PORCELAIN_V7_TARGET_CLIP_MAX
        rq5_min_cuts = DIORAMA_TARGET_CUT_MIN

    edl_pacing_ok = True
    edl_min_cut_sec: float | None = None
    edl_max_cut_sec: float | None = None
    edl_avg_cut_sec: float | None = None
    if assembled_edl_path.exists():
        try:
            asm_edl = asm_edl_for_fmt or json.loads(assembled_edl_path.read_text(encoding="utf-8"))
            asm_durs = [float(c.get("duration_sec") or 0.0) for c in (asm_edl.get("cuts") or []) if isinstance(c, dict)]
            if asm_durs:
                edl_min_cut_sec = round(min(asm_durs), 4)
                edl_max_cut_sec = round(max(asm_durs), 4)
                edl_avg_cut_sec = round(float(np.mean(asm_durs)), 4)
                edl_pacing_ok = (
                    len(asm_durs) >= rq5_min_cuts
                    and edl_min_cut_sec >= PORCELAIN_V7_MIN_CUT_SEC - 1e-3
                    and edl_max_cut_sec <= PORCELAIN_V7_LONG_TAKE_MAX_SEC + 1e-3
                )
        except Exception:
            edl_pacing_ok = False
    rq5_ok = bool(
        rq5_min_clips <= total_clips <= rq5_max_clips
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
            "format_profile": rq5_fmt,
            "style_profile": vp.get("style_profile"),
            "total_clips": total_clips,
            "min_clips_required": rq5_min_clips,
            "max_clips_allowed": rq5_max_clips,
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
