"""
ALL ABOUT BRAIN — Schema v7 / v6 Neuro-Diorama 3-Minute Long-Short Assembler (R58, R59, R63, R64).

Assembles Neuro-Diorama 3-minute Long-Shorts in 100% US English (`en-US`):
  - Default Schema v7 (`lowpoly_pastel_v7`, R63/R64): Continuous `edge-tts` (`en-US-AndrewMultilingualNeural`,
    unified `+8%` / `1.08x`, `+14Hz` high-tenor pitch, `-10%` tear-free Silk Clean EQ, `kokoro-onnx` fallback) natural breath-trimmed master clock (`140.0-179.0s`),
    `24.0fps` (`1.00x`) 1:1 Zero-Reuse low-poly cuts (`hstack` split comparisons), bundled
    `AABCondensed-Black.ttf` frame-grid subtitles + giant chapter headlines + `AnatomyLabel` badges, and
    2-channel stereo documentary score (`-21 dB` ducking) linearly normalized to `-15.5 LUFS` (`TP <= -1.8 dBFS`).
  - Legacy Schema v6 (`neuro_diorama`, R58/R59): Continuous storyteller master clock (`170.0-179.0s`),
    `30.0fps` 1:1 / NLE Cross-Cut EDL, pure-white (`#FFFFFF`) 1-line hard-cut ASS subtitles at `MarginV=650`
    (`Y≈64%`), top callouts, final `2.2s` title card, and `88 BPM` documentary pulse BGM (`-24 dB` ducking).
"""
from __future__ import annotations
import hashlib
import json
import logging
import math
import os
import re
import shutil
import subprocess
import tempfile
import time
import wave
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any
import cv2
import numpy as np
logger = logging.getLogger("diorama_assembler")
import pipeline.config as _cfg  # runtime-tunable audio constants (DIORAMA_V7_MASTER_DEESSER)
from pipeline.config import (
    DIORAMA_ACT5_MONTAGE_CUT_MAX_SEC,
    DIORAMA_ACT5_MONTAGE_CUT_MIN_SEC,
    DIORAMA_ACT_COUNT,
    DIORAMA_BGM_BPM,
    DIORAMA_BGM_DUCK_DB,
    DIORAMA_CALLOUT_COUNT_RANGE,
    DIORAMA_CALLOUT_FONT_SIZE,
    DIORAMA_CALLOUT_MARGIN_V,
    DIORAMA_CLIP_COUNT_MIN,
    DIORAMA_ENTRY_RAMP_MAIN_SPEED,
    DIORAMA_ENTRY_RAMP_START_SPEED,
    DIORAMA_ENTRY_SPEED_RAMP,
    DIORAMA_MAX_CLIP_REUSE,
    DIORAMA_MIN_CUT_DURATION_SEC,
    DIORAMA_OUTRO_SWELL_GAIN_DB,
    DIORAMA_OUTRO_SWELL_SEC,
    DIORAMA_OUTRO_TITLE_FONT_SIZE,
    DIORAMA_OUTRO_TITLE_MARGIN_V,
    DIORAMA_SLICE_CROPS,
    DIORAMA_SUBTITLE_FONT_SIZE,
    DIORAMA_SUBTITLE_MARGIN_V,
    DIORAMA_SUBTITLE_MAX_WORDS,
    DIORAMA_SUBTITLE_OUTLINE_WIDTH,
    DIORAMA_TARGET_CUT_MAX,
    DIORAMA_TARGET_CUT_MIN,
    DIORAMA_TARGET_LUFS,
    DIORAMA_V7_ANATOMY_LABEL_FONT_SIZE,
    DIORAMA_V7_ANATOMY_LABEL_MARGIN_V,
    DIORAMA_V7_ANATOMY_LABEL_OUTLINE_WIDTH,
    DIORAMA_V7_ANATOMY_LABEL_SCALE_X,
    DIORAMA_V7_AUDIO_CHANNELS,
    DIORAMA_V7_BGM_DUCK_DB,
    DIORAMA_V7_CAMERA_MOVES,
    DIORAMA_V7_CHAPTER_HEADLINE_FONT_SIZE,
    DIORAMA_V7_CHAPTER_HEADLINE_MARGIN_LR,
    DIORAMA_V7_CHAPTER_HEADLINE_MARGIN_V,
    DIORAMA_V7_CHAPTER_HEADLINE_MAX_WIDTH_PX,
    DIORAMA_V7_CHAPTER_HEADLINE_OUTLINE_WIDTH,
    DIORAMA_V7_CHAPTER_HEADLINE_SCALE_X,
    DIORAMA_V7_CUT_CV_MIN,
    DIORAMA_V7_DURATION_MIN_SEC,
    DIORAMA_V7_LOCKED_CAMERA_MIN_RATIO,
    DIORAMA_V7_LONG_TAKE_MAX_SEC,
    DIORAMA_V7_MID_ACT_MAX_CUT_SEC,
    DIORAMA_V7_RAPID_CUT_MIN_SEC,
    DIORAMA_V7_SPLIT_DIVIDER_PX,
    DIORAMA_V7_SPLIT_MODE,
    DIORAMA_V7_STYLE_PROFILE,
    DIORAMA_V7_VISUAL_PLAYBACK_SPEED,
    DIORAMA_V7_ZOOM_CAMERA_MAX_RATIO,
    DIORAMA_V7_SUBTITLE_FONT_NAME,
    DIORAMA_V7_SUBTITLE_FONT_SIZE,
    DIORAMA_V7_SUBTITLE_MARGIN_V,
    DIORAMA_V7_SUBTITLE_OUTLINE_WIDTH,
    DIORAMA_V7_SUBTITLE_SHADOW_DEPTH,
    DIORAMA_V7_VIDEO_FPS,
    DIORAMA_VISUAL_PLAYBACK_SPEED,
    FONT_CONDENSED_BLACK_PATH,
    FONT_PRIMARY_PATH,
    PORCELAIN_V7_LONG_TAKE_MAX_SEC,
    PORCELAIN_V7_MID_ACT_MAX_CUT_SEC,
    PORCELAIN_V7_MIN_CUT_SEC,
    PROJECTS_DIR,
    PROMPT_SCHEMA_VERSION_V7,
    EXPRESSIVE_V8_HARD_CEILING_SEC,
    SHORTS_HARD_CEILING_FRAMES,
    SHORTS_HARD_CEILING_FRAMES_V7,
    SHORTS_HARD_CEILING_SEC,
    SUBTITLE_FONT_NAME,
    VIDEO_FPS,
    VIDEO_HEIGHT,
    VIDEO_WIDTH,
    is_diorama_v7_plan,
    is_expressive_v8_plan,
    is_porcelain_v7_plan,
    resolve_diorama_v7_style_profile,
)
from pipeline.hardware_profile import (
    resolve_assembler_workers,
    resolve_cpu_budget,
    resolve_ffmpeg_threads_per_worker,
    resolve_xfade_workers,
)
from pipeline.media_cache import (
    atomic_commit_from_scratch,
    enforce_ram_scratch_budget,
    get_ram_scratch_root,
    ram_tempdir,
)
from pipeline.media_integrity import MediaIntegrityValidator
from pipeline.storage import numeric_clip_sort_key
from pipeline.audio_utils import _clip_duration, _ffmpeg, _write_mono_wav, synthesize_continuous_diorama_track
SCRIPT_AUDIO_MTIME_TOLERANCE_SEC = 0.05
_V7_DEFAULT_CAM_CYCLE: tuple[str, ...] = (
    "locked_tripod",
    "pan_right",
    "locked_tripod",
    "gentle_push_in",
    "pan_left",
    "locked_tripod",
    "tilt_up",
    "locked_tripod",
    "tilt_down",
    "clean_pullback_reveal",
)
_V8_STOPWORDS: frozenset[str] = frozenset(
    {
        "a", "an", "the", "and", "or", "but", "yet", "for", "nor", "so", "to", "of", "in", "on",
        "at", "by", "with", "from", "into", "onto", "over", "under", "your", "their", "his", "her",
        "its", "our", "this", "that", "these", "those", "is", "are", "was", "were", "be", "been",
        "have", "has", "had", "do", "does", "did", "what", "when", "where", "which", "while", "just",
        "than", "then", "very", "also", "even", "only", "like", "about", "there",
    }
)
_V8_POWER_TOKENS: frozenset[str] = frozenset(
    {
        "awake", "asleep", "half", "split", "watch", "guard", "night", "alert", "blind", "dead",
        "trap", "secret", "wrong", "never", "freeze", "frozen", "open", "shut", "panic", "danger",
        "brain", "left", "right", "truth", "lie", "wait", "shock", "silent", "alarm",
    }
)
from pipeline.config import DIORAMA_MUX_TRUE_PEAK_LIMITER, DIORAMA_MUX_TRUE_PEAK_TARGET_DBTP  # noqa: E402
_KEYWORD_BEAT_SPLIT_RE = re.compile(
    r"(?:,\s+|\s+(?:—|--|-)\s+|\s+(?=(?:but|yet|while|until|because|forcing|driving|triggering|revealing|cutting|dropping|spiking)\b))",
    flags=re.IGNORECASE,
)


