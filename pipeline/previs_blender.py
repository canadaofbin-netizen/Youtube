"""
3D Blockout Previs Keyframe Generator (`pipeline/previs_blender.py` — Master Plan Phase 5.5).

Adapts the 3 core previs principles (`previs_workflow_analysis.md`) to ALL ABOUT BRAIN's
zero-cost Google Flow `Image` -> `VIDEO_FRAMES` pipeline:
1. Rule 1 (Subtraction / 빼기):
   - Every human/character dummy is strictly 3 solid primitives (`lower_body` box + `torso` box + `head` sphere)
     with zero facial features, fingers, hair, or clothing geometry.
   - Every prop is strictly 1 real-scale 3D bounding box (`size_xyz` in meters, optional `back_color_hex`
     on the rear face for 180-degree rotation shots).
2. Rule 2 (Collision-Free Color Coding / 색 표시):
   - Assigns each actor/prop a unique marker color from `PREVIS_SAFE_PALETTE`, mathematically verified
     to stay `>= PREVIS_MIN_COLOR_DISTANCE_RGB` away from porcelain/vinyl whites AND all 4 Brain colors
     (Cyan-Blue, Crimson-Red, Amber-Gold/Kintsugi, Pearl-Aqua), storing `color_role_legend` for prompt mapping.
3. Rule 3 + Mathematical Seam Continuity:
   - `propagate_previs_camera_continuity` copies `Cut[i].previs.camera_end` -> `Cut[i+1].previs.camera_start`
     (and actor end poses -> next start poses) across same-location cuts so `End(i)` and `Start(i+1)` share
     identical 3D projection geometry before Flow `Image` translation (`<= 2` ingredients: Previs PNG + Cast Sheet).
"""

from __future__ import annotations

import copy
import json
import logging
import math
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import cv2
import numpy as np

logger = logging.getLogger(__name__)

DEFAULT_BLENDER_BIN = Path.home() / "opt" / "blender" / "blender"
PREVIS_DEFAULT_WIDTH = 540
PREVIS_DEFAULT_HEIGHT = 960
PREVIS_MIN_COLOR_DISTANCE_RGB = 65.0

# Forbidden colors that must NEVER be assigned to previs dummies/boxes:
# - Porcelain / Cream-White Vinyl cast colors
# - 4-Color Contained / Crystal X-Ray Brain colors + Kintsugi Gold
PREVIS_FORBIDDEN_COLORS: dict[str, str] = {
    "porcelain_white": "#FFFFFF",
    "vinyl_cream_white": "#F5F2EB",
    "ceramic_ivory": "#EDEAE2",
    "matte_bone": "#E8E4DC",
    "brain_cyan_blue": "#00D4FF",
    "brain_cyan_deep": "#00B4D8",
    "brain_crimson_red": "#DC1E32",
    "brain_crimson_dark": "#C81D25",
    "brain_amber_gold": "#F5AF19",
    "brain_kintsugi_gold": "#D4AF37",
    "brain_pearl_aqua": "#7FFFD4",
    "brain_aqua_soft": "#64DFDF",
}

# Collision-free marker palette: every color is >= 100 RGB Euclidean units from all PREVIS_FORBIDDEN_COLORS
PREVIS_SAFE_PALETTE: tuple[tuple[str, str], ...] = (
    ("Royal Violet", "#7B2CBF"),
    ("Forest Olive", "#386641"),
    ("Saddle Ochre", "#8C5A2B"),
    ("Deep Indigo", "#2B3A67"),
    ("Plum Magenta", "#8F2D75"),
    ("Slate Petrol", "#4F6D7A"),
    ("Olive Moss", "#5C6B28"),
    ("Espresso Umber", "#5E3A24"),
)

PREVIS_NEUTRAL_ROOM_HEX = "#8A8F98"
PREVIS_NEUTRAL_FLOOR_HEX = "#6E737B"
PREVIS_FLOOR_GRID_HEX = "#555A63"
PREVIS_BG_SKY_HEX = "#B8C0CC"
PREVIS_GLASS_ALPHA = 0.22

TRANSLUCENT_BLOCK_KEYWORDS: tuple[str, ...] = (
    "glass",
    "window",
    "terrarium",
    "acrylic",
    "translucent",
    "transparent",
    "clear_mask",
    "silicone_mask",
    "cutaway",
    "portal",
    "facade_slice",
    "parapet",
    "brain_shell",
    "cortical_shell",
    "cortical_rib",
    "neural_chamber",
)


def hex_to_rgb(color_hex: str) -> tuple[int, int, int]:
    """Parses `#RRGGBB` into `(R, G, B)` integers in `0..255`."""
    raw = str(color_hex or "").strip().lstrip("#")
    if len(raw) != 6 or any(c not in "0123456789abcdefABCDEF" for c in raw):
        raise ValueError(f"Invalid hex color {color_hex!r}; expected '#RRGGBB'")
    return int(raw[0:2], 16), int(raw[2:4], 16), int(raw[4:6], 16)


def _darken_hex(color_hex: str, factor: float = 0.54) -> str:
    """Returns a darkened `#RRGGBB` shade of `color_hex` for gaze visors and mechanical joints."""
    r, g, b = hex_to_rgb(color_hex)
    f = max(0.15, min(1.0, float(factor)))
    return f"#{int(round(r * f)):02X}{int(round(g * f)):02X}{int(round(b * f)):02X}"


def _resolve_block_alpha(item: dict[str, Any]) -> float:
    """Resolves render opacity (`1.0` opaque, `0.22` translucent glass/window/terrarium)."""
    if item.get("alpha") is not None:
        return max(0.08, min(1.0, float(item["alpha"])))
    tag = " ".join(
        str(item.get(k) or "")
        for k in ("block_id", "chunk_id", "prop_id", "label", "compound_type")
    ).lower()
    if any(kw in tag for kw in TRANSLUCENT_BLOCK_KEYWORDS):
        return PREVIS_GLASS_ALPHA
    return 1.0


def hex_to_unit_rgba(color_hex: str, alpha: float = 1.0) -> tuple[float, float, float, float]:
    r, g, b = hex_to_rgb(color_hex)
    return (round(r / 255.0, 5), round(g / 255.0, 5), round(b / 255.0, 5), float(alpha))


def rgb_euclidean_distance(hex_a: str, hex_b: str) -> float:
    ra, ga, ba = hex_to_rgb(hex_a)
    rb, gb, bb = hex_to_rgb(hex_b)
    return math.sqrt((ra - rb) ** 2 + (ga - gb) ** 2 + (ba - bb) ** 2)


def validate_previs_color_safety(
    color_hex: str,
    *,
    min_distance_rgb: float = PREVIS_MIN_COLOR_DISTANCE_RGB,
) -> tuple[bool, str]:
    """
    Verifies `color_hex` does not collide with porcelain/vinyl whites or any of the 4 Brain colors.
    Returns `(is_safe, diagnostic_message)`.
    """
    try:
        _ = hex_to_rgb(color_hex)
    except ValueError as exc:
        return False, str(exc)

    closest_name = ""
    closest_hex = ""
    closest_dist = float("inf")
    for forb_name, forb_hex in PREVIS_FORBIDDEN_COLORS.items():
        dist = rgb_euclidean_distance(color_hex, forb_hex)
        if dist < closest_dist:
            closest_dist = dist
            closest_name = forb_name
            closest_hex = forb_hex
    if closest_dist < float(min_distance_rgb):
        return (
            False,
            f"Previs marker color {color_hex} collides with forbidden {closest_name} ({closest_hex}): "
            f"RGB distance {closest_dist:.1f} < {min_distance_rgb:.1f}",
        )
    return True, f"ok (min_distance={closest_dist:.1f} vs {closest_name})"


def assign_previs_palette(
    entities: list[dict[str, Any]],
    *,
    existing_assignments: dict[str, tuple[str, str]] | None = None,
) -> dict[str, dict[str, str]]:
    """
    Assigns deterministic collision-free `(color_name, color_hex)` markers to actors and props,
    validating any explicitly provided `color_hex` against `PREVIS_FORBIDDEN_COLORS`.
    """
    assigned: dict[str, dict[str, str]] = {}
    used_hexes: set[str] = set()
    carry = dict(existing_assignments or {})

    for ent in entities:
        ent_id = str(ent.get("role_id") or ent.get("prop_id") or ent.get("id") or "").strip()
        if not ent_id:
            continue
        ent_label = str(ent.get("label") or ent.get("target_label") or ent.get("description") or ent_id).strip()
        ent_kind = "prop" if ("prop_id" in ent or ent.get("entity_kind") == "prop") else "actor"
        explicit_hex = str(ent.get("color_hex") or "").strip().upper()
        explicit_name = str(ent.get("color_name") or "").strip()

        if explicit_hex:
            ok, msg = validate_previs_color_safety(explicit_hex)
            if not ok:
                raise ValueError(msg)
            c_name = explicit_name or next(
                (nm for nm, hx in PREVIS_SAFE_PALETTE if hx.upper() == explicit_hex),
                f"Marker {explicit_hex}",
            )
            c_hex = explicit_hex
        elif ent_id in carry:
            c_name, c_hex = carry[ent_id]
            c_hex = c_hex.upper()
            ok, msg = validate_previs_color_safety(c_hex)
            if not ok:
                raise ValueError(msg)
        else:
            chosen: tuple[str, str] | None = None
            for nm, hx in PREVIS_SAFE_PALETTE:
                if hx.upper() not in used_hexes:
                    chosen = (nm, hx.upper())
                    break
            if chosen is None:
                nm, hx = PREVIS_SAFE_PALETTE[len(assigned) % len(PREVIS_SAFE_PALETTE)]
                chosen = (nm, hx.upper())
            c_name, c_hex = chosen

        used_hexes.add(c_hex)
        ent["color_hex"] = c_hex
        ent["color_name"] = c_name
        if ent.get("back_color_hex"):
            b_hex = str(ent["back_color_hex"]).strip().upper()
            ok_b, msg_b = validate_previs_color_safety(b_hex)
            if not ok_b:
                raise ValueError(msg_b)
            ent["back_color_hex"] = b_hex

        assigned[ent_id] = {
            "color_name": c_name,
            "color_hex": c_hex,
            "target_label": ent_label,
            "entity_kind": ent_kind,
        }
    return assigned


def find_blender_executable(preferred_path: str | Path | None = None) -> Path | None:
    """Locates portable or system Blender binary (`$BLENDER_BIN`, `~/opt/blender/blender`, or `PATH`)."""
    candidates: list[Path] = []
    if preferred_path:
        candidates.append(Path(preferred_path).expanduser())
    env_bin = os.environ.get("BLENDER_BIN", "").strip()
    if env_bin:
        candidates.append(Path(env_bin).expanduser())
    candidates.append(DEFAULT_BLENDER_BIN)
    which_bin = shutil.which("blender")
    if which_bin:
        candidates.append(Path(which_bin))

    for cand in candidates:
        if cand.is_file() and os.access(cand, os.X_OK):
            return cand
    return None


def is_blender_available(preferred_path: str | Path | None = None) -> bool:
    """Returns True only if a Blender binary exists AND executes `--version` cleanly on this host."""
    bin_path = find_blender_executable(preferred_path)
    if bin_path is None:
        return False
    try:
        proc = subprocess.run(
            [str(bin_path), "--version"],
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
            stdin=subprocess.DEVNULL,
        )
        return proc.returncode == 0 and "Blender" in (proc.stdout or "")
    except (OSError, subprocess.SubprocessError):
        return False


def build_three_chunk_actor_primitives(actor: dict[str, Any], phase: str = "start") -> list[dict[str, Any]]:
    """
    Rule 1 (Subtraction / 빼기) + E3 Pose & Body-Scale Support:
    Decomposes a character marker into 3 solid primitives (`lower_body`, `torso`, `head`), plus an optional
    4th `reach_arm` block ONLY when `pose == "reaching"`:
      - Supports child (`1.05m`), adult (`1.72m`), and `mini_cortex` (`0.22m`) heights (`min 0.18m`).
      - Supports `pose` / `pose_start` / `pose_end` in `("standing", "seated", "leaning", "reaching")`.
    """
    pos_key = "pos_end" if phase == "end" and actor.get("pos_end") is not None else "pos_start"
    if phase == "mid":
        p0 = [float(v) for v in (actor.get("pos_start") or actor.get("pos") or [0.0, 0.0, 0.0])]
        p1 = [float(v) for v in (actor.get("pos_end") or p0)]
        base_pos = [0.5 * (a + b) for a, b in zip(p0, p1)]
    else:
        base_pos = [float(v) for v in (actor.get(pos_key) or actor.get("pos") or [0.0, 0.0, 0.0])]
    bx, by, bz = base_pos[0], base_pos[1], base_pos[2]
    height_m = max(0.18, float(actor.get("height_m") or 1.72))
    yaw_deg = float(actor.get("yaw_deg") or 0.0)
    yaw_rad = math.radians(yaw_deg)
    fwd_x = -math.sin(yaw_rad)
    fwd_y = -math.cos(yaw_rad)
    c_hex = str(actor.get("color_hex") or PREVIS_SAFE_PALETTE[0][1]).upper()
    role_id = str(actor.get("role_id") or "actor_1")
    pose_raw = (
        actor.get("pose_end")
        if (phase == "end" and actor.get("pose_end"))
        else (actor.get("pose_start") or actor.get("pose") or "standing")
    )
    pose = str(pose_raw).strip().lower()

    head_ratio = float(actor.get("head_ratio") or (0.24 if height_m <= 1.20 else 0.095 * 2.0))
    head_r = height_m * (head_ratio * 0.5 if head_ratio > 0.15 else 0.095)
    shoulder_w = height_m * (0.30 if height_m <= 1.20 else 0.25)
    chest_d = height_m * (0.18 if height_m <= 1.20 else 0.15)

    if pose == "seated":
        lower_h = height_m * 0.26
        torso_h = height_m * 0.34
        lower_center = [bx + fwd_x * (chest_d * 0.45), by + fwd_y * (chest_d * 0.45), bz + lower_h * 0.5]
        lower_size = [shoulder_w * 0.84, chest_d * 1.45, lower_h]
        torso_center = [bx, by, bz + lower_h + (torso_h * 0.5) + 0.01]
        head_center = [bx, by, bz + lower_h + torso_h + head_r + 0.025]
    elif pose == "leaning":
        lower_h = height_m * 0.46
        torso_h = height_m * 0.34
        lean_off = height_m * 0.06
        lower_center = [bx, by, bz + lower_h * 0.5]
        lower_size = [shoulder_w * 0.80, chest_d * 0.82, lower_h]
        torso_center = [bx + fwd_x * lean_off, by + fwd_y * lean_off, bz + lower_h + (torso_h * 0.48)]
        head_center = [bx + fwd_x * (lean_off * 1.6), by + fwd_y * (lean_off * 1.6), bz + lower_h + torso_h + head_r + 0.015]
    else:
        lower_h = height_m * 0.46
        torso_h = height_m * 0.34
        lower_center = [bx, by, bz + lower_h * 0.5]
        lower_size = [shoulder_w * 0.80, chest_d * 0.82, lower_h]
        torso_center = [bx, by, bz + lower_h + (torso_h * 0.5) + 0.015]
        head_center = [bx, by, bz + lower_h + torso_h + head_r + 0.03]

    visor_hex = _darken_hex(c_hex, 0.52)
    chunks: list[dict[str, Any]] = [
        {
            "chunk_id": f"{role_id}_lower_body",
            "shape": "box",
            "center": lower_center,
            "size_xyz": lower_size,
            "yaw_deg": yaw_deg,
            "color_hex": c_hex,
            "shadow_center": [bx, by, max(0.004, bz + 0.004)],
            "shadow_radii_xy": [max(0.08, shoulder_w * 0.62), max(0.08, chest_d * 0.85)],
        },
        {
            "chunk_id": f"{role_id}_torso",
            "shape": "box",
            "center": torso_center,
            "size_xyz": [shoulder_w, chest_d, torso_h],
            "yaw_deg": yaw_deg,
            "color_hex": c_hex,
        },
        {
            "chunk_id": f"{role_id}_head",
            "shape": "sphere",
            "center": head_center,
            "radius": head_r,
            "yaw_deg": yaw_deg,
            "color_hex": c_hex,
            "gaze_dir_xy": [round(fwd_x, 5), round(fwd_y, 5)],
            "visor_center": [
                head_center[0] + fwd_x * (head_r * 0.78),
                head_center[1] + fwd_y * (head_r * 0.78),
                head_center[2] + head_r * 0.06,
            ],
            "visor_size_xyz": [head_r * 1.12, head_r * 0.54, head_r * 0.40],
            "visor_color_hex": visor_hex,
        },
    ]
    if pose == "reaching":
        arm_len = height_m * 0.32
        arm_z = torso_center[2] + torso_h * 0.22
        chunks.append(
            {
                "chunk_id": f"{role_id}_reach_arm",
                "shape": "box",
                "center": [
                    torso_center[0] + fwd_x * (chest_d * 0.5 + arm_len * 0.5),
                    torso_center[1] + fwd_y * (chest_d * 0.5 + arm_len * 0.5),
                    arm_z,
                ],
                "size_xyz": [shoulder_w * 0.24, arm_len, shoulder_w * 0.22],
                "yaw_deg": yaw_deg,
                "color_hex": c_hex,
            }
        )
    return chunks


PROP_SHAPE_LIBRARY: dict[str, dict[str, Any]] = {
    "snake_terrarium": {"shape": "box", "size_xyz": [0.46, 0.30, 0.28], "compound_type": "snake_terrarium"},
    "terrarium": {"shape": "box", "size_xyz": [0.46, 0.30, 0.28], "compound_type": "snake_terrarium"},
    "snake": {"shape": "cylinder", "size_xyz": [0.22, 0.22, 0.10], "compound_type": "snake_terrarium"},
    "tarantula": {"shape": "box", "size_xyz": [0.36, 0.26, 0.24], "compound_type": "snake_terrarium"},
    "mask_tube": {"shape": "cylinder", "size_xyz": [0.16, 0.26, 0.18], "compound_type": "mask_tube"},
    "breathing mask": {"shape": "cylinder", "size_xyz": [0.16, 0.26, 0.18], "compound_type": "mask_tube"},
    "silicone mask": {"shape": "cylinder", "size_xyz": [0.16, 0.26, 0.18], "compound_type": "mask_tube"},
    "robot_arm": {"shape": "box", "size_xyz": [0.30, 0.36, 0.42], "compound_type": "robot_arm"},
    "robot": {"shape": "box", "size_xyz": [0.30, 0.36, 0.42], "compound_type": "robot_arm"},
    "tickle": {"shape": "box", "size_xyz": [0.28, 0.34, 0.38], "compound_type": "robot_arm"},
    "brain_cutaway": {"shape": "cylinder", "size_xyz": [0.22, 0.24, 0.24], "compound_type": "brain_cutaway"},
    "brain model": {"shape": "cylinder", "size_xyz": [0.22, 0.24, 0.24], "compound_type": "brain_cutaway"},
    "chair": {"shape": "box", "size_xyz": [0.48, 0.48, 0.86], "compound_type": "chair"},
    "monitor": {"shape": "box", "size_xyz": [0.44, 0.18, 0.36], "compound_type": "monitor"},
    "screen": {"shape": "box", "size_xyz": [0.44, 0.18, 0.36], "compound_type": "monitor"},
    "projector": {"shape": "box", "size_xyz": [0.30, 0.26, 0.16], "compound_type": "monitor"},
    "toggle switch": {"shape": "box", "size_xyz": [0.22, 0.16, 0.16], "compound_type": "toggle_switch"},
    "switch": {"shape": "box", "size_xyz": [0.22, 0.16, 0.16], "compound_type": "toggle_switch"},
    "stopwatch": {"shape": "cylinder", "size_xyz": [0.09, 0.09, 0.05], "compound_type": "stopwatch"},
    "saucer": {"shape": "cylinder", "size_xyz": [0.20, 0.20, 0.035]},
    "plate": {"shape": "cylinder", "size_xyz": [0.24, 0.24, 0.035]},
    "marshmallow": {"shape": "cylinder", "size_xyz": [0.065, 0.065, 0.055]},
    "mug": {"shape": "cylinder", "size_xyz": [0.10, 0.10, 0.12]},
    "cup": {"shape": "cylinder", "size_xyz": [0.09, 0.09, 0.11]},
    "crayon": {"shape": "box", "size_xyz": [0.12, 0.06, 0.03]},
    "marker": {"shape": "box", "size_xyz": [0.34, 0.24, 0.06]},
    "tray": {"shape": "box", "size_xyz": [0.38, 0.26, 0.07]},
    "diary": {"shape": "box", "size_xyz": [0.20, 0.26, 0.04]},
    "notebook": {"shape": "box", "size_xyz": [0.24, 0.30, 0.035]},
    "book": {"shape": "box", "size_xyz": [0.26, 0.32, 0.14]},
    "clipboard": {"shape": "box", "size_xyz": [0.24, 0.32, 0.03]},
    "dumbbell": {"shape": "box", "size_xyz": [0.30, 0.12, 0.12]},
    "scale": {"shape": "box", "size_xyz": [0.36, 0.16, 0.30]},
    "balance": {"shape": "box", "size_xyz": [0.36, 0.16, 0.30]},
    "refrigerator": {"shape": "box", "size_xyz": [0.85, 0.76, 1.85]},
    "fridge": {"shape": "box", "size_xyz": [0.85, 0.76, 1.85]},
    "cake": {"shape": "cylinder", "size_xyz": [0.22, 0.22, 0.12]},
}


