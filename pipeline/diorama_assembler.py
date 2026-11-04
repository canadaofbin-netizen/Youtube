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

import json
import math
import os
import re
import shutil
import subprocess
import tempfile
import time
import wave
from pathlib import Path
from typing import Any

import cv2
import numpy as np

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
    SHORTS_HARD_CEILING_FRAMES,
    SHORTS_HARD_CEILING_FRAMES_V7,
    SHORTS_HARD_CEILING_SEC,
    SUBTITLE_FONT_NAME,
    VIDEO_FPS,
    VIDEO_HEIGHT,
    VIDEO_WIDTH,
    is_diorama_v7_plan,
    is_porcelain_v7_plan,
    resolve_diorama_v7_style_profile,
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
    clip_durs = [max(4.0, float(_clip_duration(Path(cf)))) for cf in clip_files]
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
    """Resolves Schema v7 camera_move identically to build_diorama_v7_prompts."""
    explicit_cam = str(spec.get("camera") or spec.get("camera_move") or "").strip().lower()
    if explicit_cam in DIORAMA_V7_CAMERA_MOVES:
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
) -> tuple[float, float]:
    """
    Selects `[src_start_sec, src_span_sec]` inside an 8.0s native Flow clip:
      - Honors explicit `override_src_start_sec` (e.g. from R64 `shift_window_recommendations`)
        or authored `spec["src_start_sec"]`.
      - On real video clips with `>= 0.90s` slack, samples sequential low-res grayscale frames and
        scores candidate windows by combining physical motion (`raw_mad`) with upper-center
        `[22%..56%]` focal-zone Canny edge occupancy so `tilt_down` / `pan_*` reveals never slice
        empty-wall pre-roll before the primary subject enters frame.
    """
    spec_d = spec if isinstance(spec, dict) else {}
    max_usable_end = max(0.62, float(clip_dur) - 0.08)
    default_s = 0.12
    default_avail = max(0.50, max_usable_end - default_s)
    target_src_span = float(out_dur) * float(DIORAMA_V7_VISUAL_PLAYBACK_SPEED)
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
            latest_s = max(0.08, max_usable_end - default_span)
            chosen_s = max(0.08, min(latest_s, exp_s))
            avail = max(0.50, max_usable_end - chosen_s)
            return round(chosen_s, 4), round(target_src_span if avail >= target_src_span else avail, 4)
        except (TypeError, ValueError):
            pass

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


