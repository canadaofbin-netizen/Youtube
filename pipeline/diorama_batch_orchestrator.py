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
import datetime as dt
import hashlib
import json
import math
import re
import shutil
import time
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from pipeline import research_dossier as rd
from pipeline.asset_manifest import build_asset_manifest
from pipeline.config import (
    DIORAMA_DURATION_MIN_SEC,
    DIORAMA_TTS_VOICE,
    FLOW_MAX_PARALLEL_BATCH_SIZE,
    PROJECTS_DIR,
    SHORTS_HARD_CEILING_SEC,
    WORKSPACE_ROOT,
)
from pipeline.diorama_assembler import assemble_diorama_project, load_diorama_script_sentences
from pipeline.flow_diorama_sharded_worker import run_sharded_diorama_flow_generation
from pipeline.flow_prompt_builder import build_diorama_v6_prompts, write_flow_prompts_json
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

DIORAMA_BATCH_20_SPECS: tuple[dict[str, Any], ...] = (
    # Wave 1 (01-05)
    {
        "index": 1,
        "wave": 1,
        "project_id": "diorama_01_patient_hm_hippocampus",
        "slug": "patient_hm_hippocampus",
        "pillar": "brain_history",
    },
    {
        "index": 2,
        "wave": 1,
        "project_id": "diorama_02_ramachandran_phantom_mirror",
        "slug": "ramachandran_phantom_limb_mirror",
        "pillar": "brain_health",
    },
    {
        "index": 3,
        "wave": 1,
        "project_id": "diorama_03_alien_hand_syndrome",
        "slug": "alien_hand_syndrome",
        "pillar": "brain_mysteries",
    },
    {
        "index": 4,
        "wave": 1,
        "project_id": "diorama_04_milgram_obedience_switch",
        "slug": "milgram_obedience_shock",
        "pillar": "bci_ethics",
    },
    {
        "index": 5,
        "wave": 1,
        "project_id": "diorama_05_hippocampal_memory_prosthesis",
        "slug": "hippocampal_memory_prosthesis",
        "pillar": "bci_tech",
    },
    # Wave 2 (06-10)
    {
        "index": 6,
        "wave": 2,
        "project_id": "diorama_06_clive_wearing_seven_second_mind",
        "slug": "clive_wearing_seven_second_mind",
        "pillar": "brain_mysteries",
    },
    {
        "index": 7,
        "wave": 2,
        "project_id": "diorama_07_invisible_gorilla_attention",
        "slug": "invisible_gorilla_attention",
        "pillar": "brain_mysteries",
    },
    {
        "index": 8,
        "wave": 2,
        "project_id": "diorama_08_maguire_london_taxi_hippocampus",
        "slug": "maguire_london_taxi_hippocampus",
        "pillar": "brain_health",
    },
    {
        "index": 9,
        "wave": 2,
        "project_id": "diorama_09_broca_patient_tan_speech_loss",
        "slug": "broca_patient_tan_speech_loss",
        "pillar": "brain_history",
    },
    {
        "index": 10,
        "wave": 2,
        "project_id": "diorama_10_olds_milner_pleasure_center",
        "slug": "olds_milner_pleasure_center",
        "pillar": "bci_tech",
    },
    # Wave 3 (11-15)
    {
        "index": 11,
        "wave": 3,
        "project_id": "diorama_11_blindsight_subcortical_vision",
        "slug": "blindsight_subcortical_vision",
        "pillar": "brain_mysteries",
    },
    {
        "index": 12,
        "wave": 3,
        "project_id": "diorama_12_penfield_cortical_homunculus",
        "slug": "penfield_cortical_homunculus",
        "pillar": "brain_history",
    },
    {
        "index": 13,
        "wave": 3,
        "project_id": "diorama_13_asch_conformity_pressure",
        "slug": "asch_conformity_pressure",
        "pillar": "bci_ethics",
    },
    {
        "index": 14,
        "wave": 3,
        "project_id": "diorama_14_libet_readiness_potential",
        "slug": "libet_readiness_potential_free_will",
        "pillar": "brain_mysteries",
    },
    {
        "index": 15,
        "wave": 3,
        "project_id": "diorama_15_draganski_juggling_gray_matter",
        "slug": "draganski_juggling_gray_matter",
        "pillar": "brain_health",
    },
    # Wave 4 (16-20)
    {
        "index": 16,
        "wave": 4,
        "project_id": "diorama_16_rizzolatti_mirror_neuron_empathy",
        "slug": "rizzolatti_mirror_neuron_empathy",
        "pillar": "brain_news",
    },
    {
        "index": 17,
        "wave": 4,
        "project_id": "diorama_17_damasio_somatic_marker_decision",
        "slug": "damasio_somatic_marker_decision",
        "pillar": "brain_basics",
    },
    {
        "index": 18,
        "wave": 4,
        "project_id": "diorama_18_greene_trolley_dilemma_dual_process",
        "slug": "greene_trolley_dilemma_dual_process",
        "pillar": "bci_ethics",
    },
    {
        "index": 19,
        "wave": 4,
        "project_id": "diorama_19_davidson_monk_gamma_synchrony",
        "slug": "davidson_monk_gamma_synchrony",
        "pillar": "brain_health",
    },
    {
        "index": 20,
        "wave": 4,
        "project_id": "diorama_20_dutton_aron_capilano_bridge",
        "slug": "dutton_aron_capilano_bridge_arousal",
        "pillar": "brain_basics",
    },
)


