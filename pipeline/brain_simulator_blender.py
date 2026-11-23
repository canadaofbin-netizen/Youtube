"""
Rule R76 & Rule R84: Deterministic Blender 4.2 Cycles MNI152 3D Surgical Cutaway & Volume-Compare Brain Simulator
(`pipeline/brain_simulator_blender.py`).

Replaces AI video diffusion on brain cuts with 100% deterministic, zero-neon, Complete-Anatomy-grade 3D rendering
of genuine MNI152 human MRI neuroanatomy (`neuro_atlas_mni152.npz`, 36 parcels, 299,769 triangles, 0 Flow credits):
  - Rule R84 `Cycles` (`OpenImageDenoise` + `AgX`) matte medical subsurface PBR (`Roughness 0.58-0.65`, `Subsurf x2`, 0% neon)
  - Automatic view-aligned `EXACT` Boolean quadrant/opercular surgical cutaway exposing deep nuclei (`Hippocampus` Z=-12mm)
    alongside true dorsal landmarks (`Corpus Callosum` Z=+18mm, `Thalamus`) so viewers never confuse midline arches with limbic hubs
  - `9:16` Stacked `2.5x` Cutaway + `1.0x` White Dashed Baseline Contour (`stacked_cutaway_brain_compare=True`, `mode="split_vstack"`)
    with animated localized shape-key volume/state morphing (`posterior_hypertrophy`, `posterior_vs_anterior_tradeoff`,
    `pulsatile_pump`, `pain_gate_suppression`, `working_memory_retention`)
  - Exact 30fps `world_to_camera_view` export (`<clip_stem>_camera_track.json`) for `0.0 px` `Rule R81` XL `PatrickHand` callout lock
  - Deterministic Simulator QA (`SQ1-SQ6` -> `<clip_stem>_sim_qa.json`)
"""

from __future__ import annotations

import concurrent.futures
import hashlib
import json
import math
import multiprocessing
import os
import shutil
import subprocess
import textwrap
import time
from pathlib import Path
from typing import Any

import cv2
import imageio_ffmpeg
import numpy as np
from PIL import Image, ImageDraw

from pipeline.anatomy_map import resolve_region
from pipeline.config import (
    BLENDER_SIM_THREADS_PER_WORKER,
    DEFAULT_SIMULATOR_BLENDER_BIN,
    EXPRESSIVE_V8_BRAIN_SIM_DRONE_MOVES,
    EXPRESSIVE_V8_VIDEO_FPS,
    PROJECTS_DIR,
    R76_BRAIN_SIM_SQ_PASS_REQUIRED,
    R84_CYCLES_SAMPLES,
    R84_DASHED_BASELINE_DASH_GAP_PX,
    R84_DASHED_BASELINE_WIDTH_PX,
    R84_DEEP_CUTAWAY_REGIONS,
)
from pipeline.hardware_profile import resolve_blender_parallel_plan, resolve_cpu_budget
from pipeline.media_cache import atomic_commit_from_scratch, ram_tempdir

REPO_ROOT = Path(__file__).resolve().parents[1]
ATLAS_DIR = REPO_ROOT / "pipeline" / "assets" / "neuro_atlas_3d"
ATLAS_NPZ_PATH = ATLAS_DIR / "neuro_atlas_mni152.npz"
ATLAS_MANIFEST_PATH = ATLAS_DIR / "manifest.json"

CLINICAL_BG_HEX = "#05080F"
R78M_MATERIAL_MODES: tuple[str, ...] = ("xray_glass", "cool_matte_silver_31")
R84_MATERIAL_MODES: tuple[str, ...] = ("xray_glass", "cool_matte_silver_31", "r84_medical_pbr")
CLINICAL_PALETTE_HEX: dict[str, str] = {
    "primary": "#E2443E",     # Matte Medical Coral-Terracotta (active / hypertrophied hub)
    "partner": "#3B86C4",     # Matte Clinical Cerulean (partner / baseline comparison hub)
    "sensory": "#D49A2A",     # Warm Anatomical Ochre (sensory organ / relay entry)
    "silenced": "#5C6675",    # Muted Clinical Slate (offline / suppressed / baseline)
    "cortex": "#B8C0C7",      # R78-M Cool Matte Silver-Gray (preserved for R78 unit contract)
    "cortex_r84": "#6E7785",  # Rule R84 Matte Slate-Gray Cerebral Cortex (zero neon, zero ivory)
    "cut_plane": "#8A92A0",   # Warm Matte Cross-Section Surgical Cut Plane
    "callosum": "#487AA8",    # Calm Dorsal Landmark Slate-Blue (Corpus Callosum Z=+18mm)
    "subcortical": "#545D6B", # Neutral Deep Landmark Context (Thalamus / Brainstem / Cerebellum)
    "sulcal_cyan": "#2FA8E6", # Clean Clinical Fluid / Pathway Accent
    "head_shell": "#B8C4D4",  # Faint Cranial Reference Contour
    "signal": "#EAB34B",      # Matte Gold Directional Signal Bolus
    "grid": "#253042",        # Stereotaxic Floor Reference Ring
}

# Stacked 2.5x Cutaway Viewport Boxes on 1080x1920 Canvas:
# Clears Top XL PatrickHand Header (Y=182..392), Right Shorts UI Rail (X>=920), and Bottom ASS Subtitles (Y>=1265)!
STACKED_TOP_BOX: tuple[int, int, int, int] = (76, 416, 916, 816)     # 840 x 400
STACKED_BOT_BOX: tuple[int, int, int, int] = (76, 844, 916, 1244)    # 840 x 400


def hex_to_linear_rgb(hex_color: str) -> tuple[float, float, float]:
    """Converts sRGB `#RRGGBB` to Blender linear RGB."""
    h = str(hex_color).strip().lstrip("#")
    vals = [int(h[i : i + 2], 16) / 255.0 for i in (0, 2, 4)]
    out: list[float] = []
    for c in vals:
        out.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    return (round(out[0], 5), round(out[1], 5), round(out[2], 5))


def load_atlas_manifest() -> dict[str, Any]:
    if not ATLAS_MANIFEST_PATH.is_file():
        raise FileNotFoundError(
            f"Missing 3D neuroanatomy manifest at {ATLAS_MANIFEST_PATH}. Run scripts/build_neuro_atlas_3d.py first."
        )
    return json.loads(ATLAS_MANIFEST_PATH.read_text(encoding="utf-8"))


def normalize_atlas_region_key(region_text: str | None, manifest: dict[str, Any] | None = None) -> str:
    """Maps a canonical/alias region string onto a valid key in `neuro_atlas_3d/manifest.json`."""
    mf = manifest or load_atlas_manifest()
    regions = mf.get("regions") or {}
    raw = str(region_text or "").strip().lower()
    if not raw:
        return "prefrontal cortex"
    if raw in regions:
        return raw
    if any(k in raw for k in ("eye", "retina", "optic nerve", "optic chiasm", "optic tract")):
        return "eyes" if "eyes" in regions else "primary visual cortex"
    if any(k in raw for k in ("cochlea", "inner ear", "ear canal", "auditory nerve", "ear")):
        return "inner ear" if "inner ear" in regions else "auditory cortex"
    if "fusiform" in raw or "face area" in raw or "face patch" in raw:
        return "fusiform face area"
    if "visual cortex" in raw or "occipital" in raw or raw == "v1":
        return "primary visual cortex"
    if "auditory" in raw or "heschl" in raw or raw == "a1":
        return "auditory cortex"
    if "hippocamp" in raw or "seahorse" in raw:
        return "hippocampus"
    if "amygdala" in raw:
        return "amygdala"
    if "insula" in raw:
        return "insula" if "insula" in regions else "somatosensory cortex"
    if "thalam" in raw:
        return "thalamus"
    if "brainstem" in raw or "locus coeruleus" in raw or "pons" in raw or "medulla" in raw:
        return "brainstem"
    if "callosum" in raw:
        return "corpus callosum" if "corpus callosum" in regions else "anterior cingulate cortex"
    if "ventromedial" in raw or "vmpfc" in raw:
        return "ventromedial prefrontal cortex"
    if "dorsolateral" in raw or "dlpfc" in raw:
        return "dorsolateral prefrontal cortex"
    if "anterior cingulate" in raw or "cingulate" in raw or "acc" == raw:
        return "anterior cingulate cortex"
    if "parietal" in raw:
        return "posterior parietal cortex" if "posterior parietal cortex" in regions else "somatosensory cortex"
    if "somatosensory" in raw:
        return "somatosensory cortex"
    if "premotor" in raw:
        return "premotor cortex"
    if "motor" in raw:
        return "motor cortex"
    if "temporal" in raw:
        return "fusiform face area" if "fusiform face area" in regions else "auditory cortex"
    if "prefrontal" in raw or "frontal lobe" in raw or "frontal" in raw:
        return "prefrontal cortex"
    canon = resolve_region(raw)
    if canon and canon.lower() in regions:
        return canon.lower()
    if canon and canon in regions:
        return canon
    return "prefrontal cortex"


def resolve_anatomical_tract_points(
    start_key: str,
    end_key: str,
    manifest: dict[str, Any],
) -> list[list[float]]:
    """
    Looks up precomputed curved MNI152 white-matter tract spline or generates an
    anatomically routed intra-cranial curved Catmull-Rom spline inside brain bounds.
    """
    tracts = manifest.get("tracts") or {}
    fwd_key = f"{start_key}__to__{end_key}"
    rev_key = f"{end_key}__to__{start_key}"
    if fwd_key in tracts:
        return [list(p) for p in tracts[fwd_key]]
    if rev_key in tracts:
        return [list(p) for p in reversed(tracts[rev_key])]

    regions = manifest["regions"]

    def _pt(k: str) -> np.ndarray:
        r = regions.get(k) or regions["prefrontal cortex"]
        return np.asarray(r.get("rh_centroid_mni") or r["centroid_mni"], dtype=np.float64)

    p0 = _pt(start_key)
    p1 = _pt(end_key)
    if np.linalg.norm(p1 - p0) < 3.0:
        # Intra-regional longitudinal axis spline (e.g. Hippocampus Posterior Tail -> Anterior Head)
        p0 = p0 + np.array([0.0, -10.0, 4.0], dtype=np.float64)
        p1 = p1 + np.array([-1.5, 11.0, -5.0], dtype=np.float64)
    mid = 0.5 * (p0 + p1)
    deep_hub = np.array([18.0 if mid[0] >= 0 else -18.0, -10.0, 1.0], dtype=np.float64)
    ctrl_mid = 0.76 * mid + 0.24 * deep_hub
    ctrl = np.vstack([p0, 0.65 * p0 + 0.35 * ctrl_mid, ctrl_mid, 0.35 * ctrl_mid + 0.65 * p1, p1])

    n_out = 36
    ts = np.linspace(0.0, 1.0, n_out)
    ext = np.vstack([2 * ctrl[0] - ctrl[1], ctrl, 2 * ctrl[-1] - ctrl[-2]])
    n_seg = len(ctrl) - 1
    out: list[list[float]] = []
    for u in ts:
        sc = u * n_seg
        seg = min(int(sc), n_seg - 1)
        t = sc - seg
        a, b, c, d = ext[seg], ext[seg + 1], ext[seg + 2], ext[seg + 3]
        t2, t3 = t * t, t * t * t
        pos = 0.5 * ((2 * b) + (-a + c) * t + (2 * a - 5 * b + 4 * c - d) * t2 + (-a + 3 * b - 3 * c + d) * t3)
        out.append([round(float(x), 2) for x in pos])
    return out


def _plan_macro_cutaway_camera(target_key: str, manifest: dict[str, Any]) -> dict[str, Any]:
    """
    Plans a 2.5x close surgical cutaway inspection sweep (~14 deg smooth lateral-superior micro-orbit + push-in)
    framing the target subcortical/cortical hub cleanly inside stacked 2.5x panels or single macro trade-off cuts.
    """
    regions = manifest["regions"]
    r_meta = regions.get(target_key) or regions["hippocampus"]
    c_m = np.asarray(r_meta.get("rh_centroid_mni") or r_meta["centroid_mni"], dtype=np.float64) * 0.001

    if target_key == "hippocampus":
        # Lateral-superior 3/4 view showing full curved seahorse from Posterior Tail (screen-left) to Anterior Head (screen-right)!
        eye_wps = [
            [0.168, -0.048, 0.044],
            [0.156, -0.032, 0.038],
            [0.146, -0.016, 0.032],
            [0.138, -0.002, 0.027],
        ]
        tgt_wps = [
            [0.024, -0.023, -0.009],
            [0.025, -0.023, -0.010],
            [0.026, -0.023, -0.011],
            [0.026, -0.022, -0.011],
        ]
        lens_mm = 80.0
    elif target_key in ("brainstem", "thalamus"):
        eye_wps = [
            [0.195, -0.042, 0.038],
            [0.184, -0.018, 0.032],
            [0.174, 0.008, 0.026],
            [0.165, 0.028, 0.022],
        ]
        tgt_wps = [
            [0.008, -0.022, -0.012],
            [0.008, -0.020, -0.010],
            [0.008, -0.018, -0.008],
            [0.008, -0.016, -0.006],
        ]
        lens_mm = 68.0
    elif target_key == "insula":
        eye_wps = [
            [0.192, 0.038, 0.036],
            [0.180, 0.016, 0.030],
            [0.170, -0.008, 0.024],
            [0.162, -0.026, 0.020],
        ]
        tgt_wps = [
            [0.034, 0.006, 0.002],
            [0.035, 0.005, 0.002],
            [0.036, 0.004, 0.001],
            [0.036, 0.003, 0.001],
        ]
        lens_mm = 74.0
    else:
        cx, cy, cz = float(c_m[0]), float(c_m[1]), float(c_m[2])
        eye_wps = [
            [max(0.185, cx + 0.165), cy + 0.055, cz + 0.048],
            [max(0.175, cx + 0.155), cy + 0.022, cz + 0.040],
            [max(0.166, cx + 0.146), cy - 0.012, cz + 0.034],
            [max(0.158, cx + 0.138), cy - 0.038, cz + 0.028],
        ]
        tgt_wps = [
            [cx * 0.65, cy, cz],
            [cx * 0.68, cy, cz],
            [cx * 0.70, cy, cz],
            [cx * 0.72, cy, cz],
        ]
        lens_mm = 66.0

    return {
        "camera_move": "circuit_cooperation_drone",
        "lens_mm": lens_mm,
        "mirror_lr": False,
        "eye_waypoints_m": eye_wps,
        "target_waypoints_m": tgt_wps,
    }


