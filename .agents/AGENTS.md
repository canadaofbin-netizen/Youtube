# ALL ABOUT BRAIN — Workspace Master Specification (AGENTS.md)

Autonomous production and YouTube Studio operations for **ALL ABOUT BRAIN** (`@AllAboutBrainOfficial`, channel ID `UC4FeioYYv9X04Di07_MfZ7g`): English neuroscience / BCI documentary Shorts generated in Google Flow (Gemini Omni 1.1) through the visible Naver Whale browser, with zero paid APIs.

This file is the index only: identity, pipeline overview, CLI, Rule ID registry, customization index. **Every number lives in [production_constants.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/production_constants.md)** (mirrors `pipeline/config.py`); every rule has exactly one owner document.

---

## 1. 5-Gear Pipeline

| Gear | Stage dirs | Main code | Output | Owner rules |
|---|---|---|---|---|
| 1 Research | `01_ideation`, `research_dossiers/<slug>/` | `pipeline/researcher.py` (`TopicResearcher`), `pipeline/research_dossier.py` | shortlisted case + verified DOI → longform-depth **research dossier** (visual mode, iconic scene bible, media analysis, plain language, brain links, longform outline) | R1, P1, R44, R45 |
| 2 Script + Prompts | `02_script`, `03_visuals` | `pipeline/scripting.py`, `pipeline/flow_prompt_builder.py`, `pipeline/prompt_quality_v5.py`, `pipeline/reference_image_qa.py` | `script.json` (`clip_narrations`, TTS-safe), v5 `visual_plan.json`, `flow_all_in_one_prompts.json` (schema 5), `reference_image_specs.json`, `qa_report.json`, `prompt-gate` pass | R2, R42, R26, R24, R40-A/B/C, R45–R48, R15 v5, R18, R18-V5, R51 |
| 3 Flow Generation | `03_visuals` | `pipeline/flow_browser.py`, `pipeline/flow_live_single_worker.py`, `pipeline/reference_image_qa.py` | `reference_images/ref_*.png` + `reference_image_qa_report.json` (10-axis Q1–Q10 pass), `flow_native_clips/clip_1..clip_N.mp4` conditioned on approved reference images, provenance receipt, V1–V5 screenshots; voice outliers regenerated | R5, R14-A, R14-D, R18-B, R37, R39, R49, R51 |
| 4 Assembly | `04_audio`, `05_assembly` | `produce_psychology_batch.py`, `pipeline/voice_fallback.py`, `pipeline/video_autopsy.py`, `pipeline/asset_manifest.py` | `voice_report.json`, `audio_master.wav`, `subtitles.ass`, `final_shorts_1080x1920.mp4`, `asset_manifest.json`, autopsy + QA reports | R13, R16, R17, R41, R43-A/B, R25, R49, R50 |
| 5 Publish + Studio | `06_publish` | `pipeline/publish.py`, `pipeline/studio/` | metadata, thumbnails A/B/C, upload / community receipts, daily report | R8–R10, R4, R30–R36 |

**Topic → prompt database:** `pipeline/prompts_db.py` pre-renders every catalog topic through `flow_prompt_builder` into `BCI_Shorts_Channel/database/` (records: `visual_plan`, `clip_narrations_5` / `clip_narrations_10`, `flow_5clip_prompts` / `flow_10clip_prompts`; QA counts from `validate_flow_prompts` / `validate_narrations`). Records are drafts — upgrade them with a hand-authored `visual_plan` via [bci-script-gen](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/skills/bci-script-gen/SKILL.md) before generation.

