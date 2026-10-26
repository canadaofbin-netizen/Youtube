"""
Test Suite for Google Flow Credit Auto-Approval, Gate V1-V5 Visual QA, and Anti-Placeholder Strict Policy
Validates:
1. Anti-Placeholder Fatal Error Policy: assemble_clips_if_available(strict=True) raises RuntimeError
   when clips are missing or < 1MB (rejecting fake black screen / thumbnail loops).
2. assemble_final_shorts_video raises RuntimeError when forced and valid clips (> 1MB) are missing.
3. Gate V5 verification helper correctly validates clip presence and file size (> 1MB).
4. FlowProjectSubagentWorker correctly initializes credit_approved and visual_qa_report fields.
Adheres strictly to R28 (self-contained test hygiene with try...finally cleanup).
"""

import pytest
from pathlib import Path
from pipeline.config import PROJECTS_DIR
from pipeline.flow_browser import FlowProjectSubagentWorker, GoogleFlowWhaleController
from pipeline.orchestrator import PipelineOrchestrator
from pipeline.storage import ProjectStorage
from produce_psychology_batch import assemble_final_shorts_video


def test_anti_placeholder_fatal_error_on_missing_clips():
    """Validates that assemble_clips_if_available(strict=True) raises RuntimeError when no clips exist."""
    proj_id = "test_smoke_anti_fake_missing"
    storage = ProjectStorage(proj_id, title="Smoke Test Missing Clips", pillar="bci_tech")
    try:
        with pytest.raises(RuntimeError, match="FATAL ERROR \\[Anti-Placeholder Policy\\]"):
            PipelineOrchestrator.assemble_clips_if_available(storage, strict=True)
    finally:
        import shutil
        shutil.rmtree(storage.project_dir, ignore_errors=True)


def test_anti_placeholder_fatal_error_on_undersized_clips():
    """Validates that clips smaller than 1MB are rejected and trigger Fatal Error."""
    proj_id = "test_smoke_anti_fake_undersized"
    storage = ProjectStorage(proj_id, title="Smoke Test Undersized Clips", pillar="bci_tech")
    try:
        clips_dir = storage.project_dir / "03_visuals" / "flow_native_clips"
        clips_dir.mkdir(parents=True, exist_ok=True)
        tiny_clip = clips_dir / "clip_1.mp4"
        # Write dummy file of only 500 bytes (far below 1MB requirement)
        tiny_clip.write_bytes(b"\x00" * 500)

        with pytest.raises(RuntimeError, match="FATAL ERROR \\[Anti-Placeholder Policy\\]"):
            PipelineOrchestrator.assemble_clips_if_available(storage, strict=True)
    finally:
        import shutil
        shutil.rmtree(storage.project_dir, ignore_errors=True)


def test_gate_v5_verification_helper():
    """Validates Gate V5 verification logic for clip presence and > 1MB byte size."""
    proj_id = "test_smoke_gate_v5_check"
    storage = ProjectStorage(proj_id, title="Smoke Gate V5", pillar="bci_tech")
    try:
        # Case 1: Missing clips -> FAIL
        res_empty = GoogleFlowWhaleController.verify_flow_native_clips_v5(proj_id)
        assert res_empty["status"] == "FAIL"
        assert res_empty["passed"] is False

        # Case 2: Undersized clip (< 1MB) -> FAIL
        clips_dir = storage.project_dir / "03_visuals" / "flow_native_clips"
        clips_dir.mkdir(parents=True, exist_ok=True)
        tiny_file = clips_dir / "clip_1.mp4"
        tiny_file.write_bytes(b"dummy_short" * 100)
        res_tiny = GoogleFlowWhaleController.verify_flow_native_clips_v5(proj_id)
        assert res_tiny["status"] == "FAIL"
        assert res_tiny["invalid_clips_count"] == 1

        # Case 3: Valid clip (> 1MB) -> PASS
        large_file = clips_dir / "clip_1.mp4"
        large_file.write_bytes(b"\x00" * 1_000_100)
        res_valid = GoogleFlowWhaleController.verify_flow_native_clips_v5(proj_id)
        assert res_valid["status"] == "PASS"
        assert res_valid["passed"] is True
        assert res_valid["valid_clips_count"] == 1
    finally:
        import shutil
        shutil.rmtree(storage.project_dir, ignore_errors=True)


