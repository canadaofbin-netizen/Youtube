# Production Constants — Single Numeric Source of Truth

Owner of all numeric thresholds, budgets, and timing constants across the ALL ABOUT BRAIN workspace. Every constant below maps 1:1 to [pipeline/config.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/config.py). No other rule or skill file may restate numeric values; other documents reference these constant names directly.

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
| `DEFAULT_FLOW_MODEL` | `"Omni 1.1 Flash"` | model | Default Google Flow primary video engine |
| `FLOW_MODEL_QUALITY` | `"Omni 1.1 Quality"` | model | High-detail Google Flow video engine |
| `ALLOWED_FLOW_MODELS` | `["Omni 1.1 Flash", "Omni 1.1 Quality", "Veo 3.1 - Lite [Lower Priority]"]` | list | Permitted Google Flow Dual-Tier engines (`Omni 1.1` primary -> `0-credit` auto-fallback, R5) |
| `FLOW_DEFAULT_VOICE` | `"Puck"` | voice | Exclusive male documentary narrator voice (R13) |
| `FLOW_ALLOWED_VOICES` | `("Puck",)` | tuple | Permitted voices (Aoede and female voices banned) |
| `FLOW_VOICE_PROMPT_DESCRIPTOR` | `"Consistent deep male baritone documentary narrator"` | str | Voice descriptor injected in the `Voice:` prompt clause (R13, R40-A) |
| `PUCK_F0_RANGE_HZ` | `(85.0, 185.0)` | Hz | Accepted fundamental-frequency range for Puck voice verification |
| `NATIVE_FLOW_WPS` | `2.7` | words/s | Target speaking rate in native Google Flow generation |
| `EFFECTIVE_WPS` | `2.7` (`round(2.7 * 1.00, 3)`) | words/s | Effective speaking rate after `AV_SPEEDUP_FACTOR` (`1.00`) |
| `FLOW_ACTIVE_VIDEO_MODEL` / `FLOW_PRIMARY_VIDEO_MODEL` | `"Omni 1.1 Flash"` | model | Primary Flow engine when AI credits are available (`omni_1_1_flash`) |
| `FLOW_ZERO_CREDIT_MODEL` | `"Veo 3.1 - Lite [Lower Priority]"` | model | Automatic `0-credit` fallback engine (`veo_3_1_lite_low_priority`) when monthly credits are exhausted |
| `FLOW_ENGINE_MODES` / `DEFAULT_FLOW_ENGINE_MODE` | `("auto", "omni", "zero-credit")` / `"auto"` | tuple / str | Credit-aware Dual-Tier engine selection policy (`R5`) |
| `FLOW_VIDEO_MODEL_PROFILES` | Omni: 4s / 6s / 8s / 10s (`max_sec=10`, `max_sec_with_ingredient=8`) · Veo 3.1 Lite LP: 4s / 6s / 8s (`0 credits`) | dict | Verified Flow settings-pane profiles (`Omni 1.1 Flash` primary -> `Veo 3.1 - Lite [Lower Priority]` `0-credit` fallback) |
| `FLOW_BANNED_VIDEO_MODEL_MARKERS` / `FLOW_ZERO_CREDIT_TEXT` | `("Veo 2",)` / `"Generating will use 0 credits"` | tuple / str | Banned legacy model marker & `0-credit` UI verification string |
| `FLOW_ZERO_CREDIT_IMAGE_MODEL` / `FLOW_ZERO_CREDIT_IMAGE_FAMILY_ID` / `FLOW_ZERO_CREDIT_IMAGE_BATCH_COUNT` | `"Nano Banana 2.1"` / `"beluga_display"` / `4` | model / str / count | Native Google Flow `0-credit` `Image` engine (`x4` candidates per prompt, auto-selecting highest-scoring QA-passing still) |
| `FLOW_ZERO_CREDIT_MAX_CONCURRENT_RENDERS` / `FLOW_ZERO_CREDIT_VIDEO_MAX_BATCH` | `4` / `4` | renders / count | Optimal `0-credit` concurrent video render ceiling (`4` parallel tabs × `x1` for full episodes; scales up to `x4` per prompt when rendering `1–2` clips) |
| `REENACT_IMAGE_BACKENDS` / `DEFAULT_REENACT_IMAGE_BACKEND` | `("flow", "gemini")` / `"flow"` | tuple / str | Reference/reenactment image generation backends (`"flow"` native Google Flow `0-credit` `x4` primary) |
| `FLOW_CLIP_DURATION_TARGET` | `"10s"` | mode | Omni default (`10s` both with and without static PNG references) |
| `FLOW_ALLOWED_DURATION_TARGETS` | `("4s", "6s", "8s", "10s")` | tuple | From the active model profile; other requests are clamped |
| `FLOW_SHORT_CLIP_MAX_WORDS` | `19` | words | Max words for dynamic `"8s"` clip selection (`<= 32` syllables) |
| `FLOW_SHORT_CLIP_MAX_SYLLABLES` | `32` | syllables | Max syllables for dynamic `"8s"` clip selection |
| `FLOW_CLIP_SAFE_MAX_SYLLABLES` | `48` | syllables | Syllable ceiling above which `"10s"` clips flag tail-cutoff risk |
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

## 2-B. Prompt System v5 — Modes, Acting, Plain Language, Voice, Longform (2026-10-24)

