"""
ALL ABOUT BRAIN — Standalone 16:9 (`1920x1080 @ 24fps`) ASS Subtitle & Lower-Left Citation Card Engine
(`pipeline/longform_subtitles.py`).

Renders `04_audio/subtitles.ass` (`PlayResX: 1920, PlayResY: 1080`) with:
  1. Burned-in bottom-center single-line `Default` subtitles (`AAB Condensed Black`, `fs=58`, `MarginV=98`,
     `Y ∈ [922, 982]`, `<= 5` words & `<= 32` characters per card, 0-frame gap inside each sentence).
  2. Non-overlapping lower-left `DocCitationCard` (`X=96`, `Y ∈ [752, 868]`, `+54px >= +50px` vertical clearance
     above `Default` subtitles, dynamic `PIL`-measured box width `340..660px`, `5.0s` `\fad(220,280)`).
  3. Top-center `ChapterHeadline` (`Y=86`), `AnatomyLabel` (`Y=92`), and `SplitLeft` (`X=480`) / `SplitRight` (`X=1440`).
"""

from __future__ import annotations

import math
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import ImageFont

from pipeline.config import (
    DIORAMA_V7_SUBTITLE_FONT_NAME,
    FONT_CONDENSED_BLACK_PATH,
    LONGFORM_CHAPTER_HEADLINE_DURATION_SEC,
    LONGFORM_CHAPTER_HEADLINE_FONT_SIZE,
    LONGFORM_CITATION_CARD_BAR_WIDTH_PX,
    LONGFORM_CITATION_CARD_DURATION_SEC,
    LONGFORM_CITATION_CARD_MIN_CLEARANCE_PX,
    LONGFORM_CITATION_CARD_WIDTH_RANGE,
    LONGFORM_CITATION_CARD_X,
    LONGFORM_SPLIT_LEFT_X,
    LONGFORM_SPLIT_RIGHT_X,
    LONGFORM_SUBTITLE_FONT_SIZE,
    LONGFORM_SUBTITLE_MARGIN_V,
    LONGFORM_SUBTITLE_MAX_CHARS,
    LONGFORM_SUBTITLE_MAX_WORDS,
    LONGFORM_SUBTITLE_OUTLINE_WIDTH,
    LONGFORM_SUBTITLE_SHADOW_DEPTH,
    LONGFORM_SUBTITLE_Y_RANGE,
    LONGFORM_VIDEO_FPS,
    LONGFORM_VIDEO_HEIGHT,
    LONGFORM_VIDEO_WIDTH,
)
from pipeline.diorama_assembler import ensure_bundled_condensed_font
from pipeline.longform_prompt_builder import resolve_longform_project_dir

CARD_Y_TOP = 752
CARD_HEIGHT = 116  # Y_bot = 868 -> 922 - 868 = +54px (>= +50px clearance!)


def _resolve_ffmpeg_bin() -> str:
    sys_ff = shutil.which("ffmpeg")
    if sys_ff:
        return sys_ff
    import imageio_ffmpeg

    return imageio_ffmpeg.get_ffmpeg_exe()