def test_worker_credit_approval_and_visual_qa_fields():
    """Validates worker initialization of credit approval tracking and visual QA reports."""
    worker = FlowProjectSubagentWorker("test_worker_proj_01")
    assert worker.credit_approved is False
    assert isinstance(worker.visual_qa_report, dict)
    assert worker.status == "initialized"


def test_produce_psychology_batch_anti_fake_error():
    """Validates that assemble_final_shorts_video raises RuntimeError instead of rendering fake video."""
    proj_id = "test_smoke_psych_assembly_fatal"
    storage = ProjectStorage(proj_id, title="Smoke Psych Assembly", pillar="bci_tech")
    try:
        with pytest.raises(RuntimeError, match="FATAL ERROR \\[Anti-Placeholder Policy\\]"):
            assemble_final_shorts_video(storage, force=True)
    finally:
        import shutil
        shutil.rmtree(storage.project_dir, ignore_errors=True)


def test_layer3_static_asset_and_screenshot_blocker():
    """Validates Layer 3 guard blocking <img>, poster, .png/.jpg, and screenshots from being saved as video."""
    assert FlowProjectSubagentWorker.is_valid_video_asset_url("flow_gate_v1_prompt_approved.png", "image/png") is False
    assert FlowProjectSubagentWorker.is_valid_video_asset_url("https://flow.google.com/poster_frame.jpg", "image/jpeg") is False
    assert FlowProjectSubagentWorker.is_valid_video_asset_url("thumbnail_var_A.png", "image/png") is False
    assert FlowProjectSubagentWorker.is_valid_video_asset_url("shot_01_flow.mp4", "video/mp4") is True


def test_circuit_breaker_trips_after_max_retries():
    """Validates Phase 4 Circuit Breaker trips FlowCircuitBreakerError after max_retries=2 when rendering fails to start."""
    import asyncio
    from pipeline.flow_browser import FlowCircuitBreakerError
    import pipeline.flow_browser as fb_mod

    class DummyIdleClient:
        async def eval(self, _js: str):
            return {"is_rendering": False, "found": True, "disabled": False, "x": 100, "y": 100, "injected": True, "button_enabled": True}

        async def send(self, _method: str, _params: dict | None = None):
            return {}

    worker = FlowProjectSubagentWorker("test_cb_trip_proj", trigger_generation=True, max_retries=2)
    orig_timeout = fb_mod.FLOW_TRIGGER_VERIFY_TIMEOUT_SEC
    fb_mod.FLOW_TRIGGER_VERIFY_TIMEOUT_SEC = 0.2
    try:
        async def _capture_dummy(name: str) -> str:
            return f"/tmp/{name}"

        with pytest.raises(FlowCircuitBreakerError, match="CIRCUIT BREAKER TRIPPED"):
            asyncio.run(worker.trigger_and_verify_generation(DummyIdleClient(), "test prompt", _capture_dummy))
        assert worker.circuit_breaker_tripped is True
        assert worker.retry_count == 2
    finally:
        fb_mod.FLOW_TRIGGER_VERIFY_TIMEOUT_SEC = orig_timeout


@pytest.mark.integration
def test_executable_qa_preflight_and_browser_gates():
    """Validates Phase 5 Executable Pre-Flight QA and Browser Generation QA gates."""
    from pipeline.qa_gates import run_browser_generation_qa, run_preflight_qa

    s1 = run_preflight_qa(require_live_cdp=False)
    assert s1["passed"] is True
    assert s1["checks"]["zero_external_paid_apis"]["passed"] is True
    assert s1["checks"]["ffmpeg_binary"]["passed"] is True

    s2 = run_browser_generation_qa()
    assert s2["checks"]["layer3_static_asset_blocker"]["passed"] is True
    assert s2["checks"]["layer1_worker_circuit_breaker_config"]["passed"] is True


