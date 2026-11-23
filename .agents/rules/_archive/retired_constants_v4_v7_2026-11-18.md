# Archived Pre-Restructure `production_constants.md` Verbatim Prose (2026-11-18 — Zero-Deletion Archive)

> Canonical live values live in `pipeline/config.py`. Active compact index: `.agents/rules/production_constants.md`.

# Production Constants (`pipeline/config.py` 1:1 SSOT)

Master Index: [AGENTS.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/AGENTS.md) | Code SSOT: [pipeline/config.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/config.py)

## 1. Video & Clip Specifications
| Constant | Value | Rule / Note |
|---|---|---|
| `VIDEO_WIDTH` | `1080` | Vertical Shorts output width |
| `VIDEO_HEIGHT` | `1920` | Vertical Shorts output height |
| `VIDEO_FPS` | `30` | Output frame rate |
| `VIDEO_MAX_DURATION_SEC` | `105.0` | Hard ceiling on final assembled |
| `CLIP_COUNT_MIN` | `5` | Minimum native Google Flow clips |
| `CLIP_COUNT_MAX` | `10` | Maximum native Google Flow clips |
| `DEFAULT_CLIP_COUNT` | `10` | Default clip count |
| `MIN_CLIPS_FOR_ASSEMBLY` | `5` (`CLIP_COUNT_MIN`) | Minimum clips required to run |

## 2. Production Contract v4 — Prompts, Narration & Voice
| Constant | Value | Rule / Note |
|---|---|---|
| `DEFAULT_FLOW_MODEL` | `"Omni 1.2 Flash"` | Default Google Flow primary video |
| `FLOW_MODEL_QUALITY` | `"Omni 1.2 Flash"` | High-detail Google Flow video engine |
| `ALLOWED_FLOW_MODELS` | `["Omni 1.2 Flash", "Omni 1.1 Flash", "Veo 3.1 - Lite [Lower Priority]"]` | Permitted Google Flow Dual-Tier [R5] |
| `FLOW_DEFAULT_VOICE` | `"Puck"` | Exclusive male documentary [R13] |
| `FLOW_ALLOWED_VOICES` | `("Puck",)` | Permitted voices |
| `FLOW_VOICE_PROMPT_DESCRIPTOR` | `"Consistent deep male baritone documentary narrator"` | Voice descriptor injected in the [R13,R40-A] |
| `PUCK_F0_RANGE_HZ` | `(85.0, 185.0)` | Accepted fundamental-frequency |
| `NATIVE_FLOW_WPS` | `2.7` | Target speaking rate in native |
| `EFFECTIVE_WPS` | `2.7` (`round(2.7 * 1.00, 3)`) | Effective speaking rate after `AV_SPEEDUP_FACTOR` |
| `FLOW_ACTIVE_VIDEO_MODEL` / `FLOW_PRIMARY_VIDEO_MODEL` | `"Omni 1.2 Flash"` | Primary Flow engine when AI credits > 0 (`macaron_cookie`; secondary `Omni 1.1 Flash` `abra`) |
| `FLOW_ZERO_CREDIT_MODEL` | `"Veo 3.1 - Lite [Lower Priority]"` | Automatic fallback engine when `veo_3_1_lite_low_priority` |
| `FLOW_ENGINE_MODES` / `DEFAULT_FLOW_ENGINE_MODE` | `("auto", "omni", "zero-credit")` / `"auto"` | Credit-aware Dual-Tier engine `R5` [R5] |
| `FLOW_VIDEO_MODEL_PROFILES` | Omni 1.2 / 1.1 Flash: 4s / 6s / 8s / 10s (`max_sec=10`, `max_sec_with_ingredient=8`) · Veo 3.1 Lite LP: 4s / 6s / 8s (`0 credits`) | Verified Flow settings-pane profiles |
| `FLOW_BANNED_VIDEO_MODEL_MARKERS` / `FLOW_ZERO_CREDIT_TEXT` | `("Veo 2",)` / `"Generating will use 0 credits"` | Banned legacy model marker & UI |
| `FLOW_ZERO_CREDIT_IMAGE_MODEL` / `FLOW_ZERO_CREDIT_IMAGE_FAMILY_ID` / `FLOW_ZERO_CREDIT_IMAGE_BATCH_COUNT` | `"Nano Banana 2.1"` / `"beluga_display"` / `4` | Native Google Flow engine `Image` `x4` |
| `FLOW_ZERO_CREDIT_MAX_CONCURRENT_RENDERS` / `FLOW_ZERO_CREDIT_VIDEO_MAX_BATCH` | `4` / `4` | Optimal concurrent video render `x1` `x4` |
| `FLOW_ZERO_CREDIT_SAFE_PARALLEL_TABS` / `FLOW_ZERO_CREDIT_SUBMIT_JITTER_SEC` / `FLOW_ZERO_CREDIT_PENALTY_QUIET_SEC` / `FLOW_ZERO_CREDIT_RECOVERY_STREAK` | `2` / `(14.0, 22.0)` / `75.0` / `3` | Adaptive 0-credit anti-cooldown governor defaults [R5] |
| `REENACT_IMAGE_BACKENDS` / `DEFAULT_REENACT_IMAGE_BACKEND` | `("flow",)` / `"flow"` | Reference/reenactment image `x4` |
| `FLOW_OMNI_CREDIT_COST_NO_REF` / `FLOW_OMNI_CREDIT_COST_WITH_REF` / `FLOW_AUTO_CLEANUP_ON_SUCCESS` | `24` / `24` / `False` | Omni 1.2 Flash credit reservation costs & room preservation (`False` = never delete `AAB_<project_id>` rooms) [R5] |
| `FLOW_TAB_OPEN_STAGGER_SEC` / `FLOW_TAB_OPEN_COOLDOWN_STAGGER_SEC` / `FLOW_SUBMIT_STAGGER_SEC` / `FLOW_SUBMIT_COOLDOWN_STAGGER_SEC` | `2.5` / `12.0` / `3.0` / `9.5` | Normal vs post-cooldown shard tab/submit staggers (`<30m` target) |
| `PERSISTENT_SHA_CACHE_MAX_ENTRIES` / `UNMANNED_QA_SIGNOFF_DEFAULT` | `8192` / `False` | Persistent SHA-256 LRU cap & R85 VLM/human semantic review requirement (`False` = machine sign-off forbidden) [R85] |
| `FLOW_CLIP_DURATION_TARGET` | `"10s"` | Omni default |
| `FLOW_ALLOWED_DURATION_TARGETS` | `("4s", "6s", "8s", "10s")` | From the active model profile |
| `FLOW_SHORT_CLIP_MAX_WORDS` | `19` | Max words for dynamic clip selection |
| `FLOW_SHORT_CLIP_MAX_SYLLABLES` | `32` | Max syllables for dynamic clip |
| `FLOW_CLIP_SAFE_MAX_SYLLABLES` | `48` | Syllable ceiling above which |
| `FLOW_CLIP_TARGET_SEC_MIN` | `8.0` | Target minimum native clip duration |
| `FLOW_CLIP_TARGET_SEC_MAX` | `12.0` | Target maximum native clip duration |
| `CLIP_WORDS_MIN` | `18` | Minimum spoken words per clip [R2] |
| `CLIP_WORDS_MAX` | `28` | Maximum spoken words per clip [R2] |
| `SCRIPT_WORD_MIN` | `90` | Minimum total spoken words |
| `SCRIPT_WORD_MAX` | `280` | Maximum total spoken words |
| `MAX_WORDS_PER_SENTENCE` | `26` | Maximum words in a single spoken [R15] |
| `PROMPT_SCENE_WORDS_MIN` | `50` | Minimum visual scene description [R40-A] |
| `PROMPT_SCENE_WORDS_MAX` | `80` | Maximum visual scene description [R40-A] |
| `FLOW_PROMPT_PREFIX` | `"Generate a 9:16 vertical video clip (video animation with spoken voiceover only, never a static image):"` | Mandatory opening prefix for |
| `script_word_range(n_clips)` | `(n_clips * 18, n_clips * 28)` | Total spoken-word range for an `n_clips` |
| `clip_roles(n_clips)` | `CLIP_ROLE_SEQUENCES[n_clips]` | Ordered Deep-Mechanism role spine [R42] |
| `pivot_clip_index(n_clips)` | `clip_roles(n_clips).index("pivot")` | 0-based index of the pivot clip |

## 2-B. Prompt System v5 — Modes, Acting, Plain Language, Voice, Longform
| Constant | Value | Rule / Note |
|---|---|---|
| `PROMPT_SCHEMA_VERSION_V5` | `5` | Schema version written for v5 |
| `PROMPT_SCENE_WORDS_MAX_V5` | `95` | Max scene words in v5 prompts `FLOW_MOTION_STYLE_V5` |
| `FLOW_ASPECT_SHORTS` / `FLOW_ASPECT_LONGFORM` | `"9:16"` / `"16:9"` | [R50] |
| `FLOW_ASPECT_LABELS` | `{"9:16": "9:16 vertical", "16:9": "16:9 horizontal"}` | Prefix wording per aspect |
| `FLOW_MOTION_STYLE_V5` | `"Articulated matte-white porcelain figures move with fluid, natural human motion; key action stays centred in frame."` | Appended after every v5 scene [R47,R50] |
| `FLOW_VOICE_PROMPT_DESCRIPTOR_V5` | `"Same calm male documentary narrator in every clip, warm mid-low baritone, steady even pitch, relaxed measured pace, neutral American accent, no dramatic pitch swings"` | v5 clause [R13,R49] |
| `FLOW_LEGACY_VOICE_LABELS` | v4 descriptors | Still accepted by `validate_flow_prompts` |
| `VISUAL_MODES` | `("BEHAVIORAL_PSYCH", "HYBRID", "NEURO_BIOLOGY")` | R45 [R45] |
| `BRAIN_SETTINGS` | `("drill_down", "brain_void")` | Settings counted as brain clips |
| `ALLOWED_SETTINGS_V5` | `("real_env", "drill_down", "brain_void", "pull_out")` | Valid values |
| `MAX_BRAIN_CLIPS_BY_MODE` | `{BEHAVIORAL_PSYCH: 0, HYBRID: 2, NEURO_BIOLOGY: 4}` | R45 [R45] |
| `MAX_ANATOMY_TERMS_BY_MODE` | `{BEHAVIORAL_PSYCH: 1, HYBRID: 2, NEURO_BIOLOGY: 4}` | Distinct region names per script [R15] |
| `MODE_ROLE_SETTINGS` | HYBRID: pivot `drill_down`, mechanism/step1 `brain_void`, step2 `pull_out`, rest `real_env`; NEURO: crisis `drill_down`, pivot/mechanism/step1/step2 `brain_void`, step3 `pull_out`, rest `real_env`; BEHAVIORAL: all `real_env` | Default setting per role [R45] |
| `ICONIC_SCENE_MAX_CLIP` | `2` | Iconic scene appears in clip 1..2 [R46] |
| `READABILITY_SCRIPT_FK_MAX` | `8.0` | Flesch-Kincaid, whole script |
| `READABILITY_CLIP_FK_MAX` | `11.0` | Flesch-Kincaid, any clip |
| `JARGON_TERMS_MAX` | `1` | Non-anatomy technical terms per |
| `SECOND_PERSON_CLIPS_MIN` | `1` | Clips that speak to "you / your" |
| `RESEARCH_DOSSIERS_DIRNAME` / `DOSSIERS_DIR` | `"research_dossiers"` / `CHANNEL_ROOT / "research_dossiers"` | [R44] |
| `ASSET_LIBRARY_DIRNAME` | `"asset_library"` | [R50] |
| `LONGFORM_TARGET_MIN_SEC` / `LONGFORM_TARGET_MAX_SEC` | `480` / `900` | Longform built from proven Shorts |
| `REF_IMAGES_DIRNAME` | `"reference_images"` | & [R51] |
| `MIN_REF_IMAGES_PER_PROJECT` | `6` | Minimum reference images per project |
| `MIN_REF_IMAGE_SIZE_BYTES` | `30_000` | Minimum file size per reference |
| `REF_IMAGE_MIN_WIDTH_SHORTS` / `REF_IMAGE_MIN_HEIGHT_SHORTS` | `720` / `1280` | Minimum resolution for reference |
| `REF_IMAGE_LUMA_MIN` / `REF_IMAGE_LUMA_MAX` | `70.0` / `242.0` | R14-A bright high-key daylight [R14-A] |
| `REF_IMAGE_CONTRAST_STD_MIN` | `22.0` | Minimum dynamic contrast standard |
| `REF_IMAGE_SHARPNESS_MIN` | `45.0` | Minimum focus sharpness threshold |
| `REF_IMAGE_EDGE_DENSITY_MIN` | `0.015` | Minimum Canny structural edge |
| `REF_IMAGE_PORCELAIN_RATIO_MIN` | `0.04` | Minimum matte-white porcelain |
| `REF_IMAGE_HUMAN_SKIN_MAX` | `0.12` | Maximum allowed human flesh-tone |
| `REF_IMAGE_CROSS_HIST_CORR_MIN` | `0.55` | Minimum HSV palette correlation |
| `REF_IMAGE_CROSS_LUMA_SPREAD_MAX` | `55.0` | Maximum luminance spread across |
| `REF_IMAGE_CAST_CHROMA_DRIFT_MAX` | `16.0` | Maximum chrominance drift across |
| `REF_IMAGE_CLIP_CONTINUITY_CORR_MIN` | `0.55` | Minimum HSV correlation between |
| `REF_IMAGE_MAX_REGEN_ROUNDS` | `3` | Max automatic regeneration rounds |
| `REF_IMAGE_MIN_DHASH_DISTANCE` | `6` | Q10 duplicate threshold between [Q10] |
| `REF_IMAGE_BIOLUM_MIN` | `0.005` | Q6 minimum 4-point colour-code [Q6] |
| `REF_IMAGE_SOURCES_PRE_GENERATION` | `("flow_image_generation",)` | Provenance values that count for `pre_generation_ready` |
| `REF_IMAGE_SOURCE_EXTRACTED` | `"extracted_from_clip"` | Audit-only frames cut out of |
| `SCENE_BLUEPRINT_FILENAME` | `"scene_blueprint.json"` | R52 blueprint [R52] |
| `GENERATION_PACKETS_DIRNAME` | `"generation_packets"` | R52 per-clip packets [R52] |
| `GENERATION_BACKENDS` | `("flow", "gemini_app")` | Clip generators |
| `VOICE_SOURCES` / `DEFAULT_VOICE_SOURCE` | `("tts", "native")` / `"tts"` | tts = am_fenrir voiceover in Gear |
| `CLIP_MAX_RENDER_SEC` | `10` | Omni 1.1 Flash ceiling |
| `CLIP_MAX_RENDER_SEC_WITH_REFERENCE` | `8` | Render ceiling when a reference |
| `GEMINI_APP_MAX_RENDER_SEC` | `8` | Legacy Gemini app render length [R5] |
| `TIMED_BEAT_WINDOWS` | `((0, 3), (3, 6), (6, 8))` | action / prop change / reaction |
| `BLUEPRINT_MIN_EVIDENCE_ICONIC` | `1` | timecode evidence required for |
| `DOSSIER_MIN_SOURCES` | `6` | R44-D depth standard [R44-D] |
| `DOSSIER_MIN_FOLLOWUP_SOURCES` | `2` | replication / follow-up / review |
| `DOSSIER_MIN_CORE_FACTS` | `8` | entries |
| `DOSSIER_MIN_MEDIA` | `2` | media refs |
| `DOSSIER_MIN_ANALYZED_MEDIA` | `1` | media analysed on disk |
| `DOSSIER_MIN_KEYFRAMES` | `8` | keyframes per analysed media |
| `DOSSIER_MIN_MEDIA_TIMECODES` | `2` | timecoded shot notes per media |
| `DOSSIER_MIN_STORY_CHARS` | `6000` | master story length |
| `DOSSIER_MIN_ICONIC_POSITIONS` | `2` | who / where / facing entries |
| `DOSSIER_MIN_ICONIC_PROPS` | `2` | props with period_detail + |

