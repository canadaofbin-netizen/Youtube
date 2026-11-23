"""
ALL ABOUT BRAIN — R70-M Statistical, Distribution & Mathematical Curve Data Engine (`pipeline/charts/data_prep.py`).

Prepares deterministic data structures across all 3 modes (`study`, `derived`, `illustrative`):
  - Group distributions (`samples`, `quartiles` `[min, q1, median, q3, max]`, `mean`, `sd`, `kde_grid`, `kde_density`)
  - Bivariate scatter + OLS regression line + confidence band (exact target Pearson `r` via orthogonalized Cholesky)
  - Histogram bins + smooth kernel density curves
  - Mathematical & cognitive science function curves (`exp_decay`, `sigmoid`, `normal_pdf`, `prospect_value`,
    `inverted_u`, `power`, `log`, `linear`, `piecewise`).
"""

from __future__ import annotations

import math
import re
from typing import Any

import numpy as np
from scipy.stats import gaussian_kde, norm

from pipeline.config import DATA_STAMP_MAX_GROUPS, DATA_STAMP_MAX_SCATTER_POINTS


def _parse_truncation_bounds(model_name: str) -> tuple[float | None, float | None]:
    m = re.search(r"truncated_(-?\d+(?:\.\d+)?)_(-?\d+(?:\.\d+)?)", str(model_name or "").lower())
    if m:
        return float(m.group(1)), float(m.group(2))
    return None, None


def _deterministic_matched_normal(
    mean: float,
    sd: float,
    n: int,
    seed: int,
    *,
    lo_bound: float | None = None,
    hi_bound: float | None = None,
) -> np.ndarray:
    """
    Generates `n` deterministic samples whose sample mean and sample SD closely match `(mean, sd)`
    using stratified quantiles shuffled with `seed`.
    """
    n_eff = max(8, min(80, int(n)))
    rng = np.random.default_rng(seed)
    probs = (np.arange(1, n_eff + 1, dtype=np.float64) - 0.5) / float(n_eff)
    z = norm.ppf(probs)
    z = z + rng.normal(0.0, 0.08, size=n_eff)
    z = (z - np.mean(z)) / max(1e-6, float(np.std(z)))
    rng.shuffle(z)
    eff_sd = max(1e-3, float(sd))
    vals = float(mean) + z * eff_sd
    if lo_bound is not None:
        vals = np.maximum(float(lo_bound), vals)
    if hi_bound is not None:
        vals = np.minimum(float(hi_bound), vals)
    return vals.astype(np.float64)


def compute_kde_profile(samples: np.ndarray, n_grid: int = 64) -> tuple[np.ndarray, np.ndarray]:
    """Computes normalized `(grid_y, density_0_to_1)` using `scipy.stats.gaussian_kde`."""
    arr = np.asarray(samples, dtype=np.float64).ravel()
    if arr.size < 3 or float(np.std(arr)) < 1e-5:
        c = float(np.mean(arr)) if arr.size else 0.0
        span = max(1.0, abs(c) * 0.2)
        grid = np.linspace(c - span, c + span, n_grid)
        dens = np.exp(-0.5 * ((grid - c) / (span * 0.35)) ** 2)
        return grid, dens / max(1e-6, float(np.max(dens)))
    lo, hi = float(np.min(arr)), float(np.max(arr))
    pad = max(1e-3, (hi - lo) * 0.14)
    grid = np.linspace(lo - pad, hi + pad, n_grid)
    try:
        kde = gaussian_kde(arr, bw_method="scott")
        dens = kde(grid)
    except Exception:
        sd = max(1e-3, float(np.std(arr)))
        dens = np.exp(-0.5 * ((grid - float(np.mean(arr))) / sd) ** 2)
    peak = float(np.max(dens)) if dens.size else 1.0
    return grid, (dens / max(1e-6, peak)).astype(np.float64)


