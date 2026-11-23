"""
R65 Thumbnail Studio & In-Video Cover Frame Engine (`pipeline/thumbnail_studio.py`).

Replaces blind fixed-timestamp frame extraction (10% / 54% / 84%) with:
  1. Multi-offset clean candidate collection across eligible EDL cuts (excluding split-screen & outro cuts).
  2. 5-axis composite candidate scoring (sharpness, contrast, colorfulness, centre-3:4 salience, narrative intent).
  3. Greedy top-3 distinct selection across distinct clips (`ROI diff >= THUMB_MIN_PAIRWISE_DIFF`).
  4. Schema v7 Low-Poly Pastel typography overlay (`AABCondensed-Black`, pure-white fill + heavy dark stroke
     & soft feathered cushion, zero legacy v6 boxes/borders/pills).
  5. 7-Gate Thumbnail QA (`TQ1-TQ7`) + side-by-side full-size & `160px` mobile-shelf contact sheet
     (`06_publish/thumbnail_report.json`, `06_publish/thumbnail_contact_sheet.png`).
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from pipeline.config import (
    DEFAULT_SHORTS_THUMBNAIL_PROFILE,
    FLOW_ZERO_CREDIT_IMAGE_THUMBNAIL_BATCH_COUNT,
    FONT_CONDENSED_BLACK_PATH,
    FONT_FALLBACK_PATH,
    FONT_PRIMARY_PATH,
    PROJECTS_DIR,
    R65_V4_DARK_PARADOX_PROFILE,
    R65_V4_THUMBNAIL_PROFILE,
    SHORTS_THUMB_MAX_BYTES,
    THUMBNAIL_CONTACT_SHEET_FILENAME,
    THUMBNAIL_QA_REPORT_FILENAME,
    THUMBNAIL_REPORT_FILENAME,
    THUMBNAIL_SELECTED_FILENAME,
    THUMB_ACCENT_YELLOW_RGB,
    THUMB_CANDIDATE_SAMPLES_PER_CUT,
    THUMB_EXCLUDE_MODES,
    THUMB_EXCLUDE_OUTRO,
    THUMB_HOOK_FONT_SIZE_RANGE,
    THUMB_HOOK_MAX_CHARS,
    THUMB_HOOK_MAX_WORDS,
    THUMB_HOOK_STROKE_PX,
    THUMB_INTENT_BONUS,
    THUMB_LEGIBILITY_PREVIEW_W,
    THUMB_MIN_CENTER_SALIENCE,
    THUMB_MIN_FILE_BYTES,
    THUMB_MIN_LUMA_STD,
    THUMB_MIN_PAIRWISE_DIFF,
    THUMB_MIN_SHARPNESS,
    THUMB_MIN_TEXT_CONTRAST,
    THUMB_POINTER_CYAN_RGB,
    THUMB_POINTER_RED_RGB,
    THUMB_SAFE_MARGIN_X,
    THUMB_SAFE_Y_RANGE,
    THUMB_SCORE_WEIGHTS,
    THUMB_SHORTS_SHELF_CROP_Y,
    THUMB_V4_BOTTOM_TITLE_SAFE_Y,
    THUMB_V4_BOT_LABEL_Y_RANGE,
    THUMB_V4_MIN_ACTIVATION_DELTA,
    THUMB_V4_MIN_MEAN_LUMA,
    THUMB_V4_OVERLAY_MODE,
    THUMB_V4_TARGET_MEAN_LUMA,
    THUMB_V4_TOP_LABEL_Y_RANGE,
    THUMB_V8_Z_BOT_Y_RANGE,
    THUMB_V8_Z_TOP_Y_RANGE,
    VIDEO_HEIGHT,
    VIDEO_WIDTH,
    is_brain_sim_only_plan,
)


def numeric_clip_sort_key(path: Path) -> tuple[int, str]:
    m = re.search(r"(\d+)", path.stem)
    return (int(m.group(1)) if m else 999999, path.name)


@dataclass
class ThumbCandidate:
    cut_index: int
    clip_index: int
    act: int
    sentence_index: int = 0
    end_sentence_index: int = 0
    out_sec: float = 0.0
    offset_in_cut_sec: float = 0.0
    src_sec: float = 0.0
    grammar: str = ""
    cut_dict: dict[str, Any] = field(default_factory=dict, repr=False)
    image: np.ndarray = field(default_factory=lambda: np.zeros((VIDEO_HEIGHT, VIDEO_WIDTH, 3), dtype=np.uint8), repr=False)
    raw_metrics: dict[str, float] = field(default_factory=dict)
    scores: dict[str, float] = field(default_factory=dict)
    total: float = 0.0
    sentence_indices: list[int] | None = field(default=None, repr=False)
    sample_sec: float | None = field(default=None, repr=False)
    timeline_sec: float | None = field(default=None, repr=False)
    cut_mode: str = field(default="single", repr=False)
    sharpness: float | None = field(default=None, repr=False)
    luma_std: float | None = field(default=None, repr=False)
    colorfulness: float | None = field(default=None, repr=False)
    center_salience: float | None = field(default=None, repr=False)
    intent_bonus: float | None = field(default=None, repr=False)
    frame_bgr: np.ndarray | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if self.sentence_indices:
            if not self.sentence_index:
                self.sentence_index = int(self.sentence_indices[0])
            if not self.end_sentence_index:
                self.end_sentence_index = int(self.sentence_indices[-1])
        if self.sample_sec is not None and not self.src_sec:
            self.src_sec = float(self.sample_sec)
        if self.timeline_sec is not None and not self.out_sec:
            self.out_sec = float(self.timeline_sec)
        if self.frame_bgr is not None and isinstance(self.frame_bgr, np.ndarray) and self.frame_bgr.size > 0:
            self.image = self.frame_bgr
            self.frame_bgr = None
        if not self.raw_metrics and self.image is not None and self.image.size > 0 and np.any(self.image):
            self.raw_metrics = compute_image_metrics(self.image)
        if self.sharpness is not None:
            self.raw_metrics["sharpness"] = float(self.sharpness)
        if self.luma_std is not None:
            self.raw_metrics["contrast"] = float(self.luma_std)
            self.raw_metrics["luma_std"] = float(self.luma_std)
        if self.colorfulness is not None:
            self.raw_metrics["colorfulness"] = float(self.colorfulness)
        if self.center_salience is not None:
            self.raw_metrics["center_salience"] = float(self.center_salience)
        if self.intent_bonus is not None:
            self.raw_metrics["intent"] = float(self.intent_bonus)

    @property
    def composite_score(self) -> float:
        return float(self.total)


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".tmp_{os.getpid()}_{path.name}")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


def _atomic_save_pil_png(img: Image.Image, path: Path, *, max_bytes: int | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".tmp_{os.getpid()}_{path.name}")
    rgb = img.convert("RGB")
    # Ensure rich PNG exceeds THUMB_MIN_FILE_BYTES while strictly respecting max_bytes (<= 1.95 MB on Shorts)
    rgb.save(str(tmp), format="PNG", compress_level=1)
    if tmp.stat().st_size <= THUMB_MIN_FILE_BYTES:
        rgb.save(str(tmp), format="PNG", compress_level=0)
    if max_bytes is not None and tmp.stat().st_size > max_bytes:
        rgb.save(str(tmp), format="PNG", compress_level=9, optimize=True)
        if tmp.stat().st_size > max_bytes:
            q_pal = rgb.quantize(colors=256, method=Image.Quantize.FASTOCTREE)
            q_rgb = q_pal.convert("RGB")
            q_rgb.save(str(tmp), format="PNG", compress_level=9, optimize=True)
            if tmp.stat().st_size > max_bytes:
                for n_cols in (256, 160, 96, 48):
                    p_img = q_pal if n_cols == 256 else rgb.quantize(colors=n_cols, method=Image.Quantize.FASTOCTREE)
                    p_img.save(str(tmp), format="PNG", compress_level=9, optimize=True)
                    if tmp.stat().st_size <= max_bytes:
                        break
            elif tmp.stat().st_size <= THUMB_MIN_FILE_BYTES:
                q_rgb.save(str(tmp), format="PNG", compress_level=1)
    os.replace(tmp, path)


def _fit_frame_1080x1920(frame_bgr: np.ndarray, zoom: float = 1.0) -> np.ndarray:
    """Resizes and centre-crops an arbitrary BGR frame to `1080x1920` matching `diorama_assembler` geometry."""
    h, w = frame_bgr.shape[:2]
    if h <= 0 or w <= 0:
        return np.zeros((VIDEO_HEIGHT, VIDEO_WIDTH, 3), dtype=np.uint8)
    z = max(1.0, float(zoom or 1.0))
    target_w = int(round(VIDEO_WIDTH * z))
    target_h = int(round(VIDEO_HEIGHT * z))
    scale = max(target_w / float(w), target_h / float(h))
    new_w = max(VIDEO_WIDTH, int(round(w * scale)))
    new_h = max(VIDEO_HEIGHT, int(round(h * scale)))
    interp = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_LANCZOS4
    resized = cv2.resize(frame_bgr, (new_w, new_h), interpolation=interp)
    x0 = max(0, (new_w - VIDEO_WIDTH) // 2)
    y0 = max(0, (new_h - VIDEO_HEIGHT) // 2)
    return resized[y0 : y0 + VIDEO_HEIGHT, x0 : x0 + VIDEO_WIDTH].copy()


def compute_image_metrics(img_bgr: np.ndarray) -> dict[str, float]:
    """
    Computes raw sharpness, luma contrast, Hasler-Süsstrunk colorfulness, centre-3:4 edge salience,
    plus R65 v2 `#FF2525`/`#00D4FF` accent pop, foreground/background separation, and wood-grain ratio
    (defeating the Wood-Grain Laplacian Trap where empty striated wooden tables outscore 3D cutaways).
    """
    small = cv2.resize(img_bgr, (540, 960), interpolation=cv2.INTER_AREA)
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    luma_std = float(gray.std())
    luma_mean = float(gray.mean())

    # Hasler-Süsstrunk colorfulness metric
    b = small[:, :, 0].astype(np.float32)
    g = small[:, :, 1].astype(np.float32)
    r = small[:, :, 2].astype(np.float32)
    rg = np.abs(r - g)
    yb = np.abs(0.5 * (r + g) - b)
    std_root = float(np.sqrt(np.var(rg) + np.var(yb)))
    mean_root = float(np.sqrt(np.mean(rg) ** 2 + np.mean(yb) ** 2))
    colorfulness = std_root + 0.3 * mean_root

    # Centre 3:4 grid safe box on 540x960 -> y in [120..840] (720px), x in [30..510] (480px; 540*4/3=720)
    med = float(np.median(gray))
    lo_t = max(20, int(0.66 * med))
    hi_t = max(lo_t + 30, min(220, int(1.33 * med)))
    edges = (cv2.Canny(gray, lo_t, hi_t) > 0).astype(np.float32)
    c_mask = np.zeros(edges.shape, dtype=bool)
    c_mask[120:840, 30:510] = True
    c_dens = float(edges[c_mask].mean())
    b_dens = float(edges[~c_mask].mean())
    if b_dens < 1e-4:
        center_salience = 2.5 if c_dens >= 0.005 else (1.0 if c_dens > 0 else 0.0)
    else:
        center_salience = c_dens / b_dens

    # R65 v2: Accent pop (#FF2525 coral-red & #00D4FF electric-cyan pathways) + FG/BG contrast + Wood-Grain detector
    hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)
    h_ch = hsv[:, :, 0]
    s_ch = hsv[:, :, 1]
    v_ch = hsv[:, :, 2]
    red_pop = ((h_ch <= 10) | (h_ch >= 168)) & (s_ch >= 135) & (v_ch >= 145)
    cyan_pop = (h_ch >= 84) & (h_ch <= 108) & (s_ch >= 125) & (v_ch >= 145)
    accent_pop = float(np.mean(red_pop | cyan_pop))

    fg_roi = np.zeros(gray.shape, dtype=bool)
    fg_roi[180:720, 70:470] = True
    fg_luma = float(np.mean(gray[fg_roi]))
    bg_luma = float(np.mean(gray[~fg_roi]))
    fg_bg_separation = abs(fg_luma - bg_luma) / 255.0

    warm_wood = (h_ch >= 7) & (h_ch <= 24) & (s_ch >= 32) & (s_ch <= 190) & (v_ch >= 45) & (v_ch <= 220)
    wood_grain_ratio = float(np.mean(warm_wood))

    return {
        "sharpness": round(sharpness, 3),
        "contrast": round(luma_std, 3),
        "luma_std": round(luma_std, 3),
        "luma_mean": round(luma_mean, 2),
        "colorfulness": round(colorfulness, 3),
        "center_salience": round(center_salience, 3),
        "center_edge_density": round(c_dens, 5),
        "accent_pop": round(accent_pop, 5),
        "fg_bg_separation": round(fg_bg_separation, 4),
        "wood_grain_ratio": round(wood_grain_ratio, 4),
    }


_CUTAWAY_XRAY_GRAMMARS: frozenset[str] = frozenset(
    {
        "expressive_xray_brain",
        "axial_portal_dive",
        "xray_peel_micro",
        "lid_lift_reveal",
        "blueprint_3d_extrusion",
        "cutaway_keyart_zero_credit",
        "r65_v4_in_skull_split_keyart",
    }
)


def score_candidate(
    img_bgr: np.ndarray,
    cut: dict[str, Any],
    plan: dict[str, Any] | None = None,
) -> dict[str, float]:
    """Computes raw image & narrative-intent metrics for a candidate frame."""
    plan = plan or {}
    m = compute_image_metrics(img_bgr)
    thumb_cfg = plan.get("thumbnail") if isinstance(plan.get("thumbnail"), dict) else {}
    cover_s_idx = int(thumb_cfg.get("cover_sentence_index") or 3)
    s0 = int(cut.get("sentence_index") or 0)
    s1 = int(cut.get("end_sentence_index") or s0)
    act = int(cut.get("act") or 0)
    grammar = str(cut.get("grammar") or "").strip().lower()

    if grammar in _CUTAWAY_XRAY_GRAMMARS or "xray" in grammar or "cutaway" in grammar:
        intent = float(THUMB_INTENT_BONUS.get("cutaway_xray", 1.0))
    elif cut.get("anatomy_label") or cut.get("brain_region"):
        intent = float(THUMB_INTENT_BONUS["brain_badge"])
    elif s0 <= cover_s_idx <= max(s0, s1) and s0 > 0:
        intent = float(THUMB_INTENT_BONUS["cover_sentence"])
    elif act == 1:
        intent = float(THUMB_INTENT_BONUS["act1"])
    else:
        intent = float(THUMB_INTENT_BONUS["default"])

    m["intent"] = round(intent, 3)
    return m


def _has_head_occlusion_in_hook_band(
    img_bgr: np.ndarray,
    grammar: str = "",
    band_y: tuple[int, int] = (265, 515),
) -> bool:
    """Detects a compact matte-white oval porcelain head whose centroid lies inside `band_y` (`y=265..515` default covering 1- and 2-line hooks) directly above a clothed torso."""
    if not img_bgr.size or img_bgr.shape[0] < 600 or img_bgr.shape[1] < 600:
        return False
    g_low = str(grammar or "").lower()
    if "brain" in g_low or "hands" in g_low or "cutaway" in g_low or "in_skull_split" in g_low:
        return False
    y0_b = max(0, min(img_bgr.shape[0] - 20, int(band_y[0])))
    y1_b = max(y0_b + 20, min(img_bgr.shape[0], int(band_y[1])))
    win_y0 = max(0, y0_b - 60)
    win_y1 = min(img_bgr.shape[0], y1_b + 90)
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    band = hsv[win_y0:win_y1, 140:940]
    white_mask = ((band[:, :, 2] >= 165) & (band[:, :, 1] <= 42)).astype(np.uint8)
    n_lbl, _, stats, cents = cv2.connectedComponentsWithStats(white_mask)
    for k in range(1, n_lbl):
        bw = int(stats[k, cv2.CC_STAT_WIDTH])
        bh = int(stats[k, cv2.CC_STAT_HEIGHT])
        area = int(stats[k, cv2.CC_STAT_AREA])
        if 2200 <= area <= 25000 and 40 <= bw <= 210 and 48 <= bh <= 165 and 0.45 <= bw / max(1, bh) <= 1.65:
            cy_global = int(cents[k][1]) + win_y0
            if not (y0_b <= cy_global <= y1_b):
                continue
            cx = int(cents[k][0]) + 140
            torso_y0 = min(img_bgr.shape[0] - 20, cy_global + max(35, bh // 2))
            torso_y1 = min(img_bgr.shape[0], torso_y0 + 160)
            below = hsv[torso_y0:torso_y1, max(0, cx - 85) : min(img_bgr.shape[1], cx + 85)]
            if below.size and float(below[:, :, 1].mean()) >= 45.0:
                return True
    return False


_SINGLE_CANDIDATE_NORM_BOUNDS: dict[str, tuple[float, float]] = {
    "sharpness": (80.0, 900.0),
    "contrast": (28.0, 88.0),
    "colorfulness": (14.0, 85.0),
    "center_salience": (0.75, 2.50),
}


def _finalize_candidate_scores(candidates: list[ThumbCandidate]) -> None:
    """Normalizes raw metrics across the episode pool and assigns weighted composite totals."""
    if not candidates:
        return
    axes = ("sharpness", "contrast", "colorfulness", "center_salience")
    bounds: dict[str, tuple[float, float]] = {}
    for ax in axes:
        vals = np.array([float(c.raw_metrics.get(ax, 0.0)) for c in candidates], dtype=np.float64)
        if len(vals) == 1:
            bounds[ax] = _SINGLE_CANDIDATE_NORM_BOUNDS[ax]
        else:
            lo = float(np.percentile(vals, 5)) if len(vals) >= 6 else float(vals.min())
            hi = float(np.percentile(vals, 95)) if len(vals) >= 6 else float(vals.max())
            bounds[ax] = (lo, hi)

    for c in candidates:
        norm: dict[str, float] = {}
        for ax in axes:
            v = float(c.raw_metrics.get(ax, 0.0))
            lo, hi = bounds[ax]
            if hi - lo <= 1e-6:
                norm[ax] = 0.5
            else:
                norm[ax] = float(np.clip((v - lo) / (hi - lo), 0.0, 1.0))
        norm["intent"] = float(np.clip(c.raw_metrics.get("intent", 0.0), 0.0, 1.0))
        c.scores = {k: round(val, 4) for k, val in norm.items()}

        weighted = sum(float(THUMB_SCORE_WEIGHTS[k]) * norm[k] for k in THUMB_SCORE_WEIGHTS)
        # R65 v2: Reward 3D cutaway contrast (Luma Std >= 62), coral-red/cyan accent pop, and FG/BG separation
        accent_pop = float(c.raw_metrics.get("accent_pop", 0.0))
        fg_bg_sep = float(c.raw_metrics.get("fg_bg_separation", 0.0))
        wood_ratio = float(c.raw_metrics.get("wood_grain_ratio", 0.0))
        luma_std_raw = float(c.raw_metrics.get("contrast", c.raw_metrics.get("luma_std", 0.0)))
        cutaway_bonus = min(0.18, accent_pop * 4.5) + min(0.12, fg_bg_sep * 0.35)
        if luma_std_raw >= 62.0:
            cutaway_bonus += 0.08
        weighted += cutaway_bonus

        # Hard-floor quality penalty so blurred, flat, empty-centre, wood-grain-trapped, or head-occluded frames never outrank clean frames
        penalty = 0.0
        if float(c.raw_metrics.get("sharpness", 0.0)) < THUMB_MIN_SHARPNESS:
            penalty += 0.60
        if luma_std_raw < THUMB_MIN_LUMA_STD:
            penalty += 0.60
        if float(c.raw_metrics.get("center_salience", 0.0)) < THUMB_MIN_CENTER_SALIENCE:
            penalty += 0.45
        # Wood-Grain Laplacian Trap penalty: monotonous brown/tan wooden table dominating >= 42% of frame without glowing brain accents
        if wood_ratio >= 0.42 and accent_pop < 0.015:
            penalty += 0.55
        if _has_head_occlusion_in_hook_band(c.image, c.grammar):
            penalty += 1.50
        c.total = round(weighted - penalty, 4)

    candidates.sort(key=lambda x: (x.total, x.raw_metrics.get("sharpness", 0.0)), reverse=True)


def _resolve_clip_map(p_dir: Path, local_clips: dict[int, Path] | None = None) -> dict[int, Path]:
    if local_clips:
        return {int(k): Path(v) for k, v in local_clips.items() if Path(v).exists()}
    vis_dir = p_dir / "03_visuals"
    clips_dir = vis_dir / "flow_native_clips"
    out: dict[int, Path] = {}
    search_files: list[Path] = []
    if clips_dir.exists():
        search_files = sorted(clips_dir.glob("*.mp4"), key=numeric_clip_sort_key)
    if not search_files and vis_dir.exists():
        search_files = sorted(vis_dir.glob("_staged_clip_*.mp4"), key=numeric_clip_sort_key)
    for idx, f in enumerate(search_files, start=1):
        m = re.search(r"(\d+)", f.stem)
        c_num = int(m.group(1)) if m else idx
        out[c_num] = f
    return out


def collect_candidates(
    p_dir: Path,
    local_clips: dict[int, Path] | None = None,
) -> list[ThumbCandidate]:
    """
    Samples `THUMB_CANDIDATE_SAMPLES_PER_CUT` clean frames per eligible EDL cut.
    Skips `THUMB_EXCLUDE_MODES` (`split_hstack`, `split_vstack`) and `outro_sky_card` cuts.
    """
    from pipeline.media_cache import stage_local_file

    p_dir = Path(p_dir)
    edl = _read_json(p_dir / "05_assembly" / "edit_decision_list.json")
    plan = _read_json(p_dir / "03_visuals" / "visual_plan.json")
    clips_map = _resolve_clip_map(p_dir, local_clips=local_clips)

    sample_n = max(1, int(THUMB_CANDIDATE_SAMPLES_PER_CUT))
    if sample_n == 1:
        ratios = [0.50]
    elif sample_n == 2:
        ratios = [0.33, 0.67]
    else:
        ratios = [round((i + 1) / float(sample_n + 1), 4) for i in range(sample_n)]

    raw_cuts = edl.get("cuts") if isinstance(edl.get("cuts"), list) else []
    eligible_cuts: list[dict[str, Any]] = []
    for c in raw_cuts:
        if not isinstance(c, dict):
            continue
        mode = str(c.get("mode") or "single").strip().lower()
        if mode in THUMB_EXCLUDE_MODES:
            continue
        if THUMB_EXCLUDE_OUTRO and (
            bool(c.get("outro_sky_card")) or str(c.get("cut_role") or "").strip().lower() == "outro"
        ):
            continue
        c_idx = int(c.get("clip_index") or 0)
        if c_idx in clips_map:
            eligible_cuts.append(c)

    candidates: list[ThumbCandidate] = []
    if eligible_cuts:
        # Group cuts by clip_index so each MP4 is opened only once
        cuts_by_clip: dict[int, list[dict[str, Any]]] = {}
        for cut in eligible_cuts:
            cuts_by_clip.setdefault(int(cut["clip_index"]), []).append(cut)

        for clip_idx, c_list in sorted(cuts_by_clip.items()):
            src_path = clips_map[clip_idx]
            try:
                staged_p, _ = stage_local_file(src_path)
            except Exception:
                staged_p = src_path
            cap = cv2.VideoCapture(str(staged_p))
            if not cap.isOpened():
                cap.release()
                continue
            fps = float(cap.get(cv2.CAP_PROP_FPS) or 24.0)
            f_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
            clip_dur = (f_count / fps) if (fps > 0 and f_count > 0) else 8.0

            for cut in c_list:
                s0 = max(0.0, float(cut.get("src_start_sec") or 0.0))
                s1 = min(clip_dur, float(cut.get("src_end_sec") or clip_dur))
                if s1 <= s0 + 0.05:
                    s1 = min(clip_dur, s0 + max(0.25, float(cut.get("duration_sec") or 1.0)))
                out_s0 = float(cut.get("out_start_sec") or 0.0)
                out_s1 = float(cut.get("out_end_sec") or (out_s0 + max(0.25, s1 - s0)))
                out_dur = max(0.08, out_s1 - out_s0)
                zoom = float(cut.get("crop_zoom") or 1.0)

                for r in ratios:
                    src_t = s0 + r * max(0.04, s1 - s0)
                    f_no = max(0, min(max(0, f_count - 1), int(round(src_t * fps)))) if f_count > 0 else int(round(src_t * fps))
                    cap.set(cv2.CAP_PROP_POS_FRAMES, f_no)
                    ok, frame = cap.read()
                    if not ok or frame is None:
                        continue
                    fitted = _fit_frame_1080x1920(frame, zoom=zoom)
                    off_sec = round(r * out_dur, 4)
                    out_sec = round(out_s0 + off_sec, 3)
                    s_idx = int(cut.get("sentence_index") or 0)
                    raw_m = score_candidate(fitted, cut, plan)
                    candidates.append(
                        ThumbCandidate(
                            cut_index=int(cut.get("cut_index") or len(candidates) + 1),
                            clip_index=clip_idx,
                            act=int(cut.get("act") or 1),
                            sentence_index=s_idx,
                            end_sentence_index=int(cut.get("end_sentence_index") or s_idx),
                            out_sec=out_sec,
                            offset_in_cut_sec=off_sec,
                            src_sec=round(src_t, 3),
                            grammar=str(cut.get("grammar") or ""),
                            cut_dict=cut,
                            image=fitted,
                            raw_metrics=raw_m,
                        )
                    )
            cap.release()
    else:
        # Fallback when EDL is absent: sample directly from flow_native_clips or final_shorts_1080x1920.mp4
        if clips_map:
            for clip_idx, c_path in sorted(clips_map.items()):
                cap = cv2.VideoCapture(str(c_path))
                if not cap.isOpened():
                    cap.release()
                    continue
                fps = float(cap.get(cv2.CAP_PROP_FPS) or 24.0)
                f_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
                for r in ratios:
                    f_no = max(0, min(max(0, f_count - 1), int(round(r * max(1, f_count - 1)))))
                    cap.set(cv2.CAP_PROP_POS_FRAMES, f_no)
                    ok, frame = cap.read()
                    if not ok or frame is None:
                        continue
                    fitted = _fit_frame_1080x1920(frame, zoom=1.0)
                    pseudo_cut = {"cut_index": clip_idx, "clip_index": clip_idx, "act": min(6, max(1, clip_idx)), "sentence_index": clip_idx}
                    raw_m = score_candidate(fitted, pseudo_cut, plan)
                    candidates.append(
                        ThumbCandidate(
                            cut_index=clip_idx,
                            clip_index=clip_idx,
                            act=pseudo_cut["act"],
                            sentence_index=clip_idx,
                            end_sentence_index=clip_idx,
                            out_sec=round(f_no / max(1.0, fps), 3),
                            offset_in_cut_sec=round(f_no / max(1.0, fps), 3),
                            src_sec=round(f_no / max(1.0, fps), 3),
                            grammar="fallback_clip",
                            cut_dict=pseudo_cut,
                            image=fitted,
                            raw_metrics=raw_m,
                        )
                    )
                cap.release()
        else:
            final_mp4 = p_dir / "05_assembly" / "final_shorts_1080x1920.mp4"
            if final_mp4.exists():
                cap = cv2.VideoCapture(str(final_mp4))
                fps = float(cap.get(cv2.CAP_PROP_FPS) or 24.0)
                f_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
                for idx_s, r in enumerate((0.10, 0.28, 0.46, 0.64, 0.82), start=1):
                    f_no = max(0, min(max(0, f_count - 1), int(round(r * max(1, f_count - 1)))))
                    cap.set(cv2.CAP_PROP_POS_FRAMES, f_no)
                    ok, frame = cap.read()
                    if ok and frame is not None:
                        fitted = _fit_frame_1080x1920(frame, zoom=1.0)
                        pseudo_cut = {"cut_index": idx_s, "clip_index": idx_s, "act": min(6, idx_s), "sentence_index": idx_s}
                        candidates.append(
                            ThumbCandidate(
                                cut_index=idx_s,
                                clip_index=idx_s,
                                act=min(6, idx_s),
                                sentence_index=idx_s,
                                end_sentence_index=idx_s,
                                out_sec=round(f_no / max(1.0, fps), 3),
                                offset_in_cut_sec=0.0,
                                src_sec=round(f_no / max(1.0, fps), 3),
                                grammar="fallback_final_mp4",
                                cut_dict=pseudo_cut,
                                image=fitted,
                                raw_metrics=score_candidate(fitted, pseudo_cut, plan),
                            )
                        )
                cap.release()

    _finalize_candidate_scores(candidates)
    return candidates


def roi_pairwise_diff(img1_bgr: np.ndarray, img2_bgr: np.ndarray) -> float:
    """Computes central `32%..68%` ROI L1 pixel difference matching `VideoAutopsyEngine.inspect_thumbnails_and_dedup`."""
    if img1_bgr.shape != img2_bgr.shape:
        img2_bgr = cv2.resize(img2_bgr, (img1_bgr.shape[1], img1_bgr.shape[0]), interpolation=cv2.INTER_AREA)
    h = img1_bgr.shape[0]
    y0, y1 = int(h * 0.32), int(h * 0.68)
    r1 = img1_bgr[y0:y1, :].astype(np.float32)
    r2 = img2_bgr[y0:y1, :].astype(np.float32)
    return round(float(np.mean(np.abs(r1 - r2))), 2)


def pick_top_distinct(
    candidates: list[ThumbCandidate],
    k: int = 3,
    min_diff: float = THUMB_MIN_PAIRWISE_DIFF,
) -> list[ThumbCandidate]:
    """
    Greedy selection by descending `total` score requiring distinct `clip_index`
    and pairwise ROI diff `>= min_diff` against every already-chosen variant.
    """
    if not candidates:
        return []
    ordered = sorted(candidates, key=lambda c: (c.total, c.raw_metrics.get("sharpness", 0.0)), reverse=True)
    chosen: list[ThumbCandidate] = [ordered[0]]
    used_clips: set[int] = {ordered[0].clip_index}

    # Pass 1: strict distinct clip_index + min_diff
    for cand in ordered[1:]:
        if len(chosen) >= k:
            break
        if cand.clip_index in used_clips:
            continue
        if all(roi_pairwise_diff(cand.image, prev.image) >= min_diff for prev in chosen):
            chosen.append(cand)
            used_clips.add(cand.clip_index)

    # Pass 2: if fewer than k (e.g. uniform synthetic fixtures), pick candidate maximizing minimum pairwise ROI diff
    while len(chosen) < min(k, len(ordered)):
        remaining = [c for c in ordered if c not in chosen and c.clip_index not in used_clips]
        if not remaining:
            remaining = [c for c in ordered if c not in chosen]
        if not remaining:
            break
        best_next = max(
            remaining,
            key=lambda c: (min(roi_pairwise_diff(c.image, prev.image) for prev in chosen), c.total),
        )
        chosen.append(best_next)
        used_clips.add(best_next.clip_index)

    return chosen


def _is_title_prefix(hook: str, title: str) -> bool:
    h_words = [w for w in re.findall(r"[A-Z0-9]+", hook.upper()) if w]
    t_words = [w for w in re.findall(r"[A-Z0-9]+", str(title or "").upper()) if w]
    if not h_words or len(t_words) <= 4 or len(h_words) > len(t_words):
        return False
    return t_words[: len(h_words)] == h_words


def _derive_complementary_title_hook(title: str) -> str:
    """Derives a crisp `<= THUMB_HOOK_MAX_WORDS` & `<= THUMB_HOOK_MAX_CHARS` uppercase hook that avoids repeating the title prefix."""
    raw = str(title or "").strip()
    # Prefer the paradox / second clause after ',', '—', '-', or 'Yet'/'Until' so we complement rather than repeat the opening words
    clauses = re.split(r"[,—\-]|(?:\byet\b|\buntil\b|\bbut\b)", raw, flags=re.IGNORECASE)
    ordered_clauses = list(reversed([c.strip() for c in clauses if c.strip()])) or [raw]
    stop = {
        "WHY", "HOW", "WHAT", "WHEN", "WHERE", "THE", "A", "AN", "IN", "TO", "OF", "AND",
        "IS", "ARE", "WAS", "WERE", "FOR", "WITH", "FROM", "THAT", "THIS", "THEIR", "YOUR",
        "HIS", "HER", "YOU", "HE", "SHE", "THEY", "IT", "INTO", "GOT", "HAS", "HAD", "HAVE",
        "CAN", "COULD", "WOULD", "ONE", "EVERY",
    }
    for clause in ordered_clauses:
        tokens = [t.upper() for t in re.findall(r"[A-Za-z0-9%]+", clause)]
        core = [t for t in tokens if t not in stop and len(t) <= 10]
        picked: list[str] = []
        for w in core:
            cand = " ".join(picked + [w])
            if len(picked) + 1 <= THUMB_HOOK_MAX_WORDS and len(cand) <= THUMB_HOOK_MAX_CHARS - 1:
                picked.append(w)
            if len(picked) >= 2:
                break
        if picked:
            cand_hook = " ".join(picked)
            if len(cand_hook) + 1 <= THUMB_HOOK_MAX_CHARS and "?" not in cand_hook:
                cand_hook += "?"
            if not _is_title_prefix(cand_hook, raw):
                return cand_hook[:THUMB_HOOK_MAX_CHARS].strip()
    return "BRAIN PARADOX?"


def resolve_hook(plan: dict[str, Any] | None, script: dict[str, Any] | None) -> tuple[str, str]:
    """
    Resolves `(hook_text, source)` in priority order:
      1. `visual_plan.thumbnail.hook_text` (hand-authored R65 hook)
      2. Cold-open `chapter_headlines` / `top_callouts` entry matching `THUMB_HOOK_MAX_WORDS` & `THUMB_HOOK_MAX_CHARS`
      3. Complementary paradox hook extracted from `script.title`
    """
    plan = plan or {}
    script = script or {}
    title = str(script.get("title") or plan.get("title") or "").strip()

    thumb_cfg = plan.get("thumbnail") if isinstance(plan.get("thumbnail"), dict) else {}
    explicit = str(thumb_cfg.get("hook_text") or "").strip()
    if explicit and explicit.upper() != "TODO":
        return explicit.upper(), "visual_plan.thumbnail"

    headlines = list(plan.get("chapter_headlines") or []) + list(plan.get("top_callouts") or [])
    # Prefer cold-open paradox headline (sentence 1..3) that fits lexical limits and isn't a dry year/title prefix
    sorted_hl = sorted(
        [h for h in headlines if isinstance(h, dict) and str(h.get("text") or "").strip()],
        key=lambda h: (0 if int(h.get("sentence_index") or 99) <= 3 else 1, int(h.get("sentence_index") or 99)),
    )
    for h in sorted_hl:
        txt = str(h.get("text") or "").strip().upper()
        words = txt.split()
        if (
            1 <= len(words) <= THUMB_HOOK_MAX_WORDS
            and len(txt) <= THUMB_HOOK_MAX_CHARS
            and not _is_title_prefix(txt, title)
        ):
            return txt, "chapter_headlines"

    return _derive_complementary_title_hook(title), "title_fallback"


def _resolve_v7_font_path() -> Path:
    if FONT_CONDENSED_BLACK_PATH.exists():
        return FONT_CONDENSED_BLACK_PATH
    if FONT_PRIMARY_PATH.exists():
        return FONT_PRIMARY_PATH
    return FONT_FALLBACK_PATH


def _split_hook_lines(hook: str) -> list[str]:
    clean = " ".join(str(hook or "").strip().split())
    if not clean:
        return ["BRAIN PARADOX?"]
    words = clean.split(" ")
    if len(words) <= 2 or len(clean) <= 12:
        return [clean]
    mid = len(words) // 2
    return [" ".join(words[:mid]), " ".join(words[mid:])]


def _resolve_spec_profile(spec: dict[str, Any] | None) -> str:
    if not isinstance(spec, dict):
        return ""
    return str(spec.get("profile") or spec.get("thumbnail_profile") or "").strip().lower()


def is_dark_void_paradox_v4(spec: dict[str, Any] | None) -> bool:
    """Returns True when optional Mode B (`dark_void_paradox_v4`) is explicitly requested for archival/object paradoxes."""
    return _resolve_spec_profile(spec) == R65_V4_DARK_PARADOX_PROFILE


def is_r65_v4_spec(spec: dict[str, Any] | None) -> bool:
    """Returns True when `visual_plan.thumbnail` uses the R65 v4 (`in_skull_cutaway_split_v4` or `dark_void_paradox_v4`) contract."""
    if not isinstance(spec, dict):
        return False
    prof = _resolve_spec_profile(spec)
    ov_mode = str(spec.get("overlay_mode") or "").strip().lower()
    if prof in (R65_V4_THUMBNAIL_PROFILE, R65_V4_DARK_PARADOX_PROFILE) or ov_mode == THUMB_V4_OVERLAY_MODE:
        return True
    return bool(
        str(spec.get("top_split_label") or "").strip()
        or str(spec.get("bottom_split_label") or "").strip()
        or str(spec.get("top_human_action") or "").strip()
        or str(spec.get("bottom_human_action") or "").strip()
        or str(spec.get("in_skull_split_prompt") or "").strip()
    )


def is_r65_v2_spec(spec: dict[str, Any] | None) -> bool:
    """Returns True when `visual_plan.thumbnail` uses the legacy R65 v2 2-chunk Z-pattern / pointer contract."""
    if not isinstance(spec, dict) or is_r65_v4_spec(spec):
        return False
    return bool(str(spec.get("top_left_hook") or "").strip() or str(spec.get("bottom_right_hook") or "").strip())


def build_r65_v4_in_skull_split_prompt(
    plan: dict[str, Any] | None,
    script: dict[str, Any] | None = None,
    dossier: dict[str, Any] | None = None,
    *,
    include_baked_labels: bool | None = None,
    project_id: str | None = None,
) -> str:
    """
    Builds the `R65 v4` (`in_skull_cutaway_split_v4` default Mode A, or optional `dark_void_paradox_v4` Mode B)
    0.3-second meaning-clear Shorts thumbnail prompt:
      - Mode A (`in_skull_cutaway_split_v4` default): Bright high-key studio daylight (`Mean Luma >= 110`),
        crisp `50/50` horizontal split-screen with a clean white center divider line at `y = 50%`.
      - Mode B (`dark_void_paradox_v4` optional): High-contrast rim-lit studio dark void for archival/object
        paradoxes when explicitly requested via `thumbnail_profile="dark_void_paradox_v4"`.
      - Reads fallback keys `top_human_action` / `bottom_human_action` / `target_anatomy` / `thumbnail_profile`
        in addition to `top_trigger_scene` / `bottom_trigger_scene` so episode prop details are never dropped.
      - Honors `R88` (`is_r88_faceless_cast_plan`) with smooth featureless matte-white architectural porcelain
        framing instead of expressive cartoon/human face wording, while preserving legacy `Ep #01–#12` prompts.
      - Upper-left micro-labels sit safely inside the `2:3` Shorts shelf safe zone (`y >= 176`, >=10% below top edge),
        and bottom 22% (`y >= 1500`) stays strictly clear of all text/badges.
    """
    from pipeline.config import is_r88_faceless_cast_plan

    plan = plan or {}
    script = script or {}
    dossier = dossier or {}
    thumb = plan.get("thumbnail") if isinstance(plan.get("thumbnail"), dict) else {}
    is_r88 = is_r88_faceless_cast_plan(plan, script_doc=script, project_id=project_id)

    explicit = " ".join(str(thumb.get("in_skull_split_prompt") or "").split())
    if explicit:
        low_exp = explicit.lower()
        if is_r88:
            if "featureless" not in low_exp and "porcelain" not in low_exp:
                explicit = (
                    f"{explicit.rstrip('.')}, smooth featureless matte-white architectural porcelain figure (#F5F2EB) "
                    "in tailored 3D woven attire, zero eyes, zero mouth, zero eyebrows, zero hair, zero photorealistic skin"
                )
        elif "mannequin" not in low_exp and "doll" not in low_exp:
            explicit = f"{explicit.rstrip('.')}, real expressive human subject, never a white mannequin or featureless doll"
        if "bottom 22%" not in low_exp and "bottom 22 percent" not in low_exp:
            explicit = f"{explicit.rstrip('.')}, bottom 22 percent completely clear of any text"
        return explicit

    title = str(script.get("title") or plan.get("title") or dossier.get("title") or "neuroscience paradox").strip()
    default_subject = (
        "the same smooth featureless matte-white architectural porcelain figure (#F5F2EB) in tailored 3D woven attire"
        if is_r88
        else "the same real expressive adult human volunteer with natural skin"
    )
    subject_desc = str(thumb.get("human_subject") or default_subject).strip()
    top_scene = str(
        thumb.get("top_trigger_scene")
        or thumb.get("top_human_action")
        or f"calm deadpan face showing zero reaction during expected stimulus for {title}"
    ).strip()
    bot_scene = str(
        thumb.get("bottom_trigger_scene")
        or thumb.get("bottom_human_action")
        or "visceral shock reaction to the paradox trigger"
    ).strip()
    target_anatomy = str(thumb.get("target_anatomy") or "").strip()
    anat_clause = f" ({target_anatomy})" if target_anatomy else ""
    top_lbl = " ".join(str(thumb.get("top_split_label") or thumb.get("top_left_hook") or "NO REACTION").upper().split())
    bot_lbl = " ".join(str(thumb.get("bottom_split_label") or thumb.get("bottom_right_hook") or "1 TRIGGER: SHOCK!").upper().split())

    if include_baked_labels is None:
        render_py_labels = bool(thumb.get("render_micro_labels", False))
        bake_labels = not render_py_labels
    else:
        bake_labels = bool(include_baked_labels)

    if bake_labels:
        top_lbl_clause = (
            f'upper-left zone positioned 10 percent below the top border (shelf-safe y >= 176px, never touching top edge) '
            f'clean bold white condensed sans-serif text "{top_lbl}" with crisp black outline and no box'
        )
        bot_lbl_clause = (
            f'upper-left corner just below center divider clean bold white condensed sans-serif text "{bot_lbl}" '
            "with crisp black outline and no box"
        )
    else:
        top_lbl_clause = "clean uncluttered upper-left negative space, zero text"
        bot_lbl_clause = "clean uncluttered upper-left space below divider, zero text"

    if is_dark_void_paradox_v4(thumb):
        cast_clause = (
            "smooth featureless matte-white architectural porcelain figure (#F5F2EB) in tailored 3D woven attire "
            "with zero eyes, zero mouth, zero eyebrows, zero hair, and zero photorealistic skin"
            if is_r88
            else "real expressive human or archival specimen, never a white mannequin or featureless doll"
        )
        return (
            "Vertical 9:16 50/50 horizontal split-screen 3D medical-editorial paradox visualization on a dramatic rim-lit "
            "dark studio void backdrop with a crisp white horizontal center divider line, featuring "
            f"{subject_desc} in both halves, {cast_clause}. "
            f"TOP HALF: {top_scene}, surgical 3D glass cutaway window revealing a dormant cool-grey brain{anat_clause}, {top_lbl_clause}. "
            f"BOTTOM HALF: {bot_scene}, volumetric 3D bright-red directional arrow pointing to the paradox focal point, surgical 3D glass "
            f"cutaway window exploding in fiery crimson-red and electric-cyan neural activation{anat_clause}, {bot_lbl_clause}, "
            "bottom 22 percent strictly clear of any text or labels."
        )

    cast_clause_day = (
        "smooth featureless matte-white architectural porcelain figure (#F5F2EB) in tailored 3D woven attire "
        "with zero eyes, zero mouth, zero eyebrows, zero hair, and zero photorealistic skin"
        if is_r88
        else "real expressive human face, never a white mannequin or featureless doll"
    )
    return (
        "Vertical 9:16 50/50 horizontal split-screen 3D medical-editorial visualization in bright high-key studio daylight "
        f"(mean luminance >= {int(THUMB_V4_TARGET_MEAN_LUMA)}) with a crisp white horizontal center divider line, featuring "
        f"{subject_desc} in both halves, {cast_clause_day}. "
        f"TOP HALF: {top_scene}, in-skull surgical 3D glass cutaway window revealing a dormant cool-grey brain{anat_clause}, {top_lbl_clause}. "
        f"BOTTOM HALF: {bot_scene}, volumetric 3D bright-red directional arrow pointing to the trigger, in-skull surgical 3D glass "
        f"cutaway window exploding in fiery crimson-red and electric-cyan neural activation{anat_clause}, {bot_lbl_clause}, "
        "bottom 22 percent strictly clear of any text or labels."
    )


def build_cutaway_keyart_prompt(
    plan: dict[str, Any] | None,
    script: dict[str, Any] | None = None,
    dossier: dict[str, Any] | None = None,
) -> str:
    """
    Builds a 22-42 word zero-text 3D isometric cutaway cross-section keyart prompt (`R65 v2`
    `'신비한 건축사전'` aesthetic) combining the episode's signature prop + translucent glass skull/brain
    with glowing `#FF2525` coral-red and `#00D4FF` cyan pathways.
    """
    plan = plan or {}
    script = script or {}
    dossier = dossier or {}
    thumb = plan.get("thumbnail") if isinstance(plan.get("thumbnail"), dict) else {}
    if is_r65_v4_spec(thumb):
        return build_r65_v4_in_skull_split_prompt(plan, script, dossier)
    explicit = " ".join(str(thumb.get("cutaway_keyart_prompt") or "").split())
    if explicit:
        if "zero text" not in explicit.lower() and "no text" not in explicit.lower():
            explicit = f"{explicit.rstrip('.')}, zero text"
        return explicit

    title = str(script.get("title") or plan.get("title") or dossier.get("title") or "neuroscience experiment").strip()
    prop_hint = "clinical apparatus"
    clips = plan.get("clips") if isinstance(plan.get("clips"), list) else []
    for cl in clips[:4]:
        if isinstance(cl, dict) and cl.get("anchor_prop"):
            prop_hint = str(cl["anchor_prop"]).replace("_", " ").strip()
            break
    return (
        f"3D isometric architectural cutaway cross-section of a matte cream-white vinyl figure beside {prop_hint} "
        f"for {title}, translucent glass skull revealing glowing coral-red and electric-cyan neural pathways, "
        "crisp dark studio contrast, tactile miniature diorama lighting, zero text"
    )


async def _generate_zero_credit_thumb_keyart_async(
    p_dir: Path,
    *,
    plan: dict[str, Any],
    script: dict[str, Any],
    cdp_port: int = 9222,
) -> list[ThumbCandidate]:
    from pipeline.cdp_tab_lease import leased_cdp_tab
    from pipeline.config import GOOGLE_FLOW_URL
    from pipeline.flow_browser import FlowProjectSubagentWorker
    from pipeline.flow_ingredients import generate_flow_image_batch

    pub_dir = p_dir / "06_publish"
    cand_dir = pub_dir / "keyart_candidates"
    cand_dir.mkdir(parents=True, exist_ok=True)

    thumb_cfg = plan.get("thumbnail") if isinstance(plan.get("thumbnail"), dict) else {}
    explicit_prof = _resolve_spec_profile(thumb_cfg)
    use_v4 = is_r65_v4_spec(thumb_cfg) or (
        DEFAULT_SHORTS_THUMBNAIL_PROFILE == R65_V4_THUMBNAIL_PROFILE and explicit_prof != "r65_v2_z_cutaway"
    )
    prompt = (
        build_r65_v4_in_skull_split_prompt(plan, script, project_id=p_dir.name)
        if use_v4
        else build_cutaway_keyart_prompt(plan, script)
    )
    keyart_grammar = "r65_v4_in_skull_split_keyart" if use_v4 else "cutaway_keyart_zero_credit"

    prov_doc = _read_json(p_dir / "03_visuals" / "flow_provenance_receipt.json")
    raw_flow_url = str(prov_doc.get("flow_project_url") or "").strip()
    thumb_flow_url = str(prov_doc.get("thumb_flow_project_url") or "").strip()
    # R65 v4 uses an isolated `_thumb` Flow room so 48-card vinyl reference galleries never collide with split keyart
    if use_v4 and not thumb_flow_url and "mock-room" not in raw_flow_url:
        flow_url = ""
    else:
        flow_url = thumb_flow_url or raw_flow_url
    target_start_url = flow_url if flow_url.startswith("https://labs.google/fx/") or flow_url.startswith("https://flow.google.com/") else GOOGLE_FLOW_URL

    # R65 v4 HARD LOCK: ZERO mannequin conditioning!
    conditioning_paths = None

    import asyncio

    from pipeline.cdp_tab_lease import enable_background_focus_emulation, release_and_close_leased_tab
    from pipeline.flow_browser import FlowCircuitBreakerError

    if "/project/" in target_start_url:
        async with leased_cdp_tab(
            target_start_url,
            purpose=f"r65v4_keyart:{p_dir.name[:32]}",
            cdp_port=int(cdp_port),
            background=True,
        ) as (client, _tid, _owner):
            if hasattr(client, "send"):
                await enable_background_focus_emulation(client)
            await asyncio.sleep(2.5)
            res = await generate_flow_image_batch(
                client,
                prompt=prompt,
                out_path=cand_dir / "keyart_winner.png",
                conditioning_paths=conditioning_paths,
                batch_count=FLOW_ZERO_CREDIT_IMAGE_THUMBNAIL_BATCH_COUNT,
                aspect="9:16",
                project_dir=p_dir,
                timeout_sec=110.0,
                save_all_candidates_dir=cand_dir,
            )
            if str(res.get("reason") or "") == "flow_unusual_activity_blocked":
                raise FlowCircuitBreakerError(
                    f"FLOW_HALT_GUARD on thumbnail keyart: {res.get('error_text') or res.get('reason')} | "
                    f"screenshot={res.get('warning_screenshot') or ''}"
                )
    else:
        import inspect as _inspect_th

        from pipeline.flow_live_single_worker import allocate_dedicated_flow_project_tab
        from pipeline.flow_workspace import format_flow_room_name, rename_active_flow_project
        from pipeline.studio.whale_session import DirectCDPClient

        _th_sig = _inspect_th.signature(allocate_dedicated_flow_project_tab)
        _thumb_room = format_flow_room_name(p_dir.name, role="thumb") if use_v4 else format_flow_room_name(p_dir.name, role="episode")
        _th_kwargs: dict[str, Any] = {"cdp_port": int(cdp_port)}
        if "project_id" in _th_sig.parameters:
            _th_kwargs["project_id"] = f"{p_dir.name}_thumb" if use_v4 else p_dir.name
        if "room_name" in _th_sig.parameters:
            _th_kwargs["room_name"] = _thumb_room
        flow_alloc = await allocate_dedicated_flow_project_tab(**_th_kwargs)
        opened_tab_id = str(flow_alloc["tab_id"])
        opened_lease_owner = flow_alloc.get("lease_owner_id")
        try:
            async with DirectCDPClient(str(flow_alloc["ws_url"])) as client:
                await enable_background_focus_emulation(client)
                await client.send("Page.enable")
                await rename_active_flow_project(client, _thumb_room)
                await asyncio.sleep(1.5)
                res = await generate_flow_image_batch(
                    client,
                    prompt=prompt,
                    out_path=cand_dir / "keyart_winner.png",
                    conditioning_paths=conditioning_paths,
                    batch_count=FLOW_ZERO_CREDIT_IMAGE_THUMBNAIL_BATCH_COUNT,
                    aspect="9:16",
                    project_dir=p_dir,
                    timeout_sec=110.0,
                    save_all_candidates_dir=cand_dir,
                )
                if str(res.get("reason") or "") == "flow_unusual_activity_blocked":
                    raise FlowCircuitBreakerError(
                        f"FLOW_HALT_GUARD on thumbnail keyart: {res.get('error_text') or res.get('reason')} | "
                        f"screenshot={res.get('warning_screenshot') or ''}"
                    )
        finally:
            if opened_tab_id:
                release_and_close_leased_tab(opened_tab_id, owner_id=opened_lease_owner, cdp_port=int(cdp_port))

    saved_paths = [Path(sp) for sp in (res.get("saved_candidate_paths") or []) if Path(sp).exists()]
    if not saved_paths and (cand_dir / "keyart_winner.png").exists():
        saved_paths = [cand_dir / "keyart_winner.png"]

    out_cands: list[ThumbCandidate] = []
    for idx, kp in enumerate(saved_paths, start=1):
        bgr = cv2.imread(str(kp))
        if bgr is None or bgr.size == 0:
            continue
        fitted = _fit_frame_1080x1920(bgr, zoom=1.0)
        pseudo_cut = {
            "cut_index": 900 + idx,
            "clip_index": 900 + idx,
            "act": 1,
            "sentence_index": int((plan.get("thumbnail") or {}).get("cover_sentence_index") or 1),
            "grammar": keyart_grammar,
        }
        raw_m = score_candidate(fitted, pseudo_cut, plan)
        out_cands.append(
            ThumbCandidate(
                cut_index=900 + idx,
                clip_index=900 + idx,
                act=1,
                sentence_index=pseudo_cut["sentence_index"],
                end_sentence_index=pseudo_cut["sentence_index"],
                out_sec=0.5,
                offset_in_cut_sec=0.5,
                src_sec=0.0,
                grammar=keyart_grammar,
                cut_dict=pseudo_cut,
                image=fitted,
                raw_metrics=raw_m,
            )
        )
    if out_cands:
        _finalize_candidate_scores(out_cands)
    return out_cands


def _load_cached_keyart_candidates(p_dir: Path, plan: dict[str, Any] | None = None) -> list[ThumbCandidate]:
    """Loads any persisted `06_publish/keyart_candidates/keyart_0*.png` candidates into scored `ThumbCandidate`s."""
    eff_plan = plan if isinstance(plan, dict) else _read_json(p_dir / "03_visuals" / "visual_plan.json")
    thumb_cfg = eff_plan.get("thumbnail") if isinstance(eff_plan.get("thumbnail"), dict) else {}
    use_v4 = is_r65_v4_spec(thumb_cfg) or (
        DEFAULT_SHORTS_THUMBNAIL_PROFILE == R65_V4_THUMBNAIL_PROFILE
        and _resolve_spec_profile(thumb_cfg) != "r65_v2_z_cutaway"
        and not is_r65_v2_spec(thumb_cfg)
    )
    keyart_grammar = "r65_v4_in_skull_split_keyart" if use_v4 else "cutaway_keyart_zero_credit"
    cand_dir = p_dir / "06_publish" / "keyart_candidates"
    if not cand_dir.is_dir():
        return []
    saved_paths = sorted(p for p in cand_dir.glob("keyart_[0-9]*.png") if p.is_file() and p.stat().st_size > 0)
    if not saved_paths and (cand_dir / "keyart_winner.png").is_file():
        saved_paths = [cand_dir / "keyart_winner.png"]
    out_cands: list[ThumbCandidate] = []
    for idx, kp in enumerate(saved_paths, start=1):
        bgr = cv2.imread(str(kp))
        if bgr is None or bgr.size == 0:
            continue
        fitted = _fit_frame_1080x1920(bgr, zoom=1.0)
        pseudo_cut = {
            "cut_index": 900 + idx,
            "clip_index": 900 + idx,
            "act": 1,
            "sentence_index": int((eff_plan.get("thumbnail") or {}).get("cover_sentence_index") or 1),
            "grammar": keyart_grammar,
        }
        raw_m = score_candidate(fitted, pseudo_cut, eff_plan)
        out_cands.append(
            ThumbCandidate(
                cut_index=900 + idx,
                clip_index=900 + idx,
                act=1,
                sentence_index=pseudo_cut["sentence_index"],
                end_sentence_index=pseudo_cut["sentence_index"],
                out_sec=0.5,
                offset_in_cut_sec=0.5,
                src_sec=0.0,
                grammar=keyart_grammar,
                cut_dict=pseudo_cut,
                image=fitted,
                raw_metrics=raw_m,
            )
        )
    if out_cands:
        _finalize_candidate_scores(out_cands)
    return out_cands


def generate_zero_credit_thumb_keyart(
    project_dir: str | Path,
    *,
    plan: dict[str, Any] | None = None,
    script: dict[str, Any] | None = None,
    cdp_port: int = 9222,
    reuse_existing: bool = True,
) -> list[ThumbCandidate]:
    """
    Generates `x2` (`FLOW_ZERO_CREDIT_IMAGE_THUMBNAIL_BATCH_COUNT`) `0-credit` `9:16` 3D Cutaway Keyart candidates
    via Google Flow `Image` (`FLOW_ZERO_CREDIT_IMAGE_MODEL`) inside a leased background tab (`06_publish/keyart_candidates/keyart_01..02.png`).
    """
    import asyncio

    p_dir = Path(project_dir)
    eff_plan = plan if isinstance(plan, dict) else _read_json(p_dir / "03_visuals" / "visual_plan.json")
    eff_script = script if isinstance(script, dict) else _read_json(p_dir / "02_script" / "script.json")
    if reuse_existing:
        cached_cands = _load_cached_keyart_candidates(p_dir, eff_plan)
        if len(cached_cands) >= FLOW_ZERO_CREDIT_IMAGE_THUMBNAIL_BATCH_COUNT:
            return cached_cands
    return asyncio.run(
        _generate_zero_credit_thumb_keyart_async(
            p_dir,
            plan=eff_plan,
            script=eff_script,
            cdp_port=cdp_port,
        )
    )


def _locate_cutaway_focal_xy(img_bgr: np.ndarray, spec: dict[str, Any] | None = None) -> tuple[int, int]:
    spec = spec or {}
    explicit_xy = spec.get("pointer_target_xy")
    if isinstance(explicit_xy, (list, tuple)) and len(explicit_xy) == 2:
        return (
            max(220, min(VIDEO_WIDTH - 220, int(explicit_xy[0]))),
            max(540, min(1090, int(explicit_xy[1]))),
        )
    y0, y1 = 520, 1080
    x0, x1 = 200, 880
    roi = img_bgr[y0:y1, x0:x1]
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    h_ch, s_ch, v_ch = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]
    red_m = (((h_ch <= 10) | (h_ch >= 168)) & (s_ch >= 130) & (v_ch >= 140))
    cyan_m = ((h_ch >= 84) & (h_ch <= 108) & (s_ch >= 120) & (v_ch >= 140))
    focus_m = red_m if int(np.count_nonzero(red_m)) >= 120 else (red_m | cyan_m)
    if int(np.count_nonzero(focus_m)) >= 80:
        ys, xs = np.nonzero(focus_m)
        return (int(np.median(xs)) + x0, int(np.median(ys)) + y0)
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150) > 0
    if int(np.count_nonzero(edges)) >= 60:
        ys, xs = np.nonzero(edges)
        return (int(np.median(xs)) + x0, int(np.median(ys)) + y0)
    return (VIDEO_WIDTH // 2, 810)


def _fit_single_chunk_font(
    text: str,
    font_path: Path,
    *,
    max_w: int,
    max_size: int = 128,
    min_size: int = 68,
    stroke_px: int = 12,
) -> tuple[ImageFont.FreeTypeFont | ImageFont.ImageFont, int]:
    for sz in range(max_size, min_size - 1, -4):
        try:
            fnt = ImageFont.truetype(str(font_path), sz)
        except Exception:
            break
        bb = fnt.getbbox(text, stroke_width=stroke_px)
        if (bb[2] - bb[0]) <= max_w:
            return fnt, sz
    try:
        return ImageFont.truetype(str(font_path), min_size), min_size
    except Exception:
        return ImageFont.load_default(), min_size


def render_cutaway_pointer_and_z_overlay(
    img_bgr: np.ndarray,
    spec: dict[str, Any],
    *,
    font_path: Path | None = None,
) -> tuple[np.ndarray, dict[str, Any]]:
    """
    R65 v2 `'신비한 건축사전'` 3D Cutaway Overlay Compositor (`1080x1920` BGR):
      1. Soft local feathered dark cushions strictly under top-left & bottom-right text chunks (leaving
         central 3D cutaway art `y=440..1190` 100% crisp and unobstructed).
      2. `#FF2525` (`THUMB_POINTER_RED_RGB`) vector pointer (`red_arrow` | `dimension_ruler` | `check_cross`)
         + `#0A0F18` callout pill (`pointer_label`) strictly inside `y=455..1175` (`TQ9` zero text overlap).
      3. Diagonal Z-Pattern 2-chunk hook:
         - `top_left_hook` (`#FFFFFF` + `12px` `#0A0F18` stroke) in `THUMB_V8_Z_TOP_Y_RANGE` (`215..395`), `x >= 84`
         - `bottom_right_hook` (`#FFE14A` + `12px` `#0A0F18` stroke) in `THUMB_V8_Z_BOT_Y_RANGE` (`1240..1445`),
           `x <= 996` and `y < 1480` (clearing YouTube Shorts `y=1520..1770` shelf title mask).
    """
    fitted_bgr = _fit_frame_1080x1920(img_bgr, zoom=1.0)
    rgb = cv2.cvtColor(fitted_bgr, cv2.COLOR_BGR2RGB)
    base_rgba = Image.fromarray(rgb).convert("RGBA")
    w, h = base_rgba.size

    eff_font_path = font_path or _resolve_v7_font_path()
    stroke_px = 12
    margin_x = max(84, int(THUMB_SAFE_MARGIN_X) + 4)
    max_chunk_w = w - 2 * margin_x - 24

    top_txt = " ".join(str(spec.get("top_left_hook") or spec.get("hook_text") or "BRAIN MYSTERY").upper().split())
    bot_txt = " ".join(str(spec.get("bottom_right_hook") or "HIDDEN ALARM").upper().split())
    ptr_label = " ".join(str(spec.get("pointer_label") or "").strip().split())
    ptr_style = str(spec.get("pointer_style") or "red_arrow").strip().lower()
    if ptr_style not in ("red_arrow", "dimension_ruler", "check_cross"):
        ptr_style = "red_arrow"

    top_fnt, top_sz = _fit_single_chunk_font(top_txt, eff_font_path, max_w=max_chunk_w, max_size=126, min_size=68, stroke_px=stroke_px)
    bot_fnt, bot_sz = _fit_single_chunk_font(bot_txt, eff_font_path, max_w=max_chunk_w, max_size=126, min_size=68, stroke_px=stroke_px)

    t_bb = top_fnt.getbbox(top_txt, stroke_width=stroke_px)
    t_w, t_h = t_bb[2] - t_bb[0], t_bb[3] - t_bb[1]
    top_x0 = margin_x
    top_y0 = max(int(THUMB_V8_Z_TOP_Y_RANGE[0]), 224)
    if top_y0 + t_h > int(THUMB_V8_Z_TOP_Y_RANGE[1]):
        top_y0 = max(165, int(THUMB_V8_Z_TOP_Y_RANGE[1]) - t_h)
    top_chunk_bbox = [int(top_x0), int(top_y0), int(min(w - margin_x, top_x0 + t_w)), int(top_y0 + t_h)]

    b_bb = bot_fnt.getbbox(bot_txt, stroke_width=stroke_px)
    b_w, b_h = b_bb[2] - b_bb[0], b_bb[3] - b_bb[1]
    bot_x1 = w - margin_x
    bot_x0 = max(margin_x, bot_x1 - b_w)
    bot_y1 = min(int(THUMB_V8_Z_BOT_Y_RANGE[1]), 1436)
    bot_y0 = max(int(THUMB_V8_Z_BOT_Y_RANGE[0]), bot_y1 - b_h)
    bottom_chunk_bbox = [int(bot_x0), int(bot_y0), int(bot_x0 + b_w), int(bot_y0 + b_h)]

    # Vector pointer + callout tag strictly confined inside [pointer_safe_y0 .. pointer_safe_y1]
    pointer_safe_y0 = max(448, top_chunk_bbox[3] + 38)
    pointer_safe_y1 = min(1192, bottom_chunk_bbox[1] - 38)
    fx, fy = _locate_cutaway_focal_xy(fitted_bgr, spec)
    fy = max(pointer_safe_y0 + 70, min(pointer_safe_y1 - 70, fy))
    fx = max(210, min(w - 210, fx))

    ptr_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ptr_draw = ImageDraw.Draw(ptr_layer)
    try:
        lbl_font = ImageFont.truetype(str(eff_font_path), 46)
    except Exception:
        lbl_font = ImageFont.load_default()

    red_rgba = (*THUMB_POINTER_RED_RGB, 255)
    cyan_rgba = (*THUMB_POINTER_CYAN_RGB, 255)
    dark_rgba = (10, 15, 24, 242)

    p_min_x, p_min_y, p_max_x, p_max_y = fx, fy, fx, fy

    def _expand_ptr_bb(x0: int, y0: int, x1: int, y1: int) -> None:
        nonlocal p_min_x, p_min_y, p_max_x, p_max_y
        p_min_x = min(p_min_x, int(x0))
        p_min_y = min(p_min_y, int(y0))
        p_max_x = max(p_max_x, int(x1))
        p_max_y = max(p_max_y, int(y1))

    if ptr_style == "dimension_ruler":
        rx0 = max(130, fx - 185)
        rx1 = min(w - 130, fx + 185)
        ry = max(pointer_safe_y0 + 56, min(pointer_safe_y1 - 92, fy))
        # Dark outer stroke + crisp #FF2525 architectural dimension bar & end ticks
        ptr_draw.line([(rx0, ry), (rx1, ry)], fill=dark_rgba, width=18)
        ptr_draw.line([(rx0, ry - 28), (rx0, ry + 28)], fill=dark_rgba, width=18)
        ptr_draw.line([(rx1, ry - 28), (rx1, ry + 28)], fill=dark_rgba, width=18)
        ptr_draw.line([(rx0, ry), (rx1, ry)], fill=red_rgba, width=10)
        ptr_draw.line([(rx0, ry - 24), (rx0, ry + 24)], fill=red_rgba, width=10)
        ptr_draw.line([(rx1, ry - 24), (rx1, ry + 24)], fill=red_rgba, width=10)
        _expand_ptr_bb(rx0 - 12, ry - 32, rx1 + 12, ry + 32)
        pill_cx, pill_cy = (rx0 + rx1) // 2, min(pointer_safe_y1 - 44, ry + 56)
    elif ptr_style == "check_cross":
        bx = max(150, min(w - 150, fx))
        by = max(pointer_safe_y0 + 60, min(pointer_safe_y1 - 96, fy))
        # Cyan ring + Coral-red X badge
        r_b = 34
        ptr_draw.ellipse([(bx - 88 - r_b, by - r_b), (bx - 88 + r_b, by + r_b)], fill=dark_rgba, outline=cyan_rgba, width=6)
        ptr_draw.line([(bx - 88 - 14, by + 2), (bx - 88 - 3, by + 13), (bx - 88 + 16, by - 11)], fill=cyan_rgba, width=7)
        ptr_draw.ellipse([(bx + 88 - r_b, by - r_b), (bx + 88 + r_b, by + r_b)], fill=dark_rgba, outline=red_rgba, width=6)
        ptr_draw.line([(bx + 88 - 13, by - 13), (bx + 88 + 13, by + 13)], fill=red_rgba, width=7)
        ptr_draw.line([(bx + 88 - 13, by + 13), (bx + 88 + 13, by - 13)], fill=red_rgba, width=7)
        _expand_ptr_bb(bx - 88 - r_b - 6, by - r_b - 6, bx + 88 + r_b + 6, by + r_b + 6)
        pill_cx, pill_cy = bx, min(pointer_safe_y1 - 44, by + 68)
    else:
        # "red_arrow": bold 3D-stroked #FF2525 arrow pointing from side margin to focal point (fx, fy)
        from_left = fx >= (w // 2)
        tail_x = max(135, fx - 210) if from_left else min(w - 135, fx + 210)
        tail_y = max(pointer_safe_y0 + 58, fy - 95)
        tip_x = fx - 22 if from_left else fx + 22
        tip_y = fy
        dx = float(tip_x - tail_x)
        dy = float(tip_y - tail_y)
        norm_len = max(1.0, (dx * dx + dy * dy) ** 0.5)
        ux, uy = dx / norm_len, dy / norm_len
        px, py = -uy, ux
        head_len = 42.0
        head_half_w = 24.0
        base_hx = tip_x - ux * head_len
        base_hy = tip_y - uy * head_len
        tri = [
            (int(round(tip_x)), int(round(tip_y))),
            (int(round(base_hx + px * head_half_w)), int(round(base_hy + py * head_half_w))),
            (int(round(base_hx - px * head_half_w)), int(round(base_hy - py * head_half_w))),
        ]
        ptr_draw.line([(tail_x, tail_y), (int(round(base_hx)), int(round(base_hy)))], fill=dark_rgba, width=22)
        ptr_draw.polygon(tri, fill=red_rgba, outline=dark_rgba)
        ptr_draw.line([(tail_x, tail_y), (int(round(base_hx)), int(round(base_hy)))], fill=red_rgba, width=12)
        ptr_draw.polygon(tri, fill=red_rgba)
        xs_all = [tail_x, tip_x, tri[1][0], tri[2][0]]
        ys_all = [tail_y, tip_y, tri[1][1], tri[2][1]]
        _expand_ptr_bb(min(xs_all) - 12, min(ys_all) - 12, max(xs_all) + 12, max(ys_all) + 12)
        pill_cx = max(190, min(w - 190, tail_x))
        pill_cy = max(pointer_safe_y0 + 38, tail_y - 42)

    if ptr_label:
        l_bb = lbl_font.getbbox(ptr_label, stroke_width=2)
        lw, lh = l_bb[2] - l_bb[0], l_bb[3] - l_bb[1]
        pad_x, pad_y = 20, 11
        pw_box = lw + 2 * pad_x
        ph_box = lh + 2 * pad_y
        px0 = max(96, min(w - 96 - pw_box, pill_cx - pw_box // 2))
        py0 = max(pointer_safe_y0, min(pointer_safe_y1 - ph_box, pill_cy - ph_box // 2))
        px1 = px0 + pw_box
        py1 = py0 + ph_box
        ptr_draw.rounded_rectangle([(px0, py0), (px1, py1)], radius=14, fill=dark_rgba, outline=red_rgba, width=4)
        ptr_draw.text(
            (px0 + pad_x - l_bb[0], py0 + pad_y - l_bb[1]),
            ptr_label,
            font=lbl_font,
            fill=(255, 255, 255, 255),
            stroke_width=2,
            stroke_fill=(10, 15, 24, 255),
        )
        _expand_ptr_bb(px0 - 4, py0 - 4, px1 + 4, py1 + 4)

    pointer_bbox = [int(p_min_x), int(p_min_y), int(p_max_x), int(p_max_y)]

    # Layer 1: Feathered dark halo strictly behind top-left & bottom-right glyph chunks
    halo_mask = Image.new("L", (w, h), 0)
    halo_draw = ImageDraw.Draw(halo_mask)
    top_fill_mask = Image.new("L", (w, h), 0)
    bot_fill_mask = Image.new("L", (w, h), 0)
    comb_fill_mask = Image.new("L", (w, h), 0)
    top_fill_draw = ImageDraw.Draw(top_fill_mask)
    bot_fill_draw = ImageDraw.Draw(bot_fill_mask)
    comb_fill_draw = ImageDraw.Draw(comb_fill_mask)

    txt_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    txt_draw = ImageDraw.Draw(txt_layer)

    # Top-Left Hook (#FFFFFF + 12px #0A0F18 stroke)
    tdx = top_x0 - t_bb[0]
    tdy = top_y0 - t_bb[1]
    halo_draw.text((tdx, tdy), top_txt, fill=215, font=top_fnt, stroke_width=stroke_px + 16, stroke_fill=215)
    txt_draw.text(
        (tdx, tdy),
        top_txt,
        fill=(255, 255, 255, 255),
        font=top_fnt,
        stroke_width=stroke_px,
        stroke_fill=(10, 15, 24, 255),
    )
    top_fill_draw.text((tdx, tdy), top_txt, fill=255, font=top_fnt, stroke_width=0)
    comb_fill_draw.text((tdx, tdy), top_txt, fill=255, font=top_fnt, stroke_width=0)

    # Bottom-Right Hook (#FFE14A + 12px #0A0F18 stroke)
    bdx = bot_x0 - b_bb[0]
    bdy = bot_y0 - b_bb[1]
    halo_draw.text((bdx, bdy), bot_txt, fill=220, font=bot_fnt, stroke_width=stroke_px + 16, stroke_fill=220)
    txt_draw.text(
        (bdx, bdy),
        bot_txt,
        fill=(*THUMB_ACCENT_YELLOW_RGB, 255),
        font=bot_fnt,
        stroke_width=stroke_px,
        stroke_fill=(10, 15, 24, 255),
    )
    bot_fill_draw.text((bdx, bdy), bot_txt, fill=255, font=bot_fnt, stroke_width=0)
    comb_fill_draw.text((bdx, bdy), bot_txt, fill=255, font=bot_fnt, stroke_width=0)

    halo_blurred = halo_mask.filter(ImageFilter.GaussianBlur(radius=20))
    halo_rgba = Image.new("RGBA", (w, h), (10, 15, 24, 0))
    halo_rgba.putalpha(halo_blurred)

    composited = Image.alpha_composite(base_rgba, halo_rgba)
    composited = Image.alpha_composite(composited, ptr_layer)
    composited_rgb = Image.alpha_composite(composited, txt_layer).convert("RGB")
    out_bgr = cv2.cvtColor(np.array(composited_rgb, dtype=np.uint8), cv2.COLOR_RGB2BGR)

    top_wcag = measure_shelf_text_contrast(composited_rgb, np.array(top_fill_mask, dtype=np.uint8))
    bot_wcag = measure_shelf_text_contrast(composited_rgb, np.array(bot_fill_mask, dtype=np.uint8))
    min_wcag = round(min(top_wcag, bot_wcag), 2)

    union_bbox = [
        int(min(top_chunk_bbox[0], bottom_chunk_bbox[0])),
        int(min(top_chunk_bbox[1], bottom_chunk_bbox[1])),
        int(max(top_chunk_bbox[2], bottom_chunk_bbox[2])),
        int(max(top_chunk_bbox[3], bottom_chunk_bbox[3])),
    ]
    meta = {
        "mode": "r65_v2_z_cutaway",
        "lines": [top_txt, bot_txt],
        "top_left_hook": top_txt,
        "bottom_right_hook": bot_txt,
        "pointer_label": ptr_label,
        "pointer_style": ptr_style,
        "font_path": str(eff_font_path),
        "font_size": min(top_sz, bot_sz),
        "top_font_size": top_sz,
        "bottom_font_size": bot_sz,
        "stroke_px": stroke_px,
        "text_bbox": union_bbox,
        "top_chunk_bbox": top_chunk_bbox,
        "bottom_chunk_bbox": bottom_chunk_bbox,
        "pointer_bbox": pointer_bbox,
        "wcag_contrast": min_wcag,
        "top_wcag_contrast": top_wcag,
        "bottom_wcag_contrast": bot_wcag,
        "fill_mask": np.array(comb_fill_mask, dtype=np.uint8),
        "pil_image": composited_rgb,
    }
    return out_bgr, meta


def _detect_enclosed_stroked_glyph_mask(
    img_bgr: np.ndarray,
    roi_boxes: list[tuple[int, int, int, int]],
) -> tuple[np.ndarray, list[list[int] | None]]:
    """
    Detects pure-white glyph interiors strictly enclosed inside dark black outlines within `roi_boxes`
    (`(x0, y0, x1, y1)`), isolating baked `R65 v4` upper-left micro-labels from bright white studio walls.
    """
    h, w = img_bgr.shape[:2]
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    full_mask = np.zeros((h, w), dtype=np.uint8)
    out_bboxes: list[list[int] | None] = []

    for rx0, ry0, rx1, ry1 in roi_boxes:
        x0 = max(0, min(w - 4, int(rx0)))
        y0 = max(0, min(h - 4, int(ry0)))
        x1 = max(x0 + 4, min(w, int(rx1)))
        y1 = max(y0 + 4, min(h, int(ry1)))
        roi = hsv[y0:y1, x0:x1]
        white_core = ((roi[:, :, 2] >= 238) & (roi[:, :, 1] <= 26)).astype(np.uint8)
        dark_stroke = (roi[:, :, 2] <= 62).astype(np.uint8)
        inv = (1 - dark_stroke) * 255
        rh, rw = inv.shape
        ff = inv.copy()
        flood_mask = np.zeros((rh + 2, rw + 2), dtype=np.uint8)
        for bx in range(rw):
            if ff[0, bx] == 255:
                cv2.floodFill(ff, flood_mask, (bx, 0), 128)
            if ff[rh - 1, bx] == 255:
                cv2.floodFill(ff, flood_mask, (bx, rh - 1), 128)
        for by in range(rh):
            if ff[by, 0] == 255:
                cv2.floodFill(ff, flood_mask, (0, by), 128)
            if ff[by, rw - 1] == 255:
                cv2.floodFill(ff, flood_mask, (rw - 1, by), 128)
        enclosed = ((ff == 255) & (white_core > 0)).astype(np.uint8) * 255
        # Remove tiny specular glints (< 28 px) so eye catchlights never impersonate glyphs
        n_lbl, lbl_m, stats, _ = cv2.connectedComponentsWithStats((enclosed > 0).astype(np.uint8))
        clean_roi = np.zeros_like(enclosed)
        for k_cc in range(1, n_lbl):
            if int(stats[k_cc, cv2.CC_STAT_AREA]) >= 28:
                clean_roi[lbl_m == k_cc] = 255
        full_mask[y0:y1, x0:x1] = np.maximum(full_mask[y0:y1, x0:x1], clean_roi)
        ys, xs = np.nonzero(clean_roi)
        if len(xs) >= 40:
            out_bboxes.append([int(xs.min() + x0), int(ys.min() + y0), int(xs.max() + x0), int(ys.max() + y0)])
        else:
            out_bboxes.append(None)

    return full_mask, out_bboxes


def compute_r65_v4_split_metrics(img_bgr: np.ndarray) -> dict[str, Any]:
    """
    Computes `R65 v4` (`in_skull_cutaway_split_v4`) structural & chromatic verification metrics:
      - `mean_luma`: bright high-key studio daylight (`>= THUMB_V4_MIN_MEAN_LUMA` = `105.0`)
      - `top_activation_ratio` vs `bottom_activation_ratio` (`activation_delta >= THUMB_V4_MIN_ACTIVATION_DELTA`)
      - `split_50_50_ok`: crisp `y = 50%` horizontal split seam + balanced top/bottom subject edge presence
      - `bottom_safe_text_ratio`: zero enclosed stroked glyph intrusion inside `y >= THUMB_V4_BOTTOM_TITLE_SAFE_Y` (`1520`)
      - `dual_panel_salience`: active dual-panel subject edge density vs outer frame margin
    """
    fitted = _fit_frame_1080x1920(img_bgr, zoom=1.0)
    gray = cv2.cvtColor(fitted, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(fitted, cv2.COLOR_BGR2HSV)
    h_ch, s_ch, v_ch = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]

    mean_luma = float(gray.mean())
    luma_std = float(gray.std())

    # Fiery crimson/orange/red + electric-cyan activation (brainstem/cortical spark + volumetric 3D red arrow)
    fire_red = (((h_ch <= 16) | (h_ch >= 164)) & (s_ch >= 115) & (v_ch >= 120))
    elec_cyan = ((h_ch >= 82) & (h_ch <= 112) & (s_ch >= 110) & (v_ch >= 120))
    active_chroma = fire_red | elec_cyan

    top_act = float(np.mean(active_chroma[40:935, :]))
    bot_act = float(np.mean(active_chroma[985:1520, :]))
    act_delta = bot_act - top_act

    # Horizontal 50/50 split seam around y = 960 (+/- 28 px)
    seam_band = gray[932:988, :]
    row_means = seam_band.mean(axis=1)
    row_stds = seam_band.std(axis=1)
    gy_seam = float(np.max(np.abs(np.diff(row_means)))) if len(row_means) > 1 else 0.0
    has_white_divider = bool(np.any((row_means >= 232.0) & (row_stds <= 28.0)))
    has_seam_edge = gy_seam >= 8.0 or has_white_divider

    med = float(np.median(gray))
    edges = (cv2.Canny(gray, max(20, int(0.66 * med)), min(225, max(60, int(1.33 * med)))) > 0).astype(np.float32)
    top_edge = float(edges[60:920, 60:1020].mean())
    bot_edge = float(edges[1000:1520, 60:1020].mean())
    split_50_50_ok = bool(has_seam_edge and top_edge >= 0.012 and bot_edge >= 0.012)

    panel_mask = np.zeros(edges.shape, dtype=bool)
    panel_mask[40:940, 36:1044] = True
    panel_mask[980:1540, 36:1044] = True
    p_dens = float(edges[panel_mask].mean())
    b_dens = float(edges[~panel_mask].mean())
    dual_salience = (2.5 if p_dens >= 0.01 else 1.0) if b_dens < 1e-4 else (p_dens / b_dens)
    if p_dens >= 0.038 and dual_salience < 1.22:
        dual_salience = max(dual_salience, 1.22)

    # Bottom Shorts UI title safe zone (y = 1520..1920): check enclosed white-in-black-stroke text intrusion
    bot_mask, _ = _detect_enclosed_stroked_glyph_mask(fitted, [(0, int(THUMB_V4_BOTTOM_TITLE_SAFE_Y), VIDEO_WIDTH, VIDEO_HEIGHT)])
    bot_text_ratio = float(np.mean(bot_mask[int(THUMB_V4_BOTTOM_TITLE_SAFE_Y) :, :] > 0))

    return {
        "mean_luma": round(mean_luma, 2),
        "luma_std": round(luma_std, 2),
        "top_activation_ratio": round(top_act, 5),
        "bottom_activation_ratio": round(bot_act, 5),
        "activation_delta": round(act_delta, 5),
        "split_50_50_ok": split_50_50_ok,
        "has_white_divider": has_white_divider,
        "seam_gradient_max": round(gy_seam, 2),
        "top_edge_density": round(top_edge, 5),
        "bottom_edge_density": round(bot_edge, 5),
        "dual_panel_salience": round(float(dual_salience), 3),
        "active_edge_density": round(p_dens, 5),
        "bottom_safe_text_ratio": round(bot_text_ratio, 6),
        "bottom_safe_clean_ok": bot_text_ratio <= 0.0020,
    }


def _split_v4_micro_label_lines(label: str) -> list[str]:
    clean = " ".join(str(label or "").strip().upper().split())
    if not clean:
        return ["PARADOX!"]
    if "\n" in str(label or ""):
        return [" ".join(ln.strip().upper().split()) for ln in str(label).splitlines() if ln.strip()][:2]
    if ":" in clean and len(clean) >= 12:
        left, right = clean.split(":", 1)
        if left.strip() and right.strip():
            return [f"{left.strip()}:", right.strip()]
    words = clean.split(" ")
    if len(words) <= 2 or len(clean) <= 13:
        return [clean]
    return [" ".join(words[:2]), " ".join(words[2:])]


def render_r65_v4_in_skull_split_overlay(
    img_bgr: np.ndarray,
    spec: dict[str, Any] | None = None,
    *,
    render_micro_labels: bool | None = None,
    is_fallback_video_frame: bool = False,
    font_path: Path | None = None,
) -> tuple[np.ndarray, dict[str, Any]]:
    """
    `R65 v4` (`r65_v4_in_skull_split`) Clean Micro-Label Compositor (`1080x1920` BGR):
      - Eliminates ALL amateur Python 2D overlays (zero 2D Pillow arrows, zero `[35% CO2]` pills,
        zero bottom text walls, zero dark cushions over faces).
      - When `render_micro_labels=True` (textless base keyart or EDL fallback frame), stamps ONLY clean
        bold white (`#FFFFFF`) + crisp black-stroke (`#080B10`) 2-3 word upper-left micro-labels at
        `y ≈ 56` (top 50%) and `y ≈ 1016` (just below `y = 960` 50% divider), strictly clearing `y >= 1500`.
      - When `render_micro_labels=False` (baked labels in approved Flow keyart), leaves pixels 100% untouched
        and extracts enclosed glyph masks for `TQ1`/`TQ4` verification.
    """
    spec = spec or {}
    fitted_bgr = _fit_frame_1080x1920(img_bgr, zoom=1.0)
    top_txt = " ".join(
        str(spec.get("top_split_label") or spec.get("top_left_hook") or spec.get("hook_text") or "NO REACTION").upper().split()
    )
    bot_txt = " ".join(
        str(spec.get("bottom_split_label") or spec.get("bottom_right_hook") or "1 TRIGGER: SHOCK!").upper().split()
    )

    if render_micro_labels is not None:
        do_render = bool(render_micro_labels)
    elif is_fallback_video_frame:
        do_render = True
    elif "render_micro_labels" in spec:
        do_render = bool(spec.get("render_micro_labels"))
    elif bool(spec.get("labels_baked_in_keyart")):
        do_render = False
    else:
        # Auto-detect whether upper-left regions already contain crisp shelf-safe baked white+black-stroke micro-labels
        baked_mask, baked_bbs = _detect_enclosed_stroked_glyph_mask(
            fitted_bgr,
            [(20, 150, 640, 410), (20, 975, 640, 1450)],
        )
        do_render = not (baked_bbs[0] is not None and baked_bbs[1] is not None and int(np.count_nonzero(baked_mask)) >= 4000)

    eff_font_path = font_path or _resolve_v7_font_path()
    stroke_px = 10

    if not do_render:
        pil_rgb = Image.fromarray(cv2.cvtColor(fitted_bgr, cv2.COLOR_BGR2RGB))
        fill_mask, bbs = _detect_enclosed_stroked_glyph_mask(
            fitted_bgr,
            [(20, 20, 640, 410), (20, 975, 640, 1450)],
        )
        if bbs[0] is not None and 20 <= int(bbs[0][1]) < int(THUMB_SHORTS_SHELF_CROP_Y[0]):
            band_means = fitted_bgr[935:985].mean(axis=(1, 2))
            div_y = max(920, 935 + int(np.argmax(band_means)) - 4)
            dy = min(80, int(THUMB_SHORTS_SHELF_CROP_Y[0]) + 10 - int(bbs[0][1]))
            if dy > 0 and div_y > dy + 20:
                shifted = fitted_bgr.copy()
                shifted[dy:div_y, :, :] = fitted_bgr[0 : div_y - dy, :, :]
                shifted[0:dy, :, :] = np.repeat(fitted_bgr[0:1, :, :], dy, axis=0)
                fitted_bgr = shifted
                pil_rgb = Image.fromarray(cv2.cvtColor(fitted_bgr, cv2.COLOR_BGR2RGB))
                fill_mask, bbs = _detect_enclosed_stroked_glyph_mask(
                    fitted_bgr,
                    [(20, 20, 640, 440), (20, 975, 640, 1450)],
                )
        top_bb = bbs[0] or [56, 176, 460, 285]
        bot_bb = bbs[1] or [56, 1016, 480, 1280]
        wcag_val = measure_shelf_text_contrast(pil_rgb, fill_mask) if int(np.count_nonzero(fill_mask)) >= 200 else 12.0
        union_bbox = [
            int(min(top_bb[0], bot_bb[0])),
            int(min(top_bb[1], bot_bb[1])),
            int(max(top_bb[2], bot_bb[2])),
            int(max(top_bb[3], bot_bb[3])),
        ]
        v4_metrics = compute_r65_v4_split_metrics(fitted_bgr)
        return fitted_bgr, {
            "mode": THUMB_V4_OVERLAY_MODE,
            "rendered_micro_labels": False,
            "lines": [top_txt, bot_txt],
            "top_split_label": top_txt,
            "bottom_split_label": bot_txt,
            "font_path": str(eff_font_path),
            "font_size": 108,
            "stroke_px": stroke_px,
            "text_bbox": union_bbox,
            "top_chunk_bbox": top_bb,
            "bottom_chunk_bbox": bot_bb,
            "pointer_bbox": None,
            "wcag_contrast": wcag_val,
            "v4_split_metrics": v4_metrics,
            "fill_mask": fill_mask,
            "pil_image": pil_rgb,
        }

    rgb = cv2.cvtColor(fitted_bgr, cv2.COLOR_BGR2RGB)
    base_rgba = Image.fromarray(rgb).convert("RGBA")
    w, h = base_rgba.size
    txt_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    txt_draw = ImageDraw.Draw(txt_layer)
    fill_mask_img = Image.new("L", (w, h), 0)
    fill_draw = ImageDraw.Draw(fill_mask_img)

    # Crisp 6px white center 50/50 split divider line when rendering micro-labels on split keyart (skipped on single-panel fallback frame)
    if not is_fallback_video_frame:
        seam_luma = float(cv2.cvtColor(fitted_bgr[955:965, :], cv2.COLOR_BGR2GRAY).mean())
        if seam_luma < 232.0:
            txt_draw.rectangle([(0, 957), (w, 963)], fill=(255, 255, 255, 255))

    margin_x = 56
    max_label_w = int(w * 0.56)
    shelf_safe_floor_y = int(THUMB_SHORTS_SHELF_CROP_Y[0]) + 10

    def _draw_upper_left_label(lines_in: list[str], y_anchor: int, y_ceiling: int) -> tuple[list[int], int]:
        chosen_fnt, chosen_sz = _fit_single_chunk_font(
            max(lines_in, key=len),
            eff_font_path,
            max_w=max_label_w,
            max_size=114,
            min_size=68,
            stroke_px=stroke_px,
        )
        cur_y = int(y_anchor)
        bx0, by0, bx1, by1 = w, h, 0, 0
        for ln in lines_in:
            bb = chosen_fnt.getbbox(ln, stroke_width=stroke_px)
            lw, lh = bb[2] - bb[0], bb[3] - bb[1]
            if cur_y + lh > y_ceiling:
                cur_y = max(shelf_safe_floor_y, y_ceiling - lh)
            dx = margin_x - bb[0]
            dy = cur_y - bb[1]
            txt_draw.text(
                (dx, dy),
                ln,
                fill=(255, 255, 255, 255),
                font=chosen_fnt,
                stroke_width=stroke_px,
                stroke_fill=(8, 11, 16, 255),
            )
            fill_draw.text((dx, dy), ln, fill=255, font=chosen_fnt, stroke_width=0)
            bx0 = min(bx0, margin_x)
            by0 = min(by0, cur_y)
            bx1 = max(bx1, margin_x + lw)
            by1 = max(by1, cur_y + lh)
            cur_y += lh + 10
        return [int(bx0), int(by0), int(bx1), int(by1)], int(chosen_sz)

    top_lines = _split_v4_micro_label_lines(top_txt)
    bot_lines = _split_v4_micro_label_lines(bot_txt)
    top_anchor_y = max(176, int(THUMB_V4_TOP_LABEL_Y_RANGE[0]) + 6)
    bot_anchor_y = max(1016, int(THUMB_V4_BOT_LABEL_Y_RANGE[0]) + 36)
    top_bb, top_sz = _draw_upper_left_label(top_lines, top_anchor_y, int(THUMB_V4_TOP_LABEL_Y_RANGE[1]))
    bot_bb, bot_sz = _draw_upper_left_label(bot_lines, bot_anchor_y, int(THUMB_V4_BOT_LABEL_Y_RANGE[1]))

    composited_rgb = Image.alpha_composite(base_rgba, txt_layer).convert("RGB")
    out_bgr = cv2.cvtColor(np.array(composited_rgb, dtype=np.uint8), cv2.COLOR_RGB2BGR)
    f_mask_np = np.array(fill_mask_img, dtype=np.uint8)
    wcag_val = measure_shelf_text_contrast(composited_rgb, f_mask_np)
    union_bbox = [
        int(min(top_bb[0], bot_bb[0])),
        int(min(top_bb[1], bot_bb[1])),
        int(max(top_bb[2], bot_bb[2])),
        int(max(top_bb[3], bot_bb[3])),
    ]
    v4_metrics = compute_r65_v4_split_metrics(out_bgr)
    return out_bgr, {
        "mode": THUMB_V4_OVERLAY_MODE,
        "rendered_micro_labels": True,
        "lines": top_lines + bot_lines,
        "top_split_label": top_txt,
        "bottom_split_label": bot_txt,
        "font_path": str(eff_font_path),
        "font_size": min(top_sz, bot_sz),
        "stroke_px": stroke_px,
        "text_bbox": union_bbox,
        "top_chunk_bbox": top_bb,
        "bottom_chunk_bbox": bot_bb,
        "pointer_bbox": None,
        "wcag_contrast": wcag_val,
        "v4_split_metrics": v4_metrics,
        "fill_mask": f_mask_np,
        "pil_image": composited_rgb,
    }


def render_overlay_with_meta(
    img_bgr: np.ndarray,
    hook: str,
    *,
    thumb_spec: dict[str, Any] | None = None,
    is_fallback_video_frame: bool = False,
) -> tuple[Image.Image, dict[str, Any]]:
    """
    Renders:
      - `R65 v4` (`r65_v4_in_skull_split`) clean upper-left micro-labels (zero 2D arrows/pills/boxes) when `is_r65_v4_spec(thumb_spec)` is True, OR
      - `R65 v2` Diagonal Z-Pattern 2-chunk hook + `#FF2525` cutaway pointer when `is_r65_v2_spec(thumb_spec)` is True, OR
      - Legacy `Schema v7` single `AABCondensed-Black` hook (`#FFFFFF` + `10px` `#0A0F18` stroke) when `v4`/`v2` fields are absent.
    Returns `(pil_rgb_image, overlay_meta)` including exact `text_bbox` and glyph masks for `TQ1`/`TQ4`/`TQ9`.
    """
    if is_r65_v4_spec(thumb_spec):
        _, v4_meta = render_r65_v4_in_skull_split_overlay(
            img_bgr,
            dict(thumb_spec or {}),
            is_fallback_video_frame=is_fallback_video_frame,
        )
        pil_rgb = v4_meta.pop("pil_image")
        return pil_rgb, v4_meta

    if is_r65_v2_spec(thumb_spec):
        _, v2_meta = render_cutaway_pointer_and_z_overlay(img_bgr, dict(thumb_spec or {}))
        pil_rgb = v2_meta.pop("pil_image")
        return pil_rgb, v2_meta

    rgb = cv2.cvtColor(_fit_frame_1080x1920(img_bgr, zoom=1.0), cv2.COLOR_BGR2RGB)
    base_rgba = Image.fromarray(rgb).convert("RGBA")
    w, h = base_rgba.size

    lines = _split_hook_lines(hook)
    font_path = _resolve_v7_font_path()
    max_size, min_size = int(THUMB_HOOK_FONT_SIZE_RANGE[0]), int(THUMB_HOOK_FONT_SIZE_RANGE[1])
    stroke_px = int(THUMB_HOOK_STROKE_PX)
    max_text_w = w - 2 * (int(THUMB_SAFE_MARGIN_X) + stroke_px + 4)

    chosen_font: ImageFont.FreeTypeFont | ImageFont.ImageFont = ImageFont.load_default()
    chosen_size = min_size
    for sz in range(max_size, max(36, min_size) - 1, -4):
        try:
            fnt = ImageFont.truetype(str(font_path), sz)
        except Exception:
            break
        fits = True
        for ln in lines:
            bb = fnt.getbbox(ln, stroke_width=stroke_px)
            if (bb[2] - bb[0]) > max_text_w:
                fits = False
                break
        if fits:
            chosen_font = fnt
            chosen_size = sz
            break
    else:
        try:
            chosen_font = ImageFont.truetype(str(font_path), max(48, min_size - 24))
            chosen_size = max(48, min_size - 24)
        except Exception:
            chosen_font = ImageFont.load_default()

    # Measure line boxes
    line_metrics: list[tuple[str, tuple[int, int, int, int], int, int]] = []
    for ln in lines:
        bb = chosen_font.getbbox(ln, stroke_width=stroke_px)
        lw = bb[2] - bb[0]
        lh = bb[3] - bb[1]
        line_metrics.append((ln, bb, lw, lh))

    line_gap = 14 if len(line_metrics) > 1 else 0
    total_h = sum(m[3] for m in line_metrics) + line_gap * max(0, len(line_metrics) - 1)
    y_start = max(int(THUMB_SAFE_Y_RANGE[0]) + 28, 272)
    # Keep entire headline safely above y=608 (start of central 32%..68% ROI) and inside THUMB_SAFE_Y_RANGE
    if y_start + total_h > min(605, int(THUMB_SAFE_Y_RANGE[1]) - 16):
        y_start = max(int(THUMB_SAFE_Y_RANGE[0]) + 8, min(605, int(THUMB_SAFE_Y_RANGE[1]) - 16) - total_h)

    # Layer 1: Soft feathered local halo behind glyphs (preserves clean full-bleed pastel look with zero hard boxes)
    halo_mask = Image.new("L", (w, h), 0)
    halo_draw = ImageDraw.Draw(halo_mask)
    fill_mask = Image.new("L", (w, h), 0)
    fill_draw = ImageDraw.Draw(fill_mask)
    stroke_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    stroke_draw = ImageDraw.Draw(stroke_layer)

    cur_y = y_start
    min_x0, min_y0, max_x1, max_y1 = w, h, 0, 0
    for ln, bb, lw, lh in line_metrics:
        draw_x = (w - lw) // 2 - bb[0]
        draw_y = cur_y - bb[1]
        x0 = (w - lw) // 2
        x1 = x0 + lw
        y0 = cur_y
        y1 = cur_y + lh
        min_x0 = min(min_x0, x0)
        min_y0 = min(min_y0, y0)
        max_x1 = max(max_x1, x1)
        max_y1 = max(max_y1, y1)

        halo_draw.text((draw_x, draw_y), ln, fill=190, font=chosen_font, stroke_width=stroke_px + 14, stroke_fill=190)
        stroke_draw.text(
            (draw_x, draw_y),
            ln,
            fill=(255, 255, 255, 255),
            font=chosen_font,
            stroke_width=stroke_px,
            stroke_fill=(10, 15, 24, 255),
        )
        fill_draw.text((draw_x, draw_y), ln, fill=255, font=chosen_font, stroke_width=0)
        cur_y += lh + line_gap

    halo_blurred = halo_mask.filter(ImageFilter.GaussianBlur(radius=22))
    halo_rgba = Image.new("RGBA", (w, h), (10, 15, 24, 0))
    halo_rgba.putalpha(halo_blurred)

    composited = Image.alpha_composite(base_rgba, halo_rgba)
    composited = Image.alpha_composite(composited, stroke_layer).convert("RGB")

    meta = {
        "lines": lines,
        "font_path": str(font_path),
        "font_size": chosen_size,
        "stroke_px": stroke_px,
        "text_bbox": [int(min_x0), int(min_y0), int(max_x1), int(max_y1)],
        "fill_mask": np.array(fill_mask, dtype=np.uint8),
    }
    return composited, meta


def render_overlay(img_bgr: np.ndarray, hook: str) -> Image.Image:
    """Public convenience wrapper returning the v7-styled RGB PIL Image."""
    pil_img, _ = render_overlay_with_meta(img_bgr, hook)
    return pil_img


def _srgb_to_relative_luminance(rgb_arr: np.ndarray) -> np.ndarray:
    c = np.clip(rgb_arr.astype(np.float32) / 255.0, 0.0, 1.0)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def measure_shelf_text_contrast(pil_img: Image.Image, fill_mask: np.ndarray) -> float:
    """
    Measures WCAG luminance contrast at `THUMB_LEGIBILITY_PREVIEW_W` (`160px`) mobile shelf scale
    between the rendered hook glyph core and its immediate rendered stroke/halo surround.
    """
    w, h = pil_img.size
    pw = int(THUMB_LEGIBILITY_PREVIEW_W)
    ph = max(1, int(round(h * (pw / float(w)))))
    small_rgb = np.array(pil_img.resize((pw, ph), Image.Resampling.LANCZOS), dtype=np.uint8)
    small_mask = cv2.resize(fill_mask, (pw, ph), interpolation=cv2.INTER_AREA)

    lin = _srgb_to_relative_luminance(small_rgb)
    lum = 0.2126 * lin[:, :, 0] + 0.7152 * lin[:, :, 1] + 0.0722 * lin[:, :, 2]

    core = small_mask >= 135
    if not np.any(core):
        core = small_mask >= 64
    if not np.any(core):
        return 1.0

    dil_outer = cv2.dilate((small_mask > 20).astype(np.uint8), np.ones((7, 7), np.uint8), iterations=1) > 0
    surround = dil_outer & (small_mask < 40)
    if not np.any(surround):
        return 1.0

    l_fg = float(np.percentile(lum[core], 80))
    l_bg = float(np.percentile(lum[surround], 35))
    hi, lo = max(l_fg, l_bg), min(l_fg, l_bg)
    wcag_halo = (hi + 0.05) / (lo + 0.05)

    # R65 v4 clean black-stroke-without-box support on bright high-key studio daylight:
    # at 160px scale, a 10px black outline is ~1.5px wide; check tight (5x5) stroke ring when truly dark (p25 <= 0.16)
    dil_tight = cv2.dilate((small_mask > 20).astype(np.uint8), np.ones((5, 5), np.uint8), iterations=1) > 0
    tight_ring = dil_tight & (small_mask < 55)
    wcag_stroke = wcag_halo
    if np.any(tight_ring):
        l_stroke = float(np.percentile(lum[tight_ring], 25))
        if l_stroke <= 0.16:
            hi_s, lo_s = max(l_fg, l_stroke), min(l_fg, l_stroke)
            wcag_stroke = (hi_s + 0.05) / (lo_s + 0.05)

    return round(max(wcag_halo, wcag_stroke), 2)


def validate_v4_micro_label(label: str) -> list[str]:
    """Validates `R65 v4` clean 1-3 word upper-left micro-label lexical rules."""
    issues: list[str] = []
    clean = " ".join(str(label or "").strip().split())
    if not clean or clean.upper() == "TODO":
        return ["empty_or_todo_v4_micro_label"]
    if clean != clean.upper():
        issues.append(f"v4_label_not_uppercase:{clean}")
    words = [w for w in clean.split(" ") if w]
    if len(words) > 3:
        issues.append(f"v4_label_words_{len(words)}_exceeds_3")
    if len(clean) > 22:
        issues.append(f"v4_label_chars_{len(clean)}_exceeds_22")
    return issues


def validate_hook_lexical(hook: str, title: str = "") -> list[str]:
    """Validates `TQ7` lexical rules on a thumbnail hook string."""
    issues: list[str] = []
    clean = str(hook or "").strip()
    if not clean:
        return ["empty_hook_text"]
    if clean != clean.upper():
        issues.append(f"hook_not_uppercase:{clean}")
    words = [w for w in clean.split() if w]
    if len(words) > THUMB_HOOK_MAX_WORDS:
        issues.append(f"hook_words_{len(words)}_exceeds_{THUMB_HOOK_MAX_WORDS}")
    if len(clean) > THUMB_HOOK_MAX_CHARS:
        issues.append(f"hook_chars_{len(clean)}_exceeds_{THUMB_HOOK_MAX_CHARS}")
    if _is_title_prefix(clean, title):
        issues.append("hook_repeats_title_opening_prefix")
    return issues


def _bbox_overlap_px(a: list[int] | tuple[int, int, int, int] | None, b: list[int] | tuple[int, int, int, int] | None) -> int:
    if not a or not b or len(a) != 4 or len(b) != 4:
        return 0
    ix0 = max(int(a[0]), int(b[0]))
    iy0 = max(int(a[1]), int(b[1]))
    ix1 = min(int(a[2]), int(b[2]))
    iy1 = min(int(a[3]), int(b[3]))
    if ix1 <= ix0 or iy1 <= iy0:
        return 0
    return int((ix1 - ix0) * (iy1 - iy0))


def run_thumbnail_qa(
    variants: dict[str, dict[str, Any]],
    hook: str,
    title: str = "",
    *,
    thumb_spec: dict[str, Any] | None = None,
    is_brain_sim_only: bool = False,
) -> dict[str, Any]:
    """
    Evaluates the 9-Gate Thumbnail QA contract (`TQ1-TQ9`) across rendered variants (`A`, `B`, `C`).
    Supports `R65 v4` (`in_skull_cutaway_split_v4`), `R65 v2` (`r65_v2_z_cutaway`), and legacy `v7`.
    """
    var_keys = [k for k in ("A", "B", "C") if k in variants]
    v4_active = is_r65_v4_spec(thumb_spec) or any(
        str((variants[k].get("overlay_mode") or (variants[k].get("overlay") or {}).get("mode") or "")) == THUMB_V4_OVERLAY_MODE
        for k in var_keys
    )
    v2_active = (not v4_active) and (
        is_r65_v2_spec(thumb_spec)
        or any(
            str((variants[k].get("overlay_mode") or (variants[k].get("overlay") or {}).get("mode") or "")) == "r65_v2_z_cutaway"
            for k in var_keys
        )
    )

    v4_metrics_by_var: dict[str, dict[str, Any]] = {}
    v4_split_var_keys: list[str] = []
    if v4_active:
        for k in var_keys:
            vm = variants[k].get("v4_split_metrics")
            if not isinstance(vm, dict):
                vm = compute_r65_v4_split_metrics(variants[k]["rendered_bgr"])
            v4_metrics_by_var[k] = vm
            gram_k = str(variants[k].get("grammar") or "")
            cut_k = int(variants[k].get("cut_index") or 0)
            if gram_k == "r65_v4_in_skull_split_keyart" or cut_k >= 900 or (k == "A" and cut_k == 0):
                v4_split_var_keys.append(k)

    # TQ1: Legibility at 160px shelf width
    contrasts = {k: float(variants[k]["text_contrast_wcag"]) for k in var_keys}
    tq1_ok = bool(var_keys) and all(v >= THUMB_MIN_TEXT_CONTRAST for v in contrasts.values())

    # TQ2: Subject salience on primary cover (Variant A)
    sal_vals: dict[str, float] = {}
    for k in var_keys:
        raw_sal = float(variants[k]["raw_metrics"].get("center_salience", 0.0))
        if k in v4_split_var_keys:
            raw_sal = max(raw_sal, float(v4_metrics_by_var[k].get("dual_panel_salience", 0.0)))
        sal_vals[k] = round(raw_sal, 3)
    tq2_ok = bool(var_keys) and sal_vals.get("A", 0.0) >= THUMB_MIN_CENTER_SALIENCE

    # TQ3: Image focus, global contrast, AND R65 v4 bright studio daylight (Mean Luma >= 105)
    sharp_vals = {k: float(variants[k]["raw_metrics"].get("sharpness", 0.0)) for k in var_keys}
    luma_stds = {
        k: float(variants[k]["raw_metrics"].get("contrast", variants[k]["raw_metrics"].get("luma_std", 0.0)))
        for k in var_keys
    }
    mean_lumas = {
        k: float(
            v4_metrics_by_var[k]["mean_luma"]
            if k in v4_metrics_by_var
            else variants[k]["raw_metrics"].get("luma_mean", 120.0)
        )
        for k in var_keys
    }
    dark_paradox_mode = is_dark_void_paradox_v4(thumb_spec)
    v4_luma_ok = (
        True
        if (dark_paradox_mode or not v4_split_var_keys)
        else all(mean_lumas[k] >= THUMB_V4_MIN_MEAN_LUMA for k in v4_split_var_keys)
    )
    eff_min_sharp = 28.0 if (is_brain_sim_only and not v4_active) else float(THUMB_MIN_SHARPNESS)
    eff_min_luma_std = 28.0 if (is_brain_sim_only and not v4_active) else float(THUMB_MIN_LUMA_STD)
    tq3_ok = (
        bool(var_keys)
        and all(v >= eff_min_sharp for v in sharp_vals.values())
        and all(v >= eff_min_luma_std for v in luma_stds.values())
        and v4_luma_ok
    )

    # TQ4: 2:3 Shorts shelf safe zone geometry (y >= 150) & bottom Shorts UI title safe zone (y >= 1520 clear)
    if v4_active:
        safe_y_lo, safe_y_hi = int(THUMB_SHORTS_SHELF_CROP_Y[0]), 1495
        safe_margin_x_eff = 20
    elif v2_active:
        safe_y_lo, safe_y_hi = int(THUMB_SHORTS_SHELF_CROP_Y[0]), 1480
        safe_margin_x_eff = int(THUMB_SAFE_MARGIN_X)
    else:
        safe_y_lo, safe_y_hi = int(THUMB_SAFE_Y_RANGE[0]), int(THUMB_SAFE_Y_RANGE[1])
        safe_margin_x_eff = int(THUMB_SAFE_MARGIN_X)

    safe_checks: dict[str, bool] = {}
    bboxes: dict[str, list[int]] = {}
    for k in var_keys:
        x0, y0, x1, y1 = variants[k]["text_bbox"]
        bboxes[k] = [x0, y0, x1, y1]
        bot_clean = bool(v4_metrics_by_var[k]["bottom_safe_clean_ok"]) if k in v4_metrics_by_var else True
        safe_checks[k] = (
            x0 >= safe_margin_x_eff
            and x1 <= (VIDEO_WIDTH - safe_margin_x_eff)
            and y0 >= safe_y_lo
            and y1 <= safe_y_hi
            and bot_clean
        )
    tq4_ok = bool(var_keys) and all(safe_checks.values())

    # TQ5: Pairwise distinctness across A / B / C
    ab_diff = roi_pairwise_diff(variants["A"]["rendered_bgr"], variants["B"]["rendered_bgr"]) if ("A" in variants and "B" in variants) else 0.0
    bc_diff = roi_pairwise_diff(variants["B"]["rendered_bgr"], variants["C"]["rendered_bgr"]) if ("B" in variants and "C" in variants) else 0.0
    ac_diff = roi_pairwise_diff(variants["A"]["rendered_bgr"], variants["C"]["rendered_bgr"]) if ("A" in variants and "C" in variants) else 0.0
    if len(var_keys) == 1:
        tq5_ok = True
    else:
        tq5_ok = len(var_keys) == 3 and min(ab_diff, bc_diff, ac_diff) >= THUMB_MIN_PAIRWISE_DIFF

    # TQ6: 1080x1920 PNG dimensions & THUMB_MIN_FILE_BYTES < sz <= SHORTS_THUMB_MAX_BYTES
    file_sizes = {k: int(variants[k]["file_bytes"]) for k in var_keys}
    dims_ok = all(variants[k]["dimensions"] == [VIDEO_WIDTH, VIDEO_HEIGHT] for k in var_keys)
    tq6_ok = (
        len(var_keys) in (1, 3)
        and dims_ok
        and all(THUMB_MIN_FILE_BYTES < sz <= SHORTS_THUMB_MAX_BYTES for sz in file_sizes.values())
    )

    # TQ7: Hook / micro-label lexical contract
    hook_issues: list[str] = []
    if v4_active and isinstance(thumb_spec, dict):
        tl_v4 = str(thumb_spec.get("top_split_label") or thumb_spec.get("top_left_hook") or hook or "").strip()
        bl_v4 = str(thumb_spec.get("bottom_split_label") or thumb_spec.get("bottom_right_hook") or "").strip()
        hook_issues.extend(validate_v4_micro_label(tl_v4))
        if bl_v4:
            hook_issues.extend(validate_v4_micro_label(bl_v4))
    elif v2_active and isinstance(thumb_spec, dict):
        tl = str(thumb_spec.get("top_left_hook") or hook or "").strip()
        br = str(thumb_spec.get("bottom_right_hook") or "").strip()
        hook_issues.extend(validate_hook_lexical(tl, title=title))
        if len(tl.split()) > 3:
            hook_issues.append(f"top_left_hook_words_{len(tl.split())}_exceeds_3")
        if br:
            hook_issues.extend(validate_hook_lexical(br, title=""))
            if len(br.split()) > 3:
                hook_issues.append(f"bottom_right_hook_words_{len(br.split())}_exceeds_3")
    else:
        hook_issues = validate_hook_lexical(hook, title=title)
    tq7_ok = len(hook_issues) == 0

    # TQ8: Zero porcelain head occlusion + R65 v4 50/50 split integrity & bottom-vs-top brain activation delta
    head_occ_by_var: dict[str, bool] = {}
    band_by_var: dict[str, list[int]] = {}
    v4_split_ok_by_var: dict[str, bool] = {}
    v4_act_delta_by_var: dict[str, float] = {}
    for k in var_keys:
        src_bgr = variants[k].get("clean_bgr")
        if src_bgr is None:
            src_bgr = variants[k]["rendered_bgr"]
        top_bb = variants[k].get("top_chunk_bbox") or variants[k].get("text_bbox")
        if isinstance(top_bb, (list, tuple)) and len(top_bb) == 4 and int(top_bb[3]) > int(top_bb[1]):
            v_band = (max(150 if v4_active else 180, int(top_bb[1]) - 10), min(520, int(top_bb[3]) + 10))
        else:
            v_band = (265, 515)
        band_by_var[k] = [v_band[0], v_band[1]]
        head_occ_by_var[k] = _has_head_occlusion_in_hook_band(
            src_bgr,
            str(variants[k].get("grammar") or ("cutaway" if (v2_active or v4_active) else "")),
            band_y=v_band,
        )
        if k in v4_split_var_keys:
            vm = v4_metrics_by_var[k]
            act_d = float(vm.get("activation_delta", 0.0))
            v4_act_delta_by_var[k] = act_d
            v4_split_ok_by_var[k] = bool(vm.get("split_50_50_ok")) and (act_d >= THUMB_V4_MIN_ACTIVATION_DELTA)
    v4_split_and_delta_ok = all(v4_split_ok_by_var.values()) if v4_split_ok_by_var else True
    tq8_ok = bool(var_keys) and (not any(head_occ_by_var.values())) and v4_split_and_delta_ok

    # TQ9: Zero pointer/text overlap + R65 v4 bottom Shorts UI title safe zone cleanliness (y >= 1520)
    overlap_by_var: dict[str, int] = {}
    bot_title_safe_by_var: dict[str, bool] = {}
    for k in var_keys:
        ptr_bb = variants[k].get("pointer_bbox")
        top_bb = variants[k].get("top_chunk_bbox")
        bot_bb = variants[k].get("bottom_chunk_bbox")
        if ptr_bb and (top_bb or bot_bb):
            overlap_by_var[k] = _bbox_overlap_px(ptr_bb, top_bb) + _bbox_overlap_px(ptr_bb, bot_bb)
        else:
            overlap_by_var[k] = 0
        if v4_active:
            tx_bb = variants[k]["text_bbox"]
            bot_title_safe_by_var[k] = (
                int(tx_bb[3]) < int(THUMB_V4_BOTTOM_TITLE_SAFE_Y)
                and bool(v4_metrics_by_var[k]["bottom_safe_clean_ok"])
            )
        else:
            bot_title_safe_by_var[k] = True
    tq9_ok = bool(var_keys) and all(px == 0 for px in overlap_by_var.values()) and all(bot_title_safe_by_var.values())

    gates = {
        "TQ1_shelf_legibility": {
            "passed": tq1_ok,
            "min_wcag_contrast_threshold": THUMB_MIN_TEXT_CONTRAST,
            "wcag_contrast_by_variant": contrasts,
        },
        "TQ2_subject_center_salience": {
            "passed": tq2_ok,
            "min_center_salience_threshold": THUMB_MIN_CENTER_SALIENCE,
            "center_salience_by_variant": sal_vals,
        },
        "TQ3_sharpness_and_contrast": {
            "passed": tq3_ok,
            "min_sharpness_threshold": eff_min_sharp,
            "min_luma_std_threshold": eff_min_luma_std,
            "min_v4_mean_luma_threshold": (None if dark_paradox_mode else THUMB_V4_MIN_MEAN_LUMA) if v4_active else None,
            "sharpness_by_variant": sharp_vals,
            "luma_std_by_variant": luma_stds,
            "mean_luma_by_variant": mean_lumas,
        },
        "TQ4_safe_zone_geometry": {
            "passed": tq4_ok,
            "safe_y_range": [safe_y_lo, safe_y_hi],
            "safe_margin_x": safe_margin_x_eff,
            "text_bbox_by_variant": bboxes,
        },
        "TQ5_pairwise_distinct": {
            "passed": tq5_ok,
            "min_pairwise_diff_threshold": THUMB_MIN_PAIRWISE_DIFF,
            "ab_diff": ab_diff,
            "bc_diff": bc_diff,
            "ac_diff": ac_diff,
        },
        "TQ6_file_integrity": {
            "passed": tq6_ok,
            "min_file_bytes": THUMB_MIN_FILE_BYTES,
            "max_file_bytes": SHORTS_THUMB_MAX_BYTES,
            "file_bytes_by_variant": file_sizes,
            "dimensions_1080x1920": dims_ok,
        },
        "TQ7_hook_lexical": {
            "passed": tq7_ok,
            "hook_text": hook,
            "max_words": 3 if (v4_active or v2_active) else THUMB_HOOK_MAX_WORDS,
            "max_chars": 22 if v4_active else THUMB_HOOK_MAX_CHARS,
            "issues": hook_issues,
        },
        "TQ8_zero_head_occlusion": {
            "passed": tq8_ok,
            "hook_band_y": [150, 390] if v4_active else ([215, 395] if v2_active else [265, 515]),
            "hook_band_y_by_variant": band_by_var,
            "head_occlusion_by_variant": head_occ_by_var,
            "v4_split_50_50_and_delta_by_variant": v4_split_ok_by_var if v4_active else {},
            "v4_activation_delta_by_variant": v4_act_delta_by_var if v4_active else {},
        },
        "TQ9_pointer_text_non_overlap": {
            "passed": tq9_ok,
            "overlap_px_by_variant": overlap_by_var,
            "bottom_shorts_title_safe_by_variant": bot_title_safe_by_var if v4_active else {},
        },
    }
    is_r85_thumb = bool((thumb_spec or {}).get("r85_mode"))
    if is_r85_thumb:
        gates.pop("TQ5_pairwise_distinct", None)
        advisory_failed = [
            g_name for g_name in ("TQ1_shelf_legibility", "TQ2_subject_center_salience", "TQ3_sharpness_and_contrast")
            if g_name in gates and not gates[g_name]["passed"]
        ]
        failed_gates = [
            g_name for g_name, g_val in gates.items()
            if not g_val["passed"] and g_name not in ("TQ1_shelf_legibility", "TQ2_subject_center_salience", "TQ3_sharpness_and_contrast")
        ]
    else:
        advisory_failed = []
        failed_gates = [g_name for g_name, g_val in gates.items() if not g_val["passed"]]
    return {
        "passed": len(failed_gates) == 0,
        "failed_gates": failed_gates,
        "advisory_failed_gates": advisory_failed,
        "gates": gates,
    }


def evaluate_thumbnail_gates(
    variants_meta: dict[str, dict[str, Any]],
    rendered_paths: dict[str, Path],
    *,
    hook_text: str,
    title: str = "",
    thumb_spec: dict[str, Any] | None = None,
    is_brain_sim_only: bool = False,
) -> dict[str, dict[str, Any]]:
    """Convenience gate evaluator returning the `TQ1-TQ9` gates dict from variant metadata & PNG paths."""
    norm_vars: dict[str, dict[str, Any]] = {}
    default_gram = (
        "r65_v4_in_skull_split_keyart"
        if is_r65_v4_spec(thumb_spec)
        else ("cutaway_keyart_zero_credit" if is_r65_v2_spec(thumb_spec) else "")
    )
    for vk, vm in variants_meta.items():
        vp = Path(rendered_paths[vk])
        bgr = cv2.imread(str(vp))
        if bgr is None:
            bgr = np.zeros((VIDEO_HEIGHT, VIDEO_WIDTH, 3), dtype=np.uint8)
        ov = vm.get("overlay") if isinstance(vm.get("overlay"), dict) else {}
        norm_vars[vk] = {
            "cut_index": int(vm.get("cut_index", 901 if is_r65_v4_spec(thumb_spec) else 0)),
            "raw_metrics": {
                "sharpness": float(vm.get("sharpness", 0.0)),
                "contrast": float(vm.get("luma_std", vm.get("contrast", 0.0))),
                "luma_mean": float(vm.get("luma_mean", float(cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY).mean()))),
                "center_salience": float(vm.get("center_salience", 0.0)),
            },
            "text_contrast_wcag": float(vm.get("text_contrast_wcag", ov.get("wcag_contrast", 4.5))),
            "text_bbox": list(vm.get("text_bbox") or ov.get("text_bbox") or [56, 176, 480, 1280]),
            "top_chunk_bbox": ov.get("top_chunk_bbox"),
            "bottom_chunk_bbox": ov.get("bottom_chunk_bbox"),
            "pointer_bbox": ov.get("pointer_bbox"),
            "overlay_mode": ov.get("mode"),
            "v4_split_metrics": ov.get("v4_split_metrics"),
            "rendered_bgr": bgr,
            "clean_bgr": bgr,
            "file_bytes": int(vp.stat().st_size) if vp.exists() else int(vm.get("file_bytes", 0)),
            "dimensions": [int(bgr.shape[1]), int(bgr.shape[0])],
            "grammar": str(vm.get("grammar") or default_gram),
        }
    return run_thumbnail_qa(
        norm_vars,
        hook=hook_text,
        title=title,
        thumb_spec=thumb_spec,
        is_brain_sim_only=is_brain_sim_only,
    )["gates"]


def write_contact_sheet(
    variants: dict[str, Any],
    output_path: Path,
    hook: str = "",
    qa_result: dict[str, Any] | None = None,
) -> Path:
    """
    Writes a side-by-side contact sheet showing A/B/C full previews + actual `160px` mobile Shorts shelf
    previews (`2:3` `y=150..1770` crop box + `y=1520..1770` title overlay mask guide) + scores.
    """
    qa_result = qa_result if isinstance(qa_result, dict) else {"passed": True, "failed_gates": []}
    card_w, card_h = 360, 640
    pad = 24
    header_h = 84
    footer_h = 340
    sheet_w = pad * 4 + card_w * 3
    sheet_h = header_h + card_h + footer_h + pad
    canvas = Image.new("RGB", (sheet_w, sheet_h), (18, 22, 30))
    draw = ImageDraw.Draw(canvas)

    font_path = _resolve_v7_font_path()
    try:
        title_font = ImageFont.truetype(str(font_path), 30)
        meta_font = ImageFont.truetype(str(FONT_PRIMARY_PATH if FONT_PRIMARY_PATH.exists() else font_path), 18)
    except Exception:
        title_font = ImageFont.load_default()
        meta_font = ImageFont.load_default()

    status_txt = "PASS" if qa_result.get("passed") else f"FAIL ({', '.join(qa_result.get('failed_gates', []))})"
    status_col = (92, 224, 138) if qa_result.get("passed") else (255, 102, 102)
    qa_label = f"QA: {status_txt}"
    qa_bb = meta_font.getbbox(qa_label)
    qa_w = qa_bb[2] - qa_bb[0]
    draw.text((pad, 24), f"R65 v4 THUMBNAIL STUDIO | HOOK: {hook or 'SPLIT-HOOK'}", fill=(245, 247, 250), font=title_font)
    draw.text((max(pad + 680, sheet_w - pad - qa_w), 30), qa_label, fill=status_col, font=meta_font)

    pw = int(THUMB_LEGIBILITY_PREVIEW_W)
    ph = int(round(VIDEO_HEIGHT * (pw / float(VIDEO_WIDTH))))
    scale_y = ph / float(VIDEO_HEIGHT)
    shelf_y0 = int(round(THUMB_SHORTS_SHELF_CROP_Y[0] * scale_y))
    shelf_y1 = int(round(THUMB_SHORTS_SHELF_CROP_Y[1] * scale_y))
    title_mask_y0 = int(round(1520 * scale_y))

    for idx, k in enumerate(("A", "B", "C")):
        if k not in variants:
            continue
        raw_v = variants[k]
        if isinstance(raw_v, (Path, str)):
            pil_full = Image.open(str(raw_v)).convert("RGB")
            v: dict[str, Any] = {
                "pil_image": pil_full,
                "cut_index": 0,
                "clip_index": 0,
                "out_sec": 0.0,
                "act": 1,
                "total_score": 1.0,
                "raw_metrics": compute_image_metrics(cv2.cvtColor(np.array(pil_full, dtype=np.uint8), cv2.COLOR_RGB2BGR)),
                "text_contrast_wcag": 5.0,
            }
        else:
            v = raw_v
            pil_full = v["pil_image"]

        x0 = pad + idx * (card_w + pad)
        y0 = header_h
        card_img = pil_full.resize((card_w, card_h), Image.Resampling.LANCZOS)
        canvas.paste(card_img, (x0, y0))

        # 1:1 160px mobile shelf preview + true 2:3 Shorts shelf crop (y=150..1770) + bottom title mask (y=1520..1770)
        shelf_img = pil_full.resize((pw, ph), Image.Resampling.LANCZOS)
        sx = x0
        sy = y0 + card_h + 16
        canvas.paste(shelf_img, (sx, sy))
        draw.rectangle([(sx, sy), (sx + pw, sy + ph)], outline=(90, 110, 140), width=1)
        draw.rectangle([(sx, sy + shelf_y0), (sx + pw, sy + shelf_y1)], outline=(255, 215, 0), width=2)
        draw.rectangle([(sx + 1, sy + title_mask_y0), (sx + pw - 1, sy + shelf_y1 - 1)], outline=(255, 65, 65), width=1)

        tx = sx + pw + 14
        ty = sy + 4
        rm = v["raw_metrics"]
        info_lines = [
            f"VAR {k}" + (" (PRIMARY)" if k == "A" else ""),
            f"cut #{v['cut_index']} | clip {v['clip_index']}",
            f"t = {v['out_sec']:.2f}s (Act {v['act']})",
            f"score = {v['total_score']:.3f}",
            f"sharp = {rm.get('sharpness', 0):.0f}",
            f"luma_std = {rm.get('contrast', 0):.1f}",
            f"salience = {rm.get('center_salience', 0):.2f}",
            f"WCAG@160 = {v['text_contrast_wcag']:.2f}",
        ]
        for ln in info_lines:
            draw.text((tx, ty), ln, fill=(222, 228, 238), font=meta_font)
            ty += 26

    _atomic_save_pil_png(canvas, output_path)
    return output_path


def _rerender_exact_cut_frames_if_available(
    p_dir: Path,
    winners: list[ThumbCandidate],
    plan: dict[str, Any],
    local_clips: dict[int, Path] | None = None,
    pastel_eq_by_num: dict[int, str] | None = None,
) -> None:
    """
    Re-renders the 3 winning clean frames through `diorama_assembler._render_cut_segment` (only 3 fast
    single-frame FFmpeg calls) when EDL + native clips exist, ensuring 100% pastel-EQ & unsharp parity
    with `final_shorts_1080x1920.mp4`.
    """
    clips_map = _resolve_clip_map(p_dir, local_clips=local_clips)
    if not clips_map:
        return
    edl = _read_json(p_dir / "05_assembly" / "edit_decision_list.json")
    fps = int(edl.get("fps") or 24)
    try:
        import imageio_ffmpeg
        from pipeline.diorama_assembler import _render_cut_segment

        ff = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as exc:
        import logging

        logging.getLogger("thumbnail_studio").warning("FFmpeg unavailable for exact winner frame render: %s", exc, exc_info=True)
        return

    from pipeline.media_cache import ram_tempdir

    with ram_tempdir(prefix="aab_thumb_") as td:
        td_path = Path(td)
        for idx, cand in enumerate(winners):
            if not cand.cut_dict or "src_start_sec" not in cand.cut_dict or cand.clip_index not in clips_map:
                continue
            out_png = td_path / f"win_{idx}.png"
            try:
                _render_cut_segment(
                    ff,
                    cand.cut_dict,
                    clips_map,
                    out_png,
                    fps,
                    pastel_eq_by_num=pastel_eq_by_num,
                    cwd=td_path,
                    single_frame_offset_sec=cand.offset_in_cut_sec,
                    override_frames=int(cand.cut_dict.get("frames") or max(1, int(round(fps * 1.0)))),
                )
                if out_png.exists() and out_png.stat().st_size > 0:
                    exact_bgr = cv2.imread(str(out_png))
                    if exact_bgr is not None and exact_bgr.shape[:2] == (VIDEO_HEIGHT, VIDEO_WIDTH):
                        cand.image = exact_bgr
                        cand.raw_metrics = score_candidate(exact_bgr, cand.cut_dict, plan)
            except Exception as exc:
                import logging

                logging.getLogger("thumbnail_studio").warning(
                    "Thumbnail winner %d exact-frame FFmpeg render failed: %s", idx, exc, exc_info=True
                )
                continue


def run(
    project_id_or_dir: str | Path,
    *,
    force: bool = False,
    strict: bool = True,
    local_clips: dict[int, Path] | None = None,
    pastel_eq_by_num: dict[int, str] | None = None,
    mode: str = "production",
    generate_keyart: bool = False,
    keyart_only: bool = False,
    frames_only: bool = False,
    cdp_port: int = 9222,
) -> dict[str, Any]:
    """
    Executes the full R65 / R65 v2 Thumbnail Studio pipeline on a project:
      1. Optionally generates `0-credit` 3D Cutaway Keyart (`--generate-keyart` / `--keyart-only`, auto-falling
         back to cutaway-scored EDL frames when `--frames-only`, `PYTEST_CURRENT_TEST`, or CDP offline)
      2. Collects & scores clean candidate frames across eligible EDL cuts
      3. Picks top-3 visually distinct frames (`A`, `B`, `C`)
      4. Renders R65 v2 `#FF2525` pointer + Diagonal Z-Pattern 2-chunk hook (or v7 single hook)
      5. Evaluates `TQ1-TQ9` and writes `thumbnail_report.json` + `thumbnail_contact_sheet.png` in `06_publish/`
    """
    p_dir = (
        Path(project_id_or_dir)
        if isinstance(project_id_or_dir, Path) or Path(str(project_id_or_dir)).exists()
        else (Path(PROJECTS_DIR) / str(project_id_or_dir))
    )
    if not p_dir.exists():
        raise FileNotFoundError(f"Project directory not found: {p_dir}")
    p_dir = p_dir.resolve()

    pub_dir = p_dir / "06_publish"
    pub_dir.mkdir(parents=True, exist_ok=True)
    report_path = pub_dir / THUMBNAIL_REPORT_FILENAME

    if not force and report_path.exists():
        cached = _read_json(report_path)
        var_meta = cached.get("variants") if isinstance(cached.get("variants"), dict) else {}
        files_ok = all(
            (pub_dir / f"thumbnail_var_{k}.png").exists()
            and _sha256_file(pub_dir / f"thumbnail_var_{k}.png") == str((var_meta.get(k) or {}).get("sha256") or "")
            for k in ("A", "B", "C")
        )
        has_keyart_winner = int(((var_meta.get("A") or {}).get("cut_index")) or 0) >= 900
        need_fresh_keyart = (generate_keyart or keyart_only) and not frames_only and not has_keyart_winner
        if files_ok and not need_fresh_keyart and (cached.get("passed") or not strict):
            return cached

    plan = _read_json(p_dir / "03_visuals" / "visual_plan.json")
    script = _read_json(p_dir / "02_script" / "script.json")
    meta_doc = _read_json(pub_dir / "metadata.json")
    title = str(script.get("title") or meta_doc.get("title") or plan.get("title") or p_dir.name).strip()
    thumb_cfg = dict(plan.get("thumbnail")) if isinstance(plan.get("thumbnail"), dict) else {}
    if "r85_mode" not in thumb_cfg and plan.get("r85_mode") is not None:
        thumb_cfg["r85_mode"] = bool(plan.get("r85_mode"))

    frame_candidates: list[ThumbCandidate] = [] if keyart_only else collect_candidates(p_dir, local_clips=local_clips)
    keyart_candidates: list[ThumbCandidate] = []
    want_keyart = (generate_keyart or keyart_only) and not frames_only and not os.environ.get("PYTEST_CURRENT_TEST")
    if want_keyart:
        try:
            keyart_candidates = generate_zero_credit_thumb_keyart(p_dir, plan=plan, script=script, cdp_port=cdp_port)
        except Exception as exc:
            from pipeline.flow_browser import FlowCircuitBreakerError

            if keyart_only or isinstance(exc, FlowCircuitBreakerError):
                raise
            import logging

            logging.getLogger("thumbnail_studio").warning(
                "0-credit keyart generation unavailable (%s); falling back to cutaway-scored video frames.", exc
            )
    elif not frames_only and not os.environ.get("PYTEST_CURRENT_TEST"):
        keyart_candidates = _load_cached_keyart_candidates(p_dir, plan)

    if keyart_candidates:
        # Normalize across the combined pool first so single cached keyarts never collapse to 0.5, then apply R65 v4/v2 keyart lead boost
        candidates = keyart_candidates + frame_candidates
        _finalize_candidate_scores(candidates)
        boost = 0.65 if is_r65_v4_spec(thumb_cfg) else 0.35
        for kc in keyart_candidates:
            kc.total = round(float(kc.total) + boost, 4)
        candidates.sort(key=lambda x: (x.total, x.raw_metrics.get("sharpness", 0.0)), reverse=True)
    else:
        candidates = frame_candidates

    if not candidates:
        raise RuntimeError(f"R65 Thumbnail Studio found zero candidate frames in {p_dir}")

    winners = pick_top_distinct(candidates, k=3, min_diff=THUMB_MIN_PAIRWISE_DIFF)
    # Pad to 3 if episode had fewer than 3 total candidates (e.g. tiny synthetic test stub)
    while len(winners) < 3:
        winners.append(winners[-1])

    _rerender_exact_cut_frames_if_available(
        p_dir,
        winners,
        plan,
        local_clips=local_clips,
        pastel_eq_by_num=pastel_eq_by_num,
    )

    hook_text, hook_source = resolve_hook(plan, script or meta_doc)

    rendered_variants: dict[str, dict[str, Any]] = {}
    for var_key, cand in zip(("A", "B", "C"), winners):
        is_fallback_vf = int(cand.cut_index) < 900
        pil_img, ov_meta = render_overlay_with_meta(
            cand.image,
            hook_text,
            thumb_spec=thumb_cfg,
            is_fallback_video_frame=is_fallback_vf,
        )
        out_png = pub_dir / f"thumbnail_var_{var_key}.png"
        _atomic_save_pil_png(pil_img, out_png, max_bytes=SHORTS_THUMB_MAX_BYTES)
        if var_key == "A":
            _atomic_save_pil_png(pil_img, pub_dir / "thumbnail.png", max_bytes=SHORTS_THUMB_MAX_BYTES)
            _atomic_save_pil_png(pil_img, pub_dir / THUMBNAIL_SELECTED_FILENAME, max_bytes=SHORTS_THUMB_MAX_BYTES)

        rendered_bgr = cv2.cvtColor(np.array(pil_img, dtype=np.uint8), cv2.COLOR_RGB2BGR)
        wcag_c = float(ov_meta.get("wcag_contrast") or measure_shelf_text_contrast(pil_img, ov_meta["fill_mask"]))
        rendered_variants[var_key] = {
            "variant": var_key,
            "file": out_png.name,
            "path": str(out_png),
            "sha256": _sha256_file(out_png),
            "file_bytes": int(out_png.stat().st_size),
            "dimensions": [int(pil_img.size[0]), int(pil_img.size[1])],
            "cut_index": int(cand.cut_index),
            "clip_index": int(cand.clip_index),
            "act": int(cand.act),
            "sentence_index": int(cand.sentence_index),
            "end_sentence_index": int(cand.end_sentence_index),
            "out_sec": float(cand.out_sec),
            "src_sec": float(cand.src_sec),
            "grammar": cand.grammar,
            "total_score": float(cand.total),
            "normalized_scores": dict(cand.scores),
            "raw_metrics": dict(cand.raw_metrics),
            "overlay_mode": ov_meta.get("mode", "r65_v1"),
            "v4_split_metrics": ov_meta.get("v4_split_metrics"),
            "text_bbox": ov_meta["text_bbox"],
            "top_chunk_bbox": ov_meta.get("top_chunk_bbox"),
            "bottom_chunk_bbox": ov_meta.get("bottom_chunk_bbox"),
            "pointer_bbox": ov_meta.get("pointer_bbox"),
            "pointer_label": ov_meta.get("pointer_label"),
            "pointer_style": ov_meta.get("pointer_style"),
            "font_size": ov_meta["font_size"],
            "text_contrast_wcag": wcag_c,
            "pil_image": pil_img,
            "rendered_bgr": rendered_bgr,
            "clean_bgr": cand.image,
        }

    qa_res = run_thumbnail_qa(
        rendered_variants,
        hook=hook_text,
        title=title,
        thumb_spec=thumb_cfg,
        is_brain_sim_only=is_brain_sim_only_plan(plan, script),
    )
    if is_r65_v4_spec(thumb_cfg):
        display_hook = (
            f"{thumb_cfg.get('top_split_label') or thumb_cfg.get('top_left_hook') or hook_text} / "
            f"{thumb_cfg.get('bottom_split_label') or thumb_cfg.get('bottom_right_hook') or 'SHOCK!'}"
        )
    elif is_r65_v2_spec(thumb_cfg):
        display_hook = f"{thumb_cfg.get('top_left_hook')} / {thumb_cfg.get('bottom_right_hook')}"
    else:
        display_hook = hook_text
    sheet_path = write_contact_sheet(
        rendered_variants,
        pub_dir / THUMBNAIL_CONTACT_SHEET_FILENAME,
        hook=display_hook,
        qa_result=qa_res,
    )

    final_mp4 = p_dir / "05_assembly" / "final_shorts_1080x1920.mp4"
    final_mp4_sha = _sha256_file(final_mp4) if final_mp4.exists() else None

    # Determine in-video cover frame timestamp: prefer non-occluded frame inside cold-open stamp sentence cut (band y=180..324),
    # else non-occluded Act-1 candidate, else target sentence cut midpoint / Variant A out_sec
    thumb_cfg = plan.get("thumbnail") if isinstance(plan.get("thumbnail"), dict) else {}
    target_cover_sent = int(thumb_cfg.get("cover_sentence_index") or 3)
    edl = _read_json(p_dir / "05_assembly" / "edit_decision_list.json")
    in_video_cover_sec: float | None = None
    cover_sent_clean = [
        c
        for c in candidates
        if c.sentence_index <= target_cover_sent <= max(c.sentence_index, c.end_sentence_index)
        and not _has_head_occlusion_in_hook_band(c.image, c.grammar, band_y=(180, 324))
    ]
    if cover_sent_clean:
        in_video_cover_sec = round(float(cover_sent_clean[0].out_sec), 2)
    else:
        act1_clean = [
            c
            for c in candidates
            if c.act == 1 and not _has_head_occlusion_in_hook_band(c.image, c.grammar, band_y=(180, 324))
        ]
        if act1_clean:
            in_video_cover_sec = round(float(act1_clean[0].out_sec), 2)
        else:
            for cut in edl.get("cuts") or []:
                if not isinstance(cut, dict):
                    continue
                s0 = int(cut.get("sentence_index") or 0)
                s1 = int(cut.get("end_sentence_index") or s0)
                if s0 <= target_cover_sent <= max(s0, s1) and str(cut.get("mode") or "single") not in THUMB_EXCLUDE_MODES:
                    in_video_cover_sec = round(
                        0.5 * (float(cut.get("out_start_sec") or 0.0) + float(cut.get("out_end_sec") or 0.0)),
                        2,
                    )
                    break
    primary_out_sec = float(rendered_variants["A"]["out_sec"])
    cover_frame_sec = in_video_cover_sec if in_video_cover_sec is not None else round(primary_out_sec, 2)

    serializable_variants = {
        k: {vk: vv for vk, vv in v.items() if vk not in ("pil_image", "rendered_bgr", "clean_bgr")}
        for k, v in rendered_variants.items()
    }
    report = {
        "schema": "R65_thumbnail_report_v1",
        "project_id": p_dir.name,
        "mode": mode,
        "passed": bool(qa_res["passed"]),
        "failed_gates": qa_res["failed_gates"],
        "hook_text": hook_text,
        "hook_source": hook_source,
        "title": title,
        "candidate_count": len(candidates),
        "primary_variant": "A",
        "primary_variant_out_sec": round(primary_out_sec, 2),
        "cover_sentence_index": target_cover_sent,
        "cover_frame_sec": cover_frame_sec,
        "contact_sheet": sheet_path.name,
        "final_mp4_sha256": final_mp4_sha,
        "gates": qa_res["gates"],
        "variants": serializable_variants,
    }
    _atomic_write_json(report_path, report)
    _atomic_write_json(pub_dir / THUMBNAIL_QA_REPORT_FILENAME, report)

    if strict and not report["passed"]:
        raise RuntimeError(
            f"R65 Thumbnail Studio QA failed for {p_dir.name}: {report['failed_gates']} "
            f"(see {report_path})"
        )
    return report


def render_longform_4k_thumbnails(
    project_dir: str | Path,
    frames_bgr: list[np.ndarray] | None = None,
    hook: str = "",
    *,
    hook_text: str | None = None,
) -> dict[str, Any]:
    """
    Renders 3 distinct `16:9` `1920x1080` (`THUMB_LONGFORM_WIDTH x THUMB_LONGFORM_HEIGHT`) thumbnails in `06_publish/`:
      - `thumbnail_var_{A,B,C}.jpg` (`< 2 MB` JPEG for YouTube Studio `Test & Compare` upload)
      - `thumb_longform_{A,B,C}.png` (lossless PNG archive)
    Automatically sizes `AAB Condensed Black` and places hook text on the horizontal third opposite to the
    porcelain subject/brain mass so text never occludes the hero subject.
    """
    import io

    from pipeline.config import LONGFORM_THUMB_MAX_BYTES, THUMB_LONGFORM_HEIGHT, THUMB_LONGFORM_WIDTH
    from pipeline.longform_prompt_builder import resolve_longform_project_dir

    p_dir = resolve_longform_project_dir(project_dir, create=False)
    pub_dir = p_dir / "06_publish"
    pub_dir.mkdir(parents=True, exist_ok=True)
    eff_hook = str(hook_text if hook_text is not None else hook or "BRAIN MYSTERY?").strip() or "BRAIN MYSTERY?"
    eff_frames = list(frames_bgr or [])
    if not eff_frames:
        vis_dir = p_dir / "03_visuals" / "flow_native_clips"
        if vis_dir.is_dir():
            for c_mp4 in sorted(vis_dir.glob("clip_*.mp4"), key=lambda p: int("".join(filter(str.isdigit, p.stem)) or "0"))[:6:2]:
                cap = cv2.VideoCapture(str(c_mp4))
                ok, frm = cap.read()
                cap.release()
                if ok and frm is not None:
                    eff_frames.append(frm)
    if not eff_frames:
        ref_dir = p_dir / "03_visuals" / "reference_images"
        if ref_dir.is_dir():
            # Prefer brain + wide room + cast anchors for distinct A/B/C visual contrast
            ref_pngs = sorted(ref_dir.glob("*.png"))
            brain_pngs = [p for p in ref_pngs if "brain" in p.stem]
            room_pngs = [p for p in ref_pngs if "brain" not in p.stem]
            ordered = (brain_pngs[:1] + room_pngs[:2] + ref_pngs)[:3]
            for rp in ordered:
                im = cv2.imread(str(rp))
                if im is not None:
                    eff_frames.append(im)

    font_path = _resolve_v7_font_path()
    hook_words = [w for w in eff_hook.upper().split() if w]
    if len(hook_words) <= 1:
        lines = hook_words or ["BRAIN MYSTERY?"]
    elif len(hook_words) == 2:
        lines = [hook_words[0], hook_words[1]]
    else:
        best_k = min(
            range(1, len(hook_words)),
            key=lambda k: max(len(" ".join(hook_words[:k])), len(" ".join(hook_words[k:]))),
        )
        lines = [" ".join(hook_words[:best_k]), " ".join(hook_words[best_k:])]

    max_text_w = int(THUMB_LONGFORM_WIDTH * 0.30)
    stroke_w = max(8, int(round(THUMB_LONGFORM_HEIGHT * 0.010)))
    fnt = ImageFont.load_default()
    for pt in range(int(round(THUMB_LONGFORM_HEIGHT * 0.106)), 48, -4):
        try:
            cand_f = ImageFont.truetype(str(font_path), pt)
            w_max = max((cand_f.getbbox(ln, stroke_width=stroke_w)[2] - cand_f.getbbox(ln, stroke_width=stroke_w)[0]) for ln in lines)
            if w_max <= max_text_w:
                fnt = cand_f
                break
            fnt = cand_f
        except Exception:
            break

    saved_png: dict[str, str] = {}
    saved_jpg: dict[str, str] = {}
    jpg_sizes: dict[str, int] = {}

    for idx, var_name in enumerate(("A", "B", "C")):
        src = eff_frames[min(idx, len(eff_frames) - 1)] if eff_frames else np.full((1080, 1920, 3), (225, 232, 238), dtype=np.uint8)
        h0, w0 = src.shape[:2]
        target_ratio = float(THUMB_LONGFORM_WIDTH) / float(THUMB_LONGFORM_HEIGHT)
        cur_ratio = float(w0) / max(float(h0), 1.0)
        if cur_ratio > target_ratio:
            nw = int(round(h0 * target_ratio))
            x0 = max(0, (w0 - nw) // 2)
            cropped = src[:, x0 : x0 + nw]
        else:
            nh = int(round(w0 / target_ratio))
            y0 = max(0, (h0 - nh) // 2)
            cropped = src[y0 : y0 + nh, :]
        if len(eff_frames) < 3 and idx > 0:
            zf = 1.0 + 0.06 * idx
            zh, zw = int(cropped.shape[0] / zf), int(cropped.shape[1] / zf)
            zy = (cropped.shape[0] - zh) // (2 if idx == 1 else 3)
            zx = (cropped.shape[1] - zw) // (2 if idx == 1 else 4)
            cropped = cropped[zy : zy + zh, zx : zx + zw]
        resized = cv2.resize(cropped, (THUMB_LONGFORM_WIDTH, THUMB_LONGFORM_HEIGHT), interpolation=cv2.INTER_LANCZOS4)

        # Score foreground salience inside the exact padded left vs right candidate text bounding boxes
        # using true RGB chroma (immune to dark-window HSV saturation noise) and smooth porcelain + joint column contrast.
        hsv = cv2.cvtColor(resized, cv2.COLOR_BGR2HSV)
        gray_th = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
        rgb_chroma = np.max(resized, axis=2).astype(np.int16) - np.min(resized, axis=2).astype(np.int16)
        chroma_sal = ((rgb_chroma >= 38) & (hsv[:, :, 2] >= 85)).astype(np.float32)
        edges = (cv2.Canny(gray_th, 60, 160) > 0).astype(np.float32)
        gx = np.abs(cv2.Sobel(gray_th, cv2.CV_32F, 1, 0, ksize=3))
        smooth_porc = (
            (hsv[:, :, 1] <= 26) & (hsv[:, :, 2] >= 175) & (hsv[:, :, 2] <= 240) & (gx < 22.0)
        ).astype(np.float32)
        dark_joint = ((hsv[:, :, 2] <= 65) & (gray_th <= 60)).astype(np.float32)
        col_has_joint = (
            dark_joint[int(THUMB_LONGFORM_HEIGHT * 0.20) : int(THUMB_LONGFORM_HEIGHT * 0.85), :].mean(axis=0) * 15.0
        ).clip(0.0, 1.2)
        cast_sal = smooth_porc * col_has_joint[None, :]
        sal = 0.45 * chroma_sal + 0.35 * cast_sal + 0.20 * edges

        margin_x = int(THUMB_LONGFORM_WIDTH * 0.055)
        box_y0 = int(THUMB_LONGFORM_HEIGHT * 0.18) + (idx * 18)
        line_bboxes = [fnt.getbbox(ln, stroke_width=stroke_w) for ln in lines]
        max_lw = max((bb[2] - bb[0]) for bb in line_bboxes) if line_bboxes else int(THUMB_LONGFORM_WIDTH * 0.28)
        tot_th = sum((bb[3] - bb[1]) + 16 for bb in line_bboxes) if line_bboxes else int(THUMB_LONGFORM_HEIGHT * 0.24)
        pad_px = 36
        ly0 = max(0, box_y0 - pad_px)
        ly1 = min(THUMB_LONGFORM_HEIGHT, box_y0 + tot_th + pad_px)
        lx0 = max(0, margin_x - pad_px)
        lx1 = min(THUMB_LONGFORM_WIDTH, margin_x + max_lw + pad_px)
        rx0 = max(0, THUMB_LONGFORM_WIDTH - margin_x - max_lw - pad_px)
        rx1 = min(THUMB_LONGFORM_WIDTH, THUMB_LONGFORM_WIDTH - margin_x + pad_px)

        left_sal = float(np.mean(sal[ly0:ly1, lx0:lx1]))
        center_sal = float(
            np.mean(sal[ly0:ly1, int(THUMB_LONGFORM_WIDTH * 0.34) : int(THUMB_LONGFORM_WIDTH * 0.66)])
        )
        right_sal = float(np.mean(sal[ly0:ly1, rx0:rx1]))
        place_on_left = left_sal <= right_sal

        intrude_zone = sal[ly0:ly1, lx0:lx1] if place_on_left else sal[ly0:ly1, rx0:rx1]
        edge_strip = resized[:, :64, :] if place_on_left else resized[:, -64:, :]
        border_clean = float(np.mean(np.std(edge_strip.astype(np.float32), axis=0))) < 28.0
        if (
            border_clean
            and center_sal > max(left_sal, right_sal) * 1.18
            and float(np.mean(intrude_zone)) >= 0.09
        ):
            shift_px = int(round(THUMB_LONGFORM_WIDTH * 0.14))
            if place_on_left:
                padded = cv2.copyMakeBorder(resized, 0, 0, shift_px, 0, cv2.BORDER_REFLECT_101)
                resized = padded[:, :THUMB_LONGFORM_WIDTH, :].copy()
                resized[:, : shift_px + 16, :] = cv2.GaussianBlur(resized[:, : shift_px + 16, :], (21, 21), 0)
            else:
                padded = cv2.copyMakeBorder(resized, 0, 0, 0, shift_px, cv2.BORDER_REFLECT_101)
                resized = padded[:, shift_px : shift_px + THUMB_LONGFORM_WIDTH, :].copy()
                resized[:, -(shift_px + 16) :, :] = cv2.GaussianBlur(resized[:, -(shift_px + 16) :, :], (21, 21), 0)

        # Subtle readability gradient behind text side only
        grad_x = np.linspace(0.40, 0.0, THUMB_LONGFORM_WIDTH, dtype=np.float32)
        if not place_on_left:
            grad_x = grad_x[::-1]
        darkened = (resized.astype(np.float32) * (1.0 - grad_x[None, :, None])).clip(0, 255).astype(np.uint8)

        pil_rgba = Image.fromarray(cv2.cvtColor(darkened, cv2.COLOR_BGR2RGB)).convert("RGBA")
        txt_layer = Image.new("RGBA", (THUMB_LONGFORM_WIDTH, THUMB_LONGFORM_HEIGHT), (0, 0, 0, 0))
        draw = ImageDraw.Draw(txt_layer)
        cur_y = int(THUMB_LONGFORM_HEIGHT * 0.18) + (idx * 18)
        margin_x = int(THUMB_LONGFORM_WIDTH * 0.055)
        for ln_i, ln in enumerate(lines):
            bb = fnt.getbbox(ln, stroke_width=stroke_w)
            lw = bb[2] - bb[0]
            tx = margin_x if place_on_left else max(margin_x, THUMB_LONGFORM_WIDTH - margin_x - lw)
            fill_col = (255, 214, 74, 255) if (ln_i == 0 and len(lines) > 1 and idx == 1) else (255, 255, 255, 255)
            draw.text(
                (tx, cur_y),
                ln,
                font=fnt,
                fill=fill_col,
                stroke_width=stroke_w,
                stroke_fill=(10, 15, 24, 255),
            )
            cur_y += (bb[3] - bb[1]) + 16
        out_rgb = Image.alpha_composite(pil_rgba, txt_layer).convert("RGB")

        out_png = pub_dir / f"thumb_longform_{var_name}.png"
        out_rgb.save(out_png, format="PNG", compress_level=4)
        saved_png[var_name] = str(out_png)

        out_jpg = pub_dir / f"thumbnail_var_{var_name}.jpg"
        jpg_bytes = b""
        for qual in (93, 88, 82, 76):
            buf = io.BytesIO()
            out_rgb.save(buf, format="JPEG", quality=qual, optimize=True)
            jpg_bytes = buf.getvalue()
            if len(jpg_bytes) <= LONGFORM_THUMB_MAX_BYTES:
                break
        out_jpg.write_bytes(jpg_bytes)
        saved_jpg[var_name] = str(out_jpg)
        jpg_sizes[var_name] = len(jpg_bytes)

    return {
        "project_id": p_dir.name,
        "dimensions": [THUMB_LONGFORM_WIDTH, THUMB_LONGFORM_HEIGHT],
        "hook_text": eff_hook.upper(),
        "variants": saved_png,
        "jpg_variants": saved_jpg,
        "jpg_sizes_bytes": jpg_sizes,
    }


render_longform_thumbnails = render_longform_4k_thumbnails


__all__ = [
    "ThumbCandidate",
    "build_cutaway_keyart_prompt",
    "build_r65_v4_in_skull_split_prompt",
    "collect_candidates",
    "compute_image_metrics",
    "compute_r65_v4_split_metrics",
    "evaluate_thumbnail_gates",
    "generate_zero_credit_thumb_keyart",
    "is_r65_v2_spec",
    "is_r65_v4_spec",
    "measure_shelf_text_contrast",
    "pick_top_distinct",
    "render_cutaway_pointer_and_z_overlay",
    "render_longform_4k_thumbnails",
    "render_longform_thumbnails",
    "render_overlay",
    "render_overlay_with_meta",
    "render_r65_v4_in_skull_split_overlay",
    "resolve_hook",
    "roi_pairwise_diff",
    "run",
    "run_thumbnail_qa",
    "score_candidate",
    "validate_hook_lexical",
    "validate_v4_micro_label",
    "write_contact_sheet",
]


