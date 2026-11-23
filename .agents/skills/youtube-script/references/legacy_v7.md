# `youtube-script` Legacy `porcelain_cinematic_v7` & Archived Notes (`v4–v7`)

Load ONLY when maintaining or backfilling legacy `porcelain_cinematic_v7` / `lowpoly_pastel_v7` projects (or inspecting `PRE_R76_FROZEN_V8_PROJECTS` `Ep #1..#8 v1`). Active episodes MUST use `expressive_25d_v8` (`R85–R87`) in [`SKILL.md`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/skills/youtube-script/SKILL.md).

## 1. Legacy `porcelain_cinematic_v7` Cast, Grammars & Cold-Open (`R57-H2`, `R66`)
- **Format**: `1080x1920 @ 24fps`, target `~90s`, `<= PORCELAIN_V7_MAX_HOLD_SENTENCES` sentences/clip, bright minimalist high-key lighting (`PORCELAIN_V7_WORLD_STYLE`).
- **Cast & Brain**: Clothed matte-white porcelain figures with **smooth featureless solid matte-white oval heads** (`0` facial ink expressions) + **Contained Living 4-Color 3D Brain** (`PORCELAIN_V7_BRAIN_RENDER_MODES`).
- **Grammars**: `PORCELAIN_V7_VISUAL_GRAMMARS` via `populate_porcelain_reference_contract(plan, dossier_dir)`.
- **R57-H2 Cold-Open (`v7` `S1–S3`)**:
  - `S1`: Myth-flip / visceral hook ending `!` (`<= DIORAMA_V7_COLD_OPEN_S1_MAX_WORDS` words, `rush`).
  - `S2`: `Yet / But ...` contrast (`<= DIORAMA_V7_COLD_OPEN_S2_MAX_WORDS` words, `rush`).
  - `S3`: Rotating case stamp from `DIORAMA_COLD_OPEN_S3_BANK` (`stamp`; matching chapter headline at `sentence_index: 3`).
- **Legacy Debate / Re-Hooks**:
  - Opener banks: `DIORAMA_CRISIS_BEAT_BANK`, `DIORAMA_MECHANISM_PIVOT_BANK`, `DIORAMA_EUREKA_REVEAL_BANK`, `DIORAMA_TAKEAWAY_BRIDGE_BANK`, `DIORAMA_MIDPOINT_REHOOK_BANK`.
  - Stage 3 `offcenter_creator_bet` (`<= 45` chars 1st-person bet in `metadata.json` / `script.json` on `v7`; replaced on `v8` by `R68-D` plain 1-sentence `?` `debate_question`).
- **Legacy Metadata & Thumbnail**:
  - `DESCRIPTION_EDITORIAL_TEMPLATES` (`1`-line hook, mechanism, `https://doi.org/<doi>`, `AI_DISCLOSURE_SENTENCE`, `#Shorts`), title `<= TITLE_MAX_CHARS_DIORAMA`.
  - `thumbnail` (`v7` single `hook_text` + `cover_sentence_index: 1..3`).
- **Archived Frozen Notes (`v8` `Ep #1..#8 v1` ONLY)**: Early `v8` pilots used `Roger`/`Hope`/`Laura` 3-voice cast and `Mini-Cortex` cameos (`PRE_R76_FROZEN_V8_PROJECTS`), permanently retired on active `R76+` (`Solo Siren`, `0` cameos). Legacy Schema `v4/v5` uses `validate_production_v5` / `validate_flow_prompts` in `pipeline/flow_prompt_builder.py`.
