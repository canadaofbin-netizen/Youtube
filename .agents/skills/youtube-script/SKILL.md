---
name: youtube-script
description: Gear 2 Neuro-Diorama v7/v8 (porcelain_cinematic_v7 & expressive_25d_v8) script, visual_plan, R65 thumbnail spec, and Google Flow prompt authoring + prompt-gate validation.
---

# youtube-script (AI-Only Spec)

SSOT: [AGENTS.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/AGENTS.md) | [neuro_diorama_rules.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/neuro_diorama_rules.md) | [production_constants.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/production_constants.md) | Code: [`pipeline/flow_prompt_builder.py`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/flow_prompt_builder.py), [`pipeline/porcelain_anchor_pack.py`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/porcelain_anchor_pack.py)
Golden refs: `BCI_Shorts_Channel/projects/reenact_01_ainsworth_strange_situation` (`v7`), `BCI_Shorts_Channel/projects/v8_pilot_01_sleep_first_night_watch` (`v8`)

## 1. Script Contract (`script.json`, Schema 7/8, 100% US English)
- **Target Pacing**: Brisk `~90s` (`porcelain_cinematic_v7`) or `58–88s` (`<= 89.5s`, `shorts_expressive_v8` / `R68`: `13–15` sentences `160–240` words @ `~190–210 WPM`, `0.32–0.50s` breath gaps).
- **Voice & Prosody**: `voice_preset: "emma_v7"` (`en-US-EmmaMultilingualNeural`, `+0Hz`, single-narrator default across `prosody_mode: "dynamic_us_v7"` on `v7` and `prosody_mode: "expressive_us_v8"` `+14%/+10%/+4%` `foil_sentence_indices: []` on `R68`; optional `andrew_v8` `en-US-AndrewMultilingualNeural` & optional foil presets `foil_v8` `en-US-SteffanNeural` / `guy_foil_v8` `en-US-GuyNeural` supported; legacy `andrew_v7` preserved; never use banned legacy neural voices).
- **Sentence Hygiene**: Every sentence `<= DIORAMA_US_SENTENCE_WORDS_MAX` (`13` words on `v7`) or `<= SHORTS_EXPRESSIVE_V8_SENTENCE_WORDS_MAX` (`22` words, 1 new idea per sentence, natural contractions on `v8`), FK grade `<= DIORAMA_V7_MAX_FK_GRADE`, TTS-safe, zero AI clichés or `"Imagine..."` (`R57-H`). In `expressive_25d_v8` (`R68`), omit spoken academic nicknames (`omit_experiment_nicknames`) and pair with R35 pinned DOI comment; close on a `0.20s` seamless answer-loop sentence back to `S1`.
- **R68 Empathy-First 3-Beat Opening & Beats (`expressive_25d_v8`, `opening_mode: "question"` default)**:
  - **① Relatable 2nd-Person Question (`0–3s`, `S1`, `<= 14` words)**: Start with 1 of 5 templates (`Ever…?` / `Why do you…?` / `Have you noticed…?` / `What if your…?` / `How come you…?`; zero years/institutions/jargon). Set `opening_mode: "situation"` only for legacy `!` cold-opens.
  - **② Empathy + Myth-Flip Aggro (`3–6s`, `S2–S3`, `1–2` lines `<= 10` words each)**: Validate shared experience (`"You're not alone."`) + flip the common excuse without blaming the viewer (`"And no, it's not the bed."`). Cap total myth-flip patterns across the entire episode at `<= EXPRESSIVE_V8_MAX_MYTH_FLIPS` (`1`; ban 2+ repetitive foil/`Wrong` flips or off-spine tangents).
  - **③ Early Core Reveal + Brain Cut (`6–10s`, `<= S4` / `<= 15s`)**: Set `core_reveal_sentence_index: 4` (`<= 4`) and show the first crystal X-Ray brain cut right on the core sentence (`portal_to_brain: True`).
  - **④–⑦ Body Beats (`sentence_beats`: `question|empathy|aggro|core|evidence|mechanism|payoff|cta_question|loop`)**: Evidence (`3–4` sents, researcher + `[Number]->[Analogy]`) -> Mechanism (`2–3` sents, plain-speech brain gloss, `You see` & `Wait, what` advisory only + `>=1` X-Ray brain cut in `[45–85%]`) -> Payoff (`2` sents) -> CTA question + Answer-Loop closing `S1`'s question.
  - **Good vs Bad Opening Pair**:
    - ✅ Good: `"Ever sleep terribly your first night in a hotel? You're not alone. And no, it's not the bed. Half of your brain stayed awake on purpose — standing guard."`
    - ❌ Bad: `"At 3 AM in a new hotel bed, your eyes snap wide open!"` + 3 repeated clerk/assistant/friend `"Wrong!"` loops + delaying the core finding until 30s.
