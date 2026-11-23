"""
ALL ABOUT BRAIN — R70-M Hand-Drawn Grammar-of-Graphics Spec Parser & Preset Router (`pipeline/charts/spec.py`).

Supports:
  - 3 Data Modes (`study`, `derived`, `illustrative` -> `"Concept"` badge)
  - 15 Layer Types (`bar`, `error`, `slope`, `dot_array`, `arc_gauge`, `points`, `box`, `violin`,
    `histogram`, `density`, `scatter`, `regression`, `line`, `band`, `function_curve`)
  - 16 Composite & Single Presets (`raincloud`, `violin_box`, `box_points`, `bar_points_error`,
    `scatter_fit`, `line_band`, `hist_density`, `curve_marker`, `bar_compare`, `dot_array`,
    `arc_gauge`, `slope_paired`, `line`, `range_band`, `box`, `violin`)
  - Single-panel (`1x1`) and 2-panel vertical (`2x1`) layouts.
"""

from __future__ import annotations

import copy
from typing import Any

from pipeline.config import (
    DATA_STAMP_BASE_HOLD_SEC,
    DATA_STAMP_COMPLEXITY_STEP_SEC,
    DATA_STAMP_DEFAULT_STYLE,
    DATA_STAMP_ILLUSTRATION_TAG,
    DATA_STAMP_LAYER_TYPES,
    DATA_STAMP_MAX_GROUPS,
    DATA_STAMP_MAX_HOLD_SEC,
    DATA_STAMP_MAX_LAYERS_PER_PANEL,
    DATA_STAMP_MAX_PANELS,
    DATA_STAMP_MODES,
    DATA_STAMP_PRESETS,
)

STAT_FORMAT_TO_PRESET: dict[str, str] = {
    "group_means": "bar_compare",
    "group_counts": "bar_compare",
    "count_of_n": "dot_array",
    "single_percent": "arc_gauge",
    "before_after": "line",
    "timeseries": "line",
    "correlation_r": "scatter_fit",
    "math_function": "curve_marker",
}


def route_chart_for_stat(stat_format: str | None) -> str:
    """Maps a dossier `stats.format` token to its canonical default preset."""
    key = str(stat_format or "").strip().lower()
    return STAT_FORMAT_TO_PRESET.get(key, "bar_compare")


def is_legacy_bar_compare_only(stamp: dict[str, Any]) -> bool:
    """
    Returns True iff `stamp` uses the classic R70 v2 single-panel `bar_compare` schema without
    error bars, custom layers, multi-panel layout, or non-study modes, so existing `bar_compare`
    outputs remain 100% pixel-identical.
    """
    if not isinstance(stamp, dict):
        return False
    if stamp.get("panels") or stamp.get("layers") or str(stamp.get("layout") or "1x1") != "1x1":
        return False
    mode = str(stamp.get("mode") or "study").strip().lower()
    if mode != "study":
        return False
    preset = str(stamp.get("preset") or stamp.get("chart") or "bar_compare").strip().lower()
    if preset != "bar_compare":
        return False
    bars = stamp.get("bars")
    if not isinstance(bars, list) or not (2 <= len(bars) <= 3):
        return False
    if any(isinstance(b, dict) and b.get("error") is not None for b in bars):
        return False
    return True


