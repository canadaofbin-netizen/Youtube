---
trigger: model_decision
description: "Load when designing or validating Solo Siren narration (R76), R82 dual-speed pacing & 120ft drones, R86 Semantic Beat Cards, or R87-H 0-3s hook recovery & 118pt HookTitle (R76, R82, R86, R87-H)."
---

# Hook Recovery, Dual-Speed Pacing & Semantic Beat Cards (`R76`, `R82`, `R86`, `R87-H`)

Index: [AGENTS.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/AGENTS.md) | Constants: [production_constants.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/production_constants.md) | Brain & Arrows: [brain_depiction_rules.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/brain_depiction_rules.md), [arrows_callouts_motion_rules.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/arrows_callouts_motion_rules.md)

## R76 / R76-P — Solo `Siren` Narrator (`el_siren_v4`)
- `100%` of spoken narration uses ElevenLabs `v4` `Siren` (`ELEVENLABS_VOICE_SIREN_ID = "eXpIbVcVbLo8ZJQDlDnl"`, `el_siren_v4`), `0` foil voices, `0` secondary mascot cameos (`EXPRESSIVE_V8_CAMEO_COUNT_PER_EPISODE = 0`).

## R82 — Dual-Speed Pacing & Mandatory Institution Aerial Drone
- **Design Targets (`Tier-2` flexible `±0.4s` / `35–62%`)**: Brisk `1.90–4.25s` 2-beat human cuts vs poised `4.20–6.80s` (`42–58%` share, `<= 15°` single-plane parallax, zero 90° spin) 3D brain cuts across `18–28` cuts.
- **Mandatory `S01–S04` `120ft` Institution Drone (`Tier-1 #7`)**: Real campus/hospital/institute aerial shot with `R85_DRONE_ALTITUDE_LOCK_CLAUSE` (`"120ft altitude, figures read as tiny dots"`) and zero ground walking verbs (`walk`, `stride`, `jog`).

## R86 — Semantic Beat Contract (`Tier-1 #5 & #6`, `pipeline/flow_prompt_builder.py`, `pipeline/prompt_quality_v5.py`)
- **Required Per-Cut Beat Card**: `claim`, `viewer_must_understand`, `visual_proof_type` (`mechanism`, `comparison`, `causal_arrow`, `scale`, `misconception_flip`, `data`, `metaphor`, `reaction` `<=2`/ep; `0` `decorative`), `visual_register` (`story` 2.5D vinyl with `0` overlays vs `diagram` 31-brain / `R80` arrow / `R70` stamp on clean backdrop), `concrete_referent` (in `scene`), `metaphor_continuity_id` (`3–5` cuts + `bridge_element`), `concept_id` + `state_delta` (`0` zero-delta brain repeats), 3-step `misconception_flip` (`mechanism_seed`), `< 3` consecutive identical proof types, and `anti_filler_check`.

## R87-H — `0.0–3.0s` Hook Recovery & 3-App Safe Zone (`Ep #13+`)
- **`R87-H1` (`Cut #1`)**: Require `hook_visual_mode ∈ {mode1_daily_xray_shock, mode2_instant_brain_shock, bizarre_prop_interrupt}`, `1.90–2.60s` `Cut #1`, static domestic sitting/tea/temple-rub ban, thumbnail↔`Cut #1` referent match, and Lock 3 `J01–J06` or `A01–A19` canonical binding (`t=0.0s` Mode 1/2 hook exempt from early-brain-reveal errors).
- **`R87-H2` (`S01`)**: Default `opening_mode="immediate_brain_shock"` (`bizarre_experiment`, `paradox_action`), ban `"Why do/does/did"` / `"How come"` / `"Imagine"` / `"Have you ever"` / `"Did you know"` and `?` on `S01`, `6–12` words, `P_R87_s01_duration <= 3.50s` (`warn > 3.10s`).
- **`R87-H3` (3-App Safe Zone)**: Emit `0.00–2.20s` ASS `HookTitle` (`118pt`, white+`#FFE14A`, `Y=250–415px`, `X=85–905px`, `{\fad(0,120)}`); `Default` v8 ASS `82pt`, `Outline=5.5`, `Shadow=1.5`, `MarginV=510`, `MarginR=165`, `<= 3` words, `1` `#FFE600` keyword highlight.
