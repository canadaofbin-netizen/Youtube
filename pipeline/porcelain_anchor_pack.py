"""
ALL ABOUT BRAIN — Dual-Track (`R67` + `R66-Anchor`) Porcelain Reference Contract Compiler & Pack Orchestrator.

Bridges Research Dossiers (`03_visual_reference.json`, `04_media_refs.json`, `06_brain_link.json`) to
`porcelain_cinematic_v7` reference-conditioned generation across both Track A (`R67` archival film
reenactment) and Track B (`R66-Anchor` scene-bible room & cast pack):

  1. `populate_porcelain_reference_contract(plan, dossier_dir)`:
       - Deterministically populates `reenactment_track` (`"track_a"` or `"track_b"`), `default_location_id`,
         `cast` (all recurring human roles with role-classified period wardrobe, closed matte-white footwear,
         zero leaked investigator/patient personal names, zero animal sculptures on human roles, and smooth
         featureless matte-white oval heads), `real_environment`, `environment_props` (normalized & plaque-free),
         `require_scene_state_ledger: True`, and `strict_room_continuity: True`.
       - Repairs sequential `scene_state` room-occupancy transitions (`protocol_phase_jump: True` where needed)
         so `validate_scene_state_continuity(plan)` passes with zero issues.
       - Synthesizes `3–5` curated `reference_anchors` (`generation_order: 3`, conditioned on `ref_env_master`
         and `ref_cast_<role>`, mapped to `S01..S0N` shots on Track A or `LOC_<location_id>` on Track B) so
         `build_reference_image_specs` produces `6–9` total `9:16` reference specs.
       - Applies selective room/brain anchor binding (`PORCELAIN_ANCHOR_MIN_CLIP_RATIO..PORCELAIN_ANCHOR_MAX_CLIP_RATIO`):
           * `porcelain_fullbleed_world` / `porcelain_cutaway_section` -> matching `(location_id, present_cast_start)` room anchor
           * `porcelain_living_brain` (non-micro) -> `03_visuals/reference_images/ref_brain_master.png`
           * `porcelain_hands_closeup` / `porcelain_pov_hands` / `bounded_micro_channel` /
             `porcelain_literal_analogy` / `porcelain_data_sculpture` / `outro` -> unanchored (`None`) so macro
             hand/prop closeups are NEVER Frame-0 locked to wide full-body standing portraits.
       - On Track A (`R67`), maps every non-brain/non-outro lab clip's `source_shot_id` across `S01..S0N`
         (`100% >= REENACT_COMPOSITION_MATCH_MIN` `RQ5` blocking alignment).

  2. `ensure_porcelain_reference_pack(...)`:
       - Stages quarantined `/tmp/aab_reenact/<slug>` `S01..S0N` structural guides for Track A when needed,
         generates missing `9:16` reference PNGs in `0-credit` Google Flow `Image` mode (`Nano Banana 2.1`,
         `x4` batch per prompt, auto-selecting the top `Q1..Q7` candidate) in strict `1 -> 2 -> 3` order,
         registers `"flow_image_generation"` provenance, guarantees `/tmp/aab_reenact` purge in `finally:`,
         and verifies `inspect_reference_image_pack(...)["pre_generation_ready"] == True`.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from pipeline.config import (
    BRAIN_SETTINGS,
    CHANNEL_ROOT,
    DEFAULT_CDP_PORT,
    DEFAULT_REENACT_IMAGE_BACKEND,
    DOSSIERS_DIR,
    EXPRESSIVE_25D_V8_STYLE_PROFILE,
    EXPRESSIVE_V8_CAMEO_SHEET_FILENAME,
    EXPRESSIVE_V8_CAST_SHEET_FILENAMES,
    EXPRESSIVE_V8_REFS_DIRNAME,
    EXPRESSIVE_V8_SPECIES_SHEET_FILENAME,
    EXPRESSIVE_V8_VISUAL_GRAMMARS,
    FLOW_ZERO_CREDIT_IMAGE_BATCH_COUNT,
    MIN_REF_IMAGES_PER_PROJECT,
    PROJECTS_DIR,
    PROMPT_SCHEMA_VERSION_V8,
    REF_IMAGES_DIRNAME,
    REENACT_EDL_FILENAME,
    REENACT_QUARANTINE_ROOT,
    SHORTS_EXPRESSIVE_V8_PROFILE,
    is_expressive_v8_plan,
    is_porcelain_v7_plan,
)

_PLAQUE_SANITIZE_SUBS: tuple[tuple[re.Pattern[str], str], ...] = (
    # Strip quoted display titles / chart headings while preserving apostrophes inside words (e.g. subject's, 1930's)
    (re.compile(r'"[^"]{2,120}"'), ""),
    (re.compile(r"(?<![A-Za-z0-9])'[^']{2,120}'(?![A-Za-z0-9])"), ""),
    # Strip parenthetical numeric/percentage chart captions (e.g. "(86% vs 14%)")
    (re.compile(r"\([^()]*\d+\s*%[^()]*\)"), ""),
    (re.compile(r"\bledgers\b", re.IGNORECASE), "bound notebooks"),
    (re.compile(r"(?<!bound )\bledger\b", re.IGNORECASE), "bound notebook"),
    (re.compile(r"(?<!unmarked brushed-metal )\b(?:plaques|nameplates|placards|banners)\b", re.IGNORECASE), "unmarked brushed-metal plates"),
    (re.compile(r"(?<!unmarked brushed-metal )\b(?:plaque|nameplate|placard|banner)\b", re.IGNORECASE), "unmarked brushed-metal plate"),
    (re.compile(r"(?<!smooth unmarked slate wall )\b(?:chalkboards|blackboards|whiteboards|signboards)\b", re.IGNORECASE), "smooth unmarked slate wall panels"),
    (re.compile(r"(?<!smooth unmarked slate wall )\b(?:chalkboard|blackboard|whiteboard|signboard)\b", re.IGNORECASE), "smooth unmarked slate wall panel"),
    (re.compile(r"(?<!unmarked paper )\b(?:newspapers|headlines)\b", re.IGNORECASE), "unmarked paper sheets"),
    (re.compile(r"(?<!unmarked paper )\b(?:newspaper|headline)\b", re.IGNORECASE), "unmarked paper sheet"),
    (re.compile(r"(?<!unmarked paper )\b(?:charts|graphs)\b", re.IGNORECASE), "unmarked paper sheets"),
    (re.compile(r"(?<!unmarked paper )\b(?:chart|graph)\b", re.IGNORECASE), "unmarked paper sheet"),
    (re.compile(r"(?<!unmarked wall )\b(?:posters)\b", re.IGNORECASE), "unmarked wall panels"),
    (re.compile(r"(?<!unmarked wall )\b(?:poster)\b", re.IGNORECASE), "unmarked wall panel"),
    (re.compile(r"(?<!unmarked anatomical relief )\b(?:diagrams)\b", re.IGNORECASE), "unmarked anatomical relief models"),
    (re.compile(r"(?<!unmarked anatomical relief )\b(?:diagram)\b", re.IGNORECASE), "unmarked anatomical relief model"),
    (re.compile(r"(?<!blank unmarked matte )\b(?:flashcards|stimulus cards|playing cards|index cards|cue cards)\b", re.IGNORECASE), "blank unmarked matte cards"),
    (re.compile(r"(?<!blank unmarked matte )\b(?:flashcard|stimulus card|playing card|index card|cue card)\b", re.IGNORECASE), "blank unmarked matte card"),
    (re.compile(r"(?<!blank matte )(?<!blank unmarked matte )\bcards\b", re.IGNORECASE), "blank matte cards"),
    (re.compile(r"(?<!blank matte )(?<!blank unmarked matte )\bcard\b", re.IGNORECASE), "blank matte card"),
    (re.compile(r"(?<!unmarked cloth )\btextbooks\b", re.IGNORECASE), "unmarked cloth volumes"),
    (re.compile(r"(?<!unmarked cloth )\btextbook\b", re.IGNORECASE), "unmarked cloth volume"),
    (re.compile(r"\b(?:inscribed|engraved|labelled|labeled|printed|handwritten|titled)\b", re.IGNORECASE), "unmarked"),
    (re.compile(r"\bnumerals\b", re.IGNORECASE), "tick marks"),
    (re.compile(r"\bnumeral\b", re.IGNORECASE), "tick mark"),
    (re.compile(r"\b(?:stopwatch|chronometer|pocket watch|wristwatch|hourglass|metronome)\b", re.IGNORECASE), "brushed-metal instrument"),
    (re.compile(r"\bwater tumbler\b", re.IGNORECASE), "clear glass vessel"),
    (re.compile(r"\bbeam scale\b", re.IGNORECASE), "brass laboratory stand"),
    (re.compile(r"\blow-?poly\b", re.IGNORECASE), "smooth architectural"),
    (re.compile(r"\b(?:faceted|origami|papercraft)\b", re.IGNORECASE), "smooth matte"),
    (re.compile(r"\b(?:human face|human faces|flesh|skin tone|eyebrows|eyelashes)\b", re.IGNORECASE), "smooth matte-white porcelain"),
)

_DEFAULT_ROLE_WARDROBE: dict[str, str] = {
    "subject": "adult participant in a muted slate-blue woven cardigan over a crisp pale linen shirt, dark tailored trousers, and closed matte-white leather shoes",
    "researcher": "clinical investigator in a tailored crisp white laboratory coat over a charcoal wool waistcoat, dark trousers, and closed matte-white leather shoes",
    "clinician": "attending neurologist in a crisp white clinical coat over a navy woven shirt, tailored trousers, and closed matte-white leather shoes",
    "doctor": "attending physician in a tailored dark charcoal wool frock coat over a crisp pale collar shirt, dark trousers, and closed matte-white leather shoes",
    "mother": "adult caregiver in a sleeveless dark woven summer top, mid-length pleated skirt, and closed matte-white flats",
    "stranger": "visiting researcher in a light short-sleeved woven blouse, tailored pleated skirt, and closed matte-white flats",
    "assistant": "laboratory assistant in a buttoned light-gray cotton utility jacket, dark trousers, and closed matte-white leather shoes",
    "experimenter": "lead experimenter in a tailored light-gray laboratory coat over a crisp white shirt, dark tie, dark trousers, and closed matte-white leather shoes",
    "child": "young child in a pale cotton romper with neat woven shorts and closed matte-white canvas shoes",
}

_CRANIUM_CLAUSE = "with a completely smooth featureless solid matte-white egg-shaped oval head"
_FOOTWEAR_RE = re.compile(
    r"\b(?:shoe|shoes|boot|boots|loafer|loafers|oxford|oxfords|sneaker|sneakers|sandal|sandals|slipper|slippers|footwear|heels|flats|brogues|clogs|fins|wetsuit)\b",
    re.IGNORECASE,
)
_ANIMAL_CLAUSE_RE = re.compile(
    r"\b(?:animal\s+subject|porcelain\s+(?:dog|dogs|cat|cats|pigeon|pigeons|rat|rats|mouse|mice|monkey|monkeys|macaque|aplysia|sea\s+slug|rabbit|octopus|bird|birds))\b",
    re.IGNORECASE,
)
_INVESTIGATOR_LEAD_RE = re.compile(
    r"\b(?:investigator|investigators|researcher|researchers|experimenter|experimenters|physician|physicians|doctor|doctors|dr\.|neurologist|neurologists|clinician|clinicians|professor|professors|scientist|scientists|surgeon|psychiatrist|teacher|teachers|observer|observers|interviewer|technician|attending|guard|guards|nurse|nurses|staff|examiner)\b",
    re.IGNORECASE,
)
_INVESTIGATOR_GARMENT_RE = re.compile(
    r"\b(?:laboratory\s+coat|lab\s+coat|frock\s+coat|clinical\s+coat|surgical\s+coat|white\s+coat|medical\s+coat)\b",
    re.IGNORECASE,
)
_PARTICIPANT_LEAD_RE = re.compile(
    r"\b(?:patient|patients|participant|participants|subject|subjects|volunteer|volunteers|pseudopatient|pseudopatients|child|children|boy|boys|girl|girls|infant|toddler|student|students|schoolboy|schoolboys|schoolgirl|undergraduate|undergraduates|prisoner|prisoners|hiker|cellist|musician|driver|drivers|diver|divers|woman|women|man|men|mademoiselle|monsieur|foreman|clerk|monk|monks|meditator|juggler|gamer|reader|speaker|bystander|confederate|mother|caregiver| amputee|veteran|stroke\s+patient)\b",
    re.IGNORECASE,
)

_ANCHOR_CAMERA_VARIANTS: tuple[str, ...] = (
    "Wide high-key architectural establishing three-quarter view across",
    "Medium side-angle tripod composition across",
    "Medium-wide opposite-corner diagonal architectural view inside",
    "Three-quarter workbench-level documentary framing inside",
    "Wide symmetrical gallery-lit room composition inside",
)


def sanitize_porcelain_contract_text(text: str) -> str:
    s = re.sub(r"\s+", " ", str(text or "")).strip()
    if not s:
        return ""
    for pat, repl in _PLAQUE_SANITIZE_SUBS:
        s = pat.sub(repl, s)
    s = re.sub(r"\bunmarked\s+unmarked\b", "unmarked", s, flags=re.IGNORECASE)
    s = re.sub(r"\s+([,.;:])", r"\1", s)
    s = re.sub(r"\s+", " ", s).strip(" ,;:-")
    return s


def _normalize_prop_entry(raw_prop: Any) -> dict[str, str] | None:
    if isinstance(raw_prop, str):
        clean_p = sanitize_porcelain_contract_text(raw_prop)
        return {"name": clean_p, "period_detail": "", "physical_behavior": ""} if clean_p else None
    if not isinstance(raw_prop, dict):
        return None
    name = sanitize_porcelain_contract_text(raw_prop.get("name") or raw_prop.get("item") or "")
    detail = sanitize_porcelain_contract_text(raw_prop.get("period_detail") or raw_prop.get("look") or "")
    behavior = sanitize_porcelain_contract_text(raw_prop.get("physical_behavior") or "")
    if not name and not detail:
        return None
    return {"name": name or detail, "period_detail": detail, "physical_behavior": behavior}


def _extract_iconic_scene_from_dossier(dossier_dir: Path | None) -> dict[str, Any]:
    if dossier_dir is None or not Path(dossier_dir).exists():
        return {}
    vis_ref_path = Path(dossier_dir) / "03_visual_reference.json"
    if not vis_ref_path.exists():
        return {}
    try:
        doc = json.loads(vis_ref_path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    scenes = doc.get("scenes") or []
    iconic = [s for s in scenes if isinstance(s, dict) and s.get("iconic")]
    if iconic:
        return iconic[0]
    return scenes[0] if (scenes and isinstance(scenes[0], dict)) else {}


def _classify_wardrobe_clause(clause: str) -> str:
    c_str = str(clause or "").strip()
    if not c_str:
        return "empty"
    if _ANIMAL_CLAUSE_RE.search(c_str):
        return "animal"
    lead = c_str.split(" in ", 1)[0] if " in " in c_str.lower() else c_str[:70]
    has_inv_lead = bool(_INVESTIGATOR_LEAD_RE.search(lead))
    has_part_lead = bool(_PARTICIPANT_LEAD_RE.search(lead))
    if has_inv_lead and not has_part_lead:
        return "investigator"
    if has_part_lead and not has_inv_lead:
        return "participant"
    if _INVESTIGATOR_GARMENT_RE.search(c_str) and not has_part_lead:
        return "investigator"
    if has_part_lead:
        return "participant"
    if has_inv_lead:
        return "investigator"
    return "unknown"


def _anonymize_and_lock_wardrobe_clause(clause: str, role: str) -> str:
    """
    Replaces any named historical person lead (`Dr. Jules Cotard in ...`, `Mademoiselle X in ...`,
    `Investigators Shepard and Metzler in ...`) with an anonymous role descriptor while preserving
    the exact period garment specification, closed matte-white footwear, and smooth oval head lock.
    """
    raw = str(clause or "").strip()
    # Strip trailing cranium boilerplate before re-appending canonically
    raw = re.sub(
        r"\s*with\s+a\s+completely\s+smooth\s+featureless\s+solid\s+matte-white\s+egg-shaped\s+oval\s+head\.?$",
        "",
        raw,
        flags=re.IGNORECASE,
    ).strip(" ,;.")

    m_in = re.match(r"^(.{2,85}?)\s+in\s+(.+)$", raw, flags=re.IGNORECASE)
    if m_in:
        lead_raw = m_in.group(1).strip()
        garment_raw = m_in.group(2).strip()
        lead_low = lead_raw.lower()
        if role in ("researcher", "clinician", "doctor", "experimenter", "assistant", "stranger"):
            if "physician" in lead_low or "dr." in lead_low or "doctor" in lead_low or role == "doctor":
                anon_lead = "attending physician"
            elif "neurologist" in lead_low or "clinician" in lead_low or role == "clinician":
                anon_lead = "attending neurologist"
            elif "teacher" in lead_low:
                anon_lead = "classroom instructor"
            elif "guard" in lead_low:
                anon_lead = "uniformed corridor officer"
            elif "assistant" in lead_low or role == "assistant":
                anon_lead = "laboratory assistant"
            else:
                anon_lead = "clinical investigator"
        else:
            if any(k in lead_low for k in ("child", "boy", "girl", "schoolboy", "schoolgirl", "toddler", "infant", "preschool")) or role == "child":
                anon_lead = "young child participant"
            elif any(k in lead_low for k in ("mademoiselle", "woman", "female", "mother", "wife", "lady", "sister")):
                anon_lead = "adult female participant"
            elif "patient" in lead_low:
                anon_lead = "clinical patient"
            elif "student" in lead_low or "undergraduate" in lead_low:
                anon_lead = "adult student participant"
            else:
                anon_lead = "adult participant"
        garment_clean = sanitize_porcelain_contract_text(garment_raw)
        clean_cand = f"{anon_lead} in {garment_clean}"
    else:
        clean_cand = sanitize_porcelain_contract_text(raw)

    if not clean_cand or len(clean_cand) < 16 or _ANIMAL_CLAUSE_RE.search(clean_cand):
        clean_cand = _DEFAULT_ROLE_WARDROBE.get(
            role,
            f"articulated studio figure ({role.replace('_', ' ')}) in muted period woven attire and closed matte-white leather shoes",
        )

    if not _FOOTWEAR_RE.search(clean_cand):
        clean_cand = f"{clean_cand} and closed matte-white leather shoes"
    if "egg-shaped oval head" not in clean_cand.lower() and "smooth featureless" not in clean_cand.lower():
        clean_cand = f"{clean_cand} {_CRANIUM_CLAUSE}"
    return clean_cand


def _extract_animal_props_from_wardrobe(iconic_scene: dict[str, Any]) -> list[str]:
    wardrobe_raw = iconic_scene.get("wardrobe")
    if not isinstance(wardrobe_raw, str) or not wardrobe_raw.strip():
        return []
    out: list[str] = []
    for part in wardrobe_raw.split(";"):
        p = part.strip()
        if p and _ANIMAL_CLAUSE_RE.search(p):
            cleaned = sanitize_porcelain_contract_text(
                re.sub(r"^animal\s+subject\s+(?:strictly\s+)?rendered\s+as\s+", "", p, flags=re.IGNORECASE)
            )
            if cleaned:
                out.append(cleaned)
    return out


def _is_valid_existing_role_wardrobe(role: str, val: str) -> bool:
    s = str(val or "").strip()
    if len(s) < 18:
        return False
    if _ANIMAL_CLAUSE_RE.search(s):
        return False
    if re.search(r"\b(?:Dr\.|Mademoiselle|Monsieur|Investigators\s+[A-Z]|Professor\s+[A-Z])\b", s):
        return False
    cls = _classify_wardrobe_clause(s)
    is_inv_role = role in ("researcher", "clinician", "doctor", "experimenter", "assistant")
    if is_inv_role and cls == "participant":
        return False
    if role in ("subject", "child", "patient") and cls == "investigator":
        return False
    return True


def _infer_wardrobe_for_role(role: str, iconic_scene: dict[str, Any], clips: list[dict[str, Any]]) -> str:
    wardrobe_raw = iconic_scene.get("wardrobe")
    is_inv_role = role in ("researcher", "clinician", "doctor", "experimenter", "assistant")
    target_cls = "investigator" if is_inv_role else "participant"
    cand = ""

    if isinstance(wardrobe_raw, dict):
        for k, v in wardrobe_raw.items():
            kl = str(k).lower()
            v_str = str(v or "").strip()
            if not v_str or _ANIMAL_CLAUSE_RE.search(v_str):
                continue
            if role == kl or (
                not is_inv_role and any(t in kl for t in ("patient", "subject", "participant", "volunteer", "child", "student", "foreman", "mother"))
            ) or (
                is_inv_role and any(t in kl for t in ("researcher", "doctor", "physician", "clinician", "experimenter", "neurologist", "scientist", "assistant", "teacher"))
            ):
                cand = v_str
                break
    elif isinstance(wardrobe_raw, str) and wardrobe_raw.strip():
        # Split strictly on semicolons so abbreviations like 'St. Louis' or 'Dr. Cotard' are never broken
        clauses = [p.strip() for p in wardrobe_raw.split(";") if p.strip()]
        typed = [(c_txt, _classify_wardrobe_clause(c_txt)) for c_txt in clauses]
        non_animal = [(c_txt, c_cls) for c_txt, c_cls in typed if c_cls != "animal"]
        for c_txt, c_cls in non_animal:
            if c_cls == target_cls:
                cand = c_txt
                break
        if not cand:
            unknowns = [c_txt for c_txt, c_cls in non_animal if c_cls == "unknown"]
            if unknowns:
                cand = unknowns[0] if not is_inv_role else unknowns[-1]

    if not cand:
        role_regex = (
            r"(?:patient|participant|volunteer|subject|man|woman|student|child)\s+in\s+(a\s+[a-z0-9 ,-]+?(?:cardigan|coat|shirt|jacket|sweater|blouse|smock|suit|gown|vest|waistcoat|romper|tunic|dress))"
            if not is_inv_role
            else r"(?:researcher|neurologist|physician|clinician|scientist|doctor|investigator|experimenter)\s+in\s+(a\s+[a-z0-9 ,-]+?(?:coat|jacket|suit|frock coat|waistcoat|shirt|blouse|cardigan))"
        )
        for c in clips:
            act = str(c.get("action") or "")
            m = re.search(role_regex, act, flags=re.IGNORECASE)
            if m and not _ANIMAL_CLAUSE_RE.search(m.group(0)):
                label_prefix = "adult participant in " if not is_inv_role else "clinical investigator in "
                cand = label_prefix + m.group(1).strip()
                break

    return _anonymize_and_lock_wardrobe_clause(cand, role)


def normalize_strict_room_continuity_ledger(plan: dict[str, Any]) -> None:
    """
    Normalizes `clip["scene_state"]` across `plan["clips"]` so `strict_room_continuity: True`
    passes `validate_scene_state_continuity(plan)` with zero issues.
    """
    clips = [c for c in (plan.get("clips") or []) if isinstance(c, dict)]
    loc_state: dict[str, dict[str, Any]] = {}

    for idx, mc in enumerate(clips, start=1):
        g_name = str(mc.get("grammar") or "").strip()
        c_role = str(mc.get("cut_role") or "").strip().lower()
        is_brain_or_outro = (
            g_name in ("porcelain_living_brain", "porcelain_data_sculpture", "lowpoly_living_brain", "lowpoly_data_sculpture")
            or bool(mc.get("brain_mode"))
            or c_role == "outro"
        )
        st = mc.get("scene_state")
        if not isinstance(st, dict):
            if is_brain_or_outro or c_role in ("split_right", "split_bottom"):
                continue
            loc_fallback = str(mc.get("location_id") or plan.get("default_location_id") or "primary_studio_room").strip()
            st = {
                "location_id": loc_fallback,
                "present_cast_start": ["researcher"],
                "entering_cast": [],
                "exiting_cast": [],
                "present_cast_end": ["researcher"],
            }
            mc["scene_state"] = st

        loc_id = str(st.get("location_id") or mc.get("location_id") or plan.get("default_location_id") or "").strip()
        if loc_id:
            st["location_id"] = loc_id
            mc.setdefault("location_id", loc_id)

        p_start = [str(x).strip() for x in (st.get("present_cast_start") or []) if str(x).strip()]
        entering = [str(x).strip() for x in (st.get("entering_cast") or []) if str(x).strip() and str(x).strip() not in p_start]
        exiting = [str(x).strip() for x in (st.get("exiting_cast") or []) if str(x).strip() and str(x).strip() in (set(p_start) | set(entering))]
        expected_end = sorted((set(p_start) | set(entering)) - set(exiting))
        st["present_cast_start"] = p_start
        st["entering_cast"] = entering
        st["exiting_cast"] = exiting
        st["present_cast_end"] = expected_end

        if loc_id and not is_brain_or_outro and c_role not in ("split_right", "split_bottom"):
            has_phase_reset = bool(st.get("scene_reset") or st.get("protocol_phase_jump"))
            prev_loc = loc_state.get(loc_id)
            if prev_loc is not None and not has_phase_reset:
                ghost_returns = set(p_start) & prev_loc["departed"]
                dup_reentries = set(entering) & prev_loc["present_end"]
                fullbleed_mismatch = (
                    g_name == "porcelain_fullbleed_world"
                    and prev_loc.get("prev_fullbleed_end") is not None
                    and not bool(st.get("camera_framing_subset"))
                    and set(p_start) != prev_loc["prev_fullbleed_end"]
                )
                if ghost_returns or dup_reentries or fullbleed_mismatch:
                    st["protocol_phase_jump"] = True
                    has_phase_reset = True

            new_departed = (
                set(exiting)
                if (prev_loc is None or bool(st.get("scene_reset")) or bool(st.get("protocol_phase_jump")))
                else ((prev_loc["departed"] - set(entering)) | set(exiting))
            )
            explicit_absent = {str(x).strip() for x in (st.get("absent_cast") or []) if str(x).strip()}
            new_departed |= (explicit_absent - set(expected_end))
            loc_state[loc_id] = {
                "present_end": set(expected_end),
                "departed": new_departed,
                "prev_clip_id": idx,
                "last_exit_clip": idx if exiting else (prev_loc["last_exit_clip"] if prev_loc else idx),
                "prev_fullbleed_end": (
                    set(expected_end)
                    if g_name == "porcelain_fullbleed_world"
                    else (prev_loc.get("prev_fullbleed_end") if prev_loc and not has_phase_reset else None)
                ),
                "prev_fullbleed_clip": (
                    idx
                    if g_name == "porcelain_fullbleed_world"
                    else (prev_loc.get("prev_fullbleed_clip") if prev_loc and not has_phase_reset else None)
                ),
            }


def _resolve_track_a_shot_ids(plan: dict[str, Any], d_dir: Path | None, project_dir: Path | None = None) -> list[str]:
    """Resolves `S01..S0N` shot IDs from `source_edl.json` / `08_reenactment_edl.json` or deterministic defaults."""
    candidates: list[Any] = []
    if isinstance(plan.get("source_edl"), dict):
        candidates.append(plan["source_edl"])
    if project_dir is not None and (Path(project_dir) / "03_visuals" / REENACT_EDL_FILENAME).exists():
        try:
            candidates.append(json.loads((Path(project_dir) / "03_visuals" / REENACT_EDL_FILENAME).read_text(encoding="utf-8")))
        except Exception:
            pass
    if d_dir is not None and (d_dir / "08_reenactment_edl.json").exists():
        try:
            candidates.append(json.loads((d_dir / "08_reenactment_edl.json").read_text(encoding="utf-8")))
        except Exception:
            pass
    for doc in candidates:
        if isinstance(doc, dict):
            s_ids = [str(s.get("shot_id")).strip() for s in (doc.get("shots") or []) if isinstance(s, dict) and s.get("shot_id")]
            if s_ids:
                return s_ids
    return ["S01", "S02", "S03", "S04"]


def populate_expressive_v8_reference_contract(
    plan: dict[str, Any],
    dossier_dir: str | Path | None = None,
    *,
    project_dir: str | Path | None = None,
    synthesize_scene_anchors: bool = False,
    daisy_chain_keyframes: bool = False,
) -> dict[str, Any]:
    """
    Compiles the `expressive_25d_v8` (`안 1 + 안 3 결합형`) reference-conditioning contract onto `plan`:
      - Normal cuts (~93%): single-scene `9:16` location anchor (or `species_opt1_sheet.png` in 2-chip/offline mode)
      - `[70–85%]` `expressive_xray_brain` cuts: episode-matched `9:16` X-Ray anchor (or `xray_brain75_master.png`)
      - Easter-egg cut (strictly 1 cut per episode, `cameo_easter_egg: True`): 2-chip
        `[start_ref, cameo_opt3_sheet.png]` via `secondary_reference_image` & `reference_images`
        (with dedicated `ref_cameo_9x16.png` start-frame anchor when `synthesize_scene_anchors=True` so 1-frame
        `0-credit` `Veo 3.1 - Lite` `Frames` mode renders the `4cm` `Mini-Cortex` figurine reliably).
      - Preserves `reenactment_track == 'track_a'` if set, and preserves `end_reference_image` on `Start+End` cuts.
    """
    if not is_expressive_v8_plan(plan):
        return plan

    from pipeline.depiction_rules import normalize_expressive_v8_grammar

    plan["style_profile"] = EXPRESSIVE_25D_V8_STYLE_PROFILE
    plan["schema_version"] = int(plan.get("schema_version") or PROMPT_SCHEMA_VERSION_V8)
    plan.setdefault("shorts_format_profile", SHORTS_EXPRESSIVE_V8_PROFILE)
    existing_track = str(plan.get("reenactment_track") or "").strip().lower()
    plan["reenactment_track"] = existing_track if existing_track in ("track_a", "track_b") else "track_b"

    slug = str(plan.get("dossier_slug") or plan.get("dossier") or "").strip()
    d_dir: Path | None = None
    if dossier_dir is not None and Path(dossier_dir).exists():
        d_dir = Path(dossier_dir)
    elif slug and (Path(DOSSIERS_DIR) / slug).exists():
        d_dir = Path(DOSSIERS_DIR) / slug

    iconic_scene = _extract_iconic_scene_from_dossier(d_dir)
    if not plan.get("default_location_id"):
        raw_id = str(iconic_scene.get("id") or slug or "primary_diorama_stage").lower()
        plan["default_location_id"] = re.sub(r"[^a-z0-9_]+", "_", raw_id).strip("_") or "primary_diorama_stage"
    if not plan.get("real_environment"):
        lay = iconic_scene.get("layout") if isinstance(iconic_scene.get("layout"), dict) else {}
        desc = str(lay.get("description") or iconic_scene.get("title") or "").strip()
        plan["real_environment"] = desc or "a stylized 3D miniature diorama room with crisp architectural lighting"
    if not plan.get("environment_props"):
        plan["environment_props"] = ["a tactile brushed-metal experimental instrument on a wooden desk"]
    if not isinstance(plan.get("cast"), dict) or not plan["cast"]:
        plan["cast"] = {
            "subject": (
                "2.5D matte cream-white vinyl character with smooth earless noseless hairless oval head, "
                "bold charcoal-black 2D cartoon ink eyes eyebrows and mouth, wearing tailored 3D woven everyday attire"
            ),
            "foil": (
                "2.5D matte cream-white vinyl foil character with skeptical raised charcoal-black 2D ink eyebrow "
                "and smirk, wearing crisp 3D structured jacket attire"
            ),
        }

    species_rel = f"03_visuals/{REF_IMAGES_DIRNAME}/{EXPRESSIVE_V8_SPECIES_SHEET_FILENAME}"
    cameo_rel = f"03_visuals/{REF_IMAGES_DIRNAME}/{EXPRESSIVE_V8_CAMEO_SHEET_FILENAME}"
    xray_rel = f"03_visuals/{REF_IMAGES_DIRNAME}/xray_brain75_master.png"
    conflict_rel = f"03_visuals/{REF_IMAGES_DIRNAME}/expressive_conflict_master.png"
    multi_panel_v8_sheets = (
        EXPRESSIVE_V8_SPECIES_SHEET_FILENAME,
        EXPRESSIVE_V8_CAMEO_SHEET_FILENAME,
        *EXPRESSIVE_V8_CAST_SHEET_FILENAMES,
    )
    clips = [c for c in (plan.get("clips") or []) if isinstance(c, dict)]

    use_daisy = bool(daisy_chain_keyframes or plan.get("daisy_chain_keyframes"))
    auto_synth = bool(synthesize_scene_anchors or plan.get("auto_scene_anchors") or use_daisy)
    existing_anchors = [a for a in (plan.get("reference_anchors") or []) if isinstance(a, dict)]
    all_seeded_placeholders = bool(existing_anchors) and all(bool(a.get("seeded_placeholder")) for a in existing_anchors)
    daisy_cam_progression = (
        ("eye_level_medium", "eye-level medium 35mm cinema composition facing the foreground action"),
        ("high_angle_3q", "elevated 40-degree bird's-eye three-quarter diorama angle looking down across the room geometry"),
        ("object_portal_macro", "tactile foreground object-portal macro composition framing the key physical prop with deep background room depth"),
        ("over_shoulder_orbit", "reverse 180-degree over-the-shoulder three-quarter orbit composition showing spatial depth across the room"),
    )
    if use_daisy and clips and (not existing_anchors or all_seeded_placeholders):
        daisy_anchors: list[dict[str, Any]] = []
        brain_seen_count = 0
        for idx_c, c_item in enumerate(clips, start=1):
            g_raw = str(c_item.get("grammar") or "")
            c_is_cameo = bool(c_item.get("cameo_easter_egg")) or g_raw == "expressive_cameo_world"
            c_is_brain = bool(c_item.get("brain_clip")) or g_raw in ("expressive_xray_brain", "porcelain_living_brain")
            loc_k = re.sub(
                r"[^a-z0-9_]+",
                "_",
                str(c_item.get("location_id") or plan["default_location_id"]).strip().lower(),
            ).strip("_") or str(plan["default_location_id"])
            env_txt = str(c_item.get("environment") or plan["real_environment"]).strip()
            allow_t = [str(t).strip() for t in (c_item.get("diegetic_text_allowlist") or ()) if str(t).strip()][:2]
            cam_tag, cam_desc = daisy_cam_progression[(idx_c - 1) % len(daisy_cam_progression)]
            act_hint = str(c_item.get("action") or "").strip()
            act_clause = f" staging {act_hint[:110]}" if act_hint else ""
            if c_is_cameo:
                cm_place = str(
                    c_item.get("cameo_placement")
                    or "a tiny 4cm glowing 4-color translucent vinyl Mini-Cortex brain figurine resting quietly on a background shelf"
                ).strip()
                daisy_anchors.append(
                    {
                        "ref_id": "ref_cameo_9x16",
                        "filename": "ref_cameo_9x16.png",
                        "clip_number": idx_c,
                        "frame": "start",
                        "category": "clip_keyframe_anchor",
                        "role": "cameo_anchor",
                        "setting": "real_env",
                        "location_id": loc_k,
                        "camera_angle_tag": cam_tag,
                        "generation_order": 3,
                        "conditioned_on": ["species_opt1_sheet", "cameo_opt3_sheet"],
                        "diegetic_text_allowlist": allow_t,
                        "prompt": (
                            f"Single full-bleed vertical 9:16 3D miniature diorama scene ({cam_desc}) of {env_txt} "
                            f"featuring {cm_place}, cinema key-and-rim lighting, zero floating captions."
                        ),
                    }
                )
            elif c_is_brain:
                brain_seen_count += 1
                b_fname = "ref_xray_brain_9x16.png" if brain_seen_count == 1 else f"ref_xray_brain_{brain_seen_count}_9x16.png"
                if bool(c_item.get("portal_to_brain")):
                    fname_start_portal = f"kf_{idx_c:02d}_{loc_k[:22]}_{cam_tag}_9x16.png"
                    daisy_anchors.append(
                        {
                            "ref_id": Path(fname_start_portal).stem,
                            "filename": fname_start_portal,
                            "clip_number": idx_c,
                            "frame": "start",
                            "category": "clip_keyframe_anchor",
                            "role": "reenactment",
                            "setting": "real_env",
                            "location_id": loc_k,
                            "camera_angle_tag": cam_tag,
                            "generation_order": 3,
                            "conditioned_on": ["species_opt1_sheet"],
                            "diegetic_text_allowlist": allow_t,
                            "prompt": (
                                f"Single full-bleed vertical 9:16 3D miniature diorama scene ({cam_desc}) of {env_txt}"
                                f"{act_clause} with a clothed 2.5D matte cream-white vinyl character with smooth earless "
                                "noseless hairless oval head and bold charcoal-black 2D cartoon ink eyes, eyebrows, and "
                                "mouth, cinema key-and-rim lighting, zero text."
                            ),
                        }
                    )
                    brain_frame_role = "end"
                else:
                    brain_frame_role = "start"
                daisy_anchors.append(
                    {
                        "ref_id": Path(b_fname).stem,
                        "filename": b_fname,
                        "clip_number": idx_c,
                        "frame": brain_frame_role,
                        "category": "brain_anchor",
                        "role": "brain_mechanism",
                        "setting": "brain_studio",
                        "camera_angle_tag": ("xray_dome_closeup" if brain_frame_role == "end" else cam_tag),
                        "generation_order": 3,
                        "conditioned_on": ["xray_brain75_master", "species_opt1_sheet"],
                        "prompt": (
                            f"Single full-bleed vertical 9:16 3D miniature diorama scene ({cam_desc}) inside {env_txt}: "
                            "a clothed 2.5D matte cream-white vinyl character with smooth earless noseless oval head, "
                            "charcoal-black 2D ink eyes, and a gleaming golden metallic ring parting the upper head into "
                            "a crystal-clear glass dome exposing the bounded 4-color glowing 3D brain (crimson-red, "
                            "amber-gold, cyan-blue, deep indigo), zero text."
                        ),
                    }
                )
            else:
                fname_k = f"kf_{idx_c:02d}_{loc_k[:22]}_{cam_tag}_9x16.png"
                daisy_anchors.append(
                    {
                        "ref_id": Path(fname_k).stem,
                        "filename": fname_k,
                        "clip_number": idx_c,
                        "frame": "start",
                        "category": "clip_keyframe_anchor",
                        "role": "reenactment",
                        "setting": "real_env",
                        "location_id": loc_k,
                        "camera_angle_tag": cam_tag,
                        "generation_order": 3,
                        "conditioned_on": ["species_opt1_sheet"],
                        "diegetic_text_allowlist": allow_t,
                        "prompt": (
                            f"Single full-bleed vertical 9:16 3D miniature diorama scene ({cam_desc}) of {env_txt}"
                            f"{act_clause} with a clothed 2.5D matte cream-white vinyl character with smooth earless "
                            "noseless hairless oval head and bold charcoal-black 2D cartoon ink eyes, eyebrows, and "
                            "mouth, cinema key-and-rim lighting, zero text."
                        ),
                    }
                )
        plan["reference_anchors"] = daisy_anchors
        plan["daisy_chain_keyframes"] = True
        existing_anchors = daisy_anchors
    elif auto_synth and clips and (not existing_anchors or all_seeded_placeholders):
        synth_anchors: list[dict[str, Any]] = []
        seen_locs: dict[str, dict[str, Any]] = {}
        cameo_clip_pair: tuple[int, dict[str, Any]] | None = None
        brain_clip_pair: tuple[int, dict[str, Any]] | None = None
        for idx_c, c_item in enumerate(clips, start=1):
            g_raw = str(c_item.get("grammar") or "")
            c_is_cameo = bool(c_item.get("cameo_easter_egg")) or g_raw == "expressive_cameo_world"
            c_is_brain = bool(c_item.get("brain_clip")) or g_raw in ("expressive_xray_brain", "porcelain_living_brain")
            if c_is_cameo and cameo_clip_pair is None:
                cameo_clip_pair = (idx_c, c_item)
                continue
            if c_is_brain:
                if brain_clip_pair is None:
                    brain_clip_pair = (idx_c, c_item)
                if not bool(c_item.get("portal_to_brain")):
                    continue
            loc_k = re.sub(
                r"[^a-z0-9_]+",
                "_",
                str(c_item.get("location_id") or plan["default_location_id"]).strip().lower(),
            ).strip("_")
            if loc_k and loc_k not in seen_locs:
                seen_locs[loc_k] = {"clip_number": idx_c, "clip": c_item}
        for loc_k, info in seen_locs.items():
            c_src = info["clip"]
            env_txt = str(c_src.get("environment") or plan["real_environment"]).strip()
            allow_t = [str(t).strip() for t in (c_src.get("diegetic_text_allowlist") or ()) if str(t).strip()][:2]
            fname_l = f"ref_loc_{loc_k[:36]}_9x16.png"
            synth_anchors.append(
                {
                    "ref_id": Path(fname_l).stem,
                    "filename": fname_l,
                    "clip_number": int(info["clip_number"]),
                    "frame": "start",
                    "category": "clip_keyframe_anchor",
                    "role": "reenactment",
                    "setting": "real_env",
                    "location_id": loc_k,
                    "generation_order": 3,
                    "conditioned_on": ["species_opt1_sheet"],
                    "diegetic_text_allowlist": allow_t,
                    "prompt": (
                        f"Single full-bleed vertical 9:16 3D miniature diorama scene of {env_txt} with a clothed "
                        "2.5D matte cream-white vinyl character with smooth earless noseless hairless oval head and "
                        "bold charcoal-black 2D cartoon ink eyes, eyebrows, and mouth, cinema key-and-rim lighting, zero text."
                    ),
                }
            )
        if cameo_clip_pair is not None:
            c_idx_cm, c_cm = cameo_clip_pair
            cm_loc = str(c_cm.get("location_id") or plan["default_location_id"]).strip()
            cm_env = str(c_cm.get("environment") or plan["real_environment"]).strip()
            cm_place = str(
                c_cm.get("cameo_placement")
                or "a tiny 4cm glowing 4-color translucent vinyl Mini-Cortex brain figurine resting quietly on a background shelf"
            ).strip()
            cm_allow = [str(t).strip() for t in (c_cm.get("diegetic_text_allowlist") or ()) if str(t).strip()][:2]
            synth_anchors.append(
                {
                    "ref_id": "ref_cameo_9x16",
                    "filename": "ref_cameo_9x16.png",
                    "clip_number": c_idx_cm,
                    "frame": "start",
                    "category": "clip_keyframe_anchor",
                    "role": "cameo_anchor",
                    "setting": "real_env",
                    "location_id": cm_loc,
                    "generation_order": 3,
                    "conditioned_on": ["species_opt1_sheet", "cameo_opt3_sheet"],
                    "diegetic_text_allowlist": cm_allow,
                    "prompt": (
                        f"Single full-bleed vertical 9:16 3D miniature diorama scene of {cm_env} featuring {cm_place}, "
                        "cinema key-and-rim lighting, zero floating captions."
                    ),
                }
            )
        if brain_clip_pair is not None:
            b_idx, b_clip = brain_clip_pair
            b_env = str(b_clip.get("environment") or plan["real_environment"]).strip()
            b_frame_role = "end" if bool(b_clip.get("portal_to_brain")) else "start"
            synth_anchors.append(
                {
                    "ref_id": "ref_xray_brain_9x16",
                    "filename": "ref_xray_brain_9x16.png",
                    "clip_number": b_idx,
                    "frame": b_frame_role,
                    "category": "brain_anchor",
                    "role": "brain_mechanism",
                    "setting": "brain_studio",
                    "generation_order": 3,
                    "conditioned_on": ["xray_brain75_master", "species_opt1_sheet"],
                    "prompt": (
                        f"Single full-bleed vertical 9:16 3D miniature diorama scene inside {b_env}: a clothed 2.5D "
                        "matte cream-white vinyl character with smooth earless noseless oval head, charcoal-black 2D ink "
                        "eyes, and a gleaming golden metallic ring parting the upper head into a crystal-clear glass dome "
                        "exposing the bounded 4-color glowing 3D brain (crimson-red, amber-gold, cyan-blue, deep indigo), zero text."
                    ),
                }
            )
        plan["reference_anchors"] = synth_anchors
        existing_anchors = synth_anchors

    loc_to_rel: dict[str, str] = {}
    clip_num_to_rel: dict[int, str] = {}
    clip_num_to_end_rel: dict[int, str] = {}
    brain_anchor_rel: str = ""
    cameo_anchor_rel: str = ""
    for anc in existing_anchors:
        fname_a = str(anc.get("filename") or (f"{anc['ref_id']}.png" if anc.get("ref_id") else "")).strip()
        if not fname_a:
            continue
        rel_a = fname_a if fname_a.startswith("03_visuals/") else f"03_visuals/{REF_IMAGES_DIRNAME}/{fname_a}"
        role_a = str(anc.get("role") or "").strip().lower()
        setting_a = str(anc.get("setting") or "").strip().lower()
        loc_a = str(anc.get("location_id") or "").strip()
        c_num_a = int(anc.get("clip_number") or 0)
        frame_a = str(anc.get("frame") or "start").strip().lower()
        if c_num_a > 0 and frame_a == "start" and c_num_a not in clip_num_to_rel:
            clip_num_to_rel[c_num_a] = rel_a
        elif c_num_a > 0 and frame_a == "end" and c_num_a not in clip_num_to_end_rel:
            clip_num_to_end_rel[c_num_a] = rel_a
        if setting_a == "brain_studio" or str(anc.get("category") or "") == "brain_anchor":
            if not brain_anchor_rel:
                brain_anchor_rel = rel_a
        elif role_a == "cameo_anchor" or "cameo" in fname_a.lower():
            if not cameo_anchor_rel:
                cameo_anchor_rel = rel_a
        elif loc_a and loc_a not in loc_to_rel:
            loc_to_rel[loc_a] = rel_a

    for idx_clip, c in enumerate(clips, start=1):
        c["style_profile"] = EXPRESSIVE_25D_V8_STYLE_PROFILE
        c["schema_version"] = PROMPT_SCHEMA_VERSION_V8
        g_name = str(c.get("grammar") or "expressive_vinyl_world").strip()
        is_cameo = bool(c.get("cameo_easter_egg")) or g_name == "expressive_cameo_world"
        norm_g = normalize_expressive_v8_grammar(g_name, cameo_easter_egg=is_cameo)
        is_brain = bool(c.get("brain_clip")) or norm_g == "expressive_xray_brain"
        c_loc = str(
            ((c.get("scene_state") or {}).get("location_id") if isinstance(c.get("scene_state"), dict) else "")
            or c.get("location_id")
            or plan.get("default_location_id")
            or ""
        ).strip()
        cur_ref = str(c.get("reference_image") or "").strip()
        eff_c_num = int(c.get("clip_number") or idx_clip)
        per_clip_ref = clip_num_to_rel.get(eff_c_num, "") if use_daisy else ""
        per_clip_end_ref = clip_num_to_end_rel.get(eff_c_num, "")

        if is_cameo:
            c["cameo_easter_egg"] = True
            c["grammar"] = "expressive_cameo_world"
            preferred_cameo_start = per_clip_ref or cameo_anchor_rel or loc_to_rel.get(c_loc) or species_rel
            start_ref = preferred_cameo_start if (not cur_ref or (cur_ref == species_rel and preferred_cameo_start != species_rel)) else cur_ref
            c["reference_image"] = start_ref
            c["secondary_reference_image"] = cameo_rel
            c["reference_images"] = [start_ref, cameo_rel]
            c.pop("end_reference_image", None)
        elif is_brain:
            c["cameo_easter_egg"] = False
            c["grammar"] = "expressive_xray_brain"
            c["brain_clip"] = True
            if bool(c.get("portal_to_brain")):
                raw_cur_end = str(c.get("end_reference_image") or "").strip()
                end_brain_target = (
                    (raw_cur_end if (raw_cur_end and not raw_cur_end.endswith(multi_panel_v8_sheets)) else "")
                    or per_clip_end_ref
                    or brain_anchor_rel
                    or xray_rel
                )
                loc_candidate = loc_to_rel.get(c_loc, "")
                start_room_target = (
                    (per_clip_ref if (per_clip_ref and per_clip_ref != end_brain_target and not per_clip_ref.endswith(multi_panel_v8_sheets)) else "")
                    or (loc_candidate if (loc_candidate and not loc_candidate.endswith(multi_panel_v8_sheets)) else "")
                    or conflict_rel
                )
                if not cur_ref or cur_ref in (xray_rel, brain_anchor_rel) or cur_ref.endswith(multi_panel_v8_sheets):
                    c["reference_image"] = start_room_target
                if (not raw_cur_end or raw_cur_end.endswith(multi_panel_v8_sheets)) and str(c.get("reference_image") or "").strip() != end_brain_target:
                    c["end_reference_image"] = end_brain_target
                c["full_trajectory_span"] = True
            else:
                preferred_brain = per_clip_ref or brain_anchor_rel or xray_rel
                if not cur_ref or (cur_ref == xray_rel and preferred_brain != xray_rel):
                    c["reference_image"] = preferred_brain
                if per_clip_end_ref and per_clip_end_ref != str(c.get("reference_image") or "").strip():
                    c.setdefault("end_reference_image", per_clip_end_ref)
            if "reference_images" in c:
                c["reference_images"] = [c["reference_image"]] if c.get("reference_image") else []
            c.pop("secondary_reference_image", None)
        else:
            c["cameo_easter_egg"] = False
            c["grammar"] = (
                norm_g
                if norm_g in EXPRESSIVE_V8_VISUAL_GRAMMARS and norm_g not in ("expressive_xray_brain", "expressive_cameo_world")
                else "expressive_vinyl_world"
            )
            loc_ref = per_clip_ref or loc_to_rel.get(c_loc, "")
            if not cur_ref or (cur_ref == species_rel and loc_ref):
                if c["grammar"] == "expressive_literal_analogy" and not (c.get("scene_state") or {}).get("present_cast_start") and not loc_ref:
                    c.pop("reference_image", None)
                else:
                    c["reference_image"] = loc_ref or species_rel
            if per_clip_end_ref and per_clip_end_ref != str(c.get("reference_image") or "").strip():
                c.setdefault("end_reference_image", per_clip_end_ref)
            if "reference_images" in c:
                c["reference_images"] = [c["reference_image"]] if c.get("reference_image") else []
            c.pop("secondary_reference_image", None)

    if use_daisy and len(clips) >= 2:
        from pipeline.config import EXPRESSIVE_V8_MAX_STYLED_TRANSITIONS

        styled_set = {
            "dissolve_6f",
            "dissolve_8f",
            "portal_crash_zoom_10f",
            "whip_pan_blur_8f",
            "occlusion_wipe",
            "split_screen_wipe",
            "match_cut_bridge",
        }

        def _is_brain_clip_spec(clip_d: dict[str, Any]) -> bool:
            return bool(clip_d.get("brain_clip")) or clip_d.get("grammar") == "expressive_xray_brain"

        def _is_room_portal_clip(clip_d: dict[str, Any]) -> bool:
            r_start = str(clip_d.get("reference_image") or "").strip()
            return (
                _is_brain_clip_spec(clip_d)
                and bool(clip_d.get("portal_to_brain"))
                and bool(r_start)
                and "xray_brain" not in r_start
                and "brain_master" not in r_start
            )

        styled_used = 0
        for idx_chk, c_chk in enumerate(clips[:-1]):
            tr_chk = str(c_chk.get("transition_out") or c_chk.get("transition_to_next") or "").strip().lower()
            if tr_chk in styled_set:
                styled_used += 1
            elif tr_chk == "daisy_chain_bridge":
                end_chk = str(c_chk.get("end_reference_image") or "").strip()
                nxt_chk = str(clips[idx_chk + 1].get("reference_image") or "").strip()
                if not (end_chk and nxt_chk and end_chk == nxt_chk):
                    styled_used += 1

        has_future_brain_entry = [
            any(
                (not _is_brain_clip_spec(clips[k]))
                and _is_brain_clip_spec(clips[k + 1])
                and (not _is_room_portal_clip(clips[k + 1]))
                for k in range(i_k + 1, len(clips) - 1)
            )
            for i_k in range(len(clips) - 1)
        ]
        for i_c in range(len(clips) - 1):
            c_cur = clips[i_c]
            c_nxt = clips[i_c + 1]
            cur_cameo = bool(c_cur.get("cameo_easter_egg")) or c_cur.get("grammar") == "expressive_cameo_world"
            nxt_cameo = bool(c_nxt.get("cameo_easter_egg")) or c_nxt.get("grammar") == "expressive_cameo_world"
            cur_brain = _is_brain_clip_spec(c_cur)
            nxt_brain = _is_brain_clip_spec(c_nxt)
            loc_cur = str(c_cur.get("location_id") or plan.get("default_location_id") or "").strip()
            loc_nxt = str(c_nxt.get("location_id") or plan.get("default_location_id") or "").strip()
            ref_cur = str(c_cur.get("reference_image") or "").strip()
            ref_nxt = str(c_nxt.get("reference_image") or "").strip()
            cur_end_pre = str(c_cur.get("end_reference_image") or "").strip()

            # Seamless handoff when a portal_to_brain (or explicit End-anchored) brain clip is followed by another brain clip
            if (
                cur_brain
                and nxt_brain
                and not cur_cameo
                and not nxt_cameo
                and not bool(c_nxt.get("portal_to_brain"))
                and cur_end_pre
                and ref_nxt
                and cur_end_pre != ref_nxt
                and not c_nxt.get("end_reference_image")
                and not cur_end_pre.endswith(multi_panel_v8_sheets)
                and not ref_nxt.endswith(multi_panel_v8_sheets)
            ):
                c_nxt["reference_image"] = cur_end_pre
                c_nxt["end_reference_image"] = ref_nxt
                c_nxt["full_trajectory_span"] = True
                if "reference_images" in c_nxt:
                    c_nxt["reference_images"] = [cur_end_pre]
                ref_nxt = cur_end_pre

            nxt_portal_from_room = _is_room_portal_clip(c_nxt)
            cur_pullback_to_room = (
                cur_brain
                and (not nxt_brain)
                and bool(loc_cur and loc_cur == loc_nxt)
                and bool(cur_end_pre and cur_end_pre == ref_nxt)
                and "xray_brain" not in cur_end_pre
                and "brain_master" not in cur_end_pre
            )
            same_space_ok = (
                not cur_cameo
                and not nxt_cameo
                and (
                    ((cur_brain == nxt_brain) and (cur_brain or (loc_cur and loc_cur == loc_nxt)))
                    or ((not cur_brain) and nxt_portal_from_room and bool(loc_cur and loc_cur == loc_nxt))
                    or cur_pullback_to_room
                )
                and bool(ref_cur and ref_nxt and ref_cur != ref_nxt)
                and not ref_cur.endswith(multi_panel_v8_sheets)
                and not ref_nxt.endswith(multi_panel_v8_sheets)
            )
            if same_space_ok:
                if not c_cur.get("end_reference_image"):
                    c_cur["end_reference_image"] = ref_nxt
                c_cur["full_trajectory_span"] = True
                exact_handoff = bool(ref_nxt) and str(c_cur.get("end_reference_image") or "").strip() == ref_nxt
                if not c_cur.get("transition_to_next") and not c_cur.get("transition_out"):
                    if exact_handoff:
                        c_cur["transition_to_next"] = "daisy_chain_bridge"
                    else:
                        budget_cap = int(EXPRESSIVE_V8_MAX_STYLED_TRANSITIONS) - (1 if has_future_brain_entry[i_c] else 0)
                        if styled_used < budget_cap:
                            c_cur["transition_to_next"] = "whip_pan_blur_8f"
                            styled_used += 1
                        else:
                            c_cur["transition_to_next"] = "hard"
            else:
                # Never leak cross-location or multi-panel turnaround/cast sheets into end_reference_image
                existing_end = str(c_cur.get("end_reference_image") or "").strip()
                eff_cur_num = int(c_cur.get("clip_number") or (i_c + 1))
                has_explicit_portal = bool(c_cur.get("portal_to_brain")) and cur_brain
                has_explicit_end_anchor = eff_cur_num in clip_num_to_end_rel
                if existing_end.endswith(multi_panel_v8_sheets) or (
                    existing_end == ref_nxt and not has_explicit_portal and not has_explicit_end_anchor
                ):
                    c_cur.pop("end_reference_image", None)
                if not c_cur.get("transition_to_next") and not c_cur.get("transition_out"):
                    entering_brain = (not cur_brain) and nxt_brain and (not nxt_portal_from_room)
                    budget_cap = int(EXPRESSIVE_V8_MAX_STYLED_TRANSITIONS) - (
                        1 if (not entering_brain and has_future_brain_entry[i_c]) else 0
                    )
                    if entering_brain and styled_used < int(EXPRESSIVE_V8_MAX_STYLED_TRANSITIONS):
                        c_cur["transition_to_next"] = "portal_crash_zoom_10f"
                        styled_used += 1
                    elif styled_used < budget_cap:
                        c_cur["transition_to_next"] = "whip_pan_blur_8f"
                        styled_used += 1
                    else:
                        c_cur["transition_to_next"] = "hard"
    for c in clips:
        if c.get("end_reference_image"):
            c.setdefault("full_trajectory_span", True)

    return plan


def populate_porcelain_reference_contract(
    plan: dict[str, Any],
    dossier_dir: str | Path | None = None,
    *,
    preserve_curated_source_edl: bool = True,
    project_dir: str | Path | None = None,
    synthesize_scene_anchors: bool = False,
    daisy_chain_keyframes: bool = False,
) -> dict[str, Any]:
    """
    Compiles the complete `porcelain_cinematic_v7` (or `expressive_25d_v8`) reference-conditioning contract onto `plan`.
    """
    if is_expressive_v8_plan(plan):
        return populate_expressive_v8_reference_contract(
            plan,
            dossier_dir=dossier_dir,
            project_dir=project_dir,
            synthesize_scene_anchors=synthesize_scene_anchors,
            daisy_chain_keyframes=daisy_chain_keyframes,
        )
    if not is_porcelain_v7_plan(plan):
        return plan

    slug = str(plan.get("dossier_slug") or plan.get("dossier") or "").strip()
    d_dir: Path | None = None
    if dossier_dir is not None and Path(dossier_dir).exists():
        d_dir = Path(dossier_dir)
    elif slug and (Path(DOSSIERS_DIR) / slug).exists():
        d_dir = Path(DOSSIERS_DIR) / slug
    p_dir = Path(project_dir) if (project_dir is not None and Path(project_dir).exists()) else None

    # Determine reenactment_track from dossier suitability audit if available
    track = str(plan.get("reenactment_track") or "").strip().lower()
    if track not in ("track_a", "track_b"):
        if plan.get("source_edl") or (d_dir and (d_dir / "08_reenactment_edl.json").exists()):
            track = "track_a"
        elif d_dir is not None:
            try:
                from pipeline.research_dossier import audit_dossier_media_suitability

                suit = audit_dossier_media_suitability(d_dir, write_back=False)
                track = str(suit.get("reenactment_track") or "track_b")
            except Exception:
                track = "track_b"
        else:
            track = "track_b"
    plan["reenactment_track"] = track

    # Preserve hand-authored R67 pilot / curated source_edl plans untouched
    if (
        preserve_curated_source_edl
        and plan.get("source_edl")
        and isinstance(plan.get("reference_anchors"), list)
        and len(plan["reference_anchors"]) >= 2
        and isinstance(plan.get("cast"), dict)
        and plan.get("real_environment")
    ):
        plan["require_scene_state_ledger"] = True
        plan["strict_room_continuity"] = True
        return plan

    clips = [c for c in (plan.get("clips") or []) if isinstance(c, dict)]
    iconic_scene = _extract_iconic_scene_from_dossier(d_dir)

    # 1. Resolve default_location_id & room environments (prioritizing early iconic Acts 1–2 room)
    loc_counter: Counter[str] = Counter()
    loc_env_texts: dict[str, Counter[str]] = {}
    early_cutoff = max(12, len(clips) // 3)
    for c_idx, c in enumerate(clips):
        g_name = str(c.get("grammar") or "")
        c_role = str(c.get("cut_role") or "").strip().lower()
        if g_name in ("porcelain_living_brain", "porcelain_data_sculpture") or c_role == "outro":
            continue
        loc = str((c.get("scene_state") or {}).get("location_id") or c.get("location_id") or "").strip()
        if loc:
            base_w = 3 if g_name == "porcelain_fullbleed_world" else 1
            weight = base_w * 2 if c_idx < early_cutoff else base_w
            loc_counter[loc] += weight
            env_t = sanitize_porcelain_contract_text(str(c.get("environment") or ""))
            if env_t:
                loc_env_texts.setdefault(loc, Counter())[env_t] += weight

    default_loc = str(plan.get("default_location_id") or "").strip()
    if not default_loc or (loc_counter and default_loc not in loc_counter):
        if loc_counter:
            default_loc = loc_counter.most_common(1)[0][0]
        else:
            raw_id = str(iconic_scene.get("id") or slug or "primary_studio_room").lower()
            default_loc = re.sub(r"[^a-z0-9_]+", "_", raw_id).strip("_") or "primary_studio_room"
    elif loc_counter:
        # Prefer the Act 1–2 primary historical room if existing default_loc was a late secondary room
        top_loc = loc_counter.most_common(1)[0][0]
        if top_loc != default_loc and loc_counter[top_loc] > loc_counter[default_loc]:
            default_loc = top_loc
    plan["default_location_id"] = default_loc

    # 2. Resolve real_environment & environment_props (plaque-sanitized + animal sculptures routed to props)
    existing_env = sanitize_porcelain_contract_text(str(plan.get("real_environment") or ""))
    if not existing_env or (default_loc in loc_env_texts and loc_env_texts[default_loc]):
        if default_loc in loc_env_texts and loc_env_texts[default_loc]:
            existing_env = loc_env_texts[default_loc].most_common(1)[0][0]
        elif not existing_env:
            lay = iconic_scene.get("layout") if isinstance(iconic_scene.get("layout"), dict) else {}
            era = sanitize_porcelain_contract_text(str(iconic_scene.get("era") or ""))
            desc = sanitize_porcelain_contract_text(str(lay.get("description") or iconic_scene.get("title") or ""))
            existing_env = sanitize_porcelain_contract_text(
                f"a bright sunlit high-key architectural studio room ({era}) with {desc}"
                if (era and desc)
                else (desc or "a bright sunlit high-key architectural neurology studio laboratory with pale walls and a warm oak workbench")
            )
    plan["real_environment"] = existing_env

    existing_props = [
        sanitize_porcelain_contract_text(str(p))
        for p in (plan.get("environment_props") or [])
        if sanitize_porcelain_contract_text(str(p))
    ]
    if not existing_props or iconic_scene.get("props"):
        rebuilt_props: list[str] = []
        for rp in iconic_scene.get("props") or []:
            np_entry = _normalize_prop_entry(rp)
            if not np_entry:
                continue
            nm = np_entry["name"]
            dt = np_entry["period_detail"]
            combined = f"{nm} ({dt})" if (dt and dt.lower() not in nm.lower() and len(dt) <= 75) else nm
            combined = sanitize_porcelain_contract_text(combined)
            if combined and combined not in rebuilt_props:
                rebuilt_props.append(combined)
            if len(rebuilt_props) >= 4:
                break
        for anim_prop in _extract_animal_props_from_wardrobe(iconic_scene):
            if anim_prop not in rebuilt_props and len(rebuilt_props) < 4:
                rebuilt_props.append(anim_prop)
        if rebuilt_props:
            existing_props = rebuilt_props
    if not existing_props:
        existing_props = [
            "a brushed-aluminum clinical apparatus on a sunlit oak workbench",
            "an unmarked archival protocol folder beside a matte-ceramic instrument tray",
        ]
    plan["environment_props"] = existing_props[:4]

    # 3. Resolve cast dictionary covering all recurring human roles in scene_state
    role_counts: Counter[str] = Counter()
    for c in clips:
        st = c.get("scene_state") or {}
        for k in ("present_cast_start", "present_cast_end", "entering_cast", "exiting_cast"):
            for r in st.get(k) or []:
                rs = str(r).strip()
                if rs:
                    role_counts[rs] += 1
    if not role_counts:
        role_counts["subject"] = 2
        role_counts["researcher"] = 2

    cast_dict: dict[str, str] = {}
    existing_cast = plan.get("cast") if isinstance(plan.get("cast"), dict) else {}
    ordered_roles = (["subject"] if "subject" in role_counts else []) + [
        r for r, _ in role_counts.most_common() if r != "subject"
    ]
    has_dossier_wardrobe = bool(iconic_scene.get("wardrobe"))
    for role in ordered_roles[:4]:
        prev_val = existing_cast.get(role) if isinstance(existing_cast.get(role), str) else ""
        if (
            prev_val
            and not has_dossier_wardrobe
            and "wardrobe" not in existing_cast
            and _is_valid_existing_role_wardrobe(role, prev_val)
        ):
            cast_dict[role] = _anonymize_and_lock_wardrobe_clause(prev_val, role)
        else:
            cast_dict[role] = _infer_wardrobe_for_role(role, iconic_scene, clips)
    plan["cast"] = cast_dict

    # 4. Enforce strict_room_continuity & scene_state ledger
    plan["require_scene_state_ledger"] = True
    plan["strict_room_continuity"] = True
    if clips:
        normalize_strict_room_continuity_ledger(plan)

    # 5. Synthesize 3–5 curated room/shot `reference_anchors` so total_specs >= MIN_REF_IMAGES_PER_PROJECT (6..9)
    visual_mode = str(plan.get("visual_mode") or "HYBRID").upper()
    has_brain_master = visual_mode in ("HYBRID", "NEURO_BIOLOGY")
    master_count = 1 + len(cast_dict) + (1 if has_brain_master else 0)
    min_room_anchors = max(3, MIN_REF_IMAGES_PER_PROJECT - master_count)
    target_room_anchors = min(5, max(min_room_anchors, 4 if not has_brain_master else 3))

    state_counter: Counter[tuple[str, tuple[str, ...]]] = Counter()
    state_sample_clip: dict[tuple[str, tuple[str, ...]], dict[str, Any]] = {}
    for c in clips:
        if str(c.get("grammar") or "") not in ("porcelain_fullbleed_world", "porcelain_cutaway_section"):
            continue
        if str(c.get("cut_role") or "").strip().lower() == "outro":
            continue
        st = c.get("scene_state") or {}
        loc = str(st.get("location_id") or c.get("location_id") or default_loc).strip()
        p_start = tuple(sorted({str(x).strip() for x in (st.get("present_cast_start") or []) if str(x).strip()}))
        key = (loc, p_start)
        state_counter[key] += 1
        state_sample_clip.setdefault(key, c)

    selected_states: list[tuple[str, tuple[str, ...]]] = [k for k, _ in state_counter.most_common(target_room_anchors)]
    fallback_cast_combos: list[tuple[str, ...]] = [
        tuple(sorted(list(cast_dict.keys())[:2])),
        ("subject",) if "subject" in cast_dict else (ordered_roles[0],),
        ("researcher",) if "researcher" in cast_dict else (ordered_roles[-1],),
        (),
    ]
    for fc in fallback_cast_combos:
        if len(selected_states) >= target_room_anchors:
            break
        cand_key = (default_loc, fc)
        if cand_key not in selected_states:
            selected_states.append(cand_key)

    hero_prop = plan["environment_props"][0]
    secondary_prop = plan["environment_props"][1] if len(plan["environment_props"]) > 1 else hero_prop
    track_a_shots = _resolve_track_a_shot_ids(plan, d_dir, project_dir=p_dir) if track == "track_a" else []

    anchors: list[dict[str, Any]] = []
    anchor_by_state: dict[tuple[str, tuple[str, ...]], str] = {}

    for a_idx, (loc_id, p_tuple) in enumerate(selected_states, start=1):
        ref_id = f"ref_anchor_{a_idx:02d}"
        sample_c = state_sample_clip.get((loc_id, p_tuple), {})
        loc_env = (
            loc_env_texts[loc_id].most_common(1)[0][0]
            if (loc_id in loc_env_texts and loc_env_texts[loc_id])
            else (
                sanitize_porcelain_contract_text(str(sample_c.get("environment") or ""))
                or existing_env
            )
        )
        cam_lead = _ANCHOR_CAMERA_VARIANTS[(a_idx - 1) % len(_ANCHOR_CAMERA_VARIANTS)]
        # Avoid injecting primary room's historical prop into a secondary room from a different era/location
        if loc_id == default_loc:
            prop_focus = hero_prop if (a_idx % 2 == 1) else secondary_prop
            featuring_clause = f", featuring {prop_focus}"
            beside_target = prop_focus
        else:
            prop_focus = "an unmarked clinical tabletop apparatus"
            featuring_clause = ""
            beside_target = "the central tabletop workspace"

        if p_tuple:
            cast_clauses = [
                f"{r} ({cast_dict.get(r, _DEFAULT_ROLE_WARDROBE.get(r, r))})"
                for r in p_tuple
            ]
            cast_prose = (
                f"Inside the room, {', '.join(cast_clauses)} positioned naturally beside {beside_target}."
            )
        else:
            cast_prose = f"The room is completely unoccupied, showcasing {beside_target} in crisp architectural stillness."

        cond_list: list[str] = []
        if track_a_shots and p_tuple:
            for r in p_tuple:
                cid = f"ref_cast_{r}"
                if r in cast_dict and cid not in cond_list and len(cond_list) < 2:
                    cond_list.append(cid)
            if loc_id == default_loc and "ref_env_master" not in cond_list and len(cond_list) < 2:
                cond_list.append("ref_env_master")
        else:
            if loc_id == default_loc:
                cond_list.append("ref_env_master")
            for r in p_tuple:
                cid = f"ref_cast_{r}"
                if r in cast_dict and cid not in cond_list and len(cond_list) < 2:
                    cond_list.append(cid)
        if not cond_list:
            cond_list.append("ref_env_master")

        sc_id = (
            track_a_shots[(a_idx - 1) % len(track_a_shots)]
            if track_a_shots
            else f"LOC_{loc_id}"
        )
        prompt_txt = sanitize_porcelain_contract_text(
            f"Generate a single 9:16 vertical still photograph (one frozen instant, not a video): "
            f"{cam_lead} {loc_env}{featuring_clause}. {cast_prose} "
            f"Bright high-key sunlit architectural studio daylight, smooth featureless blank matte-white oval porcelain heads, "
            f"clean unmarked walls, deep depth of field, zero text, zero letters, zero numbers, no watermark."
        )
        anchor_entry: dict[str, Any] = {
            "ref_id": ref_id,
            "filename": f"{ref_id}.png",
            "category": "clip_keyframe_anchor",
            "role": "reenactment",
            "scene_id": sc_id,
            "location_id": loc_id,
            "present_cast": list(p_tuple),
            "setting": "real_env",
            "generation_order": 3,
            "conditioned_on": cond_list[:2],
            "title": (
                f"Shot {sc_id} anchor {a_idx} ({loc_id}: {', '.join(p_tuple) if p_tuple else 'empty'})"
                if track_a_shots
                else f"Room state anchor {a_idx} ({loc_id}: {', '.join(p_tuple) if p_tuple else 'empty'})"
            ),
            "prompt": prompt_txt,
            "must_include": [loc_env[:72], prop_focus[:56]],
        }
        if track_a_shots:
            anchor_entry["frame"] = "start"
        anchors.append(anchor_entry)
        if (loc_id, p_tuple) not in anchor_by_state:
            anchor_by_state[(loc_id, p_tuple)] = ref_id

    plan["reference_anchors"] = anchors

    # 6. Selective clip-to-reference binding (zero wide-frame portrait lock on hand/prop closeups!)
    lab_clips_for_shots: list[dict[str, Any]] = []
    for c in clips:
        g_name = str(c.get("grammar") or "").strip()
        c_role = str(c.get("cut_role") or "").strip().lower()
        c.pop("end_reference_image", None)

        is_brain_or_split = (
            g_name in ("porcelain_living_brain", "porcelain_data_sculpture", "lowpoly_living_brain", "lowpoly_data_sculpture")
            or bool(c.get("brain_mode"))
            or c.get("setting") in (*BRAIN_SETTINGS, "brain_studio")
            or c_role in ("split_left", "split_right", "split_top", "split_bottom")
        )
        if not is_brain_or_split and c_role != "outro":
            lab_clips_for_shots.append(c)
        elif track != "track_a":
            c.pop("source_shot_id", None)

        if c_role == "outro":
            c.pop("reference_image", None)
            c.pop("source_shot_id", None)
            continue

        if g_name == "porcelain_living_brain" and has_brain_master:
            b_mode = str(c.get("brain_mode") or "").strip()
            if b_mode != "bounded_micro_channel":
                c["reference_image"] = f"03_visuals/{REF_IMAGES_DIRNAME}/ref_brain_master.png"
            else:
                c.pop("reference_image", None)
            continue

        if g_name in ("porcelain_fullbleed_world", "porcelain_cutaway_section"):
            st = c.get("scene_state") or {}
            loc = str(st.get("location_id") or c.get("location_id") or default_loc).strip()
            p_start = tuple(sorted({str(x).strip() for x in (st.get("present_cast_start") or []) if str(x).strip()}))
            matched_rid = anchor_by_state.get((loc, p_start))
            if not matched_rid:
                for (aloc, ap_tuple), cand_rid in anchor_by_state.items():
                    if aloc == loc and set(ap_tuple).issubset(set(p_start)):
                        matched_rid = cand_rid
                        break
            if matched_rid:
                c["reference_image"] = f"03_visuals/{REF_IMAGES_DIRNAME}/{matched_rid}.png"
            elif loc == default_loc:
                c["reference_image"] = f"03_visuals/{REF_IMAGES_DIRNAME}/ref_env_master.png"
            else:
                c.pop("reference_image", None)
            continue

        # Macro closeups (`porcelain_hands_closeup`, `porcelain_pov_hands`), literal analogies, data sculptures -> unanchored
        c.pop("reference_image", None)

    if track == "track_a" and track_a_shots and lab_clips_for_shots:
        n_lab = len(lab_clips_for_shots)
        n_shots = len(track_a_shots)
        for idx_lc, lc in enumerate(lab_clips_for_shots):
            existing_sid = str(lc.get("source_shot_id") or "").strip()
            if existing_sid not in track_a_shots:
                lc["source_shot_id"] = track_a_shots[min(n_shots - 1, (idx_lc * n_shots) // max(1, n_lab))]
    elif track != "track_a":
        for lc in lab_clips_for_shots:
            lc.pop("source_shot_id", None)

    return plan


def _persist_plan_and_prompts(p_dir: Path, plan: dict[str, Any]) -> None:
    from pipeline.flow_prompt_builder import build_flow_prompts, write_flow_prompts_json

    vis_dir = p_dir / "03_visuals"
    vis_dir.mkdir(parents=True, exist_ok=True)
    vp_path = vis_dir / "visual_plan.json"
    vp_path.write_text(json.dumps(plan, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    scr_path = p_dir / "02_script" / "script.json"
    if scr_path.exists():
        s_doc = json.loads(scr_path.read_text(encoding="utf-8"))
        sents = [str(x) for x in (s_doc.get("sentences") or s_doc.get("clip_narrations") or []) if str(x).strip()]
        if sents and plan.get("clips"):
            write_flow_prompts_json(p_dir, build_flow_prompts(plan, sents))


def _reference_specs_cover_plan(
    vis_dir: Path,
    ref_dir: Path,
    plan: dict[str, Any],
) -> bool:
    """Returns True iff `reference_image_specs.json` covers every non-placeholder anchor in `plan` and its PNG exists."""
    specs_file = vis_dir / "reference_image_specs.json"
    if not specs_file.exists():
        return False
    try:
        on_disk_specs = json.loads(specs_file.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return False
    spec_pairs = {
        (str(s.get("ref_id") or ""), str(s.get("filename") or f"{s.get('ref_id')}.png"))
        for s in (on_disk_specs.get("all_specs") or [])
        if isinstance(s, dict)
    }
    if not spec_pairs:
        return False
    for anc in plan.get("reference_anchors") or []:
        if not isinstance(anc, dict) or bool(anc.get("seeded_placeholder")):
            continue
        fn_a = str(anc.get("filename") or (f"{anc['ref_id']}.png" if anc.get("ref_id") else "")).strip()
        if not fn_a:
            continue
        fn_clean = Path(fn_a).name
        rid_a = str(anc.get("ref_id") or Path(fn_clean).stem).strip()
        if (rid_a, fn_clean) not in spec_pairs or not (ref_dir / fn_clean).exists():
            return False
    return True


def ensure_porcelain_reference_pack(
    project_dir: str | Path,
    dossier_dir: str | Path | None = None,
    *,
    cdp_port: int = DEFAULT_CDP_PORT,
    backend: str = DEFAULT_REENACT_IMAGE_BACKEND,
    batch_count: int = FLOW_ZERO_CREDIT_IMAGE_BATCH_COUNT,
    force: bool = False,
    require_review: bool = False,
    auto_populate_review: bool = False,
    synthesize_scene_anchors: bool = False,
) -> dict[str, Any]:
    """
    Ensures all required `porcelain_cinematic_v7` reference PNGs exist in `03_visuals/reference_images/`
    and pass `inspect_reference_image_pack` (`pre_generation_ready == True`), generating any missing or
    failed anchors via `0-credit` Google Flow `Image` (`Nano Banana 2.1`, `x4` batch) in `1 -> 2 -> 3` order.
    """
    from pipeline.config import REENACT_IMAGE_BACKENDS
    from pipeline.flow_prompt_builder import load_visual_plan
    from pipeline.reference_image_qa import (
        auto_populate_reference_semantic_review,
        build_and_verify_project_reference_pack,
        inspect_reference_image_pack,
    )
    from pipeline.source_reenactment import (
        extract_source_edl,
        purge_reenactment_quarantine,
        sanitize_structural_frames,
        translate_porcelain_keyframes,
    )

    eff_backend = str(backend or DEFAULT_REENACT_IMAGE_BACKEND).strip().lower()
    if eff_backend not in REENACT_IMAGE_BACKENDS:
        raise ValueError(
            f"Unsupported reference image backend: {backend!r} (expected one of {REENACT_IMAGE_BACKENDS})"
        )

    p_dir = Path(project_dir) if Path(project_dir).is_dir() else (Path(PROJECTS_DIR) / str(project_dir))
    if not p_dir.exists():
        raise FileNotFoundError(f"Project directory not found: {p_dir}")

    vis_dir = p_dir / "03_visuals"
    vp_path = vis_dir / "visual_plan.json"
    plan = load_visual_plan(project_dir=p_dir)
    if is_expressive_v8_plan(plan):
        return ensure_expressive_v8_reference_pack(
            p_dir,
            dossier_dir=dossier_dir,
            cdp_port=cdp_port,
            backend=backend,
            batch_count=batch_count,
            force=force,
            require_review=require_review,
            auto_populate_review=auto_populate_review,
            synthesize_scene_anchors=synthesize_scene_anchors,
        )
    if not is_porcelain_v7_plan(plan):
        return {"skipped": True, "reason": "not_porcelain_cinematic_v7", "project_id": p_dir.name}

    slug = str(plan.get("dossier_slug") or plan.get("dossier") or p_dir.name).strip()
    d_dir: Path | None = None
    if dossier_dir is not None and Path(dossier_dir).exists():
        d_dir = Path(dossier_dir)
    elif slug and (Path(DOSSIERS_DIR) / slug).exists():
        d_dir = Path(DOSSIERS_DIR) / slug

    # Fast cached check before mutating or opening browser
    if not force and _reference_specs_cover_plan(vis_dir, vis_dir / REF_IMAGES_DIRNAME, plan):
        cached_qa = inspect_reference_image_pack(p_dir, save_report=True, require_review=require_review)
        if cached_qa.get("pre_generation_ready"):
            return {
                "skipped": False,
                "cached": True,
                "project_id": p_dir.name,
                "slug": slug,
                "reenactment_track": str(plan.get("reenactment_track") or "track_b"),
                "pre_generation_ready": True,
                "cv_pre_generation_ready": cached_qa.get("cv_pre_generation_ready"),
                "reference_qa_score": cached_qa.get("reference_qa_score"),
                "total_images": cached_qa.get("total_existing"),
            }

    before_plan_txt = json.dumps(plan, sort_keys=True, ensure_ascii=False)
    populate_porcelain_reference_contract(plan, dossier_dir=d_dir, project_dir=p_dir)
    if vp_path.exists() and json.dumps(plan, sort_keys=True, ensure_ascii=False) != before_plan_txt:
        _persist_plan_and_prompts(p_dir, plan)

    track = str(plan.get("reenactment_track") or "track_b").strip().lower()
    q_dir = Path(REENACT_QUARANTINE_ROOT) / slug
    used_quarantine = False

    try:
        if track == "track_a":
            edl_path = vis_dir / REENACT_EDL_FILENAME
            if not edl_path.exists() and d_dir and (d_dir / "08_reenactment_edl.json").exists():
                edl_doc = json.loads((d_dir / "08_reenactment_edl.json").read_text(encoding="utf-8"))
                edl_path.write_text(json.dumps(edl_doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

            ref_dir_check = vis_dir / REF_IMAGES_DIRNAME
            need_shot_anchors = [
                a
                for a in (plan.get("reference_anchors") or [])
                if isinstance(a, dict)
                and str(a.get("scene_id") or "").startswith("S")
                and (force or not (ref_dir_check / str(a.get("filename") or f"{a.get('ref_id')}.png")).exists())
            ]
            guides_ready = (q_dir / "guides").is_dir() and any((q_dir / "guides").glob("S*_guide.png"))
            if not guides_ready and need_shot_anchors:
                if not (d_dir and (d_dir / "04_media_refs.json").exists()):
                    raise RuntimeError(
                        f"[porcelain-refs] Track A fail-closed: missing 04_media_refs.json for {slug} while {len(need_shot_anchors)} shot anchors require structural guides."
                    )
                from pipeline.research_dossier import audit_dossier_media_suitability

                suit = audit_dossier_media_suitability(d_dir, write_back=False)
                best_media = suit.get("primary_track_a_media")
                if not (best_media and best_media.get("url")):
                    raise RuntimeError(
                        f"[porcelain-refs] Track A fail-closed: no suitable_track_a archival media URL found for {slug}; refusing silent Track B fallback."
                    )
                used_quarantine = True
                edl_doc = extract_source_edl(
                    best_media["url"],
                    slug=slug,
                    project_dir=p_dir,
                    dossier_dir=d_dir,
                    section=best_media.get("reenactment_section") or best_media.get("recommended_section") or best_media.get("section"),
                )
                sanitize_structural_frames(
                    work_dir=q_dir,
                    edl_doc=edl_doc,
                    project_dir=p_dir,
                    dossier_dir=d_dir,
                )
                if not ((q_dir / "guides").is_dir() and any((q_dir / "guides").glob("S*_guide.png"))):
                    raise RuntimeError(
                        f"[porcelain-refs] Track A fail-closed: sanitize_structural_frames produced zero S*_guide.png files for {slug}."
                    )
                # Re-align `S01..S0K` shot IDs in plan & prompts with freshly extracted source_edl.json
                populate_porcelain_reference_contract(plan, dossier_dir=d_dir, project_dir=p_dir)
                if vp_path.exists():
                    _persist_plan_and_prompts(p_dir, plan)

        gen_summary = translate_porcelain_keyframes(
            project_dir=p_dir,
            slug=slug,
            cdp_port=cdp_port,
            force=force,
            backend=backend,
            batch_count=batch_count,
        )
    finally:
        if used_quarantine or q_dir.exists():
            purge_reenactment_quarantine(slug)

    if auto_populate_review:
        auto_populate_reference_semantic_review(p_dir)

    qa_rep = build_and_verify_project_reference_pack(
        p_dir,
        dossier_dir=d_dir,
        require_review=require_review,
        auto_populate_review=auto_populate_review,
    )
    return {
        "skipped": False,
        "cached": False,
        "project_id": p_dir.name,
        "slug": slug,
        "reenactment_track": track,
        "generation": gen_summary,
        "pre_generation_ready": bool(qa_rep.get("pre_generation_ready")),
        "cv_pre_generation_ready": bool(qa_rep.get("cv_pre_generation_ready")),
        "reference_qa_score": qa_rep.get("reference_qa_score"),
        "regenerate_image_ids": qa_rep.get("regenerate_image_ids") or [],
        "total_images": qa_rep.get("total_existing"),
    }


def ensure_expressive_v8_reference_pack(
    project_dir: str | Path,
    dossier_dir: str | Path | None = None,
    *,
    cdp_port: int = DEFAULT_CDP_PORT,
    backend: str = DEFAULT_REENACT_IMAGE_BACKEND,
    batch_count: int = FLOW_ZERO_CREDIT_IMAGE_BATCH_COUNT,
    force: bool = False,
    require_review: bool = False,
    auto_populate_review: bool = True,
    synthesize_scene_anchors: bool = False,
) -> dict[str, Any]:
    """
    Stages the 6 pre-verified `expressive_25d_v8` (`안 1 + 안 3 결합형`) Flow-generated master reference PNGs
    from `BCI_Shorts_Channel/reference_style_anchors/expressive_25d_v8_refs/` into `03_visuals/reference_images/`,
    generates any custom episode `reference_anchors` (e.g. `daisy_chain_bridge` `Start+End` keyframes) via
    `0-credit` Flow `Image` (`x4` batch) if missing, and verifies `pre_generation_ready == True`.
    """
    import shutil

    from pipeline.flow_prompt_builder import load_visual_plan
    from pipeline.reference_image_qa import (
        auto_populate_reference_semantic_review,
        build_and_verify_project_reference_pack,
        inspect_reference_image_pack,
        register_reference_image,
    )
    from pipeline.source_reenactment import translate_porcelain_keyframes

    p_dir = Path(project_dir) if Path(project_dir).is_dir() else (Path(PROJECTS_DIR) / str(project_dir))
    if not p_dir.exists():
        raise FileNotFoundError(f"Project directory not found: {p_dir}")

    vis_dir = p_dir / "03_visuals"
    ref_dir = vis_dir / REF_IMAGES_DIRNAME
    ref_dir.mkdir(parents=True, exist_ok=True)
    vp_path = vis_dir / "visual_plan.json"
    plan = load_visual_plan(project_dir=p_dir)
    slug = str(plan.get("dossier_slug") or plan.get("dossier") or p_dir.name).strip()
    d_dir: Path | None = None
    if dossier_dir is not None and Path(dossier_dir).exists():
        d_dir = Path(dossier_dir)
    elif slug and (Path(DOSSIERS_DIR) / slug).exists():
        d_dir = Path(DOSSIERS_DIR) / slug

    import copy

    before_plan_txt = json.dumps(plan, sort_keys=True, ensure_ascii=False)
    preview_plan = copy.deepcopy(plan)
    populate_expressive_v8_reference_contract(
        preview_plan,
        dossier_dir=d_dir,
        project_dir=p_dir,
        synthesize_scene_anchors=synthesize_scene_anchors,
    )
    plan_unchanged = json.dumps(preview_plan, sort_keys=True, ensure_ascii=False) == before_plan_txt
    if not force and plan_unchanged and _reference_specs_cover_plan(vis_dir, ref_dir, preview_plan):
        cached_qa = inspect_reference_image_pack(p_dir, save_report=True, require_review=require_review)
        if cached_qa.get("pre_generation_ready"):
            return {
                "skipped": False,
                "cached": True,
                "project_id": p_dir.name,
                "slug": slug,
                "style_profile": EXPRESSIVE_25D_V8_STYLE_PROFILE,
                "reenactment_track": str(plan.get("reenactment_track") or "track_b"),
                "pre_generation_ready": True,
                "cv_pre_generation_ready": cached_qa.get("cv_pre_generation_ready"),
                "reference_qa_score": cached_qa.get("reference_qa_score"),
                "total_images": cached_qa.get("total_existing"),
            }

    plan.clear()
    plan.update(preview_plan)
    if vp_path.exists() and not plan_unchanged:
        _persist_plan_and_prompts(p_dir, plan)

    master_src_dir = Path(CHANNEL_ROOT) / "reference_style_anchors" / EXPRESSIVE_V8_REFS_DIRNAME
    master_files = (
        EXPRESSIVE_V8_SPECIES_SHEET_FILENAME,
        EXPRESSIVE_V8_CAMEO_SHEET_FILENAME,
        "xray_brain75_master.png",
        "expressive_conflict_master.png",
        "cast_sheet_02_clinical_historical_6roles.png",
        "cast_sheet_03_everyday_lifestyle_6roles.png",
    )
    staged_masters: list[str] = []
    for fname in master_files:
        src_f = master_src_dir / fname
        dst_f = ref_dir / fname
        if src_f.exists():
            if force or not dst_f.exists() or dst_f.stat().st_size != src_f.stat().st_size:
                shutil.copy2(src_f, dst_f)
            register_reference_image(p_dir, fname, "flow_image_generation")
            staged_masters.append(fname)

    gen_summary: dict[str, Any] = {"staged_masters": staged_masters, "generated_custom": 0}
    custom_anchors = [
        a
        for a in (plan.get("reference_anchors") or [])
        if isinstance(a, dict)
        and str(a.get("filename") or f"{a.get('ref_id')}.png") not in set(master_files)
        and (force or not (ref_dir / str(a.get("filename") or f"{a.get('ref_id')}.png")).exists())
    ]
    if custom_anchors:
        custom_ref_ids = {
            str(a.get("ref_id") or Path(str(a.get("filename") or f"ref_clip_{i:02d}.png")).stem)
            for i, a in enumerate(custom_anchors, start=1)
        }
        gen_summary["custom_translation"] = translate_porcelain_keyframes(
            project_dir=p_dir,
            slug=slug,
            cdp_port=cdp_port,
            only_ref_ids=custom_ref_ids,
            force=force,
            backend=backend,
            batch_count=batch_count,
        )
        gen_summary["generated_custom"] = len(custom_ref_ids)

    if auto_populate_review:
        auto_populate_reference_semantic_review(p_dir)

    qa_rep = build_and_verify_project_reference_pack(
        p_dir,
        dossier_dir=d_dir,
        require_review=require_review,
        auto_populate_review=auto_populate_review,
    )
    return {
        "skipped": False,
        "cached": False,
        "project_id": p_dir.name,
        "slug": slug,
        "style_profile": EXPRESSIVE_25D_V8_STYLE_PROFILE,
        "reenactment_track": str(plan.get("reenactment_track") or "track_b"),
        "generation": gen_summary,
        "pre_generation_ready": bool(qa_rep.get("pre_generation_ready")),
        "cv_pre_generation_ready": bool(qa_rep.get("cv_pre_generation_ready")),
        "reference_qa_score": qa_rep.get("reference_qa_score"),
        "regenerate_image_ids": qa_rep.get("regenerate_image_ids") or [],
        "total_images": qa_rep.get("total_existing"),
    }


__all__ = [
    "ensure_expressive_v8_reference_pack",
    "ensure_porcelain_reference_pack",
    "normalize_strict_room_continuity_ledger",
    "populate_expressive_v8_reference_contract",
    "populate_porcelain_reference_contract",
    "sanitize_porcelain_contract_text",
]
