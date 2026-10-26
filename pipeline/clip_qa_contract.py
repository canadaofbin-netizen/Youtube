"""
ALL ABOUT BRAIN - Per-Video / Per-Clip QA Contract Compiler & Post-Generation Verification Engine.

Solves the root cause of topic-blind QA:
  1. `compile_clip_qa_contract(project_dir, dossier_dir=None, save=True)`:
     Compiles an explicit per-video, per-clip QA contract (`03_visuals/clip_qa_contract.json`) from the
     research dossier (`03_visual_reference.json`, `06_brain_link.json`), `02_script/script.json`, and
     `03_visuals/visual_plan.json` BEFORE generation. Every clip gets:
       - Concrete `required_entities` (cast, wardrobe, props, actions, landmarks — never bare scene IDs like "S1")
       - Explicit `forbidden_elements` (human skin, text/watermarks, R53 green/cyan particle bleed, scene-specific bans)
       - `narration_grounding` (temporal clause beats + 2-beat scale/state progression requirements)
       - `conditioning_contract` (per-clip start/key ref + shared `ref_brain_master` lock across all brain clips)
       - `anatomical_contract` (`canonical_region`, `hemisphere`, `expected_facing`, `expected_signal_roi_norm`,
         `forbidden_roi_norm`, `require_crimson_lesion`, `forbid_crimson_lesion`)
       - `motion_contract` (camera-compensated residual subject flow + multi-window scene progression)

  2. `verify_clips_against_contract(project_dir, contract=None, save_report=True, render_strips=True)`:
     Audits rendered `reference_images/ref_*.png`, `flow_native_clips/clip_*.mp4`, and optional assembled
     `05_assembly/final_shorts_1080x1920.mp4` against `clip_qa_contract.json`:
       - 5-point `[0%, 25%, 50%, 75%, 95%]` spatial-grid LAB + Canny edge + HSV continuity (`min` not `max`,
         catching late-clip morphing at 60-95%)
       - Cross-brain-clip silhouette & structural consistency against `ref_brain_master` and pairwise across brain clips
       - Anatomical lesion/signal ROI centroid & coronal-symmetry check (catching central/bilateral lesions or wrong facing)
       - R53 localized neon green/cyan particle dot & bleed detector
       - Camera-motion-compensated residual subject/prop action progression (catching static tableaux)
       - Cryptographic SHA-256 binding across contract, refs, clips, and final MP4 (`is_clip_qa_report_fresh`)
       - Automated 6-panel per-clip diagnostic contact strips (`03_visuals/qa_contact_strips/clip_XX_5frame_strip.png`)
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

import cv2
import numpy as np

from pipeline.config import (
    BRAIN_SETTINGS,
    FLOW_ASPECT_SHORTS,
    MIN_CLIP_SIZE_BYTES,
    PROJECTS_DIR,
    REF_IMAGE_HUMAN_SKIN_MAX,
    REF_IMAGE_PORCELAIN_RATIO_MIN,
    REF_IMAGES_DIRNAME,
    clip_roles,
)

CLIP_QA_CONTRACT_FILENAME = "clip_qa_contract.json"
CLIP_QA_REPORT_FILENAME = "clip_contract_qa_report.json"
CLIP_SEMANTIC_REVIEW_FILENAME = "clip_semantic_review.json"
CLIP_QA_STRIPS_DIRNAME = "qa_contact_strips"
SAMPLE_WINDOWS_5PT: tuple[float, ...] = (0.0, 0.25, 0.50, 0.75, 0.95)
AUDIO_TRUE_PEAK_MAX_DBFS = -1.0
AUDIO_LIMITER_CEILING_DBFS = -1.5


def compute_sha256(path: Path) -> str:
    """Computes full hex SHA-256 digest of a file on disk."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _clean(text: Any) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _resolve_project_inputs(project_dir: Path, dossier_dir: Path | None = None) -> tuple[dict[str, Any], list[str], Path | None, dict[str, str]]:
    p_dir = Path(project_dir)
    plan_candidates = [p_dir / "03_visuals" / "visual_plan.json", p_dir / "visual_plan.json"]
    script_candidates = [p_dir / "02_script" / "script.json", p_dir / "script.json"]

    plan_path = next((p for p in plan_candidates if p.exists()), None)
    script_path = next((p for p in script_candidates if p.exists()), None)

    from pipeline.flow_prompt_builder import load_visual_plan

    if plan_path is not None:
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
    else:
        plan = load_visual_plan(project_dir=p_dir)

    narrations: list[str] = []
    if script_path is not None:
        raw_script = json.loads(script_path.read_text(encoding="utf-8"))
        narrations = [str(x) for x in (raw_script.get("clip_narrations") or [])]

    slug = _clean(plan.get("dossier"))
    if dossier_dir is None and slug:
        for cand in (
            p_dir.parent.parent / "research_dossiers" / slug,
            PROJECTS_DIR.parent / "research_dossiers" / slug,
        ):
            if cand.exists():
                dossier_dir = cand
                break
    if dossier_dir is None:
        from pipeline.research_dossier import resolve_dossier_for_project

        dossier_dir = resolve_dossier_for_project(slug or p_dir.name, root=p_dir.parent.parent / "research_dossiers")

    hashes: dict[str, str] = {}
    if plan_path and plan_path.exists():
        hashes["visual_plan_sha256"] = compute_sha256(plan_path)
    if script_path and script_path.exists():
        hashes["script_sha256"] = compute_sha256(script_path)
    return plan, narrations, dossier_dir, hashes


def extract_clip_required_entities(
    plan: dict[str, Any],
    role: str,
    scene_id: str,
    setting: str,
    narration: str,
    scene_text: str = "",
) -> list[str]:
    """
    Extracts concrete, human-verifiable visual entities/actions/landmarks for a clip.
    Never falls back to bare opaque IDs like ['S1'] or ['BRAIN'].
    """
    from pipeline.scene_blueprint import cast_for_shot, key_visual_for_scene

    entities: list[str] = []
    is_brain = setting in BRAIN_SETTINGS

    if is_brain:
        bl = (plan.get("brain_link") or {}).get(role) or {}
        region = _clean(bl.get("canonical_region") or bl.get("region") or plan.get("target_region") or "brain cross-section")
        state = _clean(bl.get("state") or bl.get("function") or "")
        cue = _clean(bl.get("story_cue") or bl.get("narration_bridge") or "")
        entities.append(f"porcelain_brain_anatomy: {region}")
        if state:
            entities.append(f"neural_state: {state[:90]}")
        if cue:
            entities.append(f"story_link: {cue[:90]}")
        if "left eye" in f"{narration} {scene_text} {cue}".lower():
            entities.append("landmark: left eye socket & left prefrontal cross-section directly behind left eye")
        entities.append("r53_signal: restrained internal warm-amber/ivory tract conduction (zero green/blue flying particles)")
    else:
        kv = key_visual_for_scene(plan, scene_id)
        if kv:
            for item in kv.get("must_show") or []:
                val = _clean(item)
                if val:
                    entities.append(val)
        for m in plan.get("must_have_scenes") or []:
            if isinstance(m, dict) and str(m.get("id") or m.get("scene_id") or "") == scene_id:
                hook = _clean(m.get("recognition_hook") or "")
                if hook:
                    entities.append(f"iconic_scene: {hook[:105]}")
                for tok in m.get("required_tokens") or []:
                    t_clean = _clean(tok)
                    if t_clean and all(t_clean.lower() not in e.lower() for e in entities):
                        entities.append(f"prop_or_element: {t_clean}")

        for c_entry in cast_for_shot(plan, role)[:2]:
            cid = _clean(c_entry.get("id", "subject")).replace("_", " ")
            look = _clean(c_entry.get("look", ""))[:80]
            if look:
                entities.append(f"cast ({cid}): matte-white porcelain mannequin wearing {look}")

        shot = (plan.get("shots") or {}).get(role) or {}
        if isinstance(shot, dict):
            act = _clean(shot.get("action", ""))
            prop_chg = _clean(shot.get("prop_change", ""))
            env = _clean(shot.get("environment", "")) or _clean((plan.get("scenes") or {}).get(scene_id, ""))
            if env:
                entities.append(f"environment: {env[:90]}")
            if act:
                entities.append(f"action: {act[:100]}")
            if prop_chg:
                entities.append(f"prop_progression: {prop_chg[:100]}")

        if not entities and scene_text:
            entities.append(f"scene_depiction: {scene_text[:110]}")
        if not entities:
            entities.append(f"porcelain_reenactment_{role}: {_clean(narration)[:90] or 'documentary action beat'}")

    # Deduplicate while preserving order
    deduped: list[str] = []
    seen: set[str] = set()
    for e in entities:
        key = e.lower().strip()
        if key and key not in seen and key not in {"s1", "s2", "s3", "s4", "brain"}:
            seen.add(key)
            deduped.append(e)
    return deduped[:8]


def infer_forbidden_elements(
    plan: dict[str, Any],
    role: str,
    setting: str,
    narration: str,
    scene_text: str,
) -> list[str]:
    is_brain = setting in BRAIN_SETTINGS
    combined = f"{narration} {scene_text} {json.dumps((plan.get('shots') or {}).get(role) or {})}".lower()
    bans = [
        "real_human_face_or_skin",
        "on_screen_text_logo_or_watermark",
        "r53_neon_green_or_cyan_particles",
    ]
    if is_brain:
        bans.append("flying_sparks_or_scattered_bokeh")
        bans.append("mismatched_brain_bust_angle_or_mid_clip_morph")
    if "hippocamp" in combined:
        bans.append("marine_seahorse_animal_shape")
    if any(tok in combined for tok in ("one modern", "single researcher", "lone porcelain researcher", "strictly one", "one neuroscientist")):
        bans.append("cloned_duplicate_background_mannequins")
    if any(tok in combined for tok in ("stagecoach", "mountain road", "mountain pass", "granite", "ox cart", "railroad cut")):
        bans.append("indoor_red_curtains_or_giant_golden_disc")
    return bans


def _build_narration_grounding(
    plan: dict[str, Any],
    role: str,
    setting: str,
    narration: str,
    scene_text: str,
) -> dict[str, Any]:
    shot = (plan.get("shots") or {}).get(role) or {}
    cam_txt = _clean(shot.get("camera", "")) if isinstance(shot, dict) else ""
    combined_low = f"{cam_txt} {scene_text} {narration}".lower()

    clauses = [c.strip() for c in re.split(r"(?<=[.!?])\s+|\s*;\s*|\s+—\s+", _clean(narration)) if c.strip()]
    if len(clauses) == 1 and ", " in clauses[0]:
        sub = [s.strip() for s in re.split(r",\s+(?:yet|but|while|then|until|leaving|proving)\s+", clauses[0], flags=re.I) if s.strip()]
        if len(sub) >= 2:
            clauses = sub

    requires_scale_pullback = bool(
        re.search(r"\b(pulls?\s+back|pulling\s+back|pull-back|widens?\s+from|zooms?\s+out|pulls?\s+out)\b", combined_low)
    )
    has_temporal_transition = bool(
        requires_scale_pullback
        or len(clauses) >= 2
        or re.search(r"\b(minutes\s+later|months\s+later|yet\s+minutes|until\s+it|which\s+proves)\b", combined_low)
    )

    if len(clauses) >= 2:
        beats = [
            {"window_pct": [0.0, 0.45], "narration_clause": clauses[0]},
            {"window_pct": [0.45, 1.0], "narration_clause": " ".join(clauses[1:])},
        ]
    else:
        beats = [{"window_pct": [0.0, 1.0], "narration_clause": _clean(narration)}]

    return {
        "clauses": clauses,
        "beats": beats,
        "requires_scale_pullback": requires_scale_pullback,
        "requires_two_beat_progression": bool(has_temporal_transition and setting not in BRAIN_SETTINGS),
    }


