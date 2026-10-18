# Production Constants — Single Numeric Source of Truth

Owner of all numeric thresholds, budgets, and timing constants across the ALL ABOUT BRAIN workspace. Every constant below maps 1:1 to [pipeline/config.py](file:///g:/My%20Drive/Kyubin_Yun_Workspace/07_Youtube/pipeline/config.py). No other rule or skill file may restate numeric values; other documents reference these constant names directly.

---

## 1. Video & Clip Specifications

| Constant | Value | Unit | Meaning |
|---|---|---|---|
| `VIDEO_WIDTH` | `1080` | px | Vertical Shorts output width (9:16) |
| `VIDEO_HEIGHT` | `1920` | px | Vertical Shorts output height (9:16) |
| `VIDEO_FPS` | `30` | fps | Output frame rate |
| `VIDEO_MAX_DURATION_SEC` | `105.0` | s | Hard ceiling on final assembled Shorts duration |
| `CLIP_COUNT_MIN` | `5` | clips | Minimum native Google Flow clips per Short |
| `CLIP_COUNT_MAX` | `10` | clips | Maximum native Google Flow clips per Short |
| `DEFAULT_CLIP_COUNT` | `10` | clips | Default clip count (10-clip Deep-Mechanism Role Spine) |
| `MIN_CLIPS_FOR_ASSEMBLY` | `5` (`CLIP_COUNT_MIN`) | clips | Minimum clips required to run assembly |

---

## 2. Production Contract v4 — Prompts, Narration & Voice

| Constant / Helper | Value | Unit | Meaning |
|---|---|---|---|
| `DEFAULT_FLOW_MODEL` | `"Omni 1.1 Flash"` | model | Default Google Flow video engine |
| `FLOW_MODEL_QUALITY` | `"Omni 1.1 Quality"` | model | High-detail Google Flow video engine |
| `ALLOWED_FLOW_MODELS` | `["Omni 1.1 Flash", "Omni 1.1 Quality"]` | list | Permitted Google Flow engines (R5) |
| `FLOW_DEFAULT_VOICE` | `"Puck"` | voice | Exclusive male documentary narrator voice (R13) |
| `FLOW_ALLOWED_VOICES` | `("Puck",)` | tuple | Permitted voices (Aoede and female voices banned) |
| `PUCK_F0_RANGE_HZ` | `(85.0, 185.0)` | Hz | Accepted fundamental-frequency range for Puck voice verification |
| `NATIVE_FLOW_WPS` | `2.7` | words/s | Target speaking rate in native Google Flow generation |
| `EFFECTIVE_WPS` | `2.916` (`round(2.7 * 1.08, 3)`) | words/s | Effective speaking rate after `AV_SPEEDUP_FACTOR` |
| `FLOW_CLIP_TARGET_SEC_MIN` | `8.0` | s | Target minimum native clip duration |
| `FLOW_CLIP_TARGET_SEC_MAX` | `12.0` | s | Target maximum native clip duration |
| `CLIP_WORDS_MIN` | `18` | words | Minimum spoken words per clip (R2) |
| `CLIP_WORDS_MAX` | `28` | words | Maximum spoken words per clip (R2) |
| `SCRIPT_WORD_MIN` | `90` | words | Minimum total spoken words (5 clips × 18 words) |
| `SCRIPT_WORD_MAX` | `280` | words | Maximum total spoken words (10 clips × 28 words) |
| `MAX_WORDS_PER_SENTENCE` | `26` | words | Maximum words in a single spoken sentence (R15) |
| `PROMPT_SCENE_WORDS_MIN` | `50` | words | Minimum visual scene description words per clip prompt (R40-A) |
| `PROMPT_SCENE_WORDS_MAX` | `80` | words | Maximum visual scene description words per clip prompt (R40-A) |
| `FLOW_PROMPT_PREFIX` | `"Generate a 9:16 vertical video clip (video animation with spoken voiceover only, never a static image):"` | str | Mandatory opening prefix for every Flow prompt |
| `script_word_range(n_clips)` | `(n_clips * 18, n_clips * 28)` | words | Total spoken-word range for an `n_clips` script |
| `clip_roles(n_clips)` | `CLIP_ROLE_SEQUENCES[n_clips]` | tuple | Ordered Deep-Mechanism role spine for 5..10 clips (R42) |
| `pivot_clip_index(n_clips)` | `clip_roles(n_clips).index("pivot")` | index | 0-based index of the pivot clip (`2` for 5–6, `3` for 7–8, `4` for 9–10) |

---

## 3. Assembly Timing, Holds & Speech Window Detection

| Constant | Value | Unit | Meaning |
|---|---|---|---|
| `AV_SPEEDUP_FACTOR` | `1.08` | ratio | Synchronized video (`setpts`) and audio (`atempo`) speed-up (R43-A) |
| `CLIP_VISUAL_HOLD_SEC` | `0.15` | s | Post-speech visual hold on non-pre-pivot clips `1..N-1` (R43-B) |
| `CLIP_PRE_PIVOT_HOLD_SEC` | `0.30` | s | Post-speech visual hold on the clip immediately before `pivot` (R43-B) |
| `CLIP_PRE_ROLL_TRIM_SEC` | `0.40` | s | Minimum pre-roll trim on clips `2..N` when speech starts later |
| `FINAL_TAIL_SEC` | `0.20` | s | Post-speech hold on the final clip (independent conclusion ending, R19/R43-B) |
| `END_FADE_SEC` | `0.09` | s | Clean video/audio fade-out at the very end of the final clip (R43-B) |
| `MASTER_TAIL_MUTE_SEC` | `0.095` | s | Final linear mute across all 4 mixed audio layers at the end of `audio_master.wav` |
| `VOCAL_ONSET_PROTECT_SEC` | `0.22` | s | Pre-onset window before first voiced edge to protect soft `/w/` onsets (R41) |
| `VOCAL_ONSET_PAD_SEC` | `0.05` | s | Additional trim pad before `speech_start` (effective pre-speech pad = `0.27` s) |
| `PROMPT_BLEED_SYLLABLE_SEC` | `0.185` | s/syllable | Expected speech duration per syllable for prompt-bleed detection |
| `PROMPT_BLEED_MIN_EXPECTED_SEC` | `2.2` | s | Floor on expected speech duration per clip |
| `PROMPT_BLEED_DEFAULT_SYLLABLES` | `22` | syllables | Fallback syllable count when clip narration text is unavailable |
| `PROMPT_BLEED_PAUSE_ALLOWANCE_SEC` | `0.40` | s | Internal pause threshold excluded from cumulative spoken duration |
| `PROMPT_BLEED_CUTOFF_RULES` | `((1.38, 0.65), (1.65, 0.35))` | `(mult, gap_s)` | Early cut rules to truncate hallucinated post-script prompt bleed |
| `SOFT_TAIL_FLOOR_DB` | `-36.5` | dBFS | Minimum threshold for trailing quiet-syllable extension |
| `SOFT_TAIL_P95_OFFSET_DB` | `15.0` | dB | Offset below 95th-percentile RMS for soft-tail threshold |
| `SOFT_TAIL_P15_OFFSET_DB` | `1.8` | dB | Offset above 15th-percentile noise floor for soft-tail threshold |
| `SOFT_TAIL_SEARCH_SEC` | `0.95` | s | Forward search window after last voiced cluster for trailing consonants |
| `SOFT_TAIL_MAX_GAP_SEC` | `0.32` | s | Maximum continuous sub-threshold gap before ending soft-tail extension |
| `SPEECH_END_PAD_SEC` | `0.36` | s | Post-speech pad after normal sentence completion |
| `SPEECH_END_PAD_BROKE_EARLY_SEC` | `0.12` | s | Tighter post-speech pad when prompt-bleed cutoff triggered |

---

## 4. Vocal Chain & Typography (Subtitles)

| Constant | Value | Unit | Meaning |
|---|---|---|---|
| `VOCAL_BANDPASS_HZ` | `(95, 13500)` | Hz | High-pass / low-pass corner frequencies on native Puck vocal track |
| `VOCAL_EQ_BANDS` | `((180, 1.2, 2.5), (3200, 1.0, 4.0), (8500, 1.5, 2.0))` | `(Hz, Q, dB)` | 3-band parametric vocal EQ (chest warmth, consonant clarity, air) |
| `VOCAL_COMPRESSOR` | `{"threshold_db": -18, "ratio": 3.5, "attack_ms": 5, "release_ms": 60, "makeup_db": 3}` | dict | Vocal dynamics compressor settings |
| `SUBTITLE_FONT_NAME` | `"Arial Black"` | font | Primary ASS subtitle font family (R16) |
| `SUBTITLE_FONT_SIZE` | `86` | pt | Primary ASS subtitle font size |
| `SUBTITLE_OUTLINE_WIDTH` | `7.0` | px | Black outline thickness for contrast |
| `SUBTITLE_SHADOW_DEPTH` | `0.0` | px | Drop shadow depth |
| `SUBTITLE_MARGIN_V` | `440` | px | Vertical margin from bottom (`1920 - 440 = 1480` px, lower-third anchor) |
| `SUBTITLE_MAX_WORDS_PER_EVENT` | `3` | words | Maximum words per single subtitle burst (R16) |
| `SUBTITLE_MAX_LINES` | `1` | lines | Strict single-line subtitle lock (zero `\N` line breaks) |

---

## 5. Media Integrity, Dead-Air & Anti-Derivative Thresholds

| Constant / Helper | Value | Unit | Meaning |
|---|---|---|---|
| `MIN_CLIP_SIZE_BYTES` | `1_000_000` | bytes | Minimum valid size (1 MB) per native Flow MP4 clip (V5 / R37) |
| `MIN_FINAL_VIDEO_SIZE_BYTES` | `1_000_000` | bytes | Minimum valid size (1 MB) for final assembled Short |
| `FLOW_CLIP_DURATION_MIN_SEC` | `3.0` | s | Minimum valid native clip duration |
| `FLOW_CLIP_DURATION_MAX_SEC` | `15.0` | s | Maximum valid native clip duration |
| `FINAL_SHORTS_DURATION_MIN_SEC` | `24.0` | s | Minimum valid assembled Shorts duration |
| `FINAL_SHORTS_DURATION_MAX_SEC` | `105.0` | s | Maximum valid assembled Shorts duration |
| `MIN_FRAME_DIFF_THRESHOLD` | `2.0` | L1 diff | Minimum mean pixel difference across start/mid/end frames |
| `MIN_PAIR_TOP_DIFF_THRESHOLD` | `0.5` | L1 diff | Minimum upper-frame diff between consecutive sampled frames |
| `MIN_INTRA_SEGMENT_DIFF_THRESHOLD` | `0.5` | L1 diff | Minimum intra-segment motion diff (blocks static slideshows) |
| `MIN_OPTICAL_FLOW_THRESHOLD` | `0.12` | px/frame | Minimum Farneback dense optical flow magnitude |
| `MAX_PERCEPTUAL_DHASH_HAMMING_DISTANCE` | `10` | bits | 64-bit dHash distance ceiling below which clips are flagged as clones (R37) |
| `DEAD_AIR_FLOOR_SEC` | `16.50` | s | Floor on allowed cumulative non-speech time for videos `> 31.0` s |
| `DEAD_AIR_DURATION_RATIO` | `0.38` | ratio | Scaling factor for allowed non-speech time (`duration * 0.38`) |
| `DEAD_AIR_SHORT_VIDEO_SEC` | `31.0` | s | Duration boundary separating short vs multi-clip dead-air rules |
| `DEAD_AIR_SHORT_VIDEO_MAX_SEC` | `0.90` | s | Maximum cumulative internal dead air for videos `<= 31.0` s |
| `max_allowed_dead_air_sec(duration_sec)` | helper | s | Returns allowed cumulative dead air for a given duration |
| `expected_final_duration_sec(n_clips)` | helper | s | Nominal assembled duration for `n_clips` (`n * 8.0 / 1.08`, clamped to `24..105` s) |

---

## 6. Browser Automation, Concurrency & Circuit Breakers

| Constant | Value | Unit | Meaning |
|---|---|---|---|
| `DEFAULT_CDP_HOST` | `"127.0.0.1"` | host | Naver Whale remote debugging host |
| `DEFAULT_CDP_PORT` | `9222` | port | Naver Whale remote debugging port |
| `FLOW_MAX_PARALLEL_BATCH_SIZE` | `5` | tabs / workers | Hard cap on parallel subagents / Whale tabs per batch (R37 Guard 6) |
| `FLOW_MAX_RETRIES` | `2` | retries | Maximum generation trigger retries before circuit breaker trips |
| `FLOW_TRIGGER_VERIFY_TIMEOUT_SEC` | `5.0` | s | Window to verify UI entered rendering state after clicking generate |
| `FLOW_TRIGGER_POLL_INTERVAL_SEC` | `0.5` | s | DOM polling interval during trigger verification |
| `FLOW_RENDER_POLL_INTERVAL_SEC` | `10.0` | s | Polling interval while waiting for video render completion |
| `FLOW_RENDER_TIMEOUT_SEC` | `210.0` | s | Maximum wait time for a single Google Flow clip render |
| `SUBPROCESS_TIMEOUT_SEC` | `180.0` | s | Hard timeout on every `ffmpeg` / `ffprobe` subprocess invocation |
| `MAX_LOOP_ITERATIONS` | `60` | iterations | Hard safety ceiling on any polling loop |
| `ALLOW_EXTERNAL_PAID_APIS` | `False` | bool | Zero external paid API policy lock (R5) |
| `ALLOW_STATIC_IMAGE_VIDEO_FALLBACK` | `False` | bool | Anti-placeholder policy lock (no static images or fake loops) |
