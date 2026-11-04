"""
ALL ABOUT BRAIN — Standalone 16:9 (`1920x1080 @ 24fps`) Long-Form Plan & Prompt Builder (`pipeline/longform_prompt_builder.py`).

100% isolated from the `9:16` Shorts pipeline (`BCI_Shorts_Channel/projects/`).
Stores standalone Long-Form documentary episodes strictly under `BCI_Shorts_Channel/projects_longform/<project_id>/`,
combining:
  - 3-Layer Topic Formula (5 Everyday Domains × Behavioral Psychology × Circuit Neuroscience)
  - Relaxed Long-Form Vocal Delivery (`longform_us_v7`, `emma_v7`, `~142–148 WPM`, natural breathing pauses)
  - Flowing Documentary Sentences (`<= 22` words/sentence, chunked `<= 5` words in `1920x1080` ASS subtitles)
  - Relaxed `16:9` Documentary Cut Pacing (`3.2s..7.0s`, `~5.0s` average, `~95–108` unique 1:1 clips)
  - Hybrid `Track A` (`R67` academic/experiment composition reenactment) + `Track B` (`1920x1080` master anchors)
  - 3-Stage Comment Debate Ignition (midpoint open-loop `?` + Act/Chapter 7 forced-choice `?` + `<= 45` char creator bet)
"""

from __future__ import annotations

import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pipeline.config import (
    DOSSIERS_DIR,
    FLOW_ASPECT_LONGFORM,
    LONGFORM_AVG_CUT_RANGE_SEC,
    LONGFORM_AVG_CUT_TARGET_SEC,
    LONGFORM_BEAT_PAUSE_SEC,
    LONGFORM_CHAPTER_FADE_SEC,
    LONGFORM_CHAPTER_PAUSE_SEC,
    LONGFORM_DEFAULT_VOICE_PRESET,
    LONGFORM_INTER_SENTENCE_PAUSE_SEC,
    LONGFORM_MAX_CUT_SEC,
    LONGFORM_MAX_SENTENCE_WORDS,
    LONGFORM_MIN_CUT_SEC,
    LONGFORM_OUTRO_SWELL_SEC,
    LONGFORM_PRODUCTION_PROFILE,
    LONGFORM_PROJECTS_DIR,
    LONGFORM_PROSODY_GEAR_RATES,
    LONGFORM_PROSODY_MODE,
    LONGFORM_RUSH_PAUSE_SEC,
    LONGFORM_SHARD_MAX_CLIPS,
    LONGFORM_TARGET_LUFS,
    LONGFORM_UPLOAD_CC_SRT_DEFAULT,
    LONGFORM_VIDEO_FPS,
    LONGFORM_VIDEO_HEIGHT,
    LONGFORM_VIDEO_WIDTH,
    PORCELAIN_V7_OPTICS_LOCK,
    PORCELAIN_V7_STYLE_PROFILE,
    PORCELAIN_V7_WORLD_STYLE,
    PROJECTS_DIR,
)
from pipeline.knowledge_hub import query_knowledge_base

LONGFORM_STAGE_DIRS: tuple[str, ...] = (
    "01_ideation",
    "02_script",
    "03_visuals",
    "04_audio",
    "05_assembly",
    "06_publish",
)

LONGFORM_ALLOWED_CAMERAS: tuple[str, ...] = (
    "locked_tripod",
    "gentle_push_in",
    "slow_lateral_slider",
    "macro_rack_focus",
    "orbital_3d_arc_sweep",
    "overhead_top_down",
    "gentle_pull_back",
)

_CLOCK_AND_PLAQUE_SANITIZE_RULES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bdigital\s+(?:alarm\s+)?clock\b", re.IGNORECASE), "unmarked warm brass bedside timepiece without numerals"),
    (re.compile(r"\balarm\s+clock\b", re.IGNORECASE), "unmarked warm brass bedside bell timepiece without numerals"),
    (re.compile(r"\b3(?::00)?\s*a\.?m\.?\b", re.IGNORECASE), "deep pre-dawn night"),
    (re.compile(r"\bglowing\s+(?:red\s+|green\s+|blue\s+)?(?:numbers|digits|numerals)\b", re.IGNORECASE), "soft unmarked amber indicator glow"),
    (re.compile(r"\b(?:pill|prescription|medicine)\s+bottle\s+with\s+label\b", re.IGNORECASE), "unlabeled frosted amber apothecary glass vial"),
    (re.compile(r"\blabeled\s+(?:pill\s+|medicine\s+)?(?:bottle|vial|jar|box)\b", re.IGNORECASE), "unlabeled frosted glass vial"),
    (re.compile(r"\bprescription\s+label\b", re.IGNORECASE), "smooth blank ceramic tray"),
    (re.compile(r"\b(?:scoreboard|nameplate|placard|plaque|signboard|banner|poster|billboard)\b", re.IGNORECASE), "clean unmarked architectural panel"),
    (re.compile(r"\b(?:text|words|letters|numbers|digits|captions|subtitles)\s+on\s+(?:the\s+)?(?:screen|monitor|wall|display)\b", re.IGNORECASE), "clean abstract waveform waveforms without characters on the display"),
    (re.compile(r"\bcalendar\b", re.IGNORECASE), "unmarked walnut wall grid"),
    (re.compile(r"\bstopwatch\b", re.IGNORECASE), "unmarked brass balance wheel"),
    (
        re.compile(r"\b(?:unmarked\s+|small\s+|round\s+|tiny\s+)*(?:white|sleeping|sedative|oral)\s+tablet\b", re.IGNORECASE),
        "small round unmarked white sleep capsule",
    ),
    (
        re.compile(r"\b(?:boston|harvard|stanford|oxford|rochester)-style\b", re.IGNORECASE),
        "university research",
    ),
)