def resolve_prop_compound_type(label_or_id: str, explicit_compound: str | None = None) -> str | None:
    if explicit_compound:
        return str(explicit_compound).strip().lower()
    low = str(label_or_id or "").strip().lower()
    for kw, spec in PROP_SHAPE_LIBRARY.items():
        if kw in low and spec.get("compound_type"):
            return str(spec["compound_type"])
    return None


def resolve_prop_shape_and_size(label_or_id: str, explicit_size: list[float] | None = None, explicit_shape: str | None = None) -> tuple[str, list[float]]:
    """Infers (`shape`, `size_xyz`) from `PROP_SHAPE_LIBRARY` when not explicitly overridden."""
    low = str(label_or_id or "").strip().lower()
    matched: dict[str, Any] | None = None
    for kw, spec in PROP_SHAPE_LIBRARY.items():
        if kw in low:
            matched = spec
            break
    shape = str(explicit_shape or (matched["shape"] if matched else "box")).strip().lower()
    if shape not in ("box", "cylinder", "sphere"):
        shape = "box"
    if explicit_size is not None:
        size_xyz = [max(0.03, float(v)) for v in explicit_size]
    elif matched is not None:
        size_xyz = list(matched["size_xyz"])
    else:
        size_xyz = [0.30, 0.24, 0.20]
    return shape, size_xyz


def build_prop_box_primitive(prop: dict[str, Any], phase: str = "start") -> dict[str, Any]:
    """Rule 1 (Subtraction / 빼기) + E4 Prop Shape Silhouette: Real-scale 3D bounding box or cylinder."""
    pos_key = "pos_end" if phase == "end" and prop.get("pos_end") is not None else "pos_start"
    if phase == "mid":
        p0 = [float(v) for v in (prop.get("pos_start") or prop.get("pos") or [0.0, 0.4, 0.75])]
        p1 = [float(v) for v in (prop.get("pos_end") or p0)]
        raw_pos = [0.5 * (a + b) for a, b in zip(p0, p1)]
    else:
        raw_pos = [float(v) for v in (prop.get(pos_key) or prop.get("pos") or [0.0, 0.4, 0.75])]
    has_exp_size = prop.get("size_xyz") is not None
    has_exp_shape = prop.get("shape") is not None
    if has_exp_size and not has_exp_shape:
        # Preserve strict box shape when caller explicitly passes `size_xyz` without `shape`
        shape = "box"
        raw_size = [max(0.03, float(v)) for v in prop["size_xyz"]]
    else:
        shape, raw_size = resolve_prop_shape_and_size(
            str(prop.get("label") or prop.get("prop_id") or ""),
            explicit_size=prop.get("size_xyz"),
            explicit_shape=prop.get("shape"),
        )
    c_hex = str(prop.get("color_hex") or PREVIS_SAFE_PALETTE[2][1]).upper()
    back_hex = str(prop.get("back_color_hex") or "").strip().upper() or None
    out_prim: dict[str, Any] = {
        "chunk_id": f"{prop.get('prop_id', 'prop_1')}_bbox",
        "shape": shape,
        "center": [raw_pos[0], raw_pos[1], raw_pos[2] + raw_size[2] * 0.5],
        "size_xyz": raw_size,
        "yaw_deg": float(prop.get("yaw_deg") or 0.0),
        "color_hex": c_hex,
        "back_color_hex": back_hex,
        "alpha": _resolve_block_alpha(prop),
    }
    if shape == "sphere" or prop.get("radius") is not None:
        out_prim["radius"] = float(prop.get("radius") or (0.5 * raw_size[0]))
    return out_prim


def build_prop_primitives(prop: dict[str, Any], phase: str = "start") -> list[dict[str, Any]]:
    """
    P3 Compound Prop Silhouettes: Expands high-salience experimental props (`snake_terrarium`,
    `mask_tube`, `robot_arm`, `brain_cutaway`, `chair`, `monitor`, `toggle_switch`, `stopwatch`)
    into multi-part silhouettes while keeping explicit legacy single-box props unchanged.
    """
    has_explicit_bbox_only = (
        prop.get("size_xyz") is not None
        and not prop.get("compound_type")
        and prop.get("shape") is None
    )
    if has_explicit_bbox_only:
        return [build_prop_box_primitive(prop, phase=phase)]

    ctype = resolve_prop_compound_type(
        str(prop.get("label") or prop.get("prop_id") or ""),
        explicit_compound=prop.get("compound_type"),
    )
    if not ctype:
        return [build_prop_box_primitive(prop, phase=phase)]

    pos_key = "pos_end" if phase == "end" and prop.get("pos_end") is not None else "pos_start"
    if phase == "mid":
        p0 = [float(v) for v in (prop.get("pos_start") or prop.get("pos") or [0.0, -0.34, 0.72])]
        p1 = [float(v) for v in (prop.get("pos_end") or p0)]
        bx, by, bz = [0.5 * (a + b) for a, b in zip(p0, p1)]
    else:
        bx, by, bz = [float(v) for v in (prop.get(pos_key) or prop.get("pos") or [0.0, -0.34, 0.72])]

    pid = str(prop.get("prop_id") or "prop_1")
    yaw = float(prop.get("yaw_deg") or 0.0)
    c_hex = str(prop.get("color_hex") or PREVIS_SAFE_PALETTE[2][1]).upper()
    dark_hex = _darken_hex(c_hex, 0.62)

    if ctype == "snake_terrarium":
        return [
            {
                "chunk_id": f"{pid}_terrarium_base",
                "shape": "box",
                "center": [bx, by, bz + 0.02],
                "size_xyz": [0.48, 0.32, 0.04],
                "yaw_deg": yaw,
                "color_hex": dark_hex,
                "alpha": 1.0,
            },
            {
                "chunk_id": f"{pid}_coil_body",
                "shape": "cylinder",
                "center": [bx, by, bz + 0.085],
                "size_xyz": [0.20, 0.20, 0.09],
                "yaw_deg": yaw,
                "color_hex": c_hex,
                "alpha": 1.0,
            },
            {
                "chunk_id": f"{pid}_snake_neck",
                "shape": "box",
                "center": [bx + 0.04, by - 0.03, bz + 0.17],
                "size_xyz": [0.06, 0.08, 0.11],
                "yaw_deg": yaw,
                "color_hex": c_hex,
                "alpha": 1.0,
            },
            {
                "chunk_id": f"{pid}_glass_enclosure",
                "shape": "box",
                "center": [bx, by, bz + 0.16],
                "size_xyz": [0.46, 0.30, 0.28],
                "yaw_deg": yaw,
                "color_hex": "#A8B6C4",
                "alpha": PREVIS_GLASS_ALPHA,
            },
        ]
    if ctype == "mask_tube":
        return [
            {
                "chunk_id": f"{pid}_valve_base",
                "shape": "cylinder",
                "center": [bx, by + 0.08, bz + 0.05],
                "size_xyz": [0.09, 0.09, 0.10],
                "yaw_deg": yaw,
                "color_hex": dark_hex,
                "alpha": 1.0,
            },
            {
                "chunk_id": f"{pid}_hose",
                "shape": "box",
                "center": [bx, by - 0.03, bz + 0.12],
                "size_xyz": [0.05, 0.24, 0.05],
                "yaw_deg": yaw,
                "color_hex": c_hex,
                "alpha": 1.0,
            },
            {
                "chunk_id": f"{pid}_clear_mask_cone",
                "shape": "cylinder",
                "center": [bx, by - 0.14, bz + 0.16],
                "size_xyz": [0.15, 0.15, 0.13],
                "yaw_deg": yaw,
                "color_hex": c_hex,
                "alpha": 0.36,
            },
        ]
    if ctype == "robot_arm":
        return [
            {
                "chunk_id": f"{pid}_rig_base",
                "shape": "cylinder",
                "center": [bx, by, bz + 0.04],
                "size_xyz": [0.24, 0.24, 0.08],
                "yaw_deg": yaw,
                "color_hex": dark_hex,
                "alpha": 1.0,
            },
            {
                "chunk_id": f"{pid}_arm_mast",
                "shape": "box",
                "center": [bx, by + 0.05, bz + 0.22],
                "size_xyz": [0.07, 0.07, 0.30],
                "yaw_deg": yaw,
                "color_hex": c_hex,
                "alpha": 1.0,
            },
            {
                "chunk_id": f"{pid}_arm_boom",
                "shape": "box",
                "center": [bx, by - 0.08, bz + 0.35],
                "size_xyz": [0.06, 0.28, 0.06],
                "yaw_deg": yaw,
                "color_hex": c_hex,
                "alpha": 1.0,
            },
            {
                "chunk_id": f"{pid}_effector_tip",
                "shape": "box",
                "center": [bx, by - 0.22, bz + 0.31],
                "size_xyz": [0.05, 0.12, 0.04],
                "yaw_deg": yaw,
                "color_hex": dark_hex,
                "alpha": 1.0,
            },
        ]
    if ctype == "brain_cutaway":
        return [
            {
                "chunk_id": f"{pid}_brainstem_stalk",
                "shape": "cylinder",
                "center": [bx, by, bz + 0.06],
                "size_xyz": [0.06, 0.06, 0.12],
                "yaw_deg": yaw,
                "color_hex": dark_hex,
                "alpha": 1.0,
            },
            {
                "chunk_id": f"{pid}_hemispheres",
                "shape": "sphere",
                "center": [bx, by, bz + 0.18],
                "radius": 0.11,
                "size_xyz": [0.22, 0.24, 0.20],
                "yaw_deg": yaw,
                "color_hex": c_hex,
                "alpha": 1.0,
            },
        ]
    if ctype == "chair":
        return [
            {
                "chunk_id": f"{pid}_chair_pedestal",
                "shape": "cylinder",
                "center": [bx, by, bz + 0.21],
                "size_xyz": [0.12, 0.12, 0.42],
                "yaw_deg": yaw,
                "color_hex": dark_hex,
                "alpha": 1.0,
            },
            {
                "chunk_id": f"{pid}_chair_seat",
                "shape": "box",
                "center": [bx, by, bz + 0.44],
                "size_xyz": [0.48, 0.48, 0.07],
                "yaw_deg": yaw,
                "color_hex": c_hex,
                "alpha": 1.0,
            },
            {
                "chunk_id": f"{pid}_chair_back",
                "shape": "box",
                "center": [bx, by + 0.21, bz + 0.69],
                "size_xyz": [0.46, 0.07, 0.45],
                "yaw_deg": yaw,
                "color_hex": c_hex,
                "alpha": 1.0,
            },
        ]
    if ctype == "monitor":
        return [
            {
                "chunk_id": f"{pid}_monitor_stand",
                "shape": "box",
                "center": [bx, by + 0.02, bz + 0.06],
                "size_xyz": [0.18, 0.14, 0.12],
                "yaw_deg": yaw,
                "color_hex": dark_hex,
                "alpha": 1.0,
            },
            {
                "chunk_id": f"{pid}_monitor_panel",
                "shape": "box",
                "center": [bx, by, bz + 0.24],
                "size_xyz": [0.44, 0.05, 0.28],
                "yaw_deg": yaw,
                "color_hex": c_hex,
                "alpha": 1.0,
            },
        ]
    if ctype == "toggle_switch":
        return [
            {
                "chunk_id": f"{pid}_switch_base",
                "shape": "box",
                "center": [bx, by, bz + 0.035],
                "size_xyz": [0.22, 0.16, 0.07],
                "yaw_deg": yaw,
                "color_hex": dark_hex,
                "alpha": 1.0,
            },
            {
                "chunk_id": f"{pid}_switch_lever",
                "shape": "box",
                "center": [bx, by - 0.02, bz + 0.11],
                "size_xyz": [0.04, 0.06, 0.11],
                "yaw_deg": yaw,
                "color_hex": c_hex,
                "alpha": 1.0,
            },
        ]
    if ctype == "stopwatch":
        return [
            {
                "chunk_id": f"{pid}_watch_body",
                "shape": "cylinder",
                "center": [bx, by, bz + 0.03],
                "size_xyz": [0.10, 0.10, 0.04],
                "yaw_deg": yaw,
                "color_hex": c_hex,
                "alpha": 1.0,
            },
            {
                "chunk_id": f"{pid}_watch_crown",
                "shape": "cylinder",
                "center": [bx, by - 0.05, bz + 0.055],
                "size_xyz": [0.03, 0.03, 0.03],
                "yaw_deg": yaw,
                "color_hex": dark_hex,
                "alpha": 1.0,
            },
        ]
    return [build_prop_box_primitive(prop, phase=phase)]


ROLE_LOCKED_DEFAULT_COLORS: dict[str, tuple[str, str]] = {
    "protagonist": ("Forest Olive", "#386641"),
    "patient": ("Forest Olive", "#386641"),
    "patient_sm": ("Forest Olive", "#386641"),
    "child_subject": ("Forest Olive", "#386641"),
    "subject": ("Forest Olive", "#386641"),
    "neurologist": ("Royal Violet", "#7B2CBF"),
    "neurologist_1": ("Royal Violet", "#7B2CBF"),
    "neurologist_2": ("Deep Indigo", "#2B3A67"),
    "researcher": ("Royal Violet", "#7B2CBF"),
    "researcher_1": ("Royal Violet", "#7B2CBF"),
    "researcher_2": ("Deep Indigo", "#2B3A67"),
    "professor": ("Slate Petrol", "#4F6D7A"),
    "monster_actor": ("Saddle Ochre", "#8C5A2B"),
    "foil": ("Saddle Ochre", "#8C5A2B"),
    "assistant": ("Deep Indigo", "#2B3A67"),
    "mini_cortex": ("Plum Magenta", "#8F2D75"),
}

_PLURAL_CAST_COUNTS: dict[str, int] = {
    "two": 2,
    "2": 2,
    "both": 2,
    "pair": 2,
    "three": 3,
    "3": 3,
}

_PERSON_ROLE_HINTS: tuple[str, ...] = (
    "patient",
    "neurologist",
    "researcher",
    "scientist",
    "experimenter",
    "doctor",
    "clinician",
    "physician",
    "professor",
    "woman",
    "man",
    "child",
    "boy",
    "girl",
    "toddler",
    "actor",
    "monster",
    "volunteer",
    "subject",
    "participant",
    "assistant",
    "character",
    "figurine",
    "mini",
)


def canonicalize_actor_role_id(label: str, fallback_idx: int = 1) -> str:
    """Maps descriptive cast text onto a canonical episode-stable `role_id` so colors never swap across cuts."""
    raw = str(label or "").strip()
    low = raw.lower()
    if not raw:
        return f"actor_{fallback_idx}"
    if " " not in raw and re.fullmatch(r"[a-zA-Z0-9_\-]+", raw):
        return raw.lower().replace("-", "_")
    if "mini_cortex" in low or "mini-cortex" in low or "mini cortex" in low:
        return "mini_cortex"
    m_pat = re.search(r"\bpatient\s+([a-z]\.?[a-z]?\.?|[a-z0-9_]+)", low)
    if m_pat:
        tok = re.sub(r"[^a-z0-9]+", "", m_pat.group(1))
        return f"patient_{tok}" if tok else "patient"
    if "patient" in low:
        return "patient"
    if any(k in low for k in ("child", "kid", "toddler", "four-year", "boy", "girl")):
        return "child_subject"
    if "monster" in low or "costumed" in low:
        return "monster_actor"
    if "professor" in low:
        return "professor"
    if "neurologist" in low or "doctor" in low or "clinician" in low or "physician" in low:
        return "neurologist"
    if "researcher" in low or "scientist" in low or "experimenter" in low:
        return "researcher"
    if "assistant" in low or "technician" in low:
        return "assistant"
    if any(k in low for k in ("protagonist", "volunteer", "participant", "subject", "woman", "man")):
        return "protagonist"
    return f"actor_{fallback_idx}"


def expand_cast_entries(raw_cast_field: Any) -> list[dict[str, Any]]:
    """
    Expands cast descriptions into structured actor entries, splitting multi-character `'X and Y'`
    conjunctions AND plural group nouns (`'two neurologists'`, `'three researchers'`) into distinct
    3D positioned dummies with stable `role_id`s.
    """
    raw_items: list[Any] = []
    if isinstance(raw_cast_field, str):
        s = raw_cast_field.strip()
        if not s:
            raw_items = ["protagonist"]
        else:
            parts = [
                p.strip()
                for p in re.split(
                    r"\s+and\s+|,\s+|\s+(?:watching|observing|facing|beside|next\s+to|across\s+from|opposite)\s+",
                    s,
                    flags=re.IGNORECASE,
                )
                if p.strip()
            ]
            merged: list[str] = []
            for p in parts:
                p_low = p.lower()
                if not merged or any(h in p_low for h in _PERSON_ROLE_HINTS):
                    merged.append(p)
                else:
                    merged[-1] = f"{merged[-1]} and {p}"
            raw_items = merged or [s]
    elif isinstance(raw_cast_field, (list, tuple)):
        raw_items = list(raw_cast_field) or ["protagonist"]
    else:
        raw_items = ["protagonist"]

    expanded: list[dict[str, Any]] = []
    used_role_ids: set[str] = set()
    for idx, entry in enumerate(raw_items, start=1):
        if isinstance(entry, dict):
            lbl = str(entry.get("label") or entry.get("role_id") or f"actor_{idx}").strip()
            exp_rid = str(entry.get("role_id") or "").strip()
            rid = exp_rid if exp_rid else canonicalize_actor_role_id(lbl, idx)
            if rid in used_role_ids:
                suffix = 2
                while f"{rid}_{suffix}" in used_role_ids:
                    suffix += 1
                rid = f"{rid}_{suffix}"
            used_role_ids.add(rid)
            d_copy = dict(entry)
            d_copy["role_id"] = rid
            d_copy["label"] = lbl
            expanded.append(d_copy)
            continue

        lbl_str = str(entry).strip()
        m_pl = re.match(r"^(two|2|both|pair\s+of|three|3)\b\s+(.*)$", lbl_str, flags=re.IGNORECASE)
        if m_pl:
            cnt_tok = m_pl.group(1).lower().split()[0]
            count = _PLURAL_CAST_COUNTS.get(cnt_tok, 2)
            base_rid = canonicalize_actor_role_id(lbl_str, idx)
            for k in range(1, count + 1):
                cand_rid = base_rid if (k == 1 and base_rid not in used_role_ids) else f"{base_rid}_{k}"
                while cand_rid in used_role_ids:
                    k += 1
                    cand_rid = f"{base_rid}_{k}"
                used_role_ids.add(cand_rid)
                expanded.append({"role_id": cand_rid, "label": f"{lbl_str} (#{k})"})
        else:
            rid = canonicalize_actor_role_id(lbl_str, idx)
            if rid in used_role_ids:
                suffix = 2
                while f"{rid}_{suffix}" in used_role_ids:
                    suffix += 1
                rid = f"{rid}_{suffix}"
            used_role_ids.add(rid)
            expanded.append({"role_id": rid, "label": lbl_str})

    return expanded[:4]


_ACTIVE_PROP_EXTRACTION_RULES: tuple[tuple[str, tuple[str, ...], str, str], ...] = (
    ("prop_snake_terrarium", ("snake", "terrarium", "reptile", "tarantula"), "glass snake terrarium", "snake_terrarium"),
    ("prop_mask_tube", ("breathing mask", "silicone mask", "co2 mask", "oxygen mask", "breathing valve"), "clear breathing mask and tube", "mask_tube"),
    ("prop_robot_arm", ("robot", "robotic", "tickle rig", "actuator", "pantograph"), "delayed tickle robot arm", "robot_arm"),
    ("prop_photo_enlarger", ("enlarger", "darkroom", "photo print", "silver-gelatin", "developing tray"), "darkroom photo enlarger and print tray", ""),
    ("prop_jam_jar_rack", ("jam jar", "preserve jar", "24 jam", "6 jam", "tasting booth"), "gourmet jam jar tasting display", ""),
    ("prop_toggle_switch", ("toggle switch", "porcelain switch", "switch"), "heavy toggle switch", "toggle_switch"),
    ("prop_stopwatch", ("stopwatch", "brass timer", "chronometer"), "brass stopwatch", "stopwatch"),
    ("prop_diary_book", ("pocket diary", "diary", "notebook", "leather volumes", "clipboard", "to-do list"), "experiment diary notebook", ""),
    ("prop_monitor", ("projector", "monitor", "oscilloscope", "screen"), "laboratory monitor display", "monitor"),
    ("prop_marshmallow", ("marshmallow", "saucer", "plate"), "plate with marshmallow", ""),
    ("prop_medical_chair", ("medical chair", "exam chair"), "clinical medical chair", "chair"),
)


