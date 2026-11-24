---
trigger: model_decision
description: "Load when building Audio-First 1:1 Zero-Reuse EDLs, ElevenLabs v4 Solo Siren mixes, 82pt #FFE600 MarginV=510 ASS subtitles, 5-archetype titles, or running prompt-gate (R56-R61)."
---

# Diorama Assembly, Subtitles & Titles (`R56–R61`)

Index: [AGENTS.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/AGENTS.md) | Constants: [production_constants.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/production_constants.md) | Pacing & Hook: [hook_pacing_beatcard_rules.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/hook_pacing_beatcard_rules.md) | Retired: [retired_rules_2026-11-18.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/_archive/retired_rules_2026-11-18.md)

## R56 — Zero-Flesh Vinyl Cast & Zero In-Scene AI Text (`Tier-1 #2 & #9`)
- **[Tier-1 Hard Block]**: Zero photorealistic human skin, hair, beards/stubble, photoreal eyeballs/lips, department-store mannequins, or burned-in AI gibberish text/plaques/watermarks (`"9:16"`, `"museum"`, `"plinth"`, `"sign"`, `"label"` banned in scene prompts unless in `<=2`-token `diegetic_text_allowlist`).
- **[Tier-2 Advisory (`R56-C`)]**: Smooth earless/noseless silhouette preferred; `v8_ep13+` enforces **`R88` faceless architectural porcelain (`0` eyes/mouth/eyebrows)**, while minor vinyl contours on frozen `Ep #01–#12` (`PRE_R88_FROZEN_V8_PROJECTS`) never reject a historical clip.

## R57 — 6-Act US English Spine & Debate Ignition
- **100% US English (`en-US`)**: Plain conversational storytelling (`DIORAMA_BANNED_SLOGAN_OPENERS`, `DIORAMA_BANNED_WEAK_HOOK_PREFIXES` `"Imagine..."`, `DIORAMA_BANNED_AI_CLICHES` banned). Shorts ceiling `<= SHORTS_HARD_CEILING_SEC` (`<= 88.0s` on active `R75` `v8`).

## R58 — Audio-First Master Clock & 1:1 Zero-Reuse EDL (`Tier-1 #10`)
- Synthesize `elevenlabs_v4` (`DIORAMA_TTS_ENGINE="eleven_v4"`, Solo `Siren`) voiceover master first (`HISTORICAL_LEGACY_VOICE_PRESET_IDS` frozen on legacy archives; zero `asetrate` pitch shifts).
- Build 1:1 Zero-Reuse EDL (`05_assembly/edit_decision_list.json`, `max_clip_reuse == 1`) across sharded Flow tabs (`<= FLOW_MAX_PARALLEL_BATCH_SIZE`).

## R59 — Documentary Stereo Score & Frame-Grid ASS Subtitles (`Tier-1 #10`)
- 2ch stereo score (`-14.0 LUFS` target on `v8`, `<= -1.0 dBTP`, zero digital UI cut ticks).
- Bundled `AABCondensed-Black.ttf` ASS subtitles (`v8` `Default`: `82pt`, `Outline=5.5`, `Shadow=1.5`, `MarginV = EXPRESSIVE_V8_SUBTITLE_MARGIN_V = 510`, `MarginR=165`, `<= 3` words/event with `1` `#FFE600` keyword highlight + `0.00–2.20s` `118pt HookTitle` `#FFE14A` accent) + programmatic `AnatomyLabel` / `DataStamp` overlays with `0px` overlap.

## R60 — 5-Archetype US English Title Formula (`Tier-2`)
- Plain US English curiosity title (`<= R68_TITLE_MAX_CHARS` `55` chars / `4–8` words on `v8`; `<= TITLE_MAX_CHARS_DIORAMA` on `v7`), zero all-caps spam, zero claims beyond verified DOI.

## R61 — Pre-Flow Production Gate (`main.py prompt-gate`)
- Validates `R1` DOI/fact accuracy, `R85` drone/viewpoint/zero-Blender locks, `R86` Semantic Beat Contract, `R87` hook/arrow eligibility, zero AI text triggers, and `R65` thumbnail spec before Flow generation.
