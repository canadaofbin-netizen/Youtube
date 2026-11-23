---
name: youtube-script
description: Gear 2 Neuro-Diorama active expressive_25d_v8 (R68-R87) script, visual_plan, R65 v4 thumbnail spec, and Google Flow prompt authoring + prompt-gate validation.
---

# youtube-script (AI-Only Spec — Active `expressive_25d_v8`)

SSOT: [AGENTS.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/AGENTS.md) | [hook_pacing_beatcard_rules.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/hook_pacing_beatcard_rules.md) | [arrows_callouts_motion_rules.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/arrows_callouts_motion_rules.md) | [real_world_drone_refs_rules.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/real_world_drone_refs_rules.md) | [production_constants.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/production_constants.md) | Legacy `v7`: [legacy_v7.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/skills/youtube-script/references/legacy_v7.md)

## 1. Script Contract (`script.json`, Schema 8, `en-US`, `R68 / R73 / R76 / R87-H`)
- **Duration & Voice**: `61.5–86.0s` (`<= 88.0s` `R75` ceiling on `shorts_expressive_v8`: `15–22` sentences, `<= 22w`/sentence, `FK <= 6.2`, `0.36–0.42s` pause after `S01`). `100%` Solo `Siren` (`elevenlabs_v4` `"el_siren_v4"`, `ELEVENLABS_VOICE_SIREN_ID = "eXpIbVcVbLo8ZJQDlDnl"`, `0` foil lines, `0` mascot cameos), 5-tone `prosody_gears` (`surprised_lift`, `insider_reveal`, `hushed_suspense`, `deadpan_drop`, `action`).
- **4-Stage Emotional Curve & `1 Core Fact per 15s` Mute Check**:
  1. **`0–3s` Visceral Shock Hook (`S01`, `R87-H`)**: `opening_mode="immediate_brain_shock"` (`bizarre_experiment`, `paradox_action`; rotate `EXPRESSIVE_V8_US_NATIVE_OPENING_MODES`; ban `"In [Year]..."`, `"Why do/does/did"`, `"How come"`, `"Imagine"`, `"Have you ever"`, `"Did you know"`, and `?` on `S01`), `6–12w`, `<= 3.50s`, `1.90–2.60s` `Cut #1` (`mode1_daily_xray_shock`, `mode2_instant_brain_shock`, `bizarre_prop_interrupt`; `J01–J06` / `A01–A19` Lock 3; `118pt HookTitle` `<= 4w`/`24c`; `"Mute & Hide Name Test"` at `0.0s`).
  2. **Paradox / Failed Intuition (`S02–S08`)**: `S02–S04` real institution `120ft` drone bridge (`R72`) + everyday failed intuition (`0` AI text).
  3. **Multi-Scale `Ep #31` Brain Mechanism (`S09–S16`)**: Control condition (`R87-A` `C01b–C03b` spatial arrows if `spatial_arrow_eligible=True`, else `Category K` `K01–K06` / `A12`), `<= 2` `1x1` `mode="study"` `data_stamps` (`R70-M`), `6`-scale `Ep #31` (`31_O2CmlKOk`) brain cuts (`4.20–6.80s`), `<= 2` plain-first glossed neuro terms (`"Emotional Center — amygdala"`), US bridges (`"In fact,"`, `"That's because"`, `"Instead,"`, `"Turns out,"`, `"But here's the catch:"`), `0` `EXPRESSIVE_V8_BANNED_AI_CLICHES`.
  4. **1-Line Callback Mic-Drop (`S17–S20`, `R73-5`)**: Everyday mirror + punchy `ending_mode: "mic_drop"` (no `?`) or `"seamless_loop"` callback.
