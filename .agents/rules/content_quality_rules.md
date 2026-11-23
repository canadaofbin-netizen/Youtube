---
trigger: model_decision
description: "Load when writing or fact-checking episode scripts, verifying single-study DOI & species accuracy, or checking plain conversational US English readability and TTS normalization (R1, R3, R15, R49-T, R73)."
---

# Content Quality & Narrative Rules (`R1`, `R3`, `R15`, `R49-T`, `R73`)

Index: [AGENTS.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/AGENTS.md) | US Narration Spec: [real_world_drone_refs_rules.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/real_world_drone_refs_rules.md) (`R73`) | Retired (`R2, R2-B, R24, R26, R42`): [retired_rules_2026-11-18.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/_archive/retired_rules_2026-11-18.md)

## R1 — Fact Accuracy, Verified DOI & Species Fidelity (`Tier-1 #1`)
- **Verified DOI & Exact Numbers**: Every episode is anchored to verified peer-reviewed DOI(s) in `01_sources.json` (`verify_doi`); spoken claims, charts, and captions must match exact source statistics (`check_narration_facts`, e.g. never round `99.2%` or conflate `29%` vs `30%`).
- **Species Precision**: Never refer to animal-study cohorts (`mice`, `rats`, `macaques`) as human `"subjects"` or `"patients"`; state the exact species in spoken lines, chart titles (`(Mice)`), and `R35` pinned comment notes when human + animal papers are paired.

## R3, R15, R49-T & R73 — Pathway Spine, Conversational US English & TTS Safety
- **R3 Signal Spine**: Narration traces a clear causal biological mechanism (`stimulus -> brain hub/pathway -> behavioral outcome`) aligned 1:1 with `visual_plan`.
- **R15 & R73 Readability (`Tier-2 Advisory` Metrics, `Tier-1` Anti-Cliché)**: Natural US English, zero 1st-person (`I/we`), zero academic seminar transitions or AI clichés (`DIORAMA_BANNED_AI_CLICHES`, `EXPRESSIVE_V8_BANNED_AI_CLICHES`). Numeric targets (`FK <= 6.5`, `<= 22` words/sentence, `<= 2` plain-first glossed neuro terms) are **Tier-2 Advisories** (`advisories` list, non-blocking).
- **R49-T TTS Normalization**: `to_expressive_tts_text` / `to_tts_text` ensures clean ElevenLabs `v4` pronunciation while `to_display_text` renders crisp numerals in ASS subtitles.