def ensure_bundled_condensed_font(out_path: Path = FONT_CONDENSED_BLACK_PATH) -> Path:
    """Ensures `AABCondensed-Black.ttf` exists with condensed glyphs (0.82x) and wide readable word spaces (1.18x)."""
    from fontTools.ttLib import TTFont
    from fontTools.varLib.instancer import instantiateVariableFont

    out_p = Path(out_path)
    if out_p.exists() and out_p.stat().st_size > 50_000:
        try:
            existing_tt = TTFont(str(out_p))
            sp_adv = existing_tt["hmtx"].metrics.get("space", (0, 0))[0]
            existing_tt.close()
            if sp_adv >= 440:
                return out_p
        except Exception:
            pass

    tt = TTFont(str(FONT_PRIMARY_PATH))
    static_tt = instantiateVariableFont(tt, {"wght": 900.0, "opsz": 28.0}, inplace=False)
    condense_x = 0.82
    space_expand_x = 1.18
    glyf = static_tt["glyf"]
    hmtx = static_tt["hmtx"]
    space_glyph_names = {"space", "uni00A0", "nbspace"}
    for gname in static_tt.getGlyphOrder():
        g = glyf[gname]
        if gname in space_glyph_names or (g.numberOfContours == 0 and not g.isComposite()):
            adv, lsb = hmtx.metrics[gname]
            hmtx.metrics[gname] = (max(1, int(round(adv * space_expand_x))), lsb)
            continue
        if g.isComposite():
            for comp in g.components:
                if hasattr(comp, "x"):
                    comp.x = int(round(comp.x * condense_x))
        elif g.numberOfContours > 0 and hasattr(g, "coordinates") and g.coordinates is not None:
            coords = g.coordinates
            for i in range(len(coords)):
                x, y = coords[i]
                coords[i] = (int(round(x * condense_x)), y)
        adv, lsb = hmtx.metrics[gname]
        hmtx.metrics[gname] = (max(1, int(round(adv * condense_x))), int(round(lsb * condense_x)))
    for gname in static_tt.getGlyphOrder():
        glyf[gname].recalcBounds(glyf)
    name_table = static_tt["name"]
    name_table.names = []
    ps_name = "AABCondensed-Black"
    records = {
        1: DIORAMA_V7_SUBTITLE_FONT_NAME,
        2: "Regular",
        3: f"1.000;AAB;{ps_name}",
        4: DIORAMA_V7_SUBTITLE_FONT_NAME,
        6: ps_name,
        16: DIORAMA_V7_SUBTITLE_FONT_NAME,
        17: "Regular",
    }
    for name_id, val in records.items():
        name_table.setName(val, name_id, 3, 1, 0x0409)
        name_table.setName(val, name_id, 1, 0, 0)
    if "OS/2" in static_tt:
        static_tt["OS/2"].usWeightClass = 900
        static_tt["OS/2"].usWidthClass = 3
        static_tt["OS/2"].fsSelection &= ~(1 << 5)
        static_tt["OS/2"].fsSelection |= (1 << 6)
    if "head" in static_tt:
        static_tt["head"].macStyle &= ~(1 << 0)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    static_tt.save(str(out_p))
    return out_p


def _frame_boundary_ass_sec(frame_idx: int, fps: int) -> float:
    """
    Returns an ASS centisecond timestamp strictly between `(frame_idx - 1) / fps` and `frame_idx / fps`
    so `libass` switches subtitle cards on exact frame `frame_idx` with 0-frame gap and 0-frame overlap.
    """
    if frame_idx <= 0:
        return 0.0
    mid = (float(frame_idx) - 0.5) / float(fps)
    return round(math.ceil(mid * 100.0) / 100.0, 2)


