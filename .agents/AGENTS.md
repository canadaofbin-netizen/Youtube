# ALL ABOUT BRAIN — AI Master Spec (`AGENTS.md`)

Channel: `@AllAboutBrainOfficial` (`UC4FeioYYv9X04Di07_MfZ7g`) | Root: `/home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube`
Py: `/home/canadaofbin/hermes-venv/bin/python -X utf8` | Numbers SSOT: [production_constants.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/production_constants.md) (`pipeline/config.py`)

## 1. Core Operating Locks
- **Format & Pacing**: Shorts-first (`1080x1920 @ 24fps`, target `~90s` / `1m30s` high-retention Shorts; hard ceiling `<= SHORTS_HARD_CEILING_SEC`). Hold `16:9` Longform until Shorts scale.
- **Active Profile**: `DEFAULT_PRODUCTION_PROFILE="neuro_diorama"`, `DEFAULT_DIORAMA_STYLE_PROFILE="porcelain_cinematic_v7"` (R66 smooth featureless matte-white oval-head porcelain cast + Contained Living 4-Color 3D Brain; Track A R67 archival reenactment / Track B R66-Anchor). Voice: `emma_v7` (`en-US-EmmaMultilingualNeural`) + `dynamic_us_v7` native per-gear US speech (`kokoro-onnx` `af_bella` fallback; legacy `andrew_v7` `en-US-AndrewMultilingualNeural` preserved on Public `diorama_01..07`).
- **Monthly Credit Dual-Tier Flow (R5)**: `--engine auto` uses `Omni 1.1 Flash` while monthly AI credits > 0, seamlessly falling back to `0-credit` `Veo 3.1 - Lite [Lower Priority]` + `0-credit` `FLOW_ZERO_CREDIT_IMAGE_MODEL` (`x4` batch) when credits hit 0. Zero paid APIs; never click `Add AI credits`.
- **Google Flow Workspace & Multi-Agent Tab Isolation**:
  - Canonical Flow room naming: `AAB_<project_id>` (1 room per episode; delete temporary/orphan Flow projects after harvest).
  - Per-worker CDP `targetId` lock (port `9222`): open dedicated `about:blank` -> Flow URL tabs, bind `targetId` per worker, never navigate/steal/close tabs owned by sibling agents or the user, and close only self-opened tabs on exit.
- **FUSE Storage**: `/home/canadaofbin/gdrive` is `fuse.rclone` (no POSIX symlinks inside gdrive; use `rclone delete`/`rclone purge --fast-list` for bulk media deletion; `.rgignore` keeps `rg` `<1s`).
- **Artifact Auto-Archive**: All `<appDataDir>/brain/<conv_id>/` reports & media across all YouTube chatrooms auto-mirror into `artifacts_archive/` (`01_YouTube_CEO`..`05_Channel_Art` + `INDEX.md`, relative media links) via `.agents/hooks.json` + `~/.gemini/config/hooks.json` (`PostToolUse` + `Stop`) & `scripts/sync_artifacts_archive.py --sync-all`.

## 2. Cross-Chatroom `@mention` Dispatch ([chatrooms.json](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/chatrooms.json))
Resolve any `@<chatroom>` (EN/KO aliases + live DB auto-sync):
`python -X utf8 scripts/chatroom_mention.py resolve "<user_prompt>"` -> `send_message(Recipient="<conversation_id>", Message="<task_message>")`

| Handle | `conversation_id` | Scope |
|---|---|---|
| `@YouTube_CEO` (`@ceo`, `@총괄`) | `b57c97a8-6324-4c31-a2bb-16b25e28dd55` | Executive strategy, bottleneck architecture, cross-chatroom dispatch |
| `@Research` (`@리서치`, `@벤치마크`) | `ffbdfca1-9c07-48b3-9b1e-3e3045d67c0c` | Competitor Shorts teardown, retention/hook formula extraction, topic research |
| `@Daily_Report` (`@일일리포트`, `@보고서`) | `e3210c73-cc41-4432-87b1-c158efe9cadb` | Daily Studio traffic-light KPI funnel report & PNG charts |
| `@Headquarters` (`@hq`, `@본부`) | `8c7f8d97-664d-4d6b-9ef8-b17e721354f9` | Pipeline engineering, episode production, QA gates, Studio operations |
| `@Channel_Art` (`@채널아트`, `@브랜딩`) | `3c2fa53b-b43c-4f67-9dfd-0e5c86581f67` | Channel avatar, banner, visual branding prompts |

## 3. Unified Skills (`youtube-*`) & 5-Gear Map
| Gear | Skill | Stage Dirs | Key Code | Core Gates |
|---|---|---|---|---|
| 1 Research | [youtube-research](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/skills/youtube-research/SKILL.md) | `research_dossiers/<slug>/` | `research_dossier.py`, `researcher.py` | R1, P1, R44, R44-M (`dossier validate --require-v2`) |
| 2 Script+Plan | [youtube-script](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/skills/youtube-script/SKILL.md) | `02_script`, `03_visuals` | `flow_prompt_builder.py`, `porcelain_anchor_pack.py` | R57-H2, R60, R61, R65, R66 (`prompt-gate`) |
| 3 Flow Gen | [youtube-produce](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/skills/youtube-produce/SKILL.md) | `03_visuals` | `flow_browser.py`, `reference_image_qa.py` | R5, R18-B, R37, R51, R67 (`porcelain-refs` Q1-Q10) |
| 4 Assembly+QA | [youtube-produce](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/skills/youtube-produce/SKILL.md) | `04_audio`, `05_assembly`, `knowledge_base/` | `diorama_assembler.py`, `posthoc_semantic_qa.py`, `thumbnail_studio.py` | R58, R59, R62 (DQ1-12), R63-P (P1-10), R64, R65 (TQ1-7) |
| 5 Studio+Report | [youtube-studio](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/skills/youtube-studio/SKILL.md), [youtube-report](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/skills/youtube-report/SKILL.md) | `06_publish`, `reports/daily/` | `publish.py`, `pipeline/studio/` | R4, R8-R10, R30-R36-B |