| Constant | Value | Unit | Meaning |
|---|---|---|---|
| `PROMPT_SCHEMA_VERSION_V5` | `5` | — | Schema version written for v5 plans / prompt files |
| `PROMPT_SCENE_WORDS_MAX_V5` | `95` | words | Max scene words in v5 prompts (Action-Physics needs room; excludes `FLOW_MOTION_STYLE_V5`) |
| `FLOW_ASPECT_SHORTS` / `FLOW_ASPECT_LONGFORM` | `"9:16"` / `"16:9"` | aspect | `flow_prompt_prefix(aspect)` (R50) |
| `FLOW_ASPECT_LABELS` | `{"9:16": "9:16 vertical", "16:9": "16:9 horizontal"}` | — | Prefix wording per aspect |
| `FLOW_MOTION_STYLE_V5` | `"Articulated matte-white porcelain figures move with fluid, natural human motion; key action stays centred in frame."` | str | Appended after every v5 scene (R47, R50) |
| `FLOW_VOICE_PROMPT_DESCRIPTOR_V5` | `"Same calm male documentary narrator in every clip, warm mid-low baritone, steady even pitch, relaxed measured pace, neutral American accent, no dramatic pitch swings"` | str | v5 `Voice:` clause (R13, R49) |
| `FLOW_LEGACY_VOICE_LABELS` | v4 descriptors | tuple | Still accepted by `validate_flow_prompts` |
| `VISUAL_MODES` | `("BEHAVIORAL_PSYCH", "HYBRID", "NEURO_BIOLOGY")` | — | R45 |
| `BRAIN_SETTINGS` | `("drill_down", "brain_void")` | — | Settings counted as brain clips |
| `ALLOWED_SETTINGS_V5` | `("real_env", "drill_down", "brain_void", "pull_out")` | — | Valid `shots[role].setting` values |
| `MAX_BRAIN_CLIPS_BY_MODE` | `{BEHAVIORAL_PSYCH: 0, HYBRID: 2, NEURO_BIOLOGY: 4}` | clips | R45 |
| `MAX_ANATOMY_TERMS_BY_MODE` | `{BEHAVIORAL_PSYCH: 1, HYBRID: 2, NEURO_BIOLOGY: 4}` | terms | Distinct region names per script (R15 v5) |
| `MODE_ROLE_SETTINGS` | HYBRID: pivot `drill_down`, mechanism/step1 `brain_void`, step2 `pull_out`, rest `real_env`; NEURO: crisis `drill_down`, pivot/mechanism/step1/step2 `brain_void`, step3 `pull_out`, rest `real_env`; BEHAVIORAL: all `real_env` | — | Default setting per role (R45) |
| `ICONIC_SCENE_MAX_CLIP` | `2` | clip | Iconic scene appears in clip 1..2 (R46) |
| `READABILITY_SCRIPT_FK_MAX` | `8.0` | grade | Flesch-Kincaid, whole script |
| `READABILITY_CLIP_FK_MAX` | `11.0` | grade | Flesch-Kincaid, any clip |
| `JARGON_TERMS_MAX` | `1` | terms | Non-anatomy technical terms per script |
| `SECOND_PERSON_CLIPS_MIN` | `1` | clips | Clips that speak to "you / your" |
| `VOICE_F0_CLIP_DEV_MAX_ST` | `1.5` | semitones | Clip median F0 vs project median (R49) |
| `VOICE_F0_ADJ_JUMP_MAX_ST` | `2.0` | semitones | Adjacent-clip F0 jump |
| `VOICE_F0_SPREAD_MAX_ST` | `3.0` | semitones | Max − min F0 across the project |
| `VOICE_REGEN_MAX_ROUNDS` | `4` | rounds | Flow regeneration rounds for failing clips |
| `VOICE_FALLBACK_ENABLED` | `True` | bool | Local TTS fallback allowed (decision 2026-10-24) |
| `VOICE_FALLBACK_ENGINE` | `"kokoro-onnx"` | — | Free local engine (Apache-2.0) |
| `VOICE_FALLBACK_VOICE` | `"am_fenrir"` | voice | Fixed fallback narrator (deep cinematic baritone) |
| `VOICE_FALLBACK_SPEED` | `1.00` | ratio | Kokoro speaking speed (natural `1.00x` documentary pace) |
| `VOICE_FALLBACK_MODEL_DIR` | `~/.cache/aab_tts` | path | `kokoro-v1.0.onnx`, `voices-v1.0.bin` |
| `VOICE_FALLBACK_VIDEO_SPEED_RANGE` | `(0.75, 1.15)` | ratio | Video speed range when fitting clips to TTS lines (outside → warning, never frame cloning) |
| `RESEARCH_DOSSIERS_DIRNAME` / `DOSSIERS_DIR` | `"research_dossiers"` / `CHANNEL_ROOT / "research_dossiers"` | dir / path | `BCI_Shorts_Channel/research_dossiers/<slug>/` (R44) |
| `ASSET_LIBRARY_DIRNAME` | `"asset_library"` | dir | `BCI_Shorts_Channel/asset_library/index.jsonl` (R50) |
| `LONGFORM_TARGET_MIN_SEC` / `LONGFORM_TARGET_MAX_SEC` | `480` / `900` | s | Longform built from proven Shorts |
| `REF_IMAGES_DIRNAME` | `"reference_images"` | dir | `03_visuals/reference_images/` & `research_dossiers/<slug>/reference_images/` (R51) |
| `MIN_REF_IMAGES_PER_PROJECT` | `6` | images | Minimum reference images per project (cast, env, hero prop, scenes/clips; up to 10 per-clip keyframes) |
| `MIN_REF_IMAGE_SIZE_BYTES` | `30_000` | bytes | Minimum file size per reference PNG/JPG |
| `REF_IMAGE_MIN_WIDTH_SHORTS` / `REF_IMAGE_MIN_HEIGHT_SHORTS` | `720` / `1280` | px | Minimum resolution for `9:16` reference images |
| `REF_IMAGE_LUMA_MIN` / `REF_IMAGE_LUMA_MAX` | `70.0` / `242.0` | luma (0–255) | R14-A bright high-key daylight exposure window |
| `REF_IMAGE_CONTRAST_STD_MIN` | `22.0` | luma std | Minimum dynamic contrast standard deviation |
| `REF_IMAGE_SHARPNESS_MIN` | `45.0` | Laplacian var | Minimum focus sharpness threshold |
| `REF_IMAGE_EDGE_DENSITY_MIN` | `0.015` | ratio | Minimum Canny structural edge density |
| `REF_IMAGE_PORCELAIN_RATIO_MIN` | `0.04` | ratio | Minimum matte-white porcelain surface presence in subject zone |
| `REF_IMAGE_HUMAN_SKIN_MAX` | `0.12` | ratio | Maximum allowed human flesh-tone ratio (blocks photoreal human skin on mannequins) |
| `REF_IMAGE_CROSS_HIST_CORR_MIN` | `0.55` | corr | Minimum HSV palette correlation across same-scene reference images |
| `REF_IMAGE_CROSS_LUMA_SPREAD_MAX` | `55.0` | luma | Maximum luminance spread across same-scene reference images |
| `REF_IMAGE_CAST_CHROMA_DRIFT_MAX` | `16.0` | LAB delta | Maximum chrominance drift across same-cast appearances |
| `REF_IMAGE_CLIP_CONTINUITY_CORR_MIN` | `0.55` | corr | Minimum HSV correlation between rendered video clip and its bound reference image |
| `REF_IMAGE_MAX_REGEN_ROUNDS` | `3` | rounds | Max automatic regeneration rounds in Flow Image mode when a reference image fails QA |
| `REF_IMAGE_MIN_DHASH_DISTANCE` | `6` | bits | Q10 duplicate threshold between clip keyframes |
| `REF_IMAGE_BIOLUM_MIN` | `0.005` | ratio | Q6 minimum 4-point colour-code pixels in brain shots |
| `REF_IMAGE_SOURCES_PRE_GENERATION` | `("flow_image_generation", "gemini_image_generation")` | tuple | Provenance values that count for `pre_generation_ready` |
| `REF_IMAGE_SOURCE_EXTRACTED` | `"extracted_from_clip"` | tag | Audit-only frames cut out of finished clips |
| `SCENE_BLUEPRINT_FILENAME` | `"scene_blueprint.json"` | file | R52 blueprint (`03_visuals/`) |
| `GENERATION_PACKETS_DIRNAME` | `"generation_packets"` | dir | R52 per-clip packets (`03_visuals/`) |
| `GENERATION_BACKENDS` | `("flow", "gemini_app")` | tuple | Clip generators |
| `VOICE_SOURCES` / `DEFAULT_VOICE_SOURCE` | `("tts", "native")` / `"tts"` | mode | tts = am_fenrir voiceover in Gear 4, clip prompts ask for ambience only |
| `CLIP_MAX_RENDER_SEC` | `10` | s | Omni 1.1 Flash ceiling (without ingredient) |
| `CLIP_MAX_RENDER_SEC_WITH_REFERENCE` | `8` | s | Render ceiling (`8s`) when a reference ingredient is attached (`max_sec_with_ingredient = 8`) |
| `GEMINI_APP_MAX_RENDER_SEC` | `8` | s | Legacy Gemini app render length (not used for video generation per R5) |
| `TIMED_BEAT_WINDOWS` | `((0, 3), (3, 6), (6, 8))` | s | action / prop change / reaction windows in the 8s timed video prompt |
| `BLUEPRINT_MIN_EVIDENCE_ICONIC` | `1` | count | timecode evidence required for the iconic scene |
| `DOSSIER_MIN_SOURCES` | `6` | count | R44-D depth standard |
| `DOSSIER_MIN_FOLLOWUP_SOURCES` | `2` | count | replication / follow-up / review |
| `DOSSIER_MIN_CORE_FACTS` | `8` | count | `{fact, source_id}` entries |
| `DOSSIER_MIN_MEDIA` | `2` | count | media refs |
| `DOSSIER_MIN_ANALYZED_MEDIA` | `1` | count | media analysed on disk |
| `DOSSIER_MIN_KEYFRAMES` | `8` | count | keyframes per analysed media |
| `DOSSIER_MIN_MEDIA_TIMECODES` | `2` | count | timecoded shot notes per media |
| `DOSSIER_MIN_STORY_CHARS` | `6000` | chars | master story length |
| `DOSSIER_MIN_ICONIC_POSITIONS` | `2` | count | who / where / facing entries |
| `DOSSIER_MIN_ICONIC_PROPS` | `2` | count | props with period_detail + physical_behavior |

---

## 2-C. Prompt & Assembly System v6 — Neuro-Diorama 3-Minute Long-Short (R56–R61, 2026-10-26)

