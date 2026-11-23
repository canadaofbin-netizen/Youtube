---
trigger: model_decision
description: "Load when configuring expressive_25d_v8 format/transitions, R72 120ft institution aerial drones, R72-R open-license Wikimedia real-world references, or R73 US conversational narration (R68, R72, R72-R, R73)."
---

# `expressive_25d_v8` World, `120ft` Drones, Open-License Refs & US Narration (`R68`, `R72/R72-R`, `R73`)

Index: [AGENTS.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/AGENTS.md) | Constants: [production_constants.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/production_constants.md) | Refs: [reference_depiction_rules.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/reference_depiction_rules.md)

## R68 & R55-B/R58-K/R68-A — Active `expressive_25d_v8` / `shorts_expressive_v8` (`<= 88.0s`, `30fps`)
- **Format & Voice Lock**: Schema `8` (`PROMPT_SCHEMA_VERSION_V8`), `61.5–88.0s` (`SHORTS_EXPRESSIVE_V8_R75_MAX_SEC = 88.0s`), `18–28` clips (`R82_CLIP_COUNT_RANGE`), `30fps` (`EXPRESSIVE_V8_VIDEO_FPS = 30`, `EXPRESSIVE_V8_OUTRO_TAIL_SEC = 0.20`), `MarginV = EXPRESSIVE_V8_SUBTITLE_MARGIN_V = 510` (`82pt` `EXPRESSIVE_V8_SUBTITLE_FONT_SIZE`, `<= 3` words/event `EXPRESSIVE_V8_SUBTITLE_MAX_WORDS`, `#FFE600` highlight + `118pt HookTitle`), `elevenlabs_v4` (`EXPRESSIVE_V8_PROSODY_MODE = "expressive_us_v8"` solo `Siren` `el_siren_v4`), `EXPRESSIVE_V8_CAMEO_COUNT_PER_EPISODE = 0`.
- **Prompt Diet & 12 Transitions**: `ExpressiveV8PromptComposer` context-split (`18–64` words on conditioned cuts); narrative lighting (`luma >= 26.0`, blocking `<22–26` pitch-black); 12 `EXPRESSIVE_V8_TRANSITION_TYPES` (`daisy_chain_bridge`, `seamless_relay_cut`, `occlusion_wipe`, `action_impact_cut`, `dissolve_6f`, `dissolve_8f`, `dissolve_12f`, `dissolve_15f`, `match_cut_bridge`, `split_screen_wipe`, `portal_crash_zoom_10f`, `whip_pan_blur_8f`) guarded by `DQ13_transition_hygiene`.
- **Unified Flow Routing**: `Omni 1.2 Flash` (`macaron_cookie`) handles BOTH single-anchor `Ingredients` (`3s–15s`) AND `Start+End` `VIDEO_FRAMES` (`3s–10s`; `0-credit` fallback `Veo 3.1 - Lite [Lower Priority]`; `Omni 1.1 Flash` retired `2026-12-05`). Camera ratios (`R55-B`) are Tier-2.

## R72 / R72-R — `120ft` Institution Drone & Open-License Real Refs (`Tier-1 #3 & #7`)
- **True `120ft` Drone (`Tier-1 #7`)**: `S01–S04` includes a genuine `~120ft/30m` campus/hospital/institute aerial drone cut (`>= 25%` outdoor human scenes).
- **3-Category Hygiene & Open License (`Tier-1 #3`, `pipeline/real_world_reference_builder.py`)**: Quarantines Wikimedia plates in `/tmp/aab_real_refs/<project_id>/` (`institution`, `urban_setting`, `scientific_apparatus` + `NEUROANATOMY_CUTAWAY_MAP`), generates via `0-credit` Flow `Image`, purges `/tmp`, blocks `FEMA`/ruin/`Waarschuwing`/`mg bottle`/alphabet blocks/`digifoto`, and mandates open licenses (`Public Domain`, `CC0`, `CC-BY`, `CC-BY-SA`) + `source_url` in `real_world_refs_manifest.json` & `reference_provenance.json`.

## R73 — US Native Spoken Narration (`pipeline/prompt_quality_v5.py`)
- Defaults to `EXPRESSIVE_V8_DEFAULT_OPENING_MODE = "immediate_brain_shock"` across `EXPRESSIVE_V8_US_NATIVE_OPENING_MODES` + `S02–S04` institution bridge (`0.42s` pause) + `mic_drop`/`seamless_loop` close; bans `"Have you ever..."`/`"Did you know..."` and AI clichés. `FK <= 6.5`, `<= 22w`/sentence, `<= 2` plain-first glossed neuro terms (`Tier-2`).
