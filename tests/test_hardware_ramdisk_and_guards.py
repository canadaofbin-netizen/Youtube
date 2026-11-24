from __future__ import annotations

import errno
import hashlib
import json
import os
import shutil
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import inspect

import pytest

import pipeline.audio_utils as vf_mod
from pipeline.assembler import (
    _atomic_copy_file,
    _merge_xfade_group_multistage,
    _render_cut_segment,
    assemble_diorama_project,
    compute_locked_edl_cut_frame_requirements,
    recut_diorama_cuts,
)
from pipeline.hardware_profile import (
    detect_host_hardware,
    resolve_assembler_workers,
    resolve_cpu_budget,
    resolve_ffmpeg_threads_per_worker,
    resolve_whisper_threads,
    resolve_xfade_workers,
)
from pipeline.media_cache import (
    _should_persist_sha_for_path,
    atomic_commit_from_scratch,
    enforce_ram_scratch_budget,
    get_ram_scratch_root,
    is_ephemeral_scratch_path,
    ram_tempdir,
    stage_local_file,
)


class TestGuard1ExdevAtomicCommit:
    """Guard 1: Cross-mount `/dev/shm -> FUSE/ext4` commits never fail with `Errno 18 EXDEV`."""

    def test_atomic_commit_handles_exdev_and_cleans_scratch_source(self, tmp_path: Path) -> None:
        scratch_dir = tmp_path / "fake_shm"
        fuse_dir = tmp_path / "fake_fuse" / "05_assembly"
        scratch_dir.mkdir(parents=True)

        src_file = scratch_dir / "rendered_out.mp4"
        payload = b"ftypisom_mock_h264_stream_" * 512
        src_file.write_bytes(payload)
        dst_file = fuse_dir / "final_shorts_1080x1920.mp4"

        real_replace = os.replace
        replace_calls: list[tuple[Path, Path]] = []

        def _mock_exdev_replace(src: str | os.PathLike[str], dst: str | os.PathLike[str]) -> None:
            sp = Path(src)
            dp = Path(dst)
            replace_calls.append((sp, dp))
            if sp.parent.resolve() != dp.parent.resolve():
                raise OSError(errno.EXDEV, "Invalid cross-device link")
            real_replace(sp, dp)

        with patch("pipeline.media_cache.os.replace", side_effect=_mock_exdev_replace):
            out = atomic_commit_from_scratch(src_file, dst_file)

        assert out == dst_file
        assert dst_file.is_file()
        assert dst_file.read_bytes() == payload
        assert not src_file.exists(), "Scratch source should be unlinked when keep_src=False"
        # Ensure sibling .tmp inside fuse_dir was swapped cleanly and no .tmp files remain
        leftover_tmps = [p for p in fuse_dir.iterdir() if p != dst_file]
        assert leftover_tmps == []
        assert any(sp.parent.resolve() == dp.parent.resolve() for sp, dp in replace_calls)

    def test_atomic_copy_file_preserves_scratch_source_under_exdev(self, tmp_path: Path) -> None:
        scratch_dir = tmp_path / "fake_shm"
        fuse_dir = tmp_path / "fake_fuse"
        scratch_dir.mkdir(parents=True)
        fuse_dir.mkdir(parents=True)

        src_file = scratch_dir / "local_final.mp4"
        payload = b"keep_source_for_register_staged_copy_" * 128
        src_file.write_bytes(payload)
        dst_file = fuse_dir / "final_shorts_1080x1920.mp4"

        real_replace = os.replace

        def _forbid_cross_dir_replace(src: str | os.PathLike[str], dst: str | os.PathLike[str]) -> None:
            sp, dp = Path(src), Path(dst)
            if sp.parent.resolve() != dp.parent.resolve():
                raise OSError(errno.EXDEV, "Invalid cross-device link")
            real_replace(sp, dp)

        with patch("pipeline.media_cache.os.replace", side_effect=_forbid_cross_dir_replace):
            _atomic_copy_file(src_file, dst_file, suffix=".mp4.tmp")

        assert src_file.is_file(), "_atomic_copy_file must preserve src for downstream callers"
        assert dst_file.is_file()
        assert dst_file.read_bytes() == payload
        assert not dst_file.with_suffix(".mp4.tmp").exists()