def _build_anatomical_contract(
    plan: dict[str, Any],
    role: str,
    setting: str,
    narration: str,
    scene_text: str,
    dossier_brain_links: list[dict[str, Any]],
) -> dict[str, Any] | None:
    if setting not in BRAIN_SETTINGS:
        return None

    bl = (plan.get("brain_link") or {}).get(role) or {}
    canonical_region = _clean(
        bl.get("canonical_region") or bl.get("region") or plan.get("target_region") or "cerebral_cortex"
    )
    reg_norm = canonical_region.lower().replace("_", " ")
    matched_links = [
        x
        for x in dossier_brain_links
        if isinstance(x, dict)
        and (
            str(x.get("role") or "").strip().lower() == role
            or (
                reg_norm
                and reg_norm != "cerebral cortex"
                and (
                    reg_norm in str(x.get("region") or x.get("canonical_region") or "").lower().replace("_", " ")
                    or str(x.get("region") or x.get("canonical_region") or "").lower().replace("_", " ") in reg_norm
                )
            )
        )
    ]
    scoped_dossier_txt = " ".join(json.dumps(x) for x in matched_links).lower()
    all_dossier_txt = " ".join(json.dumps(x) for x in dossier_brain_links).lower()
    shot_spec = (plan.get("shots") or {}).get(role) or {}
    authored_txt = f"{narration} {json.dumps(bl)} {json.dumps(shot_spec)} {reg_norm}".lower()
    local_txt = f"{authored_txt} {scene_text}".lower()
    clip_txt = f"{authored_txt} {scoped_dossier_txt}".strip()

    left_keys = (
        "behind his left eye",
        "behind the left eye",
        "left cheekbone",
        "left orbitofrontal",
        "left ventromedial",
        "left prefrontal",
        "left frontal",
        "left temple",
        "left hemisphere",
    )
    right_keys = (
        "right hemisphere",
        "right parietal",
        "right temporal",
        "right prefrontal",
        "right frontal",
        "right orbitofrontal",
        "behind his right eye",
        "behind the right eye",
    )
    has_left = any(k in clip_txt for k in left_keys)
    has_right = any(k in clip_txt for k in right_keys)
    if has_left and not has_right:
        hemisphere = "left"
    elif has_right and not has_left:
        hemisphere = "right"
    elif has_left and has_right:
        hemisphere = "bilateral_or_medial"
    elif any(k in all_dossier_txt for k in left_keys) and not any(k in all_dossier_txt for k in right_keys):
        hemisphere = "left"
    elif any(k in all_dossier_txt for k in right_keys) and not any(k in all_dossier_txt for k in left_keys):
        hemisphere = "right"
    else:
        hemisphere = "bilateral_or_medial"

    if any(k in clip_txt for k in ("orbitofrontal", "ventromedial", "vmpfc", "behind his left eye", "behind the left eye", "behind his right eye", "behind the right eye", "prefrontal")):
        region_group = "anterior_prefrontal_behind_eye"
    elif any(k in clip_txt for k in ("hippocamp", "fornix", "amygdala", "temporal lobe")):
        region_group = "deep_medial_temporal_limbic"
    else:
        region_group = "cortical_tract"

    if "translucent" in local_txt and "whole brain" in local_txt:
        view_plane = "translucent_whole_brain"
    elif hemisphere == "left":
        view_plane = "three_quarter_left_parasagittal"
    elif hemisphere == "right":
        view_plane = "three_quarter_right_parasagittal"
    else:
        view_plane = "anatomical_cross_section"

    physical_lesion_words = (
        "fracture",
        "lesion",
        "severed",
        "torn",
        "damaged",
        "pierced",
        "wound",
        "stroke",
        "infarct",
        "hemorrhage",
        "rod trajectory",
        "iron bar",
        "iron rod",
    )
    functional_gate_only = any(
        w in authored_txt for w in ("inhibitory gate", "attention spotlight", "healthy", "suppresses", "suppressing", "shuts out", "filters out")
    ) and not any(w in authored_txt for w in physical_lesion_words)
    has_damage_words = any(w in authored_txt for w in physical_lesion_words)
    explicit_intact = (
        ("zero red" in authored_txt)
        or ("no lesion" in authored_txt)
        or (role == "step1" and "intact" in authored_txt and not has_damage_words)
    )
    is_bypass_recovery = role == "step3" or any(
        w in authored_txt for w in ("bypass", "reroute", "reconnect", "around the damaged", "around the dimmed")
    )

    require_crimson_lesion = bool(has_damage_words and not functional_gate_only and not explicit_intact and not is_bypass_recovery)
    forbid_crimson_lesion = bool(explicit_intact)

    # Normalized ROI inside detected head/brain bounding box [x0, y0, x1, y1]:
    # Head+bust bbox spans crown (y=0.0) to shoulders (y=1.0), so the cranium sits in y=0.04..0.62
    # (including dorsal prefrontal bypass tracts around y=0.10..0.22 while excluding neck/chest y>0.62).
    if hemisphere == "left" and region_group == "anterior_prefrontal_behind_eye":
        expected_signal_roi_norm = [0.04, 0.04, 0.66, 0.62]
        forbidden_roi_norm = [0.70, 0.0, 1.0, 1.0]  # Posterior occipital back of head
        expected_facing = "left"
        forbid_symmetric_coronal = True
    elif hemisphere == "right" and region_group == "anterior_prefrontal_behind_eye":
        expected_signal_roi_norm = [0.34, 0.04, 0.96, 0.62]
        forbidden_roi_norm = [0.0, 0.0, 0.30, 1.0]
        expected_facing = "right"
        forbid_symmetric_coronal = True
    elif hemisphere in ("left", "right") and view_plane != "translucent_whole_brain":
        expected_signal_roi_norm = [0.08, 0.06, 0.92, 0.72]
        forbidden_roi_norm = []
        expected_facing = hemisphere
        forbid_symmetric_coronal = False
    else:
        expected_signal_roi_norm = [0.08, 0.06, 0.92, 0.82]
        forbidden_roi_norm = []
        expected_facing = "any"
        forbid_symmetric_coronal = False

    return {
        "canonical_region": canonical_region,
        "region_group": region_group,
        "hemisphere": hemisphere,
        "view_plane": view_plane,
        "expected_facing": expected_facing,
        "forbid_symmetric_coronal": forbid_symmetric_coronal,
        "require_crimson_lesion": require_crimson_lesion,
        "forbid_crimson_lesion": forbid_crimson_lesion,
        "expected_signal_roi_norm": expected_signal_roi_norm,
        "forbidden_roi_norm": forbidden_roi_norm,
    }


def compile_clip_qa_contract(
    project_dir: Path,
    dossier_dir: Path | None = None,
    save: bool = True,
) -> dict[str, Any]:
    """
    Compiles `03_visuals/clip_qa_contract.json` from research dossier + script.json + visual_plan.json.
    """
    from pipeline.flow_prompt_builder import build_flow_prompts, resolve_clip_setting
    from pipeline.scene_blueprint import key_visual_clip_numbers

    p_dir = Path(project_dir)
    plan, narrations, resolved_dossier, source_hashes = _resolve_project_inputs(p_dir, dossier_dir=dossier_dir)

    n_clips = int(plan.get("clip_count") or len(narrations) or 10)
    roles = clip_roles(n_clips)
    eff_narrations = narrations if len(narrations) == n_clips else [
        narrations[i] if i < len(narrations) else "" for i in range(n_clips)
    ]

    built_clips: list[dict[str, Any]] = []
    try:
        built_clips = build_flow_prompts(
            plan,
            [n or "In this historical case, a single moment changed neuroscience forever." for n in eff_narrations],
            aspect=str(plan.get("aspect") or FLOW_ASPECT_SHORTS),
        )
    except Exception:
        built_clips = [
            {
                "clip_number": i + 1,
                "role": roles[i],
                "setting": resolve_clip_setting(plan, roles[i]),
                "scene_id": ((plan.get("shots") or {}).get(roles[i]) or {}).get("scene_id") or ("BRAIN" if resolve_clip_setting(plan, roles[i]) in BRAIN_SETTINGS else "S1"),
                "scene": "",
            }
            for i in range(n_clips)
        ]

    dossier_brain_links: list[dict[str, Any]] = []
    if resolved_dossier and Path(resolved_dossier).exists():
        bl_file = Path(resolved_dossier) / "06_brain_link.json"
        if bl_file.exists():
            try:
                bl_data = json.loads(bl_file.read_text(encoding="utf-8"))
                dossier_brain_links = list(bl_data.get("links") or [])
            except Exception:
                dossier_brain_links = []

    key_clip_map = key_visual_clip_numbers(plan, built_clips)
    key_clips = {min(nums) for nums in key_clip_map.values() if nums}
    brain_clip_nums = [int(c["clip_number"]) for c in built_clips if str(c.get("setting") or "") in BRAIN_SETTINGS]
    has_brain_clips = len(brain_clip_nums) > 0

    ref_spec_prompts: dict[int, str] = {}
    ref_specs_file = p_dir / "03_visuals" / "reference_image_specs.json"
    if ref_specs_file.exists():
        try:
            rs_data = json.loads(ref_specs_file.read_text(encoding="utf-8"))
            for item in rs_data.get("clip_anchors") or rs_data.get("all_specs") or []:
                if item.get("clip_number") is not None and item.get("prompt"):
                    ref_spec_prompts[int(item["clip_number"])] = str(item["prompt"])
        except Exception:
            ref_spec_prompts = {}

    clip_contracts: list[dict[str, Any]] = []
    for idx, c in enumerate(built_clips):
        c_num = int(c["clip_number"])
        role = str(c["role"])
        setting = str(c.get("setting") or resolve_clip_setting(plan, role))
        is_brain = setting in BRAIN_SETTINGS
        scene_id = str(c.get("scene_id") or ("BRAIN" if is_brain else "S1"))
        scene_txt = _clean(c.get("scene") or "")
        narr = _clean(eff_narrations[idx] if idx < len(eff_narrations) else "")

        ref_ids = [f"ref_clip_{c_num:02d}"]
        if c_num in key_clips:
            ref_ids.append(f"ref_clip_{c_num:02d}_key")

        grounding = _build_narration_grounding(plan, role, setting, narr, scene_txt)
        anat_contract = _build_anatomical_contract(plan, role, setting, narr, scene_txt, dossier_brain_links)
        req_entities = extract_clip_required_entities(plan, role, scene_id, setting, narr, scene_txt)
        forb_elems = infer_forbidden_elements(
            plan,
            role,
            setting,
            narr,
            f"{scene_txt} {ref_spec_prompts.get(c_num, '')}".strip(),
        )

        clip_contracts.append(
            {
                "clip_number": c_num,
                "role": role,
                "scene_id": scene_id,
                "setting": setting,
                "is_brain_clip": is_brain,
                "is_key_visual_clip": c_num in key_clips,
                "narration": narr,
                "required_entities": req_entities,
                "forbidden_elements": forb_elems,
                "narration_grounding": grounding,
                "conditioning_contract": {
                    "primary_ref_id": f"ref_clip_{c_num:02d}",
                    "must_match_ref_ids": ref_ids,
                    "shared_master_anchor": "ref_brain_master" if is_brain else "ref_env_master",
                    "sample_windows_pct": list(SAMPLE_WINDOWS_5PT),
                    "aggregation_mode": "pullback_windowed" if grounding["requires_scale_pullback"] else "strict_min_5pt",
                    "min_continuity_score": 0.45 if grounding["requires_scale_pullback"] else (0.52 if is_brain else 0.46),
                    "max_late_morph_drop": 0.42 if grounding["requires_scale_pullback"] else (0.28 if is_brain else 0.34),
                },
                "anatomical_contract": anat_contract,
                "motion_contract": {
                    "min_raw_flow_mean": 0.14,
                    "min_residual_subject_flow_p90": 0.40 if is_brain else 0.75,
                    "min_active_window_ratio": 0.50,
                    "min_beat1_vs_beat2_shift": 0.08 if grounding["requires_scale_pullback"] else 0.025,
                    "speedup_bounds": [0.85, 1.25],
                },
            }
        )

    contract = {
        "schema_version": 1,
        "compiled_at": datetime.now(timezone.utc).isoformat(),
        "project_id": p_dir.name,
        "dossier": plan.get("dossier"),
        "visual_mode": str(plan.get("visual_mode") or "HYBRID"),
        "aspect": str(plan.get("aspect") or FLOW_ASPECT_SHORTS),
        "clip_count": n_clips,
        "has_brain_clips": has_brain_clips,
        "shared_brain_master_anchor": "ref_brain_master" if has_brain_clips else None,
        "cross_brain_continuity_contract": {
            "enabled": len(brain_clip_nums) >= 2,
            "brain_clip_numbers": brain_clip_nums,
            "master_anchor_id": "ref_brain_master",
            "min_pairwise_silhouette_iou": 0.45,
            "min_pairwise_spatial_corr": 0.52,
            "max_bg_luma_spread": 45.0,
            "require_consistent_facing": True,
        },
        "r53_particle_ban": {
            "enabled": True,
            "max_brain_neon_green_cyan_ratio": 0.0025,
            "max_floating_particle_dots": 2,
        },
        "audio_contract": {
            "max_true_peak_dbfs": AUDIO_TRUE_PEAK_MAX_DBFS,
            "limiter_ceiling_dbfs": AUDIO_LIMITER_CEILING_DBFS,
        },
        "source_hashes": source_hashes,
        "clips": clip_contracts,
    }

    if save:
        out_dir = p_dir / "03_visuals" if (p_dir / "03_visuals").exists() or (p_dir / "02_script").exists() else p_dir
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / CLIP_QA_CONTRACT_FILENAME).write_text(
            json.dumps(contract, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    return contract


# ==============================================================================
# Deterministic Computer Vision Inspection Primitives (Zero Paid APIs)
# ==============================================================================

def sample_video_frames_5pt(
    video_path: Path,
    pcts: Sequence[float] = SAMPLE_WINDOWS_5PT,
) -> tuple[dict[str, Any], list[tuple[float, np.ndarray]]]:
    """Decodes exact frames at `[0%, 25%, 50%, 75%, 95%]` with sequential fallback so 95% never fails."""
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        return {"readable": False, "width": 0, "height": 0, "fps": 0.0, "frame_count": 0, "duration_sec": 0.0}, []

    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 24.0)
    declared_n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)

    all_frames: list[np.ndarray] = []
    # Sequential read guarantees exact frame count even on variable-GOP / webm-remuxed MP4s
    max_read = max(declared_n + 30, 600)
    for _ in range(max_read):
        ok, frm = cap.read()
        if not ok or frm is None or frm.size == 0:
            break
        all_frames.append(frm)
    cap.release()

    actual_n = len(all_frames)
    if actual_n == 0:
        return {"readable": False, "width": w, "height": h, "fps": fps, "frame_count": 0, "duration_sec": 0.0}, []

    h_actual, w_actual = all_frames[0].shape[:2]
    dur = round(actual_n / max(fps, 1.0), 3)
    sampled: list[tuple[float, np.ndarray]] = []
    for p in pcts:
        idx = min(actual_n - 1, max(0, int(round(p * (actual_n - 1)))))
        sampled.append((float(p), all_frames[idx]))

    meta = {
        "readable": True,
        "width": w_actual,
        "height": h_actual,
        "fps": round(fps, 3),
        "frame_count": actual_n,
        "duration_sec": dur,
        "_all_frames": all_frames,
    }
    return meta, sampled