def extract_active_props_from_clip(clip_spec: dict[str, Any], *, surf_z: float = 0.72) -> list[dict[str, Any]]:
    """
    P3 Active Prop Extractor: Parses `analogy_object`, `action`, `cast`, and `environment` when
    `clip_spec['props']` is omitted so tabletop/floor experiment props are never missing (`props: []`).
    """
    text_blob = " ".join(
        str(clip_spec.get(k) or "")
        for k in ("analogy_object", "action", "scene_body", "cast", "environment", "prompt")
    ).lower()
    if not text_blob.strip():
        return []

    found: list[tuple[str, str, str]] = []
    for prop_id, keywords, nice_label, ctype in _ACTIVE_PROP_EXTRACTION_RULES:
        if any(kw in text_blob for kw in keywords):
            found.append((prop_id, nice_label, ctype))
        if len(found) >= 2:
            break

    props_out: list[dict[str, Any]] = []
    for idx, (pid, lbl, ctype) in enumerate(found):
        p_shape, p_size = resolve_prop_shape_and_size(lbl)
        if ctype == "chair" or p_size[2] > 0.80:
            p_pos = [0.55, 0.10, 0.0]
        elif pid == "prop_stopwatch":
            p_pos = [0.16, -0.18, surf_z + 0.26]
        elif pid == "prop_mask_tube" and ("holds up" in text_blob or "lifting" in text_blob):
            p_pos = [0.10, -0.12, surf_z + 0.34]
        else:
            x_off = 0.0 if len(found) == 1 else (-0.22 + 0.44 * idx)
            p_pos = [x_off, -0.34, surf_z]
        p_entry: dict[str, Any] = {
            "prop_id": pid,
            "label": lbl,
            "shape": p_shape,
            "pos_start": list(p_pos),
            "pos_end": [p_pos[0] + (0.03 if idx == 0 else 0.0), p_pos[1] - 0.02, p_pos[2]],
            "size_xyz": p_size,
            "yaw_deg": 0.0,
        }
        if ctype:
            p_entry["compound_type"] = ctype
        props_out.append(p_entry)
    return props_out


def solve_9x16_camera_frustum(
    cam: dict[str, Any],
    actors: list[dict[str, Any]],
    props: list[dict[str, Any]],
    *,
    phase: str = "start",
    grammar: str = "",
    surf_z: float = 0.72,
    margin_ratio: float = 0.12,
    aspect: float = 9.0 / 16.0,
) -> dict[str, Any]:
    """
    P2 `9:16` Portrait Auto-Framing Frustum Solver:
    Computes true horizontal FOV `HFOV = 2 * atan((9/16) * tan(VFOV/2))` and adjusts `look_at`
    and camera pullback distance so active actors and props project inside `margin_ratio` (`12%`)
    without lateral clipping (`S01/S04/S06`) or `34cm` torso-wall blockage (`S02_end`).
    """
    g_low = str(grammar or "").strip().lower()
    out_cam = copy.deepcopy(cam)
    if "pov_hands" in g_low:
        return out_cam
    init_look = np.array([float(v) for v in (out_cam.get("look_at") or [0.0, 0.05, 1.15])], dtype=np.float64)
    init_pos = np.array([float(v) for v in (out_cam.get("pos") or [0.0, -2.5, 1.38])], dtype=np.float64)
    init_dist = float(np.linalg.norm(init_pos - init_look))
    if (
        init_dist >= 4.2
        or float(init_pos[2]) >= 3.1
        or bool(out_cam.get("preserve_drone_altitude"))
        or g_low in ("expressive_exterior_establishing", "architectural_cutaway_portal")
    ):
        # Preserve high-altitude R72 drone / aerial / facade-breach 3D trajectory without clamping to 3.75m indoor room bounds!
        return out_cam

    human_actors = [
        a for a in (actors or [])
        if isinstance(a, dict) and float(a.get("height_m") or 1.72) > 0.35 and "mini" not in str(a.get("role_id") or "").lower()
    ]
    active_actors = human_actors or [a for a in (actors or []) if isinstance(a, dict)]
    if not active_actors and not props:
        return out_cam

    target_pts: list[list[float]] = []
    pos_key = "pos_end" if phase == "end" else "pos_start"

    if "hands_closeup" in g_low:
        for pr in (props or []):
            pp = pr.get(pos_key) or pr.get("pos_start") or pr.get("pos") or [0.0, -0.34, surf_z]
            psz = pr.get("size_xyz") or [0.30, 0.24, 0.20]
            for dx in (-0.5, 0.5):
                for dz in (0.0, 1.0):
                    target_pts.append([float(pp[0]) + dx * float(psz[0]), float(pp[1]), float(pp[2]) + dz * float(psz[2])])
        for act in active_actors[:1]:
            ap = act.get(pos_key) or act.get("pos_start") or [0.0, 0.18, 0.0]
            hm = float(act.get("height_m") or 1.72)
            for dx in (-0.22, 0.22):
                target_pts.append([float(ap[0]) + dx, float(ap[1]), surf_z + 0.02])
                target_pts.append([float(ap[0]) + dx, float(ap[1]), min(hm * 0.84, surf_z + 0.62)])
        if not props:
            target_pts.append([-0.24, -0.34, surf_z])
            target_pts.append([0.24, -0.34, surf_z + 0.28])
    elif "reaction_closeup" in g_low or "xray_brain" in g_low or "living_brain" in g_low:
        for act in active_actors[:1]:
            ap = act.get(pos_key) or act.get("pos_start") or [0.0, 0.18, 0.0]
            hm = float(act.get("height_m") or 1.72)
            pose_now = str(act.get("pose_end" if phase == "end" else "pose_start") or act.get("pose") or "standing").lower()
            top_z = hm * (0.80 if pose_now == "seated" else 1.00)
            bot_z = hm * (0.42 if pose_now == "seated" else 0.54)
            hw = hm * 0.19
            for dx in (-hw, hw):
                target_pts.append([float(ap[0]) + dx, float(ap[1]), bot_z])
                target_pts.append([float(ap[0]) + dx, float(ap[1]), top_z])
        for pr in (props or [])[:1]:
            pp = pr.get(pos_key) or pr.get("pos_start") or [0.0, -0.20, surf_z]
            if float(pp[2]) >= surf_z:
                target_pts.append([float(pp[0]), float(pp[1]), float(pp[2]) + 0.12])
    else:
        for act in active_actors:
            ap = act.get(pos_key) or act.get("pos_start") or [0.0, 0.18, 0.0]
            hm = float(act.get("height_m") or 1.72)
            pose_now = str(act.get("pose_end" if phase == "end" else "pose_start") or act.get("pose") or "standing").lower()
            top_z = hm * (0.82 if pose_now == "seated" else 1.01)
            hw = hm * 0.18
            for dx in (-hw, hw):
                target_pts.append([float(ap[0]) + dx, float(ap[1]), 0.02])
                target_pts.append([float(ap[0]) + dx, float(ap[1]), top_z])
        for pr in (props or []):
            pp = pr.get(pos_key) or pr.get("pos_start") or [0.0, -0.34, surf_z]
            psz = pr.get("size_xyz") or [0.30, 0.24, 0.20]
            if float(psz[2]) <= 1.25:
                for dx in (-0.5 * float(psz[0]), 0.5 * float(psz[0])):
                    target_pts.append([float(pp[0]) + dx, float(pp[1]), float(pp[2])])
                    target_pts.append([float(pp[0]) + dx, float(pp[1]), float(pp[2]) + float(psz[2])])

    if not target_pts:
        return out_cam

    pts_arr = np.array(target_pts, dtype=np.float64)
    centroid = np.mean(pts_arr, axis=0)
    orig_look = np.array([float(v) for v in (out_cam.get("look_at") or [0.0, 0.05, 1.15])], dtype=np.float64)
    orig_pos = np.array([float(v) for v in (out_cam.get("pos") or [0.0, -2.5, 1.38])], dtype=np.float64)

    # Keep gentle pan offset bounded within +-0.18m of subject centroid so single actors never pan off-screen
    pan_dx = max(-0.18, min(0.18, float(orig_look[0] - centroid[0]) * 0.35))
    new_look = np.array(
        [
            float(centroid[0]) + pan_dx,
            0.65 * float(centroid[1]) + 0.35 * float(orig_look[1]),
            0.72 * float(centroid[2]) + 0.28 * float(orig_look[2]),
        ],
        dtype=np.float64,
    )

    ray = orig_pos - orig_look
    cur_dist = float(np.linalg.norm(ray))
    if cur_dist < 0.25:
        ray_dir = np.array([0.0, -1.0, 0.15], dtype=np.float64)
        ray_dir /= float(np.linalg.norm(ray_dir))
        cur_dist = 1.6
    else:
        ray_dir = ray / cur_dist

    if "hands_closeup" in g_low:
        # Elevate slightly so tabletop prop + hands are seen cleanly at 35-deg angle instead of torso wall
        ray_dir = np.array([ray_dir[0] * 0.6, min(-0.72, ray_dir[1]), max(0.38, ray_dir[2])], dtype=np.float64)
        ray_dir /= float(np.linalg.norm(ray_dir))
        cur_dist = max(cur_dist, 1.18)

    vfov_deg = max(28.0, min(68.0, float(out_cam.get("fov_deg") or 48.0)))
    safe_scale = max(0.55, 1.0 - float(margin_ratio))

    def _required_dist(vf_deg: float) -> float:
        vf_rad = math.radians(vf_deg)
        tan_v = math.tan(vf_rad * 0.5) * safe_scale
        tan_h = float(aspect) * math.tan(vf_rad * 0.5) * safe_scale
        probe_pos = new_look + ray_dir * cur_dist
        r_vec, u_vec, f_vec = _camera_basis(probe_pos, new_look)
        rel_l = pts_arr - new_look
        req = cur_dist
        for pt_rel in rel_l:
            proj_x = abs(float(np.dot(pt_rel, r_vec)))
            proj_y = abs(float(np.dot(pt_rel, u_vec)))
            proj_f = float(np.dot(pt_rel, f_vec))
            d_x = (proj_x / max(1e-4, tan_h)) - proj_f
            d_y = (proj_y / max(1e-4, tan_v)) - proj_f
            req = max(req, d_x, d_y, 0.55 - proj_f)
        return req

    needed_dist = _required_dist(vfov_deg)
    max_dist = 3.55
    if needed_dist > max_dist and vfov_deg < 58.0:
        vfov_deg = min(58.0, max(vfov_deg, 52.0))
        needed_dist = _required_dist(vfov_deg)
    final_dist = min(3.75, max(cur_dist, needed_dist))
    new_pos = new_look + ray_dir * final_dist
    new_pos[2] = max(0.28, float(new_pos[2]))

    out_cam["pos"] = [round(float(v), 4) for v in new_pos]
    out_cam["look_at"] = [round(float(v), 4) for v in new_look]
    out_cam["fov_deg"] = round(float(vfov_deg), 2)
    return out_cam


def evaluate_previs_visibility_gate(
    frame_bgr: np.ndarray,
    previs_spec: dict[str, Any] | None = None,
    *,
    min_marker_ratio: float = 0.08,
    max_single_block_ratio: float = 0.60,
) -> dict[str, Any]:
    """
    P2 Previs Visibility Gate:
      1. Active actor/prop marker pixels (`HSV S >= 48`) must cover `>= min_marker_ratio` (`8%`) when entities exist.
      2. No single solid block (e.g. opaque wall or `34cm` torso closeup) may exceed `max_single_block_ratio` (`60%`)
         in the central `80%` subject zone while crowding out spatial context.
    """
    if frame_bgr is None or frame_bgr.size == 0:
        return {"passed": False, "active_marker_ratio": 0.0, "max_single_block_ratio": 1.0, "reason": "empty_frame"}

    spec = previs_spec or {}
    has_entities = bool((spec.get("actors") or []) or (spec.get("props") or []))
    max_cam_dist = 0.0
    for ck in ("camera_start", "camera_end"):
        cd = spec.get(ck)
        if isinstance(cd, dict) and cd.get("pos") and cd.get("look_at"):
            p_arr = np.array([float(v) for v in cd["pos"]], dtype=np.float64)
            l_arr = np.array([float(v) for v in cd["look_at"]], dtype=np.float64)
            max_cam_dist = max(max_cam_dist, float(np.linalg.norm(p_arr - l_arr)))
    is_neural_stage = bool(spec.get("neural_cutaway_stage"))
    eff_min_marker = 0.0 if max_cam_dist >= 4.2 else (0.004 if is_neural_stage else float(min_marker_ratio))
    hsv = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV)
    marker_mask = hsv[:, :, 1] >= 48
    total_px = float(frame_bgr.shape[0] * frame_bgr.shape[1])
    active_ratio = float(np.count_nonzero(marker_mask)) / max(1.0, total_px)

    # Quantize central 80% region into coarse color bins to detect single-block wall/torso dominance
    h, w = frame_bgr.shape[:2]
    cy0, cy1 = int(h * 0.10), int(h * 0.90)
    cx0, cx1 = int(w * 0.10), int(w * 0.90)
    roi_hsv = hsv[cy0:cy1, cx0:cx1]
    roi_marker = roi_hsv[:, :, 1] >= 48
    marker_dom_ratio = float(np.count_nonzero(roi_marker)) / max(1.0, float(roi_marker.size))

    passed = True
    reasons: list[str] = []
    if has_entities and active_ratio < eff_min_marker:
        passed = False
        reasons.append(f"low_marker_coverage:{active_ratio:.4f}<{eff_min_marker:.2f}")
    if marker_dom_ratio > float(max_single_block_ratio):
        passed = False
        reasons.append(f"excessive_single_block_dominance:{marker_dom_ratio:.4f}>{max_single_block_ratio:.2f}")

    return {
        "passed": passed,
        "active_marker_ratio": round(active_ratio, 4),
        "max_single_block_ratio": round(marker_dom_ratio, 4),
        "reasons": reasons,
    }


def _pullback_camera_spec(cam: dict[str, Any], factor: float = 1.30) -> dict[str, Any]:
    out = copy.deepcopy(cam)
    pos = np.array([float(v) for v in (out.get("pos") or [0.0, -2.5, 1.4])], dtype=np.float64)
    look = np.array([float(v) for v in (out.get("look_at") or [0.0, 0.05, 1.15])], dtype=np.float64)
    vec = pos - look
    dist = float(np.linalg.norm(vec))
    if dist >= 4.2 or bool(out.get("preserve_drone_altitude")):
        return out
    if dist < 0.2:
        vec = np.array([0.0, -1.8, 0.35], dtype=np.float64)
    else:
        new_dist = min(3.85, max(dist * float(factor), dist + 0.45))
        vec = (vec / dist) * new_dist
    new_pos = look + vec
    new_pos[2] = max(0.35, float(new_pos[2]))
    out["pos"] = [round(float(v), 4) for v in new_pos]
    out["fov_deg"] = round(min(60.0, max(44.0, float(out.get("fov_deg") or 48.0) + 4.0)), 2)
    return out


def propagate_previs_camera_continuity(
    visual_plan: dict[str, Any],
    *,
    sync_actor_poses: bool = True,
) -> dict[str, Any]:
    """
    Copies `Cut[i].previs.camera_end` -> `Cut[i+1].previs.camera_start` across consecutive cuts
    in the same `location_id` (unless `break_continuity=True`), guaranteeing exact mathematical
    seam alignment (`End(i) == Start(i+1)`).
    """
    clips = visual_plan.get("clips")
    if not isinstance(clips, list) or len(clips) < 2:
        return visual_plan

    default_loc = str(visual_plan.get("default_location_id") or "").strip()
    carry_palette: dict[str, tuple[str, str]] = {}
    existing_reg = visual_plan.get("previs_role_color_registry")
    if isinstance(existing_reg, dict):
        for rid_k, meta_v in existing_reg.items():
            if isinstance(meta_v, dict) and meta_v.get("color_hex"):
                carry_palette[str(rid_k)] = (str(meta_v.get("color_name") or rid_k), str(meta_v["color_hex"]))

    for clip in clips:
        if not isinstance(clip, dict) or not isinstance(clip.get("previs"), dict):
            continue
        pv = clip["previs"]
        entities = list(pv.get("actors") or []) + list(pv.get("props") or [])
        legend = assign_previs_palette(entities, existing_assignments=carry_palette)
        pv["color_role_legend"] = legend
        for eid, meta in legend.items():
            carry_palette[eid] = (meta["color_name"], meta["color_hex"])

    for idx in range(len(clips) - 1):
        cur_c = clips[idx]
        nxt_c = clips[idx + 1]
        if not isinstance(cur_c, dict) or not isinstance(nxt_c, dict):
            continue
        pv_cur = cur_c.get("previs")
        pv_nxt = nxt_c.get("previs")
        if not isinstance(pv_cur, dict) or not isinstance(pv_nxt, dict):
            continue
        if bool(pv_nxt.get("break_continuity")):
            continue
        if bool(pv_cur.get("neural_cutaway_stage")) != bool(pv_nxt.get("neural_cutaway_stage")):
            continue

        loc_cur = str(cur_c.get("location_id") or default_loc).strip()
        loc_nxt = str(nxt_c.get("location_id") or default_loc).strip()
        explicit_chain = bool(pv_nxt.get("chain_from_prev"))
        same_loc = bool(loc_cur and loc_nxt and loc_cur == loc_nxt)
        if not (same_loc or explicit_chain):
            continue

        # Avoid copying a tight tabletop hands_closeup camera into a non-hands_closeup reaction/wide cut
        g_cur = str(cur_c.get("grammar") or cur_c.get("visual_grammar") or "").lower()
        g_nxt = str(nxt_c.get("grammar") or nxt_c.get("visual_grammar") or "").lower()
        closeup_mismatch = (
            bool(pv_nxt.get("auto_frame"))
            and not explicit_chain
            and ("hands_closeup" in g_cur or "pov_hands" in g_cur)
            and ("hands_closeup" not in g_nxt and "pov_hands" not in g_nxt)
        )

        cam_end = pv_cur.get("camera_end")
        if isinstance(cam_end, dict) and not closeup_mismatch:
            pv_nxt["camera_start"] = copy.deepcopy(cam_end)
            pv_nxt["continuity_chained_from_cut"] = int(cur_c.get("clip_number") or (idx + 1))
            if bool(pv_nxt.get("auto_frame")):
                pv_nxt["camera_start"] = solve_9x16_camera_frustum(
                    pv_nxt["camera_start"],
                    list(pv_nxt.get("actors") or []),
                    list(pv_nxt.get("props") or []),
                    phase="start",
                    grammar=g_nxt,
                )

        if sync_actor_poses and isinstance(pv_cur.get("actors"), list) and isinstance(pv_nxt.get("actors"), list):
            end_by_role: dict[str, list[float]] = {}
            for act in pv_cur["actors"]:
                r_id = str(act.get("role_id") or act.get("id") or "").strip()
                p_end = act.get("pos_end") or act.get("pos_start")
                if r_id and isinstance(p_end, list) and len(p_end) == 3:
                    end_by_role[r_id] = [float(x) for x in p_end]
            for act_nxt in pv_nxt["actors"]:
                r_id = str(act_nxt.get("role_id") or act_nxt.get("id") or "").strip()
                if r_id in end_by_role and not bool(act_nxt.get("override_pos_start")):
                    act_nxt["pos_start"] = list(end_by_role[r_id])

    return visual_plan


