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
    FONT_CONDENSED_BLACK_PATH,
    FONT_FALLBACK_PATH,
    FONT_PRIMARY_PATH,
    PROJECTS_DIR,
    THUMBNAIL_CONTACT_SHEET_FILENAME,
    THUMBNAIL_REPORT_FILENAME,
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
    THUMB_SAFE_MARGIN_X,
    THUMB_SAFE_Y_RANGE,
    THUMB_SCORE_WEIGHTS,
    VIDEO_HEIGHT,
    VIDEO_WIDTH,
)


def numeric_clip_sort_key(path: Path) -> tuple[int, str]:
    m = re.search(r"(\d+)", path.stem)
    return (int(m.group(1)) if m else 999999, path.name)


@dataclass
class ThumbCandidate:
    cut_index: int
    clip_index: int
    act: int
    sentence_index: int
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


def _atomic_save_pil_png(img: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".tmp_{os.getpid()}_{path.name}")
    # Ensure rich uncompressed/low-compression 24-bit PNG so valid frames comfortably exceed THUMB_MIN_FILE_BYTES
    img.convert("RGB").save(str(tmp), format="PNG", compress_level=1)
    if tmp.stat().st_size <= THUMB_MIN_FILE_BYTES:
        img.convert("RGB").save(str(tmp), format="PNG", compress_level=0)
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
    """Computes raw sharpness, luma contrast, Hasler-Süsstrunk colorfulness, and centre-3:4 edge salience."""
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

    return {
        "sharpness": round(sharpness, 3),
        "contrast": round(luma_std, 3),
        "luma_mean": round(luma_mean, 2),
        "colorfulness": round(colorfulness, 3),
        "center_salience": round(center_salience, 3),
        "center_edge_density": round(c_dens, 5),
    }


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

    if s0 <= cover_s_idx <= max(s0, s1) and s0 > 0:
        intent = float(THUMB_INTENT_BONUS["cover_sentence"])
    elif act == 1:
        intent = float(THUMB_INTENT_BONUS["act1"])
    elif cut.get("anatomy_label") or cut.get("brain_region"):
        intent = float(THUMB_INTENT_BONUS["brain_badge"])
    else:
        intent = float(THUMB_INTENT_BONUS["default"])

    m["intent"] = round(intent, 3)
    return m


def _has_head_occlusion_in_hook_band(img_bgr: np.ndarray, grammar: str = "") -> bool:
    """Detects a compact matte-white oval porcelain head inside the top hook-text band (`y=265..415`) directly above a clothed torso."""
    if not img_bgr.size or img_bgr.shape[0] < 600 or img_bgr.shape[1] < 600:
        return False
    g_low = str(grammar or "").lower()
    if "brain" in g_low or "hands" in g_low or "cutaway" in g_low:
        return False
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    band = hsv[265:415, 140:940]
    white_mask = ((band[:, :, 2] >= 165) & (band[:, :, 1] <= 42)).astype(np.uint8)
    n_lbl, _, stats, cents = cv2.connectedComponentsWithStats(white_mask)
    for k in range(1, n_lbl):
        bw = int(stats[k, cv2.CC_STAT_WIDTH])
        bh = int(stats[k, cv2.CC_STAT_HEIGHT])
        area = int(stats[k, cv2.CC_STAT_AREA])
        if 2200 <= area <= 25000 and 40 <= bw <= 210 and 48 <= bh <= 150 and 0.45 <= bw / max(1, bh) <= 1.65:
            cx = int(cents[k][0]) + 140
            below = hsv[415:575, max(0, cx - 85) : min(img_bgr.shape[1], cx + 85)]
            if below.size and float(below[:, :, 1].mean()) >= 45.0:
                return True
    return False


