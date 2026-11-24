"""ALL ABOUT BRAIN — Multimodal QA, Prosody & Loudness Constants (`config_qa.py`)."""

from __future__ import annotations
import os
import sys as _sys_cfg
import tempfile
from pathlib import Path
from typing import Any
from pipeline.config_paths import *
from pipeline.config_flow import *

UNMANNED_QA_SIGNOFF_DEFAULT = False                       # R85: semantic review must be a real VLM/human visual sign-off
REF_IMAGE_HUMAN_SKIN_MAX = 0.12          # Maximum allowed human flesh-tone ratio in mannequin head/body zone
REF_IMAGE_MIN_DHASH_DISTANCE = 6         # Q10: two clip keyframes closer than this (64-bit dHash) are duplicates
DIORAMA_TARGET_LUFS = -15.5
EXPRESSIVE_V8_TARGET_LUFS = -14.0
EXPRESSIVE_V8_PROSODY_MODE = "expressive_us_v8"
EXPRESSIVE_V8_PROSODY_BASE_RATE = "+10%"
EXPRESSIVE_V8_PROSODY_GEAR_RATES: dict[str, str] = {
    "rush": "+14%",
    "brisk": "+10%",
    "stamp": "+4%",
    "surprised_lift": "+6%",
    "insider_reveal": "+4%",
    "hushed_suspense": "+2%",
    "deadpan_drop": "-2%",
}
EXPRESSIVE_V8_PROSODY_GEARS: dict[str, dict[str, float]] = {
    "rush": {"tempo": 1.14, "trim_thresh": 0.06, "trim_keep": 0.02, "gap_before": 0.32},
    "brisk": {"tempo": 1.10, "trim_thresh": 0.10, "trim_keep": 0.035, "gap_before": 0.36},
    "stamp": {"tempo": 1.04, "trim_thresh": 0.14, "trim_keep": 0.05, "gap_before": 0.45},
    "surprised_lift": {"tempo": 1.06, "trim_thresh": 0.08, "trim_keep": 0.03, "gap_before": 0.32},
    "insider_reveal": {"tempo": 1.04, "trim_thresh": 0.09, "trim_keep": 0.03, "gap_before": 0.34},
    "hushed_suspense": {"tempo": 1.02, "trim_thresh": 0.10, "trim_keep": 0.035, "gap_before": 0.36},
    "deadpan_drop": {"tempo": 0.98, "trim_thresh": 0.12, "trim_keep": 0.04, "gap_before": 0.40},
}
PROSODY_P11_F0_SPAN_MIN_ST = 6.5
PROSODY_P11_LIFT_VS_DROP_MIN_ST = 1.2
EXPRESSIVE_V8_R77N_PROSODY_GEARS: dict[str, dict[str, float]] = {
    "rush": {"tempo": 1.14, "trim_thresh": 0.06, "trim_keep": 0.02, "gap_before": 0.16},
    "brisk": {"tempo": 1.10, "trim_thresh": 0.09, "trim_keep": 0.03, "gap_before": 0.18},
    "stamp": {"tempo": 1.04, "trim_thresh": 0.12, "trim_keep": 0.04, "gap_before": 0.22},
    "surprised_lift": {"tempo": 1.06, "trim_thresh": 0.08, "trim_keep": 0.03, "gap_before": 0.18},
    "insider_reveal": {"tempo": 1.04, "trim_thresh": 0.08, "trim_keep": 0.03, "gap_before": 0.18},
    "hushed_suspense": {"tempo": 1.02, "trim_thresh": 0.10, "trim_keep": 0.035, "gap_before": 0.20},
    "deadpan_drop": {"tempo": 0.98, "trim_thresh": 0.11, "trim_keep": 0.04, "gap_before": 0.22},
}
PORCELAIN_V7_HUMAN_SKIN_MAX = 0.14              # Max HSV+YCrCb flesh-tone ratio on porcelain hands/closeup clips
DIORAMA_V7_PROSODY_MODES: tuple[str, ...] = (
    "uniform_108x",
    "uniform_110x",
    "dynamic_rush_v7",
    "dynamic_us_v7",
    "expressive_us_v8",
)
DIORAMA_V7_PROSODY_MODE = "dynamic_us_v7"       # Channel default (US 45+ ear-first dynamic_us_v7); legacy Public 01..07 preserve dynamic_rush_v7
DIORAMA_V7_US_PROSODY_MODE = "dynamic_us_v7"   # US 45+ ear-first documentary prosody (~162-174 WPM: rush +10% / brisk +7% / stamp +4%)
DIORAMA_V7_PROSODY_BASE_RATE = "+8%"           # dynamic_rush_v7 synthesizes once at the approved +8% Silk Clean timbre
DIORAMA_V7_US_PROSODY_BASE_RATE = "+7%"        # dynamic_us_v7 base rate (+7% brisk baseline)
DIORAMA_V7_PROSODY_UNIFORM_110_RATE = "+10%"   # uniform_110x native edge-tts rate (no WSOLA post-processing)
DIORAMA_V7_PROSODY_UNIFORM_110: dict[str, float] = {
    "trim_thresh": 0.14,     # internal silences longer than this are compressed
    "trim_keep": 0.045,      # ... down to this
    "gap_before": 0.085,     # inserted gap before a regular sentence
    "stamp_gap_before": 0.17,  # inserted gap before a stamp sentence (acoustic ~0.25s incl. pads)
    "act_gap_before": 0.20,  # inserted gap at Act boundaries
}
DIORAMA_V7_PROSODY_GEARS: dict[str, dict[str, float]] = {
    "rush": {"tempo": 1.12, "trim_thresh": 0.06, "trim_keep": 0.02, "gap_before": 0.025},
    "stamp": {"tempo": 1.08, "trim_thresh": 0.16, "trim_keep": 0.06, "gap_before": 0.17},
    "brisk": {"tempo": 1.15, "trim_thresh": 0.12, "trim_keep": 0.04, "gap_before": 0.065},
}
DIORAMA_V7_US_PROSODY_GEARS: dict[str, dict[str, float]] = {
    "rush": {"tempo": 1.10, "trim_thresh": 0.06, "trim_keep": 0.02, "gap_before": 0.030},
    "stamp": {"tempo": 1.04, "trim_thresh": 0.16, "trim_keep": 0.06, "gap_before": 0.180},
    "brisk": {"tempo": 1.07, "trim_thresh": 0.12, "trim_keep": 0.045, "gap_before": 0.075},
}
DIORAMA_V7_PROSODY_GEAR_RATES: dict[str, str] = {"rush": "+12%", "stamp": "+8%", "brisk": "+15%"}
DIORAMA_V7_US_PROSODY_GEAR_RATES: dict[str, str] = {"rush": "+10%", "stamp": "+4%", "brisk": "+7%"}
DIORAMA_V7_PROSODY_SPLICE_FADE_SEC = 0.014       # Smooth 14ms raised-cosine edge fade (replaces 6ms hard gate)
DIORAMA_V7_PROSODY_ACT_GAP_MIN = 0.20          # Act boundary gap floor in dynamic_rush_v7
DIORAMA_V7_PROSODY_MAX_ADJ_TEMPO_JUMP = 0.05   # Max adjacent WSOLA factor jump when the inserted gap is < 0.10s
DIORAMA_V7_PROSODY_RUSH_MAX_STREAK = 3         # 4th consecutive rush sentence is demoted to brisk
DIORAMA_V7_PROSODY_EMPHASIS_PAUSE_SEC = 0.0    # 0.0s = zero mid-sentence digital zero-slicing (preserves co-articulation)
DIORAMA_V7_PROSODY_EMPHASIS_GAIN_DB = 1.0      # Smooth 25ms cosine emphasis contour lift without cutting connected speech
DIORAMA_V7_PROSODY_RUSH_CLIMAX_WORDS: tuple[str, ...] = ("yet", "then", "suddenly", "instead")
PROSODY_P1_FIRST_ONSET_MAX_SEC = 0.10
PROSODY_P2_HOOK_END_MAX_SEC = 9.0              # end of sentence 2 (recalibrated to the approved 3-sentence cold-open: HM Plan B S2 ends 8.4s)
PROSODY_P2_STAMP_END_MAX_SEC = 11.5            # end of sentence 3 when it is the case stamp (HM Plan B S3 ends 10.9s)
PROSODY_P3_TEMPO_TOLERANCE = 0.03              # applied tempo within +/-3% of the gear target
PROSODY_P4_RUSH_MAX_INTERNAL_SILENCE_SEC = 0.07  # 10ms RMS window quantization on a 0.06s trim threshold
PROSODY_P5_STAMP_PRE_SILENCE_RANGE: tuple[float, float] = (0.20, 0.32)
PROSODY_P6_ASR_MATCH_MIN = 0.95
PROSODY_P10_OPEN_LOOP_MAX_GAP_SEC = 35.0
REENACT_MIN_DHASH_DISTANCE = 18                # RQ2: min 64-bit dHash Hamming distance from sanitized/source frames
REAL_WORLD_REFS_MIN_DHASH_DISTANCE = 14
THUMB_V4_OVERLAY_MODE = "r65_v4_in_skull_split"
THUMB_V4_MIN_MEAN_LUMA = 105.0               # Bright high-key studio daylight floor on R65 v4 split covers (TQ3)
THUMB_V4_TARGET_MEAN_LUMA = 110.0            # Target bright studio daylight luma in R65 v4 prompt contract
THUMB_V4_MIN_ACTIVATION_DELTA = 0.015        # Bottom 50% red/cyan brain+arrow activation minus Top 50% dormant grey (TQ8)
THUMB_V4_TOP_LABEL_Y_RANGE: tuple[int, int] = (170, 390)    # 2:3 Shorts shelf-safe (y >= 150) upper-left Top 50% micro-label band (y ≈ 176)
THUMB_V4_BOT_LABEL_Y_RANGE: tuple[int, int] = (980, 1450)   # Clean upper-left Bottom 50% 2-3w micro-label band (y ≈ 1016)
THUMB_V4_BOTTOM_TITLE_SAFE_Y = 1520          # Bottom Shorts UI title zone (y >= 1520) strictly clear of text/labels (TQ4/TQ9)
THUMB_CANDIDATE_SAMPLES_PER_CUT = 3          # Sample offsets at 25 / 50 / 75 % of each eligible EDL cut
THUMB_EXCLUDE_MODES = ("split_hstack", "split_vstack")  # Split-screen cuts never become covers
THUMB_EXCLUDE_OUTRO = True                   # Exclude Act 6 outro sky card from thumbnail candidates
THUMB_SCORE_WEIGHTS = {
    "sharpness": 0.25,
    "contrast": 0.20,
    "colorfulness": 0.10,
    "center_salience": 0.25,
    "intent": 0.20,
}
THUMB_INTENT_BONUS = {
    "cover_sentence": 1.0,
    "cutaway_xray": 1.0,
    "brain_badge": 0.95,
    "act1": 0.6,
    "default": 0.0,
}
THUMB_SHORTS_SHELF_CROP_Y: tuple[int, int] = (150, 1770)  # True YouTube Shorts 2:3 (1080x1620) shelf crop band
THUMB_V8_Z_TOP_Y_RANGE: tuple[int, int] = (215, 395)      # Top-left Z-pattern hook band inside 2:3 shelf
THUMB_V8_Z_BOT_Y_RANGE: tuple[int, int] = (1240, 1445)    # Bottom-right Z-pattern hook band (< 1480px, above y=1520 title mask)
THUMB_POINTER_RED_RGB: tuple[int, int, int] = (255, 37, 37)     # #FF2525 3D vector arrow / dimension ruler accent
THUMB_POINTER_CYAN_RGB: tuple[int, int, int] = (0, 212, 255)    # #00D4FF glowing neural pathway / glass-brain accent
THUMB_ACCENT_YELLOW_RGB: tuple[int, int, int] = (255, 225, 74)  # #FFE14A high-visibility bottom-right hook fill
THUMB_MIN_SHARPNESS = 60.0                   # Laplacian variance floor at 540x960 (TQ3)
THUMB_MIN_LUMA_STD = 38.0                    # Global luminance standard deviation floor (TQ3)
THUMB_MIN_CENTER_SALIENCE = 1.15             # Centre 3:4 Canny edge density / border edge density floor (TQ2)
THUMB_MIN_PAIRWISE_DIFF = 15.0               # Pairwise mean abs pixel diff across A/B/C variants (R31 / TQ5)
THUMB_MIN_TEXT_CONTRAST = 4.5                # WCAG contrast ratio of hook fill vs local/stroke background at 160px shelf width (TQ1)
THUMB_LEGIBILITY_PREVIEW_W = 160             # Mobile Shorts shelf preview width in pixels (TQ1 & contact sheet)
THUMB_SAFE_Y_RANGE = (240, 1440)             # Inside centre 3:4 grid crop & above bottom 25% Shorts UI overlay (TQ4)
THUMB_SAFE_MARGIN_X = 80                     # Minimum left/right horizontal safe margin in pixels (TQ4)
THUMB_HOOK_MAX_WORDS = 4                     # Max words in thumbnail hook headline (TQ7)
THUMB_HOOK_MAX_CHARS = 18                    # Max characters in thumbnail hook headline (TQ7)
THUMB_HOOK_FONT_SIZE_RANGE = (150, 96)       # Auto-fit condensed black headline font size range (max, min)
THUMB_HOOK_STROKE_PX = 10                    # Dark outer stroke thickness on hook headline (replaces v6 navy box)
SHORTS_THUMB_MAX_BYTES = 1_950_000           # Maximum Shorts PNG byte size (< 2.00 MB YouTube Studio custom thumbnail ceiling, TQ6)
MAX_PERCEPTUAL_DHASH_HAMMING_DISTANCE = 10  # Clips across projects with dHash distance <= 10 are flagged as recycled clones
MIN_CLIP_SIZE_BYTES = 1_000_000          # Minimum 1 MB per MP4 clip (blocks thumbnails/empty files)
DEAD_AIR_FLOOR_SEC = 16.50               # Lower bound of the limit for videos longer than DEAD_AIR_SHORT_VIDEO_SEC
DEAD_AIR_DURATION_RATIO = 0.38           # Limit scales with duration: max(DEAD_AIR_FLOOR_SEC, duration x 0.38)
DEAD_AIR_SHORT_VIDEO_SEC = 31.0          # Videos at or below this length use DEAD_AIR_SHORT_VIDEO_MAX_SEC
DEAD_AIR_SHORT_VIDEO_MAX_SEC = 0.90
def max_allowed_dead_air_sec(duration_sec: float) -> float:
    """Cumulative internal dead-air limit (seconds) for an assembled Short of the given duration."""
    _cmod = _sys_cfg.modules.get('pipeline.config')
    DEAD_AIR_DURATION_RATIO = getattr(_cmod, 'DEAD_AIR_DURATION_RATIO', globals()['DEAD_AIR_DURATION_RATIO']) if _cmod is not None else globals()['DEAD_AIR_DURATION_RATIO']
    DEAD_AIR_FLOOR_SEC = getattr(_cmod, 'DEAD_AIR_FLOOR_SEC', globals()['DEAD_AIR_FLOOR_SEC']) if _cmod is not None else globals()['DEAD_AIR_FLOOR_SEC']
    DEAD_AIR_SHORT_VIDEO_MAX_SEC = getattr(_cmod, 'DEAD_AIR_SHORT_VIDEO_MAX_SEC', globals()['DEAD_AIR_SHORT_VIDEO_MAX_SEC']) if _cmod is not None else globals()['DEAD_AIR_SHORT_VIDEO_MAX_SEC']
    DEAD_AIR_SHORT_VIDEO_SEC = getattr(_cmod, 'DEAD_AIR_SHORT_VIDEO_SEC', globals()['DEAD_AIR_SHORT_VIDEO_SEC']) if _cmod is not None else globals()['DEAD_AIR_SHORT_VIDEO_SEC']
    if duration_sec > DEAD_AIR_SHORT_VIDEO_SEC:
        return max(DEAD_AIR_FLOOR_SEC, round(duration_sec * DEAD_AIR_DURATION_RATIO, 2))
    return DEAD_AIR_SHORT_VIDEO_MAX_SEC
AUDIO_SIBILANCE_BAND_HZ: tuple[float, float] = (4200.0, 9200.0)
AUDIO_MAX_SIBILANCE_ENERGY_RATIO = 0.62          # Max HF (4.2-9.2kHz) / mid-band RMS ratio on voiced windows before flagging harshness tear
AUDIO_MAX_SIBILANCE_CREST_DB = 32.0              # Max HF peak-to-RMS crest (dB) over active 50ms voiced windows
DIORAMA_V7_TARGET_LUFS = -15.5                   # Unified BS.1770 documentary loudness target (matches DIORAMA_TARGET_LUFS)
DIORAMA_LUFS_TOLERANCE_LU = 4.0                  # Accepted BS.1770 integrated LUFS window around target (-19.5..-11.5 LUFS)
R89_YUNET_SAMPLE_FPS: float = 5.0
R89_YUNET_FACE_SCORE_THRESHOLD: float = 0.42
