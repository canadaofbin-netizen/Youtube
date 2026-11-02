# Rule: Brain, Anatomy & 5-Stage Contained Channel Depiction Protocol (`31_O2CmlKOk` Schema v4)

Parent Master Index: [AGENTS.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/AGENTS.md) · Composer Spec: [visual_prompt_spec.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/visual_prompt_spec.md) · Code: [`pipeline/flow_prompt_builder.py`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/flow_prompt_builder.py)

Single source of truth for depicting the 3D brain interior (`Clip 4–8`: `crisis`, `pivot`, `step1`, `step2`, `step3`), anatomical structures, and the `31_O2CmlKOk` 5-stage architectural cross-section cutaway & contained fluid/channel mechanism formula.

## R38 & R53 — 5-Stage Brain Cutaway & Contained Channel Stream (`31_O2CmlKOk` Standard)
- **Space & Material**: Inside brain clips (`Clip 4–8`), the camera operates inside a **bright white studio gallery** (`bright studio daylight`) holding an **architectural cross-section cutaway of a realistic matte-white 3D brain with visible gyri and sulci**.
- **100% Positive Prompting Rule**:
  - **NEVER** put negative words (`no particles`, `zero sparks`, `never scatter`) inside prompts sent to the video generator; write 100% positive descriptions of the smooth, contained internal flow.
  - Banned VFX words (`particles`, `sparks`, `scatter into space`, `crash and scatter`, `fireworks`, `flashing`, `electric`) are enforced inside Python `validate_flow_prompts` only.
- **5-Stage Visual-Explanatory Formula (`Clip 4 -> 5 -> 6 -> 7 -> 8 -> 9`)**:
  1. **Clip 4 (`crisis` — Cranium Dive into Architectural Cross-Section Cutaway)**: Dive smoothly through the translucent frosted-glass cranium into a bright white studio gallery holding an **architectural cross-section cutaway** of a realistic matte-white 3D brain with visible gyri and sulci, zooming into the internal problem zone shaded deep `crimson-red` alongside `soft cyan-blue` structures.
  2. **Clip 5 (`pivot` — 3D Cross-Section Orbit & Channel Opening)**: Smoothly orbit inside the 3D cross-section contrasting the `crimson-red` blocked/severed zone and `soft cyan-blue` structure as the key anatomical channels/tracts warm to `amber-gold` and open, pushing in closer.
  3. **Clip 6 (`step1` — Macro Contained Stream Inside Channel)**: Macro view deep inside the folded brain tissue and translucent anatomical channel (`inside the white-matter channel`), showing a **smooth, contained fluid-like stream** (`smooth warm amber-gold` or `clear cyan-blue` luminous stream strictly inside the anatomical channel wall) flowing steadily inward as the camera tracks alongside it.
  4. **Clip 7 (`step2` — Macro Physical Mechanism Inside Channel)**: Macro tracking following that smooth internal stream inside the channel to show the physical mechanism (pooling and fading softly against the severed `crimson-red` channel edge inside the tissue in disconnection topics, or washing away `crimson-red` buildup in clearance topics).
  5. **Clip 8 (`step3` — Full 3D Cutaway Circuit Reveal)**: Pull back to reveal the complete 3D anatomical circuit inside the matte-white cutaway brain showing the clear resulting state (`soft cyan-blue` origin, `crimson-red` quiet lesion, steady `warm amber-gold` flow gliding inside the intact channels) turning slowly in bright studio daylight.
  6. **Clip 9 (`breakthrough` — Cranium Pull-Out)**: Smooth pull-out from the brain back through the translucent frosted-glass cranium into the bright minimalist white studio room.