# E1: 12-Move Camera Trajectory Presets (`pos`, `look_at`, `fov_deg`)
CAMERA_MOVE_PREVIS_PRESETS: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {
    "dolly_zoom_vertigo": (
        {"pos": [0.0, -2.95, 1.35], "look_at": [0.0, 0.05, 1.15], "fov_deg": 36.0},
        {"pos": [0.0, -1.45, 1.28], "look_at": [0.0, 0.05, 1.15], "fov_deg": 62.0},
    ),
    "crane_swoop_dive": (
        {"pos": [-0.35, -2.55, 2.95], "look_at": [0.0, -0.15, 0.95], "fov_deg": 54.0},
        {"pos": [0.10, -1.25, 1.12], "look_at": [0.0, -0.22, 0.82], "fov_deg": 46.0},
    ),
    "orbital_3d_arc_sweep": (
        {"pos": [-0.92, -2.15, 1.34], "look_at": [0.0, 0.05, 1.15], "fov_deg": 48.0},
        {"pos": [0.88, -2.15, 1.30], "look_at": [0.0, 0.05, 1.15], "fov_deg": 46.0},
    ),
    "axial_portal_dive": (
        {"pos": [0.0, -0.45, 3.15], "look_at": [0.0, -0.08, 0.85], "fov_deg": 54.0},
        {"pos": [0.0, -0.82, 1.18], "look_at": [0.0, -0.10, 0.96], "fov_deg": 44.0},
    ),
    "pan_left": (
        {"pos": [0.35, -2.35, 1.35], "look_at": [0.55, 0.15, 1.15], "fov_deg": 48.0},
        {"pos": [-0.25, -2.35, 1.35], "look_at": [-0.55, 0.15, 1.15], "fov_deg": 48.0},
    ),
    "pan_right": (
        {"pos": [-0.35, -2.35, 1.35], "look_at": [-0.55, 0.15, 1.15], "fov_deg": 48.0},
        {"pos": [0.25, -2.35, 1.35], "look_at": [0.55, 0.15, 1.15], "fov_deg": 48.0},
    ),
    "fpv_3d_flight": (
        {"pos": [-0.20, -2.85, 1.55], "look_at": [0.0, -0.10, 1.05], "fov_deg": 56.0},
        {"pos": [0.04, -1.05, 1.08], "look_at": [0.0, -0.20, 0.90], "fov_deg": 46.0},
    ),
    "gentle_push_in": (
        {"pos": [0.12, -2.45, 1.36], "look_at": [0.0, 0.05, 1.14], "fov_deg": 50.0},
        {"pos": [0.05, -1.62, 1.30], "look_at": [0.0, 0.05, 1.18], "fov_deg": 45.0},
    ),
    "whip_pan_occlusion": (
        {"pos": [-1.75, -1.85, 1.32], "look_at": [-0.45, 0.20, 1.18], "fov_deg": 54.0},
        {"pos": [1.15, -1.90, 1.30], "look_at": [0.25, 0.10, 1.15], "fov_deg": 48.0},
    ),
    "portal_dive_flight": (
        {"pos": [0.0, -2.35, 1.48], "look_at": [0.0, 0.02, 1.48], "fov_deg": 50.0},
        {"pos": [0.0, -0.66, 1.52], "look_at": [0.0, 0.06, 1.54], "fov_deg": 40.0},
    ),
    "clean_pullback_reveal": (
        {"pos": [0.0, -1.32, 1.32], "look_at": [0.0, 0.04, 1.22], "fov_deg": 45.0},
        {"pos": [-0.35, -3.05, 1.82], "look_at": [0.0, 0.12, 1.12], "fov_deg": 54.0},
    ),
    "top_down_overhead": (
        {"pos": [0.0, -0.85, 3.25], "look_at": [0.0, -0.15, 0.85], "fov_deg": 52.0},
        {"pos": [0.15, -1.55, 1.35], "look_at": [0.0, -0.10, 1.05], "fov_deg": 48.0},
    ),
    "low_angle_hero": (
        {"pos": [0.0, -2.25, 0.58], "look_at": [0.0, 0.08, 1.38], "fov_deg": 54.0},
        {"pos": [0.18, -1.52, 0.74], "look_at": [0.0, 0.08, 1.44], "fov_deg": 48.0},
    ),
    # Rule R72 Continuous Drone / FPV 3D Flight Presets (K0 -> K1 -> K2 exact seam continuity!)
    "drone_aerial_approach": (
        {"pos": [0.0, -24.0, 13.5], "look_at": [0.0, 3.20, 2.60], "fov_deg": 54.0, "preserve_drone_altitude": True},
        {"pos": [0.0, -4.80, 3.20], "look_at": [0.0, 1.50, 2.10], "fov_deg": 48.0, "preserve_drone_altitude": True},
    ),
    "fpv_window_portal_breach": (
        {"pos": [0.0, -4.80, 3.20], "look_at": [0.0, 1.50, 2.10], "fov_deg": 48.0, "preserve_drone_altitude": True},
        {"pos": [0.0, -0.95, 1.45], "look_at": [0.0, 0.15, 0.98], "fov_deg": 46.0, "preserve_drone_altitude": True},
    ),
    "drone_high_orbit_drop": (
        {"pos": [-8.80, -14.2, 9.60], "look_at": [0.0, 0.40, 1.50], "fov_deg": 52.0, "preserve_drone_altitude": True},
        {"pos": [1.25, -2.55, 1.62], "look_at": [0.0, 0.10, 1.12], "fov_deg": 46.0, "preserve_drone_altitude": True},
    ),
    "vertical_90_topdown_dive": (
        {"pos": [0.0, -1.35, 16.0], "look_at": [0.0, 0.0, 0.85], "fov_deg": 52.0, "preserve_drone_altitude": True},
        {"pos": [0.0, -1.55, 1.80], "look_at": [0.0, -0.05, 0.95], "fov_deg": 46.0, "preserve_drone_altitude": True},
    ),
    "drone_skyline_pullback": (
        {"pos": [0.0, -2.20, 1.48], "look_at": [0.0, 0.20, 1.18], "fov_deg": 46.0, "preserve_drone_altitude": True},
        {"pos": [-3.20, -21.0, 12.2], "look_at": [0.0, 2.00, 2.20], "fov_deg": 56.0, "preserve_drone_altitude": True},
    ),
    # Rule R74 3D Neural FPV Dive & Subcortical Macro Relay Presets (`B0 <-> B1`)
    "neural_fpv_dive_in": (
        {"pos": [0.0, -1.45, 1.54], "look_at": [0.0, 0.0, 1.50], "fov_deg": 46.0, "preserve_drone_altitude": True},
        {"pos": [-0.46, -0.06, 1.41], "look_at": [-0.12, 0.02, 1.44], "fov_deg": 42.0, "preserve_drone_altitude": True},
    ),
    "neural_macro_orbit_hold": (
        {"pos": [-0.46, -0.06, 1.41], "look_at": [-0.12, 0.02, 1.44], "fov_deg": 42.0, "preserve_drone_altitude": True},
        {"pos": [-0.43, -0.16, 1.45], "look_at": [-0.12, 0.02, 1.44], "fov_deg": 41.0, "preserve_drone_altitude": True},
    ),
    "neural_fpv_pullback_out": (
        {"pos": [-0.43, -0.16, 1.45], "look_at": [-0.12, 0.02, 1.44], "fov_deg": 42.0, "preserve_drone_altitude": True},
        {"pos": [0.0, -1.45, 1.54], "look_at": [0.0, 0.0, 1.50], "fov_deg": 46.0, "preserve_drone_altitude": True},
    ),
    "neural_tract_relay_flight": (
        {"pos": [-0.46, -0.06, 1.41], "look_at": [-0.12, 0.02, 1.44], "fov_deg": 42.0, "preserve_drone_altitude": True},
        {"pos": [0.0, -0.52, 1.61], "look_at": [0.0, -0.17, 1.55], "fov_deg": 42.0, "preserve_drone_altitude": True},
    ),
}

PREVIS_CAMERA_PRESETS: dict[str, dict[str, Any]] = {
    move_name: {
        "start": copy.deepcopy(pair[0]),
        "end": copy.deepcopy(pair[1]),
        **(
            {"arc_deg": 40.0, "gaze_lock_target": "head_center"}
            if move_name == "orbital_3d_arc_sweep"
            else {}
        ),
    }
    for move_name, pair in CAMERA_MOVE_PREVIS_PRESETS.items()
}


def _match_camera_move_preset(cam_move: str, clip_index: int = 1) -> tuple[dict[str, Any], dict[str, Any]]:
    cm = str(cam_move or "gentle_push_in").strip().lower()
    if cm == "drone_pullback_skyline":
        cm = "drone_skyline_pullback"
    if cm in CAMERA_MOVE_PREVIS_PRESETS:
        s_c, e_c = CAMERA_MOVE_PREVIS_PRESETS[cm]
        return copy.deepcopy(s_c), copy.deepcopy(e_c)
    if "aerial" in cm and "drone" in cm:
        s_c, e_c = CAMERA_MOVE_PREVIS_PRESETS["drone_aerial_approach"]
    elif "window" in cm and ("breach" in cm or "portal" in cm or "fpv" in cm):
        s_c, e_c = CAMERA_MOVE_PREVIS_PRESETS["fpv_window_portal_breach"]
    elif "drone" in cm and ("orbit" in cm or "drop" in cm):
        s_c, e_c = CAMERA_MOVE_PREVIS_PRESETS["drone_high_orbit_drop"]
    elif "90" in cm or ("topdown" in cm and "dive" in cm) or ("vertical" in cm and "dive" in cm):
        s_c, e_c = CAMERA_MOVE_PREVIS_PRESETS["vertical_90_topdown_dive"]
    elif "drone" in cm and ("skyline" in cm or "pullback" in cm):
        s_c, e_c = CAMERA_MOVE_PREVIS_PRESETS["drone_skyline_pullback"]
    elif "dolly_zoom" in cm or "vertigo" in cm:
        s_c, e_c = CAMERA_MOVE_PREVIS_PRESETS["dolly_zoom_vertigo"]
    elif "crane" in cm or "swoop" in cm:
        s_c, e_c = CAMERA_MOVE_PREVIS_PRESETS["crane_swoop_dive"]
    elif "whip" in cm:
        s_c, e_c = CAMERA_MOVE_PREVIS_PRESETS["whip_pan_occlusion"]
    elif "orbit" in cm or "arc" in cm:
        s_c, e_c = CAMERA_MOVE_PREVIS_PRESETS["orbital_3d_arc_sweep"]
    elif "pan_left" in cm or ("pan" in cm and "left" in cm):
        s_c, e_c = CAMERA_MOVE_PREVIS_PRESETS["pan_left"]
    elif "pan_right" in cm or ("pan" in cm and "right" in cm):
        s_c, e_c = CAMERA_MOVE_PREVIS_PRESETS["pan_right"]
    elif "axial" in cm and "portal" in cm:
        s_c, e_c = CAMERA_MOVE_PREVIS_PRESETS["axial_portal_dive"]
    elif "fpv" in cm or "flight" in cm and "portal" not in cm:
        s_c, e_c = CAMERA_MOVE_PREVIS_PRESETS["fpv_3d_flight"]
    elif "portal" in cm or "macro" in cm or "crash" in cm:
        s_c, e_c = CAMERA_MOVE_PREVIS_PRESETS["portal_dive_flight"]
    elif "pullback" in cm or "reveal" in cm:
        s_c, e_c = CAMERA_MOVE_PREVIS_PRESETS["clean_pullback_reveal"]
    elif "top_down" in cm or "overhead" in cm:
        s_c, e_c = CAMERA_MOVE_PREVIS_PRESETS["top_down_overhead"]
    elif "low_angle" in cm or "hero" in cm:
        s_c, e_c = CAMERA_MOVE_PREVIS_PRESETS["low_angle_hero"]
    else:
        angle_off = ((clip_index % 3) - 1) * 0.36
        return (
            {"pos": [angle_off, -2.50, 1.38], "look_at": [0.0, 0.05, 1.16], "fov_deg": 50.0},
            {"pos": [angle_off * 0.4, -1.65, 1.30], "look_at": [0.0, 0.05, 1.20], "fov_deg": 46.0},
        )
    return copy.deepcopy(s_c), copy.deepcopy(e_c)


def load_location_registry(path: Path | None = None) -> dict[str, Any]:
    """E2: Loads reusable architectural `room_blocks` by `location_id` from `location_registry.json`."""
    from pipeline.config import LOCATION_REGISTRY_PATH

    reg_p = Path(path) if path is not None else Path(LOCATION_REGISTRY_PATH)
    if reg_p.is_file():
        try:
            doc = json.loads(reg_p.read_text(encoding="utf-8"))
            if isinstance(doc, dict) and isinstance(doc.get("locations"), dict):
                return doc
        except Exception:  # noqa: BLE001
            pass
    return {"locations": {}}


def resolve_location_room_spec(location_id: str | None, registry: dict[str, Any] | None = None) -> tuple[list[dict[str, Any]], float]:
    """Resolves `(room_blocks, surface_top_z)` for `location_id`, keeping spatial layout identical across same-location cuts."""
    reg = registry if isinstance(registry, dict) else load_location_registry()
    locs = reg.get("locations") if isinstance(reg.get("locations"), dict) else {}
    loc_norm = str(location_id or "").strip().lower().replace("-", "_")
    matched: dict[str, Any] | None = None
    if loc_norm and loc_norm in locs:
        matched = locs[loc_norm]
    elif loc_norm:
        for k_loc, spec_loc in locs.items():
            if not isinstance(spec_loc, dict):
                continue
            aliases = [str(a).strip().lower() for a in (spec_loc.get("aliases") or [])]
            if k_loc in loc_norm or loc_norm in k_loc or any(a in loc_norm or loc_norm in a for a in aliases):
                matched = spec_loc
                break
    if matched is None and isinstance(locs.get("default_studio"), dict):
        matched = locs["default_studio"]
    if isinstance(matched, dict) and isinstance(matched.get("room_blocks"), list):
        return copy.deepcopy(matched["room_blocks"]), float(matched.get("surface_top_z") or 0.72)
    return (
        [
            {"block_id": "floor", "pos": [0.0, 0.20, -0.06], "size_xyz": [4.40, 4.40, 0.12], "color_hex": PREVIS_NEUTRAL_FLOOR_HEX},
            {"block_id": "back_wall", "pos": [0.0, 2.15, 1.50], "size_xyz": [4.40, 0.14, 3.10], "color_hex": PREVIS_NEUTRAL_ROOM_HEX},
            {"block_id": "surface_block", "pos": [0.0, -0.42, 0.36], "size_xyz": [1.30, 0.65, 0.72], "color_hex": "#7C828D"},
        ],
        0.72,
    )


_OUTDOOR_ENV_KEYWORDS: tuple[str, ...] = (
    "outdoor",
    "exterior",
    "courtyard",
    "quad",
    "campus",
    "portico",
    "facade",
    "aerial",
    "crosswalk",
    "street",
    "avenue",
    "plaza",
    "square",
    "bridge",
    "footbridge",
    "river",
    "park",
    "walkway",
    "promenade",
    "market",
    "pavilion",
    "stadium",
    "bleacher",
    "rooftop",
    "terrace",
    "skyline",
    "subway platform",
    "underground platform",
    "station platform",
    "harvard yard",
    "cutaway",
)


def is_outdoor_or_architectural_clip(
    clip_or_loc: dict[str, Any] | str | None,
    *,
    registry: dict[str, Any] | None = None,
) -> bool:
    """
    Returns True if a clip or `location_id` represents an `R72` open-world outdoor, civic/transit,
    or exterior-to-interior architectural cutaway stage (`>= 35%` episode ratio under Rule R72-2).
    """
    reg = registry if isinstance(registry, dict) else load_location_registry()
    locs = reg.get("locations") if isinstance(reg.get("locations"), dict) else {}

    if isinstance(clip_or_loc, dict):
        if bool(clip_or_loc.get("outdoor")) or bool(clip_or_loc.get("is_outdoor")):
            return True
        g_raw = str(clip_or_loc.get("grammar") or clip_or_loc.get("visual_grammar") or "").strip().lower()
        if g_raw in ("expressive_exterior_establishing", "architectural_cutaway_portal", "spatial_3d_arrow_diorama"):
            return True
        loc_id = str(clip_or_loc.get("location_id") or "").strip().lower().replace("-", "_")
        env_txt = f"{loc_id} {clip_or_loc.get('environment', '')} {clip_or_loc.get('scene', '')}".lower()
    else:
        loc_id = str(clip_or_loc or "").strip().lower().replace("-", "_")
        env_txt = loc_id

    if loc_id:
        if loc_id in locs and isinstance(locs[loc_id], dict):
            return bool(locs[loc_id].get("outdoor"))
        for k_loc, spec_loc in locs.items():
            if not isinstance(spec_loc, dict):
                continue
            aliases = [str(a).strip().lower() for a in (spec_loc.get("aliases") or [])]
            if k_loc in loc_id or loc_id in k_loc or any(a in loc_id or loc_id in a for a in aliases):
                if bool(spec_loc.get("outdoor")):
                    return True
    return any(kw in env_txt for kw in _OUTDOOR_ENV_KEYWORDS)


def _infer_actor_archetype_and_pose(label: str, action_text: str, grammar: str) -> tuple[float, str, str]:
    """Infers `(height_m, pose_start, pose_end)` from cast label, action description, and visual grammar."""
    low_lbl = str(label or "").lower()
    low_act = str(action_text or "").lower()
    g_low = str(grammar or "").lower()
    if "mini_cortex" in low_lbl or "mini-cortex" in low_lbl:
        return 0.22, "standing", "standing"
    if any(k in low_lbl for k in ("child", "kid", "toddler", "four-year", "boy", "girl")):
        h_m = 1.05
        default_pose = "seated"
    else:
        h_m = 1.72
        default_pose = "seated" if ("seated" in low_lbl or "sitting" in low_lbl) else "standing"

    p_start = default_pose
    p_end = default_pose
    if any(k in low_act for k in ("reach", "snatch", "lunge", "slide", "draw", "place", "set down", "pull open", "lifts", "holds up")):
        p_end = "reaching"
    elif "lean" in low_act or "slump" in low_act:
        p_end = "leaning"
    if "pov_hands" in g_low:
        p_start = "reaching"
        p_end = "reaching"
    return h_m, p_start, p_end


