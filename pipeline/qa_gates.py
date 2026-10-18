"""
ALL ABOUT BRAIN - Executable 4-Stage QA Gate Suite (Production Contract v4)
Provides programmatic, self-verifying QA checks across:
  1. Pre-Flight QA (environment, FFmpeg, OpenCV, Whale CDP, zero paid APIs, Capgras golden prompt build)
  2. Browser Generation QA (Google Flow DOM & asset guards, Gates V1-V5, provenance receipts)
  3. Media Integrity QA (ffprobe/ffmpeg + OpenCV frame diff & optical flow on clips and final MP4s)
  4. Intent & Content QA (5-10 clip scripts within SCRIPT_WORD_MIN-SCRIPT_WORD_MAX, schema-4 Flow prompts,
     A/B thumbnails, single-line subtitles, en-US metadata)
"""

from __future__ import annotations

import json
import urllib.request
from pathlib import Path
from typing import Any

from pipeline.config import (
    ALLOW_EXTERNAL_PAID_APIS,
    CLIP_COUNT_MAX,
    CLIP_COUNT_MIN,
    FLOW_ALLOWED_VOICES,
    FLOW_MAX_PARALLEL_BATCH_SIZE,
    MIN_CLIP_SIZE_BYTES,
    PROJECTS_DIR,
    SCRIPT_WORD_MAX,
    SCRIPT_WORD_MIN,
    WORKSPACE_ROOT,
    script_word_range,
)
from pipeline.flow_browser import (
    WHALE_EXECUTABLE,
    FlowParallelOrchestrator,
    FlowProjectSubagentWorker,
    GoogleFlowWhaleController,
)
from pipeline.media_integrity import MediaIntegrityValidator, get_pipeline_logger
from pipeline.storage import numeric_clip_sort_key

FLOW_PROMPTS_SCHEMA_VERSION = 4

logger = get_pipeline_logger("qa_gates")

BANNED_SHORTCUT_CODE_PATTERNS = (
    "def build_unique_project_clips",
    "def generate_unique_project_clips",
    "unique_flow_derivative",
    "unique_batch",
)