def _format_ass_ts(sec: float) -> str:
    s = max(0.0, float(sec))
    h = int(s // 3600)
    m = int((s % 3600) // 60)
    rem = s - (h * 3600 + m * 60)
    return f"{h}:{m:02d}:{rem:05.2f}"


def _snap_frame_ass_sec(sec: float, fps: int = LONGFORM_VIDEO_FPS) -> float:
    if sec <= 0.0:
        return 0.0
    f_idx = max(1, int(round(sec * fps)))
    mid = (float(f_idx) - 0.5) / float(fps)
    return round(math.ceil(mid * 100.0) / 100.0, 2)


def _escape_ass_text(text: str) -> str:
    t = str(text or "").replace("\\", "").replace("{", "(").replace("}", ")")
    return re.sub(r"\s+", " ", t).strip()


def chunk_timed_words_for_longform(
    timed_words: list[dict[str, Any]],
    *,
    max_words: int = LONGFORM_SUBTITLE_MAX_WORDS,
    max_chars: int = LONGFORM_SUBTITLE_MAX_CHARS,
) -> list[dict[str, Any]]:
    """
    Splits a sentence's `timed_words` (`[{"word": str, "start": float, "end": float}, ...]`)
    into balanced single-line subtitle bursts (`<= max_words` and `<= max_chars`), avoiding
    awkward 1-word trailing orphans where possible.
    """
    clean_words = [
        {
            "word": _escape_ass_text(w.get("word") or ""),
            "start": float(w.get("start") or 0.0),
            "end": float(w.get("end") or 0.0),
        }
        for w in timed_words
        if _escape_ass_text(w.get("word") or "")
    ]
    if not clean_words:
        return []

    raw_groups: list[list[dict[str, Any]]] = []
    cur: list[dict[str, Any]] = []
    for item in clean_words:
        w_txt = item["word"]
        # Guard an ultra-long hyphenated token (> max_chars) by splitting on hyphen
        if len(w_txt) > max_chars and "-" in w_txt:
            parts = [p for p in w_txt.split("-") if p]
            mid_t = 0.5 * (item["start"] + item["end"])
            sub_items = [
                {"word": parts[0] + "-", "start": item["start"], "end": mid_t},
                {"word": "-".join(parts[1:]), "start": mid_t, "end": item["end"]},
            ]
        else:
            sub_items = [item]

        for sub in sub_items:
            cand_words = [x["word"] for x in cur] + [sub["word"]]
            cand_str = " ".join(cand_words)
            if cur and (len(cand_words) > max_words or len(cand_str) > max_chars):
                raw_groups.append(cur)
                cur = [sub]
            else:
                cur.append(sub)
                # Natural clause break after comma / semicolon / em-dash / colon when >= 3 words
                if len(cur) >= 3 and cur[-1]["word"].endswith((",", ";", ":", "—", "–")):
                    raw_groups.append(cur)
                    cur = []
    if cur:
        raw_groups.append(cur)

    # Rebalance 1-word trailing orphan if previous group has >= 3 words and moving 1 word stays <= max_chars
    if len(raw_groups) >= 2 and len(raw_groups[-1]) == 1 and len(raw_groups[-2]) >= 3:
        moved = raw_groups[-2][-1]
        cand_last = " ".join([moved["word"], raw_groups[-1][0]["word"]])
        if len(cand_last) <= max_chars:
            raw_groups[-2] = raw_groups[-2][:-1]
            raw_groups[-1] = [moved, raw_groups[-1][0]]

    events: list[dict[str, Any]] = []
    for grp in raw_groups:
        txt = " ".join(x["word"] for x in grp).strip()
        if len(txt) > max_chars:
            txt = txt[: max_chars - 1].rstrip() + "…"
        events.append(
            {
                "text": txt,
                "word_count": len(grp),
                "char_count": len(txt),
                "start": grp[0]["start"],
                "end": grp[-1]["end"],
            }
        )
    return events


_DANGLING_CITATION_STOPWORDS = frozenset(
    {"in", "to", "and", "or", "of", "with", "for", "by", "on", "at", "from", "into", "the", "a", "an", "as", "that"}
)


def _measure_citation_card_lines(
    card: dict[str, Any],
    font_path: Path,
) -> tuple[str, str, int, int, int]:
    """Formats & PIL-measures the 2 lines of a `DocCitationCard` with adaptive font-size step-down before truncation."""
    year = str(card.get("year") or "").strip()
    journal = str(card.get("journal") or "PEER-REVIEWED STUDY").strip().upper()
    doi = str(card.get("doi") or "").strip()
    authors = str(card.get("authors") or "Research Team").strip()
    finding = str(card.get("finding") or card.get("summary") or "").strip()

    line1 = _escape_ass_text(f"{year} · {journal}" + (f"  |  DOI {doi}" if doi else ""))
    line2 = _escape_ass_text(f"{authors} — {finding}" if finding else authors)

    min_w, max_w = LONGFORM_CITATION_CARD_WIDTH_RANGE
    pad_left = 18
    pad_right = 28
    max_text_px = max_w - (pad_left + pad_right)

    def _load_fnt(sz: int) -> Any:
        try:
            return ImageFont.truetype(str(font_path), sz)
        except Exception:
            return ImageFont.load_default()

    def _eff_px(txt: str, fnt: Any) -> int:
        bb = fnt.getbbox(txt)
        return int(math.ceil((bb[2] - bb[0]) * 1.04))

    def _fit_with_sizes(txt: str, candidate_sizes: tuple[int, ...]) -> tuple[str, int, int]:
        for sz in candidate_sizes:
            fnt = _load_fnt(sz)
            w0 = _eff_px(txt, fnt)
            if w0 <= max_text_px:
                return txt, w0, sz
        min_sz = candidate_sizes[-1]
        fnt_min = _load_fnt(min_sz)
        toks = txt.split()
        while len(toks) > 3:
            toks = toks[:-1]
            while len(toks) > 3 and toks[-1].lower().strip(",;:-—.") in _DANGLING_CITATION_STOPWORDS:
                toks = toks[:-1]
            cand = " ".join(toks).rstrip(",;:-—.") + "…"
            w_c = _eff_px(cand, fnt_min)
            if w_c <= max_text_px:
                return cand, w_c, min_sz
        cur = txt
        while len(cur) > 12:
            w_c = _eff_px(cur, fnt_min)
            if w_c <= max_text_px:
                return cur, w_c, min_sz
            cur = cur[:-2].rstrip() + "…"
        return cur, _eff_px(cur, fnt_min), min_sz

    fit1, w1, fs1 = _fit_with_sizes(line1, (22, 20, 18))
    fit2, w2, fs2 = _fit_with_sizes(line2, (26, 24, 22, 20, 18, 16))
    box_w = max(min_w, min(max_w, max(w1, w2) + pad_left + pad_right))
    return fit1, fit2, int(box_w), int(fs1), int(fs2)


def build_longform_subtitles_ass(
    project_id_or_dir: str | Path,
    *,
    sentence_timings: list[dict[str, Any]],
    total_duration_sec: float,
    script_doc: dict[str, Any] | None = None,
    visual_plan: dict[str, Any] | None = None,
    out_ass_path: Path | None = None,
) -> dict[str, Any]:
    """
    Builds and writes `04_audio/subtitles.ass` (`PlayResX: 1920, PlayResY: 1080`) with burned-in
    single-line `Default` subtitles and non-overlapping lower-left `DocCitationCard` overlays.
    """
    p_dir = resolve_longform_project_dir(project_id_or_dir, create=False)
    font_path = ensure_bundled_condensed_font(FONT_CONDENSED_BLACK_PATH)
    ass_path = Path(out_ass_path) if out_ass_path is not None else (p_dir / "04_audio" / "subtitles.ass")
    ass_path.parent.mkdir(parents=True, exist_ok=True)

    s_doc = script_doc or {}
    vp_doc = visual_plan or {}
    citations_by_id: dict[str, dict[str, Any]] = {}
    for c_card in (vp_doc.get("citation_cards") or s_doc.get("citation_cards") or []):
        cid = str(c_card.get("citation_id") or c_card.get("id") or "").strip()
        if cid:
            citations_by_id[cid] = c_card

    chapters_by_num: dict[int, dict[str, Any]] = {}
    for ch in (s_doc.get("chapters") or vp_doc.get("chapters") or []):
        chapters_by_num[int(ch.get("chapter_number") or 0)] = ch

    header = f"""[Script Info]
Title: ALL ABOUT BRAIN 16x9 Long-Form Subtitles & DOI Citation Cards
ScriptType: v4.00+
PlayResX: {LONGFORM_VIDEO_WIDTH}
PlayResY: {LONGFORM_VIDEO_HEIGHT}
WrapStyle: 2
ScaledBorderAndShadow: yes
YCbCr Matrix: TV.709

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{DIORAMA_V7_SUBTITLE_FONT_NAME},{LONGFORM_SUBTITLE_FONT_SIZE},&H00FFFFFF,&H0000D4FF,&H00120C08,&H64000000,0,0,0,0,100,100,0.4,0,1,{LONGFORM_SUBTITLE_OUTLINE_WIDTH},{LONGFORM_SUBTITLE_SHADOW_DEPTH},2,140,140,{LONGFORM_SUBTITLE_MARGIN_V},1
Style: ChapterHeadline,{DIORAMA_V7_SUBTITLE_FONT_NAME},{LONGFORM_CHAPTER_HEADLINE_FONT_SIZE},&H00FFFFFF,&H00FFFFFF,&H00140E0A,&H78000000,0,0,0,0,96,100,1.0,0,1,4.0,1.2,8,120,120,82,1
Style: AnatomyLabel,{DIORAMA_V7_SUBTITLE_FONT_NAME},44,&H00FFF4D8,&H00FFFFFF,&H00140E0A,&H70000000,0,0,0,0,96,100,0.8,0,1,3.2,0.8,8,120,120,88,1
Style: SplitLabel,{DIORAMA_V7_SUBTITLE_FONT_NAME},42,&H00FFFFFF,&H00FFFFFF,&H00140E0A,&H70000000,0,0,0,0,96,100,0.8,0,1,3.2,0.8,8,60,60,88,1
Style: DocCitationBg,{DIORAMA_V7_SUBTITLE_FONT_NAME},20,&H30221810,&H30221810,&HFF000000,&HFF000000,0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1
Style: DocCitationBar,{DIORAMA_V7_SUBTITLE_FONT_NAME},20,&H0038B8F5,&H0038B8F5,&HFF000000,&HFF000000,0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1
Style: DocCitationHeader,{DIORAMA_V7_SUBTITLE_FONT_NAME},22,&H0058C8FF,&H0058C8FF,&H00100A06,&H00000000,0,0,0,0,100,100,0.5,0,1,1.6,0.0,7,0,0,0,1
Style: DocCitationBody,{DIORAMA_V7_SUBTITLE_FONT_NAME},26,&H00F8FAFC,&H00F8FAFC,&H00100A06,&H00000000,0,0,0,0,100,100,0.3,0,1,1.8,0.0,7,0,0,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    dialogue_lines: list[str] = []
    sub_count = 0
    citation_events: list[dict[str, Any]] = []
    seen_citations: set[str] = set()
    seen_chapters: set[int] = set()
    chapter_headline_windows: list[tuple[float, float]] = []
    last_card_end = 0.0

    for s_info in sentence_timings:
        s_idx = int(s_info.get("sentence_index") or 0)
        ch_num = int(s_info.get("chapter") or 1)
        s_start = float(s_info.get("start_sec") or 0.0)
        s_end = float(s_info.get("end_sec") or (s_start + 2.0))
        words = list(s_info.get("words") or [])
        if not words and s_info.get("text"):
            toks = [t for t in str(s_info["text"]).split() if t]
            dur_w = max(0.15, (s_end - s_start) / max(1, len(toks)))
            words = [
                {
                    "word": tok,
                    "start": s_start + k * dur_w,
                    "end": s_start + (k + 1) * dur_w,
                }
                for k, tok in enumerate(toks)
            ]

        # 1. Chapter Headline at start of each chapter
        if ch_num not in seen_chapters and ch_num in chapters_by_num:
            seen_chapters.add(ch_num)
            hl_txt = _escape_ass_text(chapters_by_num[ch_num].get("headline") or f"CHAPTER {ch_num}")
            hl_start = max(0.12 if ch_num == 1 else s_start, s_start)
            hl_end = min(total_duration_sec - 0.4, hl_start + LONGFORM_CHAPTER_HEADLINE_DURATION_SEC)
            if hl_end - hl_start >= 1.2:
                chapter_headline_windows.append((hl_start, hl_end))
                dialogue_lines.append(
                    f"Dialogue: 2,{_format_ass_ts(hl_start)},{_format_ass_ts(hl_end)},ChapterHeadline,,0,0,0,,"
                    f"{{\\an8\\pos(960,84)\\fad(220,300)}}{hl_txt}"
                )

        # 2. Default Bottom-Center Single-Line Subtitles (<= 5 words, <= 32 chars, 0-frame intra-sentence handoff)
        bursts = chunk_timed_words_for_longform(words)
        snapped_bounds: list[tuple[float, float, str]] = []
        for b_i, b in enumerate(bursts):
            t0 = _snap_frame_ass_sec(b["start"]) if b_i > 0 else round(max(0.0, b["start"]), 2)
            t1 = _snap_frame_ass_sec(b["end"]) if b_i < len(bursts) - 1 else round(max(t0 + 0.28, b["end"] + 0.06), 2)
            if snapped_bounds and t0 < snapped_bounds[-1][1]:
                t0 = snapped_bounds[-1][1]
            if t1 <= t0 + 0.12:
                t1 = round(t0 + 0.24, 2)
            snapped_bounds.append((t0, min(round(total_duration_sec - 0.10, 2), t1), b["text"]))

        for k_b in range(len(snapped_bounds) - 1):
            cur_t0, cur_t1, cur_txt = snapped_bounds[k_b]
            next_t0 = snapped_bounds[k_b + 1][0]
            if 0.0 < next_t0 - cur_t1 <= 0.55:
                snapped_bounds[k_b] = (cur_t0, next_t0, cur_txt)

        for t0, t1, vis_txt in snapped_bounds:
            if t1 > t0:
                dialogue_lines.append(
                    f"Dialogue: 2,{_format_ass_ts(t0)},{_format_ass_ts(t1)},Default,,0,0,0,,{vis_txt}"
                )
                sub_count += 1

        # 3. Lower-Left DocCitationCard on first mention
        cid = str(s_info.get("citation_id") or "").strip()
        if cid and cid in citations_by_id and cid not in seen_citations:
            seen_citations.add(cid)
            card_obj = citations_by_id[cid]
            line1_txt, line2_txt, box_w, fs1, fs2 = _measure_citation_card_lines(card_obj, font_path)
            c_start = round(max(s_start + 0.10, last_card_end + 0.35), 2)
            c_end = round(min(total_duration_sec - 0.45, c_start + LONGFORM_CITATION_CARD_DURATION_SEC), 2)
            if c_end - c_start >= 2.2:
                last_card_end = c_end
                x0 = LONGFORM_CITATION_CARD_X
                y0 = CARD_Y_TOP
                bh = CARD_HEIGHT
                bar_w = LONGFORM_CITATION_CARD_BAR_WIDTH_PX
                fs1_tag = f"\\fs{fs1}" if fs1 != 22 else ""
                fs2_tag = f"\\fs{fs2}" if fs2 != 26 else ""
                dialogue_lines.append(
                    f"Dialogue: 0,{_format_ass_ts(c_start)},{_format_ass_ts(c_end)},DocCitationBg,{cid},0,0,0,,"
                    f"{{\\an7\\pos({x0},{y0})\\fad(220,280)\\1c&H221810&\\1a&H28&\\3a&HFF&\\4a&HFF&\\p1}}"
                    f"m 0 0 l {box_w} 0 {box_w} {bh} 0 {bh}{{\\p0}}"
                )
                dialogue_lines.append(
                    f"Dialogue: 1,{_format_ass_ts(c_start)},{_format_ass_ts(c_end)},DocCitationBar,{cid},0,0,0,,"
                    f"{{\\an7\\pos({x0},{y0})\\fad(220,280)\\1c&H38B8F5&\\1a&H00&\\3a&HFF&\\4a&HFF&\\p1}}"
                    f"m 0 0 l {bar_w} 0 {bar_w} {bh} 0 {bh}{{\\p0}}"
                )
                dialogue_lines.append(
                    f"Dialogue: 2,{_format_ass_ts(c_start)},{_format_ass_ts(c_end)},DocCitationHeader,{cid},0,0,0,,"
                    f"{{\\an7\\pos({x0 + 18},{y0 + 18}){fs1_tag}\\fad(220,280)}}{line1_txt}"
                )
                dialogue_lines.append(
                    f"Dialogue: 2,{_format_ass_ts(c_start)},{_format_ass_ts(c_end)},DocCitationBody,{cid},0,0,0,,"
                    f"{{\\an7\\pos({x0 + 18},{y0 + 54}){fs2_tag}\\fad(220,280)}}{line2_txt}"
                )
                citation_events.append(
                    {
                        "citation_id": cid,
                        "sentence_index": s_idx,
                        "start_sec": c_start,
                        "end_sec": c_end,
                        "x": x0,
                        "y_top": y0,
                        "y_bottom": y0 + bh,
                        "width_px": box_w,
                        "font_size_body": fs2,
                        "clearance_to_subtitle_px": LONGFORM_SUBTITLE_Y_RANGE[0] - (y0 + bh),
                        "line1": line1_txt,
                        "line2": line2_txt,
                    }
                )

    # 4. Optional AnatomyLabel / SplitLeft / SplitRight from visual_plan clips if timed
    sent_span_map = {int(s["sentence_index"]): (float(s["start_sec"]), float(s["end_sec"])) for s in sentence_timings if s.get("sentence_index")}
    for c_spec in (vp_doc.get("clips") or []):
        s_ids = [int(x) for x in (c_spec.get("sentence_indices") or []) if int(x) in sent_span_map]
        if not s_ids:
            continue
        c_t0 = sent_span_map[s_ids[0]][0]
        c_t1 = sent_span_map[s_ids[-1]][1]
        frac = c_spec.get("sentence_fraction") or [0.0, 1.0]
        if len(s_ids) == 1 and frac != [0.0, 1.0]:
            span_len = c_t1 - c_t0
            c_t1 = c_t0 + span_len * float(frac[1])
            c_t0 = c_t0 + span_len * float(frac[0])
        overlaps_hl = any(not (c_t1 <= hw0 or c_t0 >= hw1) for hw0, hw1 in chapter_headline_windows)
        if overlaps_hl:
            continue
        if c_spec.get("split_mode") == "split_hstack":
            l_lbl = _escape_ass_text(c_spec.get("split_left_label") or "")
            r_lbl = _escape_ass_text(c_spec.get("split_right_label") or "")
            if l_lbl:
                dialogue_lines.append(
                    f"Dialogue: 2,{_format_ass_ts(c_t0)},{_format_ass_ts(c_t1)},SplitLabel,,0,0,0,,"
                    f"{{\\an8\\pos({LONGFORM_SPLIT_LEFT_X},88)\\fad(160,160)}}{l_lbl}"
                )
            if r_lbl:
                dialogue_lines.append(
                    f"Dialogue: 2,{_format_ass_ts(c_t0)},{_format_ass_ts(c_t1)},SplitLabel,,0,0,0,,"
                    f"{{\\an8\\pos({LONGFORM_SPLIT_RIGHT_X},88)\\fad(160,160)}}{r_lbl}"
                )
        elif c_spec.get("anatomy_label"):
            anat_lbl = _escape_ass_text(c_spec["anatomy_label"])
            dialogue_lines.append(
                f"Dialogue: 2,{_format_ass_ts(c_t0)},{_format_ass_ts(c_t1)},AnatomyLabel,,0,0,0,,"
                f"{{\\an8\\pos(960,88)\\fad(180,200)}}{anat_lbl}"
            )

    ass_content = header + "\n".join(dialogue_lines) + "\n"
    ass_path.write_text(ass_content, encoding="utf-8")
    return {
        "ass_path": str(ass_path),
        "play_res": [LONGFORM_VIDEO_WIDTH, LONGFORM_VIDEO_HEIGHT],
        "subtitle_event_count": sub_count,
        "citation_card_count": len(citation_events),
        "citation_events": citation_events,
        "min_vertical_clearance_px": (
            min(e["clearance_to_subtitle_px"] for e in citation_events)
            if citation_events
            else LONGFORM_SUBTITLE_Y_RANGE[0] - (CARD_Y_TOP + CARD_HEIGHT)
        ),
    }


def render_subtitle_citation_preview_frame(
    project_id_or_dir: str | Path,
    *,
    timestamp_sec: float | None = None,
    background_png: Path | None = None,
    out_png: Path | None = None,
) -> dict[str, Any]:
    """
    Burns `04_audio/subtitles.ass` onto a `1920x1080` widescreen plate at a timestamp where both
    `DocCitationCard` and `Default` bottom subtitles are active, writing `05_assembly/preview_subtitle_citation_1920x1080.png`
    and verifying zero pixel collision across the clearance band `Y ∈ [874, 916]`.
    """
    p_dir = resolve_longform_project_dir(project_id_or_dir, create=False)
    ass_path = p_dir / "04_audio" / "subtitles.ass"
    if not ass_path.exists():
        raise FileNotFoundError(f"Missing subtitles.ass: {ass_path}")

    font_path = ensure_bundled_condensed_font(FONT_CONDENSED_BLACK_PATH)
    fonts_dir = font_path.parent

    # Auto-pick midpoint of first DocCitationBg event so both card and subtitle are guaranteed active
    ts = timestamp_sec
    if ts is None:
        ass_txt = ass_path.read_text(encoding="utf-8")
        for ln in ass_txt.splitlines():
            if ln.startswith("Dialogue:") and ",DocCitationBg," in ln:
                parts = ln.split(",", 9)
                def _parse_ts(t_s: str) -> float:
                    hh, mm, ss = t_s.strip().split(":")
                    return int(hh) * 3600 + int(mm) * 60 + float(ss)
                t0, t1 = _parse_ts(parts[1]), _parse_ts(parts[2])
                ts = round(t0 + min(1.35, 0.45 * (t1 - t0)), 2)
                break
    if ts is None:
        ts = 1.50

    out_path = Path(out_png) if out_png is not None else (p_dir / "05_assembly" / "preview_subtitle_citation_1920x1080.png")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    bg_plate: np.ndarray | None = None
    if background_png and Path(background_png).exists():
        bg_plate = cv2.imread(str(background_png))
    else:
        import json as _json

        vp_path = p_dir / "03_visuals" / "visual_plan.json"
        ref_dir = p_dir / "03_visuals" / "reference_images"
        if vp_path.exists():
            try:
                vp_doc_prev = _json.loads(vp_path.read_text(encoding="utf-8"))
                for c_sp in (vp_doc_prev.get("clips") or []):
                    t_s0 = float(c_sp.get("start_sec") or 0.0)
                    t_s1 = float(c_sp.get("end_sec") or 0.0)
                    if t_s0 <= ts <= t_s1:
                        ri_rel = str(c_sp.get("reference_image") or "").strip()
                        anc_id = str(c_sp.get("reference_anchor_id") or "").strip()
                        for cand_p in (
                            (p_dir / ri_rel) if ri_rel else None,
                            (ref_dir / f"{anc_id}.png") if anc_id else None,
                        ):
                            if cand_p and cand_p.exists():
                                im_c = cv2.imread(str(cand_p))
                                if im_c is not None and im_c.shape[1] > im_c.shape[0]:
                                    bg_plate = im_c
                                    break
                        if bg_plate is None and c_sp.get("grammar") == "porcelain_living_brain" and ref_dir.is_dir():
                            for b_cand in sorted(ref_dir.glob("*brain*.png")):
                                im_b = cv2.imread(str(b_cand))
                                if im_b is not None and im_b.shape[1] > im_b.shape[0]:
                                    bg_plate = im_b
                                    break
                        break
            except Exception:
                pass
        if bg_plate is None and ref_dir.is_dir():
            for cand in sorted(ref_dir.glob("*.png")):
                im = cv2.imread(str(cand))
                if im is not None and im.shape[1] > im.shape[0]:
                    bg_plate = im
                    break
    if bg_plate is None:
        # Clean high-key architectural porcelain gallery gradient plate
        y_grad = np.linspace(236, 198, LONGFORM_VIDEO_HEIGHT, dtype=np.float32)[:, None]
        x_grad = np.linspace(0, 12, LONGFORM_VIDEO_WIDTH, dtype=np.float32)[None, :]
        base = np.clip(y_grad - x_grad, 175, 244).astype(np.uint8)
        bg_plate = np.stack([base, base, np.clip(base + 4, 0, 250).astype(np.uint8)], axis=2)
    else:
        bg_plate = cv2.resize(bg_plate, (LONGFORM_VIDEO_WIDTH, LONGFORM_VIDEO_HEIGHT), interpolation=cv2.INTER_LANCZOS4)

    ffmpeg_bin = _resolve_ffmpeg_bin()
    with tempfile.TemporaryDirectory(prefix="aab_lf_sub_prev_") as td:
        plate_png = Path(td) / "plate.png"
        clean_ass = Path(td) / "subtitles.ass"
        f_dir = Path(td) / "fonts"
        f_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(font_path, f_dir / font_path.name)
        shutil.copy2(ass_path, clean_ass)
        cv2.imwrite(str(plate_png), bg_plate)

        vf = f"ass=filename='{clean_ass.as_posix()}':fontsdir='{f_dir.as_posix()}'"
        dur_vid = max(ts + 0.5, 3.0)
        subprocess.run(
            [
                ffmpeg_bin,
                "-nostdin",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-loop",
                "1",
                "-t",
                f"{dur_vid:.2f}",
                "-r",
                str(LONGFORM_VIDEO_FPS),
                "-i",
                str(plate_png),
                "-ss",
                f"{ts:.2f}",
                "-vf",
                vf,
                "-frames:v",
                "1",
                str(out_path),
            ],
            check=True,
            capture_output=True,
            timeout=90,
        )

    rendered = cv2.imread(str(out_path))
    if rendered is None:
        raise RuntimeError(f"Failed to render subtitle/citation preview frame: {out_path}")

    diff = np.max(np.abs(rendered.astype(np.int16) - bg_plate.astype(np.int16)), axis=2)
    card_roi_changed = float(np.mean(diff[CARD_Y_TOP : CARD_Y_TOP + CARD_HEIGHT, 96:560] > 18))
    gap_band_changed = float(np.mean(diff[CARD_Y_TOP + CARD_HEIGHT + 4 : LONGFORM_SUBTITLE_Y_RANGE[0] - 4, 96:1200] > 25))
    sub_roi_changed = float(np.mean(diff[LONGFORM_SUBTITLE_Y_RANGE[0] - 8 : LONGFORM_SUBTITLE_Y_RANGE[1] + 12, 480:1440] > 18))

    return {
        "preview_png": str(out_path),
        "timestamp_sec": ts,
        "resolution": [int(rendered.shape[1]), int(rendered.shape[0])],
        "card_roi_active_ratio": round(card_roi_changed, 4),
        "clearance_gap_band_dirty_ratio": round(gap_band_changed, 4),
        "subtitle_roi_active_ratio": round(sub_roi_changed, 4),
        "non_overlapping_verified": bool(gap_band_changed == 0.0 and (LONGFORM_SUBTITLE_Y_RANGE[0] - (CARD_Y_TOP + CARD_HEIGHT)) >= LONGFORM_CITATION_CARD_MIN_CLEARANCE_PX),
    }
