# ALL ABOUT BRAIN — Knowledge Base & Reusable Asset Hub

Structured accumulation layer for cross-episode QA analytics, prompt optimization,
Shorts reuse, and 8–15 minute Longform expansion.

## Directory Layout
- `telemetry/episodes_index.jsonl` — Per-episode speed (`1.08x` / `+8%`, `+14Hz` Silk Clean), WPM, duration, DQ1–DQ12, and R64 clarity summary.
- `telemetry/clip_clarity_ledger.jsonl` — Every evaluated cut/clip with prompt, grammar, camera move, 5-axis clarity scores, and defects.
- `telemetry/qa_analytics_summary.json` & `qa_analytics_report.md` — Aggregated clarity benchmarks by grammar, camera move, and Act.
- `reusable_packs/prompts_golden_bank.json` — Verified high-clarity prompts (`>= 82.0`) indexed by grammar & camera move.
- `reusable_packs/analogies_registry.json` — Spoken `[Number] -> [Everyday Analogy]` pairs + visual staging recipes.
- `reusable_packs/brain_models_registry.json` — Canonical 3D brain region depictions & reusable clip paths.
- `reusable_packs/locations_and_props_registry.json` — Verified recurring environments & text-free props.
- `experiments/` — Archived controlled A/B render comparisons with provenance manifests.

## CLI Usage
```bash
python -X utf8 main.py kb sync
python -X utf8 main.py kb stats
python -X utf8 main.py kb search --pack prompts --grammar lowpoly_hands_closeup --min-clarity 85
python -X utf8 main.py kb search --pack clips --query "frontal lobe"
```
