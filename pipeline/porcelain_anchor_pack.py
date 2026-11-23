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
         `x1` first-pass / `x2` retry per prompt, auto-selecting the top `Q1..Q7` candidate) in strict `1 -> 2 -> 3` order,
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
    is_r72_open_world_v8_plan,
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
    "Medium side-angle locked-off architectural framing across",
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
        except Exception as exc:
            import logging

            logging.getLogger("porcelain_anchor_pack").warning(
                "Failed reading %s in %s: %s", REENACT_EDL_FILENAME, project_dir, exc
            )
    if d_dir is not None and (d_dir / "08_reenactment_edl.json").exists():
        try:
            candidates.append(json.loads((d_dir / "08_reenactment_edl.json").read_text(encoding="utf-8")))
        except Exception as exc:
            import logging

            logging.getLogger("porcelain_anchor_pack").warning(
                "Failed reading 08_reenactment_edl.json in %s: %s", d_dir, exc
            )
    for doc in candidates:
        if isinstance(doc, dict):
            s_ids = [str(s.get("shot_id")).strip() for s in (doc.get("shots") or []) if isinstance(s, dict) and s.get("shot_id")]
            if s_ids:
                return s_ids
    return ["S01", "S02", "S03", "S04"]


_PARALLAX_3D_CAMERA_MOVES: frozenset[str] = frozenset(
    {
        "orbital_3d_arc_sweep",
        "crane_swoop_dive",
        "dolly_zoom_vertigo",
        "axial_portal_dive",
        "portal_dive_flight",
        "clean_pullback_reveal",
        "fpv_3d_flight",
        "fpv_dive_glide",
        "top_down_overhead",
        "low_angle_hero",
    }
)