def build_v7_dynamic_edl(
    visual_plan: dict[str, Any],
    sentence_spans: list[dict[str, Any]],
    clip_files: list[Path],
    speech_end_sec: float,
    total_duration_sec: float,
    script_doc: dict[str, Any] | None = None,
    source_window_overrides: dict[int, Any] | None = None,
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
    from pipeline.depiction_rules import normalize_porcelain_v7_grammar

    n_sents = len(sentence_spans)
    n_clips = len(clip_files)
    if n_clips < DIORAMA_CLIP_COUNT_MIN:
        raise ValueError(
            f"build_v7_dynamic_edl requires >= {DIORAMA_CLIP_COUNT_MIN} unique clips (got {n_clips})"
        )
    use_porcelain = is_porcelain_v7_plan(visual_plan)
    fps = int(DIORAMA_V7_VIDEO_FPS)
    total_frames = min(SHORTS_HARD_CEILING_FRAMES_V7, max(48, int(round(total_duration_sec * fps))))
    min_outro_f = int(math.ceil(PORCELAIN_V7_MIN_CUT_SEC * fps - 1e-9)) if use_porcelain else 24
    speech_frames = min(total_frames - int(round(DIORAMA_OUTRO_SWELL_SEC * fps)), int(round(speech_end_sec * fps)))
    if use_porcelain:
        max_outro_f = int(PORCELAIN_V7_LONG_TAKE_MAX_SEC * fps)
        speech_frames = max(speech_frames, total_frames - max_outro_f)
    speech_frames = max(24, min(total_frames - min_outro_f, speech_frames))
    outro_frames = max(min_outro_f, total_frames - speech_frames)
    resolved_style = resolve_diorama_v7_style_profile(visual_plan)
    default_grammar = "porcelain_fullbleed_world" if use_porcelain else "lowpoly_fullbleed_world"
    plan_clips = visual_plan.get("clips") if isinstance(visual_plan.get("clips"), list) else []
    auto_anat = bool(visual_plan.get("auto_anatomy_labels", True))
    clip_durs = [max(4.0, float(_clip_duration(Path(cf)))) for cf in clip_files]
    clip_specs: dict[int, dict[str, Any]] = {}
    clip_grammars: dict[int, str] = {}
    clip_locations: dict[int, str] = {}
    clip_cameras: dict[int, str] = {}
    clip_brain_regions: dict[int, str | None] = {}
    clip_anatomy_labels: dict[int, str | None] = {}
    for idx in range(n_clips):
        spec = plan_clips[idx] if idx < len(plan_clips) and isinstance(plan_clips[idx], dict) else {}
        g_raw = str(spec.get("grammar") or spec.get("visual_grammar") or default_grammar)
        g_norm = normalize_porcelain_v7_grammar(g_raw) if use_porcelain else g_raw
        spec_eff = {**spec, "grammar": g_norm} if spec else {"grammar": g_norm}
        clip_specs[idx] = spec_eff
        clip_grammars[idx] = g_norm
        clip_locations[idx] = str(spec.get("location_id") or "").strip()
        clip_cameras[idx] = _resolve_v7_clip_camera(spec_eff, idx)
        b_reg, a_lbl = _resolve_v7_cut_anatomy_label(spec_eff, auto_enabled=auto_anat)
        clip_brain_regions[idx] = b_reg
        clip_anatomy_labels[idx] = a_lbl

    # 1. Identify dedicated outro clip (0-based)
    outro_clip_idx = n_clips - 1
    for idx in range(n_clips):
        spec = clip_specs[idx]
        if str(spec.get("cut_role") or "").strip().lower() == "outro":
            outro_clip_idx = idx
            break
    reserved_clips: set[int] = {outro_clip_idx}

    is_legacy_lowpoly = resolve_diorama_v7_style_profile(visual_plan) == DIORAMA_V7_STYLE_PROFILE

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
        if role in ("outro", "split_right", "split_bottom"):
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
        caps_loc = [
            max_ss_cf
            if int(b.get("end_sentence_index") or b.get("sentence_index") or 0) == int(b.get("sentence_index") or 0)
            else max_cf
            for b in beats_in
        ]
        if nb_loc > 0 and sum(caps_loc) < speech_frames <= nb_loc * max_cf:
            caps_loc = [max_cf] * nb_loc
        bnds = [0]
        for i_b in range(1, nb_loc):
            ideal_t = float(beats_in[i_b]["t0"])
            f_idx = int(round((ideal_t / max(0.1, speech_end_sec)) * speech_frames))
            min_f = bnds[-1] + min_cf
            max_f = speech_frames - (nb_loc - i_b) * min_cf
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
        all_durs_loc = [max(10, bnds[i_b + 1] - bnds[i_b]) / float(fps) for i_b in range(nb_loc)] + [
            outro_frames / float(fps)
        ]
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
        if "brain" in gm or "analogy" in gm or clip_anatomy_labels.get(c_i):
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

        src_s, src_span = _select_v7_source_window(
            Path(clip_files[chosen]),
            clip_durs[chosen],
            out_dur,
            clip_specs.get(chosen),
            override_src_start_sec=_override_start_for_1based(chosen + 1),
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

        cuts.append(
            {
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
                "anatomy_label": (clip_anatomy_labels.get(chosen) if mode == "single" else None),
                "src_start_sec": round(src_s, 4),
                "src_end_sec": src_e,
                "speed_ramp": False,
                "main_speed": round(src_span / max(0.1, out_dur), 4),
                "crop_zoom": 1.00,
                "secondary_clip_index": (secondary_clip_idx + 1 if secondary_clip_idx is not None else None),
                "secondary_clip_file": (clip_files[secondary_clip_idx].name if secondary_clip_idx is not None else None),
                "secondary_camera_move": secondary_cam,
                "secondary_src_span": secondary_src,
                "split_labels": split_labels,
                "outro_sky_card": False,
            }
        )

    # Append dedicated final Act 6 Sky Tilt-Up Outro Card cut at 1.00x natural 24fps
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

    all_used = {int(c["clip_index"]) for c in cuts} | {
        int(c["secondary_clip_index"]) for c in cuts if c.get("secondary_clip_index") is not None
    }
    return {
        "schema": PROMPT_SCHEMA_VERSION_V7,
        "profile": "neuro_diorama",
        "style_profile": resolved_style,
        "edl_mode": "v7_dynamic_zero_reuse_24fps",
        "playback_speed": float(DIORAMA_V7_VISUAL_PLAYBACK_SPEED),
        "zero_clip_reuse": bool(max_reuse <= 1),
        "max_clip_reuse": max_reuse,
        "fps": fps,
        "total_frames": total_frames,
        "total_duration_sec": round(total_frames / float(fps), 3),
        "speech_end_sec": round(speech_frames / float(fps), 3),
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
        "cuts": cuts,
    }


def build_crosscut_edl(
    visual_plan: dict[str, Any],
    sentence_spans: list[dict[str, Any]],
    clip_files: list[Path],
    speech_end_sec: float,
    total_duration_sec: float,
    script_doc: dict[str, Any] | None = None,
    source_window_overrides: dict[int, Any] | None = None,
) -> dict[str, Any]:
    """
    R58 / R63 NLE Edit Decision List builder:
      - Dispatches to Schema v7 `build_v7_dynamic_edl` (`24.0fps`, dynamic `CV >= 0.45`, `split_hstack`, `0%` reuse)
        whenever `is_diorama_v7_plan(visual_plan)` is True.
      - Dispatches to Schema v6.1 `build_one_to_one_edl` (`0%` clip reuse, `1.00x` framing)
        whenever `visual_plan.get("zero_clip_reuse")` is True or `len(clip_files) >= len(sentence_spans) + 1`.
      - Preserves legacy multi-window interleaving fallback only for legacy synthetic `20-26`-clip fixtures.
    """
    if is_diorama_v7_plan(visual_plan):
        return build_v7_dynamic_edl(
            visual_plan=visual_plan,
            sentence_spans=sentence_spans,
            clip_files=clip_files,
            speech_end_sec=speech_end_sec,
            total_duration_sec=total_duration_sec,
            script_doc=script_doc,
            source_window_overrides=source_window_overrides,
        )
    if bool(visual_plan.get("zero_clip_reuse")) or len(clip_files) >= len(sentence_spans) + 1:
        return build_one_to_one_edl(
            visual_plan=visual_plan,
            sentence_spans=sentence_spans,
            clip_files=clip_files,
            speech_end_sec=speech_end_sec,
            total_duration_sec=total_duration_sec,
            script_doc=script_doc,
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
    clip_durs = [max(4.0, float(_clip_duration(Path(cf)))) for cf in clip_files]

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

    # Tune cut count cleanly into [DIORAMA_TARGET_CUT_MIN, DIORAMA_TARGET_CUT_MAX - 1] (+1 outro cut)
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


def generate_diorama_ass_subtitles(
    ass_path: Path,
    events: list[tuple[float, float, list[str]]],
    sentence_spans: list[dict[str, Any]],
    visual_plan: dict[str, Any],
    edl: dict[str, Any],
) -> Path:
    """
    R59 / R63 pure-white (`#FFFFFF`) 1-line hard-cut subtitle & impact headline generator:
      - Schema v7 (`lowpoly_pastel_v7`): Bundled `AAB Condensed Black` (`78pt`), `Outline=5.0`, `Shadow=0.0`,
        `MarginV=678` (`Y_center ≈ 1209px`), frame-quantized `[f0, f1)` `24.0fps` contiguous `0-frame` handoffs
        (`1-frame` crisp reset only at Act breaks), `276pt` top `ChapterHeadline` cards, and `SplitLeft`/`SplitRight` labels.
      - Schema v6 (`neuro_diorama`): `Default` MarginV=650 (`Y≈64%`), 76px Arial Black, `<= 3 words`,
        `Callout` MarginV=1520, `SplitLeft`/`SplitRight` / `SplitTop`/`SplitBot`, and `OutroTitle`.
    """
    ass_path = Path(ass_path)
    ass_path.parent.mkdir(parents=True, exist_ok=True)
    hstack_spans = [
        (float(cut["out_start_sec"]), float(cut["out_end_sec"]))
        for cut in (edl.get("cuts") or [])
        if cut.get("mode") == "split_hstack"
    ]
    is_v7 = is_diorama_v7_plan(visual_plan) or int(edl.get("schema") or 6) >= PROMPT_SCHEMA_VERSION_V7
    if is_v7:
        fps = max(1, int(edl.get("fps") or DIORAMA_V7_VIDEO_FPS))
        speech_end = float(edl.get("speech_end_sec") or 172.0)
        total_dur = float(edl.get("total_duration_sec") or 174.5)
        speech_end_frame = max(8, int(round(speech_end * fps)))
        total_frames = max(speech_end_frame + 6, int(edl.get("total_frames") or round(total_dur * fps)))

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
            f"Style: Default,{DIORAMA_V7_SUBTITLE_FONT_NAME},{DIORAMA_V7_SUBTITLE_FONT_SIZE},&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,"
            f"0,0,0,0,100,100,0,0,1,{DIORAMA_V7_SUBTITLE_OUTLINE_WIDTH},{DIORAMA_V7_SUBTITLE_SHADOW_DEPTH},2,80,80,{DIORAMA_V7_SUBTITLE_MARGIN_V},1",
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

        filtered_evs = [
            (
                float(t0),
                float(t1),
                [_sanitize_ass_single_line(w) for w in words[:DIORAMA_SUBTITLE_MAX_WORDS] if _sanitize_ass_single_line(w)],
            )
            for t0, t1, words in events
        ]
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

            txt = _sanitize_ass_single_line(to_display_text(" ".join(clean_words)))
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
                sub_mv = int(DIORAMA_V7_SUBTITLE_MARGIN_V) + 16
                sub_prefix = "{\\bord9.5\\shad2\\4c&H000000&\\4a&H50&}"
                lines_v7.append(
                    f"Dialogue: 2,{_format_ass_ts(s0)},{_format_ass_ts(s1)},Default,,0,0,{sub_mv},,{sub_prefix}{txt}"
                )
            else:
                lines_v7.append(f"Dialogue: 2,{_format_ass_ts(s0)},{_format_ass_ts(s1)},Default,,0,0,0,,{txt}")
            f1_prev = f1
            prev_was_act_break = is_act_break_after

        # 2. Giant Top Chapter Impact Headlines (~144px height, <= DIORAMA_V7_CHAPTER_HEADLINE_MAX_WIDTH_PX width, >= 80px side margins)
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


def generate_diorama_audio_master(
    wav_path: Path,
    voice_pcm: np.ndarray,
    sr: int,
    speech_end_sec: float,
    edl: dict[str, Any],
) -> Path:
    """Mixes master voiceover + documentary score and normalizes to `-15.5 LUFS` (2ch stereo in Schema v7)."""
    wav_path = Path(wav_path)
    wav_path.parent.mkdir(parents=True, exist_ok=True)
    n_samples = len(voice_pcm)
    is_v7 = int(edl.get("schema") or 6) >= PROMPT_SCHEMA_VERSION_V7

    if is_v7:
        stereo_bgm = _synthesize_stereo_orchestral_bgm(n_samples, sr, speech_end_sec, edl)
        voice_mono = voice_pcm.astype(np.float32).reshape(-1)
        voice_st = np.column_stack([voice_mono, voice_mono])
        raw_sum = voice_st + stereo_bgm
        peak_raw = float(np.max(np.abs(raw_sum))) if raw_sum.size else 0.0
        # Stage unclipped 16-bit PCM with clean headroom before 2-pass EBU R128 linear normalization
        pre_scale = min(0.78, 0.92 / peak_raw) if peak_raw > 1e-5 else 0.78
        mixed_st = (raw_sum * pre_scale).astype(np.float32)
        with tempfile.TemporaryDirectory(prefix="aab_diorama_mix_v7_") as td:
            raw_wav = Path(td) / "raw_mix_st.wav"
            norm_wav = Path(td) / "norm_mix_st.wav"
            _write_stereo_wav(raw_wav, mixed_st, sr)
            # Pass 1: Measure integrated loudness & LRA so Schema v7 uses pure constant scalar linear gain
            # rather than FFmpeg single-pass loudnorm's 3-second sliding-window dynamic AGC gain-rider.
            af = (
                f"loudnorm=I={DIORAMA_TARGET_LUFS}:TP=-1.8:LRA=8.5,"
                "alimiter=limit=0.812:attack=5:release=50:level=disabled"
            )
            res_p1 = subprocess.run(
                [
                    _ffmpeg(), "-nostdin", "-hide_banner", "-y",
                    "-i", str(raw_wav),
                    "-af", f"loudnorm=I={DIORAMA_TARGET_LUFS}:TP=-1.8:LRA=8.5:print_format=json",
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
                            gain_db = max(-24.0, min(24.0, float(DIORAMA_TARGET_LUFS) - meas_i))
                            af = (
                                f"{_cfg.DIORAMA_V7_MASTER_DEESSER},"
                                f"volume={gain_db:.4f}dB,alimiter=limit=0.812:attack=5:release=50:level=disabled"
                            )
                        elif math.isfinite(meas_tp) and math.isfinite(meas_thresh) and math.isfinite(meas_offset):
                            af = (
                                f"{_cfg.DIORAMA_V7_MASTER_DEESSER},"
                                f"loudnorm=I={DIORAMA_TARGET_LUFS}:TP=-1.8:LRA=8.5"
                                f":measured_I={meas_i:.2f}:measured_TP={meas_tp:.2f}"
                                f":measured_LRA={meas_lra:.2f}:measured_thresh={meas_thresh:.2f}"
                                f":offset={meas_offset:.2f}:linear=true,"
                                "alimiter=limit=0.812:attack=5:release=50:level=disabled"
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
                pcm_st = np.clip(raw_sum * 0.84, -0.812, 0.812).astype(np.float32)
            mute_n = min(pcm_st.shape[0], int(0.095 * sr))
            if mute_n > 0:
                env_tail = np.linspace(1.0, 0.0, mute_n, dtype=np.float32)[:, None]
                pcm_st[-mute_n:, :] *= env_tail
            _write_stereo_wav(wav_path, pcm_st, sr)
        return wav_path

    accompaniment = _synthesize_documentary_pulse_bgm(n_samples, sr, speech_end_sec, edl)
    mixed = np.clip(voice_pcm.astype(np.float32) + accompaniment, -0.96, 0.96)

    with tempfile.TemporaryDirectory(prefix="aab_diorama_mix_") as td:
        raw_wav = Path(td) / "raw_mix.wav"
        norm_wav = Path(td) / "norm_mix.wav"
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
        _write_mono_wav(wav_path, pcm_out, sr)
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
) -> None:
    """Renders one frame-exact stitchable H.264 cut segment (`1080x1920 @ fps`, optional single-pass ASS burn-in or 1-frame PNG)."""
    c_frames = int(override_frames if override_frames is not None else cut["frames"])
    out_dur = c_frames / float(fps)
    c1_num = int(cut["clip_index"])
    p1 = clips_by_num[c1_num]
    eq1 = (pastel_eq_by_num or {}).get(c1_num, "")
    s0 = float(cut["src_start_sec"])
    s1 = float(cut["src_end_sec"])
    src_dur = max(0.25, s1 - s0)
    pts_ratio = out_dur / src_dur
    zoom = float(cut.get("crop_zoom") or 1.0)
    scaled_w = int(round(VIDEO_WIDTH * zoom))
    scaled_h = int(round(VIDEO_HEIGHT * zoom))
    scaled_w += scaled_w % 2
    scaled_h += scaled_h % 2

    interp_fps = max(48, fps * 2)
    pre_interp_1 = f"framerate=fps={interp_fps}:interp_start=0:interp_end=255:scene=100," if pts_ratio > 1.22 else ""
    s1_pad = s1 + (0.05 if pts_ratio > 1.22 else 0.04)
    tail_trim = ""
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
            "-threads", "1",
            "-pix_fmt", "yuv420p", "-an",
            str(out_seg),
        ]
    )

    if cut.get("mode") == "split_hstack" and cut.get("secondary_clip_index"):
        c2_num = int(cut["secondary_clip_index"])
        p2 = clips_by_num[c2_num]
        eq2 = (pastel_eq_by_num or {}).get(c2_num, "")
        sec0, sec1 = cut["secondary_src_span"]
        sec_dur = max(0.25, float(sec1) - float(sec0))
        pts2 = out_dur / sec_dur
        pre_interp_2 = f"framerate=fps={interp_fps}:interp_start=0:interp_end=255:scene=100," if pts2 > 1.22 else ""
        sec1_pad = float(sec1) + (0.05 if pts2 > 1.22 else 0.04)
        div_w = int(DIORAMA_V7_SPLIT_DIVIDER_PX)
        left_w = (VIDEO_WIDTH - div_w) // 2
        right_w = VIDEO_WIDTH - left_w - div_w
        pts_expr_1 = "setpts=PTS-STARTPTS" if abs(pts_ratio - 1.0) <= 0.035 else f"{pre_interp_1}setpts=({pts_ratio:.5f})*(PTS-STARTPTS)"
        pts_expr_2 = "setpts=PTS-STARTPTS" if abs(pts2 - 1.0) <= 0.035 else f"{pre_interp_2}setpts=({pts2:.5f})*(PTS-STARTPTS)"
        fc = (
            f"[0:v]trim=start={s0:.4f}:end={s1_pad:.4f},{pts_expr_1},"
            f"fps={fps},tpad=stop_mode=clone:stop_duration=0.25,"
            f"scale={VIDEO_WIDTH}:{VIDEO_HEIGHT}:force_original_aspect_ratio=increase:flags=lanczos,"
            f"{eq1}unsharp=5:5:0.35:5:5:0.0,format=gbrp,crop={left_w}:{VIDEO_HEIGHT}:(in_w-{left_w})/2:0[left];"
            f"[1:v]trim=start={sec0:.4f}:end={sec1_pad:.4f},{pts_expr_2},"
            f"fps={fps},tpad=stop_mode=clone:stop_duration=0.25,"
            f"scale={VIDEO_WIDTH}:{VIDEO_HEIGHT}:force_original_aspect_ratio=increase:flags=lanczos,"
            f"{eq2}unsharp=5:5:0.35:5:5:0.0,format=gbrp,crop={right_w}:{VIDEO_HEIGHT}:(in_w-{right_w})/2:0[right];"
            f"color=c=black:s={div_w}x{VIDEO_HEIGHT}:r={fps}:d={out_dur + 0.25:.4f},format=gbrp[div];"
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
        sec0, sec1 = cut["secondary_src_span"]
        sec_dur = max(0.25, float(sec1) - float(sec0))
        pts2 = out_dur / sec_dur
        pre_interp_2 = f"framerate=fps={interp_fps}:interp_start=0:interp_end=255:scene=100," if pts2 > 1.22 else ""
        sec1_pad = float(sec1) + (0.05 if pts2 > 1.22 else 0.04)
        half_h = (VIDEO_HEIGHT - 6) // 2
        half_h -= half_h % 2
        rem_h = VIDEO_HEIGHT - half_h - 6
        fc = (
            f"[0:v]trim=start={s0:.4f}:end={s1_pad:.4f},{pre_interp_1}setpts=({pts_ratio:.5f})*(PTS-STARTPTS),"
            f"fps={fps},tpad=stop_mode=clone:stop_duration=0.25,"
            f"scale={VIDEO_WIDTH}:{VIDEO_HEIGHT}:force_original_aspect_ratio=increase:flags=lanczos,"
            f"unsharp=5:5:0.35:5:5:0.0,crop={VIDEO_WIDTH}:{half_h}[top];"
            f"[1:v]trim=start={sec0:.4f}:end={sec1_pad:.4f},{pre_interp_2}setpts=({pts2:.5f})*(PTS-STARTPTS),"
            f"fps={fps},tpad=stop_mode=clone:stop_duration=0.25,"
            f"scale={VIDEO_WIDTH}:{VIDEO_HEIGHT}:force_original_aspect_ratio=increase:flags=lanczos,"
            f"unsharp=5:5:0.35:5:5:0.0,crop={VIDEO_WIDTH}:{rem_h}[bot];"
            f"color=c=white:s={VIDEO_WIDTH}x6:r={fps}:d={out_dur + 0.25:.4f}[div];"
            f"[top][div][bot]vstack=inputs=3,setsar=1,format=yuv420p{eff_ass}{tail_trim}[vout]"
        )
        cmd = [
            ff, "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
            "-i", str(p1), "-i", str(p2),
            "-filter_complex", fc, "-map", "[vout]",
            *v_enc_args,
        ]
    else:
        use_ramp = bool(cut.get("speed_ramp") and not cut.get("outro_sky_card"))
        if use_ramp:
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
        vf = (
            f"{pts_chain}"
            f"fps={fps},"
            f"tpad=stop_mode=clone:stop_duration=0.25,"
            f"scale={scaled_w}:{scaled_h}:force_original_aspect_ratio=increase:flags=lanczos,"
            f"{eq1}unsharp=5:5:0.35:5:5:0.0,"
            f"crop={VIDEO_WIDTH}:{VIDEO_HEIGHT},"
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


def _atomic_copy_file(src: Path, dst: Path, suffix: str | None = None) -> None:
    """Copies `src` to a temporary sibling file and atomically replaces `dst` via `os.replace()`."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp_dst = dst.with_suffix(suffix) if suffix else dst.with_name(f".tmp_{os.getpid()}_{dst.name}")
    shutil.copy2(src, tmp_dst)
    for attempt in range(5):
        try:
            os.replace(tmp_dst, dst)
            return
        except OSError:
            if attempt == 4:
                tmp_dst.unlink(missing_ok=True)
                raise
            time.sleep(0.15 * (attempt + 1))


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
) -> list[dict[str, Any]]:
    """
    F-1 pre-render plaque guard: probes every single-mode cut's source window at the exact frames DQ9
    (`start+0.08`, mid, `end-0.08` on 1080x1920 non-subtitle ROIs) and R64 (12/31/50/69/88% on the 360x640 grid)
    will later inspect. When any probe hits a horizontal glyph run >= `run_fail_threshold`, the window slides
    (closest-first, 0.125s steps) to the nearest start whose probes all stay below the threshold. Mutates `edl`.
    """
    from pipeline.dynamic_episode_qa import _non_subtitle_scene_rois
    from pipeline.flow_diorama_sharded_worker import _max_horizontal_plaque_glyph_run
    from pipeline.media_cache import stage_local_file

    clips_by_num = {i: Path(cf) for i, cf in enumerate(clip_files, start=1)}
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
            (_max_horizontal_plaque_glyph_run(r) for r in _non_subtitle_scene_rois(f1080, has_top_overlay=False, is_outro=False)),
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
            num = int(cut["clip_index"])
            if num not in clips_by_num or not clips_by_num[num].exists():
                continue
            s0 = float(cut["src_start_sec"])
            span = max(0.05, float(cut["src_end_sec"]) - s0)
            out_d = max(0.05, float(cut["duration_sec"]))
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
                    refinements.append(
                        {"cut_index": cut["cut_index"], "clip_index": num, "from_src_start": round(s0, 4), "to_src_start": round(cand, 4), "worst_run_before": worst}
                    )
                    fixed = True
                    break
            if not fixed:
                refinements.append({"cut_index": cut["cut_index"], "clip_index": num, "status": "unresolved", "worst_run": worst})
    finally:
        for cap in caps.values():
            cap.release()
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


def recut_diorama_cuts(project_id_or_dir: str | Path, cut_indices: list[int], allow_published_overwrite: bool = False) -> dict[str, Any]:
    """
    F-3 official partial re-render: re-renders only `cut_indices` from the current EDL (font-safe libass burn-in at the
    exact output offset), reuses every other cached segment, re-concats with `-c:v copy`, and re-muxes audio_master.wav.
    """
    from pipeline.media_cache import stage_local_file

    p_dir = Path(project_id_or_dir) if Path(str(project_id_or_dir)).exists() else (PROJECTS_DIR / str(project_id_or_dir))
    if (p_dir / "06_publish" / "upload_receipt.json").exists() and not allow_published_overwrite:
        raise RuntimeError(f"Refusing to recut published project {p_dir.name} (pass allow_published_overwrite=True)")
    asm_dir = p_dir / "05_assembly"
    edl = json.loads((asm_dir / "edit_decision_list.json").read_text(encoding="utf-8"))
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
    clips_dir = p_dir / "03_visuals" / "flow_native_clips"
    clip_files = sorted((f for f in clips_dir.glob("clip_*.mp4") if f.is_file()), key=numeric_clip_sort_key)
    ff = _ffmpeg()
    fps = int(index["fps"])
    with tempfile.TemporaryDirectory(prefix="aab_recut_") as td:
        td_path = Path(td)
        need_nums = set()
        for ci in want:
            c = cuts_by_idx[ci]
            need_nums.add(int(c["clip_index"]))
            if c.get("secondary_clip_index"):
                need_nums.add(int(c["secondary_clip_index"]))
        local_clips = {n: stage_local_file(clip_files[n - 1])[0] for n in need_nums}
        pastel = {} if is_porcelain_v7_plan(edl) else {n: _compute_v7_pastel_eq_filter(local_clips[n]) for n in need_nums}
        shutil.copy2(ass_path, td_path / "subtitles.ass")
        fonts_dir = td_path / "fonts"
        fonts_dir.mkdir()
        bundled = ensure_bundled_condensed_font()
        shutil.copy2(bundled, fonts_dir / bundled.name)
        font_rep = probe_ass_font_resolution(ff, td_path, "subtitles.ass", fontsdir="fonts")
        if not font_rep["passed"]:
            raise RuntimeError(f"F-2 font guard failed during recut: {font_rep['fallbacks'][:2]}")
        ass_filter = "ass=subtitles.ass:fontsdir=fonts"
        for s in segs:
            if s["cut_index"] not in want:
                continue
            out_seg = td_path / s["file"]
            burn = f",setpts=PTS+{float(s['start_sec']):.6f}/TB,{ass_filter},setpts=PTS-STARTPTS"
            _render_cut_segment(
                ff, cuts_by_idx[s["cut_index"]], local_clips, out_seg, fps,
                pastel_eq_by_num=pastel, ass_burn_chain=burn, crf=18, preset="veryfast", cwd=td_path,
                override_frames=int(s["frames"]),
            )
            shutil.copy2(out_seg, cdir / s["file"])
        concat_txt = td_path / "concat.txt"
        concat_txt.write_text("\n".join(f"file '{(cdir / s['file']).as_posix()}'" for s in segs) + "\n", encoding="utf-8")
        shutil.copy2(wav_path, td_path / "audio_master.wav")
        cum = sum(int(s["frames"]) for s in segs)
        exact_dur = min(SHORTS_HARD_CEILING_SEC, cum / float(fps))
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
        pass
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
) -> dict[str, Any]:
    """
    End-to-end Schema v6 / Schema v7 `neuro_diorama` Gear 4 assembly:
      - Schema v7 (`porcelain_cinematic_v7` / `lowpoly_pastel_v7`): `DIORAMA_VOICE_PRESETS` (`andrew_v7` / `emma_v7` / `ava_v7` / `aria_v7` / `christopher_v7`)
        breath-trimmed master clock (`dynamic_us_v7` / `dynamic_rush_v7`), `24.0fps` `1.00x` dynamic-rhythm 1:1 Zero-Reuse EDL,
        `split_hstack` `6px` black vertical divider, bundled `AABCondensed-Black.ttf` subtitles + `276pt` chapter headlines, and 2ch stereo score.
      - Schema v6 (`neuro_diorama`): `30fps` NLE EDL (`<= 5,370 frames`), `Y=64%` single-line ASS, `-24 dB` BGM.
    """
    from pipeline.config import MICRO_SHORT_CUT_MIN, MICRO_SHORT_PROFILE

    p_dir = Path(project_id_or_dir) if Path(str(project_id_or_dir)).exists() else (PROJECTS_DIR / str(project_id_or_dir))
    final_mp4 = p_dir / "05_assembly" / "final_shorts_1080x1920.mp4"
    if final_mp4.exists() and not force_rebuild and preview_sec is None:
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
    sentences, script_doc = load_diorama_script_sentences(p_dir)
    fmt_profile = str(script_doc.get("format_profile") or visual_plan.get("format_profile") or "").strip().lower()
    min_clips_req = MICRO_SHORT_CUT_MIN if fmt_profile == MICRO_SHORT_PROFILE else DIORAMA_CLIP_COUNT_MIN

    clips_dir = p_dir / "03_visuals" / "flow_native_clips"
    clip_files = sorted((f for f in clips_dir.glob("clip_*.mp4") if f.is_file()), key=numeric_clip_sort_key)
    if len(clip_files) < min_clips_req:
        raise RuntimeError(
            f"neuro_diorama assembly requires >= {min_clips_req} clips in {clips_dir} (found {len(clip_files)})"
        )
    if not visual_plan.get("outro_title_lines") and script_doc.get("outro_title_lines"):
        visual_plan["outro_title_lines"] = script_doc["outro_title_lines"]
    is_v7 = is_diorama_v7_plan(visual_plan) or is_diorama_v7_plan(script_doc)
    if is_v7 and int(script_doc.get("schema") or 0) < PROMPT_SCHEMA_VERSION_V7:
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
        vr = json.loads(existing_vr.read_text(encoding="utf-8"))
        tts_res = {
            "sentence_spans": vr["sentence_spans"],
            "events": vr["events"],
            "speech_end_sec": float(vr["speech_end_sec"]),
            "total_duration_sec": float(vr["total_duration_sec"]),
            "active_speech_ratio": float(vr.get("active_speech_ratio", 0.90)),
            "true_rms_voiced_ratio": vr.get("true_rms_voiced_ratio"),
            "report": vr,
            "pcm": None,
            "sr": int(vr.get("sample_rate") or 48000),
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

    edl = build_crosscut_edl(
        visual_plan=visual_plan,
        sentence_spans=tts_res["sentence_spans"],
        clip_files=clip_files,
        speech_end_sec=tts_res["speech_end_sec"],
        total_duration_sec=tts_res["total_duration_sec"],
        script_doc=script_doc,
        source_window_overrides=(eff_overrides or None),
    )
    if is_v7 and optimize_plaque_windows:
        edl["plaque_window_refinements"] = refine_plaque_safe_source_windows(edl, clip_files)
    pros_mode_used = str((tts_res.get("report") or {}).get("prosody_mode") or "uniform_108x")
    edl["prosody_mode"] = pros_mode_used
    if pros_mode_used != "uniform_108x":
        stamp_windows: list[list[float]] = []
        spans_by_idx = {int(sp["sentence_index"]): sp for sp in tts_res["sentence_spans"]}
        try:
            pr_doc = json.loads((p_dir / "04_audio" / "prosody_report.json").read_text(encoding="utf-8"))
            for row in pr_doc.get("sentences") or []:
                si = int(row["sentence_index"])
                if row.get("gear") == "stamp" and si > 1 and (si - 1) in spans_by_idx and si in spans_by_idx:
                    w0 = float(spans_by_idx[si - 1]["end_sec"]) - 0.04
                    w1 = float(spans_by_idx[si]["start_sec"]) + 0.06
                    if w1 - w0 >= 0.12:
                        stamp_windows.append([round(w0, 3), round(w1, 3)])
        except Exception:  # noqa: BLE001
            stamp_windows = []
        edl["prosody_stamp_windows"] = stamp_windows
    asm_dir = p_dir / "05_assembly"
    asm_dir.mkdir(parents=True, exist_ok=True)
    edl_path = asm_dir / "edit_decision_list.json"
    tmp_edl = edl_path.with_suffix(".json.tmp")
    tmp_edl.write_text(json.dumps(edl, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp_edl, edl_path)

    # 3. Subtitles & Master Audio
    ass_path = generate_diorama_ass_subtitles(
        ass_path=audio_dir / "subtitles.ass",
        events=tts_res["events"],
        sentence_spans=tts_res["sentence_spans"],
        visual_plan=visual_plan,
        edl=edl,
    )
    if preserve_audio_master:
        wav_path = audio_dir / "audio_master.wav"
    else:
        wav_path = generate_diorama_audio_master(
            wav_path=audio_dir / "audio_master.wav",
            voice_pcm=tts_res["pcm"],
            sr=tts_res["sr"],
            speech_end_sec=edl["speech_end_sec"],
            edl=edl,
        )

    # 4. Single-pass stitchable ASS segment encode in local /tmp scratch + zero-reencode mux (Speed-3)
    from concurrent.futures import ThreadPoolExecutor
    from pipeline.media_cache import register_staged_copy, stage_local_file

    ff = _ffmpeg()
    fps = int(edl["fps"])
    is_v7_edl = is_v7 or int(edl.get("schema") or 6) >= PROMPT_SCHEMA_VERSION_V7
    ceiling_frames = SHORTS_HARD_CEILING_FRAMES_V7 if is_v7_edl else SHORTS_HARD_CEILING_FRAMES
    total_frames = min(ceiling_frames, int(edl["total_frames"]))
    target_crf = 18 if is_v7_edl else 19
    n_workers = max(1, min(4, os.cpu_count() or 2))

    with tempfile.TemporaryDirectory(prefix="aab_diorama_asm_") as td:
        td_path = Path(td)
        local_clips: dict[int, Path] = {}
        for idx, cf in enumerate(clip_files, start=1):
            local_clips[idx], _ = stage_local_file(cf)
        pastel_eq_by_num: dict[int, str] = {}
        is_porcelain_edl = is_porcelain_v7_plan(visual_plan, edl)
        if is_v7_edl and not is_porcelain_edl:
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

        def _render_one(job: tuple[dict[str, Any], Path, int, float]) -> None:
            c_item, s_path, eff_f, start_s = job
            burn_chain = f",setpts=PTS+{start_s:.6f}/TB,{ass_filter},setpts=PTS-STARTPTS"
            _render_cut_segment(
                ff,
                c_item,
                local_clips,
                s_path,
                fps,
                pastel_eq_by_num=pastel_eq_by_num,
                ass_burn_chain=burn_chain,
                crf=target_crf,
                preset="veryfast",
                cwd=td_path,
                override_frames=eff_f,
            )

        with ThreadPoolExecutor(max_workers=n_workers) as pool:
            list(pool.map(_render_one, seg_jobs))

        concat_txt = td_path / "concat.txt"
        concat_txt.write_text("\n".join(f"file '{jb[1].name}'" for jb in seg_jobs) + "\n", encoding="utf-8")

        local_final = td_path / "final_shorts_1080x1920.mp4"
        audio_ch = str(DIORAMA_V7_AUDIO_CHANNELS) if is_v7_edl else "1"
        lim_ceil = "0.812" if is_v7_edl else "0.776"
        # v7: 4x-oversampled (192 kHz) limiter so intersample peaks are caught before AAC; loudness untouched
        lim_chain = (DIORAMA_MUX_TRUE_PEAK_LIMITER if is_v7_edl
                     else f"alimiter=limit={lim_ceil}:attack=5:release=50:level=disabled")
        exact_dur = min(SHORTS_HARD_CEILING_SEC, cum_frames / float(fps))

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

        res_mux = _run_final_mux(0.0)
        # AAC true-peak guard: the sample-peak limiter cannot see AAC intersample overshoot (up to ~1.4 dB on
        # restored-HF consonant transients). Re-encode with a static trim until the encoded file sits under target.
        mux_trim_db = 0.0
        for _ in range(3):
            if res_mux.returncode != 0 or not local_final.exists():
                break
            tp_enc = _measure_true_peak_dbtp(local_final)
            if tp_enc is None or tp_enc <= DIORAMA_MUX_TRUE_PEAK_TARGET_DBTP:
                break
            mux_trim_db -= (tp_enc - DIORAMA_MUX_TRUE_PEAK_TARGET_DBTP) + 0.1
            res_mux = _run_final_mux(mux_trim_db)
        if res_mux.returncode != 0 or not local_final.exists():
            raise RuntimeError(f"FFmpeg final mux failed: {res_mux.stderr[:300]}")
        if preview_sec is not None:
            prev_mp4 = asm_dir / f"preview_0-{int(round(float(preview_sec)))}s.mp4"
            _atomic_copy_file(local_final, prev_mp4, suffix=".mp4.tmp")
            return {
                "project_dir": str(p_dir),
                "preview_mp4": str(prev_mp4),
                "preview_sec": round(cum_frames / float(fps), 3),
                "prosody_mode": edl.get("prosody_mode"),
                "plaque_window_refinements": edl.get("plaque_window_refinements"),
                "rebuilt": True,
            }
        _store_segment_cache(p_dir, seg_jobs, edl, ass_path)
        _atomic_copy_file(local_final, final_mp4, suffix=".mp4.tmp")
        register_staged_copy(local_final, final_mp4)
        from pipeline import thumbnail_studio

        thumbnail_studio.run(
            p_dir,
            force=force_rebuild,
            strict=False,
            local_clips=local_clips,
            pastel_eq_by_num=pastel_eq_by_num,
        )

    from pipeline.config import MICRO_SHORT_MIN_SEC

    probe_min_dur = (
        MICRO_SHORT_MIN_SEC
        if fmt_profile == MICRO_SHORT_PROFILE
        else (DIORAMA_V7_DURATION_MIN_SEC if is_v7_edl else None)
    )
    probe_report = MediaIntegrityValidator.validate_video_asset(
        final_mp4,
        asset_type="final_shorts",
        strict=True,
        min_duration_sec=probe_min_dur,
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
            "mean_clarity_score": ph_rep["summary"]["mean_clarity_score"],
            "weak_cut_indices": ph_rep["summary"]["weak_cut_indices"],
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
        "rebuilt": True,
    }
    if posthoc_summary is not None:
        out_payload["posthoc_qa"] = posthoc_summary
    return out_payload


assemble_diorama_episode = assemble_diorama_project

__all__ = [
    "assemble_diorama_episode",
    "assemble_diorama_project",
    "build_crosscut_edl",
    "build_one_to_one_edl",
    "build_v7_dynamic_edl",
    "ensure_bundled_condensed_font",
    "generate_diorama_ass_subtitles",
    "generate_diorama_audio_master",
    "load_diorama_script_sentences",
]
