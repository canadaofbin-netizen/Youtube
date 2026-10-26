# Rule: Research Dossier & Longform Reuse Protocol

Parent Master Index: [AGENTS.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/AGENTS.md) · Numbers: [production_constants.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/production_constants.md) · Code: [`pipeline/research_dossier.py`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/research_dossier.py), [`pipeline/asset_manifest.py`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/asset_manifest.py) · Skill: [bci-deep-research](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/skills/bci-deep-research/SKILL.md)

Why: prompts can only show "the scene everybody knows" (the rod through Gage's skull, the gorilla walking through the passers, the dog drooling at a sound, the teacher pressing the switch) when research captures the **physical** event — who stood where, what was in their hands, what moved — not just a summary. Shorts that perform become longform, so research is written at longform depth from day one.

---

## R44 — Research Dossier (mandatory before Gear 2)
Location: `BCI_Shorts_Channel/research_dossiers/<slug>/` (one per topic, shared by Shorts and longform; projects link to it through `visual_plan.dossier`).

| File | Content |
|---|---|
| `dossier.json` | `visual_mode` + `visual_mode_reason` (R45), `primary_case`, `core_facts`, `wow_facts` (≥ 3, ranked), `misconceptions`, `everyday_hooks`, `linked_projects` |
| `01_sources.json` | primary (DOI verified via Crossref) or `primary_historical` (verified archival URL), replications / follow-ups / reviews, critiques, books, biographies, archives, museums, documentaries |
| `02_master_story.md` | longform storyline: cold open → world before → people → event step by step → results (as reported) → twist / controversy → aftermath → what it means for you |
| `03_visual_reference.json` | scenes with the 5 required fields **era, layout (blocking + positions), props (period detail + physical behaviour), actions (verb sequence), reactions** + `recognition_hook`, wardrobe, lighting, sources. Exactly one `iconic: true` |
| `04_media_refs.json` | YouTube / archive film / photos / museum objects with timecodes and shot notes |
| `media/<id>/` | `analyze_reference_video` output: scene keyframes, contact sheet, transcript (analysis only) |
| `05_plain_language.json` | one-sentence story, "so what for you", jargon → plain word → analogy |
| `06_brain_link.json` | region ↔ plain name ↔ function ↔ scene ↔ narration bridge (anatomy_map regions only); empty for `BEHAVIORAL_PSYCH` |
| `07_longform_outline.json` | ≥ 5 chapters (beats, scene ids, reusable Shorts roles, new shots needed) + `shorts_extract {hook, core_experiment, twist}` |

**Research checklist** (`RESEARCH_CHECKLIST`, enforced by `validate_dossier`): primary source · method details (layout + ≥ 1500-char story) · follow-up · critique / misconception · people · visual media · iconic scene with all 5 fields · ≥ 3 wow facts · everyday hook · plain-language map · brain link (NEURO / HYBRID) · longform outline. Gear 2 starts only when `validate_dossier(slug)["ready"]` is true.

### R44-D — Depth standard (how detailed is detailed enough)
Rule of thumb: research is deep enough when **someone who has never seen the original footage could stage the iconic scene from the dossier alone**, with every number in the script traceable to a source. `research_depth_report` (inside `validate_dossier`, checklist key `depth_standard`) enforces:

| Area | Minimum (constant) | Why |
|---|---|---|
| Sources | ≥ `DOSSIER_MIN_SOURCES` (6), incl. verified primary + ≥ `DOSSIER_MIN_FOLLOWUP_SOURCES` (2) follow-up / replication / review + 1 critique or misconception | one paper is not a story; critiques stop myths |
| Facts | ≥ `DOSSIER_MIN_CORE_FACTS` (8) `core_facts {fact, source_id}`; every `source_id` exists in `01_sources.json` | every number on screen has an owner |
| Script numbers | every number in the subtitles (`to_display_text`) appears in the dossier (`check_narration_facts`, prompt-gate tag `[fact]`) | no invented statistics |
| Master story | ≥ `DOSSIER_MIN_STORY_CHARS` (6000) chars | longform reuse |
| Media | ≥ `DOSSIER_MIN_MEDIA` (2) entries, each ≥ `DOSSIER_MIN_MEDIA_TIMECODES` (2) timecoded shot notes `{t, what}`; ≥ `DOSSIER_MIN_ANALYZED_MEDIA` (1) analysed on disk (`media/<id>/keyframes` ≥ `DOSSIER_MIN_KEYFRAMES` = 8, via `dossier yt-analyze`) | the video is converted into text the prompt can use |
| Shot notes | each note says **who, where on screen, what moves, what the prop does, how long** ("00:25 enters from the right edge in front of the rightmost door … 00:34 exits left, 9 s on screen") | becomes blueprint beats with evidence |
| Iconic scene | layout positions ≥ `DOSSIER_MIN_ICONIC_POSITIONS` (2) (who / where / facing); props ≥ `DOSSIER_MIN_ICONIC_PROPS` (2) with `period_detail` (size, material, colour) + `physical_behavior`; wardrobe, lighting, sources; **`key_visual {description, must_show, source}`** (R46-K) | the scene can be staged and the money shot cannot be skipped |

**Where to look** (in order): the primary paper and its methods section → follow-up / replication / review papers (PubMed, Google Scholar) → critiques and books (e.g. Macmillan on Gage, Perry on Milgram) → museum and university archives (Warren Anatomical Museum, Yale archives) → original footage and famous recreations on YouTube (`dossier yt-search`, `dossier yt-analyze`) → reputable journalism for real-life echoes. Reference footage is **analysis only**; nothing is reused in channel videos.

**Tools (free, local):** `verify_doi` (Crossref), `research_depth_report`, `check_narration_facts`, `search_youtube` / `analyze_reference_video` (yt-dlp + ffmpeg scene keyframes + faster-whisper), `plan_seed_from_dossier` (→ draft v5 `visual_plan`).

## R50 — Asset Manifest & Longform Readiness
| Item | Requirement |
|---|---|
| Two tiers | Dossier = longform depth. Short = extract of `shorts_extract` (hook + core experiment + twist). |
| Manifest | Every assembly writes `05_assembly/asset_manifest.json` (`build_asset_manifest`): per clip `asset_id = <topic_slug>_<role>_<shot_type>`, scene id, mode, setting, camera, aspect, file + sha256, scene, narration, full prompt, Flow model / project URL / seed (when exposed), source in/out used in the Short, timeline start, voice source, longform reuse hint. |
| Library | One line per clip in `BCI_Shorts_Channel/asset_library/index.jsonl` (`upsert_library`, `search_library`). |
| Aspect-neutral prompts | Scene text never mentions the aspect; only `flow_prompt_prefix(aspect)` does, so `build_flow_prompts(plan, narrations, aspect="16:9")` re-generates the same scene for longform. `FLOW_MOTION_STYLE_V5` keeps the key action centred so 9:16 clips also survive pillarbox / blurred-fill reuse. |
| Longform plan | `07_longform_outline.json` marks per chapter which Shorts clips are reused, which scenes are re-generated at 16:9 and which bridge clips are new. |
