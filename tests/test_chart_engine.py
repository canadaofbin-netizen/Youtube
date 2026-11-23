"""
Unit tests for the R70-M v3.1 Intuitive Hand-Drawn Chart Engine (`pipeline/charts/`).
"""

from __future__ import annotations

import numpy as np

from pipeline.charts import (
    compute_stamp_complexity_and_hold_sec,
    evaluate_function_curve,
    expand_preset_to_layers,
    is_legacy_bar_compare_only,
    parse_chart_spec,
    prepare_scatter_and_regression,
    route_chart_for_stat,
)
from pipeline.config import (
    DATA_STAMP_BANNED_PRESETS,
    DATA_STAMP_LAYER_TYPES,
    DATA_STAMP_MAX_PANELS,
    DATA_STAMP_MAX_PER_EPISODE,
    DATA_STAMP_MODES,
    DATA_STAMP_PRESETS,
)
from pipeline.data_stamp_overlay import render_data_stamp_rgba_frame


def test_r70m_v31_intuitive_diet_constants_and_routing() -> None:
    assert DATA_STAMP_MAX_PER_EPISODE == 2
    assert DATA_STAMP_MAX_PANELS == 1
    assert DATA_STAMP_MODES == ("study", "illustrative")
    assert set(DATA_STAMP_PRESETS) == {
        "bar_compare",
        "arc_gauge",
        "dot_array",
        "line",
        "curve_marker",
        "scatter_fit",
    }
    assert set(DATA_STAMP_PRESETS).isdisjoint(set(DATA_STAMP_BANNED_PRESETS))

    assert route_chart_for_stat("group_means") == "bar_compare"
    assert route_chart_for_stat("single_percent") == "arc_gauge"
    assert route_chart_for_stat("count_of_n") == "dot_array"
    assert route_chart_for_stat("before_after") == "line"
    assert route_chart_for_stat("timeseries") == "line"
    assert route_chart_for_stat("correlation_r") == "scatter_fit"
    assert route_chart_for_stat("math_function") == "curve_marker"

    sf_layers = expand_preset_to_layers({"preset": "scatter_fit"})
    assert [l["type"] for l in sf_layers] == ["scatter", "regression"]

    ln_layers = expand_preset_to_layers({"preset": "line"})
    assert [l["type"] for l in ln_layers] == ["line"]


def test_scatter_regression_and_function_curves() -> None:
    sc = prepare_scatter_and_regression({"r": 0.79, "n": 48}, seed=77)
    assert abs(sc["r"] - 0.79) <= 0.01
    assert len(sc["x"]) == 48

    for fn_name in ("exp_decay", "sigmoid", "normal_pdf", "prospect_value", "inverted_u", "power", "log", "linear"):
        curve = evaluate_function_curve({"fn": fn_name})
        assert len(curve["x"]) == 96
        assert len(curve["y"]) == 96


def test_all_intuitive_presets_and_layers_render_and_protect_subtitle_zone() -> None:
    W, H = 540, 960
    sub_y0 = int(round(H * 0.68))

    for preset in DATA_STAMP_PRESETS:
        stamp = {
            "sentence_index": 3,
            "mode": "illustrative" if preset == "curve_marker" else "study",
            "preset": preset,
            "style": "crayon",
            "title": f"Preset {preset}",
            "concept": "Cognitive curve" if preset == "curve_marker" else "",
            "doi": "" if preset == "curve_marker" else "10.1016/j.cognition.2012.08.004",
            "source_citation": "Kidd et al. (2013)",
            "groups": [
                {"label": "Unreliable", "mean": 3.0, "value": 3.0, "unit": "min"},
                {"label": "Reliable", "mean": 12.0, "value": 12.0, "unit": "min"},
            ],
            "bars": [
                {"label": "Unreliable", "value": 3.0, "unit": "min"},
                {"label": "Reliable", "value": 12.0, "unit": "min"},
            ],
            "percent": 86.0,
            "highlighted_k": 9,
            "total_n": 14,
            "r": 0.78,
            "fn": "inverted_u",
        }
        im = render_data_stamp_rgba_frame(stamp, t_rel=3.8, total_dur=4.5, width=W, height=H)
        arr = np.asarray(im, dtype=np.uint8)
        assert arr.shape == (H, W, 4)
        assert int(np.count_nonzero(arr[:sub_y0, :, 3] > 20)) > 800, f"Preset {preset} rendered empty upper canvas"
        assert int(np.max(arr[sub_y0:, :, 3])) == 0, f"Preset {preset} leaked pixels into Y >= 68% subtitle zone"

    for l_type in DATA_STAMP_LAYER_TYPES:
        stamp_l = {
            "sentence_index": 2,
            "mode": "illustrative",
            "title": f"Layer {l_type}",
            "concept": f"Testing {l_type}",
            "layers": [{"type": l_type, "fn": "sigmoid", "r": 0.72, "percent": 74.0}],
        }
        im_l = render_data_stamp_rgba_frame(stamp_l, t_rel=3.6, total_dur=4.2, width=W, height=H)
        arr_l = np.asarray(im_l, dtype=np.uint8)
        assert int(np.count_nonzero(arr_l[:sub_y0, :, 3] > 20)) > 400, f"Layer {l_type} rendered empty"
        assert int(np.max(arr_l[sub_y0:, :, 3])) == 0


