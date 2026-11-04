"""
ALL ABOUT BRAIN — Unpublished Dossier `diorama_v7_porcelain/` Compiler & 7-Pillar Rebalancer (Component 5).

Safely upgrades unpublished `diorama_v7_lowpoly/` drafts across `BCI_Shorts_Channel/research_dossiers/*`
into `diorama_v7_porcelain/{script.json, visual_plan.json, metadata.json}` (`R66`), rotating Anti-Clone
documentary transition phrases (`[US-06]`) in lockstep across `acts` and `sentences`, selecting `dynamic_us_v7`
ear-first prosody whenever word/clause/FK budgets fit (and preserving `dynamic_rush_v7` on 471-505w scripts so
runtime never overflows `179s`), generating independent 3-paragraph dossier-backed academic descriptions and
5-archetype `R60` titles, and emitting `BCI_Shorts_Channel/porcelain_rebalanced_queue.json` with true 7-pillar
window interleaving.

Never modifies frozen/published `diorama_01..26`, `phineas_gage_iron_rod`, or any project with an `upload_receipt.json`.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from collections import defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from pipeline.config import (
    CHANNEL_ROOT,
    DEFAULT_DIORAMA_VOICE_PRESET,
    DIORAMA_COLD_OPEN_S3_BANK,
    DIORAMA_CRISIS_BEAT_BANK,
    DIORAMA_EUREKA_REVEAL_BANK,
    DIORAMA_TAKEAWAY_BRIDGE_BANK,
    DIORAMA_US_SENTENCE_WORDS_MAX,
    DIORAMA_US_WORD_COUNT_MAX,
    DIORAMA_V7_MAX_FK_GRADE,
    DIORAMA_V7_PROSODY_MODE,
    DIORAMA_V7_SENTENCE_WORDS_MAX,
    DIORAMA_V7_US_PROSODY_MODE,
    DOSSIERS_DIR,
    PILLAR_DEFAULT_STYLE_MAP,
    PORCELAIN_V7_CAST_STYLE,
    PORCELAIN_V7_OPTICS_LOCK,
    PORCELAIN_V7_STYLE_PROFILE,
    PORCELAIN_V7_WORLD_STYLE,
    PRE_R66_FROZEN_PROJECT_PREFIXES,
    PROJECTS_DIR,
)
from pipeline.depiction_rules import normalize_porcelain_v7_brain_mode, normalize_porcelain_v7_grammar
from pipeline.diorama_batch_orchestrator import build_editorial_description_from_dossier
from pipeline.dynamic_episode_qa import (
    _ACTIVE_MOTION_VERBS_RE,
    _PORCELAIN_V7_CAST_RE,
    _WARDROBE_OR_HAT_RE,
)
from pipeline.flow_prompt_builder import _compose_porcelain_v7_clip_scene, count_words
from pipeline.prompt_quality_v5 import (
    _PRE_R65_ASSEMBLED_DOSSIERS,
    analyze_script,
    validate_takeaway_bridge_grammar,
)
from pipeline.publish import validate_diorama_paradox_title
from pipeline.studio.sanitize_scheduled_metadata import diversify_clone_title

PILLAR_PRIORITY_ORDER: tuple[str, ...] = (
    "brain_health",
    "brain_mysteries",
    "bci_tech",
    "brain_news",
    "brain_history",
    "bci_ethics",
    "brain_basics",
)

_PILLAR_ALIAS_MAP: dict[str, str] = {
    "bci_medicine": "brain_health",
    "everyday_brain": "brain_health",
    "neuro_history": "brain_history",
    "cognitive_tricks": "brain_mysteries",
    "cognitive_psychology": "brain_mysteries",
}

LOWPOLY_TOKEN_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    ("low-poly", "matte-white porcelain"),
    ("low poly", "matte-white porcelain"),
    ("faceted", "smooth sculptural"),
    ("pastel clay", "high-key architectural"),
    ("mint-teal", "pearl-aqua"),
    ("mint teal", "pearl-aqua"),
    ("origami", "clean museum"),
)

_PORCELAIN_BANNED_REGEX_REPLACEMENTS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bneon[\s\-]+green\b", re.IGNORECASE), "electric cyan-blue"),
    (re.compile(r"\blime[\s\-]+green\b", re.IGNORECASE), "electric cyan-blue"),
    (re.compile(r"\btoxic\s+green\b", re.IGNORECASE), "electric cyan-blue"),
    (re.compile(r"\bradioactive\b", re.IGNORECASE), "subsurface"),
    (re.compile(r"\bbioluminescent\b", re.IGNORECASE), "subsurface"),
    (re.compile(r"\bsparks?\b", re.IGNORECASE), "amber-gold pulse"),
    (re.compile(r"\bparticles?\b", re.IGNORECASE), "contained fiber pathways"),
    (re.compile(r"\b(?:mist|fog|haze|smoke)\b", re.IGNORECASE), "clear daylight"),
    (re.compile(r"\b(?:slime|ooze|viscous)\b", re.IGNORECASE), "smooth ceramic"),
)

_EDITORIAL_LEAD_PREFIXES: tuple[str, ...] = (
    "Clinical Case Briefing — ",
    "Experimental Chronicle — ",
    "Myth vs. Neural Mechanism — ",
    "Behavioral & Circuit Analysis — ",
)


def _normalize_canonical_pillar(raw_pillar: str, slug: str = "") -> str:
    cleaned = str(raw_pillar or "").strip().lower()
    if cleaned in PILLAR_DEFAULT_STYLE_MAP:
        return cleaned
    if cleaned in _PILLAR_ALIAS_MAP:
        return _PILLAR_ALIAS_MAP[cleaned]
    s_low = slug.lower()
    if any(k in s_low for k in ("bci", "implant", "prosthe", "electrode")):
        return "bci_tech"
    if any(k in s_low for k in ("sleep", "stress", "pain", "placebo", "depression", "trauma", "burnout", "habit")):
        return "brain_health"
    return "brain_basics"


def _is_frozen_or_published(
    project_id: str,
    *,
    slug: str = "",
    shorts_pids: list[str] | None = None,
) -> bool:
    if slug and slug in _PRE_R65_ASSEMBLED_DOSSIERS:
        return True
    all_pids = [str(project_id or "").strip(), *(str(x).strip() for x in (shorts_pids or []) if str(x).strip())]
    for pid in all_pids:
        if not pid:
            continue
        if pid.startswith("gage_diorama_"):
            return True
        if any(pid.startswith(pref) for pref in PRE_R66_FROZEN_PROJECT_PREFIXES):
            return True
        rcpt = Path(PROJECTS_DIR) / pid / "06_publish" / "upload_receipt.json"
        if rcpt.exists():
            try:
                from pipeline.studio.unschedule_retired_shorts import RETIRED_LOWPOLY_SCHEDULED_WHITELIST

                r_doc = json.loads(rcpt.read_text(encoding="utf-8"))
                if str(r_doc.get("video_id") or "") in set(RETIRED_LOWPOLY_SCHEDULED_WHITELIST.values()):
                    continue
            except Exception:
                pass
            return True
    return False


def _clean_porcelain_scene_text(text: str) -> str:
    out = str(text or "")
    for old_tok, new_tok in LOWPOLY_TOKEN_REPLACEMENTS:
        out = re.sub(re.escape(old_tok), new_tok, out, flags=re.IGNORECASE)
    for pat, repl in _PORCELAIN_BANNED_REGEX_REPLACEMENTS:
        out = pat.sub(repl, out)
    return " ".join(out.split())


def _enrich_porcelain_cast_clip(clip_spec: dict[str, Any]) -> dict[str, Any]:
    """Ensures every porcelain cast/hands clip satisfies R66 wardrobe + 2-beat physical motion gates."""
    g_name = str(clip_spec.get("grammar") or "")
    if g_name in ("porcelain_living_brain", "lowpoly_matte_brain", "frosted_crystal_specimen"):
        return clip_spec

    composed = _compose_porcelain_v7_clip_scene(clip_spec)
    needs_cast_lock = g_name in ("porcelain_hands_closeup", "porcelain_pov_hands") or bool(
        _PORCELAIN_V7_CAST_RE.search(composed)
    )
    if not needs_cast_lock:
        return clip_spec

    has_wardrobe = bool(_WARDROBE_OR_HAT_RE.search(composed))
    verb_count = len(_ACTIVE_MOTION_VERBS_RE.findall(composed))
    if has_wardrobe and verb_count >= 2:
        return clip_spec

    updated = dict(clip_spec)
    wardrobe_clause = "" if has_wardrobe else " in tailored linen sleeves and a woven cardigan"
    motion_clause = "" if verb_count >= 2 else " as porcelain hands reach forward and press cleanly into position"

    if str(updated.get("scene") or "").strip():
        base = str(updated["scene"]).strip().rstrip(".")
        updated["scene"] = _clean_porcelain_scene_text(f"{base}{wardrobe_clause}{motion_clause}.")
        return updated

    if g_name in ("porcelain_hands_closeup", "porcelain_pov_hands"):
        if not has_wardrobe:
            att = str(updated.get("attire_and_hands") or "tailored coat cuffs and matte-white porcelain hands").strip().rstrip(".")
            updated["attire_and_hands"] = f"{att} with rolled linen sleeves"
        if verb_count < 2:
            pa = str(updated.get("prop_action") or "the porcelain hands reach forward").strip().rstrip(".")
            updated["prop_action"] = f"{pa} and press the instrument into alignment"
        return updated

    if g_name == "porcelain_cutaway_section":
        target_key = "internal_mechanism" if updated.get("internal_mechanism") or not updated.get("kinetic_action") else "kinetic_action"
    elif g_name == "porcelain_literal_analogy":
        target_key = "comparison_action" if updated.get("comparison_action") or not updated.get("comparison_motion") else "comparison_motion"
    else:
        target_key = "action" if updated.get("action") or not updated.get("kinetic_action") else "kinetic_action"

    cur_val = str(updated.get(target_key) or "").strip().rstrip(".")
    updated[target_key] = _clean_porcelain_scene_text(f"{cur_val}{wardrobe_clause}{motion_clause}.").strip()
    return updated


def _sub_phrase_respecting_case_and_cap(
    sentence: str,
    pattern: str,
    bank: tuple[str, ...],
    slot_idx: int,
    max_words: int,
) -> str:
    m = re.search(pattern, sentence, flags=re.IGNORECASE)
    if not m:
        return " ".join(sentence.split())

    orig_wc = count_words(sentence)
    eff_cap = max(max_words, orig_wc)
    at_start = m.start() == 0 or bool(re.search(r"[.!?]\s*$", sentence[: m.start()]))

    for offset in range(len(bank)):
        raw_phrase = " ".join(bank[(slot_idx + offset) % len(bank)].split()).strip()
        if at_start and raw_phrase:
            phrase = raw_phrase[0].upper() + raw_phrase[1:]
        else:
            phrase = raw_phrase
        # Avoid trailing double punctuation when substituting inside a clause
        if m.end() < len(sentence) and sentence[m.end() : m.end() + 1] not in ("", " ") and phrase.endswith((".", ":", ",")):
            phrase = phrase.rstrip(".:,")
        elif m.end() < len(sentence) and phrase.endswith("."):
            phrase = phrase.rstrip(".")
        cand = " ".join((sentence[: m.start()] + phrase + sentence[m.end() :]).split())
        if count_words(cand) <= eff_cap and not validate_takeaway_bridge_grammar(cand):
            return cand
    return " ".join(sentence.split())


def _rotate_clone_phrases(
    sentences: list[str],
    slot_idx: int,
    case_label: str,
    max_words: int = DIORAMA_V7_SENTENCE_WORDS_MAX,
) -> list[str]:
    updated = [" ".join(str(s).split()) for s in sentences]
    s3_tmpl = DIORAMA_COLD_OPEN_S3_BANK[slot_idx % len(DIORAMA_COLD_OPEN_S3_BANK)]

    for i, s in enumerate(updated):
        low = s.lower()
        if i == 2 and "this is the true story of" in low:
            m = re.search(r"this is the true story of\s+(.+?)([.!?])?$", s, flags=re.IGNORECASE)
            subj = m.group(1).strip() if m else case_label
            for off in range(len(DIORAMA_COLD_OPEN_S3_BANK)):
                tmpl = DIORAMA_COLD_OPEN_S3_BANK[(slot_idx + off) % len(DIORAMA_COLD_OPEN_S3_BANK)]
                cand = tmpl.format(case=subj) if "{case}" in tmpl else f"{tmpl.rstrip('.')} {subj}."
                cand = " ".join(cand.split())
                if count_words(cand) <= max(max_words, count_words(s)):
                    updated[i] = cand
                    break
        elif "here is what went wrong" in low:
            updated[i] = _sub_phrase_respecting_case_and_cap(
                s,
                r"here is what went wrong\.?",
                DIORAMA_CRISIS_BEAT_BANK,
                slot_idx,
                max_words,
            )
        elif "the researchers were left completely stunned" in low:
            updated[i] = _sub_phrase_respecting_case_and_cap(
                s,
                r"the researchers were left completely stunned\.?",
                DIORAMA_EUREKA_REVEAL_BANK,
                slot_idx,
                max_words,
            )
        elif low.startswith(("which proves", "which is why")):
            updated[i] = _sub_phrase_respecting_case_and_cap(
                s,
                r"^(?:which proves(?:\s+that)?|which is why)",
                DIORAMA_TAKEAWAY_BRIDGE_BANK,
                slot_idx,
                max_words,
            )
    return updated


def _build_editorial_description(
    dossier: dict[str, Any],
    sources_doc: Any,
    slot_idx: int,
    *,
    project_id: str = "",
    pillar: str = "brain_basics",
    script_doc: dict[str, Any] | None = None,
) -> str:
    slug = str(dossier.get("slug") or "").strip()
    lead_prefix = _EDITORIAL_LEAD_PREFIXES[slot_idx % len(_EDITORIAL_LEAD_PREFIXES)]
    if slug and (Path(DOSSIERS_DIR) / slug).is_dir():
        desc, _, _ = build_editorial_description_from_dossier(
            project_id=project_id or f"diorama_{slug}",
            pillar=pillar,
            slug=slug,
            script_doc=script_doc or {},
        )
        if desc.startswith("Documentary case briefing on "):
            desc = lead_prefix + desc[len("Documentary case briefing on ") :]
        return desc

    pc = dossier.get("primary_case") or {}
    year = pc.get("year") or "classic"
    place = pc.get("place") or "a clinical neuroscience laboratory"
    title = pc.get("title") or dossier.get("topic") or slug or "this landmark study"
    people = [p.get("name") for p in (pc.get("people") or []) if isinstance(p, dict) and p.get("name")]
    lead_scientist = people[0] if people else "researchers"
    facts = [f.get("fact") for f in (dossier.get("core_facts") or []) if isinstance(f, dict) and f.get("fact")]
    core_summary = facts[1] if len(facts) > 1 else (facts[0] if facts else f"Investigators examined {title}.")
    takeaway = (dossier.get("everyday_hooks") or ["Understanding this neural circuit reshapes how we navigate daily life."])[0]
    doi_str = ""
    src_list = sources_doc.get("sources") if isinstance(sources_doc, dict) else (sources_doc if isinstance(sources_doc, list) else [])
    for s_item in src_list or []:
        if isinstance(s_item, dict) and s_item.get("doi"):
            doi_str = str(s_item["doi"]).strip()
            break
    opener = f"{lead_prefix}{lead_scientist} ({year}) at {place} investigated {title}."
    p2 = f"{core_summary} In everyday life, this mechanism explains: {takeaway}"
    p3 = (
        f"Primary Peer-Reviewed Source DOI: https://doi.org/{doi_str}\n"
        "AI Disclosure: Visual reenactments, 3D anatomical models, and narration in this documentary Short were produced with AI synthesis tools from verified peer-reviewed sources."
        if doi_str
        else "AI Disclosure: Visual reenactments, 3D anatomical models, and narration in this documentary Short were produced with AI synthesis tools from verified peer-reviewed sources."
    )
    return f"{opener}\n\n{p2}\n\n{p3}\n\n#Shorts #Neuroscience #BrainHealth #Psychology"


def convert_single_dossier_to_porcelain(dossier_dir: Path, slot_idx: int = 0, overwrite: bool = False) -> dict[str, Any]:
    d_file = dossier_dir / "dossier.json"
    if not d_file.exists():
        return {"slug": dossier_dir.name, "status": "skipped_missing_dossier"}
    dossier = json.loads(d_file.read_text(encoding="utf-8"))
    slug = str(dossier.get("slug") or dossier_dir.name)
    shorts_pids = [str(x) for x in (dossier.get("shorts_projects") or []) if str(x).strip()]
    primary_pid = shorts_pids[0] if shorts_pids else f"diorama_{slug}"

    out_dir = dossier_dir / "diorama_v7_porcelain"
    if _is_frozen_or_published(primary_pid, slug=slug, shorts_pids=shorts_pids):
        if overwrite and out_dir.exists() and slug in _PRE_R65_ASSEMBLED_DOSSIERS:
            shutil.rmtree(out_dir, ignore_errors=True)
        return {"slug": slug, "project_id": primary_pid, "status": "skipped_frozen_or_published"}

    canonical_pillar = _normalize_canonical_pillar(str(dossier.get("pillar") or "brain_basics"), slug=slug)
    if out_dir.exists() and (out_dir / "visual_plan.json").exists() and not overwrite:
        return {
            "slug": slug,
            "project_id": primary_pid,
            "pillar": canonical_pillar,
            "status": "already_migrated",
            "porcelain_dir": str(out_dir),
        }

    src_dir = dossier_dir / "diorama_v7_lowpoly"
    if not src_dir.exists() or not (src_dir / "visual_plan.json").exists():
        return {"slug": slug, "project_id": primary_pid, "status": "skipped_no_v7_draft"}

    out_dir.mkdir(parents=True, exist_ok=True)
    vp = json.loads((src_dir / "visual_plan.json").read_text(encoding="utf-8"))
    sc = json.loads((src_dir / "script.json").read_text(encoding="utf-8")) if (src_dir / "script.json").exists() else {}
    md = json.loads((src_dir / "metadata.json").read_text(encoding="utf-8")) if (src_dir / "metadata.json").exists() else {}
    sources_doc = (
        json.loads((dossier_dir / "01_sources.json").read_text(encoding="utf-8"))
        if (dossier_dir / "01_sources.json").exists()
        else {}
    )

    vp["style_profile"] = PORCELAIN_V7_STYLE_PROFILE
    vp["shader_style"] = PORCELAIN_V7_WORLD_STYLE
    vp["cast_style"] = PORCELAIN_V7_CAST_STYLE
    vp["optics_lock"] = PORCELAIN_V7_OPTICS_LOCK

    new_clips: list[dict[str, Any]] = []
    for clip in vp.get("clips") or []:
        if not isinstance(clip, dict):
            continue
        c_copy = dict(clip)
        c_copy["style_profile"] = PORCELAIN_V7_STYLE_PROFILE
        c_copy["grammar"] = normalize_porcelain_v7_grammar(str(c_copy.get("grammar") or "porcelain_fullbleed_world"))
        if c_copy.get("brain_mode"):
            c_copy["brain_mode"] = normalize_porcelain_v7_brain_mode(str(c_copy["brain_mode"]))
        for txt_k in (
            "scene",
            "subject_action",
            "environment_backdrop",
            "environment",
            "action",
            "kinetic_action",
            "attire_and_hands",
            "prop_action",
            "consequence",
            "structure",
            "internal_mechanism",
            "analogy_world",
            "analogy_scene",
            "comparison_action",
            "comparison_motion",
            "brain_scene",
            "maquette_scene",
        ):
            if c_copy.get(txt_k):
                c_copy[txt_k] = _clean_porcelain_scene_text(str(c_copy[txt_k]))
        if "lowpoly" in str(c_copy.get("reference_image") or "").lower():
            c_copy.pop("reference_image", None)
        c_copy = _enrich_porcelain_cast_clip(c_copy)
        new_clips.append(c_copy)
    vp["clips"] = new_clips

    act_lengths: list[int] = []
    if isinstance(sc.get("acts"), list) and sc["acts"]:
        raw_sents: list[str] = []
        for act_obj in sc["acts"]:
            a_sents = [str(x).strip() for x in (act_obj.get("sentences") or []) if str(x).strip()]
            act_lengths.append(len(a_sents))
            raw_sents.extend(a_sents)
    else:
        raw_sents = [str(x).strip() for x in (sc.get("sentences") or []) if str(x).strip()]

    sents = list(raw_sents)
    if sents:
        case_lbl = str((dossier.get("primary_case") or {}).get("title") or slug.replace("_", " "))
        sents = _rotate_clone_phrases(
            sents,
            slot_idx=slot_idx,
            case_label=case_lbl,
            max_words=DIORAMA_V7_SENTENCE_WORDS_MAX,
        )
        sc["sentences"] = sents
        if isinstance(sc.get("acts"), list) and sum(act_lengths) == len(sents):
            cursor = 0
            for act_obj, a_len in zip(sc["acts"], act_lengths):
                act_obj["sentences"] = sents[cursor : cursor + a_len]
                cursor += a_len
        sc["full_script"] = " ".join(sents)
        sc["word_count"] = sum(count_words(s) for s in sents)

    total_wc = sum(count_words(s) for s in sents) if sents else 0
    max_sw = max((count_words(s) for s in sents), default=0)
    fk_grade = analyze_script(sents)["script_fk_grade"] if sents else 0.0
    fits_us_v7 = (
        total_wc <= DIORAMA_US_WORD_COUNT_MAX
        and max_sw <= DIORAMA_US_SENTENCE_WORDS_MAX
        and fk_grade <= DIORAMA_V7_MAX_FK_GRADE
    )

    sc["pillar"] = canonical_pillar
    sc["style_profile"] = PORCELAIN_V7_STYLE_PROFILE
    sc["prosody_mode"] = DIORAMA_V7_US_PROSODY_MODE
    sc["voice_preset"] = DEFAULT_DIORAMA_VOICE_PRESET
    sc["us_anti_clone_v7"] = True

    md_title = str(md.get("title") or "").strip()
    sc_title = str(sc.get("title") or "").strip()
    title_pool = [
        diversify_clone_title(t, index_seed=slot_idx)
        for t in (md_title, sc_title)
        if t
    ] + [t for t in (sc_title, md_title) if t]
    chosen_title = ""
    for cand_t in title_pool:
        if not validate_diorama_paradox_title(cand_t):
            chosen_title = cand_t
            break
    if not chosen_title and title_pool:
        chosen_title = title_pool[0]
    if chosen_title:
        sc["title"] = chosen_title
        md["title"] = chosen_title

    desc_str, hashtags, doi_val = (
        build_editorial_description_from_dossier(
            project_id=primary_pid,
            pillar=canonical_pillar,
            slug=slug,
            script_doc=sc,
        )
        if (dossier_dir / "01_sources.json").exists()
        else (
            _build_editorial_description(dossier, sources_doc, slot_idx=slot_idx, project_id=primary_pid, pillar=canonical_pillar, script_doc=sc),
            ["#Shorts", "#Neuroscience", "#BrainHealth", "#Psychology"],
            str(sc.get("doi") or ""),
        )
    )
    lead_prefix = _EDITORIAL_LEAD_PREFIXES[slot_idx % len(_EDITORIAL_LEAD_PREFIXES)]
    if desc_str.startswith("Documentary case briefing on "):
        desc_str = lead_prefix + desc_str[len("Documentary case briefing on ") :]

    md["pillar"] = canonical_pillar
    md["style_profile"] = PORCELAIN_V7_STYLE_PROFILE
    md["voice_preset"] = DEFAULT_DIORAMA_VOICE_PRESET
    md["prosody_mode"] = DIORAMA_V7_US_PROSODY_MODE
    if doi_val:
        md["doi"] = doi_val
    md["ai_disclosure"] = True
    md["hashtags"] = hashtags
    md["description"] = desc_str

    (out_dir / "visual_plan.json").write_text(json.dumps(vp, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (out_dir / "script.json").write_text(json.dumps(sc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (out_dir / "metadata.json").write_text(json.dumps(md, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    return {
        "slug": slug,
        "project_id": primary_pid,
        "pillar": canonical_pillar,
        "prosody_mode": sc["prosody_mode"],
        "status": "migrated",
        "porcelain_dir": str(out_dir),
    }


def rebalance_pillar_queue(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Reorders candidate episodes across canonical 7 pillars so consecutive 4-slot windows maximize
    distinct pillars while prioritizing high-US-conversion pillars (`brain_health`, `brain_mysteries`,
    `bci_tech`, `brain_news`, `brain_history`, `bci_ethics`, `brain_basics`) and preventing end-of-queue clumping.
    """
    buckets: dict[str, deque[dict[str, Any]]] = defaultdict(deque)
    for it in sorted(items, key=lambda x: (str(x.get("project_id") or ""), str(x.get("slug") or ""))):
        pil = _normalize_canonical_pillar(str(it.get("pillar") or "brain_basics"), slug=str(it.get("slug") or ""))
        norm_it = dict(it, pillar=pil)
        buckets[pil].append(norm_it)

    priority_rank = {p: idx for idx, p in enumerate(PILLAR_PRIORITY_ORDER)}
    ordered: list[dict[str, Any]] = []

    while any(buckets.values()):
        non_empty = [p for p, q in buckets.items() if q]
        last_pillar = ordered[-1]["pillar"] if ordered else None
        recent_3 = {x["pillar"] for x in ordered[-3:]}
        # First 6 pilot slots maximize distinct priority pillars; subsequent slots balance window diversity & remaining depth
        candidates = [p for p in non_empty if p != last_pillar] or non_empty
        if len(ordered) < 6:
            fresh = [p for p in candidates if p not in {x["pillar"] for x in ordered}]
            pool = fresh or candidates
            pool.sort(key=lambda p: (priority_rank.get(p, 99), -len(buckets[p])))
        else:
            pool = list(candidates)
            pool.sort(
                key=lambda p: (
                    1 if p in recent_3 else 0,
                    -len(buckets[p]),
                    priority_rank.get(p, 99),
                )
            )
        chosen_p = pool[0]
        entry = dict(buckets[chosen_p].popleft())
        entry["queue_rank"] = len(ordered) + 1
        ordered.append(entry)
    return ordered


