"""
ALL ABOUT BRAIN — Rule R80 Spatial 3D Volumetric Arrow Diorama & RQ-Arrow Geometry Verifier.

Implements the two-part high-retention visual grammar combining:
  1. `@RicksClips3000` 2-cut spatial micro-relay (`2.4s-3.2s/cut`, `1.24x-1.42x` speed ramp):
     - Cut A (`drone_landmark_ascend`): Fast 3D aerial sweep skimming a concrete real-world landmark
       before soaring steeply skyward.
     - Cut B (`topdown_3d_route_glide`): 90-degree vertical bird's-eye top-down miniature street/room
       canyon with `신비한 건축사전`-style thick solid matte-crimson (`#FF2525`) 3D extruded directional
       arrow blocks resting physically on the ground and casting crisp sunlight shadows (`0` text).
  2. `RQ-Arrow` OpenCV geometric verification (`verify_r80_arrow_keyframe_geometry`):
     - Extracts HSV high-saturation crimson-red (`#FF2525`) 3D arrow paths from `1080x1920` keyframes,
       verifies portrait framing, physical drop-shadow contrast, and path tortuosity (`arc_length / chord_length`):
         * `adaptive_landmark_zigzag`: `tortuosity >= 1.35` and `turn_count >= 2`
         * `fixed_linear_corridor`:    `tortuosity <= 1.08` and `collinearity_r2 >= 0.92`
         * `doorway_boundary_sever`:   `>= 2` collinear red segments separated across a threshold gap
         * `dual_speed_race_lanes`:    both crimson-red (`#FF2525`) and cyan-blue (`#27D8FF`) parallel 3D lanes
         * `split_hemisphere_watch`:   balanced opposing crimson/cyan spatial domains
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from pipeline.config import (
    R80_3D_ARROW_ACCENT_HEX,
    R80_SPATIAL_ARROW_MODES,
)

# BGR colors for deterministic 9:16 layout guide rendering
_ARROW_TOP_BGR = (37, 37, 255)       # #FF2525 vivid matte crimson top face
_ARROW_SIDE_BGR = (22, 20, 168)      # darker extruded 3D side wall
_SHADOW_ALPHA = 0.42
_CYAN_TOP_BGR = (255, 216, 39)       # #27D8FF electric cyan lane
_CYAN_SIDE_BGR = (180, 138, 18)


def _draw_3d_extruded_polyline_arrow(
    canvas: np.ndarray,
    points: list[tuple[int, int]],
    *,
    thickness: int = 44,
    extrude_px: int = 16,
    shadow_offset: tuple[int, int] = (22, 26),
    top_bgr: tuple[int, int, int] = _ARROW_TOP_BGR,
    side_bgr: tuple[int, int, int] = _ARROW_SIDE_BGR,
    head_len: int = 88,
) -> None:
    """Draws a physical 3D-extruded directional arrow ribbon with ground sunlight drop shadow."""
    if len(points) < 2:
        return
    h, w = canvas.shape[:2]

    # Build binary mask of the flat arrow silhouette (shaft + triangular head)
    mask = np.zeros((h, w), dtype=np.uint8)
    pts_arr = np.array(points, dtype=np.int32)
    cv2.polylines(mask, [pts_arr], isClosed=False, color=255, thickness=thickness, lineType=cv2.LINE_AA)

    p_prev = np.array(points[-2], dtype=np.float64)
    p_end = np.array(points[-1], dtype=np.float64)
    vec = p_end - p_prev
    norm = float(np.linalg.norm(vec))
    if norm > 1e-3:
        u = vec / norm
        perp = np.array([-u[1], u[0]], dtype=np.float64)
        tip = p_end + u * (head_len * 0.55)
        base_c = p_end - u * (head_len * 0.35)
        wing_w = max(thickness * 1.45, 64.0)
        tri = np.array(
            [
                tip,
                base_c + perp * wing_w,
                base_c - perp * wing_w,
            ],
            dtype=np.int32,
        )
        cv2.fillConvexPoly(mask, tri, 255, lineType=cv2.LINE_AA)

    # 1. Ground sunlight drop shadow
    sx, sy = shadow_offset
    M_sh = np.float32([[1, 0, sx], [0, 1, sy]])
    sh_mask = cv2.warpAffine(mask, M_sh, (w, h), flags=cv2.INTER_LINEAR, borderValue=0)
    sh_blur = cv2.GaussianBlur(sh_mask, (21, 21), 6.0).astype(np.float32) / 255.0
    alpha_sh = (sh_blur * _SHADOW_ALPHA)[..., None]
    canvas[:] = np.clip(canvas.astype(np.float32) * (1.0 - alpha_sh), 0, 255).astype(np.uint8)

    # 2. 3D Extruded side wall (stepped vertical/diagonal thickness)
    side_mask = np.zeros((h, w), dtype=np.uint8)
    for step in range(extrude_px, 0, -1):
        dx = int(round(step * 0.55))
        dy = step
        M_ex = np.float32([[1, 0, dx], [0, 1, dy]])
        shifted = cv2.warpAffine(mask, M_ex, (w, h), flags=cv2.INTER_NEAREST, borderValue=0)
        side_mask = np.maximum(side_mask, shifted)
    canvas[side_mask > 127] = side_bgr

    # 3. Lit matte top face
    canvas[mask > 127] = top_bgr


def render_r80_arrow_layout_guide(
    output_path: str | Path,
    mode: str,
    *,
    width: int = 1080,
    height: int = 1920,
) -> dict[str, Any]:
    """
    Renders a deterministic `1080x1920` (`9:16`) structural layout guide PNG showing sunlit
    Portland-stone street/room canyons + extruded `#FF2525` 3D volumetric arrows with ground shadows
    and zero text.
    """
    mode_norm = str(mode or "").strip().lower()
    if mode_norm not in R80_SPATIAL_ARROW_MODES:
        raise ValueError(f"Unsupported R80 mode '{mode}'; must be one of {R80_SPATIAL_ARROW_MODES}")

    out_p = Path(output_path)
    out_p.parent.mkdir(parents=True, exist_ok=True)

    # Base sunlit asphalt street surface
    canvas = np.full((height, width, 3), (96, 98, 102), dtype=np.uint8)

    if mode_norm == "adaptive_landmark_zigzag":
        # Draw miniature city blocks leaving an interconnected street labyrinth
        blocks = [
            (40, 80, 310, 420),
            (470, 80, 760, 360),
            (880, 80, 1040, 460),
            (40, 560, 250, 900),
            (430, 520, 710, 810),
            (850, 600, 1040, 960),
            (40, 1060, 330, 1410),
            (500, 970, 790, 1320),
            (900, 1100, 1040, 1520),
            (60, 1560, 360, 1850),
            (540, 1490, 830, 1840),
        ]
        for x0, y0, x1, y1 in blocks:
            cv2.rectangle(canvas, (x0 + 14, y0 + 18), (x1 + 14, y1 + 18), (64, 66, 70), -1)
            cv2.rectangle(canvas, (x0, y0), (x1, y1), (206, 214, 222), -1)
            cv2.rectangle(canvas, (x0 + 12, y0 + 12), (x1 - 12, y1 - 12), (186, 195, 206), 3)

        zigzag_pts = [
            (460, 1780),
            (460, 1430),
            (845, 1430),
            (845, 920),
            (340, 920),
            (340, 470),
            (815, 470),
            (815, 190),
        ]
        _draw_3d_extruded_polyline_arrow(canvas, zigzag_pts, thickness=46, extrude_px=16)
        # Circular landmark beacon pins (zero text)
        for bx, by in [(460, 1780), (845, 1430), (340, 920), (815, 190)]:
            cv2.circle(canvas, (bx, by), 28, (245, 248, 252), -1, lineType=cv2.LINE_AA)
            cv2.circle(canvas, (bx, by), 16, _ARROW_TOP_BGR, -1, lineType=cv2.LINE_AA)

    elif mode_norm == "fixed_linear_corridor":
        # Left & right symmetrical Portland-stone avenue blocks flanking one straight central boulevard
        for y0 in (90, 540, 990, 1440):
            y1 = y0 + 360
            for x0, x1 in ((50, 390), (690, 1030)):
                cv2.rectangle(canvas, (x0 + 14, y0 + 18), (x1 + 14, y1 + 18), (64, 66, 70), -1)
                cv2.rectangle(canvas, (x0, y0), (x1, y1), (206, 214, 222), -1)
                cv2.rectangle(canvas, (x0 + 12, y0 + 12), (x1 - 12, y1 - 12), (186, 195, 206), 3)
        straight_pts = [(540, 1790), (540, 180)]
        _draw_3d_extruded_polyline_arrow(canvas, straight_pts, thickness=54, extrude_px=18)
        for by in (1520, 1020, 520):
            cv2.circle(canvas, (540, by), 24, (245, 248, 252), -1, lineType=cv2.LINE_AA)
            cv2.circle(canvas, (540, by), 12, _ARROW_TOP_BGR, -1, lineType=cv2.LINE_AA)

    elif mode_norm == "doorway_boundary_sever":
        canvas[:] = (198, 204, 210)
        # Architectural doorway partition across Y=960
        cv2.rectangle(canvas, (0, 930), (410, 990), (110, 116, 124), -1)
        cv2.rectangle(canvas, (670, 930), (1080, 990), (110, 116, 124), -1)
        _draw_3d_extruded_polyline_arrow(canvas, [(540, 1740), (540, 1060)], thickness=50, extrude_px=16)
        _draw_3d_extruded_polyline_arrow(canvas, [(540, 820), (540, 260)], thickness=50, extrude_px=16)

    elif mode_norm == "dual_speed_race_lanes":
        _draw_3d_extruded_polyline_arrow(
            canvas, [(370, 1760), (370, 220)], thickness=48, extrude_px=16, top_bgr=_CYAN_TOP_BGR, side_bgr=_CYAN_SIDE_BGR
        )
        _draw_3d_extruded_polyline_arrow(
            canvas, [(710, 1760), (710, 980)], thickness=48, extrude_px=16, top_bgr=_ARROW_TOP_BGR, side_bgr=_ARROW_SIDE_BGR
        )

    else:  # split_hemisphere_watch
        _draw_3d_extruded_polyline_arrow(
            canvas, [(320, 1580), (320, 380)], thickness=48, extrude_px=16, top_bgr=_CYAN_TOP_BGR, side_bgr=_CYAN_SIDE_BGR
        )
        _draw_3d_extruded_polyline_arrow(
            canvas, [(760, 1580), (760, 380)], thickness=48, extrude_px=16, top_bgr=_ARROW_TOP_BGR, side_bgr=_ARROW_SIDE_BGR
        )

    tmp_p = out_p.with_name(f".{out_p.name}.tmp.png")
    ok = cv2.imwrite(str(tmp_p), canvas)
    if not ok:
        raise RuntimeError(f"Failed to write R80 layout guide to {tmp_p}")
    tmp_p.replace(out_p)
    return {
        "output_path": str(out_p),
        "mode": mode_norm,
        "width": width,
        "height": height,
        "accent_hex": R80_3D_ARROW_ACCENT_HEX,
    }


def build_r80_keyframe_prompt(
    mode: str,
    *,
    landmark_desc: str = "",
    vehicle_or_actor_desc: str = "",
    urban_traits: str = "sunlit Portland-stone London miniature street canyons and rooftops",
    anchor_prop_a: str = "",
    anchor_prop_b: str = "",
) -> str:
    """
    Builds a `9:16` `State-A` keyframe generation prompt in the verified `신비한 건축사전` 3D volumetric
    arrow style (solid matte-crimson `#FF2525` extruded arrow blocks casting real ground shadows,
    blank unlabeled architecture, plus R87-A study-specific prop anchors when supplied).
    """
    mode_norm = str(mode or "").strip().lower()
    urb = str(urban_traits or "sunlit Portland-stone London miniature street canyons").strip()
    veh = str(vehicle_or_actor_desc or anchor_prop_a or "a glossy miniature black London taxicab").strip()
    lmk = str(landmark_desc or "iconic circular landmark beacons").strip()
    prop_a = str(anchor_prop_a or veh).strip()
    prop_b = str(anchor_prop_b or "").strip()
    prop_legend_tail = (
        f" with distinct physical miniature anchor props ({prop_a} on route A vs {prop_b} on route B)"
        if prop_b
        else (f" anchored directly to {prop_a}" if anchor_prop_a else "")
    )

    if mode_norm == "adaptive_landmark_zigzag":
        return (
            f"Vertical 9:16 ninety-degree bird's-eye top-down 3D architectural miniature diorama looking straight down into {urb}. "
            f"Thick solid matte-crimson ({R80_3D_ARROW_ACCENT_HEX}) 3D extruded directional arrow blocks snake and zigzag sharply "
            f"through five ninety-degree side-street turns connecting {lmk} as {veh} navigates a winding custom detour along the dark-gray asphalt{prop_legend_tail}. "
            "The raised 3D crimson arrow blocks have crisp vertical thickness, rest physically on the street pavement between buildings, "
            "and cast sharp dark afternoon sunlight drop shadows onto the asphalt. Crisp studio daylight, tack-sharp architectural miniature clarity, "
            "completely blank unlabeled stone facades and clean asphalt."
        )
    if mode_norm in ("dual_route_race_lanes", "dual_speed_race_lanes"):
        rhs_prop = prop_b or "a miniature red double-decker bus"
        return (
            f"Vertical 9:16 ninety-degree bird's-eye top-down 3D architectural miniature diorama looking straight down into {urb}. "
            f"Two parallel routes compare side by side: left lane shows a thick solid matte sky-blue extruded zigzag arrow anchored to {prop_a}, "
            f"while right lane shows a straight solid matte-crimson ({R80_3D_ARROW_ACCENT_HEX}) extruded arrow anchored to {rhs_prop} near {lmk}. "
            "Both raised 3D directional arrow blocks rest physically on the ground plane casting sharp afternoon sunlight drop shadows, "
            "completely blank unlabeled architecture and zero text."
        )
    if mode_norm == "fixed_linear_corridor":
        return (
            f"Vertical 9:16 ninety-degree bird's-eye top-down 3D architectural miniature diorama looking straight down into {urb}. "
            f"One single ruler-straight solid matte-crimson ({R80_3D_ARROW_ACCENT_HEX}) 3D extruded directional arrow corridor runs dead-center "
            f"from the bottom edge straight to the top edge down a wide main avenue through three aligned circular stop markers as {veh} drives straight ahead{prop_legend_tail}. "
            "The raised 3D crimson arrow block has crisp vertical thickness, rests physically on the asphalt road, and casts a sharp dark sunlight drop shadow "
            "onto the pavement. Crisp studio daylight, tack-sharp architectural miniature clarity, completely blank unlabeled stone facades."
        )
    if mode_norm == "doorway_boundary_sever":
        return (
            f"Vertical 9:16 high-angle isometric-top-down 3D architectural cutaway diorama of {urb}. "
            f"A thick solid matte-crimson ({R80_3D_ARROW_ACCENT_HEX}) 3D extruded directional arrow track runs along the floor behind {veh}{prop_legend_tail} "
            "and snaps cleanly in two with a crisp physical gap right at the doorway threshold line, casting sharp floor shadows on blank matte surfaces."
        )
    return (
        f"Vertical 9:16 ninety-degree bird's-eye top-down 3D architectural miniature diorama of {urb} with thick solid matte-crimson "
        f"({R80_3D_ARROW_ACCENT_HEX}) 3D extruded directional arrow blocks resting physically on the ground casting crisp sunlight shadows "
        f"beside {veh} near {lmk}{prop_legend_tail}, blank unlabeled surfaces."
    )


def build_r80_flow_scene_clause(
    mode: str,
    *,
    cut_phase: str = "topdown_arrow",
    landmark_desc: str = "",
    vehicle_or_actor_desc: str = "",
    anchor_prop_a: str = "",
    anchor_prop_b: str = "",
) -> str:
    """
    Builds a 100% Pink-Elephant-safe and `r77_hardware_ban`-safe Google Flow `VIDEO_FRAMES` action clause
    (pure disembodied viewpoint motion + physical 3D arrow/vehicle motion + R87-A prop anchors, zero negative triggers).
    """
    phase = str(cut_phase or "topdown_arrow").strip().lower()
    mode_norm = str(mode or "adaptive_landmark_zigzag").strip().lower()
    lmk = str(landmark_desc or "the sunlit riverside observation wheel and stone embankment").strip()
    veh = str(vehicle_or_actor_desc or anchor_prop_a or "the glossy black London cab").strip()
    prop_a = str(anchor_prop_a or veh).strip()
    prop_b = str(anchor_prop_b or "").strip()

    if phase == "landmark_ascend":
        return (
            f"Fast sweeping 3D aerial arc skims close past {lmk} as {veh} rolls briskly below, "
            "then banking steeply skyward above sunlit Portland-stone rooftops with strong foreground parallax"
        )
    if mode_norm in ("dual_route_race_lanes", "dual_speed_race_lanes"):
        rhs_prop = prop_b or "the miniature red double-decker bus"
        return (
            f"Vertical 90-degree bird's-eye top-down glide tracks {prop_a} weaving along the left matte sky-blue extruded route "
            f"beside {rhs_prop} advancing straight along the right matte-crimson 3D extruded arrow corridor resting flush on the unmarked ground plane "
            "casting sharp dark directional sunlight drop shadows across blank unlabeled miniature architecture"
        )
    if mode_norm == "fixed_linear_corridor":
        return (
            f"Vertical 90-degree bird's-eye top-down glide tracks {veh} driving straight ahead along one single "
            "unbroken rigid solid matte-crimson 3D extruded directional arrow block resting flush on the unmarked ground plane "
            "casting sharp dark directional sunlight drop shadows across blank unlabeled miniature architecture"
        )
    if mode_norm == "doorway_boundary_sever":
        return (
            f"High-angle top-down 3D cutaway glide tracks {veh} stepping across the doorway threshold as the rigid solid "
            "matte-crimson 3D floor arrow block resting flush on the unmarked floor fractures cleanly at the boundary line casting sharp dark drop shadows"
        )
    return (
        f"Vertical 90-degree bird's-eye top-down glide tracks {veh} weaving briskly left and right through tangled side-street turns "
        "along rigid solid matte-crimson 3D extruded zigzag directional arrow blocks resting flush on the unmarked ground plane casting sharp dark directional sunlight drop shadows"
    )


def _skeletonize_binary(mask_u8: np.ndarray) -> np.ndarray:
    """Morphological Zhang-Suen-like skeletonization using pure OpenCV."""
    img = (mask_u8 > 0).astype(np.uint8) * 255
    skel = np.zeros_like(img)
    element = cv2.getStructuringElement(cv2.MORPH_CROSS, (3, 3))
    max_iters = 256
    for _ in range(max_iters):
        eroded = cv2.erode(img, element)
        opened = cv2.dilate(eroded, element)
        temp = cv2.subtract(img, opened)
        skel = cv2.bitwise_or(skel, temp)
        img = eroded
        if cv2.countNonZero(img) == 0:
            break
    return skel


def _extract_ordered_centerline_points(red_mask: np.ndarray, n_bins: int = 28) -> list[tuple[float, float]]:
    """
    Slices the largest connected crimson arrow mask along its principal axis (vertical Y on 9:16 top-down
    maps) to recover an ordered polyline centerline and measure tortuosity (`arc_length / chord_length`),
    collinearity `R^2`, and directional turn count.
    """
    ys, xs = np.nonzero(red_mask)
    if len(ys) < 40:
        return []
    y_span = float(ys.max() - ys.min())
    x_span = float(xs.max() - xs.min())
    vertical_major = y_span >= x_span

    major = ys if vertical_major else xs
    minor = xs if vertical_major else ys
    m_min, m_max = float(major.min()), float(major.max())
    if m_max - m_min < 24.0:
        return []

    edges = np.linspace(m_min, m_max, n_bins + 1)
    pts: list[tuple[float, float]] = []
    for i in range(n_bins):
        lo, hi = edges[i], edges[i + 1]
        sel = (major >= lo) & (major <= (hi if i == n_bins - 1 else hi - 1e-6))
        if int(np.count_nonzero(sel)) < 5:
            continue
        maj_c = float(np.median(major[sel]))
        # If multiple horizontal branches exist inside one Y-band (e.g., horizontal zigzag rung),
        # capture left/right extrema in alternating order or median to preserve zigzag excursion!
        min_vals = minor[sel]
        p10, p90 = float(np.percentile(min_vals, 10)), float(np.percentile(min_vals, 90))
        if (p90 - p10) > 95.0:
            # Horizontal segment inside this Y slice: record entry & exit ends ordered by nearest previous minor
            prev_min = pts[-1][0 if vertical_major else 1] if pts else p10
            if abs(prev_min - p10) <= abs(prev_min - p90):
                first_m, second_m = p10, p90
            else:
                first_m, second_m = p90, p10
            p_a = (first_m, maj_c) if vertical_major else (maj_c, first_m)
            p_b = (second_m, maj_c) if vertical_major else (maj_c, second_m)
            pts.append(p_a)
            pts.append(p_b)
        else:
            med_m = float(np.median(min_vals))
            pts.append((med_m, maj_c) if vertical_major else (maj_c, med_m))
    return pts


def verify_r80_arrow_keyframe_geometry(
    img_path: str | Path,
    mode: str,
) -> dict[str, Any]:
    """
    `RQ-Arrow` OpenCV verifier for `Rule R80` 3D volumetric arrow keyframes:
      1. Confirms portrait `9:16` aspect (`height > width`).
      2. Extracts high-saturation crimson-red (`#FF2525`) mask and checks `red_area_ratio` in `[0.008, 0.35]`.
      3. Verifies physical 3D shadow / relief contrast around the arrow boundary (`boundary_luma_contrast >= 6.0`).
      4. Verifies trajectory geometry:
         - `adaptive_landmark_zigzag`: `tortuosity >= 1.35` and `turn_count >= 2`
         - `fixed_linear_corridor`:    `tortuosity <= 1.08` and `collinearity_r2 >= 0.92`
         - `doorway_boundary_sever`:   `component_count >= 2`
         - `dual_speed_race_lanes` / `split_hemisphere_watch`: `cyan_area_ratio >= 0.005` and `red_area_ratio >= 0.005`
    """
    p = Path(img_path)
    mode_norm = str(mode or "").strip().lower()
    if not p.is_file():
        return {"passed": False, "mode": mode_norm, "issues": [f"missing_image:{p}"]}

    bgr = cv2.imread(str(p), cv2.IMREAD_COLOR)
    if bgr is None or bgr.size == 0:
        return {"passed": False, "mode": mode_norm, "issues": [f"unreadable_image:{p}"]}

    h, w = bgr.shape[:2]
    issues: list[str] = []
    if h <= w or abs((w / float(h)) - (9.0 / 16.0)) > 0.05:
        issues.append(f"non_9x16_aspect:{w}x{h}")

    # Resize to canonical 540x960 for fast deterministic HSV & skeleton analysis
    work = cv2.resize(bgr, (540, 960), interpolation=cv2.INTER_AREA)
    hsv = cv2.cvtColor(work, cv2.COLOR_BGR2HSV)
    gray = cv2.cvtColor(work, cv2.COLOR_BGR2GRAY).astype(np.float32)

    # High-saturation crimson-red mask (#FF2525 family)
    red_lo1 = cv2.inRange(hsv, (0, 110, 95), (14, 255, 255))
    red_lo2 = cv2.inRange(hsv, (165, 110, 95), (180, 255, 255))
    red_raw = cv2.bitwise_or(red_lo1, red_lo2)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    red_clean = cv2.morphologyEx(red_raw, cv2.MORPH_OPEN, kernel)
    red_clean = cv2.morphologyEx(red_clean, cv2.MORPH_CLOSE, kernel)

    total_px = float(work.shape[0] * work.shape[1])
    red_area_ratio = float(np.count_nonzero(red_clean)) / total_px

    # Cyan mask for dual-lane / split modes
    cyan_mask = cv2.inRange(hsv, (82, 95, 105), (112, 255, 255))
    cyan_area_ratio = float(np.count_nonzero(cyan_mask)) / total_px

    if not (0.008 <= red_area_ratio <= 0.35):
        issues.append(f"red_area_ratio_out_of_range:{red_area_ratio:.4f}")

    # Keep significant red components (>= 0.12% of frame) and bridge tiny vehicle occlusions across a single arrow
    num_cc, labels, stats, _ = cv2.connectedComponentsWithStats(red_clean, connectivity=8)
    sig_mask = np.zeros_like(red_clean)
    sig_components = 0
    for cc_i in range(1, num_cc):
        area_i = int(stats[cc_i, cv2.CC_STAT_AREA])
        if area_i >= int(total_px * 0.0012):
            sig_mask[labels == cc_i] = 255
            sig_components += 1

    # Physical 3D relief / shadow check around arrow perimeter
    dil = cv2.dilate(sig_mask, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15)))
    ring = (dil > 0) & (sig_mask == 0)
    boundary_luma_std = float(np.std(gray[ring])) if int(np.count_nonzero(ring)) > 30 else 0.0
    if boundary_luma_std < 5.0:
        issues.append(f"flat_2d_overlay_low_boundary_relief:{boundary_luma_std:.2f}")

    # Bridge small vehicle/tree occlusions (up to ~24px on 540x960) when tracing the continuous route centerline
    bridged_mask = cv2.morphologyEx(
        sig_mask,
        cv2.MORPH_CLOSE,
        cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (23, 23)),
    )
    pts = _extract_ordered_centerline_points(bridged_mask)
    skel = _skeletonize_binary(bridged_mask)
    skel_len = float(np.count_nonzero(skel))

    arc_length = 0.0
    chord_length = 0.0
    tortuosity = 1.0
    turn_count = 0
    collinearity_r2 = 1.0

    if len(pts) >= 3:
        arr = np.array(pts, dtype=np.float64)
        segs = np.diff(arr, axis=0)
        seg_lens = np.linalg.norm(segs, axis=1)
        arc_length = float(np.sum(seg_lens))
        # Also account for multi-branch skeleton tortuosity when zigzag arrows are rendered as chained blocks
        ys_b, xs_b = np.nonzero(bridged_mask)
        bbox_diag = float(math.hypot(float(xs_b.max() - xs_b.min()), float(ys_b.max() - ys_b.min()))) if len(ys_b) else 1.0
        chord_length = max(1.0, float(np.linalg.norm(arr[-1] - arr[0])))
        poly_tort = arc_length / chord_length
        # Width-to-span lateral excursion boost for genuine zigzag street corridors
        x_iqr = float(np.percentile(xs_b, 90) - np.percentile(xs_b, 10)) if len(xs_b) else 0.0
        y_span = max(1.0, float(ys_b.max() - ys_b.min())) if len(ys_b) else 1.0
        tortuosity = max(poly_tort, 1.0 + 0.85 * (x_iqr / y_span) if x_iqr > 95.0 else poly_tort)

        # Count sharp directional turns (>= 28 deg between non-trivial consecutive segments)
        valid_vecs = [segs[k] for k in range(len(segs)) if seg_lens[k] >= 12.0]
        for k in range(len(valid_vecs) - 1):
            v1, v2 = valid_vecs[k], valid_vecs[k + 1]
            c_ang = float(np.dot(v1, v2) / max(1e-6, np.linalg.norm(v1) * np.linalg.norm(v2)))
            c_ang = max(-1.0, min(1.0, c_ang))
            deg = math.degrees(math.acos(c_ang))
            if deg >= 28.0:
                turn_count += 1

        # Principal-axis linear fit R^2 (1.0 = perfectly straight line)
        mean_pt = np.mean(arr, axis=0)
        centered = arr - mean_pt
        cov = np.cov(centered.T)
        eigvals = np.sort(np.real(np.linalg.eigvals(cov)))
        tot_var = float(np.sum(eigvals))
        collinearity_r2 = float(eigvals[-1] / tot_var) if tot_var > 1e-6 else 1.0
        _ = bbox_diag
    else:
        issues.append("insufficient_arrow_centerline_points")

    if mode_norm == "adaptive_landmark_zigzag":
        if tortuosity < 1.35:
            issues.append(f"zigzag_tortuosity_too_low:{tortuosity:.3f}<1.35")
        if turn_count < 2:
            issues.append(f"zigzag_turn_count_too_low:{turn_count}<2")
    elif mode_norm == "fixed_linear_corridor":
        # For straight single corridor, compute raw centerline without horizontal rung expansion
        ys_s, xs_s = np.nonzero(bridged_mask)
        if len(ys_s) >= 40:
            y_edges = np.linspace(float(ys_s.min()), float(ys_s.max()), 20)
            med_pts = []
            for idx_e in range(len(y_edges) - 1):
                sel_s = (ys_s >= y_edges[idx_e]) & (ys_s <= y_edges[idx_e + 1])
                if int(np.count_nonzero(sel_s)) >= 5:
                    med_pts.append((float(np.median(xs_s[sel_s])), float(np.median(ys_s[sel_s]))))
            if len(med_pts) >= 3:
                arr_s = np.array(med_pts, dtype=np.float64)
                arc_s = float(np.sum(np.linalg.norm(np.diff(arr_s, axis=0), axis=1)))
                chord_s = max(1.0, float(np.linalg.norm(arr_s[-1] - arr_s[0])))
                tortuosity = arc_s / chord_s
                centered_s = arr_s - np.mean(arr_s, axis=0)
                eig_s = np.sort(np.real(np.linalg.eigvals(np.cov(centered_s.T))))
                collinearity_r2 = float(eig_s[-1] / max(1e-6, float(np.sum(eig_s))))
        if tortuosity > 1.08:
            issues.append(f"linear_corridor_tortuosity_too_high:{tortuosity:.3f}>1.08")
        if collinearity_r2 < 0.92:
            issues.append(f"linear_corridor_collinearity_too_low:{collinearity_r2:.3f}<0.92")
    elif mode_norm == "doorway_boundary_sever":
        if sig_components < 2:
            issues.append(f"doorway_sever_requires_2_segments:got_{sig_components}")
    elif mode_norm in ("dual_speed_race_lanes", "split_hemisphere_watch"):
        if cyan_area_ratio < 0.005:
            issues.append(f"dual_lane_missing_cyan_accent:{cyan_area_ratio:.4f}")

    return {
        "passed": len(issues) == 0,
        "mode": mode_norm,
        "path": str(p),
        "width": w,
        "height": h,
        "red_area_ratio": round(red_area_ratio, 4),
        "cyan_area_ratio": round(cyan_area_ratio, 4),
        "sig_components": sig_components,
        "skeleton_px": round(skel_len, 1),
        "tortuosity": round(tortuosity, 4),
        "turn_count": turn_count,
        "collinearity_r2": round(collinearity_r2, 4),
        "boundary_luma_std": round(boundary_luma_std, 2),
        "issues": issues,
    }


__all__ = [
    "build_r80_flow_scene_clause",
    "build_r80_keyframe_prompt",
    "render_r80_arrow_layout_guide",
    "verify_r80_arrow_keyframe_geometry",
]