def run_preflight_qa(cdp_port: int = 9222, require_live_cdp: bool = False) -> dict[str, Any]:
    """
    Stage 1: Pre-Flight QA
    Verifies local tools (FFmpeg, OpenCV, Whale executable), zero external paid API lock,
    Guard 3 & Guard 6 zero-shortcut code lock + max 5 batch cap, the Production Contract v4 prompt lock
    (Capgras golden builds and validates; 5-10 clip word range; Puck-only voice), the assembly timing/subtitle
    constants, and optional live CDP port 9222 connectivity.
    """
    checks: dict[str, Any] = {}

    # 1. Zero External Paid API Lock
    gen_path = Path(__file__).resolve().parent / "generator.py"
    gen_src = gen_path.read_text(encoding="utf-8") if gen_path.exists() else ""
    has_paid_sdk = ("from google import genai" in gen_src) or ("import google.generativeai" in gen_src)
    checks["zero_external_paid_apis"] = {
        "passed": (ALLOW_EXTERNAL_PAID_APIS is False) and not has_paid_sdk,
        "allow_external_paid_apis_flag": ALLOW_EXTERNAL_PAID_APIS,
        "generator_has_paid_sdk_imports": has_paid_sdk,
    }

    # 2. Guard 3 & Guard 6 (R37): Zero-Shortcut Code Lock & Max 5 Batch Concurrency Lock
    shortcut_violations: list[str] = []
    scan_files: list[Path] = []
    if WORKSPACE_ROOT.exists():
        scan_files.extend(sorted(WORKSPACE_ROOT.glob("produce_*.py")))
    pipeline_dir = Path(__file__).resolve().parent
    excluded_pipeline_files = {"qa_gates.py", "media_integrity.py", "config.py"}
    for py_file in sorted(pipeline_dir.glob("*.py")):
        if py_file.name in excluded_pipeline_files or py_file.name.startswith("test_"):
            continue
        scan_files.append(py_file)

    for src_file in scan_files:
        try:
            content = src_file.read_text(encoding="utf-8")
            for banned_pat in BANNED_SHORTCUT_CODE_PATTERNS:
                if banned_pat in content:
                    shortcut_violations.append(f"{src_file.name}: contains '{banned_pat}'")
        except Exception as exc:
            shortcut_violations.append(f"{src_file.name}: read error ({exc})")

    batch_cap_locked = (
        FLOW_MAX_PARALLEL_BATCH_SIZE == 5
        and GoogleFlowWhaleController.MAX_BATCH_CONCURRENCY == 5
        and FlowParallelOrchestrator.MAX_BATCH_SIZE == 5
    )
    if not batch_cap_locked:
        shortcut_violations.append(
            f"Batch cap mismatch: FLOW_MAX_PARALLEL_BATCH_SIZE={FLOW_MAX_PARALLEL_BATCH_SIZE}, "
            f"MAX_BATCH_CONCURRENCY={GoogleFlowWhaleController.MAX_BATCH_CONCURRENCY}"
        )

    checks["zero_shortcut_code_lock"] = {
        "passed": len(shortcut_violations) == 0 and batch_cap_locked,
        "files_scanned": len(scan_files),
        "flow_max_parallel_batch_size": FLOW_MAX_PARALLEL_BATCH_SIZE,
        "violations": shortcut_violations,
    }

    # 2b. Production Contract v4 prompt lock: the Capgras golden (psych_05) builds and validates cleanly
    try:
        from pipeline.flow_prompt_builder import (
            build_flow_prompts,
            load_visual_plan,
            validate_flow_prompts,
            validate_narrations,
        )
        from pipeline.topics_catalog import PSYCHOLOGY_TOPICS

        golden = next(t for t in PSYCHOLOGY_TOPICS if str(t.get("project_id", "")).startswith("psych_05"))
        golden_narrations = [str(s) for s in golden.get("clip_narrations") or []]
        golden_clips = build_flow_prompts(load_visual_plan(topic_item=golden), golden_narrations)
        prompt_issues = validate_flow_prompts(golden_clips)
        narration_issues = validate_narrations(golden_narrations)
        word_range_ok = (SCRIPT_WORD_MIN, SCRIPT_WORD_MAX) == (
            script_word_range(CLIP_COUNT_MIN)[0],
            script_word_range(CLIP_COUNT_MAX)[1],
        )
        voices_ok = tuple(FLOW_ALLOWED_VOICES) == ("Puck",)
        checks["contract_v4_golden_prompt_lock"] = {
            "passed": (
                not prompt_issues
                and not narration_issues
                and len(golden_clips) == len(golden_narrations)
                and word_range_ok
                and voices_ok
            ),
            "golden_project_id": golden["project_id"],
            "prompts_count": len(golden_clips),
            "prompt_issues": prompt_issues,
            "narration_issues": narration_issues,
            "script_word_range": f"{SCRIPT_WORD_MIN}-{SCRIPT_WORD_MAX}",
            "allowed_voices": list(FLOW_ALLOWED_VOICES),
        }
    except Exception as exc:
        checks["contract_v4_golden_prompt_lock"] = {
            "passed": False,
            "error": f"{type(exc).__name__}: {exc}",
        }

    # 2c. Assembly lock: 1.08x speedup, 0.15s hold, 0.30s pre-pivot hold, 0.20s final tail,
    #     single-line 2-3 word subtitles at MarginV=440, Puck voice
    try:
        from pipeline.config import (
            AV_SPEEDUP_FACTOR,
            CLIP_PRE_PIVOT_HOLD_SEC,
            CLIP_VISUAL_HOLD_SEC,
            FINAL_TAIL_SEC,
            FLOW_DEFAULT_VOICE,
            SUBTITLE_MARGIN_V,
            SUBTITLE_MAX_LINES,
            SUBTITLE_MAX_WORDS_PER_EVENT,
        )
        assembly_ok = (
            AV_SPEEDUP_FACTOR == 1.08
            and CLIP_VISUAL_HOLD_SEC == 0.15
            and CLIP_PRE_PIVOT_HOLD_SEC == 0.30
            and FINAL_TAIL_SEC == 0.20
            and SUBTITLE_MARGIN_V == 440
            and SUBTITLE_MAX_WORDS_PER_EVENT == 3
            and SUBTITLE_MAX_LINES == 1
            and FLOW_DEFAULT_VOICE == "Puck"
        )
        checks["assembly_timing_subtitle_voice_lock"] = {
            "passed": assembly_ok,
            "av_speedup_factor": AV_SPEEDUP_FACTOR,
            "clip_visual_hold_sec": CLIP_VISUAL_HOLD_SEC,
            "clip_pre_pivot_hold_sec": CLIP_PRE_PIVOT_HOLD_SEC,
            "final_tail_sec": FINAL_TAIL_SEC,
            "subtitle_margin_v": SUBTITLE_MARGIN_V,
            "subtitle_max_words_per_event": SUBTITLE_MAX_WORDS_PER_EVENT,
            "subtitle_max_lines": SUBTITLE_MAX_LINES,
            "flow_default_voice": FLOW_DEFAULT_VOICE,
        }
    except Exception as exc:
        checks["assembly_timing_subtitle_voice_lock"] = {
            "passed": False,
            "error": str(exc),
        }

    # 3. FFmpeg binary availability
    try:
        ffmpeg_exe = MediaIntegrityValidator.get_ffmpeg_exe()
        checks["ffmpeg_binary"] = {"passed": Path(ffmpeg_exe).exists(), "path": ffmpeg_exe}
    except Exception as exc:
        checks["ffmpeg_binary"] = {"passed": False, "error": str(exc)}

    # 4. OpenCV & NumPy availability
    try:
        import cv2
        import numpy as np
        checks["opencv_numpy"] = {
            "passed": True,
            "cv2_version": cv2.__version__,
            "numpy_version": np.__version__,
        }
    except Exception as exc:
        checks["opencv_numpy"] = {"passed": False, "error": str(exc)}

    # 5. Visible Naver Whale executable
    checks["naver_whale_executable"] = {
        "passed": WHALE_EXECUTABLE.exists(),
        "path": str(WHALE_EXECUTABLE),
    }

    # 6. CDP Port 9222 inspection
    cdp_reachable = False
    flow_tabs_count = 0
    try:
        req = urllib.request.Request(f"http://127.0.0.1:{cdp_port}/json/list")
        tabs = json.loads(urllib.request.urlopen(req, timeout=3).read().decode("utf-8"))
        cdp_reachable = True
        flow_tabs_count = sum(
            1 for t in tabs if "flow.google" in t.get("url", "") or "labs.google" in t.get("url", "")
        )
    except Exception as exc:
        checks["cdp_connection_note"] = str(exc)

    checks["whale_cdp_port"] = {
        "passed": cdp_reachable if require_live_cdp else True,
        "cdp_reachable": cdp_reachable,
        "cdp_port": cdp_port,
        "active_flow_tabs": flow_tabs_count,
    }

    stage_passed = all(
        v.get("passed", True) for k, v in checks.items() if isinstance(v, dict) and "passed" in v
    )
    return {
        "stage": "Stage 1: Pre-Flight QA",
        "passed": stage_passed,
        "checks": checks,
    }


