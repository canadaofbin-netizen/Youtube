"""
ALL ABOUT BRAIN - Video Production Pipeline Configuration.

Single numeric source of truth for the 5-10 clip Google Flow (Puck) pipeline (Production Contract v4).
Every value here is documented 1:1 in .agents/rules/production_constants.md.
"""

from pathlib import Path
from typing import Any

# Base Paths (derived from this file's location: <workspace>/pipeline/config.py)
WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
CHANNEL_ROOT = WORKSPACE_ROOT / "BCI_Shorts_Channel"
PROJECTS_DIR = CHANNEL_ROOT / "projects"
PROJECTS_QUARANTINE_DIR = CHANNEL_ROOT / "projects_quarantine_pending_flow"
FLOW_DOWNLOAD_HARVEST_LOCK_FILE = CHANNEL_ROOT / ".flow_download_harvest.lock"
ASSETS_DIR = CHANNEL_ROOT / "assets"
FONTS_DIR = ASSETS_DIR / "fonts"
BASE_CLIPS_DIR = ASSETS_DIR / "base_clips"

# Video Specifications (Shorts 9:16)
VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920
VIDEO_FPS = 30
VIDEO_MAX_DURATION_SEC = 105.0
CLIP_COUNT_MIN = 5
CLIP_COUNT_MAX = 10
DEFAULT_CLIP_COUNT = 10                  # 10-clip Deep-Mechanism spine is the default; 5-9 use subsets (CLIP_ROLE_SEQUENCES)

# Assembly timing (per-clip trim / hold around the detected speech window)
CLIP_VISUAL_HOLD_SEC = 0.32              # Post-speech hold on clips 1..N-1
CLIP_PRE_PIVOT_HOLD_SEC = 0.45           # Post-speech hold on the clip right before the pivot clip
CLIP_PRE_ROLL_TRIM_SEC = 0.40            # Minimum pre-roll trim on clips 2..N when speech starts later than this
AV_SPEEDUP_FACTOR = 1.00                 # Synchronized video (setpts) + vocal (atempo) speedup

# Speech-window detection (produce_psychology_batch.measure_clip_speech_window), 10 ms analysis windows
VOCAL_ONSET_PROTECT_SEC = 0.22           # speech_start = first voiced edge - 0.22 s (protects soft /w/ onsets below 750 Hz)
VOCAL_ONSET_PAD_SEC = 0.05               # trim_start = speech_start - 0.05 s (effective pre-speech pad = 0.27 s)
PROMPT_BLEED_SYLLABLE_SEC = 0.185        # Expected speech length = max(PROMPT_BLEED_MIN_EXPECTED_SEC, syllables x 0.185 s)
PROMPT_BLEED_MIN_EXPECTED_SEC = 2.2
PROMPT_BLEED_DEFAULT_SYLLABLES = 22      # Syllable count assumed when the clip narration text is unknown
PROMPT_BLEED_PAUSE_ALLOWANCE_SEC = 0.40  # Pause length above this is excluded from the spoken-duration tally
# Cut speech_end before hallucinated post-script speech: (spoken >= expected x multiple) and (silence gap >= gap_sec)
PROMPT_BLEED_CUTOFF_RULES: tuple[tuple[float, float], ...] = ((1.38, 0.65), (1.65, 0.35))
SOFT_TAIL_FLOOR_DB = -36.5               # soft_tail_thresh = max(-36.5, min(p95 - 15.0, p15 + 1.8)) dBFS
SOFT_TAIL_P95_OFFSET_DB = 15.0
SOFT_TAIL_P15_OFFSET_DB = 1.8
SOFT_TAIL_SEARCH_SEC = 0.95              # Search window after the last voiced cluster for quiet trailing syllables
SOFT_TAIL_MAX_GAP_SEC = 0.32             # Stop extending after this much continuous sub-threshold audio
SPEECH_END_PAD_SEC = 0.36                # speech_end pad after a normal (non-bleed) sentence end
SPEECH_END_PAD_BROKE_EARLY_SEC = 0.12    # speech_end pad when the prompt-bleed cutoff fired

# Native Flow vocal chain (produce_psychology_batch.extract_native_flow_clip_speech)
VOCAL_BANDPASS_HZ: tuple[int, int] = (95, 13500)              # highpass / lowpass corner frequencies
VOCAL_EQ_BANDS: tuple[tuple[int, float, float], ...] = (      # (centre Hz, Q width, gain dB)
    (180, 1.2, 2.5),                                          # chest warmth
    (3200, 1.0, 4.0),                                         # consonant articulation
    (8500, 1.5, 2.0),                                         # air
)
VOCAL_COMPRESSOR: dict[str, float] = {
    "threshold_db": -18,
    "ratio": 3.5,
    "attack_ms": 5,
    "release_ms": 60,
    "makeup_db": 3,
}
MASTER_TAIL_MUTE_SEC = 0.095             # Linear mute across all 4 mixed layers at the very end of audio_master.wav

# ==============================================================================
# Production Contract v4 (Locked Prompt Spec, 2026-10-17) — single numeric source of truth.
# Documented 1:1 in .agents/rules/production_constants.md. Never restate these values elsewhere.
# ==============================================================================
NATIVE_FLOW_WPS = 2.7                    # Speaking rate requested from Google Flow (Puck)
EFFECTIVE_WPS = round(NATIVE_FLOW_WPS * AV_SPEEDUP_FACTOR, 3)  # ~2.92 WPS after the 1.08x A/V speedup
# Flow video models as shown in the settings pane (verified live 2026-10-24). Production uses OMNI ONLY (owner decision
# 2026-10-24; matches ALLOWED_FLOW_MODELS). Veo is listed only so the guard can recognise and refuse it.
#   Omni 1.1 Flash -> 4s / 6s / 8s / 10s, 12 credits without an ingredient; with an ingredient attached the length is
#                     locked ("Length based on ingredient · 8s") and the cost is 20 credits
#   Veo 3.1 - Lite [Lower Priority] -> 4s / 6s / 8s, 0 credits (NOT USED)
FLOW_VIDEO_MODEL_PROFILES: dict[str, dict] = {
    "Omni 1.1 Flash": {
        "durations": ("4s", "6s", "8s", "10s"),
        "max_sec": 10,
        "max_sec_with_ingredient": 8,
        "model_family_id": "omni_1_1_flash",
        "zero_credit": False,
    },
    "Veo 3.1 - Lite [Lower Priority]": {
        "durations": ("4s", "6s", "8s"),
        "max_sec": 8,
        "max_sec_with_ingredient": 8,
        "model_family_id": "veo_3_1_lite_low_priority",
        "zero_credit": True,
    },
}
FLOW_ACTIVE_VIDEO_MODEL = "Omni 1.1 Flash"
FLOW_PRIMARY_VIDEO_MODEL = FLOW_ACTIVE_VIDEO_MODEL
FLOW_ZERO_CREDIT_MODEL = "Veo 3.1 - Lite [Lower Priority]"
FLOW_ENGINE_MODES: tuple[str, ...] = ("auto", "omni", "zero-credit")
DEFAULT_FLOW_ENGINE_MODE = "auto"
FLOW_BANNED_VIDEO_MODEL_MARKERS: tuple[str, ...] = ("Veo 2",)
FLOW_ZERO_CREDIT_TEXT = "Generating will use 0 credits"   # 0-credit verification marker when monthly credits are exhausted
FLOW_ALLOWED_DURATION_TARGETS: tuple[str, ...] = tuple(FLOW_VIDEO_MODEL_PROFILES[FLOW_ACTIVE_VIDEO_MODEL]["durations"])
FLOW_CLIP_DURATION_TARGET = "10s"        # Omni, no ingredient; clamps to 8s automatically when an ingredient is attached
FLOW_SHORT_CLIP_MAX_WORDS = 19           # Clips <= 19 words & <= 32 syllables dynamically route to "8s"
FLOW_SHORT_CLIP_MAX_SYLLABLES = 32
FLOW_CLIP_SAFE_MAX_SYLLABLES = 48        # Ceiling above which 10s Omni clips risk tail speech truncation (native voice only)
FLOW_CLIP_TARGET_SEC_MIN = 8.0           # Target native Flow clip length (prompt design)
FLOW_CLIP_TARGET_SEC_MAX = 12.0
CLIP_WORDS_MIN = 18                      # Spoken words per clip
CLIP_WORDS_MAX = 28
PROMPT_SCENE_WORDS_MIN = 50              # Visual scene description words per Flow prompt (excludes prefix/voice/narration)
PROMPT_SCENE_WORDS_MAX = 80
FINAL_TAIL_SEC = 0.20                    # Post-speech hold on the final clip (independent conclusion, no loop)
END_FADE_SEC = 0.09                      # Clean end fade on the final clip (keeps the truncation check passing)
PUCK_F0_RANGE_HZ = (85.0, 185.0)         # Puck male voice fundamental-frequency acceptance window
FLOW_PROMPT_PREFIX = (
    "Generate a 9:16 vertical video clip (video animation with spoken voiceover only, never a static image):"
)

# Narrative roles per clip count. Setting: real_env = narration-matched photoreal environment with porcelain
# mannequins; drill_down = dive from mannequin through the frosted-glass cranium into the brain; brain_void =
# realistic matte-white brain on deep midnight navy; pull_out = from brain back out into the real environment.
CLIP_ROLE_SEQUENCES: dict[int, tuple[str, ...]] = {
    5: ("setup", "crisis", "pivot", "mechanism", "conclusion"),
    6: ("setup", "crisis", "pivot", "mechanism", "breakthrough", "conclusion"),
    7: ("setup", "symptom", "crisis", "pivot", "mechanism", "breakthrough", "conclusion"),
    8: ("setup", "symptom", "crisis", "pivot", "step1", "step2", "breakthrough", "conclusion"),
    9: ("setup", "symptom", "crisis", "pivot", "step1", "step2", "step3", "breakthrough", "conclusion"),
    10: ("setup", "symptom", "failure", "crisis", "pivot", "step1", "step2", "step3", "breakthrough", "conclusion"),
}
ROLE_SETTINGS: dict[str, str] = {
    "setup": "real_env",
    "symptom": "real_env",
    "failure": "real_env",
    "crisis": "drill_down",
    "pivot": "brain_void",
    "mechanism": "brain_void",
    "step1": "brain_void",
    "step2": "brain_void",
    "step3": "brain_void",
    "breakthrough": "pull_out",
    "conclusion": "real_env",
}