## 4. CLI Quick Reference (`main.py <cmd>`)
- **Dossier / Reenact**: `news-radar` | `dossier init|validate|seed|doi|yt-search|yt-analyze|audit-media` | `reenact-extract` | `reenact-refs` | `reenact-produce` | `reenact-qa`
- **Prompts / Refs**: `prompt-gate --dir <d>` | `porcelain-refs --project <id>` | `ref-qa --project <id>` | `packets --project <id>`
- **Produce / Assemble**: `diorama-episode --slug <s> --project <id> --pillar <p> [--precheck-only] [--engine auto|omni|zero-credit]` | `diorama-flow` | `diorama-assemble` | `diorama-batch`
- **QA / KB**: `verify` | `autopsy` | `episode-qa` | `posthoc-qa` | `prosody-qa` | `thumbnail` | `voice-check` | `asset-manifest` | `kb sync|stats|search` | `pytest -v`
- **Studio**: `studio-settings` | `studio-upload` | `studio-queue` | `studio-link` | `studio-pin` | `studio-watchdog` | `studio-ab-test` | `studio-report`

## 5. Rule Registry (`.agents/rules/*.md`)
| ID | Owner Doc | Rule |
|---|---|---|
| R1-R3, R15, R24, R26, R42, R49-T | `content_quality_rules.md` | Verified single-case DOI, word budget, signal spine, plain TTS-safe US English |
| P1, R20 | `pillars_domain_rules.md` | 7 pillars & 5 everyday domains diversity |
| R4, R30-R36-B | `youtube_studio_operations.md` | AI disclosure, `<10K` Prime Slots (`12:00`/`20:00 ET`), Unlisted buffer, R35 DOI pin, R35-B `Related video` ring, R36 `en-US` lock, tab hygiene |
| R5, R14-A/B, R38, R40-A/B/C, R46, R48, R54 | `visual_prompt_spec.md` | Dual-Tier Flow (`Omni 1.1 Flash` -> `0-credit` `Veo 3.1 - Lite`), banned tokens, anatomy & prop contracts |
| R8-R12, R19, R28-R29 | `channel_operations_rules.md` | Title/desc/tags, lossless `01..06` project layout, no-loop conclusion, resume safety |
| R13, R16-R17, R39, R41, R43-A/B, R49 | `audio_assembly_rules.md` | Voice lock, ASS subtitles, soundscape, vocal chain, Kokoro fallback |
| R14-D, R55 | `camera_choreography_rules.md` | One camera move per clip, cranium transitions |
| R18, R18-B, R18-V5, R25, R37 | `qa_gates_rules.md` | Master QA G1-G12, browser V1-V5, single MP4 delivery, 5-tab concurrency lock |
| R21, R53 | `brain_depiction_rules.md` | 4-color subsurface anatomy code |
| R44, R44-D, R44-M, R50, R50-B | `research_dossier_rules.md` | `Schema v2` 3-Layer dossier, 4-Gate archival classifier, asset manifest & `knowledge_base/` |
| R45 | `cast_depiction_rules.md` | Clothed matte-white porcelain figures |
| R47 | `scene_depiction_rules.md` | 2-Beat physical prop action chain |
| R51, R52 | `reference_depiction_rules.md` | `9:16` reference pack Q1-Q11 & generation packets |
| R56 | `neuro_diorama_rules.md` | Zero-flesh porcelain/ceramic staging, `<=20%` cutaway, zero in-scene AI text |
| R57, R57-H2 | `neuro_diorama_rules.md` | 6-Act US English spine, 3-sentence cold-open (S1 `!` -> S2 `Yet/But` -> S3 stamp), midpoint `?`, `[Number]->[Analogy]`, 3-Stage Debate Ignition |
| R58 | `neuro_diorama_rules.md` | Audio-first master clock & 1:1 Zero-Reuse dynamic EDL |
| R59 | `neuro_diorama_rules.md` | Documentary stereo score (`DIORAMA_V7_BGM_DUCK_DB`), frame-grid ASS + chapter headlines |
| R60 | `neuro_diorama_rules.md` | 5-Archetype US title (`<= TITLE_MAX_CHARS_DIORAMA`) |
| R61 | `neuro_diorama_rules.md` | Pre-Flow & autopsy production gate |
| R62 | `neuro_diorama_rules.md` | Dynamic episode contract (`DQ1-DQ12`) |
| R63, R63-P | `neuro_diorama_rules.md` | Schema v7 architecture & native per-gear sentence prosody (`P1-P10`, zero WSOLA) |
| R64 | `neuro_diorama_rules.md` | Post-hoc 100%-cut expressive clarity QA (`posthoc-qa`) |
| R65 | `neuro_diorama_rules.md` | Thumbnail Studio (`TQ1-TQ7`) + `cover_frame_sec` |
| R66 | `neuro_diorama_rules.md` | `porcelain_cinematic_v7` world, featureless oval-head cast & Contained Living 4-Color Brain |
| R67 | `neuro_diorama_rules.md` | Source-conditioned 1:1 porcelain reenactment (`RQ1-RQ5`, zero source pixel reuse) |