| Constant / Helper | Value | Unit | Meaning |
|---|---|---|---|
| `PRODUCTION_PROFILES` | `("classic_v5", "neuro_diorama")` | tuple | Supported channel production profiles |
| `DEFAULT_PRODUCTION_PROFILE` | `"neuro_diorama"` | str | Default profile for new 3-minute US English Long-Shorts |
| `PROMPT_SCHEMA_VERSION_V6` | `6` | — | Schema version for `neuro_diorama` plans / prompt packages |
| `DIORAMA_ZERO_FLESH_LOCK` | `True` | bool | Zero human skin, eyes, faces, full-body mannequins, crowds, or animals (R56) |
| `DIORAMA_ALLOW_CRYSTAL_SPECIMEN` | `True` | bool | Allows pedestal-mounted `satin-frosted optical crystal` head bust / hand sculpture for trajectory or sensory scenes (R56) |
| `DIORAMA_CRYSTAL_SPECIMEN_MAX_RATIO` | `0.20` | ratio | Ceiling on crystal partial-specimen clips (`<= 20%`); `>= 80%` uninhabited Ghost-Lab dioramas & automata |
| `DIORAMA_BACKDROP_STYLE` / `DIORAMA_LIGHTING_STYLE` | `"deep midnight-navy studio void"` / `"cinematic chiaroscuro rim lighting"` | str | Channel-signature dark midnight-navy backdrop (`RGB_DEEP_NAVY`) and dramatic rim lighting across all `neuro_diorama` clips (R56) |
| `DIORAMA_BRAIN_RENDER_MODES` | `("matte_white_cortical_sulcal_glow", "translucent_smoked_glass_subcortical_xray")` | tuple | 2-mode isolated dark-void 3D anatomical brain visualization (opaque matte-white cortical sulcal glow vs semi-translucent smoked-glass X-ray subcortical glow) (R56) |
| `DIORAMA_VISUAL_GRAMMARS` | `("arch_cutaway_diorama", "kinetic_trace_automata", "recurring_gauge_motif", "tactile_token_grid", "literal_analogy_cutaway", "arch_brain_maquette", "frosted_crystal_specimen")` | tuple | Permitted `6+1` visual grammars in `neuro_diorama` incl. 1:1 literal analogy dioramas (R56, R57-V) |
| `DIORAMA_CAMERA_MOVES` | `("smooth_tilt_up", "smooth_tilt_down", "horizontal_tracking_pan", "isometric_push_in", "locked_macro_gauge", "dynamic_dolly_rush_in", "orbital_3d_arc_sweep", "crane_swoop_dive", "low_angle_chase_track", "vertical_rocket_ascent", "fpv_trench_passthrough", "pullback_parallax_reveal")` | tuple | Permitted single-axis smooth & dynamic 3D probe/orbital/crane/chase camera moves in `neuro_diorama` (R56) |
| `DEFAULT_DIORAMA_CAMERA_PROFILE` / `DIORAMA_DYNAMIC_3D_CAMERA_MOVES` | `"dynamic_3d_cinema_rig"` / `("dynamic_dolly_rush_in", "orbital_3d_arc_sweep", "crane_swoop_dive", "low_angle_chase_track", "vertical_rocket_ascent", "fpv_trench_passthrough", "pullback_parallax_reveal")` | str / tuple | Default Dynamic 3D Cinema Camera Rig profile and 7 volumetric 3D camera moves for all new `neuro_diorama` productions (R56) |
| `DIORAMA_MOTIF_APPEARANCES_MIN` / `DIORAMA_MOTIF_APPEARANCES_MAX` | `4` / `8` | clips | Recurring analog gauge prop appearances across Acts 1–6 (R56) |
| `DIORAMA_SCENE_WORDS_MIN` / `DIORAMA_SCENE_WORDS_MAX` | `45` / `115` | words | Visual scene word bounds per `neuro_diorama` Flow clip prompt |
| `DIORAMA_ACT_COUNT` | `6` | acts | 6-Act Neuro-Documentary narrative spine (R57) |
| `DIORAMA_SENTENCE_COUNT_MIN` / `DIORAMA_SENTENCE_COUNT_MAX` | `48` / `58` | sentences | High-density US English storyteller sentence count per 3-minute Long-Short (R57) |
| `DIORAMA_SENTENCE_WORDS_MAX` / `DIORAMA_V7_SENTENCE_WORDS_MAX` / `DIORAMA_US_SENTENCE_WORDS_MAX` | `15` / `18` / `13` | words | Max words in any single `neuro_diorama` sentence (`15` Schema v6; `18` Schema v7 `R57-C`; `13` US 45+ ear-first `dynamic_us_v7`) |
| `DIORAMA_WORD_COUNT_MIN` / `DIORAMA_WORD_COUNT_MAX` / `DIORAMA_US_WORD_COUNT_MAX` | `430` / `505` / `470` | words | Total spoken US English word budget (`430..505` legacy `dynamic_rush_v7`; `430..470` US 45+ `dynamic_us_v7` landing `~154–168s`) (R57) |
| `DIORAMA_V7_MAX_FK_GRADE` / `DIORAMA_ADJACENT_OPENER_WINDOW` / `DIORAMA_MAX_4GRAM_JACCARD` | `5.5` / `4` / `0.08` | grade / episodes / Jaccard | US ear-first Flesch-Kincaid grade cap (`<= 5.5`) and Anti-Clone structural opener/pivot rotation across adjacent `4` episodes (`<= 0.08` 4-gram Jaccard) |
| `DIORAMA_COLD_OPEN_S3_BANK` / `DIORAMA_CRISIS_BEAT_BANK` / `DIORAMA_MECHANISM_PIVOT_BANK` / `DIORAMA_EUREKA_REVEAL_BANK` / `DIORAMA_TAKEAWAY_BRIDGE_BANK` / `DIORAMA_MIDPOINT_REHOOK_BANK` | `12` / `12` / `12` / `12` / `12` / `8` phrases | tuple | Rotating US Anti-Clone structural transition banks replacing single hardcoded catchphrases across episodes (`R57-H2` / `R63-P`) |
| `DESCRIPTION_EDITORIAL_TEMPLATES` / `AI_DISCLOSURE_SENTENCE` / `MAX_DAILY_SUBSCRIBER_NOTIFICATIONS` / `PRE_R66_FROZEN_PROJECT_PREFIXES` | `("clinical_brief", "experiment_chronicle", "myth_vs_mechanism", "everyday_neurobiology")` / R4 AI disclosure sentence / `3` / `diorama_01..26 + gage_* + psych_*` | tuple / str / int / tuple | 4-layout editorial description templates (`publish.py`), R4 AI disclosure text, 24h subscriber notification cap (`R30`), and frozen pre-R66 project prefix lock (`studio_batch_100_scheduler.py`) |
| `DIORAMA_BANNED_SLOGAN_OPENERS` / `DIORAMA_BANNED_WEAK_HOOK_PREFIXES` / `DIORAMA_REQUIRE_SIGNATURE_HOOKS` | `("university brain science, made simple", ...)` / `("imagine ", "picture this", "have you ever ", "what if ", "suppose ")` / `True` | tuple / tuple / bool | Generic channel-slogan & weak hypothetical cold-opens banned (`0.0s` immediate concrete paradox hook required, `R57` / `R57-H`) + restored R24 / R26 hooks |
| `DIORAMA_V7_REQUIRE_COLD_OPEN` / `DIORAMA_V7_COLD_OPEN_S1_MAX_WORDS` / `DIORAMA_V7_COLD_OPEN_S2_MAX_WORDS` / `DIORAMA_V7_COLD_OPEN_S2_PREFIXES` / `DIORAMA_V7_COLD_OPEN_CASE_STAMP_PREFIX` | `True` / `18` / `12` / `("yet ", "but ", "and yet ", "still ", "meanwhile ")` / `"this is the true story of "` | bool / words / words / tuple / str | R57-H2 Schema v7 3-sentence cold-open enforced by `prompt-gate` (`validate_cold_open_v7`): S1 myth-flip `!` → S2 contrast → S3 case stamp from `DIORAMA_COLD_OPEN_S3_BANK`; opt-out `visual_plan.require_cold_open_v7 = false` |
| `DIORAMA_BANNED_AI_CLICHES` / `DIORAMA_BANNED_SEMINAR_TRANSITIONS` | `("delve into", "let's unpack", "underscore", "pivotal", "paramount", "tapestry", "furthermore", "moreover", "consequently", ...)` / `("moving on to", "this paper looks at", "the main region here is", "to wrap up and bring everything together", ...)` | tuple / tuple | YouTube Natural Script ear-first spoken lock (`R57-C`): bans AI-essay giveaway vocabulary AND academic slide-seminar transitions while enforcing conversational documentary flow |
| `DIORAMA_DURATION_MIN_SEC` / `DIORAMA_DURATION_TARGET_SEC` / `DIORAMA_DURATION_MAX_SEC` | `140.0` / `158.0` / `179.0` | s | Target brisk Long-Short duration window (`~150–165s`) safely below YouTube's `180.00s` Long-form cutoff (R57) |
| `SHORTS_HARD_CEILING_SEC` / `SHORTS_HARD_CEILING_FRAMES` | `179.0` / `5370` | s / frames | Hard mux ceiling at `30 fps` (`179.0s`) preventing accidental `>180s` classification (R57) |
| `DIORAMA_NUMBER_ANALOGY_MAX_SENTENCE_GAP` | `1` | sentences | Max sentence distance from a core quantitative metric to its everyday physical analogy (R57) |
| `DIORAMA_CLIP_COUNT_MIN` / `DIORAMA_CLIP_COUNT_DEFAULT` / `DIORAMA_CLIP_COUNT_MAX` | `20` / `48` / `240` | clips | 1:1 Zero-Reuse Flow base motion clips (`default 48` balanced documentary pacing for `~46–48` cuts; `20..240` supported) (R58/R66) |
| `DIORAMA_MAX_CLIP_REUSE` / `DIORAMA_SHARD_MAX_CLIPS` | `1` / `14` | uses / clips | Strict `0%` reuse lock (`1` cut per clip at `1.00x`) and max clips per sharded Flow project tab (R58) |
| `DIORAMA_CLIP_RENDER_SEC` | `8` | s | Render duration per base Flow clip |
| `DIORAMA_SLICE_WINDOWS_SEC` | `((0.20, 2.45), (2.60, 4.85), (5.00, 7.25))` | s | Legacy 3-window intra-clip slices (only used when `zero_clip_reuse == False`) (R58) |
| `DIORAMA_SLICE_CROPS` | `(1.00, 1.12, 1.22)` | zoom | Legacy progressive framing (`1.00x` full framing locked when `zero_clip_reuse == True`) |
| `DIORAMA_TARGET_CUT_MIN` / `DIORAMA_TARGET_CUT_MAX` / `PORCELAIN_V7_TARGET_CLIP_MIN` / `PORCELAIN_V7_TARGET_CLIP_MAX` / `PORCELAIN_V7_MAX_HOLD_SENTENCES` / `PORCELAIN_V7_LITERAL_ANALOGY_MAX_CLIPS` | `44` / `110` / `45` / `52` / `2` / `2` | cuts / cuts / clips / clips / sents / clips | Assembled shot range (`>= 44` cuts; active `porcelain_cinematic_v7` episodes target `45..52` clips for `~46–48` cuts, `<= 2` sentences per hold, and `<= 2` literal analogy cutaways) (R58/R66) |
| `DIORAMA_MIN_CUT_DURATION_SEC` / `DIORAMA_VISUAL_PLAYBACK_SPEED` / `DIORAMA_ENTRY_SPEED_RAMP` | `1.30` / `1.12` / `True` | s / ratio / bool | Gear-1 montage floor (`1.30s`), `1.12x` snappy motion speed, and `0.35s` entry speed-ramp (`1.26x -> 1.10x`) (R58) |
| `DIORAMA_ENTRY_RAMP_START_SPEED` / `DIORAMA_ENTRY_RAMP_MAIN_SPEED` | `1.26` / `1.10` | ratio / ratio | Entry speed-ramp peak (`0.00–0.35s`) and main cruise speed (`0.35s..end`) per cut (R58) |
| `DIORAMA_ACT5_MONTAGE_CUT_MIN_SEC` / `DIORAMA_ACT5_MONTAGE_CUT_MAX_SEC` | `0.65` / `1.10` | s | Rhythmic cut window during the Act 5 physical lab crisis climax (legacy cross-cut mode) |
| `DIORAMA_TTS_ENGINE` / `DIORAMA_TTS_VOICE` / `DIORAMA_TTS_OUTPUT_FORMAT` / `DIORAMA_TTS_BITRATE_BPS` / `DIORAMA_TTS_RATE` / `DIORAMA_TTS_PITCH` | `"edge_tts"` / `"en-US-AndrewMultilingualNeural"` / `"audio-24khz-96kbitrate-mono-mp3"` / `96000` / `"+32%"` / `"+14Hz"` | str / str / str / bps / str / str | Crisp, natural American male high-tenor documentary storyteller voice streamed at `96 kbps` CBR (`2x` over `48 kbps` default, `0.000s` timing diff, R59/R63) |
| `DIORAMA_TTS_SPEED` / `DIORAMA_MIN_CONVERSATIONAL_QUESTIONS` | `1.10` / `4` | ratio / count | Offline `kokoro-onnx` fallback speed & minimum conversational `?` hooks per script (R57/R59) |
| `DIORAMA_SPEECH_PAUSE_SEC` / `DIORAMA_ACT_BOUNDARY_PAUSE_SEC` | `0.14` / `0.24` | s / s | Snappy inter-sentence breath gap (`0.14s`) and Act 1–6 boundary breath transition (`0.24s`) (R59) |
| `DIORAMA_PAUSE_TUNE_RANGE_SEC` | `(0.10, 0.32)` | s | Breath-gap auto-fit range to land inside `DIORAMA_DURATION_MIN_SEC..DIORAMA_DURATION_MAX_SEC` |
| `DIORAMA_ATEMPO_FIT_RANGE` | `(0.95, 1.04)` | ratio | Bounded pitch-preserving `atempo` fine-tuning range (zero `asetrate` pitch shift) |
| `DIORAMA_ACTIVE_SPEECH_RATIO_MIN` | `0.84` | ratio | Minimum active voiced speech density before the outro swell (R59) |
| `DIORAMA_BGM_BPM` / `DIORAMA_BGM_DUCK_DB` | `88` / `-24.0` | BPM / dB | Minimal documentary pulse BGM tempo and speech-ducked level (R59) |
| `DIORAMA_OUTRO_SWELL_SEC` / `DIORAMA_OUTRO_SWELL_GAIN_DB` | `2.2` / `8.0` | s / dB | Final sky tilt-up title card hold and BGM swell gain |
| `DIORAMA_TARGET_LUFS` / `DIORAMA_MAX_LRA_LU` | `-15.5` / `4.0` | LUFS / LU | Integrated loudness and loudness-range ceiling (R59) |
| `DIORAMA_SUBTITLE_FONT_SIZE` / `DIORAMA_SUBTITLE_OUTLINE_WIDTH` / `DIORAMA_SUBTITLE_MARGIN_V` | `76` / `4.5` / `650` | pt / px / px | Single-line `Y≈64%` (`1920 - 650 = 1270` px) pure-white subtitle typography (R59) |
| `DIORAMA_SUBTITLE_MAX_WORDS` / `DIORAMA_SUBTITLE_HIGHLIGHT_GOLD` | `3` / `False` | words / bool | Strict `2–3` word pure `#FFFFFF` hard-cut subtitle lock with zero color highlights (R59) |
| `DIORAMA_CALLOUT_FONT_SIZE` / `DIORAMA_CALLOUT_MARGIN_V` / `DIORAMA_CALLOUT_COUNT_RANGE` | `64` / `1520` / `(4, 8)` | pt / px / count | Clean top-space (`Y≈21%`) US English year/metric callout style (R59) |
| `DIORAMA_OUTRO_TITLE_FONT_SIZE` / `DIORAMA_OUTRO_TITLE_MARGIN_V` | `84` / `1140` | pt / px | Upper-sky (`Y≈41%`) 2-line uppercase English title card on final tilt-up (R59) |
| `TITLE_MAX_CHARS_DIORAMA` | `95` | chars | Max character length for 2-Clause US English Paradox Titles (R60) |
| `is_diorama_profile(x)` / `is_diorama_v7_plan(x)` / `is_porcelain_v7_plan(x)` / `resolve_diorama_v7_style_profile(x)` / `clip_count_range_for_profile(p)` / `shorts_duration_range_for_profile(p)` / `word_count_range_for_profile(p)` | helpers | — | Profile-aware contract resolvers in `pipeline/config.py` |
| `PROMPT_SCHEMA_VERSION_V7` / `PORCELAIN_V7_STYLE_PROFILE` / `DIORAMA_V7_STYLE_PROFILE` / `DIORAMA_V7_STYLE_PROFILES` / `DEFAULT_DIORAMA_STYLE_PROFILE` | `7` / `"porcelain_cinematic_v7"` / `"lowpoly_pastel_v7"` / `("lowpoly_pastel_v7", "porcelain_cinematic_v7")` / `"porcelain_cinematic_v7"` | int / str / str / tuple / str | Schema v7 style profiles: **`porcelain_cinematic_v7` channel default** (R66) with backward-compatible `lowpoly_pastel_v7` preservation (R63) |
| `PORCELAIN_V7_WORLD_STYLE` / `PORCELAIN_V7_CAST_STYLE` / `PORCELAIN_V7_OPTICS_LOCK` | `"photorealistic bright high-key documentary studio world"` / `"clothed articulated matte-white porcelain figures with translucent frosted-glass craniums"` / `"crisp cinema prime lens clarity with soft natural studio daylight and subtle rim lighting"` | str / str / str | Photorealistic high-key porcelain/frosted-glass cast & cinema prime optics lock (R66) |
| `PORCELAIN_V7_LUMA_RANGE` / `PORCELAIN_V7_DARK_VOID_RATIO_MAX` / `PORCELAIN_V7_SATURATION_RANGE` | `(88.0, 226.0)` / `0.24` / `(8.0, 115.0)` | Y / ratio / S | High-key native-color episode exposure, dark-shadow ceiling (`HSV V < 35`), and 4-color luminescence saturation bounds (R66) |
| `PORCELAIN_V7_NEON_GREEN_SPILL_MAX` / `PORCELAIN_V7_BRAIN_MARGIN_SAT_MAX` / `PORCELAIN_V7_HUMAN_SKIN_MAX` | `0.015` / `48.0` / `0.14` | ratio / S / ratio | Hard CV caps blocking fluorescent neon-green AI slime/mist (`<= 1.5%`), outer studio margin glow bleed on whole-brain gallery cuts (`<= 48.0`), and HSV+YCrCb mannequin-to-human flesh morph (`<= 14%`) (R66) |
| `PORCELAIN_V7_BRAIN_RENDER_MODES` / `PORCELAIN_V7_VISUAL_GRAMMARS` / `ALL_DIORAMA_V7_VISUAL_GRAMMARS` | 4 brain modes / 6 porcelain grammars / 12 v7 grammars | tuple / tuple / tuple | 4-mode Contained Living 4-Color 3D Brain (`cortical_vascular_whole`, `sagittal_coronal_cutaway`, `frosted_glass_subcortical_xray`, `bounded_micro_channel`) & 6 porcelain grammars (`porcelain_fullbleed_world`, `porcelain_hands_closeup`, `porcelain_pov_hands`, `porcelain_cutaway_section`, `porcelain_literal_analogy`, `porcelain_living_brain`) (R66) |
| `DIORAMA_V7_WORLD_STYLE` / `DIORAMA_V7_SHADER_STYLE` / `DIORAMA_V7_OPTICS_LOCK` | `"full-bleed bright diffused pastel daylight world"` / `"untextured flat-shaded matte low-poly 3D"` / `"crisp infinite deep focus from foreground to horizon"` | str / str / str | Legacy `lowpoly_pastel_v7` full-bleed low-poly world, matte flat-shaded polygons, and `100%` infinite deep focus (R63) |
| `DIORAMA_V7_LUMA_RANGE` / `DIORAMA_V7_DARK_VOID_RATIO_MAX` / `DIORAMA_V7_SATURATION_RANGE` | `(105.0, 168.0)` / `0.14` / `(24.0, 52.0)` | Y / ratio / S | Legacy `lowpoly_pastel_v7` episode mean luma window, dark-void pixel ceiling (`HSV V < 35`), and calm low-saturation pastel window (R63) |
| `DIORAMA_V7_CUTAWAY_MAX_RATIO` / `DIORAMA_V7_BRAIN_RENDER_MODES` | `0.15` / `("matte_pastel_cortical_model", "matte_pastel_sagittal_cutaway")` | ratio / tuple | Cross-section cutaway ceiling (`<= 15%`) and 2-mode bright-studio matte architectural brain models (R63) |
| `DIORAMA_V7_VISUAL_GRAMMARS` / `DIORAMA_V7_CAMERA_MOVES` | 6 grammars / 7 camera moves | tuple / tuple | 3-tier face-excluding low-poly framing (`lowpoly_hands_closeup`, `lowpoly_pov_hands`, `lowpoly_fullbleed_world`, `lowpoly_cutaway_section`, `lowpoly_literal_analogy`, `lowpoly_matte_brain`) and orthogonal camera rig (R63/R66) |
| `DIORAMA_V7_LOCKED_CAMERA_MIN_RATIO` / `DIORAMA_V7_ZOOM_CAMERA_MAX_RATIO` | `0.35` / `0.30` | ratio / ratio | Minimum tripod lock-off ratio (`>= 35%`, target `~40%`) and zoom/push-pull ceiling (`<= 30%`) (R63) |
| `DIORAMA_V7_VIDEO_FPS` / `DIORAMA_V7_VISUAL_PLAYBACK_SPEED` / `DIORAMA_V7_DURATION_MIN_SEC` / `SHORTS_HARD_CEILING_FRAMES_V7` | `24` / `1.00` / `140.0` / `4296` | fps / ratio / s / frames | Native `24.0fps` `1.00x` Flow timeline (`0%` `24->30` pulldown judder, `0%` speed-ramp knees, `140.0..179.0s` `<= 4,296` frames) (R63) |
| `DIORAMA_V7_RAPID_CUT_MIN_SEC` / `DIORAMA_V7_MID_ACT_MAX_CUT_SEC` / `DIORAMA_V7_LONG_TAKE_MAX_SEC` / `DIORAMA_V7_CUT_CV_MIN` | `0.68` / `4.60` / `6.50` / `0.36` | s / s / s / CV | Legacy `lowpoly_pastel_v7` cut rhythm bounds (R63) |
| `PORCELAIN_V7_MIN_CUT_SEC` / `PORCELAIN_V7_MID_ACT_MAX_CUT_SEC` / `PORCELAIN_V7_LONG_TAKE_MAX_SEC` / `PORCELAIN_V7_AVG_CUT_MIN_SEC` / `PORCELAIN_V7_AVG_CUT_MAX_SEC` / `PORCELAIN_V7_CUT_CV_MIN` | `1.80` / `4.30` / `4.50` / `2.85` / `3.35` / `0.15` | s / s / s / s / s / CV | Active `porcelain_cinematic_v7` balanced documentary pacing: `>= 1.80s` floor (zero flash cuts), `<= 4.30s` single-sentence ceiling, `<= 4.50s` 2-sentence hold ceiling (zero `>= 5.0s` stagnant holds), and `2.85..3.35s` (`~3.0–3.2s`) average cut rhythm via same-scene multi-angle coverage (`CV >= 0.15`, R66.4) |
| `DIORAMA_V7_SPLIT_MODE` / `DIORAMA_V7_SPLIT_DIVIDER_PX` | `"split_hstack"` / `6` | str / px | Left/Right vertical split-screen with `6px` solid `#000000` black divider (R63) |
| `DIORAMA_V7_TTS_RATE` / `DIORAMA_V7_TTS_PITCH` / `DIORAMA_V7_TTS_VOLUME` / `DIORAMA_V7_TTS_SPEED` / `DIORAMA_V7_WPM_MIN` / `DIORAMA_V7_WPM_MAX` / `DIORAMA_V7_ACTIVE_VOICED_RMS_RATIO_MIN` | `"+8%"` / `"+14Hz"` / `"-10%"` / `1.08` / `135.0` / `212.0` / `0.80` | str / str / str / ratio / WPM / WPM / ratio | Unified `1.08x` (`+8%`, `+14Hz` high-tenor pitch, `-10%` tear-free Silk Clean EQ) `en-US-AndrewMultilingualNeural` & offline `kokoro-onnx` speech rate with natural conversational breath preservation (`>= 80%` true RMS voiced ratio) (R63) |
| `DIORAMA_VOICE_PRESETS` / `DEFAULT_DIORAMA_VOICE_PRESET` / `DEFAULT_REENACTMENT_VOICE_PRESET` / `STORYTELLER_VOCAL_FILTER_FEMALE` / `resolve_diorama_voice_preset(...)` | `5` presets (`andrew_v7`, `emma_v7`, `ava_v7`, `aria_v7`, `christopher_v7`) / `"andrew_v7"` / `"emma_v7"` / `95Hz HPF + 2.85kHz presence + 7.2kHz sibilance trim` | dict / str / str / filter / helper | Multi-voice narrator preset registry: `andrew_v7` (`+14Hz` male Silk Clean default) & `emma_v7` (`en-US-EmmaMultilingualNeural`, `+0Hz`, `af_bella` offline fallback, warm authoritative female narrator default for R67 reenactments) |
| `DIORAMA_V7_PROSODY_MODES` / `DIORAMA_V7_PROSODY_MODE` / `DIORAMA_V7_US_PROSODY_MODE` | `("uniform_108x", "uniform_110x", "dynamic_rush_v7", "dynamic_us_v7")` / `"dynamic_rush_v7"` / `"dynamic_us_v7"` | tuple / str / str | Sentence-level prosody profiles: `dynamic_rush_v7` channel legacy default; **`dynamic_us_v7` US `45+` ear-first cadence (`~162–174 WPM`)** for new Porcelain & R67 reenactment episodes |
| `DIORAMA_V7_PROSODY_BASE_RATE` / `DIORAMA_V7_US_PROSODY_BASE_RATE` / `DIORAMA_V7_PROSODY_UNIFORM_110_RATE` | `"+8%"` / `"+7%"` / `"+10%"` | str | Base/fallback edge-tts synthesis rates for `dynamic_rush_v7`, `dynamic_us_v7`, and `uniform_110x` |
| `DIORAMA_V7_PROSODY_GEAR_RATES` / `DIORAMA_V7_US_PROSODY_GEAR_RATES` | rush `"+12%"` / stamp `"+8%"` / brisk `"+15%"` · US: rush `"+10%"` / stamp `"+4%"` / brisk `"+7%"` | dict / dict | Native per-gear edge-tts rates (`wsola_factor = 1.0`, zero `atempo` phasiness) for `dynamic_rush_v7` vs US `45+` `dynamic_us_v7` |
| `DIORAMA_V7_PROSODY_SPLICE_FADE_SEC` | `0.014` | s | Smooth `14ms` raised-cosine fade at every sentence edge and emphasis micro-pause splice (studio booth glue) |
| `DIORAMA_V7_MASTER_DEESSER` | `"deesser=i=0.48:m=0.5:f=0.5:s=o"` | ffmpeg filter | Calibrated Schema v7 master studio velvet de-esser (`< 0.58`; tames `4–10 kHz` vocoder sibilance while preserving `96 kbps` high-band clarity) |
| `DIORAMA_MUX_TRUE_PEAK_TARGET_DBTP` / `DIORAMA_MUX_TRUE_PEAK_LIMITER` | `-1.5` / `"aresample=192000,alimiter=limit=0.794:attack=1:release=50:level=disabled,aresample=48000"` | dBTP / filter | Encoded AAC true-peak ceiling (`<= -1.5 dBTP`, matching Prosody QA `P7`) with 4x-oversampled `-2.0 dBFS` limiter before AAC |
| ASR scoring (`_asr_tokens`, P6) | — | — | Hyphen split, dotted-initials join (`H.M.` → `hm`), light inflection fold before SequenceMatcher so Whisper orthography (`brand new`, `juggle`, `tests`) is not scored as mis-speech; threshold `PROSODY_P6_ASR_MATCH_MIN` unchanged |
| `DIORAMA_V7_PROSODY_GEARS` / `DIORAMA_V7_US_PROSODY_GEARS` | `1.12x / 1.08x / 1.15x` · US: rush `1.10x` (gap `0.030s`) / stamp `1.04x` (gap `0.180s`) / brisk `1.07x` (gap `0.075s`) | dict / dict | Per-gear target tempo, internal-silence trim threshold → keep, inserted gap before sentence |
| `DIORAMA_V7_PROSODY_UNIFORM_110` | trim `0.14→0.045s`, gap `0.085s`, stamp gap `0.17s`, act gap `0.20s` | dict | `uniform_110x` breath/gap profile |
| `DIORAMA_V7_PROSODY_ACT_GAP_MIN` / `DIORAMA_V7_PROSODY_MAX_ADJ_TEMPO_JUMP` / `DIORAMA_V7_PROSODY_RUSH_MAX_STREAK` | `0.20` / `0.05` / `3` | s / ratio / count | Act boundary gap floor, adjacent gear-tempo jump clamp (when gap `< 0.10s`; clamped sentences synthesize at the nearest integer-% rate), max consecutive auto-rush sentences |
| `DIORAMA_V7_PROSODY_EMPHASIS_PAUSE_SEC` / `DIORAMA_V7_PROSODY_EMPHASIS_GAIN_DB` | `0.0` / `1.0` | s / dB | Co-articulation-safe smooth `25ms` cosine gain contour lift (`0.0s` default disables mid-word digital zero-slicing) on `script.json` `emphasis_words` |
| `DIORAMA_V7_PROSODY_STAMP_PHRASES` / `DIORAMA_V7_PROSODY_RUSH_CLIMAX_WORDS` / `DIORAMA_V7_PROSODY_REHOOK_PHRASES` | Anti-Clone bank union / `yet, then, suddenly, instead` / midpoint bank union | tuple | Rule-based gear classifier inputs spanning all Anti-Clone banks |
| `PROSODY_P1_FIRST_ONSET_MAX_SEC` / `PROSODY_P2_HOOK_END_MAX_SEC` / `PROSODY_P2_STAMP_END_MAX_SEC` / `PROSODY_P3_TEMPO_TOLERANCE` / `PROSODY_P4_RUSH_MAX_INTERNAL_SILENCE_SEC` / `PROSODY_P5_STAMP_PRE_SILENCE_RANGE` / `PROSODY_P6_ASR_MATCH_MIN` / `PROSODY_P10_OPEN_LOOP_MAX_GAP_SEC` | `0.10` / `9.0` / `11.5` / `0.03` / `0.07` / `(0.20, 0.32)` / `0.95` / `35.0` | s / s / s / ratio / s / s / ratio / s | Prosody QA Gates `P1–P10` (`pipeline/prosody.py`, `main.py prosody-qa`) — P2 recalibrated 2026-10-31 to the approved 3-sentence cold-open (HM Plan B: S2 ends 8.4s, S3 stamp ends 10.9s) |
| `DIORAMA_V7_INTERNAL_SILENCE_TRIM_THRESHOLD_SEC` / `DIORAMA_V7_INTERNAL_BREATH_KEEP_SEC` / `DIORAMA_V7_INTER_SENTENCE_PAUSE_SEC` / `DIORAMA_V7_ACT_BOUNDARY_PAUSE_SEC` | `0.28` / `0.14` / `0.15` / `0.32` | s | Conversational breath/silence trimming and Act boundary pause targets (R63) |
| `DIORAMA_V7_AUDIO_CHANNELS` / `DIORAMA_V7_BGM_DUCK_DB` | `2` / `-22.0` | ch / dB | 2-channel stereo acoustic/orchestral documentary score ducked `-22.0 dB` under centered voice (R63) |
| `FONT_CONDENSED_BLACK_PATH` / `DIORAMA_V7_SUBTITLE_FONT_NAME` / `DIORAMA_V7_SUBTITLE_FONT_SIZE` / `DIORAMA_V7_SUBTITLE_OUTLINE_WIDTH` / `DIORAMA_V7_SUBTITLE_SHADOW_DEPTH` / `DIORAMA_V7_SUBTITLE_MARGIN_V` | `AABCondensed-Black.ttf` / `"AAB Condensed Black"` / `94` / `5.5` / `0.0` / `672` | path / str / pt / px / px / px | Bundled condensed extra-black `.ttf` (`fontsdir` loaded, uncondensed space glyph, `Shadow=0`, `H_median ≈ 52px`, `Y_center ≈ 1209px`, `0f` contiguous frame-grid handoff) (R63) |
| `DIORAMA_V7_CHAPTER_HEADLINE_FONT_SIZE` / `DIORAMA_V7_CHAPTER_HEADLINE_OUTLINE_WIDTH` / `DIORAMA_V7_CHAPTER_HEADLINE_MARGIN_V` / `DIORAMA_V7_CHAPTER_HEADLINE_SCALE_X` / `DIORAMA_V7_CHAPTER_HEADLINE_MARGIN_LR` / `DIORAMA_V7_CHAPTER_HEADLINE_MAX_WIDTH_PX` | `276` / `2.5` / `180` / `85` / `85` / `920` | pt / px / px / % / px / px | Giant single-line top chapter impact headline (`~144px` height, `ScaleX=85` horizontal safe margins keeping rendered width `<= 920px` with `>= 80px` side margins, clear word separation + soft drop shadow) (R63) |
| `DIORAMA_V7_ANATOMY_LABEL_FONT_SIZE` / `DIORAMA_V7_ANATOMY_LABEL_OUTLINE_WIDTH` / `DIORAMA_V7_ANATOMY_LABEL_SCALE_X` / `DIORAMA_V7_ANATOMY_LABEL_MARGIN_V` | `104` / `5.0` / `90` / `190` | pt / px / % / px | Programmatic upper-viewport ASS anatomical region callout badge (`AnatomyLabel` style on `porcelain_living_brain` / `lowpoly_matte_brain` cuts, collision-free vs `ChapterHeadline` & `split_hstack`, zero AI-rendered text inside Flow clips) (R63/R66) |

