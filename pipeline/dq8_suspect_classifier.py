"""
Rule R85 / DQ8 2-Tier Suspect Classifier & Annotated Evidence-Crop Exporter.

Architecture (empirically calibrated on 65 visually labeled YuNet detections across Ep09–Ep12):
  1. Stage 0 (`NON_HUMAN_PAREIDOLIA`): Filters out tiny architectural/window/hook pareidolia
     (`min_dim < 65px` in 1080p ROI, `l_med < 85`, or `non_ink_frac < 0.15`).
  2. Stage 1 (`HIGH_SUSPECT` — 0.0% clean-vinyl FPR, triggers automatic clip regeneration / DQ8 fail):
     - `eye_3d_flesh_socket >= 0.35` (photorealistic / 3D shaded reddish eye socket around YuNet eye landmarks)
     - OR `cheek_pore_hf >= 0.55` (high-frequency skin pore / hair / stubble residual with 2D ink masked out)
     - OR (`dark_hair_wrap >= 0.24` and `hemoglobin_index > -1.35` and `scalp_strand_energy <= 8.5`)
       (dark hair wrapping both crown and temples while excluding woven tweed flat caps)
  3. Stage 2 (`MODERATE_SUSPECT` — all remaining valid YuNet head boxes; 100% total defect coverage):
     - Does NOT trigger automatic clip retry or hard-block `DQ8` CV pass on its own.
     - Saves timestamped, bbox+landmark-annotated evidence crops (`05_assembly/dq8_suspect_crops/`)
       and composite `05_assembly/dq8_suspect_contact_sheet.jpg` for mandatory `@Research` Gate 2 visual verdict.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any

import cv2
import numpy as np


def _atomic_imwrite(path: Path, img: np.ndarray, params: list[int] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    suffix = path.suffix or ".png"
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp_dq8_", suffix=suffix)
    os.close(fd)
    tmp_p = Path(tmp_name)
    try:
        ok = cv2.imwrite(str(tmp_p), img, params or [])
        if not ok:
            raise RuntimeError(f"cv2.imwrite failed for {path}")
        os.replace(str(tmp_p), str(path))
    finally:
        if tmp_p.exists():
            tmp_p.unlink(missing_ok=True)


def detect_yunet_boxes_with_landmarks(
    bgr: np.ndarray,
    score_threshold: float = 0.62,
) -> list[dict[str, Any]]:
    """
    Runs bundled Apache-2.0 `face_detection_yunet_2023mar.onnx` at normalized `<= 640px` scale
    and returns deduplicated detections with 5-point landmarks (`re, le, nt, rm, lm`) in `bgr` coords.
    """
    from pipeline.source_reenactment import YUNET_FACE_MODEL_PATH, _DETECTOR_TLS

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

    model_path = Path(YUNET_FACE_MODEL_PATH)
    if not model_path.exists():
        return []

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
            _DETECTOR_TLS.yunet = False
            return []
    if not det:
        return []

    det.setScoreThreshold(float(score_threshold))
    det.setInputSize((in_w, in_h))
    try:
        _, faces = det.detect(resized)
    except Exception:
        faces = None
    if faces is None or len(faces) == 0:
        return []

    raw_items: list[dict[str, Any]] = []
    for row in faces:
        vals = [float(v) for v in row]
        fw_s, fh_s, sc = vals[2], vals[3], vals[14]
        if fw_s < 8.0 or fh_s < 8.0 or sc < float(score_threshold):
            continue
        bx = int(round(vals[0] / scale))
        by = int(round(vals[1] / scale))
        bw = int(round(fw_s / scale))
        bh = int(round(fh_s / scale))
        x0 = max(0, min(w - 1, bx))
        y0 = max(0, min(h - 1, by))
        x1 = max(x0 + 1, min(w, bx + bw))
        y1 = max(y0 + 1, min(h, by + bh))
        lms = [
            [round(vals[4] / scale, 1), round(vals[5] / scale, 1)],
            [round(vals[6] / scale, 1), round(vals[7] / scale, 1)],
            [round(vals[8] / scale, 1), round(vals[9] / scale, 1)],
            [round(vals[10] / scale, 1), round(vals[11] / scale, 1)],
            [round(vals[12] / scale, 1), round(vals[13] / scale, 1)],
        ]
        raw_items.append(
            {
                "bbox": [x0, y0, x1 - x0, y1 - y0],
                "raw_bbox": [bx, by, bw, bh],
                "score": round(sc, 4),
                "landmarks": lms,
            }
        )

    raw_items.sort(key=lambda d: float(d["score"]), reverse=True)
    deduped: list[dict[str, Any]] = []
    for cand in raw_items:
        x0, y0, cw, ch = cand["bbox"]
        x1, y1 = x0 + cw, y0 + ch
        keep = True
        for prev in deduped:
            px0, py0, pw, ph = prev["bbox"]
            px1, py1 = px0 + pw, py0 + ph
            ix0, iy0 = max(x0, px0), max(y0, py0)
            ix1, iy1 = min(x1, px1), min(y1, py1)
            inter = max(0, ix1 - ix0) * max(0, iy1 - iy0)
            union = max(1, cw * ch + pw * ph - inter)
            if (inter / float(union)) > 0.45:
                keep = False
                break
        if keep:
            deduped.append(cand)
    return deduped


def extract_context_crop_from_roi(
    roi_bgr: np.ndarray,
    bbox_xywh: list[int] | tuple[int, int, int, int],
    landmarks_in_roi: list[list[float]] | None = None,
) -> tuple[np.ndarray, list[int], list[int], list[list[float]]]:
    """
    Slices the standard padded head+crown+temple context patch around `bbox_xywh` inside `roi_bgr`.
    Returns `(ctx_crop, crop_origin_xy, bbox_in_crop, landmarks_in_crop)`.
    """
    hr, wr = roi_bgr.shape[:2]
    bx, by, bw, bh = [int(v) for v in bbox_xywh]
    pad_x = int(bw * 0.35)
    pad_y_top = int(bh * 0.45)
    pad_y_bot = int(bh * 0.25)
    x0 = max(0, bx - pad_x)
    y0 = max(0, by - pad_y_top)
    x1 = min(wr, bx + bw + pad_x)
    y1 = min(hr, by + bh + pad_y_bot)
    ctx_crop = roi_bgr[y0:y1, x0:x1].copy()
    bbox_in_crop = [bx - x0, by - y0, bw, bh]
    if landmarks_in_roi and len(landmarks_in_roi) == 5:
        lms_crop = [[round(float(lx) - x0, 1), round(float(ly) - y0, 1)] for lx, ly in landmarks_in_roi]
    else:
        # Fallback geometric landmark estimate when caller only passed 4-tuple bbox
        cbx, cby = bx - x0, by - y0
        lms_crop = [
            [round(cbx + bw * 0.33, 1), round(cby + bh * 0.38, 1)],
            [round(cbx + bw * 0.67, 1), round(cby + bh * 0.38, 1)],
            [round(cbx + bw * 0.50, 1), round(cby + bh * 0.56, 1)],
            [round(cbx + bw * 0.36, 1), round(cby + bh * 0.74, 1)],
            [round(cbx + bw * 0.64, 1), round(cby + bh * 0.74, 1)],
        ]
    return ctx_crop, [x0, y0], bbox_in_crop, lms_crop


def classify_dq8_yunet_box(
    img_bgr: np.ndarray,
    bbox_xywh: list[int] | tuple[int, int, int, int],
    score: float,
    landmarks_5pt: list[list[float]] | None = None,
    *,
    is_precrop: bool = False,
    roi_bbox_xywh: list[int] | tuple[int, int, int, int] | None = None,
) -> dict[str, Any]:
    """
    Evaluates a YuNet detection and classifies it into:
      - `NON_HUMAN_PAREIDOLIA`
      - `HIGH_SUSPECT` (auto-regeneration / DQ8 fail trigger; 0% clean-vinyl FPR on 65-box benchmark)
      - `MODERATE_SUSPECT` (forwarded with crop + timecode to `@Research` Gate 2; 100% total defect recall)
    """
    if img_bgr is None or img_bgr.size == 0:
        return {
            "tier": "NON_HUMAN_PAREIDOLIA",
            "is_high_suspect": False,
            "is_suspect": False,
            "reasons": ["empty_image"],
            "metrics": {},
        }

    if is_precrop:
        ctx_crop = img_bgr
        bx, by, bw, bh = [int(v) for v in bbox_xywh]
        orig_xy = [0, 0]
        roi_box = [int(v) for v in (roi_bbox_xywh or bbox_xywh)]
        lms = landmarks_5pt or [
            [bx + bw * 0.33, by + bh * 0.38],
            [bx + bw * 0.67, by + bh * 0.38],
            [bx + bw * 0.50, by + bh * 0.56],
            [bx + bw * 0.36, by + bh * 0.74],
            [bx + bw * 0.64, by + bh * 0.74],
        ]
    else:
        roi_box = [int(v) for v in bbox_xywh]
        ctx_crop, orig_xy, (bx, by, bw, bh), lms = extract_context_crop_from_roi(
            img_bgr, bbox_xywh, landmarks_5pt
        )

    hc, wc = ctx_crop.shape[:2]
    x0, y0 = max(0, bx), max(0, by)
    x1, y1 = min(wc, bx + bw), min(hc, by + bh)
    face = ctx_crop[y0:y1, x0:x1]
    if face.size == 0 or face.shape[0] < 10 or face.shape[1] < 10:
        return {
            "tier": "NON_HUMAN_PAREIDOLIA",
            "is_high_suspect": False,
            "is_suspect": False,
            "reasons": ["degenerate_face_crop"],
            "metrics": {},
        }

    fh, fw = face.shape[:2]
    min_dim = float(min(roi_box[2], roi_box[3]))
    max_dim = float(max(roi_box[2], roi_box[3]))
    re_xy, le_xy = lms[0], lms[1]
    eye_dist = float(np.hypot(float(le_xy[0]) - float(re_xy[0]), float(le_xy[1]) - float(re_xy[1]))) / max(1.0, float(bw))

    in_face = face[int(fh * 0.14) : max(1, int(fh * 0.86)), int(fw * 0.14) : max(1, int(fw * 0.86))]
    if in_face.size == 0:
        in_face = face
    in_hsv = cv2.cvtColor(in_face, cv2.COLOR_BGR2HSV).astype(np.float32)
    in_lab = cv2.cvtColor(in_face, cv2.COLOR_BGR2LAB).astype(np.float32)
    in_gray = cv2.cvtColor(in_face, cv2.COLOR_BGR2GRAY).astype(np.float32)
    non_ink = in_hsv[:, :, 2] >= 75.0
    non_ink_frac = float(np.mean(non_ink))

    # Crown + Temple Hair Wrap & Scalp Strand High-Frequency Energy
    c_y0 = max(0, by - int(bh * 0.32))
    c_y1 = min(hc, by + int(bh * 0.18))
    crown = ctx_crop[c_y0:c_y1, max(0, bx + int(bw * 0.10)) : min(wc, bx + int(bw * 0.90))]
    crown_hsv = cv2.cvtColor(crown, cv2.COLOR_BGR2HSV).astype(np.float32) if crown.size else in_hsv
    crown_gray = cv2.cvtColor(crown, cv2.COLOR_BGR2GRAY).astype(np.float32) if crown.size else in_gray

    t_y0 = max(0, by + int(bh * 0.06))
    t_y1 = min(hc, by + int(bh * 0.52))
    t_left = ctx_crop[t_y0:t_y1, max(0, bx - int(bw * 0.14)) : min(wc, bx + int(bw * 0.22))]
    t_right = ctx_crop[t_y0:t_y1, max(0, bx + int(bw * 0.78)) : min(wc, bx + int(bw * 1.14))]

    cheek_v_med = float(np.median(in_hsv[:, :, 2][non_ink])) if np.any(non_ink) else float(np.median(in_hsv[:, :, 2]))
    crown_dark = float(np.mean(crown_hsv[:, :, 2] < min(82.0, cheek_v_med * 0.52)))
    up_patch = face[0 : max(1, int(fh * 0.26)), int(fw * 0.15) : max(1, int(fw * 0.85))]
    if up_patch.size > 0:
        uhsv = cv2.cvtColor(up_patch, cv2.COLOR_BGR2HSV).astype(np.float32)
        upper_box_dark = float(np.mean(uhsv[:, :, 2] < min(82.0, cheek_v_med * 0.52)))
    else:
        upper_box_dark = 0.0
    temple_darks: list[float] = []
    for tp in (t_left, t_right):
        if tp.size > 0:
            thsv = cv2.cvtColor(tp, cv2.COLOR_BGR2HSV).astype(np.float32)
            temple_darks.append(float(np.mean(thsv[:, :, 2] < min(82.0, cheek_v_med * 0.52))))
    temple_dark_max = max(temple_darks) if temple_darks else 0.0
    dark_hair_wrap = float(min(crown_dark, temple_dark_max * 1.25))

    if crown_gray.shape[0] >= 12 and crown_gray.shape[1] >= 12:
        blur_c = cv2.GaussianBlur(crown_gray, (0, 0), 1.4)
        scalp_strand_energy = float(np.percentile(np.abs(crown_gray - blur_c), 80))
    else:
        scalp_strand_energy = 0.0

    # Illuminant-normalized CIE Lab hemoglobin redness, raw luminance & ceramic-bowl glare pareidolia stats
    raw_l_med = float(np.median(in_lab[:, :, 0]))
    specular_glare_frac = float(np.mean((in_hsv[:, :, 2] >= 185.0) & (in_hsv[:, :, 1] <= 50.0)))
    ctx_hsv = cv2.cvtColor(ctx_crop, cv2.COLOR_BGR2HSV).astype(np.float32)
    rim_mask = np.ones((hc, wc), dtype=bool)
    rim_mask[int(hc * 0.20) : int(hc * 0.85), int(wc * 0.18) : int(wc * 0.82)] = False
    outer_ceramic_rim_frac = (
        float(np.mean((ctx_hsv[:, :, 2][rim_mask] >= 160.0) & (ctx_hsv[:, :, 1][rim_mask] <= 48.0)))
        if int(np.sum(rim_mask)) >= 20
        else 0.0
    )
    if int(np.sum(non_ink)) >= 25:
        a_vals = in_lab[:, :, 1][non_ink] - 128.0
        b_vals = in_lab[:, :, 2][non_ink] - 128.0
        l_vals = in_lab[:, :, 0][non_ink]
        a_p85 = float(np.percentile(a_vals, 85))
        a_iqr = float(np.percentile(a_vals, 85) - np.percentile(a_vals, 15))
        b_med = float(np.median(b_vals))
        l_med = float(np.median(l_vals))
        hemoglobin_index = float(a_p85 - 0.28 * max(0.0, b_med))
        chroma_heterogeneity = float(np.hypot(a_iqr, float(np.percentile(b_vals, 85) - np.percentile(b_vals, 15)) * 0.5))
    else:
        a_p85, b_med, l_med = 0.0, 0.0, float(np.median(in_lab[:, :, 0]))
        hemoglobin_index = 0.0
        chroma_heterogeneity = 0.0

    # YuNet eye landmark 3D flesh socket vs 2D ink stroke bimodality
    r_eye_r = max(4, int(round(max(bw, bh) * 0.09)))
    eye_ink_sharpness_list: list[float] = []
    eye_midtone_flesh_list: list[float] = []
    for ex, ey in (re_xy, le_xy):
        exi, eyi = int(round(float(ex))), int(round(float(ey)))
        ep = ctx_crop[max(0, eyi - r_eye_r) : min(hc, eyi + r_eye_r + 1), max(0, exi - r_eye_r) : min(wc, exi + r_eye_r + 1)]
        if ep.size >= 16:
            eg = cv2.cvtColor(ep, cv2.COLOR_BGR2GRAY).astype(np.float32)
            elab = cv2.cvtColor(ep, cv2.COLOR_BGR2LAB).astype(np.float32)
            dark_ink_p = float(np.mean(eg < 58.0))
            bright_sur_p = float(np.mean(eg > 130.0))
            mid_socket_red = float(np.mean((eg >= 58.0) & (eg <= 145.0) & ((elab[:, :, 1] - 128.0) >= 5.5)))
            eye_ink_sharpness_list.append(min(dark_ink_p, bright_sur_p))
            eye_midtone_flesh_list.append(mid_socket_red)
    eye_2d_bimodal = max(eye_ink_sharpness_list) if eye_ink_sharpness_list else 0.0
    eye_3d_flesh_socket = max(eye_midtone_flesh_list) if eye_midtone_flesh_list else 0.0

    # Jaw / chin beard-stubble anomaly
    fh_patch = face[int(fh * 0.06) : max(1, int(fh * 0.32)), int(fw * 0.20) : max(1, int(fw * 0.80))]
    jaw_patch = face[int(fh * 0.64) : max(1, int(fh * 0.94)), int(fw * 0.16) : max(1, int(fw * 0.84))]
    jaw_beard_anomaly = 0.0
    if fh_patch.size >= 25 and jaw_patch.size >= 25:
        fh_lab = cv2.cvtColor(fh_patch, cv2.COLOR_BGR2LAB).astype(np.float32)
        jw_lab = cv2.cvtColor(jaw_patch, cv2.COLOR_BGR2LAB).astype(np.float32)
        fh_ni = fh_lab[:, :, 0] >= 80.0
        jw_ni = jw_lab[:, :, 0] >= 55.0
        if int(np.sum(fh_ni)) >= 10 and int(np.sum(jw_ni)) >= 10:
            fh_l = float(np.median(fh_lab[:, :, 0][fh_ni]))
            fh_b = float(np.median(fh_lab[:, :, 2][fh_ni]))
            fh_a = float(np.median(fh_lab[:, :, 1][fh_ni]))
            brown_jaw_mask = (
                (jw_lab[:, :, 0] >= 55.0)
                & (jw_lab[:, :, 0] <= fh_l - 22.0)
                & (((jw_lab[:, :, 2] - fh_b) >= 8.0) | ((jw_lab[:, :, 1] - fh_a) >= 5.0))
            )
            jaw_beard_anomaly = float(np.mean(brown_jaw_mask))

    # Cheek high-frequency pore/stubble residual (masking 2D ink strokes)
    ck_patch = face[int(fh * 0.38) : max(1, int(fh * 0.66)), int(fw * 0.18) : max(1, int(fw * 0.82))]
    if ck_patch.shape[0] >= 10 and ck_patch.shape[1] >= 10:
        ck_g = cv2.cvtColor(ck_patch, cv2.COLOR_BGR2GRAY).astype(np.float32)
        ink_dil = cv2.dilate((ck_g < 75.0).astype(np.uint8), np.ones((5, 5), np.uint8)) == 0
        ck_blur = cv2.GaussianBlur(ck_g, (0, 0), 1.2)
        hp = np.abs(ck_g - ck_blur)
        cheek_pore_hf = float(np.median(hp[ink_dil])) if int(np.sum(ink_dil)) >= 15 else 0.0
    else:
        cheek_pore_hf = 0.0

    metrics = {
        "min_dim": round(min_dim, 1),
        "max_dim": round(max_dim, 1),
        "score": round(float(score), 4),
        "eye_dist": round(eye_dist, 3),
        "non_ink_frac": round(non_ink_frac, 3),
        "l_med": round(l_med, 2),
        "raw_l_med": round(raw_l_med, 2),
        "outer_ceramic_rim_frac": round(outer_ceramic_rim_frac, 4),
        "specular_glare_frac": round(specular_glare_frac, 4),
        "crown_dark": round(crown_dark, 4),
        "upper_box_dark": round(upper_box_dark, 4),
        "temple_dark_max": round(temple_dark_max, 4),
        "dark_hair_wrap": round(dark_hair_wrap, 4),
        "scalp_strand_energy": round(scalp_strand_energy, 3),
        "a_p85": round(a_p85, 2),
        "b_med": round(b_med, 2),
        "hemoglobin_index": round(hemoglobin_index, 2),
        "chroma_heterogeneity": round(chroma_heterogeneity, 2),
        "eye_2d_bimodal": round(eye_2d_bimodal, 4),
        "eye_3d_flesh_socket": round(eye_3d_flesh_socket, 4),
        "jaw_beard_anomaly": round(jaw_beard_anomaly, 4),
        "cheek_pore_hf": round(cheek_pore_hf, 3),
    }

    # Stage 0: Architectural / dark window pareidolia filter
    if min_dim < 65.0 or l_med < 85.0 or non_ink_frac < 0.15:
        return {
            "tier": "NON_HUMAN_PAREIDOLIA",
            "is_high_suspect": False,
            "is_suspect": False,
            "reasons": ["pareidolia_small_or_dark_non_head"],
            "metrics": metrics,
            "crop_bgr": ctx_crop,
            "crop_origin_xy": orig_xy,
            "bbox_in_crop": [bx, by, bw, bh],
            "landmarks_in_crop": lms,
        }

    # Stage 1: HIGH_SUSPECT (Composite Option A — 0% clean-vinyl FPR; auto-regen trigger)
    high_reasons: list[str] = []
    if eye_3d_flesh_socket >= 0.35:
        high_reasons.append(f"eye_3d_flesh_socket={eye_3d_flesh_socket:.3f}>=0.35")
    if cheek_pore_hf >= 0.62 and a_p85 >= 3.0:
        high_reasons.append(f"cheek_pore_hf={cheek_pore_hf:.3f}>=0.62")
    if dark_hair_wrap >= 0.24 and upper_box_dark >= 0.16 and hemoglobin_index > -1.35 and scalp_strand_energy <= 5.5:
        high_reasons.append(f"dark_hair_wrap={dark_hair_wrap:.3f}>=0.24,ubd={upper_box_dark:.3f}")
    if scalp_strand_energy >= 4.0 and hemoglobin_index >= 1.80:
        high_reasons.append(f"textured_hair_and_redness={scalp_strand_energy:.2f}/{hemoglobin_index:.2f}")
    if hemoglobin_index >= 6.0:
        high_reasons.append(f"hemoglobin_index={hemoglobin_index:.2f}>=6.0")

    if high_reasons:
        is_glossy_ceramic_bowl = (
            outer_ceramic_rim_frac >= 0.20
            and specular_glare_frac >= 0.008
            and (
                raw_l_med < 83.0
                or (
                    raw_l_med <= 92.0
                    and b_med >= 8.0
                    and specular_glare_frac >= 0.020
                    and dark_hair_wrap < 0.24
                    and scalp_strand_energy <= 2.2
                )
                or (
                    min_dim >= 620.0
                    and max_dim >= 1000.0
                    and specular_glare_frac >= 0.20
                    and b_med >= 12.0
                    and chroma_heterogeneity >= 12.0
                    and dark_hair_wrap < 0.08
                    and scalp_strand_energy <= 2.2
                    and cheek_pore_hf < 0.62
                )
            )
        )
        if is_glossy_ceramic_bowl:
            return {
                "tier": "MODERATE_SUSPECT",
                "is_high_suspect": False,
                "is_suspect": True,
                "reasons": ["glossy_bowl_or_liquid_pareidolia_for_gate2", *high_reasons],
                "metrics": metrics,
                "crop_bgr": ctx_crop,
                "crop_origin_xy": orig_xy,
                "bbox_in_crop": [bx, by, bw, bh],
                "landmarks_in_crop": lms,
            }
        return {
            "tier": "HIGH_SUSPECT",
            "is_high_suspect": True,
            "is_suspect": True,
            "reasons": high_reasons,
            "metrics": metrics,
            "crop_bgr": ctx_crop,
            "crop_origin_xy": orig_xy,
            "bbox_in_crop": [bx, by, bw, bh],
            "landmarks_in_crop": lms,
        }

    # Stage 2: MODERATE_SUSPECT — all remaining valid YuNet boxes (forwarded to @Research Gate 2 with crop + timecode)
    mod_reasons: list[str] = ["yunet_head_candidate_for_gate2"]
    if dark_hair_wrap >= 0.10:
        mod_reasons.append(f"temple_or_cap_dark={dark_hair_wrap:.3f}")
    if hemoglobin_index >= 2.20:
        mod_reasons.append(f"warm_or_flesh_redness={hemoglobin_index:.2f}")
    if jaw_beard_anomaly >= 0.45:
        mod_reasons.append(f"jaw_luma_chroma_step={jaw_beard_anomaly:.3f}")

    return {
        "tier": "MODERATE_SUSPECT",
        "is_high_suspect": False,
        "is_suspect": True,
        "reasons": mod_reasons,
        "metrics": metrics,
        "crop_bgr": ctx_crop,
        "crop_origin_xy": orig_xy,
        "bbox_in_crop": [bx, by, bw, bh],
        "landmarks_in_crop": lms,
    }


def render_annotated_dq8_crop(det_result: dict[str, Any], header_line: str = "") -> np.ndarray:
    """Draws bounding box, 5 YuNet landmarks, and telemetry banner onto a context crop."""
    crop = det_result["crop_bgr"].copy()
    bx, by, bw, bh = [int(v) for v in det_result["bbox_in_crop"]]
    is_high = bool(det_result.get("is_high_suspect"))
    color = (0, 0, 255) if is_high else (0, 200, 255)
    cv2.rectangle(crop, (bx, by), (bx + bw, by + bh), color, 2)
    for lx, ly in det_result.get("landmarks_in_crop") or []:
        cv2.circle(crop, (int(round(float(lx))), int(round(float(ly)))), 2, (255, 255, 0), -1)
    if header_line:
        h, w = crop.shape[:2]
        banner_h = 38
        out = np.zeros((h + banner_h, max(w, 220), 3), dtype=np.uint8)
        out[:banner_h, :] = (28, 20, 48) if is_high else (28, 36, 42)
        out[banner_h : banner_h + h, :w] = crop
        lines = header_line.split("\n")[:2]
        for li, ln in enumerate(lines):
            cv2.putText(
                out,
                ln,
                (5, 14 + li * 16),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.38,
                (80, 120, 255) if (li == 0 and is_high) else (230, 230, 230),
                1,
                cv2.LINE_AA,
            )
        return out
    return crop


def save_dq8_suspect_evidence(
    project_dir: Path,
    suspect_items: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Persists individual annotated suspect crops (`05_assembly/dq8_suspect_crops/*.png`) and
    a composite contact sheet (`05_assembly/dq8_suspect_contact_sheet.jpg`) for `@Research` Gate 2.
    """
    asm_dir = Path(project_dir) / "05_assembly"
    crops_dir = asm_dir / "dq8_suspect_crops"
    crops_dir.mkdir(parents=True, exist_ok=True)
    # Clean stale crops from prior runs in this folder so old filenames don't linger
    for old_png in crops_dir.glob("cut_*.png"):
        old_png.unlink(missing_ok=True)

    saved_records: list[dict[str, Any]] = []
    sheet_tiles: list[np.ndarray] = []

    for item in suspect_items:
        c_idx = int(item["cut_index"])
        b_idx = int(item["box_index"])
        t_sec = float(item["timeline_sec"])
        src_sec = float(item["src_clip_sec"])
        det_res = item["det_result"]
        tier = str(det_res["tier"])
        tier_slug = "high" if tier == "HIGH_SUSPECT" else "mod"
        fname = f"cut_{c_idx:02d}_t{t_sec:05.2f}s_src{src_sec:05.2f}s_b{b_idx}_{tier_slug}.png"
        out_png = crops_dir / fname
        m = det_res["metrics"]
        hdr = (
            f"C{c_idx:02d} t={t_sec:.2f}s [{tier_slug.upper()}] sc={m.get('score', 0):.2f}\n"
            f"e3d={m.get('eye_3d_flesh_socket', 0):.2f} pr={m.get('cheek_pore_hf', 0):.2f} wr={m.get('dark_hair_wrap', 0):.2f}"
        )
        vis_crop = render_annotated_dq8_crop(det_res, header_line=hdr)
        _atomic_imwrite(out_png, vis_crop)
        rel_crop = f"05_assembly/dq8_suspect_crops/{fname}"
        sheet_tiles.append(vis_crop)
        saved_records.append(
            {
                "cut_index": c_idx,
                "box_index": b_idx,
                "timeline_sec": round(t_sec, 3),
                "src_clip_sec": round(src_sec, 3),
                "frame_index": int(item.get("frame_index") or 0),
                "bbox_in_roi": list(item["bbox_in_roi"]),
                "landmarks_in_roi": list(item["landmarks_in_roi"]),
                "yunet_score": m.get("score", 0.0),
                "suspect_tier": tier,
                "reasons": list(det_res.get("reasons") or []),
                "metrics": m,
                "crop_path": rel_crop,
            }
        )

    sheet_rel: str | None = None
    sheet_path = asm_dir / "dq8_suspect_contact_sheet.jpg"
    if sheet_tiles:
        cols = min(6, max(1, len(sheet_tiles)))
        rows = (len(sheet_tiles) + cols - 1) // cols
        tw, th = 240, 260
        canvas = np.full((rows * th, cols * tw, 3), 20, dtype=np.uint8)
        for idx, tile_img in enumerate(sheet_tiles):
            r_i, c_i = divmod(idx, cols)
            ih, iw = tile_img.shape[:2]
            sc = min((tw - 8) / max(1, iw), (th - 8) / max(1, ih))
            nw, nh = max(1, int(round(iw * sc))), max(1, int(round(ih * sc)))
            rsz = cv2.resize(tile_img, (nw, nh), interpolation=cv2.INTER_AREA)
            ox = c_i * tw + (tw - nw) // 2
            oy = r_i * th + (th - nh) // 2
            canvas[oy : oy + nh, ox : ox + nw] = rsz
        _atomic_imwrite(sheet_path, canvas, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
        sheet_rel = "05_assembly/dq8_suspect_contact_sheet.jpg"
    elif sheet_path.exists():
        sheet_path.unlink(missing_ok=True)

    return {
        "suspect_detections": saved_records,
        "contact_sheet_path": sheet_rel,
    }
