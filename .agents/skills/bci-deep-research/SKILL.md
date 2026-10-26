---
name: bci-deep-research
description: Builds the longform-depth research dossier (BCI_Shorts_Channel/research_dossiers/<slug>/) for an ALL ABOUT BRAIN topic before any script or prompt is written - verified primary paper and follow-ups / critiques, the iconic "I know this!" scene broken into era, layout, props, actions and reactions, YouTube / archive reference analysis (yt-dlp keyframes + transcript), plain-language map, brain-region links, visual mode decision and an 8-15 minute longform outline. Use for every new topic and before upgrading any legacy project.
---

# BCI Deep Research — Dossier Builder (Gear 1, R44)

Master: [AGENTS.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/AGENTS.md) · Rules: [research_dossier_rules.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/research_dossier_rules.md) (R44, R50) · [visual_prompt_spec.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/visual_prompt_spec.md) (R45–R48) · [content_quality_rules.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/content_quality_rules.md) (R1, R15 v5) · Code: [`pipeline/research_dossier.py`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/research_dossier.py), [`pipeline/anatomy_map.py`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/anatomy_map.py) · Worked examples: `BCI_Shorts_Channel/research_dossiers/{phineas_gage_iron_rod, invisible_gorilla_attention, pavlov_dogs_conditioning, milgram_obedience_shock}/`

---

## Why
A prompt can only show the scene the audience remembers when the research describes it **physically**. "A scientist tests a dog" produces a generic lab; "a porcelain dog in a leather harness on a wooden stand, a metronome ticking on the shelf, saliva dripping from a glass tube into a graduated cylinder" produces Pavlov. Research is written at longform depth because Shorts that perform become 8–15 minute videos.

## Procedure
| Step | Action | Output |
|---|---|---|
| 1 | `main.py dossier init --slug <slug> --topic "<title>" --pillar <id> --mode <MODE>`; pick the mode topic-first (R45) and write `visual_mode_reason`. | folder + empty schema files |
| 2 | Primary source: find the original paper / report, verify with `main.py dossier doi --doi <doi>` (Crossref), read its methods. Pre-DOI history → `primary_historical` with a verified archival URL. | `01_sources.json` |
| 3 | Breadth: follow-ups / replications / reviews, critiques and misconceptions, biographies, museum objects, documentaries, real-life echoes. Every source gets `verified` from an actual check. | `01_sources.json`, `dossier.json` facts |
| 4 | Reference media: `main.py dossier yt-search --query "<experiment> original footage"`, then `main.py dossier yt-analyze --slug <slug> --url <url> --media-id <id> [--section "*mm:ss-mm:ss"]`. **Look at** `media/<id>/contact_sheet.jpg` and keyframes; write concrete blocking / prop / motion notes. Analysis only — never reuse footage. | `04_media_refs.json`, `media/` |
| 5 | Scene bible: break each key moment into **era, layout (positions + facing), props (period detail + physical behaviour), actions (verb sequence), reactions** + `recognition_hook`. Exactly one `iconic`. Rank `shorts_priority`. | `03_visual_reference.json` |
| 6 | Story: write the longform master story (8 sections) and ≥ 3 ranked wow facts ("no way!"), misconceptions, everyday hooks. | `02_master_story.md`, `dossier.json` |
| 7 | Plain language: one-sentence story, "so what for you", jargon → plain word → analogy. | `05_plain_language.json` |
| 8 | Brain links (HYBRID / NEURO only): regions from `anatomy_map` only, with plain name, function, scene id and the narration bridge that ties the region to what the viewer just saw. | `06_brain_link.json` |
| 9 | Longform: ≥ 5 chapters with beats, scene ids, reusable Shorts roles and new shots; `shorts_extract {hook, core_experiment, twist}`. | `07_longform_outline.json` |
| 10 | Gate: `main.py dossier validate --slug <slug>` → `ready: true`. Then `main.py dossier seed --slug <slug>` and hand off to [bci-script-gen](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/skills/bci-script-gen/SKILL.md). | v5 plan seed |

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