def _foreground_mask(bgr_small: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(bgr_small, cv2.COLOR_BGR2GRAY).astype(np.float32)
    border = np.concatenate([gray[:6, :].ravel(), gray[-6:, :].ravel(), gray[:, :6].ravel(), gray[:, -6:].ravel()])
    if float(np.std(border)) < 24.0:
        bg_med = float(np.median(border))
        diff = np.abs(gray - bg_med)
        thresh = max(16.0, float(np.percentile(diff, 55)) * 0.65)
        mask = (diff >= thresh).astype(np.uint8)
    else:
        gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
        gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
        mag = cv2.magnitude(gx, gy)
        hi_luma = gray >= float(np.percentile(gray, 72))
        hi_edge = mag >= float(np.percentile(mag, 70))
        mask = (hi_luma | hi_edge).astype(np.uint8)
    kernel = np.ones((5, 5), dtype=np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), dtype=np.uint8))
    return mask


def _compute_single_scale_continuity(
    ref_bgr: np.ndarray,
    frame_bgr: np.ndarray,
    grid_h: int = 8,
    grid_w: int = 6,
) -> dict[str, float]:
    tw, th = 180, 320
    a = cv2.resize(ref_bgr, (tw, th), interpolation=cv2.INTER_AREA)
    b = cv2.resize(frame_bgr, (tw, th), interpolation=cv2.INTER_AREA)

    # 1. 3D LAB palette probability-mass intersection (jointly captures brightness + chrominance
    # without desaturated [H=0, S=0] histogram-correlation inflation on porcelain scenes).
    lab_full_a = cv2.cvtColor(a, cv2.COLOR_BGR2LAB)
    lab_full_b = cv2.cvtColor(b, cv2.COLOR_BGR2LAB)
    ha = cv2.calcHist([lab_full_a], [0, 1, 2], None, [12, 10, 10], [0, 256, 64, 208, 64, 208]).flatten()
    hb = cv2.calcHist([lab_full_b], [0, 1, 2], None, [12, 10, 10], [0, 256, 64, 208, 64, 208]).flatten()
    ha = ha / max(1e-6, float(np.sum(ha)))
    hb = hb / max(1e-6, float(np.sum(hb)))
    pal_sim = float(max(0.0, min(1.0, float(np.sum(np.minimum(ha, hb))))))

    # 2. Per-channel spatial LAB grid correlation (never flatten interleaved [L, A+128, B+128]!)
    ga_grid = cv2.resize(lab_full_a.astype(np.float32), (grid_w, grid_h), interpolation=cv2.INTER_AREA)
    gb_grid = cv2.resize(lab_full_b.astype(np.float32), (grid_w, grid_h), interpolation=cv2.INTER_AREA)
    l_a, a_a, b_a = ga_grid[:, :, 0].ravel(), ga_grid[:, :, 1].ravel(), ga_grid[:, :, 2].ravel()
    l_b, a_b, b_b = gb_grid[:, :, 0].ravel(), gb_grid[:, :, 1].ravel(), gb_grid[:, :, 2].ravel()
    if float(np.std(l_a)) > 1.0 and float(np.std(l_b)) > 1.0:
        r_l = float(np.corrcoef(l_a, l_b)[0, 1])
        if np.isnan(r_l):
            r_l = 0.0
    else:
        r_l = 0.0
    prox_l = max(0.0, 1.0 - float(np.mean(np.abs(l_a - l_b))) / 85.0)
    prox_ab = max(0.0, 1.0 - 0.5 * float(np.mean(np.abs(a_a - a_b)) + np.mean(np.abs(b_a - b_b))) / 28.0)
    lab_grid_corr = float(max(0.0, min(1.0, 0.55 * max(0.0, r_l) + 0.25 * prox_l + 0.20 * prox_ab)))

    # 3. Spatial Canny edge density layout correlation (zero/negative correlation -> 0.0, not 0.50!)
    ga = cv2.cvtColor(a, cv2.COLOR_BGR2GRAY)
    gb = cv2.cvtColor(b, cv2.COLOR_BGR2GRAY)
    ea = cv2.resize(cv2.Canny(ga, 50, 140).astype(np.float32), (grid_w, grid_h), interpolation=cv2.INTER_AREA).ravel()
    eb = cv2.resize(cv2.Canny(gb, 50, 140).astype(np.float32), (grid_w, grid_h), interpolation=cv2.INTER_AREA).ravel()
    if float(np.std(ea)) > 1e-3 and float(np.std(eb)) > 1e-3:
        r_e = float(np.corrcoef(ea, eb)[0, 1])
        edge_grid_corr = float(max(0.0, min(1.0, 0.0 if np.isnan(r_e) else r_e)))
    else:
        edge_grid_corr = 0.0

    # 4. Foreground / salient structure IoU
    ma = _foreground_mask(a)
    mb = _foreground_mask(b)
    inter = float(np.sum((ma > 0) & (mb > 0)))
    union = float(np.sum((ma > 0) | (mb > 0)))
    fg_iou = inter / union if union > 10.0 else 0.5

    combined = 0.28 * pal_sim + 0.36 * lab_grid_corr + 0.16 * edge_grid_corr + 0.20 * fg_iou
    return {
        "combined_score": round(float(combined), 4),
        "hsv_corr": round(pal_sim, 4),
        "lab_grid_corr": round(lab_grid_corr, 4),
        "edge_grid_corr": round(edge_grid_corr, 4),
        "fg_iou": round(float(fg_iou), 4),
    }