---

## 2-D. Post-Hoc Clip-by-Clip Expressive Clarity QA (R64) & Knowledge Base Hub (R50-B)

| Constant | Value | Unit | Meaning |
|---|---|---|---|
| `POSTHOC_SEMANTIC_QA_REPORT_FILENAME` | `"posthoc_semantic_qa_report.json"` | file | Dual-stream post-hoc visual clarity report (`05_assembly/`) (R64) |
| `POSTHOC_SEMANTIC_REVIEW_FILENAME` | `"posthoc_semantic_review.json"` | file | SHA-256-bound per-cut semantic review artifact (`05_assembly/`) (R64) |
| `POSTHOC_VIEWER_STRIPS_DIRNAME` | `"posthoc_viewer_strips"` | dir | Annotated `[START \| MID \| END]` viewer contact sheets (`05_assembly/posthoc_viewer_strips/`) (R64) |
| `POSTHOC_CUTS_PER_VIEWER_SHEET` | `6` | cuts/sheet | Number of assembled cuts rendered per contact sheet image (R64) |
| `POSTHOC_MIN_CUT_CLARITY_SCORE` | `75.0` | score (0–100) | Minimum passing expressive clarity score for every individual cut (R64) |
| `POSTHOC_MIN_EPISODE_MEAN_CLARITY_SCORE` | `82.0` | score (0–100) | Minimum episode-wide mean clarity score across all cuts (R64) |
| `POSTHOC_MIN_SHARPNESS_LAPLACIAN` | `12.0` | Laplacian var | Minimum clean-ROI Laplacian focus sharpness on `360x640` standardized grid (R64) |
| `POSTHOC_MIN_EDGE_DENSITY` | `0.005` | ratio | Minimum Canny structural edge ratio in clean action ROI (R64) |
| `POSTHOC_MIN_FG_BG_CONTRAST_DE` | `4.0` | LAB ΔE | Minimum perceptual LAB foreground-to-periphery separation (R64) |
| `POSTHOC_MIN_MOVING_CAM_DIFF` | `1.00` | L1 diff | Minimum mean temporal luma diff across moving-camera cuts (R64) |
| `POSTHOC_LOCKED_TRIPOD_MIN_P95_DIFF` | `1.50` | L1 diff | Minimum 95th-percentile localized hand/prop motion diff on `locked_tripod` cuts (R64) |
| `POSTHOC_MAX_STEP_HIST_JUMP` | `0.78` | Bhattacharyya | Maximum normalized HSV histogram step distance before flagging mid-cut AI morph/flash (R64) |
| `POSTHOC_SPLIT_PANE_MIN_DIFF` | `10.0` | L1 diff | Minimum mean pixel difference between `split_hstack` left/right panes (R64) |
| `POSTHOC_BRAIN_HIGHLIGHT_MIN_CHROMA` | `6.0` | LAB chroma | Minimum `p99.5 - median` LAB chroma accent separation on lesion/anatomy brain cuts (R64) |
| `POSTHOC_ANALOGY_SYNC_TOLERANCE_SEC` | `0.45` | s | Maximum timing delta between ASR spoken analogy phrase and visual cut (R64) |
| `POSTHOC_MIN_REVIEW_NOTE_CHARS` | `20` | chars | Minimum length for per-cut `observed_visual_summary` in `posthoc_semantic_review.json` (R64) |
| `POSTHOC_MAX_IDENTICAL_REVIEW_NOTES` | `3` | cuts | Maximum identical review summaries allowed before flagging copy-paste boilerplate (R64) |
| `KNOWLEDGE_BASE_DIRNAME` / `KNOWLEDGE_BASE_DIR` | `"knowledge_base"` / `CHANNEL_ROOT / "knowledge_base"` | dir / path | Channel-wide accumulated Knowledge Hub root (`BCI_Shorts_Channel/knowledge_base/`) (R50-B) |
| `KNOWLEDGE_TELEMETRY_DIRNAME` | `"telemetry"` | dir | Episode & clip clarity telemetry (`knowledge_base/telemetry/`) (R50-B) |
| `EPISODES_INDEX_FILENAME` / `CLIP_CLARITY_LEDGER_FILENAME` / `QA_ANALYTICS_SUMMARY_FILENAME` | `"episodes_index.jsonl"` / `"clip_clarity_ledger.jsonl"` / `"qa_analytics_summary.json"` | files | Episode registry, per-cut clarity ledger, and aggregated grammar/act failure analytics (R50-B) |
| `REUSABLE_PACKS_DIRNAME` / `EXPERIMENTS_ARCHIVE_DIRNAME` | `"reusable_packs"` / `"experiments"` | dirs | Reusable prompt/analogy/brain/location JSON packs and dated parameter-tuning experiments archive (R50-B) |