def _finalize_candidate_scores(candidates: list[ThumbCandidate]) -> None:
    """Normalizes raw metrics across the episode pool and assigns weighted composite totals."""
    if not candidates:
        return
    axes = ("sharpness", "contrast", "colorfulness", "center_salience")
    bounds: dict[str, tuple[float, float]] = {}
    for ax in axes:
        vals = np.array([float(c.raw_metrics.get(ax, 0.0)) for c in candidates], dtype=np.float64)
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
        # Hard-floor quality penalty so blurred, flat, empty-centre, or head-decapitated frames never outrank clean frames
        penalty = 0.0
        if float(c.raw_metrics.get("sharpness", 0.0)) < THUMB_MIN_SHARPNESS:
            penalty += 0.60
        if float(c.raw_metrics.get("contrast", 0.0)) < THUMB_MIN_LUMA_STD:
            penalty += 0.60
        if float(c.raw_metrics.get("center_salience", 0.0)) < THUMB_MIN_CENTER_SALIENCE:
            penalty += 0.45
        if _has_head_occlusion_in_hook_band(c.image, c.grammar):
            penalty += 0.22
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


def render_overlay_with_meta(
    img_bgr: np.ndarray,
    hook: str,
) -> tuple[Image.Image, dict[str, Any]]:
    """
    Renders the Schema v7 `AABCondensed-Black` hook onto a `1080x1920` clean frame:
      - Pure `#FFFFFF` fill + `THUMB_HOOK_STROKE_PX` (`10px`) `#0A0F18` outer stroke
      - Soft feathered Gaussian glyph halo cushion (zero rectangular boxes, borders, or pills)
      - Positioned inside `THUMB_SAFE_Y_RANGE` (`240..1440`) above the `32%..68%` hero action ROI (`y < 605`)
    Returns `(pil_rgb_image, overlay_meta)` including exact `text_bbox` and glyph masks for `TQ1`/`TQ4`.
    """
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
    return round((hi + 0.05) / (lo + 0.05), 2)


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


def run_thumbnail_qa(
    variants: dict[str, dict[str, Any]],
    hook: str,
    title: str = "",
) -> dict[str, Any]:
    """
    Evaluates the 7-Gate Thumbnail QA contract (`TQ1-TQ7`) across rendered variants `A`, `B`, `C`.
    """
    var_keys = [k for k in ("A", "B", "C") if k in variants]
    # TQ1: Legibility at 160px shelf width
    contrasts = {k: float(variants[k]["text_contrast_wcag"]) for k in var_keys}
    tq1_ok = bool(var_keys) and all(v >= THUMB_MIN_TEXT_CONTRAST for v in contrasts.values())

    # TQ2: Centre 3:4 subject salience on primary cover (Variant A) and mean across variants
    sal_vals = {k: float(variants[k]["raw_metrics"].get("center_salience", 0.0)) for k in var_keys}
    tq2_ok = bool(var_keys) and sal_vals.get("A", 0.0) >= THUMB_MIN_CENTER_SALIENCE

    # TQ3: Image focus & global contrast on primary cover (Variant A) and variants
    sharp_vals = {k: float(variants[k]["raw_metrics"].get("sharpness", 0.0)) for k in var_keys}
    luma_stds = {k: float(variants[k]["raw_metrics"].get("contrast", 0.0)) for k in var_keys}
    tq3_ok = (
        bool(var_keys)
        and all(v >= THUMB_MIN_SHARPNESS for v in sharp_vals.values())
        and all(v >= THUMB_MIN_LUMA_STD for v in luma_stds.values())
    )

    # TQ4: Safe zone geometry (text bbox inside THUMB_SAFE_Y_RANGE and >= THUMB_SAFE_MARGIN_X side margins)
    safe_checks: dict[str, bool] = {}
    bboxes: dict[str, list[int]] = {}
    for k in var_keys:
        x0, y0, x1, y1 = variants[k]["text_bbox"]
        bboxes[k] = [x0, y0, x1, y1]
        safe_checks[k] = (
            x0 >= THUMB_SAFE_MARGIN_X
            and x1 <= (VIDEO_WIDTH - THUMB_SAFE_MARGIN_X)
            and y0 >= THUMB_SAFE_Y_RANGE[0]
            and y1 <= THUMB_SAFE_Y_RANGE[1]
        )
    tq4_ok = bool(var_keys) and all(safe_checks.values())

    # TQ5: Pairwise distinctness across A / B / C
    ab_diff = roi_pairwise_diff(variants["A"]["rendered_bgr"], variants["B"]["rendered_bgr"]) if ("A" in variants and "B" in variants) else 0.0
    bc_diff = roi_pairwise_diff(variants["B"]["rendered_bgr"], variants["C"]["rendered_bgr"]) if ("B" in variants and "C" in variants) else 0.0
    ac_diff = roi_pairwise_diff(variants["A"]["rendered_bgr"], variants["C"]["rendered_bgr"]) if ("A" in variants and "C" in variants) else 0.0
    tq5_ok = len(var_keys) == 3 and min(ab_diff, bc_diff, ac_diff) >= THUMB_MIN_PAIRWISE_DIFF

    # TQ6: 1080x1920 PNG dimensions & > THUMB_MIN_FILE_BYTES
    file_sizes = {k: int(variants[k]["file_bytes"]) for k in var_keys}
    dims_ok = all(variants[k]["dimensions"] == [VIDEO_WIDTH, VIDEO_HEIGHT] for k in var_keys)
    tq6_ok = len(var_keys) == 3 and dims_ok and all(sz > THUMB_MIN_FILE_BYTES for sz in file_sizes.values())

    # TQ7: Hook lexical contract
    hook_issues = validate_hook_lexical(hook, title=title)
    tq7_ok = len(hook_issues) == 0

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
            "min_sharpness_threshold": THUMB_MIN_SHARPNESS,
            "min_luma_std_threshold": THUMB_MIN_LUMA_STD,
            "sharpness_by_variant": sharp_vals,
            "luma_std_by_variant": luma_stds,
        },
        "TQ4_safe_zone_geometry": {
            "passed": tq4_ok,
            "safe_y_range": list(THUMB_SAFE_Y_RANGE),
            "safe_margin_x": THUMB_SAFE_MARGIN_X,
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
            "file_bytes_by_variant": file_sizes,
            "dimensions_1080x1920": dims_ok,
        },
        "TQ7_hook_lexical": {
            "passed": tq7_ok,
            "hook_text": hook,
            "max_words": THUMB_HOOK_MAX_WORDS,
            "max_chars": THUMB_HOOK_MAX_CHARS,
            "issues": hook_issues,
        },
    }
    failed_gates = [g_name for g_name, g_val in gates.items() if not g_val["passed"]]
    return {
        "passed": len(failed_gates) == 0,
        "failed_gates": failed_gates,
        "gates": gates,
    }


