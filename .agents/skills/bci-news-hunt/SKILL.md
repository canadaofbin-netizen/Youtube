---
name: bci-news-hunt
description: Researches clinical, historical and BCI neuroscience cases with verified peer-reviewed DOIs for ALL ABOUT BRAIN Shorts - one case per topic, its real cast, the sensory organ to brain region signal path, damaged / target / compensatory regions, and a draft visual_plan for bci-script-gen.
---

# BCI & Neuroscience Case Hunter (`TopicResearcher`)

Master: [AGENTS.md](file:///g:/My%20Drive/Kyubin_Yun_Workspace/07_Youtube/.agents/AGENTS.md) · Rules: [content_quality_rules.md](file:///g:/My%20Drive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/content_quality_rules.md) (R1, R3) · [pillars_domain_rules.md](file:///g:/My%20Drive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/pillars_domain_rules.md) (P1, R20) · [visual_prompt_spec.md](file:///g:/My%20Drive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/visual_prompt_spec.md) (R40-C) · Code: [`pipeline/researcher.py`](file:///g:/My%20Drive/Kyubin_Yun_Workspace/07_Youtube/pipeline/researcher.py)

---

## Procedure
| Step | Action | Rule |
|---|---|---|
| 1 | Pick the pillar (P1) and query; check `BCI_Shorts_Channel/database/` and the weekly batch for duplicate topics / DOIs. | P1, R20 |
| 2 | Find **one** case in a peer-reviewed paper; open the DOI (`https://doi.org/<doi>`) and confirm authors, year, journal, subject and the key measurement. Use `search_web` for anything unknown — never guess. | R1 |
| 3 | Fill `research_card.json` (fields below). | R1, R3 |
| 4 | Draft `visual_plan` from the paper (`researcher.infer_visual_plan` gives a template draft): real environment of the case, cast as mannequins, regions, `signal_path`. | R40-C |
| 5 | Hand off to [bci-script-gen](file:///g:/My%20Drive/Kyubin_Yun_Workspace/07_Youtube/.agents/skills/bci-script-gen/SKILL.md). | — |

## `research_card.json` Fields
| Field | Content |
|---|---|
| `story_context.era_year` / `location` / `protagonist` | exact year, institution, named (or anonymised, e.g. "patient DS") subject — from the same paper |
| `story_context.inciting_incident` | concrete event that started the case |
| `sensory_organ_link` | organ → nerve route (e.g. retina → optic nerve) |
| `brain_regions` | anatomical names: target, damaged, compensatory |
| `doi`, `source_url` | verified citation |
| `core_facts`, `verified_claims[]` | claims the narration may use, each with source |
| `visual_plan` (optional) | draft per R40-C |
| `weighted_score` | ranking score computed by `TopicResearcher` |

## Commands
```bash
python -X utf8 main.py research --query "Capgras delusion" --style case_file --count 3
python -X utf8 main.py research --pillar brain_history --query "Phineas Gage" --save-project <project_id>
python -X utf8 main.py research --query "phantom limb" --offline
```
`--save-project <project_id>` writes `01_ideation/research_card.json` into that project.