## 2-C. Prompt & Assembly System v6 — Neuro-Diorama 3-Minute Long-Short (R56–R61, 2026-10-26)
| Constant | Value | Rule / Note |
|---|---|---|
| `PRODUCTION_PROFILES` | `("classic_v5", "neuro_diorama")` | Supported channel production |
| `DEFAULT_PRODUCTION_PROFILE` | `"neuro_diorama"` | Default profile for new 3-minute |
| `PROMPT_SCHEMA_VERSION_V6` | `6` | Schema version for plans / prompt `neuro_diorama` |
| `DIORAMA_ZERO_FLESH_LOCK` | `True` | Zero human skin, eyes, faces [R56] |
| `DIORAMA_ALLOW_CRYSTAL_SPECIMEN` | `True` | Allows pedestal-mounted head bust [R56] |
| `DIORAMA_CRYSTAL_SPECIMEN_MAX_RATIO` | `0.20` | Ceiling on crystal |
| `DIORAMA_BACKDROP_STYLE` / `DIORAMA_LIGHTING_STYLE` | `"deep midnight-navy studio void"` / `"cinematic chiaroscuro rim lighting"` | Channel-signature dark `RGB_DEEP_NAVY` `neuro_diorama` [R56] |
| `DIORAMA_BRAIN_RENDER_MODES` | `("matte_white_cortical_sulcal_glow", "translucent_smoked_glass_subcortical_xray")` | 2-mode isolated dark-void 3D [R56] |
| `DIORAMA_VISUAL_GRAMMARS` | `("arch_cutaway_diorama", "kinetic_trace_automata", "recurring_gauge_motif", "tactile_token_grid", "literal_analogy_cutaway", "arch_brain_maquette", "frosted_crystal_specimen")` | Permitted visual grammars in `neuro_diorama` [R56,R57-V] |
| `DIORAMA_CAMERA_MOVES` | `("smooth_tilt_up", "smooth_tilt_down", "horizontal_tracking_pan", "isometric_push_in", "locked_macro_gauge", "dynamic_dolly_rush_in", "orbital_3d_arc_sweep", "crane_swoop_dive", "low_angle_chase_track", "vertical_rocket_ascent", "fpv_trench_passthrough", "pullback_parallax_reveal")` | Permitted single-axis smooth & `neuro_diorama` [R56] |
| `DEFAULT_DIORAMA_CAMERA_PROFILE` / `DIORAMA_DYNAMIC_3D_CAMERA_MOVES` | `"dynamic_3d_cinema_rig"` / `("dynamic_dolly_rush_in", "orbital_3d_arc_sweep", "crane_swoop_dive", "low_angle_chase_track", "vertical_rocket_ascent", "fpv_trench_passthrough", "pullback_parallax_reveal")` | Default Dynamic 3D Cinema Camera `neuro_diorama` [R56] |
| `DIORAMA_MOTIF_APPEARANCES_MIN` / `DIORAMA_MOTIF_APPEARANCES_MAX` | `4` / `8` | Recurring analog gauge prop [R56] |
| `DIORAMA_SCENE_WORDS_MIN` / `DIORAMA_SCENE_WORDS_MAX` | `45` / `115` | Visual scene word bounds per Flow `neuro_diorama` |
| `DIORAMA_ACT_COUNT` | `6` | 6-Act Neuro-Documentary narrative [R57] |
| `DIORAMA_SENTENCE_COUNT_MIN` / `DIORAMA_SENTENCE_COUNT_MAX` | `48` / `58` | High-density US English [R57] |
| `DIORAMA_SENTENCE_WORDS_MAX` / `DIORAMA_V7_SENTENCE_WORDS_MAX` / `DIORAMA_US_SENTENCE_WORDS_MAX` | `15` / `18` / `13` | Max words in any single sentence `neuro_diorama` `dynamic_us_v7` [R57-C] |
| `DIORAMA_WORD_COUNT_MIN` / `DIORAMA_WORD_COUNT_MAX` / `DIORAMA_US_WORD_COUNT_MAX` | `430` / `505` / `470` | Total spoken US English word budget `dynamic_rush_v7` `dynamic_us_v7` [R57] |
| `DIORAMA_V7_MAX_FK_GRADE` / `DIORAMA_ADJACENT_OPENER_WINDOW` / `DIORAMA_MAX_4GRAM_JACCARD` | `5.5` / `4` / `0.08` | US ear-first Flesch-Kincaid grade |
| `DIORAMA_COLD_OPEN_S3_BANK` / `DIORAMA_CRISIS_BEAT_BANK` / `DIORAMA_MECHANISM_PIVOT_BANK` / `DIORAMA_EUREKA_REVEAL_BANK` / `DIORAMA_TAKEAWAY_BRIDGE_BANK` / `DIORAMA_MIDPOINT_REHOOK_BANK` | `12` / `12` / `12` / `12` / `12` / `8` phrases | Rotating US Anti-Clone structural [R57-H2,R63-P] |
| `DESCRIPTION_EDITORIAL_TEMPLATES` / `AI_DISCLOSURE_SENTENCE` / `MAX_DAILY_SUBSCRIBER_NOTIFICATIONS` / `PRE_R66_FROZEN_PROJECT_PREFIXES` | `("clinical_brief", "experiment_chronicle", "myth_vs_mechanism", "everyday_neurobiology")` / R4 AI disclosure sentence / `3` / `diorama_01..07 + gage_* + psych_*` | 4-layout editorial description `publish.py` `R30` [R4,R30,R66] |
| `DIORAMA_BANNED_SLOGAN_OPENERS` / `DIORAMA_BANNED_WEAK_HOOK_PREFIXES` / `DIORAMA_REQUIRE_SIGNATURE_HOOKS` | `("university brain science, made simple", ...)` / `("imagine ", "picture this", "have you ever ", "what if ", "suppose ")` / `True` | Generic channel-slogan & weak `R57` [R57,R57-H,R24,R26] |
| `DIORAMA_V7_REQUIRE_COLD_OPEN` / `DIORAMA_V7_COLD_OPEN_S1_MAX_WORDS` / `DIORAMA_V7_COLD_OPEN_S2_MAX_WORDS` / `DIORAMA_V7_COLD_OPEN_S2_PREFIXES` / `DIORAMA_V7_COLD_OPEN_CASE_STAMP_PREFIX` | `True` / `18` / `12` / `("yet ", "but ", "and yet ", "still ", "meanwhile ")` / `"this is the true story of "` | R57-H2 Schema v7 3-sentence `validate_cold_open_v7` `DIORAMA_COLD_OPEN_S3_BANK` [R57-H2] |
| `DIORAMA_BANNED_AI_CLICHES` / `DIORAMA_BANNED_SEMINAR_TRANSITIONS` | `("delve into", "let's unpack", "underscore", "pivotal", "paramount", "tapestry", "furthermore", "moreover", "consequently", ...)` / `("moving on to", "this paper looks at", "the main region here is", "to wrap up and bring everything together", ...)` | YouTube Natural Script ear-first [R57-C] |
| `DIORAMA_DURATION_MIN_SEC` / `DIORAMA_DURATION_TARGET_SEC` / `DIORAMA_DURATION_MAX_SEC` | `140.0` / `158.0` / `179.0` | Target brisk Long-Short duration [R57] |
| `SHORTS_HARD_CEILING_SEC` / `SHORTS_HARD_CEILING_FRAMES` | `179.0` / `5370` | Hard mux ceiling at preventing [R57] |
| `DIORAMA_NUMBER_ANALOGY_MAX_SENTENCE_GAP` | `1` | Max sentence distance from a core [R57] |
| `DIORAMA_CLIP_COUNT_MIN` / `DIORAMA_CLIP_COUNT_DEFAULT` / `DIORAMA_CLIP_COUNT_MAX` | `20` / `48` / `240` | 1:1 Zero-Reuse Flow base motion [R58,R66] |
| `DIORAMA_MAX_CLIP_REUSE` / `DIORAMA_SHARD_MAX_CLIPS` | `1` / `14` | Strict reuse lock and max clips [R58] |
| `DIORAMA_CLIP_RENDER_SEC` | `8` | Render duration per base Flow clip |
| `DIORAMA_SLICE_WINDOWS_SEC` | `((0.20, 2.45), (2.60, 4.85), (5.00, 7.25))` | Legacy 3-window intra-clip slices [R58] |
| `DIORAMA_SLICE_CROPS` | `(1.00, 1.12, 1.22)` | Legacy progressive framing |
| `DIORAMA_TARGET_CUT_MIN` / `DIORAMA_TARGET_CUT_MAX` / `PORCELAIN_V7_TARGET_CLIP_MIN` / `PORCELAIN_V7_TARGET_CLIP_MAX` / `PORCELAIN_V7_MAX_HOLD_SENTENCES` / `PORCELAIN_V7_LITERAL_ANALOGY_MAX_CLIPS` | `44` / `110` / `45` / `52` / `2` / `2` | Assembled shot range `porcelain_cinematic_v7` [R58,R66] |
| `DIORAMA_MIN_CUT_DURATION_SEC` / `DIORAMA_VISUAL_PLAYBACK_SPEED` / `DIORAMA_ENTRY_SPEED_RAMP` | `1.30` / `1.12` / `True` | Gear-1 montage floor , snappy [R58] |
| `DIORAMA_ENTRY_RAMP_START_SPEED` / `DIORAMA_ENTRY_RAMP_MAIN_SPEED` | `1.26` / `1.10` | Entry speed-ramp peak and main [R58] |
| `DIORAMA_ACT5_MONTAGE_CUT_MIN_SEC` / `DIORAMA_ACT5_MONTAGE_CUT_MAX_SEC` | `0.65` / `1.10` | Rhythmic cut window during the |
| `DIORAMA_TTS_ENGINE` / `DIORAMA_TTS_RATE` / `DIORAMA_TTS_PITCH` | `"eleven_v4"` / `"+32%"` / `"+14Hz"` | Sole ElevenLabs `eleven_v4` engine & legacy rate markers [R59,R63] |
| `DIORAMA_MIN_CONVERSATIONAL_QUESTIONS` | `4` | Minimum conversational questions [R57,R59] |
| `DIORAMA_SPEECH_PAUSE_SEC` / `DIORAMA_ACT_BOUNDARY_PAUSE_SEC` | `0.14` / `0.24` | Snappy inter-sentence breath gap [R59] |
| `DIORAMA_PAUSE_TUNE_RANGE_SEC` | `(0.10, 0.32)` | Breath-gap auto-fit range to land |
| `DIORAMA_ATEMPO_FIT_RANGE` | `(0.95, 1.04)` | Bounded pitch-preserving `atempo` `asetrate` |
| `DIORAMA_ACTIVE_SPEECH_RATIO_MIN` | `0.84` | Minimum active voiced speech [R59] |
| `DIORAMA_BGM_BPM` / `DIORAMA_BGM_DUCK_DB` | `88` / `-24.0` | Minimal documentary pulse BGM [R59] |
| `DIORAMA_OUTRO_SWELL_SEC` / `DIORAMA_OUTRO_SWELL_GAIN_DB` | `2.2` / `8.0` | Final sky tilt-up title card hold |
| `DIORAMA_TARGET_LUFS` / `DIORAMA_MAX_LRA_LU` | `-15.5` / `4.0` | Integrated loudness and [R59] |
| `DIORAMA_SUBTITLE_FONT_SIZE` / `DIORAMA_SUBTITLE_OUTLINE_WIDTH` / `DIORAMA_SUBTITLE_MARGIN_V` | `76` / `4.5` / `650` | Single-line pure-white subtitle [R59] |
| `DIORAMA_SUBTITLE_MAX_WORDS` / `DIORAMA_SUBTITLE_HIGHLIGHT_GOLD` | `3` / `False` | Strict word pure hard-cut [R59] |
| `DIORAMA_CALLOUT_FONT_SIZE` / `DIORAMA_CALLOUT_MARGIN_V` / `DIORAMA_CALLOUT_COUNT_RANGE` | `64` / `1520` / `(4, 8)` | Clean top-space US English [R59] |
| `DIORAMA_OUTRO_TITLE_FONT_SIZE` / `DIORAMA_OUTRO_TITLE_MARGIN_V` | `84` / `1140` | Upper-sky 2-line uppercase [R59] |
| `TITLE_MAX_CHARS_DIORAMA` | `95` | Max character length for 2-Clause [R60] |
| `is_diorama_profile(x)` / `is_diorama_v7_plan(x)` / `is_porcelain_v7_plan(x)` / `resolve_diorama_v7_style_profile(x)` / `resolve_shorts_format_profile(...)` / `clip_count_range_for_profile(p)` / `shorts_duration_range_for_profile(p)` / `word_count_range_for_profile(p)` / `sentence_count_range_for_profile(p)` | helpers | Profile-aware contract resolvers in `pipeline/config.py` |
| `PROMPT_SCHEMA_VERSION_V7` / `PORCELAIN_V7_STYLE_PROFILE` / `DIORAMA_V7_STYLE_PROFILE` / `DIORAMA_V7_STYLE_PROFILES` / `DEFAULT_DIORAMA_STYLE_PROFILE` | `7` / `"porcelain_cinematic_v7"` / `"lowpoly_pastel_v7"` / `("lowpoly_pastel_v7", "porcelain_cinematic_v7")` / `"porcelain_cinematic_v7"` | Schema v7 style profiles: ** `porcelain_cinematic_v7` `lowpoly_pastel_v7` [R66,R63] |
| `PORCELAIN_V7_WORLD_STYLE` / `PORCELAIN_V7_CAST_STYLE` / `PORCELAIN_V7_OPTICS_LOCK` | `"photorealistic bright high-key documentary studio world"` / `"clothed articulated matte-white porcelain figures with smooth featureless solid matte-white egg-shaped oval heads"` / `"crisp cinema prime lens clarity with soft natural studio daylight and subtle rim lighting"` | Photorealistic high-key solid [R66,R67] |
| `DOSSIER_SCHEMA_VERSION` / `DOSSIER_NEURO_MODERN_MIN_YEAR` / `FROZEN_PRE_SCHEMA_V2_PROJECT_PREFIXES` | `2` / `2015` / `(PRE_R66_FROZEN_PROJECT_PREFIXES + ("reenact_01_ainsworth_strange_situation",))` | 3-Layer Formula research dossier [R44] |
| `PORCELAIN_V7_LUMA_RANGE` / `PORCELAIN_V7_DARK_VOID_RATIO_MAX` / `PORCELAIN_V7_SATURATION_RANGE` | `(88.0, 226.0)` / `0.24` / `(8.0, 115.0)` | High-key native-color episode [R66] |
| `PORCELAIN_V7_NEON_GREEN_SPILL_MAX` / `PORCELAIN_V7_BRAIN_MARGIN_SAT_MAX` / `PORCELAIN_V7_HUMAN_SKIN_MAX` | `0.015` / `48.0` / `0.14` | Hard CV caps blocking fluorescent [R66] |
| `PORCELAIN_V7_BRAIN_RENDER_MODES` / `PORCELAIN_V7_VISUAL_GRAMMARS` / `ALL_DIORAMA_V7_VISUAL_GRAMMARS` | 4 brain modes / 6 porcelain grammars / 12 v7 grammars | 4-mode Contained Living 4-Color `cortical_vascular_whole` `sagittal_coronal_cutaway` `frosted_glass_subcortical_xray` `bounded_micro_channel` `porcelain_fullbleed_world` `porcelain_hands_closeup` `porcelain_pov_hands` `porcelain_cutaway_section` `porcelain_literal_analogy` `porcelain_living_brain` [R66] |
| `DIORAMA_V7_WORLD_STYLE` / `DIORAMA_V7_SHADER_STYLE` / `DIORAMA_V7_OPTICS_LOCK` | `"full-bleed bright diffused pastel daylight world"` / `"untextured flat-shaded matte low-poly 3D"` / `"crisp infinite deep focus from foreground to horizon"` | Legacy full-bleed low-poly world `lowpoly_pastel_v7` [R63] |
| `DIORAMA_V7_LUMA_RANGE` / `DIORAMA_V7_DARK_VOID_RATIO_MAX` / `DIORAMA_V7_SATURATION_RANGE` | `(105.0, 168.0)` / `0.14` / `(24.0, 52.0)` | Legacy episode mean luma window `lowpoly_pastel_v7` [R63] |
| `DIORAMA_V7_CUTAWAY_MAX_RATIO` / `DIORAMA_V7_BRAIN_RENDER_MODES` | `0.15` / `("matte_pastel_cortical_model", "matte_pastel_sagittal_cutaway")` | Cross-section cutaway ceiling and [R63] |
| `DIORAMA_V7_VISUAL_GRAMMARS` / `DIORAMA_V7_CAMERA_MOVES` | 6 grammars / 7 camera moves | 3-tier face-excluding low-poly `lowpoly_hands_closeup` `lowpoly_pov_hands` `lowpoly_fullbleed_world` `lowpoly_cutaway_section` `lowpoly_literal_analogy` `lowpoly_matte_brain` [R63,R66] |
| `DIORAMA_V7_LOCKED_CAMERA_MIN_RATIO` / `DIORAMA_V7_ZOOM_CAMERA_MAX_RATIO` | `0.35` / `0.30` | Minimum tripod lock-off ratio and [R63] |
| `DIORAMA_V7_VIDEO_FPS` / `DIORAMA_V7_VISUAL_PLAYBACK_SPEED` / `DIORAMA_V7_DURATION_MIN_SEC` / `SHORTS_HARD_CEILING_FRAMES_V7` | `24` / `1.00` / `140.0` / `4296` | Native Flow timeline [R63] |
| `DIORAMA_V7_RAPID_CUT_MIN_SEC` / `DIORAMA_V7_MID_ACT_MAX_CUT_SEC` / `DIORAMA_V7_LONG_TAKE_MAX_SEC` / `DIORAMA_V7_CUT_CV_MIN` | `0.68` / `4.60` / `6.50` / `0.36` | Legacy cut rhythm bounds `lowpoly_pastel_v7` [R63] |
| `PORCELAIN_V7_MIN_CUT_SEC` / `PORCELAIN_V7_MID_ACT_MAX_CUT_SEC` / `PORCELAIN_V7_LONG_TAKE_MAX_SEC` / `PORCELAIN_V7_AVG_CUT_MIN_SEC` / `PORCELAIN_V7_AVG_CUT_MAX_SEC` / `PORCELAIN_V7_CUT_CV_MIN` | `1.80` / `4.30` / `4.50` / `2.85` / `3.35` / `0.15` | Active balanced documentary `porcelain_cinematic_v7` [R66] |
| `DIORAMA_V7_SPLIT_MODE` / `DIORAMA_V7_SPLIT_DIVIDER_PX` | `"split_hstack"` / `6` | Left/Right vertical split-screen [R63] |
| `DIORAMA_V7_TTS_RATE` / `DIORAMA_V7_TTS_PITCH` / `DIORAMA_V7_TTS_VOLUME` / `DIORAMA_V7_WPM_MIN` / `DIORAMA_V7_WPM_MAX` / `DIORAMA_V7_ACTIVE_VOICED_RMS_RATIO_MIN` | `"+8%"` / `"+14Hz"` / `"-10%"` / `135.0` / `212.0` / `0.80` | Unified WPM & active voiced RMS floor [R63] |
| `DIORAMA_VOICE_PRESETS` / `HISTORICAL_LEGACY_VOICE_PRESET_IDS` / `DEFAULT_DIORAMA_VOICE_PRESET` / `DEFAULT_REENACTMENT_VOICE_PRESET` / `STORYTELLER_VOCAL_FILTER_FEMALE` / `resolve_diorama_voice_preset(...)` | `5` presets (`elevenlabs_v4`, `el_researcher_v4`, `el_minicortex_v4`, `elevenlabs_v4_male`, `elevenlabs_v4_female`) / `8` archive IDs / `"elevenlabs_v4"` / `"elevenlabs_v4"` / `95Hz HPF + 2.85kHz presence + 7.2kHz sibilance trim` | Sole fail-fast ElevenLabs `eleven_v4` 3-member Repertory Cast (`Roger` narrator, `Hope` researcher, `Laura` Mini-Cortex) |
| `DIORAMA_V7_PROSODY_MODES` / `DIORAMA_V7_PROSODY_MODE` / `DIORAMA_V7_US_PROSODY_MODE` | `("uniform_108x", "uniform_110x", "dynamic_rush_v7", "dynamic_us_v7")` / `"dynamic_us_v7"` / `"dynamic_us_v7"` | Sentence-level prosody profiles `dynamic_us_v7` `dynamic_rush_v7` |
| `DIORAMA_V7_PROSODY_BASE_RATE` / `DIORAMA_V7_US_PROSODY_BASE_RATE` / `DIORAMA_V7_PROSODY_UNIFORM_110_RATE` | `"+8%"` / `"+7%"` / `"+10%"` | Base prosody rate tags `dynamic_rush_v7` `dynamic_us_v7` `uniform_110x` |
| `DIORAMA_V7_PROSODY_GEAR_RATES` / `DIORAMA_V7_US_PROSODY_GEAR_RATES` | rush `"+12%"` / stamp `"+8%"` / brisk `"+15%"` · US: rush `"+10%"` / stamp `"+4%"` / brisk `"+7%"` | Per-gear prosody rate tags `dynamic_rush_v7` `dynamic_us_v7` |
| `DIORAMA_V7_PROSODY_SPLICE_FADE_SEC` | `0.014` | Smooth raised-cosine fade at |
| `DIORAMA_V7_MASTER_DEESSER` | `"deesser=i=0.48:m=0.5:f=0.5:s=o"` | Calibrated Schema v7 master |
| `DIORAMA_MUX_TRUE_PEAK_TARGET_DBTP` / `DIORAMA_MUX_TRUE_PEAK_LIMITER` | `-1.5` / `"aresample=192000,alimiter=limit=0.794:attack=1:release=50:level=disabled,aresample=48000"` | Encoded AAC true-peak ceiling `P7` [P7] |
| ASR scoring (`_asr_tokens`, P6) | — | Hyphen split, dotted-initials `hm` `juggle` `tests` `PROSODY_P6_ASR_MATCH_MIN` |
| `DIORAMA_V7_PROSODY_GEARS` / `DIORAMA_V7_US_PROSODY_GEARS` | `1.12x / 1.08x / 1.15x` · US: rush `1.10x` (gap `0.030s`) / stamp `1.04x` (gap `0.180s`) / brisk `1.07x` (gap `0.075s`) | Per-gear target tempo |
| `DIORAMA_V7_PROSODY_UNIFORM_110` | trim `0.14→0.045s`, gap `0.085s`, stamp gap `0.17s`, act gap `0.20s` | breath/gap profile `uniform_110x` |
| `DIORAMA_V7_PROSODY_ACT_GAP_MIN` / `DIORAMA_V7_PROSODY_MAX_ADJ_TEMPO_JUMP` / `DIORAMA_V7_PROSODY_RUSH_MAX_STREAK` | `0.20` / `0.05` / `3` | Act boundary gap floor, adjacent |
| `DIORAMA_V7_PROSODY_EMPHASIS_PAUSE_SEC` / `DIORAMA_V7_PROSODY_EMPHASIS_GAIN_DB` | `0.0` / `1.0` | Co-articulation-safe smooth `script.json` `emphasis_words` |
| `DIORAMA_V7_PROSODY_STAMP_PHRASES` / `DIORAMA_V7_PROSODY_RUSH_CLIMAX_WORDS` / `DIORAMA_V7_PROSODY_REHOOK_PHRASES` | Anti-Clone bank union / `yet, then, suddenly, instead` / midpoint bank union | Rule-based gear classifier inputs |
| `PROSODY_P1_FIRST_ONSET_MAX_SEC` / `PROSODY_P2_HOOK_END_MAX_SEC` / `PROSODY_P2_STAMP_END_MAX_SEC` / `PROSODY_P3_TEMPO_TOLERANCE` / `PROSODY_P4_RUSH_MAX_INTERNAL_SILENCE_SEC` / `PROSODY_P5_STAMP_PRE_SILENCE_RANGE` / `PROSODY_P6_ASR_MATCH_MIN` / `PROSODY_P10_OPEN_LOOP_MAX_GAP_SEC` | `0.10` / `9.0` / `11.5` / `0.03` / `0.07` / `(0.20, 0.32)` / `0.95` / `35.0` | Prosody QA Gates — P2 [P2,P1–P10] |
| `DIORAMA_V7_INTERNAL_SILENCE_TRIM_THRESHOLD_SEC` / `DIORAMA_V7_INTERNAL_BREATH_KEEP_SEC` / `DIORAMA_V7_INTER_SENTENCE_PAUSE_SEC` / `DIORAMA_V7_ACT_BOUNDARY_PAUSE_SEC` | `0.28` / `0.14` / `0.15` / `0.32` | Conversational breath/silence [R63] |
| `DIORAMA_V7_AUDIO_CHANNELS` / `DIORAMA_V7_BGM_DUCK_DB` | `2` / `-22.0` | 2-channel stereo [R63] |
| `FONT_CONDENSED_BLACK_PATH` / `DIORAMA_V7_SUBTITLE_FONT_NAME` / `DIORAMA_V7_SUBTITLE_FONT_SIZE` / `DIORAMA_V7_SUBTITLE_OUTLINE_WIDTH` / `DIORAMA_V7_SUBTITLE_SHADOW_DEPTH` / `DIORAMA_V7_SUBTITLE_MARGIN_V` | `AABCondensed-Black.ttf` / `"AAB Condensed Black"` / `94` / `5.5` / `0.0` / `672` | Bundled condensed extra-black `fontsdir` [R63] |
| `DIORAMA_V7_CHAPTER_HEADLINE_FONT_SIZE` / `DIORAMA_V7_CHAPTER_HEADLINE_OUTLINE_WIDTH` / `DIORAMA_V7_CHAPTER_HEADLINE_MARGIN_V` / `DIORAMA_V7_CHAPTER_HEADLINE_SCALE_X` / `DIORAMA_V7_CHAPTER_HEADLINE_MARGIN_LR` / `DIORAMA_V7_CHAPTER_HEADLINE_MAX_WIDTH_PX` | `276` / `2.5` / `180` / `85` / `85` / `920` | Giant single-line top chapter [R63] |
| `DIORAMA_V7_ANATOMY_LABEL_FONT_SIZE` / `DIORAMA_V7_ANATOMY_LABEL_OUTLINE_WIDTH` / `DIORAMA_V7_ANATOMY_LABEL_SCALE_X` / `DIORAMA_V7_ANATOMY_LABEL_MARGIN_V` | `104` / `5.0` / `90` / `190` | Programmatic upper-viewport ASS `AnatomyLabel` `porcelain_living_brain` `lowpoly_matte_brain` `ChapterHeadline` `split_hstack` [R63,R66] |