def compute_spatial_and_palette_continuity(
    ref_bgr: np.ndarray,
    frame_bgr: np.ndarray,
    grid_h: int = 8,
    grid_w: int = 6,
    allow_interior_zoom: bool = False,
) -> dict[str, float]:
    """
    Combines 3D LAB palette intersection + per-channel spatial LAB grid correlation + Canny edge layout
    correlation + foreground/salient-structure IoU.
    When `allow_interior_zoom=True` (enabled only after verifying that the clip's opening/closing anchor
    genuinely matches the 1.0x reference image), also checks interior push-in crops (0.68x / 0.46x) so
    smooth macro camera push-ins are not confused with mid-clip scene morphing.
    """
    best = _compute_single_scale_continuity(ref_bgr, frame_bgr, grid_h=grid_h, grid_w=grid_w)
    if allow_interior_zoom and ref_bgr.shape[0] >= 120 and ref_bgr.shape[1] >= 80:
        rh, rw = ref_bgr.shape[:2]
        for scale, cy_frac in ((0.68, 0.46), (0.46, 0.42), (0.68, 0.54)):
            ch, cw = max(32, int(rh * scale)), max(32, int(rw * scale))
            y0 = max(0, min(rh - ch, int(rh * cy_frac - ch // 2)))
            x0 = max(0, (rw - cw) // 2)
            cand = _compute_single_scale_continuity(ref_bgr[y0 : y0 + ch, x0 : x0 + cw], frame_bgr, grid_h=grid_h, grid_w=grid_w)
            if cand["combined_score"] > best["combined_score"]:
                best = cand
    return best


def detect_r53_neon_particles(bgr: np.ndarray, is_brain_or_cutaway: bool = True) -> dict[str, Any]:
    """
    Detects R53 violations:
      1. Global neon green/cyan hue bleed (`36 <= H <= 132`, saturated bright pixels) in brain/cutaway clips.
      2. Localized small glowing green/cyan or pale-mint particle dots (`connectedComponentsWithStats` isolated
         blobs on either dark slate backdrops OR bright white porcelain brain tissue), catching floating particles
         even when global pixel ratio < 0.2%!
    """
    h_img, w_img = bgr.shape[:2]
    scale = min(1.0, 720.0 / max(h_img, w_img, 1))
    work = cv2.resize(bgr, (max(32, int(round(w_img * scale))), max(32, int(round(h_img * scale)))), interpolation=cv2.INTER_AREA) if scale < 1.0 else bgr
    wh, ww = work.shape[:2]
    total_px = float(max(1, wh * ww))

    hsv = cv2.cvtColor(work, cv2.COLOR_BGR2HSV)
    H, S, V = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]
    b_ch, g_ch, r_ch = [x.astype(np.float32) for x in cv2.split(work)]

    if is_brain_or_cutaway:
        neon_mask = ((H >= 36) & (H <= 132) & (S >= 48) & (V >= 100) & ((g_ch - r_ch) >= 8.0)).astype(np.uint8)
        sat_dot_cand = ((H >= 35) & (H <= 135) & (S >= 42) & (V >= 110) & ((g_ch - r_ch) >= 8.0))
        # Also catch pale mint-green floating dots over bright ivory/white porcelain (e.g. S=20..45, G > R + 10)
        g_excess = g_ch - np.maximum(r_ch, b_ch * 0.92)
        g_blur = cv2.GaussianBlur(g_excess, (17, 17), 0)
        mint_dot_cand = ((H >= 36) & (H <= 98) & (S >= 20) & (V >= 145) & ((g_ch - r_ch) >= 10.0) & ((g_excess - g_blur) >= 5.5))
        dot_cand = (sat_dot_cand | mint_dot_cand).astype(np.uint8)
        min_local_contrast = 12.0
    else:
        # In outdoor real_env shots, avoid flagging natural trees/sky; flag only intense glowing neon pinpoints
        neon_mask = ((H >= 42) & (H <= 102) & (S >= 150) & (V >= 185)).astype(np.uint8)
        dot_cand = neon_mask.copy()
        min_local_contrast = 32.0

    neon_ratio = float(np.sum(neon_mask > 0)) / total_px

    v_float = V.astype(np.float32)
    s_float = S.astype(np.float32)
    bg_blur_v = cv2.GaussianBlur(v_float, (21, 21), 0)
    bg_blur_s = cv2.GaussianBlur(s_float, (21, 21), 0)
    g_diff = g_ch - r_ch
    bg_blur_g = cv2.GaussianBlur(g_diff, (17, 17), 0)
    min_sat_contrast = 24.0 if is_brain_or_cutaway else 65.0

    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(dot_cand, connectivity=8)
    particle_dots = 0
    max_dot_area = max(140, int(total_px * 0.0014))
    for lbl in range(1, num_labels):
        area = int(stats[lbl, cv2.CC_STAT_AREA])
        bw = int(stats[lbl, cv2.CC_STAT_WIDTH])
        bh = int(stats[lbl, cv2.CC_STAT_HEIGHT])
        if 2 <= area <= max_dot_area and max(bw, bh) <= 32:
            aspect_blob = float(max(bw, bh)) / float(max(1, min(bw, bh)))
            if aspect_blob <= 4.0:
                comp_mask = labels == lbl
                contrast_v = float(np.mean(v_float[comp_mask]) - np.mean(bg_blur_v[comp_mask]))
                contrast_s = float(np.mean(s_float[comp_mask]) - np.mean(bg_blur_s[comp_mask]))
                contrast_g = float(np.mean(g_diff[comp_mask]) - np.mean(bg_blur_g[comp_mask]))
                if (
                    contrast_v >= min_local_contrast
                    or contrast_s >= min_sat_contrast
                    or (is_brain_or_cutaway and contrast_g >= 5.5)
                ):
                    particle_dots += 1

    return {
        "neon_green_cyan_ratio": round(neon_ratio, 6),
        "floating_particle_dots": int(particle_dots),
        "has_particle_bleed": bool(
            (is_brain_or_cutaway and neon_ratio > 0.0025)
            or particle_dots > 2
        ),
    }


def analyze_brain_anatomy_frame(bgr: np.ndarray) -> dict[str, Any]:
    """
    Segments the porcelain head/brain object and measures:
      - Head/brain bounding box & 64x64 silhouette + normalized luma template
      - Background border luminance (studio slate vs white gallery)
      - Coronal bilateral symmetry (`coronal_symmetry`, high >= 0.68 when front-facing two-eye coronal view)
      - Facing direction (`left`, `right`, or `frontal_coronal`) from smooth-forehead vs gyri-cutaway X-offset
      - True crimson lesion pixel ratio & normalized centroid `(cx, cy)` inside head bbox
      - Warm champagne-amber signal ratio & normalized centroid `(cx, cy)` inside head bbox
    """
    small = cv2.resize(bgr, (180, 320), interpolation=cv2.INTER_AREA)
    sh, sw = small.shape[:2]
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY).astype(np.float32)
    border = np.concatenate([gray[:8, :].ravel(), gray[-8:, :].ravel(), gray[:, :8].ravel(), gray[:, -8:].ravel()])
    bg_luma = float(np.median(border))

    fg = _foreground_mask(small)
    ys, xs = np.where(fg > 0)
    if len(xs) >= 80:
        x0, x1 = int(np.percentile(xs, 2)), int(np.percentile(xs, 98))
        y0, y1 = int(np.percentile(ys, 2)), int(np.percentile(ys, 98))
        x0, y0 = max(0, x0 - 4), max(0, y0 - 4)
        x1, y1 = min(sw - 1, x1 + 4), min(sh - 1, y1 + 4)
    else:
        x0, y0, x1, y1 = int(sw * 0.12), int(sh * 0.12), int(sw * 0.88), int(sh * 0.88)

    bw = max(16, x1 - x0)
    bh = max(16, y1 - y0)
    head_crop = small[y0:y1, x0:x1]
    head_gray = gray[y0:y1, x0:x1]

    sil_64 = cv2.resize(fg, (64, 64), interpolation=cv2.INTER_NEAREST)
    luma_64 = cv2.resize(gray, (64, 64), interpolation=cv2.INTER_AREA)

    # Coronal bilateral symmetry inside head bbox (upper 75% of head bbox where eyes/lobes sit)
    upper_gray = cv2.resize(head_gray[: max(8, int(bh * 0.78)), :], (64, 64), interpolation=cv2.INTER_AREA)
    flipped_upper = np.fliplr(upper_gray)
    if float(np.std(upper_gray)) > 2.0:
        coronal_sym = float(np.corrcoef(upper_gray.ravel(), flipped_upper.ravel())[0, 1])
    else:
        coronal_sym = 0.0

    hsv_head = cv2.cvtColor(head_crop, cv2.COLOR_BGR2HSV)
    Hh, Sh, Vh = hsv_head[:, :, 0], hsv_head[:, :, 1], hsv_head[:, :, 2]
    bh_c, gh_c, rh_c = [x.astype(np.int16) for x in cv2.split(head_crop)]

    # True crimson lesion requires pure red hue + strong R-over-G/B excess (never triggered by warm peach/champagne-amber)
    crimson_mask = (
        ((Hh <= 8) | (Hh >= 168))
        & (Sh >= 75)
        & (Vh >= 40)
        & ((rh_c - gh_c) >= 50)
        & ((rh_c - bh_c) >= 40)
    )
    amber_mask = ((Hh >= 9) & (Hh <= 35) & (Sh >= 32) & (Vh >= 90) & ~crimson_mask)

    head_area = float(max(1, bw * bh))
    crimson_ratio = float(np.sum(crimson_mask)) / head_area
    amber_ratio = float(np.sum(amber_mask)) / head_area

    crimson_centroid: list[float] | None = None
    if np.sum(crimson_mask) >= 6:
        cy_arr, cx_arr = np.where(crimson_mask)
        crimson_centroid = [round(float(np.mean(cx_arr)) / bw, 4), round(float(np.mean(cy_arr)) / bh, 4)]

    amber_centroid: list[float] | None = None
    if np.sum(amber_mask) >= 6:
        ay_arr, ax_arr = np.where(amber_mask)
        amber_centroid = [round(float(np.mean(ax_arr)) / bw, 4), round(float(np.mean(ay_arr)) / bh, 4)]

    # Facing direction invariant:
    # In a left-facing three-quarter porcelain bust (exposing the left hemisphere), the smooth bright-white
    # forehead sits anterior on viewer-left (`wx < ex`), while gyral cutaway edges sit posterior to its right (`ex > wx`).
    # In a right-facing bust, the smooth forehead sits on viewer-right (`wx > ex`).
    # In a symmetric coronal front-facing head, `coronal_sym >= 0.68` and `|ex - wx| < 0.09`.
    u0, u1 = int(bh * 0.08), max(int(bh * 0.08) + 8, int(bh * 0.55))
    upper_u8 = head_gray[u0:u1, :].astype(np.uint8)
    edges_upper = cv2.Canny(upper_u8, 45, 130)
    smooth_white = (upper_u8 >= 195) & (cv2.dilate(edges_upper, np.ones((3, 3), np.uint8)) == 0)
    xx_u = np.broadcast_to(np.arange(bw, dtype=np.float32)[None, :], upper_u8.shape)
    wx = float(xx_u[smooth_white].mean() / bw) if int(np.sum(smooth_white)) > 20 else 0.5
    ex = float(xx_u[edges_upper > 0].mean() / bw) if int(np.sum(edges_upper > 0)) > 20 else 0.5
    diff_ex_wx = ex - wx

    if coronal_sym >= 0.68 and abs(diff_ex_wx) < 0.09:
        facing = "frontal_coronal"
    elif diff_ex_wx >= 0.08:
        facing = "left"
    elif diff_ex_wx <= -0.08:
        facing = "right"
    else:
        facing = "ambiguous"

    return {
        "bg_luma": round(bg_luma, 2),
        "head_bbox_norm": [round(x0 / sw, 4), round(y0 / sh, 4), round(x1 / sw, 4), round(y1 / sh, 4)],
        "coronal_symmetry": round(coronal_sym, 4),
        "facing_direction": facing,
        "crimson_ratio": round(crimson_ratio, 5),
        "crimson_centroid_norm": crimson_centroid,
        "amber_ratio": round(amber_ratio, 5),
        "amber_centroid_norm": amber_centroid,
        "_sil_64": sil_64,
        "_luma_64": luma_64,
    }


def compute_camera_compensated_motion(all_frames: list[np.ndarray], fps: float) -> dict[str, Any]:
    """
    Separates global 2D camera pan/zoom from articulated subject/prop residual motion across 4 temporal windows,
    measures Beat-1 (15%) vs Beat-2 (80%) composition progression, and detects stitched intra-clip hard jump cuts.
    """
    n = len(all_frames)
    if n < 6:
        return {
            "raw_flow_mean": 0.0,
            "residual_subject_flow_p90": 0.0,
            "active_window_ratio": 0.0,
            "beat1_vs_beat2_shift": 0.0,
            "max_frame_step_diff": 0.0,
            "median_frame_step_diff": 0.0,
            "has_hard_jump_cut": False,
        }

    # Intra-clip hard jump-cut check across consecutive frames (catches stitched two-shot clips while allowing flashes)
    tiny_grays = [
        cv2.cvtColor(cv2.resize(frm, (90, 160), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY).astype(np.float32)
        for frm in all_frames
    ]
    step_diffs = [float(np.mean(np.abs(tiny_grays[k] - tiny_grays[k - 1]))) for k in range(1, n)]
    k_max = int(np.argmax(step_diffs)) + 1 if step_diffs else 1
    max_step_diff = step_diffs[k_max - 1] if step_diffs else 0.0
    med_step_diff = float(np.median(step_diffs)) if step_diffs else 0.0
    cross_cut_diff = float(
        np.mean(np.abs(tiny_grays[min(n - 1, k_max + 2)] - tiny_grays[max(0, k_max - 3)]))
    )
    has_hard_jump_cut = bool(
        n >= 16
        and max_step_diff >= 30.0
        and cross_cut_diff >= 28.0
        and max_step_diff >= max(med_step_diff * 2.5, 30.0)
    )

    step = max(2, int(round(max(fps, 12.0) * 0.35)))
    anchors = [0.12, 0.35, 0.58, 0.80]
    raw_means: list[float] = []
    res_p90s: list[float] = []
    active_wins = 0

    for a in anchors:
        i0 = min(n - 2, max(0, int(round(a * (n - 1)))))
        i1 = min(n - 1, i0 + step)
        if i1 <= i0:
            continue
        s0 = cv2.resize(all_frames[i0], (180, 320), interpolation=cv2.INTER_AREA)
        s1 = cv2.resize(all_frames[i1], (180, 320), interpolation=cv2.INTER_AREA)
        g0 = cv2.cvtColor(s0, cv2.COLOR_BGR2GRAY)
        g1 = cv2.cvtColor(s1, cv2.COLOR_BGR2GRAY)

        flow = cv2.calcOpticalFlowFarneback(g0, g1, None, 0.5, 3, 15, 3, 5, 1.2, 0)
        fx, fy = flow[..., 0], flow[..., 1]
        raw_mag = np.sqrt(fx * fx + fy * fy)
        raw_means.append(float(np.mean(raw_mag)))

        # Fit affine global camera field (pan + zoom + rotation) across a 2D coordinate grid
        yy, xx = np.mgrid[0:g0.shape[0], 0:g0.shape[1]].astype(np.float32)
        design = np.column_stack([xx.ravel(), yy.ravel(), np.ones(xx.size, dtype=np.float32)])
        coef_x, _, _, _ = np.linalg.lstsq(design, fx.ravel(), rcond=None)
        coef_y, _, _, _ = np.linalg.lstsq(design, fy.ravel(), rcond=None)
        cam_fx = (design @ coef_x).reshape(fx.shape)
        cam_fy = (design @ coef_y).reshape(fy.shape)

        res_mag = np.sqrt((fx - cam_fx) ** 2 + (fy - cam_fy) ** 2)
        fg_union = (_foreground_mask(s0) > 0) | (_foreground_mask(s1) > 0)
        fg_p90 = float(np.percentile(res_mag[fg_union], 90)) if int(np.sum(fg_union)) >= 120 else 0.0
        full_p98 = float(np.percentile(res_mag, 98))
        p90 = max(fg_p90, full_p98)
        res_p90s.append(p90)
        if p90 >= 0.45 or float(np.mean(raw_mag)) >= 0.55:
            active_wins += 1

    f_early = all_frames[min(n - 1, int(round(0.15 * (n - 1))))]
    f_late = all_frames[min(n - 1, int(round(0.82 * (n - 1))))]
    early_late_cont = compute_spatial_and_palette_continuity(f_early, f_late)
    beat_shift = round(max(0.0, 1.0 - early_late_cont["lab_grid_corr"]), 4)

    return {
        "raw_flow_mean": round(float(np.mean(raw_means)) if raw_means else 0.0, 4),
        "residual_subject_flow_p90": round(float(np.mean(res_p90s)) if res_p90s else 0.0, 4),
        "active_window_ratio": round(float(active_wins) / float(max(1, len(res_p90s))), 4),
        "beat1_vs_beat2_shift": beat_shift,
        "max_frame_step_diff": round(max_step_diff, 3),
        "median_frame_step_diff": round(med_step_diff, 3),
        "has_hard_jump_cut": has_hard_jump_cut,
    }


def count_porcelain_upper_figures(bgr: np.ndarray) -> int:
    """
    Counts horizontally distinct bright matte-white porcelain head/shoulder figures in the upper standing
    band (`y = 24%..52%`), avoiding lower-table skull specimens and 3D CT scans inside dark display monitors
    while catching cloned side/background researchers.
    """
    small = cv2.resize(bgr, (180, 320), interpolation=cv2.INTER_AREA)
    full_hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)
    hsv = full_hsv[76:166, :]
    mask = ((hsv[:, :, 1] <= 36) & (hsv[:, :, 2] >= 175)).astype(np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))
    n_lbl, _, stats, cents = cv2.connectedComponentsWithStats(mask, connectivity=8)
    xs: list[float] = []
    for i in range(1, n_lbl):
        area = int(stats[i, cv2.CC_STAT_AREA])
        bh = int(stats[i, cv2.CC_STAT_HEIGHT])
        bw = int(stats[i, cv2.CC_STAT_WIDTH])
        if area >= 220 and bh >= 24 and bw <= 115:
            bx = int(stats[i, cv2.CC_STAT_LEFT])
            by = int(stats[i, cv2.CC_STAT_TOP])
            y0, y1 = max(0, 76 + by - 12), min(320, 76 + by + bh + 12)
            x0, x1 = max(0, bx - 10), min(180, bx + bw + 10)
            patch = full_hsv[y0:y1, x0:x1]
            amber_r = float(
                np.mean((patch[:, :, 0] >= 10) & (patch[:, :, 0] <= 34) & (patch[:, :, 1] >= 65) & (patch[:, :, 2] >= 120))
            )
            dark_r = float(np.mean(patch[:, :, 2] <= 58))
            if dark_r >= 0.18 and amber_r >= 0.015:
                continue  # 3D bone-white CT skull + amber tractography inside a dark display monitor bezel
            cx = float(cents[i][0])
            if all(abs(cx - prev_x) >= 32.0 for prev_x in xs):
                xs.append(cx)
    return len(xs)


def detect_forbidden_scene_hallucinations(
    sampled_frames: list[tuple[float, np.ndarray]],
    forbidden_elements: list[str],
    is_brain_clip: bool = False,
    require_porcelain_presence: bool = False,
) -> list[str]:
    """Detects concrete scene-specific hallucinations (human flesh/fur drift, lost porcelain cast, curtains, cloned figures)."""
    violations: list[str] = []
    if not sampled_frames:
        return violations

    if (not is_brain_clip) and "real_human_face_or_skin" in forbidden_elements:
        skin_logged = False
        porc_logged = False
        for pct, frm in sampled_frames:
            hsv = cv2.cvtColor(frm, cv2.COLOR_BGR2HSV)
            fh, fw = hsv.shape[:2]
            head_hsv = hsv[int(fh * 0.15) : int(fh * 0.48), int(fw * 0.28) : int(fw * 0.72)]
            skin_mask = (
                (head_hsv[:, :, 0] >= 6)
                & (head_hsv[:, :, 0] <= 16)
                & (head_hsv[:, :, 1] >= 68)
                & (head_hsv[:, :, 1] <= 145)
                & (head_hsv[:, :, 2] >= 95)
                & (head_hsv[:, :, 2] <= 210)
            )
            skin_ratio = float(np.mean(skin_mask)) if head_hsv.size > 0 else 0.0
            if not skin_logged and skin_ratio > REF_IMAGE_HUMAN_SKIN_MAX:
                violations.append(
                    f"forbidden_real_human_face_or_skin@{int(round(pct * 100))}pct(skin_ratio={skin_ratio:.3f}>{REF_IMAGE_HUMAN_SKIN_MAX:.2f})"
                )
                skin_logged = True
            if require_porcelain_presence and not porc_logged:
                center_hsv = hsv[int(fh * 0.18) : int(fh * 0.82), int(fw * 0.15) : int(fw * 0.85)]
                porc_mask = (center_hsv[:, :, 1] <= 55) & (center_hsv[:, :, 2] >= 150)
                porc_ratio = float(np.mean(porc_mask)) if center_hsv.size > 0 else 0.0
                if porc_ratio < REF_IMAGE_PORCELAIN_RATIO_MIN:
                    violations.append(
                        f"porcelain_cast_lost_or_cropped_out@{int(round(pct * 100))}pct(porcelain_ratio={porc_ratio:.3f}<{REF_IMAGE_PORCELAIN_RATIO_MIN:.2f})"
                    )
                    porc_logged = True

    if "indoor_red_curtains_or_giant_golden_disc" in forbidden_elements:
        for pct, frm in sampled_frames:
            small = cv2.resize(frm, (180, 320), interpolation=cv2.INTER_AREA)
            hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)
            H, S, V = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]
            # Red curtains along left/right upper side borders
            upper = slice(0, 210)
            sides_h = np.concatenate([H[upper, :36].ravel(), H[upper, -36:].ravel()])
            sides_s = np.concatenate([S[upper, :36].ravel(), S[upper, -36:].ravel()])
            sides_v = np.concatenate([V[upper, :36].ravel(), V[upper, -36:].ravel()])
            red_curtain_ratio = float(np.mean(((sides_h <= 12) | (sides_h >= 166)) & (sides_s >= 75) & (sides_v >= 45)))
            # Giant golden disc in center
            mid = hsv[70:250, 35:145]
            gold_center_ratio = float(np.mean((mid[:, :, 0] >= 14) & (mid[:, :, 0] <= 32) & (mid[:, :, 1] >= 95) & (mid[:, :, 2] >= 120)))
            if red_curtain_ratio >= 0.14 or (red_curtain_ratio >= 0.07 and gold_center_ratio >= 0.16):
                violations.append(
                    f"forbidden_indoor_red_curtains_or_golden_disc@{int(pct*100)}pct(red_side={red_curtain_ratio:.2f},gold_mid={gold_center_ratio:.2f})"
                )
                break

    if "cloned_duplicate_background_mannequins" in forbidden_elements:
        for pct, frm in sampled_frames:
            n_figs = count_porcelain_upper_figures(frm)
            if n_figs >= 2:
                violations.append(f"forbidden_cloned_duplicate_mannequins@{int(pct*100)}pct(upper_figures={n_figs})")
                break

    return violations


