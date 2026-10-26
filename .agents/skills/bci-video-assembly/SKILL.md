---
name: bci-video-assembly
description: Assembles downloaded Google Flow Omni 1.1 clips (clip_1..clip_N) into the final vertical ALL ABOUT BRAIN Short - ASR clip ordering, per-clip vocal window detection and vocal chain, synchronized A/V speed-up, short inter-clip holds with a pre-pivot beat, independent conclusion ending with end fade, single-line gold-keyword subtitles, 4-layer soundscape, final mux and VideoAutopsyEngine verification. No overlays, no punch-in zoom, no loop.
---

# BCI Video Assembly & Audio Engineering

Master: [AGENTS.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/AGENTS.md) · Rules: [audio_assembly_rules.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/audio_assembly_rules.md) (R13, R16, R17, R39, R41, R43-A, R43-B) · [qa_gates_rules.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/qa_gates_rules.md) (R18, R25, R37) · Numbers: [production_constants.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/production_constants.md)

Code: [`produce_psychology_batch.py`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/produce_psychology_batch.py) (`measure_clip_speech_window`, `extract_native_flow_clip_speech`, `generate_audio_master_wav`, `generate_ass_subtitles`, `assemble_final_shorts_video`), `pipeline/flow_live_single_worker.py` (`order_downloaded_flow_clips_for_project`), `pipeline/video_autopsy.py` (`VideoAutopsyEngine`).

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