def clip_roles(n_clips: int) -> tuple[str, ...]:
    """Returns the narrative role sequence for a 5-10 clip Short."""
    if n_clips not in CLIP_ROLE_SEQUENCES:
        raise ValueError(f"Clip count must be {CLIP_COUNT_MIN}-{CLIP_COUNT_MAX}, got {n_clips}")
    return CLIP_ROLE_SEQUENCES[n_clips]


def pivot_clip_index(n_clips: int) -> int:
    """0-based index of the 'pivot' (Instead of...) clip for a given clip count."""
    return clip_roles(n_clips).index("pivot")


def script_word_range(n_clips: int) -> tuple[int, int]:
    """Total spoken-word budget for an n-clip script (5 -> 90-140, 10 -> 180-280)."""
    return (n_clips * CLIP_WORDS_MIN, n_clips * CLIP_WORDS_MAX)


# Google Flow Video Generation Model (MANDATORY OMNI 1.1 EXCLUSIVE LOCK)
# All video generation MUST proceed ONLY with Gemini Omni 1.1 (Flash / Quality).
# Other engines (including legacy Veo) are strictly prohibited.
DEFAULT_FLOW_MODEL = "Omni 1.1 Flash"
FLOW_MODEL_QUALITY = "Omni 1.1 Quality"
FLOW_ZERO_CREDIT_FALLBACK_MODEL = "Veo 3.1 - Lite [Lower Priority]"
ALLOWED_FLOW_MODELS = ["Omni 1.1 Flash", "Omni 1.1 Quality", "Veo 3.1 - Lite [Lower Priority]"]
FLOW_MODELS = {
    "Omni 1.1 Flash": "Omni 1.1 Flash - High-throughput, multimodal video engine (Default)",
    "Omni 1.1 Quality": "Omni 1.1 Quality - Maximum cinematic photorealism & cutaway detail",
    "Veo 3.1 - Lite [Lower Priority]": "Veo 3.1 - Lite [Lower Priority] - Unlimited 0-credit Google AI Ultra fallback",
}

# Google Flow Native Voice (Puck only — male documentary narrator)
FLOW_DEFAULT_VOICE = "Puck"
FLOW_ALLOWED_VOICES = ("Puck",)
FLOW_VOICE_TONE_DIRECTION = (
    f"male documentary narrator speaking clear English at {NATIVE_FLOW_WPS} words per second"
)
FLOW_VOICE_PROMPT_DESCRIPTOR = "Consistent deep male baritone documentary narrator"
# v5 voice line (R49): identical, detailed descriptor in every clip so Flow re-creates the same narrator.
# Must stay a single sentence without periods (prompt parser splits on the first period).
FLOW_VOICE_PROMPT_DESCRIPTOR_V5 = (
    "Same calm male documentary narrator in every clip, warm mid-low baritone, steady even pitch, "
    "relaxed measured pace, neutral American accent, no dramatic pitch swings"
)
FLOW_LEGACY_VOICE_LABELS: tuple[str, ...] = (
    FLOW_VOICE_PROMPT_DESCRIPTOR,
    "Deep male baritone documentary narrator",
)

# ==============================================================================
# Prompt System v5 (2026-10-24) — research dossier, visual modes, action physics, brain link,
# plain-language and voice-consistency gates. Documented 1:1 in production_constants.md (v5 block).
# ==============================================================================
PROMPT_SCHEMA_VERSION_V5 = 5
PROMPT_SCENE_WORDS_MAX_V5 = 95           # v5 scenes carry camera + body verb + prop change + reaction
FLOW_ASPECT_SHORTS = "9:16"
FLOW_ASPECT_LONGFORM = "16:9"
FLOW_ASPECT_LABELS: dict[str, str] = {"9:16": "9:16 vertical", "16:9": "16:9 horizontal"}
# Appended after every v5 scene (outside the scene word budget): fluid acting, centred safe framing for reuse.
FLOW_MOTION_STYLE_V5 = (
    "Articulated matte-white porcelain figures move with fluid, natural human motion; "
    "key action stays centred in frame."
)

VISUAL_MODES: tuple[str, ...] = ("BEHAVIORAL_PSYCH", "HYBRID", "NEURO_BIOLOGY")
BRAIN_SETTINGS: tuple[str, ...] = ("drill_down", "brain_void")     # clips counted as brain clips
ALLOWED_SETTINGS_V5: tuple[str, ...] = ("real_env", "drill_down", "brain_void", "pull_out")
MAX_BRAIN_CLIPS_BY_MODE: dict[str, int] = {"BEHAVIORAL_PSYCH": 0, "HYBRID": 2, "NEURO_BIOLOGY": 4}
MAX_ANATOMY_TERMS_BY_MODE: dict[str, int] = {"BEHAVIORAL_PSYCH": 1, "HYBRID": 2, "NEURO_BIOLOGY": 4}
# Default per-role setting by mode (a shot may override with visual_plan.shots[role].setting within the caps).
MODE_ROLE_SETTINGS: dict[str, dict[str, str]] = {
    "BEHAVIORAL_PSYCH": {r: "real_env" for r in ROLE_SETTINGS},
    "HYBRID": {
        **{r: "real_env" for r in ROLE_SETTINGS},
        "pivot": "drill_down",
        "mechanism": "brain_void",
        "step1": "brain_void",
        "step2": "pull_out",
    },
    "NEURO_BIOLOGY": {
        **{r: "real_env" for r in ROLE_SETTINGS},
        "crisis": "drill_down",
        "pivot": "brain_void",
        "mechanism": "brain_void",
        "step1": "brain_void",
        "step2": "brain_void",
        "step3": "pull_out",
    },
}
ICONIC_SCENE_MAX_CLIP = 2                # The must-have iconic scene appears in clip 1 or 2 (hook)
READABILITY_SCRIPT_FK_MAX = 8.0          # Flesch-Kincaid grade, whole script
READABILITY_CLIP_FK_MAX = 11.0           # Flesch-Kincaid grade, any single clip
JARGON_TERMS_MAX = 1                     # Non-anatomical technical terms per script
SECOND_PERSON_CLIPS_MIN = 1              # Clips that connect the story to "you" (everyday consequence)

# Voice consistency (R49) — semitone gates on per-clip median F0, never corrected by pitch shifting.
VOICE_F0_CLIP_DEV_MAX_ST = 1.5           # |clip F0 - project median| in semitones
VOICE_F0_ADJ_JUMP_MAX_ST = 2.0           # |clip k+1 - clip k| in semitones
VOICE_F0_SPREAD_MAX_ST = 3.0             # max - min across the project, semitones
VOICE_REGEN_MAX_ROUNDS = 4               # Flow regeneration rounds for voice outliers before the TTS fallback
VOICE_FALLBACK_ENABLED = True            # Decision 2026-10-24: local free TTS fallback when Flow voice stays inconsistent
VOICE_FALLBACK_ENGINE = "kokoro-onnx"    # Apache-2.0 local model, zero paid APIs
VOICE_FALLBACK_VOICE = "am_fenrir"       # Deep cinematic American male baritone; fixed for the whole channel
VOICE_FALLBACK_SPEED = 1.00              # Natural 1.00x documentary pacing for Kokoro am_fenrir
VOICE_FALLBACK_MODEL_DIR = Path.home() / ".cache" / "aab_tts"
VOICE_FALLBACK_VIDEO_SPEED_RANGE: tuple[float, float] = (0.75, 1.15)  # video setpts factor range to fit TTS length

# Research dossier + longform reuse (R44, R50)
RESEARCH_DOSSIERS_DIRNAME = "research_dossiers"
ASSET_LIBRARY_DIRNAME = "asset_library"
LONGFORM_TARGET_MIN_SEC = 480            # 8-15 min longform built from proven Shorts
LONGFORM_TARGET_MAX_SEC = 900

# Reference Image Consistency & 10-Axis Granular Image QA (R51)
REF_IMAGES_DIRNAME = "reference_images"
MIN_REF_IMAGES_PER_PROJECT = 6           # Minimum reference images per project (cast, env, hero prop, scenes/clips)
MIN_REF_IMAGE_SIZE_BYTES = 30_000        # Minimum valid PNG/JPG size (30 KB)
REF_IMAGE_MIN_WIDTH_SHORTS = 720         # Minimum width for 9:16 reference image
REF_IMAGE_MIN_HEIGHT_SHORTS = 1280       # Minimum height for 9:16 reference image
REF_IMAGE_LUMA_MIN = 70.0                # R14-A high-key daylight floor (mean luma 0-255)
REF_IMAGE_LUMA_MAX = 242.0               # R14-A ceiling (avoids pure whiteout)
REF_IMAGE_CONTRAST_STD_MIN = 22.0        # Minimum luma standard deviation (dynamic contrast)
REF_IMAGE_SHARPNESS_MIN = 45.0           # Minimum Laplacian variance sharpness
REF_IMAGE_EDGE_DENSITY_MIN = 0.015       # Minimum Canny edge density
REF_IMAGE_PORCELAIN_RATIO_MIN = 0.04     # Minimum matte-white/neutral porcelain highlight ratio in subject zone
REF_IMAGE_HUMAN_SKIN_MAX = 0.12          # Maximum allowed human flesh-tone ratio in mannequin head/body zone
REF_IMAGE_CROSS_HIST_CORR_MIN = 0.55     # Minimum HSV histogram correlation across same-scene reference images
REF_IMAGE_CROSS_LUMA_SPREAD_MAX = 55.0   # Maximum luma mean spread across same-scene reference images
REF_IMAGE_CAST_CHROMA_DRIFT_MAX = 16.0   # Maximum LAB chrominance drift across cast appearances
REF_IMAGE_CLIP_CONTINUITY_CORR_MIN = 0.55  # Minimum HSV correlation between rendered video clip and its reference image
REF_IMAGE_MAX_REGEN_ROUNDS = 3           # Automatic regeneration rounds in Flow Image mode when a reference image fails QA
REF_IMAGE_MIN_DHASH_DISTANCE = 6         # Q10: two clip keyframes closer than this (64-bit dHash) are duplicates
REF_IMAGE_BIOLUM_MIN = 0.005             # Q6: minimum saturated 4-point colour-code pixel ratio in brain shots
# Provenance: only images generated for the pack count before clip generation. Frames pulled out of
# already-rendered clips ("extracted_from_clip") are audit-only and can never satisfy the pre-generation gate.
REF_IMAGE_SOURCES_PRE_GENERATION: tuple[str, ...] = ("flow_image_generation", "gemini_image_generation")
REF_IMAGE_SOURCE_EXTRACTED = "extracted_from_clip"

