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
    DEFAULT_CDP_PORT,
    DEFAULT_REENACT_IMAGE_BACKEND,
    DOSSIERS_DIR,
    FLOW_ZERO_CREDIT_IMAGE_BATCH_COUNT,
    MIN_REF_IMAGES_PER_PROJECT,
    PROJECTS_DIR,
    REF_IMAGES_DIRNAME,
    REENACT_EDL_FILENAME,
    REENACT_QUARANTINE_ROOT,
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


def populate_porcelain_reference_contract(
    plan: dict[str, Any],
    dossier_dir: str | Path | None = None,
    *,
    preserve_curated_source_edl: bool = True,
    project_dir: str | Path | None = None,
) -> dict[str, Any]:
    """
    Compiles the complete `porcelain_cinematic_v7` reference-conditioning contract onto `plan` (in-place & returned):
      - `reenactment_track` (`"track_a"` or `"track_b"`)
      - `default_location_id`, `cast`, `real_environment`, `environment_props`
      - `require_scene_state_ledger: True`, `strict_room_continuity: True`
      - `reference_anchors` (`6–9` total reference PNG specs across masters + room/shot anchors)
      - Selective room/brain `clip["reference_image"]` bindings (zero closeup full-body wide locks)
      - Track A `clip["source_shot_id"]` blocking alignment across `S01..S0N`
    """
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
) -> dict[str, Any]:
    """
    Ensures all required `porcelain_cinematic_v7` reference PNGs exist in `03_visuals/reference_images/`
    and pass `inspect_reference_image_pack` (`pre_generation_ready == True`), generating any missing or
    failed anchors via `0-credit` Google Flow `Image` (`Nano Banana 2.1`, `x4` batch) in `1 -> 2 -> 3` order.
    """
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

    p_dir = Path(project_dir) if Path(project_dir).is_dir() else (Path(PROJECTS_DIR) / str(project_dir))
    if not p_dir.exists():
        raise FileNotFoundError(f"Project directory not found: {p_dir}")

    vis_dir = p_dir / "03_visuals"
    vp_path = vis_dir / "visual_plan.json"
    plan = load_visual_plan(project_dir=p_dir)
    if not is_porcelain_v7_plan(plan):
        return {"skipped": True, "reason": "not_porcelain_cinematic_v7", "project_id": p_dir.name}

    slug = str(plan.get("dossier_slug") or plan.get("dossier") or p_dir.name).strip()
    d_dir: Path | None = None
    if dossier_dir is not None and Path(dossier_dir).exists():
        d_dir = Path(dossier_dir)
    elif slug and (Path(DOSSIERS_DIR) / slug).exists():
        d_dir = Path(DOSSIERS_DIR) / slug

    # Fast cached check before mutating or opening browser
    if not force and (vis_dir / "reference_image_specs.json").exists():
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


__all__ = [
    "ensure_porcelain_reference_pack",
    "normalize_strict_room_continuity_ledger",
    "populate_porcelain_reference_contract",
    "sanitize_porcelain_contract_text",
]
