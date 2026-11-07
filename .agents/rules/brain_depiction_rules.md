# Brain Depiction Rules (`R21`, `R38`, `R48`, `R53`, `R56-B`, `R66`)

Index: [AGENTS.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/AGENTS.md) | Prompts: [visual_prompt_spec.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/visual_prompt_spec.md), [neuro_diorama_rules.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/neuro_diorama_rules.md) | Code: [`pipeline/flow_prompt_builder.py`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/flow_prompt_builder.py), [`pipeline/depiction_rules.py`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/depiction_rules.py)

## R66 — Active `porcelain_cinematic_v7` Contained Living 4-Color 3D Brain (`PORCELAIN_V7_BRAIN_RENDER_MODES`)
- **Anchor**: Bound to per-project `ref_brain_master.png` (`porcelain_living_brain`, except macro `bounded_micro_channel`); neutral test fixtures in `BCI_Shorts_Channel/reference_style_anchors/lowpoly_v7_refs/`.
- **4 Render Modes**: `cortical_vascular_whole`, `sagittal_coronal_cutaway`, `frosted_glass_subcortical_xray`, `bounded_micro_channel`.
- **Hard Containment**: Zero uncontained neon-green slime/mist (`PORCELAIN_V7_NEON_GREEN_SPILL_MAX`), margin saturation `<= PORCELAIN_V7_BRAIN_MARGIN_SAT_MAX`, zero flying sparks/particles (`R53`), zero in-scene AI text (use programmatic ASS `AnatomyLabel`).

## R21 — 4-Color Subsurface Anatomy Code (`COLOR_CODE`)
Unaffected brain tissue stays **matte-white porcelain**; only 4 functional subsurface colors are permitted:
| Color Token | Role | `visual_plan` Field |
|---|---|---|
| `crimson-red` | Damaged, severed, suppressed, or overloaded lesion/tract | `crisis_region` + `crisis_lesion` |
| `soft cyan-blue` / `electric cyan-blue` | Primary active sensory, target, or executive hub | `target_region` |
| `warm amber-gold` | Intact, spared, or compensatory pathway | `compensatory_region` |
| `clear cyan-blue` / `warm amber-gold` stream | Contained luminous fluid stream strictly inside white-matter channel walls | `signal_path`, `mechanism_steps` |

## R38 & R53 — Realistic Anatomy, Contained Channels & 100% Positive Prompting
- **Real Neuroanatomy Only**: Depict true structures (`gyri and sulci`, `almond-shaped amygdala`, `curved seahorse-shaped hippocampus`, `ventromedial prefrontal cortex`, `fusiform gyrus`, `white-matter tracts`). Real BCI implants (`Utah microelectrode array`, `flexible Neuralink polymer threads`, `subdural ECoG electrode grid`) allowed on BCI topics only.
- **Zero Metaphor Props**: Clockwork, gears, tape reels, scales, shutters, coins, and bills are banned (`BANNED_PROMPT_TOKENS`).
- **100% Positive Prompts**: Never write negative VFX disclaimers (`no particles`, `zero sparks`, `never scatter`) in generator prompts; enforce VFX bans (`particles`, `sparks`, `scatter into space`, `fireworks`, `flashing`) in Python `validate_flow_prompts`.
- **Legacy v4 5-Stage Cutaway (`Clip 4–9`)**: `Clip 4 crisis` (cranium dive into bright white studio gallery cross-section, `crimson-red` + `soft cyan-blue`) -> `Clip 5 pivot` (orbit, `amber-gold` channel opens) -> `Clip 6 step1` (macro contained stream inside channel wall) -> `Clip 7 step2` (pooling at `crimson-red` edge or clearing buildup) -> `Clip 8 step3` (full cutaway circuit reveal) -> `Clip 9 breakthrough` (cranium pull-out).

## R48 — Brain <-> Behavior Alignment
On-screen regions (`target_region`, `crisis_region`, `compensatory_region`, `signal_path`) MUST directly explain the setup symptom and breakthrough/takeaway behavior.

## R56-B — Legacy v6 Dark-Void Modes (`DIORAMA_BRAIN_RENDER_MODES`)
Legacy Schema v6 `neuro_diorama`: `matte_white_cortical_sulcal_glow` (opaque chalk-white brain, sulcal glow) and `translucent_smoked_glass_subcortical_xray` (frosted smoked-glass cortex revealing glowing deep subcortical structures) isolated in midnight-navy void.
