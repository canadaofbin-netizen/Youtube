---
trigger: model_decision
description: "Load when selecting or balancing weekly episode topics across the 7 academic pillars and 5 everyday domains in Topic Radar or dossier seeding (P1, R20 — Tier-2 operational diversity)."
---

# 7 Pillars & 5 Everyday Domains (`P1`, `R20` — Tier-2 Operational Diversity)

Index: [AGENTS.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/AGENTS.md) | Code: [`pipeline/pillars.py`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/pillars.py), `PILLAR_DEFAULT_STYLE_MAP` ([`pipeline/config.py`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/config.py)), `PILLAR_SLOT_MAP` ([`pipeline/studio/config.py`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/studio/config.py))

## P1 — 7 Academic Content Pillars
| `pillar_id` | Default Style (`R2-B`) | Typical `signal_path` -> `target_region` |
|---|---|---|
| `bci_tech` | `chronicle_cutaway` | hand motor nerves, spinal cord -> primary motor cortex (real BCI hardware allowed) |
| `brain_news` | `chronicle_cutaway` | jugular vein, motor tracts -> superior sagittal sinus / motor cortex |
| `brain_history` | `delusion_museum` | optic nerve -> ventromedial prefrontal cortex, amygdala |
| `brain_basics` | `icon_autopsy` | skin mechanoreceptors, dorsal column -> myelinated axons, somatosensory cortex |
| `brain_mysteries` | `case_file` | retina / cochlea -> thalamus, fusiform gyrus, amygdala, hippocampus |
| `brain_health` | `caveman_brain` | retinal light receptors -> glymphatic channels, cortex |
| `bci_ethics` | `forbidden_lab` | auditory / subvocal larynx nerves -> superior temporal gyrus, prefrontal cortex, reward tract |

- **Domain & Everyday Routing**: Every project locks to 1 `pillar_id` (`PILLAR_SLOT_MAP` / `PILLAR_PLAYLIST_MAP`) and, under Schema v2 (`R44`), 1 `everyday_domain` in `EVERYDAY_LONGFORM_DOMAINS` (`sleep`, `habits`, `memory`, `anxiety`, `relationships`). Paper anatomy (`R1`) overrides default `signal_path`. Zero HUD/telemetry overlays.
- **R20 Batch Diversity**: Weekly 7-episode batches span all 7 pillars with zero duplicate topics, zero duplicate DOIs, and zero shared clips (`R37` Guard 2).
