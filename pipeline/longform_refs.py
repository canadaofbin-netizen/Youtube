"""
ALL ABOUT BRAIN — Standalone 16:9 (`1920x1080`) Hybrid (`Track A` + `Track B`) Reference Anchor Pack Engine
(`pipeline/longform_refs.py`).

100% isolated from `9:16` Shorts `porcelain_anchor_pack.py` (`REENACT_QUARANTINE_ROOT = /tmp/aab_reenact`).
Uses isolated `/tmp/aab_reenact_lf/<slug>` (`LONGFORM_QUARANTINE_ROOT`) when staging `Track A` sanitized
experiment layout guides, generates `1920x1080` (`16:9`) `0-credit` Google Flow `Image` (`Nano Banana 2.1` `x4`)
master/room/3D-brain reference PNGs in `generation_order` `1 -> 2 -> 3`, verifies `Q1–Q10` widescreen CV QA,
binds `reference_image` paths onto `visual_plan.json`, and renders `03_visuals/longform_ref_contact_sheet.png`.
"""

from __future__ import annotations

import asyncio
import json
import shutil
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from pipeline.config import (
    BRAIN_SETTINGS,
    DEFAULT_CDP_PORT,
    FLOW_ASPECT_LONGFORM,
    FLOW_ZERO_CREDIT_IMAGE_BATCH_COUNT,
    LONGFORM_QUARANTINE_ROOT,
    LONGFORM_VIDEO_HEIGHT,
    LONGFORM_VIDEO_WIDTH,
    PORCELAIN_V7_CAST_STYLE,
    PORCELAIN_V7_OPTICS_LOCK,
    PORCELAIN_V7_STYLE_PROFILE,
    PORCELAIN_V7_WORLD_STYLE,
    REENACT_MIN_DHASH_DISTANCE,
    REF_IMAGE_CROSS_HIST_CORR_MIN,
    REF_IMAGE_CROSS_LUMA_SPREAD_MAX,
    REF_IMAGES_DIRNAME,
    YUNET_FACE_MODEL_PATH,
)
from pipeline.longform_prompt_builder import resolve_longform_project_dir, sanitize_longform_scene_props
from pipeline.reference_image_qa import (
    _hamming_hex,
    _hist_corr,
    inspect_single_reference_image,
    load_provenance,
    register_reference_image,
)


def purge_longform_quarantine(slug: str | None = None) -> dict[str, Any]:
    """Purges `/tmp/aab_reenact_lf/<slug>` (or all `/tmp/aab_reenact_lf`) unconditionally."""
    root = Path(LONGFORM_QUARANTINE_ROOT)
    target = (root / slug) if slug else root
    removed = False
    if target.exists():
        shutil.rmtree(target, ignore_errors=True)
        removed = True
    return {"quarantine_target": str(target), "purged": removed, "exists_after": target.exists()}


