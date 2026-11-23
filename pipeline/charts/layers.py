"""
ALL ABOUT BRAIN — R70-M 15-Layer Hand-Drawn Renderer (`pipeline/charts/layers.py`).

Implements progressive hand-drawn rendering for all 15 grammar-of-graphics layer types:
  1. `bar`            — Horizontal/vertical crayon/pen bars + Bézier comparison arrow + 1.32-turn ellipse loop
  2. `error`          — Hand-drawn `I`-beam error bars (`SD`, `SE`, `95% CI`)
  3. `slope`          — Left-to-right paired `Before -> After` slope graph
  4. `dot_array`      — `k of n` hand-drawn dot matrix (`1 of 14`)
  5. `arc_gauge`      — Clockwise hand-drawn circular arc gauge (`0% -> 86%`)
  6. `points`         — Jittered strip/swarm sample points or curve inflection markers
  7. `box`            — Hand-drawn quartile box (`Q1..Q3`) + median stroke + `min..max` whiskers
  8. `violin`         — `gaussian_kde` probability silhouette (`full` or `half=True` raincloud) + crayon hatching
  9. `histogram`      — Binned hand-drawn columns rising from baseline
 10. `density`        — Smooth kernel density curve with soft hand-sketched hatching
 11. `scatter`        — `(x, y)` bivariate point cloud (up to 120 points)
 12. `regression`     — Hand-drawn OLS fit line + `r = 0.79` callout badge
 13. `line`           — Multi-series progressive trajectory lines (`1..3` series)
 14. `band`           — Confidence / range band (`regression_ci`, `line_band`, `range_bars`)
 15. `function_curve` — Mathematical & cognitive curves (`exp_decay`, `sigmoid`, `normal_pdf`, `prospect_value`, `inverted_u`, `power`, `log`, `linear`)
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
from PIL import Image, ImageDraw

from pipeline.charts.axes import PanelViewport
from pipeline.charts.data_prep import (
     compute_kde_profile,
    evaluate_function_curve,
    prepare_group_distributions,
    prepare_scatter_and_regression,
)

PALETTE_GROUPS: list[tuple[int, int, int]] = [
    (238, 114, 104),  # Warm coral-red
    (68, 228, 162),   # Mint-emerald
    (92, 206, 255),   # Sky-cyan
    (255, 204, 96),   # Warm amber-gold
]


def _display_unit(unit: str = "") -> str:
    u = str(unit or "").strip()
    if u in ("uV^2", "µV^2", "μV^2", "µV²"):
        return "\u03bcV\u00b2"
    return u.replace("^2", "\u00b2").replace("\u00b5", "\u03bc")


def _fmt_val(v: float, unit: str = "", ref_v: float | None = None) -> str:
    check_v = v if ref_v is None else ref_v
    if abs(check_v - round(check_v)) < 0.005:
        s = f"{int(round(v))}"
    elif abs(check_v * 10.0 - round(check_v * 10.0)) < 0.05:
        s = f"{v:.1f}"
    else:
        s = f"{v:.2f}"
    return f"{s} {_display_unit(unit)}".strip()


def _group_domain(groups: list[dict[str, Any]]) -> tuple[float, float]:
    if not groups:
        return 0.0, 10.0
    lo = min(min(float(g["min"]), float(g["error_lo"]), float(g["mean"])) for g in groups)
    hi = max(max(float(g["max"]), float(g["error_hi"]), float(g["mean"])) for g in groups)
    if lo >= 0.0 and lo < (hi - lo) * 0.45:
        lo = 0.0
    span = max(1.0, hi - lo)
    return lo - 0.06 * span, hi + 0.14 * span


def _group_slot_y(vp: PanelViewport, idx: int, n_groups: int) -> tuple[float, float]:
    slot_h = vp.plot_h / max(1, n_groups)
    cy = float(vp.plot_top) + (idx + 0.52) * slot_h
    return cy, slot_h


def _draw_hand_circle(
    canvas: Image.Image,
    cx: float,
    cy: float,
    radius: float,
    rgb: tuple[int, int, int],
    *,
    alpha: int,
    fill_alpha: int,
    style: str,
    seed: int,
    scale: float,
    draw_stroke_fn: Any,
) -> None:
    if alpha <= 2 or radius <= 1.0:
        return
    if fill_alpha > 4:
        ov = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        odraw = ImageDraw.Draw(ov, "RGBA")
        r_in = max(1.0, radius * 0.84)
        odraw.ellipse([cx - r_in, cy - r_in, cx + r_in, cy + r_in], fill=(rgb[0], rgb[1], rgb[2], fill_alpha))
        canvas.alpha_composite(ov)
    u = np.linspace(0.0, 1.0, 28, dtype=np.float32)
    th = 2.0 * math.pi * 1.12 * u + (seed % 7) * 0.4
    r_mod = radius * (0.94 + 0.10 * np.sin(3.0 * th))
    pts = np.column_stack([cx + r_mod * np.cos(th), cy + r_mod * np.sin(th)]).astype(np.float32)
    w = np.full(len(u), max(2.2, 3.6 * scale), dtype=np.float32)
    draw_stroke_fn(canvas, pts, w, rgb, alpha=alpha, progress=1.0, style=style, seed=seed)


def render_bar_layer(
    canvas: Image.Image,
    vp: PanelViewport,
    layer: dict[str, Any],
    panel_spec: dict[str, Any],
    *,
    progress: float,
    master_alpha: float,
    ctx: dict[str, Any],
) -> None:
    groups = prepare_group_distributions(layer, seed=int(panel_spec.get("seed") or 101))
    if not groups:
        return
    draw_stroke_fn = ctx["draw_stroke_fn"]
    draw_text_fn = ctx["draw_text_fn"]
    load_font_fn = ctx["load_font_fn"]
    arrow_fn = ctx["arrow_fn"]
    loop_fn = ctx["loop_fn"]

    def _a(b: int) -> int:
        return max(0, min(255, int(round(b * master_alpha))))

    style = str(panel_spec.get("style") or "crayon")
    is_two = vp.layout == "2x1"
    f_lbl = load_font_fn(int(round((34 if is_two else 46) * vp.scale_y)), expressive_accent=False)
    f_val = load_font_fn(int(round((40 if is_two else 56) * vp.scale_y)), expressive_accent=False)
    f_mult = load_font_fn(int(round((56 if is_two else 82) * vp.scale_y)), expressive_accent=True)

    has_neg = any(float(g["mean"]) < 0.0 for g in groups)
    min_v = min(float(g["mean"]) for g in groups)
    max_pos_v = max(0.0, max(float(g["mean"]) for g in groups))
    max_v = max(max(0.01, abs(float(g["mean"])), abs(float(g["error_hi"]))) for g in groups)
    bar_max_w = max(120.0 * vp.scale_x, vp.plot_w * 0.62)
    signed_x0 = float(vp.plot_left + 145 * vp.scale_x)
    signed_span_w = max(180.0 * vp.scale_x, float(vp.plot_right) - signed_x0 - 150.0 * vp.scale_x)
    signed_total = max(1e-3, max_pos_v - min_v)
    zero_x = signed_x0 + signed_span_w * (abs(min_v) / signed_total) if has_neg else float(vp.plot_left + 12 * vp.scale_x)
    tips: list[tuple[float, float]] = []
    val_right_edges: list[float] = []
    n_g = len(groups)
    probe_d = ImageDraw.Draw(canvas)

    if has_neg and progress > 0.02:
        z_pts = np.column_stack([
            np.full(24, zero_x, dtype=np.float32),
            np.linspace(float(vp.plot_top + 6 * vp.scale_y), float(vp.plot_bot - 10 * vp.scale_y), 24, dtype=np.float32),
        ]).astype(np.float32)
        z_w = np.full(24, 3.0 * vp.scale, dtype=np.float32)
        draw_stroke_fn(canvas, z_pts, z_w, (195, 208, 224), alpha=_a(155), progress=min(1.0, progress * 1.4), style=style, seed=107)

    for idx, g in enumerate(groups):
        cy, slot_h = _group_slot_y(vp, idx, n_g)
        by = cy + slot_h * 0.12
        lbl_y = cy - slot_h * 0.38
        rgb = PALETTE_GROUPS[idx % len(PALETTE_GROUPS)]
        g_prog = max(0.0, min(1.0, (progress - idx * 0.14) / max(0.25, 1.0 - idx * 0.14)))
        if g_prog <= 0.01:
            continue

        draw_text_fn(
            canvas,
            (int(round(vp.plot_left + 14 * vp.scale_x)), int(round(lbl_y))),
            str(g["label"])[:28],
            f_lbl,
            (248, 245, 236, _a(246)),
            halo_alpha=_a(155),
        )
        raw_v = float(g["mean"])
        if has_neg:
            full_len = max(32.0 * vp.scale_x, signed_span_w * (abs(raw_v) / signed_total))
            direction = -1.0 if raw_v < 0.0 else 1.0
            x0 = zero_x
            x1 = zero_x + direction * full_len
            tips.append((x1, by))
            u = np.linspace(0.0, 1.0, 60, dtype=np.float32)
            bar_thick = (20.0 if is_two else 28.0) * vp.scale
            for pk, (y_off, w_m) in enumerate(((-4.5, 1.0), (4.5, 0.92))):
                pts = np.column_stack([
                    x0 + direction * full_len * u,
                    by + y_off * vp.scale_y + (1.8 * vp.scale_y) * np.sin(2.0 * np.pi * 1.4 * u + idx + pk),
                ]).astype(np.float32)
                w = np.full(len(u), bar_thick * w_m, dtype=np.float32)
                draw_stroke_fn(canvas, pts, w, rgb, alpha=_a(238), progress=g_prog, style=style, seed=110 + idx * 13 + pk)

            cur_x = x0 + direction * full_len * g_prog
            val_txt = _fmt_val(raw_v * g_prog, str(g["unit"]), ref_v=raw_v)
            vb = probe_d.textbbox((0, 0), val_txt, font=f_val)
            vw = vb[2] - vb[0]
            if direction < 0.0:
                vx_pos = max(vp.x_left + int(round(8 * vp.scale_x)), int(round(cur_x - vw - 14 * vp.scale_x)))
            else:
                vx_pos = min(vp.x_right - vw - int(round(14 * vp.scale_x)), int(round(cur_x + 16 * vp.scale_x)))
            draw_text_fn(
                canvas,
                (vx_pos, int(round(by - 26 * vp.scale_y))),
                val_txt,
                f_val,
                (255, 252, 240, _a(252)),
                halo_alpha=_a(170),
            )
            val_right_edges.append(float(vx_pos + vw))
            continue

        v = max(0.0, raw_v)
        full_len = max(38.0 * vp.scale_x, bar_max_w * (v / max_v))
        x0 = float(vp.plot_left + 12 * vp.scale_x)
        x1 = x0 + full_len
        tips.append((x1, by))

        u = np.linspace(0.0, 1.0, 60, dtype=np.float32)
        bar_thick = (20.0 if is_two else 28.0) * vp.scale
        for pk, (y_off, w_m) in enumerate(((-4.5, 1.0), (4.5, 0.92))):
            pts = np.column_stack([
                x0 + full_len * u,
                by + y_off * vp.scale_y + (1.8 * vp.scale_y) * np.sin(2.0 * np.pi * 1.4 * u + idx + pk),
            ]).astype(np.float32)
            w = np.full(len(u), bar_thick * w_m, dtype=np.float32)
            draw_stroke_fn(canvas, pts, w, rgb, alpha=_a(238), progress=g_prog, style=style, seed=110 + idx * 13 + pk)

        cur_x = x0 + full_len * g_prog
        val_txt = _fmt_val(v * g_prog, str(g["unit"]), ref_v=v)
        vb = probe_d.textbbox((0, 0), val_txt, font=f_val)
        vw = vb[2] - vb[0]
        vx_pos = min(vp.x_right - vw - int(round(14 * vp.scale_x)), int(round(cur_x + 16 * vp.scale_x)))
        draw_text_fn(
            canvas,
            (vx_pos, int(round(by - 26 * vp.scale_y))),
            val_txt,
            f_val,
            (255, 252, 240, _a(252)),
            halo_alpha=_a(170),
        )
        full_val_txt = _fmt_val(v, str(g["unit"]))
        fvb = probe_d.textbbox((0, 0), full_val_txt, font=f_val)
        fvw, fvh = fvb[2] - fvb[0], fvb[3] - fvb[1]
        fvx = float(min(vp.x_right - fvw - int(round(14 * vp.scale_x)), int(round(x1 + 16 * vp.scale_x))))
        fvy = float(int(round(by - 26 * vp.scale_y)))
        val_right_edges.append(float(fvx + fvw))
        if "full_val_bboxes" not in locals():
            full_val_bboxes: list[tuple[float, float, float, float]] = []
        full_val_bboxes.append((fvx, fvy, fvx + fvw, fvy + fvh))

    if (not has_neg) and len(tips) >= 2 and progress > 0.65:
        v0 = max(0.01, float(groups[0]["mean"]))
        v1 = max(0.01, float(groups[-1]["mean"]))
        ratio = max(v0, v1) / min(v0, v1)
        badge_txt = str(panel_spec.get("multiplier_badge") or "").strip()
        if not badge_txt and ratio >= 1.35:
            badge_txt = f"{int(round(ratio))}×" if abs(ratio - round(ratio)) < 0.12 else f"{ratio:.1f}×"
        if badge_txt:
            arr_p = min(1.0, (progress - 0.65) / 0.32)
            arr_start_x = min(
                vp.x_right - 88.0 * vp.scale_x,
                (val_right_edges[0] + 16.0 * vp.scale_x) if val_right_edges else (tips[0][0] + 90.0 * vp.scale_x),
            )
            geo = arrow_fn(
                (arr_start_x, tips[0][1]),
                (tips[-1][0] - 8 * vp.scale_x, tips[-1][1] - 18 * vp.scale_y),
                base_width=7.2 if is_two else 8.4,
                scale=vp.scale,
                seed=404,
            )
            shaft_pts = np.asarray(geo["shaft_points"], dtype=np.float32).copy()
            shaft_pts[:, 0] = np.minimum(shaft_pts[:, 0], float(vp.x_right - 14.0 * vp.scale_x))
            draw_stroke_fn(canvas, shaft_pts, geo["shaft_widths"], (255, 214, 92), alpha=_a(245), progress=arr_p, style=style, seed=405)
            if arr_p > 0.65:
                wp = (arr_p - 0.65) / 0.35
                draw_stroke_fn(canvas, geo["left_wing_points"], geo["left_wing_widths"], (255, 214, 92), alpha=_a(248), progress=wp, style=style, seed=406)
                draw_stroke_fn(canvas, geo["right_wing_points"], geo["right_wing_widths"], (255, 214, 92), alpha=_a(248), progress=wp, style=style, seed=407)
                ax_x, ax_y = geo["arc_peak_xy"]
                b_word = badge_txt.split()[0]
                bb = probe_d.textbbox((0, 0), b_word, font=f_mult)
                bw_m, bh_m = bb[2] - bb[0], bb[3] - bb[1]
                rx_m = max(36.0 * vp.scale_x, 0.64 * bw_m + 12.0 * vp.scale_x)
                ry_m = max(26.0 * vp.scale_y, 0.60 * bh_m + 8.0 * vp.scale_y)
                max_cx_m = int(round(vp.x_right - 0.5 * bw_m - 1.15 * rx_m - 14.0 * vp.scale_x))
                cx_m = min(max_cx_m, max(vp.plot_left + int(round(120 * vp.scale_x)), int(round(ax_x + 20 * vp.scale_x))))
                cy_m = max(vp.plot_top + int(round(8 * vp.scale_y)), int(round(ax_y - 34 * vp.scale_y)))
                vbox_list = locals().get("full_val_bboxes") or []

                def _overlaps_bar_val(tx: int, ty: int) -> bool:
                    lcx, lcy = tx + 0.5 * bw_m, ty + 0.5 * bh_m
                    px_pad, py_pad = 1.15 * rx_m + 8.0 * vp.scale_x, 1.15 * ry_m + 8.0 * vp.scale_y
                    for vx0, vy0, vx1, vy1 in vbox_list:
                        if not (lcx + px_pad < vx0 or lcx - px_pad > vx1 or lcy + py_pad < vy0 or lcy - py_pad > vy1):
                            return True
                    return False

                if _overlaps_bar_val(cx_m, cy_m) and tips:
                    short_i = int(np.argmin([tp[0] for tp in tips]))
                    sr_x = float(val_right_edges[short_i]) if short_i < len(val_right_edges) else float(tips[short_i][0])
                    for alt_x, alt_y in (
                        (min(max_cx_m, int(round(sr_x + 0.65 * rx_m + 20 * vp.scale_x))), int(round(tips[short_i][1] - 0.5 * bh_m))),
                        (cx_m, int(round(max(v[3] for v in vbox_list) + 1.2 * ry_m))),
                    ):
                        if alt_x <= max_cx_m and not _overlaps_bar_val(alt_x, alt_y):
                            cx_m, cy_m = alt_x, alt_y
                            break
                mb = draw_text_fn(canvas, (cx_m, cy_m), b_word, f_mult, (255, 232, 118, _a(252)), halo_alpha=_a(175))
                lp, lw = loop_fn(
                    (0.5 * (mb[0] + mb[2]), 0.5 * (mb[1] + mb[3])),
                    rx=max(36.0 * vp.scale_x, 0.64 * (mb[2] - mb[0]) + 12 * vp.scale_x),
                    ry=ry_m,
                    scale=vp.scale,
                )
                lp = np.asarray(lp, dtype=np.float32).copy()
                draw_stroke_fn(canvas, lp, lw, (255, 136, 96), alpha=_a(238), progress=wp, style=style, seed=809)


def render_error_layer(
    canvas: Image.Image,
    vp: PanelViewport,
    layer: dict[str, Any],
    panel_spec: dict[str, Any],
    *,
    progress: float,
    master_alpha: float,
    ctx: dict[str, Any],
) -> None:
    groups = prepare_group_distributions(layer, seed=int(panel_spec.get("seed") or 101))
    if not groups or progress <= 0.01:
        return
    draw_stroke_fn = ctx["draw_stroke_fn"]
    style = str(panel_spec.get("style") or "ink_pen")

    def _a(b: int) -> int:
        return max(0, min(255, int(round(b * master_alpha))))

    max_v = max(max(0.01, abs(float(g["mean"])), abs(float(g["error_hi"]))) for g in groups)
    bar_max_w = max(120.0 * vp.scale_x, vp.plot_w * 0.62)
    x0 = float(vp.plot_left + 12 * vp.scale_x)
    cap_h = (12.0 if vp.layout == "2x1" else 16.0) * vp.scale_y

    for idx, g in enumerate(groups):
        cy, slot_h = _group_slot_y(vp, idx, len(groups))
        by = cy + slot_h * 0.12
        x_lo = x0 + bar_max_w * (max(0.0, float(g["error_lo"])) / max_v)
        x_hi = x0 + bar_max_w * (max(0.0, float(g["error_hi"])) / max_v)
        u = np.linspace(0.0, 1.0, 24, dtype=np.float32)
        w = np.full(len(u), 4.6 * vp.scale, dtype=np.float32)
        h_pts = np.column_stack([x_lo + (x_hi - x_lo) * u, np.full_like(u, by)]).astype(np.float32)
        draw_stroke_fn(canvas, h_pts, w, (255, 248, 224), alpha=_a(235), progress=progress, style=style, seed=210 + idx)
        for cap_x in (x_lo, x_hi):
            c_pts = np.column_stack([np.full_like(u, cap_x), (by - cap_h) + 2.0 * cap_h * u]).astype(np.float32)
            draw_stroke_fn(canvas, c_pts, w, (255, 248, 224), alpha=_a(235), progress=progress, style=style, seed=220 + idx)


def render_box_layer(
    canvas: Image.Image,
    vp: PanelViewport,
    layer: dict[str, Any],
    panel_spec: dict[str, Any],
    *,
    progress: float,
    master_alpha: float,
    ctx: dict[str, Any],
) -> None:
    groups = prepare_group_distributions(layer, seed=int(panel_spec.get("seed") or 101))
    if not groups or progress <= 0.01:
        return
    draw_stroke_fn = ctx["draw_stroke_fn"]
    draw_text_fn = ctx["draw_text_fn"]
    load_font_fn = ctx["load_font_fn"]
    style = str(panel_spec.get("style") or "ink_pen")
    mini = bool(layer.get("mini", False))
    is_two = vp.layout == "2x1"
    f_lbl = load_font_fn(int(round((32 if is_two else 42) * vp.scale_y)), expressive_accent=False)

    def _a(b: int) -> int:
        return max(0, min(255, int(round(b * master_alpha))))

    vmin, vmax = _group_domain(groups)
    for idx, g in enumerate(groups):
        cy, slot_h = _group_slot_y(vp, idx, len(groups))
        rgb = PALETTE_GROUPS[idx % len(PALETTE_GROUPS)]
        half_h = slot_h * (0.09 if mini else 0.22)
        x_min = vp.map_x(g["min"], vmin, vmax)
        x_q1 = vp.map_x(g["q1"], vmin, vmax)
        x_med = vp.map_x(g["median"], vmin, vmax)
        x_q3 = vp.map_x(g["q3"], vmin, vmax)
        x_max = vp.map_x(g["max"], vmin, vmax)

        if not mini:
            draw_text_fn(
                canvas,
                (int(round(vp.plot_left + 10 * vp.scale_x)), int(round(cy - half_h - 38 * vp.scale_y))),
                f"{g['label']} (med {_fmt_val(g['median'], g['unit'])})"[:34],
                f_lbl,
                (248, 244, 234, _a(240)),
                halo_alpha=_a(155),
            )

        # Soft translucent box fill
        if progress > 0.2:
            ov = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
            ImageDraw.Draw(ov, "RGBA").rectangle(
                [x_q1, cy - half_h, x_q3, cy + half_h],
                fill=(rgb[0], rgb[1], rgb[2], _a(58 if mini else 82)),
            )
            canvas.alpha_composite(ov)

        u = np.linspace(0.0, 1.0, 28, dtype=np.float32)
        w_box = np.full(len(u), (3.8 if mini else 5.2) * vp.scale, dtype=np.float32)
        # Whiskers
        w_l = np.column_stack([x_min + (x_q1 - x_min) * u, np.full_like(u, cy)]).astype(np.float32)
        w_r = np.column_stack([x_q3 + (x_max - x_q3) * u, np.full_like(u, cy)]).astype(np.float32)
        draw_stroke_fn(canvas, w_l, w_box, rgb, alpha=_a(225), progress=progress, style=style, seed=300 + idx)
        draw_stroke_fn(canvas, w_r, w_box, rgb, alpha=_a(225), progress=progress, style=style, seed=301 + idx)

        # Box top, bottom, left, right
        for s_k, (xa, ya, xb, yb) in enumerate((
            (x_q1, cy - half_h, x_q3, cy - half_h),
            (x_q1, cy + half_h, x_q3, cy + half_h),
            (x_q1, cy - half_h, x_q1, cy + half_h),
            (x_q3, cy - half_h, x_q3, cy + half_h),
        )):
            seg = np.column_stack([xa + (xb - xa) * u, ya + (yb - ya) * u]).astype(np.float32)
            draw_stroke_fn(canvas, seg, w_box, rgb, alpha=_a(245), progress=progress, style=style, seed=310 + idx * 5 + s_k)

        # Thick median line
        w_med = np.full(len(u), (6.2 if mini else 8.0) * vp.scale, dtype=np.float32)
        med_seg = np.column_stack([np.full_like(u, x_med), (cy - half_h) + 2.0 * half_h * u]).astype(np.float32)
        draw_stroke_fn(canvas, med_seg, w_med, (255, 248, 220), alpha=_a(252), progress=progress, style=style, seed=330 + idx)


def render_violin_layer(
    canvas: Image.Image,
    vp: PanelViewport,
    layer: dict[str, Any],
    panel_spec: dict[str, Any],
    *,
    progress: float,
    master_alpha: float,
    ctx: dict[str, Any],
) -> None:
    groups = prepare_group_distributions(layer, seed=int(panel_spec.get("seed") or 101))
    if not groups or progress <= 0.01:
        return
    draw_stroke_fn = ctx["draw_stroke_fn"]
    draw_text_fn = ctx["draw_text_fn"]
    load_font_fn = ctx["load_font_fn"]
    style = str(panel_spec.get("style") or "crayon")
    half = bool(layer.get("half", False))
    is_two = vp.layout == "2x1"
    f_lbl = load_font_fn(int(round((32 if is_two else 42) * vp.scale_y)), expressive_accent=False)

    def _a(b: int) -> int:
        return max(0, min(255, int(round(b * master_alpha))))

    vmin, vmax = _group_domain(groups)
    for idx, g in enumerate(groups):
        cy, slot_h = _group_slot_y(vp, idx, len(groups))
        rgb = PALETTE_GROUPS[idx % len(PALETTE_GROUPS)]
        amp = slot_h * (0.34 if half else 0.28)
        xs = np.asarray([vp.map_x(v, vmin, vmax) for v in g["kde_grid"]], dtype=np.float32)
        dens = np.asarray(g["kde_density"], dtype=np.float32)
        top_ys = cy - dens * amp
        bot_ys = np.full_like(xs, cy) if half else (cy + dens * amp)

        # Translucent polygon fill + hand-sketched diagonal hatching
        n_vis = max(3, int(round(progress * len(xs))))
        poly_pts = [(float(xs[i]), float(top_ys[i])) for i in range(n_vis)] + [
            (float(xs[i]), float(bot_ys[i])) for i in range(n_vis - 1, -1, -1)
        ]
        ov = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        ImageDraw.Draw(ov, "RGBA").polygon(poly_pts, fill=(rgb[0], rgb[1], rgb[2], _a(68)))
        canvas.alpha_composite(ov)

        w_v = np.full(len(xs), 4.8 * vp.scale, dtype=np.float32)
        draw_stroke_fn(canvas, np.column_stack([xs, top_ys]).astype(np.float32), w_v, rgb, alpha=_a(246), progress=progress, style=style, seed=350 + idx)
        if not half:
            draw_stroke_fn(canvas, np.column_stack([xs, bot_ys]).astype(np.float32), w_v, rgb, alpha=_a(236), progress=progress, style=style, seed=360 + idx)

        draw_text_fn(
            canvas,
            (int(round(vp.plot_left + 12 * vp.scale_x)), int(round(cy - amp - 34 * vp.scale_y))),
            f"{g['label']} ({_fmt_val(g['mean'], g['unit'])})"[:34],
            f_lbl,
            (248, 245, 236, _a(242)),
            halo_alpha=_a(155),
        )


def render_points_layer(
    canvas: Image.Image,
    vp: PanelViewport,
    layer: dict[str, Any],
    panel_spec: dict[str, Any],
    *,
    progress: float,
    master_alpha: float,
    ctx: dict[str, Any],
) -> None:
    if progress <= 0.01:
        return
    draw_stroke_fn = ctx["draw_stroke_fn"]
    draw_text_fn = ctx["draw_text_fn"]
    load_font_fn = ctx["load_font_fn"]
    style = str(panel_spec.get("style") or "ink_pen")

    def _a(b: int) -> int:
        return max(0, min(255, int(round(b * master_alpha))))

    if layer.get("marker_mode"):
        curve = evaluate_function_curve(layer)
        xs_c, ys_c = curve["x"], curve["y"]
        xmin, xmax = float(np.min(xs_c)), float(np.max(xs_c))
        ymin, ymax = float(np.min(ys_c)), float(np.max(ys_c))
        f_mk = load_font_fn(int(round(36 * vp.scale_y)), expressive_accent=False)
        for m_i, mk in enumerate(curve.get("markers") or []):
            mx = vp.map_x(float(mk.get("x", 0.0)), xmin, xmax)
            my = vp.map_y(float(mk.get("y", 0.0)), ymin, ymax)
            _draw_hand_circle(
                canvas, mx, my, 10.0 * vp.scale, (255, 218, 98),
                alpha=_a(250), fill_alpha=_a(190), style=style, seed=500 + m_i, scale=vp.scale, draw_stroke_fn=draw_stroke_fn,
            )
            lbl = str(mk.get("label") or "").strip()
            if lbl:
                disp_mk = lbl[:28]
                mk_bb = ImageDraw.Draw(canvas).textbbox((0, 0), disp_mk, font=f_mk)
                mk_tw = mk_bb[2] - mk_bb[0]
                mk_x = max(
                    vp.x_left + int(round(8 * vp.scale_x)),
                    min(vp.x_right - mk_tw - int(round(14 * vp.scale_x)), int(round(mx + 14 * vp.scale_x))),
                )
                draw_text_fn(
                    canvas,
                    (mk_x, int(round(max(vp.plot_top + 6 * vp.scale_y, my - 38 * vp.scale_y)))),
                    disp_mk,
                    f_mk,
                    (255, 238, 148, _a(248)),
                    halo_alpha=_a(170),
                )
        return

    groups = prepare_group_distributions(layer, seed=int(panel_spec.get("seed") or 101))
    vmin, vmax = _group_domain(groups)
    jitter_below = str(layer.get("jitter_side") or "") == "below"
    for idx, g in enumerate(groups):
        cy, slot_h = _group_slot_y(vp, idx, len(groups))
        rgb = PALETTE_GROUPS[idx % len(PALETTE_GROUPS)]
        rng = np.random.default_rng(700 + idx * 31)
        samples = g["samples"]
        n_vis = max(1, int(round(progress * len(samples))))
        for p_i, s_val in enumerate(samples[:n_vis]):
            px = vp.map_x(float(s_val), vmin, vmax)
            jy = float(rng.uniform(0.06 * slot_h, 0.24 * slot_h)) if jitter_below else float(rng.uniform(-0.14 * slot_h, 0.14 * slot_h))
            py = cy + jy
            _draw_hand_circle(
                canvas, px, py, 5.2 * vp.scale, rgb,
                alpha=_a(220), fill_alpha=_a(145), style=style, seed=720 + idx * 50 + p_i, scale=vp.scale, draw_stroke_fn=draw_stroke_fn,
            )


def render_scatter_layer(
    canvas: Image.Image,
    vp: PanelViewport,
    layer: dict[str, Any],
    panel_spec: dict[str, Any],
    *,
    progress: float,
    master_alpha: float,
    ctx: dict[str, Any],
) -> None:
    sc = prepare_scatter_and_regression(layer, seed=int(panel_spec.get("seed") or 101))
    xs, ys = sc["x"], sc["y"]
    if len(xs) == 0 or progress <= 0.01:
        return
    draw_stroke_fn = ctx["draw_stroke_fn"]
    style = str(panel_spec.get("style") or "crayon")

    def _a(b: int) -> int:
        return max(0, min(255, int(round(b * master_alpha))))

    xmin, xmax = float(np.min(xs)), float(np.max(xs))
    ymin, ymax = min(float(np.min(ys)), float(np.min(sc["ci_lo"]))), max(float(np.max(ys)), float(np.max(sc["ci_hi"])))
    n_vis = max(1, int(round(progress * len(xs))))
    for i in range(n_vis):
        px = vp.map_x(float(xs[i]), xmin, xmax)
        py = vp.map_y(float(ys[i]), ymin, ymax)
        _draw_hand_circle(
            canvas, px, py, 6.2 * vp.scale, (92, 206, 255),
            alpha=_a(235), fill_alpha=_a(155), style=style, seed=900 + i, scale=vp.scale, draw_stroke_fn=draw_stroke_fn,
        )


def render_regression_layer(
    canvas: Image.Image,
    vp: PanelViewport,
    layer: dict[str, Any],
    panel_spec: dict[str, Any],
    *,
    progress: float,
    master_alpha: float,
    ctx: dict[str, Any],
) -> None:
    sc = prepare_scatter_and_regression(layer, seed=int(panel_spec.get("seed") or 101))
    if progress <= 0.01:
        return
    draw_stroke_fn = ctx["draw_stroke_fn"]
    draw_text_fn = ctx["draw_text_fn"]
    load_font_fn = ctx["load_font_fn"]
    loop_fn = ctx["loop_fn"]
    style = str(panel_spec.get("style") or "crayon")

    def _a(b: int) -> int:
        return max(0, min(255, int(round(b * master_alpha))))

    xs, ys = sc["x"], sc["y"]
    xmin, xmax = float(np.min(xs)), float(np.max(xs))
    ymin, ymax = min(float(np.min(ys)), float(np.min(sc["ci_lo"]))), max(float(np.max(ys)), float(np.max(sc["ci_hi"])))
    pts = np.column_stack([
        [vp.map_x(float(xv), xmin, xmax) for xv in sc["x_grid"]],
        [vp.map_y(float(yv), ymin, ymax) for yv in sc["y_hat"]],
    ]).astype(np.float32)
    w = np.full(len(pts), 6.8 * vp.scale, dtype=np.float32)
    draw_stroke_fn(canvas, pts, w, (255, 214, 92), alpha=_a(248), progress=progress, style=style, seed=980)

    callout_txt = str(layer.get("callout") or panel_spec.get("multiplier_badge") or "").strip()
    if progress > 0.55 and callout_txt and not callout_txt.lower().startswith("r ="):
        f_c = load_font_fn(int(round(52 * vp.scale_y)), expressive_accent=True)
        bx = vp.plot_left + int(round(36 * vp.scale_x))
        by = vp.plot_top + int(round(20 * vp.scale_y))
        mb = draw_text_fn(canvas, (bx, by), callout_txt[:22], f_c, (255, 232, 118, _a(252)), halo_alpha=_a(175))
        lp, lw = loop_fn(
            (0.5 * (mb[0] + mb[2]), 0.5 * (mb[1] + mb[3])),
            rx=max(44.0 * vp.scale_x, 0.62 * (mb[2] - mb[0]) + 14 * vp.scale_x),
            ry=max(26.0 * vp.scale_y, 0.58 * (mb[3] - mb[1]) + 8 * vp.scale_y),
            scale=vp.scale,
        )
        draw_stroke_fn(canvas, lp, lw, (255, 136, 96), alpha=_a(235), progress=(progress - 0.55) / 0.45, style=style, seed=985)


def render_dot_array_layer(
    canvas: Image.Image,
    vp: PanelViewport,
    layer: dict[str, Any],
    panel_spec: dict[str, Any],
    *,
    progress: float,
    master_alpha: float,
    ctx: dict[str, Any],
) -> None:
    draw_stroke_fn = ctx["draw_stroke_fn"]
    draw_text_fn = ctx["draw_text_fn"]
    load_font_fn = ctx["load_font_fn"]
    style = str(panel_spec.get("style") or "crayon")

    def _a(b: int) -> int:
        return max(0, min(255, int(round(b * master_alpha))))

    params = layer.get("params") if isinstance(layer.get("params"), dict) else {}
    total_n = int(layer.get("total_n") or params.get("n") or 14)
    lit_k = int(layer.get("highlighted_k") or params.get("k") or 1)
    if isinstance(layer.get("bars"), list) and len(layer["bars"]) >= 2:
        v0 = int(round(float(layer["bars"][0].get("value") or 1)))
        v1 = int(round(float(layer["bars"][1].get("value") or 14)))
        lit_k, total_n = min(v0, v1), max(v0, v1)
    total_n = max(2, min(100, total_n))
    lit_k = max(0, min(total_n, lit_k))

    cols = min(10, max(4, int(math.ceil(math.sqrt(total_n * 1.6)))))
    rows = int(math.ceil(total_n / float(cols)))
    cell_w = vp.plot_w / float(cols)
    cell_h = (vp.plot_h * 0.68) / float(max(1, rows))
    rad = min(cell_w, cell_h) * 0.34

    n_vis = max(1, int(round(progress * total_n)))
    for i in range(n_vis):
        r_i = i // cols
        c_i = i % cols
        cx = vp.plot_left + (c_i + 0.5) * cell_w
        cy = vp.plot_top + int(round(28 * vp.scale_y)) + (r_i + 0.5) * cell_h
        is_lit = i < lit_k
        rgb = (68, 228, 162) if is_lit else (142, 148, 162)
        _draw_hand_circle(
            canvas, cx, cy, rad, rgb,
            alpha=_a(250 if is_lit else 185),
            fill_alpha=_a(210 if is_lit else 55),
            style=style,
            seed=600 + i,
            scale=vp.scale,
            draw_stroke_fn=draw_stroke_fn,
        )

    f_big = load_font_fn(int(round((48 if vp.layout == "2x1" else 64) * vp.scale_y)), expressive_accent=True)
    ratio_lbl = str(layer.get("ratio_label") or f"{lit_k} of {total_n} ({100.0 * lit_k / total_n:.1f}%)")
    r_bb = ImageDraw.Draw(canvas).textbbox((0, 0), ratio_lbl, font=f_big)
    r_tw = r_bb[2] - r_bb[0]
    rx_lbl = max(
        vp.x_left + int(round(8 * vp.scale_x)),
        min(vp.x_right - r_tw - int(round(14 * vp.scale_x)), vp.plot_left + int(round(18 * vp.scale_x))),
    )
    draw_text_fn(
        canvas,
        (rx_lbl, vp.plot_bot - int(round(62 * vp.scale_y))),
        ratio_lbl,
        f_big,
        (255, 232, 118, _a(252)),
        halo_alpha=_a(180),
    )


def render_arc_gauge_layer(
    canvas: Image.Image,
    vp: PanelViewport,
    layer: dict[str, Any],
    panel_spec: dict[str, Any],
    *,
    progress: float,
    master_alpha: float,
    ctx: dict[str, Any],
) -> None:
    draw_stroke_fn = ctx["draw_stroke_fn"]
    draw_text_fn = ctx["draw_text_fn"]
    load_font_fn = ctx["load_font_fn"]
    style = str(panel_spec.get("style") or "crayon")

    def _a(b: int) -> int:
        return max(0, min(255, int(round(b * master_alpha))))

    pct = float(layer.get("percent") or layer.get("value") or 0.0)
    if pct <= 0.0 and isinstance(layer.get("bars"), list) and layer["bars"]:
        pct = max(float(b.get("value") or 0.0) for b in layer["bars"] if isinstance(b, dict))
    pct = max(1.0, min(100.0, pct))

    cx = 0.5 * (vp.plot_left + vp.plot_right)
    cy = 0.5 * (vp.plot_top + vp.plot_bot)
    rad = min(vp.plot_w, vp.plot_h) * 0.38

    # Background muted track arc
    u_bg = np.linspace(0.0, 1.0, 72, dtype=np.float32)
    ang_bg = -0.5 * math.pi + 2.0 * math.pi * u_bg
    pts_bg = np.column_stack([cx + rad * np.cos(ang_bg), cy + rad * np.sin(ang_bg)]).astype(np.float32)
    w_bg = np.full(len(u_bg), 16.0 * vp.scale, dtype=np.float32)
    draw_stroke_fn(canvas, pts_bg, w_bg, (112, 120, 136), alpha=_a(115), progress=1.0, style=style, seed=650)

    # Foreground progressive arc
    target_frac = (pct / 100.0) * progress
    ang_fg = -0.5 * math.pi + 2.0 * math.pi * target_frac * u_bg
    pts_fg = np.column_stack([cx + rad * np.cos(ang_fg), cy + rad * np.sin(ang_fg)]).astype(np.float32)
    w_fg = np.full(len(u_bg), 24.0 * vp.scale, dtype=np.float32)
    draw_stroke_fn(canvas, pts_fg, w_fg, (68, 228, 162), alpha=_a(248), progress=1.0, style=style, seed=651)

    f_pct = load_font_fn(int(round((62 if vp.layout == "2x1" else 92) * vp.scale_y)), expressive_accent=True)
    cur_txt = f"{pct * progress:.0f}%"
    tb = ImageDraw.Draw(canvas).textbbox((0, 0), cur_txt, font=f_pct)
    draw_text_fn(
        canvas,
        (int(round(cx - 0.5 * (tb[2] - tb[0]))), int(round(cy - 0.55 * (tb[3] - tb[1])))),
        cur_txt,
        f_pct,
        (255, 248, 224, _a(254)),
        halo_alpha=_a(185),
    )


def render_slope_layer(
    canvas: Image.Image,
    vp: PanelViewport,
    layer: dict[str, Any],
    panel_spec: dict[str, Any],
    *,
    progress: float,
    master_alpha: float,
    ctx: dict[str, Any],
) -> None:
    groups = prepare_group_distributions(layer, seed=int(panel_spec.get("seed") or 101))
    if len(groups) < 2 or progress <= 0.01:
        return
    draw_stroke_fn = ctx["draw_stroke_fn"]
    draw_text_fn = ctx["draw_text_fn"]
    load_font_fn = ctx["load_font_fn"]
    style = str(panel_spec.get("style") or "crayon")

    def _a(b: int) -> int:
        return max(0, min(255, int(round(b * master_alpha))))

    g0, g1 = groups[0], groups[-1]
    v0, v1 = float(g0["mean"]), float(g1["mean"])
    vmin = min(v0, v1) - 0.18 * max(1.0, abs(v1 - v0))
    vmax = max(v0, v1) + 0.22 * max(1.0, abs(v1 - v0))
    x0 = float(vp.plot_left + 75 * vp.scale_x)
    x1 = float(vp.plot_right - 95 * vp.scale_x)
    y0 = vp.map_y(v0, vmin, vmax)
    y1 = vp.map_y(v1, vmin, vmax)

    u = np.linspace(0.0, 1.0, 52, dtype=np.float32)
    pts = np.column_stack([
        x0 + (x1 - x0) * u,
        y0 + (y1 - y0) * u + (2.5 * vp.scale_y) * np.sin(np.pi * u),
    ]).astype(np.float32)
    w = np.full(len(u), 9.0 * vp.scale, dtype=np.float32)
    draw_stroke_fn(canvas, pts, w, (68, 228, 162), alpha=_a(248), progress=progress, style=style, seed=770)

    _draw_hand_circle(canvas, x0, y0, 12.0 * vp.scale, (238, 114, 104), alpha=_a(250), fill_alpha=_a(200), style=style, seed=771, scale=vp.scale, draw_stroke_fn=draw_stroke_fn)
    if progress > 0.7:
        _draw_hand_circle(canvas, x1, y1, 13.0 * vp.scale, (68, 228, 162), alpha=_a(252), fill_alpha=_a(210), style=style, seed=772, scale=vp.scale, draw_stroke_fn=draw_stroke_fn)

    f_lbl = load_font_fn(int(round((38 if vp.layout == "2x1" else 48) * vp.scale_y)), expressive_accent=False)
    probe_sl = ImageDraw.Draw(canvas)
    s0_txt = f"{g0['label']}: {_fmt_val(v0, g0['unit'])}"[:26]
    s1_txt = f"{g1['label']}: {_fmt_val(v1, g1['unit'])}"[:26]
    s0_w = probe_sl.textbbox((0, 0), s0_txt, font=f_lbl)[2]
    s1_w = probe_sl.textbbox((0, 0), s1_txt, font=f_lbl)[2]
    s0_x = max(vp.x_left + int(round(8 * vp.scale_x)), min(vp.x_right - s0_w - int(round(14 * vp.scale_x)), int(round(x0 - 35 * vp.scale_x))))
    s1_x = max(vp.x_left + int(round(8 * vp.scale_x)), min(vp.x_right - s1_w - int(round(14 * vp.scale_x)), int(round(x1 - 0.5 * s1_w))))
    draw_text_fn(canvas, (s0_x, int(round(y0 - 56 * vp.scale_y))), s0_txt, f_lbl, (248, 244, 234, _a(248)), halo_alpha=_a(170))
    draw_text_fn(canvas, (s1_x, int(round(y1 - 56 * vp.scale_y))), s1_txt, f_lbl, (255, 252, 240, _a(252)), halo_alpha=_a(175))


def compute_line_label_layout(
    vp: PanelViewport,
    vals: list[float],
    xs: np.ndarray,
    ys: np.ndarray,
    *,
    start_bbox: tuple[int, int, int, int],
    mid_bbox: tuple[int, int, int, int] | None,
    end_bbox: tuple[int, int, int, int],
) -> dict[str, tuple[int, int]]:
    """
    Computes dot- and stroke-cleared `(x, y)` origins for line-chart point labels so
    ascending trajectories place low start/mid labels below points cleanly and peak end
    labels sit `>= 18px` (scaled) above end dots with zero line-segment intersection.
    """
    is_asc = len(vals) >= 2 and float(ys[1]) < float(ys[0])
    is_end_peak = len(vals) < 2 or float(ys[-1]) <= float(ys[-2])
    st_w = max(1, start_bbox[2] - start_bbox[0])
    en_w = max(1, end_bbox[2] - end_bbox[0])

    st_x = max(
        vp.x_left + int(round(8 * vp.scale_x)),
        min(vp.x_right - st_w - int(round(14 * vp.scale_x)), int(round(float(xs[0]) - 10 * vp.scale_x))),
    )
    if is_asc:
        st_top_ink = float(ys[0]) + 10.5 * vp.scale + 18.0 * vp.scale_y
        st_y = min(
            int(round(vp.plot_bot - 6 * vp.scale_y - start_bbox[3])),
            int(round(st_top_ink - start_bbox[1])),
        )
    else:
        st_bot_ink = float(ys[0]) - 10.5 * vp.scale - 18.0 * vp.scale_y
        st_y = max(
            int(round(vp.plot_top + 4 * vp.scale_y - start_bbox[1])),
            int(round(st_bot_ink - start_bbox[3])),
        )

    out: dict[str, tuple[int, int]] = {"start": (int(st_x), int(st_y))}

    if mid_bbox is not None and len(xs) >= 3:
        mid_w = max(1, mid_bbox[2] - mid_bbox[0])
        mid_x = max(
            vp.x_left + int(round(8 * vp.scale_x)),
            min(vp.x_right - mid_w - int(round(14 * vp.scale_x)), int(round(float(xs[1]) + 22 * vp.scale_x))),
        )
        if float(ys[-1]) <= float(ys[0]):
            mid_top_ink = float(ys[1]) + 10.5 * vp.scale + 16.0 * vp.scale_y
            mid_y = min(
                int(round(vp.plot_bot - 6 * vp.scale_y - mid_bbox[3])),
                int(round(mid_top_ink - mid_bbox[1])),
            )
        else:
            mid_bot_ink = float(ys[1]) - 10.5 * vp.scale - 16.0 * vp.scale_y
            mid_y = max(
                int(round(vp.plot_top + 4 * vp.scale_y - mid_bbox[1])),
                int(round(mid_bot_ink - mid_bbox[3])),
            )
        out["mid"] = (int(mid_x), int(mid_y))

    en_x = max(
        vp.x_left + int(round(8 * vp.scale_x)),
        min(vp.x_right - en_w - int(round(14 * vp.scale_x)), int(round(float(xs[-1]) - en_w + 18 * vp.scale_x))),
    )
    if is_end_peak:
        en_bot_ink = float(ys[-1]) - 11.5 * vp.scale - 18.0 * vp.scale_y
        en_y = max(
            int(round(vp.plot_top + 4 * vp.scale_y - end_bbox[1])),
            int(round(en_bot_ink - end_bbox[3])),
        )
    else:
        en_top_ink = float(ys[-1]) + 11.5 * vp.scale + 18.0 * vp.scale_y
        en_y = min(
            int(round(vp.plot_bot - 6 * vp.scale_y - end_bbox[3])),
            int(round(en_top_ink - end_bbox[1])),
        )
    out["end"] = (int(en_x), int(en_y))
    return out


def render_line_layer(
    canvas: Image.Image,
    vp: PanelViewport,
    layer: dict[str, Any],
    panel_spec: dict[str, Any],
    *,
    progress: float,
    master_alpha: float,
    ctx: dict[str, Any],
) -> None:
    draw_stroke_fn = ctx["draw_stroke_fn"]
    draw_text_fn = ctx["draw_text_fn"]
    load_font_fn = ctx["load_font_fn"]
    style = str(panel_spec.get("style") or "crayon")

    def _a(b: int) -> int:
        return max(0, min(255, int(round(b * master_alpha))))

    series = layer.get("series")
    if not isinstance(series, list) or not series:
        groups = prepare_group_distributions(layer, seed=int(panel_spec.get("seed") or 101))
        series = [
            {
                "label": str(groups[-1]["label"]) if groups else "After",
                "start_label": str(groups[0]["label"]) if groups else "Before",
                "point_labels": [str(g["label"]) for g in groups],
                "values": [float(g["mean"]) for g in groups],
                "unit": str(groups[0].get("unit") or panel_spec.get("unit") or "") if groups else "",
            }
        ]

    all_vals = [float(v) for s in series if isinstance(s, dict) for v in (s.get("values") or [0.0, 1.0])]
    vmin, vmax = (min(all_vals), max(all_vals)) if all_vals else (0.0, 10.0)
    span = max(1.0, vmax - vmin)
    vmin -= 0.24 * span
    vmax += 0.25 * span

    if vmin < 0.0 < vmax and progress > 0.02:
        y_zero = vp.map_y(0.0, vmin, vmax)
        z_xs = np.linspace(vp.plot_left + 28 * vp.scale_x, vp.plot_right - 44 * vp.scale_x, 36, dtype=np.float32)
        z_pts = np.column_stack([z_xs, np.full(len(z_xs), y_zero, dtype=np.float32)]).astype(np.float32)
        draw_stroke_fn(canvas, z_pts, np.full(len(z_xs), 2.8 * vp.scale, dtype=np.float32), (188, 200, 218), alpha=_a(135), progress=min(1.0, progress * 1.4), style=style, seed=805)

    f_lbl = load_font_fn(int(round(44 * vp.scale_y)), expressive_accent=False)
    for s_i, s in enumerate(series[:2]):
        if not isinstance(s, dict):
            continue
        vals = [float(v) for v in (s.get("values") or [1.0, 2.0])]
        if len(vals) < 2:
            vals = [vals[0], vals[0] * 1.5]
        s_unit = str(s.get("unit") if "unit" in s else (panel_spec.get("unit") or "")).strip()
        rgb = PALETTE_GROUPS[(s_i + 1) % len(PALETTE_GROUPS)]
        xs = np.linspace(vp.plot_left + 44 * vp.scale_x, vp.plot_right - 64 * vp.scale_x, len(vals))
        ys = np.asarray([vp.map_y(v, vmin, vmax) for v in vals], dtype=np.float32)
        u_dense = np.linspace(0.0, len(vals) - 1, 64)
        px = np.interp(u_dense, np.arange(len(vals)), xs)
        py = np.interp(u_dense, np.arange(len(vals)), ys)
        w = np.full(len(u_dense), 7.8 * vp.scale, dtype=np.float32)
        draw_stroke_fn(canvas, np.column_stack([px, py]).astype(np.float32), w, rgb, alpha=_a(248), progress=progress, style=style, seed=810 + s_i)

        probe_ln = ImageDraw.Draw(canvas)
        start_lbl = str(s.get("start_label") or "").strip()
        start_txt = (f"{start_lbl}: {_fmt_val(vals[0], s_unit)}" if start_lbl else _fmt_val(vals[0], s_unit))[:30]
        start_bbox = probe_ln.textbbox((0, 0), start_txt, font=f_lbl)

        pt_labels = s.get("point_labels") if isinstance(s.get("point_labels"), list) else []
        show_mid = len(series) == 1 and len(vals) == 3 and progress > 0.45
        mid_txt = ""
        mid_bbox: tuple[int, int, int, int] | None = None
        if show_mid:
            mid_lbl = str(pt_labels[1]).strip() if len(pt_labels) > 1 else ""
            mid_txt = (f"{mid_lbl}: {_fmt_val(vals[1], s_unit)}" if mid_lbl else _fmt_val(vals[1], s_unit))[:30]
            mid_bbox = probe_ln.textbbox((0, 0), mid_txt, font=f_lbl)

        end_lbl = str(s.get("label") or "").strip()
        end_txt = (f"{end_lbl}: {_fmt_val(vals[-1], s_unit)}" if end_lbl else _fmt_val(vals[-1], s_unit))[:30]
        end_bbox = probe_ln.textbbox((0, 0), end_txt, font=f_lbl)

        layout = compute_line_label_layout(
            vp,
            vals,
            xs,
            ys,
            start_bbox=start_bbox,
            mid_bbox=mid_bbox,
            end_bbox=end_bbox,
        )

        # Draw start dot and start value label
        _draw_hand_circle(canvas, float(xs[0]), float(ys[0]), 10.5 * vp.scale, (238, 114, 104) if len(series) == 1 else rgb, alpha=_a(250), fill_alpha=_a(205), style=style, seed=820 + s_i, scale=vp.scale, draw_stroke_fn=draw_stroke_fn)
        draw_text_fn(
            canvas,
            layout["start"],
            start_txt,
            f_lbl,
            (248, 244, 234, _a(248)),
            halo_alpha=_a(170),
        )

        # Draw middle point dot & non-overlapping value label for 3-point trajectory
        if show_mid and "mid" in layout:
            _draw_hand_circle(canvas, float(xs[1]), float(ys[1]), 10.5 * vp.scale, (255, 204, 96), alpha=_a(250), fill_alpha=_a(205), style=style, seed=825 + s_i, scale=vp.scale, draw_stroke_fn=draw_stroke_fn)
            draw_text_fn(
                canvas,
                layout["mid"],
                mid_txt,
                f_lbl,
                (255, 246, 214, _a(250)),
                halo_alpha=_a(175),
            )

        # Draw end dot and end value label
        if progress > 0.72:
            _draw_hand_circle(canvas, float(xs[-1]), float(ys[-1]), 11.5 * vp.scale, rgb, alpha=_a(252), fill_alpha=_a(215), style=style, seed=830 + s_i, scale=vp.scale, draw_stroke_fn=draw_stroke_fn)
            draw_text_fn(
                canvas,
                layout["end"],
                end_txt,
                f_lbl,
                (255, 250, 236, _a(252)),
                halo_alpha=_a(175),
            )


def render_band_layer(
    canvas: Image.Image,
    vp: PanelViewport,
    layer: dict[str, Any],
    panel_spec: dict[str, Any],
    *,
    progress: float,
    master_alpha: float,
    ctx: dict[str, Any],
) -> None:
    if progress <= 0.01:
        return
    draw_stroke_fn = ctx["draw_stroke_fn"]
    draw_text_fn = ctx["draw_text_fn"]
    load_font_fn = ctx["load_font_fn"]
    style = str(panel_spec.get("style") or "crayon")

    def _a(b: int) -> int:
        return max(0, min(255, int(round(b * master_alpha))))

    band_mode = str(layer.get("band_mode") or "line_ci")
    if band_mode == "regression_ci":
        sc = prepare_scatter_and_regression(layer, seed=int(panel_spec.get("seed") or 101))
        xs, ys = sc["x"], sc["y"]
        xmin, xmax = float(np.min(xs)), float(np.max(xs))
        ymin, ymax = min(float(np.min(ys)), float(np.min(sc["ci_lo"]))), max(float(np.max(ys)), float(np.max(sc["ci_hi"])))
        gx = [vp.map_x(float(xv), xmin, xmax) for xv in sc["x_grid"]]
        ylo = [vp.map_y(float(yv), ymin, ymax) for yv in sc["ci_lo"]]
        yhi = [vp.map_y(float(yv), ymin, ymax) for yv in sc["ci_hi"]]
        n_vis = max(3, int(round(progress * len(gx))))
        poly = [(gx[i], yhi[i]) for i in range(n_vis)] + [(gx[i], ylo[i]) for i in range(n_vis - 1, -1, -1)]
        ov = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        ImageDraw.Draw(ov, "RGBA").polygon(poly, fill=(255, 214, 92, _a(52)))
        canvas.alpha_composite(ov)
        return

    if band_mode == "range_bars":
        groups = prepare_group_distributions(layer, seed=int(panel_spec.get("seed") or 101))
        vmin, vmax = _group_domain(groups)
        f_lbl = load_font_fn(int(round(40 * vp.scale_y)), expressive_accent=False)
        for idx, g in enumerate(groups):
            cy, _ = _group_slot_y(vp, idx, len(groups))
            x_lo = vp.map_x(g["min"], vmin, vmax)
            x_hi = vp.map_x(g["max"], vmin, vmax)
            u = np.linspace(0.0, 1.0, 40, dtype=np.float32)
            pts = np.column_stack([x_lo + (x_hi - x_lo) * u, np.full_like(u, cy)]).astype(np.float32)
            w = np.full(len(u), 24.0 * vp.scale, dtype=np.float32)
            rgb = PALETTE_GROUPS[idx % len(PALETTE_GROUPS)]
            draw_stroke_fn(canvas, pts, w, rgb, alpha=_a(210), progress=progress, style=style, seed=840 + idx)
            draw_text_fn(
                canvas,
                (int(round(x_lo)), int(round(cy - 44 * vp.scale_y))),
                f"{g['label']}: {_fmt_val(g['min'])}–{_fmt_val(g['max'], g['unit'])}"[:32],
                f_lbl,
                (255, 250, 236, _a(246)),
                halo_alpha=_a(165),
            )
        return

    # Default line CI band
    groups = prepare_group_distributions(layer, seed=int(panel_spec.get("seed") or 101))
    vmin, vmax = _group_domain(groups)
    xs = np.linspace(vp.plot_left + 18 * vp.scale_x, vp.plot_right - 36 * vp.scale_x, max(2, len(groups)))
    ylo = [vp.map_y(float(g["error_lo"]), vmin, vmax) for g in groups]
    yhi = [vp.map_y(float(g["error_hi"]), vmin, vmax) for g in groups]
    poly = [(float(xs[i]), float(yhi[i])) for i in range(len(xs))] + [(float(xs[i]), float(ylo[i])) for i in range(len(xs) - 1, -1, -1)]
    ov = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    ImageDraw.Draw(ov, "RGBA").polygon(poly, fill=(68, 228, 162, _a(54)))
    canvas.alpha_composite(ov)


def render_histogram_layer(
    canvas: Image.Image,
    vp: PanelViewport,
    layer: dict[str, Any],
    panel_spec: dict[str, Any],
    *,
    progress: float,
    master_alpha: float,
    ctx: dict[str, Any],
) -> None:
    groups = prepare_group_distributions(layer, seed=int(panel_spec.get("seed") or 101))
    if not groups or progress <= 0.01:
        return
    draw_stroke_fn = ctx["draw_stroke_fn"]
    style = str(panel_spec.get("style") or "crayon")

    def _a(b: int) -> int:
        return max(0, min(255, int(round(b * master_alpha))))

    samples = np.concatenate([g["samples"] for g in groups])
    counts, edges = np.histogram(samples, bins=10)
    max_c = max(1, int(np.max(counts)))
    bin_w = vp.plot_w / float(len(counts))
    u = np.linspace(0.0, 1.0, 28, dtype=np.float32)
    for b_i, c in enumerate(counts):
        bx = vp.plot_left + (b_i + 0.5) * bin_w
        bh = vp.plot_h * 0.82 * (float(c) / max_c) * progress
        pts = np.column_stack([np.full_like(u, bx), vp.plot_bot - bh * u]).astype(np.float32)
        w = np.full(len(u), max(8.0, bin_w * 0.68), dtype=np.float32)
        draw_stroke_fn(canvas, pts, w, (92, 206, 255), alpha=_a(195), progress=1.0, style=style, seed=860 + b_i)


def render_density_layer(
    canvas: Image.Image,
    vp: PanelViewport,
    layer: dict[str, Any],
    panel_spec: dict[str, Any],
    *,
    progress: float,
    master_alpha: float,
    ctx: dict[str, Any],
) -> None:
    groups = prepare_group_distributions(layer, seed=int(panel_spec.get("seed") or 101))
    if not groups or progress <= 0.01:
        return
    draw_stroke_fn = ctx["draw_stroke_fn"]
    style = str(panel_spec.get("style") or "ink_pen")

    def _a(b: int) -> int:
        return max(0, min(255, int(round(b * master_alpha))))

    samples = np.concatenate([g["samples"] for g in groups])
    grid, dens = compute_kde_profile(samples, n_grid=64)
    vmin, vmax = float(np.min(grid)), float(np.max(grid))
    xs = [vp.map_x(float(v), vmin, vmax) for v in grid]
    ys = [vp.plot_bot - float(d) * (vp.plot_h * 0.84) for d in dens]
    pts = np.column_stack([xs, ys]).astype(np.float32)
    w = np.full(len(pts), 6.8 * vp.scale, dtype=np.float32)
    draw_stroke_fn(canvas, pts, w, (255, 214, 92), alpha=_a(248), progress=progress, style=style, seed=880)


def render_function_curve_layer(
    canvas: Image.Image,
    vp: PanelViewport,
    layer: dict[str, Any],
    panel_spec: dict[str, Any],
    *,
    progress: float,
    master_alpha: float,
    ctx: dict[str, Any],
) -> None:
    curve = evaluate_function_curve(layer)
    if progress <= 0.01:
        return
    draw_stroke_fn = ctx["draw_stroke_fn"]
    style = str(panel_spec.get("style") or "ink_pen")

    def _a(b: int) -> int:
        return max(0, min(255, int(round(b * master_alpha))))

    xs_c, ys_c = curve["x"], curve["y"]
    xmin, xmax = float(np.min(xs_c)), float(np.max(xs_c))
    ymin, ymax = float(np.min(ys_c)), float(np.max(ys_c))
    pts = np.column_stack([
        [vp.map_x(float(xv), xmin, xmax) for xv in xs_c],
        [vp.map_y(float(yv), ymin, ymax) for yv in ys_c],
    ]).astype(np.float32)
    w = np.full(len(pts), 7.4 * vp.scale, dtype=np.float32)
    draw_stroke_fn(canvas, pts, w, (68, 228, 162), alpha=_a(250), progress=progress, style=style, seed=940)


LAYER_DISPATCH = {
    "bar": render_bar_layer,
    "error": render_error_layer,
    "box": render_box_layer,
    "violin": render_violin_layer,
    "points": render_points_layer,
    "scatter": render_scatter_layer,
    "regression": render_regression_layer,
    "dot_array": render_dot_array_layer,
    "arc_gauge": render_arc_gauge_layer,
    "slope": render_slope_layer,
    "line": render_line_layer,
    "band": render_band_layer,
    "histogram": render_histogram_layer,
    "density": render_density_layer,
    "function_curve": render_function_curve_layer,
}
