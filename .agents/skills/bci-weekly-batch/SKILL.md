---
name: bci-weekly-batch
description: Plans and produces a 7-day ALL ABOUT BRAIN batch covering all 7 content pillars with zero duplicate topics or DOIs, hand-authored narrations and visual_plan per topic, Google Flow generation in capped parallel chunks of dedicated Naver Whale tabs, assembly and QA for every project.
---

# BCI Weekly Batch Producer

Master: [AGENTS.md](file:///g:/My%20Drive/Kyubin_Yun_Workspace/07_Youtube/.agents/AGENTS.md) · Rules: [pillars_domain_rules.md](file:///g:/My%20Drive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/pillars_domain_rules.md) (P1, R20) · [qa_gates_rules.md](file:///g:/My%20Drive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/qa_gates_rules.md) (R18, R37) · [youtube_studio_operations.md](file:///g:/My%20Drive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/youtube_studio_operations.md) (R30, R33)

---

## Procedure
| Step | Action | Rule |
|---|---|---|
| 1 | Pick one topic per pillar (7 total); reject duplicate topics / DOIs against `BCI_Shorts_Channel/database/` and existing projects. | P1, R20 |
| 2 | Per topic: [bci-news-hunt](file:///g:/My%20Drive/Kyubin_Yun_Workspace/07_Youtube/.agents/skills/bci-news-hunt/SKILL.md) → [bci-script-gen](file:///g:/My%20Drive/Kyubin_Yun_Workspace/07_Youtube/.agents/skills/bci-script-gen/SKILL.md) (validators must return `[]`). | R1, R2, R40-A |
| 3 | Generate in chunks of ≤ `FLOW_MAX_PARALLEL_BATCH_SIZE` projects: 1 topic = 1 subagent = 1 Whale tab. | R37 Guard 6 |
| 4 | Per project: [bci-video-assembly](file:///g:/My%20Drive/Kyubin_Yun_Workspace/07_Youtube/.agents/skills/bci-video-assembly/SKILL.md). | R25 |
| 5 | Batch QA: unique provenance and dHash across the batch, all G1–G12 / V1–V5 pass. | R18, R37 |
| 6 | Stage uploads as unlisted and queue into pillar slots via [youtube-studio-manager](file:///g:/My%20Drive/Kyubin_Yun_Workspace/07_Youtube/.agents/skills/youtube-studio-manager/SKILL.md). | R30, R33, R34 |

## Commands
```bash
python -X utf8 main.py batch --count 7 --style auto
python -X utf8 main.py flow-parallel --projects <p1>,<p2>,<p3>,<p4>,<p5> --trigger
python -X utf8 main.py qa
python -X utf8 main.py studio-queue --action plan --days 7
```
