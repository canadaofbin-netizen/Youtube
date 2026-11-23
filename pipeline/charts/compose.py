"""
ALL ABOUT BRAIN — R70-M Multi-Layer & Multi-Panel Chart Composer (`pipeline/charts/compose.py`).

Composes single-panel (`1x1`) and 2-panel (`2x1`) hand-drawn charts with:
  - Sequential layer build-up (`reveal_at`)
  - Top-right handwritten `"Concept"` badge for `mode="illustrative"`
  - Provenance footer (`Study: ...` / `Modeled from reported stats · ...` / `Concept · ...`)
  - Strict lower-canvas protection (`Y >= 68%` remains `alpha == 0`).
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
from PIL import Image, ImageDraw

from pipeline.charts.axes import PanelViewport, build_panel_viewport, draw_panel_header_and_axes
from pipeline.charts.layers import LAYER_DISPATCH
from pipeline.charts.spec import parse_chart_spec
from pipeline.config import (
    DATA_STAMP_ILLUSTRATION_TAG,
    DATA_STAMP_Y_FRAC_RANGE,
    UNIVERSAL_SAFE_X_RIGHT_PX,
    VIDEO_HEIGHT,
    VIDEO_WIDTH,
)


def _ease_out_cubic(x: float) -> float:
    t = max(0.0, min(1.0, float(x)))
    return 1.0 - (1.0 - t) ** 3


def _select_axis_mode(panel_spec: dict[str, Any]) -> str:
    layers = panel_spec.get("layers") or []
    if not layers:
        return "none"
    types = [str(l.get("type") or "") for l in layers]
    if any(t in ("bar", "dot_array", "arc_gauge", "slope") for t in types):
        return "none"
    for lyr in layers:
        if lyr.get("type") == "function_curve" and str(lyr.get("fn") or lyr.get("function") or "").lower() == "prospect_value":
            return "zero_cross"
    return "l_frame"


def _draw_concept_badge(
    canvas: Image.Image,
    vp: PanelViewport,
    *,
    progress: float,
    master_alpha: float,
    style: str,
    ctx: dict[str, Any],
) -> None:
    if progress <= 0.05:
        return
    draw_stroke_fn = ctx["draw_stroke_fn"]
    draw_text_fn = ctx["draw_text_fn"]
    load_font_fn = ctx["load_font_fn"]
    loop_fn = ctx["loop_fn"]

    alpha_i = max(0, min(255, int(round(248 * master_alpha * min(1.0, progress * 1.6)))))
    f_badge = load_font_fn(int(round((34 if vp.layout == "2x1" else 42) * vp.scale_y)), expressive_accent=True)
    tag_txt = str(DATA_STAMP_ILLUSTRATION_TAG or "Concept")
    tb = ImageDraw.Draw(canvas).textbbox((0, 0), tag_txt, font=f_badge)
    tw, th = tb[2] - tb[0], tb[3] - tb[1]
    rx_est = max(42.0 * vp.scale_x, 0.62 * tw + 16.0 * vp.scale_x)
    ry_est = max(22.0 * vp.scale_y, 0.62 * th + 8.0 * vp.scale_y)
    bx = int(round(vp.x_right - 0.5 * tw - rx_est - 14.0 * vp.scale_x))
    by = max(
        vp.y_top + int(round((18 if vp.layout == "2x1" else 22) * vp.scale_y)),
        int(math.ceil(vp.y_top + ry_est - 0.5 * th + 10.0 * vp.scale_y)),
    )

    mb = draw_text_fn(
        canvas,
        (bx, by),
        tag_txt,
        f_badge,
        (255, 226, 118, alpha_i),
        halo_alpha=int(alpha_i * 0.72),
    )
    cx = 0.5 * (mb[0] + mb[2])
    cy = 0.5 * (mb[1] + mb[3]) + 2.0 * vp.scale_y
    lp, lw = loop_fn(
        (cx, cy),
        rx=rx_est,
        ry=ry_est,
        turns=1.22,
        tilt_deg=-4.0,
        base_width=4.8,
        scale=vp.scale,
        seed=919,
    )
    draw_stroke_fn(canvas, lp, lw, (255, 204, 96), alpha=alpha_i, progress=min(1.0, progress * 1.3), style=style, seed=920)


def _draw_panel_footer(
    canvas: Image.Image,
    vp: PanelViewport,
    panel_spec: dict[str, Any],
    *,
    norm_p: float,
    master_alpha: float,
    ctx: dict[str, Any],
) -> None:
    if norm_p < 0.18:
        return
    mode = str(panel_spec.get("mode") or "study").lower()
    if mode == "illustrative":
        # Illustrative charts display only the top-right 'Concept' stamp (no duplicate bottom footer)
        return
    cite = str(panel_spec.get("source_citation") or "").strip()
    if not cite:
        return
    footer_txt = cite if cite.lower().startswith("study:") else f"Study: {cite}"

    load_font_fn = ctx["load_font_fn"]
    draw_text_fn = ctx["draw_text_fn"]
    f_cite = load_font_fn(int(round(30 * vp.scale_y)), expressive_accent=False)
    a_val = max(0, min(255, int(round(215 * master_alpha * min(1.0, (norm_p - 0.18) / 0.25)))))
    is_compact_vp = (vp.y_bot - vp.plot_bot) <= int(round(72 * vp.scale_y))
    footer_pad = 16 if is_compact_vp else 48
    bot_guard = 36 if is_compact_vp else 28
    fy = min(vp.y_bot - int(round(bot_guard * vp.scale_y)), vp.plot_bot + int(round(footer_pad * vp.scale_y)))
    fx = vp.plot_left
    max_fw = max(int(round(180 * vp.scale_x)), vp.x_right - int(round(14 * vp.scale_x)) - fx)
    probe_d = ImageDraw.Draw(canvas)
    disp_footer = footer_txt[:68]
    while len(disp_footer) > 12:
        fb = probe_d.textbbox((0, 0), disp_footer, font=f_cite)
        if (fb[2] - fb[0]) <= max_fw:
            break
        if " " in disp_footer:
            disp_footer = disp_footer.rsplit(" ", 1)[0].rstrip(" ·,;:-")
        else:
            disp_footer = disp_footer[:-2]
    draw_text_fn(
        canvas,
        (fx, fy),
        disp_footer,
        f_cite,
        (226, 224, 214, a_val),
        halo_alpha=int(a_val * 0.70),
        halo_blur_px=3.0,
    )


def render_chart_spec_rgba_frame(
    stamp: dict[str, Any],
    t_rel: float,
    total_dur: float,
    *,
    width: int = VIDEO_WIDTH,
    height: int = VIDEO_HEIGHT,
    ctx: dict[str, Any],
    max_y_frac: float | None = None,
) -> Image.Image:
    """Renders a full-frame RGBA overlay for any R70-M single-panel (`1x1`) or 2-panel (`2x1`) chart spec."""
    fade_in = min(1.0, max(0.0, t_rel / 0.22))
    fade_out = min(1.0, max(0.0, (total_dur - t_rel) / 0.28))
    master_alpha = min(fade_in, fade_out)

    canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    if master_alpha <= 0.01:
        return canvas

    spec = parse_chart_spec(stamp)
    layout = spec["layout"]
    draw_window = max(1.8, min(4.8, total_dur - 0.55))
    norm_p = max(0.0, min(1.0, t_rel / draw_window))
    p_axis = _ease_out_cubic(norm_p / 0.14)

    for p_spec in spec["panels"]:
        vp = build_panel_viewport(
            width,
            height,
            layout=layout,
            panel_index=int(p_spec["panel_index"]),
            max_y_frac=max_y_frac,
        )
        axis_mode = _select_axis_mode(p_spec)
        draw_panel_header_and_axes(
            canvas,
            vp,
            p_spec,
            p_axis=p_axis,
            master_alpha=master_alpha,
            draw_stroke_fn=ctx["draw_stroke_fn"],
            draw_text_fn=ctx["draw_text_fn"],
            load_font_fn=ctx["load_font_fn"],
            axis_mode=axis_mode,
        )

        for lyr in p_spec["layers"]:
            l_type = str(lyr.get("type") or "bar").lower()
            fn = LAYER_DISPATCH.get(l_type)
            if not fn:
                continue
            u0, u1 = (lyr.get("reveal_at") or [0.08, 0.90])[:2]
            span = max(0.08, float(u1) - float(u0))
            l_prog = _ease_out_cubic((norm_p - float(u0)) / span)
            fn(
                canvas,
                vp,
                lyr,
                p_spec,
                progress=l_prog,
                master_alpha=master_alpha,
                ctx=ctx,
            )

        if str(p_spec.get("mode") or "").lower() == "illustrative":
            _draw_concept_badge(
                canvas,
                vp,
                progress=p_axis,
                master_alpha=master_alpha,
                style=str(p_spec.get("style") or "crayon"),
                ctx=ctx,
            )

        _draw_panel_footer(
            canvas,
            vp,
            p_spec,
            norm_p=norm_p,
            master_alpha=master_alpha,
            ctx=ctx,
        )

    # Hard 3-platform safe-zone guarantee:
    #   - Y >= 12% (avoids top search bar)
    #   - Y < 68%  (keeps burned subtitle zone 100% untouched)
    #   - X <= UNIVERSAL_SAFE_X_RIGHT_PX * scale_x (avoids TikTok/Reels right-hand icon stack)
    top_y0 = int(math.ceil(height * float(DATA_STAMP_Y_FRAC_RANGE[0])))
    sub_y0 = int(round(height * 0.68))
    safe_x_end = min(width, int(round(UNIVERSAL_SAFE_X_RIGHT_PX * (width / 1080.0))) + 1)
    arr = np.asarray(canvas, dtype=np.uint8)
    if (
        np.any(arr[:top_y0, :, 3] > 0)
        or np.any(arr[sub_y0:, :, 3] > 0)
        or (safe_x_end < width and np.any(arr[:, safe_x_end:, 3] > 0))
    ):
        arr = arr.copy()
        arr[:top_y0, :, :] = 0
        arr[sub_y0:, :, :] = 0
        if safe_x_end < width:
            arr[:, safe_x_end:, :] = 0
        canvas = Image.fromarray(arr, mode="RGBA")
    return canvas
