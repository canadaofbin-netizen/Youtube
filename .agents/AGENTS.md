# ALL ABOUT BRAIN — Workspace Master Specification (AGENTS.md)

Autonomous production and YouTube Studio operations for **ALL ABOUT BRAIN** (`@AllAboutBrainOfficial`, channel ID `UC4FeioYYv9X04Di07_MfZ7g`): English neuroscience / BCI documentary Shorts generated in Google Flow (Gemini Omni 1.1) through the visible Naver Whale browser, with zero paid APIs.

This file is the index only: identity, pipeline overview, CLI, Rule ID registry, customization index. **Every number lives in [production_constants.md](file:///g:/My%20Drive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/production_constants.md)** (mirrors `pipeline/config.py`); every rule has exactly one owner document.

---

## 1. 5-Gear Pipeline

| Gear | Stage dirs | Main code | Output | Owner rules |
|---|---|---|---|---|
| 1 Research | `01_ideation` | `pipeline/researcher.py` (`TopicResearcher`, `infer_visual_plan`) | `research_card.json` (one case, verified DOI, draft `visual_plan`) | R1, P1 |
| 2 Script + Prompts | `02_script`, `03_visuals` | `pipeline/scripting.py`, `pipeline/flow_prompt_builder.py` | `script.json` (`clip_narrations`), `visual_plan.json`, `flow_all_in_one_prompts.json`, `qa_report.json` | R2, R42, R26, R24, R40-A/B/C, R18 |
| 3 Flow Generation | `03_visuals` | `pipeline/flow_browser.py`, `pipeline/flow_live_single_worker.py` | `flow_native_clips/clip_1..clip_N.mp4`, provenance receipt, V1–V5 screenshots | R5, R14-A, R14-D, R18-B, R37, R39 |
| 4 Assembly | `04_audio`, `05_assembly` | `produce_psychology_batch.py`, `pipeline/video_autopsy.py` | `audio_master.wav`, `subtitles.ass`, `final_shorts_1080x1920.mp4`, autopsy + QA reports | R13, R16, R17, R41, R43-A/B, R25 |
| 5 Publish + Studio | `06_publish` | `pipeline/publish.py`, `pipeline/studio/` | metadata, thumbnails A/B/C, upload / community receipts, daily report | R8–R10, R4, R30–R36 |

**Topic → prompt database:** `pipeline/prompts_db.py` pre-renders every catalog topic through `flow_prompt_builder` into `BCI_Shorts_Channel/database/` (records: `visual_plan`, `clip_narrations_5` / `clip_narrations_10`, `flow_5clip_prompts` / `flow_10clip_prompts`; QA counts from `validate_flow_prompts` / `validate_narrations`). Records are drafts — upgrade them with a hand-authored `visual_plan` via [bci-script-gen](file:///g:/My%20Drive/Kyubin_Yun_Workspace/07_Youtube/.agents/skills/bci-script-gen/SKILL.md) before generation.

**Canonical prompt example:** [capgras_delusion_10clip_prompts.md](file:///C:/Users/yunky/.gemini/antigravity/brain/a935bacf-5ae3-4e1a-b5e2-7ed23172c727/capgras_delusion_10clip_prompts.md); in-repo golden = Capgras topic `visual_plan` in `pipeline/topics_catalog.py`.

---

## 2. CLI Reference (`python -X utf8 main.py <command>`)

| Command | Purpose |
|---|---|
| `research --query "<topic>" [--pillar <id>] [--style <archetype>] [--count <n>] [--save-project <project_id>] [--offline]` | Gear 1 research cards |
| `produce --pillar <id> --topic "<topic>" [--style <archetype>] [--project <project_id>]` | Gears 1–2 from templates |
| `batch --count <n> [--style <archetype>]` | weekly multi-pillar batch |
| `flow-parallel --projects <p1,p2,…> [--max-batch <n>] [--trigger]` | Gear 3, one Whale tab per project (cap `FLOW_MAX_PARALLEL_BATCH_SIZE`) |
| `import-clips --project <project_id> --dir "<download_dir>" [--auto-assemble]` | Gear 4 ingest, ASR ordering, assembly |
| `verify --project <project_id>` | lossless artifact integrity |
| `autopsy [--project <project_id>]` | forensic video / audio / subtitle check |
| `evolve [--project <project_id>]` | rebuild audio, subtitles, video, thumbnails |
| `qa [--project <project_id>]` | 4-stage executable QA suite |
| `info` / `list` / `test-all` | channel profile, pillars, test sweep |
| `studio-settings` / `studio-upload` / `studio-queue` / `studio-pin` / `studio-ab-test` / `studio-report` | Gear 5 Studio operations |

Tests: `python -m pytest -v`.

---

## 3. Rule ID Registry

| ID | Owner | Summary |
|---|---|---|
| R1 | content_quality_rules | Verified DOI; one case, one cast, no blending |
| R2 | content_quality_rules | Word budget and clip count by constant names |
| R2-B | content_quality_rules | Narrative archetypes (`--style`) |
| R3 | content_quality_rules | Narration follows the sensory-to-brain signal path |
| R4 | youtube_studio_operations | AI disclosure on every upload |
| R5 | visual_prompt_spec | Google Flow Omni 1.1 only, visible Whale, no paid APIs |
| R8 | channel_operations_rules | Title formula |
| R9 | channel_operations_rules | Description |
| R10 | channel_operations_rules | Hashtags |
| R11–R12 | channel_operations_rules | Lossless project layout |
| R13 | audio_assembly_rules | Puck-only voice lock |
| R14-A | visual_prompt_spec | Mannequin cast; real environment vs brain void by role; acting; lighting; scale anchor |
| R14-B | visual_prompt_spec | Banned prompt tokens |
| R14-D | camera_choreography_rules | Per-role camera vocabulary, one move per clip |
| R15 | content_quality_rules | Tone and readability |
| R16 | audio_assembly_rules | Single-line gold-keyword subtitles |
| R17 | audio_assembly_rules | 4-layer soundscape |
| R18 | qa_gates_rules | Master QA gates G1–G12 |
| R18-B | qa_gates_rules | Visual browser gates V1–V5 |
| R19 | channel_operations_rules | Independent conclusion ending (no loop) |
| R20 | pillars_domain_rules | Weekly batch diversity |
| R21 | visual_prompt_spec | 4-point colour code |
| R24 | content_quality_rules | Dual signature memes and placement |
| R25 | qa_gates_rules | Single MP4 delivery |
| R26 | content_quality_rules | Role openers (pivot, mechanism, conclusion) |
| R28 | channel_operations_rules | Test hygiene |
| R29 | channel_operations_rules | Defensive manifest and resume |
| R30 / R30-B | youtube_studio_operations | 5-slot timetable, notification cap / seed protection |
| R31 | youtube_studio_operations | Three thumbnail variants |
| R32 | youtube_studio_operations | Sequential A/B/C Z-test |
| R33 | youtube_studio_operations | Unlisted staging buffer |
| R34 | youtube_studio_operations | Zero-duplicate queue |
| R35 | youtube_studio_operations | Pinned DOI comment |
| R36 | youtube_studio_operations | Localization lock (KR residence, en-US metadata) |
| R37 | qa_gates_rules | 6-guard quality lock incl. subagent / tab cap |
| R38 | visual_prompt_spec | Realistic anatomy; banned metaphor props; real BCI hardware allowed |
| R39 | audio_assembly_rules | Native Flow colour and speech; ASR clip ordering |
| R40-A | visual_prompt_spec | Prompt template |
| R40-B | visual_prompt_spec | Sanitizer constraints |
| R40-C | visual_prompt_spec | `visual_plan` schema |
| R41 | audio_assembly_rules | Vocal window detection and vocal chain |
| R42 | content_quality_rules | Deep-Mechanism Role Spine |
| R43-A | audio_assembly_rules | Synchronized A/V speed-up, no punch-in |
| R43-B | audio_assembly_rules | Trim, holds, final tail and end fade |
| P1 | pillars_domain_rules | 7 content pillars |

**Retired / merged IDs:** R6, R14-E, R23-B, R23-C, R23-E (never specified) · R7 → R2 · R14-C HUD → removed · R22 Möbius loop → removed (R19) · R23-A → R43-B · R23-D → R43-A · R27 → R17 / G12 · R30-Pillars → P1 · R36 subagent cap → R37 · R40 HUD part → removed · R43 punch-in → removed · R43 title formula → R8 · "SIMUL-ARC" → R42.

---

## Agent Customizations Index

### Rules (`rules/`)
- [Rule: Production Constants](file:///g:/My%20Drive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/production_constants.md) — Only place for numbers; 1:1 with `pipeline/config.py` (Production Contract v4 block + assembly / media / subtitle constants).
- [Rule: Visual Prompt Specification](file:///g:/My%20Drive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/visual_prompt_spec.md) — R5, R14-A, R14-B, R21, R38, R40-A/B/C: mannequins in real environments vs brain void, realistic anatomy, colour code, camera grammar, prompt template, sanitizer, `visual_plan` schema, Capgras golden, `flow_prompt_builder`.
- [Rule: Camera Choreography Protocol](file:///g:/My%20Drive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/camera_choreography_rules.md) — R14-D per-role camera vocabulary, one move per clip.
- [Rule: Content Quality & Narrative Architecture Protocol](file:///g:/My%20Drive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/content_quality_rules.md) — R1, R2, R2-B, R3, R15, R24, R26, R42: single-case DOI accuracy, word budget, Deep-Mechanism Role Spine, openers, memes, readability.
- [Rule: Audio & Assembly Protocol](file:///g:/My%20Drive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/audio_assembly_rules.md) — R13, R16, R17, R39, R41, R43-A/B: Puck voice, vocal window and chain, speed-up, holds and end fade, subtitles, 4-layer soundscape.
- [Rule: Master QA Loop & Video Validation Protocol](file:///g:/My%20Drive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/qa_gates_rules.md) — R18 G1–G12, R18-B V1–V5, R25 delivery, R37 6-guard lock, executable QA suite.
- [Rule: 7 Content Pillars & Domain Isolation Protocol](file:///g:/My%20Drive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/pillars_domain_rules.md) — P1 pillars, signal-path seeds, R20 weekly diversity.
- [Rule: Channel Operations & Workspace Hygiene Protocol](file:///g:/My%20Drive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/channel_operations_rules.md) — R8–R12, R19, R28, R29: metadata, project layout, shared locations, independent ending, test hygiene, recovery.
- [Rule: YouTube Studio Shorts Operations Protocol](file:///g:/My%20Drive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/youtube_studio_operations.md) — R4, R30–R36: timetable, thumbnails, Z-test, staging, queue, pinned DOI, localization.

### Skills (`skills/`)
- [Skill: BCI Video Pipeline (Master Orchestrator)](file:///g:/My%20Drive/Kyubin_Yun_Workspace/07_Youtube/.agents/skills/bci-video-pipeline/SKILL.md) — Runs the 5-Gear pipeline end to end.
- [Skill: BCI News Hunter](file:///g:/My%20Drive/Kyubin_Yun_Workspace/07_Youtube/.agents/skills/bci-news-hunt/SKILL.md) — One verified case per topic, research card, draft `visual_plan`.
- [Skill: BCI Script Generator](file:///g:/My%20Drive/Kyubin_Yun_Workspace/07_Youtube/.agents/skills/bci-script-gen/SKILL.md) — Hand-authored `clip_narrations` + `visual_plan`, rendered and validated with `flow_prompt_builder`.
- [Skill: BCI Video Assembly & Audio Engineering](file:///g:/My%20Drive/Kyubin_Yun_Workspace/07_Youtube/.agents/skills/bci-video-assembly/SKILL.md) — ASR ordering, vocal windows, holds, subtitles, soundscape, mux, autopsy.
- [Skill: BCI Weekly Batch](file:///g:/My%20Drive/Kyubin_Yun_Workspace/07_Youtube/.agents/skills/bci-weekly-batch/SKILL.md) — 7-pillar weekly batch in capped parallel chunks.
- [Skill: YouTube Studio Manager](file:///g:/My%20Drive/Kyubin_Yun_Workspace/07_Youtube/.agents/skills/youtube-studio-manager/SKILL.md) — Upload, schedule, pin, A/B test, localization.
- [Skill: YouTube Daily Report (`/report_youtube`)](file:///g:/My%20Drive/Kyubin_Yun_Workspace/07_Youtube/.agents/skills/report_youtube/SKILL.md) — 9-section daily analytics report with duration-proportional retention quartiles, per-video 3-axis change attribution (6-2), 7-risk compliance audit (8-3), and success/failure signal radar & 5-Gear amplification playbook (9-1..9-3).
