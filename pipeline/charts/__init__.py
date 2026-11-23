"""
ALL ABOUT BRAIN — R70-M Hand-Drawn Grammar-of-Graphics Chart Package (`pipeline/charts`).
"""

from pipeline.charts.axes import PanelViewport, build_panel_viewport
from pipeline.charts.compose import render_chart_spec_rgba_frame
from pipeline.charts.data_prep import (
    compute_kde_profile,
    evaluate_function_curve,
    prepare_group_distributions,
    prepare_scatter_and_regression,
)
from pipeline.charts.spec import (
    STAT_FORMAT_TO_PRESET,
    compute_stamp_complexity_and_hold_sec,
    expand_preset_to_layers,
    is_legacy_bar_compare_only,
    parse_chart_spec,
    route_chart_for_stat,
)

__all__ = [
    "PanelViewport",
    "STAT_FORMAT_TO_PRESET",
    "build_panel_viewport",
    "compute_kde_profile",
    "compute_stamp_complexity_and_hold_sec",
    "evaluate_function_curve",
    "expand_preset_to_layers",
    "is_legacy_bar_compare_only",
    "parse_chart_spec",
    "prepare_group_distributions",
    "prepare_scatter_and_regression",
    "render_chart_spec_rgba_frame",
    "route_chart_for_stat",
]