def select_hybrid_previs_hero_cuts(
    clips: list[dict[str, Any]],
    *,
    min_cuts: int = 6,
    max_cuts: int = 10,
) -> list[int]:
    """
    P4 Hybrid `v8` Previs Selector: Selects `6..10` high-value cuts per episode whose spatial
    composition benefits most from 3D Previs keyframe conditioning (Act 1 hook, 2+ person staging,
    compound-prop closeups, and 3D parallax camera trajectories).
    """
    scored: list[tuple[int, int, int]] = []
    seen_acts: set[int] = set()
    for idx_c, c_item in enumerate(clips, start=1):
        if not isinstance(c_item, dict):
            continue
        g_raw = str(c_item.get("grammar") or c_item.get("visual_grammar") or "").strip().lower()
        c_is_cameo = bool(c_item.get("cameo_easter_egg")) or g_raw == "expressive_cameo_world"
        c_is_brain = bool(c_item.get("brain_clip")) or g_raw in ("expressive_xray_brain", "porcelain_living_brain")
        if c_is_cameo or (c_is_brain and not bool(c_item.get("portal_to_brain"))):
            continue
        c_num = int(c_item.get("clip_number") or idx_c)
        pv = c_item.get("previs") if isinstance(c_item.get("previs"), dict) else {}
        cam_move = str(c_item.get("camera_movement") or c_item.get("camera_move") or "").strip().lower()
        act_num = int(c_item.get("act") or ((idx_c - 1) // 4 + 1))

        score = 0
        if idx_c == 1:
            score += 60
        if len(pv.get("actors") or []) >= 2:
            score += 32
        if cam_move in _PARALLAX_3D_CAMERA_MOVES or any(k in cam_move for k in ("orbit", "crane", "dolly_zoom", "portal", "pullback", "fpv")):
            score += 28
        if any(k in g_raw for k in ("hands_closeup", "pov_hands", "literal_analogy")):
            score += 24
        if len(pv.get("props") or []) >= 1:
            score += 14
        if act_num not in seen_acts:
            score += 8
            seen_acts.add(act_num)
        scored.append((score, -idx_c, c_num))

    if not scored:
        return []
    scored.sort(reverse=True)
    target_n = min(max_cuts, max(min(min_cuts, len(scored)), min(max_cuts, max(min_cuts, round(len(clips) * 0.40)))))
    target_n = min(len(scored), target_n)
    return sorted(c_num for _sc, _neg_i, c_num in scored[:target_n])


def select_dual_parallax_highlight_cuts(
    clips: list[dict[str, Any]],
    hero_cut_nums: set[int],
    *,
    min_cuts: int = 3,
    max_cuts: int = 5,
) -> list[int]:
    """
    P6 Dual-Keyframe (`Start + End` `VIDEO_FRAMES`) 3D Parallax Selector:
    Picks `3..5` highlight 3D camera-move cuts among `hero_cut_nums` where `camera_start != camera_end`
    (excluding `portal_to_brain` cuts which already end on `ref_xray_brain_9x16.png`).
    """
    from pipeline.config import EXPRESSIVE_V8_NEURAL_DIVE_MOVES

    candidates: list[tuple[int, int, int]] = []
    for idx_c, c_item in enumerate(clips, start=1):
        if not isinstance(c_item, dict):
            continue
        c_num = int(c_item.get("clip_number") or idx_c)
        if c_num not in hero_cut_nums or bool(c_item.get("portal_to_brain")):
            continue
        g_raw = str(c_item.get("grammar") or c_item.get("visual_grammar") or "").strip().lower()
        cam_move = str(c_item.get("camera_movement") or c_item.get("camera_move") or "").strip().lower()
        is_r74_dual_dive = cam_move in (
            "neural_fpv_dive_in",
            "neural_fpv_pullback_out",
            "neural_tract_relay_flight",
        )
        if not is_r74_dual_dive and (
            bool(c_item.get("brain_clip"))
            or g_raw in ("expressive_xray_brain", "porcelain_living_brain", "expressive_cameo_world")
        ):
            continue
        pv = c_item.get("previs") if isinstance(c_item.get("previs"), dict) else {}
        if not is_r74_dual_dive and (not pv or pv.get("camera_start") == pv.get("camera_end")):
            continue
        prio = 0
        if is_r74_dual_dive:
            prio = 60
        elif "orbit" in cam_move or "arc" in cam_move:
            prio = 50
        elif "crane" in cam_move or "swoop" in cam_move:
            prio = 45
        elif "dolly_zoom" in cam_move or "vertigo" in cam_move:
            prio = 42
        elif "pullback" in cam_move or "reveal" in cam_move or "portal" in cam_move or "fpv" in cam_move:
            prio = 38
        elif cam_move in _PARALLAX_3D_CAMERA_MOVES:
            prio = 34
        if prio > 0:
            candidates.append((prio, -idx_c, c_num))

    if not candidates:
        return []
    candidates.sort(reverse=True)
    take_n = min(max_cuts, len(candidates))
    return sorted(c_num for _p, _ni, c_num in candidates[:take_n])


def _compose_v8_non_brain_keyframe_prompt(
    *,
    env_text: str,
    action_clause: str = "",
    camera_desc: str = "",
    closing: bool = False,
    outdoor_architectural: bool = False,
    clip_spec: dict[str, Any] | None = None,
) -> str:
    """Build selective-color + act-lighting 9:16 2.5D vinyl keyframe prompt (P0-2) without grayscale collapse."""
    from pipeline.depiction_rules import SELECTIVE_COLOR_BACKDROP_CLAUSE, resolve_act_lighting_hint

    spec = clip_spec if isinstance(clip_spec, dict) else {}
    kind = "closing keyframe" if closing else "scene"
    cam_seg = f" ({camera_desc})" if camera_desc else ""
    act_hint = (
        spec.get("act_index")
        if spec.get("act_index") is not None
        else (spec.get("act") or spec.get("act_role") or spec.get("narrative_act"))
    )
    if outdoor_architectural:
        lighting_seg = (
            "crisp sunlit architectural daylight casting tactile 3D shadows across stone, foliage, and pavement, "
            "deep f/8 focus, zero text."
        )
    elif act_hint is not None and str(act_hint).strip():
        lighting_seg = f"{resolve_act_lighting_hint(act_hint)}, cinema key-and-rim depth, zero text."
    else:
        lighting_seg = "cinema key-and-rim lighting, zero text."
    low_env = f"{env_text} {action_clause}".lower()
    sc_seg = (
        ""
        if ("low-saturation" in low_env or "isolating the vivid" in low_env)
        else f", {SELECTIVE_COLOR_BACKDROP_CLAUSE}"
    )
    return (
        f"Single full-bleed vertical 9:16 3D miniature diorama {kind}{cam_seg} of {env_text}{action_clause}"
        " with a clothed smooth featureless matte-white architectural porcelain figure framed via "
        f"back or three-quarter silhouette, hands-only close-up, or translucent Mode 1 x-ray cranium{sc_seg}, {lighting_seg}"
    )


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
                "clothed smooth featureless matte-white architectural porcelain figure, "
                "framed via back or three-quarter silhouette, hands-only close-up, or translucent Mode 1 x-ray cranium, "
                "wearing tailored 3D woven everyday attire"
            ),
            "foil": (
                "clothed smooth featureless matte-white architectural porcelain foil figure, "
                "framed in back or three-quarter silhouette, wearing crisp 3D structured jacket attire"
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

    from pipeline.config import EXPRESSIVE_V8_NEURAL_DIVE_MOVES

    has_r74_dive_clips = any(
        isinstance(c_it, dict)
        and (
            bool(c_it.get("neural_dive_relay"))
            or str(c_it.get("camera_move") or c_it.get("camera_movement") or "").strip().lower()
            in EXPRESSIVE_V8_NEURAL_DIVE_MOVES
        )
        for c_it in clips
    )
    use_daisy = bool(
        (daisy_chain_keyframes or plan.get("daisy_chain_keyframes"))
        and not (plan.get("r72_mode") or plan.get("r74_mode") or has_r74_dive_clips)
    )
    auto_synth = bool(
        synthesize_scene_anchors
        or plan.get("auto_scene_anchors")
        or use_daisy
        or plan.get("r72_mode")
        or plan.get("real_world_targets")
        or plan.get("r72_cold_open_relay")
        or plan.get("r74_mode")
        or has_r74_dive_clips
    )
    existing_anchors = [a for a in (plan.get("reference_anchors") or []) if isinstance(a, dict)]
    all_seeded_placeholders = bool(existing_anchors) and all(bool(a.get("seeded_placeholder")) for a in existing_anchors)
    daisy_cam_progression = (
        ("eye_level_medium", "eye-level medium 35mm f/8 deep-focus cinema composition facing the foreground action"),
        ("fpv_aperture_wide", "28mm f/8 deep-focus perspective looking cleanly through a foreground aperture across the room"),
        ("three_quarter_orbit_left", "elevated 35-degree f/8 deep-focus three-quarter left orbit composition with tack-sharp room depth"),
        ("three_quarter_orbit_right", "reverse 35-degree f/8 deep-focus three-quarter right orbit composition showing tack-sharp spatial depth"),
    )
    single_start_only = bool(plan.get("single_start_frame_default") or plan.get("v8_3_mode"))
    if bool(plan.get("auto_previs")) or (synthesize_scene_anchors and clips and not existing_anchors):
        from pipeline.previs_blender import auto_synthesize_plan_previs_specs, render_visual_plan_previs_pack

        auto_synthesize_plan_previs_specs(plan, overwrite=False)
        if project_dir is not None and Path(project_dir).exists():
            pv_dir = Path(project_dir) / "03_visuals" / "previs_guides"
            render_visual_plan_previs_pack(plan, out_dir=pv_dir, auto_populate_missing=True, backend="auto")
    elif any(isinstance(c_it, dict) and isinstance(c_it.get("previs"), dict) for c_it in clips):
        from pipeline.previs_blender import propagate_previs_camera_continuity, render_visual_plan_previs_pack

        propagate_previs_camera_continuity(plan)
        if project_dir is not None and Path(project_dir).exists():
            missing_pv_png = any(
                isinstance(c_it, dict)
                and isinstance(c_it.get("previs"), dict)
                and not c_it["previs"].get("start_previs_png")
                for c_it in clips
            )
            if missing_pv_png:
                pv_dir = Path(project_dir) / "03_visuals" / "previs_guides"
                render_visual_plan_previs_pack(plan, out_dir=pv_dir, auto_populate_missing=False, backend="auto")
    if use_daisy and clips and (not existing_anchors or all_seeded_placeholders):
        daisy_anchors: list[dict[str, Any]] = []
        brain_seen_count = 0
        for idx_c, c_item in enumerate(clips, start=1):
            g_raw = str(c_item.get("grammar") or c_item.get("visual_grammar") or "")
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
                            "prompt": _compose_v8_non_brain_keyframe_prompt(
                                env_text=env_txt,
                                action_clause=act_clause,
                                camera_desc=cam_desc,
                                clip_spec=c_item,
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
                        "conditioned_on": ["xray_brain75_master"],
                        "prompt": (
                            "Single full-bleed vertical 9:16 medical-grade 3D neuroanatomy scene in a deep midnight-navy "
                            "studio void (#050811): an isolated semi-transparent frosted-glass 3D human brain (folded cerebral "
                            "cortex gyri and sulci, cerebellum, brainstem) with glowing internal subcortical hubs (crimson-red, "
                            "electric cyan-blue, warm amber-gold), zero mannequin head, zero face, zero bell jar, zero text."
                        ),
                    }
                )
            else:
                fname_k = f"kf_{idx_c:02d}_{loc_k[:22]}_{cam_tag}_9x16.png"
                pv_meta = c_item.get("previs") if isinstance(c_item.get("previs"), dict) else {}
                anc_k: dict[str, Any] = {
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
                    "prompt": _compose_v8_non_brain_keyframe_prompt(
                        env_text=env_txt,
                        action_clause=act_clause,
                        camera_desc=cam_desc,
                        clip_spec=c_item,
                    ),
                }
                if pv_meta.get("start_previs_png"):
                    anc_k["previs_guide_png"] = str(pv_meta["start_previs_png"])
                if pv_meta.get("color_role_legend"):
                    anc_k["color_role_legend"] = dict(pv_meta["color_role_legend"])
                daisy_anchors.append(anc_k)

                pv_end_png = str(pv_meta.get("end_previs_png") or "").strip()
                pv_start_png = str(pv_meta.get("start_previs_png") or "").strip()
                pv_cam_moved = pv_meta.get("camera_start") != pv_meta.get("camera_end")
                has_same_loc_daisy_next = False
                if idx_c < len(clips):
                    nxt_item = clips[idx_c]
                    nxt_g = str(nxt_item.get("grammar") or nxt_item.get("visual_grammar") or "")
                    nxt_cameo = bool(nxt_item.get("cameo_easter_egg")) or nxt_g == "expressive_cameo_world"
                    nxt_brain = bool(nxt_item.get("brain_clip")) or nxt_g in ("expressive_xray_brain", "porcelain_living_brain")
                    nxt_loc = re.sub(
                        r"[^a-z0-9_]+",
                        "_",
                        str(nxt_item.get("location_id") or plan["default_location_id"]).strip().lower(),
                    ).strip("_") or str(plan["default_location_id"])
                    if (not nxt_cameo) and (not nxt_brain or bool(nxt_item.get("portal_to_brain"))) and nxt_loc == loc_k:
                        has_same_loc_daisy_next = True
                if pv_end_png and (pv_end_png != pv_start_png or pv_cam_moved) and not has_same_loc_daisy_next:
                    end_cam_tag, end_cam_desc = daisy_cam_progression[idx_c % len(daisy_cam_progression)]
                    fname_end_k = f"kf_{idx_c:02d}_{loc_k[:22]}_end_9x16.png"
                    anc_end_k: dict[str, Any] = {
                        "ref_id": Path(fname_end_k).stem,
                        "filename": fname_end_k,
                        "clip_number": idx_c,
                        "frame": "end",
                        "category": "clip_keyframe_anchor",
                        "role": "reenactment",
                        "setting": "real_env",
                        "location_id": loc_k,
                        "camera_angle_tag": end_cam_tag,
                        "generation_order": 3,
                        "conditioned_on": ["species_opt1_sheet"],
                        "diegetic_text_allowlist": allow_t,
                        "previs_guide_png": pv_end_png,
                        "prompt": _compose_v8_non_brain_keyframe_prompt(
                            env_text=env_txt,
                            action_clause=act_clause,
                            camera_desc=end_cam_desc,
                            closing=True,
                            clip_spec=c_item,
                        ),
                    }
                    if pv_meta.get("color_role_legend"):
                        anc_end_k["color_role_legend"] = dict(pv_meta["color_role_legend"])
                    daisy_anchors.append(anc_end_k)
        plan["reference_anchors"] = daisy_anchors
        plan["daisy_chain_keyframes"] = True
        existing_anchors = daisy_anchors
    elif auto_synth and clips and (not existing_anchors or all_seeded_placeholders):
        synth_anchors: list[dict[str, Any]] = []
        seen_locs: dict[str, dict[str, Any]] = {}
        cameo_clip_pair: tuple[int, dict[str, Any]] | None = None
        brain_clip_pair: tuple[int, dict[str, Any]] | None = None
        is_r72_plan = is_r72_open_world_v8_plan(
            plan,
            project_id=(Path(project_dir).name if project_dir is not None else None),
        )
        from pipeline.previs_blender import is_outdoor_or_architectural_clip

        r72_cold_open_wired = False
        r72_relay_pair: tuple[int, int] | None = None
        c1_is_outdoor = len(clips) >= 2 and (
            is_outdoor_or_architectural_clip(clips[0])
            or bool(clips[0].get("real_world_target_id"))
        )
        c2_is_outdoor_bridge = (not c1_is_outdoor) and len(clips) >= 3 and (
            is_outdoor_or_architectural_clip(clips[1])
            or bool(clips[1].get("real_world_target_id"))
        )
        if is_r72_plan and plan.get("r72_cold_open_relay") is not False:
            if c1_is_outdoor or (bool(plan.get("r72_cold_open_relay")) and not c2_is_outdoor_bridge and len(clips) >= 2):
                r72_relay_pair = (0, 1)
            elif c2_is_outdoor_bridge:
                r72_relay_pair = (1, 2)
        if r72_relay_pair is not None:
            from pipeline.real_world_reference_builder import (
                build_r72_drone_cutaway_prompts,
                extract_episode_real_world_targets,
                resolve_real_world_target_spec,
            )

            ext_i0, cut_i0 = r72_relay_pair
            ext_cnum, cut_cnum = ext_i0 + 1, cut_i0 + 1
            discovered_rw = extract_episode_real_world_targets(dossier=d_dir, visual_plan=plan)
            c_ext_tid = str(clips[ext_i0].get("real_world_target_id") or plan.get("primary_institution") or "").strip()
            if c_ext_tid:
                primary_inst_spec = resolve_real_world_target_spec(c_ext_tid, fallback_category="institution")
            else:
                primary_inst_spec = next(
                    (t for t in discovered_rw if str(t.get("category") or "") == "institution"),
                    discovered_rw[0] if discovered_rw else resolve_real_world_target_spec("harvard", fallback_category="institution"),
                )
            c_cut_tid = str(clips[cut_i0].get("real_world_target_id") or "").strip()
            if c_cut_tid and c_cut_tid != str(primary_inst_spec.get("target_id") or ""):
                apparatus_spec: dict[str, Any] | None = resolve_real_world_target_spec(c_cut_tid, fallback_category="scientific_apparatus")
            else:
                apparatus_spec = next(
                    (t for t in discovered_rw if str(t.get("category") or "") == "scientific_apparatus"),
                    None,
                )
            loc_c1 = re.sub(
                r"[^a-z0-9_]+",
                "_",
                str(clips[ext_i0].get("location_id") or plan["default_location_id"]).strip().lower(),
            ).strip("_") or str(plan["default_location_id"])
            loc_c2 = re.sub(
                r"[^a-z0-9_]+",
                "_",
                str(clips[cut_i0].get("location_id") or loc_c1).strip().lower(),
            ).strip("_") or loc_c1
            k_prompts = build_r72_drone_cutaway_prompts(
                primary_inst_spec,
                interior_lab_desc=str(clips[cut_i0].get("environment") or plan["real_environment"]),
                interior_apparatus_traits=str((apparatus_spec or {}).get("architectural_traits") or ""),
            )
            pv_c1 = clips[ext_i0].get("previs") if isinstance(clips[ext_i0].get("previs"), dict) else {}
            pv_c2 = clips[cut_i0].get("previs") if isinstance(clips[cut_i0].get("previs"), dict) else {}
            k0_id = f"kf_{ext_cnum:02d}_r72_k0_aerial_9x16"
            k1_id = f"kf_{ext_cnum:02d}_r72_k1_facade_9x16"
            k2_id = f"kf_{cut_cnum:02d}_r72_k2_cutaway_9x16"
            anc_k0: dict[str, Any] = {
                "ref_id": k0_id,
                "filename": f"{k0_id}.png",
                "clip_number": ext_cnum,
                "frame": "start",
                "category": "clip_keyframe_anchor",
                "role": "r72_cold_open_k0",
                "setting": "real_env",
                "location_id": loc_c1,
                "camera_angle_tag": "drone_aerial_30m",
                "generation_order": 1,
                "conditioned_on": [],
                "real_world_target_id": str(primary_inst_spec["target_id"]),
                "real_world_category": str(primary_inst_spec.get("category") or "institution"),
                "r72_relay_stage": "K0",
                "prompt": k_prompts["K0"],
            }
            if pv_c1.get("start_previs_png"):
                anc_k0["previs_guide_png"] = str(pv_c1["start_previs_png"])
            anc_k1: dict[str, Any] = {
                "ref_id": k1_id,
                "filename": f"{k1_id}.png",
                "clip_number": ext_cnum,
                "frame": "end",
                "category": "clip_keyframe_anchor",
                "role": "r72_cold_open_k1",
                "setting": "real_env",
                "location_id": loc_c1,
                "camera_angle_tag": "fpv_facade_4m",
                "generation_order": 2,
                "conditioned_on": [k0_id],
                "real_world_target_id": str(primary_inst_spec["target_id"]),
                "real_world_category": str(primary_inst_spec.get("category") or "institution"),
                "r72_relay_stage": "K1",
                "prompt": k_prompts["K1"],
            }
            if pv_c1.get("end_previs_png"):
                anc_k1["previs_guide_png"] = str(pv_c1["end_previs_png"])
            anc_k2: dict[str, Any] = {
                "ref_id": k2_id,
                "filename": f"{k2_id}.png",
                "clip_number": cut_cnum,
                "frame": "end",
                "category": "clip_keyframe_anchor",
                "role": "r72_cold_open_k2",
                "setting": "real_env",
                "location_id": loc_c2,
                "camera_angle_tag": "cutaway_interior_portal",
                "generation_order": 3,
                "conditioned_on": [k1_id],
                "real_world_target_id": str((apparatus_spec or primary_inst_spec)["target_id"]),
                "real_world_category": str((apparatus_spec or primary_inst_spec).get("category") or "institution"),
                "r72_relay_stage": "K2",
                "prompt": k_prompts["K2"],
            }
            if pv_c2.get("end_previs_png"):
                anc_k2["previs_guide_png"] = str(pv_c2["end_previs_png"])
            synth_anchors.extend([anc_k0, anc_k1, anc_k2])
            clips[ext_i0]["dual_keyframe_parallax"] = True
            clips[ext_i0]["r72_cold_open_relay"] = True
            clips[ext_i0]["flow_input_mode"] = "VIDEO_FRAMES"
            clips[ext_i0]["transition_out"] = "seamless_relay_cut"
            clips[cut_i0]["dual_keyframe_parallax"] = True
            clips[cut_i0]["r72_cold_open_relay"] = True
            clips[cut_i0]["flow_input_mode"] = "VIDEO_FRAMES"
            r72_cold_open_wired = True

        for idx_c, c_item in enumerate(clips, start=1):
            g_raw = str(c_item.get("grammar") or c_item.get("visual_grammar") or "")
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
        from pipeline.previs_blender import is_outdoor_or_architectural_clip

        for loc_k, info in seen_locs.items():
            c_src = info["clip"]
            env_txt = str(c_src.get("environment") or plan["real_environment"]).strip()
            allow_t = [str(t).strip() for t in (c_src.get("diegetic_text_allowlist") or ()) if str(t).strip()][:2]
            fname_l = f"ref_loc_{loc_k[:36]}_9x16.png"
            c_outdoor = is_outdoor_or_architectural_clip(c_src)
            loc_anc_entry: dict[str, Any] = {
                "ref_id": Path(fname_l).stem,
                "filename": fname_l,
                "clip_number": int(info["clip_number"]),
                "frame": "start",
                "category": "clip_keyframe_anchor",
                "role": "location_master",
                "setting": "real_env",
                "location_id": loc_k,
                "generation_order": 2,
                "conditioned_on": ["species_opt1_sheet"],
                "diegetic_text_allowlist": allow_t,
                "prompt": _compose_v8_non_brain_keyframe_prompt(
                    env_text=env_txt,
                    outdoor_architectural=c_outdoor,
                    clip_spec=c_src,
                ),
            }
            if c_src.get("real_world_target_id"):
                loc_anc_entry["real_world_target_id"] = str(c_src["real_world_target_id"]).strip()
                if c_src.get("real_world_category"):
                    loc_anc_entry["real_world_category"] = str(c_src["real_world_category"]).strip()
            synth_anchors.append(loc_anc_entry)

        # P4 + P6: Hybrid v8 Previs Keyframes (6..10 high-value hero cuts + 3..5 Start+End VIDEO_FRAMES parallax cuts)
        has_rendered_pv = any(
            isinstance(c_it.get("previs"), dict) and bool(c_it["previs"].get("start_previs_png"))
            for c_it in clips
        )
        hybrid_pv_flag = plan.get("hybrid_previs_v8")
        hybrid_pv_active = (bool(hybrid_pv_flag) if hybrid_pv_flag is not None else True) and (
            has_rendered_pv or bool(hybrid_pv_flag)
        )
        if hybrid_pv_active:
            hero_cut_nums = set(select_hybrid_previs_hero_cuts(clips, min_cuts=6, max_cuts=10))
            if r72_cold_open_wired and r72_relay_pair is not None:
                hero_cut_nums.discard(r72_relay_pair[0] + 1)
                hero_cut_nums.discard(r72_relay_pair[1] + 1)
            parallax_cut_nums = (
                set(select_dual_parallax_highlight_cuts(clips, hero_cut_nums, min_cuts=3, max_cuts=5))
                if bool(plan.get("enable_dual_keyframe_parallax", True))
                else set()
            )
            clips_by_cnum = {
                int(c_it.get("clip_number") or i_c): (i_c, c_it)
                for i_c, c_it in enumerate(clips, start=1)
            }
            for hc_num in sorted(hero_cut_nums):
                if hc_num not in clips_by_cnum:
                    continue
                idx_hc, c_hc = clips_by_cnum[hc_num]
                pv_hc = c_hc.get("previs") if isinstance(c_hc.get("previs"), dict) else {}
                loc_hc = re.sub(
                    r"[^a-z0-9_]+",
                    "_",
                    str(c_hc.get("location_id") or plan["default_location_id"]).strip().lower(),
                ).strip("_") or str(plan["default_location_id"])
                env_hc = str(c_hc.get("environment") or plan["real_environment"]).strip()
                act_hc = str(c_hc.get("action") or "").strip()
                act_clause_hc = f" staging {act_hc[:110]}" if act_hc else ""
                allow_hc = [str(t).strip() for t in (c_hc.get("diegetic_text_allowlist") or ()) if str(t).strip()][:2]
                sc_id_hc = str(c_hc.get("scene_id") or f"S{hc_num:02d}")
                cam_tag_hc, cam_desc_hc = daisy_cam_progression[(idx_hc - 1) % len(daisy_cam_progression)]
                loc_master_id = f"ref_loc_{loc_hc[:36]}_9x16"
                fname_hs = f"kf_{hc_num:02d}_{loc_hc[:20]}_pv_start_9x16.png"
                anc_hs: dict[str, Any] = {
                    "ref_id": Path(fname_hs).stem,
                    "filename": fname_hs,
                    "clip_number": hc_num,
                    "scene_id": sc_id_hc,
                    "frame": "start",
                    "category": "clip_keyframe_anchor",
                    "role": "reenactment",
                    "setting": "real_env",
                    "location_id": loc_hc,
                    "camera_angle_tag": cam_tag_hc,
                    "is_hybrid_previs_anchor": True,
                    "generation_order": 3,
                    "conditioned_on": ["species_opt1_sheet", loc_master_id],
                    "diegetic_text_allowlist": allow_hc,
                    "prompt": _compose_v8_non_brain_keyframe_prompt(
                        env_text=env_hc,
                        action_clause=act_clause_hc,
                        camera_desc=cam_desc_hc,
                        clip_spec=c_hc,
                    ),
                }
                if pv_hc.get("start_previs_png"):
                    anc_hs["previs_guide_png"] = str(pv_hc["start_previs_png"])
                if pv_hc.get("color_role_legend"):
                    anc_hs["color_role_legend"] = dict(pv_hc["color_role_legend"])
                synth_anchors.append(anc_hs)

                pv_end_p = str(pv_hc.get("end_previs_png") or "").strip()
                if hc_num in parallax_cut_nums and (pv_end_p or bool(hybrid_pv_flag)):
                    end_tag_hc, end_desc_hc = daisy_cam_progression[idx_hc % len(daisy_cam_progression)]
                    fname_he = f"kf_{hc_num:02d}_{loc_hc[:20]}_pv_end_9x16.png"
                    anc_he: dict[str, Any] = {
                        "ref_id": Path(fname_he).stem,
                        "filename": fname_he,
                        "clip_number": hc_num,
                        "scene_id": sc_id_hc,
                        "frame": "end",
                        "category": "clip_keyframe_anchor",
                        "role": "reenactment",
                        "setting": "real_env",
                        "location_id": loc_hc,
                        "camera_angle_tag": end_tag_hc,
                        "is_hybrid_previs_anchor": True,
                        "generation_order": 3,
                        "conditioned_on": ["species_opt1_sheet", loc_master_id],
                        "diegetic_text_allowlist": allow_hc,
                        "prompt": _compose_v8_non_brain_keyframe_prompt(
                            env_text=env_hc,
                            action_clause=act_clause_hc,
                            camera_desc=end_desc_hc,
                            closing=True,
                            clip_spec=c_hc,
                        ),
                    }
                    if pv_end_p:
                        anc_he["previs_guide_png"] = pv_end_p
                    if pv_hc.get("color_role_legend"):
                        anc_he["color_role_legend"] = dict(pv_hc["color_role_legend"])
                    synth_anchors.append(anc_he)
                    c_hc["dual_keyframe_parallax"] = True
                    c_hc["flow_input_mode"] = "VIDEO_FRAMES"

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
            if has_r74_dive_clips or bool(plan.get("r74_mode")):
                from pipeline.anatomy_map import build_neural_state_macro_desc, resolve_anatomy_screen_anchor

                synth_anchors.append(
                    {
                        "ref_id": "ref_brain_B0_wide_9x16",
                        "filename": "ref_brain_B0_wide_9x16.png",
                        "clip_number": b_idx,
                        "frame": "start",
                        "category": "brain_anchor",
                        "role": "brain_mechanism",
                        "setting": "brain_studio",
                        "r74_relay_stage": "B0",
                        "present_cast": [],
                        "must_include": ["translucent frosted-glass 3D brain, zero text"],
                        "generation_order": 3,
                        "conditioned_on": ["xray_brain75_master"],
                        "prompt": (
                            "Single full-bleed vertical 9:16 medical-grade 3D neuroanatomy scene in a deep midnight-navy "
                            "studio void (#050811): an isolated semi-transparent frosted borosilicate crystal-glass 3D human brain "
                            "(folded cerebral cortex gyri and sulci, cerebellum, brainstem) with glowing internal optical-glass "
                            "subcortical hubs (crimson-red, cool sapphire-blue, warm amber-gold), zero mannequin head, zero face, "
                            "zero bell jar, zero wet biological tissue, zero text."
                        ),
                    }
                )
                seen_r74_canon_states: set[tuple[str, str]] = set()
                for idx_rc, c_rc in enumerate(clips, start=1):
                    g_rc = normalize_expressive_v8_grammar(
                        str(c_rc.get("grammar") or c_rc.get("visual_grammar") or ""),
                        cameo_easter_egg=bool(c_rc.get("cameo_easter_egg")),
                    )
                    if not (bool(c_rc.get("brain_clip")) or g_rc == "expressive_xray_brain"):
                        continue
                    cam_rc = str(c_rc.get("camera_move") or c_rc.get("camera_movement") or "").strip().lower()
                    if cam_rc not in EXPRESSIVE_V8_NEURAL_DIVE_MOVES and not bool(c_rc.get("neural_dive_relay")):
                        continue
                    clip_ns = str(c_rc.get("neural_state") or "active").strip().lower()
                    if clip_ns not in ("active", "silenced", "severed", "rerouted"):
                        clip_ns = "active"
                    start_ns = str(
                        c_rc.get("start_neural_state")
                        or ("active" if cam_rc == "neural_tract_relay_flight" else clip_ns)
                    ).strip().lower()
                    if start_ns not in ("active", "silenced", "severed", "rerouted"):
                        start_ns = "active"
                    start_reg_raw = str(c_rc.get("brain_region") or "hippocampus").strip()
                    reg_candidates: list[tuple[str, str, str | None]] = []
                    if cam_rc == "neural_tract_relay_flight" and c_rc.get("end_brain_region"):
                        end_reg_raw = str(c_rc.get("end_brain_region")).strip()
                        reg_candidates.append((start_reg_raw, start_ns, None))
                        reg_candidates.append(
                            (
                                end_reg_raw,
                                clip_ns,
                                start_reg_raw if clip_ns in ("severed", "rerouted") else None,
                            )
                        )
                    elif cam_rc == "neural_fpv_pullback_out":
                        reg_candidates.append((start_reg_raw, start_ns, None))
                    else:
                        reg_candidates.append((start_reg_raw, clip_ns, None))
                    pv_rc = c_rc.get("previs") if isinstance(c_rc.get("previs"), dict) else {}
                    for reg_cand_idx, (reg_cand, eff_state, from_reg_ctx) in enumerate(reg_candidates):
                        anc_m = resolve_anatomy_screen_anchor(reg_cand, macro_mode=True)
                        if not anc_m or (anc_m["canonical"], eff_state) in seen_r74_canon_states:
                            continue
                        seen_r74_canon_states.add((anc_m["canonical"], eff_state))
                        reg_slug = re.sub(r"[^a-z0-9]+", "_", str(anc_m["canonical"]).lower()).strip("_")
                        b1_ref_id = (
                            f"ref_brain_B1_{reg_slug}_macro_9x16"
                            if eff_state == "active"
                            else f"ref_brain_B1_{reg_slug}_{eff_state}_macro_9x16"
                        )
                        b1_frame = (
                            "end"
                            if (cam_rc == "neural_fpv_dive_in" or (cam_rc == "neural_tract_relay_flight" and reg_cand_idx == 1))
                            else "start"
                        )
                        if from_reg_ctx and eff_state in ("severed", "rerouted"):
                            macro_desc = build_neural_state_macro_desc(
                                from_reg_ctx,
                                neural_state=eff_state,
                                end_region=anc_m["canonical"],
                            )
                        else:
                            macro_desc = build_neural_state_macro_desc(
                                anc_m["canonical"],
                                neural_state=eff_state,
                            )
                        b1_anc: dict[str, Any] = {
                            "ref_id": b1_ref_id,
                            "filename": f"{b1_ref_id}.png",
                            "clip_number": int(c_rc.get("clip_number") or idx_rc),
                            "frame": b1_frame,
                            "category": "brain_anchor",
                            "role": "brain_macro_mechanism",
                            "setting": "brain_studio",
                            "r74_relay_stage": "B1",
                            "is_r74_macro_anchor": True,
                            "brain_region": anc_m["canonical"],
                            "neural_state": eff_state,
                            "present_cast": [],
                            "must_include": ["translucent frosted-glass 3D brain, zero text"],
                            "generation_order": 3,
                            "conditioned_on": ["ref_brain_B0_wide_9x16"],
                            "prompt": (
                                "Single full-bleed vertical 9:16 ultra-macro 3D neuroanatomy close-up inside a deep midnight-navy "
                                f"chamber (#050811): {macro_desc}, razor-sharp architectural borosilicate crystal-glass "
                                "refraction, zero mannequin head, zero face, zero wet biological flesh, zero blood vessels, zero text."
                            ),
                        }
                        pv_guide_b1 = str(
                            pv_rc.get("end_previs_png" if b1_frame == "end" else "start_previs_png") or ""
                        ).strip()
                        if pv_guide_b1:
                            b1_anc["previs_guide_png"] = pv_guide_b1
                        if pv_rc.get("color_role_legend"):
                            b1_anc["color_role_legend"] = dict(pv_rc["color_role_legend"])
                        synth_anchors.append(b1_anc)
            else:
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
                        "conditioned_on": ["xray_brain75_master"],
                        "prompt": (
                            "Single full-bleed vertical 9:16 medical-grade 3D neuroanatomy scene in a deep midnight-navy "
                            "studio void (#050811): an isolated semi-transparent frosted-glass 3D human brain (folded cerebral "
                            "cortex gyri and sulci, cerebellum, brainstem) with glowing internal subcortical hubs (crimson-red, "
                            "electric cyan-blue, warm amber-gold), zero mannequin head, zero face, zero bell jar, zero text."
                        ),
                    }
                )
        plan["reference_anchors"] = synth_anchors
        existing_anchors = synth_anchors

    from pipeline.anatomy_map import resolve_anatomy_screen_anchor as _resolve_r74_anchor

    loc_to_rel: dict[str, str] = {}
    clip_num_to_rel: dict[int, str] = {}
    clip_num_to_end_rel: dict[int, str] = {}
    brain_anchor_rel: str = ""
    r74_b0_rel: str = ""
    r74_b1_by_canon: dict[str, str] = {}
    r74_b1_by_canon_state: dict[tuple[str, str], str] = {}
    cameo_anchor_rel: str = ""
    r72_k1_rel: str = ""
    r72_k2_rel: str = ""
    r72_k1_cnum: int = 1
    r72_k2_cnum: int = 2
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
        relay_stage_a = str(anc.get("r72_relay_stage") or "").strip().upper()
        r74_stage_a = str(anc.get("r74_relay_stage") or "").strip().upper()
        if relay_stage_a == "K1":
            r72_k1_rel = rel_a
            if c_num_a > 0:
                r72_k1_cnum = c_num_a
        elif relay_stage_a == "K2":
            r72_k2_rel = rel_a
            if c_num_a > 0:
                r72_k2_cnum = c_num_a
        if r74_stage_a == "B0" or Path(fname_a).name == "ref_brain_B0_wide_9x16.png":
            r74_b0_rel = rel_a
        elif r74_stage_a == "B1" or bool(anc.get("is_r74_macro_anchor")) or "_B1_" in Path(fname_a).name:
            stem_clean = Path(fname_a).stem
            inferred_ns = str(anc.get("neural_state") or "").strip().lower()
            for st_tok in ("silenced", "severed", "rerouted"):
                if f"_{st_tok}_macro" in stem_clean:
                    if not inferred_ns:
                        inferred_ns = st_tok
                    stem_clean = stem_clean.replace(f"_{st_tok}_macro", "_macro")
            if inferred_ns not in ("active", "silenced", "severed", "rerouted"):
                inferred_ns = "active"
            anc_reg_info = _resolve_r74_anchor(str(anc.get("brain_region") or stem_clean), macro_mode=True)
            if anc_reg_info:
                r74_b1_by_canon_state.setdefault((anc_reg_info["canonical"], inferred_ns), rel_a)
                if inferred_ns == "active" or anc_reg_info["canonical"] not in r74_b1_by_canon:
                    r74_b1_by_canon[anc_reg_info["canonical"]] = rel_a
        is_loc_master_file = Path(fname_a).name.startswith("ref_loc_") or role_a == "location_master"
        is_r74_shared_brain = bool(r74_stage_a in ("B0", "B1") or anc.get("is_r74_macro_anchor"))
        if not is_loc_master_file and not is_r74_shared_brain and c_num_a > 0 and frame_a == "start" and c_num_a not in clip_num_to_rel:
            clip_num_to_rel[c_num_a] = rel_a
        elif not is_r74_shared_brain and c_num_a > 0 and frame_a == "end" and c_num_a not in clip_num_to_end_rel:
            clip_num_to_end_rel[c_num_a] = rel_a
        if setting_a == "brain_studio" or str(anc.get("category") or "") == "brain_anchor":
            if not brain_anchor_rel and r74_stage_a != "B1" and not bool(anc.get("is_r74_macro_anchor")):
                brain_anchor_rel = rel_a
        elif role_a == "cameo_anchor" or "cameo" in fname_a.lower():
            if not cameo_anchor_rel:
                cameo_anchor_rel = rel_a
        elif loc_a and (is_loc_master_file or loc_a not in loc_to_rel):
            loc_to_rel[loc_a] = rel_a
    if r72_k1_rel and r72_k2_rel and len(clips) >= r72_k2_cnum:
        clip_num_to_end_rel.setdefault(r72_k1_cnum, r72_k1_rel)
        clip_num_to_rel[r72_k2_cnum] = r72_k1_rel
        clip_num_to_end_rel[r72_k2_cnum] = r72_k2_rel

    for idx_clip, c in enumerate(clips, start=1):
        c["style_profile"] = EXPRESSIVE_25D_V8_STYLE_PROFILE
        c["schema_version"] = PROMPT_SCHEMA_VERSION_V8
        g_name = str(c.get("grammar") or c.get("visual_grammar") or "expressive_vinyl_world").strip()
        if g_name == "brain_simulator_3d":
            c["cameo_easter_egg"] = False
            c["brain_clip"] = True
            continue
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
        cur_end_ref = str(c.get("end_reference_image") or "").strip()
        eff_c_num = int(c.get("clip_number") or idx_clip)
        per_clip_ref = clip_num_to_rel.get(eff_c_num, "")
        per_clip_end_ref = clip_num_to_end_rel.get(eff_c_num, "")
        explicit_slot_id = str(c.get("canonical_slot_id") or "").strip()
        if (
            bool(c.get("lock_start_and_end_keyframes"))
            and per_clip_ref
            and per_clip_end_ref
            and per_clip_ref != per_clip_end_ref
            and (not cur_end_ref or cur_ref != per_clip_ref)
        ):
            cur_ref = per_clip_ref
            cur_end_ref = per_clip_end_ref
        has_locked_start_end_pair = bool(
            cur_ref
            and cur_end_ref
            and cur_ref != cur_end_ref
            and not cur_ref.endswith(multi_panel_v8_sheets)
            and not cur_end_ref.endswith(multi_panel_v8_sheets)
            and (
                bool(c.get("lock_start_and_end_keyframes"))
                or bool(c.get("stacked_cutaway_brain_compare"))
                or bool(c.get("side_by_side_brain_compare"))
                or bool(c.get("non_spatial_contrast_cut"))
                or bool(explicit_slot_id and (explicit_slot_id in cur_ref or explicit_slot_id in cur_end_ref))
            )
        )

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
            cam_brain = str(c.get("camera_move") or c.get("camera_movement") or "").strip().lower()
            if has_locked_start_end_pair:
                c["reference_image"] = cur_ref
                c["start_frame_image"] = cur_ref
                c["end_reference_image"] = cur_end_ref
                c["end_frame_image"] = cur_end_ref
                c["flow_input_mode"] = "VIDEO_FRAMES"
                c["single_start_frame_lock"] = False
                c["full_trajectory_span"] = True
                c.pop("neural_dive_relay", None)
                c.pop("r74_macro_mode", None)
            elif cam_brain in EXPRESSIVE_V8_NEURAL_DIVE_MOVES or bool(c.get("neural_dive_relay")):
                eff_cam_b = cam_brain if cam_brain in EXPRESSIVE_V8_NEURAL_DIVE_MOVES else "neural_fpv_dive_in"
                anc_b_cur = _resolve_r74_anchor(str(c.get("brain_region") or "hippocampus"), macro_mode=True)
                canon_b_cur = anc_b_cur["canonical"] if anc_b_cur else "hippocampus"
                clip_ns_b = str(c.get("neural_state") or "active").strip().lower()
                if clip_ns_b not in ("active", "silenced", "severed", "rerouted"):
                    clip_ns_b = "active"
                start_ns_b = str(
                    c.get("start_neural_state")
                    or ("active" if eff_cam_b == "neural_tract_relay_flight" else clip_ns_b)
                ).strip().lower()
                if start_ns_b not in ("active", "silenced", "severed", "rerouted"):
                    start_ns_b = "active"
                b0_target = r74_b0_rel or brain_anchor_rel or xray_rel
                b1_target = (
                    r74_b1_by_canon_state.get((canon_b_cur, clip_ns_b))
                    or r74_b1_by_canon.get(canon_b_cur)
                    or b0_target
                )
                c["neural_dive_relay"] = True
                if eff_cam_b == "neural_fpv_dive_in":
                    c["reference_image"] = b0_target
                    c["end_reference_image"] = b1_target
                    c["start_frame_image"] = b0_target
                    c["end_frame_image"] = b1_target
                    c["flow_input_mode"] = "VIDEO_FRAMES"
                    c["single_start_frame_lock"] = False
                    c["dual_keyframe_parallax"] = True
                    c["full_trajectory_span"] = True
                    c.setdefault("transition_out", "seamless_relay_cut")
                elif eff_cam_b == "neural_macro_orbit_hold":
                    c["reference_image"] = b1_target
                    c["start_frame_image"] = b1_target
                    c.pop("end_reference_image", None)
                    c.pop("end_frame_image", None)
                    c["single_start_frame_lock"] = True
                    c["r74_macro_mode"] = True
                elif eff_cam_b == "neural_fpv_pullback_out":
                    b1_pull_start = (
                        r74_b1_by_canon_state.get((canon_b_cur, start_ns_b))
                        or r74_b1_by_canon_state.get((canon_b_cur, clip_ns_b))
                        or r74_b1_by_canon.get(canon_b_cur)
                        or b0_target
                    )
                    explicit_world_end = str(c.get("portal_to_world_ref") or "").strip()
                    end_pull = explicit_world_end or b0_target
                    c["reference_image"] = b1_pull_start
                    c["end_reference_image"] = end_pull
                    c["start_frame_image"] = b1_pull_start
                    c["end_frame_image"] = end_pull
                    c["flow_input_mode"] = "VIDEO_FRAMES"
                    c["single_start_frame_lock"] = False
                    c["dual_keyframe_parallax"] = True
                    c["full_trajectory_span"] = True
                elif eff_cam_b == "neural_tract_relay_flight":
                    b1_start_target = (
                        r74_b1_by_canon_state.get((canon_b_cur, start_ns_b))
                        or r74_b1_by_canon.get(canon_b_cur)
                        or b0_target
                    )
                    anc_b_end = _resolve_r74_anchor(
                        str(c.get("end_brain_region") or c.get("brain_region") or "prefrontal cortex"),
                        macro_mode=True,
                    )
                    canon_b_end = anc_b_end["canonical"] if anc_b_end else canon_b_cur
                    b1_end_target = (
                        r74_b1_by_canon_state.get((canon_b_end, clip_ns_b))
                        or r74_b1_by_canon.get(canon_b_end)
                        or b0_target
                    )
                    c["reference_image"] = b1_start_target
                    c["end_reference_image"] = b1_end_target
                    c["start_frame_image"] = b1_start_target
                    c["end_frame_image"] = b1_end_target
                    c["flow_input_mode"] = "VIDEO_FRAMES"
                    c["single_start_frame_lock"] = False
                    c["dual_keyframe_parallax"] = True
                    c["full_trajectory_span"] = True
                    c["r74_macro_mode"] = True
            elif bool(c.get("portal_to_brain")):
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
            cur_is_generic_loc = bool(cur_ref) and Path(cur_ref).name.startswith("ref_loc_")
            if not cur_ref or (cur_ref == species_rel and loc_ref) or (cur_is_generic_loc and per_clip_ref):
                if c["grammar"] == "expressive_literal_analogy" and not (c.get("scene_state") or {}).get("present_cast_start") and not loc_ref:
                    c.pop("reference_image", None)
                else:
                    c["reference_image"] = loc_ref or species_rel
            is_portal_or_extrusion = bool(
                c.get("portal_to_brain")
                or c.get("r72_cold_open_relay")
                or c["grammar"] in ("axial_portal_dive", "blueprint_3d_extrusion", "xray_peel_micro", "architectural_cutaway_portal")
            )
            is_dual_parallax = (
                bool(
                    c.get("dual_keyframe_parallax")
                    or c.get("r72_cold_open_relay")
                    or c.get("lock_start_and_end_keyframes")
                )
                and bool(per_clip_end_ref or c.get("end_reference_image"))
            )
            if single_start_only and not is_portal_or_extrusion and not is_dual_parallax:
                c.pop("end_reference_image", None)
                c["single_start_frame_lock"] = True
            elif per_clip_end_ref and per_clip_end_ref != str(c.get("reference_image") or "").strip():
                c["end_reference_image"] = per_clip_end_ref
                if is_dual_parallax:
                    c["single_start_frame_lock"] = False
                    c["flow_input_mode"] = "VIDEO_FRAMES"
                    c["start_frame_image"] = str(c.get("reference_image") or "")
                    c["end_frame_image"] = per_clip_end_ref
            if "reference_images" in c:
                c["reference_images"] = [c["reference_image"]] if c.get("reference_image") else []
            c.pop("secondary_reference_image", None)

    if use_daisy and not single_start_only and len(clips) >= 2:
        from pipeline.config import EXPRESSIVE_V8_MAX_STYLED_TRANSITIONS

        styled_set = {
            "dissolve_6f",
            "dissolve_8f",
            "dissolve_12f",
            "dissolve_15f",
            "portal_crash_zoom_10f",
            "whip_pan_blur_8f",
            "occlusion_wipe",
            "split_screen_wipe",
            "match_cut_bridge",
        }
        alpha_set = {"dissolve_6f", "dissolve_8f", "dissolve_12f", "dissolve_15f", "split_screen_wipe", "match_cut_bridge"}
        alpha_used = sum(
            1
            for c_chk in clips[:-1]
            if str(c_chk.get("transition_out") or c_chk.get("transition_to_next") or "").strip().lower() in alpha_set
        )
        max_alpha_auto = max(1, len(clips) // 2)

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
                and not bool(c_nxt.get("lock_start_and_end_keyframes"))
                and not bool(c_nxt.get("canonical_slot_id"))
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
                has_explicit_end_anchor = eff_cur_num in clip_num_to_end_rel or bool(c_cur.get("lock_start_and_end_keyframes"))
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
                        if loc_cur != loc_nxt and alpha_used < max_alpha_auto:
                            c_cur["transition_to_next"] = "dissolve_12f"
                            alpha_used += 1
                        else:
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
    batch_count: int | None = None,
    only_ref_ids: set[str] | None = None,
    force: bool = False,
    require_review: bool | None = None,
    auto_populate_review: bool = False,
    synthesize_scene_anchors: bool = False,
) -> dict[str, Any]:
    """
    Ensures all required `porcelain_cinematic_v7` reference PNGs exist in `03_visuals/reference_images/`
    and pass `inspect_reference_image_pack` (`pre_generation_ready == True`), generating any missing or
    failed anchors via `0-credit` Google Flow `Image` (`Nano Banana 2.1`, `x1` first-pass / `x2` retry) in `1 -> 2 -> 3` order.
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
            only_ref_ids=only_ref_ids,
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

    norm_only_ref_ids = {str(x).strip() for x in (only_ref_ids or set()) if str(x).strip()} or None

    # Fast cached check before mutating or opening browser
    if not force and not norm_only_ref_ids and _reference_specs_cover_plan(vis_dir, vis_dir / REF_IMAGES_DIRNAME, plan):
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
                and (
                    not norm_only_ref_ids
                    or str(a.get("ref_id") or "").strip() in norm_only_ref_ids
                    or Path(str(a.get("filename") or "")).stem in norm_only_ref_ids
                )
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
            only_ref_ids=norm_only_ref_ids,
            force=force,
            backend=backend,
            batch_count=batch_count,
        )
    finally:
        if used_quarantine or q_dir.exists():
            purge_reenactment_quarantine(slug)

    qa_rep = build_and_verify_project_reference_pack(
        p_dir,
        dossier_dir=d_dir,
        require_review=require_review,
        auto_populate_review=False,
    )
    return {
        "skipped": False,
        "cached": False,
        "project_id": p_dir.name,
        "slug": slug,
        "reenactment_track": track,
        "generation": gen_summary,
        "status": "APPROVED" if qa_rep.get("pre_generation_ready") else ("REVIEW_PENDING" if qa_rep.get("cv_pre_generation_ready") else "QA_FAILED"),
        "review_file": str(p_dir / "03_visuals" / "reference_images" / "reference_semantic_review.json"),
        "reference_dir": str(p_dir / "03_visuals" / "reference_images"),
        "pre_generation_ready": bool(qa_rep.get("pre_generation_ready")),
        "cv_pre_generation_ready": bool(qa_rep.get("cv_pre_generation_ready")),
        "reference_qa_score": qa_rep.get("reference_qa_score"),
        "regenerate_image_ids": qa_rep.get("regenerate_image_ids") or [],
        "total_images": qa_rep.get("total_existing"),
    }


def build_r85_canonical_master_bindings(
    plan: dict[str, Any] | None,
    *,
    project_id: str | None = None,
) -> list[tuple[str, str | None, str]]:
    """
    Returns master canonical slot bindings `(slot_id, dest_filename, frame)`.
    Under R88 faceless cast mode (`v8_ep13+`), binds strictly clean empty architectural rooms
    (`E01_laboratory_empty`, `E05_kitchen_empty`, `select_canonical_environment_slot(..., staged=False)`)
    and blocks pre-R88 dotted-eye `E*_staged` auto-bindings.
    """
    from pipeline.canonical_assets import guard_r88_autobound_slot, select_canonical_environment_slot
    from pipeline.config import is_r88_faceless_cast_plan

    p = plan if isinstance(plan, dict) else {}
    is_r88 = is_r88_faceless_cast_plan(p, project_id=project_id)
    if is_r88:
        bindings: list[tuple[str, str | None, str]] = [
            ("A01_mode1_translucent_head_lateral", EXPRESSIVE_V8_SPECIES_SHEET_FILENAME, "single"),
            ("E01_laboratory_empty", "cast_sheet_02_clinical_historical_6roles.png", "single"),
            ("E05_kitchen_empty", "cast_sheet_03_everyday_lifestyle_6roles.png", "single"),
            (
                select_canonical_environment_slot(
                    str(p.get("real_environment") or ""),
                    staged=False,
                    r88_faceless=True,
                ),
                "expressive_conflict_master.png",
                "single",
            ),
            ("A01_mode1_translucent_head_lateral", None, "single"),
            ("A02_mode2_whole_brain_lateral", None, "single"),
            ("A03_mode2_whole_brain_dorsal_topdown", None, "single"),
            ("A05_sulcal_vessel_macro", None, "single"),
        ]
        for sid, _, _ in bindings:
            guard_r88_autobound_slot(sid, r88_faceless=True)
        return bindings
    return [
        ("A01_mode1_translucent_head_lateral", EXPRESSIVE_V8_SPECIES_SHEET_FILENAME, "single"),
        ("E06_laboratory_staged", "cast_sheet_02_clinical_historical_6roles.png", "single"),
        ("E10_kitchen_staged", "cast_sheet_03_everyday_lifestyle_6roles.png", "single"),
        (
            select_canonical_environment_slot(str(p.get("real_environment") or ""), staged=True),
            "expressive_conflict_master.png",
            "single",
        ),
        ("A01_mode1_translucent_head_lateral", None, "single"),
        ("A02_mode2_whole_brain_lateral", None, "single"),
        ("A03_mode2_whole_brain_dorsal_topdown", None, "single"),
        ("A05_sulcal_vessel_macro", None, "single"),
    ]


def ensure_expressive_v8_reference_pack(
    project_dir: str | Path,
    dossier_dir: str | Path | None = None,
    *,
    cdp_port: int = DEFAULT_CDP_PORT,
    backend: str = DEFAULT_REENACT_IMAGE_BACKEND,
    batch_count: int | None = None,
    only_ref_ids: set[str] | None = None,
    force: bool = False,
    require_review: bool | None = None,
    auto_populate_review: bool = False,
    synthesize_scene_anchors: bool = False,
) -> dict[str, Any]:
    """
    Stages the 6 pre-verified `expressive_25d_v8` (`안 1 + 안 3 결합형`) Flow-generated master reference PNGs
    from `BCI_Shorts_Channel/reference_style_anchors/expressive_25d_v8_refs/` into `03_visuals/reference_images/`,
    generates any custom episode `reference_anchors` (e.g. `daisy_chain_bridge` `Start+End` keyframes) via
    `0-credit` Flow `Image` (`x1` first-pass / `x2` retry) if missing, and verifies `pre_generation_ready == True`.
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
    norm_only_ref_ids = {str(x).strip() for x in (only_ref_ids or set()) if str(x).strip()} or None
    plan_unchanged = json.dumps(preview_plan, sort_keys=True, ensure_ascii=False) == before_plan_txt
    if not force and not norm_only_ref_ids and plan_unchanged and _reference_specs_cover_plan(vis_dir, ref_dir, preview_plan):
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
    translucent_brain_dir = Path(CHANNEL_ROOT) / "reference_style_anchors" / "translucent_brain_v8_refs"
    from pipeline.canonical_assets import (
        CanonicalAssetError,
        guard_r88_autobound_slot,
        is_retired_derivative_anchor,
        select_canonical_arrow_slot,
        select_canonical_brain_slot,
        select_canonical_drone_slot,
        select_canonical_environment_slot,
        stage_canonical_slot_to_project,
    )
    from pipeline.config import is_r85_flow_31_brain_plan, is_r88_faceless_cast_plan

    is_r85_pack = is_r85_flow_31_brain_plan(plan, project_id=p_dir.name) or bool(plan.get("canonical_assets_version"))
    is_r88_pack = is_r88_faceless_cast_plan(plan, project_id=p_dir.name)
    staged_masters: list[str] = []

    if is_r85_pack:
        # Strict Canonical Asset Library v1 lock: zero legacy reference_style_anchors copies; stage ONLY approved SHA-locked v1 slots!
        for c_chk in plan.get("clips") or []:
            if not isinstance(c_chk, dict):
                continue
            for k_ref in ("reference_image", "secondary_reference_image", "end_reference_image"):
                if is_retired_derivative_anchor(c_chk.get(k_ref)):
                    raise CanonicalAssetError(
                        f"Clip {c_chk.get('clip_number')} {k_ref}='{c_chk.get(k_ref)}' uses retired derivative anchor"
                    )
        for a_chk in plan.get("reference_anchors") or []:
            if not isinstance(a_chk, dict):
                continue
            afn_chk = str(a_chk.get("filename") or a_chk.get("ref_id") or "")
            if is_retired_derivative_anchor(afn_chk):
                raise CanonicalAssetError(f"reference_anchors entry '{afn_chk}' uses retired derivative anchor")
            for cond_chk in a_chk.get("conditioned_on") or []:
                if is_retired_derivative_anchor(str(cond_chk)):
                    raise CanonicalAssetError(
                        f"reference_anchors '{afn_chk}' conditioned_on retired anchor '{cond_chk}'"
                    )

        # Stage core approved faceless v1 anchors (under R88, strictly clean empty architectural masters; 0 dotted-eye E*_staged auto-binds)
        canonical_core_bindings = build_r85_canonical_master_bindings(plan, project_id=p_dir.name)
        # Also stage exact category slots needed by clips/anchors in this episode
        for c_it in plan.get("clips") or []:
            if not isinstance(c_it, dict):
                continue
            explicit_slot = str(c_it.get("canonical_slot_id") or "").strip()
            g_it = str(c_it.get("grammar") or "")
            cam_it = str(c_it.get("camera_move") or c_it.get("camera") or "")
            if explicit_slot:
                ref_img_s = str(c_it.get("reference_image") or "")
                end_img_s = str(c_it.get("end_reference_image") or "")
                if ref_img_s.endswith(f"canonical_{explicit_slot}_start.png") or end_img_s.endswith(f"canonical_{explicit_slot}_end.png"):
                    canonical_core_bindings.append((explicit_slot, None, "start"))
                    canonical_core_bindings.append((explicit_slot, None, "end"))
                else:
                    canonical_core_bindings.append((explicit_slot, None, "single"))
            elif g_it == "expressive_xray_brain" or bool(c_it.get("brain_clip")) or bool(c_it.get("r85_brain_clip")):
                bslot = select_canonical_brain_slot(
                    brain_region=str(c_it.get("brain_region") or ""),
                    viewpoint=str(c_it.get("viewpoint") or ""),
                    mode=str(c_it.get("r85_brain_mode") or ""),
                    shot_scale=str(c_it.get("r85_shot_scale") or ""),
                    neural_state=str(c_it.get("neural_state") or ""),
                    side_by_side=bool(c_it.get("side_by_side_brain_compare")),
                )
                canonical_core_bindings.append((guard_r88_autobound_slot(bslot, r88_faceless=is_r88_pack), None, "single"))
            elif g_it == "spatial_3d_arrow_diorama" or bool(c_it.get("arrow_3d_mode")):
                aslot = select_canonical_arrow_slot(str(c_it.get("arrow_3d_mode") or ""))
                canonical_core_bindings.append((guard_r88_autobound_slot(aslot, r88_faceless=is_r88_pack), None, "single"))
            elif g_it == "expressive_exterior_establishing" or cam_it.startswith("drone_"):
                dslot = select_canonical_drone_slot(str(c_it.get("environment") or c_it.get("scene") or ""))
                canonical_core_bindings.append((guard_r88_autobound_slot(dslot, r88_faceless=is_r88_pack), None, "single"))
            else:
                eslot = select_canonical_environment_slot(
                    str(c_it.get("environment") or ""),
                    staged=False,
                    r88_faceless=is_r88_pack,
                )
                canonical_core_bindings.append((guard_r88_autobound_slot(eslot, r88_faceless=is_r88_pack), None, "single"))

        for a_it in plan.get("reference_anchors") or []:
            if not isinstance(a_it, dict):
                continue
            for cond_item in a_it.get("conditioned_on") or []:
                cond_name = Path(str(cond_item or "")).name
                m_can = re.match(r"^canonical_([A-Za-z0-9_]+)\.png$", cond_name)
                if m_can:
                    stem_id = m_can.group(1)
                    if stem_id.endswith("_start"):
                        canonical_core_bindings.append((stem_id[:-6], None, "start"))
                    elif stem_id.endswith("_end"):
                        canonical_core_bindings.append((stem_id[:-4], None, "end"))
                    else:
                        canonical_core_bindings.append((stem_id, None, "single"))

        seen_dest: set[str] = set()
        for slot_id_c, alias_fn, frame_mode in canonical_core_bindings:
            st_info = stage_canonical_slot_to_project(
                p_dir,
                slot_id_c,
                dest_filename=alias_fn,
                version="auto",
                frame=frame_mode,
            )
            fn_st = st_info["staged_filename"]
            if fn_st not in seen_dest:
                seen_dest.add(fn_st)
                staged_masters.append(fn_st)
        master_files = tuple(staged_masters)
    else:
        master_files = (
            EXPRESSIVE_V8_SPECIES_SHEET_FILENAME,
            EXPRESSIVE_V8_CAMEO_SHEET_FILENAME,
            "xray_brain75_master.png",
            "expressive_conflict_master.png",
            "cast_sheet_02_clinical_historical_6roles.png",
            "cast_sheet_03_everyday_lifestyle_6roles.png",
        )
        for fname in master_files:
            src_f = master_src_dir / fname
            if fname == "xray_brain75_master.png" and (translucent_brain_dir / "cand_04_neutral_master_translucent_glass_9x16.png").exists():
                src_f = translucent_brain_dir / "cand_04_neutral_master_translucent_glass_9x16.png"
            dst_f = ref_dir / fname
            if src_f.exists():
                if force or not dst_f.exists() or dst_f.stat().st_size != src_f.stat().st_size:
                    shutil.copy2(src_f, dst_f)
                register_reference_image(p_dir, fname, "flow_image_generation")
                staged_masters.append(fname)

        # Auto-stage role-matched translucent 3D human brain anchors (`cand_01..06`) for legacy non-R85 plans only
        if translucent_brain_dir.exists():
            clips_by_num = {
                int(c.get("clip_number") or i): c
                for i, c in enumerate(plan.get("clips") or [], start=1)
                if isinstance(c, dict)
            }
            for anc in plan.get("reference_anchors") or []:
                if not isinstance(anc, dict) or str(anc.get("category") or "") != "brain_anchor":
                    continue
                b_fn = str(anc.get("filename") or f"{anc.get('ref_id')}.png").strip()
                if (
                    str(anc.get("r74_relay_stage") or "").strip().upper() == "B1"
                    or bool(anc.get("is_r74_macro_anchor"))
                    or bool(anc.get("custom_brain_anchor"))
                    or bool(anc.get("r85_brain_clip"))
                    or bool(anc.get("side_by_side_brain_compare"))
                    or "_B1_" in b_fn
                    or b_fn.startswith(("ref_r78m_", "ref_r82_", "kf_r85_"))
                ):
                    continue
                c_num = int(anc.get("clip_number") or 0)
                c_meta = clips_by_num.get(c_num, {})
                reg_txt = f"{c_meta.get('brain_region', '')} {c_meta.get('action', '')} {c_meta.get('scene', '')}".lower()
                if any(k in reg_txt for k in ("prefrontal", "pathway", "tract", "brake", "sagittal")):
                    cand_name = "cand_02_side_profile_pfc_accumbens_xray_9x16.png"
                elif any(k in reg_txt for k in ("accumbens", "amygdala", "reward", "conflict")):
                    cand_name = "cand_03_anterior_3q_dual_hub_xray_9x16.png"
                elif any(k in reg_txt for k in ("hippocamp", "limbic", "memory", "thalam", "sleep")):
                    cand_name = "cand_01_3q_subcortical_limbic_xray_9x16.png"
                elif any(k in reg_txt for k in ("motor", "autonomic", "brainstem", "frontal lobe")):
                    cand_name = "cand_05_elevated_3q_frontal_cyan_brainstem_red_9x16.png"
                else:
                    cand_name = "cand_04_neutral_master_translucent_glass_9x16.png"
                cand_src = translucent_brain_dir / cand_name
                if cand_src.exists():
                    shutil.copy2(cand_src, ref_dir / b_fn)
                    register_reference_image(p_dir, b_fn, "flow_image_generation")
                    staged_masters.append(b_fn)

    gen_summary: dict[str, Any] = {"staged_masters": staged_masters, "generated_custom": 0}
    custom_anchors = [
        a
        for a in (plan.get("reference_anchors") or [])
        if isinstance(a, dict)
        and str(a.get("filename") or f"{a.get('ref_id')}.png") not in set(master_files)
        and (force or not (ref_dir / str(a.get("filename") or f"{a.get('ref_id')}.png")).exists())
    ]
    if norm_only_ref_ids is not None:
        custom_anchors = [
            a
            for a in custom_anchors
            if (
                str(a.get("ref_id") or "").strip() in norm_only_ref_ids
                or Path(str(a.get("filename") or "")).stem in norm_only_ref_ids
            )
        ]
    target_custom_ref_ids: set[str] = (
        set(norm_only_ref_ids)
        if norm_only_ref_ids is not None
        else {
            str(a.get("ref_id") or Path(str(a.get("filename") or f"ref_clip_{i:02d}.png")).stem)
            for i, a in enumerate(custom_anchors, start=1)
        }
    )
    has_real_world_anchors = any(
        isinstance(a, dict) and bool(a.get("real_world_target_id"))
        for a in (plan.get("reference_anchors") or [])
    )
    from pipeline.config import REAL_WORLD_REFS_MANIFEST_FILENAME

    rw_manifest_path = vis_dir / REAL_WORLD_REFS_MANIFEST_FILENAME
    need_rw_guides = has_real_world_anchors and (
        bool(target_custom_ref_ids) or (force and norm_only_ref_ids is None) or not rw_manifest_path.exists()
    )
    try:
        if need_rw_guides:
            from pipeline.real_world_reference_builder import prepare_episode_real_world_guides

            gen_summary["real_world_manifest"] = prepare_episode_real_world_guides(
                project_dir=p_dir,
                visual_plan=plan,
                dossier_dir=d_dir,
            )
        if target_custom_ref_ids:
            gen_summary["custom_translation"] = translate_porcelain_keyframes(
                project_dir=p_dir,
                slug=slug,
                cdp_port=cdp_port,
                only_ref_ids=target_custom_ref_ids,
                force=force,
                backend=backend,
                batch_count=batch_count,
            )
            gen_summary["generated_custom"] = len(target_custom_ref_ids)
    finally:
        if has_real_world_anchors:
            from pipeline.real_world_reference_builder import finalize_real_world_manifest_and_purge

            gen_summary["real_world_finalize"] = finalize_real_world_manifest_and_purge(
                project_dir=p_dir,
                visual_plan=plan,
            )

    qa_rep = build_and_verify_project_reference_pack(
        p_dir,
        dossier_dir=d_dir,
        require_review=require_review,
        auto_populate_review=False,
    )
    return {
        "skipped": False,
        "cached": False,
        "project_id": p_dir.name,
        "slug": slug,
        "style_profile": EXPRESSIVE_25D_V8_STYLE_PROFILE,
        "reenactment_track": str(plan.get("reenactment_track") or "track_b"),
        "generation": gen_summary,
        "status": "APPROVED" if qa_rep.get("pre_generation_ready") else ("REVIEW_PENDING" if qa_rep.get("cv_pre_generation_ready") else "QA_FAILED"),
        "review_file": str(p_dir / "03_visuals" / "reference_images" / "reference_semantic_review.json"),
        "reference_dir": str(p_dir / "03_visuals" / "reference_images"),
        "pre_generation_ready": bool(qa_rep.get("pre_generation_ready")),
        "cv_pre_generation_ready": bool(qa_rep.get("cv_pre_generation_ready")),
        "reference_qa_score": qa_rep.get("reference_qa_score"),
        "regenerate_image_ids": qa_rep.get("regenerate_image_ids") or [],
        "total_images": qa_rep.get("total_existing"),
    }


