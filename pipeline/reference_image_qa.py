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
    REF_IMAGE_CAST_CHROMA_DRIFT_MAX,
    REF_IMAGE_CLIP_CONTINUITY_CORR_MIN,
    REF_IMAGE_CONTRAST_STD_MIN,
    REF_IMAGE_CROSS_HIST_CORR_MIN,
    REF_IMAGE_CROSS_LUMA_SPREAD_MAX,
    REF_IMAGE_EDGE_DENSITY_MIN,
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
)
from pipeline.scene_blueprint import (
    cast_for_shot,
    cast_lock_entries,
    cast_lock_sentence,
    key_visual_clip_numbers,
    key_visual_for_scene,
    still_frame_prompt,
    still_prefix,
)
from pipeline.flow_prompt_builder import (
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
    mode = str(plan.get("visual_mode") or "NEURO_BIOLOGY").upper()
    n_clips = len(narrations) if narrations else 10
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
    first_shot = shots.get(roles[0]) or next(iter(shots.values()), {}) if isinstance(shots, dict) else {}
    if not plan.get("real_environment") and isinstance(first_shot, dict) and first_shot.get("environment"):
        env_desc = str(first_shot["environment"]).strip()
    if not props_list and isinstance(first_shot, dict) and first_shot.get("prop_change"):
        hero_prop = str(first_shot["prop_change"]).strip()

    cranium_clause = (
        "with a smooth opaque matte-white porcelain head"
        if mode == "BEHAVIORAL_PSYCH"
        else "with a translucent frosted-glass cranium softly revealing the matte-white brain gyri inside"
    )

    sprefix = still_prefix(aspect)
    no_text = "Razor-sharp focus, bright even documentary light, no real human faces, no text, no watermark."
    cast_lock = cast_lock_sentence(plan)
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
            "prompt": sanitize_scene(
                f"{sprefix} Wide empty establishing view of {env_desc}, featuring {hero_prop}, no people. "
                f"Even natural daylight, deep depth of field. {no_text}"
            ),
            "must_include": [env_desc[:80], hero_prop[:60]],
        },
    ]
    for i, entry in enumerate(cast_lock_entries(plan)[:4]):
        master_anchors.append(
            {
                "ref_id": f"ref_cast_{entry['id']}",
                "category": "cast_anchor",
                "role": "cast_master",
                "scene_id": "MASTER_CAST",
                "setting": "real_env",
                "filename": f"ref_cast_{entry['id']}.png",
                "title": f"Cast sheet: {entry['id']} (full body, front view, inside the environment plate)",
                "generation_order": 2,
                "conditioned_on": ["ref_env_master"],
                "prompt": sanitize_scene(
                    f"{sprefix} Full-body front view of one articulated matte-white porcelain mannequin "
                    f"{cranium_clause}, {entry['id'].replace('_', ' ')} wearing {entry['look']}, standing in {env_desc}. "
                    f"Smooth porcelain joints, no human skin. {no_text}"
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
            "prompt": sanitize_scene(
                f"{sprefix} Close-up of {hero_prop} inside {env_desc}, exact period materials and textures. {no_text}"
            ),
            "must_include": [hero_prop[:80]],
        }
    )
    cast_ids = [m["ref_id"] for m in master_anchors if m["category"] == "cast_anchor"]

    # Per-clip START frames (+ KEY frame for the clip that must show the money shot), aligned with build_flow_prompts
    dummy_narrs = narrations if narrations and len(narrations) == n_clips else [
        "In this historical case, a single moment changed neuroscience forever." for _ in range(n_clips)
    ]
    built_clips = build_flow_prompts(plan, dummy_narrs, aspect=aspect)
    has_brain_clips = any(
        str(c.get("setting") or resolve_clip_setting(plan, str(c["role"]))) in BRAIN_SETTINGS
        for c in built_clips
    )
    if has_brain_clips:
        from pipeline.depiction_rules import BrainDepictionRule, PromptComposer

        first_brain_scene = next(
            (str(c.get("scene") or "") for c in built_clips if str(c.get("setting") or "") in BRAIN_SETTINGS),
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

    from pipeline.clip_qa_contract import extract_clip_required_entities

    key_clips = {min(nums) for nums in key_visual_clip_numbers(plan, built_clips).values() if nums}
    clip_anchors: list[dict[str, Any]] = []
    for c in built_clips:
        c_num = int(c["clip_number"])
        role = str(c["role"])
        setting = str(c.get("setting") or resolve_clip_setting(plan, role))
        scene_id = str(c.get("scene_id") or ("BRAIN" if setting in BRAIN_SETTINGS else "S1"))
        scene_txt = str(c.get("scene") or "").strip()
        is_brain = setting in BRAIN_SETTINGS
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
            clip_anchors.append(
                {
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
            )

    all_specs = master_anchors + clip_anchors
    return {
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
    setting = str(spec.get("setting") or "real_env")
    role = str(spec.get("role") or "setup")
    scene_id = str(spec.get("scene_id") or "S1")

    if not path.exists() or not path.is_file():
        return {
            "ref_id": ref_id,
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
    has_black_bars = min(top_strip, bot_strip, left_strip, right_strip) < 6.0
    q1_ok = bool(
        file_size >= MIN_REF_IMAGE_SIZE_BYTES
        and w >= min_w
        and h >= min_h
        and abs(actual_ratio - target_ratio) <= 0.035
        and not has_black_bars
    )

    # --- Q2: High-Key Daylight Exposure & Dynamic Contrast ---
    luma_mean = round(float(np.mean(gray)), 2)
    luma_std = round(float(np.std(gray)), 2)
    dark_ratio = round(float(np.mean(gray < 25)), 4)
    white_ratio = round(float(np.mean(gray > 250)), 4)
    q2_ok = bool(
        REF_IMAGE_LUMA_MIN <= luma_mean <= REF_IMAGE_LUMA_MAX
        and luma_std >= REF_IMAGE_CONTRAST_STD_MIN
        and dark_ratio <= 0.42
        and white_ratio <= (0.72 if setting in BRAIN_SETTINGS else 0.55)
    )

    # --- Q3: Sharpness (Laplacian Variance) & Structural Edge Density ---
    lap_var = round(float(cv2.Laplacian(gray, cv2.CV_64F).var()), 2)
    edges = cv2.Canny(gray, 60, 160)
    edge_density = round(float(np.mean(edges > 0)), 4)
    min_sharp = 10.0 if setting in BRAIN_SETTINGS else REF_IMAGE_SHARPNESS_MIN
    min_edge = 0.008 if setting in BRAIN_SETTINGS else REF_IMAGE_EDGE_DENSITY_MIN
    q3_ok = bool(lap_var >= min_sharp and edge_density >= min_edge)

    # --- Q4: Porcelain Mannequin Surface Fidelity & Anti-Human-Skin Lock ---
    cy0, cy1 = int(h * 0.18), int(h * 0.82)
    cx0, cx1 = int(w * 0.15), int(w * 0.85)
    center_hsv = hsv[cy0:cy1, cx0:cx1]
    # Matte-white / neutral light porcelain: low saturation (S <= 55), high value (V >= 150)
    porcelain_mask = (center_hsv[:, :, 1] <= 55) & (center_hsv[:, :, 2] >= 150)
    porcelain_ratio = round(float(np.mean(porcelain_mask)), 4)
    # Narrow human skin cluster in upper-center head zone (H in 6..18, S in 55..150, V in 90..215)
    hy0, hy1 = int(h * 0.15), int(h * 0.48)
    hx0, hx1 = int(w * 0.28), int(w * 0.72)
    head_hsv = hsv[hy0:hy1, hx0:hx1]
    skin_mask = (
        (head_hsv[:, :, 0] >= 6)
        & (head_hsv[:, :, 0] <= 16)
        & (head_hsv[:, :, 1] >= 68)
        & (head_hsv[:, :, 1] <= 145)
        & (head_hsv[:, :, 2] >= 95)
        & (head_hsv[:, :, 2] <= 210)
    )
    human_skin_ratio = round(float(np.mean(skin_mask)), 4)
    # Both conditions must hold. (The previous "skin <= max OR porcelain >= min" made the skin check a no-op:
    # a frame with a real human experimenter next to the mannequins passed Q4.)
    q4_ok = bool(porcelain_ratio >= REF_IMAGE_PORCELAIN_RATIO_MIN and human_skin_ratio <= REF_IMAGE_HUMAN_SKIN_MAX)

    # --- Q5: Environment & Prop Spatial Depth Entropy ---
    entropy = _shannon_entropy(gray)
    fg_edges = float(np.mean(edges[cy0:cy1, cx0:cx1] > 0))
    surround_mask = np.ones_like(edges, dtype=bool)
    surround_mask[cy0:cy1, cx0:cx1] = False
    bg_edges = float(np.mean(edges[surround_mask] > 0))
    if setting in BRAIN_SETTINGS:
        # Studio gallery / dark-slate brain busts have a clean uniform surround (near-zero bg_edges by R21/R53 design)
        q5_ok = bool(entropy >= 3.4 and fg_edges >= 0.010)
    else:
        q5_ok = bool(entropy >= 4.2 and fg_edges >= 0.012 and bg_edges >= 0.002)

    # --- Q6: Brain Restrained Subsurface Palette Verification (R53: zero neon green/blue, subtle warm/crimson) ---
    sat_mask = hsv[:, :, 1] >= 18
    val_mask = hsv[:, :, 2] >= 70
    active_c = sat_mask & val_mask
    hue = hsv[:, :, 0]
    crimson_ratio = float(np.mean(active_c & ((hue <= 12) | (hue >= 166))))
    amber_ivory_ratio = float(np.mean(active_c & (hue >= 13) & (hue <= 34)))
    neon_sat = (hsv[:, :, 1] >= 75) & val_mask
    green_ratio = float(np.mean(neon_sat & (hue >= 36) & (hue <= 82)))
    cyan_ratio = float(np.mean(neon_sat & (hue >= 85) & (hue <= 118)))
    biolum_total = round(crimson_ratio + amber_ivory_ratio, 4)
    neon_green_blue = round(green_ratio + cyan_ratio, 4)
    if setting in BRAIN_SETTINGS:
        q6_ok = bool(porcelain_ratio >= REF_IMAGE_PORCELAIN_RATIO_MIN and neon_green_blue <= 0.015)
    else:
        q6_ok = True

    # --- Q7: Zero Burned-in Text / HUD / Watermark Pollution ---
    # Check extreme top/bottom 5% margins for unnatural ultra-high-frequency binary text strokes
    top_edges = float(np.mean(edges[: int(h * 0.05), :] > 0))
    bot_edges = float(np.mean(edges[int(h * 0.95) :, :] > 0))
    q7_ok = bool(top_edges <= 0.35 and bot_edges <= 0.35)

    axes = {
        "Q1_resolution_and_aspect": q1_ok,
        "Q2_lighting_and_exposure": q2_ok,
        "Q3_sharpness_and_detail": q3_ok,
        "Q4_porcelain_cast_fidelity": q4_ok,
        "Q5_environment_and_prop_depth": q5_ok,
        "Q6_brain_4point_color_code": q6_ok,
        "Q7_zero_text_or_ui_pollution": q7_ok,
    }
    failed_axes = [k for k, v in axes.items() if not v]

    center_lab = lab[cy0:cy1, cx0:cx1]
    return {
        "ref_id": ref_id,
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
        "failed_axes": failed_axes,
        "passed": len(failed_axes) == 0,
        "_hist": _hsv_hist(bgr),
    }


def inspect_reference_image_pack(
    project_dir: Path,
    save_report: bool = True,
) -> dict[str, Any]:
    """
    Evaluates the entire Reference Image Pack (`03_visuals/reference_images/`) across all 10 QA axes (Q1..Q10),
    including cross-image scene palette lock (Q8), cast chrominance lock (Q9), and clip-to-reference
    visual continuity (Q10).
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
            narrations = [str(x) for x in (s_obj.get("clip_narrations") or [])]
        except Exception:
            narrations = []

    fresh_specs = build_reference_image_specs(plan, narrations)
    if specs_path.exists():
        try:
            specs_payload = json.loads(specs_path.read_text(encoding="utf-8"))
            existing_ids = {str(s.get("ref_id")) for s in (specs_payload.get("all_specs") or [])}
            fresh_master_ids = {str(s.get("ref_id")) for s in (fresh_specs.get("master_anchors") or [])}
            has_bare_ids = any(
                m in {"S1", "S2", "S3", "S4", "S5", "BRAIN"}
                for s in (specs_payload.get("all_specs") or [])
                for m in (s.get("must_include") or [])
            )
            if not fresh_master_ids.issubset(existing_ids) or has_bare_ids:
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
    all_specs = specs_payload.get("all_specs") or []

    per_image_reports: list[dict[str, Any]] = []
    hist_by_id: dict[str, np.ndarray] = {}
    for spec in all_specs:
        img_path = ref_dir / str(spec.get("filename") or f"{spec.get('ref_id')}.png")
        rep = inspect_single_reference_image(img_path, spec, aspect=aspect)
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
        is_brain_rep = r.get("setting") in BRAIN_SETTINGS
        grp_key = "BRAIN_GALLERY" if is_brain_rep else str(r.get("scene_id") or r.get("setting") or "real_env")
        if grp_key.startswith("MASTER"):
            continue
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

    # --- Q9: Cross-Image Cast & Wardrobe Chrominance Stability ---
    real_env_clips = [
        r for r in existing_reports
        if r.get("setting") == "real_env" and r.get("ref_id", "").startswith("ref_clip_")
    ]
    if len(real_env_clips) >= 2:
        a_vals = [float(r["lab_subject"][1]) for r in real_env_clips]
        b_vals = [float(r["lab_subject"][2]) for r in real_env_clips]
        med_a, med_b = float(np.median(a_vals)), float(np.median(b_vals))
        drifts = [float(np.hypot(a - med_a, b - med_b)) for a, b in zip(a_vals, b_vals)]
        max_cast_chroma_drift = round(max(drifts), 2)
    else:
        max_cast_chroma_drift = 0.0
    q9_ok = bool(sufficient_count_ok and max_cast_chroma_drift <= REF_IMAGE_CAST_CHROMA_DRIFT_MAX)

    # --- Q10: Per-Role Shot Diversity & Video-to-Reference Continuity ---
    clip_reps = [r for r in existing_reports if r.get("ref_id", "").startswith("ref_clip_")]
    duplicate_ref_pairs: list[tuple[str, str]] = []
    for i in range(len(clip_reps)):
        for j in range(i + 1, len(clip_reps)):
            both_brain = clip_reps[i].get("setting") in BRAIN_SETTINGS and clip_reps[j].get("setting") in BRAIN_SETTINGS
            min_dist = 1 if both_brain else REF_IMAGE_MIN_DHASH_DISTANCE
            if _hamming_hex(clip_reps[i].get("dhash_64", ""), clip_reps[j].get("dhash_64", "")) < min_dist:
                duplicate_ref_pairs.append((clip_reps[i]["ref_id"], clip_reps[j]["ref_id"]))

    from pipeline.clip_qa_contract import (
        CLIP_QA_CONTRACT_FILENAME,
        SAMPLE_WINDOWS_5PT,
        compile_clip_qa_contract,
        compute_sha256,
        compute_spatial_and_palette_continuity,
        sample_video_frames_5pt,
    )

    native_dir = vis_dir / "flow_native_clips"
    rendered_mp4s = sorted(native_dir.glob("clip_*.mp4")) if native_dir.exists() else []
    has_rendered_clips = len(rendered_mp4s) > 0
    clip_continuity_scores: list[dict[str, Any]] = []
    sampled_clip_cache: dict[int, list[tuple[float, np.ndarray]]] = {}

    if has_rendered_clips and clip_reps:
        c_file = vis_dir / CLIP_QA_CONTRACT_FILENAME
        try:
            c_obj = json.loads(c_file.read_text(encoding="utf-8")) if c_file.exists() else compile_clip_qa_contract(p_dir, save=False)
        except Exception:
            c_obj = {"clips": []}
        cond_by_clip = {
            int(cs["clip_number"]): dict(cs.get("conditioning_contract") or {})
            for cs in (c_obj.get("clips") or [])
            if cs.get("clip_number") is not None
        }

        for r in clip_reps:
            m_num = re.search(r"^ref_clip_(\d+)(?:_(start|key|end))?$", str(r["ref_id"]))
            if not m_num:
                continue
            c_idx = int(m_num.group(1))
            variant = m_num.group(2) or "start"
            is_brain_clip = r.get("setting") in BRAIN_SETTINGS
            cond_spec = cond_by_clip.get(c_idx, {})
            mp4_p = native_dir / f"clip_{c_idx}.mp4"
            ref_img_p = ref_dir / str(r.get("filename") or f"{r['ref_id']}.png")
            if not mp4_p.exists():
                clip_continuity_scores.append(
                    {
                        "clip_index": c_idx,
                        "ref_id": r["ref_id"],
                        "variant": variant,
                        "continuity_score": 0.0,
                        "hist_correlation": 0.0,
                        "passed": False,
                        "reason": "missing_clip_mp4",
                    }
                )
                continue
            ref_bgr = cv2.imread(str(ref_img_p)) if ref_img_p.exists() else None
            if ref_bgr is None or ref_bgr.size == 0:
                continue
            if c_idx not in sampled_clip_cache:
                _, sampled_frames = sample_video_frames_5pt(mp4_p, SAMPLE_WINDOWS_5PT)
                sampled_clip_cache[c_idx] = sampled_frames
            sampled_frames = sampled_clip_cache[c_idx]
            if not sampled_frames:
                clip_continuity_scores.append(
                    {
                        "clip_index": c_idx,
                        "ref_id": r["ref_id"],
                        "variant": variant,
                        "continuity_score": 0.0,
                        "hist_correlation": 0.0,
                        "passed": False,
                        "reason": "unreadable_clip_mp4",
                    }
                )
                continue

            start_1x = compute_spatial_and_palette_continuity(ref_bgr, sampled_frames[0][1], allow_interior_zoom=False)
            end_1x = compute_spatial_and_palette_continuity(ref_bgr, sampled_frames[-1][1], allow_interior_zoom=False)
            allow_zoom = bool(variant == "key" or start_1x["combined_score"] >= 0.78 or end_1x["combined_score"] >= 0.78)
            win_metrics = [
                compute_spatial_and_palette_continuity(ref_bgr, frm, allow_interior_zoom=allow_zoom)
                for _, frm in sampled_frames
            ]
            comb_vals = [m["combined_score"] for m in win_metrics]
            hsv_vals = [m["hsv_corr"] for m in win_metrics]
            adj_vals = [
                compute_spatial_and_palette_continuity(sampled_frames[k][1], sampled_frames[k + 1][1], allow_interior_zoom=False)["combined_score"]
                for k in range(len(sampled_frames) - 1)
            ]
            min_adj = min(adj_vals) if adj_vals else 1.0

            if variant == "key":
                agg_score = max(comb_vals[1:]) if len(comb_vals) > 1 else comb_vals[0]
                agg_hsv = max(hsv_vals[1:]) if len(hsv_vals) > 1 else hsv_vals[0]
                passed_cont = bool(agg_score >= 0.44 and agg_hsv >= 0.40)
            elif variant == "end":
                agg_score = min(comb_vals[-2:]) if len(comb_vals) >= 2 else comb_vals[-1]
                agg_hsv = min(hsv_vals[-2:]) if len(hsv_vals) >= 2 else hsv_vals[-1]
                passed_cont = bool(agg_score >= 0.46 and agg_hsv >= 0.42)
            else:
                agg_mode = str(cond_spec.get("aggregation_mode") or "strict_min_5pt")
                min_req = float(cond_spec.get("min_continuity_score", 0.52 if is_brain_clip else 0.46))
                agg_hsv = min(hsv_vals)
                if agg_mode == "pullback_windowed":
                    agg_score = max(min(comb_vals[:2]), min(comb_vals[-2:]))
                    passed_cont = bool(agg_score >= min_req and agg_hsv >= 0.42)
                else:
                    agg_score = min(comb_vals)
                    is_smooth_macro_zoom = bool(
                        is_brain_clip
                        and start_1x["combined_score"] >= 0.82
                        and agg_score >= 0.48
                        and (min_adj >= 0.46 or end_1x["combined_score"] >= 0.80)
                    )
                    is_smooth_real_pan = bool(
                        (not is_brain_clip)
                        and start_1x["combined_score"] >= 0.80
                        and agg_hsv >= 0.60
                        and min_adj >= 0.52
                        and agg_score >= 0.44
                    )
                    passed_cont = bool(
                        is_smooth_macro_zoom
                        or is_smooth_real_pan
                        or (agg_score >= min_req and agg_hsv >= 0.42)
                    )
            clip_continuity_scores.append(
                {
                    "clip_index": c_idx,
                    "ref_id": r["ref_id"],
                    "variant": variant,
                    "continuity_score": round(float(agg_score), 4),
                    "hist_correlation": round(float(agg_hsv), 4),
                    "window_scores_5pt": [round(float(v), 4) for v in comb_vals],
                    "passed": passed_cont,
                }
            )

    video_continuity_checked = len(clip_continuity_scores) > 0
    mean_clip_continuity: float | None = (
        round(float(np.mean([x["continuity_score"] for x in clip_continuity_scores])), 4)
        if video_continuity_checked
        else None
    )
    low_continuity_clips = sorted({int(x["clip_index"]) for x in clip_continuity_scores if not x["passed"]})
    if has_rendered_clips:
        q10_ok = bool(
            sufficient_count_ok
            and len(duplicate_ref_pairs) == 0
            and video_continuity_checked
            and len(low_continuity_clips) == 0
            and (mean_clip_continuity or 0.0) >= 0.46
        )
    else:
        # Pre-generation mode (no clip_*.mp4 rendered yet): verify shot diversity without faking 1.0 video continuity
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

    regenerate_ids = [r["ref_id"] for r in per_image_reports if not r.get("passed")]
    regenerate_ids += [x for x in semantic["failed"] if x not in regenerate_ids]
    all_single_ok = len(regenerate_ids) == 0 and sufficient_count_ok
    all_passed = bool(all_single_ok and q8_ok and q9_ok and q10_ok and q11_ok)
    # The only state that allows clip generation: every image passed Q1..Q11 AND was generated for the pack
    # (never cut out of an existing clip).
    pre_generation_ready = bool(all_passed and not unproven)

    # Compute 0-100 score
    score = 100.0
    if not sufficient_count_ok:
        score -= 40.0
    score -= 6.0 * len(regenerate_ids)
    if not q8_ok:
        score -= 12.0
    if not q9_ok:
        score -= 12.0
    if not q10_ok:
        score -= 12.0
    if not q11_ok:
        score -= 20.0
    if unproven:
        score -= 20.0
    score = round(max(0.0, score), 1)

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
        "all_passed": all_passed,
        "pre_generation_ready": pre_generation_ready,
        "video_continuity_checked": video_continuity_checked,
        "reference_qa_score": score,
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
        ref_dir.mkdir(parents=True, exist_ok=True)
        rep_txt = json.dumps(report, indent=2, ensure_ascii=False)
        (ref_dir / REF_QA_REPORT_FILENAME).write_text(rep_txt, encoding="utf-8")
        (vis_dir / REF_QA_REPORT_FILENAME).write_text(rep_txt, encoding="utf-8")

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
    """Record how an image in reference_images/ was made (flow_image_generation / gemini_image_generation /
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


def _expected_semantic_checks(spec: dict[str, Any]) -> dict[str, Any]:
    checks: dict[str, Any] = {f"shows: {m}": None for m in (spec.get("must_include") or [])}
    if spec.get("setting") not in BRAIN_SETTINGS:
        checks.update({c: None for c in SEMANTIC_STANDARD_CHECKS})
    else:
        checks.update({"realistic_brain_anatomy": None, "no_text_logo_or_watermark": None})
    return checks


def write_semantic_review_template(project_dir: Path, specs: list[dict[str, Any]] | None = None) -> Path:
    """
    Q11 template: one entry per image with its must_include items + standard checks, every value null.
    A reviewer (the agent viewing each PNG with a multimodal read, or the user) sets true / false and a note.
    Existing answers are preserved ONLY when the underlying PNG SHA-256 has not changed.
    """
    from pipeline.clip_qa_contract import compute_sha256

    p_dir = Path(project_dir)
    ref_dir = p_dir / "03_visuals" / REF_IMAGES_DIRNAME
    ref_dir.mkdir(parents=True, exist_ok=True)
    if specs is None:
        specs = json.loads((p_dir / "03_visuals" / REF_SPECS_FILENAME).read_text(encoding="utf-8")).get("all_specs") or []
    path = ref_dir / REF_SEMANTIC_REVIEW_FILENAME
    old: dict[str, Any] = {}
    if path.exists():
        try:
            old = json.loads(path.read_text(encoding="utf-8")).get("images") or {}
        except Exception:  # noqa: BLE001
            old = {}
    images: dict[str, Any] = {}
    for spec in specs:
        rid = str(spec.get("ref_id"))
        fname = str(spec.get("filename") or f"{rid}.png")
        img_p = ref_dir / fname
        cur_sha = compute_sha256(img_p) if img_p.exists() else None
        checks = _expected_semantic_checks(spec)
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
    path.write_text(json.dumps({"reviewer": "", "images": images}, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def validate_semantic_review(project_dir: Path, specs: list[dict[str, Any]]) -> dict[str, Any]:
    from collections import Counter
    from pipeline.clip_qa_contract import compute_sha256

    p_dir = Path(project_dir)
    ref_dir = p_dir / "03_visuals" / REF_IMAGES_DIRNAME
    path = ref_dir / REF_SEMANTIC_REVIEW_FILENAME
    try:
        images = json.loads(path.read_text(encoding="utf-8")).get("images") or {}
    except Exception:  # noqa: BLE001
        images = {}

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

    for spec in specs:
        rid = str(spec.get("ref_id"))
        fname = str(spec.get("filename") or f"{rid}.png")
        entry = images.get(rid) or {}
        checks = entry.get("checks") or {}
        expected_keys = list(_expected_semantic_checks(spec).keys())

        # Check SHA-256 freshness if recorded on entry and image exists on disk
        rec_sha = entry.get("image_sha256")
        img_p = ref_dir / fname
        if rec_sha and img_p.exists() and compute_sha256(img_p) != rec_sha:
            pending.append(rid)
            stale_sha_ids.append(rid)
            continue

        if not checks or any(k not in checks or checks[k] is None for k in expected_keys):
            pending.append(rid)
        elif not all(checks.get(k) is True for k in expected_keys):
            failed.append(rid)
        elif note_by_id.get(rid) in boilerplate_notes:
            failed.append(rid)
            boilerplate_ids.append(rid)

    return {
        "file_exists": path.exists(),
        "complete": not pending and bool(specs),
        "pending": pending,
        "failed": failed,
        "stale_sha256_ids": stale_sha_ids,
        "boilerplate_note_ids": boilerplate_ids,
    }


def is_reference_qa_report_fresh(project_dir: Path, report: dict[str, Any] | None = None) -> tuple[bool, list[str]]:
    """Checks whether `reference_image_qa_report.json` matches SHA-256 digests of current PNGs and MP4 clips."""
    from pipeline.clip_qa_contract import compute_sha256

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


def build_and_verify_project_reference_pack(
    project_dir: Path,
    dossier_dir: Path | None = None,
    audit_extract_from_clips: bool = False,
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

    plan = load_visual_plan(project_dir=p_dir)
    narrations: list[str] = []
    script_path = p_dir / "02_script" / "script.json"
    if script_path.exists():
        try:
            narrations = [str(x) for x in (json.loads(script_path.read_text(encoding="utf-8")).get("clip_narrations") or [])]
        except Exception:  # noqa: BLE001
            narrations = []

    specs_payload = build_reference_image_specs(plan, narrations)
    write_reference_image_specs(p_dir, specs_payload)
    write_semantic_review_template(p_dir, specs_payload.get("all_specs") or [])

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

    prompts_path = vis_dir / "flow_all_in_one_prompts.json"
    if prompts_path.exists():
        try:
            p_obj = json.loads(prompts_path.read_text(encoding="utf-8"))
            if isinstance(p_obj, dict) and isinstance(p_obj.get("clips"), list):
                masters = [m["ref_id"] for m in specs_payload.get("master_anchors") or []]
                for item in p_obj["clips"]:
                    if isinstance(item, dict) and item.get("clip_number"):
                        ref_id = f"ref_clip_{int(item['clip_number']):02d}"
                        item["reference_image_id"] = ref_id
                        item["reference_image_path"] = f"03_visuals/{REF_IMAGES_DIRNAME}/{ref_id}.png"
                        item["master_reference_anchors"] = masters
                p_obj["reference_specs_file"] = f"03_visuals/{REF_SPECS_FILENAME}"
                prompts_path.write_text(json.dumps(p_obj, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception:  # noqa: BLE001
            pass

    slug = str(plan.get("dossier") or "").strip()
    if dossier_dir is None and slug:
        cand = p_dir.parent.parent / "research_dossiers" / slug
        if cand.exists():
            dossier_dir = cand
    if dossier_dir is None:
        from pipeline.research_dossier import resolve_dossier_for_project

        dossier_dir = resolve_dossier_for_project(slug or p_dir.name, root=p_dir.parent.parent / "research_dossiers")

    try:
        from pipeline.clip_qa_contract import compile_clip_qa_contract

        compile_clip_qa_contract(p_dir, dossier_dir=dossier_dir, save=True)
    except Exception:  # noqa: BLE001
        pass

    qa_report = inspect_reference_image_pack(p_dir, save_report=True)
    qa_report["mode"] = "audit_extracted_from_clips" if audit_extract_from_clips else "pre_generation"

    if dossier_dir and Path(dossier_dir).exists():
        v5_dir = Path(dossier_dir) / "shorts_v5"
        if v5_dir.exists():
            (v5_dir / REF_SPECS_FILENAME).write_text(json.dumps(specs_payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return qa_report


__all__ = [
    "REF_PROVENANCE_FILENAME",
    "REF_SEMANTIC_REVIEW_FILENAME",
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