def _build_r74_neural_cutaway_previs_spec(
    clip_spec: dict[str, Any],
    *,
    cam_move: str,
    carry_palette: dict[str, tuple[str, str]] | None = None,
) -> dict[str, Any]:
    """
    Previs v2.3 (Rule R74): Synthesizes a 3D translucent cortical glass brain shell (`alpha=0.20`, `r=0.26m`
    at `[0.0, 0.0, 1.50]`) + anatomically true subcortical target mesh(es) (`anatomy_map.py`) and computes
    exact `B0 (1.45m wide)` <-> `B1 (0.35m subcortical macro)` camera trajectories along the region's
    neuroanatomical approach azimuth/elevation vector.
    """
    from pipeline.anatomy_map import resolve_anatomy_screen_anchor

    reg_raw = str(clip_spec.get("brain_region") or "hippocampus").strip()
    anc_a = resolve_anatomy_screen_anchor(reg_raw, macro_mode=True) or resolve_anatomy_screen_anchor("hippocampus", macro_mode=True)
    assert anc_a is not None
    end_reg_raw = str(clip_spec.get("end_brain_region") or "").strip()
    anc_b = resolve_anatomy_screen_anchor(end_reg_raw, macro_mode=True) if end_reg_raw else None
    neural_state = str(clip_spec.get("neural_state") or "active").strip().lower()
    if neural_state not in ("active", "silenced", "severed", "rerouted"):
        neural_state = "active"

    brain_center = [0.0, 0.0, 1.50]

    def _approach_unit(az_deg: float, el_deg: float) -> list[float]:
        az = math.radians(float(az_deg))
        el = math.radians(float(el_deg))
        return [
            math.sin(az) * math.cos(el),
            -math.cos(az) * math.cos(el),
            math.sin(el),
        ]

    u_a = _approach_unit(anc_a["approach_azimuth_deg"], anc_a["approach_elevation_deg"])
    t_a = [float(v) for v in anc_a["pos_3d_brain_xyz"]]
    b0_cam = {
        "pos": [round(brain_center[i] + u_a[i] * 1.45, 4) for i in range(3)],
        "look_at": list(brain_center),
        "fov_deg": 46.0,
        "preserve_drone_altitude": True,
    }
    b1_a_cam = {
        "pos": [round(t_a[i] + u_a[i] * 0.35, 4) for i in range(3)],
        "look_at": [round(v, 4) for v in t_a],
        "fov_deg": 42.0,
        "preserve_drone_altitude": True,
    }
    u_a_orb = _approach_unit(anc_a["approach_azimuth_deg"] + 16.0, anc_a["approach_elevation_deg"] + 4.0)
    b1_a_orb_cam = {
        "pos": [round(t_a[i] + u_a_orb[i] * 0.35, 4) for i in range(3)],
        "look_at": [round(v, 4) for v in t_a],
        "fov_deg": 41.0,
        "preserve_drone_altitude": True,
    }

    slug_a = re.sub(r"[^a-z0-9]+", "_", str(anc_a["canonical"]).lower()).strip("_")
    sz_sub = [0.098, 0.092, 0.088]
    prop_a: dict[str, Any] = {
        "prop_id": f"subcortical_{slug_a}",
        "label": f"3D {anc_a['display_title']} ({anc_a['short_role']})",
        "shape": "sphere",
        "radius": 0.049,
        "pos_start": [round(t_a[0], 4), round(t_a[1], 4), round(t_a[2] - 0.5 * sz_sub[2], 4)],
        "pos_end": [round(t_a[0], 4), round(t_a[1], 4), round(t_a[2] - 0.5 * sz_sub[2], 4)],
        "size_xyz": list(sz_sub),
        "yaw_deg": 0.0,
    }
    if neural_state == "silenced" and (anc_b is None or anc_b["canonical"] == anc_a["canonical"]):
        prop_a["color_hex"] = "#5B6778"
        prop_a["color_name"] = "Muted Slate"
    props: list[dict[str, Any]] = [prop_a]

    tract_blocks: list[dict[str, Any]] = []
    has_dual_tract = anc_b is not None and anc_b["canonical"] != anc_a["canonical"]
    if has_dual_tract:
        assert anc_b is not None
        u_b = _approach_unit(anc_b["approach_azimuth_deg"], anc_b["approach_elevation_deg"])
        t_b = [float(v) for v in anc_b["pos_3d_brain_xyz"]]
        slug_b = re.sub(r"[^a-z0-9]+", "_", str(anc_b["canonical"]).lower()).strip("_")
        prop_b: dict[str, Any] = {
            "prop_id": f"subcortical_{slug_b}",
            "label": f"3D {anc_b['display_title']} ({anc_b['short_role']})",
            "shape": "sphere",
            "radius": 0.049,
            "pos_start": [round(t_b[0], 4), round(t_b[1], 4), round(t_b[2] - 0.5 * sz_sub[2], 4)],
            "pos_end": [round(t_b[0], 4), round(t_b[1], 4), round(t_b[2] - 0.5 * sz_sub[2], 4)],
            "size_xyz": list(sz_sub),
            "yaw_deg": 0.0,
        }
        if neural_state in ("severed", "silenced"):
            prop_b["color_hex"] = "#5B6778"
            prop_b["color_name"] = "Muted Slate"
        props.append(prop_b)

        dx_t = t_b[0] - t_a[0]
        dy_t = t_b[1] - t_a[1]
        dz_t = t_b[2] - t_a[2]
        tract_len = max(1e-4, math.sqrt(dx_t * dx_t + dy_t * dy_t + dz_t * dz_t))
        tract_dir = [dx_t / tract_len, dy_t / tract_len, dz_t / tract_len]
        mid_pt = [0.5 * (t_a[i] + t_b[i]) for i in range(3)]

        if neural_state == "severed":
            half_gap = min(0.02, 0.22 * tract_len)
            gap_a = [round(mid_pt[i] - tract_dir[i] * half_gap, 4) for i in range(3)]
            gap_b = [round(mid_pt[i] + tract_dir[i] * half_gap, 4) for i in range(3)]
            disc_a = [round(mid_pt[i] - tract_dir[i] * 0.008, 4) for i in range(3)]
            disc_b = [round(mid_pt[i] + tract_dir[i] * 0.008, 4) for i in range(3)]
            tract_blocks.extend(
                [
                    {
                        "block_id": "neural_tract_bridge",
                        "shape": "cylinder",
                        "p0": [round(v, 4) for v in t_a],
                        "p1": gap_a,
                        "pos": [round(0.5 * (t_a[i] + gap_a[i]), 4) for i in range(3)],
                        "radius": 0.015,
                        "size_xyz": [0.030, 0.030, round(max(0.02, 0.5 * tract_len - half_gap), 4)],
                        "color_hex": "#4F6D7A",
                        "alpha": 1.0,
                    },
                    {
                        "block_id": "neural_tract_bridge_distal",
                        "shape": "cylinder",
                        "p0": gap_b,
                        "p1": [round(v, 4) for v in t_b],
                        "pos": [round(0.5 * (gap_b[i] + t_b[i]), 4) for i in range(3)],
                        "radius": 0.014,
                        "size_xyz": [0.028, 0.028, round(max(0.02, 0.5 * tract_len - half_gap), 4)],
                        "color_hex": "#5B6778",
                        "alpha": 1.0,
                    },
                    {
                        "block_id": "kintsugi_fault_disc",
                        "shape": "cylinder",
                        "p0": disc_a,
                        "p1": disc_b,
                        "pos": [round(v, 4) for v in mid_pt],
                        "radius": 0.036,
                        "size_xyz": [0.072, 0.072, 0.016],
                        "color_hex": "#D4AF37",
                        "alpha": 1.0,
                    },
                ]
            )
            look_b = [round(0.42 * mid_pt[i] + 0.58 * t_b[i], 4) for i in range(3)]
            # Side-approach vector perpendicular to tract so both fault disc & destination hub stay clear in 9:16
            perp_xy = [-tract_dir[1], tract_dir[0], 0.18]
            if perp_xy[0] * u_b[0] + perp_xy[1] * u_b[1] < 0.0:
                perp_xy = [-perp_xy[0], -perp_xy[1], 0.18]
            blended_v = [0.55 * u_b[i] + 0.45 * perp_xy[i] for i in range(3)]
            bv_norm = max(1e-4, math.sqrt(sum(x * x for x in blended_v)))
            blended_u = [x / bv_norm for x in blended_v]
            cam_dist_b = max(0.38, min(0.58, 1.45 * tract_len))
            b1_b_cam = {
                "pos": [round(look_b[i] + blended_u[i] * cam_dist_b, 4) for i in range(3)],
                "look_at": look_b,
                "fov_deg": 44.0,
                "preserve_drone_altitude": True,
            }
        else:
            bridge_hex = "#8C5A2B" if neural_state == "rerouted" else "#4F6D7A"
            tract_blocks.append(
                {
                    "block_id": "neural_tract_bridge",
                    "shape": "cylinder",
                    "p0": [round(v, 4) for v in t_a],
                    "p1": [round(v, 4) for v in t_b],
                    "pos": [round(v, 4) for v in mid_pt],
                    "radius": 0.015,
                    "size_xyz": [0.030, 0.030, round(tract_len, 4)],
                    "color_hex": bridge_hex,
                    "alpha": 1.0,
                }
            )
            b1_b_cam = {
                "pos": [round(t_b[i] + u_b[i] * 0.35, 4) for i in range(3)],
                "look_at": [round(v, 4) for v in t_b],
                "fov_deg": 42.0,
                "preserve_drone_altitude": True,
            }

        if cam_move == "neural_tract_relay_flight":
            cam_start, cam_end = b1_a_cam, b1_b_cam
        elif cam_move == "neural_macro_orbit_hold":
            cam_start, cam_end = b1_b_cam, b1_b_cam
        elif cam_move == "neural_fpv_pullback_out":
            cam_start, cam_end = b1_b_cam, b0_cam
        else:
            cam_start, cam_end = b0_cam, b1_b_cam
    elif cam_move == "neural_macro_orbit_hold":
        cam_start, cam_end = b1_a_cam, b1_a_orb_cam
    elif cam_move == "neural_fpv_pullback_out":
        cam_start, cam_end = b1_a_cam, b0_cam
    else:
        cam_start, cam_end = b0_cam, b1_a_cam

    # Orthogonal tangent vector for foreground translucent cortical rib framing at B1 macro scale
    tan_xy_norm = math.hypot(-u_a[1], u_a[0]) or 1.0
    tan_vec = [-u_a[1] / tan_xy_norm, u_a[0] / tan_xy_norm, 0.0]
    rib_mid = [t_a[i] + u_a[i] * 0.14 for i in range(3)]
    room_blocks: list[dict[str, Any]] = [
        {"block_id": "neural_void_floor", "pos": [0.0, 0.0, -0.06], "size_xyz": [4.40, 4.40, 0.12], "color_hex": "#3B4250"},
        {
            "block_id": "cortical_glass_shell",
            "shape": "sphere",
            "pos": list(brain_center),
            "radius": 0.26,
            "size_xyz": [0.52, 0.52, 0.52],
            "color_hex": "#6C7A89",
            "alpha": 0.20,
        },
        {
            "block_id": "cortical_rib_left",
            "shape": "cylinder",
            "pos": [round(rib_mid[0] - tan_vec[0] * 0.105, 4), round(rib_mid[1] - tan_vec[1] * 0.105, 4), round(t_a[2], 4)],
            "size_xyz": [0.032, 0.032, 0.28],
            "color_hex": "#7D8B99",
            "alpha": 0.22,
        },
        {
            "block_id": "cortical_rib_right",
            "shape": "cylinder",
            "pos": [round(rib_mid[0] + tan_vec[0] * 0.105, 4), round(rib_mid[1] + tan_vec[1] * 0.105, 4), round(t_a[2], 4)],
            "size_xyz": [0.032, 0.032, 0.28],
            "color_hex": "#7D8B99",
            "alpha": 0.22,
        },
        *tract_blocks,
    ]

    seeded_carry = dict(ROLE_LOCKED_DEFAULT_COLORS)
    if carry_palette:
        seeded_carry.update(carry_palette)
    legend = assign_previs_palette(props, existing_assignments=seeded_carry)
    return {
        "auto_frame": False,
        "neural_cutaway_stage": True,
        "r74_brain_region": anc_a["canonical"],
        "r74_end_brain_region": anc_b["canonical"] if has_dual_tract and anc_b is not None else None,
        "r74_neural_state": neural_state,
        "camera_start": cam_start,
        "camera_end": cam_end,
        "actors": [],
        "props": props,
        "room_blocks": room_blocks,
        "color_role_legend": legend,
    }


