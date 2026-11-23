---
trigger: model_decision
description: "Load when working on ElevenLabs v4 Solo Siren TTS synthesis, audio master clock & LUFS normalization, stereo room ambience/BGM, ASS subtitles, or prosody QA (R49, R58, R59, R63-P)."
---

# Audio & Assembly Rules (`R49`, `R58`, `R59`, `R63-P`)

Index: [AGENTS.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/AGENTS.md) | Constants: [production_constants.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/production_constants.md) | Core Spec: [diorama_assembly_subtitles_rules.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/diorama_assembly_subtitles_rules.md) | Retired (`R13, R16, R17, R39, R41, R43`): [retired_rules_2026-11-18.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/_archive/retired_rules_2026-11-18.md)

## Active `elevenlabs_v4` Solo `Siren` & Audio-First Assembly
- **Voice Lock (`R49`, `R76-1`)**: `DEFAULT_DIORAMA_VOICE_PRESET="elevenlabs_v4"` (`DIORAMA_TTS_ENGINE="eleven_v4"`, solo `Siren` `el_siren_v4` `eXpIbVcVbLo8ZJQDlDnl` on active `v8`; 3x transient HTTP retry, fail-fast on auth/quota error with zero silent neural/Kokoro downgrade; `HISTORICAL_LEGACY_VOICE_PRESET_IDS` frozen on legacy Public archives). TTS-safe text normalization via `R49-T` (`to_expressive_tts_text` / `to_display_text`).
- **Master Clock & Stereo Mux (`R58`, `R59`)**: Audio-first 1:1 Zero-Reuse EDL (`30fps` on `v8`, `24fps` on `v7`), 2ch stereo mix (`-14.0 LUFS` on `v8`, `<= -1.0 dBTP` via `DIORAMA_MUX_TRUE_PEAK_LIMITER` + `DIORAMA_V7_MASTER_DEESSER`, zero digital UI cut ticks), bundled `AABCondensed-Black.ttf` ASS subtitles (`82pt`, `Outline=5.5`, `Shadow=1.5`, `MarginV=510`, `<= 3` words/event with `#FFE600` keyword highlight + `0.00–2.20s` `118pt HookTitle` `#FFE14A`).
- **Prosody QA (`R63-P`, `main.py prosody-qa`)**: `P7` (zero speech truncation/clipping) and `P9` (zero dead air / ASR transcript match) are **Tier-1 Blockers**; `P1–P6, P8, P10, P11` are **Tier-2 Advisories**.