def prepare_group_distributions(panel_raw: dict[str, Any], seed: int = 101) -> list[dict[str, Any]]:
    """
    Builds rich per-group distribution records from `groups` or `bars`.
    Each returned dict contains:
      `label`, `unit`, `mean`, `sd`, `min`, `q1`, `median`, `q3`, `max`,
      `samples` (`np.ndarray`), `kde_grid` (`np.ndarray`), `kde_density` (`np.ndarray`),
      `error_lo`, `error_hi`.
    """
    raw_groups = panel_raw.get("groups") or panel_raw.get("bars") or []
    if not isinstance(raw_groups, list) or not raw_groups:
        # Default illustrative 2-group distribution if none specified
        raw_groups = [
            {"label": "Control", "mean": 3.2, "sd": 1.4, "n": 24},
            {"label": "Experiment", "mean": 11.8, "sd": 2.6, "n": 24},
        ]
    model_name = str(panel_raw.get("model") or "")
    lo_b, hi_b = _parse_truncation_bounds(model_name)
    unit_default = str(panel_raw.get("unit") or "").strip()

    prepared: list[dict[str, Any]] = []
    for idx, g in enumerate(raw_groups[:DATA_STAMP_MAX_GROUPS]):
        if not isinstance(g, dict):
            continue
        lbl = str(g.get("label") or f"Group {idx + 1}").strip()
        unit = str(g.get("unit") or unit_default).strip()
        g_seed = int(seed) + idx * 53

        if isinstance(g.get("samples"), list) and len(g["samples"]) >= 3:
            s_arr = np.asarray([float(x) for x in g["samples"]], dtype=np.float64)
            q_min, q1, med, q3, q_max = np.percentile(s_arr, [0, 25, 50, 75, 100])
            mean_v = float(np.mean(s_arr))
            sd_v = float(np.std(s_arr, ddof=1)) if s_arr.size > 1 else 0.0
        elif all(k in g for k in ("q1", "median", "q3")):
            q1 = float(g["q1"])
            med = float(g["median"])
            q3 = float(g["q3"])
            iqr = max(0.1, q3 - q1)
            q_min = float(g.get("min", g.get("lo", q1 - 1.25 * iqr)))
            q_max = float(g.get("max", g.get("hi", q3 + 1.25 * iqr)))
            mean_v = float(g.get("mean", g.get("value", med)))
            sd_v = float(g.get("sd", iqr / 1.349))
            s_arr = _deterministic_matched_normal(
                med,
                max(0.05, sd_v),
                int(g.get("n") or 24),
                g_seed,
                lo_bound=q_min,
                hi_bound=q_max,
            )
        else:
            mean_v = float(g.get("mean") if g.get("mean") is not None else (g.get("value") or 0.0))
            sd_raw = g.get("sd")
            if sd_raw is None and isinstance(g.get("error"), dict):
                sd_raw = g["error"].get("sd") or g["error"].get("se") or g["error"].get("half_width")
            sd_v = float(sd_raw) if sd_raw is not None else max(0.4, abs(mean_v) * 0.22)
            n_pts = int(g.get("n") or 24)
            s_arr = _deterministic_matched_normal(
                mean_v,
                max(0.05, sd_v),
                n_pts,
                g_seed,
                lo_bound=lo_b if lo_b is not None else (0.0 if mean_v >= 0 else None),
                hi_bound=hi_b,
            )
            q_min, q1, med, q3, q_max = np.percentile(s_arr, [0, 25, 50, 75, 100])

        err_spec = g.get("error")
        if isinstance(err_spec, dict):
            if "lo" in err_spec and "hi" in err_spec:
                err_lo = float(err_spec["lo"])
                err_hi = float(err_spec["hi"])
            else:
                hw = float(err_spec.get("value") or err_spec.get("sd") or err_spec.get("se") or sd_v)
                err_lo = mean_v - hw
                err_hi = mean_v + hw
        elif isinstance(err_spec, (int, float)):
            err_lo = mean_v - float(err_spec)
            err_hi = mean_v + float(err_spec)
        else:
            err_lo = mean_v - sd_v
            err_hi = mean_v + sd_v

        kde_g, kde_d = compute_kde_profile(s_arr)
        prepared.append(
            {
                "label": lbl,
                "unit": unit,
                "value": mean_v,
                "mean": mean_v,
                "sd": sd_v,
                "min": float(q_min),
                "q1": float(q1),
                "median": float(med),
                "q3": float(q3),
                "max": float(q_max),
                "error_lo": float(err_lo),
                "error_hi": float(err_hi),
                "samples": s_arr,
                "kde_grid": kde_g,
                "kde_density": kde_d,
            }
        )
    return prepared