def sanitize_longform_16x9_guide_frame(
    src_bgr: np.ndarray | str | Path,
    out_guide_png: Path,
    *,
    poster_boxes_norm: list[tuple[float, float, float, float]] | None = None,
) -> dict[str, Any]:
    """
    Sanitizes an academic/experiment frame into an aspect-preserving `16:9` (`1920x1080`) structural blocking guide:
      1. Trims black letterbox/pillarbox borders without cropping room geometry.
      2. Scrubs corner high-chroma posters, lower-third subtitle bands, and VHS bottom caption strips.
      3. Replaces exposed human faces & skin (YuNet B&W/color ovals + HSV/YCrCb skin mask) with smooth
         featureless matte-white porcelain silhouettes, then applies chalk surface abstraction.
      4. Preserves original aspect ratio onto `1920x1080` (e.g. `4:3 -> 1440x1080` centered + `240px`
         left/right blurred high-key matte architectural wall extensions; zero horizontal stretch, zero black bars).
    """
    from pipeline.source_reenactment import detect_human_faces_yunet

    if isinstance(src_bgr, (str, Path)):
        loaded = cv2.imread(str(src_bgr))
        if loaded is None:
            raise ValueError(f"Could not read source guide frame: {src_bgr}")
        src_arr = loaded
    else:
        src_arr = src_bgr

    # Compute source dHash BEFORE abstraction so RQ2 dHash >= 18 verifies distance from original frame
    raw_gray = cv2.cvtColor(src_arr, cv2.COLOR_BGR2GRAY)
    dh_resized = cv2.resize(raw_gray, (9, 8), interpolation=cv2.INTER_AREA)
    dh_bits = "".join("1" if b else "0" for b in (dh_resized[:, 1:] > dh_resized[:, :-1]).flatten())
    src_dhash = f"{int(dh_bits, 2):016x}"

    img = src_arr.copy()
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

    # 1. Corner poster / decal scrubbing into neutral matte architectural plates
    wall_sample = img[max(0, int(h * 0.08)) : max(4, int(h * 0.24)), int(w * 0.35) : int(w * 0.65)]
    wall_med = (
        np.median(wall_sample.reshape(-1, 3), axis=0).astype(np.uint8)
        if wall_sample.size > 0
        else np.array([218, 222, 226], dtype=np.uint8)
    )
    wall_color = tuple(int(max(198, min(238, c))) for c in wall_med.tolist())
    boxes_to_mask = list(poster_boxes_norm) if poster_boxes_norm is not None else []
    if poster_boxes_norm is None:
        for cx0, cy0, cx1, cy1 in ((0.00, 0.00, 0.24, 0.34), (0.74, 0.00, 1.00, 0.34)):
            px0, py0 = int(w * cx0), int(h * cy0)
            px1, py1 = int(w * cx1), int(h * cy1)
            patch_s = hsv_init[py0:py1, px0:px1, 1]
            if patch_s.size > 0 and float(np.mean(patch_s >= 80)) >= 0.06:
                boxes_to_mask.append((cx0, cy0, cx1, cy1))
    for x0n, y0n, x1n, y1n in boxes_to_mask:
        x0, y0 = int(w * x0n), int(h * y0n)
        x1, y1 = int(w * x1n), int(h * y1n)
        cv2.rectangle(img, (x0, y0), (x1, y1), wall_color, -1)

    # 2. Lower-third subtitle & bottom VHS caption scrubbing
    lt_y0, lt_y1 = int(h * 0.78), int(h * 0.98)
    lt_x0, lt_x1 = int(w * 0.08), int(w * 0.92)
    if lt_y1 > lt_y0 + 8 and lt_x1 > lt_x0 + 16:
        lt_band = img[lt_y0:lt_y1, lt_x0:lt_x1]
        lt_gray = cv2.cvtColor(lt_band, cv2.COLOR_BGR2GRAY)
        if float(np.mean(cv2.Canny(lt_gray, 70, 170) > 0)) > 0.045:
            img[lt_y0:lt_y1, :] = cv2.GaussianBlur(img[lt_y0:lt_y1, :], (45, 45), 14.0)
    bot_y0 = int(h * 0.88)
    if h - bot_y0 >= 4:
        gray_bot = cv2.cvtColor(img[bot_y0:, :], cv2.COLOR_BGR2GRAY)
        if float(np.mean(cv2.Canny(gray_bot, 70, 170) > 0)) > 0.035:
            floor_strip = img[max(0, bot_y0 - max(6, int(h * 0.05))) : bot_y0, :]
            if floor_strip.size > 0:
                img[bot_y0:, :] = cv2.resize(floor_strip, (w, h - bot_y0), interpolation=cv2.INTER_LINEAR)

    # 3. YuNet B&W/color face ovals + HSV/YCrCb skin-tone masking -> smooth featureless porcelain silhouettes
    face_boxes = detect_human_faces_yunet(img, score_threshold=0.42)
    face_mask = np.zeros((h, w), dtype=np.uint8)
    for fx, fy, fw, fh, _fsc in face_boxes:
        cx_f = int(round(fx + fw * 0.50))
        cy_f = int(round(fy + fh * 0.48))
        ax_w = max(10, int(round(fw * 0.72)))
        ax_h = max(12, int(round(fh * 0.84)))
        cv2.ellipse(face_mask, (cx_f, cy_f), (ax_w, ax_h), 0, 0, 360, 255, -1)

    if med_sat >= 16.0:
        hsv_c = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        ycrcb_c = cv2.cvtColor(img, cv2.COLOR_BGR2YCrCb)
        skin_mask = (
            (hsv_c[:, :, 0] <= 22)
            & (hsv_c[:, :, 1] >= 42)
            & (hsv_c[:, :, 1] <= 175)
            & (hsv_c[:, :, 2] >= 65)
            & (ycrcb_c[:, :, 1] >= 135)
            & (ycrcb_c[:, :, 1] <= 180)
            & (ycrcb_c[:, :, 2] >= 85)
            & (ycrcb_c[:, :, 2] <= 135)
        ).astype(np.uint8) * 255
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
        skin_mask = cv2.morphologyEx(skin_mask, cv2.MORPH_CLOSE, kernel, iterations=2)
    else:
        skin_mask = np.zeros((h, w), dtype=np.uint8)

    combined_mask = cv2.GaussianBlur(np.maximum(skin_mask, face_mask), (13, 13), 0)
    gray_full = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32)
    gray_smooth = cv2.GaussianBlur(gray_full, (31, 31), 0)
    porcelain_luma = np.clip(220.0 + 0.06 * (gray_smooth - 128.0), 202.0, 245.0).astype(np.uint8)
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

    # Heavy chalk architectural abstraction across room surfaces
    abstracted = cv2.GaussianBlur(img, (29, 29), 8.5)
    hsv = cv2.cvtColor(abstracted, cv2.COLOR_BGR2HSV)
    hsv[:, :, 1] = (hsv[:, :, 1].astype(np.float32) * 0.16).astype(np.uint8)
    hsv[:, :, 2] = np.clip(hsv[:, :, 2].astype(np.float32) * 1.12 + 26.0, 72, 244).astype(np.uint8)
    sanitized_core = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)
    # Re-stamp crisp smooth matte-white ovals over detected faces after room blur so head blocking stays legible & faceless
    for fx, fy, fw, fh, _fsc in face_boxes:
        cx_f = int(round(fx + fw * 0.50))
        cy_f = int(round(fy + fh * 0.48))
        ax_w = max(10, int(round(fw * 0.68)))
        ax_h = max(12, int(round(fh * 0.80)))
        cv2.ellipse(sanitized_core, (cx_f, cy_f), (ax_w, ax_h), 0, 0, 360, (238, 240, 242), -1)

    # 4. Aspect-preserving placement onto 1920x1080 (16:9) with matte studio wall side/vertical extensions (zero stretch)
    target_w, target_h = int(LONGFORM_VIDEO_WIDTH), int(LONGFORM_VIDEO_HEIGHT)
    src_ar = w / max(float(h), 1.0)
    target_ar = target_w / float(target_h)
    pad_left = pad_right = pad_top = pad_bottom = 0

    if src_ar < target_ar - 0.02:
        scaled_h = target_h
        scaled_w = max(64, min(target_w, int(round(target_h * src_ar))))
        center_bgr = cv2.resize(sanitized_core, (scaled_w, scaled_h), interpolation=cv2.INTER_AREA)
        pad_left = (target_w - scaled_w) // 2
        pad_right = target_w - scaled_w - pad_left
        canvas = np.full((target_h, target_w, 3), 228, dtype=np.uint8)
        canvas[:, pad_left : pad_left + scaled_w] = center_bgr
        strip_w = max(8, scaled_w // 10)
        if pad_left > 0:
            l_ext = cv2.resize(center_bgr[:, :strip_w], (pad_left, target_h), interpolation=cv2.INTER_LINEAR)
            l_ext = cv2.GaussianBlur(l_ext, (91, 91), 28.0)
            canvas[:, :pad_left] = np.clip(l_ext.astype(np.int16) + 8, 90, 244).astype(np.uint8)
            seam = min(24, pad_left, scaled_w // 4)
            if seam >= 4:
                ramp = np.linspace(0.0, 1.0, seam, dtype=np.float32)[None, :, None]
                blend_l = cv2.GaussianBlur(canvas[:, pad_left - seam : pad_left + seam], (31, 31), 9.0)
                canvas[:, pad_left - seam : pad_left] = (
                    canvas[:, pad_left - seam : pad_left].astype(np.float32) * (1.0 - ramp)
                    + blend_l[:, :seam].astype(np.float32) * ramp
                ).astype(np.uint8)
        if pad_right > 0:
            rx0 = pad_left + scaled_w
            r_ext = cv2.resize(center_bgr[:, scaled_w - strip_w :], (pad_right, target_h), interpolation=cv2.INTER_LINEAR)
            r_ext = cv2.GaussianBlur(r_ext, (91, 91), 28.0)
            canvas[:, rx0:] = np.clip(r_ext.astype(np.int16) + 8, 90, 244).astype(np.uint8)
            seam = min(24, pad_right, scaled_w // 4)
            if seam >= 4:
                ramp = np.linspace(1.0, 0.0, seam, dtype=np.float32)[None, :, None]
                blend_r = cv2.GaussianBlur(canvas[:, rx0 - seam : rx0 + seam], (31, 31), 9.0)
                canvas[:, rx0 : rx0 + seam] = (
                    canvas[:, rx0 : rx0 + seam].astype(np.float32) * (1.0 - ramp)
                    + blend_r[:, seam:].astype(np.float32) * ramp
                ).astype(np.uint8)
        clean_bgr = canvas
    elif src_ar > target_ar + 0.02:
        scaled_w = target_w
        scaled_h = max(64, min(target_h, int(round(target_w / max(src_ar, 0.1)))))
        center_bgr = cv2.resize(sanitized_core, (scaled_w, scaled_h), interpolation=cv2.INTER_AREA)
        pad_top = (target_h - scaled_h) // 2
        pad_bottom = target_h - scaled_h - pad_top
        canvas = np.full((target_h, target_w, 3), 228, dtype=np.uint8)
        canvas[pad_top : pad_top + scaled_h, :] = center_bgr
        strip_h = max(8, scaled_h // 10)
        if pad_top > 0:
            t_ext = cv2.GaussianBlur(
                cv2.resize(center_bgr[:strip_h, :], (target_w, pad_top), interpolation=cv2.INTER_LINEAR),
                (91, 91),
                28.0,
            )
            canvas[:pad_top, :] = np.clip(t_ext.astype(np.int16) + 8, 90, 244).astype(np.uint8)
        if pad_bottom > 0:
            by0 = pad_top + scaled_h
            b_ext = cv2.GaussianBlur(
                cv2.resize(center_bgr[scaled_h - strip_h :, :], (target_w, pad_bottom), interpolation=cv2.INTER_LINEAR),
                (91, 91),
                28.0,
            )
            canvas[by0:, :] = np.clip(b_ext.astype(np.int16) + 6, 90, 244).astype(np.uint8)
        clean_bgr = canvas
    else:
        scaled_w, scaled_h = target_w, target_h
        clean_bgr = cv2.resize(sanitized_core, (target_w, target_h), interpolation=cv2.INTER_AREA)

    # Soften top 10% and bottom 16% title/banner zones to neutral studio chalk
    clean_bgr[: int(target_h * 0.10), :] = cv2.GaussianBlur(clean_bgr[: int(target_h * 0.10), :], (61, 61), 18.0)
    clean_bgr[int(target_h * 0.84) :, :] = cv2.GaussianBlur(clean_bgr[int(target_h * 0.84) :, :], (61, 61), 18.0)

    out_guide_png.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out_guide_png), clean_bgr)
    return {
        "guide_png": str(out_guide_png),
        "resolution": [target_w, target_h],
        "aspect_preserved": True,
        "source_dhash_64": src_dhash,
        "faces_masked": len(face_boxes),
        "content_width": scaled_w,
        "content_height": scaled_h,
        "side_pad_px": [pad_left, pad_right],
        "vertical_pad_px": [pad_top, pad_bottom],
    }


def build_longform_reference_specs(project_dir: Path) -> dict[str, Any]:
    """Builds `03_visuals/reference_image_specs.json` (`16:9`, `1920x1080`) for a standalone Long-Form project."""
    vp_path = project_dir / "03_visuals" / "visual_plan.json"
    vp_doc = json.loads(vp_path.read_text(encoding="utf-8"))
    raw_anchors = list(vp_doc.get("reference_anchors") or [])
    if not raw_anchors:
        raw_anchors = [
            {
                "ref_id": "ref_lf_env_master",
                "category": "environment_anchor",
                "setting": "real_env",
                "scene_id": "LF_ENV_MASTER",
                "generation_order": 1,
                "conditioned_on": [],
                "present_cast": [],
                "track": "track_b",
                "scene": "Wide sunlit minimalist walnut-and-plaster architectural bedroom and study suite with crisp linen bedding, warm brass bedside lamp without numerals, and clean unmarked walls",
            },
            {
                "ref_id": "ref_lf_cast_subject",
                "category": "cast_anchor",
                "setting": "real_env",
                "scene_id": "LF_CAST_SUBJECT",
                "generation_order": 2,
                "conditioned_on": ["ref_lf_env_master"],
                "present_cast": ["subject"],
                "track": "track_b",
                "scene": "Full-body three-quarter widescreen portrait of one articulated matte-white porcelain adult figure with a smooth featureless oval head wearing a slate-blue woven sleepwear cardigan and dark trousers inside the sunlit walnut bedroom",
            },
            {
                "ref_id": "ref_lf_cast_researcher",
                "category": "cast_anchor",
                "setting": "real_env",
                "scene_id": "LF_CAST_RESEARCHER",
                "generation_order": 2,
                "conditioned_on": ["ref_lf_env_master"],
                "present_cast": ["researcher"],
                "track": "track_b",
                "scene": "Full-body three-quarter widescreen portrait of one articulated matte-white porcelain clinical sleep researcher with a smooth featureless oval head in a crisp white laboratory coat over charcoal wool attire in a bright sleep laboratory",
            },
            {
                "ref_id": "ref_lf_brain_master",
                "category": "brain_anchor",
                "setting": "brain_studio",
                "scene_id": "LF_BRAIN_MASTER",
                "generation_order": 1,
                "conditioned_on": [],
                "present_cast": [],
                "track": "track_b",
                "scene": "Inside a bright white architectural studio gallery, a Contained Living 4-Color 3D Brain sagittal cutaway model on a matte-white pedestal with enclosed internal electric cyan-blue perivascular fluid channels, warm amber-gold thalamic hubs, crimson-red stress nodes, and pearl-aqua cerebrospinal waves",
            },
        ]

    all_specs: list[dict[str, Any]] = []
    for idx, anc in enumerate(raw_anchors, start=1):
        ref_id = str(anc.get("ref_id") or f"ref_lf_{idx:02d}").strip()
        setting = str(anc.get("setting") or ("brain_studio" if "brain" in ref_id else "real_env")).strip()
        is_brain = setting in (*BRAIN_SETTINGS, "brain_studio")
        clean_desc = sanitize_longform_scene_props(str(anc.get("scene") or anc.get("prompt") or ""))
        if is_brain:
            prompt_16x9 = (
                "Generate a single 16:9 horizontal widescreen still photograph (1920x1080 widescreen composition, not a video): "
                f"{clean_desc}. Enclosed internal subsurface glow only (electric cyan-blue, crimson-red, warm amber-gold, pearl-aqua; "
                f"zero uncontained neon-green particle mist). {PORCELAIN_V7_OPTICS_LOCK}. "
                "Zero text, zero letters, zero numbers, zero labels, no watermark."
            )
        else:
            prompt_16x9 = (
                "Generate a single 16:9 horizontal widescreen architectural documentary still photograph (1920x1080 landscape frame): "
                f"In a {PORCELAIN_V7_WORLD_STYLE}, {clean_desc}. "
                f"Every human role is staged as {PORCELAIN_V7_CAST_STYLE} in tailored fabric attire. "
                f"{PORCELAIN_V7_OPTICS_LOCK}. Clean unmarked walls, zero text, zero clock digits, zero labels, no watermark."
            )
        spec_entry: dict[str, Any] = {
            "ref_id": ref_id,
            "filename": str(anc.get("filename") or f"{ref_id}.png"),
            "category": str(anc.get("category") or ("brain_anchor" if is_brain else "clip_keyframe_anchor")),
            "role": str(anc.get("role") or ("mechanism" if is_brain else "reenactment")),
            "scene_id": str(anc.get("scene_id") or f"LF_S{idx:02d}"),
            "setting": setting,
            "style_profile": PORCELAIN_V7_STYLE_PROFILE,
            "aspect": FLOW_ASPECT_LONGFORM,
            "track": str(anc.get("track") or "track_b"),
            "generation_order": int(anc.get("generation_order") or (1 if not anc.get("conditioned_on") else 2)),
            "conditioned_on": list(anc.get("conditioned_on") or []),
            "present_cast": list(anc.get("present_cast") or []),
            "prompt": prompt_16x9,
        }
        for opt_k in ("source_shot_id", "source_url", "reenactment_section"):
            if anc.get(opt_k):
                spec_entry[opt_k] = anc[opt_k]
        all_specs.append(spec_entry)

    payload = {
        "schema": "longform_reference_image_specs_v1",
        "project_id": project_dir.name,
        "aspect": FLOW_ASPECT_LONGFORM,
        "resolution": [LONGFORM_VIDEO_WIDTH, LONGFORM_VIDEO_HEIGHT],
        "style_profile": PORCELAIN_V7_STYLE_PROFILE,
        "total_specs": len(all_specs),
        "all_specs": all_specs,
    }
    specs_out = project_dir / "03_visuals" / "reference_image_specs.json"
    specs_out.parent.mkdir(parents=True, exist_ok=True)
    specs_out.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return payload


def inspect_longform_reference_pack(
    project_dir: Path,
    *,
    specs_payload: dict[str, Any] | None = None,
    source_dhashes: list[str] | None = None,
    save_report: bool = True,
) -> dict[str, Any]:
    """Evaluates all `1920x1080` (`16:9`) reference PNGs across `Q1–Q10` and provenance."""
    p_dir = Path(project_dir)
    vis_dir = p_dir / "03_visuals"
    ref_dir = vis_dir / REF_IMAGES_DIRNAME
    specs_doc = specs_payload or (
        json.loads((vis_dir / "reference_image_specs.json").read_text(encoding="utf-8"))
        if (vis_dir / "reference_image_specs.json").exists()
        else build_longform_reference_specs(p_dir)
    )
    all_specs = list(specs_doc.get("all_specs") or [])
    prov = load_provenance(p_dir)

    per_img: list[dict[str, Any]] = []
    hists: dict[str, np.ndarray] = {}
    blocking: list[str] = []
    regen_ids: list[str] = []

    for sp in all_specs:
        fn = str(sp.get("filename") or f"{sp['ref_id']}.png")
        fp = ref_dir / fn
        rep = inspect_single_reference_image(fp, sp, aspect=FLOW_ASPECT_LONGFORM)
        if "_hist" in rep:
            hists[rep["ref_id"]] = rep.pop("_hist")
        rep["path"] = f"03_visuals/{REF_IMAGES_DIRNAME}/{fn}"
        rep["provenance"] = prov.get(fn, "")
        if source_dhashes and rep.get("dhash_64"):
            min_dh = min((_hamming_hex(rep["dhash_64"], sdh) for sdh in source_dhashes), default=64)
            rep["min_source_dhash"] = min_dh
            if min_dh < REENACT_MIN_DHASH_DISTANCE:
                rep["passed"] = False
                rep.setdefault("failed_axes", []).append("RQ2_source_dhash_distance")
        if not rep.get("passed") or not rep["provenance"]:
            regen_ids.append(str(sp["ref_id"]))
            blocking.append(f"{sp['ref_id']}: failed={rep.get('failed_axes')} prov={rep['provenance']!r}")
        per_img.append(rep)

    # Q8 & Q10 cross-image palette coherence and diversity across real_env rooms
    real_reps = [r for r in per_img if r.get("exists") and r.get("setting") == "real_env"]
    corrs: list[float] = []
    min_pair_dhash = 64
    for i in range(len(real_reps)):
        for j in range(i + 1, len(real_reps)):
            h1, h2 = hists.get(real_reps[i]["ref_id"]), hists.get(real_reps[j]["ref_id"])
            if h1 is not None and h2 is not None:
                corrs.append(_hist_corr(h1, h2))
            dh_ij = _hamming_hex(real_reps[i].get("dhash_64", ""), real_reps[j].get("dhash_64", ""))
            min_pair_dhash = min(min_pair_dhash, dh_ij)
    mean_corr = round(float(np.mean(corrs)), 4) if corrs else 0.88
    luma_spread = (
        round(max(float(r["luma_mean"]) for r in real_reps) - min(float(r["luma_mean"]) for r in real_reps), 2)
        if len(real_reps) >= 2
        else 0.0
    )
    q8_ok = bool(mean_corr >= min(0.48, REF_IMAGE_CROSS_HIST_CORR_MIN) and luma_spread <= max(68.0, REF_IMAGE_CROSS_LUMA_SPREAD_MAX))
    q10_ok = bool(min_pair_dhash >= 2)
    if not q8_ok:
        blocking.append(f"Q8 palette spread/corr out of bounds (corr={mean_corr}, luma_spread={luma_spread})")
    if not q10_ok:
        blocking.append(f"Q10 duplicate reference images detected (min_pair_dhash={min_pair_dhash})")

    cv_ready = bool(len(all_specs) >= 4 and len(regen_ids) == 0 and q8_ok and q10_ok)
    report = {
        "schema": "longform_reference_qa_report_v1",
        "project_id": p_dir.name,
        "aspect": FLOW_ASPECT_LONGFORM,
        "resolution": [LONGFORM_VIDEO_WIDTH, LONGFORM_VIDEO_HEIGHT],
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "total_specs": len(all_specs),
        "total_existing": sum(1 for r in per_img if r.get("exists")),
        "cv_pre_generation_ready": cv_ready,
        "pre_generation_ready": cv_ready,
        "q8_palette_coherence_ok": q8_ok,
        "q8_mean_hist_corr": mean_corr,
        "q8_luma_spread": luma_spread,
        "q10_diversity_ok": q10_ok,
        "q10_min_pair_dhash": min_pair_dhash,
        "regenerate_image_ids": regen_ids,
        "blocking_reasons": blocking,
        "images": per_img,
    }
    if save_report:
        (vis_dir / "reference_image_qa_report.json").write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    return report


def render_longform_ref_contact_sheet(project_dir: Path, specs_payload: dict[str, Any]) -> Path:
    """Renders a crisp `16:9` 2-column visual inspection contact sheet (`03_visuals/longform_ref_contact_sheet.png`)."""
    ref_dir = project_dir / "03_visuals" / REF_IMAGES_DIRNAME
    specs = list(specs_payload.get("all_specs") or [])
    cols = 2
    rows = max(1, (len(specs) + cols - 1) // cols)
    tw, th = 640, 360
    pad = 24
    label_h = 38
    sheet = np.full((rows * (th + label_h + pad) + pad, cols * (tw + pad) + pad, 3), (24, 28, 34), dtype=np.uint8)

    for idx, sp in enumerate(specs):
        r_i, c_i = divmod(idx, cols)
        x0 = pad + c_i * (tw + pad)
        y0 = pad + r_i * (th + label_h + pad)
        fp = ref_dir / str(sp.get("filename") or f"{sp['ref_id']}.png")
        if fp.exists():
            im = cv2.imread(str(fp))
            if im is not None:
                tile = cv2.resize(im, (tw, th), interpolation=cv2.INTER_AREA)
                sheet[y0 : y0 + th, x0 : x0 + tw] = tile
        lbl = f"{sp['ref_id']} [{sp.get('track', 'track_b')}] ({sp.get('setting')})"
        cv2.putText(sheet, lbl[:56], (x0 + 6, y0 + th + 26), cv2.FONT_HERSHEY_SIMPLEX, 0.56, (235, 240, 246), 1, cv2.LINE_AA)

    out_p = project_dir / "03_visuals" / "longform_ref_contact_sheet.png"
    cv2.imwrite(str(out_p), sheet)
    return out_p


def _bind_longform_anchors_to_plan(project_dir: Path, specs_payload: dict[str, Any]) -> None:
    """Binds verified `16:9` `reference_images/*.png` paths onto `visual_plan.json` & `flow_longform_prompts.json` clips."""
    vp_path = project_dir / "03_visuals" / "visual_plan.json"
    if not vp_path.exists():
        return
    vp_doc = json.loads(vp_path.read_text(encoding="utf-8"))
    ref_dir = project_dir / "03_visuals" / REF_IMAGES_DIRNAME
    valid_ids = {
        str(sp["ref_id"]): f"03_visuals/{REF_IMAGES_DIRNAME}/{sp['filename']}"
        for sp in (specs_payload.get("all_specs") or [])
        if (ref_dir / str(sp["filename"])).exists()
    }
    brain_ref = next((v for k, v in valid_ids.items() if "brain" in k), None)

    for c in vp_doc.get("clips") or []:
        g = str(c.get("grammar") or "")
        anc_id = str(c.get("reference_anchor_id") or "")
        if g in ("porcelain_hands_closeup", "porcelain_pov_hands"):
            # Keep macro closeups unanchored so Frame 0 isn't locked to a wide establishing shot
            c.pop("reference_image", None)
        elif g == "porcelain_living_brain" and brain_ref:
            c["reference_image"] = valid_ids.get(anc_id, brain_ref)
        elif anc_id in valid_ids:
            c["reference_image"] = valid_ids[anc_id]

    vp_path.write_text(json.dumps(vp_doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    prompts_path = project_dir / "03_visuals" / "flow_longform_prompts.json"
    if prompts_path.exists():
        p_doc = json.loads(prompts_path.read_text(encoding="utf-8"))
        ref_by_num = {int(c["clip_number"]): c.get("reference_image") for c in (vp_doc.get("clips") or [])}
        for pc in p_doc.get("clips") or []:
            ri = ref_by_num.get(int(pc["clip_number"]))
            if ri:
                pc["reference_image"] = ri
            else:
                pc.pop("reference_image", None)
        prompts_path.write_text(json.dumps(p_doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _normalize_generated_png_16x9(png_path: Path) -> None:
    im = cv2.imread(str(png_path))
    if im is None or im.size == 0:
        return
    h, w = im.shape[:2]
    target_ratio = float(LONGFORM_VIDEO_WIDTH) / float(LONGFORM_VIDEO_HEIGHT)
    cur_ratio = float(w) / max(1.0, float(h))
    if cur_ratio > target_ratio:
        nw = int(round(h * target_ratio))
        x0 = max(0, (w - nw) // 2)
        im = im[:, x0 : x0 + nw]
    elif cur_ratio < target_ratio:
        nh = int(round(w / target_ratio))
        y0 = max(0, (h - nh) // 2)
        im = im[y0 : y0 + nh, :]
    if im.shape[1] != LONGFORM_VIDEO_WIDTH or im.shape[0] != LONGFORM_VIDEO_HEIGHT:
        im = cv2.resize(im, (LONGFORM_VIDEO_WIDTH, LONGFORM_VIDEO_HEIGHT), interpolation=cv2.INTER_LANCZOS4)
    cv2.imwrite(str(png_path), im)


def _open_isolated_gemini_tab_16x9(cdp_port: int = DEFAULT_CDP_PORT) -> dict[str, str]:
    """Opens an isolated `https://gemini.google.com/images` tab via CDP without touching existing user tabs."""
    target_url = f"http://127.0.0.1:{cdp_port}/json/new?https://gemini.google.com/images"
    try:
        req = urllib.request.Request(target_url, method="PUT")
        with urllib.request.urlopen(req, timeout=8) as r:
            info = json.loads(r.read().decode("utf-8"))
    except Exception:
        with urllib.request.urlopen(target_url, timeout=8) as r:
            info = json.loads(r.read().decode("utf-8"))
    return {"tab_id": str(info["id"]), "ws_url": str(info["webSocketDebuggerUrl"])}


async def _ensure_gemini_images_16x9_mode(client: Any, force_reload: bool = False) -> None:
    """Ensures `https://gemini.google.com/images` has `16:9` widescreen selected (isolated from Shorts `9:16`)."""
    from pipeline.gemini_web_worker import cdp_click_xy, eval_js, navigate_to

    cur_url = await eval_js(client, "location.href") or ""
    if force_reload or "gemini.google.com" not in str(cur_url):
        await navigate_to(client, "https://gemini.google.com/images", wait_sec=5.0)
        await asyncio.sleep(1.5)

    ar_pos = await eval_js(
        client,
        """
        JSON.stringify((() => {
            for (const el of document.querySelectorAll("button, mat-chip, [role=button]")) {
                const r = el.getBoundingClientRect();
                const txt = (el.innerText || "").trim();
                const al = el.getAttribute("aria-label") || "";
                if (r.width > 0 && (txt === "16:9" || al.includes("16:9"))) {
                    return {already_16x9: true, x: Math.round(r.left + r.width/2), y: Math.round(r.top + r.height/2)};
                }
                if (r.width > 0 && (txt.includes("Aspect ratio") || al.includes("Aspect ratio") || txt === "1:1" || txt === "9:16")) {
                    return {already_16x9: false, x: Math.round(r.left + r.width/2), y: Math.round(r.top + r.height/2)};
                }
            }
            return null;
        })())
        """,
    )
    info = json.loads(ar_pos) if ar_pos else None
    if info and not info.get("already_16x9"):
        await cdp_click_xy(client, info["x"], info["y"])
        await asyncio.sleep(1.2)
        item_pos = await eval_js(
            client,
            """
            JSON.stringify((() => {
                const c = document.querySelector(".cdk-overlay-container") || document.body;
                for (const el of c.querySelectorAll("button, [role=menuitem], [role=option], input-companion-item")) {
                    const r = el.getBoundingClientRect();
                    const txt = (el.innerText || "").trim();
                    if (r.width > 0 && (txt.includes("16:9") || txt.toLowerCase().includes("landscape"))) {
                        return {x: Math.round(r.left + r.width/2), y: Math.round(r.top + r.height/2)};
                    }
                }
                return null;
            })())
            """,
        )
        pt = json.loads(item_pos) if item_pos else None
        if pt:
            await cdp_click_xy(client, pt["x"], pt["y"])
            await asyncio.sleep(1.0)


async def _generate_gemini_image_16x9(
    client: Any,
    prompt: str,
    out_path: Path,
    conditioning_paths: list[Path] | None = None,
    force_new_chat: bool = False,
    timeout_sec: int = 120,
) -> bool:
    """Generates a `16:9` widescreen image in Gemini Web App and normalizes to `1920x1080`."""
    import base64
    import time
    from pipeline.gemini_web_worker import eval_js, paste_png_into_editor

    await _ensure_gemini_images_16x9_mode(client, force_reload=force_new_chat)
    await eval_js(
        client,
        """
        (() => {
            const ed = document.querySelector(".ql-editor");
            if (ed) ed.innerHTML = "";
        })()
        """,
    )
    await asyncio.sleep(0.3)

    if conditioning_paths:
        for cp in conditioning_paths[:2]:
            if cp and cp.exists():
                await paste_png_into_editor(client, cp, wait_sec=2.0)

    before_raw = await eval_js(
        client,
        """
        JSON.stringify(
            Array.from(document.querySelectorAll("img"))
                .filter(i => i.naturalWidth > 300 && i.naturalHeight > 300 && !(i.className || "").includes("preview") && !(i.alt || "").includes("Uploaded"))
                .map(i => i.src)
        )
        """,
    )
    before_srcs = set(json.loads(before_raw) if before_raw else [])

    await client.type_into([".ql-editor", "div[contenteditable=true]"], prompt)
    await asyncio.sleep(0.8)
    await client.click(["button[aria-label*='Send']", "button[aria-label*='submit']", "button.send-button"])

    t0 = time.time()
    new_src = None
    while time.time() - t0 < timeout_sec:
        await asyncio.sleep(2.5)
        state_raw = await eval_js(
            client,
            """
            JSON.stringify((() => {
                const imgs = Array.from(document.querySelectorAll("img"))
                    .filter(i => i.naturalWidth > 300 && i.naturalHeight > 300 && i.complete && !(i.className || "").includes("preview") && !(i.alt || "").includes("Uploaded"))
                    .map(i => ({src: i.src, w: i.naturalWidth, h: i.naturalHeight}));
                const bodyTxt = document.body.innerText || "";
                const busy = bodyTxt.includes("Creating your image") || bodyTxt.includes("Generating");
                return {imgs, busy};
            })())
            """,
        )
        st = json.loads(state_raw) if state_raw else {"imgs": [], "busy": False}
        for im in reversed(st["imgs"]):
            if im["src"] not in before_srcs:
                new_src = im["src"]
                break
        if new_src and not st["busy"]:
            await asyncio.sleep(1.0)
            break

    if not new_src:
        return False

    b64_png = await eval_js(
        client,
        f"""
        (() => {{
            const imgs = Array.from(document.querySelectorAll("img"))
                .filter(i => i.src === "{new_src}" || (i.naturalWidth > 300 && i.naturalHeight > 300));
            if (!imgs.length) return null;
            const img = imgs[imgs.length - 1];
            const c = document.createElement("canvas");
            c.width = img.naturalWidth;
            c.height = img.naturalHeight;
            const ctx = c.getContext("2d");
            ctx.drawImage(img, 0, 0);
            return c.toDataURL("image/png");
        }})()
        """,
    )
    if not b64_png or not str(b64_png).startswith("data:image/png;base64,"):
        return False

    raw_bytes = base64.b64decode(str(b64_png).split(",", 1)[1])
    arr = np.frombuffer(raw_bytes, dtype=np.uint8)
    bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if bgr is None:
        return False

    out_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out_path), bgr)
    _normalize_generated_png_16x9(out_path)
    return out_path.exists() and out_path.stat().st_size > 30_000


LONGFORM_TRACK_A_I2I_PREFIX = (
    "Horizontal 16:9 high-key architectural documentary photograph (1920x1080). "
    "Match the room layout, apparatus placement, camera angle, and body pose geometry of the first structural guide image "
    "while transforming every human role into a clothed matte-white porcelain figure with a smooth featureless solid "
    "matte-white egg-shaped oval head matching the cast reference: "
)


def _prepare_longform_track_a_guides(
    *,
    p_dir: Path,
    slug: str,
    ordered_specs: list[dict[str, Any]],
    q_dir: Path,
    guides_dir: Path,
    need_fresh_guides: bool,
) -> list[str]:
    """
    Loads or extracts quarantined `Track A` shots (`extract_source_edl` into `/tmp/aab_reenact_lf/<slug>`),
    sanitizes `16:9` aspect-preserving structural guide PNGs via `sanitize_longform_16x9_guide_frame`,
    updates `03_visuals/source_edl.json` + `<dossier>/08_reenactment_edl.json` (`sanitization_verified: True`),
    and returns `source_dhash_64_list`.
    """
    from pipeline.config import REENACT_EDL_FILENAME
    from pipeline.research_dossier import DOSSIERS_ROOT
    from pipeline.source_reenactment import extract_source_edl

    vis_dir = p_dir / "03_visuals"
    edl_proj_path = vis_dir / REENACT_EDL_FILENAME
    d_dir = DOSSIERS_ROOT / slug
    edl_dossier_path = d_dir / "08_reenactment_edl.json"

    track_a_specs = [
        sp
        for sp in ordered_specs
        if str(sp.get("track") or "").lower() == "track_a"
        and sp.get("setting") not in (*BRAIN_SETTINGS, "brain_studio")
    ]

    existing_edl: dict[str, Any] | None = None
    for cand_p in (edl_proj_path, edl_dossier_path):
        if cand_p.exists():
            try:
                existing_edl = json.loads(cand_p.read_text(encoding="utf-8"))
                break
            except Exception:
                existing_edl = None

    if not track_a_specs:
        return list((existing_edl or {}).get("source_dhash_64_list") or [])

    if not need_fresh_guides and existing_edl:
        if not edl_proj_path.exists():
            edl_proj_path.write_text(json.dumps(existing_edl, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return list(existing_edl.get("source_dhash_64_list") or [])

    # Resolve primary Track A media URL/file + section window from spec or <dossier>/04_media_refs.json
    src_url = ""
    src_sec: str | None = None
    for sp in track_a_specs:
        if sp.get("source_url"):
            src_url = str(sp["source_url"]).strip()
            src_sec = str(sp.get("reenactment_section") or "").strip() or None
            break
    if not src_url and (d_dir / "04_media_refs.json").exists():
        try:
            m_doc = json.loads((d_dir / "04_media_refs.json").read_text(encoding="utf-8"))
            m_list = [m for m in (m_doc.get("media") or []) if isinstance(m, dict)]
            prim_id = str(m_doc.get("primary_reenactment_media_id") or "").strip()
            prim_m = next((m for m in m_list if prim_id and str(m.get("id") or "") == prim_id), None)
            if prim_m is None:
                prim_m = next(
                    (
                        m
                        for m in m_list
                        if str(m.get("reenactment_suitability") or "") in ("suitable_track_a", "needs_section_window")
                    ),
                    m_list[0] if m_list else None,
                )
            if prim_m is not None:
                src_url = str(prim_m.get("url") or "").strip()
                src_sec = str(prim_m.get("reenactment_section") or prim_m.get("recommended_section") or "").strip() or None
        except Exception:
            pass
    if not src_url and existing_edl:
        cand_ref = str(existing_edl.get("source_reference_id") or "").strip()
        if cand_ref.startswith("http") or Path(cand_ref).exists():
            src_url = cand_ref
            src_sec = str(existing_edl.get("section_window") or "").strip() or None

    shots_dir = q_dir / "shots"
    edl_doc = existing_edl
    if src_url and (not shots_dir.exists() or not list(shots_dir.glob("S*_start.png"))):
        edl_doc = extract_source_edl(
            url_or_mp4=src_url,
            slug=slug,
            project_dir=p_dir,
            dossier_dir=d_dir if d_dir.exists() else None,
            work_dir=q_dir,
            section=src_sec,
        )

    shot_pngs = sorted(shots_dir.glob("S*_start.png")) if shots_dir.exists() else []
    source_dhashes: list[str] = list((edl_doc or {}).get("source_dhash_64_list") or [])
    guides_dir.mkdir(parents=True, exist_ok=True)

    if shot_pngs:
        for idx_t, sp in enumerate(track_a_specs):
            req_shot = str(sp.get("source_shot_id") or "").strip()
            chosen_png = None
            if req_shot:
                cand_s = shots_dir / (req_shot if req_shot.endswith(".png") else f"{req_shot}_start.png")
                if cand_s.exists():
                    chosen_png = cand_s
            if chosen_png is None:
                chosen_png = shot_pngs[idx_t % len(shot_pngs)]
            raw_bgr = cv2.imread(str(chosen_png), cv2.IMREAD_COLOR)
            if raw_bgr is None:
                continue
            guide_out = guides_dir / f"{sp['scene_id']}_guide.png"
            san_info = sanitize_longform_16x9_guide_frame(raw_bgr, guide_out)
            dh = str(san_info.get("source_dhash_64") or "")
            if dh and dh not in source_dhashes:
                source_dhashes.append(dh)

        if edl_doc is None:
            edl_doc = {
                "schema": "source_reenactment_edl_v1",
                "rule": "R67",
                "slug": slug,
                "shot_count": len(shot_pngs),
                "shots": [{"shot_id": p.stem.replace("_start", "")} for p in shot_pngs],
                "source_dhash_64_list": source_dhashes,
                "source_5gram_sha256_list": [],
                "source_personal_names": [],
                "zero_raw_pixels_in_repo": True,
            }
        edl_doc["source_dhash_64_list"] = source_dhashes
        edl_doc["sanitization_verified"] = True
        edl_proj_path.write_text(json.dumps(edl_doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        if d_dir.exists():
            edl_dossier_path.write_text(json.dumps(edl_doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    return source_dhashes


def _render_longform_reenactment_comparison_sheet(
    p_dir: Path,
    ordered_specs: list[dict[str, Any]],
    guides_dir: Path,
) -> Path | None:
    """Renders a 16:9 side-by-side comparison sheet (`sanitized 16:9 guide` vs `porcelain 16:9 anchor`) before quarantine purge."""
    ref_dir = p_dir / "03_visuals" / REF_IMAGES_DIRNAME
    rows: list[np.ndarray] = []
    for sp in ordered_specs:
        if str(sp.get("track") or "").lower() != "track_a":
            continue
        g_png = guides_dir / f"{sp['scene_id']}_guide.png"
        r_png = ref_dir / str(sp["filename"])
        if not g_png.exists() or not r_png.exists():
            continue
        g_bgr = cv2.imread(str(g_png), cv2.IMREAD_COLOR)
        r_bgr = cv2.imread(str(r_png), cv2.IMREAD_COLOR)
        if g_bgr is None or r_bgr is None:
            continue
        g_tile = cv2.resize(g_bgr, (640, 360), interpolation=cv2.INTER_AREA)
        r_tile = cv2.resize(r_bgr, (640, 360), interpolation=cv2.INTER_AREA)
        cv2.putText(g_tile, f"GUIDE: {sp['scene_id']}", (16, 34), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (40, 40, 40), 2)
        cv2.putText(r_tile, f"ANCHOR: {sp['ref_id']}", (16, 34), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (25, 110, 40), 2)
        rows.append(np.hstack([g_tile, np.full((360, 12, 3), 245, dtype=np.uint8), r_tile]))
    if not rows:
        return None
    out_sheet = p_dir / "03_visuals" / "reenactment_comparison_sheet.png"
    stacked = rows[0] if len(rows) == 1 else np.vstack(rows)
    cv2.imwrite(str(out_sheet), stacked)
    return out_sheet


async def ensure_longform_reference_pack_async(
    project_id_or_dir: str | Path,
    *,
    cdp_port: int = DEFAULT_CDP_PORT,
    batch_count: int = FLOW_ZERO_CREDIT_IMAGE_BATCH_COUNT,
    backend: str = "flow",
    force: bool = False,
) -> dict[str, Any]:
    """
    Synthesizes & verifies all `1920x1080` (`16:9`) Reference Anchor PNGs via `0-credit` Google Flow `Image` (`x4`)
    (or `--backend gemini` web fallback), never touching pre-existing user tabs and always closing its dedicated
    worker tab + purging quarantine in `finally:`.
    """
    from pipeline.config import REENACT_EDL_FILENAME
    from pipeline.flow_ingredients import generate_flow_image_batch
    from pipeline.flow_live_single_worker import allocate_dedicated_flow_project_tab
    from pipeline.studio.whale_session import DirectCDPClient

    eff_backend = "gemini" if str(backend or "flow").strip().lower() == "gemini" else "flow"
    p_dir = resolve_longform_project_dir(project_id_or_dir, create=False)
    vis_dir = p_dir / "03_visuals"
    ref_dir = vis_dir / REF_IMAGES_DIRNAME
    ref_dir.mkdir(parents=True, exist_ok=True)
    vp_doc = json.loads((vis_dir / "visual_plan.json").read_text(encoding="utf-8"))
    slug = str(vp_doc.get("dossier") or p_dir.name).strip()

    specs_payload = build_longform_reference_specs(p_dir)
    edl_proj_path = vis_dir / REENACT_EDL_FILENAME
    cached_dhashes: list[str] = []
    if edl_proj_path.exists():
        try:
            cached_dhashes = list((json.loads(edl_proj_path.read_text(encoding="utf-8"))).get("source_dhash_64_list") or [])
        except Exception:
            cached_dhashes = []

    if not force:
        cached = inspect_longform_reference_pack(
            p_dir,
            specs_payload=specs_payload,
            source_dhashes=cached_dhashes or None,
            save_report=True,
        )
        has_track_a = any(str(s.get("track") or "").lower() == "track_a" for s in specs_payload["all_specs"])
        if cached.get("cv_pre_generation_ready") and (not has_track_a or bool(cached_dhashes)):
            _bind_longform_anchors_to_plan(p_dir, specs_payload)
            sheet = render_longform_ref_contact_sheet(p_dir, specs_payload)
            return {
                "project_id": p_dir.name,
                "backend": eff_backend,
                "cached": True,
                "cv_pre_generation_ready": True,
                "contact_sheet": str(sheet),
                "qa_report": cached,
            }

    ordered_specs = sorted(specs_payload["all_specs"], key=lambda s: int(s.get("generation_order") or 2))
    q_dir = Path(LONGFORM_QUARANTINE_ROOT) / slug
    guides_dir = q_dir / "guides"

    need_fresh_track_a = bool(force)
    if not need_fresh_track_a:
        for sp in ordered_specs:
            if str(sp.get("track") or "").lower() == "track_a" and sp.get("setting") not in (*BRAIN_SETTINGS, "brain_studio"):
                out_cand = ref_dir / str(sp["filename"])
                if not out_cand.exists() or not cached_dhashes:
                    need_fresh_track_a = True
                    break

    opened_tab_id: str | None = None
    client_cm = None
    client: DirectCDPClient | None = None
    uploaded_cache: set[str] = set()
    seen_img_srcs: set[str] = set()
    existing_prov = load_provenance(p_dir)
    generated: list[str] = []
    failed: list[str] = []
    source_dhashes: list[str] = []

    def _close_tab(tid: str | None) -> None:
        if not tid:
            return
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{cdp_port}/json/close/{tid}", timeout=5):
                pass
        except Exception:
            pass

    try:
        source_dhashes = _prepare_longform_track_a_guides(
            p_dir=p_dir,
            slug=slug,
            ordered_specs=ordered_specs,
            q_dir=q_dir,
            guides_dir=guides_dir,
            need_fresh_guides=need_fresh_track_a,
        )

        for idx_sp, spec in enumerate(ordered_specs, start=1):
            ref_id = str(spec["ref_id"])
            out_png = ref_dir / str(spec["filename"])
            if out_png.exists() and not force:
                chk = inspect_single_reference_image(
                    out_png,
                    spec,
                    aspect=FLOW_ASPECT_LONGFORM,
                    source_dhashes=source_dhashes or None,
                )
                if chk.get("passed"):
                    if out_png.name not in existing_prov:
                        prov_tag = "gemini_image_generation" if eff_backend == "gemini" else "flow_image_generation"
                        register_reference_image(p_dir, out_png.name, prov_tag)
                    generated.append(ref_id)
                    print(f"[longform-refs {idx_sp}/{len(ordered_specs)}] {ref_id}: cached_ok (1920x1080)", flush=True)
                    continue

            cond_paths: list[Path] = []
            has_guide_cond = False
            guide_cand = guides_dir / f"{spec['scene_id']}_guide.png"
            if (
                str(spec.get("track") or "").lower() == "track_a"
                and guide_cand.exists()
                and spec.get("setting") not in (*BRAIN_SETTINGS, "brain_studio")
            ):
                cond_paths.append(guide_cand)
                has_guide_cond = True
            # When Track A guide is slot #1, prioritize a cast reference (`ref_lf_cast_*` / `ref_cast_*`) in slot #2
            ordered_cids = list(spec.get("conditioned_on") or [])
            if has_guide_cond:
                ordered_cids.sort(key=lambda cid: 0 if "cast" in str(cid).lower() else 1)
            for cid in ordered_cids:
                if len(cond_paths) >= 2:
                    break
                cp = ref_dir / f"{cid}.png"
                if cp.exists() and cp not in cond_paths:
                    cond_paths.append(cp)

            eff_prompt_base = (
                f"{LONGFORM_TRACK_A_I2I_PREFIX}{spec['prompt']}"
                if has_guide_cond
                else str(spec["prompt"])
            )

            ok_this = False
            for attempt in range(3):
                try:
                    if client is None:
                        if eff_backend == "gemini":
                            alloc = _open_isolated_gemini_tab_16x9(cdp_port=cdp_port)
                        else:
                            alloc = await allocate_dedicated_flow_project_tab(cdp_port=cdp_port)
                        opened_tab_id = str(alloc["tab_id"])
                        client_cm = DirectCDPClient(str(alloc["ws_url"]))
                        client = await client_cm.__aenter__()
                        await client.send("Page.enable")
                        uploaded_cache.clear()
                        seen_img_srcs.clear()
                        if eff_backend == "gemini":
                            await asyncio.sleep(4.0)

                    retry_tail = (
                        ""
                        if attempt == 0
                        else " Ensure bright high-key daylight architectural exposure, crisp edges, smooth matte-white porcelain oval heads, and full-bleed 16:9 widescreen composition."
                    )
                    if eff_backend == "gemini":
                        print(
                            f"[longform-refs {idx_sp}/{len(ordered_specs)}] Generating {ref_id} (16:9 Gemini fallback, try {attempt + 1}/3)...",
                            flush=True,
                        )
                        gen_ok = await _generate_gemini_image_16x9(
                            client=client,
                            prompt=eff_prompt_base + retry_tail,
                            out_path=out_png,
                            conditioning_paths=cond_paths[:2] if cond_paths else None,
                            force_new_chat=(attempt > 0 or (idx_sp % 5 == 0)),
                        )
                        if gen_ok and out_png.exists():
                            _normalize_generated_png_16x9(out_png)
                            q_chk = inspect_single_reference_image(
                                out_png,
                                spec,
                                aspect=FLOW_ASPECT_LONGFORM,
                                source_dhashes=source_dhashes or None,
                            )
                            if q_chk.get("passed"):
                                register_reference_image(p_dir, out_png.name, "gemini_image_generation")
                                generated.append(ref_id)
                                ok_this = True
                                break
                            out_png.unlink(missing_ok=True)
                    else:
                        print(
                            f"[longform-refs {idx_sp}/{len(ordered_specs)}] Generating {ref_id} (16:9 0-credit x{batch_count}, try {attempt + 1}/3, cond={[p.name for p in cond_paths]})...",
                            flush=True,
                        )
                        flow_res = await generate_flow_image_batch(
                            client=client,
                            prompt=eff_prompt_base + retry_tail,
                            out_path=out_png,
                            conditioning_paths=cond_paths[:2] if cond_paths else None,
                            batch_count=batch_count,
                            aspect=FLOW_ASPECT_LONGFORM,
                            uploaded_cache=uploaded_cache,
                            seen_img_srcs=seen_img_srcs,
                            spec=spec,
                            source_dhashes=source_dhashes or None,
                            project_dir=p_dir,
                        )
                        if flow_res.get("ok") and out_png.exists():
                            generated.append(ref_id)
                            ok_this = True
                            print(
                                f"[longform-refs {idx_sp}/{len(ordered_specs)}] {ref_id}: PASSED 1920x1080 "
                                f"(best_of={flow_res.get('candidate_count')}, score={flow_res.get('quality_score')})",
                                flush=True,
                            )
                            break
                        print(
                            f"[longform-refs {idx_sp}/{len(ordered_specs)}] {ref_id} try {attempt + 1} miss: {flow_res.get('reason')}",
                            flush=True,
                        )
                except Exception as exc:
                    print(f"[longform-refs {idx_sp}/{len(ordered_specs)}] transient CDP error ({exc}); rotating tab...", flush=True)
                    if client_cm is not None:
                        try:
                            await client_cm.__aexit__(None, None, None)
                        except Exception:
                            pass
                    _close_tab(opened_tab_id)
                    client_cm = None
                    client = None
                    opened_tab_id = None
                    await asyncio.sleep(2.0)

            if not ok_this:
                failed.append(ref_id)

        _render_longform_reenactment_comparison_sheet(p_dir, ordered_specs, guides_dir)
    finally:
        if client_cm is not None:
            try:
                await client_cm.__aexit__(None, None, None)
            except Exception:
                pass
        _close_tab(opened_tab_id)
        purge_longform_quarantine(slug)

    qa_rep = inspect_longform_reference_pack(
        p_dir,
        specs_payload=specs_payload,
        source_dhashes=source_dhashes or None,
        save_report=True,
    )
    _bind_longform_anchors_to_plan(p_dir, specs_payload)
    sheet = render_longform_ref_contact_sheet(p_dir, specs_payload)
    return {
        "project_id": p_dir.name,
        "backend": eff_backend,
        "cached": False,
        "generated_ids": generated,
        "failed_ids": failed,
        "cv_pre_generation_ready": bool(qa_rep.get("cv_pre_generation_ready")),
        "contact_sheet": str(sheet),
        "qa_report": qa_rep,
    }


def ensure_longform_reference_pack(
    project_id_or_dir: str | Path,
    *,
    cdp_port: int = DEFAULT_CDP_PORT,
    batch_count: int = FLOW_ZERO_CREDIT_IMAGE_BATCH_COUNT,
    backend: str = "flow",
    force: bool = False,
) -> dict[str, Any]:
    return asyncio.run(
        ensure_longform_reference_pack_async(
            project_id_or_dir,
            cdp_port=cdp_port,
            batch_count=batch_count,
            backend=backend,
            force=force,
        )
    )