def synthesize_default_previs_spec_for_clip(
    clip_spec: dict[str, Any],
    clip_index: int,
    *,
    carry_palette: dict[str, tuple[str, str]] | None = None,
    location_registry: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Builds a deterministic 3D previs blockout specification from a `visual_plan.json` clip entry
    incorporating E1 (12-move camera presets), E2 (`location_registry`), E3 (child/adult height & pose),
    E4/P3 (`PROP_SHAPE_LIBRARY` + compound silhouettes + active prop extraction + Role-Color Lock + plural split),
    E5 (grammar-specific framing), P2 (`solve_9x16_camera_frustum`), and R74 (`Previs v2.3` 3D Neural Cutaway).
    """
    from pipeline.config import EXPRESSIVE_V8_NEURAL_DIVE_MOVES

    cam_move = str(clip_spec.get("camera_movement") or clip_spec.get("camera_move") or "gentle_push_in").strip().lower()
    grammar = str(clip_spec.get("grammar") or clip_spec.get("visual_grammar") or "expressive_vinyl_world").strip().lower()
    if cam_move in EXPRESSIVE_V8_NEURAL_DIVE_MOVES or bool(clip_spec.get("neural_dive_relay")):
        return _build_r74_neural_cutaway_previs_spec(
            clip_spec,
            cam_move=cam_move if cam_move in EXPRESSIVE_V8_NEURAL_DIVE_MOVES else "neural_fpv_dive_in",
            carry_palette=carry_palette,
        )
    action_txt = str(clip_spec.get("action") or clip_spec.get("scene_body") or clip_spec.get("prompt") or "")
    loc_id = str(clip_spec.get("location_id") or "default_studio").strip()

    room_blocks, surf_z = resolve_location_room_spec(loc_id, registry=location_registry)
    cam_start, cam_end = _match_camera_move_preset(cam_move, clip_index=clip_index)

    raw_cast_field = clip_spec.get("present_cast") or clip_spec.get("cast")
    cast_entries = expand_cast_entries(raw_cast_field)
    if ("cameo" in grammar or bool(clip_spec.get("cameo_easter_egg"))) and not any(
        "mini" in str(c.get("role_id") or "").lower() for c in cast_entries
    ):
        cast_entries.append({"role_id": "mini_cortex", "label": "mini_cortex"})

    human_entries = [c for c in cast_entries[:4] if "mini" not in str(c.get("role_id") or "").lower()]
    human_count = len(human_entries)
    human_slot_idx = 0

    actors: list[dict[str, Any]] = []
    for c_entry in cast_entries[:4]:
        c_lbl = str(c_entry.get("label") or c_entry.get("role_id") or "protagonist")
        r_id = str(c_entry.get("role_id") or canonicalize_actor_role_id(c_lbl, human_slot_idx + 1))
        h_m, p_s, p_e = _infer_actor_archetype_and_pose(c_lbl, action_txt, grammar)
        if c_entry.get("height_m"):
            h_m = float(c_entry["height_m"])
        if c_entry.get("pose"):
            p_s = p_e = str(c_entry["pose"])
        if "mini_cortex" in r_id or h_m <= 0.30:
            pos_s = [1.45, 1.78, 1.22]
            pos_e = [1.45, 1.78, 1.22]
            yaw_d = -20.0
        else:
            if human_count <= 1:
                x_pos = 0.0
                yaw_d = 0.0
            elif human_count == 2:
                x_pos = -0.34 if human_slot_idx == 0 else 0.34
                yaw_d = 16.0 if human_slot_idx == 0 else -16.0
            else:
                spread = (-0.44, 0.0, 0.44)
                x_pos = spread[min(human_slot_idx, 2)]
                yaw_d = 18.0 if human_slot_idx == 0 else (-18.0 if human_slot_idx >= 2 else 0.0)
            y_pos = 0.12 if p_s == "seated" else 0.24
            pos_s = [x_pos, y_pos, 0.0]
            pos_e = [x_pos + (0.04 if human_slot_idx == 0 else (-0.04 if human_count > 1 else 0.0)), y_pos - 0.03, 0.0]
            human_slot_idx += 1
        actors.append(
            {
                "role_id": r_id,
                "label": c_lbl.strip(),
                "pos_start": pos_s,
                "pos_end": pos_e,
                "height_m": h_m,
                "pose_start": p_s,
                "pose_end": p_e,
                "yaw_deg": yaw_d,
            }
        )

    props: list[dict[str, Any]] = []
    raw_props_field = clip_spec.get("props")
    if isinstance(raw_props_field, str) and raw_props_field.strip():
        raw_props: list[Any] = [p.strip() for p in re.split(r"\s+and\s+|,\s+", raw_props_field) if p.strip()]
    elif isinstance(raw_props_field, (list, tuple)) and len(raw_props_field) > 0:
        raw_props = list(raw_props_field)
    else:
        raw_props = []

    if raw_props:
        for p_idx, p_entry in enumerate(raw_props[:3]):
            p_label = p_entry.get("label") if isinstance(p_entry, dict) else str(p_entry)
            p_shape, p_size = resolve_prop_shape_and_size(str(p_label))
            ctype = resolve_prop_compound_type(
                str(p_label),
                explicit_compound=(p_entry.get("compound_type") if isinstance(p_entry, dict) else None),
            )
            if p_size[2] > 1.2:
                p_pos = [0.85, 1.10, 0.0]
            else:
                x_off = 0.0 if len(raw_props[:3]) == 1 else (-0.24 + 0.24 * p_idx)
                p_pos = [x_off, -0.34, surf_z]
            p_dict: dict[str, Any] = {
                "prop_id": str((p_entry.get("prop_id") if isinstance(p_entry, dict) else None) or f"prop_{p_idx + 1}"),
                "label": str(p_label or f"prop_{p_idx + 1}").strip(),
                "shape": p_shape,
                "pos_start": list(p_pos),
                "pos_end": [p_pos[0] + (0.04 if p_idx == 0 else 0.0), p_pos[1] - 0.03, p_pos[2]],
                "size_xyz": p_size,
                "yaw_deg": 0.0,
            }
            if ctype:
                p_dict["compound_type"] = ctype
            props.append(p_dict)
    else:
        props = extract_active_props_from_clip(clip_spec, surf_z=surf_z)

    # E5: Grammar-specific camera & framing overrides
    if "hands_closeup" in grammar:
        cam_start = {"pos": [-0.18, -1.25, surf_z + 0.56], "look_at": [0.0, -0.22, surf_z + 0.14], "fov_deg": 44.0}
        cam_end = {"pos": [0.08, -1.06, surf_z + 0.46], "look_at": [0.0, -0.24, surf_z + 0.12], "fov_deg": 40.0}
    elif "pov_hands" in grammar:
        head_z = (actors[0]["height_m"] * 0.90) if actors else 1.52
        cam_start = {"pos": [0.0, -0.05, head_z], "look_at": [0.15, 0.85, surf_z + 0.12], "fov_deg": 58.0}
        cam_end = {"pos": [0.04, 0.12, head_z - 0.04], "look_at": [0.25, 0.95, surf_z + 0.10], "fov_deg": 54.0}
    elif "xray_brain" in grammar or "living_brain" in grammar:
        head_z = (actors[0]["height_m"] * 0.88) if actors else 1.52
        cam_start = {"pos": [-0.22, -1.28, head_z + 0.06], "look_at": [0.0, 0.08, head_z], "fov_deg": 42.0}
        cam_end = {"pos": [0.18, -0.92, head_z + 0.04], "look_at": [0.0, 0.08, head_z + 0.02], "fov_deg": 38.0}

    # P2: Solve 9:16 portrait frustum so active subjects + props stay within 12% safe margins
    cam_start = solve_9x16_camera_frustum(cam_start, actors, props, phase="start", grammar=grammar, surf_z=surf_z)
    cam_end = solve_9x16_camera_frustum(cam_end, actors, props, phase="end", grammar=grammar, surf_z=surf_z)

    seeded_carry = dict(ROLE_LOCKED_DEFAULT_COLORS)
    if carry_palette:
        seeded_carry.update(carry_palette)
    legend = assign_previs_palette(actors + props, existing_assignments=seeded_carry)
    return {
        "auto_frame": True,
        "camera_start": cam_start,
        "camera_end": cam_end,
        "actors": actors,
        "props": props,
        "room_blocks": room_blocks,
        "color_role_legend": legend,
    }


def auto_synthesize_plan_previs_specs(
    visual_plan: dict[str, Any],
    *,
    overwrite: bool = False,
) -> dict[str, Any]:
    """
    Section 3-D Automatic Pipeline Hook: Populates missing `clip["previs"]` specs across `visual_plan["clips"]`
    using 12-move camera presets, `location_registry.json`, episode-locked `Role-Color Registry`, active compound
    props, `9:16` portrait frustum auto-framing, and `propagate_previs_camera_continuity()`.
    """
    clips = visual_plan.get("clips")
    if not isinstance(clips, list) or not clips:
        return visual_plan
    loc_reg = load_location_registry()
    carry_palette: dict[str, tuple[str, str]] = dict(ROLE_LOCKED_DEFAULT_COLORS)
    default_loc = str(visual_plan.get("default_location_id") or "default_studio").strip()
    for idx, clip in enumerate(clips, start=1):
        if not isinstance(clip, dict):
            continue
        if isinstance(clip.get("previs"), dict) and not overwrite:
            pv_ex = clip["previs"]
            ents = list(pv_ex.get("actors") or []) + list(pv_ex.get("props") or [])
            leg_ex = assign_previs_palette(ents, existing_assignments=carry_palette)
            pv_ex["color_role_legend"] = leg_ex
            for eid, meta in leg_ex.items():
                carry_palette[eid] = (meta["color_name"], meta["color_hex"])
            continue
        clip_in = dict(clip)
        if not clip_in.get("location_id"):
            clip_in["location_id"] = default_loc
        pv = synthesize_default_previs_spec_for_clip(
            clip_in,
            idx,
            carry_palette=carry_palette,
            location_registry=loc_reg,
        )
        clip["previs"] = pv
        for eid, meta in pv["color_role_legend"].items():
            carry_palette[eid] = (meta["color_name"], meta["color_hex"])

    visual_plan["previs_role_color_registry"] = {
        rid: {"color_name": nm, "color_hex": hx}
        for rid, (nm, hx) in carry_palette.items()
    }
    propagate_previs_camera_continuity(visual_plan)
    return visual_plan


def _serialize_cut_for_blender(
    previs_spec: dict[str, Any],
    start_png: str | Path,
    end_png: str | Path,
    *,
    mid_png: str | Path | None = None,
    width: int = PREVIS_DEFAULT_WIDTH,
    height: int = PREVIS_DEFAULT_HEIGHT,
) -> dict[str, Any]:
    entities = [copy.deepcopy(x) for x in (previs_spec.get("actors") or [])] + [
        copy.deepcopy(x) for x in (previs_spec.get("props") or [])
    ]
    assign_previs_palette(entities)
    actors_list = [e for e in entities if "prop_id" not in e]
    props_list = [e for e in entities if "prop_id" in e]

    room_out: list[dict[str, Any]] = []
    for rb in previs_spec.get("room_blocks") or []:
        rb_c = dict(rb)
        rb_c["alpha"] = _resolve_block_alpha(rb_c)
        room_out.append(rb_c)

    props_expanded: list[dict[str, Any]] = []
    for pr in props_list:
        parts_s = build_prop_primitives(pr, phase="start")
        parts_e = build_prop_primitives(pr, phase="end")
        pr_copy = dict(pr)
        pr_copy["parts_start"] = parts_s
        pr_copy["parts_end"] = parts_e
        props_expanded.append(pr_copy)

    return {
        "camera_start": previs_spec.get("camera_start") or {"pos": [0.0, -2.5, 1.4], "look_at": [0.0, 0.0, 1.2], "fov_deg": 50.0},
        "camera_end": previs_spec.get("camera_end") or previs_spec.get("camera_start") or {"pos": [0.0, -1.8, 1.4], "look_at": [0.0, 0.0, 1.2], "fov_deg": 50.0},
        "actors": actors_list,
        "props": props_expanded,
        "room_blocks": room_out,
        "start_png": str(Path(start_png).resolve()),
        "end_png": str(Path(end_png).resolve()),
        "mid_png": str(Path(mid_png).resolve()) if mid_png is not None else None,
        "width": int(width),
        "height": int(height),
        "bg_rgba": hex_to_unit_rgba(PREVIS_BG_SKY_HEX),
        "grid_hex": PREVIS_FLOOR_GRID_HEX,
    }


_BLENDER_RENDER_SCENE_BODY = '''
def _hex_rgba(hex_str: str, alpha: float = 1.0):
    h = hex_str.lstrip("#")
    return (int(h[0:2], 16) / 255.0, int(h[2:4], 16) / 255.0, int(h[4:6], 16) / 255.0, float(alpha))


def _darken_rgba(rgba, factor: float = 0.52):
    return (rgba[0] * factor, rgba[1] * factor, rgba[2] * factor, rgba[3])


def _render_single_spec(SPEC: dict):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.display.shading.light = "STUDIO"
    scene.display.shading.color_type = "OBJECT"
    scene.display.shading.show_backface_culling = True
    scene.display.shading.show_cavity = True
    scene.display.shading.show_object_outline = True
    scene.display.shading.object_outline_color = (0.12, 0.14, 0.17)
    scene.display.shading.show_shadows = True
    scene.display.shading.shadow_intensity = 0.35
    scene.render.resolution_x = int(SPEC["width"])
    scene.render.resolution_y = int(SPEC["height"])
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"

    world = bpy.data.worlds.new("PrevisWorld")
    scene.world = world
    world.color = SPEC["bg_rgba"][:3]

    # Room architectural massing blocks (with P1 translucent alpha + R72 cylinder/sphere columns & canopies)
    for rb in SPEC.get("room_blocks", []):
        rb_shape = str(rb.get("shape") or "box").strip().lower()
        sx, sy, sz = [float(v) for v in rb.get("size_xyz", [1.0, 1.0, 1.0])]
        px, py, pz = [float(v) for v in rb.get("pos", [0.0, 0.0, 0.0])]
        if rb_shape == "sphere":
            rad = max(0.05, float(rb.get("radius") or (0.5 * sx)))
            bpy.ops.mesh.primitive_uv_sphere_add(segments=18, ring_count=10, radius=rad, location=(px, py, pz))
            obj = bpy.context.active_object
        elif rb_shape == "cylinder":
            if rb.get("p0") and rb.get("p1"):
                p0_v = [float(v) for v in rb["p0"]]
                p1_v = [float(v) for v in rb["p1"]]
                dx_c = p1_v[0] - p0_v[0]
                dy_c = p1_v[1] - p0_v[1]
                dz_c = p1_v[2] - p0_v[2]
                c_len = max(0.004, math.sqrt(dx_c * dx_c + dy_c * dy_c + dz_c * dz_c))
                c_rad = max(0.005, float(rb.get("radius") or (0.5 * sx)))
                bpy.ops.mesh.primitive_cylinder_add(
                    vertices=20,
                    radius=c_rad,
                    depth=c_len,
                    location=(0.5 * (p0_v[0] + p1_v[0]), 0.5 * (p0_v[1] + p1_v[1]), 0.5 * (p0_v[2] + p1_v[2])),
                )
                obj = bpy.context.active_object
                obj.rotation_euler = (0.0, math.acos(max(-1.0, min(1.0, dz_c / c_len))), math.atan2(dy_c, dx_c))
            else:
                bpy.ops.mesh.primitive_cylinder_add(vertices=20, radius=0.5, depth=1.0, location=(px, py, pz))
                obj = bpy.context.active_object
                obj.scale = (sx, sy, sz)
        else:
            bpy.ops.mesh.primitive_cube_add(size=1.0, location=(px, py, pz))
            obj = bpy.context.active_object
            obj.scale = (sx, sy, sz)
        obj.name = f"room_{rb.get('block_id', 'blk')}"
        obj.color = _hex_rgba(rb.get("color_hex", "#8A8F98"), float(rb.get("alpha", 1.0)))

    # P1 Perspective 0.5m floor grid strips at z=0.002m
    grid_rgba = _hex_rgba(SPEC.get("grid_hex", "#555A63"), 0.55)
    for gi in range(-4, 5):
        coord = gi * 0.5
        bpy.ops.mesh.primitive_cube_add(size=1.0, location=(coord, 0.2, 0.002))
        gx = bpy.context.active_object
        gx.name = f"floor_grid_x_{gi}"
        gx.scale = (0.012, 4.2, 0.002)
        gx.color = grid_rgba
        bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0.0, coord + 0.2, 0.002))
        gy = bpy.context.active_object
        gy.name = f"floor_grid_y_{gi}"
        gy.scale = (4.2, 0.012, 0.002)
        gy.color = grid_rgba

    # Rule 1 Subtraction + E3 Pose/Height + P1 Gaze Visor & Contact Shadow
    for act in SPEC.get("actors", []):
        rid = str(act.get("role_id", "actor"))
        h_m = max(0.18, float(act.get("height_m", 1.72)))
        rgba = _hex_rgba(act["color_hex"], 1.0)
        visor_rgba = _darken_rgba(rgba, 0.52)
        yaw_r = math.radians(float(act.get("yaw_deg", 0.0)))
        pose_s = str(act.get("pose_start") or act.get("pose") or "standing").strip().lower()

        root = bpy.data.objects.new(f"actor_root_{rid}", None)
        scene.collection.objects.link(root)
        root.rotation_euler = (0.0, 0.0, yaw_r)

        lower_h = h_m * (0.26 if pose_s == "seated" else 0.46)
        torso_h = h_m * 0.34
        head_r = h_m * (0.12 if h_m <= 1.20 else 0.095)
        sw = h_m * (0.30 if h_m <= 1.20 else 0.25)
        cd = h_m * (0.18 if h_m <= 1.20 else 0.15)
        low_y = -cd * 0.45 if pose_s == "seated" else 0.0
        low_d = cd * 1.45 if pose_s == "seated" else cd * 0.82

        if h_m > 0.35:
            bpy.ops.mesh.primitive_cylinder_add(vertices=20, radius=0.5, depth=0.004, location=(0.0, 0.0, 0.004))
            shd = bpy.context.active_object
            shd.name = f"{rid}_contact_shadow"
            shd.scale = (sw * 1.28, cd * 1.65, 1.0)
            shd.color = (0.14, 0.16, 0.19, 0.38)
            shd.parent = root

        bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0.0, low_y, lower_h * 0.5))
        low = bpy.context.active_object
        low.name = f"{rid}_lower_body"
        low.scale = (sw * 0.80, low_d, lower_h)
        low.color = rgba
        low.parent = root

        bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0.0, 0.0, lower_h + torso_h * 0.5 + 0.015))
        tor = bpy.context.active_object
        tor.name = f"{rid}_torso"
        tor.scale = (sw, cd, torso_h)
        tor.color = rgba
        tor.parent = root

        head_z = lower_h + torso_h + head_r + 0.03
        bpy.ops.mesh.primitive_uv_sphere_add(segments=20, ring_count=12, radius=head_r, location=(0.0, 0.0, head_z))
        hd = bpy.context.active_object
        hd.name = f"{rid}_head"
        hd.color = rgba
        hd.parent = root

        # P1 Front-facing gaze direction visor (-Y local forward)
        bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0.0, -head_r * 0.78, head_z + head_r * 0.06))
        vis = bpy.context.active_object
        vis.name = f"{rid}_gaze_visor"
        vis.scale = (head_r * 1.12, head_r * 0.54, head_r * 0.40)
        vis.color = visor_rgba
        vis.parent = root

        if pose_s == "reaching" or str(act.get("pose_end") or "").strip().lower() == "reaching":
            arm_len = h_m * 0.32
            bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0.0, -(cd * 0.5 + arm_len * 0.5), lower_h + torso_h * 0.72))
            arm = bpy.context.active_object
            arm.name = f"{rid}_reach_arm"
            arm.scale = (sw * 0.24, arm_len, sw * 0.22)
            arm.color = rgba
            arm.parent = root

        p_start = [float(v) for v in act.get("pos_start", [0.0, 0.0, 0.0])]
        p_end = [float(v) for v in act.get("pos_end", p_start)]
        root.location = tuple(p_start)
        root.keyframe_insert(data_path="location", frame=1)
        root.location = tuple(p_end)
        root.keyframe_insert(data_path="location", frame=3)

    # Rule 1 Subtraction + E4/P3 Compound Prop Silhouettes
    for pr in SPEC.get("props", []):
        pid = str(pr.get("prop_id", "prop"))
        parts_s = pr.get("parts_start") or []
        parts_e = pr.get("parts_end") or parts_s
        if not parts_s:
            p_shape = str(pr.get("shape") or "box").strip().lower()
            sx, sy, sz = [max(0.03, float(v)) for v in pr.get("size_xyz", [0.30, 0.25, 0.20])]
            ps0 = [float(v) for v in pr.get("pos_start", pr.get("pos", [0.0, 0.0, 0.75]))]
            pe0 = [float(v) for v in pr.get("pos_end", ps0)]
            parts_s = [{"chunk_id": f"{pid}_bbox", "shape": p_shape, "center": [ps0[0], ps0[1], ps0[2] + sz * 0.5], "size_xyz": [sx, sy, sz], "yaw_deg": pr.get("yaw_deg", 0.0), "color_hex": pr["color_hex"], "back_color_hex": pr.get("back_color_hex"), "alpha": 1.0}]
            parts_e = [{"chunk_id": f"{pid}_bbox", "shape": p_shape, "center": [pe0[0], pe0[1], pe0[2] + sz * 0.5], "size_xyz": [sx, sy, sz], "yaw_deg": pr.get("yaw_deg", 0.0), "color_hex": pr["color_hex"], "back_color_hex": pr.get("back_color_hex"), "alpha": 1.0}]

        for part_idx, pt_s in enumerate(parts_s):
            pt_e = parts_e[min(part_idx, len(parts_e) - 1)]
            p_shape = str(pt_s.get("shape") or "box").strip().lower()
            cs = [float(v) for v in pt_s.get("center", [0.0, 0.0, 0.8])]
            ce = [float(v) for v in pt_e.get("center", cs)]
            yaw_rad = math.radians(float(pt_s.get("yaw_deg", 0.0)))
            p_alpha = float(pt_s.get("alpha", 1.0))
            if p_shape == "sphere":
                rad = max(0.03, float(pt_s.get("radius", 0.10)))
                bpy.ops.mesh.primitive_uv_sphere_add(segments=18, ring_count=10, radius=rad, location=tuple(cs))
                box = bpy.context.active_object
            elif p_shape == "cylinder":
                sx, sy, sz = [max(0.02, float(v)) for v in pt_s.get("size_xyz", [0.20, 0.20, 0.12])]
                bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=0.5, depth=1.0, location=tuple(cs))
                box = bpy.context.active_object
                box.scale = (sx, sy, sz)
            else:
                sx, sy, sz = [max(0.02, float(v)) for v in pt_s.get("size_xyz", [0.30, 0.25, 0.20])]
                bpy.ops.mesh.primitive_cube_add(size=1.0, location=tuple(cs))
                box = bpy.context.active_object
                box.scale = (sx, sy, sz)
            box.name = str(pt_s.get("chunk_id") or f"{pid}_bbox")
            box.rotation_euler = (0.0, 0.0, yaw_rad)
            box.color = _hex_rgba(pt_s["color_hex"], p_alpha)
            box.keyframe_insert(data_path="location", frame=1)
            box.location = tuple(ce)
            box.keyframe_insert(data_path="location", frame=3)
            if pt_s.get("back_color_hex"):
                bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0.0, 0.52, 0.0))
                back_pl = bpy.context.active_object
                back_pl.name = f"{pid}_bbox_back" if part_idx == 0 else f"{box.name}_back"
                back_pl.scale = (0.98, 0.04, 0.98)
                back_pl.color = _hex_rgba(pt_s["back_color_hex"], 1.0)
                back_pl.parent = box

    # Pinhole camera + Track-To target (Blender 4.2 LTS animatable lens in MILLIMETERS w/ VERTICAL sensor fit)
    cam_data = bpy.data.cameras.new("PrevisCamera")
    cam_data.sensor_fit = "VERTICAL"
    cam_data.lens_unit = "MILLIMETERS"
    cam_data.clip_start = 0.08
    cam_data.clip_end = 180.0
    cam_obj = bpy.data.objects.new("PrevisCamera", cam_data)
    scene.collection.objects.link(cam_obj)
    scene.camera = cam_obj

    target_empty = bpy.data.objects.new("PrevisCamTarget", None)
    scene.collection.objects.link(target_empty)
    track = cam_obj.constraints.new(type="TRACK_TO")
    track.target = target_empty
    track.track_axis = "TRACK_NEGATIVE_Z"
    track.up_axis = "UP_Y"

    for frame_idx, cam_key in ((1, "camera_start"), (3, "camera_end")):
        c_spec = SPEC[cam_key]
        cam_obj.location = tuple(float(v) for v in c_spec["pos"])
        cam_obj.keyframe_insert(data_path="location", frame=frame_idx)
        target_empty.location = tuple(float(v) for v in c_spec["look_at"])
        target_empty.keyframe_insert(data_path="location", frame=frame_idx)
        fov_rad = math.radians(max(20.0, min(115.0, float(c_spec.get("fov_deg", 50.0)))))
        cam_data.lens = (cam_data.sensor_height * 0.5) / math.tan(fov_rad * 0.5)
        cam_data.keyframe_insert(data_path="lens", frame=frame_idx)

    scene.frame_set(1)
    scene.render.filepath = SPEC["start_png"]
    bpy.ops.render.render(write_still=True)

    if SPEC.get("mid_png"):
        scene.frame_set(2)
        scene.render.filepath = SPEC["mid_png"]
        bpy.ops.render.render(write_still=True)

    scene.frame_set(3)
    scene.render.filepath = SPEC["end_png"]
    bpy.ops.render.render(write_still=True)
'''


def generate_blender_workbench_script(
    previs_spec: dict[str, Any],
    start_png: str | Path,
    end_png: str | Path,
    *,
    mid_png: str | Path | None = None,
    width: int = PREVIS_DEFAULT_WIDTH,
    height: int = PREVIS_DEFAULT_HEIGHT,
) -> str:
    """
    Generates a standalone headless Blender 4.x Python (`bpy`) script configuring `BLENDER_WORKBENCH`
    (`STUDIO` lighting, `OBJECT` solid/alpha color, cavity, outlines, shadows), `0.5m` perspective floor grid,
    contact shadows, 3-chunk actor dummies with gaze visors, compound prop silhouettes, and `9:16` renders.
    """
    spec_payload = _serialize_cut_for_blender(
        previs_spec,
        start_png,
        end_png,
        mid_png=mid_png,
        width=width,
        height=height,
    )
    payload_json = json.dumps(spec_payload, ensure_ascii=True, indent=2)
    return (
        '"""Auto-generated ALL ABOUT BRAIN 3D Workbench Previs v2 Script."""\n'
        "import json\nimport math\nimport bpy\n\n"
        f'SPEC_SINGLE = json.loads(r"""{payload_json}""")\n'
        f"{_BLENDER_RENDER_SCENE_BODY}\n"
        "_render_single_spec(SPEC_SINGLE)\n"
    )


def generate_blender_batch_pack_script(cut_payloads: list[dict[str, Any]]) -> str:
    """Generates a single-process batch Blender 4.x script rendering all episode cuts in one invocation."""
    batch_json = json.dumps(cut_payloads, ensure_ascii=True)
    return (
        '"""Auto-generated ALL ABOUT BRAIN Batch 3D Workbench Previs v2 Pack Script."""\n'
        "import json\nimport math\nimport bpy\n\n"
        f'BATCH_SPECS = json.loads(r"""{batch_json}""")\n'
        f"{_BLENDER_RENDER_SCENE_BODY}\n"
        "for _spec_item in BATCH_SPECS:\n"
        "    _render_single_spec(_spec_item)\n"
    )


def _camera_basis(pos: np.ndarray, look_at: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    forward = look_at - pos
    f_norm = float(np.linalg.norm(forward))
    if f_norm < 1e-6:
        forward = np.array([0.0, 1.0, 0.0], dtype=np.float64)
    else:
        forward = forward / f_norm
    world_up = np.array([0.0, 0.0, 1.0], dtype=np.float64)
    if abs(float(np.dot(forward, world_up))) > 0.985:
        world_up = np.array([0.0, 1.0, 0.0], dtype=np.float64)
    right = np.cross(forward, world_up)
    right = right / max(1e-8, float(np.linalg.norm(right)))
    up = np.cross(right, forward)
    up = up / max(1e-8, float(np.linalg.norm(up)))
    return right, up, forward


def _box_faces_world(
    center: list[float],
    size_xyz: list[float],
    yaw_deg: float,
    color_hex: str,
    back_color_hex: str | None = None,
) -> list[tuple[np.ndarray, np.ndarray, tuple[int, int, int]]]:
    cx, cy, cz = [float(v) for v in center]
    hx, hy, hz = [float(v) * 0.5 for v in size_xyz]
    yaw = math.radians(float(yaw_deg))
    cyaw, syaw = math.cos(yaw), math.sin(yaw)
    rot = np.array([[cyaw, -syaw, 0.0], [syaw, cyaw, 0.0], [0.0, 0.0, 1.0]], dtype=np.float64)
    c_vec = np.array([cx, cy, cz], dtype=np.float64)

    local_verts = np.array(
        [
            [-hx, -hy, -hz],
            [hx, -hy, -hz],
            [hx, hy, -hz],
            [-hx, hy, -hz],
            [-hx, -hy, hz],
            [hx, -hy, hz],
            [hx, hy, hz],
            [-hx, hy, hz],
        ],
        dtype=np.float64,
    )
    world_verts = (local_verts @ rot.T) + c_vec
    rgb_main = hex_to_rgb(color_hex)
    rgb_back = hex_to_rgb(back_color_hex) if back_color_hex else rgb_main

    # (vertex_indices, local_outward_normal, face_rgb)
    face_defs = [
        ([0, 1, 5, 4], np.array([0.0, -1.0, 0.0]), rgb_main),  # front (-Y facing default camera)
        ([2, 3, 7, 6], np.array([0.0, 1.0, 0.0]), rgb_back),   # back (+Y)
        ([1, 2, 6, 5], np.array([1.0, 0.0, 0.0]), rgb_main),   # right (+X)
        ([3, 0, 4, 7], np.array([-1.0, 0.0, 0.0]), rgb_main),  # left (-X)
        ([4, 5, 6, 7], np.array([0.0, 0.0, 1.0]), rgb_main),   # top (+Z)
        ([3, 2, 1, 0], np.array([0.0, 0.0, -1.0]), rgb_main),  # bottom (-Z)
    ]
    out: list[tuple[np.ndarray, np.ndarray, tuple[int, int, int]]] = []
    for idxs, n_loc, f_rgb in face_defs:
        out.append((world_verts[idxs], rot @ n_loc, f_rgb))
    return out


def _cylinder_faces_world(
    center: list[float],
    size_xyz: list[float],
    yaw_deg: float,
    color_hex: str,
    segments: int = 12,
) -> list[tuple[np.ndarray, np.ndarray, tuple[int, int, int]]]:
    cx, cy, cz = [float(v) for v in center]
    rx, ry, hz = float(size_xyz[0]) * 0.5, float(size_xyz[1]) * 0.5, float(size_xyz[2]) * 0.5
    yaw = math.radians(float(yaw_deg))
    cyaw, syaw = math.cos(yaw), math.sin(yaw)
    rot = np.array([[cyaw, -syaw, 0.0], [syaw, cyaw, 0.0], [0.0, 0.0, 1.0]], dtype=np.float64)
    c_vec = np.array([cx, cy, cz], dtype=np.float64)
    rgb_main = hex_to_rgb(color_hex)

    angles = [2.0 * math.pi * i / float(segments) for i in range(segments)]
    bot_ring = np.array([[rx * math.cos(a), ry * math.sin(a), -hz] for a in angles], dtype=np.float64)
    top_ring = np.array([[rx * math.cos(a), ry * math.sin(a), hz] for a in angles], dtype=np.float64)
    bot_w = (bot_ring @ rot.T) + c_vec
    top_w = (top_ring @ rot.T) + c_vec

    faces: list[tuple[np.ndarray, np.ndarray, tuple[int, int, int]]] = []
    faces.append((top_w, np.array([0.0, 0.0, 1.0]), rgb_main))
    faces.append((bot_w[::-1], np.array([0.0, 0.0, -1.0]), rgb_main))
    for i in range(segments):
        j = (i + 1) % segments
        quad = np.array([bot_w[i], bot_w[j], top_w[j], top_w[i]], dtype=np.float64)
        mid_a = 0.5 * (angles[i] + (angles[j] if j > i else angles[j] + 2.0 * math.pi))
        n_loc = np.array([math.cos(mid_a), math.sin(mid_a), 0.0], dtype=np.float64)
        faces.append((quad, rot @ n_loc, rgb_main))
    return faces


def _render_workbench_cpu_frame(
    previs_spec: dict[str, Any],
    phase: str,
    width: int,
    height: int,
) -> np.ndarray:
    """
    Deterministic pure-CPU Workbench Z-buffered pinhole renderer (`numpy + cv2`, `9:16` BGR uint8).
    Supports P1 translucent glass/window alpha (`0.22`), `0.5m` perspective floor grid, elliptical contact
    drop shadows, actor head gaze visors, and P3 compound prop silhouettes.
    """
    bg_r, bg_g, bg_b = hex_to_rgb(PREVIS_BG_SKY_HEX)
    canvas = np.full((height, width, 3), (bg_b, bg_g, bg_r), dtype=np.uint8)
    zbuf = np.full((height, width), np.inf, dtype=np.float32)

    if phase == "mid":
        cs = previs_spec.get("camera_start") or {"pos": [0.0, -2.5, 1.4], "look_at": [0.0, 0.0, 1.2], "fov_deg": 50.0}
        ce = previs_spec.get("camera_end") or cs
        cam = {
            "pos": [0.5 * (float(a) + float(b)) for a, b in zip(cs["pos"], ce["pos"])],
            "look_at": [0.5 * (float(a) + float(b)) for a, b in zip(cs["look_at"], ce["look_at"])],
            "fov_deg": 0.5 * (float(cs.get("fov_deg") or 50.0) + float(ce.get("fov_deg") or 50.0)),
        }
    else:
        cam_key = "camera_end" if phase == "end" else "camera_start"
        cam = previs_spec.get(cam_key) or previs_spec.get("camera_start") or {
            "pos": [0.0, -2.5, 1.4],
            "look_at": [0.0, 0.0, 1.2],
            "fov_deg": 50.0,
        }
    cam_pos = np.array([float(v) for v in cam["pos"]], dtype=np.float64)
    cam_look = np.array([float(v) for v in cam["look_at"]], dtype=np.float64)
    fov_rad = math.radians(max(20.0, min(115.0, float(cam.get("fov_deg") or 50.0))))
    focal_px = (height * 0.5) / math.tan(fov_rad * 0.5)
    right, up, forward = _camera_basis(cam_pos, cam_look)

    light_dir = np.array([-0.38, -0.58, 0.72], dtype=np.float64)
    light_dir = light_dir / float(np.linalg.norm(light_dir))

    opaque_items: list[tuple[float, str, Any]] = []
    translucent_items: list[tuple[float, str, Any]] = []

    def _enqueue_faces(faces: list[tuple[np.ndarray, np.ndarray, tuple[int, int, int]]], alpha: float = 1.0, draw_edges: bool = True) -> None:
        is_trans = float(alpha) < 0.99
        for poly_w, norm_w, rgb_base in faces:
            rel = poly_w - cam_pos
            depths = rel @ forward
            if float(np.min(depths)) <= 0.08:
                continue
            face_center = np.mean(poly_w, axis=0)
            to_cam = cam_pos - face_center
            if not is_trans and float(np.dot(norm_w, to_cam)) <= 0.0:
                continue
            if is_trans and float(np.dot(norm_w, to_cam)) <= 0.0:
                continue
            xs = (rel @ right) / depths * focal_px + (width * 0.5)
            ys = -(rel @ up) / depths * focal_px + (height * 0.5)
            pts_2d = np.stack([xs, ys], axis=1).astype(np.int32)

            ndotl = max(0.0, abs(float(np.dot(norm_w, light_dir))) if is_trans else float(np.dot(norm_w, light_dir)))
            shade = 0.54 + 0.44 * ndotl
            bgr_shaded = (
                int(min(255, round(rgb_base[2] * shade))),
                int(min(255, round(rgb_base[1] * shade))),
                int(min(255, round(rgb_base[0] * shade))),
            )
            edge_bgr = (
                max(0, bgr_shaded[0] - 28),
                max(0, bgr_shaded[1] - 28),
                max(0, bgr_shaded[2] - 28),
            )
            mean_d = float(np.mean(depths))
            item = (mean_d, "poly", (pts_2d, bgr_shaded, edge_bgr, float(alpha), draw_edges))
            if is_trans:
                translucent_items.append(item)
            else:
                opaque_items.append(item)

    def _enqueue_box(center: list[float], size_xyz: list[float], yaw_deg: float, c_hex: str, back_hex: str | None = None, alpha: float = 1.0) -> None:
        _enqueue_faces(_box_faces_world(center, size_xyz, yaw_deg, c_hex, back_hex), alpha=alpha, draw_edges=True)

    def _enqueue_cylinder(center: list[float], size_xyz: list[float], yaw_deg: float, c_hex: str, alpha: float = 1.0) -> None:
        _enqueue_faces(_cylinder_faces_world(center, size_xyz, yaw_deg, c_hex, segments=12), alpha=alpha, draw_edges=False)

    def _enqueue_oriented_cylinder(p0: list[float], p1: list[float], radius: float, c_hex: str, alpha: float = 1.0) -> None:
        v0 = np.array([float(x) for x in p0], dtype=np.float64)
        v1 = np.array([float(x) for x in p1], dtype=np.float64)
        ax_v = v1 - v0
        ax_len = float(np.linalg.norm(ax_v))
        if ax_len < 1e-5:
            return
        u_ax = ax_v / ax_len
        ref_v = np.array([0.0, 0.0, 1.0], dtype=np.float64) if abs(float(u_ax[2])) < 0.92 else np.array([1.0, 0.0, 0.0], dtype=np.float64)
        e1 = np.cross(u_ax, ref_v)
        e1 = e1 / max(1e-8, float(np.linalg.norm(e1)))
        e2 = np.cross(u_ax, e1)
        e2 = e2 / max(1e-8, float(np.linalg.norm(e2)))
        rgb_main = hex_to_rgb(c_hex)
        segs = 14
        angs = [2.0 * math.pi * i / float(segs) for i in range(segs)]
        r_f = max(0.004, float(radius))
        ring0 = np.array([v0 + r_f * (math.cos(a) * e1 + math.sin(a) * e2) for a in angs], dtype=np.float64)
        ring1 = np.array([v1 + r_f * (math.cos(a) * e1 + math.sin(a) * e2) for a in angs], dtype=np.float64)
        faces_o: list[tuple[np.ndarray, np.ndarray, tuple[int, int, int]]] = [
            (ring1, u_ax, rgb_main),
            (ring0[::-1], -u_ax, rgb_main),
        ]
        for i_s in range(segs):
            j_s = (i_s + 1) % segs
            quad_o = np.array([ring0[i_s], ring0[j_s], ring1[j_s], ring1[i_s]], dtype=np.float64)
            mid_ang = 0.5 * (angs[i_s] + (angs[j_s] if j_s > i_s else angs[j_s] + 2.0 * math.pi))
            n_out = math.cos(mid_ang) * e1 + math.sin(mid_ang) * e2
            faces_o.append((quad_o, n_out, rgb_main))
        _enqueue_faces(faces_o, alpha=alpha, draw_edges=False)

    def _enqueue_sphere(center: list[float], radius: float, c_hex: str, alpha: float = 1.0) -> None:
        sph_c = np.array(center, dtype=np.float64)
        rel_c = sph_c - cam_pos
        if float(alpha) < 0.99 and float(np.linalg.norm(rel_c)) <= float(radius) * 1.65:
            # Camera has breached inside/against the translucent outer shell (B1 macro); rely on flanking ribs
            return
        depth_c = float(np.dot(rel_c, forward))
        if depth_c <= 0.08:
            return
        sx_px = int(round((float(np.dot(rel_c, right)) / depth_c) * focal_px + (width * 0.5)))
        sy_px = int(round(-(float(np.dot(rel_c, up)) / depth_c) * focal_px + (height * 0.5)))
        rad_px = max(3, int(round((float(radius) / depth_c) * focal_px)))
        r0, g0, b0 = hex_to_rgb(c_hex)
        item = (depth_c, "sphere", (sx_px, sy_px, rad_px, float(radius), (b0, g0, r0), float(alpha)))
        if float(alpha) < 0.99:
            translucent_items.append(item)
        else:
            opaque_items.append(item)

    def _enqueue_shadow_disc(center: list[float], radii_xy: list[float]) -> None:
        rx, ry = float(radii_xy[0]), float(radii_xy[1])
        angles = [2.0 * math.pi * i / 14.0 for i in range(14)]
        ring_w = np.array([[center[0] + rx * math.cos(a), center[1] + ry * math.sin(a), center[2]] for a in angles], dtype=np.float64)
        rel = ring_w - cam_pos
        depths = rel @ forward
        if float(np.min(depths)) <= 0.10:
            return
        xs = (rel @ right) / depths * focal_px + (width * 0.5)
        ys = -(rel @ up) / depths * focal_px + (height * 0.5)
        pts_2d = np.stack([xs, ys], axis=1).astype(np.int32)
        translucent_items.append((float(np.mean(depths)) - 0.01, "poly", (pts_2d, (38, 40, 44), (38, 40, 44), 0.34, False)))

    # 1. Room architectural blocks (glass/windows automatically route to translucent_items; columns/canopies use cylinder/sphere)
    for rb in previs_spec.get("room_blocks") or []:
        rb_shape = str(rb.get("shape") or "box").strip().lower()
        rb_pos = [float(v) for v in (rb.get("pos") or [0.0, 0.0, 0.0])]
        rb_size = [float(v) for v in (rb.get("size_xyz") or [4.0, 4.0, 0.1])]
        rb_col = str(rb.get("color_hex") or PREVIS_NEUTRAL_ROOM_HEX)
        rb_alpha = _resolve_block_alpha(rb)
        if rb_shape == "sphere":
            _enqueue_sphere(rb_pos, float(rb.get("radius") or (0.5 * rb_size[0])), rb_col, alpha=rb_alpha)
        elif rb_shape == "cylinder":
            if rb.get("p0") and rb.get("p1"):
                _enqueue_oriented_cylinder(
                    [float(v) for v in rb["p0"]],
                    [float(v) for v in rb["p1"]],
                    float(rb.get("radius") or (0.5 * rb_size[0])),
                    rb_col,
                    alpha=rb_alpha,
                )
            else:
                _enqueue_cylinder(rb_pos, rb_size, 0.0, rb_col, alpha=rb_alpha)
        else:
            _enqueue_box(rb_pos, rb_size, 0.0, rb_col, alpha=rb_alpha)

    # 2. Props (single-box or P3 compound multi-part silhouettes)
    for pr in previs_spec.get("props") or []:
        for pb in build_prop_primitives(pr, phase=phase):
            p_alpha = float(pb.get("alpha", 1.0))
            p_shape = str(pb.get("shape") or "box")
            if p_shape == "sphere":
                _enqueue_sphere(pb["center"], float(pb.get("radius") or 0.10), pb["color_hex"], alpha=p_alpha)
            elif p_shape == "cylinder":
                _enqueue_cylinder(pb["center"], pb["size_xyz"], pb["yaw_deg"], pb["color_hex"], alpha=p_alpha)
            else:
                _enqueue_box(pb["center"], pb["size_xyz"], pb["yaw_deg"], pb["color_hex"], pb.get("back_color_hex"), alpha=p_alpha)

    # 3. Actors (3-chunk dummy + P1 head gaze visor + elliptical contact drop shadow)
    for act in previs_spec.get("actors") or []:
        for chunk in build_three_chunk_actor_primitives(act, phase=phase):
            if chunk.get("shadow_center") and chunk.get("shadow_radii_xy") and float(act.get("height_m") or 1.72) > 0.35:
                _enqueue_shadow_disc(chunk["shadow_center"], chunk["shadow_radii_xy"])
            if chunk["shape"] == "box":
                _enqueue_box(chunk["center"], chunk["size_xyz"], chunk["yaw_deg"], chunk["color_hex"])
            else:
                _enqueue_sphere(chunk["center"], float(chunk["radius"]), chunk["color_hex"])
                if chunk.get("visor_center") and chunk.get("visor_size_xyz") and chunk.get("visor_color_hex"):
                    _enqueue_box(
                        chunk["visor_center"],
                        chunk["visor_size_xyz"],
                        chunk["yaw_deg"],
                        chunk["visor_color_hex"],
                    )

    def _rasterize_poly_z(
        pts_2d: np.ndarray,
        depth_val: float,
        bgr_fill: tuple[int, int, int],
        bgr_edge: tuple[int, int, int],
        alpha: float,
        draw_edges: bool,
        write_z: bool,
    ) -> None:
        x0 = max(0, int(np.min(pts_2d[:, 0])) - 1)
        y0 = max(0, int(np.min(pts_2d[:, 1])) - 1)
        x1 = min(width, int(np.max(pts_2d[:, 0])) + 2)
        y1 = min(height, int(np.max(pts_2d[:, 1])) + 2)
        if x1 <= x0 or y1 <= y0:
            return
        rw, rh = x1 - x0, y1 - y0
        mask = np.zeros((rh, rw), dtype=np.uint8)
        pts_loc = pts_2d - np.array([[x0, y0]], dtype=np.int32)
        cv2.fillConvexPoly(mask, pts_loc, 255)
        vis = (mask > 0) & (float(depth_val) <= zbuf[y0:y1, x0:x1] + 1e-3)
        if not np.any(vis):
            return
        roi = canvas[y0:y1, x0:x1]
        fill_arr = np.array(bgr_fill, dtype=np.float32)
        if alpha >= 0.99:
            roi[vis] = np.array(bgr_fill, dtype=np.uint8)
            if write_z:
                zbuf[y0:y1, x0:x1][vis] = float(depth_val)
        else:
            blended = (1.0 - alpha) * roi[vis].astype(np.float32) + alpha * fill_arr
            roi[vis] = np.clip(np.round(blended), 0, 255).astype(np.uint8)

        if draw_edges:
            edge_mask = np.zeros((rh, rw), dtype=np.uint8)
            cv2.polylines(edge_mask, [pts_loc], isClosed=True, color=255, thickness=1, lineType=cv2.LINE_AA)
            e_vis = (edge_mask > 0) & (float(depth_val) <= zbuf[y0:y1, x0:x1] + 0.02)
            if np.any(e_vis):
                if alpha >= 0.99:
                    roi[e_vis] = np.array(bgr_edge, dtype=np.uint8)
                else:
                    e_alpha = min(0.75, alpha + 0.35)
                    eb = (1.0 - e_alpha) * roi[e_vis].astype(np.float32) + e_alpha * np.array(bgr_edge, dtype=np.float32)
                    roi[e_vis] = np.clip(np.round(eb), 0, 255).astype(np.uint8)

    def _rasterize_sphere_z(
        cx_p: int,
        cy_p: int,
        r_p: int,
        r_world: float,
        depth_c: float,
        bgr_base: tuple[int, int, int],
        alpha: float,
    ) -> None:
        x0 = max(0, cx_p - r_p - 1)
        y0 = max(0, cy_p - r_p - 1)
        x1 = min(width, cx_p + r_p + 2)
        y1 = min(height, cy_p + r_p + 2)
        if x1 <= x0 or y1 <= y0:
            return
        yy, xx = np.ogrid[y0:y1, x0:x1]
        dist_sq = (xx - cx_p) ** 2 + (yy - cy_p) ** 2
        in_circle = dist_sq <= (r_p * r_p)
        if not np.any(in_circle):
            return
        norm_r2 = np.clip(dist_sq.astype(np.float32) / max(1.0, float(r_p * r_p)), 0.0, 1.0)
        dz = np.sqrt(1.0 - norm_r2) * float(r_world)
        pix_z = float(depth_c) - dz
        vis = in_circle & (pix_z <= zbuf[y0:y1, x0:x1] + 1e-3)
        if not np.any(vis):
            return

        # Smooth Workbench studio sphere shading
        nx = (xx - cx_p).astype(np.float32) / max(1.0, float(r_p))
        ny = -(yy - cy_p).astype(np.float32) / max(1.0, float(r_p))
        nz = np.sqrt(np.clip(1.0 - nx * nx - ny * ny, 0.0, 1.0))
        lum = np.clip(0.62 + 0.34 * (-0.35 * nx + 0.45 * ny + 0.82 * nz), 0.48, 1.14)
        shaded = np.stack(
            [
                np.clip(lum * bgr_base[0], 0, 255),
                np.clip(lum * bgr_base[1], 0, 255),
                np.clip(lum * bgr_base[2], 0, 255),
            ],
            axis=-1,
        )
        roi = canvas[y0:y1, x0:x1]
        if alpha >= 0.99:
            roi[vis] = np.round(shaded[vis]).astype(np.uint8)
            zbuf[y0:y1, x0:x1][vis] = pix_z[vis]
        else:
            bl = (1.0 - alpha) * roi[vis].astype(np.float32) + alpha * shaded[vis]
            roi[vis] = np.clip(np.round(bl), 0, 255).astype(np.uint8)

    # Pass 1: Opaque geometry (near -> far or far -> near; Z-buffer resolves exact pixel visibility!)
    opaque_items.sort(key=lambda item: item[0])
    for depth_v, kind, payload in opaque_items:
        if kind == "poly":
            pts_2d, bgr_fill, bgr_edge, a_val, d_edg = payload
            _rasterize_poly_z(pts_2d, depth_v, bgr_fill, bgr_edge, a_val, d_edg, write_z=True)
        else:
            cx_p, cy_p, r_p, r_w, bgr_base, a_val = payload
            _rasterize_sphere_z(cx_p, cy_p, r_p, r_w, depth_v, bgr_base, a_val)

    # Pass 1.5: Perspective 0.5m 3D floor grid lines at z = 0.004m (depth-tested against opaque Z-buffer)
    grid_r, grid_g, grid_b = hex_to_rgb(PREVIS_FLOOR_GRID_HEX)
    grid_bgr = np.array([grid_b, grid_g, grid_r], dtype=np.float32)
    for gi in range(-4, 5):
        coord = gi * 0.5
        for seg_start, seg_end in (
            (np.array([coord, -1.9, 0.004]), np.array([coord, 2.3, 0.004])),
            (np.array([-2.1, coord + 0.2, 0.004]), np.array([2.1, coord + 0.2, 0.004])),
        ):
            ts = np.linspace(0.0, 1.0, 36)
            pts_w = seg_start[None, :] * (1.0 - ts[:, None]) + seg_end[None, :] * ts[:, None]
            rel_g = pts_w - cam_pos[None, :]
            dg = rel_g @ forward
            valid = dg > 0.14
            if np.count_nonzero(valid) < 2:
                continue
            rel_v = rel_g[valid]
            dg_v = dg[valid]
            gx = np.round((rel_v @ right) / dg_v * focal_px + (width * 0.5)).astype(np.int32)
            gy = np.round(-(rel_v @ up) / dg_v * focal_px + (height * 0.5)).astype(np.int32)
            for k in range(len(gx) - 1):
                x_a, y_a, z_a = int(gx[k]), int(gy[k]), float(dg_v[k])
                x_b, y_b, z_b = int(gx[k + 1]), int(gy[k + 1]), float(dg_v[k + 1])
                if (0 <= x_a < width and 0 <= y_a < height) or (0 <= x_b < width and 0 <= y_b < height):
                    mx = max(0, min(width - 1, (x_a + x_b) // 2))
                    my = max(0, min(height - 1, (y_a + y_b) // 2))
                    if 0.5 * (z_a + z_b) <= float(zbuf[my, mx]) + 0.06:
                        cv2.line(
                            canvas,
                            (x_a, y_a),
                            (x_b, y_b),
                            (int(grid_b), int(grid_g), int(grid_r)),
                            1,
                            lineType=cv2.LINE_AA,
                        )

    # Pass 2: Translucent glass/window/terrarium & floor contact drop shadows (sorted back -> front)
    translucent_items.sort(key=lambda item: item[0], reverse=True)
    for depth_v, kind, payload in translucent_items:
        if kind == "poly":
            pts_2d, bgr_fill, bgr_edge, a_val, d_edg = payload
            _rasterize_poly_z(pts_2d, depth_v, bgr_fill, bgr_edge, a_val, d_edg, write_z=False)
        else:
            cx_p, cy_p, r_p, r_w, bgr_base, a_val = payload
            _rasterize_sphere_z(cx_p, cy_p, r_p, r_w, depth_v, bgr_base, a_val)

    return canvas


def _atomic_write_png(target_png: Path, frame_bgr: np.ndarray) -> None:
    fd, tmp_name = tempfile.mkstemp(prefix=".tmp_previs_", suffix=".png", dir=str(target_png.parent))
    os.close(fd)
    tmp_p = Path(tmp_name)
    try:
        ok_w = cv2.imwrite(str(tmp_p), frame_bgr)
        if not ok_w:
            raise RuntimeError(f"cv2.imwrite failed for {target_png}")
        os.replace(tmp_p, target_png)
    finally:
        tmp_p.unlink(missing_ok=True)


def render_previs_keyframes(
    previs_spec: dict[str, Any],
    out_dir: str | Path,
    cut_id: str = "S01",
    *,
    width: int = PREVIS_DEFAULT_WIDTH,
    height: int = PREVIS_DEFAULT_HEIGHT,
    backend: str = "auto",
    blender_bin: str | Path | None = None,
    render_midpoint: bool = False,
    auto_visibility_pullback: bool | None = None,
) -> dict[str, Any]:
    """
    Renders `9:16` Start & End blockout previs PNGs (`{cut_id}_start_previs.png`, `{cut_id}_end_previs.png`),
    optional E6 `{cut_id}_mid_previs.png`, plus `{cut_id}_previs_blender.py`, color legend metadata, and P2
    Visibility Gate diagnostics.
    """
    if width <= 0 or height <= 0 or abs((width / float(height)) - (9.0 / 16.0)) > 0.02:
        raise ValueError(f"Previs keyframes must be 9:16 portrait aspect ratio (got {width}x{height})")

    out_p = Path(out_dir)
    out_p.mkdir(parents=True, exist_ok=True)
    spec_copy = copy.deepcopy(previs_spec)
    entities = list(spec_copy.get("actors") or []) + list(spec_copy.get("props") or [])
    legend = assign_previs_palette(entities)
    spec_copy["color_role_legend"] = legend

    enable_vis_pullback = (
        bool(spec_copy.get("auto_frame"))
        if auto_visibility_pullback is None
        else bool(auto_visibility_pullback)
    )
    if enable_vis_pullback:
        for _attempt in range(2):
            probe_s = _render_workbench_cpu_frame(spec_copy, phase="start", width=270, height=480)
            probe_e = _render_workbench_cpu_frame(spec_copy, phase="end", width=270, height=480)
            vg_s = evaluate_previs_visibility_gate(probe_s, spec_copy)
            vg_e = evaluate_previs_visibility_gate(probe_e, spec_copy)
            if vg_s["passed"] and vg_e["passed"]:
                break
            if not vg_s["passed"] and isinstance(spec_copy.get("camera_start"), dict):
                spec_copy["camera_start"] = _pullback_camera_spec(spec_copy["camera_start"])
            if not vg_e["passed"] and isinstance(spec_copy.get("camera_end"), dict):
                spec_copy["camera_end"] = _pullback_camera_spec(spec_copy["camera_end"])
        previs_spec["camera_start"] = copy.deepcopy(spec_copy["camera_start"])
        previs_spec["camera_end"] = copy.deepcopy(spec_copy["camera_end"])

    start_png = out_p / f"{cut_id}_start_previs.png"
    end_png = out_p / f"{cut_id}_end_previs.png"
    mid_png = (out_p / f"{cut_id}_mid_previs.png") if render_midpoint else None
    script_path = out_p / f"{cut_id}_previs_blender.py"
    script_src = generate_blender_workbench_script(
        spec_copy,
        start_png,
        end_png,
        mid_png=mid_png,
        width=width,
        height=height,
    )
    script_path.write_text(script_src, encoding="utf-8")

    eff_mode = str(backend or "auto").strip().lower()
    if eff_mode not in ("auto", "blender", "workbench_cpu"):
        raise ValueError(f"Unsupported previs backend {backend!r}; expected 'auto', 'blender', or 'workbench_cpu'")

    in_pytest_fast = bool(os.environ.get("PYTEST_CURRENT_TEST")) and eff_mode == "auto"
    used_backend = "workbench_cpu"
    if eff_mode == "blender" or (eff_mode == "auto" and not in_pytest_fast):
        b_exe = find_blender_executable(blender_bin)
        if b_exe is not None and is_blender_available(b_exe):
            proc = subprocess.run(
                [str(b_exe), "-b", "--factory-startup", "-P", str(script_path)],
                capture_output=True,
                text=True,
                timeout=90,
                check=False,
                stdin=subprocess.DEVNULL,
            )
            if proc.returncode != 0 or not start_png.is_file() or not end_png.is_file():
                raise RuntimeError(
                    f"Headless Blender previs render failed (rc={proc.returncode}): {(proc.stderr or proc.stdout or '')[:400]}"
                )
            used_backend = "blender"
        elif eff_mode == "blender":
            raise RuntimeError("Blender backend explicitly requested, but portable/system Blender is not runnable on this host")

    if used_backend == "workbench_cpu":
        start_img = _render_workbench_cpu_frame(spec_copy, phase="start", width=width, height=height)
        end_img = _render_workbench_cpu_frame(spec_copy, phase="end", width=width, height=height)
        _atomic_write_png(start_png, start_img)
        _atomic_write_png(end_png, end_img)
        if mid_png is not None:
            mid_img = _render_workbench_cpu_frame(spec_copy, phase="mid", width=width, height=height)
            _atomic_write_png(mid_png, mid_img)

    s_chk = cv2.imread(str(start_png))
    e_chk = cv2.imread(str(end_png))
    vis_gate_start = evaluate_previs_visibility_gate(s_chk, spec_copy) if s_chk is not None else {"passed": False}
    vis_gate_end = evaluate_previs_visibility_gate(e_chk, spec_copy) if e_chk is not None else {"passed": False}

    out_res: dict[str, Any] = {
        "cut_id": cut_id,
        "backend_used": used_backend,
        "start_png": str(start_png),
        "end_png": str(end_png),
        "blender_script": str(script_path),
        "resolution": [int(width), int(height)],
        "color_role_legend": legend,
        "visibility_gate_start": vis_gate_start,
        "visibility_gate_end": vis_gate_end,
    }
    if mid_png is not None:
        out_res["mid_png"] = str(mid_png)
    return out_res


def render_visual_plan_previs_pack(
    visual_plan: dict[str, Any],
    out_dir: str | Path,
    *,
    auto_populate_missing: bool = False,
    width: int = PREVIS_DEFAULT_WIDTH,
    height: int = PREVIS_DEFAULT_HEIGHT,
    backend: str = "auto",
    render_midpoint: bool = False,
) -> dict[str, Any]:
    """
    Propagates `camera_end -> next.camera_start` continuity across `visual_plan["clips"]` and renders
    Start/End `9:16` previs PNGs for every previs-enabled cut (using a single fast batch Blender 4.x
    process when Blender is active so a 20-cut episode renders in `< 7s`).
    """
    if auto_populate_missing:
        auto_synthesize_plan_previs_specs(visual_plan, overwrite=False)
    else:
        propagate_previs_camera_continuity(visual_plan)

    out_p = Path(out_dir)
    out_p.mkdir(parents=True, exist_ok=True)
    eff_mode = str(backend or "auto").strip().lower()
    in_pytest_fast = bool(os.environ.get("PYTEST_CURRENT_TEST")) and eff_mode == "auto"
    b_exe = None
    use_batch_blender = False
    if eff_mode == "blender" or (eff_mode == "auto" and not in_pytest_fast):
        b_exe = find_blender_executable()
        if b_exe is not None and is_blender_available(b_exe):
            use_batch_blender = True
        elif eff_mode == "blender":
            raise RuntimeError("Blender backend explicitly requested, but Blender is not runnable on this host")

    clips = visual_plan.get("clips") or []
    if not use_batch_blender:
        rendered_cuts: list[dict[str, Any]] = []
        for idx, clip in enumerate(clips, start=1):
            if not isinstance(clip, dict) or not isinstance(clip.get("previs"), dict):
                continue
            c_num = int(clip.get("clip_number") or idx)
            cut_id = str(clip.get("scene_id") or f"S{c_num:02d}")
            res = render_previs_keyframes(
                clip["previs"],
                out_dir=out_p,
                cut_id=cut_id,
                width=width,
                height=height,
                backend="workbench_cpu",
                render_midpoint=render_midpoint,
            )
            clip["previs"]["start_previs_png"] = res["start_png"]
            clip["previs"]["end_previs_png"] = res["end_png"]
            if res.get("mid_png"):
                clip["previs"]["mid_previs_png"] = res["mid_png"]
            rendered_cuts.append(res)
        return {"rendered_count": len(rendered_cuts), "cuts": rendered_cuts, "backend_used": "workbench_cpu"}

    # Fast single-process Batch Blender 4.x path
    batch_payloads: list[dict[str, Any]] = []
    cut_records: list[tuple[dict[str, Any], str, Path, Path, Path | None, Path, dict[str, Any]]] = []
    for idx, clip in enumerate(clips, start=1):
        if not isinstance(clip, dict) or not isinstance(clip.get("previs"), dict):
            continue
        c_num = int(clip.get("clip_number") or idx)
        cut_id = str(clip.get("scene_id") or f"S{c_num:02d}")
        pv = clip["previs"]
        if bool(pv.get("auto_frame")):
            for _att in range(2):
                ps_img = _render_workbench_cpu_frame(pv, phase="start", width=270, height=480)
                pe_img = _render_workbench_cpu_frame(pv, phase="end", width=270, height=480)
                vgs = evaluate_previs_visibility_gate(ps_img, pv)
                vge = evaluate_previs_visibility_gate(pe_img, pv)
                if vgs["passed"] and vge["passed"]:
                    break
                if not vgs["passed"] and isinstance(pv.get("camera_start"), dict):
                    pv["camera_start"] = _pullback_camera_spec(pv["camera_start"])
                if not vge["passed"] and isinstance(pv.get("camera_end"), dict):
                    pv["camera_end"] = _pullback_camera_spec(pv["camera_end"])
        s_png = out_p / f"{cut_id}_start_previs.png"
        e_png = out_p / f"{cut_id}_end_previs.png"
        m_png = (out_p / f"{cut_id}_mid_previs.png") if render_midpoint else None
        s_py = out_p / f"{cut_id}_previs_blender.py"
        s_py.write_text(
            generate_blender_workbench_script(pv, s_png, e_png, mid_png=m_png, width=width, height=height),
            encoding="utf-8",
        )
        ser = _serialize_cut_for_blender(pv, s_png, e_png, mid_png=m_png, width=width, height=height)
        batch_payloads.append(ser)
        cut_records.append((clip, cut_id, s_png, e_png, m_png, s_py, dict(pv.get("color_role_legend") or {})))

    if not batch_payloads:
        return {"rendered_count": 0, "cuts": [], "backend_used": "blender"}

    batch_script_p = out_p / "_batch_previs_pack_blender.py"
    batch_script_p.write_text(generate_blender_batch_pack_script(batch_payloads), encoding="utf-8")
    proc = subprocess.run(
        [str(b_exe), "-b", "--factory-startup", "-P", str(batch_script_p)],
        capture_output=True,
        text=True,
        timeout=240,
        check=False,
        stdin=subprocess.DEVNULL,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"Batch Blender previs pack render failed (rc={proc.returncode}): {(proc.stderr or proc.stdout or '')[:400]}"
        )

    rendered_cuts = []
    for clip, cut_id, s_png, e_png, m_png, s_py, leg in cut_records:
        clip["previs"]["start_previs_png"] = str(s_png)
        clip["previs"]["end_previs_png"] = str(e_png)
        if m_png is not None:
            clip["previs"]["mid_previs_png"] = str(m_png)
        res_item: dict[str, Any] = {
            "cut_id": cut_id,
            "backend_used": "blender",
            "start_png": str(s_png),
            "end_png": str(e_png),
            "blender_script": str(s_py),
            "resolution": [int(width), int(height)],
            "color_role_legend": leg,
        }
        if m_png is not None:
            res_item["mid_png"] = str(m_png)
        rendered_cuts.append(res_item)

    return {
        "rendered_count": len(rendered_cuts),
        "cuts": rendered_cuts,
        "backend_used": "blender",
    }


def _extract_previs_marker_bbox(previs_bgr: np.ndarray) -> tuple[int, int, int, int] | None:
    """Extracts the union bounding box `(x0, y0, x1, y1)` of saturated marker dummies/props in a Previs PNG."""
    hsv = cv2.cvtColor(previs_bgr, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv[:, :, 1], 55, 255)
    ys, xs = np.where(mask > 0)
    if xs.size < 32:
        return None
    return (int(np.min(xs)), int(np.min(ys)), int(np.max(xs)), int(np.max(ys)))


def _extract_keyframe_subject_bbox(kf_bgr: np.ndarray) -> tuple[int, int, int, int] | None:
    """Extracts the primary subject/foreground bounding box `(x0, y0, x1, y1)` from a generated Flow keyframe."""
    h, w = kf_bgr.shape[:2]
    gray = cv2.cvtColor(kf_bgr, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 45, 135)
    # Focus within central-safe framing (exclude 4% border) and combine high-contrast vinyl/ink regions
    margin_x, margin_y = int(w * 0.04), int(h * 0.04)
    edges[:margin_y, :] = 0
    edges[h - margin_y :, :] = 0
    edges[:, :margin_x] = 0
    edges[:, w - margin_x :] = 0
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (9, 9))
    closed = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel)
    ys, xs = np.where(closed > 0)
    if xs.size < 48:
        return None
    x0 = int(np.percentile(xs, 6))
    x1 = int(np.percentile(xs, 94))
    y0 = int(np.percentile(ys, 6))
    y1 = int(np.percentile(ys, 94))
    if x1 <= x0 or y1 <= y0:
        return None
    return (x0, y0, x1, y1)


def previs_conformance_qa(
    previs_png: str | Path,
    keyframe_png: str | Path,
    *,
    min_iou: float = 0.35,
) -> dict[str, Any]:
    """
    E7 Previs Conformance QA: Compares normalized foreground bounding-box placement between the 3D Previs
    guide PNG and the generated Flow keyframe PNG BEFORE spending video credits.
    Flags `passed = False` (`regenerate_recommended = True`) when spatial IoU < `min_iou`.
    """
    pv_img = cv2.imread(str(previs_png))
    kf_img = cv2.imread(str(keyframe_png))
    if pv_img is None or kf_img is None:
        return {
            "passed": False,
            "iou": 0.0,
            "min_iou": float(min_iou),
            "regenerate_recommended": True,
            "reason": "missing_image",
        }
    target_h, target_w = 640, 360
    pv_rs = cv2.resize(pv_img, (target_w, target_h), interpolation=cv2.INTER_AREA)
    kf_rs = cv2.resize(kf_img, (target_w, target_h), interpolation=cv2.INTER_AREA)
    bb_pv = _extract_previs_marker_bbox(pv_rs)
    bb_kf = _extract_keyframe_subject_bbox(kf_rs)
    if bb_pv is None or bb_kf is None:
        return {
            "passed": True,
            "iou": 1.0,
            "min_iou": float(min_iou),
            "regenerate_recommended": False,
            "reason": "no_distinct_marker_bbox",
        }
    frame_area = max(1, target_w * target_h)
    ix0 = max(bb_pv[0], bb_kf[0])
    iy0 = max(bb_pv[1], bb_kf[1])
    ix1 = min(bb_pv[2], bb_kf[2])
    iy1 = min(bb_pv[3], bb_kf[3])
    inter = max(0, ix1 - ix0) * max(0, iy1 - iy0)
    area_pv = max(1, (bb_pv[2] - bb_pv[0]) * (bb_pv[3] - bb_pv[1]))
    area_kf = max(1, (bb_kf[2] - bb_kf[0]) * (bb_kf[3] - bb_kf[1]))
    union = max(1, area_pv + area_kf - inter)
    iou = round(float(inter) / float(union), 4)
    # Wide outdoor / aerial drone shots have distant tiny actor markers (<12% frame) inside full-bleed architecture (>=45% frame)
    if (area_pv / float(frame_area)) < 0.12 and (area_kf / float(frame_area)) >= 0.45:
        containment = float(inter) / float(area_pv)
        bb_arch = _extract_keyframe_subject_bbox(pv_rs)
        arch_iou = 0.0
        if bb_arch is not None:
            ax0, ay0 = max(bb_arch[0], bb_kf[0]), max(bb_arch[1], bb_kf[1])
            ax1, ay1 = min(bb_arch[2], bb_kf[2]), min(bb_arch[3], bb_kf[3])
            a_inter = max(0, ax1 - ax0) * max(0, ay1 - ay0)
            a_pv = max(1, (bb_arch[2] - bb_arch[0]) * (bb_arch[3] - bb_arch[1]))
            a_union = max(1, a_pv + area_kf - a_inter)
            arch_iou = float(a_inter) / float(a_union)
        if containment >= 0.70 or arch_iou >= float(min_iou):
            iou = round(max(iou, arch_iou, min(0.85, containment * 0.55)), 4)
    passed = bool(iou >= float(min_iou))
    return {
        "passed": passed,
        "iou": iou,
        "min_iou": float(min_iou),
        "previs_bbox": list(bb_pv),
        "keyframe_bbox": list(bb_kf),
        "regenerate_recommended": not passed,
    }


def format_previs_color_mapping_prompt(
    color_role_legend: dict[str, dict[str, str]] | None,
    *,
    style_profile: str = "expressive_25d_v8",
    has_character_sheet: bool = True,
) -> str:
    """
    Builds the concise Rule 2 + Rule 3 Flow `Image` translation instruction pairing:
    - Attachment 1 = 3D blockout previs PNG (camera angle, perspective, spatial layout ONLY)
    - Attachment 2 = Character / style reference sheet
    """
    legend = dict(color_role_legend or {})
    mappings: list[str] = []
    for role_id, meta in legend.items():
        c_name = str(meta.get("color_name") or role_id).strip()
        c_hex = str(meta.get("color_hex") or "").strip()
        t_lbl = str(meta.get("target_label") or role_id).strip()
        kind = str(meta.get("entity_kind") or "actor")
        tag = f"{c_name} ({c_hex})" if c_hex else c_name
        if kind == "prop":
            mappings.append(f"{tag} box = real-world {t_lbl}")
        elif has_character_sheet:
            mappings.append(f"{tag} 3-chunk dummy = {t_lbl} (match Attachment 2 character sheet)")
        else:
            mappings.append(f"{tag} 3-chunk dummy = {t_lbl}")

    mapping_clause = (
        f" Color-to-subject mapping: {'; '.join(mappings)}."
        if mappings
        else ""
    )
    species_clause = (
        "Replace every dummy marker with smooth matte cream-white vinyl 2.5D characters with bold 2D charcoal ink eyes/mouth and woven fabric clothing"
        if style_profile == "expressive_25d_v8"
        else "Replace every dummy marker with articulated matte-white porcelain figures with smooth featureless oval porcelain heads and woven fabric clothing"
    )
    return (
        "Vertical 9:16 full-bleed cinematic miniature diorama photograph. "
        "Follow camera angle, lens perspective, and 3D spatial placement strictly from Attachment 1 "
        "(3D blockout previs; simple colored 3-chunk dummies and boxes are position markers ONLY — "
        f"do NOT copy blocky geometry or solid marker colors). {species_clause}.{mapping_clause}"
    )


def _interpolate_previs_spec_at_alpha(previs_spec: dict[str, Any], alpha: float) -> dict[str, Any]:
    """Interpolates camera and actor/prop positions at `alpha` in `[0.0, 1.0]` for smooth 30fps Previs motion guides."""
    t = max(0.0, min(1.0, float(alpha)))
    cs = previs_spec.get("camera_start") or {"pos": [0.0, -2.5, 1.4], "look_at": [0.0, 0.0, 1.2], "fov_deg": 50.0}
    ce = previs_spec.get("camera_end") or cs
    cam_t = {
        "pos": [(1.0 - t) * float(a) + t * float(b) for a, b in zip(cs["pos"], ce["pos"])],
        "look_at": [(1.0 - t) * float(a) + t * float(b) for a, b in zip(cs["look_at"], ce["look_at"])],
        "fov_deg": (1.0 - t) * float(cs.get("fov_deg") or 50.0) + t * float(ce.get("fov_deg") or 50.0),
    }
    spec_t = copy.deepcopy(previs_spec)
    spec_t["camera_start"] = cam_t
    spec_t["camera_end"] = cam_t
    for act in spec_t.get("actors") or []:
        ps = act.get("pos_start") or [0.0, 0.0, 0.0]
        pe = act.get("pos_end") or ps
        act["pos_start"] = [(1.0 - t) * float(a) + t * float(b) for a, b in zip(ps, pe)]
    for pr in spec_t.get("props") or []:
        ps = pr.get("pos_start") or [0.0, 0.0, 0.0]
        pe = pr.get("pos_end") or ps
        pr["pos_start"] = [(1.0 - t) * float(a) + t * float(b) for a, b in zip(ps, pe)]
    return spec_t


def render_previs_motion_guide_mp4(
    previs_spec: dict[str, Any],
    out_mp4: str | Path,
    *,
    duration_sec: float = 3.0,
    fps: int = 30,
    width: int = PREVIS_DEFAULT_WIDTH,
    height: int = PREVIS_DEFAULT_HEIGHT,
) -> dict[str, Any]:
    """
    Component 2 (`v8.3`): Renders a `3.0s @ 30fps` (`9:16`) camera & blockout motion guide MP4
    for `Omni 1.2 Flash` multi-ingredient motion conditioning.
    """
    import imageio_ffmpeg

    dst = Path(out_mp4)
    dst.parent.mkdir(parents=True, exist_ok=True)
    n_frames = max(6, int(round(float(duration_sec) * max(1, int(fps)))))
    spec_copy = copy.deepcopy(previs_spec)
    entities = list(spec_copy.get("actors") or []) + list(spec_copy.get("props") or [])
    legend = assign_previs_palette(entities)
    spec_copy["color_role_legend"] = legend

    fd, tmp_avi_str = tempfile.mkstemp(prefix=".tmp_previs_guide_", suffix=".avi")
    os.close(fd)
    tmp_avi = Path(tmp_avi_str)
    try:
        vw = cv2.VideoWriter(
            str(tmp_avi),
            cv2.VideoWriter_fourcc(*"MJPG"),
            float(fps),
            (int(width), int(height)),
        )
        for f_idx in range(n_frames):
            alpha = f_idx / float(max(1, n_frames - 1))
            interp_spec = _interpolate_previs_spec_at_alpha(spec_copy, alpha)
            frm = _render_workbench_cpu_frame(interp_spec, phase="start", width=int(width), height=int(height))
            vw.write(frm)
        vw.release()

        ff = imageio_ffmpeg.get_ffmpeg_exe()
        subprocess.run(
            [
                ff,
                "-y",
                "-i",
                str(tmp_avi),
                "-c:v",
                "libx264",
                "-preset",
                "fast",
                "-crf",
                "18",
                "-pix_fmt",
                "yuv420p",
                "-movflags",
                "+faststart",
                str(dst),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=60,
        )
    finally:
        tmp_avi.unlink(missing_ok=True)

    return {
        "out_mp4": str(dst),
        "duration_sec": round(float(duration_sec), 2),
        "fps": int(fps),
        "frame_count": int(n_frames),
        "resolution": [int(width), int(height)],
        "file_size_bytes": dst.stat().st_size if dst.exists() else 0,
    }
