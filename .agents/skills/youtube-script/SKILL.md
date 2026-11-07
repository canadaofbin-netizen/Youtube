---
name: youtube-script
description: Gear 2 Neuro-Diorama v7 (porcelain_cinematic_v7) script, visual_plan, R65 thumbnail spec, and Google Flow prompt authoring + prompt-gate validation.
---

# youtube-script (AI-Only Spec)

SSOT: [AGENTS.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/AGENTS.md) | [neuro_diorama_rules.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/neuro_diorama_rules.md) | [production_constants.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/production_constants.md) | Code: [`pipeline/flow_prompt_builder.py`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/flow_prompt_builder.py), [`pipeline/porcelain_anchor_pack.py`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/porcelain_anchor_pack.py)
Golden ref: `BCI_Shorts_Channel/projects/reenact_01_ainsworth_strange_situation`

## 1. Script Contract (`script.json`, Schema 7, 100% US English)
- **Target Pacing**: Brisk `~90s` (`1m30s`) high-retention 6-Act Shorts spine (within active `DIORAMA_V7_DURATION_MIN_SEC..SHORTS_HARD_CEILING_SEC` & word budget constants in `pipeline/config.py`).
- **Voice & Prosody**: `voice_preset: "emma_v7"` (`en-US-EmmaMultilingualNeural`), `prosody_mode: "dynamic_us_v7"` (legacy `andrew_v7` `en-US-AndrewMultilingualNeural` supported; never reference `RogerNeural` or `BrianMultilingualNeural`).
- **Sentence Hygiene**: Every sentence `<= DIORAMA_US_SENTENCE_WORDS_MAX` (`13` words), FK grade `<= DIORAMA_V7_MAX_FK_GRADE`, TTS-safe, zero AI clichés or `"Imagine..."` (`R57-H`).
- **R57-H2 Cold-Open (S1-S3)**:
  - `S1`: Myth-flip / visceral hook ending `!` (`<= DIORAMA_V7_COLD_OPEN_S1_MAX_WORDS` words, `rush`).
  - `S2`: `Yet / But ...` contrast (`<= DIORAMA_V7_COLD_OPEN_S2_MAX_WORDS` words, `rush`).
  - `S3`: Rotating case stamp from `DIORAMA_COLD_OPEN_S3_BANK` (`stamp`) + matching chapter headline at `sentence_index: 3`.
- **Re-Hooks & 3-Stage Debate Ignition**:
  - Anti-clone opener rotation (`DIORAMA_CRISIS_BEAT_BANK`, `DIORAMA_MECHANISM_PIVOT_BANK`, `DIORAMA_EUREKA_REVEAL_BANK`, `DIORAMA_TAKEAWAY_BRIDGE_BANK`, `DIORAMA_MIDPOINT_REHOOK_BANK`).
  - Re-hook spacing `<= PROSODY_P10_OPEN_LOOP_MAX_GAP_SEC` (`R57-R`), midpoint `?` across Act 3->4 (`R57-M`).
  - Stage 1 pre-bunking myth reversal (Act 2/3); Stage 2 2-sentence binary `... or ...?` open-verdict close (Act 6); Stage 3 `offcenter_creator_bet` (`<= 45` chars 1st-person bet in `metadata.json` / `script.json`).
  - `[Number] -> [Everyday Analogy]` on non-everyday metrics (`R57-V`); glossed neuro terms (`R57-C`).

## 2. Visual Plan Contract (`visual_plan.json`, `porcelain_cinematic_v7`, R66/R67)
- **1:1 Zero-Reuse Clips**: `<= PORCELAIN_V7_MAX_HOLD_SENTENCES` sentences/clip, `strict_room_continuity: True`, positive phrasing only, zero plaque/signage trigger nouns.
- **Grammars (`PORCELAIN_V7_VISUAL_GRAMMARS`)**: `porcelain_fullbleed_world`, `porcelain_hands_closeup`, `porcelain_pov_hands`, `porcelain_cutaway_section`, `porcelain_literal_analogy` (`<= PORCELAIN_V7_LITERAL_ANALOGY_MAX_CLIPS`), `porcelain_living_brain` (`PORCELAIN_V7_BRAIN_RENDER_MODES`).
- **Cast & Brain Lock**: Clothed matte-white porcelain figures with **smooth featureless solid matte-white egg-shaped oval heads** (zero `"frosted-glass cranium"` on cast scenes); **Contained Living 4-Color 3D Brain** (`clear cyan-blue`, `deep crimson-red`, `warm amber-gold`, `luminous pearl-aqua` enclosed fluid; zero `"bioluminescent green"`, `"particles"`, `"mist"`, `"slime"`).
- **Reference Binding & R65 Thumbnail**:
  - Call `populate_porcelain_reference_contract(plan, dossier_dir)` (`6-9` `reference_anchors`, `~55-68%` `clip["reference_image"]` bindings).
  - Include `thumbnail: {"hook_text": "<2-4 UPPERCASE WORDS>", "cover_sentence_index": 3, "cover_brief": "..."}` (`<= THUMB_HOOK_MAX_WORDS` words, `<= THUMB_HOOK_MAX_CHARS` chars) + R60 title (`<= TITLE_MAX_CHARS_DIORAMA`) in `metadata.json`.

## 3. Render & Gate
Run from a Python script file (never inline bash `python -c` with apostrophes):
1. `build_flow_prompts(plan, sentences)` + `write_flow_prompts_json(draft_dir, clips)` + `build_reference_image_specs(plan, sentences)`
2. `/home/canadaofbin/hermes-venv/bin/python -X utf8 main.py prompt-gate --dir <draft_or_project_dir>` -> must return `"passed": true, "issues": []`.
(Legacy Schema v5/v4 projects use `validate_production_v5` / `validate_flow_prompts` in `pipeline/flow_prompt_builder.py`.)