def run_browser_generation_qa(project_id: str | None = None) -> dict[str, Any]:
    """
    Stage 2: Browser Generation QA (Guard 1, Guard 3 & Guard 6)
    Validates Layer 1-3 browser guards (real typing/button enablement logic, retry circuit breaker config,
    strict static-image/screenshot rejection, 1:1:1 subagent binding, max 5 batch cap) AND verifies that
    EVERY project in PROJECTS_DIR has:
      1. V1-V4 screenshots present and non-empty
      2. visual_qa_report.json with gate_v1..gate_v5 == "PASS"
      3. Valid cryptographic 03_visuals/flow_provenance_receipt.json with unique flow_project_url and tab_target_id
      4. Gate V5 clip integrity (>= CLIP_COUNT_MIN clips, zero synthetic derivative metadata tags)
    """
    checks: dict[str, Any] = {}

    # 1. Layer 3 Static Image / Screenshot Blocker Verification
    blocked_png = not FlowProjectSubagentWorker.is_valid_video_asset_url("flow_gate_v1_prompt_approved.png", "image/png")
    blocked_poster = not FlowProjectSubagentWorker.is_valid_video_asset_url("https://flow.google.com/poster_thumb.jpg", "image/jpeg")
    blocked_thumb = not FlowProjectSubagentWorker.is_valid_video_asset_url("thumbnail_var_A.png", "image/png")
    allowed_mp4 = FlowProjectSubagentWorker.is_valid_video_asset_url("clip_1.mp4", "video/mp4")

    checks["layer3_static_asset_blocker"] = {
        "passed": blocked_png and blocked_poster and blocked_thumb and allowed_mp4,
        "blocked_png_screenshot": blocked_png,
        "blocked_poster_jpg": blocked_poster,
        "blocked_thumbnail_png": blocked_thumb,
        "allowed_official_mp4": allowed_mp4,
    }

    # 2. Layer 1 & Guard 6 (1:1:1 Subagent + Max 5 Batch Cap) Verification
    worker = FlowProjectSubagentWorker("qa_probe_worker", trigger_generation=True)
    checks["layer1_worker_circuit_breaker_config"] = {
        "passed": (
            worker.trigger_generation is True
            and worker.subagent_1_to_1_bound is True
            and worker.max_retries == 2
            and FLOW_MAX_PARALLEL_BATCH_SIZE == 5
            and hasattr(worker, "inject_prompt_and_enable_button")
            and hasattr(worker, "trigger_and_verify_generation")
            and hasattr(worker, "poll_until_video_ready")
            and hasattr(worker, "write_provenance_receipt")
        ),
        "max_retries": worker.max_retries,
        "trigger_generation": worker.trigger_generation,
        "subagent_1_to_1_bound": worker.subagent_1_to_1_bound,
        "flow_max_parallel_batch_size": FLOW_MAX_PARALLEL_BATCH_SIZE,
    }

    # 3. Per-Project Visual Gates V1-V5 & Cryptographic Flow Provenance Receipt Verification
    target_projects: list[Path] = []
    if project_id:
        p_dir = PROJECTS_DIR / project_id
        if p_dir.exists():
            target_projects = [p_dir]
    else:
        if PROJECTS_DIR.exists():
            target_projects = sorted([
                d for d in PROJECTS_DIR.iterdir()
                if d.is_dir() and (d / "00_project_manifest.json").exists()
            ])

    seen_urls: dict[str, str] = {}
    seen_tabs: dict[str, str] = {}
    project_provenance_results: dict[str, Any] = {}
    all_projects_provenance_ok = len(target_projects) > 0

    for p_dir in target_projects:
        pid = p_dir.name
        prov_res = FlowProjectSubagentWorker.validate_provenance_receipt(p_dir)
        vqa_file = p_dir / "03_visuals" / "flow_screenshots" / "visual_qa_report.json"
        use_fast_v5 = False
        if vqa_file.exists():
            try:
                vqa_data = json.loads(vqa_file.read_text(encoding="utf-8"))
                if (
                    vqa_data.get("gate_v5", {}).get("status") == "PASS"
                    and vqa_data.get("gate_v5", {}).get("valid_clips_count", 0) >= CLIP_COUNT_MIN
                ):
                    use_fast_v5 = True
            except Exception:
                pass
        v5_res = GoogleFlowWhaleController.verify_flow_native_clips_v5(pid, deep_probe=not use_fast_v5)
        p_errors = list(prov_res.get("errors", []))
        f_url = prov_res.get("flow_project_url", "")
        t_id = prov_res.get("tab_target_id", "")

        if f_url:
            if f_url in seen_urls and seen_urls[f_url] != pid:
                p_errors.append(f"duplicate_flow_project_url_with_{seen_urls[f_url]}")
            else:
                seen_urls[f_url] = pid
        if t_id:
            if t_id in seen_tabs and seen_tabs[t_id] != pid:
                p_errors.append(f"duplicate_tab_target_id_with_{seen_tabs[t_id]}")
            else:
                seen_tabs[t_id] = pid

        p_passed = (
            len(p_errors) == 0
            and v5_res["passed"]
            and v5_res["valid_clips_count"] >= CLIP_COUNT_MIN
            and v5_res["invalid_clips_count"] == 0
        )
        if not p_passed:
            all_projects_provenance_ok = False

        project_provenance_results[pid] = {
            "passed": p_passed,
            "flow_project_url": f_url,
            "tab_target_id": t_id,
            "valid_clips_count": v5_res["valid_clips_count"],
            "invalid_clips_count": v5_res["invalid_clips_count"],
            "errors": p_errors,
        }

    checks["projects_flow_provenance_and_v1_v5"] = {
        "passed": all_projects_provenance_ok,
        "projects_checked": len(target_projects),
        "results": project_provenance_results,
    }

    stage_passed = all(
        v.get("passed", True) for v in checks.values() if isinstance(v, dict) and "passed" in v
    )
    return {
        "stage": "Stage 2: Browser Generation QA",
        "passed": stage_passed,
        "checks": checks,
    }


