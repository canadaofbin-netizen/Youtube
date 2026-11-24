# Production Constants Reference (`pipeline/config.py` 1:1 SSOT)

Canonical live values live in [`pipeline/config.py`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/config.py). Historical prose archive: [retired_constants_v4_v7_2026-11-18.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/_archive/retired_constants_v4_v7_2026-11-18.md).

## 1. Active Core Locks & SSOT Anchors
| Constant | Live Value (`pipeline/config.py`) | Notes |
|---|---|---|
| `DEFAULT_DIORAMA_STYLE_PROFILE` | `porcelain_cinematic_v7` | v7 baseline; active Shorts v8 uses `expressive_25d_v8` (`shorts_expressive_v8`) |
| `EXPRESSIVE_25D_V8_STYLE_PROFILE` | `expressive_25d_v8` | `30fps`, `61.5–88.0s` (`<=88.0s` R75), `elevenlabs_v4` Solo `Siren` (`el_siren_v4`) |
| `UNMANNED_QA_SIGNOFF_DEFAULT` | `False` | Machine auto-signoff permanently banned (`Rule R85`) |
| `R85_BRAIN_RENDER_ENGINE` | `google_flow` | `100%` Google Flow Ep #31 6-Scale Brain (`0%` Blender screen render) |
| `FLOW_PRIMARY_VIDEO_MODEL` | `Omni 1.2 Flash` | Unified single-Omni tier (`macaron_cookie`, `gemini-omni-1.2-flash`): `Ingredients` (`3s–15s`) + `Start+End` `VIDEO_FRAMES` (`3s–10s`); `Omni 1.1` / `Veo Fast/Quality` retired |
| `FLOW_ZERO_CREDIT_MODEL` | `Veo 3.1 - Lite [Lower Priority]` | `0-credit` video fallback (`4s/6s/8s`, `Start+End` supported) |
| `DEFAULT_REENACT_IMAGE_BACKEND` | `flow` | `100%` Google Flow native (`"flow"` locked; zero external paid APIs) |
| `FLOW_ZERO_CREDIT_IMAGE_MODEL` | `Nano Banana 2.1` | Zero-credit Flow Image keyframe model |
| `FLOW_ZERO_CREDIT_IMAGE_BATCH_COUNT` | `1` | 1st-pass default `x1` in Flow Image mode (`0`-retry fail-fast on `"unusual activity"`) |
| `FLOW_ZERO_CREDIT_IMAGE_RETRY_BATCH_COUNT` | `2` | CV retry & `--force` / Gate 1 rejected targeted regen `x2` |
| `FLOW_ZERO_CREDIT_IMAGE_THUMBNAIL_BATCH_COUNT` | `2` | `R65 v4` hero thumbnail keyart `x2` (1 prompt/ep) |
| `FLOW_ZERO_CREDIT_MAX_CONCURRENT_RENDERS` | `4` | Max concurrent zero-credit renders |
| `FLOW_ZERO_CREDIT_VIDEO_MAX_BATCH` | `4` | Max zero-credit video batch size |
| `REENACT_MIN_DHASH_DISTANCE` | `18` | Track A anti-derivative dHash floor (`R67`) |
| `REENACT_BRAIN_RATIO_MIN` | `0.20` | Track A minimum brain/split intercut share (`R67`) |
| `DIORAMA_V7_US_PROSODY_MODE` | `dynamic_us_v7` | Default v7 US sentence prosody mode |