# Source-to-prompt architecture (R52): research dossier -> scene blueprint -> reference frames -> clip packets
SCENE_BLUEPRINT_FILENAME = "scene_blueprint.json"
GENERATION_PACKETS_DIRNAME = "generation_packets"
GENERATION_BACKENDS: tuple[str, ...] = ("flow", "gemini_app")
VOICE_SOURCES: tuple[str, ...] = ("tts", "native")   # tts = am_fenrir voiceover added in Gear 4 (default)
DEFAULT_VOICE_SOURCE = "tts"
CLIP_MAX_RENDER_SEC = int(FLOW_VIDEO_MODEL_PROFILES[FLOW_ACTIVE_VIDEO_MODEL]["max_sec"])  # Omni 10 s (no ingredient)
CLIP_MAX_RENDER_SEC_WITH_REFERENCE = int(FLOW_VIDEO_MODEL_PROFILES[FLOW_ACTIVE_VIDEO_MODEL]["max_sec_with_ingredient"])  # 8 s
GEMINI_APP_MAX_RENDER_SEC = 8
TIMED_BEAT_WINDOWS: tuple[tuple[int, int], ...] = ((0, 3), (3, 6), (6, 8))  # action / prop change / reaction
BLUEPRINT_MIN_EVIDENCE_ICONIC = 1        # iconic scene needs >= 1 media timecode or source citation per beat set

# ==============================================================================
# Prompt & Assembly System v6 — Neuro-Diorama 3-Minute Long-Short (R56-R61)
# ==============================================================================
PRODUCTION_PROFILES: tuple[str, ...] = ("classic_v5", "neuro_diorama")
DEFAULT_PRODUCTION_PROFILE = "neuro_diorama"
PROMPT_SCHEMA_VERSION_V6 = 6

# Visual grammar & zero-flesh / frosted-crystal specimen / dark midnight-navy void locks (R56)
DIORAMA_ZERO_FLESH_LOCK = True
DIORAMA_ALLOW_CRYSTAL_SPECIMEN = True
DIORAMA_CRYSTAL_SPECIMEN_MAX_RATIO = 0.20      # At most 20% of base clips use frosted-crystal partial specimens; >=80% Ghost-Lab
DIORAMA_BACKDROP_STYLE = "deep midnight-navy studio void"
DIORAMA_LIGHTING_STYLE = "cinematic chiaroscuro rim lighting"
DIORAMA_BRAIN_RENDER_MODES: tuple[str, ...] = (
    "matte_white_cortical_sulcal_glow",
    "translucent_smoked_glass_subcortical_xray",
)
DIORAMA_VISUAL_GRAMMARS: tuple[str, ...] = (
    "arch_cutaway_diorama",
    "kinetic_trace_automata",
    "recurring_gauge_motif",
    "tactile_token_grid",
    "literal_analogy_cutaway",
    "arch_brain_maquette",
    "frosted_crystal_specimen",
)
DIORAMA_CAMERA_MOVES: tuple[str, ...] = (
    "smooth_tilt_up",
    "smooth_tilt_down",
    "horizontal_tracking_pan",
    "isometric_push_in",
    "locked_macro_gauge",
    "dynamic_dolly_rush_in",
    "orbital_3d_arc_sweep",
    "crane_swoop_dive",
    "low_angle_chase_track",
    "vertical_rocket_ascent",
    "fpv_trench_passthrough",
    "pullback_parallax_reveal",
)
DEFAULT_DIORAMA_CAMERA_PROFILE = "dynamic_3d_cinema_rig"
DIORAMA_DYNAMIC_3D_CAMERA_MOVES: tuple[str, ...] = (
    "dynamic_dolly_rush_in",
    "orbital_3d_arc_sweep",
    "crane_swoop_dive",
    "low_angle_chase_track",
    "vertical_rocket_ascent",
    "fpv_trench_passthrough",
    "pullback_parallax_reveal",
)
DIORAMA_MOTIF_APPEARANCES_MIN = 4              # Recurring analog gauge prop appears >= 4 times across Acts 1-6 (R56)
DIORAMA_MOTIF_APPEARANCES_MAX = 8
DIORAMA_SCENE_WORDS_MIN = 45
DIORAMA_SCENE_WORDS_MAX = 115

# 6-Act 3-minute US English Long-Short script, cold-open hook & high-density storyteller contract (R57)
DIORAMA_ACT_COUNT = 6
DIORAMA_SENTENCE_COUNT_MIN = 48
DIORAMA_SENTENCE_COUNT_MAX = 58
DIORAMA_SENTENCE_WORDS_MAX = 15                # Concise woven clauses for Schema v6 (Schema v7 uses DIORAMA_V7_SENTENCE_WORDS_MAX = 18)
DIORAMA_V7_SENTENCE_WORDS_MAX = 18             # Concrete, intuitive causal storytelling clauses in Schema v7 (R57-C)
DIORAMA_WORD_COUNT_MIN = 440
DIORAMA_WORD_COUNT_MAX = 505
DIORAMA_BANNED_SLOGAN_OPENERS: tuple[str, ...] = (
    "university brain science, made simple",
    "what university neuroscience teaches, made simple",
    "college brain science, made simple",
    "all about brain",
)
DIORAMA_BANNED_WEAK_HOOK_PREFIXES: tuple[str, ...] = (
    "imagine ",
    "picture this",
    "have you ever ",
    "what if ",
    "suppose ",
)
# --- Schema v7 3-sentence Cold-Open (R57-H2, approved HM Plan B 2026-10-31) ---
# S1 myth-flip / paradox shock ending in '!' (rush gear) -> S2 'Yet/But...' contrast (rush gear)
# -> S3 'This is the true story of <case>.' case stamp (stamp gear + chapter headline)
DIORAMA_V7_REQUIRE_COLD_OPEN = True
DIORAMA_V7_COLD_OPEN_S1_MAX_WORDS = 18
DIORAMA_V7_COLD_OPEN_S2_MAX_WORDS = 12
DIORAMA_V7_COLD_OPEN_S2_PREFIXES: tuple[str, ...] = ("yet ", "but ", "and yet ", "still ", "meanwhile ")
DIORAMA_V7_COLD_OPEN_CASE_STAMP_PREFIX = "this is the true story of "
DIORAMA_BANNED_AI_CLICHES: tuple[str, ...] = (
    "delve into",
    "delving into",
    "let's unpack",
    "unpack this",
    "unpack why",
    "underscore",
    "highlight the fact",
    "pivotal",
    "paramount",
    "tapestry",
    "multifaceted",
    "testament to",
    "shed light on",
    "furthermore",
    "moreover",
    "in addition to this",
    "consequently",
    "nevertheless",
    "in conclusion",
)
DIORAMA_BANNED_SEMINAR_TRANSITIONS: tuple[str, ...] = (
    "moving on to",
    "this paper looks at",
    "the main region here is",
    "to wrap up and bring everything together",
    "as we saw across",
    "if we look at the three main",
)
DIORAMA_REQUIRE_SIGNATURE_HOOKS = True         # Immediate 0.10s paradox cold-open + R24 dual memes + R26 openers
DIORAMA_DURATION_MIN_SEC = 140.0
DIORAMA_DURATION_TARGET_SEC = 158.0
DIORAMA_DURATION_MAX_SEC = 179.0               # Safe margin below YouTube Shorts 180.00s hard ceiling
SHORTS_HARD_CEILING_SEC = 179.0
SHORTS_HARD_CEILING_FRAMES = 5370              # 179.0s x 30fps
DIORAMA_NUMBER_ANALOGY_MAX_SENTENCE_GAP = 1    # Every core quantitative metric paired within <=1 sentence with an everyday analogy

# Unlimited 1:1 Zero-Reuse Flow clips & 3-Gear Dynamic EDL contract (R58)
DIORAMA_CLIP_COUNT_MIN = 20                    # Legacy cross-cut floor; zero_clip_reuse=True requires >= len(sentences)+1 (~56-66 clips)
DIORAMA_CLIP_COUNT_DEFAULT = 60                # 1:1 sentence + multi-beat 2-cut action pairs + split + outro default
DIORAMA_CLIP_COUNT_MAX = 240                   # Uncapped headroom for 0-credit unlimited Flow generation
DIORAMA_MAX_CLIP_REUSE = 1                     # Strict 0% reuse lock (every clip appears once at 1.00x full framing)
DIORAMA_SHARD_MAX_CLIPS = 14                   # Max clips per Flow project shard (avoids >24-tile virtual-scroll DOM unmount)
DIORAMA_CLIP_RENDER_SEC = 8
DIORAMA_SLICE_WINDOWS_SEC: tuple[tuple[float, float], ...] = (
    (0.20, 2.45),
    (2.60, 4.85),
    (5.00, 7.25),
)
DIORAMA_SLICE_CROPS: tuple[float, ...] = (1.00, 1.12, 1.22)
DIORAMA_TARGET_CUT_MIN = 52
DIORAMA_TARGET_CUT_MAX = 110
DIORAMA_MIN_CUT_DURATION_SEC = 1.30            # Gear-1 fast montage floor (1.30-1.95s) while keeping avg ~2.55s
DIORAMA_VISUAL_PLAYBACK_SPEED = 1.12           # Snappy lively 3D motion speed
DIORAMA_ENTRY_SPEED_RAMP = True                # Crisp 0.35s entry kinetic speed-ramp (1.26x -> 1.10x) on cuts
DIORAMA_ENTRY_RAMP_START_SPEED = 1.26
DIORAMA_ENTRY_RAMP_MAIN_SPEED = 1.10
DIORAMA_ACT5_MONTAGE_CUT_MIN_SEC = 0.65
DIORAMA_ACT5_MONTAGE_CUT_MAX_SEC = 1.10

