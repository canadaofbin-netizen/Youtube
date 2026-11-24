---
trigger: model_decision
description: "Load when authoring or validating R70/R70-M intuitive 1x1 study Data Stamps, chart safe zones, or R71/R71-B tracked anatomy callout leader lines (R70, R70-M, R71, R71-B)."
---

# Data Stamps & Tracked Anatomy Leader Lines (`R70/R70-M`, `R71/R71-B`)

Index: [AGENTS.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/AGENTS.md) | Constants: [production_constants.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/production_constants.md) | Code: [`pipeline/stamp_overlay.py`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/stamp_overlay.py), [`pipeline/anatomy_overlay.py`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/anatomy_overlay.py)

## R70 / R70-M — Intuitive `1x1` Hand-Drawn Data Stamp (`pipeline/charts/`)
- **Safe Zone & Presets**: Programmatic overlay in `Y = 12%..62%` (`max_y_frac <= 0.62`, `DATA_STAMP_Y_FRAC_RANGE`), `X <= 910px` (`<= 2` stamps/ep, `1x1` single-panel across `bar_compare`, `arc_gauge`, `dot_array`, `line`, `curve_marker`, `scatter_fit`; academic violin/box/CI/SD banned).
- **[Tier-1 #1 & #10 Hard Blockers]**:
  1. **Zero Fake `"Concept"` Badge on Empirical Facts**: `mode="illustrative"` (`"Concept"`) is strictly forbidden whenever a verified study DOI exists; use `mode="study"` matching exact paper/verified-dossier numbers (`0` spoken contradictions like `29% != 30%`, `0` species conflation — label animal data `(Mice)` explicitly).
  2. **Zero Glyph Collision (`R70-M8/M9`)**: Highlight loops/arrows must maintain `0px` overlap with bar value digits and `>= 2.0s` separation from `R71/R81` anatomy callouts.
- **[Tier-2 Advisory]**: `1 vs 2` stamps per episode and `< 8.0s` inter-stamp gap (`R70-M5/M6/M7`).

## R71 / R71-B — Tracked 2-Node Pathway & Severance Callouts
- Fountain-pen leader lines (`single_region`, `pathway_relay` `──▶`, `pathway_severed` crimson `── ✕ ──`) clamped inside `X = 48..910px`, `Y = 12%..65%` (`0%` AI scene text).
