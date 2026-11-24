---
trigger: model_decision
description: "Load when working on project directory layout (00_project_manifest..06_publish), Google Flow AAB_<project_id> rooms, fuse.rclone hygiene, tmp_path tests, atomic resume, or artifacts_archive sync (R11-R12, R19, R28-R29)."
---

# Project Storage, Flow Room & Archive Hygiene (`R11–R12`, `R19`, `R28–R29`)

Index: [AGENTS.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/AGENTS.md) | Code: [`pipeline/storage.py`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/storage.py) | Archive Hook: [`scripts/sync_archive.py`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/scripts/sync_archive.py)

## R11–R12 — Project & Shared Workspace Layout (`ProjectStorage`)
`BCI_Shorts_Channel/projects/<project_id>/`:
- `00_project_manifest.json`: Stage status, `word_count`, `doi`, timestamps (`R29` atomic temp-write auto-repair).
- `01_ideation/`: Optional `research_card.json` (created lazily only when written).
- `02_script/`: `script.json`, `script.md`, `qa_report.json`.
- `03_visuals/`: `visual_plan.json`, `reference_image_specs.json`, `reference_images/`, `flow_all_in_one_prompts.json`, `flow_provenance_receipt.json`, `flow_native_clips/`.
- `04_audio/`: `audio_master.wav`, `subtitles.ass`, `prosody_report.json`.
- `05_assembly/`: `final_shorts_1080x1920.mp4`, `edit_decision_list.json`, `asset_manifest.json`, `probe_report.json`, `video_autopsy_report.json`, `dynamic_episode_qa_report.json`, `posthoc_semantic_qa_report.json`, `master_qa_report.json`.
- `06_publish/`: `metadata.json`, `thumbnail_selected.png`, `thumbnail_report.json`, `upload_receipt.json`, `community_receipt.json`, `related_video_receipt.json`.
- Root export (`R83-4`): Mirror completed/remade MP4 to `07_Youtube/final_shorts_<project_id>.mp4`.

Shared under `BCI_Shorts_Channel/`: `research_dossiers/<slug>/`, `knowledge_base/` (`telemetry/`, `reusable_packs/`), `asset_library/index.jsonl`, `database/`, `reports/daily/`.

## Flow Rooms, `fuse.rclone` & `artifacts_archive/`
- **Flow Room**: `AAB_<project_id>` (`1` room/ep; `FLOW_AUTO_CLEANUP_ON_SUCCESS = False` — NEVER delete Flow rooms/assets). Claim dedicated `targetId` tabs (`allocate_dedicated_flow_project_tab`); never touch sibling tabs.
- **FUSE Mount**: `/home/canadaofbin/gdrive` is `fuse.rclone` (`0` POSIX symlinks); use `rclone delete`/`rclone purge --fast-list` for bulk media cleanup.
- **Artifacts Archive**: `.agents/hooks.json` runs `scripts/sync_archive.py` to mirror active chatroom brain reports/charts into `artifacts_archive/` and update `artifacts_archive/INDEX.md`.

## R19, R28, R29 — Ending, Test & Recovery Locks
- **R19**: Independent elevated conclusion scene; zero loop-back to Clip 1.
- **R28**: `tests/` (`pytest.ini`) use `tmp_path` only and never mutate `BCI_Shorts_Channel/projects/`.
- **R29**: Atomic temp-writes; `main.py ep run <project_id>` resumes cleanly from on-disk stage receipts.