class TestGuard2EphemeralRamScratch:
    """Guard 2: `/dev/shm/aab_scratch` paths are recognized as ephemeral scratch with zero re-copy or FUSE SHA writes."""

    def test_ram_tempdir_and_ephemeral_detection_and_zero_copy_staging(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        scratch_root = get_ram_scratch_root()
        assert scratch_root.is_dir()
        if Path("/dev/shm").is_dir() and os.access("/dev/shm", os.W_OK | os.X_OK):
            assert str(scratch_root.resolve()).startswith("/dev/shm/")

        fake_sha_json = tmp_path / "persistent_sha256_cache.json"
        monkeypatch.setenv("AAB_PERSISTENT_SHA_CACHE_PATH", str(fake_sha_json))

        with ram_tempdir(prefix="aab_test_g2_") as td:
            assert isinstance(td, str)
            td_path = Path(td)
            assert is_ephemeral_scratch_path(td_path) is True

            clip_p = td_path / "clip_01.mp4"
            raw_bytes = b"ramdisk_clip_payload_" * 256
            clip_p.write_bytes(raw_bytes)
            expected_sha = hashlib.sha256(raw_bytes).hexdigest()

            assert is_ephemeral_scratch_path(clip_p) is True
            assert _should_persist_sha_for_path(clip_p) is False

            with patch("pipeline.media_cache.shutil.copy2", wraps=shutil.copy2) as spy_copy:
                staged_p, got_sha = stage_local_file(clip_p)

            assert spy_copy.call_count == 0
            assert staged_p == clip_p.resolve()
            assert got_sha == expected_sha
            assert not fake_sha_json.exists(), "/dev/shm scratch files must never pollute persistent_sha256_cache.json"

        assert not td_path.exists()
        budget_stats = enforce_ram_scratch_budget()
        assert set(budget_stats.keys()) >= {"removed_staged", "removed_segments", "removed_global"}

    def test_media_integrity_skips_tmp_copy_for_ram_scratch_paths(self) -> None:
        from pipeline.media_integrity import MediaIntegrityValidator

        with ram_tempdir(prefix="aab_test_mi_") as td:
            dummy_mp4 = Path(td) / "clip_01.mp4"
            dummy_mp4.write_bytes(b"not_a_real_mp4_but_nonempty" * 64)
            with patch("pipeline.media_integrity.shutil.copy2") as mock_copy:
                res = MediaIntegrityValidator.compute_perceptual_dhash(dummy_mp4)
            assert mock_copy.call_count == 0
            assert res["frames_sampled"] == 0


class TestGuard3WhisperThreadPromotionAndBudgets:
    """Guard 3: Cached `_WHISPER_MODEL` upgrades `6 -> 8` threads on promotion and respects CPU budgets."""

    def test_cpu_worker_and_ffmpeg_thread_budgets(self) -> None:
        hw = detect_host_hardware()
        assert hw["cpu_count"] >= 1
        assert resolve_assembler_workers(6) == 6
        assert resolve_assembler_workers(8) == 8
        assert resolve_xfade_workers(6) == 6
        assert resolve_xfade_workers(8) == 8
        assert resolve_ffmpeg_threads_per_worker(8, 8) == 1
        assert resolve_ffmpeg_threads_per_worker(4, 8) == 2
        assert resolve_whisper_threads(6) == 6
        assert resolve_whisper_threads(8) == 8
        assert resolve_cpu_budget(6) == 6
        assert resolve_cpu_budget(8) == 8

        # Verify Workstream A <-> B contract signatures
        asm_sig = inspect.signature(assemble_diorama_project)
        assert "cpu_budget" in asm_sig.parameters
        assert asm_sig.parameters["cpu_budget"].default is None

        recut_sig = inspect.signature(recut_diorama_cuts)
        assert "cpu_budget" in recut_sig.parameters
        assert recut_sig.parameters["cpu_budget"].default is None

        seg_sig = inspect.signature(_render_cut_segment)
        assert "ffmpeg_threads" in seg_sig.parameters
        assert seg_sig.parameters["ffmpeg_threads"].default == 1

        xf_sig = inspect.signature(_merge_xfade_group_multistage)
        assert "n_workers" in xf_sig.parameters
        assert xf_sig.parameters["n_workers"].default is None

    def test_whisper_model_recreates_on_thread_promotion_6_to_8(self) -> None:
        orig_model = vf_mod._WHISPER_MODEL
        orig_threads = vf_mod._WHISPER_MODEL_THREADS
        created_calls: list[dict[str, Any]] = []

        def _fake_whisper_cls(model_size: str, **kwargs: Any) -> MagicMock:
            inst = MagicMock(name=f"WhisperModel_{kwargs.get('cpu_threads')}")
            inst.cpu_threads = kwargs.get("cpu_threads")
            created_calls.append({"model_size": model_size, **kwargs})
            return inst

        try:
            vf_mod._WHISPER_MODEL = None
            vf_mod._WHISPER_MODEL_THREADS = 0
            with patch("faster_whisper.WhisperModel", side_effect=_fake_whisper_cls):
                m6_first = vf_mod._whisper_model(cpu_threads=6)
                m6_second = vf_mod._whisper_model(cpu_threads=6)
                assert m6_first is m6_second
                assert len(created_calls) == 1
                assert created_calls[0]["cpu_threads"] == 6
                assert created_calls[0]["compute_type"] == "int8"
                assert vf_mod._WHISPER_MODEL_THREADS == 6

                # Promote overlapped (6) -> standalone (8): MUST recreate WhisperModel with 8 threads!
                m8 = vf_mod._whisper_model(cpu_threads=8)
                assert m8 is not m6_first
                assert len(created_calls) == 2
                assert created_calls[1]["cpu_threads"] == 8
                assert vf_mod._WHISPER_MODEL_THREADS == 8

                # Subsequent lower-budget call reuses the already-warmed 8-thread model without thrashing
                m_after = vf_mod._whisper_model(cpu_threads=6)
                assert m_after is m8
                assert len(created_calls) == 2
        finally:
            vf_mod._WHISPER_MODEL = orig_model
            vf_mod._WHISPER_MODEL_THREADS = orig_threads


class TestGuard4VirtualLockedEdlFrameRequirements:
    """Guard 4: Computes exact `30fps` `edl_frame_map` BEFORE any Flow or Blender MP4 clips exist on disk."""

    def test_compute_locked_edl_cut_frame_requirements_with_zero_mp4s_on_disk(self, tmp_path: Path) -> None:
        proj_dir = tmp_path / "virtual_v8_ep"
        (proj_dir / "02_script").mkdir(parents=True)
        (proj_dir / "03_visuals" / "flow_native_clips").mkdir(parents=True)
        (proj_dir / "03_visuals" / "brain_simulator_clips").mkdir(parents=True)
        (proj_dir / "04_audio").mkdir(parents=True)

        n_cuts = 18
        sentences = [f"Sentence number {i} explains how neural circuits fire rapidly." for i in range(1, n_cuts + 1)]
        acts = [
            {"act": a_i, "sentences": sentences[(a_i - 1) * 3 : a_i * 3]}
            for a_i in range(1, 7)
        ]
        script_doc = {
            "schema": 8,
            "profile": "neuro_diorama",
            "style_profile": "expressive_25d_v8",
            "format_profile": "shorts_expressive_v8",
            "voice_preset": "el_siren_v4",
            "sentences": sentences,
            "acts": acts,
        }
        (proj_dir / "02_script" / "script.json").write_text(json.dumps(script_doc, indent=2), encoding="utf-8")

        clips_spec: list[dict[str, Any]] = []
        for idx in range(1, n_cuts + 1):
            is_sim = idx in (2, 5, 8, 11, 14, 16, 17)
            tr_out = "action_impact_cut"
            if idx == 1:
                tr_out = "portal_crash_zoom_10f"
            elif idx == 4:
                tr_out = "whip_pan_blur_8f"
            clips_spec.append(
                {
                    "clip_index": idx,
                    "act": ((idx - 1) // 3) + 1,
                    "sentence_index": idx,
                    "end_sentence_index": idx,
                    "grammar": "brain_simulator_3d" if is_sim else "expressive_story_world",
                    "render_engine": "blender_3d_simulator" if is_sim else "google_flow",
                    "camera_move": "orbit_45_right" if is_sim else "push_in_slow",
                    "transition_out": tr_out,
                    "location_id": "brain_space" if is_sim else f"street_{idx % 4}",
                }
            )
        visual_plan = {
            "schema": 8,
            "profile": "neuro_diorama",
            "style_profile": "expressive_25d_v8",
            "format_profile": "shorts_expressive_v8",
            "fps": 30,
            "zero_clip_reuse": True,
            "clips": clips_spec,
        }
        (proj_dir / "03_visuals" / "visual_plan.json").write_text(json.dumps(visual_plan, indent=2), encoding="utf-8")

        # 18 sentences spanning 68.0s total (3.70s speech + ~0.08s gap each)
        spans: list[dict[str, Any]] = []
        cursor = 0.0
        for idx in range(1, n_cuts + 1):
            dur_s = 3.70 if idx < n_cuts else round(68.0 - cursor, 3)
            s0 = round(cursor, 3)
            s1 = round(cursor + dur_s, 3)
            spans.append(
                {
                    "sentence_index": idx,
                    "speaker": "narrator",
                    "start_sec": s0,
                    "end_sec": s1,
                    "duration_sec": round(s1 - s0, 3),
                    "text": sentences[idx - 1],
                    "display_text": sentences[idx - 1],
                }
            )
            cursor = round(s1 + (0.08 if idx < n_cuts else 0.0), 3)

        total_dur = round(spans[-1]["end_sec"] + 0.20, 3)
        voice_report = {
            "fps": 30,
            "speech_end_sec": spans[-1]["end_sec"],
            "total_duration_sec": total_dur,
            "sentence_spans": spans,
        }
        (proj_dir / "04_audio" / "voice_report.json").write_text(json.dumps(voice_report, indent=2), encoding="utf-8")

        # Confirm 0 MP4s exist on disk before calling helper
        assert list((proj_dir / "03_visuals").rglob("*.mp4")) == []

        res = compute_locked_edl_cut_frame_requirements(proj_dir, safety_pad_frames=6)
        assert res["fps"] == 30
        assert res["total_frames"] == int(round(total_dur * 30))
        assert abs(res["total_duration_sec"] - round(res["total_frames"] / 30.0, 3)) < 1e-6
        assert len(res["cuts"]) == n_cuts

        fmap = res["edl_frame_map"]
        assert set(fmap.keys()) == set(range(1, n_cuts + 1))
        assert all(isinstance(k, int) and isinstance(v, int) and v >= 30 for k, v in fmap.items())

        cuts_by_clip = {int(c["clip_index"]): c for c in res["cuts"]}
        # Clip 1 transitions into Clip 2 with portal_crash_zoom_10f -> eff_f + 10 + 6
        c1 = cuts_by_clip[1]
        if str(c1.get("transition_out") or "").lower() == "portal_crash_zoom_10f":
            assert fmap[1] == int(c1["frames"]) + 10 + 6
        # Clip 2 is a hard/action_impact cut -> eff_f + 0 + 6
        c2 = cuts_by_clip[2]
        if str(c2.get("transition_out") or "").lower() in ("", "hard", "action_impact_cut"):
            assert fmap[2] == int(c2["frames"]) + 6

        # Passing explicit tts_res produces identical frame requirements
        res_explicit = compute_locked_edl_cut_frame_requirements(proj_dir, tts_res=voice_report, safety_pad_frames=6)
        assert res_explicit["edl_frame_map"] == fmap



class TestGuard5MaxRamOomHeadroomAndSinglePassMp4Session:
    """Guard 5: 64GB Max-RAM (`MemAvailable >= 12 GiB` OOM guard) + Single-Pass `cv2.VideoCapture` MP4 Scanner."""

    def test_mem_available_12gib_oom_headroom_and_zero_swap_boundary(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from pipeline.hardware_profile import (
            AAB_MIN_MEM_AVAILABLE_HEADROOM_BYTES,
            read_mem_available_bytes,
            resolve_dynamic_ram_budget_bytes,
        )

        assert AAB_MIN_MEM_AVAILABLE_HEADROOM_BYTES == 12 * 1024**3

        # Live host telemetry check
        live_avail = read_mem_available_bytes()
        assert live_avail > 0

        # 52 GiB available -> 40 GiB usable pool
        monkeypatch.setenv("AAB_MEM_AVAILABLE_BYTES_OVERRIDE", str(52 * 1024**3))
        assert resolve_dynamic_ram_budget_bytes() == 40 * 1024**3

        # Boundary: exactly 12 GiB available -> 0 B pool (protects 0B-Swap host from OOM)
        monkeypatch.setenv("AAB_MEM_AVAILABLE_BYTES_OVERRIDE", str(12 * 1024**3))
        assert resolve_dynamic_ram_budget_bytes() == 0

        # Below 12 GiB (8 GiB) -> clamped to 0 B (never negative)
        monkeypatch.setenv("AAB_MEM_AVAILABLE_BYTES_OVERRIDE", str(8 * 1024**3))
        assert resolve_dynamic_ram_budget_bytes() == 0

    def test_single_pass_mp4_session_opens_videocapture_once_and_frees_ram_on_exit(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import cv2
        import numpy as np
        from pipeline.media_cache import decode_needed_frames, shared_mp4_decode_session
        from pipeline.posthoc_qa import evaluate_cut_temporal_smoothness
        from pipeline.media_probe import VideoAutopsyEngine

        mp4_p = tmp_path / "single_pass_test.mp4"
        w, h, fps = 180, 320, 30.0
        writer = cv2.VideoWriter(str(mp4_p), cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
        for i in range(45):
            frm = np.full((h, w, 3), 40 + (i * 3) % 180, dtype=np.uint8)
            cv2.circle(frm, (40 + i * 2, 160), 22, (240, 220, 90), -1)
            writer.write(frm)
        writer.release()

        monkeypatch.setenv("AAB_SCRATCH_DIR", str(tmp_path / "shm_scratch"))
        monkeypatch.setenv("AAB_SPEED_CACHE_DIR", str(tmp_path / "shm_scratch" / "speed_cache"))
        monkeypatch.setenv("AAB_MEM_AVAILABLE_BYTES_OVERRIDE", str(48 * 1024**3))
        real_vc = cv2.VideoCapture
        vc_calls: list[str] = []

        def _spy_vc(*args: Any, **kwargs: Any) -> Any:
            vc_calls.append(str(args[0]) if args else "")
            return real_vc(*args, **kwargs)

        cuts_spec = [
            {"cut_index": 1, "out_start_sec": 0.0, "out_end_sec": 0.75, "camera_move": "push_in_slow", "grammar": "expressive_vinyl_world"},
            {"cut_index": 2, "out_start_sec": 0.75, "out_end_sec": 1.50, "camera_move": "pull_back_slow", "grammar": "expressive_xray_brain"},
        ]
        with patch("cv2.VideoCapture", side_effect=_spy_vc):
            with shared_mp4_decode_session(mp4_p) as sess:
                assert sess["all_frames_cached"] is True
                assert sess["decoded_fc"] == 45
                assert len(sess["grays_270x480"]) == 45
                assert len(sess["flicker_64x36"]) == 45

                _, fc_d, f_map = decode_needed_frames(sess["local_mp4"], sess["sha256"], {0, 15, 30, 44})
                assert fc_d == 45 and set(f_map.keys()) == {0, 15, 30, 44}

                sm_rep = evaluate_cut_temporal_smoothness(mp4_p, cuts_spec)
                assert set(sm_rep.keys()) == {1, 2}

                vs_rep = VideoAutopsyEngine.inspect_video_stream(mp4_p, expected_duration_sec=1.5)
                assert vs_rep["decoded_frame_count"] == 45

            # All frame buffers MUST be cleared immediately on context exit
            assert sess["frames"] == {}
            assert sess["even_small_bgr"] == {}
            assert sess["grays_270x480"] == []
            assert sess["flicker_64x36"] == []

        assert len(vc_calls) == 1, f"Expected single VideoCapture pass, got {len(vc_calls)}: {vc_calls}"


class TestGuard6EpisodeRunnerAndWorkflowStateMachine:
    """Guard 6: `pipeline.episode_runner` (`main.py ep`) & `workflows/produce_episode.py` state machine."""

    def test_episode_status_ladder_and_published_mutation_guard(self, tmp_path: Path) -> None:
        from pipeline.episode_runner import get_episode_status, run_episode_until

        missing = get_episode_status(str(tmp_path / "does_not_exist"))
        assert missing["exists"] is False and missing["stage"] == "missing"

        with pytest.raises(FileNotFoundError):
            run_episode_until(str(tmp_path / "does_not_exist"))

        proj = tmp_path / "v8_ep99_runner_test"
        (proj / "02_script").mkdir(parents=True)
        (proj / "03_visuals").mkdir(parents=True)
        (proj / "05_assembly").mkdir(parents=True)
        (proj / "06_publish").mkdir(parents=True)
        (proj / "02_script" / "script.json").write_text(
            json.dumps({"sentences": [{"text": "Hook line."}, {"text": "Second line."}]}), encoding="utf-8"
        )
        (proj / "03_visuals" / "visual_plan.json").write_text(
            json.dumps({"clips": [{"clip_number": 1}, {"clip_number": 2}]}), encoding="utf-8"
        )

        st1 = get_episode_status(str(proj))
        assert st1["exists"] is True and st1["stage"] == "script_and_plan_ready"

        # Simulate Gate 2 passed without root MP4 yet -> gate2_passed_pending_packaging (not script_and_plan_ready!)
        (proj / "05_assembly" / "final_shorts_1080x1920.mp4").write_bytes(b"0" * 600_000)
        (proj / "05_assembly" / "dynamic_episode_qa_report.json").write_text(json.dumps({"passed": True}), encoding="utf-8")
        (proj / "05_assembly" / "video_autopsy_report.json").write_text(json.dumps({"passed": True}), encoding="utf-8")
        (proj / "05_assembly" / "posthoc_semantic_qa_report.json").write_text(
            json.dumps({"cv_passed": True, "passed": True}), encoding="utf-8"
        )
        st2 = get_episode_status(str(proj))
        assert st2["stage"] == "gate2_passed_pending_packaging"

        # Published project MUST refuse mutation in run_episode_until
        (proj / "06_publish" / "upload_receipt.json").write_text(
            json.dumps({"video_id": "abc123XYZ", "visibility": "PUBLIC"}), encoding="utf-8"
        )
        st3 = get_episode_status(str(proj))
        assert st3["stage"] == "published:PUBLIC"
        with pytest.raises(RuntimeError, match="Refusing to mutate published project"):
            run_episode_until(str(proj), until="gate1")

        # CLI `main.py ep status` exits cleanly on existing project and raises SystemExit(1) on missing project
        import sys
        import pipeline.cli as cli_mod
        old_argv = sys.argv
        try:
            sys.argv = ["main.py", "ep", "status", str(proj)]
            assert cli_mod.main() in (0, None)
            sys.argv = ["main.py", "ep", "status", str(tmp_path / "missing_xyz")]
            with pytest.raises(SystemExit) as exc_info:
                cli_mod.main()
            assert exc_info.value.code == 1
        finally:
            sys.argv = old_argv

    def test_episode_runner_gate2_resume_preserves_signed_mp4_sha_and_writes_verify_receipt(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        Regression test for `run_episode_until(..., until="ready")` after Gate 2 sign-off:
          - Must NOT re-run `assemble_diorama_project` when `final_shorts_1080x1920.mp4` already exists and
            `pending_flow` is False (otherwise re-encoding invalidates the signed `posthoc_semantic_review.json` SHA).
          - Must check `run_thumbnail_studio` pass status, sync `00_project_manifest.json` from disk, verify
            `all_intact == True`, and write `05_assembly/ceo_verify_receipt.json`.
        """
        import pipeline.assembler as asm_mod
        import pipeline.batch_runner as br_mod
        import pipeline.cli as cli_mod
        import pipeline.episode_qa as eq_mod
        import pipeline.episode_runner as er_mod
        import pipeline.media_probe as mp_mod
        import pipeline.posthoc_qa as ph_mod
        import pipeline.prompt_builder as pb_mod
        import pipeline.prompt_gate as pg_mod
        import pipeline.ref_qa as rq_mod
        import pipeline.reference_pack as rp_mod
        import pipeline.thumbnail as th_mod

        monkeypatch.setenv("AAB_SCRATCH_DIR", str(tmp_path / "shm_scratch"))
        monkeypatch.setenv("AAB_SPEED_CACHE_DIR", str(tmp_path / "shm_scratch" / "speed_cache"))

        projects_root = tmp_path / "projects"
        proj = projects_root / "v8_ep98_gate2_resume"
        for sub in ("02_script", "03_visuals/reference_images", "03_visuals/flow_native_clips", "04_audio", "05_assembly", "06_publish"):
            (proj / sub).mkdir(parents=True, exist_ok=True)
        (proj / "02_script" / "script.json").write_text(
            json.dumps({"title": "Why Sleep Washes Your Brain", "pillar": "brain_health", "sentences": ["Line 1.", "Line 2."]}),
            encoding="utf-8",
        )
        (proj / "03_visuals" / "visual_plan.json").write_text(
            json.dumps({"clips": [{"clip_number": 1, "scene": "clean studio"}, {"clip_number": 2, "scene": "clean lab"}]}),
            encoding="utf-8",
        )
        # Partial reference pack: 1 PNG exists, but cv_pre_generation_ready is initially False -> must still invoke ensure_porcelain_reference_pack!
        (proj / "03_visuals" / "reference_images" / "ref_01.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 128)
        (proj / "04_audio" / "audio_master.wav").write_bytes(b"RIFF" + b"0" * 256)
        final_mp4 = proj / "05_assembly" / "final_shorts_1080x1920.mp4"
        final_mp4.write_bytes(b"SIGNED_MP4_BYTES_" + b"X" * 60_000)
        orig_mp4_bytes = final_mp4.read_bytes()

        monkeypatch.setattr(
            cli_mod,
            "_load_gate_inputs",
            lambda _d: (
                {"style_profile": "expressive_25d_v8", "clips": []},
                ["Line 1.", "Line 2."],
                {"style_profile": "expressive_25d_v8", "title": "Why Sleep Washes Your Brain", "pillar": "brain_health"},
            ),
        )
        monkeypatch.setattr(pb_mod, "build_flow_prompts", lambda _p, _n: [{"clip_number": 1, "scene": "clean studio"}])
        monkeypatch.setattr(pg_mod, "validate_production_diorama_v6", lambda *_a, **_kw: [])
        monkeypatch.setattr(pb_mod, "validate_flow_credit_safety_lint", lambda *_a, **_kw: [])
        monkeypatch.setattr(pb_mod, "is_diorama_v6_plan", lambda *_a, **_kw: True)
        monkeypatch.setattr(eq_mod, "write_episode_qa_contract", lambda *_a, **_kw: (proj / "03_visuals" / "episode_qa_contract.json", {}))

        ensure_calls: list[Path] = []
        monkeypatch.setattr(rp_mod, "ensure_porcelain_reference_pack", lambda p_d, **_kw: ensure_calls.append(Path(p_d)) or {"pre_generation_ready": True})
        rq_iter = iter([
            {"cv_pre_generation_ready": False, "pre_generation_ready": False},
            {"cv_pre_generation_ready": True, "pre_generation_ready": True, "regenerate_image_ids": []},
        ])
        monkeypatch.setattr(rq_mod, "inspect_reference_image_pack", lambda *_a, **_kw: next(rq_iter))
        monkeypatch.setattr(er_mod, "has_pending_human_flow_clips", lambda *_a, **_kw: (False, 0))
        monkeypatch.setattr(asm_mod, "verify_script_audio_freshness", lambda *_a, **_kw: {"fresh": True})

        assemble_calls: list[Path] = []
        monkeypatch.setattr(asm_mod, "assemble_diorama_project", lambda p_d, **_kw: assemble_calls.append(Path(p_d)) or {"final_mp4": str(final_mp4)})
        monkeypatch.setattr(ph_mod, "run_posthoc_semantic_qa", lambda *_a, **_kw: {"cv_passed": True, "passed": True, "viewer_sheets": []})
        monkeypatch.setattr(eq_mod, "verify_final_mp4_against_contract", lambda *_a, **_kw: {"passed": True})
        monkeypatch.setattr(mp_mod.VideoAutopsyEngine, "inspect_project", classmethod(lambda cls, *_a, **_kw: {"passed": True}))
        def _stub_thumb(p_d: Path, **_kw: Any) -> dict[str, Any]:
            (Path(p_d) / "06_publish" / "thumbnail_report.json").write_text('{"passed": true}', encoding="utf-8")
            return {"passed": True}

        monkeypatch.setattr(th_mod, "run", _stub_thumb)

        res = er_mod.run_episode_until(str(proj), until="ready")
        assert len(ensure_calls) == 1, "Partial ref pack with cv_pre_generation_ready=False must call ensure_porcelain_reference_pack"
        assert assemble_calls == [], "Already-assembled & fresh MP4 must NOT be re-encoded on Gate 2 resume"
        assert final_mp4.read_bytes() == orig_mp4_bytes
        assert res["status"] == "READY_TO_PUBLISH"
        assert res["all_intact"] is True
        assert (projects_root / "final_shorts_v8_ep98_gate2_resume.mp4").read_bytes() == orig_mp4_bytes
        assert (proj / "05_assembly" / "ceo_verify_receipt.json").is_file()


    def test_episode_runner_auto_renders_r88a_and_r89_archival_clips(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import pipeline.archival_insert as ai_mod
        import pipeline.archival_video as av_mod
        import pipeline.assembler as asm_mod
        import pipeline.cli as cli_mod
        import pipeline.episode_qa as eq_mod
        import pipeline.episode_runner as er_mod
        import pipeline.media_probe as mp_mod
        import pipeline.posthoc_qa as ph_mod
        import pipeline.prompt_builder as pb_mod
        import pipeline.prompt_gate as pg_mod
        import pipeline.ref_qa as rq_mod

        proj = tmp_path / "projects" / "v8_ep99_r88a_r89_wiring"
        for sub in ("02_script", "03_visuals/reference_images", "03_visuals/flow_native_clips", "04_audio", "05_assembly", "06_publish"):
            (proj / sub).mkdir(parents=True, exist_ok=True)
        (proj / "02_script" / "script.json").write_text(json.dumps({"title": "Sleep Pupil Arousal", "pillar": "brain_health", "sentences": ["S1.", "S2."]}), encoding="utf-8")
        (proj / "03_visuals" / "visual_plan.json").write_text(json.dumps({"clips": [{"clip_number": 1, "scene": "lab"}]}), encoding="utf-8")
        (proj / "03_visuals" / "reference_images" / "ref_01.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 64)
        (proj / "03_visuals" / "archival_inserts_manifest.json").write_text(json.dumps({"inserts": [{"clip_number": 2}]}), encoding="utf-8")
        (proj / "03_visuals" / "archival_videos_manifest.json").write_text(json.dumps({"videos": [{"clip_number": 3}]}), encoding="utf-8")
        (proj / "04_audio" / "audio_master.wav").write_bytes(b"RIFF" + b"0" * 128)
        final_mp4 = proj / "05_assembly" / "final_shorts_1080x1920.mp4"

        monkeypatch.setattr(cli_mod, "_load_gate_inputs", lambda _d: ({"style_profile": "expressive_25d_v8", "clips": []}, ["S1.", "S2."], {"style_profile": "expressive_25d_v8"}))
        monkeypatch.setattr(pb_mod, "build_flow_prompts", lambda _p, _n: [{"clip_number": 1, "scene": "lab"}])
        monkeypatch.setattr(pg_mod, "validate_production_diorama_v6", lambda *_a, **_kw: [])
        monkeypatch.setattr(pb_mod, "validate_flow_credit_safety_lint", lambda *_a, **_kw: [])
        monkeypatch.setattr(pb_mod, "is_diorama_v6_plan", lambda *_a, **_kw: True)
        monkeypatch.setattr(eq_mod, "write_episode_qa_contract", lambda *_a, **_kw: (proj / "03_visuals" / "episode_qa_contract.json", {}))
        monkeypatch.setattr(rq_mod, "inspect_reference_image_pack", lambda *_a, **_kw: {"cv_pre_generation_ready": True, "pre_generation_ready": True, "regenerate_image_ids": []})
        monkeypatch.setattr(er_mod, "has_pending_human_flow_clips", lambda *_a, **_kw: (False, 0))
        monkeypatch.setattr(asm_mod, "verify_script_audio_freshness", lambda *_a, **_kw: {"fresh": True})

        r88a_calls: list[Path] = []
        r89_calls: list[Path] = []
        monkeypatch.setattr(ai_mod, "render_archival_insert_clips", lambda p_d, **_kw: r88a_calls.append(Path(p_d)) or {"rendered": [2]})
        monkeypatch.setattr(av_mod, "render_archival_video_clips", lambda p_d, **_kw: r89_calls.append(Path(p_d)) or {"rendered": [3]})
        def _fake_assemble(_d: object, **_kw: object) -> dict[str, str]:
            final_mp4.write_bytes(b"MP4" * 20_000)
            return {"final_mp4": str(final_mp4)}

        monkeypatch.setattr(asm_mod, "assemble_diorama_project", _fake_assemble)
        monkeypatch.setattr(ph_mod, "run_posthoc_semantic_qa", lambda *_a, **_kw: {"cv_passed": True, "passed": False, "viewer_sheets": []})
        monkeypatch.setattr(eq_mod, "verify_final_mp4_against_contract", lambda *_a, **_kw: {"passed": True})
        monkeypatch.setattr(mp_mod.VideoAutopsyEngine, "inspect_project", classmethod(lambda cls, *_a, **_kw: {"passed": True}))

        res = er_mod.run_episode_until(str(proj), until="gate2")
        assert len(r88a_calls) == 1 and r88a_calls[0] == proj
        assert len(r89_calls) == 1 and r89_calls[0] == proj
        assert res["status"] == "PAUSED_AT_GATE2"
