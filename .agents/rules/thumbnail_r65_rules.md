---
trigger: model_decision
description: "Load when generating, compositing, or QA-checking R65 v4 50/50 in-skull cutaway split thumbnails and TQ1-TQ9 gates (R65)."
---

# Thumbnail Studio & `R65 v4` Split Cover (`R65`)

Index: [AGENTS.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/AGENTS.md) | Constants: [production_constants.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/production_constants.md) | Code: [`pipeline/thumbnail_studio.py`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/thumbnail_studio.py)

## R65 — Thumbnail Studio (`R65 v4` 50/50 In-Skull Cutaway Split, `pipeline/thumbnail_studio.py`)
- **Profile & Keyart Generation**: Default `DEFAULT_SHORTS_THUMBNAIL_PROFILE = "in_skull_cutaway_split_v4"` (`R65_V4_THUMBNAIL_PROFILE`; optional `dark_void_paradox_v4`). Uses `conditioning_paths=None` (`0` mannequin conditioning) via `0-credit` Flow `Image` (`Nano Banana 2.1`, `x2` `FLOW_ZERO_CREDIT_IMAGE_THUMBNAIL_BATCH_COUNT = 2`, 1 prompt/ep).
- **Layout & Safe Zone**: `50/50` horizontal split of the same expressive human (dormant top vs active bottom in-skull 3D brain cutaway + `#FF2525` 3D arrow), `2:3` shelf-safe (`y = 150..1495`, `y >= 1520` bottom title zone clear), `<= 3w` micro-labels (`thumbnail_selected.png`), and `cover_frame_sec` matched to `Cut #1` (`R87-H1`).
- **Gates**:
  - **Tier-1 Blockers**: `TQ4` (safe zone), `TQ6` (`1080x1920`, `< 2MB`), `TQ7` (`<= 3w` lexical), `TQ8` (`50/50` split & zero head occlusion), `TQ9` (zero pointer/text overlap).
  - **Tier-2 Advisory**: `TQ1–TQ3`.
  - **Retired on Shorts**: `TQ5_pairwise_distinct` (3-variant diff).