---

## 2-E. Source-Conditioned 1:1 Porcelain Reenactment (R67) & 3-Format US Funnel

| Constant | Value | Unit | Meaning |
|---|---|---|---|
| `REENACT_QUARANTINE_ROOT` | `Path("/tmp/aab_reenact")` | path | Ephemeral quarantine workspace outside repo for Stage 1–2 source analysis & structural guides (`RQ1` requires deletion before final QA) |
| `REENACT_EDL_FILENAME` / `REENACT_QA_REPORT_FILENAME` / `REENACT_COMPARISON_SHEET_FILENAME` | `"source_edl.json"` / `"reenactment_qa_report.json"` / `"reenactment_comparison_sheet.png"` | files | Repo-safe shot/hash EDL (`03_visuals/`), `RQ1–RQ5` QA report (`05_assembly/`), and porcelain keyframe sheet (`03_visuals/`) (R67) |
| `REENACT_MIN_DHASH_DISTANCE` | `18` | bits | `RQ2` minimum 64-bit `dHash` Hamming distance between generated porcelain assets/clips and source video frames |
| `REENACT_MAX_TRANSCRIPT_5GRAM_OVERLAP` | `0.0` | ratio | `RQ3` `0.0%` verbatim 5-gram SHA-256 overlap against source video captions/ASR |
| `REENACT_LAB_RATIO_TARGET` / `REENACT_BRAIN_RATIO_MIN` / `REENACT_COMPOSITION_MATCH_MIN` | `0.78` / `0.20` / `0.85` | ratio | `~78%` source-conditioned room choreography cuts, `>= 20%` original `R66` 4-color 3D brain / `hstack` cuts (`RQ5`), and `>= 85%` blocking zone match (`RQ5`) |
| `PORCELAIN_REF_WHITE_RATIO_MAX` / `PORCELAIN_REF_NEON_GREEN_MAX` | `0.72` / `0.012` | ratio | Calibrated `R66` `porcelain_cinematic_v7` `Q2` high-key white ratio ceiling (`0.72`) and `Q6` uncontained neon-green cap (`0.012`, allowing `electric cyan-blue`) |
| `REENACTMENT_TRACKS` | `("track_a", "track_b")` | tuple | Dual-Track `porcelain_cinematic_v7` reference-conditioning tracks: `track_a` (`R67` archival film reenactment) and `track_b` (`R66-Anchor` scene-bible room & cast pack) |
| `MEDIA_SUITABILITY_CLASSES` | `("suitable_track_a", "needs_section_window", "reject_track_b_only")` | tuple | 4-Gate CV/Transcript/Metadata suitability classes for `04_media_refs.json` entries (`pipeline/research_dossier.py`) |
| `MEDIA_REJECT_CHANNEL_PATTERNS` | `("ted", "tedx", "ted-ed", ..., "huberman lab")` | tuple | Lecture, dark-stage, 2D-explainer, and hospital PR channel patterns rejected by Gate 1 (`reject_track_b_only`) |
| `MEDIA_MAX_DARK_VOID_RATIO` | `0.72` | ratio | Gate 2 max median dark pixel ratio (`Y < 35`) across sampled keyframes before rejecting dark TED/stage voids |
| `MEDIA_MAX_FLAT_SLIDE_RATIO` | `0.62` | ratio | Gate 3 max flat low-texture slide/vector ratio on non-B&W frames (1920s–60s grayscale `S_p90 <= 22` film is exempt) |
| `MEDIA_MAX_UNWINDOWED_DURATION_SEC` | `600.0` | s | Gate 4 max unwindowed video duration (`10 min`) before requiring an explicit `--section MM:SS-MM:SS` window |
| `YUNET_FACE_MODEL_PATH` | `ASSETS_DIR / "models" / "face_detection_yunet_2023mar.onnx"` | path | Bundled OpenCV Zoo Apache-2.0 YuNet ONNX face detector for B&W + color archival face sanitization (`R67`) & talking-head rejection (`Gate 4`) |
| `MICRO_SHORT_PROFILE` | `"micro_short_v7"` | str | `35–45s` Micro-Short discovery funnel profile |
| `MICRO_SHORT_DURATION_MIN_SEC` / `MICRO_SHORT_DURATION_MAX_SEC` (`MICRO_SHORT_MIN_SEC` / `MICRO_SHORT_MAX_SEC`) | `35.0` / `45.0` | s | Assembled duration bounds for `micro_short_v7` |
| `MICRO_SHORT_WORD_COUNT_MIN` / `MICRO_SHORT_WORD_COUNT_MAX` (`MICRO_SHORT_WORD_MIN` / `MICRO_SHORT_WORD_MAX`) | `95` / `120` | words | Spoken word budget for `micro_short_v7` |
| `MICRO_SHORT_CUT_COUNT_MIN` / `MICRO_SHORT_CUT_COUNT_MAX` (`MICRO_SHORT_CUT_MIN` / `MICRO_SHORT_CUT_MAX`) | `14` / `16` | cuts | Cut count bounds for `micro_short_v7` |
| `LONGFORM_VIDEO_WIDTH` / `LONGFORM_VIDEO_HEIGHT` / `LONGFORM_VIDEO_FPS` / `LONGFORM_TARGET_LUFS` / `LONGFORM_CHAPTER_FADE_SEC` | `3840` / `2160` / `24` / `-14.0` / `0.45` | px / px / fps / LUFS / s | `16:9` `4K` CTV Long-Form documentary assembly specification (`pipeline/longform_assembler.py`) |
| `THUMB_LONGFORM_WIDTH` / `THUMB_LONGFORM_HEIGHT` | `3840` / `2160` | px | `16:9` `4K` CTV Long-Form A/B/C thumbnail resolution (`render_longform_4k_thumbnails`) |
| `NEURO_NEWS_STAGING_DIR` | `WORKSPACE_ROOT / "Completed_Neuro_News_Shorts"` | path | Staging folder for DOI/NCT-verified breaking BCI & neuroscience candidates (`pipeline/news_radar.py`) |