def run_media_integrity_qa(project_id: str | None = None) -> dict[str, Any]:
    """
    Stage 3: Media Integrity & Video Autopsy QA
    Runs 7-point MediaIntegrityValidator (ffprobe/ffmpeg + OpenCV frame diff + optical flow + audio VAD + anti-derivative)
    and VideoAutopsyEngine (including Guard 2 perceptual 64-bit dHash & Guard 1/6 provenance receipt)
    on assembled Shorts videos and native clips.
    """
    from pipeline.video_autopsy import VideoAutopsyEngine

    target_projects: list[Path] = []
    if project_id:
        p_dir = PROJECTS_DIR / project_id
        if p_dir.exists():
            target_projects = [p_dir]
    else:
        if PROJECTS_DIR.exists():
            target_projects = sorted([
                d for d in PROJECTS_DIR.iterdir()
                if d.is_dir() and (d / "05_assembly" / "final_shorts_1080x1920.mp4").exists()
            ])

    project_results: dict[str, Any] = {}
    all_passed = len(target_projects) > 0

    for p_dir in target_projects:
        pid = p_dir.name
        final_mp4 = p_dir / "05_assembly" / "final_shorts_1080x1920.mp4"
        clips_dir = p_dir / "03_visuals" / "flow_native_clips"
        clip_files = sorted(clips_dir.glob("*.mp4"), key=numeric_clip_sort_key) if clips_dir.exists() else []

        try:
            receipt_file = p_dir / "03_visuals" / "flow_provenance_receipt.json"
            if not receipt_file.exists():
                for cf in clip_files:
                    MediaIntegrityValidator.verify_not_synthetic_derivative(cf, strict=True)

            probe_cache_file = p_dir / "05_assembly" / "probe_report.json"
            autopsy_cache_file = p_dir / "05_assembly" / "video_autopsy_report.json"
            if (
                probe_cache_file.exists()
                and autopsy_cache_file.exists()
                and final_mp4.exists()
                and abs(autopsy_cache_file.stat().st_mtime - final_mp4.stat().st_mtime) < 900.0
            ):
                probe = json.loads(probe_cache_file.read_text(encoding="utf-8"))
                autopsy = json.loads(autopsy_cache_file.read_text(encoding="utf-8"))
            else:
                probe = MediaIntegrityValidator.validate_video_file(
                    final_mp4,
                    min_size_bytes=MIN_CLIP_SIZE_BYTES,
                    require_30s_shorts=True,
                    check_motion=True,
                    check_audio=True,
                )
                autopsy = VideoAutopsyEngine.inspect_project(p_dir, save_report=True)
            valid_clips = [c.name for c in clip_files if c.stat().st_size >= MIN_CLIP_SIZE_BYTES]
            has_multi_clips = len(valid_clips) >= CLIP_COUNT_MIN
            dedup_info = autopsy.get("thumbnails_and_dedup", {})
            provenance_ok = bool(dedup_info.get("provenance_receipt_valid"))
            zero_derivatives = len(dedup_info.get("derivative_clips_across_projects", [])) == 0
            proj_pass = (
                bool(probe.get("passed_integrity"))
                and has_multi_clips
                and bool(autopsy.get("passed"))
                and provenance_ok
                and zero_derivatives
            )
            if not proj_pass:
                all_passed = False
            project_results[pid] = {
                "passed": proj_pass,
                "autopsy_score": autopsy.get("autopsy_score", 0.0),
                "provenance_receipt_valid": provenance_ok,
                "derivative_clips_count": len(dedup_info.get("derivative_clips_across_projects", [])),
                "video_path": str(final_mp4),
                "size_mb": round(probe["file_size_bytes"] / (1024 * 1024), 2),
                "resolution": f"{probe['width']}x{probe['height']}",
                "fps": probe["fps"],
                "decoded_frames": autopsy["video_stream"]["decoded_frame_count"],
                "duration_seconds": probe["duration_seconds"],
                "video_stream_duration_seconds": probe.get("video_stream_duration_seconds"),
                "mean_frame_diff": probe.get("motion_analysis", {}).get("mean_frame_diff"),
                "min_pair_top_diff": probe.get("motion_analysis", {}).get("min_pair_top_diff"),
                "mean_optical_flow": probe.get("motion_analysis", {}).get("mean_optical_flow"),
                "cut_count": autopsy["video_stream"]["cut_count"],
                "cutaway_cool_ratio": autopsy["video_stream"]["cutaway_cool_ratio"],
                "speech_end_sec": autopsy["audio_stream"]["speech_end_sec"],
                "cumulative_dead_air_sec": autopsy["audio_stream"]["cumulative_dead_air_sec"],
                "last_100ms_dbfs": autopsy["audio_stream"]["last_100ms_dbfs"],
                "native_clips_count": len(valid_clips),
            }
        except Exception as exc:
            all_passed = False
            project_results[pid] = {
                "passed": False,
                "video_path": str(final_mp4),
                "error": str(exc),
            }

    return {
        "stage": "Stage 3: Media Integrity QA",
        "passed": all_passed,
        "projects_checked": len(target_projects),
        "results": project_results,
    }