EXPRESSIVE_V8_PREVIS_CAMERA_ANGLES: dict[str, str] = {
    "eye_level_medium": "eye-level medium 35mm f/8 deep-focus cinema composition facing the foreground action",
    "fpv_aperture_wide": "28mm f/8 deep-focus perspective looking cleanly through a foreground aperture across the room",
    "three_quarter_orbit_left": "elevated 35-degree f/8 deep-focus three-quarter left orbit composition with tack-sharp room depth",
    "three_quarter_orbit_right": "reverse 35-degree f/8 deep-focus three-quarter right orbit composition showing tack-sharp spatial depth",
}


R85_EP31_MASTER_STYLE_PROMPT = (
    "Vertical 9:16 ultra-clean 3D neuroanatomy render in the genuine Episode #31 style over solid flat dark navy void (#040711), "
    "large hero framing filling 85% to 92% of the horizontal 9:16 frame width under unified bright top-left 45-degree studio keylight: "
    "almost-white bright cool matte sculpted gypsum-plaster cortical gyri (#DCDFE3 to #F0F3F6, ultra-low saturation matte chalk texture, "
    "strictly zero blue steel tint, zero wet cortical gloss) with an organic tree-like branching network of thick round opaque sky-blue "
    "(#27D8FF to #58E4FF) 3D cylindrical blood-vessel tubes and crisp glossy white specular edge highlights spreading naturally OVER the "
    "cortical surface (organic surface vascular branching tree, never outlining or tracing every sulcal fold like a contour wireframe), "
    "zero text, zero labels, zero watermark. "
    "Zero glow, zero neon, zero particles, zero sparks, zero embers, zero light beams, zero bloom halo, zero smoke or haze."
)