---

## 3. Assembly Timing, Holds & Speech Window Detection

| Constant | Value | Unit | Meaning |
|---|---|---|---|
| `AV_SPEEDUP_FACTOR` | `1.00` | ratio | Synchronized video (`setpts`) and audio (`atempo`) speed-up (R43-A) |
| `CLIP_VISUAL_HOLD_SEC` | `0.32` | s | Post-speech visual hold on non-pre-pivot clips `1..N-1` (R43-B) |
| `CLIP_PRE_PIVOT_HOLD_SEC` | `0.45` | s | Post-speech visual hold on the clip immediately before `pivot` (R43-B) |
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
| `AUDIO_SIBILANCE_BAND_HZ` / `AUDIO_SPEECH_BODY_BAND_HZ` | `(4200.0, 9200.0)` / `(180.0, 3600.0)` | Hz | High-frequency sibilance/harshness band vs speech body band (`VideoAutopsyEngine.inspect_audio_stream`) |
| `AUDIO_MAX_SIBILANCE_ENERGY_RATIO` / `AUDIO_MAX_SIBILANCE_CREST_DB` | `0.62` / `32.0` | ratio / dB | Max HF/body RMS ratio and HF crest over active 50ms voiced windows before flagging harshness tear |
| `DIORAMA_V7_TARGET_LUFS` / `DIORAMA_LUFS_TOLERANCE_LU` | `-15.5` / `4.0` | LUFS / LU | BS.1770 (`ebur128`) integrated documentary loudness target and accepted tolerance window (`-19.5..-11.5 LUFS`) |
| `AUDIO_MAX_OVERSAMPLED_TRUE_PEAK_DBTP` / `AUDIO_MIN_TTS_ASR_WORD_COVERAGE` | `-0.5` / `0.85` | dBTP / ratio | Max 4x oversampled True Peak (`ebur128=peak=true`) and minimum TTS spoken word coverage ratio |

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

