# `porcelain_cinematic_v7` Baseline & `1:1` Archival Reenactment (`R66`, `R67`)

Index: [AGENTS.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/AGENTS.md) | Constants: [production_constants.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/production_constants.md) | Code: [`pipeline/archival_media.py`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/archival_media.py)

## R66 — `porcelain_cinematic_v7` Baseline Profile
- Legacy/archival baseline profile `DEFAULT_DIORAMA_STYLE_PROFILE="porcelain_cinematic_v7"` (`PORCELAIN_V7_VISUAL_GRAMMARS`, `PORCELAIN_V7_BRAIN_RENDER_MODES`, zero neon-green spill `<= PORCELAIN_V7_NEON_GREEN_SPILL_MAX`), featuring high-key bright minimalist worlds and smooth featureless oval matte-white porcelain heads.

## R67 — `Track A` `1:1` Archival Footage Reenactment (`pipeline/archival_media.py`)
- Quarantines external archival footage inside `/tmp/aab_reenact` (`REENACT_QUARANTINE_ROOT`), strips faces/text into `9:16` structural silhouette guides, translates to bespoke keyframes via `0-credit` Flow `Image` (`Nano Banana 2.1`), purges `/tmp`, and enforces `RQ1–RQ5` (`dHash >= REENACT_MIN_DHASH_DISTANCE`, `REENACT_BRAIN_RATIO_MIN = 0.20`, `0.0%` 5-gram pixel overlap).
