"""
ALL ABOUT BRAIN - Voice consistency gate (R49).

Google Flow re-creates the narrator for every clip, so per-clip pitch can drift (measured spreads of 53-113 Hz
in delivered projects). This module judges consistency in semitones (perceptual), picks the clips to regenerate,
and never corrects pitch by shifting (user preference: natural, unshifted voice).
"""

from __future__ import annotations

import math
from statistics import median
from typing import Any

from pipeline.config import (
    PUCK_F0_RANGE_HZ,
    VOICE_F0_ADJ_JUMP_MAX_ST,
    VOICE_F0_CLIP_DEV_MAX_ST,
    VOICE_F0_SPREAD_MAX_ST,
)


def semitones(f_a: float, f_b: float) -> float:
    """Signed interval from f_b to f_a in semitones."""
    if f_a <= 0 or f_b <= 0:
        return 0.0
    return 12.0 * math.log2(float(f_a) / float(f_b))


def evaluate_f0_series(f0_hz: list[float]) -> dict[str, Any]:
    """
    Per-clip median F0 series -> semitone metrics, pass/fail and the clip numbers (1-based) to regenerate.
    Outliers: unvoiced/invalid clips (f0 <= 0.0), clips outside PUCK_F0_RANGE_HZ, clips deviating
    > VOICE_F0_CLIP_DEV_MAX_ST from the project median; if only an adjacent jump / spread fails,
    the clip of the worst pair farther from the median.
    """
    vals = [float(f) for f in f0_hz]
    if not vals:
        return {
            "passed": False,
            "reason": "no F0 values",
            "unvoiced_outliers": [],
            "regenerate_clips": [],
        }

    unvoiced_outliers = sorted(i + 1 for i, f in enumerate(vals) if not math.isfinite(f) or f <= 0.0)
    voiced_vals = [f for f in vals if math.isfinite(f) and f > 0.0]
    limits_st = {
        "clip_dev": VOICE_F0_CLIP_DEV_MAX_ST,
        "adjacent_jump": VOICE_F0_ADJ_JUMP_MAX_ST,
        "spread": VOICE_F0_SPREAD_MAX_ST,
    }
    if not voiced_vals:
        return {
            "passed": False,
            "reason": "no valid voiced F0 values",
            "project_f0_median_hz": 0.0,
            "clip_f0_hz": [round(v, 1) if math.isfinite(v) else 0.0 for v in vals],
            "clip_deviation_st": [None for _ in vals],
            "adjacent_jump_st": [None for _ in range(max(0, len(vals) - 1))],
            "max_adjacent_jump_st": None,
            "spread_st": None,
            "limits_st": limits_st,
            "unvoiced_outliers": unvoiced_outliers,
            "regenerate_clips": unvoiced_outliers,
        }

    lo, hi = PUCK_F0_RANGE_HZ
    in_band = [f for f in voiced_vals if lo <= f <= hi] or voiced_vals
    med = float(median(in_band))
    dev: list[float | None] = [
        round(semitones(f, med), 2) if (math.isfinite(f) and f > 0.0) else None
        for f in vals
    ]
    jumps: list[float | None] = [
        round(abs(semitones(vals[k + 1], vals[k])), 2)
        if (math.isfinite(vals[k]) and vals[k] > 0.0 and math.isfinite(vals[k + 1]) and vals[k + 1] > 0.0)
        else None
        for k in range(len(vals) - 1)
    ]
    voiced_jumps = [j for j in jumps if j is not None]
    spread = round(semitones(max(voiced_vals), min(voiced_vals)), 2) if len(voiced_vals) > 1 else 0.0

    outliers: set[int] = set(unvoiced_outliers)
    outliers |= {i + 1 for i, f in enumerate(vals) if math.isfinite(f) and f > 0.0 and not (lo <= f <= hi)}
    outliers |= {i + 1 for i, d in enumerate(dev) if d is not None and abs(d) > VOICE_F0_CLIP_DEV_MAX_ST}
    max_jump = max(voiced_jumps, default=0.0)
    if not outliers and (max_jump > VOICE_F0_ADJ_JUMP_MAX_ST or spread > VOICE_F0_SPREAD_MAX_ST):
        if max_jump > VOICE_F0_ADJ_JUMP_MAX_ST:
            k = jumps.index(max_jump)
            d_k = abs(dev[k]) if dev[k] is not None else 0.0
            d_next = abs(dev[k + 1]) if dev[k + 1] is not None else 0.0
            outliers.add(k + 1 if d_k >= d_next else k + 2)
        else:
            outliers.add(max(range(len(dev)), key=lambda i: abs(dev[i]) if dev[i] is not None else -1.0) + 1)
    passed = (
        not unvoiced_outliers
        and not outliers
        and max_jump <= VOICE_F0_ADJ_JUMP_MAX_ST
        and spread <= VOICE_F0_SPREAD_MAX_ST
    )
    return {
        "passed": passed,
        "project_f0_median_hz": round(med, 1),
        "clip_f0_hz": [round(v, 1) if math.isfinite(v) else 0.0 for v in vals],
        "clip_deviation_st": dev,
        "adjacent_jump_st": jumps,
        "max_adjacent_jump_st": max_jump,
        "spread_st": spread,
        "limits_st": limits_st,
        "unvoiced_outliers": unvoiced_outliers,
        "regenerate_clips": sorted(outliers),
    }