## 2-D. Post-Hoc Clip-by-Clip Expressive Clarity QA (R64) & Knowledge Base Hub (R50-B)
| Constant | Value | Rule / Note |
|---|---|---|
| `POSTHOC_SEMANTIC_QA_REPORT_FILENAME` | `"posthoc_semantic_qa_report.json"` | Dual-stream post-hoc visual [R64] |
| `POSTHOC_SEMANTIC_REVIEW_FILENAME` | `"posthoc_semantic_review.json"` | SHA-256-bound per-cut semantic [R64] |
| `POSTHOC_VIEWER_STRIPS_DIRNAME` | `"posthoc_viewer_strips"` | Annotated viewer contact sheets [R64] |
| `POSTHOC_CUTS_PER_VIEWER_SHEET` | `6` | Number of assembled cuts rendered [R64] |
| `POSTHOC_MIN_CUT_CLARITY_SCORE` | `75.0` | Minimum passing expressive [R64] |
| `POSTHOC_MIN_EPISODE_MEAN_CLARITY_SCORE` | `82.0` | Minimum episode-wide mean clarity [R64] |
| `POSTHOC_MIN_SHARPNESS_LAPLACIAN` | `12.0` | Minimum clean-ROI Laplacian focus [R64] |
| `POSTHOC_MIN_EDGE_DENSITY` | `0.005` | Minimum Canny structural edge [R64] |
| `POSTHOC_MIN_FG_BG_CONTRAST_DE` | `4.0` | Minimum perceptual LAB [R64] |
| `POSTHOC_MIN_MOVING_CAM_DIFF` | `1.00` | Minimum mean temporal luma diff [R64] |
| `POSTHOC_LOCKED_TRIPOD_MIN_P95_DIFF` | `1.50` | Minimum 95th-percentile localized `locked_tripod` [R64] |
| `POSTHOC_MAX_STEP_HIST_JUMP` | `0.78` | Maximum normalized HSV histogram [R64] |
| `POSTHOC_SPLIT_PANE_MIN_DIFF` | `10.0` | Minimum mean pixel difference `split_hstack` [R64] |
| `POSTHOC_BRAIN_HIGHLIGHT_MIN_CHROMA` | `6.0` | Minimum LAB chroma accent [R64] |
| `POSTHOC_ANALOGY_SYNC_TOLERANCE_SEC` | `0.45` | Maximum timing delta between ASR [R64] |
| `POSTHOC_MIN_REVIEW_NOTE_CHARS` | `20` | Minimum length for per-cut in `observed_visual_summary` `posthoc_semantic_review.json` [R64] |
| `POSTHOC_MAX_IDENTICAL_REVIEW_NOTES` | `3` | Maximum identical review [R64] |
| `KNOWLEDGE_BASE_DIRNAME` / `KNOWLEDGE_BASE_DIR` | `"knowledge_base"` / `CHANNEL_ROOT / "knowledge_base"` | Channel-wide accumulated [R50-B] |
| `KNOWLEDGE_TELEMETRY_DIRNAME` | `"telemetry"` | Episode & clip clarity telemetry [R50-B] |
| `EPISODES_INDEX_FILENAME` / `CLIP_CLARITY_LEDGER_FILENAME` / `QA_ANALYTICS_SUMMARY_FILENAME` | `"episodes_index.jsonl"` / `"clip_clarity_ledger.jsonl"` / `"qa_analytics_summary.json"` | Episode registry, per-cut clarity [R50-B] |
| `REUSABLE_PACKS_DIRNAME` / `EXPERIMENTS_ARCHIVE_DIRNAME` | `"reusable_packs"` / `"experiments"` | Reusable [R50-B] |

