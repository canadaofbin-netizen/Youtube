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
    Outliers: clips outside PUCK_F0_RANGE_HZ, clips deviating > VOICE_F0_CLIP_DEV_MAX_ST from the project
    median; if only an adjacent jump / spread fails, the clip of the worst pair farther from the median.
    """
    vals = [float(f) for f in f0_hz]
    if not vals:
        return {"passed": False, "reason": "no F0 values", "regenerate_clips": []}
    lo, hi = PUCK_F0_RANGE_HZ
    in_band = [f for f in vals if lo <= f <= hi] or vals
    med = float(median(in_band))
    dev = [round(semitones(f, med), 2) for f in vals]
    jumps = [round(abs(semitones(vals[k + 1], vals[k])), 2) for k in range(len(vals) - 1)]
    spread = round(semitones(max(vals), min(vals)), 2) if len(vals) > 1 else 0.0
    outliers = {i + 1 for i, f in enumerate(vals) if not (lo <= f <= hi)}
    outliers |= {i + 1 for i, d in enumerate(dev) if abs(d) > VOICE_F0_CLIP_DEV_MAX_ST}
    max_jump = max(jumps, default=0.0)
    if not outliers and (max_jump > VOICE_F0_ADJ_JUMP_MAX_ST or spread > VOICE_F0_SPREAD_MAX_ST):
        if max_jump > VOICE_F0_ADJ_JUMP_MAX_ST:
            k = jumps.index(max_jump)
            outliers.add(k + 1 if abs(dev[k]) >= abs(dev[k + 1]) else k + 2)
        else:
            outliers.add(max(range(len(dev)), key=lambda i: abs(dev[i])) + 1)
    passed = (
        not outliers
        and max_jump <= VOICE_F0_ADJ_JUMP_MAX_ST
        and spread <= VOICE_F0_SPREAD_MAX_ST
    )
    return {
        "passed": passed,
        "project_f0_median_hz": round(med, 1),
        "clip_f0_hz": [round(v, 1) for v in vals],
        "clip_deviation_st": dev,
        "adjacent_jump_st": jumps,
        "max_adjacent_jump_st": max_jump,
        "spread_st": spread,
        "limits_st": {
            "clip_dev": VOICE_F0_CLIP_DEV_MAX_ST,
            "adjacent_jump": VOICE_F0_ADJ_JUMP_MAX_ST,
            "spread": VOICE_F0_SPREAD_MAX_ST,
        },
        "regenerate_clips": sorted(outliers),
    }
