---
trigger: model_decision
description: "Load when updating asset_manifest.json, asset_library/index.jsonl, or syncing knowledge_base/ telemetry and reusable_packs (R50, R50-B)."
---

# Asset Manifest & Knowledge Hub (`R50`, `R50-B`)

Index: [AGENTS.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/AGENTS.md) | Constants: [production_constants.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/production_constants.md) | Code: [`pipeline/asset_manifest.py`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/asset_manifest.py), [`pipeline/knowledge_hub.py`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/knowledge_hub.py)

## R50 — Per-Clip Asset Manifest (`pipeline/asset_manifest.py`)
- `05_assembly/asset_manifest.json` + `BCI_Shorts_Channel/asset_library/index.jsonl` log per-clip `asset_id`, grammar, camera, SHA-256, prompt, Flow model/URL, EDL in/out, R64 `clarity_score`, and reuse hints (`aspect`-neutral scene text via `flow_prompt_prefix(aspect)`).

## R50-B — Knowledge Hub (`main.py kb sync --project <id>`)
- Under `KNOWLEDGE_BASE_DIR`:
  - `telemetry/`: `EPISODES_INDEX_FILENAME`, `CLIP_CLARITY_LEDGER_FILENAME`, `QA_ANALYTICS_SUMMARY_FILENAME`.
  - `reusable_packs/`: `prompts_golden_bank.json`, `analogies_registry.json`, `brain_models_registry.json`, `locations_and_props_registry.json` (plus optional `EXPERIMENTS_ARCHIVE_DIRNAME`).
- Incremental `--project <id>` sync is default; use `--full-rescan` only for full rebuilds.