## 2-E. Source-Conditioned 1:1 Porcelain Reenactment (R67) & 3-Format US Funnel
| Constant | Value | Rule / Note |
|---|---|---|
| `REENACT_QUARANTINE_ROOT` | `Path("/tmp/aab_reenact")` | Ephemeral quarantine workspace `RQ1` [RQ1] |
| `REENACT_EDL_FILENAME` / `REENACT_QA_REPORT_FILENAME` / `REENACT_COMPARISON_SHEET_FILENAME` | `"source_edl.json"` / `"reenactment_qa_report.json"` / `"reenactment_comparison_sheet.png"` | Repo-safe shot/hash EDL , QA [RQ1–RQ5,R67] |
| `REENACT_MIN_DHASH_DISTANCE` | `18` | minimum 64-bit Hamming distance `RQ2` `dHash` [RQ2] |
| `REENACT_MAX_TRANSCRIPT_5GRAM_OVERLAP` | `0.0` | verbatim 5-gram SHA-256 overlap `RQ3` [RQ3] |
| `REENACT_LAB_RATIO_TARGET` / `REENACT_BRAIN_RATIO_MIN` / `REENACT_COMPOSITION_MATCH_MIN` | `0.78` / `0.20` / `0.85` | source-conditioned room `R66` `hstack` `RQ5` [R66,RQ5] |
| `PORCELAIN_REF_WHITE_RATIO_MAX` / `PORCELAIN_REF_NEON_GREEN_MAX` | `0.72` / `0.012` | Calibrated high-key white ratio `R66` `porcelain_cinematic_v7` `Q2` `Q6` [R66,Q2,Q6] |
| `REENACTMENT_TRACKS` | `("track_a", "track_b")` | Dual-Track reference-conditioning `porcelain_cinematic_v7` `track_a` `R67` `track_b` [R67,R66] |
| `MEDIA_SUITABILITY_CLASSES` | `("suitable_track_a", "needs_section_window", "reject_track_b_only")` | 4-Gate CV/Transcript/Metadata `04_media_refs.json` |
| `MEDIA_REJECT_CHANNEL_PATTERNS` | `("ted", "tedx", "ted-ed", ..., "huberman lab")` | Lecture, dark-stage `reject_track_b_only` [Gate 1] |
| `MEDIA_SUITABILITY_SCHEMA_VERSION` / `MEDIA_MIN_CINEMA_YEAR` | `2` / `1895` | Schema version & pre-cinema year [R44-M] |
| `MEDIA_MAX_DARK_VOID_RATIO` | `0.72` | Gate 2 max median dark pixel [Gate 2] |
| `MEDIA_BW_ARCHIVAL_SAT_MAX` / `MEDIA_BW_FRAME_P90_SAT_MAX` | `24.0` / `36.0` | Gate 3 per-pixel and frame-wide [Gate 3] |
| `MEDIA_MAX_FLAT_SLIDE_RATIO` / `MEDIA_MIN_MOTION_DIFF` | `0.62` / `1.2` | Gate 3 max flat low-texture [Gate 3] |
| `MEDIA_MAX_UNWINDOWED_DURATION_SEC` | `600.0` | Gate 4 max unwindowed video [Gate 4] |
| `MEDIA_ARCHIVAL_SEARCH_SUFFIXES` | `("original archival footage", "16mm experiment film", "clinical demonstration video")` | Archival query boost suffixes [R44-M] |
| `PORCELAIN_ANCHOR_MIN_CLIP_RATIO` / `PORCELAIN_ANCHOR_MAX_CLIP_RATIO` | `0.28` / `0.88` | Non-outro clip reference-binding `R67` [R66,R67] |
| `YUNET_FACE_MODEL_PATH` | `ASSETS_DIR / "models" / "face_detection_yunet_2023mar.onnx"` | Bundled OpenCV Zoo Apache-2.0 `R67` [R67,Gate 4] |
| `MICRO_SHORT_PROFILE` | `"micro_short_v7"` | Micro-Short discovery funnel profile |
| `MICRO_SHORT_DURATION_MIN_SEC` / `MICRO_SHORT_DURATION_MAX_SEC` (`MICRO_SHORT_MIN_SEC` / `MICRO_SHORT_MAX_SEC`) | `35.0` / `45.0` | Assembled duration bounds for `micro_short_v7` |
| `MICRO_SHORT_WORD_COUNT_MIN` / `MICRO_SHORT_WORD_COUNT_MAX` (`MICRO_SHORT_WORD_MIN` / `MICRO_SHORT_WORD_MAX`) | `95` / `120` | Spoken word budget for `micro_short_v7` |
| `MICRO_SHORT_CUT_COUNT_MIN` / `MICRO_SHORT_CUT_COUNT_MAX` (`MICRO_SHORT_CUT_MIN` / `MICRO_SHORT_CUT_MAX`) | `14` / `16` | Cut count bounds for `micro_short_v7` |
| `SHORTS_90S_PROFILE` / `SHORTS_EXPRESSIVE_V8_PROFILE` / `SHORTS_180S_PROFILE` / `SHORTS_FORMAT_PROFILES` / `DEFAULT_SHORTS_FORMAT_PROFILE` | `"shorts_90s_v7"` / `"shorts_expressive_v8"` / `"shorts_180s_v7"` / `("micro_short_v7", "shorts_90s_v7", "shorts_expressive_v8", "shorts_180s_v7")` / `"shorts_90s_v7"` | 90s (`1m30s`) Shorts default profile (`<30m` target), Expressive 2.5D v8 (`58-88s`), & 180s archive preservation |
| `SHORTS_90S_DURATION_MIN_SEC` / `SHORTS_90S_DURATION_TARGET_SEC` / `SHORTS_90S_DURATION_MAX_SEC` | `75.0` / `90.0` / `105.0` | Assembled duration bounds & target for `shorts_90s_v7` |
| `SHORTS_90S_WORD_COUNT_MIN` / `SHORTS_90S_WORD_COUNT_MAX` / `SHORTS_90S_SENTENCE_COUNT_MIN` / `SHORTS_90S_SENTENCE_COUNT_MAX` | `210` / `275` / `22` / `32` | Spoken word & sentence count bounds for `shorts_90s_v7` |
| `SHORTS_90S_CLIP_COUNT_MIN` / `SHORTS_90S_CLIP_COUNT_DEFAULT` / `SHORTS_90S_CLIP_COUNT_MAX` / `SHORTS_90S_CUT_COUNT_MIN` / `SHORTS_90S_CUT_COUNT_MAX` | `24` / `28` / `32` / `24` / `36` | Clip & cut count bounds for `shorts_90s_v7` |
| `LONGFORM_DEFERRED` / `LONGFORM_PRODUCTION_PROFILE` / `LONGFORM_PROJECTS_DIRNAME` / `LONGFORM_PROJECTS_DIR` / `LONGFORM_QUARANTINE_ROOT` | `True` / `"longform_porcelain_16x9_v1"` / `"projects_longform"` / `CHANNEL_ROOT / "projects_longform"` / `Path("/tmp/aab_reenact_lf")` | Deferred Long-Form hold (`LONGFORM_DEFERRED = True`) & isolated workspace [R67] |
| `LONGFORM_VIDEO_WIDTH` / `LONGFORM_VIDEO_HEIGHT` / `LONGFORM_VIDEO_FPS` / `LONGFORM_H264_PROFILE` / `LONGFORM_H264_LEVEL` / `LONGFORM_H264_CRF` / `LONGFORM_FINAL_MP4_FILENAME` | `1920` / `1080` / `24` / `"high"` / `"4.2"` / `18` / `"final_longform_1920x1080.mp4"` | Native Full HD Long-Form |
| `LONGFORM_TARGET_LUFS` / `LONGFORM_TRUE_PEAK_CEILING_DBTP` / `LONGFORM_PROSODY_MODE` / `LONGFORM_DEFAULT_VOICE_PRESET` / `LONGFORM_PROSODY_GEAR_RATES` / `LONGFORM_RUSH_PAUSE_SEC` / `LONGFORM_INTER_SENTENCE_PAUSE_SEC` / `LONGFORM_BEAT_PAUSE_SEC` / `LONGFORM_CHAPTER_PAUSE_SEC` / `LONGFORM_BGM_DUCK_DB` / `LONGFORM_BGM_SWELL_PEAK_DB` / `LONGFORM_WPM_RANGE` / `LONGFORM_PILOT_DURATION_RANGE_SEC` / `LONGFORM_MAX_SENTENCE_WORDS` (`LONGFORM_MAX_WORDS_PER_SENTENCE`) / `LONGFORM_UPLOAD_CC_SRT_DEFAULT` | `-14.0` / `-1.5` / `"longform_us_v7"` / `"elevenlabs_v4"` / `{rush:"+4%", explain:"+0%", stamp:"-2%"}` / `0.22` / `0.25` / `0.45` / `0.92` / `-22.0` / `-13.5` / `(132.0, 158.0)` / `(510.0, 560.0)` / `22` / `False` | Relaxed Long-Form vocal delivery |
| `LONGFORM_MIN_CUT_SEC` / `LONGFORM_AVG_CUT_TARGET_SEC` / `LONGFORM_AVG_CUT_RANGE_SEC` / `LONGFORM_MAX_CUT_SEC` / `LONGFORM_PILOT_CLIP_COUNT_RANGE` / `LONGFORM_SHARD_MAX_CLIPS` / `LONGFORM_SPLIT_DIVIDER_PX` | `3.20` / `5.00` / `(4.60, 5.80)` / `7.00` / `(90, 114)` / `14` / `3` | Relaxed documentary cut pacing |
| `LONGFORM_SUBTITLE_FONT_SIZE` / `LONGFORM_SUBTITLE_OUTLINE_WIDTH` / `LONGFORM_SUBTITLE_SHADOW_DEPTH` / `LONGFORM_SUBTITLE_MARGIN_V` / `LONGFORM_SUBTITLE_Y_RANGE` / `LONGFORM_SUBTITLE_MAX_WORDS` / `LONGFORM_SUBTITLE_MAX_CHARS` | `58` / `3.5` / `1.0` / `98` / `(922, 982)` / `5` / `32` | Burned-in bottom-center subtitle |
| `LONGFORM_CITATION_CARD_X` / `LONGFORM_CITATION_CARD_Y_RANGE` / `LONGFORM_CITATION_CARD_MIN_CLEARANCE_PX` / `LONGFORM_CITATION_CARD_DURATION_SEC` / `LONGFORM_CITATION_CARD_WIDTH_RANGE` / `LONGFORM_CITATION_CARD_BAR_WIDTH_PX` / `LONGFORM_CHAPTER_HEADLINE_Y_RANGE` / `LONGFORM_CHAPTER_HEADLINE_FONT_SIZE` / `LONGFORM_CHAPTER_HEADLINE_DURATION_SEC` / `LONGFORM_SPLIT_LEFT_X` / `LONGFORM_SPLIT_RIGHT_X` | `96` / `(735, 872)` / `50` / `5.0` / `(340, 860)` / `4` / `(78, 180)` / `66` / `3.0` / `480` / `1440` | Non-overlapping lower-left , top `DocCitationCard` `ChapterHeadline` `SplitLeft` `SplitRight` |
| `THUMB_LONGFORM_WIDTH` / `THUMB_LONGFORM_HEIGHT` / `LONGFORM_THUMB_MAX_BYTES` | `1920` / `1080` / `1_950_000` | Native Long-Form A/B/C thumbnail |
| `DEBATE_CREATOR_BET_PREFIXES` / `DEBATE_CREATOR_BET_MAX_PREFIX_CHARS` / `PINNED_COMMENT_LINE1_MAX_CHARS` / `BANNED_COMMENT_VIOLENCE_TOKENS` / `DIORAMA_OPEN_VERDICT_BRIDGE_BANK` | `5` prefixes / `45` / `240` / `13` tokens / `6` bridges | 3-Stage Ignition pinned-comment |
| `EVERYDAY_LONGFORM_DOMAINS` / `NEURO_NEWS_STAGING_DIR` / `NEURO_NEWS_HOLD_FROM_AUTO_QUEUE` | `("sleep", "habits", "memory", "anxiety", "relationships")` / `WORKSPACE_ROOT / "Completed_Neuro_News_Shorts"` / `True` | 5 everyday behavioral-psych × |

