---
trigger: model_decision
description: "Load when staging 2.5D miniature diorama environments, atmospheric lighting, interactive experimental props, or 2-Beat physical prop action chains (R14-A, R47, R68, R86)."
---

# Real-World Scene & 2-Beat Prop Acting (`R14-A`, `R47`, `R68`, `R86`)

Index: [AGENTS.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/AGENTS.md) | Prompts: [visual_prompt_spec.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/visual_prompt_spec.md), [real_world_drone_refs_rules.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/real_world_drone_refs_rules.md) | Code: [`pipeline/flow_prompt_builder.py`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/flow_prompt_builder.py), [`pipeline/depiction_rules.py`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/depiction_rules.py)

## R14-A — Environment, `P0-2` Selective Color & Narrative Lighting Arc
- **Profile-Matched Lighting (`v7` High-Key vs `v8` Narrative Atmosphere)**:
  - `porcelain_cinematic_v7`: High-key bright minimalist studio/period lab (`PORCELAIN_V7_WORLD_STYLE` / `PORCELAIN_V7_OPTICS_LOCK`) — zero dark noir voids.
  - `expressive_25d_v8` (`R68`): Natively preserves atmospheric/night/dramatic lighting (`luma >= 26.0`, `dark_v35 <= 0.68`, `EXPRESSIVE_V8_MIN_LUMA = 28.0`), blocking only `< 26.0` pitch-black render errors.
- **`P0-2` Selective Color Isolation & Story Lighting Arc**: On non-brain 2.5D lifestyle/lab cuts, pair a **warm muted low-saturation architectural backdrop isolating the vivid full-color hero prop** (never full-frame monochrome, avoiding `desaturated_grayscale_v7`), and follow the **Act lighting arc** (crisp daylight Act 1 → shadowed moody Act 2/conflict → `#040711` brain void Act 3–4 → crisp golden rim Act 5–6).
- **Focused Props (`environment_props`, `scale_anchor_object`)**: 1–3 concrete interactive props per room so motion concentrates on hands and prop physics.

## R47 — 2-Beat Physical Action Chain (`validate_character_motion`)
Every character clip MUST pair an active body/hand verb on a prop with an immediate physical consequence or partner reaction (`<= 14 words` in v4 `mannequin_actions`):
`[Beat 1: Concrete Hand/Arm/Body Verb + Prop] -> [Beat 2: Physical State Change or Partner Reaction]`
- **Valid**: `"strikes a heavy steel rod down onto the workbench as a bright spark flashes"`, `"lifts the steel rod with both hands and places it onto the display stand"`.
- **Banned Static Poses**: `"sits upright"`, `"stands calmly"`, `"freezes with a tense posture"`, `"turns its head away in silent confusion"` (rejected by `validate_character_motion()`).
