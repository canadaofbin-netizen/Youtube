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
from pipeline.voice_fallback import _clip_duration, _ffmpeg, _write_mono_wav, synthesize_continuous_diorama_track


def _write_stereo_wav(path: Path, stereo_pcm: np.ndarray, sr: int) -> None:
    """Writes a 2-channel 16-bit PCM WAV (`shape == (N, 2)`)."""
    arr = np.asarray(stereo_pcm, dtype=np.float32)
    if arr.ndim == 1:
        arr = np.stack([arr, arr], axis=1)
    clipped = np.clip(arr, -1.0, 1.0)
    pcm16 = (clipped * 32767.0).astype(np.int16)
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(int(sr))
        wf.writeframes(pcm16.tobytes())


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


def load_diorama_script_sentences(project_dir: Path) -> tuple[list[str], dict[str, Any]]:
    """Loads ordered US English sentences and full script dict from `02_script/script.json`."""
    p_dir = Path(project_dir)
    script_path = next((p for p in (p_dir / "02_script" / "script.json", p_dir / "script.json") if p.exists()), None)
    if script_path is None:
        raise FileNotFoundError(f"script.json not found in {p_dir}")
    doc = json.loads(script_path.read_text(encoding="utf-8"))
    if isinstance(doc.get("sentences"), list) and doc["sentences"]:
        sents = [str(s).strip() for s in doc["sentences"] if str(s).strip()]
    elif isinstance(doc.get("acts"), list) and doc["acts"]:
        sents = [
            str(s).strip()
            for act in doc["acts"]
            if isinstance(act, dict)
            for s in (act.get("sentences") or [])
            if str(s).strip()
        ]
    elif isinstance(doc.get("clip_narrations"), list) and doc["clip_narrations"]:
        sents = [str(s).strip() for s in doc["clip_narrations"] if str(s).strip()]
    else:
        raise ValueError(f"No sentences/acts/clip_narrations found in {script_path}")
    return sents, doc


SCRIPT_AUDIO_MTIME_TOLERANCE_SEC = 0.05