**Canonical prompt example:** [capgras_delusion_10clip_prompts.md](file:///C:/Users/yunky/.gemini/antigravity/brain/a935bacf-5ae3-4e1a-b5e2-7ed23172c727/capgras_delusion_10clip_prompts.md); in-repo golden = Capgras topic `visual_plan` in `pipeline/topics_catalog.py`.

**Prompt System v5 (2026-10-24):** every new topic goes research dossier → visual mode (brain only when the topic needs it) → iconic must-have scene in clip 1–2 → Action-Physics acting → brain ↔ story link → plain-language, TTS-safe script → `prompt-gate`. Worked examples: `BCI_Shorts_Channel/research_dossiers/{phineas_gage_iron_rod, invisible_gorilla_attention, pavlov_dogs_conditioning, milgram_obedience_shock}/shorts_v5/`. Shorts are extracts of longform-depth dossiers; every clip is archived in the asset library for longform reuse.

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
| `studio-settings` / `studio-upload` / `studio-queue` / `studio-link` / `studio-pin` / `studio-ab-test` / `studio-report` | Gear 5 Studio operations (incl. R35-B `Related video` & 7-Pillar playlist ring) |
| `dossier init\|validate\|seed\|doi\|yt-search\|yt-analyze\|checklist --slug <slug> [...]` | Gear 1b research dossier (R44) |
| `prompt-gate --dir <project_or_draft_dir>` | v5 production gate before Gear 3 (R18-V5) |
| `audit-prompts` | back-catalogue score sheet → `BCI_Shorts_Channel/reports/prompt_v5_score_sheet.md` |
| `voice-check --project <project_id>` | semitone voice-consistency report (R49) |
| `asset-manifest --project <project_id>` | asset manifest + library index (R50) |
| `ref-qa --project <project_id> [--register <file> --source flow_image_generation\|gemini_image_generation] [--audit]` | reference image specs + Q1–Q11 QA; exits 0 only when `pre_generation_ready` (R51) |
| `packets --project <project_id> [--backend gemini_app\|flow] [--voice-source tts\|native] [--chain N]` | scene blueprint + per-clip generation packets; `--chain N` cuts clip N's last frame as clip N+1's start frame (R52) |

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
| R21 | brain_depiction_rules | 4-point subsurface colour code (`crimson-red`, `electric cyan-blue`, `warm amber-gold`, `bioluminescent green signal particles`) inside a bright white studio gallery 3D matte-white brain (`31_O2CmlKOk` Schema v4) |
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
| R35-B | youtube_studio_operations | Short-to-Short `Related video` circular seed-rescue ring & 7-Pillar playlist lock (`StudioShortLinker`) |
| R36 | youtube_studio_operations | Localization lock (KR residence, en-US metadata) |
| R36-B | youtube_studio_operations | Polymer web-component click (`DirectCDPClient.click`) & Studio tab memory hygiene |
| R37 | qa_gates_rules | 6-guard quality lock incl. subagent / tab cap |
| R38 | visual_prompt_spec | Realistic anatomy; banned metaphor props; real BCI hardware allowed |
| R39 | audio_assembly_rules | Native Flow colour and speech; ASR clip ordering |
| R40-A | visual_prompt_spec | Schema v4 50–80 word 3-sentence prompt template (`Voice: Consistent deep male baritone documentary narrator.`) |
| R40-B | visual_prompt_spec | Sanitizer & 2-Beat character motion validation (`validate_character_motion`) |
| R40-C | visual_prompt_spec | `visual_plan` schema |
| R41 | audio_assembly_rules | Vocal window detection and vocal chain |
| R42 | content_quality_rules | Deep-Mechanism Role Spine |
| R43-A | audio_assembly_rules | Synchronized A/V speed-up, no punch-in |
| R43-B | audio_assembly_rules | Trim, holds, final tail and end fade |
| R44 | research_dossier_rules | Longform-depth research dossier + checklist before Gear 2 |
| R45 | cast_depiction_rules | Clothed matte-white porcelain mannequins with translucent frosted-glass craniums in minimalist bright studio rooms (`31_O2CmlKOk` Schema v4) |
| R46 | visual_prompt_spec | Concrete interactive room props & role-matched wardrobe |
| R47 | scene_depiction_rules | 2-Beat physical action chain (`[Beat 1: active hand/arm/body prop verb] -> [Beat 2: immediate physical consequence/reaction]`) in Clips 1, 2, 3, 9, 10 |
| R48 | visual_prompt_spec | Brain ↔ story link, canonical anatomy (`anatomy_map`) |
| R15 v5 / R49-T | content_quality_rules | Quantified plain language; TTS-safe narration |
| R49 | audio_assembly_rules | Semitone voice gate, regeneration, local Kokoro TTS fallback |
| R50 | research_dossier_rules | Asset manifest, asset library, aspect-neutral prompts for longform |
| R51 / R52 | reference_depiction_rules | Default text-only Schema v4 generation; optional reference image conditioning (`ref-qa`, `packets`) |
| R46-K | scene_depiction_rules | Key physical prop interaction visible in Clip 1–2 |
| R44-D | research_dossier_rules | Research depth standard (sources, sourced facts, analysed footage, stageable iconic scene, `[fact]` number trace) |
| R53 | brain_depiction_rules | `31_O2CmlKOk` 3D brain gallery signal conduction (`bioluminescent green` particles along `signal_path`, `crimson-red` lesion, `electric cyan-blue` hub, `warm amber-gold` compensatory route) |
| R54 | visual_prompt_spec | Modular Depiction Rule Composition (`CastDepictionRule` + `SceneDepictionRule` + `BrainDepictionRule` + `CameraDepictionRule` + `ReferenceDepictionRule`) |
| R55 | brain_depiction_rules / camera_choreography_rules | Cranium dive in Clip 4 (`crisis`) → 3D brain in bright white studio gallery (`Clip 4–8`) → Cranium pull-out in Clip 9 (`breakthrough`) |
| R18-V5 | qa_gates_rules | `validate_production_v5` production gate |
| R14-D v5 | camera_choreography_rules | Reenactment camera vocabulary |
| P1 | pillars_domain_rules | 7 content pillars |

**Retired / merged IDs:** R6, R14-E, R23-B, R23-C, R23-E (never specified) · R7 → R2 · R14-C HUD → removed · R22 Möbius loop → removed (R19) · R23-A → R43-B · R23-D → R43-A · R27 → R17 / G12 · R30-Pillars → P1 · R36 subagent cap → R37 · R40 HUD part → removed · R43 punch-in → removed · R43 title formula → R8 · "SIMUL-ARC" → R42.

---

## Agent Customizations Index

### Rules (`rules/`)
- [Rule: Production Constants](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/production_constants.md) — Only place for numbers; 1:1 with `pipeline/config.py` (Production Contract v4 block + assembly / media / subtitle constants).
- [Rule: Visual Prompt Specification (Master Composer)](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/visual_prompt_spec.md) — R5, R14-B, R40-A/B/C, R54: modular composition of cast, scene, brain, camera, and reference depiction rules (`pipeline/depiction_rules.py` & `flow_prompt_builder.py`).
- [Rule: Cast & Mannequin Depiction Protocol](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/cast_depiction_rules.md) — R14-A (Cast), R45 (Cranium), R46 (Wardrobe & Animals): matte-white porcelain mannequins, mode-based cranium translucency, period wardrobe lock, porcelain animals.
- [Rule: Real-World Scene, Prop & Action Depiction Protocol](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/scene_depiction_rules.md) — R14-A (Env/Light/Scale), R46, R46-K, R47: high-key documentary environments, iconic scenes, money shots, Action-Physics 3-window acting.
- [Rule: Brain, Anatomy & Restrained Signal Depiction Protocol](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/brain_depiction_rules.md) — R21, R38, R48, R53: studio gallery matte-white 3D brain, canonical anatomy, 4-point subsurface colour code, restrained internal fiber pulse (zero flying particles or sparks).
- [Rule: Camera Choreography Protocol](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/camera_choreography_rules.md) — R14-D & R14-D v5 per-role camera vocabulary, one move per clip.
- [Rule: Reference Frame & Source-to-Prompt Depiction Protocol](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/reference_depiction_rules.md) — R51, R52: frozen reference frame hierarchy, 11-axis QA gate, blueprint-to-packet conditioning.
- [Rule: Content Quality & Narrative Architecture Protocol](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/content_quality_rules.md) — R1, R2, R2-B, R3, R15, R24, R26, R42: single-case DOI accuracy, word budget, Deep-Mechanism Role Spine, openers, memes, readability.
- [Rule: Audio & Assembly Protocol](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/audio_assembly_rules.md) — R13, R16, R17, R39, R41, R43-A/B: Puck voice, vocal window and chain, speed-up, holds and end fade, subtitles, 4-layer soundscape.
- [Rule: Master QA Loop & Video Validation Protocol](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/qa_gates_rules.md) — R18 G1–G12, R18-B V1–V5, R25 delivery, R37 6-guard lock, executable QA suite.
- [Rule: 7 Content Pillars & Domain Isolation Protocol](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/pillars_domain_rules.md) — P1 pillars, signal-path seeds, R20 weekly diversity.
- [Rule: Channel Operations & Workspace Hygiene Protocol](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/channel_operations_rules.md) — R8–R12, R19, R28, R29: metadata, project layout, shared locations, independent ending, test hygiene, recovery.
- [Rule: YouTube Studio Shorts Operations Protocol](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/youtube_studio_operations.md) — R4, R30–R36, R35-B, R36-B: timetable, thumbnails, Z-test, staging, queue, pinned DOI, Short-to-Short `Related video` & playlist ring, localization, Polymer click & tab hygiene.
- [Rule: Research Dossier & Longform Reuse Protocol](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/research_dossier_rules.md) — R44, R50: dossier files and research checklist, free reference-media tools, asset manifest and library, aspect-neutral prompts.

### Skills (`skills/`)
- [Skill: BCI Video Pipeline (Master Orchestrator)](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/skills/bci-video-pipeline/SKILL.md) — Runs the 5-Gear pipeline end to end.
- [Skill: BCI News Hunter](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/skills/bci-news-hunt/SKILL.md) — One verified case per topic (discovery, DOI, duplicate check); hands off to bci-deep-research.
- [Skill: BCI Deep Research](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/skills/bci-deep-research/SKILL.md) — Longform-depth research dossier: sources, iconic scene bible, YouTube/archive analysis, plain language, brain links, visual mode, longform outline.
- [Skill: BCI Script Generator](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/skills/bci-script-gen/SKILL.md) — Hand-authored `clip_narrations` + `visual_plan`, rendered and validated with `flow_prompt_builder`.
- [Skill: BCI Video Assembly & Audio Engineering](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/skills/bci-video-assembly/SKILL.md) — ASR ordering, vocal windows, holds, subtitles, soundscape, mux, autopsy.
- [Skill: BCI Weekly Batch](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/skills/bci-weekly-batch/SKILL.md) — 7-pillar weekly batch in capped parallel chunks.
- [Skill: YouTube Studio Manager](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/skills/youtube-studio-manager/SKILL.md) — Upload, schedule, `Related video` & 7-Pillar playlist linking, pin, A/B test, localization.
- [Skill: YouTube Daily Report (`/report_youtube`)](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/skills/report_youtube/SKILL.md) — 9-section daily analytics report with duration-proportional retention quartiles, per-video 3-axis change attribution (6-2), 7-risk compliance audit (8-3), and success/failure signal radar & 5-Gear amplification playbook (9-1..9-3).

---

## 4. Specialist Agent Architecture & Unified SSOT (`.agents/` ↔ Hermes)

`.agents/` in this workspace is the **Single Source of Truth (SSOT)** for both **Antigravity** and **Hermes**:
- **In Antigravity**: `AGENTS.md` + `.agents/rules/*.md` + `.agents/skills/*/SKILL.md` are loaded directly. You do **not** need separate `SOUL.md` files when working in Antigravity; all specialist scopes, commands, and verification gates are consolidated below.
- **In Hermes (`~/.hermes/profiles/yt-*`)**: Each profile's `SOUL.md` and `skills/youtube-pipeline/*` are symlinked directly to `.agents/profiles/yt-*/SOUL.md` and `.agents/skills/*`, preventing any drift between environments.

| Specialist / Gear | Scope & Hard Boundary | Required Verification & CLI | Primary Rules & Skills |
|---|---|---|---|
| **Gear 1–2 (`@yt-writer`)**<br>[SOUL.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/profiles/yt-writer/SOUL.md) | Topic research, single-case DOI verification, **research dossier** (`research_dossiers/<slug>/`, incl. `yt-dlp` reference analysis), `script.json` (plain-language & TTS-safe), v5 `visual_plan.json`, `flow_prompt_builder.py`, `flow_all_in_one_prompts.json`. Never opens the Flow browser or runs FFmpeg assembly. | `main.py dossier validate --slug <slug>` (`ready: true`) → `main.py prompt-gate --dir <dir>` (`passed: true`, `issues: []`, `cutoff_risk == False`) | [bci-news-hunt](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/skills/bci-news-hunt/SKILL.md), [bci-deep-research](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/skills/bci-deep-research/SKILL.md), [bci-script-gen](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/skills/bci-script-gen/SKILL.md), R1, R2, R14-A/B, R15 v5, R21, R26, R38, R40-A/B/C, R42, R44–R48, R18-V5 |
| **Gear 3 (`@yt-flow`)**<br>[SOUL.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/profiles/yt-flow/SOUL.md) | Exclusive owner of `.flow_download_harvest.lock` and Naver Whale (`--remote-debugging-port=9222`) Flow tabs. Dynamic `"8s"` / `"10s"` clip generation (auto-upgrading `8s -> 10s` on `is_end_truncated` retry), V1–V5 gates, R49 outlier clip regeneration. Never rewrites `script.json`. | `main.py flow-parallel --projects <id> --trigger` · all `clip_1..clip_N.mp4 > 100KB` · V1–V5 pass | [bci-video-pipeline](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/skills/bci-video-pipeline/SKILL.md), R5, R18-B, R37, R49 |
| **Gear 4 (`@yt-editor`)**<br>[SOUL.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/profiles/yt-editor/SOUL.md) | Clip ingest, ASR ordering (`faster-whisper` + phonetic normalization + leading `"Puck"` bleed auto-trim), R49 semitone F0 voice gate (`±1.5 st` median dev, `<= 2.0 st` jump, `<= 3.0 st` spread) with automatic local `kokoro-onnx` (`am_fenrir` + R41 broadcast EQ/compression) fallback (`04_audio/voice_report.json`), pitch-preserving `1.08x` (`atempo`, zero `asetrate`), frame-locked ASS subtitles (`to_display_text` full-sentence before chunking, zero overlap, `<= 0.15s` drift), 4-layer soundscape, R50 `asset_manifest.json`, `VideoAutopsyEngine` & `main.py qa`. | `main.py voice-check --project <id>` · `produce_psychology_batch.py` · `main.py asset-manifest --project <id>` · `main.py autopsy --project <id>` · `main.py qa --project <id>` | [bci-video-assembly](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/skills/bci-video-assembly/SKILL.md), R13, R16, R17, R39, R41, R43-A/B, R49, R50, R18, R25 |
| **Gear 5 (`@yt-studio`)**<br>[SOUL.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/profiles/yt-studio/SOUL.md) | Thumbnails A/B/C (top safe-zone `y=185..445` text + central HUD reticle), Unlisted staging (v5-gated), stage-gated prime-slot scheduling (`daily_prime_only=True` -> Slot 2 `12:00 ET` & Slot 4 `20:00 ET` under 10K subs), Short-to-Short `Related video` circular seed-rescue ring & 7-Pillar playlists, pinned DOI comment, Z-test, daily 07:00 AM analytics report (`/report_youtube`, cron `2e725d86049e`). | `main.py studio-upload` · `studio-queue` · `studio-link` · `studio-pin` · `studio-ab-test` · `studio-report` · verify `06_publish/studio_publish_receipt.json` | [youtube-studio-manager](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/skills/youtube-studio-manager/SKILL.md), [report_youtube](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/skills/report_youtube/SKILL.md), R4, R8–R10, R30–R36, R35-B, R36-B |

- **Python interpreter on Linux**: Always use `/home/canadaofbin/hermes-venv/bin/python -X utf8` (which has `cv2`, `faster_whisper`, `yt_dlp`, `kokoro_onnx`, `soundfile`, `websockets`, `matplotlib`, and `pytest` installed).
- **Google Drive FUSE (`gdrive`) hygiene**: `/home/canadaofbin/gdrive` is a `fuse.rclone` mount; avoid recursive `rm -rf` or `du -sh` across large project trees (use `rclone purge gdrive:Kyubin_Yun_Workspace/07_Youtube/<dir>` or `rclone deletefile` for bulk operations). Completed batch MP4 deliverables are stored at `Completed_Psychology_100_Shorts/final_shorts_<project_id>.mp4`.
