---
name: bci-video-pipeline
description: Master end-to-end orchestrator for ALL ABOUT BRAIN YouTube Shorts across the 5-Gear pipeline - case research with verified DOI, hand-authored clip narrations and visual_plan rendered by flow_prompt_builder, Google Flow Omni 1.1 generation in visible Naver Whale tabs, ASR-ordered assembly with Puck voice, subtitles and 4-layer soundscape, QA gates, and YouTube Studio staging.
---

# BCI Video Pipeline (Master Orchestrator)

Master: [AGENTS.md](file:///g:/My%20Drive/Kyubin_Yun_Workspace/07_Youtube/.agents/AGENTS.md) · Numbers: [production_constants.md](file:///g:/My%20Drive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/production_constants.md)

Run gears in order; each gear's outputs are the next gear's inputs. Stop on any failed gate.

| Gear | Stage dir | Skill / code | Output | Rules |
|---|---|---|---|---|
| 1 Research | `01_ideation` | [bci-news-hunt](file:///g:/My%20Drive/Kyubin_Yun_Workspace/07_Youtube/.agents/skills/bci-news-hunt/SKILL.md) · `TopicResearcher` | `research_card.json` (case, DOI, draft `visual_plan`) | R1, P1 |
| 2 Script + prompts | `02_script`, `03_visuals` | [bci-script-gen](file:///g:/My%20Drive/Kyubin_Yun_Workspace/07_Youtube/.agents/skills/bci-script-gen/SKILL.md) · `flow_prompt_builder` | `script.json` (`clip_narrations`), `visual_plan.json`, `flow_all_in_one_prompts.json`, `qa_report.json` | R2, R42, R26, R24, R40-A/C, R18 |
| 3 Flow generation | `03_visuals` | `flow-parallel` · `FlowProjectSubagentWorker` | `flow_native_clips/clip_1..clip_N.mp4`, `flow_provenance_receipt.json`, `flow_screenshots/` | R5, R18-B, R37, R39 |
| 4 Assembly | `04_audio`, `05_assembly` | [bci-video-assembly](file:///g:/My%20Drive/Kyubin_Yun_Workspace/07_Youtube/.agents/skills/bci-video-assembly/SKILL.md) | `audio_master.wav`, `subtitles.ass`, `final_shorts_1080x1920.mp4`, autopsy + QA reports | R13, R16, R17, R41, R43-A/B, R25 |
| 5 Publish + Studio | `06_publish` | `PublishStage` · [youtube-studio-manager](file:///g:/My%20Drive/Kyubin_Yun_Workspace/07_Youtube/.agents/skills/youtube-studio-manager/SKILL.md) | `metadata.json`, thumbnails A/B/C, upload / community receipts | R8–R10, R30–R36, R4 |

## Commands
```bash
python -X utf8 main.py research --query "Capgras delusion" --style case_file --save-project <project_id>
python -X utf8 main.py produce --pillar brain_mysteries --topic "Capgras Delusion" --style case_file --project <project_id>
python -X utf8 main.py flow-parallel --projects <p1>,<p2> --max-batch 5 --trigger
python -X utf8 main.py import-clips --project <project_id> --dir "<download_dir>" --auto-assemble
python -X utf8 main.py qa --project <project_id>
python -X utf8 main.py studio-upload --project <project_id> --visibility unlisted
```
`produce` runs Gears 1–2 automatically from templates; for publishable quality, replace the generated narrations / `visual_plan` with the hand-authored versions from bci-script-gen before Gear 3. `--max-batch` is capped by `FLOW_MAX_PARALLEL_BATCH_SIZE` (R37 Guard 6).

## Recovery
`PipelineOrchestrator.resume_project(project_id)` restarts from the last completed stage (R29).