## 2. Domain-Split `pipeline/config.py` Symbol Index
- **Paths & Profiles ([`config_paths.py`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/config_paths.py))**: `WORKSPACE_ROOT`, `CHANNEL_ROOT`, `PROJECTS_DIR`, `DOSSIERS_DIR`, `KNOWLEDGE_BASE_DIR`, `PERSISTENT_SHA_CACHE_MAX_ENTRIES`, `LONGFORM_DEFERRED`, `DEFAULT_SHORTS_FORMAT_PROFILE`, `SHORTS_90S_PROFILE`, `SHORTS_180S_PROFILE`, `SHORTS_90S_DURATION_MIN_SEC`, `SHORTS_90S_DURATION_TARGET_SEC`, `SHORTS_90S_DURATION_MAX_SEC`, `SHORTS_90S_WORD_COUNT_MIN`, `SHORTS_90S_WORD_COUNT_MAX`, `SHORTS_90S_SENTENCE_COUNT_MIN`, `SHORTS_90S_SENTENCE_COUNT_MAX`, `SHORTS_90S_CLIP_COUNT_MIN`, `SHORTS_90S_CLIP_COUNT_DEFAULT`, `SHORTS_90S_CLIP_COUNT_MAX`.
- **Google Flow & Credits ([`config_flow.py`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/config_flow.py))**: `FLOW_OMNI_CREDIT_COST_NO_REF`, `FLOW_OMNI_CREDIT_COST_WITH_REF`, `FLOW_AUTO_CLEANUP_ON_SUCCESS`, `FLOW_TAB_OPEN_STAGGER_SEC`, `FLOW_SUBMIT_STAGGER_SEC`, `FLOW_MAX_PARALLEL_BATCH_SIZE`.
- **QA & R65 v4 Thumbnail ([`config_qa.py`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/config_qa.py))**: `THUMBNAIL_REPORT_FILENAME`, `THUMBNAIL_CONTACT_SHEET_FILENAME`, `THUMB_CANDIDATE_SAMPLES_PER_CUT`, `THUMB_EXCLUDE_MODES`, `THUMB_EXCLUDE_OUTRO`, `THUMB_SCORE_WEIGHTS`, `THUMB_INTENT_BONUS`, `THUMB_MIN_SHARPNESS`, `THUMB_MIN_LUMA_STD`, `THUMB_MIN_CENTER_SALIENCE`, `THUMB_MIN_PAIRWISE_DIFF`, `THUMB_MIN_TEXT_CONTRAST`, `THUMB_LEGIBILITY_PREVIEW_W`, `THUMB_SAFE_Y_RANGE`, `THUMB_SAFE_MARGIN_X`, `THUMB_HOOK_MAX_WORDS`, `THUMB_HOOK_MAX_CHARS`, `THUMB_HOOK_FONT_SIZE_RANGE`, `THUMB_HOOK_STROKE_PX`, `THUMB_MIN_FILE_BYTES`, `DIORAMA_V7_REQUIRE_THUMBNAIL_BLOCK`, `R65_V4_THUMBNAIL_PROFILE`.
- **Expressive `v8` & `R68–R89` ([`config_v8.py`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/config_v8.py))**: `PROMPT_SCHEMA_VERSION_V8`, `SHORTS_EXPRESSIVE_V8_PROFILE`, `SHORTS_EXPRESSIVE_V8_DURATION_MIN_SEC`, `SHORTS_EXPRESSIVE_V8_DURATION_MAX_SEC`, `SHORTS_EXPRESSIVE_V8_WORD_COUNT_MIN`, `SHORTS_EXPRESSIVE_V8_WORD_COUNT_MAX`, `EXPRESSIVE_V8_CLIP_COUNT_MIN`, `EXPRESSIVE_V8_CLIP_COUNT_MAX`, `EXPRESSIVE_V8_CAMERA_MOVES`, `EXPRESSIVE_V8_VISUAL_GRAMMARS`, `EXPRESSIVE_V8_TRANSITION_TYPES`, `EXPRESSIVE_V8_SUBTITLE_FONT_SIZE`, `EXPRESSIVE_V8_SUBTITLE_MARGIN_V`, `EXPRESSIVE_V8_TARGET_LUFS`, `EXPRESSIVE_V8_DISSOLVE_FRAMES`, `EXPRESSIVE_V8_CORE_REVEAL_MAX_SENTENCE`, `EXPRESSIVE_V8_CORE_REVEAL_MAX_SEC`, `EXPRESSIVE_V8_OPENING_QUESTION_MAX_WORDS`, `EXPRESSIVE_V8_OPENING_EMPATHY_MAX_WORDS`, `EXPRESSIVE_V8_MAX_MYTH_FLIPS`, `EXPRESSIVE_V8_ADVISORY_PIVOT_MARKERS`, `SHORTS_EXPRESSIVE_V8_SENTENCE_WORDS_MAX`, `SHORTS_EXPRESSIVE_V8_SENTENCE_COUNT_TARGET`, `R68_TITLE_WORD_RANGE`, `R68_TITLE_MAX_CHARS`, `R68_DESCRIPTION_HASHTAG_COUNT`, `R88_FACELESS_CAST_PROFILE`, `R89_MIN_CUT_INDEX`, `R89_MIN_START_SEC`.