# Documentary restraint audio, crisp high-tenor en-US-AndrewMultilingualNeural storyteller voice & Y=64% subtitles (R59)
DIORAMA_TTS_ENGINE = "edge_tts"                 # Free Microsoft Neural storyteller engine (kokoro-onnx offline fallback)
DIORAMA_TTS_VOICE = "en-US-AndrewMultilingualNeural"  # Crisp, natural American male documentary storyteller (Option 4A Silk Clean)
DIORAMA_TTS_OUTPUT_FORMAT = "audio-24khz-96kbitrate-mono-mp3"  # 2x raw CBR bitrate over 48kbps default (0.000s timing diff)
DIORAMA_TTS_BITRATE_BPS = 96000                 # Exact CBR bps for multi-chunk SentenceBoundary offset compensation
DIORAMA_TTS_RATE = "+32%"                       # Legacy Schema v6 fast journalistic cadence (Schema v7 uses DIORAMA_V7_TTS_RATE)
DIORAMA_TTS_PITCH = "+14Hz"                     # Native neural high-tenor pitch (+14Hz, zero formant/asetrate distortion)
DIORAMA_TTS_SPEED = 1.10                        # Offline kokoro-onnx fallback speed
DIORAMA_MIN_CONVERSATIONAL_QUESTIONS = 4        # Minimum rhetorical '?' hooks across 6 Acts for storyteller tone (R57)
DIORAMA_SPEECH_PAUSE_SEC = 0.14                 # Snappy inter-sentence breath gap (when synthesized line-by-line)
DIORAMA_ACT_BOUNDARY_PAUSE_SEC = 0.24           # Crisp structural breath transition between Acts 1->2->3->4->5->6
DIORAMA_PAUSE_TUNE_RANGE_SEC: tuple[float, float] = (0.10, 0.32)
DIORAMA_ATEMPO_FIT_RANGE: tuple[float, float] = (0.95, 1.04)
DIORAMA_ACTIVE_SPEECH_RATIO_MIN = 0.84
DIORAMA_BGM_BPM = 88
DIORAMA_BGM_DUCK_DB = -24.0
DIORAMA_OUTRO_SWELL_SEC = 2.2
DIORAMA_OUTRO_SWELL_GAIN_DB = 8.0
DIORAMA_TARGET_LUFS = -15.5
DIORAMA_MAX_LRA_LU = 4.0
DIORAMA_SUBTITLE_FONT_SIZE = 76
DIORAMA_SUBTITLE_OUTLINE_WIDTH = 4.5
DIORAMA_SUBTITLE_MARGIN_V = 650                # Y=66.1% / 64% center-lower documentary zone (1920 - 650 = 1270px)
DIORAMA_SUBTITLE_MAX_WORDS = 3
DIORAMA_SUBTITLE_HIGHLIGHT_GOLD = False
DIORAMA_CALLOUT_FONT_SIZE = 64
DIORAMA_CALLOUT_MARGIN_V = 1520                # Y=20.8% clean top space for year/metric callouts
DIORAMA_CALLOUT_COUNT_RANGE: tuple[int, int] = (4, 8)
DIORAMA_OUTRO_TITLE_FONT_SIZE = 84
DIORAMA_OUTRO_TITLE_MARGIN_V = 1140            # Y=40.6% upper-sky anchor during final tilt-up

# 2-Clause US English Paradox Title contract (R60)
TITLE_MAX_CHARS_DIORAMA = 95                   # Under YouTube 100-char limit; replaces 60-char hard truncation

# ==============================================================================
# Prompt & Assembly System v7 — Full-Bleed Low-Poly Pastel Architecture (R63)
# ==============================================================================
PROMPT_SCHEMA_VERSION_V7 = 7
DIORAMA_V7_STYLE_PROFILE = "lowpoly_pastel_v7"
PORCELAIN_V7_STYLE_PROFILE = "porcelain_cinematic_v7"
DIORAMA_V7_STYLE_PROFILES: tuple[str, ...] = (DIORAMA_V7_STYLE_PROFILE, PORCELAIN_V7_STYLE_PROFILE)
DEFAULT_DIORAMA_STYLE_PROFILE = PORCELAIN_V7_STYLE_PROFILE

PORCELAIN_V7_WORLD_STYLE = "photorealistic bright high-key documentary studio world"
PORCELAIN_V7_CAST_STYLE = "clothed articulated matte-white porcelain figures with translucent frosted-glass craniums"
PORCELAIN_V7_OPTICS_LOCK = "crisp cinema prime lens clarity with soft natural studio daylight and subtle rim lighting"
PORCELAIN_V7_LUMA_RANGE: tuple[float, float] = (88.0, 226.0)
PORCELAIN_V7_DARK_VOID_RATIO_MAX = 0.24          # HSV V < 35 ceiling across photorealistic high-key porcelain scenes
PORCELAIN_V7_SATURATION_RANGE: tuple[float, float] = (8.0, 115.0)
PORCELAIN_V7_NEON_GREEN_SPILL_MAX = 0.015       # Max HSV fluorescent-green pixel fraction in brain clips (blocks AI slime/dust)
PORCELAIN_V7_BRAIN_MARGIN_SAT_MAX = 48.0        # Outer studio margin saturation cap around whole-brain 3D gallery models
PORCELAIN_V7_HUMAN_SKIN_MAX = 0.14              # Max HSV+YCrCb flesh-tone ratio on porcelain hands/closeup clips

PORCELAIN_V7_BRAIN_RENDER_MODES: tuple[str, ...] = (
    "cortical_vascular_whole",
    "sagittal_coronal_cutaway",
    "frosted_glass_subcortical_xray",
    "bounded_micro_channel",
)
PORCELAIN_V7_VISUAL_GRAMMARS: tuple[str, ...] = (
    "porcelain_fullbleed_world",
    "porcelain_hands_closeup",
    "porcelain_pov_hands",
    "porcelain_cutaway_section",
    "porcelain_literal_analogy",
    "porcelain_living_brain",
)

DIORAMA_V7_WORLD_STYLE = "full-bleed bright diffused pastel daylight world"
DIORAMA_V7_SHADER_STYLE = "untextured flat-shaded matte low-poly 3D"
DIORAMA_V7_OPTICS_LOCK = "crisp infinite deep focus from foreground to horizon"
DIORAMA_V7_LUMA_RANGE: tuple[float, float] = (105.0, 168.0)
DIORAMA_V7_DARK_VOID_RATIO_MAX = 0.14          # HSV V < 35 ceiling across full-bleed pastel frames
DIORAMA_V7_SATURATION_RANGE: tuple[float, float] = (24.0, 52.0)
DIORAMA_V7_CUTAWAY_MAX_RATIO = 0.15            # <= 15% architectural cross-section cuts; >= 85% full-bleed world
DIORAMA_V7_BRAIN_RENDER_MODES: tuple[str, ...] = (
    "matte_pastel_cortical_model",
    "matte_pastel_sagittal_cutaway",
)
DIORAMA_V7_VISUAL_GRAMMARS: tuple[str, ...] = (
    "lowpoly_fullbleed_world",
    "lowpoly_hands_closeup",
    "lowpoly_pov_hands",
    "lowpoly_cutaway_section",
    "lowpoly_literal_analogy",
    "lowpoly_matte_brain",
)
ALL_DIORAMA_V7_VISUAL_GRAMMARS: tuple[str, ...] = DIORAMA_V7_VISUAL_GRAMMARS + PORCELAIN_V7_VISUAL_GRAMMARS
DIORAMA_V7_CAMERA_MOVES: tuple[str, ...] = (
    "locked_tripod",
    "pan_left",
    "pan_right",
    "tilt_up",
    "tilt_down",
    "gentle_push_in",
    "clean_pullback_reveal",
)
DIORAMA_V7_LOCKED_CAMERA_MIN_RATIO = 0.35      # ~40% tripod lock-off so viewers focus on internal prop/hand mechanics
DIORAMA_V7_ZOOM_CAMERA_MAX_RATIO = 0.30
DIORAMA_V7_VIDEO_FPS = 24                      # Native 24.0fps Flow cadence (0% 24->30 nearest-neighbor pulldown judder)
DIORAMA_V7_DURATION_MIN_SEC = 140.0            # Minimum assembled Long-Short duration for Schema v7
SHORTS_HARD_CEILING_FRAMES_V7 = 4296           # 179.0s x 24fps
DIORAMA_V7_RAPID_CUT_MIN_SEC = 0.68            # Rapid impact sub-cuts (0.68-1.35s)
DIORAMA_V7_MID_ACT_MAX_CUT_SEC = 4.60          # Target single-sentence cut ceiling across Acts 3-4 to prevent mid-video stalls (R57-M)
DIORAMA_V7_LONG_TAKE_MAX_SEC = 6.50            # Hard cap on 2-sentence mechanism holds (down from 7.20s, R57-M/R63)
DIORAMA_V7_CUT_CV_MIN = 0.36                   # Dynamic cut-duration coefficient of variation (std / mean >= 0.36, R57-M/R63)
DIORAMA_V7_SPLIT_MODE = "split_hstack"         # Left/Right vertical split-screen in 9:16 portrait
DIORAMA_V7_SPLIT_DIVIDER_PX = 6                # Solid #000000 black vertical divider bar
DIORAMA_V7_VISUAL_PLAYBACK_SPEED = 1.00        # Unified 1.00x natural 24fps visual playback speed (0% speed-ramp knees)
DIORAMA_V7_TTS_RATE = "+8%"                    # Unified 1.08x (+8%) crisp en-US-AndrewMultilingualNeural storyteller cadence
DIORAMA_V7_TTS_PITCH = "+14Hz"                 # Native neural high-tenor pitch (+14Hz, F0 ~132Hz) for mobile speaker clarity
DIORAMA_V7_TTS_VOLUME = "-10%"                 # Internal neural vocoder headroom (-10%) preventing high-pitch plosive tearing
DIORAMA_V7_TTS_SPEED = 1.08                    # Unified 1.08x offline kokoro-onnx fallback speed for Schema v7
DIORAMA_V7_WPM_MIN = 135.0                     # Minimum spoken WPM gate at unified 1.08x (+8%) trimmed cadence
DIORAMA_V7_WPM_MAX = 212.0                     # Maximum spoken WPM gate for Schema v7
DIORAMA_V7_INTERNAL_SILENCE_TRIM_THRESHOLD_SEC = 0.28
DIORAMA_V7_INTERNAL_BREATH_KEEP_SEC = 0.14
DIORAMA_V7_INTER_SENTENCE_PAUSE_SEC = 0.15
DIORAMA_V7_ACT_BOUNDARY_PAUSE_SEC = 0.32
DIORAMA_V7_ACTIVE_VOICED_RMS_RATIO_MIN = 0.80  # Natural human-breath RMS voiced density floor (>= 80%, blocks dead air)

