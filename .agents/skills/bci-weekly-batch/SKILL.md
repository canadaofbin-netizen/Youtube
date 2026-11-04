---
name: bci-weekly-batch
description: Plans and produces a 7-day ALL ABOUT BRAIN batch covering all 7 content pillars with zero duplicate topics or DOIs, hand-authored narrations and visual_plan per topic, Google Flow generation in capped parallel chunks of dedicated Naver Whale tabs, assembly and QA for every project.
---

# BCI Weekly Batch Producer

Master: [AGENTS.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/AGENTS.md) · Rules: [pillars_domain_rules.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/pillars_domain_rules.md) (P1, R20) · [qa_gates_rules.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/qa_gates_rules.md) (R18, R37) · [youtube_studio_operations.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/youtube_studio_operations.md) (R30, R33)

---

## Procedure
| Step | Action | Rule |
|---|---|---|
| 1 | Pick 7 pillar-balanced episodes from `BCI_Shorts_Channel/porcelain_rebalanced_queue.json` (or author new dossiers via [bci-deep-research](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/skills/bci-deep-research/SKILL.md) + `main.py dossier audit-media --slug <slug> --write`); reject duplicate topics / DOIs against existing projects. | P1, R20, R34, R44-M |
| 2 | Per topic: verify `diorama_v7_porcelain` (`script.json`, `visual_plan.json`, `reference_image_specs.json`) passes `main.py prompt-gate` + `--precheck-only` TTS clock (`populate_porcelain_reference_contract` compiled). | R1, R57-H2, R66, R67 |
| 3 | Synthesize `0-credit` `9:16` reference pack (`ensure_porcelain_reference_pack` / `porcelain-refs` → `Q1–Q10` pass) and generate `46–48` 1:1 Zero-Reuse Flow clips in `<= FLOW_MAX_PARALLEL_BATCH_SIZE` tabs (`diorama-pipeline` overlaps Flow producer with CPU Assembly+QA consumer). | R5, R37 Guard 6, R51, R66 |
| 4 | Per project: automatic `diorama-assemble` + `prosody-qa` (`P1–P10`) + `episode-qa` (`DQ1–DQ12`) + `posthoc-qa` (`R64`) + `autopsy` + `thumbnail` (`TQ1–TQ7`) + `verify` + `kb sync` (+ `reenact-qa` `RQ1–RQ5` on Track A episodes). | R25, R50-B, R62–R67 |
| 5 | Stage uploads as unlisted and queue into North American 5-slot timetable via [youtube-studio-manager](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/skills/youtube-studio-manager/SKILL.md). | R30, R33, R34 |

## Standing Preferences
- **10-minute progress reports**: During multi-wave batch runs, schedule a recurring `10m` cronjob (`deliver="origin"`) that reports seeded count, active wave/Flow status, and completed MP4 count in Korean, and removes itself once the batch finishes.

## Commands
```bash
python -X utf8 main.py dossier audit-media --all-queued
python -X utf8 main.py diorama-pipeline --projects <slug1:p1:pil1>,...,<slug7:p7:pil7> --precheck-only
python -X utf8 main.py diorama-pipeline --projects <slug1:p1:pil1>,...,<slug7:p7:pil7> --tabs 5 --engine auto
python -X utf8 main.py studio-queue --action plan --days 7
```
