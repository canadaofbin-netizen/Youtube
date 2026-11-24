"""ALL ABOUT BRAIN — Workspace, Storage & RAM Scratch Path Constants (`config_paths.py`)."""

from __future__ import annotations
import os
import sys as _sys_cfg
import tempfile
from pathlib import Path
from typing import Any

WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
CHANNEL_ROOT = WORKSPACE_ROOT / "BCI_Shorts_Channel"
PROJECTS_DIR = CHANNEL_ROOT / "projects"
DOSSIERS_DIR = CHANNEL_ROOT / "research_dossiers"
PROJECTS_QUARANTINE_DIR = CHANNEL_ROOT / "projects_quarantine_pending_flow"
FLOW_DOWNLOAD_HARVEST_LOCK_FILE = (
    Path(os.environ.get("AAB_LOCKS_DIR", "").strip() or (Path(tempfile.gettempdir()) / "aab_locks"))
    / "flow_download_harvest.lock"
)
ASSETS_DIR = CHANNEL_ROOT / "assets"
FONTS_DIR = ASSETS_DIR / "fonts"
FLOW_VIDEO_MODEL_PROFILES: dict[str, dict] = {
    "Omni 1.2 Flash": {
        "durations": ("4s", "6s", "8s", "10s"),
        "extended_durations_v83": tuple(f"{s}s" for s in range(3, 16)),
        "max_sec": 10,
        "max_sec_with_ingredient": 8,
        "max_ingredients_v83": 8,
        "supports_start_end_frames": True,
        "first_and_last_max_sec": 10,
        "api_model_id": "gemini-omni-1.2-flash",
        "supports_native_1080p_upscale": True,
        "supports_conversational_edit": True,
        "model_family_id": "macaron_cookie",
        "zero_credit": False,
    },
    "Veo 3.1 - Lite [Lower Priority]": {
        "durations": ("4s", "6s", "8s"),
        "max_sec": 8,
        "max_sec_with_ingredient": 8,
        "supports_start_end_frames": True,
        "first_and_last_max_sec": 8,
        "model_family_id": "veo_3_1_lite_low_priority",
        "zero_credit": True,
    },
}
FLOW_UI_CAPABILITIES_CACHE_FILE = CHANNEL_ROOT / ".cache" / "flow_ui_capabilities.json"
PERSISTENT_SHA_CACHE_MAX_ENTRIES = 8192                   # Compact LRU cap for BCI_Shorts_Channel/.cache/persistent_sha256_cache.json
RESEARCH_DOSSIERS_DIRNAME = "research_dossiers"
ASSET_LIBRARY_DIRNAME = "asset_library"
REF_IMAGES_DIRNAME = "reference_images"
CANONICAL_PROVENANCE_FILENAME = "canonical_assets_provenance.json"
DEFAULT_DIORAMA_CAMERA_PROFILE = "dynamic_3d_cinema_rig"
DIORAMA_V7_STYLE_PROFILE = "lowpoly_pastel_v7"
PORCELAIN_V7_STYLE_PROFILE = "porcelain_cinematic_v7"
EXPRESSIVE_25D_V8_STYLE_PROFILE = "expressive_25d_v8"
ALL_DIORAMA_STYLE_PROFILES: tuple[str, ...] = (
    DIORAMA_V7_STYLE_PROFILE,
    PORCELAIN_V7_STYLE_PROFILE,
    EXPRESSIVE_25D_V8_STYLE_PROFILE,
)
DEFAULT_DIORAMA_STYLE_PROFILE = PORCELAIN_V7_STYLE_PROFILE
EXPRESSIVE_V8_REFS_DIRNAME = "expressive_25d_v8_refs"
TRANSLUCENT_BRAIN_V8_REFS_DIRNAME = "translucent_brain_v8_refs"
TRANSLUCENT_BRAIN_V8_CANDIDATE_FILENAMES: tuple[str, ...] = (
    "cand_01_3q_subcortical_limbic_xray_9x16.png",
    "cand_02_side_profile_pfc_accumbens_xray_9x16.png",
    "cand_03_anterior_3q_dual_hub_xray_9x16.png",
    "cand_04_neutral_master_translucent_glass_9x16.png",
    "cand_05_elevated_3q_frontal_cyan_brainstem_red_9x16.png",
    "cand_06_ghost_xray_contour_translucent_brain_9x16.png",
)
EXPRESSIVE_ACTING_LEXICON_PATH = ASSETS_DIR / "expression_acting_lexicon.json"
EXPRESSIVE_V8_SPECIES_SHEET_FILENAME = "species_opt1_sheet.png"
EXPRESSIVE_V8_CAMEO_SHEET_FILENAME = "cameo_opt3_sheet.png"
EXPRESSIVE_V8_CAST_SHEET_FILENAMES: tuple[str, ...] = (
    "cast_sheet_01_core_6roles.png",
    "cast_sheet_02_clinical_historical_6roles.png",
    "cast_sheet_03_everyday_lifestyle_6roles.png",
)
EXPRESSIVE_V8_BANNED_EMPATHY_FILLERS: tuple[str, ...] = (
    "you're not alone",
    "you are not alone",
    "almost everyone has",
    "we've all been there",
    "we have all been there",
)
EXPRESSIVE_V8_OPENING_EMPATHY_MAX_WORDS = 12
BGM_BANK_DIR = CHANNEL_ROOT / "knowledge_base" / "reusable_packs" / "bgm_bank"
ELEVENLABS_ENV_FILE = Path.home() / ".config" / "aab" / "elevenlabs.env"
ELEVENLABS_CREDIT_STATE_FILE = CHANNEL_ROOT / ".cache" / "elevenlabs_credit_state.json"
CAST_REGISTRY_PATH = CHANNEL_ROOT / "knowledge_base" / "reusable_packs" / "cast_registry.json"
LOCATION_REGISTRY_PATH = CHANNEL_ROOT / "knowledge_base" / "reusable_packs" / "location_registry.json"
REENACT_QUARANTINE_ROOT = Path("/tmp/aab_reenact")
REENACT_EDL_FILENAME = "source_edl.json"
REENACT_QA_REPORT_FILENAME = "reenactment_qa_report.json"
REENACT_COMPARISON_SHEET_FILENAME = "reenactment_comparison_sheet.png"
YUNET_FACE_MODEL_PATH = WORKSPACE_ROOT / "pipeline" / "assets" / "models" / "face_detection_yunet_2023mar.onnx"
MICRO_SHORT_PROFILE = "micro_short_v7"
SHORTS_90S_PROFILE = "shorts_90s_v7"
SHORTS_EXPRESSIVE_V8_PROFILE = "shorts_expressive_v8"
SHORTS_180S_PROFILE = "shorts_180s_v7"
DEFAULT_SHORTS_FORMAT_PROFILE = SHORTS_90S_PROFILE
REAL_WORLD_REFS_QUARANTINE_ROOT = Path("/tmp/aab_real_refs")
REAL_WORLD_REFS_MANIFEST_FILENAME = "real_world_refs_manifest.json"
R88_FACELESS_CAST_PROFILE = "r88_faceless_porcelain"
R85_GENUINE_EP31_ANCHOR_FILES: tuple[str, ...] = (
    "ep31_orig_mode1_head_9x16.png",
    "ep31_orig_mode2_lateral_9x16.png",
    "ep31_orig_mode2_dorsal_9x16.png",
    "ep31_orig_mode2_vessel_macro_9x16.png",
)
LONGFORM_PRODUCTION_PROFILE = "longform_porcelain_16x9_v1"
LONGFORM_PROJECTS_DIRNAME = "projects_longform"
LONGFORM_PROJECTS_DIR = CHANNEL_ROOT / LONGFORM_PROJECTS_DIRNAME
NEURO_NEWS_STAGING_DIR = WORKSPACE_ROOT / "Completed_Neuro_News_Shorts"
FONT_CONDENSED_BLACK_PATH = FONTS_DIR / "AABCondensed-Black.ttf"
POSTHOC_SEMANTIC_QA_REPORT_FILENAME = "posthoc_semantic_qa_report.json"
POSTHOC_SEMANTIC_REVIEW_FILENAME = "posthoc_semantic_review.json"
POSTHOC_VIEWER_STRIPS_DIRNAME = "posthoc_viewer_strips"
KNOWLEDGE_BASE_DIRNAME = "knowledge_base"
KNOWLEDGE_BASE_DIR = CHANNEL_ROOT / KNOWLEDGE_BASE_DIRNAME
KNOWLEDGE_TELEMETRY_DIRNAME = "telemetry"
EPISODES_INDEX_FILENAME = "episodes_index.jsonl"
CLIP_CLARITY_LEDGER_FILENAME = "clip_clarity_ledger.jsonl"
QA_ANALYTICS_SUMMARY_FILENAME = "qa_analytics_summary.json"
REUSABLE_PACKS_DIRNAME = "reusable_packs"
EXPERIMENTS_ARCHIVE_DIRNAME = "experiments"
R65_V4_THUMBNAIL_PROFILE = "in_skull_cutaway_split_v4"
R65_V4_DARK_PARADOX_PROFILE = "dark_void_paradox_v4"
DEFAULT_SHORTS_THUMBNAIL_PROFILE = R65_V4_THUMBNAIL_PROFILE
THUMBNAIL_REPORT_FILENAME = "thumbnail_report.json"
THUMBNAIL_QA_REPORT_FILENAME = "thumbnail_qa_report.json"
THUMBNAIL_SELECTED_FILENAME = "thumbnail_selected.png"
THUMBNAIL_CONTACT_SHEET_FILENAME = "thumbnail_contact_sheet.png"
THUMB_MIN_FILE_BYTES = 80_000                # Minimum PNG byte size per variant (R31 / TQ6)
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
DEFAULT_CDP_PORT = 9222
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
AAB_MAX_STANDALONE_CPU_BUDGET = 8
AAB_OVERLAPPED_FLOW_RESERVED_CORES = 2          # 8 - 2 = 6 vCPUs for overlapped Blender/Assembly/QA while Chrome Flow runs
AAB_SHM_MOUNT_ROOT = Path("/dev/shm")
AAB_SHM_SCRATCH_DEFAULT_DIR = Path("/dev/shm/aab_scratch")
AAB_SHM_MIN_FREE_BYTES = 4 * (1024**3)          # >= 4 GiB free on /dev/shm auto-enables RAM-disk scratch
AAB_SHM_MAX_TOTAL_BYTES = 22 * (1024**3)        # Hard 22 GiB LRU cap on 64 GiB host (leaves >= 40 GiB physical RAM free)
AAB_SPEED_CACHE_STAGED_MAX_BYTES = 8_000_000_000
AAB_SPEED_CACHE_SEGMENTS_MAX_BYTES = 6_000_000_000
AAB_SPEED_CACHE_TTS_NPZ_MAX_BYTES = 2_500_000_000
AAB_SPEED_CACHE_POSTHOC_CV_MAX_BYTES = 2_000_000_000