def compute_script_freshness_digests(project_dir: Path) -> dict[str, Any]:
    """Computes raw file SHA-256 and normalized spoken-sentences SHA-256 for `02_script/script.json`."""
    p_dir = Path(project_dir)
    script_path = next((p for p in (p_dir / "02_script" / "script.json", p_dir / "script.json") if p.exists()), None)
    if script_path is None:
        return {"script_path": None, "script_sha256": "", "sentences_sha256": "", "script_mtime": None}
    raw_bytes = script_path.read_bytes()
    script_sha256 = hashlib.sha256(raw_bytes).hexdigest()
    sentences_sha256 = ""
    try:
        sents, _ = load_diorama_script_sentences(p_dir)
        sentences_sha256 = hashlib.sha256(
            json.dumps([str(s).strip() for s in sents if str(s).strip()], ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
    except Exception:
        sentences_sha256 = ""
    return {
        "script_path": script_path,
        "script_sha256": script_sha256,
        "sentences_sha256": sentences_sha256,
        "script_mtime": float(script_path.stat().st_mtime),
    }


def verify_script_audio_freshness(project_dir: Path, *, context: str = "QA") -> dict[str, Any]:
    """
    Mtime + SHA-256 guard ensuring `02_script/script.json` has not been modified after
    `04_audio/audio_master.wav` / `04_audio/voice_report.json`.
    Raises `RuntimeError` so cached assembly, `preserve_audio_master`, `recut`, and QA gates
    refuse to run against stale audio/EDL artifacts.
    """
    p_dir = Path(project_dir)
    dig = compute_script_freshness_digests(p_dir)
    script_path: Path | None = dig["script_path"]
    if script_path is None:
        return {"fresh": True, "checked": False, "reason": "no_script_json"}

    wav_path = p_dir / "04_audio" / "audio_master.wav"
    vr_path = p_dir / "04_audio" / "voice_report.json"
    script_mtime = float(dig["script_mtime"])
    wav_mtime: float | None = None

    if wav_path.exists():
        wav_mtime = float(wav_path.stat().st_mtime)
        dt = script_mtime - wav_mtime
        if dt > SCRIPT_AUDIO_MTIME_TOLERANCE_SEC:
            raise RuntimeError(
                f"[{context}] Stale audio/assembly guard: {script_path.name} is newer than audio_master.wav "
                f"by {dt:.2f}s in '{p_dir.name}'. Re-run TTS synthesis and full assembly (`diorama-assemble --force`) first."
            )

    if vr_path.exists():
        try:
            vr = json.loads(vr_path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise RuntimeError(f"[{context}] Corrupt voice_report.json in '{p_dir.name}': {exc}") from exc
        vr_script_sha = str(vr.get("script_sha256") or "").strip()
        if vr_script_sha and dig["script_sha256"] and vr_script_sha != dig["script_sha256"]:
            raise RuntimeError(
                f"[{context}] Stale audio/assembly guard: script.json sha256 ({dig['script_sha256'][:12]}) != "
                f"voice_report.script_sha256 ({vr_script_sha[:12]}) in '{p_dir.name}'. "
                "Re-run TTS synthesis and full assembly (`diorama-assemble --force`) first."
            )
        vr_sents_sha = str(vr.get("sentences_sha256") or "").strip()
        if vr_sents_sha and dig["sentences_sha256"] and vr_sents_sha != dig["sentences_sha256"]:
            raise RuntimeError(
                f"[{context}] Stale audio/assembly guard: script sentences sha256 ({dig['sentences_sha256'][:12]}) != "
                f"voice_report.sentences_sha256 ({vr_sents_sha[:12]}) in '{p_dir.name}'. "
                "Re-run TTS synthesis and full assembly (`diorama-assemble --force`) first."
            )

    return {
        "fresh": True,
        "checked": bool(wav_path.exists() or vr_path.exists()),
        "script_mtime": script_mtime,
        "audio_mtime": wav_mtime,
        "script_sha256": dig["script_sha256"],
        "sentences_sha256": dig["sentences_sha256"],
    }


def _format_ass_ts(sec: float) -> str:
    s = max(0.0, float(sec))
    h = int(s // 3600)
    m = int((s % 3600) // 60)
    rem = s - (h * 3600 + m * 60)
    return f"{h}:{m:02d}:{rem:05.2f}"


def _sentence_act_map(script_doc: dict[str, Any], n_sentences: int) -> dict[int, int]:
    """Maps 1-based sentence_index -> act number (1..6)."""
    mapping: dict[int, int] = {}
    acts = script_doc.get("acts") if isinstance(script_doc.get("acts"), list) else []
    if acts:
        cursor = 1
        for a_idx, act in enumerate(acts, start=1):
            sents = (act.get("sentences") or []) if isinstance(act, dict) else []
            for _ in sents:
                if cursor <= n_sentences:
                    mapping[cursor] = min(DIORAMA_ACT_COUNT, a_idx)
                    cursor += 1
        while cursor <= n_sentences:
            mapping[cursor] = DIORAMA_ACT_COUNT
            cursor += 1
        return mapping
    for i in range(1, n_sentences + 1):
        mapping[i] = min(DIORAMA_ACT_COUNT, ((i - 1) * DIORAMA_ACT_COUNT) // max(1, n_sentences) + 1)
    return mapping


def _compute_max_clip_reuse(cuts: list[dict[str, Any]]) -> int:
    counts: dict[int, int] = {}
    for c in cuts:
        p_idx = c.get("clip_index")
        if p_idx is not None:
            counts[int(p_idx)] = counts.get(int(p_idx), 0) + 1
        s_idx = c.get("secondary_clip_index")
        if s_idx is not None:
            counts[int(s_idx)] = counts.get(int(s_idx), 0) + 1
    return max(counts.values()) if counts else 0


def build_one_to_one_edl(
    visual_plan: dict[str, Any],
    sentence_spans: list[dict[str, Any]],
    clip_files: list[Path],
    speech_end_sec: float,
    total_duration_sec: float,
    script_doc: dict[str, Any] | None = None,
    virtual_clip_duration_sec: float | None = None,
) -> dict[str, Any]:
    """
    R58 Schema v6.1 Unlimited Dedicated 1:1 Zero-Reuse EDL builder:
      - Maps every spoken sentence (`1..S`) directly to its dedicated Google Flow clip(s)
        at `1.00x` full framing (`0%` clip reuse, `max_clip_reuse == 1`).
      - Dedicates separate unique clips to `split_comparisons` bottom panes and the final
        `2.2s` sky tilt-up outro card so zero clips are ever repeated anywhere in the Short.
    """
    n_sents = len(sentence_spans)
    n_clips = len(clip_files)
    if n_clips < n_sents + 1:
        raise ValueError(
            f"build_one_to_one_edl requires >= {n_sents + 1} unique clips for {n_sents} sentences + outro (got {n_clips})"
        )
    fps = int(VIDEO_FPS)
    total_frames = min(SHORTS_HARD_CEILING_FRAMES, max(60, int(round(total_duration_sec * fps))))
    speech_frames = min(total_frames - int(round(DIORAMA_OUTRO_SWELL_SEC * fps)), int(round(speech_end_sec * fps)))
    speech_frames = max(30, speech_frames)
    outro_frames = max(30, total_frames - speech_frames)

    plan_clips = visual_plan.get("clips") if isinstance(visual_plan.get("clips"), list) else []
    clip_durs = [
        max(
            4.0,
            float(virtual_clip_duration_sec)
            if (virtual_clip_duration_sec is not None and (not Path(cf).is_file() or Path(cf).stat().st_size <= 0))
            else float(_clip_duration(Path(cf))),
        )
        for cf in clip_files
    ]
    clip_grammars: dict[int, str] = {}
    for idx in range(n_clips):
        spec = plan_clips[idx] if idx < len(plan_clips) and isinstance(plan_clips[idx], dict) else {}
        clip_grammars[idx] = str(spec.get("grammar") or "arch_cutaway_diorama")

    # 1. Identify dedicated outro clip (0-based)
    outro_clip_idx = n_clips - 1
    for idx in range(n_clips):
        spec = plan_clips[idx] if idx < len(plan_clips) and isinstance(plan_clips[idx], dict) else {}
        if str(spec.get("cut_role") or "").strip().lower() == "outro":
            outro_clip_idx = idx
            break
    reserved_clips: set[int] = {outro_clip_idx}

    # 2. Parse split_comparisons and reserve dedicated secondary right/bottom clips
    split_by_sentence: dict[int, dict[str, Any]] = {}
    raw_splits = visual_plan.get("split_comparisons") if isinstance(visual_plan.get("split_comparisons"), list) else []
    for sc in raw_splits:
        if not isinstance(sc, dict):
            continue
        s_no = int(sc.get("sentence_index") or 0)
        sec_1based = int(sc.get("right_clip_index") or sc.get("bottom_clip_index") or 0)
        b_idx = sec_1based - 1
        if 1 <= s_no <= n_sents and 0 <= b_idx < n_clips and b_idx not in reserved_clips:
            split_by_sentence[s_no] = sc
            reserved_clips.add(b_idx)

    # 3. Assign remaining unique clips to sentences (1..n_sents) with zero reuse
    clips_for_sentence: dict[int, list[tuple[int, int]]] = {s: [] for s in range(1, n_sents + 1)}
    used_primary: set[int] = set()
    for idx in range(n_clips):
        if idx in reserved_clips:
            continue
        spec = plan_clips[idx] if idx < len(plan_clips) and isinstance(plan_clips[idx], dict) else {}
        role = str(spec.get("cut_role") or "").strip().lower()
        if role in ("outro", "split_bottom", "split_right"):
            reserved_clips.add(idx)
            continue
        s_no = spec.get("sentence_index")
        if isinstance(s_no, int) and 1 <= s_no <= n_sents:
            beat_i = int(spec.get("beat_index") or (len(clips_for_sentence[s_no]) + 1))
            clips_for_sentence[s_no].append((beat_i, idx))
            used_primary.add(idx)

    spare_clips = [idx for idx in range(n_clips) if idx not in reserved_clips and idx not in used_primary]
    spare_cursor = 0
    for s_no in range(1, n_sents + 1):
        if not clips_for_sentence[s_no]:
            if spare_cursor >= len(spare_clips):
                raise ValueError(
                    f"build_one_to_one_edl ran out of unique clips at sentence {s_no} (n_clips={n_clips})"
                )
            chosen_idx = spare_clips[spare_cursor]
            spare_cursor += 1
            clips_for_sentence[s_no].append((1, chosen_idx))
            used_primary.add(chosen_idx)

    # 4. Build ordered 1:1 sentence/beat intervals across [0, speech_frames]
    s_act = _sentence_act_map(script_doc or {}, n_sents)
    raw_beats: list[dict[str, Any]] = []
    for sp in sentence_spans:
        s_idx = int(sp["sentence_index"])
        act_no = s_act.get(s_idx, 1)
        t0 = float(sp["start_sec"])
        t1 = float(sp["end_sec"])
        dur = max(0.35, t1 - t0)
        ordered_clips = [c_idx for _, c_idx in sorted(clips_for_sentence[s_idx], key=lambda x: (x[0], x[1]))]
        k = len(ordered_clips)
        for sub_i, c_idx in enumerate(ordered_clips):
            b0 = t0 + dur * (sub_i / float(k))
            b1 = t0 + dur * ((sub_i + 1) / float(k))
            raw_beats.append(
                {
                    "act": act_no,
                    "sentence_index": s_idx,
                    "sub_beat": sub_i,
                    "clip_idx": c_idx,
                    "t0": b0,
                    "t1": b1,
                }
            )

    n_b = len(raw_beats)
    min_cut_frames = min(
        int(round(DIORAMA_MIN_CUT_DURATION_SEC * fps)),
        max(12, int(speech_frames * 0.85) // max(1, n_b)),
    )
    boundaries = [0]
    for i in range(1, n_b):
        ideal_t = raw_beats[i]["t0"]
        f_idx = int(round((ideal_t / max(0.1, speech_end_sec)) * speech_frames))
        min_f = boundaries[-1] + min_cut_frames
        max_f = speech_frames - (n_b - i) * min_cut_frames
        boundaries.append(max(min_f, min(max_f, f_idx)))
    boundaries.append(speech_frames)

    target_vis_speed = float(DIORAMA_VISUAL_PLAYBACK_SPEED)
    ramp_start_speed = float(DIORAMA_ENTRY_RAMP_START_SPEED)
    main_ramp_speed = float(DIORAMA_ENTRY_RAMP_MAIN_SPEED)
    ramp_out_win = 0.35
    ramp_src_head = round(ramp_out_win * ramp_start_speed, 5)
    cuts: list[dict[str, Any]] = []
    for cut_i in range(n_b):
        f0, f1 = boundaries[cut_i], boundaries[cut_i + 1]
        c_frames = max(12, f1 - f0)
        out_dur = c_frames / float(fps)
        beat = raw_beats[cut_i]
        act_no = int(beat["act"])
        s_idx = int(beat["sentence_index"])
        chosen = int(beat["clip_idx"])

        is_split = bool(beat["sub_beat"] == 0 and s_idx in split_by_sentence)
        src_s = 0.15
        avail = max(0.45, (clip_durs[chosen] - 0.12) - src_s)
        ramp_src = ramp_src_head + max(0.0, out_dur - ramp_out_win) * main_ramp_speed
        use_speed_ramp = bool(DIORAMA_ENTRY_SPEED_RAMP and not is_split and out_dur >= 1.30 and avail >= ramp_src)
        if use_speed_ramp:
            src_span = ramp_src
        else:
            speed = target_vis_speed if avail >= out_dur * target_vis_speed else max(0.72, avail / out_dur)
            src_span = min(avail, out_dur * speed)
        src_e = round(src_s + src_span, 4)

        mode = "single"
        secondary_clip_idx = None
        secondary_src = None
        split_labels = None
        if is_split:
            sc = split_by_sentence[s_idx]
            sec_1based = int(sc.get("right_clip_index") or sc.get("bottom_clip_index") or 0)
            b_idx = sec_1based - 1
            sec_avail = max(0.45, (clip_durs[b_idx] - 0.12) - 0.15)
            sec_speed = target_vis_speed if sec_avail >= out_dur * target_vis_speed else max(0.72, sec_avail / out_dur)
            s2_span = min(sec_avail, out_dur * sec_speed)
            req_mode = str(sc.get("mode") or ("split_hstack" if sc.get("right_clip_index") else "split_vstack")).strip()
            mode = req_mode if req_mode in ("split_hstack", "split_vstack") else "split_vstack"
            secondary_clip_idx = b_idx
            secondary_src = [0.15, round(0.15 + s2_span, 4)]
            split_labels = [
                str(sc.get("left_label") or sc.get("top_label") or "EXPECTED"),
                str(sc.get("right_label") or sc.get("bottom_label") or "ACTUAL"),
            ]

        cuts.append(
            {
                "cut_index": cut_i + 1,
                "act": act_no,
                "sentence_index": s_idx,
                "mode": mode,
                "out_start_sec": round(f0 / float(fps), 4),
                "out_end_sec": round(f1 / float(fps), 4),
                "frames": c_frames,
                "duration_sec": round(out_dur, 4),
                "clip_index": chosen + 1,
                "clip_file": clip_files[chosen].name,
                "grammar": clip_grammars.get(chosen, "arch_cutaway_diorama"),
                "src_start_sec": round(src_s, 4),
                "src_end_sec": src_e,
                "speed_ramp": use_speed_ramp,
                "main_speed": main_ramp_speed if use_speed_ramp else round(src_span / max(0.1, out_dur), 4),
                "crop_zoom": 1.00,
                "secondary_clip_index": (secondary_clip_idx + 1 if secondary_clip_idx is not None else None),
                "secondary_clip_file": (clip_files[secondary_clip_idx].name if secondary_clip_idx is not None else None),
                "secondary_src_span": secondary_src,
                "split_labels": split_labels,
                "outro_sky_card": False,
            }
        )

    # 5. Append dedicated final Act 6 Sky Tilt-Up Outro Card cut
    outro_dur = outro_frames / float(fps)
    outro_s = 0.15
    outro_avail = max(0.60, (clip_durs[outro_clip_idx] - 0.12) - outro_s)
    outro_e = round(outro_s + min(outro_avail, outro_dur * target_vis_speed), 4)
    cuts.append(
        {
            "cut_index": len(cuts) + 1,
            "act": DIORAMA_ACT_COUNT,
            "sentence_index": n_sents,
            "mode": "single",
            "out_start_sec": round(speech_frames / float(fps), 4),
            "out_end_sec": round(total_frames / float(fps), 4),
            "frames": outro_frames,
            "duration_sec": round(outro_dur, 4),
            "clip_index": outro_clip_idx + 1,
            "clip_file": clip_files[outro_clip_idx].name,
            "grammar": clip_grammars.get(outro_clip_idx, "arch_cutaway_diorama"),
            "src_start_sec": outro_s,
            "src_end_sec": outro_e,
            "crop_zoom": 1.00,
            "secondary_clip_index": None,
            "secondary_clip_file": None,
            "secondary_src_span": None,
            "split_labels": None,
            "outro_sky_card": True,
        }
    )

    max_reuse = _compute_max_clip_reuse(cuts)
    if max_reuse > DIORAMA_MAX_CLIP_REUSE:
        raise RuntimeError(
            f"build_one_to_one_edl violated zero-reuse lock: max_clip_reuse={max_reuse} > {DIORAMA_MAX_CLIP_REUSE}"
        )
    all_used = {int(c["clip_index"]) for c in cuts} | {
        int(c["secondary_clip_index"]) for c in cuts if c.get("secondary_clip_index") is not None
    }
    return {
        "schema": 6,
        "profile": "neuro_diorama",
        "edl_mode": "one_to_one_zero_reuse",
        "zero_clip_reuse": True,
        "max_clip_reuse": max_reuse,
        "fps": fps,
        "total_frames": total_frames,
        "total_duration_sec": round(total_frames / float(fps), 3),
        "speech_end_sec": round(speech_frames / float(fps), 3),
        "cut_count": len(cuts),
        "avg_cut_duration_sec": round((total_frames / float(fps)) / max(1, len(cuts)), 3),
        "base_clips_used": len(all_used),
        "split_screen_cuts": sum(1 for c in cuts if c["mode"] in ("split_hstack", "split_vstack")),
        "act5_montage_cuts": sum(1 for c in cuts if c["act"] == 5),
        "cuts": cuts,
    }


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


def _resolve_v7_clip_camera(spec: dict[str, Any], idx_0based: int) -> str:
    """Resolves Schema v7/v8 camera_move identically to build_diorama_v7_prompts / build_expressive_v8_prompts."""
    from pipeline.config import EXPRESSIVE_V8_CAMERA_MOVES

    explicit_cam = str(spec.get("camera") or spec.get("camera_move") or "").strip().lower()
    if explicit_cam in DIORAMA_V7_CAMERA_MOVES or explicit_cam in EXPRESSIVE_V8_CAMERA_MOVES:
        return explicit_cam
    if str(spec.get("cut_role") or "").strip().lower() == "outro":
        return "tilt_up"
    cam = _V7_DEFAULT_CAM_CYCLE[idx_0based % len(_V7_DEFAULT_CAM_CYCLE)]
    g = str(spec.get("grammar") or spec.get("visual_grammar") or "").strip().lower()
    if g in ("lowpoly_hands_closeup", "porcelain_hands_closeup", "hands_closeup") and cam in ("tilt_up", "clean_pullback_reveal"):
        cam = "locked_tripod" if cam == "tilt_up" else "gentle_push_in"
    return cam


def _select_v7_source_window(
    clip_path: Path,
    clip_dur: float,
    out_dur: float,
    spec: dict[str, Any] | None = None,
    override_src_start_sec: float | None = None,
    override_src_end_sec: float | None = None,
) -> tuple[float, float]:
    """
    Selects `[src_start_sec, src_span_sec]` inside an 8.0s native Flow clip:
      - Honors explicit `override_src_start_sec` / `override_src_end_sec` (e.g. from R64
        `shift_window_recommendations`) or authored `spec["src_start_sec"]` / `spec["max_src_end_sec"]`.
      - On real video clips with `>= 0.90s` slack, samples sequential low-res grayscale frames and
        scores candidate windows by combining physical motion (`raw_mad`) with upper-center
        `[22%..56%]` focal-zone Canny edge occupancy so `tilt_down` / `pan_*` reveals never slice
        empty-wall pre-roll before the primary subject enters frame.
    """
    spec_d = spec if isinstance(spec, dict) else {}
    allow_slowmo = bool(spec_d.get("allow_slowmo_stretch"))
    max_usable_end = max(0.62, float(clip_dur) - 0.08)
    explicit_end = (
        override_src_end_sec
        if override_src_end_sec is not None
        else (
            spec_d.get("max_src_end_sec")
            if spec_d.get("max_src_end_sec") is not None
            else spec_d.get("src_end_sec")
        )
    )
    if explicit_end is not None:
        try:
            max_usable_end = max(0.62, min(max_usable_end, float(explicit_end)))
        except (TypeError, ValueError):
            pass
    elif bool(spec_d.get("end_reference_image")) and clip_path.exists() and clip_path.stat().st_size >= 8_192:
        end_ref_str = str(spec_d.get("end_reference_image") or "").strip()
        cand_refs = [
            clip_path.parent.parent / "reference_images" / Path(end_ref_str).name,
            clip_path.parent.parent.parent / end_ref_str,
        ]
        ref_png = next((rp for rp in cand_refs if rp.exists() and rp.is_file()), None)
        if ref_png is not None:
            ref_im = cv2.imread(str(ref_png))
            if ref_im is not None:
                ref_g = cv2.cvtColor(cv2.resize(ref_im, (180, 320)), cv2.COLOR_BGR2GRAY).astype(np.float32)
                cap_kf = cv2.VideoCapture(str(clip_path))
                try:
                    if cap_kf.isOpened():
                        fps_kf = max(1.0, float(cap_kf.get(cv2.CAP_PROP_FPS) or 24.0))
                        fc_kf = max(1, int(cap_kf.get(cv2.CAP_PROP_FRAME_COUNT) or 1))
                        best_mae = 999.0
                        best_idx = fc_kf - 1
                        for f_i in range(max(0, fc_kf - 12), fc_kf):
                            cap_kf.set(cv2.CAP_PROP_POS_FRAMES, f_i)
                            ok_f, frm_f = cap_kf.read()
                            if ok_f and frm_f is not None:
                                fg = cv2.cvtColor(cv2.resize(frm_f, (180, 320)), cv2.COLOR_BGR2GRAY).astype(np.float32)
                                m_val = float(np.mean(np.abs(fg - ref_g)))
                                if m_val < best_mae:
                                    best_mae = m_val
                                    best_idx = f_i
                        if best_mae < 24.0:
                            snapped_end = (best_idx + 1) / fps_kf
                            max_usable_end = max(0.62, min(float(clip_dur) - 0.02, snapped_end))
                finally:
                    cap_kf.release()
    min_non_slowmo_span = min(max(0.50, float(clip_dur) - 0.08), float(out_dur))
    if not allow_slowmo and (max_usable_end - 0.06) < min_non_slowmo_span and float(clip_dur) >= float(out_dur) + 0.08:
        # Never accidentally clamp a native full-length clip below out_dur into artificial slow-mo stretch.
        max_usable_end = max(max_usable_end, min(float(clip_dur) - 0.04, 0.06 + min_non_slowmo_span))
    from pipeline.config import (
        EXPRESSIVE_V8_DRONE_CAMERA_MOVES,
        EXPRESSIVE_V8_DRONE_PEAK_CORE_WINDOW_SEC,
        EXPRESSIVE_V8_NEURAL_DIVE_MOVES,
        EXPRESSIVE_V8_NEURAL_DIVE_PEAK_WINDOW_SEC,
        R79M_HUMAN_CUT_MAX_MAIN_SPEED,
    )

    is_r79m_snappy = bool(spec_d.get("_r79m_snappy_human") or spec_d.get("r79m_snappy_human"))
    is_full_traj = bool(spec_d.get("end_reference_image") or spec_d.get("full_trajectory_span"))
    cam_spec_cur = str(spec_d.get("camera_move") or spec_d.get("camera") or "").strip()
    is_sim_3d = (
        str(spec_d.get("grammar") or "") == "brain_simulator_3d"
        or str(spec_d.get("render_engine") or "") == "blender_3d_simulator"
        or "brain_simulator_clips" in str(clip_path)
    )
    if is_sim_3d:
        exp_sim_s = (
            override_src_start_sec
            if override_src_start_sec is not None
            else (
                spec_d.get("src_start_sec")
                if spec_d.get("src_start_sec") is not None
                else spec_d.get("source_start_sec")
            )
        )
        is_flow_brain = (
            str(spec_d.get("render_engine") or "").strip().lower() == "google_flow"
            and "brain_simulator_clips" not in str(clip_path)
        )
        sim_s = 0.0
        if exp_sim_s is not None:
            try:
                sim_s = max(0.0, min(max(0.0, float(clip_dur) - float(out_dur) - 0.04), float(exp_sim_s)))
            except (TypeError, ValueError):
                sim_s = 0.0
        elif is_flow_brain and float(clip_dur) >= float(out_dur) + 0.32:
            sim_s = 0.20
        span_sim = max(0.50, min(max(0.50, float(clip_dur) - sim_s - (0.04 if sim_s > 0.0 else 0.0)), float(out_dur)))
        return round(sim_s, 4), round(span_sim, 4)
    default_s = 0.12
    if cam_spec_cur in EXPRESSIVE_V8_DRONE_CAMERA_MOVES and not is_full_traj:
        peak_s = float(EXPRESSIVE_V8_DRONE_PEAK_CORE_WINDOW_SEC[0])
        if max_usable_end - peak_s >= max(0.50, float(out_dur) * float(DIORAMA_V7_VISUAL_PLAYBACK_SPEED)) + 0.10:
            default_s = peak_s
    elif cam_spec_cur in EXPRESSIVE_V8_NEURAL_DIVE_MOVES and cam_spec_cur != "neural_macro_orbit_hold" and not is_full_traj:
        peak_s = float(EXPRESSIVE_V8_NEURAL_DIVE_PEAK_WINDOW_SEC[0])
        if max_usable_end - peak_s >= max(0.50, float(out_dur) * float(DIORAMA_V7_VISUAL_PLAYBACK_SPEED)) + 0.10:
            default_s = peak_s
    target_src_span = float(out_dur) * float(DIORAMA_V7_VISUAL_PLAYBACK_SPEED)
    if not allow_slowmo:
        target_src_span = max(float(out_dur), target_src_span)
    if not allow_slowmo and (max_usable_end - default_s) < float(out_dur) and (max_usable_end - 0.06) >= float(out_dur):
        default_s = max(0.06, max_usable_end - max(float(out_dur), target_src_span))
    default_avail = max(0.50, max_usable_end - default_s)
    default_span = target_src_span if default_avail >= target_src_span else default_avail

    explicit_start = (
        override_src_start_sec
        if override_src_start_sec is not None
        else (
            spec_d.get("src_start_sec")
            if spec_d.get("src_start_sec") is not None
            else spec_d.get("source_start_sec")
        )
    )
    if explicit_start is not None:
        try:
            exp_s = float(explicit_start)
            if not allow_slowmo:
                needed_span = min(max(0.50, max_usable_end - 0.06), max(float(out_dur), target_src_span))
                latest_s = max(0.06, max_usable_end - needed_span)
                chosen_s = max(0.06, min(latest_s, exp_s))
            elif explicit_end is not None or is_full_traj:
                chosen_s = max(0.06, min(max(0.06, max_usable_end - 0.50), exp_s))
            else:
                latest_s = max(0.08, max_usable_end - default_span)
                chosen_s = max(0.08, min(latest_s, exp_s))
            avail = max(0.50, max_usable_end - chosen_s)
            if is_full_traj and avail >= float(out_dur):
                return round(chosen_s, 4), round(avail, 4)
            return round(chosen_s, 4), round(target_src_span if avail >= target_src_span else avail, 4)
        except (TypeError, ValueError):
            pass

    if is_full_traj and clip_dur >= float(out_dur) + 0.16:
        traj_s = 0.06
        traj_span = max(float(out_dur), max_usable_end - traj_s)
        if is_r79m_snappy:
            traj_span = min(traj_span, float(out_dur) * float(R79M_HUMAN_CUT_MAX_MAIN_SPEED))
        if (
            str(spec_d.get("grammar") or "") in ("architectural_cutaway_portal", "expressive_exterior_establishing")
            and clip_path.exists()
            and clip_path.stat().st_size >= 8_192
            and (max_usable_end - (traj_s + 0.85)) >= traj_span
        ):
            try:
                from pipeline.flow_diorama_sharded_worker import _max_horizontal_plaque_glyph_run

                cap_p = cv2.VideoCapture(str(clip_path))
                if cap_p.isOpened():
                    pfps = max(1.0, float(cap_p.get(cv2.CAP_PROP_FPS) or 24.0))
                    cap_p.set(cv2.CAP_PROP_POS_FRAMES, int(round((traj_s + 0.22) * pfps)))
                    ok_p0, fr_p0 = cap_p.read()
                    if ok_p0 and fr_p0 is not None and _max_horizontal_plaque_glyph_run(fr_p0) >= 5:
                        for cand_nudge in (0.75, 0.95, 1.15):
                            if (max_usable_end - cand_nudge) < traj_span:
                                break
                            cap_p.set(cv2.CAP_PROP_POS_FRAMES, int(round((cand_nudge + 0.18) * pfps)))
                            ok_pn, fr_pn = cap_p.read()
                            if ok_pn and fr_pn is not None and _max_horizontal_plaque_glyph_run(fr_pn) < 5:
                                traj_s = cand_nudge
                                break
                    cap_p.release()
            except Exception:  # noqa: BLE001
                pass
        return round(traj_s, 4), round(traj_span, 4)

    if is_r79m_snappy and clip_dur >= float(out_dur) + 0.12 and clip_path.exists() and clip_path.stat().st_size >= 8_192:
        from pipeline.media_cache import cached_by_clip_stat

        min_s_r79 = 0.16 if (max_usable_end - 0.16) >= float(out_dur) else 0.06
        max_avail_r79 = max(0.50, max_usable_end - min_s_r79)
        # Prefer 1.25x snappy cadence (maps 24fps Flow natively 1:1 onto 30fps without frame-drop judder)
        pref_span = float(out_dur) * 1.25
        if max_avail_r79 >= pref_span:
            r79_span = pref_span
        else:
            r79_span = min(max_avail_r79, max(float(out_dur), float(out_dur) * min(float(R79M_HUMAN_CUT_MAX_MAIN_SPEED), max_avail_r79 / max(0.1, float(out_dur)))))
        r79_span = min(r79_span, float(out_dur) * float(R79M_HUMAN_CUT_MAX_MAIN_SPEED))

        if (max_usable_end - min_s_r79 - r79_span) < 0.24:
            return round(min_s_r79, 4), round(r79_span, 4)

        def _probe_r79_dis_tel(local_clip: Path) -> dict[str, Any]:
            cap_d = cv2.VideoCapture(str(local_clip))
            if not cap_d.isOpened():
                return {"ok": False}
            sfps = max(1.0, float(cap_d.get(cv2.CAP_PROP_FPS) or 24.0))
            sw_d, sh_d = 270, 480
            gs: list[np.ndarray] = []
            ts: list[float] = []
            fi_d = 0
            while True:
                ok_d, bgr_d = cap_d.read()
                if not ok_d:
                    break
                if fi_d % 2 == 0:
                    t_c = fi_d / sfps
                    if t_c <= max_usable_end + 0.06:
                        sm_d = cv2.resize(bgr_d, (sw_d, sh_d), interpolation=cv2.INTER_AREA)
                        gs.append(cv2.cvtColor(sm_d, cv2.COLOR_BGR2GRAY))
                        ts.append(round(t_c, 4))
                fi_d += 1
            cap_d.release()
            if len(gs) < 5:
                return {"ok": False}
            dis_f = cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_FAST)
            b_mask = np.ones((sh_d, sw_d), dtype=bool)
            b_mask[int(sh_d * 0.22) : int(sh_d * 0.82), int(sw_d * 0.18) : int(sw_d * 0.82)] = False
            pairs: list[list[float]] = []
            for k_i in range(len(gs) - 1):
                fl = dis_f.calc(gs[k_i], gs[k_i + 1], None)
                fx_d, fy_d = fl[..., 0], fl[..., 1]
                mvx = float(np.median(fx_d[b_mask]))
                mvy = float(np.median(fy_d[b_mask]))
                res_m = np.hypot(fx_d - mvx, fy_d - mvy)
                roi_m = res_m[int(sh_d * 0.12) : int(sh_d * 0.88), int(sw_d * 0.12) : int(sw_d * 0.88)]
                p90_v = float(np.percentile(roi_m, 90))
                pairs.append([round(0.5 * (ts[k_i] + ts[k_i + 1]), 4), round(p90_v, 4)])
            return {"ok": True, "pairs": pairs}

        r79_tel = cached_by_clip_stat(
            clip_path,
            namespace="v8_r79_dis_tel_v1",
            compute_fn=_probe_r79_dis_tel,
            extra_key=f"{round(max_usable_end, 2)}",
        )
        if isinstance(r79_tel, dict) and r79_tel.get("ok") and r79_tel.get("pairs"):
            p_list = [(float(tm), float(pv)) for tm, pv in r79_tel["pairs"]]
            latest_ws = max(min_s_r79, max_usable_end - r79_span)
            best_ws = min_s_r79
            best_wscore = -1.0
            ws_c = min_s_r79
            while ws_c <= latest_ws + 1e-6:
                we_c = ws_c + r79_span
                vals_w = [pv for tm, pv in p_list if ws_c - 1e-3 <= tm <= we_c + 1e-3]
                if len(vals_w) >= 2:
                    h_w = max(1, len(vals_w) // 2)
                    m_all = float(np.mean(vals_w))
                    sh_r = float(np.mean(vals_w[h_w:]) / max(0.15, float(np.mean(vals_w[:h_w]))))
                    tail_mult = min(1.12, max(0.25, sh_r)) if sh_r < 0.45 else min(1.12, 0.85 + 0.25 * min(1.2, sh_r))
                    dead_head = 0.82 if vals_w[0] < 0.65 else 1.0
                    sc_w = m_all * tail_mult * dead_head
                    if sc_w > best_wscore:
                        best_wscore = sc_w
                        best_ws = ws_c
                ws_c += 0.20
            return round(best_ws, 4), round(r79_span, 4)
        return round(min_s_r79, 4), round(r79_span, 4)

    if (
        out_dur > PORCELAIN_V7_LONG_TAKE_MAX_SEC
        or (max_usable_end - default_s - out_dur) < 0.90
        or not clip_path.exists()
        or clip_path.stat().st_size < 8_192
    ):
        return default_s, round(default_span, 4)

    from pipeline.media_cache import cached_by_clip_stat

    is_brain_clip = str(spec_d.get("grammar") or "").strip() in ("lowpoly_matte_brain", "porcelain_living_brain", "living_brain")
    action_blob = " ".join(
        str(spec_d.get(k) or "") for k in ("action", "prop_action", "consequence", "comparison_action", "internal_mechanism")
    ).lower()
    upward_bias = any(tok in action_blob for tok in ("upward", "blast", "sparks", "airborne", "sky", "shoots", "streaks"))

    def _probe_clip_tel(local_clip: Path) -> dict[str, Any]:
        cap = cv2.VideoCapture(str(local_clip))
        if not cap.isOpened():
            return {"ok": False}
        src_fps = float(cap.get(cv2.CAP_PROP_FPS) or 24.0)
        step = max(1, int(round(src_fps * 0.25)))
        s_t: list[float] = []
        s_g: list[np.ndarray] = []
        s_focal: list[float] = []
        s_chroma: list[float] = []
        f_idx = 0
        while True:
            ok, frm = cap.read()
            if not ok:
                break
            if f_idx % step == 0:
                t_cur = f_idx / max(1.0, src_fps)
                if t_cur <= max_usable_end + 0.05:
                    small_bgr = cv2.resize(frm, (90, 160))
                    g_small = cv2.cvtColor(small_bgr, cv2.COLOR_BGR2GRAY)
                    focal_roi = g_small[int(160 * 0.22) : int(160 * 0.56), int(90 * 0.08) : int(90 * 0.92)]
                    focal_e = float(np.mean(cv2.Canny(focal_roi, 45, 135) > 0))
                    if is_brain_clip:
                        lab_roi = cv2.cvtColor(
                            small_bgr[int(160 * 0.20) : int(160 * 0.72), int(90 * 0.12) : int(90 * 0.88)],
                            cv2.COLOR_BGR2LAB,
                        ).astype(np.float32)
                        chroma_dev = np.hypot(lab_roi[:, :, 1] - 130.5, lab_roi[:, :, 2] - 144.0)
                        s_chroma.append(round(float(np.mean(chroma_dev > 11.5)), 6))
                    else:
                        s_chroma.append(0.0)
                    s_t.append(round(t_cur, 5))
                    s_g.append(g_small)
                    s_focal.append(round(focal_e, 6))
            f_idx += 1
        cap.release()
        if len(s_g) < 6:
            return {"ok": False}
        steps: list[list[float]] = []
        for i in range(1, len(s_g)):
            diff_full = np.abs(s_g[i].astype(np.float32) - s_g[i - 1].astype(np.float32))
            raw_mad = float(np.mean(diff_full))
            upper = float(np.mean(diff_full[8:92, :]))
            lower = float(np.mean(diff_full[92:, :]))
            steps.append([round(0.5 * (s_t[i - 1] + s_t[i]), 5), round(raw_mad, 5), round(upper, 5), round(lower, 5)])
        return {
            "ok": True,
            "sampled_t": s_t,
            "sampled_focal": s_focal,
            "sampled_chroma": s_chroma,
            "steps": steps,
        }

    tel = cached_by_clip_stat(
        clip_path,
        namespace="v7_win_tel_v1",
        compute_fn=_probe_clip_tel,
        extra_key=f"{int(is_brain_clip)}|{round(max_usable_end, 2)}",
    )
    if not isinstance(tel, dict) or not tel.get("ok"):
        return default_s, round(default_span, 4)

    sampled_t = [float(x) for x in tel["sampled_t"]]
    sampled_focal = [float(x) for x in tel["sampled_focal"]]
    sampled_chroma = [float(x) for x in tel["sampled_chroma"]]
    max_clip_focal = max(sampled_focal, default=0.0)
    max_clip_chroma = max(sampled_chroma, default=0.0)
    scores: list[tuple[float, float, float]] = []
    for t_mid, raw_mad, upper, lower in tel["steps"]:
        sc_val = (2.0 * float(upper) + 0.65 * float(lower)) if upward_bias else float(raw_mad)
        scores.append((float(t_mid), sc_val, float(raw_mad)))

    def _focal_at_mid(ws: float, we: float) -> float:
        mid_t = 0.5 * (ws + we)
        best_i = min(range(len(sampled_t)), key=lambda k: abs(sampled_t[k] - mid_t))
        return sampled_focal[best_i]

    def _mean_chroma_in_win(ws: float, we: float) -> float:
        vals = [sampled_chroma[k] for k, t_k in enumerate(sampled_t) if ws - 1e-3 <= t_k <= we + 1e-3]
        return float(np.mean(vals)) if vals else 0.0

    def _window_score(ws: float) -> float:
        we = ws + default_span
        sub = [(v, m) for t_m, v, m in scores if ws <= t_m <= we]
        if not sub:
            return 0.0
        dead_cnt = sum(1 for _, m in sub if m < 0.35)
        penalty = 0.55 ** max(0, dead_cnt - 1)
        mid_focal = _focal_at_mid(ws, we)
        if max_clip_focal >= 0.010 and mid_focal < 0.0045:
            focal_mult = 0.18
        elif mid_focal >= 0.008:
            focal_mult = 1.0 + min(0.35, mid_focal * 6.0)
        else:
            focal_mult = 1.0
        chroma_mult = 1.0
        if is_brain_clip and max_clip_chroma >= 0.015:
            win_ch = _mean_chroma_in_win(ws, we)
            if win_ch < 0.35 * max_clip_chroma:
                chroma_mult = 0.25
            else:
                chroma_mult = 1.0 + 0.65 * (win_ch / max(1e-6, max_clip_chroma))
        return max(0.05 if is_brain_clip else 0.0, float(np.mean([v for v, _ in sub]))) * penalty * focal_mult * chroma_mult

    base_score = _window_score(default_s)
    base_focal = _focal_at_mid(default_s, default_s + default_span)
    base_chroma = _mean_chroma_in_win(default_s, default_s + default_span)
    latest_start = max(default_s, max_usable_end - default_span)
    best_s = default_s
    best_score = base_score
    cand = default_s
    while cand <= latest_start + 1e-6:
        sc_c = _window_score(cand)
        if sc_c > best_score:
            best_score = sc_c
            best_s = cand
        cand += 0.25

    focal_rescue = max_clip_focal >= 0.010 and base_focal < 0.0045 and _focal_at_mid(best_s, best_s + default_span) >= 0.008
    chroma_rescue = (
        is_brain_clip
        and max_clip_chroma >= 0.015
        and base_chroma < 0.35 * max_clip_chroma
        and _mean_chroma_in_win(best_s, best_s + default_span) >= 0.65 * max_clip_chroma
    )
    if focal_rescue or chroma_rescue or best_score >= max(0.75, base_score * 1.12):
        return round(best_s, 4), round(default_span, 4)
    return default_s, round(default_span, 4)


def _normalize_v7_anatomy_badge_text(raw_label: str) -> str:
    """Formats an uppercase 1- or 2-line programmatic ASS anatomical region badge without curly-brace or raw-newline injection."""
    cleaned = (
        str(raw_label or "")
        .replace("{", "")
        .replace("}", "")
        .replace("\r\n", "\\N")
        .replace("\r", "\\N")
        .replace("\n", "\\N")
        .replace("\\n", "\\N")
        .strip()
    )
    if not cleaned:
        return ""
    if "\\N" in cleaned:
        segs = [s.strip().upper() for s in cleaned.split("\\N") if s.strip()]
        return "\\N".join(segs[:2])
    if len(cleaned) > 18:
        for sep in (" · ", " — ", " – ", " | ", " - ", ": "):
            if sep in cleaned:
                left, right = cleaned.split(sep, 1)
                if left.strip() and right.strip():
                    return f"{left.strip().upper()}\\N{right.strip().upper()}"
    return cleaned.upper()


def _resolve_v7_cut_anatomy_label(
    spec: dict[str, Any] | None,
    auto_enabled: bool = True,
) -> tuple[str | None, str | None]:
    """Resolves `(canonical_brain_region, formatted_anatomy_label)` for Schema v7 `porcelain_living_brain` / `lowpoly_matte_brain` clips."""
    if not isinstance(spec, dict):
        return None, None
    grammar = str(spec.get("grammar") or "").strip()
    if grammar not in ("lowpoly_matte_brain", "porcelain_living_brain", "living_brain"):
        return None, None
    from pipeline.anatomy_map import find_regions, plain_name, resolve_region

    raw_reg = str(spec.get("brain_region") or "").strip()
    canon = resolve_region(raw_reg) if raw_reg else None
    if not canon:
        scene_probe = str(spec.get("brain_scene") or spec.get("maquette_scene") or spec.get("scene") or "")
        found = find_regions(scene_probe)
        if found:
            canon = found[0]

    raw_lbl = spec.get("anatomy_label")
    if raw_lbl is False:
        return canon, None
    if isinstance(raw_lbl, str) and raw_lbl.strip():
        return canon, _normalize_v7_anatomy_badge_text(raw_lbl)
    if auto_enabled and canon:
        p_name = plain_name(canon).strip()
        if p_name and p_name.lower() != canon.lower():
            return canon, f"{canon.upper()}\\N{p_name.upper()}"
        return canon, canon.upper()
    return canon, None


def resolve_overlay_window_conflicts(
    resolved_data_stamps: list[dict[str, Any]],
    resolved_anatomy_callouts: list[dict[str, Any]],
    *,
    buffer_sec: float | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """
    R70-M8 / R81 conflict avoidance between R70 HERO Data Stamps and R71/R81 3D Anatomy Leader-Line Callouts:
      - Ensures at least `DATA_STAMP_OVERLAY_BUFFER_SEC` (`2.0s`) separation when sharing the same cut,
        and `DATA_STAMP_CROSS_CUT_BUFFER_SEC` (`0.08s`) across distinct cuts already separated by a hard cut.
      - Shifts/trims the anatomy callout if `>= 1.2s` of non-conflicting duration remains; otherwise suppresses
        the overlapping anatomy callout so R70 HERO graph takes priority.
    """
    from pipeline.config import DATA_STAMP_CROSS_CUT_BUFFER_SEC, DATA_STAMP_OVERLAY_BUFFER_SEC

    buf = float(DATA_STAMP_OVERLAY_BUFFER_SEC if buffer_sec is None else buffer_sec)
    if not resolved_data_stamps or not resolved_anatomy_callouts:
        return list(resolved_anatomy_callouts or []), []

    kept_callouts: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []
    for ac in resolved_anatomy_callouts:
        if not isinstance(ac, dict):
            continue
        ac0 = float(ac.get("start_sec") or 0.0)
        ac1 = float(ac.get("end_sec") or 0.0)
        ac_cut_s = ac.get("cut_start_sec")
        ac_cut_e = ac.get("cut_end_sec")
        adj0, adj1 = ac0, ac1
        suppressed = False
        for ds in resolved_data_stamps:
            if not isinstance(ds, dict):
                continue
            ds0 = float(ds.get("start_sec") or 0.0)
            ds1 = float(ds.get("end_sec") or 0.0)
            is_distinct_cut = (
                buffer_sec is None
                and ac_cut_s is not None
                and ac_cut_e is not None
                and (ds1 <= float(ac_cut_s) + 0.05 or ds0 >= float(ac_cut_e) - 0.05)
            )
            eff_buf = float(DATA_STAMP_CROSS_CUT_BUFFER_SEC) if is_distinct_cut else buf
            if adj0 < ds1 + eff_buf and adj1 > ds0 - eff_buf:
                # Try keeping tail after ds1 + eff_buf or head before ds0 - eff_buf
                if adj1 - (ds1 + eff_buf) >= 1.2:
                    conflicts.append(
                        {
                            "type": "shifted_after_data_stamp",
                            "region": ac.get("canonical_region"),
                            "old_span": [round(adj0, 3), round(adj1, 3)],
                            "new_span": [round(ds1 + eff_buf, 3), round(adj1, 3)],
                        }
                    )
                    adj0 = ds1 + eff_buf
                elif (ds0 - eff_buf) - adj0 >= 1.2:
                    conflicts.append(
                        {
                            "type": "trimmed_before_data_stamp",
                            "region": ac.get("canonical_region"),
                            "old_span": [round(adj0, 3), round(adj1, 3)],
                            "new_span": [round(adj0, 3), round(ds0 - eff_buf, 3)],
                        }
                    )
                    adj1 = ds0 - eff_buf
                else:
                    conflicts.append(
                        {
                            "type": "suppressed_by_data_stamp",
                            "region": ac.get("canonical_region"),
                            "old_span": [round(adj0, 3), round(adj1, 3)],
                            "stamp_span": [round(ds0, 3), round(ds1, 3)],
                        }
                    )
                    suppressed = True
                    break
        if not suppressed and adj1 - adj0 >= 1.0:
            kept_callouts.append(
                {
                    **ac,
                    "start_sec": round(adj0, 3),
                    "end_sec": round(adj1, 3),
                    "duration_sec": round(adj1 - adj0, 3),
                }
            )
    return kept_callouts, conflicts


def _resolve_diorama_clip_files(visuals_dir: Path) -> list[Path]:
    """Collects `flow_native_clips/clip_*.mp4` and lets `brain_simulator_clips/` + verified `archival_insert_clips/` + verified `archival_video_clips/` override matching indices."""
    from pipeline.archival_insert_builder import load_verified_archival_insert_clip_map
    from pipeline.archival_video_builder import load_verified_archival_video_clip_map

    clips_dir = visuals_dir / "flow_native_clips"
    sim_dir = visuals_dir / "brain_simulator_clips"
    by_name: dict[str, Path] = {}
    if clips_dir.is_dir():
        for f in clips_dir.glob("clip_*.mp4"):
            if f.is_file():
                by_name[f.name] = f
    if sim_dir.is_dir():
        for f in sim_dir.glob("clip_*.mp4"):
            if f.is_file():
                by_name[f.name] = f
    for verified_map in (
        load_verified_archival_insert_clip_map(visuals_dir),
        load_verified_archival_video_clip_map(visuals_dir),
    ):
        for clip_num, entry in sorted(verified_map.items()):
            c_path = Path(str(entry.get("resolved_clip_path") or entry.get("clip_path") or ""))
            if c_path.is_file():
                target_key = f"clip_{clip_num:02d}.mp4"
                unpadded_key = f"clip_{clip_num}.mp4"
                if unpadded_key in by_name and target_key not in by_name:
                    del by_name[unpadded_key]
                by_name[target_key] = c_path
    return sorted(by_name.values(), key=numeric_clip_sort_key)


def enforce_combined_r88a_r89_edl_contract(
    project_dir: str | Path,
    edl: dict[str, Any],
    total_duration_sec: float,
) -> dict[str, Any]:
    """
    Validates R88-A + R89 EDL placement (`cut_index >= 2`, `start >= 2.20s` for R89 video cuts)
    and combined quota (`<= 2` cuts total, `<= 10%` combined duration share).
    """
    p_dir = Path(project_dir)
    v_dir = p_dir / "03_visuals"
    r88_mf = v_dir / "archival_inserts_manifest.json"
    r89_mf = v_dir / "archival_videos_manifest.json"
    if not r88_mf.is_file() and not r89_mf.is_file():
        return {"present": False, "passed": True, "r88a_cuts": [], "r89_cuts": []}

    from pipeline.archival_insert_builder import load_verified_archival_insert_clip_map
    from pipeline.archival_video_builder import (
        load_verified_archival_video_clip_map,
        validate_archival_videos_manifest,
        validate_combined_archival_budget,
    )
    from pipeline.config import R89_MIN_CUT_INDEX, R89_MIN_START_SEC

    if r89_mf.is_file():
        r89_val = validate_archival_videos_manifest(
            p_dir,
            episode_duration_sec=total_duration_sec,
            edl=edl,
            check_faces=False,
            strict_sha256=False,
        )
        if not r89_val["passed"]:
            raise ValueError("R89 archival videos contract failed: " + "; ".join(r89_val["issues"]))

    r88_map = load_verified_archival_insert_clip_map(v_dir)
    r89_map = load_verified_archival_video_clip_map(v_dir)

    r88_used: list[dict[str, Any]] = []
    r89_used: list[dict[str, Any]] = []
    for cut in edl.get("cuts") or []:
        if not isinstance(cut, dict) or cut.get("outro_sky_card"):
            continue
        c_idx = int(cut.get("clip_index") or 0)
        cut_num = int(cut.get("cut_index") or 0)
        start_s = float(cut.get("start") or 0.0)
        end_s = float(cut.get("end") or start_s)
        dur_s = max(0.0, end_s - start_s)
        c_file = str(cut.get("clip_file") or "").replace("\\", "/")

        is_r89 = ("archival_video_clips/" in c_file) or (c_idx in r89_map and "flow_native_clips/" not in c_file)
        is_r88 = ("archival_insert_clips/" in c_file) or (c_idx in r88_map and "flow_native_clips/" not in c_file and not is_r89)
        if is_r89:
            if cut_num < R89_MIN_CUT_INDEX or start_s < R89_MIN_START_SEC - 1e-6:
                raise ValueError(
                    f"[r89_cut_placement_forbidden] cut {cut_num} at start={start_s:.2f}s violates "
                    f"Cut>={R89_MIN_CUT_INDEX} & start>={R89_MIN_START_SEC:.2f}s (118pt HookTitle zone)"
                )
            r89_used.append({"cut_index": cut_num, "clip_index": c_idx, "duration_sec": dur_s})
        elif is_r88:
            r88_used.append({"cut_index": cut_num, "clip_index": c_idx, "duration_sec": dur_s})

    edl_budget_issues = validate_combined_archival_budget(
        len(r88_used),
        sum(x["duration_sec"] for x in r88_used),
        len(r89_used),
        sum(x["duration_sec"] for x in r89_used),
        episode_duration_sec=total_duration_sec,
    )
    if edl_budget_issues:
        raise ValueError("; ".join(edl_budget_issues))

    return {
        "present": True,
        "passed": True,
        "r88a_cuts": r88_used,
        "r89_cuts": r89_used,
    }


def build_v7_dynamic_edl(
    visual_plan: dict[str, Any],
    sentence_spans: list[dict[str, Any]],
    clip_files: list[Path],
    speech_end_sec: float,
    total_duration_sec: float,
    script_doc: dict[str, Any] | None = None,
    source_window_overrides: dict[int, Any] | None = None,
    virtual_clip_duration_sec: float | None = None,
) -> dict[str, Any]:
    """
    R63/R66 Schema v7 (`porcelain_cinematic_v7` / `lowpoly_pastel_v7`) 24.0fps Dynamic-Rhythm Zero-Reuse EDL builder:
      - Native `24.0fps` timeline (`<= 4,296 frames` for `<= 179.0s`) at `1.00x` natural motion speed
        (zero `1.26x -> 1.10x` entry speed-ramp knee, zero `24->30fps` pulldown judder).
      - Pairs `0.68-1.35s` rapid multi-beat physical impact sub-cuts with `4.5-7.2s` multi-sentence
        continuous long-take holds (`sentence_index..end_sentence_index`) so `cut_duration_cv >= 0.50`
        while strictly preserving `max_clip_reuse == 1` (`0%` clip reuse).
      - Populates `camera_move` per cut (`1..N`) and top-level camera ratios (`locked_camera_ratio`, `zoom_camera_ratio`).
      - Renders side-by-side comparisons via `split_hstack` (`6px` solid `#000000` vertical divider).
    """
    from pipeline.config import (
        EXPRESSIVE_25D_V8_STYLE_PROFILE,
        EXPRESSIVE_V8_3D_FLIGHT_MOVES,
        EXPRESSIVE_V8_CLIP_COUNT_RANGE,
        EXPRESSIVE_V8_FIRST_15S_MAX_CUT_SEC,
        EXPRESSIVE_V8_FIRST_CUT_MAX_SEC,
        EXPRESSIVE_V8_FLIGHT_SPEED_RAMP_RANGE,
        EXPRESSIVE_V8_HARD_CEILING_SEC,
        EXPRESSIVE_V8_LEGACY_CLIP_COUNT_MIN,
        EXPRESSIVE_V8_LONG_TAKE_MAX_SEC,
        EXPRESSIVE_V8_MAX_CUT_SEC,
        EXPRESSIVE_V8_MIN_CUT_SEC,
        EXPRESSIVE_V8_VIDEO_FPS,
        MICRO_SHORT_CUT_MIN,
        MICRO_SHORT_PROFILE,
        PROMPT_SCHEMA_VERSION_V8,
        SHORTS_90S_CLIP_COUNT_MIN,
        SHORTS_90S_PROFILE,
        SHORTS_EXPRESSIVE_V8_PROFILE,
        resolve_shorts_format_profile,
    )
    from pipeline.depiction_rules import (
        normalize_expressive_v8_grammar,
        normalize_porcelain_v7_grammar,
    )

    from pipeline.config import (
        EXPRESSIVE_V8_LEGACY_FIRST_15S_MAX_CUT_SEC,
        EXPRESSIVE_V8_LEGACY_FIRST_CUT_MAX_SEC,
        EXPRESSIVE_V8_LEGACY_INDOOR_CLIP_COUNT_RANGE,
        EXPRESSIVE_V8_LEGACY_LONG_TAKE_MAX_SEC,
        EXPRESSIVE_V8_LEGACY_MAX_CUT_SEC,
        BRAIN_SIM_ONLY_CLIP_COUNT_RANGE,
        EXPRESSIVE_V8_R76_BRAIN_SIM_MIN_CUT_SEC,
        EXPRESSIVE_V8_R76_CLIP_COUNT_RANGE,
        EXPRESSIVE_V8_R76_HUMAN_MIN_CUT_SEC,
        EXPRESSIVE_V8_R76_MAX_CUT_SEC,
        EXPRESSIVE_V8_SPATIAL_RELAY_MIN_CUT_SEC,
        R80_SPATIAL_FLIGHT_SPEED_RAMP_RANGE,
        R82_BRAIN_MAX_CUT_SEC,
        R82_BRAIN_MIN_CUT_SEC,
        R82_CLIP_COUNT_RANGE,
        R82_FIRST_15S_MAX_CUT_SEC,
        R82_FIRST_CUT_MAX_SEC,
        R82_HUMAN_MAX_CUT_SEC,
        R82_HUMAN_MIN_CUT_SEC,
        SHORTS_EXPRESSIVE_V8_CUT_COUNT_MIN,
        is_brain_sim_only_plan,
        is_r72_open_world_v8_plan,
        is_r76_v8_plan,
        is_r82_dual_speed_pacing_plan,
    )

    n_sents = len(sentence_spans)
    n_clips = len(clip_files)
    is_v8 = is_expressive_v8_plan(visual_plan, script_doc)
    is_brain_only_edl = is_v8 and is_brain_sim_only_plan(visual_plan, script_doc)
    is_r82_edl = is_v8 and is_r82_dual_speed_pacing_plan(visual_plan, script_doc)
    is_r76_edl = is_v8 and is_r76_v8_plan(visual_plan, script_doc)
    is_r72_edl = is_v8 and is_r72_open_world_v8_plan(visual_plan, script_doc)
    fmt_prof_edl = resolve_shorts_format_profile(visual_plan, script_doc)
    if fmt_prof_edl == MICRO_SHORT_PROFILE:
        min_edl_clips = MICRO_SHORT_CUT_MIN
    elif is_brain_only_edl:
        min_edl_clips = BRAIN_SIM_ONLY_CLIP_COUNT_RANGE[0]
    elif is_r82_edl:
        min_edl_clips = R82_CLIP_COUNT_RANGE[0]
    elif is_r76_edl:
        min_edl_clips = EXPRESSIVE_V8_R76_CLIP_COUNT_RANGE[0]
    elif is_v8 or fmt_prof_edl == SHORTS_EXPRESSIVE_V8_PROFILE:
        if bool(visual_plan.get("allow_legacy_v8_clip_count")):
            min_edl_clips = EXPRESSIVE_V8_LEGACY_CLIP_COUNT_MIN
        elif not is_r72_edl:
            min_edl_clips = min(EXPRESSIVE_V8_LEGACY_INDOOR_CLIP_COUNT_RANGE[0], EXPRESSIVE_V8_CLIP_COUNT_RANGE[0])
        else:
            min_edl_clips = EXPRESSIVE_V8_CLIP_COUNT_RANGE[0]
    else:
        min_edl_clips = DIORAMA_CLIP_COUNT_MIN
    if n_clips < min_edl_clips:
        raise ValueError(
            f"build_v7_dynamic_edl requires >= {min_edl_clips} unique clips (got {n_clips})"
        )
    use_porcelain = (not is_v8) and is_porcelain_v7_plan(visual_plan)
    fps = int(visual_plan.get("fps") or (EXPRESSIVE_V8_VIDEO_FPS if is_v8 else DIORAMA_V7_VIDEO_FPS))
    ceiling_edl_frames = int(round(EXPRESSIVE_V8_HARD_CEILING_SEC * fps)) if is_v8 else SHORTS_HARD_CEILING_FRAMES_V7
    total_frames = min(ceiling_edl_frames, max(48, int(round(total_duration_sec * fps))))
    if is_v8:
        speech_frames_actual = min(total_frames - 2, max(24, int(round(speech_end_sec * fps))))
        speech_frames = total_frames
        outro_frames = 0
    else:
        min_outro_f = int(math.ceil(PORCELAIN_V7_MIN_CUT_SEC * fps - 1e-9)) if use_porcelain else 24
        speech_frames = min(total_frames - int(round(DIORAMA_OUTRO_SWELL_SEC * fps)), int(round(speech_end_sec * fps)))
        if use_porcelain:
            max_outro_f = int(PORCELAIN_V7_LONG_TAKE_MAX_SEC * fps)
            speech_frames = max(speech_frames, total_frames - max_outro_f)
        speech_frames = max(24, min(total_frames - min_outro_f, speech_frames))
        speech_frames_actual = speech_frames
        outro_frames = max(min_outro_f, total_frames - speech_frames)
    resolved_style = EXPRESSIVE_25D_V8_STYLE_PROFILE if is_v8 else resolve_diorama_v7_style_profile(visual_plan)
    default_grammar = (
        "expressive_story_world"
        if is_v8
        else ("porcelain_fullbleed_world" if use_porcelain else "lowpoly_fullbleed_world")
    )
    plan_clips = visual_plan.get("clips") if isinstance(visual_plan.get("clips"), list) else []
    auto_anat = False if is_v8 else bool(visual_plan.get("auto_anatomy_labels", True))

    def _v7_edl_clip_dur(cf: Path) -> float:
        p_cf = Path(cf)
        if virtual_clip_duration_sec is not None and (not p_cf.is_file() or p_cf.stat().st_size <= 0):
            return max(0.50, float(virtual_clip_duration_sec))
        raw_cd = float(_clip_duration(p_cf))
        return max(0.50, raw_cd) if raw_cd > 0.05 else 4.0

    clip_durs = [_v7_edl_clip_dur(cf) for cf in clip_files]
    clip_specs: dict[int, dict[str, Any]] = {}
    clip_grammars: dict[int, str] = {}
    clip_locations: dict[int, str] = {}
    clip_cameras: dict[int, str] = {}
    clip_brain_regions: dict[int, str | None] = {}
    clip_anatomy_labels: dict[int, str | None] = {}
    for idx in range(n_clips):
        spec = plan_clips[idx] if idx < len(plan_clips) and isinstance(plan_clips[idx], dict) else {}
        g_raw = str(spec.get("grammar") or spec.get("visual_grammar") or default_grammar)
        if is_v8:
            g_norm = normalize_expressive_v8_grammar(g_raw)
        elif use_porcelain:
            g_norm = normalize_porcelain_v7_grammar(g_raw)
        else:
            g_norm = g_raw
        spec_eff = {**spec, "grammar": g_norm} if spec else {"grammar": g_norm}
        clip_specs[idx] = spec_eff
        clip_grammars[idx] = g_norm
        clip_locations[idx] = str(spec.get("location_id") or "").strip()
        clip_cameras[idx] = _resolve_v7_clip_camera(spec_eff, idx)
        b_reg, a_lbl = _resolve_v7_cut_anatomy_label(spec_eff, auto_enabled=auto_anat)
        clip_brain_regions[idx] = b_reg
        clip_anatomy_labels[idx] = None if is_v8 else a_lbl

    # 1. Identify dedicated outro clip (0-based) — suppressed on `expressive_25d_v8` (`0` outro cards)
    outro_clip_idx = n_clips - 1
    if is_v8:
        reserved_clips: set[int] = set()
    else:
        for idx in range(n_clips):
            spec = clip_specs[idx]
            if str(spec.get("cut_role") or "").strip().lower() == "outro":
                outro_clip_idx = idx
                break
        reserved_clips = {outro_clip_idx}

    is_legacy_lowpoly = (not is_v8) and resolve_diorama_v7_style_profile(visual_plan) == DIORAMA_V7_STYLE_PROFILE

    # 2. Parse split_comparisons (supporting explicit left_clip_index/top_clip_index + right_clip_index/bottom_clip_index)
    split_by_sentence: dict[int, dict[str, Any]] = {}
    split_by_left_clip: dict[int, dict[str, Any]] = {}
    raw_splits = visual_plan.get("split_comparisons") if isinstance(visual_plan.get("split_comparisons"), list) else []
    for sc in raw_splits:
        if not isinstance(sc, dict):
            continue
        s_no = int(sc.get("sentence_index") or 0)
        sec_1based = int(sc.get("right_clip_index") or sc.get("bottom_clip_index") or 0)
        sec_idx = sec_1based - 1
        left_1based = int(sc.get("left_clip_index") or sc.get("top_clip_index") or 0)
        if 1 <= s_no <= n_sents and 0 <= sec_idx < n_clips and sec_idx not in reserved_clips:
            split_by_sentence[s_no] = sc
            if 1 <= left_1based <= n_clips and (left_1based - 1) != sec_idx:
                split_by_left_clip[left_1based - 1] = sc
            reserved_clips.add(sec_idx)

    # 3. Map remaining unique primary clips across sentences (supporting multi-sentence holds & explicit sub-beats)
    clips_by_start_sentence: dict[int, list[tuple[int, int, int, float]]] = {s: [] for s in range(1, n_sents + 1)}
    used_primary: set[int] = set()
    for idx in range(n_clips):
        if idx in reserved_clips:
            continue
        spec = clip_specs[idx]
        role = str(spec.get("cut_role") or "").strip().lower()
        if role in ("split_right", "split_bottom") or (not is_v8 and role == "outro"):
            reserved_clips.add(idx)
            continue
        s_no = spec.get("sentence_index")
        if isinstance(s_no, int) and 1 <= s_no <= n_sents:
            hold_cnt = max(1, int(spec.get("hold_sentences") or 1))
            s_end = int(spec.get("end_sentence_index") or (s_no + hold_cnt - 1))
            s_end = max(s_no, min(n_sents, s_end))
            beat_i = int(spec.get("beat_index") or (len(clips_by_start_sentence[s_no]) + 1))
            b_weight = max(0.25, float(spec.get("beat_weight") or 1.0))
            clips_by_start_sentence[s_no].append((beat_i, idx, s_end, b_weight))
            used_primary.add(idx)

    spare_clips = [idx for idx in range(n_clips) if idx not in reserved_clips and idx not in used_primary]
    spare_cursor = 0

    span_by_s = {int(sp["sentence_index"]): sp for sp in sentence_spans}
    s_act = _sentence_act_map(script_doc or {}, n_sents)
    raw_beats: list[dict[str, Any]] = []
    emitted_primary: set[int] = set()
    s_cursor = 1
    while s_cursor <= n_sents:
        assigned = sorted(clips_by_start_sentence.get(s_cursor) or [], key=lambda x: (x[0], x[1]))
        if assigned:
            s_end = max(x[2] for x in assigned)
            # Never orphan an explicitly authored primary clip on an intermediate sentence inside a multi-sentence hold:
            # split the hold cleanly before the next occupied sentence so every authored primary clip gets its own cut.
            if s_end > s_cursor:
                for mid_s in range(s_cursor + 1, s_end + 1):
                    if clips_by_start_sentence.get(mid_s):
                        s_end = mid_s - 1
                        break
            t0 = float(span_by_s[s_cursor]["start_sec"])
            t1 = float(span_by_s[s_end]["end_sec"])
            dur = max(0.35, t1 - t0)
            eff_weights = [float(x[3]) for x in assigned]
            if is_legacy_lowpoly and len(assigned) == 2 and dur >= 2.15:
                w_sum = sum(eff_weights) or 1.0
                r0 = eff_weights[0] / w_sum
                if 0.39 <= r0 <= 0.61:
                    eff_weights = [0.33, 0.67]
            total_w = sum(eff_weights) or float(len(assigned))
            acc_w = 0.0
            for sub_i, ((_, c_idx, _, _), bw) in enumerate(zip(assigned, eff_weights)):
                b0 = t0 + dur * (acc_w / total_w)
                acc_w += bw
                b1 = t0 + dur * (acc_w / total_w)
                emitted_primary.add(c_idx)
                raw_beats.append(
                    {
                        "act": s_act.get(s_cursor, 1),
                        "sentence_index": s_cursor,
                        "end_sentence_index": s_end,
                        "sub_beat": sub_i,
                        "clip_idx": c_idx,
                        "t0": b0,
                        "t1": b1,
                    }
                )
            s_cursor = s_end + 1
        else:
            # Recycle any previously un-emitted primary clip before drawing from spare_clips
            if spare_cursor >= len(spare_clips):
                recycled = [
                    idx_r
                    for s_prev in range(1, s_cursor)
                    for _, idx_r, _, _ in sorted(clips_by_start_sentence.get(s_prev) or [], key=lambda x: (x[0], x[1]))
                    if idx_r not in emitted_primary and idx_r not in spare_clips
                ]
                if recycled:
                    spare_clips.extend(recycled)
            if spare_cursor < len(spare_clips):
                chosen_idx = spare_clips[spare_cursor]
                spare_cursor += 1
                used_primary.add(chosen_idx)
                emitted_primary.add(chosen_idx)
                sp = span_by_s[s_cursor]
                raw_beats.append(
                    {
                        "act": s_act.get(s_cursor, 1),
                        "sentence_index": s_cursor,
                        "end_sentence_index": s_cursor,
                        "sub_beat": 0,
                        "clip_idx": chosen_idx,
                        "t0": float(sp["start_sec"]),
                        "t1": float(sp["end_sec"]),
                    }
                )
                s_cursor += 1
            elif raw_beats:
                # Extend preceding hold to cover uncovered sentence if clip count is compact
                raw_beats[-1]["end_sentence_index"] = s_cursor
                raw_beats[-1]["t1"] = float(span_by_s[s_cursor]["end_sec"])
                s_cursor += 1
            else:
                raise ValueError(f"build_v7_dynamic_edl has zero usable primary clips at sentence {s_cursor}")

    # Consume any remaining unused spare clips on R72 fast-cut timelines by splitting the longest single-clip beats
    # Rule R76-P forbids mid-sentence spare-clip splitting to eliminate chaotic ADHD flicker.
    while is_r72_edl and (not is_r76_edl) and spare_cursor < len(spare_clips) and raw_beats:
        longest_i = max(
            range(len(raw_beats)),
            key=lambda bi: (
                float(raw_beats[bi]["t1"]) - float(raw_beats[bi]["t0"])
                if "brain" not in str(clip_grammars.get(int(raw_beats[bi]["clip_idx"])) or "")
                and not bool(clip_specs.get(int(raw_beats[bi]["clip_idx"]), {}).get("cameo_easter_egg"))
                else -1.0
            ),
        )
        b_long = raw_beats[longest_i]
        span_l = float(b_long["t1"]) - float(b_long["t0"])
        if span_l < 2.40:
            break
        nxt_spare = spare_clips[spare_cursor]
        spare_cursor += 1
        used_primary.add(nxt_spare)
        emitted_primary.add(nxt_spare)
        mid_t_l = 0.5 * (float(b_long["t0"]) + float(b_long["t1"]))
        raw_beats[longest_i : longest_i + 1] = [
            {**b_long, "sub_beat": int(b_long.get("sub_beat") or 0), "t1": mid_t_l},
            {**b_long, "sub_beat": int(b_long.get("sub_beat") or 0) + 1, "clip_idx": nxt_spare, "t0": mid_t_l},
        ]

    if is_v8:
        if is_r82_edl:
            eff_min_cut_sec = R82_HUMAN_MIN_CUT_SEC
            eff_mid_act_max_sec = R82_BRAIN_MAX_CUT_SEC
            eff_long_take_max_sec = R82_BRAIN_MAX_CUT_SEC
        elif is_r76_edl:
            eff_min_cut_sec = EXPRESSIVE_V8_R76_HUMAN_MIN_CUT_SEC
            eff_mid_act_max_sec = EXPRESSIVE_V8_R76_MAX_CUT_SEC
            eff_long_take_max_sec = EXPRESSIVE_V8_R76_MAX_CUT_SEC
        else:
            eff_min_cut_sec = EXPRESSIVE_V8_MIN_CUT_SEC
            eff_mid_act_max_sec = EXPRESSIVE_V8_MAX_CUT_SEC if is_r72_edl else EXPRESSIVE_V8_LEGACY_MAX_CUT_SEC
            eff_long_take_max_sec = EXPRESSIVE_V8_MAX_CUT_SEC if is_r72_edl else EXPRESSIVE_V8_LEGACY_LONG_TAKE_MAX_SEC
    else:
        eff_min_cut_sec = DIORAMA_V7_RAPID_CUT_MIN_SEC if is_legacy_lowpoly else PORCELAIN_V7_MIN_CUT_SEC
        eff_mid_act_max_sec = DIORAMA_V7_MID_ACT_MAX_CUT_SEC if is_legacy_lowpoly else PORCELAIN_V7_MID_ACT_MAX_CUT_SEC
        eff_long_take_max_sec = DIORAMA_V7_LONG_TAKE_MAX_SEC if is_legacy_lowpoly else PORCELAIN_V7_LONG_TAKE_MAX_SEC

    def _compute_v7_boundaries_and_cv(beats_in: list[dict[str, Any]]) -> tuple[list[int], float]:
        nb_loc = len(beats_in)
        raw_min_cf = (
            int(round(eff_min_cut_sec * fps))
            if is_legacy_lowpoly
            else int(math.ceil(eff_min_cut_sec * fps - 1e-9))
        )
        min_slack_ratio = 0.80 if is_legacy_lowpoly else 0.96
        min_cf = min(
            raw_min_cf,
            max(10, int(speech_frames * min_slack_ratio) // max(1, nb_loc)),
        )
        max_cf = max(min_cf + 1, int(eff_long_take_max_sec * fps))
        max_ss_cf = max(min_cf + 1, int(eff_mid_act_max_sec * fps))
        r82_human_cap_cf = max(min_cf + 1, int(math.floor(R82_HUMAN_MAX_CUT_SEC * fps)))
        r82_brain_cap_cf = max(min_cf + 1, int(math.floor(R82_BRAIN_MAX_CUT_SEC * fps)))
        is_brain_beat_cap = [
            str(clip_grammars.get(int(b.get("clip_idx") or 0)) or "") == "brain_simulator_3d"
            or bool(clip_specs.get(int(b.get("clip_idx") or 0), {}).get("brain_clip"))
            for b in beats_in
        ]
        caps_loc = [
            (r82_brain_cap_cf if is_b_c else r82_human_cap_cf)
            if is_r82_edl
            else (
                max_ss_cf
                if int(b.get("end_sentence_index") or b.get("sentence_index") or 0) == int(b.get("sentence_index") or 0)
                else max_cf
            )
            for b, is_b_c in zip(beats_in, is_brain_beat_cap)
        ]
        if is_v8 and nb_loc > 0 and not bool(visual_plan.get("allow_legacy_v8_clip_count")):
            from pipeline.config import R87_FIRST_CUT_MAX_SEC, is_r87_plan as _is_r87_edl_fn

            is_r87_edl = _is_r87_edl_fn(visual_plan, None)
            eff_first_cap_s = (
                R87_FIRST_CUT_MAX_SEC
                if is_r87_edl
                else (
                    R82_FIRST_CUT_MAX_SEC
                    if is_r82_edl
                    else (
                        5.20
                        if is_r76_edl
                        else (EXPRESSIVE_V8_FIRST_CUT_MAX_SEC if is_r72_edl else EXPRESSIVE_V8_LEGACY_FIRST_CUT_MAX_SEC)
                    )
                )
            )
            eff_f15_cap_s = (
                R82_FIRST_15S_MAX_CUT_SEC
                if is_r82_edl
                else (
                    5.80
                    if is_r76_edl
                    else (EXPRESSIVE_V8_FIRST_15S_MAX_CUT_SEC if is_r72_edl else EXPRESSIVE_V8_LEGACY_FIRST_15S_MAX_CUT_SEC)
                )
            )
            first_cap_cf = max(min_cf, int(round(eff_first_cap_s * fps)))
            first_15_cap_cf = max(min_cf + 1, int(round(eff_f15_cap_s * fps)))
            cand_caps = list(caps_loc)
            cand_caps[0] = min(cand_caps[0], first_cap_cf)
            for idx_cap in range(1, nb_loc):
                if float(beats_in[idx_cap].get("t0") or 0.0) < 15.0:
                    cand_caps[idx_cap] = min(cand_caps[idx_cap], first_15_cap_cf)
            if sum(cand_caps) >= speech_frames:
                caps_loc = cand_caps
            elif (cand_caps[0] + sum(caps_loc[1:])) >= speech_frames:
                caps_loc[0] = cand_caps[0]
        if nb_loc > 0 and sum(caps_loc) < speech_frames <= nb_loc * max_cf:
            caps_loc = [max_cf] * nb_loc
        bnds = [0]
        ref_end_sec = max(0.1, total_duration_sec if is_v8 else speech_end_sec)
        spatial_min_cf = min(
            min_cf,
            max(10, int(math.ceil(EXPRESSIVE_V8_SPATIAL_RELAY_MIN_CUT_SEC * fps - 1e-9))),
        )
        is_spatial_relay_beat = [
            str(clip_grammars.get(int(b.get("clip_idx") or 0)) or "") in ("spatial_3d_arrow_diorama", "expressive_split_contrast")
            or bool(clip_specs.get(int(b.get("clip_idx") or 0), {}).get("spatial_relay_cut"))
            or bool(clip_specs.get(int(b.get("clip_idx") or 0), {}).get("non_spatial_contrast_cut"))
            for b in beats_in
        ]
        init_mins_loc = [
            spatial_min_cf if (is_r76_edl and is_sp_b) else min_cf
            for is_sp_b in is_spatial_relay_beat
        ]
        for i_b in range(1, nb_loc):
            ideal_t = float(beats_in[i_b]["t0"])
            f_idx = int(round((ideal_t / ref_end_sec) * speech_frames))
            min_f = bnds[-1] + init_mins_loc[i_b - 1]
            max_f = speech_frames - sum(init_mins_loc[i_b:])
            bnds.append(max(min_f, min(max_f, f_idx)))
        bnds.append(speech_frames)
        if nb_loc > 0 and speech_frames <= sum(caps_loc):
            lens = [bnds[i_b + 1] - bnds[i_b] for i_b in range(nb_loc)]
            for i_b in range(nb_loc):
                while lens[i_b] > caps_loc[i_b]:
                    best_j = -1
                    for dist in range(1, nb_loc):
                        cand_js = [
                            j_c
                            for j_c in (i_b + dist, i_b - dist)
                            if 0 <= j_c < nb_loc and lens[j_c] < caps_loc[j_c]
                        ]
                        if cand_js:
                            best_j = max(cand_js, key=lambda j_c: caps_loc[j_c] - lens[j_c])
                            break
                    if best_j < 0:
                        break
                    take = min(lens[i_b] - caps_loc[i_b], caps_loc[best_j] - lens[best_j])
                    lens[i_b] -= take
                    lens[best_j] += take
            bnds = [0]
            for ln_f in lens:
                bnds.append(bnds[-1] + ln_f)
        if is_r76_edl and nb_loc > 1:
            eff_b_min_s = R82_BRAIN_MIN_CUT_SEC if is_r82_edl else EXPRESSIVE_V8_R76_BRAIN_SIM_MIN_CUT_SEC
            brain_min_cf = max(min_cf, int(math.ceil((eff_b_min_s + 0.02) * fps - 1e-9)))
            is_brain_beat = [
                str(clip_grammars.get(int(b.get("clip_idx") or 0)) or "") == "brain_simulator_3d"
                or bool(clip_specs.get(int(b.get("clip_idx") or 0), {}).get("brain_clip"))
                for b in beats_in
            ]
            mins_loc = [
                brain_min_cf if is_b else (min_cf if is_r82_edl else (spatial_min_cf if is_sp_b else min_cf))
                for is_b, is_sp_b in zip(is_brain_beat, is_spatial_relay_beat)
            ]
            if sum(mins_loc) <= speech_frames:
                lens_r76 = [bnds[i_b + 1] - bnds[i_b] for i_b in range(nb_loc)]
                for i_b in range(nb_loc):
                    while lens_r76[i_b] < mins_loc[i_b]:
                        best_j = -1
                        for same_dom in (True, False):
                            for dist in range(1, nb_loc):
                                cand_js = [
                                    j_c
                                    for j_c in (i_b + dist, i_b - dist)
                                    if 0 <= j_c < nb_loc
                                    and lens_r76[j_c] > mins_loc[j_c]
                                    and ((is_brain_beat[j_c] == is_brain_beat[i_b]) if same_dom else True)
                                ]
                                if cand_js:
                                    best_j = max(cand_js, key=lambda j_c: lens_r76[j_c] - mins_loc[j_c])
                                    break
                            if best_j >= 0:
                                break
                        if best_j < 0:
                            break
                        give = min(mins_loc[i_b] - lens_r76[i_b], lens_r76[best_j] - mins_loc[best_j])
                        lens_r76[i_b] += give
                        lens_r76[best_j] -= give
                bnds = [0]
                for ln_f in lens_r76:
                    bnds.append(bnds[-1] + ln_f)
        all_durs_loc = [max(10, bnds[i_b + 1] - bnds[i_b]) / float(fps) for i_b in range(nb_loc)]
        if not is_v8:
            all_durs_loc.append(outro_frames / float(fps))
        cv_loc = float(np.std(all_durs_loc) / max(1e-6, np.mean(all_durs_loc))) if all_durs_loc else 0.0
        return bnds, cv_loc

    def _is_swappable_room_beat(b_item: dict[str, Any]) -> bool:
        s0 = int(b_item.get("sentence_index") or 0)
        s1 = int(b_item.get("end_sentence_index") or s0)
        if s0 < 4 or s0 != s1 or int(b_item.get("sub_beat") or 0) != 0:
            return False
        if s0 in split_by_sentence:
            return False
        c_i = int(b_item.get("clip_idx") or 0)
        gm = str(clip_grammars.get(c_i) or "")
        if (
            "brain" in gm
            or "analogy" in gm
            or gm in ("spatial_3d_arrow_diorama", "expressive_split_contrast")
            or bool(clip_specs.get(c_i, {}).get("spatial_relay_cut"))
            or bool(clip_specs.get(c_i, {}).get("non_spatial_contrast_cut"))
            or clip_anatomy_labels.get(c_i)
        ):
            return False
        return True

    boundaries, cur_cv = _compute_v7_boundaries_and_cv(raw_beats)
    if is_legacy_lowpoly:
        target_cv_floor = 0.385
        if cur_cv < target_cv_floor and len(raw_beats) >= 50:
            min_split_dur = 2.54
            max_hold_dur = 6.15
            for _swap_round in range(5):
                if cur_cv >= target_cv_floor:
                    break
                merge_cands: list[tuple[float, int]] = []
                for k_idx in range(len(raw_beats) - 1):
                    ba, bb = raw_beats[k_idx], raw_beats[k_idx + 1]
                    if not (_is_swappable_room_beat(ba) and _is_swappable_room_beat(bb)):
                        continue
                    if int(ba.get("act") or 0) != int(bb.get("act") or 0):
                        continue
                    comb_d = float(bb["t1"]) - float(ba["t0"])
                    if 3.60 <= comb_d <= max_hold_dur and clip_durs[int(ba["clip_idx"])] >= comb_d + 0.35:
                        merge_cands.append((comb_d, k_idx))
                if not merge_cands:
                    break
                merge_cands.sort(reverse=True)
                best_merge_k = merge_cands[0][1]
                freed_clip = int(raw_beats[best_merge_k + 1]["clip_idx"])

                split_cands: list[tuple[float, int]] = []
                for m_idx, bm in enumerate(raw_beats):
                    if m_idx in (best_merge_k, best_merge_k + 1) or not _is_swappable_room_beat(bm):
                        continue
                    m_d = float(bm["t1"]) - float(bm["t0"])
                    if m_d >= min_split_dur:
                        split_cands.append((-abs(m_d - 2.65), m_idx))
                if not split_cands:
                    break
                split_cands.sort(reverse=True)
                best_split_m = split_cands[0][1]

                cand_beats: list[dict[str, Any]] = []
                idx_it = 0
                while idx_it < len(raw_beats):
                    if idx_it == best_merge_k:
                        ba = raw_beats[idx_it]
                        bb = raw_beats[idx_it + 1]
                        cand_beats.append(
                            {
                                **ba,
                                "end_sentence_index": int(bb["end_sentence_index"]),
                                "t1": float(bb["t1"]),
                            }
                        )
                        idx_it += 2
                    elif idx_it == best_split_m:
                        bm = raw_beats[idx_it]
                        mt0 = float(bm["t0"])
                        mt1 = float(bm["t1"])
                        mmid = mt0 + 0.30 * (mt1 - mt0)
                        cand_beats.append({**bm, "sub_beat": 0, "t0": mt0, "t1": mmid})
                        cand_beats.append({**bm, "sub_beat": 1, "clip_idx": freed_clip, "t0": mmid, "t1": mt1})
                        idx_it += 1
                    else:
                        cand_beats.append(dict(raw_beats[idx_it]))
                        idx_it += 1
                cand_bnds, cand_cv = _compute_v7_boundaries_and_cv(cand_beats)
                if cand_cv <= cur_cv:
                    break
                raw_beats = cand_beats
                boundaries = cand_bnds
                cur_cv = cand_cv

    n_b = len(raw_beats)
    from pipeline.config import (
        EXPRESSIVE_V8_DRONE_CAMERA_MOVES,
        R79M_HUMAN_CUT_MAX_MAIN_SPEED,
        is_r79m_character_motion_plan,
    )

    is_r79m_edl = bool(is_v8 and is_r79m_character_motion_plan(visual_plan, script_doc))

    cuts: list[dict[str, Any]] = []
    for cut_i in range(n_b):
        f0, f1 = boundaries[cut_i], boundaries[cut_i + 1]
        c_frames = max(10, f1 - f0)
        out_dur = c_frames / float(fps)
        beat = raw_beats[cut_i]
        act_no = int(beat["act"])
        s_idx = int(beat["sentence_index"])
        s_end = int(beat["end_sentence_index"])
        chosen = int(beat["clip_idx"])
        c_spec_raw = clip_specs.get(chosen) or {}
        is_r79m_human_cut = bool(
            is_r79m_edl
            and str(clip_grammars.get(chosen, default_grammar)) != "brain_simulator_3d"
            and str(c_spec_raw.get("render_engine") or "") != "blender_3d_simulator"
            and str(clip_cameras.get(chosen, "")) not in EXPRESSIVE_V8_DRONE_CAMERA_MOVES
        )

        split_sc = None
        if chosen in split_by_left_clip:
            split_sc = split_by_left_clip[chosen]
        elif beat["sub_beat"] == 0:
            for s_chk in range(s_idx, s_end + 1):
                if s_chk in split_by_sentence:
                    cand_sc = split_by_sentence[s_chk]
                    exp_left = int(cand_sc.get("left_clip_index") or cand_sc.get("top_clip_index") or 0)
                    if exp_left <= 0 or exp_left == chosen + 1:
                        split_sc = cand_sc
                        break

        def _override_start_for_1based(clip_1based: int) -> float | None:
            if not isinstance(source_window_overrides, dict):
                return None
            val = source_window_overrides.get(clip_1based)
            if val is None:
                val = source_window_overrides.get(str(clip_1based))  # type: ignore[arg-type]
            if isinstance(val, (list, tuple)) and len(val) >= 1:
                return float(val[0])
            if isinstance(val, (int, float)):
                return float(val)
            return None

        def _override_end_for_1based(clip_1based: int) -> float | None:
            if not isinstance(source_window_overrides, dict):
                return None
            val = source_window_overrides.get(clip_1based)
            if val is None:
                val = source_window_overrides.get(str(clip_1based))  # type: ignore[arg-type]
            if isinstance(val, (list, tuple)) and len(val) >= 2 and val[1] is not None:
                return float(val[1])
            return None

        spec_for_win = {**c_spec_raw, "_r79m_snappy_human": True} if is_r79m_human_cut else clip_specs.get(chosen)
        src_s, src_span = _select_v7_source_window(
            Path(clip_files[chosen]),
            clip_durs[chosen],
            out_dur,
            spec_for_win,
            override_src_start_sec=_override_start_for_1based(chosen + 1),
            override_src_end_sec=_override_end_for_1based(chosen + 1),
        )
        src_e = round(src_s + src_span, 4)

        mode = "single"
        secondary_clip_idx = None
        secondary_src = None
        secondary_cam = None
        split_labels = None
        if split_sc is not None:
            sec_1based = int(split_sc.get("right_clip_index") or split_sc.get("bottom_clip_index") or 0)
            sec_idx = sec_1based - 1
            s2_s, s2_span = _select_v7_source_window(
                Path(clip_files[sec_idx]),
                clip_durs[sec_idx],
                out_dur,
                clip_specs.get(sec_idx),
                override_src_start_sec=_override_start_for_1based(sec_1based),
                override_src_end_sec=_override_end_for_1based(sec_1based),
            )
            mode = str(split_sc.get("mode") or DIORAMA_V7_SPLIT_MODE).strip()
            if mode not in ("split_hstack", "split_vstack"):
                mode = "split_hstack"
            secondary_clip_idx = sec_idx
            secondary_src = [round(s2_s, 4), round(s2_s + s2_span, 4)]
            secondary_cam = clip_cameras.get(sec_idx, "locked_tripod")
            split_labels = [
                str(split_sc.get("left_label") or split_sc.get("top_label") or "EXPECTED"),
                str(split_sc.get("right_label") or split_sc.get("bottom_label") or "ACTUAL"),
            ]

        c_spec_cur = clip_specs.get(chosen) or {}
        cut_row: dict[str, Any] = {
            "cut_index": cut_i + 1,
            "act": act_no,
            "sentence_index": s_idx,
            "end_sentence_index": s_end,
            "sentence_span": [s_idx, s_end],
            "mode": mode,
            "out_start_sec": round(f0 / float(fps), 4),
            "out_end_sec": round(f1 / float(fps), 4),
            "frames": c_frames,
            "duration_sec": round(out_dur, 4),
            "clip_index": chosen + 1,
            "clip_file": clip_files[chosen].name,
            "grammar": clip_grammars.get(chosen, default_grammar),
            "camera_move": clip_cameras.get(chosen, "locked_tripod"),
            "location_id": clip_locations.get(chosen, ""),
            "brain_region": clip_brain_regions.get(chosen),
            "anatomy_label": (None if is_v8 else (clip_anatomy_labels.get(chosen) if mode == "single" else None)),
            "src_start_sec": round(src_s, 4),
            "src_end_sec": src_e,
            "forbid_slowmo_stretch": bool(c_spec_cur.get("forbid_slowmo_stretch")),
            "allow_slowmo_stretch": bool(c_spec_cur.get("allow_slowmo_stretch")),
            "speed_ramp": False,
            "main_speed": round(src_span / max(0.1, out_dur), 4),
            "crop_zoom": round(max(1.0, min(1.30, float(c_spec_cur.get("crop_zoom") or 1.00))), 4),
            "secondary_clip_index": (secondary_clip_idx + 1 if secondary_clip_idx is not None else None),
            "secondary_clip_file": (clip_files[secondary_clip_idx].name if secondary_clip_idx is not None else None),
            "secondary_camera_move": secondary_cam,
            "secondary_src_span": secondary_src,
            "split_labels": split_labels,
            "outro_sky_card": False,
        }
        if is_v8:
            from pipeline.config import EXPRESSIVE_V8_TRANSITION_TYPES

            raw_tr = str(c_spec_cur.get("transition_out") or c_spec_cur.get("transition_to_next") or "").strip().lower()
            if raw_tr == "dissolve_6f":
                eff_tr = "dissolve_6f" if (cut_i < n_b - 1 and mode == "single") else "action_impact_cut"
            elif raw_tr in EXPRESSIVE_V8_TRANSITION_TYPES:
                eff_tr = raw_tr
            else:
                eff_tr = "hard"
            cut_row["transition_out"] = eff_tr
            cut_row["transition_to_next"] = eff_tr
            cut_row["cameo_easter_egg"] = bool(c_spec_cur.get("cameo_easter_egg"))
            if c_spec_cur.get("end_reference_image"):
                cut_row["end_reference_image"] = str(c_spec_cur["end_reference_image"])
            is_flight_span = bool(
                c_spec_cur.get("end_reference_image")
                or c_spec_cur.get("full_trajectory_span")
                or clip_cameras.get(chosen, "") in EXPRESSIVE_V8_3D_FLIGHT_MOVES
            )
            cut_row["is_3d_flight"] = is_flight_span
            is_r80_spatial = bool(
                str(cut_row.get("grammar") or "") == "spatial_3d_arrow_diorama"
                or c_spec_cur.get("spatial_relay_cut")
            )
            if is_r80_spatial:
                cut_row["spatial_relay_cut"] = True
                if c_spec_cur.get("arrow_3d_mode"):
                    cut_row["arrow_3d_mode"] = str(c_spec_cur.get("arrow_3d_mode")).strip()
            if is_flight_span and (c_spec_cur.get("flight_speed_ramp") is not None or is_r80_spatial):
                raw_rv = c_spec_cur.get("flight_speed_ramp")
                ramp_v = float(raw_rv) if raw_rv is not None else 1.32
                if is_r80_spatial:
                    lo_r, hi_r = R80_SPATIAL_FLIGHT_SPEED_RAMP_RANGE
                elif is_r82_edl or is_r76_edl or (raw_rv is not None and float(raw_rv) < 2.0):
                    lo_r, hi_r = (1.05, float(R79M_HUMAN_CUT_MAX_MAIN_SPEED))
                else:
                    lo_r, hi_r = EXPRESSIVE_V8_FLIGHT_SPEED_RAMP_RANGE
                ramp_v = max(lo_r, min(hi_r, ramp_v))
                max_avail_span = max(0.50, clip_durs[chosen] - 0.08 - src_s)
                ramped_span = min(max_avail_span, out_dur * ramp_v)
                cut_row["src_end_sec"] = round(src_s + ramped_span, 4)
                cut_row["main_speed"] = round(ramped_span / max(0.1, out_dur), 4)
                cut_row["flight_speed_ramp"] = round(ramped_span / max(0.1, out_dur), 3)
            elif is_flight_span:
                cut_row["flight_speed_ramp"] = round(float(cut_row["main_speed"]), 3)
            cur_src_span = float(cut_row["src_end_sec"]) - float(cut_row["src_start_sec"])
            is_sim_cut = (
                str(cut_row.get("grammar") or "") == "brain_simulator_3d"
                or str(c_spec_cur.get("render_engine") or "") == "blender_3d_simulator"
            )
            if (
                not is_sim_cut
                and not bool(cut_row.get("allow_slowmo_stretch"))
                and float(clip_durs[chosen]) >= out_dur + 0.08
                and cur_src_span < out_dur - 0.02
            ):
                safe_clip_end = float(clip_durs[chosen]) - 0.04
                new_s0 = max(0.06, min(float(cut_row["src_start_sec"]), safe_clip_end - out_dur))
                new_s1 = min(safe_clip_end, new_s0 + out_dur)
                cut_row["src_start_sec"] = round(new_s0, 4)
                cut_row["src_end_sec"] = round(new_s1, 4)
                cut_row["main_speed"] = round((new_s1 - new_s0) / max(0.1, out_dur), 4)
            is_r82_non_brain_cut = bool(is_r82_edl and not is_sim_cut)
            if (is_r79m_human_cut or is_r82_non_brain_cut) and float(cut_row["main_speed"]) > float(R79M_HUMAN_CUT_MAX_MAIN_SPEED) + 1e-4:
                clamped_span = round(out_dur * float(R79M_HUMAN_CUT_MAX_MAIN_SPEED), 4)
                cut_row["src_end_sec"] = round(float(cut_row["src_start_sec"]) + clamped_span, 4)
                cut_row["main_speed"] = round(clamped_span / max(0.1, out_dur), 4)
                if "flight_speed_ramp" in cut_row:
                    cut_row["flight_speed_ramp"] = round(float(cut_row["main_speed"]), 3)
            if (
                bool(getattr(_cfg, "EXPRESSIVE_V8_CURVE_RAMP", False) or c_spec_cur.get("force_curve_ramp"))
                and mode == "single"
                and bool(c_spec_cur.get("end_reference_image") or c_spec_cur.get("full_trajectory_span"))
                and (float(cut_row["src_end_sec"]) - float(cut_row["src_start_sec"])) / max(0.1, out_dur) >= 1.28
                and out_dur >= 1.10
            ):
                cut_row["v8_curve_ramp"] = True
            cut_row["diegetic_text_allowlist"] = [
                str(x).strip() for x in (c_spec_cur.get("diegetic_text_allowlist") or []) if str(x).strip()
            ]
            cut_row["lighting_mode"] = str(c_spec_cur.get("lighting_mode") or "daylight_studio")
            if c_spec_cur.get("foley_cue"):
                cut_row["foley_cue"] = str(c_spec_cur["foley_cue"])
            for r74b_k in ("render_engine", "start_brain_region", "end_brain_region", "neural_state", "start_neural_state", "callout_mode", "callout_gloss"):
                if c_spec_cur.get(r74b_k) is not None and str(c_spec_cur.get(r74b_k)).strip():
                    cut_row[r74b_k] = str(c_spec_cur[r74b_k]).strip()
            if isinstance(c_spec_cur.get("r78m_callout"), dict):
                cut_row["r78m_callout"] = dict(c_spec_cur["r78m_callout"])
            if "callout_enabled" in c_spec_cur:
                cut_row["callout_enabled"] = c_spec_cur["callout_enabled"]
            if "anatomy_label" in c_spec_cur:
                cut_row["anatomy_label"] = c_spec_cur["anatomy_label"]
            if c_spec_cur.get("single_start_frame_lock"):
                cut_row["single_start_frame_lock"] = True
            for r82_k in ("human_action_relay", "r72_cold_open_relay", "side_by_side_brain_compare", "stacked_cutaway_brain_compare", "dashed_baseline"):
                if c_spec_cur.get(r82_k):
                    cut_row[r82_k] = True
            if c_spec_cur.get("surgical_cutaway") is not None:
                cut_row["surgical_cutaway"] = bool(c_spec_cur["surgical_cutaway"])
            if c_spec_cur.get("morph_mode"):
                cut_row["morph_mode"] = str(c_spec_cur["morph_mode"]).strip()
            if c_spec_cur.get("stacked_cutaway_brain_compare") and not cut_row.get("secondary_clip_index"):
                cut_row["mode"] = "split_vstack"
        cuts.append(cut_row)

    # Append dedicated final Act 6 Sky Tilt-Up Outro Card cut ONLY for Schema v7 (suppressed on Schema v8)
    if not is_v8:
        outro_dur = outro_frames / float(fps)
        outro_s = 0.12
        outro_avail = max(0.50, (clip_durs[outro_clip_idx] - 0.08) - outro_s)
        outro_span = outro_dur if outro_avail >= outro_dur else outro_avail
        outro_e = round(outro_s + outro_span, 4)
        cuts.append(
            {
                "cut_index": len(cuts) + 1,
                "act": DIORAMA_ACT_COUNT,
                "sentence_index": n_sents,
                "end_sentence_index": n_sents,
                "sentence_span": [n_sents, n_sents],
                "mode": "single",
                "out_start_sec": round(speech_frames / float(fps), 4),
                "out_end_sec": round(total_frames / float(fps), 4),
                "frames": outro_frames,
                "duration_sec": round(outro_dur, 4),
                "clip_index": outro_clip_idx + 1,
                "clip_file": clip_files[outro_clip_idx].name,
                "grammar": clip_grammars.get(outro_clip_idx, default_grammar),
                "camera_move": clip_cameras.get(outro_clip_idx, "tilt_up"),
                "location_id": clip_locations.get(outro_clip_idx, ""),
                "brain_region": None,
                "anatomy_label": None,
                "src_start_sec": outro_s,
                "src_end_sec": outro_e,
                "speed_ramp": False,
                "main_speed": round(outro_span / max(0.1, outro_dur), 4),
                "crop_zoom": 1.00,
                "secondary_clip_index": None,
                "secondary_clip_file": None,
                "secondary_camera_move": None,
                "secondary_src_span": None,
                "split_labels": None,
                "outro_sky_card": True,
            }
        )

    max_reuse = _compute_max_clip_reuse(cuts)
    if bool(visual_plan.get("zero_clip_reuse", True)) and max_reuse > DIORAMA_MAX_CLIP_REUSE:
        raise RuntimeError(
            f"build_v7_dynamic_edl violated zero-reuse lock: max_clip_reuse={max_reuse} > {DIORAMA_MAX_CLIP_REUSE}"
        )

    cut_durs = [float(c["duration_sec"]) for c in cuts]
    mean_cut = float(np.mean(cut_durs)) if cut_durs else 0.0
    std_cut = float(np.std(cut_durs)) if cut_durs else 0.0
    cut_cv = round(std_cut / max(1e-6, mean_cut), 4)
    rapid_ratio = round(sum(1 for d in cut_durs if d <= 1.50) / max(1, len(cut_durs)), 4)

    cam_counts: dict[str, int] = {m: 0 for m in DIORAMA_V7_CAMERA_MOVES}
    for c in cuts:
        cm = str(c.get("camera_move") or "locked_tripod")
        cam_counts[cm] = cam_counts.get(cm, 0) + 1
    n_c_tot = max(1, len(cuts))
    locked_cam_ratio = round(cam_counts.get("locked_tripod", 0) / float(n_c_tot), 4)
    zoom_cam_ratio = round(
        (cam_counts.get("gentle_push_in", 0) + cam_counts.get("clean_pullback_reveal", 0)) / float(n_c_tot),
        4,
    )

    # Count A-B-A spatial location returns (same location_id returning after >=1 different location)
    seen_locs: dict[str, int] = {}
    aba_returns = 0
    for idx_c, c in enumerate(cuts):
        loc = str(c.get("location_id") or "").strip()
        if not loc:
            continue
        if loc in seen_locs and idx_c - seen_locs[loc] >= 2:
            aba_returns += 1
        seen_locs[loc] = idx_c

    from pipeline.anatomy_label_overlay import resolve_anatomy_callout_windows
    from pipeline.data_stamp_overlay import resolve_data_stamp_windows

    allow_v8_alpha_dissolves = bool((visual_plan or {}).get("allow_alpha_dissolves"))
    if is_v8 and not allow_v8_alpha_dissolves:
        _alpha_fade_names = {
            "dissolve_6f",
            "dissolve_8f",
            "dissolve_12f",
            "dissolve_15f",
            "match_cut_bridge",
            "split_screen_wipe",
            "daisy_chain_bridge",
        }
        for c in cuts:
            if str(c.get("transition_out") or "").strip().lower() in _alpha_fade_names:
                c["transition_out"] = "action_impact_cut"
                c["transition_to_next"] = "action_impact_cut"

    resolved_data_stamps = resolve_data_stamp_windows(
        script_doc,
        sentence_spans,
        round(total_frames / float(fps), 3),
    )
    if is_v8 and resolved_data_stamps and cuts:
        for ds in resolved_data_stamps:
            ds_s_idx = int(ds.get("sentence_index") or 0)
            ds_e_idx = int(ds.get("end_sentence_index") or ds_s_idx)
            matching_cuts = [
                c_it
                for c_it in cuts
                if int(c_it.get("sentence_index") or 0) <= ds_e_idx
                and int(c_it.get("end_sentence_index") or c_it.get("sentence_index") or 0) >= ds_s_idx
            ]
            if matching_cuts:
                c_bound_s = float(matching_cuts[0].get("out_start_sec") or 0.0)
                c_bound_e = float(matching_cuts[-1].get("out_end_sec") or 0.0)
                ds_t0 = float(ds.get("start_sec") or 0.0)
                ds_t1 = float(ds.get("end_sec") or 0.0)
                ds_dur = max(1.0, ds_t1 - ds_t0)
                if (c_bound_e - c_bound_s) >= 1.60 and (ds_t0 < c_bound_s + 0.05 or ds_t1 > c_bound_e - 0.05):
                    new_t0 = max(ds_t0, c_bound_s + 0.06)
                    new_t1 = min(c_bound_e - 0.06, new_t0 + ds_dur)
                    if new_t1 - new_t0 >= 1.0:
                        ds["start_sec"] = round(new_t0, 3)
                        ds["end_sec"] = round(new_t1, 3)
                        ds["duration_sec"] = round(new_t1 - new_t0, 3)
    data_stamp_spans = [[float(ds["start_sec"]), float(ds["end_sec"])] for ds in resolved_data_stamps]
    vdir_hint = (visual_plan or {}).get("_visuals_dir")
    raw_anatomy_callouts = (
        resolve_anatomy_callout_windows(
            {"cuts": cuts},
            visual_plan,
            visuals_dir=Path(str(vdir_hint)) if vdir_hint else None,
        )
        if is_v8
        else []
    )
    resolved_anatomy_callouts, overlay_conflicts_resolved = resolve_overlay_window_conflicts(
        resolved_data_stamps,
        raw_anatomy_callouts,
    )
    anatomy_callout_spans = [[float(ac["start_sec"]), float(ac["end_sec"])] for ac in resolved_anatomy_callouts]
    for c in cuts:
        c_s0 = float(c.get("out_start_sec") or 0.0)
        c_e0 = float(c.get("out_end_sec") or 0.0)
        c["has_data_stamp"] = any(ds0 < c_e0 - 0.04 and ds1 > c_s0 + 0.04 for ds0, ds1 in data_stamp_spans)
        c["has_anatomy_callout"] = any(ac0 < c_e0 - 0.04 and ac1 > c_s0 + 0.04 for ac0, ac1 in anatomy_callout_spans)

    all_used = {int(c["clip_index"]) for c in cuts} | {
        int(c["secondary_clip_index"]) for c in cuts if c.get("secondary_clip_index") is not None
    }
    edl_out: dict[str, Any] = {
        "schema": (PROMPT_SCHEMA_VERSION_V8 if is_v8 else PROMPT_SCHEMA_VERSION_V7),
        "profile": "neuro_diorama",
        "style_profile": resolved_style,
        "edl_mode": (f"v8_expressive_dynamic_{fps}fps" if is_v8 else "v7_dynamic_zero_reuse_24fps"),
        "playback_speed": float(DIORAMA_V7_VISUAL_PLAYBACK_SPEED),
        "zero_clip_reuse": bool(max_reuse <= 1),
        "max_clip_reuse": max_reuse,
        "fps": fps,
        "total_frames": total_frames,
        "total_duration_sec": round(total_frames / float(fps), 3),
        "speech_end_sec": round((speech_frames_actual if is_v8 else speech_frames) / float(fps), 3),
        "cut_count": len(cuts),
        "avg_cut_duration_sec": round(mean_cut, 3),
        "cut_duration_std_sec": round(std_cut, 3),
        "cut_duration_cv": cut_cv,
        "rapid_cut_ratio": rapid_ratio,
        "max_cut_duration_sec": round(max(cut_durs) if cut_durs else 0.0, 3),
        "min_cut_duration_sec": round(min(cut_durs) if cut_durs else 0.0, 3),
        "camera_move_counts": cam_counts,
        "locked_camera_ratio": locked_cam_ratio,
        "zoom_camera_ratio": zoom_cam_ratio,
        "pan_left_cuts": cam_counts.get("pan_left", 0),
        "pan_right_cuts": cam_counts.get("pan_right", 0),
        "aba_location_returns": aba_returns,
        "base_clips_used": len(all_used),
        "split_screen_cuts": sum(1 for c in cuts if c["mode"] in ("split_hstack", "split_vstack")),
        "split_hstack_cuts": sum(1 for c in cuts if c["mode"] == "split_hstack"),
        "act5_montage_cuts": sum(1 for c in cuts if c["act"] == 5),
        "data_stamp_spans": data_stamp_spans,
        "resolved_data_stamps": resolved_data_stamps,
        "anatomy_callout_spans": anatomy_callout_spans,
        "resolved_anatomy_callouts": resolved_anatomy_callouts,
        "overlay_conflicts_resolved": overlay_conflicts_resolved,
        "cuts": cuts,
    }
    if is_v8:
        edl_out["cameo_cuts"] = sum(1 for c in cuts if c.get("cameo_easter_egg"))
        edl_out["dissolve_6f_cuts"] = sum(1 for c in cuts if c.get("transition_out") == "dissolve_6f")
        edl_out["camera_bridge_cuts"] = sum(
            1
            for c in cuts[:-1]
            if str(c.get("transition_out") or "").strip().lower() not in ("", "hard", "action_impact_cut", "seamless_relay_cut")
        )
    return edl_out


def build_crosscut_edl(
    visual_plan: dict[str, Any],
    sentence_spans: list[dict[str, Any]],
    clip_files: list[Path],
    speech_end_sec: float,
    total_duration_sec: float,
    script_doc: dict[str, Any] | None = None,
    source_window_overrides: dict[int, Any] | None = None,
    virtual_clip_duration_sec: float | None = None,
) -> dict[str, Any]:
    """
    R58 / R63 / R68 NLE Edit Decision List builder:
      - Dispatches to Schema v7/v8 `build_v7_dynamic_edl` (`24.0fps`, `0%` reuse)
        whenever `is_diorama_v7_plan(visual_plan)` or `is_expressive_v8_plan(visual_plan, script_doc)` is True.
      - Dispatches to Schema v6.1 `build_one_to_one_edl` (`0%` clip reuse, `1.00x` framing)
        whenever `visual_plan.get("zero_clip_reuse")` is True or `len(clip_files) >= len(sentence_spans) + 1`.
      - Preserves legacy multi-window interleaving fallback only for legacy synthetic `20-26`-clip fixtures.
    """
    if is_diorama_v7_plan(visual_plan) or is_expressive_v8_plan(visual_plan, script_doc):
        return build_v7_dynamic_edl(
            visual_plan=visual_plan,
            sentence_spans=sentence_spans,
            clip_files=clip_files,
            speech_end_sec=speech_end_sec,
            total_duration_sec=total_duration_sec,
            script_doc=script_doc,
            source_window_overrides=source_window_overrides,
            virtual_clip_duration_sec=virtual_clip_duration_sec,
        )
    if bool(visual_plan.get("zero_clip_reuse")) or len(clip_files) >= len(sentence_spans) + 1:
        return build_one_to_one_edl(
            visual_plan=visual_plan,
            sentence_spans=sentence_spans,
            clip_files=clip_files,
            speech_end_sec=speech_end_sec,
            total_duration_sec=total_duration_sec,
            script_doc=script_doc,
            virtual_clip_duration_sec=virtual_clip_duration_sec,
        )
    if len(clip_files) < DIORAMA_CLIP_COUNT_MIN:
        raise ValueError(
            f"build_crosscut_edl requires >= {DIORAMA_CLIP_COUNT_MIN} Flow clips (got {len(clip_files)})"
        )
    fps = int(VIDEO_FPS)
    total_frames = min(SHORTS_HARD_CEILING_FRAMES, max(60, int(round(total_duration_sec * fps))))
    speech_frames = min(total_frames - int(round(DIORAMA_OUTRO_SWELL_SEC * fps)), int(round(speech_end_sec * fps)))
    speech_frames = max(30, speech_frames)
    outro_frames = max(30, total_frames - speech_frames)

    plan_clips = visual_plan.get("clips") if isinstance(visual_plan.get("clips"), list) else []
    n_clips = len(clip_files)
    clip_durs = [
        (
            max(0.50, float(virtual_clip_duration_sec))
            if (virtual_clip_duration_sec is not None and (not Path(cf).is_file() or Path(cf).stat().st_size <= 0))
            else (max(0.50, raw_cd) if (raw_cd := float(_clip_duration(Path(cf)))) > 0.05 else 4.0)
        )
        for cf in clip_files
    ]

    # Group 0-based clip indices by Act (1..6)
    act_pools: dict[int, list[int]] = {a: [] for a in range(1, DIORAMA_ACT_COUNT + 1)}
    clip_grammars: dict[int, str] = {}
    for idx in range(n_clips):
        spec = plan_clips[idx] if idx < len(plan_clips) and isinstance(plan_clips[idx], dict) else {}
        act_no = int(spec.get("act") or min(DIORAMA_ACT_COUNT, (idx * DIORAMA_ACT_COUNT) // n_clips + 1))
        act_no = max(1, min(DIORAMA_ACT_COUNT, act_no))
        act_pools[act_no].append(idx)
        clip_grammars[idx] = str(spec.get("grammar") or "arch_cutaway_diorama")
    for a in range(1, DIORAMA_ACT_COUNT + 1):
        if not act_pools[a]:
            act_pools[a] = [min(n_clips - 1, (a - 1) * max(1, n_clips // DIORAMA_ACT_COUNT))]

    # Reserve final clip in Act 6 pool for the sky tilt-up outro card
    outro_clip_idx = act_pools[DIORAMA_ACT_COUNT][-1]

    # Build beat intervals across [0, speech_frames]
    s_act = _sentence_act_map(script_doc or {}, len(sentence_spans))
    raw_beats: list[dict[str, Any]] = []
    for sp in sentence_spans:
        s_idx = int(sp["sentence_index"])
        act_no = s_act.get(s_idx, 1)
        t0 = float(sp["start_sec"])
        t1 = float(sp["end_sec"])
        dur = max(0.35, t1 - t0)
        if act_no == 5 and dur >= 1.4:
            # Act 5 crisis climax: slice sentences into fast rhythmic 0.65s montage beats
            target_sub = round((DIORAMA_ACT5_MONTAGE_CUT_MIN_SEC + DIORAMA_ACT5_MONTAGE_CUT_MAX_SEC) * 0.5, 2)
            k = max(2, min(4, int(round(dur / target_sub))))
        elif dur >= 2.25:
            k = 2
        else:
            k = 1
        for sub_i in range(k):
            b0 = t0 + dur * (sub_i / float(k))
            b1 = t0 + dur * ((sub_i + 1) / float(k))
            raw_beats.append({"act": act_no, "sentence_index": s_idx, "t0": b0, "t1": b1})

    # Tune cut count cleanly into profile-appropriate [cut_min, cut_max - 1] (+1 outro cut)
    from pipeline.config import (
        MICRO_SHORT_CUT_MAX,
        MICRO_SHORT_CUT_MIN,
        MICRO_SHORT_PROFILE,
        SHORTS_90S_CUT_COUNT_MAX,
        SHORTS_90S_CUT_COUNT_MIN,
        SHORTS_90S_PROFILE,
        resolve_shorts_format_profile,
    )

    cc_fmt = resolve_shorts_format_profile(
        visual_plan,
        script_doc,
        {"sentences": sentence_spans, "total_duration_sec": total_duration_sec},
    )
    if cc_fmt == MICRO_SHORT_PROFILE:
        min_speech_cuts = MICRO_SHORT_CUT_MIN - 1
        max_speech_cuts = MICRO_SHORT_CUT_MAX - 1
    elif cc_fmt == SHORTS_90S_PROFILE:
        min_speech_cuts = SHORTS_90S_CUT_COUNT_MIN - 1
        max_speech_cuts = SHORTS_90S_CUT_COUNT_MAX - 1
    else:
        min_speech_cuts = DIORAMA_TARGET_CUT_MIN - 1
        max_speech_cuts = DIORAMA_TARGET_CUT_MAX - 1
    while len(raw_beats) < min_speech_cuts:
        # Split the longest beat
        longest_i = max(range(len(raw_beats)), key=lambda i: raw_beats[i]["t1"] - raw_beats[i]["t0"])
        b = raw_beats[longest_i]
        mid = 0.5 * (b["t0"] + b["t1"])
        if b["t1"] - b["t0"] < 0.70:
            break
        raw_beats[longest_i : longest_i + 1] = [
            {"act": b["act"], "sentence_index": b["sentence_index"], "t0": b["t0"], "t1": mid},
            {"act": b["act"], "sentence_index": b["sentence_index"], "t0": mid, "t1": b["t1"]},
        ]
    while len(raw_beats) > max_speech_cuts:
        # Merge shortest adjacent pair in the same act
        best_i = min(
            range(len(raw_beats) - 1),
            key=lambda i: (0 if raw_beats[i]["act"] == raw_beats[i + 1]["act"] else 100.0)
            + (raw_beats[i + 1]["t1"] - raw_beats[i]["t0"]),
        )
        merged = {
            "act": raw_beats[best_i]["act"],
            "sentence_index": raw_beats[best_i]["sentence_index"],
            "t0": raw_beats[best_i]["t0"],
            "t1": raw_beats[best_i + 1]["t1"],
        }
        raw_beats[best_i : best_i + 2] = [merged]

    # Convert beats to contiguous frame-exact spans covering [0, speech_frames]
    n_b = len(raw_beats)
    speech_dur_s = speech_frames / float(fps)
    boundaries = [0]
    for i in range(1, n_b):
        ideal_t = raw_beats[i]["t0"]
        f_idx = int(round((ideal_t / max(0.1, speech_end_sec)) * speech_frames))
        min_f = boundaries[-1] + 12  # >= 0.40s per cut
        max_f = speech_frames - (n_b - i) * 12
        boundaries.append(max(min_f, min(max_f, f_idx)))
    boundaries.append(speech_frames)

    # Track monotonic source cursors per clip so no source window is ever reused
    cursors = [0.15 for _ in range(n_clips)]
    slice_visits = [0 for _ in range(n_clips)]
    act_rr = {a: 0 for a in range(1, DIORAMA_ACT_COUNT + 1)}
    split_cfg = visual_plan.get("split_screen") if isinstance(visual_plan.get("split_screen"), dict) else {}
    raw_splits = visual_plan.get("split_comparisons") if isinstance(visual_plan.get("split_comparisons"), list) else []
    first_split_comp = raw_splits[0] if raw_splits and isinstance(raw_splits[0], dict) else {}
    act3_seen = 0

    cuts: list[dict[str, Any]] = []
    prev_clip_idx = -1
    for cut_i in range(n_b):
        f0, f1 = boundaries[cut_i], boundaries[cut_i + 1]
        c_frames = max(12, f1 - f0)
        out_dur = c_frames / float(fps)
        beat = raw_beats[cut_i]
        act_no = int(beat["act"])
        pool = list(act_pools[act_no])

        # Select next clip via round-robin interleaving (never same clip back-to-back when pool > 1)
        chosen = pool[act_rr[act_no] % len(pool)]
        act_rr[act_no] += 1
        if chosen == prev_clip_idx and len(pool) > 1:
            chosen = pool[act_rr[act_no] % len(pool)]
            act_rr[act_no] += 1
        # If chosen clip has little remaining footage, pick clip in pool (or global) with most remaining headroom
        rem = (clip_durs[chosen] - 0.15) - cursors[chosen]
        if rem < out_dur * 0.78:
            best_pool = max(pool, key=lambda idx: (clip_durs[idx] - 0.15) - cursors[idx])
            if (clip_durs[best_pool] - 0.15) - cursors[best_pool] >= out_dur * 0.78 and best_pool != prev_clip_idx:
                chosen = best_pool
            else:
                candidates = [idx for idx in range(n_clips) if idx != prev_clip_idx and idx != outro_clip_idx]
                if candidates:
                    chosen = max(candidates, key=lambda idx: (clip_durs[idx] - 0.15) - cursors[idx])

        avail = max(0.45, (clip_durs[chosen] - 0.12) - cursors[chosen])
        speed = 1.00
        if avail < out_dur:
            speed = max(0.75, avail / out_dur)
        src_span = min(avail, out_dur * speed)
        src_s = round(cursors[chosen], 4)
        src_e = round(src_s + src_span, 4)
        cursors[chosen] = round(src_e + 0.05, 4)

        visit_no = slice_visits[chosen]
        slice_visits[chosen] += 1
        crop_zoom = DIORAMA_SLICE_CROPS[min(visit_no, len(DIORAMA_SLICE_CROPS) - 1)]

        mode = "single"
        secondary_clip_idx = None
        secondary_src = None
        if act_no == 3:
            act3_seen += 1
            if act3_seen in (2, 5) and len(pool) >= 2 and out_dur >= 1.2:
                sec_candidates = [idx for idx in pool if idx != chosen]
                sec_idx = sec_candidates[0]
                sec_avail = max(0.45, (clip_durs[sec_idx] - 0.12) - cursors[sec_idx])
                if sec_avail >= out_dur * 0.80:
                    mode = "split_vstack"
                    secondary_clip_idx = sec_idx
                    s2_span = min(sec_avail, out_dur)
                    secondary_src = [round(cursors[sec_idx], 4), round(cursors[sec_idx] + s2_span, 4)]
                    cursors[sec_idx] = round(cursors[sec_idx] + s2_span + 0.05, 4)

        top_lbl = str(first_split_comp.get("top_label") or split_cfg.get("left_label") or "EXPECTED")
        bot_lbl = str(first_split_comp.get("bottom_label") or split_cfg.get("right_label") or "ACTUAL")
        cuts.append(
            {
                "cut_index": cut_i + 1,
                "act": act_no,
                "sentence_index": beat["sentence_index"],
                "mode": mode,
                "out_start_sec": round(f0 / float(fps), 4),
                "out_end_sec": round(f1 / float(fps), 4),
                "frames": c_frames,
                "duration_sec": round(out_dur, 4),
                "clip_index": chosen + 1,
                "clip_file": clip_files[chosen].name,
                "grammar": clip_grammars.get(chosen, "arch_cutaway_diorama"),
                "src_start_sec": src_s,
                "src_end_sec": src_e,
                "crop_zoom": crop_zoom,
                "secondary_clip_index": (secondary_clip_idx + 1 if secondary_clip_idx is not None else None),
                "secondary_clip_file": (clip_files[secondary_clip_idx].name if secondary_clip_idx is not None else None),
                "secondary_src_span": secondary_src,
                "split_labels": ([top_lbl, bot_lbl] if mode == "split_vstack" else None),
                "outro_sky_card": False,
            }
        )
        prev_clip_idx = chosen

    # Append final Act 6 Sky Tilt-Up Outro Card cut
    outro_dur = outro_frames / float(fps)
    outro_avail = max(0.6, clip_durs[outro_clip_idx] - 0.20)
    outro_s = max(0.10, min(cursors[outro_clip_idx], clip_durs[outro_clip_idx] - min(outro_avail, outro_dur + 0.15)))
    outro_e = min(clip_durs[outro_clip_idx] - 0.05, outro_s + min(outro_avail, outro_dur))
    cuts.append(
        {
            "cut_index": len(cuts) + 1,
            "act": DIORAMA_ACT_COUNT,
            "sentence_index": len(sentence_spans),
            "mode": "single",
            "out_start_sec": round(speech_frames / float(fps), 4),
            "out_end_sec": round(total_frames / float(fps), 4),
            "frames": outro_frames,
            "duration_sec": round(outro_dur, 4),
            "clip_index": outro_clip_idx + 1,
            "clip_file": clip_files[outro_clip_idx].name,
            "grammar": clip_grammars.get(outro_clip_idx, "arch_cutaway_diorama"),
            "src_start_sec": round(outro_s, 4),
            "src_end_sec": round(outro_e, 4),
            "crop_zoom": 1.00,
            "secondary_clip_index": None,
            "secondary_clip_file": None,
            "secondary_src_span": None,
            "split_labels": None,
            "outro_sky_card": True,
        }
    )

    return {
        "schema": 6,
        "profile": "neuro_diorama",
        "edl_mode": "legacy_crosscut",
        "zero_clip_reuse": False,
        "max_clip_reuse": _compute_max_clip_reuse(cuts),
        "fps": fps,
        "total_frames": total_frames,
        "total_duration_sec": round(total_frames / float(fps), 3),
        "speech_end_sec": round(speech_frames / float(fps), 3),
        "cut_count": len(cuts),
        "avg_cut_duration_sec": round((total_frames / float(fps)) / max(1, len(cuts)), 3),
        "base_clips_used": len({c["clip_index"] for c in cuts}),
        "split_screen_cuts": sum(1 for c in cuts if c["mode"] in ("split_hstack", "split_vstack")),
        "act5_montage_cuts": sum(1 for c in cuts if c["act"] == 5),
        "cuts": cuts,
    }


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


def _format_v8_highlighted_phrase(disp_text: str) -> str:
    """Wraps 1 anchor keyword per phrase in `#FFE600` (`{\\c&H00E6FF&}...{\\c&HFFFFFF&}`) while keeping other words `#FFFFFF`."""
    toks = [t for t in str(disp_text or "").split(" ") if t]
    if not toks:
        return disp_text
    best_i = -1
    best_score = -1.0
    for idx_t, tok in enumerate(toks):
        alpha_num = re.sub(r"[^a-zA-Z0-9%]", "", tok)
        low = alpha_num.lower()
        if not low:
            continue
        if any(ch.isdigit() for ch in alpha_num):
            score = 100.0 + len(alpha_num)
        elif low in _V8_POWER_TOKENS or tok.endswith(("!", "?")):
            score = 80.0 + len(alpha_num)
        elif low not in _V8_STOPWORDS and len(alpha_num) >= 3:
            score = 40.0 + len(alpha_num)
        else:
            score = 5.0 + len(alpha_num) * 0.5
        if score > best_score:
            best_score = score
            best_i = idx_t
    if best_i < 0:
        return " ".join(toks)
    out_toks = list(toks)
    if len(out_toks) == 1:
        out_toks[0] = f"{{\\c&H00E6FF&}}{out_toks[0]}"
    elif best_i == len(out_toks) - 1:
        out_toks[best_i] = f"{{\\c&H00E6FF&}}{out_toks[best_i]}"
    else:
        out_toks[best_i] = f"{{\\c&H00E6FF&}}{out_toks[best_i]}{{\\c&HFFFFFF&}}"
    return " ".join(out_toks)


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


def _synthesize_documentary_pulse_bgm(
    total_samples: int,
    sr: int,
    speech_end_sec: float,
    edl: dict[str, Any],
) -> np.ndarray:
    """
    R59 Restrained Documentary Soundscape:
      - `88 BPM` minimal warm acoustic marimba/pulse tension bed in D minor.
      - Ducked at `-24.0 dB` under voice, swelling `+8.0 dB` over the final `2.2s` sky title card.
      - Zero digital UI cut ticks; sparse physical analog impulses only on key prop actions.
    """
    t = np.arange(total_samples, dtype=np.float32) / float(sr)
    beat_sec = 60.0 / float(DIORAMA_BGM_BPM)
    sub_beat = beat_sec * 0.5  # 8th-note documentary pulse

    # Warm evolving 6-Act D-minor documentary harmonic progression (Dm9 -> Bbmaj7 -> Gm9 -> Asus4/A7 -> Fmaj7 -> Dm/Dsus2)
    act_chords: dict[int, tuple[float, float, tuple[float, ...]]] = {
        1: (73.42, 110.00, (146.83, 220.00, 174.61, 164.81, 146.83, 220.00, 196.00, 174.61)),
        2: (58.27, 87.31, (116.54, 174.61, 146.83, 220.00, 116.54, 174.61, 130.81, 146.83)),
        3: (49.00, 73.42, (98.00, 146.83, 116.54, 220.00, 98.00, 146.83, 174.61, 146.83)),
        4: (55.00, 82.41, (110.00, 164.81, 146.83, 138.59, 110.00, 196.00, 174.61, 164.81)),
        5: (65.41, 98.00, (130.81, 196.00, 174.61, 220.00, 146.83, 220.00, 261.63, 220.00)),
        6: (73.42, 110.00, (146.83, 220.00, 164.81, 174.61, 220.00, 293.66, 220.00, 174.61)),
    }
    act_windows: list[tuple[float, float, int]] = []
    for cut in edl.get("cuts") or []:
        a_no = max(1, min(6, int(cut.get("act") or 1)))
        cs0 = float(cut.get("out_start_sec") or 0.0)
        cs1 = float(cut.get("out_end_sec") or cs0)
        if act_windows and act_windows[-1][2] == a_no:
            act_windows[-1] = (act_windows[-1][0], cs1, a_no)
        else:
            act_windows.append((cs0, cs1, a_no))
    if not act_windows:
        act_windows = [(0.0, float(total_samples) / float(sr), 1)]

    def _act_at(sec_val: float) -> int:
        for w0, w1, a_no in act_windows:
            if w0 <= sec_val <= w1:
                return a_no
        return act_windows[-1][2]

    bed = np.zeros(total_samples, dtype=np.float32)
    xfade_n = int(0.18 * sr)
    for w0, w1, a_no in act_windows:
        i0 = max(0, min(total_samples, int(round(w0 * sr))))
        i1 = max(i0, min(total_samples, int(round(w1 * sr))))
        if i1 <= i0:
            continue
        b1_hz, b2_hz, _ = act_chords[a_no]
        seg_t = t[i0:i1]
        drone = (0.24 * np.sin(2.0 * math.pi * b1_hz * seg_t) + 0.14 * np.sin(2.0 * math.pi * b2_hz * seg_t)).astype(np.float32)
        if xfade_n > 0 and len(drone) > 2 * xfade_n:
            ramp = np.linspace(0.0, 1.0, xfade_n, dtype=np.float32)
            drone[:xfade_n] *= ramp
            drone[-xfade_n:] *= ramp[::-1]
        bed[i0:i1] += drone

    n_pulses = int(total_samples / max(1, int(sub_beat * sr))) + 1
    pulse_len = min(int(0.34 * sr), max(1, int(sub_beat * sr)))
    p_t = np.arange(pulse_len, dtype=np.float32) / float(sr)
    env = np.exp(-p_t * 11.5) * (1.0 - np.exp(-p_t * 140.0))
    for p_idx in range(n_pulses):
        s_i = int(round(p_idx * sub_beat * sr))
        if s_i >= total_samples:
            break
        e_i = min(total_samples, s_i + pulse_len)
        _, _, notes_hz = act_chords[_act_at(s_i / float(sr))]
        freq = notes_hz[p_idx % len(notes_hz)]
        tone = (0.65 * np.sin(2.0 * math.pi * freq * p_t[: e_i - s_i]) + 0.22 * np.sin(4.0 * math.pi * freq * p_t[: e_i - s_i])) * env[: e_i - s_i]
        bed[s_i:e_i] += tone.astype(np.float32)

    # Normalize raw bed to 0 dBFS peak before applying the -24 dB ducking & +8 dB outro swell envelope
    bed_peak = float(np.max(np.abs(bed))) or 1.0
    bed = bed / bed_peak

    duck_lin = 10.0 ** (DIORAMA_BGM_DUCK_DB / 20.0)
    swell_lin = 10.0 ** ((DIORAMA_BGM_DUCK_DB + DIORAMA_OUTRO_SWELL_GAIN_DB) / 20.0)
    gain_env = np.full(total_samples, duck_lin, dtype=np.float32)
    swell_start = min(total_samples, int(round(speech_end_sec * sr)))
    if swell_start < total_samples:
        ramp_n = min(int(0.35 * sr), total_samples - swell_start)
        gain_env[swell_start : swell_start + ramp_n] = np.linspace(duck_lin, swell_lin, ramp_n, dtype=np.float32)
        gain_env[swell_start + ramp_n :] = swell_lin
    fade_n = min(int(0.14 * sr), total_samples)
    if fade_n > 0:
        gain_env[-fade_n:] *= np.linspace(1.0, 0.0, fade_n, dtype=np.float32)
    bgm = bed * gain_env

    # Sparse physical analog foley on kinetic_trace_automata / recurring_gauge_motif cuts (max 1 every 6 cuts)
    foley = np.zeros(total_samples, dtype=np.float32)
    click_len = int(0.035 * sr)
    c_t = np.arange(click_len, dtype=np.float32) / float(sr)
    brass_click = (np.sin(2.0 * math.pi * 1180.0 * c_t) + 0.6 * np.sin(2.0 * math.pi * 420.0 * c_t)) * np.exp(-c_t * 130.0)
    last_foley_t = -10.0
    for cut in edl.get("cuts") or []:
        t0 = float(cut.get("out_start_sec") or 0.0)
        if t0 >= speech_end_sec - 0.5 or t0 - last_foley_t < 8.0:
            continue
        if cut.get("grammar") in ("kinetic_trace_automata", "recurring_gauge_motif"):
            s_i = min(total_samples, int(round((t0 + 0.12) * sr)))
            e_i = min(total_samples, s_i + click_len)
            foley[s_i:e_i] += (0.045 * brass_click[: e_i - s_i]).astype(np.float32)
            last_foley_t = t0

    return (bgm + foley).astype(np.float32)


def _synthesize_stereo_orchestral_bgm(
    total_samples: int,
    sr: int,
    speech_end_sec: float,
    edl: dict[str, Any],
) -> np.ndarray:
    """
    R63 Schema v7 2-Channel Stereo Warm Orchestral / Acoustic Documentary Score:
      - Decorrelated stereo bowed cello + contrabass ensemble sustain (harmonics 1..7, warm wooden body filter).
      - Stereo felt-piano & marimba documentary arpeggio panned across `[-0.42, +0.42]`.
      - Convolved with a warm stereo wooden chamber impulse response (`fftconvolve`).
      - Ducked at `-22.0 dB` under centered voiceover and swelling `+8.0 dB` over the final `2.2s` sky card.
    """
    from scipy import signal as sp_signal

    t = np.arange(total_samples, dtype=np.float32) / float(sr)
    beat_sec = 60.0 / float(DIORAMA_BGM_BPM)
    sub_beat = beat_sec * 0.5

    act_chords: dict[int, tuple[float, float, tuple[float, ...]]] = {
        1: (73.42, 110.00, (146.83, 220.00, 261.63, 174.61, 164.81, 220.00, 293.66, 196.00)),
        2: (58.27, 87.31, (116.54, 174.61, 220.00, 261.63, 146.83, 174.61, 233.08, 196.00)),
        3: (65.41, 98.00, (130.81, 196.00, 220.00, 261.63, 174.61, 220.00, 293.66, 261.63)),
        4: (55.00, 82.41, (110.00, 164.81, 220.00, 196.00, 146.83, 174.61, 246.94, 164.81)),
        5: (58.27, 98.00, (146.83, 196.00, 233.08, 293.66, 220.00, 261.63, 329.63, 220.00)),
        6: (73.42, 110.00, (146.83, 220.00, 293.66, 329.63, 261.63, 220.00, 174.61, 293.66)),
    }
    act_windows: list[tuple[float, float, int]] = []
    for cut in edl.get("cuts") or []:
        a_no = max(1, min(6, int(cut.get("act") or 1)))
        cs0 = float(cut.get("out_start_sec") or 0.0)
        cs1 = float(cut.get("out_end_sec") or cs0)
        if act_windows and act_windows[-1][2] == a_no:
            act_windows[-1] = (act_windows[-1][0], cs1, a_no)
        else:
            act_windows.append((cs0, cs1, a_no))
    if not act_windows:
        act_windows = [(0.0, float(total_samples) / float(sr), 1)]

    def _act_at(sec_val: float) -> int:
        for w0, w1, a_no in act_windows:
            if w0 <= sec_val <= w1:
                return a_no
        return act_windows[-1][2]

    bed_l = np.zeros(total_samples, dtype=np.float32)
    bed_r = np.zeros(total_samples, dtype=np.float32)
    xfade_n = int(0.22 * sr)

    # Layer 1: Stereo bowed cello (L-weighted) + contrabass/viola fifth (R-weighted) with natural vibrato
    for w0, w1, a_no in act_windows:
        i0 = max(0, min(total_samples, int(round(w0 * sr))))
        i1 = max(i0, min(total_samples, int(round(w1 * sr))))
        if i1 <= i0:
            continue
        b1_hz, b2_hz, _ = act_chords[a_no]
        seg_t = t[i0:i1] - t[i0]
        vib_l = 1.0 + 0.0022 * np.sin(2.0 * math.pi * 4.55 * seg_t)
        vib_r = 1.0 + 0.0024 * np.sin(2.0 * math.pi * 4.90 * seg_t + 1.1)
        str_l = np.zeros_like(seg_t, dtype=np.float32)
        str_r = np.zeros_like(seg_t, dtype=np.float32)
        for h_k in range(1, 7):
            amp = 0.26 / (float(h_k) ** 1.38)
            ph_l = 2.0 * math.pi * (b1_hz * 0.9985 * h_k) * seg_t * vib_l
            ph_r = 2.0 * math.pi * (b2_hz * 1.0015 * h_k) * seg_t * vib_r + 0.65 * h_k
            str_l += (amp * np.sin(ph_l)).astype(np.float32)
            str_r += (amp * np.sin(ph_r)).astype(np.float32)
        if xfade_n > 0 and len(seg_t) > 2 * xfade_n:
            ramp = np.linspace(0.0, 1.0, xfade_n, dtype=np.float32)
            str_l[:xfade_n] *= ramp
            str_l[-xfade_n:] *= ramp[::-1]
            str_r[:xfade_n] *= ramp
            str_r[-xfade_n:] *= ramp[::-1]
        bed_l[i0:i1] += 0.82 * str_l + 0.28 * str_r
        bed_r[i0:i1] += 0.28 * str_l + 0.82 * str_r

    sos_body = sp_signal.butter(2, min(920.0, sr * 0.42), btype="low", fs=float(sr), output="sos")
    bed_l = sp_signal.sosfilt(sos_body, bed_l).astype(np.float32)
    bed_r = sp_signal.sosfilt(sos_body, bed_r).astype(np.float32)

    # Layer 2: Stereo felt-piano & marimba documentary arpeggio panned across [-0.42, +0.42]
    n_pulses = int(total_samples / max(1, int(sub_beat * sr))) + 1
    pulse_len = min(int(0.46 * sr), max(1, int(sub_beat * 1.35 * sr)))
    p_t = np.arange(pulse_len, dtype=np.float32) / float(sr)
    felt_env = (1.0 - np.exp(-p_t * 95.0)) * np.exp(-p_t * 6.2)
    pan_positions = (-0.42, -0.16, 0.18, 0.42, -0.28, 0.30)
    for p_idx in range(n_pulses):
        s_i = int(round(p_idx * sub_beat * sr))
        if s_i >= total_samples:
            break
        e_i = min(total_samples, s_i + pulse_len)
        seg_len = e_i - s_i
        _, _, notes_hz = act_chords[_act_at(s_i / float(sr))]
        freq = notes_hz[p_idx % len(notes_hz)]
        pt_slice = p_t[:seg_len]
        note_wave = (
            0.58 * np.sin(2.0 * math.pi * freq * pt_slice)
            + 0.24 * np.sin(4.0 * math.pi * freq * pt_slice) * np.exp(-pt_slice * 12.0)
            + 0.09 * np.sin(6.0 * math.pi * freq * pt_slice) * np.exp(-pt_slice * 20.0)
        ) * felt_env[:seg_len]
        pan = pan_positions[p_idx % len(pan_positions)]
        gain_l = math.cos((pan + 1.0) * math.pi * 0.25)
        gain_r = math.sin((pan + 1.0) * math.pi * 0.25)
        bed_l[s_i:e_i] += (note_wave * gain_l).astype(np.float32)
        bed_r[s_i:e_i] += (note_wave * gain_r).astype(np.float32)

    # Layer 3: Warm stereo wooden chamber impulse response convolution
    ir_len = max(64, int(0.46 * sr))
    ir_t = np.arange(ir_len, dtype=np.float32) / float(sr)
    rng = np.random.default_rng(707)
    ir_l = (rng.standard_normal(ir_len).astype(np.float32) * np.exp(-ir_t * 8.2)) * 0.06
    ir_r = (rng.standard_normal(ir_len).astype(np.float32) * np.exp(-ir_t * 8.0)) * 0.06
    for delay_ms, g_l, g_r in ((17.0, 0.32, 0.14), (29.0, 0.15, 0.30), (43.0, 0.22, 0.12), (61.0, 0.11, 0.21)):
        d_idx = min(ir_len - 1, int(round(delay_ms * 0.001 * sr)))
        ir_l[d_idx] += g_l
        ir_r[d_idx] += g_r
    sos_ir = sp_signal.butter(2, min(2600.0, sr * 0.45), btype="low", fs=float(sr), output="sos")
    ir_l = sp_signal.sosfilt(sos_ir, ir_l).astype(np.float32)
    ir_r = sp_signal.sosfilt(sos_ir, ir_r).astype(np.float32)
    wet_l = sp_signal.fftconvolve(bed_l, ir_l, mode="full")[:total_samples].astype(np.float32)
    wet_r = sp_signal.fftconvolve(bed_r, ir_r, mode="full")[:total_samples].astype(np.float32)
    st_l = 0.72 * bed_l + 0.28 * wet_l
    st_r = 0.72 * bed_r + 0.28 * wet_r

    # Carve a subtle 1.15-2.85 kHz vocal-formant pocket during active narration so pure sine overtones
    # never fuse into the narrator's vowels as an electronic sheen, while leaving the outro swell full-range.
    speech_samp = max(0, min(total_samples, int(round(speech_end_sec * sr))))
    if speech_samp > int(0.25 * sr) and sr >= 16000:
        sos_pocket = sp_signal.butter(
            2,
            [1150.0, min(2850.0, sr * 0.44)],
            btype="bandstop",
            fs=float(sr),
            output="sos",
        )
        p_l = sp_signal.sosfilt(sos_pocket, st_l[:speech_samp]).astype(np.float32)
        p_r = sp_signal.sosfilt(sos_pocket, st_r[:speech_samp]).astype(np.float32)
        # 55% pocket blend (~-4.5 dB smooth vocal-formant dip)
        pocket_mix = 0.55
        st_l[:speech_samp] = (1.0 - pocket_mix) * st_l[:speech_samp] + pocket_mix * p_l
        st_r[:speech_samp] = (1.0 - pocket_mix) * st_r[:speech_samp] + pocket_mix * p_r

    stereo_bed = np.column_stack([st_l, st_r]).astype(np.float32)
    bed_peak = float(np.max(np.abs(stereo_bed))) or 1.0
    stereo_bed = stereo_bed / bed_peak

    duck_lin = 10.0 ** (DIORAMA_V7_BGM_DUCK_DB / 20.0)
    swell_lin = 10.0 ** ((DIORAMA_V7_BGM_DUCK_DB + DIORAMA_OUTRO_SWELL_GAIN_DB) / 20.0)
    gain_env = np.full(total_samples, duck_lin, dtype=np.float32)
    swell_start = min(total_samples, int(round(speech_end_sec * sr)))
    if swell_start < total_samples:
        ramp_n = min(int(0.35 * sr), total_samples - swell_start)
        gain_env[swell_start : swell_start + ramp_n] = np.linspace(duck_lin, swell_lin, ramp_n, dtype=np.float32)
        gain_env[swell_start + ramp_n :] = swell_lin
    fade_n = min(int(0.14 * sr), total_samples)
    if fade_n > 0:
        gain_env[-fade_n:] *= np.linspace(1.0, 0.0, fade_n, dtype=np.float32)

    # Prosody stamp beats: drop the score to -30 dB inside the pre-stamp silence so the case stamp lands clean
    drop_lin = 10.0 ** (-30.0 / 20.0)
    ramp_d = max(8, int(0.04 * sr))
    for win in edl.get("prosody_stamp_windows") or []:
        try:
            w0, w1 = int(float(win[0]) * sr), int(float(win[1]) * sr)
        except (TypeError, ValueError, IndexError):
            continue
        w0, w1 = max(0, w0), min(total_samples, w1)
        if w1 - w0 <= 2 * ramp_d:
            continue
        seg = gain_env[w0:w1].copy()
        target = np.minimum(seg, drop_lin)
        target[:ramp_d] = np.linspace(seg[0], drop_lin, ramp_d, dtype=np.float32)
        target[-ramp_d:] = np.linspace(drop_lin, seg[-1], ramp_d, dtype=np.float32)
        gain_env[w0:w1] = target

    return (stereo_bed * gain_env[:, None]).astype(np.float32)


def _synthesize_v8_foley_oneshot(cue: str, dur_sec: float, sr: int, rng: np.random.Generator) -> np.ndarray:
    """Synthesizes a stereo procedural physical foley cue (`shape=(N, 2)`, normalized to peak 1.0)."""
    n = max(64, int(round(dur_sec * sr)))
    t = np.arange(n, dtype=np.float32) / float(sr)
    c_norm = str(cue or "pop").strip().lower()
    if c_norm == "thud":
        phase = 2.0 * np.pi * (28.0 * t + 38.0 * (1.0 - np.exp(-t / 0.028)) * 0.028)
        body = np.sin(phase) * np.exp(-t / 0.045) + 0.35 * np.sin(2.0 * np.pi * 135.0 * t) * np.exp(-t / 0.020)
        sig_l, sig_r = body, body * 0.96
    elif c_norm == "whoosh":
        nz_l = rng.standard_normal(n).astype(np.float32)
        nz_r = rng.standard_normal(n).astype(np.float32)
        freqs = np.fft.rfftfreq(n, d=1.0 / float(sr))
        bp = np.exp(-0.5 * ((freqs - 720.0) / 480.0) ** 2).astype(np.float32)
        env = np.maximum(0.0, np.sin(np.pi * np.linspace(0.0, 1.0, n, dtype=np.float32))) ** 1.4
        pan = np.linspace(0.32, 0.68, n, dtype=np.float32)
        sig_l = np.fft.irfft(np.fft.rfft(nz_l) * bp, n=n).astype(np.float32) * env * (1.0 - pan)
        sig_r = np.fft.irfft(np.fft.rfft(nz_r) * bp, n=n).astype(np.float32) * env * pan
    elif c_norm == "click":
        imp = (
            np.sin(2.0 * np.pi * 1850.0 * t) * np.exp(-t / 0.006)
            + 0.6 * np.sin(2.0 * np.pi * 3350.0 * t) * np.exp(-t / 0.0035)
        )
        sig_l, sig_r = imp, imp * 0.94
    elif c_norm == "crystal_shimmer":
        env = np.maximum(0.0, np.sin(np.pi * np.minimum(1.0, t / max(0.02, dur_sec)))) * np.exp(-t / max(0.05, dur_sec * 0.55))
        sh_l = (
            0.55 * np.sin(2.0 * np.pi * 1480.0 * t)
            + 0.30 * np.sin(2.0 * np.pi * 2220.0 * t + 0.4)
            + 0.15 * np.sin(2.0 * np.pi * 2960.0 * t + 1.1)
        ) * env
        sh_r = (
            0.55 * np.sin(2.0 * np.pi * 1483.0 * t + 0.5)
            + 0.30 * np.sin(2.0 * np.pi * 2217.0 * t + 1.2)
            + 0.15 * np.sin(2.0 * np.pi * 2964.0 * t + 0.2)
        ) * env
        sig_l, sig_r = sh_l * 0.72, sh_r * 0.72
    elif c_norm == "heartbeat_thump":
        t2 = np.maximum(0.0, t - min(0.095, dur_sec * 0.48))
        lub = np.sin(2.0 * np.pi * 48.0 * t) * np.exp(-t / 0.032)
        dub = (t >= min(0.095, dur_sec * 0.48)).astype(np.float32) * np.sin(2.0 * np.pi * 42.0 * t2) * np.exp(-t2 / 0.028)
        hb = lub + 0.82 * dub
        sig_l, sig_r = hb, hb
    else:  # "pop"
        phase = 2.0 * np.pi * (210.0 * t + 340.0 * (t ** 2) / max(0.03, dur_sec))
        pop = np.sin(phase) * np.exp(-t / 0.018)
        sig_l, sig_r = pop, pop * 0.97

    st = np.column_stack([sig_l.astype(np.float32), sig_r.astype(np.float32)])
    fade = min(n // 4, max(8, int(0.004 * sr)))
    if fade > 0:
        ramp = np.linspace(0.0, 1.0, fade, dtype=np.float32)[:, None]
        st[:fade, :] *= ramp
        st[-fade:, :] *= ramp[::-1]
    pk = float(np.max(np.abs(st))) if st.size else 0.0
    if pk > 1e-6:
        st /= pk
    return st


def _synthesize_expressive_v8_ambience_and_foley(
    n_samples: int,
    sr: int,
    speech_end_sec: float,
    edl: dict[str, Any],
) -> np.ndarray:
    """
    `expressive_25d_v8` Rising Dark-Suspense Soundscape (`@RicksClips3000`-calibrated):
      - Continuous minor/Phrygian dark synth-cello + sub-bass tension underscore (`C2 + G2 + C3 + Eb3 + Db3`
        slow breathing swell, zero 88-BPM beat grid, vocal-pocket low-passed below `520 Hz`, narrow/center-focused
        stereo with subtle `±0.22 Hz` chorus + `-30 dBFS` decorrelated room air).
      - Strictly monotonic rising envelope from `EXPRESSIVE_V8_BGM_START_DB` (`-25.0 dBFS` post-LUFS) at `0.0s` to
        `EXPRESSIVE_V8_BGM_PEAK_DB` / `EXPRESSIVE_V8_BGM_END_DB` (`-18.0 dBFS` post-LUFS) held through climax & ending
        with zero tail dip.
      - Crisp procedural physical foley + auto-placed camera-flight/styled-transition `whoosh`/`thud` accents.
    """
    from pipeline.config import (
        EXPRESSIVE_V8_3D_FLIGHT_MOVES,
        EXPRESSIVE_V8_BGM_BREATH_DB,
        EXPRESSIVE_V8_BGM_DUCK_DB,
        EXPRESSIVE_V8_BGM_END_DB,
        EXPRESSIVE_V8_BGM_MODE,
        EXPRESSIVE_V8_BGM_PEAK_DB,
        EXPRESSIVE_V8_BGM_START_DB,
        EXPRESSIVE_V8_BGM_TAIL_DBFS,
        EXPRESSIVE_V8_DEFAULT_BGM_MOOD,
        EXPRESSIVE_V8_FLIGHT_WHOOSH_DBFS,
        EXPRESSIVE_V8_FOLEY_PEAK_DBFS,
        EXPRESSIVE_V8_FOLEY_TYPES,
        EXPRESSIVE_V8_ROOM_AMBIENCE_DBFS,
        EXPRESSIVE_V8_ROOM_TONE_DBFS,
        EXPRESSIVE_V8_SYNTH_TONAL_FOLEY,
    )
    from pipeline.elevenlabs_music import (
        synthesize_or_load_elevenlabs_bgm,
        synthesize_room_tone_only,
        synthesize_tonal_fixed_underscore,
    )

    if n_samples <= 0:
        return np.zeros((0, 2), dtype=np.float32)
    seed_val = sum(ord(ch) for ch in str(edl.get("style_profile") or "v8")) + int(n_samples % 9973)
    rng = np.random.default_rng(seed_val)
    t_sec = np.arange(n_samples, dtype=np.float32) / float(sr)
    total_sec = max(0.25, n_samples / float(sr))
    sp_end = max(0.20, min(total_sec, float(speech_end_sec or total_sec)))

    bgm_mode = str(edl.get("bgm_mode") or EXPRESSIVE_V8_BGM_MODE or "elevenlabs_music").strip().lower()
    bgm_mood = str(edl.get("bgm_mood") or EXPRESSIVE_V8_DEFAULT_BGM_MOOD).strip()
    gap_windows = edl.get("gap_windows") if isinstance(edl.get("gap_windows"), list) else []

    bgm_meta: dict[str, Any] = {"bgm_source": bgm_mode}
    if bgm_mode == "elevenlabs_music":
        unit_bgm_st, bgm_meta = synthesize_or_load_elevenlabs_bgm(
            mood_id=bgm_mood,
            duration_sec=total_sec,
            sr=sr,
            n_samples=n_samples,
        )
        if bgm_meta.get("bgm_source") == "room_tone_fallback":
            amb_st = unit_bgm_st.astype(np.float32)
        else:
            # Vocal-clear dynamic ducking: -21.5 dB pre-LUFS (~ -25.5 dB raw) during speech, gentle lift in breath gaps
            duck_db = float(EXPRESSIVE_V8_BGM_DUCK_DB) - 4.0
            breath_db = float(EXPRESSIVE_V8_BGM_BREATH_DB) - 4.0
            env_db = np.full(n_samples, duck_db, dtype=np.float32)
            for gw in gap_windows:
                if isinstance(gw, (list, tuple)) and len(gw) >= 2:
                    g0, g1 = float(gw[0]), float(gw[1])
                    i0 = max(0, min(n_samples, int(round((g0 - 0.08) * sr))))
                    i1 = max(i0, min(n_samples, int(round((g1 + 0.08) * sr))))
                    if i1 - i0 >= 16:
                        win_u = np.linspace(0.0, 1.0, i1 - i0, dtype=np.float32)
                        bump = (breath_db - duck_db) * np.sin(np.pi * win_u)
                        env_db[i0:i1] = np.maximum(env_db[i0:i1], duck_db + bump)
            bgm_st = unit_bgm_st * (10.0 ** (env_db / 20.0)).astype(np.float32)[:, None]
            room_st = synthesize_room_tone_only(n_samples, sr=sr, target_dbfs=EXPRESSIVE_V8_ROOM_TONE_DBFS, seed=seed_val)
            amb_st = (bgm_st + room_st).astype(np.float32)
    elif bgm_mode == "tonal_fixed":
        tonal_st = synthesize_tonal_fixed_underscore(n_samples, sr=sr)
        tonal_rms = max(1e-6, float(np.sqrt(np.mean(np.square(tonal_st)))))
        tonal_st = tonal_st / tonal_rms
        gain_lin = float(10.0 ** ((-31.0 - 4.0) / 20.0))
        room_st = synthesize_room_tone_only(n_samples, sr=sr, target_dbfs=EXPRESSIVE_V8_ROOM_TONE_DBFS, seed=seed_val)
        amb_st = (tonal_st * gain_lin + room_st).astype(np.float32)
    else:
        amb_st = synthesize_room_tone_only(n_samples, sr=sr, target_dbfs=EXPRESSIVE_V8_ROOM_TONE_DBFS, seed=seed_val)

    fade_in = min(n_samples // 6, int(0.045 * sr))
    if fade_in > 0:
        amb_st[:fade_in, :] *= np.linspace(0.15, 1.0, fade_in, dtype=np.float32)[:, None]
    fade_out = min(n_samples // 6, int(0.18 * sr))
    if fade_out > 0:
        amb_st[-fade_out:, :] *= np.linspace(1.0, 0.05, fade_out, dtype=np.float32)[:, None]

    # 2. Subtle non-tonal physical thud/whoosh foley on cut boundaries (all 1.4-3.3 kHz sine click/shimmer tones disabled)
    placed_foley: list[dict[str, Any]] = []
    cuts = edl.get("cuts") if isinstance(edl.get("cuts"), list) else []
    outgoing_candidates = cuts[:-1] if len(cuts) > 1 else cuts
    foley_peak = float(10.0 ** ((float(EXPRESSIVE_V8_FOLEY_PEAK_DBFS) + 1.5) / 20.0))
    for gw in gap_windows:
        if not (isinstance(gw, (list, tuple)) and len(gw) >= 2):
            continue
        g0, g1 = float(gw[0]), float(gw[1])
        if g1 - g0 < 0.14 or g1 > sp_end + 0.05:
            continue
        w0, w1 = g0 + 0.015, g1 - 0.015
        avail = w1 - w0
        if avail < 0.08:
            continue
        mid_t = 0.5 * (w0 + w1)
        out_cut = None
        best_dt = 999.0
        for c_cand in outgoing_candidates:
            ce = float(c_cand.get("out_end_sec") or 0.0)
            dt = abs(ce - mid_t)
            if dt < best_dt and dt <= 0.45:
                best_dt = dt
                out_cut = c_cand
        tr_out = str((out_cut or {}).get("transition_out") or "").strip().lower()
        if tr_out == "action_impact_cut":
            cue_name = "thud"
        elif tr_out in ("whip_pan_blur_8f", "portal_crash_zoom_10f", "occlusion_wipe", "seamless_relay_cut") or bool(EXPRESSIVE_V8_SYNTH_TONAL_FOLEY):
            cue_name = "whoosh"
        else:
            continue
        dur_cue = min(avail, 0.13)
        oneshot = _synthesize_v8_foley_oneshot(cue_name, dur_cue, sr, rng) * foley_peak
        s0 = max(0, int(round((mid_t - 0.5 * dur_cue) * sr)))
        s1 = min(n_samples, s0 + oneshot.shape[0])
        if s1 > s0:
            amb_st[s0:s1, :] += oneshot[: s1 - s0, :]
            placed_foley.append({"time_sec": round(s0 / float(sr), 3), "cue": cue_name, "duration_sec": round((s1 - s0) / float(sr), 3)})

    # Rule R74: Subtle -21 dBFS bandpass (160-850 Hz) velvet air-glass portal whoosh (0.36s) on neural & portal dives
    from pipeline.config import (
        NEURAL_WHOOSH_BAND_HZ,
        NEURAL_WHOOSH_DURATION_SEC,
        NEURAL_WHOOSH_GAIN_DB,
    )

    neural_whoosh_events: list[dict[str, Any]] = []
    whoosh_moves = {
        "neural_fpv_dive_in",
        "neural_fpv_pullback_out",
        "neural_tract_relay_flight",
        "fpv_window_portal_breach",
    }
    w_len = max(64, int(round(float(NEURAL_WHOOSH_DURATION_SEC) * sr)))
    w_peak = float(10.0 ** (float(NEURAL_WHOOSH_GAIN_DB) / 20.0))
    cuts_for_whoosh = edl.get("cuts") if isinstance(edl.get("cuts"), list) else []
    for c_w in cuts_for_whoosh:
        if not isinstance(c_w, dict):
            continue
        cm_w = str(c_w.get("camera_move") or c_w.get("camera") or "").strip().lower()
        if cm_w not in whoosh_moves:
            continue
        t_w = max(0.0, float(c_w.get("out_start_sec") or 0.0))
        s0_w = max(0, int(round(t_w * sr)))
        s1_w = min(n_samples, s0_w + w_len)
        if s1_w - s0_w < 32:
            continue
        seg_n = s1_w - s0_w
        wn = rng.standard_normal(seg_n).astype(np.float64)
        freqs = np.fft.rfftfreq(seg_n, d=1.0 / float(sr))
        lo_hz, hi_hz = float(NEURAL_WHOOSH_BAND_HZ[0]), float(NEURAL_WHOOSH_BAND_HZ[1])
        spec_w = np.fft.rfft(wn)
        bp_mask = np.exp(-0.5 * ((np.maximum(0.0, lo_hz - freqs) / 45.0) ** 2)) * np.exp(
            -0.5 * ((np.maximum(0.0, freqs - hi_hz) / 180.0) ** 2)
        )
        velvet_mono = np.fft.irfft(spec_w * bp_mask, n=seg_n)
        t_axis = np.linspace(0.0, float(seg_n) / float(sr), seg_n, endpoint=False)
        chime_sub = 0.22 * np.sin(2.0 * math.pi * (420.0 if cm_w != "neural_fpv_pullback_out" else 340.0) * t_axis)
        raw_velvet = (velvet_mono / max(1e-6, float(np.max(np.abs(velvet_mono))))) * 0.78 + chime_sub
        env_w = np.hanning(seg_n)
        pan_l = np.linspace(0.92, 0.68, seg_n) if cm_w != "neural_fpv_pullback_out" else np.linspace(0.68, 0.92, seg_n)
        pan_r = np.linspace(0.68, 0.92, seg_n) if cm_w != "neural_fpv_pullback_out" else np.linspace(0.92, 0.68, seg_n)
        whoosh_st = np.column_stack([raw_velvet * env_w * pan_l, raw_velvet * env_w * pan_r]).astype(np.float32)
        mx_w = float(np.max(np.abs(whoosh_st)))
        if mx_w > 1e-6:
            whoosh_st = whoosh_st * (w_peak / mx_w)
        amb_st[s0_w:s1_w, :] += whoosh_st
        neural_whoosh_events.append(
            {
                "cut_index": c_w.get("cut_index"),
                "camera_move": cm_w,
                "time_sec": round(s0_w / float(sr), 3),
                "duration_sec": round(seg_n / float(sr), 3),
                "gain_dbfs": float(NEURAL_WHOOSH_GAIN_DB),
            }
        )

    edl["neural_whoosh_events"] = neural_whoosh_events
    edl["bgm_profile"] = str(bgm_meta.get("bgm_source") or bgm_mode)
    edl["bgm_mood"] = bgm_mood
    edl["bgm_model_id"] = bgm_meta.get("model_id")
    edl["bgm_file"] = bgm_meta.get("bgm_file")
    edl["bgm_start_dbfs"] = float(EXPRESSIVE_V8_BGM_DUCK_DB)
    edl["bgm_peak_dbfs"] = float(EXPRESSIVE_V8_BGM_BREATH_DB)
    edl["bgm_end_dbfs"] = float(EXPRESSIVE_V8_BGM_DUCK_DB)
    edl["bgm_tail_dbfs"] = float(EXPRESSIVE_V8_BGM_TAIL_DBFS)
    edl["bgm_melodic_ratio"] = 1.0
    edl["room_ambience_dbfs"] = float(EXPRESSIVE_V8_ROOM_TONE_DBFS)
    edl["foley_events_synthesized"] = len(placed_foley)
    edl["placed_foley"] = placed_foley
    return amb_st


def generate_diorama_audio_master(
    wav_path: Path,
    voice_pcm: np.ndarray,
    sr: int,
    speech_end_sec: float,
    edl: dict[str, Any],
) -> Path:
    """Mixes master voiceover + documentary score (or v8 room ambience + foley) and normalizes to target LUFS."""
    from pipeline.config import EXPRESSIVE_V8_TARGET_LUFS, is_expressive_v8_plan

    wav_path = Path(wav_path)
    wav_path.parent.mkdir(parents=True, exist_ok=True)
    n_samples = len(voice_pcm)
    is_v8 = is_expressive_v8_plan(edl)
    is_v7 = is_v8 or int(edl.get("schema") or 6) >= PROMPT_SCHEMA_VERSION_V7

    if is_v7:
        stereo_bgm = (
            _synthesize_expressive_v8_ambience_and_foley(n_samples, sr, speech_end_sec, edl)
            if is_v8
            else _synthesize_stereo_orchestral_bgm(n_samples, sr, speech_end_sec, edl)
        )
        target_lufs = float(EXPRESSIVE_V8_TARGET_LUFS if is_v8 else DIORAMA_TARGET_LUFS)
        tp_target = -1.6 if is_v8 else -1.8
        lim_ceil = 0.831 if is_v8 else 0.812
        voice_mono = voice_pcm.astype(np.float32).reshape(-1)
        voice_st = np.column_stack([voice_mono, voice_mono])
        raw_sum = voice_st + stereo_bgm
        peak_raw = float(np.max(np.abs(raw_sum))) if raw_sum.size else 0.0
        # Stage unclipped 16-bit PCM with clean headroom before 2-pass EBU R128 linear normalization
        pre_scale = min(0.78, 0.92 / peak_raw) if peak_raw > 1e-5 else 0.78
        mixed_st = (raw_sum * pre_scale).astype(np.float32)
        with ram_tempdir(prefix="aab_diorama_mix_v7_") as td:
            td_p = Path(td)
            raw_wav = td_p / "raw_mix_st.wav"
            norm_wav = td_p / "norm_mix_st.wav"
            out_wav_tmp = td_p / "audio_master_st.wav"
            _write_stereo_wav(raw_wav, mixed_st, sr)
            # Pass 1: Measure integrated loudness & LRA so Schema v7/v8 uses pure constant scalar linear gain
            # rather than FFmpeg single-pass loudnorm's 3-second sliding-window dynamic AGC gain-rider.
            af = (
                f"loudnorm=I={target_lufs}:TP={tp_target}:LRA=8.5,"
                f"alimiter=limit={lim_ceil}:attack=5:release=50:level=disabled"
            )
            res_p1 = subprocess.run(
                [
                    _ffmpeg(), "-nostdin", "-hide_banner", "-y",
                    "-i", str(raw_wav),
                    "-af", f"loudnorm=I={target_lufs}:TP={tp_target}:LRA=8.5:print_format=json",
                    "-f", "null", "-",
                ],
                capture_output=True, text=True, check=False, timeout=180, stdin=subprocess.DEVNULL,
            )
            m_json = re.search(r"\{\s*\"input_i\"[\s\S]*?\}", res_p1.stderr or "")
            if m_json:
                try:
                    ln_stats = json.loads(m_json.group(0))
                    meas_i = float(ln_stats["input_i"])
                    meas_lra = float(ln_stats["input_lra"])
                    meas_tp = float(ln_stats["input_tp"])
                    meas_thresh = float(ln_stats["input_thresh"])
                    meas_offset = float(ln_stats["target_offset"])
                    if math.isfinite(meas_i) and meas_i > -70.0:
                        if meas_lra <= 8.5:
                            gain_db = max(-24.0, min(24.0, target_lufs - meas_i))
                            af = (
                                f"{_cfg.DIORAMA_V7_MASTER_DEESSER},"
                                f"volume={gain_db:.4f}dB,alimiter=limit={lim_ceil}:attack=5:release=50:level=disabled"
                            )
                        elif math.isfinite(meas_tp) and math.isfinite(meas_thresh) and math.isfinite(meas_offset):
                            af = (
                                f"{_cfg.DIORAMA_V7_MASTER_DEESSER},"
                                f"loudnorm=I={target_lufs}:TP={tp_target}:LRA=8.5"
                                f":measured_I={meas_i:.2f}:measured_TP={meas_tp:.2f}"
                                f":measured_LRA={meas_lra:.2f}:measured_thresh={meas_thresh:.2f}"
                                f":offset={meas_offset:.2f}:linear=true,"
                                f"alimiter=limit={lim_ceil}:attack=5:release=50:level=disabled"
                            )
                except (KeyError, TypeError, ValueError, json.JSONDecodeError):
                    pass
            res = subprocess.run(
                [
                    _ffmpeg(), "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
                    "-i", str(raw_wav), "-af", af, "-ar", str(sr), "-ac", str(DIORAMA_V7_AUDIO_CHANNELS), str(norm_wav),
                ],
                capture_output=True, check=False, timeout=180, stdin=subprocess.DEVNULL,
            )
            if res.returncode == 0 and norm_wav.exists():
                with wave.open(str(norm_wav), "rb") as wf:
                    n_ch = max(1, wf.getnchannels())
                    raw_bytes = wf.readframes(wf.getnframes())
                raw_arr = np.frombuffer(raw_bytes, dtype=np.int16).astype(np.float32) / 32767.0
                if n_ch >= 2:
                    pcm_st = raw_arr[: (len(raw_arr) // n_ch) * n_ch].reshape(-1, n_ch)[:, :2]
                else:
                    pcm_st = np.column_stack([raw_arr, raw_arr])
                if pcm_st.shape[0] >= n_samples:
                    pcm_st = pcm_st[:n_samples, :].copy()
                else:
                    pad_rows = n_samples - pcm_st.shape[0]
                    pcm_st = np.pad(pcm_st, ((0, pad_rows), (0, 0))).astype(np.float32)
            else:
                pcm_st = np.clip(raw_sum * 0.84, -lim_ceil, lim_ceil).astype(np.float32)
            mute_n = min(pcm_st.shape[0], int(0.095 * sr))
            if mute_n > 0:
                env_tail = np.linspace(1.0, 0.0, mute_n, dtype=np.float32)[:, None]
                pcm_st[-mute_n:, :] *= env_tail
            _write_stereo_wav(out_wav_tmp, pcm_st, sr)
            atomic_commit_from_scratch(out_wav_tmp, wav_path)
        return wav_path

    accompaniment = _synthesize_documentary_pulse_bgm(n_samples, sr, speech_end_sec, edl)
    mixed = np.clip(voice_pcm.astype(np.float32) + accompaniment, -0.96, 0.96)

    with ram_tempdir(prefix="aab_diorama_mix_") as td:
        td_p = Path(td)
        raw_wav = td_p / "raw_mix.wav"
        norm_wav = td_p / "norm_mix.wav"
        out_wav_tmp = td_p / "audio_master_mono.wav"
        _write_mono_wav(raw_wav, mixed, sr)
        af = (
            f"loudnorm=I={DIORAMA_TARGET_LUFS}:TP=-2.2:LRA=4.0,"
            "alimiter=limit=0.776:attack=5:release=50:level=disabled"
        )
        res = subprocess.run(
            [
                _ffmpeg(), "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
                "-i", str(raw_wav), "-af", af, "-ar", str(sr), "-ac", "1", str(norm_wav),
            ],
            capture_output=True, check=False, timeout=180, stdin=subprocess.DEVNULL,
        )
        if res.returncode == 0 and norm_wav.exists():
            # Ensure exact sample count matches video frame duration + clean 95ms tail mute
            with wave.open(str(norm_wav), "rb") as wf:
                raw_bytes = wf.readframes(wf.getnframes())
            pcm_out = np.frombuffer(raw_bytes, dtype=np.int16).astype(np.float32) / 32767.0
            if len(pcm_out) >= n_samples:
                pcm_out = pcm_out[:n_samples].copy()
            else:
                pcm_out = np.pad(pcm_out, (0, n_samples - len(pcm_out))).astype(np.float32)
        else:
            pcm_out = mixed * 0.84
        mute_n = min(len(pcm_out), int(0.095 * sr))
        if mute_n > 0:
            pcm_out[-mute_n:] *= np.linspace(1.0, 0.0, mute_n, dtype=np.float32)
        _write_mono_wav(out_wav_tmp, pcm_out, sr)
        atomic_commit_from_scratch(out_wav_tmp, wav_path)
    return wav_path


def _compute_v7_pastel_eq_filter(clip_path: Path) -> str:
    """Computes an adaptive FFmpeg `eq` pastel saturation/luma grade across the active NLE window while leaving pastel clips untouched."""
    from pipeline.media_cache import cached_by_clip_stat

    def _probe_pastel_eq(local_p: Path) -> str:
        cap = cv2.VideoCapture(str(local_p))
        if not cap.isOpened():
            return ""
        fc = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        sats: list[float] = []
        lumas: list[float] = []
        fracs = (0.12, 0.25, 0.42) if fc >= 12 else (0.5,)
        for fr in fracs:
            if fc > 1:
                cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, min(fc - 1, int(round(fc * fr)))))
            ok, frm = cap.read()
            if ok and frm is not None:
                hsv = cv2.cvtColor(frm, cv2.COLOR_BGR2HSV)
                gray = cv2.cvtColor(frm, cv2.COLOR_BGR2GRAY)
                sats.append(float(np.mean(hsv[:, :, 1])))
                lumas.append(float(np.mean(gray)))
        cap.release()
        if not lumas:
            return ""
        raw_sat = float(np.mean(sats))
        raw_luma = float(np.mean(lumas))
        min_luma = float(min(lumas))
        if raw_sat <= 42.0 and 112.0 <= raw_luma <= 146.0 and min_luma >= 96.0:
            return ""
        sat_mul = min(1.0, max(0.38, 36.5 / max(1.0, raw_sat))) if raw_sat > 42.0 else 1.0
        if min_luma < 96.0:
            bright_shift = float(np.clip((108.0 - min_luma) / 380.0, 0.015, 0.065))
        elif raw_luma > 146.0:
            bright_shift = float(np.clip((134.0 - raw_luma) / 520.0, -0.045, 0.0))
        elif raw_luma < 112.0:
            bright_shift = float(np.clip((124.0 - raw_luma) / 480.0, 0.0, 0.040))
        else:
            bright_shift = 0.0
        if abs(sat_mul - 1.0) < 0.02 and abs(bright_shift) < 0.005:
            return ""
        return f"eq=saturation={sat_mul:.3f}:brightness={bright_shift:.3f},"

    return str(cached_by_clip_stat(Path(clip_path), namespace="pastel_eq_v1", compute_fn=_probe_pastel_eq))


def _probe_segment_frame_count(seg_path: Path) -> int:
    """Probes exact video frame count of a rendered cut/xfade segment (fast metadata + decode fallback)."""
    if not seg_path.is_file() or seg_path.stat().st_size <= 0:
        return 0
    cap = cv2.VideoCapture(str(seg_path))
    if not cap.isOpened():
        return 0
    try:
        meta_cnt = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        if meta_cnt > 0:
            return meta_cnt
        cnt = 0
        while True:
            ok, _ = cap.read()
            if not ok:
                break
            cnt += 1
        return cnt
    finally:
        cap.release()


def _execute_xfade_batch_ffmpeg(
    ff: str,
    batch_inputs: list[tuple[Path, int, str, int]],
    out_path: Path,
    fps: int,
    *,
    target_crf: int = 18,
    ass_filter: str = "",
    burn_start_sec: float | None = None,
    cwd: Path | None = None,
    ffmpeg_threads: int = 2,
) -> int:
    """Validates input frame counts & xfade offsets and merges `batch_inputs` into `out_path` without silent truncation."""
    in_frame_counts: list[int] = []
    for b_idx, (raw_p, req_eff_f, _xf_k, req_ov_f) in enumerate(batch_inputs):
        actual_in_f = _probe_segment_frame_count(raw_p)
        min_needed_f = int(req_eff_f) + (
            int(req_ov_f) + 1 if (b_idx < len(batch_inputs) - 1 and int(req_ov_f) > 0) else 0
        )
        if actual_in_f < min_needed_f:
            raise RuntimeError(
                f"FFmpeg xfade input {raw_p.name} has {actual_in_f} frames (< required {min_needed_f} frames)"
            )
        in_frame_counts.append(actual_in_f)

    fc_parts: list[str] = [
        f"[{b_i}:v]setpts=PTS-STARTPTS,fps={fps}[vin{b_i}]"
        for b_i in range(len(batch_inputs))
    ]
    prev_lbl = "[vin0]"
    acc_f = 0
    avail_f = in_frame_counts[0]
    for m_idx in range(1, len(batch_inputs)):
        _prev_raw, prev_eff_f, prev_xf_kind, prev_ov_f = batch_inputs[m_idx - 1]
        acc_f += prev_eff_f
        nxt_lbl = f"[xf{m_idx}]"
        off_sec = acc_f / float(fps)
        ov_sec = prev_ov_f / float(fps)
        avail_dur = avail_f / float(fps)
        if not (off_sec < avail_dur - ov_sec - 1e-6):
            raise RuntimeError(
                f"Invalid xfade offset {off_sec:.6f}s >= avail_dur {avail_dur:.6f}s - overlap {ov_sec:.6f}s "
                f"at chain index {m_idx}"
            )
        fc_parts.append(
            f"{prev_lbl}[vin{m_idx}]xfade=transition={prev_xf_kind}:duration={ov_sec:.6f}:offset={off_sec:.6f}{nxt_lbl}"
        )
        avail_f = acc_f + in_frame_counts[m_idx]
        prev_lbl = nxt_lbl

    is_final_stage = burn_start_sec is not None
    if is_final_stage:
        total_out_f = sum(int(x[1]) for x in batch_inputs)
        ass_chain = f",{ass_filter}" if ass_filter else ""
        fc_parts.append(
            f"{prev_lbl}fps={fps},setpts=PTS+{float(burn_start_sec):.6f}/TB{ass_chain},setpts=PTS-STARTPTS,format=yuv420p[vout]"
        )
        enc_preset = "ultrafast"
        enc_crf = str(max(14, int(target_crf) - 2))
    else:
        tail_ov_f = int(batch_inputs[-1][3])
        total_out_f = sum(int(x[1]) for x in batch_inputs) + (tail_ov_f + 1 if tail_ov_f > 0 else 0)
        fc_parts.append(f"{prev_lbl}fps={fps},setpts=PTS-STARTPTS,format=yuv420p[vout]")
        enc_preset = "ultrafast"
        enc_crf = str(max(13, int(target_crf) - 3))

    in_args: list[str] = []
    for raw_p, _, _, _ in batch_inputs:
        in_args.extend(["-i", raw_p.name if cwd is not None else str(raw_p)])
    out_arg = out_path.name if cwd is not None else str(out_path)
    res_xf = subprocess.run(
        [
            ff,
            "-nostdin",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            *in_args,
            "-filter_complex",
            ";".join(fc_parts),
            "-map",
            "[vout]",
            "-frames:v",
            str(total_out_f),
            "-r",
            str(fps),
            "-c:v",
            "libx264",
            "-preset",
            enc_preset,
            "-crf",
            enc_crf,
            "-profile:v",
            "high",
            "-level:v",
            "4.2",
            "-x264-params",
            "stitchable=1",
            "-video_track_timescale",
            str(fps * 1000),
            "-threads",
            str(max(1, int(ffmpeg_threads))),
            "-pix_fmt",
            "yuv420p",
            "-an",
            out_arg,
        ],
        cwd=str(cwd) if cwd is not None else None,
        capture_output=True,
        text=True,
        check=False,
        timeout=240,
        stdin=subprocess.DEVNULL,
    )
    if res_xf.returncode != 0 or not out_path.exists():
        raise RuntimeError(f"FFmpeg Track-V1 camera transition xfade failed: {(res_xf.stderr or '')[:300]}")
    rendered_xf_f = _probe_segment_frame_count(out_path)
    if rendered_xf_f < total_out_f:
        raise RuntimeError(
            f"FFmpeg Track-V1 xfade output {out_path.name} truncated ({rendered_xf_f} < {total_out_f} frames)"
        )
    return rendered_xf_f


def _merge_xfade_group_multistage(
    ff: str,
    grp_inputs: list[tuple[Path, int, str, int]],
    out_path: Path,
    fps: int,
    *,
    target_crf: int = 18,
    ass_filter: str = "",
    burn_start_sec: float | None = 0.0,
    cwd: Path | None = None,
    group_idx: int = 0,
    n_workers: int | None = None,
) -> int:
    """Multi-stage (<=4-input per FFmpeg call) xfade merger preserving exact frame counts across mixed timebases."""
    eff_workers = int(n_workers) if (n_workers is not None and int(n_workers) >= 1) else resolve_xfade_workers()
    eff_ff_threads = resolve_ffmpeg_threads_per_worker(eff_workers)
    work_dir = cwd if cwd is not None else out_path.parent
    cur_stage = list(grp_inputs)
    stage_round = 0
    while len(cur_stage) > 4:
        chunks = [cur_stage[i : i + 4] for i in range(0, len(cur_stage), 4)]
        next_stage: list[tuple[Path, int, str, int]] = []
        sub_jobs: list[tuple[list[tuple[Path, int, str, int]], Path]] = []
        for ch_idx, chunk in enumerate(chunks):
            if len(chunk) == 1:
                next_stage.append(chunk[0])
            else:
                mid_p = work_dir / f"xfmid_g{group_idx}_r{stage_round}_{ch_idx}.mp4"
                sub_jobs.append((chunk, mid_p))
                next_stage.append((mid_p, sum(int(x[1]) for x in chunk), chunk[-1][2], int(chunk[-1][3])))
        if sub_jobs:
            with ThreadPoolExecutor(max_workers=min(max(1, eff_workers), len(sub_jobs))) as xf_pool:
                list(
                    xf_pool.map(
                        lambda jb: _execute_xfade_batch_ffmpeg(
                            ff=ff,
                            batch_inputs=jb[0],
                            out_path=jb[1],
                            fps=fps,
                            target_crf=int(target_crf),
                            ass_filter="",
                            burn_start_sec=None,
                            cwd=work_dir,
                            ffmpeg_threads=eff_ff_threads,
                        ),
                        sub_jobs,
                    )
                )
        cur_stage = next_stage
        stage_round += 1
    return _execute_xfade_batch_ffmpeg(
        ff=ff,
        batch_inputs=cur_stage,
        out_path=out_path,
        fps=fps,
        target_crf=int(target_crf),
        ass_filter=ass_filter,
        burn_start_sec=burn_start_sec,
        cwd=work_dir,
        ffmpeg_threads=resolve_ffmpeg_threads_per_worker(1),
    )


def _clamp_source_window_to_eof(
    clip_path: Path,
    s0_in: float,
    s1_in: float,
    min_span: float = 0.20,
) -> tuple[float, float]:
    """Shifts `s0` backward and clamps `s1` when a cut window approaches or exceeds source clip EOF."""
    s0 = max(0.0, float(s0_in))
    s1 = max(s0 + min_span, float(s1_in))
    actual_dur = float(_clip_duration(clip_path) or 0.0)
    if actual_dur <= min_span:
        return s0, s1
    req_span = max(min_span, s1 - s0)
    safe_eof = max(min_span, actual_dur - 0.015)
    if s1 > safe_eof:
        s0 = max(0.0, min(s0, safe_eof - req_span))
        s1 = max(s0 + min(min_span, safe_eof), min(s1, actual_dur))
    return round(s0, 5), round(s1, 5)


def _upsample_clip_window_optical_flow(
    ff: str,
    src_path: Path,
    s0: float,
    s1: float,
    target_fps: int,
    *,
    tail_pad_sec: float = 0.22,
) -> tuple[Path, float] | None:
    """
    Upsamples `[s0, s1 + tail_pad_sec]` from a sub-30fps source (e.g. 24fps Flow clip) to `target_fps` (e.g. 30fps)
    using half-res bidirectional OpenCV `DISOpticalFlow` (`ULTRAFAST`) so every output frame has genuine sub-frame
    motion without `fps=30` duplicated-frame judder or blurry alpha frame-blending.
    Returns `(temp_mp4_path, actual_t0)` when upsampled, or `None` if source is already `>= target_fps - 0.5` or small.
    """
    if not src_path.exists() or src_path.stat().st_size < 4096:
        return None
    cap = cv2.VideoCapture(str(src_path))
    if not cap.isOpened():
        return None
    try:
        src_fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        if src_fps <= 0.5 or src_fps >= float(target_fps) - 0.5 or w < 320 or h < 320:
            return None
        start_f = max(0, int(math.floor(max(0.0, float(s0) - 0.02) * src_fps)))
        end_f = max(start_f + 2, int(math.ceil((float(s1) + float(tail_pad_sec)) * src_fps)) + 1)
        frames: list[np.ndarray] = []
        f_idx = 0
        while f_idx <= end_f:
            if f_idx < start_f:
                if not cap.grab():
                    break
            else:
                ok, frm = cap.read()
                if not ok or frm is None:
                    break
                frames.append(frm)
            f_idx += 1
    finally:
        cap.release()
    if len(frames) < 2:
        return None

    actual_t0 = float(start_f) / src_fps
    t_rel_end = float(len(frames) - 1) / src_fps
    n_out = max(2, int(math.ceil(t_rel_end * float(target_fps))) + 1)
    sw = max(64, ((w // 2) // 2) * 2)
    sh = max(64, ((h // 2) // 2) * 2)
    sx_scale = float(w) / float(sw)
    sy_scale = float(h) / float(sh)
    dis = cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_ULTRAFAST)
    grays = [cv2.cvtColor(cv2.resize(f, (sw, sh), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY) for f in frames]
    grid_x, grid_y = np.meshgrid(np.arange(w, dtype=np.float32), np.arange(h, dtype=np.float32))

    tmp_f = tempfile.NamedTemporaryFile(
        suffix=".mp4",
        prefix="aab_oflow_",
        dir=str(get_ram_scratch_root()),
        delete=False,
    )
    tmp_path = Path(tmp_f.name)
    tmp_f.close()

    cmd_pipe = [
        ff, "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
        "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{w}x{h}", "-r", str(int(target_fps)),
        "-i", "pipe:0",
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "10", "-threads", "1",
        "-pix_fmt", "yuv420p", "-an",
        str(tmp_path),
    ]
    proc: subprocess.Popen[bytes] | None = None
    try:
        proc = subprocess.Popen(cmd_pipe, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        assert proc.stdin is not None
        cached_pair = -1
        cached_fwd: np.ndarray | None = None
        cached_bwd: np.ndarray | None = None
        cached_cut = False
        for k in range(n_out):
            pos = min(float(len(frames) - 1), (float(k) / float(target_fps)) * src_fps)
            i0 = min(len(frames) - 2, max(0, int(math.floor(pos))))
            i1 = i0 + 1
            alpha = max(0.0, min(1.0, pos - float(i0)))
            if alpha <= 0.005:
                out_frm = frames[i0]
            elif alpha >= 0.995:
                out_frm = frames[i1]
            else:
                if i0 != cached_pair:
                    g0, g1 = grays[i0], grays[i1]
                    mad = float(np.mean(np.abs(g1.astype(np.float32) - g0.astype(np.float32))))
                    cached_pair = i0
                    if mad > 68.0:
                        cached_cut = True
                        cached_fwd = None
                        cached_bwd = None
                    else:
                        cached_cut = False
                        f_low = dis.calc(g0, g1, None)
                        b_low = dis.calc(g1, g0, None)
                        ff_full = cv2.resize(f_low, (w, h), interpolation=cv2.INTER_LINEAR)
                        fb_full = cv2.resize(b_low, (w, h), interpolation=cv2.INTER_LINEAR)
                        ff_full[:, :, 0] *= sx_scale
                        ff_full[:, :, 1] *= sy_scale
                        fb_full[:, :, 0] *= sx_scale
                        fb_full[:, :, 1] *= sy_scale
                        cached_fwd = ff_full
                        cached_bwd = fb_full
                if cached_cut or cached_fwd is None or cached_bwd is None:
                    out_frm = frames[i0 if alpha < 0.5 else i1]
                else:
                    # Warp frames cleanly along bidirectional displacement fields without ghost crossfade.
                    m0x = grid_x - alpha * cached_fwd[:, :, 0]
                    m0y = grid_y - alpha * cached_fwd[:, :, 1]
                    m1x = grid_x - (1.0 - alpha) * cached_bwd[:, :, 0]
                    m1y = grid_y - (1.0 - alpha) * cached_bwd[:, :, 1]
                    w0 = cv2.remap(frames[i0], m0x, m0y, interpolation=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
                    w1 = cv2.remap(frames[i1], m1x, m1y, interpolation=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
                    out_frm = cv2.addWeighted(w0, 1.0 - alpha, w1, alpha, 0.0)
            proc.stdin.write(np.ascontiguousarray(out_frm).tobytes())
        proc.stdin.close()
        proc.wait(timeout=120)
        if proc.returncode != 0 or not tmp_path.exists() or tmp_path.stat().st_size < 1024:
            tmp_path.unlink(missing_ok=True)
            return None
        return tmp_path, round(actual_t0, 6)
    except Exception:
        if proc is not None:
            try:
                if proc.stdin:
                    proc.stdin.close()
                proc.kill()
            except Exception:
                pass
        tmp_path.unlink(missing_ok=True)
        return None


def _render_cut_segment(
    ff: str,
    cut: dict[str, Any],
    clips_by_num: dict[int, Path],
    out_seg: Path,
    fps: int,
    pastel_eq_by_num: dict[int, str] | None = None,
    ass_burn_chain: str = "",
    crf: int = 18,
    preset: str = "veryfast",
    cwd: Path | None = None,
    single_frame_offset_sec: float | None = None,
    override_frames: int | None = None,
    ffmpeg_threads: int = 1,
) -> None:
    """Renders one frame-exact stitchable H.264 cut segment (`1080x1920 @ fps`, optional single-pass ASS burn-in or 1-frame PNG)."""
    c_frames = int(override_frames if override_frames is not None else cut["frames"])
    out_dur = c_frames / float(fps)
    c1_num = int(cut["clip_index"])
    p1 = clips_by_num[c1_num]
    eq1 = (pastel_eq_by_num or {}).get(c1_num, "")
    s0, s1 = _clamp_source_window_to_eof(p1, float(cut["src_start_sec"]), float(cut["src_end_sec"]))
    src_dur = max(0.20, s1 - s0)
    pts_ratio = out_dur / src_dur
    if bool(cut.get("forbid_slowmo_stretch")):
        pts_ratio = min(1.0, pts_ratio)
    zoom = float(cut.get("crop_zoom") or 1.0)
    scaled_w = int(round(VIDEO_WIDTH * zoom))
    scaled_h = int(round(VIDEO_HEIGHT * zoom))
    scaled_w += scaled_w % 2
    scaled_h += scaled_h % 2

    # Never use FFmpeg double-image alpha frame-blending (causes blurry ghosting); use bidirectional DISOpticalFlow instead.
    pre_interp_1 = ""
    s1_pad = s1 + (0.05 if pts_ratio > 1.22 else 0.04)
    stop_pad = max(1.50, out_dur + 1.00)
    tmp_oflow_paths: list[Path] = []
    allow_oflow = single_frame_offset_sec is None and not bool(cut.get("disable_optical_flow"))
    try:
        if allow_oflow and (pts_ratio >= 0.76 or int(fps) >= 29):
            # At ~1.25x speed on a 24fps source (24 / 0.80 = 30.0fps), native frames already supply >= target_fps
            # without synthetic optical-flow interpolation blur or dropped-frame cadence judder.
            cap_chk = cv2.VideoCapture(str(p1))
            src_fps_chk = float(cap_chk.get(cv2.CAP_PROP_FPS) or 0.0) if cap_chk.isOpened() else 0.0
            cap_chk.release()
            eff_src_rate = src_fps_chk / max(0.25, float(pts_ratio)) if src_fps_chk > 0.5 else 0.0
            up1 = (
                None
                if (pts_ratio < 0.96 and abs(eff_src_rate - float(fps)) <= 0.65)
                else _upsample_clip_window_optical_flow(ff, p1, s0, s1, int(fps), tail_pad_sec=0.22)
            )
            if up1 is not None:
                p1_up, t0_1 = up1
                tmp_oflow_paths.append(p1_up)
                p1 = p1_up
                s0 = max(0.0, s0 - t0_1)
                s1 = max(s0 + 0.20, s1 - t0_1)
                s1_pad = max(s1 + 0.04, s1_pad - t0_1)
        tail_trim = f",trim=end_frame={c_frames},setpts=PTS-STARTPTS"
        if single_frame_offset_sec is not None:
            off_t = max(0.0, min(max(0.0, out_dur - (1.0 / float(fps))), float(single_frame_offset_sec)))
            tail_trim = f",trim=start={off_t:.4f},setpts=PTS-STARTPTS"
        eff_ass = "" if single_frame_offset_sec is not None else ass_burn_chain

        v_enc_args = (
            ["-frames:v", "1", str(out_seg)]
            if single_frame_offset_sec is not None
            else [
                "-frames:v", str(c_frames), "-r", str(fps),
                "-c:v", "libx264", "-preset", preset, "-crf", str(crf),
                "-profile:v", "high", "-level:v", "4.2",
                "-x264-params", "stitchable=1",
                "-video_track_timescale", str(fps * 1000),
                "-threads", str(max(1, int(ffmpeg_threads))),
                "-pix_fmt", "yuv420p", "-an",
                str(out_seg),
            ]
        )

        if cut.get("mode") == "split_hstack" and cut.get("secondary_clip_index"):
            c2_num = int(cut["secondary_clip_index"])
            p2 = clips_by_num[c2_num]
            eq2 = (pastel_eq_by_num or {}).get(c2_num, "")
            raw_sec0, raw_sec1 = cut["secondary_src_span"]
            sec0, sec1 = _clamp_source_window_to_eof(p2, float(raw_sec0), float(raw_sec1))
            sec_dur = max(0.20, float(sec1) - float(sec0))
            pts2 = out_dur / sec_dur
            pre_interp_2 = ""
            sec1_pad = float(sec1) + (0.05 if pts2 > 1.22 else 0.04)
            if allow_oflow and pts2 >= 0.85:
                up2 = _upsample_clip_window_optical_flow(ff, p2, sec0, sec1, int(fps), tail_pad_sec=0.22)
                if up2 is not None:
                    p2_up, t0_2 = up2
                    tmp_oflow_paths.append(p2_up)
                    p2 = p2_up
                    sec0 = max(0.0, sec0 - t0_2)
                    sec1 = max(sec0 + 0.20, sec1 - t0_2)
                    sec1_pad = max(sec1 + 0.04, sec1_pad - t0_2)
            div_w = int(DIORAMA_V7_SPLIT_DIVIDER_PX)
            left_w = (VIDEO_WIDTH - div_w) // 2
            right_w = VIDEO_WIDTH - left_w - div_w
            pts_expr_1 = "setpts=PTS-STARTPTS" if abs(pts_ratio - 1.0) <= 0.035 else f"{pre_interp_1}setpts=({pts_ratio:.5f})*(PTS-STARTPTS)"
            pts_expr_2 = "setpts=PTS-STARTPTS" if abs(pts2 - 1.0) <= 0.035 else f"{pre_interp_2}setpts=({pts2:.5f})*(PTS-STARTPTS)"
            fc = (
                f"[0:v]trim=start={s0:.4f}:end={s1_pad:.4f},{pts_expr_1},"
                f"fps={fps},tpad=stop_mode=clone:stop_duration={stop_pad:.4f},"
                f"scale={VIDEO_WIDTH}:{VIDEO_HEIGHT}:force_original_aspect_ratio=increase:flags=lanczos,"
                f"{eq1}unsharp=5:5:0.35:5:5:0.0,format=gbrp,crop={left_w}:{VIDEO_HEIGHT}:(in_w-{left_w})/2:0[left];"
                f"[1:v]trim=start={sec0:.4f}:end={sec1_pad:.4f},{pts_expr_2},"
                f"fps={fps},tpad=stop_mode=clone:stop_duration={stop_pad:.4f},"
                f"scale={VIDEO_WIDTH}:{VIDEO_HEIGHT}:force_original_aspect_ratio=increase:flags=lanczos,"
                f"{eq2}unsharp=5:5:0.35:5:5:0.0,format=gbrp,crop={right_w}:{VIDEO_HEIGHT}:(in_w-{right_w})/2:0[right];"
                f"color=c=black:s={div_w}x{VIDEO_HEIGHT}:r={fps}:d={out_dur + stop_pad:.4f},format=gbrp[div];"
                f"[left][div][right]hstack=inputs=3,setsar=1,format=yuv420p{eff_ass}{tail_trim}[vout]"
            )
            cmd = [
                ff, "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
                "-i", str(p1), "-i", str(p2),
                "-filter_complex", fc, "-map", "[vout]",
                *v_enc_args,
            ]
        elif cut.get("mode") == "split_vstack" and cut.get("secondary_clip_index"):
            p2 = clips_by_num[int(cut["secondary_clip_index"])]
            raw_sec0, raw_sec1 = cut["secondary_src_span"]
            sec0, sec1 = _clamp_source_window_to_eof(p2, float(raw_sec0), float(raw_sec1))
            sec_dur = max(0.20, float(sec1) - float(sec0))
            pts2 = out_dur / sec_dur
            pre_interp_2 = ""
            sec1_pad = float(sec1) + (0.05 if pts2 > 1.22 else 0.04)
            if allow_oflow and pts2 >= 0.85:
                up2 = _upsample_clip_window_optical_flow(ff, p2, sec0, sec1, int(fps), tail_pad_sec=0.22)
                if up2 is not None:
                    p2_up, t0_2 = up2
                    tmp_oflow_paths.append(p2_up)
                    p2 = p2_up
                    sec0 = max(0.0, sec0 - t0_2)
                    sec1 = max(sec0 + 0.20, sec1 - t0_2)
                    sec1_pad = max(sec1 + 0.04, sec1_pad - t0_2)
            half_h = (VIDEO_HEIGHT - 6) // 2
            half_h -= half_h % 2
            rem_h = VIDEO_HEIGHT - half_h - 6
            fc = (
                f"[0:v]trim=start={s0:.4f}:end={s1_pad:.4f},{pre_interp_1}setpts=({pts_ratio:.5f})*(PTS-STARTPTS),"
                f"fps={fps},tpad=stop_mode=clone:stop_duration={stop_pad:.4f},"
                f"scale={VIDEO_WIDTH}:{VIDEO_HEIGHT}:force_original_aspect_ratio=increase:flags=lanczos,"
                f"unsharp=5:5:0.35:5:5:0.0,crop={VIDEO_WIDTH}:{half_h}[top];"
                f"[1:v]trim=start={sec0:.4f}:end={sec1_pad:.4f},{pre_interp_2}setpts=({pts2:.5f})*(PTS-STARTPTS),"
                f"fps={fps},tpad=stop_mode=clone:stop_duration={stop_pad:.4f},"
                f"scale={VIDEO_WIDTH}:{VIDEO_HEIGHT}:force_original_aspect_ratio=increase:flags=lanczos,"
                f"unsharp=5:5:0.35:5:5:0.0,crop={VIDEO_WIDTH}:{rem_h}[bot];"
                f"color=c=white:s={VIDEO_WIDTH}x6:r={fps}:d={out_dur + stop_pad:.4f}[div];"
                f"[top][div][bot]vstack=inputs=3,setsar=1,format=yuv420p{eff_ass}{tail_trim}[vout]"
            )
            cmd = [
                ff, "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
                "-i", str(p1), "-i", str(p2),
                "-filter_complex", fc, "-map", "[vout]",
                *v_enc_args,
            ]
        else:
            use_v8_curve = bool(cut.get("v8_curve_ramp") and single_frame_offset_sec is None and not cut.get("outro_sky_card"))
            use_ramp = bool(cut.get("speed_ramp") and not cut.get("outro_sky_card"))
            if use_v8_curve:
                nom_f = max(c_frames, int(cut.get("curve_nominal_frames") or c_frames))
                nom_dur = max(0.25, nom_f / float(fps))
                s1_curve_pad = s1 + 0.12
                pts_chain = (
                    f"trim=start={s0:.4f}:end={s1_curve_pad:.4f},"
                    "setpts=PTS-STARTPTS,"
                    f"setpts='(({nom_dur:.5f})*(min(T/{src_dur:.5f},1.0)-0.054113*sin(6.283185*min(T/{src_dur:.5f},1.0))+max(0.0,T/{src_dur:.5f}-1.0)*0.66))/TB',"
                )
            elif use_ramp:
                start_spd = max(1.05, float(DIORAMA_ENTRY_RAMP_START_SPEED))
                main_spd = max(0.85, float(cut.get("main_speed") or DIORAMA_ENTRY_RAMP_MAIN_SPEED))
                src_head = round(0.35 * start_spd, 5)
                s1_ramp_pad = s1 + 0.08
                pts_chain = (
                    f"trim=start={s0:.4f}:end={s1_ramp_pad:.4f},"
                    "setpts=PTS-STARTPTS,"
                    f"setpts='(if(lt(T,{src_head:.5f}),T/{start_spd:.5f},0.35+(T-{src_head:.5f})/{main_spd:.5f}))/TB',"
                )
            elif abs(pts_ratio - 1.0) <= 0.035:
                pts_chain = f"trim=start={s0:.4f}:end={s1 + 0.08:.4f},setpts=PTS-STARTPTS,"
            else:
                pts_chain = (
                    f"trim=start={s0:.4f}:end={s1_pad:.4f},"
                    f"{pre_interp_1}"
                    f"setpts=({pts_ratio:.5f})*(PTS-STARTPTS),"
                )
            portal_zoom_parts: list[str] = []
            pz_head = int(cut.get("_portal_zoom_head_frames") or 0)
            pz_tail_start = cut.get("_portal_zoom_tail_start_f")
            if single_frame_offset_sec is None and (pz_head > 0 or pz_tail_start is not None):
                z_expr = "1.0"
                if pz_head > 0 and pz_tail_start is not None:
                    ts_i = max(1, int(pz_tail_start))
                    span_t = max(2, c_frames - ts_i)
                    z_expr = f"if(lte(n,{pz_head}),1.16-0.16*n/{float(pz_head):.1f},if(gte(n,{ts_i}),1.0+0.20*(n-{ts_i})/{float(span_t):.1f},1.0))"
                elif pz_head > 0:
                    z_expr = f"if(lte(n,{pz_head}),1.16-0.16*n/{float(pz_head):.1f},1.0)"
                elif pz_tail_start is not None:
                    ts_i = max(1, int(pz_tail_start))
                    span_t = max(2, c_frames - ts_i)
                    z_expr = f"if(gte(n,{ts_i}),1.0+0.20*(n-{ts_i})/{float(span_t):.1f},1.0)"
                portal_zoom_parts.append(
                    f"scale=w='trunc(iw*({z_expr})/2)*2':h='trunc(ih*({z_expr})/2)*2':eval=frame:flags=bicubic,"
                    f"crop={VIDEO_WIDTH}:{VIDEO_HEIGHT}:'(in_w-{VIDEO_WIDTH})/2':'(in_h-{VIDEO_HEIGHT})/2',"
                )
            elif (
                single_frame_offset_sec is None
                and not cut.get("outro_sky_card")
                and c_frames >= 20
                and any(k in str(cut.get("camera_move") or "").lower() for k in ("push", "pull", "dolly", "orbit"))
            ):
                # Locked-camera Flow Start->End color-morph clips (e.g. K06 twin stacked brains over #040711 void)
                # can have near-zero frame-to-frame camera motion (median center-ROI diff < 0.30).
                # Apply a silky sub-pixel 5.5% Ken Burns micro-push/pull so 30fps temporal motion stays fluid (0 frozen pairs).
                try:
                    cap_m = cv2.VideoCapture(str(p1))
                    if cap_m.isOpened():
                        fps_m = max(1.0, float(cap_m.get(cv2.CAP_PROP_FPS) or 24.0))
                        f_a = max(0, int(round(s0 * fps_m)))
                        f_b = max(f_a + 4, int(round(s1 * fps_m)))
                        sample_idxs = sorted({min(f_b - 1, f_a + int((f_b - f_a) * r)) for r in (0.15, 0.35, 0.55, 0.75)})
                        m_diffs: list[float] = []
                        for si in sample_idxs:
                            cap_m.set(cv2.CAP_PROP_POS_FRAMES, si)
                            ok_1, fr_1 = cap_m.read()
                            ok_2, fr_2 = cap_m.read()
                            if ok_1 and ok_2 and fr_1 is not None and fr_2 is not None:
                                g1 = cv2.cvtColor(fr_1, cv2.COLOR_BGR2GRAY)
                                g2 = cv2.cvtColor(fr_2, cv2.COLOR_BGR2GRAY)
                                hh, ww = g1.shape[:2]
                                r1 = g1[int(hh * 0.30):int(hh * 0.68), int(ww * 0.12):int(ww * 0.88)]
                                r2 = g2[int(hh * 0.30):int(hh * 0.68), int(ww * 0.12):int(ww * 0.88)]
                                m_diffs.append(float(np.mean(cv2.absdiff(r1, r2))))
                        cap_m.release()
                        if m_diffs and float(np.median(m_diffs)) < 0.30:
                            is_pull_cam = "pull" in str(cut.get("camera_move") or "").lower()
                            zp_expr = (
                                f"1.055-0.055*min(1,in/{max(1, c_frames):.1f})"
                                if is_pull_cam
                                else f"1+0.055*min(1,in/{max(1, c_frames):.1f})"
                            )
                            portal_zoom_parts.append(
                                f"zoompan=z='{zp_expr}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s={VIDEO_WIDTH}x{VIDEO_HEIGHT}:fps={fps},"
                            )
                except Exception:
                    pass
            portal_zoom_str = "".join(portal_zoom_parts)
            vf = (
                f"{pts_chain}"
                f"fps={fps},"
                f"tpad=stop_mode=clone:stop_duration={stop_pad:.4f},"
                f"scale={scaled_w}:{scaled_h}:force_original_aspect_ratio=increase:flags=lanczos,"
                f"{eq1}unsharp=5:5:0.75:3:3:0.35,"
                f"crop={VIDEO_WIDTH}:{VIDEO_HEIGHT},"
                f"{portal_zoom_str}"
                f"setsar=1,format=yuv420p"
            )
            if cut.get("outro_sky_card"):
                fade_s = max(0.0, out_dur - 0.14)
                vf += f",fade=t=out:st={fade_s:.3f}:d=0.12"
            if eff_ass:
                vf += eff_ass
            if tail_trim:
                vf += tail_trim
            cmd = [
                ff, "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
                "-i", str(p1), "-vf", vf,
                *v_enc_args,
            ]
        res = subprocess.run(
            cmd,
            cwd=(str(cwd) if cwd is not None else None),
            capture_output=True,
            text=True,
            check=False,
            timeout=180,
            stdin=subprocess.DEVNULL,
        )
        if res.returncode != 0 or not out_seg.exists():
            raise RuntimeError(f"Failed rendering EDL cut {cut['cut_index']}: {res.stderr[:280]}")
        if single_frame_offset_sec is None:
            rendered_f = _probe_segment_frame_count(out_seg)
            if rendered_f < c_frames:
                raise RuntimeError(
                    f"Rendered EDL cut {cut['cut_index']} truncated: got {rendered_f} frames < expected {c_frames} frames ({out_seg.name})"
                )
    finally:
        for tp in tmp_oflow_paths:
            tp.unlink(missing_ok=True)


def _atomic_copy_file(src: Path, dst: Path, suffix: str | None = None) -> None:
    """Copies `src` to a temporary sibling file and atomically replaces `dst` via `atomic_commit_from_scratch` (`EXDEV`-safe, preserves `src`)."""
    atomic_commit_from_scratch(src, dst, suffix=suffix, keep_src=True)


from pipeline.config import DIORAMA_MUX_TRUE_PEAK_LIMITER, DIORAMA_MUX_TRUE_PEAK_TARGET_DBTP  # noqa: E402


def _measure_true_peak_dbtp(path: Path) -> float | None:
    """4x-oversampled BS.1770 true peak (dBTP) of the first audio stream via FFmpeg `ebur128=peak=true`."""
    try:
        res = subprocess.run(
            [_ffmpeg(), "-nostdin", "-hide_banner", "-i", str(path), "-map", "0:a:0", "-af", "ebur128=peak=true", "-f", "null", "-"],
            capture_output=True, text=True, check=False, timeout=180, stdin=subprocess.DEVNULL,
        )
        m = re.findall(r"Peak:\s*(-?[\d.]+|-inf)\s*dBFS", res.stderr or "")
        if not m or m[-1] == "-inf":
            return None
        return float(m[-1])
    except Exception:  # noqa: BLE001
        return None


def _write_distinct_thumbnails(
    mp4_path: Path,
    pub_dir: Path,
    total_dur: float,
    overwrite: bool = False,
) -> None:
    """R65 wrapper: delegates project thumbnail generation to `pipeline.thumbnail_studio.run` (falling back to 3-point extraction only for standalone MP4s)."""
    pub_dir.mkdir(parents=True, exist_ok=True)
    p_dir = pub_dir.parent
    if (p_dir / "05_assembly").exists() or (p_dir / "03_visuals").exists():
        try:
            from pipeline import thumbnail_studio

            thumbnail_studio.run(p_dir, force=overwrite, strict=False)
            return
        except Exception:
            pass
    targets = [
        ("thumbnail_var_A.png", min(total_dur * 0.10, 4.5)),
        ("thumbnail_var_B.png", total_dur * 0.54),
        ("thumbnail_var_C.png", total_dur * 0.84),
    ]
    pending = [
        (fname, t_sec)
        for fname, t_sec in targets
        if overwrite or not (pub_dir / fname).exists() or (pub_dir / fname).stat().st_size == 0
    ]
    if not pending:
        return
    cap = cv2.VideoCapture(str(mp4_path))
    fps = cap.get(cv2.CAP_PROP_FPS) or float(VIDEO_FPS)
    for fname, t_sec in pending:
        cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, int(round(t_sec * fps))))
        ok, frame = cap.read()
        if ok and frame is not None:
            dst = pub_dir / fname
            tmp_png = dst.with_name(f".tmp_{os.getpid()}_{fname}")
            cv2.imwrite(str(tmp_png), frame)
            os.replace(tmp_png, dst)
    cap.release()


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


def refine_plaque_safe_source_windows(
    edl: dict[str, Any],
    clip_files: list[Path],
    run_fail_threshold: int = 5,
    max_candidates: int = 48,
    cache_dir: Path | None = None,
) -> list[dict[str, Any]]:
    """
    F-1 pre-render plaque guard: probes every single-mode cut's source window at the exact frames DQ9
    (`start+0.08`, mid, `end-0.08` on 1080x1920 non-subtitle ROIs) and R64 (12/31/50/69/88% on the 360x640 grid)
    will later inspect. When any probe hits a horizontal glyph run >= `run_fail_threshold`, the window slides
    (closest-first, 0.125s steps) to the nearest start whose probes all stay below the threshold. Mutates `edl`.
    """
    from pipeline.dynamic_episode_qa import _non_subtitle_scene_rois
    from pipeline.flow_diorama_sharded_worker import _max_horizontal_plaque_glyph_run
    from pipeline.media_cache import fast_file_sha256, stage_local_file

    clips_by_num = {i: Path(cf) for i, cf in enumerate(clip_files, start=1)}
    plaque_cache_p = (Path(cache_dir) / "plaque_cache.json") if cache_dir else None
    plaque_cache: dict[str, Any] = {}
    if plaque_cache_p and plaque_cache_p.is_file():
        try:
            plaque_cache = json.loads(plaque_cache_p.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            plaque_cache = {}
    plaque_cache_dirty = False
    clip_sha_by_num: dict[int, str] = {}
    caps: dict[int, Any] = {}
    fps_by: dict[int, float] = {}
    nframes_by: dict[int, int] = {}
    memo: dict[tuple[int, int], int] = {}

    def _cap(num: int) -> Any:
        if num not in caps:
            local_p, _ = stage_local_file(clips_by_num[num])
            cap = cv2.VideoCapture(str(local_p))
            caps[num] = cap
            fps_by[num] = float(cap.get(cv2.CAP_PROP_FPS) or 24.0)
            nframes_by[num] = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        return caps[num]

    is_v8_ref = is_expressive_v8_plan(edl)

    def _run_at(num: int, t_sec: float) -> int:
        cap = _cap(num)
        f_idx = max(0, min(max(0, nframes_by[num] - 1), int(round(t_sec * fps_by[num]))))
        key = (num, f_idx)
        if key in memo:
            return memo[key]
        cap.set(cv2.CAP_PROP_POS_FRAMES, f_idx)
        ok, frm = cap.read()
        if not ok or frm is None:
            memo[key] = 0
            return 0
        f1080 = cv2.resize(frm, (VIDEO_WIDTH, VIDEO_HEIGHT), interpolation=cv2.INTER_LINEAR)
        r_hi = max(
            (
                _max_horizontal_plaque_glyph_run(r)
                for r in _non_subtitle_scene_rois(
                    f1080,
                    has_top_overlay=False,
                    is_outro=False,
                    is_expressive_v8=is_v8_ref,
                )
            ),
            default=0,
        )
        small = cv2.resize(frm, (360, 640), interpolation=cv2.INTER_AREA)
        roi = cv2.cvtColor(small[int(640 * 0.06) : int(640 * 0.92), int(360 * 0.06) : int(360 * 0.94)], cv2.COLOR_BGR2GRAY)
        r_lo = _max_horizontal_plaque_glyph_run(roi)
        memo[key] = int(max(r_hi, r_lo))
        return memo[key]

    refinements: list[dict[str, Any]] = []
    try:
        for cut in edl.get("cuts") or []:
            if cut.get("mode") != "single" or cut.get("outro_sky_card"):
                continue
            if is_v8_ref and cut.get("diegetic_text_allowlist"):
                continue
            num = int(cut["clip_index"])
            if num not in clips_by_num or not clips_by_num[num].exists():
                continue
            s0 = float(cut["src_start_sec"])
            span = max(0.05, float(cut["src_end_sec"]) - s0)
            out_d = max(0.05, float(cut["duration_sec"]))
            c_sha = ""
            if plaque_cache_p is not None:
                if num not in clip_sha_by_num:
                    clip_sha_by_num[num] = fast_file_sha256(clips_by_num[num])
                c_sha = clip_sha_by_num[num]
                p_key = f"{c_sha}|{s0:.4f}|{span:.4f}|{out_d:.4f}|{int(is_v8_ref)}|{run_fail_threshold}"
                if p_key in plaque_cache:
                    hit_entry = plaque_cache[p_key]
                    if hit_entry.get("to_src_start") is not None:
                        cand_hit = float(hit_entry["to_src_start"])
                        cut["src_start_sec"] = round(cand_hit, 4)
                        cut["src_end_sec"] = round(cand_hit + span, 4)
                    if hit_entry.get("refinement"):
                        ref_cp = dict(hit_entry["refinement"])
                        ref_cp["cut_index"] = cut["cut_index"]
                        refinements.append(ref_cp)
                    continue
            else:
                p_key = ""
            ratio = span / out_d
            offs = sorted(
                {
                    round(min(out_d, max(0.0, o)), 4)
                    for o in (0.08, max(0.08, out_d - 0.08), 0.5 * out_d, 0.12 * out_d, 0.31 * out_d, 0.69 * out_d, 0.88 * out_d)
                }
            )

            def _probe(start: float, _num: int = num, _offs: tuple[float, ...] = tuple(offs), _ratio: float = ratio) -> int:
                return max(_run_at(_num, start + o * _ratio) for o in _offs)

            worst = _probe(s0)
            if worst < run_fail_threshold:
                if p_key:
                    plaque_cache[p_key] = {"to_src_start": None, "refinement": None}
                    plaque_cache_dirty = True
                continue
            clip_dur = max(span + 0.2, float(_clip_duration(clips_by_num[num])))
            max_start = max(0.08, clip_dur - 0.08 - span)
            grid = [round(0.08 + 0.125 * k, 4) for k in range(int((max_start - 0.08) / 0.125) + 1)]
            grid = sorted(grid, key=lambda c: abs(c - s0))[:max_candidates]
            fixed = False
            for cand in grid:
                if abs(cand - s0) < 1e-6:
                    continue
                if _probe(cand) < run_fail_threshold:
                    cut["src_start_sec"] = round(cand, 4)
                    cut["src_end_sec"] = round(cand + span, 4)
                    ref_item = {"cut_index": cut["cut_index"], "clip_index": num, "from_src_start": round(s0, 4), "to_src_start": round(cand, 4), "worst_run_before": worst}
                    refinements.append(ref_item)
                    if p_key:
                        plaque_cache[p_key] = {"to_src_start": round(cand, 4), "refinement": ref_item}
                        plaque_cache_dirty = True
                    fixed = True
                    break
            if not fixed:
                ref_unres = {"cut_index": cut["cut_index"], "clip_index": num, "status": "unresolved", "worst_run": worst}
                refinements.append(ref_unres)
                if p_key:
                    plaque_cache[p_key] = {"to_src_start": None, "refinement": ref_unres}
                    plaque_cache_dirty = True
    finally:
        for cap in caps.values():
            cap.release()
        if plaque_cache_p is not None and plaque_cache_dirty:
            try:
                plaque_cache_p.write_text(json.dumps(plaque_cache, indent=2), encoding="utf-8")
            except OSError:
                pass
    return refinements


def _segment_cache_dir(p_dir: Path) -> Path:
    from pipeline.media_cache import get_speed_cache_dir

    h = hashlib.sha1(str(Path(p_dir).resolve()).encode("utf-8")).hexdigest()[:16]
    d = get_speed_cache_dir() / "segments" / h
    d.mkdir(parents=True, exist_ok=True)
    return d


def _store_segment_cache(p_dir: Path, seg_jobs: list[tuple[dict[str, Any], Path, int, float]], edl: dict[str, Any], ass_path: Path) -> None:
    """F-3: persists rendered stitchable segments (local SSD cache) so `recut_diorama_cuts` can re-render single cuts."""
    try:
        cdir = _segment_cache_dir(p_dir)
        index: dict[str, Any] = {"ass_sha1": hashlib.sha1(Path(ass_path).read_bytes()).hexdigest(), "fps": int(edl["fps"]), "segments": []}
        for cut, s_path, eff_f, start_s in seg_jobs:
            dst = cdir / s_path.name
            shutil.copy2(s_path, dst)
            index["segments"].append({"cut_index": int(cut["cut_index"]), "file": dst.name, "frames": int(eff_f), "start_sec": round(start_s, 6)})
        (cdir / "index.json").write_text(json.dumps(index, indent=2), encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass


def _raw_cut_cache_path(
    p_dir: Path,
    cut: dict[str, Any],
    local_clips: dict[int, Path],
    fps: int,
    f_cnt: int,
    pastel_eq_by_num: dict[int, str],
    ass_burn_chain: str = "",
    ass_sha1: str = "",
) -> Path | None:
    """Deterministic local-SSD segment cache path (`/tmp/aab_speed_cache/segments/<proj>/raw_v8/<sha1>.mp4`)."""
    from pipeline.media_cache import fast_file_sha256

    c1_num = int(cut.get("clip_index") or 0)
    p1 = local_clips.get(c1_num)
    if p1 is None or not p1.exists():
        return None
    sha1_clip = fast_file_sha256(p1)
    c2_num = int(cut.get("secondary_clip_index") or 0)
    sha2_clip = ""
    if c2_num > 0:
        p2 = local_clips.get(c2_num)
        if p2 is None or not p2.exists():
            return None
        sha2_clip = fast_file_sha256(p2)
    render_spec = {
        "mode": cut.get("mode", "single"),
        "s0": round(float(cut.get("src_start_sec") or 0.0), 4),
        "s1": round(float(cut.get("src_end_sec") or 0.0), 4),
        "sec_span": cut.get("secondary_src_span"),
        "zoom": round(float(cut.get("crop_zoom") or 1.0), 4),
        "v8_curve": bool(cut.get("v8_curve_ramp")),
        "curve_nom_f": int(cut.get("curve_nominal_frames") or f_cnt) if cut.get("v8_curve_ramp") else 0,
        "speed_ramp": bool(cut.get("speed_ramp")),
        "main_speed": round(float(cut.get("main_speed") or 0.0), 4) if cut.get("speed_ramp") else 0.0,
        "outro": bool(cut.get("outro_sky_card")),
        "pz_head": int(cut.get("_portal_zoom_head_frames") or 0),
        "pz_tail": cut.get("_portal_zoom_tail_start_f"),
        "fps": int(fps),
        "frames": int(f_cnt),
        "eq1": (pastel_eq_by_num or {}).get(c1_num, ""),
        "eq2": (pastel_eq_by_num or {}).get(c2_num, "") if c2_num > 0 else "",
        "burn": ass_burn_chain if ass_burn_chain else "",
        "ass_sha1": ass_sha1 if ass_burn_chain else "",
    }
    raw_key = hashlib.sha1(
        f"raw_v8_v2_noblend|{sha1_clip}|{sha2_clip}|{json.dumps(render_spec, sort_keys=True)}".encode("utf-8")
    ).hexdigest()[:24]
    raw_dir = _segment_cache_dir(p_dir) / "raw_v8"
    raw_dir.mkdir(parents=True, exist_ok=True)
    return raw_dir / f"{raw_key}.mp4"


def recut_diorama_cuts(
    project_id_or_dir: str | Path,
    cut_indices: list[int],
    allow_published_overwrite: bool = False,
    cpu_budget: int | None = None,
) -> dict[str, Any]:
    """
    F-3 official partial re-render: re-renders only `cut_indices` from the current EDL (font-safe libass burn-in at the
    exact output offset), reuses every other cached segment, re-concats with `-c:v copy`, and re-muxes audio_master.wav.
    """
    from pipeline.media_cache import stage_local_file

    p_dir = Path(project_id_or_dir) if Path(str(project_id_or_dir)).exists() else (PROJECTS_DIR / str(project_id_or_dir))
    if (p_dir / "06_publish" / "upload_receipt.json").exists() and not allow_published_overwrite:
        raise RuntimeError(f"Refusing to recut published project {p_dir.name} (pass allow_published_overwrite=True)")
    verify_script_audio_freshness(p_dir, context="recut_diorama_cuts")
    asm_dir = p_dir / "05_assembly"
    edl = json.loads((asm_dir / "edit_decision_list.json").read_text(encoding="utf-8"))
    if any(
        str(c.get("transition_out") or "").strip().lower()
        in (
            "dissolve_6f",
            "dissolve_8f",
            "dissolve_12f",
            "dissolve_15f",
            "portal_crash_zoom_10f",
            "whip_pan_blur_8f",
            "occlusion_wipe",
            "split_screen_wipe",
            "match_cut_bridge",
            "daisy_chain_bridge",
        )
        for c in (edl.get("cuts") or [])
    ):
        keep_audio = (p_dir / "04_audio" / "audio_master.wav").exists() and (p_dir / "04_audio" / "voice_report.json").exists()
        res = assemble_diorama_project(
            p_dir,
            force_rebuild=True,
            preserve_audio_master=keep_audio,
            allow_published_overwrite=allow_published_overwrite,
            cpu_budget=cpu_budget,
        )
        res["recut_cuts"] = sorted({int(c) for c in cut_indices})
        return res
    ass_path = p_dir / "04_audio" / "subtitles.ass"
    wav_path = p_dir / "04_audio" / "audio_master.wav"
    cdir = _segment_cache_dir(p_dir)
    idx_p = cdir / "index.json"
    if not idx_p.exists():
        raise RuntimeError("No segment cache for this project; run a full diorama-assemble first.")
    index = json.loads(idx_p.read_text(encoding="utf-8"))
    if index.get("ass_sha1") != hashlib.sha1(ass_path.read_bytes()).hexdigest():
        raise RuntimeError("subtitles.ass changed since the cached render; run a full diorama-assemble instead.")
    segs = index["segments"]
    missing = [s["file"] for s in segs if not (cdir / s["file"]).exists()]
    if missing:
        raise RuntimeError(f"Segment cache incomplete ({len(missing)} missing); run a full diorama-assemble.")
    want = {int(c) for c in cut_indices}
    cuts_by_idx = {int(c["cut_index"]): c for c in edl["cuts"]}
    clip_files = _resolve_diorama_clip_files(p_dir / "03_visuals")
    ff = _ffmpeg()
    fps = int(index["fps"])
    with ram_tempdir(prefix="aab_recut_") as td:
        td_path = Path(td)
        need_nums = set()
        for ci in want:
            c = cuts_by_idx[ci]
            need_nums.add(int(c["clip_index"]))
            if c.get("secondary_clip_index"):
                need_nums.add(int(c["secondary_clip_index"]))
        local_clips = {n: stage_local_file(clip_files[n - 1])[0] for n in need_nums}
        pastel = (
            {}
            if (is_porcelain_v7_plan(edl) or is_expressive_v8_plan(edl))
            else {n: _compute_v7_pastel_eq_filter(local_clips[n]) for n in need_nums}
        )
        shutil.copy2(ass_path, td_path / "subtitles.ass")
        fonts_dir = td_path / "fonts"
        fonts_dir.mkdir()
        bundled = ensure_bundled_condensed_font()
        shutil.copy2(bundled, fonts_dir / bundled.name)
        font_rep = probe_ass_font_resolution(ff, td_path, "subtitles.ass", fontsdir="fonts")
        if not font_rep["passed"]:
            raise RuntimeError(f"F-2 font guard failed during recut: {font_rep['fallbacks'][:2]}")
        ass_filter = "ass=subtitles.ass:fontsdir=fonts"
        recut_targets = [s for s in segs if s["cut_index"] in want]
        recut_workers = min(resolve_assembler_workers(cpu_budget), max(1, len(want)))
        recut_ff_threads = resolve_ffmpeg_threads_per_worker(recut_workers, cpu_budget)

        def _recut_one_seg(s_entry: dict[str, Any]) -> None:
            out_seg = td_path / s_entry["file"]
            burn = f",setpts=PTS+{float(s_entry['start_sec']):.6f}/TB,{ass_filter},setpts=PTS-STARTPTS"
            _render_cut_segment(
                ff,
                cuts_by_idx[s_entry["cut_index"]],
                local_clips,
                out_seg,
                fps,
                pastel_eq_by_num=pastel,
                ass_burn_chain=burn,
                crf=18,
                preset="veryfast",
                cwd=td_path,
                override_frames=int(s_entry["frames"]),
                ffmpeg_threads=recut_ff_threads,
            )
            _atomic_copy_file(out_seg, cdir / s_entry["file"])

        if recut_targets:
            prev_cv_threads = cv2.getNumThreads()
            if recut_workers > 1 and prev_cv_threads > 1:
                cv2.setNumThreads(1)
            try:
                with ThreadPoolExecutor(max_workers=recut_workers) as recut_pool:
                    list(recut_pool.map(_recut_one_seg, recut_targets))
            finally:
                if recut_workers > 1 and prev_cv_threads > 1:
                    cv2.setNumThreads(prev_cv_threads)
        concat_txt = td_path / "concat.txt"
        concat_txt.write_text("\n".join(f"file '{(cdir / s['file']).as_posix()}'" for s in segs) + "\n", encoding="utf-8")
        shutil.copy2(wav_path, td_path / "audio_master.wav")
        cum = sum(int(s["frames"]) for s in segs)
        recut_ceil_sec = EXPRESSIVE_V8_HARD_CEILING_SEC if is_expressive_v8_plan(edl) else SHORTS_HARD_CEILING_SEC
        exact_dur = min(recut_ceil_sec, cum / float(fps))
        local_final = td_path / "final_shorts_1080x1920.mp4"

        def _recut_mux(trim_db: float) -> subprocess.CompletedProcess:
            vol = f"volume={trim_db:.2f}dB," if trim_db < 0 else ""
            return subprocess.run(
                [
                    ff, "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
                    "-f", "concat", "-safe", "0", "-i", "concat.txt", "-i", "audio_master.wav",
                    "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy",
                    "-af", f"atrim=0:{exact_dur:.6f},asetpts=PTS-STARTPTS,{vol}{DIORAMA_MUX_TRUE_PEAK_LIMITER}",
                    "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", str(DIORAMA_V7_AUDIO_CHANNELS),
                    "-movflags", "+faststart", local_final.name,
                ],
                cwd=str(td_path), capture_output=True, text=True, check=False, timeout=300, stdin=subprocess.DEVNULL,
            )

        res = _recut_mux(0.0)
        recut_trim_db = 0.0
        for _ in range(3):  # AAC true-peak guard (see assemble_diorama_project)
            if res.returncode != 0 or not local_final.exists():
                break
            tp_enc = _measure_true_peak_dbtp(local_final)
            if tp_enc is None or tp_enc <= DIORAMA_MUX_TRUE_PEAK_TARGET_DBTP:
                break
            recut_trim_db -= (tp_enc - DIORAMA_MUX_TRUE_PEAK_TARGET_DBTP) + 0.1
            res = _recut_mux(recut_trim_db)
        if res.returncode != 0 or not local_final.exists():
            raise RuntimeError(f"recut mux failed: {res.stderr[:300]}")
        final_mp4 = asm_dir / "final_shorts_1080x1920.mp4"
        _atomic_copy_file(local_final, final_mp4, suffix=".mp4.tmp")
    (asm_dir / "font_probe.json").write_text(json.dumps(font_rep, indent=2, ensure_ascii=False), encoding="utf-8")
    try:
        from pipeline import thumbnail_studio

        thumbnail_studio.run(p_dir, force=True, strict=False)
    except Exception:
        logger.warning("Non-fatal thumbnail refresh error during recut_diorama_cuts for %s", p_dir.name, exc_info=True)
    enforce_ram_scratch_budget()
    return {"project_dir": str(p_dir), "final_mp4": str(final_mp4), "recut_cuts": sorted(want), "frames": cum}


def assemble_diorama_project(
    project_id_or_dir: str | Path,
    force_rebuild: bool = True,
    align_whisper: bool = True,
    pre_synthesized_lines: list[np.ndarray] | None = None,
    tts_rate: str | None = None,
    run_posthoc_qa: bool = False,
    source_window_overrides: dict[int, Any] | None = None,
    apply_posthoc_window_shifts: bool = True,
    prosody_mode: str | None = None,
    voice_preset: str | None = None,
    preview_sec: float | None = None,
    allow_published_overwrite: bool = False,
    optimize_plaque_windows: bool = True,
    preserve_audio_master: bool = False,
    cpu_budget: int | None = None,
) -> dict[str, Any]:
    """
    End-to-end Schema v6 / Schema v7 `neuro_diorama` Gear 4 assembly:
      - Schema v7 (`porcelain_cinematic_v7` / `lowpoly_pastel_v7`): `DIORAMA_VOICE_PRESETS` (`andrew_v7` / `emma_v7` / `ava_v7` / `aria_v7` / `christopher_v7`)
        breath-trimmed master clock (`dynamic_us_v7` / `dynamic_rush_v7`), `24.0fps` `1.00x` dynamic-rhythm 1:1 Zero-Reuse EDL,
        `split_hstack` `6px` black vertical divider, bundled `AABCondensed-Black.ttf` subtitles + `276pt` chapter headlines, and 2ch stereo score.
      - Schema v6 (`neuro_diorama`): `30fps` NLE EDL (`<= 5,370 frames`), `Y=64%` single-line ASS, `-24 dB` BGM.
    """
    from pipeline.config import (
        EXPRESSIVE_V8_CLIP_COUNT_RANGE,
        EXPRESSIVE_V8_DISSOLVE_8_FRAMES,
        EXPRESSIVE_V8_DISSOLVE_FRAMES,
        EXPRESSIVE_V8_PORTAL_ZOOM_FRAMES,
        EXPRESSIVE_V8_WHIP_PAN_FRAMES,
        MICRO_SHORT_CUT_MIN,
        MICRO_SHORT_PROFILE,
        PROMPT_SCHEMA_VERSION_V8,
        SHORTS_90S_CLIP_COUNT_MIN,
        SHORTS_90S_PROFILE,
        SHORTS_EXPRESSIVE_V8_PROFILE,
        is_expressive_v8_plan,
        resolve_shorts_format_profile,
        shorts_duration_range_for_profile,
    )

    p_dir = Path(project_id_or_dir) if Path(str(project_id_or_dir)).exists() else (PROJECTS_DIR / str(project_id_or_dir))
    final_mp4 = p_dir / "05_assembly" / "final_shorts_1080x1920.mp4"
    if final_mp4.exists() and not force_rebuild and preview_sec is None:
        verify_script_audio_freshness(p_dir, context="assemble_diorama_project(force_rebuild=False)")
        return {"project_dir": str(p_dir), "final_mp4": str(final_mp4), "rebuilt": False}
    upload_receipt = p_dir / "06_publish" / "upload_receipt.json"
    if upload_receipt.exists() and not allow_published_overwrite:
        try:
            vid = json.loads(upload_receipt.read_text(encoding="utf-8")).get("video_id")
        except Exception:  # noqa: BLE001
            vid = "unknown"
        raise RuntimeError(
            f"Refusing to rebuild {p_dir.name}: it is already published (video_id={vid}). "
            "Rebuild a lab copy instead, or pass allow_published_overwrite=True / --allow-published-overwrite."
        )

    vp_path = next((p for p in (p_dir / "03_visuals" / "visual_plan.json", p_dir / "visual_plan.json") if p.exists()), None)
    visual_plan = json.loads(vp_path.read_text(encoding="utf-8")) if vp_path else {}
    if isinstance(visual_plan, dict):
        visual_plan = {**visual_plan, "_visuals_dir": str(p_dir / "03_visuals")}
    sentences, script_doc = load_diorama_script_sentences(p_dir)
    fmt_profile = resolve_shorts_format_profile(
        visual_plan,
        script_doc,
        {"sentences": sentences},
        project_id=p_dir.name,
    )
    if fmt_profile == MICRO_SHORT_PROFILE:
        min_clips_req = MICRO_SHORT_CUT_MIN
    elif fmt_profile == SHORTS_EXPRESSIVE_V8_PROFILE:
        from pipeline.config import (
            BRAIN_SIM_ONLY_CLIP_COUNT_RANGE,
            EXPRESSIVE_V8_LEGACY_CLIP_COUNT_MIN,
            EXPRESSIVE_V8_LEGACY_INDOOR_CLIP_COUNT_RANGE,
            EXPRESSIVE_V8_R76_CLIP_COUNT_RANGE,
            is_brain_sim_only_plan,
            is_r72_open_world_v8_plan,
            is_r76_v8_plan,
        )

        if bool(visual_plan.get("allow_legacy_v8_clip_count")):
            min_clips_req = EXPRESSIVE_V8_LEGACY_CLIP_COUNT_MIN
        elif is_brain_sim_only_plan(visual_plan, script_doc):
            min_clips_req = BRAIN_SIM_ONLY_CLIP_COUNT_RANGE[0]
        elif is_r76_v8_plan(visual_plan, script_doc, project_id=p_dir.name):
            min_clips_req = EXPRESSIVE_V8_R76_CLIP_COUNT_RANGE[0]
        elif not is_r72_open_world_v8_plan(visual_plan, script_doc, project_id=p_dir.name):
            min_clips_req = min(EXPRESSIVE_V8_LEGACY_INDOOR_CLIP_COUNT_RANGE[0], EXPRESSIVE_V8_CLIP_COUNT_RANGE[0])
        else:
            min_clips_req = EXPRESSIVE_V8_CLIP_COUNT_RANGE[0]
    elif fmt_profile == SHORTS_90S_PROFILE:
        min_clips_req = SHORTS_90S_CLIP_COUNT_MIN
    else:
        min_clips_req = DIORAMA_CLIP_COUNT_MIN

    clips_dir = p_dir / "03_visuals" / "flow_native_clips"
    clip_files = _resolve_diorama_clip_files(p_dir / "03_visuals")
    if len(clip_files) < min_clips_req:
        raise RuntimeError(
            f"neuro_diorama assembly requires >= {min_clips_req} clips in {clips_dir} (found {len(clip_files)})"
        )
    if not visual_plan.get("outro_title_lines") and script_doc.get("outro_title_lines"):
        visual_plan["outro_title_lines"] = script_doc["outro_title_lines"]
    is_v8 = is_expressive_v8_plan(visual_plan, script_doc)
    is_v7 = is_v8 or is_diorama_v7_plan(visual_plan) or is_diorama_v7_plan(script_doc)
    if is_v8 and int(script_doc.get("schema") or 0) < PROMPT_SCHEMA_VERSION_V8:
        script_doc = {
            **script_doc,
            "schema": PROMPT_SCHEMA_VERSION_V8,
            "style_profile": resolve_diorama_v7_style_profile(visual_plan),
        }
    elif is_v7 and not is_v8 and int(script_doc.get("schema") or 0) < PROMPT_SCHEMA_VERSION_V7:
        script_doc = {
            **script_doc,
            "schema": PROMPT_SCHEMA_VERSION_V7,
            "style_profile": resolve_diorama_v7_style_profile(visual_plan),
        }
    eff_voice_preset = str(
        voice_preset
        or script_doc.get("voice_preset")
        or visual_plan.get("voice_preset")
        or ""
    ).strip() or None
    if eff_voice_preset:
        script_doc = {**script_doc, "voice_preset": eff_voice_preset}

    # 1. Master Voiceover Clock
    audio_dir = p_dir / "04_audio"
    if preserve_audio_master:
        existing_wav = audio_dir / "audio_master.wav"
        existing_vr = audio_dir / "voice_report.json"
        if not existing_wav.exists() or not existing_vr.exists():
            raise FileNotFoundError(
                f"preserve_audio_master=True requires existing {existing_wav} and {existing_vr}"
            )
        verify_script_audio_freshness(p_dir, context="assemble_diorama_project(preserve_audio_master=True)")
        vr = json.loads(existing_vr.read_text(encoding="utf-8"))
        preserved_pcm: np.ndarray | None = None
        preserved_sr = int(vr.get("sample_rate") or 48000)
        needs_stereo_soundscape_mix = False
        try:
            import wave as _wave_mod

            with _wave_mod.open(str(existing_wav), "rb") as _wf_chk:
                if _wf_chk.getnchannels() == 1 and _wf_chk.getsampwidth() == 2:
                    dry_backup = audio_dir / "voice_dry_mono.wav"
                    if not dry_backup.exists():
                        _atomic_copy_file(existing_wav, dry_backup)
                    preserved_sr = int(_wf_chk.getframerate() or preserved_sr)
                    raw_i16 = np.frombuffer(_wf_chk.readframes(_wf_chk.getnframes()), dtype=np.int16)
                    preserved_pcm = (raw_i16.astype(np.float32) / 32768.0).reshape(-1)
                    needs_stereo_soundscape_mix = True
        except Exception:  # noqa: BLE001
            needs_stereo_soundscape_mix = False
        tts_res = {
            "sentence_spans": vr["sentence_spans"],
            "events": vr["events"],
            "speech_end_sec": float(vr["speech_end_sec"]),
            "total_duration_sec": float(vr["total_duration_sec"]),
            "active_speech_ratio": float(vr.get("active_speech_ratio", 0.90)),
            "true_rms_voiced_ratio": vr.get("true_rms_voiced_ratio"),
            "report": vr,
            "pcm": preserved_pcm,
            "sr": preserved_sr,
            "_needs_stereo_soundscape_mix": needs_stereo_soundscape_mix,
        }
    else:
        tts_res = synthesize_continuous_diorama_track(
            project_dir=p_dir,
            sentences=sentences,
            align_whisper=align_whisper,
            pre_synthesized_lines=pre_synthesized_lines,
            script_doc=script_doc,
            rate=tts_rate,
            prosody_mode=prosody_mode,
            voice_preset=eff_voice_preset,
            cpu_budget=cpu_budget,
        )

    # 2. Cross-Cut EDL (applying explicit or prior R64 shift_window_recommendations when present)
    eff_overrides: dict[int, Any] = dict(source_window_overrides or {})
    if apply_posthoc_window_shifts and not eff_overrides:
        vp_clips = visual_plan.get("clips") if isinstance(visual_plan.get("clips"), list) else []
        authored_starts = {
            idx_1
            for idx_1, cs in enumerate(vp_clips, start=1)
            if isinstance(cs, dict) and (cs.get("src_start_sec") is not None or cs.get("source_start_sec") is not None)
        }
        prev_ph = p_dir / "05_assembly" / "posthoc_semantic_qa_report.json"
        if prev_ph.exists():
            try:
                ph_mtime_ns = prev_ph.stat().st_mtime_ns
                vp_path_chk = p_dir / "03_visuals" / "visual_plan.json"
                plan_not_newer = (not vp_path_chk.exists()) or (ph_mtime_ns >= vp_path_chk.stat().st_mtime_ns)
                ph_doc = json.loads(prev_ph.read_text(encoding="utf-8"))
                ph_src_clips = ph_doc.get("source_clips") if isinstance(ph_doc.get("source_clips"), list) else []
                clip_count_matches = (not ph_src_clips) or (len(ph_src_clips) == len(clip_files))
                if plan_not_newer and clip_count_matches:
                    def _clip_not_regenerated_since_report(cid_1: int) -> bool:
                        if not (1 <= cid_1 <= len(clip_files)):
                            return False
                        try:
                            return ph_mtime_ns >= Path(clip_files[cid_1 - 1]).stat().st_mtime_ns
                        except OSError:
                            return False

                    for rec in (ph_doc.get("summary") or {}).get("shift_window_recommendations") or []:
                        if isinstance(rec, dict) and rec.get("clip_index") and rec.get("recommended_src_window_sec"):
                            c_id = int(rec["clip_index"])
                            if c_id not in authored_starts and _clip_not_regenerated_since_report(c_id):
                                eff_overrides[c_id] = rec["recommended_src_window_sec"]
                    for crep in ph_doc.get("cuts") or []:
                        if (
                            isinstance(crep, dict)
                            and crep.get("remediation") == "shift_edl_source_window"
                            and crep.get("recommended_src_window_sec")
                        ):
                            c_id = int((crep.get("offending_clip_indices") or [crep["clip_index"]])[0])
                            if c_id not in authored_starts and _clip_not_regenerated_since_report(c_id):
                                eff_overrides.setdefault(c_id, crep["recommended_src_window_sec"])
            except Exception:  # noqa: BLE001
                pass

    asm_dir = p_dir / "05_assembly"
    asm_dir.mkdir(parents=True, exist_ok=True)
    edl_path = asm_dir / "edit_decision_list.json"

    def _build_edl_and_audio_outputs(cur_tts_res: dict[str, Any]) -> tuple[dict[str, Any], Path, Path]:
        cur_edl = build_crosscut_edl(
            visual_plan=visual_plan,
            sentence_spans=cur_tts_res["sentence_spans"],
            clip_files=clip_files,
            speech_end_sec=cur_tts_res["speech_end_sec"],
            total_duration_sec=cur_tts_res["total_duration_sec"],
            script_doc=script_doc,
            source_window_overrides=(eff_overrides or None),
        )
        if is_v7 and optimize_plaque_windows:
            cur_edl["plaque_window_refinements"] = refine_plaque_safe_source_windows(
                cur_edl,
                clip_files,
                cache_dir=_segment_cache_dir(p_dir),
            )
        cur_pros_mode = str((cur_tts_res.get("report") or {}).get("prosody_mode") or "uniform_108x")
        cur_edl["prosody_mode"] = cur_pros_mode
        cur_gap_wins = (cur_tts_res.get("report") or {}).get("gap_windows")
        if isinstance(cur_gap_wins, list) and cur_gap_wins:
            cur_edl["gap_windows"] = cur_gap_wins
        if cur_pros_mode != "uniform_108x":
            stamp_windows_local: list[list[float]] = []
            spans_by_idx_local = {int(sp["sentence_index"]): sp for sp in cur_tts_res["sentence_spans"]}
            try:
                pr_doc_local = json.loads((p_dir / "04_audio" / "prosody_report.json").read_text(encoding="utf-8"))
                for row_local in pr_doc_local.get("sentences") or []:
                    si_local = int(row_local["sentence_index"])
                    if row_local.get("gear") == "stamp" and si_local > 1 and (si_local - 1) in spans_by_idx_local and si_local in spans_by_idx_local:
                        w0 = float(spans_by_idx_local[si_local - 1]["end_sec"]) - 0.04
                        w1 = float(spans_by_idx_local[si_local]["start_sec"]) + 0.06
                        if w1 - w0 >= 0.12:
                            stamp_windows_local.append([round(w0, 3), round(w1, 3)])
            except Exception:  # noqa: BLE001
                stamp_windows_local = []
            cur_edl["prosody_stamp_windows"] = stamp_windows_local
        cur_ass = generate_diorama_ass_subtitles(
            ass_path=audio_dir / "subtitles.ass",
            events=cur_tts_res["events"],
            sentence_spans=cur_tts_res["sentence_spans"],
            visual_plan=visual_plan,
            edl=cur_edl,
        )
        if preserve_audio_master and not cur_tts_res.get("_needs_stereo_soundscape_mix"):
            cur_wav = audio_dir / "audio_master.wav"
        else:
            cur_wav = generate_diorama_audio_master(
                wav_path=audio_dir / "audio_master.wav",
                voice_pcm=cur_tts_res["pcm"],
                sr=cur_tts_res["sr"],
                speech_end_sec=cur_edl["speech_end_sec"],
                edl=cur_edl,
            )
        tmp_edl_local = edl_path.with_suffix(".json.tmp")
        tmp_edl_local.write_text(json.dumps(cur_edl, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp_edl_local, edl_path)
        return cur_edl, cur_ass, cur_wav

    edl, ass_path, wav_path = _build_edl_and_audio_outputs(tts_res)
    enforce_combined_r88a_r89_edl_contract(
        p_dir,
        edl,
        float(edl.get("total_duration_sec") or tts_res.get("total_duration_sec") or 0.0),
    )

    # 3B. Pre-Assembly 3-Second Audio & ASR Prosody Gate (Workstream 2A: catch word drops BEFORE video encode)
    pre_assembly_prosody_retried_sentences: list[int] = []
    if (not preserve_audio_master) and align_whisper and preview_sec is None:
        try:
            from pipeline import prosody as _prosody_mod

            pre_pros = _prosody_mod.evaluate_prosody_gates_on_audio(
                p_dir,
                audio_path=wav_path,
                gates=("P6_asr_by_gear",),
                run_asr=True,
            )
            p6_gate = (pre_pros.get("gates") or {}).get("P6_asr_by_gear") or {}
            low_sents = sorted(
                {int(i) for i in (p6_gate.get("low_sentences_lt_0_80") or []) if int(i) >= 1}
            )
            if (not p6_gate.get("passed", True)) or low_sents:
                retry_targets = set(low_sents) if low_sents else set(range(1, len(sentences) + 1))
                pre_assembly_prosody_retried_sentences = sorted(retry_targets)
                tts_res = synthesize_continuous_diorama_track(
                    project_dir=p_dir,
                    sentences=sentences,
                    align_whisper=align_whisper,
                    pre_synthesized_lines=None if pre_synthesized_lines is None else pre_synthesized_lines,
                    script_doc=script_doc,
                    rate=tts_rate,
                    prosody_mode=prosody_mode,
                    voice_preset=eff_voice_preset,
                    retry_intact_sentence_indices=retry_targets,
                    cpu_budget=cpu_budget,
                )
                edl, ass_path, wav_path = _build_edl_and_audio_outputs(tts_res)
                enforce_combined_r88a_r89_edl_contract(
                    p_dir,
                    edl,
                    float(edl.get("total_duration_sec") or tts_res.get("total_duration_sec") or 0.0),
                )
        except Exception:  # noqa: BLE001
            logger.warning("Pre-assembly P6 prosody retry failed for %s; retaining initial track", p_dir.name, exc_info=True)

    # 4. Single-pass stitchable ASS segment encode in local /tmp scratch + zero-reencode mux (Speed-3)
    from concurrent.futures import ThreadPoolExecutor
    from pipeline.media_cache import register_staged_copy, stage_local_file

    ff = _ffmpeg()
    fps = int(edl["fps"])
    is_v8_edl = is_v8 or is_expressive_v8_plan(visual_plan, edl)
    is_v7_edl = is_v8_edl or is_v7 or int(edl.get("schema") or 6) >= PROMPT_SCHEMA_VERSION_V7
    ceiling_frames = (
        int(round(EXPRESSIVE_V8_HARD_CEILING_SEC * fps))
        if is_v8_edl
        else (SHORTS_HARD_CEILING_FRAMES_V7 if is_v7_edl else SHORTS_HARD_CEILING_FRAMES)
    )
    total_frames = min(ceiling_frames, int(edl["total_frames"]))
    target_crf = 18 if is_v7_edl else 19
    n_workers = resolve_assembler_workers(cpu_budget)
    seg_ff_threads = resolve_ffmpeg_threads_per_worker(n_workers, cpu_budget)
    xf_workers = resolve_xfade_workers(cpu_budget)
    xf_ff_threads = resolve_ffmpeg_threads_per_worker(xf_workers, cpu_budget)
    preview_result: dict[str, Any] | None = None

    with ram_tempdir(prefix="aab_diorama_asm_") as td:
        td_path = Path(td)
        local_clips: dict[int, Path] = {}
        for idx, cf in enumerate(clip_files, start=1):
            local_clips[idx], _ = stage_local_file(cf)
        pastel_eq_by_num: dict[int, str] = {}
        is_porcelain_edl = is_porcelain_v7_plan(visual_plan, edl)
        if is_v7_edl and not (is_porcelain_edl or is_v8_edl):
            with ThreadPoolExecutor(max_workers=n_workers) as eq_pool:
                eq_vals = list(eq_pool.map(_compute_v7_pastel_eq_filter, [local_clips[i] for i in range(1, len(clip_files) + 1)]))
            pastel_eq_by_num = {i: v for i, v in enumerate(eq_vals, start=1)}

        local_ass = td_path / "subtitles.ass"
        local_wav = td_path / "audio_master.wav"
        shutil.copy2(ass_path, local_ass)
        shutil.copy2(wav_path, local_wav)

        ass_filter = f"ass={local_ass.name}"
        if is_v7_edl:
            fonts_dir = td_path / "fonts"
            fonts_dir.mkdir(parents=True, exist_ok=True)
            bundled_ttf = ensure_bundled_condensed_font()
            shutil.copy2(bundled_ttf, fonts_dir / bundled_ttf.name)
            ass_filter = f"ass={local_ass.name}:fontsdir=fonts"
            font_rep = probe_ass_font_resolution(ff, td_path, local_ass.name, fontsdir="fonts")
            (asm_dir / "font_probe.json").write_text(json.dumps(font_rep, indent=2, ensure_ascii=False), encoding="utf-8")
            if not font_rep["passed"]:
                raise RuntimeError(f"F-2 font guard: libass fell back from {DIORAMA_V7_SUBTITLE_FONT_NAME}: {font_rep['fallbacks'][:2]}")

        # Compute exact clamped per-segment frame counts & start offsets so concat `-c:v copy` equals `total_frames`
        seg_jobs: list[tuple[dict[str, Any], Path, int, float]] = []
        cum_frames = 0
        preview_frames = int(round(float(preview_sec) * fps)) if preview_sec else None
        for cut in edl["cuts"]:
            rem = total_frames - cum_frames
            if preview_frames is not None:
                rem = min(rem, preview_frames - cum_frames)
            if rem <= 0:
                break
            eff_f = min(rem, int(cut["frames"]))
            s_path = td_path / f"seg_{int(cut['cut_index']):03d}.mp4"
            seg_jobs.append((cut, s_path, eff_f, cum_frames / float(fps)))
            cum_frames += eff_f

        # Render 3 clean uncaptioned 1080x1920 preview frames (Act 1, Act 4, Act 6) into 05_assembly/
        # (`06_publish/thumbnail_var_A/B/C.png` are generated via R65 `thumbnail_studio` after final mux).
        pub_dir = p_dir / "06_publish"
        pub_dir.mkdir(parents=True, exist_ok=True)
        total_dur_eff = cum_frames / float(fps)
        thumb_targets = (
            ("A", "frame_preview_A.png", min(total_dur_eff * 0.10, 4.5)),
            ("B", "frame_preview_B.png", total_dur_eff * 0.54),
            ("C", "frame_preview_C.png", total_dur_eff * 0.84),
        )
        for var_tag, t_fname, t_sec in (thumb_targets if preview_sec is None else ()):
            if preserve_audio_master and (asm_dir / f"frame_preview_{var_tag}.png").is_file():
                continue
            chosen_job = seg_jobs[-1]
            for jb in seg_jobs:
                j_start = jb[3]
                j_end = j_start + (jb[2] / float(fps))
                if j_start <= t_sec < j_end:
                    chosen_job = jb
                    break
            j_cut, _, j_frames, j_start = chosen_job
            local_png = td_path / t_fname
            _render_cut_segment(
                ff,
                j_cut,
                local_clips,
                local_png,
                fps,
                pastel_eq_by_num=pastel_eq_by_num,
                cwd=td_path,
                single_frame_offset_sec=max(0.0, t_sec - j_start),
                override_frames=j_frames,
            )
            _atomic_copy_file(local_png, asm_dir / f"frame_preview_{var_tag}.png")

        # Group contiguous Track-V1 camera transitions (`expressive_25d_v8`) underneath crisp Track-V2 ASS subtitles
        def _source_daisy_boundary_mae(cut_a: dict[str, Any], cut_b: dict[str, Any]) -> float:
            pa = local_clips.get(int(cut_a.get("clip_index") or 0))
            pb = local_clips.get(int(cut_b.get("clip_index") or 0))
            if pa is None or pb is None or not pa.exists() or not pb.exists():
                return 99.0
            cap_a = cv2.VideoCapture(str(pa))
            cap_b = cv2.VideoCapture(str(pb))
            try:
                if not cap_a.isOpened() or not cap_b.isOpened():
                    return 99.0
                fps_a = max(1.0, float(cap_a.get(cv2.CAP_PROP_FPS) or 24.0))
                fc_a = max(1, int(cap_a.get(cv2.CAP_PROP_FRAME_COUNT) or 1))
                src_end_a = float(cut_a.get("src_end_sec") or 0.0)
                idx_a = max(0, min(fc_a - 1, int(round(src_end_a * fps_a)) - 1))
                fps_b = max(1.0, float(cap_b.get(cv2.CAP_PROP_FPS) or 24.0))
                fc_b = max(1, int(cap_b.get(cv2.CAP_PROP_FRAME_COUNT) or 1))
                src_start_b = float(cut_b.get("src_start_sec") or 0.0)
                idx_b = max(0, min(fc_b - 1, int(round(src_start_b * fps_b))))
                cap_a.set(cv2.CAP_PROP_POS_FRAMES, idx_a)
                ok_a, frm_a = cap_a.read()
                cap_b.set(cv2.CAP_PROP_POS_FRAMES, idx_b)
                ok_b, frm_b = cap_b.read()
                if not ok_a or not ok_b or frm_a is None or frm_b is None:
                    return 99.0
                ga = cv2.cvtColor(cv2.resize(frm_a, (180, 320)), cv2.COLOR_BGR2GRAY).astype(np.float32)
                gb = cv2.cvtColor(cv2.resize(frm_b, (180, 320)), cv2.COLOR_BGR2GRAY).astype(np.float32)
                return float(np.mean(np.abs(ga - gb)))
            finally:
                cap_a.release()
                cap_b.release()

        daisy_pair_mae_cache: dict[tuple[int, int], float] = {}

        def _v8_track_v1_spec(
            tr_raw: str,
            cut_a: dict[str, Any] | None = None,
            cut_b: dict[str, Any] | None = None,
        ) -> tuple[str, int]:
            tr_n = str(tr_raw or "").strip().lower()
            allow_alpha = bool((visual_plan or {}).get("allow_alpha_dissolves"))
            if tr_n == "portal_crash_zoom_10f":
                return "smoothup", int(EXPRESSIVE_V8_PORTAL_ZOOM_FRAMES)
            if tr_n == "whip_pan_blur_8f":
                return "smoothleft", int(EXPRESSIVE_V8_WHIP_PAN_FRAMES)
            if tr_n == "occlusion_wipe":
                return "smoothright", int(EXPRESSIVE_V8_WHIP_PAN_FRAMES)
            if allow_alpha:
                if tr_n == "dissolve_15f":
                    return "fade", 15
                if tr_n == "dissolve_12f":
                    return "fade", 12
                if tr_n == "dissolve_8f":
                    return "fade", int(EXPRESSIVE_V8_DISSOLVE_8_FRAMES)
                if tr_n == "dissolve_6f":
                    return "fade", int(EXPRESSIVE_V8_DISSOLVE_FRAMES)
                if tr_n == "split_screen_wipe":
                    return "fade", int(EXPRESSIVE_V8_DISSOLVE_8_FRAMES)
                if tr_n == "match_cut_bridge":
                    return "fade", int(EXPRESSIVE_V8_DISSOLVE_FRAMES)
                if tr_n == "daisy_chain_bridge":
                    if cut_a is not None and cut_b is not None:
                        pair_k = (int(cut_a.get("cut_index") or 0), int(cut_b.get("cut_index") or 0))
                        if pair_k not in daisy_pair_mae_cache:
                            daisy_pair_mae_cache[pair_k] = _source_daisy_boundary_mae(cut_a, cut_b)
                        if daisy_pair_mae_cache[pair_k] < 22.0:
                            return "", 0
                    return "fade", int(EXPRESSIVE_V8_DISSOLVE_8_FRAMES)
            return "", 0

        chains: list[list[tuple[dict[str, Any], Path, int, float]]] = []
        for idx_j, jb in enumerate(seg_jobs):
            prev_tr_name = str(seg_jobs[idx_j - 1][0].get("transition_out") or "").strip().lower() if idx_j > 0 else ""
            prev_xf, prev_ov_f = (
                _v8_track_v1_spec(prev_tr_name, seg_jobs[idx_j - 1][0], jb[0])
                if (is_v8_edl and idx_j > 0)
                else ("", 0)
            )
            prev_bridges = (
                bool(prev_xf)
                and prev_ov_f > 0
                and seg_jobs[idx_j - 1][0].get("mode") == "single"
                and jb[0].get("mode") == "single"
                and seg_jobs[idx_j - 1][2] >= prev_ov_f + 4
                and jb[2] >= prev_ov_f + 4
            )
            if prev_bridges and chains:
                chains[-1].append(jb)
            else:
                chains.append([jb])

        render_tasks: list[tuple[dict[str, Any], Path, int, str]] = []
        dissolve_groups: list[tuple[list[tuple[Path, int, str, int]], Path, float, int]] = []
        concat_names: list[str] = []
        for chain in chains:
            if len(chain) == 1:
                c_item, s_path, eff_f, start_s = chain[0]
                burn_chain = f",setpts=PTS+{start_s:.6f}/TB,{ass_filter},setpts=PTS-STARTPTS"
                render_tasks.append((c_item, s_path, eff_f, burn_chain))
                concat_names.append(s_path.name)
            else:
                grp_inputs: list[tuple[Path, int, str, int]] = []
                for k_ch, (c_item, _s_path, eff_f, _start_s) in enumerate(chain):
                    raw_p = td_path / f"raw_{int(c_item['cut_index']):03d}.mp4"
                    prev_tr_k = str(chain[k_ch - 1][0].get("transition_out") or "").strip().lower() if k_ch > 0 else ""
                    cur_tr_k = str(c_item.get("transition_out") or "").strip().lower() if k_ch < len(chain) - 1 else ""
                    xf_k, ov_f_k = (
                        _v8_track_v1_spec(cur_tr_k, c_item, chain[k_ch + 1][0])
                        if k_ch < len(chain) - 1
                        else ("", 0)
                    )
                    c_mod: dict[str, Any] = dict(c_item)
                    if prev_tr_k == "portal_crash_zoom_10f":
                        c_mod["_portal_zoom_head_frames"] = int(EXPRESSIVE_V8_PORTAL_ZOOM_FRAMES)
                    if k_ch < len(chain) - 1 and ov_f_k > 0:
                        req_raw_f = eff_f + ov_f_k + 1
                        if cur_tr_k == "portal_crash_zoom_10f":
                            c_mod["_portal_zoom_tail_start_f"] = max(1, eff_f - 3)
                        if c_mod.get("v8_curve_ramp"):
                            c_mod["curve_nominal_frames"] = req_raw_f
                        else:
                            c_mod["src_end_sec"] = round(float(c_item["src_end_sec"]) + ((ov_f_k + 1) / float(fps)), 4)
                        render_tasks.append((c_mod, raw_p, req_raw_f, ""))
                    else:
                        render_tasks.append((c_mod, raw_p, eff_f, ""))
                    grp_inputs.append((raw_p, eff_f, xf_k, ov_f_k))
                grp_out = td_path / f"grp_{int(chain[0][0]['cut_index']):03d}.mp4"
                dissolve_groups.append((grp_inputs, grp_out, chain[0][3], sum(x[1] for x in grp_inputs)))
                concat_names.append(grp_out.name)

        import hashlib
        import threading

        ass_sha1_cur = hashlib.sha1(local_ass.read_bytes()).hexdigest()
        cache_stats_lock = threading.Lock()
        cache_stats = {"hits": 0, "misses": 0}

        def _render_task(task: tuple[dict[str, Any], Path, int, str]) -> None:
            c_item, out_p, f_cnt, b_chain = task
            use_raw_cache = bool(preview_sec is None and (dissolve_groups or b_chain == ""))
            cache_p = (
                _raw_cut_cache_path(
                    p_dir,
                    c_item,
                    local_clips,
                    fps,
                    f_cnt,
                    pastel_eq_by_num,
                    ass_burn_chain=b_chain,
                    ass_sha1=ass_sha1_cur,
                )
                if use_raw_cache
                else None
            )
            if (
                cache_p is not None
                and cache_p.is_file()
                and cache_p.stat().st_size > 2048
                and _probe_segment_frame_count(cache_p) >= f_cnt
            ):
                out_p.unlink(missing_ok=True)
                try:
                    os.link(cache_p, out_p)
                except OSError:
                    shutil.copy2(cache_p, out_p)
                with cache_stats_lock:
                    cache_stats["hits"] += 1
                return
            seg_preset = "ultrafast" if b_chain == "" else "veryfast"
            seg_crf = max(13, target_crf - 4) if b_chain == "" else target_crf
            _render_cut_segment(
                ff,
                c_item,
                local_clips,
                out_p,
                fps,
                pastel_eq_by_num=pastel_eq_by_num,
                ass_burn_chain=b_chain,
                crf=seg_crf,
                preset=seg_preset,
                cwd=td_path,
                override_frames=f_cnt,
                ffmpeg_threads=seg_ff_threads,
            )
            with cache_stats_lock:
                cache_stats["misses"] += 1
            if cache_p is not None and out_p.is_file() and out_p.stat().st_size > 2048:
                try:
                    _atomic_copy_file(out_p, cache_p)
                except OSError:
                    logger.warning("Failed to persist raw cut segment cache %s", cache_p, exc_info=True)

        prev_cv_threads = cv2.getNumThreads()
        if n_workers > 1 and prev_cv_threads > 1:
            cv2.setNumThreads(1)
        try:
            with ThreadPoolExecutor(max_workers=n_workers) as pool:
                list(pool.map(_render_task, render_tasks))
        finally:
            if n_workers > 1 and prev_cv_threads > 1:
                cv2.setNumThreads(prev_cv_threads)
        raw_segment_cache_hits = int(cache_stats["hits"])
        raw_segment_cache_misses = int(cache_stats["misses"])

        xfmid_cache_dir = _segment_cache_dir(p_dir) / "xfmid_v8"
        xfmid_cache_dir.mkdir(parents=True, exist_ok=True)

        def _file_head_tail_sig(fp: Path) -> str:
            st = fp.stat()
            h = hashlib.sha1()
            h.update(f"{st.st_size}:".encode("utf-8"))
            with fp.open("rb") as fh:
                h.update(fh.read(65536))
                if st.st_size > 131072:
                    fh.seek(max(0, st.st_size - 65536))
                    h.update(fh.read(65536))
            return h.hexdigest()[:18]

        def _run_xfade_batch(
            batch_inputs: list[tuple[Path, int, str, int]],
            out_path: Path,
            burn_start_sec: float | None = None,
        ) -> None:
            is_final_stage = burn_start_sec is not None
            xf_cache_p: Path | None = None
            if not is_final_stage:
                tail_ov_f = int(batch_inputs[-1][3])
                total_out_f = sum(int(x[1]) for x in batch_inputs) + (tail_ov_f + 1 if tail_ov_f > 0 else 0)
                enc_crf = str(max(13, int(target_crf) - 3))
                xf_key = hashlib.sha1(
                    json.dumps(
                        [
                            [_file_head_tail_sig(rp), int(ef), str(xk), int(of)]
                            for rp, ef, xk, of in batch_inputs
                        ]
                        + [int(fps), enc_crf, int(total_out_f)],
                        separators=(",", ":"),
                    ).encode("utf-8")
                ).hexdigest()[:24]
                xf_cache_p = xfmid_cache_dir / f"{xf_key}.mp4"
                if (
                    xf_cache_p.is_file()
                    and xf_cache_p.stat().st_size > 2048
                    and _probe_segment_frame_count(xf_cache_p) >= total_out_f
                ):
                    try:
                        os.link(xf_cache_p, out_path)
                    except OSError:
                        shutil.copy2(xf_cache_p, out_path)
                    return
            _execute_xfade_batch_ffmpeg(
                ff=ff,
                batch_inputs=batch_inputs,
                out_path=out_path,
                fps=fps,
                target_crf=int(target_crf),
                ass_filter=ass_filter,
                burn_start_sec=burn_start_sec,
                cwd=td_path,
                ffmpeg_threads=(resolve_ffmpeg_threads_per_worker(1, cpu_budget) if is_final_stage else xf_ff_threads),
            )
            if xf_cache_p is not None and out_path.is_file() and out_path.stat().st_size > 2048:
                try:
                    _atomic_copy_file(out_path, xf_cache_p)
                except OSError:
                    logger.warning("Failed to persist xfmid segment cache %s", xf_cache_p, exc_info=True)

        for grp_idx, (grp_inputs, grp_out, grp_start_s, _grp_total_f) in enumerate(dissolve_groups):
            cur_stage = list(grp_inputs)
            stage_round = 0
            while len(cur_stage) > 4:
                chunks = [cur_stage[i : i + 4] for i in range(0, len(cur_stage), 4)]
                next_stage: list[tuple[Path, int, str, int]] = []
                sub_jobs: list[tuple[list[tuple[Path, int, str, int]], Path]] = []
                for ch_idx, chunk in enumerate(chunks):
                    if len(chunk) == 1:
                        next_stage.append(chunk[0])
                    else:
                        mid_p = td_path / f"xfmid_g{grp_idx}_r{stage_round}_{ch_idx}.mp4"
                        sub_jobs.append((chunk, mid_p))
                        next_stage.append(
                            (mid_p, sum(int(x[1]) for x in chunk), chunk[-1][2], int(chunk[-1][3]))
                        )
                if sub_jobs:
                    with ThreadPoolExecutor(max_workers=min(xf_workers, len(sub_jobs))) as xf_pool:
                        list(xf_pool.map(lambda jb: _run_xfade_batch(jb[0], jb[1], None), sub_jobs))
                cur_stage = next_stage
                stage_round += 1
            _run_xfade_batch(cur_stage, grp_out, burn_start_sec=grp_start_s)

        concat_txt = td_path / "concat.txt"
        concat_txt.write_text("\n".join(f"file '{nm}'" for nm in concat_names) + "\n", encoding="utf-8")

        active_stamps = [
            ds
            for ds in (edl.get("resolved_data_stamps") or [])
            if isinstance(ds, dict)
            and (preview_sec is None or float(ds.get("start_sec") or 0.0) < float(preview_sec) - 0.5)
        ]
        active_anatomy_callouts = [
            ac
            for ac in (edl.get("resolved_anatomy_callouts") or [])
            if isinstance(ac, dict)
            and (preview_sec is None or float(ac.get("start_sec") or 0.0) < float(preview_sec) - 0.5)
        ]
        if active_stamps or active_anatomy_callouts:
            pre_ov_mp4 = td_path / "pre_overlay_concat.mp4"
            res_pre_ov = subprocess.run(
                [
                    ff,
                    "-nostdin",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-y",
                    "-f",
                    "concat",
                    "-safe",
                    "0",
                    "-i",
                    str(concat_txt.name),
                    "-c:v",
                    "copy",
                    str(pre_ov_mp4.name),
                ],
                cwd=str(td_path),
                capture_output=True,
                text=True,
                check=False,
                timeout=180,
                stdin=subprocess.DEVNULL,
            )
            if res_pre_ov.returncode != 0 or not pre_ov_mp4.is_file():
                raise RuntimeError(f"Pre-overlay concat failed: {(res_pre_ov.stderr or '')[:300]}")
            cur_ov_mp4 = pre_ov_mp4
            if active_stamps:
                from pipeline.data_stamp_overlay import composite_data_stamps_on_video

                stamped_mp4 = td_path / "stamped_video_stream.mp4"
                composite_data_stamps_on_video(
                    cur_ov_mp4,
                    stamped_mp4,
                    active_stamps,
                    fps=fps,
                    width=VIDEO_WIDTH,
                    height=VIDEO_HEIGHT,
                )
                cur_ov_mp4 = stamped_mp4
            if active_anatomy_callouts:
                from pipeline.anatomy_label_overlay import composite_anatomy_labels_on_video

                anat_mp4 = td_path / "anatomy_labeled_video_stream.mp4"
                composite_anatomy_labels_on_video(
                    cur_ov_mp4,
                    anat_mp4,
                    active_anatomy_callouts,
                    fps=fps,
                    width=VIDEO_WIDTH,
                    height=VIDEO_HEIGHT,
                )
                cur_ov_mp4 = anat_mp4
            concat_txt.write_text(f"file '{cur_ov_mp4.name}'\n", encoding="utf-8")

        local_final = td_path / "final_shorts_1080x1920.mp4"
        audio_ch = str(DIORAMA_V7_AUDIO_CHANNELS) if is_v7_edl else "1"
        lim_ceil = "0.812" if is_v7_edl else "0.776"
        # v7: 4x-oversampled (192 kHz) limiter so intersample peaks are caught before AAC; loudness untouched
        lim_chain = (DIORAMA_MUX_TRUE_PEAK_LIMITER if is_v7_edl
                     else f"alimiter=limit={lim_ceil}:attack=5:release=50:level=disabled")
        mux_ceil_sec = EXPRESSIVE_V8_HARD_CEILING_SEC if is_v8_edl else SHORTS_HARD_CEILING_SEC
        exact_dur = min(mux_ceil_sec, cum_frames / float(fps))

        def _run_final_mux(trim_db: float) -> subprocess.CompletedProcess:
            vol = f"volume={trim_db:.2f}dB," if trim_db < 0 else ""
            return subprocess.run(
                [
                    ff, "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
                    "-f", "concat", "-safe", "0", "-i", str(concat_txt.name),
                    "-i", str(local_wav.name),
                    "-map", "0:v:0", "-map", "1:a:0",
                    "-c:v", "copy",
                    "-af", f"atrim=0:{exact_dur:.6f},asetpts=PTS-STARTPTS,{vol}{lim_chain}",
                    "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", audio_ch,
                    "-movflags", "+faststart",
                    str(local_final.name),
                ],
                cwd=str(td_path), capture_output=True, text=True, check=False, timeout=300, stdin=subprocess.DEVNULL,
            )

        mux_trim_cache_p = _segment_cache_dir(p_dir) / "mux_trim_cache.json"
        wav_trim_key = f"{_file_head_tail_sig(local_wav)}|{exact_dur:.3f}" if dissolve_groups or is_v7_edl else ""
        mux_trim_cache: dict[str, float] = {}
        if mux_trim_cache_p.is_file():
            try:
                mux_trim_cache = json.loads(mux_trim_cache_p.read_text(encoding="utf-8"))
            except Exception:  # noqa: BLE001
                mux_trim_cache = {}
        mux_trim_db = float(mux_trim_cache.get(wav_trim_key, 0.0)) if wav_trim_key else 0.0
        res_mux = _run_final_mux(mux_trim_db)
        # AAC true-peak guard: the sample-peak limiter cannot see AAC intersample overshoot (up to ~1.4 dB on
        # restored-HF consonant transients). Re-encode with a static trim until the encoded file sits under target.
        for _ in range(3):
            if res_mux.returncode != 0 or not local_final.exists():
                break
            tp_enc = _measure_true_peak_dbtp(local_final)
            if tp_enc is None or tp_enc <= DIORAMA_MUX_TRUE_PEAK_TARGET_DBTP:
                break
            mux_trim_db -= (tp_enc - DIORAMA_MUX_TRUE_PEAK_TARGET_DBTP) + 0.1
            res_mux = _run_final_mux(mux_trim_db)
        if wav_trim_key and res_mux.returncode == 0:
            try:
                mux_trim_cache[wav_trim_key] = round(mux_trim_db, 4)
                mux_trim_cache_p.write_text(json.dumps(mux_trim_cache, indent=2), encoding="utf-8")
            except OSError:
                pass
        if res_mux.returncode != 0 or not local_final.exists():
            raise RuntimeError(f"FFmpeg final mux failed: {res_mux.stderr[:300]}")
        if preview_sec is not None:
            prev_mp4 = asm_dir / f"preview_0-{int(round(float(preview_sec)))}s.mp4"
            _atomic_copy_file(local_final, prev_mp4, suffix=".mp4.tmp")
            preview_result = {
                "project_dir": str(p_dir),
                "preview_mp4": str(prev_mp4),
                "preview_sec": round(cum_frames / float(fps), 3),
                "prosody_mode": edl.get("prosody_mode"),
                "plaque_window_refinements": edl.get("plaque_window_refinements"),
                "rebuilt": True,
            }
        else:
            if not dissolve_groups:
                _store_segment_cache(p_dir, seg_jobs, edl, ass_path)
            _atomic_copy_file(local_final, final_mp4, suffix=".mp4.tmp")
            register_staged_copy(local_final, final_mp4)
            from pipeline import thumbnail_studio

            thumbnail_studio.run(
                p_dir,
                force=bool(force_rebuild and not preserve_audio_master),
                strict=False,
                local_clips=local_clips,
                pastel_eq_by_num=pastel_eq_by_num,
            )

    if preview_result is not None:
        enforce_ram_scratch_budget()
        return preview_result

    if fmt_profile in (MICRO_SHORT_PROFILE, SHORTS_90S_PROFILE, SHORTS_EXPRESSIVE_V8_PROFILE):
        probe_min_dur, probe_max_dur = shorts_duration_range_for_profile(
            fmt_profile,
            project_id=p_dir.name,
            plan=visual_plan,
            script_doc=script_doc,
        )
    else:
        probe_min_dur = DIORAMA_V7_DURATION_MIN_SEC if is_v7_edl else None
        probe_max_dur = None
    probe_report = MediaIntegrityValidator.validate_video_asset(
        final_mp4,
        asset_type="final_shorts",
        strict=True,
        min_duration_sec=probe_min_dur,
        max_duration_sec=probe_max_dur,
    )
    tmp_probe = asm_dir / "probe_report.json.tmp"
    tmp_probe.write_text(json.dumps(probe_report, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp_probe, asm_dir / "probe_report.json")
    manifest_path = p_dir / "00_project_manifest.json"
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["status"] = "ASSEMBLED"
            manifest["clip_count"] = len(clip_files)
            manifest["cut_count"] = edl["cut_count"]
            manifest["max_clip_reuse"] = edl.get("max_clip_reuse", 1)
            manifest["duration_sec"] = edl["total_duration_sec"]
            manifest["final_mp4"] = str(final_mp4)
            if (tts_res.get("report") or {}).get("voice_preset"):
                manifest["voice_preset"] = tts_res["report"]["voice_preset"]
            manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass

    posthoc_summary = None
    if run_posthoc_qa:
        from pipeline.posthoc_semantic_qa import run_posthoc_semantic_qa

        ph_rep = run_posthoc_semantic_qa(
            p_dir,
            render_strips=True,
            run_asr_sync=align_whisper,
            save_report=True,
            sync_knowledge_base=False,
        )
        posthoc_summary = {
            "passed": ph_rep["passed"],
            "cv_passed": ph_rep.get("cv_passed", False),
            "mean_clarity_score": ph_rep["summary"]["mean_clarity_score"],
            "weak_cut_indices": ph_rep["summary"]["weak_cut_indices"],
            "viewer_sheets": ph_rep.get("viewer_sheets") or [],
            "semantic_review": ph_rep.get("semantic_review") or {},
        }

    if manifest_path.exists():
        from pipeline.storage import ProjectStorage

        ProjectStorage.sync_existing_manifest_from_disk(p_dir, status="ASSEMBLED")

    out_payload = {
        "project_dir": str(p_dir),
        "final_mp4": str(final_mp4),
        "edl_path": str(edl_path),
        "ass_path": str(ass_path),
        "wav_path": str(wav_path),
        "duration_sec": edl["total_duration_sec"],
        "cut_count": edl["cut_count"],
        "cut_duration_cv": edl.get("cut_duration_cv"),
        "max_clip_reuse": edl.get("max_clip_reuse", 1),
        "avg_cut_duration_sec": edl["avg_cut_duration_sec"],
        "active_speech_ratio": tts_res["active_speech_ratio"],
        "true_rms_voiced_ratio": tts_res.get("true_rms_voiced_ratio"),
        "voice_preset": (tts_res.get("report") or {}).get("voice_preset"),
        "raw_segment_cache_hits": raw_segment_cache_hits,
        "raw_segment_cache_misses": raw_segment_cache_misses,
        "pre_assembly_prosody_retried_sentences": pre_assembly_prosody_retried_sentences,
        "rebuilt": True,
    }
    if posthoc_summary is not None:
        out_payload["posthoc_qa"] = posthoc_summary
    enforce_ram_scratch_budget()
    return out_payload


def compute_locked_edl_cut_frame_requirements(
    project_id_or_dir: str | Path,
    tts_res: dict[str, Any] | None = None,
    *,
    safety_pad_frames: int = 6,
) -> dict[str, Any]:
    """
    Guard 4 Virtual Master EDL Frame-Requirement Calculator:
      - Computes exact `30fps` (or plan-native FPS) EDL cut durations and Track-V1 transition overlaps
        from `visual_plan.json` + locked TTS timings (`tts_res` or `04_audio/voice_report.json`) even BEFORE
        `03_visuals/flow_native_clips` or `03_visuals/brain_simulator_clips` exist on disk (`0` MP4 files).
      - Returns `{"fps", "total_frames", "total_duration_sec", "edl_frame_map", "cuts"}` where each 1-based
        `clip_index` maps to `req_n_frames = eff_f + ov_f_next + int(safety_pad_frames)` (`max` across cuts).
    """
    from pipeline.config import (
        EXPRESSIVE_V8_DISSOLVE_8_FRAMES,
        EXPRESSIVE_V8_DISSOLVE_FRAMES,
        EXPRESSIVE_V8_PORTAL_ZOOM_FRAMES,
        EXPRESSIVE_V8_WHIP_PAN_FRAMES,
        PROMPT_SCHEMA_VERSION_V8,
    )

    p_dir = Path(project_id_or_dir) if Path(str(project_id_or_dir)).exists() else (PROJECTS_DIR / str(project_id_or_dir))
    vp_path = next(
        (
            p
            for p in (
                p_dir / "03_visuals" / "visual_plan.json",
                p_dir / "02_script" / "visual_plan.json",
                p_dir / "visual_plan.json",
            )
            if p.exists()
        ),
        None,
    )
    if vp_path is None:
        raise FileNotFoundError(f"visual_plan.json not found in {p_dir}")
    visual_plan = json.loads(vp_path.read_text(encoding="utf-8"))
    if isinstance(visual_plan, dict):
        visual_plan = {**visual_plan, "_visuals_dir": str(p_dir / "03_visuals")}

    try:
        _sents, script_doc = load_diorama_script_sentences(p_dir)
    except (FileNotFoundError, ValueError):
        raw_sc_path = next((p for p in (p_dir / "02_script" / "script.json", p_dir / "script.json") if p.exists()), None)
        script_doc = json.loads(raw_sc_path.read_text(encoding="utf-8")) if raw_sc_path else {}

    is_v8 = is_expressive_v8_plan(visual_plan, script_doc)
    is_v7 = is_v8 or is_diorama_v7_plan(visual_plan) or is_diorama_v7_plan(script_doc)
    if is_v8 and int(script_doc.get("schema") or 0) < PROMPT_SCHEMA_VERSION_V8:
        script_doc = {
            **script_doc,
            "schema": PROMPT_SCHEMA_VERSION_V8,
            "style_profile": resolve_diorama_v7_style_profile(visual_plan),
        }
    elif is_v7 and not is_v8 and int(script_doc.get("schema") or 0) < PROMPT_SCHEMA_VERSION_V7:
        script_doc = {
            **script_doc,
            "schema": PROMPT_SCHEMA_VERSION_V7,
            "style_profile": resolve_diorama_v7_style_profile(visual_plan),
        }

    if tts_res is None:
        vr_path = p_dir / "04_audio" / "voice_report.json"
        if not vr_path.exists():
            raise FileNotFoundError(f"voice_report.json not found in {p_dir / '04_audio'}")
        vr = json.loads(vr_path.read_text(encoding="utf-8"))
        wav_p = p_dir / "04_audio" / "audio_master.wav"
        tot_dur = float(vr.get("total_duration_sec") or 0.0)
        if tot_dur <= 0.0 and wav_p.is_file():
            tot_dur = float(_clip_duration(wav_p))
        sentence_spans = list(vr["sentence_spans"])
        speech_end_sec = float(vr["speech_end_sec"])
        total_duration_sec = tot_dur
    else:
        sentence_spans = list(tts_res["sentence_spans"])
        speech_end_sec = float(tts_res["speech_end_sec"])
        total_duration_sec = float(tts_res["total_duration_sec"])

    disk_clips = _resolve_diorama_clip_files(p_dir / "03_visuals")
    disk_by_num: dict[int, Path] = {}
    for cf in disk_clips:
        m_num = re.search(r"(\d+)", cf.stem)
        if m_num:
            disk_by_num[int(m_num.group(1))] = cf

    plan_clips = visual_plan.get("clips") if isinstance(visual_plan.get("clips"), list) else []
    n_target = max(len(plan_clips), max(disk_by_num.keys(), default=0))
    if n_target <= 0:
        raise ValueError(f"visual_plan.json in {p_dir} defines 0 clips")

    clip_files: list[Path] = []
    for idx_1 in range(1, n_target + 1):
        if idx_1 in disk_by_num:
            clip_files.append(disk_by_num[idx_1])
        else:
            spec_c = plan_clips[idx_1 - 1] if (idx_1 - 1 < len(plan_clips) and isinstance(plan_clips[idx_1 - 1], dict)) else {}
            is_sim_clip = (
                str(spec_c.get("grammar") or "").strip() == "brain_simulator_3d"
                or str(spec_c.get("render_engine") or "").strip().lower() == "blender_3d_simulator"
            )
            sub_d = "brain_simulator_clips" if is_sim_clip else "flow_native_clips"
            clip_files.append(p_dir / "03_visuals" / sub_d / f"clip_{idx_1:02d}.mp4")

    edl = build_crosscut_edl(
        visual_plan=visual_plan,
        sentence_spans=sentence_spans,
        clip_files=clip_files,
        speech_end_sec=speech_end_sec,
        total_duration_sec=total_duration_sec,
        script_doc=script_doc,
        virtual_clip_duration_sec=8.0,
    )

    fps = int(edl["fps"])
    is_v8_edl = is_v8 or is_expressive_v8_plan(visual_plan, edl)
    is_v7_edl = is_v8_edl or is_v7 or int(edl.get("schema") or 6) >= PROMPT_SCHEMA_VERSION_V7
    ceiling_frames = (
        int(round(EXPRESSIVE_V8_HARD_CEILING_SEC * fps))
        if is_v8_edl
        else (SHORTS_HARD_CEILING_FRAMES_V7 if is_v7_edl else SHORTS_HARD_CEILING_FRAMES)
    )
    total_frames = min(ceiling_frames, int(edl["total_frames"]))
    allow_alpha = bool((visual_plan or {}).get("allow_alpha_dissolves"))

    def _transition_overlap_frames(tr_raw: str) -> int:
        tr_n = str(tr_raw or "").strip().lower()
        if tr_n == "portal_crash_zoom_10f":
            return int(EXPRESSIVE_V8_PORTAL_ZOOM_FRAMES)
        if tr_n in ("whip_pan_blur_8f", "occlusion_wipe"):
            return int(EXPRESSIVE_V8_WHIP_PAN_FRAMES)
        if allow_alpha:
            if tr_n == "dissolve_15f":
                return 15
            if tr_n == "dissolve_12f":
                return 12
            if tr_n in ("dissolve_8f", "split_screen_wipe", "daisy_chain_bridge"):
                return int(EXPRESSIVE_V8_DISSOLVE_8_FRAMES)
            if tr_n in ("dissolve_6f", "match_cut_bridge"):
                return int(EXPRESSIVE_V8_DISSOLVE_FRAMES)
        return 0

    clamped_cuts: list[tuple[dict[str, Any], int]] = []
    cum_f = 0
    for cut in edl["cuts"]:
        rem = total_frames - cum_f
        if rem <= 0:
            break
        eff_f = min(rem, int(cut["frames"]))
        clamped_cuts.append((cut, eff_f))
        cum_f += eff_f

    pad_f = max(0, int(safety_pad_frames))
    edl_frame_map: dict[int, int] = {}
    for idx_c, (cut_cur, eff_f) in enumerate(clamped_cuts):
        ov_f_next = 0
        if is_v8_edl and idx_c < len(clamped_cuts) - 1:
            cut_nxt, eff_f_nxt = clamped_cuts[idx_c + 1]
            cand_ov = _transition_overlap_frames(str(cut_cur.get("transition_out") or ""))
            if (
                cand_ov > 0
                and cut_cur.get("mode") == "single"
                and cut_nxt.get("mode") == "single"
                and eff_f >= cand_ov + 4
                and eff_f_nxt >= cand_ov + 4
            ):
                ov_f_next = cand_ov
        req_n_frames = int(eff_f) + int(ov_f_next) + pad_f
        c_idx = int(cut_cur["clip_index"])
        edl_frame_map[c_idx] = max(edl_frame_map.get(c_idx, 0), req_n_frames)
        if cut_cur.get("secondary_clip_index") is not None:
            sec_idx = int(cut_cur["secondary_clip_index"])
            edl_frame_map[sec_idx] = max(edl_frame_map.get(sec_idx, 0), req_n_frames)

    total_dur = round(cum_f / float(fps), 3) if cum_f > 0 else round(total_frames / float(fps), 3)
    return {
        "fps": int(fps),
        "total_frames": int(cum_f if cum_f > 0 else total_frames),
        "total_duration_sec": float(total_dur),
        "edl_frame_map": dict(sorted(edl_frame_map.items())),
        "cuts": edl["cuts"],
    }


def lock_audio_durations_onto_visual_plan(
    visual_plan: dict[str, Any],
    sentence_spans: list[tuple[float, float]],
    *,
    enable_extended_durations: bool | None = None,
) -> dict[str, Any]:
    """
    Audio-Before-Flow (`M3`):
      1. Computes exact spoken duration `[t0, t1]` for each clip's `sentence_index .. end_sentence_index`.
      2. Snaps `render_sec` to `FLOW_OMNI_EXTENDED_DURATION_CHOICES` (`3..15s`) when `enable_extended_durations`
         is True (`max(3, min(15, ceil(spoken_dur + 0.6)))`), or `8s` otherwise.
      3. Marks `forbid_slowmo_stretch = True` (`0%` slow-motion stretch) when `render_sec >= spoken_dur`.
    """
    from pipeline.config import (
        DIORAMA_CLIP_RENDER_SEC,
        EXPRESSIVE_V8_FORBID_SLOWMO_STRETCH,
        FLOW_OMNI_ENABLE_EXTENDED_DURATIONS,
        FLOW_OMNI_EXTENDED_DURATION_CHOICES,
    )

    ext_ok = FLOW_OMNI_ENABLE_EXTENDED_DURATIONS if enable_extended_durations is None else bool(enable_extended_durations)
    out_plan = dict(visual_plan)
    out_clips: list[dict[str, Any]] = []
    n_sents = len(sentence_spans)
    for idx, c in enumerate(visual_plan.get("clips") or [], start=1):
        if not isinstance(c, dict):
            continue
        spec = dict(c)
        s0_i = int(spec.get("sentence_index") or min(idx, max(1, n_sents)))
        s1_i = int(spec.get("end_sentence_index") or s0_i)
        s0_clamped = max(1, min(n_sents, s0_i))
        s1_clamped = max(s0_clamped, min(n_sents, s1_i))
        if n_sents > 0:
            t_start = float(sentence_spans[s0_clamped - 1][0])
            t_end = float(sentence_spans[s1_clamped - 1][1])
            spoken_dur = max(0.35, t_end - t_start)
        else:
            spoken_dur = 3.5
        if ext_ok:
            needed = int(math.ceil(spoken_dur + 0.6))
            snapped = min(
                FLOW_OMNI_EXTENDED_DURATION_CHOICES,
                key=lambda d: (0 if d >= needed else 1, abs(d - needed)),
            )
            spec["render_sec"] = int(snapped)
        else:
            spec["render_sec"] = int(spec.get("render_sec") or DIORAMA_CLIP_RENDER_SEC)
        spec["locked_spoken_duration_sec"] = round(spoken_dur, 3)
        spec["forbid_slowmo_stretch"] = bool(
            EXPRESSIVE_V8_FORBID_SLOWMO_STRETCH and float(spec["render_sec"]) >= spoken_dur
        )
        out_clips.append(spec)
    out_plan["clips"] = out_clips
    out_plan["audio_before_flow_locked"] = True
    return out_plan


_KEYWORD_BEAT_SPLIT_RE = re.compile(
    r"(?:,\s+|\s+(?:—|--|-)\s+|\s+(?=(?:but|yet|while|until|because|forcing|driving|triggering|revealing|cutting|dropping|spiking)\b))",
    flags=re.IGNORECASE,
)


def split_sentences_at_keyword_beats(
    sentence_spans: list[tuple[float, float]],
    sentences: list[str],
    *,
    target_beat_sec: float | None = None,
) -> list[dict[str, Any]]:
    """
    Sub-Sentence Keyword Impact Cutter (`M6` / `R58-K`):
    Splits any spoken sentence span longer than `target_beat_sec * 1.45` at natural clause/keyword pivots
    so visual cuts land every `~2.0s` (`1.6–2.4s`) on spoken action verbs, numbers, or contrast pivots.
    """
    from pipeline.config import EXPRESSIVE_V8_KEYWORD_BEAT_TARGET_SEC

    beat_target = float(target_beat_sec or EXPRESSIVE_V8_KEYWORD_BEAT_TARGET_SEC)
    beats: list[dict[str, Any]] = []
    for s_idx, ((t0, t1), text) in enumerate(zip(sentence_spans, sentences), start=1):
        dur = max(0.20, float(t1) - float(t0))
        clean_txt = str(text or "").strip()
        if dur <= beat_target * 1.45:
            beats.append(
                {
                    "sentence_index": s_idx,
                    "sub_beat_index": 1,
                    "start_sec": round(float(t0), 4),
                    "end_sec": round(float(t1), 4),
                    "duration_sec": round(dur, 4),
                    "text": clean_txt,
                }
            )
            continue
        raw_clauses = [p.strip() for p in _KEYWORD_BEAT_SPLIT_RE.split(clean_txt) if p and p.strip()]
        n_target = max(2, int(round(dur / max(1.2, beat_target))))
        if len(raw_clauses) < 2:
            words = clean_txt.split()
            chunk_sz = max(2, int(math.ceil(len(words) / float(n_target))))
            raw_clauses = [" ".join(words[i : i + chunk_sz]) for i in range(0, len(words), chunk_sz)]
        elif len(raw_clauses) > n_target:
            merged: list[str] = []
            for cl in raw_clauses:
                if merged and len(merged[-1].split()) < 4:
                    merged[-1] = f"{merged[-1]}, {cl}"
                else:
                    merged.append(cl)
            raw_clauses = merged
        word_counts = [max(1, len(c.split())) for c in raw_clauses]
        total_w = float(sum(word_counts))
        cur_t = float(t0)
        for b_i, (cl_txt, wc) in enumerate(zip(raw_clauses, word_counts), start=1):
            b_dur = (float(t1) - cur_t) if b_i == len(raw_clauses) else dur * (wc / total_w)
            nxt_t = cur_t + max(0.20, b_dur)
            beats.append(
                {
                    "sentence_index": s_idx,
                    "sub_beat_index": b_i,
                    "start_sec": round(cur_t, 4),
                    "end_sec": round(nxt_t, 4),
                    "duration_sec": round(nxt_t - cur_t, 4),
                    "text": cl_txt,
                }
            )
            cur_t = nxt_t
    return beats


def build_dual_harvest_edl_windows(clip_dur_sec: float = 8.0) -> tuple[tuple[float, float], tuple[float, float]]:
    """
    Returns non-overlapping early (`A₁`) and late (`A₂`) NLE harvest windows inside a single 8s source clip (`M6`),
    allowing `A₁ -> B -> A₂` cross-cutting without frame reuse.
    """
    from pipeline.config import EXPRESSIVE_V8_DUAL_HARVEST_WINDOWS_SEC

    (a0, a1), (b0, b1) = EXPRESSIVE_V8_DUAL_HARVEST_WINDOWS_SEC
    safe_eof = max(2.5, float(clip_dur_sec) - 0.15)
    w1 = (round(min(a0, safe_eof - 0.5), 3), round(min(a1, safe_eof - 0.25), 3))
    w2_start = max(w1[1] + 0.60, min(b0, safe_eof - 1.20))
    w2_end = max(w2_start + 0.50, min(b1, safe_eof))
    return w1, (round(w2_start, 3), round(w2_end, 3))


def verify_state_swap_hist_corr(frame_a_bgr: np.ndarray, frame_b_bgr: np.ndarray) -> dict[str, Any]:
    """
    Verifies background color/lighting continuity (`hist_corr >= EXPRESSIVE_V8_STATE_SWAP_MIN_HIST_CORR` = `0.90`)
    across a `T2` Same-Framing State-Swap Jump Cut (`M8`).
    """
    from pipeline.config import EXPRESSIVE_V8_STATE_SWAP_MIN_HIST_CORR

    if frame_a_bgr is None or frame_b_bgr is None or frame_a_bgr.size == 0 or frame_b_bgr.size == 0:
        return {"passed": False, "hist_corr": 0.0, "threshold": EXPRESSIVE_V8_STATE_SWAP_MIN_HIST_CORR}
    hsv_a = cv2.cvtColor(frame_a_bgr, cv2.COLOR_BGR2HSV)
    hsv_b = cv2.cvtColor(frame_b_bgr, cv2.COLOR_BGR2HSV)
    hist_a = cv2.calcHist([hsv_a], [0, 1], None, [24, 24], [0, 180, 0, 256])
    hist_b = cv2.calcHist([hsv_b], [0, 1], None, [24, 24], [0, 180, 0, 256])
    cv2.normalize(hist_a, hist_a, 0, 1, cv2.NORM_MINMAX)
    cv2.normalize(hist_b, hist_b, 0, 1, cv2.NORM_MINMAX)
    corr = float(cv2.compareHist(hist_a, hist_b, cv2.HISTCMP_CORREL))
    return {
        "passed": corr >= float(EXPRESSIVE_V8_STATE_SWAP_MIN_HIST_CORR),
        "hist_corr": round(corr, 4),
        "threshold": float(EXPRESSIVE_V8_STATE_SWAP_MIN_HIST_CORR),
    }


def resolve_spatial_metric_stamps(
    script_doc: dict[str, Any] | None,
    sentence_spans: list[tuple[float, float]],
) -> list[dict[str, Any]]:
    """
    Resolves up to 3 post-composite 3D-tracked diegetic metric stamps (`M9`, e.g., `15 MIN`, `4X LONGER`, `88%`)
    aligned to their spoken `sentence_index` window without injecting AI text into Google Flow.
    """
    raw_stamps = (script_doc or {}).get("spatial_metric_stamps") or []
    resolved: list[dict[str, Any]] = []
    n_sents = len(sentence_spans)
    for item in raw_stamps[:3]:
        if not isinstance(item, dict):
            continue
        label = str(item.get("label") or item.get("text") or "").strip().upper()
        if not label:
            continue
        s_idx = int(item.get("sentence_index") or 1)
        if 1 <= s_idx <= n_sents:
            t0, t1 = sentence_spans[s_idx - 1]
        else:
            t0, t1 = float(item.get("start_sec") or 0.0), float(item.get("end_sec") or 2.0)
        resolved.append(
            {
                "label": label[:18],
                "sentence_index": s_idx,
                "start_sec": round(float(t0), 3),
                "end_sec": round(float(t1), 3),
                "anchor_xy_norm": tuple(item.get("anchor_xy_norm") or (0.50, 0.26)),
            }
        )
    return resolved


assemble_diorama_episode = assemble_diorama_project

__all__ = [
    "assemble_diorama_episode",
    "assemble_diorama_project",
    "build_crosscut_edl",
    "build_dual_harvest_edl_windows",
    "build_one_to_one_edl",
    "build_v7_dynamic_edl",
    "compute_locked_edl_cut_frame_requirements",
    "ensure_bundled_condensed_font",
    "generate_diorama_ass_subtitles",
    "generate_diorama_audio_master",
    "load_diorama_script_sentences",
    "lock_audio_durations_onto_visual_plan",
    "resolve_spatial_metric_stamps",
    "split_sentences_at_keyword_beats",
    "verify_state_swap_hist_corr",
]
