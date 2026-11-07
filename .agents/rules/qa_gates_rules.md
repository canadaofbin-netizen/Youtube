# Master QA Gates & Validation (`R18`, `R18-V5`, `R18-B`, `R25`, `R37`)

Index: [AGENTS.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/AGENTS.md) | Numbers: [production_constants.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/production_constants.md) | Diorama Gates: [neuro_diorama_rules.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/neuro_diorama_rules.md) (`R61–R67`) | Code: [`pipeline/qa_gates.py`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/qa_gates.py), [`pipeline/posthoc_semantic_qa.py`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/posthoc_semantic_qa.py)

## Active `neuro_diorama` Gate Chain (Pre-Upload Lock — `verify_publish_ready_qa_bundle`)
1. **Gear 1 (`dossier validate --require-v2`)**: `Schema v2` 3-Layer + `R44-D` depth + `R44-M` 4-Gate media suitability (`08_reenactment_edl.json` for Track A).
2. **Gear 2 (`prompt-gate`)**: `R57-H2` cold-open, FK grade, Anti-Clone 4-gram Jaccard, `[fact]` dossier numbers, `R60` title, `R65` thumbnail block.
3. **Gear 3 (`porcelain-refs` / `ref-qa` / `reenact-qa`)**: `Q1–Q10` + provenance (`flow_image_generation`); `RQ1–RQ5` (`dHash >= REENACT_MIN_DHASH_DISTANCE`, `0.0%` 5-gram overlap, `/tmp/aab_reenact` purged) on Track A.
4. **Gear 4 (`autopsy` + `episode-qa` + `prosody-qa` + `posthoc-qa` + `thumbnail`)**: SHA-256-bound `video_autopsy_report.json` + `DQ1–DQ12` (`dynamic_episode_qa_report.json`) + `P1–P10` (`prosody_report.json`) + `R64` 100%-cut clarity (`posthoc_semantic_qa_report.json` + `posthoc_semantic_review.json`) + `R65` `TQ1–TQ7` (`thumbnail_report.json`).

## R18 — Master QA Gates `G1–G12` (`ScriptingStage.validate_qa_gates`)
Delegates prompt/narration checks to `flow_prompt_builder.validate_flow_prompts` & `validate_narrations` (`02_script/qa_report.json`, `05_assembly/master_qa_report.json`):
- **G1**: Word/timing budget & `FINAL_SHORTS_DURATION_MIN_SEC..FINAL_SHORTS_DURATION_MAX_SEC`, zero audio truncation.
- **G2 / G3 / G4 / G5 / G6**: Concrete hook (`R42`), failed attempt + cause (`R42`), real anatomy pathway (`R3`/`R38`), `"Which proves"`/`"Which is why"` conclusion (`R26`), zero 1st-person/clickbait (`R15`).
- **G7 / G8 / G9 / G10 / G11 / G12**: Setting + 4-color code + zero `#hex` (`R14-A`/`R21`), zero `BANNED_PROMPT_TOKENS` (`R14-B`), 1 camera move (`R14-D`), `Voice:` clause + zero `Audio:` (`R13`/`R40-A`), `"Instead of"` pivot + 2 memes (`R26`/`R24`), R41 vocal window + silence `< DEAD_AIR_FLOOR_SEC` (`R43-B`).

## R18-V5 — Classic v5 Gate (`validate_production_v5` / `main.py prompt-gate`)
Wraps `G1/G5/G8/G10/G11` + `[scene]` (`R46`), `[acting]` (`R47`), `[brain]` (`R45`/`R48`), `[plain]` (`R15 v5`), `[tts]` (`R49-T`), `[keyshot]` (`R46-K`), `[fact]` (`R44-D`). Pre-clip gates: `ref-qa` (`pre_generation_ready: true`, `R51`) & `packets` (`validate_scene_blueprints`, `R52`).

## R18-B, R25 & R37 — Browser Gates `V1–V5`, Single MP4 & 6-Guard Lock
- **R18-B (`03_visuals/flow_screenshots/` + `visual_qa_report.json`)**: `V1` (`flow_gate_v1_prompt_approved.png`: 9:16 + `.ProseMirror` prompt), `V2` (`first_clip_rendered`), `V3` (`all_clips_timeline`), `V4` (`export_ready` `.mp4`), `V5` (`ingested_clips`: `>= MIN_CLIP_SIZE_BYTES`, unique SHA-256 + dHash, ASR-ordered `R39`).
- **R25**: Single deliverable `05_assembly/final_shorts_1080x1920.mp4` + `probe_report.json` + `video_autopsy_report.json` + `master_qa_report.json`.
- **R37 (6 Guards)**:
  1. `flow_provenance_receipt.json` (`flow_project_url`, `tab_target_id`, clip SHA-256; canonical room `AAB_<project_id>`).
  2. Cross-project 64-bit dHash `> MAX_PERCEPTUAL_DHASH_HAMMING_DISTANCE`.
  3. Zero-shortcut static scan (`ALLOW_EXTERNAL_PAID_APIS=False`, `ALLOW_STATIC_IMAGE_VIDEO_FALLBACK=False`).
  4. Unverified quarantine (`projects_quarantine_pending_flow/`).
  5. `V1–V5` browser audit (`run_browser_generation_qa`).
  6. Per-worker CDP `targetId` tab lock (`allocate_dedicated_flow_project_tab`, `<= FLOW_MAX_PARALLEL_BATCH_SIZE` parallel tabs; close only self-opened tabs).
- **Executable Suite (`main.py verify` / `run_full_executable_qa`)**: Stage 1 `run_preflight_qa` -> Stage 2 `run_browser_generation_qa` -> Stage 3 `run_media_integrity_qa` -> Stage 4 `run_intent_content_qa` -> Stage 5 `run_posthoc_semantic_qa` (`R64`).