def prepare_scatter_and_regression(panel_raw: dict[str, Any], seed: int = 101) -> dict[str, Any]:
    """
    Prepares `(x, y)` scatter coordinates (capped at `DATA_STAMP_MAX_SCATTER_POINTS = 120`),
    exact Pearson `r`, OLS regression line `(x_line, y_line)`, and 95% confidence band `(ci_lo, ci_hi)`.
    When synthesized from `r` (`derived` / `illustrative`), orthogonalizes draws so sample `r` matches target `r` within `±0.005`.
    """
    params = panel_raw.get("params") if isinstance(panel_raw.get("params"), dict) else {}
    pts_raw = panel_raw.get("points") or panel_raw.get("scatter_points")
    if isinstance(pts_raw, list) and len(pts_raw) >= 4 and isinstance(pts_raw[0], (list, tuple, dict)):
        xs_l: list[float] = []
        ys_l: list[float] = []
        for p in pts_raw[:DATA_STAMP_MAX_SCATTER_POINTS]:
            if isinstance(p, dict):
                xs_l.append(float(p.get("x", 0.0)))
                ys_l.append(float(p.get("y", 0.0)))
            elif len(p) >= 2:
                xs_l.append(float(p[0]))
                ys_l.append(float(p[1]))
        x = np.asarray(xs_l, dtype=np.float64)
        y = np.asarray(ys_l, dtype=np.float64)
    elif isinstance(panel_raw.get("x"), list) and isinstance(panel_raw.get("y"), list) and len(panel_raw["x"]) >= 4:
        n_cap = min(DATA_STAMP_MAX_SCATTER_POINTS, len(panel_raw["x"]), len(panel_raw["y"]))
        x = np.asarray([float(v) for v in panel_raw["x"][:n_cap]], dtype=np.float64)
        y = np.asarray([float(v) for v in panel_raw["y"][:n_cap]], dtype=np.float64)
    else:
        r_target = float(
            panel_raw.get("r")
            if panel_raw.get("r") is not None
            else (params.get("r") if params.get("r") is not None else 0.74)
        )
        r_target = max(-0.98, min(0.98, r_target))
        n_pts = int(panel_raw.get("n") or params.get("n") or 48)
        n_pts = max(12, min(DATA_STAMP_MAX_SCATTER_POINTS, n_pts))
        rng = np.random.default_rng(int(panel_raw.get("seed") or params.get("seed") or seed))
        u1 = rng.normal(0.0, 1.0, size=n_pts)
        u2 = rng.normal(0.0, 1.0, size=n_pts)
        u1 = (u1 - np.mean(u1)) / max(1e-6, float(np.std(u1)))
        # Orthogonalize u2 against u1 so empirical correlation equals r_target exactly
        u2 = u2 - (np.dot(u1, u2) / max(1e-6, float(np.dot(u1, u1)))) * u1
        u2 = (u2 - np.mean(u2)) / max(1e-6, float(np.std(u2)))
        z_y = r_target * u1 + math.sqrt(max(0.0, 1.0 - r_target ** 2)) * u2

        x_lo, x_hi = (panel_raw.get("x_range") or params.get("x_range") or [10.0, 90.0])[:2]
        y_lo, y_hi = (panel_raw.get("y_range") or params.get("y_range") or [15.0, 95.0])[:2]
        x = 0.5 * (float(x_lo) + float(x_hi)) + u1 * (0.22 * (float(x_hi) - float(x_lo)))
        y = 0.5 * (float(y_lo) + float(y_hi)) + z_y * (0.22 * (float(y_hi) - float(y_lo)))

    # Sort by x for smooth left-to-right progressive drawing
    order = np.argsort(x)
    x = x[order]
    y = y[order]

    xm, ym = float(np.mean(x)), float(np.mean(y))
    dx = x - xm
    dy = y - ym
    denom = float(np.sum(dx ** 2))
    slope = float(np.sum(dx * dy) / denom) if denom > 1e-8 else 0.0
    intercept = ym - slope * xm
    r_emp = float(np.sum(dx * dy) / max(1e-8, math.sqrt(float(np.sum(dx ** 2) * np.sum(dy ** 2)))))

    x_grid = np.linspace(float(np.min(x)), float(np.max(x)), 48)
    y_hat = intercept + slope * x_grid
    resid = y - (intercept + slope * x)
    s_err = math.sqrt(float(np.sum(resid ** 2)) / max(1, len(x) - 2))
    se_line = s_err * np.sqrt(1.0 / max(1, len(x)) + ((x_grid - xm) ** 2) / max(1e-6, denom))
    ci_half = np.maximum(2.0 * se_line, 0.06 * (float(np.max(y)) - float(np.min(y))))

    return {
        "x": x,
        "y": y,
        "r": round(r_emp, 3),
        "slope": slope,
        "intercept": intercept,
        "x_grid": x_grid,
        "y_hat": y_hat,
        "ci_lo": y_hat - ci_half,
        "ci_hi": y_hat + ci_half,
    }