## 2-F. Expressive 2.5D Vinyl v8, 3-Voice Repertory Cast, Prompt Diet, R70 Data Stamp & R72–R74 Open-World / Neural FPV (R68 / R70 / R72 / R73 / R74)
| Constant | Value | Rule / Note |
|---|---|---|
| `PROMPT_SCHEMA_VERSION_V8` / `EXPRESSIVE_25D_V8_STYLE_PROFILE` / `ALL_DIORAMA_STYLE_PROFILES` | `8` / `"expressive_25d_v8"` / `("lowpoly_pastel_v7", "porcelain_cinematic_v7", "expressive_25d_v8")` | Expressive 2.5D vinyl art-toy + golden seam X-Ray + 1-cut Mini-Cortex cameo [R68] |
| `SHORTS_EXPRESSIVE_V8_DURATION_MIN_SEC` / `SHORTS_EXPRESSIVE_V8_DURATION_TARGET_RANGE_SEC` / `SHORTS_EXPRESSIVE_V8_R75_MAX_SEC` / `SHORTS_EXPRESSIVE_V8_DURATION_MAX_SEC` / `EXPRESSIVE_V8_HARD_CEILING_SEC` / `PRE_R75_DURATION_GRANDFATHER_PROJECTS` | `61.5` / `(62.0, 86.0)` / `88.0` / `120.0` / `120.0` / `v8_pilot_01..03 + v8_ep04..06` | Assembled storytelling duration bounds (`>= 61.5s`, `<= 88.0s` R75 ceiling on new `shorts_expressive_v8`; `<= 120.0s` grandfathered on `PRE_R75_DURATION_GRANDFATHER_PROJECTS`) [R68,R75] |
| `SHORTS_EXPRESSIVE_V8_CLIP_COUNT_MIN` (`EXPRESSIVE_V8_CLIP_COUNT_MIN`) / `SHORTS_EXPRESSIVE_V8_CLIP_COUNT_DEFAULT` / `SHORTS_EXPRESSIVE_V8_CLIP_COUNT_MAX` (`EXPRESSIVE_V8_CLIP_COUNT_MAX`) / `EXPRESSIVE_V8_CLIP_COUNT_RANGE` / `SHORTS_EXPRESSIVE_V8_CUT_COUNT_MIN` / `SHORTS_EXPRESSIVE_V8_CUT_COUNT_MAX` / `EXPRESSIVE_V8_LEGACY_INDOOR_CLIP_COUNT_RANGE` | `22` / `28` / `36` / `(22, 36)` / `28` / `46` / `(18, 26)` | R72 fast-cut open-world `8.0s` clip & EDL cut count bounds (`22-36` clips, `28-46` cuts; legacy `18-26` preserved for `PRE_R72_FROZEN_V8_PROJECTS`) [R68,R72] |
| `SHORTS_EXPRESSIVE_V8_WORD_COUNT_MIN` / `SHORTS_EXPRESSIVE_V8_WORD_COUNT_MAX` / `SHORTS_EXPRESSIVE_V8_SENTENCE_COUNT_MIN` / `SHORTS_EXPRESSIVE_V8_SENTENCE_COUNT_TARGET` / `SHORTS_EXPRESSIVE_V8_SENTENCE_COUNT_MAX` / `SHORTS_EXPRESSIVE_V8_SENTENCE_WORDS_MAX` | `145` / `420` / `12` / `(15, 22)` / `28` / `30` | Easy-to-follow storytelling word & sentence bounds (`<= 30` words/sentence, `145-420` words for `62-86s` R75 Shorts) [R68,R75] |
| `EXPRESSIVE_V8_CONTEXT_SPLIT_WORDS_RANGE` | `(18, 45)` | Google Flow `Prompt Diet` (`45%` shorter prompts: strips UI-redundant `8s vertical video.`, `Bridges opening...`, `Settles smoothly...`) |
| `EXPRESSIVE_V8_REFS_DIRNAME` / `EXPRESSIVE_V8_SPECIES_SHEET_FILENAME` / `EXPRESSIVE_V8_CAMEO_SHEET_FILENAME` / `EXPRESSIVE_V8_CAST_SHEET_FILENAMES` | `"expressive_25d_v8_refs"` / `"species_opt1_sheet.png"` / `"cameo_opt3_sheet.png"` / `3` 6-role sheets | Master Option 1 + Option 3 reference anchor pack + Headless Blender 3D Previs (`E1-E8`) |
| `EXPRESSIVE_V8_DEFAULT_OPENING_MODE` / `EXPRESSIVE_V8_ALLOWED_OPENING_MODES` / `EXPRESSIVE_V8_OPENING_CASE_STAMP_MIN_WORDS` / `EXPRESSIVE_V8_OPENING_CASE_STAMP_MAX_WORDS` / `EXPRESSIVE_V8_CASE_STAMP_ANCHOR_WINDOW_WORDS` / `PRE_R68H_FROZEN_V8_PROJECTS` / `EXPRESSIVE_V8_CORE_REVEAL_MAX_SENTENCE` / `EXPRESSIVE_V8_CORE_REVEAL_MAX_SEC` / `EXPRESSIVE_V8_OPENING_ACTION_MAX_WORDS` / `EXPRESSIVE_V8_OPENING_QUESTION_MAX_WORDS` / `EXPRESSIVE_V8_OPENING_EMPATHY_MAX_WORDS` / `EXPRESSIVE_V8_OPENING_QUESTION_STARTERS` / `EXPRESSIVE_V8_MAX_MYTH_FLIPS` / `EXPRESSIVE_V8_FORBID_SPOKEN_CITATIONS` / `EXPRESSIVE_V8_ADVISORY_PIVOT_MARKERS` / `EXPRESSIVE_V8_BRAIN_REVEAL_WINDOW_FRAC` / `EXPRESSIVE_V8_BRAIN_REVEAL_TOLERANCE_FRAC` / `EXPRESSIVE_V8_CAMEO_COUNT_PER_EPISODE` | `"case_stamp"` / `("case_stamp", "action", "question", "situation")` / `10` / `22` / `9` / `v8_pilot_01..03` / `16` / `95.0` / `30` / `20` / `12` / `8` starters / `1` / `False` / `True` / `(0.55, 0.88)` / `(0.50, 0.92)` / `1` | `R68-H` first-2s `case_stamp` hook (`10-22w`, year/duration within first `9w` + real institution/person event; `"Imagine..."` banned), `[60-80%]` delayed core reveal, X-Ray 4-color brain, & `1` Mini-Cortex cameo cut [R68,R68-H] |
| `EXPRESSIVE_V8_VISUAL_GRAMMARS` / `EXPRESSIVE_V8_TRANSITION_TYPES` / `EXPRESSIVE_V8_DRONE_CAMERA_MOVES` / `EXPRESSIVE_V8_NEURAL_DIVE_MOVES` / `EXPRESSIVE_V8_CAMERA_MOVES` | `16` grammars (`expressive_exterior_establishing`, `architectural_cutaway_portal`) / `12` transitions (`seamless_relay_cut` 0-frame `K1` relay) / `5` drone moves / `4` neural dive moves / `23` moves | 12-type 3D camera-bridge transition & Open-World/Neural `Previs v2.3` FPV schema [R68,R72,R74] |
| `EXPRESSIVE_V8_MIN_CUT_SEC` / `EXPRESSIVE_V8_MAX_CUT_SEC` / `EXPRESSIVE_V8_LONG_TAKE_MAX_SEC` / `EXPRESSIVE_V8_FIRST_CUT_MAX_SEC` / `EXPRESSIVE_V8_FIRST_15S_MAX_CUT_SEC` / `EXPRESSIVE_V8_FIRST_15S_MIN_CUTS` / `EXPRESSIVE_V8_AVG_CUT_TARGET_RANGE` (`EXPRESSIVE_V8_AVG_CUT_MIN_SEC`..`EXPRESSIVE_V8_AVG_CUT_MAX_SEC`) / `EXPRESSIVE_V8_CUT_CV_MIN` / `EXPRESSIVE_V8_DRONE_PEAK_CORE_WINDOW_SEC` | `0.85` / `4.80` / `14.50` / `2.60` / `3.20` / `5` / `(2.05, 3.30)` (`2.05`..`3.30`) / `0.18` / `(0.45, 2.75)` | R72 fast-cut shot hold & drone peak-motion harvest bounds (`<= 2.60s` first cut, `>= 5` cuts in `0-15s` `<= 3.20s`, `<= 4.80s` max cut; `EXPRESSIVE_V8_LEGACY_*` preserved) [R68,R72] |
| `EXPRESSIVE_V8_VIDEO_FPS` / `EXPRESSIVE_V8_DISSOLVE_FRAMES` / `EXPRESSIVE_V8_DISSOLVE_8_FRAMES` / `EXPRESSIVE_V8_PORTAL_ZOOM_FRAMES` / `EXPRESSIVE_V8_WHIP_PAN_FRAMES` / `EXPRESSIVE_V8_MAX_STYLED_TRANSITIONS` / `EXPRESSIVE_V8_MAX_OVERLAP_FRAMES` / `EXPRESSIVE_V8_MAX_ALPHA_DISSOLVE_FRAMES` / `EXPRESSIVE_V8_MAX_HARD_JUMP_CUTS` / `EXPRESSIVE_V8_DISSOLVE_SEC` / `EXPRESSIVE_V8_OUTRO_TAIL_SEC` / `EXPRESSIVE_V8_OUTRO_TAIL_RANGE_SEC` | `30` / `6` / `8` / `10` / `8` / `4` / `10` / `6` / `1` / `0.25` / `0.20` / `(0.16, 0.25)` | Native `30fps` Track-V1 spatial camera transitions (`<= 4` styled transitions, `DQ13`) & `0.20s` climax cut |
| `EXPRESSIVE_V8_SUBTITLE_FONT_SIZE` / `EXPRESSIVE_V8_SUBTITLE_OUTLINE_WIDTH` / `EXPRESSIVE_V8_SUBTITLE_SHADOW_DEPTH` / `EXPRESSIVE_V8_SUBTITLE_MARGIN_V` / `EXPRESSIVE_V8_SUBTITLE_MAX_WORDS` / `EXPRESSIVE_V8_SUBTITLE_HIGHLIGHT_HEX` (`EXPRESSIVE_V8_SUBTITLE_HIGHLIGHT_ASS_BGR`) / `EXPRESSIVE_V8_MIN_LUMA` / `EXPRESSIVE_V8_MIN_SATURATION` | `64` / `3.5` / `0.0` / `521` / `2` / `"#FFFFFF"` (`"&H00FFFFFF&"`) / `28.0` / `26.0` | Clean pure-white `1-2w` `AAB Condensed Black` subtitle (`MarginV=521`, `0` top banners) & story-matched atmospheric luma floor (`28.0`) |
| `EXPRESSIVE_V8_WPM_TARGET_RANGE` / `EXPRESSIVE_V8_WPM_ALLOWED_RANGE` / `EXPRESSIVE_V8_PROSODY_MODE` / `EXPRESSIVE_V8_PROSODY_BASE_RATE` / `EXPRESSIVE_V8_PROSODY_GEAR_RATES` / `EXPRESSIVE_V8_PROSODY_GEARS` / `EXPRESSIVE_V8_VOICE_PRESET` / `EXPRESSIVE_V8_FOIL_VOICE_PRESET` / `EXPRESSIVE_V8_ALLOWED_SPEAKER_ROLES` / `EXPRESSIVE_V8_MAX_VOICES_PER_EPISODE` / `EXPRESSIVE_V8_MIN_NARRATOR_SHARE` / `EXPRESSIVE_V8_FOIL_SENTENCE_RANGE` / `EXPRESSIVE_V8_REQUIRE_FOIL` / `EXPRESSIVE_V8_CLAUSE_CROSSFADE_SEC` / `EXPRESSIVE_V8_FIRST_ONSET_TARGET_SEC` / `STORYTELLER_VOCAL_FILTER_EXPRESSIVE_V8` | `(165.0, 205.0)` / `(135.0, 225.0)` / `"expressive_us_v8"` / `"+10%"` / `{rush:"+14%", brisk:"+10%", stamp:"+4%"}` / `1.14/1.10/1.04` / `"elevenlabs_v4"` / `"elevenlabs_v4_male"` / `("narrator", "researcher", "mini_cortex", "foil")` / `3` / `0.75` / `(0, 0)` / `False` / `0.020` / `0.0` / `145Hz +3.2dB warmth` | Sole fail-fast ElevenLabs `v4` 3-Voice Repertory Cast (`narrator`=`Roger` `>=75%`, `researcher`=`Hope`, `mini_cortex`=`Laura`, `<=3` voices) |
| `DATA_STAMP_MIN_PER_EPISODE` / `DATA_STAMP_MAX_PER_EPISODE` / `DATA_STAMP_Y_FRAC_RANGE` / `UNIVERSAL_SAFE_X_RIGHT_PX` / `DATA_STAMP_ILLUSTRATION_TAG` / `DATA_STAMP_MODES` / `DATA_STAMP_LAYER_TYPES` / `DATA_STAMP_PRESETS` / `DATA_STAMP_MAX_PANELS` / `DATA_STAMP_MAX_LAYERS_PER_PANEL` / `DATA_STAMP_MAX_GROUPS` / `DATA_STAMP_MAX_SCATTER_POINTS` | `2` / `2` / `(0.12, 0.62)` / `910` / `"Concept"` / `("study", "illustrative")` / `8` layers / `6` presets / `1` / `2` / `3` / `80` | `R70` / `R70-M` 3-platform safe-zone (`Y >= 12%`, `X <= 910px`) programmatic hand-drawn chart engine (`pipeline/data_stamp_overlay.py`, `pipeline/charts/`) |
| `EXPRESSIVE_V8_BGM_START_DBFS` / `EXPRESSIVE_V8_BGM_PEAK_DBFS` / `EXPRESSIVE_V8_BGM_TAIL_DBFS` / `EXPRESSIVE_V8_AMBIENCE_DBFS` (`EXPRESSIVE_V8_ROOM_AMBIENCE_DBFS`) / `EXPRESSIVE_V8_FOLEY_PEAK_DBFS` / `EXPRESSIVE_V8_GAP_WINDOW_RANGE_SEC` / `EXPRESSIVE_V8_TARGET_LUFS` / `EXPRESSIVE_V8_TRUE_PEAK_MAX_DBTP` / `EXPRESSIVE_V8_VOICED_RATIO_MIN` / `EXPRESSIVE_V8_FOLEY_TYPES` | `-25.0` / `-18.0` / `-18.0` / `-30.0` / `-14.5` / `(0.18, 0.55)` / `-14.0` / `-1.5` / `0.72` / `("thud", "whoosh", "click", "pop", "crystal_shimmer", "heartbeat_thump")` | Rising dark-suspense tonal underscore BGM (`-25 -> -18 dBFS`) + stereo room air + camera-transition/gap Foley |
| `R68_TITLE_WORD_RANGE` / `R68_TITLE_MAX_CHARS` / `R68_DESCRIPTION_HASHTAG_COUNT` / `R68_DESCRIPTION_HASHTAG_MAX` | `(4, 8)` / `55` / `1` / `1` | R68 paradox/common-noun title (`4-8` words, `<= 55` chars) & single clean `#shorts` routing tag in description (`0` hashtags in title) [R68,R75] |
| `R68D_DESCRIPTION_WORD_RANGE` / `R68D_BANNED_AI_CLICHES` | `(55, 135)` / `25` tokens (`"—"`, `" -- "`, `"documentary case briefing on"`, `"turns out,"`, `"what's wild is"`, `"here's the catch"`, `"visuals and voice"`, `"delve"`, ...) | `R68-D` Zero-AI-Smell plain 2-paragraph YouTube description + `Research:` citation line & DOI/em-dash/cliché hard gate [R68-D] |
| `EXPRESSIVE_V8_REQUIRE_EXTERIOR_COLD_OPEN` / `EXPRESSIVE_V8_MIN_OUTDOOR_OR_ARCH_RATIO` / `EXPRESSIVE_V8_MIN_DRONE_FLIGHT_RATIO` / `EXPRESSIVE_V8_MAX_CONSECUTIVE_SAME_INDOOR_LOC` / `EXPRESSIVE_V8_REQUIRE_REAL_LANDMARK_REFS` / `PRE_R72_FROZEN_V8_PROJECTS` / `PRE_R72_FROZEN_V8_DOSSIERS` / `REAL_WORLD_REFS_QUARANTINE_ROOT` / `REAL_WORLD_REFS_MANIFEST_FILENAME` / `REAL_WORLD_REFS_MIN_DHASH_DISTANCE` / `REAL_WORLD_REFS_MIN_EDGE_ALIGNMENT` | `True` / `0.35` / `0.35` / `2` / `True` / `Ep #1..#6` / `4` slugs / `Path("/tmp/aab_real_refs")` / `"real_world_refs_manifest.json"` / `14` / `0.30` | `Rule R72 + R72-R` Open-World Architectural Scale, `K0->K1->K2` FPV Drone Cutaway Relay & Quarantined 3-Category Real-World Reference Conditioning (`RQ-Real`) [R72,R72-R] |
| `EXPRESSIVE_V8_US_NATIVE_OPENING_MODES` / `EXPRESSIVE_V8_R73_OPENING_WORD_RANGES` / `EXPRESSIVE_V8_POST_HOOK_PAUSE_SEC` (`EXPRESSIVE_V8_POST_HOOK_PAUSE_RANGE_SEC`) / `EXPRESSIVE_V8_MAX_HARD_JARGON_TERMS` / `EXPRESSIVE_V8_IMMEDIATE_GLOSS_WINDOW_WORDS` / `SHORTS_EXPRESSIVE_V8_R73_SENTENCE_WORDS_MAX` / `EXPRESSIVE_V8_MAX_FK_GRADE` / `EXPRESSIVE_V8_ENDING_MODES` / `PRE_R73_FROZEN_V8_PROJECTS` | `("paradox_question", "myth_flip_claim", "sensory_test", "action_first_stamp")` / `8-18w` (`8-20w`) / `0.42` (`(0.38, 0.48)`) / `2` / `8` / `22` / `6.2` / `("mic_drop", "seamless_loop")` / `Ep #1..#6` | `Rule R73` US-Native Spoken Narration, `0.42s` Post-Hook Pause, `S2-S4` University Credibility Bridge, `Plain-First` `<=8w` Gloss, `<=22w` Sentences & `FK <= 6.2` [R73] |
| `EXPRESSIVE_V8_NEURAL_DIVE_MOVES` / `EXPRESSIVE_V8_NEURAL_DIVE_PEAK_WINDOW_SEC` / `EXPRESSIVE_V8_REQUIRE_NEURAL_DIVE_RELAY` / `EXPRESSIVE_V8_DEFAULT_NEURAL_DIVE_CYCLES` / `EXPRESSIVE_V8_MAX_CONSECUTIVE_BRAIN_CUTS` / `NEURAL_WHOOSH_GAIN_DB` / `NEURAL_WHOOSH_DURATION_SEC` / `NEURAL_WHOOSH_BAND_HZ` / `PRE_R74_FROZEN_V8_PROJECTS` / `PRE_R74_FROZEN_V8_DOSSIERS` | `("neural_fpv_dive_in", "neural_macro_orbit_hold", "neural_fpv_pullback_out", "neural_tract_relay_flight")` / `(0.40, 2.55)` / `True` / `2` / `3` / `-21.0` / `0.36` / `(160.0, 850.0)` / `Ep #1..#6` / `4` slugs | `Rule R74` 3D Neural FPV Dive, `50%` Subcortical Macro Lock (`B0 <-> B1`), Arrival-Locked `R71` Callout & `-21.0 dBFS` Velvet Glass-Whoosh [R74] |
| `EXPRESSIVE_V8_TOPIC_FOCUSES` / `EXPRESSIVE_V8_PSYCH_BRAIN_CLIP_RATIO_RANGE` / `EXPRESSIVE_V8_NEURO_BRAIN_CLIP_RATIO_RANGE` / `EXPRESSIVE_V8_NEURO_BRAIN_REVEAL_WINDOW_FRAC` / `EXPRESSIVE_V8_NEURAL_STATES` / `R71_CALLOUT_MODES` / `PRE_R74B_FROZEN_V8_PROJECTS` / `PRE_R74B_FROZEN_V8_DOSSIERS` | `("psychology", "neuroscience")` / `(0.12, 0.26)` / `(0.24, 0.38)` / `(0.45, 0.88)` / `("active", "silenced", "severed", "rerouted")` / `("single_region", "pathway_relay", "pathway_severed")` / `Ep #1..#7` / `5` slugs | `Rule R74-B` & `Rule R71-B` Psych (`12-26%`) vs Neuro (`24-38%`, `>=45%` reveal) branching, `31/31` Brain Atlas, 4-State Pathology (`Previs v2.4`) & 2-Node Pathway/Severance Pen Callouts [R71-B,R74-B] |