# --- Sentence-level Prosody Engine (rush / stamp / brisk gears, R63-P) ---
DIORAMA_V7_PROSODY_MODES: tuple[str, ...] = ("uniform_108x", "uniform_110x", "dynamic_rush_v7")
DIORAMA_V7_PROSODY_MODE = "dynamic_rush_v7"    # Channel default (Plan B approved 2026-10-31); per-project override via script.json `prosody_mode`
DIORAMA_V7_PROSODY_BASE_RATE = "+8%"           # dynamic_rush_v7 synthesizes once at the approved +8% Silk Clean timbre
DIORAMA_V7_PROSODY_UNIFORM_110_RATE = "+10%"   # uniform_110x native edge-tts rate (no WSOLA post-processing)
DIORAMA_V7_PROSODY_UNIFORM_110: dict[str, float] = {
    "trim_thresh": 0.14,     # internal silences longer than this are compressed
    "trim_keep": 0.045,      # ... down to this
    "gap_before": 0.085,     # inserted gap before a regular sentence
    "stamp_gap_before": 0.17,  # inserted gap before a stamp sentence (acoustic ~0.25s incl. pads)
    "act_gap_before": 0.20,  # inserted gap at Act boundaries
}
DIORAMA_V7_PROSODY_GEARS: dict[str, dict[str, float]] = {
    "rush": {"tempo": 1.12, "trim_thresh": 0.06, "trim_keep": 0.02, "gap_before": 0.025},
    "stamp": {"tempo": 1.08, "trim_thresh": 0.16, "trim_keep": 0.06, "gap_before": 0.17},
    "brisk": {"tempo": 1.15, "trim_thresh": 0.12, "trim_keep": 0.04, "gap_before": 0.065},
}
# Native per-gear edge-tts synthesis rates (Q-1, 2026-10-31): each Act is synthesized once per needed gear rate and
# every sentence is sliced from the stream matching its gear, so the WSOLA factor is 1.0 (no atempo phasiness).
DIORAMA_V7_PROSODY_GEAR_RATES: dict[str, str] = {"rush": "+12%", "stamp": "+8%", "brisk": "+15%"}
DIORAMA_V7_PROSODY_SPLICE_FADE_SEC = 0.014       # Smooth 14ms raised-cosine edge fade (replaces 6ms hard gate)
DIORAMA_V7_MASTER_DEESSER = "deesser=i=0.48:m=0.5:f=0.5:s=o"  # Studio velvet de-esser (< 0.58; tames 4-10kHz vocoder sibilance)
DIORAMA_V7_PROSODY_ACT_GAP_MIN = 0.20          # Act boundary gap floor in dynamic_rush_v7
DIORAMA_V7_PROSODY_MAX_ADJ_TEMPO_JUMP = 0.05   # Max adjacent WSOLA factor jump when the inserted gap is < 0.10s
DIORAMA_V7_PROSODY_RUSH_MAX_STREAK = 3         # 4th consecutive rush sentence is demoted to brisk
DIORAMA_V7_PROSODY_EMPHASIS_PAUSE_SEC = 0.0    # 0.0s = zero mid-sentence digital zero-slicing (preserves co-articulation)
DIORAMA_V7_PROSODY_EMPHASIS_GAIN_DB = 1.0      # Smooth 25ms cosine emphasis contour lift without cutting connected speech
DIORAMA_V7_PROSODY_STAMP_PHRASES: tuple[str, ...] = (
    "this is the true story",
    "here is what went wrong",
    "completely stunned",
    "total nightmare",
    "which proves",
    "which is why",
)
DIORAMA_V7_PROSODY_RUSH_CLIMAX_WORDS: tuple[str, ...] = ("yet", "then", "suddenly", "instead")
DIORAMA_V7_PROSODY_REHOOK_PHRASES: tuple[str, ...] = (
    "wasn't the strangest",
    "was not the strangest",
    "but here's",
    "but here is",
    "here is what went wrong",
)
# Prosody QA gates (P1-P10)
PROSODY_P1_FIRST_ONSET_MAX_SEC = 0.10
PROSODY_P2_HOOK_END_MAX_SEC = 9.0              # end of sentence 2 (recalibrated to the approved 3-sentence cold-open: HM Plan B S2 ends 8.4s)
PROSODY_P2_STAMP_END_MAX_SEC = 11.5            # end of sentence 3 when it is the case stamp (HM Plan B S3 ends 10.9s)
PROSODY_P3_TEMPO_TOLERANCE = 0.03              # applied tempo within +/-3% of the gear target
PROSODY_P4_RUSH_MAX_INTERNAL_SILENCE_SEC = 0.07  # 10ms RMS window quantization on a 0.06s trim threshold
PROSODY_P5_STAMP_PRE_SILENCE_RANGE: tuple[float, float] = (0.20, 0.32)
PROSODY_P6_ASR_MATCH_MIN = 0.95
PROSODY_P10_OPEN_LOOP_MAX_GAP_SEC = 35.0
DIORAMA_V7_AUDIO_CHANNELS = 2                  # 2-channel stereo acoustic/orchestral documentary score
DIORAMA_MUX_TRUE_PEAK_TARGET_DBTP = -1.5       # Encoded AAC true-peak ceiling (= Prosody QA P7 limit); fallback static trim only if the oversampled limiter is not enough
DIORAMA_MUX_TRUE_PEAK_LIMITER = "aresample=192000,alimiter=limit=0.794:attack=1:release=50:level=disabled,aresample=48000"  # v7 4x-oversampled -2.0 dBFS true-peak limiter before AAC
DIORAMA_V7_BGM_DUCK_DB = -22.0
FONT_CONDENSED_BLACK_PATH = FONTS_DIR / "AABCondensed-Black.ttf"
DIORAMA_V7_SUBTITLE_FONT_NAME = "AAB Condensed Black"
DIORAMA_V7_SUBTITLE_FONT_SIZE = 94
DIORAMA_V7_SUBTITLE_OUTLINE_WIDTH = 5.5
DIORAMA_V7_SUBTITLE_SHADOW_DEPTH = 0.0
DIORAMA_V7_SUBTITLE_MARGIN_V = 672             # Y_center ≈ 1209px, H_median ≈ 52px on 1080x1920 (0f contiguous handoff)
DIORAMA_V7_CHAPTER_HEADLINE_FONT_SIZE = 276    # Giant top chapter impact headline (~144px single-line height)
DIORAMA_V7_CHAPTER_HEADLINE_OUTLINE_WIDTH = 2.5
DIORAMA_V7_CHAPTER_HEADLINE_MARGIN_V = 180
DIORAMA_V7_CHAPTER_HEADLINE_SCALE_X = 85       # Horizontal condensation keeping 10-char headlines <= 850px (>= 110px side margins)
DIORAMA_V7_CHAPTER_HEADLINE_MARGIN_LR = 85     # Left/right horizontal safe margin for ChapterHeadline style
DIORAMA_V7_CHAPTER_HEADLINE_MAX_WIDTH_PX = 920 # Maximum rendered pixel width on 1080x1920 (>= 80px safe margin per side)
DIORAMA_V7_ANATOMY_LABEL_FONT_SIZE = 104       # Programmatic upper-viewport anatomical region badge (mobile-legible 104pt, zero AI text)
DIORAMA_V7_ANATOMY_LABEL_OUTLINE_WIDTH = 5.0
DIORAMA_V7_ANATOMY_LABEL_SCALE_X = 90          # Condensed horizontal fit keeping 1- or 2-line region badges <= 880px (>= 100px side margins)
DIORAMA_V7_ANATOMY_LABEL_MARGIN_V = 190        # Top-aligned at Y≈9.9%..19.8% (strictly < 23% clean-scene ROI & above Y≈31% 3D brain crown)

