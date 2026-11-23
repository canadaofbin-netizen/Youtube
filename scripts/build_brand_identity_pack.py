"""
ALL ABOUT BRAIN — Ep #31 Brand Identity Pack Builder & Safe-Zone Verifier.

Generates locked local channel identity assets (100% pure Pillow + OpenCV + NumPy,
zero network / Google Flow / CDP / browser / paid API calls):
  1. `logo_A_ep31_gypsum_cyan.png` (800x800 PNG, Priority #1)
  2. `logo_A_red_ep31_gypsum_crimson.png` (800x800 PNG, Crimson Vessel Variant)
  3. `logo_B_mode1_xray_skull.png` (800x800 PNG)
  4. `logo_C_split_cyan_crimson.png` (800x800 PNG)
  5. `banner_youtube_2560x1440.png` (2560x1440 PNG)
  6. `banner_youtube_2560x1440_red.png` (2560x1440 PNG, Crimson Variant)
  7. `brand_rebrand_comparison_sheet.jpg` (RGB high-res presentation board)
  8. `logo_A_cyan_vs_red_comparison.jpg` (RGB 800px 1:1 Cyan vs Crimson comparison board)
  9. `logo_A_ted_red_bg_cyan_brain.png` (800x800 PNG, TED Red #E62B1E BG + Ep #31 Cyan Brain)
 10. `logo_A_crimson_studio_bg_cyan_brain.png` (800x800 PNG, Deep Studio Crimson BG + Ep #31 Cyan Brain)
 11. `logo_ted_red_bg_comparison.jpg` (RGB 800px 1:1 TED Red vs Deep Studio Crimson comparison board)
 12. `banner_youtube_2560x1440_matrix_10slice_A_cyan.png` (2560x1440 PNG, 10-Slice Exploded Matrix Cyan)
 13. `banner_youtube_2560x1440_matrix_10slice_B_dual.png` (2560x1440 PNG, 10-Slice Center-Window Cyan/TED-Red)
 14. `banner_matrix_10slice_comparison.jpg` (RGB 2560x423 & Desktop/Mobile/TV TED-Red Avatar Harmony Sheet)
 15. `banner_youtube_2560x1440_crimson_echo_A_lateral.png` (2560x1440 PNG, Centered Whole A02 Lateral Brain + Cyan Echoes)
 16. `banner_youtube_2560x1440_crimson_echo_B_dorsal.png` (2560x1440 PNG, Centered Whole A03 Dorsal Brain + Cyan Echoes)
 17. `banner_crimson_echo_comparison.jpg` (RGB ECHO-A vs ECHO-B Desktop/Mobile/TV TED-Red Avatar Comparison)
 18. `banner_youtube_2560x1440_mri_glass_A_panes.png` (2560x1440 PNG, 9 MNI152 Coronal Oblique MRI Glass Panes)
 19. `banner_youtube_2560x1440_mri_glass_B_sculpted.png` (2560x1440 PNG, 9 MNI152 Oblique Sculpted Coronal Slabs)
 20. `banner_mri_glass_comparison.jpg` (RGB MRI-A vs MRI-B Desktop/Mobile/TV TED-Red Avatar Comparison)
 21. `banner_youtube_2560x1440_jh1_lightbox.png` (2560x1440 PNG, JH-1 Midnight Lab x MRI Lightbox Cinema Banner)
 22. `banner_youtube_2560x1440_jh2_crimson_darkroom.png` (2560x1440 PNG, JH-2 Crimson Darkroom Specimen Case Cinema Banner)
 23. `banner_youtube_2560x1440_jh3_human_element_homage.png` (2560x1440 PNG, JH-3 THE HUMAN ELEMENT Faceless Glass Head Homage)
 24. `banner_youtube_2560x1440_jh4_fmri_tunnel.png` (2560x1440 PNG, JH-4 3T fMRI Scanner Tunnel Cinema Still)
 25. `banner_youtube_2560x1440_jh5_investigator_desk.png` (2560x1440 PNG, JH-5 Investigative Neuroscience Evidence Desk)
 26. `banner_jh5_collection_comparison.jpg` (RGB JH-1..JH-5 35mm Cinema Collection Desktop/Mobile/TV Comparison)
 27. `banner_youtube_2560x1440_jh2a_hologram_wave_stream.png` (2560x1440 PNG, JH2-A Crimson Darkroom + Wide Blue Brain Hologram Wave Stream)
 28. `banner_youtube_2560x1440_jh2b_hologram_multi_angle_beam.png` (2560x1440 PNG, JH2-B Crimson Darkroom + Wide 4-View Blue Hologram Beam)
 29. `banner_youtube_2560x1440_jh2c_hologram_mri_strip.png` (2560x1440 PNG, JH2-C Crimson Darkroom + 7-Slice MNI152 Blue Hologram Filmstrip)
 30. `banner_youtube_2560x1440_jh2d_hologram_echo_panorama.png` (2560x1440 PNG, JH2-D Crimson Darkroom + Wide Bullet-Time Blue Hologram Echoes)
 31. `banner_youtube_2560x1440_jh2e_hologram_cortical_horizon.png` (2560x1440 PNG, JH2-E Crimson Darkroom + Edge-to-Edge Blue Cortical Horizon)
 32. `banner_jh2_5opts_comparison.jpg` (RGB JH2-A..JH2-E Crimson Darkroom + Wide Blue Hologram Comparison)
 33. `manifest.json` (SHA-256 locks, safe-zone coords, exact text bounding boxes)

Usage:
  /home/canadaofbin/hermes-venv/bin/python -X utf8 scripts/build_brand_identity_pack.py
  /home/canadaofbin/hermes-venv/bin/python -X utf8 scripts/build_brand_identity_pack.py --check
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import functools
import hashlib
import json
import math
import os
from pathlib import Path
import sys
from typing import Any

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
CANONICAL_V1_DIR = WORKSPACE_ROOT / "BCI_Shorts_Channel" / "canonical_assets" / "v1"
CANONICAL_V1_1_DIR = WORKSPACE_ROOT / "BCI_Shorts_Channel" / "canonical_assets" / "v1_1"
OUTPUT_DIR = WORKSPACE_ROOT / "BCI_Shorts_Channel" / "brand_assets" / "v2_ep31_rebrand"

FONTS_DIR = WORKSPACE_ROOT / "BCI_Shorts_Channel" / "assets" / "fonts"
PRIMARY_DISPLAY_FONT = FONTS_DIR / "AABCondensed-Black.ttf"
PRIMARY_BODY_FONT = FONTS_DIR / "Inter-Variable.ttf"
PATRICK_HAND_FONT = WORKSPACE_ROOT / "pipeline" / "assets" / "fonts" / "PatrickHand-Regular.ttf"
CAVEAT_FONT = WORKSPACE_ROOT / "pipeline" / "assets" / "fonts" / "Caveat-Variable.ttf"
MONO_FONT = Path("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf")
MNI152_ATLAS_NPZ = WORKSPACE_ROOT / "pipeline" / "assets" / "neuro_atlas_3d" / "neuro_atlas_mni152.npz"
FALLBACK_FONT = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")

SOURCE_ASSETS: dict[str, Path] = {
    "ep31_orig_mode2_lateral": CANONICAL_V1_DIR / "_reference_31_O2CmlKOk" / "ep31_orig_mode2_lateral_9x16.png",
    "ep31_orig_mode1_head": CANONICAL_V1_DIR / "_reference_31_O2CmlKOk" / "ep31_orig_mode1_head_9x16.png",
    "ep31_orig_mode2_dorsal": CANONICAL_V1_DIR / "_reference_31_O2CmlKOk" / "ep31_orig_mode2_dorsal_9x16.png",
    "a02_lateral_cand02": CANONICAL_V1_DIR / "A_brain" / "A02_mode2_whole_brain_lateral" / "cand_02.png",
    "a01_mode1_cand01": CANONICAL_V1_DIR / "A_brain" / "A01_mode1_translucent_head_lateral" / "cand_01.png",
    "a01_mode1_cand02": CANONICAL_V1_DIR / "A_brain" / "A01_mode1_translucent_head_lateral" / "cand_02.png",
    "a03_dorsal_cand01": CANONICAL_V1_DIR / "A_brain" / "A03_mode2_whole_brain_dorsal_topdown" / "cand_01.png",
}

# Strictly verified ZERO-FACE canonical sources for JH-1..JH-5
# (NEVER include B01-B15, G02, E06_laboratory_staged, E07_mri_suite_staged, A16, or A17)
JH5_SOURCE_ASSETS: dict[str, Path] = {
    "e01_lab_empty_01": CANONICAL_V1_DIR / "E_environments" / "E01_laboratory_empty" / "cand_01.png",
    "e01_lab_empty_02": CANONICAL_V1_DIR / "E_environments" / "E01_laboratory_empty" / "cand_02.png",
    "e02_mri_empty_01": CANONICAL_V1_DIR / "E_environments" / "E02_mri_suite_empty" / "cand_01.png",
    "d01_campus_drone_02": CANONICAL_V1_DIR / "D_drone_120ft" / "D01_drone_university_campus_120ft" / "cand_02.png",
    "a01_mode1_head_01": CANONICAL_V1_DIR / "A_brain" / "A01_mode1_translucent_head_lateral" / "cand_01.png",
    "a02_lateral_brain_02": CANONICAL_V1_DIR / "A_brain" / "A02_mode2_whole_brain_lateral" / "cand_02.png",
    "a03_dorsal_brain_01": CANONICAL_V1_DIR / "A_brain" / "A03_mode2_whole_brain_dorsal_topdown" / "cand_01.png",
    "a05_sulcal_vessel_01": CANONICAL_V1_DIR / "A_brain" / "A05_sulcal_vessel_macro" / "cand_01.png",
    "a07_midsagittal_01": CANONICAL_V1_DIR / "A_brain" / "A07_thalamus_brainstem_midsagittal" / "cand_01.png",
    "a13_tract_canyon_01": CANONICAL_V1_1_DIR / "A_brain_expansion" / "A13_1p_white_matter_tract_canyon" / "cand_01.png",
    "a18_coronal_hipp_01": CANONICAL_V1_1_DIR / "A_brain_expansion" / "A18_coronal_bilateral_hippocampus_ventricles" / "cand_01.png",
    "g01_mri_lightbox_01": CANONICAL_V1_1_DIR / "G_experimental_props" / "G01_mri_lightbox_dual_brain_scans" / "cand_01.png",
    "g08_desk_stimulus_01": CANONICAL_V1_1_DIR / "G_experimental_props" / "G08_geometric_stimulus_cards_and_sketchpads" / "cand_01.png",
    "h01_glass_case_02": CANONICAL_V1_1_DIR / "H_misconception_flip_props" / "H01_padlocked_acrylic_plaster_brain_case" / "cand_02.png",
}

JH5_FLOW_PROMPTS: dict[str, dict[str, str]] = {
    "jh1": {
        "title": "JH-1: Midnight Neuroscience Lab x MRI Lightbox",
        "aspect_ratio": "16:9",
        "filename": "banner_youtube_2560x1440_jh1_lightbox.png",
        "prompt": (
            "16:9 anamorphic 35mm documentary cinema still inside a dimly lit university neuroscience laboratory at midnight, "
            "no people, no faces. Deep misty teal shadows (#091822) across steel lab benches on the outer third, warm tungsten "
            "illuminated MRI lightbox in upper background glow (#C84B31), shallow depth of field foreground with subtle cyan neural "
            "reflection on brushed glass optics. Clean unobstructed dark atmospheric center third for wide title typography, "
            "Kodak Vision3 500T film grain, zero embedded text, zero cartoon elements."
        ),
    },
    "jh2": {
        "title": "JH-2: Crimson Darkroom Specimen Case",
        "aspect_ratio": "16:9",
        "filename": "banner_youtube_2560x1440_jh2_crimson_darkroom.png",
        "prompt": (
            "16:9 35mm cinema documentary still inside a shadowed crimson-lit archival specimen darkroom, no faces. Deep obsidian "
            "background (#07080B) washed in directional TED-red darkroom rim light (#B81D24) illuminating a brushed steel and glass "
            "museum specimen vitrine along the right third containing a pale matte gypsum anatomical brain sculpture with faint cyan "
            "vessel glow, misty dust motes in volumetric light beam, dark balanced center scrim zone, zero text, zero faces."
        ),
    },
    "jh3": {
        "title": "JH-3: THE HUMAN ELEMENT Homage — Faceless Glass Head + Misty Teal Horizon",
        "aspect_ratio": "16:9",
        "filename": "banner_youtube_2560x1440_jh3_human_element_homage.png",
        "prompt": (
            "16:9 widescreen 35mm anamorphic movie poster backdrop inspired by Johnny Harris The Human Element: atmospheric foggy "
            "teal coastal twilight horizon (#173E4F -> #3D8096 -> #6BABB2) with subtle misty ridge silhouette, right-centered "
            "faceless frosted obsidian-glass human cranium in profile housing an intricate glowing cyan neural connectome inside the "
            "cranial vault, kissed by warm salmon-crimson side key light (#E0523C) on the brow edge. Open misty teal outer left wing, "
            "zero facial features, zero text."
        ),
    },
    "jh4": {
        "title": "JH-4: 3T fMRI Scanner Tunnel Cinema Still",
        "aspect_ratio": "16:9",
        "filename": "banner_youtube_2560x1440_jh4_fmri_tunnel.png",
        "prompt": (
            "16:9 35mm documentary still down the center axis of a clinical 3-Tesla fMRI neuroimaging suite at night, completely "
            "empty room, zero people. Cool steel-teal ambient room light (#0E2634) contrasting against warm amber-crimson status LEDs "
            "along the circular scanner bore, soft translucent coronal MRI hippocampus glass slice hovering subtly in optical foreground "
            "focus, clean negative-space center across the bore horizon for typography, Kodak 35mm grain, zero text."
        ),
    },
    "jh5": {
        "title": "JH-5: Investigative Neuroscience Evidence Desk",
        "aspect_ratio": "16:9",
        "filename": "banner_youtube_2560x1440_jh5_investigator_desk.png",
        "prompt": (
            "16:9 overhead three-quarter 35mm documentary still of a late-night investigative neuroscience desk illuminated by one "
            "warm crimson-amber architect lamp, dark oiled walnut table with subtle laboratory glassware, coiled oscilloscope cables, "
            "unlabeled white matter tract macro print pinned beside a small dark plaster cortical study model on outer wings, deep "
            "uncluttered shadow across the center band for crisp cinema title legibility, zero readable words, zero hands or faces."
        ),
    },
}

JH2_5OPTS_FLOW_PROMPTS: dict[str, dict[str, str]] = {
    "jh2a": {
        "title": "JH2-A: Crimson Darkroom + Wide Blue Brain Hologram Wave Stream",
        "aspect_ratio": "16:9",
        "filename": "banner_youtube_2560x1440_jh2a_hologram_wave_stream.png",
        "prompt": (
            "16:9 35mm documentary cinema still inside a deep 660nm crimson safelight neuroimaging darkroom (#8F151A -> #1E0305), "
            "no people, no faces. Floating dead center in midair is a pure luminous translucent blue-cyan (#27D8FF) holographic wireframe brain "
            "streaming wide horizontally left and right into flowing glowing blue neural-fiber ribbons, oscillating EEG brainwave lines, "
            "subtle 1px horizontal laser scanlines, and micro blue light sparks across the full panorama, Kodak Vision3 500T film grain, zero text."
        ),
    },
    "jh2b": {
        "title": "JH2-B: Crimson Darkroom + Wide 4-View Blue Hologram Projection Beam",
        "aspect_ratio": "16:9",
        "filename": "banner_youtube_2560x1440_jh2b_hologram_multi_angle_beam.png",
        "prompt": (
            "16:9 35mm documentary still inside a 660nm crimson-lit neuroimaging darkroom with shallow f/1.4 bokeh, zero faces. "
            "A sleek wide horizontal glowing cyan (#27D8FF) holographic projection beam spans across the center horizontal band, "
            "projecting four translucent glowing blue holographic anatomical brain angles side by side (faceless cranial profile, lateral cortex, "
            "dorsal topdown, midsagittal thalamus/brainstem) connected by delicate horizontal scanlines and telemetry ticks, zero pink mud, zero text."
        ),
    },
    "jh2c": {
        "title": "JH2-C: Crimson Darkroom + 7-Slice MNI152 Blue Hologram Strip",
        "aspect_ratio": "16:9",
        "filename": "banner_youtube_2560x1440_jh2c_hologram_mri_strip.png",
        "prompt": (
            "16:9 35mm documentary cinema still inside a shadowed crimson 660nm darkroom, zero faces. Floating horizontally through the air "
            "is a wide ethereal translucent blue (#27D8FF) holographic MRI filmstrip showing seven sequential coronal brain cross-sections "
            "rendered purely as glowing cyan anatomical wireframe contours and subcortical nuclei light lines (no solid white panes), "
            "linked by horizontal laser projection lines and 1px scanlines, zero text."
        ),
    },
    "jh2d": {
        "title": "JH2-D: Crimson Darkroom + Pure Blue Hologram Bullet-Time Echo Panorama",
        "aspect_ratio": "16:9",
        "filename": "banner_youtube_2560x1440_jh2d_hologram_echo_panorama.png",
        "prompt": (
            "16:9 35mm documentary cinema still inside a moody 660nm TED-crimson darkroom vault, zero faces. Dead center floats a sharp translucent "
            "electric-blue (#27D8FF) holographic anatomical brain emitting ten symmetrical bullet-time horizontal holographic contour echoes "
            "and cyan scanline streaks stretching wide across the full horizontal darkroom horizon, Kodak 35mm film grain, zero text."
        ),
    },
    "jh2e": {
        "title": "JH2-E: Crimson Darkroom + Edge-to-Edge Blue Cortical Horizon",
        "aspect_ratio": "16:9",
        "filename": "banner_youtube_2560x1440_jh2e_hologram_cortical_horizon.png",
        "prompt": (
            "16:9 35mm cinema wide shot inside a crimson-safelight midnight neuroscience laboratory, zero faces. Stretching seamlessly edge-to-edge "
            "across the entire horizontal frame is a continuous luminous translucent blue (#27D8FF) holographic cortical fold and white-matter "
            "synaptic fiber horizon centered on a glowing holographic lateral brain core with laser scanlines, zero pasted panels, zero text."
        ),
    },
}

VOID_HEX = "#040711"
VOID_RGB = (4, 7, 17)
GLOW_HEX = "#0C1830"
GLOW_RGB = (12, 24, 48)
CYAN_HEX = "#27D8FF"
CYAN_RGB = (39, 216, 255)
CRIMSON_HEX = "#FF2525"
CRIMSON_RGB = (255, 37, 37)
CRIMSON_GLOW_HEX = "#200A10"
CRIMSON_GLOW_RGB = (32, 10, 16)
TED_RED_CENTER_HEX = "#E62B1E"
TED_RED_CENTER_RGB = (230, 43, 30)
TED_RED_EDGE_HEX = "#C81E15"
TED_RED_EDGE_RGB = (200, 30, 21)
STUDIO_CRIMSON_CENTER_HEX = "#DC2228"
STUDIO_CRIMSON_CENTER_RGB = (220, 34, 40)
STUDIO_CRIMSON_EDGE_HEX = "#8A0E16"
STUDIO_CRIMSON_EDGE_RGB = (138, 14, 22)
SUBHEAD_LIGHT_RGB = (226, 232, 240)

LOGO_SIZE = 800
BANNER_W = 2560
BANNER_H = 1440
YT_BANNER_UPLOAD_MAX_BYTES = 5_500_000
# YouTube universal desktop/mobile safe zone centered inside 2560x1440:
# x: (2560 - 1546) / 2 = 507 .. 2053
# y: int((1440 - 423) / 2) = 508 .. 931
SAFE_ZONE_BOX = (507, 508, 2053, 931)
DESKTOP_ZONE_BOX = (0, 508, 2560, 931)

OUTPUT_FILENAMES = (
    "logo_A_ep31_gypsum_cyan.png",
    "logo_A_red_ep31_gypsum_crimson.png",
    "logo_A_ted_red_bg_cyan_brain.png",
    "logo_A_crimson_studio_bg_cyan_brain.png",
    "logo_B_mode1_xray_skull.png",
    "logo_C_split_cyan_crimson.png",
    "banner_youtube_2560x1440.png",
    "banner_youtube_2560x1440_red.png",
    "banner_youtube_2560x1440_matrix_10slice_A_cyan.png",
    "banner_youtube_2560x1440_matrix_10slice_B_dual.png",
    "banner_youtube_2560x1440_crimson_echo_A_lateral.png",
    "banner_youtube_2560x1440_crimson_echo_B_dorsal.png",
    "banner_youtube_2560x1440_mri_glass_A_panes.png",
    "banner_youtube_2560x1440_mri_glass_B_sculpted.png",
    "banner_youtube_2560x1440_jh1_lightbox.png",
    "banner_youtube_2560x1440_jh2_crimson_darkroom.png",
    "banner_youtube_2560x1440_jh3_human_element_homage.png",
    "banner_youtube_2560x1440_jh4_fmri_tunnel.png",
    "banner_youtube_2560x1440_jh5_investigator_desk.png",
    "banner_youtube_2560x1440_jh2a_hologram_wave_stream.png",
    "banner_youtube_2560x1440_jh2b_hologram_multi_angle_beam.png",
    "banner_youtube_2560x1440_jh2c_hologram_mri_strip.png",
    "banner_youtube_2560x1440_jh2d_hologram_echo_panorama.png",
    "banner_youtube_2560x1440_jh2e_hologram_cortical_horizon.png",
    "brand_rebrand_comparison_sheet.jpg",
    "logo_A_cyan_vs_red_comparison.jpg",
    "logo_ted_red_bg_comparison.jpg",
    "banner_matrix_10slice_comparison.jpg",
    "banner_crimson_echo_comparison.jpg",
    "banner_mri_glass_comparison.jpg",
    "banner_jh5_collection_comparison.jpg",
    "banner_jh2_5opts_comparison.jpg",
    "banner_youtube_2560x1440_rc1_pure_type.png",
    "banner_youtube_2560x1440_rc2_type_plus_brain.png",
    "banner_youtube_2560x1440_rc3_stacked_3d_poster.png",
    "banner_ricks_clips_3opts_comparison.jpg",
    "banner_youtube_2560x1440_jh3_yt_upload.jpg",
    "brand_final_lock_preview.jpg",
)


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _atomic_save_image(img: Image.Image, target: Path, **save_kwargs: Any) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = target.parent / f".tmp_{os.getpid()}_{target.name}"
    try:
        img.save(tmp_path, **save_kwargs)
        os.replace(tmp_path, target)
    finally:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)


def _atomic_write_json(payload: dict[str, Any], target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = target.parent / f".tmp_{os.getpid()}_{target.name}"
    try:
        tmp_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        os.replace(tmp_path, target)
    finally:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)


def _load_font(
    primary_path: Path,
    size: int,
    *,
    weight: int | None = None,
) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for fp in (primary_path, FALLBACK_FONT):
        if fp.exists():
            try:
                font = ImageFont.truetype(str(fp), size=size)
                if fp == PRIMARY_BODY_FONT:
                    try:
                        opsz = max(14, min(32, int(size)))
                        wt = int(weight) if weight is not None else 500
                        font.set_variation_by_axes([opsz, wt])
                    except (AttributeError, OSError):
                        pass
                elif fp == CAVEAT_FONT:
                    try:
                        wt = max(400, min(700, int(weight) if weight is not None else 600))
                        font.set_variation_by_axes([wt])
                    except (AttributeError, OSError):
                        pass
                return font
            except OSError:
                continue
    return ImageFont.load_default()


def _extract_subject_rgba(
    image_path: Path,
    *,
    bg_threshold: float = 13.5,
    ramp_span: float = 16.0,
    feather_sigma: float = 1.25,
) -> tuple[np.ndarray, tuple[int, int, int, int]]:
    """
    Extract foreground subject from a dark navy studio void with smooth alpha masking.

    Uses border-sampled background estimation, blurred foreground score (immune to
    high HSV saturation on dark #040711 navy), exterior connected-component flood
    segmentation, and interior hole filling so dark sulcal/cranial shadows stay 100%
    opaque while outer edges feather smoothly to alpha=0 with zero rectangular seams.
    """
    bgr = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
    if bgr is None:
        raise FileNotFoundError(f"Failed to read source asset: {image_path}")
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB).astype(np.float32)
    h, w, _ = rgb.shape

    border_samples = np.concatenate(
        [
            rgb[:24].reshape(-1, 3),
            rgb[-24:].reshape(-1, 3),
            rgb[:, :24].reshape(-1, 3),
            rgb[:, -24:].reshape(-1, 3),
        ],
        axis=0,
    )
    bg_rgb = np.median(border_samples, axis=0)
    bg_luma = float(0.299 * bg_rgb[0] + 0.587 * bg_rgb[1] + 0.114 * bg_rgb[2])

    luma = 0.299 * rgb[:, :, 0] + 0.587 * rgb[:, :, 1] + 0.114 * rgb[:, :, 2]
    color_dist = np.linalg.norm(rgb - bg_rgb[None, None, :], axis=2)

    fg_score = np.maximum(luma - bg_luma, color_dist * 0.90)
    fg_score_smooth = cv2.GaussianBlur(fg_score, (5, 5), sigmaX=1.0, sigmaY=1.0)
    candidate_void = (fg_score_smooth < bg_threshold).astype(np.uint8)

    # Identify exterior connected void touching image perimeter
    _, labels = cv2.connectedComponents(candidate_void, connectivity=8)
    edge_labels = np.unique(
        np.concatenate([labels[0, :], labels[-1, :], labels[:, 0], labels[:, -1]])
    )
    edge_labels = edge_labels[edge_labels > 0]
    ext_void = np.isin(labels, edge_labels)

    # Keep only significant foreground components (remove tiny noise specks)
    fg_raw = (~ext_void).astype(np.uint8)
    n_fg, fg_labels, stats, _ = cv2.connectedComponentsWithStats(fg_raw, connectivity=8)
    min_area = max(1500, int(0.002 * h * w))
    solid_fg = np.zeros((h, w), dtype=np.uint8)
    for lbl in range(1, n_fg):
        if int(stats[lbl, cv2.CC_STAT_AREA]) >= min_area:
            solid_fg[fg_labels == lbl] = 1

    # Fill any enclosed dark interior holes (sulcal clefts, glass shadows)
    inv_fg = (1 - solid_fg).astype(np.uint8)
    _, hole_labels = cv2.connectedComponents(inv_fg, connectivity=4)
    hole_edge = np.unique(
        np.concatenate([hole_labels[0, :], hole_labels[-1, :], hole_labels[:, 0], hole_labels[:, -1]])
    )
    hole_edge = hole_edge[hole_edge > 0]
    solid_fg = (~np.isin(hole_labels, hole_edge)).astype(np.uint8)

    # Compute smooth outer perimeter transition via distance from exterior void
    dist_inside = cv2.distanceTransform(solid_fg, cv2.DIST_L2, 5)
    soft_ramp = np.clip((fg_score_smooth - (bg_threshold * 0.65)) / ramp_span, 0.0, 1.0)

    # Deep interior (> 5px inside silhouette) stays fully opaque; perimeter blends smoothly
    interior_lock = np.clip((dist_inside - 0.8) / 4.2, 0.0, 1.0)
    alpha = np.where(solid_fg > 0, np.maximum(interior_lock, soft_ramp * 0.94), 0.0)
    alpha = cv2.GaussianBlur(alpha.astype(np.float32), (0, 0), sigmaX=feather_sigma, sigmaY=feather_sigma)
    alpha = np.where(dist_inside > 5.5, 1.0, np.clip(alpha, 0.0, 1.0))
    alpha[solid_fg == 0] = 0.0

    # Decontaminate semi-transparent rim pixels from dark navy background tint
    a_safe = np.maximum(alpha, 0.18)[:, :, None]
    rgb_clean = np.where(
        (alpha[:, :, None] > 0.01) & (alpha[:, :, None] < 0.98),
        np.clip((rgb - (1.0 - alpha[:, :, None]) * bg_rgb[None, None, :]) / a_safe, 0.0, 255.0),
        rgb,
    )

    rgba = np.zeros((h, w, 4), dtype=np.uint8)
    rgba[:, :, :3] = np.clip(rgb_clean, 0.0, 255.0).astype(np.uint8)
    rgba[:, :, 3] = np.clip(alpha * 255.0, 0.0, 255.0).astype(np.uint8)

    ys, xs = np.where(rgba[:, :, 3] > 24)
    if len(xs) == 0 or len(ys) == 0:
        raise RuntimeError(f"Empty foreground extraction for {image_path}")
    bbox = (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1)
    return rgba, bbox


def _enhance_gypsum_and_cyan(rgba: np.ndarray, *, cyan_boost: float = 1.24, contrast_gain: float = 1.08) -> np.ndarray:
    """Boost cyan vascular vibrancy and crisp gypsum tonal separation for 32px legibility."""
    out = rgba.copy()
    rgb = out[:, :, :3].astype(np.float32)
    hsv = cv2.cvtColor(out[:, :, :3], cv2.COLOR_RGB2HSV).astype(np.float32)

    # Subtle contrast curve on gypsum luminance while preserving bright highlights
    luma = 0.299 * rgb[:, :, 0] + 0.587 * rgb[:, :, 1] + 0.114 * rgb[:, :, 2]
    centered = 128.0 + (rgb - 128.0) * contrast_gain
    rgb = np.where(luma[:, :, None] > 28.0, np.clip(centered, 0.0, 255.0), rgb)

    # Identify cyan/sky-blue vessels and nudge saturation/hue toward #27D8FF
    hue = hsv[:, :, 0]
    sat = hsv[:, :, 1]
    val = hsv[:, :, 2]
    cyan_w = (
        np.clip(1.0 - np.abs(hue - 97.0) / 18.0, 0.0, 1.0)
        * np.clip((sat - 45.0) / 60.0, 0.0, 1.0)
        * np.clip((val - 40.0) / 50.0, 0.0, 1.0)
    )
    hsv_boost = cv2.cvtColor(rgb.astype(np.uint8), cv2.COLOR_RGB2HSV).astype(np.float32)
    hsv_boost[:, :, 0] = hsv_boost[:, :, 0] * (1.0 - cyan_w * 0.35) + 95.5 * (cyan_w * 0.35)
    hsv_boost[:, :, 1] = np.clip(hsv_boost[:, :, 1] * (1.0 + cyan_w * (cyan_boost - 1.0)), 0.0, 255.0)
    hsv_boost[:, :, 2] = np.clip(hsv_boost[:, :, 2] * (1.0 + cyan_w * 0.08), 0.0, 255.0)

    out[:, :, :3] = cv2.cvtColor(hsv_boost.astype(np.uint8), cv2.COLOR_HSV2RGB)
    return out


def _make_studio_backdrop(
    width: int,
    height: int,
    *,
    glow_strength: float = 0.28,
    glow_scale: float = 0.72,
    glow_rgb: tuple[int, int, int] = GLOW_RGB,
) -> Image.Image:
    """Create a seamless #040711 studio canvas with subtle radial center depth."""
    yy, xx = np.mgrid[0:height, 0:width].astype(np.float32)
    cx, cy = width * 0.5, height * 0.5
    rx, ry = width * glow_scale * 0.5, height * glow_scale * 0.5
    r2 = ((xx - cx) / max(1.0, rx)) ** 2 + ((yy - cy) / max(1.0, ry)) ** 2
    falloff = np.exp(-1.75 * r2) * glow_strength

    base = np.zeros((height, width, 3), dtype=np.float32)
    for ch in range(3):
        base[:, :, ch] = VOID_RGB[ch] + (glow_rgb[ch] - VOID_RGB[ch]) * falloff
    return Image.fromarray(np.clip(base, 0.0, 255.0).astype(np.uint8), mode="RGB")


def _draw_subtle_circular_ring(
    canvas_rgba: Image.Image,
    *,
    radius: int = 378,
    width_px: int = 4,
    mode: str = "cyan",
    alpha_peak: int = 165,
) -> Image.Image:
    """
    Draw an antialiased subtle circular highlight ring inside the 800x800 safe frame.

    Rendered at 2x supersampling with soft inner glow so the ring remains crisp in
    square previews and never clips under YouTube's circular avatar crop.
    """
    w, h = canvas_rgba.size
    ss = 2
    sw, sh = w * ss, h * ss
    cx, cy = sw * 0.5, sh * 0.5
    yy, xx = np.mgrid[0:sh, 0:sw].astype(np.float32)
    dist = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)

    r_ss = radius * ss
    half_w = width_px * ss * 0.5
    stroke = np.clip(1.0 - np.maximum(0.0, np.abs(dist - r_ss) - half_w + 1.0) / 2.2, 0.0, 1.0)
    halo = np.exp(-((dist - r_ss) ** 2) / (2.0 * (5.5 * ss) ** 2)) * 0.28
    ring_alpha = np.clip(stroke * (alpha_peak / 255.0) + halo * (alpha_peak / 255.0), 0.0, 1.0)

    ring_arr = np.zeros((sh, sw, 4), dtype=np.float32)
    if mode == "cyan":
        ring_arr[:, :, :3] = np.array(CYAN_RGB, dtype=np.float32)
    elif mode == "crimson":
        ring_arr[:, :, :3] = np.array(CRIMSON_RGB, dtype=np.float32)
    elif mode == "slate_cyan":
        ring_arr[:, :, :3] = np.array((72, 185, 224), dtype=np.float32)
    elif mode == "split_cyan_crimson":
        # Smooth left=#27D8FF -> right=#FF2525 transition across vertical poles
        blend = np.clip((xx - (cx - 40.0)) / 80.0, 0.0, 1.0)[:, :, None]
        left_c = np.array(CYAN_RGB, dtype=np.float32)[None, None, :]
        right_c = np.array(CRIMSON_RGB, dtype=np.float32)[None, None, :]
        ring_arr[:, :, :3] = left_c * (1.0 - blend) + right_c * blend
    else:
        ring_arr[:, :, :3] = np.array(CYAN_RGB, dtype=np.float32)

    ring_arr[:, :, 3] = ring_alpha * 255.0
    ring_img = Image.fromarray(np.clip(ring_arr, 0, 255).astype(np.uint8), mode="RGBA").resize(
        (w, h), resample=Image.Resampling.LANCZOS
    )
    return Image.alpha_composite(canvas_rgba, ring_img)


def _composite_centered_subject(
    backdrop_rgb: Image.Image,
    subject_rgba: np.ndarray,
    *,
    target_w: int,
    target_h: int,
    offset_x: int = 0,
    offset_y: int = 0,
) -> Image.Image:
    """Scale and composite an RGBA subject cleanly onto an RGB backdrop."""
    src = Image.fromarray(subject_rgba, mode="RGBA")
    resized = src.resize((target_w, target_h), resample=Image.Resampling.LANCZOS)
    canvas = backdrop_rgb.convert("RGBA")
    px = (canvas.width - target_w) // 2 + offset_x
    py = (canvas.height - target_h) // 2 + offset_y
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    layer.paste(resized, (px, py))
    return Image.alpha_composite(canvas, layer)


def build_logo_a(out_path: Path) -> dict[str, Any]:
    """Logo A (Priority #1): 800x800 lateral Ep #31 matte gypsum brain + #27D8FF vessels."""
    src_path = SOURCE_ASSETS["a02_lateral_cand02"]
    rgba, bbox = _extract_subject_rgba(src_path)
    x0, y0, x1, y1 = bbox
    cropped = rgba[y0:y1, x0:x1]
    cropped = _enhance_gypsum_and_cyan(cropped, cyan_boost=1.28, contrast_gain=1.10)

    cw, ch = x1 - x0, y1 - y0
    # ~76% of the 800px circular safe frame -> 608px width; preserves crisp circular breathing room
    target_w = 608
    target_h = int(round(target_w * (ch / cw)))

    backdrop = _make_studio_backdrop(LOGO_SIZE, LOGO_SIZE, glow_strength=0.35, glow_scale=0.68)
    composed = _composite_centered_subject(
        backdrop,
        cropped,
        target_w=target_w,
        target_h=target_h,
        offset_x=-4,
        offset_y=14,  # Visually center cortical dome above brainstem taper
    )
    composed = _draw_subtle_circular_ring(composed, radius=378, width_px=4, mode="cyan", alpha_peak=180)
    final_rgb = composed.convert("RGB")
    _atomic_save_image(final_rgb, out_path, format="PNG", optimize=True)
    return {
        "file": out_path.name,
        "width": LOGO_SIZE,
        "height": LOGO_SIZE,
        "priority": 1,
        "recommended": True,
        "source_asset": str(src_path.relative_to(WORKSPACE_ROOT)),
        "subject_frame_ratio": round(target_w / LOGO_SIZE, 3),
        "ring_radius_px": 378,
        "sha256": _sha256_file(out_path),
        "bytes": out_path.stat().st_size,
    }


def _recolor_lateral_vessels_crimson(rgba: np.ndarray, *, contrast_gain: float = 1.10) -> np.ndarray:
    """
    Precision-replace ONLY the cyan/blue (#27D8FF) sulcal vessels on a lateral Ep #31 brain
    with 3D cylindrical #FF2525 crimson vessels while mapping non-vessel gypsum strictly onto
    cool silver-white #DCDFE3 (R <= G <= B, 0% pink bleed & 0% cyan fringe).
    """
    out = rgba.copy()
    rgb = out[:, :, :3].astype(np.float32)
    hsv = cv2.cvtColor(out[:, :, :3], cv2.COLOR_RGB2HSV).astype(np.float32)

    hue = hsv[:, :, 0]
    sat = hsv[:, :, 1]
    bmr = rgb[:, :, 2] - rgb[:, :, 0]

    # Strict sulcal vessel detector calibrated for A02_mode2_whole_brain_lateral (~16-19% vessel core)
    w_sat = np.clip((sat - 104.0) / 42.0, 0.0, 1.0)
    w_bmr = np.clip((bmr - 68.0) / 42.0, 0.0, 1.0)
    w_hue = np.clip(1.0 - np.abs(hue - 98.0) / 18.0, 0.0, 1.0)
    raw_w = w_sat * w_bmr * w_hue
    smooth_w = cv2.GaussianBlur(raw_w.astype(np.float32), (0, 0), sigmaX=0.65, sigmaY=0.65)
    # Hard-zero cool shaded gypsum slopes so 0% pink bleed ever reaches cortical gyri
    vessel_w = np.where((sat < 92.0) | (bmr < 56.0), 0.0, smooth_w)
    vessel_w = np.clip(vessel_w * 1.35, 0.0, 1.0)

    # Clean cool matte silver-white #DCDFE3 gypsum cortex (R <= G <= B across 100% non-vessel gyri)
    luma_g = 0.24 * rgb[:, :, 0] + 0.54 * rgb[:, :, 1] + 0.22 * rgb[:, :, 2]
    luma_c = np.where(luma_g > 28.0, np.clip(128.0 + (luma_g - 128.0) * contrast_gain, 0.0, 255.0), luma_g)
    gypsum_rgb = np.stack(
        [
            np.clip(luma_c * 0.968, 0.0, 255.0),
            np.clip(luma_c * 0.985, 0.0, 255.0),
            np.clip(luma_c * 1.015, 0.0, 255.0),
        ],
        axis=2,
    )

    # 3D cylindrical #FF2525 crimson vessel shading + crisp bright crimson specular ridge
    v_norm = np.clip((0.18 * rgb[:, :, 0] + 0.54 * rgb[:, :, 1] + 0.28 * rgb[:, :, 2]) / 205.0, 0.0, 1.20)
    crimson_base = np.array(CRIMSON_RGB, dtype=np.float32)[None, None, :]
    spec = np.clip((v_norm - 0.78) / 0.30, 0.0, 1.0)[:, :, None] * np.array([255.0, 150.0, 150.0], dtype=np.float32)[None, None, :]
    crimson_rgb = np.clip(crimson_base * (0.40 + 0.78 * v_norm[:, :, None]) + spec * 0.42, 0.0, 255.0)

    blended = gypsum_rgb * (1.0 - vessel_w[:, :, None]) + crimson_rgb * vessel_w[:, :, None]
    alpha_mask = (out[:, :, 3] > 0)[:, :, None]
    out[:, :, :3] = np.where(alpha_mask, np.clip(blended, 0.0, 255.0), 0.0).astype(np.uint8)
    return out


def build_logo_a_red(out_path: Path) -> dict[str, Any]:
    """Logo A-Red: 800x800 lateral Ep #31 cool matte gypsum brain + precision #FF2525 crimson vessels."""
    src_path = SOURCE_ASSETS["a02_lateral_cand02"]
    rgba, bbox = _extract_subject_rgba(src_path)
    x0, y0, x1, y1 = bbox
    cropped = rgba[y0:y1, x0:x1]
    cropped = _recolor_lateral_vessels_crimson(cropped, contrast_gain=1.10)

    cw, ch = x1 - x0, y1 - y0
    target_w = 608
    target_h = int(round(target_w * (ch / cw)))

    backdrop = _make_studio_backdrop(
        LOGO_SIZE,
        LOGO_SIZE,
        glow_strength=0.35,
        glow_scale=0.68,
        glow_rgb=CRIMSON_GLOW_RGB,
    )
    composed = _composite_centered_subject(
        backdrop,
        cropped,
        target_w=target_w,
        target_h=target_h,
        offset_x=-4,
        offset_y=14,
    )
    composed = _draw_subtle_circular_ring(composed, radius=378, width_px=4, mode="crimson", alpha_peak=185)
    final_rgb = composed.convert("RGB")
    _atomic_save_image(final_rgb, out_path, format="PNG", optimize=True)
    return {
        "file": out_path.name,
        "width": LOGO_SIZE,
        "height": LOGO_SIZE,
        "priority": 1,
        "variant": "crimson_red",
        "accent_color": CRIMSON_HEX,
        "source_asset": str(src_path.relative_to(WORKSPACE_ROOT)),
        "subject_frame_ratio": round(target_w / LOGO_SIZE, 3),
        "ring_radius_px": 378,
        "sha256": _sha256_file(out_path),
        "bytes": out_path.stat().st_size,
    }


def _extract_fringe_free_cyan_brain_rgba(image_path: Path) -> np.ndarray:
    """
    Extract lateral Ep #31 brain from dark void with 0px navy rim halo so it composites
    cleanly onto bright TED Red (#E62B1E) or Deep Studio Crimson backgrounds while
    keeping interior matte #DCDFE3 gypsum and #27D8FF cyan vessels 100% original.
    """
    rgba, bbox = _extract_subject_rgba(image_path)
    x0, y0, x1, y1 = bbox
    crop = rgba[y0:y1, x0:x1].copy()
    rgb = crop[:, :, :3].astype(np.float32)

    fg_bin = (crop[:, :, 3] > 128).astype(np.uint8)
    # 0-pad before distanceTransform so pixels touching the crop bbox edge (y=0, etc.) get true boundary distance
    fg_pad = cv2.copyMakeBorder(fg_bin, 2, 2, 2, 2, cv2.BORDER_CONSTANT, value=0)
    dist = cv2.distanceTransform(fg_pad, cv2.DIST_L2, 5)[2:-2, 2:-2]

    # Erode dark #040711 navy outer antialias rim (0..1.85px) cleanly with soft 0.55px feather
    clean_alpha = np.clip((dist - 1.85) / 1.55, 0.0, 1.0)
    clean_alpha = cv2.GaussianBlur(clean_alpha.astype(np.float32), (0, 0), sigmaX=0.55, sigmaY=0.55)
    clean_alpha = np.where(
        dist <= 1.25,
        0.0,
        np.where(dist >= 3.8, 1.0, np.clip(clean_alpha, 0.0, 1.0)),
    )

    # Interior-to-edge RGB decontamination from bright clean interior tissue (dist >= 3.5px & luma >= 95) outward
    src_luma = 0.299 * rgb[:, :, 0] + 0.587 * rgb[:, :, 1] + 0.114 * rgb[:, :, 2]
    valid = ((dist >= 3.5) & (src_luma >= 95.0)).astype(np.float32)
    clean_rgb = rgb.copy()
    kernel = np.ones((3, 3), dtype=np.float32)
    for _ in range(8):
        cnt = cv2.filter2D(valid, -1, kernel, borderType=cv2.BORDER_REPLICATE)
        summed = cv2.filter2D(clean_rgb * valid[:, :, None], -1, kernel, borderType=cv2.BORDER_REPLICATE)
        upd = (valid < 0.5) & (cnt > 0.5)
        avg_rgb = summed / np.maximum(cnt, 1.0)[:, :, None]
        clean_rgb = np.where(upd[:, :, None], avg_rgb, clean_rgb)
        valid = np.where(upd, 1.0, valid)

    w_edge = np.clip((3.6 - dist) / 1.9, 0.0, 1.0)
    w_crevice = np.where(src_luma < 95.0, np.clip((6.0 - dist) / 2.5, 0.0, 1.0), 0.0)
    w_int = np.maximum(w_edge, w_crevice)
    rgb_decontam = rgb * (1.0 - w_int[:, :, None]) + clean_rgb * w_int[:, :, None]

    out = np.zeros_like(crop)
    out[:, :, :3] = np.clip(rgb_decontam, 0.0, 255.0).astype(np.uint8)
    out[:, :, 3] = np.clip(clean_alpha * 255.0, 0.0, 255.0).astype(np.uint8)
    out = _enhance_gypsum_and_cyan(out, cyan_boost=1.24, contrast_gain=1.08)

    ys, xs = np.where(out[:, :, 3] > 16)
    if len(xs) == 0 or len(ys) == 0:
        raise RuntimeError(f"Empty fringe-free foreground for {image_path}")
    return out[int(ys.min()) : int(ys.max()) + 1, int(xs.min()) : int(xs.max()) + 1]


def _make_radial_gradient_backdrop(
    width: int,
    height: int,
    *,
    center_rgb: tuple[int, int, int],
    edge_rgb: tuple[int, int, int],
    power: float = 1.25,
) -> Image.Image:
    """Create a smooth radial vignette gradient RGB canvas from center_rgb to edge_rgb."""
    yy, xx = np.mgrid[0:height, 0:width].astype(np.float32)
    cx, cy = width * 0.5, height * 0.5
    radius = max(1.0, width * 0.5)
    t = np.clip(np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2) / radius, 0.0, 1.0) ** power

    c0 = np.array(center_rgb, dtype=np.float32)[None, None, :]
    c1 = np.array(edge_rgb, dtype=np.float32)[None, None, :]
    rgb = c0 * (1.0 - t[:, :, None]) + c1 * t[:, :, None]
    return Image.fromarray(np.clip(rgb, 0.0, 255.0).astype(np.uint8), mode="RGB")


def _composite_brain_with_soft_shadow(
    backdrop_rgb: Image.Image,
    brain_rgba: np.ndarray,
    *,
    target_w: int = 648,
    offset_x: int = -4,
    offset_y: int = 12,
    shadow_rgb: tuple[int, int, int] = (52, 4, 6),
    shadow_alpha_scale: float = 0.26,
    shadow_dy: int = 14,
    shadow_blur: float = 16.0,
) -> Image.Image:
    """Composite fringe-free brain onto bright backdrop with subtle warm downward drop shadow."""
    ch, cw = brain_rgba.shape[:2]
    target_h = int(round(target_w * (ch / cw)))
    src = Image.fromarray(brain_rgba, mode="RGBA")
    resized = src.resize((target_w, target_h), resample=Image.Resampling.LANCZOS)

    canvas = backdrop_rgb.convert("RGBA")
    px = (canvas.width - target_w) // 2 + offset_x
    py = (canvas.height - target_h) // 2 + offset_y

    # Soft downward drop shadow only (positive Y offset avoids top/side rim darkening)
    alpha_ch = resized.split()[3].point(lambda a: int(round(a * shadow_alpha_scale)))
    shadow_alpha = Image.new("L", canvas.size, 0)
    shadow_alpha.paste(alpha_ch, (px, py + shadow_dy))
    shadow_alpha = shadow_alpha.filter(ImageFilter.GaussianBlur(radius=shadow_blur))
    shadow_layer = Image.new("RGBA", canvas.size, (*shadow_rgb, 255))
    shadow_layer.putalpha(shadow_alpha)
    canvas = Image.alpha_composite(canvas, shadow_layer)

    fg_layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    fg_layer.paste(resized, (px, py))
    return Image.alpha_composite(canvas, fg_layer)


def _build_red_bg_cyan_brain_logo(
    out_path: Path,
    *,
    center_rgb: tuple[int, int, int],
    edge_rgb: tuple[int, int, int],
    center_hex: str,
    edge_hex: str,
    shadow_rgb: tuple[int, int, int],
    shadow_alpha_scale: float,
    variant_name: str,
    recommended: bool,
) -> dict[str, Any]:
    """Build 800x800 full-bleed red circular icon with original Ep #31 gypsum + #27D8FF brain."""
    src_path = SOURCE_ASSETS["a02_lateral_cand02"]
    cropped = _extract_fringe_free_cyan_brain_rgba(src_path)
    target_w = 648

    backdrop = _make_radial_gradient_backdrop(
        LOGO_SIZE,
        LOGO_SIZE,
        center_rgb=center_rgb,
        edge_rgb=edge_rgb,
        power=1.25,
    )
    composed = _composite_brain_with_soft_shadow(
        backdrop,
        cropped,
        target_w=target_w,
        offset_x=-4,
        offset_y=12,
        shadow_rgb=shadow_rgb,
        shadow_alpha_scale=shadow_alpha_scale,
        shadow_dy=14,
        shadow_blur=16.0,
    )
    final_rgb = composed.convert("RGB")
    _atomic_save_image(final_rgb, out_path, format="PNG", optimize=True)
    return {
        "file": out_path.name,
        "width": LOGO_SIZE,
        "height": LOGO_SIZE,
        "variant": variant_name,
        "recommended": recommended,
        "backdrop_center_hex": center_hex,
        "backdrop_edge_hex": edge_hex,
        "ring_radius_px": None,
        "source_asset": str(src_path.relative_to(WORKSPACE_ROOT)),
        "subject_frame_ratio": round(target_w / LOGO_SIZE, 3),
        "sha256": _sha256_file(out_path),
        "bytes": out_path.stat().st_size,
    }


def build_logo_a_ted_red(out_path: Path) -> dict[str, Any]:
    """Priority #1 Red-BG Logo: TED Red (#E62B1E -> #C81E15) + Ep #31 gypsum & #27D8FF brain."""
    return _build_red_bg_cyan_brain_logo(
        out_path,
        center_rgb=TED_RED_CENTER_RGB,
        edge_rgb=TED_RED_EDGE_RGB,
        center_hex=TED_RED_CENTER_HEX,
        edge_hex=TED_RED_EDGE_HEX,
        shadow_rgb=(58, 5, 4),
        shadow_alpha_scale=0.25,
        variant_name="ted_red_bg_cyan_brain",
        recommended=True,
    )


def build_logo_a_crimson_studio(out_path: Path) -> dict[str, Any]:
    """Option 2 Red-BG Logo: Deep Studio Crimson (#DC2228 -> #8A0E16) + Ep #31 gypsum & #27D8FF brain."""
    return _build_red_bg_cyan_brain_logo(
        out_path,
        center_rgb=STUDIO_CRIMSON_CENTER_RGB,
        edge_rgb=STUDIO_CRIMSON_EDGE_RGB,
        center_hex=STUDIO_CRIMSON_CENTER_HEX,
        edge_hex=STUDIO_CRIMSON_EDGE_HEX,
        shadow_rgb=(36, 2, 5),
        shadow_alpha_scale=0.30,
        variant_name="deep_crimson_studio_bg_cyan_brain",
        recommended=False,
    )


def _soften_glass_face_features(rgba: np.ndarray) -> np.ndarray:
    """
    Smooth subtle inner sculpted glass eye/lip creases on Mode 1 profile while leaving
    the crisp outer glass profile contour and interior #27D8FF brain 100% untouched.
    """
    out = rgba.copy()
    h, w, _ = out.shape
    rgb = out[:, :, :3]
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)

    # Interior facial glass zone covering eye-socket & mouth region below frontal lobe
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    face_zone = (
        (xx >= w * 0.06)
        & (xx <= w * 0.34)
        & (yy >= h * 0.36)
        & (yy <= h * 0.84)
    )
    not_brain_cyan = hsv[:, :, 1] < 45
    interior = out[:, :, 3] > 235
    fg_bin = (out[:, :, 3] > 128).astype(np.uint8)
    dist_edge = cv2.distanceTransform(fg_bin, cv2.DIST_L2, 5)
    mask = (face_zone & not_brain_cyan & interior & (dist_edge > 12.0)).astype(np.float32)
    mask = cv2.GaussianBlur(mask, (0, 0), sigmaX=8.0, sigmaY=8.0)

    smoothed = cv2.bilateralFilter(rgb, d=19, sigmaColor=55, sigmaSpace=28)
    smoothed = cv2.GaussianBlur(smoothed, (0, 0), sigmaX=7.5, sigmaY=7.5)
    blended = rgb.astype(np.float32) * (1.0 - mask[:, :, None]) + smoothed.astype(np.float32) * mask[:, :, None]
    out[:, :, :3] = np.clip(blended, 0.0, 255.0).astype(np.uint8)
    return out


def build_logo_b(out_path: Path) -> dict[str, Any]:
    """Logo B: 800x800 featureless Mode 1 translucent profile X-Ray cranium + #27D8FF brain."""
    src_path = SOURCE_ASSETS["a01_mode1_cand01"]
    rgba, bbox = _extract_subject_rgba(src_path, bg_threshold=13.5, ramp_span=16.0)
    x0, y0, x1, y1 = bbox
    cropped = rgba[y0:y1, x0:x1]

    # Full profile head from crown through chin/jawline; softly taper upper neck into void
    # so zero eyes/mouth are ever cropped and brain reads clearly at 32px
    ch_full, cw_full = cropped.shape[:2]
    head_keep_h = int(round(ch_full * 0.81))
    cropped = cropped[:head_keep_h, :].copy()
    cropped = _soften_glass_face_features(cropped)
    cropped = _enhance_gypsum_and_cyan(cropped, cyan_boost=1.36, contrast_gain=1.10)

    # Apply smooth vertical fade across the lower neck (bottom 20% of cropped height)
    yy = np.linspace(0.0, 1.0, cropped.shape[0], dtype=np.float32)[:, None]
    neck_fade = np.where(yy > 0.80, np.clip(1.0 - (yy - 0.80) / 0.20, 0.0, 1.0) ** 1.45, 1.0)
    cropped[:, :, 3] = np.clip(cropped[:, :, 3].astype(np.float32) * neck_fade, 0.0, 255.0).astype(np.uint8)

    cw, ch = cropped.shape[1], cropped.shape[0]
    target_h = 640
    target_w = int(round(target_h * (cw / ch)))
    if target_w > 604:
        target_w = 604
        target_h = int(round(target_w * (ch / cw)))

    backdrop = _make_studio_backdrop(LOGO_SIZE, LOGO_SIZE, glow_strength=0.30, glow_scale=0.68)
    composed = _composite_centered_subject(
        backdrop,
        cropped,
        target_w=target_w,
        target_h=target_h,
        offset_x=6,
        offset_y=24,
    )
    composed = _draw_subtle_circular_ring(composed, radius=378, width_px=3, mode="slate_cyan", alpha_peak=155)
    final_rgb = composed.convert("RGB")
    _atomic_save_image(final_rgb, out_path, format="PNG", optimize=True)
    return {
        "file": out_path.name,
        "width": LOGO_SIZE,
        "height": LOGO_SIZE,
        "priority": 2,
        "recommended": False,
        "source_asset": str(src_path.relative_to(WORKSPACE_ROOT)),
        "subject_frame_ratio": round(max(target_w, target_h) / LOGO_SIZE, 3),
        "ring_radius_px": 378,
        "sha256": _sha256_file(out_path),
        "bytes": out_path.stat().st_size,
    }


def _recolor_right_hemisphere_crimson(rgba: np.ndarray) -> np.ndarray:
    """
    Split dorsal brain cleanly along the exact interhemispheric fissure curve:
      - Left hemisphere: glowing matte #27D8FF cyan vascular accent
      - Right hemisphere: high-contrast #FF2525 crimson vascular/functional contrast
    """
    out = rgba.copy()
    h, w, _ = out.shape
    rgb = out[:, :, :3].astype(np.float32)
    hsv = cv2.cvtColor(out[:, :, :3], cv2.COLOR_RGB2HSV).astype(np.float32)
    gray = cv2.cvtColor(out[:, :, :3], cv2.COLOR_RGB2GRAY).astype(np.float32)

    # Trace exact dark interhemispheric fissure per row near horizontal center
    cx = w // 2
    search_half = max(18, int(w * 0.045))
    x_lo = max(0, cx - search_half)
    x_hi = min(w, cx + search_half)
    fissure_x = np.full(h, float(cx), dtype=np.float32)
    for y in range(int(h * 0.12), int(h * 0.88)):
        row_vals = gray[y, x_lo:x_hi]
        fissure_x[y] = float(x_lo + int(np.argmin(row_vals)))
    # Smooth fissure trajectory along y so split never jitters
    fissure_x = cv2.GaussianBlur(fissure_x[:, None], (1, 51), sigmaX=0, sigmaY=16)[:, 0]

    xx = np.arange(w, dtype=np.float32)[None, :]
    # 2px soft seam strictly tucked inside the dark interhemispheric cleft
    right_mask = np.clip((xx - fissure_x[:, None] + 1.0) / 2.0, 0.0, 1.0)
    left_mask = 1.0 - right_mask

    # Continuous cyan-vessel weight (captures opaque blue/cyan vessels and their shading skirts)
    hue = hsv[:, :, 0]
    sat = hsv[:, :, 1]
    val = hsv[:, :, 2]
    b_minus_r = np.clip((rgb[:, :, 2] - rgb[:, :, 0]) / 64.0, 0.0, 1.0)
    hue_cyan = np.clip(1.0 - np.abs(hue - 97.5) / 20.0, 0.0, 1.0)
    vessel_w = np.clip(hue_cyan * np.clip((sat - 40.0) / 55.0, 0.0, 1.0) * np.clip((val - 35.0) / 50.0, 0.0, 1.0), 0.0, 1.0)
    vessel_w = np.maximum(vessel_w, b_minus_r * np.clip((sat - 50.0) / 70.0, 0.0, 1.0))

    # Left hemisphere: deepen #27D8FF cyan vibrancy
    left_hsv = hsv.copy()
    lw = vessel_w * left_mask
    left_hsv[:, :, 0] = left_hsv[:, :, 0] * (1.0 - lw * 0.40) + 95.5 * (lw * 0.40)
    left_hsv[:, :, 1] = np.clip(left_hsv[:, :, 1] * (1.0 + lw * 0.30), 0.0, 255.0)
    left_hsv[:, :, 2] = np.clip(left_hsv[:, :, 2] * (1.0 + lw * 0.10), 0.0, 255.0)
    left_rgb = cv2.cvtColor(left_hsv.astype(np.uint8), cv2.COLOR_HSV2RGB).astype(np.float32)

    # Right hemisphere: map vascular shading onto pure #FF2525 crimson + subtle functional sulcal glow
    # Preserve 3D cylindrical brightness & specular ridges while replacing blue/cyan hue with crimson
    luma_norm = np.clip((0.22 * rgb[:, :, 0] + 0.52 * rgb[:, :, 1] + 0.26 * rgb[:, :, 2]) / 225.0, 0.0, 1.15)
    crimson_base = np.array(CRIMSON_RGB, dtype=np.float32)[None, None, :]
    spec_highlight = np.clip((luma_norm - 0.78) / 0.32, 0.0, 1.0)[:, :, None] * np.array([255.0, 170.0, 170.0], dtype=np.float32)[None, None, :]
    crimson_shaded = np.clip(crimson_base * (0.42 + 0.75 * luma_norm[:, :, None]) + spec_highlight * 0.45, 0.0, 255.0)

    # Subtle warm crimson functional bounce on right cortex gyri so 32px icon clearly splits L cyan / R red
    alpha_norm = out[:, :, 3].astype(np.float32) / 255.0
    right_cortex_tint = rgb * 0.93 + np.array([255.0, 195.0, 195.0], dtype=np.float32)[None, None, :] * 0.07
    rw = np.clip(vessel_w * 1.15, 0.0, 1.0) * right_mask
    right_rgb = right_cortex_tint * (1.0 - rw[:, :, None]) + crimson_shaded * rw[:, :, None]
    right_rgb = rgb * (1.0 - alpha_norm[:, :, None]) + right_rgb * alpha_norm[:, :, None]

    combined = left_rgb * left_mask[:, :, None] + right_rgb * right_mask[:, :, None]
    out[:, :, :3] = np.clip(combined, 0.0, 255.0).astype(np.uint8)
    return out


def build_logo_c(out_path: Path) -> dict[str, Any]:
    """Logo C: 800x800 dorsal Ep #31 brain split cleanly into left #27D8FF cyan vs right #FF2525 crimson."""
    src_path = SOURCE_ASSETS["a03_dorsal_cand01"]
    rgba, bbox = _extract_subject_rgba(src_path)
    x0, y0, x1, y1 = bbox
    cropped = rgba[y0:y1, x0:x1]
    cropped = _recolor_right_hemisphere_crimson(cropped)

    cw, ch = x1 - x0, y1 - y0
    # Frame ~81% height / ~66% width inside 800px circle so split reads strongly at 32x32px
    target_h = 652
    target_w = int(round(target_h * (cw / ch)))

    backdrop = _make_studio_backdrop(LOGO_SIZE, LOGO_SIZE, glow_strength=0.30, glow_scale=0.68)
    composed = _composite_centered_subject(
        backdrop,
        cropped,
        target_w=target_w,
        target_h=target_h,
        offset_x=0,
        offset_y=0,
    )
    composed = _draw_subtle_circular_ring(
        composed,
        radius=378,
        width_px=4,
        mode="split_cyan_crimson",
        alpha_peak=165,
    )
    final_rgb = composed.convert("RGB")
    _atomic_save_image(final_rgb, out_path, format="PNG", optimize=True)
    return {
        "file": out_path.name,
        "width": LOGO_SIZE,
        "height": LOGO_SIZE,
        "priority": 3,
        "recommended": False,
        "source_asset": str(src_path.relative_to(WORKSPACE_ROOT)),
        "subject_frame_ratio": round(target_h / LOGO_SIZE, 3),
        "ring_radius_px": 378,
        "sha256": _sha256_file(out_path),
        "bytes": out_path.stat().st_size,
    }


def _draw_tracked_segments(
    draw: ImageDraw.ImageDraw,
    center_x: int,
    y_top: int,
    segments: list[tuple[str, tuple[int, int, int]]],
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    tracking_px: int = 0,
) -> tuple[int, int, int, int]:
    """Draw multi-color single-line text centered at `center_x` and return exact ink bbox."""
    full_text = "".join(t for t, _ in segments)
    if not full_text:
        return (center_x, y_top, center_x, y_top)

    advances: list[float] = []
    for ch in full_text:
        adv = float(draw.textlength(ch, font=font))
        advances.append(adv)
    total_w = sum(advances) + tracking_px * max(0, len(full_text) - 1)

    # Measure vertical ink offset using full-string bbox at (0, 0)
    raw_bb = draw.textbbox((0, 0), full_text, font=font)
    cursor_x = float(center_x) - total_w * 0.5
    draw_y = float(y_top) - raw_bb[1]

    min_x, min_y = 10**9, 10**9
    max_x, max_y = -(10**9), -(10**9)
    idx = 0
    for seg_text, color in segments:
        for ch in seg_text:
            if ch != " ":
                ch_bb = draw.textbbox((cursor_x, draw_y), ch, font=font)
                min_x = min(min_x, int(math.floor(ch_bb[0])))
                min_y = min(min_y, int(math.floor(ch_bb[1])))
                max_x = max(max_x, int(math.ceil(ch_bb[2])))
                max_y = max(max_y, int(math.ceil(ch_bb[3])))
            draw.text((cursor_x, draw_y), ch, font=font, fill=color)
            cursor_x += advances[idx] + tracking_px
            idx += 1

    return (min_x, min_y, max_x, max_y)


def _make_vignetted_flank_brain(
    brain_rgba: np.ndarray,
    *,
    target_w: int,
    target_h: int,
    flip_horizontal: bool,
    fade_toward_right: bool,
) -> Image.Image:
    """Prepare a softly vignetted, low-key Ep #31 flank brain silhouette for banner margins."""
    src = Image.fromarray(brain_rgba, mode="RGBA")
    if flip_horizontal:
        src = src.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    src = src.resize((target_w, target_h), resample=Image.Resampling.LANCZOS)
    arr = np.array(src, dtype=np.float32)

    # Attenuate brightness smoothly so flank silhouettes frame the banner without competing with typography
    arr[:, :, :3] *= 0.48
    h, w, _ = arr.shape
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    nx = (xx / max(1.0, w - 1.0)) * 2.0 - 1.0
    ny = (yy / max(1.0, h - 1.0)) * 2.0 - 1.0
    radial = np.clip(1.0 - (0.55 * nx ** 2 + 0.65 * ny ** 2), 0.0, 1.0) ** 1.35

    # Stronger directional taper toward the inner text safe zone
    u = xx / max(1.0, w - 1.0)
    if fade_toward_right:
        inward = np.clip(1.0 - np.maximum(0.0, u - 0.30) / 0.68, 0.0, 1.0) ** 1.6
    else:
        inward = np.clip(1.0 - np.maximum(0.0, (1.0 - u) - 0.30) / 0.68, 0.0, 1.0) ** 1.6

    arr[:, :, 3] = np.clip(arr[:, :, 3] * radial * inward * 0.78, 0.0, 255.0)
    return Image.fromarray(arr.astype(np.uint8), mode="RGBA")


def build_banner(out_path: Path, *, accent_mode: str = "cyan") -> dict[str, Any]:
    """Build 2560x1440 YouTube banner (`cyan` or `crimson`) with text locked inside [507..2053, 508..931]."""
    is_crimson = str(accent_mode).strip().lower() == "crimson"
    backdrop = _make_studio_backdrop(
        BANNER_W,
        BANNER_H,
        glow_strength=0.85 if is_crimson else 0.92,
        glow_scale=0.58,
        glow_rgb=CRIMSON_GLOW_RGB if is_crimson else GLOW_RGB,
    )
    canvas = backdrop.convert("RGBA")

    # Symmetrical Ep #31 lateral brain silhouettes vignetted on outer flanks (x < 507, x > 2053)
    brain_rgba, bbox = _extract_subject_rgba(SOURCE_ASSETS["a02_lateral_cand02"])
    x0, y0, x1, y1 = bbox
    raw_crop = brain_rgba[y0:y1, x0:x1]
    brain_crop = (
        _recolor_lateral_vessels_crimson(raw_crop, contrast_gain=1.06)
        if is_crimson
        else _enhance_gypsum_and_cyan(raw_crop, cyan_boost=1.22, contrast_gain=1.06)
    )
    bw, bh = x1 - x0, y1 - y0
    flank_w = 476
    flank_h = int(round(flank_w * (bh / bw)))
    flank_y = (BANNER_H - flank_h) // 2 + 6

    left_brain = _make_vignetted_flank_brain(
        brain_crop,
        target_w=flank_w,
        target_h=flank_h,
        flip_horizontal=True,
        fade_toward_right=True,
    )
    right_brain = _make_vignetted_flank_brain(
        brain_crop,
        target_w=flank_w,
        target_h=flank_h,
        flip_horizontal=False,
        fade_toward_right=False,
    )

    flank_layer = Image.new("RGBA", (BANNER_W, BANNER_H), (0, 0, 0, 0))
    flank_layer.paste(left_brain, (18, flank_y))
    flank_layer.paste(right_brain, (BANNER_W - flank_w - 18, flank_y))
    canvas = Image.alpha_composite(canvas, flank_layer)

    # Render crisp central typography strictly inside 1546x423 safe zone [507..2053, 508..931]
    text_layer = Image.new("RGBA", (BANNER_W, BANNER_H), (0, 0, 0, 0))
    tdraw = ImageDraw.Draw(text_layer)

    title_font = _load_font(PRIMARY_DISPLAY_FONT, 164)
    sub_font = _load_font(PRIMARY_BODY_FONT, 46, weight=600)

    # Compute exact rendered heights to vertically center title + subhead inside y: 508..931
    title_raw = tdraw.textbbox((0, 0), "ALL ABOUT BRAIN", font=title_font)
    title_h = title_raw[3] - title_raw[1]  # ~124px
    sub_raw = tdraw.textbbox((0, 0), "REAL NEUROSCIENCE  ·  VERIFIED STUDIES", font=sub_font)
    sub_h = sub_raw[3] - sub_raw[1]  # ~36px
    gap_y = 44

    block_h = title_h + gap_y + sub_h
    safe_center_y = (SAFE_ZONE_BOX[1] + SAFE_ZONE_BOX[3]) // 2  # 719
    title_y = safe_center_y - block_h // 2
    sub_y = title_y + title_h + gap_y

    accent_rgb = CRIMSON_RGB if is_crimson else CYAN_RGB
    title_bbox = _draw_tracked_segments(
        tdraw,
        BANNER_W // 2,
        title_y,
        [("ALL ABOUT BRAIN", (255, 255, 255, 255))],
        title_font,
        tracking_px=2,
    )
    subhead_bbox = _draw_tracked_segments(
        tdraw,
        BANNER_W // 2,
        sub_y,
        [
            ("REAL NEUROSCIENCE", (*accent_rgb, 255)),
            ("  ·  ", (148, 163, 184, 255)),
            ("VERIFIED STUDIES", (226, 232, 240, 255)),
        ],
        sub_font,
        tracking_px=4,
    )

    # Subtle crisp accent hairline rule placed at exact ink midpoint between title and subhead
    rule_y = (title_bbox[3] + subhead_bbox[1]) // 2
    rule_alpha = 130 if is_crimson else 115
    tdraw.rectangle((BANNER_W // 2 - 160, rule_y - 1, BANNER_W // 2 + 160, rule_y + 1), fill=(*accent_rgb, rule_alpha))

    # Pixel-verify actual drawn ink union inside text_layer before compositing
    text_arr = np.array(text_layer)
    tys, txs = np.where(text_arr[:, :, 3] > 8)
    ink_union_bbox = (int(txs.min()), int(tys.min()), int(txs.max()) + 1, int(tys.max()) + 1)

    sx0, sy0, sx1, sy1 = SAFE_ZONE_BOX
    if not (
        ink_union_bbox[0] >= sx0
        and ink_union_bbox[1] >= sy0
        and ink_union_bbox[2] <= sx1
        and ink_union_bbox[3] <= sy1
    ):
        raise RuntimeError(f"Banner text ink bbox {ink_union_bbox} breached safe zone {SAFE_ZONE_BOX}")

    final_rgb = Image.alpha_composite(canvas, text_layer).convert("RGB")
    _atomic_save_image(final_rgb, out_path, format="PNG", optimize=True)

    return {
        "file": out_path.name,
        "width": BANNER_W,
        "height": BANNER_H,
        "variant": "crimson_red" if is_crimson else "cyan",
        "safe_zone_box": list(SAFE_ZONE_BOX),
        "desktop_zone_box": list(DESKTOP_ZONE_BOX),
        "text_bboxes": {
            "title": list(title_bbox),
            "title_height_px": title_bbox[3] - title_bbox[1],
            "subhead": list(subhead_bbox),
            "subhead_height_px": subhead_bbox[3] - subhead_bbox[1],
            "combined_ink_union": list(ink_union_bbox),
        },
        "safe_zone_margins_px": {
            "left": ink_union_bbox[0] - sx0,
            "top": ink_union_bbox[1] - sy0,
            "right": sx1 - ink_union_bbox[2],
            "bottom": sy1 - ink_union_bbox[3],
        },
        "sha256": _sha256_file(out_path),
        "bytes": out_path.stat().st_size,
    }


def build_banner_red(out_path: Path) -> dict[str, Any]:
    """Build 2560x1440 crimson-vessel matching YouTube banner inside [507..2053, 508..931]."""
    return build_banner(out_path, accent_mode="crimson")


def _make_circular_avatar(img_rgb: Image.Image, size: int) -> Image.Image:
    """Create a smooth antialiased circular RGBA avatar from a square logo."""
    ss = 4
    scaled = img_rgb.resize((size * ss, size * ss), resample=Image.Resampling.LANCZOS).convert("RGBA")
    mask = Image.new("L", (size * ss, size * ss), 0)
    mdraw = ImageDraw.Draw(mask)
    mdraw.ellipse((0, 0, size * ss - 1, size * ss - 1), fill=255)
    scaled.putalpha(mask)
    return scaled.resize((size, size), resample=Image.Resampling.LANCZOS)


def _draw_dashed_rect(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    *,
    outline: tuple[int, int, int],
    width: int = 2,
    dash: int = 16,
    gap: int = 10,
) -> None:
    x0, y0, x1, y1 = box
    for x in range(x0, x1, dash + gap):
        xe = min(x + dash, x1)
        draw.line((x, y0, xe, y0), fill=outline, width=width)
        draw.line((x, y1, xe, y1), fill=outline, width=width)
    for y in range(y0, y1, dash + gap):
        ye = min(y + dash, y1)
        draw.line((x0, y, x0, ye), fill=outline, width=width)
        draw.line((x1, y, x1, ye), fill=outline, width=width)


def _draw_dashed_hline(
    draw: ImageDraw.ImageDraw,
    x0: int,
    x1: int,
    y: int,
    *,
    fill: tuple[int, int, int],
    width: int = 2,
    dash: int = 14,
    gap: int = 10,
) -> None:
    for x in range(x0, x1, dash + gap):
        draw.line((x, y, min(x + dash, x1), y), fill=fill, width=width)


def build_comparison_sheet(
    out_path: Path,
    *,
    logo_paths: list[tuple[str, str, str, bool, Path]],
    banner_path: Path,
) -> dict[str, Any]:
    """
    Build high-res RGB presentation comparison board showing:
      - Top row: Logos A (#1 RECOMMENDED), B, C as 360px squares + circular avatars
        + real-size 64x64px and 32x32px circular Shorts feed UI strips on BOTH #0F0F0F and #FFFFFF.
      - Bottom row: Scaled 2560x1440 banner with thin dashed cyan 1546x423 safe-zone callout.
    """
    board_w, board_h = 2400, 2180
    board = Image.new("RGB", (board_w, board_h), (7, 11, 22))
    draw = ImageDraw.Draw(board)

    f_hdr = _load_font(PRIMARY_DISPLAY_FONT, 50)
    f_hdr_sub = _load_font(PRIMARY_BODY_FONT, 20, weight=500)
    f_card_title = _load_font(PRIMARY_DISPLAY_FONT, 30)
    f_card_sub = _load_font(PRIMARY_BODY_FONT, 18, weight=450)
    f_badge = _load_font(PRIMARY_BODY_FONT, 15, weight=700)
    f_ui_bold = _load_font(PRIMARY_BODY_FONT, 18, weight=700)
    f_ui_sm = _load_font(PRIMARY_BODY_FONT, 14, weight=600)
    f_ui_tiny = _load_font(PRIMARY_BODY_FONT, 13, weight=500)

    # Header bar
    draw.rectangle((0, 0, board_w, 116), fill=(10, 16, 30))
    draw.text((48, 28), "ALL ABOUT BRAIN  —  BRAND IDENTITY v2 (EP #31 REBRAND)", fill=(255, 255, 255), font=f_hdr)
    draw.text(
        (48, 84),
        "LOCKED PALETTE: #040711 STUDIO VOID  ·  #27D8FF SULCAL CYAN  ·  ZERO-TEXT AVATARS  ·  1546×423 SAFE BANNER",
        fill=CYAN_RGB,
        font=f_hdr_sub,
    )
    draw.line((0, 116, board_w, 116), fill=(39, 216, 255), width=2)

    # Top row: 3 logo cards
    margin_x = 48
    gap_x = 32
    card_w = (board_w - 2 * margin_x - 2 * gap_x) // 3  # 746px
    card_y = 140
    card_h = 842

    for idx, (label, subtitle, tag, is_rec, lpath) in enumerate(logo_paths):
        cx = margin_x + idx * (card_w + gap_x)
        border_col = CYAN_RGB if is_rec else (44, 58, 82)
        border_w = 3 if is_rec else 2
        draw.rounded_rectangle(
            (cx, card_y, cx + card_w, card_y + card_h),
            radius=16,
            fill=(11, 17, 32),
            outline=border_col,
            width=border_w,
        )

        # Badge & title
        badge_bg = CYAN_RGB if is_rec else (30, 41, 59)
        badge_fg = (4, 7, 17) if is_rec else (203, 213, 225)
        draw.rounded_rectangle((cx + 22, card_y + 18, cx + 190, card_y + 46), radius=6, fill=badge_bg)
        draw.text((cx + 106, card_y + 32), tag, fill=badge_fg, font=f_badge, anchor="mm")

        draw.text((cx + 206, card_y + 16), label, fill=(255, 255, 255), font=f_card_title)
        draw.text((cx + 22, card_y + 56), subtitle, fill=(148, 163, 184), font=f_card_sub)

        with Image.open(lpath) as lim:
            logo_rgb = lim.convert("RGB")

        # 800 -> 360px square preview
        sq_preview = logo_rgb.resize((360, 360), resample=Image.Resampling.LANCZOS)
        sq_x = cx + 22
        sq_y = card_y + 92
        draw.rectangle((sq_x - 1, sq_y - 1, sq_x + 360, sq_y + 360), outline=(45, 60, 86), width=1)
        board.paste(sq_preview, (sq_x, sq_y))
        draw.text((sq_x, sq_y + 368), "800→360px SQUARE MASTER", fill=(148, 163, 184), font=f_ui_tiny)

        # Circular avatar preview (240x240)
        av_240 = _make_circular_avatar(logo_rgb, 240)
        av_x = cx + 444
        av_y = card_y + 150
        board.paste(av_240, (av_x, av_y), mask=av_240.split()[3])
        draw.text((av_x + 28, sq_y + 368), "240px CIRCLE AVATAR", fill=(148, 163, 184), font=f_ui_tiny)

def _paste_youtube_ui_mock_strips(
    board: Image.Image,
    draw: ImageDraw.ImageDraw,
    *,
    logo_rgb: Image.Image,
    strip_x: int,
    start_y: int,
    strip_w: int,
    strip_h: int,
    strip_gap: int,
    div_offset_x: int,
    x32_btn_offset: int,
    f_ui_bold: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    f_ui_sm: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    f_ui_tiny: ImageFont.FreeTypeFont | ImageFont.ImageFont,
) -> None:
    """Render actual 64x64 and 32x32 YouTube Dark (#0F0F0F) & Light (#FFFFFF) UI strips."""
    av_64 = _make_circular_avatar(logo_rgb, 64)
    av_32 = _make_circular_avatar(logo_rgb, 32)
    for s_idx, (bg_c, fg_c, sub_c, pill_bg, pill_fg, mode_lbl) in enumerate(
        [
            ((15, 15, 15), (255, 255, 255), (170, 170, 170), (255, 255, 255), (15, 15, 15), "DARK UI #0F0F0F  ·  ACTUAL 64×64 & 32×32px"),
            ((255, 255, 255), (15, 15, 15), (96, 96, 96), (15, 15, 15), (255, 255, 255), "LIGHT UI #FFFFFF  ·  ACTUAL 64×64 & 32×32px"),
        ]
    ):
        sy = start_y + s_idx * (strip_h + strip_gap)
        draw.rounded_rectangle((strip_x, sy, strip_x + strip_w, sy + strip_h), radius=10, fill=bg_c, outline=(48, 62, 84), width=1)
        draw.text((strip_x + 14, sy + 10), mode_lbl, fill=sub_c, font=f_ui_tiny)

        # 64x64 Channel Header Mock (Left)
        y64 = sy + 46 if strip_h >= 140 else sy + 36
        board.paste(av_64, (strip_x + 16, y64), mask=av_64.split()[3])
        draw.text((strip_x + 92, y64 + 6), "@AllAboutBrainOfficial", fill=fg_c, font=f_ui_bold)
        draw.rounded_rectangle((strip_x + 92, y64 + 33, strip_x + 188, y64 + 59), radius=13, fill=pill_bg)
        draw.text((strip_x + 140, y64 + 46), "Subscribe", fill=pill_fg, font=f_ui_sm, anchor="mm")
        draw.text((strip_x + 30, y64 + 69), "64px", fill=sub_c, font=f_ui_tiny)

        # Divider between 64px and 32px tests
        div_x = strip_x + div_offset_x
        draw.line((div_x, sy + 32, div_x, sy + strip_h - 14), fill=(120, 130, 145), width=1)

        # 32x32 Mobile Shorts Feed Mock (Right)
        y32 = y64 + 14
        x32 = div_x + 16
        board.paste(av_32, (x32, y32), mask=av_32.split()[3])
        draw.text((x32 + 40, y32 + 8), "@AllAboutBrainOfficial", fill=fg_c, font=f_ui_sm)
        draw.rounded_rectangle((x32 + x32_btn_offset, y32 + 3, x32 + x32_btn_offset + 78, y32 + 29), radius=13, fill=pill_bg)
        draw.text((x32 + x32_btn_offset + 39, y32 + 16), "Subscribe", fill=pill_fg, font=f_ui_tiny, anchor="mm")
        draw.text((x32 + 2, y32 + 38), "32px Shorts", fill=sub_c, font=f_ui_tiny)


def _paste_banner_preview_panel(
    board: Image.Image,
    draw: ImageDraw.ImageDraw,
    *,
    banner_path: Path,
    board_w: int,
    margin_x: int,
    bot_y: int,
    bot_h: int,
    title: str,
    subtitle: str,
    accent_rgb: tuple[int, int, int],
    f_card_title: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    f_card_sub: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    f_ui_sm: ImageFont.FreeTypeFont | ImageFont.ImageFont,
) -> None:
    """Render a scaled 2560x1440 YouTube banner panel with 1546x423 safe-zone callout."""
    draw.rounded_rectangle(
        (margin_x, bot_y, board_w - margin_x, bot_y + bot_h),
        radius=16,
        fill=(11, 17, 32),
        outline=(44, 58, 82),
        width=2,
    )
    draw.text((margin_x + 24, bot_y + 18), title, fill=(255, 255, 255), font=f_card_title)
    draw.text((margin_x + 24, bot_y + 56), subtitle, fill=accent_rgb, font=f_card_sub)

    with Image.open(banner_path) as bim:
        banner_rgb = bim.convert("RGB")
    disp_w = 1840
    disp_h = 1035  # exact 16:9
    banner_scaled = banner_rgb.resize((disp_w, disp_h), resample=Image.Resampling.LANCZOS)
    bx = (board_w - disp_w) // 2
    by = bot_y + 92
    draw.rectangle((bx - 2, by - 2, bx + disp_w + 1, by + disp_h + 1), outline=(51, 65, 85), width=2)
    board.paste(banner_scaled, (bx, by))

    scale = disp_w / BANNER_W
    sx0 = bx + int(round(SAFE_ZONE_BOX[0] * scale))
    sy0 = by + int(round(SAFE_ZONE_BOX[1] * scale))
    sx1 = bx + int(round(SAFE_ZONE_BOX[2] * scale))
    sy1 = by + int(round(SAFE_ZONE_BOX[3] * scale))

    _draw_dashed_hline(draw, bx, bx + disp_w, sy0, fill=(100, 116, 139), width=2)
    _draw_dashed_hline(draw, bx, bx + disp_w, sy1, fill=(100, 116, 139), width=2)
    _draw_dashed_rect(draw, (sx0, sy0, sx1, sy1), outline=accent_rgb, width=2, dash=14, gap=8)

    draw.text((bx + 16, by + 14), "TV FULL BLEED (2560×1440)", fill=(148, 163, 184), font=f_ui_sm)
    draw.text((bx + 16, sy0 - 24), "DESKTOP BAND (2560×423 @ y:508..931)", fill=(148, 163, 184), font=f_ui_sm)
    draw.text((sx0 + 10, sy0 - 24), "MOBILE / UNIVERSAL SAFE ZONE (1546×423 @ x:507..2053)", fill=accent_rgb, font=f_ui_sm)


def build_comparison_sheet(
    out_path: Path,
    *,
    logo_paths: list[tuple[str, str, str, bool, Path]],
    banner_path: Path,
) -> dict[str, Any]:
    """
    Build high-res RGB presentation comparison board showing:
      - Top row: Logos A (#1 RECOMMENDED), B, C as 360px squares + circular avatars
        + real-size 64x64px and 32x32px circular Shorts feed UI strips on BOTH #0F0F0F and #FFFFFF.
      - Bottom row: Scaled 2560x1440 banner with thin dashed cyan 1546x423 safe-zone callout.
    """
    board_w, board_h = 2400, 2180
    board = Image.new("RGB", (board_w, board_h), (7, 11, 22))
    draw = ImageDraw.Draw(board)

    f_hdr = _load_font(PRIMARY_DISPLAY_FONT, 50)
    f_hdr_sub = _load_font(PRIMARY_BODY_FONT, 20, weight=500)
    f_card_title = _load_font(PRIMARY_DISPLAY_FONT, 30)
    f_card_sub = _load_font(PRIMARY_BODY_FONT, 18, weight=450)
    f_badge = _load_font(PRIMARY_BODY_FONT, 15, weight=700)
    f_ui_bold = _load_font(PRIMARY_BODY_FONT, 18, weight=700)
    f_ui_sm = _load_font(PRIMARY_BODY_FONT, 14, weight=600)
    f_ui_tiny = _load_font(PRIMARY_BODY_FONT, 13, weight=500)

    # Header bar
    draw.rectangle((0, 0, board_w, 116), fill=(10, 16, 30))
    draw.text((48, 28), "ALL ABOUT BRAIN  —  BRAND IDENTITY v2 (EP #31 REBRAND)", fill=(255, 255, 255), font=f_hdr)
    draw.text(
        (48, 84),
        "LOCKED PALETTE: #040711 STUDIO VOID  ·  #27D8FF SULCAL CYAN  ·  ZERO-TEXT AVATARS  ·  1546×423 SAFE BANNER",
        fill=CYAN_RGB,
        font=f_hdr_sub,
    )
    draw.line((0, 116, board_w, 116), fill=(39, 216, 255), width=2)

    # Top row: 3 logo cards
    margin_x = 48
    gap_x = 32
    card_w = (board_w - 2 * margin_x - 2 * gap_x) // 3  # 746px
    card_y = 140
    card_h = 842

    for idx, (label, subtitle, tag, is_rec, lpath) in enumerate(logo_paths):
        cx = margin_x + idx * (card_w + gap_x)
        border_col = CYAN_RGB if is_rec else (44, 58, 82)
        border_w = 3 if is_rec else 2
        draw.rounded_rectangle(
            (cx, card_y, cx + card_w, card_y + card_h),
            radius=16,
            fill=(11, 17, 32),
            outline=border_col,
            width=border_w,
        )

        # Badge & title
        badge_bg = CYAN_RGB if is_rec else (30, 41, 59)
        badge_fg = (4, 7, 17) if is_rec else (203, 213, 225)
        draw.rounded_rectangle((cx + 22, card_y + 18, cx + 190, card_y + 46), radius=6, fill=badge_bg)
        draw.text((cx + 106, card_y + 32), tag, fill=badge_fg, font=f_badge, anchor="mm")

        draw.text((cx + 206, card_y + 16), label, fill=(255, 255, 255), font=f_card_title)
        draw.text((cx + 22, card_y + 56), subtitle, fill=(148, 163, 184), font=f_card_sub)

        with Image.open(lpath) as lim:
            logo_rgb = lim.convert("RGB")

        # 800 -> 360px square preview
        sq_preview = logo_rgb.resize((360, 360), resample=Image.Resampling.LANCZOS)
        sq_x = cx + 22
        sq_y = card_y + 92
        draw.rectangle((sq_x - 1, sq_y - 1, sq_x + 360, sq_y + 360), outline=(45, 60, 86), width=1)
        board.paste(sq_preview, (sq_x, sq_y))
        draw.text((sq_x, sq_y + 368), "800→360px SQUARE MASTER", fill=(148, 163, 184), font=f_ui_tiny)

        # Circular avatar preview (240x240)
        av_240 = _make_circular_avatar(logo_rgb, 240)
        av_x = cx + 444
        av_y = card_y + 150
        board.paste(av_240, (av_x, av_y), mask=av_240.split()[3])
        draw.text((av_x + 28, sq_y + 368), "240px CIRCLE AVATAR", fill=(148, 163, 184), font=f_ui_tiny)

        _paste_youtube_ui_mock_strips(
            board,
            draw,
            logo_rgb=logo_rgb,
            strip_x=cx + 22,
            start_y=card_y + 500,
            strip_w=card_w - 44,
            strip_h=148,
            strip_gap=16,
            div_offset_x=365,
            x32_btn_offset=236,
            f_ui_bold=f_ui_bold,
            f_ui_sm=f_ui_sm,
            f_ui_tiny=f_ui_tiny,
        )

    _paste_banner_preview_panel(
        board,
        draw,
        banner_path=banner_path,
        board_w=board_w,
        margin_x=margin_x,
        bot_y=1004,
        bot_h=1144,
        title="YOUTUBE CHANNEL BANNER (2560 × 1440)  —  SAFE-ZONE VERIFICATION",
        subtitle="DASHED CYAN = UNIVERSAL MOBILE/DESKTOP SAFE ZONE (1546×423 @ x:507..2053, y:508..931)   |   DASHED SLATE = DESKTOP STRIP (2560×423)   |   OUTER = TV BLEED",
        accent_rgb=CYAN_RGB,
        f_card_title=f_card_title,
        f_card_sub=f_card_sub,
        f_ui_sm=f_ui_sm,
    )

    _atomic_save_image(board, out_path, format="JPEG", quality=94, subsampling=0)
    return {
        "file": out_path.name,
        "width": board_w,
        "height": board_h,
        "mode": "RGB",
        "sha256": _sha256_file(out_path),
        "bytes": out_path.stat().st_size,
    }


def _draw_two_up_800px_logo_cards(
    board: Image.Image,
    draw: ImageDraw.ImageDraw,
    *,
    board_w: int,
    header_title: str,
    header_sub: str,
    header_accent_rgb: tuple[int, int, int],
    cards: list[tuple[str, str, str, tuple[int, int, int], Path]],
) -> tuple[int, int]:
    """Render shared 2-column 800px 1:1 comparison header + cards (with 240px avatar & 64/32px UI mocks)."""
    f_hdr = _load_font(PRIMARY_DISPLAY_FONT, 48)
    f_hdr_sub = _load_font(PRIMARY_BODY_FONT, 20, weight=500)
    f_card_title = _load_font(PRIMARY_DISPLAY_FONT, 30)
    f_card_sub = _load_font(PRIMARY_BODY_FONT, 18, weight=450)
    f_badge = _load_font(PRIMARY_BODY_FONT, 15, weight=700)
    f_ui_bold = _load_font(PRIMARY_BODY_FONT, 18, weight=700)
    f_ui_sm = _load_font(PRIMARY_BODY_FONT, 14, weight=600)
    f_ui_tiny = _load_font(PRIMARY_BODY_FONT, 13, weight=500)

    draw.rectangle((0, 0, board_w, 116), fill=(10, 16, 30))
    draw.text((48, 28), header_title, fill=(255, 255, 255), font=f_hdr)
    draw.text((48, 84), header_sub, fill=header_accent_rgb, font=f_hdr_sub)
    draw.line((0, 116, board_w, 116), fill=header_accent_rgb, width=2)

    margin_x = 48
    gap_x = 32
    card_w = (board_w - 2 * margin_x - gap_x) // 2  # 1136px
    card_y = 140
    card_h = 1208

    for idx, (label, subtitle, tag, accent_c, lpath) in enumerate(cards):
        cx = margin_x + idx * (card_w + gap_x)
        draw.rounded_rectangle(
            (cx, card_y, cx + card_w, card_y + card_h),
            radius=16,
            fill=(11, 17, 32),
            outline=accent_c,
            width=3,
        )
        draw.rounded_rectangle((cx + 22, card_y + 18, cx + 220, card_y + 46), radius=6, fill=accent_c)
        draw.text((cx + 121, card_y + 32), tag, fill=(4, 7, 17), font=f_badge, anchor="mm")
        draw.text((cx + 236, card_y + 16), label, fill=(255, 255, 255), font=f_card_title)
        draw.text((cx + 22, card_y + 56), subtitle, fill=(148, 163, 184), font=f_card_sub)

        with Image.open(lpath) as lim:
            logo_rgb = lim.convert("RGB")

        sq_x = cx + 22
        sq_y = card_y + 92
        draw.rectangle((sq_x - 1, sq_y - 1, sq_x + LOGO_SIZE, sq_y + LOGO_SIZE), outline=(52, 68, 96), width=1)
        board.paste(logo_rgb, (sq_x, sq_y))
        draw.text((sq_x, sq_y + LOGO_SIZE + 8), "800×800px 1:1 FULL MASTER", fill=(148, 163, 184), font=f_ui_tiny)

        av_240 = _make_circular_avatar(logo_rgb, 240)
        av_x = cx + 858
        av_y = card_y + 350
        board.paste(av_240, (av_x, av_y), mask=av_240.split()[3])
        draw.text((av_x + 42, av_y + 252), "240px CIRCLE AVATAR", fill=(148, 163, 184), font=f_ui_tiny)

        _paste_youtube_ui_mock_strips(
            board,
            draw,
            logo_rgb=logo_rgb,
            strip_x=cx + 22,
            start_y=card_y + 926,
            strip_w=card_w - 44,
            strip_h=124,
            strip_gap=14,
            div_offset_x=546,
            x32_btn_offset=260,
            f_ui_bold=f_ui_bold,
            f_ui_sm=f_ui_sm,
            f_ui_tiny=f_ui_tiny,
        )
    return margin_x, card_y + card_h


def build_cyan_vs_red_comparison_sheet(
    out_path: Path,
    *,
    logo_cyan_path: Path,
    logo_red_path: Path,
    banner_red_path: Path,
) -> dict[str, Any]:
    """
    Side-by-side Logo A Cyan (#27D8FF) vs Logo A-Red Crimson (#FF2525) sheet at exact
    800x800px 1:1 master size + 240px circular avatar + 64px/32px Dark/Light UI mocks + Red banner.
    """
    board_w, board_h = 2400, 2544
    board = Image.new("RGB", (board_w, board_h), (7, 11, 22))
    draw = ImageDraw.Draw(board)

    margin_x, cards_bottom = _draw_two_up_800px_logo_cards(
        board,
        draw,
        board_w=board_w,
        header_title="LOGO A SIDE-BY-SIDE COMPARISON  —  CYAN (#27D8FF)  vs  CRIMSON RED (#FF2525)",
        header_sub="1:1 800×800px MASTER  ·  240px CIRCLE AVATAR  ·  64px/32px DARK & LIGHT YOUTUBE UI  ·  MATCHING #FF2525 BANNER PREVIEW",
        header_accent_rgb=CRIMSON_RGB,
        cards=[
            (
                "LOGO A (CYAN)",
                "Ep #31 matte gypsum lateral 3D brain + #27D8FF sulcal vessels",
                "CYAN #27D8FF",
                CYAN_RGB,
                logo_cyan_path,
            ),
            (
                "LOGO A-RED (CRIMSON)",
                "Cool matte #DCDFE3 gypsum (0% pink bleed) + #FF2525 crimson vessels",
                "CRIMSON #FF2525",
                CRIMSON_RGB,
                logo_red_path,
            ),
        ],
    )

    f_card_title = _load_font(PRIMARY_DISPLAY_FONT, 30)
    f_card_sub = _load_font(PRIMARY_BODY_FONT, 18, weight=450)
    f_ui_sm = _load_font(PRIMARY_BODY_FONT, 14, weight=600)
    _paste_banner_preview_panel(
        board,
        draw,
        banner_path=banner_red_path,
        board_w=board_w,
        margin_x=margin_x,
        bot_y=cards_bottom + 24,
        bot_h=1144,
        title="MATCHING CRIMSON RED BANNER (2560 × 1440)  —  SAFE-ZONE VERIFICATION",
        subtitle="DASHED CRIMSON = UNIVERSAL MOBILE/DESKTOP SAFE ZONE (1546×423 @ x:507..2053, y:508..931)   |   DASHED SLATE = DESKTOP STRIP (2560×423)   |   OUTER = TV BLEED",
        accent_rgb=CRIMSON_RGB,
        f_card_title=f_card_title,
        f_card_sub=f_card_sub,
        f_ui_sm=f_ui_sm,
    )

    _atomic_save_image(board, out_path, format="JPEG", quality=94, subsampling=0)
    return {
        "file": out_path.name,
        "width": board_w,
        "height": board_h,
        "mode": "RGB",
        "sha256": _sha256_file(out_path),
        "bytes": out_path.stat().st_size,
    }


def build_ted_red_comparison_sheet(
    out_path: Path,
    *,
    ted_logo_path: Path,
    studio_logo_path: Path,
) -> dict[str, Any]:
    """
    Side-by-side TED Red (#E62B1E) vs Deep Studio Crimson (#DC2228->#8A0E16) comparison board
    with original Ep #31 gypsum + #27D8FF cyan brain at 800x800px 1:1 + 240px + 64px/32px UI mocks.
    """
    board_w, board_h = 2400, 1384
    board = Image.new("RGB", (board_w, board_h), (7, 11, 22))
    draw = ImageDraw.Draw(board)

    _draw_two_up_800px_logo_cards(
        board,
        draw,
        board_w=board_w,
        header_title="RED BACKDROP + EP #31 CYAN BRAIN  —  TED RED (#E62B1E)  vs  DEEP STUDIO CRIMSON",
        header_sub="0px NAVY RIM DECONTAMINATION  ·  ORIGINAL #DCDFE3 GYPSUM + #27D8FF CYAN VESSELS  ·  FULL-BLEED 64px/32px UI PUNCH",
        header_accent_rgb=TED_RED_CENTER_RGB,
        cards=[
            (
                "TED RED (#E62B1E) + CYAN BRAIN",
                "Center #E62B1E -> Edge #C81E15 · Ep #31 gypsum & #27D8FF vessels · soft shadow",
                "#1 RECOMMENDED",
                TED_RED_CENTER_RGB,
                ted_logo_path,
            ),
            (
                "DEEP STUDIO CRIMSON + CYAN BRAIN",
                "Center #DC2228 -> Edge #8A0E16 · Documentary studio vignette · soft shadow",
                "OPTION 2",
                STUDIO_CRIMSON_CENTER_RGB,
                studio_logo_path,
            ),
        ],
    )

    _atomic_save_image(board, out_path, format="JPEG", quality=94, subsampling=0)
    return {
        "file": out_path.name,
        "width": board_w,
        "height": board_h,
        "mode": "RGB",
        "sha256": _sha256_file(out_path),
        "bytes": out_path.stat().st_size,
    }


def _verify_banner_safe_zone_entry(
    output_dir: Path,
    fname: str,
    banner_meta: dict[str, Any],
    issues: list[str],
    label: str,
) -> dict[str, Any]:
    """Verify manifest text bbox union and rendered >200-luma pixels stay inside SAFE_ZONE_BOX."""
    sz = banner_meta.get("safe_zone_box", [])
    bboxes = banner_meta.get("text_bboxes", {})
    union_bb = bboxes.get("combined_ink_union", [])
    safe_ok = False
    if len(sz) == 4 and len(union_bb) == 4 and tuple(sz) == SAFE_ZONE_BOX:
        safe_ok = (
            union_bb[0] >= SAFE_ZONE_BOX[0]
            and union_bb[1] >= SAFE_ZONE_BOX[1]
            and union_bb[2] <= SAFE_ZONE_BOX[2]
            and union_bb[3] <= SAFE_ZONE_BOX[3]
        )
    if not safe_ok:
        issues.append(f"Manifest {label} text union {union_bb} outside safe zone {SAFE_ZONE_BOX}")

    banner_file = output_dir / fname
    pixel_safe_ok = False
    if banner_file.is_file():
        barr = np.array(Image.open(banner_file).convert("RGB"))
        luma = 0.299 * barr[:, :, 0] + 0.587 * barr[:, :, 1] + 0.114 * barr[:, :, 2]
        bright_ys, bright_xs = np.where(luma > 200.0)
        if len(bright_xs) > 0:
            outside = (
                (bright_xs < SAFE_ZONE_BOX[0])
                | (bright_xs >= SAFE_ZONE_BOX[2])
                | (bright_ys < SAFE_ZONE_BOX[1])
                | (bright_ys >= SAFE_ZONE_BOX[3])
            )
            pixel_safe_ok = not bool(np.any(outside))
            if not pixel_safe_ok:
                issues.append(f"Rendered {label} ({fname}) has bright >200 luma pixels outside safe zone")
        else:
            issues.append(f"Rendered {label} ({fname}) has zero bright text pixels")

    return {
        "safe_zone_box": list(SAFE_ZONE_BOX),
        "combined_ink_union": union_bb,
        "manifest_bounds_ok": safe_ok,
        "rendered_pixel_bounds_ok": pixel_safe_ok,
    }


def _verify_logo_a_red_purity(fpath: Path, issues: list[str]) -> bool:
    """Verify crimson vessels (#FF2525) are strong and non-vessel cortex has 0% pink bleed & 0% cyan fringe."""
    if not fpath.is_file():
        return False
    rgb = np.array(Image.open(fpath).convert("RGB"), dtype=np.float32)
    h, w, _ = rgb.shape
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    dist_c = np.sqrt((xx - w * 0.5) ** 2 + (yy - h * 0.5) ** 2)
    luma = 0.299 * rgb[:, :, 0] + 0.587 * rgb[:, :, 1] + 0.114 * rgb[:, :, 2]
    fg_brain = (dist_c < 340.0) & (luma > 35.0)
    fg_count = int(fg_brain.sum())
    if fg_count < 10_000:
        issues.append(f"logo_A_red foreground too small: {fg_count}")
        return False

    hsv = cv2.cvtColor(rgb.astype(np.uint8), cv2.COLOR_RGB2HSV).astype(np.float32)
    sat = hsv[:, :, 1]
    rmb = rgb[:, :, 0] - rgb[:, :, 2]
    bmr = rgb[:, :, 2] - rgb[:, :, 0]

    # Non-vessel cool gypsum cortex (outside 2px vessel antialias rim): must remain strictly cool silver-white
    ves_core = (fg_brain & (rmb >= 60.0)).astype(np.uint8)
    dilated_ves = cv2.dilate(ves_core, np.ones((5, 5), np.uint8), iterations=1) > 0
    cortex_mask = fg_brain & (~dilated_ves) & (luma >= 100.0)
    pink_bleed = cortex_mask & (rmb > 12.0)
    cortex_mean_rmb = float(np.mean(rmb[cortex_mask])) if np.any(cortex_mask) else 0.0
    pink_frac = float(pink_bleed.sum()) / max(1, int(cortex_mask.sum()))
    crimson_frac = float((fg_brain & (rmb >= 90.0) & (rgb[:, :, 0] >= 140.0)).sum()) / fg_count
    cyan_leftover_frac = float((fg_brain & (bmr >= 45.0) & (sat >= 70.0)).sum()) / fg_count

    ok = (pink_frac <= 0.005) and (cortex_mean_rmb <= 2.0) and (crimson_frac >= 0.06) and (cyan_leftover_frac <= 0.002)
    if not ok:
        issues.append(
            f"logo_A_red purity failed: pink_frac={pink_frac:.4f}, mean_rmb={cortex_mean_rmb:.2f}, "
            f"crimson_frac={crimson_frac:.3f}, cyan_leftover={cyan_leftover_frac:.4f}"
        )
    return ok


def _verify_red_bg_cyan_brain_fringe_free(
    fpath: Path,
    expected_edge_rgb: tuple[int, int, int],
    issues: list[str],
    label: str,
) -> bool:
    """
    Verify red-backdrop + Ep #31 cyan-brain logo:
      1. Corners match expected_edge_rgb within tolerance.
      2. Original #27D8FF cyan vessels (>= 8%) and cool matte #DCDFE3 gypsum (>= 25%) remain intact.
      3. Zero dark-navy/purple halo dip pixels along the upper/lateral boundary (y < 430).
    """
    if not fpath.is_file():
        return False
    rgb = np.array(Image.open(fpath).convert("RGB"), dtype=np.float32)
    h, w, _ = rgb.shape
    corners = np.stack([rgb[0, 0], rgb[0, -1], rgb[-1, 0], rgb[-1, -1]])
    corner_diff = int(np.max(np.abs(corners - np.array(expected_edge_rgb, dtype=np.float32))))
    if corner_diff > 18:
        issues.append(f"{label} corner backdrop mismatch: max_diff={corner_diff}")
        return False

    hsv = cv2.cvtColor(rgb.astype(np.uint8), cv2.COLOR_RGB2HSV).astype(np.float32)
    sat = hsv[:, :, 1]
    luma = 0.299 * rgb[:, :, 0] + 0.587 * rgb[:, :, 1] + 0.114 * rgb[:, :, 2]
    bmr = rgb[:, :, 2] - rgb[:, :, 0]

    # Brain tissue interior has bright green/blue relative to pure red backdrop (where R > 125 and G <= 45)
    fg_brain = (rgb[:, :, 1] > 85.0) & (rgb[:, :, 2] > 85.0)
    fg_count = int(fg_brain.sum())
    if fg_count < 20_000:
        issues.append(f"{label} extracted cyan/gypsum brain pixels too small: {fg_count}")
        return False

    cyan_frac = float((fg_brain & (bmr >= 60.0) & (sat >= 90.0)).sum()) / fg_count
    gypsum_frac = float((fg_brain & (sat <= 45.0) & (luma >= 150.0)).sum()) / fg_count

    # Zero dark navy/purple rim dip along the <= 4px upper/lateral perimeter adjacent to the red backdrop (y < 430);
    # preserve genuine shaded deep-cyan cortical vessels (R <= 15, G >= 50, B >= 90, B - R >= 60) inside sulci.
    upper_roi = rgb[:430, :, :]
    upper_luma = luma[:430, :]
    red_bg = (upper_roi[:, :, 0] > 110.0) & (upper_roi[:, :, 1] < 65.0) & (upper_roi[:, :, 2] < 65.0)
    rim_zone = (cv2.dilate(red_bg.astype(np.uint8), np.ones((9, 9), np.uint8)) > 0) & (~red_bg)
    shaded_cyan_vessel = (
        (upper_roi[:, :, 0] <= 15.0)
        & (upper_roi[:, :, 1] >= 50.0)
        & (upper_roi[:, :, 2] >= 90.0)
        & ((upper_roi[:, :, 2] - upper_roi[:, :, 0]) >= 60.0)
    )
    dark_dip = rim_zone & (~shaded_cyan_vessel) & (
        (upper_luma < 75.0)
        | (
            (upper_roi[:, :, 2] > upper_roi[:, :, 0] * 0.55)
            & (upper_roi[:, :, 0] < 150.0)
            & (upper_roi[:, :, 1] < 90.0)
        )
    )
    navy_dip_count = int(dark_dip.sum())

    ok = (cyan_frac >= 0.08) and (gypsum_frac >= 0.25) and (navy_dip_count == 0)
    if not ok:
        issues.append(
            f"{label} red-bg fringe/purity check failed: cyan_frac={cyan_frac:.3f}, "
            f"gypsum_frac={gypsum_frac:.3f}, navy_dip_pixels={navy_dip_count}"
        )
    return ok


def _build_3d_extruded_brain_slices(
    src_path: Path,
    *,
    dual_red: bool,
    num_slices: int = 10,
) -> tuple[list[dict[str, Any]], np.ndarray]:
    """
    Slice fringe-free A02 lateral Ep #31 brain into `num_slices` vertical slabs with
    1-point perspective 3D extruded MRI cross-section walls facing banner center.
    """
    cropped = _extract_fringe_free_cyan_brain_rgba(src_path)
    ch, cw = cropped.shape[:2]
    brain_w = 460
    brain_h = int(round(brain_w * (ch / cw)))  # ~412px: floats unclipped inside y=508..931 strip!
    resized = np.array(
        Image.fromarray(cropped, mode="RGBA").resize((brain_w, brain_h), resample=Image.Resampling.LANCZOS),
        dtype=np.uint8,
    )

    face_w = brain_w // num_slices
    cy = brain_h * 0.5
    yy = np.arange(brain_h, dtype=np.float32)

    slices: list[dict[str, Any]] = []
    for idx in range(num_slices):
        x0 = idx * face_w
        x1 = brain_w if idx == num_slices - 1 else (idx + 1) * face_w
        face = resized[:, x0:x1, :].copy()
        fw = face.shape[1]

        # Smooth 0.65px vertical cut alpha antialiasing
        edge_ramp = np.ones(fw, dtype=np.float32)
        edge_ramp[0] = 0.72
        edge_ramp[-1] = 0.72
        face[:, :, 3] = np.clip(face[:, :, 3].astype(np.float32) * edge_ramp[None, :], 0.0, 255.0).astype(np.uint8)

        # Left 5 slabs (0..4) face right toward center; Right 5 slabs (5..9) face left toward center
        is_left_side = idx < (num_slices // 2)
        extrude_side = "right" if is_left_side else "left"
        dist_from_center = ((num_slices // 2 - 1) - idx) if is_left_side else (idx - (num_slices // 2))
        extrude_w = 10 + 2 * dist_from_center  # 10..18px perspective depth

        edge_src = face[:, -2, :].astype(np.float32) if is_left_side else face[:, 1, :].astype(np.float32)
        wall = np.zeros((brain_h, extrude_w, 4), dtype=np.uint8)

        if dual_red and not is_left_side:
            wall_glow = np.array([232.0, 42.0, 30.0], dtype=np.float32)
            front_rim = np.array([255.0, 175.0, 168.0], dtype=np.float32)
            back_rim = np.array([235.0, 46.0, 34.0], dtype=np.float32)
        else:
            wall_glow = np.array([18.0, 152.0, 202.0], dtype=np.float32)
            front_rim = np.array([182.0, 246.0, 255.0], dtype=np.float32)
            back_rim = np.array([39.0, 216.0, 255.0], dtype=np.float32)

        for d in range(extrude_w):
            t = float(d) / max(1.0, float(extrude_w - 1))
            # 4.5% vertical perspective convergence toward horizontal horizon center
            y_src = np.clip((yy - cy) / (1.0 - 0.045 * t) + cy, 0.0, float(brain_h - 1))
            y_lo = np.floor(y_src).astype(np.int32)
            y_hi = np.minimum(y_lo + 1, brain_h - 1)
            yf = (y_src - y_lo)[:, None]

            sampled = edge_src[y_lo] * (1.0 - yf) + edge_src[y_hi] * yf
            depth_shade = 1.0 - 0.45 * t
            striation = 0.88 + 0.12 * np.sin(yy * 0.25 + d * 0.42)
            base_col = (sampled[:, :3] * 0.28 + wall_glow[None, :] * 0.72) * depth_shade * striation[:, None]

            if d == 0:
                col = base_col * 0.30 + front_rim[None, :] * 0.70
                a_mul = 0.98
            elif d == 1:
                col = base_col * 0.58 + front_rim[None, :] * 0.42
                a_mul = 0.92
            elif d >= extrude_w - 2:
                col = base_col * 0.45 + back_rim[None, :] * 0.55
                a_mul = 0.78
            else:
                col = base_col
                a_mul = 0.86 - 0.16 * t

            wall_x = d if is_left_side else (extrude_w - 1 - d)
            wall[:, wall_x, :3] = np.clip(col, 0.0, 255.0).astype(np.uint8)
            wall[:, wall_x, 3] = np.clip(sampled[:, 3] * a_mul, 0.0, 255.0).astype(np.uint8)

        slab = np.concatenate([face, wall], axis=1) if is_left_side else np.concatenate([wall, face], axis=1)

        # Crisp micro bevel fold separation on the outer cortical column right beside the bright cut rim
        fold_x = fw - 1 if is_left_side else extrude_w
        slab[:, fold_x, :3] = np.clip(slab[:, fold_x, :3].astype(np.float32) * 0.82, 0.0, 255.0).astype(np.uint8)

        alpha_fg = face[:, :, 3] > 80
        row_has = np.any(alpha_fg, axis=1)
        y_indices = np.where(row_has)[0]
        y_min = int(y_indices.min()) if len(y_indices) else 0
        y_max = int(y_indices.max()) if len(y_indices) else brain_h - 1
        slices.append(
            {
                "index": idx,
                "label": f"S{idx + 1:02d}",
                "rgba": slab,
                "extrude_side": extrude_side,
                "extrude_w": extrude_w,
                "face_w": fw,
                "slab_w": slab.shape[1],
                "slab_h": brain_h,
                "y_span_local": (y_min, y_max),
                "left_profile": face[:, 2, 3] > 64,
                "right_profile": face[:, -3, 3] > 64,
            }
        )
    return slices, resized


def _make_matrix_10slice_backdrop(
    width: int,
    height: int,
    *,
    centers_x: list[int],
    dual_red: bool,
) -> Image.Image:
    """
    Build Johnny Harris obsidian-teal volumetric atmosphere (#06141F -> #14435A -> #266A82)
    with radial god-ray light shafts streaming through inter-slice slits and 2% cinema grain.
    """
    yy, xx = np.mgrid[0:height, 0:width].astype(np.float32)
    nx = (xx - width * 0.5) / (width * 0.52)
    ny = (yy - height * 0.5) / (height * 0.48)

    # Smooth elliptical teal studio wash + wide banner strip illumination
    radial_teal = np.exp(-0.5 * (nx ** 2 * 1.15 + ny ** 2 * 2.15))
    strip_glow = np.exp(-0.5 * (nx ** 2 * 0.65 + ny ** 2 * 5.20))

    obsidian = np.array([6.0, 20.0, 31.0], dtype=np.float32)[None, None, :]
    mid_teal = np.array([20.0, 67.0, 90.0], dtype=np.float32)[None, None, :]
    center_bloom = np.array([38.0, 106.0, 130.0], dtype=np.float32)[None, None, :]

    rgb = obsidian + (mid_teal - obsidian) * np.clip(radial_teal[:, :, None] * 0.92, 0.0, 1.0)
    rgb = rgb + (center_bloom - mid_teal) * np.clip(strip_glow[:, :, None] * 0.72, 0.0, 1.0)

    # Overhead angled volumetric light shafts streaming softly through inter-slice slits (no vertical bottom pillar)
    ray_source_x = width * 0.5
    ray_source_y = -height * 0.12
    dx_src = xx - ray_source_x
    dy_src = yy - ray_source_y
    r_len = np.sqrt(dx_src ** 2 + dy_src ** 2) + 1e-4
    ray_energy = np.zeros((height, width), dtype=np.float32)

    for i in range(len(centers_x) - 1):
        gx = 0.5 * (centers_x[i] + centers_x[i + 1])
        gy = height * 0.50
        vx = gx - ray_source_x
        vy = gy - ray_source_y
        vnorm = math.hypot(vx, vy) + 1e-4
        ux, uy = vx / vnorm, vy / vnorm
        perp = np.abs(dx_src * uy - dy_src * ux)
        beam_w = 24.0 + 0.048 * r_len
        along = (dx_src * ux + dy_src * uy) / max(1.0, height * 0.58)
        fwd_mask = np.clip((along - 0.15) / 0.45, 0.0, 1.0) * np.exp(-0.5 * np.maximum(0.0, along - 0.95) ** 2 / 0.55)
        weight = 0.24 if i == 4 else 0.34
        ray_energy += np.exp(-0.5 * (perp / beam_w) ** 2) * fwd_mask * weight

    ray_energy = cv2.GaussianBlur(ray_energy, (0, 0), sigmaX=24.0, sigmaY=20.0)
    rgb += np.clip(ray_energy[:, :, None], 0.0, 1.10) * np.array([18.0, 84.0, 114.0], dtype=np.float32)[None, None, :]

    if dual_red:
        # Left cyan / Right TED-Red dual volumetric tension across the open center bullet-time chasm
        cyan_pool = np.exp(-0.5 * (((xx - 860.0) / 360.0) ** 2 + ((yy - 720.0) / 185.0) ** 2))
        red_pool = np.exp(-0.5 * (((xx - 1700.0) / 400.0) ** 2 + ((yy - 720.0) / 185.0) ** 2))
        rgb += cyan_pool[:, :, None] * np.array([8.0, 56.0, 74.0], dtype=np.float32)[None, None, :]
        rgb += red_pool[:, :, None] * np.array([84.0, 12.0, 14.0], dtype=np.float32)[None, None, :]

    # Deterministic ~2% Gaussian cinema film grain across full 2560x1440 master
    rng = np.random.default_rng(41010 if not dual_red else 41011)
    grain = rng.normal(0.0, 4.4, size=(height, width, 1)).astype(np.float32)
    rgb = rgb + grain

    return Image.fromarray(np.clip(rgb, 0.0, 255.0).astype(np.uint8), mode="RGB")


def _draw_rotated_alpha_stamp(
    layer: Image.Image,
    pos_xy: tuple[int, int],
    text: str,
    *,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    color_rgba: tuple[int, int, int, int],
    angle_deg: float,
) -> None:
    """Paste slightly tilted low-opacity handwritten Johnny Harris lab annotation onto RGBA layer."""
    dummy = ImageDraw.Draw(Image.new("RGBA", (10, 10), (0, 0, 0, 0)))
    bb = dummy.textbbox((0, 0), text, font=font)
    tw = max(4, int(math.ceil(bb[2] - bb[0])) + 16)
    th = max(4, int(math.ceil(bb[3] - bb[1])) + 16)
    stamp = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(stamp)
    sdraw.text((8 - bb[0], 8 - bb[1]), text, font=font, fill=color_rgba)
    rotated = stamp.rotate(angle_deg, resample=Image.Resampling.BICUBIC, expand=True)
    layer.alpha_composite(rotated, dest=pos_xy)


def _draw_matrix_kinetic_trails_and_hud(
    canvas_rgba: Image.Image,
    *,
    slices: list[dict[str, Any]],
    centers_x: list[int],
    y_centers: list[int],
    dual_red: bool,
) -> Image.Image:
    """
    Render Matrix bullet-time horizontal motion-echo trails, silhouette-locked cyan/red
    synaptic bridges, floating micro sparks, MRI index ruler, and Johnny Harris wing notes.
    """
    w, h = canvas_rgba.size
    trail_glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    trail_core = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    tdraw_glow = ImageDraw.Draw(trail_glow)
    tdraw_core = ImageDraw.Draw(trail_core)

    rng = np.random.default_rng(91021 if not dual_red else 91022)

    # 1. Silhouette-locked horizontal Matrix bullet-time trails + synaptic arcs across all 9 gaps
    slab_top_lefts: list[tuple[int, int, int]] = []
    for idx, sl in enumerate(slices):
        sx0 = centers_x[idx] - sl["slab_w"] // 2
        sy0 = y_centers[idx] - sl["slab_h"] // 2
        slab_top_lefts.append((sx0, sy0, sx0 + sl["slab_w"]))

    for idx in range(len(slices) - 1):
        sl_l = slices[idx]
        sl_r = slices[idx + 1]
        _, sy0_l, gx0 = slab_top_lefts[idx]
        gx1, sy0_r, _ = slab_top_lefts[idx + 1]
        if gx1 <= gx0 + 6:
            continue

        # Silhouette envelope rows from left & right cut columns
        prof_l = np.where(sl_l["right_profile"])[0]
        prof_r = np.where(sl_r["left_profile"])[0]
        if len(prof_l) < 10 or len(prof_r) < 10:
            continue
        yl_top, yl_bot = sy0_l + int(prof_l.min()), sy0_l + int(prof_l.max())
        yr_top, yr_bot = sy0_r + int(prof_r.min()), sy0_r + int(prof_r.max())

        # Silky horizontal bullet-time motion-echo smear (zero hard ghost cut rectangles)
        ghost_arr = sl_l["rgba"].astype(np.float32)
        ghost_arr[:, :, :3] = ghost_arr[:, :, :3] * 0.32 + np.array(
            [230.0, 43.0, 30.0] if (dual_red and idx >= 5) else [39.0, 216.0, 255.0],
            dtype=np.float32,
        ) * 0.68
        ghost_blur = cv2.GaussianBlur(ghost_arr, (37, 5), sigmaX=14.0, sigmaY=1.2)
        for g_step, g_frac in enumerate((0.15, 0.34, 0.54)):
            g_x = int(round(slab_top_lefts[idx][0] + (gx1 - gx0) * g_frac))
            g_mul = (0.14, 0.09, 0.05)[g_step]
            ga = ghost_blur.copy()
            ga[:, :, 3] = np.clip(ga[:, :, 3] * g_mul, 0.0, 255.0)
            trail_glow.alpha_composite(Image.fromarray(ga.astype(np.uint8), mode="RGBA"), dest=(g_x, sy0_l))

        # Varied-length bullet-time horizontal motion streaks inside brain silhouette Y bounds
        y_start = max(yl_top, yr_top) + 14
        y_end = min(yl_bot, yr_bot) - 14
        if y_end > y_start + 30:
            gap_span = gx1 - gx0
            for s_idx in range(10):
                frac = (s_idx + 0.5) / 10.0
                yb = int(round(y_start + frac * (y_end - y_start) + rng.uniform(-7.0, 7.0)))
                sx_a = gx0 + int(gap_span * rng.uniform(0.02, 0.22))
                sx_b = gx1 - int(gap_span * rng.uniform(0.02, 0.22))
                if sx_b <= sx_a + 12:
                    sx_a, sx_b = gx0, gx1
                s_red = dual_red and (idx >= 5 or (idx == 4 and s_idx % 2 == 1))
                sg_c = (230, 43, 30, 76) if s_red else (39, 216, 255, 58)
                sc_c = (255, 175, 168, 62) if s_red else (195, 248, 255, 48)
                tdraw_glow.line((sx_a, yb, sx_b, yb), fill=sg_c, width=3)
                tdraw_core.line((sx_a, yb, sx_b, yb), fill=sc_c, width=1)

            # 6 curved glowing synaptic neural filaments bridging S_i <-> S_{i+1}
            for a_idx in range(6):
                ya = int(rng.integers(y_start, y_end))
                yb_end = int(np.clip(ya + rng.integers(-42, 43), y_start, y_end))
                amp = float(rng.uniform(-20.0, 20.0))
                pts: list[tuple[float, float]] = []
                for step_k in range(19):
                    u = step_k / 18.0
                    px_k = gx0 + (gx1 - gx0) * u
                    py_k = ya * (1.0 - u) + yb_end * u + amp * math.sin(math.pi * u)
                    pts.append((px_k, py_k))
                use_red = dual_red and (idx >= 4 and (idx >= 5 or a_idx % 2 == 0))
                glow_c = (232, 43, 30, 195 if idx >= 4 else 145) if use_red else (39, 216, 255, 145)
                core_c = (255, 172, 164, 210) if use_red else (218, 252, 255, 165)
                tdraw_glow.line(pts, fill=glow_c, width=4)
                tdraw_core.line(pts, fill=core_c, width=1)

            # Floating frozen bullet-time sparks inside the gap
            for _ in range(11):
                px_p = int(rng.integers(gx0 + 6, max(gx0 + 8, gx1 - 6)))
                py_p = int(rng.integers(y_start - 14, y_end + 14))
                pr = int(rng.integers(2, 5))
                is_red_p = dual_red and (px_p > w * 0.44 or rng.random() < 0.42)
                pg_c = (232, 43, 30, 205) if is_red_p else (39, 216, 255, 175)
                pc_c = (255, 200, 194, 235) if is_red_p else (230, 252, 255, 220)
                tdraw_glow.ellipse((px_p - pr - 2, py_p - pr - 2, px_p + pr + 2, py_p + pr + 2), fill=pg_c)
                tdraw_core.ellipse((px_p - max(1, pr - 1), py_p - max(1, pr - 1), px_p + max(1, pr - 1), py_p + max(1, pr - 1)), fill=pc_c)

    # 2. Subtle holographic laser scanline pulse (Cyan on MX-A; crisp #E62B1E TED-Red on MX-B)
    if dual_red:
        tdraw_glow.line((200, 560, 2360, 560), fill=(232, 43, 30, 190), width=7)
        tdraw_core.line((200, 560, 2360, 560), fill=(255, 118, 108, 235), width=2)
        tdraw_glow.line((260, 882, 2300, 882), fill=(232, 43, 30, 145), width=5)
        tdraw_core.line((260, 882, 2300, 882), fill=(255, 128, 118, 195), width=2)
    else:
        tdraw_glow.line((220, 560, 2340, 560), fill=(39, 216, 255, 84), width=4)
        tdraw_core.line((220, 560, 2340, 560), fill=(195, 248, 255, 96), width=1)

    # Directional horizontal blur on glow pass + crisp blend of core pass
    trail_glow_blurred = trail_glow.filter(ImageFilter.GaussianBlur(radius=6.0))
    canvas_rgba = Image.alpha_composite(canvas_rgba, trail_glow_blurred)
    canvas_rgba = Image.alpha_composite(canvas_rgba, trail_core)

    # 3. Johnny Harris subtle HUD ruler ticks, outer EEG waveform, & handwritten PatrickHand wing notes
    hud_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    hdraw = ImageDraw.Draw(hud_layer)
    f_mono = _load_font(MONO_FONT, 14)
    f_hand = _load_font(PATRICK_HAND_FONT, 26)

    # Subtle outer EEG trace threads in far desktop wings (x = 18..145 and x = 2415..2542)
    for wing_x0, wing_x1, fade_left in ((18, 148, False), (2412, 2542, True)):
        for ch_idx, y_base in enumerate((596, 650, 774)):
            pts_eeg: list[tuple[float, float]] = []
            for xk in range(wing_x0, wing_x1 + 1, 3):
                yk = y_base + 11.0 * math.sin(xk * 0.08 + ch_idx * 1.3) * math.cos(xk * 0.023)
                pts_eeg.append((float(xk), yk))
            eeg_c = (230, 43, 30, 40) if (dual_red and ch_idx == 1 and fade_left) else (99, 178, 199, 38)
            hdraw.line(pts_eeg, fill=eeg_c, width=1)

    # Fine MRI ruler ticks in TV bleed cleanly outside SAFE_ZONE_BOX (y = 950..978 and y = 468..490)
    hdraw.line((150, 488, 2410, 488), fill=(99, 178, 199, 38), width=1)
    hdraw.line((150, 954, 2410, 954), fill=(99, 178, 199, 44), width=1)
    for idx, cx in enumerate(centers_x):
        hdraw.line((cx, 480, cx, 494), fill=(39, 216, 255, 68), width=1)
        hdraw.line((cx, 948, cx, 962), fill=(39, 216, 255, 76), width=1)
        lbl = f"S{idx + 1:02d}"
        hdraw.text((cx, 974), lbl, font=f_mono, fill=(140, 214, 232, 74), anchor="mm")

    # Minimal MNI152 telemetry headers inside upper/lower TV zones (zero clutter on banner strip)
    hdraw.text((60, 248), "MNI152  3.0T  CORONAL EXPANSION  //  10 SLABS", font=f_mono, fill=(140, 214, 232, 54))
    hdraw.text((2500, 248), "BULLET-TIME VELOCITY LOCK  ·  ΔX 14.0mm", font=f_mono, fill=(140, 214, 232, 54), anchor="ra")
    hdraw.text((60, 1188), "CORTICAL VESSEL TRACE: SULCAL CYAN #27D8FF", font=f_mono, fill=(140, 214, 232, 50))
    hdraw.text((2500, 1188), "ALL ABOUT BRAIN  ·  NEURAL ARCHITECTURE SERIES", font=f_mono, fill=(140, 214, 232, 50), anchor="ra")

    # Delicate low-opacity Johnny Harris PatrickHand field-journal annotations in outer TV & far margins
    _draw_rotated_alpha_stamp(hud_layer, (42, 310), "fMRI 3T · MNI152", font=f_hand, color_rgba=(186, 228, 240, 46), angle_deg=-2.5)
    _draw_rotated_alpha_stamp(hud_layer, (44, 1086), "PFC -> striatum", font=f_hand, color_rgba=(186, 228, 240, 44), angle_deg=1.8)
    _draw_rotated_alpha_stamp(hud_layer, (2260, 310), "N=49 · p<0.001", font=f_hand, color_rgba=(186, 228, 240, 46), angle_deg=2.2)
    _draw_rotated_alpha_stamp(hud_layer, (2210, 1086), "hippocampal replay", font=f_hand, color_rgba=(186, 228, 240, 44), angle_deg=-1.8)

    return Image.alpha_composite(canvas_rgba, hud_layer)


def _apply_scifi_slab_depth_pass(
    slab_rgba: np.ndarray,
    *,
    blur_radius: float,
    mist_blend: float,
) -> Image.Image:
    """Apply subtle Z-depth mist & shallow lens softening to outermost bullet-time brain slices."""
    im = Image.fromarray(slab_rgba, mode="RGBA")
    if blur_radius > 0.05:
        im = im.filter(ImageFilter.GaussianBlur(radius=blur_radius))
    if mist_blend > 0.0:
        arr = np.array(im, dtype=np.float32)
        mist_col = np.array([20.0, 67.0, 90.0], dtype=np.float32)[None, None, :]
        arr[:, :, :3] = arr[:, :, :3] * (1.0 - mist_blend) + mist_col * mist_blend
        im = Image.fromarray(np.clip(arr, 0.0, 255.0).astype(np.uint8), mode="RGBA")
    return im


def build_banner_matrix_10slice(out_path: Path, *, variant: str) -> dict[str, Any]:
    """
    Build 2560x1440 Johnny Harris Sci-Fi 10-Slice Exploded Matrix Bullet-Time Banner:
      - variant='matrix_10slice_A_cyan': Uniform 10-slice Matrix bullet-time across full banner.
      - variant='matrix_10slice_B_dual': 10-slice center-window shockwave + #E62B1E / #27D8FF dual energy.
    """
    dual_red = str(variant).strip() == "matrix_10slice_B_dual"
    src_path = SOURCE_ASSETS["a02_lateral_cand02"]
    slices, _ = _build_3d_extruded_brain_slices(src_path, dual_red=dual_red, num_slices=10)

    if dual_red:
        centers_x = [200, 392, 584, 776, 968, 1592, 1784, 1976, 2168, 2360]
    else:
        centers_x = [210, 448, 686, 924, 1140, 1420, 1636, 1874, 2112, 2350]

    # Bullet-time suspended vertical slow-motion wave kept strictly inside y=508..931 strip
    y_centers = [720 + int(round(5.0 * math.sin(i * 0.78 - 0.5))) for i in range(10)]

    backdrop = _make_matrix_10slice_backdrop(BANNER_W, BANNER_H, centers_x=centers_x, dual_red=dual_red)
    canvas = backdrop.convert("RGBA")

    # 1. Bullet-time motion-echo trails, cyan/red synaptic bridges, sparks & wing field notes
    canvas = _draw_matrix_kinetic_trails_and_hud(
        canvas,
        slices=slices,
        centers_x=centers_x,
        y_centers=y_centers,
        dual_red=dual_red,
    )

    # 2. Composite suspended 3D-extruded brain slices with soft shadows & atmospheric Z-depth
    shadow_layer = Image.new("RGBA", (BANNER_W, BANNER_H), (0, 0, 0, 0))
    slab_layer = Image.new("RGBA", (BANNER_W, BANNER_H), (0, 0, 0, 0))
    slice_spans: list[dict[str, Any]] = []

    for idx, sl in enumerate(slices):
        cx = centers_x[idx]
        cy = y_centers[idx]
        x0 = cx - sl["slab_w"] // 2
        y0 = cy - sl["slab_h"] // 2
        slice_spans.append({"label": sl["label"], "cx": cx, "cy": cy, "x0": x0, "x1": x0 + sl["slab_w"]})

        if idx in (0, 9):
            slab_im = _apply_scifi_slab_depth_pass(sl["rgba"], blur_radius=0.85, mist_blend=0.14)
        elif idx in (1, 8):
            slab_im = _apply_scifi_slab_depth_pass(sl["rgba"], blur_radius=0.30, mist_blend=0.06)
        else:
            slab_im = _apply_scifi_slab_depth_pass(sl["rgba"], blur_radius=0.0, mist_blend=0.0)

        a_ch = slab_im.split()[3].point(lambda a: int(round(a * 0.30)))
        sh = Image.new("RGBA", slab_im.size, (3, 10, 18, 255))
        sh.putalpha(a_ch)
        sh_off_x = -8 if idx < 5 else 8
        shadow_layer.alpha_composite(sh, dest=(x0 + sh_off_x, y0 + 14))
        slab_layer.alpha_composite(slab_im, dest=(x0, y0))

    canvas = Image.alpha_composite(canvas, shadow_layer.filter(ImageFilter.GaussianBlur(radius=10.0)))
    canvas = Image.alpha_composite(canvas, slab_layer)

    # 3. Elliptical dark obsidian-teal readability scrim behind movie-poster title block
    yy, xx = np.mgrid[0:BANNER_H, 0:BANNER_W].astype(np.float32)
    scrim_r2 = ((xx - BANNER_W * 0.5) / 500.0) ** 2 + ((yy - 716.0) / 132.0) ** 2
    scrim_peak = 178.0 if dual_red else 206.0
    scrim_alpha = np.clip(np.exp(-0.5 * scrim_r2) * scrim_peak, 0.0, 230.0).astype(np.uint8)
    scrim_arr = np.zeros((BANNER_H, BANNER_W, 4), dtype=np.uint8)
    scrim_arr[:, :, :3] = np.array([5, 15, 24], dtype=np.uint8)
    scrim_arr[:, :, 3] = scrim_alpha
    canvas = Image.alpha_composite(canvas, Image.fromarray(scrim_arr, mode="RGBA"))

    # 4. Crisp Movie-Poster Typography Lockup strictly inside SAFE_ZONE_BOX [507..2053, 508..931]
    text_layer = Image.new("RGBA", (BANNER_W, BANNER_H), (0, 0, 0, 0))
    tdraw = ImageDraw.Draw(text_layer)

    f_eyebrow = _load_font(PRIMARY_BODY_FONT, 24, weight=700)
    f_sub = _load_font(PRIMARY_BODY_FONT, 23, weight=600)

    # Auto-fit wide-tracked hero title within <= 920px center width
    hero_size = 80
    hero_track = 13
    while hero_size >= 64:
        f_title = _load_font(PRIMARY_BODY_FONT, hero_size, weight=850)
        advs = [float(tdraw.textlength(ch, font=f_title)) for ch in "ALL ABOUT BRAIN"]
        tot_w = sum(advs) + hero_track * (len("ALL ABOUT BRAIN") - 1)
        if tot_w <= 920:
            break
        if hero_track > 8:
            hero_track -= 1
        else:
            hero_size -= 2

    # Eyebrow with #E62B1E live documentary dot
    eyebrow_text = "PEER-REVIEWED NEUROSCIENCE"
    eyebrow_adv = sum(float(tdraw.textlength(ch, font=f_eyebrow)) for ch in eyebrow_text) + 7 * (len(eyebrow_text) - 1)
    dot_r = 5
    dot_gap = 16
    eyebrow_total_w = dot_r * 2 + dot_gap + eyebrow_adv
    eyebrow_start_x = BANNER_W * 0.5 - eyebrow_total_w * 0.5
    eyebrow_cy = 602
    tdraw.ellipse((eyebrow_start_x, eyebrow_cy - dot_r, eyebrow_start_x + dot_r * 2, eyebrow_cy + dot_r), fill=(230, 43, 30, 255))
    eyebrow_text_cx = int(round(eyebrow_start_x + dot_r * 2 + dot_gap + eyebrow_adv * 0.5))
    eyebrow_bbox = _draw_tracked_segments(
        tdraw,
        eyebrow_text_cx,
        590,
        [(eyebrow_text, (216, 236, 245, 255))],
        f_eyebrow,
        tracking_px=7,
    )

    title_bbox = _draw_tracked_segments(
        tdraw,
        BANNER_W // 2,
        662,
        [("ALL ABOUT BRAIN", (248, 250, 252, 255))],
        f_title,
        tracking_px=hero_track,
    )

    rule_y = 766
    tdraw.rectangle((BANNER_W // 2 - 220, rule_y, BANNER_W // 2 - 18, rule_y + 1), fill=(99, 178, 199, 150))
    tdraw.rectangle((BANNER_W // 2 + 18, rule_y, BANNER_W // 2 + 220, rule_y + 1), fill=(99, 178, 199, 150))
    tdraw.ellipse((BANNER_W // 2 - 4, rule_y - 4, BANNER_W // 2 + 4, rule_y + 4), fill=(230, 43, 30, 255))

    sub_bbox = _draw_tracked_segments(
        tdraw,
        BANNER_W // 2,
        794,
        [
            ("REAL STUDIES", (180, 220, 235, 255)),
            ("  ·  ", (230, 43, 30, 255)),
            ("INSIDE THE HUMAN MIND", (180, 220, 235, 255)),
        ],
        f_sub,
        tracking_px=6,
    )

    text_arr = np.array(text_layer)
    tys, txs = np.where(text_arr[:, :, 3] > 8)
    ink_union_bbox = (int(txs.min()), int(tys.min()), int(txs.max()) + 1, int(tys.max()) + 1)
    if not (
        ink_union_bbox[0] >= 607
        and ink_union_bbox[1] >= SAFE_ZONE_BOX[1]
        and ink_union_bbox[2] <= 1953
        and ink_union_bbox[3] <= SAFE_ZONE_BOX[3]
    ):
        raise RuntimeError(f"Matrix banner text bbox {ink_union_bbox} breached safe zone {SAFE_ZONE_BOX}")

    # Soft glyph-hugging dark shadow behind text_layer for razor legibility
    text_shadow = Image.new("RGBA", (BANNER_W, BANNER_H), (4, 12, 20, 255))
    text_shadow.putalpha(text_layer.split()[3].point(lambda a: int(round(a * 0.90))))
    text_shadow = text_shadow.filter(ImageFilter.GaussianBlur(radius=12.0))
    canvas = Image.alpha_composite(canvas, text_shadow)
    canvas = Image.alpha_composite(canvas, text_layer)

    final_rgb = canvas.convert("RGB")
    _atomic_save_image(final_rgb, out_path, format="PNG", optimize=True)

    return {
        "file": out_path.name,
        "width": BANNER_W,
        "height": BANNER_H,
        "variant": variant,
        "slice_count": 10,
        "slice_spans": slice_spans,
        "source_asset": str(src_path.relative_to(WORKSPACE_ROOT)),
        "safe_zone_box": list(SAFE_ZONE_BOX),
        "desktop_zone_box": list(DESKTOP_ZONE_BOX),
        "text_bboxes": {
            "eyebrow": list(eyebrow_bbox),
            "title": list(title_bbox),
            "subhead": list(sub_bbox),
            "combined_ink_union": list(ink_union_bbox),
        },
        "sha256": _sha256_file(out_path),
        "bytes": out_path.stat().st_size,
    }


def build_banner_matrix_10slice_a(out_path: Path) -> dict[str, Any]:
    """Concept MX-A: Uniform 10-slice Matrix bullet-time cyan brain banner."""
    return build_banner_matrix_10slice(out_path, variant="matrix_10slice_A_cyan")


def build_banner_matrix_10slice_b(out_path: Path) -> dict[str, Any]:
    """Concept MX-B: 10-slice center-window + cyan/TED-Red dual bullet-time pulse banner."""
    return build_banner_matrix_10slice(out_path, variant="matrix_10slice_B_dual")


def _draw_two_banner_mock_comparison_sheet(
    out_path: Path,
    *,
    header_title: str,
    header_sub: str,
    header_accent_rgb: tuple[int, int, int],
    ted_red_logo_path: Path,
    cards: list[tuple[str, str, str, tuple[int, int, int], Path]],
    strip_labels: tuple[str, str, str],
) -> dict[str, Any]:
    """
    Shared 2400x2660 2-card YouTube banner comparison board showing:
      - Full 2560x423 Desktop strip + green dashed 1546x423 Mobile Safe Zone
      - Live Desktop & Mobile #0F0F0F YouTube Channel Headers paired with Option 1 TED Red avatar
      - Full 2560x1440 TV 16:9 vertical bleed preview
    """
    board_w, board_h = 2400, 2660
    board = Image.new("RGB", (board_w, board_h), (7, 11, 22))
    draw = ImageDraw.Draw(board)

    f_hdr = _load_font(PRIMARY_DISPLAY_FONT, 48)
    f_hdr_sub = _load_font(PRIMARY_BODY_FONT, 20, weight=500)
    f_card_title = _load_font(PRIMARY_DISPLAY_FONT, 32)
    f_card_sub = _load_font(PRIMARY_BODY_FONT, 18, weight=450)
    f_badge = _load_font(PRIMARY_BODY_FONT, 15, weight=700)
    f_ui_bold = _load_font(PRIMARY_BODY_FONT, 20, weight=700)
    f_ui_sm = _load_font(PRIMARY_BODY_FONT, 14, weight=600)
    f_ui_tiny = _load_font(PRIMARY_BODY_FONT, 13, weight=500)

    draw.rectangle((0, 0, board_w, 116), fill=(10, 16, 30))
    draw.text((48, 28), header_title, fill=(255, 255, 255), font=f_hdr)
    draw.text((48, 84), header_sub, fill=header_accent_rgb, font=f_hdr_sub)
    draw.line((0, 116, board_w, 116), fill=header_accent_rgb, width=2)

    with Image.open(ted_red_logo_path) as lim:
        avatar_rgb = lim.convert("RGB")
    av_84 = _make_circular_avatar(avatar_rgb, 84)
    av_60 = _make_circular_avatar(avatar_rgb, 60)

    margin_x = 48
    card_w = board_w - 2 * margin_x  # 2304px
    card_h = 1220
    gap_y = 32
    left_lbl, mid_lbl, right_lbl = strip_labels

    for idx, (title, subtitle, tag, accent_rgb, bpath) in enumerate(cards):
        cy = 140 + idx * (card_h + gap_y)
        draw.rounded_rectangle((margin_x, cy, margin_x + card_w, cy + card_h), radius=16, fill=(11, 17, 32), outline=accent_rgb, width=3)
        draw.rounded_rectangle((margin_x + 24, cy + 18, margin_x + 256, cy + 48), radius=6, fill=accent_rgb)
        draw.text((margin_x + 140, cy + 33), tag, fill=(4, 7, 17), font=f_badge, anchor="mm")
        draw.text((margin_x + 274, cy + 16), title, fill=(255, 255, 255), font=f_card_title)
        draw.text((margin_x + 24, cy + 56), subtitle, fill=(148, 163, 184), font=f_card_sub)

        with Image.open(bpath) as bim:
            banner_full = bim.convert("RGB")

        strip_crop = banner_full.crop(DESKTOP_ZONE_BOX)
        disp_w = card_w - 48  # 2256px
        disp_h = int(round(disp_w * (423.0 / 2560.0)))  # 373px
        sx = margin_x + 24
        sy = cy + 94
        board.paste(strip_crop.resize((disp_w, disp_h), resample=Image.Resampling.LANCZOS), (sx, sy))
        draw.rectangle((sx, sy, sx + disp_w, sy + disp_h), outline=(64, 84, 112), width=2)

        mob_x0 = sx + int(round(disp_w * (SAFE_ZONE_BOX[0] / float(BANNER_W))))
        mob_x1 = sx + int(round(disp_w * (SAFE_ZONE_BOX[2] / float(BANNER_W))))
        _draw_dashed_rect(draw, (mob_x0, sy + 2, mob_x1, sy + disp_h - 2), outline=(34, 197, 94), width=3, dash=18, gap=10)
        draw.text((sx + 10, sy + disp_h + 8), left_lbl, fill=(148, 163, 184), font=f_ui_tiny)
        draw.text(((mob_x0 + mob_x1) // 2, sy + disp_h + 8), mid_lbl, fill=(34, 197, 94), font=f_ui_sm, anchor="mt")
        draw.text((sx + disp_w - 10, sy + disp_h + 8), right_lbl, fill=(148, 163, 184), font=f_ui_tiny, anchor="ra")

        row_y = sy + disp_h + 46
        panel_h = 668
        p1_w = 1040
        p2_w = 576
        p3_w = disp_w - p1_w - p2_w - 40  # 600px

        p1_x = sx
        draw.rounded_rectangle((p1_x, row_y, p1_x + p1_w, row_y + panel_h), radius=12, fill=(15, 15, 15), outline=(48, 62, 84), width=1)
        draw.text((p1_x + 18, row_y + 14), "DESKTOP YOUTUBE HEADER PREVIEW (#0F0F0F + OPTION 1 TED RED AVATAR)", fill=(170, 170, 170), font=f_ui_tiny)
        desk_w = p1_w - 36
        desk_h = int(round(desk_w * (423.0 / 2560.0)))
        board.paste(strip_crop.resize((desk_w, desk_h), resample=Image.Resampling.LANCZOS), (p1_x + 18, row_y + 42))
        board.paste(av_84, (p1_x + 36, row_y + 42 + desk_h + 24), mask=av_84.split()[3])
        draw.text((p1_x + 138, row_y + 42 + desk_h + 28), "All About Brain", fill=(255, 255, 255), font=f_ui_bold)
        draw.text((p1_x + 138, row_y + 42 + desk_h + 56), "@AllAboutBrainOfficial · Peer-reviewed neuroscience", fill=(170, 170, 170), font=f_ui_sm)
        btn_y = row_y + 42 + desk_h + 84
        draw.rounded_rectangle((p1_x + 138, btn_y, p1_x + 252, btn_y + 34), radius=17, fill=(255, 255, 255))
        draw.text((p1_x + 195, btn_y + 17), "Subscribe", fill=(15, 15, 15), font=f_ui_sm, anchor="mm")
        for c_k in range(3):
            kx0 = p1_x + 22 + c_k * 334
            draw.rounded_rectangle((kx0, btn_y + 58, kx0 + 314, row_y + panel_h - 22), radius=10, fill=(24, 24, 24), outline=(42, 42, 42), width=1)
            draw.text((kx0 + 157, (btn_y + 58 + row_y + panel_h - 22) // 2), f"Shorts Slot #{c_k + 1}", fill=(95, 105, 120), font=f_ui_sm, anchor="mm")

        p2_x = p1_x + p1_w + 20
        draw.rounded_rectangle((p2_x, row_y, p2_x + p2_w, row_y + panel_h), radius=12, fill=(15, 15, 15), outline=(48, 62, 84), width=1)
        draw.text((p2_x + 18, row_y + 14), "MOBILE YOUTUBE HEADER PREVIEW (1546×423 CROP)", fill=(170, 170, 170), font=f_ui_tiny)
        mob_crop = banner_full.crop(SAFE_ZONE_BOX)
        mob_pw = p2_w - 36
        mob_ph = int(round(mob_pw * (423.0 / 1546.0)))
        board.paste(mob_crop.resize((mob_pw, mob_ph), resample=Image.Resampling.LANCZOS), (p2_x + 18, row_y + 42))
        my_hdr = row_y + 42 + mob_ph + 22
        board.paste(av_60, (p2_x + 24, my_hdr), mask=av_60.split()[3])
        draw.text((p2_x + 98, my_hdr + 8), "All About Brain", fill=(255, 255, 255), font=f_ui_bold)
        draw.text((p2_x + 98, my_hdr + 34), "@AllAboutBrainOfficial · Science", fill=(170, 170, 170), font=f_ui_sm)
        sub_y0 = my_hdr + 74
        draw.rounded_rectangle((p2_x + 24, sub_y0, p2_x + p2_w - 24, sub_y0 + 38), radius=19, fill=(255, 255, 255))
        draw.text((p2_x + p2_w // 2, sub_y0 + 19), "Subscribe", fill=(15, 15, 15), font=f_ui_sm, anchor="mm")
        for s_k in range(3):
            sx0 = p2_x + 24 + s_k * 178
            draw.rounded_rectangle((sx0, sub_y0 + 56, sx0 + 164, row_y + panel_h - 22), radius=10, fill=(24, 24, 24), outline=(42, 42, 42), width=1)
            draw.text((sx0 + 82, (sub_y0 + 56 + row_y + panel_h - 22) // 2), "9:16\nShort", fill=(95, 105, 120), font=f_ui_tiny, anchor="mm", align="center")

        p3_x = p2_x + p2_w + 20
        draw.rounded_rectangle((p3_x, row_y, p3_x + p3_w, row_y + panel_h), radius=12, fill=(11, 17, 32), outline=(48, 62, 84), width=1)
        draw.text((p3_x + 18, row_y + 14), "TV 2560×1440 FULL 16:9 VERTICAL BLEED", fill=(170, 170, 170), font=f_ui_tiny)
        tv_w = p3_w - 36
        tv_h = int(round(tv_w * (BANNER_H / float(BANNER_W))))
        tv_y = row_y + 52
        board.paste(banner_full.resize((tv_w, tv_h), resample=Image.Resampling.LANCZOS), (p3_x + 18, tv_y))
        ty_d0 = tv_y + int(round(tv_h * (SAFE_ZONE_BOX[1] / float(BANNER_H))))
        ty_d1 = tv_y + int(round(tv_h * (SAFE_ZONE_BOX[3] / float(BANNER_H))))
        tx_m0 = p3_x + 18 + int(round(tv_w * (SAFE_ZONE_BOX[0] / float(BANNER_W))))
        tx_m1 = p3_x + 18 + int(round(tv_w * (SAFE_ZONE_BOX[2] / float(BANNER_W))))
        _draw_dashed_hline(draw, p3_x + 18, p3_x + 18 + tv_w, ty_d0, fill=(148, 163, 184), width=1)
        _draw_dashed_hline(draw, p3_x + 18, p3_x + 18 + tv_w, ty_d1, fill=(148, 163, 184), width=1)
        _draw_dashed_rect(draw, (tx_m0, ty_d0, tx_m1, ty_d1), outline=(34, 197, 94), width=2, dash=10, gap=6)
        draw.text((p3_x + 18, tv_y + tv_h + 16), "Dashed White/Slate: Desktop 2560×423\nDashed Green: Mobile Safe Zone 1546×423\nOuter: TV 16:9 Atmospheric Bleed + MNI HUD", fill=(148, 163, 184), font=f_ui_sm)

    _atomic_save_image(board, out_path, format="JPEG", quality=94, subsampling=0)
    return {
        "file": out_path.name,
        "width": board_w,
        "height": board_h,
        "mode": "RGB",
        "sha256": _sha256_file(out_path),
        "bytes": out_path.stat().st_size,
    }


def build_matrix_10slice_comparison_sheet(
    out_path: Path,
    *,
    mx_a_path: Path,
    mx_b_path: Path,
    ted_red_logo_path: Path,
) -> dict[str, Any]:
    """Compare MX-A (Uniform 10-Slice Cyan) vs MX-B (Center-Window Dual Cyan/TED-Red)."""
    return _draw_two_banner_mock_comparison_sheet(
        out_path,
        header_title="10-SLICE MATRIX BULLET-TIME BANNERS  —  MX-A (CYAN) vs MX-B (CYAN + TED RED)",
        header_sub="3D EXTRUDED A02 BRAIN SLABS (S01–S10)  ·  JOHNNY HARRIS SCI-FI ATMOSPHERE  ·  PAIRED WITH OPTION 1 TED RED (#E62B1E) AVATAR",
        header_accent_rgb=TED_RED_CENTER_RGB,
        ted_red_logo_path=ted_red_logo_path,
        cards=[
            (
                "CONCEPT MX-A: UNIFORM 10-SLICE MATRIX BULLET-TIME (CYAN)",
                "S01–S10 evenly exploded across 2560px · S03–S08 inside Mobile Safe Zone · holographic cyan trails & volumetric light shafts",
                "MX-A · PURE CYAN",
                CYAN_RGB,
                mx_a_path,
            ),
            (
                "CONCEPT MX-B: 10-SLICE CENTER-WINDOW + CYAN / TED-RED PULSE",
                "Wide bullet-time center shockwave framing title · #E62B1E holographic laser + dual energy rim matching TED Red avatar",
                "MX-B · DUAL CYAN + RED",
                TED_RED_CENTER_RGB,
                mx_b_path,
            ),
        ],
        strip_labels=(
            "LEFT WING (S01–S02)  ·  DESKTOP 2560×423",
            "GREEN DASHED = MOBILE SAFE ZONE 1546×423 (S03–S08 + TITLE 100% INSIDE)",
            "RIGHT WING (S09–S10)  ·  DESKTOP 2560×423",
        ),
    )


def _verify_matrix_10slice_banner_entry(
    output_dir: Path,
    fname: str,
    banner_meta: dict[str, Any],
    issues: list[str],
    label: str,
    *,
    expect_dual_red: bool,
) -> dict[str, Any]:
    """
    Verify 10-slice Matrix bullet-time banner:
      1. Typography ink union strictly inside central region of SAFE_ZONE_BOX.
      2. 10 slices present with >=6 inside Mobile [507..2053] and >=2 per desktop wing.
      3. Strong brain/cyan slab pixels visible inside Mobile Safe Zone and both wings.
      4. Johnny Harris non-dead-black teal atmosphere + cinema film grain on corners.
      5. Dual cyan+TED-Red pulse pixels when expect_dual_red=True.
    """
    bboxes = banner_meta.get("text_bboxes", {})
    union_bb = bboxes.get("combined_ink_union", [])
    text_bounds_ok = False
    if len(union_bb) == 4:
        text_bounds_ok = (
            union_bb[0] >= 607
            and union_bb[1] >= SAFE_ZONE_BOX[1]
            and union_bb[2] <= 1953
            and union_bb[3] <= SAFE_ZONE_BOX[3]
        )
    if not text_bounds_ok:
        issues.append(f"{label} text bbox {union_bb} outside center safe zone")

    spans = banner_meta.get("slice_spans") or []
    mobile_slices = sum(1 for sp in spans if SAFE_ZONE_BOX[0] <= int(sp.get("cx", -1)) <= SAFE_ZONE_BOX[2])
    left_wing_slices = sum(1 for sp in spans if int(sp.get("cx", 9999)) < SAFE_ZONE_BOX[0])
    right_wing_slices = sum(1 for sp in spans if int(sp.get("cx", -1)) > SAFE_ZONE_BOX[2])
    spans_ok = (len(spans) == 10) and (mobile_slices >= 6) and (left_wing_slices >= 2) and (right_wing_slices >= 2)
    if not spans_ok:
        issues.append(
            f"{label} 10-slice geometry check failed: total={len(spans)}, "
            f"mobile={mobile_slices}, left={left_wing_slices}, right={right_wing_slices}"
        )

    fpath = output_dir / fname
    hero_ok = False
    atmosphere_ok = False
    dual_pulse_ok = not expect_dual_red
    if fpath.is_file():
        rgb = np.array(Image.open(fpath).convert("RGB"), dtype=np.float32)
        luma = 0.299 * rgb[:, :, 0] + 0.587 * rgb[:, :, 1] + 0.114 * rgb[:, :, 2]

        # Hero visibility across mobile safe zone and both desktop wings (strip y=508..931)
        mob_roi = rgb[SAFE_ZONE_BOX[1]:SAFE_ZONE_BOX[3], SAFE_ZONE_BOX[0]:SAFE_ZONE_BOX[2]]
        mob_luma = luma[SAFE_ZONE_BOX[1]:SAFE_ZONE_BOX[3], SAFE_ZONE_BOX[0]:SAFE_ZONE_BOX[2]]
        mob_brain_px = int(((mob_luma >= 100.0) & ((mob_roi[:, :, 2] >= 95.0) | (mob_roi[:, :, 1] >= 100.0))).sum())
        left_wing_px = int((luma[SAFE_ZONE_BOX[1]:SAFE_ZONE_BOX[3], 120:SAFE_ZONE_BOX[0]] >= 85.0).sum())
        right_wing_px = int((luma[SAFE_ZONE_BOX[1]:SAFE_ZONE_BOX[3], SAFE_ZONE_BOX[2]:2440] >= 85.0).sum())
        hero_ok = (mob_brain_px >= 18_000) and (left_wing_px >= 5_000) and (right_wing_px >= 5_000)
        if not hero_ok:
            issues.append(
                f"{label} slab hero pixel visibility failed: mob={mob_brain_px}, "
                f"left_wing={left_wing_px}, right_wing={right_wing_px}"
            )

        # Corner teal atmosphere + non-flat cinema film grain
        patch = rgb[8:88, 8:88]
        patch_luma = luma[8:88, 8:88]
        p_mean = patch.mean(axis=(0, 1))
        atmosphere_ok = (
            float(p_mean[2]) > float(p_mean[0])
            and float(p_mean[1]) > float(p_mean[0])
            and float(patch_luma.mean()) >= 10.0
            and float(patch_luma.std()) >= 1.2
        )
        if not atmosphere_ok:
            issues.append(
                f"{label} Johnny Harris teal+grain check failed: mean_rgb={p_mean.tolist()}, "
                f"luma_mean={patch_luma.mean():.2f}, luma_std={patch_luma.std():.2f}"
            )

        if expect_dual_red:
            band = rgb[450:990, :, :]
            red_px = int(((band[:, :, 0] >= 150.0) & ((band[:, :, 0] - band[:, :, 2]) >= 80.0)).sum())
            cyan_px = int(((band[:, :, 2] >= 140.0) & ((band[:, :, 2] - band[:, :, 0]) >= 60.0)).sum())
            dual_pulse_ok = (red_px >= 1_500) and (cyan_px >= 12_000)
            if not dual_pulse_ok:
                issues.append(f"{label} dual cyan+red energy check failed: red_px={red_px}, cyan_px={cyan_px}")

    return {
        "safe_zone_box": list(SAFE_ZONE_BOX),
        "combined_ink_union": union_bb,
        "text_bounds_ok": text_bounds_ok,
        "slice_spans_ok": spans_ok,
        "hero_10slice_mobile_and_wings_ok": bool(hero_ok and spans_ok),
        "atmosphere_grain_ok": atmosphere_ok,
        "dual_red_pulse_ok": dual_pulse_ok,
    }


def _make_crimson_echo_backdrop(width: int, height: int, *, seed: int) -> Image.Image:
    """
    Build Johnny Harris deep studio crimson spotlight backdrop:
      Center #C81E1A -> midtone #780E14 -> vignette #3D050A -> edge corners #280306
    with deterministic ~2% cinema film grain (0 dead black, 0 neon-orange clip).
    """
    yy, xx = np.mgrid[0:height, 0:width].astype(np.float32)
    nx = (xx - width * 0.5) / (width * 0.44)
    ny = (yy - height * 0.5) / (height * 0.38)

    spot = np.exp(-0.5 * (nx ** 2 * 1.15 + ny ** 2 * 1.45))
    strip_breath = np.exp(-0.5 * (nx ** 2 * 0.52 + ny ** 2 * 3.80))

    c_edge = np.array([40.0, 3.0, 6.0], dtype=np.float32)[None, None, :]       # #280306
    c_vign = np.array([61.0, 5.0, 10.0], dtype=np.float32)[None, None, :]      # #3D050A
    c_mid = np.array([120.0, 14.0, 20.0], dtype=np.float32)[None, None, :]     # #780E14
    c_hot = np.array([200.0, 30.0, 26.0], dtype=np.float32)[None, None, :]     # #C81E1A

    edge_mix = np.clip(spot * 1.25, 0.0, 1.0)[:, :, None]
    base = c_edge + (c_vign - c_edge) * np.clip((strip_breath * 0.75 + spot * 0.65), 0.0, 1.0)[:, :, None]
    rgb = base + (c_mid - base) * (edge_mix ** 0.90)
    rgb = rgb + (c_hot - c_mid) * (np.clip(spot * 0.85 + strip_breath * 0.25, 0.0, 1.0) ** 1.35)[:, :, None]

    # Clamp pre-grain red below neon-orange clipping while keeping rich crimson bloodline
    rgb[:, :, 0] = np.minimum(rgb[:, :, 0], 206.0)
    rgb[:, :, 1] = np.minimum(rgb[:, :, 1], 34.0)
    rgb[:, :, 2] = np.minimum(rgb[:, :, 2], 30.0)

    rng = np.random.default_rng(seed)
    grain = rng.normal(0.0, 4.3, size=(height, width, 1)).astype(np.float32)
    # Apply balanced luminance grain keeping crimson ratio intact in dark vignette corners
    rgb = rgb + grain * np.array([1.0, 0.42, 0.42], dtype=np.float32)[None, None, :]
    return Image.fromarray(np.clip(rgb, 0.0, 255.0).astype(np.uint8), mode="RGB")


def _build_cyan_mri_hologram_energy(hero_rgba: np.ndarray) -> np.ndarray:
    """
    Extract crisp hollow #27D8FF MRI wireframe + sulcal vessel linework (0 opaque white fill)
    so symmetrical holographic echoes composite cleanly over crimson with zero pink mud.
    """
    rgb = hero_rgba[:, :, :3].astype(np.float32)
    alpha_f = hero_rgba[:, :, 3].astype(np.float32) / 255.0
    fg = (hero_rgba[:, :, 3] > 96).astype(np.uint8)
    fg_pad = cv2.copyMakeBorder(fg, 2, 2, 2, 2, cv2.BORDER_CONSTANT, value=0)
    dist_in = cv2.distanceTransform(fg_pad, cv2.DIST_L2, 5)[2:-2, 2:-2]

    # 1. Crisp single-line outer cortical MRI contour rim
    rim_map = np.exp(-0.5 * ((dist_in - 1.6) / 1.15) ** 2) * alpha_f

    # 2. Sulcal #27D8FF cyan vessels extracted directly via B - R differential
    vessel_map = np.clip((rgb[:, :, 2] - rgb[:, :, 0]) / 80.0, 0.0, 1.0) * alpha_f

    # 3. Topographic cortical gyri wireframe via DoG + Sobel inside dist_in >= 2.6
    luma = 0.299 * rgb[:, :, 0] + 0.587 * rgb[:, :, 1] + 0.114 * rgb[:, :, 2]
    b_fast = cv2.GaussianBlur(luma, (0, 0), sigmaX=1.0, sigmaY=1.0)
    b_slow = cv2.GaussianBlur(luma, (0, 0), sigmaX=3.8, sigmaY=3.8)
    dog = np.maximum(0.0, b_fast - b_slow) / 24.0
    gx = cv2.Sobel(luma, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(luma, cv2.CV_32F, 0, 1, ksize=3)
    sobel = np.sqrt(gx ** 2 + gy ** 2) / 145.0
    interior = np.clip((dist_in - 2.4) / 1.6, 0.0, 1.0) * alpha_f
    gyri_map = np.clip((0.68 * dog + 0.55 * sobel) * interior, 0.0, 1.0)

    # 4. Ultra-subtle hollow glass rim sheen (no opaque solid fill)
    sheen = 0.08 * np.exp(-dist_in / 14.0) * (dist_in > 0).astype(np.float32) * alpha_f

    return np.clip(1.05 * rim_map + 0.96 * vessel_map + 0.66 * gyri_map + sheen, 0.0, 1.0)


def _blend_cyan_energy_onto_crimson(canvas_rgb_f: np.ndarray, energy_full: np.ndarray) -> np.ndarray:
    """
    Optical anti-mud compositor: suppresses underlying crimson red proportionally along
    cyan wireframe energy so luminous #27D8FF/#99F4FF MRI echoes never turn salmon/purple.
    """
    bloom = cv2.GaussianBlur(energy_full, (0, 0), sigmaX=4.2, sigmaY=4.2)
    core = np.clip(energy_full, 0.0, 1.0)
    w_c = np.clip(0.90 * core + 0.46 * bloom, 0.0, 1.0)

    r_keep = (1.0 - np.clip(w_c * 1.38, 0.0, 0.96)) ** 1.5
    gb_keep = 1.0 - 0.46 * w_c
    spec = np.clip((core - 0.58) / 0.42, 0.0, 1.0)

    out = np.empty_like(canvas_rgb_f)
    out[:, :, 0] = canvas_rgb_f[:, :, 0] * r_keep + 24.0 * w_c + 145.0 * spec * 0.45
    out[:, :, 1] = canvas_rgb_f[:, :, 1] * gb_keep + 216.0 * w_c + 34.0 * spec
    out[:, :, 2] = canvas_rgb_f[:, :, 2] * gb_keep + 255.0 * w_c
    return np.clip(out, 0.0, 255.0)


def _stamp_float_energy(dst: np.ndarray, stamp: np.ndarray, x0: int, y0: int, weight: float) -> None:
    """Max-blend scaled 2D holographic energy stamp cleanly within destination bounds."""
    dh, dw = dst.shape
    sh, sw = stamp.shape
    sx0 = max(0, -x0)
    sy0 = max(0, -y0)
    dx0 = max(0, x0)
    dy0 = max(0, y0)
    copy_w = min(sw - sx0, dw - dx0)
    copy_h = min(sh - sy0, dh - dy0)
    if copy_w <= 0 or copy_h <= 0:
        return
    roi_dst = dst[dy0 : dy0 + copy_h, dx0 : dx0 + copy_w]
    roi_src = stamp[sy0 : sy0 + copy_h, sx0 : sx0 + copy_w] * weight
    dst[dy0 : dy0 + copy_h, dx0 : dx0 + copy_w] = np.maximum(roi_dst, roi_src)


def _overlay_crimson_wing_hud(
    canvas_rgba: Image.Image,
    *,
    tick_xs: list[int],
    header_right_label: str,
) -> Image.Image:
    """Overlay delicate low-opacity Johnny Harris wing EEG traces, MNI ticks, and PatrickHand lab notes."""
    hud_layer = Image.new("RGBA", (BANNER_W, BANNER_H), (0, 0, 0, 0))
    hdraw = ImageDraw.Draw(hud_layer)
    f_mono = _load_font(MONO_FONT, 14)
    f_hand = _load_font(PATRICK_HAND_FONT, 26)

    for wing_x0, wing_x1 in ((22, 168), (2392, 2538)):
        for ch_idx, y_base in enumerate((620, 694, 796)):
            pts_eeg: list[tuple[float, float]] = []
            for xk in range(wing_x0, wing_x1 + 1, 3):
                yk = y_base + 10.0 * math.sin(xk * 0.08 + ch_idx * 1.4) * math.cos(xk * 0.025)
                pts_eeg.append((float(xk), yk))
            hdraw.line(pts_eeg, fill=(248, 214, 214, 34), width=1)

    hdraw.line((180, 484, 2380, 484), fill=(248, 214, 214, 32), width=1)
    hdraw.line((180, 956, 2380, 956), fill=(248, 214, 214, 34), width=1)
    for tx in tick_xs:
        hdraw.line((tx, 478, tx, 490), fill=(153, 244, 255, 42), width=1)
        hdraw.line((tx, 950, tx, 962), fill=(153, 244, 255, 44), width=1)

    hdraw.text((58, 244), "MNI152  3.0T  SYMMETRICAL FIELD  //  ALL ABOUT BRAIN", font=f_mono, fill=(248, 214, 214, 38))
    hdraw.text((2502, 244), header_right_label, font=f_mono, fill=(248, 214, 214, 38), anchor="ra")
    _draw_rotated_alpha_stamp(hud_layer, (48, 306), "fMRI 3T · MNI152", font=f_hand, color_rgba=(248, 224, 222, 38), angle_deg=-2.2)
    _draw_rotated_alpha_stamp(hud_layer, (48, 1094), "PFC -> striatum", font=f_hand, color_rgba=(248, 224, 222, 36), angle_deg=1.8)
    _draw_rotated_alpha_stamp(hud_layer, (2272, 306), "N=49 · p<0.001", font=f_hand, color_rgba=(248, 224, 222, 38), angle_deg=2.2)
    _draw_rotated_alpha_stamp(hud_layer, (2216, 1094), "hippocampal replay", font=f_hand, color_rgba=(248, 224, 222, 36), angle_deg=-1.8)
    return Image.alpha_composite(canvas_rgba, hud_layer)


def _composite_crimson_title_only_lockup(
    canvas_rgba: Image.Image,
    *,
    aura_peak_alpha: float = 162.0,
) -> tuple[Image.Image, dict[str, list[int]]]:
    """Composite feathered dark-crimson aura + wide-tracked single-line 'ALL ABOUT BRAIN' title."""
    cx = BANNER_W // 2
    cy = BANNER_H // 2
    yy, xx = np.mgrid[0:BANNER_H, 0:BANNER_W].astype(np.float32)
    aura_r2 = ((xx - cx) / 560.0) ** 2 + ((yy - cy) / 68.0) ** 2
    aura_alpha = np.clip(np.exp(-0.5 * aura_r2) * float(aura_peak_alpha), 0.0, 220.0).astype(np.uint8)
    aura_arr = np.zeros((BANNER_H, BANNER_W, 4), dtype=np.uint8)
    aura_arr[:, :, :3] = np.array([22, 2, 5], dtype=np.uint8)
    aura_arr[:, :, 3] = aura_alpha
    canvas_rgba = Image.alpha_composite(canvas_rgba, Image.fromarray(aura_arr, mode="RGBA"))

    text_layer = Image.new("RGBA", (BANNER_W, BANNER_H), (0, 0, 0, 0))
    tdraw = ImageDraw.Draw(text_layer)
    title_text = "ALL ABOUT BRAIN"

    hero_size = 90
    hero_track = 18
    while hero_size >= 68:
        f_title = _load_font(PRIMARY_BODY_FONT, hero_size, weight=860)
        advs = [float(tdraw.textlength(ch, font=f_title)) for ch in title_text]
        tot_w = sum(advs) + hero_track * (len(title_text) - 1)
        if tot_w <= 1140:
            break
        if hero_track > 10:
            hero_track -= 1
        else:
            hero_size -= 2

    raw_bb = tdraw.textbbox((0, 0), title_text, font=f_title)
    ink_h = raw_bb[3] - raw_bb[1]
    title_y = cy - ink_h // 2
    title_bbox = _draw_tracked_segments(
        tdraw,
        cx,
        title_y,
        [(title_text, (255, 255, 255, 255))],
        f_title,
        tracking_px=hero_track,
    )

    text_arr = np.array(text_layer)
    tys, txs = np.where(text_arr[:, :, 3] > 8)
    ink_union_bbox = (int(txs.min()), int(tys.min()), int(txs.max()) + 1, int(tys.max()) + 1)
    if not (
        ink_union_bbox[0] >= 620
        and ink_union_bbox[1] >= 640
        and ink_union_bbox[2] <= 1940
        and ink_union_bbox[3] <= 800
    ):
        raise RuntimeError(f"Crimson banner title bbox {ink_union_bbox} outside strict center title zone")

    text_a = text_layer.split()[3]
    sh_wide = Image.new("RGBA", (BANNER_W, BANNER_H), (16, 2, 4, 255))
    sh_wide.putalpha(text_a.point(lambda a: int(round(a * 0.90))))
    canvas_rgba = Image.alpha_composite(canvas_rgba, sh_wide.filter(ImageFilter.GaussianBlur(radius=16.0)))

    sh_tight = Image.new("RGBA", (BANNER_W, BANNER_H), (16, 2, 4, 255))
    sh_tight.putalpha(text_a.point(lambda a: int(round(a * 0.85))))
    sh_tight_shifted = Image.new("RGBA", (BANNER_W, BANNER_H), (0, 0, 0, 0))
    sh_tight_shifted.paste(sh_tight.filter(ImageFilter.GaussianBlur(radius=5.0)), (0, 3))
    canvas_rgba = Image.alpha_composite(canvas_rgba, sh_tight_shifted)
    canvas_rgba = Image.alpha_composite(canvas_rgba, text_layer)
    return canvas_rgba, {
        "title": list(title_bbox),
        "combined_ink_union": list(ink_union_bbox),
    }


def _stamp_wing_kinetic_vfx(
    energy_canvas: np.ndarray,
    *,
    x_near_abs: int,
    x_far_abs: int,
    seed: int,
    n_streaks: int = 18,
    n_arcs: int = 6,
    n_sparks: int = 42,
) -> np.ndarray:
    """Paint horizontal Matrix bullet-time streaks, synaptic wave arcs & micro particles onto float energy."""
    cx = BANNER_W // 2
    vfx_mask = Image.new("L", (BANNER_W, BANNER_H), 0)
    vdraw = ImageDraw.Draw(vfx_mask)
    rng = np.random.default_rng(seed)

    for sign in (-1, 1):
        x_near = cx + sign * x_near_abs
        x_far = cx + sign * x_far_abs
        x_min_s, x_max_s = min(x_near, x_far), max(x_near, x_far)

        for _ in range(n_streaks):
            sy_k = int(rng.integers(544, 896))
            span = int(rng.integers(140, 380))
            sx0 = int(rng.integers(x_min_s, max(x_min_s + 20, x_max_s - span)))
            val = int(rng.integers(48, 96))
            vdraw.line((sx0, sy_k, sx0 + span, sy_k), fill=val, width=1)

        for a_idx in range(n_arcs):
            ya = int(rng.integers(560, 880))
            yb = int(rng.integers(560, 880))
            amp = float(rng.uniform(-24.0, 24.0))
            pts: list[tuple[float, float]] = []
            for step in range(28):
                u = step / 27.0
                px_u = x_near + (x_far - x_near) * u
                py_u = ya * (1.0 - u) + yb * u + amp * math.sin(math.pi * 2.0 * u + a_idx)
                pts.append((px_u, py_u))
            vdraw.line(pts, fill=int(rng.integers(78, 128)), width=2 if a_idx < 3 else 1)

        for _ in range(n_sparks):
            px_p = int(rng.integers(x_min_s, x_max_s))
            py_p = int(rng.integers(528, 912))
            pr = int(rng.integers(1, 4))
            edge_fade = max(0.30, 1.0 - abs(px_p - cx) / 1320.0)
            pval = int(round(rng.integers(140, 235) * edge_fade))
            vdraw.ellipse((px_p - pr, py_p - pr, px_p + pr, py_p + pr), fill=pval)

    vfx_arr = np.array(vfx_mask, dtype=np.float32) / 255.0
    xx_1d = np.arange(BANNER_W, dtype=np.float32)[None, :]
    x_envelope = np.clip(1.0 - np.maximum(0.0, np.abs(xx_1d - cx) - 960.0) / 280.0, 0.0, 1.0)
    return np.maximum(energy_canvas, vfx_arr * x_envelope)


def build_banner_crimson_echo(out_path: Path, *, mode: str) -> dict[str, Any]:
    """
    Build 2560x1440 Final Candidate Banner (`ECHO-A` lateral A02 or `ECHO-B` dorsal A03):
      - One 100% whole, unclipped Ep #31 alabaster + #27D8FF brain dead center
      - 4 symmetrical L/R Matrix cyan holographic MRI contour echoes (anti-mud optical blend)
      - Deep studio crimson spotlight backdrop with 2% grain + faint wing PatrickHand/EEG HUD
      - Title-only wide-tracked 'ALL ABOUT BRAIN' centered in #FFFFFF over soft crimson-obsidian aura
    """
    is_dorsal = str(mode).strip().lower() == "dorsal"
    src_key = "a03_dorsal_cand01" if is_dorsal else "a02_lateral_cand02"
    src_path = SOURCE_ASSETS[src_key]

    cropped = _extract_fringe_free_cyan_brain_rgba(src_path)
    ch, cw = cropped.shape[:2]
    hero_h = 392 if is_dorsal else 388
    hero_w = int(round(hero_h * (cw / ch)))
    hero_im = Image.fromarray(cropped, mode="RGBA").resize((hero_w, hero_h), resample=Image.Resampling.LANCZOS)
    hero_rgba = np.array(hero_im, dtype=np.uint8)

    base_energy = _build_cyan_mri_hologram_energy(hero_rgba)
    backdrop_rgb = _make_crimson_echo_backdrop(BANNER_W, BANNER_H, seed=52012 if is_dorsal else 52011)
    energy_canvas = np.zeros((BANNER_H, BANNER_W), dtype=np.float32)

    cx = BANNER_W // 2  # 1280
    cy = BANNER_H // 2  # 720
    scales = (0.97, 0.93, 0.88, 0.82)
    weights = (0.94, 0.70, 0.48, 0.30)
    dxs = (214, 434, 668, 912) if is_dorsal else (236, 456, 686, 924)

    for scale, weight, dx in zip(scales, weights, dxs):
        ew = max(16, int(round(hero_w * scale)))
        eh = max(16, int(round(hero_h * scale)))
        e_scaled = cv2.resize(base_energy, (ew, eh), interpolation=cv2.INTER_AREA)
        ey0 = cy - eh // 2
        _stamp_float_energy(energy_canvas, e_scaled, cx - dx - ew // 2, ey0, weight)
        _stamp_float_energy(energy_canvas, e_scaled, cx + dx - ew // 2, ey0, weight)

    energy_canvas = _stamp_wing_kinetic_vfx(
        energy_canvas,
        x_near_abs=hero_w // 2 + 12,
        x_far_abs=1120,
        seed=77031 if is_dorsal else 77030,
    )
    canvas_rgb_f = _blend_cyan_energy_onto_crimson(np.array(backdrop_rgb, dtype=np.float32), energy_canvas)
    canvas = Image.fromarray(canvas_rgb_f.astype(np.uint8), mode="RGB").convert("RGBA")

    canvas = _overlay_crimson_wing_hud(
        canvas,
        tick_xs=[cx] + [cx - dx for dx in dxs] + [cx + dx for dx in dxs],
        header_right_label="CRANIAL HOLOGRAM MATRIX  ·  ZERO-CUT ARCHIVE",
    )

    hx0 = cx - hero_w // 2
    hy0 = cy - hero_h // 2
    hx1 = hx0 + hero_w
    hy1 = hy0 + hero_h

    hero_shadow_a = hero_im.split()[3].point(lambda a: int(round(a * 0.52)))
    hero_shadow = Image.new("RGBA", (BANNER_W, BANNER_H), (0, 0, 0, 0))
    sh_stamp = Image.new("RGBA", hero_im.size, (20, 2, 4, 255))
    sh_stamp.putalpha(hero_shadow_a)
    hero_shadow.paste(sh_stamp, (hx0, hy0 + 10))
    canvas = Image.alpha_composite(canvas, hero_shadow.filter(ImageFilter.GaussianBlur(radius=20.0)))

    fg_layer = Image.new("RGBA", (BANNER_W, BANNER_H), (0, 0, 0, 0))
    fg_layer.paste(hero_im, (hx0, hy0))
    canvas = Image.alpha_composite(canvas, fg_layer)

    canvas, text_bboxes = _composite_crimson_title_only_lockup(canvas, aura_peak_alpha=162.0)

    final_rgb = canvas.convert("RGB")
    _atomic_save_image(final_rgb, out_path, format="PNG", optimize=True)

    return {
        "file": out_path.name,
        "width": BANNER_W,
        "height": BANNER_H,
        "variant": f"crimson_echo_{'B_dorsal' if is_dorsal else 'A_lateral'}",
        "hero_mode": "dorsal" if is_dorsal else "lateral",
        "hero_bbox": [hx0, hy0, hx1, hy1],
        "echo_count_per_side": len(dxs),
        "echo_dxs_px": list(dxs),
        "source_asset": str(src_path.relative_to(WORKSPACE_ROOT)),
        "safe_zone_box": list(SAFE_ZONE_BOX),
        "desktop_zone_box": list(DESKTOP_ZONE_BOX),
        "text_bboxes": text_bboxes,
        "sha256": _sha256_file(out_path),
        "bytes": out_path.stat().st_size,
    }


def build_banner_crimson_echo_a(out_path: Path) -> dict[str, Any]:
    """ECHO-A: Centered whole A02 lateral Ep #31 brain + symmetrical cyan Matrix echoes over crimson."""
    return build_banner_crimson_echo(out_path, mode="lateral")


def build_banner_crimson_echo_b(out_path: Path) -> dict[str, Any]:
    """ECHO-B: Centered whole A03 symmetrical dorsal Ep #31 brain + symmetrical cyan Matrix echoes over crimson."""
    return build_banner_crimson_echo(out_path, mode="dorsal")


def build_crimson_echo_comparison_sheet(
    out_path: Path,
    *,
    echo_a_path: Path,
    echo_b_path: Path,
    ted_red_logo_path: Path,
) -> dict[str, Any]:
    """Compare ECHO-A (Centered Lateral A02) vs ECHO-B (Centered Dorsal A03) paired with Option 1 TED Red avatar."""
    return _draw_two_banner_mock_comparison_sheet(
        out_path,
        header_title="CRIMSON BULLET-TIME ECHO BANNERS  —  ECHO-A (LATERAL A02) vs ECHO-B (DORSAL A03)",
        header_sub="WHOLE UNBROKEN EP #31 BRAIN  ·  HOLLOW #27D8FF MRI HOLOGRAM ECHOES ON DEEP CRIMSON  ·  TITLE-ONLY ALL ABOUT BRAIN",
        header_accent_rgb=TED_RED_CENTER_RGB,
        ted_red_logo_path=ted_red_logo_path,
        cards=[
            (
                "ECHO-A: CENTERED WHOLE A02 LATERAL BRAIN + CYAN ECHOES",
                "1:1 avatar silhouette match · 4 progressive glowing cyan MRI echoes L/R · ultra-minimal single-line title over crimson spotlight",
                "ECHO-A · LATERAL 1:1",
                TED_RED_CENTER_RGB,
                echo_a_path,
            ),
            (
                "ECHO-B: CENTERED WHOLE A03 DORSAL BRAIN + CYAN ECHOES",
                "Bilateral symmetrical dorsal geometry · 4 progressive glowing cyan MRI echoes L/R · ultra-minimal single-line title over crimson spotlight",
                "ECHO-B · DORSAL SYMM",
                CYAN_RGB,
                echo_b_path,
            ),
        ],
        strip_labels=(
            "LEFT WING (ECHOES k=3..4)  ·  DESKTOP 2560×423",
            "GREEN DASHED = MOBILE SAFE ZONE 1546×423 (WHOLE BRAIN + ECHOES k=1..2 + TITLE ONLY INSIDE)",
            "RIGHT WING (ECHOES k=3..4)  ·  DESKTOP 2560×423",
        ),
    )


def _verify_crimson_echo_banner_entry(
    output_dir: Path,
    fname: str,
    banner_meta: dict[str, Any],
    issues: list[str],
    label: str,
) -> dict[str, Any]:
    """
    Verify finalized Crimson Echo banner contract:
      1. Title-only single-line typography (zero eyebrows/subheads) strictly inside [620, 640, 1940, 800].
      2. Centered whole unclipped brain inside y=508..931 with zero pink-mud contamination.
      3. Symmetrical glowing cyan MRI echoes visible in both Mobile Safe Zone flanks and Desktop Wings.
      4. Deep Studio Crimson spotlight palette (#C81E1A -> #280306) + film grain in corners.
    """
    bboxes = banner_meta.get("text_bboxes", {})
    union_bb = bboxes.get("combined_ink_union", [])
    has_only_title = set(bboxes.keys()) == {"title", "combined_ink_union"}
    title_only_bounds_ok = False
    if has_only_title and len(union_bb) == 4:
        ux0, uy0, ux1, uy1 = union_bb
        title_only_bounds_ok = (
            ux0 >= 620
            and uy0 >= 640
            and ux1 <= 1940
            and uy1 <= 800
            and (uy1 - uy0) <= 110
        )
    if not title_only_bounds_ok:
        issues.append(f"{label} title-only safe-zone check failed: keys={list(bboxes.keys())}, union={union_bb}")

    hero_bb = banner_meta.get("hero_bbox", [])
    hero_geom_ok = False
    if len(hero_bb) == 4:
        hx0, hy0, hx1, hy1 = [int(v) for v in hero_bb]
        hero_cx = 0.5 * (hx0 + hx1)
        hero_geom_ok = (
            abs(hero_cx - BANNER_W * 0.5) <= 4.0
            and hy0 >= 514
            and hy1 <= 926
            and (hx1 - hx0) >= 280
        )
    else:
        hx0, hy0, hx1, hy1 = 1080, 524, 1480, 916

    whole_brain_unclipped_ok = False
    cyan_echoes_ok = False
    crimson_atmosphere_ok = False

    fpath = output_dir / fname
    if fpath.is_file():
        rgb = np.array(Image.open(fpath).convert("RGB"), dtype=np.float32)
        luma = 0.299 * rgb[:, :, 0] + 0.587 * rgb[:, :, 1] + 0.114 * rgb[:, :, 2]

        # Solid brain purity on undimmed upper (y: 526..645) and lower (y: 795..914) bands inside hero_bbox
        ix0, ix1 = max(0, hx0 + 8), min(BANNER_W, hx1 - 8)
        top_band = rgb[max(520, hy0 + 4):646, ix0:ix1]
        bot_band = rgb[794:min(920, hy1 - 4), ix0:ix1]
        undimmed = np.concatenate([top_band.reshape(-1, 3), bot_band.reshape(-1, 3)], axis=0)
        undim_luma = 0.299 * undimmed[:, 0] + 0.587 * undimmed[:, 1] + 0.114 * undimmed[:, 2]
        cool_brain_px = int(((undimmed[:, 1] >= 130.0) & (undimmed[:, 2] >= 135.0)).sum())
        gypsum_mask = (undim_luma >= 155.0) & (undimmed[:, 2] >= 145.0) & ((undimmed[:, 2] - undimmed[:, 0]) >= -10.0)
        mean_rmb = float(np.mean(undimmed[gypsum_mask, 0] - undimmed[gypsum_mask, 2])) if np.any(gypsum_mask) else 99.0
        whole_brain_unclipped_ok = bool(hero_geom_ok and cool_brain_px >= 10_000 and mean_rmb <= 4.0)
        if not whole_brain_unclipped_ok:
            issues.append(
                f"{label} whole center brain check failed: geom={hero_geom_ok}, "
                f"cool_px={cool_brain_px}, mean_rmb={mean_rmb:.2f}"
            )

        # Glowing cyan echoes on BOTH Left and Right Mobile flanks AND Desktop wings (zero salmon mud)
        mob_l = rgb[520:920, 515 : max(520, hx0 - 12)]
        mob_r = rgb[520:920, min(2040, hx1 + 12) : 2045]
        mob_l_px = int(((mob_l[:, :, 2] >= 110.0) & (mob_l[:, :, 1] >= 85.0) & (mob_l[:, :, 2] > mob_l[:, :, 0] + 15.0)).sum())
        mob_r_px = int(((mob_r[:, :, 2] >= 110.0) & (mob_r[:, :, 1] >= 85.0) & (mob_r[:, :, 2] > mob_r[:, :, 0] + 15.0)).sum())

        wing_l = rgb[520:920, 160:507]
        wing_r = rgb[520:920, 2053:2400]
        wing_l_px = int(((wing_l[:, :, 2] >= 65.0) & (wing_l[:, :, 1] >= 55.0) & (wing_l[:, :, 2] >= wing_l[:, :, 0] * 0.80)).sum())
        wing_r_px = int(((wing_r[:, :, 2] >= 65.0) & (wing_r[:, :, 1] >= 55.0) & (wing_r[:, :, 2] >= wing_r[:, :, 0] * 0.80)).sum())
        cyan_echoes_ok = (mob_l_px >= 2_000) and (mob_r_px >= 2_000) and (wing_l_px >= 500) and (wing_r_px >= 500)
        if not cyan_echoes_ok:
            issues.append(
                f"{label} cyan echo symmetry check failed: mob_l={mob_l_px}, mob_r={mob_r_px}, "
                f"wing_l={wing_l_px}, wing_r={wing_r_px}"
            )

        # Deep Studio Crimson vignette corners + mid spotlight crimson + cinema film grain
        corner_patch = rgb[8:88, 8:88]
        corner_luma = luma[8:88, 8:88]
        cm = corner_patch.mean(axis=(0, 1))
        mid_patch = rgb[420:495, 600:760].mean(axis=(0, 1))
        crimson_atmosphere_ok = (
            float(cm[0]) > float(cm[1]) * 2.0
            and float(cm[0]) > float(cm[2]) * 2.0
            and 20.0 <= float(cm[0]) <= 80.0
            and float(corner_luma.std()) >= 1.2
            and float(mid_patch[0]) >= 75.0
            and float(mid_patch[0] - mid_patch[2]) >= 50.0
        )
        if not crimson_atmosphere_ok:
            issues.append(
                f"{label} crimson spotlight/grain check failed: corner={cm.tolist()}, "
                f"grain_std={corner_luma.std():.2f}, mid={mid_patch.tolist()}"
            )

    return {
        "safe_zone_box": list(SAFE_ZONE_BOX),
        "combined_ink_union": union_bb,
        "hero_bbox": hero_bb,
        "title_only_bounds_ok": title_only_bounds_ok,
        "whole_brain_unclipped_ok": whole_brain_unclipped_ok,
        "cyan_echoes_ok": cyan_echoes_ok,
        "crimson_atmosphere_ok": crimson_atmosphere_ok,
    }


MNI_CORONAL_Y_PLANES = (52.0, 34.5, 17.0, -0.5, -18.0, -35.5, -53.0, -70.5, -86.0)
_MNI_X_MIN, _MNI_X_MAX = -78.0, 78.0
_MNI_Z_MIN, _MNI_Z_MAX = -76.0, 86.0
_MNI_SLICE_W, _MNI_SLICE_H = 624, 648  # 4.0 px/mm (2x supersampled slice texture)


def _slice_mesh_coronal_segments(
    verts: np.ndarray,
    faces: np.ndarray,
    face_normals: np.ndarray,
    y0: float,
) -> np.ndarray:
    """Intersect 3D triangle mesh cleanly with coronal plane Y=y0 and orient (x0,z0)->(x1,z1)."""
    vy = verts[:, 1] - float(y0)
    vy = np.where(vy == 0.0, 1e-5, vy)
    f_vy = vy[faces]
    n_pos = (f_vy > 0.0).sum(axis=1)
    cross_idx = np.where((n_pos == 1) | (n_pos == 2))[0]
    if len(cross_idx) == 0:
        return np.zeros((0, 4), dtype=np.float32)

    segs = np.empty((len(cross_idx), 4), dtype=np.float32)
    out_n = 0
    for ti in cross_idx:
        a, b, c = int(faces[ti, 0]), int(faces[ti, 1]), int(faces[ti, 2])
        pts: list[tuple[float, float]] = []
        for u, v in ((a, b), (b, c), (c, a)):
            va, vb = float(vy[u]), float(vy[v])
            if (va > 0.0) != (vb > 0.0):
                t = va / (va - vb)
                px = float(verts[u, 0] + t * (verts[v, 0] - verts[u, 0]))
                pz = float(verts[u, 2] + t * (verts[v, 2] - verts[u, 2]))
                pts.append((px, pz))
        if len(pts) != 2:
            continue
        x0, z0 = pts[0]
        x1, z1 = pts[1]
        dx, dz = x1 - x0, z1 - z0
        if dx * dx + dz * dz < 1e-8:
            continue
        nx, nz = float(face_normals[ti, 0]), float(face_normals[ti, 2])
        if (dz * nx - dx * nz) < 0.0:
            x0, z0, x1, z1 = x1, z1, x0, z0
        segs[out_n] = (x0, z0, x1, z1)
        out_n += 1
    return segs[:out_n]


def _winding_mask_from_segments(
    segs: np.ndarray,
    *,
    out_w: int = _MNI_SLICE_W,
    out_h: int = _MNI_SLICE_H,
) -> np.ndarray:
    """
    Compute leak-free 2D Generalized Winding Number interior mask cropped strictly to the
    segment XZ bounding box (grid step 2px -> upsampled with cubic antialiasing).
    """
    if len(segs) < 3:
        return np.zeros((out_h, out_w), dtype=np.float32)

    px_scale = out_w / (_MNI_X_MAX - _MNI_X_MIN)
    pz_scale = out_h / (_MNI_Z_MAX - _MNI_Z_MIN)
    pad_mm = 4.0
    x_lo = max(_MNI_X_MIN, float(min(segs[:, 0].min(), segs[:, 2].min())) - pad_mm)
    x_hi = min(_MNI_X_MAX, float(max(segs[:, 0].max(), segs[:, 2].max())) + pad_mm)
    z_lo = max(_MNI_Z_MIN, float(min(segs[:, 1].min(), segs[:, 3].min())) - pad_mm)
    z_hi = min(_MNI_Z_MAX, float(max(segs[:, 1].max(), segs[:, 3].max())) + pad_mm)

    px0 = max(0, int(math.floor((x_lo - _MNI_X_MIN) * px_scale)))
    px1 = min(out_w, int(math.ceil((x_hi - _MNI_X_MIN) * px_scale)))
    py0 = max(0, int(math.floor((_MNI_Z_MAX - z_hi) * pz_scale)))
    py1 = min(out_h, int(math.ceil((_MNI_Z_MAX - z_lo) * pz_scale)))
    roi_w, roi_h = px1 - px0, py1 - py0
    if roi_w < 4 or roi_h < 4:
        return np.zeros((out_h, out_w), dtype=np.float32)

    # Evaluate on 2px coarse grid inside ROI for high speed and precision
    cw = max(8, (roi_w + 1) // 2)
    ch = max(8, (roi_h + 1) // 2)
    gx_vals = _MNI_X_MIN + (np.linspace(px0, px1 - 1, cw, dtype=np.float32) + 0.5) / px_scale
    gz_vals = _MNI_Z_MAX - (np.linspace(py0, py1 - 1, ch, dtype=np.float32) + 0.5) / pz_scale
    gx, gz = np.meshgrid(gx_vals, gz_vals)

    wn = np.zeros((ch, cw), dtype=np.float32)
    for start in range(0, len(segs), 256):
        batch = segs[start : start + 256]
        ax = batch[:, 0][None, None, :] - gx[:, :, None]
        az = batch[:, 1][None, None, :] - gz[:, :, None]
        bx = batch[:, 2][None, None, :] - gx[:, :, None]
        bz = batch[:, 3][None, None, :] - gz[:, :, None]
        wn += np.arctan2(ax * bz - az * bx, ax * bx + az * bz).sum(axis=2)
    wn = np.abs(wn) / (2.0 * np.pi)

    wn_hi = cv2.resize(wn, (roi_w, roi_h), interpolation=cv2.INTER_CUBIC)
    full = np.zeros((out_h, out_w), dtype=np.float32)
    full[py0:py1, px0:px1] = np.clip((wn_hi - 0.38) / 0.16, 0.0, 1.0)
    return full


def _rasterize_segments_glow(segs: np.ndarray, width_px: float = 2.0) -> np.ndarray:
    """Rasterize MNI coronal boundary segments onto 624x648 crisp AA float mask [0..1]."""
    if len(segs) == 0:
        return np.zeros((_MNI_SLICE_H, _MNI_SLICE_W), dtype=np.float32)
    px_scale = _MNI_SLICE_W / (_MNI_X_MAX - _MNI_X_MIN)
    pz_scale = _MNI_SLICE_H / (_MNI_Z_MAX - _MNI_Z_MIN)
    shift = 8  # subpixel fixed-point precision for cv2.line
    mult = 1 << shift
    canvas = np.zeros((_MNI_SLICE_H, _MNI_SLICE_W), dtype=np.uint8)
    thick = max(1, int(round(width_px)))
    for x0, z0, x1, z1 in segs:
        p0 = (int(round((x0 - _MNI_X_MIN) * px_scale * mult)), int(round((_MNI_Z_MAX - z0) * pz_scale * mult)))
        p1 = (int(round((x1 - _MNI_X_MIN) * px_scale * mult)), int(round((_MNI_Z_MAX - z1) * pz_scale * mult)))
        cv2.line(canvas, p0, p1, 255, thickness=thick, lineType=cv2.LINE_AA, shift=shift)
    return canvas.astype(np.float32) / 255.0


@functools.lru_cache(maxsize=1)
def _build_mni152_9_coronal_slices() -> tuple[dict[str, Any], ...]:
    """
    Generate all 9 supersampled 3D MNI152 coronal cross-section slices (`S01` frontal pole ->
    `S09` occipital pole) using exact triangle-plane intersections & Generalized Winding Number.
    """
    if not MNI152_ATLAS_NPZ.is_file():
        raise FileNotFoundError(f"Missing MNI152 3D atlas: {MNI152_ATLAS_NPZ}")
    atlas = np.load(MNI152_ATLAS_NPZ)

    mesh_names = (
        "cortex_lh",
        "cortex_rh",
        "cerebellum",
        "brainstem",
        "corpus_callosum",
        "thalamus",
        "basal_ganglia",
        "hippocampus",
        "amygdala",
    )
    meshes: dict[str, tuple[np.ndarray, np.ndarray, np.ndarray]] = {}
    for m in mesh_names:
        verts = atlas[f"{m}__verts"].astype(np.float32)
        faces = atlas[f"{m}__faces"].astype(np.int32)
        v0, v1, v2 = verts[faces[:, 0]], verts[faces[:, 1]], verts[faces[:, 2]]
        fn = np.cross(v1 - v0, v2 - v0)
        fn_len = np.linalg.norm(fn, axis=1, keepdims=True) + 1e-8
        meshes[m] = (verts, faces, fn / fn_len)

    yy_grid, xx_grid = np.mgrid[0:_MNI_SLICE_H, 0:_MNI_SLICE_W].astype(np.float32)
    z_mm_row = (_MNI_Z_MAX - (yy_grid / _MNI_SLICE_H) * (_MNI_Z_MAX - _MNI_Z_MIN))
    light_grad = np.clip(1.06 - 0.14 * (xx_grid / _MNI_SLICE_W) - 0.12 * (yy_grid / _MNI_SLICE_H), 0.84, 1.08)

    slices_out: list[dict[str, Any]] = []
    for idx, y0 in enumerate(MNI_CORONAL_Y_PLANES):
        segs_map: dict[str, np.ndarray] = {}
        masks_map: dict[str, np.ndarray] = {}
        for m in mesh_names:
            verts, faces, fn = meshes[m]
            segs = _slice_mesh_coronal_segments(verts, faces, fn, y0)
            segs_map[m] = segs
            masks_map[m] = _winding_mask_from_segments(segs)

        cortex_mask = np.maximum(masks_map["cortex_lh"], masks_map["cortex_rh"])
        outer_parenchyma = np.maximum(
            cortex_mask,
            np.maximum(masks_map["cerebellum"], masks_map["brainstem"]),
        )
        parenchyma_bin = (outer_parenchyma > 0.45).astype(np.uint8)
        dist_pial = cv2.distanceTransform(parenchyma_bin, cv2.DIST_L2, 5)

        # Cortical gray-matter ribbon (0..11px inward) -> smooth matte alabaster white matter interior
        w_white = np.clip((dist_pial - 3.0) / 11.0, 0.0, 1.0)
        gray_col = np.array([170.0, 186.0, 202.0], dtype=np.float32)[None, None, :]
        white_col = np.array([232.0, 238.0, 244.0], dtype=np.float32)[None, None, :]
        slice_rgb = (gray_col * (1.0 - w_white[:, :, None]) + white_col * w_white[:, :, None]) * light_grad[:, :, None]

        # Cerebellar arbor-vitae / folia texture modulation
        cereb_w = np.clip(masks_map["cerebellum"] * (1.0 - cortex_mask * 0.75), 0.0, 1.0)
        folia = 0.86 + 0.14 * np.cos(z_mm_row * 1.45)
        cereb_col = np.array([186.0, 202.0, 218.0], dtype=np.float32)[None, None, :] * folia[:, :, None]
        slice_rgb = slice_rgb * (1.0 - cereb_w[:, :, None] * 0.75) + cereb_col * (cereb_w[:, :, None] * 0.75)

        # Luminous cyan MRI internal nuclei highlights inside the cross-section
        sub_glow_specs = (
            ("basal_ganglia", np.array([39.0, 216.0, 255.0], dtype=np.float32), 0.48, 2.0),
            ("thalamus", np.array([72.0, 228.0, 255.0], dtype=np.float32), 0.56, 2.0),
            ("hippocampus", np.array([64.0, 236.0, 255.0], dtype=np.float32), 0.64, 2.0),
            ("amygdala", np.array([110.0, 242.0, 255.0], dtype=np.float32), 0.66, 2.0),
            ("corpus_callosum", np.array([164.0, 246.0, 255.0], dtype=np.float32), 0.60, 2.4),
        )
        sub_lines = np.zeros((_MNI_SLICE_H, _MNI_SLICE_W), dtype=np.float32)
        for m, nuc_col, blend_w, line_w in sub_glow_specs:
            mw = np.clip(masks_map[m] * outer_parenchyma, 0.0, 1.0)
            if np.any(mw > 0.02):
                slice_rgb = slice_rgb * (1.0 - mw[:, :, None] * blend_w) + nuc_col[None, None, :] * (mw[:, :, None] * blend_w)
                sub_lines = np.maximum(sub_lines, _rasterize_segments_glow(segs_map[m], width_px=line_w))

        # Pial surface & sulcal fold glowing cyan ribbon (#27D8FF / #AAF4FF)
        outer_segs_all = [segs_map[k] for k in ("cortex_lh", "cortex_rh", "cerebellum", "brainstem") if len(segs_map[k])]
        pial_segs = np.concatenate(outer_segs_all, axis=0) if outer_segs_all else np.zeros((0, 4), dtype=np.float32)
        pial_core = _rasterize_segments_glow(pial_segs, width_px=2.2)
        pial_halo = cv2.GaussianBlur(pial_core, (0, 0), sigmaX=3.2, sigmaY=3.2)
        sub_halo = cv2.GaussianBlur(sub_lines, (0, 0), sigmaX=2.2, sigmaY=2.2)

        cyan_core = np.array([168.0, 248.0, 255.0], dtype=np.float32)[None, None, :]
        cyan_mid = np.array([39.0, 216.0, 255.0], dtype=np.float32)[None, None, :]

        halo_w = np.clip((pial_halo * 0.72 + sub_halo * 0.62) * (0.28 + 0.72 * outer_parenchyma), 0.0, 0.85)
        slice_rgb = slice_rgb * (1.0 - halo_w[:, :, None] * 0.65) + cyan_mid * (halo_w[:, :, None] * 0.88)

        line_w_map = np.clip(pial_core * 0.92 + sub_lines * 0.85, 0.0, 1.0)
        slice_rgb = slice_rgb * (1.0 - line_w_map[:, :, None] * 0.85) + cyan_core * (line_w_map[:, :, None] * 0.95)

        alpha_total = np.clip(np.maximum(outer_parenchyma, pial_core * 0.90), 0.0, 1.0)
        # Apply subtle sulcal outer glow skirt so pial rim looks crisp without dark fringe
        rgba = np.zeros((_MNI_SLICE_H, _MNI_SLICE_W, 4), dtype=np.uint8)
        rgba[:, :, :3] = np.clip(slice_rgb, 0.0, 255.0).astype(np.uint8)
        rgba[:, :, 3] = np.clip(alpha_total * 255.0, 0.0, 255.0).astype(np.uint8)

        # Build shaded 3D extruded rim texture (sculpted dark-alabaster + #27D8FF MRI rim glow)
        rim_rgb = slice_rgb * 0.44 + np.array([26.0, 162.0, 206.0], dtype=np.float32)[None, None, :] * 0.56
        rim_rgba = rgba.copy()
        rim_rgba[:, :, :3] = np.clip(rim_rgb, 0.0, 255.0).astype(np.uint8)

        # Extract true 3D anatomical landmarks (crown, L/R lateral, center/callosum, inferior) in mm
        if len(pial_segs):
            all_x = np.concatenate([pial_segs[:, 0], pial_segs[:, 2]])
            all_z = np.concatenate([pial_segs[:, 1], pial_segs[:, 3]])
            landmarks_mm = [
                (float(all_x[np.argmax(all_z)]), float(all_z.max() - 4.0)),     # top crown
                (float(all_x.min() + 4.0), float(all_z[np.argmin(all_x)])),     # left lateral
                (float(all_x.max() - 4.0), float(all_z[np.argmax(all_x)])),     # right lateral
                (0.0, float(np.median(all_z) + 12.0)),                          # callosal/upper core
                (float(all_x[np.argmin(all_z)]), float(all_z.min() + 5.0)),     # inferior temporal/cerebellar
            ]
        else:
            landmarks_mm = [(0.0, 15.0)]

        slices_out.append(
            {
                "index": idx,
                "label": f"{idx + 1:02d}",
                "y_mni": float(y0),
                "rgba": rgba,
                "rim_rgba": rim_rgba,
                "landmarks_mm": landmarks_mm,
            }
        )
    return tuple(slices_out)


def _make_bevelled_mri_glass_card(label: str) -> np.ndarray:
    """
    Build Hannibal x Jarvis sleek smoked optical-glass specimen pane texture (`624x648` RGBA)
    with dark obsidian-teal tint (0 milky pink wash), specular glass sweep, and #27D8FF bevel.
    """
    card = np.zeros((_MNI_SLICE_H, _MNI_SLICE_W, 4), dtype=np.uint8)
    px_scale = _MNI_SLICE_W / (_MNI_X_MAX - _MNI_X_MIN)
    pz_scale = _MNI_SLICE_H / (_MNI_Z_MAX - _MNI_Z_MIN)

    # Glass pane bounds in MNI mm: X in [-71, +71], Z in [-72, +82]
    gx0 = max(4, int(round((-71.0 - _MNI_X_MIN) * px_scale)))
    gx1 = min(_MNI_SLICE_W - 5, int(round((71.0 - _MNI_X_MIN) * px_scale)))
    gy0 = max(4, int(round((_MNI_Z_MAX - 82.0) * pz_scale)))
    gy1 = min(_MNI_SLICE_H - 5, int(round((_MNI_Z_MAX - (-72.0)) * pz_scale)))

    # Smoked obsidian-cyan glass interior + soft diagonal specular sweep (NO white milky haze)
    yy, xx = np.mgrid[gy0:gy1, gx0:gx1].astype(np.float32)
    u = (xx - gx0) / max(1.0, float(gx1 - gx0))
    v = (yy - gy0) / max(1.0, float(gy1 - gy0))
    diag_band = np.exp(-0.5 * ((u * 0.72 + v * 0.68 - 0.54) / 0.14) ** 2)
    edge_prox = np.maximum(np.exp(-u * 14.0) + np.exp(-(1.0 - u) * 14.0), np.exp(-v * 14.0) + np.exp(-(1.0 - v) * 14.0))

    interior = np.zeros((gy1 - gy0, gx1 - gx0, 4), dtype=np.float32)
    interior[:, :, 0] = 6.0 + 104.0 * diag_band * 0.45 + 32.0 * edge_prox
    interior[:, :, 1] = 28.0 + 196.0 * diag_band * 0.54 + 170.0 * edge_prox * 0.55
    interior[:, :, 2] = 40.0 + 224.0 * diag_band * 0.64 + 216.0 * edge_prox * 0.65
    interior[:, :, 3] = np.clip(72.0 + 26.0 * diag_band + 50.0 * edge_prox, 0.0, 168.0)
    card[gy0:gy1, gx0:gx1] = np.clip(interior, 0.0, 255.0).astype(np.uint8)

    pil_card = Image.fromarray(card, mode="RGBA")
    cdraw = ImageDraw.Draw(pil_card)

    # Outer cyan bevel frame + inner hairline specular rim
    cdraw.rounded_rectangle((gx0, gy0, gx1, gy1), radius=14, outline=(39, 216, 255, 232), width=4)
    cdraw.rounded_rectangle((gx0 + 5, gy0 + 5, gx1 - 5, gy1 - 5), radius=10, outline=(182, 246, 255, 138), width=2)

    # Corner precision laser brackets + slice number in unoccluded front-left bottom corner
    brk = 24
    for bx, sx in ((gx0 - 1, 1), (gx1 + 1, -1)):
        for by, sy in ((gy0 - 1, 1), (gy1 + 1, -1)):
            cdraw.line((bx, by, bx + sx * brk, by), fill=(210, 252, 255, 245), width=3)
            cdraw.line((bx, by, bx, by + sy * brk), fill=(210, 252, 255, 245), width=3)

    f_idx = _load_font(MONO_FONT, 22)
    cdraw.text((gx0 + 18, gy1 - 16), label, font=f_idx, fill=(198, 250, 255, 225), anchor="ld")
    return np.array(pil_card, dtype=np.uint8)


def _warp_slice_roi_into_canvas(
    target_rgba: Image.Image,
    src_rgba: np.ndarray,
    *,
    u_center: float,
    scale_mm: float,
    cos_yaw: float,
    sin_yaw: float,
    cos_pitch: float,
    sin_pitch: float,
    n_off_px: float,
    f_cam: float = 2350.0,
    d_cam: float = 2350.0,
) -> tuple[int, int, int, int]:
    """Perspective-warp a 624x648 MNI coronal slab layer onto tight local ROI of 2560x1440 canvas."""
    cx, cy = BANNER_W * 0.5, BANNER_H * 0.5
    src_corners = np.array(
        [[0.0, 0.0], [_MNI_SLICE_W - 1.0, 0.0], [_MNI_SLICE_W - 1.0, _MNI_SLICE_H - 1.0], [0.0, _MNI_SLICE_H - 1.0]],
        dtype=np.float32,
    )
    mni_corners = ((_MNI_X_MIN, _MNI_Z_MAX), (_MNI_X_MAX, _MNI_Z_MAX), (_MNI_X_MAX, _MNI_Z_MIN), (_MNI_X_MIN, _MNI_Z_MIN))
    dst_pts: list[list[float]] = []
    for x_mm, z_mm in mni_corners:
        rx = x_mm * scale_mm
        du = rx * cos_yaw + n_off_px * sin_yaw
        dw = rx * sin_yaw - n_off_px * cos_yaw
        dv = (-z_mm * scale_mm) * cos_pitch + dw * sin_pitch
        s = f_cam / (d_cam + dw)
        dst_pts.append([cx + (u_center + du) * s, cy + dv * s])
    dst_arr = np.array(dst_pts, dtype=np.float32)

    rx0 = max(0, int(math.floor(dst_arr[:, 0].min())) - 6)
    ry0 = max(0, int(math.floor(dst_arr[:, 1].min())) - 6)
    rx1 = min(BANNER_W, int(math.ceil(dst_arr[:, 0].max())) + 6)
    ry1 = min(BANNER_H, int(math.ceil(dst_arr[:, 1].max())) + 6)
    if rx1 <= rx0 or ry1 <= ry0:
        return (0, 0, 0, 0)

    local_dst = dst_arr - np.array([float(rx0), float(ry0)], dtype=np.float32)
    h_mat = cv2.getPerspectiveTransform(src_corners, local_dst)
    warped = cv2.warpPerspective(
        src_rgba,
        h_mat,
        (rx1 - rx0, ry1 - ry0),
        flags=cv2.INTER_LANCZOS4,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(0, 0, 0, 0),
    )
    target_rgba.alpha_composite(Image.fromarray(warped, mode="RGBA"), dest=(rx0, ry0))
    ys, xs = np.where(warped[:, :, 3] > 20)
    if len(xs) == 0:
        return (rx0, ry0, rx0, ry0)
    return (rx0 + int(xs.min()), ry0 + int(ys.min()), rx0 + int(xs.max()) + 1, ry0 + int(ys.max()) + 1)


def build_banner_mri_glass(out_path: Path, *, with_glass_panes: bool) -> dict[str, Any]:
    """
    Build 2560x1440 True 3D Oblique MNI152 9-Slice Coronal MRI Banner:
      - with_glass_panes=True  (MRI-A): Hannibal x Jarvis bevelled smoked-glass MRI specimen plates
      - with_glass_panes=False (MRI-B): Frameless floating sculpted 3D coronal anatomical slabs
    """
    slices = _build_mni152_9_coronal_slices()
    backdrop_rgb = _make_crimson_echo_backdrop(BANNER_W, BANNER_H, seed=62011 if with_glass_panes else 62012)

    # Background bullet-time kinetic trails + cyan wing continuity out into Desktop Wings
    energy_canvas = np.zeros((BANNER_H, BANNER_W), dtype=np.float32)
    energy_canvas = _stamp_wing_kinetic_vfx(
        energy_canvas,
        x_near_abs=660,
        x_far_abs=1195,
        seed=88041 if with_glass_panes else 88042,
        n_streaks=26,
        n_arcs=7,
        n_sparks=54,
    )
    canvas_rgb_f = _blend_cyan_energy_onto_crimson(np.array(backdrop_rgb, dtype=np.float32), energy_canvas)
    canvas = Image.fromarray(canvas_rgb_f.astype(np.uint8), mode="RGB").convert("RGBA")

    cx, cy = BANNER_W * 0.5, BANNER_H * 0.5
    u_centers = [(i - 4) * 184.0 for i in range(9)]  # -736 .. +736 (~1660px assembled 3D footprint)
    scale_mm = 2.34
    yaw_rad = math.radians(-54.0)  # Sleek 3/4 oblique cascade reducing pane overlap to ~14px
    pitch_rad = math.radians(-6.5)
    cos_yaw, sin_yaw = math.cos(yaw_rad), math.sin(yaw_rad)
    cos_pitch, sin_pitch = math.cos(pitch_rad), math.sin(pitch_rad)
    f_cam, d_cam = 2350.0, 2350.0

    canvas = _overlay_crimson_wing_hud(
        canvas,
        tick_xs=[int(round(cx + u)) for u in u_centers],
        header_right_label="MNI152 9-PLANE OBLIQUE MRI  ·  3/4 PERSPECTIVE",
    )

    def proj_pt(u_c: float, x_mm: float, z_mm: float, n_off: float = 0.0) -> tuple[float, float]:
        rx = x_mm * scale_mm
        du = rx * cos_yaw + n_off * sin_yaw
        dw = rx * sin_yaw - n_off * cos_yaw
        dv = (-z_mm * scale_mm) * cos_pitch + dw * sin_pitch
        s = f_cam / (d_cam + dw)
        return cx + (u_c + du) * s, cy + dv * s

    # Pre-project slice centers & landmarks for back-to-front painter's-algorithm rendering
    slice_bboxes_ordered: list[dict[str, Any]] = [{} for _ in range(9)]
    for i in range(8, -1, -1):
        sl = slices[i]
        u_c = u_centers[i]

        # Inter-slice 3D synaptic neural bridges connecting slice i+1 (behind) to slice i (front)
        if i < 8:
            bridge_glow = Image.new("RGBA", (BANNER_W, BANNER_H), (0, 0, 0, 0))
            bridge_core = Image.new("RGBA", (BANNER_W, BANNER_H), (0, 0, 0, 0))
            bgdraw = ImageDraw.Draw(bridge_glow)
            bcdraw = ImageDraw.Draw(bridge_core)
            pts_prev = slices[i + 1]["landmarks_mm"]
            pts_curr = sl["landmarks_mm"]
            u_prev = u_centers[i + 1]
            for l_idx in range(min(len(pts_prev), len(pts_curr))):
                p_back = proj_pt(u_prev, pts_prev[l_idx][0], pts_prev[l_idx][1], -2.0)
                p_front = proj_pt(u_c, pts_curr[l_idx][0], pts_curr[l_idx][1], -8.0)
                curve_pts = []
                for sk in range(13):
                    t = sk / 12.0
                    mx = p_back[0] * (1.0 - t) + p_front[0] * t
                    my = p_back[1] * (1.0 - t) + p_front[1] * t + 7.0 * math.sin(math.pi * t) * (-1 if l_idx % 2 else 1)
                    curve_pts.append((mx, my))
                bgdraw.line(curve_pts, fill=(39, 216, 255, 130), width=4)
                bcdraw.line(curve_pts, fill=(198, 250, 255, 195), width=1)
                bcdraw.ellipse((p_back[0] - 2, p_back[1] - 2, p_back[0] + 2, p_back[1] + 2), fill=(215, 252, 255, 220))
                bcdraw.ellipse((p_front[0] - 2, p_front[1] - 2, p_front[0] + 2, p_front[1] + 2), fill=(215, 252, 255, 220))
            canvas = Image.alpha_composite(canvas, bridge_glow.filter(ImageFilter.GaussianBlur(radius=3.5)))
            canvas = Image.alpha_composite(canvas, bridge_core)

        # Soft deep-crimson occlusion drop shadow behind each slice for physical 3D separation
        sh_src = sl["rgba"].copy()
        sh_src[:, :, :3] = np.array([16, 2, 4], dtype=np.uint8)
        sh_src[:, :, 3] = np.clip(sh_src[:, :, 3].astype(np.float32) * 0.44, 0.0, 255.0).astype(np.uint8)
        sh_layer = Image.new("RGBA", (BANNER_W, BANNER_H), (0, 0, 0, 0))
        _warp_slice_roi_into_canvas(
            sh_layer,
            sh_src,
            u_center=u_c + 10.0,
            scale_mm=scale_mm,
            cos_yaw=cos_yaw,
            sin_yaw=sin_yaw,
            cos_pitch=cos_pitch,
            sin_pitch=sin_pitch,
            n_off_px=-14.0,
        )
        canvas = Image.alpha_composite(canvas, sh_layer.filter(ImageFilter.GaussianBlur(radius=12.0)))

        # Optional optical-glass specimen pane (MRI-A) behind extruded tissue rim
        glass_bb = (9999, 9999, 0, 0)
        if with_glass_panes:
            glass_src = _make_bevelled_mri_glass_card(sl["label"])
            glass_bb = _warp_slice_roi_into_canvas(
                canvas,
                glass_src,
                u_center=u_c,
                scale_mm=scale_mm,
                cos_yaw=cos_yaw,
                sin_yaw=sin_yaw,
                cos_pitch=cos_pitch,
                sin_pitch=sin_pitch,
                n_off_px=-10.0,
            )

        # True 3D extruded slab rim (-10px -> -1.5px), then crisp front coronal cross-section (0px)
        for n_off in (-10.0, -8.2, -6.4, -4.6, -2.8, -1.3):
            _warp_slice_roi_into_canvas(
                canvas,
                sl["rim_rgba"],
                u_center=u_c,
                scale_mm=scale_mm,
                cos_yaw=cos_yaw,
                sin_yaw=sin_yaw,
                cos_pitch=cos_pitch,
                sin_pitch=sin_pitch,
                n_off_px=n_off,
            )

        front_bb = _warp_slice_roi_into_canvas(
            canvas,
            sl["rgba"],
            u_center=u_c,
            scale_mm=scale_mm,
            cos_yaw=cos_yaw,
            sin_yaw=sin_yaw,
            cos_pitch=cos_pitch,
            sin_pitch=sin_pitch,
            n_off_px=0.0,
        )
        bx0 = min(front_bb[0], glass_bb[0]) if with_glass_panes else front_bb[0]
        by0 = min(front_bb[1], glass_bb[1]) if with_glass_panes else front_bb[1]
        bx1 = max(front_bb[2], glass_bb[2]) if with_glass_panes else front_bb[2]
        by1 = max(front_bb[3], glass_bb[3]) if with_glass_panes else front_bb[3]
        pcx, pcy = proj_pt(u_c, 0.0, 0.0, 0.0)
        slice_bboxes_ordered[i] = {
            "label": f"S{sl['label']}",
            "y_mni": sl["y_mni"],
            "cx": int(round(pcx)),
            "cy": int(round(pcy)),
            "bbox": [bx0, by0, bx1, by1],
        }

    # Soft feathered dark-crimson aura + wide-tracked single-line 'ALL ABOUT BRAIN'
    canvas, text_bboxes = _composite_crimson_title_only_lockup(canvas, aura_peak_alpha=148.0)

    final_rgb = canvas.convert("RGB")
    _atomic_save_image(final_rgb, out_path, format="PNG", optimize=True)

    return {
        "file": out_path.name,
        "width": BANNER_W,
        "height": BANNER_H,
        "variant": "mri_glass_A_panes" if with_glass_panes else "mri_glass_B_sculpted",
        "with_glass_panes": with_glass_panes,
        "slice_count": len(slice_bboxes_ordered),
        "slice_bboxes": slice_bboxes_ordered,
        "source_atlas": str(MNI152_ATLAS_NPZ.relative_to(WORKSPACE_ROOT)),
        "safe_zone_box": list(SAFE_ZONE_BOX),
        "desktop_zone_box": list(DESKTOP_ZONE_BOX),
        "text_bboxes": text_bboxes,
        "sha256": _sha256_file(out_path),
        "bytes": out_path.stat().st_size,
    }


def build_banner_mri_glass_a(out_path: Path) -> dict[str, Any]:
    """MRI-A: 9 true 3D MNI152 coronal slabs encased in oblique Hannibal x Jarvis optical-glass panes."""
    return build_banner_mri_glass(out_path, with_glass_panes=True)


def build_banner_mri_glass_b(out_path: Path) -> dict[str, Any]:
    """MRI-B: 9 frameless floating 3D MNI152 sculpted alabaster + #27D8FF coronal anatomical slabs."""
    return build_banner_mri_glass(out_path, with_glass_panes=False)


def build_mri_glass_comparison_sheet(
    out_path: Path,
    *,
    mri_a_path: Path,
    mri_b_path: Path,
    ted_red_logo_path: Path,
) -> dict[str, Any]:
    """Compare MRI-A (Glass Specimen Panes) vs MRI-B (Frameless Sculpted Slabs) w/ TED Red avatar."""
    return _draw_two_banner_mock_comparison_sheet(
        out_path,
        header_title="3D OBLIQUE MNI152 CORONAL MRI BANNERS  —  MRI-A (GLASS PANES) vs MRI-B (SCULPTED SLABS)",
        header_sub="9 ANATOMICAL MNI152 PLANES (FRONTAL -> OCCIPITAL)  ·  3/4 PERSPECTIVE + MATRIX SYNAPTIC BRIDGES  ·  TED RED AVATAR",
        header_accent_rgb=TED_RED_CENTER_RGB,
        ted_red_logo_path=ted_red_logo_path,
        cards=[
            (
                "MRI-A: HANNIBAL × JARVIS BEVELLED GLASS MRI PANES (9 SLABS)",
                "Smoked optical-glass plates + #27D8FF bevel frames · MNI152 cortex/CC/thalamus/hippocampus · crimson film-grain depth",
                "MRI-A · GLASS PANES",
                CYAN_RGB,
                mri_a_path,
            ),
            (
                "MRI-B: FRAMELESS FLOATING 3D SCULPTED CORONAL SLABS (9 SLABS)",
                "Zero glass frames · pure extruded alabaster-gypsum & #27D8FF anatomical cross-sections fusing into one unified 3D brain",
                "MRI-B · SCULPTED 3D",
                TED_RED_CENTER_RGB,
                mri_b_path,
            ),
        ],
        strip_labels=(
            "LEFT WING (S01 + BULLET-TIME TRAILS)  ·  DESKTOP 2560×423",
            "GREEN DASHED = MOBILE SAFE ZONE 1546×423 (9-SLICE 3D BRAIN ASSEMBLY + TITLE ONLY INSIDE)",
            "RIGHT WING (S09 + BULLET-TIME TRAILS)  ·  DESKTOP 2560×423",
        ),
    )


def _verify_mri_glass_banner_entry(
    output_dir: Path,
    fname: str,
    banner_meta: dict[str, Any],
    issues: list[str],
    label: str,
) -> dict[str, Any]:
    """
    Verify 9-slice oblique MNI152 coronal MRI banner contract:
      1. Title-only single line inside [620, 640, 1940, 800] (no eyebrow/subhead).
      2. All 9 coronal slices vertically unclipped inside y=508..931 with >=7 centers inside Mobile.
      3. Undimmed anatomical alabaster+cyan clarity, zero pink-mud smears, rich cyan wing continuity.
      4. Deep studio crimson spotlight + film grain in corners.
    """
    bboxes = banner_meta.get("text_bboxes", {})
    union_bb = bboxes.get("combined_ink_union", [])
    has_only_title = set(bboxes.keys()) == {"title", "combined_ink_union"}
    title_only_bounds_ok = False
    if has_only_title and len(union_bb) == 4:
        ux0, uy0, ux1, uy1 = union_bb
        title_only_bounds_ok = (
            ux0 >= 620
            and uy0 >= 640
            and ux1 <= 1940
            and uy1 <= 800
            and (uy1 - uy0) <= 110
        )
    if not title_only_bounds_ok:
        issues.append(f"{label} title-only check failed: keys={list(bboxes.keys())}, union={union_bb}")

    slice_entries = banner_meta.get("slice_bboxes") or []
    slices_9_unclipped_ok = False
    if len(slice_entries) == 9 and banner_meta.get("slice_count") == 9:
        y0_all = min(int(s["bbox"][1]) for s in slice_entries)
        y1_all = max(int(s["bbox"][3]) for s in slice_entries)
        x0_all = min(int(s["bbox"][0]) for s in slice_entries)
        x1_all = max(int(s["bbox"][2]) for s in slice_entries)
        mob_count = sum(1 for s in slice_entries if SAFE_ZONE_BOX[0] <= int(s["cx"]) <= SAFE_ZONE_BOX[2])
        footprint_w = x1_all - x0_all
        slices_9_unclipped_ok = (
            y0_all >= 509
            and y1_all <= 930
            and mob_count >= 7
            and 1280 <= footprint_w <= 1860
        )
        if not slices_9_unclipped_ok:
            issues.append(
                f"{label} 9-slice oblique geometry check failed: y=({y0_all}..{y1_all}), "
                f"footprint_w={footprint_w}, mobile_centers={mob_count}"
            )
    else:
        issues.append(f"{label} expected 9 slice_bboxes, got {len(slice_entries)}")

    anatomy_and_wings_ok = False
    crimson_atmosphere_ok = False
    fpath = output_dir / fname
    if fpath.is_file():
        rgb = np.array(Image.open(fpath).convert("RGB"), dtype=np.float32)
        luma = 0.299 * rgb[:, :, 0] + 0.587 * rgb[:, :, 1] + 0.114 * rgb[:, :, 2]

        # Anatomical brain visibility in undimmed upper & lower mobile bands + zero pink mud
        top_roi = rgb[516:646, SAFE_ZONE_BOX[0]:SAFE_ZONE_BOX[2]]
        bot_roi = rgb[794:924, SAFE_ZONE_BOX[0]:SAFE_ZONE_BOX[2]]
        undimmed = np.concatenate([top_roi.reshape(-1, 3), bot_roi.reshape(-1, 3)], axis=0)
        undim_luma = 0.299 * undimmed[:, 0] + 0.587 * undimmed[:, 1] + 0.114 * undimmed[:, 2]
        anat_px = int(((undimmed[:, 1] >= 100.0) & (undimmed[:, 2] >= 110.0) & (undimmed[:, 2] >= undimmed[:, 0] - 10.0)).sum())
        gypsum_mask = (undim_luma >= 155.0) & (undimmed[:, 2] >= 145.0) & ((undimmed[:, 2] - undimmed[:, 0]) >= -10.0)
        mean_rmb = float(np.mean(undimmed[gypsum_mask, 0] - undimmed[gypsum_mask, 2])) if np.any(gypsum_mask) else 99.0

        wing_l = rgb[520:920, 160:SAFE_ZONE_BOX[0]]
        wing_r = rgb[520:920, SAFE_ZONE_BOX[2]:2400]
        wing_l_px = int(((wing_l[:, :, 2] >= 65.0) & (wing_l[:, :, 1] >= 55.0) & (wing_l[:, :, 2] >= wing_l[:, :, 0] * 0.80)).sum())
        wing_r_px = int(((wing_r[:, :, 2] >= 65.0) & (wing_r[:, :, 1] >= 55.0) & (wing_r[:, :, 2] >= wing_r[:, :, 0] * 0.80)).sum())
        anatomy_and_wings_ok = (anat_px >= 14_000) and (mean_rmb <= 4.0) and (wing_l_px >= 450) and (wing_r_px >= 450)
        if not anatomy_and_wings_ok:
            issues.append(
                f"{label} anatomy/wings purity failed: anat_px={anat_px}, mean_rmb={mean_rmb:.2f}, "
                f"wing_l={wing_l_px}, wing_r={wing_r_px}"
            )

        corner_patch = rgb[8:88, 8:88]
        corner_luma = luma[8:88, 8:88]
        cm = corner_patch.mean(axis=(0, 1))
        crimson_atmosphere_ok = (
            float(cm[0]) > float(cm[1]) * 2.0
            and float(cm[0]) > float(cm[2]) * 2.0
            and 20.0 <= float(cm[0]) <= 80.0
            and float(corner_luma.std()) >= 1.2
        )
        if not crimson_atmosphere_ok:
            issues.append(f"{label} crimson atmosphere/grain failed: corner={cm.tolist()}, std={corner_luma.std():.2f}")

    return {
        "safe_zone_box": list(SAFE_ZONE_BOX),
        "combined_ink_union": union_bb,
        "slice_count": len(slice_entries),
        "title_only_bounds_ok": title_only_bounds_ok,
        "slices_9_unclipped_ok": slices_9_unclipped_ok,
        "anatomy_and_wings_ok": anatomy_and_wings_ok,
        "crimson_atmosphere_ok": crimson_atmosphere_ok,
    }


BANNED_JH5_TOKENS: tuple[str, ...] = (
    "B01",
    "B02",
    "B03",
    "B04",
    "B05",
    "B06",
    "B07",
    "B08",
    "B09",
    "B10",
    "B11",
    "B12",
    "B13",
    "B14",
    "B15",
    "G02",
    "E06",
    "E07",
    "A16",
    "A17",
)


def _cover_crop_2560x1440(
    image_or_path: Path | Image.Image,
    *,
    y_frac: float = 0.45,
    x_frac: float = 0.5,
    flip_x: bool = False,
    bg_blur: float = 0.0,
) -> Image.Image:
    """Proportionally cover-fit any source into 2560x1440 without stretching."""
    if isinstance(image_or_path, Image.Image):
        src = image_or_path.convert("RGB")
    else:
        with Image.open(image_or_path) as im:
            src = im.convert("RGB")
    if flip_x:
        src = src.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    sw, sh = src.size
    scale = max(BANNER_W / float(sw), BANNER_H / float(sh))
    rw = max(BANNER_W, int(round(sw * scale)))
    rh = max(BANNER_H, int(round(sh * scale)))
    resized = src.resize((rw, rh), resample=Image.Resampling.LANCZOS)
    x0 = int(round(max(0.0, min(1.0, x_frac)) * max(0, rw - BANNER_W)))
    y0 = int(round(max(0.0, min(1.0, y_frac)) * max(0, rh - BANNER_H)))
    cropped = resized.crop((x0, y0, x0 + BANNER_W, y0 + BANNER_H))
    if bg_blur > 0.0:
        cropped = cropped.filter(ImageFilter.GaussianBlur(radius=bg_blur))
    return cropped


def _feather_paste_rgba(
    dst_rgba: Image.Image,
    src_rgba: Image.Image,
    center_xy: tuple[int, int],
    *,
    target_h: int | None = None,
    target_w: int | None = None,
    edge_feather_frac: float = 0.24,
    edge_blur_px: float = 28.0,
    opacity: float = 1.0,
    tint_rgb: tuple[int, int, int] | None = None,
    tint_strength: float = 0.0,
    mirror_x: bool = False,
) -> Image.Image:
    """Proportionally scale an RGBA plate/prop and softly feather perimeter before compositing."""
    work = src_rgba.convert("RGBA")
    if mirror_x:
        work = work.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    sw, sh = work.size
    if target_h is not None:
        scale = float(target_h) / float(sh)
    elif target_w is not None:
        scale = float(target_w) / float(sw)
    else:
        scale = 1.0
    nw = max(16, int(round(sw * scale)))
    nh = max(16, int(round(sh * scale)))
    work = work.resize((nw, nh), resample=Image.Resampling.LANCZOS)

    arr = np.array(work, dtype=np.float32)
    if tint_rgb is not None and tint_strength > 0.0:
        tr, tg, tb = [float(c) for c in tint_rgb]
        k = max(0.0, min(1.0, float(tint_strength)))
        arr[:, :, 0] = arr[:, :, 0] * (1.0 - k) + tr * k
        arr[:, :, 1] = arr[:, :, 1] * (1.0 - k) + tg * k
        arr[:, :, 2] = arr[:, :, 2] * (1.0 - k) + tb * k

    yy, xx = np.mgrid[0:nh, 0:nw].astype(np.float32)
    ux = (xx - (nw - 1) * 0.5) / max(1.0, nw * 0.5)
    uy = (yy - (nh - 1) * 0.5) / max(1.0, nh * 0.5)
    # Super-elliptical soft vignette mask guaranteeing zero hard rectangular corners
    radial = (np.abs(ux) ** 2.6 + np.abs(uy) ** 2.6) ** (1.0 / 2.6)
    inner = max(0.05, 1.0 - float(edge_feather_frac) * 1.45)
    outer = 0.985
    ramp = np.clip((outer - radial) / max(0.05, outer - inner), 0.0, 1.0)
    ramp = ramp * ramp * (3.0 - 2.0 * ramp)
    if edge_blur_px > 0.5:
        ramp_img = Image.fromarray((ramp * 255.0).astype(np.uint8), mode="L").filter(
            ImageFilter.GaussianBlur(radius=float(edge_blur_px) * 0.35)
        )
        ramp = np.array(ramp_img, dtype=np.float32) / 255.0

    arr[:, :, 3] = np.clip(arr[:, :, 3] * ramp * max(0.0, min(1.0, float(opacity))), 0.0, 255.0)
    feathered = Image.fromarray(arr.astype(np.uint8), mode="RGBA")
    layer = Image.new("RGBA", dst_rgba.size, (0, 0, 0, 0))
    px = int(round(center_xy[0] - nw * 0.5))
    py = int(round(center_xy[1] - nh * 0.5))
    layer.paste(feathered, (px, py))
    return Image.alpha_composite(dst_rgba, layer)


def _add_anamorphic_bokeh_and_light(
    canvas_rgb_f: np.ndarray,
    *,
    lights: list[tuple[float, float, float, float, tuple[int, int, int], float]],
    seed: int = 7701,
    n_bokeh: int = 18,
    bokeh_colors: tuple[tuple[float, float, float], tuple[float, float, float]] | None = None,
) -> np.ndarray:
    """
    Add volumetric 35mm cinema light pools and subtle anamorphic bokeh discs.
    Each light entry is (cx_px, cy_px, rx_px, ry_px, rgb, strength_0_to_1).
    """
    h, w, _ = canvas_rgb_f.shape
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    out = canvas_rgb_f.copy()
    for lcx, lcy, lrx, lry, lrgb, lstr in lights:
        dist2 = ((xx - lcx) / max(1.0, lrx)) ** 2 + ((yy - lcy) / max(1.0, lry)) ** 2
        glow = np.exp(-0.95 * dist2) * float(lstr)
        for ch in range(3):
            out[:, :, ch] += glow * float(lrgb[ch])

    if n_bokeh > 0:
        rng = np.random.default_rng(seed)
        bokeh_layer = np.zeros((h, w, 3), dtype=np.float32)
        warm_col = (
            np.array(bokeh_colors[0], dtype=np.float32)
            if bokeh_colors is not None
            else np.array([232.0, 88.0, 62.0], dtype=np.float32)
        )
        cool_col = (
            np.array(bokeh_colors[1], dtype=np.float32)
            if bokeh_colors is not None
            else np.array([48.0, 198.0, 224.0], dtype=np.float32)
        )
        for _ in range(n_bokeh):
            bx = float(rng.uniform(80.0, w - 80.0))
            by = float(rng.uniform(380.0, 1060.0))
            br = float(rng.uniform(16.0, 48.0))
            # Prefer bokeh away from center text block
            if 780.0 <= bx <= 1780.0 and 590.0 <= by <= 840.0:
                bx = float(rng.choice([rng.uniform(90.0, 560.0), rng.uniform(1980.0, w - 90.0)]))
            is_warm = bool(rng.random() < 0.48)
            bcol = warm_col if is_warm else cool_col
            # Anamorphic slight vertical elongation 1.15x
            d2 = ((xx - bx) / br) ** 2 + ((yy - by) / (br * 1.15)) ** 2
            disc = np.clip((1.0 - d2) * 1.8, 0.0, 1.0) ** 2.2
            alp = float(rng.uniform(0.035, 0.085))
            bokeh_layer += disc[:, :, None] * bcol[None, None, :] * alp
        bokeh_img = Image.fromarray(np.clip(bokeh_layer, 0.0, 255.0).astype(np.uint8), mode="RGB").filter(
            ImageFilter.GaussianBlur(radius=9.0)
        )
        out += np.array(bokeh_img, dtype=np.float32)

    return np.clip(out, 0.0, 255.0)


def apply_jh_cinema_finish(
    base_rgb: Image.Image,
    *,
    seed: int = 9901,
    with_notes: bool = True,
    eyebrow_text: str = "ORIGINAL NEUROSCIENCE SERIES",
    signature_text: str = "inside the human mind",
    left_notes: list[tuple[str, float]] | None = None,
    right_notes: list[tuple[str, float]] | None = None,
    scrim_peak_alpha: float = 0.56,
    scrim_rgb: tuple[float, float, float] = (6.0, 14.0, 20.0),
    scrim_ry: float = 145.0,
    note_ink_rgb: tuple[int, int, int] = (226, 240, 244),
    grain_sigma: float = 5.6,
    accent_bar_rgb: tuple[int, int, int] = (224, 84, 62),
) -> tuple[Image.Image, dict[str, Any]]:
    """
    Apply Johnny Harris 'THE HUMAN ELEMENT' 35mm Cinema Banner finishing layer:
      1. 35mm cinema S-curve + teal/obsidian edge vignette + subtle corner depth falloff.
      2. Feathered horizontal atmospheric scrim centered behind typography.
      3. Optional Caveat-Variable handwritten research notes across outer desktop wings.
      4. Wide-tracked movie-poster 'ALL ABOUT BRAIN' lockup strictly within SAFE_ZONE_BOX.
      5. Unified ~2.2% Kodak Vision3 500T film grain across the final frame.
    """
    src_rgb = base_rgb.convert("RGB")
    if src_rgb.size != (BANNER_W, BANNER_H):
        src_rgb = _cover_crop_2560x1440(src_rgb, y_frac=0.5, x_frac=0.5)

    arr = np.array(src_rgb, dtype=np.float32)
    yy, xx = np.mgrid[0:BANNER_H, 0:BANNER_W].astype(np.float32)

    # 1. Gentle 35mm cinema tone curve (lifted deep teal-charcoal black toe + smooth roll-off)
    norm = arr / 255.0
    curved = norm * norm * (3.0 - 2.0 * norm) * 0.28 + norm * 0.72
    arr = np.clip(curved * 246.0 + 4.0, 0.0, 255.0)

    # Anamorphic elliptical vignette (darker top/bottom TV zones & subtle corner falloff)
    vx = (xx - BANNER_W * 0.5) / (BANNER_W * 0.56)
    vy = (yy - BANNER_H * 0.5) / (BANNER_H * 0.42)
    vig = 1.0 - 0.52 * np.clip((vx * vx + vy * vy - 0.42) / 1.55, 0.0, 1.0)
    arr *= vig[:, :, None]

    # 2. Feathered horizontal cinema scrim centered behind typography (never a box)
    sx_d = ((xx - BANNER_W * 0.5) / 580.0) ** 2 + ((yy - BANNER_H * 0.5) / max(32.0, float(scrim_ry))) ** 2
    scrim = float(scrim_peak_alpha) * np.exp(-0.88 * sx_d)
    arr = arr * (1.0 - scrim[:, :, None]) + np.array(scrim_rgb, dtype=np.float32)[None, None, :] * scrim[:, :, None]

    canvas = Image.fromarray(np.clip(arr, 0.0, 255.0).astype(np.uint8), mode="RGB").convert("RGBA")

    # 3. Optional Caveat handwritten research notes in outer Desktop wings (never clipped on Mobile)
    wing_notes_bboxes: list[list[int]] = []
    if with_notes:
        default_left = [
            ("fig. 01  ·  human connectome", -5.5),
            ("gray matter  ~1.1mm cortex", 3.2),
            ("neural signal  ->  trace", -2.8),
        ]
        default_right = [
            ("case archive  ·  ep 31", 4.2),
            ("peer-reviewed  DOI lock", -3.8),
            ("40 Hz  cortical rhythm", 2.4),
        ]
        l_items = left_notes if left_notes is not None else default_left
        r_items = right_notes if right_notes is not None else default_right
        f_note_lg = _load_font(CAVEAT_FONT, 31, weight=600)
        f_note_sm = _load_font(CAVEAT_FONT, 26, weight=520)

        l_coords = [(118, 565), (156, 690), (108, 816)]
        r_coords = [(2100, 570), (2132, 694), (2090, 814)]
        for i, (txt, ang) in enumerate(l_items[:3]):
            px, py = l_coords[i]
            fnt = f_note_lg if i == 0 else f_note_sm
            _draw_rotated_alpha_stamp(
                canvas,
                (px + 2, py + 2),
                txt,
                font=fnt,
                color_rgba=(4, 9, 14, 72),
                angle_deg=ang,
            )
            _draw_rotated_alpha_stamp(
                canvas,
                (px, py),
                txt,
                font=fnt,
                color_rgba=(*note_ink_rgb, 78 if i % 2 == 0 else 64),
                angle_deg=ang,
            )
            wing_notes_bboxes.append([px, py, px + 320, py + 44])
        for i, (txt, ang) in enumerate(r_items[:3]):
            px, py = r_coords[i]
            fnt = f_note_lg if i == 0 else f_note_sm
            _draw_rotated_alpha_stamp(
                canvas,
                (px + 2, py + 2),
                txt,
                font=fnt,
                color_rgba=(4, 9, 14, 72),
                angle_deg=ang,
            )
            _draw_rotated_alpha_stamp(
                canvas,
                (px, py),
                txt,
                font=fnt,
                color_rgba=(*note_ink_rgb, 76 if i % 2 == 0 else 62),
                angle_deg=ang,
            )
            wing_notes_bboxes.append([px, py, px + 320, py + 44])

    # 4. Wide-tracked cinema poster title lockup strictly inside SAFE_ZONE_BOX (507, 508, 2053, 931)
    cx = BANNER_W // 2  # 1280
    f_eyebrow = _load_font(PRIMARY_BODY_FONT, 20, weight=650)
    f_title = _load_font(PRIMARY_DISPLAY_FONT, 92)
    f_sig = _load_font(CAVEAT_FONT, 36, weight=620)

    # Soft cinema drop-shadow pass for crisp legibility over illuminated glass/horizon backdrops
    shadow_layer = Image.new("RGBA", (BANNER_W, BANNER_H), (0, 0, 0, 0))
    sh_draw = ImageDraw.Draw(shadow_layer)
    _draw_tracked_segments(
        sh_draw,
        cx,
        622,
        [(eyebrow_text, (4, 9, 14))],
        f_eyebrow,
        tracking_px=7,
    )
    _draw_tracked_segments(
        sh_draw,
        cx,
        664,
        [("ALL ABOUT BRAIN", (4, 9, 14))],
        f_title,
        tracking_px=18,
    )
    # Apply subtle shadow alpha by extracting dark silhouette density via brightness mask
    sh_arr = np.array(shadow_layer, dtype=np.float32)
    sh_arr[:, :, 3] = np.clip(sh_arr[:, :, 3] * 0.78, 0.0, 255.0)
    shadow_blurred = Image.fromarray(sh_arr.astype(np.uint8), mode="RGBA").filter(
        ImageFilter.GaussianBlur(radius=9.5)
    )
    canvas = Image.alpha_composite(canvas, shadow_blurred)

    text_layer = Image.new("RGBA", (BANNER_W, BANNER_H), (0, 0, 0, 0))
    tdraw = ImageDraw.Draw(text_layer)

    bb_eye = _draw_tracked_segments(
        tdraw,
        cx,
        622,
        [(eyebrow_text, (192, 214, 224))],
        f_eyebrow,
        tracking_px=7,
    )
    bb_title = _draw_tracked_segments(
        tdraw,
        cx,
        664,
        [("ALL ABOUT ", (245, 247, 250)), ("BRAIN", (236, 245, 249))],
        f_title,
        tracking_px=18,
    )

    # Subtle 3px Johnny Harris crimson/coral rule accent tucked cleanly under left/right title balance
    rule_y = bb_title[3] + 15
    rule_x0 = cx - 295
    rule_x1 = cx - 10
    tdraw.line((rule_x0, rule_y, rule_x1, rule_y), fill=(*accent_bar_rgb, 175), width=2)

    # Handwritten Caveat documentary credit tucked cleanly right-of-center under main title
    sig_bb = _draw_tracked_segments(
        tdraw,
        cx + 155,
        bb_title[3] + 10,
        [(signature_text, (218, 232, 238))],
        f_sig,
        tracking_px=0,
    )

    canvas = Image.alpha_composite(canvas, text_layer)
    final_f = np.array(canvas.convert("RGB"), dtype=np.float32)

    # 5. Unified 35mm Kodak Vision3 500T optical film grain (~2.2% std)
    rng = np.random.default_rng(seed)
    luma_grain = rng.normal(0.0, float(grain_sigma), size=(BANNER_H, BANNER_W, 1)).astype(np.float32)
    chroma_grain = rng.normal(0.0, float(grain_sigma) * 0.22, size=(BANNER_H, BANNER_W, 3)).astype(np.float32)
    final_f = np.clip(final_f + luma_grain + chroma_grain, 0.0, 255.0)

    ux0 = min(bb_eye[0], bb_title[0], sig_bb[0], rule_x0)
    uy0 = min(bb_eye[1], bb_title[1], sig_bb[1])
    ux1 = max(bb_eye[2], bb_title[2], sig_bb[2])
    uy1 = max(bb_eye[3], bb_title[3], sig_bb[3], rule_y + 2)

    text_bboxes = {
        "eyebrow": list(bb_eye),
        "title": list(bb_title),
        "signature": list(sig_bb),
        "combined_ink_union": [ux0, uy0, ux1, uy1],
    }
    return Image.fromarray(final_f.astype(np.uint8), mode="RGB"), {
        "text_bboxes": text_bboxes,
        "wing_notes_count": len(wing_notes_bboxes) if with_notes else 0,
        "with_notes": bool(with_notes),
    }


def finish_jh_banner_image(
    input_path: Path,
    out_path: Path,
    *,
    with_notes: bool = True,
    eyebrow_text: str = "ORIGINAL NEUROSCIENCE SERIES",
    signature_text: str = "inside the human mind",
    seed: int = 9931,
) -> dict[str, Any]:
    """Reusable CLI/API helper applying the JH 35mm cinema finish to any 16:9 backdrop image."""
    if not input_path.is_file():
        raise FileNotFoundError(f"Missing JH backdrop input image: {input_path}")
    cropped = _cover_crop_2560x1440(input_path, y_frac=0.5, x_frac=0.5)
    finished_rgb, meta = apply_jh_cinema_finish(
        cropped,
        seed=seed,
        with_notes=with_notes,
        eyebrow_text=eyebrow_text,
        signature_text=signature_text,
    )
    _atomic_save_image(finished_rgb, out_path, format="PNG", optimize=True)
    return {
        "file": out_path.name,
        "output_path": str(out_path),
        "input_path": str(input_path),
        "width": BANNER_W,
        "height": BANNER_H,
        "safe_zone_box": list(SAFE_ZONE_BOX),
        "desktop_zone_box": list(DESKTOP_ZONE_BOX),
        "with_notes": bool(with_notes),
        "text_bboxes": meta["text_bboxes"],
        "sha256": _sha256_file(out_path),
        "bytes": out_path.stat().st_size,
    }


def build_banner_jh1_lightbox(out_path: Path) -> dict[str, Any]:
    """JH-1: Midnight Neuroscience Lab x MRI Lightbox (100% zero-face verified sources, 0 floating stickers)."""
    base = _cover_crop_2560x1440(JH5_SOURCE_ASSETS["e01_lab_empty_01"], y_frac=0.50, bg_blur=2.2)
    base_f = np.array(base, dtype=np.float32)
    # Midnight oceanic teal lab grade + lower bright upper wall midtones for dramatic spotlight contrast
    base_f[:, :, 0] *= 0.34
    base_f[:, :, 1] *= 0.54
    base_f[:, :, 2] *= 0.66
    base_f = _add_anamorphic_bokeh_and_light(
        base_f,
        lights=[
            (1930.0, 695.0, 310.0, 220.0, (226, 94, 62), 0.36),
            (380.0, 720.0, 320.0, 220.0, (36, 178, 210), 0.22),
        ],
        seed=9101,
        n_bokeh=18,
    )
    canvas = Image.fromarray(base_f.astype(np.uint8), mode="RGB").convert("RGBA")

    # Crop tight around dual brain MRI lightbox scans in G01 (removing pale grey pedestal slab below)
    with Image.open(JH5_SOURCE_ASSETS["g01_mri_lightbox_01"]) as im_g:
        gw, gh = im_g.size
        mri_tight = im_g.crop((int(gw * 0.06), int(gh * 0.31), int(gw * 0.94), int(gh * 0.67))).convert("RGBA")
    # Darken outer border of MRI tray into smoky dark glass frame & place cleanly clear of title (x=1925)
    canvas = _feather_paste_rgba(
        canvas,
        mri_tight,
        (1925, 708),
        target_w=255,
        edge_feather_frac=0.28,
        edge_blur_px=34.0,
        opacity=0.86,
        tint_rgb=(210, 92, 72),
        tint_strength=0.14,
    )

    finished_rgb, finish_meta = apply_jh_cinema_finish(
        canvas.convert("RGB"),
        seed=9101,
        with_notes=True,
        eyebrow_text="ORIGINAL NEUROSCIENCE SERIES",
        signature_text="inside the human mind",
        left_notes=[
            ("fig. 01  ·  T1 structural scan", -5.2),
            ("lab bench 04  ·  01:18 AM", 2.8),
            ("cortical map  ->  baseline", -2.4),
        ],
        right_notes=[
            ("lightbox  ·  dual hemisphere", 4.1),
            ("sulcal vessel contrast +1.4", -3.4),
            ("peer-reviewed evidence", 2.1),
        ],
        scrim_peak_alpha=0.64,
        accent_bar_rgb=(228, 92, 68),
    )
    _atomic_save_image(finished_rgb, out_path, format="PNG", optimize=True)
    return {
        "file": out_path.name,
        "variant": "jh1_lightbox",
        "width": BANNER_W,
        "height": BANNER_H,
        "source_keys": ["e01_lab_empty_01", "g01_mri_lightbox_01"],
        "safe_zone_box": list(SAFE_ZONE_BOX),
        "desktop_zone_box": list(DESKTOP_ZONE_BOX),
        "text_bboxes": finish_meta["text_bboxes"],
        "sha256": _sha256_file(out_path),
        "bytes": out_path.stat().st_size,
    }


def build_banner_jh2_crimson_darkroom(out_path: Path) -> dict[str, Any]:
    """JH-2: Crimson Darkroom Specimen Case (TED-red darkroom rim light + zero-face acrylic case)."""
    base = _cover_crop_2560x1440(JH5_SOURCE_ASSETS["e02_mri_empty_01"], y_frac=0.46, bg_blur=5.0)
    base_f = np.array(base, dtype=np.float32)
    luma_b = 0.299 * base_f[:, :, 0] + 0.587 * base_f[:, :, 1] + 0.114 * base_f[:, :, 2]
    dark_f = np.zeros_like(base_f)
    dark_f[:, :, 0] = np.clip(luma_b * 0.44 + 12.0, 0.0, 255.0)
    dark_f[:, :, 1] = np.clip(luma_b * 0.10 + 4.0, 0.0, 255.0)
    dark_f[:, :, 2] = np.clip(luma_b * 0.12 + 7.0, 0.0, 255.0)
    dark_f = _add_anamorphic_bokeh_and_light(
        dark_f,
        lights=[
            (1920.0, 700.0, 340.0, 260.0, (212, 36, 40), 0.34),
            (360.0, 720.0, 310.0, 220.0, (184, 28, 34), 0.24),
            (1915.0, 712.0, 140.0, 120.0, (39, 216, 255), 0.14),
        ],
        seed=9202,
        n_bokeh=18,
    )
    canvas = Image.fromarray(dark_f.astype(np.uint8), mode="RGB").convert("RGBA")

    # Right-side acrylic plaster brain specimen case (H01 cand_02, strictly 0 faces), cropped tight around cube & placed clear of title
    with Image.open(JH5_SOURCE_ASSETS["h01_glass_case_02"]) as im_h:
        hw, hh = im_h.size
        case_tight = im_h.crop((int(hw * 0.10), int(hh * 0.30), int(hw * 0.90), int(hh * 0.72))).convert("RGBA")
    canvas = _feather_paste_rgba(
        canvas,
        case_tight,
        (1920, 714),
        target_w=300,
        edge_feather_frac=0.40,
        edge_blur_px=52.0,
        opacity=0.88,
        tint_rgb=(210, 44, 48),
        tint_strength=0.18,
    )

    finished_rgb, finish_meta = apply_jh_cinema_finish(
        canvas.convert("RGB"),
        seed=9202,
        with_notes=True,
        eyebrow_text="ORIGINAL NEUROSCIENCE SERIES",
        signature_text="specimen archive · 35mm",
        left_notes=[
            ("darkroom vault  ·  02", -4.8),
            ("crimson safelight  660nm", 3.4),
            ("sulcal fold  ->  gypsum", -2.2),
        ],
        right_notes=[
            ("vitrine  ·  case H-02", 4.5),
            ("sealed cortex specimen", -3.1),
            ("cyan vascular resonance", 2.0),
        ],
        scrim_peak_alpha=0.58,
        accent_bar_rgb=(230, 43, 30),
    )
    _atomic_save_image(finished_rgb, out_path, format="PNG", optimize=True)
    return {
        "file": out_path.name,
        "variant": "jh2_crimson_darkroom",
        "width": BANNER_W,
        "height": BANNER_H,
        "source_keys": ["e02_mri_empty_01", "h01_glass_case_02"],
        "safe_zone_box": list(SAFE_ZONE_BOX),
        "desktop_zone_box": list(DESKTOP_ZONE_BOX),
        "text_bboxes": finish_meta["text_bboxes"],
        "sha256": _sha256_file(out_path),
        "bytes": out_path.stat().st_size,
    }


JH3_FINAL_EYEBROW = "PEER-REVIEWED NEUROSCIENCE"
JH3_FINAL_SIGNATURE = "inside the human mind"
JH3_FINAL_LEFT_NOTES: list[tuple[str, float]] = [
    ("what makes us conscious?", -5.4),
    ("86 billion neurons", 3.6),
    ("memory  ->  emotion  ->  choice", -2.9),
]
JH3_FINAL_RIGHT_NOTES: list[tuple[str, float]] = [
    ("real experiments, real data", 4.0),
    ("one study, one story", -3.3),
    ("how the brain rewires", 2.2),
]
JH3_BANNED_INTERNAL_TERMS: tuple[str, ...] = ("salmon rim", "translucent cranium")


def build_banner_jh3_human_element_homage(out_path: Path) -> dict[str, Any]:
    """
    JH-3: 1:1 Homage to Johnny Harris 'THE HUMAN ELEMENT' (bench_sheet Row 4):
      - Silky misty teal coastal horizon (#173E4F -> #3D8096 -> #6BABB2) with layered atmospheric ridges
      - Warm salmon-crimson edge rim light (#E0523C)
      - Tall faceless frosted glass Mode 1 cranium + glowing #27D8FF brain (0 facial features)
    """
    yy, xx = np.mgrid[0:BANNER_H, 0:BANNER_W].astype(np.float32)
    y_norm = yy / float(BANNER_H - 1)

    stops_y = np.array([0.0, 0.34, 0.50, 0.64, 0.78, 1.0], dtype=np.float32)
    stops_r = np.array([14.0, 26.0, 74.0, 102.0, 28.0, 12.0], dtype=np.float32)
    stops_g = np.array([38.0, 72.0, 144.0, 170.0, 68.0, 30.0], dtype=np.float32)
    stops_b = np.array([49.0, 92.0, 160.0, 178.0, 82.0, 40.0], dtype=np.float32)
    grad = np.zeros((BANNER_H, BANNER_W, 3), dtype=np.float32)
    grad[:, :, 0] = np.interp(y_norm, stops_y, stops_r)
    grad[:, :, 1] = np.interp(y_norm, stops_y, stops_g)
    grad[:, :, 2] = np.interp(y_norm, stops_y, stops_b)

    # Organic misty coastal headland silhouettes (pure smooth harmonic waves, zero blocky buildings)
    ridge_y1 = 790.0 + 48.0 * np.sin(xx * 0.0018 + 0.6) + 22.0 * np.cos(xx * 0.0043 + 1.2)
    ridge_y2 = 865.0 + 32.0 * np.sin(xx * 0.0029 + 2.3) + 14.0 * np.sin(xx * 0.0071)
    m1 = 1.0 / (1.0 + np.exp(-(yy - ridge_y1) / 18.0))
    m2 = 1.0 / (1.0 + np.exp(-(yy - ridge_y2) / 15.0))
    grad = grad * (1.0 - 0.38 * m1[:, :, None]) + np.array([16.0, 42.0, 54.0], dtype=np.float32)[None, None, :] * (0.38 * m1[:, :, None])
    grad = grad * (1.0 - 0.44 * m2[:, :, None]) + np.array([9.0, 25.0, 33.0], dtype=np.float32)[None, None, :] * (0.44 * m2[:, :, None])

    # Heavily diffused atmospheric cloud luminescence from verified zero-face campus horizon (no crisp architecture shapes)
    tex = _cover_crop_2560x1440(JH5_SOURCE_ASSETS["d01_campus_drone_02"], y_frac=0.35, bg_blur=42.0)
    tex_f = np.array(tex, dtype=np.float32)
    tex_luma = (0.299 * tex_f[:, :, 0] + 0.587 * tex_f[:, :, 1] + 0.114 * tex_f[:, :, 2])[:, :, None]
    grad = np.clip(grad * 0.90 + tex_luma * np.array([0.06, 0.14, 0.16], dtype=np.float32)[None, None, :], 0.0, 255.0)

    # Vivid Johnny Harris salmon-coral key light + cool teal mist rim around centered glass cranium
    grad = _add_anamorphic_bokeh_and_light(
        grad,
        lights=[
            (1425.0, 690.0, 310.0, 240.0, (230, 88, 62), 0.46),
            (1265.0, 710.0, 240.0, 210.0, (39, 216, 255), 0.22),
            (320.0, 700.0, 380.0, 210.0, (78, 168, 182), 0.14),
        ],
        seed=9303,
        n_bokeh=12,
    )
    canvas = Image.fromarray(grad.astype(np.uint8), mode="RGB").convert("RGBA")

    # Taller faceless frosted glass Mode 1 cranium centered cleanly so brain & coral key shine behind title
    a01_rgba, _ = _extract_subject_rgba(
        JH5_SOURCE_ASSETS["a01_mode1_head_01"],
        bg_threshold=15.0,
        ramp_span=18.0,
        feather_sigma=1.8,
    )
    a01_faceless = _soften_glass_face_features(a01_rgba)
    af = a01_faceless.astype(np.float32)
    ah, aw, _ = af.shape
    a_alp = af[:, :, 3] / 255.0
    edge_dx = np.abs(np.gradient(a_alp, axis=1))
    right_weight = np.linspace(0.0, 1.0, aw)[None, :] ** 1.15
    rim = np.clip(edge_dx * 9.5, 0.0, 1.0) * right_weight
    body_glow = a_alp * (np.linspace(0.0, 1.0, aw)[None, :] ** 2.2) * 0.28
    af[:, :, 0] = np.clip(af[:, :, 0] + rim * 175.0 + body_glow * 225.0, 0.0, 255.0)
    af[:, :, 1] = np.clip(af[:, :, 1] + rim * 52.0 + body_glow * 74.0, 0.0, 255.0)
    af[:, :, 2] = np.clip(af[:, :, 2] + rim * 32.0 + body_glow * 50.0, 0.0, 255.0)

    canvas = _feather_paste_rgba(
        canvas,
        Image.fromarray(af.astype(np.uint8), mode="RGBA"),
        (BANNER_W // 2, 728),
        target_h=650,
        edge_feather_frac=0.14,
        edge_blur_px=18.0,
        opacity=0.92,
    )

    finished_rgb, finish_meta = apply_jh_cinema_finish(
        canvas.convert("RGB"),
        seed=9303,
        with_notes=True,
        eyebrow_text=JH3_FINAL_EYEBROW,
        signature_text=JH3_FINAL_SIGNATURE,
        left_notes=JH3_FINAL_LEFT_NOTES,
        right_notes=JH3_FINAL_RIGHT_NOTES,
        scrim_peak_alpha=0.52,
        accent_bar_rgb=(230, 88, 62),
    )
    _atomic_save_image(finished_rgb, out_path, format="PNG", optimize=True)
    return {
        "file": out_path.name,
        "variant": "jh3_human_element_homage",
        "width": BANNER_W,
        "height": BANNER_H,
        "source_keys": ["d01_campus_drone_02", "a01_mode1_head_01"],
        "safe_zone_box": list(SAFE_ZONE_BOX),
        "desktop_zone_box": list(DESKTOP_ZONE_BOX),
        "copy_slots": {
            "eyebrow_text": JH3_FINAL_EYEBROW,
            "signature_text": JH3_FINAL_SIGNATURE,
            "left_notes": [txt for txt, _ in JH3_FINAL_LEFT_NOTES],
            "right_notes": [txt for txt, _ in JH3_FINAL_RIGHT_NOTES],
        },
        "text_bboxes": finish_meta["text_bboxes"],
        "sha256": _sha256_file(out_path),
        "bytes": out_path.stat().st_size,
    }


def build_banner_jh3_yt_upload(
    src_png_path: Path,
    out_jpg_path: Path,
    *,
    copy_bboxes: dict[str, Any],
) -> dict[str, Any]:
    """
    Create visually lossless 4:4:4 JPEG upload master (`<= 5.5 MB`) for YouTube Studio
    because PNG film grain pushes the raw PNG above Studio's strict 6 MB banner cap.
    """
    with Image.open(src_png_path) as im:
        rgb = im.convert("RGB")
        if rgb.size != (BANNER_W, BANNER_H):
            raise ValueError(f"Expected {BANNER_W}x{BANNER_H} banner master, got {rgb.size}")

    chosen_q = 96
    for q in (96, 95, 94, 93, 92):
        _atomic_save_image(rgb, out_jpg_path, format="JPEG", quality=q, subsampling=0, optimize=True)
        chosen_q = q
        if out_jpg_path.stat().st_size <= YT_BANNER_UPLOAD_MAX_BYTES:
            break

    n_bytes = out_jpg_path.stat().st_size
    if n_bytes > YT_BANNER_UPLOAD_MAX_BYTES:
        raise RuntimeError(
            f"YouTube upload JPEG {out_jpg_path.name} exceeded {YT_BANNER_UPLOAD_MAX_BYTES} B limit ({n_bytes} B)"
        )

    return {
        "file": out_jpg_path.name,
        "variant": "jh3_yt_upload_444",
        "source_master": src_png_path.name,
        "width": BANNER_W,
        "height": BANNER_H,
        "jpeg_quality": chosen_q,
        "subsampling": "4:4:4",
        "max_upload_bytes": YT_BANNER_UPLOAD_MAX_BYTES,
        "safe_zone_box": list(SAFE_ZONE_BOX),
        "desktop_zone_box": list(DESKTOP_ZONE_BOX),
        "text_bboxes": copy_bboxes,
        "sha256": _sha256_file(out_jpg_path),
        "bytes": n_bytes,
    }


def build_banner_jh4_fmri_tunnel(out_path: Path) -> dict[str, Any]:
    """JH-4: 3T fMRI Scanner Tunnel Cinema Still (nocturnal 3T bore + subtle coronal hologram right of title)."""
    base = _cover_crop_2560x1440(JH5_SOURCE_ASSETS["e02_mri_empty_01"], y_frac=0.52, bg_blur=1.6)
    base_f = np.array(base, dtype=np.float32)
    # Rich dark nocturnal 3T MRI suite grade (tame bright cream walls for true 35mm cinema atmosphere)
    base_f[:, :, 0] *= 0.40
    base_f[:, :, 1] *= 0.60
    base_f[:, :, 2] *= 0.72
    base_f = _add_anamorphic_bokeh_and_light(
        base_f,
        lights=[
            (1930.0, 710.0, 290.0, 210.0, (39, 216, 255), 0.24),
            (1420.0, 680.0, 240.0, 170.0, (226, 78, 56), 0.20),
            (380.0, 720.0, 320.0, 220.0, (28, 148, 178), 0.16),
        ],
        seed=9404,
        n_bokeh=18,
    )
    canvas = Image.fromarray(base_f.astype(np.uint8), mode="RGB").convert("RGBA")

    # Single translucent cyan holographic coronal hippocampus scan strictly right of title (0 left sticker!)
    hipp_rgba, _ = _extract_subject_rgba(
        JH5_SOURCE_ASSETS["a18_coronal_hipp_01"],
        bg_threshold=22.0,
        ramp_span=24.0,
        feather_sigma=2.4,
    )
    canvas = _feather_paste_rgba(
        canvas,
        Image.fromarray(hipp_rgba, mode="RGBA"),
        (1935, 716),
        target_h=305,
        edge_feather_frac=0.28,
        edge_blur_px=30.0,
        opacity=0.76,
        tint_rgb=(39, 216, 255),
        tint_strength=0.18,
    )

    finished_rgb, finish_meta = apply_jh_cinema_finish(
        canvas.convert("RGB"),
        seed=9404,
        with_notes=True,
        eyebrow_text="ORIGINAL NEUROSCIENCE SERIES",
        signature_text="3T neuroimaging series",
        left_notes=[
            ("3.0 Tesla  fMRI bore", -4.6),
            ("TR = 800ms · TE = 30ms", 3.1),
            ("BOLD hemodynamic signal", -2.5),
        ],
        right_notes=[
            ("bilateral hippocampus", 4.3),
            ("coronal slice  y = -22", -3.0),
            ("memory circuit lock", 2.0),
        ],
        scrim_peak_alpha=0.66,
        accent_bar_rgb=(39, 216, 255),
    )
    _atomic_save_image(finished_rgb, out_path, format="PNG", optimize=True)
    return {
        "file": out_path.name,
        "variant": "jh4_fmri_tunnel",
        "width": BANNER_W,
        "height": BANNER_H,
        "source_keys": ["e02_mri_empty_01", "a18_coronal_hipp_01"],
        "safe_zone_box": list(SAFE_ZONE_BOX),
        "desktop_zone_box": list(DESKTOP_ZONE_BOX),
        "text_bboxes": finish_meta["text_bboxes"],
        "sha256": _sha256_file(out_path),
        "bytes": out_path.stat().st_size,
    }


def build_banner_jh5_investigator_desk(out_path: Path) -> dict[str, Any]:
    """JH-5: Investigative Neuroscience Evidence Desk (2900K moody walnut desk + grounded gypsum brain model)."""
    base = _cover_crop_2560x1440(JH5_SOURCE_ASSETS["g08_desk_stimulus_01"], y_frac=0.62, bg_blur=2.0)
    base_f = np.array(base, dtype=np.float32)
    # Suppress distracting bright cream card center contrast into deep warm nocturnal desk shadows
    base_f[:, :, 0] *= 0.48
    base_f[:, :, 1] *= 0.42
    base_f[:, :, 2] *= 0.44
    base_f = _add_anamorphic_bokeh_and_light(
        base_f,
        lights=[
            (380.0, 620.0, 400.0, 260.0, (228, 102, 58), 0.30),
            (1940.0, 725.0, 310.0, 220.0, (216, 88, 56), 0.26),
        ],
        seed=9505,
        n_bokeh=16,
    )
    canvas = Image.fromarray(base_f.astype(np.uint8), mode="RGB").convert("RGBA")

    # Grounded physical contact drop shadow + sculpted matte-gypsum brain model (A02) cleanly right of title
    a02_rgba, _ = _extract_subject_rgba(
        JH5_SOURCE_ASSETS["a02_lateral_brain_02"],
        bg_threshold=16.0,
        ramp_span=19.0,
        feather_sigma=1.8,
    )
    a02_clean = _enhance_gypsum_and_cyan(a02_rgba, cyan_boost=1.18, contrast_gain=1.08)
    shadow_a02 = a02_clean.copy()
    shadow_a02[:, :, :3] = np.array([10, 6, 4], dtype=np.uint8)
    shadow_a02[:, :, 3] = np.clip(shadow_a02[:, :, 3].astype(np.float32) * 0.68, 0.0, 255.0).astype(np.uint8)
    canvas = _feather_paste_rgba(
        canvas,
        Image.fromarray(shadow_a02, mode="RGBA").filter(ImageFilter.GaussianBlur(radius=14.0)),
        (1956, 742),
        target_h=305,
        edge_feather_frac=0.14,
        edge_blur_px=16.0,
        opacity=0.85,
    )
    canvas = _feather_paste_rgba(
        canvas,
        Image.fromarray(a02_clean, mode="RGBA"),
        (1938, 722),
        target_h=295,
        edge_feather_frac=0.14,
        edge_blur_px=14.0,
        opacity=0.92,
        tint_rgb=(220, 122, 86),
        tint_strength=0.12,
    )

    finished_rgb, finish_meta = apply_jh_cinema_finish(
        canvas.convert("RGB"),
        seed=9505,
        with_notes=True,
        eyebrow_text="ORIGINAL NEUROSCIENCE SERIES",
        signature_text="neuroscience evidence log",
        left_notes=[
            ("case file  ·  tractography", -5.0),
            ("white matter bundles", 3.3),
            ("DOI verification lock", -2.5),
        ],
        right_notes=[
            ("gypsum cortex study", 4.2),
            ("lamp index  2900K", -3.4),
            ("all about brain", 2.0),
        ],
        scrim_peak_alpha=0.68,
        accent_bar_rgb=(228, 108, 62),
    )
    _atomic_save_image(finished_rgb, out_path, format="PNG", optimize=True)
    return {
        "file": out_path.name,
        "variant": "jh5_investigator_desk",
        "width": BANNER_W,
        "height": BANNER_H,
        "source_keys": ["g08_desk_stimulus_01", "a02_lateral_brain_02"],
        "safe_zone_box": list(SAFE_ZONE_BOX),
        "desktop_zone_box": list(DESKTOP_ZONE_BOX),
        "text_bboxes": finish_meta["text_bboxes"],
        "sha256": _sha256_file(out_path),
        "bytes": out_path.stat().st_size,
    }


def build_jh5_collection_comparison_sheet(
    out_path: Path,
    *,
    jh_paths: list[tuple[str, str, str, tuple[int, int, int], Path]],
    ted_red_logo_path: Path,
    header_title: str = "JOHNNY HARRIS 'THE HUMAN ELEMENT' 35MM CINEMA BANNERS  —  JH-1 TO JH-5",
    header_sub: str = "0 CARTOON FACES  ·  PROPORTIONAL SCALING  ·  CAVEAT WING NOTES  ·  SAFE ZONE (1546×423) + TED RED AVATAR PAIRING",
    header_accent_rgb: tuple[int, int, int] = (228, 92, 68),
) -> dict[str, Any]:
    """
    Build 5-row Johnny Harris 35mm Cinema Collection contact sheet (2400x3612 RGB JPEG):
      For each card:
        - Full 2560x423 Desktop strip + green dashed 1546x423 Mobile Safe Zone
        - Live #0F0F0F Desktop Channel Header + Mobile Channel Header paired with TED Red avatar
        - Full 16:9 TV bleed preview
    """
    board_w = 2400
    card_h = 668
    gap_y = 24
    header_h = 120
    margin_x = 40
    board_h = header_h + 24 + len(jh_paths) * card_h + max(0, len(jh_paths) - 1) * gap_y + 32

    board = Image.new("RGB", (board_w, board_h), (8, 14, 22))
    draw = ImageDraw.Draw(board)

    f_hdr = _load_font(PRIMARY_DISPLAY_FONT, 44)
    f_hdr_sub = _load_font(PRIMARY_BODY_FONT, 19, weight=550)
    f_card_title = _load_font(PRIMARY_DISPLAY_FONT, 28)
    f_card_sub = _load_font(PRIMARY_BODY_FONT, 16, weight=450)
    f_badge = _load_font(PRIMARY_BODY_FONT, 14, weight=700)
    f_ui_bold = _load_font(PRIMARY_BODY_FONT, 16, weight=700)
    f_ui_sm = _load_font(PRIMARY_BODY_FONT, 13, weight=600)
    f_ui_tiny = _load_font(PRIMARY_BODY_FONT, 12, weight=500)

    draw.rectangle((0, 0, board_w, header_h), fill=(11, 20, 32))
    draw.text(
        (48, 24),
        header_title,
        fill=(245, 247, 250),
        font=f_hdr,
    )
    draw.text(
        (48, 78),
        header_sub,
        fill=header_accent_rgb,
        font=f_hdr_sub,
    )
    draw.line((0, header_h, board_w, header_h), fill=header_accent_rgb, width=2)

    with Image.open(ted_red_logo_path) as lim:
        av_rgb = lim.convert("RGB")
    av_54 = _make_circular_avatar(av_rgb, 54)
    av_42 = _make_circular_avatar(av_rgb, 42)

    card_w = board_w - 2 * margin_x
    for idx, (title, subtitle, tag, accent_rgb, bpath) in enumerate(jh_paths):
        cy = header_h + 24 + idx * (card_h + gap_y)
        draw.rounded_rectangle(
            (margin_x, cy, margin_x + card_w, cy + card_h),
            radius=14,
            fill=(12, 18, 28),
            outline=accent_rgb,
            width=2,
        )
        draw.rounded_rectangle((margin_x + 20, cy + 14, margin_x + 208, cy + 42), radius=6, fill=accent_rgb)
        draw.text((margin_x + 114, cy + 28), tag, fill=(8, 12, 18), font=f_badge, anchor="mm")
        draw.text((margin_x + 224, cy + 14), title, fill=(245, 247, 250), font=f_card_title)
        draw.text((margin_x + 224, cy + 48), subtitle, fill=(148, 163, 184), font=f_card_sub)

        with Image.open(bpath) as bim:
            bfull = bim.convert("RGB")
        strip_crop = bfull.crop(DESKTOP_ZONE_BOX)
        mob_crop = bfull.crop(SAFE_ZONE_BOX)

        # Full 2560x423 Desktop strip + green 1546x423 Mobile Safe Box
        sx = margin_x + 20
        sy = cy + 78
        disp_w = 1720
        disp_h = int(round(disp_w * (423.0 / 2560.0)))  # 284px
        board.paste(strip_crop.resize((disp_w, disp_h), resample=Image.Resampling.LANCZOS), (sx, sy))
        draw.rectangle((sx, sy, sx + disp_w, sy + disp_h), outline=(64, 84, 112), width=2)
        mx0 = sx + int(round(disp_w * (SAFE_ZONE_BOX[0] / float(BANNER_W))))
        mx1 = sx + int(round(disp_w * (SAFE_ZONE_BOX[2] / float(BANNER_W))))
        _draw_dashed_rect(draw, (mx0, sy + 2, mx1, sy + disp_h - 2), outline=(34, 197, 94), width=2, dash=14, gap=8)

        # TV 16:9 Full Preview on top-right of card
        tv_x = sx + disp_w + 20
        tv_w = card_w - 40 - disp_w - 20  # 540px
        tv_h = int(round(tv_w * (9.0 / 16.0)))  # 304px
        board.paste(bfull.resize((tv_w, tv_h), resample=Image.Resampling.LANCZOS), (tv_x, sy))
        draw.rectangle((tv_x, sy, tv_x + tv_w, sy + tv_h), outline=(80, 96, 120), width=2)
        _draw_dashed_hline(draw, tv_x + 2, tv_x + tv_w - 2, sy + int(round(tv_h * (SAFE_ZONE_BOX[1] / float(BANNER_H)))), fill=(34, 197, 94), width=1)
        _draw_dashed_hline(draw, tv_x + 2, tv_x + tv_w - 2, sy + int(round(tv_h * (SAFE_ZONE_BOX[3] / float(BANNER_H)))), fill=(34, 197, 94), width=1)
        draw.text((tv_x + 8, sy + tv_h + 6), "TV 16:9 FULL BLEED (2560×1440)", fill=(148, 163, 184), font=f_ui_tiny)

        # 2. Live #0F0F0F Desktop + Mobile YouTube UI Previews paired with TED Red Avatar below top strip
        row_y = sy + disp_h + 16
        ui_h = card_h - (row_y - cy) - 16
        desk_pw = 1040
        desk_px = sx
        draw.rounded_rectangle((desk_px, row_y, desk_px + desk_pw, row_y + ui_h), radius=10, fill=(15, 15, 15), outline=(44, 54, 72), width=1)
        d_bw = desk_pw - 28
        d_bh = int(round(d_bw * (423.0 / 2560.0)))  # 167px
        board.paste(strip_crop.resize((d_bw, d_bh), resample=Image.Resampling.LANCZOS), (desk_px + 14, row_y + 14))
        board.paste(av_54, (desk_px + 20, row_y + 14 + d_bh + 14), mask=av_54.split()[3])
        draw.text((desk_px + 88, row_y + 14 + d_bh + 16), "All About Brain", fill=(255, 255, 255), font=f_ui_bold)
        draw.text((desk_px + 88, row_y + 14 + d_bh + 38), "@AllAboutBrainOfficial · DESKTOP #0F0F0F + TED RED", fill=(170, 170, 170), font=f_ui_tiny)
        draw.rounded_rectangle((desk_px + desk_pw - 132, row_y + 14 + d_bh + 24, desk_px + desk_pw - 22, row_y + 14 + d_bh + 54), radius=15, fill=(255, 255, 255))
        draw.text((desk_px + desk_pw - 77, row_y + 14 + d_bh + 39), "Subscribe", fill=(15, 15, 15), font=f_ui_sm, anchor="mm")

        mob_px = desk_px + desk_pw + 18
        mob_pw = disp_w - desk_pw - 18  # 662px
        draw.rounded_rectangle((mob_px, row_y, mob_px + mob_pw, row_y + ui_h), radius=10, fill=(15, 15, 15), outline=(44, 54, 72), width=1)
        m_bw = mob_pw - 28
        m_bh = int(round(m_bw * (423.0 / 1546.0)))  # 173px
        board.paste(mob_crop.resize((m_bw, m_bh), resample=Image.Resampling.LANCZOS), (mob_px + 14, row_y + 14))
        board.paste(av_42, (mob_px + 20, row_y + 14 + m_bh + 14), mask=av_42.split()[3])
        draw.text((mob_px + 74, row_y + 14 + m_bh + 16), "All About Brain", fill=(255, 255, 255), font=f_ui_bold)
        draw.text((mob_px + 74, row_y + 14 + m_bh + 38), "MOBILE 1546×423 SAFE CROP + TED RED", fill=(34, 197, 94), font=f_ui_tiny)

    _atomic_save_image(board, out_path, format="JPEG", quality=93, subsampling=0)
    return {
        "file": out_path.name,
        "width": board_w,
        "height": board_h,
        "variants_compared": len(jh_paths),
        "sha256": _sha256_file(out_path),
        "bytes": out_path.stat().st_size,
    }


def _verify_jh5_banner_entry(
    output_dir: Path,
    fname: str,
    banner_meta: dict[str, Any],
    issues: list[str],
    label: str,
) -> dict[str, Any]:
    """
    Verify JH-1..JH-5 35mm Cinema Banner contract:
      1. Eyebrow + title + Caveat signature strictly inside SAFE_ZONE_BOX (507, 508, 2053, 931).
      2. Zero banned cartoon/face canonical source tokens (B01-B15, G02, E06, E07, A16, A17).
      3. Zero hard compositing rectangular boundary steps along wing blend transitions.
      4. Unified 35mm optical film grain + moody edge falloff + crisp ivory title contrast.
    """
    bboxes = banner_meta.get("text_bboxes", {})
    union_bb = bboxes.get("combined_ink_union", [])
    safe_bounds_ok = False
    if len(union_bb) == 4:
        ux0, uy0, ux1, uy1 = [int(v) for v in union_bb]
        safe_bounds_ok = (
            ux0 >= SAFE_ZONE_BOX[0] + 20
            and uy0 >= SAFE_ZONE_BOX[1] + 20
            and ux1 <= SAFE_ZONE_BOX[2] - 20
            and uy1 <= SAFE_ZONE_BOX[3] - 20
            and set(bboxes.keys()) >= {"eyebrow", "title", "signature", "combined_ink_union"}
        )
    if not safe_bounds_ok:
        issues.append(f"{label} safe-zone lockup check failed: keys={list(bboxes.keys())}, union={union_bb}")

    src_keys = [str(k) for k in (banner_meta.get("source_keys") or [])]
    banned_hits = [
        k for k in src_keys if any(tok.lower() in k.lower() for tok in BANNED_JH5_TOKENS)
    ]
    zero_cartoon_faces_ok = len(src_keys) >= 2 and len(banned_hits) == 0
    if not zero_cartoon_faces_ok:
        issues.append(f"{label} source check failed: src_keys={src_keys}, banned_hits={banned_hits}")

    zero_hard_seams_ok = False
    cinema_grain_and_depth_ok = False
    fpath = output_dir / fname
    if fpath.is_file():
        rgb = np.array(Image.open(fpath).convert("RGB"), dtype=np.float32)
        luma = 0.299 * rgb[:, :, 0] + 0.587 * rgb[:, :, 1] + 0.114 * rgb[:, :, 2]

        # Inspect soft feather transitions along Desktop/Mobile/Wing framing boundaries (excluding central centered hero silhouette x=1060..1500)
        seam_checks = [
            np.abs(np.diff(luma[480:520, 220:1060], axis=0)),
            np.abs(np.diff(luma[480:520, 1500:2340], axis=0)),
            np.abs(np.diff(luma[920:960, 220:1060], axis=0)),
            np.abs(np.diff(luma[920:960, 1500:2340], axis=0)),
            np.abs(np.diff(luma[520:920, 480:540], axis=1)),
            np.abs(np.diff(luma[520:920, 2020:2080], axis=1)),
        ]
        p99_seam = float(max(np.percentile(band, 99.5) for band in seam_checks))
        zero_hard_seams_ok = p99_seam <= 32.0
        if not zero_hard_seams_ok:
            issues.append(f"{label} hard seam gradient detected: p99_5={p99_seam:.2f}")

        corner_luma = luma[12:92, 12:92]
        corner_mean = float(corner_luma.mean())
        corner_std = float(corner_luma.std())
        title_box = bboxes.get("title", [900, 650, 1660, 770])
        tx0, ty0, tx1, ty1 = [max(0, int(v)) for v in title_box]
        title_peak = float(np.percentile(luma[ty0:ty1, tx0:tx1], 99.0)) if (tx1 > tx0 and ty1 > ty0) else 0.0
        cinema_grain_and_depth_ok = (corner_std >= 2.2) and (corner_mean <= 78.0) and (title_peak >= 210.0)
        if not cinema_grain_and_depth_ok:
            issues.append(
                f"{label} cinema grain/contrast check failed: corner_mean={corner_mean:.2f}, "
                f"corner_std={corner_std:.2f}, title_peak={title_peak:.2f}"
            )

    return {
        "safe_zone_box": list(SAFE_ZONE_BOX),
        "combined_ink_union": union_bb,
        "source_keys": src_keys,
        "safe_bounds_ok": safe_bounds_ok,
        "zero_cartoon_faces_ok": zero_cartoon_faces_ok,
        "zero_hard_seams_ok": zero_hard_seams_ok,
        "cinema_grain_and_depth_ok": cinema_grain_and_depth_ok,
    }


def _make_jh2_660nm_crimson_backdrop(
    src_path: Path,
    *,
    y_frac: float = 0.46,
    bg_blur: float = 5.0,
    seed: int = 9600,
    extra_lights: list[tuple[float, float, float, float, tuple[int, int, int], float]] | None = None,
) -> np.ndarray:
    """
    Build JH-2 signature 660nm crimson darkroom photographic backdrop (float32 RGB 2560x1440).
    Maps architectural room luminance into deep #1E0305 -> #3B070B -> #8F151A crimson safelight tones.
    """
    base = _cover_crop_2560x1440(src_path, y_frac=y_frac, bg_blur=bg_blur)
    base_f = np.array(base, dtype=np.float32)
    luma_b = 0.299 * base_f[:, :, 0] + 0.587 * base_f[:, :, 1] + 0.114 * base_f[:, :, 2]

    dark_f = np.zeros_like(base_f)
    dark_f[:, :, 0] = np.clip(luma_b * 0.46 + 13.0, 0.0, 255.0)
    dark_f[:, :, 1] = np.clip(luma_b * 0.095 + 4.0, 0.0, 255.0)
    dark_f[:, :, 2] = np.clip(luma_b * 0.115 + 6.0, 0.0, 255.0)

    lights: list[tuple[float, float, float, float, tuple[int, int, int], float]] = [
        (1280.0, 720.0, 620.0, 320.0, (176, 26, 30), 0.24),
        (360.0, 720.0, 320.0, 220.0, (186, 28, 34), 0.22),
        (2180.0, 700.0, 340.0, 230.0, (204, 34, 38), 0.24),
    ]
    if extra_lights:
        lights.extend(extra_lights)

    return _add_anamorphic_bokeh_and_light(
        dark_f,
        lights=lights,
        seed=seed,
        n_bokeh=18,
        bokeh_colors=((222.0, 38.0, 44.0), (168.0, 22.0, 28.0)),
    )


def _extract_subject_hologram_energy(
    image_path: Path,
    *,
    target_h: int,
    faceless_glass: bool = False,
    mirror_x: bool = False,
    boost: float = 1.12,
) -> np.ndarray:
    """
    Extract pure [0..1] float32 glowing #27D8FF anatomical hologram wireframe + sulcal vessels
    scaled proportionally to `target_h` (0 opaque white/grey fill -> 0 pink mud on crimson).
    """
    rgba, bbox = _extract_subject_rgba(image_path, bg_threshold=14.0, ramp_span=17.0, feather_sigma=1.4)
    if faceless_glass:
        rgba = _soften_glass_face_features(rgba)
    x0, y0, x1, y1 = bbox
    crop = rgba[y0:y1, x0:x1].copy()
    if mirror_x:
        crop = np.ascontiguousarray(crop[:, ::-1, :])
    ch, cw, _ = crop.shape
    scale = float(target_h) / float(ch)
    nw = max(16, int(round(cw * scale)))
    nh = max(16, int(round(ch * scale)))
    resized = np.array(
        Image.fromarray(crop, mode="RGBA").resize((nw, nh), resample=Image.Resampling.LANCZOS),
        dtype=np.uint8,
    )

    energy = _build_cyan_mri_hologram_energy(resized)
    fg = (resized[:, :, 3] > 80).astype(np.uint8)
    fg_pad = cv2.copyMakeBorder(fg, 2, 2, 2, 2, cv2.BORDER_CONSTANT, value=0)
    dist_in = cv2.distanceTransform(fg_pad, cv2.DIST_L2, 5)[2:-2, 2:-2]
    alpha_f = resized[:, :, 3].astype(np.float32) / 255.0
    holo_fill = 0.14 * alpha_f * np.exp(-dist_in / 24.0) * (dist_in > 0).astype(np.float32)
    return np.clip(energy * float(boost) + holo_fill, 0.0, 1.0)


def _extract_panoramic_texture_hologram_energy(
    image_path: Path,
    *,
    target_w: int,
    target_h: int,
    mirror_x: bool = False,
) -> np.ndarray:
    """
    Extract feathered super-elliptical cyan cortical/tract ridge hologram stamp [0..1] from
    panoramic micro-anatomy photos (A05 sulcal vessels / A13 white-matter tract canyon).
    """
    with Image.open(image_path) as im:
        src = im.convert("RGB")
    if mirror_x:
        src = src.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    sw, sh = src.size
    sc = max(target_w / float(sw), target_h / float(sh))
    rw, rh = max(target_w, int(round(sw * sc))), max(target_h, int(round(sh * sc)))
    resized = src.resize((rw, rh), resample=Image.Resampling.LANCZOS)
    cx0, cy0 = (rw - target_w) // 2, (rh - target_h) // 2
    crop = np.array(resized.crop((cx0, cy0, cx0 + target_w, cy0 + target_h)), dtype=np.float32)

    luma = 0.299 * crop[:, :, 0] + 0.587 * crop[:, :, 1] + 0.114 * crop[:, :, 2]
    b_fast = cv2.GaussianBlur(luma, (0, 0), sigmaX=1.0, sigmaY=1.0)
    b_slow = cv2.GaussianBlur(luma, (0, 0), sigmaX=3.6, sigmaY=3.6)
    dog = np.maximum(0.0, b_fast - b_slow) / 20.0
    gx = cv2.Sobel(luma, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(luma, cv2.CV_32F, 0, 1, ksize=3)
    sobel = np.sqrt(gx ** 2 + gy ** 2) / 135.0
    # Delicate fine wireframe ridges only (avoid thick solid B-R column fills)
    raw = np.clip(0.80 * dog + 0.62 * sobel, 0.0, 1.0)

    yy, xx = np.mgrid[0:target_h, 0:target_w].astype(np.float32)
    ux = (xx - (target_w - 1) * 0.5) / max(1.0, target_w * 0.5)
    uy = (yy - (target_h - 1) * 0.5) / max(1.0, target_h * 0.5)
    # Soft Gaussian vertical bell + wide horizontal taper -> zero flat top/bottom crop bars
    env_x = np.clip(1.0 - (ux * ux) ** 1.6, 0.0, 1.0)
    env_y = np.exp(-2.6 * (uy * uy))
    env = env_x * env_y
    return np.clip(raw * env, 0.0, 1.0)


def _stamp_horizontal_beam_rails(
    energy_canvas: np.ndarray,
    *,
    x0: int = 180,
    x1: int = 2380,
    y_top: int = 548,
    y_bot: int = 892,
    tick_xs: list[int] | None = None,
    beam_strength: float = 0.14,
) -> np.ndarray:
    """Overlay delicate horizontal holographic projection carrier rails, MNI ticks & soft beam haze."""
    h, w = energy_canvas.shape
    cx = w * 0.5
    cy = h * 0.5
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)

    half_w = max(100.0, (x1 - x0) * 0.5)
    half_h = max(40.0, (y_bot - y_top) * 0.5)
    x_env = np.clip(1.0 - np.maximum(0.0, np.abs(xx - cx) - (half_w * 0.65)) / max(60.0, half_w * 0.42), 0.0, 1.0)
    y_env = np.exp(-0.5 * ((yy - cy) / (half_h * 0.68)) ** 2)
    out = np.maximum(energy_canvas, float(beam_strength) * x_env * y_env)

    rail_mask = Image.new("L", (w, h), 0)
    rdraw = ImageDraw.Draw(rail_mask)
    for yr in (y_top, y_bot):
        rdraw.line((x0, yr, x1, yr), fill=96, width=1)
    rdraw.line((x0 + 80, h // 2, x1 - 80, h // 2), fill=46, width=1)
    if tick_xs:
        for tx in tick_xs:
            rdraw.line((tx, y_top - 7, tx, y_top + 7), fill=150, width=1)
            rdraw.line((tx, y_bot - 7, tx, y_bot + 7), fill=150, width=1)
    rail_f = (np.array(rail_mask, dtype=np.float32) / 255.0) * x_env
    return np.maximum(out, rail_f)


def _finalize_jh2_hologram_banner(
    crimson_rgb_f: np.ndarray,
    energy_full: np.ndarray,
    out_path: Path,
    *,
    variant: str,
    source_keys: list[str],
    seed: int,
    signature_text: str,
    left_notes: list[tuple[str, float]],
    right_notes: list[tuple[str, float]],
    accent_bar_rgb: tuple[int, int, int] = CYAN_RGB,
    scrim_peak_alpha: float = 0.48,
) -> dict[str, Any]:
    """
    Apply 1px holographic laser scanlines + anti-mud optical cyan-on-crimson blending +
    Johnny Harris 35mm cinema lockup & grain, then atomically save 2560x1440 PNG.
    """
    scan_mask = np.ones((BANNER_H, 1), dtype=np.float32)
    scan_mask[0::4, 0] = 0.74
    scan_mask[2::4, 0] = 1.07
    energy_scan = np.where(
        energy_full > 0.012,
        np.clip(energy_full * scan_mask, 0.0, 1.0),
        energy_full,
    )

    blended_f = _blend_cyan_energy_onto_crimson(crimson_rgb_f, energy_scan)
    blended_img = Image.fromarray(blended_f.astype(np.uint8), mode="RGB")

    finished_rgb, finish_meta = apply_jh_cinema_finish(
        blended_img,
        seed=seed,
        with_notes=True,
        eyebrow_text="ORIGINAL NEUROSCIENCE SERIES",
        signature_text=signature_text,
        left_notes=left_notes,
        right_notes=right_notes,
        scrim_peak_alpha=scrim_peak_alpha,
        scrim_rgb=(18.0, 3.0, 6.0),
        scrim_ry=88.0,
        note_ink_rgb=(244, 220, 224),
        accent_bar_rgb=accent_bar_rgb,
    )
    _atomic_save_image(finished_rgb, out_path, format="PNG", optimize=True)
    return {
        "file": out_path.name,
        "variant": variant,
        "width": BANNER_W,
        "height": BANNER_H,
        "source_keys": source_keys,
        "safe_zone_box": list(SAFE_ZONE_BOX),
        "desktop_zone_box": list(DESKTOP_ZONE_BOX),
        "text_bboxes": finish_meta["text_bboxes"],
        "sha256": _sha256_file(out_path),
        "bytes": out_path.stat().st_size,
    }


def build_banner_jh2a_hologram_wave_stream(out_path: Path) -> dict[str, Any]:
    """JH2-A: JH-2 Crimson Darkroom + Centered Blue Brain Hologram + Wide Neural/EEG Wave Stream."""
    crimson_f = _make_jh2_660nm_crimson_backdrop(
        JH5_SOURCE_ASSETS["e02_mri_empty_01"],
        y_frac=0.46,
        bg_blur=5.0,
        seed=9601,
    )
    energy = np.zeros((BANNER_H, BANNER_W), dtype=np.float32)

    # Wide horizontal neural-fiber ribbons + oscillating multi-channel EEG waves across x=140..2420
    wave_mask = Image.new("L", (BANNER_W, BANNER_H), 0)
    wdraw = ImageDraw.Draw(wave_mask)
    cx, cy = BANNER_W // 2, BANNER_H // 2
    for ch_idx, y_off in enumerate((-138, -82, -26, 26, 82, 138)):
        amp = 22.0 - abs(ch_idx - 2.5) * 3.0
        freq1 = 0.011 + 0.002 * ch_idx
        freq2 = 0.029 + 0.003 * (ch_idx % 3)
        pts: list[tuple[float, float]] = []
        for xk in range(140, 2421, 6):
            dist_c = abs(xk - cx)
            amp_env = 0.35 + 0.65 * math.sin(min(math.pi, dist_c / 920.0 * math.pi * 0.5))
            yk = cy + y_off * (0.84 + 0.16 * math.cos(dist_c * 0.0024)) + amp * amp_env * (
                math.sin(xk * freq1 + ch_idx * 1.1) * 0.68 + math.cos(xk * freq2 - ch_idx * 0.7) * 0.32
            )
            pts.append((float(xk), yk))
        wdraw.line(pts, fill=145 if ch_idx in (1, 2, 3, 4) else 98, width=2 if ch_idx in (2, 3) else 1)

    wave_arr = np.array(wave_mask, dtype=np.float32) / 255.0
    xx_1d = np.arange(BANNER_W, dtype=np.float32)[None, :]
    x_fade = np.clip(1.0 - np.maximum(0.0, np.abs(xx_1d - cx) - 820.0) / 360.0, 0.0, 1.0)
    energy = np.maximum(energy, wave_arr * x_fade * 0.86)

    energy = _stamp_horizontal_beam_rails(
        energy,
        x0=160,
        x1=2400,
        y_top=552,
        y_bot=888,
        tick_xs=[cx - 880, cx - 540, cx - 260, cx + 260, cx + 540, cx + 880],
        beam_strength=0.14,
    )
    energy = _stamp_wing_kinetic_vfx(
        energy,
        x_near_abs=210,
        x_far_abs=1160,
        seed=9601,
        n_streaks=26,
        n_arcs=8,
        n_sparks=64,
    )

    brain_stamp = _extract_subject_hologram_energy(
        JH5_SOURCE_ASSETS["a02_lateral_brain_02"],
        target_h=384,
        boost=1.18,
    )
    bh, bw = brain_stamp.shape
    _stamp_float_energy(energy, brain_stamp, cx - bw // 2, cy - bh // 2, 1.0)

    return _finalize_jh2_hologram_banner(
        crimson_f,
        energy,
        out_path,
        variant="jh2a_hologram_wave_stream",
        source_keys=["e02_mri_empty_01", "a02_lateral_brain_02"],
        seed=9601,
        signature_text="neural wave hologram",
        left_notes=[
            ("660nm safelight  ·  eeg field", -5.0),
            ("40 Hz  gamma oscillation", 3.1),
            ("cortex  ->  wave stream", -2.4),
        ],
        right_notes=[
            ("lateral connectome  A02", 4.3),
            ("wide holographic beam", -3.0),
            ("all about brain", 2.1),
        ],
    )


def build_banner_jh2b_hologram_multi_angle_beam(out_path: Path) -> dict[str, Any]:
    """JH2-B: JH-2 Crimson Darkroom + Wide 4-View Blue Hologram Projection Beam (A01 -> A02 -> A03 -> A07)."""
    crimson_f = _make_jh2_660nm_crimson_backdrop(
        JH5_SOURCE_ASSETS["e02_mri_empty_01"],
        y_frac=0.46,
        bg_blur=5.4,
        seed=9602,
    )
    energy = np.zeros((BANNER_H, BANNER_W), dtype=np.float32)

    view_specs = (
        ("a01_mode1_head_01", True, False, 675, 0.90),
        ("a02_lateral_brain_02", False, False, 1075, 0.96),
        ("a03_dorsal_brain_01", False, False, 1485, 0.96),
        ("a07_midsagittal_01", False, True, 1885, 0.92),
    )
    cy = BANNER_H // 2
    energy = _stamp_horizontal_beam_rails(
        energy,
        x0=180,
        x1=2380,
        y_top=546,
        y_bot=894,
        tick_xs=[460, 675, 875, 1075, 1280, 1485, 1685, 1885, 2100],
        beam_strength=0.16,
    )
    energy = _stamp_wing_kinetic_vfx(
        energy,
        x_near_abs=620,
        x_far_abs=1170,
        seed=9602,
        n_streaks=24,
        n_arcs=6,
        n_sparks=52,
    )

    for key, faceless, mirror_x, x_c, wt in view_specs:
        stamp = _extract_subject_hologram_energy(
            JH5_SOURCE_ASSETS[key],
            target_h=324,
            faceless_glass=faceless,
            mirror_x=mirror_x,
            boost=1.15,
        )
        sh, sw = stamp.shape
        _stamp_float_energy(energy, stamp, int(x_c) - sw // 2, cy - sh // 2, wt)

    return _finalize_jh2_hologram_banner(
        crimson_f,
        energy,
        out_path,
        variant="jh2b_hologram_multi_angle_beam",
        source_keys=[
            "e02_mri_empty_01",
            "a01_mode1_head_01",
            "a02_lateral_brain_02",
            "a03_dorsal_brain_01",
            "a07_midsagittal_01",
        ],
        seed=9602,
        signature_text="4-view projection beam",
        left_notes=[
            ("beam array  ·  A01 -> A07", -4.8),
            ("cranial / lateral / dorsal", 3.2),
            ("midsagittal brainstem", -2.3),
        ],
        right_notes=[
            ("projection optics  3.0T", 4.1),
            ("pure #27D8FF hologram", -3.2),
            ("specimen archive · 35mm", 2.0),
        ],
    )


def build_banner_jh2c_hologram_mri_strip(out_path: Path) -> dict[str, Any]:
    """JH2-C: JH-2 Crimson Darkroom + Wide 7-Slice MNI152 Blue Hologram Cross-Section Filmstrip."""
    crimson_f = _make_jh2_660nm_crimson_backdrop(
        JH5_SOURCE_ASSETS["e02_mri_empty_01"],
        y_frac=0.46,
        bg_blur=5.2,
        seed=9603,
    )
    slices = _build_mni152_9_coronal_slices()
    picked_idxs = (0, 1, 3, 4, 5, 7, 8)
    x_centers = (590, 820, 1050, 1280, 1510, 1740, 1970)
    cy = BANNER_H // 2

    energy = np.zeros((BANNER_H, BANNER_W), dtype=np.float32)
    energy = _stamp_horizontal_beam_rails(
        energy,
        x0=180,
        x1=2380,
        y_top=548,
        y_bot=892,
        tick_xs=list(x_centers),
        beam_strength=0.14,
    )
    energy = _stamp_wing_kinetic_vfx(
        energy,
        x_near_abs=640,
        x_far_abs=1170,
        seed=9603,
        n_streaks=24,
        n_arcs=6,
        n_sparks=50,
    )

    for s_idx, xc in zip(picked_idxs, x_centers):
        sl_rgba = slices[s_idx]["rgba"]
        # Pure translucent wireframe + internal subcortical nuclei hologram linework (0 solid opaque panes)
        sl_energy = _build_cyan_mri_hologram_energy(sl_rgba)
        sh, sw = sl_energy.shape
        target_h = 318
        nw = max(16, int(round(sw * (target_h / float(sh)))))
        sl_resized = cv2.resize(sl_energy, (nw, target_h), interpolation=cv2.INTER_AREA)
        dist_center = abs(xc - BANNER_W // 2) / 720.0
        wt = max(0.72, 1.0 - 0.24 * dist_center)
        _stamp_float_energy(energy, np.clip(sl_resized * 1.18, 0.0, 1.0), xc - nw // 2, cy - target_h // 2, wt)

    return _finalize_jh2_hologram_banner(
        crimson_f,
        energy,
        out_path,
        variant="jh2c_hologram_mri_strip",
        source_keys=["e02_mri_empty_01", "neuro_atlas_mni152"],
        seed=9603,
        signature_text="MNI152 holographic MRI",
        left_notes=[
            ("7-plane coronal strip", -4.7),
            ("frontal -> occipital MNI", 3.3),
            ("hippocampus / thalamus", -2.5),
        ],
        right_notes=[
            ("zero opaque fill panes", 4.4),
            ("subcortical nuclei glow", -3.1),
            ("all about brain", 2.1),
        ],
    )


def build_banner_jh2d_hologram_echo_panorama(out_path: Path) -> dict[str, Any]:
    """JH2-D: JH-2 Crimson Darkroom + Pure Blue Hologram A02 Brain + Symmetrical Bullet-Time Echo Panorama."""
    crimson_f = _make_jh2_660nm_crimson_backdrop(
        JH5_SOURCE_ASSETS["e02_mri_empty_01"],
        y_frac=0.46,
        bg_blur=5.0,
        seed=9604,
    )
    energy = np.zeros((BANNER_H, BANNER_W), dtype=np.float32)
    cx, cy = BANNER_W // 2, BANNER_H // 2

    energy = _stamp_horizontal_beam_rails(
        energy,
        x0=180,
        x1=2380,
        y_top=548,
        y_bot=892,
        tick_xs=[cx - 890, cx - 720, cx - 545, cx - 365, cx - 185, cx + 185, cx + 365, cx + 545, cx + 720, cx + 890],
        beam_strength=0.13,
    )
    energy = _stamp_wing_kinetic_vfx(
        energy,
        x_near_abs=320,
        x_far_abs=1175,
        seed=9604,
        n_streaks=28,
        n_arcs=6,
        n_sparks=58,
    )

    # 5 symmetrical pairs of wide horizontal hologram echoes fanning left & right across Desktop/Mobile
    echo_pairs = (
        (185, 360, 0.72),
        (365, 336, 0.58),
        (545, 312, 0.46),
        (720, 290, 0.34),
        (890, 268, 0.24),
    )
    base_l = _extract_subject_hologram_energy(
        JH5_SOURCE_ASSETS["a02_lateral_brain_02"],
        target_h=388,
        mirror_x=False,
        boost=1.18,
    )
    base_r = np.ascontiguousarray(base_l[:, ::-1])
    for dx, eh, wt in echo_pairs:
        sc = eh / float(base_l.shape[0])
        ew = max(16, int(round(base_l.shape[1] * sc)))
        el = cv2.resize(base_l, (ew, eh), interpolation=cv2.INTER_AREA)
        er = cv2.resize(base_r, (ew, eh), interpolation=cv2.INTER_AREA)
        _stamp_float_energy(energy, el, (cx - dx) - ew // 2, cy - eh // 2, wt)
        _stamp_float_energy(energy, er, (cx + dx) - ew // 2, cy - eh // 2, wt)

    # Dead-center luminous primary hologram core
    _stamp_float_energy(energy, base_l, cx - base_l.shape[1] // 2, cy - base_l.shape[0] // 2, 1.0)

    return _finalize_jh2_hologram_banner(
        crimson_f,
        energy,
        out_path,
        variant="jh2d_hologram_echo_panorama",
        source_keys=["e02_mri_empty_01", "a02_lateral_brain_02"],
        seed=9604,
        signature_text="bullet-time echo field",
        left_notes=[
            ("660nm darkroom vault", -4.9),
            ("10 symmetrical echoes", 3.2),
            ("harmonic phase delay", -2.4),
        ],
        right_notes=[
            ("pure #27D8FF resonance", 4.3),
            ("zero pink-mud overlap", -3.0),
            ("specimen archive · 35mm", 2.0),
        ],
    )


def build_banner_jh2e_hologram_cortical_horizon(out_path: Path) -> dict[str, Any]:
    """JH2-E: JH-2 Crimson Midnight Lab + Edge-to-Edge Panoramic Blue Holographic Cortical & Synaptic Horizon."""
    crimson_f = _make_jh2_660nm_crimson_backdrop(
        JH5_SOURCE_ASSETS["e01_lab_empty_01"],
        y_frac=0.50,
        bg_blur=3.8,
        seed=9605,
        extra_lights=[
            (1280.0, 720.0, 760.0, 220.0, (192, 32, 38), 0.16),
        ],
    )
    energy = np.zeros((BANNER_H, BANNER_W), dtype=np.float32)
    cx, cy = BANNER_W // 2, BANNER_H // 2

    # Continuous edge-to-edge full-width (x=0..2560) delicate holographic cortical + white-matter wireframe horizon
    left_outer = _extract_panoramic_texture_hologram_energy(
        JH5_SOURCE_ASSETS["a13_tract_canyon_01"], target_w=1080, target_h=440, mirror_x=False
    )
    left_inner = _extract_panoramic_texture_hologram_energy(
        JH5_SOURCE_ASSETS["a05_sulcal_vessel_01"], target_w=920, target_h=420, mirror_x=True
    )
    right_inner = _extract_panoramic_texture_hologram_energy(
        JH5_SOURCE_ASSETS["a05_sulcal_vessel_01"], target_w=920, target_h=420, mirror_x=False
    )
    right_outer = _extract_panoramic_texture_hologram_energy(
        JH5_SOURCE_ASSETS["a13_tract_canyon_01"], target_w=1080, target_h=440, mirror_x=True
    )

    _stamp_float_energy(energy, left_outer, -60, cy - left_outer.shape[0] // 2, 0.56)
    _stamp_float_energy(energy, left_inner, 360, cy - left_inner.shape[0] // 2, 0.48)
    _stamp_float_energy(energy, right_inner, BANNER_W - 360 - right_inner.shape[1], cy - right_inner.shape[0] // 2, 0.48)
    _stamp_float_energy(energy, right_outer, BANNER_W + 60 - right_outer.shape[1], cy - right_outer.shape[0] // 2, 0.56)

    # Flowing panoramic synaptic connectome filaments weaving edge-to-edge into centered core
    fib_mask = Image.new("L", (BANNER_W, BANNER_H), 0)
    fdraw = ImageDraw.Draw(fib_mask)
    rng_f = np.random.default_rng(9655)
    for f_i in range(14):
        phase = float(rng_f.uniform(0.0, 6.28))
        y_edge = float(cy + (f_i - 6.5) * 20.0)
        y_core = float(cy + (f_i - 6.5) * 9.5)
        pts: list[tuple[float, float]] = []
        for xk in range(0, BANNER_W + 1, 8):
            u = abs(xk - cx) / float(cx)
            yk = y_core * (1.0 - u) + y_edge * u + 16.0 * math.sin(xk * 0.008 + phase) * (0.3 + 0.7 * u)
            pts.append((float(xk), yk))
        fdraw.line(pts, fill=140 if f_i % 3 == 0 else 92, width=2 if f_i % 4 == 0 else 1)
    energy = np.maximum(energy, (np.array(fib_mask, dtype=np.float32) / 255.0) * 0.85)

    energy = _stamp_horizontal_beam_rails(
        energy,
        x0=0,
        x1=BANNER_W,
        y_top=534,
        y_bot=906,
        tick_xs=[240, 507, 820, 1280, 1740, 2053, 2320],
        beam_strength=0.14,
    )
    energy = _stamp_wing_kinetic_vfx(
        energy,
        x_near_abs=240,
        x_far_abs=1240,
        seed=9605,
        n_streaks=28,
        n_arcs=8,
        n_sparks=60,
    )

    core_brain = _extract_subject_hologram_energy(
        JH5_SOURCE_ASSETS["a02_lateral_brain_02"],
        target_h=380,
        boost=1.22,
    )
    _stamp_float_energy(energy, core_brain, cx - core_brain.shape[1] // 2, cy - core_brain.shape[0] // 2, 1.0)

    return _finalize_jh2_hologram_banner(
        crimson_f,
        energy,
        out_path,
        variant="jh2e_hologram_cortical_horizon",
        source_keys=[
            "e01_lab_empty_01",
            "a13_1p_white_matter_tract_canyon",
            "a05_sulcal_vessel_macro",
            "a02_lateral_brain_02",
        ],
        seed=9605,
        signature_text="cortical hologram horizon",
        left_notes=[
            ("white-matter axonal canyon", -4.8),
            ("edge-to-edge  2560px field", 3.0),
            ("midnight lab  660nm", -2.3),
        ],
        right_notes=[
            ("sulcal vessel arborization", 4.2),
            ("full panorama  scanlines", -3.1),
            ("all about brain", 2.0),
        ],
    )


def build_jh2_5opts_comparison_sheet(
    out_path: Path,
    *,
    jh2_paths: list[tuple[str, str, str, tuple[int, int, int], Path]],
    ted_red_logo_path: Path,
) -> dict[str, Any]:
    """Compare JH2-A..JH2-E (Crimson Darkroom + Wide Blue Brain Hologram 5 Options) w/ TED Red Avatar."""
    return build_jh5_collection_comparison_sheet(
        out_path,
        jh_paths=jh2_paths,
        ted_red_logo_path=ted_red_logo_path,
        header_title="JH-2 CRIMSON DARKROOM × WIDE BLUE BRAIN HOLOGRAMS  —  5 OPTIONS (JH2-A TO JH2-E)",
        header_sub="660NM CRIMSON DARKROOM + LUMINOUS #27D8FF WIDE HORIZONTAL HOLOGRAMS  ·  0 PINK MUD  ·  TED RED AVATAR PAIRING",
        header_accent_rgb=TED_RED_CENTER_RGB,
    )


def _verify_jh2_5opts_banner_entry(
    output_dir: Path,
    fname: str,
    banner_meta: dict[str, Any],
    issues: list[str],
    label: str,
) -> dict[str, Any]:
    """
    Verify JH2-A..JH2-E Crimson Darkroom + Wide Blue Brain Hologram contract:
      1. 3-tier Johnny Harris lockup strictly inside SAFE_ZONE_BOX (507, 508, 2053, 931).
      2. Zero banned cartoon faces / H01 box sticker tokens.
      3. Strong anti-mud luminous #27D8FF blue hologram across Left, Center-Undimmed, and Right horizontal spans.
      4. Authentic 660nm crimson darkroom background luminance + 35mm film grain + crisp white title contrast.
    """
    bboxes = banner_meta.get("text_bboxes", {})
    union_bb = bboxes.get("combined_ink_union", [])
    safe_bounds_ok = False
    if len(union_bb) == 4:
        ux0, uy0, ux1, uy1 = [int(v) for v in union_bb]
        safe_bounds_ok = (
            ux0 >= SAFE_ZONE_BOX[0] + 20
            and uy0 >= SAFE_ZONE_BOX[1] + 20
            and ux1 <= SAFE_ZONE_BOX[2] - 20
            and uy1 <= SAFE_ZONE_BOX[3] - 20
            and set(bboxes.keys()) >= {"eyebrow", "title", "signature", "combined_ink_union"}
        )
    if not safe_bounds_ok:
        issues.append(f"{label} safe-zone lockup check failed: keys={list(bboxes.keys())}, union={union_bb}")

    src_keys = [str(k) for k in (banner_meta.get("source_keys") or [])]
    banned_hits = [
        k for k in src_keys
        if any(tok.lower() in k.lower() for tok in BANNED_JH5_TOKENS) or ("h01" in k.lower())
    ]
    zero_cartoon_faces_ok = len(src_keys) >= 2 and len(banned_hits) == 0
    if not zero_cartoon_faces_ok:
        issues.append(f"{label} source check failed: src_keys={src_keys}, banned_hits={banned_hits}")

    wide_blue_hologram_ok = False
    crimson_darkroom_and_grain_ok = False
    fpath = output_dir / fname
    if fpath.is_file():
        rgb = np.array(Image.open(fpath).convert("RGB"), dtype=np.float32)
        luma = 0.299 * rgb[:, :, 0] + 0.587 * rgb[:, :, 1] + 0.114 * rgb[:, :, 2]

        def _count_cyan_holo(y0: int, y1: int, x0: int, x1: int) -> int:
            roi = rgb[y0:y1, x0:x1]
            mask = (roi[:, :, 2] >= 125.0) & (roi[:, :, 1] >= 95.0) & ((roi[:, :, 2] - roi[:, :, 0]) >= 40.0)
            return int(mask.sum())

        left_holo_px = _count_cyan_holo(520, 920, 180, 980)
        center_top_px = _count_cyan_holo(520, 622, 980, 1580)
        center_bot_px = _count_cyan_holo(780, 920, 980, 1580)
        right_holo_px = _count_cyan_holo(520, 920, 1580, 2380)
        wide_blue_hologram_ok = (
            left_holo_px >= 2500
            and (center_top_px + center_bot_px) >= 1500
            and right_holo_px >= 2500
        )
        if not wide_blue_hologram_ok:
            issues.append(
                f"{label} wide blue hologram check failed: left={left_holo_px}, "
                f"center={center_top_px + center_bot_px}, right={right_holo_px}"
            )

        darkroom_top = rgb[140:340, 200:2360]
        dr_mean = darkroom_top.mean(axis=(0, 1))
        corner_luma = luma[12:92, 12:92]
        corner_std = float(corner_luma.std())
        title_box = bboxes.get("title", [809, 664, 1751, 733])
        tx0, ty0, tx1, ty1 = [max(0, int(v)) for v in title_box]
        title_peak = float(np.percentile(luma[ty0:ty1, tx0:tx1], 99.0)) if (tx1 > tx0 and ty1 > ty0) else 0.0
        crimson_darkroom_and_grain_ok = (
            float(dr_mean[0]) > float(dr_mean[1]) * 2.0
            and float(dr_mean[0]) > float(dr_mean[2]) * 1.7
            and 22.0 <= float(dr_mean[0]) <= 145.0
            and corner_std >= 2.2
            and title_peak >= 215.0
        )
        if not crimson_darkroom_and_grain_ok:
            issues.append(
                f"{label} crimson darkroom/grain check failed: dr_mean={dr_mean.tolist()}, "
                f"corner_std={corner_std:.2f}, title_peak={title_peak:.2f}"
            )

    return {
        "safe_zone_box": list(SAFE_ZONE_BOX),
        "combined_ink_union": union_bb,
        "source_keys": src_keys,
        "safe_bounds_ok": safe_bounds_ok,
        "zero_cartoon_faces_ok": zero_cartoon_faces_ok,
        "wide_blue_hologram_ok": wide_blue_hologram_ok,
        "crimson_darkroom_and_grain_ok": crimson_darkroom_and_grain_ok,
    }


def _make_ricks_clips_vivid_red_backdrop() -> Image.Image:
    """
    Create ultra-clean 2560x1440 vivid TED/RicksClips Red (#E62B1E -> #DA261A) backdrop
    with zero darkroom mud, zero wing clutter, and seamless pairing with Ep #31 TED Red avatar.
    """
    return _make_radial_gradient_backdrop(
        BANNER_W,
        BANNER_H,
        center_rgb=TED_RED_CENTER_RGB,
        edge_rgb=(218, 38, 26),
        power=1.5,
    )


def _render_ricks_clips_3d_line_rgba(
    text: str,
    *,
    font_size: int,
    tracking_px: int = -3,
    space_ratio: float = 0.25,
    y_stretch: float = 1.12,
    outline_px: int = 13,
    extrude_dx: int = 11,
    extrude_dy: int = 14,
) -> Image.Image:
    """
    Render crisp `#FFFFFF` chunky weight-900 uppercase display lettering with thick `#1A0707`
    outline + solid stepped 3D block extrusion + subtle warm drop shadow (`2x` supersampled).
    """
    ss = 2
    font = _load_font(PRIMARY_BODY_FONT, font_size * ss, weight=900)
    probe = ImageDraw.Draw(Image.new("RGBA", (32, 32), (0, 0, 0, 0)))

    glyphs: list[tuple[str, float]] = []
    total_adv = 0.0
    space_adv = float(font_size * ss * space_ratio)
    for idx_ch, ch in enumerate(text):
        if ch == " ":
            total_adv += space_adv
            continue
        adv = float(probe.textlength(ch, font=font))
        glyphs.append((ch, total_adv))
        next_is_char = idx_ch + 1 < len(text) and text[idx_ch + 1] != " "
        total_adv += adv + (tracking_px * ss if next_is_char else 0.0)

    max_ext = max(abs(extrude_dx), abs(extrude_dy), 12) * ss
    pad_x = 90 * ss + outline_px * ss + max_ext
    pad_y = 90 * ss + outline_px * ss + max_ext
    tmp_w = max(256, int(math.ceil(total_adv)) + 2 * pad_x)
    tmp_h = max(256, int(math.ceil(font_size * ss * 1.45)) + 2 * pad_y)

    # Pass A: Soft downward-right dark-crimson drop shadow
    shadow_mask = Image.new("L", (tmp_w, tmp_h), 0)
    sh_draw = ImageDraw.Draw(shadow_mask)
    sh_dx = (extrude_dx + 7) * ss
    sh_dy = (extrude_dy + 8) * ss
    for ch, gx in glyphs:
        sh_draw.text(
            (pad_x + gx + sh_dx, pad_y + sh_dy),
            ch,
            font=font,
            fill=255,
            stroke_width=outline_px * ss,
            stroke_fill=255,
        )
    shadow_mask = shadow_mask.filter(ImageFilter.GaussianBlur(radius=6.0 * ss))
    shadow_mask = shadow_mask.point(lambda a: int(round(a * 0.34)))
    shadow_layer = Image.new("RGBA", (tmp_w, tmp_h), (64, 4, 4, 255))
    shadow_layer.putalpha(shadow_mask)

    # Pass B: Continuous stepped 3D block extrusion + unified #1A0707 perimeter stroke
    layer = shadow_layer
    block_layer = Image.new("RGBA", (tmp_w, tmp_h), (0, 0, 0, 0))
    bdraw = ImageDraw.Draw(block_layer)
    steps = max(abs(extrude_dx) * ss, abs(extrude_dy) * ss, 1)
    for st in range(steps, -1, -1):
        frac = st / float(steps)
        ox = int(round(extrude_dx * ss * frac))
        oy = int(round(extrude_dy * ss * frac))
        if st > 0:
            col = (
                int(round(26 + 14 * (1.0 - frac))),
                int(round(7 + 3 * (1.0 - frac))),
                int(round(7 + 3 * (1.0 - frac))),
                255,
            )
        else:
            col = (26, 7, 7, 255)
        for ch, gx in glyphs:
            bdraw.text(
                (pad_x + gx + ox, pad_y + oy),
                ch,
                font=font,
                fill=col,
                stroke_width=outline_px * ss,
                stroke_fill=col,
            )

    # Pass C: Razor-crisp pure #FFFFFF faces across all glyphs on top (never clipped by adjacent stroke)
    for ch, gx in glyphs:
        bdraw.text(
            (pad_x + gx, pad_y),
            ch,
            font=font,
            fill=(255, 255, 255, 255),
            stroke_width=0,
        )

    composed = Image.alpha_composite(layer, block_layer)
    out_w = max(1, int(round(composed.width / float(ss))))
    out_h = max(1, int(round((composed.height / float(ss)) * float(y_stretch))))
    down = composed.resize((out_w, out_h), resample=Image.Resampling.LANCZOS)
    bb = down.getbbox()
    return down.crop(bb) if bb else down


def _scale_rgba_to_width(img: Image.Image, target_w: int) -> Image.Image:
    if img.width <= 0 or img.height <= 0 or img.width == target_w:
        return img
    target_h = max(1, int(round(img.height * (float(target_w) / float(img.width)))))
    return img.resize((target_w, target_h), resample=Image.Resampling.LANCZOS)


def _fit_rgba_within_box(img: Image.Image, max_w: int, max_h: int) -> Image.Image:
    if img.width <= 0 or img.height <= 0:
        return img
    scale = min(float(max_w) / float(img.width), float(max_h) / float(img.height))
    out_w = max(1, int(round(img.width * scale)))
    out_h = max(1, int(round(img.height * scale)))
    if out_w == img.width and out_h == img.height:
        return img
    return img.resize((out_w, out_h), resample=Image.Resampling.LANCZOS)


def _compute_non_bg_union_bbox(banner_rgb: Image.Image, bg_rgb: Image.Image) -> list[int]:
    arr = np.array(banner_rgb, dtype=np.float32)
    ref = np.array(bg_rgb, dtype=np.float32)
    diff = np.max(np.abs(arr - ref), axis=2)
    ys, xs = np.where(diff > 14.0)
    if len(xs) == 0 or len(ys) == 0:
        return [0, 0, 0, 0]
    return [int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1]


def build_banner_rc1_pure_type(out_path: Path) -> dict[str, Any]:
    """RC-1: Pure vivid #E62B1E Ricks Clips 1:1 single-line 3D `ALL ABOUT BRAIN` wordmark."""
    bg = _make_ricks_clips_vivid_red_backdrop()
    canvas = bg.convert("RGBA")

    line = _render_ricks_clips_3d_line_rgba(
        "ALL ABOUT BRAIN",
        font_size=148,
        tracking_px=-3,
        space_ratio=0.28,
        y_stretch=1.18,
        outline_px=13,
        extrude_dx=11,
        extrude_dy=14,
    )
    line = _fit_rgba_within_box(line, 1300, 230)
    lx = (BANNER_W - line.width) // 2
    ly = (BANNER_H - line.height) // 2 + 2
    fg = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    fg.paste(line, (lx, ly))
    final_rgb = Image.alpha_composite(canvas, fg).convert("RGB")

    ink_bb = _compute_non_bg_union_bbox(final_rgb, bg)
    _atomic_save_image(final_rgb, out_path, format="PNG", optimize=True)
    return {
        "file": out_path.name,
        "variant": "rc1_pure_type",
        "width": BANNER_W,
        "height": BANNER_H,
        "safe_zone_box": list(SAFE_ZONE_BOX),
        "desktop_zone_box": list(DESKTOP_ZONE_BOX),
        "text_bboxes": {
            "line_1": [lx, ly, lx + line.width, ly + line.height],
            "combined_ink_union": ink_bb,
        },
        "sha256": _sha256_file(out_path),
        "bytes": out_path.stat().st_size,
    }


def build_banner_rc2_type_plus_brain(out_path: Path) -> dict[str, Any]:
    """RC-2: Pure vivid #E62B1E + fringe-free Ep #31 cyan brain (left) + stacked 3D `ALL ABOUT / BRAIN` (right)."""
    bg = _make_ricks_clips_vivid_red_backdrop()
    canvas = bg.convert("RGBA")

    # Left: Fringe-free Ep #31 alabaster-gypsum & #27D8FF cyan brain with bold 3D drop silhouette matching type
    brain_raw = _extract_fringe_free_cyan_brain_rgba(SOURCE_ASSETS["a02_lateral_cand02"])
    brain_im = _fit_rgba_within_box(Image.fromarray(brain_raw, mode="RGBA"), 336, 300)
    bx = 592
    by = (BANNER_H - brain_im.height) // 2

    # Stepped solid 3D extrusion silhouette down-right only (keeps top-left rim 100% fringe-free)
    b_alpha = brain_im.split()[3]
    ext_canvas = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    for st in range(12, 0, -1):
        ox = int(round(8 * (st / 12.0)))
        oy = int(round(11 * (st / 12.0)))
        silhouette = Image.new("RGBA", brain_im.size, (26, 7, 7, 255))
        silhouette.putalpha(b_alpha)
        step_layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        step_layer.paste(silhouette, (bx + ox, by + oy))
        ext_canvas = Image.alpha_composite(ext_canvas, step_layer)
    soft_sh_alpha = Image.new("L", canvas.size, 0)
    soft_sh_alpha.paste(b_alpha.point(lambda a: int(round(a * 0.34))), (bx + 14, by + 17))
    soft_sh_alpha = soft_sh_alpha.filter(ImageFilter.GaussianBlur(radius=6.0))
    soft_sh = Image.new("RGBA", canvas.size, (64, 4, 4, 255))
    soft_sh.putalpha(soft_sh_alpha)
    canvas = Image.alpha_composite(canvas, soft_sh)
    canvas = Image.alpha_composite(canvas, ext_canvas)

    brain_fg = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    brain_fg.paste(brain_im, (bx, by))
    canvas = Image.alpha_composite(canvas, brain_fg)

    # Right: Stacked 3D `ALL ABOUT` above extra-huge `BRAIN` strictly inside [970..1970, 535..905]
    top_line = _render_ricks_clips_3d_line_rgba(
        "ALL ABOUT",
        font_size=82,
        tracking_px=-2,
        space_ratio=0.28,
        y_stretch=1.08,
        outline_px=9,
        extrude_dx=7,
        extrude_dy=9,
    )
    top_line = _fit_rgba_within_box(top_line, 660, 102)
    bot_line = _render_ricks_clips_3d_line_rgba(
        "BRAIN",
        font_size=168,
        tracking_px=-2,
        y_stretch=1.02,
        outline_px=13,
        extrude_dx=11,
        extrude_dy=13,
    )
    bot_line = _fit_rgba_within_box(bot_line, 920, 232)

    gap_y = 12
    stack_h = top_line.height + gap_y + bot_line.height
    right_cx = 1475
    top_y = (BANNER_H - stack_h) // 2 + 2
    bot_y = top_y + top_line.height + gap_y
    top_x = right_cx - top_line.width // 2
    bot_x = right_cx - bot_line.width // 2

    txt_fg = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    txt_fg.paste(top_line, (top_x, top_y))
    txt_fg.paste(bot_line, (bot_x, bot_y), mask=bot_line.split()[3])
    final_rgb = Image.alpha_composite(canvas, txt_fg).convert("RGB")

    ink_bb = _compute_non_bg_union_bbox(final_rgb, bg)
    _atomic_save_image(final_rgb, out_path, format="PNG", optimize=True)
    return {
        "file": out_path.name,
        "variant": "rc2_type_plus_brain",
        "width": BANNER_W,
        "height": BANNER_H,
        "source_keys": ["a02_lateral_cand02"],
        "safe_zone_box": list(SAFE_ZONE_BOX),
        "desktop_zone_box": list(DESKTOP_ZONE_BOX),
        "text_bboxes": {
            "brain": [bx, by, bx + brain_im.width, by + brain_im.height],
            "top_line": [top_x, top_y, top_x + top_line.width, top_y + top_line.height],
            "bot_line": [bot_x, bot_y, bot_x + bot_line.width, bot_y + bot_line.height],
            "combined_ink_union": ink_bb,
        },
        "sha256": _sha256_file(out_path),
        "bytes": out_path.stat().st_size,
    }


def build_banner_rc3_stacked_3d_poster(out_path: Path) -> dict[str, Any]:
    """RC-3: Monumental centered 2-line stacked 3D `ALL ABOUT / BRAIN` + `#27D8FF` cyan accent underscore bar."""
    bg = _make_ricks_clips_vivid_red_backdrop()
    canvas = bg.convert("RGBA")

    top_line = _render_ricks_clips_3d_line_rgba(
        "ALL ABOUT",
        font_size=82,
        tracking_px=-2,
        space_ratio=0.28,
        y_stretch=1.04,
        outline_px=9,
        extrude_dx=7,
        extrude_dy=9,
    )
    top_line = _fit_rgba_within_box(top_line, 660, 96)
    bot_line = _render_ricks_clips_3d_line_rgba(
        "BRAIN",
        font_size=168,
        tracking_px=-1,
        y_stretch=1.00,
        outline_px=13,
        extrude_dx=11,
        extrude_dy=13,
    )
    bot_line = _fit_rgba_within_box(bot_line, 940, 218)

    # Crisp 3D-extruded electric #27D8FF cyan accent underscore bar tying to the TED Red avatar brain
    bar_w, bar_h = 500, 14
    pad = 24
    bar_rgba = Image.new("RGBA", (bar_w + pad * 2, bar_h + pad * 2), (0, 0, 0, 0))
    bdraw = ImageDraw.Draw(bar_rgba)
    for st in range(7, -1, -1):
        ox = int(round(5 * (st / 7.0)))
        oy = int(round(7 * (st / 7.0)))
        bdraw.rounded_rectangle(
            (pad - 4 + ox, pad - 4 + oy, pad + bar_w + 4 + ox, pad + bar_h + 4 + oy),
            radius=9,
            fill=(26, 7, 7, 255),
        )
    bdraw.rounded_rectangle(
        (pad, pad, pad + bar_w, pad + bar_h),
        radius=6,
        fill=(39, 216, 255, 255),
    )
    bar_bb = bar_rgba.getbbox()
    bar_crop = bar_rgba.crop(bar_bb) if bar_bb else bar_rgba

    gap1 = 10
    gap2 = 14
    total_h = top_line.height + gap1 + bot_line.height + gap2 + bar_crop.height
    top_y = (BANNER_H - total_h) // 2 + 2
    bot_y = top_y + top_line.height + gap1
    bar_y = bot_y + bot_line.height + gap2
    top_x = (BANNER_W - top_line.width) // 2
    bot_x = (BANNER_W - bot_line.width) // 2
    bar_x = (BANNER_W - bar_crop.width) // 2

    fg = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    fg.paste(top_line, (top_x, top_y))
    fg.paste(bot_line, (bot_x, bot_y), mask=bot_line.split()[3])
    fg.paste(bar_crop, (bar_x, bar_y), mask=bar_crop.split()[3])
    final_rgb = Image.alpha_composite(canvas, fg).convert("RGB")

    ink_bb = _compute_non_bg_union_bbox(final_rgb, bg)
    _atomic_save_image(final_rgb, out_path, format="PNG", optimize=True)
    return {
        "file": out_path.name,
        "variant": "rc3_stacked_3d_poster",
        "width": BANNER_W,
        "height": BANNER_H,
        "safe_zone_box": list(SAFE_ZONE_BOX),
        "desktop_zone_box": list(DESKTOP_ZONE_BOX),
        "text_bboxes": {
            "top_line": [top_x, top_y, top_x + top_line.width, top_y + top_line.height],
            "bot_line": [bot_x, bot_y, bot_x + bot_line.width, bot_y + bot_line.height],
            "cyan_bar": [bar_x, bar_y, bar_x + bar_crop.width, bar_y + bar_crop.height],
            "combined_ink_union": ink_bb,
        },
        "sha256": _sha256_file(out_path),
        "bytes": out_path.stat().st_size,
    }


def build_ricks_clips_3opts_comparison_sheet(
    out_path: Path,
    *,
    rc_paths: list[tuple[str, str, str, tuple[int, int, int], Path]],
    ted_red_logo_path: Path,
) -> dict[str, Any]:
    """Compare RC-1..RC-3 vivid TED Red + chunky 3D-extruded type banners paired with Option 1 TED Red avatar."""
    return build_jh5_collection_comparison_sheet(
        out_path,
        jh_paths=rc_paths,
        ted_red_logo_path=ted_red_logo_path,
        header_title="RICKS CLIPS × ALL ABOUT BRAIN  —  VIVID TED RED 3D BLOCK BANNERS (RC-1 TO RC-3)",
        header_sub="PURE VIVID #E62B1E RED  ·  0% DARKROOM MUD  ·  CHUNKY #FFFFFF + #1A0707 3D EXTRUSION  ·  TED RED AVATAR PAIRING",
        header_accent_rgb=TED_RED_CENTER_RGB,
    )


def _verify_ricks_clips_banner_entry(
    output_dir: Path,
    fname: str,
    banner_meta: dict[str, Any],
    issues: list[str],
    label: str,
    mode: str,
) -> dict[str, Any]:
    """Verify Ricks Clips–style vivid red banner constraints (`safe_bounds`, `pure_vivid_red_wings`, `3D type`, variant feature)."""
    bboxes = banner_meta.get("text_bboxes", {})
    union_bb = bboxes.get("combined_ink_union", [])
    safe_bounds_ok = False
    pure_vivid_red_wings_ok = False
    chunky_3d_pop_type_ok = False
    variant_feature_ok = False

    fpath = output_dir / fname
    if fpath.is_file():
        rgb = np.array(Image.open(fpath).convert("RGB"), dtype=np.float32)
        bg = np.array(_make_ricks_clips_vivid_red_backdrop(), dtype=np.float32)
        diff = np.max(np.abs(rgb - bg), axis=2)
        ys_ink, xs_ink = np.where(diff > 22.0)
        if len(xs_ink) > 0 and len(ys_ink) > 0:
            px_bb = [int(xs_ink.min()), int(ys_ink.min()), int(xs_ink.max()) + 1, int(ys_ink.max()) + 1]
            safe_bounds_ok = (
                px_bb[0] >= SAFE_ZONE_BOX[0]
                and px_bb[1] >= SAFE_ZONE_BOX[1]
                and px_bb[2] <= SAFE_ZONE_BOX[2]
                and px_bb[3] <= SAFE_ZONE_BOX[3]
                and len(union_bb) == 4
                and int(union_bb[0]) >= SAFE_ZONE_BOX[0]
                and int(union_bb[1]) >= SAFE_ZONE_BOX[1]
                and int(union_bb[2]) <= SAFE_ZONE_BOX[2]
                and int(union_bb[3]) <= SAFE_ZONE_BOX[3]
            )
        else:
            px_bb = [0, 0, 0, 0]

        wing_l = rgb[520:920, 40:480]
        wing_r = rgb[520:920, 2080:2520]
        wl_m, wr_m = wing_l.mean(axis=(0, 1)), wing_r.mean(axis=(0, 1))
        wl_s = float(wing_l.std(axis=(0, 1)).max())
        wr_s = float(wing_r.std(axis=(0, 1)).max())
        pure_vivid_red_wings_ok = (
            wl_m[0] >= 210.0
            and 28.0 <= wl_m[1] <= 55.0
            and 18.0 <= wl_m[2] <= 42.0
            and wr_m[0] >= 210.0
            and 28.0 <= wr_m[1] <= 55.0
            and 18.0 <= wr_m[2] <= 42.0
            and wl_s < 5.0
            and wr_s < 5.0
        )

        safe_roi = rgb[SAFE_ZONE_BOX[1] : SAFE_ZONE_BOX[3], SAFE_ZONE_BOX[0] : SAFE_ZONE_BOX[2]]
        white_px = int(((safe_roi[:, :, 0] >= 235.0) & (safe_roi[:, :, 1] >= 235.0) & (safe_roi[:, :, 2] >= 235.0)).sum())
        outline_px = int(((safe_roi[:, :, 0] <= 55.0) & (safe_roi[:, :, 1] <= 25.0) & (safe_roi[:, :, 2] <= 25.0)).sum())
        chunky_3d_pop_type_ok = white_px >= 22_000 and outline_px >= 15_000

        cyan_mask = (safe_roi[:, :, 2] >= 170.0) & (safe_roi[:, :, 1] >= 140.0) & ((safe_roi[:, :, 2] - safe_roi[:, :, 0]) >= 65.0)
        cyan_total = int(cyan_mask.sum())
        if mode == "rc1_pure_type":
            variant_feature_ok = cyan_total == 0 and (px_bb[2] - px_bb[0]) >= 1100
        elif mode == "rc2_type_plus_brain":
            brain_roi = rgb[520:920, 540:955]
            brain_hsv = cv2.cvtColor(brain_roi.astype(np.uint8), cv2.COLOR_RGB2HSV).astype(np.float32)
            brain_luma = 0.299 * brain_roi[:, :, 0] + 0.587 * brain_roi[:, :, 1] + 0.114 * brain_roi[:, :, 2]
            cyan_b = int(((brain_roi[:, :, 2] >= 165.0) & (brain_roi[:, :, 1] >= 135.0) & ((brain_roi[:, :, 2] - brain_roi[:, :, 0]) >= 65.0)).sum())
            gypsum_b = int(((brain_hsv[:, :, 1] <= 45.0) & (brain_luma >= 145.0)).sum())
            # Ensure zero dark-navy fringe along outer upper-left perimeter touching the red backdrop
            red_b = (brain_roi[:, :, 0] > 140.0) & (brain_roi[:, :, 1] < 65.0) & (brain_roi[:, :, 2] < 65.0)
            rim_b = (cv2.dilate(red_b.astype(np.uint8), np.ones((7, 7), np.uint8)) > 0) & (~red_b)
            navy_rim = int(
                (
                    rim_b[:, :210]
                    & (brain_roi[:, :210, 2] > brain_roi[:, :210, 0] + 30.0)
                    & (brain_luma[:, :210] < 95.0)
                ).sum()
            )
            variant_feature_ok = cyan_b >= 2500 and gypsum_b >= 8000 and navy_rim < 120
        else:
            bar_roi = rgb[810:925, 900:1660]
            bar_cyan = int(((bar_roi[:, :, 2] >= 180.0) & (bar_roi[:, :, 1] >= 150.0) & ((bar_roi[:, :, 2] - bar_roi[:, :, 0]) >= 75.0)).sum())
            variant_feature_ok = bar_cyan >= 1800

    for ok_flag, msg in (
        (safe_bounds_ok, f"{label} safe-zone bounds check failed: union={union_bb}"),
        (pure_vivid_red_wings_ok, f"{label} pure vivid red wings check failed"),
        (chunky_3d_pop_type_ok, f"{label} chunky 3D white+outline type check failed"),
        (variant_feature_ok, f"{label} variant feature check failed ({mode})"),
    ):
        if not ok_flag:
            issues.append(msg)

    return {
        "safe_zone_box": list(SAFE_ZONE_BOX),
        "combined_ink_union": union_bb,
        "safe_bounds_ok": safe_bounds_ok,
        "pure_vivid_red_wings_ok": pure_vivid_red_wings_ok,
        "chunky_3d_pop_type_ok": chunky_3d_pop_type_ok,
        "variant_feature_ok": variant_feature_ok,
    }


def build_brand_final_lock_preview_sheet(
    out_path: Path,
    *,
    ted_red_logo_path: Path,
    final_banner_path: Path,
) -> dict[str, Any]:
    """
    Build 2400x2280 RGB final brand lock sign-off board uniting:
      - Locked Avatar: `logo_A_ted_red_bg_cyan_brain.png` (YouTube Dark/Light 240/64/32px + IG/TikTok circles)
      - Locked Banner: `banner_youtube_2560x1440_jh3_human_element_homage.png` (2560x423, 1546x423, TV 16:9, Live Headers, 8-slot copy check)
    """
    board_w, board_h = 2400, 2280
    board = Image.new("RGB", (board_w, board_h), (8, 13, 22))
    draw = ImageDraw.Draw(board)

    f_hdr = _load_font(PRIMARY_DISPLAY_FONT, 46)
    f_hdr_sub = _load_font(PRIMARY_BODY_FONT, 18, weight=600)
    f_sec = _load_font(PRIMARY_DISPLAY_FONT, 28)
    f_sub = _load_font(PRIMARY_BODY_FONT, 15, weight=500)
    f_badge = _load_font(PRIMARY_BODY_FONT, 14, weight=700)
    f_ui_bold = _load_font(PRIMARY_BODY_FONT, 16, weight=700)
    f_ui_sm = _load_font(PRIMARY_BODY_FONT, 13, weight=600)
    f_ui_tiny = _load_font(PRIMARY_BODY_FONT, 12, weight=500)

    coral_accent = (230, 88, 62)
    teal_accent = (107, 171, 178)

    # Header band (0..118)
    draw.rectangle((0, 0, board_w, 118), fill=(11, 18, 30))
    draw.text((48, 24), "ALL ABOUT BRAIN  —  FINAL LOCKED BRAND IDENTITY", fill=(245, 247, 250), font=f_hdr)
    draw.text(
        (48, 78),
        "AVATAR: OPTION 1 TED RED (#E62B1E + EP #31 CYAN BRAIN)  ·  BANNER: JH-3 CINEMA HORIZON (FINAL VIEWER COPY)",
        fill=coral_accent,
        font=f_hdr_sub,
    )
    draw.line((0, 118, board_w, 118), fill=coral_accent, width=2)

    with Image.open(ted_red_logo_path) as lim:
        logo_rgb = lim.convert("RGB")
    with Image.open(final_banner_path) as bim:
        banner_rgb = bim.convert("RGB")

    # ------------------------------------------------------------------
    # PANEL 1: FINAL LOCKED AVATAR (YouTube Dark/Light + IG/TikTok)
    # ------------------------------------------------------------------
    p1_y, p1_h = 140, 570
    draw.rounded_rectangle((40, p1_y, board_w - 40, p1_y + p1_h), radius=16, fill=(12, 18, 28), outline=TED_RED_CENTER_RGB, width=2)
    draw.rounded_rectangle((64, p1_y + 18, 254, p1_y + 46), radius=6, fill=TED_RED_CENTER_RGB)
    draw.text((159, p1_y + 32), "LOCKED AVATAR", fill=(255, 255, 255), font=f_badge, anchor="mm")
    draw.text((272, p1_y + 16), "OPTION 1: TED RED (#E62B1E) + EP #31 GYPSUM & #27D8FF CYAN BRAIN", fill=(245, 247, 250), font=f_sec)
    draw.text((64, p1_y + 52), "Zero navy fringe · crisp 64px / 32px YouTube Shorts recognition · cross-platform IG & TikTok circles", fill=(148, 163, 184), font=f_sub)

    sq_340 = logo_rgb.resize((340, 340), resample=Image.Resampling.LANCZOS)
    sq_x, sq_y = 64, p1_y + 92
    draw.rectangle((sq_x - 1, sq_y - 1, sq_x + 340, sq_y + 340), outline=(56, 72, 98), width=1)
    board.paste(sq_340, (sq_x, sq_y))
    draw.text((sq_x + 170, sq_y + 356), "800×800 SQUARE MASTER", fill=(148, 163, 184), font=f_ui_tiny, anchor="mm")

    av_240 = _make_circular_avatar(logo_rgb, 240)
    av_x, av_y = 446, p1_y + 142
    board.paste(av_240, (av_x, av_y), mask=av_240.split()[3])
    draw.text((av_x + 120, sq_y + 356), "240px CIRCLE AVATAR", fill=(148, 163, 184), font=f_ui_tiny, anchor="mm")

    _paste_youtube_ui_mock_strips(
        board,
        draw,
        logo_rgb=logo_rgb,
        strip_x=760,
        start_y=sq_y,
        strip_w=860,
        strip_h=178,
        strip_gap=18,
        div_offset_x=445,
        x32_btn_offset=230,
        f_ui_bold=f_ui_bold,
        f_ui_sm=f_ui_sm,
        f_ui_tiny=f_ui_tiny,
    )

    # Cross-platform IG & TikTok Circular Profile Cards (1656..2336)
    soc_x, soc_w, soc_h = 1656, 680, 178
    av_108 = _make_circular_avatar(logo_rgb, 108)
    for idx_s, (bg_s, border_s, plat_lbl, handle, bio_txt, btn_col, btn_txt_col, ring_col) in enumerate(
        [
            ((0, 0, 0), (54, 54, 54), "INSTAGRAM PROFILE CIRCLE", "@allaboutbrain", "Peer-Reviewed Neuroscience · Shorts", (0, 149, 246), (255, 255, 255), (225, 48, 108)),
            ((18, 18, 18), (58, 58, 58), "TIKTOK PROFILE CIRCLE", "@allaboutbrain", "Real Experiments · Real Brain Data", (254, 44, 85), (255, 255, 255), (37, 244, 238)),
        ]
    ):
        sy_s = sq_y + idx_s * (soc_h + 18)
        draw.rounded_rectangle((soc_x, sy_s, soc_x + soc_w, sy_s + soc_h), radius=10, fill=bg_s, outline=border_s, width=1)
        draw.text((soc_x + 18, sy_s + 12), plat_lbl, fill=(148, 163, 184), font=f_ui_tiny)
        cx_av, cy_av = soc_x + 30, sy_s + 44
        draw.ellipse((cx_av - 5, cy_av - 5, cx_av + 113, cy_av + 113), outline=ring_col, width=3)
        board.paste(av_108, (cx_av, cy_av), mask=av_108.split()[3])
        draw.text((soc_x + 166, sy_s + 54), handle, fill=(255, 255, 255), font=f_ui_bold)
        draw.text((soc_x + 166, sy_s + 80), "All About Brain", fill=(226, 232, 240), font=f_ui_sm)
        draw.text((soc_x + 166, sy_s + 104), bio_txt, fill=(156, 163, 175), font=f_ui_tiny)
        draw.rounded_rectangle((soc_x + 516, sy_s + 72, soc_x + 652, sy_s + 106), radius=8, fill=btn_col)
        draw.text((soc_x + 584, sy_s + 89), "Follow", fill=btn_txt_col, font=f_ui_sm, anchor="mm")

    # ------------------------------------------------------------------
    # PANEL 2: FINAL LOCKED BANNER (JH-3) + YOUTUBE HEADERS + TV BLEED
    # ------------------------------------------------------------------
    p2_y, p2_h = 734, 750
    draw.rounded_rectangle((40, p2_y, board_w - 40, p2_y + p2_h), radius=16, fill=(12, 18, 28), outline=teal_accent, width=2)
    draw.rounded_rectangle((64, p2_y + 18, 254, p2_y + 46), radius=6, fill=teal_accent)
    draw.text((159, p2_y + 32), "LOCKED BANNER", fill=(8, 12, 18), font=f_badge, anchor="mm")
    draw.text((272, p2_y + 16), "JH-3 CINEMA HORIZON + VIEWER-CLEAN 8-SLOT COPY LOCK", fill=(245, 247, 250), font=f_sec)
    draw.text((64, p2_y + 52), "2560×423 Desktop strip · green 1546×423 Mobile safe crop · live #0F0F0F Desktop/Mobile headers + 16:9 TV bleed", fill=(148, 163, 184), font=f_sub)

    strip_crop = banner_rgb.crop(DESKTOP_ZONE_BOX)
    mob_crop = banner_rgb.crop(SAFE_ZONE_BOX)
    av_54 = _make_circular_avatar(logo_rgb, 54)
    av_42 = _make_circular_avatar(logo_rgb, 42)

    sx, sy = 64, p2_y + 92
    disp_w = 1720
    disp_h = int(round(disp_w * (423.0 / 2560.0)))  # 284
    board.paste(strip_crop.resize((disp_w, disp_h), resample=Image.Resampling.LANCZOS), (sx, sy))
    draw.rectangle((sx, sy, sx + disp_w, sy + disp_h), outline=(64, 84, 112), width=2)
    mx0 = sx + int(round(disp_w * (SAFE_ZONE_BOX[0] / float(BANNER_W))))
    mx1 = sx + int(round(disp_w * (SAFE_ZONE_BOX[2] / float(BANNER_W))))
    _draw_dashed_rect(draw, (mx0, sy + 2, mx1, sy + disp_h - 2), outline=(34, 197, 94), width=2, dash=14, gap=8)

    tv_x, tv_w = sx + disp_w + 20, 532
    tv_h = int(round(tv_w * (9.0 / 16.0)))  # 299
    board.paste(banner_rgb.resize((tv_w, tv_h), resample=Image.Resampling.LANCZOS), (tv_x, sy))
    draw.rectangle((tv_x, sy, tv_x + tv_w, sy + tv_h), outline=(80, 96, 120), width=2)
    _draw_dashed_hline(draw, tv_x + 2, tv_x + tv_w - 2, sy + int(round(tv_h * (SAFE_ZONE_BOX[1] / float(BANNER_H)))), fill=(34, 197, 94), width=1)
    _draw_dashed_hline(draw, tv_x + 2, tv_x + tv_w - 2, sy + int(round(tv_h * (SAFE_ZONE_BOX[3] / float(BANNER_H)))), fill=(34, 197, 94), width=1)
    draw.text((tv_x + 6, sy + tv_h + 8), "TV 16:9 FULL BLEED (2560×1440)", fill=(148, 163, 184), font=f_ui_tiny)

    row_y = sy + disp_h + 22
    ui_h = p2_y + p2_h - row_y - 22  # ~330px
    desk_px, desk_pw = sx, 1040
    draw.rounded_rectangle((desk_px, row_y, desk_px + desk_pw, row_y + ui_h), radius=10, fill=(15, 15, 15), outline=(44, 54, 72), width=1)
    d_bw = desk_pw - 28
    d_bh = int(round(d_bw * (423.0 / 2560.0)))
    board.paste(strip_crop.resize((d_bw, d_bh), resample=Image.Resampling.LANCZOS), (desk_px + 14, row_y + 14))
    board.paste(av_54, (desk_px + 20, row_y + 14 + d_bh + 18), mask=av_54.split()[3])
    draw.text((desk_px + 88, row_y + 14 + d_bh + 20), "All About Brain", fill=(255, 255, 255), font=f_ui_bold)
    draw.text((desk_px + 88, row_y + 14 + d_bh + 44), "@AllAboutBrainOfficial · DESKTOP #0F0F0F HEADER", fill=(170, 170, 170), font=f_ui_tiny)
    draw.rounded_rectangle((desk_px + desk_pw - 132, row_y + 14 + d_bh + 28, desk_px + desk_pw - 22, row_y + 14 + d_bh + 60), radius=16, fill=(255, 255, 255))
    draw.text((desk_px + desk_pw - 77, row_y + 14 + d_bh + 44), "Subscribe", fill=(15, 15, 15), font=f_ui_sm, anchor="mm")

    mob_px = desk_px + desk_pw + 18
    mob_pw = disp_w - desk_pw - 18  # 662
    draw.rounded_rectangle((mob_px, row_y, mob_px + mob_pw, row_y + ui_h), radius=10, fill=(15, 15, 15), outline=(44, 54, 72), width=1)
    m_bw = mob_pw - 28
    m_bh = int(round(m_bw * (423.0 / 1546.0)))
    board.paste(mob_crop.resize((m_bw, m_bh), resample=Image.Resampling.LANCZOS), (mob_px + 14, row_y + 14))
    board.paste(av_42, (mob_px + 18, row_y + 14 + m_bh + 16), mask=av_42.split()[3])
    draw.text((mob_px + 72, row_y + 14 + m_bh + 18), "All About Brain", fill=(255, 255, 255), font=f_ui_bold)
    draw.text((mob_px + 72, row_y + 14 + m_bh + 40), "MOBILE 1546×423 SAFE CROP + TED RED", fill=(34, 197, 94), font=f_ui_tiny)
    draw.rounded_rectangle((mob_px + mob_pw - 118, row_y + 14 + m_bh + 24, mob_px + mob_pw - 18, row_y + 14 + m_bh + 54), radius=15, fill=(255, 255, 255))
    draw.text((mob_px + mob_pw - 68, row_y + 14 + m_bh + 39), "Subscribe", fill=(15, 15, 15), font=f_ui_sm, anchor="mm")

    # Summary spec box below TV bleed
    spec_y = row_y + 16
    spec_h = p2_y + p2_h - spec_y - 22
    draw.rounded_rectangle((tv_x, spec_y, tv_x + tv_w, spec_y + spec_h), radius=10, fill=(15, 23, 36), outline=(56, 72, 98), width=1)
    draw.text((tv_x + 18, spec_y + 18), "FINAL BRAND SELECTION SUMMARY", fill=coral_accent, font=f_badge)
    spec_lines = [
        "Avatar Key: logo_A_ted_red (800×800 RGB PNG)",
        "Banner Key: banner_jh3_human_element (2560×1440 PNG)",
        "Studio Upload: banner_youtube_2560x1440_jh3_yt_upload.jpg (<=5.5MB)",
        "Mobile Safe Box: x:507..2053, y:508..931 (1546×423)",
        "Upload Ready: YouTube Studio · IG · TikTok",
    ]
    for i_sp, s_ln in enumerate(spec_lines):
        draw.text((tv_x + 18, spec_y + 54 + i_sp * 42), s_ln, fill=(226, 232, 240), font=f_sub)

    # ------------------------------------------------------------------
    # PANEL 3: FULL 2560x423 STRIP ZOOM + 8-SLOT COPY CHECKLIST
    # ------------------------------------------------------------------
    p3_y, p3_h = 1508, 732
    draw.rounded_rectangle((40, p3_y, board_w - 40, p3_y + p3_h), radius=16, fill=(12, 18, 28), outline=(56, 72, 98), width=2)
    draw.text((64, p3_y + 18), "3. HIGH-RES 2560×423 DESKTOP STRIP ZOOM & 8-SLOT VIEWER COPY VERIFICATION", fill=(245, 247, 250), font=f_sec)
    draw.text((64, p3_y + 52), "Inspect left desktop wing notes, center 1546×423 title lockup, and right desktop wing notes at near-1:1 legibility", fill=(148, 163, 184), font=f_sub)

    z_x, z_y, z_w = 64, p3_y + 88, 2272
    z_h = int(round(z_w * (423.0 / 2560.0)))  # 375
    board.paste(strip_crop.resize((z_w, z_h), resample=Image.Resampling.LANCZOS), (z_x, z_y))
    draw.rectangle((z_x, z_y, z_x + z_w, z_y + z_h), outline=(72, 94, 124), width=2)
    zx0 = z_x + int(round(z_w * (SAFE_ZONE_BOX[0] / float(BANNER_W))))
    zx1 = z_x + int(round(z_w * (SAFE_ZONE_BOX[2] / float(BANNER_W))))
    _draw_dashed_rect(draw, (zx0, z_y + 2, zx1, z_y + z_h - 2), outline=(34, 197, 94), width=2, dash=14, gap=8)

    # 3-column 8-slot copy verification strip
    col_y = z_y + z_h + 22
    col_h = p3_y + p3_h - col_y - 22  # ~225
    col_w = 740
    cols_spec = [
        (
            "LEFT DESKTOP WING NOTES (x:108..400)",
            teal_accent,
            [
                f"1. \"{JH3_FINAL_LEFT_NOTES[0][0]}\"  ({JH3_FINAL_LEFT_NOTES[0][1]:+.1f}°)",
                f"2. \"{JH3_FINAL_LEFT_NOTES[1][0]}\"  ({JH3_FINAL_LEFT_NOTES[1][1]:+.1f}°)",
                f"3. \"{JH3_FINAL_LEFT_NOTES[2][0]}\"  ({JH3_FINAL_LEFT_NOTES[2][1]:+.1f}°)",
            ],
        ),
        (
            "CENTER SAFE-ZONE LOCKUP (1546×423)",
            coral_accent,
            [
                f"4. Eyebrow:   {JH3_FINAL_EYEBROW}",
                "5. Wordmark:  ALL ABOUT BRAIN",
                f"6. Signature: \"{JH3_FINAL_SIGNATURE}\"",
            ],
        ),
        (
            "RIGHT DESKTOP WING NOTES (x:2090..2390)",
            teal_accent,
            [
                f"7. \"{JH3_FINAL_RIGHT_NOTES[0][0]}\"  ({JH3_FINAL_RIGHT_NOTES[0][1]:+.1f}°)",
                f"8. \"{JH3_FINAL_RIGHT_NOTES[1][0]}\"  ({JH3_FINAL_RIGHT_NOTES[1][1]:+.1f}°)",
                f"9. \"{JH3_FINAL_RIGHT_NOTES[2][0]}\"  ({JH3_FINAL_RIGHT_NOTES[2][1]:+.1f}°)",
            ],
        ),
    ]
    for c_i, (c_title, c_acc, c_lines) in enumerate(cols_spec):
        cx_c = 64 + c_i * (col_w + 26)
        draw.rounded_rectangle((cx_c, col_y, cx_c + col_w, col_y + col_h), radius=10, fill=(16, 24, 38), outline=(50, 68, 92), width=1)
        draw.text((cx_c + 18, col_y + 18), c_title, fill=c_acc, font=f_badge)
        for l_i, line_txt in enumerate(c_lines):
            draw.text((cx_c + 18, col_y + 56 + l_i * 44), line_txt, fill=(236, 242, 248), font=f_sub)

    _atomic_save_image(board, out_path, format="JPEG", quality=95, subsampling=0)
    return {
        "file": out_path.name,
        "width": board_w,
        "height": board_h,
        "avatar_key": "logo_A_ted_red",
        "banner_key": "banner_jh3_human_element",
        "sha256": _sha256_file(out_path),
        "bytes": out_path.stat().st_size,
    }


def build_pack(output_dir: Path = OUTPUT_DIR) -> dict[str, Any]:
    """Generate all brand identity assets and manifest.json atomically."""
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, src in SOURCE_ASSETS.items():
        if not src.is_file():
            raise FileNotFoundError(f"Missing locked source asset '{name}': {src}")
    for name, src in JH5_SOURCE_ASSETS.items():
        if not src.is_file():
            raise FileNotFoundError(f"Missing JH-5 zero-face source asset '{name}': {src}")
    if not MNI152_ATLAS_NPZ.is_file():
        raise FileNotFoundError(f"Missing MNI152 3D atlas: {MNI152_ATLAS_NPZ}")

    logo_a_path = output_dir / "logo_A_ep31_gypsum_cyan.png"
    logo_a_red_path = output_dir / "logo_A_red_ep31_gypsum_crimson.png"
    logo_a_ted_red_path = output_dir / "logo_A_ted_red_bg_cyan_brain.png"
    logo_a_studio_crimson_path = output_dir / "logo_A_crimson_studio_bg_cyan_brain.png"
    logo_b_path = output_dir / "logo_B_mode1_xray_skull.png"
    logo_c_path = output_dir / "logo_C_split_cyan_crimson.png"
    banner_path = output_dir / "banner_youtube_2560x1440.png"
    banner_red_path = output_dir / "banner_youtube_2560x1440_red.png"
    banner_mx_a_path = output_dir / "banner_youtube_2560x1440_matrix_10slice_A_cyan.png"
    banner_mx_b_path = output_dir / "banner_youtube_2560x1440_matrix_10slice_B_dual.png"
    banner_ce_a_path = output_dir / "banner_youtube_2560x1440_crimson_echo_A_lateral.png"
    banner_ce_b_path = output_dir / "banner_youtube_2560x1440_crimson_echo_B_dorsal.png"
    banner_mri_a_path = output_dir / "banner_youtube_2560x1440_mri_glass_A_panes.png"
    banner_mri_b_path = output_dir / "banner_youtube_2560x1440_mri_glass_B_sculpted.png"
    banner_jh1_path = output_dir / "banner_youtube_2560x1440_jh1_lightbox.png"
    banner_jh2_path = output_dir / "banner_youtube_2560x1440_jh2_crimson_darkroom.png"
    banner_jh3_path = output_dir / "banner_youtube_2560x1440_jh3_human_element_homage.png"
    banner_jh3_yt_upload_path = output_dir / "banner_youtube_2560x1440_jh3_yt_upload.jpg"
    banner_jh4_path = output_dir / "banner_youtube_2560x1440_jh4_fmri_tunnel.png"
    banner_jh5_path = output_dir / "banner_youtube_2560x1440_jh5_investigator_desk.png"
    banner_jh2a_path = output_dir / "banner_youtube_2560x1440_jh2a_hologram_wave_stream.png"
    banner_jh2b_path = output_dir / "banner_youtube_2560x1440_jh2b_hologram_multi_angle_beam.png"
    banner_jh2c_path = output_dir / "banner_youtube_2560x1440_jh2c_hologram_mri_strip.png"
    banner_jh2d_path = output_dir / "banner_youtube_2560x1440_jh2d_hologram_echo_panorama.png"
    banner_jh2e_path = output_dir / "banner_youtube_2560x1440_jh2e_hologram_cortical_horizon.png"
    banner_rc1_path = output_dir / "banner_youtube_2560x1440_rc1_pure_type.png"
    banner_rc2_path = output_dir / "banner_youtube_2560x1440_rc2_type_plus_brain.png"
    banner_rc3_path = output_dir / "banner_youtube_2560x1440_rc3_stacked_3d_poster.png"
    sheet_path = output_dir / "brand_rebrand_comparison_sheet.jpg"
    cyan_vs_red_sheet_path = output_dir / "logo_A_cyan_vs_red_comparison.jpg"
    ted_red_sheet_path = output_dir / "logo_ted_red_bg_comparison.jpg"
    mx_sheet_path = output_dir / "banner_matrix_10slice_comparison.jpg"
    ce_sheet_path = output_dir / "banner_crimson_echo_comparison.jpg"
    mri_sheet_path = output_dir / "banner_mri_glass_comparison.jpg"
    jh5_sheet_path = output_dir / "banner_jh5_collection_comparison.jpg"
    jh2_5opts_sheet_path = output_dir / "banner_jh2_5opts_comparison.jpg"
    rc_sheet_path = output_dir / "banner_ricks_clips_3opts_comparison.jpg"
    final_lock_sheet_path = output_dir / "brand_final_lock_preview.jpg"
    manifest_path = output_dir / "manifest.json"

    logo_a_meta = build_logo_a(logo_a_path)
    logo_a_red_meta = build_logo_a_red(logo_a_red_path)
    logo_a_ted_red_meta = build_logo_a_ted_red(logo_a_ted_red_path)
    logo_a_studio_crimson_meta = build_logo_a_crimson_studio(logo_a_studio_crimson_path)
    logo_b_meta = build_logo_b(logo_b_path)
    logo_c_meta = build_logo_c(logo_c_path)
    banner_meta = build_banner(banner_path, accent_mode="cyan")
    banner_red_meta = build_banner_red(banner_red_path)
    banner_mx_a_meta = build_banner_matrix_10slice_a(banner_mx_a_path)
    banner_mx_b_meta = build_banner_matrix_10slice_b(banner_mx_b_path)
    banner_ce_a_meta = build_banner_crimson_echo_a(banner_ce_a_path)
    banner_ce_b_meta = build_banner_crimson_echo_b(banner_ce_b_path)
    banner_mri_a_meta = build_banner_mri_glass_a(banner_mri_a_path)
    banner_mri_b_meta = build_banner_mri_glass_b(banner_mri_b_path)
    banner_jh1_meta = build_banner_jh1_lightbox(banner_jh1_path)
    banner_jh2_meta = build_banner_jh2_crimson_darkroom(banner_jh2_path)
    banner_jh3_meta = build_banner_jh3_human_element_homage(banner_jh3_path)
    banner_jh3_yt_upload_meta = build_banner_jh3_yt_upload(
        banner_jh3_path,
        banner_jh3_yt_upload_path,
        copy_bboxes=banner_jh3_meta["text_bboxes"],
    )
    banner_jh4_meta = build_banner_jh4_fmri_tunnel(banner_jh4_path)
    banner_jh5_meta = build_banner_jh5_investigator_desk(banner_jh5_path)
    banner_jh2a_meta = build_banner_jh2a_hologram_wave_stream(banner_jh2a_path)
    banner_jh2b_meta = build_banner_jh2b_hologram_multi_angle_beam(banner_jh2b_path)
    banner_jh2c_meta = build_banner_jh2c_hologram_mri_strip(banner_jh2c_path)
    banner_jh2d_meta = build_banner_jh2d_hologram_echo_panorama(banner_jh2d_path)
    banner_jh2e_meta = build_banner_jh2e_hologram_cortical_horizon(banner_jh2e_path)
    banner_rc1_meta = build_banner_rc1_pure_type(banner_rc1_path)
    banner_rc2_meta = build_banner_rc2_type_plus_brain(banner_rc2_path)
    banner_rc3_meta = build_banner_rc3_stacked_3d_poster(banner_rc3_path)
    sheet_meta = build_comparison_sheet(
        sheet_path,
        logo_paths=[
            ("LOGO A: GYPSUM + CYAN", "Ep #31 lateral matte gypsum + #27D8FF vessels", "#1 RECOMMENDED", True, logo_a_path),
            ("LOGO B: MODE 1 X-RAY", "Featureless translucent Mode 1 profile + #27D8FF", "OPTION B", False, logo_b_path),
            ("LOGO C: SPLIT HEMISPHERES", "Dorsal Ep #31 split: #27D8FF cyan vs #FF2525", "OPTION C", False, logo_c_path),
        ],
        banner_path=banner_path,
    )
    cyan_vs_red_meta = build_cyan_vs_red_comparison_sheet(
        cyan_vs_red_sheet_path,
        logo_cyan_path=logo_a_path,
        logo_red_path=logo_a_red_path,
        banner_red_path=banner_red_path,
    )
    ted_red_sheet_meta = build_ted_red_comparison_sheet(
        ted_red_sheet_path,
        ted_logo_path=logo_a_ted_red_path,
        studio_logo_path=logo_a_studio_crimson_path,
    )
    mx_sheet_meta = build_matrix_10slice_comparison_sheet(
        mx_sheet_path,
        mx_a_path=banner_mx_a_path,
        mx_b_path=banner_mx_b_path,
        ted_red_logo_path=logo_a_ted_red_path,
    )
    ce_sheet_meta = build_crimson_echo_comparison_sheet(
        ce_sheet_path,
        echo_a_path=banner_ce_a_path,
        echo_b_path=banner_ce_b_path,
        ted_red_logo_path=logo_a_ted_red_path,
    )
    mri_sheet_meta = build_mri_glass_comparison_sheet(
        mri_sheet_path,
        mri_a_path=banner_mri_a_path,
        mri_b_path=banner_mri_b_path,
        ted_red_logo_path=logo_a_ted_red_path,
    )
    jh5_sheet_meta = build_jh5_collection_comparison_sheet(
        jh5_sheet_path,
        jh_paths=[
            ("JH-1: MIDNIGHT LAB × MRI LIGHTBOX", "Moody university neuro lab · dual MRI lightbox · Caveat wing notes", "JH-1 · LIGHTBOX", (228, 92, 68), banner_jh1_path),
            ("JH-2: CRIMSON DARKROOM SPECIMEN", "TED-red 660nm darkroom glow · faceless H01 gypsum specimen vitrine", "JH-2 · DARKROOM", (230, 43, 30), banner_jh2_path),
            ("JH-3: 'THE HUMAN ELEMENT' HORIZON", "Misty teal coastal horizon · viewer-friendly neuroscience notes · 1546×423 safe lockup", "JH-3 · HORIZON", (107, 171, 178), banner_jh3_path),
            ("JH-4: 3T fMRI SCANNER TUNNEL", "Empty 3-Tesla fMRI suite · floating A18 coronal hippocampus glass slice", "JH-4 · fMRI", (39, 216, 255), banner_jh4_path),
            ("JH-5: INVESTIGATIVE EVIDENCE DESK", "Architect lamp walnut study · grounded A02 gypsum cortex specimen", "JH-5 · EVIDENCE", (228, 128, 72), banner_jh5_path),
        ],
        ted_red_logo_path=logo_a_ted_red_path,
    )
    jh2_5opts_sheet_meta = build_jh2_5opts_comparison_sheet(
        jh2_5opts_sheet_path,
        jh2_paths=[
            ("JH2-A: CENTER HOLOGRAM + EEG WAVE STREAM", "660nm crimson darkroom · centered A02 blue hologram + wide EEG & neural wave ribbons", "JH2-A · WAVE", (39, 216, 255), banner_jh2a_path),
            ("JH2-B: 4-VIEW BLUE HOLOGRAM BEAM", "Wide horizontal beam projecting A01 glass profile -> A02 lateral -> A03 dorsal -> A07 brainstem", "JH2-B · 4-VIEW", (230, 43, 30), banner_jh2b_path),
            ("JH2-C: 7-SLICE MNI152 HOLOGRAM MRI STRIP", "Floating #27D8FF wireframe MNI152 coronal slice sequence across crimson darkroom", "JH2-C · MNI152", (39, 216, 255), banner_jh2c_path),
            ("JH2-D: PURE BLUE HOLOGRAM + ECHO PANORAMA", "Translucent blue holographic A02 brain radiating 10 horizontal bullet-time contour echoes", "JH2-D · ECHOES", (230, 43, 30), banner_jh2d_path),
            ("JH2-E: EDGE-TO-EDGE CORTICAL HORIZON", "2560px panoramic A13 white-matter tracts + A02 core + A05 sulcal vessels in 660nm lab", "JH2-E · HORIZON", (39, 216, 255), banner_jh2e_path),
        ],
        ted_red_logo_path=logo_a_ted_red_path,
    )
    rc_sheet_meta = build_ricks_clips_3opts_comparison_sheet(
        rc_sheet_path,
        rc_paths=[
            ("RC-1: PURE SINGLE-LINE 3D WORDMARK", "100% vivid #E62B1E red · massive single-line ALL ABOUT BRAIN in 3D pop typography", "RC-1 · PURE 3D", (230, 43, 30), banner_rc1_path),
            ("RC-2: VIVID RED + EP #31 CYAN BRAIN + STACKED 3D", "Clean #E62B1E red · fringe-free Ep #31 cyan brain (left) + stacked 3D ALL ABOUT / BRAIN", "RC-2 · + BRAIN", (39, 216, 255), banner_rc2_path),
            ("RC-3: GIANT 2-LINE STACKED 3D + #27D8FF BAR", "Pure #E62B1E red · monumental ALL ABOUT / BRAIN 3D lockup + electric cyan underscore bar", "RC-3 · POSTER", (230, 43, 30), banner_rc3_path),
        ],
        ted_red_logo_path=logo_a_ted_red_path,
    )
    final_lock_sheet_meta = build_brand_final_lock_preview_sheet(
        final_lock_sheet_path,
        ted_red_logo_path=logo_a_ted_red_path,
        final_banner_path=banner_jh3_path,
    )

    manifest = {
        "schema": "aab_brand_identity_pack_v2",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "output_dir": str(output_dir.relative_to(WORKSPACE_ROOT)),
        "final_selected_pair": {
            "avatar_key": "logo_A_ted_red",
            "avatar_file": logo_a_ted_red_meta["file"],
            "avatar_sha256": logo_a_ted_red_meta["sha256"],
            "banner_key": "banner_jh3_human_element",
            "banner_file": banner_jh3_meta["file"],
            "banner_sha256": banner_jh3_meta["sha256"],
            "banner_upload_key": "banner_jh3_yt_upload",
            "banner_upload_file": banner_jh3_yt_upload_meta["file"],
            "banner_upload_path": str(banner_jh3_yt_upload_path.relative_to(WORKSPACE_ROOT)),
            "banner_upload_sha256": banner_jh3_yt_upload_meta["sha256"],
            "banner_upload_bytes": banner_jh3_yt_upload_meta["bytes"],
            "preview_sheet_key": "brand_final_lock_sheet",
            "preview_sheet_file": final_lock_sheet_meta["file"],
            "copy_slots": banner_jh3_meta["copy_slots"],
        },
        "palette": {
            "void_bg": VOID_HEX,
            "studio_glow": GLOW_HEX,
            "crimson_glow": CRIMSON_GLOW_HEX,
            "sulcal_cyan": CYAN_HEX,
            "contrast_crimson": CRIMSON_HEX,
            "ted_red_center": TED_RED_CENTER_HEX,
            "ted_red_edge": TED_RED_EDGE_HEX,
            "studio_crimson_center": STUDIO_CRIMSON_CENTER_HEX,
            "studio_crimson_edge": STUDIO_CRIMSON_EDGE_HEX,
        },
        "fonts": {
            "display": str(PRIMARY_DISPLAY_FONT.relative_to(WORKSPACE_ROOT)) if PRIMARY_DISPLAY_FONT.exists() else str(FALLBACK_FONT),
            "subhead": str(PRIMARY_BODY_FONT.relative_to(WORKSPACE_ROOT)) if PRIMARY_BODY_FONT.exists() else str(FALLBACK_FONT),
            "handwriting": str(CAVEAT_FONT.relative_to(WORKSPACE_ROOT)) if CAVEAT_FONT.exists() else str(FALLBACK_FONT),
        },
        "jh5_flow_prompts": JH5_FLOW_PROMPTS,
        "jh2_5opts_flow_prompts": JH2_5OPTS_FLOW_PROMPTS,
        "assets": {
            "logo_A": logo_a_meta,
            "logo_A_red": logo_a_red_meta,
            "logo_A_ted_red": logo_a_ted_red_meta,
            "logo_A_crimson_studio": logo_a_studio_crimson_meta,
            "logo_B": logo_b_meta,
            "logo_C": logo_c_meta,
            "banner": banner_meta,
            "banner_red": banner_red_meta,
            "banner_matrix_10slice_A": banner_mx_a_meta,
            "banner_matrix_10slice_B": banner_mx_b_meta,
            "banner_crimson_echo_A": banner_ce_a_meta,
            "banner_crimson_echo_B": banner_ce_b_meta,
            "banner_mri_glass_A": banner_mri_a_meta,
            "banner_mri_glass_B": banner_mri_b_meta,
            "banner_jh1_lightbox": banner_jh1_meta,
            "banner_jh2_crimson_darkroom": banner_jh2_meta,
            "banner_jh3_human_element": banner_jh3_meta,
            "banner_jh3_yt_upload": banner_jh3_yt_upload_meta,
            "banner_jh4_fmri_tunnel": banner_jh4_meta,
            "banner_jh5_investigator_desk": banner_jh5_meta,
            "banner_jh2a_wave_stream": banner_jh2a_meta,
            "banner_jh2b_multi_angle": banner_jh2b_meta,
            "banner_jh2c_mri_strip": banner_jh2c_meta,
            "banner_jh2d_echo_panorama": banner_jh2d_meta,
            "banner_jh2e_cortical_horizon": banner_jh2e_meta,
            "banner_rc1_pure_type": banner_rc1_meta,
            "banner_rc2_type_plus_brain": banner_rc2_meta,
            "banner_rc3_stacked_3d_poster": banner_rc3_meta,
            "comparison_sheet": sheet_meta,
            "logo_A_cyan_vs_red_sheet": cyan_vs_red_meta,
            "logo_ted_red_bg_sheet": ted_red_sheet_meta,
            "banner_matrix_10slice_sheet": mx_sheet_meta,
            "banner_crimson_echo_sheet": ce_sheet_meta,
            "banner_mri_glass_sheet": mri_sheet_meta,
            "banner_jh5_collection_sheet": jh5_sheet_meta,
            "banner_jh2_5opts_sheet": jh2_5opts_sheet_meta,
            "banner_ricks_clips_3opts_sheet": rc_sheet_meta,
            "brand_final_lock_sheet": final_lock_sheet_meta,
        },
    }
    _atomic_write_json(manifest, manifest_path)
    return manifest


def check_pack(output_dir: Path = OUTPUT_DIR) -> dict[str, Any]:
    """Read-only verification of all generated brand assets, SHA-256 locks, and banner safe zones."""
    issues: list[str] = []
    manifest_path = output_dir / "manifest.json"
    if not manifest_path.is_file():
        return {"passed": False, "output_dir": str(output_dir), "issues": ["Missing manifest.json"]}

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assets_meta = manifest.get("assets", {})
    expected_specs = {
        "logo_A": ("logo_A_ep31_gypsum_cyan.png", LOGO_SIZE, LOGO_SIZE),
        "logo_A_red": ("logo_A_red_ep31_gypsum_crimson.png", LOGO_SIZE, LOGO_SIZE),
        "logo_A_ted_red": ("logo_A_ted_red_bg_cyan_brain.png", LOGO_SIZE, LOGO_SIZE),
        "logo_A_crimson_studio": ("logo_A_crimson_studio_bg_cyan_brain.png", LOGO_SIZE, LOGO_SIZE),
        "logo_B": ("logo_B_mode1_xray_skull.png", LOGO_SIZE, LOGO_SIZE),
        "logo_C": ("logo_C_split_cyan_crimson.png", LOGO_SIZE, LOGO_SIZE),
        "banner": ("banner_youtube_2560x1440.png", BANNER_W, BANNER_H),
        "banner_red": ("banner_youtube_2560x1440_red.png", BANNER_W, BANNER_H),
        "banner_matrix_10slice_A": ("banner_youtube_2560x1440_matrix_10slice_A_cyan.png", BANNER_W, BANNER_H),
        "banner_matrix_10slice_B": ("banner_youtube_2560x1440_matrix_10slice_B_dual.png", BANNER_W, BANNER_H),
        "banner_crimson_echo_A": ("banner_youtube_2560x1440_crimson_echo_A_lateral.png", BANNER_W, BANNER_H),
        "banner_crimson_echo_B": ("banner_youtube_2560x1440_crimson_echo_B_dorsal.png", BANNER_W, BANNER_H),
        "banner_mri_glass_A": ("banner_youtube_2560x1440_mri_glass_A_panes.png", BANNER_W, BANNER_H),
        "banner_mri_glass_B": ("banner_youtube_2560x1440_mri_glass_B_sculpted.png", BANNER_W, BANNER_H),
        "banner_jh1_lightbox": ("banner_youtube_2560x1440_jh1_lightbox.png", BANNER_W, BANNER_H),
        "banner_jh2_crimson_darkroom": ("banner_youtube_2560x1440_jh2_crimson_darkroom.png", BANNER_W, BANNER_H),
        "banner_jh3_human_element": ("banner_youtube_2560x1440_jh3_human_element_homage.png", BANNER_W, BANNER_H),
        "banner_jh3_yt_upload": ("banner_youtube_2560x1440_jh3_yt_upload.jpg", BANNER_W, BANNER_H),
        "banner_jh4_fmri_tunnel": ("banner_youtube_2560x1440_jh4_fmri_tunnel.png", BANNER_W, BANNER_H),
        "banner_jh5_investigator_desk": ("banner_youtube_2560x1440_jh5_investigator_desk.png", BANNER_W, BANNER_H),
        "banner_jh2a_wave_stream": ("banner_youtube_2560x1440_jh2a_hologram_wave_stream.png", BANNER_W, BANNER_H),
        "banner_jh2b_multi_angle": ("banner_youtube_2560x1440_jh2b_hologram_multi_angle_beam.png", BANNER_W, BANNER_H),
        "banner_jh2c_mri_strip": ("banner_youtube_2560x1440_jh2c_hologram_mri_strip.png", BANNER_W, BANNER_H),
        "banner_jh2d_echo_panorama": ("banner_youtube_2560x1440_jh2d_hologram_echo_panorama.png", BANNER_W, BANNER_H),
        "banner_jh2e_cortical_horizon": ("banner_youtube_2560x1440_jh2e_hologram_cortical_horizon.png", BANNER_W, BANNER_H),
        "banner_rc1_pure_type": ("banner_youtube_2560x1440_rc1_pure_type.png", BANNER_W, BANNER_H),
        "banner_rc2_type_plus_brain": ("banner_youtube_2560x1440_rc2_type_plus_brain.png", BANNER_W, BANNER_H),
        "banner_rc3_stacked_3d_poster": ("banner_youtube_2560x1440_rc3_stacked_3d_poster.png", BANNER_W, BANNER_H),
        "comparison_sheet": ("brand_rebrand_comparison_sheet.jpg", None, None),
        "logo_A_cyan_vs_red_sheet": ("logo_A_cyan_vs_red_comparison.jpg", None, None),
        "logo_ted_red_bg_sheet": ("logo_ted_red_bg_comparison.jpg", None, None),
        "banner_matrix_10slice_sheet": ("banner_matrix_10slice_comparison.jpg", None, None),
        "banner_crimson_echo_sheet": ("banner_crimson_echo_comparison.jpg", None, None),
        "banner_mri_glass_sheet": ("banner_mri_glass_comparison.jpg", None, None),
        "banner_jh5_collection_sheet": ("banner_jh5_collection_comparison.jpg", None, None),
        "banner_jh2_5opts_sheet": ("banner_jh2_5opts_comparison.jpg", None, None),
        "banner_ricks_clips_3opts_sheet": ("banner_ricks_clips_3opts_comparison.jpg", None, None),
        "brand_final_lock_sheet": ("brand_final_lock_preview.jpg", None, None),
    }

    verified_assets: dict[str, Any] = {}
    sha_all_match = True
    for key, (fname, exp_w, exp_h) in expected_specs.items():
        fpath = output_dir / fname
        if not fpath.is_file() or fpath.stat().st_size == 0:
            issues.append(f"Missing or empty asset: {fname}")
            sha_all_match = False
            continue
        with Image.open(fpath) as im:
            w, h = im.size
            mode = im.mode
        actual_sha = _sha256_file(fpath)
        locked_sha = assets_meta.get(key, {}).get("sha256")
        sha_match = bool(locked_sha and actual_sha == locked_sha)
        if not sha_match:
            issues.append(f"SHA-256 mismatch on {fname}: actual={actual_sha[:12]} locked={str(locked_sha)[:12]}")
            sha_all_match = False
        if exp_w is not None and (w != exp_w or h != exp_h):
            issues.append(f"Dimension mismatch on {fname}: got {w}x{h}, expected {exp_w}x{exp_h}")
        if key in (
            "comparison_sheet",
            "logo_A_cyan_vs_red_sheet",
            "logo_ted_red_bg_sheet",
            "banner_matrix_10slice_sheet",
            "banner_crimson_echo_sheet",
            "banner_mri_glass_sheet",
            "banner_jh5_collection_sheet",
            "banner_jh2_5opts_sheet",
            "banner_ricks_clips_3opts_sheet",
            "brand_final_lock_sheet",
        ) and (mode != "RGB" or w < 1800 or h < 1200):
            issues.append(f"Comparison sheet format/res invalid: {w}x{h} {mode}")
        verified_assets[key] = {
            "path": str(fpath),
            "size": f"{w}x{h}",
            "mode": mode,
            "bytes": fpath.stat().st_size,
            "sha256": actual_sha,
            "sha256_prefix": actual_sha[:12],
            "sha256_match": sha_match,
        }

    banner_safe_zone_check = _verify_banner_safe_zone_entry(
        output_dir,
        "banner_youtube_2560x1440.png",
        assets_meta.get("banner", {}),
        issues,
        "banner",
    )
    banner_red_safe_zone_check = _verify_banner_safe_zone_entry(
        output_dir,
        "banner_youtube_2560x1440_red.png",
        assets_meta.get("banner_red", {}),
        issues,
        "banner_red",
    )
    banner_matrix_10slice_a_check = _verify_matrix_10slice_banner_entry(
        output_dir,
        "banner_youtube_2560x1440_matrix_10slice_A_cyan.png",
        assets_meta.get("banner_matrix_10slice_A", {}),
        issues,
        "banner_matrix_10slice_A",
        expect_dual_red=False,
    )
    banner_matrix_10slice_b_check = _verify_matrix_10slice_banner_entry(
        output_dir,
        "banner_youtube_2560x1440_matrix_10slice_B_dual.png",
        assets_meta.get("banner_matrix_10slice_B", {}),
        issues,
        "banner_matrix_10slice_B",
        expect_dual_red=True,
    )
    matrix_10slice_banners_ok = bool(
        banner_matrix_10slice_a_check["text_bounds_ok"]
        and banner_matrix_10slice_a_check["hero_10slice_mobile_and_wings_ok"]
        and banner_matrix_10slice_a_check["atmosphere_grain_ok"]
        and banner_matrix_10slice_a_check["dual_red_pulse_ok"]
        and banner_matrix_10slice_b_check["text_bounds_ok"]
        and banner_matrix_10slice_b_check["hero_10slice_mobile_and_wings_ok"]
        and banner_matrix_10slice_b_check["atmosphere_grain_ok"]
        and banner_matrix_10slice_b_check["dual_red_pulse_ok"]
    )
    banner_crimson_echo_a_check = _verify_crimson_echo_banner_entry(
        output_dir,
        "banner_youtube_2560x1440_crimson_echo_A_lateral.png",
        assets_meta.get("banner_crimson_echo_A", {}),
        issues,
        "banner_crimson_echo_A",
    )
    banner_crimson_echo_b_check = _verify_crimson_echo_banner_entry(
        output_dir,
        "banner_youtube_2560x1440_crimson_echo_B_dorsal.png",
        assets_meta.get("banner_crimson_echo_B", {}),
        issues,
        "banner_crimson_echo_B",
    )
    crimson_echo_banners_ok = bool(
        banner_crimson_echo_a_check["title_only_bounds_ok"]
        and banner_crimson_echo_a_check["whole_brain_unclipped_ok"]
        and banner_crimson_echo_a_check["cyan_echoes_ok"]
        and banner_crimson_echo_a_check["crimson_atmosphere_ok"]
        and banner_crimson_echo_b_check["title_only_bounds_ok"]
        and banner_crimson_echo_b_check["whole_brain_unclipped_ok"]
        and banner_crimson_echo_b_check["cyan_echoes_ok"]
        and banner_crimson_echo_b_check["crimson_atmosphere_ok"]
    )
    banner_mri_glass_a_check = _verify_mri_glass_banner_entry(
        output_dir,
        "banner_youtube_2560x1440_mri_glass_A_panes.png",
        assets_meta.get("banner_mri_glass_A", {}),
        issues,
        "banner_mri_glass_A",
    )
    banner_mri_glass_b_check = _verify_mri_glass_banner_entry(
        output_dir,
        "banner_youtube_2560x1440_mri_glass_B_sculpted.png",
        assets_meta.get("banner_mri_glass_B", {}),
        issues,
        "banner_mri_glass_B",
    )
    mri_glass_banners_ok = bool(
        banner_mri_glass_a_check["title_only_bounds_ok"]
        and banner_mri_glass_a_check["slices_9_unclipped_ok"]
        and banner_mri_glass_a_check["anatomy_and_wings_ok"]
        and banner_mri_glass_a_check["crimson_atmosphere_ok"]
        and banner_mri_glass_b_check["title_only_bounds_ok"]
        and banner_mri_glass_b_check["slices_9_unclipped_ok"]
        and banner_mri_glass_b_check["anatomy_and_wings_ok"]
        and banner_mri_glass_b_check["crimson_atmosphere_ok"]
    )
    banner_jh5_checks: dict[str, dict[str, Any]] = {}
    for jh_key, jh_fname in (
        ("banner_jh1_lightbox", "banner_youtube_2560x1440_jh1_lightbox.png"),
        ("banner_jh2_crimson_darkroom", "banner_youtube_2560x1440_jh2_crimson_darkroom.png"),
        ("banner_jh3_human_element", "banner_youtube_2560x1440_jh3_human_element_homage.png"),
        ("banner_jh4_fmri_tunnel", "banner_youtube_2560x1440_jh4_fmri_tunnel.png"),
        ("banner_jh5_investigator_desk", "banner_youtube_2560x1440_jh5_investigator_desk.png"),
    ):
        banner_jh5_checks[jh_key] = _verify_jh5_banner_entry(
            output_dir,
            jh_fname,
            assets_meta.get(jh_key, {}),
            issues,
            jh_key,
        )
    jh5_collection_ok = len(banner_jh5_checks) == 5 and all(
        chk["safe_bounds_ok"]
        and chk["zero_cartoon_faces_ok"]
        and chk["zero_hard_seams_ok"]
        and chk["cinema_grain_and_depth_ok"]
        for chk in banner_jh5_checks.values()
    )
    banner_jh2_5opts_checks: dict[str, dict[str, Any]] = {}
    for jh2_key, jh2_fname in (
        ("banner_jh2a_wave_stream", "banner_youtube_2560x1440_jh2a_hologram_wave_stream.png"),
        ("banner_jh2b_multi_angle", "banner_youtube_2560x1440_jh2b_hologram_multi_angle_beam.png"),
        ("banner_jh2c_mri_strip", "banner_youtube_2560x1440_jh2c_hologram_mri_strip.png"),
        ("banner_jh2d_echo_panorama", "banner_youtube_2560x1440_jh2d_hologram_echo_panorama.png"),
        ("banner_jh2e_cortical_horizon", "banner_youtube_2560x1440_jh2e_hologram_cortical_horizon.png"),
    ):
        banner_jh2_5opts_checks[jh2_key] = _verify_jh2_5opts_banner_entry(
            output_dir,
            jh2_fname,
            assets_meta.get(jh2_key, {}),
            issues,
            jh2_key,
        )
    jh2_5opts_ok = len(banner_jh2_5opts_checks) == 5 and all(
        chk["safe_bounds_ok"]
        and chk["zero_cartoon_faces_ok"]
        and chk["wide_blue_hologram_ok"]
        and chk["crimson_darkroom_and_grain_ok"]
        for chk in banner_jh2_5opts_checks.values()
    )
    banner_ricks_clips_checks: dict[str, dict[str, Any]] = {}
    for rc_key, rc_fname, rc_mode in (
        ("banner_rc1_pure_type", "banner_youtube_2560x1440_rc1_pure_type.png", "rc1_pure_type"),
        ("banner_rc2_type_plus_brain", "banner_youtube_2560x1440_rc2_type_plus_brain.png", "rc2_type_plus_brain"),
        ("banner_rc3_stacked_3d_poster", "banner_youtube_2560x1440_rc3_stacked_3d_poster.png", "rc3_stacked_3d_poster"),
    ):
        banner_ricks_clips_checks[rc_key] = _verify_ricks_clips_banner_entry(
            output_dir,
            rc_fname,
            assets_meta.get(rc_key, {}),
            issues,
            rc_key,
            rc_mode,
        )
    ricks_clips_3opts_ok = len(banner_ricks_clips_checks) == 3 and all(
        chk["safe_bounds_ok"]
        and chk["pure_vivid_red_wings_ok"]
        and chk["chunky_3d_pop_type_ok"]
        and chk["variant_feature_ok"]
        for chk in banner_ricks_clips_checks.values()
    )
    logo_a_red_zero_pink_bleed_ok = _verify_logo_a_red_purity(
        output_dir / "logo_A_red_ep31_gypsum_crimson.png",
        issues,
    )
    ted_red_zero_navy_fringe_ok = _verify_red_bg_cyan_brain_fringe_free(
        output_dir / "logo_A_ted_red_bg_cyan_brain.png",
        TED_RED_EDGE_RGB,
        issues,
        "logo_A_ted_red",
    ) and _verify_red_bg_cyan_brain_fringe_free(
        output_dir / "logo_A_crimson_studio_bg_cyan_brain.png",
        STUDIO_CRIMSON_EDGE_RGB,
        issues,
        "logo_A_crimson_studio",
    )

    # Dark-void corner & interior seam integrity check
    void_seam_ok = True
    for key in ("logo_A", "logo_A_red", "logo_B", "logo_C", "banner", "banner_red"):
        fpath = output_dir / expected_specs[key][0]
        if fpath.is_file():
            arr = np.array(Image.open(fpath).convert("RGB"))
            corners = np.stack([arr[0, 0], arr[0, -1], arr[-1, 0], arr[-1, -1]])
            max_diff = int(np.max(np.abs(corners.astype(np.int32) - np.array(VOID_RGB, dtype=np.int32))))
            if max_diff > 6:
                issues.append(f"Corner void mismatch on {fpath.name}: max_diff={max_diff}")
                void_seam_ok = False
            if key not in ("banner", "banner_red"):
                band = arr[52:68, 330:470].astype(np.int32)
                if int(np.abs(np.diff(band, axis=1)).max()) > 4 or int(np.abs(np.diff(band, axis=0)).max()) > 4:
                    issues.append(f"Rectangular seam gradient step detected in {fpath.name}")
                    void_seam_ok = False

    final_pair = manifest.get("final_selected_pair") or {}
    jh3_meta = assets_meta.get("banner_jh3_human_element") or {}
    jh3_upload_ver = verified_assets.get("banner_jh3_yt_upload") or {}
    yt_upload_bytes = int(jh3_upload_ver.get("bytes") or 0)
    yt_banner_6mb_safe_ok = (
        jh3_upload_ver.get("mode") == "RGB"
        and jh3_upload_ver.get("size") == f"{BANNER_W}x{BANNER_H}"
        and bool(jh3_upload_ver.get("sha256_match"))
        and 0 < yt_upload_bytes <= YT_BANNER_UPLOAD_MAX_BYTES
        and final_pair.get("banner_upload_key") == "banner_jh3_yt_upload"
        and final_pair.get("banner_upload_path")
        == "BCI_Shorts_Channel/brand_assets/v2_ep31_rebrand/banner_youtube_2560x1440_jh3_yt_upload.jpg"
        and final_pair.get("banner_upload_sha256") == jh3_upload_ver.get("sha256")
        and int(final_pair.get("banner_upload_bytes") or 0) == yt_upload_bytes <= YT_BANNER_UPLOAD_MAX_BYTES
    )
    if not yt_banner_6mb_safe_ok:
        issues.append(
            f"YouTube banner <= {YT_BANNER_UPLOAD_MAX_BYTES} B upload lock failed: bytes={yt_upload_bytes}, pair={final_pair}"
        )

    jh3_copy = jh3_meta.get("copy_slots") or {}
    expected_copy = {
        "eyebrow_text": JH3_FINAL_EYEBROW,
        "signature_text": JH3_FINAL_SIGNATURE,
        "left_notes": [txt for txt, _ in JH3_FINAL_LEFT_NOTES],
        "right_notes": [txt for txt, _ in JH3_FINAL_RIGHT_NOTES],
    }
    copy_blob = json.dumps({"final_pair": final_pair, "jh3_copy": jh3_copy}, ensure_ascii=False).lower()
    final_lock_ok = (
        yt_banner_6mb_safe_ok
        and final_pair.get("avatar_key") == "logo_A_ted_red"
        and final_pair.get("avatar_sha256") == (assets_meta.get("logo_A_ted_red") or {}).get("sha256")
        and final_pair.get("banner_key") == "banner_jh3_human_element"
        and final_pair.get("banner_sha256") == jh3_meta.get("sha256")
        and final_pair.get("preview_sheet_key") == "brand_final_lock_sheet"
        and jh3_copy == expected_copy
        and final_pair.get("copy_slots") == expected_copy
        and not any(bad_t in copy_blob for bad_t in JH3_BANNED_INTERNAL_TERMS)
    )
    if not final_lock_ok:
        issues.append(f"final_selected_pair / JH-3 copy lock validation failed: {final_pair}")

    return {
        "passed": len(issues) == 0,
        "output_dir": str(output_dir),
        "manifest_path": str(manifest_path),
        "sha256_matches": sha_all_match,
        "void_seam_ok": void_seam_ok,
        "logo_a_red_zero_pink_bleed_ok": logo_a_red_zero_pink_bleed_ok,
        "ted_red_zero_navy_fringe_ok": ted_red_zero_navy_fringe_ok,
        "matrix_10slice_banners_ok": matrix_10slice_banners_ok,
        "crimson_echo_banners_ok": crimson_echo_banners_ok,
        "mri_glass_banners_ok": mri_glass_banners_ok,
        "jh5_collection_ok": jh5_collection_ok,
        "jh2_5opts_ok": jh2_5opts_ok,
        "ricks_clips_3opts_ok": ricks_clips_3opts_ok,
        "yt_banner_6mb_safe_ok": yt_banner_6mb_safe_ok,
        "banner_yt_upload_bytes": yt_upload_bytes,
        "final_lock_ok": final_lock_ok,
        "banner_safe_zone_check": banner_safe_zone_check,
        "banner_red_safe_zone_check": banner_red_safe_zone_check,
        "banner_matrix_10slice_A_check": banner_matrix_10slice_a_check,
        "banner_matrix_10slice_B_check": banner_matrix_10slice_b_check,
        "banner_crimson_echo_A_check": banner_crimson_echo_a_check,
        "banner_crimson_echo_B_check": banner_crimson_echo_b_check,
        "banner_mri_glass_A_check": banner_mri_glass_a_check,
        "banner_mri_glass_B_check": banner_mri_glass_b_check,
        "banner_jh5_checks": banner_jh5_checks,
        "banner_jh2_5opts_checks": banner_jh2_5opts_checks,
        "banner_ricks_clips_checks": banner_ricks_clips_checks,
        "assets": verified_assets,
        "issues": issues,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build & verify ALL ABOUT BRAIN Ep #31 brand identity pack.")
    parser.add_argument("--check", action="store_true", help="Read-only verification outputting JSON.")
    parser.add_argument("--out-dir", type=Path, default=OUTPUT_DIR, help="Output directory override.")
    parser.add_argument(
        "--finish-jh-banner",
        type=Path,
        default=None,
        help="Apply Johnny Harris 35mm cinema finish + ALL ABOUT BRAIN typography to a 16:9 backdrop PNG.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Output 2560x1440 PNG path when using --finish-jh-banner.",
    )
    parser.add_argument(
        "--notes",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Enable/disable Caveat handwritten field notes on outer desktop wings (--notes / --no-notes).",
    )
    args = parser.parse_args(argv)

    if args.finish_jh_banner is not None:
        out_path = args.out or args.finish_jh_banner.with_name(f"{args.finish_jh_banner.stem}_jh_2560x1440.png")
        res = finish_jh_banner_image(args.finish_jh_banner, out_path, with_notes=bool(args.notes))
        print(json.dumps(res, indent=2))
        return 0

    if args.check:
        report = check_pack(args.out_dir)
        print(json.dumps(report, indent=2))
        return 0 if report.get("passed") else 1

    build_pack(args.out_dir)
    report = check_pack(args.out_dir)
    print(json.dumps(report, indent=2))
    return 0 if report.get("passed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