- **R57-H2 Cold-Open (`v7` S1-S3)**:
  - `S1`: Myth-flip / visceral hook ending `!` (`<= DIORAMA_V7_COLD_OPEN_S1_MAX_WORDS` words, `rush`).
  - `S2`: `Yet / But ...` contrast (`<= DIORAMA_V7_COLD_OPEN_S2_MAX_WORDS` words, `rush`).
  - `S3`: Rotating case stamp from `DIORAMA_COLD_OPEN_S3_BANK` (`stamp`; matching chapter headline at `sentence_index: 3` on `v7`).
- **Re-Hooks & 3-Stage Debate Ignition**:
  - Anti-clone opener rotation (`DIORAMA_CRISIS_BEAT_BANK`, `DIORAMA_MECHANISM_PIVOT_BANK`, `DIORAMA_EUREKA_REVEAL_BANK`, `DIORAMA_TAKEAWAY_BRIDGE_BANK`, `DIORAMA_MIDPOINT_REHOOK_BANK`).
  - Re-hook spacing `<= PROSODY_P10_OPEN_LOOP_MAX_GAP_SEC` (`R57-R`), midpoint `?` across Act 3->4 (`R57-M`).
  - Stage 1 pre-bunking myth reversal (Act 2/3); Stage 2 2-sentence binary `... or ...?` open-verdict close (Act 6); Stage 3 `offcenter_creator_bet` (`<= 45` chars 1st-person bet in `metadata.json` / `script.json`).
  - `[Number] -> [Everyday Analogy]` on non-everyday metrics (`R57-V`); glossed neuro terms (`R57-C`).

## 2. Visual Plan Contract (`visual_plan.json`, `porcelain_cinematic_v7` R66/R67 & `expressive_25d_v8` R68)
- **1:1 Zero-Reuse Clips**: `v7` `<= PORCELAIN_V7_MAX_HOLD_SENTENCES` sentences/clip; `v8` (`diorama_v8_expressive/`, `dossier seed --style-profile expressive_25d_v8`) `14–26` multi-beat `30fps` `VIDEO_FRAMES` (`Start+End` `End(cur)==Start(nxt)` 0-overlap keyframe-chained) clips across continuous spaces/face->brain zooms + clean `"hard"` cuts at full location shifts and 9 Track-V1 camera-bridge transitions (`daisy_chain_bridge`, `occlusion_wipe`, `action_impact_cut`, `dissolve_6f`, `match_cut_bridge`, `split_screen_wipe`, `portal_crash_zoom_10f`, `whip_pan_blur_8f`, `dissolve_8f`, `EXPRESSIVE_V8_TRANSITION_TYPES`). Positive phrasing only, zero plaque/signage trigger nouns.
- **Grammars**: `PORCELAIN_V7_VISUAL_GRAMMARS` (`v7`) or `EXPRESSIVE_V8_VISUAL_GRAMMARS` (`v8`: `expressive_vinyl_world`, `expressive_hands_closeup`, `expressive_pov_hands`, `expressive_xray_brain`, `expressive_literal_analogy`, `expressive_cameo_world`, `expressive_split_contrast`).
- **Cast & Brain Lock**:
  - `porcelain_cinematic_v7` (`R66`): Clothed matte-white porcelain figures with **smooth featureless solid matte-white egg-shaped oval heads** + **Contained Living 4-Color 3D Brain** (`clear cyan-blue`, `deep crimson-red`, `warm amber-gold`, `luminous pearl-aqua`; zero `"bioluminescent green"`, `"particles"`, `"mist"`, `"slime"`).
  - `expressive_25d_v8` (`R68` `안 1`): Smooth 3D matte cream-white vinyl heads (`#F5F2EB`) + bold 2D charcoal-black ink expressions; first gold-seam (`#D4AF37`) crystal X-Ray 4-color brain reveal at `core_reveal_sentence_index` (`<= S4 / 15s`) + `>=1` mechanism X-Ray cut in `[45–85%]`; `1` `4cm` `Mini-Cortex` cameo.
- **Reference Binding & R65 Thumbnail**:
  - Call `populate_porcelain_reference_contract(plan, dossier_dir)` (`v7`) or `populate_expressive_v8_reference_contract(plan, dossier_dir)` (`v8`).
  - Include `thumbnail: {"hook_text": "<2-4 UPPERCASE WORDS>", "cover_sentence_index": 3, "cover_brief": "..."}` (`cover_sentence_index: 1` allowed on `v8`) + title in `metadata.json` (`<= TITLE_MAX_CHARS_DIORAMA` on `v7`; `4–8` words `<= R68_TITLE_MAX_CHARS` `55` chars & `0` hashtags on `v8`).

## 3. Render & Gate
Run from a Python script file (never inline bash `python -c` with apostrophes):
1. `build_flow_prompts(plan, sentences)` + `write_flow_prompts_json(draft_dir, clips)` + `build_reference_image_specs(plan, sentences)`
2. `/home/canadaofbin/hermes-venv/bin/python -X utf8 main.py prompt-gate --dir <draft_or_project_dir>` -> must return `"passed": true, "issues": []`.
(Legacy Schema v5/v4 projects use `validate_production_v5` / `validate_flow_prompts` in `pipeline/flow_prompt_builder.py`.)