def evaluate_function_curve(layer_raw: dict[str, Any], n_pts: int = 96) -> dict[str, Any]:
    """
    Evaluates a mathematical or cognitive science function curve (`fn`) over `n_pts`:
      - `exp_decay` (Ebbinghaus forgetting curve)
      - `sigmoid` (Conscious ignition threshold / psychometric curve)
      - `normal_pdf` (Gaussian bell curve)
      - `prospect_value` (Kahneman-Tversky asymmetric loss-aversion value function)
      - `inverted_u` (Yerkes-Dodson arousal-performance curve)
      - `power`, `log`, `linear`, `piecewise`
    """
    fn = str(layer_raw.get("fn") or layer_raw.get("function") or "exp_decay").strip().lower()
    params = layer_raw.get("params") if isinstance(layer_raw.get("params"), dict) else {}

    if fn == "prospect_value":
        x = np.linspace(-1.0, 1.0, n_pts)
        alpha = float(params.get("alpha", 0.88))
        lam = float(params.get("lambda", 2.25))
        y = np.where(x >= 0.0, np.power(np.maximum(0.0, x), alpha), -lam * np.power(np.maximum(0.0, -x), alpha))
        markers = layer_raw.get("markers") or [
            {"x": 0.5, "y": float(0.5 ** alpha), "label": "+$100 Gain"},
            {"x": -0.5, "y": float(-lam * (0.5 ** alpha)), "label": "-$100 Loss (2.25× Pain)"},
        ]
        return {"fn": fn, "x": x, "y": y, "zero_cross": True, "markers": markers}

    if fn == "normal_pdf":
        mu = float(params.get("mu", 0.0))
        sigma = max(0.1, float(params.get("sigma", 1.0)))
        x = np.linspace(mu - 3.2 * sigma, mu + 3.2 * sigma, n_pts)
        y = np.exp(-0.5 * ((x - mu) / sigma) ** 2) * 100.0
        markers = layer_raw.get("markers") or [{"x": mu, "y": 100.0, "label": "Mean (μ)"}]
        return {"fn": fn, "x": x, "y": y, "zero_cross": False, "markers": markers}

    if fn == "sigmoid":
        x0 = float(params.get("x0", 5.0))
        k = float(params.get("k", 1.15))
        x = np.linspace(0.0, 10.0, n_pts)
        y = 100.0 / (1.0 + np.exp(-k * (x - x0)))
        markers = layer_raw.get("markers") or [{"x": x0, "y": 50.0, "label": "Ignition Threshold"}]
        return {"fn": fn, "x": x, "y": y, "zero_cross": False, "markers": markers}

    if fn == "inverted_u":
        x = np.linspace(0.0, 10.0, n_pts)
        peak_x = float(params.get("peak_x", 5.0))
        y = 100.0 * np.exp(-0.18 * ((x - peak_x) ** 2))
        markers = layer_raw.get("markers") or [{"x": peak_x, "y": 100.0, "label": "Optimal Zone"}]
        return {"fn": fn, "x": x, "y": y, "zero_cross": False, "markers": markers}

    if fn == "power":
        alpha = float(params.get("alpha", 0.6))
        x = np.linspace(0.0, 10.0, n_pts)
        y = np.power(x, alpha) * 10.0
        return {"fn": fn, "x": x, "y": y, "zero_cross": False, "markers": layer_raw.get("markers") or []}

    if fn == "log":
        k = float(params.get("k", 1.5))
        x = np.linspace(0.0, 10.0, n_pts)
        y = np.log1p(k * x) * 35.0
        return {"fn": fn, "x": x, "y": y, "zero_cross": False, "markers": layer_raw.get("markers") or []}

    if fn == "linear":
        m = float(params.get("slope", 8.0))
        b = float(params.get("intercept", 15.0))
        x = np.linspace(0.0, 10.0, n_pts)
        y = m * x + b
        return {"fn": fn, "x": x, "y": y, "zero_cross": False, "markers": layer_raw.get("markers") or []}

    if fn in ("exp_growth", "exponential_growth"):
        base = float(params.get("base", 12.0))
        rate = float(params.get("k", 0.32))
        x = np.linspace(0.0, 7.0, n_pts)
        y = base * np.exp(rate * x)
        markers = layer_raw.get("markers") or [
            {"x": 4.8, "y": float(base * math.exp(rate * 4.8)), "label": "Ironic Rebound"},
        ]
        return {"fn": "exp_growth", "x": x, "y": y, "zero_cross": False, "markers": markers}

    # Default: `exp_decay` (Ebbinghaus forgetting curve)
    asymptote = float(params.get("asymptote", 21.0))
    rate = float(params.get("k", 0.55))
    x = np.linspace(0.0, 7.0, n_pts)
    y = asymptote + (100.0 - asymptote) * np.exp(-rate * x)
    markers = layer_raw.get("markers") or [
        {"x": 1.0, "y": float(asymptote + (100.0 - asymptote) * math.exp(-rate * 1.0)), "label": "Day 1 Drop"},
    ]
    return {"fn": "exp_decay", "x": x, "y": y, "zero_cross": False, "markers": markers}
