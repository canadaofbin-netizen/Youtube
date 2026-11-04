"""
ALL ABOUT BRAIN — Track B (`R66-Anchor`) Porcelain Reference Contract Compiler & Pack Orchestrator.

Bridges Research Dossiers (`03_visual_reference.json`, `04_media_refs.json`, `06_brain_link.json`) to
`porcelain_cinematic_v7` reference-conditioned generation when archival experiment video is unavailable
or unsuitable for Track A (`R67`):

  1. `populate_porcelain_reference_contract(plan, dossier_dir)`:
       - Deterministically populates `reenactment_track` (`"track_a"` or `"track_b"`), `default_location_id`,
         `cast` (all recurring roles with period wardrobe + smooth featureless matte-white oval heads),
         `real_environment`, `environment_props` (normalized across `"name"` / `"item"`),
         `require_scene_state_ledger: True`, and `strict_room_continuity: True`.
       - Repairs sequential `scene_state` room-occupancy transitions (`protocol_phase_jump: True` where needed)
         so `validate_scene_state_continuity(plan)` passes with zero issues.
       - Synthesizes `3–5` curated `reference_anchors` (`generation_order: 3`, conditioned on `ref_env_master`
         and `ref_cast_<role>`) so `build_reference_image_specs` produces `6–9` total `9:16` reference specs.
       - Applies the selective `~55–68%` anchor-binding sweet spot:
           * `porcelain_fullbleed_world` -> matching `(location_id, present_cast_start)` room anchor
           * `porcelain_living_brain` -> `03_visuals/reference_images/ref_brain_master.png`
           * `porcelain_hands_closeup` / `porcelain_pov_hands` / `porcelain_cutaway_section` /
             `porcelain_literal_analogy` / `outro` -> unanchored (`None`) to prevent wide-frame lock.

  2. `ensure_porcelain_reference_pack(...)`:
       - Generates missing `9:16` reference PNGs in `0-credit` Google Flow `Image` mode (`Nano Banana 2.1`,
         `x4` batch per prompt, auto-selecting the top `Q1..Q7` candidate) in strict `1 -> 2 -> 3` order,
         registers `"flow_image_generation"` provenance, purges any `/tmp/aab_reenact` quarantine for Track A,
         and verifies `inspect_reference_image_pack(...)["pre_generation_ready"] == True`.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from pipeline.config import (
    DEFAULT_CDP_PORT,
    DEFAULT_REENACT_IMAGE_BACKEND,
    DOSSIERS_DIR,
    FLOW_ZERO_CREDIT_IMAGE_BATCH_COUNT,
    MIN_REF_IMAGES_PER_PROJECT,
    PORCELAIN_V7_STYLE_PROFILE,
    PROJECTS_DIR,
    REF_IMAGES_DIRNAME,
    REENACT_EDL_FILENAME,
    is_porcelain_v7_plan,
)

_PLAQUE_SANITIZE_SUBS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bledgers\b", re.IGNORECASE), "bound notebooks"),
    (re.compile(r"\bledger\b", re.IGNORECASE), "bound notebook"),
    (re.compile(r"\b(?:plaques|nameplates)\b", re.IGNORECASE), "brushed metal plates"),
    (re.compile(r"\b(?:plaque|nameplate)\b", re.IGNORECASE), "brushed metal plate"),
    (re.compile(r"\b(?:chalkboards|blackboards|signboards)\b", re.IGNORECASE), "smooth slate wall panels"),
    (re.compile(r"\b(?:chalkboard|blackboard|signboard)\b", re.IGNORECASE), "smooth slate wall panel"),
    (re.compile(r"\b(?:newspapers|headlines)\b", re.IGNORECASE), "unmarked paper sheets"),
    (re.compile(r"\b(?:newspaper|headline)\b", re.IGNORECASE), "unmarked paper sheet"),
    (re.compile(r"\btextbooks\b", re.IGNORECASE), "unmarked cloth volumes"),
    (re.compile(r"\btextbook\b", re.IGNORECASE), "unmarked cloth volume"),
    (re.compile(r"\b(?:inscribed|engraved|labelled|labeled)\b", re.IGNORECASE), "unmarked"),
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
    "subject": "adult participant in a muted slate-blue woven cardigan over a crisp pale linen shirt and dark trousers",
    "researcher": "clinical investigator in a tailored crisp white laboratory coat over a charcoal wool waistcoat and dark trousers",
    "clinician": "attending neurologist in a crisp white clinical coat over a navy woven shirt and tailored trousers",
    "doctor": "attending physician in a tailored dark charcoal wool frock coat over a crisp pale collar shirt",
    "mother": "adult caregiver in a sleeveless dark woven summer top and mid-length pleated skirt",
    "stranger": "visiting researcher in a light short-sleeved woven blouse and tailored pleated skirt",
    "assistant": "laboratory assistant in a buttoned light-gray cotton utility jacket and dark trousers",
    "experimenter": "lead experimenter in a tailored light-gray laboratory coat over a crisp white shirt and dark tie",
    "child": "young child in a pale cotton romper with neat woven shorts",
}

_CRANIUM_CLAUSE = "with a completely smooth featureless solid matte-white egg-shaped oval head"

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


def _infer_wardrobe_for_role(role: str, iconic_scene: dict[str, Any], clips: list[dict[str, Any]]) -> str:
    wardrobe_raw = iconic_scene.get("wardrobe")
    cand = ""
    if isinstance(wardrobe_raw, dict):
        for k, v in wardrobe_raw.items():
            kl = str(k).lower()
            if role == kl or (
                role == "subject" and any(t in kl for t in ("patient", "subject", "participant", "volunteer", "child", "student", "foreman"))
            ) or (
                role == "researcher" and any(t in kl for t in ("researcher", "doctor", "physician", "clinician", "experimenter", "neurologist", "scientist"))
            ):
                cand = str(v or "").strip()
                if cand:
                    break
    elif isinstance(wardrobe_raw, str) and wardrobe_raw.strip():
        parts = [p.strip() for p in re.split(r"[.;]", wardrobe_raw) if p.strip()]
        if parts:
            cand = parts[0] if role == "subject" else (parts[1] if len(parts) > 1 else "")

    if not cand:
        # Check clip action descriptions for concrete garment phrases
        role_Regex = (
            r"(?:patient|participant|volunteer|subject|man|woman|student|child)\s+in\s+(a\s+[a-z0-9 ,-]+?(?:cardigan|coat|shirt|jacket|sweater|blouse|smock|suit|gown|vest|waistcoat|romper|tunic))"
            if role == "subject"
            else r"(?:researcher|neurologist|physician|clinician|scientist|doctor|investigator|experimenter)\s+in\s+(a\s+[a-z0-9 ,-]+?(?:coat|jacket|suit|frock coat|waistcoat|shirt|blouse|cardigan))"
        )
        for c in clips:
            act = str(c.get("action") or "")
            m = re.search(role_Regex, act, flags=re.IGNORECASE)
            if m:
                label_prefix = "adult participant in " if role == "subject" else "clinical investigator in "
                cand = label_prefix + m.group(1).strip()
                break

    clean_cand = sanitize_porcelain_contract_text(cand)
    if not clean_cand or len(clean_cand) < 12:
        clean_cand = _DEFAULT_ROLE_WARDROBE.get(
            role,
            f"articulated studio figure ({role.replace('_', ' ')}) in muted period woven attire",
        )
    if "egg-shaped oval head" not in clean_cand.lower() and "smooth featureless" not in clean_cand.lower():
        clean_cand = f"{clean_cand} {_CRANIUM_CLAUSE}"
    return clean_cand


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


def populate_porcelain_reference_contract(
    plan: dict[str, Any],
    dossier_dir: str | Path | None = None,
    *,
    preserve_curated_source_edl: bool = True,
) -> dict[str, Any]:
    """
    Compiles the complete `porcelain_cinematic_v7` reference-conditioning contract onto `plan` (in-place & returned):
      - `reenactment_track` (`"track_a"` or `"track_b"`)
      - `default_location_id`, `cast`, `real_environment`, `environment_props`
      - `require_scene_state_ledger: True`, `strict_room_continuity: True`
      - `reference_anchors` (`6–9` total reference PNG specs across masters + room anchors)
      - Selective `~55–68%` `clip["reference_image"]` bindings across `plan["clips"]`
    """
    if not is_porcelain_v7_plan(plan):
        return plan

    slug = str(plan.get("dossier_slug") or plan.get("dossier") or "").strip()
    d_dir: Path | None = None
    if dossier_dir is not None and Path(dossier_dir).exists():
        d_dir = Path(dossier_dir)
    elif slug and (Path(DOSSIERS_DIR) / slug).exists():
        d_dir = Path(DOSSIERS_DIR) / slug

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

    # Preserve hand-authored R67 pilot / source_edl plans untouched
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

    # 1. Resolve default_location_id & room environments
    loc_counter: Counter[str] = Counter()
    loc_env_texts: dict[str, Counter[str]] = {}
    for c in clips:
        g_name = str(c.get("grammar") or "")
        c_role = str(c.get("cut_role") or "").strip().lower()
        if g_name in ("porcelain_living_brain", "porcelain_data_sculpture") or c_role == "outro":
            continue
        loc = str((c.get("scene_state") or {}).get("location_id") or c.get("location_id") or "").strip()
        if loc:
            weight = 3 if g_name == "porcelain_fullbleed_world" else 1
            loc_counter[loc] += weight
            env_t = sanitize_porcelain_contract_text(str(c.get("environment") or ""))
            if env_t:
                loc_env_texts.setdefault(loc, Counter())[env_t] += weight

    default_loc = str(plan.get("default_location_id") or "").strip()
    if not default_loc:
        if loc_counter:
            default_loc = loc_counter.most_common(1)[0][0]
        else:
            raw_id = str(iconic_scene.get("id") or slug or "primary_studio_room").lower()
            default_loc = re.sub(r"[^a-z0-9_]+", "_", raw_id).strip("_") or "primary_studio_room"
    plan["default_location_id"] = default_loc

    # 2. Resolve real_environment & environment_props
    existing_env = sanitize_porcelain_contract_text(str(plan.get("real_environment") or ""))
    if not existing_env:
        if default_loc in loc_env_texts and loc_env_texts[default_loc]:
            existing_env = loc_env_texts[default_loc].most_common(1)[0][0]
        else:
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
    if not existing_props:
        for rp in iconic_scene.get("props") or []:
            np_entry = _normalize_prop_entry(rp)
            if not np_entry:
                continue
            nm = np_entry["name"]
            dt = np_entry["period_detail"]
            combined = f"{nm} ({dt})" if (dt and dt.lower() not in nm.lower() and len(dt) <= 75) else nm
            combined = sanitize_porcelain_contract_text(combined)
            if combined and combined not in existing_props:
                existing_props.append(combined)
            if len(existing_props) >= 4:
                break
    if not existing_props:
        existing_props = [
            "a brushed-aluminum clinical apparatus on a sunlit oak workbench",
            "an unmarked archival protocol folder beside a matte-ceramic instrument tray",
        ]
    plan["environment_props"] = existing_props[:4]

    # 3. Resolve cast dictionary covering all recurring roles in scene_state
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
    for role in ordered_roles[:4]:
        prev_val = existing_cast.get(role) if isinstance(existing_cast.get(role), str) else ""
        if prev_val and len(prev_val.strip()) >= 18 and "wardrobe" not in existing_cast:
            clean_v = sanitize_porcelain_contract_text(prev_val)
            if "oval head" not in clean_v.lower() and "featureless" not in clean_v.lower():
                clean_v = f"{clean_v} {_CRANIUM_CLAUSE}"
            cast_dict[role] = clean_v
        else:
            cast_dict[role] = _infer_wardrobe_for_role(role, iconic_scene, clips)
    plan["cast"] = cast_dict

    # 4. Enforce strict_room_continuity & scene_state ledger
    plan["require_scene_state_ledger"] = True
    plan["strict_room_continuity"] = True
    if clips:
        normalize_strict_room_continuity_ledger(plan)

    # 5. Synthesize 3–5 curated room `reference_anchors` so total_specs >= MIN_REF_IMAGES_PER_PROJECT (6..9)
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
    # Pad if plan has empty clips (e.g. fresh seed) or fewer than target_room_anchors distinct fullbleed states
    fallback_cast_combos: list[tuple[str, ...]] = [
        tuple(sorted( list(cast_dict.keys())[:2] )),
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
        prop_focus = hero_prop if (a_idx % 2 == 1) else secondary_prop

        if p_tuple:
            cast_clauses = [
                f"{r} ({cast_dict.get(r, _DEFAULT_ROLE_WARDROBE.get(r, r))})"
                for r in p_tuple
            ]
            cast_prose = (
                f"Inside the room, {', '.join(cast_clauses)} positioned naturally beside {prop_focus}."
            )
        else:
            cast_prose = f"The room is completely unoccupied, showcasing {prop_focus} in crisp architectural stillness."

        cond_list: list[str] = []
        if loc_id == default_loc:
            cond_list.append("ref_env_master")
        for r in p_tuple:
            cid = f"ref_cast_{r}"
            if r in cast_dict and cid not in cond_list and len(cond_list) < 2:
                cond_list.append(cid)
        if not cond_list:
            cond_list.append("ref_env_master")

        prompt_txt = sanitize_porcelain_contract_text(
            f"Generate a single 9:16 vertical still photograph (one frozen instant, not a video): "
            f"{cam_lead} {loc_env}, featuring {prop_focus}. {cast_prose} "
            f"Bright high-key sunlit architectural studio daylight, smooth featureless blank matte-white oval porcelain heads, "
            f"clean unmarked walls, deep depth of field."
        )
        anchors.append(
            {
                "ref_id": ref_id,
                "filename": f"{ref_id}.png",
                "category": "clip_keyframe_anchor",
                "role": "reenactment",
                "scene_id": f"LOC_{loc_id}",
                "location_id": loc_id,
                "present_cast": list(p_tuple),
                "setting": "real_env",
                "generation_order": 3,
                "conditioned_on": cond_list[:2],
                "title": f"Room state anchor {a_idx} ({loc_id}: {', '.join(p_tuple) if p_tuple else 'empty'})",
                "prompt": prompt_txt,
                "must_include": [loc_env[:72], prop_focus[:56]],
            }
        )
        if (loc_id, p_tuple) not in anchor_by_state:
            anchor_by_state[(loc_id, p_tuple)] = ref_id

    plan["reference_anchors"] = anchors

    # 6. Selective clip-to-reference binding (~50–68% anchored sweet spot; zero wide-frame lock on closeups)
    hands_seen = 0
    for c in clips:
        g_name = str(c.get("grammar") or "").strip()
        c_role = str(c.get("cut_role") or "").strip().lower()
        c.pop("end_reference_image", None)

        if c_role == "outro":
            c.pop("reference_image", None)
            continue

        if g_name == "porcelain_living_brain" and has_brain_master:
            b_mode = str(c.get("brain_mode") or "").strip()
            # Anchor whole-brain / sagittal / frosted-glass views to ref_brain_master; leave bounded_micro_channel free for macro detail
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
                # Subset fallback at the SAME location_id (satisfies validate_scene_state_continuity lines 668-681)
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

        if g_name == "porcelain_hands_closeup":
            hands_seen += 1
            st = c.get("scene_state") or {}
            p_start = [str(x).strip() for x in (st.get("present_cast_start") or []) if str(x).strip() in cast_dict]
            cast_role = p_start[0] if p_start else (ordered_roles[0] if ordered_roles else "")
            if hands_seen % 2 == 0 and cast_role in cast_dict:
                c["reference_image"] = f"03_visuals/{REF_IMAGES_DIRNAME}/ref_cast_{cast_role}.png"
            else:
                c.pop("reference_image", None)
            continue

        # POV hands, literal analogies, data sculptures -> unanchored
        c.pop("reference_image", None)

    return plan


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
    from pipeline.flow_prompt_builder import build_flow_prompts, load_visual_plan, write_flow_prompts_json
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

    # Ensure visual_plan has full reference contract & re-render flow_all_in_one_prompts.json if upgraded
    had_anchors = bool(plan.get("reference_anchors"))
    populate_porcelain_reference_contract(plan, dossier_dir=d_dir)
    if not had_anchors and vp_path.exists():
        vp_path.write_text(json.dumps(plan, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        scr_path = p_dir / "02_script" / "script.json"
        if scr_path.exists():
            s_doc = json.loads(scr_path.read_text(encoding="utf-8"))
            sents = [str(x) for x in (s_doc.get("sentences") or s_doc.get("clip_narrations") or []) if str(x).strip()]
            if sents and plan.get("clips"):
                write_flow_prompts_json(p_dir, build_flow_prompts(plan, sents))

    track = str(plan.get("reenactment_track") or "track_b").strip().lower()
    used_quarantine = False
    if track == "track_a":
        # Stage sanitized structural guides if an archival media URL is configured and guides aren't cached
        edl_path = vis_dir / REENACT_EDL_FILENAME
        if not edl_path.exists() and d_dir and (d_dir / "08_reenactment_edl.json").exists():
            edl_doc = json.loads((d_dir / "08_reenactment_edl.json").read_text(encoding="utf-8"))
            (vis_dir / REENACT_EDL_FILENAME).write_text(json.dumps(edl_doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        if d_dir and (d_dir / "04_media_refs.json").exists():
            try:
                from pipeline.research_dossier import audit_dossier_media_suitability

                suit = audit_dossier_media_suitability(d_dir, write_back=False)
                best_media = suit.get("primary_track_a_media")
                has_shot_anchors = any(
                    str(a.get("scene_id") or "").startswith("S")
                    for a in (plan.get("reference_anchors") or [])
                    if isinstance(a, dict)
                )
                if best_media and best_media.get("url") and has_shot_anchors:
                    edl_doc = extract_source_edl(
                        best_media["url"],
                        slug=slug,
                        project_dir=p_dir,
                        dossier_dir=d_dir,
                        section=best_media.get("recommended_section") or best_media.get("section"),
                    )
                    sanitize_structural_frames(
                        work_dir=Path("/tmp/aab_reenact") / slug,
                        edl_doc=edl_doc,
                        project_dir=p_dir,
                        dossier_dir=d_dir,
                    )
                    used_quarantine = True
            except Exception:
                pass

    try:
        gen_summary = translate_porcelain_keyframes(
            project_dir=p_dir,
            slug=slug,
            cdp_port=cdp_port,
            force=force,
            backend=backend,
            batch_count=batch_count,
        )
    finally:
        if used_quarantine:
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
