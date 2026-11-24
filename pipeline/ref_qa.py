"""
ALL ABOUT BRAIN - Reference Image Bible & 10-Axis Granular Image QA Engine (Rule R51).

Why this module exists:
Generating 10 video clips independently from text prompts alone risks visual drift in:
  1. Mannequin head/body proportions, frosted-glass cranium translucency, and period wardrobe.
  2. Room architecture, window placement, and daylight colour temperature.
  3. Hero apparatus geometry (e.g. 30-switch shock generator, 43-inch tamping iron, metronome & harness).
  4. 3D brain orientation and 4-point bioluminescent colour code (crimson, cyan, amber-gold, green).

Solution (Gear 2.5 -> Gear 3):
  1. `build_reference_image_specs(plan, narrations, dossier_data, aspect)` builds a deterministic Reference Image
     Bible (`03_visuals/reference_image_specs.json`) covering:
       - `ref_cast_subject` (primary porcelain mannequin & wardrobe turnaround anchor)
       - `ref_env_master` (master room / site layout & daylight anchor)
       - `ref_prop_hero` (signature experimental apparatus macro anchor)
       - `ref_clip_01 .. ref_clip_N` (per-clip keyframe anchors mapped to `scene_id` and `role`)
  2. `inspect_single_reference_image` & `inspect_reference_image_pack` enforce a strict 10-Axis Quantitative
     Image QA Gate (`Q1..Q10`):
       - Q1: Resolution, aspect ratio (9:16 or 16:9), file size >= 30 KB, zero black letterbox/pillarbox bars.
       - Q2: High-key daylight exposure (`70.0 <= luma_mean <= 242.0`) & dynamic contrast (`luma_std >= 22.0`).
       - Q3: Focus sharpness (`Laplacian var >= 45.0`) & structural Canny edge density (`>= 0.015`).
       - Q4: Matte-white porcelain cast fidelity (`porcelain_ratio >= 0.04`) & zero human flesh-tone drift (`<= 0.12`).
       - Q5: Environment & prop spatial depth (Shannon entropy `>= 4.2` bits, foreground/background edge balance).
       - Q6: Brain 4-point colour-code verification (`crimson-red`, `electric cyan-blue`, `warm amber-gold`,
             `bioluminescent green` on bright studio gallery) for `brain_void` / `drill_down` shots.
       - Q7: Zero burned-in text, HUD boxes, or watermark pollution in top/bottom safe zones.
       - Q8: Cross-image scene palette & lighting consistency (`HSV hist corr >= 0.55`, `luma_spread <= 55.0`).
       - Q9: Cross-image cast & wardrobe chrominance lock (`LAB ab drift <= 16.0`).
       - Q10: Per-role shot diversity (`dHash distance >= 2`) & Video-to-Reference continuity (`corr >= 0.55`).
  3. Any failing reference image is flagged in `regenerate_image_ids` for automatic regeneration in Google Flow
     `Image` mode (`Nano Banana 2.1`, 0 credits) before video clips are conditioned via `"Add ingredients to the prompt box"`.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from pipeline.config import (
    BRAIN_SETTINGS,
    FLOW_ASPECT_SHORTS,
    MIN_REF_IMAGE_SIZE_BYTES,
    MIN_REF_IMAGES_PER_PROJECT,
    PORCELAIN_REF_NEON_GREEN_MAX,
    PORCELAIN_REF_WHITE_RATIO_MAX,
    PORCELAIN_V7_STYLE_PROFILE,
    REF_IMAGE_CAST_CHROMA_DRIFT_MAX,
    REF_IMAGE_CLIP_CONTINUITY_CORR_MIN,
    REF_IMAGE_CONTRAST_STD_MIN,
    REF_IMAGE_CROSS_HIST_CORR_MIN,
    REF_IMAGE_CROSS_LUMA_SPREAD_MAX,
    REF_IMAGE_EDGE_DENSITY_MIN,
    EXPRESSIVE_25D_V8_STYLE_PROFILE,
    EXPRESSIVE_V8_CAMEO_SHEET_FILENAME,
    EXPRESSIVE_V8_SPECIES_SHEET_FILENAME,
    REF_IMAGE_HUMAN_SKIN_MAX,
    REF_IMAGE_LUMA_MAX,
    REF_IMAGE_LUMA_MIN,
    REF_IMAGE_MIN_HEIGHT_SHORTS,
    REF_IMAGE_MIN_WIDTH_SHORTS,
    REF_IMAGE_PORCELAIN_RATIO_MIN,
    REF_IMAGE_BIOLUM_MIN,
    REF_IMAGE_MIN_DHASH_DISTANCE,
    REF_IMAGE_SHARPNESS_MIN,
    REF_IMAGE_SOURCE_EXTRACTED,
    REF_IMAGE_SOURCES_PRE_GENERATION,
    REF_IMAGES_DIRNAME,
    clip_roles,
    extract_explicit_v7_style_profile,
    is_expressive_v8_plan,
)
from pipeline.storage import compute_sha256
from pipeline.depiction_rules import (
    cast_for_shot,
    cast_lock_entries,
    cast_lock_sentence,
    key_visual_clip_numbers,
    key_visual_for_scene,
    still_frame_prompt,
    still_prefix,
)
from pipeline.prompt_builder import (
    build_flow_prompts,
    flow_prompt_prefix,
    load_visual_plan,
    resolve_clip_setting,
    sanitize_prompt_for_flow as sanitize_scene,
)

REF_SPECS_FILENAME = "reference_image_specs.json"
REF_QA_REPORT_FILENAME = "reference_image_qa_report.json"
REF_PROVENANCE_FILENAME = "provenance.json"            # {filename: source} - who made each image
REF_SEMANTIC_REVIEW_FILENAME = "reference_semantic_review.json"   # Q11: human / multimodal content check


def _dhash_64(gray: np.ndarray) -> str:
    resized = cv2.resize(gray, (9, 8), interpolation=cv2.INTER_AREA)
    diff = resized[:, 1:] > resized[:, :-1]
    bits = "".join("1" if b else "0" for b in diff.flatten())
    return f"{int(bits, 2):016x}"


def _hamming_hex(h1: str, h2: str) -> int:
    try:
        return bin(int(h1, 16) ^ int(h2, 16)).count("1")
    except Exception:
        return 64


def _hsv_hist(bgr: np.ndarray) -> np.ndarray:
    """Computes a 48-bin marginal LAB + HSV palette descriptor invariant to camera angle changes."""
    lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB)
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    h_l = cv2.calcHist([lab], [0], None, [12], [0, 256]).flatten()
    h_a = cv2.calcHist([lab], [1], None, [12], [0, 256]).flatten()
    h_b = cv2.calcHist([lab], [2], None, [12], [0, 256]).flatten()
    h_s = cv2.calcHist([hsv], [1], None, [12], [0, 256]).flatten()
    vec = np.concatenate([h_l, h_a, h_b, h_s]).astype(np.float32)
    norm = float(np.linalg.norm(vec))
    return vec / max(norm, 1e-6)


def _hist_corr(h1: np.ndarray, h2: np.ndarray) -> float:
    if h1.size == 0 or h2.size == 0:
        return 0.0
    n1 = float(np.linalg.norm(h1))
    n2 = float(np.linalg.norm(h2))
    if n1 <= 1e-6 or n2 <= 1e-6:
        return 0.0
    c = float(np.dot(h1, h2) / (n1 * n2))
    return round(max(0.0, min(1.0, c)), 4)


def _shannon_entropy(gray: np.ndarray) -> float:
    hist = cv2.calcHist([gray], [0], None, [256], [0, 256]).flatten()
    p = hist / max(float(hist.sum()), 1.0)
    p = p[p > 0]
    return round(float(-np.sum(p * np.log2(p))), 3)


def _extract_script_lines(s_obj: Any) -> list[str]:
    if not isinstance(s_obj, dict):
        return []
    if isinstance(s_obj.get("clip_narrations"), list) and s_obj["clip_narrations"]:
        return [str(x).strip() for x in s_obj["clip_narrations"] if str(x).strip()]
    if isinstance(s_obj.get("sentences"), list) and s_obj["sentences"]:
        return [str(x).strip() for x in s_obj["sentences"] if str(x).strip()]
    if isinstance(s_obj.get("acts"), list) and s_obj["acts"]:
        return [
            str(s).strip()
            for act in s_obj["acts"]
            if isinstance(act, dict)
            for s in (act.get("sentences") or [])
            if str(s).strip()
        ]
    return []


def build_reference_image_specs(
    plan: dict[str, Any],
    narrations: list[str] | None = None,
    dossier_data: dict[str, Any] | None = None,
    aspect: str = FLOW_ASPECT_SHORTS,
) -> dict[str, Any]:
    """
    Builds the complete Reference Image Bible specification for a project:
      - 3 Master Anchors (`ref_cast_subject`, `ref_env_master`, `ref_prop_hero`)
      - N Per-Clip Keyframe Reference Anchors (`ref_clip_01 .. ref_clip_N`)
    """
    from pipeline.config import is_r76_v8_plan, is_r85_flow_31_brain_plan, is_r88_faceless_cast_plan
    from pipeline.prompt_builder import is_diorama_v6_plan

    mode = str(plan.get("visual_mode") or "NEURO_BIOLOGY").upper()
    if is_expressive_v8_plan(plan):
        is_r76 = is_r76_v8_plan(plan) or is_r85_flow_31_brain_plan(plan)
        is_r88 = is_r88_faceless_cast_plan(plan)
        if is_r88:
            master_anchors_v8 = [
                {
                    "ref_id": "species_opt1_sheet",
                    "category": "cast_anchor",
                    "role": "cast_master",
                    "scene_id": "MASTER_SPECIES",
                    "setting": "real_env",
                    "filename": EXPRESSIVE_V8_SPECIES_SHEET_FILENAME,
                    "title": "Core 6-role matte-white R88 faceless architectural porcelain species turnaround sheet (R88 faceless silhouettes & hands)",
                    "generation_order": 1,
                    "conditioned_on": [],
                    "style_profile": EXPRESSIVE_25D_V8_STYLE_PROFILE,
                    "r88_mode": True,
                    "prompt": "Vertical 9:16 R88 architectural style sheet conditioned on A01 translucent Mode 1 porcelain bust: smooth featureless matte-white architectural porcelain figure proportions, four-fingered porcelain hands, tailored matte woven attire, pure blank porcelain head crown silhouette, studio daylight, zero text.",
                    "must_include": [
                        "matte-white smooth featureless matte-white architectural porcelain cast",
                        "smooth blank porcelain head silhouette",
                    ],
                },
                {
                    "ref_id": "expressive_conflict_master",
                    "category": "environment_anchor",
                    "role": "env_master",
                    "scene_id": "MASTER_CONFLICT",
                    "setting": "real_env",
                    "filename": "expressive_conflict_master.png",
                    "title": "Expressive 2.5D empty sunlit architectural environment master plate (E02_mri_suite_empty, zero cartoon faces)",
                    "generation_order": 1,
                    "conditioned_on": ["species_opt1_sheet"],
                    "style_profile": EXPRESSIVE_25D_V8_STYLE_PROFILE,
                    "r88_mode": True,
                    "prompt": "Vertical 9:16 stylized 2.5D empty architectural environment master plate (E02_mri_suite_empty): a sunlit cream-plaster and oak architectural fMRI imaging suite with soft daylight across clean tables and equipment, zero figures, zero faces, zero cartoon eyes, zero text.",
                    "must_include": [
                        "stylized 2.5D tactile empty architectural room master plate, zero cartoon ink faces",
                    ],
                },
                {
                    "ref_id": "cast_sheet_02_clinical_historical_6roles",
                    "category": "cast_anchor",
                    "role": "cast_master",
                    "scene_id": "MASTER_CAST_CLINICAL",
                    "setting": "real_env",
                    "filename": "cast_sheet_02_clinical_historical_6roles.png",
                    "title": "R88 clinical laboratory empty architectural environment master plate (E01_laboratory_empty, zero cartoon faces)",
                    "generation_order": 2,
                    "conditioned_on": ["species_opt1_sheet"],
                    "style_profile": EXPRESSIVE_25D_V8_STYLE_PROFILE,
                    "r88_mode": True,
                    "prompt": "Vertical 9:16 R88 empty clinical laboratory architectural diorama master plate (E01_laboratory_empty): clean sunlit laboratory benches, cabinetry, and warm natural daylight with strictly zero people, zero figures, zero cartoon eyes, zero text.",
                    "must_include": [
                        "clean empty sunlit clinical laboratory architectural diorama master plate, zero cartoon ink faces",
                    ],
                },
                {
                    "ref_id": "cast_sheet_03_everyday_lifestyle_6roles",
                    "category": "cast_anchor",
                    "role": "cast_master",
                    "scene_id": "MASTER_CAST_EVERYDAY",
                    "setting": "real_env",
                    "filename": "cast_sheet_03_everyday_lifestyle_6roles.png",
                    "title": "R88 everyday kitchen empty architectural environment master plate (E05_kitchen_empty, zero cartoon faces)",
                    "generation_order": 2,
                    "conditioned_on": ["species_opt1_sheet"],
                    "style_profile": EXPRESSIVE_25D_V8_STYLE_PROFILE,
                    "r88_mode": True,
                    "prompt": "Vertical 9:16 R88 empty everyday kitchen architectural diorama master plate (E05_kitchen_empty): warm sunlit kitchen island and cabinetry with crisp architectural surfaces and strictly zero people, zero figures, zero cartoon eyes, zero text.",
                    "must_include": [
                        "clean empty sunlit everyday kitchen architectural diorama master plate, zero cartoon ink faces",
                    ],
                },
            ]
        else:
            master_anchors_v8 = [
                {
                    "ref_id": "species_opt1_sheet",
                    "category": "cast_anchor",
                    "role": "cast_master",
                    "scene_id": "MASTER_SPECIES",
                    "setting": "real_env",
                    "filename": EXPRESSIVE_V8_SPECIES_SHEET_FILENAME,
                    "title": "Core 6-role matte-white 2.5D vinyl species turnaround sheet (2D charcoal ink faces)",
                    "generation_order": 1,
                    "conditioned_on": [],
                    "style_profile": EXPRESSIVE_25D_V8_STYLE_PROFILE,
                    "prompt": "Vertical 9:16 character bible sheet of matte-white 2.5D vinyl cast with crisp charcoal 2D ink expressions and tailored matte fabric wardrobe, zero text.",
                    "must_include": ["matte-white 2.5D vinyl cast", "charcoal 2D ink facial features"],
                },
                {
                    "ref_id": "expressive_conflict_master",
                    "category": "environment_anchor",
                    "role": "env_master",
                    "scene_id": "MASTER_CONFLICT",
                    "setting": "real_env",
                    "filename": "expressive_conflict_master.png",
                    "title": "Expressive 2.5D dramatic tactile lighting and staging master plate",
                    "generation_order": 1,
                    "conditioned_on": ["species_opt1_sheet"],
                    "style_profile": EXPRESSIVE_25D_V8_STYLE_PROFILE,
                    "prompt": "Vertical 9:16 stylized 2.5D cinematic interior room staging plate: a sunlit warm oak-and-cream-plaster architectural study room with tall paned windows casting soft diagonal daylight beams across a wooden desk, where one bald smooth matte cream-white 2.5D vinyl protagonist with bold 2D charcoal-black cartoon ink eyes and eyebrows sits in thoughtful focus wearing a tailored navy jacket; completely blank smooth cream walls, strictly zero wall text, zero stencil letters, zero clocks, zero numbers, zero labels.",
                    "must_include": ["stylized 2.5D tactile room staging", "matte-white vinyl protagonist"],
                },
                {
                    "ref_id": "cast_sheet_02_clinical_historical_6roles",
                    "category": "cast_anchor",
                    "role": "cast_master",
                    "scene_id": "MASTER_CAST_CLINICAL",
                    "setting": "real_env",
                    "filename": "cast_sheet_02_clinical_historical_6roles.png",
                    "title": "Clinical & historical 6-role matte-white 2.5D vinyl cast sheet",
                    "generation_order": 2,
                    "conditioned_on": ["species_opt1_sheet"],
                    "style_profile": EXPRESSIVE_25D_V8_STYLE_PROFILE,
                    "prompt": "Vertical 9:16 6-role clinical and historical matte-white 2.5D vinyl cast turnaround sheet, zero text.",
                    "must_include": ["clinical and historical 2.5D vinyl cast"],
                },
                {
                    "ref_id": "cast_sheet_03_everyday_lifestyle_6roles",
                    "category": "cast_anchor",
                    "role": "cast_master",
                    "scene_id": "MASTER_CAST_EVERYDAY",
                    "setting": "real_env",
                    "filename": "cast_sheet_03_everyday_lifestyle_6roles.png",
                    "title": "Everyday lifestyle 6-role matte-white 2.5D vinyl cast sheet",
                    "generation_order": 2,
                    "conditioned_on": ["species_opt1_sheet"],
                    "style_profile": EXPRESSIVE_25D_V8_STYLE_PROFILE,
                    "prompt": "Vertical 9:16 6-role everyday lifestyle matte-white 2.5D vinyl cast turnaround sheet, zero text.",
                    "must_include": ["everyday lifestyle 2.5D vinyl cast"],
                },
            ]
        if not is_r76:
            master_anchors_v8[1:1] = [
                {
                    "ref_id": "cameo_opt3_sheet",
                    "category": "cast_anchor",
                    "role": "cameo_master",
                    "scene_id": "MASTER_CAMEO",
                    "setting": "real_env",
                    "filename": EXPRESSIVE_V8_CAMEO_SHEET_FILENAME,
                    "title": "Mini-Cortex palm-sized porcelain-gyri mascot cameo bible sheet",
                    "generation_order": 1,
                    "conditioned_on": [],
                    "style_profile": EXPRESSIVE_25D_V8_STYLE_PROFILE,
                    "prompt": "Vertical 9:16 Mini-Cortex palm-sized translucent porcelain-gyri cameo mascot turnaround sheet, zero text.",
                    "must_include": ["Mini-Cortex palm-sized brain cameo mascot"],
                },
                {
                    "ref_id": "xray_brain75_master",
                    "category": "brain_anchor",
                    "role": "brain_master",
                    "scene_id": "MASTER_BRAIN",
                    "setting": "brain_studio",
                    "filename": "xray_brain75_master.png",
                    "title": "Translucent X-ray 3D brain silhouette master anchor over dark studio void",
                    "generation_order": 1,
                    "conditioned_on": [],
                    "style_profile": EXPRESSIVE_25D_V8_STYLE_PROFILE,
                    "prompt": "Vertical 9:16 translucent X-ray 3D brain silhouette with cerebellum and brainstem floating over #05080F dark studio void, zero text.",
                    "must_include": ["translucent X-ray 3D brain silhouette", "dark studio void background"],
                },
            ]
        master_fnames_v8 = {m["filename"] for m in master_anchors_v8}
        clip_anchors_v8: list[dict[str, Any]] = []
        for idx, raw_anc in enumerate(plan.get("reference_anchors") or [], start=1):
            if not isinstance(raw_anc, dict):
                continue
            fname = str(raw_anc.get("filename") or f"{raw_anc.get('ref_id') or f'ref_clip_{idx:02d}'}.png")
            if fname in master_fnames_v8:
                continue
            c_num = int(raw_anc.get("clip_number") or idx)
            which = str(raw_anc.get("frame") or "start")
            ref_id = str(raw_anc.get("ref_id") or Path(fname).stem)
            setting = str(raw_anc.get("setting") or "real_env")
            is_brain = setting in (*BRAIN_SETTINGS, "brain_studio")
            raw_cond = raw_anc.get("conditioned_on")
            is_r85_brain = bool(raw_anc.get("r85_brain_clip"))
            if is_r76:
                from pipeline.canonical_assets import (
                    select_canonical_arrow_slot,
                    select_canonical_brain_slot,
                    select_canonical_character_slot,
                    select_canonical_drone_slot,
                    select_canonical_environment_slot,
                )

                explicit_can_slot = str(raw_anc.get("canonical_slot_id") or "").strip()
                if explicit_can_slot:
                    default_r85_cond = [f"canonical_{explicit_can_slot}"]
                elif is_brain:
                    bslot = select_canonical_brain_slot(
                        brain_region=str(raw_anc.get("brain_region") or ""),
                        viewpoint=str(raw_anc.get("viewpoint") or ""),
                        mode=str(raw_anc.get("r85_brain_mode") or ""),
                        shot_scale=str(raw_anc.get("r85_shot_scale") or ""),
                        neural_state=str(raw_anc.get("neural_state") or ""),
                        side_by_side=bool(raw_anc.get("side_by_side_brain_compare")),
                    )
                    default_r85_cond = [f"canonical_{bslot}"]
                elif str(raw_anc.get("arrow_3d_mode") or ""):
                    default_r85_cond = [f"canonical_{select_canonical_arrow_slot(str(raw_anc.get('arrow_3d_mode') or ''))}"]
                elif str(raw_anc.get("category") or "") == "drone_anchor":
                    default_r85_cond = [f"canonical_{select_canonical_drone_slot(str(raw_anc.get('prompt') or ''))}"]
                elif raw_anc.get("present_cast") == []:
                    default_r85_cond = [f"canonical_{select_canonical_environment_slot(str(raw_anc.get('prompt') or ''), staged=False, r88_faceless=is_r88)}"]
                else:
                    default_r85_cond = [f"canonical_{select_canonical_character_slot(r88_faceless=is_r88)}"]
            else:
                default_r85_cond = ["xray_brain75_master"] if is_brain else ["species_opt1_sheet"]

            cond_list_v8 = (
                list(raw_cond)
                if raw_cond is not None
                else default_r85_cond
            )
            default_must_inc = (
                ["Episode #31 matte silver-white gypsum 3D brain with opaque sky-blue sulcal groove tubes, zero VFX, zero text"]
                if (is_brain and is_r85_brain)
                else (
                    ["translucent frosted-glass 3D brain, zero text"]
                    if is_brain
                    else (
                        ["stylized 3D miniature architectural landmark, zero text"]
                        if raw_anc.get("present_cast") == []
                        else (
                            ["matte-white smooth featureless architectural porcelain cast, no human skin"]
                            if is_r88
                            else ["matte-white 2.5D vinyl cast, no human skin"]
                        )
                    )
                )
            )
            clip_anchors_v8.append(
                {
                    "ref_id": ref_id,
                    "clip_number": c_num,
                    "frame": which,
                    "category": str(raw_anc.get("category") or ("brain_anchor" if is_brain else "clip_keyframe_anchor")),
                    "role": str(raw_anc.get("role") or ("brain_mechanism" if is_brain else "reenactment")),
                    "scene_id": str(raw_anc.get("scene_id") or ("BRAIN" if is_brain else f"EP{idx:02d}")),
                    "setting": setting,
                    "location_id": raw_anc.get("location_id"),
                    "filename": fname,
                    "title": str(raw_anc.get("title") or f"Clip {c_num:02d} {which} anchor"),
                    "generation_order": int(raw_anc.get("generation_order") or 3),
                    "canonical_slot_id": raw_anc.get("canonical_slot_id"),
                    "conditioned_on": cond_list_v8,
                    "style_profile": EXPRESSIVE_25D_V8_STYLE_PROFILE,
                    "r88_mode": bool(is_r88),
                    "prompt": sanitize_scene(str(raw_anc.get("prompt") or "")),
                    "diegetic_text_allowlist": list(raw_anc.get("diegetic_text_allowlist") or []),
                    "present_cast": raw_anc.get("present_cast"),
                    "previs_guide_png": raw_anc.get("previs_guide_png"),
                    "color_role_legend": raw_anc.get("color_role_legend"),
                    "real_world_target_id": raw_anc.get("real_world_target_id"),
                    "real_world_category": raw_anc.get("real_world_category"),
                    "r72_relay_stage": raw_anc.get("r72_relay_stage"),
                    "r74_relay_stage": raw_anc.get("r74_relay_stage"),
                    "is_r74_macro_anchor": bool(raw_anc.get("is_r74_macro_anchor")),
                    "brain_region": raw_anc.get("brain_region"),
                    "end_brain_region": raw_anc.get("end_brain_region"),
                    "neural_state": raw_anc.get("neural_state"),
                    "side_by_side_brain_compare": bool(raw_anc.get("side_by_side_brain_compare")),
                    "custom_brain_anchor": bool(raw_anc.get("custom_brain_anchor") or is_r85_brain),
                    "r85_brain_clip": is_r85_brain,
                    "r85_brain_mode": raw_anc.get("r85_brain_mode"),
                    "r85_shot_scale": raw_anc.get("r85_shot_scale"),
                    "viewpoint": raw_anc.get("viewpoint"),
                    "structural_guide_path": raw_anc.get("structural_guide_path"),
                    "wikimedia_structural_plate": raw_anc.get("wikimedia_structural_plate"),
                    "mni152_offscreen_guide": raw_anc.get("mni152_offscreen_guide"),
                    "viewer_must_understand": raw_anc.get("viewer_must_understand"),
                    "skip_structural_guide": bool(raw_anc.get("skip_structural_guide")),
                    "must_include": list(raw_anc.get("must_include") or default_must_inc),
                }
            )
        all_v8 = master_anchors_v8 + clip_anchors_v8
        return {
            "schema_version": 8,
            "visual_mode": mode,
            "style_profile": EXPRESSIVE_25D_V8_STYLE_PROFILE,
            "aspect": aspect,
            "dossier": plan.get("dossier") or plan.get("dossier_slug"),
            "total_reference_images": len(all_v8),
            "cast_lock": cast_lock_sentence(plan),
            "generation_order": "1 pre-verified expressive_25d_v8 species/cameo/brain/conflict masters -> 2 18-character cast sheets -> 3 optional daisy-chain clip keyframes",
            "master_anchors": master_anchors_v8,
            "clip_anchors": clip_anchors_v8,
            "all_specs": all_v8,
        }

    diorama_mode = is_diorama_v6_plan(plan)
    if diorama_mode:
        n_clips = len(plan.get("clips") or []) or (len(narrations) if narrations else 60)
        roles: tuple[str, ...] = ()
    else:
        n_clips = len(narrations) if narrations and 5 <= len(narrations) <= 10 else 10
        roles = clip_roles(n_clips)
    prefix = flow_prompt_prefix(aspect)
    still_suffix = (
        "Still reference keyframe photograph, razor-sharp macro focus, bright high-key documentary daylight, "
        "matte-white porcelain mannequin figures with period wardrobe, zero on-screen text, zero watermark."
    )

    cast_info = plan.get("cast") or {}
    subj_desc = str(
        cast_info.get("subject")
        or "an articulated matte-white porcelain subject mannequin in authentic period wardrobe"
    ).strip()
    env_desc = str(
        plan.get("real_environment")
        or "a bright, historically accurate documentary environment with natural daylight streaming through windows"
    ).strip()
    props_list = plan.get("environment_props") or []
    hero_prop = str(
        props_list[0]
        if props_list
        else (plan.get("scale_anchor_object") or "the primary experimental apparatus on a wooden table")
    ).strip()

    # If v5 shots exist, extract rich environment/action/prop descriptions
    shots = plan.get("shots") or {}
    first_shot = (
        (shots.get(roles[0]) if roles else None) or next(iter(shots.values()), {})
        if isinstance(shots, dict)
        else {}
    )
    if not plan.get("real_environment") and isinstance(first_shot, dict) and first_shot.get("environment"):
        env_desc = str(first_shot["environment"]).strip()
    if not props_list and isinstance(first_shot, dict) and first_shot.get("prop_change"):
        hero_prop = str(first_shot["prop_change"]).strip()

    from pipeline.config import is_porcelain_v7_plan

    porcelain_v7 = is_porcelain_v7_plan(plan)
    if porcelain_v7 or mode == "BEHAVIORAL_PSYCH":
        cranium_clause = "with a completely smooth featureless solid matte-white egg-shaped oval head"
    else:
        cranium_clause = "with a translucent frosted-glass cranium softly revealing the matte-white brain gyri inside"

    sprefix = still_prefix(aspect)
    no_text = (
        "Razor-sharp focus, bright even documentary light, smooth featureless blank matte-white oval porcelain heads, clean unmarked walls, zero text, zero letters, zero numbers, no watermark."
        if porcelain_v7
        else "Razor-sharp focus, bright even documentary light, no real human faces, no text, no watermark."
    )
    cast_lock = cast_lock_sentence(plan)
    default_env_loc = str(plan.get("default_location_id") or "").strip()
    master_anchors: list[dict[str, Any]] = [
        {
            "ref_id": "ref_env_master",
            "category": "environment_anchor",
            "role": "env_master",
            "scene_id": "MASTER_ENV",
            "setting": "real_env",
            "filename": "ref_env_master.png",
            "title": "Empty environment plate (generate FIRST; every later image is conditioned on it)",
            "generation_order": 1,
            "conditioned_on": [],
            "present_cast": [],
            **({"location_id": default_env_loc} if default_env_loc else {}),
            "prompt": sanitize_scene(
                f"{sprefix} Wide empty establishing view of {env_desc}, featuring {hero_prop}. "
                f"Even natural daylight, deep depth of field. {no_text}"
            ),
            "must_include": [env_desc[:80], hero_prop[:60]],
        },
    ]
    cast_view_lead = "Full-body three-quarter profile view" if porcelain_v7 else "Full-body front view"
    for i, entry in enumerate(cast_lock_entries(plan)[:4]):
        master_anchors.append(
            {
                "ref_id": f"ref_cast_{entry['id']}",
                "category": "cast_anchor",
                "role": "cast_master",
                "scene_id": "MASTER_CAST",
                "setting": "real_env",
                "filename": f"ref_cast_{entry['id']}.png",
                "title": f"Cast sheet: {entry['id']} (full body, inside the environment plate)",
                "generation_order": 2,
                "conditioned_on": ["ref_env_master"],
                "present_cast": [str(entry["id"])],
                **({"location_id": default_env_loc} if default_env_loc else {}),
                "prompt": sanitize_scene(
                    f"{sprefix} {cast_view_lead} of one articulated matte-white porcelain mannequin "
                    f"{cranium_clause}, {entry['id'].replace('_', ' ')} wearing {entry['look']}, standing in {env_desc}. "
                    f"Smooth ball-jointed matte-white porcelain hands and joints. {no_text}"
                ),
                "must_include": [entry["look"][:80], "porcelain mannequin, no human skin or face"],
            }
        )
    master_anchors.append(
        {
            "ref_id": "ref_prop_hero",
            "category": "prop_anchor",
            "role": "prop_master",
            "scene_id": "MASTER_PROP",
            "setting": "real_env",
            "filename": "ref_prop_hero.png",
            "title": "Hero prop close-up (exact geometry, materials, scale)",
            "generation_order": 2,
            "conditioned_on": ["ref_env_master"],
            "present_cast": [],
            **({"location_id": default_env_loc} if default_env_loc else {}),
            "prompt": sanitize_scene(
                f"{sprefix} Close-up of {hero_prop} inside {env_desc}, exact period materials and textures. {no_text}"
            ),
            "must_include": [hero_prop[:80]],
        }
    )
    cast_ids = [m["ref_id"] for m in master_anchors if m["category"] == "cast_anchor"]

    # Per-clip START frames (+ KEY frame for the clip that must show the money shot), aligned with build_flow_prompts
    if diorama_mode:
        dummy_narrs = list(narrations) if narrations else [
            "In this historical case, a single moment changed neuroscience forever."
        ]
    else:
        dummy_narrs = narrations if narrations and len(narrations) == n_clips else [
            "In this historical case, a single moment changed neuroscience forever." for _ in range(n_clips)
        ]
    built_clips = build_flow_prompts(plan, dummy_narrs, aspect=aspect)

    def _safe_clip_setting(clip_item: dict[str, Any]) -> str:
        if clip_item.get("setting"):
            return str(clip_item["setting"])
        if diorama_mode:
            return "brain_studio" if clip_item.get("brain_clip") else "real_env"
        try:
            return resolve_clip_setting(plan, str(clip_item["role"]))
        except KeyError:
            return "real_env"

    has_brain_clips = any(
        bool(c.get("brain_clip")) or _safe_clip_setting(c) in (*BRAIN_SETTINGS, "brain_studio")
        for c in built_clips
    )
    if has_brain_clips:
        from pipeline.depiction_rules import BrainDepictionRule, PromptComposer

        first_brain_scene = next(
            (
                str(c.get("scene") or "")
                for c in built_clips
                if bool(c.get("brain_clip")) or _safe_clip_setting(c) in (*BRAIN_SETTINGS, "brain_studio")
            ),
            "Matte-white porcelain mannequin bust with clean anatomical brain cross-section exposing internal white-matter tracts.",
        )
        master_anchors.append(
            {
                "ref_id": "ref_brain_master",
                "category": "brain_master_anchor",
                "role": "brain_master",
                "scene_id": "MASTER_BRAIN",
                "setting": "brain_void",
                "filename": "ref_brain_master.png",
                "title": "Master brain cutaway bust (generate FIRST for brain clips; every brain clip conditions on this single bust, angle, and backdrop)",
                "generation_order": 1,
                "conditioned_on": [],
                "prompt": sanitize_scene(
                    PromptComposer.compose_brain_still_prompt(
                        BrainDepictionRule.sanitize_brain_signal_text(first_brain_scene),
                        aspect=aspect,
                    )
                ),
                "must_include": [
                    "matte-white porcelain brain cutaway bust with unified angle and studio backdrop",
                    "restrained internal warm-amber/ivory tract glow, zero green or blue flying particles",
                ],
            }
        )

    plan_style_profile = extract_explicit_v7_style_profile(plan) or ""
    if plan_style_profile:
        for m_spec in master_anchors:
            m_spec["style_profile"] = plan_style_profile

    key_clips = {min(nums) for nums in key_visual_clip_numbers(plan, built_clips).values() if nums}
    clip_anchors: list[dict[str, Any]] = []
    curated_anchors = plan.get("reference_anchors")
    if diorama_mode and isinstance(curated_anchors, list) and curated_anchors:
        for idx, raw_anc in enumerate(curated_anchors, start=1):
            if not isinstance(raw_anc, dict):
                continue
            c_num = int(raw_anc.get("clip_number") or idx)
            which = str(raw_anc.get("frame") or "start")
            ref_id = str(raw_anc.get("ref_id") or f"ref_clip_{c_num:02d}{'' if which == 'start' else '_' + which}")
            setting = str(raw_anc.get("setting") or "real_env")
            is_brain = setting in (*BRAIN_SETTINGS, "brain_studio")
            scene_id = str(raw_anc.get("scene_id") or ("BRAIN" if is_brain else f"EP{idx:02d}"))
            role = str(raw_anc.get("role") or ("brain_mechanism" if is_brain else "reenactment"))
            cond_anchors = list(
                raw_anc.get("conditioned_on")
                or (["ref_brain_master"] if is_brain else ["ref_env_master", *cast_ids[:2], "ref_prop_hero"])
            )
            anc_entry: dict[str, Any] = {
                "ref_id": ref_id,
                "clip_number": c_num,
                "frame": which,
                "category": str(raw_anc.get("category") or ("brain_anchor" if is_brain else "clip_keyframe_anchor")),
                "role": role,
                "scene_id": scene_id,
                "setting": setting,
                "filename": str(raw_anc.get("filename") or f"{ref_id}.png"),
                "title": str(raw_anc.get("title") or f"Clip {c_num:02d} ({role} / {scene_id}) {which} frame"),
                "generation_order": int(raw_anc.get("generation_order") or 3),
                "conditioned_on": cond_anchors,
                "prompt": sanitize_scene(str(raw_anc.get("prompt") or still_frame_prompt(plan, role, which, aspect, ""))),
                "must_include": list(raw_anc.get("must_include") or [scene_id, "porcelain mannequin, no human skin"]),
                "key_visual": raw_anc.get("key_visual"),
                "bound_master_anchors": cond_anchors,
            }
            for extra_key in (
                "location_id",
                "present_cast",
                "skip_structural_guide",
                "empty_chairs_note",
                "previs_guide_png",
                "color_role_legend",
                "diegetic_text_allowlist",
            ):
                if extra_key in raw_anc and raw_anc[extra_key] is not None:
                    anc_entry[extra_key] = raw_anc[extra_key]
            if plan_style_profile:
                anc_entry["style_profile"] = plan_style_profile
            clip_anchors.append(anc_entry)
    else:
        for c in built_clips:
            c_num = int(c["clip_number"])
            role = str(c["role"])
            setting = _safe_clip_setting(c)
            is_brain = bool(c.get("brain_clip")) or setting in (*BRAIN_SETTINGS, "brain_studio")
            scene_id = str(c.get("scene_id") or ("BRAIN" if is_brain else "S1"))
            scene_txt = str(c.get("scene") or "").strip()
            if diorama_mode:
                s_idx = int(c.get("sentence_index") or 0)
                narr_txt = dummy_narrs[s_idx - 1] if 1 <= s_idx <= len(dummy_narrs) else ""
            else:
                narr_txt = dummy_narrs[c_num - 1] if 1 <= c_num <= len(dummy_narrs) else ""
            # only the cast sheets of people who are actually in this shot (era variants filtered by year)
            shot_cast_ids = [f"ref_cast_{e['id']}" for e in cast_for_shot(plan, role)] if not is_brain else []
            shot_cast_ids = [x for x in shot_cast_ids if x in cast_ids] or cast_ids[:1]
            variants = [("start", f"ref_clip_{c_num:02d}")]
            if c_num in key_clips:
                variants.append(("key", f"ref_clip_{c_num:02d}_key"))
            for which, ref_id in variants:
                kv = key_visual_for_scene(plan, c.get("scene_id")) if which == "key" else None
                concrete_must = (
                    list(kv.get("must_show") or [])
                    if kv
                    else extract_clip_required_entities(plan, role, scene_id, setting, narr_txt, scene_txt)[:4]
                )
                cond_anchors = ["ref_brain_master"] if is_brain else ["ref_env_master", *shot_cast_ids, "ref_prop_hero"]
                anc_entry = {
                    "ref_id": ref_id,
                    "clip_number": c_num,
                    "frame": which,
                    "category": "brain_anchor" if is_brain else ("key_visual_anchor" if kv else "clip_keyframe_anchor"),
                    "role": role,
                    "scene_id": scene_id,
                    "setting": setting,
                    "filename": f"{ref_id}.png",
                    "title": f"Clip {c_num:02d} ({role} / {scene_id}) {which} frame",
                    "generation_order": 3,
                    "conditioned_on": cond_anchors,
                    "prompt": sanitize_scene(still_frame_prompt(plan, role, which, aspect, scene_txt)),
                    "must_include": concrete_must,
                    "key_visual": kv,
                    "bound_master_anchors": cond_anchors,
                }
                if plan_style_profile:
                    anc_entry["style_profile"] = plan_style_profile
                clip_anchors.append(anc_entry)

    all_specs = master_anchors + clip_anchors
    out_specs: dict[str, Any] = {
        "schema_version": 5,
        "visual_mode": mode,
        "aspect": aspect,
        "dossier": plan.get("dossier"),
        "total_reference_images": len(all_specs),
        "cast_lock": cast_lock,
        "generation_order": "1 env plate + master brain bust -> 2 cast sheets + hero prop (conditioned on env) -> 3 clip start / key frames (conditioned on master anchors)",
        "master_anchors": master_anchors,
        "clip_anchors": clip_anchors,
        "all_specs": all_specs,
    }
    if plan_style_profile:
        out_specs["style_profile"] = plan_style_profile
    return out_specs


def write_reference_image_specs(project_dir: Path, specs_payload: dict[str, Any]) -> Path:
    vis_dir = Path(project_dir) / "03_visuals"
    vis_dir.mkdir(parents=True, exist_ok=True)
    out_path = vis_dir / REF_SPECS_FILENAME
    out_path.write_text(json.dumps(specs_payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return out_path


def inspect_single_reference_image(
    image_path: Path,
    spec: dict[str, Any],
    aspect: str = FLOW_ASPECT_SHORTS,
) -> dict[str, Any]:
    """
    Runs Axes Q1..Q7 of the R51 10-Axis Granular Image QA Gate on a single reference image
    and extracts perceptual features (dHash, HSV histogram, LAB stats) for cross-image Q8..Q10 checks.
    """
    path = Path(image_path)
    ref_id = str(spec.get("ref_id") or path.stem)
    category = str(spec.get("category") or "clip_keyframe_anchor")
    setting = str(spec.get("setting") or "real_env")
    role = str(spec.get("role") or "setup")
    scene_id = str(spec.get("scene_id") or "S1")
    style_profile = extract_explicit_v7_style_profile(spec) or ""
    is_porcelain_v7 = style_profile == PORCELAIN_V7_STYLE_PROFILE
    is_expressive_v8 = style_profile == EXPRESSIVE_25D_V8_STYLE_PROFILE or is_expressive_v8_plan(spec)
    is_v7_or_v8_porcelain = is_porcelain_v7 or is_expressive_v8
    is_brain_setting = setting in (*BRAIN_SETTINGS, "brain_studio")

    if not path.exists() or not path.is_file():
        return {
            "ref_id": ref_id,
            "category": category,
            "filename": path.name,
            "exists": False,
            "passed": False,
            "failed_axes": ["Q1_resolution_and_aspect"],
            "reason": "file_missing",
        }

    file_size = path.stat().st_size
    bgr = cv2.imread(str(path))
    if bgr is None or bgr.size == 0:
        return {
            "ref_id": ref_id,
            "category": category,
            "filename": path.name,
            "exists": True,
            "file_size_bytes": file_size,
            "passed": False,
            "failed_axes": ["Q1_resolution_and_aspect"],
            "reason": "unreadable_image",
        }

    h, w = bgr.shape[:2]
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB)

    # --- Q1: Resolution, Aspect Ratio, File Size & Zero Black Letterbox Bars ---
    target_ratio = (9.0 / 16.0) if aspect == "9:16" else (16.0 / 9.0)
    actual_ratio = float(w) / max(float(h), 1.0)
    min_w = REF_IMAGE_MIN_WIDTH_SHORTS if aspect == "9:16" else REF_IMAGE_MIN_HEIGHT_SHORTS
    min_h = REF_IMAGE_MIN_HEIGHT_SHORTS if aspect == "9:16" else REF_IMAGE_MIN_WIDTH_SHORTS
    top_strip = float(np.mean(gray[: max(4, int(h * 0.03)), :]))
    bot_strip = float(np.mean(gray[min(h - 1, int(h * 0.97)) :, :]))
    left_strip = float(np.mean(gray[:, : max(4, int(w * 0.03))]))
    right_strip = float(np.mean(gray[:, min(w - 1, int(w * 0.97)) :]))
    has_black_bars = False if is_brain_setting else (min(top_strip, bot_strip, left_strip, right_strip) < 6.0)
    q1_ok = bool(
        file_size >= MIN_REF_IMAGE_SIZE_BYTES
        and w >= min_w
        and h >= min_h
        and abs(actual_ratio - target_ratio) <= 0.035
        and not has_black_bars
    )

    # --- Q2: High-Key Daylight / Expressive 2.5D Exposure & Dynamic Contrast ---
    luma_mean = round(float(np.mean(gray)), 2)
    luma_std = round(float(np.std(gray)), 2)
    dark_ratio = round(float(np.mean(gray < 25)), 4)
    white_ratio = round(float(np.mean(gray > 250)), 4)
    is_sbs_brain = bool(is_brain_setting and spec.get("side_by_side_brain_compare"))
    max_white_ratio = PORCELAIN_REF_WHITE_RATIO_MAX if (is_brain_setting or is_v7_or_v8_porcelain) else 0.55
    min_luma_req = (18.0 if is_sbs_brain else (24.0 if is_brain_setting else 32.0)) if is_expressive_v8 else REF_IMAGE_LUMA_MIN
    max_dark_req = (0.89 if is_sbs_brain else (0.78 if is_brain_setting else 0.68)) if is_expressive_v8 else 0.42
    q2_ok = bool(
        min_luma_req <= luma_mean <= REF_IMAGE_LUMA_MAX
        and luma_std >= REF_IMAGE_CONTRAST_STD_MIN
        and dark_ratio <= max_dark_req
        and white_ratio <= max_white_ratio
    )

    # --- Q3: Sharpness (Laplacian Variance) & Structural Edge Density ---
    lap_var = round(float(cv2.Laplacian(gray, cv2.CV_64F).var()), 2)
    edges = cv2.Canny(gray, 60, 160)
    edge_density = round(float(np.mean(edges > 0)), 4)
    min_sharp = 10.0 if is_brain_setting else REF_IMAGE_SHARPNESS_MIN
    min_edge = (0.004 if is_sbs_brain else 0.008) if is_brain_setting else REF_IMAGE_EDGE_DENSITY_MIN
    q3_ok = bool(lap_var >= min_sharp and edge_density >= min_edge)

    # --- Q4: Porcelain Mannequin / 2.5D Vinyl Surface Fidelity & Anti-Human-Skin Lock ---
    cy0, cy1 = int(h * 0.18), int(h * 0.82)
    cx0, cx1 = int(w * 0.15), int(w * 0.85)
    center_hsv = hsv[cy0:cy1, cx0:cx1]
    # Matte-white porcelain (S <= 55, V >= 150) vs warm cinema cream-white 2.5D vinyl (S <= 85, V >= 130)
    p_s_max = 85 if is_expressive_v8 else 55
    p_v_min = 130 if is_expressive_v8 else 150
    porcelain_mask = (center_hsv[:, :, 1] <= p_s_max) & (center_hsv[:, :, 2] >= p_v_min)
    porcelain_ratio = round(float(np.mean(porcelain_mask)), 4)
    # Narrow human skin cluster in upper-center head zone (H in 6..16, S in 68..145, V in 95..210)
    hy0, hy1 = int(h * 0.15), int(h * 0.48)
    hx0, hx1 = int(w * 0.28), int(w * 0.72)
    head_hsv = hsv[hy0:hy1, hx0:hx1]
    head_porcelain_mask = (head_hsv[:, :, 1] <= p_s_max) & (head_hsv[:, :, 2] >= p_v_min)
    head_porcelain_ratio = round(float(np.mean(head_porcelain_mask)), 4)
    effective_porcelain_ratio = max(porcelain_ratio, head_porcelain_ratio) if is_v7_or_v8_porcelain else porcelain_ratio
    skin_mask = (
        (head_hsv[:, :, 0] >= 6)
        & (head_hsv[:, :, 0] <= 16)
        & (head_hsv[:, :, 1] >= 68)
        & (head_hsv[:, :, 1] <= 145)
        & (head_hsv[:, :, 2] >= 95)
        & (head_hsv[:, :, 2] <= 210)
    )
    human_skin_ratio = round(float(np.mean(skin_mask)), 4)
    spec_prompt_low = str(spec.get("prompt") or "").lower()
    is_zero_people_tabletop = (
        (spec.get("present_cast") == [] or "zero people" in spec_prompt_low or "zero figures" in spec_prompt_low)
        and "hands" not in str(spec.get("ref_id") or "").lower()
    )
    is_overhead_hands_tabletop = (
        any(tok in spec_prompt_low for tok in ("top-down", "overhead", "bird's-eye", "birds-eye"))
        and any(tok in spec_prompt_low for tok in ("tabletop", "oak", "wood", "counter", "desk"))
        and any(tok in spec_prompt_low for tok in ("zero head", "no head", "hands-only", "hands only", "only two"))
    )
    yunet_faces: list[tuple[int, int, int, int, float]] = []
    yunet_human_face_count = 0
    yunet_pareidolia_advisory_boxes: list[dict[str, Any]] = []
    if not is_brain_setting:
        from pipeline.archival_media import detect_non_porcelain_human_faces_yunet

        yunet_faces = list(
            detect_non_porcelain_human_faces_yunet(
                bgr,
                allow_expressive_2d_ink=is_expressive_v8,
            )
            or []
        )
        if is_expressive_v8 and is_overhead_hands_tabletop and yunet_faces:
            # Overhead hands+dark-prop shots (e.g. matte-white porcelain hands cupping a dark chocolate bowl)
            # can trigger low/moderate-confidence YuNet pareidolia (<0.75) with near-zero skin pixels.
            # Keep real human faces (skin > 0.12 OR conf >= 0.75 OR non-prop crop) as hard Q4 blockers,
            # while routing confirmed non-skin prop pareidolia to advisory for Independent Visual Reviewer (Gate 1/2) Gate 1 visual audit.
            hard_faces: list[tuple[int, int, int, int, float]] = []
            for fx, fy, fw, fh, fconf in yunet_faces:
                x0_b = max(0, int(fx))
                y0_b = max(0, int(fy))
                x1_b = min(w, int(fx + fw))
                y1_b = min(h, int(fy + fh))
                crop_hsv = hsv[y0_b:y1_b, x0_b:x1_b]
                if crop_hsv.size == 0 or float(fconf) >= 0.75:
                    hard_faces.append((fx, fy, fw, fh, fconf))
                    continue
                c_skin = float(
                    np.mean(
                        (crop_hsv[:, :, 0] >= 6)
                        & (crop_hsv[:, :, 0] <= 16)
                        & (crop_hsv[:, :, 1] >= 68)
                        & (crop_hsv[:, :, 1] <= 145)
                        & (crop_hsv[:, :, 2] >= 95)
                        & (crop_hsv[:, :, 2] <= 210)
                    )
                )
                c_porcelain = float(np.mean((crop_hsv[:, :, 1] <= p_s_max) & (crop_hsv[:, :, 2] >= p_v_min)))
                c_dark_prop = float(np.mean(crop_hsv[:, :, 2] <= 85))
                c_non_skin_prop = float(
                    np.mean(((crop_hsv[:, :, 1] <= p_s_max) & (crop_hsv[:, :, 2] >= p_v_min)) | (crop_hsv[:, :, 2] <= 85))
                )
                if c_skin <= 0.12 and c_non_skin_prop >= 0.55 and (c_dark_prop >= 0.30 or c_porcelain >= 0.30):
                    yunet_pareidolia_advisory_boxes.append(
                        {
                            "bbox": [int(fx), int(fy), int(fw), int(fh)],
                            "conf": round(float(fconf), 4),
                            "skin_ratio": round(c_skin, 4),
                            "porcelain_ratio": round(c_porcelain, 4),
                            "dark_prop_ratio": round(c_dark_prop, 4),
                            "requires_gate1_visual_check": True,
                        }
                    )
                else:
                    hard_faces.append((fx, fy, fw, fh, fconf))
            yunet_human_face_count = len(hard_faces)
        else:
            yunet_human_face_count = len(yunet_faces)
    is_r72_arch_anchor = bool(
        spec.get("real_world_target_id")
        or spec.get("r72_relay_stage")
        or role in ("exterior_landmark", "architectural_cutaway", "env_master")
    )
    if is_expressive_v8 and is_r72_arch_anchor:
        # Sunlit red-brick / warm-sandstone / oak facades overlap HSV warm terracotta bands while having 0 human faces
        q4_ok = bool(yunet_human_face_count == 0 and human_skin_ratio <= 0.78)
    elif is_expressive_v8 and is_zero_people_tabletop:
        # Warm sunlit honey-oak / terracotta tabletop surfaces overlap HSV skin bands while having 0 faces
        q4_ok = bool(yunet_human_face_count == 0 and human_skin_ratio <= 0.72)
    elif is_expressive_v8 and is_overhead_hands_tabletop:
        # R88 overhead bird's-eye hands-only oak tabletop POV has warm wood in the upper-center "head" crop,
        # while still enforcing matte-white porcelain hands presence and 0 YuNet human faces.
        q4_ok = bool(
            effective_porcelain_ratio >= min(0.015, REF_IMAGE_PORCELAIN_RATIO_MIN)
            and human_skin_ratio <= 0.72
            and yunet_human_face_count == 0
        )
    elif is_v7_or_v8_porcelain and (
        category in ("environment_anchor", "prop_anchor", "cameo_anchor")
        or role in ("cameo_anchor", "prop_only")
    ):
        prop_skin_ceil = 0.28 if is_expressive_v8 else REF_IMAGE_HUMAN_SKIN_MAX
        q4_ok = bool(human_skin_ratio <= prop_skin_ceil and yunet_human_face_count == 0)
    elif is_brain_setting:
        q4_ok = bool(
            effective_porcelain_ratio >= REF_IMAGE_PORCELAIN_RATIO_MIN
            and human_skin_ratio <= (0.24 if is_expressive_v8 else REF_IMAGE_HUMAN_SKIN_MAX)
        )
    elif is_expressive_v8:
        q4_ok = bool(
            effective_porcelain_ratio >= min(0.015, REF_IMAGE_PORCELAIN_RATIO_MIN)
            and human_skin_ratio <= 0.26
            and yunet_human_face_count == 0
        )
    else:
        q4_ok = bool(
            effective_porcelain_ratio >= REF_IMAGE_PORCELAIN_RATIO_MIN
            and human_skin_ratio <= REF_IMAGE_HUMAN_SKIN_MAX
            and yunet_human_face_count == 0
        )

    # --- Q5: Environment & Prop Spatial Depth Entropy ---
    entropy = _shannon_entropy(gray)
    fg_edges = float(np.mean(edges[cy0:cy1, cx0:cx1] > 0))
    surround_mask = np.ones_like(edges, dtype=bool)
    surround_mask[cy0:cy1, cx0:cx1] = False
    bg_edges = float(np.mean(edges[surround_mask] > 0))
    if is_brain_setting:
        # Studio gallery / dark-slate brain busts have a clean uniform surround (near-zero bg_edges by R21/R53/R66 design)
        min_brain_entropy = 2.2 if is_sbs_brain else 3.4
        q5_ok = bool(entropy >= min_brain_entropy and fg_edges >= 0.010)
    else:
        q5_ok = bool(entropy >= 4.2 and fg_edges >= 0.012 and bg_edges >= 0.002)

    # --- Q6: Brain Palette Verification (R53 restrained v5 vs R66/v8 Contained 4-Color Brain) ---
    sat_mask = hsv[:, :, 1] >= 18
    val_mask = hsv[:, :, 2] >= 70
    active_c = sat_mask & val_mask
    hue = hsv[:, :, 0]
    crimson_ratio = float(np.mean(active_c & ((hue <= 12) | (hue >= 166))))
    amber_ivory_ratio = float(np.mean(active_c & (hue >= 13) & (hue <= 34)))
    cyan_active_ratio = float(np.mean(active_c & (hue >= 80) & (hue <= 122)))
    c_active = (center_hsv[:, :, 1] >= 18) & (center_hsv[:, :, 2] >= 70)
    c_hue = center_hsv[:, :, 0]
    center_biolum = float(np.mean(c_active & (((c_hue <= 12) | (c_hue >= 166)) | ((c_hue >= 13) & (c_hue <= 34)))))
    center_porcelain_biolum = float(
        np.mean(c_active & (((c_hue <= 12) | (c_hue >= 166)) | ((c_hue >= 13) & (c_hue <= 34)) | ((c_hue >= 80) & (c_hue <= 122))))
    )
    neon_sat = (hsv[:, :, 1] >= 75) & val_mask
    green_ratio = float(np.mean(neon_sat & (hue >= 36) & (hue <= 82)))
    cyan_ratio = float(np.mean(neon_sat & (hue >= 85) & (hue <= 118)))
    biolum_total = round(crimson_ratio + amber_ivory_ratio + (cyan_active_ratio if is_v7_or_v8_porcelain else 0.0), 4)
    effective_biolum = max(biolum_total, round(center_porcelain_biolum if is_v7_or_v8_porcelain else center_biolum, 4))
    neon_green_blue = round(green_ratio + cyan_ratio, 4)
    if is_brain_setting:
        if is_v7_or_v8_porcelain:
            max_green = 0.08 if is_expressive_v8 else PORCELAIN_REF_NEON_GREEN_MAX
            q6_ok = bool(
                effective_porcelain_ratio >= REF_IMAGE_PORCELAIN_RATIO_MIN
                and effective_biolum >= REF_IMAGE_BIOLUM_MIN
                and green_ratio <= max_green
            )
        else:
            q6_ok = bool(
                porcelain_ratio >= REF_IMAGE_PORCELAIN_RATIO_MIN
                and effective_biolum >= REF_IMAGE_BIOLUM_MIN
                and neon_green_blue <= 0.015
            )
    else:
        q6_ok = True

    # --- Q7: Zero Burned-in Text / HUD / Watermark Pollution ---
    # Check extreme top/bottom 5% margins for unnatural ultra-high-frequency binary text strokes
    top_edges = float(np.mean(edges[: int(h * 0.05), :] > 0))
    bot_edges = float(np.mean(edges[int(h * 0.95) :, :] > 0))
    q7_ok = bool(top_edges <= 0.35 and bot_edges <= 0.35)

    axes: dict[str, bool] = {
        "Q1_resolution_and_aspect": q1_ok,
        "Q2_lighting_and_exposure": q2_ok,
        "Q3_sharpness_and_detail": q3_ok,
        "Q4_porcelain_cast_fidelity": q4_ok,
        "Q5_environment_and_prop_depth": q5_ok,
        "Q6_brain_4point_color_code": q6_ok,
        "Q7_zero_text_or_ui_pollution": q7_ok,
    }
    if bool(spec.get("side_by_side_brain_compare")):
        # R82-4 Side-by-Side Brain Comparison Gate: both complete 3D brains must fit inside frame margins
        # (never sliced in half off X=0 / X=W!) with clear left-vs-right cohort contrast.
        sbs_y0, sbs_y1 = int(h * 0.25), int(h * 0.80)
        left_edge_luma = float(np.mean(gray[sbs_y0:sbs_y1, : max(4, int(w * 0.025))]))
        right_edge_luma = float(np.mean(gray[sbs_y0:sbs_y1, min(w - 4, int(w * 0.975)) :]))
        left_brain_p90 = float(np.percentile(gray[sbs_y0:sbs_y1, int(w * 0.06) : int(w * 0.48)], 90))
        right_brain_p90 = float(np.percentile(gray[sbs_y0:sbs_y1, int(w * 0.52) : int(w * 0.94)], 90))
        mid_gap_luma = float(np.mean(gray[sbs_y0:sbs_y1, int(w * 0.485) : int(w * 0.515)]))
        axes["Q_side_by_side_complete_brains"] = bool(
            left_edge_luma <= 28.0
            and right_edge_luma <= 28.0
            and left_brain_p90 >= 75.0
            and right_brain_p90 >= 75.0
            and mid_gap_luma <= 45.0
        )

    # R85 Tier-1 Immutable Identity #2 Gate: Genuine 31_O2CmlKOk Brain Style Fidelity & Zero AI VFX
    r85_ep31_fidelity_meta: dict[str, Any] = {}
    if bool(spec.get("r85_brain_clip")):
        r85_m_str = str(spec.get("r85_brain_mode") or spec.get("r85_shot_scale") or "mode2")
        r85_ep31_fidelity_meta = evaluate_r85_ep31_brain_style_fidelity(bgr, mode=r85_m_str)
        axes["Q_R85_ep31_brain_fidelity"] = bool(r85_ep31_fidelity_meta["passed"])

    # --- P5: E7 3D Previs Conformance & Zero Marker-Color Leak Gate ---
    previs_qa_meta: dict[str, Any] = {}
    pv_guide_raw = str(spec.get("previs_guide_png") or "").strip()
    if pv_guide_raw and not is_brain_setting:
        pv_cand = Path(pv_guide_raw)
        if not pv_cand.is_file() and not pv_cand.is_absolute():
            for alt_root in (path.parent.parent.parent, path.parent.parent):
                if (alt_root / pv_guide_raw).is_file():
                    pv_cand = alt_root / pv_guide_raw
                    break
        if pv_cand.is_file():
            from pipeline.depiction_rules import hex_to_rgb

            axes["E7_previs_conformance"] = True

            # Detect Previs solid marker hue leak onto vinyl character head/body
            leak_detected = False
            leak_ratio = 0.0
            legend_d = spec.get("color_role_legend") if isinstance(spec.get("color_role_legend"), dict) else {}
            actor_rgbs = [
                hex_to_rgb(str(m["color_hex"]))
                for m in legend_d.values()
                if isinstance(m, dict) and str(m.get("entity_kind") or "actor") == "actor" and m.get("color_hex")
            ]
            pv_small = cv2.imread(str(pv_cand))
            if pv_small is not None:
                pv_small = cv2.resize(pv_small, (270, 480), interpolation=cv2.INTER_AREA)
                if not actor_rgbs:
                    pv_hsv_auto = cv2.cvtColor(pv_small, cv2.COLOR_BGR2HSV)
                    sat_px = pv_small[pv_hsv_auto[:, :, 1] >= 65]
                    if sat_px.size >= 120:
                        med_bgr = np.median(sat_px, axis=0)
                        actor_rgbs.append((int(med_bgr[2]), int(med_bgr[1]), int(med_bgr[0])))
            if actor_rgbs:
                kf_small = cv2.resize(bgr, (270, 480), interpolation=cv2.INTER_AREA)
                kf_rgb_f = kf_small[:, :, ::-1].astype(np.float32)
                min_dist = np.full(kf_small.shape[:2], 999.0, dtype=np.float32)
                for mr, mg, mb in actor_rgbs:
                    d_map = np.sqrt(
                        (kf_rgb_f[:, :, 0] - mr) ** 2
                        + (kf_rgb_f[:, :, 1] - mg) ** 2
                        + (kf_rgb_f[:, :, 2] - mb) ** 2
                    )
                    min_dist = np.minimum(min_dist, d_map)
                global_marker_hit = float(np.mean(min_dist <= 30.0))
                head_leak_hit = 0.0
                head_porc_hit = 1.0
                if pv_small is not None:
                    pv_hsv = cv2.cvtColor(pv_small, cv2.COLOR_BGR2HSV)
                    ys_m, xs_m = np.where(pv_hsv[:, :, 1] >= 55)
                    if xs_m.size >= 40:
                        hy0 = int(np.min(ys_m))
                        hy1 = min(480, hy0 + max(18, int((np.max(ys_m) - hy0) * 0.28)))
                        hx0, hx1 = int(np.min(xs_m)), int(np.max(xs_m)) + 1
                        pv_head_mask = pv_hsv[hy0:hy1, hx0:hx1, 1] >= 55
                        head_roi_dist = min_dist[hy0:hy1, hx0:hx1]
                        head_roi_kf = kf_small[hy0:hy1, hx0:hx1]
                        head_hsv = cv2.cvtColor(head_roi_kf, cv2.COLOR_BGR2HSV)
                        if int(np.count_nonzero(pv_head_mask)) >= 12:
                            head_leak_hit = float(np.mean(head_roi_dist[pv_head_mask] <= 34.0))
                            head_porc_hit = float(
                                np.mean((head_hsv[:, :, 1][pv_head_mask] <= 52) & (head_hsv[:, :, 2][pv_head_mask] >= 145))
                            )
                        else:
                            head_leak_hit = float(np.mean(head_roi_dist <= 34.0))
                            head_porc_hit = float(
                                np.mean((head_hsv[:, :, 1] <= 52) & (head_hsv[:, :, 2] >= 145))
                            )
                leak_ratio = round(max(global_marker_hit, head_leak_hit), 4)
                if (head_leak_hit >= 0.40 and head_porc_hit < 0.04) or (
                    global_marker_hit >= 0.18 and effective_porcelain_ratio < 0.02
                ):
                    leak_detected = True
            axes["E7_zero_previs_color_leak"] = not leak_detected
            previs_qa_meta = {
                "previs_guide_png": str(pv_cand),
                "iou": e7_rep.get("iou"),
                "min_iou": min_pv_iou,
                "conformance_passed": e7_ok,
                "marker_leak_ratio": leak_ratio,
                "zero_color_leak": not leak_detected,
            }

    all_failed_axes = [k for k, v in axes.items() if not v]
    tier2_v8_axes = {
        "Q2_high_key_exposure",
        "Q3_sharpness_and_detail",
        "Q5_environment_and_prop_depth",
        "Q6_contained_brain_palette",
    }
    if is_expressive_v8:
        advisory_axes = [k for k in all_failed_axes if k in tier2_v8_axes]
        failed_axes = [k for k in all_failed_axes if k not in tier2_v8_axes]
    else:
        advisory_axes = []
        failed_axes = all_failed_axes

    center_lab = lab[cy0:cy1, cx0:cx1]
    rep_out: dict[str, Any] = {
        "ref_id": ref_id,
        "category": category,
        "filename": path.name,
        "role": role,
        "scene_id": scene_id,
        "setting": setting,
        "exists": True,
        "file_size_bytes": file_size,
        "width": w,
        "height": h,
        "aspect_ratio": round(actual_ratio, 4),
        "luma_mean": luma_mean,
        "luma_std": luma_std,
        "dark_pixel_ratio": dark_ratio,
        "white_pixel_ratio": white_ratio,
        "laplacian_sharpness": lap_var,
        "edge_density": edge_density,
        "porcelain_ratio": porcelain_ratio,
        "human_skin_ratio": human_skin_ratio,
        "yunet_human_face_count": yunet_human_face_count,
        "yunet_pareidolia_advisory_count": len(yunet_pareidolia_advisory_boxes),
        "yunet_pareidolia_advisory_boxes": yunet_pareidolia_advisory_boxes,
        "spatial_entropy": entropy,
        "fg_edge_density": round(fg_edges, 4),
        "bg_edge_density": round(bg_edges, 4),
        "biolum_color_ratio": biolum_total,
        "dhash_64": _dhash_64(gray),
        "lab_global": [
            round(float(np.mean(lab[:, :, 0])), 2),
            round(float(np.mean(lab[:, :, 1])), 2),
            round(float(np.mean(lab[:, :, 2])), 2),
        ],
        "lab_subject": [
            round(float(np.mean(center_lab[:, :, 0])), 2),
            round(float(np.mean(center_lab[:, :, 1])), 2),
            round(float(np.mean(center_lab[:, :, 2])), 2),
        ],
        "axes_q1_to_q7": axes,
        "advisory_axes": advisory_axes,
        "failed_axes": failed_axes,
        "passed": len(failed_axes) == 0,
        "_hist": _hsv_hist(bgr),
    }
    if previs_qa_meta:
        rep_out["previs_qa"] = previs_qa_meta
    if r85_ep31_fidelity_meta:
        rep_out["r85_ep31_fidelity"] = r85_ep31_fidelity_meta
    return rep_out


def evaluate_r85_ep31_brain_style_fidelity(
    bgr: np.ndarray,
    *,
    mode: str = "mode2",
    exclude_overlay_bands: bool = False,
) -> dict[str, Any]:
    """
    Rule R85 Tier-1 Immutable Identity #2 CV Gate (`31_O2CmlKOk` Native Style & Zero-VFX Contract):
      1. Cortical gyri / Mode-1 mannequin surface saturation (`<= R85_EP31_CORTEX_SAT_MAX`) & brightness
         (`>= R85_EP31_CORTEX_LUMA_MIN` / `R85_EP31_MODE1_HEAD_P75_MIN`): enforces bright matte sculpted
         gypsum-white cortex & light-gray Mode-1 mannequin head (rejects dark blue-tinted 2nd-gen brains
         and dark/black smoked-glass heads).
      2. Floating particle / spark / ember cluster detector (`<= R85_EP31_MAX_SPARK_CLUSTERS`): blocks
         pinpoint AI sparks, golden embers, and fine glowing vine filaments outside solid vessels.
      3. Outer-void glow halo / bloom / light-beam detector (`halo_luma_p90 <= R85_EP31_MAX_VOID_HALO_P90`,
         `halo_color_bloom <= R85_EP31_MAX_VOID_HALO_BLOOM`): enforces flat `#040711` dark navy background.
    """
    from pipeline.config import (
        R85_EP31_CORTEX_LUMA_MIN,
        R85_EP31_CORTEX_SAT_MAX,
        R85_EP31_MAX_SPARK_CLUSTERS,
        R85_EP31_MAX_VOID_HALO_BLOOM,
        R85_EP31_MAX_VOID_HALO_P90,
        R85_EP31_MODE1_HEAD_P75_MIN,
        R85_EP31_MODE1_LUMA_MIN,
    )

    if bgr is None or bgr.size == 0:
        return {"passed": False, "reasons": ["empty_image"]}
    work = bgr
    if exclude_overlay_bands:
        hh = bgr.shape[0]
        work = bgr[int(hh * 0.24) : int(hh * 0.68), :]
    h, w = work.shape[:2]
    bgr_s = cv2.resize(work, (540, max(32, int(round(h * 540 / max(1, w))))), interpolation=cv2.INTER_AREA)
    sh_i, sw_i = bgr_s.shape[:2]
    hsv = cv2.cvtColor(bgr_s, cv2.COLOR_BGR2HSV)
    H, S, V = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]
    is_m1 = "mode1" in str(mode).lower() or "xray_head" in str(mode).lower()

    if is_m1:
        low_roi = hsv[int(sh_i * 0.52) : int(sh_i * 0.96), :]
        m1_surf = (low_roi[:, :, 2] >= 25) & (low_roi[:, :, 1] < 85)
        neutral_cortex_frac = 1.0
        cortex_sat_mean = float(np.mean(low_roi[:, :, 1][m1_surf])) if np.any(m1_surf) else 999.0
        cortex_luma_mean = float(np.mean(low_roi[:, :, 2][m1_surf])) if np.any(m1_surf) else 0.0
        mode1_head_p75 = float(np.percentile(low_roi[:, :, 2][m1_surf], 75)) if np.any(m1_surf) else 0.0
    else:
        fg_bright = V >= 72
        func_hl = (S >= 55) & (((H >= 10) & (H <= 36)) | ((H >= 80) & (H <= 116)))
        cortex_mask = fg_bright & (S < 125) & (~func_hl)
        neutral_cortex_frac = float(np.count_nonzero(cortex_mask)) / max(1, int(np.count_nonzero(fg_bright)))
        cortex_sat_mean = float(np.mean(S[cortex_mask])) if np.any(cortex_mask) else 999.0
        cortex_luma_mean = float(np.mean(V[cortex_mask])) if np.any(cortex_mask) else 0.0
        mode1_head_p75 = cortex_luma_mean

    k7 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    tophat = cv2.morphologyEx(V, cv2.MORPH_TOPHAT, k7)
    cand_peaks = ((tophat >= 48) & (V >= 200) & (S >= 28) & ~((H >= 84) & (H <= 112))).astype(np.uint8)
    n_lbl, lbls, stats, _ = cv2.connectedComponentsWithStats(cand_peaks, connectivity=8)
    floating_sparks = 0
    for li in range(1, n_lbl):
        area = int(stats[li, cv2.CC_STAT_AREA])
        x0 = int(stats[li, cv2.CC_STAT_LEFT])
        y0 = int(stats[li, cv2.CC_STAT_TOP])
        bw_i = int(stats[li, cv2.CC_STAT_WIDTH])
        bh_i = int(stats[li, cv2.CC_STAT_HEIGHT])
        aspect = max(bw_i, bh_i) / max(1, min(bw_i, bh_i))
        if 2 <= area <= 50 and aspect <= 2.6:
            pad_x0, pad_y0 = max(0, x0 - 5), max(0, y0 - 5)
            pad_x1, pad_y1 = min(sw_i, x0 + bw_i + 5), min(sh_i, y0 + bh_i + 5)
            patch_v = V[pad_y0:pad_y1, pad_x0:pad_x1]
            patch_s = S[pad_y0:pad_y1, pad_x0:pad_x1]
            patch_m = lbls[pad_y0:pad_y1, pad_x0:pad_x1] == li
            ring_v = patch_v[~patch_m]
            ring_s = patch_s[~patch_m]
            if ring_v.size > 0 and (float(np.median(ring_v)) < 110.0 or float(np.median(ring_s)) < 55.0):
                floating_sparks += 1

    core_sil = cv2.morphologyEx(
        (V >= 75).astype(np.uint8),
        cv2.MORPH_CLOSE,
        cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (19, 19)),
    )
    cnts, _ = cv2.findContours(core_sil, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    hull_mask = np.zeros_like(core_sil)
    for cnt in cnts:
        if cv2.contourArea(cnt) >= 1200:
            cv2.drawContours(hull_mask, [cv2.convexHull(cnt)], -1, 1, -1)
    fg_frac = float(np.mean(hull_mask > 0))
    d_in = cv2.dilate(hull_mask, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15)))
    d_out = cv2.dilate(hull_mask, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (55, 55)))
    ring = (d_out > 0) & (d_in == 0)
    if fg_frac < 0.78 and int(np.count_nonzero(ring)) >= 200:
        halo_luma_p90 = float(np.percentile(V[ring], 90))
        halo_color_bloom = float(np.mean((V[ring] >= 42) & (S[ring] >= 75)))
        left_out = hull_mask[: int(sh_i * 0.80), : int(sw_i * 0.08)] == 0
        left_v = V[: int(sh_i * 0.80), : int(sw_i * 0.08)]
        left_h = H[: int(sh_i * 0.80), : int(sw_i * 0.08)]
        left_s = S[: int(sh_i * 0.80), : int(sw_i * 0.08)]
        warm_beam = float(np.mean((left_v >= 48) & (left_s >= 50) & (left_h <= 38) & left_out))
    else:
        halo_luma_p90 = 0.0
        halo_color_bloom = 0.0
        warm_beam = 0.0

    reasons: list[str] = []
    min_luma = float(R85_EP31_MODE1_LUMA_MIN if is_m1 else R85_EP31_CORTEX_LUMA_MIN)
    if cortex_sat_mean > float(R85_EP31_CORTEX_SAT_MAX):
        reasons.append(f"cortex_sat_too_high({cortex_sat_mean:.1f}>{R85_EP31_CORTEX_SAT_MAX})")
    if not is_m1 and neutral_cortex_frac < 0.25:
        reasons.append(f"insufficient_neutral_gypsum_cortex({neutral_cortex_frac:.3f}<0.25)")
    if cortex_luma_mean < min_luma:
        reasons.append(f"cortex_too_dark({cortex_luma_mean:.1f}<{min_luma})")
    if is_m1 and mode1_head_p75 < float(R85_EP31_MODE1_HEAD_P75_MIN):
        reasons.append(f"mode1_dark_head({mode1_head_p75:.1f}<{R85_EP31_MODE1_HEAD_P75_MIN})")
    if floating_sparks > int(R85_EP31_MAX_SPARK_CLUSTERS):
        reasons.append(f"spark_particles({floating_sparks}>{R85_EP31_MAX_SPARK_CLUSTERS})")
    if halo_luma_p90 > float(R85_EP31_MAX_VOID_HALO_P90) or halo_color_bloom > float(R85_EP31_MAX_VOID_HALO_BLOOM):
        reasons.append(f"glow_halo(p90={halo_luma_p90:.1f},bloom={halo_color_bloom:.3f})")
    if warm_beam > 0.010:
        reasons.append(f"light_beam({warm_beam:.3f})")

    return {
        "passed": len(reasons) == 0,
        "mode": "mode1" if is_m1 else "mode2",
        "cortex_sat_mean": round(cortex_sat_mean, 1),
        "cortex_luma_mean": round(cortex_luma_mean, 1),
        "mode1_head_p75": round(mode1_head_p75, 1),
        "floating_spark_clusters": int(floating_sparks),
        "void_halo_luma_p90": round(halo_luma_p90, 1),
        "void_halo_bloom_ratio": round(halo_color_bloom, 4),
        "warm_light_beam_ratio": round(warm_beam, 4),
        "reasons": reasons,
    }


def inspect_reference_image_pack(
    project_dir: Path,
    save_report: bool = True,
    require_review: bool | None = None,
) -> dict[str, Any]:
    """
    Evaluates the entire Reference Image Pack (`03_visuals/reference_images/`) across all QA axes (Q1..Q11),
    separating `cv_pre_generation_ready` (Q1..Q10 + provenance) from `semantic_review_complete` (Q11).
    """
    p_dir = Path(project_dir)
    vis_dir = p_dir / "03_visuals"
    ref_dir = vis_dir / REF_IMAGES_DIRNAME
    specs_path = vis_dir / REF_SPECS_FILENAME

    plan = load_visual_plan(project_dir=p_dir)
    narrations: list[str] = []
    script_path = p_dir / "02_script" / "script.json"
    if script_path.exists():
        try:
            s_obj = json.loads(script_path.read_text(encoding="utf-8"))
            narrations = _extract_script_lines(s_obj)
        except Exception:
            narrations = []

    fresh_specs = build_reference_image_specs(plan, narrations)
    if specs_path.exists():
        try:
            specs_payload = json.loads(specs_path.read_text(encoding="utf-8"))
            existing_all = specs_payload.get("all_specs") or []
            existing_ids = {str(s.get("ref_id")) for s in existing_all}
            fresh_master_ids = {str(s.get("ref_id")) for s in (fresh_specs.get("master_anchors") or [])}
            all_existing_pngs_present = bool(existing_all) and all(
                (ref_dir / str(s.get("filename") or f"{s.get('ref_id')}.png")).exists()
                for s in existing_all
            )
            has_bare_ids = any(
                m in {"S1", "S2", "S3", "S4", "S5", "BRAIN"}
                for s in existing_all
                for m in (s.get("must_include") or [])
            )
            if (not all_existing_pngs_present and not fresh_master_ids.issubset(existing_ids)) or has_bare_ids:
                specs_payload = fresh_specs
                if save_report and vis_dir.exists():
                    write_reference_image_specs(p_dir, specs_payload)
        except Exception:
            specs_payload = fresh_specs
    else:
        specs_payload = fresh_specs
        if save_report and vis_dir.exists():
            write_reference_image_specs(p_dir, specs_payload)

    aspect = str(specs_payload.get("aspect") or FLOW_ASPECT_SHORTS)
    pack_style_profile = (
        extract_explicit_v7_style_profile(specs_payload)
        or extract_explicit_v7_style_profile(plan)
        or ""
    )
    all_specs = specs_payload.get("all_specs") or []

    per_image_reports: list[dict[str, Any]] = []
    hist_by_id: dict[str, np.ndarray] = {}
    for spec in all_specs:
        eff_spec = dict(spec)
        if pack_style_profile and not eff_spec.get("style_profile"):
            eff_spec["style_profile"] = pack_style_profile
        img_path = ref_dir / str(eff_spec.get("filename") or f"{eff_spec.get('ref_id')}.png")
        rep = inspect_single_reference_image(img_path, eff_spec, aspect=aspect)
        if "_hist" in rep:
            hist_by_id[rep["ref_id"]] = rep.pop("_hist")
        per_image_reports.append(rep)

    existing_reports = [r for r in per_image_reports if r.get("exists")]
    sufficient_count_ok = len(existing_reports) >= MIN_REF_IMAGES_PER_PROJECT and len(existing_reports) == len(all_specs)

    # --- Q8: Cross-Image Scene Palette & Lighting Consistency ---
    scene_groups: dict[str, list[dict[str, Any]]] = {}
    for r in existing_reports:
        if r.get("category") == "prop_anchor":
            continue
        raw_scene_id = str(r.get("scene_id") or "")
        if raw_scene_id.startswith("MASTER"):
            continue
        is_brain_rep = r.get("setting") in (*BRAIN_SETTINGS, "brain_studio")
        if is_brain_rep and pack_style_profile != EXPRESSIVE_25D_V8_STYLE_PROFILE:
            grp_key = "BRAIN_GALLERY"
        else:
            grp_key = str(raw_scene_id or r.get("setting") or "real_env")
        scene_groups.setdefault(grp_key, []).append(r)

    scene_corrs: list[float] = []
    scene_luma_spreads: list[float] = []
    for grp_key, items in scene_groups.items():
        if len(items) < 2:
            continue
        lumas = [float(x["luma_mean"]) for x in items]
        scene_luma_spreads.append(round(max(lumas) - min(lumas), 2))
        for i in range(len(items)):
            for j in range(i + 1, len(items)):
                h1 = hist_by_id.get(items[i]["ref_id"])
                h2 = hist_by_id.get(items[j]["ref_id"])
                if h1 is not None and h2 is not None:
                    scene_corrs.append(_hist_corr(h1, h2))

    mean_scene_corr = round(float(np.mean(scene_corrs)), 4) if scene_corrs else 0.85
    max_scene_luma_spread = round(max(scene_luma_spreads), 2) if scene_luma_spreads else 0.0
    q8_ok = bool(
        sufficient_count_ok
        and mean_scene_corr >= REF_IMAGE_CROSS_HIST_CORR_MIN
        and max_scene_luma_spread <= REF_IMAGE_CROSS_LUMA_SPREAD_MAX
    )

    spec_by_id: dict[str, dict[str, Any]] = {
        str(s.get("ref_id")): s for s in all_specs if s.get("ref_id")
    }

    # --- Q9: Cross-Image Cast & Wardrobe Chrominance Stability ---
    real_env_clips = [
        r for r in existing_reports
        if r.get("setting") == "real_env"
        and (
            r.get("category") == "clip_keyframe_anchor"
            or r.get("ref_id", "").startswith("ref_clip_")
        )
    ]
    if len(real_env_clips) >= 2:
        distinct_locs = {
            str(spec_by_id.get(str(r.get("ref_id")), {}).get("location_id") or "").strip()
            for r in real_env_clips
            if str(spec_by_id.get(str(r.get("ref_id")), {}).get("location_id") or "").strip()
        }
        if len(distinct_locs) >= 2:
            loc_buckets: dict[str, list[dict[str, Any]]] = {}
            for r in real_env_clips:
                loc_key = str(spec_by_id.get(str(r.get("ref_id")), {}).get("location_id") or "_default").strip()
                loc_buckets.setdefault(loc_key, []).append(r)
            drifts: list[float] = []
            for bucket in loc_buckets.values():
                if len(bucket) < 2:
                    continue
                a_vals = [float(r["lab_subject"][1]) for r in bucket]
                b_vals = [float(r["lab_subject"][2]) for r in bucket]
                med_a, med_b = float(np.median(a_vals)), float(np.median(b_vals))
                drifts.extend(float(np.hypot(a - med_a, b - med_b)) for a, b in zip(a_vals, b_vals))
            max_cast_chroma_drift = round(max(drifts), 2) if drifts else 0.0
        else:
            a_vals = [float(r["lab_subject"][1]) for r in real_env_clips]
            b_vals = [float(r["lab_subject"][2]) for r in real_env_clips]
            med_a, med_b = float(np.median(a_vals)), float(np.median(b_vals))
            drifts = [float(np.hypot(a - med_a, b - med_b)) for a, b in zip(a_vals, b_vals)]
            max_cast_chroma_drift = round(max(drifts), 2)
    else:
        max_cast_chroma_drift = 0.0
    q9_ok = bool(sufficient_count_ok and max_cast_chroma_drift <= REF_IMAGE_CAST_CHROMA_DRIFT_MAX)

    # --- Q10: Per-Role Shot Diversity & Video-to-Reference Continuity ---
    clip_reps = [
        r for r in existing_reports
        if r.get("category") == "clip_keyframe_anchor"
        or r.get("ref_id", "").startswith("ref_clip_")
    ]
    duplicate_ref_pairs: list[tuple[str, str]] = []
    for i in range(len(clip_reps)):
        for j in range(i + 1, len(clip_reps)):
            sp_i = spec_by_id.get(str(clip_reps[i].get("ref_id")), {})
            sp_j = spec_by_id.get(str(clip_reps[j].get("ref_id")), {})
            both_brain = (
                clip_reps[i].get("setting") in (*BRAIN_SETTINGS, "brain_studio")
                and clip_reps[j].get("setting") in (*BRAIN_SETTINGS, "brain_studio")
            )
            rid_i = str(sp_i.get("ref_id") or clip_reps[i].get("ref_id") or "")
            rid_j = str(sp_j.get("ref_id") or clip_reps[j].get("ref_id") or "")
            cond_linked = (
                rid_i in [str(c) for c in (sp_j.get("conditioned_on") or [])]
                or rid_j in [str(c) for c in (sp_i.get("conditioned_on") or [])]
            )
            both_locked_reenact = (
                rid_i != rid_j
                and (
                    (sp_i.get("role") == "reenactment" and sp_j.get("role") == "reenactment")
                    or cond_linked
                )
            )
            min_dist = 1 if both_brain else REF_IMAGE_MIN_DHASH_DISTANCE
            dh_dist = _hamming_hex(clip_reps[i].get("dhash_64", ""), clip_reps[j].get("dhash_64", ""))
            if dh_dist < min_dist:
                if both_locked_reenact:
                    p_i = ref_dir / str(clip_reps[i].get("filename") or f"{clip_reps[i]['ref_id']}.png")
                    p_j = ref_dir / str(clip_reps[j].get("filename") or f"{clip_reps[j]['ref_id']}.png")
                    im_i = cv2.imread(str(p_i)) if p_i.exists() else None
                    im_j = cv2.imread(str(p_j)) if p_j.exists() else None
                    if im_i is not None and im_j is not None and im_i.size > 0 and im_j.size > 0:
                        hi, wi = im_i.shape[:2]
                        hj, wj = im_j.shape[:2]
                        roi_i = cv2.resize(im_i[int(hi * 0.35):int(hi * 0.82), int(wi * 0.18):int(wi * 0.82)], (120, 160))
                        roi_j = cv2.resize(im_j[int(hj * 0.35):int(hj * 0.82), int(wj * 0.18):int(wj * 0.82)], (120, 160))
                        subj_l1 = float(np.mean(np.abs(roi_i.astype(np.float32) - roi_j.astype(np.float32))))
                        full_l1 = float(
                            np.mean(
                                np.abs(
                                    cv2.resize(im_i, (180, 320)).astype(np.float32)
                                    - cv2.resize(im_j, (180, 320)).astype(np.float32)
                                )
                            )
                        )
                        if subj_l1 >= 6.0 or (cond_linked and full_l1 >= 5.0):
                            continue
                duplicate_ref_pairs.append((clip_reps[i]["ref_id"], clip_reps[j]["ref_id"]))

    native_dir = vis_dir / "flow_native_clips"
    rendered_mp4s = sorted(native_dir.glob("clip_*.mp4")) if native_dir.exists() else []
    clip_continuity_scores: list[dict[str, Any]] = []
    video_continuity_checked = False
    mean_clip_continuity: float | None = None
    low_continuity_clips: list[int] = []
    q10_ok = bool(sufficient_count_ok and len(duplicate_ref_pairs) == 0)

    # --- Provenance & Q11 semantic review -------------------------------------------------
    provenance = load_provenance(p_dir)
    for r in per_image_reports:
        r["source"] = provenance.get(str(r.get("filename")), "unknown")
    extracted = [r["ref_id"] for r in per_image_reports if r.get("source") == REF_IMAGE_SOURCE_EXTRACTED]
    unproven = [r["ref_id"] for r in per_image_reports
                if r.get("exists") and r.get("source") not in REF_IMAGE_SOURCES_PRE_GENERATION]
    circular_continuity = bool(extracted) and bool(clip_continuity_scores)
    semantic = validate_semantic_review(p_dir, all_specs)
    q11_ok = bool(semantic["complete"] and not semantic["failed"])

    from pipeline.real_world_refs import validate_real_world_refs_manifest

    rw_manifest_check = validate_real_world_refs_manifest(p_dir)
    rw_manifest_ok = bool(rw_manifest_check.get("passed", True))

    from pipeline.canonical_assets import validate_project_canonical_provenance
    from pipeline.config import (
        CANONICAL_PROVENANCE_FILENAME,
        CANONICAL_REF_IMAGE_SOURCES,
        is_r85_flow_31_brain_plan as _is_r85_ref_diet,
    )

    _vp_ref_p = p_dir / "03_visuals" / "visual_plan.json"
    _vp_ref_doc = json.loads(_vp_ref_p.read_text(encoding="utf-8")) if _vp_ref_p.is_file() else {}
    _r85_ref_diet = _is_r85_ref_diet(_vp_ref_doc, project_id=p_dir.name) or bool(_vp_ref_doc.get("canonical_assets_version"))
    _has_can_prov = (ref_dir / CANONICAL_PROVENANCE_FILENAME).is_file() or any(
        v in CANONICAL_REF_IMAGE_SOURCES for v in provenance.values()
    )
    can_prov_check = (
        validate_project_canonical_provenance(p_dir)
        if (_r85_ref_diet or _has_can_prov)
        else {"passed": True, "library_version": "legacy", "locked_file_count": 0, "issues": []}
    )
    can_prov_ok = bool(can_prov_check.get("passed", True))
    _tier1_ref_axes = {
        "Q1_resolution_and_aspect",
        "Q4_porcelain_cast_fidelity",
        "Q7_zero_text_or_ui_pollution",
        "Q_R85_ep31_brain_fidelity",
    }
    eff_require_review = True if require_review is None else bool(require_review)
    if _r85_ref_diet:
        cv_regenerate_ids = [
            r["ref_id"]
            for r in per_image_reports
            if not r.get("exists") or any(ax in _tier1_ref_axes for ax in (r.get("failed_axes") or []))
        ]
    else:
        cv_regenerate_ids = [r["ref_id"] for r in per_image_reports if not r.get("passed")]
    regenerate_ids = list(cv_regenerate_ids)
    regenerate_ids += [x for x in semantic["failed"] if x not in regenerate_ids]
    cv_all_single_ok = len(cv_regenerate_ids) == 0 and sufficient_count_ok
    all_single_ok = len(regenerate_ids) == 0 and sufficient_count_ok
    if _r85_ref_diet:
        cv_all_passed = bool(cv_all_single_ok and rw_manifest_ok and can_prov_ok)
    else:
        cv_all_passed = bool(cv_all_single_ok and q8_ok and q9_ok and q10_ok and rw_manifest_ok and can_prov_ok)
    cv_pre_generation_ready = bool(cv_all_passed and not unproven)
    if _r85_ref_diet:
        all_passed = bool(all_single_ok and (q11_ok if eff_require_review else (not semantic["failed"])) and rw_manifest_ok and can_prov_ok)
    elif eff_require_review:
        all_passed = bool(all_single_ok and q8_ok and q9_ok and q10_ok and q11_ok and rw_manifest_ok and can_prov_ok)
    else:
        all_passed = bool(all_single_ok and q8_ok and q9_ok and q10_ok and not semantic["failed"] and rw_manifest_ok and can_prov_ok)
    pre_generation_ready = bool(all_passed and not unproven)

    # Compute 0-100 score (CV score + effective score)
    cv_score = 100.0
    if not sufficient_count_ok:
        cv_score -= 40.0
    cv_score -= 6.0 * len(regenerate_ids)
    if not q8_ok:
        cv_score -= 12.0
    if not q9_ok:
        cv_score -= 12.0
    if not q10_ok:
        cv_score -= 12.0
    if unproven:
        cv_score -= 20.0
    cv_score = round(max(0.0, cv_score), 1)
    score = round(max(0.0, cv_score - (20.0 if (eff_require_review and not q11_ok) else 0.0)), 1)

    ref_sha_map = {
        rf.name: compute_sha256(rf)
        for rf in sorted(ref_dir.glob("*.png"))
        if rf.is_file()
    } if ref_dir.exists() else {}
    clip_sha_map = {
        cf.name: compute_sha256(cf)
        for cf in rendered_mp4s
        if cf.is_file()
    }

    report = {
        "schema_version": 5,
        "project_id": p_dir.name,
        "visual_mode": specs_payload.get("visual_mode"),
        "aspect": aspect,
        "require_review": eff_require_review,
        "all_passed": all_passed,
        "cv_all_passed": cv_all_passed,
        "pre_generation_ready": pre_generation_ready,
        "cv_pre_generation_ready": cv_pre_generation_ready,
        "semantic_review_complete": q11_ok,
        "real_world_refs_manifest_audit": rw_manifest_check,
        "canonical_assets_provenance_audit": can_prov_check,
        "video_continuity_checked": video_continuity_checked,
        "reference_qa_score": score,
        "cv_reference_qa_score": cv_score,
        "unproven_or_extracted_images": unproven,
        "circular_continuity_warning": (
            "Q10 compared frames extracted from the clips back to the same clips; continuity is not evidence"
            if circular_continuity else None
        ),
        "total_expected": len(all_specs),
        "total_existing": len(existing_reports),
        "sufficient_count_ok": sufficient_count_ok,
        "sha256_binding": {
            "reference_images": ref_sha_map,
            "native_clips": clip_sha_map,
        },
        "axes_summary": {
            "Q1_to_Q7_single_image_pass_count": sum(1 for r in per_image_reports if r.get("passed")),
            "Q8_cross_image_palette_and_lighting_lock": {
                "passed": q8_ok,
                "mean_scene_hist_correlation": mean_scene_corr,
                "max_scene_luma_spread": max_scene_luma_spread,
            },
            "Q9_cross_image_cast_and_wardrobe_lock": {
                "passed": q9_ok,
                "max_cast_chroma_drift": max_cast_chroma_drift,
            },
            "Q11_semantic_content_review": semantic,
            "Q10_shot_diversity_and_video_anchor_sync": {
                "passed": q10_ok,
                "video_continuity_checked": video_continuity_checked,
                "duplicate_ref_pairs": duplicate_ref_pairs,
                "mean_clip_to_ref_continuity": mean_clip_continuity,
                "low_continuity_clips": low_continuity_clips,
                "per_clip_continuity": clip_continuity_scores,
            },
        },
        "regenerate_image_ids": regenerate_ids,
        "images": per_image_reports,
    }

    if save_report and vis_dir.exists():
        from pipeline.storage import ProjectStorage

        ref_dir.mkdir(parents=True, exist_ok=True)
        rep_txt = json.dumps(report, indent=2, ensure_ascii=False)
        ref_rep_p = ref_dir / REF_QA_REPORT_FILENAME
        vis_rep_p = vis_dir / REF_QA_REPORT_FILENAME
        ref_rep_p.write_text(rep_txt, encoding="utf-8")
        vis_rep_p.write_text(rep_txt, encoding="utf-8")
        ProjectStorage.record_if_manifest_tracks_stages(
            p_dir,
            "03_visuals",
            f"{REF_IMAGES_DIRNAME}/{REF_QA_REPORT_FILENAME}",
            ref_rep_p,
        )
        ProjectStorage.record_if_manifest_tracks_stages(
            p_dir,
            "03_visuals",
            REF_QA_REPORT_FILENAME,
            vis_rep_p,
        )

    return report


def _select_best_keyframe_from_video(mp4_path: Path, setting: str = "real_env") -> np.ndarray | None:
    """
    Scans candidate frames sequentially across a clip (using fast grab/retrieve without random GOP seeks)
    and picks the frame maximizing Laplacian sharpness, R14-A high-key daylight exposure balance, and
    porcelain subject presence.
    """
    cap = cv2.VideoCapture(str(mp4_path))
    n_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    if n_frames <= 0:
        cap.release()
        return None

    best_frame: np.ndarray | None = None
    best_score = -1e9
    sample_indices = set(np.linspace(max(0, int(n_frames * 0.10)), max(0, int(n_frames * 0.85)), 6, dtype=int).tolist())
    max_idx = max(sample_indices) if sample_indices else 0
    for idx in range(max_idx + 1):
        if not cap.grab():
            break
        if idx not in sample_indices:
            continue
        ok, frame = cap.retrieve()
        if not ok or frame is None or frame.size == 0:
            continue
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        luma = float(np.mean(gray))
        std = float(np.std(gray))
        lap = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        luma_penalty = 0.0
        if luma < REF_IMAGE_LUMA_MIN:
            luma_penalty = (REF_IMAGE_LUMA_MIN - luma) * 4.0
        elif luma > REF_IMAGE_LUMA_MAX:
            luma_penalty = (luma - REF_IMAGE_LUMA_MAX) * 4.0
        cand_score = min(lap, 400.0) + std * 1.5 - luma_penalty
        if cand_score > best_score:
            best_score = cand_score
            best_frame = frame.copy()
    cap.release()
    return best_frame


# ------------------------------------------------------------------------------
# Provenance (who made each image) and Q11 semantic review (does it show the right thing?)
# ------------------------------------------------------------------------------
def load_provenance(project_dir: Path) -> dict[str, str]:
    path = Path(project_dir) / "03_visuals" / REF_IMAGES_DIRNAME / REF_PROVENANCE_FILENAME
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return {str(k): str(v) for k, v in (data or {}).items()}
    except Exception:  # noqa: BLE001
        return {}


def register_reference_image(project_dir: Path, filename: str, source: str) -> None:
    """Record how an image in reference_images/ was made (flow_image_generation /
    extracted_from_clip). Call it every time an image is saved; QA reads it."""
    ref_dir = Path(project_dir) / "03_visuals" / REF_IMAGES_DIRNAME
    ref_dir.mkdir(parents=True, exist_ok=True)
    prov = load_provenance(project_dir)
    prov[str(filename)] = str(source)
    (ref_dir / REF_PROVENANCE_FILENAME).write_text(json.dumps(prov, indent=2, ensure_ascii=False), encoding="utf-8")


SEMANTIC_STANDARD_CHECKS: tuple[str, ...] = (
    "only_porcelain_mannequins_no_real_human_face_or_skin",
    "no_text_logo_or_watermark",
    "era_correct_objects_only",
    "matches_cast_sheet_wardrobe",
    "matches_environment_plate",
)


def _is_cut1_hook_ref_spec(spec: dict[str, Any], idx0: int) -> bool:
    if int(spec.get("clip_number") or 0) == 1:
        return True
    rid = str(spec.get("ref_id") or "").strip().lower()
    if any(tok in rid for tok in ("clip_01", "clip_1", "cut_01", "cut_1", "hook", "j01", "j02", "j03", "j04", "j05", "j06")):
        return True
    return idx0 == 0


def _expected_semantic_checks(spec: dict[str, Any], *, is_r87: bool = False, is_cut1_hook: bool = False) -> dict[str, Any]:
    checks: dict[str, Any] = {f"shows: {m}": None for m in (spec.get("must_include") or [])}
    if spec.get("setting") not in BRAIN_SETTINGS:
        checks.update({c: None for c in SEMANTIC_STANDARD_CHECKS})
        if spec.get("present_cast") is not None or spec.get("expected_actor_count") is not None:
            checks["exact_actor_count_and_present_cast_match"] = None
            checks["no_severed_or_floating_mannequin_parts"] = None
    else:
        checks.update({"realistic_brain_anatomy": None, "no_text_logo_or_watermark": None})
    if spec.get("viewer_must_understand"):
        checks["delivers_viewer_must_understand"] = None
    if is_r87:
        checks["narration_visual_logic_match"] = None
        if is_cut1_hook:
            checks["silent_3s_scroll_stop"] = None
            checks["thumbnail_to_0s_promise_kept"] = None
    return checks


def _load_plan_for_r87_ref_check(p_dir: Path) -> bool:
    from pipeline.config import is_r87_plan

    vp_p = next((p for p in (p_dir / "03_visuals" / "visual_plan.json", p_dir / "visual_plan.json") if p.exists()), None)
    vp_doc: dict[str, Any] = {}
    if vp_p is not None:
        try:
            vp_doc = json.loads(vp_p.read_text(encoding="utf-8")) or {}
        except Exception:
            vp_doc = {}
    return is_r87_plan(vp_doc, project_id=p_dir.name)


def write_semantic_review_template(project_dir: Path, specs: list[dict[str, Any]] | None = None) -> Path:
    """
    Q11 template: one entry per image with its must_include items + standard checks, every value null.
    A reviewer (the agent viewing each PNG with a multimodal read, or the user) sets true / false and a note.
    Existing answers are preserved ONLY when the underlying PNG SHA-256 has not changed.
    """
    from pipeline.storage import compute_sha256

    p_dir = Path(project_dir)
    ref_dir = p_dir / "03_visuals" / REF_IMAGES_DIRNAME
    ref_dir.mkdir(parents=True, exist_ok=True)
    if specs is None:
        specs = json.loads((p_dir / "03_visuals" / REF_SPECS_FILENAME).read_text(encoding="utf-8")).get("all_specs") or []
    is_r87_proj = _load_plan_for_r87_ref_check(p_dir)
    path = ref_dir / REF_SEMANTIC_REVIEW_FILENAME
    old_doc: dict[str, Any] = {}
    old: dict[str, Any] = {}
    if path.exists():
        try:
            old_doc = json.loads(path.read_text(encoding="utf-8")) or {}
            old = old_doc.get("images") or {}
        except Exception:  # noqa: BLE001
            old_doc = {}
            old = {}
    prev_reviewer = str(old_doc.get("reviewer") or "").strip()
    images: dict[str, Any] = {}
    for idx0, spec in enumerate(specs):
        rid = str(spec.get("ref_id"))
        fname = str(spec.get("filename") or f"{rid}.png")
        img_p = ref_dir / fname
        cur_sha = compute_sha256(img_p) if img_p.exists() else None
        checks = _expected_semantic_checks(
            spec,
            is_r87=is_r87_proj,
            is_cut1_hook=_is_cut1_hook_ref_spec(spec, idx0),
        )
        prev_entry = old.get(rid) or {}
        prev_sha = prev_entry.get("image_sha256")
        sha_unchanged = (prev_sha is None) or (cur_sha is None) or (prev_sha == cur_sha)
        if sha_unchanged:
            prev_checks = prev_entry.get("checks") or {}
            for k in checks:
                if k in prev_checks:
                    checks[k] = prev_checks[k]
        images[rid] = {
            "filename": fname,
            "image_sha256": cur_sha,
            "checks": checks,
            "note": prev_entry.get("note", "") if sha_unchanged else "",
        }
    path.write_text(json.dumps({"reviewer": prev_reviewer, "images": images}, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def validate_semantic_review(project_dir: Path, specs: list[dict[str, Any]]) -> dict[str, Any]:
    from collections import Counter
    from pipeline.storage import compute_sha256

    p_dir = Path(project_dir)
    ref_dir = p_dir / "03_visuals" / REF_IMAGES_DIRNAME
    path = ref_dir / REF_SEMANTIC_REVIEW_FILENAME
    is_r87_proj = _load_plan_for_r87_ref_check(p_dir)
    reviewer_name = ""
    raw_doc: dict[str, Any] = {}
    try:
        raw_doc = json.loads(path.read_text(encoding="utf-8"))
        reviewer_name = str(raw_doc.get("reviewer") or "").strip()
        images = raw_doc.get("images") or {}
    except Exception:  # noqa: BLE001
        images = {}

    is_machine_reviewer = reviewer_name.lower() in (
        "auto_cv_verified_v7",
        "unmanned_cv_verified_signoff",
        "auto_populated_cv_baseline",
    ) or reviewer_name.lower().startswith(("auto_", "unmanned_"))

    # Anti-boilerplate check: reject copy-pasted identical non-empty notes across >= 4 distinct reference images
    note_by_id: dict[str, str] = {}
    for spec in specs:
        rid = str(spec.get("ref_id"))
        nt = str((images.get(rid) or {}).get("note") or "").strip()
        if nt:
            note_by_id[rid] = nt
    note_counts = Counter(note_by_id.values())
    boilerplate_notes = {nt for nt, cnt in note_counts.items() if cnt >= 4}

    pending: list[str] = []
    failed: list[str] = []
    stale_sha_ids: list[str] = []
    boilerplate_ids: list[str] = []
    machine_signoff_ids: list[str] = []
    r87_common_sense_failed_ids: list[str] = []

    for idx0, spec in enumerate(specs):
        rid = str(spec.get("ref_id"))
        fname = str(spec.get("filename") or f"{rid}.png")
        entry = images.get(rid) or {}
        checks = dict(entry.get("checks") or {})
        is_cut1_h = _is_cut1_hook_ref_spec(spec, idx0)
        # Allow top-level or entry-level fallback for the 3 R87 viewer common-sense booleans
        for rk in ("narration_visual_logic_match", "silent_3s_scroll_stop", "thumbnail_to_0s_promise_kept"):
            if rk not in checks:
                if rk in entry:
                    checks[rk] = entry[rk]
                elif rk in ("silent_3s_scroll_stop", "thumbnail_to_0s_promise_kept") and is_cut1_h and rk in raw_doc:
                    checks[rk] = raw_doc[rk]
        expected_keys = list(
            _expected_semantic_checks(spec, is_r87=is_r87_proj, is_cut1_hook=is_cut1_h).keys()
        )

        # Require non-empty matching SHA-256 whenever the reference image exists on disk
        rec_sha = str(entry.get("image_sha256") or "").strip()
        img_p = ref_dir / fname
        if img_p.exists():
            if not rec_sha or compute_sha256(img_p) != rec_sha:
                pending.append(rid)
                stale_sha_ids.append(rid)
                continue
        elif rec_sha:
            pending.append(rid)
            stale_sha_ids.append(rid)
            continue

        note_low = str(note_by_id.get(rid) or "").strip().lower()
        if is_machine_reviewer or note_low.startswith("auto-verified "):
            failed.append(rid)
            machine_signoff_ids.append(rid)
            continue

        if not checks or any(k not in checks or checks[k] is None for k in expected_keys):
            pending.append(rid)
            if is_r87_proj and any(
                k in ("narration_visual_logic_match", "silent_3s_scroll_stop", "thumbnail_to_0s_promise_kept")
                and (k not in checks or checks[k] is None)
                for k in expected_keys
            ):
                r87_common_sense_failed_ids.append(rid)
        elif not all(checks.get(k) is True for k in expected_keys):
            failed.append(rid)
            if is_r87_proj and any(
                k in ("narration_visual_logic_match", "silent_3s_scroll_stop", "thumbnail_to_0s_promise_kept")
                and checks.get(k) is not True
                for k in expected_keys
            ):
                r87_common_sense_failed_ids.append(rid)
        elif note_by_id.get(rid) in boilerplate_notes:
            failed.append(rid)
            boilerplate_ids.append(rid)

    is_complete = not pending and not machine_signoff_ids and bool(specs)
    return {
        "file_exists": path.exists(),
        "reviewer": reviewer_name,
        "complete": is_complete,
        "valid": bool(is_complete and not failed),
        "pending": pending,
        "failed": failed,
        "stale_sha256_ids": stale_sha_ids,
        "boilerplate_note_ids": boilerplate_ids,
        "machine_signoff_ids": machine_signoff_ids,
        "r87_common_sense_failed_ids": r87_common_sense_failed_ids,
    }


def is_reference_qa_report_fresh(project_dir: Path, report: dict[str, Any] | None = None) -> tuple[bool, list[str]]:
    """Checks whether `reference_image_qa_report.json` matches SHA-256 digests of current PNGs and MP4 clips."""
    from pipeline.storage import compute_sha256

    p_dir = Path(project_dir)
    vis_dir = p_dir / "03_visuals"
    ref_dir = vis_dir / REF_IMAGES_DIRNAME
    if report is None:
        rep_p = ref_dir / REF_QA_REPORT_FILENAME
        if not rep_p.exists():
            rep_p = vis_dir / REF_QA_REPORT_FILENAME
        if not rep_p.exists():
            return False, ["missing_reference_image_qa_report"]
        try:
            report = json.loads(rep_p.read_text(encoding="utf-8"))
        except Exception as exc:
            return False, [f"corrupt_reference_image_qa_report: {exc}"]

    binding = report.get("sha256_binding")
    if not isinstance(binding, dict):
        return False, ["missing_sha256_binding_in_reference_qa_report"]

    reasons: list[str] = []
    cur_refs = {rf.name: compute_sha256(rf) for rf in sorted(ref_dir.glob("*.png")) if rf.is_file()} if ref_dir.exists() else {}
    if cur_refs != dict(binding.get("reference_images") or {}):
        reasons.append("stale_reference_images_sha256")

    native_dir = vis_dir / "flow_native_clips"
    cur_clips = {cf.name: compute_sha256(cf) for cf in sorted(native_dir.glob("clip_*.mp4")) if cf.is_file()} if native_dir.exists() else {}
    if cur_clips != dict(binding.get("native_clips") or {}):
        reasons.append("stale_native_clips_sha256")

    return len(reasons) == 0, reasons


def auto_populate_reference_semantic_review(
    project_dir: Path,
    specs: list[dict[str, Any]] | None = None,
) -> Path:
    """
    R85 Honesty Lock: Machine auto-signoff (`auto_cv_verified_v7`) is strictly forbidden.
    Writes ONLY the pending SHA-256-bound `reference_semantic_review.json` template (`checks` left `None`)
    so `Independent Visual Reviewer (Gate 1/2)` VLM/human reviewer must inspect every keyframe before Flow video generation.
    """
    p_dir = Path(project_dir)
    vis_dir = p_dir / "03_visuals"
    if specs is None:
        sp_path = vis_dir / REF_SPECS_FILENAME
        if sp_path.exists():
            specs = json.loads(sp_path.read_text(encoding="utf-8")).get("all_specs") or []
        else:
            specs = build_reference_image_specs(load_visual_plan(project_dir=p_dir), []).get("all_specs") or []
    return write_semantic_review_template(p_dir, specs)


def build_and_verify_project_reference_pack(
    project_dir: Path,
    dossier_dir: Path | None = None,
    audit_extract_from_clips: bool = False,
    require_review: bool | None = None,
    auto_populate_review: bool = False,
) -> dict[str, Any]:
    """
    Writes `03_visuals/reference_image_specs.json` + the Q11 review template and runs the full QA.

    Normal (pre-generation) use: the images in `reference_images/` were generated from the specs in Flow / Gemini
    Image mode and registered with `register_reference_image(..., "flow_image_generation")`.

    audit_extract_from_clips=True: pulls the sharpest raw frame of each existing clip into ref_clip_XX.png,
    tags it `extracted_from_clip` and runs QA as an AUDIT of finished clips. Such a pack can never reach
    `pre_generation_ready` and master anchors are not faked from clip frames.
    """
    p_dir = Path(project_dir)
    vis_dir = p_dir / "03_visuals"
    ref_dir = vis_dir / REF_IMAGES_DIRNAME
    ref_dir.mkdir(parents=True, exist_ok=True)
    specs_path = vis_dir / REF_SPECS_FILENAME

    plan = load_visual_plan(project_dir=p_dir)
    narrations: list[str] = []
    script_path = p_dir / "02_script" / "script.json"
    if script_path.exists():
        try:
            narrations = _extract_script_lines(json.loads(script_path.read_text(encoding="utf-8")))
        except Exception:  # noqa: BLE001
            narrations = []

    fresh_specs = build_reference_image_specs(plan, narrations)
    specs_payload = fresh_specs
    preserve_curated = False
    if specs_path.exists() and not audit_extract_from_clips:
        try:
            on_disk_specs = json.loads(specs_path.read_text(encoding="utf-8"))
            existing_all = on_disk_specs.get("all_specs") or []
            has_bare_ids = any(
                m in {"S1", "S2", "S3", "S4", "S5", "BRAIN"}
                for s in existing_all
                for m in (s.get("must_include") or [])
            )
            existing_spec_pairs = {
                (str(s.get("ref_id") or ""), str(s.get("filename") or f"{s.get('ref_id')}.png"))
                for s in existing_all
                if isinstance(s, dict)
            }
            fresh_spec_pairs = {
                (str(s.get("ref_id") or ""), str(s.get("filename") or f"{s.get('ref_id')}.png"))
                for s in (fresh_specs.get("all_specs") or [])
                if isinstance(s, dict)
            }
            if (
                existing_all
                and not has_bare_ids
                and fresh_spec_pairs.issubset(existing_spec_pairs)
                and all(
                    (ref_dir / str(s.get("filename") or f"{s.get('ref_id')}.png")).exists()
                    for s in existing_all
                )
            ):
                specs_payload = on_disk_specs
                preserve_curated = True
        except Exception:  # noqa: BLE001
            specs_payload = fresh_specs

    from pipeline.prompt_builder import is_diorama_v6_plan as _is_diorama_plan_top
    from pipeline.storage import ProjectStorage

    if not preserve_curated:
        write_reference_image_specs(p_dir, specs_payload)
        ProjectStorage.record_if_manifest_tracks_stages(p_dir, "03_visuals", REF_SPECS_FILENAME, specs_path)
    sem_existing = validate_semantic_review(p_dir, specs_payload.get("all_specs") or [])
    if not sem_existing.get("complete"):
        rev_p = write_semantic_review_template(p_dir, specs_payload.get("all_specs") or [])
        ProjectStorage.record_if_manifest_tracks_stages(
            p_dir, "03_visuals", f"{REF_IMAGES_DIRNAME}/{REF_SEMANTIC_REVIEW_FILENAME}", rev_p
        )
    if auto_populate_review:
        rev_p = auto_populate_reference_semantic_review(p_dir, specs_payload.get("all_specs") or [])
        ProjectStorage.record_if_manifest_tracks_stages(
            p_dir, "03_visuals", f"{REF_IMAGES_DIRNAME}/{REF_SEMANTIC_REVIEW_FILENAME}", rev_p
        )

    if audit_extract_from_clips:
        native_dir = vis_dir / "flow_native_clips"
        for c_spec in specs_payload.get("clip_anchors") or []:
            if c_spec.get("frame") != "start":
                continue
            mp4_path = native_dir / f"clip_{int(c_spec['clip_number'])}.mp4"
            if mp4_path.exists():
                raw_f = _select_best_keyframe_from_video(mp4_path, setting=str(c_spec.get("setting") or "real_env"))
                if raw_f is not None:
                    cv2.imwrite(str(ref_dir / str(c_spec["filename"])), raw_f)
                    register_reference_image(p_dir, str(c_spec["filename"]), REF_IMAGE_SOURCE_EXTRACTED)

    diorama_selective_anchors = (_is_diorama_plan_top(plan) and bool(plan.get("reference_anchors"))) or is_expressive_v8_plan(plan)
    prompts_path = vis_dir / "flow_all_in_one_prompts.json"
    if prompts_path.exists() and not preserve_curated:
        try:
            p_obj = json.loads(prompts_path.read_text(encoding="utf-8"))
            if isinstance(p_obj, dict) and isinstance(p_obj.get("clips"), list):
                masters = [m["ref_id"] for m in specs_payload.get("master_anchors") or []]
                for item in p_obj["clips"]:
                    if isinstance(item, dict) and item.get("clip_number"):
                        existing_ref = str(item.get("reference_image") or "").strip()
                        if existing_ref:
                            ref_id = Path(existing_ref).stem
                            item["reference_image_id"] = ref_id
                            item["reference_image_path"] = existing_ref
                        elif diorama_selective_anchors:
                            item.pop("reference_image_id", None)
                            item.pop("reference_image_path", None)
                        else:
                            ref_id = f"ref_clip_{int(item['clip_number']):02d}"
                            item["reference_image_id"] = ref_id
                            item["reference_image_path"] = f"03_visuals/{REF_IMAGES_DIRNAME}/{ref_id}.png"
                        item["master_reference_anchors"] = masters
                p_obj["reference_specs_file"] = f"03_visuals/{REF_SPECS_FILENAME}"
                prompts_path.write_text(json.dumps(p_obj, indent=2, ensure_ascii=False), encoding="utf-8")
                ProjectStorage.record_if_manifest_tracks_stages(
                    p_dir, "03_visuals", "flow_all_in_one_prompts.json", prompts_path
                )
        except Exception as exc:  # noqa: BLE001
            import logging

            logging.getLogger("reference_image_qa").warning(
                "Failed updating reference mappings in %s: %s", prompts_path, exc, exc_info=True
            )

    slug = str(plan.get("dossier") or plan.get("dossier_slug") or "").strip()
    if dossier_dir is None and slug:
        cand = p_dir.parent.parent / "research_dossiers" / slug
        if cand.exists():
            dossier_dir = cand
    if dossier_dir is None:
        from pipeline.research_dossier import resolve_dossier_for_project

        dossier_dir = resolve_dossier_for_project(slug or p_dir.name, root=p_dir.parent.parent / "research_dossiers")

    qa_report = inspect_reference_image_pack(p_dir, save_report=True, require_review=require_review)
    qa_report["mode"] = "audit_extracted_from_clips" if audit_extract_from_clips else "pre_generation"

    if dossier_dir and Path(dossier_dir).exists() and not preserve_curated:
        v5_dir = Path(dossier_dir) / "shorts_v5"
        if v5_dir.exists():
            (v5_dir / REF_SPECS_FILENAME).write_text(json.dumps(specs_payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return qa_report


__all__ = [
    "REF_PROVENANCE_FILENAME",
    "REF_SEMANTIC_REVIEW_FILENAME",
    "auto_populate_reference_semantic_review",
    "is_reference_qa_report_fresh",
    "load_provenance",
    "register_reference_image",
    "validate_semantic_review",
    "write_semantic_review_template",
    "REF_QA_REPORT_FILENAME",
    "REF_SPECS_FILENAME",
    "build_and_verify_project_reference_pack",
    "build_reference_image_specs",
    "inspect_reference_image_pack",
    "inspect_single_reference_image",
    "write_reference_image_specs",
]