def resolve_longform_project_dir(
    project_id_or_dir: str | Path,
    *,
    projects_longform_dir: str | Path | None = None,
    create: bool = False,
) -> Path:
    """
    Resolves a standalone Long-Form project directory strictly under `projects_longform/`
    when creating new episodes, with read/assemble fallback to an explicit path or hermetic test dir.
    """
    raw_str = str(project_id_or_dir).strip()
    cand_path = Path(raw_str)
    if cand_path.is_absolute() or "/" in raw_str or "\\" in raw_str:
        if create:
            for st in LONGFORM_STAGE_DIRS:
                (cand_path / st).mkdir(parents=True, exist_ok=True)
        return cand_path

    import pipeline.config as _cfg

    lf_root = Path(projects_longform_dir) if projects_longform_dir is not None else Path(_cfg.LONGFORM_PROJECTS_DIR)
    lf_dir = lf_root / raw_str
    if lf_dir.is_dir() or create:
        if create:
            for st in LONGFORM_STAGE_DIRS:
                (lf_dir / st).mkdir(parents=True, exist_ok=True)
        return lf_dir

    # Hermetic unit-test fallback ONLY if caller staged native clips under a monkeypatched PROJECTS_DIR
    legacy_dir = Path(_cfg.PROJECTS_DIR) / raw_str
    if (legacy_dir / "03_visuals" / "flow_native_clips").is_dir():
        return legacy_dir

    return lf_dir