def expand_preset_to_layers(panel_raw: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Expands a `preset` / `chart` name (or explicit `layers` list) into a normalized sequence of
    layer dictionaries with progressive `reveal_at` (`[u0, u1]`) windows.
    """
    explicit_layers = panel_raw.get("layers")
    if isinstance(explicit_layers, list) and explicit_layers:
        out_explicit: list[dict[str, Any]] = []
        n_exp = len(explicit_layers)
        for idx, lyr in enumerate(explicit_layers[:DATA_STAMP_MAX_LAYERS_PER_PANEL]):
            if not isinstance(lyr, dict):
                continue
            l_copy = copy.deepcopy(lyr)
            l_type = str(l_copy.get("type") or "bar").strip().lower()
            l_copy["type"] = l_type
            if "reveal_at" not in l_copy:
                u0 = round(0.08 + 0.22 * idx, 3)
                u1 = round(min(0.96, u0 + max(0.38, 0.72 / max(1, n_exp))), 3)
                l_copy["reveal_at"] = [u0, u1]
            out_explicit.append(l_copy)
        return out_explicit

    preset = str(panel_raw.get("preset") or panel_raw.get("chart") or "bar_compare").strip().lower()
    base_payload = {
        k: copy.deepcopy(v)
        for k, v in panel_raw.items()
        if k not in ("layers", "panels", "layout")
    }

    if preset == "bar_compare":
        return [{"type": "bar", "reveal_at": [0.08, 0.88], **base_payload}]

    if preset == "dot_array":
        return [{"type": "dot_array", "reveal_at": [0.08, 0.90], **base_payload}]

    if preset in ("arc_gauge", "arc_gauge_ring"):
        return [{"type": "arc_gauge", "reveal_at": [0.08, 0.90], **base_payload}]

    if preset in ("line", "line_trajectory"):
        return [{"type": "line", "reveal_at": [0.08, 0.90], **base_payload}]

    if preset in ("scatter_fit", "scatter"):
        return [
            {"type": "scatter", "reveal_at": [0.08, 0.68], **base_payload},
            {"type": "regression", "reveal_at": [0.45, 0.94], **base_payload},
        ]

    if preset in ("curve_marker", "function_curve"):
        return [
            {"type": "function_curve", "reveal_at": [0.08, 0.82], **base_payload},
            {"type": "points", "marker_mode": True, "reveal_at": [0.58, 0.94], **base_payload},
        ]

    if preset in DATA_STAMP_LAYER_TYPES:
        return [{"type": preset, "reveal_at": [0.08, 0.90], **base_payload}]

    return [{"type": "bar", "reveal_at": [0.08, 0.88], **base_payload}]


def _normalize_single_panel(raw_p: dict[str, Any], parent_stamp: dict[str, Any], panel_idx: int) -> dict[str, Any]:
    mode = str(raw_p.get("mode") or parent_stamp.get("mode") or "study").strip().lower()
    if mode not in DATA_STAMP_MODES:
        mode = "study"
    style = str(raw_p.get("style") or parent_stamp.get("style") or DATA_STAMP_DEFAULT_STYLE).strip().lower()
    if style not in ("crayon", "ink_pen", "marker", "chalk"):
        style = "ink_pen"
    preset = str(
        raw_p.get("preset")
        or raw_p.get("chart")
        or parent_stamp.get("preset")
        or parent_stamp.get("chart")
        or "bar_compare"
    ).strip().lower()
    merged = {**parent_stamp, **raw_p, "mode": mode, "style": style, "preset": preset}
    layers = expand_preset_to_layers(merged)
    return {
        "panel_index": panel_idx,
        "mode": mode,
        "style": style,
        "preset": preset,
        "title": str(raw_p.get("title") or (parent_stamp.get("title") if panel_idx == 0 else "") or "").strip(),
        "x_label": str(raw_p.get("x_label") or parent_stamp.get("x_label") or "").strip(),
        "y_label": str(raw_p.get("y_label") or parent_stamp.get("y_label") or "").strip(),
        "unit": str(raw_p.get("unit") or parent_stamp.get("unit") or "").strip(),
        "doi": str(raw_p.get("doi") if "doi" in raw_p else (parent_stamp.get("doi") or "")).strip(),
        "source_citation": str(
            raw_p.get("source_citation")
            if "source_citation" in raw_p
            else (parent_stamp.get("source_citation") or "")
        ).strip(),
        "model": str(raw_p.get("model") or parent_stamp.get("model") or "").strip(),
        "concept": str(raw_p.get("concept") or parent_stamp.get("concept") or "").strip(),
        "badge_tag": DATA_STAMP_ILLUSTRATION_TAG if mode == "illustrative" else "",
        "seed": int(raw_p.get("seed") or parent_stamp.get("seed") or (101 + panel_idx * 37)),
        "multiplier_badge": str(raw_p.get("multiplier_badge") or parent_stamp.get("multiplier_badge") or "").strip(),
        "layers": layers,
        "raw": merged,
    }


def parse_chart_spec(stamp: dict[str, Any]) -> dict[str, Any]:
    """Parses a raw `data_stamps` entry into a normalized single-panel (`1x1`) `ChartSpec` dict."""
    if not isinstance(stamp, dict):
        raise ValueError("stamp must be a dict")
    raw_panels = stamp.get("panels")
    layout = "1x1"
    p0 = raw_panels[0] if (isinstance(raw_panels, list) and raw_panels and isinstance(raw_panels[0], dict)) else stamp
    panels = [_normalize_single_panel(p0, stamp, 0)]

    return {
        "layout": layout,
        "title": str(stamp.get("title") or (panels[0]["title"] if panels else "Study Data")).strip(),
        "style": panels[0]["style"] if panels else DATA_STAMP_DEFAULT_STYLE,
        "mode": panels[0]["mode"] if panels else "study",
        "panels": panels,
        "sentence_index": int(stamp.get("sentence_index") or 1),
        "end_sentence_index": int(stamp.get("end_sentence_index") or stamp.get("sentence_index") or 1),
    }


def compute_stamp_complexity_and_hold_sec(stamp: dict[str, Any]) -> tuple[int, float]:
    """
    Computes `(complexity_score, recommended_min_duration_sec)`:
      - Base hold = `DATA_STAMP_BASE_HOLD_SEC` (`4.2s`)
      - Adds `DATA_STAMP_COMPLEXITY_STEP_SEC` (`+0.8s`) per extra layer or extra panel, capped at `7.5s`.
    """
    spec = parse_chart_spec(stamp)
    n_panels = len(spec["panels"])
    total_layers = sum(len(p["layers"]) for p in spec["panels"])
    max_groups = 2
    for p in spec["panels"]:
        raw = p["raw"]
        for k in ("bars", "groups", "series"):
            if isinstance(raw.get(k), list):
                max_groups = max(max_groups, min(DATA_STAMP_MAX_GROUPS, len(raw[k])))
    complexity = max(1, n_panels * total_layers * max(1, max_groups // 2))
    extra_steps = max(0, (n_panels - 1) + (total_layers - 1))
    dur = min(
        float(DATA_STAMP_MAX_HOLD_SEC),
        float(DATA_STAMP_BASE_HOLD_SEC) + extra_steps * float(DATA_STAMP_COMPLEXITY_STEP_SEC),
    )
    return complexity, round(dur, 2)