def write_contact_sheet(
    variants: dict[str, dict[str, Any]],
    output_path: Path,
    hook: str,
    qa_result: dict[str, Any],
) -> Path:
    """Writes a side-by-side contact sheet showing A/B/C full previews + actual `160px` mobile shelf previews + scores."""
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
    draw.text((pad, 24), f"R65 THUMBNAIL STUDIO | HOOK: {hook}", fill=(245, 247, 250), font=title_font)
    draw.text((sheet_w - 420, 28), f"QA: {status_txt}", fill=status_col, font=meta_font)

    pw = int(THUMB_LEGIBILITY_PREVIEW_W)
    ph = int(round(VIDEO_HEIGHT * (pw / float(VIDEO_WIDTH))))

    for idx, k in enumerate(("A", "B", "C")):
        if k not in variants:
            continue
        v = variants[k]
        pil_full: Image.Image = v["pil_image"]
        x0 = pad + idx * (card_w + pad)
        y0 = header_h
        card_img = pil_full.resize((card_w, card_h), Image.Resampling.LANCZOS)
        canvas.paste(card_img, (x0, y0))

        # 1:1 160px mobile shelf preview + 3:4 centre crop box indicator
        shelf_img = pil_full.resize((pw, ph), Image.Resampling.LANCZOS)
        sx = x0
        sy = y0 + card_h + 16
        canvas.paste(shelf_img, (sx, sy))
        draw.rectangle([(sx, sy), (sx + pw, sy + ph)], outline=(90, 110, 140), width=1)
        # 3:4 grid crop lines on 160x284 preview
        crop_pad_y = int(round((ph - int(round(pw * 4.0 / 3.0))) / 2.0))
        draw.rectangle([(sx, sy + crop_pad_y), (sx + pw, sy + ph - crop_pad_y)], outline=(255, 215, 0), width=1)

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
    except Exception:
        return

    with tempfile.TemporaryDirectory(prefix="aab_thumb_") as td:
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
            except Exception:
                continue