def sanitize_longform_scene_props(scene_text: str) -> str:
    """Removes clock digits, bottle labels, and text-triggering props from 16:9 Flow scene descriptions."""
    cleaned = str(scene_text or "").strip()
    for pat, repl in _CLOCK_AND_PLAQUE_SANITIZE_RULES:
        cleaned = pat.sub(repl, cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip().rstrip(".")
    return cleaned


def build_longform_16x9_flow_prompt(clip_spec: dict[str, Any]) -> str:
    """
    Renders a single `16:9` (`1920x1080`) `porcelain_cinematic_v7` Google Flow video prompt
    with zero spoken dialogue (narration is mastered separately via `longform_audio.py`) and zero in-scene text.
    """
    grammar = str(clip_spec.get("grammar") or "porcelain_fullbleed_world").strip()
    camera = str(clip_spec.get("camera") or "locked_tripod").strip()
    if camera not in LONGFORM_ALLOWED_CAMERAS:
        camera = "gentle_push_in"
    cam_phrase = camera.replace("_", " ")
    clean_scene = sanitize_longform_scene_props(str(clip_spec.get("scene") or clip_spec.get("beat_summary") or ""))

    prefix = (
        "Generate a 16:9 horizontal widescreen documentary video clip "
        "(silent cinematic 24fps motion only, zero spoken voiceover, zero on-screen text):"
    )
    if grammar == "porcelain_living_brain":
        brain_mode = str(clip_spec.get("brain_mode") or "sagittal_coronal_cutaway").replace("_", " ")
        body = (
            f"Inside a bright minimalist white architectural gallery, a Contained Living 4-Color 3D Brain model "
            f"({brain_mode}) rests on a matte-white pedestal with enclosed internal subsurface luminescence "
            f"(electric cyan-blue active pathways, crimson-red stress/blockade nodes, warm amber-gold regulation hubs, "
            f"and pearl-aqua cerebrospinal fluid waves strictly inside translucent anatomical vessels, zero uncontained neon-green particle mist). "
            f"{clean_scene}. Camera: smooth {cam_phrase}. {PORCELAIN_V7_OPTICS_LOCK}."
        )
    elif grammar in ("porcelain_hands_closeup", "porcelain_pov_hands"):
        body = (
            f"Widescreen 16:9 macro documentary tabletop close-up in a {PORCELAIN_V7_WORLD_STYLE} focusing strictly on "
            f"articulated matte-white porcelain hands and forearms in clean tailored fabric sleeves "
            f"(zero disembodied heads, skulls, busts, or electronic screen devices in frame). "
            f"{clean_scene}. Camera: smooth {cam_phrase}. {PORCELAIN_V7_OPTICS_LOCK}."
        )
    else:
        body = (
            f"Widescreen 16:9 architectural documentary scene in a {PORCELAIN_V7_WORLD_STYLE} featuring "
            f"clothed articulated matte-white porcelain figures with completely smooth featureless blank oval matte-white heads "
            f"(zero eyes, zero nose, zero mouth, zero sculpted facial features) and expressive articulated hands. "
            f"{clean_scene}. Camera: smooth {cam_phrase}. {PORCELAIN_V7_OPTICS_LOCK}."
        )
    safety_tail = (
        "Zero visible text, numbers, letters, clock digits, labels, captions, facial features, or human flesh anywhere in frame."
    )
    return f"{prefix} {body} {safety_tail}"


def count_spoken_words(sentence: str) -> int:
    tokens = [t for t in re.split(r"\s+", (sentence or "").strip()) if re.search(r"[A-Za-z0-9]", t)]
    return len(tokens)


def estimate_sentence_duration_sec(text: str, gear: str = "explain", beat_break: bool = False, chapter_end: bool = False) -> float:
    """Estimates spoken duration + natural breathing pause under `longform_us_v7` (`~145 WPM` effective)."""
    words = max(1, count_spoken_words(text))
    wps_map = {"rush": 2.72, "explain": 2.55, "brisk": 2.55, "stamp": 2.42}
    wps = wps_map.get(gear, 2.55)
    voiced = words / wps
    if chapter_end:
        pause = LONGFORM_CHAPTER_PAUSE_SEC
    elif beat_break or gear == "stamp":
        pause = LONGFORM_BEAT_PAUSE_SEC
    elif gear == "rush":
        pause = LONGFORM_RUSH_PAUSE_SEC
    else:
        pause = LONGFORM_INTER_SENTENCE_PAUSE_SEC
    return round(voiced + pause, 3)


def plan_relaxed_cuts_for_sentences(
    sentences: list[dict[str, Any]],
    chapter_visual_templates: dict[int, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    """
    Groups/splits chapter sentences into relaxed `16:9` documentary cuts (`3.2s..7.0s`, avg `~5.0s`):
      - Pairs adjacent short sentences in the same chapter/scene when combined duration `<= 6.5s`
      - Holds a single flowing `14–22`-word sentence as one `4.5s..6.9s` shot
      - Splits any `> 7.0s` sentence+pause span cleanly into two same-scene multi-angle shots (`A` wide + `B` closeup/brain)
    """
    planned_clips: list[dict[str, Any]] = []
    clip_idx = 1

    by_chapter: dict[int, list[dict[str, Any]]] = {}
    for s in sentences:
        by_chapter.setdefault(int(s["chapter"]), []).append(s)

    for ch_num in sorted(by_chapter.keys()):
        ch_sents = by_chapter[ch_num]
        templates = chapter_visual_templates.get(ch_num) or [
            {
                "grammar": "porcelain_fullbleed_world",
                "camera": "locked_tripod",
                "anchor_id": "ref_master_bedroom_wide",
                "scene": "A clothed matte-white porcelain figure sits on the edge of a minimalist walnut bed in calm pre-dawn moonlight, hands resting on crisp linen sheets",
            }
        ]
        t_cursor = 0
        i = 0
        first_in_chapter = True
        ch_clips: list[dict[str, Any]] = []
        while i < len(ch_sents):
            s_cur = ch_sents[i]
            dur_cur = float(s_cur["est_duration_sec"])
            tmpl = dict(templates[t_cursor % len(templates)])
            t_cursor += 1

            # Case 1: Pair adjacent sentences in same chapter when combined duration <= 6.55s
            # (also avoid leaving a single < 3.2s orphan at the very end of the chapter if we can pair differently)
            can_pair_next = (
                i + 1 < len(ch_sents)
                and not bool(s_cur.get("force_cut_after"))
                and (dur_cur < LONGFORM_MIN_CUT_SEC + 0.25 or (dur_cur + float(ch_sents[i + 1]["est_duration_sec"]) <= 6.45))
                and (dur_cur + float(ch_sents[i + 1]["est_duration_sec"]) <= LONGFORM_MAX_CUT_SEC - 0.15)
            )
            if can_pair_next:
                s_next = ch_sents[i + 1]
                comb_dur = round(dur_cur + float(s_next["est_duration_sec"]), 3)
                ch_clips.append(
                    _make_clip_dict(
                        clip_idx=0,
                        ch_num=ch_num,
                        sentence_indices=[int(s_cur["sentence_index"]), int(s_next["sentence_index"])],
                        est_dur=comb_dur,
                        tmpl=tmpl,
                        chapter_break=first_in_chapter,
                        sub_angle=None,
                    )
                )
                first_in_chapter = False
                i += 2
                continue

            # Case 2: Long sentence + pause (> 7.0s) -> split into K (>=2) same-scene multi-angle cuts (each in [3.2s, 7.0s])
            if dur_cur > LONGFORM_MAX_CUT_SEC:
                n_parts = max(2, int(math.ceil(dur_cur / (LONGFORM_MAX_CUT_SEC - 0.15))))
                part_dur = round(dur_cur / n_parts, 3)
                rem_dur = dur_cur
                for p_i in range(n_parts):
                    this_dur = round(rem_dur, 3) if p_i == n_parts - 1 else part_dur
                    rem_dur -= this_dur
                    p_tmpl = tmpl if p_i == 0 else dict(templates[t_cursor % len(templates)])
                    if p_i > 0:
                        t_cursor += 1
                        if p_tmpl.get("camera") == tmpl.get("camera"):
                            p_tmpl["camera"] = (
                                "macro_rack_focus"
                                if p_tmpl.get("grammar") != "porcelain_living_brain"
                                else "orbital_3d_arc_sweep"
                            )
                    f0 = round(p_i / float(n_parts), 3)
                    f1 = round((p_i + 1) / float(n_parts), 3)
                    ch_clips.append(
                        _make_clip_dict(
                            clip_idx=0,
                            ch_num=ch_num,
                            sentence_indices=[int(s_cur["sentence_index"])],
                            est_dur=this_dur,
                            tmpl=p_tmpl,
                            chapter_break=first_in_chapter and (p_i == 0),
                            sub_angle=f"angle_{chr(ord('a') + p_i)}",
                            sentence_fraction=(f0, f1),
                        )
                    )
                first_in_chapter = False
                i += 1
                continue

            # Case 3: Single sentence
            ch_clips.append(
                _make_clip_dict(
                    clip_idx=0,
                    ch_num=ch_num,
                    sentence_indices=[int(s_cur["sentence_index"])],
                    est_dur=round(dur_cur, 3),
                    tmpl=tmpl,
                    chapter_break=first_in_chapter,
                    sub_angle=None,
                )
            )
            first_in_chapter = False
            i += 1

        # Rebalance any < 3.2s cut within the chapter while preserving exact total chapter duration
        k = 0
        while k < len(ch_clips):
            d_k = float(ch_clips[k]["target_duration_sec"])
            if d_k >= LONGFORM_MIN_CUT_SEC or len(ch_clips) == 1:
                k += 1
                continue
            neighbor_idx = k - 1 if k > 0 else k + 1
            a_idx, b_idx = min(k, neighbor_idx), max(k, neighbor_idx)
            ca, cb = ch_clips[a_idx], ch_clips[b_idx]
            comb = round(float(ca["target_duration_sec"]) + float(cb["target_duration_sec"]), 3)
            merged_sents = sorted({*ca["sentence_indices"], *cb["sentence_indices"]})
            if comb <= LONGFORM_MAX_CUT_SEC:
                ca["sentence_indices"] = merged_sents
                ca["sentence_fraction"] = [0.0, 1.0]
                ca["sub_angle"] = None
                ca["target_duration_sec"] = comb
                ch_clips.pop(b_idx)
                k = max(0, a_idx)
            else:
                half1 = round(comb * 0.5, 3)
                half2 = round(comb - half1, 3)
                ca["sentence_indices"] = merged_sents
                cb["sentence_indices"] = merged_sents
                ca["target_duration_sec"] = half1
                cb["target_duration_sec"] = half2
                ca["sub_angle"] = "angle_a"
                cb["sub_angle"] = "angle_b"
                k = b_idx + 1

        planned_clips.extend(ch_clips)

    t_running = 0.0
    for idx_final, c_item in enumerate(planned_clips, start=1):
        c_item["index"] = idx_final
        c_item["clip_number"] = idx_final
        dur_c = round(max(LONGFORM_MIN_CUT_SEC, min(LONGFORM_MAX_CUT_SEC, float(c_item["target_duration_sec"]))), 3)
        c_item["target_duration_sec"] = dur_c
        c_item["start_sec"] = round(t_running, 3)
        t_running += dur_c
        c_item["end_sec"] = round(t_running, 3)

    return planned_clips


def _make_clip_dict(
    *,
    clip_idx: int,
    ch_num: int,
    sentence_indices: list[int],
    est_dur: float,
    tmpl: dict[str, Any],
    chapter_break: bool,
    sub_angle: str | None,
    sentence_fraction: tuple[float, float] = (0.0, 1.0),
) -> dict[str, Any]:
    grammar = str(tmpl.get("grammar") or "porcelain_fullbleed_world")
    camera = str(tmpl.get("camera") or "locked_tripod")
    scene_clean = sanitize_longform_scene_props(str(tmpl.get("scene") or ""))
    spec: dict[str, Any] = {
        "index": clip_idx,
        "clip_number": clip_idx,
        "chapter": ch_num,
        "act": ch_num,
        "chapter_break": bool(chapter_break),
        "sentence_indices": sentence_indices,
        "sentence_fraction": [sentence_fraction[0], sentence_fraction[1]],
        "sub_angle": sub_angle,
        "target_duration_sec": round(est_dur, 3),
        "flow_render_duration": "8s",
        "aspect": FLOW_ASPECT_LONGFORM,
        "style_profile": PORCELAIN_V7_STYLE_PROFILE,
        "grammar": grammar,
        "brain_mode": tmpl.get("brain_mode") if grammar == "porcelain_living_brain" else None,
        "anatomy_label": tmpl.get("anatomy_label"),
        "split_mode": tmpl.get("split_mode"),
        "split_left_label": tmpl.get("split_left_label"),
        "split_right_label": tmpl.get("split_right_label"),
        "camera": camera,
        "conditioning_track": str(tmpl.get("conditioning_track") or "track_b"),
        "reference_anchor_id": tmpl.get("anchor_id"),
        "scene": scene_clean,
    }
    spec["prompt"] = build_longform_16x9_flow_prompt(spec)
    return spec


def build_flow_shards(clips: list[dict[str, Any]], max_per_shard: int = LONGFORM_SHARD_MAX_CLIPS) -> list[dict[str, Any]]:
    shards: list[dict[str, Any]] = []
    for s_idx in range(0, len(clips), max_per_shard):
        chunk = clips[s_idx : s_idx + max_per_shard]
        shards.append(
            {
                "shard_index": len(shards) + 1,
                "clip_numbers": [int(c["clip_number"]) for c in chunk],
                "chapters_covered": sorted({int(c["chapter"]) for c in chunk}),
                "clip_count": len(chunk),
            }
        )
    return shards


def initialize_longform_project(
    project_id: str,
    episode_spec: dict[str, Any],
    *,
    projects_longform_dir: str | Path | None = None,
) -> dict[str, Any]:
    """
    Creates a complete standalone `16:9` (`1920x1080`) Long-Form project inside `projects_longform/<project_id>/`
    with `script.json`, `visual_plan.json`, `flow_longform_prompts.json`, `research_card.json`, and `00_project_manifest.json`.
    """
    proj_dir = resolve_longform_project_dir(
        project_id,
        projects_longform_dir=projects_longform_dir,
        create=True,
    )
    now_iso = datetime.now(timezone.utc).isoformat()
    slug = str(episode_spec.get("dossier_slug") or re.sub(r"^longform_\d+_", "", project_id)).strip()
    title = str(episode_spec["title"]).strip()
    pillar = str(episode_spec.get("pillar") or "brain_health").strip()
    everyday_domain = str(episode_spec.get("everyday_domain") or "sleep").strip()
    voice_preset = str(episode_spec.get("voice_preset") or LONGFORM_DEFAULT_VOICE_PRESET).strip()
    prosody_mode = str(episode_spec.get("prosody_mode") or LONGFORM_PROSODY_MODE).strip()

    chapters_in = list(episode_spec["chapters"])
    flat_sentences: list[dict[str, Any]] = []
    chapters_out: list[dict[str, Any]] = []
    chapter_templates: dict[int, list[dict[str, Any]]] = {}

    s_global_idx = 1
    for ch_pos, ch in enumerate(chapters_in, start=1):
        ch_num = int(ch.get("chapter_number") or ch_pos)
        ch_title = str(ch["title"]).strip()
        ch_headline = str(ch.get("headline") or f"CHAPTER {ch_num} · {ch_title.upper()}").strip()
        raw_sents = list(ch["sentences"])
        ch_sent_indices: list[int] = []
        ch_words = 0
        for local_i, s_item in enumerate(raw_sents):
            is_last_in_ch = local_i == len(raw_sents) - 1
            is_last_in_ep = (ch_pos == len(chapters_in)) and is_last_in_ch
            if isinstance(s_item, str):
                txt = s_item.strip()
                gear = "rush" if (ch_pos == 1 and local_i < 2) else ("stamp" if is_last_in_ch else "explain")
                beat_break = is_last_in_ch
                citation_id = None
                emphasis_words: list[str] = []
                force_cut = False
            else:
                txt = str(s_item["text"]).strip()
                gear = str(s_item.get("gear") or ("stamp" if is_last_in_ch else "explain")).strip()
                beat_break = bool(s_item.get("beat_break", is_last_in_ch))
                citation_id = s_item.get("citation_id")
                emphasis_words = list(s_item.get("emphasis_words") or [])
                force_cut = bool(s_item.get("force_cut_after", False))

            wc = count_spoken_words(txt)
            ch_words += wc
            est_sec = estimate_sentence_duration_sec(
                txt,
                gear=gear,
                beat_break=beat_break or bool(citation_id),
                chapter_end=is_last_in_ch and not is_last_in_ep,
            )
            s_rec = {
                "sentence_index": s_global_idx,
                "chapter": ch_num,
                "chapter_sentence_index": local_i + 1,
                "text": txt,
                "word_count": wc,
                "gear": gear,
                "edge_tts_rate": LONGFORM_PROSODY_GEAR_RATES.get(gear, "+0%"),
                "beat_break": beat_break,
                "chapter_end": is_last_in_ch and not is_last_in_ep,
                "episode_end": is_last_in_ep,
                "citation_id": citation_id,
                "emphasis_words": emphasis_words,
                "force_cut_after": force_cut,
                "est_duration_sec": est_sec,
            }
            flat_sentences.append(s_rec)
            ch_sent_indices.append(s_global_idx)
            s_global_idx += 1

        chapter_templates[ch_num] = list(ch.get("visual_templates") or [])
        chapters_out.append(
            {
                "chapter_number": ch_num,
                "title": ch_title,
                "headline": ch_headline,
                "role": str(ch.get("role") or "mechanism"),
                "sentence_indices": ch_sent_indices,
                "word_count": ch_words,
                "chapter_pause_after_sec": LONGFORM_CHAPTER_PAUSE_SEC if ch_pos < len(chapters_in) else LONGFORM_OUTRO_SWELL_SEC,
            }
        )

    total_words = sum(s["word_count"] for s in flat_sentences)
    est_total_sec = round(sum(s["est_duration_sec"] for s in flat_sentences) + LONGFORM_OUTRO_SWELL_SEC, 2)
    planned_clips = plan_relaxed_cuts_for_sentences(flat_sentences, chapter_templates)
    shards = build_flow_shards(planned_clips, max_per_shard=LONGFORM_SHARD_MAX_CLIPS)

    citation_cards = list(episode_spec.get("citation_cards") or [])
    reference_anchors = list(episode_spec.get("reference_anchors") or [])
    offcenter_bet = str(episode_spec.get("offcenter_creator_bet") or "").strip()

    script_doc = {
        "schema": "longform_script_v1",
        "project_id": project_id,
        "dossier_slug": slug,
        "title": title,
        "pillar": pillar,
        "everyday_domain": everyday_domain,
        "production_profile": LONGFORM_PRODUCTION_PROFILE,
        "style_profile": PORCELAIN_V7_STYLE_PROFILE,
        "voice_preset": voice_preset,
        "prosody_mode": prosody_mode,
        "max_sentence_words": LONGFORM_MAX_SENTENCE_WORDS,
        "chapter_count": len(chapters_out),
        "sentence_count": len(flat_sentences),
        "word_count": total_words,
        "estimated_duration_sec": est_total_sec,
        "full_text": " ".join(s["text"] for s in flat_sentences),
        "chapters": chapters_out,
        "sentences": flat_sentences,
        "citation_cards": citation_cards,
        "offcenter_creator_bet": offcenter_bet,
        "doi": str(episode_spec.get("primary_doi") or (citation_cards[0]["doi"] if citation_cards else "")),
        "created_at": now_iso,
    }

    cut_durs = [float(c["target_duration_sec"]) for c in planned_clips]
    avg_cut = round(sum(cut_durs) / max(1, len(cut_durs)), 3)

    visual_plan_doc = {
        "schema": "longform_visual_plan_v1",
        "schema_version": 7,
        "project_id": project_id,
        "dossier": slug,
        "title": title,
        "pillar": pillar,
        "everyday_domain": everyday_domain,
        "production_profile": LONGFORM_PRODUCTION_PROFILE,
        "style_profile": PORCELAIN_V7_STYLE_PROFILE,
        "aspect": FLOW_ASPECT_LONGFORM,
        "resolution": [LONGFORM_VIDEO_WIDTH, LONGFORM_VIDEO_HEIGHT],
        "fps": LONGFORM_VIDEO_FPS,
        "target_lufs": LONGFORM_TARGET_LUFS,
        "voice_preset": voice_preset,
        "prosody_mode": prosody_mode,
        "zero_clip_reuse": True,
        "upload_cc_srt": LONGFORM_UPLOAD_CC_SRT_DEFAULT,
        "cut_pacing": {
            "min_cut_sec": LONGFORM_MIN_CUT_SEC,
            "avg_cut_target_sec": LONGFORM_AVG_CUT_TARGET_SEC,
            "avg_cut_range_sec": list(LONGFORM_AVG_CUT_RANGE_SEC),
            "max_cut_sec": LONGFORM_MAX_CUT_SEC,
            "planned_avg_cut_sec": avg_cut,
            "planned_clip_count": len(planned_clips),
        },
        "thumbnail": dict(
            episode_spec.get("thumbnail")
            or {
                "hook_text": str(episode_spec.get("thumbnail_hook") or "60% BRAIN WASH"),
                "variants": ["A", "B", "C"],
            }
        ),
        "reference_anchors": reference_anchors,
        "citation_cards": citation_cards,
        "chapter_visual_templates": {str(k): v for k, v in chapter_templates.items()},
        "chapters": chapters_out,
        "clips": planned_clips,
        "flow_shards": shards,
        "compiled_at": now_iso,
    }

    prompts_doc = {
        "schema": "longform_flow_prompts_v1",
        "project_id": project_id,
        "aspect": FLOW_ASPECT_LONGFORM,
        "resolution": [LONGFORM_VIDEO_WIDTH, LONGFORM_VIDEO_HEIGHT],
        "clip_count": len(planned_clips),
        "shard_count": len(shards),
        "shards": shards,
        "clips": [
            {
                "clip_number": c["clip_number"],
                "chapter": c["chapter"],
                "target_duration_sec": c["target_duration_sec"],
                "flow_render_duration": c["flow_render_duration"],
                "conditioning_track": c["conditioning_track"],
                "reference_anchor_id": c["reference_anchor_id"],
                "grammar": c["grammar"],
                "camera": c["camera"],
                "prompt": c["prompt"],
            }
            for c in planned_clips
        ],
    }

    research_card = {
        "project_id": project_id,
        "dossier_slug": slug,
        "title": title,
        "pillar": pillar,
        "everyday_domain": everyday_domain,
        "doi": script_doc["doi"],
        "three_layer_formula": dict(
            episode_spec.get("three_layer_formula")
            or {
                "everyday_problem": everyday_domain,
                "psychology_studies": [],
                "neuroscience_studies": [],
            }
        ),
        "citation_cards": citation_cards,
        "story_context": {
            "social_comment_trigger": offcenter_bet,
        },
    }

    manifest_doc = {
        "project_id": project_id,
        "title": title,
        "pillar": pillar,
        "everyday_domain": everyday_domain,
        "dossier_slug": slug,
        "production_profile": LONGFORM_PRODUCTION_PROFILE,
        "style_profile": PORCELAIN_V7_STYLE_PROFILE,
        "isolated_from_shorts": True,
        "aspect": FLOW_ASPECT_LONGFORM,
        "resolution": [LONGFORM_VIDEO_WIDTH, LONGFORM_VIDEO_HEIGHT],
        "fps": LONGFORM_VIDEO_FPS,
        "voice_preset": voice_preset,
        "prosody_mode": prosody_mode,
        "created_at": now_iso,
        "updated_at": now_iso,
    }

    (proj_dir / "00_project_manifest.json").write_text(json.dumps(manifest_doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (proj_dir / "01_ideation" / "research_card.json").write_text(json.dumps(research_card, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (proj_dir / "02_script" / "script.json").write_text(json.dumps(script_doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (proj_dir / "03_visuals" / "visual_plan.json").write_text(json.dumps(visual_plan_doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (proj_dir / "03_visuals" / "flow_longform_prompts.json").write_text(json.dumps(prompts_doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    return {
        "project_id": project_id,
        "project_dir": str(proj_dir),
        "chapter_count": len(chapters_out),
        "sentence_count": len(flat_sentences),
        "word_count": total_words,
        "estimated_duration_sec": est_total_sec,
        "planned_clip_count": len(planned_clips),
        "planned_avg_cut_sec": avg_cut,
        "shard_count": len(shards),
    }


def compile_longform_plan_from_dossier(
    slug_or_dir: str | Path,
    voice_preset: str = LONGFORM_DEFAULT_VOICE_PRESET,
    target_wpm: int = 145,
    save: bool = True,
) -> dict[str, Any]:
    """Compiles `07_longform_outline.json` from a research dossier into a `1920x1080` `16:9` Long-Form plan."""
    d_dir = Path(slug_or_dir) if Path(slug_or_dir).is_dir() else (Path(DOSSIERS_DIR) / str(slug_or_dir))
    if not d_dir.exists():
        raise FileNotFoundError(f"Dossier directory not found: {d_dir}")

    dossier = json.loads((d_dir / "dossier.json").read_text(encoding="utf-8"))
    outline_path = d_dir / "07_longform_outline.json"
    if not outline_path.exists():
        raise FileNotFoundError(f"Missing 07_longform_outline.json in {d_dir}")
    outline = json.loads(outline_path.read_text(encoding="utf-8"))

    slug = str(dossier.get("slug") or d_dir.name)
    target_minutes = max(8, min(12, int(outline.get("target_minutes") or 9)))
    target_total_words = target_minutes * int(target_wpm)

    chapters_raw = list(outline.get("chapters") or [])
    n_ch = max(1, len(chapters_raw))
    words_per_chapter = max(165, target_total_words // n_ch)

    reusable_hits = query_knowledge_base(
        pack="clips",
        query=slug.replace("_", " "),
        style_profile=PORCELAIN_V7_STYLE_PROFILE,
        limit=16,
    )

    compiled_chapters: list[dict[str, Any]] = []
    clip_counter = 1
    for idx, ch in enumerate(chapters_raw, start=1):
        beats = list(ch.get("beats") or ["Everyday setup", "Behavioral psychology test", "Neural circuit mechanism"])
        shots_needed = list(ch.get("new_shots_needed") or [])
        ch_clips: list[dict[str, Any]] = []
        for b_i, beat_txt in enumerate(beats):
            is_brain = (b_i == len(beats) - 1) or ("brain" in str(beat_txt).lower()) or ("cortex" in str(beat_txt).lower())
            grammar = "porcelain_living_brain" if is_brain else "porcelain_fullbleed_world"
            c_spec = {
                "clip_number": clip_counter,
                "chapter_number": idx,
                "aspect": FLOW_ASPECT_LONGFORM,
                "style_profile": PORCELAIN_V7_STYLE_PROFILE,
                "grammar": grammar,
                "brain_mode": "sagittal_coronal_cutaway" if is_brain else None,
                "camera": "gentle_push_in" if is_brain else "locked_tripod",
                "beat_summary": sanitize_longform_scene_props(str(beat_txt)),
            }
            c_spec["prompt"] = build_longform_16x9_flow_prompt(c_spec)
            ch_clips.append(c_spec)
            clip_counter += 1
        for extra_shot in shots_needed[:2]:
            c_spec = {
                "clip_number": clip_counter,
                "chapter_number": idx,
                "aspect": FLOW_ASPECT_LONGFORM,
                "style_profile": PORCELAIN_V7_STYLE_PROFILE,
                "grammar": "porcelain_hands_closeup",
                "camera": "macro_rack_focus",
                "beat_summary": sanitize_longform_scene_props(str(extra_shot)),
            }
            c_spec["prompt"] = build_longform_16x9_flow_prompt(c_spec)
            ch_clips.append(c_spec)
            clip_counter += 1

        compiled_chapters.append(
            {
                "chapter_number": idx,
                "title": str(ch.get("title") or f"Chapter {idx}"),
                "target_words": words_per_chapter,
                "chapter_pause_after_sec": LONGFORM_CHAPTER_PAUSE_SEC if idx < n_ch else LONGFORM_OUTRO_SWELL_SEC,
                "midroll_valley_after_sec": LONGFORM_CHAPTER_FADE_SEC if idx < n_ch else 0.0,
                "beats": beats,
                "clips": ch_clips,
            }
        )

    plan_doc: dict[str, Any] = {
        "schema": "longform_v7_porcelain_plan_v2",
        "slug": slug,
        "topic": dossier.get("topic"),
        "pillar": dossier.get("pillar"),
        "aspect": FLOW_ASPECT_LONGFORM,
        "resolution": [LONGFORM_VIDEO_WIDTH, LONGFORM_VIDEO_HEIGHT],
        "fps": LONGFORM_VIDEO_FPS,
        "target_lufs": LONGFORM_TARGET_LUFS,
        "style_profile": PORCELAIN_V7_STYLE_PROFILE,
        "prosody_mode": LONGFORM_PROSODY_MODE,
        "voice_preset": voice_preset,
        "max_sentence_words": LONGFORM_MAX_SENTENCE_WORDS,
        "target_minutes": target_minutes,
        "target_wpm": target_wpm,
        "target_total_words": target_total_words,
        "reusable_kb_clips_found": len(reusable_hits),
        "chapters": compiled_chapters,
        "total_planned_clips": clip_counter - 1,
        "compiled_at": datetime.now(timezone.utc).isoformat(),
    }

    if save:
        out_dir = d_dir / "longform_v7_porcelain"
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "longform_plan.json").write_text(
            json.dumps(plan_doc, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    return plan_doc
