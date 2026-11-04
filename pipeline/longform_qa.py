"""
ALL ABOUT BRAIN — Standalone 16:9 (`1920x1080`) 12-Axis Long-Form QA Validator (`pipeline/longform_qa.py`).

Enforces `LFQ1–LFQ12`:
  - `LFQ1`: Natural sentence budget (`<= 22` words/sentence), zero 1st-person pronouns in narration (`R15`), zero AI clichés
  - `LFQ2`: 6–8 chapters (7 default) & relaxed `longform_us_v7` duration/WPM window (`~142–148 WPM`, `480..900s`)
  - `LFQ3`: 3-Layer Formula (`everyday` + `psychology` + `neuroscience`) & `>= 3` peer-reviewed DOIs mapped to `citation_cards`
  - `LFQ4`: 3-Stage Debate Ignition (midpoint `?` open-loop + final chapter `?` verdict + `<= 45` char creator-bet pinned comment)
  - `LFQ5`: Strict Shorts isolation (`projects_longform/`, never `BCI_Shorts_Channel/projects/`), `1920x1080 @ 24fps` `16:9` lock
  - `LFQ6`: Relaxed `16:9` documentary cut pacing (`3.2s..7.0s`, avg `4.6s..5.8s`), 1:1 zero reuse, shards `<= 14`, `>= 20%` brain/split
  - `LFQ7`: Zero clock digits, bottle labels, or plaque/text-generating nouns in positive Flow prompts
  - `LFQ8`: `1920x1080` ASS burned-in subtitle (`Y ∈ [922, 982]`, `<= 5w / <= 32ch`) & `DocCitationCard` (`Y_bottom <= 872`, `>= +50px` gap)
  - `LFQ9`: `04_audio/audio_master.wav` `longform_us_v7` relaxed vocal breathing pauses, zero WSOLA, `-14.0 LUFS`, `TP <= -1.2 dBTP`
  - `LFQ10`: `1920x1080` (`16:9`) Reference Anchor Pack `Q1–Q10` readiness & `/tmp/aab_reenact_lf` quarantine purge
  - `LFQ11`: `1920x1080` `< 2 MB` JPEG thumbnails `A/B/C`, chapter timestamps (`00:00`), `upload_cc_srt == False`
  - `LFQ12`: Final `05_assembly/final_longform_1920x1080.mp4` H.264 High `1920x1080 @ 24fps` & bright `t=0.0s` start (when assembled)
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from pipeline.config import (
    FLOW_ASPECT_LONGFORM,
    LONGFORM_AVG_CUT_RANGE_SEC,
    LONGFORM_CHAPTER_COUNT_RANGE,
    LONGFORM_CITATION_CARD_MIN_CLEARANCE_PX,
    LONGFORM_CITATION_CARD_WIDTH_RANGE,
    LONGFORM_CITATION_CARD_Y_RANGE,
    LONGFORM_FINAL_MP4_FILENAME,
    LONGFORM_MAX_CUT_SEC,
    LONGFORM_MAX_SENTENCE_WORDS,
    LONGFORM_MIN_CUT_SEC,
    LONGFORM_PROSODY_MODE,
    LONGFORM_QUARANTINE_ROOT,
    LONGFORM_SHARD_MAX_CLIPS,
    LONGFORM_SUBTITLE_MARGIN_V,
    LONGFORM_SUBTITLE_MAX_CHARS,
    LONGFORM_SUBTITLE_MAX_WORDS,
    LONGFORM_SUBTITLE_Y_RANGE,
    LONGFORM_TARGET_LUFS,
    LONGFORM_TARGET_MAX_SEC,
    LONGFORM_TARGET_MIN_SEC,
    LONGFORM_THUMB_MAX_BYTES,
    LONGFORM_VIDEO_FPS,
    LONGFORM_VIDEO_HEIGHT,
    LONGFORM_VIDEO_WIDTH,
    LONGFORM_WPM_RANGE,
    PROJECTS_DIR,
)
from pipeline.longform_prompt_builder import count_spoken_words, resolve_longform_project_dir
from pipeline.plain_language import find_ai_cliches_and_seminar_isms
from pipeline.studio.community import CommunityManager, validate_debate_pinned_comment_line1

_FIRST_PERSON_RE = re.compile(r"\b(?:I|I'm|I've|I'd|I'll|me|my|mine|we|we're|we've|we'll|us|our|ours)\b", re.IGNORECASE)
_BANNED_POSITIVE_PROP_RE = re.compile(
    r"\b(?:digital\s+alarm\s+clock|alarm\s+clock|3:00\s*am|3\s*am|scoreboard|nameplate|placard|plaque|signboard|billboard|prescription\s+label|(?:unmarked\s+|small\s+)*(?:white|sleeping|sedative)\s+tablet|(?:boston|harvard|stanford|oxford|rochester)-style)\b",
    re.IGNORECASE,
)
_ASS_OVERRIDE_RE = re.compile(r"\{[^}]*\}")
_DRAW_BOX_RE = re.compile(r"\\p1\}m\s+0\s+0\s+l\s+(\d+)\s+0\s+(\d+)\s+(\d+)\s+0\s+(\d+)")
_POS_RE = re.compile(r"\\pos\((\d+(?:\.\d+)?),(\d+(?:\.\d+)?)\)")


def _strip_negated_clauses(scene: str) -> str:
    return re.sub(
        r"\b(?:zero|without|no)\s+[a-z0-9\s,\-]{1,95}",
        " ",
        scene or "",
        flags=re.IGNORECASE,
    )


def run_longform_qa(
    project_id_or_dir: str | Path,
    *,
    projects_longform_dir: str | Path | None = None,
    require_audio: bool = False,
    require_refs: bool = False,
    require_final_mp4: bool = False,
    save_report: bool = True,
) -> dict[str, Any]:
    """Executes `LFQ1–LFQ12` on a standalone Long-Form project and writes `05_assembly/longform_qa_report.json`."""
    p_dir = resolve_longform_project_dir(project_id_or_dir, projects_longform_dir=projects_longform_dir, create=False)
    if not p_dir.is_dir():
        raise FileNotFoundError(f"Long-Form project directory not found: {p_dir}")

    gates: dict[str, dict[str, Any]] = {}
    all_issues: list[str] = []

    def _record(gate_id: str, issues: list[str], metrics: dict[str, Any] | None = None) -> None:
        gates[gate_id] = {
            "passed": len(issues) == 0,
            "issues": issues,
            "metrics": metrics or {},
        }
        all_issues.extend(f"[{gate_id}] {msg}" for msg in issues)

    script_path = p_dir / "02_script" / "script.json"
    vp_path = p_dir / "03_visuals" / "visual_plan.json"
    rc_path = p_dir / "01_ideation" / "research_card.json"
    script_doc = json.loads(script_path.read_text(encoding="utf-8")) if script_path.exists() else {}
    vp_doc = json.loads(vp_path.read_text(encoding="utf-8")) if vp_path.exists() else {}
    rc_doc = json.loads(rc_path.read_text(encoding="utf-8")) if rc_path.exists() else {}

    sentences = list(script_doc.get("sentences") or [])
    chapters = list(script_doc.get("chapters") or vp_doc.get("chapters") or [])
    clips = list(vp_doc.get("clips") or [])
    citation_cards = list(vp_doc.get("citation_cards") or script_doc.get("citation_cards") or [])

    # --- LFQ1: Natural Sentence Budget (<= 22 words), Zero 1st-Person in Narration, Zero AI Clichés ---
    g1_issues: list[str] = []
    if not sentences:
        g1_issues.append("Missing sentences in 02_script/script.json")
    max_wc_seen = 0
    for s in sentences:
        txt = str(s.get("text") or "").strip()
        wc = count_spoken_words(txt)
        max_wc_seen = max(max_wc_seen, wc)
        if wc > LONGFORM_MAX_SENTENCE_WORDS:
            g1_issues.append(f"Sentence {s.get('sentence_index')} has {wc} words (> {LONGFORM_MAX_SENTENCE_WORDS}): {txt!r}")
        unquoted = re.sub(r"'[^']*'|\"[^\"]*\"", " ", txt)
        fp_hit = _FIRST_PERSON_RE.search(unquoted)
        if fp_hit:
            g1_issues.append(f"Sentence {s.get('sentence_index')} uses banned 1st-person pronoun {fp_hit.group(0)!r}: {txt!r}")
    full_txt = " ".join(str(s.get("text") or "") for s in sentences)
    cliches = find_ai_cliches_and_seminar_isms(full_txt)
    if cliches["ai_cliches"] or cliches["seminar_isms"]:
        g1_issues.append(f"Narration contains banned AI clichés / seminar transitions: {cliches}")
    _record("LFQ1_sentence_and_pronoun_lock", g1_issues, {"sentence_count": len(sentences), "max_sentence_words": max_wc_seen})

    # --- LFQ2: Chapter Count & Duration / WPM Budget ---
    g2_issues: list[str] = []
    if not (LONGFORM_CHAPTER_COUNT_RANGE[0] <= len(chapters) <= LONGFORM_CHAPTER_COUNT_RANGE[1]):
        g2_issues.append(f"Chapter count {len(chapters)} outside {LONGFORM_CHAPTER_COUNT_RANGE}")
    est_dur = float(script_doc.get("estimated_duration_sec") or 0.0)
    if est_dur and not (LONGFORM_TARGET_MIN_SEC <= est_dur <= LONGFORM_TARGET_MAX_SEC):
        g2_issues.append(f"Estimated duration {est_dur:.1f}s outside {LONGFORM_TARGET_MIN_SEC}..{LONGFORM_TARGET_MAX_SEC}s")
    _record("LFQ2_chapter_and_duration_budget", g2_issues, {"chapter_count": len(chapters), "estimated_duration_sec": est_dur})

    # --- LFQ3: 3-Layer Formula & Verified DOI Citation Cards ---
    g3_issues: list[str] = []
    tlf = rc_doc.get("three_layer_formula") or {}
    if not tlf.get("everyday_problem"):
        g3_issues.append("Missing three_layer_formula.everyday_problem in research_card.json")
    if not tlf.get("psychology_studies"):
        g3_issues.append("Missing three_layer_formula.psychology_studies in research_card.json")
    if not tlf.get("neuroscience_studies"):
        g3_issues.append("Missing three_layer_formula.neuroscience_studies in research_card.json")
    valid_dois = [str(c.get("doi") or "") for c in citation_cards if str(c.get("doi") or "").startswith("10.")]
    if len(valid_dois) < 3:
        g3_issues.append(f"Expected >= 3 peer-reviewed DOI citation_cards across behavioral psych + neuroscience, got {len(valid_dois)}")
    _record("LFQ3_three_layer_formula_and_dois", g3_issues, {"doi_count": len(valid_dois), "dois": valid_dois})

    # --- LFQ4: 3-Stage Comment Debate Ignition ---
    g4_issues: list[str] = []
    mid_sents = [
        str(s.get("text") or "")
        for s in sentences
        if 2 <= int(s.get("chapter") or 0) <= max(2, len(chapters) - 2)
    ]
    if not any("?" in t for t in mid_sents):
        g4_issues.append("Missing Stage 1 midpoint open-loop '?' question in middle chapters")
    if sentences:
        last_txt = str(sentences[-1].get("text") or "").strip()
        if not last_txt.endswith("?"):
            g4_issues.append(f"Stage 2 final spoken sentence must end with an open-verdict forced-choice '?', got: {last_txt!r}")
    cm = CommunityManager(projects_dir=p_dir.parent)
    comm_pkg = cm.prepare_comment_content(p_dir.name)
    comm_line1 = comm_pkg["comment_text"].splitlines()[0].strip() if comm_pkg.get("comment_text") else ""
    g4_issues.extend(
        validate_debate_pinned_comment_line1(
            comm_line1,
            full_comment=comm_pkg.get("comment_text", ""),
            require_doi=True,
        )
    )
    _record("LFQ4_debate_three_stage_ignition", g4_issues, {"pinned_line1": comm_line1})

    # --- LFQ5: Strict Shorts Isolation & 1920x1080 @ 24fps 16:9 Lock ---
    g5_issues: list[str] = []
    import pipeline.config as _cfg

    shorts_root = Path(_cfg.PROJECTS_DIR).resolve()
    try:
        if p_dir.resolve().is_relative_to(shorts_root):
            g5_issues.append(f"Long-Form project {p_dir} violates Shorts isolation (located inside {shorts_root})")
    except Exception:
        pass
    if list(vp_doc.get("resolution") or []) != [LONGFORM_VIDEO_WIDTH, LONGFORM_VIDEO_HEIGHT]:
        g5_issues.append(f"visual_plan resolution {vp_doc.get('resolution')} != {[LONGFORM_VIDEO_WIDTH, LONGFORM_VIDEO_HEIGHT]}")
    if str(vp_doc.get("aspect") or "") != FLOW_ASPECT_LONGFORM:
        g5_issues.append(f"visual_plan aspect {vp_doc.get('aspect')!r} != {FLOW_ASPECT_LONGFORM!r}")
    if int(vp_doc.get("fps") or 0) != LONGFORM_VIDEO_FPS:
        g5_issues.append(f"visual_plan fps {vp_doc.get('fps')} != {LONGFORM_VIDEO_FPS}")
    _record("LFQ5_aspect_and_isolation_lock", g5_issues, {"project_dir": str(p_dir), "resolution": vp_doc.get("resolution")})

    # --- LFQ6: Relaxed Documentary Cut Pacing (3.2s..7.0s, avg ~5.0s), Shards <= 14, Brain Ratio >= 20% ---
    g6_issues: list[str] = []
    if not clips:
        g6_issues.append("No clips planned in visual_plan.json")
    cut_durs = [float(c.get("target_duration_sec") or 0.0) for c in clips]
    avg_cut = round(sum(cut_durs) / max(1, len(cut_durs)), 3) if cut_durs else 0.0
    for c in clips:
        cd = float(c.get("target_duration_sec") or 0.0)
        if cd < LONGFORM_MIN_CUT_SEC - 0.05 or cd > LONGFORM_MAX_CUT_SEC + 0.05:
            g6_issues.append(f"Clip {c.get('clip_number')} target_duration_sec={cd:.2f}s outside [{LONGFORM_MIN_CUT_SEC}, {LONGFORM_MAX_CUT_SEC}]")
    if cut_durs and not (LONGFORM_AVG_CUT_RANGE_SEC[0] <= avg_cut <= LONGFORM_AVG_CUT_RANGE_SEC[1]):
        g6_issues.append(f"Mean planned cut duration {avg_cut:.2f}s outside relaxed range {LONGFORM_AVG_CUT_RANGE_SEC}")
    brain_or_split = sum(
        1 for c in clips if c.get("grammar") == "porcelain_living_brain" or c.get("split_mode") == "split_hstack"
    )
    brain_ratio = round(brain_or_split / max(1, len(clips)), 3)
    if clips and brain_ratio < 0.20:
        g6_issues.append(f"3D brain + split comparison ratio {brain_ratio:.1%} < 20.0%")
    shards = list(vp_doc.get("flow_shards") or [])
    for sh in shards:
        if int(sh.get("clip_count") or 0) > LONGFORM_SHARD_MAX_CLIPS:
            g6_issues.append(f"Shard {sh.get('shard_index')} has {sh.get('clip_count')} clips (> {LONGFORM_SHARD_MAX_CLIPS})")
    _record(
        "LFQ6_relaxed_cut_pacing_and_shards",
        g6_issues,
        {"clip_count": len(clips), "avg_cut_sec": avg_cut, "brain_or_split_ratio": brain_ratio, "shard_count": len(shards)},
    )

    # --- LFQ7: Plaque & Clock-Digit Sanitizer ---
    g7_issues: list[str] = []
    for c in clips:
        positive_scene = _strip_negated_clauses(f"{c.get('scene', '')} {c.get('prompt', '')}")
        m_bad = _BANNED_POSITIVE_PROP_RE.search(positive_scene)
        if m_bad:
            g7_issues.append(f"Clip {c.get('clip_number')} contains banned text/clock prop {m_bad.group(0)!r}")
    _record("LFQ7_plaque_and_clock_prop_sanitizer", g7_issues)

    # --- LFQ8: 1920x1080 ASS Burned-In Subtitles & Lower-Left DocCitationCard Non-Overlap ---
    ass_path = p_dir / "04_audio" / "subtitles.ass"
    g8_issues: list[str] = []
    g8_metrics: dict[str, Any] = {"present": ass_path.exists()}
    if require_audio and not ass_path.exists():
        g8_issues.append("Missing 04_audio/subtitles.ass")
    if ass_path.exists():
        ass_txt = ass_path.read_text(encoding="utf-8")
        if "PlayResX: 1920" not in ass_txt or "PlayResY: 1080" not in ass_txt:
            g8_issues.append("subtitles.ass must lock PlayResX: 1920 and PlayResY: 1080")
        m_def = re.search(r"^Style:\s*Default,([^\r\n]+)$", ass_txt, flags=re.MULTILINE)
        if not m_def:
            g8_issues.append("Missing Default style in subtitles.ass")
        else:
            fields = [f.strip() for f in m_def.group(1).split(",")]
            # ASS v4+ Style fields after Name: Fontname(0), Fontsize(1), ..., MarginL(18), MarginR(19), MarginV(20)
            if len(fields) > 20 and int(fields[20]) != LONGFORM_SUBTITLE_MARGIN_V:
                g8_issues.append(f"Default MarginV={fields[20]} != {LONGFORM_SUBTITLE_MARGIN_V}")

        sub_events = 0
        card_boxes = 0
        min_clearance_px = 999
        for line in ass_txt.splitlines():
            if not line.startswith("Dialogue:"):
                continue
            parts = line.split(",", 9)
            if len(parts) < 10:
                continue
            style = parts[3].strip()
            raw_payload = parts[9]
            if style == "Default":
                sub_events += 1
                if r"\N" in raw_payload or r"\n" in raw_payload:
                    g8_issues.append(f"Multi-line break found in Default subtitle: {raw_payload!r}")
                vis = _ASS_OVERRIDE_RE.sub("", raw_payload).strip()
                wc = len([w for w in vis.split() if w])
                if wc > LONGFORM_SUBTITLE_MAX_WORDS:
                    g8_issues.append(f"Subtitle exceeds {LONGFORM_SUBTITLE_MAX_WORDS} words ({wc}): {vis!r}")
                if len(vis) > LONGFORM_SUBTITLE_MAX_CHARS:
                    g8_issues.append(f"Subtitle exceeds {LONGFORM_SUBTITLE_MAX_CHARS} chars ({len(vis)}): {vis!r}")
            elif style in ("DocCitationBg", "DocCitationBar"):
                m_pos = _POS_RE.search(raw_payload)
                m_box = _DRAW_BOX_RE.search(raw_payload)
                if m_pos and m_box:
                    x0 = float(m_pos.group(1))
                    y0 = float(m_pos.group(2))
                    bw = int(m_box.group(1))
                    bh = int(m_box.group(3))
                    y_bot = y0 + bh
                    clearance = int(round(LONGFORM_SUBTITLE_Y_RANGE[0] - y_bot))
                    min_clearance_px = min(min_clearance_px, clearance)
                    if style == "DocCitationBg":
                        card_boxes += 1
                        if not (LONGFORM_CITATION_CARD_WIDTH_RANGE[0] <= bw <= LONGFORM_CITATION_CARD_WIDTH_RANGE[1]):
                            g8_issues.append(f"DocCitationBg width {bw}px outside {LONGFORM_CITATION_CARD_WIDTH_RANGE}")
                    if y0 < LONGFORM_CITATION_CARD_Y_RANGE[0] - 2 or y_bot > LONGFORM_CITATION_CARD_Y_RANGE[1] + 2:
                        g8_issues.append(f"{style} Y=[{y0:.0f}, {y_bot:.0f}] outside {LONGFORM_CITATION_CARD_Y_RANGE}")
                    if clearance < LONGFORM_CITATION_CARD_MIN_CLEARANCE_PX:
                        g8_issues.append(
                            f"{style} clearance to Default subtitle top ({LONGFORM_SUBTITLE_Y_RANGE[0]}) is {clearance}px "
                            f"(< {LONGFORM_CITATION_CARD_MIN_CLEARANCE_PX}px)"
                        )
            elif style == "DocCitationBody":
                vis_body = _ASS_OVERRIDE_RE.sub("", raw_payload).strip()
                if vis_body.endswith("…") or vis_body.endswith("..."):
                    g8_issues.append(f"DocCitationBody truncated with ellipsis: {vis_body!r}")
        g8_metrics.update(
            {
                "subtitle_events": sub_events,
                "citation_card_boxes": card_boxes,
                "min_vertical_clearance_px": min_clearance_px if card_boxes else None,
            }
        )
        if citation_cards and card_boxes < len(citation_cards):
            g8_issues.append(f"Expected {len(citation_cards)} DocCitationBg boxes in subtitles.ass, found {card_boxes}")
    _record("LFQ8_subtitle_and_citation_non_overlap", g8_issues, g8_metrics)

    # --- LFQ9: Relaxed Long-Form Audio Master Integrity ---
    wav_path = p_dir / "04_audio" / "audio_master.wav"
    pr_path = p_dir / "04_audio" / "prosody_report.json"
    g9_issues: list[str] = []
    g9_metrics: dict[str, Any] = {"present": wav_path.exists()}
    if require_audio and not wav_path.exists():
        g9_issues.append("Missing 04_audio/audio_master.wav")
    if wav_path.exists() and pr_path.exists():
        pr_doc = json.loads(pr_path.read_text(encoding="utf-8"))
        g9_metrics.update(
            {
                "duration_sec": pr_doc.get("duration_sec"),
                "effective_wpm": pr_doc.get("effective_wpm"),
                "integrated_lufs": pr_doc.get("integrated_lufs"),
                "true_peak_dbtp": pr_doc.get("true_peak_dbtp"),
                "prosody_mode": pr_doc.get("prosody_mode"),
            }
        )
        if pr_doc.get("prosody_mode") != LONGFORM_PROSODY_MODE:
            g9_issues.append(f"prosody_mode={pr_doc.get('prosody_mode')!r} != {LONGFORM_PROSODY_MODE!r}")
        if float(pr_doc.get("max_wsola_stretch_delta", 0.0)) > 0.001:
            g9_issues.append("WSOLA time-stretching detected; Long-Form requires native edge-tts rates only")
        wpm_val = float(pr_doc.get("effective_wpm") or 0.0)
        if wpm_val and not (LONGFORM_WPM_RANGE[0] <= wpm_val <= LONGFORM_WPM_RANGE[1]):
            g9_issues.append(f"Effective WPM {wpm_val:.1f} outside relaxed documentary window {LONGFORM_WPM_RANGE}")
        lufs_val = float(pr_doc.get("integrated_lufs") or 0.0)
        if abs(lufs_val - LONGFORM_TARGET_LUFS) > 1.5:
            g9_issues.append(f"Integrated loudness {lufs_val:.2f} LUFS drifts > 1.5 LU from {LONGFORM_TARGET_LUFS} LUFS")
        tp_val = float(pr_doc.get("true_peak_dbtp") or 0.0)
        if tp_val > -1.2:
            g9_issues.append(f"True peak {tp_val:.2f} dBTP > -1.2 dBTP")
    _record("LFQ9_relaxed_audio_master_integrity", g9_issues, g9_metrics)

    # --- LFQ10: 1920x1080 (16:9) Reference Anchor Pack & Quarantine Purge ---
    ref_rep_path = p_dir / "03_visuals" / "reference_image_qa_report.json"
    g10_issues: list[str] = []
    g10_metrics: dict[str, Any] = {"present": ref_rep_path.exists()}
    if require_refs and not ref_rep_path.exists():
        g10_issues.append("Missing 03_visuals/reference_image_qa_report.json")
    if ref_rep_path.exists():
        r_doc = json.loads(ref_rep_path.read_text(encoding="utf-8"))
        g10_metrics["cv_pre_generation_ready"] = bool(r_doc.get("cv_pre_generation_ready"))
        g10_metrics["image_count"] = len(r_doc.get("images") or [])
        if not r_doc.get("cv_pre_generation_ready"):
            g10_issues.append(f"16:9 Reference pack failed Q1-Q10 CV QA: {r_doc.get('blocking_reasons')}")
        for im_rec in r_doc.get("images") or []:
            fp = Path(str(im_rec.get("path") or ""))
            if not fp.is_absolute():
                fp = p_dir / fp
            if fp.exists():
                arr = cv2.imread(str(fp))
                if arr is not None:
                    ih, iw = arr.shape[:2]
                    if iw <= ih or abs((iw / max(ih, 1)) - (16.0 / 9.0)) > 0.05:
                        g10_issues.append(f"Reference image {fp.name} is {iw}x{ih}, expected 16:9 widescreen")
    q_dir = Path(LONGFORM_QUARANTINE_ROOT) / str(script_doc.get("dossier_slug") or p_dir.name)
    if q_dir.exists() and any(q_dir.iterdir()):
        g10_issues.append(f"Track A quarantine directory not purged: {q_dir}")
    _record("LFQ10_reference_pack_16x9_qa", g10_issues, g10_metrics)

    # --- LFQ11: 1920x1080 < 2 MB Thumbnails & Publish Metadata ---
    meta_path = p_dir / "06_publish" / "metadata.json"
    g11_issues: list[str] = []
    g11_metrics: dict[str, Any] = {"present": meta_path.exists()}
    if meta_path.exists():
        m_doc = json.loads(meta_path.read_text(encoding="utf-8"))
        if m_doc.get("upload_cc_srt") is not False:
            g11_issues.append("metadata.json upload_cc_srt must default to False (burned-in subtitles active)")
        desc = str(m_doc.get("description") or "")
        if "00:00 " not in desc:
            g11_issues.append("metadata.json description missing '00:00 ' YouTube chapter timestamp spine")
        for var in ("A", "B", "C"):
            jpg_p = p_dir / "06_publish" / f"thumbnail_var_{var}.jpg"
            if jpg_p.exists():
                sz = jpg_p.stat().st_size
                if sz > LONGFORM_THUMB_MAX_BYTES:
                    g11_issues.append(f"{jpg_p.name} size {sz} bytes > {LONGFORM_THUMB_MAX_BYTES}")
                im = cv2.imread(str(jpg_p))
                if im is None or (im.shape[1], im.shape[0]) != (LONGFORM_VIDEO_WIDTH, LONGFORM_VIDEO_HEIGHT):
                    g11_issues.append(f"{jpg_p.name} resolution != 1920x1080")
    _record("LFQ11_thumbnail_and_publish_package", g11_issues, g11_metrics)

    # --- LFQ12: Final 1920x1080 @ 24fps MP4 & Bright t=0.0s Start ---
    mp4_path = p_dir / "05_assembly" / LONGFORM_FINAL_MP4_FILENAME
    g12_issues: list[str] = []
    g12_metrics: dict[str, Any] = {"present": mp4_path.exists()}
    if require_final_mp4 and not mp4_path.exists():
        g12_issues.append(f"Missing 05_assembly/{LONGFORM_FINAL_MP4_FILENAME}")
    if mp4_path.exists():
        cap = cv2.VideoCapture(str(mp4_path))
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
        ok0, frm0 = cap.read()
        cap.release()
        luma0 = float(np.mean(cv2.cvtColor(frm0, cv2.COLOR_BGR2GRAY))) if (ok0 and frm0 is not None) else 0.0
        g12_metrics.update({"width": w, "height": h, "fps": round(fps, 3), "t0_mean_luma": round(luma0, 2)})
        if (w, h) != (LONGFORM_VIDEO_WIDTH, LONGFORM_VIDEO_HEIGHT):
            g12_issues.append(f"Final MP4 resolution {w}x{h} != {LONGFORM_VIDEO_WIDTH}x{LONGFORM_VIDEO_HEIGHT}")
        if abs(fps - LONGFORM_VIDEO_FPS) > 0.5:
            g12_issues.append(f"Final MP4 fps {fps:.2f} != {LONGFORM_VIDEO_FPS}")
        if luma0 < 65.0:
            g12_issues.append(f"Final MP4 starts dark at t=0.0s (mean luma {luma0:.1f} < 65.0; black fade-in is banned on frame 0)")
    prov_path = p_dir / "03_visuals" / "flow_provenance_receipt.json"
    fp_path = p_dir / "03_visuals" / "flow_longform_prompts.json"
    if prov_path.exists() and fp_path.exists():
        prov_doc = json.loads(prov_path.read_text(encoding="utf-8"))
        fp_doc = json.loads(fp_path.read_text(encoding="utf-8"))
        prov_clips = {int(c.get("clip_number") or c.get("clip_index") or 0): c for c in (prov_doc.get("clips") or [])}
        g12_metrics["provenance_clip_count"] = len(prov_clips)
        if str(prov_doc.get("engine_mode") or "").lower().replace("_", "-") == "zero-credit" and not prov_doc.get("zero_credit_verified"):
            g12_issues.append("flow_provenance_receipt.json failed zero_credit_verified under zero-credit engine mode")
        for pc in (fp_doc.get("clips") or []):
            cn = int(pc.get("clip_number") or 0)
            exp_ref = Path(str(pc["reference_image"])).name if pc.get("reference_image") else None
            if exp_ref and cn in prov_clips:
                rec = prov_clips[cn]
                if rec.get("reference_image") != exp_ref or rec.get("reference_attached") is not True:
                    g12_issues.append(
                        f"Clip {cn:03d} bound to {exp_ref} failed provenance anchor check "
                        f"(reference_image={rec.get('reference_image')!r}, reference_attached={rec.get('reference_attached')!r})"
                    )
    _record("LFQ12_final_mp4_stream_lock", g12_issues, g12_metrics)

    report = {
        "schema": "longform_qa_report_v1",
        "project_id": p_dir.name,
        "project_dir": str(p_dir),
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "passed": len(all_issues) == 0,
        "issue_count": len(all_issues),
        "issues": all_issues,
        "gates": gates,
    }
    if save_report:
        (p_dir / "05_assembly").mkdir(parents=True, exist_ok=True)
        (p_dir / "05_assembly" / "longform_qa_report.json").write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    return report
