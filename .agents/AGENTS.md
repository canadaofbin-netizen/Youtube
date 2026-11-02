# ALL ABOUT BRAIN — Workspace Master Specification (AGENTS.md)

Autonomous production and YouTube Studio operations for **ALL ABOUT BRAIN** (`@AllAboutBrainOfficial`, channel ID `UC4FeioYYv9X04Di07_MfZ7g`): English neuroscience / BCI documentary Shorts generated in Google Flow (`Omni 1.1 Flash` primary when AI credits are available, seamlessly falling back to `0-credit` `Veo 3.1 - Lite [Lower Priority]`) through the visible Naver Whale browser, with zero paid APIs.

This file is the index only: identity, pipeline overview, CLI, Rule ID registry, customization index. **Every number lives in [production_constants.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/production_constants.md)** (mirrors `pipeline/config.py`); every rule has exactly one owner document.

---

## 1. 5-Gear Pipeline

| Gear | Stage dirs | Main code | Output | Owner rules |
|---|---|---|---|---|
| 1 Research | `01_ideation`, `research_dossiers/<slug>/` | `pipeline/researcher.py` (`TopicResearcher`), `pipeline/research_dossier.py` | shortlisted case + verified DOI → longform-depth **research dossier** (visual mode, iconic scene bible, media analysis, plain language, brain links, longform outline) | R1, P1, R44, R45 |
| 2 Script + Prompts | `02_script`, `03_visuals` | `pipeline/scripting.py`, `pipeline/flow_prompt_builder.py`, `pipeline/prompt_quality_v5.py`, `pipeline/reference_image_qa.py` | `script.json` (`clip_narrations`, TTS-safe), v5 `visual_plan.json`, `flow_all_in_one_prompts.json` (schema 5), `reference_image_specs.json`, `qa_report.json`, `prompt-gate` pass | R2, R42, R26, R24, R40-A/B/C, R45–R48, R15 v5, R18, R18-V5, R51 |
| 3 Flow Generation | `03_visuals` | `pipeline/flow_browser.py`, `pipeline/flow_live_single_worker.py`, `pipeline/reference_image_qa.py` | `reference_images/ref_*.png` + `reference_image_qa_report.json` (10-axis Q1–Q10 pass), `flow_native_clips/clip_1..clip_N.mp4` conditioned on approved reference images, provenance receipt, V1–V5 screenshots; voice outliers regenerated | R5, R14-A, R14-D, R18-B, R37, R39, R49, R51 |
| 4 Assembly | `04_audio`, `05_assembly`, `knowledge_base/` | `pipeline/diorama_assembler.py`, `pipeline/thumbnail_studio.py`, `produce_psychology_batch.py`, `pipeline/voice_fallback.py`, `pipeline/video_autopsy.py`, `pipeline/posthoc_semantic_qa.py`, `pipeline/asset_manifest.py`, `pipeline/knowledge_hub.py` | `voice_report.json`, `audio_master.wav`, `subtitles.ass`, `final_shorts_1080x1920.mp4`, `asset_manifest.json`, `posthoc_semantic_qa_report.json` + `posthoc_viewer_strips/`, `thumbnail_report.json` + `thumbnail_contact_sheet.png`, autopsy + QA reports, `knowledge_base/` sync | R13, R16, R17, R41, R43-A/B, R25, R49, R50, R50-B, R63, R64, R65, R66 |
| 5 Publish + Studio | `06_publish` | `pipeline/publish.py`, `pipeline/thumbnail_studio.py`, `pipeline/studio/` | metadata, R65 scored thumbnails A/B/C + `cover_frame_sec`, upload / community receipts, daily report | R8–R10, R4, R30–R36, R65 |

**Topic → prompt database:** `pipeline/prompts_db.py` pre-renders every catalog topic through `flow_prompt_builder` into `BCI_Shorts_Channel/database/` (records: `visual_plan`, `clip_narrations_5` / `clip_narrations_10`, `flow_5clip_prompts` / `flow_10clip_prompts`; QA counts from `validate_flow_prompts` / `validate_narrations`). Records are drafts — upgrade them with a hand-authored `visual_plan` via [bci-script-gen](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/skills/bci-script-gen/SKILL.md) before generation.