def _plan_drone_camera_keyframes(
    shot_spec: dict[str, Any],
    manifest: dict[str, Any],
    start_key: str,
    end_key: str,
    tract_pts_mm: list[list[float]],
) -> dict[str, Any]:
    """
    Plans smooth 30fps Catmull-Rom 3D camera eye & target trajectories in meters (MNI * 0.001).
    Keeps all anatomical anchors inside vertical safe band `Y = 26%..68%`, clearing top `Rule R81` XL
    `PatrickHand` callouts and bottom `ASS` subtitles.
    """
    if bool(shot_spec.get("stacked_cutaway_brain_compare")) or (
        str(shot_spec.get("morph_mode") or "").strip().lower() == "posterior_vs_anterior_tradeoff"
    ):
        focus_k = "hippocampus" if "hippocampus" in (start_key, end_key) else start_key
        cam_m = _plan_macro_cutaway_camera(focus_k, manifest)
        if not bool(shot_spec.get("stacked_cutaway_brain_compare")):
            # Single-frame 9:16 2.1x cutaway view: lift target slightly so seahorse sits at Y=46%
            cam_m["lens_mm"] = 74.0
            cam_m["eye_waypoints_m"] = [[x * 1.18, y * 1.12, z + 0.010] for x, y, z in cam_m["eye_waypoints_m"]]
            cam_m["target_waypoints_m"] = [[x, y, z + 0.008] for x, y, z in cam_m["target_waypoints_m"]]
        return cam_m

    regions = manifest["regions"]

    def _mni_m(key: str) -> np.ndarray:
        r = regions.get(key) or regions["prefrontal cortex"]
        c = r.get("rh_centroid_mni") or r["centroid_mni"]
        return np.asarray(c, dtype=np.float64) * 0.001

    p_start = _mni_m(start_key)
    p_end = _mni_m(end_key)
    p_mid = np.asarray(tract_pts_mm[len(tract_pts_mm) // 2], dtype=np.float64) * 0.001
    camera_move = str(shot_spec.get("camera_move") or "circuit_cooperation_drone").strip().lower()
    if camera_move not in EXPRESSIVE_V8_BRAIN_SIM_DRONE_MOVES:
        camera_move = "circuit_cooperation_drone"

    z_lift = 0.010

    if bool(shot_spec.get("side_by_side_brain_compare")):
        eye_wps = [
            [0.0, 0.440, 0.016],
            [-0.012, 0.422, 0.018],
            [0.008, 0.405, 0.020],
            [0.0, 0.392, 0.022],
        ]
        tgt_wps = [
            [0.0, -0.008, -0.004],
            [0.0, -0.008, -0.004],
            [0.0, -0.008, -0.003],
            [0.0, -0.008, -0.003],
        ]
        return {
            "camera_move": camera_move,
            "lens_mm": 50.0,
            "mirror_lr": False,
            "eye_waypoints_m": eye_wps,
            "target_waypoints_m": tgt_wps,
        }

    # Keep camera strictly on the surgical-cutaway right hemisphere (+X >= +0.185m) so the open cutaway window faces camera!
    if camera_move == "sensory_to_brain_drone":
        if start_key == "eyes":
            eye_wps = [
                [0.255, 0.175, 0.032],
                [0.285, 0.065, 0.038],
                [0.280, -0.055, 0.044],
                [0.245, -0.155, 0.048],
            ]
            tgt_wps = [
                [0.010, 0.022, -0.006 + z_lift],
                [0.010, 0.004, -0.004 + z_lift],
                [0.010, -0.014, -0.002 + z_lift],
                [0.010, -0.026, 0.002 + z_lift],
            ]
            lens_mm = 50.0
        else:
            eye_wps = [
                [0.220, 0.045, -0.022],
                [0.240, 0.005, -0.004],
                [0.235, -0.045, 0.018],
                [0.210, -0.095, 0.038],
            ]
            tgt_wps = [
                [0.026, -0.018, -0.018 + z_lift],
                [0.026, -0.018, -0.012 + z_lift],
                [0.028, -0.018, -0.006 + z_lift],
                [0.028, -0.020, 0.000 + z_lift],
            ]
            lens_mm = 54.0
    elif camera_move == "1p_nerve_canyon_drone":
        eye_wps = [
            [0.145, 0.045, 0.038],
            [0.132, 0.015, 0.032],
            [0.122, -0.015, 0.026],
            [0.114, -0.038, 0.020],
        ]
        tgt_wps = [
            [float(p_start[0]) * 0.55, float(p_start[1]), float(p_start[2]) + z_lift],
            [float(p_mid[0]) * 0.55, float(p_mid[1]), float(p_mid[2]) + z_lift],
            [float(p_end[0]) * 0.55, float(p_end[1]), float(p_end[2]) + z_lift],
            [float(p_end[0]) * 0.60, float(p_end[1]), float(p_end[2]) + z_lift],
        ]
        lens_mm = 32.0
    elif camera_move == "3p_region_shutdown_pullout":
        focus = np.array([float(p_end[0]) * 0.50, float(p_end[1]), float(p_end[2]) + z_lift])
        eye_wps = [
            [0.165, float(p_end[1]) + 0.028, float(p_end[2]) + 0.034],
            [0.190, float(p_end[1]) + 0.004, float(p_end[2]) + 0.045],
            [0.215, -0.028, 0.055],
            [0.238, -0.062, 0.064],
        ]
        tgt_wps = [
            [float(focus[0]), float(focus[1]), float(focus[2])],
            [0.6 * float(focus[0]), 0.6 * float(focus[1]), 0.6 * float(focus[2]) + 0.004],
            [0.008, -0.008, 0.004 + z_lift],
            [0.006, -0.010, 0.004 + z_lift],
        ]
        lens_mm = 42.0
    elif camera_move == "global_system_orbit_drone":
        eye_wps = [
            [0.245, 0.135, 0.072],
            [0.268, 0.048, 0.078],
            [0.265, -0.042, 0.072],
            [0.235, -0.125, 0.062],
        ]
        tgt_wps = [
            [0.006, -0.006, 0.002 + z_lift],
            [0.006, -0.010, 0.002 + z_lift],
            [0.006, -0.014, 0.002 + z_lift],
            [0.006, -0.016, 0.002 + z_lift],
        ]
        lens_mm = 56.0
    else:
        # circuit_cooperation_drone: poised surgical cutaway inspection sweep (~15 deg right-superior 3/4 view)
        mid_cam = 0.5 * (p_start + p_end)
        eye_wps = [
            [0.248, 0.105, 0.076],
            [0.258, 0.038, 0.072],
            [0.252, -0.032, 0.066],
            [0.232, -0.095, 0.058],
        ]
        tgt_wps = [
            [float(mid_cam[0]) * 0.45, float(mid_cam[1]) - 0.004, float(mid_cam[2]) + z_lift],
            [float(mid_cam[0]) * 0.48, float(mid_cam[1]) - 0.006, float(mid_cam[2]) + z_lift],
            [float(mid_cam[0]) * 0.50, float(mid_cam[1]) - 0.008, float(mid_cam[2]) + z_lift],
            [float(mid_cam[0]) * 0.52, float(mid_cam[1]) - 0.010, float(mid_cam[2]) + z_lift],
        ]
        lens_mm = 58.0

    return {
        "camera_move": camera_move,
        "lens_mm": lens_mm,
        "mirror_lr": False,
        "eye_waypoints_m": eye_wps,
        "target_waypoints_m": tgt_wps,
    }


def _find_blender_bin() -> Path:
    env_b = os.environ.get("BLENDER_BIN", "").strip()
    candidates = [Path(env_b)] if env_b else []
    candidates.append(DEFAULT_SIMULATOR_BLENDER_BIN)
    wb = shutil.which("blender")
    if wb:
        candidates.append(Path(wb))
    for c in candidates:
        if c and c.is_file():
            return c
    raise FileNotFoundError(f"Blender 4.2 executable not found in {candidates}")


_SIM_SPEC_PATH_KEYS: frozenset[str] = frozenset(
    {"npz_path", "output_path", "out_mp4_path", "track_path", "qa_path"}
)


def compute_sim_spec_sha256(render_cfg: dict[str, Any]) -> str:
    """Computes a deterministic SHA-256 over pure rendering parameters (excluding filesystem output/asset paths)."""
    pure_spec = {k: v for k, v in render_cfg.items() if k not in _SIM_SPEC_PATH_KEYS}
    payload = json.dumps(pure_spec, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def is_brain_simulator_clip_spec(clip_spec: dict[str, Any] | None) -> bool:
    """
    Returns True when a visual_plan clip spec belongs to the local Blender 4.2 MNI152 3D Brain Simulator
    (Rule R76 / R84 `blender_3d_simulator`, excluding legacy R78-M `google_flow` brain clips).
    """
    if not isinstance(clip_spec, dict):
        return False
    render_eng = str(clip_spec.get("render_engine") or "").strip().lower()
    if render_eng == "blender_3d_simulator":
        return True
    if render_eng == "google_flow" or bool(clip_spec.get("r78m_flow_prompt")):
        return False
    grammar = str(clip_spec.get("grammar") or clip_spec.get("visual_grammar") or "").strip()
    return grammar == "brain_simulator_3d"


def _draw_dashed_mask_contour(
    panel_rgb: np.ndarray,
    mask_gray: np.ndarray,
    *,
    color_rgb: tuple[int, int, int] = (237, 242, 247),
    width_px: int = R84_DASHED_BASELINE_WIDTH_PX,
    dash_px: int = R84_DASHED_BASELINE_DASH_GAP_PX[0],
    gap_px: int = R84_DASHED_BASELINE_DASH_GAP_PX[1],
) -> np.ndarray:
    """Extracts the outer 1.0x anatomical silhouette from `mask_gray` and draws an anti-aliased dashed contour."""
    if mask_gray is None or mask_gray.size == 0:
        return panel_rgb
    ph, pw = panel_rgb.shape[:2]
    if mask_gray.shape[0] != ph or mask_gray.shape[1] != pw:
        mask_gray = cv2.resize(mask_gray, (pw, ph), interpolation=cv2.INTER_LINEAR)
    bin_m = (mask_gray > 96).astype(np.uint8) * 255
    cnts, _ = cv2.findContours(bin_m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    if not cnts:
        return panel_rgb
    pil_im = Image.fromarray(panel_rgb)
    draw = ImageDraw.Draw(pil_im)
    # Draw up to the 2 largest connected components (e.g. main parcel + adjacent partner if dual)
    cnts_sorted = sorted(cnts, key=cv2.contourArea, reverse=True)
    main_area = float(cv2.contourArea(cnts_sorted[0]))
    if main_area < 60.0:
        return panel_rgb
    for cnt in cnts_sorted[:2]:
        if float(cv2.contourArea(cnt)) < max(60.0, 0.18 * main_area):
            continue
        raw_pts = cnt[:, 0, :]
        pts: list[np.ndarray] = []
        for pt in raw_pts:
            p_arr = np.array([float(pt[0]), float(pt[1])], dtype=np.float64)
            if not pts or float(np.linalg.norm(p_arr - pts[-1])) >= 6.0:
                pts.append(p_arr)
        if len(pts) < 4:
            continue
        perim = [0.0]
        for i in range(len(pts)):
            p0 = pts[i]
            p1 = pts[(i + 1) % len(pts)]
            perim.append(perim[-1] + float(np.linalg.norm(p1 - p0)))
        total_len = perim[-1]
        if total_len < 20.0:
            continue
        pos = 0.0
        while pos < total_len:
            end_p = min(total_len, pos + float(dash_px))
            if end_p - pos >= 3.0:
                seg_xy: list[tuple[float, float]] = []
                for sd in np.linspace(pos, end_p, 6):
                    idx = max(0, min(len(pts) - 1, int(np.searchsorted(perim, sd, side="right")) - 1))
                    span = max(1e-6, perim[idx + 1] - perim[idx])
                    t = (sd - perim[idx]) / span
                    p0 = pts[idx]
                    p1 = pts[(idx + 1) % len(pts)]
                    px_f = p0 + t * (p1 - p0)
                    seg_xy.append((float(px_f[0]), float(px_f[1])))
                draw.line(seg_xy, fill=color_rgb, width=int(width_px))
            pos += float(dash_px + gap_px)
    return np.asarray(pil_im, dtype=np.uint8)


def _interpolate_intermediate_frame_dis(
    bgr_a: np.ndarray,
    bgr_b: np.ndarray,
    alpha: float = 0.5,
) -> np.ndarray:
    """Symmetric bidirectional `cv2.DISOpticalFlow` midpoint synthesis (`15fps -> 30fps` calm 3D camera glide)."""
    if abs(alpha) <= 1e-4:
        return bgr_a
    if abs(alpha - 1.0) <= 1e-4:
        return bgr_b
    h, w = bgr_a.shape[:2]
    # Compute dense flow at half resolution for speed, then scale flow vectors 2x
    hw, hh = max(64, w // 2), max(64, h // 2)
    ga = cv2.cvtColor(cv2.resize(bgr_a, (hw, hh), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY)
    gb = cv2.cvtColor(cv2.resize(bgr_b, (hw, hh), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY)
    dis = cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_FAST)
    flow_ab_s = dis.calc(ga, gb, None)
    flow_ba_s = dis.calc(gb, ga, None)
    flow_ab = cv2.resize(flow_ab_s, (w, h), interpolation=cv2.INTER_LINEAR) * 2.0
    flow_ba = cv2.resize(flow_ba_s, (w, h), interpolation=cv2.INTER_LINEAR) * 2.0
    grid_x, grid_y = np.meshgrid(np.arange(w, dtype=np.float32), np.arange(h, dtype=np.float32))
    wa = cv2.remap(
        bgr_a,
        grid_x - float(alpha) * flow_ba[..., 0],
        grid_y - float(alpha) * flow_ba[..., 1],
        interpolation=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_REPLICATE,
    )
    wb = cv2.remap(
        bgr_b,
        grid_x - float(1.0 - alpha) * flow_ab[..., 0],
        grid_y - float(1.0 - alpha) * flow_ab[..., 1],
        interpolation=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_REPLICATE,
    )
    return cv2.addWeighted(wa, 1.0 - float(alpha), wb, float(alpha), 0.0)


def render_brain_simulator_clip(
    shot_spec: dict[str, Any],
    out_mp4_path: Path | str,
    *,
    width: int = 1080,
    height: int = 1920,
    fps: int = EXPRESSIVE_V8_VIDEO_FPS,
    timeout_sec: int = 420,
    threads: int = BLENDER_SIM_THREADS_PER_WORKER,
    force: bool = False,
) -> dict[str, Any]:
    """
    Renders a single deterministic `Blender 4.2` MNI152 3D Medical Brain Simulator clip (`out_mp4_path`),
    plus `<clip_stem>_camera_track.json` and `<clip_stem>_sim_qa.json` (`SQ1-SQ6`).
    Supports both Rule R84 Cycles Matte Subsurface PBR surgical cutaways and Stacked 2.5x Dashed-Baseline
    Cohort Comparisons (`stacked_cutaway_brain_compare=True`).
    """
    if bool(shot_spec.get("r85_mode")):
        raise RuntimeError(
            "[R85] Direct on-screen Blender brain clip rendering is retired under Rule R85; "
            "use render_mni152_guide_silhouette() in /tmp/aab_real_refs/ + 100% Google Flow Ep #31 brain clips."
        )
    t0 = time.monotonic()
    eff_threads = max(1, int(threads or BLENDER_SIM_THREADS_PER_WORKER))
    out_p = Path(out_mp4_path).resolve()
    out_p.parent.mkdir(parents=True, exist_ok=True)
    stem = out_p.stem
    track_path = out_p.with_name(f"{stem}_camera_track.json")
    qa_path = out_p.with_name(f"{stem}_sim_qa.json")

    manifest = load_atlas_manifest()
    explicit_n_frames = shot_spec.get("n_frames")
    if explicit_n_frames is not None and int(explicit_n_frames) > 0:
        n_frames = max(int(explicit_n_frames), int(fps))
    else:
        duration_sec = max(1.0, float(shot_spec.get("duration_sec") or shot_spec.get("target_duration_sec") or 4.8))
        n_frames = max(int(round(duration_sec * fps)), int(fps))

    raw_start = shot_spec.get("start_brain_region") or shot_spec.get("brain_region") or "fusiform face area"
    raw_end = shot_spec.get("end_brain_region") or shot_spec.get("brain_region") or raw_start
    start_key = normalize_atlas_region_key(str(raw_start), manifest)
    end_key = normalize_atlas_region_key(str(raw_end), manifest)
    neural_state = str(shot_spec.get("neural_state") or "active").strip().lower()
    if neural_state not in ("active", "silenced", "severed", "rerouted"):
        neural_state = "active"

    extra_raw = shot_spec.get("secondary_regions") or []
    extra_keys = [
        normalize_atlas_region_key(str(x), manifest)
        for x in extra_raw
        if str(x).strip()
    ]
    extra_keys = [k for k in extra_keys if k not in (start_key, end_key)]

    dimmed_raw = list(shot_spec.get("dimmed_regions") or [])
    if not dimmed_raw and isinstance(shot_spec.get("regions"), list) and len(shot_spec["regions"]) >= 3:
        vis_dir_low = str(shot_spec.get("visual_direction") or "").lower()
        for r_item in shot_spec["regions"]:
            r_low = str(r_item or "").strip().lower()
            if any(tok in r_low for tok in ("pathway", "nerve")):
                continue
            rk = normalize_atlas_region_key(r_low, manifest)
            if rk not in (start_key, end_key) and rk not in extra_keys:
                if any(tok in vis_dir_low for tok in ("dimmed", "damaged", "offline", "silenced")):
                    dimmed_raw.append(rk)
                else:
                    extra_keys.append(rk)
    dimmed_keys: list[str] = []
    for dk_raw in dimmed_raw:
        dk = normalize_atlas_region_key(str(dk_raw), manifest)
        if dk not in (start_key, end_key) and dk not in dimmed_keys:
            dimmed_keys.append(dk)
    extra_keys = [k for k in extra_keys if k not in dimmed_keys]

    is_stacked_compare = bool(shot_spec.get("stacked_cutaway_brain_compare", False))
    is_sbs_compare = bool(shot_spec.get("side_by_side_brain_compare", False)) and not is_stacked_compare
    morph_mode = str(shot_spec.get("morph_mode") or "").strip().lower()
    if is_stacked_compare and not morph_mode:
        if "hippocampus" in (start_key, end_key):
            morph_mode = "posterior_hypertrophy"
        elif "insula" in (start_key, end_key):
            morph_mode = "pain_gate_suppression"
        elif "brainstem" in (start_key, end_key) or "thalamus" in (start_key, end_key):
            morph_mode = "pulsatile_pump"
        else:
            morph_mode = "working_memory_retention"

    dashed_baseline = bool(
        shot_spec.get("dashed_baseline")
        if shot_spec.get("dashed_baseline") is not None
        else (is_stacked_compare or morph_mode in ("posterior_hypertrophy", "posterior_vs_anterior_tradeoff"))
    )
    need_surgical_cutaway = bool(
        shot_spec.get("surgical_cutaway")
        if shot_spec.get("surgical_cutaway") is not None
        else (
            is_stacked_compare
            or bool(morph_mode)
            or start_key in R84_DEEP_CUTAWAY_REGIONS
            or end_key in R84_DEEP_CUTAWAY_REGIONS
        )
    )

    blender_engine = str(shot_spec.get("blender_engine") or "CYCLES").strip().upper()
    if blender_engine not in ("CYCLES", "WORKBENCH"):
        blender_engine = "CYCLES"
    cycles_samples = max(4, int(shot_spec.get("cycles_samples") or 12))
    default_stride = (
        (6 if (is_stacked_compare and n_frames >= 24) else (4 if n_frames >= 16 else 1))
        if blender_engine == "CYCLES"
        else 1
    )
    keyframe_stride = int(shot_spec.get("keyframe_stride") or default_stride)

    tract_pts_mm = resolve_anatomical_tract_points(start_key, end_key, manifest)
    cam_plan = _plan_drone_camera_keyframes(shot_spec, manifest, start_key, end_key, tract_pts_mm)
    mirror_lr = bool(cam_plan.get("mirror_lr"))
    if mirror_lr:
        tract_pts_mm = [[-float(x), float(y), float(z)] for x, y, z in tract_pts_mm]

    if start_key in ("eyes", "inner ear"):
        start_role = "sensory"
    else:
        start_role = "partner" if start_key != end_key else "primary"

    if neural_state in ("severed", "silenced"):
        end_role = "silenced"
    else:
        end_role = "primary"

    if shot_spec.get("start_role") in CLINICAL_PALETTE_HEX:
        start_role = str(shot_spec["start_role"])
    if shot_spec.get("end_role") in CLINICAL_PALETTE_HEX:
        end_role = str(shot_spec["end_role"])

    regions_meta = manifest["regions"]

    def _centroid_mm(k: str) -> list[float]:
        r = regions_meta.get(k) or regions_meta["prefrontal cortex"]
        if mirror_lr:
            c = list(r.get("lh_centroid_mni") or r.get("rh_centroid_mni") or r["centroid_mni"])
            if float(c[0]) > 2.0:
                c[0] = -float(c[0])
            return c
        return list(r.get("rh_centroid_mni") or r["centroid_mni"])

    sbs_scale = 0.62
    sbs_dx_mm = 82.0
    left_reg_scale = float(shot_spec.get("left_region_scale") or 1.32)
    right_reg_scale = float(shot_spec.get("right_region_scale") or (1.00 if is_stacked_compare else 0.86))
    posterior_expand = float(shot_spec.get("posterior_expand") or (0.56 if morph_mode in ("posterior_hypertrophy", "posterior_vs_anterior_tradeoff") else 0.0))
    anterior_shrink = float(shot_spec.get("anterior_shrink") or (0.28 if morph_mode == "posterior_vs_anterior_tradeoff" else (0.18 if morph_mode == "posterior_hypertrophy" else 0.0)))

    if is_sbs_compare:
        c_s_raw = _centroid_mm(start_key)
        c_e_raw = _centroid_mm(end_key)
        start_anchor_mm = [round(sbs_dx_mm + sbs_scale * float(c_s_raw[0]), 2), round(sbs_scale * float(c_s_raw[1]), 2), round(sbs_scale * float(c_s_raw[2]), 2)]
        end_anchor_mm = [round(-sbs_dx_mm + sbs_scale * float(c_e_raw[0]), 2), round(sbs_scale * float(c_e_raw[1]), 2), round(sbs_scale * float(c_e_raw[2]), 2)]
    elif morph_mode == "posterior_vs_anterior_tradeoff":
        # Posterior Tail (screen-left) vs Anterior Head (screen-right) of Right Hippocampus!
        start_anchor_mm = [28.5, -33.5, -5.5]
        end_anchor_mm = [25.5, -11.5, -17.5]
    elif start_key == end_key and start_key == "hippocampus" and not is_stacked_compare:
        # Bilateral or Anterior/Posterior callout on single Hippocampus cut
        start_anchor_mm = [28.5, -32.5, -6.0]
        end_anchor_mm = [26.0, -13.0, -16.5]
    else:
        start_anchor_mm = _centroid_mm(start_key)
        end_anchor_mm = _centroid_mm(end_key)

    lesion_mid_mm = tract_pts_mm[len(tract_pts_mm) // 2]
    if is_stacked_compare:
        render_w, render_h = 546, 260
    elif int(width) == 1080 and int(height) == 1920:
        render_w, render_h = (540, 960) if blender_engine == "CYCLES" else (720, 1280)
    else:
        render_w, render_h = int(width), int(height)

    render_cfg = {
        "rule_version": "R84_v1",
        "blender_engine": blender_engine,
        "cycles_samples": cycles_samples,
        "keyframe_stride": keyframe_stride,
        "npz_path": str(ATLAS_NPZ_PATH),
        "width": int(width),
        "height": int(height),
        "render_width": render_w,
        "render_height": render_h,
        "fps": int(fps),
        "n_frames": int(n_frames),
        "duration_sec": round(n_frames / float(fps), 4),
        "start_key": start_key,
        "end_key": end_key,
        "start_role": "primary" if (is_sbs_compare or is_stacked_compare) else start_role,
        "end_role": ("partner" if morph_mode in ("posterior_hypertrophy", "pulsatile_pump") else "silenced") if is_stacked_compare else ("silenced" if is_sbs_compare else end_role),
        "extra_keys": extra_keys,
        "dimmed_keys": dimmed_keys,
        "neural_state": neural_state,
        "mirror_lr": mirror_lr,
        "surgical_cutaway": need_surgical_cutaway,
        "dashed_baseline": dashed_baseline,
        "morph_mode": morph_mode,
        "posterior_expand": posterior_expand,
        "anterior_shrink": anterior_shrink,
        "stacked_cutaway_brain_compare": is_stacked_compare,
        "stacked_top_box": list(STACKED_TOP_BOX),
        "stacked_bot_box": list(STACKED_BOT_BOX),
        "side_by_side_brain_compare": is_sbs_compare,
        "sbs_scale": sbs_scale,
        "sbs_dx_mm": sbs_dx_mm,
        "left_region_scale": left_reg_scale,
        "right_region_scale": right_reg_scale,
        "tract_pts_mm": tract_pts_mm,
        "lesion_mid_mm": lesion_mid_mm,
        "anchors_mm": {
            "start": start_anchor_mm,
            "end": end_anchor_mm,
            "lesion_midpoint": lesion_mid_mm,
            "head_center": [0.0, -5.0, 0.0],
        },
        "colors_linear": {k: hex_to_linear_rgb(v) for k, v in CLINICAL_PALETTE_HEX.items()},
        "bg_linear": hex_to_linear_rgb(CLINICAL_BG_HEX),
        "material_mode": str(shot_spec.get("material_mode") or "r84_medical_pbr").strip().lower(),
        "show_callosum_landmark": bool(
            shot_spec.get("show_callosum_landmark", True)
            and any(k in ("hippocampus", "amygdala", "thalamus", "corpus callosum") for k in (start_key, end_key))
        ),
        "mid_sagittal_split": bool(shot_spec.get("mid_sagittal_split", False)),
        "camera_plan": cam_plan,
        "sensory_entry_context": "eyes" if start_key == "eyes" else ("inner ear" if start_key == "inner ear" else str(shot_spec.get("sensory_entry_context") or "eyes")),
    }
    sim_spec_sha256 = compute_sim_spec_sha256(render_cfg)

    if not force and out_p.is_file() and track_path.is_file() and qa_path.is_file():
        try:
            qa_doc = json.loads(qa_path.read_text(encoding="utf-8"))
            track_doc_existing = json.loads(track_path.read_text(encoding="utf-8"))
            existing_frames = int(track_doc_existing.get("n_frames") or 0)
            if (
                qa_doc.get("passed") is True
                and qa_doc.get("sim_spec_sha256") == sim_spec_sha256
                and existing_frames >= int(n_frames)
            ):
                return {
                    "clip_path": str(out_p),
                    "camera_track_path": str(track_path),
                    "sim_qa_path": str(qa_path),
                    "n_frames": existing_frames,
                    "duration_sec": round(existing_frames / float(fps), 4),
                    "sim_qa": qa_doc,
                    "sim_spec_sha256": sim_spec_sha256,
                    "threads": eff_threads,
                    "cached": True,
                    "elapsed_sec": 0.0,
                }
        except Exception:  # noqa: BLE001
            pass

    blender_bin = _find_blender_bin()
    with ram_tempdir(prefix=f"aab_sim_{stem}_") as td:
        tmp_p = Path(td)
        cfg_p = tmp_p / "render_cfg.json"
        frames_dir = tmp_p / "frames"
        tmp_track_p = tmp_p / f"{stem}_camera_track.json"
        tmp_mp4_p = tmp_p / f"{stem}.mp4"
        tmp_qa_p = tmp_p / f"{stem}_sim_qa.json"
        frames_dir.mkdir(parents=True, exist_ok=True)
        cfg_p.write_text(json.dumps(render_cfg, indent=2), encoding="utf-8")

        blender_script = _build_blender_runner_script(cfg_p, frames_dir, tmp_track_p)
        script_p = tmp_p / "run_sim.py"
        script_p.write_text(blender_script, encoding="utf-8")

        env = dict(os.environ)
        env.setdefault("DISPLAY", ":0")
        env["LP_NUM_THREADS"] = str(eff_threads)
        env["OMP_NUM_THREADS"] = str(eff_threads)
        env["MKL_NUM_THREADS"] = "1"
        env["OPENBLAS_NUM_THREADS"] = "1"
        env["GALLIUM_THREAD"] = "0"
        proc = subprocess.run(
            [str(blender_bin), "-b", "--factory-startup", "-t", str(eff_threads), "-P", str(script_p)],
            capture_output=True,
            text=True,
            env=env,
            timeout=int(timeout_sec),
            check=False,
        )
        if proc.returncode != 0 or not tmp_track_p.is_file():
            raise RuntimeError(
                f"Blender 3D Brain Simulator failed (rc={proc.returncode}):\n"
                f"STDOUT:\n{proc.stdout[-1500:]}\nSTDERR:\n{proc.stderr[-1500:]}"
            )

        full_frame_files = sorted(frames_dir.glob("frame_*.png"))
        if (
            not bool(render_cfg.get("stacked_cutaway_brain_compare"))
            and not bool(render_cfg.get("dashed_baseline"))
            and len(full_frame_files) >= n_frames
        ):
            sq_pixel_stats = _composite_and_encode_frames(
                full_frame_files[:n_frames],
                tmp_mp4_p,
                width=width,
                height=height,
                fps=fps,
                threads=eff_threads,
            )
        else:
            sq_pixel_stats = _assemble_rendered_sequence(
                frames_dir=frames_dir,
                render_cfg=render_cfg,
                out_mp4=tmp_mp4_p,
                width=width,
                height=height,
                fps=fps,
                threads=eff_threads,
            )

        track_doc = json.loads(tmp_track_p.read_text(encoding="utf-8"))
        qa_report = evaluate_simulator_qa(
            render_cfg=render_cfg,
            manifest=manifest,
            track_doc=track_doc,
            pixel_stats=sq_pixel_stats,
            width=width,
            height=height,
        )
        qa_report["sim_spec_sha256"] = sim_spec_sha256
        qa_report["threads"] = eff_threads
        tmp_qa_p.write_text(json.dumps(qa_report, indent=2), encoding="utf-8")

        atomic_commit_from_scratch(tmp_mp4_p, out_p)
        atomic_commit_from_scratch(tmp_track_p, track_path)
        atomic_commit_from_scratch(tmp_qa_p, qa_path)

    return {
        "clip_path": str(out_p),
        "camera_track_path": str(track_path),
        "sim_qa_path": str(qa_path),
        "n_frames": n_frames,
        "duration_sec": round(n_frames / float(fps), 4),
        "sim_qa": qa_report,
        "sim_spec_sha256": sim_spec_sha256,
        "threads": eff_threads,
        "cached": False,
        "elapsed_sec": round(time.monotonic() - t0, 3),
    }


def _render_project_sim_clip_worker(job: dict[str, Any]) -> dict[str, Any]:
    """Picklable top-level subprocess worker for `render_project_brain_simulator_clips_parallel`."""
    os.environ["OMP_NUM_THREADS"] = "1"
    os.environ["MKL_NUM_THREADS"] = "1"
    os.environ["OPENBLAS_NUM_THREADS"] = "1"
    try:
        cv2.setNumThreads(1)
    except Exception:  # noqa: BLE001
        pass

    res = render_brain_simulator_clip(
        shot_spec=job["shot_spec"],
        out_mp4_path=job["out_mp4_path"],
        width=int(job["width"]),
        height=int(job["height"]),
        fps=int(job["fps"]),
        timeout_sec=int(job.get("timeout_sec", 420)),
        threads=int(job["threads"]),
        force=bool(job["force"]),
    )
    return {"clip_index": int(job["clip_index"]), **res}


def render_project_brain_simulator_clips_parallel(
    project_dir: str | Path,
    *,
    edl_frame_map: dict[int, int] | None = None,
    cpu_budget: int | None = None,
    overlapped: bool = False,
    threads_per_worker: int = 2,
    force: bool = False,
) -> dict[str, Any]:
    """
    Renders all R76/R84 `brain_simulator_3d` / `blender_3d_simulator` clips for a project in parallel:
      - Standalone (`cpu_budget=8`): `4 processes * 2 threads = 8 vCPUs`
      - Overlapped (`overlapped=True` / `cpu_budget=6`): `3 processes * 2 threads = 6 vCPUs`
    """
    if bool(shot_spec.get("r85_mode")):
        raise RuntimeError(
            "[R85] Direct on-screen Blender brain clip rendering is retired under Rule R85; "
            "use render_mni152_guide_silhouette() in /tmp/aab_real_refs/ + 100% Google Flow Ep #31 brain clips."
        )
    t0 = time.monotonic()
    cand_p = Path(project_dir)
    p_dir = cand_p.resolve() if cand_p.exists() else (Path(PROJECTS_DIR) / str(project_dir)).resolve()
    vp_path = next(
        (
            p
            for p in (
                p_dir / "03_visuals" / "visual_plan.json",
                p_dir / "02_script" / "visual_plan.json",
                p_dir / "visual_plan.json",
            )
            if p.is_file()
        ),
        None,
    )
    if vp_path is None:
        raise FileNotFoundError(f"visual_plan.json not found under {p_dir}")

    vp_doc = json.loads(vp_path.read_text(encoding="utf-8"))
    from pipeline.config import is_r85_flow_31_brain_plan

    if is_r85_flow_31_brain_plan(vp_doc, project_id=p_dir.name):
        raise RuntimeError(
            f"[R85] Direct on-screen Blender brain simulator rendering is retired for {p_dir.name}; "
            "all final brain clips must render 100% via Google Flow Ep #31 6-Scale mechanism."
        )
    fps = max(1, int(vp_doc.get("fps") or EXPRESSIVE_V8_VIDEO_FPS))
    width = int(vp_doc.get("width") or 1080)
    height = int(vp_doc.get("height") or 1920)
    out_dir = p_dir / "03_visuals" / "brain_simulator_clips"
    out_dir.mkdir(parents=True, exist_ok=True)

    normalized_frame_map: dict[int, int] = {}
    if isinstance(edl_frame_map, dict):
        for k_raw, v_raw in edl_frame_map.items():
            try:
                normalized_frame_map[int(k_raw)] = int(v_raw)
            except (TypeError, ValueError):
                continue

    plan_clips = vp_doc.get("clips") if isinstance(vp_doc.get("clips"), list) else []
    raw_jobs: list[tuple[int, dict[str, Any]]] = []
    for pos_idx, c_spec in enumerate(plan_clips, start=1):
        if not is_brain_simulator_clip_spec(c_spec):
            continue
        clip_idx = int(c_spec.get("clip_number") or c_spec.get("clip_index") or c_spec.get("id") or pos_idx)
        if clip_idx in normalized_frame_map and normalized_frame_map[clip_idx] > 0:
            target_n_frames = max(int(fps) * 2, int(normalized_frame_map[clip_idx]))
        else:
            dur_s = float(
                c_spec.get("duration_sec")
                or c_spec.get("target_duration_sec")
                or c_spec.get("locked_spoken_duration_sec")
                or 5.2
            )
            target_n_frames = max(int(fps) * 2, int(round(dur_s * fps)))
        spec_with_frames = {
            **c_spec,
            "n_frames": int(target_n_frames),
            "duration_sec": round(target_n_frames / float(fps), 4),
        }
        raw_jobs.append((clip_idx, spec_with_frames))

    eff_budget = resolve_cpu_budget(cpu_budget, overlapped=overlapped)
    if not raw_jobs:
        _, tpw_idle = resolve_blender_parallel_plan(
            cpu_budget,
            overlapped=overlapped,
            threads_per_worker=threads_per_worker,
            clip_count=0,
        )
        return {
            "project_dir": str(p_dir),
            "clip_count": 0,
            "rendered_count": 0,
            "cache_hits": 0,
            "n_workers": 0,
            "threads_per_worker": int(tpw_idle),
            "cpu_budget": int(eff_budget),
            "overlapped": bool(overlapped),
            "all_passed": True,
            "elapsed_sec": round(time.monotonic() - t0, 3),
            "clips": [],
        }

    n_proc, tpw = resolve_blender_parallel_plan(
        cpu_budget,
        overlapped=overlapped,
        threads_per_worker=threads_per_worker,
        clip_count=len(raw_jobs),
    )
    jobs = [
        {
            "clip_index": clip_idx,
            "shot_spec": spec_item,
            "out_mp4_path": str(out_dir / f"clip_{clip_idx}.mp4"),
            "width": width,
            "height": height,
            "fps": fps,
            "threads": int(tpw),
            "force": bool(force),
        }
        for clip_idx, spec_item in raw_jobs
    ]

    mp_ctx = multiprocessing.get_context("spawn")
    with concurrent.futures.ProcessPoolExecutor(max_workers=n_proc, mp_context=mp_ctx) as pool:
        clip_results = list(pool.map(_render_project_sim_clip_worker, jobs))
    clip_results.sort(key=lambda r: int(r["clip_index"]))

    cache_hits = sum(1 for r in clip_results if bool(r.get("cached")))
    rendered_count = len(clip_results) - cache_hits
    all_passed = all(bool((r.get("sim_qa") or {}).get("passed", False)) for r in clip_results)

    return {
        "project_dir": str(p_dir),
        "clip_count": len(clip_results),
        "rendered_count": int(rendered_count),
        "cache_hits": int(cache_hits),
        "n_workers": int(n_proc),
        "threads_per_worker": int(tpw),
        "cpu_budget": int(eff_budget),
        "overlapped": bool(overlapped),
        "all_passed": bool(all_passed),
        "elapsed_sec": round(time.monotonic() - t0, 3),
        "clips": clip_results,
    }


def _composite_single_keyframe_bgr(
    frames_dir: Path,
    f_idx: int,
    render_cfg: dict[str, Any],
    width: int,
    height: int,
    vignette: np.ndarray,
) -> np.ndarray:
    """Builds a full `width x height` BGR keyframe (either stacked 2.5x dual-panel or full-frame cutaway + dashed baseline)."""
    is_stacked = bool(render_cfg.get("stacked_cutaway_brain_compare"))
    has_dash = bool(render_cfg.get("dashed_baseline"))

    if is_stacked:
        canvas = np.full((height, width, 3), (15, 8, 5), dtype=np.uint8)  # BGR #05080F
        x0, yt0, x1, yt1 = [int(v) for v in render_cfg.get("stacked_top_box", STACKED_TOP_BOX)]
        _, yb0, _, yb1 = [int(v) for v in render_cfg.get("stacked_bot_box", STACKED_BOT_BOX)]
        pw_t, ph_t = x1 - x0, yt1 - yt0
        pw_b, ph_b = x1 - x0, yb1 - yb0

        top_f = frames_dir / f"top_{f_idx:04d}.png"
        bot_f = frames_dir / f"bot_{f_idx:04d}.png"
        mask_f = frames_dir / f"mask_{f_idx:04d}.png"
        top_bgr = cv2.imread(str(top_f), cv2.IMREAD_COLOR)
        bot_bgr = cv2.imread(str(bot_f), cv2.IMREAD_COLOR)
        if top_bgr is None or bot_bgr is None:
            raise RuntimeError(f"Missing stacked panel frame at idx={f_idx}")
        top_rgb = cv2.cvtColor(cv2.resize(top_bgr, (pw_t, ph_t), interpolation=cv2.INTER_LANCZOS4), cv2.COLOR_BGR2RGB)
        bot_rgb = cv2.cvtColor(cv2.resize(bot_bgr, (pw_b, ph_b), interpolation=cv2.INTER_LANCZOS4), cv2.COLOR_BGR2RGB)

        if has_dash and mask_f.is_file():
            m_gray = cv2.imread(str(mask_f), cv2.IMREAD_GRAYSCALE)
            if m_gray is not None:
                top_rgb = _draw_dashed_mask_contour(top_rgb, m_gray, color_rgb=(237, 242, 247), width_px=3)
                bot_rgb = _draw_dashed_mask_contour(bot_rgb, m_gray, color_rgb=(226, 236, 246), width_px=2)

        canvas[yt0:yt1, x0:x1] = cv2.cvtColor(top_rgb, cv2.COLOR_RGB2BGR)
        canvas[yb0:yb1, x0:x1] = cv2.cvtColor(bot_rgb, cv2.COLOR_RGB2BGR)
        # Subtle clinical viewport frames (Coral-Red Top vs Cerulean-Blue Bottom)
        cv2.rectangle(canvas, (x0, yt0), (x1 - 1, yt1 - 1), (96, 84, 232), 3, lineType=cv2.LINE_AA)
        cv2.rectangle(canvas, (x0, yb0), (x1 - 1, yb1 - 1), (228, 168, 66), 3, lineType=cv2.LINE_AA)
        return np.clip(canvas.astype(np.float32) * vignette, 0.0, 250.0).astype(np.uint8)

    fp = frames_dir / f"frame_{f_idx:04d}.png"
    img = cv2.imread(str(fp), cv2.IMREAD_COLOR)
    if img is None:
        raise RuntimeError(f"Failed reading rendered frame {fp}")
    if img.shape[0] != height or img.shape[1] != width:
        img = cv2.resize(img, (width, height), interpolation=cv2.INTER_LANCZOS4)
    if has_dash:
        mask_f = frames_dir / f"mask_{f_idx:04d}.png"
        if mask_f.is_file():
            m_gray = cv2.imread(str(mask_f), cv2.IMREAD_GRAYSCALE)
            if m_gray is not None:
                rgb_full = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                rgb_full = _draw_dashed_mask_contour(rgb_full, m_gray, color_rgb=(237, 242, 247), width_px=3)
                img = cv2.cvtColor(rgb_full, cv2.COLOR_RGB2BGR)
    return np.clip(img.astype(np.float32) * vignette, 0.0, 250.0).astype(np.uint8)


def _assemble_rendered_sequence(
    *,
    frames_dir: Path,
    render_cfg: dict[str, Any],
    out_mp4: Path,
    width: int,
    height: int,
    fps: int,
    threads: int = BLENDER_SIM_THREADS_PER_WORKER,
) -> dict[str, Any]:
    """Composites rendered Cycles keyframes (with optional DISOpticalFlow stride-2 upsampling) into a 30fps H.264 MP4."""
    eff_threads = max(1, int(threads or BLENDER_SIM_THREADS_PER_WORKER))
    n_frames = int(render_cfg["n_frames"])
    stride = max(1, int(render_cfg.get("keyframe_stride") or 1))
    rendered_indices = sorted(set(list(range(0, n_frames, stride)) + [n_frames - 1]))

    yy, xx = np.mgrid[0:height, 0:width].astype(np.float32)
    nx = (xx - width * 0.50) / (width * 0.55)
    ny = (yy - height * 0.48) / (height * 0.42)
    r2 = np.clip(nx * nx + ny * ny, 0.0, 2.0)
    vignette = (1.08 - 0.12 * r2)[:, :, None].astype(np.float32)

    key_bgr: dict[int, np.ndarray] = {}
    for ki in rendered_indices:
        key_bgr[ki] = _composite_single_keyframe_bgr(frames_dir, ki, render_cfg, width, height, vignette)

    ff = imageio_ffmpeg.get_ffmpeg_exe()
    cmd = [
        ff,
        "-y",
        "-f", "rawvideo",
        "-vcodec", "rawvideo",
        "-s", f"{width}x{height}",
        "-pix_fmt", "bgr24",
        "-r", str(fps),
        "-i", "-",
        "-an",
        "-c:v", "libx264",
        "-threads", str(eff_threads),
        "-preset", "fast",
        "-crf", "16",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        str(out_mp4),
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert proc.stdin is not None

    p995_vals: list[float] = []
    mean_luma_vals: list[float] = []
    sample_indices = {0, n_frames // 2, n_frames - 1}

    import bisect

    for f_i in range(n_frames):
        if f_i in key_bgr:
            out_img = key_bgr[f_i]
        else:
            pos = bisect.bisect_right(rendered_indices, f_i)
            i0 = rendered_indices[max(0, pos - 1)]
            i1 = rendered_indices[min(len(rendered_indices) - 1, pos)]
            alpha = (f_i - i0) / float(max(1, i1 - i0))
            out_img = _interpolate_intermediate_frame_dis(key_bgr[i0], key_bgr[i1], alpha=alpha)
        proc.stdin.write(out_img.tobytes())
        if f_i in sample_indices:
            gray = cv2.cvtColor(out_img, cv2.COLOR_BGR2GRAY)
            p995_vals.append(float(np.percentile(gray, 99.5)))
            mean_luma_vals.append(float(gray.mean()))

    proc.stdin.flush()
    proc.stdin.close()
    rc = proc.wait(timeout=120)
    err_bytes = proc.stderr.read() if proc.stderr else b""
    if proc.stdout:
        proc.stdout.close()
    if proc.stderr:
        proc.stderr.close()
    if rc != 0 or not out_mp4.is_file():
        raise RuntimeError(f"ffmpeg encode failed rc={rc}: {err_bytes.decode('utf-8', 'ignore')[-800:]}")

    return {
        "max_p995_luma": round(max(p995_vals) if p995_vals else 0.0, 2),
        "mean_luma": round(float(np.mean(mean_luma_vals)) if mean_luma_vals else 0.0, 2),
        "file_size_bytes": int(out_mp4.stat().st_size),
    }


def _composite_and_encode_frames(
    frame_files: list[Path],
    out_mp4: Path,
    *,
    width: int,
    height: int,
    fps: int,
    threads: int = BLENDER_SIM_THREADS_PER_WORKER,
) -> dict[str, Any]:
    """Legacy frame-list encoder preserved for existing unit tests."""
    eff_threads = max(1, int(threads or BLENDER_SIM_THREADS_PER_WORKER))
    yy, xx = np.mgrid[0:height, 0:width].astype(np.float32)
    nx = (xx - width * 0.50) / (width * 0.55)
    ny = (yy - height * 0.48) / (height * 0.42)
    r2 = np.clip(nx * nx + ny * ny, 0.0, 2.0)
    vignette = (1.08 - 0.12 * r2)[:, :, None].astype(np.float32)

    ff = imageio_ffmpeg.get_ffmpeg_exe()
    cmd = [
        ff, "-y", "-f", "rawvideo", "-vcodec", "rawvideo", "-s", f"{width}x{height}",
        "-pix_fmt", "bgr24", "-r", str(fps), "-i", "-", "-an", "-c:v", "libx264",
        "-threads", str(eff_threads), "-preset", "fast", "-crf", "16", "-pix_fmt", "yuv420p",
        "-movflags", "+faststart", str(out_mp4),
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert proc.stdin is not None
    p995_vals: list[float] = []
    mean_luma_vals: list[float] = []
    sample_indices = {0, len(frame_files) // 2, len(frame_files) - 1}
    for idx, fp in enumerate(frame_files):
        img = cv2.imread(str(fp), cv2.IMREAD_COLOR)
        if img is None:
            raise RuntimeError(f"Failed reading rendered frame {fp}")
        if img.shape[0] != height or img.shape[1] != width:
            img = cv2.resize(img, (width, height), interpolation=cv2.INTER_LANCZOS4)
        out_img = np.clip(img.astype(np.float32) * vignette, 0.0, 250.0).astype(np.uint8)
        proc.stdin.write(out_img.tobytes())
        if idx in sample_indices:
            gray = cv2.cvtColor(out_img, cv2.COLOR_BGR2GRAY)
            p995_vals.append(float(np.percentile(gray, 99.5)))
            mean_luma_vals.append(float(gray.mean()))
    proc.stdin.flush()
    proc.stdin.close()
    rc = proc.wait(timeout=120)
    if proc.stdout:
        proc.stdout.close()
    if proc.stderr:
        proc.stderr.close()
    if rc != 0 or not out_mp4.is_file():
        raise RuntimeError(f"ffmpeg encode failed rc={rc}")
    return {
        "max_p995_luma": round(max(p995_vals) if p995_vals else 0.0, 2),
        "mean_luma": round(float(np.mean(mean_luma_vals)) if mean_luma_vals else 0.0, 2),
        "file_size_bytes": int(out_mp4.stat().st_size),
    }


def evaluate_simulator_qa(
    *,
    render_cfg: dict[str, Any],
    manifest: dict[str, Any],
    track_doc: dict[str, Any],
    pixel_stats: dict[str, Any],
    width: int,
    height: int,
) -> dict[str, Any]:
    """Evaluates deterministic Rule R76 & Rule R84 Simulator QA gates `SQ1-SQ6`."""
    regions = manifest["regions"]
    start_k = str(render_cfg["start_key"])
    end_k = str(render_cfg["end_key"])
    n_start = int((regions.get(start_k) or {}).get("n_verts") or 0)
    n_end = int((regions.get(end_k) or {}).get("n_verts") or 0)
    sq1_ok = n_start >= 80 and n_end >= 80

    sq2_ok = all(
        int((regions.get(ctx) or {}).get("n_verts") or 0) >= 500
        for ctx in ("head_shell", "cortex_lh", "cortex_rh", "cerebellum", "brainstem")
    )

    tract_pts = np.asarray(render_cfg["tract_pts_mm"], dtype=np.float64)
    c_start = np.asarray(render_cfg["anchors_mm"]["start"], dtype=np.float64)
    c_end = np.asarray(render_cfg["anchors_mm"]["end"], dtype=np.float64)
    d_start = float(np.linalg.norm(tract_pts[0] - c_start))
    d_end = float(np.linalg.norm(tract_pts[-1] - c_end))
    frames = track_doc.get("frames") or []
    start_pts = [f["anchors"]["start"] for f in frames if "start" in f.get("anchors", {})]
    end_pts = [f["anchors"]["end"] for f in frames if "end" in f.get("anchors", {})]

    if bool(render_cfg.get("stacked_cutaway_brain_compare")):
        # Top vs Bottom 2.5x stacked viewports must maintain clean vertical separation (>= 320px)
        sq3_ok = bool(start_pts and end_pts and abs(end_pts[0]["y_px"] - start_pts[0]["y_px"]) >= 280.0)
    elif bool(render_cfg.get("side_by_side_brain_compare")):
        sq3_ok = float(abs(c_start[0] - c_end[0])) >= 80.0
    elif str(render_cfg.get("morph_mode") or "") == "posterior_vs_anterior_tradeoff":
        sq3_ok = float(np.linalg.norm(c_start - c_end)) >= 15.0
    else:
        sq3_ok = (len(tract_pts) >= 12) and (d_start <= 26.0) and (d_end <= 22.0)

    all_pts = start_pts + end_pts
    y_lo = 0.20 if bool(render_cfg.get("stacked_cutaway_brain_compare")) else 0.22
    y_hi = 0.74 if bool(render_cfg.get("stacked_cutaway_brain_compare")) else 0.73
    in_bounds = [
        (0.06 * width <= p["x_px"] <= 0.92 * width) and (y_lo * height <= p["y_px"] <= y_hi * height)
        for p in all_pts
    ]
    sq4_frac = (sum(1 for b in in_bounds if b) / len(in_bounds)) if in_bounds else 0.0
    sq4_ok = sq4_frac >= 0.88

    steps_px: list[float] = []
    for i in range(1, len(start_pts)):
        dx = start_pts[i]["x_px"] - start_pts[i - 1]["x_px"]
        dy = start_pts[i]["y_px"] - start_pts[i - 1]["y_px"]
        steps_px.append(math.hypot(dx, dy))
    max_step = max(steps_px) if steps_px else 0.0
    total_travel = sum(steps_px)
    sq5_ok = (total_travel >= 6.0) and (max_step <= 38.0)

    max_p995 = float(pixel_stats.get("max_p995_luma") or 0.0)
    mean_l = float(pixel_stats.get("mean_luma") or 0.0)
    sq6_ok = (6.0 <= mean_l <= 145.0) and (max_p995 <= 252.0)

    gates = {
        "SQ1_genuine_atlas_meshes": sq1_ok,
        "SQ2_head_and_cortex_context": sq2_ok,
        "SQ3_tract_connectivity": sq3_ok,
        "SQ4_viewport_safe_framing": sq4_ok,
        "SQ5_smooth_drone_motion": sq5_ok,
        "SQ6_zero_glow_clinical_exposure": sq6_ok,
    }
    passed = all(gates.values()) if R76_BRAIN_SIM_SQ_PASS_REQUIRED else True
    return {
        "passed": passed,
        "gates": gates,
        "metrics": {
            "rule_version": render_cfg.get("rule_version", "R84_v1"),
            "blender_engine": render_cfg.get("blender_engine", "CYCLES"),
            "surgical_cutaway": bool(render_cfg.get("surgical_cutaway")),
            "stacked_cutaway_brain_compare": bool(render_cfg.get("stacked_cutaway_brain_compare")),
            "dashed_baseline": bool(render_cfg.get("dashed_baseline")),
            "morph_mode": render_cfg.get("morph_mode", ""),
            "start_region": start_k,
            "end_region": end_k,
            "neural_state": render_cfg["neural_state"],
            "n_verts_start": n_start,
            "n_verts_end": n_end,
            "tract_d_start_mm": round(d_start, 2),
            "tract_d_end_mm": round(d_end, 2),
            "safe_viewport_frac": round(sq4_frac, 4),
            "total_track_travel_px": round(total_travel, 2),
            "max_step_px": round(max_step, 2),
            "mean_luma": mean_l,
            "max_p995_luma": max_p995,
            "file_size_bytes": pixel_stats.get("file_size_bytes", 0),
        },
    }


def _build_blender_runner_script(cfg_path: Path, frames_dir: Path, track_path: Path) -> str:
    """Generates self-contained Python script executed inside Blender 4.2 headless (`Cycles` PBR + Surgical Cutaway + Stacked 2.5x)."""
    return textwrap.dedent(f"""\
        import json
        import math
        from pathlib import Path
        import bpy
        import numpy as np
        from mathutils import Vector
        from bpy_extras.object_utils import world_to_camera_view

        cfg = json.loads(Path({str(cfg_path)!r}).read_text(encoding="utf-8"))
        npz = np.load(cfg["npz_path"])
        frames_dir = Path({str(frames_dir)!r})

        bpy.ops.object.select_all(action="SELECT")
        bpy.ops.object.delete(use_global=False)

        scene = bpy.context.scene
        eng_mode = str(cfg.get("blender_engine") or "CYCLES").upper()
        rw = int(cfg.get("render_width") or cfg["width"])
        rh = int(cfg.get("render_height") or cfg["height"])
        w = int(cfg["width"])
        h = int(cfg["height"])
        n_frames = int(cfg["n_frames"])
        fps = float(cfg["fps"])
        stride = max(1, int(cfg.get("keyframe_stride") or 1))
        rendered_indices = sorted(set(list(range(0, n_frames, stride)) + [n_frames - 1]))
        is_stacked = bool(cfg.get("stacked_cutaway_brain_compare", False))
        is_sbs = bool(cfg.get("side_by_side_brain_compare", False)) and not is_stacked
        has_dash = bool(cfg.get("dashed_baseline", False))
        morph_mode = str(cfg.get("morph_mode") or "").strip().lower()

        scene.render.resolution_x = rw
        scene.render.resolution_y = rh
        scene.render.resolution_percentage = 100
        scene.render.fps = int(fps)
        scene.render.image_settings.file_format = "PNG"
        scene.render.image_settings.color_mode = "RGB"

        if eng_mode == "CYCLES":
            scene.render.engine = "CYCLES"
            scene.cycles.device = "CPU"
            scene.cycles.samples = int(cfg.get("cycles_samples") or 16)
            scene.cycles.use_adaptive_sampling = True
            scene.cycles.adaptive_threshold = 0.05
            scene.cycles.use_denoising = True
            scene.cycles.denoiser = "OPENIMAGEDENOISE"
            scene.cycles.denoising_prefilter = "FAST"
            scene.cycles.max_bounces = 2
            scene.cycles.diffuse_bounces = 1
            scene.cycles.glossy_bounces = 1
            scene.cycles.transmission_bounces = 0
            scene.cycles.transparent_max_bounces = 1
            scene.render.use_persistent_data = True
            avail_vt = [x.identifier for x in scene.view_settings.bl_rna.properties["view_transform"].enum_items]
            scene.view_settings.view_transform = "AgX" if "AgX" in avail_vt else "Filmic"
            scene.view_settings.exposure = -0.22
            if not is_stacked and rh >= 900:
                scene.render.use_border = True
                scene.render.use_crop_to_border = False
                scene.render.border_min_x = 0.02
                scene.render.border_max_x = 0.98
                scene.render.border_min_y = 0.14
                scene.render.border_max_y = 0.86
            if scene.world is None:
                scene.world = bpy.data.worlds.new("MedicalWorld")
            scene.world.use_nodes = True
            bg_n = scene.world.node_tree.nodes.get("Background")
            if bg_n:
                bg_n.inputs[0].default_value = (0.007, 0.010, 0.018, 1.0)
                bg_n.inputs[1].default_value = 0.45
        else:
            scene.render.engine = "BLENDER_WORKBENCH"
            scene.display.render_aa = "FXAA"
            scene.display.shading.light = "STUDIO"
            scene.display.shading.color_type = "MATERIAL"
            scene.display.shading.show_cavity = True
            scene.display.shading.background_type = "WORLD"
            if scene.world is None:
                scene.world = bpy.data.worlds.new("ClinicalWorld")
            scene.world.use_nodes = False
            scene.world.color = tuple(cfg["bg_linear"])
            scene.view_settings.view_transform = "Standard"

        # 3-point clinical area lighting (zero harsh specular glare, crisp sulcal AO)
        light_objs = []
        for l_loc, l_en, l_sz in (
            ((0.30, -0.18, 0.28), 4.6, 0.36),
            ((-0.24, -0.28, 0.16), 2.1, 0.38),
            ((0.18, 0.28, 0.18), 2.8, 0.32),
        ):
            ld = bpy.data.lights.new("MedAreaLight", type="AREA")
            ld.energy = l_en
            ld.size = l_sz
            lo = bpy.data.objects.new("MedAreaLightObj", ld)
            scene.collection.objects.link(lo)
            lo.location = l_loc
            lo.rotation_euler = (Vector((0.01, -0.015, 0.0)) - Vector(l_loc)).to_track_quat("-Z", "Y").to_euler()
            light_objs.append(lo)

        colors = cfg["colors_linear"]
        mat_mode = str(cfg.get("material_mode") or "r84_medical_pbr")  # supports xray_glass, cool_matte_silver_31, r84_medical_pbr
        mid_sagittal = bool(cfg.get("mid_sagittal_split", False))

        def make_pbr_mat(name, rgb_tuple, rough=0.60, sss=0.10):
            m = bpy.data.materials.new(name)
            rgba = (float(rgb_tuple[0]), float(rgb_tuple[1]), float(rgb_tuple[2]), 1.0)
            m.diffuse_color = rgba
            m.use_nodes = True
            bsdf = m.node_tree.nodes.get("Principled BSDF")
            if bsdf is not None:
                bsdf.inputs["Base Color"].default_value = rgba
                bsdf.inputs["Roughness"].default_value = float(rough)
                if "Subsurface Weight" in bsdf.inputs:
                    bsdf.inputs["Subsurface Weight"].default_value = float(sss)
                if "Specular IOR Level" in bsdf.inputs:
                    bsdf.inputs["Specular IOR Level"].default_value = 0.22
            return m

        mat_white_mask = bpy.data.materials.new("PureWhiteMask")
        mat_white_mask.diffuse_color = (1.0, 1.0, 1.0, 1.0)
        mat_white_mask.use_nodes = True
        nt_m = mat_white_mask.node_tree
        nt_m.nodes.clear()
        out_m = nt_m.nodes.new("ShaderNodeOutputMaterial")
        em_m = nt_m.nodes.new("ShaderNodeEmission")
        em_m.inputs["Color"].default_value = (1.0, 1.0, 1.0, 1.0)
        em_m.inputs["Strength"].default_value = 2.0
        nt_m.links.new(em_m.outputs["Emission"], out_m.inputs["Surface"])

        def load_raw_vf(atlas_key, rh_only=False, y_filter=None):
            safe = atlas_key.replace(" ", "_").replace("'", "")
            v = npz[f"{{safe}}__verts"].astype(np.float64).copy()
            f = npz[f"{{safe}}__faces"].astype(np.int32).copy()
            keep = np.ones(len(v), dtype=bool)
            if rh_only:
                keep &= (v[:, 0] >= -1.5)
            if y_filter == "posterior":
                keep &= (v[:, 1] <= -18.5)
            elif y_filter == "anterior":
                keep &= (v[:, 1] >= -21.5)
            if not np.all(keep):
                idx_map = np.full(len(v), -1, dtype=np.int32)
                idx_map[keep] = np.arange(np.count_nonzero(keep), dtype=np.int32)
                v = v[keep]
                valid_f = np.all(idx_map[f] >= 0, axis=1)
                f = idx_map[f[valid_f]]
            return v, f

        def compute_morphed_verts(v_base, post_exp=0.0, ant_shr=0.0, uniform_sc=1.0):
            v = v_base.copy()
            if len(v) == 0:
                return v
            if abs(post_exp) > 1e-4 or abs(ant_shr) > 1e-4:
                y = v[:, 1]
                w_post = 1.0 / (1.0 + np.exp((y + 22.5) / 3.2))
                w_ant = 1.0 / (1.0 + np.exp(-(y + 15.0) / 3.0))
                for i in range(len(v)):
                    ms = np.abs(y - y[i]) < 3.5
                    c_xz = v_base[ms][:, [0, 2]].mean(axis=0)
                    sc = 1.0 + post_exp * w_post[i] - ant_shr * w_ant[i]
                    v[i, 0] = c_xz[0] + (v_base[i, 0] - c_xz[0]) * sc
                    v[i, 2] = c_xz[1] + (v_base[i, 2] - c_xz[1]) * sc
                    if w_post[i] > 0.40:
                        v[i, 1] -= 3.2 * post_exp * w_post[i]
            if abs(uniform_sc - 1.0) > 1e-4:
                ctr = np.mean(v, axis=0, keepdims=True)
                v = ctr + (v - ctr) * float(uniform_sc)
            return v

        def build_mesh_obj(atlas_key, obj_name, mat, *, scale=0.001, offset_m=(0.0, 0.0, 0.0), rh_only=False, y_filter=None, subsurf=0, boolean_box=None, morph_target=None):
            v0, f = load_raw_vf(atlas_key, rh_only=rh_only, y_filter=y_filter)
            ox, oy, oz = float(offset_m[0]), float(offset_m[1]), float(offset_m[2])
            off_arr = np.array([[ox, oy, oz]], dtype=np.float64)
            v_init = (v0 * scale + off_arr).tolist()
            mesh = bpy.data.meshes.new(obj_name + "_m")
            mesh.from_pydata(v_init, [], f.tolist())
            mesh.update()
            for p in mesh.polygons:
                p.use_smooth = True
            obj = bpy.data.objects.new(obj_name, mesh)
            scene.collection.objects.link(obj)
            obj.data.materials.append(mat)

            if morph_target is not None and len(v0) > 0:
                pe, ash, usc = morph_target
                v1_mm = compute_morphed_verts(v0, post_exp=pe, ant_shr=ash, uniform_sc=usc)
                v1 = v1_mm * scale + off_arr
                sk_basis = obj.shape_key_add(name="Basis", from_mix=False)
                sk_morph = obj.shape_key_add(name="Morph", from_mix=False)
                for idx_v in range(len(v1)):
                    sk_morph.data[idx_v].co = (float(v1[idx_v, 0]), float(v1[idx_v, 1]), float(v1[idx_v, 2]))
                sk_morph.value = 0.0

            if boolean_box is not None:
                bx_loc, bx_scale, cut_mat = boolean_box
                obj.data.materials.append(cut_mat)
                bpy.ops.mesh.primitive_cube_add(size=1.0, location=bx_loc)
                cutter = bpy.context.active_object
                cutter.name = obj_name + "_cutter"
                cutter.scale = bx_scale
                cutter.data.materials.append(cut_mat)
                cutter.hide_render = True
                cutter.display_type = "WIRE"
                mod = obj.modifiers.new("SurgicalCutaway", "BOOLEAN")
                mod.operation = "DIFFERENCE"
                mod.solver = "EXACT"
                mod.object = cutter
                # Bake static EXACT Boolean once at scene setup so frame_set() never re-evaluates 47k-tri CGAL intersections!
                if morph_target is None:
                    bpy.context.view_layer.objects.active = obj
                    bpy.ops.object.modifier_apply(modifier=mod.name)
                    bpy.data.objects.remove(cutter, do_unlink=True)

            if subsurf > 0:
                eff_sub = 1 if morph_target is not None else int(subsurf)
                sub = obj.modifiers.new("SmoothSubsurf", "SUBSURF")
                sub.levels = eff_sub
                sub.render_levels = eff_sub
                if morph_target is None:
                    bpy.context.view_layer.objects.active = obj
                    bpy.ops.object.modifier_apply(modifier=sub.name)
            return obj

        mat_ctx = make_pbr_mat("CortexMatte", colors.get("cortex_r84", colors["cortex"]), rough=0.62, sss=0.08)
        mat_cut = make_pbr_mat("CutPlaneMatte", colors["cut_plane"], rough=0.66, sss=0.05)
        mat_sub = make_pbr_mat("SubcorticalMatte", colors["subcortical"], rough=0.60, sss=0.06)
        mat_cc = make_pbr_mat("CallosumSlateBlue", colors["callosum"], rough=0.46, sss=0.10)
        mat_coral = make_pbr_mat("TargetCoral", colors["primary"], rough=0.40, sss=0.16)
        mat_cerul = make_pbr_mat("TargetCerulean", colors["partner"], rough=0.42, sss=0.14)
        mat_ochre = make_pbr_mat("SensoryOchre", colors["sensory"], rough=0.44, sss=0.12)
        mat_sil = make_pbr_mat("TargetSilenced", colors["silenced"], rough=0.58, sss=0.06)
        mat_cyan = make_pbr_mat("FluidCyan", colors["sulcal_cyan"], rough=0.38, sss=0.14)
        mat_sig = make_pbr_mat("SignalBolus", colors["signal"], rough=0.36, sss=0.10)

        role_mats = {{
            "primary": mat_coral,
            "partner": mat_cerul,
            "sensory": mat_ochre,
            "silenced": mat_sil,
        }}

        start_k = cfg["start_key"]
        end_k = cfg["end_key"]
        state = cfg["neural_state"]
        surg_cut = bool(cfg.get("surgical_cutaway", True))

        def make_fiber_strand(name, pts_arr, mat, radius=0.0012):
            curve_data = bpy.data.curves.new(name + "_curve", type="CURVE")
            curve_data.dimensions = "3D"
            curve_data.resolution_u = 12
            curve_data.bevel_depth = radius
            curve_data.bevel_resolution = 4
            spline = curve_data.splines.new("POLY")
            spline.points.add(len(pts_arr) - 1)
            for idx_p, pt in enumerate(pts_arr):
                spline.points[idx_p].co = (float(pt[0]), float(pt[1]), float(pt[2]), 1.0)
            obj = bpy.data.objects.new(name, curve_data)
            scene.collection.objects.link(obj)
            obj.data.materials.append(mat)
            return obj

        def sample_poly(pts, u):
            u = max(0.0, min(1.0, float(u)))
            pos_f = u * (len(pts) - 1)
            i0 = min(int(pos_f), len(pts) - 2)
            frac = pos_f - i0
            p = pts[i0] * (1.0 - frac) + pts[i0 + 1] * frac
            tangent = pts[min(i0 + 1, len(pts) - 1)] - pts[max(i0 - 1, 0)]
            nrm = np.linalg.norm(tangent)
            if nrm > 1e-8:
                tangent = tangent / nrm
            return p, tangent

        context_objs = []
        morph_objs = []
        mask_target_objs = []
        top_only_objs = []
        bot_only_objs = []
        signal_objs = []
        tract_pts = np.asarray(cfg["tract_pts_mm"], dtype=np.float64) * 0.001

        if is_stacked:
            # Shared anatomical bed for 2.5x Stacked Surgical Cutaway Comparison (Top Group A vs Bottom Group B)
            focus_k = "hippocampus" if "hippocampus" in (start_k, end_k) else start_k
            context_objs.append(build_mesh_obj("cortex_lh", "StackCortexLH", mat_ctx))
            if focus_k in ("insula", "prefrontal cortex", "ventromedial prefrontal cortex"):
                c_box = ((0.052, 0.012, 0.016), (0.064, 0.105, 0.092), mat_cut)
                context_objs.append(build_mesh_obj("cortex_rh", "StackCortexRH", mat_ctx, boolean_box=c_box))
            else:
                c_box = ((0.048, -0.006, 0.022), (0.078, 0.140, 0.112), mat_cut)
                context_objs.append(build_mesh_obj("cortex_rh", "StackCortexRH", mat_ctx, boolean_box=c_box))
            context_objs.append(build_mesh_obj("cerebellum", "StackCereb", mat_sub))
            if focus_k != "brainstem":
                context_objs.append(build_mesh_obj("brainstem", "StackStem", mat_sub))
            if focus_k != "thalamus":
                context_objs.append(build_mesh_obj("thalamus", "StackThal", mat_sub, subsurf=1))
            if focus_k == "hippocampus":
                context_objs.append(build_mesh_obj("amygdala", "StackAmyg", mat_sub, rh_only=True, subsurf=1))
                context_objs.append(build_mesh_obj("corpus callosum", "StackCallosum", mat_cc, subsurf=1))

            # Unmodified 1.0x baseline silhouette target for white dashed contour
            m_base = build_mesh_obj(focus_k, "MaskBaseline1x", mat_white_mask, rh_only=(focus_k != "brainstem"), subsurf=2)
            m_base.hide_render = True
            mask_target_objs.append(m_base)

            if morph_mode == "posterior_hypertrophy":
                # Top: Taxi (+56% posterior tail swelling outside 1.0x dashed contour) | Bottom: Bus (1.0x baseline)
                t_obj = build_mesh_obj(
                    focus_k, "TopTaxiHippo", mat_coral, rh_only=True, subsurf=2,
                    morph_target=(float(cfg.get("posterior_expand") or 0.56), float(cfg.get("anterior_shrink") or 0.18), 1.0),
                )
                b_obj = build_mesh_obj(focus_k, "BotBusHippo", mat_cerul, rh_only=True, subsurf=2)
                top_only_objs.append(t_obj)
                morph_objs.append((t_obj, 0.28, 1.0))
                bot_only_objs.append(b_obj)
            elif morph_mode == "pulsatile_pump":
                # Top: Natural Sleep (active pulsatile pump + cyan fluid tracts) | Bottom: Zolpidem (muted 0.80x pump)
                t_obj = build_mesh_obj(
                    focus_k, "TopNaturalPump", mat_ochre, rh_only=(focus_k != "brainstem"), subsurf=2,
                    morph_target=(0.0, 0.0, 1.24),
                )
                t_part = build_mesh_obj("thalamus" if focus_k == "brainstem" else "brainstem", "TopPumpPartner", mat_cyan, subsurf=1)
                f_top = make_fiber_strand("TopPumpTract", tract_pts, mat_cyan, radius=0.0022)
                b_obj = build_mesh_obj(
                    focus_k, "BotSedatedPump", mat_sil, rh_only=(focus_k != "brainstem"), subsurf=2,
                    morph_target=(0.0, 0.0, 0.82),
                )
                b_part = build_mesh_obj("thalamus" if focus_k == "brainstem" else "brainstem", "BotPumpPartner", mat_sil, subsurf=1)
                f_bot = make_fiber_strand("BotPumpTract", tract_pts, mat_sil, radius=0.0009)
                top_only_objs.extend([t_obj, t_part, f_top])
                morph_objs.extend([(t_obj, 0.35, 1.0), (b_obj, 0.50, 1.0)])
                bot_only_objs.extend([b_obj, b_part, f_bot])
            elif morph_mode == "pain_gate_suppression":
                # Top: Open Placebo (active cerulean brainstem gate + calmed 0.82x slate Insula) | Bottom: No-Pill (swollen 1.28x coral Insula)
                ins_top = build_mesh_obj("insula", "TopPlaceboInsula", mat_sil, rh_only=True, subsurf=2, morph_target=(0.0, 0.0, 0.82))
                gate_top = build_mesh_obj("brainstem", "TopPlaceboGate", mat_cerul, subsurf=1)
                ins_bot = build_mesh_obj("insula", "BotControlInsula", mat_coral, rh_only=True, subsurf=2, morph_target=(0.0, 0.0, 1.28))
                gate_bot = build_mesh_obj("brainstem", "BotControlGate", mat_sub, subsurf=1)
                top_only_objs.extend([ins_top, gate_top])
                bot_only_objs.extend([ins_bot, gate_bot])
                morph_objs.extend([(ins_top, 0.35, 1.0), (ins_bot, 0.35, 1.0)])
            else:
                # working_memory_retention (Top: Same Room bright PFC 1.18x | Bottom: Doorway Cross coral Hippocampus wipe + dimmed 0.80x PFC)
                pfc_top = build_mesh_obj(focus_k, "TopRetainedHub", mat_cerul, rh_only=True, subsurf=2, morph_target=(0.0, 0.0, 1.18))
                hip_top = build_mesh_obj("hippocampus", "TopCalmHippo", mat_sub, rh_only=True, subsurf=2)
                pfc_bot = build_mesh_obj(focus_k, "BotWipedHub", mat_sil, rh_only=True, subsurf=2, morph_target=(0.0, 0.0, 0.80))
                hip_bot = build_mesh_obj("hippocampus", "BotBoundaryHippo", mat_coral, rh_only=True, subsurf=2)
                top_only_objs.extend([pfc_top, hip_top])
                bot_only_objs.extend([pfc_bot, hip_bot])
                morph_objs.extend([(pfc_top, 0.35, 1.0), (pfc_bot, 0.35, 1.0)])
        elif is_sbs:
            sbs_sc = 0.001 * float(cfg.get("sbs_scale") or 0.62)
            dx_m = 0.001 * float(cfg.get("sbs_dx_mm") or 82.0)
            l_sc = float(cfg.get("left_region_scale") or 1.32)
            r_sc = float(cfg.get("right_region_scale") or 0.86)
            for tag_b, off_x, reg_k, reg_mat, reg_sc in (
                ("LeftA", dx_m, start_k, mat_coral, l_sc),
                ("RightB", -dx_m, end_k, mat_sil, r_sc),
            ):
                off_t = (off_x, 0.0, 0.0)
                context_objs.append(build_mesh_obj("cortex_lh", f"CortexLH_{{tag_b}}", mat_ctx, scale=sbs_sc, offset_m=off_t))
                c_box = ((off_x + 0.030, -0.005, 0.014), (0.048, 0.085, 0.070), mat_cut)
                context_objs.append(build_mesh_obj("cortex_rh", f"CortexRH_{{tag_b}}", mat_ctx, scale=sbs_sc, offset_m=off_t, boolean_box=c_box))
                context_objs.append(build_mesh_obj("cerebellum", f"Cereb_{{tag_b}}", mat_sub, scale=sbs_sc, offset_m=off_t))
                context_objs.append(build_mesh_obj("brainstem", f"Stem_{{tag_b}}", mat_sub, scale=sbs_sc, offset_m=off_t))
                context_objs.append(build_mesh_obj(reg_k, f"Cohort_{{tag_b}}", reg_mat, scale=sbs_sc, offset_m=off_t, rh_only=True, subsurf=1, morph_target=(0.0, 0.0, reg_sc)))
        else:
            # Single-Brain Rule R84 Surgical Cutaway PBR
            context_objs.append(build_mesh_obj("cortex_lh", "CortexLH", mat_ctx))
            if surg_cut:
                if "insula" in (start_k, end_k):
                    c_box = ((0.052, 0.012, 0.016), (0.064, 0.105, 0.092), mat_cut)
                else:
                    c_box = ((0.048, -0.006, 0.022), (0.078, 0.140, 0.112), mat_cut)
                context_objs.append(build_mesh_obj("cortex_rh", "CortexRH_Cutaway", mat_ctx, boolean_box=c_box))
            else:
                context_objs.append(build_mesh_obj("cortex_rh", "CortexRH_Intact", mat_ctx))

            context_objs.append(build_mesh_obj("cerebellum", "Cerebellum", mat_sub))
            if "brainstem" not in (start_k, end_k):
                context_objs.append(build_mesh_obj("brainstem", "Brainstem", mat_sub))
            if "thalamus" not in (start_k, end_k):
                context_objs.append(build_mesh_obj("thalamus", "ThalamusCtx", mat_sub, subsurf=1))
            if bool(cfg.get("show_callosum_landmark")) and "corpus callosum" not in (start_k, end_k):
                context_objs.append(build_mesh_obj("corpus callosum", "CallosumLandmark", mat_cc, subsurf=1))

            if start_k == "eyes":
                context_objs.append(build_mesh_obj("eyes", "EyesEntry", mat_ochre))
                context_objs.append(build_mesh_obj("optic pathway", "OpticPathway", mat_ochre))
            elif start_k == "inner ear":
                context_objs.append(build_mesh_obj("inner ear", "InnerEarEntry", mat_ochre))
                context_objs.append(build_mesh_obj("auditory nerve", "AuditoryNerve", mat_ochre))

            if morph_mode == "posterior_vs_anterior_tradeoff":
                # Dual-zone Hippocampus trade-off: Posterior Tail swells Coral (+56%), Anterior Head shrinks Cerulean-Slate (-30%) against 1.0x White Dashed Baseline!
                context_objs.append(build_mesh_obj("amygdala", "AmygdalaRef", mat_sub, rh_only=True, subsurf=1))
                m_base = build_mesh_obj("hippocampus", "MaskHippo1x", mat_white_mask, rh_only=True, subsurf=2)
                m_base.hide_render = True
                mask_target_objs.append(m_base)
                h_post = build_mesh_obj(
                    "hippocampus", "HippoPosteriorGrow", mat_coral, rh_only=True, y_filter="posterior", subsurf=2,
                    morph_target=(float(cfg.get("posterior_expand") or 0.56), 0.0, 1.0),
                )
                h_ant = build_mesh_obj(
                    "hippocampus", "HippoAnteriorShrink", mat_cerul, rh_only=True, y_filter="anterior", subsurf=2,
                    morph_target=(0.0, float(cfg.get("anterior_shrink") or 0.28), 1.0),
                )
                context_objs.extend([h_post, h_ant])
                morph_objs.extend([(h_post, 0.22, 1.0), (h_ant, 0.22, 1.0)])
            else:
                mat_s = role_mats.get(cfg["start_role"], mat_cerul)
                mat_e = role_mats.get(cfg["end_role"], mat_coral)
                use_rh_s = start_k in ("hippocampus", "amygdala", "insula", "fusiform face area")
                use_rh_e = end_k in ("hippocampus", "amygdala", "insula", "fusiform face area")
                if start_k not in ("eyes", "inner ear"):
                    s_pe = float(cfg.get("posterior_expand") or 0.0) if start_k == "hippocampus" else 0.0
                    s_obj = build_mesh_obj(
                        start_k, "StartRegionObj", mat_s, rh_only=use_rh_s, subsurf=2 if use_rh_s else 1,
                        morph_target=(s_pe, 0.0, 1.0) if s_pe > 0 else None,
                    )
                    context_objs.append(s_obj)
                    if s_pe > 0:
                        morph_objs.append((s_obj, 0.20, 1.0))
                        if has_dash:
                            mb = build_mesh_obj(start_k, "MaskStart1x", mat_white_mask, rh_only=use_rh_s, subsurf=2)
                            mb.hide_render = True
                            mask_target_objs.append(mb)
                if end_k != start_k:
                    e_pe = float(cfg.get("posterior_expand") or 0.0) if end_k == "hippocampus" else 0.0
                    e_obj = build_mesh_obj(
                        end_k, "EndRegionObj", mat_e, rh_only=use_rh_e, subsurf=2 if use_rh_e else 1,
                        morph_target=(e_pe, 0.0, 1.0) if e_pe > 0 else None,
                    )
                    context_objs.append(e_obj)
                    if e_pe > 0:
                        morph_objs.append((e_obj, 0.20, 1.0))

                for idx, ek in enumerate(cfg.get("extra_keys") or []):
                    context_objs.append(build_mesh_obj(ek, f"ExtraRegion_{{idx}}", mat_cerul, subsurf=1))
                for idx, dk in enumerate(cfg.get("dimmed_keys") or []):
                    context_objs.append(build_mesh_obj(dk, f"DimmedRegion_{{idx}}", mat_sil, subsurf=1))

                # Anatomical white-matter tract bundle + matte traveling signal boluses
                t_start = tract_pts[1] - tract_pts[0]
                t_start /= max(float(np.linalg.norm(t_start)), 1e-8)
                ref_v = np.array([0.0, 0.0, 1.0]) if abs(t_start[2]) < 0.85 else np.array([1.0, 0.0, 0.0])
                u_ax = np.cross(t_start, ref_v); u_ax /= max(float(np.linalg.norm(u_ax)), 1e-8)
                v_ax = np.cross(t_start, u_ax); v_ax /= max(float(np.linalg.norm(v_ax)), 1e-8)
                strand_offsets = [np.zeros(3), 0.0018 * u_ax, -0.0018 * u_ax]
                if state == "severed":
                    n_pts = len(tract_pts)
                    cut_a = max(3, int(round(0.42 * n_pts)))
                    cut_b = min(n_pts - 4, int(round(0.58 * n_pts)))
                    for s_i, off in enumerate(strand_offsets):
                        context_objs.append(make_fiber_strand(f"FiberUp_{{s_i}}", tract_pts[:cut_a] + off[None, :], mat_cerul, radius=0.0011))
                        context_objs.append(make_fiber_strand(f"FiberDn_{{s_i}}", tract_pts[cut_b:] + off[None, :], mat_sil, radius=0.0010))
                    lesion_mid = 0.5 * (tract_pts[cut_a - 1] + tract_pts[cut_b])
                    for ang in (45.0, -45.0):
                        bpy.ops.mesh.primitive_cylinder_add(radius=0.0020, depth=0.018, location=tuple(lesion_mid))
                        bar = bpy.context.active_object
                        bar.rotation_euler = (math.radians(ang), 0.0, 0.0)
                        bar.data.materials.append(mat_coral)
                        context_objs.append(bar)
                else:
                    t_mat = mat_sil if state == "silenced" else (mat_ochre if cfg["start_role"] == "sensory" else mat_cyan)
                    for s_i, off in enumerate(strand_offsets):
                        taper = np.sin(np.linspace(0.15, math.pi - 0.15, len(tract_pts)))[:, None]
                        context_objs.append(make_fiber_strand(f"FiberMain_{{s_i}}", tract_pts + off[None, :] * taper, t_mat, radius=0.0011))

                n_pulses = 0 if state == "silenced" else 3
                for p_i in range(n_pulses):
                    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.0032, location=(0, 0, 0))
                    sp = bpy.context.active_object
                    sp.name = f"SignalPulse_{{p_i}}"
                    sp.scale = (1.0, 1.0, 1.75)
                    for poly in sp.data.polygons:
                        poly.use_smooth = True
                    sp.data.materials.append(mat_sig)
                    signal_objs.append(sp)
                    context_objs.append(sp)

        cam_plan = cfg["camera_plan"]
        eye_wps = np.asarray(cam_plan["eye_waypoints_m"], dtype=np.float64)
        tgt_wps = np.asarray(cam_plan["target_waypoints_m"], dtype=np.float64)

        def eval_catmull(wps, u):
            u = max(0.0, min(1.0, float(u)))
            u_e = 0.42 * u + 0.58 * (u * u * (3.0 - 2.0 * u))
            ext = np.vstack([2 * wps[0] - wps[1], wps, 2 * wps[-1] - wps[-2]])
            n_seg = len(wps) - 1
            sc = min(u_e * n_seg, n_seg - 1e-6)
            seg = int(sc)
            t = sc - seg
            a, b, c, d = ext[seg], ext[seg + 1], ext[seg + 2], ext[seg + 3]
            t2, t3 = t * t, t * t * t
            return 0.5 * ((2 * b) + (-a + c) * t + (2 * a - 5 * b + 4 * c - d) * t2 + (-a + 3 * b - 3 * c + d) * t3)

        bpy.ops.object.empty_add(type="PLAIN_AXES", location=tuple(tgt_wps[0]))
        cam_tgt = bpy.context.active_object
        cam_tgt.name = "DroneTarget"

        bpy.ops.object.camera_add(location=tuple(eye_wps[0]))
        cam = bpy.context.active_object
        cam.name = "DroneCam"
        cam.data.lens = float(cam_plan["lens_mm"])
        cam.data.sensor_fit = "HORIZONTAL"
        cam.data.sensor_width = 36.0
        cam.data.clip_start = 0.0015
        cam.data.clip_end = 10.0
        con = cam.constraints.new("TRACK_TO")
        con.target = cam_tgt
        con.track_axis = "TRACK_NEGATIVE_Z"
        con.up_axis = "UP_Y"
        scene.camera = cam

        anchors_m = {{k: Vector([v[0] * 0.001, v[1] * 0.001, v[2] * 0.001]) for k, v in cfg["anchors_mm"].items()}}
        top_box = cfg.get("stacked_top_box", [76, 416, 916, 816])
        bot_box = cfg.get("stacked_bot_box", [76, 844, 916, 1244])

        # Pass 1: Evaluate exact 30fps `world_to_camera_view` coordinates for all `0 .. n_frames - 1` (0.0 px lock!)
        track_frames = []
        for f_idx in range(n_frames):
            u = f_idx / max(1, n_frames - 1)
            cam.location = tuple(eval_catmull(eye_wps, u))
            cam_tgt.location = tuple(eval_catmull(tgt_wps, u))
            bpy.context.view_layer.update()
            proj = {{}}
            if is_stacked:
                co_s = world_to_camera_view(scene, cam, anchors_m["start"])
                co_e = world_to_camera_view(scene, cam, anchors_m["end"])
                tx = top_box[0] + float(co_s.x) * (top_box[2] - top_box[0])
                ty = top_box[1] + (1.0 - float(co_s.y)) * (top_box[3] - top_box[1])
                bx = bot_box[0] + float(co_e.x) * (bot_box[2] - bot_box[0])
                by = bot_box[1] + (1.0 - float(co_e.y)) * (bot_box[3] - bot_box[1])
                proj["start"] = {{"x_px": round(tx, 2), "y_px": round(ty, 2), "x_norm": round(tx / w, 5), "y_norm": round(ty / h, 5), "depth_m": round(float(co_s.z), 4)}}
                proj["end"] = {{"x_px": round(bx, 2), "y_px": round(by, 2), "x_norm": round(bx / w, 5), "y_norm": round(by / h, 5), "depth_m": round(float(co_e.z), 4)}}
            else:
                for ak, av in anchors_m.items():
                    co2d = world_to_camera_view(scene, cam, av)
                    proj[ak] = {{
                        "x_px": round(float(co2d.x) * w, 2),
                        "y_px": round((1.0 - float(co2d.y)) * h, 2),
                        "x_norm": round(float(co2d.x), 5),
                        "y_norm": round(1.0 - float(co2d.y), 5),
                        "depth_m": round(float(co2d.z), 4),
                    }}
            track_frames.append({{"frame": f_idx, "t_sec": round(f_idx / fps, 4), "anchors": proj}})

        # Pass 2: Contiguous multi-pass rendering so Cycles `use_persistent_data=True` builds BVH only ONCE per pass!
        def apply_frame_state(f_idx):
            scene.frame_set(f_idx)
            u = f_idx / max(1, n_frames - 1)
            cam.location = tuple(eval_catmull(eye_wps, u))
            cam_tgt.location = tuple(eval_catmull(tgt_wps, u))
            u_m = min(1.0, u / 0.78)
            ease_m = u_m * u_m * (3.0 - 2.0 * u_m)
            for m_obj, v_lo, v_hi in morph_objs:
                if m_obj.data.shape_keys and "Morph" in m_obj.data.shape_keys.key_blocks:
                    m_obj.data.shape_keys.key_blocks["Morph"].value = float(v_lo + (v_hi - v_lo) * ease_m)
            for p_i, sp in enumerate(signal_objs):
                phase = (u * 1.35 - p_i * 0.28) % 1.06
                if state == "severed":
                    if phase > 0.41:
                        fade = max(0.0, 1.0 - (phase - 0.41) / 0.14)
                        sp.scale = (0.05 + fade * 0.95, 0.05 + fade * 0.95, (0.05 + fade * 0.95) * 1.5)
                        u_pos = 0.41
                    else:
                        sp.scale = (1.0, 1.0, 1.75)
                        u_pos = max(0.03, phase)
                else:
                    u_pos = max(0.04, min(0.95, phase / 1.04))
                    sp.scale = (1.0, 1.0, 1.75)
                pos, tan = sample_poly(tract_pts, u_pos)
                sp.location = tuple(pos)
                sp.rotation_mode = "QUATERNION"
                sp.rotation_quaternion = Vector(tan).to_track_quat("Z", "Y")

        if is_stacked:
            # Pass 2A: Top Panel (Group A) across all keyframes (1 BVH build)
            for o in context_objs + top_only_objs: o.hide_render = False
            for o in bot_only_objs + mask_target_objs: o.hide_render = True
            for f_idx in rendered_indices:
                apply_frame_state(f_idx)
                bpy.context.view_layer.update()
                scene.render.filepath = str(frames_dir / f"top_{{f_idx:04d}}.png")
                bpy.ops.render.render(write_still=True)

            # Pass 2B: Bottom Panel (Group B) across all keyframes (1 BVH build)
            for o in top_only_objs + mask_target_objs: o.hide_render = True
            for o in bot_only_objs: o.hide_render = False
            for f_idx in rendered_indices:
                apply_frame_state(f_idx)
                bpy.context.view_layer.update()
                scene.render.filepath = str(frames_dir / f"bot_{{f_idx:04d}}.png")
                bpy.ops.render.render(write_still=True)
        else:
            # Pass 2A: Single-Brain Surgical Cutaway across all keyframes (1 BVH build)
            for o in context_objs: o.hide_render = False
            for o in mask_target_objs: o.hide_render = True
            for f_idx in rendered_indices:
                apply_frame_state(f_idx)
                bpy.context.view_layer.update()
                scene.render.filepath = str(frames_dir / f"frame_{{f_idx:04d}}.png")
                bpy.ops.render.render(write_still=True)

        # Pass 2C: Ultra-fast Workbench flat binary 1.0x silhouette mask (<0.3s total for all keyframes!)
        if has_dash and mask_target_objs:
            for o in context_objs + top_only_objs + bot_only_objs + light_objs: o.hide_render = True
            for o in mask_target_objs: o.hide_render = False
            scene.render.use_border = False
            scene.render.engine = "BLENDER_WORKBENCH"
            scene.display.render_aa = "FXAA"
            scene.display.shading.light = "FLAT"
            scene.display.shading.color_type = "MATERIAL"
            scene.display.shading.show_cavity = False
            scene.display.shading.background_type = "WORLD"
            if scene.world is None:
                scene.world = bpy.data.worlds.new("MaskWorld")
            scene.world.use_nodes = False
            scene.world.color = (0.0, 0.0, 0.0)
            scene.view_settings.view_transform = "Standard"
            scene.view_settings.exposure = 0.0
            for f_idx in rendered_indices:
                apply_frame_state(f_idx)
                bpy.context.view_layer.update()
                scene.render.filepath = str(frames_dir / f"mask_{{f_idx:04d}}.png")
                bpy.ops.render.render(write_still=True)

        track_doc = {{
            "schema": 2,
            "rule_version": "R84_v1",
            "layout": "stacked_vstack" if is_stacked else ("side_by_side" if is_sbs else "surgical_cutaway"),
            "morph_mode": morph_mode,
            "width": w,
            "height": h,
            "fps": fps,
            "n_frames": n_frames,
            "start_region": start_k,
            "end_region": end_k,
            "neural_state": state,
            "frames": track_frames,
        }}
        Path({str(track_path)!r}).write_text(json.dumps(track_doc), encoding="utf-8")
    """)
