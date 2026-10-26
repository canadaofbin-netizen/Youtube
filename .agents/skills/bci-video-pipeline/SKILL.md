---
name: bci-video-pipeline
description: Master end-to-end orchestrator for ALL ABOUT BRAIN YouTube Shorts across the 5-Gear pipeline - case research with verified DOI, hand-authored clip narrations and visual_plan rendered by flow_prompt_builder, Google Flow Omni 1.1 generation in visible Naver Whale tabs, ASR-ordered assembly with Puck voice, subtitles and 4-layer soundscape, QA gates, and YouTube Studio staging.
---

# BCI Video Pipeline (Master Orchestrator)

Master: [AGENTS.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/AGENTS.md) · Numbers: [production_constants.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/production_constants.md)

Run gears in order; each gear's outputs are the next gear's inputs. Stop on any failed gate.

| Gear | Stage dir | Skill / code | Output | Rules |
|---|---|---|---|---|
| 1a Topic discovery | `01_ideation` | [bci-news-hunt](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/skills/bci-news-hunt/SKILL.md) · `TopicResearcher` | shortlisted case + DOI, duplicate check | R1, P1, R20 |
| 1b Research dossier | `research_dossiers/<slug>/` | [bci-deep-research](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/skills/bci-deep-research/SKILL.md) · `research_dossier` | longform-depth dossier, `dossier validate` ready | R44, R45 |
| 2 Script + prompts | `02_script`, `03_visuals` | [bci-script-gen](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/skills/bci-script-gen/SKILL.md) (v5 procedure) · `flow_prompt_builder` | `script.json`, v5 `visual_plan.json`, `flow_all_in_one_prompts.json` (schema 5), `prompt-gate` pass | R2, R42, R26, R24, R40-A/C, R45–R48, R15 v5, R18-V5 |
| 3 Flow generation | `03_visuals` | `flow-parallel` · `FlowProjectSubagentWorker` | `flow_native_clips/clip_1..clip_N.mp4`, `flow_provenance_receipt.json`, `flow_screenshots/`; voice outliers regenerated | R5, R18-B, R37, R39, R49 |
| 4 Assembly | `04_audio`, `05_assembly` | [bci-video-assembly](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/skills/bci-video-assembly/SKILL.md) | `voice_report.json` (native or Kokoro fallback), `audio_master.wav`, `subtitles.ass`, `final_shorts_1080x1920.mp4`, `asset_manifest.json`, autopsy + QA reports | R13, R16, R17, R41, R43-A/B, R25, R49, R50 |
| 5 Publish + Studio | `06_publish` | `PublishStage` · [youtube-studio-manager](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/skills/youtube-studio-manager/SKILL.md) | `metadata.json`, thumbnails A/B/C, upload / community receipts | R8–R10, R30–R36, R4 |

## Commands
```bash
python -X utf8 main.py research --query "Capgras delusion" --style case_file --save-project <project_id>
python -X utf8 main.py dossier init --slug <slug> --topic "<title>" --pillar <id> --mode HYBRID
python -X utf8 main.py dossier yt-search --query "<experiment> original footage"
python -X utf8 main.py dossier yt-analyze --slug <slug> --url <url> --media-id <id>
python -X utf8 main.py dossier validate --slug <slug>
python -X utf8 main.py prompt-gate --dir BCI_Shorts_Channel/projects/<project_id>
python -X utf8 main.py produce --pillar brain_mysteries --topic "Capgras Delusion" --style case_file --project <project_id>
python -X utf8 main.py flow-parallel --projects <p1>,<p2> --max-batch 5 --trigger
python -X utf8 main.py voice-check --project <project_id>
python -X utf8 main.py import-clips --project <project_id> --dir "<download_dir>" --auto-assemble
python -X utf8 main.py qa --project <project_id>
python -X utf8 main.py audit-prompts
python -X utf8 main.py studio-upload --project <project_id> --visibility unlisted
```
`produce` runs Gears 1–2 automatically from v4 templates; for publishable quality, build the dossier and replace the generated narrations / `visual_plan` with the v5 hand-authored versions from bci-script-gen, and pass `prompt-gate` before Gear 3. `--max-batch` is capped by `FLOW_MAX_PARALLEL_BATCH_SIZE` (R37 Guard 6).

