"""
ALL ABOUT BRAIN — Schema v7/v6 Neuro-Diorama 20-Video Batch Orchestrator
=========================================================================
Resumable, checkpointed mass-production orchestrator for our 20 unpublished
7-Pillar-balanced `neuro_diorama` episodes (default Schema v7 `lowpoly_pastel_v7`
with unified `1.08x` / `+8%` `en-US-AndrewMultilingualNeural` `+14Hz` Silk Clean at `24fps`, plus Schema v6 fallback):

  1. Syncs canonical `research_dossiers/<slug>/diorama_v7_lowpoly/` (or `diorama_v6_dynamic/`)
     into `projects/<project_id>/`.
  2. Runs pre-Flow `prompt-gate` (R56-R63 + R44-D dossier fact trace + Zero-Plaque noun lock)
     AND pre-Flow continuous TTS master clock verification (`140.0s..179.0s` v7 / `170.0s..179.0s` v6).
  3. Runs 5-tab sharded `0 credits` Google Flow generation (`flow_diorama_sharded_worker.py`)
     strictly sequentially per project (`<= FLOW_MAX_PARALLEL_BATCH_SIZE` tabs total, closing all
     5 worker tabs in `finally` between projects so Whale memory never leaks across 20 hours).
  4. Immediately runs `assemble_diorama_project`, copies master `.mp4` to
     `Completed_Psychology_100_Shorts/` (preserving R25 single-MP4 inside `projects/<id>/05_assembly/`),
     enforces R62 `episode-qa` + R64 `posthoc-qa` + `VideoAutopsyEngine` + `verify_integrity`,
     builds `asset_manifest`, and syncs `knowledge_base/` (`R50-B`).
  5. Writes live resumable checkpoints to `BCI_Shorts_Channel/diorama_batch_20_status.json`.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import datetime as dt
import hashlib
import inspect
import json
import math
import os
import re
import shutil
import time
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from pipeline import diorama_assembler as _diorama_assembler_mod
from pipeline import research_dossier as rd
from pipeline.asset_manifest import build_asset_manifest
from pipeline.brain_simulator_blender import (
    is_brain_simulator_clip_spec,
    render_project_brain_simulator_clips_parallel,
)
from pipeline.config import (
    AI_DISCLOSURE_SENTENCE,
    DIORAMA_DURATION_MIN_SEC,
    FLOW_MAX_PARALLEL_BATCH_SIZE,
    MIN_CLIP_SIZE_BYTES,
    PROJECTS_DIR,
    SHORTS_HARD_CEILING_SEC,
    WORKSPACE_ROOT,
)
from pipeline.diorama_assembler import (
    assemble_diorama_project,
    build_crosscut_edl,
    generate_diorama_audio_master,
    load_diorama_script_sentences,
)
from pipeline.flow_diorama_sharded_worker import run_sharded_diorama_flow_generation
from pipeline.flow_prompt_builder import build_diorama_v6_prompts, write_flow_prompts_json
from pipeline.hardware_profile import resolve_cpu_budget
from pipeline.media_cache import atomic_commit_from_scratch, ram_tempdir
from pipeline.prompt_quality_v5 import validate_production_diorama_v6
from pipeline.publish import validate_diorama_paradox_title
from pipeline.storage import STAGE_NAMES, ProjectStorage, numeric_clip_sort_key
from pipeline.video_autopsy import VideoAutopsyEngine
from pipeline.voice_fallback import synthesize_continuous_diorama_track

CHANNEL_DIR = Path(WORKSPACE_ROOT) / "BCI_Shorts_Channel"
COMPLETED_SHORTS_DIR = Path(WORKSPACE_ROOT) / "Completed_Psychology_100_Shorts"
BATCH_STATUS_PATH = CHANNEL_DIR / "diorama_batch_20_status.json"

_PLAQUE_TRIGGER_NOUNS_RE = re.compile(
    r"\b(?:plaques?|nameplates?|signboards?|chalkboards?|blackboards?|inscribed|engraved|"
    r"newspapers?|headlines?|textbooks?|ledgers?|labelled|labeled|numerals?)\b",
    flags=re.IGNORECASE,
)

DIORAMA_DAILY_30_SPECS: tuple[dict[str, Any], ...] = (
    # Wave 1 (Days 2-6: 2026-11-05 .. 2026-11-09 19:30 EST) — sleep, habits, memory, anxiety, relationships
    {"index": 1, "wave": 1, "everyday_domain": "sleep", "schedule_est": "2026-11-05 19:30 EST", "project_id": "boost_01_sleep_first_night_watch", "slug": "v2_sleep_first_night_hemisphere_watch", "pillar": "brain_health"},
    {"index": 2, "wave": 1, "everyday_domain": "habits", "schedule_est": "2026-11-06 19:30 EST", "project_id": "boost_02_habits_marshmallow_trust", "slug": "v2_habits_marshmallow_prefrontal_trust", "pillar": "brain_basics"},
    {"index": 3, "wave": 1, "everyday_domain": "memory", "schedule_est": "2026-11-07 19:30 EST", "project_id": "boost_03_memory_loftus_false_engram", "slug": "v2_memory_loftus_false_alibi_engram", "pillar": "brain_mysteries"},
    {"index": 4, "wave": 1, "everyday_domain": "anxiety", "schedule_est": "2026-11-08 19:30 EST", "project_id": "boost_04_anxiety_third_person_chatter", "slug": "v2_anxiety_kross_third_person_amygdala", "pillar": "brain_history"},
    {"index": 5, "wave": 1, "everyday_domain": "relationships", "schedule_est": "2026-11-09 19:30 EST", "project_id": "boost_05_relationships_handholding_pain", "slug": "v2_relationships_coan_handholding_pain_grid", "pillar": "brain_news"},
    # Wave 2 (Days 7-11: 2026-11-10 .. 2026-11-14 19:30 EST)
    {"index": 6, "wave": 2, "everyday_domain": "sleep", "schedule_est": "2026-11-10 19:30 EST", "project_id": "boost_06_sleep_pink_noise_spindles", "slug": "v2_sleep_ngo_closed_loop_slow_wave_tones", "pillar": "bci_tech"},
    {"index": 7, "wave": 2, "everyday_domain": "habits", "schedule_est": "2026-11-11 19:30 EST", "project_id": "boost_07_habits_variable_slot_dopamine", "slug": "v2_habits_skinner_variable_scroll_prediction_error", "pillar": "bci_ethics"},
    {"index": 8, "wave": 2, "everyday_domain": "memory", "schedule_est": "2026-11-12 19:30 EST", "project_id": "boost_08_memory_doorway_event_boundary", "slug": "v2_memory_radvansky_doorway_hippocampal_reset", "pillar": "brain_basics"},
    {"index": 9, "wave": 2, "everyday_domain": "anxiety", "schedule_est": "2026-11-13 19:30 EST", "project_id": "boost_09_anxiety_physiological_sigh_prebotzinger", "slug": "v2_anxiety_double_inhale_sigh_vagal_brake", "pillar": "brain_health"},
    {"index": 10, "wave": 2, "everyday_domain": "relationships", "schedule_est": "2026-11-14 19:30 EST", "project_id": "boost_10_relationships_social_rejection_dacc", "slug": "v2_relationships_cyberball_ghosting_pain_overlap", "pillar": "brain_mysteries"},
    # Wave 3 (Days 12-16: 2026-11-15 .. 2026-11-19 19:30 EST)
    {"index": 11, "wave": 3, "everyday_domain": "sleep", "schedule_est": "2026-11-15 19:30 EST", "project_id": "boost_11_sleep_caffeine_adenosine_quarter_life", "slug": "v2_sleep_afternoon_coffee_circadian_shift", "pillar": "brain_news"},
    {"index": 12, "wave": 3, "everyday_domain": "habits", "schedule_est": "2026-11-16 19:30 EST", "project_id": "boost_12_habits_stale_popcorn_context_cue", "slug": "v2_habits_neal_wood_context_striatum_autopilot", "pillar": "brain_health"},
    {"index": 13, "wave": 3, "everyday_domain": "memory", "schedule_est": "2026-11-17 19:30 EST", "project_id": "boost_13_memory_testing_effect_wakeful_replay", "slug": "v2_memory_roediger_retrieval_hippocampal_ripple", "pillar": "bci_tech"},
    {"index": 14, "wave": 3, "everyday_domain": "anxiety", "schedule_est": "2026-11-18 19:30 EST", "project_id": "boost_14_anxiety_uncertainty_worse_than_pain", "slug": "v2_anxiety_de_berker_uncertainty_pupil_stress", "pillar": "brain_mysteries"},
    {"index": 15, "wave": 3, "everyday_domain": "relationships", "schedule_est": "2026-11-19 19:30 EST", "project_id": "boost_15_relationships_asch_group_visual_cortex", "slug": "v2_relationships_asch_conformity_amygdala_override", "pillar": "bci_ethics"},
    # Wave 4 (Days 17-21: 2026-11-20 .. 2026-11-24 19:30 EST)
    {"index": 16, "wave": 4, "everyday_domain": "sleep", "schedule_est": "2026-11-20 19:30 EST", "project_id": "boost_16_sleep_warm_shower_distal_cooling", "slug": "v2_sleep_haghayegh_warm_bath_preoptic_thermostat", "pillar": "brain_history"},
    {"index": 17, "wave": 4, "everyday_domain": "habits", "schedule_est": "2026-11-21 19:30 EST", "project_id": "boost_17_habits_fresh_start_temporal_landmark", "slug": "v2_habits_milkman_fresh_start_self_continuity", "pillar": "brain_news"},
    {"index": 18, "wave": 4, "everyday_domain": "memory", "schedule_est": "2026-11-22 19:30 EST", "project_id": "boost_18_memory_photo_taking_impairment", "slug": "v2_memory_henkel_camera_cognitive_offloading", "pillar": "brain_health"},
    {"index": 19, "wave": 4, "everyday_domain": "anxiety", "schedule_est": "2026-11-23 19:30 EST", "project_id": "boost_19_anxiety_affect_labeling_rvlpfc", "slug": "v2_anxiety_lieberman_name_it_to_tame_it_amygdala", "pillar": "bci_tech"},
    {"index": 20, "wave": 4, "everyday_domain": "relationships", "schedule_est": "2026-11-24 19:30 EST", "project_id": "boost_20_relationships_capilano_bridge_misattribution", "slug": "v2_relationships_dutton_aron_arousal_insula", "pillar": "brain_basics"},
    # Wave 5 (Days 22-26: 2026-11-25 .. 2026-11-29 19:30 EST)
    {"index": 21, "wave": 5, "everyday_domain": "sleep", "schedule_est": "2026-11-25 19:30 EST", "project_id": "boost_21_sleep_snooze_inertia_prefrontal_lag", "slug": "v2_sleep_snooze_fragmented_rem_cortical_boot", "pillar": "brain_mysteries"},
    {"index": 22, "wave": 5, "everyday_domain": "habits", "schedule_est": "2026-11-26 19:30 EST", "project_id": "boost_22_habits_implementation_if_then_reflex", "slug": "v2_habits_gollwitzer_if_then_prospective_cue", "pillar": "brain_history"},
    {"index": 23, "wave": 5, "everyday_domain": "memory", "schedule_est": "2026-11-27 19:30 EST", "project_id": "boost_23_memory_tip_of_tongue_phonological_gap", "slug": "v2_memory_brown_mcneill_tot_left_insula_block", "pillar": "brain_news"},
    {"index": 24, "wave": 5, "everyday_domain": "anxiety", "schedule_est": "2026-11-28 19:30 EST", "project_id": "boost_24_anxiety_reappraisal_excited_vs_calm", "slug": "v2_anxiety_brooks_get_excited_arousal_reframe", "pillar": "bci_ethics"},
    {"index": 25, "wave": 5, "everyday_domain": "relationships", "schedule_est": "2026-11-29 19:30 EST", "project_id": "boost_25_relationships_phubbing_phone_on_table", "slug": "v2_relationships_przybylski_silent_phone_attention_drain", "pillar": "brain_health"},
    # Wave 6 (Days 27-31: 2026-11-30 .. 2026-12-04 19:30 EST)
    {"index": 26, "wave": 6, "everyday_domain": "sleep", "schedule_est": "2026-11-30 19:30 EST", "project_id": "boost_26_sleep_rem_emotional_overnight_therapy", "slug": "v2_sleep_walker_rem_norepinephrine_free_dreaming", "pillar": "brain_basics"},
    {"index": 27, "wave": 6, "everyday_domain": "habits", "schedule_est": "2026-12-01 19:30 EST", "project_id": "boost_27_habits_temptation_bundling_effort_discounting", "slug": "v2_habits_milkman_audiobook_gym_anterior_cingulate", "pillar": "bci_tech"},
    {"index": 28, "wave": 6, "everyday_domain": "memory", "schedule_est": "2026-12-02 19:30 EST", "project_id": "boost_28_memory_method_of_loci_taxi_grid", "slug": "v2_memory_maguire_memory_athlete_place_network", "pillar": "brain_history"},
    {"index": 29, "wave": 6, "everyday_domain": "anxiety", "schedule_est": "2026-12-03 19:30 EST", "project_id": "boost_29_anxiety_tetris_reconsolidation_visuospatial", "slug": "v2_anxiety_holmes_tetris_visual_memory_blockade", "pillar": "brain_news"},
    {"index": 30, "wave": 6, "everyday_domain": "relationships", "schedule_est": "2026-12-04 19:30 EST", "project_id": "boost_30_relationships_bystander_diffusion_motor_freeze", "slug": "v2_relationships_darley_latane_crowd_premotor_inhibition", "pillar": "brain_mysteries"},
)

DIORAMA_BATCH_20_SPECS: tuple[dict[str, Any], ...] = DIORAMA_DAILY_30_SPECS


def select_batch_specs(wave: str = "all", project_ids: list[str] | None = None) -> list[dict[str, Any]]:
    if project_ids:
        by_pid = {str(s["project_id"]): dict(s) for s in DIORAMA_DAILY_30_SPECS}
        out: list[dict[str, Any]] = []
        for idx, pid in enumerate(project_ids, start=1):
            if pid in by_pid:
                out.append(dict(by_pid[pid]))
                continue
            p_dir = Path(PROJECTS_DIR) / pid
            m_path = p_dir / "00_project_manifest.json"
            s_path = p_dir / "02_script" / "script.json"
            m_doc = json.loads(m_path.read_text(encoding="utf-8")) if m_path.exists() else {}
            s_doc = json.loads(s_path.read_text(encoding="utf-8")) if s_path.exists() else {}
            slug = str(m_doc.get("dossier_slug") or s_doc.get("dossier") or "").strip()
            pillar = str(m_doc.get("pillar") or s_doc.get("pillar") or "").strip()
            if slug and pillar:
                out.append({"index": idx, "wave": 0, "project_id": pid, "slug": slug, "pillar": pillar})
        return out
    w = str(wave or "all").strip().lower()
    if w in ("all", "1-6", "1-4", "30", "20"):
        return [dict(s) for s in DIORAMA_DAILY_30_SPECS]
    w_num = int(w)
    return [dict(s) for s in DIORAMA_DAILY_30_SPECS if int(s["wave"]) == w_num]


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


_PILLAR_TOPIC_HASHTAG_MAP: dict[str, list[str]] = {
    "brain_health": ["#BrainHealth", "#MentalHealth", "#Neuroscience", "#Psychology"],
    "brain_mysteries": ["#BrainScience", "#Psychology", "#Neurology", "#HumanMind"],
    "bci_tech": ["#BCI", "#Neurotech", "#BrainScience", "#FutureTech"],
    "brain_news": ["#NeuroscienceNews", "#BrainResearch", "#Neurotechnology", "#Science"],
    "brain_history": ["#NeuroscienceHistory", "#Psychology", "#BrainScience", "#MedicalHistory"],
    "bci_ethics": ["#Neuroethics", "#BCI", "#BrainScience", "#FutureOfMind"],
    "brain_basics": ["#Neuroscience", "#BrainAnatomy", "#Psychology", "#Science"],
    "bci_medicine": ["#Neurotechnology", "#MedicalScience", "#BrainComputerInterface", "#Neurology"],
    "cognitive_psychology": ["#Psychology", "#HumanBehavior", "#BrainScience", "#Neuroscience"],
    "everyday_brain": ["#EverydayScience", "#BrainFacts", "#Psychology", "#Neuroscience"],
}


def build_editorial_description_from_dossier(
    project_id: str,
    pillar: str,
    slug: str,
    script_doc: dict[str, Any],
) -> tuple[str, list[str], str]:
    """
    Generates an independent 3-paragraph academic editorial description from research dossier files
    (never copy-pasting `script_doc['sentences'][:4]`, satisfying YPP Anti-Clone `[US-06]` & `R9`).
    Returns `(description, hashtags, primary_doi)`.
    """
    d_dir = rd.dossier_dir(slug)
    sources_doc = json.loads((d_dir / "01_sources.json").read_text(encoding="utf-8")) if (d_dir / "01_sources.json").exists() else {}
    facts_doc = json.loads((d_dir / "02_facts.json").read_text(encoding="utf-8")) if (d_dir / "02_facts.json").exists() else {}
    brain_path = (d_dir / "06_brain_link.json") if (d_dir / "06_brain_link.json").exists() else (d_dir / "06_brain_links.json")
    brain_doc = json.loads(brain_path.read_text(encoding="utf-8")) if brain_path.exists() else {}
    dossier_meta = json.loads((d_dir / "dossier.json").read_text(encoding="utf-8")) if (d_dir / "dossier.json").exists() else {}

    src_list = (
        (sources_doc.get("primary_sources") or sources_doc.get("sources") or [])
        if isinstance(sources_doc, dict)
        else (sources_doc if isinstance(sources_doc, list) else [])
    )
    primary = src_list[0] if (src_list and isinstance(src_list[0], dict)) else {}
    doi = str(script_doc.get("doi") or primary.get("doi") or "").strip()

    def _strip_md(val: str) -> str:
        cleaned = re.sub(r"\*\*([^*]+)\*\*", r"\1", str(val or ""))
        cleaned = re.sub(r"\*([^*]+)\*", r"\1", cleaned)
        return " ".join(cleaned.split()).strip()

    def _fmt_authors(raw_auth: Any, fallback: str = "") -> str:
        if isinstance(raw_auth, (list, tuple)):
            joined = ", ".join(str(a).strip() for a in raw_auth if str(a).strip())
            return _strip_md(joined) or fallback
        s_auth = _strip_md(str(raw_auth or ""))
        if s_auth.startswith("[") and s_auth.endswith("]"):
            s_auth = s_auth.strip("[]").replace("'", "").replace('"', "").strip()
        return s_auth or fallback

    citation_lines: list[str] = []
    for s in src_list[:3]:
        if not isinstance(s, dict):
            continue
        sdoi = str(s.get("doi") or "").strip()
        url_tail = f" https://doi.org/{sdoi}" if sdoi else ""
        raw_cit = _strip_md(str(s.get("citation") or ""))
        if raw_cit:
            cit_body = raw_cit.rstrip(".")
            if sdoi and sdoi in cit_body:
                citation_lines.append(f"- {cit_body}.")
            else:
                citation_lines.append(f"- {cit_body}.{url_tail}".strip())
        else:
            authors = _fmt_authors(s.get("authors"), "Peer-reviewed study")
            year = str(s.get("year") or "").strip()
            stitle = _strip_md(str(s.get("title") or "")).rstrip(".")
            journal = _strip_md(str(s.get("journal") or s.get("venue") or "")).rstrip(".")
            yr_part = f" ({year})" if year else ""
            parts = [p for p in (f"{authors}{yr_part}", stitle, journal) if p]
            citation_lines.append(f"- {'. '.join(parts)}.{url_tail}".strip())

    topic_label = _strip_md(str(dossier_meta.get("topic") or dossier_meta.get("title") or slug.replace("_", " ").title()))
    pc = dossier_meta.get("primary_case") if isinstance(dossier_meta.get("primary_case"), dict) else {}
    pc_people = [str(p.get("name")).strip() for p in (pc.get("people") or []) if isinstance(p, dict) and str(p.get("name") or "").strip()]
    raw_primary_cit = _strip_md(str(primary.get("citation") or ""))
    cit_author = raw_primary_cit.split("(")[0].strip().rstrip(",") if "(" in raw_primary_cit else ""
    primary_auth_str = _fmt_authors(primary.get("authors"), "")
    p_author = (
        primary_auth_str.split(",")[0].split(";")[0].strip()
        or cit_author
        or (pc_people[0] if pc_people else "researchers")
    )
    p_year = str(primary.get("year") or pc.get("year") or "").strip()
    cit_journal = ""
    if raw_primary_cit:
        cit_parts = [seg.strip() for seg in raw_primary_cit.rstrip(".").split(".") if seg.strip()]
        if len(cit_parts) >= 3:
            cit_journal = cit_parts[-1]
    p_journal = _strip_md(str(primary.get("journal") or primary.get("venue") or cit_journal or pc.get("place") or "peer-reviewed neuroscience literature"))

    fact_items = list(dossier_meta.get("core_facts") or []) + list(facts_doc.get("facts") or [])
    lead_claim = ""
    second_claim = ""
    for f_item in fact_items:
        if isinstance(f_item, dict):
            cl = _strip_md(str(f_item.get("fact") or f_item.get("claim") or f_item.get("plain_claim") or f_item.get("summary") or "")).rstrip(".")
            if cl and not lead_claim:
                lead_claim = cl
            elif cl and cl != lead_claim and not second_claim:
                second_claim = cl
                break

    regions = brain_doc.get("links") or brain_doc.get("regions") or []
    region_names: list[str] = []
    for reg in regions[:3]:
        if isinstance(reg, dict):
            rn = _strip_md(str(reg.get("region") or reg.get("canonical_region") or reg.get("name") or ""))
            if rn and rn not in region_names:
                region_names.append(rn)

    year_clause = f" ({p_year})" if p_year else ""
    para_1 = (
        f"Documentary case briefing on {topic_label}, grounded in {p_author}{year_clause} ({p_journal})."
        + (f" Empirical findings show that {lead_claim[0].lower() + lead_claim[1:] if len(lead_claim) > 1 and lead_claim[:2].isalpha() and not lead_claim[:2].isupper() else lead_claim}." if lead_claim else "")
    )
    if region_names:
        para_2 = (
            f"At the circuit level, this episode examines how {', '.join(region_names)} coordinate behavioral and neural responses"
            + (f", alongside evidence that {second_claim[0].lower() + second_claim[1:] if len(second_claim) > 1 and second_claim[:2].isalpha() and not second_claim[:2].isupper() else second_claim}." if second_claim else ".")
        )
    elif second_claim:
        para_2 = f"Follow-up physiological and behavioral evidence demonstrates: {second_claim}."
    else:
        para_2 = (
            "This visual breakdown traces the experimental protocol, measurable behavioral markers, and neural mechanisms documented across controlled laboratory trials."
        )

    from pipeline.config import (
        EXPRESSIVE_25D_V8_STYLE_PROFILE,
        PRE_R68H_FROZEN_V8_PROJECTS,
        SHORTS_EXPRESSIVE_V8_PROFILE,
        is_expressive_v8_plan,
    )
    from pipeline.publish import (
        _scrub_experiment_nicknames,
        build_expressive_v8_pinned_comment,
        format_v8_viewer_story_description,
    )

    is_v8_desc = is_expressive_v8_plan(script_doc)
    is_frozen_v8 = bool(is_v8_desc and str(project_id or "") in PRE_R68H_FROZEN_V8_PROJECTS)
    omit_nicks = [
        str(x).strip()
        for x in (script_doc.get("omit_experiment_nicknames") or [])
        if str(x).strip()
    ]
    if is_v8_desc and not is_frozen_v8:
        r68d_desc = format_v8_viewer_story_description(
            script_doc,
            dossier=d_dir,
            omit_nicknames=omit_nicks,
        )
        if not r68d_desc.lower().rstrip().endswith("#shorts"):
            r68d_desc = f"{r68d_desc.rstrip()}\n\n#shorts"
        return r68d_desc, ["#shorts"], doi

    if is_v8_desc and omit_nicks:
        para_1 = _scrub_experiment_nicknames(para_1, omit_nicks)
        para_2 = _scrub_experiment_nicknames(para_2, omit_nicks)

    if is_v8_desc:
        hashtags = ["#shorts"]
    else:
        slug_words = [w.capitalize() for w in slug.split("_") if len(w) >= 4 and w.lower() not in ("with", "from", "into", "that")]
        custom_tag = f"#{''.join(slug_words[:2])}" if slug_words else "#BrainResearch"
        pillar_tags = _PILLAR_TOPIC_HASHTAG_MAP.get(pillar, ["#Neuroscience", "#Psychology", "#BrainScience"])
        hashtags = list(dict.fromkeys(["#Shorts", custom_tag, *pillar_tags]))[:5]

    sources_block = (
        "Primary Peer-Reviewed Sources:\n" + "\n".join(citation_lines) + "\n\n"
        if citation_lines
        else (f"Primary Peer-Reviewed Source: https://doi.org/{doi}\n\n" if doi else "")
    )
    ai_disc_line = f"AI Disclosure: {AI_DISCLOSURE_SENTENCE}"
    desc = (
        f"{para_1}\n\n"
        f"{para_2}\n\n"
        f"{sources_block}"
        f"{ai_disc_line}"
        + (f"\n\n{' '.join(hashtags)}" if hashtags else "")
    )
    if is_v8_desc:
        desc_body = re.sub(r"#\w+", "", desc).strip()
        desc = f"{desc_body}\n\n#shorts"
    return desc, hashtags, doi


def _default_metadata_from_script_and_dossier(
    project_id: str,
    pillar: str,
    slug: str,
    script_doc: dict[str, Any],
) -> dict[str, Any]:
    from pipeline.config import (
        EXPRESSIVE_25D_V8_STYLE_PROFILE,
        PRE_R68H_FROZEN_V8_PROJECTS,
        SHORTS_EXPRESSIVE_V8_PROFILE,
        is_expressive_v8_plan,
    )
    from pipeline.publish import (
        build_clean_episode_tags,
        build_expressive_v8_pinned_comment,
    )
    from pipeline.studio.config import DEFAULT_VIDEO_CATEGORY

    desc, hashtags, doi = build_editorial_description_from_dossier(project_id, pillar, slug, script_doc)
    clean_tags = build_clean_episode_tags(
        pillar=pillar,
        script_doc=script_doc,
        dossier=slug,
        title=str(script_doc.get("title") or ""),
        everyday_domain=str(script_doc.get("everyday_domain") or ""),
    )
    meta_out: dict[str, Any] = {
        "project_id": project_id,
        "profile": "neuro_diorama",
        "pillar": pillar,
        "dossier_slug": slug,
        "category": DEFAULT_VIDEO_CATEGORY,
        "language": "en-US",
        "video_language": "en-US",
        "title_description_language": "en-US",
        "channel_residence_country": "KR",
        "title": str(script_doc.get("title") or ""),
        "doi": doi,
        "ai_disclosure": True,
        "ai_content_declaration": True,
        "tags": clean_tags,
        "hashtags": hashtags,
        "description": desc,
    }
    if is_expressive_v8_plan(script_doc):
        is_frozen_v8 = str(project_id or "") in PRE_R68H_FROZEN_V8_PROJECTS
        meta_out["style_profile"] = EXPRESSIVE_25D_V8_STYLE_PROFILE
        meta_out["shorts_format_profile"] = SHORTS_EXPRESSIVE_V8_PROFILE
        if is_frozen_v8:
            meta_out["pinned_comment"] = build_expressive_v8_pinned_comment(
                doi=doi,
                debate_question=str(script_doc.get("debate_question") or ""),
                cameo_prompt=str(script_doc.get("cameo_prompt") or "Did you spot the 4cm Mini-Cortex hiding in the room?"),
                include_doi=True,
            )
        else:
            meta_out["pinned_comment"] = build_expressive_v8_pinned_comment(
                doi=doi,
                debate_question=str(script_doc.get("debate_question") or ""),
                cameo_prompt=(
                    str(script_doc.get("cameo_prompt") or "")
                    if script_doc.get("include_cameo_in_pinned_comment")
                    else ""
                ),
                include_doi=False,
            )
    return meta_out


def sync_project_from_dossier_diorama(
    spec: dict[str, Any],
    *,
    write_back_dossier: bool = True,
    projects_dir: Path | None = None,
) -> Path:
    """Materializes/updates `projects/<project_id>/` from `research_dossiers/<slug>/diorama_v8_expressive/` or `diorama_v7*/` (with v6 fallback)."""
    from pipeline.config import (
        DEFAULT_DIORAMA_STYLE_PROFILE,
        DIORAMA_V7_STYLE_PROFILE,
        EXPRESSIVE_25D_V8_STYLE_PROFILE,
        EXPRESSIVE_V8_PROSODY_MODE,
        PORCELAIN_V7_STYLE_PROFILE,
        PROMPT_SCHEMA_VERSION_V7,
        PROMPT_SCHEMA_VERSION_V8,
        SHORTS_EXPRESSIVE_V8_PROFILE,
        is_diorama_v7_plan,
        is_expressive_v8_plan,
        resolve_diorama_v7_style_profile,
    )
    from pipeline.flow_prompt_builder import build_flow_prompts

    project_id = str(spec["project_id"])
    slug = str(spec["slug"])
    pillar = str(spec["pillar"])
    d_root = rd.dossier_dir(slug)
    explicit_subdir = str(spec.get("draft_subdir") or "").strip()
    cand_names: list[str] = []
    if explicit_subdir:
        cand_names.append(explicit_subdir)
    else:
        cand_names.extend(
            ("diorama_v8_expressive", "diorama_v7_porcelain", "diorama_v7", "diorama_v7_lowpoly", "diorama_v6_dynamic")
        )

    def _is_authored_draft(folder: Path) -> bool:
        try:
            sc_raw = json.loads((folder / "script.json").read_text(encoding="utf-8"))
            vp_raw = json.loads((folder / "visual_plan.json").read_text(encoding="utf-8"))
        except Exception:
            return False
        has_script = bool(
            (isinstance(sc_raw, dict) and (sc_raw.get("sentences") or sc_raw.get("acts") or sc_raw.get("clip_narrations")))
        )
        has_clips = bool(isinstance(vp_raw, dict) and (vp_raw.get("clips") or vp_raw.get("shots")))
        return has_script or has_clips

    existing_cands: list[Path] = []
    for cname in cand_names:
        cand = d_root / cname
        if (cand / "script.json").exists() and (cand / "visual_plan.json").exists():
            existing_cands.append(cand)
    draft_dir: Path | None = None
    if explicit_subdir and existing_cands:
        draft_dir = existing_cands[0]
    elif existing_cands:
        draft_dir = next((c for c in existing_cands if _is_authored_draft(c)), existing_cands[0])
    if draft_dir is None:
        raise FileNotFoundError(
            f"Missing diorama_v8_expressive / diorama_v7_porcelain / diorama_v7 / diorama_v7_lowpoly / diorama_v6_dynamic draft under {d_root}"
        )

    script_doc = json.loads((draft_dir / "script.json").read_text(encoding="utf-8"))
    visual_plan = json.loads((draft_dir / "visual_plan.json").read_text(encoding="utf-8"))
    is_v8 = (
        is_expressive_v8_plan(visual_plan, script_doc)
        or draft_dir.name == "diorama_v8_expressive"
    )
    is_v7 = (
        is_v8
        or is_diorama_v7_plan(visual_plan)
        or is_diorama_v7_plan(script_doc)
        or draft_dir.name in ("diorama_v7_porcelain", "diorama_v7", "diorama_v7_lowpoly")
    )
    if is_v8:
        fallback_style = EXPRESSIVE_25D_V8_STYLE_PROFILE
    elif draft_dir.name == "diorama_v7_porcelain":
        fallback_style = PORCELAIN_V7_STYLE_PROFILE
    elif draft_dir.name == "diorama_v7":
        fallback_style = DEFAULT_DIORAMA_STYLE_PROFILE
    else:
        fallback_style = DIORAMA_V7_STYLE_PROFILE
    resolved_v7_style = (
        EXPRESSIVE_25D_V8_STYLE_PROFILE
        if is_v8
        else resolve_diorama_v7_style_profile(
            visual_plan,
            script_doc,
            fallback=fallback_style,
        )
    )
    if isinstance(script_doc.get("acts"), list) and not script_doc.get("sentences"):
        script_doc["sentences"] = [
            str(s).strip()
            for act in script_doc["acts"]
            for s in (act.get("sentences") or [])
            if str(s).strip()
        ]
    script_doc["project_id"] = project_id
    script_doc["pillar"] = pillar
    script_doc["dossier"] = slug
    script_doc["profile"] = "neuro_diorama"
    script_doc["language"] = "en-US"
    visual_plan["dossier"] = slug
    visual_plan["profile"] = "neuro_diorama"
    visual_plan["zero_clip_reuse"] = True
    visual_plan["require_signature_hooks"] = True
    if is_v8:
        script_doc["schema"] = PROMPT_SCHEMA_VERSION_V8
        script_doc["schema_version"] = PROMPT_SCHEMA_VERSION_V8
        script_doc["style_profile"] = EXPRESSIVE_25D_V8_STYLE_PROFILE
        script_doc["shorts_format_profile"] = SHORTS_EXPRESSIVE_V8_PROFILE
        visual_plan["schema"] = PROMPT_SCHEMA_VERSION_V8
        visual_plan["schema_version"] = PROMPT_SCHEMA_VERSION_V8
        visual_plan["style_profile"] = EXPRESSIVE_25D_V8_STYLE_PROFILE
        visual_plan["shorts_format_profile"] = SHORTS_EXPRESSIVE_V8_PROFILE
        visual_plan["camera_profile"] = str(visual_plan.get("camera_profile") or "expressive_dynamic_v8")
    elif is_v7:
        script_doc["schema"] = PROMPT_SCHEMA_VERSION_V7
        script_doc["schema_version"] = PROMPT_SCHEMA_VERSION_V7
        script_doc["style_profile"] = resolved_v7_style
        visual_plan["schema"] = PROMPT_SCHEMA_VERSION_V7
        visual_plan["schema_version"] = PROMPT_SCHEMA_VERSION_V7
        visual_plan["style_profile"] = resolved_v7_style
        visual_plan["camera_profile"] = str(visual_plan.get("camera_profile") or "orthogonal_tripod_v7")
    else:
        script_doc["schema_version"] = 6
        visual_plan["camera_profile"] = "dynamic_3d_cinema_rig"

    from pipeline.config import (
        DEFAULT_DIORAMA_VOICE_PRESET,
        DIORAMA_V7_US_PROSODY_MODE,
        PRE_R66_FROZEN_PROJECT_PREFIXES,
        is_porcelain_v7_plan,
    )
    from pipeline.voice_fallback import resolve_diorama_voice_preset

    is_frozen_pub = any(project_id.startswith(pref) for pref in PRE_R66_FROZEN_PROJECT_PREFIXES)
    is_porc_v7 = (is_v7 and not is_v8) and resolved_v7_style == PORCELAIN_V7_STYLE_PROFILE
    eff_voice_preset = str(
        spec.get("voice_preset")
        or script_doc.get("voice_preset")
        or visual_plan.get("voice_preset")
        or (DEFAULT_DIORAMA_VOICE_PRESET if ((is_porc_v7 or is_v8) and not is_frozen_pub) else "")
    ).strip() or None
    if eff_voice_preset:
        script_doc["voice_preset"] = eff_voice_preset
        visual_plan["voice_preset"] = eff_voice_preset
    eff_prosody_mode = str(
        spec.get("prosody_mode")
        or script_doc.get("prosody_mode")
        or (EXPRESSIVE_V8_PROSODY_MODE if is_v8 else (DIORAMA_V7_US_PROSODY_MODE if (is_porc_v7 and not is_frozen_pub) else ""))
    ).strip()
    if eff_prosody_mode:
        script_doc["prosody_mode"] = eff_prosody_mode
        visual_plan["prosody_mode"] = eff_prosody_mode
    if (is_porc_v7 or is_v8) and not is_frozen_pub:
        script_doc["us_anti_clone_v7"] = True
        visual_plan["us_anti_clone_v7"] = True
    preset_name, preset_cfg = resolve_diorama_voice_preset(eff_voice_preset, script_doc=script_doc, visual_plan=visual_plan)

    sentences = [str(s).strip() for s in script_doc["sentences"] if str(s).strip()]

    if (is_porcelain_v7_plan(visual_plan) or is_v8) and not visual_plan.get("reference_anchors"):
        from pipeline.porcelain_anchor_pack import populate_porcelain_reference_contract

        populate_porcelain_reference_contract(visual_plan, dossier_dir=d_root)
    clips = build_flow_prompts(visual_plan, sentences)
    eff_schema_ver = PROMPT_SCHEMA_VERSION_V8 if is_v8 else (PROMPT_SCHEMA_VERSION_V7 if is_v7 else 6)

    # Save canonical prompts in draft_dir only when write_back_dossier=True (never during --precheck-only)
    if write_back_dossier:
        (draft_dir / "script.json").write_text(json.dumps(script_doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        (draft_dir / "visual_plan.json").write_text(json.dumps(visual_plan, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        draft_prompts_payload: dict[str, Any] = {
            "schema_version": eff_schema_ver,
            "profile": "neuro_diorama",
            "voice": preset_cfg["voice"],
            "voice_preset": preset_name,
            "visual_mode": visual_plan.get("visual_mode", "NEURO_BIOLOGY"),
            "aspect": "9:16",
            "clips": clips,
            "prompts": [c["prompt"] for c in clips],
        }
        if is_v7:
            draft_prompts_payload["style_profile"] = resolved_v7_style
        draft_prompts_json = json.dumps(draft_prompts_payload, indent=2, ensure_ascii=False) + "\n"
        try:
            (draft_dir / "flow_all_in_one_prompts.json").write_text(draft_prompts_json, encoding="utf-8")
        except OSError:
            (draft_dir / "03_visuals").mkdir(parents=True, exist_ok=True)
            (draft_dir / "03_visuals" / "flow_all_in_one_prompts.json").write_text(draft_prompts_json, encoding="utf-8")

    if projects_dir is not None:
        p_dir = Path(projects_dir) / project_id
        p_dir.mkdir(parents=True, exist_ok=True)
    else:
        storage = ProjectStorage(project_id=project_id, title=str(script_doc.get("title") or project_id), pillar=pillar)
        p_dir = storage.project_dir
    for s_name in STAGE_NAMES:
        (p_dir / s_name).mkdir(parents=True, exist_ok=True)

    dst_script_path = p_dir / "02_script" / "script.json"
    new_script_txt = json.dumps(script_doc, indent=2, ensure_ascii=False) + "\n"
    prev_script_txt = dst_script_path.read_text(encoding="utf-8") if dst_script_path.exists() else None
    if prev_script_txt is not None and prev_script_txt != new_script_txt:
        for stale_rel in ("audio_master.wav", "voice_report.json", "prosody_report.json", "subtitles.ass"):
            (p_dir / "04_audio" / stale_rel).unlink(missing_ok=True)
    dst_script_path.write_text(new_script_txt, encoding="utf-8")
    (p_dir / "03_visuals" / "visual_plan.json").write_text(
        json.dumps(visual_plan, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    write_flow_prompts_json(p_dir, clips)

    if is_porcelain_v7_plan(visual_plan) or is_v8:
        from pipeline.reference_image_qa import build_reference_image_specs, write_reference_image_specs

        dst_specs = p_dir / "03_visuals" / "reference_image_specs.json"
        preserve_dst_specs = False
        if dst_specs.exists():
            try:
                ex_doc = json.loads(dst_specs.read_text(encoding="utf-8"))
                ex_specs = ex_doc.get("all_specs") or ex_doc.get("specs") or []
                ref_dir = p_dir / "03_visuals" / "reference_images"
                preserve_dst_specs = bool(ex_specs) and all(
                    (ref_dir / str(s.get("filename") or "")).exists() for s in ex_specs if isinstance(s, dict)
                )
            except Exception:
                preserve_dst_specs = False
        if not preserve_dst_specs:
            src_specs = draft_dir / "reference_image_specs.json"
            if src_specs.exists():
                dst_specs.write_text(src_specs.read_text(encoding="utf-8"), encoding="utf-8")
            else:
                built_specs = build_reference_image_specs(visual_plan, sentences)
                write_reference_image_specs(p_dir, built_specs)
                if write_back_dossier:
                    (draft_dir / "reference_image_specs.json").write_text(
                        dst_specs.read_text(encoding="utf-8"), encoding="utf-8"
                    )
        d_edl = d_root / "08_reenactment_edl.json"
        dst_edl = p_dir / "03_visuals" / "source_edl.json"
        if not is_v8 or str(visual_plan.get("reenactment_track") or "") == "track_a":
            if d_edl.exists() and not dst_edl.exists():
                dst_edl.write_text(d_edl.read_text(encoding="utf-8"), encoding="utf-8")
        elif dst_edl.exists():
            dst_edl.unlink(missing_ok=True)

    meta_src = draft_dir / "metadata.json"
    if meta_src.exists():
        meta_doc = json.loads(meta_src.read_text(encoding="utf-8"))
        meta_doc["project_id"] = project_id
        meta_doc["pillar"] = pillar
        meta_doc["title"] = str(script_doc.get("title") or meta_doc.get("title") or "")
        meta_doc.setdefault("video_language", "en-US")
        meta_doc.setdefault("title_description_language", "en-US")
        meta_doc.setdefault("channel_residence_country", "KR")
        if is_v8:
            meta_doc["hashtags"] = []
            meta_doc["style_profile"] = EXPRESSIVE_25D_V8_STYLE_PROFILE
            meta_doc["shorts_format_profile"] = SHORTS_EXPRESSIVE_V8_PROFILE
            meta_doc["description"] = re.sub(r"#\w+", "", str(meta_doc.get("description") or "")).strip()
    else:
        meta_doc = _default_metadata_from_script_and_dossier(project_id, pillar, slug, script_doc)
    if not str(meta_doc.get("offcenter_creator_bet") or "").strip():
        d_meta_path = d_root / "dossier.json"
        if d_meta_path.exists():
            try:
                d_meta_doc = json.loads(d_meta_path.read_text(encoding="utf-8"))
                if str(d_meta_doc.get("offcenter_creator_bet") or "").strip():
                    meta_doc["offcenter_creator_bet"] = str(d_meta_doc["offcenter_creator_bet"]).strip()
            except Exception as exc:
                import logging

                logging.getLogger("diorama_batch_orchestrator").warning(
                    "Failed reading dossier.json offcenter_creator_bet for %s: %s", slug, exc
                )
    from pipeline.publish import build_clean_episode_tags, validate_episode_tags_hygiene
    from pipeline.studio.config import DEFAULT_VIDEO_CATEGORY

    if is_v8:
        from pipeline.config import PRE_R68H_FROZEN_V8_PROJECTS
        from pipeline.publish import build_expressive_v8_pinned_comment as _build_v8_pin

        is_frozen_v8 = str(project_id or "") in PRE_R68H_FROZEN_V8_PROJECTS
        fresh_desc, fresh_tags, fresh_doi = build_editorial_description_from_dossier(project_id, pillar, slug, script_doc)
        meta_doc["description"] = fresh_desc
        meta_doc["hashtags"] = fresh_tags
        meta_doc["ai_disclosure"] = True
        meta_doc["ai_content_declaration"] = True
        if fresh_doi and not meta_doc.get("doi"):
            meta_doc["doi"] = fresh_doi
        if is_frozen_v8:
            if not str(meta_doc.get("pinned_comment") or "").strip():
                meta_doc["pinned_comment"] = _build_v8_pin(
                    doi=str(meta_doc.get("doi") or ""),
                    debate_question=str(script_doc.get("debate_question") or ""),
                    cameo_prompt=str(script_doc.get("cameo_prompt") or "Did you spot the 4cm Mini-Cortex hiding in the room?"),
                    include_doi=True,
                )
        else:
            meta_doc["pinned_comment"] = _build_v8_pin(
                doi=str(meta_doc.get("doi") or ""),
                debate_question=str(script_doc.get("debate_question") or ""),
                cameo_prompt=(
                    str(script_doc.get("cameo_prompt") or "")
                    if script_doc.get("include_cameo_in_pinned_comment")
                    else ""
                ),
                include_doi=False,
            )

    meta_doc["category"] = str(meta_doc.get("category") or DEFAULT_VIDEO_CATEGORY)
    existing_tags = meta_doc.get("tags")
    if isinstance(existing_tags, list) and not validate_episode_tags_hygiene(existing_tags, pillar=pillar, raise_on_error=False):
        meta_doc["tags"] = validate_episode_tags_hygiene(existing_tags, pillar=pillar, raise_on_error=True)
    else:
        meta_doc["tags"] = build_clean_episode_tags(
            pillar=pillar,
            script_doc=script_doc,
            dossier=d_root,
            title=str(meta_doc.get("title") or script_doc.get("title") or ""),
            everyday_domain=str(meta_doc.get("everyday_domain") or script_doc.get("everyday_domain") or ""),
            extra_tags=existing_tags if isinstance(existing_tags, list) else None,
        )
    if write_back_dossier:
        meta_src.write_text(json.dumps(meta_doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (p_dir / "06_publish" / "metadata.json").write_text(
        json.dumps(meta_doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    if str(meta_doc.get("pinned_comment") or "").strip():
        (p_dir / "06_publish" / "pinned_comment.txt").write_text(
            str(meta_doc["pinned_comment"]).strip() + "\n", encoding="utf-8"
        )

    # Ensure manifest carries profile/doi/camera_profile metadata
    m_path = p_dir / "00_project_manifest.json"
    m_doc = json.loads(m_path.read_text(encoding="utf-8")) if m_path.exists() else {}
    m_doc["project_id"] = project_id
    m_doc["title"] = str(script_doc.get("title") or project_id)
    m_doc["pillar"] = pillar
    m_doc["dossier_slug"] = slug
    m_doc["profile"] = "neuro_diorama"
    m_doc["schema_version"] = eff_schema_ver
    if is_v7:
        m_doc["style_profile"] = resolved_v7_style
    if is_v8:
        m_doc["shorts_format_profile"] = SHORTS_EXPRESSIVE_V8_PROFILE
    m_doc["voice_preset"] = preset_name
    m_doc["camera_profile"] = visual_plan["camera_profile"]
    m_doc["doi"] = str(script_doc.get("doi") or meta_doc.get("doi") or "")
    m_path.write_text(json.dumps(m_doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    ProjectStorage.sync_existing_manifest_from_disk(p_dir)

    # Link project_id into dossier.json only when write_back_dossier=True (never during --precheck-only)
    d_json_path = rd.dossier_dir(slug) / "dossier.json"
    if write_back_dossier and d_json_path.exists():
        ddoc = json.loads(d_json_path.read_text(encoding="utf-8"))
        sp = list(ddoc.get("shorts_projects") or [])
        if project_id not in sp:
            sp.append(project_id)
            ddoc["shorts_projects"] = sp
            d_json_path.write_text(json.dumps(ddoc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    return p_dir


def _plan_lock_mapping_issues(
    visual_plan: dict[str, Any],
    contract: dict[str, Any],
    rendered_clips: list[dict[str, Any]] | None = None,
) -> list[str]:
    """
    Pre-Flow check mirroring post-assembly `DQ1` (literal analogy primary cut sync) and `DQ3`
    (anatomy mention -> primary brain-grammar cut sync) directly on `visual_plan` spans in <2s.
    """
    from pipeline.config import is_expressive_v8_plan

    issues: list[str] = []
    plan_clips = visual_plan.get("clips") if isinstance(visual_plan.get("clips"), list) else []
    if not plan_clips:
        return issues

    is_v8 = is_expressive_v8_plan(visual_plan)
    n_clips = len(plan_clips)
    reserved_0based: set[int] = set()
    if not is_v8:
        outro_idx = n_clips - 1
        for idx, spec in enumerate(plan_clips):
            if isinstance(spec, dict) and str(spec.get("cut_role") or "").strip().lower() == "outro":
                outro_idx = idx
                break
        reserved_0based.add(outro_idx)
    for sc in (visual_plan.get("split_comparisons") or []):
        if isinstance(sc, dict):
            sec_1 = int(sc.get("right_clip_index") or sc.get("bottom_clip_index") or 0)
            if 1 <= sec_1 <= n_clips:
                reserved_0based.add(sec_1 - 1)
    for idx, spec in enumerate(plan_clips):
        if isinstance(spec, dict) and str(spec.get("cut_role") or "").strip().lower() in ("outro", "split_right", "split_bottom"):
            reserved_0based.add(idx)

    primary_by_sent: dict[int, list[tuple[int, dict[str, Any]]]] = {}
    for idx, spec in enumerate(plan_clips):
        if idx in reserved_0based or not isinstance(spec, dict):
            continue
        s0 = spec.get("sentence_index")
        if isinstance(s0, int) and s0 >= 1:
            s1 = max(s0, int(spec.get("end_sentence_index") or s0))
            for s_k in range(s0, s1 + 1):
                primary_by_sent.setdefault(s_k, []).append((idx + 1, spec))

    rendered_by_num = {
        int(c.get("clip_number") or (i + 1)): c
        for i, c in enumerate(rendered_clips or [])
        if isinstance(c, dict)
    }

    brain_grammars = {
        "arch_brain_maquette",
        "frosted_crystal_specimen",
        "lowpoly_matte_brain",
        "porcelain_living_brain",
        "expressive_xray_brain",
        "brain_simulator_3d",
        "living_brain",
        "matte_brain",
    }
    for an_lock in contract.get("anatomy_locks") or []:
        s_idx = int(an_lock["sentence_index"])
        p_clips = primary_by_sent.get(s_idx, [])
        if not any(str(spec.get("grammar") or "") in brain_grammars for _, spec in p_clips):
            found_g = [spec.get("grammar") for _, spec in p_clips]
            issues.append(
                f"[plan_lock:DQ3_anatomy_to_brain_sync] sentence {s_idx} ({an_lock['anatomy_terms']}) "
                f"is not mapped to any primary brain-grammar cut in visual_plan (found={found_g})"
            )

    for a_lock in contract.get("analogy_locks") or []:
        s_idx = int(a_lock["sentence_index"])
        p_clips = primary_by_sent.get(s_idx, [])
        if not p_clips:
            issues.append(
                f"[plan_lock:DQ1_literal_analogy_frame_sync] sentence {s_idx} ('{a_lock['spoken_phrase']}') "
                "has no primary EDL cut in visual_plan"
            )
            continue
        if rendered_by_num:
            p_nums = [c_no for c_no, _ in p_clips]
            combined_scene = " ".join(
                str(rendered_by_num[c_no].get("scene") or "").lower()
                for c_no in p_nums
                if c_no in rendered_by_num
            )
            for bad_abs in a_lock.get("forbidden_abstract") or []:
                if bad_abs.lower() in combined_scene:
                    issues.append(
                        f"[plan_lock:DQ1_literal_analogy_frame_sync] sentence {s_idx} ('{a_lock['spoken_phrase']}') "
                        f"uses forbidden abstract substitute '{bad_abs}' on primary clip(s) {p_nums}"
                    )
            req_nouns = a_lock.get("required_any_nouns") or []
            if req_nouns and not any(req.lower() in combined_scene for req in req_nouns):
                issues.append(
                    f"[plan_lock:DQ1_literal_analogy_frame_sync] sentence {s_idx} ('{a_lock['spoken_phrase']}') "
                    f"primary clip(s) {p_nums} never depict any of {req_nouns}"
                )

    return issues


def precheck_diorama_project(
    spec: dict[str, Any],
    run_tts_clock: bool = True,
    voice_preset: str | None = None,
    prosody_mode: str | None = None,
    *,
    materialize_project: bool = False,
    allow_live_tts: bool = False,
) -> dict[str, Any]:
    """Validates `prompt-gate`, contract lock mapping (DQ1/DQ3), paradox/R68 title, zero-plaque nouns, and pre-Flow TTS + Prosody P1-P6/P8/P10 without mutating `research_dossiers/` or `projects/` unless `materialize_project=True`."""
    import contextlib
    import os
    import tempfile

    from pipeline.config import (
        DIORAMA_V7_DURATION_MIN_SEC,
        FROZEN_PRE_SCHEMA_V2_DOSSIER_SLUGS,
        FROZEN_PRE_SCHEMA_V2_PROJECT_PREFIXES,
        MICRO_SHORT_PROFILE,
        SHORTS_90S_PROFILE,
        SHORTS_EXPRESSIVE_V8_PROFILE,
        is_diorama_v7_plan,
        is_expressive_v8_plan,
        resolve_shorts_format_profile,
        shorts_duration_range_for_profile,
    )
    from pipeline.dynamic_episode_qa import compile_episode_qa_contract
    from pipeline.flow_prompt_builder import build_flow_prompts, validate_flow_credit_safety_lint
    from pipeline.prosody import evaluate_prosody_gates_on_audio
    from pipeline.voice_fallback import _write_mono_wav, resolve_diorama_voice_preset

    eff_spec = dict(spec)
    if voice_preset:
        eff_spec["voice_preset"] = voice_preset
    if prosody_mode:
        eff_spec["prosody_mode"] = prosody_mode
    with contextlib.ExitStack() as stack:
        scratch_projects_dir: Path | None = None
        if not materialize_project:
            scratch_projects_dir = Path(stack.enter_context(tempfile.TemporaryDirectory(prefix="aab_precheck_")))
        p_dir = sync_project_from_dossier_diorama(
            eff_spec,
            write_back_dossier=False,
            projects_dir=scratch_projects_dir,
        )
        slug = str(spec["slug"])
        proj_id = str(spec["project_id"])
        sentences, script_doc = load_diorama_script_sentences(p_dir)
        visual_plan = json.loads((p_dir / "03_visuals" / "visual_plan.json").read_text(encoding="utf-8"))
        is_v8 = is_expressive_v8_plan(visual_plan, script_doc)
        is_v7 = is_v8 or is_diorama_v7_plan(visual_plan) or is_diorama_v7_plan(script_doc)
        clips = build_flow_prompts(visual_plan, sentences)

        issues: list[str] = []
        is_frozen_v1 = (
            slug in FROZEN_PRE_SCHEMA_V2_DOSSIER_SLUGS
            or any(proj_id.startswith(pref) for pref in FROZEN_PRE_SCHEMA_V2_PROJECT_PREFIXES)
        )
        if bool(spec.get("require_schema_v2", not is_frozen_v1)):
            d_val = rd.validate_dossier(slug, require_schema_v2=True)
            if not d_val.get("ready"):
                issues.extend([f"[dossier_v2] {iss}" for iss in (d_val.get("issues") or [])])
        issues.extend(validate_production_diorama_v6(visual_plan, sentences, clips, script_doc=script_doc))
        issues.extend(validate_flow_credit_safety_lint(visual_plan, clips))
        issues.extend(rd.check_narration_facts(slug, sentences))
        issues.extend(validate_diorama_paradox_title(str(script_doc.get("title") or ""), is_expressive_v8=is_v8))
        contract = compile_episode_qa_contract(visual_plan, sentences, clips, script_doc=script_doc)
        issues.extend(_plan_lock_mapping_issues(visual_plan, contract, rendered_clips=clips))

        # Positive scene scan for empirical plaque-trigger nouns (excluding negated clauses and allowlisted diegetic tokens)
        for c in clips:
            sc = re.sub(r"\b(?:without|zero|no)\s+[a-z\s,-]{1,35}", " ", str(c.get("scene") or ""), flags=re.IGNORECASE)
            for allow_tok in (c.get("diegetic_text_allowlist") or []):
                if str(allow_tok or "").strip():
                    sc = re.sub(re.escape(str(allow_tok).strip()), " ", sc, flags=re.IGNORECASE)
            hits = sorted({m.group(0).lower() for m in _PLAQUE_TRIGGER_NOUNS_RE.finditer(sc)})
            if hits:
                issues.append(f"[plaque_lock] clip {c['clip_number']} positive scene contains plaque-trigger word(s) {hits}")

        tts_duration = None
        preflight_prosody: dict[str, Any] | None = None
        fmt_profile = resolve_shorts_format_profile(
            visual_plan,
            script_doc,
            {"sentences": sentences, "clips": clips},
            slug=slug,
            project_id=str(spec.get("project_id") or p_dir.name),
        )
        is_micro = fmt_profile == MICRO_SHORT_PROFILE
        if fmt_profile in (MICRO_SHORT_PROFILE, SHORTS_90S_PROFILE, SHORTS_EXPRESSIVE_V8_PROFILE):
            min_dur, max_dur = shorts_duration_range_for_profile(
                fmt_profile,
                project_id=str(spec.get("project_id") or p_dir.name),
            )
        else:
            min_dur = DIORAMA_V7_DURATION_MIN_SEC if is_v7 else DIORAMA_DURATION_MIN_SEC
            max_dur = SHORTS_HARD_CEILING_SEC
        eff_vp = voice_preset or str(spec.get("voice_preset") or script_doc.get("voice_preset") or visual_plan.get("voice_preset") or "").strip() or None
        eff_pm = prosody_mode or str(spec.get("prosody_mode") or script_doc.get("prosody_mode") or "").strip() or None
        preset_name, preset_cfg = resolve_diorama_voice_preset(eff_vp, script_doc=script_doc, visual_plan=visual_plan)
        if run_tts_clock and not issues:
            from pipeline.elevenlabs_tts import is_episode_fully_cached
            from pipeline.prosody import plan_sentence_prosody, resolve_prosody_mode

            resolved_pm = resolve_prosody_mode(eff_pm, script_doc, is_v7)
            gears_pre = (
                [str(pl["gear"]) for pl in plan_sentence_prosody(sentences, script_doc, resolved_pm)]
                if resolved_pm != "uniform_108x"
                else None
            )
            ep_cached = is_episode_fully_cached(
                sentences,
                voice_id=str(preset_cfg.get("elevenlabs_voice_id") or preset_cfg.get("voice")),
                gears=gears_pre,
                preserve_exclamation=bool(is_v8),
            )
            use_stub = (not bool(allow_live_tts or spec.get("_allow_live_tts"))) and (not ep_cached)
            tts_res = synthesize_continuous_diorama_track(
                project_dir=p_dir,
                sentences=sentences,
                align_whisper=(not use_stub),
                prosody_mode=eff_pm,
                script_doc=script_doc,
                voice_preset=preset_name,
                allow_test_stub=use_stub,
            )
            tts_duration = round(float(tts_res["total_duration_sec"]), 2)
            if not (min_dur <= tts_duration <= max_dur):
                issues.append(
                    f"[tts_clock] synthesized {preset_cfg['voice']} ({preset_name}) "
                    f"total_duration_sec={tts_duration}s outside {min_dur}..{max_dur}s"
                )
            if is_v7 and not is_micro and (p_dir / "04_audio" / "prosody_report.json").exists() and "pcm" in tts_res:
                tmp_wav = Path(tempfile.gettempdir()) / f"aab_preflight_voice_{spec['project_id']}_{os.getpid()}.wav"
                try:
                    _write_mono_wav(tmp_wav, tts_res["pcm"], int(tts_res.get("sr") or 48000))
                    pros_gates = ("P1", "P2", "P3", "P4", "P5", "P8", "P10") if use_stub else ("P1", "P2", "P3", "P4", "P5", "P6", "P8", "P10")
                    preflight_prosody = evaluate_prosody_gates_on_audio(
                        p_dir,
                        audio_path=tmp_wav,
                        gates=pros_gates,
                        run_asr=(not use_stub),
                    )
                    for g_name, g_val in (preflight_prosody.get("gates") or {}).items():
                        if not g_val.get("passed"):
                            issues.append(f"[preflight_prosody:{g_name}] {g_val}")
                finally:
                    tmp_wav.unlink(missing_ok=True)

        return {
            "project_id": spec["project_id"],
            "slug": slug,
            "wave": spec["wave"],
            "schema_version": 8 if is_v8 else (7 if is_v7 else 6),
            "voice_preset": preset_name,
            "prosody_mode": eff_pm or script_doc.get("prosody_mode"),
            "passed": len(issues) == 0,
            "sentences": len(sentences),
            "clips": len(clips),
            "words": sum(len(s.split()) for s in sentences),
            "tts_duration_sec": tts_duration,
            "preflight_prosody": (
                {"passed": preflight_prosody["passed"], "gates_passed": preflight_prosody["gates_passed"]}
                if preflight_prosody is not None
                else None
            ),
            "issues": issues,
        }


def render_keyframe_contact_sheet(project_dir: Path) -> Path | None:
    """Renders `03_visuals/keyframe_contact_sheet.jpg` grid of all `03_visuals/reference_images/*.png` for pre-Flow human/CV checkpoint."""
    from pipeline.media_cache import stage_local_file

    p_dir = Path(project_dir)
    ref_dir = p_dir / "03_visuals" / "reference_images"
    if not ref_dir.exists():
        return None
    pngs = sorted(p for p in ref_dir.glob("*.png") if p.is_file())
    if not pngs:
        return None
    cols = min(7, len(pngs))
    rows = int(math.ceil(len(pngs) / float(cols)))
    tw, th = 180, 320
    canvas = np.full((rows * th, cols * tw, 3), 24, dtype=np.uint8)
    for idx, img_p in enumerate(pngs):
        r, c = divmod(idx, cols)
        local_p, _ = stage_local_file(img_p)
        img = cv2.imread(str(local_p), cv2.IMREAD_COLOR)
        if img is None or img.size == 0:
            continue
        thumb = cv2.resize(img, (tw, th), interpolation=cv2.INTER_AREA)
        cv2.rectangle(thumb, (0, 0), (tw, 28), (18, 18, 22), -1)
        label = f"#{idx + 1:02d} {img_p.stem[:16]}"
        cv2.putText(thumb, label, (6, 19), cv2.FONT_HERSHEY_SIMPLEX, 0.43, (245, 245, 245), 1, cv2.LINE_AA)
        canvas[r * th : (r + 1) * th, c * tw : (c + 1) * tw] = thumb
    out = p_dir / "03_visuals" / "keyframe_contact_sheet.jpg"
    out.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out), canvas, [cv2.IMWRITE_JPEG_QUALITY, 90])
    return out


def _render_contact_sheet(project_dir: Path) -> Path | None:
    from pipeline.media_cache import stage_local_file

    clips_dir = project_dir / "03_visuals" / "flow_native_clips"
    clip_files = sorted(clips_dir.glob("clip_*.mp4"), key=numeric_clip_sort_key)
    if not clip_files:
        return None
    cols = 10
    rows = int(math.ceil(len(clip_files) / float(cols)))
    tw, th = 144, 256
    canvas = np.zeros((rows * th, cols * tw, 3), dtype=np.uint8)
    for idx, cf in enumerate(clip_files):
        r, c = divmod(idx, cols)
        local_cf, _ = stage_local_file(cf)
        cap = cv2.VideoCapture(str(local_cf))
        fc = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, fc // 2))
        ok, frm = cap.read()
        cap.release()
        if ok and frm is not None:
            thumb = cv2.resize(frm, (tw, th), interpolation=cv2.INTER_AREA)
            cv2.putText(thumb, f"c{idx + 1}", (6, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2, cv2.LINE_AA)
            canvas[r * th : (r + 1) * th, c * tw : (c + 1) * tw] = thumb
    out = project_dir / "05_assembly" / "zero_plaque_contact_sheet.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out), canvas)
    return out


def _sync_full_project_manifest(project_dir: Path, status: str = "ASSEMBLED") -> None:
    from pipeline.media_cache import fast_file_sha256

    mpath = project_dir / "00_project_manifest.json"
    mdata = json.loads(mpath.read_text(encoding="utf-8")) if mpath.exists() else {"project_id": project_dir.name}
    now_iso = dt.datetime.now(dt.timezone.utc).isoformat()
    mdata["status"] = status
    mdata["updated_at"] = now_iso
    for s_name in STAGE_NAMES:
        sdir = project_dir / s_name
        arts: dict[str, Any] = {}
        if sdir.exists():
            for fp in sorted(sdir.rglob("*")):
                if fp.is_file():
                    rel = fp.relative_to(sdir).as_posix()
                    arts[rel] = {
                        "sha256": fast_file_sha256(fp),
                        "size_bytes": fp.stat().st_size,
                        "recorded_at": now_iso,
                    }
        mdata.setdefault("stages", {})[s_name] = {
            "status": "completed",
            "updated_at": now_iso,
            "artifacts": arts,
            "errors": [],
        }
    mpath.write_text(json.dumps(mdata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_stage_timings(asm_dir: Path, project_id: str, timings: dict[str, float], status: str, total_t0: float) -> None:
    asm_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "project_id": project_id,
        "status": status,
        "total_sec": round(time.monotonic() - total_t0, 2),
        "stages_sec": {k: round(float(v), 2) for k, v in timings.items()},
        "recorded_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
    }
    (asm_dir / "stage_timings.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _resolve_project_visual_plan(p_dir: Path) -> dict[str, Any]:
    vp_path = next(
        (
            p
            for p in (
                p_dir / "03_visuals" / "visual_plan.json",
                p_dir / "02_script" / "visual_plan.json",
                p_dir / "visual_plan.json",
            )
            if p.is_file()
        ),
        None,
    )
    if vp_path is None:
        return {}
    try:
        doc = json.loads(vp_path.read_text(encoding="utf-8"))
        return doc if isinstance(doc, dict) else {}
    except Exception:  # noqa: BLE001
        return {}


def partition_project_clips_by_engine(project_dir: str | Path) -> tuple[list[int], list[int]]:
    """Returns `(human_flow_clip_indices, brain_simulator_clip_indices)` (1-based) from `visual_plan.json`."""
    cand_p = Path(str(project_dir))
    p_dir = cand_p.resolve() if cand_p.exists() else (Path(PROJECTS_DIR) / str(project_dir)).resolve()
    vp = _resolve_project_visual_plan(p_dir)
    clips = vp.get("clips") if isinstance(vp.get("clips"), list) else []
    human_idxs: list[int] = []
    sim_idxs: list[int] = []
    for pos_i, c_spec in enumerate(clips, start=1):
        if not isinstance(c_spec, dict):
            continue
        c_idx = int(c_spec.get("clip_number") or c_spec.get("clip_index") or c_spec.get("id") or pos_i)
        if is_brain_simulator_clip_spec(c_spec):
            sim_idxs.append(c_idx)
        else:
            human_idxs.append(c_idx)
    return human_idxs, sim_idxs


def has_brain_simulator_clips(project_dir: str | Path) -> bool:
    _, sim_idxs = partition_project_clips_by_engine(project_dir)
    return bool(sim_idxs)


def has_pending_human_flow_clips(
    project_dir: str | Path,
    *,
    only_clips: list[int] | None = None,
    clean_existing: bool = False,
) -> tuple[bool, int]:
    """Checks whether any Flow-eligible human clips still require Google Flow browser generation."""
    cand_p = Path(str(project_dir))
    p_dir = cand_p.resolve() if cand_p.exists() else (Path(PROJECTS_DIR) / str(project_dir)).resolve()
    human_idxs, _ = partition_project_clips_by_engine(p_dir)
    if only_clips is not None:
        only_set = {int(x) for x in only_clips}
        eligible = [c for c in human_idxs if c in only_set]
    else:
        eligible = list(human_idxs)
    if not eligible:
        return False, 0
    if clean_existing and not only_clips:
        return True, len(eligible)
    native_dir = p_dir / "03_visuals" / "flow_native_clips"
    pending = 0
    for c_idx in eligible:
        mp4_p = native_dir / f"clip_{c_idx}.mp4"
        if not mp4_p.is_file() or mp4_p.stat().st_size < int(MIN_CLIP_SIZE_BYTES):
            pending += 1
    return pending > 0, pending


def _v8_transition_overlap_frames(tr_raw: str, visual_plan: dict[str, Any] | None = None) -> int:
    from pipeline.config import (
        EXPRESSIVE_V8_DISSOLVE_8_FRAMES,
        EXPRESSIVE_V8_DISSOLVE_FRAMES,
        EXPRESSIVE_V8_PORTAL_ZOOM_FRAMES,
        EXPRESSIVE_V8_WHIP_PAN_FRAMES,
    )

    tr_n = str(tr_raw or "").strip().lower()
    allow_alpha = bool((visual_plan or {}).get("allow_alpha_dissolves"))
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


def compute_edl_frame_map_from_edl(
    edl: dict[str, Any],
    visual_plan: dict[str, Any] | None = None,
    *,
    safety_pad_frames: int = 6,
) -> dict[int, int]:
    """Computes per-clip required frames (`eff_f + ov_f_next + safety_pad_frames`, floored at `fps * 2`)."""
    fps = max(1, int(edl.get("fps") or (visual_plan or {}).get("fps") or 30))
    min_frames = int(fps) * 2
    pad = max(0, int(safety_pad_frames))
    total_frames = int(edl.get("total_frames") or 0)
    cuts = edl.get("cuts") if isinstance(edl.get("cuts"), list) else []
    frame_map: dict[int, int] = {}
    cum_frames = 0
    for idx_c, cut in enumerate(cuts):
        if not isinstance(cut, dict):
            continue
        raw_f = max(1, int(cut.get("frames") or 0))
        if total_frames > 0:
            rem = total_frames - cum_frames
            if rem <= 0:
                break
            eff_f = min(rem, raw_f)
        else:
            eff_f = raw_f
        cum_frames += eff_f
        ov_out = _v8_transition_overlap_frames(
            str(cut.get("transition_out") or cut.get("transition_to_next") or ""),
            visual_plan,
        )
        prev_tr = (
            str(cuts[idx_c - 1].get("transition_out") or cuts[idx_c - 1].get("transition_to_next") or "")
            if idx_c > 0 and isinstance(cuts[idx_c - 1], dict)
            else ""
        )
        ov_in = _v8_transition_overlap_frames(prev_tr, visual_plan)
        req_f = max(min_frames, int(eff_f) + max(ov_out, ov_in) + pad)
        c_idx = int(cut.get("clip_index") or 0)
        if c_idx >= 1:
            frame_map[c_idx] = max(frame_map.get(c_idx, 0), req_f)
        sec_idx = cut.get("secondary_clip_index")
        if sec_idx is not None and int(sec_idx) >= 1:
            s_i = int(sec_idx)
            frame_map[s_i] = max(frame_map.get(s_i, 0), req_f)
    return frame_map


def lock_episode_audio_and_edl_frames(
    project_dir: str | Path,
    *,
    voice_preset: str | None = None,
    prosody_mode: str | None = None,
    safety_pad_frames: int = 6,
) -> dict[str, Any]:
    """
    Guard 4 Step 1 (Audio & Virtual Master EDL Lock):
      1. Runs `synthesize_continuous_diorama_track` + `P6` audio gate to lock `04_audio/audio_master.wav`
         and `04_audio/voice_report.json` BEFORE any Flow / Blender fork.
      2. Computes exact `30fps` per-clip frame requirements (`edl_frame_map`, `eff_f + ov_f_next + 6`)
         from the locked TTS timeline and persists `05_assembly/edl_timing_lock.json`.
    """
    import wave

    cand_p = Path(str(project_dir))
    p_dir = cand_p.resolve() if cand_p.exists() else (Path(PROJECTS_DIR) / str(project_dir)).resolve()
    audio_dir = p_dir / "04_audio"
    asm_dir = p_dir / "05_assembly"
    audio_dir.mkdir(parents=True, exist_ok=True)
    asm_dir.mkdir(parents=True, exist_ok=True)

    visual_plan = _resolve_project_visual_plan(p_dir)
    if visual_plan:
        visual_plan = {**visual_plan, "_visuals_dir": str(p_dir / "03_visuals")}
    sentences, script_doc = load_diorama_script_sentences(p_dir)

    eff_voice_preset = (
        str(
            voice_preset
            or script_doc.get("voice_preset")
            or visual_plan.get("voice_preset")
            or ""
        ).strip()
        or None
    )
    eff_prosody_mode = (
        str(
            prosody_mode
            or script_doc.get("prosody_mode")
            or visual_plan.get("prosody_mode")
            or ""
        ).strip()
        or None
    )
    if eff_voice_preset:
        script_doc = {**script_doc, "voice_preset": eff_voice_preset}

    vp_clips = visual_plan.get("clips") if isinstance(visual_plan.get("clips"), list) else []
    n_plan_clips = max(1, len(vp_clips))
    virtual_clip_files = [
        p_dir / "03_visuals" / "flow_native_clips" / f"clip_{i}.mp4"
        for i in range(1, n_plan_clips + 1)
    ]

    tts_res = synthesize_continuous_diorama_track(
        project_dir=p_dir,
        sentences=sentences,
        align_whisper=True,
        script_doc=script_doc,
        prosody_mode=eff_prosody_mode,
        voice_preset=eff_voice_preset,
    )

    wav_path = audio_dir / "audio_master.wav"
    vr_path = audio_dir / "voice_report.json"

    def _materialize_virtual_edl_and_audio(cur_tts: dict[str, Any]) -> dict[str, Any]:
        if not vr_path.is_file():
            rep_doc = cur_tts.get("report") if isinstance(cur_tts.get("report"), dict) else {
                "sentence_spans": cur_tts.get("sentence_spans") or [],
                "events": cur_tts.get("events") or [],
                "speech_end_sec": float(cur_tts.get("speech_end_sec") or 0.0),
                "total_duration_sec": float(cur_tts.get("total_duration_sec") or 0.0),
                "sample_rate": int(cur_tts.get("sr") or 48000),
            }
            with ram_tempdir(prefix="aab_vrep_") as td_vr:
                tmp_vr = Path(td_vr) / "voice_report.json"
                tmp_vr.write_text(json.dumps(rep_doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
                atomic_commit_from_scratch(tmp_vr, vr_path)

        try:
            v_edl = build_crosscut_edl(
                visual_plan=visual_plan,
                sentence_spans=cur_tts["sentence_spans"],
                clip_files=virtual_clip_files,
                speech_end_sec=float(cur_tts["speech_end_sec"]),
                total_duration_sec=float(cur_tts["total_duration_sec"]),
                script_doc=script_doc,
            )
        except Exception:  # noqa: BLE001
            fps_fb = max(1, int(visual_plan.get("fps") or 30))
            tot_s_fb = float(cur_tts.get("total_duration_sec") or 8.0)
            fb_cuts = []
            for idx_fb, c_fb in enumerate(vp_clips, start=1):
                dur_fb = float((c_fb if isinstance(c_fb, dict) else {}).get("duration_sec") or max(2.0, tot_s_fb / max(1, len(vp_clips))))
                fb_cuts.append(
                    {
                        "cut_index": idx_fb,
                        "clip_index": idx_fb,
                        "frames": max(fps_fb * 2, int(round(dur_fb * fps_fb))),
                        "duration_sec": dur_fb,
                        "transition_out": str((c_fb if isinstance(c_fb, dict) else {}).get("transition_out") or "hard"),
                    }
                )
            v_edl = {
                "fps": fps_fb,
                "speech_end_sec": float(cur_tts.get("speech_end_sec") or tot_s_fb),
                "total_duration_sec": tot_s_fb,
                "total_frames": int(round(tot_s_fb * fps_fb)),
                "cuts": fb_cuts,
            }

        pcm_arr = cur_tts.get("pcm")
        sr_val = int(cur_tts.get("sr") or 48000)
        if isinstance(pcm_arr, np.ndarray) and pcm_arr.size > 0:
            with ram_tempdir(prefix="aab_audiomaster_") as td_w:
                tmp_wav = Path(td_w) / "audio_master.wav"
                generate_diorama_audio_master(
                    wav_path=tmp_wav,
                    voice_pcm=pcm_arr,
                    sr=sr_val,
                    speech_end_sec=float(v_edl["speech_end_sec"]),
                    edl=v_edl,
                )
                atomic_commit_from_scratch(tmp_wav, wav_path)
        elif not wav_path.is_file():
            with ram_tempdir(prefix="aab_audiomaster_stub_") as td_w:
                tmp_wav = Path(td_w) / "audio_master.wav"
                n_stub = max(sr_val, int(round(float(v_edl.get("total_duration_sec") or 1.0) * sr_val)))
                with wave.open(str(tmp_wav), "wb") as wf:
                    wf.setnchannels(2)
                    wf.setsampwidth(2)
                    wf.setframerate(sr_val)
                    wf.writeframes(b"\x00\x00\x00\x00" * min(n_stub, sr_val))
                atomic_commit_from_scratch(tmp_wav, wav_path)
        return v_edl

    virtual_edl = _materialize_virtual_edl_and_audio(tts_res)

    # Pre-Fork P6 audio gate (catches word drops once before parallel video generation starts)
    retried_sentences: list[int] = []
    if (audio_dir / "prosody_report.json").is_file() and isinstance(tts_res.get("pcm"), np.ndarray):
        try:
            from pipeline import prosody as _prosody_mod

            pre_pros = _prosody_mod.evaluate_prosody_gates_on_audio(
                p_dir,
                audio_path=wav_path,
                gates=("P6_asr_by_gear",),
                run_asr=True,
            )
            p6_gate = (pre_pros.get("gates") or {}).get("P6_asr_by_gear") or {}
            low_sents = sorted({int(i) for i in (p6_gate.get("low_sentences_lt_0_80") or []) if int(i) >= 1})
            if (not p6_gate.get("passed", True)) or low_sents:
                retry_targets = set(low_sents) if low_sents else set(range(1, len(sentences) + 1))
                retried_sentences = sorted(retry_targets)
                tts_res = synthesize_continuous_diorama_track(
                    project_dir=p_dir,
                    sentences=sentences,
                    align_whisper=True,
                    script_doc=script_doc,
                    prosody_mode=eff_prosody_mode,
                    voice_preset=eff_voice_preset,
                    retry_intact_sentence_indices=retry_targets,
                )
                virtual_edl = _materialize_virtual_edl_and_audio(tts_res)
        except Exception:  # noqa: BLE001
            pass

    fps = max(1, int(virtual_edl.get("fps") or visual_plan.get("fps") or 30))
    edl_frame_map = compute_edl_frame_map_from_edl(
        virtual_edl,
        visual_plan,
        safety_pad_frames=safety_pad_frames,
    )

    asm_lock_fn = getattr(_diorama_assembler_mod, "compute_locked_edl_cut_frame_requirements", None)
    if callable(asm_lock_fn):
        try:
            helper_res = asm_lock_fn(p_dir, tts_res, safety_pad_frames=safety_pad_frames)
            helper_map = helper_res.get("edl_frame_map") if isinstance(helper_res, dict) else None
            if isinstance(helper_map, dict):
                for k_h, v_h in helper_map.items():
                    c_i = int(k_h)
                    edl_frame_map[c_i] = max(edl_frame_map.get(c_i, 0), int(v_h))
        except Exception:  # noqa: BLE001
            pass

    for pos_i, c_spec in enumerate(vp_clips, start=1):
        if not isinstance(c_spec, dict):
            continue
        c_idx = int(c_spec.get("clip_number") or c_spec.get("clip_index") or c_spec.get("id") or pos_i)
        if c_idx not in edl_frame_map:
            dur_s = float(
                c_spec.get("duration_sec")
                or c_spec.get("target_duration_sec")
                or c_spec.get("locked_spoken_duration_sec")
                or 4.8
            )
            edl_frame_map[c_idx] = max(fps * 2, int(round(dur_s * fps)) + int(safety_pad_frames))

    lock_path = asm_dir / "edl_timing_lock.json"
    lock_doc = {
        "project_id": p_dir.name,
        "fps": int(fps),
        "safety_pad_frames": int(safety_pad_frames),
        "speech_end_sec": round(float(virtual_edl.get("speech_end_sec") or tts_res.get("speech_end_sec") or 0.0), 4),
        "total_duration_sec": round(float(virtual_edl.get("total_duration_sec") or tts_res.get("total_duration_sec") or 0.0), 4),
        "edl_frame_map": {str(k): int(v) for k, v in sorted(edl_frame_map.items())},
        "p6_retried_sentences": retried_sentences,
        "locked_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
    }
    with ram_tempdir(prefix="aab_edl_lock_") as td_lk:
        tmp_lk = Path(td_lk) / "edl_timing_lock.json"
        tmp_lk.write_text(json.dumps(lock_doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        atomic_commit_from_scratch(tmp_lk, lock_path)

    return {
        "project_dir": str(p_dir),
        "audio_master_path": str(wav_path),
        "voice_report_path": str(vr_path),
        "edl_timing_lock_path": str(lock_path),
        "edl_frame_map": dict(edl_frame_map),
        "fps": int(fps),
        "speech_end_sec": lock_doc["speech_end_sec"],
        "total_duration_sec": lock_doc["total_duration_sec"],
    }


def finalize_and_verify_diorama_project(
    project_id: str,
    voice_preset: str | None = None,
    prosody_mode: str | None = None,
    *,
    cpu_budget: int | None = None,
    preserve_audio_master: bool = False,
) -> dict[str, Any]:
    """Runs `assemble_diorama_project`, fail-fast Prosody P1-P10, DQ1-DQ12, R64, `autopsy`, `thumbnail`, `reenact-qa` (Track A), KB sync, and `verify`."""
    from pipeline import thumbnail_studio
    from pipeline.config import NEURO_NEWS_HOLD_FROM_AUTO_QUEUE, NEURO_NEWS_STAGING_DIR, REENACT_QA_REPORT_FILENAME
    from pipeline.dynamic_episode_qa import compile_episode_qa_contract, verify_final_mp4_against_contract
    from pipeline.knowledge_hub import sync_project_to_knowledge_base
    from pipeline.media_cache import shared_mp4_decode_session, stage_local_file
    from pipeline.posthoc_semantic_qa import extract_cut_intent_specs, run_posthoc_semantic_qa
    from pipeline.prosody import evaluate_prosody_gates

    t_total0 = time.monotonic()
    timings: dict[str, float] = {}

    p_dir = Path(PROJECTS_DIR) / project_id
    asm_dir = p_dir / "05_assembly"
    fd_dir = p_dir / "03_visuals" / "flow_downloads"
    if fd_dir.exists():
        shutil.rmtree(fd_dir, ignore_errors=True)

    # Clear stale QA reports before rebuilding so fail-fast aborts never leave outdated pass/fail state for AutoHeal
    for stale_qa in (
        "video_autopsy_report.json",
        "dynamic_episode_qa_report.json",
        "posthoc_semantic_qa_report.json",
        "prosody_qa_report.json",
        REENACT_QA_REPORT_FILENAME,
    ):
        (asm_dir / stale_qa).unlink(missing_ok=True)

    t_s = time.monotonic()
    asm_kwargs: dict[str, Any] = {"force_rebuild": True, "run_posthoc_qa": False}
    if voice_preset:
        asm_kwargs["voice_preset"] = voice_preset
    if prosody_mode:
        asm_kwargs["prosody_mode"] = prosody_mode
    asm_sig = inspect.signature(assemble_diorama_project)
    asm_has_varkw = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in asm_sig.parameters.values())
    if preserve_audio_master and (asm_has_varkw or "preserve_audio_master" in asm_sig.parameters):
        asm_kwargs["preserve_audio_master"] = True
    elif "preserve_audio_master" in asm_sig.parameters:
        asm_kwargs["preserve_audio_master"] = bool(preserve_audio_master)
    if cpu_budget is not None and (asm_has_varkw or "cpu_budget" in asm_sig.parameters):
        asm_kwargs["cpu_budget"] = int(cpu_budget)
    asm_res = assemble_diorama_project(project_id, **asm_kwargs)
    timings["assembly_sec"] = time.monotonic() - t_s
    final_mp4 = Path(asm_res["final_mp4"])
    if not final_mp4.exists():
        _write_stage_timings(asm_dir, project_id, timings, "ASSEMBLY_FAILED", t_total0)
        raise RuntimeError(f"Final MP4 missing after assembly: {final_mp4}")

    # Enforce R25 single-MP4 inside project directory; archive delivery copy AFTER all QA passes
    stale_root_mp4 = p_dir / f"final_shorts_{project_id}.mp4"
    if stale_root_mp4.exists():
        stale_root_mp4.unlink()
    meta_doc_chk = (
        json.loads((p_dir / "06_publish" / "metadata.json").read_text(encoding="utf-8"))
        if (p_dir / "06_publish" / "metadata.json").exists()
        else {}
    )
    is_news_staging = bool(meta_doc_chk.get("hold_from_auto_queue")) or (
        NEURO_NEWS_HOLD_FROM_AUTO_QUEUE and project_id.startswith("news_")
    )
    delivery_dir = NEURO_NEWS_STAGING_DIR if is_news_staging else COMPLETED_SHORTS_DIR
    delivery_dir.mkdir(parents=True, exist_ok=True)
    completed_mp4 = delivery_dir / f"final_shorts_{project_id}.mp4"

    t_s = time.monotonic()
    local_mp4, _ = stage_local_file(final_mp4)
    _render_contact_sheet(p_dir)
    timings["stage_and_contact_sheet_sec"] = time.monotonic() - t_s

    # Fail-fast Stage: R63-P Prosody QA gates P1-P10 BEFORE expensive full-video frame decoding!
    # Also populates `mp4_asr_v1` and `autopsy_audio_v2` caches so DQ1, R64, and Autopsy reuse them in 0ms.
    prosody_rep: dict[str, Any] = {"passed": True, "skipped": True}
    if (p_dir / "04_audio" / "prosody_report.json").exists():
        t_s = time.monotonic()
        prosody_rep = evaluate_prosody_gates(p_dir, run_asr=True, save_report=True, strict_freshness=True)
        timings["prosody_qa_sec"] = time.monotonic() - t_s
        if not prosody_rep.get("passed"):
            _write_stage_timings(asm_dir, project_id, timings, "QA_FAILED_PROSODY", t_total0)
            _sync_full_project_manifest(p_dir, status="QA_FAILED")
            failed = [k for k, v in (prosody_rep.get("gates") or {}).items() if not v.get("passed")]
            raise RuntimeError(f"[script_fix_required] Prosody QA (P1-P10) failed for {project_id}: {failed}")

    # Pre-collect union of needed frame indices for DQ1-DQ12 + R64 so ONE sequential decode feeds all 3 QA engines
    t_s = time.monotonic()
    cap_hdr = cv2.VideoCapture(str(local_mp4))
    fps_u = float(cap_hdr.get(cv2.CAP_PROP_FPS) or 24.0)
    fc_u = int(cap_hdr.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    cap_hdr.release()
    dur_u = (fc_u / fps_u) if (fps_u > 0 and fc_u > 0) else 0.0
    union_fidxs: set[int] = set()
    if fc_u > 0:
        for k in range(min(30, max(6, int(dur_u / 6.0)))):
            union_fidxs.add(max(0, min(fc_u - 1, int(round((1.5 + k * max(1.0, (dur_u - 4.0) / 28.0)) * fps_u)))))
        try:
            cuts_u, _ = extract_cut_intent_specs(p_dir, final_mp4_duration_sec=dur_u)
            for c_u in cuts_u:
                c_s = float(c_u["out_start_sec"])
                c_e = max(c_s + 0.12, min(dur_u if dur_u > 0 else float(c_u["out_end_sec"]), float(c_u["out_end_sec"])))
                c_dur = c_e - c_s
                pad = min(0.38, 0.18 * c_dur) if c_dur >= 2.2 else min(0.08, 0.15 * c_dur)
                t0, t1 = c_s + pad, max(c_s + pad + 0.04, c_e - pad)
                for ts_u in np.arange(t0, t1 + 1e-6, 0.25):
                    union_fidxs.add(max(0, min(fc_u - 1, int(round(float(ts_u) * fps_u)))))
                union_fidxs.add(max(0, min(fc_u - 1, int(round(t1 * fps_u)))))
            edl_doc = json.loads((asm_dir / "edit_decision_list.json").read_text(encoding="utf-8"))
            edl_cuts = edl_doc.get("cuts") or []
            sents_u, sdoc_u = load_diorama_script_sentences(p_dir)
            vp_u = json.loads((p_dir / "03_visuals" / "visual_plan.json").read_text(encoding="utf-8"))
            from pipeline.flow_prompt_builder import build_flow_prompts as _b_fp

            contract_u = compile_episode_qa_contract(vp_u, sents_u, _b_fp(vp_u, sents_u), script_doc=sdoc_u)
            for a_lock in contract_u.get("analogy_locks") or []:
                s_idx_a = int(a_lock.get("sentence_index") or 0)
                sibs = [
                    ec for ec in edl_cuts
                    if int(ec.get("sentence_index") or 0) <= s_idx_a <= int(ec.get("end_sentence_index") or ec.get("sentence_index") or 0)
                ]
                for ec in sibs:
                    mid_t = 0.5 * (float(ec["out_start_sec"]) + float(ec["out_end_sec"]))
                    union_fidxs.add(max(0, min(fc_u - 1, int(round(mid_t * fps_u)))))
            for ec in edl_cuts:
                if str(ec.get("mode") or "") in ("split_hstack", "split_vstack"):
                    mid_t = 0.5 * (float(ec["out_start_sec"]) + float(ec["out_end_sec"]))
                    union_fidxs.add(max(0, min(fc_u - 1, int(round(mid_t * fps_u)))))
        except Exception as exc:  # noqa: BLE001
            import logging

            logging.getLogger("diorama_batch_orchestrator").warning(
                "Union frame pre-decode sample index scan warning for %s: %s", project_id, exc
            )

    ref_imgs_dir = p_dir / "03_visuals" / "reference_images"
    if ref_imgs_dir.exists() and any(ref_imgs_dir.glob("*.png")):
        from pipeline.reference_image_qa import inspect_reference_image_pack, is_reference_qa_report_fresh

        ref_fresh_ok, _ = is_reference_qa_report_fresh(p_dir)
        if not ref_fresh_ok:
            t_s = time.monotonic()
            inspect_reference_image_pack(p_dir, save_report=True)
            timings["ref_qa_refresh_sec"] = time.monotonic() - t_s

    t_dec = time.monotonic()
    with shared_mp4_decode_session(final_mp4, frame_indices=union_fidxs):
        timings["shared_decode_sec"] = time.monotonic() - t_dec
        t_s = time.monotonic()
        ep_qa_rep = verify_final_mp4_against_contract(p_dir, save_report=True)
        timings["episode_qa_sec"] = time.monotonic() - t_s
        t_s = time.monotonic()
        posthoc_rep = run_posthoc_semantic_qa(p_dir, render_strips=True, save_report=True)
        timings["posthoc_qa_sec"] = time.monotonic() - t_s
        t_s = time.monotonic()
        autopsy_rep = VideoAutopsyEngine.inspect_project(project_id, save_report=True)
        timings["autopsy_sec"] = time.monotonic() - t_s

    if not autopsy_rep.get("passed"):
        _write_stage_timings(asm_dir, project_id, timings, "QA_FAILED_AUTOPSY", t_total0)
        _sync_full_project_manifest(p_dir, status="QA_FAILED")
        raise RuntimeError(f"VideoAutopsyEngine failed for {project_id}: {autopsy_rep.get('defects')}")
    if not ep_qa_rep.get("passed"):
        _write_stage_timings(asm_dir, project_id, timings, "QA_FAILED_DQ", t_total0)
        _sync_full_project_manifest(p_dir, status="QA_FAILED")
        raise RuntimeError(f"DynamicEpisodeQA (DQ1-DQ12) failed for {project_id}: {ep_qa_rep.get('gates_passed')}")
    if not posthoc_rep.get("cv_passed", False):
        _write_stage_timings(asm_dir, project_id, timings, "QA_FAILED_POSTHOC", t_total0)
        _sync_full_project_manifest(p_dir, status="QA_FAILED")
        raise RuntimeError(
            f"PostHocSemanticQA (R64) flagged weak cuts for {project_id}: {posthoc_rep['summary']['weak_cut_indices']}"
        )
    if not posthoc_rep.get("passed"):
        from pipeline.posthoc_semantic_qa import init_posthoc_semantic_review_template

        rev_file = asm_dir / "posthoc_semantic_review.json"
        if not rev_file.exists():
            init_posthoc_semantic_review_template(p_dir, qa_report=posthoc_rep, auto_populate_from_cv=False)
        _write_stage_timings(asm_dir, project_id, timings, "REVIEW_PENDING", t_total0)
        _sync_full_project_manifest(p_dir, status="REVIEW_PENDING")
        raise RuntimeError(
            f"REVIEW_PENDING (Gate 2 @Research visual sign-off required) for {project_id}: "
            f"sheets={posthoc_rep.get('viewer_sheets')} review_file={rev_file}"
        )

    # R65 v2 Thumbnail Studio hard gate (TQ1-TQ9; auto-generates 0-credit cutaway keyart when cutaway_keyart_prompt is set)
    t_s = time.monotonic()
    try:
        vp_th_path = p_dir / "03_visuals" / "visual_plan.json"
        vp_th_doc = json.loads(vp_th_path.read_text(encoding="utf-8")) if vp_th_path.exists() else {}
        auto_keyart = bool(((vp_th_doc.get("thumbnail") or {}) if isinstance(vp_th_doc, dict) else {}).get("cutaway_keyart_prompt"))
        thumb_rep = thumbnail_studio.run(p_dir, force=False, strict=True, generate_keyart=auto_keyart)
        timings["thumbnail_sec"] = time.monotonic() - t_s
    except Exception as exc:
        timings["thumbnail_sec"] = time.monotonic() - t_s
        _write_stage_timings(asm_dir, project_id, timings, "QA_FAILED_THUMBNAIL", t_total0)
        _sync_full_project_manifest(p_dir, status="QA_FAILED")
        raise RuntimeError(f"Thumbnail Studio QA (R65 TQ1-TQ9) failed for {project_id}: {exc}") from exc

    # R67 Reenactment Non-Infringement & Fidelity QA (RQ1-RQ5) for Track A / source-EDL episodes
    rqa_rep: dict[str, Any] = {"passed": True, "skipped": True}
    vp_chk_path = p_dir / "03_visuals" / "visual_plan.json"
    vp_chk_doc = json.loads(vp_chk_path.read_text(encoding="utf-8")) if vp_chk_path.exists() else {}
    if (p_dir / "03_visuals" / "source_edl.json").exists() or str(vp_chk_doc.get("reenactment_track") or "") == "track_a":
        from pipeline.source_reenactment import purge_reenactment_quarantine, validate_reenactment_non_infringement

        t_s = time.monotonic()
        d_dir_rqa = rd.resolve_dossier_for_project(project_id)
        rqa_slug = str(
            vp_chk_doc.get("dossier_slug")
            or vp_chk_doc.get("dossier")
            or (d_dir_rqa.name if d_dir_rqa else "")
            or project_id
        ).strip()
        purge_reenactment_quarantine(slug=rqa_slug)
        rqa_rep = validate_reenactment_non_infringement(
            project_dir=p_dir,
            dossier_dir=d_dir_rqa,
            require_quarantine_purged=True,
            save_report=True,
        )
        timings["reenact_qa_sec"] = time.monotonic() - t_s
        if not rqa_rep.get("passed"):
            _write_stage_timings(asm_dir, project_id, timings, "QA_FAILED_REENACT", t_total0)
            _sync_full_project_manifest(p_dir, status="QA_FAILED")
            raise RuntimeError(f"ReenactmentQA (RQ1-RQ5) failed for {project_id}: {rqa_rep.get('gates_passed')}")

    t_s = time.monotonic()
    from pipeline.publish import export_multi_platform_bundle

    multi_bundle = export_multi_platform_bundle(p_dir, copy_video=True)
    build_asset_manifest(p_dir)
    sync_project_to_knowledge_base(p_dir, posthoc_report=posthoc_rep)
    timings["asset_and_kb_sec"] = time.monotonic() - t_s

    # Record stage timings BEFORE manifest sync so verify_integrity locks its exact SHA-256
    _write_stage_timings(asm_dir, project_id, timings, "ASSEMBLED", t_total0)
    _sync_full_project_manifest(p_dir, status="ASSEMBLED")

    t_s = time.monotonic()
    verify_rep = ProjectStorage(project_id).verify_integrity()
    verify_sec = round(time.monotonic() - t_s, 2)

    if not verify_rep.get("all_intact"):
        raise RuntimeError(f"Integrity verification failed for {project_id}: {verify_rep.get('corrupted_or_missing')}")

    t_s = time.monotonic()
    shutil.copy2(local_mp4, completed_mp4)
    gdrive_copy_sec = round(time.monotonic() - t_s, 2)

    return {
        "passed": True,
        "project_id": project_id,
        "duration_sec": asm_res["duration_sec"],
        "cut_count": asm_res["cut_count"],
        "max_clip_reuse": asm_res["max_clip_reuse"],
        "verified_artifacts": verify_rep["verified_artifacts"],
        "autopsy_passed": bool(autopsy_rep["passed"]),
        "episode_qa_passed": bool(ep_qa_rep["passed"]),
        "posthoc_passed": bool(posthoc_rep["passed"]),
        "posthoc_mean_clarity": posthoc_rep["summary"]["mean_clarity_score"],
        "prosody_qa_passed": bool(prosody_rep.get("passed")),
        "thumbnail_passed": bool(thumb_rep.get("passed")),
        "reenact_qa_passed": bool(rqa_rep.get("passed")),
        "cover_frame_sec": thumb_rep.get("cover_frame_sec"),
        "stage_timings_sec": {
            **{k: round(float(v), 2) for k, v in timings.items()},
            "verify_sec": verify_sec,
            "gdrive_copy_sec": gdrive_copy_sec,
            "total_sec": round(time.monotonic() - t_total0, 2),
        },
        "completed_mp4": str(completed_mp4),
        "multi_platform_bundle_dir": multi_bundle["bundle_dir"],
    }


def _collect_auto_heal_plan(project_id: str) -> dict[str, Any]:
    """
    Identify offending clip indices and EDL-only remediation actions from DQ2/DQ5/DQ7/DQ8/DQ9
    and R64 PostHoc QA so healthy Flow clips are never deleted when only an EDL/subtitle shift
    or a script/plan fix (`DQ3_anatomy_to_brain_sync`, `DQ1` mapping, `P*` prosody) is needed.
    """
    import re

    p_dir = Path(PROJECTS_DIR) / project_id
    asm_dir = p_dir / "05_assembly"
    regen_cuts: set[int] = set()
    edl_only_cuts: set[int] = set()
    bad_clips: set[int] = set()
    script_fix_reasons: list[str] = []

    pros_path = asm_dir / "prosody_qa_report.json"
    if pros_path.exists():
        try:
            pr_doc = json.loads(pros_path.read_text(encoding="utf-8"))
            if not pr_doc.get("passed", True):
                failed_p = [k for k, v in (pr_doc.get("gates") or {}).items() if not v.get("passed")]
                script_fix_reasons.append(f"prosody_qa:{failed_p}")
        except Exception as exc:  # noqa: BLE001
            import logging

            logging.getLogger("diorama_batch_orchestrator").warning(
                "Failed reading prosody_qa_report.json for %s: %s", project_id, exc
            )

    dq_path = asm_dir / "dynamic_episode_qa_report.json"
    if dq_path.exists():
        try:
            dq = json.loads(dq_path.read_text(encoding="utf-8"))
            gates = dq.get("gates") or {}
            if not (gates.get("DQ3_anatomy_to_brain_sync") or {}).get("passed", True):
                script_fix_reasons.append(
                    f"DQ3_anatomy_to_brain_sync:{(gates.get('DQ3_anatomy_to_brain_sync') or {}).get('failures')}"
                )
            if not (gates.get("DQ4_brisk_storyteller_wpm") or {}).get("passed", True):
                script_fix_reasons.append("DQ4_brisk_storyteller_wpm")
            if not (gates.get("DQ5_three_gear_cut_rhythm") or {}).get("passed", True):
                script_fix_reasons.append("DQ5_three_gear_cut_rhythm")
            dq1_obj = gates.get("DQ1_literal_analogy_frame_sync") or {}
            if not dq1_obj.get("passed", True):
                dq1_fails = [str(x) for x in (dq1_obj.get("failures") or [])]
                if not dq1_fails or any("no EDL cut" in f or "outside EDL cut" in f for f in dq1_fails):
                    script_fix_reasons.append(f"DQ1_literal_analogy_mapping:{dq1_fails}")

            if not script_fix_reasons:
                for g_key, field in (
                    ("DQ8_zero_uncanny_skin_gore", "skin_leak_cuts"),
                    ("DQ8_zero_uncanny_skin_gore", "yunet_human_face_cuts"),
                    ("DQ9_zero_background_plaque", "plaque_cuts"),
                ):
                    for cid in (gates.get(g_key) or {}).get(field) or []:
                        regen_cuts.add(int(cid))
                for cnum in (gates.get("DQ6_zero_clip_reuse") or {}).get("unattached_reference_clips") or []:
                    bad_clips.add(int(cnum))
                for cid in (gates.get("DQ7_continuous_motion_no_freeze") or {}).get("freeze_cuts") or []:
                    edl_only_cuts.add(int(cid))
                for g_key in ("DQ2_clothed_cast_and_impact", "DQ5_everyday_analogies", "DQ5_cold_open_and_impact"):
                    g_obj = gates.get(g_key) or {}
                    for fail_item in (
                        g_obj.get("failures")
                        or g_obj.get("failed_analogies")
                        or g_obj.get("failed_locks")
                        or []
                    ):
                        fail_str = json.dumps(fail_item) if isinstance(fail_item, dict) else str(fail_item)
                        m_clip = re.search(r"\bclip(?:_number|_index)?[_\s#:\"=]*(\d+)\b", fail_str, flags=re.IGNORECASE)
                        if m_clip:
                            bad_clips.add(int(m_clip.group(1)))
                        m_cut = re.search(r"\bcut(?:_index)?[_\s#:\"=]*(\d+)\b", fail_str, flags=re.IGNORECASE)
                        if m_cut:
                            regen_cuts.add(int(m_cut.group(1)))
        except Exception as exc:  # noqa: BLE001
            import logging

            logging.getLogger("diorama_batch_orchestrator").warning(
                "Failed reading dynamic_episode_qa_report.json for %s: %s", project_id, exc
            )

    if script_fix_reasons:
        return {
            "script_fix_required": True,
            "script_fix_reasons": script_fix_reasons,
            "regenerate_clips": [],
            "edl_only_cuts": [],
            "rebuild_only": False,
        }

    ph_cut_actions: dict[int, str] = {}
    ph_cut_bad_clips: dict[int, list[int]] = {}
    ph_path = asm_dir / "posthoc_semantic_qa_report.json"
    if ph_path.exists():
        try:
            ph = json.loads(ph_path.read_text(encoding="utf-8"))
            summary = ph.get("summary") or {}
            for cnum in summary.get("regenerate_clip_indices") or []:
                bad_clips.add(int(cnum))
            for cut_rep in ph.get("cuts") or []:
                if not isinstance(cut_rep, dict):
                    continue
                cid = int(cut_rep.get("cut_index") or 0)
                act = str(cut_rep.get("remediation_action") or "none")
                ph_cut_actions[cid] = act
                attrib = cut_rep.get("source_clip_attribution") or {}
                per_pane = [
                    int(x)
                    for x in (attrib.get("regenerate_clip_indices") or cut_rep.get("regenerate_clip_indices") or [])
                    if int(x) > 0
                ]
                if per_pane:
                    ph_cut_bad_clips[cid] = per_pane
                if cid in (summary.get("weak_cut_indices") or []):
                    if act in ("shift_edl_source_window", "rebuild_assembly_edl_or_subtitles"):
                        edl_only_cuts.add(cid)
                    else:
                        regen_cuts.add(cid)
        except Exception as exc:  # noqa: BLE001
            import logging

            logging.getLogger("diorama_batch_orchestrator").warning(
                "Failed reading posthoc_semantic_qa_report.json for %s: %s", project_id, exc
            )

    # If a freeze cut has no shift_edl_source_window recommendation or already failed R64 source motion, escalate to regen
    for cid in list(edl_only_cuts):
        if ph_cut_actions.get(cid) == "regenerate_flow_clip":
            edl_only_cuts.discard(cid)
            regen_cuts.add(cid)

    edl_path = asm_dir / "edit_decision_list.json"
    if regen_cuts and edl_path.exists():
        try:
            edl = json.loads(edl_path.read_text(encoding="utf-8"))
            for cut in edl.get("cuts") or []:
                cid = int(cut.get("cut_index") or 0)
                if cid not in regen_cuts:
                    continue
                if cid in ph_cut_bad_clips and ph_cut_bad_clips[cid]:
                    for c_only in ph_cut_bad_clips[cid]:
                        bad_clips.add(c_only)
                else:
                    if cut.get("clip_index"):
                        bad_clips.add(int(cut["clip_index"]))
                    sec_idx = cut.get("secondary_clip_index") or cut.get("right_clip_index")
                    if sec_idx:
                        bad_clips.add(int(sec_idx))
        except Exception as exc:  # noqa: BLE001
            import logging

            logging.getLogger("diorama_batch_orchestrator").warning(
                "Failed reading edit_decision_list.json for %s: %s", project_id, exc
            )

    regen_list = sorted(c for c in bad_clips if c > 0)
    return {
        "script_fix_required": False,
        "script_fix_reasons": [],
        "regenerate_clips": regen_list,
        "edl_only_cuts": sorted(c for c in edl_only_cuts if c > 0),
        "rebuild_only": bool(not regen_list and edl_only_cuts),
    }


def _collect_auto_heal_clip_indices(project_id: str) -> list[int]:
    """Identify offending clip indices from DQ2/DQ5/DQ7/DQ8/DQ9 and R64 PostHoc QA for targeted regeneration."""
    return _collect_auto_heal_plan(project_id)["regenerate_clips"]


def _is_already_completed(project_id: str) -> bool:
    from pipeline.config import (
        DEFAULT_DIORAMA_VOICE_PRESET,
        DIORAMA_V7_US_PROSODY_MODE,
        DIORAMA_VOICE_PRESETS,
        DOSSIER_SCHEMA_VERSION,
        EXPRESSIVE_25D_V8_STYLE_PROFILE,
        EXPRESSIVE_V8_PROSODY_MODE,
        FROZEN_PRE_SCHEMA_V2_PROJECT_PREFIXES,
        HISTORICAL_LEGACY_VOICE_PRESET_IDS,
        PORCELAIN_V7_STYLE_PROFILE,
        REENACT_QA_REPORT_FILENAME,
    )

    p_dir = Path(PROJECTS_DIR) / project_id
    comp_mp4 = COMPLETED_SHORTS_DIR / f"final_shorts_{project_id}.mp4"
    asm_dir = p_dir / "05_assembly"
    autopsy_path = asm_dir / "video_autopsy_report.json"
    dq_path = asm_dir / "dynamic_episode_qa_report.json"
    ph_path = asm_dir / "posthoc_semantic_qa_report.json"
    prosody_qa_path = asm_dir / "prosody_qa_report.json"
    thumb_path = p_dir / "06_publish" / "thumbnail_report.json"
    if not (
        comp_mp4.exists()
        and comp_mp4.stat().st_size > 5_000_000
        and autopsy_path.exists()
        and dq_path.exists()
        and ph_path.exists()
        and prosody_qa_path.exists()
        and thumb_path.exists()
    ):
        return False
    try:
        arep = json.loads(autopsy_path.read_text(encoding="utf-8"))
        dqrep = json.loads(dq_path.read_text(encoding="utf-8"))
        phrep = json.loads(ph_path.read_text(encoding="utf-8"))
        prrep = json.loads(prosody_qa_path.read_text(encoding="utf-8"))
        threp = json.loads(thumb_path.read_text(encoding="utf-8"))
        base_ok = (
            bool(arep.get("passed"))
            and bool(dqrep.get("passed"))
            and bool(phrep.get("passed"))
            and bool(prrep.get("passed"))
            and bool(threp.get("passed"))
        )
        if not base_ok:
            return False
        vp_path = p_dir / "03_visuals" / "visual_plan.json"
        vp_doc = json.loads(vp_path.read_text(encoding="utf-8")) if vp_path.exists() else {}
        sc_path = p_dir / "02_script" / "script.json"
        sc_doc = json.loads(sc_path.read_text(encoding="utf-8")) if sc_path.exists() else {}
        is_frozen_v1 = any(project_id.startswith(pref) for pref in FROZEN_PRE_SCHEMA_V2_PROJECT_PREFIXES)
        if not is_frozen_v1:
            vp_style = str(vp_doc.get("style_profile") or "")
            if vp_style not in (PORCELAIN_V7_STYLE_PROFILE, EXPRESSIVE_25D_V8_STYLE_PROFILE):
                return False
            expected_prosody = (
                EXPRESSIVE_V8_PROSODY_MODE
                if vp_style == EXPRESSIVE_25D_V8_STYLE_PROFILE
                else DIORAMA_V7_US_PROSODY_MODE
            )
            vp_voice = str(sc_doc.get("voice_preset") or vp_doc.get("voice_preset") or DEFAULT_DIORAMA_VOICE_PRESET).strip()
            vp_prosody = str(sc_doc.get("prosody_mode") or vp_doc.get("prosody_mode") or "").strip()
            allowed_voices = set(DIORAMA_VOICE_PRESETS) | set(HISTORICAL_LEGACY_VOICE_PRESET_IDS)
            if vp_voice not in allowed_voices or vp_prosody != expected_prosody:
                return False
            pr_meta_path = p_dir / "04_audio" / "prosody_report.json"
            if pr_meta_path.exists():
                pr_meta = json.loads(pr_meta_path.read_text(encoding="utf-8"))
                pr_voice = str(pr_meta.get("voice_preset") or "").strip()
                if (
                    (pr_voice and pr_voice != vp_voice)
                    or str(pr_meta.get("prosody_mode") or "") != expected_prosody
                ):
                    return False
            ref_qa_path = p_dir / "03_visuals" / "reference_image_qa_report.json"
            if not ref_qa_path.exists():
                return False
            ref_qa_doc = json.loads(ref_qa_path.read_text(encoding="utf-8"))
            if not bool(ref_qa_doc.get("pre_generation_ready")):
                return False
            d_slug = str(vp_doc.get("dossier") or sc_doc.get("dossier") or "").strip()
            if d_slug:
                d_meta_path = rd.dossier_dir(d_slug) / "dossier.json"
                if not d_meta_path.exists():
                    return False
                d_meta = json.loads(d_meta_path.read_text(encoding="utf-8"))
                if int(d_meta.get("schema_version") or 1) < DOSSIER_SCHEMA_VERSION:
                    return False
        if (p_dir / "03_visuals" / "source_edl.json").exists() or str(vp_doc.get("reenactment_track") or "") == "track_a":
            rqa_path = asm_dir / REENACT_QA_REPORT_FILENAME
            if not rqa_path.exists():
                return False
            rqa_doc = json.loads(rqa_path.read_text(encoding="utf-8"))
            if not bool(rqa_doc.get("passed")):
                return False
        return True
    except Exception:
        return False


def _save_batch_status(state: dict[str, Any]) -> None:
    import os

    state["updated_at_utc"] = dt.datetime.now(dt.timezone.utc).isoformat()
    payload = json.dumps(state, indent=2, ensure_ascii=False) + "\n"
    BATCH_STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = BATCH_STATUS_PATH.with_name(f".{BATCH_STATUS_PATH.name}.{os.getpid()}.tmp")
    tmp_path.write_text(payload, encoding="utf-8")
    os.replace(tmp_path, BATCH_STATUS_PATH)


def _unlink_sim_clips_for_regen(project_dir: Path, clip_indices: list[int]) -> None:
    sim_dir = project_dir / "03_visuals" / "brain_simulator_clips"
    for c_idx in clip_indices:
        for name in (
            f"clip_{c_idx}.mp4",
            f"clip_{c_idx:02d}.mp4",
            f"clip_{c_idx}_sim_qa.json",
            f"clip_{c_idx}_camera_track.json",
        ):
            (sim_dir / name).unlink(missing_ok=True)


def generate_and_finalize_diorama_episode(
    project_id: str,
    tabs: int = FLOW_MAX_PARALLEL_BATCH_SIZE,
    clean_existing: bool = False,
    cdp_port: int = 9222,
    engine_mode: str | None = None,
    max_heal_rounds: int = 2,
    voice_preset: str | None = None,
    prosody_mode: str | None = None,
) -> dict[str, Any]:
    """
    Gear 3 + Gear 4 for ONE already-synced project with Level A overlapping (Guard 4):
      1. Step 1 (Audio & Virtual Master EDL Lock): locks `audio_master.wav`, `voice_report.json`, and
         `05_assembly/edl_timing_lock.json` (`edl_frame_map`) strictly BEFORE Fork.
      2. Step 2 (Concurrent Fork): overlaps R76 Blender `3x2` (`6 vCPU`) rendering in a background
         future while Google Flow runs human clips on CDP `9222` (`<= 5` tabs), or runs Blender at
         `4x2` (`8 vCPU`) standalone when 0 Flow human clips are pending.
      3. Step 3 (Join -> Preserve Audio Master Assembly): joins both branches and runs
         `finalize_and_verify_diorama_project(..., preserve_audio_master=True, cpu_budget=8)`.
    """
    flow_sig = inspect.signature(run_sharded_diorama_flow_generation)
    flow_has_varkw = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in flow_sig.parameters.values())
    extra_flow_kwargs: dict[str, Any] = {}
    if engine_mode is not None and (flow_has_varkw or "engine_mode" in flow_sig.parameters):
        extra_flow_kwargs["engine_mode"] = engine_mode
    if flow_has_varkw or "include_brain_simulator_clips" in flow_sig.parameters:
        extra_flow_kwargs["include_brain_simulator_clips"] = False

    pid = str(project_id)
    p_dir = Path(PROJECTS_DIR) / pid
    vp_path = p_dir / "03_visuals" / "visual_plan.json"
    if vp_path.exists():
        from pipeline.config import is_expressive_v8_plan, is_porcelain_v7_plan
        from pipeline.porcelain_anchor_pack import ensure_porcelain_reference_pack

        vp_doc = json.loads(vp_path.read_text(encoding="utf-8"))
        if is_porcelain_v7_plan(vp_doc) or is_expressive_v8_plan(vp_doc):
            ref_res = ensure_porcelain_reference_pack(
                p_dir,
                cdp_port=cdp_port,
                force=False,
                require_review=True,
            )
            sheet_p_g1 = render_keyframe_contact_sheet(p_dir)
            if not ref_res.get("pre_generation_ready"):
                if ref_res.get("cv_pre_generation_ready"):
                    raise RuntimeError(
                        f"REVIEW_PENDING (Gate 1 @Research keyframe sign-off required) for {pid}: "
                        f"contact_sheet={sheet_p_g1} review_file={p_dir / '03_visuals' / 'reference_images' / 'reference_semantic_review.json'}"
                    )
                raise RuntimeError(
                    f"Reference pack failed pre_generation_ready for {pid}: "
                    f"regenerate={ref_res.get('regenerate_image_ids')} score={ref_res.get('reference_qa_score')}"
                )

    # Step 1 (Guard 4): Strictly lock TTS + P6 + Master EDL frame budget BEFORE Flow/Blender fork
    lock_info = lock_episode_audio_and_edl_frames(
        p_dir,
        voice_preset=voice_preset,
        prosody_mode=prosody_mode,
    )
    edl_frame_map: dict[int, int] = dict(lock_info["edl_frame_map"])

    # Step 2 (Guard 4): Concurrent Fork of Google Flow (human clips) + R76 Blender 3D Simulator
    human_clip_nums, sim_clip_nums = partition_project_clips_by_engine(p_dir)
    pending_flow, _ = has_pending_human_flow_clips(p_dir, clean_existing=clean_existing)

    if sim_clip_nums and pending_flow:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as fork_pool:
            sim_fut = fork_pool.submit(
                render_project_brain_simulator_clips_parallel,
                p_dir,
                edl_frame_map=edl_frame_map,
                overlapped=True,
                force=bool(clean_existing),
            )
            try:
                asyncio.run(
                    run_sharded_diorama_flow_generation(
                        project_id=pid,
                        clean_existing=clean_existing,
                        only_clips=None,
                        max_parallel_tabs=tabs,
                        cdp_port=cdp_port,
                        **extra_flow_kwargs,
                    )
                )
            finally:
                sim_res = sim_fut.result()
        if not sim_res.get("all_passed", True):
            raise RuntimeError(f"R76 Brain Simulator QA failed during overlapped fork for {pid}: {sim_res}")
    elif sim_clip_nums:
        if human_clip_nums:
            asyncio.run(
                run_sharded_diorama_flow_generation(
                    project_id=pid,
                    clean_existing=clean_existing,
                    only_clips=None,
                    max_parallel_tabs=tabs,
                    cdp_port=cdp_port,
                    **extra_flow_kwargs,
                )
            )
        sim_res = render_project_brain_simulator_clips_parallel(
            p_dir,
            edl_frame_map=edl_frame_map,
            cpu_budget=resolve_cpu_budget(overlapped=False),
            overlapped=False,
            force=bool(clean_existing),
        )
        if not sim_res.get("all_passed", True):
            raise RuntimeError(f"R76 Brain Simulator QA failed for {pid}: {sim_res}")
    else:
        asyncio.run(
            run_sharded_diorama_flow_generation(
                project_id=pid,
                clean_existing=clean_existing,
                only_clips=None,
                max_parallel_tabs=tabs,
                cdp_port=cdp_port,
                **extra_flow_kwargs,
            )
        )

    # Step 3 (Guard 4): Join -> Preserve Audio Master Assembly (8-core /dev/shm)
    fin: dict[str, Any] | None = None
    last_exc: Exception | None = None
    fin_kwargs: dict[str, Any] = {
        "cpu_budget": resolve_cpu_budget(overlapped=False),
        "preserve_audio_master": True,
    }
    if voice_preset:
        fin_kwargs["voice_preset"] = voice_preset
    if prosody_mode:
        fin_kwargs["prosody_mode"] = prosody_mode
    sim_set = set(sim_clip_nums)
    for heal_round in range(max_heal_rounds + 1):
        try:
            fin = finalize_and_verify_diorama_project(pid, **fin_kwargs)
            last_exc = None
            break
        except Exception as qa_exc:  # noqa: BLE001
            last_exc = qa_exc
            if heal_round >= max_heal_rounds:
                break
            heal_plan = _collect_auto_heal_plan(pid)
            if heal_plan.get("script_fix_required"):
                last_exc = RuntimeError(
                    f"[script_fix_required] {pid} failed script/plan gate ({heal_plan.get('script_fix_reasons')}); "
                    f"skipping pointless Flow clip regeneration ({qa_exc})"
                )
                break
            heal_clips = heal_plan["regenerate_clips"]
            if heal_plan["rebuild_only"]:
                print(
                    f"[Diorama][AutoHeal {heal_round + 1}/{max_heal_rounds}] {pid} needs EDL/window rebuild only on cuts "
                    f"{heal_plan['edl_only_cuts']} ({qa_exc}); preserving Flow clips and re-assembling..."
                )
                continue
            if not heal_clips or len(heal_clips) > 10:
                break
            print(
                f"[Diorama][AutoHeal {heal_round + 1}/{max_heal_rounds}] {pid} flagged clips {heal_clips} "
                f"({qa_exc}); regenerating offending clips..."
            )
            sim_heal = [int(c) for c in heal_clips if int(c) in sim_set]
            human_heal = [int(c) for c in heal_clips if int(c) not in sim_set]
            if human_heal:
                clips_dir = p_dir / "03_visuals" / "flow_native_clips"
                for c_idx in human_heal:
                    for pat in (f"clip_{c_idx:02d}.mp4", f"clip_{c_idx}.mp4"):
                        (clips_dir / pat).unlink(missing_ok=True)
            if sim_heal:
                _unlink_sim_clips_for_regen(p_dir, sim_heal)

            if sim_heal and human_heal:
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as heal_pool:
                    sim_heal_fut = heal_pool.submit(
                        render_project_brain_simulator_clips_parallel,
                        p_dir,
                        edl_frame_map=edl_frame_map,
                        overlapped=True,
                        force=False,
                    )
                    try:
                        asyncio.run(
                            run_sharded_diorama_flow_generation(
                                project_id=pid,
                                clean_existing=False,
                                only_clips=human_heal,
                                max_parallel_tabs=min(tabs, max(1, len(human_heal))),
                                cdp_port=cdp_port,
                                **extra_flow_kwargs,
                            )
                        )
                    finally:
                        sim_heal_fut.result()
            elif sim_heal:
                render_project_brain_simulator_clips_parallel(
                    p_dir,
                    edl_frame_map=edl_frame_map,
                    cpu_budget=resolve_cpu_budget(overlapped=False),
                    overlapped=False,
                    force=False,
                )
            elif human_heal:
                asyncio.run(
                    run_sharded_diorama_flow_generation(
                        project_id=pid,
                        clean_existing=False,
                        only_clips=human_heal,
                        max_parallel_tabs=min(tabs, max(1, len(human_heal))),
                        cdp_port=cdp_port,
                        **extra_flow_kwargs,
                    )
                )
    if fin is None:
        assert last_exc is not None
        raise last_exc
    return fin


def run_single_diorama_episode(
    slug: str,
    project_id: str,
    pillar: str,
    precheck_only: bool = False,
    tabs: int = FLOW_MAX_PARALLEL_BATCH_SIZE,
    force_regenerate: bool = False,
    cdp_port: int = 9222,
    engine_mode: str | None = None,
    voice_preset: str | None = None,
    prosody_mode: str | None = None,
    draft_subdir: str | None = None,
    stop_after: str | None = None,
) -> dict[str, Any]:
    """
    One-shot production of ANY dossier-backed episode (not limited to DIORAMA_BATCH_20_SPECS):
    sync `research_dossiers/<slug>/diorama_v8_expressive/` (or `diorama_v7_porcelain/` / `diorama_v7_lowpoly/`) -> `projects/<project_id>/`,
    pre-Flow precheck (prompt-gate incl. R57-H2 cold-open, fact trace, paradox title, plaque lock, TTS clock),
    optional checkpoint halt (`stop_after='audio'` or `'keyframes'`), then Flow generation + assembly + full QA chain.
    Refuses to touch published projects.
    """
    p_dir = Path(PROJECTS_DIR) / project_id
    if (p_dir / "06_publish" / "upload_receipt.json").exists():
        raise RuntimeError(f"Refusing to (re)produce published project {project_id} (upload_receipt.json present)")
    stop_stage = str(stop_after or "").strip().lower() or None
    if stop_stage is not None and stop_stage not in ("audio", "keyframes"):
        raise ValueError(f"Unsupported stop_after={stop_after!r} (expected None, 'audio', or 'keyframes')")
    spec: dict[str, Any] = {"index": 0, "wave": 0, "project_id": project_id, "slug": slug, "pillar": pillar}
    if draft_subdir:
        spec["draft_subdir"] = str(draft_subdir).strip()
    if voice_preset:
        spec["voice_preset"] = voice_preset
    if prosody_mode:
        spec["prosody_mode"] = prosody_mode
    if not precheck_only and stop_stage is None and not force_regenerate and _is_already_completed(project_id):
        pre = precheck_diorama_project(spec, run_tts_clock=True)
        return {"passed": True, "mode": "already_completed", "project_id": project_id, "precheck": pre}
    t0 = time.time()
    precheck_spec = {**spec, "_allow_live_tts": bool(not precheck_only)} if not precheck_only else spec
    pre = precheck_diorama_project(precheck_spec, run_tts_clock=True)
    print(
        f"[Precheck][{'PASS' if pre['passed'] else 'FAIL'}] {project_id} | sents={pre['sentences']} "
        f"clips={pre['clips']} words={pre['words']} tts={pre['tts_duration_sec']}s"
    )
    for iss in pre["issues"]:
        print(f"    - {iss}")
    if not pre["passed"]:
        raise RuntimeError(f"Precheck failed for {project_id}: {pre['issues']}")
    if precheck_only:
        return {"passed": bool(pre["passed"]), "mode": "precheck_only", "precheck": pre}
    sync_project_from_dossier_diorama(spec, write_back_dossier=True)
    if stop_stage in ("audio", "keyframes"):
        from pipeline.voice_fallback import _write_mono_wav

        sents_st, sdoc_st = load_diorama_script_sentences(p_dir)
        tts_st = synthesize_continuous_diorama_track(
            project_dir=p_dir,
            sentences=sents_st,
            align_whisper=True,
            prosody_mode=prosody_mode or str(sdoc_st.get("prosody_mode") or "").strip() or None,
            script_doc=sdoc_st,
            voice_preset=voice_preset or str(sdoc_st.get("voice_preset") or "").strip() or None,
        )
        wav_out = p_dir / "04_audio" / "audio_master.wav"
        _write_mono_wav(wav_out, tts_st["pcm"], int(tts_st.get("sr") or 48000))
        if stop_stage == "audio":
            return {
                "passed": True,
                "mode": "stopped_after_audio",
                "project_id": project_id,
                "audio_master": str(wav_out),
                "tts_duration_sec": round(float(tts_st["total_duration_sec"]), 3),
                "precheck": pre,
            }
        from pipeline.porcelain_anchor_pack import ensure_porcelain_reference_pack

        ref_res = ensure_porcelain_reference_pack(
            p_dir,
            cdp_port=cdp_port,
            force=force_regenerate,
            require_review=True,
        )
        sheet_p = render_keyframe_contact_sheet(p_dir)
        return {
            "passed": bool(ref_res.get("pre_generation_ready")),
            "status": "APPROVED" if ref_res.get("pre_generation_ready") else ("REVIEW_PENDING" if ref_res.get("cv_pre_generation_ready") else "QA_FAILED"),
            "mode": "stopped_after_keyframes",
            "project_id": project_id,
            "audio_master": str(wav_out),
            "tts_duration_sec": round(float(tts_st["total_duration_sec"]), 3),
            "reference_qa_score": ref_res.get("reference_qa_score"),
            "pre_generation_ready": bool(ref_res.get("pre_generation_ready")),
            "contact_sheet": str(sheet_p) if sheet_p else None,
            "precheck": pre,
        }
    gen_kwargs: dict[str, Any] = {
        "tabs": tabs,
        "clean_existing": force_regenerate,
        "cdp_port": cdp_port,
        "engine_mode": engine_mode,
    }
    if voice_preset:
        gen_kwargs["voice_preset"] = voice_preset
    if prosody_mode:
        gen_kwargs["prosody_mode"] = prosody_mode
    fin = generate_and_finalize_diorama_episode(project_id, **gen_kwargs)
    fin["elapsed_min"] = round((time.time() - t0) / 60.0, 2)
    fin["precheck"] = pre
    return fin


produce_single_diorama_episode = run_single_diorama_episode


def run_diorama_batch(
    wave: str = "all",
    project_ids: list[str] | None = None,
    precheck_only: bool = False,
    tabs: int = FLOW_MAX_PARALLEL_BATCH_SIZE,
    force_regenerate: bool = False,
    cdp_port: int = 9222,
    engine_mode: str | None = None,
    voice_preset: str | None = None,
    prosody_mode: str | None = None,
    sequential: bool = False,
) -> dict[str, Any]:
    specs = select_batch_specs(wave=wave, project_ids=project_ids)
    if not specs:
        raise ValueError(f"No batch specs matched wave={wave!r}, project_ids={project_ids!r}")
    if voice_preset:
        specs = [{**sp, "voice_preset": voice_preset} for sp in specs]
    if prosody_mode:
        specs = [{**sp, "prosody_mode": prosody_mode} for sp in specs]

    if not precheck_only and not sequential:
        from pipeline.diorama_pipeline_runner import run_diorama_pipeline

        pipe_rep = run_diorama_pipeline(
            specs=specs,
            precheck_only=False,
            tabs=tabs,
            force_regenerate=force_regenerate,
            cdp_port=cdp_port,
            engine_mode=engine_mode,
            isolate_precheck_failures=False,
            voice_preset=voice_preset,
            prosody_mode=prosody_mode,
        )
        return {
            "mode": "pipeline",
            "wave": wave,
            "completed_in_run": int(pipe_rep["completed_in_run"]),
            "total_completed_overall": int(pipe_rep["total_completed_overall"]),
            "results": list(pipe_rep["results"]),
        }

    prechecks = []
    for sp in specs:
        sp_pre = {**sp, "_allow_live_tts": bool(not precheck_only)} if not precheck_only else sp
        rep = precheck_diorama_project(sp_pre, run_tts_clock=True)
        prechecks.append(rep)
        status_tag = "PASS" if rep["passed"] else "FAIL"
        print(
            f"[Precheck][{status_tag}] #{sp['index']:02d} {sp['project_id']} | "
            f"sents={rep['sentences']} clips={rep['clips']} words={rep['words']} tts={rep['tts_duration_sec']}s"
        )
        if rep["issues"]:
            for iss in rep["issues"]:
                print(f"    - {iss}")

    failed_pre = [r for r in prechecks if not r["passed"]]
    if failed_pre:
        raise RuntimeError(f"Precheck failed on {len(failed_pre)} project(s): {[r['project_id'] for r in failed_pre]}")

    if precheck_only:
        return {"mode": "precheck_only", "count": len(prechecks), "all_passed": True, "projects": prechecks}

    state: dict[str, Any] = (
        json.loads(BATCH_STATUS_PATH.read_text(encoding="utf-8"))
        if BATCH_STATUS_PATH.exists()
        else {"total_target": len(DIORAMA_DAILY_30_SPECS), "completed": {}, "in_progress": None, "errors": {}}
    )
    state["total_target"] = len(DIORAMA_DAILY_30_SPECS)
    if not isinstance(state.get("completed"), dict):
        state["completed"] = {}
    if not isinstance(state.get("errors"), dict):
        state["errors"] = {}

    run_errors: dict[str, str] = {}
    results: list[dict[str, Any]] = []
    for sp in specs:
        pid = str(sp["project_id"])
        if not force_regenerate and _is_already_completed(pid):
            print(f"[DioramaBatch] Skipping already-completed & verified project: {pid}")
            state["completed"][pid] = state["completed"].get(pid) or {"status": "COMPLETED_RESUMED"}
            _save_batch_status(state)
            continue

        t0 = time.time()
        state["in_progress"] = {"project_id": pid, "wave": sp["wave"], "started_at_epoch": round(t0, 1)}
        _save_batch_status(state)
        print(
            f"\n==================== [DioramaBatch #{sp['index']:02d}/{len(DIORAMA_DAILY_30_SPECS)} | Wave {sp['wave']}] {pid} ===================="
        )
        try:
            sync_project_from_dossier_diorama(sp, write_back_dossier=True)
            gen_kwargs: dict[str, Any] = {
                "tabs": tabs,
                "clean_existing": force_regenerate,
                "cdp_port": cdp_port,
                "engine_mode": engine_mode,
            }
            if voice_preset:
                gen_kwargs["voice_preset"] = voice_preset
            if prosody_mode:
                gen_kwargs["prosody_mode"] = prosody_mode
            fin = generate_and_finalize_diorama_episode(pid, **gen_kwargs)
            fin["elapsed_min"] = round((time.time() - t0) / 60.0, 2)
            state["completed"][pid] = fin
            state["errors"].pop(pid, None)
            state["in_progress"] = None
            _save_batch_status(state)
            results.append(fin)
            print(
                f"[DioramaBatch] COMPLETED {pid} in {fin['elapsed_min']} min -> "
                f"{fin['completed_mp4']} ({fin['duration_sec']}s, {fin['cut_count']} cuts, INTACT)"
            )
        except Exception as exc:
            err_msg = str(exc)
            print(f"[DioramaBatch][ERROR] {pid} failed: {err_msg}")
            state["errors"][pid] = {"error": err_msg, "failed_at_utc": dt.datetime.now(dt.timezone.utc).isoformat()}
            state["in_progress"] = None
            _save_batch_status(state)
            run_errors[pid] = err_msg

    if run_errors:
        raise RuntimeError(f"Batch finished with {len(run_errors)} failed project(s): {run_errors}")

    return {
        "mode": "production",
        "wave": wave,
        "completed_in_run": len(results),
        "total_completed_overall": len(state.get("completed", {})),
        "results": results,
    }
