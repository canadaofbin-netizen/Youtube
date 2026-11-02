---
name: bci-video-assembly
description: Assembles downloaded Google Flow Omni 1.1 clips (clip_1..clip_N) into the final vertical ALL ABOUT BRAIN Short - ASR clip ordering, per-clip vocal window detection and vocal chain, synchronized A/V speed-up, short inter-clip holds with a pre-pivot beat, independent conclusion ending with end fade, single-line gold-keyword subtitles, 4-layer soundscape, final mux and VideoAutopsyEngine verification. No overlays, no punch-in zoom, no loop.
---

# BCI Video Assembly & Audio Engineering

Master: [AGENTS.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/AGENTS.md) · Rules: [neuro_diorama_rules.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/neuro_diorama_rules.md) (R58, R59, R61–R64 flagship `neuro_diorama` v7/v6) · [audio_assembly_rules.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/audio_assembly_rules.md) (R13, R16, R17, R39, R41, R43-A, R43-B) · [qa_gates_rules.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/qa_gates_rules.md) (R18, R25, R37) · Numbers: [production_constants.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/production_constants.md)

Code: [`pipeline/diorama_assembler.py`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/diorama_assembler.py) (`build_crosscut_edl`, `generate_diorama_ass_subtitles`, `generate_diorama_audio_master`, `assemble_diorama_project`), [`pipeline/posthoc_semantic_qa.py`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/posthoc_semantic_qa.py) (`run_posthoc_semantic_qa`, `render_posthoc_viewer_strips`), [`pipeline/knowledge_hub.py`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/knowledge_hub.py) (`sync_project_to_knowledge_base`), [`produce_psychology_batch.py`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/produce_psychology_batch.py), `pipeline/flow_live_single_worker.py` (`order_downloaded_flow_clips_for_project`), `pipeline/video_autopsy.py` (`VideoAutopsyEngine`).

---

## Neuro-Diorama v7 / v6 Assembly (`DEFAULT_DIORAMA_STYLE_PROFILE = "lowpoly_pastel_v7"`, R58–R64)
- Run `python -X utf8 main.py diorama-assemble --project <id>` (which automatically runs R64 `posthoc-qa` and syncs `BCI_Shorts_Channel/knowledge_base/`):
  1. **Schema v7 (`lowpoly_pastel_v7`, default, R63 / R63-P)**: Synthesizes `dynamic_rush_v7` sentence-level prosody (`DIORAMA_V7_PROSODY_MODE`; native per-gear `DIORAMA_V7_PROSODY_GEAR_RATES` rush `+12%` / stamp `+8%` / brisk `+15%`, zero WSOLA; `en-US-AndrewMultilingualNeural`, `DIORAMA_V7_TTS_PITCH`, `DIORAMA_V7_TTS_VOLUME` tear-free Silk Clean EQ + single `DIORAMA_V7_MASTER_DEESSER`, `DIORAMA_V7_TTS_SPEED` offline `kokoro-onnx` fallback; per-project override via `script.json` `prosody_mode` / `--prosody-mode`) waveform breath-trimmed voiceover (`>= DIORAMA_V7_ACTIVE_VOICED_RMS_RATIO_MIN` RMS voiced density), builds a native `DIORAMA_V7_VIDEO_FPS` (`DIORAMA_V7_VISUAL_PLAYBACK_SPEED`) 1:1 Zero-Reuse dynamic-CV EDL (`05_assembly/edit_decision_list.json`, `DIORAMA_V7_SPLIT_MODE`), burns bundled `FONT_CONDENSED_BLACK_PATH` frame-grid subtitles + top chapter headlines, mixes 2-channel stereo BGM (`DIORAMA_V7_BGM_DUCK_DB`), and runs **Post-Hoc Clip-by-Clip Expressive Clarity QA (`R64`)** (`05_assembly/posthoc_semantic_qa_report.json` + `05_assembly/posthoc_viewer_strips/sheet_*.jpg`) + `knowledge_base/` sync (`R50-B`).
  2. **Schema v6 (`neuro_diorama` dark-void archive, R58–R59)**: Synthesizes `DIORAMA_TTS_VOICE` / `VOICE_FALLBACK_VOICE` voiceover auto-fitted to `DIORAMA_DURATION_MIN_SEC..DIORAMA_DURATION_MAX_SEC` (`<= SHORTS_HARD_CEILING_SEC`), builds 1:1 Zero-Reuse or 3-window EDL, burns `MarginV = DIORAMA_SUBTITLE_MARGIN_V` pure `#FFFFFF` ASS subtitles, and mixes `DIORAMA_BGM_BPM` pulse BGM at `DIORAMA_BGM_DUCK_DB`.

