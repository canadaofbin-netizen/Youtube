"""
ALL ABOUT BRAIN — Dynamic Per-Episode QA Contract Compiler & 3-Stage Multimodal Gate (R62)
==========================================================================================
Because every neuroscience documentary episode depicts completely different physical events,
period clothing, everyday analogies (e.g., football stadium field, bowling ball, baseball bat,
coffee cup, toggle switch console, suspension bridge), and brain structures, static generic QA
is insufficient.

This module dynamically compiles an episode-specific `03_visuals/episode_qa_contract.json`
from `script.json` + `visual_plan.json` + `research_dossiers/<slug>/` and enforces:
  - Gate 1 (`verify_pre_flow_contract`): Pre-Flow prompt-to-narration literalism, clothed ceramic
    cast (`R56-C`), 2-beat physical action & bloodless ceramic impact (`R56-M`/`R56-I`), and
    1:1 literal analogy cutaways (`R57-V`).
  - Gate 2 (`verify_clip_multimodal_contract`): Immediate post-download CV + visual-signature
    verification inside `flow_diorama_sharded_worker.py` (green stadium turf check for football/soccer
    fields, bright matte-white ceramic cast check, dark-void 3D brain glow, zero 0.5s freeze, zero plaques).
  - Gate 3 (`verify_final_mp4_against_contract`): 12-Axis Hard Gate (`DQ1-DQ12`) on the final rendered
    `final_shorts_1080x1920.mp4`, including `faster-whisper` ASR word-timestamp <-> decoded video frame
    alignment verification (`score == 100.0` required).
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from pipeline.config import (
    DIORAMA_MAX_CLIP_REUSE,
    DIORAMA_TARGET_CUT_MIN,
    DIORAMA_V7_ACTIVE_VOICED_RMS_RATIO_MIN,
    DIORAMA_V7_CAMERA_MOVES,
    DIORAMA_V7_CHAPTER_HEADLINE_MAX_WIDTH_PX,
    DIORAMA_V7_CUT_CV_MIN,
    DIORAMA_V7_DARK_VOID_RATIO_MAX,
    DIORAMA_V7_LOCKED_CAMERA_MIN_RATIO,
    DIORAMA_V7_LONG_TAKE_MAX_SEC,
    DIORAMA_V7_LUMA_RANGE,
    DIORAMA_V7_MID_ACT_MAX_CUT_SEC,
    DIORAMA_V7_RAPID_CUT_MIN_SEC,
    DIORAMA_V7_SATURATION_RANGE,
    DIORAMA_V7_SUBTITLE_FONT_NAME,
    DIORAMA_V7_SUBTITLE_MARGIN_V,
    DIORAMA_V7_VIDEO_FPS,
    DIORAMA_V7_WPM_MAX,
    DIORAMA_V7_WPM_MIN,
    DIORAMA_V7_ZOOM_CAMERA_MAX_RATIO,
    EXPRESSIVE_25D_V8_STYLE_PROFILE,
    EXPRESSIVE_V8_CAMERA_MOVES,
    EXPRESSIVE_V8_CLIP_COUNT_MIN,
    EXPRESSIVE_V8_MAX_CUT_SEC,
    EXPRESSIVE_V8_MIN_CUT_SEC,
    EXPRESSIVE_V8_SUBTITLE_FONT_SIZE,
    EXPRESSIVE_V8_SUBTITLE_MARGIN_V,
    EXPRESSIVE_V8_VISUAL_GRAMMARS,
    PORCELAIN_V7_AVG_CUT_MAX_SEC,
    PORCELAIN_V7_AVG_CUT_MIN_SEC,
    PORCELAIN_V7_BRAIN_MARGIN_SAT_MAX,
    PORCELAIN_V7_CUT_CV_MIN,
    PORCELAIN_V7_DARK_VOID_RATIO_MAX,
    PORCELAIN_V7_HUMAN_SKIN_MAX,
    PORCELAIN_V7_LONG_TAKE_MAX_SEC,
    PORCELAIN_V7_LUMA_RANGE,
    PORCELAIN_V7_MID_ACT_MAX_CUT_SEC,
    PORCELAIN_V7_MIN_CUT_SEC,
    PORCELAIN_V7_NEON_GREEN_SPILL_MAX,
    PORCELAIN_V7_SATURATION_RANGE,
    PROJECTS_DIR,
    PROMPT_SCHEMA_VERSION_V7,
    PROMPT_SCHEMA_VERSION_V8,
    REENACT_EDL_FILENAME,
    REENACT_MIN_DHASH_DISTANCE,
    SHORTS_EXPRESSIVE_V8_PROFILE,
    VIDEO_FPS,
    is_diorama_v7_plan,
    is_expressive_v8_plan,
    is_porcelain_v7_plan,
    resolve_diorama_v7_style_profile,
)
from pipeline.depiction_rules import normalize_porcelain_v7_brain_mode, normalize_porcelain_v7_grammar
from pipeline.plain_language import find_anatomy_terms, to_display_text

# ------------------------------------------------------------------------------
# 1. Dynamic Literal Analogy Catalog (R57-V: "Say It -> Show It Literally!")
# ------------------------------------------------------------------------------
LITERAL_ANALOGY_SPECS: tuple[dict[str, Any], ...] = (
    {
        "id": "football_field",
        "spoken_re": re.compile(r"\bfootball\s+fields?\b", re.IGNORECASE),
        "required_any_nouns": ("football field", "football stadium", "green-turf", "green turf", "yard line", "yard-line"),
        "forbidden_abstract": ("oak field grid", "four equal recessed brass", "turned-oak cylinders", "ceramic square tiles"),
        "cv_signature": "green_stadium_turf",
    },
    {
        "id": "soccer_field",
        "spoken_re": re.compile(r"\bsoccer\s+fields?\b", re.IGNORECASE),
        "required_any_nouns": ("soccer field", "soccer pitch", "green-turf", "green turf"),
        "forbidden_abstract": ("oak field grid", "turned-oak cylinders", "ceramic square tiles"),
        "cv_signature": "green_stadium_turf",
    },
    {
        "id": "bowling_ball",
        "spoken_re": re.compile(r"\bbowling\s+balls?\b", re.IGNORECASE),
        "required_any_nouns": ("bowling ball", "three-hole bowling", "bowling pins"),
        "forbidden_abstract": ("matte-charcoal sphere", "charcoal sphere", "turned-oak cylinders"),
        "cv_signature": "high_contrast_object",
    },
    {
        "id": "baseball_bat",
        "spoken_re": re.compile(r"\bbaseball\s+bats?\b", re.IGNORECASE),
        "required_any_nouns": ("baseball bat",),
        "forbidden_abstract": ("turned-oak cylinders", "ceramic square tiles"),
        "cv_signature": "high_contrast_object",
    },
    {
        "id": "playing_card",
        "spoken_re": re.compile(r"\bplaying\s+cards?\b", re.IGNORECASE),
        "required_any_nouns": ("playing card", "ivory card"),
        "forbidden_abstract": ("turned-oak cylinders",),
        "cv_signature": "high_contrast_object",
    },
    {
        "id": "wagon_brake",
        "spoken_re": re.compile(r"\bwagon\s+brakes?\b", re.IGNORECASE),
        "required_any_nouns": ("wagon", "brake"),
        "forbidden_abstract": ("turned-oak cylinders", "ceramic square tiles"),
        "cv_signature": "high_contrast_object",
    },
    {
        "id": "coffee_cup",
        "spoken_re": re.compile(r"\bcoffee\s+cups?\b", re.IGNORECASE),
        "required_any_nouns": ("coffee cup", "porcelain cup", "ceramic coffee cup"),
        "forbidden_abstract": ("turned-oak cylinders", "ceramic square tiles"),
        "cv_signature": "high_contrast_object",
    },
    {
        "id": "splint",
        "spoken_re": re.compile(r"\bsplints?\b", re.IGNORECASE),
        "required_any_nouns": ("splint",),
        "forbidden_abstract": ("turned-oak cylinders",),
        "cv_signature": "high_contrast_object",
    },
    {
        "id": "pencil",
        "spoken_re": re.compile(r"\bpencils?\b", re.IGNORECASE),
        "required_any_nouns": ("pencil", "hexagonal cedar", "graphite pencil", "yellow pencil"),
        "forbidden_abstract": ("turned-oak cylinders",),
        "cv_signature": "high_contrast_object",
    },
    {
        "id": "bicycle",
        "spoken_re": re.compile(r"\b(?:bicycles?|riding\s+a\s+bike)\b", re.IGNORECASE),
        "required_any_nouns": ("bicycle", "two-wheeled bike", "pedals", "handlebars"),
        "forbidden_abstract": ("turned-oak cylinders", "ceramic square tiles"),
        "cv_signature": "high_contrast_object",
    },
    {
        "id": "juggling",
        "spoken_re": re.compile(r"\bjuggling\b", re.IGNORECASE),
        "required_any_nouns": ("juggling", "three pastel balls", "three balls", "arcing balls"),
        "forbidden_abstract": ("turned-oak cylinders",),
        "cv_signature": "high_contrast_object",
    },
    {
        "id": "bookshelf",
        "spoken_re": re.compile(r"\b(?:bookshelves|library\s+shelves|wall\s+cabinets)\b", re.IGNORECASE),
        "required_any_nouns": ("bookshelf", "bookshelves", "library shelves", "hardcover books", "wooden shelves", "wall cabinets"),
        "forbidden_abstract": ("turned-oak cylinders",),
        "cv_signature": "high_contrast_object",
    },
)

_CERAMIC_CAST_RE = re.compile(
    r"\b(?:bisque-ceramic|ceramic)\s+(?:[a-z\-]+\s+){0,4}(?:figures?|crew|crewmates?|driver|physician|leader|worker|workers)\b",
    flags=re.IGNORECASE,
)

_LOWPOLY_CAST_RE = re.compile(
    r"\b(?:low-poly|faceted)\s+(?:[a-z0-9\-]+\s+){0,5}(?:figures?|crew|crewmates?|driver|foreman|physician|doctor|surgeon|"
    r"researcher|neuropsychologist|scientist|examiner|patient|subject|cyclist|student|leader|worker|workers|hands|forearms)\b",
    flags=re.IGNORECASE,
)

_PORCELAIN_V7_CAST_RE = re.compile(
    r"\b(?:porcelain)\s+(?:[a-z0-9\-]+\s+){0,6}(?:figures?|mannequins?|crew|crewmates?|driver|physician|doctor|surgeon|"
    r"researcher|neuropsychologist|scientist|examiner|patient|subject|cyclist|student|leader|worker|workers|hands|forearms|"
    r"guards?|prisoners?|monks?|jugglers?|divers?|players?|participants?|volunteers?|confederates?|bystanders?|observers?|"
    r"witnesses?|children|child|infants?|toddlers?|boys?|girls?|men|women|man|woman|mothers?|fathers?|parents?|"
    r"nurses?|orderlies|clinicians?|therapists?|psychologists?|psychiatrists?|neurologists?|professors?|teachers?|"
    r"musicians?|pianists?|violinists?|pilots?|soldiers?|veterans?|clerks?|archivists?|runners?|swimmers?|athletes?)\b",
    flags=re.IGNORECASE,
)

_EXPRESSIVE_V8_CAST_RE = re.compile(
    r"\b(?:2\.5d\s+vinyl|matte-white\s+2\.5d|vinyl\s+(?:figure|figures|character|characters|cast|sleeper|protagonist|hands?|subject|subjects|guard|guards|doctor|researcher|traveler|guest)|"
    r"2d\s+charcoal\s+ink|charcoal\s+2d\s+ink)\b",
    flags=re.IGNORECASE,
)

_EXPRESSIVE_V8_CONTEXT_SPLIT_CAST_RE = re.compile(
    r"\b(?:protagonist|subject|subjects|foil|sleeper|sleepers|pilot|pilots|commuter|commuters|driver|drivers|"
    r"doctor|doctors|researcher|researchers|scientist|scientists|guard|guards|worker|workers|student|students|"
    r"player|players|volunteer|volunteers|participant|participants|traveler|travelers|guest|guests|character|characters|"
    r"figure|figures|hands?|fingers?|gloved|ink\s+eyes|ink\s+eyebrows)\b",
    flags=re.IGNORECASE,
)

_WARDROBE_OR_HAT_RE = re.compile(
    r"\b(?:hat|hats|cap|caps|helmet|helmets|bonnet|coat|coats|lab\s+coats?|blazers?|cardigans?|sweaters?|duster|vest|vests|"
    r"waistcoats?|jackets?|shirts?|sleeves|cuffs|trousers|slacks|pants|aprons?|gowns?|suits?|collars?|ties?|gloves|boots|"
    r"robes?|uniforms?|scrubs|dress|dresses|tunics?|linen\s+head\s+wrap|head\s+wrap|poncho|pajamas?|hoodies?|sweatshirts?|"
    r"nightshirts?|t-shirts?|tees?|slippers?|sneakers?|oxfords?|loafers?)\b",
    flags=re.IGNORECASE,
)

_ACTIVE_MOTION_VERBS_RE = re.compile(
    r"\b(?:shoot(?:s|ing)?|pierce(?:s|d)?|piercing|pass(?:es|ing)?|launch(?:es|ing)?|rocket(?:s|ing)?|"
    r"knock(?:s|ing)?|tamp(?:s|ing)?|plunge(?:s|d)?|plunging|strike(?:s)?|striking|hammer(?:s|ing)?|"
    r"drill(?:s|ing)?|drive(?:s)?|driving|grip(?:s|ping)?|grasp(?:s|ing)?|lift(?:s|ing)?|push(?:es|ing)?|"
    r"pull(?:s|ing)?|climb(?:s|ing)?|walk(?:s|ing)?|step(?:s|ping)?|rise(?:s)?|rising|turn(?:s|ing)?|"
    r"lean(?:s|ing)?|align(?:s|ing)?|latch(?:es|ing)?|close(?:s)?|closing|open(?:s|ing)?|steer(?:s|ing)?|"
    r"tension(?:s|ing)?|extend(?:s|ing)?|greet(?:s|ing)?|shake(?:s)?|shaking|ride(?:s)?|riding|pedal(?:s|ing)?|"
    r"hold(?:s|ing)?|reach(?:es|ing)?|flip(?:s|ping)?|press(?:es|ing)?|catch(?:es|ing)?|swing(?:s|ing)?|"
    r"tilt(?:s|ing)?|brace(?:s)?|bracing|pour(?:s|ing)?|drop(?:s|ping)?|roll(?:s|ing)?|arc(?:s|ing)?|"
    r"land(?:s|ing)?|snap(?:s|ping)?|crack(?:s|ing)?|gallop(?:s|ing)?|trot(?:s|ting)?|slide(?:s)?|sliding|"
    r"trace(?:s|d)?|tracing|draw(?:s|ing)?|sketch(?:es|ing)?|write(?:s)?|writing|point(?:s|ing)?|tap(?:s|ping)?|"
    r"juggle(?:s)?|juggling|glide(?:s)?|gliding|cross(?:es|ing)?|place(?:s)?|placing|rest(?:s|ing)?|set(?:s|ting)?|"
    r"sit(?:s|ting)?|bolt(?:s|ing)?|rub(?:s|bing)?|blink(?:s|ing)?|gasp(?:s|ing)?|whisper(?:s|ing)?|stare(?:s|ing)?|"
    r"glance(?:s|ing)?|toss(?:es|ing)?|slam(?:s|ming)?|click(?:s|ing)?|part(?:s|ing)?|pulse(?:s|ing)?|glow(?:s|ing)?|"
    r"perch(?:es|ed|ing)?|peek(?:s|ing)?)\b",
    flags=re.IGNORECASE,
)

_TRAUMA_OR_EVENT_HOOK_RE = re.compile(
    r"\b(?:shoots?\s+through|pierced?|skull|tamped|blast|shot\s+beneath|shock|volt|mirror|bridge|severed)\b",
    flags=re.IGNORECASE,
)


def _clips_by_sentence(clips: list[dict[str, Any]]) -> dict[int, list[dict[str, Any]]]:
    mapping: dict[int, list[dict[str, Any]]] = {}
    for idx, c in enumerate(clips, start=1):
        s_no = c.get("sentence_index")
        if isinstance(s_no, int) and s_no >= 1:
            s_end = max(s_no, int(c.get("end_sentence_index") or s_no))
            entry = dict(c)
            entry.setdefault("clip_number", idx)
            for s_k in range(s_no, s_end + 1):
                mapping.setdefault(s_k, []).append(entry)
    return mapping


def compile_episode_qa_contract(
    visual_plan: dict[str, Any],
    sentences: list[str],
    rendered_clips: list[dict[str, Any]],
    script_doc: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Dynamically compiles a strict episode-specific QA contract (`episode_qa_contract.json`)
    tailored to the exact analogies, clothed cast actions, trauma/event hooks, and
    anatomy mentions of this episode (supporting Schema v6, Schema v7, and Schema v8 `expressive_25d_v8`).
    """
    clean_sents = [str(s).strip() for s in sentences if str(s).strip()]
    by_sent = _clips_by_sentence(rendered_clips)
    is_expressive_v8 = is_expressive_v8_plan(visual_plan, *(rendered_clips or []), script_doc) or any(
        int(c.get("schema_version") or 6) >= PROMPT_SCHEMA_VERSION_V8 for c in rendered_clips
    )
    is_v7 = (
        is_expressive_v8
        or is_diorama_v7_plan(visual_plan)
        or (isinstance(script_doc, dict) and is_diorama_v7_plan(script_doc))
        or any(int(c.get("schema_version") or 6) >= PROMPT_SCHEMA_VERSION_V7 for c in rendered_clips)
    )
    is_porcelain = bool(is_v7 and (is_expressive_v8 or is_porcelain_v7_plan(visual_plan, *(rendered_clips or []), script_doc)))

    analogy_locks: list[dict[str, Any]] = []
    anatomy_locks: list[dict[str, Any]] = []
    early_hook_sentences: list[int] = []
    n_tot_clips = max(1, len(rendered_clips))

    for s_idx, sent in enumerate(clean_sents, start=1):
        bound = by_sent.get(s_idx, [])
        bound_nums = [int(c["clip_number"]) for c in bound]
        for spec in LITERAL_ANALOGY_SPECS:
            m = spec["spoken_re"].search(sent)
            if m:
                analogy_locks.append(
                    {
                        "analogy_id": spec["id"],
                        "spoken_phrase": m.group(0),
                        "sentence_index": s_idx,
                        "sentence_text": sent,
                        "bound_clip_numbers": bound_nums,
                        "required_any_nouns": list(spec["required_any_nouns"]),
                        "forbidden_abstract": list(spec["forbidden_abstract"]),
                        "cv_signature": spec["cv_signature"],
                    }
                )

        anat_terms = find_anatomy_terms(sent)
        if anat_terms:
            from pipeline.config import (
                EXPRESSIVE_V8_BRAIN_REVEAL_TOLERANCE_FRAC,
                EXPRESSIVE_V8_NEURAL_DIVE_MOVES,
            )

            tol_lo_an, tol_hi_an = EXPRESSIVE_V8_BRAIN_REVEAL_TOLERANCE_FRAC
            core_rev_an = (script_doc or {}).get("core_reveal_sentence_index") or (visual_plan or {}).get("core_reveal_sentence_index")
            is_core_an = False
            if core_rev_an is not None:
                try:
                    is_core_an = s_idx == int(core_rev_an)
                except (TypeError, ValueError):
                    is_core_an = False
            has_r74_bound = any(
                str(bc.get("camera_move") or bc.get("camera") or "") in EXPRESSIVE_V8_NEURAL_DIVE_MOVES
                or bool(bc.get("neural_dive_relay"))
                for bc in bound
            )
            in_v8_reveal_zone = (not is_expressive_v8) or is_core_an or has_r74_bound or any(
                tol_lo_an <= ((n - 1) / float(n_tot_clips)) <= tol_hi_an for n in bound_nums
            )
            if in_v8_reveal_zone:
                anatomy_locks.append(
                    {
                        "sentence_index": s_idx,
                        "sentence_text": sent,
                        "anatomy_terms": anat_terms,
                        "bound_clip_numbers": bound_nums,
                    }
                )

        if s_idx <= 12 and _TRAUMA_OR_EVENT_HOOK_RE.search(sent):
            early_hook_sentences.append(s_idx)

    cold_open_impact_locks: list[dict[str, Any]] = []
    if is_v7 and not is_expressive_v8:
        for s_idx in range(1, min(13, len(clean_sents) + 1)):
            if re.search(
                r"\b(?:(?:shoots?|shot)(?:\s+straight)?\s+through|shot\s+beneath|pierce[ds]?|launches?\s+upward)\b",
                clean_sents[s_idx - 1],
                flags=re.IGNORECASE,
            ):
                for bc in by_sent.get(s_idx, []):
                    if str(bc.get("grammar") or "") in ("lowpoly_fullbleed_world", "porcelain_fullbleed_world"):
                        cold_open_impact_locks.append(
                            {
                                "clip_number": int(bc["clip_number"]),
                                "sentence_index": s_idx,
                                "sentence_text": clean_sents[s_idx - 1],
                                "cv_signature": "upward_impact_optical_flow",
                                "min_upward_fast_pct": 2.5,
                            }
                        )

    cast_clip_locks: list[dict[str, Any]] = []
    for idx, c in enumerate(rendered_clips, start=1):
        g_name = str(c.get("grammar") or "")
        if g_name in ("frosted_crystal_specimen", "lowpoly_matte_brain", "porcelain_living_brain", "expressive_xray_brain", "brain_simulator_3d"):
            continue
        scene_txt = str(c.get("scene") or "")
        is_img_cond_clip = bool(
            str(c.get("reference_image") or c.get("end_reference_image") or "").strip()
        ) or str(c.get("flow_input_mode") or "").upper() in ("VIDEO_FRAMES", "VIDEO_REFERENCES")
        if is_v7:
            if (
                g_name
                in (
                    "lowpoly_hands_closeup",
                    "lowpoly_pov_hands",
                    "porcelain_hands_closeup",
                    "porcelain_pov_hands",
                    "expressive_hands_closeup",
                    "expressive_pov_hands",
                    "expressive_hands_macro",
                    "expressive_reaction_closeup",
                )
                or _LOWPOLY_CAST_RE.search(scene_txt)
                or _PORCELAIN_V7_CAST_RE.search(scene_txt)
                or _EXPRESSIVE_V8_CAST_RE.search(scene_txt)
                or (
                    is_expressive_v8
                    and is_img_cond_clip
                    and g_name in (
                        "expressive_vinyl_world",
                        "expressive_exterior_establishing",
                        "architectural_cutaway_portal",
                        "expressive_cameo_world",
                        "expressive_split_contrast",
                    )
                    and bool(_EXPRESSIVE_V8_CONTEXT_SPLIT_CAST_RE.search(scene_txt))
                )
            ):
                cast_clip_locks.append(
                    {
                        "clip_number": idx,
                        "sentence_index": c.get("sentence_index"),
                        "act": c.get("act"),
                        "requires_wardrobe_or_hat": not (is_expressive_v8 and is_img_cond_clip),
                        "min_action_verbs": 1 if (is_expressive_v8 and is_img_cond_clip) else 2,
                        "cv_signature": (
                            "expressive_25d_world"
                            if is_expressive_v8
                            else ("bright_porcelain_world" if is_porcelain else "bright_lowpoly_world")
                        ),
                    }
                )
        elif _CERAMIC_CAST_RE.search(scene_txt):
            cast_clip_locks.append(
                {
                    "clip_number": idx,
                    "sentence_index": c.get("sentence_index"),
                    "act": c.get("act"),
                    "requires_wardrobe_or_hat": True,
                    "min_action_verbs": 2,
                    "cv_signature": "ceramic_cast_motion",
                }
            )

    if is_expressive_v8:
        from pipeline.config import (
            EXPRESSIVE_V8_AVG_CUT_MAX_SEC,
            EXPRESSIVE_V8_AVG_CUT_MIN_SEC,
            EXPRESSIVE_V8_FIRST_15S_MAX_CUT_SEC,
            EXPRESSIVE_V8_FIRST_15S_MIN_CUTS,
            EXPRESSIVE_V8_FIRST_CUT_MAX_SEC,
            EXPRESSIVE_V8_LEGACY_AVG_CUT_RANGE,
            EXPRESSIVE_V8_LEGACY_FIRST_15S_MAX_CUT_SEC,
            EXPRESSIVE_V8_LEGACY_FIRST_CUT_MAX_SEC,
            EXPRESSIVE_V8_LEGACY_LONG_TAKE_MAX_SEC,
            EXPRESSIVE_V8_LEGACY_MAX_CUT_SEC,
            EXPRESSIVE_V8_R76_AVG_CUT_TARGET_RANGE,
            EXPRESSIVE_V8_R76_HUMAN_MIN_CUT_SEC,
            EXPRESSIVE_V8_R76_MAX_CUT_SEC,
            EXPRESSIVE_V8_SPATIAL_RELAY_MIN_CUT_SEC,
            EXPRESSIVE_V8_WPM_ALLOWED_RANGE,
            is_brain_sim_only_plan,
            is_r72_open_world_v8_plan,
            is_r76_v8_plan,
            is_r82_dual_speed_pacing_plan,
        )
        from pipeline.config import (
            R82_AVG_CUT_TARGET_RANGE,
            R82_BRAIN_MAX_CUT_SEC,
            R82_FIRST_15S_MAX_CUT_SEC,
            R82_FIRST_15S_MIN_CUTS,
            R82_FIRST_CUT_MAX_SEC,
            R82_HUMAN_MIN_CUT_SEC,
        )

        allow_legacy_v8_tempo = bool(
            (visual_plan or {}).get("allow_legacy_v8_clip_count")
            or (script_doc or {}).get("allow_legacy_v8_clip_count")
        )
        is_brain_only_tempo = is_brain_sim_only_plan(visual_plan, script_doc)
        is_r82_tempo = is_r82_dual_speed_pacing_plan(visual_plan, script_doc)
        is_r76_tempo = is_r76_v8_plan(visual_plan, script_doc)
        is_r72_tempo = is_r72_open_world_v8_plan(visual_plan, script_doc)
        has_r80_spatial_relay = any(
            isinstance(c_sp, dict)
            and (
                str(c_sp.get("grammar") or "") == "spatial_3d_arrow_diorama"
                or bool(c_sp.get("spatial_relay_cut"))
            )
            for c_sp in ((visual_plan or {}).get("clips") or [])
        )
        if allow_legacy_v8_tempo:
            avg_lo_t, avg_hi_t = 1.40, 5.80
        elif is_brain_only_tempo:
            avg_lo_t, avg_hi_t = 2.50, 7.50
        elif is_r82_tempo:
            avg_lo_t, avg_hi_t = float(R82_AVG_CUT_TARGET_RANGE[0]), float(R82_AVG_CUT_TARGET_RANGE[1])
        elif is_r76_tempo:
            avg_lo_t, avg_hi_t = float(EXPRESSIVE_V8_R76_AVG_CUT_TARGET_RANGE[0]), float(EXPRESSIVE_V8_R76_AVG_CUT_TARGET_RANGE[1])
        elif not is_r72_tempo:
            avg_lo_t, avg_hi_t = float(EXPRESSIVE_V8_LEGACY_AVG_CUT_RANGE[0]), float(EXPRESSIVE_V8_LEGACY_AVG_CUT_RANGE[1])
        else:
            avg_lo_t, avg_hi_t = float(EXPRESSIVE_V8_AVG_CUT_MIN_SEC), float(EXPRESSIVE_V8_AVG_CUT_MAX_SEC)
        tempo_targets = {
            "wpm_min": float(EXPRESSIVE_V8_WPM_ALLOWED_RANGE[0]),
            "wpm_max": max(238.0, float(EXPRESSIVE_V8_WPM_ALLOWED_RANGE[1])),
            "min_cut_sec": (
                1.40
                if is_brain_only_tempo
                else (
                    float(R82_HUMAN_MIN_CUT_SEC)
                    if is_r82_tempo
                    else (
                        float(EXPRESSIVE_V8_SPATIAL_RELAY_MIN_CUT_SEC if has_r80_spatial_relay else EXPRESSIVE_V8_R76_HUMAN_MIN_CUT_SEC)
                        if is_r76_tempo
                        else EXPRESSIVE_V8_MIN_CUT_SEC
                    )
                )
            ),
            "avg_cut_min_sec": avg_lo_t,
            "avg_cut_max_sec": avg_hi_t,
            "first_cut_max_sec": (
                6.50
                if is_brain_only_tempo
                else (
                    float(R82_FIRST_CUT_MAX_SEC)
                    if is_r82_tempo
                    else (5.20 if is_r76_tempo else float(EXPRESSIVE_V8_FIRST_CUT_MAX_SEC if is_r72_tempo else EXPRESSIVE_V8_LEGACY_FIRST_CUT_MAX_SEC))
                )
            ),
            "first_15s_max_cut_sec": (
                8.00
                if is_brain_only_tempo
                else (
                    float(R82_FIRST_15S_MAX_CUT_SEC)
                    if is_r82_tempo
                    else (5.80 if is_r76_tempo else float(EXPRESSIVE_V8_FIRST_15S_MAX_CUT_SEC if is_r72_tempo else EXPRESSIVE_V8_LEGACY_FIRST_15S_MAX_CUT_SEC))
                )
            ),
            "first_15s_min_cuts": (
                2
                if is_brain_only_tempo
                else (
                    int(R82_FIRST_15S_MIN_CUTS)
                    if is_r82_tempo
                    else (2 if is_r76_tempo else int(EXPRESSIVE_V8_FIRST_15S_MIN_CUTS if is_r72_tempo else 0))
                )
            ),
            "fast_cut_threshold_sec": 2.50,
            "fast_cut_ratio_min": 0.0,
            "cut_duration_cv_min": (0.05 if (is_r76_tempo or is_brain_only_tempo) else 0.12),
            "max_single_sentence_cut_sec": (
                9.50
                if is_brain_only_tempo
                else (
                    float(R82_BRAIN_MAX_CUT_SEC)
                    if is_r82_tempo
                    else (float(EXPRESSIVE_V8_R76_MAX_CUT_SEC) if is_r76_tempo else float(EXPRESSIVE_V8_MAX_CUT_SEC if is_r72_tempo else EXPRESSIVE_V8_LEGACY_MAX_CUT_SEC))
                )
            ),
            "max_single_speech_cut_sec": (
                float(R82_BRAIN_MAX_CUT_SEC)
                if is_r82_tempo
                else (
                    float(EXPRESSIVE_V8_R76_MAX_CUT_SEC)
                    if is_r76_tempo
                    else float(EXPRESSIVE_V8_MAX_CUT_SEC if is_r72_tempo else EXPRESSIVE_V8_LEGACY_LONG_TAKE_MAX_SEC)
                )
            ),
            "max_clip_reuse": DIORAMA_MAX_CLIP_REUSE,
        }
    elif is_v7:
        tempo_targets = {
            "wpm_min": DIORAMA_V7_WPM_MIN,
            "wpm_max": DIORAMA_V7_WPM_MAX,
            "min_cut_sec": (PORCELAIN_V7_MIN_CUT_SEC if is_porcelain else DIORAMA_V7_RAPID_CUT_MIN_SEC),
            "avg_cut_min_sec": (PORCELAIN_V7_AVG_CUT_MIN_SEC if is_porcelain else 0.0),
            "avg_cut_max_sec": (PORCELAIN_V7_AVG_CUT_MAX_SEC if is_porcelain else 3.45),
            "fast_cut_threshold_sec": (2.30 if is_porcelain else 1.50),
            "fast_cut_ratio_min": (0.0 if is_porcelain else 0.20),
            "cut_duration_cv_min": (PORCELAIN_V7_CUT_CV_MIN if is_porcelain else DIORAMA_V7_CUT_CV_MIN),
            "max_single_sentence_cut_sec": (PORCELAIN_V7_MID_ACT_MAX_CUT_SEC if is_porcelain else DIORAMA_V7_MID_ACT_MAX_CUT_SEC),
            "max_single_speech_cut_sec": (PORCELAIN_V7_LONG_TAKE_MAX_SEC if is_porcelain else DIORAMA_V7_LONG_TAKE_MAX_SEC),
            "max_clip_reuse": DIORAMA_MAX_CLIP_REUSE,
        }
    else:
        tempo_targets = {
            "wpm_min": 162.0,
            "wpm_max": 208.0,
            "avg_cut_max_sec": 2.90,
            "fast_cut_threshold_sec": 2.15,
            "fast_cut_ratio_min": 0.18,
            "max_single_speech_cut_sec": 4.55,
            "max_clip_reuse": DIORAMA_MAX_CLIP_REUSE,
        }

    return {
        "schema": (
            "episode_qa_contract_v3"
            if is_expressive_v8
            else ("episode_qa_contract_v2" if is_v7 else "episode_qa_contract_v1")
        ),
        "is_v7": is_v7,
        "is_expressive_v8": is_expressive_v8,
        "style_profile": (
            EXPRESSIVE_25D_V8_STYLE_PROFILE
            if is_expressive_v8
            else (
                resolve_diorama_v7_style_profile(visual_plan, *(rendered_clips or []), script_doc)
                if is_v7
                else "dark_ceramic_v6"
            )
        ),
        "dossier": str((visual_plan or {}).get("dossier") or (script_doc or {}).get("dossier") or ""),
        "project_id": str((script_doc or {}).get("project_id") or ""),
        "sentence_count": len(clean_sents),
        "clip_count": len(rendered_clips),
        "analogy_locks": analogy_locks,
        "cast_clip_locks": cast_clip_locks,
        "cold_open_impact_locks": cold_open_impact_locks,
        "anatomy_locks": anatomy_locks,
        "early_hook_sentences": early_hook_sentences,
        "require_early_ceramic_reenactment_min_clips": (2 if early_hook_sentences else 0),
        "tempo_targets": tempo_targets,
    }