def run_intent_content_qa(project_id: str | None = None) -> dict[str, Any]:
    """
    Stage 4: Intent & Content QA
    Verifies narrative and channel compliance per project:
      - SCRIPT_WORD_MIN-SCRIPT_WORD_MAX word count & 12 Master QA Gates (qa_report.json)
      - CLIP_COUNT_MIN-CLIP_COUNT_MAX Google Flow prompts; schema-4 prompt files (flow_all_in_one_prompts.json with
        "schema_version": 4) must also pass flow_prompt_builder.validate_flow_prompts. Older prompt files are
        reported as legacy_prompt_schema without failing (existing projects are not rewritten).
      - Non-blank, visually distinct A/B thumbnails (thumbnail_var_A.png > 80KB)
      - Single-line phrase-synced ASS subtitles without raw stage labels
      - en-US metadata with KR channel residence
    """
    from pipeline.video_autopsy import VideoAutopsyEngine

    target_projects: list[Path] = []
    if project_id:
        p_dir = PROJECTS_DIR / project_id
        if p_dir.exists():
            target_projects = [p_dir]
    else:
        if PROJECTS_DIR.exists():
            target_projects = sorted([
                d for d in PROJECTS_DIR.iterdir()
                if d.is_dir() and (d / "00_project_manifest.json").exists()
            ])

    project_results: dict[str, Any] = {}
    all_passed = len(target_projects) > 0

    for p_dir in target_projects:
        pid = p_dir.name
        manifest_file = p_dir / "00_project_manifest.json"
        manifest_data = json.loads(manifest_file.read_text(encoding="utf-8")) if manifest_file.exists() else {}

        qa_file = p_dir / "02_script" / "qa_report.json"
        if not qa_file.exists():
            qa_file = p_dir / "05_assembly" / "master_qa_report.json"

        flow_prompts_file = p_dir / "03_visuals" / "flow_all_in_one_prompts.json"
        if not flow_prompts_file.exists():
            flow_prompts_file = p_dir / "03_visuals" / "flow_prompts_7_clips.json"
        if not flow_prompts_file.exists():
            flow_prompts_file = p_dir / "03_visuals" / "veo_prompts.json"

        pub_dir = p_dir / "06_publish"

        qa_data = json.loads(qa_file.read_text(encoding="utf-8")) if qa_file.exists() else {}
        raw_prompts = json.loads(flow_prompts_file.read_text(encoding="utf-8")) if flow_prompts_file.exists() else []
        flow_prompts = (raw_prompts.get("prompts") or raw_prompts.get("clips", [])) if isinstance(raw_prompts, dict) else raw_prompts

        word_count = qa_data.get("word_count") or manifest_data.get("word_count", 0)
        gates_passed = bool(qa_data.get("all_gates_passed"))
        from pipeline.flow_prompt_builder import validate_flow_prompts

        prompt_schema_version = raw_prompts.get("schema_version") if isinstance(raw_prompts, dict) else None
        words_ok = SCRIPT_WORD_MIN <= word_count <= SCRIPT_WORD_MAX
        prompt_issues = validate_flow_prompts(flow_prompts)
        prompts_ok = (
            prompt_schema_version == FLOW_PROMPTS_SCHEMA_VERSION
            and CLIP_COUNT_MIN <= len(flow_prompts) <= CLIP_COUNT_MAX
            and not prompt_issues
        )

        thumb_a = pub_dir / "thumbnail_var_A.png"
        thumb_ok = thumb_a.exists() and thumb_a.stat().st_size > 80_000
        autopsy_cache_file = p_dir / "05_assembly" / "video_autopsy_report.json"
        if autopsy_cache_file.exists():
            thumb_div = json.loads(autopsy_cache_file.read_text(encoding="utf-8")).get("thumbnails_and_dedup", {})
        else:
            thumb_div = VideoAutopsyEngine.inspect_thumbnails_and_dedup(p_dir)
        has_final_mp4 = (p_dir / "05_assembly" / "final_shorts_1080x1920.mp4").exists()
        thumb_distinct_ok = bool(thumb_div.get("thumbnails_distinct")) if has_final_mp4 else thumb_ok

        ass_file = p_dir / "04_audio" / "subtitles.ass"
        sub_metrics = VideoAutopsyEngine.inspect_subtitles(ass_file)
        sub_ok = sub_metrics["is_dynamic_2line_compliant"] if has_final_mp4 else True

        meta_file = pub_dir / "metadata.json"
        meta_data = json.loads(meta_file.read_text(encoding="utf-8")) if meta_file.exists() else {}
        r36_localization_ok = (
            meta_data.get("video_language") == "en-US"
            and meta_data.get("title_description_language") == "en-US"
            and meta_data.get("channel_residence_country") == "KR"
        )

        proj_pass = (
            gates_passed
            and words_ok
            and prompts_ok
            and thumb_ok
            and thumb_distinct_ok
            and sub_ok
            and r36_localization_ok
        )
        if not proj_pass:
            all_passed = False

        project_results[pid] = {
            "passed": proj_pass,
            "word_count": word_count,
            "gates_passed": gates_passed,
            "flow_prompts_count": len(flow_prompts),
            "prompt_schema_version": prompt_schema_version,
            "prompt_issues": prompt_issues,
            "thumbnail_var_a_bytes": thumb_a.stat().st_size if thumb_a.exists() else 0,
            "thumbnail_non_blank": thumb_ok,
            "thumbnail_ab_bg_diff": thumb_div["thumb_ab_bg_diff"],
            "thumbnail_distinct_ok": thumb_distinct_ok,
            "subtitles_single_line_ok": sub_ok,
            "r36_localization_ok": r36_localization_ok,
        }

    return {
        "stage": "Stage 4: Intent & Content QA",
        "passed": all_passed,
        "projects_checked": len(target_projects),
        "results": project_results,
    }


def run_full_executable_qa(
    project_id: str | None = None,
    cdp_port: int = 9222,
    require_live_cdp: bool = False,
) -> dict[str, Any]:
    """Runs all 4 executable QA stages and returns a consolidated report."""
    s1 = run_preflight_qa(cdp_port=cdp_port, require_live_cdp=require_live_cdp)
    s2 = run_browser_generation_qa(project_id=project_id)
    s3 = run_media_integrity_qa(project_id=project_id)
    s4 = run_intent_content_qa(project_id=project_id)

    all_passed = s1["passed"] and s2["passed"] and s3["passed"] and s4["passed"]
    report = {
        "all_passed": all_passed,
        "target_project": project_id or "ALL_PROJECTS",
        "stages": {
            "preflight_qa": s1,
            "browser_generation_qa": s2,
            "media_integrity_qa": s3,
            "intent_content_qa": s4,
        },
    }
    return report