- **Realistic Anatomy Only**: Depict real neuroanatomical structures (`gyri and sulci`, `almond-shaped amygdala`, `curved seahorse-shaped hippocampus`, `ventromedial prefrontal cortex`, `fusiform gyrus`, `white-matter tracts`).
- **Banned Metaphor Props**: Clockwork, gears, tape reels, balance scales, camera shutters, coins, or dollar bills are strictly forbidden (`BANNED_PROMPT_TOKENS`).
- **Real BCI Hardware Exception**: For BCI topics only, real clinical implants (`Utah microelectrode array`, `flexible Neuralink polymer threads`, `subdural ECoG electrode grid`) are rendered realistically on the target cortex.

## R21 — 4-Point Subsurface Colour Code (`COLOR_CODE` in `pipeline/flow_prompt_builder.py`)
All brain tissue remains **matte-white porcelain**; only the following **4 functional colours** (`COLOR_CODE`) are used across `Clip 2` and `Clip 4–10`:

| Colour Token | Functional Role | `visual_plan` Field | Usage in Prompts |
|---|---|---|---|
| **`crimson-red`** | Damaged, severed, suppressed, or overloaded region | `crisis_region` + `crisis_lesion` | Shows the lesion, severed white-matter channel, or bottleneck where incoming flow pools (`Clip 2, 4, 5, 7, 8`). |
| **`soft cyan-blue`** | Primary active target / sensory / executive hub | `target_region` | Illuminates the primary region receiving or processing the signal (`Clip 2, 4, 5, 6, 7, 8, 10`). |
| **`warm amber-gold`** | Intact, spared, or compensatory neural pathway | `compensatory_region` | Warms and opens in `Clip 5 (pivot)` and `Clip 8 (step3)` to show the intact/compensatory channel, remaining visible inside the cranium in `Clip 9–10`. |
| **`clear cyan-blue` / `warm amber-gold` stream** | Smooth contained fluid/luminous stream inside anatomical channels | `signal_path`, `mechanism_steps` | Flows smoothly inside the translucent white-matter channel walls (`step1`), pools softly at the `crimson-red` edge (`step2`), and glides steadily through intact channels (`step3`). |

## R48 — Brain ↔ Story Alignment
- The regions depicted in `Clip 4–8` (`target_region`, `crisis_region`, `compensatory_region`, `signal_path`) MUST directly explain the behavioural symptom shown in `Clip 1–3` and the breakthrough/conclusion shown in `Clip 9–10`.

## R56-B — `neuro_diorama` Schema v6 2-Mode Isolated Dark-Void 3D Brain Visualization (`DIORAMA_BRAIN_RENDER_MODES`)
For **`neuro_diorama`** (`DEFAULT_PRODUCTION_PROFILE`, `ArchitecturalBrainMaquetteRule` in [`pipeline/depiction_rules.py`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/depiction_rules.py)), brain shots match the golden visual anchors in `BCI_Shorts_Channel/reference_style_anchors/brain_v6_refs/` and float **isolated in a deep midnight-navy / black void with zero background tables or furniture**:
1. **`matte_white_cortical_sulcal_glow` (Cortical Regions — `brain_ref_01`, `brain_ref_03`)**:
   - Opaque sculpted **matte-white / soft chalk-white 3D whole anatomical brain** (both hemispheres, gyri, sulci, cerebellum, brainstem).
   - Localized **soft cyan-blue subsurface illumination** highlights ONLY the active target lobe, glowing brightest deep inside the **sulcal creases/grooves** while unaffected cortex stays calm matte-white and brainstem/lesion tracts glow **soft crimson-red** (or compensatory pathways **warm amber-gold**).
2. **`translucent_smoked_glass_subcortical_xray` (Deep Subcortical Structures — `brain_ref_02`)**:
   - Intact whole 3D brain rendered with a **semi-translucent frosted smoked-glass X-ray outer cerebral cortex and cerebellum** with crisp rim-lit gyri contours.
   - Deep 3D subcortical structures (`hippocampus`, `amygdala`, `thalamus`, `basal ganglia`) glow inside the glass cortex in **smooth volumetric cyan-blue luminescence**, paired with **soft crimson-red** descending brainstem pathways and zero flying sparks/particles (`R53`) and zero in-scene AI text.
