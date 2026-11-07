# Real-World Scene & 2-Beat Prop Acting (`R14-A`, `R47`)

Index: [AGENTS.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/AGENTS.md) | Prompts: [visual_prompt_spec.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/visual_prompt_spec.md), [neuro_diorama_rules.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/neuro_diorama_rules.md) | Code: [`pipeline/flow_prompt_builder.py`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/flow_prompt_builder.py), [`pipeline/depiction_rules.py`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/depiction_rules.py)

## R14-A (Environment & Lighting)
- **High-Key Studio / Lab Staging**: Bright minimalist studio, clinical, or period laboratory world (`PORCELAIN_V7_WORLD_STYLE` / `PORCELAIN_V7_OPTICS_LOCK` on `porcelain_cinematic_v7`; bright minimalist indoor room on classic v4/v5) — zero dark noir voids (`PORCELAIN_V7_DARK_VOID_RATIO_MAX`).
- **Focused Props (`environment_props`, `scale_anchor_object`)**: 1–3 concrete period-accurate interactive props per room (e.g. `heavy steel tamping rod`, `switch console`, `mirror box`, `brass metronome`) so motion budget concentrates on hands and prop physics.

## R47 — 2-Beat Physical Action Chain (`validate_character_motion`)
Every character clip MUST pair an active body/hand verb on a prop with an immediate physical consequence or partner reaction (`<= 14 words` in v4 `mannequin_actions`):
`[Beat 1: Concrete Hand/Arm/Body Verb + Prop] -> [Beat 2: Physical State Change or Partner Reaction]`
- **Valid**: `"strikes a heavy steel rod down onto the workbench as a bright spark flashes"`, `"lifts the steel rod with both hands and places it onto the display stand"`.
- **Banned Static Poses**: `"sits upright"`, `"stands calmly"`, `"freezes with a tense posture"`, `"turns its head away in silent confusion"` (rejected by `validate_character_motion()`).