## Environment & Pitfalls
- **Python interpreter**: Run pipeline and Flow worker commands with `/home/canadaofbin/hermes-venv/bin/python -X utf8` (which has `cv2`, `faster_whisper`, `websockets`, and `pytest` installed) rather than bare `python3`.
- **Pipeline rule updates vs. cached project artifacts**: When script or prompt rules update (e.g. R24 banning `Step one / Step two / Step three`), existing entries in `pipeline/topics_catalog.py`, `02_script/script.json`, and `03_visuals/flow_all_in_one_prompts.json` may still hold legacy text. Re-author and re-validate `script.json`, `visual_plan.json`, and `flow_all_in_one_prompts.json`, and purge `03_visuals/flow_native_clips/*.mp4`, `03_visuals/flow_downloads/*.mp4`, `03_visuals/raw_assets/*.mp4`, `03_visuals/raw_clips/*.mp4`, and `03_visuals/flow_provenance_receipt.json` before invoking `flow_live_single_worker.py` — the worker skips generation if `len(existing_native_clips) >= len(prompts)` on disk.
- **Bulk file/directory operations on Google Drive FUSE (`gdrive`)**: Moving multiple `.mp4` files across directories inside `execute_code` (`shutil.move`), running `du -sh` across large project trees, or running `rm -rf` over dozens of project directories on the `fuse.rclone` mount issues thousands of sequential per-file FUSE RPCs and times out. Use `rclone purge gdrive:Kyubin_Yun_Workspace/07_Youtube/<dir>` (followed by `rclone mkdir` if recreating an empty folder) or `rclone deletefile` for bulk directory/file deletion, and use `ls -1` instead of `du -sh` for fast directory inspection.
- **Inline script validation**: Validate or rewrite narration lists inside `execute_code` rather than inline `python -c` shell strings — apostrophes in spoken English narrations break shell quoting and trigger terminal approval prompts.
- **Progress reporting cadence**: During long-running multi-video or multi-wave production runs, send concise Korean progress updates every 10 minutes (via a `10m` cronjob delivering to `origin`, auto-removed on batch completion) covering seeded blueprint count, current wave/clip status, and completed MP4 count.
- **Partial clip salvage & targeted regeneration**: When salvaging previously generated topics or recovering from partial/cached runs, inspect `~/.cache/rclone/vfs/gdrive/Kyubin_Yun_Workspace/07_Youtube/BCI_Shorts_Channel/projects/<project_id>/` alongside the live FUSE mount (`~/gdrive/...`). Filter clips against strict per-clip QA criteria (`shot_overlap >= 0.75`, `is_end_truncated == False`, `last_two_ok == True`, and `85 <= f0_median_hz <= 165`), copy only the passing `clip_k.mp4` files (plus `01_ideation`, `02_script/script.json`, `03_visuals/visual_plan.json`, and `03_visuals/flow_all_in_one_prompts.json`) into the active project directory on the mount, delete failing `clip_k.mp4` files and any stale `03_visuals/flow_provenance_receipt.json`, and let the Flow harvester/worker regenerate only the missing clip indices (`1..N`).
- **Completed MP4 location & Discord preview attachments**: After assembly and QA pass, `flow_live_single_worker.py` moves `05_assembly/final_shorts_1080x1920.mp4` out of the project directory into `Completed_Psychology_100_Shorts/final_shorts_<project_id>.mp4` (R25 single-MP4 delivery). Check `Completed_Psychology_100_Shorts/` rather than `projects/*/05_assembly/` when verifying completed outputs. Because master MP4s (~90–100 MB) exceed Discord attachment limits and FUSE random-access reads stall ffmpeg, copy the master to `/home/canadaofbin/.hermes/cache/scratch/` first and transcode a `<10 MB` preview using `/home/canadaofbin/hermes-venv/lib/python3.12/site-packages/imageio_ffmpeg/binaries/ffmpeg-linux-x86_64-v7.0.2 -y -i <local_in.mp4> -vf scale=720:1280 -c:v libx264 -preset ultrafast -b:v 780k -maxrate 900k -bufsize 1800k -c:a aac -b:a 96k -movflags +faststart <out_discord.mp4>` before emitting `MEDIA:<out_discord.mp4>`.
- **FUSE directory creation before Flow screenshots/downloads**: Ensure `03_visuals/flow_screenshots`, `03_visuals/flow_downloads`, and `03_visuals/flow_native_clips` call `mkdir(parents=True, exist_ok=True)` immediately before every screenshot write or download loop iteration — Google Drive FUSE directory cache eviction or external cleanup during long renders otherwise raises `FileNotFoundError` after clips finish rendering.

## Recovery
`PipelineOrchestrator.resume_project(project_id)` restarts from the last completed stage (R29).
