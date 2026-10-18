# Rule: Audio & Assembly Protocol

Parent Master Index: [AGENTS.md](file:///g:/My%20Drive/Kyubin_Yun_Workspace/07_Youtube/.agents/AGENTS.md) · Numbers: [production_constants.md](file:///g:/My%20Drive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/production_constants.md) · Code: [`produce_psychology_batch.py`](file:///g:/My%20Drive/Kyubin_Yun_Workspace/07_Youtube/produce_psychology_batch.py)

Scope: voice, clip trimming, speed, subtitles, soundscape and final mux. Replaces `audio_voice_rules.md`. No HUD, no punch-in, no loop.

---

## R13 — Voice Lock (Puck only)
| Rule | Requirement |
|---|---|
| Voice | `FLOW_DEFAULT_VOICE` = Puck, the only entry of `FLOW_ALLOWED_VOICES`. Aoede / Kore are not used. |
| Delivery | Male documentary storyteller, English, `NATIVE_FLOW_WPS`; native Flow clip length targets `FLOW_CLIP_TARGET_SEC_MIN..FLOW_CLIP_TARGET_SEC_MAX`. |
| Verification | ASR clip ordering and QA accept a voice only inside `PUCK_F0_RANGE_HZ`. |

## R39 — Native Flow Media
| Rule | Requirement |
|---|---|
| Colour | Flow's native grade is kept; FFmpeg colour filters (`colorchannelmixer`, `colorbalance`, LUTs) are prohibited. |
| Speech | When native clips contain speech, local TTS is never overlaid. |
| Ordering | `order_downloaded_flow_clips_for_project` (`pipeline/flow_live_single_worker.py`) matches ASR transcripts to `clip_narrations` and writes `03_visuals/flow_native_clips/clip_1..clip_N.mp4`; every consumer sorts with `storage.numeric_clip_sort_key` (clip_10 after clip_9). |
| Count | Assembly needs ≥ `MIN_CLIPS_FOR_ASSEMBLY` clips, each `FLOW_CLIP_DURATION_MIN_SEC..FLOW_CLIP_DURATION_MAX_SEC` and ≥ `MIN_CLIP_SIZE_BYTES`. |

## R41 — Vocal Window & Vocal Chain
**`measure_clip_speech_window`** (per clip):
1. Formant-band RMS envelope finds syllable clusters (rejects Flow's ambient bed).
2. **Prompt-bleed cutoff** — once the expected syllables of the clip narration have been spoken (`PROMPT_BLEED_*`), the next long silence ends the window (`broke_early`), so read-outs of prompt text are never kept.
3. **Onset** — `speech_start` keeps a `VOCAL_ONSET_PAD_SEC` pad; clips after the first also drop up to `CLIP_PRE_ROLL_TRIM_SEC` of hesitation frames.
4. **Soft tail** — if not `broke_early`, quiet sentence endings are kept down to the `SOFT_TAIL_*` threshold, then `SPEECH_END_PAD_SEC` is added.

**`extract_native_flow_clip_speech`** (per clip): no `afftdn` / `agate`; band-pass + 3-band EQ (`VOCAL_EQ_*`) + compression + `atempo=AV_SPEEDUP_FACTOR`, then a raised-cosine envelope mask over `[speech_start, speech_end]` so holds are free of bleed.

## R43-A — A/V Speed
- Video (`setpts`) and voice (`atempo`) both run at `AV_SPEEDUP_FACTOR`, giving `EFFECTIVE_WPS`.
- **No mid-clip punch-in / zoom** (decision D4). No colour alteration (R39).

## R43-B — Trim, Holds & Ending
| Clip | Window |
|---|---|
| Normal clip | `[trim_start, speech_end + CLIP_VISUAL_HOLD_SEC]` |
| Pre-pivot clip (`pivot_clip_index(n) - 1`) | `[trim_start, speech_end + CLIP_PRE_PIVOT_HOLD_SEC]` |
| Final clip | `[trim_start, speech_end + FINAL_TAIL_SEC]` + `END_FADE_SEC` end fade — independent conclusion, **no loop** back to clip 1 |

Inter-clip silence must stay below `DEAD_AIR_FLOOR_SEC` (gate G12). Output: `VIDEO_WIDTH`×`VIDEO_HEIGHT` @ `VIDEO_FPS`, total `FINAL_SHORTS_DURATION_MIN_SEC..FINAL_SHORTS_DURATION_MAX_SEC`.

## R16 — Subtitles (`generate_ass_subtitles` → `04_audio/subtitles.ass`)
| Rule | Requirement |
|---|---|
| Layout | Single line (`SUBTITLE_MAX_LINES`), ≤ `SUBTITLE_MAX_WORDS_PER_EVENT` words per event, `SUBTITLE_FONT_NAME` / `SUBTITLE_FONT_SIZE`, outline `SUBTITLE_OUTLINE_WIDTH`, bottom margin `SUBTITLE_MARGIN_V`. |
| Emphasis | At most one gold keyword per event with a short scale micro-pop. |
| Timing | Events stay inside each clip's `[trim_start, speech_end]` (after speed-up); never across holds. |
| Removed | No `Telemetry` / `Callout` styles, no HUD badges, no pointer glyphs. |

## R17 — 4-Layer Soundscape (`generate_audio_master_wav` → `04_audio/audio_master.wav`)
| Layer | Content | Timing |
|---|---|---|
| 1 Voice | R41 vocal stems | per clip window |
| 2 Music bed | low tension drone + heartbeat sub-bass before the pivot → harmonic chime at the pivot → brighter synth pulse after | phase switch at pivot clip start |
| 3 Foley | biological / environment sounds matched to the role: room tone and props in `real_env` (monitor beeps, footsteps), breath and heartbeat, fluid whoosh for signal flow, electric crackle at a severed junction. No hydraulic / metallic-latch sounds. | once per clip, after the clip start |
| 4 UI tick | short crisp digital tick | every clip cut + pivot clip start (decision D3); not tied to any HUD |

Music and Foley are sidechain-ducked under the voice; master is loudness-normalised (48 kHz stereo) before mux.

## Final Mux (`assemble_final_shorts_video`)
`clip_1..clip_N` (R43-A/B) + `audio_master.wav` + `subtitles.ass` → `05_assembly/final_shorts_1080x1920.mp4` (≥ `MIN_FINAL_VIDEO_SIZE_BYTES`), then `VideoAutopsyEngine.inspect_project` (R18 Stage 3).