def migrate_all_unpublished_dossiers(overwrite: bool = False) -> dict[str, Any]:
    from concurrent.futures import ThreadPoolExecutor

    d_root = Path(DOSSIERS_DIR)
    migrated_items: list[dict[str, Any]] = []
    skipped_items: list[dict[str, Any]] = []

    dirs = sorted(p for p in d_root.iterdir() if p.is_dir())

    def _run_one(pair: tuple[int, Path]) -> tuple[int, Path, dict[str, Any]]:
        i, p = pair
        return i, p, convert_single_dossier_to_porcelain(p, slot_idx=i, overwrite=overwrite)

    with ThreadPoolExecutor(max_workers=8) as pool:
        for idx, d_dir, res in pool.map(_run_one, enumerate(dirs)):
            print(f"[{idx + 1}/{len(dirs)}] {d_dir.name}: {res.get('status')}", flush=True)
            if res.get("status") in ("migrated", "already_migrated"):
                migrated_items.append(res)
            else:
                skipped_items.append(res)

    rebalanced = rebalance_pillar_queue(migrated_items)
    pillar_counts: dict[str, int] = defaultdict(int)
    for it in rebalanced:
        pillar_counts[str(it.get("pillar") or "brain_basics")] += 1

    out_queue_path = Path(CHANNEL_ROOT) / "porcelain_rebalanced_queue.json"
    payload = {
        "schema": "porcelain_rebalanced_queue_v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_ready_episodes": len(rebalanced),
        "skipped_count": len(skipped_items),
        "pillar_distribution": dict(pillar_counts),
        "pilot_top_6": rebalanced[:6],
        "queue": rebalanced,
    }
    out_queue_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return payload


def main() -> None:
    ap = argparse.ArgumentParser(description="Migrate unpublished dossiers to porcelain_cinematic_v7 & rebalance 7-pillar queue")
    ap.add_argument("--overwrite", action="store_true", default=False, help="Overwrite existing diorama_v7_porcelain drafts")
    args = ap.parse_args()
    rep = migrate_all_unpublished_dossiers(overwrite=bool(args.overwrite))
    print(
        json.dumps(
            {
                "total_ready_episodes": rep["total_ready_episodes"],
                "skipped_count": rep["skipped_count"],
                "pillar_distribution": rep["pillar_distribution"],
                "pilot_top_6": [(x["project_id"], x["pillar"]) for x in rep["pilot_top_6"]],
            },
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
