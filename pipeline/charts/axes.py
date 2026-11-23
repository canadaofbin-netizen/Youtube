"""
ALL ABOUT BRAIN — R70-M Hand-Drawn Viewport & Axes Engine (`pipeline/charts/axes.py`).

Provides:
  - Single-panel (`1x1`) and 2-panel vertical (`2x1`) HERO viewports (`Y = 10%..62%`, keeping `Y >= 68%` 100% clear).
  - Hand-drawn title + underline, L-shaped / baseline / zero-centered axes, tick marks, and axis labels.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import numpy as np
from PIL import Image, ImageDraw

from pipeline.config import DATA_STAMP_Y_FRAC_RANGE, UNIVERSAL_SAFE_X_RIGHT_PX


@dataclass(frozen=True)
class PanelViewport:
    panel_index: int
    layout: str
    width: int
    height: int
    scale_x: float
    scale_y: float
    scale: float
    x_left: int
    x_right: int
    y_top: int
    y_bot: int
    plot_left: int
    plot_right: int
    plot_top: int
    plot_bot: int

    @property
    def plot_w(self) -> float:
        return float(max(60, self.plot_right - self.plot_left))

    @property
    def plot_h(self) -> float:
        return float(max(60, self.plot_bot - self.plot_top))

    def map_x(self, val: float, vmin: float, vmax: float) -> float:
        span = max(1e-6, float(vmax) - float(vmin))
        u = max(0.0, min(1.0, (float(val) - float(vmin)) / span))
        return float(self.plot_left) + u * self.plot_w

    def map_y(self, val: float, vmin: float, vmax: float) -> float:
        span = max(1e-6, float(vmax) - float(vmin))
        u = max(0.0, min(1.0, (float(val) - float(vmin)) / span))
        return float(self.plot_bot) - u * self.plot_h


def build_panel_viewport(
    width: int,
    height: int,
    *,
    layout: str = "1x1",
    panel_index: int = 0,
    max_y_frac: float | None = None,
) -> PanelViewport:
    """
    Computes the pixel bounding box for panel `panel_index` inside the 3-platform HERO safe zone
    (`Y = 12%..62%`, `X <= UNIVERSAL_SAFE_X_RIGHT_PX = 910px` on `1080x1920`).
    When `max_y_frac` is supplied (e.g. Canonical I02 dark-void lower-brain backdrop),
    compacts the plot vertically strictly above the lower subject crown with zero overlap.
    """
    scale_x = width / 1080.0
    scale_y = height / 1920.0
    scale = min(scale_x, scale_y)
    y_lo_frac, y_hi_frac = DATA_STAMP_Y_FRAC_RANGE

    x_left = int(round(56 * scale_x))
    x_right = int(round(UNIVERSAL_SAFE_X_RIGHT_PX * scale_x))
    hero_top = int(math.ceil(height * y_lo_frac))
    eff_hi_frac = min(0.62, y_hi_frac)
    if max_y_frac is not None:
        eff_hi_frac = min(eff_hi_frac, max(y_lo_frac + 0.18, float(max_y_frac)))
    hero_bot = int(round(height * eff_hi_frac))

    if layout == "2x1":
        mid_y = int(round(0.5 * (hero_top + hero_bot)))
        gap = int(round(18 * scale_y))
        if panel_index == 0:
            y_top = hero_top
            y_bot = mid_y - gap // 2
        else:
            y_top = mid_y + gap // 2
            y_bot = hero_bot
        plot_top = y_top + int(round(88 * scale_y))
        plot_bot = y_bot - int(round(56 * scale_y))
    else:
        y_top = hero_top
        y_bot = hero_bot
        if (hero_bot - hero_top) < int(round(640 * scale_y)):
            plot_top = y_top + int(round(108 * scale_y))
            plot_bot = y_bot - int(round(60 * scale_y))
        else:
            plot_top = y_top + int(round(128 * scale_y))
            plot_bot = y_bot - int(round(98 * scale_y))

    plot_left = x_left + int(round(66 * scale_x))
    plot_right = x_right - int(round(46 * scale_x))

    return PanelViewport(
        panel_index=panel_index,
        layout=layout,
        width=width,
        height=height,
        scale_x=scale_x,
        scale_y=scale_y,
        scale=scale,
        x_left=x_left,
        x_right=x_right,
        y_top=y_top,
        y_bot=y_bot,
        plot_left=plot_left,
        plot_right=plot_right,
        plot_top=plot_top,
        plot_bot=plot_bot,
    )


def draw_panel_header_and_axes(
    canvas: Image.Image,
    vp: PanelViewport,
    panel_spec: dict[str, Any],
    *,
    p_axis: float,
    master_alpha: float,
    draw_stroke_fn: Any,
    draw_text_fn: Any,
    load_font_fn: Any,
    axis_mode: str = "l_frame",
) -> None:
    """
    Renders the panel handwritten title + warm underline and the requested axis frame:
      - `'l_frame'`: standard bottom X-axis + left Y-axis
      - `'left_only'`: vertical baseline on left (for horizontal bar / range / raincloud)
      - `'zero_cross'`: central X/Y axes crossing at `(0, 0)` (for `prospect_value` S-curve)
      - `'none'`: no Cartesian axes (for `dot_array`, `arc_gauge`, `slope`)
    """
    def _a(base: int) -> int:
        return max(0, min(255, int(round(base * master_alpha))))

    style = str(panel_spec.get("style") or "crayon")
    seed = int(panel_spec.get("seed") or 101)
    is_two = vp.layout == "2x1"

    title_txt = str(panel_spec.get("title") or "").strip()
    if title_txt:
        if title_txt.isupper():
            title_txt = title_txt.title()
        f_title = load_font_fn(int(round((42 if is_two else 52) * vp.scale_y)), expressive_accent=False)
        title_y = vp.y_top + int(round((12 if is_two else 18) * vp.scale_y))
        has_badge = bool(panel_spec.get("badge_tag")) or str(panel_spec.get("mode") or "").lower() == "illustrative"
        max_title_x = (
            vp.x_right - int(round(196 * vp.scale_x))
            if has_badge
            else vp.x_right - int(round(16 * vp.scale_x))
        )
        tx0 = vp.x_left + int(round(6 * vp.scale_x))
        avail_tw = max(int(round(160 * vp.scale_x)), max_title_x - tx0)
        probe_d = ImageDraw.Draw(canvas)
        disp_title = title_txt[:46]
        while len(disp_title) > 8:
            tb_cand = probe_d.textbbox((0, 0), disp_title, font=f_title)
            if (tb_cand[2] - tb_cand[0]) <= avail_tw:
                break
            if " " in disp_title:
                disp_title = disp_title.rsplit(" ", 1)[0].rstrip(" -:,")
            else:
                disp_title = disp_title[:-2]
        tbbox = draw_text_fn(
            canvas,
            (tx0, title_y),
            disp_title,
            f_title,
            (255, 248, 232, _a(252)),
            halo_alpha=_a(170),
        )
        ul_y = min(vp.plot_top - int(round(10 * vp.scale_y)), tbbox[3] + int(round(8 * vp.scale_y)))
        ul_x1 = min(max_title_x, tbbox[2] + int(round(14 * vp.scale_x)))
        ul_u = np.linspace(0.0, 1.0, 44, dtype=np.float32)
        ul_pts = np.column_stack([
            vp.x_left + (ul_x1 - vp.x_left) * ul_u,
            ul_y + (2.2 * vp.scale_y) * np.sin(2.0 * np.pi * 1.2 * ul_u + 0.3),
        ]).astype(np.float32)
        ul_w = ((4.6 if is_two else 5.4) * vp.scale * (0.45 + 0.55 * np.sin(np.pi * ul_u))).astype(np.float32)
        draw_stroke_fn(
            canvas,
            ul_pts,
            ul_w,
            (255, 214, 112),
            alpha=_a(222),
            progress=p_axis,
            style=style,
            seed=seed + 3,
        )

    if axis_mode == "none" or p_axis <= 0.01:
        return

    axis_rgb = (240, 236, 224)
    u = np.linspace(0.0, 1.0, 52, dtype=np.float32)
    w_ax = ((5.2 if is_two else 6.4) * vp.scale * (0.52 + 0.48 * np.sin(np.pi * u))).astype(np.float32)

    if axis_mode == "zero_cross":
        cx = 0.5 * (vp.plot_left + vp.plot_right)
        cy = 0.5 * (vp.plot_top + vp.plot_bot)
        h_pts = np.column_stack([
            vp.plot_left + (vp.plot_right - vp.plot_left) * u,
            cy + (1.8 * vp.scale_y) * np.sin(2.0 * np.pi * 1.3 * u + 0.4),
        ]).astype(np.float32)
        v_pts = np.column_stack([
            cx + (1.8 * vp.scale_x) * np.sin(2.0 * np.pi * 1.3 * u + 1.1),
            vp.plot_top + (vp.plot_bot - vp.plot_top) * u,
        ]).astype(np.float32)
        draw_stroke_fn(canvas, h_pts, w_ax, axis_rgb, alpha=_a(215), progress=p_axis, style=style, seed=seed + 5)
        draw_stroke_fn(canvas, v_pts, w_ax, axis_rgb, alpha=_a(215), progress=p_axis, style=style, seed=seed + 7)
        return

    # Left vertical axis
    v_pts = np.column_stack([
        vp.plot_left + (1.8 * vp.scale_x) * np.sin(2.0 * np.pi * 1.4 * u + 0.7),
        vp.plot_top + (vp.plot_bot - vp.plot_top) * u,
    ]).astype(np.float32)
    draw_stroke_fn(canvas, v_pts, w_ax, axis_rgb, alpha=_a(228), progress=p_axis, style=style, seed=seed + 9)

    if axis_mode == "l_frame":
        h_pts = np.column_stack([
            vp.plot_left + (vp.plot_right - vp.plot_left) * u,
            vp.plot_bot + (1.8 * vp.scale_y) * np.sin(2.0 * np.pi * 1.2 * u + 0.2),
        ]).astype(np.float32)
        draw_stroke_fn(canvas, h_pts, w_ax, axis_rgb, alpha=_a(228), progress=p_axis, style=style, seed=seed + 11)

        f_ax = load_font_fn(int(round((28 if is_two else 34) * vp.scale_y)), expressive_accent=False)
        x_lbl = str(panel_spec.get("x_label") or "").strip()
        y_lbl = str(panel_spec.get("y_label") or "").strip()
        if x_lbl and p_axis > 0.6:
            disp_xl = x_lbl[:34]
            tb = ImageDraw.Draw(canvas).textbbox((0, 0), disp_xl, font=f_ax)
            tw = tb[2] - tb[0]
            tx_xl = max(
                vp.plot_left,
                min(vp.x_right - tw - int(round(14 * vp.scale_x)), int(round(vp.plot_right - tw - 6 * vp.scale_x))),
            )
            draw_text_fn(
                canvas,
                (tx_xl, vp.plot_bot + int(round(8 * vp.scale_y))),
                disp_xl,
                f_ax,
                (224, 220, 208, _a(215)),
                halo_alpha=_a(140),
            )
        if y_lbl and p_axis > 0.6:
            draw_text_fn(
                canvas,
                (vp.x_left + int(round(4 * vp.scale_x)), vp.plot_top - int(round(32 * vp.scale_y))),
                y_lbl[:24],
                f_ax,
                (224, 220, 208, _a(215)),
                halo_alpha=_a(140),
            )
