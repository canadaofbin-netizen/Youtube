---
name: bci-script-gen
description: Authors a topic's clip narrations (one per Deep-Mechanism role) and a hand-authored visual_plan, renders Google Flow Omni 1.1 prompts with pipeline/flow_prompt_builder.py (porcelain mannequins in real environments, realistic brain interior, one camera move per clip, Puck voice line), and validates them with validate_narrations / validate_flow_prompts. Use for every new ALL ABOUT BRAIN Short and to upgrade prompts_db records to Capgras-golden quality.
---

# BCI Script & Flow Prompt Authoring

Master: [AGENTS.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/AGENTS.md) · Rules: [neuro_diorama_rules.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/neuro_diorama_rules.md) (R56–R64 flagship `neuro_diorama` v7/v6) · [content_quality_rules.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/content_quality_rules.md) (R1, R2, R3, R15, R24, R26, R42) · [visual_prompt_spec.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/visual_prompt_spec.md) (R14-A, R14-B, R21, R38, R40-A/B/C) · [camera_choreography_rules.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/camera_choreography_rules.md) (R14-D) · Numbers: [production_constants.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/production_constants.md)

Canonical example: [capgras_delusion_10clip_prompts.md](file:///C:/Users/yunky/.gemini/antigravity/brain/a935bacf-5ae3-4e1a-b5e2-7ed23172c727/capgras_delusion_10clip_prompts.md) — in-repo golden = Capgras topic `visual_plan` + `clip_narrations` in `pipeline/topics_catalog.py`; Schema v7 `lowpoly_pastel_v7` golden = `BCI_Shorts_Channel/research_dossiers/phineas_gage_iron_rod/diorama_v7_lowpoly/` (Schema v6 archive golden = `phineas_gage_iron_rod/diorama_v6_dynamic/`).

---

## Neuro-Diorama System v7 procedure (`DEFAULT_PRODUCTION_PROFILE = "neuro_diorama"`, `DEFAULT_DIORAMA_STYLE_PROFILE = "lowpoly_pastel_v7"`)
Input = a **ready** research dossier (`main.py dossier validate --slug <slug>`). Query reusable high-clarity prompts/analogies/locations first via `main.py kb search --pack prompts`. Rules: R56–R64 in [neuro_diorama_rules.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/neuro_diorama_rules.md).
1. Author `script.json` (`"schema": 7, "profile": "neuro_diorama", "style_profile": "lowpoly_pastel_v7"`; prosody defaults to `DIORAMA_V7_PROSODY_MODE = "dynamic_rush_v7"` — omit `prosody_mode` unless you deliberately override; optional `emphasis_words` / `prosody_gears`, **100% US English**): 6 Acts (`DIORAMA_ACT_COUNT`), `DIORAMA_SENTENCE_COUNT_MIN..DIORAMA_SENTENCE_COUNT_MAX` crisp concrete conversational sentences (`<= DIORAMA_V7_SENTENCE_WORDS_MAX` words each, total `DIORAMA_WORD_COUNT_MIN..DIORAMA_WORD_COUNT_MAX`, `>= DIORAMA_MIN_CONVERSATIONAL_QUESTIONS` `?` hooks), **R57-H2 3-sentence cold-open** — S1 myth-flip / paradox shock ending in `!` (`<= DIORAMA_V7_COLD_OPEN_S1_MAX_WORDS` words), S2 `Yet / But …` contrast (`<= DIORAMA_V7_COLD_OPEN_S2_MAX_WORDS` words), S3 `"This is the true story of <case>."` case stamp with a matching chapter headline (golden: `projects/diorama_01_hm_lab_B_dynamic`) — zero `"Imagine..."` / `"Picture this..."` / `"Have you ever..."` weak hypothetical openers (`R57-H`), concrete patient/researcher names + glossed neuroscience vocabulary (`R57-C`, zero repeated stock analogy idioms), Midpoint Open-Loop `?` across the Act 3 -> Act 4 transition (`R57-M`), a re-hook (`?`, stamp line, or *"But here's…"*) at least every `PROSODY_P10_OPEN_LOOP_MAX_GAP_SEC` (~6 sentences, `R57-R`), Act 5 crisis climax, and `100%` `[Number] -> [Immediate Everyday Analogy]` pairing (`validate_number_analogy_pairing`).
2. Author `visual_plan.json` (`"schema": 7, "profile": "neuro_diorama", "style_profile": "lowpoly_pastel_v7"`): stage 1:1 Zero-Reuse clips in `DIORAMA_V7_WORLD_STYLE` (`DIORAMA_V7_SHADER_STYLE`, `DIORAMA_V7_OPTICS_LOCK`) using `DIORAMA_V7_VISUAL_GRAMMARS` (`lowpoly_fullbleed_world`, `lowpoly_hands_closeup`, `lowpoly_pov_hands`, `lowpoly_cutaway_section` `<= DIORAMA_V7_CUTAWAY_MAX_RATIO`, `lowpoly_literal_analogy`, `lowpoly_matte_brain`) and `DIORAMA_V7_CAMERA_MOVES` (`>= DIORAMA_V7_LOCKED_CAMERA_MIN_RATIO` `locked_tripod`, `<= DIORAMA_V7_ZOOM_CAMERA_MAX_RATIO` zoom) with positive phrasing only (zero T5 Pink-Elephant negative noun lists). Include `thumbnail: {"hook_text": "<2-4 UPPERCASE WORDS>", "cover_sentence_index": 3, "cover_brief": "..."}` (`<= THUMB_HOOK_MAX_CHARS` chars, complementing the title) and set `chapter_headlines` at `sentence_index == 3` to `hook_text` (`R65`). Schema v6 dark-void bisque-ceramic plans remain supported when `"schema": 6` is explicitly specified.
3. Render & gate: `build_flow_prompts(plan, sentences)` -> `main.py prompt-gate --dir <dir>` (`passed: true`, `issues: []`; includes `[cold_open_v7]` and `[thumbnail_v7]` checks). After assembly, `main.py prosody-qa --project <id>` must pass P1–P10 and `main.py thumbnail --project <id>` must pass TQ1–TQ7.

---

## Prompt System v5 procedure (mandatory for new projects, 2026-10-24)
Input = a **ready** research dossier ([bci-deep-research](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/skills/bci-deep-research/SKILL.md), `main.py dossier validate --slug <slug>`). Rules: R45–R48 in [visual_prompt_spec.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/visual_prompt_spec.md), R15 v5 / R49-T in [content_quality_rules.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/content_quality_rules.md). Worked examples: `BCI_Shorts_Channel/research_dossiers/<slug>/shorts_v5/`.

| Step | Action | Rule |
|---|---|---|
| 1 | `main.py dossier seed --slug <slug>` → copy `visual_mode`, `must_have_scenes`, `brain_link` into a new `visual_plan.json` (`"dossier": "<slug>"`). | R44, R45 |
| 2 | Pick the Short's beats from `07_longform_outline.json → shorts_extract` (hook, core experiment, twist). Put the **iconic** scene in clip 1 or 2. | R46 |
| 3 | Write 10 `clip_narrations` (role jobs in R42; generalized for experiments): plain words from `05_plain_language.json`, wow facts from `dossier.json`, ≥ 1 "you / your" line, TTS-safe (spell numbers and years out, no `! ? — ; ( ) %`), memes R24, pivot "Instead of", conclusion "Which proves / Which is why", openers "First, / Next, / Finally," (never "Step one"). | R15 v5, R49-T, R24, R26 |
| 4 | Author `shots[role]` for every role: `scene_id`, `setting` (default from mode), `shot_type`, `camera` (one move), `action` (specific body verb), `prop_change` (visible physical change), `reaction` (body language). Use the dossier's layout / props / actions / reactions and wardrobe. Optional `scenes[role]` for a fully hand-written scene (still keep `shots[role].scene_id`). | R46, R47, R14-D v5 |
| 5 | Brain clips only where the mode allows: one canonical region (anatomy_map), colour code R21, and the same clip's narration names it (or its plain name) and links it to what was just shown. Fill `brain_link[role]`. | R45, R48 |
| 6 | Render + gate: `build_flow_prompts(plan, narrations)` → `validate_production_v5(plan, narrations, clips) == []` (CLI: `main.py prompt-gate --dir <project_dir>`). Fix and repeat. | R18-V5 |
| 7 | Save `02_script/script.json`, `03_visuals/visual_plan.json`, `03_visuals/flow_all_in_one_prompts.json` (`write_flow_prompts_json`, schema 5). Add the project id to the dossier's `linked_projects`. | R11–R12 |

The v4 procedure below remains valid only for legacy projects and the prompt database.

---

## Why hand-author
Template-filled prompts (from `researcher.infer_visual_plan` or a `prompts_db` record) are valid but generic. Capgras-quality prompts come from an agent writing **both** the narrations and the `visual_plan.scenes` for the specific case. Treat every `prompts_db` record as a starting point and upgrade it with a hand-authored `visual_plan`.

## Procedure
| Step | Action | Rule |
|---|---|---|
| 1 | Read `01_ideation/research_card.json`; confirm one case, one cast, one DOI. If a `prompts_db` or `pipeline/topics_catalog.py` record exists for the topic, load its `visual_plan` / `clip_narrations` as a draft — always audit and strip legacy `Step one:` / `Step two:` / `Step three:` openers from catalog or on-disk `script.json` / `flow_all_in_one_prompts.json` before rendering. | R1, R24 |
| 2 | Pick clip count `n` (default `DEFAULT_CLIP_COUNT`, range `CLIP_COUNT_MIN..CLIP_COUNT_MAX`); roles = `clip_roles(n)`. | R42 |
| 3 | Write `clip_narrations` — one line per role, within `CLIP_WORDS_MIN..CLIP_WORDS_MAX`, total `script_word_range(n)`; pivot contains "Instead of"; mechanism / step1–3 open with natural documentary transitions ("First," / "Next," / "Finally," or "Here is how it works"); conclusion opens "Which proves" / "Which is why"; place both memes. | R2, R26, R24, R15, R3 |
| 4 | Author `visual_plan` (schema R40-C): real environment + props, scale anchor outside the brain, mannequin cast and per-role actions, target / crisis / compensatory regions, `signal_path`, `mechanism_steps`, `anatomy_descriptors`, `bci_hardware` (D5 only). | R14-A, R21, R38 |
| 5 | Write `visual_plan.scenes[role]` for every role: concise sentences within `PROMPT_SCENE_WORDS_MIN..PROMPT_SCENE_WORDS_MAX`, one camera move from R14-D, colour words from R21, high-key daylight, mannequin acting the narration. For brain interior clips (`crisis`, `pivot`, `step1`), explicitly include `architectural cross-section cutaway` and `stream in a collimated flow` so Flow renders structured anatomy instead of floating glowing blobs. No banned tokens. | R40-A, R14-B, R14-D |
| 6 | Render and validate (below). Fix and re-run until both validators return `[]`. | R18 G1–G12 |
| 7 | Save `02_script/script.json` (`clip_narrations`), `03_visuals/visual_plan.json`, and `03_visuals/flow_all_in_one_prompts.json` via `write_flow_prompts_json`. | R11–R12 |

## Render & Validate
```python
import json
from pathlib import Path
from pipeline.flow_prompt_builder import (
    build_flow_prompts, validate_flow_prompts, validate_narrations, write_flow_prompts_json,
)

project_dir = Path("BCI_Shorts_Channel/projects/<project_id>")
plan = json.loads((project_dir / "03_visuals" / "visual_plan.json").read_text(encoding="utf-8"))
narrations = json.loads((project_dir / "02_script" / "script.json").read_text(encoding="utf-8"))["clip_narrations"]

assert validate_narrations(narrations) == []
clips = build_flow_prompts(plan, narrations)      # one dict per clip: role, setting, camera_move, scene, prompt
assert validate_flow_prompts(clips) == []
write_flow_prompts_json(project_dir, clips)
```
Run via `execute_code` (or `/home/canadaofbin/hermes-venv/bin/python -X utf8` on a script file) rather than inline `python -c "..."` in `terminal` — narration strings contain apostrophes (e.g., `mother's`) that break bash quoting and trigger command-parser approval blocks. Also run `ScriptingStage(ProjectStorage(project_id)).validate_qa_gates(script_data, [{'claim': '...', 'source': doi}])` from `pipeline.scripting` and `pipeline.storage` (confirm `[k for k, v in qa['gates'].items() if not v['passed']] == []`) to verify all 12 script QA gates pass.

`load_visual_plan(project_dir=...)` resolves the plan with the R40-C precedence when no hand-authored file exists.

## Self-check before handing to Gear 3
- Each prompt reads like the golden: real place → mannequin action → one camera move → lighting; brain clips name the real anatomy and colour code.
- Narration facts match the paper (R1); cast identical across clips.
- No `Audio:`, no hex, no angle labels, no loop wording, voice line last.
