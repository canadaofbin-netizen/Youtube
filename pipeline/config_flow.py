"""ALL ABOUT BRAIN — Dual-Tier Google Flow Engine & Credit Constants (`config_flow.py`)."""

from __future__ import annotations
import os
import sys as _sys_cfg
import tempfile
from pathlib import Path
from typing import Any
from pipeline.config_paths import *

FLOW_ACTIVE_VIDEO_MODEL = "Omni 1.2 Flash"
FLOW_PRIMARY_VIDEO_MODEL = FLOW_ACTIVE_VIDEO_MODEL
FLOW_PRIMARY_OMNI_MODEL_LABEL = FLOW_PRIMARY_VIDEO_MODEL
FLOW_PRIMARY_OMNI_MODEL_KEY = "macaron_cookie"
FLOW_SECONDARY_OMNI_MODEL: str | None = None
FLOW_RETIRED_VIDEO_MODELS: tuple[str, ...] = (
    "Omni 1.1 Flash",
    "Omni 1.1 Quality",
    "Veo 3.1 - Fast",
    "Veo 3.1 - Quality",
)
FLOW_ZERO_CREDIT_MODEL = "Veo 3.1 - Lite [Lower Priority]"
FLOW_ENGINE_MODES: tuple[str, ...] = ("auto", "omni", "zero-credit")
DEFAULT_FLOW_ENGINE_MODE = "auto"
FLOW_BANNED_VIDEO_MODEL_MARKERS: tuple[str, ...] = ("Veo 2",)
FLOW_ZERO_CREDIT_TEXT = "Generating will use 0 credits"   # 0-credit verification marker when monthly credits are exhausted
FLOW_ZERO_CREDIT_IMAGE_MODEL = "Nano Banana 2.1"          # Google Flow native 0-credit Image engine (beluga_display)
FLOW_ZERO_CREDIT_IMAGE_FALLBACK_MODELS: tuple[str, ...] = (
    "Nano Banana 2.1",
    "Nano Banana Pro",
    "Nano Banana 2 Lite",
)
FLOW_ZERO_CREDIT_IMAGE_FAMILY_ID = "beluga_display"
FLOW_ZERO_CREDIT_IMAGE_BATCH_COUNT = 1                    # 1st-pass default: x1 (saves ~75-86% daily Flow image volume)
FLOW_ZERO_CREDIT_IMAGE_RETRY_BATCH_COUNT = 2              # Retry / Gate 1 rejected targeted regen: x2
FLOW_ZERO_CREDIT_IMAGE_THUMBNAIL_BATCH_COUNT = 2          # R65 v4 hero thumbnail keyart (1 prompt/ep): x2
FLOW_ZERO_CREDIT_MAX_CONCURRENT_RENDERS = 4               # Optimal 0-credit concurrent video render ceiling across Flow tabs/outputs
FLOW_ZERO_CREDIT_VIDEO_MAX_BATCH = 4                      # Up to x4 free candidate videos per prompt when active_tabs * batch <= 4
FLOW_ZERO_CREDIT_SAFE_PARALLEL_TABS = 2                   # Default safe 0-credit parallel tab cap to prevent 'unusual activity' lockouts
FLOW_ZERO_CREDIT_SUBMIT_JITTER_SEC: tuple[float, float] = (14.0, 22.0)  # Jittered inter-submit spacing across 0-credit tabs
FLOW_ZERO_CREDIT_PENALTY_QUIET_SEC = 75.0                 # Immediate cross-tab quiet window on first 'unusual activity' signal
FLOW_ZERO_CREDIT_RECOVERY_STREAK = 3                      # Consecutive clean 0-credit renders required to step back up from 1 -> 2 tabs
REENACT_IMAGE_BACKENDS: tuple[str, ...] = ("flow",)
DEFAULT_REENACT_IMAGE_BACKEND = "flow"                    # Locked: native Google Flow 0-credit x1 first-pass / x2 retry Image mode only
def resolve_flow_image_batch_count(
    batch_count: int | None = None,
    *,
    is_retry: bool = False,
    force: bool = False,
    retry_batch_count: int | None = None,
) -> int:
    """Resolves Google Flow 0-credit Image batch size: explicit override > retry/force x2 > 1st-pass x1."""
    _cmod = _sys_cfg.modules.get('pipeline.config')
    FLOW_ZERO_CREDIT_IMAGE_BATCH_COUNT = getattr(_cmod, 'FLOW_ZERO_CREDIT_IMAGE_BATCH_COUNT', globals()['FLOW_ZERO_CREDIT_IMAGE_BATCH_COUNT']) if _cmod is not None else globals()['FLOW_ZERO_CREDIT_IMAGE_BATCH_COUNT']
    FLOW_ZERO_CREDIT_IMAGE_RETRY_BATCH_COUNT = getattr(_cmod, 'FLOW_ZERO_CREDIT_IMAGE_RETRY_BATCH_COUNT', globals()['FLOW_ZERO_CREDIT_IMAGE_RETRY_BATCH_COUNT']) if _cmod is not None else globals()['FLOW_ZERO_CREDIT_IMAGE_RETRY_BATCH_COUNT']
    if batch_count is not None:
        return max(1, min(4, int(batch_count)))
    if is_retry or force:
        eff_retry = FLOW_ZERO_CREDIT_IMAGE_RETRY_BATCH_COUNT if retry_batch_count is None else int(retry_batch_count)
        return max(1, min(4, eff_retry))
    return max(1, min(4, int(FLOW_ZERO_CREDIT_IMAGE_BATCH_COUNT)))
