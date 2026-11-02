# Rule: Channel Operations & Workspace Hygiene Protocol

Parent Master Index: [AGENTS.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/AGENTS.md) · Numbers: [production_constants.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/production_constants.md)

---

## R8 — Title Formula
- English (`TITLE_DESCRIPTION_LANGUAGE_CODE`), length ≤ the title limit in production_constants.md (truncated by `PublishStage`; `TITLE_MAX_CHARS_DIORAMA` for Schema v6 `neuro_diorama` 2-Clause Paradox Titles per `R60` in [neuro_diorama_rules.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/neuro_diorama_rules.md)).
- Triangular hook: **[concrete action or number] + [anatomical / clinical anomaly] + [curiosity trigger]**, consistent with the setup/symptom narration (R42). No all-caps spam, no claims beyond the paper (R1).

## R9 — Description
Structured academic summary: case in one line, the mechanism chain in plain words, `https://doi.org/<doi>` link, AI-disclosure note, `#Shorts`.

## R10 — Hashtags
Exactly the hashtag count in production_constants.md, starting with `#Shorts` and `#Neuroscience`, then pillar/topic tags.

## R11–R12 — Lossless Project Layout
`BCI_Shorts_Channel/projects/<project_id>/` (managed by `ProjectStorage`, `pipeline/storage.py`):

| Path | Contents |
|---|---|
| `00_project_manifest.json` | status, `word_count`, `doi`, stage timestamps |
| `01_ideation/` | `research_card.json` (`story_context`, `doi`, optional `visual_plan`) |
| `02_script/` | `script.json` (`clip_narrations`), `script.md`, `qa_report.json` |
| `03_visuals/` | optional `visual_plan.json`, `flow_all_in_one_prompts.json` (schema v4), `flow_provenance_receipt.json`, `flow_screenshots/`, `flow_native_clips/clip_1..clip_N.mp4` |
| `04_audio/` | `audio_master.wav`, `subtitles.ass` |
| `05_assembly/` | `final_shorts_1080x1920.mp4`, `edit_decision_list.json` (`neuro_diorama`), `asset_manifest.json` (R50), `probe_report.json`, `video_autopsy_report.json`, `dynamic_episode_qa_report.json` (R62), `posthoc_semantic_qa_report.json` + `posthoc_viewer_strips/` (R64), `master_qa_report.json` |
| `06_publish/` | `metadata.json`, `thumbnail_var_A/B/C.png`, `ab_test_manifest.json`, `upload_receipt.json`, `community_receipt.json` |

Clip count N = `CLIP_COUNT_MIN..CLIP_COUNT_MAX` (`DIORAMA_CLIP_COUNT_MIN..DIORAMA_CLIP_COUNT_MAX` for `neuro_diorama`); final duration bounds `FINAL_SHORTS_DURATION_MIN_SEC..FINAL_SHORTS_DURATION_MAX_SEC` (`DIORAMA_DURATION_MIN_SEC..DIORAMA_DURATION_MAX_SEC` for `neuro_diorama`).

## Shared Locations
| Path | Purpose |
|---|---|
| `BCI_Shorts_Channel/knowledge_base/` | accumulated episode telemetry (`telemetry/episodes_index.jsonl`, `clip_clarity_ledger.jsonl`, `qa_analytics_summary.json`, `qa_analytics_report.md`), reusable asset packs (`reusable_packs/prompts_golden_bank.json`, `analogies_registry.json`, `brain_models_registry.json`, `locations_and_props_registry.json`), and dated parameter experiments (`experiments/`) managed by `pipeline/knowledge_hub.py` (`main.py kb`, R50-B) |
| `BCI_Shorts_Channel/asset_library/` | per-clip longform reuse index (`index.jsonl`) populated by `pipeline/asset_manifest.py` (R50) |
| `BCI_Shorts_Channel/database/` | topic → prompt database built by `pipeline/prompts_db.py` (`all_about_brain_3000_prompts.db`, `brain_1500_prompts_db.jsonl`, `psychology_1500_prompts_db.jsonl`, `database_manifest.json`) |
| `BCI_Shorts_Channel/research/` | background research; docs 04 and 06 are superseded by visual_prompt_spec.md |
| `BCI_Shorts_Channel/reports/` | daily studio reports (`/report_youtube`) |

## R19 — Independent Conclusion Ending
The final clip is a self-contained conclusion scene in the real environment (role `conclusion`, rising pull-back, R14-D) that opens with the R26 conclusion opener. It never returns to clip 1 framing, no loop tail, no centre-frame title text.

## R28 — Test Hygiene
- Tests live in `tests/` and `pipeline/test_*.py` (collected via `pytest.ini`; shared fixtures in `tests/conftest.py`).
- Tests use temporary directories and clean up in `try…finally` / fixtures; they never read or write real project data on Drive.

## R29 — Defensive Manifest & Recovery
`ProjectStorage` auto-repairs missing stage keys with atomic temp-file writes; `PipelineOrchestrator.resume_project(project_id)` resumes from the last completed stage.