def test_single_panel_1x1_enforcement_and_deterministic_seed() -> None:
    W, H = 540, 960
    sub_y0 = int(round(H * 0.68))
    stamp = {
        "sentence_index": 5,
        "mode": "illustrative",
        "preset": "curve_marker",
        "title": "Arousal vs Focus Curve",
        "concept": "Yerkes-Dodson inverted-U",
        "fn": "inverted_u",
        "seed": 404,
    }
    spec = parse_chart_spec(stamp)
    assert spec["layout"] == "1x1"
    assert len(spec["panels"]) == 1
    assert spec["panels"][0]["badge_tag"] == "Concept"
    comp, hold = compute_stamp_complexity_and_hold_sec(stamp)
    assert comp >= 1
    assert hold >= 3.2

    im1 = render_data_stamp_rgba_frame(stamp, t_rel=3.8, total_dur=4.5, width=W, height=H)
    im2 = render_data_stamp_rgba_frame(stamp, t_rel=3.8, total_dur=4.5, width=W, height=H)
    a1 = np.asarray(im1, dtype=np.uint8)
    a2 = np.asarray(im2, dtype=np.uint8)
    assert np.array_equal(a1, a2)
    assert int(np.max(a1[sub_y0:, :, 3])) == 0


def test_legacy_bar_compare_detection() -> None:
    legacy = {
        "sentence_index": 4,
        "chart": "bar_compare",
        "title": "Marshmallow Wait Time",
        "bars": [
            {"label": "Broken Promise", "value": 3, "unit": "min"},
            {"label": "Kept Promise", "value": 12, "unit": "min"},
        ],
        "doi": "10.1016/j.cognition.2012.08.004",
        "source_citation": "Kidd et al. (2013)",
    }
    assert is_legacy_bar_compare_only(legacy) is True
    non_legacy = {**legacy, "preset": "line"}
    assert is_legacy_bar_compare_only(non_legacy) is False