---

## Inputs
- `02_script/script.json` → `clip_narrations` (N lines, roles = `clip_roles(N)`).
- Downloaded Flow MP4s (from `flow-parallel` or a manual download folder).

## Procedure
| Step | Action | Output | Rule |
|---|---|---|---|
| 1 | Import + ASR-order clips: `python -X utf8 main.py import-clips --project <id> --dir <download_dir>` | `03_visuals/flow_native_clips/clip_1..clip_N.mp4` (numeric order) | R39 |
| 2 | Check count / size / duration (≥ `MIN_CLIPS_FOR_ASSEMBLY`, ≥ `MIN_CLIP_SIZE_BYTES`, `FLOW_CLIP_DURATION_MIN_SEC..MAX_SEC`); Puck F0 inside `PUCK_F0_RANGE_HZ` | — | R13, R39 |
| 3 | Measure each clip's vocal window (prompt-bleed cutoff, onset pad, pre-roll trim except clip 1, soft tail) | `[trim_start, speech_end]` per clip | R41 |
| 4 | Apply windows + holds: normal `CLIP_VISUAL_HOLD_SEC`, pre-pivot `CLIP_PRE_PIVOT_HOLD_SEC`, final `FINAL_TAIL_SEC` + `END_FADE_SEC` fade; speed `AV_SPEEDUP_FACTOR` on video and voice | trimmed segments | R43-A, R43-B |
| 5 | Vocal chain + 4-layer soundscape (music phase switch at pivot; biological / environment Foley; UI tick on every cut + pivot start); duck under voice; loudness-normalise | `04_audio/audio_master.wav` | R41, R17 |
| 6 | Subtitles from `clip_narrations`, locked to each window; single line, gold keyword | `04_audio/subtitles.ass` | R16 |
| 7 | Mux | `05_assembly/final_shorts_1080x1920.mp4` | R25 |
| 8 | Verify: `python -X utf8 main.py autopsy --project <id>` then `python -X utf8 main.py qa --project <id>` | `video_autopsy_report.json`, `master_qa_report.json` | R18, R37 |

Steps 2–7 run automatically with `import-clips … --auto-assemble`.

## Never
- Colour filters / LUTs, local TTS over native speech (R39).
- HUD / telemetry / callout overlays, mid-clip punch-in zoom, loop tail back to clip 1 (D4, R19).
- `afftdn` / `agate` on the voice (R41).
- Touching legacy folders frozen by decision D7.

## Failure handling
| Symptom | Fix |
|---|---|
| Clip order wrong | Re-run step 1; ordering uses ASR vs `clip_narrations`, never file names. |
| Trailing prompt read-out audible | Prompt-bleed cutoff missed → check `PROMPT_BLEED_*`; regenerate the clip if the read-out is mid-sentence. |
| Last word clipped | Soft-tail threshold too strict → check `SOFT_TAIL_*` / `SPEECH_END_PAD_SEC`. |
| G12 dead-air failure | Inter-clip silence ≥ `DEAD_AIR_FLOOR_SEC`; re-measure windows. |
| Duration out of bounds | Too few/many words (R2) or clips; fix the script, not the speed. |