## 3. Assembly Timing, Holds & Speech Window Detection
| Constant | Value | Rule / Note |
|---|---|---|
| `AV_SPEEDUP_FACTOR` | `1.00` | Synchronized video and audio `setpts` `atempo` [R43-A] |
| `CLIP_VISUAL_HOLD_SEC` | `0.32` | Post-speech visual hold on [R43-B] |
| `CLIP_PRE_PIVOT_HOLD_SEC` | `0.45` | Post-speech visual hold on the `pivot` [R43-B] |
| `CLIP_PRE_ROLL_TRIM_SEC` | `0.40` | Minimum pre-roll trim on clips |
| `FINAL_TAIL_SEC` | `0.20` | Post-speech hold on the final clip [R19,R43-B] |
| `END_FADE_SEC` | `0.09` | Clean video/audio fade-out at the [R43-B] |
| `MASTER_TAIL_MUTE_SEC` | `0.095` | Final linear mute across all 4 |
| `VOCAL_ONSET_PROTECT_SEC` | `0.22` | Pre-onset window before first [R41] |
| `VOCAL_ONSET_PAD_SEC` | `0.05` | Additional trim pad before `speech_start` |
| `PROMPT_BLEED_SYLLABLE_SEC` | `0.185` | Expected speech duration per |
| `PROMPT_BLEED_MIN_EXPECTED_SEC` | `2.2` | Floor on expected speech duration |
| `PROMPT_BLEED_DEFAULT_SYLLABLES` | `22` | Fallback syllable count when clip |
| `PROMPT_BLEED_PAUSE_ALLOWANCE_SEC` | `0.40` | Internal pause threshold excluded |
| `PROMPT_BLEED_CUTOFF_RULES` | `((1.38, 0.65), (1.65, 0.35))` | Early cut rules to truncate |
| `SOFT_TAIL_FLOOR_DB` | `-36.5` | Minimum threshold for trailing |
| `SOFT_TAIL_P95_OFFSET_DB` | `15.0` | Offset below 95th-percentile RMS |
| `SOFT_TAIL_P15_OFFSET_DB` | `1.8` | Offset above 15th-percentile |
| `SOFT_TAIL_SEARCH_SEC` | `0.95` | Forward search window after last |
| `SOFT_TAIL_MAX_GAP_SEC` | `0.32` | Maximum continuous sub-threshold |
| `SPEECH_END_PAD_SEC` | `0.36` | Post-speech pad after normal |
| `SPEECH_END_PAD_BROKE_EARLY_SEC` | `0.12` | Tighter post-speech pad when |

## 4. Vocal Chain & Typography (Subtitles)
| Constant | Value | Rule / Note |
|---|---|---|
| `VOCAL_BANDPASS_HZ` | `(95, 13500)` | High-pass / low-pass corner |
| `VOCAL_EQ_BANDS` | `((180, 1.2, 2.5), (3200, 1.0, 4.0), (8500, 1.5, 2.0))` | 3-band parametric vocal EQ |
| `VOCAL_COMPRESSOR` | `{"threshold_db": -18, "ratio": 3.5, "attack_ms": 5, "release_ms": 60, "makeup_db": 3}` | Vocal dynamics compressor settings |
| `SUBTITLE_FONT_NAME` | `"Arial Black"` | Primary ASS subtitle font family [R16] |
| `SUBTITLE_FONT_SIZE` | `86` | Primary ASS subtitle font size |
| `SUBTITLE_OUTLINE_WIDTH` | `7.0` | Black outline thickness for contrast |
| `SUBTITLE_SHADOW_DEPTH` | `0.0` | Drop shadow depth |
| `SUBTITLE_MARGIN_V` | `440` | Vertical margin from bottom |
| `SUBTITLE_MAX_WORDS_PER_EVENT` | `3` | Maximum words per single subtitle [R16] |
| `SUBTITLE_MAX_LINES` | `1` | Strict single-line subtitle lock |
| `AUDIO_SIBILANCE_BAND_HZ` / `AUDIO_SPEECH_BODY_BAND_HZ` | `(4200.0, 9200.0)` / `(180.0, 3600.0)` | High-frequency |
| `AUDIO_MAX_SIBILANCE_ENERGY_RATIO` / `AUDIO_MAX_SIBILANCE_CREST_DB` | `0.62` / `32.0` | Max HF/body RMS ratio and HF |
| `DIORAMA_V7_TARGET_LUFS` / `DIORAMA_LUFS_TOLERANCE_LU` | `-15.5` / `4.0` | BS.1770 integrated documentary `ebur128` |
| `AUDIO_MAX_OVERSAMPLED_TRUE_PEAK_DBTP` / `AUDIO_MIN_TTS_ASR_WORD_COVERAGE` | `-0.5` / `0.85` | Max 4x oversampled True Peak and |

## 5. Media Integrity, Dead-Air & Anti-Derivative Thresholds
| Constant | Value | Rule / Note |
|---|---|---|
| `MIN_CLIP_SIZE_BYTES` | `1_000_000` | Minimum valid size per native [V5,R37] |
| `MIN_FINAL_VIDEO_SIZE_BYTES` | `1_000_000` | Minimum valid size for final |
| `FLOW_CLIP_DURATION_MIN_SEC` | `3.0` | Minimum valid native clip duration |
| `FLOW_CLIP_DURATION_MAX_SEC` | `15.0` | Maximum valid native clip duration |
| `FINAL_SHORTS_DURATION_MIN_SEC` | `24.0` | Minimum valid assembled Shorts |
| `FINAL_SHORTS_DURATION_MAX_SEC` | `105.0` | Maximum valid assembled Shorts |
| `MIN_FRAME_DIFF_THRESHOLD` | `2.0` | Minimum mean pixel difference |
| `MIN_PAIR_TOP_DIFF_THRESHOLD` | `0.5` | Minimum upper-frame diff between |
| `MIN_INTRA_SEGMENT_DIFF_THRESHOLD` | `0.5` | Minimum intra-segment motion diff |
| `MIN_OPTICAL_FLOW_THRESHOLD` | `0.12` | Minimum Farneback dense optical |
| `MAX_PERCEPTUAL_DHASH_HAMMING_DISTANCE` | `10` | 64-bit dHash distance ceiling [R37] |
| `DEAD_AIR_FLOOR_SEC` | `16.50` | Floor on allowed cumulative |
| `DEAD_AIR_DURATION_RATIO` | `0.38` | Scaling factor for allowed |
| `DEAD_AIR_SHORT_VIDEO_SEC` | `31.0` | Duration boundary separating |
| `DEAD_AIR_SHORT_VIDEO_MAX_SEC` | `0.90` | Maximum cumulative internal dead |
| `max_allowed_dead_air_sec(duration_sec)` | helper | Returns allowed cumulative dead |
| `expected_final_duration_sec(n_clips)` | helper | Nominal assembled duration for `n_clips` |

## 6. Browser Automation, Concurrency & Circuit Breakers
| Constant | Value | Rule / Note |
|---|---|---|
| `DEFAULT_CDP_HOST` | `"127.0.0.1"` | Naver Whale remote debugging host |
| `DEFAULT_CDP_PORT` | `9222` | Naver Whale remote debugging port |
| `FLOW_MAX_PARALLEL_BATCH_SIZE` | `5` | Hard cap on parallel subagents / [R37] |
| `FLOW_MAX_RETRIES` | `2` | Maximum generation trigger |
| `FLOW_TRIGGER_VERIFY_TIMEOUT_SEC` | `5.0` | Window to verify UI entered |
| `FLOW_TRIGGER_POLL_INTERVAL_SEC` | `0.5` | DOM polling interval during |
| `FLOW_RENDER_POLL_INTERVAL_SEC` | `10.0` | Polling interval while waiting |
| `FLOW_RENDER_TIMEOUT_SEC` | `210.0` | Maximum wait time for a single |
| `SUBPROCESS_TIMEOUT_SEC` | `180.0` | Hard timeout on every / `ffmpeg` `ffprobe` |
| `MAX_LOOP_ITERATIONS` | `60` | Hard safety ceiling on any |
| `ALLOW_EXTERNAL_PAID_APIS` | `False` | Zero external paid API policy lock [R5] |
| `ALLOW_STATIC_IMAGE_VIDEO_FALLBACK` | `False` | Anti-placeholder policy lock |