def write_episode_qa_contract(
    project_or_draft_dir: Path,
    visual_plan: dict[str, Any],
    sentences: list[str],
    rendered_clips: list[dict[str, Any]],
    script_doc: dict[str, Any] | None = None,
) -> tuple[Path, dict[str, Any]]:
    import os
    import time

    contract = compile_episode_qa_contract(visual_plan, sentences, rendered_clips, script_doc=script_doc)
    base = Path(project_or_draft_dir)
    out_dir = (base / "03_visuals") if (base / "03_visuals").exists() else base
    out_dir.mkdir(parents=True, exist_ok=True)
    edl_path = out_dir / REENACT_EDL_FILENAME
    if edl_path.exists():
        try:
            edl_doc = json.loads(edl_path.read_text(encoding="utf-8"))
            src_dhashes = [str(x) for x in (edl_doc.get("source_dhash_64_list") or []) if str(x)]
            if src_dhashes:
                contract["reenactment_dhash_lock"] = {
                    "min_dhash_bits": int(REENACT_MIN_DHASH_DISTANCE),
                    "source_dhash_64_list": src_dhashes,
                }
        except Exception as exc:
            import logging

            logging.getLogger("dynamic_episode_qa").warning(
                "Corrupt or unreadable %s while compiling episode_qa_contract: %s",
                edl_path,
                exc,
                exc_info=True,
            )
            raise RuntimeError(f"Corrupt Track A source EDL {edl_path}: {exc}") from exc
    out_path = out_dir / "episode_qa_contract.json"
    tmp_path = out_dir / f".tmp_{os.getpid()}_{time.time_ns()}_episode_qa_contract.json"
    tmp_path.write_text(json.dumps(contract, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp_path, out_path)
    if out_dir.name == "03_visuals":
        from pipeline.storage import ProjectStorage

        ProjectStorage.record_if_manifest_tracks_stages(base, "03_visuals", "episode_qa_contract.json", out_path)
    return out_path, contract


# ------------------------------------------------------------------------------
# 2. Gate 1: Pre-Flow Prompt-to-Contract Verification
# ------------------------------------------------------------------------------
def verify_pre_flow_contract(
    visual_plan: dict[str, Any],
    sentences: list[str],
    rendered_clips: list[dict[str, Any]],
    script_doc: dict[str, Any] | None = None,
) -> list[str]:
    """
    Zero-tolerance Pre-Flow Gate (R62/R63/v8 Gate 1):
      - Rejects abstract wooden token boards whenever a literal analogy (football field, bowling ball, etc.) is spoken.
      - Enforces period hats/wardrobe and >=2 active motion/impact verbs on every cast/hands clip.
      - Requires direct cast/hands reenactment in Acts 1-2 when physical trauma/events are narrated.
      - Verifies brain visualization alignment on anatomy-naming sentences + v8 [0-70%] brain ban / [70-85%] X-ray reveal / 1x Mini-Cortex cameo.
    """
    issues: list[str] = []
    if not rendered_clips or not sentences:
        return issues

    contract = compile_episode_qa_contract(visual_plan, sentences, rendered_clips, script_doc=script_doc)
    is_v7 = bool(contract.get("is_v7"))
    is_expressive_v8 = bool(contract.get("is_expressive_v8"))
    clips_by_num = {int(c.get("clip_number") or (i + 1)): c for i, c in enumerate(rendered_clips)}

    # 1. Literal 1:1 Analogy Locks (R57-V)
    for lock in contract["analogy_locks"]:
        b_nums = lock["bound_clip_numbers"]
        combined_scene = " ".join(str(clips_by_num[n].get("scene") or "").lower() for n in b_nums if n in clips_by_num)
        for bad_abs in lock["forbidden_abstract"]:
            if bad_abs.lower() in combined_scene:
                issues.append(
                    f"[dynamic_qa:analogy] sentence {lock['sentence_index']} ('{lock['spoken_phrase']}') uses forbidden "
                    f"abstract substitute '{bad_abs}' in clip(s) {b_nums}; must literally show '{lock['spoken_phrase']}' (R57-V/R62)"
                )
        if not any(req.lower() in combined_scene for req in lock["required_any_nouns"]):
            issues.append(
                f"[dynamic_qa:analogy] sentence {lock['sentence_index']} speaks '{lock['spoken_phrase']}' but bound clip(s) "
                f"{b_nums} never depict any of {lock['required_any_nouns']} (R57-V/R62)"
            )

    # 2. Clothed Cast & 2-Beat Motion Locks (R56-C / R56-M / R63)
    for c_lock in contract["cast_clip_locks"]:
        c_no = int(c_lock["clip_number"])
        scene_txt = str(clips_by_num[c_no].get("scene") or "")
        if c_lock.get("requires_wardrobe_or_hat", True) and not _WARDROBE_OR_HAT_RE.search(scene_txt):
            issues.append(
                f"[dynamic_qa:cast_wardrobe] clip {c_no} stages cast/hands without period headwear, sleeves, or clothing "
                "(add cap/hat/waistcoat/coat/sleeves/gloves/boots per R56-C/R63)"
            )
        verbs = _ACTIVE_MOTION_VERBS_RE.findall(scene_txt)
        if len(verbs) < int(c_lock["min_action_verbs"]):
            issues.append(
                f"[dynamic_qa:cast_motion] clip {c_no} has only {len(verbs)} physical action verb(s) {verbs}; "
                f"need >= {c_lock['min_action_verbs']} expressive 2-beat verbs (R56-M/R63)"
            )

    # 3. Direct Early Trauma / Event Reenactment Lock (R56-I / R63)
    min_early = int(contract.get("require_early_ceramic_reenactment_min_clips") or 0)
    if min_early > 0:
        if is_v7:
            early_cast_clips = [
                c_no
                for c_no, c in clips_by_num.items()
                if int(c.get("act") or 99) in (1, 2)
                and (
                    str(c.get("grammar") or "")
                    in (
                        "lowpoly_hands_closeup",
                        "lowpoly_pov_hands",
                        "porcelain_hands_closeup",
                        "porcelain_pov_hands",
                        "expressive_hands_closeup",
                        "expressive_pov_hands",
                        "expressive_hands_macro",
                        "expressive_reaction_closeup",
                    )
                    or bool(_LOWPOLY_CAST_RE.search(str(c.get("scene") or "")))
                    or bool(_PORCELAIN_V7_CAST_RE.search(str(c.get("scene") or "")))
                    or bool(_EXPRESSIVE_V8_CAST_RE.search(str(c.get("scene") or "")))
                    or (
                        is_expressive_v8
                        and (
                            bool(str(c.get("reference_image") or c.get("end_reference_image") or "").strip())
                            or str(c.get("flow_input_mode") or "").upper() in ("VIDEO_FRAMES", "VIDEO_REFERENCES")
                        )
                        and str(c.get("grammar") or "") in ("expressive_vinyl_world", "expressive_cameo_world", "expressive_split_contrast")
                        and bool(_EXPRESSIVE_V8_CONTEXT_SPLIT_CAST_RE.search(str(c.get("scene") or "")))
                    )
                )
            ]
        else:
            early_cast_clips = [
                c_no
                for c_no, c in clips_by_num.items()
                if int(c.get("act") or 99) in (1, 2) and _CERAMIC_CAST_RE.search(str(c.get("scene") or ""))
            ]
        if len(early_cast_clips) < min_early:
            issues.append(
                f"[dynamic_qa:early_impact] Acts 1-2 narrate physical trauma/events at sentences {contract['early_hook_sentences']} "
                f"but only {len(early_cast_clips)} clip(s) stage clothed cast reenactment (need >= {min_early}) (R56-I/R63)"
            )

    # 4. Anatomy Mention <-> Brain Visualization Alignment
    brain_grammars = {
        "arch_brain_maquette",
        "frosted_crystal_specimen",
        "lowpoly_matte_brain",
        "porcelain_living_brain",
        "expressive_xray_brain",
        "brain_simulator_3d",
    }
    for a_lock in contract["anatomy_locks"]:
        b_nums = a_lock["bound_clip_numbers"]
        ok_brain = False
        for n in b_nums:
            c = clips_by_num.get(n) or {}
            g = str(c.get("grammar") or "")
            sc = str(c.get("scene") or "").lower()
            if g in brain_grammars or any(
                k in sc for k in ("brain", "cortex", "subcortical", "limbic", "amygdala", "hippocamp", "fiber", "tract", "cable", "hemisphere")
            ):
                ok_brain = True
                break
        if not ok_brain:
            issues.append(
                f"[dynamic_qa:anatomy_sync] sentence {a_lock['sentence_index']} names {a_lock['anatomy_terms']} "
                f"but bound clip(s) {b_nums} do not depict 3D brain/neural anatomy (R62/R63)"
            )

    # 5. Expressive 2.5D v8 Delayed Brain Window ([60-85%] mechanism X-ray brain reveal, tolerance [55-90%]), 1x Cameo & Diegetic Text Allowlist
    if is_expressive_v8:
        from pipeline.config import (
            EXPRESSIVE_V8_BRAIN_REVEAL_TOLERANCE_FRAC,
            EXPRESSIVE_V8_NEURO_BRAIN_REVEAL_WINDOW_FRAC,
            is_brain_sim_only_plan,
            is_r74_neural_dive_v8_plan,
            is_r74b_neuro_pathway_v8_plan,
            is_r76_v8_plan,
            is_r85_flow_31_brain_plan,
            resolve_expressive_v8_topic_focus,
        )
        from pipeline.prompt_quality_v5 import validate_r74b_neuro_pathway_contract

        n_tot = max(1, len(rendered_clips))
        core_rev_s = (script_doc or {}).get("core_reveal_sentence_index") or (visual_plan or {}).get("core_reveal_sentence_index")
        allow_early_override = bool((visual_plan or {}).get("allow_early_brain_override")) or is_brain_sim_only_plan(visual_plan, script_doc)
        tol_lo, tol_hi = EXPRESSIVE_V8_BRAIN_REVEAL_TOLERANCE_FRAC
        eff_pid_pre = str((visual_plan or {}).get("project_id") or (script_doc or {}).get("project_id") or "").strip()
        is_r76_pre = is_r76_v8_plan(visual_plan, script_doc, project_id=eff_pid_pre)
        is_r85_pre = is_r85_flow_31_brain_plan(visual_plan, script_doc, project_id=eff_pid_pre)
        if is_brain_sim_only_plan(visual_plan, script_doc) or is_r85_pre:
            tol_lo, tol_hi = 0.0, 1.0
        elif is_r76_pre:
            tol_lo, tol_hi = 0.14, 0.90
        elif (
            is_r74b_neuro_pathway_v8_plan(visual_plan, script_doc, project_id=eff_pid_pre)
            and resolve_expressive_v8_topic_focus(visual_plan, script_doc) == "neuroscience"
        ):
            tol_lo = EXPRESSIVE_V8_NEURO_BRAIN_REVEAL_WINDOW_FRAC[0]
            tol_hi = max(tol_hi, EXPRESSIVE_V8_NEURO_BRAIN_REVEAL_WINDOW_FRAC[1])
        elif is_r74_neural_dive_v8_plan(visual_plan, script_doc, project_id=eff_pid_pre):
            tol_lo = min(tol_lo, 0.36)
        early_brains: list[int] = []
        window_brains: list[int] = []
        cameo_clips: list[int] = []
        core_brain_found = False
        for idx0, c in enumerate(rendered_clips):
            c_no = int(c.get("clip_number") or (idx0 + 1))
            g = str(c.get("grammar") or "")
            frac = idx0 / float(n_tot)
            frac_end = (idx0 + 1) / float(n_tot)
            if g in brain_grammars:
                if frac < tol_lo and not allow_early_override:
                    early_brains.append(c_no)
                if (tol_lo <= frac <= tol_hi) or (tol_lo <= frac_end <= tol_hi):
                    window_brains.append(c_no)
                if core_rev_s is not None:
                    try:
                        cr_i = int(core_rev_s)
                        s0_c = int(c.get("sentence_index") or 0)
                        s1_c = max(s0_c, int(c.get("end_sentence_index") or s0_c))
                        if s0_c <= cr_i <= s1_c:
                            core_brain_found = True
                    except (TypeError, ValueError):
                        pass
            if bool(c.get("cameo_easter_egg")):
                cameo_clips.append(c_no)
            d_allow = c.get("diegetic_text_allowlist") or []
            if len(d_allow) > 2 or any(len(str(tok).split()) > 2 for tok in d_allow):
                issues.append(
                    f"[dynamic_qa:diegetic_text] clip {c_no} exceeds <=2 diegetic keywords or <=2 words/token: {d_allow}"
                )
        if early_brains:
            issues.append(
                f"[dynamic_qa:v8_brain_ban] expressive_25d_v8 bans unapproved early brain CG before {int(tol_lo * 100)}%; early brain clips={early_brains}"
            )
        if core_rev_s is not None and not core_brain_found:
            issues.append(
                f"[dynamic_qa:v8_brain_core] core_reveal_sentence_index={core_rev_s} must bind to an expressive_xray_brain clip"
            )
        if not window_brains:
            issues.append(
                f"[dynamic_qa:v8_brain_reveal] expressive_25d_v8 requires >=1 expressive_xray_brain clip in the [{int(tol_lo * 100)}-{int(tol_hi * 100)}%] mechanism window"
            )
        if is_r76_pre or is_r85_pre:
            if len(cameo_clips) != 0:
                issues.append(
                    f"[dynamic_qa:v8_cameo] Rule R76 retires Mini-Cortex cameo; found {len(cameo_clips)} ({cameo_clips})"
                )
        elif len(cameo_clips) != 1:
            issues.append(
                f"[dynamic_qa:v8_cameo] expressive_25d_v8 requires cameo_easter_egg==True on exactly 1 clip; found {len(cameo_clips)} ({cameo_clips})"
            )
        issues.extend(
            validate_r74b_neuro_pathway_contract(
                visual_plan,
                rendered_clips,
                lines=sentences,
                script_doc=script_doc,
                project_id=eff_pid_pre,
            )
        )

    return issues


# ------------------------------------------------------------------------------
# 3. Gate 2: Clip-Harvest Multimodal CV & Feature Signature Verification
# ------------------------------------------------------------------------------
def _extract_sample_frames(mp4_path: Path, fracs: tuple[float, ...] = (0.15, 0.38, 0.62, 0.85)) -> tuple[list[np.ndarray], float]:
    cap = cv2.VideoCapture(str(mp4_path))
    if not cap.isOpened():
        return [], 0.0
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 24.0)
    fc = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    dur = fc / max(1.0, fps)
    frames: list[np.ndarray] = []
    for fr in fracs:
        idx = max(0, min(max(0, fc - 1), int(round(fc * fr))))
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ok, frm = cap.read()
        if ok and frm is not None:
            frames.append(frm)
    cap.release()
    return frames, dur


