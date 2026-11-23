# Pilot brief — Prompt System v5 dossier + Shorts draft

Read these before you start (they are the source of truth):
- `pipeline/research_dossier.py` (dossier files, RESEARCH_CHECKLIST, validate_dossier, verify_doi, search_youtube, analyze_reference_video, plan_seed_from_dossier)
- `pipeline/prompt_quality_v5.py` (validate_production_v5: the production gate you must pass)
- `pipeline/flow_prompt_builder.py` → `build_flow_prompts`, `is_v5_plan`, `compose_shot_scene`, `write_flow_prompts_json`
- `pipeline/anatomy_map.py` (only these regions may appear; use their `plain` names in narration)
- `pipeline/plain_language.py` (to_tts_text, analyze_script)
- `pipeline/config.py` v5 block (VISUAL_MODES, MODE_ROLE_SETTINGS, caps)
- Reference of what went WRONG before: the old project folder named in your task (`03_visuals/flow_all_in_one_prompts.json`, `02_script/script.json`). Read it, do not edit it.

## Step 1 — Dossier (longform depth) in `BCI_Shorts_Channel/research_dossiers/<slug>/`
Create with `init_dossier(slug, topic, pillar, visual_mode)` then fill every file:

- `dossier.json`: `visual_mode` + `visual_mode_reason` (topic first: BEHAVIORAL_PSYCH = no brain on screen; HYBRID = max 2 brain clips at the core mechanism; NEURO_BIOLOGY = max 4), `primary_case {title, year, place, people[]}`, `core_facts[{fact, source_id}]`, `wow_facts[{fact, why_surprising, source_id, rank}]` (≥3, the "no way!" moments), `misconceptions[{myth, truth, source_id}]`, `everyday_hooks[]`.
- `01_sources.json`: `sources[{id, type, citation, doi, url, verified, notes}]` with type in primary | primary_historical | replication | follow_up | critique | review | book | biography | archive | museum | news | documentary. Verify every DOI with `verify_doi` and set `verified` from its result. Need: primary, ≥1 follow-up/replication/review, ≥1 critique or misconception, plus archives/museum/documentary when they exist.
- `02_master_story.md`: ≥1500 characters, all 8 sections, written for an 8–15 minute documentary (people, era, step-by-step event, numbers as reported, twist/controversy, aftermath, what it means for you).
- `03_visual_reference.json`: `scenes[{id: "S1"..., title, iconic, shorts_priority (1=must be in the Short), era, layout {description, positions[{who, where, facing}]}, props[{name, period_detail, physical_behavior}], actions[{who, verb_sequence}], reactions[{who, reaction}], wardrobe, lighting, recognition_hook, sources[]}]`. Exactly ONE `iconic: true` — the moment the audience says "I know this!". Break it down physically (who stands where, what is in their hands, what moves, what breaks / lights / spills).
- `04_media_refs.json`: `media[{id, kind, title, url, channel, timecodes[{t, what}], license_note, analysis}]`. Use `search_youtube(query)` and run `analyze_reference_video(url, <dossier>/media/<id>, section="*mm:ss-mm:ss" optional)` on the 1–2 most useful clips; then LOOK at `contact_sheet.jpg` / keyframes with your file viewer and record concrete blocking/prop observations in `analysis.shot_notes` and in the visual_reference scenes.
- `05_plain_language.json`: `one_sentence_story`, `so_what_for_you`, `jargon_map[{term, plain, analogy}]`.
- `06_brain_link.json`: `links[{role, region, plain, function, scene_id, narration_bridge}]` — regions from anatomy_map only; empty for BEHAVIORAL_PSYCH.
- `07_longform_outline.json`: `target_minutes`, `shorts_extract {hook, core_experiment, twist}`, `chapters[{n, title, beats[], scene_ids[], reuse_shorts_roles[], new_shots_needed[]}]` (≥5 chapters).

Gate: `validate_dossier(slug)["ready"] is True`.