## 7. R65 v4 In-Skull 3D Cutaway Split & v2 Thumbnail Studio (`pipeline/thumbnail_studio.py`)
| Constant | Value | Rule / Note |
|---|---|---|
| `R65_V4_THUMBNAIL_PROFILE` / `DEFAULT_SHORTS_THUMBNAIL_PROFILE` | `"in_skull_cutaway_split_v4"` | Default `9:16` Shorts 0.3s meaning-clear `50/50` in-skull cutaway split cover (`conditioning_paths=None`, zero mannequins; optional `R65_V4_DARK_PARADOX_PROFILE = "dark_void_paradox_v4"`) [R65] |
| `THUMB_V4_OVERLAY_MODE` | `"r65_v4_in_skull_split"` | Clean `2:3`-shelf-safe upper-left white+black-stroke micro-labels (`y ≈ 176`, `y ≈ 1016`, zero boxes/2D arrows) [R65] |
| `THUMB_V4_MIN_MEAN_LUMA` / `THUMB_V4_TARGET_MEAN_LUMA` | `105.0` / `110.0` | Bright high-key studio daylight floor & prompt target [R65,TQ3] |
| `THUMB_V4_MIN_ACTIVATION_DELTA` | `0.015` | Bottom 50% red/cyan brain+arrow activation minus Top 50% dormant grey [R65,TQ8] |
| `THUMB_V4_TOP_LABEL_Y_RANGE` / `THUMB_V4_BOT_LABEL_Y_RANGE` | `(170, 390)` / `(980, 1450)` | `2:3` Shorts shelf-safe (`y >= 150`) upper-left 2–3w micro-label vertical bands [R65,TQ4] |
| `THUMB_V4_BOTTOM_TITLE_SAFE_Y` | `1520` | Bottom Shorts UI title safe zone (`y >= 1520` strictly clear of text) [R65,TQ4,TQ9] |
| `THUMBNAIL_REPORT_FILENAME` / `THUMBNAIL_QA_REPORT_FILENAME` | `"thumbnail_report.json"` / `"thumbnail_qa_report.json"` | Per-episode `TQ1–TQ9` thumbnail QA & SHA-256 report |
| `THUMBNAIL_SELECTED_FILENAME` / `THUMBNAIL_CONTACT_SHEET_FILENAME` | `"thumbnail_selected.png"` / `"thumbnail_contact_sheet.png"` | Selected cover PNG + full-size & `2:3` Shorts shelf contact sheet |
| `THUMB_CANDIDATE_SAMPLES_PER_CUT` | `3` | Clean intra-cut sample offsets |
| `THUMB_EXCLUDE_MODES` | `("split_hstack", "split_vstack")` | Split-screen cut modes excluded |
| `THUMB_EXCLUDE_OUTRO` | `True` | Excludes Act 6 from cover `outro_sky_card` |
| `THUMB_SCORE_WEIGHTS` | `{"sharpness": 0.25, "contrast": 0.20, "colorfulness": 0.10, "center_salience": 0.25, "intent": 0.20}` | Composite candidate frame scoring + wood-grain trap penalty |
| `THUMB_INTENT_BONUS` | `{"cover_sentence": 1.0, "cutaway_xray": 1.0, "brain_badge": 0.95, "act1": 0.6, "default": 0.0}` | Cutaway/glass-brain & cover-sentence intent bonus [R65] |
| `THUMB_SHORTS_SHELF_CROP_Y` | `(150, 1770)` | True YouTube Shorts `2:3` (`1080x1620`) shelf crop band [R65] |
| `THUMB_V8_Z_TOP_Y_RANGE` / `THUMB_V8_Z_BOT_Y_RANGE` | `(215, 395)` / `(1240, 1445)` | Diagonal Z-Pattern 2-chunk hook vertical bands (`< 1480px`, clearing shelf title mask) [R65,TQ4] |
| `THUMB_POINTER_RED_RGB` / `THUMB_POINTER_CYAN_RGB` / `THUMB_ACCENT_YELLOW_RGB` | `(255, 37, 37)` / `(0, 212, 255)` / `(255, 225, 74)` | `#FF2525` pointer/ruler, `#00D4FF` cyan & `#FFE14A` bottom hook fill [R65,TQ9] |
| `THUMB_MIN_SHARPNESS` | `60.0` | Minimum Laplacian focus variance at `TQ3` [TQ3] |
| `THUMB_MIN_LUMA_STD` | `38.0` | Minimum global luminance contrast `TQ3` [TQ3] |
| `THUMB_MIN_CENTER_SALIENCE` | `1.15` | Minimum centre- Canny edge `TQ2` [TQ2] |
| `THUMB_MIN_PAIRWISE_DIFF` | `15.0` | Minimum pairwise ROI pixel `R31` `TQ5` [R31,TQ5] |
| `THUMB_MIN_TEXT_CONTRAST` | `4.5` | Minimum hook fill vs local/stroke `TQ1` [TQ1] |
| `THUMB_LEGIBILITY_PREVIEW_W` | `160` | Simulated mobile Shorts shelf width `TQ1` [TQ1] |
| `THUMB_SAFE_Y_RANGE` | `(240, 1440)` | Safe vertical band inside centre `TQ4` [TQ4] |
| `THUMB_SAFE_MARGIN_X` | `80` | Minimum left/right horizontal `TQ4` [TQ4] |
| `THUMB_HOOK_MAX_WORDS` | `4` | Maximum word count for thumbnail `TQ7` [TQ7] |
| `THUMB_HOOK_MAX_CHARS` | `18` | Maximum character count for `TQ7` [TQ7] |
| `THUMB_HOOK_FONT_SIZE_RANGE` | `(150, 96)` | Auto-fit bundled hook font size |
| `THUMB_HOOK_STROKE_PX` | `10` | Dark outer stroke thickness (`12px` `#0A0F18` on `v8` Z-chunks) |
| `THUMB_MIN_FILE_BYTES` / `SHORTS_THUMB_MAX_BYTES` | `80_000` / `1_950_000` | Minimum & maximum PNG file size `R31` `TQ6` [R31,TQ6] |
| `DIORAMA_V7_REQUIRE_THUMBNAIL_BLOCK` | `True` | Requires + stamp headline `R65` [R65] |

## 8. R70 v2 / R70-M v3.1 Intuitive Hand-Drawn HERO Data Stamp, R71 Anatomy Leader-Line & ElevenLabs Music v2.5 (`pipeline/data_stamp_overlay.py`, `pipeline/charts/`, `pipeline/anatomy_label_overlay.py`, `pipeline/elevenlabs_music.py`)
| Constant | Value | Rule / Note |
|---|---|---|
| `DATA_STAMP_Y_FRAC_RANGE` / `UNIVERSAL_SAFE_X_RIGHT_PX` / `DATA_STAMP_HERO_MODE` | `(0.12, 0.62)` / `910` / `True` | 3-platform HERO safe-zone graph viewport (`Y >= 12%`, `X <= 910px`) [R70] |
| `DATA_STAMP_MIN_PER_EPISODE` / `DATA_STAMP_MAX_PER_EPISODE` / `DATA_STAMP_MAX_PANELS` / `DATA_STAMP_MAX_LAYERS_PER_PANEL` / `DATA_STAMP_MAX_GROUPS` | `2` / `2` / `1` / `2` / `3` | Hard cap `<= 2` single-panel (`1x1`) charts per episode/dossier (`R70-M1`, `R70-M4`, `R70-M9`) [R70-M] |
| `DATA_STAMP_MODES` / `DATA_STAMP_PRESETS` / `DATA_STAMP_LAYER_TYPES` | `("study", "illustrative")` / `("bar_compare", "arc_gauge", "dot_array", "line", "curve_marker", "scatter_fit")` / `("bar", "dot_array", "arc_gauge", "line", "slope", "function_curve", "scatter", "regression")` | 5 Intuitive Presets (`1x1` only; zero academic box/violin/raincloud/CI-band or `derived` mode) [R70-M] |
| `DATA_STAMP_BG_BLUR_SIGMA` / `DATA_STAMP_BG_DIM` / `DATA_STAMP_MIN_HOLD_SEC` | `14` / `0.35` / `0.6` | Feathered upper-scene focus-pull & post-sentence hold [R70] |
| `EXPRESSIVE_V8_BGM_MODE` / `EXPRESSIVE_V8_MUSIC_MODEL_ID` / `EXPRESSIVE_V8_DEFAULT_BGM_MOOD` | `"elevenlabs_music"` / `"music_v2_5"` / `"curious_marimba_strings"` | Official ElevenLabs `/v1/music` documentary BGM + `BGM_BANK_DIR` SHA-256 cache [R68] |
| `EXPRESSIVE_V8_BGM_DUCK_DB` / `EXPRESSIVE_V8_BGM_BREATH_DB` / `EXPRESSIVE_V8_ROOM_TONE_DBFS` | `-21.5` / `-16.5` / `-40.0` | Vocal-clear dynamic BGM ducking & studio room tone [R68] |
| `EXPRESSIVE_V8_CURVE_RAMP` / `EXPRESSIVE_V8_SYNTH_TONAL_FOLEY` | `False` / `False` | Smooth uniform playback speed & zero tonal sine foley [R68] |

## 9. Schema v8.3 Omni 1.2 Flash, Single-Start-Frame Default, 2.5D Micro-Acting Lexicon & Rigid Physics (`R55-B`, `R58-K`, `R68-A`)
| Constant | Value | Rule / Note |
|---|---|---|
| `FLOW_PRIMARY_OMNI_MODEL_KEY` / `FLOW_PRIMARY_OMNI_MODEL_LABEL` / `FLOW_LEGACY_OMNI_MODEL_KEY` / `FLOW_LEGACY_OMNI_MODEL_LABEL` / `FLOW_OMNI_CREDIT_COST_NO_REF` / `FLOW_OMNI_CREDIT_COST_WITH_REF` | `"macaron_cookie"` / `"Omni 1.2 Flash"` / `"abra"` / `"Omni 1.1 Flash"` / `24` / `24` | Primary Google Flow `Omni 1.2 Flash` (`24` credits/clip) with `Omni 1.1 Flash` & `0-credit` `Veo 3.1 - Lite` fallback [R5] |
| `FLOW_OMNI_EXTENDED_DURATION_CHOICES` / `FLOW_OMNI_ENABLE_EXTENDED_DURATIONS` / `FLOW_OMNI_ENABLE_NATIVE_1080P_DOWNLOAD` / `FLOW_OMNI_ENABLE_CONVERSATIONAL_EDIT` / `FLOW_OMNI_ENABLE_MULTI_INGREDIENTS_V83` / `FLOW_ENABLE_720P_LANCZOS_UNSHARP` / `FLOW_UI_CAPABILITIES_CACHE_FILE` | `(3, 5, 8, 10, 12, 15)` / `False` / `False` / `False` / `False` / `False` / `CHANNEL_ROOT / "flow_ui_capabilities.json"` | Phase 0 UI capability flags (`flow-probe`) & 720p sharpening guard [R5,C2,C9] |
| `FLOW_OMNI_BALANCE_SAFETY_MARGIN` / `compute_dynamic_omni_episode_budget(...)` | `20` / helper | Dynamic `All-Omni` episode budget (`credits_remaining - 20 // 24`) [R5,C3] |
| `TRANSLUCENT_BRAIN_V8_REFS_DIRNAME` / `TRANSLUCENT_BRAIN_V8_CANDIDATE_FILENAMES` | `"translucent_brain_v8_refs"` / `("cand_01_3q_subcortical_limbic_xray_9x16.png", ..., "cand_06_ghost_xray_contour_translucent_brain_9x16.png")` | 6-angle `1080x1920` Translucent 3D Human Brain reference anchor pack [R71] |
| `EXPRESSIVE_ACTING_LEXICON_PATH` / `EXPRESSIVE_V8_RIGID_PHYSICS_GRAMMARS` | `ASSETS_DIR / "expression_acting_lexicon.json"` / `("axial_portal_dive", "xray_peel_micro", "ghost_twin_offset", "lid_lift_reveal", "locked_exploded_vs_shatter", "blueprint_3d_extrusion")` | 12-archetype 2D ink micro-acting lexicon (`F1~F5`) & 6 rigid physics grammars (`expressive_reaction_closeup` in `EXPRESSIVE_V8_VISUAL_GRAMMARS`) [R68,R68-A] |
| `EXPRESSIVE_V8_SINGLE_START_FRAME_DEFAULT` / `EXPRESSIVE_V8_DAISY_CHAIN_END_FRAME_DEFAULT` / `EXPRESSIVE_V8_FORBID_SLOWMO_STRETCH` | `True` / `False` / `True` | Single-Start-Frame default (`End` slot reserved for `portal_to_brain` / `morph_transition`), `0%` slow-motion stretch (`M1`,`M3`) [R68] |
| `EXPRESSIVE_V8_KEYWORD_BEAT_TARGET_SEC` / `EXPRESSIVE_V8_DUAL_HARVEST_WINDOWS_SEC` / `EXPRESSIVE_V8_STATE_SWAP_MIN_HIST_CORR` / `EXPRESSIVE_V8_MIN_P15_CENTER_SHARPNESS` | `2.0` / `((0.25, 2.15), (5.20, 7.40))` / `0.90` / `1.65` | `2.0s` keyword impact cutter (`R58-K`), dual-harvest NLE windows (`A₁ -> B -> A₂`), `T2` state-swap histogram correlation, & `C1` mid-clip motion-blur spike gate [R58-K,R64] |
| `EXPRESSIVE_V8_CAMERA_Z_FORWARD_TARGET_RATIO` / `EXPRESSIVE_V8_CAMERA_FAST_FPV_MAX_RATIO` / `EXPRESSIVE_V8_CAMERA_ORBIT_MAX_RATIO` / `EXPRESSIVE_V8_CAMERA_LOCKED_MIN_RATIO` | `0.55` / `0.25` / `0.30` / `0.15` | `R55-B` Z-axis forward family (`gentle_push_in` + `fpv_dive_glide`), fast FPV `<= 25%`, single-scale Orbit `<= 30%`, locked/reaction `>= 15%` [R55-B] |

