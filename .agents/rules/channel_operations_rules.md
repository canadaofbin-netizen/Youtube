# Rule: Channel Operations & Workspace Hygiene Protocol

Parent Master Index: [AGENTS.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/AGENTS.md) · Numbers: [production_constants.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/production_constants.md)

---

## R8 — Title Formula
- English (`TITLE_DESCRIPTION_LANGUAGE_CODE`), length ≤ the title limit in production_constants.md (truncated by `PublishStage`).
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
| `05_assembly/` | `final_shorts_1080x1920.mp4`, `probe_report.json`, `video_autopsy_report.json`, `master_qa_report.json` |
| `06_publish/` | `metadata.json`, `thumbnail_var_A/B/C.png`, `ab_test_manifest.json`, `upload_receipt.json`, `community_receipt.json` |

Clip count N = `CLIP_COUNT_MIN..CLIP_COUNT_MAX`; final duration bounds `FINAL_SHORTS_DURATION_MIN_SEC..FINAL_SHORTS_DURATION_MAX_SEC`. Every project in `BCI_Shorts_Channel/projects/` must conform strictly to Production Contract v4 (`schema_version: 4`).

## Shared Locations
| Path | Purpose |
|---|---|
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