# --- Post-Hoc Clip-by-Clip Expressive Clarity Verification QA (R64) ---
POSTHOC_SEMANTIC_QA_REPORT_FILENAME = "posthoc_semantic_qa_report.json"
POSTHOC_SEMANTIC_REVIEW_FILENAME = "posthoc_semantic_review.json"
POSTHOC_VIEWER_STRIPS_DIRNAME = "posthoc_viewer_strips"
POSTHOC_CUTS_PER_VIEWER_SHEET = 6
POSTHOC_MIN_CUT_CLARITY_SCORE = 75.0           # Minimum per-cut visual expression clarity score (0..100)
POSTHOC_MIN_EPISODE_MEAN_CLARITY_SCORE = 82.0  # Minimum episode-wide mean clarity score across all cuts
POSTHOC_MIN_SHARPNESS_LAPLACIAN = 12.0         # Minimum clean-ROI Laplacian focus variance on 360x640 standardized grid
POSTHOC_MIN_EDGE_DENSITY = 0.005               # Minimum Canny structural edge ratio in clean action ROI
POSTHOC_MIN_FG_BG_CONTRAST_DE = 4.0            # Minimum LAB perceptual contrast deltaE between subject core and periphery
POSTHOC_MIN_MOVING_CAM_DIFF = 1.00             # Minimum mean temporal luma diff across moving-camera cuts
POSTHOC_LOCKED_TRIPOD_MIN_P95_DIFF = 1.50      # Minimum 95th-percentile localized hand/prop motion diff on locked_tripod cuts
POSTHOC_MAX_STEP_HIST_JUMP = 0.78              # Maximum normalized HSV histogram step distance before flagging mid-cut morph
POSTHOC_SPLIT_PANE_MIN_DIFF = 10.0             # Minimum mean pixel difference between split-screen panes
POSTHOC_BRAIN_HIGHLIGHT_MIN_CHROMA = 6.0       # Minimum p98-vs-median LAB chroma accent separation on lesion/anatomy brain cuts
POSTHOC_ANALOGY_SYNC_TOLERANCE_SEC = 0.45      # Maximum timing delta (s) between ASR spoken analogy phrase and visual cut
POSTHOC_MIN_REVIEW_NOTE_CHARS = 20             # Minimum character length for per-cut observed_visual_summary
POSTHOC_MAX_IDENTICAL_REVIEW_NOTES = 3         # Max allowed identical review summaries across cuts (>= 4 rejected as boilerplate)

# --- Accumulated Knowledge Hub & Reusable Asset Intelligence Layout (R50-B) ---
KNOWLEDGE_BASE_DIRNAME = "knowledge_base"
KNOWLEDGE_BASE_DIR = CHANNEL_ROOT / KNOWLEDGE_BASE_DIRNAME
KNOWLEDGE_TELEMETRY_DIRNAME = "telemetry"
EPISODES_INDEX_FILENAME = "episodes_index.jsonl"
CLIP_CLARITY_LEDGER_FILENAME = "clip_clarity_ledger.jsonl"
QA_ANALYTICS_SUMMARY_FILENAME = "qa_analytics_summary.json"
REUSABLE_PACKS_DIRNAME = "reusable_packs"
EXPERIMENTS_ARCHIVE_DIRNAME = "experiments"



def _parse_schema_version_int(profile_or_plan: dict[str, Any]) -> int:
    """Safely extracts an integer schema version (e.g. `7`, `'7'`, `'v7'`), returning `0` for named schemas like `'episode_qa_contract_v2'`."""
    for key in ("schema_version", "schema"):
        raw = profile_or_plan.get(key)
        if isinstance(raw, bool) or raw is None:
            continue
        if isinstance(raw, (int, float)):
            return int(raw)
        s = str(raw).strip().lower()
        if s.startswith("v") and s[1:].isdigit():
            return int(s[1:])
        if s.isdigit():
            return int(s)
    return 0


def extract_explicit_v7_style_profile(profile_or_plan: Any) -> str | None:
    """
    Returns an explicit style marker (`'porcelain_cinematic_v7'`, `'lowpoly_pastel_v7'`, `'dark_ceramic_v6'`, `'classic_v5'`)
    when `profile_or_plan` carries an explicit style/shader/grammar signal, or `None` when untagged.
    """
    if isinstance(profile_or_plan, str):
        s_norm = profile_or_plan.strip().lower()
        if s_norm in (PORCELAIN_V7_STYLE_PROFILE, "porcelain_v7"):
            return PORCELAIN_V7_STYLE_PROFILE
        if s_norm == DIORAMA_V7_STYLE_PROFILE:
            return DIORAMA_V7_STYLE_PROFILE
        if s_norm in ("dark_ceramic_v6", "diorama_v6", "v6", "classic_v5"):
            return "dark_ceramic_v6" if "v6" in s_norm else "classic_v5"
        return None
    if isinstance(profile_or_plan, dict):
        for key in ("style_profile", "profile", "production_profile"):
            sp = str(profile_or_plan.get(key) or "").strip().lower()
            if sp in (PORCELAIN_V7_STYLE_PROFILE, "porcelain_v7"):
                return PORCELAIN_V7_STYLE_PROFILE
            if sp == DIORAMA_V7_STYLE_PROFILE:
                return DIORAMA_V7_STYLE_PROFILE
            if sp in ("dark_ceramic_v6", "diorama_v6", "v6"):
                return "dark_ceramic_v6"
            if sp == "classic_v5":
                return "classic_v5"
        shader_low = str(profile_or_plan.get("shader_style") or "").lower()
        if "low-poly" in shader_low or "low poly" in shader_low:
            return DIORAMA_V7_STYLE_PROFILE
        if "porcelain" in shader_low:
            return PORCELAIN_V7_STYLE_PROFILE
        g_single = str(profile_or_plan.get("grammar") or profile_or_plan.get("visual_grammar") or "").strip().lower()
        if g_single in PORCELAIN_V7_VISUAL_GRAMMARS or g_single.startswith("porcelain_"):
            return PORCELAIN_V7_STYLE_PROFILE
        if g_single in DIORAMA_V7_VISUAL_GRAMMARS or g_single.startswith("lowpoly_"):
            return DIORAMA_V7_STYLE_PROFILE
        if g_single in DIORAMA_VISUAL_GRAMMARS:
            return "dark_ceramic_v6"
        for list_key in ("clips", "cuts"):
            items = profile_or_plan.get(list_key)
            if isinstance(items, list):
                for c in items:
                    if isinstance(c, dict):
                        c_sp = str(c.get("style_profile") or "").strip().lower()
                        if c_sp in (PORCELAIN_V7_STYLE_PROFILE, "porcelain_v7"):
                            return PORCELAIN_V7_STYLE_PROFILE
                        if c_sp == DIORAMA_V7_STYLE_PROFILE:
                            return DIORAMA_V7_STYLE_PROFILE
                        cg = str(c.get("grammar") or c.get("visual_grammar") or "").strip().lower()
                        if cg in PORCELAIN_V7_VISUAL_GRAMMARS or cg.startswith("porcelain_"):
                            return PORCELAIN_V7_STYLE_PROFILE
                        if cg in DIORAMA_V7_VISUAL_GRAMMARS or cg.startswith("lowpoly_"):
                            return DIORAMA_V7_STYLE_PROFILE
                        if cg in DIORAMA_VISUAL_GRAMMARS:
                            return "dark_ceramic_v6"
    return None


def _has_v7_schema_signal(profile_or_plan: Any) -> bool:
    if isinstance(profile_or_plan, str):
        return profile_or_plan.strip().lower() in (
            "neuro_diorama_v7",
            "diorama_v7",
            DIORAMA_V7_STYLE_PROFILE,
            PORCELAIN_V7_STYLE_PROFILE,
            "porcelain_v7",
            "v7",
        )
    if isinstance(profile_or_plan, dict):
        if _parse_schema_version_int(profile_or_plan) >= PROMPT_SCHEMA_VERSION_V7:
            return True
        if str(profile_or_plan.get("style_profile") or "").strip().lower() in (
            *DIORAMA_V7_STYLE_PROFILES,
            "porcelain_v7",
        ):
            return True
        prof = str(profile_or_plan.get("profile") or profile_or_plan.get("production_profile") or "").strip().lower()
        if prof in (
            "neuro_diorama_v7",
            "diorama_v7",
            DIORAMA_V7_STYLE_PROFILE,
            PORCELAIN_V7_STYLE_PROFILE,
            "porcelain_v7",
            "v7",
        ):
            return True
        explicit = extract_explicit_v7_style_profile(profile_or_plan)
        if explicit in DIORAMA_V7_STYLE_PROFILES:
            return True
    return False


def is_porcelain_v7_plan(*plans_or_profiles: Any) -> bool:
    """
    True when candidate profile string(s) or visual_plan/EDL/script/clip dict(s) select Schema v7 `porcelain_cinematic_v7`.
    When multiple candidates are passed (e.g. `is_porcelain_v7_plan(visual_plan, edl, script_doc)`), explicit style
    markers are honored in priority order before falling back to `DEFAULT_DIORAMA_STYLE_PROFILE` on untagged v7 dicts.
    """
    for item in plans_or_profiles:
        explicit = extract_explicit_v7_style_profile(item)
        if explicit is not None:
            return explicit == PORCELAIN_V7_STYLE_PROFILE
    if any(_has_v7_schema_signal(item) for item in plans_or_profiles):
        return DEFAULT_DIORAMA_STYLE_PROFILE == PORCELAIN_V7_STYLE_PROFILE
    return False


def is_diorama_v7_plan(profile_or_plan: Any) -> bool:
    """True when a profile string or visual_plan/script dict selects Schema v7 (`porcelain_cinematic_v7` or `lowpoly_pastel_v7`)."""
    return _has_v7_schema_signal(profile_or_plan)


def resolve_diorama_v7_style_profile(*plans_or_profiles: Any, fallback: str | None = None) -> str:
    """
    Resolves the canonical Schema v7 style profile (`porcelain_cinematic_v7` vs legacy `lowpoly_pastel_v7`).
    Checks explicit style/grammar markers across `plans_or_profiles` in priority order first, then `fallback`,
    and finally `DEFAULT_DIORAMA_STYLE_PROFILE`.
    """
    for item in plans_or_profiles:
        explicit = extract_explicit_v7_style_profile(item)
        if explicit in DIORAMA_V7_STYLE_PROFILES:
            return explicit
    if fallback:
        fb_norm = str(fallback).strip().lower()
        if fb_norm in (PORCELAIN_V7_STYLE_PROFILE, "porcelain_v7"):
            return PORCELAIN_V7_STYLE_PROFILE
        if fb_norm == DIORAMA_V7_STYLE_PROFILE:
            return DIORAMA_V7_STYLE_PROFILE
    return DEFAULT_DIORAMA_STYLE_PROFILE


def is_diorama_profile(profile_or_plan: Any) -> bool:
    """True when a profile string, manifest dict, or visual_plan dict selects Schema v6 or v7 neuro_diorama."""
    if is_diorama_v7_plan(profile_or_plan):
        return True
    if isinstance(profile_or_plan, str):
        return profile_or_plan.strip().lower() in ("neuro_diorama", "diorama_v6", "v6")
    if isinstance(profile_or_plan, dict):
        if _parse_schema_version_int(profile_or_plan) >= PROMPT_SCHEMA_VERSION_V6:
            return True
        prof = str(profile_or_plan.get("profile") or profile_or_plan.get("production_profile") or "").strip().lower()
        return prof in ("neuro_diorama", "diorama_v6", "v6")
    return False