def is_r85_mid_cut_electric_arc_flash(
    neon_samples: list[float],
    *,
    camera_move: str = "",
) -> tuple[bool, float, float]:
    """Detects sudden mid-cut cyan arc flashes while exempting smooth push-in zoom onto matte #27D8FF lobes."""
    if len(neon_samples) < 3:
        return (False, float(np.max(neon_samples)) if neon_samples else 0.0, 1.0)
    n_p15 = float(np.percentile(neon_samples, 15))
    neon_max_ratio = float(np.max(neon_samples))
    neon_surge = neon_max_ratio / max(0.0005, n_p15)
    if not (neon_max_ratio >= 0.018 and (neon_max_ratio - n_p15) >= 0.012 and neon_surge >= 4.0):
        return (False, neon_max_ratio, neon_surge)

    steps = [neon_samples[i + 1] - neon_samples[i] for i in range(len(neon_samples) - 1)]
    span = max(1e-6, neon_max_ratio - float(np.min(neon_samples)))
    cam_norm = str(camera_move or "").lower()
    is_push_in_cam = any(tok in cam_norm for tok in ("push_in", "push-in", "zoom_in", "zoom-in", "dive", "approach"))
    is_smooth_zoom_expansion = (
        is_push_in_cam
        and neon_samples[0] >= 0.010
        and neon_samples[-1] >= 0.80 * neon_max_ratio
        and min(steps) >= -0.010
        and max(steps) <= min(0.035, 0.35 * span)
    )
    return (not is_smooth_zoom_expansion, neon_max_ratio, neon_surge)


def compute_green_turf_ratio(frame_bgr: np.ndarray, exclude_bottom_subtitles: bool = False) -> float:
    """Computes fraction of stadium green-turf pixels in the central diorama ROI."""
    h, w = frame_bgr.shape[:2]
    y1 = int(h * 0.60) if exclude_bottom_subtitles else int(h * 0.84)
    roi = frame_bgr[int(h * 0.16) : y1, int(w * 0.08) : int(w * 0.92)]
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    green_mask = (hsv[:, :, 0] >= 28) & (hsv[:, :, 0] <= 95) & (hsv[:, :, 1] >= 32) & (hsv[:, :, 2] >= 28)
    return float(np.mean(green_mask))


def compute_ceramic_highlight_ratio(frame_bgr: np.ndarray, exclude_bottom_subtitles: bool = False) -> float:
    """Computes fraction of matte-white/ivory ceramic miniature figure/prop highlights in central ROI."""
    h, w = frame_bgr.shape[:2]
    y1 = int(h * 0.58) if exclude_bottom_subtitles else int(h * 0.85)
    roi = frame_bgr[int(h * 0.16) : y1, int(w * 0.10) : int(w * 0.90)]
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    ivory_mask = (hsv[:, :, 1] <= 68) & (hsv[:, :, 2] >= 150)
    return float(np.mean(ivory_mask))


def measure_upward_impact_flow_pct(
    mp4_path: Path,
    t_start: float = 0.0,
    t_end: float | None = None,
) -> float:
    """
    Measures peak percentage (0..100) of upper-half (`[5%..55%]`) pixels moving fast upward
    (`vy < -2.2`, `mag > 2.8` on `180x320` grayscale) inside `[t_start, t_end]`.
    """
    from pipeline.media_cache import stage_local_file

    src_p = Path(mp4_path)
    local_p = stage_local_file(src_p)[0] if src_p.exists() else src_p
    cap = cv2.VideoCapture(str(local_p))
    if not cap.isOpened():
        return 0.0
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 24.0)
    fc = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    dur = fc / max(1.0, fps)
    s0 = max(0.0, float(t_start))
    s1 = float(dur if t_end is None else min(dur, float(t_end)))
    if s1 - s0 < 0.25:
        if cap is not None:
            cap.release()
            cap = None
        return 0.0
    f0 = max(0, int(round(s0 * fps)))
    f1 = min(max(0, fc - 1), int(round(s1 * fps)))
    step = max(1, int(round(fps * 0.12)))
    cap.set(cv2.CAP_PROP_POS_FRAMES, f0)
    sampled: list[np.ndarray] = []
    cur = f0
    while cur <= f1:
        ok, frm = cap.read()
        if not ok:
            break
        if (cur - f0) % step == 0:
            sampled.append(cv2.resize(cv2.cvtColor(frm, cv2.COLOR_BGR2GRAY), (180, 320)))
        cur += 1
    cap.release()
    if len(sampled) < 2:
        return 0.0
    peak_pct = 0.0
    for i in range(1, len(sampled)):
        flow = cv2.calcOpticalFlowFarneback(
            sampled[i - 1][16:176, :],
            sampled[i][16:176, :],
            None,
            0.5,
            2,
            13,
            2,
            5,
            1.1,
            0,
        )
        vy = flow[..., 1]
        mag = np.hypot(flow[..., 0], vy)
        pct = float(np.mean((vy < -2.2) & (mag > 2.8))) * 100.0
        if pct > peak_pct:
            peak_pct = pct
    return round(peak_pct, 3)


def measure_chapter_headline_bbox(frame_bgr: np.ndarray, min_glyph_h_px: int = 44) -> tuple[int, int, int]:
    """
    Measures `(rendered_width_px, left_margin_px, right_margin_px)` of a top `ChapterHeadline` or `AnatomyLabel`
    burned onto `frame_bgr`. Immune to pure-white overcast skies and scaled font sizes by requiring
    interior white glyph components bounded away from ROI borders and enclosed by a dark `#000000`
    stroke perimeter. Returns `(0, w, w)` if no headline/badge glyphs are active on this frame.
    """
    h, w = frame_bgr.shape[:2]
    sy = h / 1920.0
    sx = w / 1080.0
    y0 = max(0, int(round(155 * sy)))
    y1 = min(h, int(round(455 * sy)))
    roi = frame_bgr[y0:y1, :]
    roi_h = roi.shape[0]
    if roi.size == 0 or roi_h < 20:
        return 0, w, w
    white = (roi[:, :, 0] > 224) & (roi[:, :, 1] > 224) & (roi[:, :, 2] > 224)
    dark = ((roi[:, :, 0] < 110) & (roi[:, :, 1] < 110) & (roi[:, :, 2] < 110)).astype(np.uint8)
    dark_near = cv2.dilate(dark, np.ones((5, 5), np.uint8)) > 0
    nl, lbl, st, _ = cv2.connectedComponentsWithStats(white.astype(np.uint8), connectivity=8)
    min_h = max(12, int(round(int(min_glyph_h_px) * sy)))
    max_h = max(min_h + 10, int(round(185 * sy)))
    base_area = 42 if int(min_glyph_h_px) < 40 else 105
    min_area = max(16, int(round(base_area * sx * sy)))
    kern3 = np.ones((3, 3), np.uint8)
    xs: list[int] = []
    comp_count = 0
    for k in range(1, nl):
        x, y, bw, bh, area = st[k]
        if y <= 1 or (y + bh) >= (roi_h - 1):
            continue
        if min_h <= bh <= max_h and area >= min_area:
            px0 = max(0, x - 2)
            py0 = max(0, y - 2)
            px1 = min(w, x + bw + 2)
            py1 = min(roi_h, y + bh + 2)
            comp_pad = (lbl[py0:py1, px0:px1] == k).astype(np.uint8)
            ring = (cv2.dilate(comp_pad, kern3) > 0) & (comp_pad == 0)
            if np.any(ring) and float(np.mean(dark_near[py0:py1, px0:px1][ring])) >= 0.80:
                xs.extend([int(x), int(x + bw)])
                comp_count += 1
    if comp_count < 3 or not xs:
        return 0, w, w
    x_min = min(xs)
    x_max = max(xs)
    return int(x_max - x_min), int(x_min), int(w - x_max)


def _non_subtitle_scene_rois(
    frame_bgr: np.ndarray,
    has_top_overlay: bool = False,
    is_outro: bool = False,
    is_expressive_v8: bool = False,
    has_hero_stamp: bool = False,
) -> list[np.ndarray]:
    """
    Returns clean upper + lower scene bands covering the full viewport outside programmatic ASS text:
      - Outro sky card (`OutroTitle` at `Y ≈ 33%..47%`): `[3%..30%]` + `[49%..97%]`.
      - Expressive 2.5D v8 HERO Data Stamp (`Y ≈ 10%..62%`): `[76%..97%]`.
      - Expressive 2.5D v8 Anatomy Callout (`Y ≈ 11%..23%`): `[25%..57%]` + `[76%..97%]`.
      - Expressive 2.5D v8 (`Default` 102pt `MarginV=521` at `Y ≈ 60%..74%`, zero top headlines): `[3%..57%]` + `[76%..97%]`.
      - Top overlay active (`ChapterHeadline` or `SplitLeft/Right` at `Y ≈ 9%..22%`): `[23%..58%]` + `[69%..97%]`.
      - Standard speech cut (`Default` subtitle at `Y ≈ 59%..68%`): `[3%..58%]` + `[69%..97%]`.
    """
    h, w = frame_bgr.shape[:2]
    x0, x1 = int(w * 0.03), int(w * 0.97)
    if is_outro:
        bands = ((0.03, 0.30), (0.49, 0.97))
    elif is_expressive_v8:
        if has_hero_stamp:
            bands = ((0.76, 0.97),)
        elif has_top_overlay:
            bands = ((0.25, 0.57), (0.76, 0.97))
        else:
            bands = ((0.03, 0.57), (0.76, 0.97))
    elif has_top_overlay:
        bands = ((0.23, 0.58), (0.69, 0.97))
    else:
        bands = ((0.03, 0.58), (0.69, 0.97))
    rois: list[np.ndarray] = []
    for r0, r1 in bands:
        ya, yb = int(h * r0), int(h * r1)
        if yb - ya >= 24:
            rois.append(frame_bgr[ya:yb, x0:x1])
    return rois


def verify_clip_multimodal_contract(
    mp4_path: Path,
    clip_number: int,
    contract: dict[str, Any] | None,
) -> dict[str, Any]:
    """
    Gate 2 per-clip semantic/visual feature verifier run inside `flow_diorama_sharded_worker.py`
    immediately after downloading `clip_<clip_number>.mp4`.
    """
    frames, dur = _extract_sample_frames(mp4_path, fracs=(0.12, 0.34, 0.56, 0.78, 0.90))
    if len(frames) < 3 or dur < 3.5:
        return {"passed": False, "reason": f"bad_clip_decode:frames={len(frames)},dur={dur:.2f}"}

    if not contract:
        return {"passed": True, "checks": []}

    is_v7 = bool(contract.get("is_v7"))
    is_expressive_v8 = bool(contract.get("is_expressive_v8"))
    checks_run: list[str] = []
    # Check analogy visual signatures bound to this clip_number
    for a_lock in contract.get("analogy_locks", []):
        if int(clip_number) in [int(x) for x in a_lock.get("bound_clip_numbers", [])]:
            sig = a_lock.get("cv_signature")
            if sig == "green_stadium_turf":
                max_green = max(compute_green_turf_ratio(f, exclude_bottom_subtitles=False) for f in frames)
                checks_run.append(f"green_turf={max_green:.4f}")
                if max_green < 0.020:
                    r_msg = f"missing_green_stadium_turf:max_green={max_green:.4f}<0.020"
                    return {"passed": False, "reason": r_msg, "issues": [r_msg]}

    # Check cold-open upward piercing/blast optical flow signature
    for imp_lock in contract.get("cold_open_impact_locks", []):
        if int(imp_lock.get("clip_number") or 0) == int(clip_number):
            min_up = float(imp_lock.get("min_upward_fast_pct") or 2.5)
            up_pct = measure_upward_impact_flow_pct(mp4_path)
            checks_run.append(f"upward_impact_flow={up_pct:.2f}%")
            if up_pct < min_up:
                r_msg = f"missing_upward_rod_impact_motion:up_pct={up_pct:.2f}%<{min_up:.2f}%"
                return {"passed": False, "reason": r_msg, "issues": [r_msg]}

    # Check cast highlight / bright world presence
    for c_lock in contract.get("cast_clip_locks", []):
        if int(c_lock.get("clip_number") or 0) == int(clip_number):
            if is_v7 or c_lock.get("cv_signature") in ("bright_lowpoly_world", "bright_porcelain_world", "expressive_25d_world"):
                mean_y = float(np.mean([float(np.mean(cv2.cvtColor(f, cv2.COLOR_BGR2GRAY))) for f in frames]))
                min_cast_y = 26.0 if (is_expressive_v8 or c_lock.get("cv_signature") == "expressive_25d_world") else 78.0
                checks_run.append(f"bright_v7_y={mean_y:.1f}")
                if mean_y < min_cast_y:
                    r_msg = f"dark_void_in_v7_cast_clip:mean_y={mean_y:.1f}<{min_cast_y:.1f}"
                    return {"passed": False, "reason": r_msg, "issues": [r_msg]}
            else:
                max_cer = max(compute_ceramic_highlight_ratio(f, exclude_bottom_subtitles=False) for f in frames)
                checks_run.append(f"ceramic_highlight={max_cer:.4f}")
                if max_cer < 0.004:
                    r_msg = f"missing_ceramic_figure_contrast:ratio={max_cer:.4f}<0.004"
                    return {"passed": False, "reason": r_msg, "issues": [r_msg]}

    # Check R67 source-reenactment dHash non-infringement lock across (0.15, 0.50, 0.85)
    reenact_lock = contract.get("reenactment_dhash_lock")
    if isinstance(reenact_lock, dict):
        src_dhashes = [str(x) for x in (reenact_lock.get("source_dhash_64_list") or []) if str(x)]
        min_req_bits = int(reenact_lock.get("min_dhash_bits") or REENACT_MIN_DHASH_DISTANCE)
        if src_dhashes:
            from pipeline.reference_image_qa import _dhash_64, _hamming_hex

            cap_dh = cv2.VideoCapture(str(mp4_path))
            min_clip_dhash = 64
            if cap_dh.isOpened():
                fc_dh = int(cap_dh.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
                for frac in (0.15, 0.50, 0.85):
                    cap_dh.set(cv2.CAP_PROP_POS_FRAMES, max(0, int(fc_dh * frac)))
                    ok_dh, frm_dh = cap_dh.read()
                    if ok_dh and frm_dh is not None:
                        dh_val = _dhash_64(cv2.cvtColor(frm_dh, cv2.COLOR_BGR2GRAY))
                        dist_bits = min(_hamming_hex(dh_val, sdh) for sdh in src_dhashes)
                        min_clip_dhash = min(min_clip_dhash, dist_bits)
                cap_dh.release()
            checks_run.append(f"reenact_dhash={min_clip_dhash}")
            if min_clip_dhash < min_req_bits:
                r_msg = f"reenact_dhash_too_close:{min_clip_dhash}<{min_req_bits}"
                return {"passed": False, "reason": r_msg, "issues": [r_msg]}

    return {"passed": True, "checks": checks_run, "issues": []}


# ------------------------------------------------------------------------------
# 4. Gate 3: Final Rendered MP4 12-Axis Hard Gate (DQ1-DQ12)
# ------------------------------------------------------------------------------
def _read_frame_at_sec(cap: cv2.VideoCapture, fps: float, total_fc: int, t_sec: float) -> np.ndarray | None:
    f_idx = max(0, min(max(0, total_fc - 1), int(round(t_sec * fps))))
    cap.set(cv2.CAP_PROP_POS_FRAMES, f_idx)
    ok, frm = cap.read()
    return frm if (ok and frm is not None) else None


def _parse_ass_ts_sec(ts: str) -> float:
    m = re.match(r"(\d+):(\d+):([\d.]+)", ts.strip())
    if not m:
        return 0.0
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))


def _asr_word_timeline_from_mp4(mp4_path: Path) -> list[tuple[float, float, str]]:
    """Extracts 16kHz mono audio from final MP4 and transcribes word timestamps via shared faster-whisper cache."""
    from pipeline.media_cache import cached_asr_word_timeline

    return cached_asr_word_timeline(Path(mp4_path))


def _is_unified_brain_cut(ct: dict[str, Any], vp_ct: dict[str, Any] | None = None) -> bool:
    """Return True if an EDL cut (+ visual_plan clip spec) is a 3D brain cut (R76 Blender or R85+ Google Flow)."""
    vp_d = vp_ct if isinstance(vp_ct, dict) else {}
    g_ct = str(ct.get("grammar") or vp_d.get("grammar") or "").strip()
    eng_ct = str(ct.get("render_engine") or vp_d.get("render_engine") or "").strip().lower()
    brain_flag = ct.get("brain_clip") if ct.get("brain_clip") is not None else vp_d.get("brain_clip")
    r85_flag = ct.get("r85_brain_clip") if ct.get("r85_brain_clip") is not None else vp_d.get("r85_brain_clip")
    return (
        g_ct in ("brain_simulator_3d", "expressive_xray_brain")
        or eng_ct == "blender_3d_simulator"
        or bool(brain_flag)
        or bool(r85_flag)
    )