def _format_ass_ts(sec: float) -> str:
    s = max(0.0, float(sec))
    h = int(s // 3600)
    m = int((s % 3600) // 60)
    rem = s - (h * 3600 + m * 60)
    return f"{h}:{m:02d}:{rem:05.2f}"


def _sanitize_ass_single_line(raw: Any) -> str:
    r"""Strips `{...}`, `{`, `}`, `\r`, `\n`, and `\N` from single-line user/plan text before adding explicit ASS tags."""
    s = re.sub(r"\{[^}]*\}", "", str(raw or ""))
    s = s.replace("{", "").replace("}", "").replace("\r", " ").replace("\n", " ").replace("\\N", " ").replace("\\n", " ").replace("\\", " ")
    return re.sub(r"\s+", " ", s).strip()


def _sanitize_ass_multiline(raw: Any, max_lines: int = 2) -> str:
    r"""Strips `{...}`, `{`, `}`, `\r`, `\n` from plan text while normalizing intentional line splits into explicit `\N`."""
    s = re.sub(r"\{[^}]*\}", "", str(raw or "")).replace("{", "").replace("}", "")
    s = s.replace("\r\n", "\n").replace("\r", "\n").replace("\\n", "\\N")
    parts = [re.sub(r"\s+", " ", seg.replace("\\", " ")).strip() for seg in re.split(r"(?:\\N|\n)+", s)]
    parts = [seg for seg in parts if seg][: max(1, max_lines)]
    return "\\N".join(parts)


def generate_diorama_ass_subtitles(
    ass_path: Path,
    events: list[tuple[float, float, list[str]]],
    sentence_spans: list[dict[str, Any]],
    visual_plan: dict[str, Any],
    edl: dict[str, Any],
) -> Path:
    """
    R59 / R63 / R68 subtitle & impact headline generator:
      - Schema v8 (`expressive_25d_v8`): `102pt` `AAB Condensed Black`, `Outline=6.0`, `Shadow=0.0`, `MarginV=521`
        (`Y ≈ 72%` lower-third safe zone), 1–3 words/beat with 1 `#FFE600` (`&H00E6FF&`) anchor keyword per phrase,
        and `0` `ChapterHeadline`, `0` `AnatomyLabel`, `0` `OutroTitle` overlays.
      - Schema v7 (`porcelain_cinematic_v7` / `lowpoly_pastel_v7`): `78pt` `AAB Condensed Black`, `Outline=5.0`,
        `MarginV=678`, frame-quantized `24.0fps` handoffs, `276pt` top `ChapterHeadline` cards, and `AnatomyLabel` badges.
      - Schema v6 (`neuro_diorama`): `Default` MarginV=650 (`Y≈64%`), 76px Arial Black, `<= 3 words`.
    """
    from pipeline.config import (
        EXPRESSIVE_V8_SUBTITLE_FONT_SIZE,
        EXPRESSIVE_V8_SUBTITLE_HIGHLIGHT_ASS_BGR,
        EXPRESSIVE_V8_SUBTITLE_MARGIN_L,
        EXPRESSIVE_V8_SUBTITLE_MARGIN_R,
        EXPRESSIVE_V8_SUBTITLE_MARGIN_V,
        EXPRESSIVE_V8_SUBTITLE_MAX_WORDS,
        EXPRESSIVE_V8_SUBTITLE_OUTLINE_WIDTH,
        EXPRESSIVE_V8_SUBTITLE_SHADOW_DEPTH,
        R87_HOOK_TITLE_ACCENT_ASS_BGR,
        R87_HOOK_TITLE_DURATION_SEC,
        R87_HOOK_TITLE_FONT_SIZE,
        R87_HOOK_TITLE_FONT_SIZE_RANGE,
        R87_HOOK_TITLE_MARGIN_L,
        R87_HOOK_TITLE_MARGIN_R,
        R87_HOOK_TITLE_MARGIN_V,
        R87_HOOK_TITLE_MAX_WIDTH_PX,
        R87_HOOK_TITLE_OUTLINE,
        R87_HOOK_TITLE_SCALE_X,
        R87_HOOK_TITLE_SHADOW,
        is_expressive_v8_plan,
    )

    _V8_ANCHOR_PRIORITY_WORDS = frozenset(
        {
            "brain", "brains", "striatum", "hippocampus", "amygdala", "cortex", "brainstem",
            "dopamine", "neuron", "neurons", "synapse", "rewired", "rewire", "muted", "locked",
            "froze", "wiped", "grew", "shrank", "blocked", "stalled", "hijacked", "placebo",
            "pill", "pills", "snack", "snacks", "pudding", "sleep", "doorway", "memory", "pain",
            "shock", "fake", "awake", "asleep", "blind", "zero", "never", "stopped", "tricked",
            "pound", "pounds", "eight", "one", "two", "twice", "half", "triple", "percent",
            "sugar", "fat", "coffee", "caffeine", "wash", "rinse", "pump", "switch", "taxi",
            "london", "map", "maps", "route", "habit", "habits", "reward", "craving",
        }
    )
    _V8_SUB_STOPWORDS = frozenset(
        {
            "the", "and", "that", "this", "with", "from", "into", "your", "their", "they",
            "them", "when", "what", "where", "which", "while", "about", "after", "before",
            "would", "could", "should", "there", "these", "those", "still", "every", "just",
        }
    )

    def _highlight_v8_anchor_keyword(raw_text: str) -> str:
        hl_bgr = str(EXPRESSIVE_V8_SUBTITLE_HIGHLIGHT_ASS_BGR or "&H00FFFFFF&").strip()
        if not is_v8 or not raw_text or hl_bgr.upper() == "&H00FFFFFF&":
            return raw_text
        toks = raw_text.split()
        if not toks:
            return raw_text
        chosen_idx = -1
        for i_t, tok in enumerate(toks):
            if any(ch.isdigit() for ch in tok) or "%" in tok or "$" in tok:
                chosen_idx = i_t
                break
        if chosen_idx < 0:
            for i_t, tok in enumerate(toks):
                cleaned = re.sub(r"[^a-zA-Z0-9']", "", tok).lower()
                if cleaned in _V8_ANCHOR_PRIORITY_WORDS:
                    chosen_idx = i_t
                    break
        if chosen_idx < 0 and len(toks) >= 2:
            best_len = 4
            for i_t, tok in enumerate(toks):
                cleaned = re.sub(r"[^a-zA-Z]", "", tok).lower()
                if len(cleaned) > best_len and cleaned not in _V8_SUB_STOPWORDS:
                    best_len = len(cleaned)
                    chosen_idx = i_t
        if chosen_idx < 0:
            return raw_text
        out_toks = list(toks)
        out_toks[chosen_idx] = f"{{\\c{hl_bgr}}}{out_toks[chosen_idx]}{{\\c&H00FFFFFF&}}"
        return " ".join(out_toks)

    ass_path = Path(ass_path)
    ass_path.parent.mkdir(parents=True, exist_ok=True)
    hstack_spans = [
        (float(cut["out_start_sec"]), float(cut["out_end_sec"]))
        for cut in (edl.get("cuts") or [])
        if cut.get("mode") == "split_hstack"
    ]
    is_v8 = is_expressive_v8_plan(visual_plan, edl)
    is_v7 = is_v8 or is_diorama_v7_plan(visual_plan) or int(edl.get("schema") or 6) >= PROMPT_SCHEMA_VERSION_V7
    if is_v7:
        fps = max(1, int(edl.get("fps") or DIORAMA_V7_VIDEO_FPS))
        speech_end = float(edl.get("speech_end_sec") or 172.0)
        total_dur = float(edl.get("total_duration_sec") or 174.5)
        speech_end_frame = max(8, int(round(speech_end * fps)))
        min_tail_frames = 2 if is_v8 else 6
        total_frames = max(speech_end_frame + min_tail_frames, int(edl.get("total_frames") or round(total_dur * fps)))

        def_fs = EXPRESSIVE_V8_SUBTITLE_FONT_SIZE if is_v8 else DIORAMA_V7_SUBTITLE_FONT_SIZE
        def_out = EXPRESSIVE_V8_SUBTITLE_OUTLINE_WIDTH if is_v8 else DIORAMA_V7_SUBTITLE_OUTLINE_WIDTH
        def_shd = EXPRESSIVE_V8_SUBTITLE_SHADOW_DEPTH if is_v8 else DIORAMA_V7_SUBTITLE_SHADOW_DEPTH
        def_mv = EXPRESSIVE_V8_SUBTITLE_MARGIN_V if is_v8 else DIORAMA_V7_SUBTITLE_MARGIN_V
        def_ml = EXPRESSIVE_V8_SUBTITLE_MARGIN_L if is_v8 else 80
        def_mr = EXPRESSIVE_V8_SUBTITLE_MARGIN_R if is_v8 else 80

        header_v7 = [
            "[Script Info]",
            "ScriptType: v4.00+",
            f"PlayResX: {VIDEO_WIDTH}",
            f"PlayResY: {VIDEO_HEIGHT}",
            "WrapStyle: 2",
            "ScaledBorderAndShadow: yes",
            "",
            "[V4+ Styles]",
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
            "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
            "Alignment, MarginL, MarginR, MarginV, Encoding",
            f"Style: Default,{DIORAMA_V7_SUBTITLE_FONT_NAME},{def_fs},&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,"
            f"0,0,0,0,100,100,0,0,1,{def_out},{def_shd},2,{def_ml},{def_mr},{def_mv},1",
            f"Style: HookTitle,{DIORAMA_V7_SUBTITLE_FONT_NAME},{R87_HOOK_TITLE_FONT_SIZE},&H00FFFFFF,&H00FFFFFF,&H00000000,&H88000000,"
            f"0,0,0,0,{R87_HOOK_TITLE_SCALE_X},100,1,0,1,{R87_HOOK_TITLE_OUTLINE},{R87_HOOK_TITLE_SHADOW},8,"
            f"{R87_HOOK_TITLE_MARGIN_L},{R87_HOOK_TITLE_MARGIN_R},{R87_HOOK_TITLE_MARGIN_V},1",
            f"Style: ChapterHeadline,{DIORAMA_V7_SUBTITLE_FONT_NAME},{DIORAMA_V7_CHAPTER_HEADLINE_FONT_SIZE},&H00FFFFFF,&H00FFFFFF,&H00000000,&H88000000,"
            f"0,0,0,0,{DIORAMA_V7_CHAPTER_HEADLINE_SCALE_X},100,2,0,1,{DIORAMA_V7_CHAPTER_HEADLINE_OUTLINE_WIDTH},4.5,8,"
            f"{DIORAMA_V7_CHAPTER_HEADLINE_MARGIN_LR},{DIORAMA_V7_CHAPTER_HEADLINE_MARGIN_LR},{DIORAMA_V7_CHAPTER_HEADLINE_MARGIN_V},1",
            f"Style: AnatomyLabel,{DIORAMA_V7_SUBTITLE_FONT_NAME},{DIORAMA_V7_ANATOMY_LABEL_FONT_SIZE},&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,"
            f"0,0,0,0,{DIORAMA_V7_ANATOMY_LABEL_SCALE_X},100,1,0,1,{DIORAMA_V7_ANATOMY_LABEL_OUTLINE_WIDTH},0.0,8,"
            f"{DIORAMA_V7_CHAPTER_HEADLINE_MARGIN_LR},{DIORAMA_V7_CHAPTER_HEADLINE_MARGIN_LR},{DIORAMA_V7_ANATOMY_LABEL_MARGIN_V},1",
            f"Style: Callout,{DIORAMA_V7_SUBTITLE_FONT_NAME},64,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,"
            "0,0,0,0,100,100,1,0,1,5.0,0.0,8,60,60,180,1",
            f"Style: SplitLeft,{DIORAMA_V7_SUBTITLE_FONT_NAME},84,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,"
            "0,0,0,0,100,100,1,0,1,5.5,0.0,8,30,30,220,1",
            f"Style: SplitRight,{DIORAMA_V7_SUBTITLE_FONT_NAME},84,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,"
            "0,0,0,0,100,100,1,0,1,5.5,0.0,8,30,30,220,1",
            f"Style: SplitTop,{DIORAMA_V7_SUBTITLE_FONT_NAME},58,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,"
            "0,0,0,0,100,100,1,0,1,4.5,0.0,2,60,60,1740,1",
            f"Style: SplitBot,{DIORAMA_V7_SUBTITLE_FONT_NAME},58,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,"
            "0,0,0,0,100,100,1,0,1,4.5,0.0,2,60,60,830,1",
            f"Style: OutroTitle,{DIORAMA_V7_SUBTITLE_FONT_NAME},96,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,"
            f"0,0,0,0,100,100,1,0,1,6.5,0.0,2,70,70,{DIORAMA_OUTRO_TITLE_MARGIN_V},1",
            "",
            "[Events]",
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
        ]
        lines_v7 = list(header_v7)

        max_sub_words = EXPRESSIVE_V8_SUBTITLE_MAX_WORDS if is_v8 else DIORAMA_SUBTITLE_MAX_WORDS
        filtered_evs: list[tuple[float, float, list[str]]] = []
        for t0, t1, words in events:
            clean_all = [_sanitize_ass_single_line(w) for w in (words or []) if _sanitize_ass_single_line(w)]
            if not clean_all:
                continue
            if is_v8 and len(clean_all) > max_sub_words:
                n_w = len(clean_all)
                span_ev = max(0.04, float(t1) - float(t0))
                for k_w in range(0, n_w, max_sub_words):
                    sub_chunk = clean_all[k_w : k_w + max_sub_words]
                    st0 = float(t0) + span_ev * (k_w / float(n_w))
                    st1 = float(t0) + span_ev * (min(n_w, k_w + max_sub_words) / float(n_w))
                    filtered_evs.append((st0, st1, sub_chunk))
            else:
                filtered_evs.append((float(t0), float(t1), clean_all[:max_sub_words]))
        filtered_evs = [x for x in filtered_evs if x[2] and x[0] < speech_end - 0.04]
        act_break_times = [
            float(sp["end_sec"])
            for sp in sentence_spans
            if isinstance(sp, dict) and bool(sp.get("act_boundary_after"))
        ]

        n_evs = len(filtered_evs)
        min_ev_frames = max(3, min(4, speech_end_frame // max(1, n_evs + 2)))
        f1_prev = 0
        prev_was_act_break = False
        for idx_e, (t0, t1, clean_words) in enumerate(filtered_evs):
            from pipeline.plain_language import to_display_text

            raw_disp = _sanitize_ass_single_line(to_display_text(" ".join(clean_words)))
            txt = _highlight_v8_anchor_keyword(raw_disp) if is_v8 else raw_disp
            is_act_break_after = (
                idx_e + 1 < n_evs
                and any(abs(t1 - ab_t) <= 0.24 and filtered_evs[idx_e + 1][0] >= ab_t - 0.12 for ab_t in act_break_times)
            )
            if idx_e == 0:
                f0 = max(0, min(3, int(round(t0 * fps))))
            elif prev_was_act_break:
                # Crisp 1-frame reset ONLY at major 6-Act boundaries (<= 5 per video)
                f0 = f1_prev + 1
            else:
                # Exact 0-frame contiguous handoff across continuous speech (zero 1f strobes, zero breath blackouts)
                f0 = f1_prev

            remaining_after = n_evs - 1 - idx_e
            max_f1 = speech_end_frame - remaining_after * (min_ev_frames + 1) - (1 if is_act_break_after else 0)
            if idx_e + 1 < n_evs:
                nxt_ideal_f0 = int(round(filtered_evs[idx_e + 1][0] * fps))
                desired_f1 = nxt_ideal_f0 - (1 if is_act_break_after else 0)
                f1 = max(f0 + min_ev_frames, min(max_f1, desired_f1))
            else:
                f1 = max(f0 + min_ev_frames, speech_end_frame)
            if f0 >= speech_end_frame - 1:
                break
            f1 = min(speech_end_frame, max(f0 + 2, f1))
            s0 = _frame_boundary_ass_sec(f0, fps)
            s1 = _frame_boundary_ass_sec(f1, fps)
            if s1 <= s0:
                s1 = round(s0 + 0.08, 2)
            overlaps_hstack = any(s0 < h1 - 0.01 and s1 > h0 + 0.01 for h0, h1 in hstack_spans)
            if overlaps_hstack:
                sub_mv = int(def_mv) + 16
                sub_prefix = "{\\bord9.5\\shad2\\4c&H000000&\\4a&H50&}"
                lines_v7.append(
                    f"Dialogue: 2,{_format_ass_ts(s0)},{_format_ass_ts(s1)},Default,,0,0,{sub_mv},,{sub_prefix}{txt}"
                )
            else:
                lines_v7.append(f"Dialogue: 2,{_format_ass_ts(s0)},{_format_ass_ts(s1)},Default,,0,0,0,,{txt}")
            f1_prev = f1
            prev_was_act_break = is_act_break_after

        from PIL import ImageFont

        font_path_v7 = ensure_bundled_condensed_font()
        pil_fnt_v7 = ImageFont.truetype(str(font_path_v7), DIORAMA_V7_CHAPTER_HEADLINE_FONT_SIZE)
        target_max_w_px = float(DIORAMA_V7_CHAPTER_HEADLINE_MAX_WIDTH_PX - 25)  # <= 895px (guarantees >= 90px side margins)
        sx_factor = float(DIORAMA_V7_CHAPTER_HEADLINE_SCALE_X) / 100.0

        def _fit_headline_text(raw_txt: str) -> str:
            safe_txt = _sanitize_ass_multiline(raw_txt, max_lines=2)
            sub_lines = [seg.strip() for seg in safe_txt.split("\\N") if seg.strip()]
            if not sub_lines:
                return safe_txt
            joined_txt = "\\N".join(sub_lines)
            base_fs = (
                int(round(DIORAMA_V7_CHAPTER_HEADLINE_FONT_SIZE * 0.68))
                if len(sub_lines) >= 2
                else int(DIORAMA_V7_CHAPTER_HEADLINE_FONT_SIZE)
            )
            max_est_px = 0.0
            for seg in sub_lines:
                bb = pil_fnt_v7.getbbox(seg)
                pil_w_at_base = (bb[2] - bb[0]) * (float(base_fs) / float(DIORAMA_V7_CHAPTER_HEADLINE_FONT_SIZE))
                # libass Fontsize uses winAscent+winDescent (~1.385 em) while PIL uses 1.0 em -> 0.725 conservative ratio
                est_w = pil_w_at_base * sx_factor * 0.725 + 2.0 * max(0, len(seg) - 1) + 22.0
                if est_w > max_est_px:
                    max_est_px = est_w
            if len(sub_lines) == 1 and max_est_px <= target_max_w_px:
                return f"{{\\q2}}{joined_txt}"
            scaled_fs = base_fs if max_est_px <= target_max_w_px else max(72, int(math.floor(base_fs * (target_max_w_px / max_est_px))))
            return f"{{\\q2\\fs{scaled_fs}}}{joined_txt}"

        def _fit_v7_split_pane_text(raw_lbl: Any, pos_x: int, pos_y: int = 240, base_fs: int = 84, max_w_px: float = 470.0) -> str:
            clean_lbl = _sanitize_ass_single_line(raw_lbl).upper()
            if not clean_lbl:
                return ""
            bb = pil_fnt_v7.getbbox(clean_lbl)
            pil_w = (bb[2] - bb[0]) * (float(base_fs) / float(DIORAMA_V7_CHAPTER_HEADLINE_FONT_SIZE))
            est_w = pil_w * 0.75 + 1.0 * max(0, len(clean_lbl) - 1) + 16.0
            if len(clean_lbl) > 9:
                est_w = max(est_w, max_w_px * (float(len(clean_lbl)) / 9.0) * 0.85)
            if est_w <= max_w_px and len(clean_lbl) <= 9:
                return f"{{\\an8\\pos({pos_x},{pos_y})}}{clean_lbl}"
            scaled_fs = base_fs if est_w <= max_w_px else max(30, int(math.floor(base_fs * (max_w_px / est_w))))
            if scaled_fs >= base_fs:
                return f"{{\\an8\\pos({pos_x},{pos_y})}}{clean_lbl}"
            return f"{{\\an8\\pos({pos_x},{pos_y})\\fs{scaled_fs}}}{clean_lbl}"

        split_spans_v7 = [
            (float(cut["out_start_sec"]), float(cut["out_end_sec"]))
            for cut in (edl.get("cuts") or [])
            if cut.get("mode") in ("split_hstack", "split_vstack")
        ]
        if is_v8:
            # R87-H3: 0.00s–2.20s Silent-Scroll HookTitle (2-3 ALL-CAPS words, 118pt 2-tone white + #FFE14A, Y=250..415px, X=85..905px)
            raw_hook_title = str(
                visual_plan.get("hook_title_text")
                or visual_plan.get("opening_hook_title")
                or ""
            ).strip()
            if raw_hook_title:
                safe_ht = _sanitize_ass_multiline(raw_hook_title, max_lines=2).upper()
                ht_lines = [seg.strip() for seg in safe_ht.split("\\N") if seg.strip()]
                if ht_lines:
                    ht_sx = float(R87_HOOK_TITLE_SCALE_X) / 100.0
                    ht_lo_fs, ht_hi_fs = R87_HOOK_TITLE_FONT_SIZE_RANGE
                    base_ht_fs = min(int(R87_HOOK_TITLE_FONT_SIZE), 96) if len(ht_lines) >= 2 else int(R87_HOOK_TITLE_FONT_SIZE)
                    max_ht_w = 0.0
                    for seg in ht_lines:
                        bb_h = pil_fnt_v7.getbbox(seg)
                        pil_w_h = (bb_h[2] - bb_h[0]) * (float(base_ht_fs) / float(DIORAMA_V7_CHAPTER_HEADLINE_FONT_SIZE))
                        est_w_h = pil_w_h * ht_sx * 0.725 + 1.5 * max(0, len(seg) - 1) + 20.0
                        if est_w_h > max_ht_w:
                            max_ht_w = est_w_h
                    if max_ht_w > float(R87_HOOK_TITLE_MAX_WIDTH_PX):
                        fit_ht_fs = max(
                            int(ht_lo_fs),
                            int(math.floor(base_ht_fs * (float(R87_HOOK_TITLE_MAX_WIDTH_PX) / max_ht_w))),
                        )
                    else:
                        fit_ht_fs = min(int(ht_hi_fs), base_ht_fs)
                    if len(ht_lines) >= 2:
                        ht_styled = f"{ht_lines[0]}\\N{{\\c{R87_HOOK_TITLE_ACCENT_ASS_BGR}}}{ht_lines[1]}{{\\c&H00FFFFFF&}}"
                    else:
                        ht_toks = ht_lines[0].split()
                        if len(ht_toks) >= 2:
                            ht_styled = f"{' '.join(ht_toks[:-1])} {{\\c{R87_HOOK_TITLE_ACCENT_ASS_BGR}}}{ht_toks[-1]}{{\\c&H00FFFFFF&}}"
                        else:
                            ht_styled = f"{{\\c{R87_HOOK_TITLE_ACCENT_ASS_BGR}}}{ht_lines[0]}{{\\c&H00FFFFFF&}}"
                    ht_end_sec = min(float(R87_HOOK_TITLE_DURATION_SEC), max(1.20, float(speech_end)))
                    ht_end_f = max(4, min(speech_end_frame, int(round(ht_end_sec * fps))))
                    ht_s1 = _frame_boundary_ass_sec(ht_end_f, fps)
                    lines_v7.append(
                        f"Dialogue: 3,0:00:00.00,{_format_ass_ts(ht_s1)},HookTitle,,0,0,0,,{{\\q2\\fs{fit_ht_fs}\\fad(0,120)}}{ht_styled}"
                    )
        if not is_v8:
            # 2. Giant Top Chapter Impact Headlines (~144px height, <= DIORAMA_V7_CHAPTER_HEADLINE_MAX_WIDTH_PX width, >= 80px side margins)
            emitted_chapter_spans: list[tuple[float, float]] = []
            raw_chapters = (
                visual_plan.get("chapter_headlines")
                if isinstance(visual_plan.get("chapter_headlines"), list) and visual_plan.get("chapter_headlines")
                else (visual_plan.get("top_callouts") if isinstance(visual_plan.get("top_callouts"), list) else [])
            )
            span_by_idx = {int(s["sentence_index"]): s for s in sentence_spans}
            for c_item in raw_chapters[:8]:
                if not isinstance(c_item, dict):
                    continue
                c_txt = _sanitize_ass_multiline(c_item.get("text"), max_lines=2).upper()
                s_idx = int(c_item.get("sentence_index") or 0)
                if not c_txt or s_idx not in span_by_idx:
                    continue
                if "UNIVERSITY NEUROSCIENCE" in c_txt or "MADE SIMPLE" in c_txt or "ALL ABOUT BRAIN" in c_txt:
                    continue
                sp = span_by_idx[s_idx]
                cf0 = max(0, int(round(float(sp["start_sec"]) * fps)))
                cf1 = min(speech_end_frame - 2, max(cf0 + int(round(1.5 * fps)), int(round(float(sp["end_sec"]) * fps))))
                c0_raw = cf0 / float(fps)
                c1_raw = cf1 / float(fps)
                skip_ch = False
                for sp0, sp1 in split_spans_v7:
                    if c0_raw < sp1 + 0.08 and c1_raw > sp0 - 0.08:
                        skip_ch = True
                        break
                if skip_ch or cf1 - cf0 < int(round(0.8 * fps)):
                    continue
                disp_ch = _fit_headline_text(c_txt)
                cs0 = _frame_boundary_ass_sec(cf0, fps)
                cs1 = _frame_boundary_ass_sec(cf1, fps)
                emitted_chapter_spans.append((c0_raw, c1_raw))
                lines_v7.append(f"Dialogue: 1,{_format_ass_ts(cs0)},{_format_ass_ts(cs1)},ChapterHeadline,,0,0,0,,{disp_ch}")

            # 2b. Programmatic Anatomical Region Callouts (`AnatomyLabel`) on `lowpoly_matte_brain` cuts (zero AI text, collision-free)
            auto_anat_ass = bool(visual_plan.get("auto_anatomy_labels", True))
            plan_clips_v7 = visual_plan.get("clips") if isinstance(visual_plan.get("clips"), list) else []
            anat_sx_factor = float(DIORAMA_V7_ANATOMY_LABEL_SCALE_X) / 100.0
            anat_target_max_w = float(DIORAMA_V7_CHAPTER_HEADLINE_MAX_WIDTH_PX - 30)  # <= 890px (>= 95px side margins)

            def _fit_anatomy_label_text(raw_txt: str) -> str:
                safe_txt = _sanitize_ass_multiline(raw_txt, max_lines=2)
                sub_lines = [seg.strip() for seg in safe_txt.split("\\N") if seg.strip()]
                if not sub_lines:
                    return safe_txt
                joined_txt = "\\N".join(sub_lines[:2])
                base_fs = 92 if len(sub_lines) >= 2 else int(DIORAMA_V7_ANATOMY_LABEL_FONT_SIZE)
                max_est_px = 0.0
                for seg in sub_lines[:2]:
                    bb = pil_fnt_v7.getbbox(seg)
                    pil_w_at_base = (bb[2] - bb[0]) * (float(base_fs) / float(DIORAMA_V7_CHAPTER_HEADLINE_FONT_SIZE))
                    est_w = pil_w_at_base * anat_sx_factor * 0.725 + 1.0 * max(0, len(seg) - 1) + 20.0
                    if est_w > max_est_px:
                        max_est_px = est_w
                if len(sub_lines) == 1 and max_est_px <= anat_target_max_w:
                    return f"{{\\q2}}{joined_txt}"
                scaled_fs = base_fs if max_est_px <= anat_target_max_w else max(56, int(math.floor(base_fs * (anat_target_max_w / max_est_px))))
                return f"{{\\q2\\fs{scaled_fs}}}{joined_txt}"

            prev_al_f1 = -1
            for cut in edl.get("cuts") or []:
                if cut.get("outro_sky_card") or cut.get("mode") in ("split_hstack", "split_vstack"):
                    continue
                if str(cut.get("grammar") or "") not in ("lowpoly_matte_brain", "porcelain_living_brain", "living_brain"):
                    continue
                lbl_raw = cut.get("anatomy_label")
                if lbl_raw is False:
                    continue
                lbl_norm = _normalize_v7_anatomy_badge_text(lbl_raw) if isinstance(lbl_raw, str) and lbl_raw.strip() else ""
                if not lbl_norm:
                    c_idx_1 = int(cut.get("clip_index") or 0)
                    c_spec = plan_clips_v7[c_idx_1 - 1] if 1 <= c_idx_1 <= len(plan_clips_v7) and isinstance(plan_clips_v7[c_idx_1 - 1], dict) else None
                    _, resolved_lbl = _resolve_v7_cut_anatomy_label(c_spec, auto_enabled=auto_anat_ass)
                    lbl_norm = resolved_lbl or ""
                if not lbl_norm:
                    continue

                a0_raw = float(cut["out_start_sec"])
                a1_raw = min(speech_end - 0.05, float(cut["out_end_sec"]))
                skip_al = False
                for ch0, ch1 in emitted_chapter_spans + split_spans_v7:
                    if a0_raw < ch1 + 0.08 and a1_raw > ch0 - 0.08:
                        # Trim to non-overlapping portion if >= 0.90s remains; otherwise suppress to prevent top-band collision
                        if a1_raw - (ch1 + 0.08) >= 0.90 and a0_raw >= ch0 - 0.15:
                            a0_raw = ch1 + 0.08
                        elif (ch0 - 0.08) - a0_raw >= 0.90 and a1_raw <= ch1 + 0.15:
                            a1_raw = ch0 - 0.08
                        else:
                            skip_al = True
                            break
                if skip_al or (a1_raw - a0_raw) < 0.85:
                    continue
                af0 = max(prev_al_f1 + 1, int(round(a0_raw * fps)) + 1)
                af1 = min(speech_end_frame - 2, int(round(a1_raw * fps)) - 1)
                if af1 - af0 < int(round(0.75 * fps)):
                    continue
                disp_al = _fit_anatomy_label_text(lbl_norm)
                as0 = _frame_boundary_ass_sec(af0, fps)
                as1 = _frame_boundary_ass_sec(af1, fps)
                lines_v7.append(f"Dialogue: 1,{_format_ass_ts(as0)},{_format_ass_ts(as1)},AnatomyLabel,,0,0,0,,{disp_al}")
                prev_al_f1 = af1

        # 3. Split-Screen Labels (supporting Left/Right split_hstack within max_width_px=470 and Top/Bottom split_vstack)
        for cut in edl.get("cuts") or []:
            c_mode = cut.get("mode")
            if c_mode in ("split_hstack", "split_vstack") and cut.get("split_labels"):
                lbl_a, lbl_b = cut["split_labels"]
                cf0 = max(0, int(round(float(cut["out_start_sec"]) * fps)))
                cf1 = max(cf0 + 4, int(round(float(cut["out_end_sec"]) * fps)))
                cs0 = _frame_boundary_ass_sec(cf0, fps)
                cs1 = _frame_boundary_ass_sec(cf1, fps)
                if c_mode == "split_hstack":
                    left_ev = _fit_v7_split_pane_text(lbl_a, pos_x=268, pos_y=240, base_fs=84, max_w_px=470.0)
                    right_ev = _fit_v7_split_pane_text(lbl_b, pos_x=812, pos_y=240, base_fs=84, max_w_px=470.0)
                    if left_ev:
                        lines_v7.append(f"Dialogue: 1,{_format_ass_ts(cs0)},{_format_ass_ts(cs1)},SplitLeft,,0,0,0,,{left_ev}")
                    if right_ev:
                        lines_v7.append(f"Dialogue: 1,{_format_ass_ts(cs0)},{_format_ass_ts(cs1)},SplitRight,,0,0,0,,{right_ev}")
                else:
                    clean_top = _sanitize_ass_single_line(lbl_a).upper()
                    clean_bot = _sanitize_ass_single_line(lbl_b).upper()
                    if clean_top:
                        lines_v7.append(f"Dialogue: 1,{_format_ass_ts(cs0)},{_format_ass_ts(cs1)},SplitTop,,0,0,0,,{clean_top}")
                    if clean_bot:
                        lines_v7.append(f"Dialogue: 1,{_format_ass_ts(cs0)},{_format_ass_ts(cs1)},SplitBot,,0,0,0,,{clean_bot}")

        # 4. Final 2.2s Sky Tilt-Up 2-Line Uppercase English Title Card (suppressed on `expressive_25d_v8`)
        if not is_v8:
            outro_lines = [
                _sanitize_ass_single_line(x).upper()
                for x in (visual_plan.get("outro_title_lines") or [])
                if _sanitize_ass_single_line(x)
            ]
            if len(outro_lines) >= 2:
                card_txt = f"{outro_lines[0]}\\N{outro_lines[1]}"
            elif len(outro_lines) == 1:
                card_txt = outro_lines[0]
            else:
                card_txt = "ALL ABOUT BRAIN\\NNEUROSCIENCE DOCUMENTARY"
            of0 = min(total_frames - 4, speech_end_frame + 1)
            of1 = max(of0 + 6, total_frames - 1)
            os0 = _frame_boundary_ass_sec(of0, fps)
            os1 = _frame_boundary_ass_sec(of1, fps)
            lines_v7.append(f"Dialogue: 3,{_format_ass_ts(os0)},{_format_ass_ts(os1)},OutroTitle,,0,0,0,,{card_txt}")

        tmp_ass = ass_path.with_suffix(".ass.tmp")
        tmp_ass.write_text("\n".join(lines_v7) + "\n", encoding="utf-8")
        os.replace(tmp_ass, ass_path)
        return ass_path

    header = [
        "[Script Info]",
        "ScriptType: v4.00+",
        f"PlayResX: {VIDEO_WIDTH}",
        f"PlayResY: {VIDEO_HEIGHT}",
        "WrapStyle: 2",
        "ScaledBorderAndShadow: yes",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
        "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding",
        f"Style: Default,{SUBTITLE_FONT_NAME},{DIORAMA_SUBTITLE_FONT_SIZE},&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,"
        f"-1,0,0,0,100,100,0,0,1,{DIORAMA_SUBTITLE_OUTLINE_WIDTH},1.5,2,60,60,{DIORAMA_SUBTITLE_MARGIN_V},1",
        f"Style: Callout,{SUBTITLE_FONT_NAME},{DIORAMA_CALLOUT_FONT_SIZE},&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,"
        f"-1,0,0,0,100,100,2,0,1,4.0,1.5,2,60,60,{DIORAMA_CALLOUT_MARGIN_V},1",
        f"Style: SplitLeft,{SUBTITLE_FONT_NAME},64,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,"
        "-1,0,0,0,100,100,1,0,1,4.5,1.0,8,30,30,220,1",
        f"Style: SplitRight,{SUBTITLE_FONT_NAME},64,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,"
        "-1,0,0,0,100,100,1,0,1,4.5,1.0,8,30,30,220,1",
        f"Style: SplitTop,{SUBTITLE_FONT_NAME},48,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,"
        "-1,0,0,0,100,100,2,0,1,3.5,1.0,2,60,60,1740,1",
        f"Style: SplitBot,{SUBTITLE_FONT_NAME},48,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,"
        "-1,0,0,0,100,100,2,0,1,3.5,1.0,2,60,60,830,1",
        f"Style: OutroTitle,{SUBTITLE_FONT_NAME},{DIORAMA_OUTRO_TITLE_FONT_SIZE},&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,"
        f"-1,0,0,0,100,100,2,0,1,5.5,2.0,2,70,70,{DIORAMA_OUTRO_TITLE_MARGIN_V},1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    lines = list(header)
    speech_end = float(edl.get("speech_end_sec") or 175.0)
    total_dur = float(edl.get("total_duration_sec") or 177.5)

    def _fit_v6_split_pane_text(raw_lbl: Any, pos_x: int, pos_y: int = 240, base_fs: int = 64, max_w_px: float = 470.0) -> str:
        clean_lbl = _sanitize_ass_single_line(raw_lbl).upper()
        if not clean_lbl:
            return ""
        est_w = float(len(clean_lbl)) * float(base_fs) * 0.70 + 1.0 * max(0, len(clean_lbl) - 1) + 18.0
        if len(clean_lbl) > 9:
            est_w = max(est_w, max_w_px * (float(len(clean_lbl)) / 9.0) * 0.90)
        if est_w <= max_w_px and len(clean_lbl) <= 9:
            return f"{{\\an8\\pos({pos_x},{pos_y})}}{clean_lbl}"
        scaled_fs = base_fs if est_w <= max_w_px else max(28, int(math.floor(base_fs * (max_w_px / est_w))))
        if scaled_fs >= base_fs:
            return f"{{\\an8\\pos({pos_x},{pos_y})}}{clean_lbl}"
        return f"{{\\an8\\pos({pos_x},{pos_y})\\fs{scaled_fs}}}{clean_lbl}"

    # 1. Pure-white single-line strictly non-overlapping Default dialogue events (>=0.25s readable floor)
    filtered_evs = [
        (
            float(t0),
            float(t1),
            [_sanitize_ass_single_line(w) for w in words[:DIORAMA_SUBTITLE_MAX_WORDS] if _sanitize_ass_single_line(w)],
        )
        for t0, t1, words in events
    ]
    filtered_evs = [x for x in filtered_evs if x[2]]
    prev_end = 0.0
    for idx_e, (t0, t1, clean_words) in enumerate(filtered_evs):
        txt = _sanitize_ass_single_line(" ".join(clean_words))
        s0 = round(max(prev_end + 0.01 if prev_end > 0 else 0.0, t0), 2)
        next_ceiling = speech_end
        if idx_e + 1 < len(filtered_evs):
            nxt_t0, nxt_t1, _ = filtered_evs[idx_e + 1]
            # Allow borrowing up to 0.08s from a long following phrase if this phrase is <0.25s
            max_borrow = round(min(nxt_t0 + 0.08, nxt_t1 - 0.26), 2) if (t1 - s0) < 0.25 else round(nxt_t0 - 0.01, 2)
            next_ceiling = min(speech_end, max(round(nxt_t0 - 0.01, 2), max_borrow))
        desired_end = max(s0 + 0.25, t1)
        s1 = round(min(next_ceiling, max(s0 + 0.08, desired_end)), 2)
        if s0 >= speech_end - 0.04:
            break
        overlaps_hstack = any(s0 < h1 - 0.01 and s1 > h0 + 0.01 for h0, h1 in hstack_spans)
        if overlaps_hstack:
            sub_mv = int(DIORAMA_SUBTITLE_MARGIN_V) + 16
            sub_prefix = "{\\bord7.5\\shad2\\4c&H000000&\\4a&H50&}"
            lines.append(f"Dialogue: 2,{_format_ass_ts(s0)},{_format_ass_ts(s1)},Default,,0,0,{sub_mv},,{sub_prefix}{txt}")
        else:
            lines.append(f"Dialogue: 2,{_format_ass_ts(s0)},{_format_ass_ts(s1)},Default,,0,0,0,,{txt}")
        prev_end = s1

    # 2. Top-space minimal US English stat/year Callouts (4..8 max, collision-free vs SplitTop / SplitLeft / SplitRight)
    split_spans = [
        (float(cut["out_start_sec"]), float(cut["out_end_sec"]))
        for cut in (edl.get("cuts") or [])
        if cut.get("mode") in ("split_hstack", "split_vstack")
    ]
    raw_callouts = visual_plan.get("top_callouts") if isinstance(visual_plan.get("top_callouts"), list) else []
    lo_c, hi_c = DIORAMA_CALLOUT_COUNT_RANGE
    span_by_idx = {int(s["sentence_index"]): s for s in sentence_spans}
    for c_item in raw_callouts[:hi_c]:
        if not isinstance(c_item, dict):
            continue
        c_txt = _sanitize_ass_single_line(c_item.get("text")).upper()
        s_idx = int(c_item.get("sentence_index") or 0)
        if not c_txt or s_idx not in span_by_idx:
            continue
        if "UNIVERSITY NEUROSCIENCE" in c_txt or "MADE SIMPLE" in c_txt or "ALL ABOUT BRAIN" in c_txt:
            continue
        sp = span_by_idx[s_idx]
        c0 = round(float(sp["start_sec"]), 2)
        c1 = round(min(speech_end - 0.1, max(c0 + 1.4, float(sp["end_sec"]))), 2)
        skip_callout = False
        for sp0, sp1 in split_spans:
            if c0 < sp1 + 0.05 and c1 > sp0 - 0.05:
                if sp0 - c0 >= 1.0:
                    c1 = round(sp0 - 0.06, 2)
                elif c1 - sp1 >= 1.0:
                    c0 = round(sp1 + 0.06, 2)
                else:
                    skip_callout = True
                    break
        if skip_callout or c1 - c0 < 0.75:
            continue
        fs_prefix = ""
        if len(c_txt) > 18:
            scaled_fs = max(32, int(round(DIORAMA_CALLOUT_FONT_SIZE * (18.0 / float(len(c_txt))))))
            fs_prefix = f"{{\\fs{scaled_fs}}}"
        lines.append(f"Dialogue: 1,{_format_ass_ts(c0)},{_format_ass_ts(c1)},Callout,,0,0,0,,{fs_prefix}{c_txt}")
    _ = lo_c

    # 3. Act 3 Split-Screen Labels (supporting both split_hstack and split_vstack)
    for cut in edl.get("cuts") or []:
        c_mode = cut.get("mode")
        if c_mode in ("split_hstack", "split_vstack") and cut.get("split_labels"):
            lbl_a, lbl_b = cut["split_labels"]
            c0 = round(float(cut["out_start_sec"]), 2)
            c1 = round(float(cut["out_end_sec"]), 2)
            if c_mode == "split_hstack":
                left_ev = _fit_v6_split_pane_text(lbl_a, pos_x=268, pos_y=240, base_fs=64, max_w_px=470.0)
                right_ev = _fit_v6_split_pane_text(lbl_b, pos_x=812, pos_y=240, base_fs=64, max_w_px=470.0)
                if left_ev:
                    lines.append(f"Dialogue: 1,{_format_ass_ts(c0)},{_format_ass_ts(c1)},SplitLeft,,0,0,0,,{left_ev}")
                if right_ev:
                    lines.append(f"Dialogue: 1,{_format_ass_ts(c0)},{_format_ass_ts(c1)},SplitRight,,0,0,0,,{right_ev}")
            else:
                top_lbl = _sanitize_ass_single_line(lbl_a).upper()
                bot_lbl = _sanitize_ass_single_line(lbl_b).upper()
                if top_lbl:
                    lines.append(f"Dialogue: 1,{_format_ass_ts(c0)},{_format_ass_ts(c1)},SplitTop,,0,0,0,,{top_lbl}")
                if bot_lbl:
                    lines.append(f"Dialogue: 1,{_format_ass_ts(c0)},{_format_ass_ts(c1)},SplitBot,,0,0,0,,{bot_lbl}")

    # 4. Final 2.2s Sky Tilt-Up 2-Line Uppercase English Title Card
    outro_lines = [
        _sanitize_ass_single_line(x).upper()
        for x in (visual_plan.get("outro_title_lines") or [])
        if _sanitize_ass_single_line(x)
    ]
    if len(outro_lines) >= 2:
        card_txt = f"{outro_lines[0]}\\N{outro_lines[1]}"
    elif len(outro_lines) == 1:
        card_txt = outro_lines[0]
    else:
        card_txt = "ALL ABOUT BRAIN\\NNEUROSCIENCE DOCUMENTARY"
    o0 = round(max(0.0, speech_end + 0.05), 2)
    o1 = round(max(o0 + 0.5, total_dur - 0.04), 2)
    lines.append(f"Dialogue: 3,{_format_ass_ts(o0)},{_format_ass_ts(o1)},OutroTitle,,0,0,0,,{card_txt}")

    tmp_ass = ass_path.with_suffix(".ass.tmp")
    tmp_ass.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.replace(tmp_ass, ass_path)
    return ass_path


def probe_ass_font_resolution(ff: str, work_dir: Path, ass_name: str, fontsdir: str | None = "fonts") -> dict[str, Any]:
    """
    F-2 font guard: renders one frame through libass at the first dialogue timestamp with `-loglevel info`
    and parses `fontselect:` lines. Any request for the bundled condensed font that resolves to another file
    (e.g. DejaVuSans) is recorded as a fallback and fails the probe.
    """
    ass_p = Path(work_dir) / ass_name
    t_probe = 1.0
    try:
        for ln in ass_p.read_text(encoding="utf-8").splitlines():
            if ln.startswith("Dialogue:"):
                parts = ln.split(",", 3)
                t_probe = _parse_ass_time(parts[1]) + 0.05
                break
    except Exception:  # noqa: BLE001
        pass
    flt = f"setpts=PTS+{t_probe:.3f}/TB,ass={ass_name}" + (f":fontsdir={fontsdir}" if fontsdir else "")
    res = subprocess.run(
        [
            ff, "-nostdin", "-hide_banner", "-loglevel", "info",
            "-f", "lavfi", "-i", f"color=c=gray:s={VIDEO_WIDTH}x{VIDEO_HEIGHT}:r=24:d=1",
            "-vf", flt, "-frames:v", "1", "-f", "null", "-",
        ],
        cwd=str(work_dir), capture_output=True, text=True, check=False, timeout=60, stdin=subprocess.DEVNULL,
    )
    lines = [ln.strip() for ln in (res.stderr or "").splitlines() if "fontselect" in ln]
    want = DIORAMA_V7_SUBTITLE_FONT_NAME.lower()
    fallbacks = []
    for ln in lines:
        low = ln.lower()
        if want in low and "->" in low:
            target = low.split("->", 1)[1]
            if "aabcondensed" not in target.replace(" ", "") and "aab condensed" not in target:
                fallbacks.append(ln)
    return {
        "passed": res.returncode == 0 and not fallbacks,
        "returncode": res.returncode,
        "probe_time_sec": round(t_probe, 3),
        "fontselect_lines": lines[:12],
        "fallbacks": fallbacks,
    }


def _parse_ass_time(ts: str) -> float:
    m = re.match(r"\s*(\d+):(\d+):([\d.]+)", str(ts))
    if not m:
        return 0.0
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))