def _render_clip_contact_strip(
    clip_num: int,
    role: str,
    ref_bgr: np.ndarray | None,
    sampled_frames: list[tuple[float, np.ndarray]],
    passed: bool,
    min_cont: float,
    max_dots: int,
    out_path: Path,
) -> None:
    tile_w, tile_h = 180, 320
    panels: list[tuple[str, np.ndarray]] = []
    if ref_bgr is not None and ref_bgr.size > 0:
        panels.append(("REF", cv2.resize(ref_bgr, (tile_w, tile_h), interpolation=cv2.INTER_AREA)))
    else:
        blank = np.full((tile_h, tile_w, 3), 36, dtype=np.uint8)
        cv2.putText(blank, "NO REF", (32, 160), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (90, 90, 230), 2)
        panels.append(("REF", blank))

    for pct, frm in sampled_frames:
        panels.append((f"{int(round(pct * 100))}%", cv2.resize(frm, (tile_w, tile_h), interpolation=cv2.INTER_AREA)))

    canvas = np.full((tile_h + 52, tile_w * len(panels), 3), 20, dtype=np.uint8)
    hdr_color = (70, 210, 90) if passed else (70, 70, 235)
    status_txt = "PASS" if passed else "FAIL"
    cv2.putText(
        canvas,
        f"Clip {clip_num:02d} ({role}) [{status_txt}] min_cont={min_cont:.2f} green_dots={max_dots}",
        (10, 24),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        hdr_color,
        2,
    )
    for i, (lbl, tile) in enumerate(panels):
        x0 = i * tile_w
        canvas[44: 44 + tile_h, x0: x0 + tile_w] = tile
        cv2.putText(canvas, lbl, (x0 + 8, 66), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (240, 240, 240), 2)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out_path), canvas)


# ==============================================================================
# Structured Anti-Boilerplate Per-Clip Semantic Verification
# ==============================================================================

CLIP_SEMANTIC_CHECKS: tuple[str, ...] = (
    "required_entities_visible",
    "narration_action_grounded",
    "zero_forbidden_hallucinations",
    "continuity_and_anatomy_verified",
)


def write_clip_semantic_review_template(
    project_dir: Path,
    contract: dict[str, Any] | None = None,
) -> Path:
    """
    Writes/updates `03_visuals/clip_semantic_review.json` binding each clip's structured semantic
    checklist to current on-disk `clip_N.mp4` and `ref_clip_NN.png` SHA-256 digests.
    """
    p_dir = Path(project_dir)
    vis_dir = p_dir / "03_visuals"
    ref_dir = vis_dir / REF_IMAGES_DIRNAME
    clips_dir = vis_dir / "flow_native_clips"
    vis_dir.mkdir(parents=True, exist_ok=True)
    sem_path = vis_dir / CLIP_SEMANTIC_REVIEW_FILENAME

    if contract is None:
        c_file = vis_dir / CLIP_QA_CONTRACT_FILENAME
        contract = json.loads(c_file.read_text(encoding="utf-8")) if c_file.exists() else compile_clip_qa_contract(p_dir, save=True)

    existing_clips: dict[str, Any] = {}
    if sem_path.exists():
        try:
            existing_clips = dict((json.loads(sem_path.read_text(encoding="utf-8")).get("clips") or {}))
        except Exception:
            existing_clips = {}

    entries: dict[str, Any] = {}
    for c_spec in contract.get("clips") or []:
        c_num = int(c_spec["clip_number"])
        key = f"clip_{c_num:02d}"
        primary_ref_id = str((c_spec.get("conditioning_contract") or {}).get("primary_ref_id") or f"ref_clip_{c_num:02d}")
        ref_p = ref_dir / f"{primary_ref_id}.png"
        mp4_p = clips_dir / f"clip_{c_num}.mp4"
        cur_clip_sha = compute_sha256(mp4_p) if mp4_p.exists() else None
        cur_ref_sha = compute_sha256(ref_p) if ref_p.exists() else None

        prev = existing_clips.get(key) if isinstance(existing_clips.get(key), dict) else {}
        same_hashes = (
            cur_clip_sha is not None
            and prev.get("clip_sha256") == cur_clip_sha
            and prev.get("primary_ref_sha256") == cur_ref_sha
        )
        checks = {
            chk: (prev.get("checks", {}).get(chk) if same_hashes and chk in (prev.get("checks") or {}) else None)
            for chk in CLIP_SEMANTIC_CHECKS
        }
        entries[key] = {
            "clip_number": c_num,
            "role": c_spec.get("role"),
            "clip_sha256": cur_clip_sha,
            "primary_ref_id": primary_ref_id,
            "primary_ref_sha256": cur_ref_sha,
            "required_entities": list(c_spec.get("required_entities") or []),
            "forbidden_elements": list(c_spec.get("forbidden_elements") or []),
            "checks": checks,
            "note": str(prev.get("note") or "") if same_hashes else "",
        }

    payload = {
        "schema_version": 1,
        "project_id": p_dir.name,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "clips": entries,
    }
    sem_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return sem_path


