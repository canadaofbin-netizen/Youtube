---
name: bci-deep-research
description: Builds the longform-depth research dossier (BCI_Shorts_Channel/research_dossiers/<slug>/) for an ALL ABOUT BRAIN topic before any script or prompt is written - verified primary paper and follow-ups / critiques, the iconic "I know this!" scene broken into era, layout, props, actions and reactions, YouTube / archive reference analysis (yt-dlp keyframes + transcript), plain-language map, brain-region links, visual mode decision and an 8-15 minute longform outline. Use for every new topic and before upgrading any legacy project.
---

# BCI Deep Research — Dossier Builder (Gear 1, R44)

Master: [AGENTS.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/AGENTS.md) · Rules: [research_dossier_rules.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/research_dossier_rules.md) (R44, R50) · [visual_prompt_spec.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/visual_prompt_spec.md) (R45–R48) · [content_quality_rules.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/content_quality_rules.md) (R1, R15 v5) · Code: [`pipeline/research_dossier.py`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/research_dossier.py), [`pipeline/anatomy_map.py`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/anatomy_map.py) · Worked examples: `BCI_Shorts_Channel/research_dossiers/{phineas_gage_iron_rod, invisible_gorilla_attention, pavlov_dogs_conditioning, milgram_obedience_shock}/`

---

## Why
A prompt can only show the scene the audience remembers when the research describes it **physically**. "A scientist tests a dog" produces a generic lab; "a porcelain dog in a leather harness on a wooden stand, a metronome ticking on the shelf, saliva dripping from a glass tube into a graduated cylinder" produces Pavlov. Research is written at longform depth because Shorts that perform become 8–15 minute videos.

## Procedure (`Schema v2` — 3-Layer Formula + Dual-Track Conditioning + 3-Stage Debate Ignition)
| Step | Action | Output |
|---|---|---|
| 1 | `main.py dossier init --slug <slug> --topic "<title>" --pillar <id> --everyday-domain <sleep\|habits\|memory\|anxiety\|relationships> --mode HYBRID`; populate `everyday_domain` and `visual_mode_reason`. | `Schema v2` folder + schema files |
| 2 | **3-Layer Source Pairing**: verify (a) classic/modern **Behavioral Psychology Experiment** source (`verify_doi` via Crossref or `primary_historical` archival URL) AND (b) distinct **`>= 2015` Neural Circuit / fMRI / EEG / Two-Photon / BCI** paper (`verify_doi` via Crossref). Record both in `01_sources.json` and link their `source_id`s in `dossier.json.three_layer_formula`. | `01_sources.json`, `three_layer_formula` |
| 3 | Breadth: ≥ 6 total verified sources incl. ≥ 2 follow-ups / replications / modern imaging studies and ≥ 1 critique or misconception check; ≥ 8 `core_facts` with `source_id`s. | `01_sources.json`, `dossier.json` facts |
| 4 | **Live Reference Media & Dual-Track Classification**: `main.py dossier yt-search --query "<experiment> archival footage"`, then `main.py dossier yt-analyze --slug <slug> --url <url> --media-id <id> [--section "*mm:ss-mm:ss"]` and `main.py dossier audit-media --slug <slug> --write` (`suitability_schema_version: 2`, 4-Gate CV/YuNet/transcript suitability filter). For **`track_a`**, lock explicit `reenactment_section` (`MM:SS-MM:SS`) in `04_media_refs.json` and run `main.py reenact-extract --source <url> --slug <slug> --section <MM:SS-MM:SS>` so `08_reenactment_edl.json` (`shot_count >= 3`, `sanitization_verified: true`) is recorded before Gear 2. **Look at** `media/<id>/contact_sheet.jpg`; write concrete blocking/prop notes. Zero source pixels reused. | `04_media_refs.json`, `08_reenactment_edl.json`, `media/` |
| 5 | Scene bible: break each key moment into **era, layout (positions + facing), props (`name` + `period_detail` + `physical_behavior`), actions (verb sequence), reactions** + `recognition_hook` + `key_visual`. Exactly one `iconic`. Rank `shorts_priority`. | `03_visual_reference.json` |
| 6 | Story & **3-Stage Debate Ignition**: write the `>= 6,000`-char master story (8 sections), ≥ 3 ranked wow facts, misconceptions, everyday hooks, and `dossier.json.debate_ignition` (`prebunk_myth`, binary `open_verdict_question` `... or ...?`, and `offcenter_creator_bet` with a 1st-person creator bet in the first `<= 45` chars passing `validate_debate_pinned_comment_line1`). | `02_master_story.md`, `dossier.json` |
| 7 | Plain language: one-sentence story, "so what for you", jargon → plain word → analogy. | `05_plain_language.json` |
| 8 | Brain links (HYBRID / NEURO only): regions from `anatomy_map` only, with plain name, function, scene id and the narration bridge that ties the region to what the viewer just saw. | `06_brain_link.json` |
| 9 | Longform: ≥ 5 chapters with beats, scene ids, reusable Shorts roles and new shots; `shorts_extract {hook, core_experiment, twist}`. | `07_longform_outline.json` |
| 10 | Gate: `main.py dossier validate --slug <slug> --require-v2` → `ready: true`. Then `main.py dossier seed --slug <slug> --profile neuro_diorama` (compiles `porcelain_cinematic_v7` + `populate_porcelain_reference_contract`) and hand off to [bci-script-gen](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/skills/bci-script-gen/SKILL.md). | v7 Dual-Track plan seed |

## What to research (checklist, `RESEARCH_CHECKLIST`)
| Item | Typical sources |
|---|---|
| Primary paper + methods | journal article, original book / report |
| Exact procedure | methods section, lab notebooks, archive photos (room, apparatus, durations, numbers) |
| Follow-ups | replications, modern imaging, reviews |
| Critiques / myths | critical books and papers, failed replications, popular misconceptions |
| People & era | biographies, obituaries, university histories |
| Visual media | original footage, archive photos, museum artefacts, famous recreations (YouTube) |
| Iconic scene | the 5 required fields + the recognition hook |
| Wow facts / everyday hooks | the paper's most surprising numbers, real-life cases, how it shows up in daily life |
| Brain link | textbook region functions (anatomy_map), conservative claims |
| Longform | chapters, sub-stories, aftermath |

## Self-check
- Every number and name traces to a `source_id`; nothing invented.
- The iconic scene could be staged by a film crew from the JSON alone.
- BEHAVIORAL_PSYCH dossiers plan no on-screen brain.
- Interpreter: `/home/canadaofbin/hermes-venv/bin/python -X utf8`; run multi-line code from script files; pass `< /dev/null` when ffmpeg runs in the background.