FLOW_OMNI_CREDIT_COST_NO_REF = 24                         # Omni 1.2 Flash credit cost per 8s clip
FLOW_OMNI_CREDIT_COST_WITH_REF = 24                       # Omni 1.2 Flash credit cost with Start/End frame attached
FLOW_OMNI_EPISODE_CREDIT_CAP = 200                        # Default fallback per-episode Omni credit cap (dynamic balance override via compute_dynamic_omni_episode_budget)
FLOW_OMNI_BALANCE_SAFETY_MARGIN = 20                      # Safety reserve kept when computing real-time dynamic Omni episode budget (C3)
FLOW_OMNI_HERO_MAX_CLIPS = 8                              # Max hero cuts tagged engine="omni" per episode when budget is capped (Cuts 1-3 + core reveal + X-Ray brain + climax)
FLOW_OMNI_MAX_ATTEMPTS_PER_CLIP = 2                       # Max Omni attempts per clip (1 initial + 1 retry) before auto-demoting to 0-credit
FLOW_AUTO_CLEANUP_ON_SUCCESS = False                      # Keep cleanly named AAB_<project_id> rooms in Google Flow (never delete episode rooms!)
FLOW_OMNI_ENABLE_EXTENDED_DURATIONS = False               # Unlock 3s..15s (1s steps) when verified in Flow UI
FLOW_OMNI_EXTENDED_DURATIONS: tuple[str, ...] = tuple(f"{s}s" for s in range(3, 16))
FLOW_OMNI_EXTENDED_DURATION_CHOICES: tuple[int, ...] = tuple(range(3, 16))
FLOW_OMNI_ENABLE_NATIVE_1080P_DOWNLOAD = False            # Prefer More -> Download -> Upscaled (1080p) when verified in Flow UI
FLOW_OMNI_ENABLE_CONVERSATIONAL_EDIT = False              # Enable 1-turn Flow conversational edit repair before full regen
FLOW_OMNI_ENABLE_MULTI_INGREDIENTS_V83 = False            # Unlock up to 8 multi-ingredients + 3s Previs motion guide MP4
FLOW_OMNI_MAX_INGREDIENTS_V83 = 8
FLOW_ENABLE_720P_LANCZOS_UNSHARP = False                  # Optional 720p -> 1080p Lanczos + adaptive unsharp fallback
def compute_dynamic_omni_episode_budget(
    credits_remaining: int | None,
    clip_count: int = 20,
    cost_per_clip: int = FLOW_OMNI_CREDIT_COST_WITH_REF,
    safety_margin: int = FLOW_OMNI_BALANCE_SAFETY_MARGIN,
) -> dict[str, Any]:
    """
    Computes the real-time balance-based Omni credit budget and clip allocation for an episode (`C3`):
      `budget_credits = min(max(0, credits_remaining - safety_margin), clip_count * cost_per_clip)`.
    When `credits_remaining` is `None` (unprobed), uses `FLOW_OMNI_EPISODE_CREDIT_CAP`.
    """
    _cmod = _sys_cfg.modules.get('pipeline.config')
    FLOW_OMNI_BALANCE_SAFETY_MARGIN = getattr(_cmod, 'FLOW_OMNI_BALANCE_SAFETY_MARGIN', globals()['FLOW_OMNI_BALANCE_SAFETY_MARGIN']) if _cmod is not None else globals()['FLOW_OMNI_BALANCE_SAFETY_MARGIN']
    FLOW_OMNI_CREDIT_COST_WITH_REF = getattr(_cmod, 'FLOW_OMNI_CREDIT_COST_WITH_REF', globals()['FLOW_OMNI_CREDIT_COST_WITH_REF']) if _cmod is not None else globals()['FLOW_OMNI_CREDIT_COST_WITH_REF']
    FLOW_OMNI_EPISODE_CREDIT_CAP = getattr(_cmod, 'FLOW_OMNI_EPISODE_CREDIT_CAP', globals()['FLOW_OMNI_EPISODE_CREDIT_CAP']) if _cmod is not None else globals()['FLOW_OMNI_EPISODE_CREDIT_CAP']
    n_clips = max(0, int(clip_count))
    unit_cost = max(1, int(cost_per_clip))
    full_episode_cost = n_clips * unit_cost
    if credits_remaining is None:
        budget_credits = min(int(FLOW_OMNI_EPISODE_CREDIT_CAP), full_episode_cost)
    else:
        usable = max(0, int(credits_remaining) - max(0, int(safety_margin)))
        budget_credits = min(usable, full_episode_cost)
    max_omni = min(n_clips, budget_credits // unit_cost)
    return {
        "credits_remaining": credits_remaining,
        "budget_credits": int(budget_credits),
        "max_omni_clips": int(max_omni),
        "zero_credit_fallback_clips": max(0, n_clips - int(max_omni)),
        "all_omni_possible": bool(n_clips > 0 and max_omni >= n_clips),
    }
FLOW_TAB_OPEN_STAGGER_SEC = 2.5                           # Normal tab-creation stagger across parallel shards (<30m target)
FLOW_TAB_OPEN_COOLDOWN_STAGGER_SEC = 12.0                 # Elevated tab-creation stagger after a rate-limit cooldown
FLOW_SUBMIT_STAGGER_SEC = 3.0                             # Normal prompt-submit stagger across parallel shards (<30m target)
FLOW_SUBMIT_COOLDOWN_STAGGER_SEC = 9.5                    # Elevated prompt-submit stagger after a rate-limit cooldown
FLOW_ALLOWED_DURATION_TARGETS: tuple[str, ...] = tuple(FLOW_VIDEO_MODEL_PROFILES[FLOW_ACTIVE_VIDEO_MODEL]["durations"])
FLOW_CLIP_DURATION_TARGET = "10s"        # Omni, no ingredient; clamps to 8s automatically when an ingredient is attached
FLOW_SHORT_CLIP_MAX_WORDS = 19           # Clips <= 19 words & <= 32 syllables dynamically route to "8s"
FLOW_SHORT_CLIP_MAX_SYLLABLES = 32
FLOW_CLIP_SAFE_MAX_SYLLABLES = 48        # Ceiling above which 10s Omni clips risk tail speech truncation (native voice only)
FLOW_CLIP_TARGET_SEC_MIN = 8.0           # Target native Flow clip length (prompt design)
FLOW_PROMPT_PREFIX = (
    "Generate a 9:16 vertical video clip (video animation with spoken voiceover only, never a static image):"
)
ALLOWED_FLOW_MODELS = ["Omni 1.2 Flash", "Veo 3.1 - Lite [Lower Priority]"]
FLOW_MODELS = {
    "Omni 1.2 Flash": "Omni 1.2 Flash - Flagship high-throughput multimodal video engine (Ingredients 3s-15s & Start+End Frames 3s-10s; Default)",
    "Veo 3.1 - Lite [Lower Priority]": "Veo 3.1 - Lite [Lower Priority] - Unlimited 0-credit Google AI Ultra fallback (4s/6s/8s; Start+End supported)",
}
FLOW_MODEL_DESCRIPTIONS = FLOW_MODELS
FLOW_DEFAULT_VOICE = "Puck"
FLOW_VOICE_PROMPT_DESCRIPTOR = "Consistent deep male baritone documentary narrator"
FLOW_VOICE_PROMPT_DESCRIPTOR_V5 = (
    "Same calm male documentary narrator in every clip, warm mid-low baritone, steady even pitch, "
    "relaxed measured pace, neutral American accent, no dramatic pitch swings"
)
FLOW_LEGACY_VOICE_LABELS: tuple[str, ...] = (
    FLOW_VOICE_PROMPT_DESCRIPTOR,
    "Deep male baritone documentary narrator",
)
FLOW_ASPECT_SHORTS = "9:16"
FLOW_ASPECT_LABELS: dict[str, str] = {"9:16": "9:16 vertical", "16:9": "16:9 horizontal"}
FLOW_MOTION_STYLE_V5 = (
    "Articulated matte-white porcelain figures move with fluid, natural human motion; "
    "key action stays centred in frame."
)
R85_FLOW_BRAIN_SHOT_ROTATION: tuple[str, ...] = (
    "xray_head_dive",
    "split_cutaway",
    "sulcal_cyan_dive",
    "vessel_csf_macro",
    "1p_tract_canyon",
    "3p_shutdown_or_top_bottom",
)
GOOGLE_FLOW_URL = "https://labs.google/fx/tools/flow"
FLOW_MAX_PARALLEL_BATCH_SIZE = 5         # Strict 1:1:1 Subagent cap: max 5 topics per batch
FLOW_MAX_RETRIES = 2                     # Hard cap: max 2 retries before circuit breaker trips
FLOW_TRIGGER_VERIFY_TIMEOUT_SEC = 5.0    # Must verify UI entered generating state within 5s of click
FLOW_RENDER_POLL_INTERVAL_SEC = 10.0     # Poll <video> readyState & download button every 10s
FLOW_RENDER_TIMEOUT_SEC = 210.0          # Asynchronous rendering timeout (180-240s range)
FLOW_CLIP_DURATION_MIN_SEC = 3.0         # Minimum valid duration for a Google Flow clip
FLOW_CLIP_DURATION_MAX_SEC = 15.0        # Maximum valid duration for a single Google Flow clip
MIN_OPTICAL_FLOW_THRESHOLD = 0.12        # Minimum Farneback optical flow magnitude
