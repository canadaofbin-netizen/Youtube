---
name: bci-script-gen
description: Authors a topic's clip narrations (one per Deep-Mechanism role) and a hand-authored visual_plan, renders Google Flow Omni 1.1 prompts with pipeline/flow_prompt_builder.py (porcelain mannequins in real environments, realistic brain interior, one camera move per clip, Puck voice line), and validates them with validate_narrations / validate_flow_prompts. Use for every new ALL ABOUT BRAIN Short and to upgrade prompts_db records to Capgras-golden quality.
---

# BCI Script & Flow Prompt Authoring

Master: [AGENTS.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/AGENTS.md) · Rules: [content_quality_rules.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/content_quality_rules.md) (R1, R2, R3, R15, R24, R26, R42) · [visual_prompt_spec.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/visual_prompt_spec.md) (R14-A, R14-B, R21, R38, R40-A/B/C) · [camera_choreography_rules.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/camera_choreography_rules.md) (R14-D) · Numbers: [production_constants.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/production_constants.md)

Canonical example: [capgras_delusion_10clip_prompts.md](file:///C:/Users/yunky/.gemini/antigravity/brain/a935bacf-5ae3-4e1a-b5e2-7ed23172c727/capgras_delusion_10clip_prompts.md) — in-repo golden = Capgras topic `visual_plan` + `clip_narrations` in `pipeline/topics_catalog.py`.

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
