# Rule: Visual Prompt Specification (Google Flow Omni 1.1)

Parent Master Index: [AGENTS.md](file:///g:/My%20Drive/Kyubin_Yun_Workspace/07_Youtube/.agents/AGENTS.md) · Numbers: [production_constants.md](file:///g:/My%20Drive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/production_constants.md) · Camera vocabulary: [camera_choreography_rules.md](file:///g:/My%20Drive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/camera_choreography_rules.md)

Single source of truth for what a Google Flow clip shows and how its prompt is written. Replaces `visual_dna_cutaway_rules.md`.

| Item | Location |
|---|---|
| Builder (only prompt path) | [`pipeline/flow_prompt_builder.py`](file:///g:/My%20Drive/Kyubin_Yun_Workspace/07_Youtube/pipeline/flow_prompt_builder.py) — `build_flow_prompts`, `render_prompt`, `validate_flow_prompts`, `validate_narrations`, `load_visual_plan`, `write_flow_prompts_json`, `BANNED_PROMPT_TOKENS` |
| Canonical example | [capgras_delusion_10clip_prompts.md](file:///C:/Users/yunky/.gemini/antigravity/brain/a935bacf-5ae3-4e1a-b5e2-7ed23172c727/capgras_delusion_10clip_prompts.md) (patient DS, DOI `10.1098/rspb.1997.0062`) |
| In-repo golden | Capgras topic `visual_plan` + `clip_narrations` in [`pipeline/topics_catalog.py`](file:///g:/My%20Drive/Kyubin_Yun_Workspace/07_Youtube/pipeline/topics_catalog.py); `build_flow_prompts` must reproduce the canonical prompts byte-for-byte (golden test) |
| Roles / settings | `CLIP_ROLE_SEQUENCES`, `ROLE_SETTINGS`, `clip_roles(n)` in `pipeline/config.py` |

---

## R5 — Engine Lock
- Every clip and its voiceover are generated in **Google Flow (Gemini Omni 1.1)**, model from `ALLOWED_FLOW_MODELS`, via the visible Naver Whale window (`WHALE_EXECUTABLE`, `DEFAULT_CDP_PORT`).
- `ALLOW_EXTERNAL_PAID_APIS` and `ALLOW_STATIC_IMAGE_VIDEO_FALLBACK` stay `False`. No paid TTS, no slideshow (`zoompan`) clips, no FFmpeg clones (violations fail R37).
- Flow credit permission dialogs are auto-approved by the browser worker.

## R14-A — Cast & Setting
| Rule | Requirement |
|---|---|
| Cast | Matte-white porcelain **mannequins only** — never real humans. Translucent frosted-glass cranium reveals the brain. Cast comes from `visual_plan.cast` and stays identical across all clips (same subject, same family members). |
| Setting by role | `real_env` roles (setup, symptom, failure, conclusion): narration-matched **photoreal real environment** (hospital room, casino, lab, classroom…) with realistic props from `environment_props`. `drill_down` (crisis): dive from the mannequin through the cranium into the brain. `brain_void` (pivot, mechanism, step1–3): realistic matte-white brain on a **deep midnight navy void**. `pull_out` (breakthrough): from the brain back out into the real environment. |
| Mannequin acting | The mannequin acts out the narration with one clear pose or gesture per clip (turns head away, reaches out, pleading gesture, holds a telephone). Actions come from `visual_plan.mannequin_actions[role]`. |
| Lighting | Cinematic dramatic chiaroscuro: rim light on porcelain contours, the rest falls into shadow. |
| Scale anchor | One real-world `scale_anchor_object` placed **outside the brain** in the real environment (e.g. EKG monitor beside the bed). Never inside the brain void. |

## R38 — Realistic Anatomy & Banned Props
- Brain anatomy is realistic: gyri and sulci, almond-shaped amygdala, seahorse-shaped hippocampus, white-matter tracts, pyramidal neuron columns. Use `visual_plan.anatomy_descriptors` for shape words.
- Signal flow is physical-simulation style: particles flowing along tracts like fluid through pipes, sparks scattering at a severed junction.
- **Banned inside the brain:** gears, clockwork, tape reels / tape recorders, brass or balance scales, camera shutters, coins, dollar bills, any toy or metaphor prop.
- **BCI topics (decision D5):** real hardware (Utah array, Neuralink threads, ECoG grids) is allowed via `visual_plan.bci_hardware`, rendered realistically. Toy or metaphor hardware stays banned.

## R21 — 4-Point Colour Code
| Colour | Meaning | `visual_plan` field |
|---|---|---|
| crimson-red | crisis / damage | `crisis_region` (+ `crisis_lesion`) |
| electric cyan-blue | target region | `target_region` |
| warm amber-gold | active / compensatory circuit | `compensatory_region` |
| bioluminescent green | signal transmission | `signal_path` |

Colours are named in words only. Everything else stays matte white on midnight navy so the four colours pop out.

## Camera Grammar (Mysterious-Architecture style)
- Dynamic camera, **one clean move per clip**; continuous-feeling progression: real exterior → X-ray through the frosted-glass cranium → brain interior (macro) → pull-out to the real environment.
- The final clip is an **independent conclusion scene** (R19), never a return to clip 1.
- Exact move phrasing per role: [camera_choreography_rules.md](file:///g:/My%20Drive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/camera_choreography_rules.md) (R14-D).

| Role | Setting | Scene content | Colour focus | Move (R14-D) |
|---|---|---|---|---|
| setup | real_env | environment + props + subject mannequin, setup action | — | establishing track-in |
| symptom | real_env | close-up of subject acting the symptom; brain visible through cranium | cyan target, dim crimson route | head orbit |
| failure | real_env | other cast attempt to help, subject rejects | warm light on others, subject in shadow | lateral track |
| crisis | drill_down | through cranium into brain; lesion revealed | cyan target, crimson lesion | drill-down dive |
| pivot | brain_void | damaged vs compensatory structures side by side | crimson vs amber-gold | orbit + push-in |
| mechanism / step1–3 | brain_void | `mechanism_steps[i]` along `signal_path` | green signal, cyan target, crimson gap | macro track (step3: pull back to full circuit) |
| breakthrough | pull_out | out of brain into environment; subject shows the proof | amber-gold route inside cranium | pull-out |
| conclusion | real_env | wide resolution scene with cast | cyan + amber-gold inside cranium | rising pull-back |

## R40-A — Prompt Template
```text
{FLOW_PROMPT_PREFIX} {scene} Voice: Puck. Spoken narration: "{narration}"
```
| Rule | Requirement |
|---|---|
| Prefix | Starts with `FLOW_PROMPT_PREFIX` verbatim. |
| Scene | Concise sentences, word count within `PROMPT_SCENE_WORDS_MIN..PROMPT_SCENE_WORDS_MAX`; no redundant modifiers, no duplicated scene anchors. |
| Voice line | Exactly one `Voice: Puck. Spoken narration: "…"`, last in the prompt; narration non-empty. Voice must be in `FLOW_ALLOWED_VOICES`. |
| Forbidden | `Audio:` directive, `#hex` codes, `Camera Angle N` labels, on-screen text instructions (`Display bold white text…`), camera hardware names. |
| Narration | Spoken from frame 0 (no silent hook); word budget per [content_quality_rules.md](file:///g:/My%20Drive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/content_quality_rules.md) (R2). |
| Output | `write_flow_prompts_json` → `03_visuals/flow_all_in_one_prompts.json` = `{schema_version, voice, clips[], prompts[]}`; each clip = `{clip_number, role, setting, camera_move, scene, spoken_narration, prompt}`. |

## R40-B — Sanitizer Constraints (`SAFETY_REPLACEMENTS`)
- Applied to the **scene only**, never to narration.
- Allow-list never replaced: environments (hospital, casino, lab, bed, monitor, EKG, classroom, courtroom…), anatomy (amygdala, fusiform, hippocampus, prefrontal, temporal lobe, white-matter, Broca's area, Wernicke's area…), `wall`, `severed`.
- No venue → studio rewrite, no tripod rewrite. Surname rules are case-sensitive and multi-word only.

## R40-C — `visual_plan` Schema
| Field | Type | Use |
|---|---|---|
| `real_environment` | str | real_env / pull_out backdrop |
| `environment_props` | list[str] | realistic props |
| `scale_anchor_object` | str | R14-A scale anchor (outside brain) |
| `cast` | `{subject, others[]}` | mannequins, fixed across clips |
| `mannequin_actions` | dict role → str | setup, symptom, failure, breakthrough, conclusion |
| `target_region` / `crisis_region` / `crisis_lesion` / `compensatory_region` | str | R21 colour mapping |
| `signal_path` | list[str] | ordered organ → region chain (green signal) |
| `mechanism_steps` | list[str] | visual description of step1..step3 |
| `anatomy_descriptors` | dict region → shape | R38 realistic shape words |
| `bci_hardware` | str \| null | D5 real hardware |
| `scenes` | dict role → str (optional) | hand-authored scene used **verbatim**; otherwise the builder fills role templates |

Load precedence (`load_visual_plan`): `03_visuals/visual_plan.json` > `research_card.json["visual_plan"]` > topic `visual_plan` > `researcher.infer_visual_plan(topic, facts)`.

## R14-B — Banned Prompt Tokens
Checked case-insensitively by `validate_flow_prompts` (`BANNED_PROMPT_TOKENS`) and QA gate G8.

| Group | Tokens |
|---|---|
| Retired formats | mobius, möbius, seamless loop, loop back, locked-off, tripod, 5% push, decoupled kinetic, HUD, telemetry, mute-test |
| Metaphor props | clockwork, gear, tape-reel, tape recorder, brass scale, balance scale, camera shutter, coin, dollar bill |
| Hardware strings | ARRI, Alexa |
| Anti-pixel (`BANNED_STYLE_TOKENS`) | pixel art, 8-bit, 16-bit, voxel, minecraft, retro game, sprite, mosaic, blocky, low-res, low resolution, glitch art, ascii art, dithering, aliased, jagged edges, cartoon, anime, 2d illustration, flat vector, comic book, cel shaded, sketch, hand-drawn |
