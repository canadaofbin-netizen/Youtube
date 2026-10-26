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
CLIP_VISUAL_HOLD_SEC = 0.15              # Post-speech hold on clips 1..N-1
CLIP_PRE_PIVOT_HOLD_SEC = 0.30           # Post-speech hold on the clip right before the pivot clip
CLIP_PRE_ROLL_TRIM_SEC = 0.40            # Minimum pre-roll trim on clips 2..N when speech starts later than this
AV_SPEEDUP_FACTOR = 1.08                 # Synchronized video (setpts) + vocal (atempo) speedup

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
    "Omni 1.1 Flash": {"durations": ("4s", "6s", "8s", "10s"), "max_sec": 10, "max_sec_with_ingredient": 8},
    "Veo 3.1 - Lite [Lower Priority]": {"durations": ("4s", "6s", "8s"), "max_sec": 8, "max_sec_with_ingredient": 8},
}
FLOW_ACTIVE_VIDEO_MODEL = "Omni 1.1 Flash"
FLOW_BANNED_VIDEO_MODEL_MARKERS: tuple[str, ...] = ("Veo",)
FLOW_ZERO_CREDIT_TEXT = "Generating will use 0 credits"   # informational; Omni always costs Flow plan credits
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
ALLOWED_FLOW_MODELS = ["Omni 1.1 Flash", "Omni 1.1 Quality"]
FLOW_MODELS = {
    "Omni 1.1 Flash": "Omni 1.1 Flash - High-throughput, multimodal video engine (Default)",
    "Omni 1.1 Quality": "Omni 1.1 Quality - Maximum cinematic photorealism & cutaway detail",
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
VOICE_FALLBACK_SPEED = 1.12              # ~EFFECTIVE_WPS without A/V speed-up on the voice
VOICE_FALLBACK_MODEL_DIR = Path.home() / ".cache" / "aab_tts"
VOICE_FALLBACK_VIDEO_SPEED_RANGE: tuple[float, float] = (0.85, 1.25)  # video setpts factor range to fit TTS length

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

# Strict Architectural Policies (Constraint #1 & #2)
ALLOW_EXTERNAL_PAID_APIS = False
ALLOW_STATIC_IMAGE_VIDEO_FALLBACK = False

# Naver Whale & Google Flow Browser Automation Settings
WHALE_EXECUTABLE = Path(r"C:\Program Files\Naver\Naver Whale\Application\whale.exe")
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


# Typography: single-line 2-3 word gold-keyword subtitles
FONT_PRIMARY_PATH = FONTS_DIR / "Inter-Variable.ttf"
FONT_FALLBACK_PATH = Path(r"C:\Windows\Fonts\arialbd.ttf")
FONT_MONO_PATH = Path(r"C:\Windows\Fonts\consola.ttf")

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