def clip_count_range_for_profile(profile: str | None = None) -> tuple[int, int]:
    """Returns (min_clips, max_clips) for classic_v5 vs neuro_diorama."""
    if is_diorama_profile(profile or ""):
        return (DIORAMA_CLIP_COUNT_MIN, DIORAMA_CLIP_COUNT_MAX)
    return (CLIP_COUNT_MIN, CLIP_COUNT_MAX)


def shorts_duration_range_for_profile(profile: str | None = None) -> tuple[float, float]:
    """Returns (min_duration_sec, max_duration_sec) for classic_v5 vs neuro_diorama."""
    if is_diorama_profile(profile or ""):
        return (DIORAMA_DURATION_MIN_SEC, DIORAMA_DURATION_MAX_SEC)
    return (FINAL_SHORTS_DURATION_MIN_SEC, FINAL_SHORTS_DURATION_MAX_SEC)


def word_count_range_for_profile(profile: str | None = None) -> tuple[int, int]:
    """Returns (min_words, max_words) for classic_v5 vs neuro_diorama."""
    if is_diorama_profile(profile or ""):
        return (DIORAMA_WORD_COUNT_MIN, DIORAMA_WORD_COUNT_MAX)
    return (SCRIPT_WORD_MIN, SCRIPT_WORD_MAX)

# Research depth standard (R44 depth): enforced by validate_dossier
DOSSIER_MIN_SOURCES = 6
DOSSIER_MIN_FOLLOWUP_SOURCES = 2         # replication / follow_up / review
DOSSIER_MIN_CORE_FACTS = 8               # each with a source_id that exists in 01_sources.json
DOSSIER_MIN_MEDIA = 2
DOSSIER_MIN_ANALYZED_MEDIA = 1           # media/<id>/analysis.json with keyframes
DOSSIER_MIN_KEYFRAMES = 8
DOSSIER_MIN_MEDIA_TIMECODES = 2          # per media entry
DOSSIER_MIN_STORY_CHARS = 6000
DOSSIER_MIN_ICONIC_POSITIONS = 2         # who / where / facing entries in the iconic layout
DOSSIER_MIN_ICONIC_PROPS = 2             # each with period_detail + physical_behavior

# Thumbnail renderer palette (pipeline/publish.py)
RGB_SECONDARY_TEAL = (14, 154, 167)
RGB_NEUTRAL_WHITE = (255, 255, 255)
RGB_SIGNAL_GOLD = (255, 215, 0)
RGB_DANGER_RED = (255, 51, 51)
RGB_DEEP_NAVY = (10, 17, 40)

# --- R65 Thumbnail Studio & In-Video Cover Frame (pipeline/thumbnail_studio.py) ---
THUMBNAIL_REPORT_FILENAME = "thumbnail_report.json"
THUMBNAIL_CONTACT_SHEET_FILENAME = "thumbnail_contact_sheet.png"
THUMB_CANDIDATE_SAMPLES_PER_CUT = 3          # Sample offsets at 25 / 50 / 75 % of each eligible EDL cut
THUMB_EXCLUDE_MODES = ("split_hstack", "split_vstack")  # Split-screen cuts never become covers
THUMB_EXCLUDE_OUTRO = True                   # Exclude Act 6 outro sky card from thumbnail candidates
THUMB_SCORE_WEIGHTS = {
    "sharpness": 0.25,
    "contrast": 0.20,
    "colorfulness": 0.10,
    "center_salience": 0.25,
    "intent": 0.20,
}
THUMB_INTENT_BONUS = {
    "cover_sentence": 1.0,
    "act1": 0.6,
    "brain_badge": 0.4,
    "default": 0.0,
}
THUMB_MIN_SHARPNESS = 60.0                   # Laplacian variance floor at 540x960 (TQ3)
THUMB_MIN_LUMA_STD = 38.0                    # Global luminance standard deviation floor (TQ3)
THUMB_MIN_CENTER_SALIENCE = 1.15             # Centre 3:4 Canny edge density / border edge density floor (TQ2)
THUMB_MIN_PAIRWISE_DIFF = 15.0               # Pairwise mean abs pixel diff across A/B/C variants (R31 / TQ5)
THUMB_MIN_TEXT_CONTRAST = 4.5                # WCAG contrast ratio of hook fill vs local/stroke background at 160px shelf width (TQ1)
THUMB_LEGIBILITY_PREVIEW_W = 160             # Mobile Shorts shelf preview width in pixels (TQ1 & contact sheet)
THUMB_SAFE_Y_RANGE = (240, 1440)             # Inside centre 3:4 grid crop & above bottom 25% Shorts UI overlay (TQ4)
THUMB_SAFE_MARGIN_X = 80                     # Minimum left/right horizontal safe margin in pixels (TQ4)
THUMB_HOOK_MAX_WORDS = 4                     # Max words in thumbnail hook headline (TQ7)
THUMB_HOOK_MAX_CHARS = 18                    # Max characters in thumbnail hook headline (TQ7)
THUMB_HOOK_FONT_SIZE_RANGE = (150, 96)       # Auto-fit condensed black headline font size range (max, min)
THUMB_HOOK_STROKE_PX = 10                    # Dark outer stroke thickness on hook headline (replaces v6 navy box)
THUMB_MIN_FILE_BYTES = 80_000                # Minimum PNG byte size per variant (R31 / TQ6)
DIORAMA_V7_REQUIRE_THUMBNAIL_BLOCK = True    # Require `visual_plan.thumbnail` block on new Schema v7 episodes (R65)

# Strict Architectural Policies (Constraint #1 & #2)
ALLOW_EXTERNAL_PAID_APIS = False
ALLOW_STATIC_IMAGE_VIDEO_FALLBACK = False

# Naver Whale & Google Flow Browser Automation Settings
def _resolve_whale_executable() -> Path:
    import sys as _sys

    if _sys.platform == "win32":
        return Path(r"C:\Program Files\Naver\Naver Whale\Application\whale.exe")
    for cand in (
        "/usr/bin/naver-whale-stable",
        "/usr/bin/naver-whale",
        "/opt/naver/whale/naver-whale",
        "/usr/bin/google-chrome-stable",
        "/usr/bin/google-chrome",
        "/usr/bin/chromium-browser",
        "/usr/bin/chromium",
        "/usr/bin/docker",  # Linux host Docker GUI container bridge -> CDP 9222
    ):
        p = Path(cand)
        if p.exists():
            return p
    return Path("/usr/bin/naver-whale-stable")


WHALE_EXECUTABLE = _resolve_whale_executable()
GOOGLE_FLOW_URL = "https://labs.google/fx/tools/flow"
DEFAULT_CDP_HOST = "127.0.0.1"
DEFAULT_CDP_PORT = 9222

# Safety Rails, Circuit Breakers & Timeouts (Phase 4 & Rule R37 Lock)
FLOW_MAX_PARALLEL_BATCH_SIZE = 5         # Strict 1:1:1 Subagent cap: max 5 topics per batch
FLOW_MAX_RETRIES = 2                     # Hard cap: max 2 retries before circuit breaker trips
FLOW_TRIGGER_VERIFY_TIMEOUT_SEC = 5.0    # Must verify UI entered generating state within 5s of click
FLOW_TRIGGER_POLL_INTERVAL_SEC = 0.5     # DOM polling interval during 5s trigger verification
FLOW_RENDER_POLL_INTERVAL_SEC = 10.0     # Poll <video> readyState & download button every 10s
FLOW_RENDER_TIMEOUT_SEC = 210.0          # Asynchronous rendering timeout (180-240s range)
SUBPROCESS_TIMEOUT_SEC = 180.0           # Hard timeout on all ffmpeg/ffprobe subprocess calls
MAX_LOOP_ITERATIONS = 60                 # Hard cap on any polling loop

# Rule R37: Anti-Derivative & Perceptual Fingerprint Locks
BANNED_DERIVATIVE_METADATA_MARKERS = (
    "unique_flow_derivative",
    "unique_batch",
    "_boost",
    "derivative_",
)
MAX_PERCEPTUAL_DHASH_HAMMING_DISTANCE = 10  # Clips across projects with dHash distance <= 10 are flagged as recycled clones

# Local Media Integrity Gate Thresholds (Core Task #4 & #5)
MIN_CLIP_SIZE_BYTES = 1_000_000          # Minimum 1 MB per MP4 clip (blocks thumbnails/empty files)
MIN_FINAL_VIDEO_SIZE_BYTES = 1_000_000   # Minimum 1 MB for final assembled Shorts MP4
FLOW_CLIP_DURATION_MIN_SEC = 3.0         # Minimum valid duration for a Google Flow clip
FLOW_CLIP_DURATION_MAX_SEC = 15.0        # Maximum valid duration for a single Google Flow clip
FINAL_SHORTS_DURATION_MIN_SEC = 24.0     # Minimum valid duration for final Shorts video
FINAL_SHORTS_DURATION_MAX_SEC = 105.0    # Maximum valid duration for final Shorts video (5-10 native Flow clips <= 105s)
MIN_FRAME_DIFF_THRESHOLD = 2.0           # Minimum mean pixel diff across start/mid/end (blocks static images)
MIN_MEAN_FRAME_DIFF = MIN_FRAME_DIFF_THRESHOLD
MIN_PAIR_TOP_DIFF_THRESHOLD = 0.5        # Minimum upper-frame diff between any consecutive pair (blocks freeze-frames)
MIN_INTRA_SEGMENT_DIFF_THRESHOLD = 0.5   # Minimum upper-frame diff across 0.5s window inside each segment (blocks slideshows & frozen clips)
MIN_OPTICAL_FLOW_THRESHOLD = 0.12        # Minimum Farneback optical flow magnitude
MIN_OPTICAL_FLOW_MAG = MIN_OPTICAL_FLOW_THRESHOLD
MIN_CLIPS_FOR_ASSEMBLY = CLIP_COUNT_MIN  # Assembly requires one native Flow clip per narration (5-10)