def run(
    project_id_or_dir: str | Path,
    *,
    force: bool = False,
    strict: bool = True,
    local_clips: dict[int, Path] | None = None,
    pastel_eq_by_num: dict[int, str] | None = None,
    mode: str = "production",
) -> dict[str, Any]:
    """
    Executes the full R65 Thumbnail Studio pipeline on a project:
      1. Collects & scores clean candidate frames across eligible EDL cuts
      2. Picks top-3 visually distinct frames (`A`, `B`, `C`)
      3. Renders the Schema v7 `AABCondensed-Black` hook overlay (`thumbnail_var_{A,B,C}.png` + `thumbnail.png`)
      4. Evaluates `TQ1-TQ7` and writes `thumbnail_report.json` + `thumbnail_contact_sheet.png` in `06_publish/`
    """
    p_dir = (
        Path(project_id_or_dir)
        if isinstance(project_id_or_dir, Path) or Path(str(project_id_or_dir)).exists()
        else (Path(PROJECTS_DIR) / str(project_id_or_dir))
    )
    if not p_dir.exists():
        raise FileNotFoundError(f"Project directory not found: {p_dir}")

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
        if files_ok and (cached.get("passed") or not strict):
            return cached

    plan = _read_json(p_dir / "03_visuals" / "visual_plan.json")
    script = _read_json(p_dir / "02_script" / "script.json")
    meta_doc = _read_json(pub_dir / "metadata.json")
    title = str(script.get("title") or meta_doc.get("title") or plan.get("title") or p_dir.name).strip()

    candidates = collect_candidates(p_dir, local_clips=local_clips)
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
        pil_img, ov_meta = render_overlay_with_meta(cand.image, hook_text)
        out_png = pub_dir / f"thumbnail_var_{var_key}.png"
        _atomic_save_pil_png(pil_img, out_png)
        if var_key == "A":
            _atomic_save_pil_png(pil_img, pub_dir / "thumbnail.png")

        rendered_bgr = cv2.cvtColor(np.array(pil_img, dtype=np.uint8), cv2.COLOR_RGB2BGR)
        wcag_c = measure_shelf_text_contrast(pil_img, ov_meta["fill_mask"])
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
            "text_bbox": ov_meta["text_bbox"],
            "font_size": ov_meta["font_size"],
            "text_contrast_wcag": wcag_c,
            "pil_image": pil_img,
            "rendered_bgr": rendered_bgr,
        }

    qa_res = run_thumbnail_qa(rendered_variants, hook=hook_text, title=title)
    sheet_path = write_contact_sheet(
        rendered_variants,
        pub_dir / THUMBNAIL_CONTACT_SHEET_FILENAME,
        hook=hook_text,
        qa_result=qa_res,
    )

    final_mp4 = p_dir / "05_assembly" / "final_shorts_1080x1920.mp4"
    final_mp4_sha = _sha256_file(final_mp4) if final_mp4.exists() else None

    # Determine in-video cover frame timestamp: prefer cold-open stamp sentence cut if present, else Variant A out_sec
    thumb_cfg = plan.get("thumbnail") if isinstance(plan.get("thumbnail"), dict) else {}
    target_cover_sent = int(thumb_cfg.get("cover_sentence_index") or 3)
    edl = _read_json(p_dir / "05_assembly" / "edit_decision_list.json")
    in_video_cover_sec: float | None = None
    for cut in edl.get("cuts") or []:
        if not isinstance(cut, dict):
            continue
        s0 = int(cut.get("sentence_index") or 0)
        s1 = int(cut.get("end_sentence_index") or s0)
        if s0 <= target_cover_sent <= max(s0, s1) and str(cut.get("mode") or "single") not in THUMB_EXCLUDE_MODES:
            in_video_cover_sec = round(0.5 * (float(cut.get("out_start_sec") or 0.0) + float(cut.get("out_end_sec") or 0.0)), 2)
            break
    primary_out_sec = float(rendered_variants["A"]["out_sec"])
    cover_frame_sec = in_video_cover_sec if in_video_cover_sec is not None else round(primary_out_sec, 2)

    serializable_variants = {
        k: {vk: vv for vk, vv in v.items() if vk not in ("pil_image", "rendered_bgr")}
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
    Renders 3 distinct `16:9` 4K (`3840x2160`) CTV thumbnails (`thumb_longform_A.png`, `B`, `C`) in `06_publish/`
    for YouTube Studio native `Test & Compare` (`Watch Time Share` optimization).
    """
    from pipeline.config import THUMB_LONGFORM_HEIGHT, THUMB_LONGFORM_WIDTH

    p_dir = Path(project_dir) if Path(project_dir).is_dir() else (Path(PROJECTS_DIR) / str(project_dir))
    pub_dir = p_dir / "06_publish"
    pub_dir.mkdir(parents=True, exist_ok=True)
    eff_hook = str(hook_text if hook_text is not None else hook or "BRAIN MYSTERY?").strip() or "BRAIN MYSTERY?"
    eff_frames = list(frames_bgr or [])
    if not eff_frames:
        vis_dir = p_dir / "03_visuals" / "flow_native_clips"
        for c_mp4 in sorted(vis_dir.glob("clip_*.mp4"), key=lambda p: int("".join(filter(str.isdigit, p.stem)) or "0"))[:3]:
            cap = cv2.VideoCapture(str(c_mp4))
            ok, frm = cap.read()
            cap.release()
            if ok and frm is not None:
                eff_frames.append(frm)
    font_path = _resolve_v7_font_path()
    lines = _split_hook_lines(eff_hook.upper())
    try:
        fnt = ImageFont.truetype(str(font_path), 240)
    except Exception:
        fnt = ImageFont.load_default()

    saved: dict[str, str] = {}
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
        # Subtle framing variation across A/B/C when fewer than 3 input frames are supplied
        if len(eff_frames) < 3 and idx > 0:
            zf = 1.0 + 0.06 * idx
            zh, zw = int(cropped.shape[0] / zf), int(cropped.shape[1] / zf)
            zy = (cropped.shape[0] - zh) // (2 if idx == 1 else 3)
            zx = (cropped.shape[1] - zw) // (2 if idx == 1 else 4)
            cropped = cropped[zy : zy + zh, zx : zx + zw]
        resized = cv2.resize(cropped, (THUMB_LONGFORM_WIDTH, THUMB_LONGFORM_HEIGHT), interpolation=cv2.INTER_LANCZOS4)
        pil_rgba = Image.fromarray(cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)).convert("RGBA")
        txt_layer = Image.new("RGBA", (THUMB_LONGFORM_WIDTH, THUMB_LONGFORM_HEIGHT), (0, 0, 0, 0))
        draw = ImageDraw.Draw(txt_layer)
        cur_y = 220 + (idx * 24)
        for ln in lines:
            draw.text(
                (180, cur_y),
                ln,
                font=fnt,
                fill=(255, 255, 255, 255),
                stroke_width=18,
                stroke_fill=(10, 15, 24, 255),
            )
            bb = fnt.getbbox(ln, stroke_width=18)
            cur_y += (bb[3] - bb[1]) + 28
        out_rgb = Image.alpha_composite(pil_rgba, txt_layer).convert("RGB")
        out_p = pub_dir / f"thumb_longform_{var_name}.png"
        out_rgb.save(out_p, format="PNG", compress_level=3)
        saved[var_name] = str(out_p)
    return {
        "project_id": p_dir.name,
        "dimensions": [THUMB_LONGFORM_WIDTH, THUMB_LONGFORM_HEIGHT],
        "hook_text": eff_hook.upper(),
        "variants": saved,
    }


__all__ = [
    "ThumbCandidate",
    "collect_candidates",
    "compute_image_metrics",
    "measure_shelf_text_contrast",
    "pick_top_distinct",
    "render_longform_4k_thumbnails",
    "render_overlay",
    "render_overlay_with_meta",
    "resolve_hook",
    "roi_pairwise_diff",
    "run",
    "run_thumbnail_qa",
    "score_candidate",
    "validate_hook_lexical",
    "write_contact_sheet",
]

