# Rule: 7 Content Pillars & Domain Isolation Protocol

Parent Master Index: [AGENTS.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/AGENTS.md) · Code: [`pipeline/pillars.py`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/pillars.py), `PILLAR_DEFAULT_STYLE_MAP` (`pipeline/config.py`), `PILLAR_SLOT_MAP` (`pipeline/studio/config.py`)

---

## P1 — 7 Academic Content Pillars
| Pillar ID | Name | Default style (R2-B) | Typical `signal_path` → `target_region` | Slot (R30) |
|---|---|---|---|---|
| `bci_tech` | BCI Tech Explained | `chronicle_cutaway` | hand motor nerves, spinal cord → primary motor cortex (real implant hardware allowed, D5) | `PILLAR_SLOT_MAP` |
| `brain_news` | Brain News | `chronicle_cutaway` | jugular vein, motor tracts → superior sagittal sinus / motor cortex | `PILLAR_SLOT_MAP` |
| `brain_history` | Brain History | `delusion_museum` | optic nerve → ventromedial prefrontal cortex, amygdala | `PILLAR_SLOT_MAP` |
| `brain_basics` | Brain Basics | `icon_autopsy` | skin mechanoreceptors, dorsal column → myelinated axons, somatosensory cortex | `PILLAR_SLOT_MAP` |
| `brain_mysteries` | Brain Mysteries | `case_file` | retina / cochlea → thalamus, fusiform gyrus, amygdala, hippocampus | `PILLAR_SLOT_MAP` |
| `brain_health` | Brain Health | `caveman_brain` | retinal light receptors → glymphatic channels, cortex | `PILLAR_SLOT_MAP` |
| `bci_ethics` | BCI Ethics | `forbidden_lab` | auditory nerve, subvocal larynx nerves → superior temporal gyrus, prefrontal cortex, reward tract | `PILLAR_SLOT_MAP` |

The mapping is a starting point for `visual_plan.signal_path` / `target_region` ([visual_prompt_spec.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/visual_prompt_spec.md) R40-C); the topic's paper (R1) always wins.

## Domain Isolation
- Each project locks to one `pillar_id`; its `visual_plan`, archetype and slot follow that pillar.
- No HUD or telemetry schema is used for any pillar.

## R20 — Weekly Batch Diversity
A 7-video weekly batch covers all 7 pillars with zero duplicate topics, zero duplicate DOIs and zero shared clips (R37 Guard 2).