def test_media_integrity_rejects_static_slideshow_and_frozen_middle_clip(tmp_path: Path):
    """
    Validates that MediaIntegrityValidator detects and raises MediaIntegrityError on:
    (a) A single static frame video,
    (b) A 5-image static slideshow (5 distinct static images concatenated, 0 intra-segment motion),
    (c) A video with 4 dynamic segments and 1 frozen/black middle segment (50% anchor frozen).
    """
    import cv2
    import numpy as np
    from pipeline.media_integrity import MediaIntegrityError, MediaIntegrityValidator

    w, h, fps = 180, 320, 10
    total_frames = 60  # 6.0s @ 10fps
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")

    # (a) Single static frame video
    static_mp4 = tmp_path / "static_single.mp4"
    writer = cv2.VideoWriter(str(static_mp4), fourcc, fps, (w, h))
    base_img = np.full((h, w, 3), 120, dtype=np.uint8)
    for _ in range(total_frames):
        writer.write(base_img)
    writer.release()

    m_static = MediaIntegrityValidator.compute_frame_motion_metrics(static_mp4)
    assert m_static["is_static_or_frozen"] is True
    assert m_static["min_intra_segment_diff"] == 0.0
    with pytest.raises(MediaIntegrityError, match="Check 4 Failed"):
        MediaIntegrityValidator.validate_video_file(static_mp4, min_size_bytes=100, strict=True)

    # (b) 5-image static slideshow (5 completely different static patterns, 12 frames = 1.2s each)
    slideshow_mp4 = tmp_path / "static_slideshow_5_images.mp4"
    writer = cv2.VideoWriter(str(slideshow_mp4), fourcc, fps, (w, h))
    rng = np.random.default_rng(42)
    slides = [rng.integers(0, 255, size=(h, w, 3), dtype=np.uint8) for _ in range(5)]
    for f_idx in range(total_frames):
        seg = min(4, f_idx // 12)
        writer.write(slides[seg])
    writer.release()

    m_slide = MediaIntegrityValidator.compute_frame_motion_metrics(slideshow_mp4)
    assert m_slide["mean_upper_diff"] > 10.0  # Inter-segment diff is high
    assert m_slide["min_intra_segment_diff"] < 0.5  # Intra-segment diff catches the static slide!
    assert m_slide["is_static_or_frozen"] is True
    with pytest.raises(MediaIntegrityError, match="Check 4 Failed"):
        MediaIntegrityValidator.validate_video_file(slideshow_mp4, min_size_bytes=100, strict=True)

    # (c) 4 dynamic segments + 1 frozen black middle segment (frames 24..38 completely black)
    frozen_mid_mp4 = tmp_path / "frozen_middle_segment.mp4"
    writer = cv2.VideoWriter(str(frozen_mid_mp4), fourcc, fps, (w, h))
    for f_idx in range(total_frames):
        if 24 <= f_idx <= 40:
            writer.write(np.zeros((h, w, 3), dtype=np.uint8))
        else:
            writer.write(rng.integers(0, 255, size=(h, w, 3), dtype=np.uint8))
    writer.release()

    m_frozen_mid = MediaIntegrityValidator.compute_frame_motion_metrics(frozen_mid_mp4)
    assert m_frozen_mid["min_intra_segment_diff"] < 0.5
    assert m_frozen_mid["is_static_or_frozen"] is True
    with pytest.raises(MediaIntegrityError, match="Check 4 Failed"):
        MediaIntegrityValidator.validate_video_file(frozen_mid_mp4, min_size_bytes=100, strict=True)


def test_trigger_rejects_disabled_button_even_when_preexisting_video_exists():
    """
    Validates that trigger_and_verify_generation does NOT false-positive pass when
    the page already has a <video> tag (video_count=1) and .ProseMirror is empty,
    if prompt injection failed or the Start generation button remained disabled.
    """
    import asyncio
    from pipeline.flow_browser import FlowCircuitBreakerError
    import pipeline.flow_browser as fb_mod

    class DisabledButtonPreexistingVideoClient:
        async def eval(self, js: str):
            if "video_count" in js and "is_rendering" not in js:
                return {"video_count": 1}
            if "selectAll" in js and "Before" not in js and "beforeinput" not in js:
                return True
            if "beforeinput" in js:
                # Simulate failed prompt injection where button stays disabled
                return {"injected": False, "button_found": True, "button_enabled": False}
            if "btn.getBoundingClientRect" in js:
                return {"found": True, "disabled": True, "x": 100, "y": 100}
            return {
                "is_rendering": True,
                "editor_cleared": True,
                "video_count": 1,
            }

        async def send(self, _method: str, _params: dict | None = None):
            return {}

    worker = FlowProjectSubagentWorker("test_false_pos_guard", trigger_generation=True, max_retries=2)
    orig_timeout = fb_mod.FLOW_TRIGGER_VERIFY_TIMEOUT_SEC
    fb_mod.FLOW_TRIGGER_VERIFY_TIMEOUT_SEC = 0.2
    try:
        async def _capture_dummy(name: str) -> str:
            return f"/tmp/{name}"

        with pytest.raises(FlowCircuitBreakerError, match="CIRCUIT BREAKER TRIPPED"):
            asyncio.run(
                worker.trigger_and_verify_generation(
                    DisabledButtonPreexistingVideoClient(),
                    "test prompt",
                    _capture_dummy,
                )
            )
        assert worker.generation_triggered is False
        assert worker.circuit_breaker_tripped is True
        assert worker.retry_count == 2
    finally:
        fb_mod.FLOW_TRIGGER_VERIFY_TIMEOUT_SEC = orig_timeout


def test_video_autopsy_subtitle_and_early_freeze_detection(tmp_path: Path):
    """
    Validates that VideoAutopsyEngine and MediaIntegrityValidator detect:
    1. Wall-of-text subtitles with raw stage labels (PARADOX:, DILEMMA:) vs compliant 2-line phrase-synced ASS.
    2. Early video stream freeze / decoded frame shortfall when a video claiming 30s only has 60 frames.
    3. Speechless pure-drone WAV vs active narrated audio in inspect_audio_stream.
    """
    import cv2
    import numpy as np
    import wave
    from pipeline.media_integrity import MediaIntegrityValidator
    from pipeline.video_autopsy import VideoAutopsyEngine
    from produce_psychology_batch import PSYCHOLOGY_TOPICS, generate_ass_subtitles

    # 1. Wall-of-text polluted ASS vs compliant dynamic 2-line ASS
    bad_ass = tmp_path / "bad_subtitles.ass"
    bad_ass.write_text(
        "[V4+ Styles]\n"
        "Style: Default,Inter,46,&H00FFFFFF,&H0000D7FF,&HCC000000,&H80000000,1,0,0,0,100,100,0,0,1,3,2,2,80,80,280,1\n"
        "[Events]\n"
        "Dialogue: 0,0:00:00.00,0:00:10.00,Default,,0,0,0,,PARADOX: One two three four five six seven eight nine ten eleven twelve.\n",
        encoding="utf-8",
    )
    bad_sub_rep = VideoAutopsyEngine.inspect_subtitles(bad_ass)
    assert bad_sub_rep["has_raw_stage_labels"] is True
    assert bad_sub_rep["is_dynamic_2line_compliant"] is False

    good_ass = tmp_path / "good_subtitles.ass"
    generate_ass_subtitles(PSYCHOLOGY_TOPICS[0], good_ass, speech_end_sec=27.2)
    good_sub_rep = VideoAutopsyEngine.inspect_subtitles(good_ass)
    assert good_sub_rep["has_raw_stage_labels"] is False
    assert good_sub_rep["dialogue_count"] >= 12
    assert good_sub_rep["max_words_per_event"] <= 8
    assert good_sub_rep["default_font_size"] == 86
    assert good_sub_rep["is_dynamic_2line_compliant"] is True

    # 2. Early video stream freeze (60 frames = 6.0s @ 10fps when expected_duration_sec=30.0)
    short_mp4 = tmp_path / "short_freeze.mp4"
    w, h, fps = 180, 320, 10
    writer = cv2.VideoWriter(str(short_mp4), cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
    rng = np.random.default_rng(7)
    for _ in range(60):
        writer.write(rng.integers(0, 255, size=(h, w, 3), dtype=np.uint8))
    writer.release()

    m_short = MediaIntegrityValidator.compute_frame_motion_metrics(short_mp4, expected_duration_sec=30.0)
    assert m_short["decoded_frame_shortfall"] is True
    assert m_short["is_static_or_frozen"] is True

    # 3. Pure sine drone WAV (no active speech) -> rejected by inspect_audio_stream
    drone_wav = tmp_path / "pure_drone.wav"
    sr = 16000
    t = np.arange(sr * 5, dtype=np.float32) / sr
    sine_pcm = (0.04 * np.sin(2.0 * np.pi * 432.0 * t) * 32767.0).astype(np.int16)
    with wave.open(str(drone_wav), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(sine_pcm.tobytes())

    drone_rep = VideoAutopsyEngine.inspect_audio_stream(drone_wav)
    assert drone_rep["has_active_speech"] is False
    assert drone_rep["is_truncated_at_30s"] is True


@pytest.mark.integration
def test_evolved_projects_pass_forensic_autopsy():
    """
    Validates that the genuine live Google Flow flagship project (psych_03_split_brain_dual_consciousness)
    achieves 100.0 autopsy score with valid decoded frames, zero dead air, native color grading preserved,
    distinct A/B/C thumbnails, and valid R37 provenance receipt.
    """
    from pipeline.video_autopsy import VideoAutopsyEngine

    pid = "psych_03_split_brain_dual_consciousness"
    rep = VideoAutopsyEngine.inspect_project(pid, save_report=False)
    assert rep["passed"] is True
    assert rep["autopsy_score"] == 100.0
    assert rep["defect_count"] == 0
    assert rep["video_stream"]["decoded_frame_count"] >= 720
    assert rep["video_stream"]["has_early_stream_freeze"] is False
    assert rep["video_stream"]["color_palette_inverted"] is False
    assert len(rep["video_stream"]["detected_cuts_sec"]) >= 4
    assert rep["audio_stream"]["has_active_speech"] is True
    assert rep["audio_stream"]["is_truncated_at_30s"] is False
    assert rep["audio_stream"]["cumulative_dead_air_sec"] <= 3.80
    assert rep["subtitles"]["is_dynamic_2line_compliant"] is True
    assert rep["thumbnails_and_dedup"]["thumbnails_distinct"] is True
    assert rep["thumbnails_and_dedup"]["provenance_receipt_valid"] is True
    assert rep["thumbnails_and_dedup"]["shared_clips_across_projects"] == []
    assert rep["thumbnails_and_dedup"]["derivative_clips_across_projects"] == []
    assert 5 <= rep["thumbnails_and_dedup"]["native_clips_count"] <= 10


def test_check6_rejects_excessive_dead_air_and_generator_preserves_metaphor(tmp_path: Path):
    """
    Validates:
    1. Check 6 (inspect_audio_stream) detects cumulative_dead_air_sec > 0.90s
       even when speech is present and not truncated at 30.0s, and NMS cut detection
       handles high intra-clip motion before hard cuts.
    2. ContentGenerator.generate builds Contract v4 visual_plan, clip_narrations, and flow_all_in_one_prompts
       without hardcoding 2500 BCE Egyptian chamber text into modern/1848 topics.
    """
    import wave
    import numpy as np
    from pipeline.flow_prompt_builder import validate_flow_prompts, validate_narrations
    from pipeline.generator import ContentGenerator
    from pipeline.video_autopsy import VideoAutopsyEngine

    # 1. Synthesize a 30s WAV with active modulated speech but two 0.65s silent gaps (1.30s > 0.90s dead air)
    bad_dead_air_wav = tmp_path / "dead_air_speech.wav"
    sr = 16000
    t = np.arange(sr * 30, dtype=np.float32) / sr
    carrier = np.sin(2.0 * np.pi * 220.0 * t) + 0.5 * np.sin(2.0 * np.pi * 440.0 * t)
    mod = 0.5 + 0.45 * np.sin(2.0 * np.pi * 4.5 * t)
    sig = 0.25 * carrier * mod
    sig[: int(0.2 * sr)] = 0.0
    sig[int(8.0 * sr) : int(8.65 * sr)] = 0.0   # 0.65s dead air gap 1
    sig[int(16.0 * sr) : int(16.65 * sr)] = 0.0  # 0.65s dead air gap 2
    sig[int(27.8 * sr) :] = 0.001 * np.sin(2.0 * np.pi * 432.0 * t[int(27.8 * sr) :])
    pcm = (np.clip(sig, -0.95, 0.95) * 32767.0).astype(np.int16)
    with wave.open(str(bad_dead_air_wav), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(pcm.tobytes())

    aud_rep = VideoAutopsyEngine.inspect_audio_stream(bad_dead_air_wav)
    assert aud_rep["has_active_speech"] is True
    assert aud_rep["is_truncated_at_30s"] is False
    assert aud_rep["cumulative_dead_air_sec"] >= 1.20

    # 2. Verify ContentGenerator builds topic-specific Contract v4 prompts without Egyptian fallback
    gen = ContentGenerator()
    bp = gen.generate(
        "brain_history",
        topic="Phineas Gage 1848 Tamping Iron Prefrontal Lobotomy",
        style="case_file",
    )
    prompts = bp["flow_all_in_one_prompts"]
    narrations = bp["clip_narrations"]
    assert 5 <= len(prompts) <= 10
    assert validate_narrations(narrations) == []
    assert validate_flow_prompts(prompts) == []
    for p in prompts:
        assert "Memphis" not in p["prompt"]
        assert "embalming" not in p["prompt"]



def test_r37_rejects_synthetic_derivative_metadata_tags(tmp_path: Path):
    """
    Guard 2 (R37): Validates that verify_not_synthetic_derivative detects and blocks
    FFmpeg-synthesized derivative clips carrying banned metadata markers
    (unique_flow_derivative, unique_batch, _boost, derivative_).
    """
    import subprocess
    from pipeline.media_integrity import MediaIntegrityError, MediaIntegrityValidator

    ffmpeg_exe = MediaIntegrityValidator.get_ffmpeg_exe()
    deriv_mp4 = tmp_path / "derivative_clone.mp4"
    cmd = [
        ffmpeg_exe, "-y", "-hide_banner", "-loglevel", "error",
        "-f", "lavfi", "-i", "testsrc2=size=180x320:rate=15:duration=2",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-metadata", "title=psych_99_clip_1_boost",
        "-metadata", "comment=unique_flow_derivative_psych_99_c1_s101",
        str(deriv_mp4),
    ]
    subprocess.run(cmd, check=True, capture_output=True)

    with pytest.raises(MediaIntegrityError, match="FATAL R37 VIOLATION"):
        MediaIntegrityValidator.verify_not_synthetic_derivative(deriv_mp4, strict=True)


def test_r37_perceptual_dhash_catches_cropped_flipped_tinted_clone(tmp_path: Path):
    """
    Guard 2 (R37): Validates that 64-bit Perceptual dHash (compute_perceptual_dhash &
    min_perceptual_dhash_distance) catches a clip that has been cropped, horizontally
    flipped (hflip), brightness/contrast shifted (eq), and color-tinted (colorbalance)
    so its SHA-256 is completely different, yet its perceptual Hamming distance is <= 10.
    """
    import hashlib
    import subprocess
    from pipeline.config import MAX_PERCEPTUAL_DHASH_HAMMING_DISTANCE
    from pipeline.media_integrity import MediaIntegrityValidator

    ffmpeg_exe = MediaIntegrityValidator.get_ffmpeg_exe()
    orig_mp4 = tmp_path / "master_orig.mp4"
    clone_mp4 = tmp_path / "transformed_clone.mp4"

    # 1. Create a structured dynamic test video
    subprocess.run(
        [
            ffmpeg_exe, "-y", "-hide_banner", "-loglevel", "error",
            "-f", "lavfi", "-i", "testsrc2=size=360x640:rate=15:duration=4",
            "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p",
            str(orig_mp4),
        ],
        check=True,
        capture_output=True,
    )

    # 2. Apply the exact shortcut transform chain: scale+crop + hflip + eq + colorbalance
    vf_shortcut = (
        "scale=396:704,crop=360:640:18:32,hflip,"
        "eq=contrast=1.08:brightness=0.03:saturation=1.12,"
        "colorbalance=rs=-0.15:gs=0.04:bs=0.18,format=yuv420p"
    )
    subprocess.run(
        [
            ffmpeg_exe, "-y", "-hide_banner", "-loglevel", "error",
            "-i", str(orig_mp4),
            "-vf", vf_shortcut,
            "-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p",
            str(clone_mp4),
        ],
        check=True,
        capture_output=True,
    )

    # SHA-256 hashes are 100% different
    sha_orig = hashlib.sha256(orig_mp4.read_bytes()).hexdigest()
    sha_clone = hashlib.sha256(clone_mp4.read_bytes()).hexdigest()
    assert sha_orig != sha_clone

    # Perceptual dHash catches the cropped + hflipped + color-shifted clone (distance <= 10)
    sig_orig = MediaIntegrityValidator.compute_perceptual_dhash(orig_mp4)
    sig_clone = MediaIntegrityValidator.compute_perceptual_dhash(clone_mp4)
    min_dist = MediaIntegrityValidator.min_perceptual_dhash_distance(sig_orig, sig_clone)
    assert min_dist <= MAX_PERCEPTUAL_DHASH_HAMMING_DISTANCE, (
        f"Expected perceptual dHash distance <= {MAX_PERCEPTUAL_DHASH_HAMMING_DISTANCE}, got {min_dist}"
    )


def test_r37_autopsy_fails_without_flow_provenance_receipt(tmp_path: Path):
    """
    Guard 1 (R37): Validates that VideoAutopsyEngine.inspect_thumbnails_and_dedup
    flags missing_or_invalid_flow_provenance_receipt when 03_visuals/flow_provenance_receipt.json
    is absent or invalid.
    """
    from pipeline.flow_browser import FlowProjectSubagentWorker
    from pipeline.video_autopsy import VideoAutopsyEngine

    fake_proj = tmp_path / "psych_99_unverified_project"
    (fake_proj / "03_visuals" / "flow_native_clips").mkdir(parents=True, exist_ok=True)
    (fake_proj / "06_publish").mkdir(parents=True, exist_ok=True)

    prov_res = FlowProjectSubagentWorker.validate_provenance_receipt(fake_proj)
    assert prov_res["valid"] is False
    assert "missing_flow_provenance_receipt_file" in prov_res["errors"]

    dedup_res = VideoAutopsyEngine.inspect_thumbnails_and_dedup(fake_proj)
    assert dedup_res["provenance_receipt_valid"] is False
    assert "missing_flow_provenance_receipt_file" in dedup_res["provenance_errors"]


def test_r37_qa_stage1_blocks_shortcut_functions_in_codebase():
    """
    Guard 3 (R37): Validates that Stage 1 Pre-Flight QA (run_preflight_qa) scans
    produce_*.py and pipeline/*.py and confirms zero shortcut clip-cloning functions
    exist in the codebase.
    """
    from pipeline.qa_gates import run_preflight_qa

    rep = run_preflight_qa(require_live_cdp=False)
    assert "zero_shortcut_code_lock" in rep["checks"]
    lock_check = rep["checks"]["zero_shortcut_code_lock"]
    assert lock_check["passed"] is True, f"Shortcut code lock violations: {lock_check['violations']}"
    assert lock_check["flow_max_parallel_batch_size"] == 5
    assert lock_check["violations"] == []


def test_r37_guard6_enforces_1_to_1_to_1_subagent_and_rejects_shared_tab_or_url(tmp_path: Path):
    """
    Guard 6 (R37): Validates:
    1. FlowProjectSubagentWorker enforces strict 1:1:1 binding (rejects empty or multi-topic project_id).
    2. VideoAutopsyEngine flags duplicate flow_project_url or tab_target_id shared across two projects.
    """
    from pipeline.flow_browser import FlowProjectSubagentWorker
    from pipeline.video_autopsy import VideoAutopsyEngine

    # 1. Multi-topic bundling into a single subagent is rejected immediately
    with pytest.raises(ValueError, match="GUARD 6 VIOLATION"):
        FlowProjectSubagentWorker("psych_01,psych_02")

    worker = FlowProjectSubagentWorker("psych_03_split_brain_dual_consciousness")
    assert worker.subagent_1_to_1_bound is True
    assert worker.worker_id == "subagent-psych_03_split_brain_dual_consciousness"

    # 2. Shared flow_project_url or tab_target_id across projects is flagged by inspect_thumbnails_and_dedup
    import json
    url_shared = "https://flow.google.com/project/b49093f4-7407-4813-96a8-59e3bd8f5d6b"
    tab_shared = "A94B9F128E5C4D03B71A2F8E9C103456"
    sample_proj = tmp_path / "psych_03_split_brain_dual_consciousness"
    (sample_proj / "03_visuals" / "flow_native_clips").mkdir(parents=True, exist_ok=True)
    (sample_proj / "06_publish").mkdir(parents=True, exist_ok=True)
    (sample_proj / "03_visuals" / "flow_provenance_receipt.json").write_text(
        json.dumps({
            "project_id": "psych_03_split_brain_dual_consciousness",
            "worker_id": "subagent-psych_03_split_brain_dual_consciousness",
            "subagent_1_to_1_bound": True,
            "flow_project_url": url_shared,
            "tab_target_id": tab_shared,
            "prompts_submitted_count": 5,
            "visual_gates_passed": True,
            "clips": [],
        }),
        encoding="utf-8",
    )

    dedup_shared = VideoAutopsyEngine.inspect_thumbnails_and_dedup(
        sample_proj,
        all_provenance_urls={url_shared: ["psych_03_split_brain_dual_consciousness", "psych_99_clone"]},
        all_provenance_tabs={tab_shared: ["psych_03_split_brain_dual_consciousness", "psych_99_clone"]},
    )
    assert dedup_shared["provenance_receipt_valid"] is False
    assert any("shared_flow_project_url_across_projects" in e for e in dedup_shared["provenance_errors"])
    assert any("shared_tab_target_id_across_projects" in e for e in dedup_shared["provenance_errors"])


def test_r37_max_5_topics_per_batch_cap():
    """
    Guard 6 (R37): Validates that FLOW_MAX_PARALLEL_BATCH_SIZE == 5,
    GoogleFlowWhaleController.MAX_BATCH_CONCURRENCY == 5, and FlowParallelOrchestrator
    strictly chunks any larger topic list into batches of at most 5 topics per batch.
    """
    from pipeline.config import FLOW_MAX_PARALLEL_BATCH_SIZE
    from pipeline.flow_browser import FlowParallelOrchestrator, GoogleFlowWhaleController

    assert FLOW_MAX_PARALLEL_BATCH_SIZE == 5
    assert GoogleFlowWhaleController.MAX_BATCH_CONCURRENCY == 5
    assert FlowParallelOrchestrator.MAX_BATCH_SIZE == 5

    # Attempting to instantiate FlowParallelOrchestrator with max_batch_size > 5 clamps to 5
    orch = FlowParallelOrchestrator(cdp_port=9222, max_batch_size=12)
    assert orch.max_batch_size == 5

    sample_12_topics = [f"psych_{i:02d}_topic" for i in range(1, 13)]
    batches = orch.split_into_batches(sample_12_topics, max_batch_size=10)
    assert len(batches) == 3
    assert [len(b) for b in batches] == [5, 5, 2]
    assert all(len(b) <= 5 for b in batches)
