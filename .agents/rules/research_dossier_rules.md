# Research Dossier, Media Audit & Knowledge Hub (`R44`, `R44-D`, `R44-M`, `R50`, `R50-B`)

Index: [AGENTS.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/AGENTS.md) | Numbers: [production_constants.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/production_constants.md) | Skill: [youtube-research](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/skills/youtube-research/SKILL.md) | Code: [`pipeline/research_dossier.py`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/research_dossier.py), [`pipeline/asset_manifest.py`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/asset_manifest.py), [`pipeline/knowledge_hub.py`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/knowledge_hub.py)

## R44 — Schema v2 Topic Dossier (`BCI_Shorts_Channel/research_dossiers/<slug>/`)
Gate before Gear 2: `main.py dossier validate --slug <slug> --require-v2` (`validate_dossier(..., require_schema_v2=True)["ready"] == True`).
| File | Contract |
|---|---|
| `dossier.json` | `schema_version: 2`, `everyday_domain` (`EVERYDAY_LONGFORM_DOMAINS`), `three_layer_formula` (`everyday_problem`, `psychology_experiment`, `neuroscience_mechanism`, `psychology_studies`, `neuroscience_studies` with `year >= DOSSIER_NEURO_MODERN_MIN_YEAR`), `debate_ignition` (`prebunk_myth`, binary `open_verdict_question`, `offcenter_creator_bet` passing `validate_debate_pinned_comment_line1`), `visual_mode` + `visual_mode_reason`, `primary_case`, `core_facts`, `wow_facts` (`>= 3`), `misconceptions`, `everyday_hooks`, `linked_projects` |
| `01_sources.json` | Verified Behavioral Psych DOI + distinct verified `>= DOSSIER_NEURO_MODERN_MIN_YEAR` Neuro/Imaging/BCI DOI (`verify_doi`), replications/follow-ups, critiques, archives (`>= DOSSIER_MIN_SOURCES`, `>= DOSSIER_MIN_FOLLOWUP_SOURCES`) |
| `02_master_story.md` | Full narrative (`>= DOSSIER_MIN_STORY_CHARS`): cold open -> world before -> people -> step-by-step method -> exact results -> twist/critique -> aftermath -> viewer takeaway |
| `03_visual_reference.json` | Scenes with `era`, `layout` (`>= DOSSIER_MIN_ICONIC_POSITIONS`), `props` (`>= DOSSIER_MIN_ICONIC_PROPS` with `period_detail` + `physical_behavior`), `actions`, `reactions`, `recognition_hook`, `key_visual {description, must_show, source}` (`R46-K`); exactly 1 `iconic: true` |
| `04_media_refs.json` | `suitability_schema_version: 2`, `reenactment_track` (`track_a` \| `track_b`), `primary_reenactment_media_id`, `>= DOSSIER_MIN_MEDIA` items each with `>= DOSSIER_MIN_MEDIA_TIMECODES` `{t, what}` notes, plus `reenactment_section` (`MM:SS-MM:SS`) for Track A |
| `05_plain_language.json` | 1-sentence story, `"so what for you"`, `jargon -> plain word -> analogy` |
| `06_brain_link.json` | `region <-> plain name <-> function <-> scene <-> narration` (`{}` when `BEHAVIORAL_PSYCH`) |
| `07_longform_outline.json` | `>= 5` chapters + `shorts_extract {hook, core_experiment, twist}` |
| `08_reenactment_edl.json` | Required on `track_a`: quarantined structural shot EDL (`shot_count >= 3`, `sanitization_verified: true`, dHash + 5-gram hashes, zero raw pixels) |

## R44-D & R44-M — Depth & 4-Gate Media Suitability (`dossier audit-media`)
- **R44-D (`research_depth_report`)**: `>= DOSSIER_MIN_CORE_FACTS` `{fact, source_id}` mapped to `01_sources.json`; every subtitle number verified by `check_narration_facts` (`[fact]`); `>= DOSSIER_MIN_ANALYZED_MEDIA` (`media/<id>/keyframes >= DOSSIER_MIN_KEYFRAMES` or `08_reenactment_edl.json`).
- **R44-M (`evaluate_media_reenactment_suitability` -> `MEDIA_SUITABILITY_CLASSES`)**:
  1. **Gate 1 (Blocklist & Era)**: Rejects `MEDIA_REJECT_CHANNEL_PATTERNS` (TED/SciShow/CrashCourse/Huberman/etc.) & pre-`MEDIA_MIN_CINEMA_YEAR` non-recreation topics -> `reject_track_b_only`.
  2. **Gate 2 (Dark Void)**: Rejects median dark ratio (`Y < 35`) `> MEDIA_MAX_DARK_VOID_RATIO`.
  3. **Gate 3 (2D Slide vs 16mm B&W)**: Rejects flat color slides (`flat_ratio > MEDIA_MAX_FLAT_SLIDE_RATIO`) & static frames (`< MEDIA_MIN_MOTION_DIFF`), exempting true 16mm B&W archival film (`MEDIA_BW_ARCHIVAL_SAT_MAX`, `MEDIA_BW_FRAME_P90_SAT_MAX`).
  4. **Gate 4 (YuNet Talking-Head & Windowing)**: Rejects talking heads via `YUNET_FACE_MODEL_PATH` + WPS; routes `> MEDIA_MAX_UNWINDOWED_DURATION_SEC` videos to `needs_section_window` (`recommended_section`).

## R50 & R50-B — Asset Manifest & Knowledge Hub (`main.py asset-manifest`, `main.py kb`)
- **R50 (`05_assembly/asset_manifest.json` + `asset_library/index.jsonl`)**: Logs per-clip `asset_id`, grammar, camera, SHA-256, prompt, Flow model/URL, EDL in/out, R64 `clarity_score`, and reuse hints (`aspect`-neutral scene text via `flow_prompt_prefix(aspect)`).
- **R50-B (`KNOWLEDGE_BASE_DIR`)**: `telemetry/` (`EPISODES_INDEX_FILENAME`, `CLIP_CLARITY_LEDGER_FILENAME`, `QA_ANALYTICS_SUMMARY_FILENAME`) + `reusable_packs/` (`prompts_golden_bank.json`, `analogies_registry.json`, `brain_models_registry.json`, `locations_and_props_registry.json`; optional `EXPERIMENTS_ARCHIVE_DIRNAME`).