def verify_final_mp4_against_contract(
    project_id_or_dir: str | Path,
    run_asr_sync: bool = True,
    save_report: bool = True,
    contract: dict[str, Any] | None = None,
    cpu_budget: int | None = None,
) -> dict[str, Any]:
    """
    Executes the 12-Axis Dynamic Episode Hard Gate (`DQ1-DQ12`) against the final rendered
    `05_assembly/final_shorts_1080x1920.mp4`. Any single failed gate marks `passed=False`.
    In Schema v7 (`porcelain_cinematic_v7` & `lowpoly_pastel_v7`), inspects 100% of all EDL cuts
    (including outro) across full non-subtitle scene bands, verifies EDL camera-move ratios,
    cold-open upward impact motion, Escher dual-edge close-up safety, neon-green spill safety,
    and `ChapterHeadline` horizontal safe margins.
    """
    import wave

    from pipeline.flow_diorama_sharded_worker import (
        _max_horizontal_plaque_glyph_run,
        compute_brain_margin_saturation,
        compute_neon_green_spill_ratio,
        compute_porcelain_flesh_leak_ratio,
        detect_escher_dual_edge_closeup,
        detect_transient_top_intrusion_pov,
        detect_unintended_horizontal_split_seam,
    )
    from pipeline.flow_prompt_builder import build_diorama_v6_prompts

    p_dir = Path(project_id_or_dir) if Path(str(project_id_or_dir)).exists() else (PROJECTS_DIR / str(project_id_or_dir))
    final_mp4 = p_dir / "05_assembly" / "final_shorts_1080x1920.mp4"
    edl_path = p_dir / "05_assembly" / "edit_decision_list.json"
    vr_path = p_dir / "04_audio" / "voice_report.json"
    ass_path = p_dir / "04_audio" / "subtitles.ass"
    script_path = p_dir / "02_script" / "script.json"
    vp_path = p_dir / "03_visuals" / "visual_plan.json"

    if not final_mp4.exists():
        raise FileNotFoundError(f"Final MP4 missing for dynamic QA: {final_mp4}")

    from pipeline.diorama_assembler import verify_script_audio_freshness

    verify_script_audio_freshness(p_dir, context="episode-qa")

    script_doc = json.loads(script_path.read_text(encoding="utf-8"))
    vp = json.loads(vp_path.read_text(encoding="utf-8"))
    edl = json.loads(edl_path.read_text(encoding="utf-8"))
    vr = json.loads(vr_path.read_text(encoding="utf-8"))
    is_expressive_v8 = (
        is_expressive_v8_plan(vp, edl, script_doc)
        or int(edl.get("schema") or 6) >= PROMPT_SCHEMA_VERSION_V8
    )
    is_v7 = (
        is_expressive_v8
        or is_diorama_v7_plan(vp)
        or is_diorama_v7_plan(script_doc)
        or int(edl.get("schema") or 6) >= PROMPT_SCHEMA_VERSION_V7
    )
    is_porcelain = bool(is_v7 and (is_expressive_v8 or is_porcelain_v7_plan(vp, edl, script_doc)))
    sentences = [str(s).strip() for s in (script_doc.get("sentences") or []) if str(s).strip()]
    if not sentences and isinstance(script_doc.get("acts"), list):
        sentences = [
            str(s).strip()
            for act in script_doc["acts"]
            if isinstance(act, dict)
            for s in (act.get("sentences") or [])
            if str(s).strip()
        ]
    rendered_clips = build_diorama_v6_prompts(vp, sentences)
    rendered_by_num = {int(rc.get("clip_number") or idx): rc for idx, rc in enumerate(rendered_clips, start=1)}
    vp_by_num = {
        int(vc.get("clip_number") or idx): vc
        for idx, vc in enumerate(vp.get("clips") or [], start=1)
        if isinstance(vc, dict)
    }
    if contract is None:
        if save_report:
            _, contract = write_episode_qa_contract(p_dir, vp, sentences, rendered_clips, script_doc=script_doc)
        else:
            contract = compile_episode_qa_contract(vp, sentences, rendered_clips, script_doc=script_doc)

    pre_issues = verify_pre_flow_contract(vp, sentences, rendered_clips, script_doc=script_doc)
    is_synth_test = vr.get("engine") in ("test_stub", "kokoro-onnx") and not (p_dir / "04_audio" / "tts_diorama" / "clip_1.wav").exists()

    ass_txt = ass_path.read_text(encoding="utf-8") if ass_path.exists() else ""
    chapter_spans: list[tuple[float, float]] = []
    anatomy_label_spans: list[tuple[float, float]] = []
    hook_title_spans: list[tuple[float, float]] = []
    for ln in ass_txt.splitlines():
        if ln.startswith("Dialogue:"):
            parts = ln.split(",", 9)
            if len(parts) >= 10:
                if ",ChapterHeadline," in ln:
                    chapter_spans.append((_parse_ass_ts_sec(parts[1]), _parse_ass_ts_sec(parts[2])))
                elif ",AnatomyLabel," in ln:
                    anatomy_label_spans.append((_parse_ass_ts_sec(parts[1]), _parse_ass_ts_sec(parts[2])))
                elif ",HookTitle," in ln:
                    hook_title_spans.append((_parse_ass_ts_sec(parts[1]), _parse_ass_ts_sec(parts[2])))
    data_stamp_spans = [
        (float(ds[0]), float(ds[1]))
        for ds in (edl.get("data_stamp_spans") or [])
        if isinstance(ds, (list, tuple)) and len(ds) >= 2
    ]
    top_overlay_spans = chapter_spans + anatomy_label_spans + hook_title_spans + data_stamp_spans

    # Stage MP4 once on local /tmp SSD and share single-pass decoded frames (Speed-4)
    from pipeline.media_cache import decode_needed_frames, stage_local_file

    local_mp4, mp4_sha = stage_local_file(final_mp4)
    if True:
        cap: cv2.VideoCapture | None = None
        probe_cap = cv2.VideoCapture(str(local_mp4))
        fps = float(probe_cap.get(cv2.CAP_PROP_FPS) or (DIORAMA_V7_VIDEO_FPS if is_v7 else VIDEO_FPS))
        total_fc = int(probe_cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        probe_cap.release()

        cuts = edl.get("cuts", [])
        cuts_by_sent: dict[int, list[dict[str, Any]]] = {}
        for c in cuts:
            if not c.get("outro_sky_card"):
                s0_c = int(c["sentence_index"])
                s1_c = max(s0_c, int(c.get("end_sentence_index") or s0_c))
                for s_k in range(s0_c, s1_c + 1):
                    cuts_by_sent.setdefault(s_k, []).append(c)

        asr_words = _asr_word_timeline_from_mp4(local_mp4) if run_asr_sync else []

        def _sec_to_fidx(t_sec: float) -> int:
            return max(0, min(max(0, total_fc - 1), int(round(t_sec * fps))))

        # Pre-collect all frame indices needed across DQ1, DQ2, DQ5, DQ7-DQ9, DQ10 for a single fast sequential decode pass
        needed_fidxs: set[int] = set()
        for a_lock in contract["analogy_locks"]:
            s_cuts = cuts_by_sent.get(int(a_lock["sentence_index"]), [])
            if s_cuts:
                c_t0_p = float(s_cuts[0]["out_start_sec"])
                c_t1_p = float(s_cuts[-1]["out_end_sec"])
                mid_p = 0.5 * (c_t0_p + c_t1_p)
                needed_fidxs.add(_sec_to_fidx(mid_p))
                if asr_words:
                    kw_toks_p = [re.sub(r"[^a-z0-9]", "", w.lower()) for w in a_lock["spoken_phrase"].split() if w.strip()]
                    if kw_toks_p:
                        hits_p = [t0 for t0, _t1, tok in asr_words if tok == kw_toks_p[0] and (c_t0_p - 1.8) <= t0 <= (c_t1_p + 1.8)]
                        if hits_p:
                            near_p = min(hits_p, key=lambda x: abs(x - mid_p))
                            if c_t0_p - 0.40 <= near_p <= c_t1_p + 0.40:
                                needed_fidxs.add(_sec_to_fidx(max(c_t0_p + 0.08, min(c_t1_p - 0.08, near_p))))
        for c_lock in contract["cast_clip_locks"]:
            c_num = int(c_lock["clip_number"])
            for mc in cuts:
                if int(mc.get("clip_index") or 0) == c_num:
                    needed_fidxs.add(_sec_to_fidx(0.5 * (float(mc["out_start_sec"]) + float(mc["out_end_sec"]))))
        if is_v7:
            hstack_cuts_pre = [c for c in cuts if c.get("mode") == "split_hstack"]
            if hstack_cuts_pre:
                hc0 = hstack_cuts_pre[0]
                needed_fidxs.add(_sec_to_fidx(0.5 * (float(hc0["out_start_sec"]) + float(hc0["out_end_sec"]))))
            for ov_s0, ov_s1 in top_overlay_spans:
                needed_fidxs.add(_sec_to_fidx(0.5 * (ov_s0 + ov_s1)))
        inspected_pre = cuts if is_v7 else [c for c in cuts[::3] if not c.get("outro_sky_card")]
        for c in inspected_pre:
            cs_p = float(c["out_start_sec"])
            ce_p = float(c["out_end_sec"])
            t0_p = cs_p + 0.08
            t1_p = max(t0_p + 0.20, ce_p - 0.08)
            tm_p = 0.5 * (t0_p + t1_p)
            needed_fidxs.add(_sec_to_fidx(t0_p))
            needed_fidxs.add(_sec_to_fidx(tm_p))
            needed_fidxs.add(_sec_to_fidx(t1_p))
            if is_v7 and not is_synth_test and (
                (ce_p - cs_p) >= 2.20 or str(c.get("grammar") or "") in ("lowpoly_pov_hands", "porcelain_pov_hands")
            ):
                needed_fidxs.add(_sec_to_fidx(t0_p + 0.25 * (t1_p - t0_p)))
                needed_fidxs.add(_sec_to_fidx(t0_p + 0.75 * (t1_p - t0_p)))
            if is_expressive_v8 and not is_synth_test and not bool(c.get("outro_sky_card")):
                for ts_q in np.arange(t0_p, t1_p + 1e-6, 0.25):
                    needed_fidxs.add(_sec_to_fidx(float(ts_q)))
        if is_expressive_v8 and not is_synth_test and len(cuts) >= 2:
            for c_bnd in cuts[:-1]:
                tb_p = float(c_bnd["out_end_sec"])
                for dt_p in (-0.36, -0.16, -0.06, 0.24):
                    needed_fidxs.add(_sec_to_fidx(max(0.0, tb_p + dt_p)))

        _d_fps, _d_fc, frame_cache = decode_needed_frames(local_mp4, mp4_sha, needed_fidxs)
        if _d_fc > 0:
            fps = _d_fps
            total_fc = _d_fc

        def _get_frame(t_sec: float) -> np.ndarray | None:
            nonlocal cap
            f_i = _sec_to_fidx(t_sec)
            if f_i in frame_cache:
                return frame_cache[f_i]
            if cap is None:
                cap = cv2.VideoCapture(str(local_mp4))
            frm_fb = _read_frame_at_sec(cap, fps, total_fc, t_sec)
            if frm_fb is not None:
                frame_cache[f_i] = frm_fb
            return frm_fb

        # DQ1: Literal Analogy Spoken-Timestamp <-> Decoded Frame Visual Verification
        dq1_failures: list[str] = []
        for a_lock in contract["analogy_locks"]:
            s_idx = int(a_lock["sentence_index"])
            s_cuts = cuts_by_sent.get(s_idx, [])
            if not s_cuts:
                dq1_failures.append(f"sentence {s_idx} ('{a_lock['spoken_phrase']}') has no EDL cut")
                continue
            c_t0 = float(s_cuts[0]["out_start_sec"])
            c_t1 = float(s_cuts[-1]["out_end_sec"])
            mid_t = 0.5 * (c_t0 + c_t1)

            if asr_words:
                kw_tokens = [re.sub(r"[^a-z0-9]", "", w.lower()) for w in a_lock["spoken_phrase"].split() if w.strip()]
                if kw_tokens:
                    target_tok = kw_tokens[0]
                    hits = [t0 for t0, _t1, tok in asr_words if tok == target_tok and (c_t0 - 1.8) <= t0 <= (c_t1 + 1.8)]
                    if hits:
                        nearest = min(hits, key=lambda x: abs(x - mid_t))
                        if not (c_t0 - 0.40 <= nearest <= c_t1 + 0.40):
                            dq1_failures.append(
                                f"ASR '{a_lock['spoken_phrase']}' spoken at {nearest:.2f}s outside EDL cut [{c_t0:.2f}, {c_t1:.2f}]"
                            )
                        else:
                            mid_t = max(c_t0 + 0.08, min(c_t1 - 0.08, nearest))

            frm = _get_frame(mid_t)
            if frm is None:
                dq1_failures.append(f"could not decode frame at {mid_t:.2f}s for '{a_lock['spoken_phrase']}'")
            elif a_lock["cv_signature"] == "green_stadium_turf":
                g_ratio = compute_green_turf_ratio(frm, exclude_bottom_subtitles=True)
                if g_ratio < 0.018:
                    dq1_failures.append(
                        f"'{a_lock['spoken_phrase']}' frame @ {mid_t:.2f}s lacks green turf (ratio={g_ratio:.4f} < 0.018)"
                    )

        # DQ2: Clothed Cast & Iconic Cold-Open Impact Cuts Verification
        dq2_failures: list[str] = [x for x in pre_issues if "cast_" in x or "early_impact" in x]
        min_dq2_y = 26.0 if is_expressive_v8 else 75.0
        for c_lock in contract["cast_clip_locks"]:
            c_num = int(c_lock["clip_number"])
            matching_cuts = [c for c in cuts if int(c.get("clip_index") or 0) == c_num]
            for mc in matching_cuts:
                mt = 0.5 * (float(mc["out_start_sec"]) + float(mc["out_end_sec"]))
                frm = _get_frame(mt)
                if frm is not None:
                    if is_v7:
                        y_m = float(np.mean(cv2.cvtColor(frm[: int(frm.shape[0] * 0.60), :], cv2.COLOR_BGR2GRAY)))
                        if y_m < min_dq2_y:
                            dq2_failures.append(f"clip {c_num} @ {mt:.2f}s dark-void leak (mean_y={y_m:.1f} < {min_dq2_y:.1f})")
                    elif compute_ceramic_highlight_ratio(frm, exclude_bottom_subtitles=True) < 0.003:
                        dq2_failures.append(f"clip {c_num} @ {mt:.2f}s lacks ceramic figure highlight contrast")

        if is_v7 and not is_synth_test:
            for imp_lock in contract.get("cold_open_impact_locks", []):
                c_num = int(imp_lock["clip_number"])
                min_up = float(imp_lock.get("min_upward_fast_pct") or 2.5)
                matching_cuts = [c for c in cuts if int(c.get("clip_index") or 0) == c_num]
                if not matching_cuts:
                    dq2_failures.append(f"cold-open impact clip {c_num} missing from EDL")
                for mc in matching_cuts:
                    up_pct = measure_upward_impact_flow_pct(
                        local_mp4,
                        t_start=float(mc["out_start_sec"]) + 0.04,
                        t_end=float(mc["out_end_sec"]) - 0.04,
                    )
                    if up_pct < min_up:
                        dq2_failures.append(
                            f"cut {mc['cut_index']} (clip {c_num}) lacks cold-open upward impact motion "
                            f"(upward_fast_pct={up_pct:.2f}% < {min_up:.2f}%)"
                        )

        # DQ3: Anatomy Mention <-> 3D Brain Cut Sync (+ v8 [0-70%] brain ban / [70-85%] X-ray reveal)
        brain_grammars = {
            "arch_brain_maquette",
            "frosted_crystal_specimen",
            "lowpoly_matte_brain",
            "porcelain_living_brain",
            "expressive_xray_brain",
            "brain_simulator_3d",
        }
        dq3_failures: list[str] = [x for x in pre_issues if "anatomy_sync" in x or "v8_brain_" in x]
        for an_lock in contract["anatomy_locks"]:
            s_cuts = cuts_by_sent.get(int(an_lock["sentence_index"]), [])
            if not any(str(c.get("grammar")) in brain_grammars for c in s_cuts):
                dq3_failures.append(f"sentence {an_lock['sentence_index']} ({an_lock['anatomy_terms']}) not mapped to brain cut in EDL")
        if is_expressive_v8 and cuts:
            from pipeline.config import (
                EXPRESSIVE_V8_BRAIN_REVEAL_TOLERANCE_FRAC,
                EXPRESSIVE_V8_NEURO_BRAIN_REVEAL_WINDOW_FRAC,
                is_brain_sim_only_plan,
                is_r76_v8_plan,
                resolve_expressive_v8_topic_focus,
            )

            ep_tot_dur = max(1.0, float(edl.get("total_duration_sec") or cuts[-1].get("out_end_sec") or 60.0))
            core_rev_s = (script_doc or {}).get("core_reveal_sentence_index") or (vp or {}).get("core_reveal_sentence_index")
            allow_early_b = bool((vp or {}).get("allow_early_brain_override")) or is_brain_sim_only_plan(vp, script_doc)
            tol_lo_b, tol_hi_b = EXPRESSIVE_V8_BRAIN_REVEAL_TOLERANCE_FRAC
            from pipeline.config import is_r85_flow_31_brain_plan

            if is_brain_sim_only_plan(vp, script_doc):
                tol_lo_b, tol_hi_b = 0.0, 1.0
            elif is_r85_flow_31_brain_plan(vp, script_doc, project_id=p_dir.name):
                tol_lo_b, tol_hi_b = 0.06, 0.96
            elif is_r76_v8_plan(vp, script_doc, project_id=p_dir.name):
                tol_lo_b, tol_hi_b = 0.14, 0.90
            elif resolve_expressive_v8_topic_focus(vp, script_doc, edl) == "neuroscience":
                tol_lo_b = min(tol_lo_b, float(EXPRESSIVE_V8_NEURO_BRAIN_REVEAL_WINDOW_FRAC[0]))
            all_b_cuts = [c for c in cuts if str(c.get("grammar") or "") in brain_grammars]
            early_b_cuts = [
                int(c["cut_index"])
                for c in all_b_cuts
                if float(c.get("out_start_sec") or 0.0) < tol_lo_b * ep_tot_dur
                and not allow_early_b
            ]
            reveal_b_cuts = [
                int(c["cut_index"])
                for c in all_b_cuts
                if float(c.get("out_end_sec") or 0.0) >= tol_lo_b * ep_tot_dur
                and float(c.get("out_start_sec") or 0.0) <= tol_hi_b * ep_tot_dur
            ]
            if early_b_cuts:
                dq3_failures.append(
                    f"early brain CG cuts before {int(tol_lo_b * 100)}% duration in expressive_25d_v8: {early_b_cuts}"
                )
            if core_rev_s is not None:
                try:
                    cr_i = int(core_rev_s)
                    cr_cuts = [
                        c
                        for c in all_b_cuts
                        if int(c.get("sentence_index") or 0)
                        <= cr_i
                        <= max(int(c.get("sentence_index") or 0), int(c.get("end_sentence_index") or c.get("sentence_index") or 0))
                    ]
                    if not cr_cuts:
                        dq3_failures.append(
                            f"core_reveal_sentence_index={cr_i} does not overlap any expressive_xray_brain cut in EDL"
                        )
                except (TypeError, ValueError):
                    pass
            if not reveal_b_cuts:
                dq3_failures.append(
                    f"missing expressive_xray_brain cut in [{int(tol_lo_b * 100)}-{int(tol_hi_b * 100)}%] mechanism window of EDL"
                )

        # DQ4: Brisk Storyteller Tempo (WPM)
        total_words = sum(len(s.split()) for s in sentences)
        speech_end = max(1.0, float(vr.get("speech_end_sec") or edl.get("total_duration_sec") or 160.0))
        measured_wpm = round(total_words / (speech_end / 60.0), 1)
        t_targets = contract["tempo_targets"]
        dq4_ok = True if is_synth_test else (t_targets["wpm_min"] <= measured_wpm <= t_targets["wpm_max"])

        # DQ5: Dynamic Cut Rhythm, EDL Camera Ratios & Split-Screen Geometry
        speech_durs = [float(c["duration_sec"]) for c in cuts if not c.get("outro_sky_card")]
        single_sent_durs = [
            float(c["duration_sec"])
            for c in cuts
            if not c.get("outro_sky_card")
            and int(c.get("end_sentence_index") or c.get("sentence_index") or 0) == int(c.get("sentence_index") or 0)
        ]
        all_cut_durs = [float(c["duration_sec"]) for c in cuts]
        avg_cut = round(float(np.mean(speech_durs)), 3) if speech_durs else 99.0
        cut_cv = round(float(np.std(all_cut_durs) / max(1e-6, np.mean(all_cut_durs))), 4) if all_cut_durs else 0.0
        fast_ratio = round(sum(1 for d in speech_durs if d <= t_targets["fast_cut_threshold_sec"]) / max(1, len(speech_durs)), 3)
        min_cut = round(min(all_cut_durs, default=0.0), 3)
        max_cut = round(max(speech_durs, default=99.0), 3)
        max_single_sent_cut = round(max(single_sent_durs, default=0.0), 3)
        hstack_divider_ok = True
        all_cuts_have_camera = True
        locked_cam_ratio = 0.0
        zoom_cam_ratio = 0.0
        pan_left_cuts = 0
        pan_right_cuts = 0
        if is_v7:
            allowed_cams_dq5 = (
                set(DIORAMA_V7_CAMERA_MOVES) | set(EXPRESSIVE_V8_CAMERA_MOVES)
                if is_expressive_v8
                else set(DIORAMA_V7_CAMERA_MOVES)
            )
            all_cuts_have_camera = bool(cuts) and all(
                str(c.get("camera_move") or "") in allowed_cams_dq5 for c in cuts
            )
            cam_counts_edl: dict[str, int] = {m: 0 for m in allowed_cams_dq5}
            for c in cuts:
                cm = str(c.get("camera_move") or "")
                if cm in cam_counts_edl:
                    cam_counts_edl[cm] += 1
            n_edl_tot = max(1, len(cuts))
            locked_cam_ratio = round(cam_counts_edl.get("locked_tripod", 0) / float(n_edl_tot), 4)
            zoom_cam_ratio = round(
                (
                    cam_counts_edl.get("gentle_push_in", 0)
                    + cam_counts_edl.get("clean_pullback_reveal", 0)
                    + cam_counts_edl.get("portal_zoom_in", 0)
                    + cam_counts_edl.get("snap_zoom_in", 0)
                )
                / float(n_edl_tot),
                4,
            )
            pan_left_cuts = cam_counts_edl.get("pan_left", 0)
            pan_right_cuts = cam_counts_edl.get("pan_right", 0)
            allow_legacy_v8 = bool(
                (vp or {}).get("allow_legacy_v8_clip_count")
                or (script_doc or {}).get("allow_legacy_v8_clip_count")
                or (edl or {}).get("allow_legacy_v8_clip_count")
            )
            flight_3d_ratio = 0.0
            first_cut_dur_edl = round(float(cuts[0]["duration_sec"]), 3) if cuts else 0.0
            first_15s_max_cut_edl = round(
                max(
                    (
                        float(c["duration_sec"])
                        for c in cuts
                        if float(c.get("out_start_sec") or 0.0) < 15.0 and not c.get("outro_sky_card")
                    ),
                    default=0.0,
                ),
                3,
            )
            if is_expressive_v8:
                from pipeline.config import (
                    EXPRESSIVE_V8_3D_FLIGHT_MOVES,
                    EXPRESSIVE_V8_FIRST_15S_MAX_CUT_SEC,
                    EXPRESSIVE_V8_FIRST_15S_MIN_CUTS,
                    EXPRESSIVE_V8_FIRST_CUT_MAX_SEC,
                    EXPRESSIVE_V8_LEGACY_FIRST_15S_MAX_CUT_SEC,
                    EXPRESSIVE_V8_LEGACY_FIRST_CUT_MAX_SEC,
                    EXPRESSIVE_V8_MIN_3D_FLIGHT_RATIO,
                    is_r72_open_world_v8_plan,
                )

                is_r72_dq5 = is_r72_open_world_v8_plan(vp, script_doc, project_id=p_dir.name)
                eff_first_cap_dq5 = float(
                    t_targets.get("first_cut_max_sec")
                    or (EXPRESSIVE_V8_FIRST_CUT_MAX_SEC if is_r72_dq5 else EXPRESSIVE_V8_LEGACY_FIRST_CUT_MAX_SEC)
                )
                eff_f15_cap_dq5 = float(
                    t_targets.get("first_15s_max_cut_sec")
                    or (EXPRESSIVE_V8_FIRST_15S_MAX_CUT_SEC if is_r72_dq5 else EXPRESSIVE_V8_LEGACY_FIRST_15S_MAX_CUT_SEC)
                )
                first_15s_cuts_cnt = sum(
                    1
                    for c in cuts
                    if float(c.get("out_start_sec") or 0.0) < 15.0 and not c.get("outro_sky_card")
                )
                first_15s_count_ok = (
                    True
                    if (not is_r72_dq5 or is_synth_test or float(edl.get("total_duration_sec") or 0.0) < 18.0)
                    else (first_15s_cuts_cnt >= int(t_targets.get("first_15s_min_cuts", EXPRESSIVE_V8_FIRST_15S_MIN_CUTS)))
                )
                is_brain_only_dq5 = is_brain_sim_only_plan(vp, script_doc)
                flight_3d_cuts = sum(
                    1
                    for c in cuts
                    if bool(c.get("is_3d_flight"))
                    or (is_brain_only_dq5 and str(c.get("grammar") or "") == "brain_simulator_3d")
                    or str(c.get("camera_move") or "") in EXPRESSIVE_V8_3D_FLIGHT_MOVES
                    or bool(str(c.get("end_reference_image") or "").strip())
                )
                flight_3d_ratio = round(flight_3d_cuts / float(max(1, len(cuts))), 4)
                first_cam_moving = bool(cuts) and str(cuts[0].get("camera_move") or "") != "locked_tripod"
                camera_ratios_ok = (
                    all_cuts_have_camera
                    and len({str(c.get("camera_move") or "") for c in cuts}) >= 2
                    and (
                        allow_legacy_v8
                        or is_synth_test
                        or (
                            first_cam_moving
                            and first_15s_count_ok
                            and flight_3d_ratio >= float(EXPRESSIVE_V8_MIN_3D_FLIGHT_RATIO)
                            and first_cut_dur_edl <= eff_first_cap_dq5 + 0.05
                            and first_15s_max_cut_edl <= eff_f15_cap_dq5 + 0.15
                        )
                    )
                )
            else:
                camera_ratios_ok = (
                    all_cuts_have_camera
                    and locked_cam_ratio >= DIORAMA_V7_LOCKED_CAMERA_MIN_RATIO
                    and zoom_cam_ratio <= DIORAMA_V7_ZOOM_CAMERA_MAX_RATIO
                    and pan_left_cuts >= 1
                    and pan_right_cuts >= 1
                )

            hstack_cuts = [c for c in cuts if c.get("mode") == "split_hstack"]
            if not hstack_cuts:
                hstack_divider_ok = True if is_expressive_v8 else False
            else:
                hc = hstack_cuts[0]
                ht = 0.5 * (float(hc["out_start_sec"]) + float(hc["out_end_sec"]))
                hfrm = _get_frame(ht)
                if hfrm is None:
                    hstack_divider_ok = False
                else:
                    # Verify 6px black vertical divider at center x=[538..542] in clean mid-height band [30%..55%]
                    hh, hw = hfrm.shape[:2]
                    div_strip = cv2.cvtColor(hfrm[int(hh * 0.30) : int(hh * 0.55), hw // 2 - 2 : hw // 2 + 2], cv2.COLOR_BGR2GRAY)
                    hstack_divider_ok = float(np.mean(div_strip)) <= 24.0
            single_sent_cap = float(t_targets.get("max_single_sentence_cut_sec", DIORAMA_V7_MID_ACT_MAX_CUT_SEC))
            min_cut_floor = float(
                t_targets.get(
                    "min_cut_sec",
                    PORCELAIN_V7_MIN_CUT_SEC if is_porcelain else DIORAMA_V7_RAPID_CUT_MIN_SEC,
                )
            )
            avg_cut_min = float(
                t_targets.get("avg_cut_min_sec", PORCELAIN_V7_AVG_CUT_MIN_SEC if is_porcelain else 0.0)
            )
            from pipeline.config import (
                BRAIN_SIM_ONLY_CLIP_COUNT_RANGE,
                EXPRESSIVE_V8_LEGACY_CLIP_COUNT_MIN,
                EXPRESSIVE_V8_LEGACY_INDOOR_CLIP_COUNT_RANGE,
                EXPRESSIVE_V8_R76_CLIP_COUNT_RANGE,
                MICRO_SHORT_CUT_MIN,
                MICRO_SHORT_PROFILE,
                SHORTS_90S_CUT_COUNT_MIN,
                SHORTS_90S_PROFILE,
                SHORTS_EXPRESSIVE_V8_CUT_COUNT_MIN,
                is_brain_sim_only_plan,
                is_r72_open_world_v8_plan,
                is_r76_v8_plan,
                resolve_shorts_format_profile,
            )

            dq5_fmt = resolve_shorts_format_profile(
                vp,
                script_doc,
                edl,
                {"sentences": sentences},
                project_id=p_dir.name,
            )
            if dq5_fmt == SHORTS_EXPRESSIVE_V8_PROFILE or is_expressive_v8:
                if allow_legacy_v8:
                    dq5_min_cuts = int(EXPRESSIVE_V8_LEGACY_CLIP_COUNT_MIN)
                elif is_brain_sim_only_plan(vp, script_doc):
                    dq5_min_cuts = int(BRAIN_SIM_ONLY_CLIP_COUNT_RANGE[0])
                elif is_r76_v8_plan(vp, script_doc, project_id=p_dir.name) or is_r85_flow_31_brain_plan(vp, script_doc, project_id=p_dir.name):
                    from pipeline.config import R82_CUT_COUNT_RANGE, is_r82_dual_speed_pacing_plan

                    dq5_min_cuts = int(
                        R82_CUT_COUNT_RANGE[0]
                        if is_r82_dual_speed_pacing_plan(vp, script_doc, project_id=p_dir.name)
                        else EXPRESSIVE_V8_R76_CLIP_COUNT_RANGE[0]
                    )
                elif not is_r72_open_world_v8_plan(vp, script_doc, project_id=p_dir.name):
                    dq5_min_cuts = int(EXPRESSIVE_V8_LEGACY_INDOOR_CLIP_COUNT_RANGE[0])
                elif is_synth_test:
                    dq5_min_cuts = int(EXPRESSIVE_V8_CLIP_COUNT_MIN)
                else:
                    dq5_min_cuts = int(SHORTS_EXPRESSIVE_V8_CUT_COUNT_MIN)
            elif dq5_fmt == MICRO_SHORT_PROFILE:
                dq5_min_cuts = MICRO_SHORT_CUT_MIN
            elif dq5_fmt == SHORTS_90S_PROFILE:
                dq5_min_cuts = SHORTS_90S_CUT_COUNT_MIN
            else:
                dq5_min_cuts = DIORAMA_TARGET_CUT_MIN
            from pipeline.config import EXPRESSIVE_V8_VIDEO_FPS

            expected_dq5_fps = (
                float(edl.get("fps") or EXPRESSIVE_V8_VIDEO_FPS) if is_expressive_v8 else float(DIORAMA_V7_VIDEO_FPS)
            )
            dq5_ok = (
                len(cuts) >= dq5_min_cuts
                and abs(fps - expected_dq5_fps) <= 0.25
                and cut_cv >= float(t_targets["cut_duration_cv_min"])
                and min_cut >= min_cut_floor - (0.35 if is_synth_test else 0.002)
                and avg_cut >= avg_cut_min - (0.45 if is_synth_test else 0.0)
                and avg_cut <= t_targets["avg_cut_max_sec"] + (0.45 if is_synth_test else 0.0)
                and max_single_sent_cut <= single_sent_cap + (0.50 if is_synth_test else 0.0)
                and max_cut <= t_targets["max_single_speech_cut_sec"] + (0.60 if is_synth_test else 0.0)
                and hstack_divider_ok
                and camera_ratios_ok
            )
        else:
            from pipeline.config import (
                MICRO_SHORT_CUT_MIN,
                MICRO_SHORT_PROFILE,
                SHORTS_90S_CUT_COUNT_MIN,
                SHORTS_90S_PROFILE,
                resolve_shorts_format_profile,
            )

            dq5_fmt = resolve_shorts_format_profile(
                vp,
                script_doc,
                edl,
                {"sentences": sentences},
                project_id=p_dir.name,
            )
            dq5_min_cuts = (
                MICRO_SHORT_CUT_MIN
                if dq5_fmt == MICRO_SHORT_PROFILE
                else (SHORTS_90S_CUT_COUNT_MIN if dq5_fmt == SHORTS_90S_PROFILE else DIORAMA_TARGET_CUT_MIN)
            )
            dq5_ok = (
                len(cuts) >= dq5_min_cuts
                and avg_cut <= t_targets["avg_cut_max_sec"] + (0.45 if is_synth_test else 0.0)
                and max_cut <= t_targets["max_single_speech_cut_sec"] + (0.60 if is_synth_test else 0.0)
            )

        # DQ6: Zero Clip Reuse, Enforced Reference Chip Provenance & R89 Archival Video Guardrails
        from pipeline.archival_insert_builder import load_verified_archival_insert_clip_map
        from pipeline.archival_video_builder import (
            count_mp4_audio_streams as _count_r89_audio_streams,
            load_verified_archival_video_clip_map,
            validate_archival_videos_manifest as _validate_r89_manifest,
            validate_combined_archival_budget as _validate_r88_r89_budget,
        )
        from pipeline.config import (
            R89_MIN_CUT_INDEX as _R89_MIN_CUT_INDEX,
            R89_MIN_FRAME_DIFF as _R89_MIN_FRAME_DIFF,
            R89_MIN_START_SEC as _R89_MIN_START_SEC,
            R89_MODE1_BOTTOM_BRAIN_BOX as _R89_M1_BRAIN_BOX,
            R89_MODE1_TOP_VIDEO_BOX as _R89_M1_TOP_BOX,
            R89_MODE2_LOCATOR_BADGE_BOX as _R89_M2_BADGE_BOX,
            R89_MODE2_VIEWFINDER_BOX as _R89_M2_VF_BOX,
            R89_YUNET_FACE_SCORE_THRESHOLD as _R89_YUNET_THRESH,
            R89_YUNET_SAMPLE_FPS as _R89_SAMPLE_FPS,
        )

        verified_archival_map = load_verified_archival_insert_clip_map(p_dir / "03_visuals")
        verified_r89_video_map = load_verified_archival_video_clip_map(p_dir / "03_visuals")
        r89_manifest_path = p_dir / "03_visuals" / "archival_videos_manifest.json"
        r89_issues: list[str] = []
        if r89_manifest_path.is_file():
            r89_val = _validate_r89_manifest(
                p_dir,
                episode_duration_sec=float(edl.get("total_duration_sec") or total_dur or 75.0),
                edl=edl,
                check_faces=False,
                strict_sha256=True,
            )
            r89_issues.extend(list(r89_val.get("issues") or []))
            r88_edl_durs: list[float] = []
            r89_edl_durs: list[float] = []
            for c_chk in cuts:
                if not isinstance(c_chk, dict) or c_chk.get("outro_sky_card"):
                    continue
                ci_num = int(c_chk.get("clip_index") or 0)
                c_fn_chk = str(c_chk.get("clip_file") or "").replace("\\", "/")
                st_s = float(c_chk.get("start") or 0.0)
                en_s = float(c_chk.get("end") or st_s)
                if ("archival_video_clips/" in c_fn_chk) or (ci_num in verified_r89_video_map and "flow_native_clips/" not in c_fn_chk):
                    if int(c_chk.get("cut_index") or 0) < _R89_MIN_CUT_INDEX or st_s < _R89_MIN_START_SEC - 1e-6:
                        r89_issues.append(
                            f"[r89_cut_1_hook_forbidden] cut {c_chk.get('cut_index')} start={st_s:.2f}s overlaps Cut 1 / HookTitle"
                        )
                    r89_entry_dq6 = verified_r89_video_map.get(ci_num) or {}
                    r89_cp = Path(str(r89_entry_dq6.get("resolved_clip_path") or r89_entry_dq6.get("clip_path") or ""))
                    if r89_cp.is_file() and _count_r89_audio_streams(r89_cp) != 0:
                        r89_issues.append(f"[r89_nonzero_audio_streams] clip {ci_num} has non-zero audio streams")
                    r89_edl_durs.append(max(0.0, en_s - st_s))
                elif ("archival_insert_clips/" in c_fn_chk) or (ci_num in verified_archival_map and "flow_native_clips/" not in c_fn_chk):
                    r88_edl_durs.append(max(0.0, en_s - st_s))
            r89_issues.extend(
                _validate_r88_r89_budget(
                    len(r88_edl_durs),
                    sum(r88_edl_durs),
                    len(r89_edl_durs),
                    sum(r89_edl_durs),
                    episode_duration_sec=float(edl.get("total_duration_sec") or total_dur or 75.0),
                )
            )
        r89_archival_video_ok = len(r89_issues) == 0

        unattached_ref_clips: list[int] = []
        prov_path = p_dir / "03_visuals" / "flow_provenance_receipt.json"
        corrupt_prov_receipt = False
        if prov_path.exists():
            try:
                prov_doc = json.loads(prov_path.read_text(encoding="utf-8"))
                prov_clips = [pc for pc in (prov_doc.get("clips") or []) if isinstance(pc, dict)]
                enforce_ref_prov = bool(prov_doc.get("reference_attachment_enforced")) or any(
                    "reference_attached" in pc for pc in prov_clips
                )
                if enforce_ref_prov:
                    prov_by_idx = {
                        int(pc.get("clip_index") or pc.get("clip_number") or 0): pc
                        for pc in prov_clips
                    }
                    used_clip_nums = sorted(
                        {
                            int(c.get("clip_index") or 0)
                            for c in cuts
                            if not c.get("outro_sky_card") and int(c.get("clip_index") or 0) > 0
                        }
                    )
                    from pipeline.brain_simulator_blender import is_brain_simulator_clip_spec as _is_b_sim_dq6

                    for c_num in used_clip_nums:
                        if c_num in verified_archival_map or c_num in verified_r89_video_map:
                            continue
                        vp_c = vp_by_num.get(c_num, {})
                        if _is_b_sim_dq6(vp_c):
                            continue
                        rc_c = rendered_by_num.get(c_num, {})
                        expected_ref = str(
                            vp_c.get("reference_image") or rc_c.get("reference_image") or ""
                        ).strip()
                        if expected_ref and prov_by_idx.get(c_num, {}).get("reference_attached") is not True:
                            unattached_ref_clips.append(c_num)
            except Exception as exc:
                import logging

                logging.getLogger("dynamic_episode_qa").warning(
                    "Corrupt flow_provenance_receipt.json at %s during DQ6: %s", prov_path, exc, exc_info=True
                )
                corrupt_prov_receipt = True
        dual_harvest_ok = bool(edl.get("dual_harvest_disjoint_verified")) and int(edl.get("max_clip_reuse") or 99) <= 2
        dq6_ok = (
            (
                (bool(edl.get("zero_clip_reuse")) and int(edl.get("max_clip_reuse") or 99) <= DIORAMA_MAX_CLIP_REUSE)
                or dual_harvest_ok
            )
            and len(unattached_ref_clips) == 0
            and not corrupt_prov_receipt
            and r89_archival_video_ok
        )

        # DQ7, DQ8, DQ9: Inspect 100% of ALL EDL cuts (including outro) across full non-subtitle scene bands in Schema v7
        freeze_cuts: list[int] = []
        skin_leaks: list[int] = []
        yunet_face_cuts: list[int] = []
        dq8_moderate_cuts: list[int] = []
        dq8_suspect_items: list[dict[str, Any]] = []
        verified_archival_insert_cuts: list[int] = []
        verified_archival_video_cuts: list[int] = []
        plaque_leaks: list[int] = []
        lens_border_cuts: list[int] = []
        cut_lumas: list[float] = []
        cut_dark_v35: list[float] = []
        cut_sats: list[float] = []
        _detect_yunet_non_porcelain = None
        _detect_yunet_faces = None
        _detect_lens_border_fn = None

        def _lookup_verified_map_entry(c_dict: dict[str, Any], target_map: dict[int, dict[str, Any]]) -> dict[str, Any] | None:
            if not target_map:
                return None
            c_fn = str(c_dict.get("clip_file") or "").strip().replace("\\", "/")
            if "flow_native_clips/" in c_fn or "brain_simulator_clips/" in c_fn:
                return None
            try:
                c_no = int(c_dict.get("clip_index") or 0)
            except (TypeError, ValueError):
                c_no = 0
            if c_no <= 0 and c_fn:
                m_cn = re.search(r"(\d+)", Path(c_fn).stem)
                if m_cn:
                    c_no = int(m_cn.group(1))
            return target_map.get(c_no)

        def _lookup_verified_archival_entry(c_dict: dict[str, Any]) -> dict[str, Any] | None:
            return _lookup_verified_map_entry(c_dict, verified_archival_map)

        def _lookup_verified_r89_entry(c_dict: dict[str, Any]) -> dict[str, Any] | None:
            return _lookup_verified_map_entry(c_dict, verified_r89_video_map)

        def _is_archival_face_exempt(entry: dict[str, Any]) -> bool:
            try:
                pub_y = int(entry.get("publication_year") if entry.get("publication_year") is not None else 9999)
            except (TypeError, ValueError):
                pub_y = 9999
            return (
                bool(entry.get("allow_deceased_pre1931_portrait"))
                and str(entry.get("license_class") or "") == "direct_insert_pd_cc0"
                and 0 < pub_y <= 1930
                and not bool(entry.get("contains_minor"))
            )

        if not is_synth_test:
            from pipeline.posthoc_semantic_qa import (
                detect_circular_lens_border_intrusion as _detect_lens_border_fn,
                evaluate_cut_temporal_smoothness as _eval_cut_smooth_fn,
            )
        else:
            _eval_cut_smooth_fn = None
        if (is_porcelain or is_expressive_v8) and not is_synth_test:
            from pipeline.source_reenactment import (
                detect_human_faces_yunet as _detect_yunet_faces,
                detect_non_porcelain_human_faces_yunet as _detect_yunet_non_porcelain,
            )
        prev_trans_by_cut: dict[int, str] = {}
        for _ci_idx, _cut_entry in enumerate(cuts):
            if _ci_idx > 0:
                prev_trans_by_cut[int(_cut_entry.get("cut_index") or (_ci_idx + 1))] = str(
                    cuts[_ci_idx - 1].get("transition_to_next") or cuts[_ci_idx - 1].get("transition_out") or ""
                )
        _v8_pad_transitions = {
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
        }
        inspected_cuts = cuts if is_v7 else [c for c in cuts[::3] if not c.get("outro_sky_card")]
        for c in inspected_cuts:
            is_outro = bool(c.get("outro_sky_card"))
            c_start = float(c["out_start_sec"])
            c_end = float(c["out_end_sec"])
            c_idx_num = int(c.get("cut_index") or 0)
            in_pad = (
                0.38
                if (
                    is_expressive_v8
                    and (c_end - c_start) >= 1.25
                    and str(prev_trans_by_cut.get(c_idx_num) or "").strip().lower() in _v8_pad_transitions
                )
                else 0.08
            )
            out_pad = (
                0.38
                if (
                    is_expressive_v8
                    and (c_end - c_start) >= 1.25
                    and str(c.get("transition_to_next") or c.get("transition_out") or "").strip().lower() in _v8_pad_transitions
                )
                else 0.08
            )
            t0 = c_start + in_pad
            t1 = max(t0 + 0.20, c_end - out_pad)
            t_mid = 0.5 * (t0 + t1)
            f_a = _get_frame(t0)
            f_mid = _get_frame(t_mid)
            f_b = _get_frame(t1)
            if f_a is not None and f_b is not None:
                h_f, _w_f = f_a.shape[:2]
                has_hero_st = bool(c.get("has_data_stamp"))
                has_top_ov = (
                    c.get("mode") in ("split_hstack", "split_vstack")
                    or has_hero_st
                    or bool(c.get("has_anatomy_callout"))
                    or any(cs0 < c_end - 0.04 and cs1 > c_start + 0.04 for cs0, cs1 in top_overlay_spans)
                )
                rc_meta = rendered_by_num.get(int(c.get("clip_index") or 0), {})
                vp_meta = vp_by_num.get(int(c.get("clip_index") or 0), {})
                arch_entry = _lookup_verified_archival_entry(c)
                r89_entry = _lookup_verified_r89_entry(c)
                raw_g_str = str(c.get("grammar") or rc_meta.get("grammar") or vp_meta.get("grammar") or "")
                g_str = normalize_porcelain_v7_grammar(raw_g_str) if (is_porcelain and not is_expressive_v8) else raw_g_str
                motion_hero_st = bool(has_hero_st and g_str not in ("brain_simulator_3d", "expressive_xray_brain"))

                def _band_diff(fa_in: np.ndarray, fb_in: np.ndarray) -> float:
                    if r89_entry is not None:
                        vx0, vy0, vx1, vy1 = (
                            _R89_M1_TOP_BOX if str(r89_entry.get("mode") or "") == "split_sync" else _R89_M2_VF_BOX
                        )
                        ma = cv2.cvtColor(fa_in[vy0 + 12 : vy1 - 12, vx0 + 12 : vx1 - 12], cv2.COLOR_BGR2GRAY)
                        mb = cv2.cvtColor(fb_in[vy0 + 12 : vy1 - 12, vx0 + 12 : vx1 - 12], cv2.COLOR_BGR2GRAY)
                        return float(np.mean(np.abs(ma.astype(np.float32) - mb.astype(np.float32))))
                    ra_l = _non_subtitle_scene_rois(
                        fa_in,
                        has_top_overlay=has_top_ov,
                        is_outro=is_outro,
                        is_expressive_v8=is_expressive_v8,
                        has_hero_stamp=motion_hero_st,
                    )
                    rb_l = _non_subtitle_scene_rois(
                        fb_in,
                        has_top_overlay=has_top_ov,
                        is_outro=is_outro,
                        is_expressive_v8=is_expressive_v8,
                        has_hero_stamp=motion_hero_st,
                    )
                    if ra_l and len(ra_l) == len(rb_l):
                        return float(
                            np.mean(
                                [
                                    float(
                                        np.mean(
                                            np.abs(
                                                cv2.cvtColor(ra, cv2.COLOR_BGR2GRAY).astype(np.float32)
                                                - cv2.cvtColor(rb, cv2.COLOR_BGR2GRAY).astype(np.float32)
                                            )
                                        )
                                    )
                                    for ra, rb in zip(ra_l, rb_l)
                                ]
                            )
                        )
                    ma = cv2.cvtColor(fa_in[int(h_f * 0.26) : int(h_f * 0.56), :], cv2.COLOR_BGR2GRAY)
                    mb = cv2.cvtColor(fb_in[int(h_f * 0.26) : int(h_f * 0.56), :], cv2.COLOR_BGR2GRAY)
                    return float(np.mean(np.abs(ma.astype(np.float32) - mb.astype(np.float32))))

                diff = _band_diff(f_a, f_b)
                ordered_pts: list[np.ndarray | None] = [f_a, f_mid, f_b]
                intra_frozen = False
                if (
                    is_v7
                    and not is_synth_test
                    and r89_entry is None
                    and ((c_end - c_start) >= 2.20 or g_str in ("lowpoly_pov_hands", "porcelain_pov_hands"))
                    and f_mid is not None
                ):
                    f_q1 = _get_frame(t0 + 0.25 * (t1 - t0))
                    f_q3 = _get_frame(t0 + 0.75 * (t1 - t0))
                    if f_q1 is not None and f_q3 is not None:
                        ordered_pts = [f_a, f_q1, f_mid, f_q3, f_b]
                        if (c_end - c_start) >= 2.20 and not is_outro:
                            q_pts = [f_a, f_q1, f_mid, f_q3, f_b]
                            q_diffs = [_band_diff(q_pts[i], q_pts[i + 1]) for i in range(4)]
                            med_cap = 1.10 if is_expressive_v8 else 1.45
                            if sum(1 for qd in q_diffs if qd < 0.28) >= 2 or (
                                max(q_diffs) < 2.0 and float(np.median(q_diffs)) < med_cap
                            ):
                                intra_frozen = True
                if (r89_entry is not None and diff < _R89_MIN_FRAME_DIFF) or (r89_entry is None and (diff < 0.30 or intra_frozen)):
                    freeze_cuts.append(int(c["cut_index"]))
                elif is_expressive_v8 and not is_synth_test and c_idx_num == 1:
                    from pipeline.config import EXPRESSIVE_V8_FIRST_MOTION_MAX_FRAMES

                    f_open0 = _get_frame(0.0)
                    f_open10 = _get_frame(min(max(0.05, c_end - 0.04), float(EXPRESSIVE_V8_FIRST_MOTION_MAX_FRAMES) / max(1.0, fps)))
                    if f_open0 is not None and f_open10 is not None and _band_diff(f_open0, f_open10) < 0.25:
                        freeze_cuts.append(int(c["cut_index"]))

                sample_frames_cut = [f for f in ordered_pts if f is not None]
                if not is_synth_test and arch_entry is None and r89_entry is None:
                    all_rois_cut = [
                        r
                        for sf in (f_a, f_mid if f_mid is not None else f_a, f_b)
                        for r in _non_subtitle_scene_rois(
                            sf,
                            has_top_overlay=has_top_ov,
                            is_outro=is_outro,
                            is_expressive_v8=is_expressive_v8,
                            has_hero_stamp=has_hero_st,
                        )
                    ]
                    max_plaque_cut = max((_max_horizontal_plaque_glyph_run(r) for r in all_rois_cut), default=0)
                    cut_allowlist = (
                        c.get("diegetic_text_allowlist")
                        or rc_meta.get("diegetic_text_allowlist")
                        or vp_meta.get("diegetic_text_allowlist")
                        or []
                    )
                    plaque_cap = (
                        14
                        if (is_expressive_v8 and isinstance(cut_allowlist, list) and len(cut_allowlist) > 0)
                        else (5 if is_v7 else 8)
                    )
                    if max_plaque_cut >= plaque_cap:
                        plaque_leaks.append(int(c["cut_index"]))

                if r89_entry is not None:
                    verified_archival_video_cuts.append(int(c["cut_index"]))
                    if not _is_archival_face_exempt(r89_entry):
                        from pipeline.source_reenactment import detect_human_faces_yunet as _detect_r89_faces

                        dt_r89 = 1.0 / max(1.0, float(_R89_SAMPLE_FPS))
                        ts_r89 = list(np.arange(t0, t1 + 1e-6, dt_r89))
                        if not ts_r89 or abs(float(ts_r89[-1]) - t1) > 0.05:
                            ts_r89.append(t1)
                        r89_mode = str(r89_entry.get("mode") or "")
                        for ts_q in ts_r89:
                            fr_q = _get_frame(float(ts_q))
                            if fr_q is None:
                                continue
                            if r89_mode == "split_sync":
                                vx0, vy0, vx1, vy1 = _R89_M1_TOP_BOX
                                roi_q = np.ascontiguousarray(fr_q[vy0 + 10 : vy1 - 10, vx0 + 10 : vx1 - 10])
                            else:
                                vx0, vy0, vx1, vy1 = _R89_M2_VF_BOX
                                bx0, by0, bx1, by1 = _R89_M2_BADGE_BOX
                                sub_q = fr_q.copy()
                                sub_q[by0:by1, bx0:bx1] = (22, 12, 8)
                                roi_q = np.ascontiguousarray(sub_q[vy0 + 10 : vy1 - 10, vx0 + 10 : vx1 - 10])
                            if len(_detect_r89_faces(roi_q, score_threshold=_R89_YUNET_THRESH)) > 0:
                                yunet_face_cuts.append(int(c["cut_index"]))
                                skin_leaks.append(int(c["cut_index"]))
                                break

                if is_v7 and r89_entry is None:
                    mid_bgr = f_a[int(h_f * 0.27) : int(h_f * 0.55), :]
                    mid_gray = cv2.cvtColor(mid_bgr, cv2.COLOR_BGR2GRAY)
                    hsv_m = cv2.cvtColor(mid_bgr, cv2.COLOR_BGR2HSV)
                    if not is_outro:
                        cut_lumas.append(float(np.mean(mid_gray)))
                        cut_dark_v35.append(float(np.mean(hsv_m[:, :, 2] < 35)))
                        cut_sats.append(float(np.mean(hsv_m[:, :, 1])))
                    if not is_synth_test:
                        cut_leak = False
                        arch_entry = _lookup_verified_archival_entry(c)
                        if arch_entry is not None:
                            verified_archival_insert_cuts.append(int(c["cut_index"]))
                        arch_face_exempt = bool(arch_entry is not None and _is_archival_face_exempt(arch_entry))
                        if any(detect_escher_dual_edge_closeup(sf, g_str) for sf in sample_frames_cut) or detect_transient_top_intrusion_pov(
                            sample_frames_cut, g_str
                        ):
                            cut_leak = True
                        if is_expressive_v8 and g_str in ("expressive_xray_brain", "brain_simulator_3d"):
                            if any(compute_neon_green_spill_ratio(sf) > 0.08 for sf in sample_frames_cut):
                                cut_leak = True
                        elif is_expressive_v8 and not is_outro and g_str not in ("expressive_xray_brain", "brain_simulator_3d"):
                            from pipeline.dq8_suspect_classifier import classify_dq8_yunet_box, detect_yunet_boxes_with_landmarks
                            from pipeline.source_reenactment import extract_dq8_scene_roi

                            sample_ts_025 = list(np.arange(t0, t1 + 1e-6, 0.25))
                            if not sample_ts_025 or abs(float(sample_ts_025[-1]) - t1) > 0.05:
                                sample_ts_025.append(t1)
                            dq8_timed_frames: list[tuple[float, float, int, np.ndarray]] = []
                            in_s0 = float(c.get("src_start_sec") or 0.0)
                            m_spd = max(0.25, float(c.get("main_speed") or 1.0))
                            clip_fn_c = str(c.get("clip_file") or "").strip()
                            raw_clip_p: Path | None = None
                            if c.get("mode") in (None, "single"):
                                if arch_entry is not None:
                                    cand_arch = Path(str(arch_entry.get("resolved_clip_path") or ""))
                                    if cand_arch.is_file():
                                        raw_clip_p = cand_arch
                                if raw_clip_p is None and clip_fn_c:
                                    for sub_d in ("flow_native_clips", "clips"):
                                        cand_p = p_dir / "03_visuals" / sub_d / clip_fn_c
                                        if cand_p.is_file():
                                            raw_clip_p = cand_p
                                            break
                            if raw_clip_p is not None:
                                raw_cap = cv2.VideoCapture(str(raw_clip_p))
                                raw_fps = float(raw_cap.get(cv2.CAP_PROP_FPS) or 24.0)
                                raw_fc = int(raw_cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
                                seen_raw_fi: set[int] = set()
                                for ts_s in sample_ts_025:
                                    src_t = in_s0 + max(0.0, float(ts_s) - c_start) * m_spd
                                    f_i = max(0, min(max(0, raw_fc - 1), int(round(src_t * raw_fps))))
                                    if f_i in seen_raw_fi:
                                        continue
                                    seen_raw_fi.add(f_i)
                                    raw_cap.set(cv2.CAP_PROP_POS_FRAMES, f_i)
                                    ok_r, fr_r = raw_cap.read()
                                    if ok_r and fr_r is not None:
                                        dq8_timed_frames.append((float(ts_s), float(src_t), int(f_i), fr_r))
                                raw_cap.release()
                            if len(dq8_timed_frames) < 2:
                                dq8_timed_frames = [
                                    (
                                        float(ts_s),
                                        float(in_s0 + max(0.0, float(ts_s) - c_start) * m_spd),
                                        _sec_to_fidx(float(ts_s)),
                                        fr_q,
                                    )
                                    for ts_s in sample_ts_025
                                    for fr_q in (_get_frame(float(ts_s)),)
                                    if fr_q is not None
                                ]

                            if arch_entry is not None:
                                # R88-A verified archival insert: exempt skin-hue tones on non-human apparatus/buildings,
                                # yet still reject any detected human face unless pre-1931 PD/CC0 deceased portrait exempt.
                                if not arch_face_exempt:
                                    for _ts_s, _src_t, _f_idx_q, sf in dq8_timed_frames:
                                        yunet_roi_sf = extract_dq8_scene_roi(sf, is_expressive_v8=True)
                                        has_face = (
                                            (_detect_yunet_faces is not None and len(_detect_yunet_faces(yunet_roi_sf, score_threshold=0.42)) > 0)
                                            or (_detect_yunet_non_porcelain is not None and len(_detect_yunet_non_porcelain(yunet_roi_sf)) > 0)
                                        )
                                        if has_face:
                                            cut_leak = True
                                            yunet_face_cuts.append(int(c["cut_index"]))
                                            break
                            else:
                                cut_candidates: list[dict[str, Any]] = []
                                suspect_frame_count = 0
                                high_frame_count = 0
                                for ts_s, src_t, f_idx_q, sf in dq8_timed_frames:
                                    hsplit_cap_dq8 = 0.92 if g_str == "spatial_3d_arrow_diorama" else 0.72
                                    if (
                                        c.get("mode") not in ("split_hstack", "split_vstack")
                                        and not bool(c.get("stacked_cutaway_brain_compare") or vp_meta.get("stacked_cutaway_brain_compare"))
                                        and g_str != "expressive_split_contrast"
                                        and detect_unintended_horizontal_split_seam(sf) >= hsplit_cap_dq8
                                    ):
                                        cut_leak = True
                                    yunet_roi_sf = extract_dq8_scene_roi(sf, is_expressive_v8=True)
                                    frame_had_suspect = False
                                    frame_had_high = False
                                    for d_lm in detect_yunet_boxes_with_landmarks(yunet_roi_sf, score_threshold=0.62):
                                        cls_res = classify_dq8_yunet_box(
                                            yunet_roi_sf, d_lm["bbox"], float(d_lm["score"]), d_lm["landmarks"]
                                        )
                                        if cls_res["is_suspect"]:
                                            frame_had_suspect = True
                                            if cls_res["is_high_suspect"]:
                                                frame_had_high = True
                                            cut_candidates.append(
                                                {
                                                    "cut_index": int(c["cut_index"]),
                                                    "timeline_sec": float(ts_s),
                                                    "src_clip_sec": float(src_t),
                                                    "frame_index": int(f_idx_q),
                                                    "bbox_in_roi": list(d_lm["bbox"]),
                                                    "landmarks_in_roi": list(d_lm["landmarks"]),
                                                    "det_result": cls_res,
                                                }
                                            )
                                    if frame_had_suspect:
                                        suspect_frame_count += 1
                                    if frame_had_high:
                                        high_frame_count += 1
                                if cut_candidates:
                                    cut_is_persistent_high = (
                                        (high_frame_count >= 1)
                                        if len(dq8_timed_frames) < 4
                                        else (
                                            high_frame_count >= 2
                                            and (high_frame_count / float(max(1, suspect_frame_count))) >= 0.35
                                        )
                                    )
                                    cut_candidates.sort(
                                        key=lambda it: (
                                            int(it["det_result"]["is_high_suspect"]),
                                            float(it["det_result"]["metrics"].get("score") or 0.0),
                                        ),
                                        reverse=True,
                                    )
                                    picked_cut: list[dict[str, Any]] = []
                                    for cand_it in cut_candidates:
                                        cbx, cby, cbw, cbh = cand_it["bbox_in_roi"]
                                        ccx, ccy = cbx + cbw * 0.5, cby + cbh * 0.5
                                        if any(
                                            abs(ccx - (pr["bbox_in_roi"][0] + pr["bbox_in_roi"][2] * 0.5)) < max(cbw, 60) * 0.8
                                            and abs(ccy - (pr["bbox_in_roi"][1] + pr["bbox_in_roi"][3] * 0.5)) < max(cbh, 60) * 0.8
                                            for pr in picked_cut
                                        ):
                                            continue
                                        if not cut_is_persistent_high and cand_it["det_result"]["is_high_suspect"]:
                                            cand_it["det_result"] = dict(cand_it["det_result"])
                                            cand_it["det_result"]["tier"] = "MODERATE_SUSPECT"
                                            cand_it["det_result"]["is_high_suspect"] = False
                                            cand_it["det_result"]["reasons"] = list(cand_it["det_result"].get("reasons") or []) + [
                                                f"transient_high_frames={high_frame_count}/{suspect_frame_count}_downgraded_for_gate2"
                                            ]
                                        cand_it["box_index"] = len(picked_cut)
                                        picked_cut.append(cand_it)
                                        if len(picked_cut) >= 2:
                                            break
                                    dq8_suspect_items.extend(picked_cut)
                                    if cut_is_persistent_high and any(it["det_result"]["is_high_suspect"] for it in picked_cut):
                                        cut_leak = True
                                        yunet_face_cuts.append(int(c["cut_index"]))
                                    else:
                                        dq8_moderate_cuts.append(int(c["cut_index"]))
                        elif is_porcelain and g_str == "porcelain_living_brain":
                            if any(
                                compute_neon_green_spill_ratio(sf) > PORCELAIN_V7_NEON_GREEN_SPILL_MAX
                                for sf in sample_frames_cut
                            ):
                                cut_leak = True
                            bmode_cut = normalize_porcelain_v7_brain_mode(
                                c.get("brain_mode") or vp_meta.get("brain_mode") or rc_meta.get("brain_mode"),
                                render_mode=(c.get("render_mode") or vp_meta.get("render_mode") or rc_meta.get("render_mode")),
                                scene_text=str(rc_meta.get("scene") or vp_meta.get("scene") or ""),
                            )
                            cam_cut = str(
                                c.get("camera_move")
                                or rc_meta.get("camera_move")
                                or vp_meta.get("camera_move")
                                or vp_meta.get("camera")
                                or ""
                            ).strip().lower()
                            if (
                                not cut_leak
                                and c.get("mode") not in ("split_hstack", "split_vstack")
                                and bmode_cut == "cortical_vascular_whole"
                                and sample_frames_cut
                            ):
                                margin_vals_cut = [compute_brain_margin_saturation(sf) for sf in sample_frames_cut]
                                if cam_cut in ("gentle_push_in", "clean_pullback_reveal"):
                                    if float(np.mean(margin_vals_cut)) > PORCELAIN_V7_BRAIN_MARGIN_SAT_MAX:
                                        cut_leak = True
                                else:
                                    if any(ms > PORCELAIN_V7_BRAIN_MARGIN_SAT_MAX for ms in margin_vals_cut):
                                        cut_leak = True
                        elif (
                            is_porcelain
                            and not is_outro
                            and g_str != "porcelain_living_brain"
                        ):
                            flesh_cap_dq8 = PORCELAIN_V7_HUMAN_SKIN_MAX + 0.04
                            for sf in sample_frames_cut:
                                sh_f, sw_f = sf.shape[:2]
                                full_roi_sf = sf[int(sh_f * 0.10) : int(sh_f * 0.92), int(sw_f * 0.04) : int(sw_f * 0.96)]
                                if arch_entry is not None:
                                    if not arch_face_exempt and (
                                        (_detect_yunet_faces is not None and len(_detect_yunet_faces(full_roi_sf, score_threshold=0.42)) > 0)
                                        or (_detect_yunet_non_porcelain is not None and len(_detect_yunet_non_porcelain(full_roi_sf)) > 0)
                                    ):
                                        cut_leak = True
                                        yunet_face_cuts.append(int(c["cut_index"]))
                                        break
                                    continue
                                if (
                                    g_str in ("porcelain_hands_closeup", "porcelain_pov_hands", "porcelain_fullbleed_world")
                                    and compute_porcelain_flesh_leak_ratio(full_roi_sf) > flesh_cap_dq8
                                ):
                                    cut_leak = True
                                    break
                                if _detect_yunet_non_porcelain is not None and len(_detect_yunet_non_porcelain(full_roi_sf)) > 0:
                                    cut_leak = True
                                    yunet_face_cuts.append(int(c["cut_index"]))
                                    break
                                if c.get("mode") not in ("split_hstack", "split_vstack") and detect_unintended_horizontal_split_seam(sf) >= 0.72:
                                    cut_leak = True
                                    break
                        if cut_leak:
                            skin_leaks.append(int(c["cut_index"]))
                elif str(c.get("grammar")) in ("arch_brain_maquette", "frosted_crystal_specimen") and not is_synth_test:
                    arch_entry = _lookup_verified_archival_entry(c)
                    if arch_entry is not None:
                        verified_archival_insert_cuts.append(int(c["cut_index"]))
                        if not _is_archival_face_exempt(arch_entry):
                            from pipeline.source_reenactment import detect_human_faces_yunet as _detect_arch_faces

                            if any(len(_detect_arch_faces(sf, score_threshold=0.42)) > 0 for sf in sample_frames_cut):
                                yunet_face_cuts.append(int(c["cut_index"]))
                                skin_leaks.append(int(c["cut_index"]))
                    else:
                        mid_bgr = f_a[int(h_f * 0.27) : int(h_f * 0.55), :]
                        hsv = cv2.cvtColor(mid_bgr, cv2.COLOR_BGR2HSV)
                        skin_m = (
                            (hsv[:, :, 0] >= 5) & (hsv[:, :, 0] <= 17)
                            & (hsv[:, :, 1] >= 55) & (hsv[:, :, 1] <= 145)
                            & (hsv[:, :, 2] >= 110) & (hsv[:, :, 2] <= 235)
                        )
                        if float(np.mean(skin_m)) > 0.22:
                            skin_leaks.append(int(c["cut_index"]))
                if (
                    _detect_lens_border_fn is not None
                    and not is_outro
                    and str(c.get("mode") or "single") == "single"
                    and str(c.get("grammar") or "") not in ("brain_simulator_3d", "expressive_xray_brain")
                ):
                    chk_frames = [fr for fr in (f_a, f_mid, f_b) if fr is not None]
                    if chk_frames and bool(_detect_lens_border_fn(chk_frames).get("detected")):
                        lens_border_cuts.append(int(c["cut_index"]))

        # Measure rendered ChapterHeadline & AnatomyLabel horizontal safe margins across all top overlay events
        max_headline_width_px = 0
        min_headline_side_margin_px = 1080
        headline_margin_violations: list[dict[str, Any]] = []
        if is_v7 and chapter_spans:
            for ch_s0, ch_s1 in chapter_spans:
                ch_mid = 0.5 * (ch_s0 + ch_s1)
                ch_frm = _get_frame(ch_mid)
                if ch_frm is None:
                    headline_margin_violations.append(
                        {"t_sec": round(ch_mid, 2), "width_px": 0, "left_margin_px": 0, "right_margin_px": 0, "error": "missing_frame"}
                    )
                else:
                    hw_px, lm_px, rm_px = measure_chapter_headline_bbox(ch_frm)
                    if hw_px <= 0:
                        headline_margin_violations.append(
                            {
                                "t_sec": round(ch_mid, 2),
                                "width_px": 0,
                                "left_margin_px": 0,
                                "right_margin_px": 0,
                                "error": "undetected_chapter_headline",
                            }
                        )
                    else:
                        max_headline_width_px = max(max_headline_width_px, hw_px)
                        min_headline_side_margin_px = min(min_headline_side_margin_px, lm_px, rm_px)
                        if hw_px > DIORAMA_V7_CHAPTER_HEADLINE_MAX_WIDTH_PX or min(lm_px, rm_px) < 75:
                            headline_margin_violations.append(
                                {
                                    "t_sec": round(ch_mid, 2),
                                    "width_px": hw_px,
                                    "left_margin_px": lm_px,
                                    "right_margin_px": rm_px,
                                }
                            )
        if is_v7 and anatomy_label_spans:
            for al_s0, al_s1 in anatomy_label_spans:
                al_mid = 0.5 * (al_s0 + al_s1)
                al_frm = _get_frame(al_mid)
                if al_frm is None:
                    headline_margin_violations.append(
                        {"t_sec": round(al_mid, 2), "width_px": 0, "left_margin_px": 0, "right_margin_px": 0, "error": "missing_anatomy_frame"}
                    )
                else:
                    aw_px, alm_px, arm_px = measure_chapter_headline_bbox(al_frm, min_glyph_h_px=24)
                    if aw_px <= 0:
                        headline_margin_violations.append(
                            {
                                "t_sec": round(al_mid, 2),
                                "width_px": 0,
                                "left_margin_px": 0,
                                "right_margin_px": 0,
                                "error": "undetected_anatomy_label",
                            }
                        )
                    else:
                        max_headline_width_px = max(max_headline_width_px, aw_px)
                        min_headline_side_margin_px = min(min_headline_side_margin_px, alm_px, arm_px)
                        if aw_px > DIORAMA_V7_CHAPTER_HEADLINE_MAX_WIDTH_PX or min(alm_px, arm_px) < 75:
                            headline_margin_violations.append(
                                {
                                    "t_sec": round(al_mid, 2),
                                    "width_px": aw_px,
                                    "left_margin_px": alm_px,
                                    "right_margin_px": arm_px,
                                    "style": "AnatomyLabel",
                                }
                            )

        if cap is not None:
            cap.release()
            cap = None

    ep_mean_luma = round(float(np.mean(cut_lumas)), 2) if cut_lumas else 0.0
    ep_dark_v35 = round(float(np.mean(cut_dark_v35)), 4) if cut_dark_v35 else 0.0
    ep_mean_sat = round(float(np.mean(cut_sats)), 2) if cut_sats else 0.0
    if is_v7 and not is_synth_test:
        if is_expressive_v8:
            from pipeline.config import (
                EXPRESSIVE_V8_MIN_DISTINCT_LOCATIONS,
                EXPRESSIVE_V8_MIN_LUMA,
                EXPRESSIVE_V8_MIN_SATURATION,
                is_brain_sim_only_plan,
                is_r76_v8_plan,
            )

            allow_low_key_v8 = bool(
                (vp or {}).get("allow_low_key_night")
                or (vp or {}).get("allow_legacy_v8_clip_count")
                or (script_doc or {}).get("allow_legacy_v8_clip_count")
            )
            is_brain_only_luma = is_brain_sim_only_plan(vp, script_doc)
            is_r76_luma = (
                is_r76_v8_plan(vp, script_doc, project_id=p_dir.name)
                or is_r85_flow_31_brain_plan(vp, script_doc, project_id=p_dir.name)
                or is_brain_only_luma
            )
            if is_r76_luma:
                lo_y, hi_y = 20.0, 238.0
                dark_max = 0.80
                lo_s, hi_s = 14.0, 185.0
            else:
                lo_y, hi_y = (28.0 if allow_low_key_v8 else float(EXPRESSIVE_V8_MIN_LUMA)), 238.0
                dark_max = 0.68
                lo_s, hi_s = (5.0 if allow_low_key_v8 else float(EXPRESSIVE_V8_MIN_SATURATION)), 148.0
            if not allow_low_key_v8 and not is_brain_only_luma and len(cuts) >= int(EXPRESSIVE_V8_CLIP_COUNT_MIN):
                distinct_locs_v8 = {
                    str(
                        c.get("location_id")
                        or vp_by_num.get(int(c.get("clip_index") or 0), {}).get("location_id")
                        or ""
                    ).strip().lower()
                    for c in cuts
                    if str(
                        c.get("location_id")
                        or vp_by_num.get(int(c.get("clip_index") or 0), {}).get("location_id")
                        or ""
                    ).strip()
                }
                if len(distinct_locs_v8) < int(EXPRESSIVE_V8_MIN_DISTINCT_LOCATIONS):
                    skin_leaks.append(-2)
        else:
            lo_y, hi_y = PORCELAIN_V7_LUMA_RANGE if is_porcelain else DIORAMA_V7_LUMA_RANGE
            dark_max = PORCELAIN_V7_DARK_VOID_RATIO_MAX if is_porcelain else DIORAMA_V7_DARK_VOID_RATIO_MAX
            lo_s, hi_s = PORCELAIN_V7_SATURATION_RANGE if is_porcelain else DIORAMA_V7_SATURATION_RANGE
        if (
            not (lo_y <= ep_mean_luma <= hi_y)
            or ep_dark_v35 > dark_max
            or not (lo_s <= ep_mean_sat <= hi_s)
        ):
            skin_leaks.append(-1)

    # DQ10: Subtitle Geometry, ChapterHeadline & AnatomyLabel Horizontal Safe Margins, Zero Shadow, Zero Strobe & Zero Speech Blackout
    strobe_1f_gaps = 0
    speech_blackout_gaps = 0
    if is_expressive_v8:
        from pipeline.config import (
            EXPRESSIVE_V8_SUBTITLE_MAX_WORDS,
            R87_HOOK_TITLE_DURATION_SEC,
        )

        # Accept both R87-H3 upgraded 82pt (78-86pt, MarginV=510, #FFE600 keyword highlight, 0-2.20s HookTitle)
        # and pre-R87 legacy 64pt (60-70pt, MarginV=521) assembled projects without false regressions.
        m_v8_def = re.search(
            rf"^Style:\s*Default,{re.escape(DIORAMA_V7_SUBTITLE_FONT_NAME)},(\d+),&H00FFFFFF,.*,(\d+),1\s*$",
            ass_txt,
            flags=re.MULTILINE,
        )
        parsed_v8_fs = int(m_v8_def.group(1)) if m_v8_def else 0
        parsed_v8_mv = int(m_v8_def.group(2)) if m_v8_def else 0
        hook_title_window_ok = all(
            hs0 <= 0.10 and hs1 <= float(R87_HOOK_TITLE_DURATION_SEC) + 0.25
            for hs0, hs1 in hook_title_spans
        )
        has_v8_style = (
            bool(m_v8_def)
            and 60 <= parsed_v8_fs <= 86
            and parsed_v8_mv in (int(EXPRESSIVE_V8_SUBTITLE_MARGIN_V), 510, 521)
            and len(chapter_spans) == 0
            and hook_title_window_ok
        )
        def_spans_v8: list[tuple[float, float]] = []
        overlong_caption_events = 0
        for ln in ass_txt.splitlines():
            if ln.startswith("Dialogue:") and ",Default," in ln:
                parts = ln.split(",", 9)
                if len(parts) >= 10:
                    def_spans_v8.append((_parse_ass_ts_sec(parts[1]), _parse_ass_ts_sec(parts[2])))
                    plain_cap = re.sub(r"\{[^}]*\}", "", parts[9]).replace("\\N", " ").strip()
                    if len(plain_cap.split()) > int(EXPRESSIVE_V8_SUBTITLE_MAX_WORDS):
                        overlong_caption_events += 1
        for i_ev in range(len(def_spans_v8) - 1):
            gap = def_spans_v8[i_ev + 1][0] - def_spans_v8[i_ev][1]
            if gap < -0.005:
                strobe_1f_gaps += 10
            elif 0.005 < gap < 0.065:
                strobe_1f_gaps += 1
            elif gap >= 0.55:
                speech_blackout_gaps += 1
        dq10_ok = (
            has_v8_style
            and overlong_caption_events == 0
            and strobe_1f_gaps <= 5
            and speech_blackout_gaps == 0
            and len(headline_margin_violations) == 0
        )
    elif is_v7:
        has_v7_style = (
            f"Style: Default,{DIORAMA_V7_SUBTITLE_FONT_NAME}," in ass_txt
            and f",{DIORAMA_V7_SUBTITLE_MARGIN_V},1" in ass_txt
            and f"Style: ChapterHeadline,{DIORAMA_V7_SUBTITLE_FONT_NAME}," in ass_txt
            and (
                not anatomy_label_spans
                or f"Style: AnatomyLabel,{DIORAMA_V7_SUBTITLE_FONT_NAME}," in ass_txt
            )
        )
        def_spans: list[tuple[float, float]] = []
        for ln in ass_txt.splitlines():
            if ln.startswith("Dialogue:") and ",Default," in ln:
                parts = ln.split(",", 9)
                if len(parts) >= 10:
                    def_spans.append((_parse_ass_ts_sec(parts[1]), _parse_ass_ts_sec(parts[2])))
        for i_ev in range(len(def_spans) - 1):
            gap = def_spans[i_ev + 1][0] - def_spans[i_ev][1]
            if gap < -0.005:
                strobe_1f_gaps += 10  # overlap penalty
            elif 0.005 < gap < 0.065:
                strobe_1f_gaps += 1
            elif gap >= (5.0 / float(DIORAMA_V7_VIDEO_FPS)) - 0.005:
                speech_blackout_gaps += 1
        # At most 5 intentional 1-frame Act-boundary resets across 6 Acts; zero mid-sentence strobes, zero >=5f blackouts,
        # and ChapterHeadline rendered width <= DIORAMA_V7_CHAPTER_HEADLINE_MAX_WIDTH_PX (920px, >=75px side margins)!
        dq10_ok = (
            has_v7_style
            and strobe_1f_gaps <= 5
            and speech_blackout_gaps == 0
            and len(headline_margin_violations) == 0
        )
    else:
        dq10_ok = ("Style: Default,Arial Black,76" in ass_txt) and (",650,1" in ass_txt)

    # DQ11: Active Speech Density, Stereo Channels & Audio Master Presence
    audio_master = p_dir / "04_audio" / "audio_master.wav"
    wav_channels = 0
    stereo_decorrelated = False
    if audio_master.exists() and audio_master.stat().st_size > 100_000:
        try:
            with wave.open(str(audio_master), "rb") as wf:
                wav_channels = wf.getnchannels()
                if wav_channels >= 2:
                    raw_b = wf.readframes(min(wf.getnframes(), wf.getframerate() * 8))
                    arr_st = np.frombuffer(raw_b, dtype=np.int16).astype(np.float32).reshape(-1, wav_channels)
                    stereo_decorrelated = float(np.max(np.abs(arr_st[:, 0] - arr_st[:, 1]))) > 15.0
        except Exception:
            pass
    min_voiced_rms_req = 0.72 if is_expressive_v8 else (DIORAMA_V7_ACTIVE_VOICED_RMS_RATIO_MIN if is_v7 else 0.84)
    if is_v7:
        rms_voiced = float(vr.get("true_rms_voiced_ratio") or vr.get("active_speech_ratio") or 0.0)
        dq11_ok = (
            audio_master.exists()
            and audio_master.stat().st_size > 100_000
            and wav_channels == 2
            and stereo_decorrelated
            and float(vr.get("active_speech_ratio") or 0.0) >= min_voiced_rms_req
            and (is_synth_test or rms_voiced >= min_voiced_rms_req)
        )
    else:
        dq11_ok = audio_master.exists() and audio_master.stat().st_size > 100_000 and float(vr.get("active_speech_ratio") or 0.0) >= 0.84

    # DQ12: 3 Visually Distinct Thumbnails
    thumbs = [p_dir / "06_publish" / f"thumbnail_var_{k}.png" for k in ("A", "B", "C")]
    dq12_ok = all(t.exists() and t.stat().st_size > 10_000 for t in thumbs)
    if dq12_ok:
        im_a = cv2.imread(str(thumbs[0]))
        im_b = cv2.imread(str(thumbs[1]))
        im_c = cv2.imread(str(thumbs[2]))
        if im_a is not None and im_b is not None and im_c is not None:
            dab = float(np.mean(np.abs(im_a.astype(np.float32) - im_b.astype(np.float32))))
            dbc = float(np.mean(np.abs(im_b.astype(np.float32) - im_c.astype(np.float32))))
            dq12_ok = dab >= 8.0 and dbc >= 8.0

    gates = {
        "DQ1_literal_analogy_frame_sync": {"passed": len(dq1_failures) == 0 and not any("analogy" in x for x in pre_issues), "failures": dq1_failures},
        "DQ2_clothed_cast_and_impact": {"passed": len(dq2_failures) == 0, "failures": dq2_failures},
        "DQ3_anatomy_to_brain_sync": {"passed": len(dq3_failures) == 0, "failures": dq3_failures},
        "DQ4_brisk_storyteller_wpm": {"passed": dq4_ok, "measured_wpm": measured_wpm},
        "DQ5_three_gear_cut_rhythm": {
            "passed": dq5_ok,
            "fps": round(fps, 2),
            "min_cut_sec": min_cut,
            "avg_cut_sec": avg_cut,
            "cut_duration_cv": cut_cv,
            "fast_cut_ratio": fast_ratio,
            "max_single_sentence_cut_sec": max_single_sent_cut,
            "max_cut_sec": max_cut,
            "hstack_divider_ok": hstack_divider_ok,
            "all_cuts_have_camera_move": all_cuts_have_camera,
            "locked_camera_ratio": locked_cam_ratio,
            "zoom_camera_ratio": zoom_cam_ratio,
            "pan_left_cuts": pan_left_cuts,
            "pan_right_cuts": pan_right_cuts,
        },
        "DQ6_zero_clip_reuse": {
            "passed": dq6_ok,
            "max_clip_reuse": edl.get("max_clip_reuse"),
            "unattached_reference_clips": unattached_ref_clips,
            "r89_archival_video_ok": r89_archival_video_ok,
            "r89_issues": r89_issues,
        },
        "DQ7_continuous_motion_no_freeze": {"passed": len(freeze_cuts) == 0, "cuts_inspected": len(inspected_cuts), "freeze_cuts": freeze_cuts},
        "DQ8_zero_uncanny_skin_gore": {
            "passed": len(skin_leaks) == 0,
            "skin_leak_cuts": skin_leaks,
            "yunet_human_face_cuts": yunet_face_cuts,
            "high_suspect_cuts": sorted(set(yunet_face_cuts)),
            "moderate_suspect_cuts": sorted(set(dq8_moderate_cuts)),
            "verified_archival_insert_cuts": sorted(set(verified_archival_insert_cuts)),
            "verified_archival_video_cuts": sorted(set(verified_archival_video_cuts)),
            "suspect_detections": [],
            "contact_sheet_path": None,
            "episode_mean_luma": ep_mean_luma,
            "episode_dark_v35_ratio": ep_dark_v35,
            "episode_mean_sat": ep_mean_sat,
        },
        "DQ9_zero_background_plaque": {"passed": len(plaque_leaks) == 0, "cuts_inspected": len(inspected_cuts), "plaque_cuts": plaque_leaks},
        "DQ10_subtitle_geometry_y64": {
            "passed": dq10_ok,
            "act_boundary_1f_resets": strobe_1f_gaps,
            "speech_blackout_gaps_ge_5f": speech_blackout_gaps,
            "max_chapter_headline_width_px": max_headline_width_px,
            "min_chapter_headline_side_margin_px": (min_headline_side_margin_px if max_headline_width_px > 0 else None),
            "headline_margin_violations": headline_margin_violations,
        },
        "DQ11_broadcast_audio_density": {
            "passed": dq11_ok,
            "channels": wav_channels,
            "stereo_decorrelated": stereo_decorrelated,
            "active_speech_ratio": vr.get("active_speech_ratio"),
            "true_rms_voiced_ratio": vr.get("true_rms_voiced_ratio"),
            "min_voiced_rms_ratio": min_voiced_rms_req,
        },
        "DQ12_three_distinct_thumbnails": {"passed": dq12_ok},
    }
    if not is_synth_test and _eval_cut_smooth_fn is not None:
        smooth_report = _eval_cut_smooth_fn(local_mp4, cuts)
        smooth_failed_cuts = [
            c_no for c_no, info in sorted(smooth_report.items()) if not bool(info.get("passed", True))
        ]
        gates["DQ_Smooth_temporal_smoothness"] = {
            "passed": len(smooth_failed_cuts) == 0,
            "failed_cuts": smooth_failed_cuts,
            "max_consecutive_frozen_frames": max(
                (int(v.get("max_consecutive_frozen_frames") or 0) for v in smooth_report.values()),
                default=0,
            ),
            "per_cut": {str(k): v for k, v in sorted(smooth_report.items())},
        }
        gates["DQ_Border_no_lens_intrusion"] = {
            "passed": len(lens_border_cuts) == 0,
            "intrusion_cuts": lens_border_cuts,
        }
    if is_expressive_v8:
        from pipeline.config import (
            EXPRESSIVE_V8_DISSOLVE_8_FRAMES,
            EXPRESSIVE_V8_DISSOLVE_FRAMES,
            EXPRESSIVE_V8_MAX_ALPHA_DISSOLVE_FRAMES,
            EXPRESSIVE_V8_MAX_OVERLAP_FRAMES,
            EXPRESSIVE_V8_MAX_STYLED_TRANSITIONS,
            EXPRESSIVE_V8_PORTAL_ZOOM_FRAMES,
            EXPRESSIVE_V8_R76_BRAIN_SIM_MIN_CUT_SEC,
            EXPRESSIVE_V8_R76_HUMAN_MIN_CUT_SEC,
            EXPRESSIVE_V8_R76_MAX_CUT_SEC,
            EXPRESSIVE_V8_SPATIAL_RELAY_MIN_CUT_SEC,
            EXPRESSIVE_V8_UNIFIED_BRAIN_SIM_DURATION_RATIO_RANGE,
            EXPRESSIVE_V8_WHIP_PAN_FRAMES,
            R76_BRAIN_SIM_SQ_PASS_REQUIRED,
            is_brain_sim_only_plan,
            is_r76_v8_plan,
        )

        is_brain_only_ep = is_brain_sim_only_plan(vp, script_doc)
        is_r85_ep = is_r85_flow_31_brain_plan(vp, script_doc, project_id=p_dir.name)
        is_r76_ep = is_r76_v8_plan(vp, script_doc, project_id=p_dir.name) or is_r85_ep
        cameo_cut_indices = [
            int(c.get("cut_index") or 0)
            for c in cuts
            if bool(
                c.get("cameo_easter_egg")
                or vp_by_num.get(int(c.get("clip_index") or 0), {}).get("cameo_easter_egg")
            )
        ]
        gates["DQ_CAMEO_single_minicortex"] = {
            "passed": (len(cameo_cut_indices) == 0) if is_r76_ep else (len(cameo_cut_indices) == 1),
            "cameo_cuts": cameo_cut_indices,
        }
        if is_r85_ep:
            blender_screen_cuts = [
                int(c.get("cut_index") or 0)
                for c in cuts
                if str(c.get("grammar") or "") == "brain_simulator_3d"
                or str(c.get("render_engine") or vp_by_num.get(int(c.get("clip_index") or 0), {}).get("render_engine") or "")
                == "blender_3d_simulator"
            ]
            gates["DQ_R85_flow_31_brain_only"] = {
                "passed": len(blender_screen_cuts) == 0,
                "blender_screen_cuts": blender_screen_cuts,
            }
            if not is_synth_test:
                from pipeline.reference_image_qa import evaluate_r85_ep31_brain_style_fidelity

                r85_brain_fidelity_failures: list[dict[str, Any]] = []
                r85_brain_checked = 0
                for c_bf in cuts:
                    c_idx_bf = int(c_bf.get("cut_index") or 0)
                    clip_no_bf = int(c_bf.get("clip_index") or 0)
                    vp_bf = vp_by_num.get(clip_no_bf, {})
                    if not (
                        bool(vp_bf.get("r85_brain_clip"))
                        or bool(c_bf.get("r85_brain_clip"))
                        or str(c_bf.get("grammar") or vp_bf.get("grammar") or "") == "expressive_xray_brain"
                    ):
                        continue
                    raw_clip_p = next(
                        (
                            cand_cp
                            for cand_cp in (
                                p_dir / "03_visuals" / "flow_native_clips" / f"clip_{clip_no_bf}.mp4",
                                p_dir / "03_visuals" / "flow_native_clips" / f"clip_{clip_no_bf:02d}.mp4",
                                p_dir / "03_visuals" / "clips" / f"clip_{clip_no_bf}.mp4",
                                p_dir / "03_visuals" / f"clip_{clip_no_bf:02d}.mp4",
                            )
                            if cand_cp.is_file()
                        ),
                        p_dir / "03_visuals" / f"clip_{clip_no_bf:02d}.mp4",
                    )
                    bf_frame = None
                    used_overlay_band_crop = False
                    neon_arc_flash = False
                    neon_max_ratio = 0.0
                    neon_surge = 1.0
                    if raw_clip_p.is_file():
                        cap_bf = cv2.VideoCapture(str(raw_clip_p))
                        fc_bf = int(cap_bf.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
                        if fc_bf > 0:
                            neon_samples: list[float] = []
                            for s_fr in (0.08, 0.20, 0.32, 0.44, 0.50, 0.58, 0.70, 0.82, 0.92):
                                fi_s = max(0, min(fc_bf - 1, int(round(s_fr * max(1, fc_bf - 1)))))
                                cap_bf.set(cv2.CAP_PROP_POS_FRAMES, fi_s)
                                ok_bf, frm_bf = cap_bf.read()
                                if ok_bf and frm_bf is not None:
                                    if abs(s_fr - 0.50) < 0.03 or bf_frame is None:
                                        bf_frame = frm_bf
                                    hsv_bf = cv2.cvtColor(frm_bf, cv2.COLOR_BGR2HSV)
                                    neon_px = (
                                        (hsv_bf[:, :, 0] >= 80)
                                        & (hsv_bf[:, :, 0] <= 120)
                                        & (hsv_bf[:, :, 1] >= 75)
                                        & (hsv_bf[:, :, 2] >= 244)
                                    )
                                    neon_samples.append(float(np.mean(neon_px)))
                            neon_arc_flash, neon_max_ratio, neon_surge = is_r85_mid_cut_electric_arc_flash(
                                neon_samples,
                                camera_move=str(c_bf.get("camera_move") or vp_bf.get("camera_move") or ""),
                            )
                        cap_bf.release()
                    if bf_frame is not None:
                        r85_brain_checked += 1
                        mode_bf = str(vp_bf.get("r85_brain_mode") or vp_bf.get("r85_shot_scale") or "mode2")
                        bf_eval = evaluate_r85_ep31_brain_style_fidelity(
                            bf_frame,
                            mode=mode_bf,
                            exclude_overlay_bands=used_overlay_band_crop,
                        )
                        if neon_arc_flash:
                            bf_eval = {
                                **bf_eval,
                                "passed": False,
                                "issues": list(bf_eval.get("issues") or [])
                                + [f"r85_mid_cut_electric_arc_flash(neon_max={neon_max_ratio:.4f},surge={neon_surge:.1f}x)"],
                            }
                        if not bf_eval["passed"]:
                            r85_brain_fidelity_failures.append(
                                {
                                    "cut_index": c_idx_bf,
                                    "clip_index": clip_no_bf,
                                    **bf_eval,
                                }
                            )
                gates["DQ_R85_ep31_brain_fidelity"] = {
                    "passed": len(r85_brain_fidelity_failures) == 0,
                    "checked_brain_cuts": r85_brain_checked,
                    "failed_cuts": r85_brain_fidelity_failures,
                }
                if not bool(gates["DQ_R85_ep31_brain_fidelity"]["passed"]):
                    gates["DQ_R85_flow_31_brain_only"]["passed"] = False
                    gates["DQ_R85_flow_31_brain_only"]["electric_or_style_failures"] = [
                        int(x["cut_index"]) for x in r85_brain_fidelity_failures
                    ]

        from pipeline.config import R87_FIRST_CUT_MAX_SEC, is_r87_plan as _is_r87_dq

        if _is_r87_dq(vp, script_doc, project_id=p_dir.name):
            r87_dq_issues: list[str] = []
            c1_dur_dq = float(cuts[0].get("duration_sec") or 0.0) if cuts else 0.0
            if cuts and c1_dur_dq > float(R87_FIRST_CUT_MAX_SEC) + 0.05:
                r87_dq_issues.append(
                    f"r87_cut1_duration_exceeds_2_60s({c1_dur_dq:.2f}s>{R87_FIRST_CUT_MAX_SEC:.2f}s)"
                )
            if vp.get("spatial_arrow_eligible") is False:
                bad_sp_cuts = [
                    int(ct.get("cut_index") or (ii + 1))
                    for ii, ct in enumerate(cuts)
                    if str(ct.get("grammar") or "") == "spatial_3d_arrow_diorama"
                    or bool(ct.get("spatial_relay_cut"))
                ]
                if bad_sp_cuts:
                    r87_dq_issues.append(f"r87_nonspatial_arrow_cuts_forbidden:{bad_sp_cuts}")
            gates["DQ_R87_hook_and_arrow_lock"] = {
                "passed": len(r87_dq_issues) == 0,
                "cut1_duration_sec": round(c1_dur_dq, 3),
                "spatial_arrow_eligible": vp.get("spatial_arrow_eligible"),
                "issues": r87_dq_issues,
            }

        styled_cut_indices: list[int] = []
        alpha_fade_cut_indices: list[int] = []
        max_ov_frames = 0
        max_alpha_frames = 0
        ghost_blend_cuts: list[int] = []
        for idx_tr, c_tr in enumerate(cuts[:-1]):
            c_nxt_tr = cuts[idx_tr + 1]
            tr_nm = str(c_tr.get("transition_out") or c_tr.get("transition_to_next") or "hard").strip().lower()
            ov_f = 0
            is_alpha = False
            if tr_nm == "portal_crash_zoom_10f":
                ov_f = int(EXPRESSIVE_V8_PORTAL_ZOOM_FRAMES)
            elif tr_nm in ("whip_pan_blur_8f", "occlusion_wipe"):
                ov_f = int(EXPRESSIVE_V8_WHIP_PAN_FRAMES)
            elif tr_nm in ("dissolve_6f", "match_cut_bridge"):
                ov_f = int(EXPRESSIVE_V8_DISSOLVE_FRAMES)
                is_alpha = True
            elif tr_nm in ("dissolve_8f", "split_screen_wipe"):
                ov_f = int(EXPRESSIVE_V8_DISSOLVE_8_FRAMES)
                is_alpha = True
            elif tr_nm == "dissolve_12f":
                ov_f = 12
                is_alpha = True
            elif tr_nm == "dissolve_15f":
                ov_f = 15
                is_alpha = True
            elif re.match(r"^dissolve_(\d+)f$", tr_nm):
                ov_f = int(re.match(r"^dissolve_(\d+)f$", tr_nm).group(1))  # type: ignore[union-attr]
                is_alpha = True
            elif re.search(r"_(\d+)f$", tr_nm):
                ov_f = int(re.search(r"_(\d+)f$", tr_nm).group(1))  # type: ignore[union-attr]
            elif tr_nm == "daisy_chain_bridge":
                end_ref_a = str(c_tr.get("end_reference_image") or vp_by_num.get(int(c_tr.get("clip_index") or 0), {}).get("end_reference_image") or "").strip()
                start_ref_b = str(vp_by_num.get(int(c_nxt_tr.get("clip_index") or 0), {}).get("reference_image") or "").strip()
                if not (end_ref_a and start_ref_b and end_ref_a == start_ref_b):
                    ov_f = int(EXPRESSIVE_V8_DISSOLVE_8_FRAMES)
                    is_alpha = True
            if ov_f > 0:
                styled_cut_indices.append(int(c_tr.get("cut_index") or (idx_tr + 1)))
                max_ov_frames = max(max_ov_frames, ov_f)
                if is_alpha:
                    alpha_fade_cut_indices.append(int(c_tr.get("cut_index") or (idx_tr + 1)))
                    max_alpha_frames = max(max_alpha_frames, ov_f)
            if not is_synth_test and not is_alpha:
                tb_v = float(c_tr["out_end_sec"])
                f_pre = _get_frame(max(0.0, tb_v - 0.36))
                f_m1 = _get_frame(max(0.0, tb_v - 0.16))
                f_m2 = _get_frame(max(0.0, tb_v - 0.06))
                f_post = _get_frame(min(max(0.0, (total_fc - 1) / max(1.0, fps)), tb_v + 0.24))
                if f_pre is not None and f_m1 is not None and f_m2 is not None and f_post is not None:
                    gp = cv2.cvtColor(cv2.resize(f_pre[:1180, :], (90, 110)), cv2.COLOR_BGR2GRAY).astype(np.float32)
                    gq = cv2.cvtColor(cv2.resize(f_post[:1180, :], (90, 110)), cv2.COLOR_BGR2GRAY).astype(np.float32)
                    scene_delta = float(np.mean(np.abs(gp - gq)))
                    if scene_delta >= 22.0:
                        sustained_alpha = True
                        for fm_chk in (f_m1, f_m2):
                            gm = cv2.cvtColor(cv2.resize(fm_chk[:1180, :], (90, 110)), cv2.COLOR_BGR2GRAY).astype(np.float32)
                            diff_pq = gp - gq
                            denom = float(np.sum(np.square(diff_pq)))
                            alpha_est = float(np.sum((gm - gq) * diff_pq) / max(1e-6, denom))
                            if not (0.20 <= alpha_est <= 0.80):
                                sustained_alpha = False
                                break
                            resid = float(np.mean(np.abs(gm - (alpha_est * gp + (1.0 - alpha_est) * gq))))
                            if resid > 0.24 * scene_delta:
                                sustained_alpha = False
                                break
                        if sustained_alpha:
                            ghost_blend_cuts.append(int(c_tr.get("cut_index") or (idx_tr + 1)))

        max_alpha_cut_share = max(1, len(cuts) // 2)
        dq13_ok = (
            len(styled_cut_indices) <= int(EXPRESSIVE_V8_MAX_STYLED_TRANSITIONS)
            and len(alpha_fade_cut_indices) <= max_alpha_cut_share
            and max_ov_frames <= int(EXPRESSIVE_V8_MAX_OVERLAP_FRAMES)
            and max_alpha_frames <= int(EXPRESSIVE_V8_MAX_ALPHA_DISSOLVE_FRAMES)
            and len(ghost_blend_cuts) == 0
        )
        gates["DQ13_transition_hygiene"] = {
            "passed": dq13_ok,
            "styled_transition_count": len(styled_cut_indices),
            "max_styled_transitions": int(EXPRESSIVE_V8_MAX_STYLED_TRANSITIONS),
            "styled_cuts": styled_cut_indices,
            "alpha_fade_cuts": alpha_fade_cut_indices,
            "max_overlap_frames": max_ov_frames,
            "max_alpha_fade_frames": max_alpha_frames,
            "ghost_blend_cuts": ghost_blend_cuts,
        }
        if is_r76_ep:
            from pipeline.config import (
                R82_BRAIN_DURATION_RATIO_RANGE,
                R82_BRAIN_MAX_CUT_SEC,
                R82_BRAIN_MIN_CUT_SEC,
                R82_HUMAN_MAX_CUT_SEC,
                R82_HUMAN_MIN_CUT_SEC,
                is_r82_dual_speed_pacing_plan,
            )

            is_r82_ep = is_r82_dual_speed_pacing_plan(vp, script_doc, project_id=p_dir.name)
            non_outro_cuts_r76 = [ct for ct in cuts if isinstance(ct, dict) and not ct.get("outro_sky_card")]
            sq_failures_r76: list[dict[str, Any]] = []
            brain_dur_r76 = 0.0
            tot_dur_r76 = 0.0
            pacing_violations_r76: list[str] = []
            sent_cut_counts_r76: dict[int, int] = {}
            r78m_prov_path = p_dir / "03_visuals" / "flow_provenance_receipt.json"
            r78m_prov_by_idx: dict[int, dict[str, Any]] = {}
            if r78m_prov_path.exists():
                try:
                    _r78m_doc = json.loads(r78m_prov_path.read_text(encoding="utf-8"))
                    r78m_prov_by_idx = {
                        int(pc.get("clip_index") or pc.get("clip_number") or 0): pc
                        for pc in (_r78m_doc.get("clips") or [])
                        if isinstance(pc, dict)
                    }
                except Exception:
                    r78m_prov_by_idx = {}
            sent_cut_roles_r76: dict[int, list[dict[str, bool]]] = {}
            for ct in non_outro_cuts_r76:
                dur_ct = float(ct.get("duration_sec") or max(0.0, float(ct.get("out_end_sec") or 0.0) - float(ct.get("out_start_sec") or 0.0)))
                tot_dur_r76 += dur_ct
                s_idx_ct = int(ct.get("sentence_index") or 0)
                c_idx_ct = int(ct.get("clip_index") or 0)
                vp_ct = vp_by_num.get(c_idx_ct, {}) if isinstance(vp_by_num, dict) else {}
                g_ct = str(ct.get("grammar") or vp_ct.get("grammar") or "").strip()
                eng_ct = str(ct.get("render_engine") or vp_ct.get("render_engine") or "").strip().lower()
                is_brain_ct = _is_unified_brain_cut(ct, vp_ct)
                is_sp_relay_ct = (
                    g_ct == "spatial_3d_arrow_diorama"
                    or bool(ct.get("spatial_relay_cut"))
                    or bool(vp_ct.get("spatial_relay_cut"))
                )
                is_authored_relay_ct = is_sp_relay_ct or (
                    is_r82_ep
                    and (not is_brain_ct)
                    and (
                        bool(ct.get("human_action_relay"))
                        or bool(vp_ct.get("human_action_relay"))
                        or bool(ct.get("r72_cold_open_relay"))
                        or bool(vp_ct.get("r72_cold_open_relay"))
                    )
                )
                if s_idx_ct > 0:
                    sent_cut_counts_r76[s_idx_ct] = sent_cut_counts_r76.get(s_idx_ct, 0) + 1
                    sent_cut_roles_r76.setdefault(s_idx_ct, []).append(
                        {
                            "is_authored_relay": bool(is_authored_relay_ct),
                            "is_brain": bool(is_brain_ct),
                            "is_full_r82_brain": bool(
                                is_brain_ct and (dur_ct + 0.005 >= float(R82_BRAIN_MIN_CUT_SEC))
                            ),
                        }
                    )
                if is_brain_ct:
                    brain_dur_r76 += dur_ct
                    if R76_BRAIN_SIM_SQ_PASS_REQUIRED and not is_synth_test:
                        if eng_ct == "google_flow" or (is_r85_ep and eng_ct != "blender_3d_simulator"):
                            flow_mp4 = p_dir / "03_visuals" / "flow_native_clips" / f"clip_{c_idx_ct}.mp4"
                            pc_entry = r78m_prov_by_idx.get(c_idx_ct)
                            cv_ok = bool((pc_entry.get("cv_qa") or {}).get("passed", True)) if isinstance(pc_entry, dict) else False
                            if not flow_mp4.is_file() or flow_mp4.stat().st_size < 10_000:
                                sq_failures_r76.append({"clip": c_idx_ct, "reason": "missing_flow_brain_mp4"})
                            elif r78m_prov_path.exists() and (not isinstance(pc_entry, dict) or pc_entry.get("reference_attached") is not True or not cv_ok):
                                sq_failures_r76.append({"clip": c_idx_ct, "reason": "missing_or_failed_flow_brain_provenance"})
                        else:
                            qa_p = p_dir / "03_visuals" / "brain_simulator_clips" / f"clip_{c_idx_ct}_sim_qa.json"
                            if not qa_p.exists():
                                sq_failures_r76.append({"clip": c_idx_ct, "reason": "missing_sim_qa_json"})
                            else:
                                try:
                                    qa_d = json.loads(qa_p.read_text(encoding="utf-8"))
                                except Exception:
                                    qa_d = {}
                                if not bool(qa_d.get("passed")):
                                    sq_failures_r76.append({"clip": c_idx_ct, "gates": qa_d.get("gates")})
                if not is_synth_test:
                    if is_brain_only_ep:
                        floor_ct, ceil_ct = 1.40, 9.50
                    elif is_r82_ep:
                        floor_ct = float(R82_BRAIN_MIN_CUT_SEC if is_brain_ct else R82_HUMAN_MIN_CUT_SEC)
                        ceil_ct = float(R82_BRAIN_MAX_CUT_SEC if is_brain_ct else R82_HUMAN_MAX_CUT_SEC)
                    else:
                        floor_ct = float(
                            EXPRESSIVE_V8_R76_BRAIN_SIM_MIN_CUT_SEC
                            if is_brain_ct
                            else (EXPRESSIVE_V8_SPATIAL_RELAY_MIN_CUT_SEC if is_sp_relay_ct else EXPRESSIVE_V8_R76_HUMAN_MIN_CUT_SEC)
                        )
                        ceil_ct = float(EXPRESSIVE_V8_R76_MAX_CUT_SEC)
                    if dur_ct + 0.005 < floor_ct:
                        pacing_violations_r76.append(
                            f"cut {ct.get('cut_index')}: {dur_ct:.2f}s < {'brain' if is_brain_ct else ('spatial_relay' if is_sp_relay_ct else 'human')} floor {floor_ct:.2f}s"
                        )
                    if dur_ct > ceil_ct + 0.005:
                        pacing_violations_r76.append(
                            f"cut {ct.get('cut_index')}: {dur_ct:.2f}s > {'brain' if is_brain_ct else 'human'} max {ceil_ct:.2f}s"
                        )
            def _is_exempt_two_cut_split_r76(roles_s: list[dict[str, bool]]) -> bool:
                if len(roles_s) != 2:
                    return False
                if all(r["is_authored_relay"] and not r["is_brain"] for r in roles_s):
                    return True
                if is_r82_ep:
                    non_brain_relays = sum(
                        1 for r in roles_s if r["is_authored_relay"] and not r["is_brain"]
                    )
                    full_r82_brains = sum(
                        1 for r in roles_s if r["is_brain"] and r["is_full_r82_brain"]
                    )
                    if non_brain_relays == 1 and full_r82_brains == 1:
                        return True
                return False

            spare_splits_r76 = {
                s_i: cnt
                for s_i, cnt in sent_cut_counts_r76.items()
                if cnt > 1 and (cnt > 2 or not _is_exempt_two_cut_split_r76(sent_cut_roles_r76.get(s_i, [])))
            }
            if not is_synth_test and spare_splits_r76:
                pacing_violations_r76.append(f"mid-sentence splits detected: {spare_splits_r76}")
            share_r76 = round(brain_dur_r76 / max(0.01, tot_dur_r76), 4)
            sh_lo_r76, sh_hi_r76 = (
                (0.99, 1.0)
                if is_brain_only_ep
                else (R82_BRAIN_DURATION_RATIO_RANGE if is_r82_ep else EXPRESSIVE_V8_UNIFIED_BRAIN_SIM_DURATION_RATIO_RANGE)
            )
            gates["DQ_R76_brain_simulator_sq"] = {
                "passed": (len(sq_failures_r76) == 0),
                "failures": sq_failures_r76,
            }
            gates["DQ_R76_unified_brain_share"] = {
                "passed": bool(is_synth_test or (sh_lo_r76 - 1e-4 <= share_r76 <= sh_hi_r76 + 1e-4)),
                "brain_duration_sec": round(brain_dur_r76, 3),
                "total_duration_sec": round(tot_dur_r76, 3),
                "brain_duration_share": share_r76,
                "target_range": [float(sh_lo_r76), float(sh_hi_r76)],
            }
            gates["DQ_R76_anti_noise_pacing"] = {
                "passed": (len(pacing_violations_r76) == 0),
                "violations": pacing_violations_r76,
                "spare_sentence_splits": spare_splits_r76,
            }

        from pipeline.config import (
            EXPRESSIVE_V8_DRONE_CAMERA_MOVES,
            R79M_HUMAN_CUT_MAX_MAIN_SPEED,
            R79M_HUMAN_MIN_SECOND_HALF_RATIO,
            R79M_HUMAN_MIN_SUBJ_P90_PX,
            is_r79m_character_motion_plan,
        )

        if is_r79m_character_motion_plan(vp, script_doc, project_id=p_dir.name):
            non_outro_cuts_r79 = [ct for ct in cuts if isinstance(ct, dict) and not ct.get("outro_sky_card")]
            r79_violations: list[str] = []
            r79_cut_telemetry: list[dict[str, Any]] = []
            grays_r79: list[np.ndarray] = []
            fps_r79 = float(fps) if fps > 0 else 30.0
            if not is_synth_test and final_mp4.exists() and final_mp4.stat().st_size >= 8_192:
                cap_r79 = cv2.VideoCapture(str(final_mp4))
                if cap_r79.isOpened():
                    fps_r79 = max(1.0, float(cap_r79.get(cv2.CAP_PROP_FPS) or 30.0))
                    while True:
                        ok_r, bgr_r = cap_r79.read()
                        if not ok_r:
                            break
                        sm_r = cv2.resize(bgr_r, (270, 480), interpolation=cv2.INTER_AREA)
                        grays_r79.append(cv2.cvtColor(sm_r, cv2.COLOR_BGR2GRAY))
                    cap_r79.release()
            from concurrent.futures import ThreadPoolExecutor
            from pipeline.hardware_profile import resolve_cpu_budget

            has_grays_r79 = len(grays_r79) > 4 and not is_synth_test
            b_mask_r79 = np.ones((480, 270), dtype=bool)
            b_mask_r79[int(480 * 0.22) : int(480 * 0.82), int(270 * 0.18) : int(270 * 0.82)] = False

            def _eval_r79_cut(ct: dict[str, Any]) -> tuple[list[str], dict[str, Any] | None]:
                c_idx_ct = int(ct.get("clip_index") or 0)
                cut_no = int(ct.get("cut_index") or c_idx_ct)
                vp_ct = vp_by_num.get(c_idx_ct, {}) if isinstance(vp_by_num, dict) else {}
                cam_ct = str(ct.get("camera_move") or vp_ct.get("camera_move") or "").strip()
                is_brain_ct = _is_unified_brain_cut(ct, vp_ct)
                if is_brain_ct or cam_ct in EXPRESSIVE_V8_DRONE_CAMERA_MOVES:
                    return [], None
                local_violations: list[str] = []
                m_spd = float(ct.get("main_speed") or 1.0)
                if m_spd > float(R79M_HUMAN_CUT_MAX_MAIN_SPEED) + 1e-3:
                    local_violations.append(
                        f"cut {cut_no}: main_speed={m_spd:.2f}x > max {R79M_HUMAN_CUT_MAX_MAIN_SPEED:.2f}x"
                    )
                local_tel: dict[str, Any] | None = None
                if has_grays_r79:
                    dis_local = cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_FAST)
                    t0_r = float(ct.get("out_start_sec") or 0.0)
                    t1_r = float(ct.get("out_end_sec") or 0.0)
                    f0_r = max(0, int(round(t0_r * fps_r79)) + 2)
                    f1_r = min(len(grays_r79) - 1, int(round(t1_r * fps_r79)) - 2)
                    cam_ms: list[float] = []
                    subj_ms: list[float] = []
                    for fi_r in range(f0_r, f1_r - 1, 2):
                        if fi_r + 2 >= len(grays_r79):
                            break
                        fl_r = dis_local.calc(grays_r79[fi_r], grays_r79[fi_r + 2], None)
                        fx_r, fy_r = fl_r[..., 0], fl_r[..., 1]
                        mvx_r = float(np.median(fx_r[b_mask_r79]))
                        mvy_r = float(np.median(fy_r[b_mask_r79]))
                        cam_ms.append(float(np.hypot(mvx_r, mvy_r)))
                        res_r = np.hypot(fx_r - mvx_r, fy_r - mvy_r)
                        roi_r = res_r[int(480 * 0.12) : int(480 * 0.88), int(270 * 0.12) : int(270 * 0.88)]
                        subj_ms.append(float(np.percentile(roi_r, 90)))
                    arr_s = np.array(subj_ms) if subj_ms else np.zeros(1)
                    half_s = max(1, len(arr_s) // 2)
                    subj_p90_v = round(float(np.percentile(arr_s, 75)), 2)
                    cam_flow_v = round(float(np.mean(cam_ms)) if cam_ms else 0.0, 2)
                    sh_ratio_v = round(float(np.mean(arr_s[half_s:]) / max(0.15, float(np.mean(arr_s[:half_s])))), 2)
                    cut_ok = (
                        subj_p90_v >= float(R79M_HUMAN_MIN_SUBJ_P90_PX)
                        and sh_ratio_v >= float(R79M_HUMAN_MIN_SECOND_HALF_RATIO)
                        and m_spd <= float(R79M_HUMAN_CUT_MAX_MAIN_SPEED) + 1e-3
                    )
                    if subj_p90_v < float(R79M_HUMAN_MIN_SUBJ_P90_PX):
                        local_violations.append(
                            f"cut {cut_no}: subj_p90_px={subj_p90_v:.2f} < floor {R79M_HUMAN_MIN_SUBJ_P90_PX:.2f}"
                        )
                    if sh_ratio_v < float(R79M_HUMAN_MIN_SECOND_HALF_RATIO):
                        local_violations.append(
                            f"cut {cut_no}: second_half_ratio={sh_ratio_v:.2f} < floor {R79M_HUMAN_MIN_SECOND_HALF_RATIO:.2f}"
                        )
                    local_tel = {
                        "cut_index": cut_no,
                        "clip_index": c_idx_ct,
                        "main_speed": round(m_spd, 3),
                        "subj_p90_px": subj_p90_v,
                        "cam_flow_px": cam_flow_v,
                        "second_half_ratio": sh_ratio_v,
                        "passed": cut_ok,
                    }
                return local_violations, local_tel

            r79_workers = min(resolve_cpu_budget(cpu_budget), max(1, len(non_outro_cuts_r79)))
            if r79_workers > 1 and has_grays_r79 and len(non_outro_cuts_r79) > 1:
                prev_cv_t = cv2.getNumThreads()
                if prev_cv_t > 1:
                    cv2.setNumThreads(1)
                try:
                    with ThreadPoolExecutor(max_workers=r79_workers) as r79_pool:
                        r79_results = list(r79_pool.map(_eval_r79_cut, non_outro_cuts_r79))
                finally:
                    if prev_cv_t > 1:
                        cv2.setNumThreads(prev_cv_t)
            else:
                r79_results = [_eval_r79_cut(ct) for ct in non_outro_cuts_r79]
            for v_list, tel_item in r79_results:
                r79_violations.extend(v_list)
                if tel_item is not None:
                    r79_cut_telemetry.append(tel_item)
            gates["DQ_R79_human_character_motion"] = {
                "passed": (len(r79_violations) == 0),
                "violations": r79_violations,
                "cuts": r79_cut_telemetry,
            }
    if cap is not None:
        cap.release()

    if is_expressive_v8 and dq8_suspect_items:
        if save_report:
            from pipeline.dq8_suspect_classifier import save_dq8_suspect_evidence

            ev_out = save_dq8_suspect_evidence(p_dir, dq8_suspect_items)
            gates["DQ8_zero_uncanny_skin_gore"]["suspect_detections"] = ev_out["suspect_detections"]
            gates["DQ8_zero_uncanny_skin_gore"]["contact_sheet_path"] = ev_out["contact_sheet_path"]
        else:
            gates["DQ8_zero_uncanny_skin_gore"]["suspect_detections"] = [
                {
                    "cut_index": int(it["cut_index"]),
                    "box_index": int(it["box_index"]),
                    "timeline_sec": round(float(it["timeline_sec"]), 3),
                    "src_clip_sec": round(float(it["src_clip_sec"]), 3),
                    "frame_index": int(it.get("frame_index") or 0),
                    "bbox_in_roi": list(it["bbox_in_roi"]),
                    "suspect_tier": str(it["det_result"]["tier"]),
                    "reasons": list(it["det_result"].get("reasons") or []),
                    "metrics": dict(it["det_result"].get("metrics") or {}),
                }
                for it in dq8_suspect_items
            ]

    advisory_gates: dict[str, Any] = {}
    from pipeline.config import is_r85_flow_31_brain_plan as _is_r85_triage

    if _is_r85_triage(vp, script_doc, project_id=p_dir.name):
        # 3-Tier Rule Diet (CEO-approved): remove Tier-3 legacy gates and demote Tier-2 aesthetics to advisory score
        for _t3_key in (
            "DQ1_literal_analogy_frame_sync",
            "DQ12_three_distinct_thumbnails",
            "DQ_CAMEO_single_minicortex",
            "DQ_R76_brain_simulator_sq",
            "DQ_R76_anti_noise_pacing",
        ):
            gates.pop(_t3_key, None)
        for _t2_key in (
            "DQ2_clothed_cast_and_impact",
            "DQ4_brisk_storyteller_wpm",
            "DQ5_three_gear_cut_rhythm",
            "DQ_R76_unified_brain_share",
            "DQ_R79_human_character_motion",
        ):
            if _t2_key in gates:
                advisory_gates[_t2_key] = {**gates.pop(_t2_key), "tier": "tier2_advisory_score"}
        pre_issues = [
            x for x in pre_issues
            if not any(tok in x for tok in ("analogy", "Mini-Cortex", "cameo", "premature 3D brain"))
        ]

    passed_count = sum(1 for g in gates.values() if g["passed"])
    adv_penalty = sum(2.5 for g in advisory_gates.values() if not g.get("passed", True))
    score = round(max(0.0, (100.0 * passed_count / max(1, len(gates))) - adv_penalty), 1)
    all_passed = passed_count == len(gates) and len(pre_issues) == 0

    import hashlib
    mp4_sha = ""
    if final_mp4.exists():
        h = hashlib.sha256()
        with open(final_mp4, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        mp4_sha = h.hexdigest()

    report = {
        "project_id": p_dir.name,
        "schema": PROMPT_SCHEMA_VERSION_V8 if is_expressive_v8 else (PROMPT_SCHEMA_VERSION_V7 if is_v7 else 6),
        "style_profile": (
            EXPRESSIVE_25D_V8_STYLE_PROFILE
            if is_expressive_v8
            else (resolve_diorama_v7_style_profile(vp, edl, script_doc) if is_v7 else "dark_ceramic_v6")
        ),
        "final_mp4_sha256": mp4_sha,
        "passed": all_passed,
        "score": score,
        "gates_passed": f"{passed_count}/{len(gates)}",
        "pre_flow_issues": pre_issues,
        "gates": gates,
        "advisory_gates": advisory_gates,
    }
    if save_report:
        from pipeline.storage import ProjectStorage

        out_rep = p_dir / "05_assembly" / "dynamic_episode_qa_report.json"
        out_rep.parent.mkdir(parents=True, exist_ok=True)
        out_rep.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        ProjectStorage.record_if_manifest_tracks_stages(p_dir, "05_assembly", "dynamic_episode_qa_report.json", out_rep)
    return report
