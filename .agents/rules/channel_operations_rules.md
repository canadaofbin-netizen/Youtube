# Channel Operations & Workspace Layout (`R8–R12`, `R19`, `R28`, `R29`)

Index: [AGENTS.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/AGENTS.md) | Numbers: [production_constants.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/production_constants.md) | Code: [`pipeline/storage.py`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/storage.py), [`pipeline/publish.py`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/publish.py)

## R8–R10 — Metadata Contract
- **R8 Title**: `en-US` (`TITLE_DESCRIPTION_LANGUAGE_CODE`); `neuro_diorama` uses 5-Archetype US Paradox Title `<= TITLE_MAX_CHARS_DIORAMA` (`R60`, zero all-caps spam, zero claims beyond DOI).
- **R9 Description**: `DESCRIPTION_EDITORIAL_TEMPLATES` (`publish.py`): 1-line case hook, plain-English mechanism, `https://doi.org/<doi>`, `AI_DISCLOSURE_SENTENCE` (`R4`), `#Shorts`.
- **R10 Hashtags**: Starts with `#Shorts` and `#Neuroscience` + pillar/topic tags.

## R11–R12 — Project & Shared Workspace Layout (`ProjectStorage`)
`BCI_Shorts_Channel/projects/<project_id>/`:
| Path | Artifacts |
|---|---|
| `00_project_manifest.json` | Stage status, `word_count`, `doi`, timestamps (`R29` atomic temp-write auto-repair) |
| `01_ideation/` | `research_card.json` (`story_context`, `doi`, `visual_plan`) |
| `02_script/` | `script.json`, `script.md`, `qa_report.json` |
| `03_visuals/` | `visual_plan.json`, `reference_image_specs.json`, `reference_images/`, `flow_all_in_one_prompts.json`, `flow_provenance_receipt.json`, `flow_native_clips/` |
| `04_audio/` | `audio_master.wav`, `subtitles.ass`, `prosody_report.json` |
| `05_assembly/` | `final_shorts_1080x1920.mp4`, `edit_decision_list.json`, `asset_manifest.json`, `probe_report.json`, `video_autopsy_report.json`, `dynamic_episode_qa_report.json`, `posthoc_semantic_qa_report.json`, `master_qa_report.json` |
| `06_publish/` | `metadata.json`, `thumbnail_var_A/B/C.png`, `thumbnail_report.json`, `upload_receipt.json`, `community_receipt.json`, `related_video_receipt.json` |

Shared directories under `BCI_Shorts_Channel/`:
- `research_dossiers/<slug>/`: Schema v2 topic dossiers (`R44`).
- `knowledge_base/`: `telemetry/` (`episodes_index.jsonl`, `clip_clarity_ledger.jsonl`, `qa_analytics_summary.json`) + `reusable_packs/` (`pipeline/knowledge_hub.py`, `R50-B`).
- `asset_library/index.jsonl`: Reusable clip index (`pipeline/asset_manifest.py`, `R50`).
- `database/`: Topic/prompt DB (`pipeline/prompts_db.py`).
- `reports/daily/`: Studio KPI reports (`youtube-report`).

## Google Flow Room & FUSE Storage Hygiene
- **Flow Workspace**: Canonical room name `AAB_<project_id>` (1 room per episode; delete temporary/orphan Flow rooms & assets after harvest). Workers bind dedicated `targetId` tabs (`allocate_dedicated_flow_project_tab`) and never steal/close sibling tabs.
- **FUSE Mount**: `/home/canadaofbin/gdrive` is `fuse.rclone` — never create POSIX symlinks inside gdrive; use `rclone delete`/`rclone purge --fast-list` + local POSIX verification for bulk media cleanup.

## R19, R28, R29 — Ending, Test & Recovery Locks
- **R19**: Independent elevated conclusion scene; zero loop-back to Clip 1, zero center-frame title overlay on v4/v5.
- **R28**: Tests (`tests/`, `pytest.ini`) use `tmp_path` fixtures only and never create or mutate project folders inside `BCI_Shorts_Channel/projects/`.
- **R29**: `ProjectStorage` uses atomic writes; `PipelineOrchestrator.resume_project(project_id)` resumes from last completed stage.