# Cumulative internal dead-air limit for an assembled Short (scripting G12, video_autopsy, media_integrity Gate 6)
DEAD_AIR_FLOOR_SEC = 16.50               # Lower bound of the limit for videos longer than DEAD_AIR_SHORT_VIDEO_SEC
DEAD_AIR_DURATION_RATIO = 0.38           # Limit scales with duration: max(DEAD_AIR_FLOOR_SEC, duration x 0.38)
DEAD_AIR_SHORT_VIDEO_SEC = 31.0          # Videos at or below this length use DEAD_AIR_SHORT_VIDEO_MAX_SEC
DEAD_AIR_SHORT_VIDEO_MAX_SEC = 0.90


def max_allowed_dead_air_sec(duration_sec: float) -> float:
    """Cumulative internal dead-air limit (seconds) for an assembled Short of the given duration."""
    if duration_sec > DEAD_AIR_SHORT_VIDEO_SEC:
        return max(DEAD_AIR_FLOOR_SEC, round(duration_sec * DEAD_AIR_DURATION_RATIO, 2))
    return DEAD_AIR_SHORT_VIDEO_MAX_SEC


def expected_final_duration_sec(n_clips: int) -> float:
    """Nominal assembled length of an n-clip Short (n x FLOW_CLIP_TARGET_SEC_MIN at AV_SPEEDUP_FACTOR), clamped to the final-Shorts bounds."""
    nominal = n_clips * FLOW_CLIP_TARGET_SEC_MIN / AV_SPEEDUP_FACTOR
    return round(min(FINAL_SHORTS_DURATION_MAX_SEC, max(FINAL_SHORTS_DURATION_MIN_SEC, nominal)), 2)


# Audio Harshness / Sibilance Tear & Integrated Loudness (BS.1770 ebur128) QA Constants
AUDIO_SIBILANCE_BAND_HZ: tuple[float, float] = (4200.0, 9200.0)
AUDIO_SPEECH_BODY_BAND_HZ: tuple[float, float] = (180.0, 3600.0)
AUDIO_MAX_SIBILANCE_ENERGY_RATIO = 0.62          # Max HF (4.2-9.2kHz) / mid-band RMS ratio on voiced windows before flagging harshness tear
AUDIO_MAX_SIBILANCE_CREST_DB = 32.0              # Max HF peak-to-RMS crest (dB) over active 50ms voiced windows
DIORAMA_V7_TARGET_LUFS = -15.5                   # Unified BS.1770 documentary loudness target (matches DIORAMA_TARGET_LUFS)
DIORAMA_LUFS_TOLERANCE_LU = 4.0                  # Accepted BS.1770 integrated LUFS window around target (-19.5..-11.5 LUFS)
AUDIO_MAX_OVERSAMPLED_TRUE_PEAK_DBTP = -0.5      # Max 4x oversampled True Peak (dBTP) via FFmpeg ebur128
AUDIO_MIN_TTS_ASR_WORD_COVERAGE = 0.85           # Minimum script/subtitle word-coverage ratio on assembled TTS narration

# Typography: single-line 2-3 word gold-keyword subtitles
FONT_PRIMARY_PATH = FONTS_DIR / "Inter-Variable.ttf"
FONT_FALLBACK_PATH = (
    Path(r"C:\Windows\Fonts\arialbd.ttf")
    if Path(r"C:\Windows\Fonts\arialbd.ttf").exists()
    else (
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
        if Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf").exists()
        else FONT_CONDENSED_BLACK_PATH
    )
)
FONT_MONO_PATH = (
    Path(r"C:\Windows\Fonts\consola.ttf")
    if Path(r"C:\Windows\Fonts\consola.ttf").exists()
    else Path("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf")
)

SUBTITLE_FONT_NAME = "Arial Black"
SUBTITLE_FONT_SIZE = 86
SUBTITLE_OUTLINE_WIDTH = 7.0
SUBTITLE_SHADOW_DEPTH = 0.0
SUBTITLE_MARGIN_V = 440                  # Y=74% lower-third anchor (1920 - 440 = 1480px) leaving 3D center (Y=35-65%) unobstructed
SUBTITLE_MAX_WORDS_PER_EVENT = 3         # Single-line 2-3 word burst per event
SUBTITLE_MAX_LINES = 1                   # Strict 1-line subtitle rule (zero \N line breaks in Default style)

# Script word budget across all clip counts (== script_word_range(CLIP_COUNT_MIN)[0] .. script_word_range(CLIP_COUNT_MAX)[1])
SCRIPT_WORD_MIN = 90
SCRIPT_WORD_MAX = 280
MAX_WORDS_PER_SENTENCE = 26

# Historical Storytelling Narrative Router (R2-B & R42 Deep-Mechanism Role Spine)
ALLOWED_NARRATIVE_STYLES = [
    "auto",
    "case_file",
    "delusion_museum",
    "forbidden_lab",
    "icon_autopsy",
    "caveman_brain",
    "chronicle_cutaway",
]

PILLAR_DEFAULT_STYLE_MAP: dict[str, str] = {
    "brain_mysteries": "case_file",
    "brain_history": "delusion_museum",
    "bci_ethics": "forbidden_lab",
    "brain_basics": "icon_autopsy",
    "brain_health": "caveman_brain",
    "bci_tech": "chronicle_cutaway",
    "brain_news": "chronicle_cutaway",
}

NARRATIVE_STYLE_SPECS: dict[str, dict[str, Any]] = {
    "case_file": {
        "id": "case_file",
        "name_ko": "Clinical Mystery Case File",
        "name_en": "Clinical Mystery Case File",
        "default_pillars": ["brain_mysteries"],
        "hook_pattern": "In [Year], Patient [X] walked into a clinic with an impossible neurological anomaly.",
        "spine": CLIP_ROLE_SEQUENCES[DEFAULT_CLIP_COUNT],
    },
    "delusion_museum": {
        "id": "delusion_museum",
        "name_ko": "Museum of Human Delusions",
        "name_en": "Museum of Human Delusions",
        "default_pillars": ["brain_history"],
        "hook_pattern": "For centuries, ancient physicians performed a bizarre surgical ritual that defies all biological logic.",
        "spine": CLIP_ROLE_SEQUENCES[DEFAULT_CLIP_COUNT],
    },
    "forbidden_lab": {
        "id": "forbidden_lab",
        "name_ko": "Declassified Forbidden Lab",
        "name_en": "Declassified Forbidden Lab",
        "default_pillars": ["bci_ethics"],
        "hook_pattern": "In [Year], a classified psychological experiment pushed human subjects past the brink of sanity.",
        "spine": CLIP_ROLE_SEQUENCES[DEFAULT_CLIP_COUNT],
    },
    "icon_autopsy": {
        "id": "icon_autopsy",
        "name_ko": "Genius & Anomaly Brain Autopsy",
        "name_en": "Genius & Madman Brain Autopsy",
        "default_pillars": ["brain_basics"],
        "hook_pattern": "When pathologists dissected an iconic genius's brain, they uncovered a structural anomaly.",
        "spine": CLIP_ROLE_SEQUENCES[DEFAULT_CLIP_COUNT],
    },
    "caveman_brain": {
        "id": "caveman_brain",
        "name_ko": "Caveman Brain Evolutionary Time-Capsule",
        "name_en": "Caveman Brain Evolutionary Time-Capsule",
        "default_pillars": ["brain_health"],
        "hook_pattern": "Fifty thousand years ago on the African savanna, this neural reflex saved human ancestors from predators.",
        "spine": CLIP_ROLE_SEQUENCES[DEFAULT_CLIP_COUNT],
    },
    "chronicle_cutaway": {
        "id": "chronicle_cutaway",
        "name_ko": "Time-Slip Chronicle x 3D Neuroanatomy",
        "name_en": "Time-Slip Chronicle x 3D Cutaway",
        "default_pillars": ["bci_tech", "brain_news"],
        "hook_pattern": "Time freezes at the exact millisecond a neural interface bridges living cortex and silicon.",
        "spine": CLIP_ROLE_SEQUENCES[DEFAULT_CLIP_COUNT],
    },
}


def resolve_narrative_style(
    style: str | None = "auto",
    pillar_id: str | None = None,
    topic: str | None = None,
) -> str:
    """
    Resolves the active narrative style from the 6 Historical Storytelling Archetypes.
    If style is 'auto' or None, routes dynamically by topic keywords first, then pillar_id.
    """
    if style and style.strip().lower() in NARRATIVE_STYLE_SPECS:
        return style.strip().lower()

    topic_lower = (topic or "").lower()
    if any(k in topic_lower for k in ["patient", "delusion", "capgras", "split", "phantom", "blindness", "agnosia"]):
        return "case_file"
    if any(k in topic_lower for k in ["ancient", "egypt", "trepanation", "medieval", "humor", "lobotomy", "phrenology"]):
        return "delusion_museum"
    if any(k in topic_lower for k in ["experiment", "classified", "milgram", "stanford", "loftus", "dissonance", "mkultra"]):
        return "forbidden_lab"
    if any(k in topic_lower for k in ["einstein", "van gogh", "gage", "genius", "autopsy", "artist", "composer"]):
        return "icon_autopsy"
    if any(k in topic_lower for k in ["caveman", "savanna", "evolution", "habit", "sleep", "glymphatic", "dopamine", "stress"]):
        return "caveman_brain"
    if any(k in topic_lower for k in ["bci", "neuralink", "electrode", "implant", "prosthesis", "decoding"]):
        return "chronicle_cutaway"

    clean_pillar = (pillar_id or "").strip().lower()
    if clean_pillar in PILLAR_DEFAULT_STYLE_MAP:
        return PILLAR_DEFAULT_STYLE_MAP[clean_pillar]
    for k, v in PILLAR_DEFAULT_STYLE_MAP.items():
        if k in clean_pillar or clean_pillar in k:
            return v
    return "chronicle_cutaway"