---

## 7. R65 Thumbnail Studio & In-Video Cover Frame (`pipeline/thumbnail_studio.py`)

| Constant | Value | Unit | Meaning |
|---|---|---|---|
| `THUMBNAIL_REPORT_FILENAME` | `"thumbnail_report.json"` | filename | Per-episode 7-gate thumbnail QA & cover-frame timestamp report (`06_publish/`) |
| `THUMBNAIL_CONTACT_SHEET_FILENAME` | `"thumbnail_contact_sheet.png"` | filename | Full-size + `160px` mobile-shelf side-by-side contact sheet (`06_publish/`) |
| `THUMB_CANDIDATE_SAMPLES_PER_CUT` | `3` | frames | Clean intra-cut sample offsets (`25% / 50% / 75%`) evaluated per eligible EDL cut |
| `THUMB_EXCLUDE_MODES` | `("split_hstack", "split_vstack")` | tuple | Split-screen cut modes excluded from single-subject cover selection |
| `THUMB_EXCLUDE_OUTRO` | `True` | bool | Excludes Act 6 `outro_sky_card` from cover candidate pool |
| `THUMB_SCORE_WEIGHTS` | `{"sharpness": 0.25, "contrast": 0.20, "colorfulness": 0.10, "center_salience": 0.25, "intent": 0.20}` | dict | Composite candidate frame scoring weights |
| `THUMB_INTENT_BONUS` | `{"cover_sentence": 1.0, "act1": 0.6, "brain_badge": 0.4, "default": 0.0}` | dict | Narrative/cover-sentence intent bonus weights |
| `THUMB_MIN_SHARPNESS` | `60.0` | Laplacian var | Minimum Laplacian focus variance at `540x960` (`TQ3`) |
| `THUMB_MIN_LUMA_STD` | `38.0` | luma std | Minimum global luminance contrast standard deviation (`TQ3`) |
| `THUMB_MIN_CENTER_SALIENCE` | `1.15` | ratio | Minimum centre-`3:4` Canny edge density vs outer border density (`TQ2`) |
| `THUMB_MIN_PAIRWISE_DIFF` | `15.0` | L1 diff | Minimum pairwise ROI pixel difference across variants A, B, and C (`R31` / `TQ5`) |
| `THUMB_MIN_TEXT_CONTRAST` | `4.5` | WCAG ratio | Minimum hook fill vs local/stroke background contrast at `160px` shelf width (`TQ1`) |
| `THUMB_LEGIBILITY_PREVIEW_W` | `160` | px | Simulated mobile Shorts shelf width (`TQ1`) |
| `THUMB_SAFE_Y_RANGE` | `(240, 1440)` | px | Safe vertical band inside centre `3:4` grid crop & above bottom `25%` Shorts UI (`TQ4`) |
| `THUMB_SAFE_MARGIN_X` | `80` | px | Minimum left/right horizontal safe margin for hook text (`TQ4`) |
| `THUMB_HOOK_MAX_WORDS` | `4` | words | Maximum word count for thumbnail hook headline (`TQ7`) |
| `THUMB_HOOK_MAX_CHARS` | `18` | chars | Maximum character count for thumbnail hook headline (`TQ7`) |
| `THUMB_HOOK_FONT_SIZE_RANGE` | `(150, 96)` | pt | Auto-fit bundled `AABCondensed-Black` hook font size range `(max, min)` |
| `THUMB_HOOK_STROKE_PX` | `10` | px | Dark outer stroke thickness around pure-white hook glyphs (zero v6 boxes/pills) |
| `THUMB_MIN_FILE_BYTES` | `80_000` | bytes | Minimum PNG file size per rendered thumbnail variant (`R31` / `TQ6`) |
| `DIORAMA_V7_REQUIRE_THUMBNAIL_BLOCK` | `True` | bool | Requires `visual_plan.thumbnail` + stamp headline alignment on new Schema v7 episodes (`R65`) |