def test_signed_bar_compare_three_point_line_and_hundredths_fmt() -> None:
    from pipeline.charts.layers import _display_unit, _fmt_val
    from pipeline.data_stamp_overlay import _format_num

    assert _display_unit("uV^2") == "\u03bcV\u00b2"
    assert _fmt_val(0.08, "uV^2") == "0.08 \u03bcV\u00b2"
    assert _fmt_val(5.53, "uV^2") == "5.53 \u03bcV\u00b2"
    assert _fmt_val(-11.51, "%") == "-11.51 %"
    assert _fmt_val(3.5, "x") == "3.5 x"
    assert _fmt_val(12.0, "min") == "12 min"
    assert _format_num(0.08, False, 2) == "0.08"
    assert _format_num(5.53, False, 2) == "5.53"

    W, H = 540, 960
    sub_y0 = int(round(H * 0.68))

    st_leg = {
        "sentence_index": 13,
        "mode": "study",
        "preset": "bar_compare",
        "chart": "bar_compare",
        "style": "crayon",
        "format": "group_means",
        "title": "45 dB Sound Spindle Boost",
        "unit": "uV^2",
        "bars": [
            {"label": "Large Pupil", "value": 0.08, "unit": "uV^2"},
            {"label": "Small Pupil", "value": 5.53, "unit": "uV^2"},
        ],
        "doi": "10.1038/s41467-025-57289-5",
        "source_citation": "Carro-Domínguez et al. (2025)",
    }
    assert is_legacy_bar_compare_only(st_leg) is True
    im_leg = render_data_stamp_rgba_frame(st_leg, t_rel=3.0, total_dur=3.4, width=W, height=H)
    arr_leg = np.asarray(im_leg, dtype=np.uint8)
    assert int(np.count_nonzero(arr_leg[:sub_y0, :, 3] > 20)) > 800
    assert int(np.max(arr_leg[sub_y0:, :, 3])) == 0

    st_line = {
        "sentence_index": 8,
        "mode": "study",
        "preset": "line",
        "style": "crayon",
        "title": "Sleep Pupil Shift in Darkness",
        "unit": "%",
        "groups": [
            {"label": "Pre-Spindle", "value": -11.51, "unit": "%"},
            {"label": "N2 K-Complex", "value": 13.49, "unit": "%"},
            {"label": "Sleep Arousal", "value": 35.37, "unit": "%"},
        ],
        "doi": "10.1038/s41467-025-57289-5",
        "source_citation": "Carro-Domínguez et al. (2025)",
    }
    im_line = render_data_stamp_rgba_frame(st_line, t_rel=3.8, total_dur=4.5, width=W, height=H)
    arr_line = np.asarray(im_line, dtype=np.uint8)
    assert int(np.count_nonzero(arr_line[:sub_y0, :, 3] > 20)) > 800
    assert int(np.max(arr_line[sub_y0:, :, 3])) == 0

    st_div = dict(st_line, preset="bar_compare", chart="bar_compare")
    im_div = render_data_stamp_rgba_frame(st_div, t_rel=3.8, total_dur=4.5, width=W, height=H)
    arr_div = np.asarray(im_div, dtype=np.uint8)
    assert int(np.count_nonzero(arr_div[:sub_y0, :, 3] > 20)) > 800
    assert int(np.max(arr_div[sub_y0:, :, 3])) == 0


def test_to_display_text_converts_spelled_decimals_and_percents() -> None:
    from pipeline.plain_language import to_display_text

    line1 = (
        "Pupils shrank minus eleven point five one percent, rose thirteen point four nine, "
        "then thirty-five point three seven."
    )
    out1 = to_display_text(line1)
    assert "-11.51%" in out1
    assert "13.49" in out1
    assert "35.37" in out1
    assert "point five" not in out1.lower()

    out2 = to_display_text("five point five three versus point zero eight")
    assert out2 == "5.53 versus 0.08"
    assert to_display_text("zero point zero eight percent") == "0.08%"


