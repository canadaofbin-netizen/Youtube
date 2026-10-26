# Rule: Brain, Anatomy & 4-Point Signal Depiction Protocol (`31_O2CmlKOk` Schema v4)

Parent Master Index: [AGENTS.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/AGENTS.md) · Composer Spec: [visual_prompt_spec.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/visual_prompt_spec.md) · Code: [`pipeline/flow_prompt_builder.py`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/flow_prompt_builder.py)

Single source of truth for depicting the 3D brain interior (`Clip 4–8`: `crisis`, `pivot`, `step1`, `step2`, `step3`), anatomical structures, and the proven `31_O2CmlKOk` 4-point colour code.

## R38 — Bright White Studio Gallery 3D Matte-White Brain (`31_O2CmlKOk` Standard)
- **Space & Material**: Inside brain clips (`Clip 4–8`), the camera operates inside a **bright white studio gallery** (`bright studio daylight`) holding a **realistic matte-white 3D brain with visible gyri and sulci**.
- **Seamless Cranium Dive & Pull-Out (`Clip 4` & `Clip 9`)**:
  1. **Clip 4 (`crisis` — Cranium Dive)**: `"The camera dives smoothly through the <subject> mannequin's translucent frosted-glass cranium into a bright white studio gallery holding a realistic matte-white brain with visible gyri and sulci."`
  2. **Clip 5–8 (`pivot`, `step1`, `step2`, `step3` — 3D Brain Mechanism)**: Camera smoothly orbits the target and crisis regions (`pivot`), tracks `bioluminescent green signal particles` along the `signal_path` (`step1`), orbits the `crimson-red` lesion/blockage where particles collide and scatter (`step2`), and pulls back as the full circuit (`electric cyan-blue`, `crimson-red`, `warm amber-gold`, and `bioluminescent green signal stream`) turns slowly in the bright white studio gallery (`step3`).
  3. **Clip 9 (`breakthrough` — Cranium Pull-Out)**: `"The camera pulls smoothly out of the brain, back through the translucent frosted-glass cranium, into the <real_environment>."`
- **Realistic Anatomy Only**: Depict real neuroanatomical structures (`gyri and sulci`, `almond-shaped amygdala`, `seahorse-shaped hippocampus`, `ventromedial prefrontal cortex`, `fusiform gyrus`, `white-matter tracts`).
- **Banned Metaphor Props**: Clockwork, gears, tape reels, balance scales, camera shutters, coins, or dollar bills are strictly forbidden (`BANNED_PROMPT_TOKENS`).
- **Real BCI Hardware Exception**: For BCI topics only, real clinical implants (`Utah microelectrode array`, `flexible Neuralink polymer threads`, `subdural ECoG electrode grid`) are rendered realistically on the target cortex.

## R21 — 4-Point Subsurface Colour Code (`COLOR_CODE` in `pipeline/flow_prompt_builder.py`)
All brain tissue remains **matte-white porcelain**; only the following **4 functional colours** (`COLOR_CODE`) are used across `Clip 2` and `Clip 4–10`:

| Colour Token | Functional Role | `visual_plan` Field | Usage in Prompts |
|---|---|---|---|
| **`crimson-red`** | Damaged, severed, suppressed, or overloaded region | `crisis_region` + `crisis_lesion` | Shows the lesion, severed white-matter bridge, or bottleneck where incoming signals fail (`Clip 2, 4, 5, 7, 8`). |
| **`electric cyan-blue`** | Primary active target / sensory / executive hub | `target_region` | Illuminates the primary region receiving or processing the signal (`Clip 2, 4, 5, 6, 7, 8, 10`). |
| **`warm amber-gold`** | Intact, spared, or compensatory neural pathway | `compensatory_region` | Ignites in `Clip 5 (pivot)` and `Clip 8 (step3)` to show the alternative/intact route, remaining visible inside the cranium in `Clip 9–10`. |
| **`bioluminescent green`** | Active neural signal particles / impulse stream | `signal_path`, `mechanism_steps` | Flows like fluid along `signal_path` (`step1`), collides/scatters at the `crimson-red` lesion (`step2`), and routes cleanly across the `warm amber-gold` pathway (`step3`). |

## R48 — Brain ↔ Story Alignment
- The regions depicted in `Clip 4–8` (`target_region`, `crisis_region`, `compensatory_region`, `signal_path`) MUST directly explain the behavioural symptom shown in `Clip 1–3` and the breakthrough/conclusion shown in `Clip 9–10`.