- **`1 Core Fact per 15s` Mute Visual Check**: On muted `posthoc_viewer_strips`, 1 core fact per `~15s` must read visually via `R70-M` Data Stamps + `R81` `PatrickHand` callouts + `R86` Beat Cards (`0%` AI scene text).
- **`R68-D` Metadata**: `title` `4–8w` (`<= 55` chars, `0` `#`); `viewer_description` `55–135w` (**2 plain paragraphs** + `Research: <Author> et al., <Institution> (<Year>).`; `0` `#`/DOIs/`—`/`;`/bullets/`R68D_BANNED_AI_CLICHES`; `ai_content_declaration=True`); `debate_question` = 1 casual `?`.

## 2. Visual Plan Contract (`visual_plan.json`, `R68–R87`)
- **Dual-Speed 1:1 EDL (`R82`)**: `18–28` unique `30fps` `VIDEO_FRAMES` clips (`R82_CLIP_COUNT_RANGE`). Human cuts `1.90–4.25s` (2-beat relays, `>= 4` cuts in `0–15s`, `~35–45%` `hero_low_angle` alternating `disembodied push-in ↔ smooth pull-back`, `>= 1` `S01–S03` `120ft` drone, `>= 25%` outdoor/architectural); `100%` Flow `Ep #31` brain cuts (`#9CA5AC–#C3C9CE` + `#27D8FF` over `#040711`) `4.20–6.80s` (`42–58%` share, `<= 15°` parallax, `0` spin, XL `82–84px` `PatrickHand` callouts).
- **Cast, Selective Color (`P0-2`) & Prompt Diet (`P0-1`)**: Bald matte cream-white (`#F5F2EB`) 2.5D vinyl + 2D ink step-snap (`R79-M`), `EXPRESSIVE_V8_CAMEO_COUNT_PER_EPISODE = 0`; warm muted low-sat backdrop isolating vivid hero prop + Act lighting arc. `ExpressiveV8PromptComposer` (`18–64w`) ends `"Silent voice track."` + `FLOW_CAMERA_HARDWARE_NEGATIVE_GUARD` (`"No voiceover, no narration, no background music, no lip movement."`).
- **Beat Card (`R86`)**: Required per-cut `claim`, `viewer_must_understand`, `visual_proof_type`, `visual_register`, `concrete_referent`, `concept_id` + `state_delta`, `< 3` consecutive identical proof types, `<= 2` `reaction`, `0` `decorative`.
- **18 Grammars & 12 Transitions (`config.py`)**:
  - Grammars: `expressive_vinyl_world`, `expressive_exterior_establishing`, `expressive_hands_closeup`, `expressive_pov_hands`, `expressive_xray_brain`, `brain_simulator_3d`, `spatial_3d_arrow_diorama`, `expressive_literal_analogy`, `expressive_cameo_world`, `expressive_split_contrast`, `expressive_reaction_closeup`, `axial_portal_dive`, `xray_peel_micro`, `ghost_twin_offset`, `lid_lift_reveal`, `locked_exploded_vs_shatter`, `blueprint_3d_extrusion`, `architectural_cutaway_portal`.
  - Transitions: `daisy_chain_bridge`, `seamless_relay_cut`, `occlusion_wipe`, `action_impact_cut`, `dissolve_6f`, `dissolve_8f`, `dissolve_12f`, `dissolve_15f`, `match_cut_bridge`, `split_screen_wipe`, `portal_crash_zoom_10f`, `whip_pan_blur_8f`.
- **Refs & `R65 v4` Thumbnail**: `populate_expressive_v8_reference_contract(plan, dossier_dir)` (`Ingredients`-only from `99` Canonical slots; `B01–B04` Frame-0 banned; 3 per-ep deltas) + `R65 v4` `thumbnail` (`in_skull_cutaway_split_v4`, `50/50`, `<= 3w`, `cover_sentence_index: 1`).

## 3. Render & Gate
1. Python script: `build_flow_prompts(plan, sentences)` + `write_flow_prompts_json(draft_dir, clips)` + `build_reference_image_specs(plan, sentences)`.
2. `/home/canadaofbin/hermes-venv/bin/python -X utf8 main.py prompt-gate --dir <dir>` -> `"passed": true, "issues": []`.