def validate_clip_semantic_review(
    project_dir: Path,
    contract: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Validates `03_visuals/clip_semantic_review.json` with:
      1. Cryptographic SHA-256 binding to `clip_N.mp4` and `ref_clip_NN.png` (any replaced file invalidates review).
      2. Structured checklist enforcement across `CLIP_SEMANTIC_CHECKS`.
      3. Anti-boilerplate copy-paste note detection (identical note repeated across >= 4 clips is rejected).
    """
    p_dir = Path(project_dir)
    vis_dir = p_dir / "03_visuals"
    ref_dir = vis_dir / REF_IMAGES_DIRNAME
    clips_dir = vis_dir / "flow_native_clips"
    sem_path = vis_dir / CLIP_SEMANTIC_REVIEW_FILENAME

    if contract is None:
        c_file = vis_dir / CLIP_QA_CONTRACT_FILENAME
        contract = json.loads(c_file.read_text(encoding="utf-8")) if c_file.exists() else compile_clip_qa_contract(p_dir, save=False)

    clip_specs = list(contract.get("clips") or [])
    if not sem_path.exists():
        return {
            "exists": False,
            "complete": False,
            "passed_clips": [],
            "failed_clips": [],
            "pending_clips": [int(c["clip_number"]) for c in clip_specs],
            "stale_sha256_clips": [],
            "boilerplate_note_clips": [],
        }

    try:
        raw = json.loads(sem_path.read_text(encoding="utf-8"))
        entries = dict(raw.get("clips") or {})
    except Exception:
        return {
            "exists": True,
            "complete": False,
            "passed_clips": [],
            "failed_clips": [int(c["clip_number"]) for c in clip_specs],
            "pending_clips": [],
            "stale_sha256_clips": [],
            "boilerplate_note_clips": [],
        }

    passed_clips: list[int] = []
    failed_clips: list[int] = []
    pending_clips: list[int] = []
    stale_clips: list[int] = []
    note_buckets: dict[str, list[int]] = {}

    for c_spec in clip_specs:
        c_num = int(c_spec["clip_number"])
        key = f"clip_{c_num:02d}"
        ent = entries.get(key)
        if not isinstance(ent, dict):
            pending_clips.append(c_num)
            continue

        primary_ref_id = str((c_spec.get("conditioning_contract") or {}).get("primary_ref_id") or f"ref_clip_{c_num:02d}")
        ref_p = ref_dir / f"{primary_ref_id}.png"
        mp4_p = clips_dir / f"clip_{c_num}.mp4"
        cur_clip_sha = compute_sha256(mp4_p) if mp4_p.exists() else None
        cur_ref_sha = compute_sha256(ref_p) if ref_p.exists() else None

        if cur_clip_sha is None or ent.get("clip_sha256") != cur_clip_sha or ent.get("primary_ref_sha256") != cur_ref_sha:
            stale_clips.append(c_num)
            pending_clips.append(c_num)
            continue

        checks = ent.get("checks") if isinstance(ent.get("checks"), dict) else {}
        vals = [checks.get(chk) for chk in CLIP_SEMANTIC_CHECKS]
        note_norm = re.sub(r"\s+", " ", str(ent.get("note") or "").strip().lower())
        if any(v is False for v in vals):
            failed_clips.append(c_num)
        elif all(v is True for v in vals):
            if len(note_norm) < 12:
                failed_clips.append(c_num)
            else:
                passed_clips.append(c_num)
                note_buckets.setdefault(note_norm, []).append(c_num)
        else:
            pending_clips.append(c_num)

    boilerplate_clips: list[int] = []
    if len(clip_specs) >= 4:
        for _, c_nums in note_buckets.items():
            if len(c_nums) >= 4:
                boilerplate_clips.extend(c_nums)
    if boilerplate_clips:
        for cn in boilerplate_clips:
            if cn in passed_clips:
                passed_clips.remove(cn)
            if cn not in failed_clips:
                failed_clips.append(cn)

    complete = len(pending_clips) == 0 and len(passed_clips) + len(failed_clips) == len(clip_specs)
    return {
        "exists": True,
        "complete": complete,
        "passed_clips": sorted(passed_clips),
        "failed_clips": sorted(set(failed_clips)),
        "pending_clips": sorted(set(pending_clips)),
        "stale_sha256_clips": sorted(set(stale_clips)),
        "boilerplate_note_clips": sorted(set(boilerplate_clips)),
    }


# ==============================================================================
# Post-Generation Per-Clip & Cross-Clip Verification Engine
# ==============================================================================

def verify_clips_against_contract(
    project_dir: Path,
    contract: dict[str, Any] | None = None,
    save_report: bool = True,
    render_strips: bool = True,
    require_reference_pack: bool = False,
    require_semantic_review: bool = False,
) -> dict[str, Any]:
    """
    Verifies rendered `ref_*.png`, `clip_*.mp4`, and optional `final_shorts_1080x1920.mp4`
    against the per-video `clip_qa_contract.json`, binding SHA-256 digests of every inspected file.
    """
    p_dir = Path(project_dir)
    vis_dir = p_dir / "03_visuals"
    ref_dir = vis_dir / REF_IMAGES_DIRNAME
    clips_dir = vis_dir / "flow_native_clips"
    strips_dir = vis_dir / CLIP_QA_STRIPS_DIRNAME
    contract_path = vis_dir / CLIP_QA_CONTRACT_FILENAME

    if contract is None:
        if contract_path.exists():
            contract = json.loads(contract_path.read_text(encoding="utf-8"))
        else:
            contract = compile_clip_qa_contract(p_dir, save=save_report)

    contract_sha = compute_sha256(contract_path) if contract_path.exists() else hashlib.sha256(
        json.dumps(contract, sort_keys=True).encode("utf-8")
    ).hexdigest()

    ref_sha_map: dict[str, str] = {}
    if ref_dir.exists():
        for rf in sorted(ref_dir.glob("*.png")):
            if rf.is_file():
                ref_sha_map[rf.name] = compute_sha256(rf)

    clip_sha_map: dict[str, str] = {}
    if clips_dir.exists():
        for cf in sorted(clips_dir.glob("clip_*.mp4")):
            if cf.is_file():
                clip_sha_map[cf.name] = compute_sha256(cf)

    final_mp4 = p_dir / "05_assembly" / "final_shorts_1080x1920.mp4"
    final_mp4_sha = compute_sha256(final_mp4) if final_mp4.exists() else None

    sem_path = vis_dir / CLIP_SEMANTIC_REVIEW_FILENAME
    sem_sha = compute_sha256(sem_path) if sem_path.exists() else None
    semantic_summary = validate_clip_semantic_review(p_dir, contract=contract)

    brain_master_bgr: np.ndarray | None = None
    master_ref_path = ref_dir / "ref_brain_master.png"
    if master_ref_path.exists():
        brain_master_bgr = cv2.imread(str(master_ref_path))

    has_clip_ref_pack = require_reference_pack or any(k.startswith("ref_clip_") for k in ref_sha_map)

    per_clip_results: list[dict[str, Any]] = []
    brain_clip_features: dict[int, dict[str, Any]] = {}
    regenerate_clips: list[int] = []

    for c_spec in contract.get("clips") or []:
        c_num = int(c_spec["clip_number"])
        role = str(c_spec["role"])
        is_brain = bool(c_spec.get("is_brain_clip"))
        cond_spec = c_spec.get("conditioning_contract") or {}
        anat_spec = c_spec.get("anatomical_contract")
        mot_spec = c_spec.get("motion_contract") or {}
        forb_elems = list(c_spec.get("forbidden_elements") or [])
        req_entities = list(c_spec.get("required_entities") or [])
        grounding_spec = dict(c_spec.get("narration_grounding") or {})

        primary_ref_id = str(cond_spec.get("primary_ref_id") or f"ref_clip_{c_num:02d}")
        ref_path = ref_dir / f"{primary_ref_id}.png"
        direct_ref_bgr = cv2.imread(str(ref_path)) if ref_path.exists() else None
        ref_bgr = direct_ref_bgr
        if ref_bgr is None and is_brain and brain_master_bgr is not None:
            ref_bgr = brain_master_bgr

        mp4_path = clips_dir / f"clip_{c_num}.mp4"
        issues: list[str] = []
        ref_qa_info: dict[str, Any] = {"primary_ref_id": primary_ref_id, "exists": direct_ref_bgr is not None, "issues": []}

        # 0. Inspect rendered reference PNG(s) against contract before/alongside clip inspection
        if direct_ref_bgr is not None and direct_ref_bgr.size > 0:
            rh, rw = direct_ref_bgr.shape[:2]
            r_ratio = float(rw) / float(max(1, rh))
            if contract.get("aspect", "9:16") == "9:16" and (rw >= rh or abs(r_ratio - (9.0 / 16.0)) > 0.04):
                ref_qa_info["issues"].append(f"ref_invalid_aspect_ratio: {rw}x{rh}")
            ref_part = detect_r53_neon_particles(direct_ref_bgr, is_brain_or_cutaway=is_brain)
            if ref_part["has_particle_bleed"]:
                ref_qa_info["issues"].append(
                    f"ref_r53_green_cyan_particle_bleed: dots={ref_part['floating_particle_dots']}, ratio={ref_part['neon_green_cyan_ratio']:.5f}"
                )
            has_cast_entity = any(str(e).startswith("cast (") for e in req_entities)
            ref_forb = detect_forbidden_scene_hallucinations(
                [(0.0, direct_ref_bgr)],
                forb_elems,
                is_brain_clip=is_brain,
                require_porcelain_presence=has_cast_entity,
            )
            ref_qa_info["issues"].extend(f"ref_{fh}" for fh in ref_forb)
            if is_brain and anat_spec:
                ref_anat = analyze_brain_anatomy_frame(direct_ref_bgr)
                if anat_spec.get("forbid_symmetric_coronal") and (
                    ref_anat["facing_direction"] == "frontal_coronal" or float(ref_anat["coronal_symmetry"]) >= 0.68
                ):
                    ref_qa_info["issues"].append(
                        f"ref_anatomical_coronal_view_violation: symmetry={ref_anat['coronal_symmetry']:.3f}"
                    )
                exp_f_ref = anat_spec.get("expected_facing", "any")
                if exp_f_ref in ("left", "right"):
                    wrong_f_ref = "right" if exp_f_ref == "left" else "left"
                    if ref_anat["facing_direction"] == wrong_f_ref:
                        ref_qa_info["issues"].append(
                            f"ref_anatomical_wrong_hemisphere_facing: detected={wrong_f_ref}, expected={exp_f_ref}"
                        )
            issues.extend(ref_qa_info["issues"])
        elif has_clip_ref_pack and mp4_path.exists():
            miss_msg = f"missing_reference_image: {ref_path.name}"
            ref_qa_info["issues"].append(miss_msg)
            issues.append(miss_msg)

        if not mp4_path.exists() or mp4_path.stat().st_size < MIN_CLIP_SIZE_BYTES:
            issues.append(f"missing_or_undersized_clip: {mp4_path.name}")
            per_clip_results.append(
                {
                    "clip_number": c_num,
                    "role": role,
                    "is_brain_clip": is_brain,
                    "required_entities": req_entities,
                    "forbidden_elements": forb_elems,
                    "narration_grounding": grounding_spec,
                    "reference_qa": ref_qa_info,
                    "exists": mp4_path.exists(),
                    "passed": False,
                    "issues": issues,
                }
            )
            regenerate_clips.append(c_num)
            continue

        meta, sampled = sample_video_frames_5pt(mp4_path, SAMPLE_WINDOWS_5PT)
        all_frames = meta.pop("_all_frames", [])
        if not meta["readable"] or not sampled:
            issues.append("unreadable_video_stream")
            per_clip_results.append(
                {
                    "clip_number": c_num,
                    "role": role,
                    "is_brain_clip": is_brain,
                    "required_entities": req_entities,
                    "forbidden_elements": forb_elems,
                    "narration_grounding": grounding_spec,
                    "reference_qa": ref_qa_info,
                    "exists": True,
                    "passed": False,
                    "issues": issues,
                }
            )
            regenerate_clips.append(c_num)
            continue

        # 1. Native 9:16 vertical aspect check
        w, h = int(meta["width"]), int(meta["height"])
        ratio = float(w) / float(max(1, h))
        if contract.get("aspect", "9:16") == "9:16" and (w >= h or abs(ratio - (9.0 / 16.0)) > 0.04):
            issues.append(f"invalid_aspect_ratio: {w}x{h} (expected 9:16 vertical)")

        # 2. 5-point Reference-to-Clip Continuity ([0%, 25%, 50%, 75%, 95%])
        win_scores: list[dict[str, Any]] = []
        if ref_bgr is not None and ref_bgr.size > 0:
            start_1x = compute_spatial_and_palette_continuity(ref_bgr, sampled[0][1], allow_interior_zoom=False)
            end_1x = compute_spatial_and_palette_continuity(ref_bgr, sampled[-1][1], allow_interior_zoom=False)
            allow_zoom = bool(start_1x["combined_score"] >= 0.78 or end_1x["combined_score"] >= 0.78)

            for pct, frm in sampled:
                sc = compute_spatial_and_palette_continuity(ref_bgr, frm, allow_interior_zoom=allow_zoom)
                win_scores.append({"window_pct": pct, **sc})
            agg_mode = str(cond_spec.get("aggregation_mode") or "strict_min_5pt")
            min_req = float(cond_spec.get("min_continuity_score", 0.48))
            max_drop = float(cond_spec.get("max_late_morph_drop", 0.32))

            all_comb = [x["combined_score"] for x in win_scores]
            min_5pt = float(min(all_comb))
            max_5pt = float(max(all_comb))
            min_hsv = float(min(x["hsv_corr"] for x in win_scores))
            late_drop = round(all_comb[0] - min(all_comb[-2:]), 4) if len(all_comb) >= 3 else 0.0
            adj_scores = [
                compute_spatial_and_palette_continuity(sampled[k][1], sampled[k + 1][1], allow_interior_zoom=False)["combined_score"]
                for k in range(len(sampled) - 1)
            ]
            min_adj = float(min(adj_scores)) if adj_scores else 1.0
            is_smooth_macro_zoom = bool(
                is_brain
                and start_1x["combined_score"] >= 0.82
                and min_5pt >= 0.48
                and (min_adj >= 0.46 or end_1x["combined_score"] >= 0.80)
            )
            is_smooth_real_camera_pan = bool(
                (not is_brain)
                and start_1x["combined_score"] >= 0.80
                and min_hsv >= 0.60
                and min_adj >= 0.52
                and min_5pt >= 0.44
            )

            if agg_mode == "pullback_windowed":
                anchor_match = max(min(all_comb[:2]), min(all_comb[-2:]))
                if not is_smooth_macro_zoom and (anchor_match < min_req or min_hsv < 0.42):
                    issues.append(
                        f"pullback_ref_continuity_failed: anchor_match={anchor_match:.3f}<{min_req:.2f}, min_hsv={min_hsv:.3f}"
                    )
            elif not is_smooth_macro_zoom and not is_smooth_real_camera_pan:
                if min_5pt < min_req:
                    issues.append(f"5pt_ref_continuity_low: min_score={min_5pt:.3f}<{min_req:.2f}")
                if late_drop > max_drop:
                    issues.append(f"late_clip_morph_detected: start_to_late_drop={late_drop:.3f}>{max_drop:.2f}")

            # Also verify any secondary key/end reference frames in `must_match_ref_ids` when present on disk
            for extra_ref_id in cond_spec.get("must_match_ref_ids") or []:
                if extra_ref_id == primary_ref_id:
                    continue
                extra_p = ref_dir / f"{extra_ref_id}.png"
                if extra_p.exists():
                    extra_bgr = cv2.imread(str(extra_p))
                    if extra_bgr is not None and extra_bgr.size > 0:
                        extra_scores = [
                            compute_spatial_and_palette_continuity(extra_bgr, frm, allow_interior_zoom=True)["combined_score"]
                            for _, frm in sampled
                        ]
                        if extra_ref_id.endswith("_key"):
                            best_key = max(extra_scores[1:]) if len(extra_scores) > 1 else extra_scores[0]
                            if best_key < 0.44:
                                issues.append(f"key_ref_continuity_low({extra_ref_id}): max_score={best_key:.3f}<0.44")
                        elif extra_ref_id.endswith("_end"):
                            end_match = min(extra_scores[-2:]) if len(extra_scores) >= 2 else extra_scores[-1]
                            if end_match < 0.44:
                                issues.append(f"end_ref_continuity_low({extra_ref_id}): end_score={end_match:.3f}<0.44")
        else:
            min_5pt = 0.0
            max_5pt = 0.0
            late_drop = 0.0
            if is_brain and len(sampled) >= 4:
                self_scores = [compute_spatial_and_palette_continuity(sampled[0][1], frm)["combined_score"] for _, frm in sampled[1:]]
                min_5pt = float(min(self_scores))
                if min_5pt < 0.48:
                    issues.append(f"intra_clip_brain_morph_without_ref: min_self_cont={min_5pt:.3f}<0.48")

        # 3. R53 Neon Green/Cyan Particle Bleed Check across all 5 sampled windows
        part_reports = [detect_r53_neon_particles(frm, is_brain_or_cutaway=is_brain) for _, frm in sampled]
        max_neon_ratio = max(p["neon_green_cyan_ratio"] for p in part_reports)
        max_dots = max(p["floating_particle_dots"] for p in part_reports)
        if any(p["has_particle_bleed"] for p in part_reports):
            issues.append(f"r53_green_cyan_particle_bleed: max_dots={max_dots}, max_neon_ratio={max_neon_ratio:.5f}")

        # 4. Anatomical ROI & View Lock (for brain clips)
        anat_measured: dict[str, Any] | None = None
        if is_brain and anat_spec:
            anat_frames = [analyze_brain_anatomy_frame(frm) for _, frm in sampled]
            wide_anat = min(
                anat_frames,
                key=lambda a: float(a["bg_luma"]) + 80.0 * float(a["head_bbox_norm"][2] - a["head_bbox_norm"][0]),
            )
            brain_clip_features[c_num] = wide_anat
            wide_candidates = [
                a for a in anat_frames if (float(a["head_bbox_norm"][2]) - float(a["head_bbox_norm"][0])) < 0.96
            ] or [wide_anat]

            max_coronal_sym = max(a["coronal_symmetry"] for a in wide_candidates)
            facings = [a["facing_direction"] for a in wide_candidates]
            max_crimson = max(a["crimson_ratio"] for a in anat_frames)
            crimson_pts = (
                [a["crimson_centroid_norm"] for a in wide_candidates if a["crimson_centroid_norm"] is not None]
                or [a["crimson_centroid_norm"] for a in anat_frames if a["crimson_centroid_norm"] is not None]
            )
            amber_pts = (
                [a["amber_centroid_norm"] for a in wide_candidates if a["amber_centroid_norm"] is not None]
                or [a["amber_centroid_norm"] for a in anat_frames if a["amber_centroid_norm"] is not None]
            )

            mean_crimson_c = (
                [round(float(np.mean([p[0] for p in crimson_pts])), 4), round(float(np.mean([p[1] for p in crimson_pts])), 4)]
                if crimson_pts else None
            )
            mean_amber_c = (
                [round(float(np.mean([p[0] for p in amber_pts])), 4), round(float(np.mean([p[1] for p in amber_pts])), 4)]
                if amber_pts else None
            )

            if anat_spec.get("forbid_symmetric_coronal") and (
                "frontal_coronal" in facings or max_coronal_sym >= 0.68
            ):
                issues.append(f"anatomical_coronal_view_violation: max_coronal_symmetry={max_coronal_sym:.3f}")

            exp_facing = anat_spec.get("expected_facing", "any")
            if exp_facing in ("left", "right"):
                wrong_face = "right" if exp_facing == "left" else "left"
                if wide_anat["facing_direction"] == wrong_face or (
                    facings.count(wrong_face) > facings.count(exp_facing) and facings.count(wrong_face) >= 1
                ):
                    issues.append(f"anatomical_wrong_hemisphere_facing: detected={wrong_face}, expected={exp_facing}")

            if anat_spec.get("forbid_crimson_lesion") and max_crimson > 0.004:
                issues.append(f"unexpected_crimson_lesion_in_intact_clip: crimson_ratio={max_crimson:.4f}")

            if anat_spec.get("require_crimson_lesion") and max_crimson < 0.0008:
                issues.append(f"missing_required_crimson_lesion: crimson_ratio={max_crimson:.5f}")

            roi = anat_spec.get("expected_signal_roi_norm") or []
            forb_roi = anat_spec.get("forbidden_roi_norm") or []
            check_pt = mean_crimson_c if mean_crimson_c is not None else mean_amber_c
            if check_pt is not None and len(roi) == 4:
                cx, cy = check_pt
                if not (roi[0] <= cx <= roi[2] and roi[1] <= cy <= roi[3]):
                    issues.append(
                        f"signal_or_lesion_outside_expected_roi: centroid=({cx:.2f},{cy:.2f}) not in {roi}"
                    )
                if len(forb_roi) == 4 and (forb_roi[0] <= cx <= forb_roi[2] and forb_roi[1] <= cy <= forb_roi[3]):
                    issues.append(f"signal_or_lesion_in_forbidden_roi: centroid=({cx:.2f},{cy:.2f}) in {forb_roi}")

            anat_measured = {
                "bg_luma": wide_anat["bg_luma"],
                "head_bbox_norm": wide_anat["head_bbox_norm"],
                "max_coronal_symmetry": round(max_coronal_sym, 4),
                "dominant_facing": wide_anat["facing_direction"],
                "max_crimson_ratio": round(max_crimson, 5),
                "crimson_centroid_norm": mean_crimson_c,
                "amber_centroid_norm": mean_amber_c,
            }

        # 5. Camera-Compensated Residual Motion, Jump-Cut Integrity & 2-Beat Scene Progression
        motion_metrics = compute_camera_compensated_motion(all_frames, float(meta["fps"]))
        min_raw = float(mot_spec.get("min_raw_flow_mean", 0.14))
        min_res = float(mot_spec.get("min_residual_subject_flow_p90", 0.40 if is_brain else 0.75))
        min_shift = float(mot_spec.get("min_beat1_vs_beat2_shift", 0.025))

        if motion_metrics.get("has_hard_jump_cut"):
            issues.append(
                f"intra_clip_hard_jump_cut_detected: max_step={motion_metrics['max_frame_step_diff']:.2f}, median_step={motion_metrics['median_frame_step_diff']:.2f}"
            )

        if motion_metrics["raw_flow_mean"] < min_raw and motion_metrics["residual_subject_flow_p90"] < min_res:
            issues.append(
                f"static_composition_low_flow: raw={motion_metrics['raw_flow_mean']:.3f}, residual_p90={motion_metrics['residual_subject_flow_p90']:.3f}"
            )
        elif not is_brain and motion_metrics["residual_subject_flow_p90"] < min_res and motion_metrics["beat1_vs_beat2_shift"] < 0.06:
            issues.append(
                f"frozen_subject_tableau: residual_p90={motion_metrics['residual_subject_flow_p90']:.3f}<{min_res:.2f}, beat_shift={motion_metrics['beat1_vs_beat2_shift']:.3f}"
            )

        if grounding_spec.get("requires_scale_pullback") and motion_metrics["beat1_vs_beat2_shift"] < min_shift:
            issues.append(
                f"missing_required_pullback_progression: beat1_vs_beat2_shift={motion_metrics['beat1_vs_beat2_shift']:.3f}<{min_shift:.2f}"
            )

        # 6. Forbidden Scene Hallucinations (human skin/fur drift, lost porcelain cast, red curtains, cloned figures)
        has_cast_entity = any(str(e).startswith("cast (") for e in req_entities)
        forb_hits = detect_forbidden_scene_hallucinations(
            sampled,
            forb_elems,
            is_brain_clip=is_brain,
            require_porcelain_presence=has_cast_entity,
        )
        issues.extend(forb_hits)

        # 7. Structured Per-Clip Semantic Verification Gate (enforced when required or when review file exists on disk)
        effective_require_sem = bool(require_semantic_review or sem_path.exists())
        if c_num in semantic_summary["boilerplate_note_clips"]:
            issues.append("semantic_review_boilerplate_copy_paste_note")
        elif c_num in semantic_summary["failed_clips"]:
            issues.append("semantic_review_check_failed")
        elif effective_require_sem and c_num in semantic_summary["pending_clips"]:
            issues.append("semantic_review_pending_or_stale_sha256")

        clip_passed = len(issues) == 0
        if not clip_passed:
            regenerate_clips.append(c_num)

        strip_rel = None
        if render_strips:
            strip_path = strips_dir / f"clip_{c_num:02d}_5frame_strip.png"
            _render_clip_contact_strip(
                c_num,
                role,
                ref_bgr,
                sampled,
                clip_passed,
                min_5pt if win_scores else 0.0,
                max_dots,
                strip_path,
            )
            strip_rel = f"03_visuals/{CLIP_QA_STRIPS_DIRNAME}/{strip_path.name}"

        per_clip_results.append(
            {
                "clip_number": c_num,
                "role": role,
                "scene_id": c_spec.get("scene_id"),
                "is_brain_clip": is_brain,
                "required_entities": req_entities,
                "forbidden_elements": forb_elems,
                "narration_grounding": grounding_spec,
                "reference_qa": ref_qa_info,
                "exists": True,
                "resolution": f"{w}x{h}",
                "duration_sec": meta["duration_sec"],
                "continuity_5pt": {
                    "min_score": round(min_5pt, 4),
                    "max_score": round(max_5pt, 4),
                    "late_drop": late_drop,
                    "windows": win_scores,
                },
                "r53_particles": {
                    "max_neon_green_cyan_ratio": round(max_neon_ratio, 6),
                    "max_floating_particle_dots": max_dots,
                },
                "anatomy": anat_measured,
                "motion": motion_metrics,
                "contact_strip": strip_rel,
                "passed": clip_passed,
                "issues": issues,
            }
        )

    # Cross-Brain-Clip & `ref_brain_master` Continuity Check (Item 5 / R51)
    cross_brain_spec = contract.get("cross_brain_continuity_contract") or {}
    cross_brain_report: dict[str, Any] = {"checked": False, "passed": True, "issues": []}
    if cross_brain_spec.get("enabled") and (len(brain_clip_features) >= 2 or (len(brain_clip_features) >= 1 and (brain_master_bgr is not None or has_clip_ref_pack))):
        b_nums = sorted(brain_clip_features.keys())
        ious: list[float] = []
        luma_corrs: list[float] = []
        per_clip_ious: dict[int, list[float]] = {n: [] for n in b_nums}
        per_clip_corrs: dict[int, list[float]] = {n: [] for n in b_nums}
        bg_lumas = [float(brain_clip_features[n]["bg_luma"]) for n in b_nums]
        facings = {n: brain_clip_features[n]["facing_direction"] for n in b_nums}
        cb_issues: list[str] = []
        outliers: list[int] = []

        req_iou = float(cross_brain_spec.get("min_pairwise_silhouette_iou", 0.45))
        req_corr = float(cross_brain_spec.get("min_pairwise_spatial_corr", 0.52))
        max_bg = float(cross_brain_spec.get("max_bg_luma_spread", 45.0))

        # A. Direct comparison of EVERY brain clip against `ref_brain_master.png`
        master_vs_clips: dict[int, dict[str, Any]] = {}
        if brain_master_bgr is not None and brain_master_bgr.size > 0:
            master_feat = analyze_brain_anatomy_frame(brain_master_bgr)
            sm = master_feat["_sil_64"] > 0
            lm = master_feat["_luma_64"].ravel()
            m_facing = master_feat["facing_direction"]
            m_bg = float(master_feat["bg_luma"])
            for bn in b_nums:
                fb = brain_clip_features[bn]
                sb = fb["_sil_64"] > 0
                inter_m = float(np.sum(sm & sb))
                union_m = float(np.sum(sm | sb))
                m_iou = inter_m / union_m if union_m > 10.0 else 0.0
                lb = fb["_luma_64"].ravel()
                m_corr = float((np.corrcoef(lm, lb)[0, 1] + 1.0) * 0.5) if (float(np.std(lm)) > 1.0 and float(np.std(lb)) > 1.0) else 0.0
                m_bg_diff = abs(float(fb["bg_luma"]) - m_bg)
                master_vs_clips[bn] = {
                    "silhouette_iou": round(m_iou, 4),
                    "spatial_corr": round(m_corr, 4),
                    "bg_luma_diff": round(m_bg_diff, 2),
                }
                if m_iou < req_iou:
                    cb_issues.append(f"brain_clip_{bn}_mismatch_with_ref_brain_master_silhouette: iou={m_iou:.3f}<{req_iou:.2f}")
                    outliers.append(bn)
                if m_corr < req_corr:
                    cb_issues.append(f"brain_clip_{bn}_mismatch_with_ref_brain_master_angle: corr={m_corr:.3f}<{req_corr:.2f}")
                    outliers.append(bn)
                if m_bg_diff > max_bg:
                    cb_issues.append(f"brain_clip_{bn}_backdrop_mismatch_with_ref_brain_master: diff={m_bg_diff:.1f}>{max_bg:.1f}")
                    outliers.append(bn)
                if m_facing in ("left", "right") and fb["facing_direction"] not in (m_facing, "ambiguous"):
                    cb_issues.append(f"brain_clip_{bn}_facing_mismatch_with_ref_brain_master: {fb['facing_direction']}!={m_facing}")
                    outliers.append(bn)
        elif has_clip_ref_pack:
            cb_issues.append("missing_ref_brain_master_anchor: 03_visuals/reference_images/ref_brain_master.png")

        # B. Pairwise consistency across all brain clips
        for i in range(len(b_nums)):
            for j in range(i + 1, len(b_nums)):
                na, nb = b_nums[i], b_nums[j]
                fa = brain_clip_features[na]
                fb = brain_clip_features[nb]
                sa, sb = fa["_sil_64"] > 0, fb["_sil_64"] > 0
                inter = float(np.sum(sa & sb))
                union = float(np.sum(sa | sb))
                pair_iou = inter / union if union > 10.0 else 0.0
                ious.append(pair_iou)
                per_clip_ious[na].append(pair_iou)
                per_clip_ious[nb].append(pair_iou)
                la, lb = fa["_luma_64"].ravel(), fb["_luma_64"].ravel()
                if float(np.std(la)) > 1.0 and float(np.std(lb)) > 1.0:
                    pair_corr = float((np.corrcoef(la, lb)[0, 1] + 1.0) * 0.5)
                    luma_corrs.append(pair_corr)
                    per_clip_corrs[na].append(pair_corr)
                    per_clip_corrs[nb].append(pair_corr)

        min_iou = round(float(min(ious)) if ious else (min((v["silhouette_iou"] for v in master_vs_clips.values()), default=0.0)), 4)
        min_luma_corr = round(float(min(luma_corrs)) if luma_corrs else (min((v["spatial_corr"] for v in master_vs_clips.values()), default=0.0)), 4)
        bg_spread = round(max(bg_lumas) - min(bg_lumas), 2) if len(bg_lumas) >= 2 else 0.0

        if ious and min_iou < req_iou:
            cb_issues.append(f"brain_bust_silhouette_mismatch_across_clips: min_iou={min_iou:.3f}<{req_iou:.2f}")
        if luma_corrs and min_luma_corr < req_corr:
            cb_issues.append(f"brain_spatial_angle_mismatch_across_clips: min_corr={min_luma_corr:.3f}<{req_corr:.2f}")
        if len(bg_lumas) >= 2 and bg_spread > max_bg:
            cb_issues.append(f"brain_backdrop_luma_inconsistent: spread={bg_spread:.1f}>{max_bg:.1f}")
        distinct_non_ambig = {v for v in facings.values() if v != "ambiguous"}
        if cross_brain_spec.get("require_consistent_facing") and len(distinct_non_ambig) > 1:
            cb_issues.append(f"inconsistent_brain_facing_directions: {facings}")

        if cb_issues:
            expected_by_clip = {
                int(cs["clip_number"]): str((cs.get("anatomical_contract") or {}).get("expected_facing") or "any")
                for cs in (contract.get("clips") or [])
            }
            non_ambig_vals = [v for v in facings.values() if v != "ambiguous"]
            majority_facing = max(set(non_ambig_vals), key=non_ambig_vals.count) if non_ambig_vals else "any"
            med_bg = float(np.median(bg_lumas)) if bg_lumas else 0.0

            for bn in b_nums:
                exp_f = expected_by_clip.get(bn, "any")
                target_f = exp_f if exp_f in ("left", "right") else majority_facing
                mean_iou_bn = float(np.mean(per_clip_ious[bn])) if per_clip_ious[bn] else 1.0
                mean_corr_bn = float(np.mean(per_clip_corrs[bn])) if per_clip_corrs[bn] else 1.0
                if (
                    bn in regenerate_clips
                    or (target_f in ("left", "right") and facings.get(bn) not in (target_f, "ambiguous"))
                    or mean_iou_bn < req_iou
                    or mean_corr_bn < req_corr
                    or (len(bg_lumas) >= 2 and abs(float(brain_clip_features[bn]["bg_luma"]) - med_bg) > max_bg * 0.65)
                ):
                    outliers.append(bn)

            for bn in (outliers or b_nums):
                if bn not in regenerate_clips:
                    regenerate_clips.append(bn)

        cross_brain_report = {
            "checked": True,
            "ref_brain_master_present": brain_master_bgr is not None,
            "ref_brain_master_comparisons": master_vs_clips,
            "brain_clips_inspected": b_nums,
            "outlier_brain_clips": sorted(set(outliers)),
            "min_pairwise_silhouette_iou": min_iou,
            "min_pairwise_spatial_corr": min_luma_corr,
            "bg_luma_spread": bg_spread,
            "facings": facings,
            "passed": len(cb_issues) == 0,
            "issues": cb_issues,
        }

    regenerate_clips = sorted(set(regenerate_clips))
    effective_sem_gate = bool(require_semantic_review or sem_path.exists())
    sem_gate_ok = (
        (semantic_summary["complete"] and not semantic_summary["failed_clips"])
        if effective_sem_gate
        else (len(semantic_summary["failed_clips"]) == 0)
    )
    all_passed = (
        len(per_clip_results) == int(contract.get("clip_count") or len(per_clip_results))
        and len(regenerate_clips) == 0
        and bool(cross_brain_report.get("passed", True))
        and sem_gate_ok
    )

    report = {
        "schema_version": 1,
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "project_id": p_dir.name,
        "all_passed": all_passed,
        "clips_checked": len(per_clip_results),
        "regenerate_clips": regenerate_clips,
        "cross_brain_continuity": cross_brain_report,
        "semantic_review": semantic_summary,
        "sha256_binding": {
            "contract_sha256": contract_sha,
            "reference_images": ref_sha_map,
            "native_clips": clip_sha_map,
            "final_shorts_mp4_sha256": final_mp4_sha,
            "semantic_review_sha256": sem_sha,
        },
        "clips": per_clip_results,
    }

    if save_report:
        vis_dir.mkdir(parents=True, exist_ok=True)
        (vis_dir / CLIP_QA_REPORT_FILENAME).write_text(
            json.dumps(report, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    return report


def is_clip_qa_report_fresh(project_dir: Path, report: dict[str, Any] | None = None) -> tuple[bool, list[str]]:
    """
    Verifies cryptographic freshness of `03_visuals/clip_contract_qa_report.json` against current files on disk.
    Any modified/replaced `ref_*.png`, `clip_*.mp4`, `clip_semantic_review.json`, or `final_shorts_1080x1920.mp4`
    invalidates the report.
    """
    p_dir = Path(project_dir)
    vis_dir = p_dir / "03_visuals"
    rep_path = vis_dir / CLIP_QA_REPORT_FILENAME
    if report is None:
        if not rep_path.exists():
            return False, ["missing_clip_contract_qa_report"]
        try:
            report = json.loads(rep_path.read_text(encoding="utf-8"))
        except Exception as exc:
            return False, [f"corrupt_clip_contract_qa_report: {exc}"]

    binding = report.get("sha256_binding") or {}
    reasons: list[str] = []

    contract_path = vis_dir / CLIP_QA_CONTRACT_FILENAME
    if contract_path.exists():
        if binding.get("contract_sha256") != compute_sha256(contract_path):
            reasons.append("stale_contract_sha256")

    ref_dir = vis_dir / REF_IMAGES_DIRNAME
    recorded_refs = dict(binding.get("reference_images") or {})
    if ref_dir.exists():
        current_refs = {rf.name: compute_sha256(rf) for rf in sorted(ref_dir.glob("*.png")) if rf.is_file()}
        if current_refs != recorded_refs:
            reasons.append("stale_reference_images_sha256")

    clips_dir = vis_dir / "flow_native_clips"
    recorded_clips = dict(binding.get("native_clips") or {})
    if clips_dir.exists():
        current_clips = {cf.name: compute_sha256(cf) for cf in sorted(clips_dir.glob("clip_*.mp4")) if cf.is_file()}
        if current_clips != recorded_clips:
            reasons.append("stale_native_clips_sha256")

    sem_path = vis_dir / CLIP_SEMANTIC_REVIEW_FILENAME
    cur_sem_sha = compute_sha256(sem_path) if sem_path.exists() else None
    if cur_sem_sha != binding.get("semantic_review_sha256"):
        reasons.append("stale_semantic_review_sha256")

    final_mp4 = p_dir / "05_assembly" / "final_shorts_1080x1920.mp4"
    if final_mp4.exists() and binding.get("final_shorts_mp4_sha256") is not None:
        if binding.get("final_shorts_mp4_sha256") != compute_sha256(final_mp4):
            reasons.append("stale_final_shorts_mp4_sha256")

    return len(reasons) == 0, reasons


__all__ = [
    "AUDIO_LIMITER_CEILING_DBFS",
    "AUDIO_TRUE_PEAK_MAX_DBFS",
    "CLIP_QA_CONTRACT_FILENAME",
    "CLIP_QA_REPORT_FILENAME",
    "CLIP_QA_STRIPS_DIRNAME",
    "CLIP_SEMANTIC_CHECKS",
    "CLIP_SEMANTIC_REVIEW_FILENAME",
    "SAMPLE_WINDOWS_5PT",
    "analyze_brain_anatomy_frame",
    "compile_clip_qa_contract",
    "compute_camera_compensated_motion",
    "compute_sha256",
    "compute_spatial_and_palette_continuity",
    "detect_forbidden_scene_hallucinations",
    "detect_r53_neon_particles",
    "extract_clip_required_entities",
    "infer_forbidden_elements",
    "is_clip_qa_report_fresh",
    "sample_video_frames_5pt",
    "validate_clip_semantic_review",
    "verify_clips_against_contract",
    "write_clip_semantic_review_template",
]