def select_batch_specs(wave: str = "all", project_ids: list[str] | None = None) -> list[dict[str, Any]]:
    if project_ids:
        wanted = set(project_ids)
        return [dict(s) for s in DIORAMA_BATCH_20_SPECS if s["project_id"] in wanted]
    w = str(wave or "all").strip().lower()
    if w in ("all", "1-4", "20"):
        return [dict(s) for s in DIORAMA_BATCH_20_SPECS]
    w_num = int(w)
    return [dict(s) for s in DIORAMA_BATCH_20_SPECS if int(s["wave"]) == w_num]


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
            authors = _strip_md(str(s.get("authors") or "Peer-reviewed study"))
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
    p_author = (
        str(primary.get("authors") or "").split(",")[0].split(";")[0].strip()
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

    slug_words = [w.capitalize() for w in slug.split("_") if len(w) >= 4 and w.lower() not in ("with", "from", "into", "that")]
    custom_tag = f"#{''.join(slug_words[:2])}" if slug_words else "#BrainResearch"
    pillar_tags = _PILLAR_TOPIC_HASHTAG_MAP.get(pillar, ["#Neuroscience", "#Psychology", "#BrainScience"])
    hashtags = list(dict.fromkeys(["#Shorts", custom_tag, *pillar_tags]))[:5]

    sources_block = (
        "Primary Peer-Reviewed Sources:\n" + "\n".join(citation_lines) + "\n\n"
        if citation_lines
        else (f"Primary Peer-Reviewed Source: https://doi.org/{doi}\n\n" if doi else "")
    )
    desc = (
        f"{para_1}\n\n"
        f"{para_2}\n\n"
        f"{sources_block}"
        "AI Disclosure: Visual reenactments, 3D anatomical models, and narration in this documentary Short were produced with AI synthesis tools from verified peer-reviewed sources.\n\n"
        + " ".join(hashtags)
    )
    return desc, hashtags, doi


def _default_metadata_from_script_and_dossier(
    project_id: str,
    pillar: str,
    slug: str,
    script_doc: dict[str, Any],
) -> dict[str, Any]:
    desc, hashtags, doi = build_editorial_description_from_dossier(project_id, pillar, slug, script_doc)
    return {
        "project_id": project_id,
        "profile": "neuro_diorama",
        "pillar": pillar,
        "dossier_slug": slug,
        "language": "en-US",
        "video_language": "en-US",
        "title_description_language": "en-US",
        "channel_residence_country": "KR",
        "title": str(script_doc.get("title") or ""),
        "doi": doi,
        "ai_disclosure": True,
        "hashtags": hashtags,
        "description": desc,
    }


def sync_project_from_dossier_diorama(spec: dict[str, Any]) -> Path:
    """Materializes/updates `projects/<project_id>/` from `research_dossiers/<slug>/diorama_v7*/` (with v6 fallback)."""
    from pipeline.config import (
        DEFAULT_DIORAMA_STYLE_PROFILE,
        DIORAMA_V7_STYLE_PROFILE,
        PORCELAIN_V7_STYLE_PROFILE,
        PROMPT_SCHEMA_VERSION_V7,
        is_diorama_v7_plan,
        resolve_diorama_v7_style_profile,
    )
    from pipeline.flow_prompt_builder import build_flow_prompts

    project_id = str(spec["project_id"])
    slug = str(spec["slug"])
    pillar = str(spec["pillar"])
    d_root = rd.dossier_dir(slug)
    cand_names: list[str] = []
    if spec.get("draft_subdir"):
        cand_names.append(str(spec["draft_subdir"]))
    for cname in ("diorama_v7_porcelain", "diorama_v7", "diorama_v7_lowpoly", "diorama_v6_dynamic"):
        if cname not in cand_names:
            cand_names.append(cname)
    draft_dir: Path | None = None
    for cname in cand_names:
        cand = d_root / cname
        if (cand / "script.json").exists() and (cand / "visual_plan.json").exists():
            draft_dir = cand
            break
    if draft_dir is None:
        raise FileNotFoundError(
            f"Missing diorama_v7_porcelain / diorama_v7 / diorama_v7_lowpoly / diorama_v6_dynamic draft under {d_root}"
        )

    script_doc = json.loads((draft_dir / "script.json").read_text(encoding="utf-8"))
    visual_plan = json.loads((draft_dir / "visual_plan.json").read_text(encoding="utf-8"))
    is_v7 = (
        is_diorama_v7_plan(visual_plan)
        or is_diorama_v7_plan(script_doc)
        or draft_dir.name in ("diorama_v7_porcelain", "diorama_v7", "diorama_v7_lowpoly")
    )
    if draft_dir.name == "diorama_v7_porcelain":
        fallback_style = PORCELAIN_V7_STYLE_PROFILE
    elif draft_dir.name == "diorama_v7":
        fallback_style = DEFAULT_DIORAMA_STYLE_PROFILE
    else:
        fallback_style = DIORAMA_V7_STYLE_PROFILE
    resolved_v7_style = resolve_diorama_v7_style_profile(
        visual_plan,
        script_doc,
        fallback=fallback_style,
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
    if is_v7:
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

    from pipeline.voice_fallback import resolve_diorama_voice_preset

    eff_voice_preset = str(
        spec.get("voice_preset")
        or script_doc.get("voice_preset")
        or visual_plan.get("voice_preset")
        or ""
    ).strip() or None
    if eff_voice_preset:
        script_doc["voice_preset"] = eff_voice_preset
        visual_plan["voice_preset"] = eff_voice_preset
    eff_prosody_mode = str(spec.get("prosody_mode") or "").strip()
    if eff_prosody_mode:
        script_doc["prosody_mode"] = eff_prosody_mode
    preset_name, preset_cfg = resolve_diorama_voice_preset(eff_voice_preset, script_doc=script_doc, visual_plan=visual_plan)

    sentences = [str(s).strip() for s in script_doc["sentences"] if str(s).strip()]
    from pipeline.config import is_porcelain_v7_plan

    if is_porcelain_v7_plan(visual_plan) and not visual_plan.get("reference_anchors"):
        from pipeline.porcelain_anchor_pack import populate_porcelain_reference_contract

        populate_porcelain_reference_contract(visual_plan, dossier_dir=d_root)
    clips = build_flow_prompts(visual_plan, sentences)

    # Save canonical prompts in draft_dir too
    (draft_dir / "script.json").write_text(json.dumps(script_doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (draft_dir / "visual_plan.json").write_text(json.dumps(visual_plan, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    draft_prompts_payload: dict[str, Any] = {
        "schema_version": PROMPT_SCHEMA_VERSION_V7 if is_v7 else 6,
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

    if is_porcelain_v7_plan(visual_plan):
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
                (draft_dir / "reference_image_specs.json").write_text(
                    dst_specs.read_text(encoding="utf-8"), encoding="utf-8"
                )
        d_edl = d_root / "08_reenactment_edl.json"
        dst_edl = p_dir / "03_visuals" / "source_edl.json"
        if d_edl.exists() and not dst_edl.exists():
            dst_edl.write_text(d_edl.read_text(encoding="utf-8"), encoding="utf-8")

    meta_src = draft_dir / "metadata.json"
    if meta_src.exists():
        meta_doc = json.loads(meta_src.read_text(encoding="utf-8"))
        meta_doc["project_id"] = project_id
        meta_doc["pillar"] = pillar
        meta_doc.setdefault("video_language", "en-US")
        meta_doc.setdefault("title_description_language", "en-US")
        meta_doc.setdefault("channel_residence_country", "KR")
    else:
        meta_doc = _default_metadata_from_script_and_dossier(project_id, pillar, slug, script_doc)
        meta_src.write_text(json.dumps(meta_doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (p_dir / "06_publish" / "metadata.json").write_text(
        json.dumps(meta_doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    # Ensure manifest carries profile/doi/camera_profile metadata
    m_path = p_dir / "00_project_manifest.json"
    m_doc = json.loads(m_path.read_text(encoding="utf-8")) if m_path.exists() else {}
    m_doc["project_id"] = project_id
    m_doc["title"] = str(script_doc.get("title") or project_id)
    m_doc["pillar"] = pillar
    m_doc["dossier_slug"] = slug
    m_doc["profile"] = "neuro_diorama"
    m_doc["schema_version"] = PROMPT_SCHEMA_VERSION_V7 if is_v7 else 6
    if is_v7:
        m_doc["style_profile"] = resolved_v7_style
    m_doc["voice_preset"] = preset_name
    m_doc["camera_profile"] = visual_plan["camera_profile"]
    m_doc["doi"] = str(script_doc.get("doi") or meta_doc.get("doi") or "")
    m_path.write_text(json.dumps(m_doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # Link project_id into dossier.json
    d_json_path = rd.dossier_dir(slug) / "dossier.json"
    if d_json_path.exists():
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
    issues: list[str] = []
    plan_clips = visual_plan.get("clips") if isinstance(visual_plan.get("clips"), list) else []
    if not plan_clips:
        return issues

    n_clips = len(plan_clips)
    outro_idx = n_clips - 1
    for idx, spec in enumerate(plan_clips):
        if isinstance(spec, dict) and str(spec.get("cut_role") or "").strip().lower() == "outro":
            outro_idx = idx
            break
    reserved_0based: set[int] = {outro_idx}
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
) -> dict[str, Any]:
    """Validates `prompt-gate`, contract lock mapping (DQ1/DQ3), paradox title, zero-plaque nouns, and pre-Flow TTS + Prosody P1-P6/P8/P10."""
    import os
    import tempfile

    from pipeline.config import (
        DIORAMA_V7_DURATION_MIN_SEC,
        MICRO_SHORT_MAX_SEC,
        MICRO_SHORT_MIN_SEC,
        MICRO_SHORT_PROFILE,
        is_diorama_v7_plan,
    )
    from pipeline.dynamic_episode_qa import compile_episode_qa_contract
    from pipeline.flow_prompt_builder import build_flow_prompts
    from pipeline.prosody import evaluate_prosody_gates_on_audio
    from pipeline.voice_fallback import _write_mono_wav, resolve_diorama_voice_preset

    eff_spec = {**spec, "voice_preset": voice_preset} if voice_preset else spec
    p_dir = sync_project_from_dossier_diorama(eff_spec)
    slug = str(spec["slug"])
    sentences, script_doc = load_diorama_script_sentences(p_dir)
    visual_plan = json.loads((p_dir / "03_visuals" / "visual_plan.json").read_text(encoding="utf-8"))
    is_v7 = is_diorama_v7_plan(visual_plan) or is_diorama_v7_plan(script_doc)
    clips = build_flow_prompts(visual_plan, sentences)

    issues: list[str] = []
    issues.extend(validate_production_diorama_v6(visual_plan, sentences, clips, script_doc=script_doc))
    issues.extend(rd.check_narration_facts(slug, sentences))
    issues.extend(validate_diorama_paradox_title(str(script_doc.get("title") or "")))
    contract = compile_episode_qa_contract(visual_plan, sentences, clips, script_doc=script_doc)
    issues.extend(_plan_lock_mapping_issues(visual_plan, contract, rendered_clips=clips))

    # Positive scene scan for empirical plaque-trigger nouns (excluding negated clauses like 'without plaques')
    for c in clips:
        sc = re.sub(r"\b(?:without|zero|no)\s+[a-z\s,-]{1,35}", " ", str(c.get("scene") or ""), flags=re.IGNORECASE)
        hits = sorted({m.group(0).lower() for m in _PLAQUE_TRIGGER_NOUNS_RE.finditer(sc)})
        if hits:
            issues.append(f"[plaque_lock] clip {c['clip_number']} positive scene contains plaque-trigger word(s) {hits}")

    tts_duration = None
    preflight_prosody: dict[str, Any] | None = None
    fmt_profile = str(script_doc.get("format_profile") or visual_plan.get("format_profile") or "").strip().lower()
    is_micro = fmt_profile == MICRO_SHORT_PROFILE
    min_dur = MICRO_SHORT_MIN_SEC if is_micro else (DIORAMA_V7_DURATION_MIN_SEC if is_v7 else DIORAMA_DURATION_MIN_SEC)
    max_dur = MICRO_SHORT_MAX_SEC if is_micro else SHORTS_HARD_CEILING_SEC
    eff_vp = voice_preset or str(spec.get("voice_preset") or script_doc.get("voice_preset") or visual_plan.get("voice_preset") or "").strip() or None
    preset_name, preset_cfg = resolve_diorama_voice_preset(eff_vp, script_doc=script_doc, visual_plan=visual_plan)
    if run_tts_clock and not issues:
        tts_res = synthesize_continuous_diorama_track(
            project_dir=p_dir,
            sentences=sentences,
            align_whisper=True,
            script_doc=script_doc,
            voice_preset=eff_vp,
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
                preflight_prosody = evaluate_prosody_gates_on_audio(
                    p_dir,
                    audio_path=tmp_wav,
                    gates=("P1", "P2", "P3", "P4", "P5", "P6", "P8", "P10"),
                    run_asr=True,
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
        "schema_version": 7 if is_v7 else 6,
        "voice_preset": preset_name,
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


def finalize_and_verify_diorama_project(
    project_id: str,
    voice_preset: str | None = None,
    prosody_mode: str | None = None,
) -> dict[str, Any]:
    """Runs `assemble_diorama_project`, fail-fast Prosody P1-P10, DQ1-DQ12, R64, `autopsy`, `thumbnail`, KB sync, and `verify`."""
    from pipeline import thumbnail_studio
    from pipeline.config import NEURO_NEWS_HOLD_FROM_AUTO_QUEUE, NEURO_NEWS_STAGING_DIR
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
    ):
        (asm_dir / stale_qa).unlink(missing_ok=True)

    t_s = time.monotonic()
    asm_kwargs: dict[str, Any] = {"force_rebuild": True, "run_posthoc_qa": False}
    if voice_preset:
        asm_kwargs["voice_preset"] = voice_preset
    if prosody_mode:
        asm_kwargs["prosody_mode"] = prosody_mode
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
        prosody_rep = evaluate_prosody_gates(p_dir, run_asr=True, save_report=True)
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
                pad = min(0.08, 0.15 * (c_e - c_s))
                t0, t1 = c_s + pad, max(c_s + pad + 0.04, c_e - pad)
                for fr in (0.0, 0.25, 0.50, 0.75, 1.0):
                    union_fidxs.add(max(0, min(fc_u - 1, int(round((t0 + fr * (t1 - t0)) * fps_u)))))
            edl_doc = json.loads((asm_dir / "edit_decision_list.json").read_text(encoding="utf-8"))
            edl_cuts = edl_doc.get("cuts") or []
            sents_u, sdoc_u = load_diorama_script_sentences(p_dir)
            vp_u = json.loads((p_dir / "03_visuals" / "visual_plan.json").read_text(encoding="utf-8"))
            from pipeline.flow_prompt_builder import build_diorama_v6_prompts as _b_v6

            contract_u = compile_episode_qa_contract(vp_u, sents_u, _b_v6(vp_u, sents_u), script_doc=sdoc_u)
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
        except Exception:  # noqa: BLE001
            pass

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
    if not posthoc_rep.get("passed"):
        _write_stage_timings(asm_dir, project_id, timings, "QA_FAILED_POSTHOC", t_total0)
        _sync_full_project_manifest(p_dir, status="QA_FAILED")
        raise RuntimeError(
            f"PostHocSemanticQA (R64) flagged weak cuts for {project_id}: {posthoc_rep['summary']['weak_cut_indices']}"
        )

    # R65 Thumbnail Studio hard gate (TQ1-TQ7)
    t_s = time.monotonic()
    try:
        thumb_rep = thumbnail_studio.run(p_dir, force=False, strict=True)
        timings["thumbnail_sec"] = time.monotonic() - t_s
    except Exception as exc:
        timings["thumbnail_sec"] = time.monotonic() - t_s
        _write_stage_timings(asm_dir, project_id, timings, "QA_FAILED_THUMBNAIL", t_total0)
        _sync_full_project_manifest(p_dir, status="QA_FAILED")
        raise RuntimeError(f"Thumbnail Studio QA (R65 TQ1-TQ7) failed for {project_id}: {exc}") from exc

    t_s = time.monotonic()
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
        "cover_frame_sec": thumb_rep.get("cover_frame_sec"),
        "stage_timings_sec": {
            **{k: round(float(v), 2) for k, v in timings.items()},
            "verify_sec": verify_sec,
            "gdrive_copy_sec": gdrive_copy_sec,
            "total_sec": round(time.monotonic() - t_total0, 2),
        },
        "completed_mp4": str(completed_mp4),
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
        except Exception:  # noqa: BLE001
            pass

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
                    ("DQ9_zero_background_plaque", "plaque_cuts"),
                ):
                    for cid in (gates.get(g_key) or {}).get(field) or []:
                        regen_cuts.add(int(cid))
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
        except Exception:  # noqa: BLE001
            pass

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
        except Exception:  # noqa: BLE001
            pass

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
        except Exception:  # noqa: BLE001
            pass

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
    p_dir = Path(PROJECTS_DIR) / project_id
    comp_mp4 = COMPLETED_SHORTS_DIR / f"final_shorts_{project_id}.mp4"
    asm_dir = p_dir / "05_assembly"
    autopsy_path = asm_dir / "video_autopsy_report.json"
    dq_path = asm_dir / "dynamic_episode_qa_report.json"
    ph_path = asm_dir / "posthoc_semantic_qa_report.json"
    if not (comp_mp4.exists() and comp_mp4.stat().st_size > 5_000_000 and autopsy_path.exists() and dq_path.exists() and ph_path.exists()):
        return False
    try:
        arep = json.loads(autopsy_path.read_text(encoding="utf-8"))
        dqrep = json.loads(dq_path.read_text(encoding="utf-8"))
        phrep = json.loads(ph_path.read_text(encoding="utf-8"))
        return bool(arep.get("passed")) and bool(dqrep.get("passed")) and bool(phrep.get("passed"))
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
    Gear 3 + Gear 4 for ONE already-synced project: sharded Flow generation, then
    `finalize_and_verify_diorama_project` (assembly + P1-P10 + DQ1-DQ12 + R64 + autopsy + verify + KB sync)
    with up to `max_heal_rounds` auto-heal rounds (EDL-only rebuild or targeted clip regeneration).
    """
    import inspect

    flow_sig = inspect.signature(run_sharded_diorama_flow_generation)
    extra_flow_kwargs: dict[str, Any] = {}
    if engine_mode is not None and "engine_mode" in flow_sig.parameters:
        extra_flow_kwargs["engine_mode"] = engine_mode

    pid = str(project_id)
    p_dir = Path(PROJECTS_DIR) / pid
    vp_path = p_dir / "03_visuals" / "visual_plan.json"
    if vp_path.exists():
        from pipeline.config import is_porcelain_v7_plan
        from pipeline.porcelain_anchor_pack import ensure_porcelain_reference_pack

        vp_doc = json.loads(vp_path.read_text(encoding="utf-8"))
        if is_porcelain_v7_plan(vp_doc) and (
            vp_doc.get("reference_anchors")
            or any(isinstance(c, dict) and c.get("reference_image") for c in (vp_doc.get("clips") or []))
        ):
            ref_res = ensure_porcelain_reference_pack(
                p_dir,
                cdp_port=cdp_port,
                force=False,
                require_review=False,
            )
            if not ref_res.get("pre_generation_ready"):
                raise RuntimeError(
                    f"Porcelain reference pack failed pre_generation_ready for {pid}: "
                    f"regenerate={ref_res.get('regenerate_image_ids')} score={ref_res.get('reference_qa_score')}"
                )

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
    fin: dict[str, Any] | None = None
    last_exc: Exception | None = None
    fin_kwargs: dict[str, Any] = {}
    if voice_preset:
        fin_kwargs["voice_preset"] = voice_preset
    if prosody_mode:
        fin_kwargs["prosody_mode"] = prosody_mode
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
            clips_dir = Path(PROJECTS_DIR) / pid / "03_visuals" / "flow_native_clips"
            for c_idx in heal_clips:
                for pat in (f"clip_{c_idx:02d}.mp4", f"clip_{c_idx}.mp4"):
                    fp = clips_dir / pat
                    if fp.exists():
                        fp.unlink()
            asyncio.run(
                run_sharded_diorama_flow_generation(
                    project_id=pid,
                    clean_existing=False,
                    only_clips=heal_clips,
                    max_parallel_tabs=min(tabs, max(1, len(heal_clips))),
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
) -> dict[str, Any]:
    """
    One-shot production of ANY dossier-backed episode (not limited to DIORAMA_BATCH_20_SPECS):
    sync `research_dossiers/<slug>/diorama_v7_porcelain/` (or `diorama_v7_lowpoly/`) -> `projects/<project_id>/`,
    pre-Flow precheck (prompt-gate incl. R57-H2 cold-open, fact trace, paradox title, plaque lock, TTS clock),
    then Flow generation + assembly + full QA chain. Refuses to touch published projects.
    """
    p_dir = Path(PROJECTS_DIR) / project_id
    if (p_dir / "06_publish" / "upload_receipt.json").exists():
        raise RuntimeError(f"Refusing to (re)produce published project {project_id} (upload_receipt.json present)")
    spec: dict[str, Any] = {"index": 0, "wave": 0, "project_id": project_id, "slug": slug, "pillar": pillar}
    if voice_preset:
        spec["voice_preset"] = voice_preset
    if prosody_mode:
        spec["prosody_mode"] = prosody_mode
    t0 = time.time()
    pre = precheck_diorama_project(spec, run_tts_clock=True)
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
    if not force_regenerate and _is_already_completed(project_id):
        return {"passed": True, "mode": "already_completed", "project_id": project_id, "precheck": pre}
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
) -> dict[str, Any]:
    specs = select_batch_specs(wave=wave, project_ids=project_ids)
    if not specs:
        raise ValueError(f"No batch specs matched wave={wave!r}, project_ids={project_ids!r}")
    if voice_preset:
        specs = [{**sp, "voice_preset": voice_preset} for sp in specs]

    prechecks = []
    for sp in specs:
        rep = precheck_diorama_project(sp, run_tts_clock=True)
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
        else {"total_target": 20, "completed": {}, "in_progress": None, "errors": {}}
    )

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
        print(f"\n==================== [DioramaBatch #{sp['index']:02d}/20 | Wave {sp['wave']}] {pid} ====================")
        try:
            gen_kwargs: dict[str, Any] = {
                "tabs": tabs,
                "clean_existing": force_regenerate,
                "cdp_port": cdp_port,
                "engine_mode": engine_mode,
            }
            if voice_preset:
                gen_kwargs["voice_preset"] = voice_preset
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
