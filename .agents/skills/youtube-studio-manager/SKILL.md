---
name: youtube-studio-manager
description: Autonomous YouTube Studio operations for ALL ABOUT BRAIN via the visible Naver Whale window (CDP) - KR residence with en-US metadata, North American 5-slot timetable with the 3-notification cap, unlisted staging buffer, zero-duplicate queue, 72h sequential thumbnail Z-test, pinned DOI comment, AI disclosure, and the daily analytics report.
---

# YouTube Studio Manager

Master: [AGENTS.md](file:///g:/My%20Drive/Kyubin_Yun_Workspace/07_Youtube/.agents/AGENTS.md) · Rule: [youtube_studio_operations.md](file:///g:/My%20Drive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/youtube_studio_operations.md) (R4, R30–R36) · Metadata: [channel_operations_rules.md](file:///g:/My%20Drive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/channel_operations_rules.md) (R8–R10) · Code: `pipeline/studio/`

---

## Procedure
| Step | Action | Code | Rule |
|---|---|---|---|
| 1 | Verify channel residence + upload defaults (once per session). | `StudioUploader.configure_studio_localization` | R36 |
| 2 | Upload `05_assembly/final_shorts_1080x1920.mp4` as unlisted with `06_publish/metadata.json`; set AI disclosure. | `StudioUploader` | R33, R4, R8–R10 |
| 3 | Queue into the pillar slot; enforce seed-protection spacing and notification cap. | `StagingQueueManager` | R30, R30-B, R34 |
| 4 | Pin the DOI + debate-question comment. | `CommunityManager` | R35 |
| 5 | Rotate thumbnails A → B → C and evaluate the Z-test. | `ThumbnailABTester` | R31, R32 |
| 6 | Daily report. | [`/report_youtube`](file:///g:/My%20Drive/Kyubin_Yun_Workspace/07_Youtube/.agents/skills/report_youtube/SKILL.md) | — |

Use `--dry-run` first on any new command sequence.

## Commands
```bash
python -X utf8 main.py studio-settings
python -X utf8 main.py studio-upload --project <project_id> --visibility unlisted --burn-first-frame
python -X utf8 main.py studio-queue --action plan --days 7
python -X utf8 main.py studio-pin --project <project_id>
python -X utf8 main.py studio-ab-test --project <project_id> --swap-next
python -X utf8 main.py studio-ab-test --project <project_id> --evaluate
python -X utf8 main.py studio-report
```
