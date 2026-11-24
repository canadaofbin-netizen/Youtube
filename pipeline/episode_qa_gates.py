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

    return issues
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
    from pipeline.media_cache import get_active_mp4_session, stage_local_file

    src_p = Path(mp4_path)
    if src_p.exists():
        local_p, mp4_sha = stage_local_file(src_p)
    else:
        local_p, mp4_sha = src_p, ""
    sess = get_active_mp4_session(mp4_sha) if mp4_sha else None
    if sess is not None and sess.get("all_frames_cached") and sess.get("frames"):
        fps = float(sess.get("fps") or 24.0)
        fc = int(sess.get("decoded_fc") or sess.get("header_fc") or 0)
        dur = fc / max(1.0, fps)
        s0 = max(0.0, float(t_start))
        s1 = float(dur if t_end is None else min(dur, float(t_end)))
        if s1 - s0 < 0.25 or fc <= 0:
            return 0.0
        f0 = max(0, int(round(s0 * fps)))
        f1 = min(max(0, fc - 1), int(round(s1 * fps)))
        step = max(1, int(round(fps * 0.12)))
        sampled: list[np.ndarray] = [
            cv2.resize(cv2.cvtColor(sess["frames"][cur], cv2.COLOR_BGR2GRAY), (180, 320))
            for cur in range(f0, f1 + 1, step)
            if cur in sess["frames"]
        ]
    else:
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
        sampled = []
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
            from pipeline.ref_qa import _dhash_64, _hamming_hex

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