R85_EP31_MODE1_STYLE_PROMPT = (
    "Vertical 9:16 ultra-clean 3D neuroanatomy render in the genuine Episode #31 Mode 1 X-Ray style over solid flat dark navy void (#040711), "
    "large hero framing filling 85% to 92% of the horizontal 9:16 frame width under unified bright top-left 45-degree studio keylight: "
    "smooth bright pearl-gray glossy mannequin head-and-shoulders bust (#C4CBD2 to #E4E8EC, never dark or black glass) whose upper cranium "
    "transitions seamlessly into clear see-through transparent glass cleanly enclosing a full interior almost-white matte gypsum-plaster 3D "
    "brain (#DCDFE3 to #F0F3F6) with an organic tree-like branching network of thick opaque sky-blue (#27D8FF to #58E4FF) 3D cylindrical "
    "blood-vessel tubes spreading naturally over the brain surface (never outlining every sulcal groove), zero text, zero labels, zero watermark. "
    "Zero glow, zero neon, zero particles, zero sparks, zero embers, zero light beams, zero bloom halo, zero smoke or haze."
)


def build_r85_31_brain_keyframe_spec(
    *,
    clip_number: int,
    brain_region: str,
    shot_scale: str = "split_cutaway",
    viewpoint: str | None = None,
    functional_highlight_color: str = "warm amber-gold",
    neural_state: str = "active",
    viewer_must_understand: str = "",
    project_id: str = "r85_project",
    mni152_guide_path: str | None = None,
    wikimedia_plate_title: str | None = None,
) -> dict[str, Any]:
    """
    R85 Ep #31 Brain Keyframe Spec Builder:
      - Pairs structural guide inputs (Wikimedia cutaway plate + `/tmp/aab_real_refs/` MNI152 silhouette)
        strictly with `canonical_assets/v1` approved SHA-locked brain anchors (`A01..A12`).
      - Enforces `R85_ANATOMY_VIEWPOINT_RULES` per target structure (`insula` -> `lateral_opercular_retracted`,
        `hippocampus` -> `inferior_lateral_cutaway` / `coronal_cutaway`, `thalamus`/`brainstem`/`csf` ->
        `midsagittal_cutaway`, `prefrontal cortex` -> `anterior_three_quarter_lateral`).
    """
    from pipeline.canonical_assets import resolve_canonical_approved_slot, select_canonical_brain_slot
    from pipeline.config import R85_ANATOMY_VIEWPOINT_RULES, R85_FLOW_BRAIN_SHOT_ROTATION
    from pipeline.real_world_reference_builder import NEUROANATOMY_CUTAWAY_MAP

    reg_low = str(brain_region or "").strip().lower()
    rule_key = next(
        (rk for rk in R85_ANATOMY_VIEWPOINT_RULES if rk in reg_low),
        None,
    )
    vp_rule = R85_ANATOMY_VIEWPOINT_RULES.get(rule_key or "", {})
    allowed_vps = vp_rule.get("allowed") or ("anterior_three_quarter_lateral",)
    forb_vps = vp_rule.get("forbidden") or ()
    eff_vp = str(viewpoint or allowed_vps[0]).strip().lower()
    if any(fb in eff_vp for fb in forb_vps) or (vp_rule and eff_vp not in allowed_vps):
        raise ValueError(
            f"[R85] Invalid viewpoint '{eff_vp}' for brain_region='{brain_region}': "
            f"allowed={list(allowed_vps)}, forbidden={list(forb_vps)}"
        )
    if shot_scale not in R85_FLOW_BRAIN_SHOT_ROTATION:
        raise ValueError(
            f"[R85] Unsupported shot_scale='{shot_scale}' (must be in {list(R85_FLOW_BRAIN_SHOT_ROTATION)})"
        )

    plate_entry = None
    for _, p_spec in NEUROANATOMY_CUTAWAY_MAP.items():
        if any(al in reg_low for al in (p_spec.get("aliases") or ())):
            plate_entry = p_spec
            break
    chosen_plate = wikimedia_plate_title or (
        (plate_entry.get("verified_commons_titles") or (None,))[0] if plate_entry else None
    )

    canonical_slot_id = select_canonical_brain_slot(
        brain_region=brain_region,
        viewpoint=eff_vp,
        mode="mode1" if shot_scale == "xray_head_dive" else "mode2",
        shot_scale=shot_scale,
        neural_state=neural_state,
        side_by_side=(shot_scale == "dual_brain_ab"),
    )
    resolved_can = resolve_canonical_approved_slot(canonical_slot_id, version="auto", verify_sha256=True)
    style_anchors = [resolved_can["staged_filename"]]
    master_lead = R85_EP31_MODE1_STYLE_PROMPT if shot_scale == "xray_head_dive" else R85_EP31_MASTER_STYLE_PROMPT

    state_clause = {
        "active": f"the focal {brain_region} structure itself is shaded in solid matte {functional_highlight_color} pigment with short opaque {functional_highlight_color} segments inside its connecting tube",
        "silenced": f"the focal {brain_region} structure sits in flat unlit matte slate-gray (#68707A) with internal vessels extinguished inside that zone",
        "severed": f"the solid {functional_highlight_color} tract segment to {brain_region} stops cleanly at a physical disconnection gap",
        "rerouted": f"short opaque {functional_highlight_color} tube segments bypass the muted slate-gray zone and enter the solid matte {functional_highlight_color} {brain_region}",
    }.get(str(neural_state or "active").lower(), f"the focal {brain_region} structure is shaded in solid matte {functional_highlight_color}")

    vp_phrase = eff_vp.replace("_", " ")
    prompt = (
        f"{master_lead} "
        f"Shot scale: {shot_scale.replace('_', ' ')} from an anatomically exact {vp_phrase} perspective; "
        f"{state_clause}."
    )
    return {
        "ref_id": f"kf_r85_c{int(clip_number):02d}_brain",
        "filename": f"kf_r85_c{int(clip_number):02d}_brain.png",
        "clip_number": int(clip_number),
        "category": "brain_anchor",
        "custom_brain_anchor": True,
        "r85_brain_clip": True,
        "r85_shot_scale": shot_scale,
        "brain_region": brain_region,
        "viewpoint": eff_vp,
        "functional_highlight_color": functional_highlight_color,
        "neural_state": neural_state,
        "viewer_must_understand": viewer_must_understand,
        "canonical_slot_id": canonical_slot_id,
        "canonical_library_version": resolved_can["library_version"],
        "canonical_sha256": resolved_can["sha256"],
        "conditioned_on": [resolved_can["staged_filename"]],
        "style_reference_anchors": style_anchors,
        "wikimedia_structural_plate": chosen_plate,
        "mni152_offscreen_guide": mni152_guide_path,
        "project_id": project_id,
        "prompt": prompt,
    }


__all__ = [
    "EXPRESSIVE_V8_PREVIS_CAMERA_ANGLES",
    "R85_EP31_MASTER_STYLE_PROMPT",
    "build_r85_31_brain_keyframe_spec",
    "ensure_expressive_v8_reference_pack",
    "ensure_porcelain_reference_pack",
    "normalize_strict_room_continuity_ledger",
    "populate_expressive_v8_reference_contract",
    "populate_porcelain_reference_contract",
    "sanitize_porcelain_contract_text",
    "select_dual_parallax_highlight_cuts",
    "select_hybrid_previs_hero_cuts",
]
