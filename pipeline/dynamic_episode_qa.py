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
    REENACT_EDL_FILENAME,
    REENACT_MIN_DHASH_DISTANCE,
    VIDEO_FPS,
    is_diorama_v7_plan,
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

_WARDROBE_OR_HAT_RE = re.compile(
    r"\b(?:hat|hats|cap|caps|helmet|helmets|bonnet|coat|coats|lab\s+coats?|blazers?|cardigans?|sweaters?|duster|vest|vests|"
    r"waistcoats?|jackets?|shirts?|sleeves|cuffs|trousers|slacks|pants|aprons?|gowns?|suits?|collars?|ties?|gloves|boots|"
    r"robes?|uniforms?|scrubs|dress|dresses|tunics?|linen\s+head\s+wrap|head\s+wrap|poncho)\b",
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
    r"juggle(?:s)?|juggling|glide(?:s)?|gliding|cross(?:es|ing)?|place(?:s)?|placing|rest(?:s|ing)?|set(?:s|ting)?)\b",
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
    anatomy mentions of this episode (supporting both Schema v6 and Schema v7).
    """
    clean_sents = [str(s).strip() for s in sentences if str(s).strip()]
    by_sent = _clips_by_sentence(rendered_clips)
    is_v7 = (
        is_diorama_v7_plan(visual_plan)
        or (isinstance(script_doc, dict) and is_diorama_v7_plan(script_doc))
        or any(int(c.get("schema_version") or 6) >= PROMPT_SCHEMA_VERSION_V7 for c in rendered_clips)
    )
    is_porcelain = bool(is_v7 and is_porcelain_v7_plan(visual_plan, *(rendered_clips or []), script_doc))

    analogy_locks: list[dict[str, Any]] = []
    anatomy_locks: list[dict[str, Any]] = []
    early_hook_sentences: list[int] = []

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
    if is_v7:
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
        if g_name in ("frosted_crystal_specimen", "lowpoly_matte_brain", "porcelain_living_brain"):
            continue
        scene_txt = str(c.get("scene") or "")
        if is_v7:
            if (
                g_name in ("lowpoly_hands_closeup", "lowpoly_pov_hands", "porcelain_hands_closeup", "porcelain_pov_hands")
                or _LOWPOLY_CAST_RE.search(scene_txt)
                or _PORCELAIN_V7_CAST_RE.search(scene_txt)
            ):
                cast_clip_locks.append(
                    {
                        "clip_number": idx,
                        "sentence_index": c.get("sentence_index"),
                        "act": c.get("act"),
                        "requires_wardrobe_or_hat": True,
                        "min_action_verbs": 2,
                        "cv_signature": "bright_porcelain_world" if is_porcelain else "bright_lowpoly_world",
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

    tempo_targets = (
        {
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
        if is_v7
        else {
            "wpm_min": 162.0,
            "wpm_max": 208.0,
            "avg_cut_max_sec": 2.90,
            "fast_cut_threshold_sec": 2.15,
            "fast_cut_ratio_min": 0.18,
            "max_single_speech_cut_sec": 4.55,
            "max_clip_reuse": DIORAMA_MAX_CLIP_REUSE,
        }
    )

    return {
        "schema": "episode_qa_contract_v2" if is_v7 else "episode_qa_contract_v1",
        "is_v7": is_v7,
        "style_profile": (
            resolve_diorama_v7_style_profile(visual_plan, *(rendered_clips or []), script_doc)
            if is_v7
            else "dark_ceramic_v6"
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
        except Exception:
            pass
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
    Zero-tolerance Pre-Flow Gate (R62/R63 Gate 1):
      - Rejects abstract wooden token boards whenever a literal analogy (football field, bowling ball, etc.) is spoken.
      - Enforces period hats/wardrobe and >=2 active motion/impact verbs on every cast/hands clip.
      - Requires direct cast/hands reenactment in Acts 1-2 when physical trauma/events are narrated.
      - Verifies brain visualization alignment on anatomy-naming sentences.
    """
    issues: list[str] = []
    if not rendered_clips or not sentences:
        return issues

    contract = compile_episode_qa_contract(visual_plan, sentences, rendered_clips, script_doc=script_doc)
    is_v7 = bool(contract.get("is_v7"))
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
        if not _WARDROBE_OR_HAT_RE.search(scene_txt):
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
                    str(c.get("grammar") or "") in ("lowpoly_hands_closeup", "lowpoly_pov_hands", "porcelain_hands_closeup", "porcelain_pov_hands")
                    or bool(_LOWPOLY_CAST_RE.search(str(c.get("scene") or "")))
                    or bool(_PORCELAIN_V7_CAST_RE.search(str(c.get("scene") or "")))
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
    brain_grammars = {"arch_brain_maquette", "frosted_crystal_specimen", "lowpoly_matte_brain", "porcelain_living_brain"}
    for a_lock in contract["anatomy_locks"]:
        b_nums = a_lock["bound_clip_numbers"]
        ok_brain = False
        for n in b_nums:
            c = clips_by_num.get(n) or {}
            g = str(c.get("grammar") or "")
            sc = str(c.get("scene") or "").lower()
            if g in brain_grammars or any(
                k in sc for k in ("brain", "cortex", "subcortical", "limbic", "amygdala", "hippocamp", "fiber", "tract", "cable")
            ):
                ok_brain = True
                break
        if not ok_brain:
            issues.append(
                f"[dynamic_qa:anatomy_sync] sentence {a_lock['sentence_index']} names {a_lock['anatomy_terms']} "
                f"but bound clip(s) {b_nums} do not depict 3D brain/neural anatomy (R62/R63)"
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
) -> list[np.ndarray]:
    """
    Returns clean upper + lower scene bands covering the full viewport outside programmatic ASS text:
      - Outro sky card (`OutroTitle` at `Y ≈ 33%..47%`): `[3%..30%]` + `[49%..97%]`.
      - Top overlay active (`ChapterHeadline` or `SplitLeft/Right` at `Y ≈ 9%..22%`): `[23%..58%]` + `[69%..97%]`.
      - Standard speech cut (`Default` subtitle at `Y ≈ 59%..68%`): `[3%..58%]` + `[69%..97%]`.
    """
    h, w = frame_bgr.shape[:2]
    x0, x1 = int(w * 0.03), int(w * 0.97)
    if is_outro:
        bands = ((0.03, 0.30), (0.49, 0.97))
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
            if is_v7 or c_lock.get("cv_signature") in ("bright_lowpoly_world", "bright_porcelain_world"):
                mean_y = float(np.mean([float(np.mean(cv2.cvtColor(f, cv2.COLOR_BGR2GRAY))) for f in frames]))
                checks_run.append(f"bright_v7_y={mean_y:.1f}")
                if mean_y < 78.0:
                    r_msg = f"dark_void_in_v7_cast_clip:mean_y={mean_y:.1f}<78.0"
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


def verify_final_mp4_against_contract(
    project_id_or_dir: str | Path,
    run_asr_sync: bool = True,
    save_report: bool = True,
    contract: dict[str, Any] | None = None,
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

    script_doc = json.loads(script_path.read_text(encoding="utf-8"))
    vp = json.loads(vp_path.read_text(encoding="utf-8"))
    edl = json.loads(edl_path.read_text(encoding="utf-8"))
    vr = json.loads(vr_path.read_text(encoding="utf-8"))
    is_v7 = is_diorama_v7_plan(vp) or is_diorama_v7_plan(script_doc) or int(edl.get("schema") or 6) >= PROMPT_SCHEMA_VERSION_V7
    is_porcelain = bool(is_v7 and is_porcelain_v7_plan(vp, edl, script_doc))
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
    is_synth_test = vr.get("engine") == "kokoro-onnx" and not (p_dir / "04_audio" / "tts_diorama" / "clip_1.wav").exists()

    ass_txt = ass_path.read_text(encoding="utf-8") if ass_path.exists() else ""
    chapter_spans: list[tuple[float, float]] = []
    anatomy_label_spans: list[tuple[float, float]] = []
    for ln in ass_txt.splitlines():
        if ln.startswith("Dialogue:"):
            parts = ln.split(",", 9)
            if len(parts) >= 10:
                if ",ChapterHeadline," in ln:
                    chapter_spans.append((_parse_ass_ts_sec(parts[1]), _parse_ass_ts_sec(parts[2])))
                elif ",AnatomyLabel," in ln:
                    anatomy_label_spans.append((_parse_ass_ts_sec(parts[1]), _parse_ass_ts_sec(parts[2])))
    top_overlay_spans = chapter_spans + anatomy_label_spans

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
        for c_lock in contract["cast_clip_locks"]:
            c_num = int(c_lock["clip_number"])
            matching_cuts = [c for c in cuts if int(c.get("clip_index") or 0) == c_num]
            for mc in matching_cuts:
                mt = 0.5 * (float(mc["out_start_sec"]) + float(mc["out_end_sec"]))
                frm = _get_frame(mt)
                if frm is not None:
                    if is_v7:
                        y_m = float(np.mean(cv2.cvtColor(frm[: int(frm.shape[0] * 0.60), :], cv2.COLOR_BGR2GRAY)))
                        if y_m < 75.0:
                            dq2_failures.append(f"clip {c_num} @ {mt:.2f}s dark-void leak (mean_y={y_m:.1f} < 75.0)")
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

        # DQ3: Anatomy Mention <-> 3D Brain Cut Sync
        brain_grammars = {"arch_brain_maquette", "frosted_crystal_specimen", "lowpoly_matte_brain", "porcelain_living_brain"}
        dq3_failures: list[str] = [x for x in pre_issues if "anatomy_sync" in x]
        for an_lock in contract["anatomy_locks"]:
            s_cuts = cuts_by_sent.get(int(an_lock["sentence_index"]), [])
            if not any(str(c.get("grammar")) in brain_grammars for c in s_cuts):
                dq3_failures.append(f"sentence {an_lock['sentence_index']} ({an_lock['anatomy_terms']}) not mapped to brain cut in EDL")

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
            all_cuts_have_camera = bool(cuts) and all(
                str(c.get("camera_move") or "") in DIORAMA_V7_CAMERA_MOVES for c in cuts
            )
            cam_counts_edl: dict[str, int] = {m: 0 for m in DIORAMA_V7_CAMERA_MOVES}
            for c in cuts:
                cm = str(c.get("camera_move") or "")
                if cm in cam_counts_edl:
                    cam_counts_edl[cm] += 1
            n_edl_tot = max(1, len(cuts))
            locked_cam_ratio = round(cam_counts_edl["locked_tripod"] / float(n_edl_tot), 4)
            zoom_cam_ratio = round(
                (cam_counts_edl["gentle_push_in"] + cam_counts_edl["clean_pullback_reveal"]) / float(n_edl_tot),
                4,
            )
            pan_left_cuts = cam_counts_edl["pan_left"]
            pan_right_cuts = cam_counts_edl["pan_right"]
            camera_ratios_ok = (
                all_cuts_have_camera
                and locked_cam_ratio >= DIORAMA_V7_LOCKED_CAMERA_MIN_RATIO
                and zoom_cam_ratio <= DIORAMA_V7_ZOOM_CAMERA_MAX_RATIO
                and pan_left_cuts >= 1
                and pan_right_cuts >= 1
            )

            hstack_cuts = [c for c in cuts if c.get("mode") == "split_hstack"]
            if not hstack_cuts:
                hstack_divider_ok = False
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
            dq5_ok = (
                len(cuts) >= DIORAMA_TARGET_CUT_MIN
                and abs(fps - float(DIORAMA_V7_VIDEO_FPS)) <= 0.25
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
            dq5_ok = (
                len(cuts) >= DIORAMA_TARGET_CUT_MIN
                and avg_cut <= t_targets["avg_cut_max_sec"] + (0.45 if is_synth_test else 0.0)
                and max_cut <= t_targets["max_single_speech_cut_sec"] + (0.60 if is_synth_test else 0.0)
            )

        # DQ6: Zero Clip Reuse
        dq6_ok = bool(edl.get("zero_clip_reuse")) and int(edl.get("max_clip_reuse") or 99) <= DIORAMA_MAX_CLIP_REUSE

        # DQ7, DQ8, DQ9: Inspect 100% of ALL EDL cuts (including outro) across full non-subtitle scene bands in Schema v7
        freeze_cuts: list[int] = []
        skin_leaks: list[int] = []
        plaque_leaks: list[int] = []
        cut_lumas: list[float] = []
        cut_dark_v35: list[float] = []
        cut_sats: list[float] = []
        inspected_cuts = cuts if is_v7 else [c for c in cuts[::3] if not c.get("outro_sky_card")]
        for c in inspected_cuts:
            is_outro = bool(c.get("outro_sky_card"))
            c_start = float(c["out_start_sec"])
            c_end = float(c["out_end_sec"])
            t0 = c_start + 0.08
            t1 = max(t0 + 0.20, c_end - 0.08)
            t_mid = 0.5 * (t0 + t1)
            f_a = _get_frame(t0)
            f_mid = _get_frame(t_mid)
            f_b = _get_frame(t1)
            if f_a is not None and f_b is not None:
                h_f, _w_f = f_a.shape[:2]
                has_top_ov = (
                    c.get("mode") in ("split_hstack", "split_vstack")
                    or any(cs0 < c_end - 0.04 and cs1 > c_start + 0.04 for cs0, cs1 in top_overlay_spans)
                )

                def _band_diff(fa_in: np.ndarray, fb_in: np.ndarray) -> float:
                    ra_l = _non_subtitle_scene_rois(fa_in, has_top_overlay=has_top_ov, is_outro=is_outro)
                    rb_l = _non_subtitle_scene_rois(fb_in, has_top_overlay=has_top_ov, is_outro=is_outro)
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
                rc_meta = rendered_by_num.get(int(c.get("clip_index") or 0), {})
                vp_meta = vp_by_num.get(int(c.get("clip_index") or 0), {})
                raw_g_str = str(c.get("grammar") or rc_meta.get("grammar") or vp_meta.get("grammar") or "")
                g_str = normalize_porcelain_v7_grammar(raw_g_str) if is_porcelain else raw_g_str
                ordered_pts: list[np.ndarray | None] = [f_a, f_mid, f_b]
                intra_frozen = False
                if (
                    is_v7
                    and not is_synth_test
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
                            if sum(1 for qd in q_diffs if qd < 0.28) >= 2 or (
                                max(q_diffs) < 2.0 and float(np.median(q_diffs)) < 1.45
                            ):
                                intra_frozen = True
                if diff < 0.30 or intra_frozen:
                    freeze_cuts.append(int(c["cut_index"]))

                sample_frames_cut = [f for f in ordered_pts if f is not None]
                if not is_synth_test:
                    all_rois_cut = [
                        r
                        for sf in (f_a, f_mid if f_mid is not None else f_a, f_b)
                        for r in _non_subtitle_scene_rois(sf, has_top_overlay=has_top_ov, is_outro=is_outro)
                    ]
                    max_plaque_cut = max((_max_horizontal_plaque_glyph_run(r) for r in all_rois_cut), default=0)
                    if max_plaque_cut >= (5 if is_v7 else 8):
                        plaque_leaks.append(int(c["cut_index"]))

                if is_v7:
                    mid_bgr = f_a[int(h_f * 0.27) : int(h_f * 0.55), :]
                    mid_gray = cv2.cvtColor(mid_bgr, cv2.COLOR_BGR2GRAY)
                    hsv_m = cv2.cvtColor(mid_bgr, cv2.COLOR_BGR2HSV)
                    if not is_outro:
                        cut_lumas.append(float(np.mean(mid_gray)))
                        cut_dark_v35.append(float(np.mean(hsv_m[:, :, 2] < 35)))
                        cut_sats.append(float(np.mean(hsv_m[:, :, 1])))
                    if not is_synth_test:
                        cut_leak = False
                        if any(detect_escher_dual_edge_closeup(sf, g_str) for sf in sample_frames_cut) or detect_transient_top_intrusion_pov(
                            sample_frames_cut, g_str
                        ):
                            cut_leak = True
                        if is_porcelain and g_str == "porcelain_living_brain":
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
                            and g_str in ("porcelain_hands_closeup", "porcelain_pov_hands", "porcelain_fullbleed_world")
                        ):
                            flesh_cap_dq8 = PORCELAIN_V7_HUMAN_SKIN_MAX + 0.04
                            for sf in sample_frames_cut:
                                sh_f, sw_f = sf.shape[:2]
                                full_roi_sf = sf[int(sh_f * 0.10) : int(sh_f * 0.92), int(sw_f * 0.04) : int(sw_f * 0.96)]
                                if compute_porcelain_flesh_leak_ratio(full_roi_sf) > flesh_cap_dq8:
                                    cut_leak = True
                                    break
                                if c.get("mode") not in ("split_hstack", "split_vstack") and detect_unintended_horizontal_split_seam(sf) >= 0.72:
                                    cut_leak = True
                                    break
                        if cut_leak:
                            skin_leaks.append(int(c["cut_index"]))
                elif str(c.get("grammar")) in ("arch_brain_maquette", "frosted_crystal_specimen") and not is_synth_test:
                    mid_bgr = f_a[int(h_f * 0.27) : int(h_f * 0.55), :]
                    hsv = cv2.cvtColor(mid_bgr, cv2.COLOR_BGR2HSV)
                    skin_m = (
                        (hsv[:, :, 0] >= 5) & (hsv[:, :, 0] <= 17)
                        & (hsv[:, :, 1] >= 55) & (hsv[:, :, 1] <= 145)
                        & (hsv[:, :, 2] >= 110) & (hsv[:, :, 2] <= 235)
                    )
                    if float(np.mean(skin_m)) > 0.22:
                        skin_leaks.append(int(c["cut_index"]))

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

    ep_mean_luma = round(float(np.mean(cut_lumas)), 2) if cut_lumas else 0.0
    ep_dark_v35 = round(float(np.mean(cut_dark_v35)), 4) if cut_dark_v35 else 0.0
    ep_mean_sat = round(float(np.mean(cut_sats)), 2) if cut_sats else 0.0
    if is_v7 and not is_synth_test:
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
    if is_v7:
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
    if is_v7:
        rms_voiced = float(vr.get("true_rms_voiced_ratio") or vr.get("active_speech_ratio") or 0.0)
        dq11_ok = (
            audio_master.exists()
            and audio_master.stat().st_size > 100_000
            and wav_channels == 2
            and stereo_decorrelated
            and float(vr.get("active_speech_ratio") or 0.0) >= DIORAMA_V7_ACTIVE_VOICED_RMS_RATIO_MIN
            and (is_synth_test or rms_voiced >= DIORAMA_V7_ACTIVE_VOICED_RMS_RATIO_MIN)
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
        "DQ6_zero_clip_reuse": {"passed": dq6_ok, "max_clip_reuse": edl.get("max_clip_reuse")},
        "DQ7_continuous_motion_no_freeze": {"passed": len(freeze_cuts) == 0, "cuts_inspected": len(inspected_cuts), "freeze_cuts": freeze_cuts},
        "DQ8_zero_uncanny_skin_gore": {
            "passed": len(skin_leaks) == 0,
            "skin_leak_cuts": skin_leaks,
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
            "min_voiced_rms_ratio": (DIORAMA_V7_ACTIVE_VOICED_RMS_RATIO_MIN if is_v7 else 0.84),
        },
        "DQ12_three_distinct_thumbnails": {"passed": dq12_ok},
    }
    passed_count = sum(1 for g in gates.values() if g["passed"])
    score = round(100.0 * passed_count / len(gates), 1)
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
        "schema": PROMPT_SCHEMA_VERSION_V7 if is_v7 else 6,
        "style_profile": (resolve_diorama_v7_style_profile(vp, edl, script_doc) if is_v7 else "dark_ceramic_v6"),
        "final_mp4_sha256": mp4_sha,
        "passed": all_passed,
        "score": score,
        "gates_passed": f"{passed_count}/{len(gates)}",
        "pre_flow_issues": pre_issues,
        "gates": gates,
    }
    if save_report:
        from pipeline.storage import ProjectStorage

        out_rep = p_dir / "05_assembly" / "dynamic_episode_qa_report.json"
        out_rep.parent.mkdir(parents=True, exist_ok=True)
        out_rep.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        ProjectStorage.record_if_manifest_tracks_stages(p_dir, "05_assembly", "dynamic_episode_qa_report.json", out_rep)
    return report
