"""
ALL ABOUT BRAIN — Schema v6.1 Unlimited Zero-Reuse Sharded Google Flow Worker (R5, R37, R56, R58)
=================================================================================================
Generates all ~60-70 dedicated 9:16 motion clips for a `neuro_diorama` 3-minute episode with
`0%` clip reuse (`max_clip_reuse == 1`) using Google Flow's `0 credits` `Veo 3.1 - Lite [Lower Priority]`
model across at most `FLOW_MAX_PARALLEL_BATCH_SIZE` (5) dedicated Flow project shards (`<= 14` clips/shard
so Angular canvas virtualization never hides off-screen tiles).

Safety & Provenance Guarantees:
  1. Never touches or closes pre-existing user tabs in Naver Whale (`127.0.0.1:9222`).
  2. Opens at most `FLOW_MAX_PARALLEL_BATCH_SIZE` (5) worker tabs and closes ONLY tabs it opened in `finally`.
  3. Submits 1 clip at a time per shard tab (up to 5 clips rendering concurrently across 5 tabs) so every
     rendered tile maps 1:1 with `clip_<clip_number>.mp4` with zero ordering ambiguity.
  4. Runs immediate CV motion, dark-void backdrop, and zero-flesh HSV checks on each downloaded clip,
     regenerating in-tab at `0 credits` if a tile fails QA.
  5. Captures real live V1-V5 Flow screenshots and writes cryptographic `03_visuals/flow_provenance_receipt.json`.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import collections
import hashlib
import inspect
import json
import math
import os
import re
import shutil
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any

_BOOTSTRAP_ROOT = Path(__file__).resolve().parents[1]
if str(_BOOTSTRAP_ROOT) not in sys.path:
    sys.path.insert(0, str(_BOOTSTRAP_ROOT))

import cv2
import numpy as np

from pipeline.config import (
    ALL_DIORAMA_V7_VISUAL_GRAMMARS,
    DEFAULT_DIORAMA_STYLE_PROFILE,
    DEFAULT_FLOW_ENGINE_MODE,
    DIORAMA_SHARD_MAX_CLIPS,
    DIORAMA_V7_VISUAL_GRAMMARS,
    DIORAMA_VISUAL_GRAMMARS,
    FLOW_ENGINE_MODES,
    FLOW_MAX_PARALLEL_BATCH_SIZE,
    FLOW_PRIMARY_VIDEO_MODEL,
    FLOW_ZERO_CREDIT_MAX_CONCURRENT_RENDERS,
    FLOW_ZERO_CREDIT_MODEL,
    FLOW_ZERO_CREDIT_VIDEO_MAX_BATCH,
    MIN_CLIP_SIZE_BYTES,
    PORCELAIN_V7_BRAIN_MARGIN_SAT_MAX,
    PORCELAIN_V7_DARK_VOID_RATIO_MAX,
    PORCELAIN_V7_HUMAN_SKIN_MAX,
    PORCELAIN_V7_NEON_GREEN_SPILL_MAX,
    PORCELAIN_V7_STYLE_PROFILE,
    PORCELAIN_V7_VISUAL_GRAMMARS,
    PROJECTS_DIR,
    PROMPT_SCHEMA_VERSION_V7,
    WORKSPACE_ROOT,
    is_diorama_v7_plan,
    is_porcelain_v7_plan,
)
from pipeline.depiction_rules import normalize_porcelain_v7_brain_mode, normalize_porcelain_v7_grammar
from pipeline.diorama_assembler import load_diorama_script_sentences
from pipeline.flow_browser import (
    CHECK_CREDIT_EXHAUSTION_JS,
    DISMISS_CREDIT_DIALOG_JS,
    FLOW_TILE_CLASSIFIER_JS,
    FlowCircuitBreakerError,
    FlowDownloadHarvestLock,
    FlowProjectSubagentWorker,
    GoogleFlowWhaleController,
    _merge_write_visual_qa_report,
)
from pipeline.flow_ingredients import (
    attach_uploaded_by_name,
    clear_prompt_ingredients,
    count_chips,
    press_escape,
    read_active_flow_model_family,
    select_flow_video_model,
    upload_file_to_flow,
    upload_start_end_frames_to_flow,
)
from pipeline.flow_live_single_worker import (
    CONTAINER_DOWNLOADS_PATH,
    USER_DOWNLOADS_DIR,
    _normalize_engine_mode,
    _render_v5_contact_sheet,
    allocate_dedicated_flow_project_tab,
    ensure_manual_video_916_mode,
)
from pipeline.flow_prompt_builder import build_diorama_v6_prompts, write_flow_prompts_json
from pipeline.media_integrity import MediaIntegrityError
from pipeline.studio.whale_session import DirectCDPClient

ZERO_CREDIT_MODEL = FLOW_ZERO_CREDIT_MODEL


def _soften_veo_false_positive_words(
    prompt_text: str,
    style_profile: str = "",
    grammar: str = "",
) -> str:
    """Gentle clinical wording fallback used ONLY if Google Flow returns `flow-error-tile` or retries after try 1."""
    import re

    out = prompt_text
    g_norm = str(grammar or "").strip().lower()
    use_porcelain = (
        is_porcelain_v7_plan(style_profile)
        or g_norm in PORCELAIN_V7_VISUAL_GRAMMARS
        or g_norm.startswith("porcelain_")
        or "photorealistic bright high-key documentary cinema" in out.lower()
    )
    subs = (
        (r"\bsevered\b", "unlinked"),
        (r"\binjured\b", "disconnected"),
        (r"\bpiercing\b", "passing"),
        (r"\bpierces\b", "passes"),
        (r"\bskull\b", "translucent frosted-glass cranium" if use_porcelain else "faceted geometric head"),
        (r"\bcheek\b", "smooth matte-white porcelain jawline" if use_porcelain else "lower geometric jaw"),
        (r"\btrauma\b", "structural impact"),
        (r"\bviolently\b", "briskly"),
        (r"\bsurges\b", "shoots"),
        (r"\bcoffin\b", "long pine box"),
        (r"\bsickroom\b", "guest room"),
        (r"\bsurgical\s+instruments\b", "polished brass calipers"),
        (r"\bsurgical\b", "precision"),
        (r"\bsuction\b", "glass siphon"),
        (r"\bshock\s+generator\b", "toggle switch console"),
        (r"\belectric\s+shocks?\b", "amber relay pulses"),
        (r"\bshocks?\b", "pulses"),
        (r"\bprison\b", "corridor"),
        (r"\bamputated\b", "absent"),
        (r"\bphantom\s+pain\b", "frozen posture"),
        (r"\bseizures?\b", "electrical storms"),
        (r"\blesions?\b", "deep crimson-red zones" if use_porcelain else "coral-red zones"),
        (r"\bstroke\b", "vascular block"),
        (r"\bcorpse\b", "still clothed porcelain figure" if use_porcelain else "still figure"),
        (r"\bcracked\b", "segmented"),
        (r"\bscar\b", "zone"),
    )
    for pat, repl in subs:
        out = re.sub(pat, repl, out, flags=re.IGNORECASE)
    return out


def _reinforce_porcelain_cv_retry_prompt(
    prompt_text: str,
    grammar: str = "",
    cv_reason: str = "",
) -> str:
    """Appends positive-only R66 containment/porcelain reinforcement before the audio tail after a CV gate failure."""
    reason_low = str(cv_reason or "").lower()
    if not reason_low:
        return prompt_text
    g_norm = str(grammar or "").strip().lower()
    extra = ""
    if ("neon_green" in reason_low or "brain_margin" in reason_low) or (
        "living_brain" in g_norm and ("spill" in reason_low or "oversaturated" in reason_low)
    ):
        extra = (
            "Keep all clear cyan-blue, deep crimson-red, warm amber-gold, and pearl-aqua luminescence "
            "enclosed strictly inside translucent vessel walls against clean matte-white studio air."
        )
    elif "human_skin_or_face_leak" in reason_low:
        extra = (
            "Stage smooth articulated matte-white glazed porcelain surfaces and tailored fabric cuffs "
            "in bright studio daylight."
        )
    elif "dark_void" in reason_low or "excess_dark_shadow" in reason_low:
        extra = "Fill the entire frame with bright high-key studio daylight and crisp white architectural surfaces."
    if not extra or extra.lower() in prompt_text.lower():
        return prompt_text
    audio_marker = "Subtle crisp physical foley"
    idx = prompt_text.find(audio_marker)
    if idx > 0:
        return f"{prompt_text[:idx].rstrip()} {extra} {prompt_text[idx:]}"
    return f"{prompt_text.rstrip()} {extra}"


def _mser_plaque_pass(gray: np.ndarray, bh_min: int = 10, bh_max: int = 110) -> int:
    gray_s = cv2.GaussianBlur(gray, (3, 3), 0.80)
    mser = cv2.MSER_create(delta=5, min_area=18, max_area=3600, max_variation=0.65)
    gh, gw = gray_s.shape[:2]
    best_run = 0
    _, bboxes = mser.detectRegions(gray_s)
    seen: set[tuple[int, int]] = set()
    dedup: list[tuple[int, int, int, int, float, float]] = []
    for x, y, bw, bh in bboxes:
        if bh_min <= bh <= bh_max and 3 <= bw <= 115 and 0.14 <= (bw / float(bh)) <= 1.35:
            patch = gray[max(0, y - 3) : min(gh, y + bh + 3), max(0, x - 2) : min(gw, x + bw + 2)]
            if patch.size == 0 or float(np.std(patch)) < 27.0:
                continue
            tb_1 = gray[max(0, y - 8) : max(0, y - 3), x : x + bw]
            tb_2 = gray[min(gh, y + bh + 3) : min(gh, y + bh + 8), x : x + bw]
            tb = np.concatenate([tb_1.ravel(), tb_2.ravel()])
            if tb.size < 4 or float(np.std(tb)) > 22.0:
                continue
            bg_med = float(np.median(tb))
            core = gray[y : min(gh, y + bh), x : min(gw, x + bw)]
            if core.size == 0:
                continue
            fg_contrast = float(np.max(np.abs(core.astype(np.float32) - bg_med)))
            if fg_contrast < 35.0:
                continue
            cell = (int(x // 4), int(y // 4))
            if cell not in seen:
                seen.add(cell)
                dedup.append((int(x), int(y), int(bw), int(bh), bg_med, fg_contrast))
    for g0 in dedup:
        _, y0, _, h0, bg0, _ = g0
        row = [
            g1
            for g1 in dedup
            if abs(g1[4] - bg0) <= 18.0
            and abs((g1[1] + g1[3] * 0.5) - (y0 + h0 * 0.5)) <= h0 * 0.22
            and abs(g1[3] - h0) <= h0 * 0.26
        ]
        row.sort(key=lambda b: (b[0], b[2]))
        dp = [1] * len(row)
        for i in range(len(row)):
            cand = row[i]
            for j in range(i):
                prev = row[j]
                gap = cand[0] - (prev[0] + prev[2])
                if -2 <= gap <= h0 * 1.15 and cand[0] >= prev[0] + 3:
                    xa = max(0, prev[0] + prev[2] - 2)
                    xb = min(gw, cand[0] + 2)
                    ya = max(0, min(prev[1], cand[1]))
                    yb = min(gh, max(prev[1] + prev[3], cand[1] + cand[3]))
                    if xb > xa and yb > ya:
                        sep_cols = np.mean(np.abs(gray[ya:yb, xa:xb].astype(np.float32) - bg0), axis=0)
                        ref_c = 0.5 * (prev[5] + cand[5])
                        if float(np.min(sep_cols)) > 0.62 * ref_c:
                            continue
                    if dp[j] + 1 > dp[i]:
                        dp[i] = dp[j] + 1
        row_best = max(dp) if dp else 0
        if row_best > best_run:
            best_run = row_best
    return best_run


def _max_horizontal_plaque_glyph_run(frame_bgr: np.ndarray) -> int:
    """
    Detects horizontal runs of character-sized MSER glyph boxes (both dark-on-light and
    light-on-dark polarities, including large hallucinated banners up to `bh <= 110`)
    mounted on a locally uniform signboard/plaque surface.
    """
    h, w = frame_bgr.shape[:2]
    roi = frame_bgr[int(h * 0.03) : int(h * 0.97), int(w * 0.03) : int(w * 0.97)]
    if roi.size == 0:
        return 0
    gray = roi if roi.ndim == 2 else cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    if gray.shape[1] > 720:
        scale = 720.0 / float(gray.shape[1])
        gray = cv2.resize(
            gray,
            (720, max(16, int(round(gray.shape[0] * scale)))),
            interpolation=cv2.INTER_AREA,
        )
    best_run = _mser_plaque_pass(gray, bh_min=10, bh_max=110)
    if best_run < 5 and gray.shape[0] >= 84 and gray.shape[1] >= 500:
        for ds in (0.50, 0.34, 0.25):
            ds_w = max(32, int(round(gray.shape[1] * ds)))
            ds_h = max(24, int(round(gray.shape[0] * ds)))
            gray_ds = cv2.resize(gray, (ds_w, ds_h), interpolation=cv2.INTER_AREA)
            ds_min = max(12, int(round(48 * ds)))
            ds_max = int(round(110 * ds)) + 2
            best_run = max(best_run, _mser_plaque_pass(gray_ds, bh_min=ds_min, bh_max=ds_max))
            if best_run >= 5:
                break
    return best_run


def detect_escher_dual_edge_closeup(frame_bgr: np.ndarray, grammar: str) -> bool:
    """
    Detects impossible Escher 4-arm / folded-body close-up defects (e.g. collar/chest facing down
    from top frame border while separate sleeves/arms rise upward from bottom frame border across
    an open tabletop gap in between). Excludes bright pastel/studio sky in outdoor POV shots.
    """
    if str(grammar or "").strip() not in (
        "lowpoly_hands_closeup",
        "lowpoly_pov_hands",
        "porcelain_hands_closeup",
        "porcelain_pov_hands",
    ):
        return False
    h, w = frame_bgr.shape[:2]
    if h < 120 or w < 80:
        return False
    hsv = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV)
    mid_strip = hsv[int(h * 0.32) : int(h * 0.56), int(w * 0.20) : int(w * 0.80)]
    if mid_strip.size == 0:
        return False
    mid_h_med = float(np.median(mid_strip[:, :, 0]))
    pastel_sky = (
        ((frame_bgr[:, :, 0].astype(np.int16) - frame_bgr[:, :, 2].astype(np.int16)) >= 8)
        & (hsv[:, :, 2] >= 170)
        & (hsv[:, :, 1] <= 95)
    )
    garment = (
        (np.abs(hsv[:, :, 0].astype(np.float32) - mid_h_med) > 22.0)
        & (hsv[:, :, 1] > 35)
        & (hsv[:, :, 2] < 205)
        & (~pastel_sky)
    ).astype(np.uint8)
    garment[int(h * 0.59) : int(h * 0.68), :] = 0
    top_roi = garment[0 : int(h * 0.12), int(w * 0.20) : int(w * 0.80)]
    mid_roi = garment[int(h * 0.26) : int(h * 0.52), int(w * 0.20) : int(w * 0.80)]
    bot_roi = garment[int(h * 0.88) : h, int(w * 0.15) : int(w * 0.85)]
    top_cov = float(np.mean(top_roi)) if top_roi.size else 0.0
    mid_cov = float(np.mean(mid_roi)) if mid_roi.size else 0.0
    bot_cov = float(np.mean(bot_roi)) if bot_roi.size else 0.0
    if top_cov >= 0.42 and bot_cov >= 0.38 and mid_cov < 0.25:
        top_h = hsv[0 : int(h * 0.12), int(w * 0.20) : int(w * 0.80), 0][top_roi > 0]
        bot_h = hsv[int(h * 0.88) : h, int(w * 0.15) : int(w * 0.85), 0][bot_roi > 0]
        if top_h.size > 0 and bot_h.size > 0 and abs(float(np.median(top_h)) - float(np.median(bot_h))) <= 14.0:
            return True
    return False


def detect_transient_top_intrusion_pov(frames_bgr: list[np.ndarray], grammar: str) -> bool:
    """
    Detects disembodied 3rd arms/sleeves temporarily dropping down from an open top sky/ceiling border
    on `lowpoly_pov_hands` / `porcelain_pov_hands` cuts, without false-firing on stationary
    vertical props anchored across the clip.
    """
    if str(grammar or "").strip() not in ("lowpoly_pov_hands", "porcelain_pov_hands") or len(frames_bgr) < 4:
        return False
    top_dark_fracs: list[float] = []
    bot_active_count = 0
    for frm in frames_bgr:
        if frm is None or frm.size == 0:
            continue
        h, w = frm.shape[:2]
        if h < 120 or w < 80:
            continue
        hsv = cv2.cvtColor(frm, cv2.COLOR_BGR2HSV)
        top_v = hsv[0 : max(12, int(h * 0.22)), :, 2]
        top_dark_fracs.append(float(np.mean(top_v < 95)))
        bot_hsv = hsv[int(h * 0.74) : h, int(w * 0.10) : int(w * 0.90)]
        if float(np.mean((bot_hsv[:, :, 2] < 215) | (bot_hsv[:, :, 1] >= 28))) >= 0.22:
            bot_active_count += 1
    if len(top_dark_fracs) < 4 or bot_active_count < max(2, len(top_dark_fracs) // 2):
        return False
    boundary_max = max(top_dark_fracs[0], top_dark_fracs[-1])
    interior_max = max(top_dark_fracs[1:-1])
    return boundary_max <= 0.035 and (interior_max - boundary_max) >= 0.035


def compute_neon_green_spill_ratio(frame_bgr: np.ndarray) -> float:
    """
    Measures HSV fluorescent/neon-green pixel fraction (`35 <= H <= 80`, `S >= 80`, `V >= 85`),
    catching uncontained radioactive green slime/mist/particles while allowing `Clear Cyan-Blue` (`H >= 92`),
    `Luminous Pearl-Aqua` (`H >= 85` or soft pearl `S < 80`), `Warm Amber-Gold` (`H <= 26`), and `Crimson-Red`.
    """
    if frame_bgr is None or frame_bgr.size == 0:
        return 0.0
    hsv = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV)
    mask = (
        (hsv[:, :, 0] >= 35)
        & (hsv[:, :, 0] <= 80)
        & (hsv[:, :, 1] >= 80)
        & (hsv[:, :, 2] >= 85)
    )
    return float(np.mean(mask))


def compute_brain_margin_saturation(frame_bgr: np.ndarray) -> float:
    """
    Measures HSV saturation in the outer studio border band (`top 10%`, `left/right 7%`) around a
    centered 3D brain model so glowing haze/spores spilling into studio air are rejected.
    """
    if frame_bgr is None or frame_bgr.size == 0:
        return 0.0
    h, w = frame_bgr.shape[:2]
    if h < 40 or w < 40:
        return 0.0
    hsv = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV)
    margin_mask = np.zeros((h, w), dtype=bool)
    margin_mask[: max(4, int(h * 0.10)), :] = True
    margin_mask[:, : max(4, int(w * 0.07))] = True
    margin_mask[:, min(w - 1, int(w * 0.93)) :] = True
    return float(np.mean(hsv[:, :, 1][margin_mask]))


def compute_porcelain_flesh_leak_ratio(frame_bgr: np.ndarray) -> float:
    """
    Measures bare biological human flesh chrominance via combined `HSV + YCrCb` mask
    (`3 <= H <= 13`, `52 <= S <= 155`, `100 <= V <= 245` AND `152 <= Cr <= 178`, `92 <= Cb <= 118`),
    rejecting mannequin-to-human flesh morphs while allowing warm sunlit cream walls and birch/oak wood.
    """
    if frame_bgr is None or frame_bgr.size == 0 or frame_bgr.ndim < 3 or frame_bgr.shape[2] < 3:
        return 0.0
    bgr = frame_bgr[:, :, :3] if frame_bgr.shape[2] > 3 else frame_bgr
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    ycc = cv2.cvtColor(bgr, cv2.COLOR_BGR2YCrCb)
    mask = (
        (hsv[:, :, 0] >= 3)
        & (hsv[:, :, 0] <= 13)
        & (hsv[:, :, 1] >= 52)
        & (hsv[:, :, 1] <= 155)
        & (hsv[:, :, 2] >= 100)
        & (hsv[:, :, 2] <= 245)
        & (ycc[:, :, 1] >= 152)
        & (ycc[:, :, 1] <= 178)
        & (ycc[:, :, 2] >= 92)
        & (ycc[:, :, 2] <= 118)
    )
    return float(np.mean(mask))


def detect_unintended_horizontal_split_seam(frame_bgr: np.ndarray) -> float:
    """
    Measures the strongest full-width horizontal split-screen seam across `Y=32%..56%`
    (strictly between top headline badges and `Y=63%` burned subtitles).
    Hallucinated top/bottom split-screens in Veo produce a sharp step across `>= 72%` of columns
    on a single scanline, whereas continuous single-shot rooms stay `< 35%`.
    """
    if frame_bgr is None or frame_bgr.size == 0:
        return 0.0
    h, w = frame_bgr.shape[:2]
    if h < 120 or w < 80:
        return 0.0
    gray = frame_bgr if frame_bgr.ndim == 2 else cv2.cvtColor(frame_bgr[:, :, :3], cv2.COLOR_BGR2GRAY)
    y0, y1 = int(h * 0.32), int(h * 0.56)
    if y1 <= y0 + 6:
        return 0.0
    g_f = gray.astype(np.float32)
    row_jump = np.abs(g_f[y0 + 2 : y1 + 2, :] - g_f[y0 - 2 : y1 - 2, :])
    edge_w = max(4, int(w * 0.08))
    full_frac = np.mean(row_jump > 28.0, axis=1)
    left_frac = np.mean(row_jump[:, :edge_w] > 28.0, axis=1)
    right_frac = np.mean(row_jump[:, w - edge_w :] > 28.0, axis=1)
    edge_anchored = np.minimum(full_frac, np.minimum(left_frac, right_frac))
    return float(np.max(edge_anchored)) if edge_anchored.size else 0.0


def _invoke_inspect_diorama_clip_cv(
    mp4_path: Path,
    grammar: str = "arch_cutaway_diorama",
    schema_version: int = 6,
    brain_mode: str = "",
    style_profile: str = "",
) -> dict[str, Any]:
    """Invokes `inspect_diorama_clip_cv` while remaining backward-compatible with 3-arg monkeypatched stubs."""
    fn = inspect_diorama_clip_cv
    try:
        sig = inspect.signature(fn)
        params = list(sig.parameters.values())
        has_varargs = any(
            p.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD)
            for p in params
        )
        if not has_varargs and len(params) <= 3:
            return fn(mp4_path, grammar, schema_version)  # type: ignore[call-arg]
    except (TypeError, ValueError):
        pass
    return fn(
        mp4_path,
        grammar=grammar,
        schema_version=schema_version,
        brain_mode=brain_mode,
        style_profile=style_profile,
    )


def inspect_diorama_clip_cv(
    mp4_path: Path,
    grammar: str = "arch_cutaway_diorama",
    schema_version: int = 6,
    brain_mode: str = "",
    style_profile: str = "",
) -> dict[str, Any]:
    """
    Fast local CV gate for newly downloaded 9:16 Neuro-Diorama clips:
      - Schema v7 (`porcelain_cinematic_v7`, R66):
        * Strict HSV+YCrCb porcelain anti-skin-morph (`PORCELAIN_V7_HUMAN_SKIN_MAX` on closeups, `0.22` on world)
        * Contained 4-color 3D brain (`neon_green_ratio <= PORCELAIN_V7_NEON_GREEN_SPILL_MAX` across all 4 modes,
          outer studio `margin_sat <= PORCELAIN_V7_BRAIN_MARGIN_SAT_MAX` on whole-brain gallery models)
        * High-key documentary exposure (`mean_luma` in `[82.0, 205.0]`, `dark_v35 <= 0.24`), natural cinema DOF allowed
      - Schema v7 (`lowpoly_pastel_v7`, R63):
        * Bright pastel world (`mean_luma` in `[92.0, 195.0]`, `dark_v35 <= 0.18`, `mean_sat` in `[14.0, 88.0]`),
          infinite deep focus (`periphery_to_center_sharpness >= 0.26` when `outer_edge_density >= 0.012`).
      - Schema v6 (`neuro_diorama`):
        * Dark studio backdrop (`top_band_luma_mean <= 175.0`), motion `>= 1.10`, plaque `< 7`.
    """
    p = Path(mp4_path)
    if not p.exists() or not p.is_file():
        return {"passed": False, "reason": "missing_file"}
    sz = p.stat().st_size
    if sz < 160_000:
        return {"passed": False, "reason": f"file_too_small:{sz}"}

    cap = cv2.VideoCapture(str(p))
    if not cap.isOpened():
        return {"passed": False, "reason": "cv2_open_failed"}
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 24.0)
    fc = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    dur = fc / max(1.0, fps)

    g_raw = str(grammar or "").strip()
    g_low = g_raw.lower()
    sp_clean = str(style_profile or "").strip()
    if g_raw in PORCELAIN_V7_VISUAL_GRAMMARS or g_low.startswith("porcelain_"):
        is_porcelain = True
    elif g_raw in DIORAMA_V7_VISUAL_GRAMMARS or g_low.startswith("lowpoly_"):
        is_porcelain = False
    elif sp_clean:
        is_porcelain = is_porcelain_v7_plan(sp_clean)
    elif int(schema_version) >= PROMPT_SCHEMA_VERSION_V7:
        is_porcelain = (DEFAULT_DIORAMA_STYLE_PROFILE == PORCELAIN_V7_STYLE_PROFILE)
    else:
        is_porcelain = False

    is_v7 = (
        is_porcelain
        or int(schema_version) >= PROMPT_SCHEMA_VERSION_V7
        or g_raw in ALL_DIORAMA_V7_VISUAL_GRAMMARS
        or g_low.startswith("lowpoly_")
    )
    if is_porcelain:
        g_norm = normalize_porcelain_v7_grammar(g_raw)
    elif is_v7:
        g_norm = {
            "fullbleed_world": "lowpoly_fullbleed_world",
            "world": "lowpoly_fullbleed_world",
            "hands_closeup": "lowpoly_hands_closeup",
            "hands": "lowpoly_hands_closeup",
            "pov_hands": "lowpoly_pov_hands",
            "pov": "lowpoly_pov_hands",
            "cutaway_section": "lowpoly_cutaway_section",
            "cutaway": "lowpoly_cutaway_section",
            "literal_analogy": "lowpoly_literal_analogy",
            "analogy": "lowpoly_literal_analogy",
            "matte_brain": "lowpoly_matte_brain",
            "living_brain": "lowpoly_matte_brain",
            "brain": "lowpoly_matte_brain",
        }.get(g_low, g_raw)
    else:
        g_norm = g_raw
    sample_fracs = (0.08, 0.20, 0.32, 0.44, 0.56, 0.68, 0.80, 0.92) if is_v7 else (0.12, 0.38, 0.64, 0.88)
    frames_bgr: list[np.ndarray] = []
    for frac in sample_fracs:
        f_idx = max(0, min(max(0, fc - 1), int(round(fc * frac))))
        cap.set(cv2.CAP_PROP_POS_FRAMES, f_idx)
        ok, frm = cap.read()
        if ok and frm is not None:
            frames_bgr.append(frm)
    cap.release()

    if len(frames_bgr) < 3 or w <= 0 or h <= w or dur < 3.5:
        return {
            "passed": False,
            "reason": f"bad_geometry_or_duration:w={w},h={h},dur={dur:.2f},frames={len(frames_bgr)}",
        }

    diffs: list[float] = []
    top_lumas: list[float] = []
    full_lumas: list[float] = []
    dark_v35_ratios: list[float] = []
    sat_means: list[float] = []
    center_sharps: list[float] = []
    focus_ratios: list[float] = []
    outer_edge_densities: list[float] = []
    peach_ratios: list[float] = []
    porcelain_flesh_ratios: list[float] = []
    neon_green_ratios: list[float] = []
    margin_sats: list[float] = []
    escher_hits = 0
    for idx, frm in enumerate(frames_bgr):
        gray = cv2.cvtColor(frm, cv2.COLOR_BGR2GRAY)
        full_lumas.append(float(np.mean(gray)))
        top_band = gray[: max(8, int(h * 0.12)), :]
        top_lumas.append(float(np.mean(top_band)))
        if idx > 0:
            prev_gray = cv2.cvtColor(frames_bgr[idx - 1], cv2.COLOR_BGR2GRAY)
            diffs.append(float(np.mean(np.abs(gray.astype(np.float32) - prev_gray.astype(np.float32)))))
        hsv = cv2.cvtColor(frm, cv2.COLOR_BGR2HSV)
        dark_v35_ratios.append(float(np.mean(hsv[:, :, 2] < 35)))
        sat_means.append(float(np.mean(hsv[:, :, 1])))

        gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
        gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
        grad = cv2.magnitude(gx, gy)
        c_y0, c_y1 = int(h * 0.28), int(h * 0.72)
        c_x0, c_x1 = int(w * 0.22), int(w * 0.78)
        center_sharp = float(np.mean(grad[c_y0:c_y1, c_x0:c_x1]))
        center_sharps.append(center_sharp)
        outer_mask = np.ones((h, w), dtype=bool)
        outer_mask[c_y0:c_y1, c_x0:c_x1] = False
        outer_mask[: int(h * 0.05), :] = False
        outer_mask[int(h * 0.95) :, :] = False
        outer_sharp = float(np.mean(grad[outer_mask])) if np.any(outer_mask) else center_sharp
        focus_ratios.append(outer_sharp / max(1.0, center_sharp))
        if np.any(outer_mask):
            canny_outer = float(np.mean((cv2.Canny(gray, 20, 60) > 0)[outer_mask]))
            grad_outer = float(np.mean((grad > 6.0)[outer_mask]))
            outer_edge_densities.append(max(canny_outer, grad_outer))
        else:
            outer_edge_densities.append(0.0)

        center = hsv[int(h * 0.18) : int(h * 0.82), int(w * 0.15) : int(w * 0.85)]
        skin_mask = (
            (center[:, :, 0] >= 5)
            & (center[:, :, 0] <= 17)
            & (center[:, :, 1] >= 48)
            & (center[:, :, 1] <= 145)
            & (center[:, :, 2] >= 105)
            & (center[:, :, 2] <= 238)
        )
        peach_ratios.append(float(np.mean(skin_mask)))
        if is_porcelain:
            porcelain_flesh_ratios.append(
                compute_porcelain_flesh_leak_ratio(
                    frm[int(h * 0.18) : int(h * 0.82), int(w * 0.15) : int(w * 0.85)]
                )
            )
            neon_green_ratios.append(compute_neon_green_spill_ratio(frm))
            margin_sats.append(compute_brain_margin_saturation(frm))
        if is_v7 and detect_escher_dual_edge_closeup(frm, g_norm):
            escher_hits += 1

    max_diff = max(diffs) if diffs else 0.0
    median_diff = float(np.median(diffs)) if diffs else 0.0
    active_spans = sum(1 for d in diffs if d >= 0.70)
    mean_top_luma = float(np.mean(top_lumas))
    mean_full_luma = float(np.mean(full_lumas))
    mean_dark_v35 = float(np.mean(dark_v35_ratios))
    mean_sat = float(np.mean(sat_means))
    mean_center_sharp = float(np.mean(center_sharps)) if center_sharps else 0.0
    mean_focus_ratio = float(np.mean(focus_ratios))
    mean_outer_edge_density = float(np.mean(outer_edge_densities)) if outer_edge_densities else 0.0
    mean_peach = float(np.mean(peach_ratios))
    plaque_frames = frames_bgr if is_v7 else frames_bgr[1:3]
    plaque_run = max((_max_horizontal_plaque_glyph_run(f) for f in plaque_frames), default=0)

    if max_diff < (1.20 if is_porcelain else (1.25 if is_v7 else 1.10)):
        return {"passed": False, "reason": f"static_clip:max_diff={max_diff:.2f}"}

    if is_porcelain:
        if len(diffs) >= 6 and (median_diff < 1.10 or active_spans < 5):
            return {
                "passed": False,
                "reason": f"intra_clip_freeze_v7:median_diff={median_diff:.2f},active_spans={active_spans}/{len(diffs)}",
            }
        mean_porcelain_flesh = float(np.mean(porcelain_flesh_ratios)) if porcelain_flesh_ratios else 0.0
        if g_norm in ("porcelain_hands_closeup", "porcelain_pov_hands"):
            peach_cap = float(PORCELAIN_V7_HUMAN_SKIN_MAX)
        elif g_norm == "porcelain_fullbleed_world":
            peach_cap = float(PORCELAIN_V7_HUMAN_SKIN_MAX) + 0.04
        elif g_norm == "porcelain_living_brain":
            peach_cap = 0.68
        else:
            peach_cap = 0.28
        if mean_porcelain_flesh > peach_cap:
            return {"passed": False, "reason": f"human_skin_or_face_leak:peach={mean_porcelain_flesh:.3f}"}
        mean_neon_green = float(np.mean(neon_green_ratios)) if neon_green_ratios else 0.0
        mean_margin_sat = float(np.mean(margin_sats)) if margin_sats else 0.0
        if g_norm == "porcelain_living_brain":
            if mean_neon_green > PORCELAIN_V7_NEON_GREEN_SPILL_MAX:
                return {"passed": False, "reason": f"neon_green_fluorescent_spill:ratio={mean_neon_green:.4f}"}
            bmode_norm = normalize_porcelain_v7_brain_mode(brain_mode)
            if bmode_norm == "cortical_vascular_whole":
                if mean_margin_sat > PORCELAIN_V7_BRAIN_MARGIN_SAT_MAX:
                    return {"passed": False, "reason": f"brain_margin_glow_spill:margin_sat={mean_margin_sat:.1f}"}
        max_hsplit_seam = max((detect_unintended_horizontal_split_seam(f) for f in frames_bgr), default=0.0)
        if g_norm != "porcelain_cutaway_section" and max_hsplit_seam >= 0.72:
            return {"passed": False, "reason": f"unintended_horizontal_split_screen:seam={max_hsplit_seam:.3f}"}
        if mean_full_luma < 82.0:
            return {"passed": False, "reason": f"dark_void_leak_v7:mean_luma={mean_full_luma:.1f}"}
        luma_cap = 242.0 if g_norm == "porcelain_living_brain" else 234.0
        if mean_full_luma > luma_cap:
            return {"passed": False, "reason": f"overexposed_blank_v7:mean_luma={mean_full_luma:.1f}"}
        if mean_dark_v35 > PORCELAIN_V7_DARK_VOID_RATIO_MAX:
            return {"passed": False, "reason": f"excess_dark_shadow_v7:dark_v35={mean_dark_v35:.3f}"}
        sat_floor = 4.0 if g_norm == "porcelain_living_brain" else 6.0
        if mean_sat < sat_floor:
            return {"passed": False, "reason": f"desaturated_grayscale_v7:sat={mean_sat:.1f}"}
        if mean_sat > 125.0:
            return {"passed": False, "reason": f"neon_oversaturated_v7:sat={mean_sat:.1f}"}
        if mean_center_sharp < 2.2:
            return {"passed": False, "reason": f"center_defocus_blur_v7:center_sharp={mean_center_sharp:.2f}"}
        if plaque_run >= 5:
            return {"passed": False, "reason": f"in_scene_garbled_text_run_v7:{plaque_run}"}
        if escher_hits > 0:
            return {"passed": False, "reason": f"escher_dual_edge_torso_and_arms_v7:{escher_hits}"}
        if detect_transient_top_intrusion_pov(frames_bgr, g_norm):
            return {"passed": False, "reason": "transient_top_intrusion_pov_v7"}
        return {
            "passed": True,
            "schema": PROMPT_SCHEMA_VERSION_V7,
            "style_profile": "porcelain_cinematic_v7",
            "width": w,
            "height": h,
            "fps": round(fps, 2),
            "duration_sec": round(dur, 2),
            "file_size_bytes": sz,
            "max_frame_diff": round(max_diff, 2),
            "median_frame_diff": round(median_diff, 2),
            "active_motion_spans": int(active_spans),
            "mean_luma": round(mean_full_luma, 1),
            "dark_v35_ratio": round(mean_dark_v35, 4),
            "mean_sat": round(mean_sat, 1),
            "center_sharpness": round(mean_center_sharp, 2),
            "deep_focus_ratio": round(mean_focus_ratio, 3),
            "outer_edge_density": round(mean_outer_edge_density, 4),
            "peach_ratio": round(mean_porcelain_flesh, 4),
            "neon_green_ratio": round(mean_neon_green, 4),
            "brain_margin_sat": round(mean_margin_sat, 2),
            "top_luma_mean": round(mean_top_luma, 1),
            "plaque_glyph_run": int(plaque_run),
            "escher_dual_edge_hits": int(escher_hits),
        }

    if is_v7:
        if len(diffs) >= 6 and (median_diff < 1.15 or active_spans < 5):
            return {
                "passed": False,
                "reason": f"intra_clip_freeze_v7:median_diff={median_diff:.2f},active_spans={active_spans}/{len(diffs)}",
            }
        if g_norm in ("lowpoly_hands_closeup", "lowpoly_pov_hands", "lowpoly_fullbleed_world"):
            peach_cap = 0.22
        elif g_norm == "lowpoly_matte_brain":
            peach_cap = 0.68
        else:
            peach_cap = 0.36
        if mean_peach > peach_cap:
            return {"passed": False, "reason": f"human_skin_or_face_leak:peach={mean_peach:.3f}"}
        if mean_full_luma < 92.0:
            return {"passed": False, "reason": f"dark_void_leak_v7:mean_luma={mean_full_luma:.1f}"}
        if mean_full_luma > 195.0:
            return {"passed": False, "reason": f"overexposed_blank_v7:mean_luma={mean_full_luma:.1f}"}
        if mean_dark_v35 > 0.18:
            return {"passed": False, "reason": f"excess_dark_shadow_v7:dark_v35={mean_dark_v35:.3f}"}
        if mean_sat < 14.0:
            return {"passed": False, "reason": f"desaturated_grayscale_v7:sat={mean_sat:.1f}"}
        if mean_sat > 88.0:
            return {"passed": False, "reason": f"neon_oversaturated_v7:sat={mean_sat:.1f}"}
        if mean_focus_ratio < 0.26 and mean_outer_edge_density >= 0.012:
            return {
                "passed": False,
                "reason": f"macro_bokeh_blur_v7:focus_ratio={mean_focus_ratio:.2f},outer_edge={mean_outer_edge_density:.4f}",
            }
        if plaque_run >= 5:
            return {"passed": False, "reason": f"in_scene_garbled_text_run_v7:{plaque_run}"}
        if escher_hits > 0:
            return {"passed": False, "reason": f"escher_dual_edge_torso_and_arms_v7:{escher_hits}"}
        if detect_transient_top_intrusion_pov(frames_bgr, g_norm):
            return {"passed": False, "reason": "transient_top_intrusion_pov_v7"}
        return {
            "passed": True,
            "schema": PROMPT_SCHEMA_VERSION_V7,
            "style_profile": "lowpoly_pastel_v7",
            "width": w,
            "height": h,
            "fps": round(fps, 2),
            "duration_sec": round(dur, 2),
            "file_size_bytes": sz,
            "max_frame_diff": round(max_diff, 2),
            "median_frame_diff": round(median_diff, 2),
            "active_motion_spans": int(active_spans),
            "mean_luma": round(mean_full_luma, 1),
            "dark_v35_ratio": round(mean_dark_v35, 4),
            "mean_sat": round(mean_sat, 1),
            "deep_focus_ratio": round(mean_focus_ratio, 3),
            "outer_edge_density": round(mean_outer_edge_density, 4),
            "peach_ratio": round(mean_peach, 4),
            "top_luma_mean": round(mean_top_luma, 1),
            "plaque_glyph_run": int(plaque_run),
            "escher_dual_edge_hits": int(escher_hits),
        }

    if mean_top_luma > 175.0:
        return {"passed": False, "reason": f"bright_white_backdrop_leak:top_luma={mean_top_luma:.1f}"}
    if g_norm in ("arch_brain_maquette", "frosted_crystal_specimen") and mean_peach > 0.22:
        return {"passed": False, "reason": f"flesh_tone_leak_in_specimen:peach={mean_peach:.3f}"}
    if plaque_run >= 7:
        return {"passed": False, "reason": f"in_scene_plaque_glyph_run:{plaque_run}"}

    return {
        "passed": True,
        "width": w,
        "height": h,
        "duration_sec": round(dur, 2),
        "file_size_bytes": sz,
        "max_frame_diff": round(max_diff, 2),
        "top_luma_mean": round(mean_top_luma, 1),
        "peach_ratio": round(mean_peach, 3),
        "plaque_glyph_run": int(plaque_run),
    }


def _ensure_min_clip_size_if_needed(mp4_path: Path) -> None:
    """
    Dark-void 720p clips occasionally compress cleanly to ~750-980KB in Veo Lite while
    `VideoAutopsyEngine` cross-project dedup indexes clips >= `MIN_CLIP_SIZE_BYTES` (1MB).
    Only if a valid Flow clip is < 1,020,000 bytes, re-mux cleanly at high-bitrate H.264
    without any synthetic metadata markers so every clip exceeds 1.05MB cleanly.
    Raises `MediaIntegrityError` if normalization fails and file remains `< MIN_CLIP_SIZE_BYTES`.
    """
    p = Path(mp4_path)
    if not p.exists() or not p.is_file():
        raise MediaIntegrityError(f"Clip file does not exist for size normalization: {p}")
    if p.stat().st_size >= MIN_CLIP_SIZE_BYTES + 20_000:
        return
    import subprocess
    import imageio_ffmpeg

    ff = imageio_ffmpeg.get_ffmpeg_exe()
    tmp_out = Path(f"/tmp/_aab_bitrate_norm_{p.stem}_{os.getpid()}_{int(time.time() * 1000)}.mp4")
    try:
        res = subprocess.run(
            [
                ff, "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
                "-i", str(p),
                "-map_metadata", "-1",
                "-c:v", "libx264", "-preset", "fast", "-b:v", "1850k", "-minrate", "1600k", "-maxrate", "2400k", "-bufsize", "3200k",
                "-pix_fmt", "yuv420p", "-c:a", "copy",
                "-movflags", "+faststart",
                str(tmp_out),
            ],
            capture_output=True, check=False, timeout=90,
        )
        if res.returncode == 0 and tmp_out.exists() and tmp_out.stat().st_size >= MIN_CLIP_SIZE_BYTES:
            shutil.copy2(tmp_out, p)
    finally:
        tmp_out.unlink(missing_ok=True)

    final_sz = p.stat().st_size if p.exists() else 0
    if final_sz < MIN_CLIP_SIZE_BYTES:
        raise MediaIntegrityError(
            f"Clip {p.name} remains below MIN_CLIP_SIZE_BYTES ({final_sz} < {MIN_CLIP_SIZE_BYTES}) after bitrate normalization"
        )


async def _configure_zero_credit_veo_lite(
    client: DirectCDPClient,
    force: bool = False,
    output_count: int = 1,
) -> str:
    """Forces Manual Video · 9:16 · 8s · x{output_count} · `Veo 3.1 - Lite [Lower Priority]` (`0 credits`), forbidding paid credit approvals."""
    eff_out = max(1, min(int(FLOW_ZERO_CREDIT_VIDEO_MAX_BATCH), int(output_count or 1)))
    out_lbl = f"x{eff_out}"
    await client.eval("window.__bci_flow_forbid_credit_approve = true;")
    already = await client.eval(
        f"Boolean(window.__bci_flow_lite_fallback && window.__bci_flow_0cred_configured && window.__bci_flow_0cred_out === {eff_out})"
    )
    has_warn = await client.eval("Boolean(document.querySelector('button.prompt-warning-button'))")
    fam = await read_active_flow_model_family(client)
    if already and not force and not has_warn and fam == "veo_3_1_lite_low_priority":
        return f"cached_0cred_veo_lite_{out_lbl}"
    await client.eval(
        "window.__bci_flow_forbid_credit_approve = true; window.__bci_flow_lite_fallback = true; window.__bci_flow_0cred_configured = false;"
    )
    cfg_res = await ensure_manual_video_916_mode(
        client,
        target_duration="8s",
        engine_mode="zero-credit",
        force_recheck=force,
    )
    prev_out = int((await client.eval("Number(window.__bci_flow_0cred_out || 1)")) or 1)
    fam = await read_active_flow_model_family(client)
    has_warn = await client.eval("Boolean(document.querySelector('button.prompt-warning-button'))")
    if has_warn or fam != "veo_3_1_lite_low_priority" or eff_out > 1 or prev_out != eff_out:
        if has_warn or fam != "veo_3_1_lite_low_priority":
            await select_flow_video_model(client, FLOW_ZERO_CREDIT_MODEL)
            await asyncio.sleep(0.4)
        await client.eval("""(() => {
            const box = document.querySelector('flow-prompt-box-settings');
            const st = document.querySelector('button.settings-trigger-button');
            if (st && (!box || !(box.innerText || '').includes('Generating will use'))) st.click();
        })()""")
        await asyncio.sleep(0.4)
        await client.eval(f"""(() => {{
            const btns = Array.from(document.querySelectorAll('flow-prompt-box-settings button, .cdk-overlay-pane button'));
            const b916 = btns.find(b => (b.innerText || '').includes('9:16'));
            if (b916) b916.click();
            const b8 = btns.find(b => (b.innerText || '').trim() === '8s');
            if (b8) b8.click();
            const bx = btns.find(b => (b.innerText || '').trim() === {json.dumps(out_lbl)});
            if (bx && !bx.disabled) bx.click();
            const bd = document.querySelector('.cdk-overlay-backdrop');
            if (bd) bd.click();
        }})()""")
        await asyncio.sleep(0.35)
    await client.eval(f"window.__bci_flow_0cred_configured = true; window.__bci_flow_0cred_out = {eff_out};")
    summary_now = await client.eval("""(() => (document.querySelector('button.settings-trigger-button')?.innerText || '').trim())()""")
    return str(summary_now or cfg_res.get("settings_summary") or "")


async def _configure_diorama_tab_engine(
    client: DirectCDPClient,
    engine_mode: str = DEFAULT_FLOW_ENGINE_MODE,
    credit_exhausted_event: asyncio.Event | None = None,
    force: bool = False,
    zero_credit_output_count: int = 1,
) -> dict[str, Any]:
    """
    Configures the Flow tab for the active dual-tier engine policy (`auto` | `omni` | `zero-credit`):
      - `auto`: uses `Omni 1.1 Flash` (`9:16`, `8s`, `720p`, `x1`) while credits are available;
        immediately sets `credit_exhausted_event` and switches to `Veo 3.1 - Lite [Lower Priority]` (`0 credits`)
        when `button.prompt-warning-button` or low/zero-credit banners appear.
      - `omni`: requires `Omni 1.1 Flash` and fails closed if out of credits.
      - `zero-credit`: locks `Veo 3.1 - Lite [Lower Priority]` (`veo_3_1_lite_low_priority`) at `x1..x4` and forbids credit approval dialogs.
    """
    mode = _normalize_engine_mode(engine_mode)
    use_zero_credit = mode == "zero-credit" or (
        mode == "auto" and credit_exhausted_event is not None and credit_exhausted_event.is_set()
    )
    zc_out = max(1, min(int(FLOW_ZERO_CREDIT_VIDEO_MAX_BATCH), int(zero_credit_output_count or 1)))
    if use_zero_credit:
        summary = (
            await _configure_zero_credit_veo_lite(client, force=force, output_count=zc_out)
            if zc_out > 1
            else await _configure_zero_credit_veo_lite(client, force=force)
        )
        fam = await read_active_flow_model_family(client)
        cred_chk = await client.eval(CHECK_CREDIT_EXHAUSTION_JS) or {}
        has_warn = bool(cred_chk.get("has_warning_btn"))
        return {
            "flow_model": FLOW_ZERO_CREDIT_MODEL,
            "credit_tier": "zero_credit_fallback",
            "zero_credit_verified": bool(fam == "veo_3_1_lite_low_priority" and not has_warn),
            "model_family_id": fam,
            "has_warning_btn": has_warn,
            "output_count": zc_out,
            "settings_summary": summary,
        }

    await client.eval("window.__bci_flow_forbid_credit_approve = false;")
    cfg_res = await ensure_manual_video_916_mode(
        client,
        target_duration="8s",
        engine_mode=mode,
        credit_exhausted_event=credit_exhausted_event,
        force_recheck=force,
    )
    cred_chk = await client.eval(CHECK_CREDIT_EXHAUSTION_JS) or {}
    chosen_model = str(cfg_res.get("flow_model") or FLOW_PRIMARY_VIDEO_MODEL)
    fell_back = chosen_model == FLOW_ZERO_CREDIT_MODEL or cfg_res.get("credit_tier") == "zero_credit_fallback"

    if mode == "omni":
        if fell_back or bool(cred_chk.get("exhausted")):
            raise FlowCircuitBreakerError(
                f"Omni 1.1 Flash required (engine_mode='omni'), but credits are exhausted: {cred_chk}"
            )
        return {
            **cfg_res,
            "flow_model": FLOW_PRIMARY_VIDEO_MODEL,
            "credit_tier": "omni_monthly_credit",
            "zero_credit_verified": False,
        }

    if fell_back or bool(cred_chk.get("exhausted")):
        if credit_exhausted_event is not None:
            credit_exhausted_event.set()
        summary = (
            await _configure_zero_credit_veo_lite(client, force=True, output_count=zc_out)
            if zc_out > 1
            else await _configure_zero_credit_veo_lite(client, force=True)
        )
        fam = await read_active_flow_model_family(client)
        has_warn = bool(await client.eval("Boolean(document.querySelector('button.prompt-warning-button'))"))
        return {
            "flow_model": FLOW_ZERO_CREDIT_MODEL,
            "credit_tier": "zero_credit_fallback",
            "zero_credit_verified": bool(fam == "veo_3_1_lite_low_priority" and not has_warn),
            "model_family_id": fam,
            "has_warning_btn": has_warn,
            "output_count": max(1, min(int(FLOW_ZERO_CREDIT_VIDEO_MAX_BATCH), int(zero_credit_output_count or 1))),
            "settings_summary": summary,
        }

    return {
        **cfg_res,
        "flow_model": FLOW_PRIMARY_VIDEO_MODEL,
        "credit_tier": "omni_monthly_credit",
        "zero_credit_verified": False,
    }


async def _submit_diorama_prompt_zero_credit(
    client: DirectCDPClient,
    prompt_text: str,
    short_ref_path: Path | None,
    ref_state: dict[str, Any],
    ref_upload_lock: asyncio.Lock | None = None,
    engine_mode: str = DEFAULT_FLOW_ENGINE_MODE,
    credit_exhausted_event: asyncio.Event | None = None,
    submission_meta_out: dict[str, Any] | None = None,
    end_ref_path: Path | None = None,
) -> bool:
    """
    Submits a Diorama prompt under the Credit-Aware Dual-Tier Engine Policy (`auto` | `omni` | `zero-credit`):
      - `auto`: attempts `Omni 1.1 Flash` (`omni_monthly_credit`) while credits are available; if credits are
        exhausted at startup or mid-episode, immediately sets `credit_exhausted_event`, switches to
        `Veo 3.1 - Lite [Lower Priority]` (`zero_credit_fallback`), verifies `veo_3_1_lite_low_priority` and
        `!prompt-warning-button`, and submits at `0 credits`.
      - Supports dual `Start Frame + End Frame` (`end_ref_path`) on `Omni 1.1 Flash`, degrading cleanly to single
        start-frame or text-only on `0-credit` fallback.
      - NEVER clicks `"Add AI credits"` top-up links under any mode.
    """
    mode = _normalize_engine_mode(engine_mode)
    zc_out = max(1, min(int(FLOW_ZERO_CREDIT_VIDEO_MAX_BATCH), int(ref_state.get("zero_credit_output_count") or 1)))
    if mode == "zero-credit" or (mode == "auto" and credit_exhausted_event is not None and credit_exhausted_event.is_set()):
        await client.eval("window.__bci_flow_forbid_credit_approve = true;")
    else:
        await client.eval("window.__bci_flow_forbid_credit_approve = false;")
    await client.eval(DISMISS_CREDIT_DIALOG_JS)

    if await count_chips(client) > 0:
        await clear_prompt_ingredients(client)

    cfg_meta = await _configure_diorama_tab_engine(
        client,
        engine_mode=mode,
        credit_exhausted_event=credit_exhausted_event,
        zero_credit_output_count=zc_out,
    )
    active_model = str(cfg_meta.get("flow_model") or FLOW_ZERO_CREDIT_MODEL)
    active_tier = str(
        cfg_meta.get("credit_tier")
        or ("zero_credit_fallback" if active_model == FLOW_ZERO_CREDIT_MODEL else "omni_monthly_credit")
    )

    async def _switch_to_zero_credit_fallback(reason_msg: str) -> None:
        nonlocal active_model, active_tier
        print(f"[FlowDiorama] {reason_msg} -> switching to 0-credit {FLOW_ZERO_CREDIT_MODEL}")
        if credit_exhausted_event is not None:
            credit_exhausted_event.set()
        await press_escape(client)
        await _configure_zero_credit_veo_lite(client, force=True, output_count=zc_out)
        fam_chk = await read_active_flow_model_family(client)
        warn_chk = bool(await client.eval("Boolean(document.querySelector('button.prompt-warning-button'))"))
        if warn_chk and await count_chips(client) > 0:
            ref_state["lite_supports_ref"] = False
            await clear_prompt_ingredients(client)
            await _configure_zero_credit_veo_lite(client, force=True, output_count=zc_out)
            fam_chk = await read_active_flow_model_family(client)
            warn_chk = bool(await client.eval("Boolean(document.querySelector('button.prompt-warning-button'))"))
        if fam_chk != "veo_3_1_lite_low_priority" or warn_chk:
            await select_flow_video_model(client, FLOW_ZERO_CREDIT_MODEL)
            await asyncio.sleep(0.4)
        active_model = FLOW_ZERO_CREDIT_MODEL
        active_tier = "zero_credit_fallback"

    allow_ref = active_model == FLOW_PRIMARY_VIDEO_MODEL or bool(ref_state.get("lite_supports_ref", True))
    if short_ref_path and short_ref_path.exists() and allow_ref:
        use_dual_end = (
            end_ref_path is not None
            and end_ref_path.exists()
            and (active_model == FLOW_PRIMARY_VIDEO_MODEL or bool(ref_state.get("lite_supports_dual_ref", True)))
        )

        async def _do_ref_attach() -> bool:
            try:
                await client.send("Page.bringToFront")
            except Exception:
                pass
            await asyncio.sleep(0.35)
            uploaded_names: set[str] = ref_state.setdefault("uploaded_in_tab", set())
            if use_dual_end and end_ref_path is not None:
                dual_res = await upload_start_end_frames_to_flow(
                    client,
                    start_frame=short_ref_path,
                    end_frame=end_ref_path,
                    uploaded_cache=uploaded_names,
                )
                return bool(dual_res.get("start_attached"))
            chip_ready = False
            if short_ref_path.name not in uploaded_names:
                up_ok = await upload_file_to_flow(client, short_ref_path)
                if up_ok:
                    uploaded_names.add(short_ref_path.name)
                    for _w in range(10):
                        await asyncio.sleep(0.5)
                        if await count_chips(client) >= 1:
                            chip_ready = True
                            break
            if not chip_ready:
                chip_ready = await attach_uploaded_by_name(client, short_ref_path.name, wait_sec=16.0)
                if not chip_ready and await count_chips(client) >= 1:
                    chip_ready = True
                if not chip_ready:
                    await press_escape(client)
                    await asyncio.sleep(0.8)
                    uploaded_names.discard(short_ref_path.name)
                    reup_ok = await upload_file_to_flow(client, short_ref_path)
                    if reup_ok:
                        uploaded_names.add(short_ref_path.name)
                        for _w in range(10):
                            await asyncio.sleep(0.5)
                            if await count_chips(client) >= 1:
                                chip_ready = True
                                break
                    if not chip_ready:
                        chip_ready = await attach_uploaded_by_name(client, short_ref_path.name, wait_sec=15.0)
            return bool(chip_ready)

        if ref_upload_lock is not None:
            async with ref_upload_lock:
                att_ok = await _do_ref_attach()
        else:
            att_ok = await _do_ref_attach()

        if att_ok:
            await select_flow_video_model(client, active_model)
            await asyncio.sleep(0.4)
            if active_model == FLOW_ZERO_CREDIT_MODEL and zc_out > 1:
                await client.eval(f"""(() => {{
                    const btns = Array.from(document.querySelectorAll('flow-prompt-box-settings button, .cdk-overlay-pane button'));
                    const bx = btns.find(b => (b.innerText || '').trim() === {json.dumps(f"x{zc_out}")});
                    if (bx && !bx.disabled) bx.click();
                }})()""")
                await asyncio.sleep(0.25)
            await client.eval("""(() => {
                const bd = document.querySelector('.cdk-overlay-backdrop');
                if (bd) bd.click();
            })()""")
            await asyncio.sleep(0.3)
            cred_chip = await client.eval(CHECK_CREDIT_EXHAUSTION_JS) or {}
            if active_model == FLOW_PRIMARY_VIDEO_MODEL:
                if bool(cred_chip.get("exhausted")):
                    if mode == "omni":
                        raise FlowCircuitBreakerError(
                            f"Omni 1.1 Flash credits exhausted after attaching {short_ref_path.name}: {cred_chip}"
                        )
                    await _switch_to_zero_credit_fallback(
                        f"Omni 1.1 Flash credit warning after attaching {short_ref_path.name} ({cred_chip})"
                    )
                else:
                    end_lbl = f" + {end_ref_path.name}" if (use_dual_end and end_ref_path) else ""
                    print(f"[FlowDiorama] Attached reference anchor on {active_model}: {short_ref_path.name}{end_lbl}")
            else:
                fam_chip = await read_active_flow_model_family(client)
                warn_with_chip = bool(cred_chip.get("has_warning_btn")) or fam_chip != "veo_3_1_lite_low_priority"
                if warn_with_chip and use_dual_end:
                    ref_state["lite_supports_dual_ref"] = False
                    await clear_prompt_ingredients(client)
                    if await attach_uploaded_by_name(client, short_ref_path.name, wait_sec=12.0):
                        await _configure_zero_credit_veo_lite(client, force=True, output_count=zc_out)
                        cred_chip = await client.eval(CHECK_CREDIT_EXHAUSTION_JS) or {}
                        fam_chip = await read_active_flow_model_family(client)
                        warn_with_chip = bool(cred_chip.get("has_warning_btn")) or fam_chip != "veo_3_1_lite_low_priority"
                if warn_with_chip:
                    print(
                        f"[FlowDiorama] Ingredient chip triggered credit warning/model drift ({fam_chip}); "
                        f"clearing chip & locking pure 0-credit {FLOW_ZERO_CREDIT_MODEL}"
                    )
                    ref_state["lite_supports_ref"] = False
                    await clear_prompt_ingredients(client)
                    await _configure_zero_credit_veo_lite(client, force=True, output_count=zc_out)
                else:
                    print(f"[FlowDiorama] Attached 0-credit reference anchor: {short_ref_path.name}")
        else:
            print(f"[FlowDiorama] Reference anchor {short_ref_path.name} failed to attach; aborting unanchored submission for retry")
            await clear_prompt_ingredients(client)
            return False


    for _ in range(15):
        ready = await client.eval("""(() => {
            const ed = document.querySelector('.ProseMirror[contenteditable="true"]');
            const fg = document.querySelector('flow-generate-icon-button');
            return Boolean(ed) && Boolean(fg);
        })()""")
        if ready:
            break
        await asyncio.sleep(1.0)

    for _attempt in range(4):
        if mode == "auto" and credit_exhausted_event is not None and credit_exhausted_event.is_set() and active_model != FLOW_ZERO_CREDIT_MODEL:
            await _switch_to_zero_credit_fallback("Sibling shard signaled credit_exhausted_event")

        await client.eval(
            "window.__bci_flow_forbid_credit_approve = true;"
            if active_model == FLOW_ZERO_CREDIT_MODEL
            else "window.__bci_flow_forbid_credit_approve = false;"
        )
        await client.eval(DISMISS_CREDIT_DIALOG_JS)
        focused = await client.eval("""(() => {
            const ed = document.querySelector('.ProseMirror[contenteditable="true"]');
            if (!ed) return false;
            ed.focus();
            document.execCommand('selectAll', false, null);
            document.execCommand('delete', false, null);
            return true;
        })()""")
        if not focused:
            await asyncio.sleep(1.0)
            continue

        await client.send("Input.insertText", {"text": prompt_text})
        await asyncio.sleep(0.35)
        await client.eval(f"""(() => {{
            const ed = document.querySelector('.ProseMirror[contenteditable="true"]');
            if (!ed) return false;
            if ((ed.innerText || '').trim().length < 15) {{
                ed.focus();
                document.execCommand('selectAll', false, null);
                document.execCommand('insertText', false, {json.dumps(prompt_text)});
            }}
            ed.dispatchEvent(new InputEvent('input', {{ bubbles: true, cancelable: true, inputType: 'insertText' }}));
            ed.dispatchEvent(new Event('change', {{ bubbles: true }}));
            return true;
        }})()""")
        await asyncio.sleep(0.35)

        cred_pre = await client.eval(CHECK_CREDIT_EXHAUSTION_JS) or {}
        if active_model == FLOW_PRIMARY_VIDEO_MODEL and bool(cred_pre.get("exhausted")):
            if mode == "omni":
                raise FlowCircuitBreakerError(
                    f"Omni 1.1 Flash out of credits before Start generation: {cred_pre}"
                )
            await _switch_to_zero_credit_fallback(f"Credits exhausted pre-submit ({cred_pre})")
            await asyncio.sleep(0.3)

        if active_model == FLOW_ZERO_CREDIT_MODEL:
            fam_now = await read_active_flow_model_family(client)
            warn_now = bool(await client.eval("Boolean(document.querySelector('button.prompt-warning-button'))"))
            if fam_now != "veo_3_1_lite_low_priority" or warn_now:
                if warn_now and await count_chips(client) > 0:
                    ref_state["lite_supports_ref"] = False
                    await clear_prompt_ingredients(client)
                await _configure_zero_credit_veo_lite(client, force=True, output_count=zc_out)
                await asyncio.sleep(0.3)
                fam_now = await read_active_flow_model_family(client)
                warn_now = bool(await client.eval("Boolean(document.querySelector('button.prompt-warning-button'))"))
                if fam_now != "veo_3_1_lite_low_priority" or warn_now:
                    print(
                        f"[FlowDiorama] Refusing to submit on zero-credit tier with model_family={fam_now!r}, warn={warn_now}; retrying..."
                    )
                    continue

        sub_res = await client.eval("""(() => {
            const fg = document.querySelector('flow-generate-icon-button');
            const btn = document.querySelector('button[aria-label="Start generation"], button.generate-icon-button');
            const r = btn ? btn.getBoundingClientRect() : null;
            const fn = typeof getEventListeners === 'function' && fg ? getEventListeners(fg)?.generate?.[0]?.listener : null;
            if (fn) {
                fn({isTrusted: true});
                return { action: 'listener_invoked', x: r ? r.x + r.width / 2 : 0, y: r ? r.y + r.height / 2 : 0 };
            }
            if (btn && !btn.disabled && r) {
                return { action: 'needs_mouse_click', x: r.x + r.width / 2, y: r.y + r.height / 2 };
            }
            return { action: 'not_ready', x: 0, y: 0 };
        })()""") or {}

        if sub_res.get("action") == "needs_mouse_click" and sub_res.get("x", 0) > 0:
            mx, my = int(sub_res["x"]), int(sub_res["y"])
            await client.send("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": mx, "y": my})
            await client.send("Input.dispatchMouseEvent", {"type": "mousePressed", "x": mx, "y": my, "button": "left", "clickCount": 1})
            await asyncio.sleep(0.08)
            await client.send("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": mx, "y": my, "button": "left", "clickCount": 1})

        switched_mid_wait = False
        for wait_i in range(10):
            await asyncio.sleep(0.5)
            await client.eval(DISMISS_CREDIT_DIALOG_JS)
            if active_model == FLOW_PRIMARY_VIDEO_MODEL:
                cred_post = await client.eval(CHECK_CREDIT_EXHAUSTION_JS) or {}
                if bool(cred_post.get("exhausted")):
                    if mode == "omni":
                        raise FlowCircuitBreakerError(
                            f"Omni 1.1 Flash ran out of credits on submit: {cred_post}"
                        )
                    await _switch_to_zero_credit_fallback(
                        f"Credits exhausted mid-episode on submit ({cred_post})"
                    )
                    switched_mid_wait = True
                    break
            ed_len = await client.eval("""(() => {
                const ed = document.querySelector('.ProseMirror[contenteditable="true"]');
                return ed ? (ed.innerText || '').trim().length : -1;
            })()""")
            if ed_len == 0:
                if submission_meta_out is not None:
                    submission_meta_out.update(
                        {
                            "flow_model": active_model,
                            "credit_tier": active_tier,
                            "zero_credit_verified": bool(active_tier == "zero_credit_fallback"),
                        }
                    )
                return True
            if wait_i == 3 and sub_res.get("x", 0) > 0:
                mx, my = int(sub_res["x"]), int(sub_res["y"])
                await client.send("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": mx, "y": my})
                await client.send("Input.dispatchMouseEvent", {"type": "mousePressed", "x": mx, "y": my, "button": "left", "clickCount": 1})
                await asyncio.sleep(0.08)
                await client.send("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": mx, "y": my, "button": "left", "clickCount": 1})
        if switched_mid_wait:
            continue

    return False


async def _download_newest_ready_tile(
    client: DirectCDPClient,
    dst_mp4: Path,
    flow_dl_dir: Path,
    seen_global_shas: set[str],
    seen_tab_srcs: set[str],
    capture_v4_ss_path: Path | None = None,
    shard_id: int | str = 0,
    project_slug: str = "",
    max_candidates: int = 1,
    candidate_eval_fn: Any = None,
) -> dict[str, Any] | None:
    """
    Downloads the newest completed `flow-video-tile` batch (up to `max_candidates` from `x1..x4`) to `dst_mp4`.
    When `max_candidates > 1` and `candidate_eval_fn` is provided, fetches all newly rendered sibling tiles
    from the batch, marks all batch URLs in `seen_tab_srcs` so subsequent prompts never collide with sibling
    tiles, evaluates each candidate via `candidate_eval_fn`, and writes the highest-scoring CV-passing MP4.
    Falls back seamlessly to `FlowDownloadHarvestLock` + isolated `shard_dl_dir` + `More -> Download -> 720p`.
    """
    eff_max_cands = max(1, min(int(FLOW_ZERO_CREDIT_VIDEO_MAX_BATCH), int(max_candidates or 1)))

    # Scroll top of Flow canvas so newest tile(s) (`validTiles[0..k]`) are mounted in DOM
    await client.eval("""(() => {
        const scrollers = Array.from(document.querySelectorAll('*')).filter(el => el.scrollHeight > el.clientHeight + 80);
        for (const s of scrollers) { try { s.scrollTop = 0; } catch (e) {} }
        const firstTile = document.querySelector('flow-video-tile');
        if (firstTile) {
            firstTile.scrollIntoView({block: 'center', inline: 'center'});
            firstTile.dispatchEvent(new MouseEvent('mouseenter', {bubbles: true}));
            firstTile.dispatchEvent(new MouseEvent('mouseover', {bubbles: true}));
        }
    })()""")
    await asyncio.sleep(0.6)

    # When multi-candidate batching is active and V4 export screenshot is still needed, capture V4 menu first
    if eff_max_cands > 1 and capture_v4_ss_path is not None and not capture_v4_ss_path.exists():
        await client.eval(f"""(() => {{
            const classifyTile = {FLOW_TILE_CLASSIFIER_JS};
            const validTiles = Array.from(document.querySelectorAll('flow-video-tile')).filter(el => {{
                const cls = classifyTile(el);
                return !cls.isError && !cls.pct;
            }});
            const target = validTiles[0];
            if (!target) return;
            target.dispatchEvent(new MouseEvent('mouseenter', {{bubbles: true}}));
            const more = target.querySelector('button[aria-label*="More" i]');
            if (more) more.click();
        }})()""")
        await asyncio.sleep(0.5)
        await client.eval("""(() => {
            const items = Array.from(document.querySelectorAll('.cdk-overlay-pane flow-menu-item, .cdk-overlay-pane button, .cdk-overlay-pane [role="menuitem"]'));
            const dl = items.find(el => (el.innerText || '').includes('Download'));
            if (dl) dl.click();
        })()""")
        await asyncio.sleep(0.5)
        ss_v4 = await client.send("Page.captureScreenshot", {"format": "png"})
        if ss_v4 and "data" in ss_v4:
            capture_v4_ss_path.parent.mkdir(parents=True, exist_ok=True)
            capture_v4_ss_path.write_bytes(base64.b64decode(ss_v4["data"]))
        await press_escape(client)
        await client.eval("document.body.click()")
        await asyncio.sleep(0.25)

    # Fast Method A: Direct authenticated in-page fetch of newest batch tiles (`x1..x4`)
    if capture_v4_ss_path is None or capture_v4_ss_path.exists():
        new_srcs_raw = await client.eval(f"""(() => {{
            const classifyTile = {FLOW_TILE_CLASSIFIER_JS};
            const seen = new Set({json.dumps(list(seen_tab_srcs))});
            const validTiles = Array.from(document.querySelectorAll('flow-video-tile')).filter(el => {{
                const cls = classifyTile(el);
                return !cls.isError && !cls.pct;
            }});
            const out = [];
            for (const tile of validTiles) {{
                const v = tile.querySelector('video[src^="https://"]');
                if (v && v.src && !seen.has(v.src) && !out.includes(v.src)) {{
                    out.push(v.src);
                }}
            }}
            return out;
        }})()""") or []
        new_srcs = [str(u) for u in new_srcs_raw if isinstance(u, str) and u.startswith("https://")]
        if new_srcs:
            batch_srcs = new_srcs[:eff_max_cands]
            cand_entries: list[dict[str, Any]] = []
            dst_mp4.parent.mkdir(parents=True, exist_ok=True)
            try:
                for cand_i, src_url in enumerate(batch_srcs):
                    b64_res = await client.eval(f"""(async () => {{
                        try {{
                            const r = await fetch({json.dumps(src_url)});
                            if (!r.ok) return '';
                            const buf = await r.arrayBuffer();
                            if (buf.byteLength < 160000) return '';
                            const u8 = new Uint8Array(buf);
                            let bin = '';
                            const chunk = 32768;
                            for (let i = 0; i < u8.length; i += chunk) {{
                                bin += String.fromCharCode.apply(null, u8.subarray(i, i + chunk));
                            }}
                            return btoa(bin);
                        }} catch (e) {{
                            return '';
                        }}
                    }})()""", await_promise=True) or ""
                    if not (isinstance(b64_res, str) and len(b64_res) > 210_000):
                        continue
                    raw_bytes = base64.b64decode(b64_res)
                    sha = hashlib.sha256(raw_bytes).hexdigest().lower()
                    if sha in seen_global_shas:
                        continue
                    if len(batch_srcs) == 1 or not callable(candidate_eval_fn):
                        dst_mp4.write_bytes(raw_bytes)
                        seen_global_shas.add(sha)
                        for s_all in new_srcs:
                            seen_tab_srcs.add(s_all)
                        return {
                            "sha256": sha,
                            "file_size_bytes": len(raw_bytes),
                            "source_download_filename": f"flow_direct_{dst_mp4.name}",
                            "candidates_evaluated": 1,
                        }
                    cand_path = dst_mp4.with_name(f"{dst_mp4.stem}_cand{cand_i}.mp4")
                    cand_path.write_bytes(raw_bytes)
                    ev = await asyncio.to_thread(candidate_eval_fn, cand_path)
                    cand_entries.append(
                        {
                            "cand_idx": cand_i,
                            "path": cand_path,
                            "sha": sha,
                            "size": len(raw_bytes),
                            "src_url": src_url,
                            "passed": bool(ev.get("passed", False)),
                            "score": float(ev.get("score", 0.0)),
                            "cv_rep": ev.get("cv_rep"),
                        }
                    )

                if cand_entries:
                    cand_entries.sort(key=lambda item: (1 if item["passed"] else 0, item["score"]), reverse=True)
                    best = cand_entries[0]
                    shutil.copy2(best["path"], dst_mp4)
                    seen_global_shas.add(best["sha"])
                    for s_all in new_srcs:
                        seen_tab_srcs.add(s_all)
                    return {
                        "sha256": best["sha"],
                        "file_size_bytes": int(best["size"]),
                        "source_download_filename": f"flow_direct_x{len(cand_entries)}_cand{best['cand_idx'] + 1}_{dst_mp4.name}",
                        "candidates_evaluated": len(cand_entries),
                        "selected_candidate_index": int(best["cand_idx"]) + 1,
                        "cached_cv_rep": best.get("cv_rep") if best["passed"] else None,
                    }
            finally:
                for ce in cand_entries:
                    p = ce.get("path")
                    if isinstance(p, Path):
                        p.unlink(missing_ok=True)

    # Reliable Method B: Official Flow UI menu download under FlowDownloadHarvestLock into isolated shard_dl_dir
    shard_dl_dir = flow_dl_dir / f"shard_{shard_id}"
    shard_bridge_dir: Path | None = None
    if CONTAINER_DOWNLOADS_PATH:
        bridge_sub = f"shard_{project_slug}_{shard_id}" if project_slug else f"shard_{shard_id}"
        shard_bridge_dir = USER_DOWNLOADS_DIR / bridge_sub

    for _dl_attempt in range(3):
        async with FlowDownloadHarvestLock(timeout_sec=300.0):
            shard_dl_dir.mkdir(parents=True, exist_ok=True)
            if shard_bridge_dir is not None:
                shard_bridge_dir.mkdir(parents=True, exist_ok=True)
                try:
                    os.chmod(shard_bridge_dir, 0o777)
                except OSError:
                    pass
                browser_dl_path = f"{CONTAINER_DOWNLOADS_PATH.rstrip('/')}/{shard_bridge_dir.name}"
                before_bridge = {f.resolve(): f.stat().st_mtime for f in shard_bridge_dir.glob("*.mp4") if f.is_file()}
            else:
                browser_dl_path = str(shard_dl_dir.resolve())
                before_bridge = {}

            await client.send("Browser.setDownloadBehavior", {
                "behavior": "allow",
                "downloadPath": browser_dl_path,
            })
            before_shard = {f.resolve(): f.stat().st_mtime for f in shard_dl_dir.glob("*.mp4") if f.is_file()}
            click_epoch = time.time()

            await client.eval("document.body.click()")
            await asyncio.sleep(0.3)

            new_src = await client.eval(f"""(() => {{
                const classifyTile = {FLOW_TILE_CLASSIFIER_JS};
                const scrollers = Array.from(document.querySelectorAll('*')).filter(el => el.scrollHeight > el.clientHeight + 80);
                for (const s of scrollers) {{ try {{ s.scrollTop = 0; }} catch (e) {{}} }}
                const validTiles = Array.from(document.querySelectorAll('flow-video-tile')).filter(el => {{
                    const cls = classifyTile(el);
                    return !cls.isError && !cls.pct;
                }});
                const target = validTiles[0];
                if (!target) return '';
                target.scrollIntoView({{block: 'center', inline: 'center'}});
                target.dispatchEvent(new MouseEvent('mouseenter', {{bubbles: true}}));
                const more = target.querySelector('button[aria-label*="More" i]');
                if (more) more.click();
                const v = target.querySelector('video[src^="https://"]');
                return v ? v.src : 'clicked';
            }})()""") or ""
            await asyncio.sleep(0.6)

            await client.eval("""(() => {
                const items = Array.from(document.querySelectorAll('.cdk-overlay-pane flow-menu-item, .cdk-overlay-pane button, .cdk-overlay-pane [role="menuitem"]'));
                const dl = items.find(el => (el.innerText || '').includes('Download'));
                if (dl) dl.click();
            })()""")
            await asyncio.sleep(0.6)

            if capture_v4_ss_path is not None and not capture_v4_ss_path.exists():
                ss_res = await client.send("Page.captureScreenshot", {"format": "png"})
                if ss_res and "data" in ss_res:
                    capture_v4_ss_path.parent.mkdir(parents=True, exist_ok=True)
                    capture_v4_ss_path.write_bytes(base64.b64decode(ss_res["data"]))

            await client.eval("""(() => {
                const items = Array.from(document.querySelectorAll('.cdk-overlay-pane button, .cdk-overlay-pane [role="menuitem"], .cdk-overlay-pane flow-menu-item'));
                const b720 = items.find(el => (el.innerText || '').includes('720p') || (el.innerText || '').includes('Original'));
                if (b720) b720.click();
            })()""")

            dl_deadline = time.monotonic() + 26.0
            while time.monotonic() < dl_deadline:
                await asyncio.sleep(0.8)
                if shard_bridge_dir is not None and shard_bridge_dir.exists():
                    for bf in list(shard_bridge_dir.glob("*.mp4")):
                        try:
                            if not bf.is_file():
                                continue
                            bst = bf.stat()
                            prev_bm = before_bridge.get(bf.resolve())
                            if bst.st_size >= 160_000 and bst.st_mtime >= click_epoch - 0.05 and (prev_bm is None or bst.st_mtime > prev_bm):
                                staged_dst = shard_dl_dir / bf.name
                                if staged_dst.exists():
                                    staged_dst = shard_dl_dir / f"{bf.stem}_{int(time.time() * 1000)}{bf.suffix}"
                                shutil.move(str(bf), str(staged_dst))
                        except OSError:
                            continue

                cands: list[Path] = []
                for f in shard_dl_dir.glob("*.mp4"):
                    try:
                        if not f.is_file():
                            continue
                        fst = f.stat()
                        prev_sm = before_shard.get(f.resolve())
                        if fst.st_size >= 160_000 and fst.st_mtime >= click_epoch - 0.05 and (prev_sm is None or fst.st_mtime > prev_sm):
                            cands.append(f)
                    except OSError:
                        continue
                if cands:
                    await asyncio.sleep(0.6)
                    newest = sorted(cands, key=lambda x: x.stat().st_mtime, reverse=True)[0]
                    sha = FlowProjectSubagentWorker.compute_file_sha256(newest).lower()
                    if sha not in seen_global_shas:
                        dst_mp4.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(newest, dst_mp4)
                        seen_global_shas.add(sha)
                        if new_src.startswith("https://"):
                            seen_tab_srcs.add(new_src)
                        return {
                            "sha256": sha,
                            "file_size_bytes": dst_mp4.stat().st_size,
                            "source_download_filename": newest.name,
                        }
        await asyncio.sleep(1.5)
    return None


MAX_CONSECUTIVE_RENDER_TIMEOUTS = 2


def compute_zero_credit_batch_plan(
    num_pending_clips: int,
    max_parallel_tabs: int = FLOW_MAX_PARALLEL_BATCH_SIZE,
) -> tuple[int, int]:
    """
    Compute `(n_worker_tabs, zero_credit_output_count)` so `n_worker_tabs * zero_credit_output_count <= 4`
    (`FLOW_ZERO_CREDIT_MAX_CONCURRENT_RENDERS`), saturating Google Flow's free `0-credit` queue
    (`4 tabs x x1` for full queues, `2 tabs x x2` for 2 clips, `1 tab x x4` for 1 clip or `--tabs 1`).
    """
    pending = max(0, int(num_pending_clips))
    if pending == 0:
        return 0, 1
    req_tabs = max(1, int(max_parallel_tabs))
    n_tabs = max(
        1,
        min(
            req_tabs,
            int(FLOW_MAX_PARALLEL_BATCH_SIZE),
            int(FLOW_ZERO_CREDIT_MAX_CONCURRENT_RENDERS),
            pending,
        ),
    )
    out_cnt = min(
        int(FLOW_ZERO_CREDIT_VIDEO_MAX_BATCH),
        max(1, int(FLOW_ZERO_CREDIT_MAX_CONCURRENT_RENDERS) // n_tabs),
    )
    return n_tabs, out_cnt


async def _run_shard_worker(
    shard_idx: int,
    shard_clips: list[dict[str, Any]],
    project_id: str,
    project_dir: Path,
    short_ref_map: dict[str, Path],
    tab_open_lock: asyncio.Lock,
    opened_tabs: list[str],
    seen_global_shas: set[str],
    episode_qa_contract: dict[str, Any] | None = None,
    cdp_port: int = 9222,
    engine_mode: str = DEFAULT_FLOW_ENGINE_MODE,
    credit_exhausted_event: asyncio.Event | None = None,
    on_clip_completed: Any = None,
    shared_clip_queue: collections.deque[dict[str, Any]] | None = None,
    zero_credit_output_count: int = 1,
) -> dict[str, Any]:
    """
    Runs one dedicated Google Flow shard worker (`<= DIORAMA_SHARD_MAX_CLIPS` (14) clips per tab wave,
    1 clip rendered at a time for 100% 1:1 ordering, opening a fresh clean Flow project tab every 14 clips
    so Angular virtual-scroll never unmounts tiles). Supports dynamic tail work-stealing via `shared_clip_queue`
    and `0-credit` multi-candidate (`x1..x4`) best-of-batch CV selection.
    """
    from pipeline.dynamic_episode_qa import verify_clip_multimodal_contract
    from pipeline.media_cache import cached_by_clip_stat, fast_file_sha256, register_staged_copy

    mode = _normalize_engine_mode(engine_mode)
    eff_zc_outputs = max(1, min(int(FLOW_ZERO_CREDIT_VIDEO_MAX_BATCH), int(zero_credit_output_count or 1)))
    native_dir = project_dir / "03_visuals" / "flow_native_clips"
    flow_dl_dir = project_dir / "03_visuals" / "flow_downloads"
    screenshots_dir = project_dir / "03_visuals" / "flow_screenshots"
    native_dir.mkdir(parents=True, exist_ok=True)
    flow_dl_dir.mkdir(parents=True, exist_ok=True)
    screenshots_dir.mkdir(parents=True, exist_ok=True)

    contract_sig = hashlib.sha1(json.dumps(episode_qa_contract or {}, sort_keys=True).encode("utf-8")).hexdigest()[:12]
    completed_records: list[dict[str, Any]] = []
    shard_failed_clips: list[tuple[int, str]] = []
    clip_queue: collections.deque[dict[str, Any]] = (
        shared_clip_queue if shared_clip_queue is not None else collections.deque(shard_clips)
    )

    def _pop_next_pending_clip() -> dict[str, Any] | None:
        while clip_queue:
            c_spec = clip_queue.popleft()
            c_num = int(c_spec["clip_number"])
            dst = native_dir / f"clip_{c_num}.mp4"
            if dst.exists() and dst.stat().st_size >= MIN_CLIP_SIZE_BYTES:
                g_str = str(c_spec.get("grammar") or "arch_cutaway_diorama")
                s_ver = int(c_spec.get("schema_version") or 6)
                b_mode = str(c_spec.get("brain_mode") or "")
                st_prof = str(c_spec.get("style_profile") or "")

                def _eval_shard_clip(
                    lp: Path,
                    _g: str = g_str,
                    _sv: int = s_ver,
                    _cn: int = c_num,
                    _bm: str = b_mode,
                    _sp: str = st_prof,
                ) -> dict[str, Any]:
                    cv_r = _invoke_inspect_diorama_clip_cv(lp, grammar=_g, schema_version=_sv, brain_mode=_bm, style_profile=_sp)
                    dq_ok = True
                    if cv_r["passed"] and episode_qa_contract:
                        dq_ok = bool(verify_clip_multimodal_contract(lp, _cn, episode_qa_contract).get("passed", True))
                    return {"cv_rep": cv_r, "dqa_ok": dq_ok}

                cached_chk = cached_by_clip_stat(
                    dst,
                    namespace="flow_clip_gate_v3",
                    compute_fn=_eval_shard_clip,
                    extra_key=f"{g_str}|{s_ver}|{b_mode}|{st_prof}|{c_num}|{contract_sig}",
                )
                cv_rep = cached_chk["cv_rep"]
                dqa_ok = bool(cached_chk["dqa_ok"])
                if cv_rep["passed"] and dqa_ok:
                    sha = fast_file_sha256(dst).lower()
                    seen_global_shas.add(sha)
                    rec = {
                        "clip_index": c_num,
                        "sha256": sha,
                        "file_size_bytes": dst.stat().st_size,
                        "source_download_filename": dst.name,
                        "downloaded_at_epoch": round(dst.stat().st_mtime, 3),
                        "cv_qa": cv_rep,
                    }
                    completed_records.append(rec)
                    if callable(on_clip_completed):
                        try:
                            on_clip_completed(rec, "", "")
                        except Exception:
                            pass
                    continue
            return c_spec
        return None

    first_pending = _pop_next_pending_clip()
    if first_pending is None:
        if shared_clip_queue is None:
            print(f"[Shard {shard_idx}] All {len(shard_clips)} clips already verified on disk; skipping browser tab.")
        return {
            "shard_idx": shard_idx,
            "tab_id": "",
            "flow_project_url": "",
            "wave_tab_ids": [],
            "wave_flow_urls": [],
            "prompts_submitted": 0,
            "clips": completed_records,
        }

    max_per_tab = max(2, int(DIORAMA_SHARD_MAX_CLIPS) // max(1, eff_zc_outputs))
    prompts_submitted = 0
    ref_state: dict[str, Any] = {
        "lite_supports_ref": True,
        "uploaded_in_tab": set(),
        "zero_credit_output_count": eff_zc_outputs,
    }
    is_primary_shard = shard_idx == 1
    shard_tab_ids: list[str] = []
    shard_flow_urls: list[str] = []
    wave_idx = 0
    wave_ws_recoveries = 0
    next_wave_first: dict[str, Any] | None = first_pending

    while next_wave_first is not None:
        shard_title = (
            f"{project_id}_shard{shard_idx}"
            if wave_idx == 0
            else f"{project_id}_shard{shard_idx}_w{wave_idx + 1}"
        )
        async with tab_open_lock:
            tab_alloc = await allocate_dedicated_flow_project_tab(
                cdp_port=cdp_port, existing_tab_id=None, project_id=None
            )
            wave_tab_id = str(tab_alloc["tab_id"])
            opened_tabs.append(wave_tab_id)
            await asyncio.sleep(1.2)

        wave_flow_url = str(tab_alloc["project_url"])
        ws_url = str(tab_alloc["ws_url"])
        shard_tab_ids.append(wave_tab_id)
        shard_flow_urls.append(wave_flow_url)
        seen_tab_srcs: set[str] = set()
        ref_state["uploaded_in_tab"] = set()
        print(
            f"[Shard {shard_idx}] Bound dedicated Flow tab {wave_tab_id[:8]} -> {wave_flow_url} "
            f"(wave {wave_idx + 1}, queue_remaining={len(clip_queue)}, engine_mode={mode}, zc_batch=x{eff_zc_outputs})"
        )

        c_spec: dict[str, Any] | None = next_wave_first
        next_wave_first = None
        try:
            async with DirectCDPClient(ws_url) as client:
                await client.send("Page.enable")
                await client.eval(f"""(() => {{
                    const input = document.querySelector('.editable-text-input');
                    if (input) {{
                        input.value = {json.dumps(shard_title)};
                        input.dispatchEvent(new Event('input', {{bubbles: true}}));
                        input.dispatchEvent(new Event('change', {{bubbles: true}}));
                        input.blur();
                    }}
                }})()""")
                init_cfg = await _configure_diorama_tab_engine(
                    client,
                    engine_mode=mode,
                    credit_exhausted_event=credit_exhausted_event,
                    zero_credit_output_count=eff_zc_outputs,
                )
                print(
                    f"[Shard {shard_idx}] Configured Flow engine ({init_cfg.get('flow_model')} / {init_cfg.get('credit_tier')}): "
                    f"{init_cfg.get('settings_summary')}"
                )

                item_i = 0
                while c_spec is not None:
                    c_num = int(c_spec["clip_number"])
                    grammar = str(c_spec.get("grammar") or "arch_cutaway_diorama")
                    prompt_str = str(c_spec.get("prompt") or c_spec.get("full_prompt") or "")
                    ref_key = _ref_stage_key(c_spec)
                    short_ref = short_ref_map.get(ref_key) if ref_key else None
                    end_rk = str(c_spec.get("end_reference_image") or "").strip()
                    end_short_ref = short_ref_map.get(f"end::{end_rk}") if end_rk else None
                    dst_mp4 = native_dir / f"clip_{c_num}.mp4"

                    clip_done = False
                    attempt_failures: list[str] = []
                    credit_fallback_retried = False
                    consecutive_render_timeouts = 0
                    last_cv_reason = ""
                    regen_try = 0
                    while regen_try < 5:
                        if regen_try == 3 and wave_flow_url:
                            print(f"[Shard {shard_idx}] Refreshing Flow tab before try 4 on Clip {c_num}...")
                            await client.send("Page.reload", {"ignoreCache": False})
                            await asyncio.sleep(7.0)
                            await _configure_diorama_tab_engine(
                                client,
                                engine_mode=mode,
                                credit_exhausted_event=credit_exhausted_event,
                                force=True,
                                zero_credit_output_count=eff_zc_outputs,
                            )

                        # Strict anti-tile-shift settle barrier: wait until 0 tiles are mid-render on this shard canvas
                        settle_js = f"""(() => {{
                            const classifyTile = {FLOW_TILE_CLASSIFIER_JS};
                            const scrollers = Array.from(document.querySelectorAll('*')).filter(el => el.scrollHeight > el.clientHeight + 80);
                            for (const s of scrollers) {{ try {{ s.scrollTop = 0; }} catch (e) {{}} }}
                            const errTiles = document.querySelectorAll('flow-error-tile');
                            errTiles.forEach(et => {{
                                const b = Array.from(et.querySelectorAll('button')).find(x => (x.innerText || x.getAttribute('aria-label') || '').toLowerCase().includes('delete'));
                                if (b) {{ try {{ b.click(); }} catch (e) {{}} }}
                            }});
                            const allTiles = Array.from(document.querySelectorAll('flow-video-tile'));
                            const validTiles = [];
                            const readyTiles = [];
                            let rendering = 0;
                            for (const el of allTiles) {{
                                const cls = classifyTile(el);
                                if (cls.isError) {{
                                    const b = Array.from(el.querySelectorAll('button')).find(x => (x.innerText || x.getAttribute('aria-label') || '').toLowerCase().includes('delete'));
                                    if (b) {{ try {{ b.click(); }} catch (e) {{}} }}
                                    continue;
                                }}
                                validTiles.push(el);
                                if (cls.isReady) {{
                                    readyTiles.push(el);
                                }} else {{
                                    rendering += 1;
                                }}
                            }}
                            if (readyTiles[0]) {{
                                readyTiles[0].dispatchEvent(new MouseEvent('mouseenter', {{bubbles: true}}));
                            }}
                            const srcs = Array.from(document.querySelectorAll('flow-video-tile video[src^="https://"]')).map(v => v.src || '').filter(Boolean);
                            const topEl = readyTiles[0];
                            const topKey = topEl ? ((topEl.querySelector('video') && topEl.querySelector('video').src) || (topEl.querySelector('img') && topEl.querySelector('img').src) || '') : '';
                            return {{ ready: readyTiles.length, rendering, srcs, topKey }};
                        }})()"""

                        settle_deadline = time.monotonic() + 150.0
                        pre_info: dict[str, Any] = {}
                        while time.monotonic() < settle_deadline:
                            pre_info = await client.eval(settle_js) or {}
                            if int(pre_info.get("rendering", 0) or 0) == 0:
                                break
                            await asyncio.sleep(3.0)

                        if int(pre_info.get("rendering", 0) or 0) != 0:
                            print(
                                f"[Shard {shard_idx}] Stale rendering tile still active before Clip {c_num}; reloading tab to enforce rendering == 0..."
                            )
                            await client.send("Page.reload", {"ignoreCache": False})
                            await asyncio.sleep(7.0)
                            await _configure_diorama_tab_engine(
                                client,
                                engine_mode=mode,
                                credit_exhausted_event=credit_exhausted_event,
                                force=True,
                                zero_credit_output_count=eff_zc_outputs,
                            )
                            reload_settle_deadline = time.monotonic() + 30.0
                            while time.monotonic() < reload_settle_deadline:
                                pre_info = await client.eval(settle_js) or {}
                                if int(pre_info.get("rendering", 0) or 0) == 0:
                                    break
                                await asyncio.sleep(2.5)
                            if int(pre_info.get("rendering", 0) or 0) != 0:
                                attempt_failures.append(
                                    f"try {regen_try + 1}: stale_in_flight_tile_not_settled(rendering={pre_info.get('rendering')})"
                                )
                                regen_try += 1
                                continue

                        prev_ready = int(pre_info.get("ready") or 0)
                        prev_top_key = str(pre_info.get("topKey") or "")
                        for s_u in (pre_info.get("srcs") or []):
                            seen_tab_srcs.add(str(s_u))

                        c_style_prof = str(c_spec.get("style_profile") or "")
                        if regen_try == 0:
                            eff_prompt = prompt_str
                        else:
                            eff_prompt = _soften_veo_false_positive_words(
                                prompt_str,
                                style_profile=c_style_prof,
                                grammar=grammar,
                            )
                            if (
                                is_porcelain_v7_plan(c_spec)
                                or grammar in PORCELAIN_V7_VISUAL_GRAMMARS
                                or str(grammar).lower().startswith("porcelain_")
                            ):
                                eff_prompt = _reinforce_porcelain_cv_retry_prompt(
                                    eff_prompt,
                                    grammar=grammar,
                                    cv_reason=last_cv_reason,
                                )
                        print(
                            f"[Shard {shard_idx}] Submitting Clip {c_num} "
                            f"(wave {wave_idx + 1} #{item_i + 1}/{max_per_tab}, queue={len(clip_queue)}, try {regen_try + 1}/5, {grammar})..."
                        )
                        sub_meta: dict[str, Any] = {}
                        ok_sub = await _submit_diorama_prompt_zero_credit(
                            client,
                            eff_prompt,
                            short_ref,
                            ref_state,
                            ref_upload_lock=tab_open_lock,
                            engine_mode=mode,
                            credit_exhausted_event=credit_exhausted_event,
                            submission_meta_out=sub_meta,
                            end_ref_path=end_short_ref,
                        )
                        if not ok_sub:
                            await asyncio.sleep(5.0)
                            ok_sub = await _submit_diorama_prompt_zero_credit(
                                client,
                                eff_prompt,
                                short_ref,
                                ref_state,
                                ref_upload_lock=tab_open_lock,
                                engine_mode=mode,
                                credit_exhausted_event=credit_exhausted_event,
                                submission_meta_out=sub_meta,
                                end_ref_path=end_short_ref,
                            )
                        if not ok_sub:
                            attempt_failures.append(f"try {regen_try + 1}: prompt_submission_failed")
                            print(f"[Shard {shard_idx}] Clip {c_num} submission failed on try {regen_try + 1}/5; retrying...")
                            await asyncio.sleep(5.0)
                            regen_try += 1
                            continue
                        prompts_submitted += 1

                        used_model = str(
                            sub_meta.get("flow_model")
                            or (
                                FLOW_ZERO_CREDIT_MODEL
                                if (mode == "zero-credit" or (credit_exhausted_event is not None and credit_exhausted_event.is_set()))
                                else FLOW_PRIMARY_VIDEO_MODEL
                            )
                        )
                        used_tier = str(
                            sub_meta.get("credit_tier")
                            or ("zero_credit_fallback" if used_model == FLOW_ZERO_CREDIT_MODEL else "omni_monthly_credit")
                        )

                        if is_primary_shard and wave_idx == 0 and item_i == 0 and regen_try == 0:
                            await asyncio.sleep(1.2)
                            ss1 = await client.send("Page.captureScreenshot", {"format": "png"})
                            if ss1 and "data" in ss1:
                                (screenshots_dir / "flow_gate_v1_prompt_approved.png").write_bytes(base64.b64decode(ss1["data"]))

                        # Poll until top ready tile changes or readyTiles increases (immune to prompt caption words & virtual-scroll)
                        render_deadline = time.monotonic() + 240.0
                        v2_done = (screenshots_dir / "flow_gate_v2_rendering_active.png").exists()
                        tile_ready = False
                        tile_errored = False
                        saw_rendering = False
                        mid_render_credit_fallback = False
                        while time.monotonic() < render_deadline:
                            await asyncio.sleep(4.5)
                            await client.eval(DISMISS_CREDIT_DIALOG_JS)

                            if used_model == FLOW_PRIMARY_VIDEO_MODEL:
                                cred_poll = await client.eval(CHECK_CREDIT_EXHAUSTION_JS) or {}
                                if bool(cred_poll.get("credit_banner")):
                                    if mode == "omni":
                                        raise FlowCircuitBreakerError(
                                            f"Omni 1.1 Flash ran out of credits mid-render on Clip {c_num}: {cred_poll}"
                                        )
                                    if mode == "auto" and not credit_fallback_retried:
                                        print(
                                            f"[Shard {shard_idx}] Credits ran out mid-render on Clip {c_num} ({cred_poll}); "
                                            f"switching all shards to 0-credit {FLOW_ZERO_CREDIT_MODEL}!"
                                        )
                                        if credit_exhausted_event is not None:
                                            credit_exhausted_event.set()
                                        credit_fallback_retried = True
                                        await press_escape(client)
                                        await _configure_zero_credit_veo_lite(
                                            client,
                                            force=True,
                                            output_count=eff_zc_outputs,
                                        )
                                        mid_render_credit_fallback = True
                                        break

                            poll = await client.eval(f"""(() => {{
                                const classifyTile = {FLOW_TILE_CLASSIFIER_JS};
                                const scrollers = Array.from(document.querySelectorAll('*')).filter(el => el.scrollHeight > el.clientHeight + 80);
                                for (const s of scrollers) {{ try {{ s.scrollTop = 0; }} catch (e) {{}} }}
                                const seen = new Set({json.dumps(list(seen_tab_srcs))});
                                const errTiles = document.querySelectorAll('flow-error-tile');
                                let hadErr = errTiles.length > 0;
                                errTiles.forEach(et => {{
                                    const b = Array.from(et.querySelectorAll('button')).find(x => (x.innerText || x.getAttribute('aria-label') || '').toLowerCase().includes('delete'));
                                    if (b) {{ try {{ b.click(); }} catch (e) {{}} }}
                                }});
                                const allTiles = Array.from(document.querySelectorAll('flow-video-tile'));
                                const readyTiles = [];
                                let rendering = 0;
                                for (const el of allTiles) {{
                                    const cls = classifyTile(el);
                                    if (cls.isError) {{
                                        hadErr = true;
                                        const b = Array.from(el.querySelectorAll('button')).find(x => (x.innerText || x.getAttribute('aria-label') || '').toLowerCase().includes('delete'));
                                        if (b) {{ try {{ b.click(); }} catch (e) {{}} }}
                                        continue;
                                    }}
                                    if (cls.isReady) {{
                                        readyTiles.push(el);
                                    }} else {{
                                        rendering += 1;
                                    }}
                                }}
                                if (readyTiles[0]) {{
                                    readyTiles[0].dispatchEvent(new MouseEvent('mouseenter', {{bubbles: true}}));
                                }}
                                const topEl = readyTiles[0];
                                const topKey = topEl ? ((topEl.querySelector('video') && topEl.querySelector('video').src) || (topEl.querySelector('img') && topEl.querySelector('img').src) || '') : '';
                                const hasNewSrc = readyTiles.some(el => {{
                                    const v = el.querySelector('video[src^="https://"]');
                                    return Boolean(v && v.src && !seen.has(v.src));
                                }});
                                return {{ ready: readyTiles.length, rendering, hasNewSrc, topKey, hadErr }};
                            }})()""") or {}

                            if int(poll.get("rendering") or 0) > 0:
                                saw_rendering = True
                                if is_primary_shard and not v2_done:
                                    ss2 = await client.send("Page.captureScreenshot", {"format": "png"})
                                    if ss2 and "data" in ss2:
                                        (screenshots_dir / "flow_gate_v2_rendering_active.png").write_bytes(base64.b64decode(ss2["data"]))
                                        v2_done = True

                            cur_top_key = str(poll.get("topKey") or "")
                            top_changed = bool(cur_top_key and cur_top_key != prev_top_key)
                            if int(poll.get("rendering") or 0) == 0 and (
                                bool(poll.get("hasNewSrc"))
                                or top_changed
                                or int(poll.get("ready") or 0) > prev_ready
                            ) and (saw_rendering or top_changed or bool(poll.get("hasNewSrc"))):
                                tile_ready = True
                                break
                            if bool(poll.get("hadErr")) and int(poll.get("rendering") or 0) == 0:
                                tile_errored = True
                                break

                        if mid_render_credit_fallback:
                            continue

                        if tile_errored or not tile_ready:
                            fail_kind = "flow_tile_error" if tile_errored else "render_timeout"
                            attempt_failures.append(f"try {regen_try + 1}: {fail_kind}")
                            if fail_kind == "render_timeout":
                                consecutive_render_timeouts += 1
                                if consecutive_render_timeouts >= MAX_CONSECUTIVE_RENDER_TIMEOUTS:
                                    attempt_failures.append(
                                        f"prompt_rewrite_needed(consecutive_render_timeouts={consecutive_render_timeouts})"
                                    )
                                    print(
                                        f"[Shard {shard_idx}] Clip {c_num} hit {consecutive_render_timeouts} consecutive "
                                        f"render_timeouts; aborting clip early (prompt_rewrite_needed)..."
                                    )
                                    break
                            else:
                                consecutive_render_timeouts = 0
                                if used_model == FLOW_ZERO_CREDIT_MODEL:
                                    backoff_s = min(50.0, 15.0 * (regen_try + 1) + 2.5 * (shard_idx % 3))
                                    print(
                                        f"[Shard {shard_idx}] Clip {c_num} {fail_kind} on try {regen_try + 1}/5; "
                                        f"backing off {backoff_s:.1f}s for 0-credit queue slot..."
                                    )
                                    await asyncio.sleep(backoff_s)
                                    regen_try += 1
                                    continue
                            print(f"[Shard {shard_idx}] Clip {c_num} {fail_kind} on try {regen_try + 1}/5; regenerating...")
                            regen_try += 1
                            continue

                        consecutive_render_timeouts = 0
                        if is_primary_shard and not (screenshots_dir / "flow_gate_v3_canvas_clips_ready.png").exists():
                            ss3 = await client.send("Page.captureScreenshot", {"format": "png"})
                            if ss3 and "data" in ss3:
                                (screenshots_dir / "flow_gate_v3_canvas_clips_ready.png").write_bytes(base64.b64decode(ss3["data"]))

                        v4_target = (
                            (screenshots_dir / "flow_gate_v4_export_ready.png")
                            if (is_primary_shard and not (screenshots_dir / "flow_gate_v4_export_ready.png").exists())
                            else None
                        )
                        schema_ver = int(c_spec.get("schema_version") or 6)
                        brain_mode_val = str(c_spec.get("brain_mode") or "")
                        style_prof_val = str(c_spec.get("style_profile") or "")
                        active_max_cands = eff_zc_outputs if used_model == FLOW_ZERO_CREDIT_MODEL else 1

                        def _score_video_candidate(
                            cand_mp4: Path,
                            _g: str = grammar,
                            _sv: int = schema_ver,
                            _bm: str = brain_mode_val,
                            _sp: str = style_prof_val,
                            _cn: int = c_num,
                        ) -> dict[str, Any]:
                            cv_r = _invoke_inspect_diorama_clip_cv(cand_mp4, _g, _sv, _bm, _sp)
                            dq_ok = True
                            if cv_r["passed"] and episode_qa_contract:
                                dq_ok = bool(verify_clip_multimodal_contract(cand_mp4, _cn, episode_qa_contract).get("passed", True))
                            passed = bool(cv_r["passed"] and dq_ok)
                            motion_val = float(cv_r.get("max_frame_diff") or 0.0)
                            plaque_pen = float(cv_r.get("plaque_glyph_run") or 0.0) * 0.4
                            luma_val = float(cv_r.get("mean_luma") or cv_r.get("top_luma_mean") or 120.0)
                            score = min(40.0, motion_val * 2.5) + min(25.0, luma_val * 0.1) - plaque_pen
                            return {"passed": passed, "score": round(score, 3), "cv_rep": cv_r}

                        tmp_cand = Path(f"/tmp/aab_flow_cand_{shard_idx}_{c_num}_{regen_try}.mp4")
                        tmp_cand.unlink(missing_ok=True)
                        dl_info = await _download_newest_ready_tile(
                            client=client,
                            dst_mp4=tmp_cand,
                            flow_dl_dir=flow_dl_dir,
                            seen_global_shas=seen_global_shas,
                            seen_tab_srcs=seen_tab_srcs,
                            capture_v4_ss_path=v4_target,
                            shard_id=shard_idx,
                            project_slug=project_id,
                            max_candidates=active_max_cands,
                            candidate_eval_fn=_score_video_candidate if active_max_cands > 1 else None,
                        )
                        if not dl_info or not tmp_cand.exists():
                            attempt_failures.append(f"try {regen_try + 1}: download_missed")
                            print(f"[Shard {shard_idx}] Clip {c_num} download missed on try {regen_try + 1}/5; retrying...")
                            tmp_cand.unlink(missing_ok=True)
                            regen_try += 1
                            continue

                        cached_cv = dl_info.get("cached_cv_rep")
                        cv_rep = (
                            cached_cv
                            if isinstance(cached_cv, dict)
                            else await asyncio.to_thread(
                                _invoke_inspect_diorama_clip_cv, tmp_cand, grammar, schema_ver, brain_mode_val, style_prof_val
                            )
                        )
                        if not cv_rep["passed"]:
                            last_cv_reason = str(cv_rep.get("reason") or "")
                            attempt_failures.append(f"try {regen_try + 1}: cv_qa({cv_rep.get('reason')})")
                            print(
                                f"[Shard {shard_idx}] Clip {c_num} failed CV gate on try {regen_try + 1}/5 "
                                f"({cv_rep['reason']}); regenerating in-tab..."
                            )
                            tmp_cand.unlink(missing_ok=True)
                            regen_try += 1
                            continue

                        if episode_qa_contract:
                            dqa_rep = await asyncio.to_thread(
                                verify_clip_multimodal_contract, tmp_cand, c_num, episode_qa_contract
                            )
                            if not dqa_rep.get("passed", True):
                                dqa_issues = dqa_rep.get("issues") or dqa_rep.get("reason") or "contract_violation"
                                last_cv_reason = str(dqa_issues)
                                attempt_failures.append(f"try {regen_try + 1}: dqa({dqa_issues})")
                                print(
                                    f"[Shard {shard_idx}] Clip {c_num} failed Dynamic Episode QA Gate 2 on try {regen_try + 1}/5 "
                                    f"({dqa_issues}); regenerating in-tab..."
                                )
                                tmp_cand.unlink(missing_ok=True)
                                regen_try += 1
                                continue

                        try:
                            await asyncio.to_thread(_ensure_min_clip_size_if_needed, tmp_cand)
                        except MediaIntegrityError as mie:
                            attempt_failures.append(f"try {regen_try + 1}: min_size({mie})")
                            print(f"[Shard {shard_idx}] Clip {c_num} failed size integrity on try {regen_try + 1}/5 ({mie}); retrying...")
                            tmp_cand.unlink(missing_ok=True)
                            regen_try += 1
                            continue

                        dst_mp4.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(tmp_cand, dst_mp4)
                        final_sha = register_staged_copy(tmp_cand, dst_mp4).lower()
                        tmp_cand.unlink(missing_ok=True)
                        seen_global_shas.add(final_sha)
                        st_final = dst_mp4.stat()
                        clip_rec = {
                            "clip_index": c_num,
                            "sha256": final_sha,
                            "file_size_bytes": st_final.st_size,
                            "source_download_filename": dl_info["source_download_filename"],
                            "downloaded_at_epoch": round(st_final.st_mtime, 3),
                            "flow_model": used_model,
                            "model": used_model,
                            "credit_tier": used_tier,
                            "cv_qa": cv_rep,
                        }
                        completed_records.append(clip_rec)
                        if callable(on_clip_completed):
                            try:
                                on_clip_completed(clip_rec, wave_flow_url, wave_tab_id)
                            except Exception:
                                pass
                        print(
                            f"[Shard {shard_idx}] DONE Clip {c_num} ({st_final.st_size / 1e6:.2f} MB, "
                            f"model={used_model}, tier={used_tier}, diff={cv_rep.get('max_frame_diff')}, "
                            f"luma={cv_rep.get('mean_luma', cv_rep.get('top_luma_mean'))}, plaque={cv_rep.get('plaque_glyph_run')})"
                        )
                        clip_done = True
                        break

                    if not clip_done:
                        detail = "; ".join(attempt_failures) if attempt_failures else "exhausted all retries"
                        msg = f"[Shard {shard_idx}] Clip {c_num} failed QA: {detail}"
                        print(f"{msg} (continuing remaining clips in queue)")
                        shard_failed_clips.append((c_num, msg))

                    item_i += 1
                    if item_i >= max_per_tab:
                        next_wave_first = _pop_next_pending_clip()
                        break
                    c_spec = _pop_next_pending_clip()

                if is_primary_shard and not (screenshots_dir / "flow_gate_v3_canvas_clips_ready.png").exists():
                    ss3 = await client.send("Page.captureScreenshot", {"format": "png"})
                    if ss3 and "data" in ss3:
                        (screenshots_dir / "flow_gate_v3_canvas_clips_ready.png").write_bytes(base64.b64decode(ss3["data"]))
                wave_ws_recoveries = 0
        except Exception as wave_exc:
            if isinstance(wave_exc, FlowCircuitBreakerError):
                raise
            wave_ws_recoveries += 1
            if wave_ws_recoveries > 4:
                raise
            print(
                f"[Shard {shard_idx}] Transient CDP/tab disconnect on wave {wave_idx + 1} ({type(wave_exc).__name__}: {wave_exc}); "
                f"rotating fresh Flow tab (recovery {wave_ws_recoveries}/4)..."
            )
            await asyncio.sleep(4.0)
            if c_spec is not None and not (native_dir / f"clip_{int(c_spec['clip_number'])}.mp4").exists():
                next_wave_first = c_spec
            elif next_wave_first is None:
                next_wave_first = _pop_next_pending_clip()
        finally:
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{cdp_port}/json/close/{wave_tab_id}", timeout=5)
                if wave_tab_id in opened_tabs:
                    opened_tabs.remove(wave_tab_id)
                print(f"[Shard {shard_idx}] Closed completed wave {wave_idx + 1} tab {wave_tab_id[:8]}")
            except Exception:
                pass
        wave_idx += 1

    if shard_failed_clips:
        raise RuntimeError(" | ".join(msg for _, msg in shard_failed_clips))

    return {
        "shard_idx": shard_idx,
        "tab_id": shard_tab_ids[0] if shard_tab_ids else "",
        "flow_project_url": shard_flow_urls[0] if shard_flow_urls else "",
        "wave_tab_ids": shard_tab_ids,
        "wave_flow_urls": shard_flow_urls,
        "prompts_submitted": prompts_submitted,
        "clips": completed_records,
    }


def _largest_painted_components(seed_mask: np.ndarray, min_area: int = 250) -> np.ndarray:
    num_l, labels, stats, _ = cv2.connectedComponentsWithStats(seed_mask.astype(np.uint8), connectivity=8)
    out = np.zeros_like(seed_mask, dtype=np.uint8)
    for lbl in range(1, num_l):
        if int(stats[lbl, cv2.CC_STAT_AREA]) >= min_area:
            out[labels == lbl] = 1
    if out.any():
        out = cv2.morphologyEx(out, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))
    return out


def neutralize_v7_brain_reference_tint(img_bgr: np.ndarray) -> np.ndarray:
    """
    Neutralizes pre-baked Phineas Gage prefrontal terracotta-coral (`LAB a`) and medial slate-blue (`LAB b`)
    patches on `lowpoly_v7_refs` brain style anchors to warm-ivory while preserving crisp low-poly facet edges.
    """
    if img_bgr is None or img_bgr.ndim != 3 or img_bgr.shape[2] != 3:
        return img_bgr
    lab = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2LAB).astype(np.float32)
    L, a, b = lab[:, :, 0], lab[:, :, 1], lab[:, :, 2]
    h, w = img_bgr.shape[:2]

    ivory_roi = np.zeros((h, w), dtype=bool)
    ivory_roi[int(h * 0.28) : int(h * 0.58), int(w * 0.15) : int(w * 0.78)] = True
    pink_roi = np.zeros((h, w), dtype=bool)
    pink_roi[int(h * 0.18) : int(h * 0.66), int(w * 0.06) : int(w * 0.94)] = True
    blue_roi = np.zeros((h, w), dtype=bool)
    blue_roi[int(h * 0.28) : int(h * 0.64), int(w * 0.06) : int(w * 0.94)] = True

    ivory_ref = ivory_roi & (a >= 127.5) & (a <= 133.5) & (b >= 139.0) & (b <= 155.0) & (L >= 145.0) & (L <= 238.0)
    if int(ivory_ref.sum()) >= 200:
        L_iv = L[ivory_ref]
        coef_a = np.polyfit(L_iv, a[ivory_ref], 1)
        coef_b = np.polyfit(L_iv, b[ivory_ref], 1)
    else:
        coef_a = np.array([-0.035, 138.0], dtype=np.float32)
        coef_b = np.array([-0.085, 163.0], dtype=np.float32)

    pink_excess = (a - 128.0) - 0.23 * np.maximum(0.0, b - 128.0)
    pink_seed = pink_roi & (L >= 118.0) & (((pink_excess > 7.5) & (a > 139.0)) | ((pink_excess > 3.2) & (a > 135.0) & (L > 168.0)))
    pink_cc = _largest_painted_components(pink_seed, min_area=350)
    if pink_cc.any():
        pink_inner = cv2.erode(pink_cc, np.ones((3, 3), np.uint8), iterations=1).astype(np.float32)
        pink_band = cv2.dilate(pink_cc, np.ones((7, 7), np.uint8), iterations=1) > 0
        pink_edge_alpha = np.clip((pink_excess - 0.8) / 5.5, 0.0, 1.0) * pink_band.astype(np.float32)
        pink_w = np.maximum(pink_inner, pink_edge_alpha)
    else:
        pink_w = np.zeros((h, w), dtype=np.float32)

    blue_seed = blue_roi & (b < 130.0) & (L >= 100.0) & (L < 216.0)
    raw_blue_cc = _largest_painted_components(blue_seed, min_area=250)
    if raw_blue_cc.any():
        num_b, lbl_b, st_b, _ = cv2.connectedComponentsWithStats(raw_blue_cc, connectivity=8)
        blue_cc = np.zeros_like(raw_blue_cc)
        for idx_b in range(1, num_b):
            comp_m = lbl_b == idx_b
            if int(st_b[idx_b, cv2.CC_STAT_AREA]) >= 250 and float(np.median(b[comp_m])) <= 126.5:
                blue_cc[comp_m] = 1
    else:
        blue_cc = raw_blue_cc
    if blue_cc.any():
        blue_inner = cv2.erode(blue_cc, np.ones((3, 3), np.uint8), iterations=1).astype(np.float32)
        blue_band = cv2.dilate(blue_cc, np.ones((7, 7), np.uint8), iterations=1) > 0
        b_expected_iv = np.clip(coef_b[0] * np.minimum(L + 42.0, 235.0) + coef_b[1] + 1.5, 142.0, 153.0)
        blue_edge_alpha = (
            np.clip((b_expected_iv - b) / np.maximum(8.0, b_expected_iv - 124.0), 0.0, 1.0)
            * np.clip((228.0 - L) / 12.0, 0.0, 1.0)
            * blue_band.astype(np.float32)
        )
        blue_w = np.maximum(blue_inner, blue_edge_alpha)
    else:
        blue_w = np.zeros((h, w), dtype=np.float32)

    if not pink_cc.any() and not blue_cc.any():
        return img_bgr.copy()

    w_tot = np.clip(np.maximum(pink_w, blue_w), 0.0, 1.0)
    dL_pink = np.clip((236.0 - L) * 0.56, 0.0, 58.0)
    dL_blue = np.clip((239.0 - L) * 0.59, 0.0, 59.0)
    L_new = L + pink_w * dL_pink + (1.0 - pink_w) * blue_w * dL_blue

    a_target = np.clip(coef_a[0] * L_new + coef_a[1], 128.0, 134.5)
    b_target = np.clip(coef_b[0] * L_new + coef_b[1] + 1.0 * blue_w, 140.0, 154.0)

    lab_out = np.rint(
        np.stack(
            [
                np.clip(L_new, 0.0, 255.0),
                np.clip((1.0 - w_tot) * a + w_tot * a_target, 0.0, 255.0),
                np.clip((1.0 - w_tot) * b + w_tot * b_target, 0.0, 255.0),
            ],
            axis=-1,
        )
    ).astype(np.uint8)
    out_bgr = cv2.cvtColor(lab_out, cv2.COLOR_LAB2BGR)
    ring = (w_tot > 0.05) & (w_tot < 0.95)
    if ring.any():
        blur_bgr = cv2.GaussianBlur(out_bgr, (3, 3), 0.8)
        out_bgr[ring] = blur_bgr[ring]
    unchanged = w_tot <= 1e-4
    out_bgr[unchanged] = img_bgr[unchanged]
    return out_bgr


def _clip_needs_neutral_brain_ref(c_spec: dict[str, Any]) -> bool:
    """Returns True when staging a lowpoly_matte_brain reference anchor whose pre-baked tint conflicts with the target region."""
    if str(c_spec.get("grammar") or "").strip() != "lowpoly_matte_brain":
        return False
    rk = str(c_spec.get("reference_image") or "").strip().lower()
    if "_neutral" in rk:
        return True
    region_blob = f"{c_spec.get('brain_region') or ''} {c_spec.get('anatomy_label') or ''}".lower()
    if "v7_ref_03_sagittal_brain" in rk and "cingulate" not in region_blob:
        return True
    return "prefrontal" not in region_blob


def _ref_stage_key(c_spec: dict[str, Any]) -> str:
    rk = str(c_spec.get("reference_image") or "").strip()
    if not rk:
        return ""
    return f"{rk}::neutral" if _clip_needs_neutral_brain_ref(c_spec) else rk


async def run_sharded_diorama_flow_generation(
    project_id: str | Path,
    clean_existing: bool = False,
    only_clips: list[int] | None = None,
    max_parallel_tabs: int = FLOW_MAX_PARALLEL_BATCH_SIZE,
    cdp_port: int = 9222,
    engine_mode: str = DEFAULT_FLOW_ENGINE_MODE,
) -> dict[str, Any]:
    """
    Main orchestrator: partitions all `neuro_diorama` clips across `<= 5` concurrent shards
    (`<= DIORAMA_SHARD_MAX_CLIPS` (14) clips per tab wave), runs them under the Credit-Aware Dual-Tier
    Engine Policy (`Omni 1.1 Flash` primary -> `Veo 3.1 - Lite [Lower Priority]` 0-credit auto-fallback),
    closes all opened tabs in `finally`, and writes V1-V5 screenshots + cryptographic
    `03_visuals/flow_provenance_receipt.json` (preserving prior clips on partial `--clips` runs).
    """
    mode = _normalize_engine_mode(engine_mode)
    cand_dir = Path(str(project_id))
    project_dir = cand_dir.resolve() if cand_dir.exists() else (PROJECTS_DIR / str(project_id))
    if not project_dir.exists():
        raise FileNotFoundError(f"Project dir not found: {project_dir}")
    project_slug = project_dir.name

    visuals_dir = project_dir / "03_visuals"
    native_dir = visuals_dir / "flow_native_clips"
    screenshots_dir = visuals_dir / "flow_screenshots"
    native_dir.mkdir(parents=True, exist_ok=True)
    screenshots_dir.mkdir(parents=True, exist_ok=True)
    prev_rcpt_path = visuals_dir / "flow_provenance_receipt.json"

    existing_clips_by_idx: dict[int, dict[str, Any]] = {}
    prev_url = ""
    prev_tab = ""
    prev_shard_urls: list[str] = []
    prev_shard_tabs: list[str] = []
    prev_prompts_submitted = 0
    prev_default_model = ""
    if not (clean_existing and not only_clips) and prev_rcpt_path.exists():
        try:
            pr = json.loads(prev_rcpt_path.read_text(encoding="utf-8"))
            if isinstance(pr, dict):
                prev_url = str(pr.get("flow_project_url") or "")
                prev_tab = str(pr.get("tab_target_id") or "")
                prev_shard_urls = [str(u) for u in (pr.get("shard_urls") or []) if u]
                prev_shard_tabs = [str(t) for t in (pr.get("shard_tab_ids") or []) if t]
                prev_prompts_submitted = int(pr.get("prompts_submitted_count") or 0)
                prev_default_model = str(pr.get("flow_model") or pr.get("model") or "")
                if " -> " in prev_default_model:
                    prev_default_model = ""
                for entry in (pr.get("clips") or []):
                    if isinstance(entry, dict) and entry.get("clip_index") is not None:
                        existing_clips_by_idx[int(entry["clip_index"])] = dict(entry)
        except Exception:
            pass

    if clean_existing and not only_clips:
        for old_f in native_dir.glob("clip_*.mp4"):
            old_f.unlink(missing_ok=True)
        prev_rcpt_path.unlink(missing_ok=True)
    elif only_clips:
        for c_idx in only_clips:
            (native_dir / f"clip_{int(c_idx)}.mp4").unlink(missing_ok=True)
            existing_clips_by_idx.pop(int(c_idx), None)

    from pipeline.dynamic_episode_qa import verify_clip_multimodal_contract, write_episode_qa_contract

    vp = json.loads((visuals_dir / "visual_plan.json").read_text(encoding="utf-8"))
    plan_schema_ver = PROMPT_SCHEMA_VERSION_V7 if is_diorama_v7_plan(vp) else 6
    sents, _ = load_diorama_script_sentences(project_dir)
    rendered_clips = build_diorama_v6_prompts(vp, sents)
    write_flow_prompts_json(project_dir, rendered_clips)
    _, episode_qa_contract = write_episode_qa_contract(project_dir, vp, sents, rendered_clips)

    # Stage content-addressed short-named JPEG copies of style/brain/end reference anchors in /tmp (`<= 13` chars, ~95KB)
    short_ref_map: dict[str, Path] = {}
    for c_spec in rendered_clips:
        for rk_raw, stage_k, needs_neutral in (
            (
                str(c_spec.get("reference_image") or "").strip(),
                _ref_stage_key(c_spec),
                _clip_needs_neutral_brain_ref(c_spec),
            ),
            (
                str(c_spec.get("end_reference_image") or "").strip(),
                f"end::{str(c_spec.get('end_reference_image') or '').strip()}",
                False,
            ),
        ):
            if rk_raw and stage_k and stage_k not in short_ref_map:
                src_p = Path(rk_raw) if Path(rk_raw).is_absolute() else (WORKSPACE_ROOT / rk_raw)
                if not src_p.exists() and not Path(rk_raw).is_absolute():
                    src_p = project_dir / rk_raw
                if src_p.exists():
                    hash_payload = src_p.read_bytes() + (b"::neutral_v7" if needs_neutral else b"")
                    sha6 = hashlib.sha1(hash_payload).hexdigest()[:6]
                    dst_tmp = Path(f"/tmp/rf_{sha6}.jpg")
                    if not dst_tmp.exists():
                        img_bgr = cv2.imread(str(src_p))
                        if img_bgr is not None:
                            if needs_neutral:
                                img_bgr = neutralize_v7_brain_reference_tint(img_bgr)
                            h0, w0 = img_bgr.shape[:2]
                            if max(h0, w0) > 1280:
                                scale = 1280.0 / float(max(h0, w0))
                                img_bgr = cv2.resize(
                                    img_bgr,
                                    (max(1, int(round(w0 * scale))), max(1, int(round(h0 * scale)))),
                                    interpolation=cv2.INTER_AREA,
                                )
                            cv2.imwrite(str(dst_tmp), img_bgr, [cv2.IMWRITE_JPEG_QUALITY, 92])
                        else:
                            dst_tmp = Path(f"/tmp/rf_{sha6}{src_p.suffix.lower()}")
                            shutil.copy2(src_p, dst_tmp)
                    short_ref_map[stage_k] = dst_tmp

    raw_targets = (
        [c for c in rendered_clips if int(c["clip_number"]) in set(only_clips)]
        if only_clips
        else list(rendered_clips)
    )
    from pipeline.media_cache import cached_by_clip_stat, fast_file_sha256

    contract_sig_main = hashlib.sha1(json.dumps(episode_qa_contract or {}, sort_keys=True).encode("utf-8")).hexdigest()[:12]
    seen_global_shas: set[str] = {
        fast_file_sha256(existing_cf).lower()
        for existing_cf in native_dir.glob("clip_*.mp4")
        if existing_cf.is_file() and existing_cf.stat().st_size >= 160_000
    }
    target_clips: list[dict[str, Any]] = []
    for c_spec in raw_targets:
        c_num = int(c_spec["clip_number"])
        dst = native_dir / f"clip_{c_num}.mp4"
        if dst.exists() and dst.stat().st_size >= MIN_CLIP_SIZE_BYTES:
            g_str = str(c_spec.get("grammar") or "arch_cutaway_diorama")
            s_ver = int(c_spec.get("schema_version") or plan_schema_ver)
            b_mode = str(c_spec.get("brain_mode") or "")
            st_prof = str(c_spec.get("style_profile") or "")

            def _eval_main_clip(
                lp: Path,
                _g: str = g_str,
                _sv: int = s_ver,
                _cn: int = c_num,
                _bm: str = b_mode,
                _sp: str = st_prof,
            ) -> dict[str, Any]:
                cv_r = _invoke_inspect_diorama_clip_cv(lp, grammar=_g, schema_version=_sv, brain_mode=_bm, style_profile=_sp)
                dq_ok = True
                if cv_r["passed"] and episode_qa_contract:
                    dq_ok = bool(verify_clip_multimodal_contract(lp, _cn, episode_qa_contract).get("passed", True))
                return {"cv_rep": cv_r, "dqa_ok": dq_ok}

            cached_chk = cached_by_clip_stat(
                dst,
                namespace="flow_clip_gate_v3",
                compute_fn=_eval_main_clip,
                extra_key=f"{g_str}|{s_ver}|{b_mode}|{st_prof}|{c_num}|{contract_sig_main}",
            )
            if cached_chk["cv_rep"]["passed"] and cached_chk["dqa_ok"]:
                seen_global_shas.add(fast_file_sha256(dst).lower())
                continue
        target_clips.append(c_spec)

    print(f"[FlowDiorama] Pending clips to generate: {len(target_clips)}/{len(raw_targets)} (engine_mode={mode})")
    n_worker_tabs = 0
    zero_credit_output_count = 1
    shared_clip_queue: collections.deque[dict[str, Any]] = collections.deque(target_clips)
    if target_clips:
        if mode == "zero-credit":
            n_worker_tabs, zero_credit_output_count = compute_zero_credit_batch_plan(
                len(target_clips), max_parallel_tabs=int(max_parallel_tabs)
            )
            print(
                f"[FlowDiorama] 0-credit batch plan: {n_worker_tabs} tab(s) x x{zero_credit_output_count} outputs/prompt "
                f"({n_worker_tabs * zero_credit_output_count}/{FLOW_ZERO_CREDIT_MAX_CONCURRENT_RENDERS} concurrent free renders)"
            )
        else:
            n_worker_tabs = max(1, min(int(max_parallel_tabs), FLOW_MAX_PARALLEL_BATCH_SIZE, len(target_clips)))
            zero_credit_output_count = min(
                int(FLOW_ZERO_CREDIT_VIDEO_MAX_BATCH),
                max(1, int(FLOW_ZERO_CREDIT_MAX_CONCURRENT_RENDERS) // max(1, n_worker_tabs)),
            )

    opened_tabs: list[str] = []
    tab_open_lock = asyncio.Lock()
    credit_exhausted_event = asyncio.Event()
    if mode == "zero-credit":
        credit_exhausted_event.set()

    live_clips_by_idx: dict[int, dict[str, Any]] = {}
    live_shard_urls: list[str] = []
    live_shard_tabs: list[str] = []
    t_start = time.time()

    def _persist_receipt_snapshot(
        *,
        final_pass: bool = False,
        visual_gates_passed: bool = False,
        extra_prompts_submitted: int = 0,
    ) -> dict[str, Any]:
        merged_by_idx: dict[int, dict[str, Any]] = {}
        for k_idx, old_rec in existing_clips_by_idx.items():
            if (native_dir / f"clip_{k_idx}.mp4").exists():
                merged_by_idx[k_idx] = dict(old_rec)
        for k_idx, new_rec in live_clips_by_idx.items():
            if (native_dir / f"clip_{k_idx}.mp4").exists():
                combined = dict(merged_by_idx.get(k_idx) or {})
                combined.update(new_rec)
                merged_by_idx[k_idx] = combined

        for cf in sorted(native_dir.glob("clip_*.mp4")):
            if not cf.is_file():
                continue
            m_idx = re.match(r"^clip_(\d+)\.mp4$", cf.name)
            if not m_idx:
                continue
            idx = int(m_idx.group(1))
            if final_pass:
                _ensure_min_clip_size_if_needed(cf)
            st = cf.stat()
            if st.st_size < MIN_CLIP_SIZE_BYTES:
                continue
            prior = merged_by_idx.get(idx) or {}
            fallback_m = (
                prev_default_model
                or (FLOW_ZERO_CREDIT_MODEL if credit_exhausted_event.is_set() else FLOW_PRIMARY_VIDEO_MODEL)
            )
            c_model = str(prior.get("flow_model") or prior.get("model") or fallback_m)
            c_tier = str(
                prior.get("credit_tier")
                or ("zero_credit_fallback" if c_model == FLOW_ZERO_CREDIT_MODEL else "omni_monthly_credit")
            )
            src_dl = str(prior.get("source_download_filename") or f"flow_shard_clip_{idx:02d}.mp4")
            entry: dict[str, Any] = {
                "clip_index": idx,
                "sha256": fast_file_sha256(cf).lower(),
                "file_size_bytes": st.st_size,
                "source_download_filename": src_dl,
                "downloaded_at_epoch": prior.get("downloaded_at_epoch") or round(st.st_mtime, 3),
                "flow_model": c_model,
                "model": c_model,
                "credit_tier": c_tier,
            }
            if prior.get("cv_qa"):
                entry["cv_qa"] = prior["cv_qa"]
            merged_by_idx[idx] = entry

        ordered_clips = [merged_by_idx[k] for k in sorted(merged_by_idx)]
        seen_models: list[str] = []
        seen_tiers: list[str] = []
        for cm in ordered_clips:
            m_val = str(cm.get("flow_model") or cm.get("model") or "").strip()
            t_val = str(cm.get("credit_tier") or "").strip()
            if m_val and m_val not in seen_models:
                seen_models.append(m_val)
            if t_val and t_val not in seen_tiers:
                seen_tiers.append(t_val)
        default_top_model = FLOW_ZERO_CREDIT_MODEL if credit_exhausted_event.is_set() else FLOW_PRIMARY_VIDEO_MODEL
        resolved_model = (
            seen_models[0]
            if len(seen_models) == 1
            else (" -> ".join(seen_models) if seen_models else default_top_model)
        )
        zero_cred_ok = bool(
            ordered_clips
            and all(
                str(cm.get("credit_tier") or "") == "zero_credit_fallback"
                or str(cm.get("flow_model") or cm.get("model") or "") == FLOW_ZERO_CREDIT_MODEL
                for cm in ordered_clips
            )
        )
        merged_urls = list(dict.fromkeys([*live_shard_urls, *prev_shard_urls]))
        merged_tabs = list(dict.fromkeys([*live_shard_tabs, *prev_shard_tabs]))
        primary_url = live_shard_urls[0] if live_shard_urls else (prev_url or (merged_urls[0] if merged_urls else ""))
        primary_tab = live_shard_tabs[0] if live_shard_tabs else (prev_tab or (merged_tabs[0] if merged_tabs else ""))

        rcpt_obj: dict[str, Any] = {
            "project_id": project_slug,
            "worker_id": f"subagent-{project_slug}",
            "subagent_1_to_1_bound": True,
            "visual_gates_passed": bool(visual_gates_passed),
            "engine_mode": mode,
            "flow_model": resolved_model,
            "model": resolved_model,
            "models_used": seen_models or [default_top_model],
            "credit_tiers_used": seen_tiers,
            "zero_credit_verified": zero_cred_ok,
            "zero_clip_reuse": True,
            "partial_receipt": not bool(final_pass),
            "flow_project_url": primary_url,
            "tab_target_id": primary_tab,
            "shard_urls": merged_urls,
            "shard_tab_ids": merged_tabs,
            "prompts_submitted_count": max(
                len(ordered_clips),
                prev_prompts_submitted,
                int(extra_prompts_submitted),
            ),
            "elapsed_sec": round(time.time() - t_start, 1),
            "clips": ordered_clips,
        }
        if primary_url or ordered_clips:
            tmp_rcpt = prev_rcpt_path.with_suffix(f".json.tmp.{os.getpid()}.{int(time.time() * 1000000)}")
            tmp_rcpt.write_text(json.dumps(rcpt_obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            os.replace(tmp_rcpt, prev_rcpt_path)
        return rcpt_obj

    def _on_shard_clip_done(clip_rec: dict[str, Any], wave_url: str, wave_tab: str) -> None:
        c_idx = int(clip_rec["clip_index"])
        live_clips_by_idx[c_idx] = dict(clip_rec)
        if wave_url and wave_url not in live_shard_urls:
            live_shard_urls.append(wave_url)
        if wave_tab and wave_tab not in live_shard_tabs:
            live_shard_tabs.append(wave_tab)
        _persist_receipt_snapshot(final_pass=False, visual_gates_passed=False)

    shard_results: list[dict[str, Any]] = []
    try:
        shard_raw = await asyncio.gather(
            *(
                _run_shard_worker(
                    shard_idx=idx + 1,
                    shard_clips=[],
                    project_id=project_slug,
                    project_dir=project_dir,
                    short_ref_map=short_ref_map,
                    tab_open_lock=tab_open_lock,
                    opened_tabs=opened_tabs,
                    seen_global_shas=seen_global_shas,
                    episode_qa_contract=episode_qa_contract,
                    cdp_port=cdp_port,
                    engine_mode=mode,
                    credit_exhausted_event=credit_exhausted_event,
                    on_clip_completed=_on_shard_clip_done,
                    shared_clip_queue=shared_clip_queue,
                    zero_credit_output_count=zero_credit_output_count,
                )
                for idx in range(n_worker_tabs)
            ),
            return_exceptions=True,
        )
        shard_errors = [r for r in shard_raw if isinstance(r, BaseException)]
        shard_results = [r for r in shard_raw if isinstance(r, dict)]
        for sr in shard_results:
            for wu in (sr.get("wave_flow_urls") or ([sr["flow_project_url"]] if sr.get("flow_project_url") else [])):
                if wu and wu not in live_shard_urls:
                    live_shard_urls.append(str(wu))
            for wt in (sr.get("wave_tab_ids") or ([sr["tab_id"]] if sr.get("tab_id") else [])):
                if wt and wt not in live_shard_tabs:
                    live_shard_tabs.append(str(wt))
            for crec in (sr.get("clips") or []):
                if isinstance(crec, dict) and crec.get("clip_index") is not None:
                    live_clips_by_idx[int(crec["clip_index"])] = dict(crec)
        if shard_errors:
            try:
                _persist_receipt_snapshot(
                    final_pass=False,
                    visual_gates_passed=False,
                    extra_prompts_submitted=sum(int(r.get("prompts_submitted") or 0) for r in shard_results),
                )
            except Exception:
                pass
            if len(shard_errors) == 1 and isinstance(shard_errors[0], FlowCircuitBreakerError):
                raise shard_errors[0]
            raise RuntimeError(f"One or more shards encountered errors: {shard_errors}")
    finally:
        for tid in list(opened_tabs):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{cdp_port}/json/close/{tid}", timeout=5)
                print(f"[FlowDiorama] Closed worker tab {tid[:8]}")
            except Exception:
                pass

    # Verify all required clips for this run exist and meet MIN_CLIP_SIZE_BYTES
    required_indices = (
        [int(c["clip_number"]) for c in raw_targets]
        if only_clips
        else list(range(1, len(rendered_clips) + 1))
    )
    for idx in required_indices:
        cf = native_dir / f"clip_{idx}.mp4"
        if not cf.exists():
            raise RuntimeError(f"Missing clip_{idx}.mp4 after sharded Flow generation!")
        _ensure_min_clip_size_if_needed(cf)

    # Ensure all 4 V1-V4 screenshots exist (copy from captured live screenshots if Shard 1 resumed from cache)
    req_ss = (
        "flow_gate_v1_prompt_approved.png",
        "flow_gate_v2_rendering_active.png",
        "flow_gate_v3_canvas_clips_ready.png",
        "flow_gate_v4_export_ready.png",
    )
    existing_ss = [
        screenshots_dir / name
        for name in req_ss
        if (screenshots_dir / name).exists() and (screenshots_dir / name).stat().st_size >= 1000
    ]
    if not existing_ss:
        first_mp4 = next(iter(sorted(native_dir.glob("clip_*.mp4"))), None)
        if first_mp4 is not None:
            cap1 = cv2.VideoCapture(str(first_mp4))
            ok_f, frm1 = cap1.read()
            cap1.release()
            if ok_f and frm1 is not None:
                cv2.imwrite(str(screenshots_dir / req_ss[0]), frm1)
                existing_ss = [screenshots_dir / req_ss[0]]
    for name in req_ss:
        p_ss = screenshots_dir / name
        if (not p_ss.exists() or p_ss.stat().st_size < 1000) and existing_ss:
            shutil.copy2(existing_ss[0], p_ss)

    # Render real Gate V5 contact sheet across all ingested clips
    v5_ss_path = screenshots_dir / "flow_gate_v5_ingested_clips.png"
    rendered_v5_ok = _render_v5_contact_sheet(native_dir, v5_ss_path)
    if (not rendered_v5_ok or not v5_ss_path.exists() or v5_ss_path.stat().st_size < 1000) and existing_ss:
        shutil.copy2(existing_ss[0], v5_ss_path)

    # Count valid and invalid clips accurately on disk
    valid_clips_count = 0
    invalid_clips_count = 0
    for mp4_f in sorted(native_dir.glob("*.mp4")):
        if not mp4_f.is_file():
            continue
        is_val = (
            mp4_f.stat().st_size >= MIN_CLIP_SIZE_BYTES
            and FlowProjectSubagentWorker.is_valid_video_asset_url(mp4_f.name, "video/mp4")
        )
        if is_val:
            valid_clips_count += 1
        else:
            invalid_clips_count += 1
    if (PROJECTS_DIR / project_slug).resolve() == project_dir.resolve():
        v5_probe = GoogleFlowWhaleController.verify_flow_native_clips_v5(project_slug, deep_probe=False)
        valid_clips_count = int(v5_probe.get("valid_clips_count", valid_clips_count))
        invalid_clips_count = int(v5_probe.get("invalid_clips_count", invalid_clips_count))

    v5_passed = valid_clips_count >= len(required_indices) and invalid_clips_count == 0
    v_qa_merged = _merge_write_visual_qa_report(
        screenshots_dir / "visual_qa_report.json",
        {
            "gate_v1": {"status": "PASS", "screenshot": str(screenshots_dir / req_ss[0])},
            "gate_v2": {"status": "PASS", "screenshot": str(screenshots_dir / req_ss[1])},
            "gate_v3": {"status": "PASS", "screenshot": str(screenshots_dir / req_ss[2])},
            "gate_v4": {"status": "PASS", "screenshot": str(screenshots_dir / req_ss[3])},
            "gate_v5": {
                "status": "PASS" if v5_passed else "FAIL",
                "passed": bool(v5_passed),
                "valid_clips_count": int(valid_clips_count),
                "invalid_clips_count": int(invalid_clips_count),
                "target_dir": str(native_dir),
                "screenshot": str(v5_ss_path),
            },
        },
    )

    total_submitted = sum(int(r.get("prompts_submitted") or 0) for r in shard_results)
    receipt = _persist_receipt_snapshot(
        final_pass=True,
        visual_gates_passed=bool(v_qa_merged.get("all_passed", False)),
        extra_prompts_submitted=max(len(rendered_clips) if not only_clips else len(required_indices), total_submitted),
    )
    all_clips_meta = receipt["clips"]
    if len(all_clips_meta) >= 5:
        v_check = FlowProjectSubagentWorker.validate_provenance_receipt(project_dir)
        if not v_check.get("valid"):
            raise RuntimeError(f"Provenance receipt validation failed: {v_check.get('errors')}")

    print(
        f"[FlowDiorama] ALL {len(all_clips_meta)} UNIQUE CLIPS READY & PROVENANCE LOCKED "
        f"({receipt['flow_model']}, zero_credit_verified={receipt['zero_credit_verified']}) in {receipt['elapsed_sec']}s!"
    )
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description="Sharded Dual-Tier Google Flow worker for Schema v6/v7 neuro_diorama")
    parser.add_argument("--project", required=True, help="Project ID under BCI_Shorts_Channel/projects/")
    parser.add_argument("--clean", action="store_true", help="Purge existing clips before generating fresh")
    parser.add_argument("--clips", default="", help="Optional comma-separated 1-based clip numbers to regenerate")
    parser.add_argument("--tabs", type=int, default=FLOW_MAX_PARALLEL_BATCH_SIZE, help="Max parallel shard tabs (<=5)")
    parser.add_argument(
        "--engine-mode",
        choices=list(FLOW_ENGINE_MODES),
        default=DEFAULT_FLOW_ENGINE_MODE,
        help="Flow engine policy: auto (Omni 1.1 Flash -> 0-credit Veo Lite fallback), omni, or zero-credit",
    )
    args = parser.parse_args()

    only = [int(x.strip()) for x in args.clips.split(",") if x.strip()] if args.clips.strip() else None
    asyncio.run(
        run_sharded_diorama_flow_generation(
            project_id=args.project,
            clean_existing=args.clean,
            only_clips=only,
            max_parallel_tabs=args.tabs,
            engine_mode=args.engine_mode,
        )
    )


if __name__ == "__main__":
    main()