## 10. Rule R72 + R72-R Open-World Drone, Landmark Refs & Rule R73 US Native Spoken Narration (`pipeline/real_world_reference_builder.py`, `pipeline/prompt_quality_v5.py`, `pipeline/prosody.py`)
| Constant | Value | Rule / Note |
|---|---|---|
| `EXPRESSIVE_V8_DRONE_CAMERA_MOVES` / `EXPRESSIVE_V8_MIN_OUTDOOR_OR_ARCH_RATIO` / `EXPRESSIVE_V8_MIN_DRONE_FLIGHT_RATIO` / `EXPRESSIVE_V8_MAX_CONSECUTIVE_SAME_INDOOR_LOC` | `("drone_aerial_approach", "fpv_window_portal_breach", "drone_high_orbit_drop", "vertical_90_topdown_dive", "drone_skyline_pullback")` / `0.35` / `0.35` / `2` | `R72` open-world architectural scale (`>= 35%` outdoor/arch, `>= 35%` drone/FPV flight, `<= 2` consecutive indoor room) [R72] |
| `SHORTS_EXPRESSIVE_V8_CLIP_COUNT_MIN` / `SHORTS_EXPRESSIVE_V8_CLIP_COUNT_DEFAULT` / `SHORTS_EXPRESSIVE_V8_CLIP_COUNT_MAX` / `SHORTS_EXPRESSIVE_V8_CUT_COUNT_MIN` / `SHORTS_EXPRESSIVE_V8_CUT_COUNT_MAX` | `22` / `28` / `36` / `28` / `46` | `R72` fast-cut unique clip & EDL cut budget (`EXPRESSIVE_V8_LEGACY_INDOOR_CLIP_COUNT_RANGE = (18, 26)` preserved on `PRE_R72_FROZEN_V8_PROJECTS`) [R72] |
| `EXPRESSIVE_V8_FIRST_CUT_MAX_SEC` / `EXPRESSIVE_V8_FIRST_15S_MAX_CUT_SEC` / `EXPRESSIVE_V8_FIRST_15S_MIN_CUTS` / `EXPRESSIVE_V8_MAX_CUT_SEC` / `EXPRESSIVE_V8_AVG_CUT_TARGET_RANGE` | `2.60` / `3.20` / `5` / `4.80` / `(2.05, 3.30)` | `R72` fast-cut assembler rhythm (`EXPRESSIVE_V8_DRONE_PEAK_CORE_WINDOW_SEC = (0.45, 2.75)`) [R72] |
| `REAL_WORLD_REFS_QUARANTINE_ROOT` / `REAL_WORLD_REFS_MANIFEST_FILENAME` / `REAL_WORLD_REFS_MIN_DHASH_DISTANCE` / `REAL_WORLD_REFS_MIN_EDGE_ALIGNMENT` | `Path("/tmp/aab_real_refs")` / `"real_world_refs_manifest.json"` / `14` / `0.30` | `R72-R` 3-category Wikimedia real-world landmark quarantine & `RQ-Real` anti-pixel-reuse verification [R72-R] |
| `EXPRESSIVE_V8_US_NATIVE_OPENING_MODES` / `EXPRESSIVE_V8_DEFAULT_OPENING_MODE` / `EXPRESSIVE_V8_LEGACY_CASE_STAMP_OPENING_MODE` | `("paradox_question", "myth_flip_claim", "sensory_test", "action_first_stamp")` / `"paradox_question"` / `"case_stamp"` | `R73` 4 US-native opening modes (`8–18w` / `8–20w` `EXPRESSIVE_V8_R73_OPENING_WORD_RANGES`; `"In [Year]..."` S1 & `EXPRESSIVE_V8_BANNED_GENERIC_QUESTION_PREFIXES` blocked; `PRE_R73_FROZEN_V8_PROJECTS` preserved) [R73] |
| `EXPRESSIVE_V8_POST_HOOK_PAUSE_SEC` / `EXPRESSIVE_V8_POST_HOOK_PAUSE_RANGE_SEC` | `0.42` / `(0.38, 0.48)` | `R73` post-hook cognitive beat between `S1` hook and `S2` university credibility bridge [R73] |
| `EXPRESSIVE_V8_MAX_HARD_JARGON_TERMS` / `EXPRESSIVE_V8_IMMEDIATE_GLOSS_WINDOW_WORDS` | `2` / `8` | `R73` `Plain-First` jargon gate (`<= 2` hard neuro terms, immediate plain-English gloss within `+-8` words) [R73] |
| `SHORTS_EXPRESSIVE_V8_R73_SENTENCE_WORDS_MAX` / `EXPRESSIVE_V8_MAX_FK_GRADE` / `EXPRESSIVE_V8_ENDING_MODES` / `EXPRESSIVE_V8_DEFAULT_ENDING_MODE` | `22` / `6.2` / `("mic_drop", "seamless_loop")` / `"mic_drop"` | `R73` spoken brevity (`<= 22w`/sentence, `FK <= 6.2`), `EXPRESSIVE_V8_BANNED_AI_CLICHES`, `EXPRESSIVE_V8_US_NATIVE_PIVOT_BRIDGES`, & ending modes [R73] |

## 11. Rule R76 & R76-P — Solo `Siren` Voice × Deterministic `Blender 4.2` MNI152 3D Brain Simulator × Anti-Noise Pacing (`pipeline/brain_simulator_blender.py`, `pipeline/anatomy_label_overlay.py`)
| Constant | Value | Rule / Note |
|---|---|---|
| `ELEVENLABS_VOICE_SIREN_ID` / `EXPRESSIVE_V8_R76_VOICE_PRESET` | `"eXpIbVcVbLo8ZJQDlDnl"` / `"el_siren_v4"` | Solo `100%` narrator lock (`Siren`), `0` foil voices (`EXPRESSIVE_V8_FOIL_SENTENCE_RANGE = (0, 0)`) [R76] |
| `EXPRESSIVE_V8_CAMEO_COUNT_PER_EPISODE` / `PRE_R76_FROZEN_V8_PROJECTS` | `0` / `Ep #1..#8 v1` tuple | Retires `Mini-Cortex` cameos on new `v8` while preserving frozen `Ep #1..#8 v1` archives [R76] |
| `EXPRESSIVE_V8_BRAIN_SIM_DRONE_MOVES` / `DEFAULT_SIMULATOR_BLENDER_BIN` / `R76_BRAIN_SIM_SQ_PASS_REQUIRED` | `("sensory_to_brain_drone", "circuit_cooperation_drone", "global_system_orbit_drone")` / `~/opt/blender/blender` / `True` | Zero-glow MNI152 `Blender 4.2` Workbench brain simulator (`grammar="brain_simulator_3d"`, `SQ1..SQ6`) [R76] |
| `EXPRESSIVE_V8_UNIFIED_BRAIN_SIM_DURATION_RATIO_RANGE` / `EXPRESSIVE_V8_R76_BRAIN_REVEAL_WINDOW_FRAC` / `EXPRESSIVE_V8_R76_MAX_CONSECUTIVE_BRAIN_CUTS` | `(0.38, 0.48)` / `(0.16, 0.34)` / `6` | Unified `38%–48%` brain simulator EDL duration share across psychology & neuroscience [R76] |
| `EXPRESSIVE_V8_R76_CLIP_COUNT_RANGE` / `EXPRESSIVE_V8_R76_CUT_COUNT_RANGE` | `(15, 22)` / `(15, 22)` | Anti-noise 1:1 clip/cut budget (`0` spare-clip mid-sentence splits) [R76-P] |
| `EXPRESSIVE_V8_R76_HUMAN_MIN_CUT_SEC` / `EXPRESSIVE_V8_R76_BRAIN_SIM_MIN_CUT_SEC` / `EXPRESSIVE_V8_R76_MAX_CUT_SEC` / `EXPRESSIVE_V8_R76_AVG_CUT_TARGET_RANGE` | `2.80` / `3.80` / `6.50` / `(3.40, 5.20)` | Anti-noise cut duration floors, ceiling & target mean cut rhythm [R76-P] |
| `EXPRESSIVE_V8_R76_MIN_HUMAN_OUTDOOR_RATIO` | `0.25` | Minimum outdoor/architectural share computed across human diorama clips (`<= 2` consecutive same indoor loc) [R76] |

## 12. Rule R78-M / R78-H / R78-V Constants (`pipeline/config.py`, `pipeline/elevenlabs_tts.py`, `pipeline/prosody.py`)
| Constant | Value | Rule / Note |
|---|---|---|
| `R78M_BRAIN_MATERIAL_MODES` | `("xray_glass", "cool_matte_silver_31")` | Dual hero brain materials: Mode 1 X-Ray Glass & Mode 2 Cool Matte Silver (`#9CA5AC~#C7CCD2`, `B > R`, zero `#DFDDD7` warm ivory) [R78-M] |
| `EXPRESSIVE_V8_BRAIN_SIM_DRONE_MOVES` | `+ ("1p_nerve_canyon_drone", "3p_region_shutdown_pullout")` | Extends MNI152/Flow drone paths with 1st-person nerve canyon dive & 3rd-person shutdown pullout (`clip_start=0.0015`) [R78-M] |
| `EXPRESSIVE_V8_PROSODY_GEARS` / `EXPRESSIVE_V8_PROSODY_GEAR_RATES` | `+ ("surprised_lift", "insider_reveal", "hushed_suspense", "deadpan_drop")` (`1.06`, `1.04`, `1.02`, `0.98`) | 5-tone expressive `Solo Siren` micro-rates + `R78V_GEAR_VOICE_SETTINGS` `(tag, stability, style)` [R78-V] |
| `PROSODY_P11_F0_SPAN_MIN_ST` / `PROSODY_P11_LIFT_VS_DROP_MIN_ST` | `6.5` / `1.2` | Acoustic pitch-variance gate `P11_siren_5tone_f0_range` (`p90-p10 F0 >= 6.5 st`, lift vs drop `>= 1.2 st`) [R78-V] |

## 13. Rule R80 — `신비한 건축사전` 3D Volumetric Arrow Diorama × `@RicksClips3000` Spatial Micro-Relay (`pipeline/spatial_arrow_guide.py`, `pipeline/diorama_assembler.py`)
| Constant | Value | Rule / Note |
|---|---|---|
| `EXPRESSIVE_V8_VISUAL_GRAMMARS` / `EXPRESSIVE_V8_DRONE_CAMERA_MOVES` | `+ ("spatial_3d_arrow_diorama",)` / `+ ("drone_landmark_ascend", "topdown_3d_route_glide")` | Native 3D volumetric `#FF2525` spatial arrow diorama grammar + 2-cut landmark-ascend -> 90° top-down route relay [R80] |
| `EXPRESSIVE_V8_SPATIAL_RELAY_MIN_CUT_SEC` / `R80_SPATIAL_FLIGHT_SPEED_RAMP_RANGE` | `2.20` / `(1.24, 1.42)` | `@RicksClips3000` `2.4s–3.2s` 2-cut spatial micro-relay floor inside `R76-P` + ballistic impulse speed-ramp window [R80] |
| `R80_3D_ARROW_ACCENT_HEX` / `R80_SPATIAL_ARROW_MODES` | `"#FF2525"` / `("adaptive_landmark_zigzag", "fixed_linear_corridor", "doorway_boundary_sever", "dual_speed_race_lanes", "split_hemisphere_watch")` | `RQ-Arrow` CV tortuosity (`>= 1.35` zigzag vs `<= 1.08` straight) & physical ground-shadow verification [R80] |

## 14. Rule R81 & R82 — XL Hand-Ink Callout Tracking & Dual-Speed Cognitive Pacing (`pipeline/anatomy_label_overlay.py`, `pipeline/config.py`, `pipeline/diorama_assembler.py`)
| Constant | Value | Rule / Note |
|---|---|---|
| `R81_CALLOUT_XL_SINGLE_LINE_MIN_PX..MAX_PX` / `R81_CALLOUT_XL_STACK_MIN_PX..MAX_PX` / `R81_CALLOUT_UNDERLINE_GAP_PX` | `72..84` / `64..82` / `10` | XL mobile `PatrickHand` sizing, auto 2-line hub stack & `0px` strikethrough gap [R81] |
| `R82_CLIP_COUNT_RANGE` / `R82_CUT_COUNT_RANGE` / `PRE_R82_FROZEN_V8_PROJECTS` | `(18, 28)` / `(18, 28)` / `Ep #1..#12` | Harmonized 1:1 clip & cut budget bridging `R76` & `R72` (`v8_ep13+` & `*_r82`) [R82] |
| `R82_HUMAN_MIN_CUT_SEC` / `R82_HUMAN_MAX_CUT_SEC` / `R82_FIRST_CUT_MAX_SEC` / `R82_FIRST_15S_MAX_CUT_SEC` / `R82_FIRST_15S_MIN_CUTS` | `1.90` / `4.25` / `3.20` / `3.80` / `4` | Crisp 2-beat purposeful human action cuts (`human_action_relay`, zero `5.8s` static filler) [R82] |
| `R82_BRAIN_MIN_CUT_SEC` / `R82_BRAIN_MAX_CUT_SEC` / `R82_BRAIN_DURATION_RATIO_RANGE` / `R82_BRAIN_CLIP_RATIO_RANGE` / `R82_AVG_CUT_TARGET_RANGE` | `4.20` / `6.80` / `(0.42, 0.58)` / `(0.28, 0.55)` / `(2.60, 4.40)` | Poised anti-spin 3D brain inspection (`<=12-15°` single-plane parallax) across `42–58%` episode share [R82] |

## 15. Rule R84 — Legacy `Blender 4.2 Cycles` MNI152 Off-Screen Guide & Archive (`pipeline/brain_simulator_blender.py`, `pipeline/config.py`)
| Constant | Value | Rule / Note |
|---|---|---|
| `R84_BLENDER_RENDER_ENGINE` / `R84_CYCLES_SAMPLES` / `R84_TARGET_SUBSURF_LEVELS` | `"CYCLES"` / `16` / `2` | `OpenImageDenoise` + `AgX` matte medical subsurface PBR (retired from screen under R85; off-screen guide only) [R84,R85] |
| `R84_MATTE_ROUGHNESS_RANGE` / `R84_DEEP_CUTAWAY_REGIONS` | `(0.58, 0.65)` / `14` deep parcels | View-aligned `EXACT` Boolean surgical cutaway & dorsal `Corpus Callosum` landmark contrast [R84] |
| `R84_STACKED_CUTAWAY_ZOOM` / `R84_DASHED_BASELINE_WIDTH_PX` / `R84_DASHED_BASELINE_DASH_GAP_PX` | `2.5` / `3` / `(22, 9)` | `9:16` Top/Bottom `2.5x` `split_vstack` cohort compare + `#EDF2F7` `1.0x` dashed baseline contour [R84] |

## 16. Rule R85 & R86 — `100%` Google Flow Ep #31 Brain, QA Honesty & Semantic Beat Contract (`pipeline/config.py`, `pipeline/porcelain_anchor_pack.py`, `pipeline/flow_prompt_builder.py`)
| Constant | Value | Rule / Note |
|---|---|---|
| `UNMANNED_QA_SIGNOFF_DEFAULT` / `R85_BRAIN_RENDER_ENGINE` | `False` / `"google_flow"` | Prohibits unmanned semantic sign-off (`REVIEW_PENDING`) & locks `100%` Google Flow Ep #31 brain rendering [R85] |
| `R85_FLOW_BRAIN_SHOT_ROTATION` | `("xray_head_dive", "split_cutaway", "sulcal_cyan_dive", "vessel_csf_macro", "1p_tract_canyon", "3p_shutdown_or_top_bottom")` | 6-Scale Ep #31 `#9CA5AC–#C3C9CE` + `#27D8FF` brain shot rotation [R85] |
| `R85_ANATOMY_VIEWPOINT_RULES` / `R85_MNI152_GUIDE_TMP_ROOT` | `4` region rules / `Path("/tmp/aab_real_refs")` | Enforces anatomically valid viewpoints (`insula` != `midsagittal`, `hippocampus` != dorsal callosum) & off-screen MNI152 guide root [R85,R85-R] |
| `R86_VISUAL_PROOF_TYPES` / `R86_MAX_CONSECUTIVE_SAME_PROOF` / `R86_MAX_REACTION_CUTS_PER_EPISODE` | `8` types / `2` / `2` | Semantic Beat Contract proof taxonomy (`< 3` consecutive same proof, `<= 2` `reaction` cuts/episode) [R86] |
