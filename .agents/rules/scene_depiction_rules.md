# Rule: Real-World Scene, Prop & 2-Beat Character Acting Protocol (`31_O2CmlKOk` Schema v4)

Parent Master Index: [AGENTS.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/AGENTS.md) · Composer Spec: [visual_prompt_spec.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/visual_prompt_spec.md) · Code: [`pipeline/flow_prompt_builder.py`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/flow_prompt_builder.py)

Single source of truth for staging real-room scenes (`Clip 1, 2, 3, 9, 10`) and enforcing expressive **2-Beat physical character movement** within the `50–80 word` Schema v4 prompt budget.

## R14-A (Environment, Lighting & Scale) — Minimalist Bright Studio / Clinical Room
- **Minimalist Bright Indoor Setting**: Real-room clips (`setup`, `symptom`, `failure`, `breakthrough`, `conclusion`) take place in a **minimalist bright studio, clinical, or laboratory room** (`a minimalist bright studio room`, `a minimalist bright psychology laboratory room`) so Google Flow Omni 1.1 focuses 100% of its motion budget on the porcelain mannequins and props rather than complex outdoor backgrounds.
- **1–2 Interactive Props (`environment_props` & `scale_anchor_object`)**: Each room contains 1–3 concrete, interactive props (e.g., `heavy steel tamping rod`, `wooden workbench`, `high-voltage switch console`, `brass metronome bell`, `glass collection tube`, `white basketball`).
- **Bright Daylight / Soft Studio Lighting**: Lit with clean `Bright daylight lighting` or `Soft studio light` — never dark noir shadows.

## R47 — 2-Beat Physical Action Chain (`mannequin_actions`, `<= 14 words`)
To eliminate stiff, statue-like mannequins while keeping every prompt concise (`50–80 words` total), every character clip (`Clip 1, 2, 3, 9, 10`) MUST use a **2-Beat physical action chain**:

```text
[Beat 1: Concrete Hand / Arm / Body Verb Manipulating a Prop]  -->  [Beat 2: Immediate Physical Consequence or Partner Reaction]
```

### Approved Examples (`pipeline/topics_catalog.py`)
- **Clip 1 (`setup`)**: `"strikes a heavy steel rod down onto the workbench as a bright spark flashes"` (`Phineas Gage`)
- **Clip 2 (`symptom`)**: `"drops his notebook onto the floor and slams his porcelain fist against the table"` (`Phineas Gage`)
- **Clip 3 (`failure`)**: `"sweeps a wooden blueprint tray off the workbench and shoves his chair backward"` (`Phineas Gage`)
- **Clip 9 (`breakthrough`)**: `"lifts the steel rod with both hands and places it onto the display stand"` (`Phineas Gage`)
- **Clip 10 (`conclusion`)**: `"sits on a wooden coach bench and pulls taut leather reins with steady hands"` (`Phineas Gage`)

### Strictly Banned Static Poses (`validate_character_motion`)
- Static-only phrases (`"sits upright at the main table"`, `"stands calmly"`, `"freezes with a tense posture"`, `"turns its head away in silent confusion"`, `"sits calmly beside the researcher"`) without an active physical hand/arm/body prop verb are rejected by `validate_character_motion()` in [`pipeline/flow_prompt_builder.py`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/flow_prompt_builder.py).