**Canonical prompt example:** [capgras_delusion_10clip_prompts.md](file:///C:/Users/yunky/.gemini/antigravity/brain/a935bacf-5ae3-4e1a-b5e2-7ed23172c727/capgras_delusion_10clip_prompts.md); in-repo golden = Capgras topic `visual_plan` in `pipeline/topics_catalog.py`.

**Prompt System v5 (2026-10-24):** every new topic goes research dossier → visual mode (brain only when the topic needs it) → iconic must-have scene in clip 1–2 → Action-Physics acting → brain ↔ story link → plain-language, TTS-safe script → `prompt-gate`. Worked examples: `BCI_Shorts_Channel/research_dossiers/{invisible_gorilla_attention, pavlov_dogs_conditioning, milgram_obedience_shock}/shorts_v5/`. Shorts are extracts of longform-depth dossiers; every clip is archived in the asset library for longform reuse.

**Neuro-Diorama System v7 (`DEFAULT_PRODUCTION_PROFILE = "neuro_diorama"`, `DEFAULT_DIORAMA_STYLE_PROFILE = "porcelain_cinematic_v7"` (`R66`; legacy `lowpoly_pastel_v7` preserved under `R63`), `dynamic_rush_v7` prosody (rush `+12%` / stamp `+8%` / brisk `+15%` native per-gear speech), `+14Hz` Silk Clean voice, 3-sentence cold-open (`R57-H2`), 100% US English):** 3-minute (`DIORAMA_V7_DURATION_MIN_SEC..DIORAMA_DURATION_MAX_SEC`, hard ceiling `<= SHORTS_HARD_CEILING_SEC`) 6-Act Neuro-Documentary Long-Short staged in **`PORCELAIN_V7_WORLD_STYLE`** (`PORCELAIN_V7_CAST_STYLE`, `PORCELAIN_V7_OPTICS_LOCK`) at native `DIORAMA_V7_VIDEO_FPS` (`DIORAMA_V7_VISUAL_PLAYBACK_SPEED`), 6-grammar porcelain cast/hand action & **Contained Living 4-Color 3D Brain** (`PORCELAIN_V7_VISUAL_GRAMMARS`, `PORCELAIN_V7_BRAIN_RENDER_MODES`; zero uncontained neon-green particle spill), `DIORAMA_V7_SPLIT_MODE` comparison cuts, bundled `FONT_CONDENSED_BLACK_PATH` frame-grid subtitles + giant top chapter headlines, `R63-P` `dynamic_rush_v7` sentence-level prosody (`DIORAMA_V7_PROSODY_GEAR_RATES`, zero WSOLA; `en-US-AndrewMultilingualNeural`, `DIORAMA_V7_TTS_PITCH`, `DIORAMA_V7_TTS_VOLUME` tear-free Silk Clean EQ) / `DIORAMA_V7_TTS_SPEED` (`kokoro-onnx` fallback) waveform breath-trimmed narration, 2-channel stereo documentary score (`DIORAMA_V7_BGM_DUCK_DB`), **Post-Hoc Clip-by-Clip Expressive Clarity QA (`R64`, `pipeline/posthoc_semantic_qa.py`)**, and channel-wide **Accumulated Knowledge Hub (`R50-B`, `BCI_Shorts_Channel/knowledge_base/`)**. Golden cold-open + prosody + audio example: `projects/diorama_01_hm_lab_B_dynamic` (approved 2026-10-31). Legacy `lowpoly_pastel_v7` visual golden: `BCI_Shorts_Channel/research_dossiers/phineas_gage_iron_rod/diorama_v7_lowpoly/` (`projects/gage_diorama_v7_lowpoly`; Schema v6 archive golden: `projects/gage_diorama_v6_dynamic`).

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
| `dossier init\|validate\|seed\|doi\|yt-search\|yt-analyze\|checklist --slug <slug> [--style-profile porcelain_cinematic_v7\|lowpoly_pastel_v7] [...]` | Gear 1b research dossier (R44; `seed --profile neuro_diorama` defaults to `porcelain_cinematic_v7`) |
| `prompt-gate --dir <project_or_draft_dir>` | v5 / v6 / v7 production gate before Gear 3 (R18-V5, R61, R63, R66, R57-H2 cold-open) |
| `prosody-qa --project <project_id> [--no-asr]` | Prosody QA gates P1–P10 (cold-open timing, breathless rush, stamp beat, ASR by gear, audio integrity, re-hook spacing) (R63-P); also run inside `diorama-batch` |
| `audit-prompts` | back-catalogue score sheet → `BCI_Shorts_Channel/reports/prompt_v5_score_sheet.md` |
| `voice-check --project <project_id>` | semitone voice-consistency report (R49) |
| `asset-manifest --project <project_id>` | asset manifest v2 + library index (R50) |
| `ref-qa --project <project_id> [--register <file> --source flow_image_generation\|gemini_image_generation] [--audit]` | reference image specs + Q1–Q11 QA; exits 0 only when `pre_generation_ready` (R51) |
| `packets --project <project_id> [--backend gemini_app\|flow] [--voice-source tts\|native] [--chain N]` | scene blueprint + per-clip generation packets; `--chain N` cuts clip N's last frame as clip N+1's start frame (R52) |
| `diorama-flow --project <project_id> [--tabs 5] [--clips ...] [--clean] [--cdp-port 9222] [--engine auto\|omni\|zero-credit]` | Schema v6/v7 5-tab sharded Dual-Tier (`Omni 1.1 Flash` -> `0-credit` auto-fallback) Google Flow generation (`60+` unique 1:1 Zero-Reuse clips, virtual-scroll top-pinned, CV motion/plaque gate, provenance lock) |
| `diorama-assemble --project <project_id> [--force] [--posthoc-qa]` | Schema v7 `porcelain_cinematic_v7` (default, R66) / `lowpoly_pastel_v7` (legacy, R63) (`dynamic_rush_v7` per-gear native speech, `+14Hz` Silk Clean `en-US-AndrewMultilingualNeural`, `24fps`) & Schema v6 `neuro_diorama` assembly + automatic `DQ1–DQ12`, `Autopsy`, `R64` post-hoc QA & Knowledge Hub sync (R56–R66) |
| `episode-qa --project <project_id> [--compile-only]` | Dynamic per-episode QA contract (`episode_qa_contract.json`) & 12-axis post-assembly verification (`DQ1–DQ12`, R62) |
| `posthoc-qa --project <project_id> [--init-review] [--auto-populate-review] [--require-review]` | Post-hoc clip-by-clip expressive clarity verification QA across 100% of cuts + viewer contact strips + source-clip remediation attribution (R64) |
| `thumbnail --project <project_id> \| --all-diorama [--unpublished-only] [--force] [--soft]` | R65 Thumbnail Studio: EDL candidate scoring, v7 condensed hook overlay, `TQ1–TQ7` QA gate, `cover_frame_sec` & contact sheet |
| `kb sync\|stats\|search [--project <id>] [--run-missing-posthoc] [--pack clips\|prompts\|analogies\|brain_models\|locations]` | Channel-wide Knowledge Hub (`BCI_Shorts_Channel/knowledge_base/`) sync, analytics summary, and reusable asset search (R50-B) |
| `diorama-batch [--wave 1\|2\|3\|4\|all] [--projects ...] [--precheck-only] [--engine auto\|omni\|zero-credit]` | Resumable 20-episode `neuro_diorama` batch orchestrator (`prompt-gate` + TTS clock precheck + 5-tab Dual-Tier Flow + assembly + `verify` + `autopsy` + `episode-qa` + `posthoc-qa` + `kb sync`) |
| `diorama-episode --slug <slug> --project <project_id> --pillar <pillar> [--precheck-only] [--engine auto\|omni\|zero-credit] [--force]` | One-shot production of ANY dossier-backed v7 episode (sync draft → precheck incl. R57-H2 + TTS clock → Flow → assembly → verify/autopsy/episode-qa/posthoc-qa/prosody-qa, auto-heal); refuses published projects |

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
| R5 | visual_prompt_spec | Credit-aware Dual-Tier Google Flow (`Omni 1.1 Flash` primary -> `0-credit` `Veo 3.1 - Lite [Lower Priority]` auto-fallback), visible Whale, zero paid APIs |
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
| R31 | youtube_studio_operations | R65 scored v7 thumbnails A/B/C (`> THUMB_MIN_FILE_BYTES`, pairwise diff `>= THUMB_MIN_PAIRWISE_DIFF`, `TQ1–TQ7`) + in-video `cover_frame_sec` |
| R32 | youtube_studio_operations | Sequential A/B/C Z-test (long-form videos only; Shorts use R65 `cover_frame_sec` + KB telemetry) |
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
| R50 / R50-B | research_dossier_rules | Asset manifest v2, asset library, aspect-neutral prompts, and `knowledge_base/` reusable intelligence hub (`pipeline/knowledge_hub.py`) |
| R51 / R52 | reference_depiction_rules | Default text-only Schema v4 generation; optional reference image conditioning (`ref-qa`, `packets`) |
| R46-K | scene_depiction_rules | Key physical prop interaction visible in Clip 1–2 |
| R44-D | research_dossier_rules | Research depth standard (sources, sourced facts, analysed footage, stageable iconic scene, `[fact]` number trace) |
| R53 | brain_depiction_rules | `31_O2CmlKOk` 3D brain gallery signal conduction (`bioluminescent green` particles along `signal_path`, `crimson-red` lesion, `electric cyan-blue` hub, `warm amber-gold` compensatory route) |
| R54 | visual_prompt_spec | Modular Depiction Rule Composition (`CastDepictionRule` + `SceneDepictionRule` + `BrainDepictionRule` + `CameraDepictionRule` + `ReferenceDepictionRule`) |
| R55 | brain_depiction_rules / camera_choreography_rules | Cranium dive in Clip 4 (`crisis`) → 3D brain in bright white studio gallery (`Clip 4–8`) → Cranium pull-out in Clip 9 (`breakthrough`) |
| R18-V5 | qa_gates_rules | `validate_production_v5` production gate |
| R14-D v5 | camera_choreography_rules | Reenactment camera vocabulary |
| R56 | neuro_diorama_rules | Zero-flesh dark-oak cutaway diorama + clothed matte-white bisque-ceramic miniature cast (`R56-C`), bloodless ceramic impact/trauma action (`R56-M`/`R56-I`) + `<= 20%` crystal specimens, zero in-scene AI text |
| R57 | neuro_diorama_rules | 6-Act brisk (`DIORAMA_DURATION_MIN_SEC..DIORAMA_DURATION_MAX_SEC`, `<= SHORTS_HARD_CEILING_SEC`) 100% US English storyteller spine, zero opening slogan or `"Imagine..."` weak hook (`R57-H`), concrete case names & glossed neuro vocabulary (`R57-C`), midpoint `?` open-loop (`R57-M`), `100%` `[Number] -> [Everyday Analogy]` + literal 1:1 analogy cutaways (`R57-V`) |
| R58 | neuro_diorama_rules | Audio-first master clock (`edge-tts` `en-US-AndrewMultilingualNeural` `DIORAMA_TTS_RATE` Act-continuous storyteller, `kokoro-onnx` fallback) & 3-Gear 1:1 Zero-Reuse dynamic EDL (`DIORAMA_VISUAL_PLAYBACK_SPEED`, `DIORAMA_ENTRY_SPEED_RAMP`, `56–66+` unique clips) |
| R59 | neuro_diorama_rules | Documentary restraint audio (`DIORAMA_BGM_BPM`, `DIORAMA_BGM_DUCK_DB`, zero UI cut ticks, outro swell, `DIORAMA_TARGET_LUFS`) & pure-white `Y=64%` (`DIORAMA_SUBTITLE_MARGIN_V`) 1-line hard-cut subtitles + clean top callouts |
| R60 | neuro_diorama_rules | 2-Clause US English Paradox Title formula (`<= TITLE_MAX_CHARS_DIORAMA`) |
| R61 | neuro_diorama_rules | `validate_production_diorama_v6` pre-Flow & autopsy production gate |
| R62 | neuro_diorama_rules | Dynamic per-episode QA contract (`episode_qa_contract.json`) & 3-stage multimodal gate (`DQ1–DQ12`, `pipeline/dynamic_episode_qa.py`) |
| R63 | neuro_diorama_rules | Schema v7 Full-Bleed Low-Poly Pastel Architecture (`DIORAMA_V7_STYLE_PROFILE = "lowpoly_pastel_v7"` legacy parity + shared v7 `DIORAMA_V7_VIDEO_FPS` @ `DIORAMA_V7_VISUAL_PLAYBACK_SPEED`, `hstack` split, bundled `AABCondensed-Black.ttf` frame-grid subtitles + programmatic `AnatomyLabel` brain badges, `+14Hz` Silk Clean `en-US-AndrewMultilingualNeural` + 2ch stereo score) |
| R64 | neuro_diorama_rules | Post-Hoc Clip-by-Clip Expressive Clarity Verification QA (`pipeline/posthoc_semantic_qa.py`, `main.py posthoc-qa`: 100%-cut 5-axis clarity scoring, annotated viewer contact strips, SHA-256-bound semantic review, and source-clip remediation attribution) |
| R63-P | neuro_diorama_rules | `dynamic_rush_v7` sentence-level prosody (default): native per-gear edge-tts rates (`DIORAMA_V7_PROSODY_GEAR_RATES`), zero WSOLA, 6ms splice fades, single `DIORAMA_V7_MASTER_DEESSER`, Prosody QA P1–P10 |
| R57-H2 | neuro_diorama_rules | Schema v7 3-sentence cold-open: S1 myth-flip `!` (rush) → S2 `Yet/But…` contrast (rush) → S3 `This is the true story of <case>.` stamp; R57-R re-hook spacing `<= PROSODY_P10_OPEN_LOOP_MAX_GAP_SEC` |
| R65 | neuro_diorama_rules | Thumbnail Studio & In-Video Cover Frame (`pipeline/thumbnail_studio.py`, `visual_plan.thumbnail`, `TQ1–TQ7` QA gate, `cover_frame_sec` aligned with cold-open stamp headline) |
| R66 | neuro_diorama_rules | Default Schema v7 `porcelain_cinematic_v7` Style Profile & Contained Living 4-Color 3D Brain (`DEFAULT_DIORAMA_STYLE_PROFILE = PORCELAIN_V7_STYLE_PROFILE`, photorealistic bright rooms, clothed matte-white porcelain cast/hands, enclosed `cyan-blue` / `crimson-red` / `amber-gold` / `pearl-aqua` 3D brain, zero uncontained neon-green particle spill) |
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
- [Rule: Master QA Loop & Video Validation Protocol](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/qa_gates_rules.md) — R18 G1–G12, R18-B V1–V5, R25 delivery, R37 6-guard lock, executable QA suite + R64 post-hoc clarity verification.
- [Rule: 7 Content Pillars & Domain Isolation Protocol](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/pillars_domain_rules.md) — P1 pillars, signal-path seeds, R20 weekly diversity.
- [Rule: Channel Operations & Workspace Hygiene Protocol](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/channel_operations_rules.md) — R8–R12, R19, R28, R29: metadata, project layout, `knowledge_base/` & shared locations, independent ending, test hygiene, recovery.
- [Rule: YouTube Studio Shorts Operations Protocol](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/youtube_studio_operations.md) — R4, R30–R36, R35-B, R36-B: timetable, thumbnails, Z-test, staging, queue, pinned DOI, Short-to-Short `Related video` & playlist ring, localization, Polymer click & tab hygiene.
- [Rule: Research Dossier & Longform Reuse Protocol](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/research_dossier_rules.md) — R44, R50, R50-B: dossier files and research checklist, free reference-media tools, asset manifest v2 and library, `knowledge_base/` reusable intelligence hub, aspect-neutral prompts.
- [Rule: Neuro-Diorama 3-Minute Long-Short Protocol (Schema v6/v7)](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/neuro_diorama_rules.md) — R56–R64: default Schema v7 `lowpoly_pastel_v7` (`24fps`, `dynamic_rush_v7` per-gear native `+12%`/`+8%`/`+15%` `+14Hz` Silk Clean speech, R57-H2 3-sentence cold-open, `hstack` split, condensed frame-grid subtitles), Schema v6 archive support, dynamic per-episode QA (`R62`), and post-hoc clip-by-clip expressive clarity verification (`R64`).

### Skills (`skills/`)
- [Skill: BCI Episode Production](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/skills/bci-episode-production/SKILL.md) — Fully automatic one-topic → QA-passed final MP4 runbook (dossier → R57-H2 script → prompt-gate → `diorama-episode` → full QA); golden = `projects/diorama_01_hm_lab_B_dynamic`.
- [Skill: BCI Video Pipeline (Master Orchestrator)](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/skills/bci-video-pipeline/SKILL.md) — Runs the 5-Gear pipeline end to end.
- [Skill: BCI News Hunter](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/skills/bci-news-hunt/SKILL.md) — One verified case per topic (discovery, DOI, duplicate check); hands off to bci-deep-research.
- [Skill: BCI Deep Research](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/skills/bci-deep-research/SKILL.md) — Longform-depth research dossier: sources, iconic scene bible, YouTube/archive analysis, plain language, brain links, visual mode, longform outline.
- [Skill: BCI Script Generator](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/skills/bci-script-gen/SKILL.md) — Hand-authored `clip_narrations` + `visual_plan`, rendered and validated with `flow_prompt_builder`.
- [Skill: BCI Video Assembly & Audio Engineering](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/skills/bci-video-assembly/SKILL.md) — ASR ordering, vocal windows, holds, subtitles, soundscape, mux, autopsy.
- [Skill: BCI Weekly Batch](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/skills/bci-weekly-batch/SKILL.md) — 7-pillar weekly batch in capped parallel chunks.
- [Skill: YouTube Studio Manager](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/skills/youtube-studio-manager/SKILL.md) — Upload, schedule, `Related video` & 7-Pillar playlist linking, pin, A/B test, localization.
- [Skill: YouTube Daily Report (`/report_youtube`)](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/skills/report_youtube/SKILL.md) — Channel-level numbers-first traffic-light executive report (Sections `0–5`) + per-video detail report and standalone PNG charts.

---

## 4. Specialist Agent Architecture & Unified SSOT (`.agents/` ↔ Hermes)

`.agents/` in this workspace is the **Single Source of Truth (SSOT)** for both **Antigravity** and **Hermes**:
- **In Antigravity**: `AGENTS.md` + `.agents/rules/*.md` + `.agents/skills/*/SKILL.md` are loaded directly. You do **not** need separate `SOUL.md` files when working in Antigravity; all specialist scopes, commands, and verification gates are consolidated below.
- **In Hermes (`~/.hermes/profiles/yt-*`)**: Each profile's `SOUL.md` and `skills/youtube-pipeline/*` are symlinked directly to `.agents/profiles/yt-*/SOUL.md` and `.agents/skills/*`, preventing any drift between environments.

| Specialist / Gear | Scope & Hard Boundary | Required Verification & CLI | Primary Rules & Skills |
|---|---|---|---|
| **Gear 1–2 (`@yt-writer`)**<br>[SOUL.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/profiles/yt-writer/SOUL.md) | Topic research, single-case DOI verification, **research dossier** (`research_dossiers/<slug>/`, incl. `yt-dlp` reference analysis), `script.json` (plain-language & TTS-safe), v5 `visual_plan.json`, `flow_prompt_builder.py`, `flow_all_in_one_prompts.json`. Never opens the Flow browser or runs FFmpeg assembly. | `main.py dossier validate --slug <slug>` (`ready: true`) → `main.py prompt-gate --dir <dir>` (`passed: true`, `issues: []`, `cutoff_risk == False`) | [bci-news-hunt](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/skills/bci-news-hunt/SKILL.md), [bci-deep-research](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/skills/bci-deep-research/SKILL.md), [bci-script-gen](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/skills/bci-script-gen/SKILL.md), R1, R2, R14-A/B, R15 v5, R21, R26, R38, R40-A/B/C, R42, R44–R48, R18-V5 |
| **Gear 3 (`@yt-flow`)**<br>[SOUL.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/profiles/yt-flow/SOUL.md) | Exclusive owner of `.flow_download_harvest.lock` and Naver Whale (`--remote-debugging-port=9222`) Flow tabs. Dynamic `"8s"` / `"10s"` clip generation (auto-upgrading `8s -> 10s` on `is_end_truncated` retry), V1–V5 gates, R49 outlier clip regeneration. Never rewrites `script.json`. | `main.py flow-parallel --projects <id> --trigger` · all `clip_1..clip_N.mp4 > 100KB` · V1–V5 pass | [bci-video-pipeline](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/skills/bci-video-pipeline/SKILL.md), R5, R18-B, R37, R49 |
| **Gear 4 (`@yt-editor`)**<br>[SOUL.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/profiles/yt-editor/SOUL.md) | `neuro_diorama` v7/v6 assembly (`diorama_assembler.py`: `dynamic_rush_v7` per-gear native `+14Hz` Silk Clean `en-US-AndrewMultilingualNeural` breath-trimmed master, native `24fps` `1.00x` EDL + `split_hstack`, condensed frame-grid subtitles, 2ch stereo score) & classic v5 clip ingest/ASR ordering/R49 voice gate, R50 `asset_manifest.json` v2, R50-B `knowledge_base/` sync, R62 `episode-qa`, R64 `posthoc-qa` clip-by-clip expressive clarity verification, `VideoAutopsyEngine` & `main.py qa`. | `main.py diorama-assemble --project <id>` · `main.py episode-qa --project <id>` · `main.py posthoc-qa --project <id>` · `main.py kb sync --project <id>` · `main.py autopsy --project <id>` · `main.py qa --project <id>` | [bci-video-assembly](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/skills/bci-video-assembly/SKILL.md), R13, R16, R17, R39, R41, R43-A/B, R49, R50, R50-B, R62, R63, R64, R18, R25 |
| **Gear 5 (`@yt-studio`)**<br>[SOUL.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/profiles/yt-studio/SOUL.md) | Thumbnails A/B/C (top safe-zone `y=185..445` clean documentary typography, zero sci-fi HUD reticles in `neuro_diorama` v7), Unlisted staging (SHA-256-locked `Autopsy` + `DQ1–DQ12` + `R64` + `posthoc_semantic_review.json` upload gate), stage-gated prime-slot scheduling (`daily_prime_only=True` -> Slot 2 `12:00 ET` & Slot 4 `20:00 ET` under 10K subs, DST-aware `America/New_York` -> `Asia/Seoul`), Short-to-Short `Related video` circular seed-rescue ring & 7-Pillar playlists, pinned DOI comment, Z-test, daily 07:00 AM analytics report (`/report_youtube`, cron `2e725d86049e`). | `main.py studio-upload` · `studio-queue` · `studio-link` · `studio-pin` · `studio-ab-test` · `studio-report` · verify `06_publish/studio_publish_receipt.json` | [youtube-studio-manager](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/skills/youtube-studio-manager/SKILL.md), [report_youtube](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/skills/report_youtube/SKILL.md), R4, R8–R10, R30–R36, R35-B, R36-B |

- **Python interpreter on Linux**: Always use `/home/canadaofbin/hermes-venv/bin/python -X utf8` (which has `cv2`, `faster_whisper`, `yt_dlp`, `kokoro_onnx`, `soundfile`, `websockets`, `matplotlib`, and `pytest` installed).
- **Google Drive FUSE (`gdrive`) hygiene**: `/home/canadaofbin/gdrive` is a `fuse.rclone` mount; avoid recursive `rm -rf` or `du -sh` across large project trees (use `rclone purge gdrive:Kyubin_Yun_Workspace/07_Youtube/<dir>` or `rclone deletefile` for bulk operations). Completed batch MP4 deliverables are stored at `Completed_Psychology_100_Shorts/final_shorts_<project_id>.mp4`.