def test_line_and_legacy_bar_zero_stroke_collision() -> None:
    from PIL import Image, ImageDraw
    from pipeline.charts.axes import build_panel_viewport
    from pipeline.charts.layers import compute_line_label_layout
    from pipeline.data_stamp_overlay import (
        _load_hand_font,
        compute_natural_arrow_geometry,
        resolve_multiplier_badge_placement,
    )

    # 1. Ascending 3-point line (-11.51 -> 13.49 -> 35.37): >= 14px clearance from segments & dots
    vp = build_panel_viewport(1080, 1920, layout="1x1", panel_index=0)
    vals = [-11.51, 13.49, 35.37]
    span = max(vals) - min(vals)
    vmin = min(vals) - 0.24 * span
    vmax = max(vals) + 0.25 * span
    xs = np.linspace(vp.plot_left + 44 * vp.scale_x, vp.plot_right - 64 * vp.scale_x, 3)
    ys = np.asarray([vp.map_y(v, vmin, vmax) for v in vals], dtype=np.float32)

    probe = ImageDraw.Draw(Image.new("RGBA", (1080, 1920), (0, 0, 0, 0)))
    f_lbl = _load_hand_font(int(round(44 * vp.scale_y)), expressive_accent=False)
    st_bb = probe.textbbox((0, 0), "Pre-Spindle: -11.51 %", font=f_lbl)
    mid_bb = probe.textbbox((0, 0), "K-Complex: 13.49 %", font=f_lbl)
    en_bb = probe.textbbox((0, 0), "Sleep Arousal: 35.37 %", font=f_lbl)
    layout = compute_line_label_layout(
        vp,
        vals,
        xs,
        ys,
        start_bbox=st_bb,
        mid_bbox=mid_bb,
        end_bbox=en_bb,
    )
    inked_boxes = {
        "start": (layout["start"][0] + st_bb[0], layout["start"][1] + st_bb[1], layout["start"][0] + st_bb[2], layout["start"][1] + st_bb[3]),
        "mid": (layout["mid"][0] + mid_bb[0], layout["mid"][1] + mid_bb[1], layout["mid"][0] + mid_bb[2], layout["mid"][1] + mid_bb[3]),
        "end": (layout["end"][0] + en_bb[0], layout["end"][1] + en_bb[1], layout["end"][0] + en_bb[2], layout["end"][1] + en_bb[3]),
    }
    u_seg = np.linspace(0.0, 1.0, 120)
    poly_x = np.concatenate([xs[0] + (xs[1] - xs[0]) * u_seg, xs[1] + (xs[2] - xs[1]) * u_seg])
    poly_y = np.concatenate([ys[0] + (ys[1] - ys[0]) * u_seg, ys[1] + (ys[2] - ys[1]) * u_seg])
    for name, (bx0, by0, bx1, by1) in inked_boxes.items():
        dx = np.maximum(0.0, np.maximum(bx0 - poly_x, poly_x - bx1))
        dy = np.maximum(0.0, np.maximum(by0 - poly_y, poly_y - by1))
        min_dist = float(np.min(np.hypot(dx, dy)))
        assert min_dist >= 14.0, f"{name} label clearance {min_dist:.1f}px < 14px"

    # 2. Legacy bar_compare curved arrow + 69.1x red oval: >= 18px separation from arrow & values
    f_val = _load_hand_font(66, expressive_accent=False)
    f_mult = _load_hand_font(92, expressive_accent=True)
    v0_bb = probe.textbbox((0, 0), "0.08 \u03bcV\u00b2", font=f_val)
    v1_bb = probe.textbbox((0, 0), "5.53 \u03bcV\u00b2", font=f_val)
    bar_start_x, x_left, x_right, ul_y, y_bot = 110.0, 56.0, 910.0, 310.0, 1190.0
    tip0 = (bar_start_x + 52.0, 494.0)
    tip1 = (bar_start_x + 510.0, 729.0)
    val_boxes = [
        (tip0[0] + 22 + v0_bb[0], tip0[1] - 38 + v0_bb[1], tip0[0] + 22 + v0_bb[2], tip0[1] - 38 + v0_bb[3]),
        (tip1[0] + 22 + v1_bb[0], tip1[1] - 38 + v1_bb[1], tip1[0] + 22 + v1_bb[2], tip1[1] - 38 + v1_bb[3]),
    ]
    bar_boxes = [
        (bar_start_x, tip0[1] - 20.0, tip0[0], tip0[1] + 20.0),
        (bar_start_x, tip1[1] - 20.0, tip1[0], tip1[1] + 20.0),
    ]
    arrow_geo = compute_natural_arrow_geometry((val_boxes[0][2] + 18.0, tip0[1] - 4.0), (tip1[0] - 6.0, tip1[1] - 28.0), base_width=8.8, scale=1.0, seed=404)
    m_tb = probe.textbbox((0, 0), "69.1\u00d7", font=f_mult)
    mw, mh = float(m_tb[2] - m_tb[0]), float(m_tb[3] - m_tb[1])
    est_rx, est_ry = max(48.0, 0.66 * mw + 18.0), max(34.0, 0.62 * mh + 12.0)
    tx_ink, ty_ink = resolve_multiplier_badge_placement(
        arrow_geo=arrow_geo,
        val_boxes=val_boxes,
        bar_boxes=bar_boxes,
        bar_tip_coords=[tip0, tip1],
        bar_val_right_x=[val_boxes[0][2], val_boxes[1][2]],
        mw_est=mw,
        mh_est=mh,
        est_rx=est_rx,
        est_ry=est_ry,
        bar_start_x=bar_start_x,
        x_left=x_left,
        x_right=x_right,
        ul_y=ul_y,
        y_bot=y_bot,
        scale_x=1.0,
        scale_y=1.0,
        scale=1.0,
    )
    lcx, lcy = tx_ink + 0.5 * mw, ty_ink + 0.5 * mh + 4.0
    all_pts = np.vstack([arrow_geo["shaft_points"], arrow_geo["left_wing_points"], arrow_geo["right_wing_points"]])
    norm_r = np.hypot((all_pts[:, 0] - lcx) / (est_rx + 22.0), (all_pts[:, 1] - lcy) / (est_ry + 22.0))
    assert float(np.min(norm_r)) >= 1.0, f"multiplier oval within 18px of arrow (min_norm={float(np.min(norm_r)):.2f})"