## Step 2 — v5 Shorts draft in `<dossier>/shorts_v5/`
Write `visual_plan.json`, `script.json` (`{"clip_narrations": [10 lines]}`) and render `flow_all_in_one_prompts.json` via `build_flow_prompts(plan, narrations)` + `write_flow_prompts_json(<dossier>/shorts_v5 as project_dir)` (it writes into `<dir>/03_visuals/`).

visual_plan v5 fields:
```json
{
  "schema": 5, "visual_mode": "...", "dossier": "<slug>",
  "real_environment": "...", "environment_props": ["..."],
  "cast": {"subject": "...", "others": ["..."], "animals": ["..."], "wardrobe": {"who": "period clothing"}},
  "must_have_scenes": [{"id": "S1", "title": "...", "iconic": true, "recognition_hook": "..."}],
  "shots": {"setup": {"scene_id": "S1", "setting": "real_env", "shot_type": "wide", "camera": "...", "action": "...", "prop_change": "...", "reaction": "..."}, "...": {}},
  "scenes": {"<role>": "optional hand-written final scene text (used verbatim; still set shots[role].scene_id)"},
  "brain_link": {"<role>": {"region": "...", "plain": "...", "link": "..."}},
  "target_region": "(HYBRID/NEURO only, one canonical region)", "crisis_region": "...", "compensatory_region": "...",
  "signal_path": ["..."], "anatomy_descriptors": {"region": "shape words"}
}
```
Every role (setup, symptom, failure, crisis, pivot, step1, step2, step3, breakthrough, conclusion) needs `shots[role]` with `scene_id`; every real_env clip needs `action` (or a verbatim `scenes[role]`).

Narrative job per role (generalized for experiments): setup = cold open on the iconic moment / who-when-where (iconic scene must be clip 1 or 2) · symptom = the shocking behaviour/result · failure = what people expected or tried and why it failed · crisis = the hidden cause · pivot = the twist, must contain "Instead of" · step1–3 = how it works in plain words, openers "First," "Next," / "Then," "Finally," (reenact variations in BEHAVIORAL; brain only where the mode allows) · breakthrough = the proof · conclusion = opens "Which proves" or "Which is why", about the viewer's life.
Signature lines: symptom or crisis contains "For your brain, this is a total nightmare." (pronoun/tense may adapt: "For his brain, this was a total nightmare."); breakthrough contains "The researchers were left completely stunned."

Narration rules: 18–28 words per clip (180–280 total), spoken from frame 0, TTS-safe (no digits — spell numbers and years out, no ! ? — ; ( ) % or abbreviations like Dr.), whole-script Flesch-Kincaid ≤ 8 and every clip ≤ 11, ≤1 non-anatomy technical term in the whole script, brain-region names ≤ mode cap and each glossed with its anatomy_map plain name, ≥1 clip speaks to "you / your", no "Step one". Facts exactly as the sources report. Easy, vivid, story first ("the world has things like this?!"), never a paper read-out.

Scene rules (Action-Physics, R47): 50–95 words per scene; formula = [camera framing + one move] + [specific body verb] + [prop with a visible physical change] + [body-language reaction — porcelain faces have no expressions, use hands, shoulders, posture]. Never only "stands nearby / sits calmly / stares / talking". Cast = matte-white porcelain mannequins wearing period wardrobe; animals are porcelain-style animals; iconic recognition details keep their real colours/clothing (e.g. white vs black shirts, gorilla suit). Real environment photoreal, bright daylight. Brain clips (drill_down / brain_void) name one canonical region, use the colour code (crimson-red damage, electric cyan-blue target, warm amber-gold active route, bioluminescent green signal) and the SAME clip's narration names that region (or its plain name) and links it to what we just saw. No banned tokens (gear, clockwork, coin, tape recorder, HUD, loop, tripod, hex colours, "Audio:").

Gate: `validate_production_v5(plan, narrations, clips) == []`. Iterate until it is. Then write `<dossier>/shorts_v5/BEFORE_AFTER.md`: a short table comparing the old project's clip 1–3 scenes vs the new ones and what the viewer now recognizes.
