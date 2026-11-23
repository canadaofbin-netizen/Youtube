from __future__ import annotations

import concurrent.futures
import json
import os
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest

import pipeline.brain_simulator_blender as bsb
import pipeline.diorama_batch_orchestrator as dbo
import pipeline.diorama_pipeline_runner as dpr
import pipeline.flow_diorama_sharded_worker as fdsw
from pipeline.hardware_profile import resolve_blender_parallel_plan, resolve_cpu_budget


def test_blender_parallel_plan_8core_and_6core(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("os.cpu_count", lambda: 8)
    assert resolve_blender_parallel_plan(8, overlapped=False, threads_per_worker=2) == (4, 2)
    assert resolve_blender_parallel_plan(6, overlapped=True, threads_per_worker=2) == (3, 2)
    assert resolve_blender_parallel_plan(None, overlapped=True, threads_per_worker=2) == (3, 2)
    assert resolve_blender_parallel_plan(8, overlapped=False, threads_per_worker=2, clip_count=2) == (2, 2)


def test_render_brain_simulator_clip_threads_guard1_and_sha256_cache_skip(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, Any]] = []
    fake_blender = tmp_path / "fake_blender"
    fake_blender.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    fake_blender.chmod(0o755)
    monkeypatch.setattr(bsb, "_find_blender_bin", lambda: fake_blender)

    def _fake_subprocess_run(cmd: list[str], **kwargs: Any) -> SimpleNamespace:
        env = kwargs.get("env") or {}
        script_path = Path(cmd[-1])
        calls.append({"cmd": list(cmd), "env": dict(env), "script_dir": str(script_path.parent)})
        frames_dir = script_path.parent / "frames"
        n_f = int(json.loads((script_path.parent / "render_cfg.json").read_text(encoding="utf-8"))["n_frames"])
        for i in range(n_f):
            (frames_dir / f"frame_{i:04d}.png").write_bytes(b"PNG_STUB")
        track_doc = {
            "schema": 1,
            "width": 540,
            "height": 960,
            "fps": 30.0,
            "n_frames": n_f,
            "start_region": "eyes",
            "end_region": "primary visual cortex",
            "neural_state": "active",
            "frames": [{"frame": i, "t_sec": round(i / 30.0, 4), "anchors": {}} for i in range(n_f)],
        }
        (script_path.parent / "clip_5_camera_track.json").write_text(json.dumps(track_doc), encoding="utf-8")
        return SimpleNamespace(returncode=0, stdout="OK", stderr="")

    encode_threads_seen: list[int] = []

    def _fake_encode(
        frame_files: list[Path],
        out_mp4: Path,
        *,
        width: int,
        height: int,
        fps: int,
        threads: int = 2,
    ) -> dict[str, Any]:
        encode_threads_seen.append(int(threads))
        out_mp4.write_bytes(b"\x00" * 64_000)
        return {"passed": True, "mean_luma": 28.0}

    monkeypatch.setattr(bsb.subprocess, "run", _fake_subprocess_run)
    monkeypatch.setattr(bsb, "_composite_and_encode_frames", _fake_encode)
    monkeypatch.setattr(
        bsb,
        "evaluate_simulator_qa",
        lambda **_kw: {"passed": True, "gates": {"SQ1": True, "SQ2": True}},
    )

    out_mp4 = tmp_path / "03_visuals" / "brain_simulator_clips" / "clip_5.mp4"
    spec = {
        "grammar": "brain_simulator_3d",
        "render_engine": "blender_3d_simulator",
        "camera_move": "sensory_to_brain_drone",
        "start_brain_region": "eyes",
        "end_brain_region": "primary visual cortex",
        "neural_state": "active",
        "n_frames": 66,
    }

    res1 = bsb.render_brain_simulator_clip(
        shot_spec=spec,
        out_mp4_path=out_mp4,
        width=540,
        height=960,
        fps=30,
        threads=2,
        force=False,
    )
    assert res1["cached"] is False
    assert res1["n_frames"] == 66
    assert len(calls) == 1
    assert encode_threads_seen == [2]

    # Verify Mesa llvmpipe + Blender CLI thread locks & /dev/shm scratch root
    c0 = calls[0]
    assert "-t" in c0["cmd"]
    t_idx = c0["cmd"].index("-t")
    assert c0["cmd"][t_idx + 1] == "2"
    assert c0["env"]["LP_NUM_THREADS"] == "2"
    assert c0["env"]["OMP_NUM_THREADS"] == "2"
    assert c0["env"]["MKL_NUM_THREADS"] == "1"
    assert c0["env"]["OPENBLAS_NUM_THREADS"] == "1"
    assert c0["env"]["GALLIUM_THREAD"] == "0"
    if Path("/dev/shm").is_dir():
        assert c0["script_dir"].startswith("/dev/shm/")

    qa_path = out_mp4.with_name("clip_5_sim_qa.json")
    track_path = out_mp4.with_name("clip_5_camera_track.json")
    assert out_mp4.is_file() and qa_path.is_file() and track_path.is_file()
    qa_doc = json.loads(qa_path.read_text(encoding="utf-8"))
    assert qa_doc["sim_spec_sha256"] == res1["sim_spec_sha256"]
    assert qa_doc["threads"] == 2

    # Second call with identical spec must hit 0.0s SHA-256 skip cache without invoking Blender
    t_skip0 = time.perf_counter()
    res2 = bsb.render_brain_simulator_clip(
        shot_spec=spec,
        out_mp4_path=out_mp4,
        width=540,
        height=960,
        fps=30,
        threads=2,
        force=False,
    )
    skip_dt = time.perf_counter() - t_skip0
    assert res2["cached"] is True
    assert skip_dt < 0.1
    assert len(calls) == 1

    # Requiring MORE frames than cached (`n_frames=90 > 66`) must invalidate cache & re-render
    res3 = bsb.render_brain_simulator_clip(
        shot_spec={**spec, "n_frames": 90},
        out_mp4_path=out_mp4,
        width=540,
        height=960,
        fps=30,
        threads=2,
        force=False,
    )
    assert res3["cached"] is False
    assert res3["n_frames"] == 90
    assert len(calls) == 2


def test_flow_sharded_worker_excludes_r76_brain_simulator_clips(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import asyncio

    p_dir = tmp_path / "r76_sim_only_proj"
    (p_dir / "02_script").mkdir(parents=True)
    (p_dir / "03_visuals").mkdir(parents=True)
    vp = {
        "schema": 8,
        "style_profile": "expressive_25d_v8",
        "fps": 30,
        "clips": [
            {"clip_number": 1, "grammar": "brain_simulator_3d", "render_engine": "blender_3d_simulator"},
            {"clip_number": 2, "grammar": "brain_simulator_3d", "render_engine": "blender_3d_simulator"},
        ],
    }
    (p_dir / "03_visuals" / "visual_plan.json").write_text(json.dumps(vp), encoding="utf-8")

    monkeypatch.setattr(fdsw, "load_diorama_script_sentences", lambda _d: (["Sentence one.", "Sentence two."], {}))
    monkeypatch.setattr(
        fdsw,
        "build_diorama_v6_prompts",
        lambda _vp, _s: [
            {"clip_number": 1, "grammar": "brain_simulator_3d", "prompt": "p1"},
            {"clip_number": 2, "grammar": "brain_simulator_3d", "prompt": "p2"},
        ],
    )
    monkeypatch.setattr(fdsw, "write_flow_prompts_json", lambda *_a, **_k: None)
    monkeypatch.setattr(
        "pipeline.dynamic_episode_qa.write_episode_qa_contract",
        lambda *_a, **_k: (p_dir / "03_visuals" / "episode_qa_contract.json", {}),
    )

    rcpt = asyncio.run(fdsw.run_sharded_diorama_flow_generation(p_dir, include_brain_simulator_clips=False))
    assert rcpt["brain_simulator_3d_only"] is True
    assert rcpt["prompts_submitted_count"] == 0
    assert rcpt["excluded_brain_simulator_clips"] == [1, 2]
    assert not (p_dir / "03_visuals" / "flow_provenance_receipt.json").exists()


def test_guard3_worker_thread_pinning_and_cpu_budget_6_to_8_promotion(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(dbo, "PROJECTS_DIR", tmp_path)
    monkeypatch.setattr(dpr, "PROJECTS_DIR", tmp_path)
    monkeypatch.setattr(dpr, "BATCH_STATUS_PATH", tmp_path / "batch_status.json")
    monkeypatch.setattr("os.cpu_count", lambda: 8)

    for pid in ("ep_a", "ep_b"):
        p_dir = tmp_path / pid
        (p_dir / "02_script").mkdir(parents=True)
        (p_dir / "03_visuals" / "flow_native_clips").mkdir(parents=True)
        (p_dir / "05_assembly").mkdir(parents=True)
        vp = {
            "schema": 8,
            "style_profile": "porcelain_cinematic_v7",
            "fps": 30,
            "clips": [{"clip_number": 1, "grammar": "porcelain_human_action", "duration_sec": 4.0}],
        }
        (p_dir / "03_visuals" / "visual_plan.json").write_text(json.dumps(vp), encoding="utf-8")

    # 1. Verify _assembly_worker_entry pins inner threads to 1 and forwards cpu_budget + preserve_audio_master
    captured_fin_calls: list[dict[str, Any]] = []

    def _fake_finalize(
        project_id: str,
        voice_preset: str | None = None,
        prosody_mode: str | None = None,
        *,
        cpu_budget: int | None = None,
        preserve_audio_master: bool = False,
    ) -> dict[str, Any]:
        captured_fin_calls.append(
            {
                "project_id": project_id,
                "cpu_budget": cpu_budget,
                "preserve_audio_master": preserve_audio_master,
                "omp": os.environ.get("OMP_NUM_THREADS"),
                "mkl": os.environ.get("MKL_NUM_THREADS"),
                "openblas": os.environ.get("OPENBLAS_NUM_THREADS"),
            }
        )
        return {
            "project_id": project_id,
            "completed_mp4": str(tmp_path / f"final_{project_id}.mp4"),
            "duration_sec": 68.0,
            "cut_count": 16,
        }

    monkeypatch.setattr(dpr, "finalize_and_verify_diorama_project", _fake_finalize)
    monkeypatch.setattr(dpr, "_is_already_completed", lambda _pid: False)
    monkeypatch.setattr(
        dpr,
        "precheck_diorama_project",
        lambda sp, **_k: {
            "project_id": sp["project_id"],
            "passed": True,
            "sentences": 12,
            "clips": 16,
            "words": 150,
            "tts_duration_sec": 68.0,
            "issues": [],
        },
    )
    monkeypatch.setattr(dpr, "sync_project_from_dossier_diorama", lambda *_a, **_k: None)
    monkeypatch.setattr(
        dpr,
        "lock_episode_audio_and_edl_frames",
        lambda p_dir, **_k: {"edl_frame_map": {1: 126}, "project_dir": str(p_dir)},
    )
    monkeypatch.setattr("pipeline.porcelain_anchor_pack.ensure_porcelain_reference_pack", lambda *_a, **_k: {"pre_generation_ready": True})

    async def _fake_flow_gen(**kwargs: Any) -> dict[str, Any]:
        return {"project_id": kwargs["project_id"], "clips": []}

    monkeypatch.setattr(dpr, "run_sharded_diorama_flow_generation", _fake_flow_gen)

    # Use in-process ThreadPoolExecutor in place of ProcessPoolExecutor so monkeypatches apply cleanly
    class _InProcPool(concurrent.futures.ThreadPoolExecutor):
        def __init__(self, max_workers: int = 1, mp_context: Any = None) -> None:
            super().__init__(max_workers=max_workers)

    monkeypatch.setattr(dpr.concurrent.futures, "ProcessPoolExecutor", _InProcPool)

    specs = [
        {"index": 1, "wave": 1, "project_id": "ep_a", "slug": "s_a", "pillar": "brain_basics"},
        {"index": 2, "wave": 1, "project_id": "ep_b", "slug": "s_b", "pillar": "brain_health"},
    ]
    res = dpr.run_diorama_pipeline(specs, force_regenerate=True)
    assert res["completed_in_run"] == 2
    assert len(captured_fin_calls) == 2

    # Ep A submitted while Ep B remained in flow_queue -> cpu_budget=6; Ep B submitted when flow_queue empty -> cpu_budget=8!
    assert captured_fin_calls[0]["project_id"] == "ep_a"
    assert captured_fin_calls[0]["cpu_budget"] == resolve_cpu_budget(overlapped=True) == 6
    assert captured_fin_calls[0]["preserve_audio_master"] is True
    assert captured_fin_calls[0]["omp"] == "1"
    assert captured_fin_calls[0]["mkl"] == "1"
    assert captured_fin_calls[0]["openblas"] == "1"

    assert captured_fin_calls[1]["project_id"] == "ep_b"
    assert captured_fin_calls[1]["cpu_budget"] == resolve_cpu_budget(overlapped=False) == 8
    assert captured_fin_calls[1]["preserve_audio_master"] is True


def test_guard4_tts_edl_lock_strictly_before_concurrent_fork_and_preserve_audio_join(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(dbo, "PROJECTS_DIR", tmp_path)
    monkeypatch.setattr("os.cpu_count", lambda: 8)

    pid = "ep_guard4_r76"
    p_dir = tmp_path / pid
    (p_dir / "02_script").mkdir(parents=True)
    (p_dir / "03_visuals" / "flow_native_clips").mkdir(parents=True)
    (p_dir / "04_audio").mkdir(parents=True)
    (p_dir / "05_assembly").mkdir(parents=True)

    vp = {
        "schema": 8,
        "style_profile": "expressive_25d_v8",
        "fps": 30,
        "clips": [
            {"clip_number": 1, "grammar": "vinyl_figure_diorama", "duration_sec": 3.5, "transition_out": "portal_crash_zoom_10f"},
            {"clip_number": 2, "grammar": "brain_simulator_3d", "render_engine": "blender_3d_simulator", "duration_sec": 4.0},
        ],
    }
    (p_dir / "03_visuals" / "visual_plan.json").write_text(json.dumps(vp), encoding="utf-8")

    timeline: dict[str, Any] = {}

    monkeypatch.setattr(
        "pipeline.porcelain_anchor_pack.ensure_porcelain_reference_pack",
        lambda *_a, **_k: {"pre_generation_ready": True},
    )
    monkeypatch.setattr(dbo, "render_keyframe_contact_sheet", lambda *_a, **_k: None)
    monkeypatch.setattr(dbo, "load_diorama_script_sentences", lambda _d: (["First sentence!", "Second sentence."], {}))

    def _fake_tts(**_kwargs: Any) -> dict[str, Any]:
        timeline["tts_start"] = time.monotonic()
        time.sleep(0.03)
        timeline["tts_end"] = time.monotonic()
        return {
            "sentence_spans": [
                {"sentence_index": 1, "start_sec": 0.0, "end_sec": 3.5},
                {"sentence_index": 2, "start_sec": 3.5, "end_sec": 7.7},
            ],
            "events": [],
            "speech_end_sec": 7.7,
            "total_duration_sec": 8.0,
            "sr": 48000,
            "pcm": None,
        }

    monkeypatch.setattr(dbo, "synthesize_continuous_diorama_track", _fake_tts)

    async def _fake_flow(**kwargs: Any) -> dict[str, Any]:
        timeline["flow_start"] = time.monotonic()
        timeline["lock_exists_at_flow_start"] = (p_dir / "05_assembly" / "edl_timing_lock.json").is_file()
        timeline["wav_exists_at_flow_start"] = (p_dir / "04_audio" / "audio_master.wav").is_file()
        timeline["flow_include_sim"] = kwargs.get("include_brain_simulator_clips")
        await __import__("asyncio").sleep(0.14)
        timeline["flow_end"] = time.monotonic()
        return {"project_id": pid, "clips": []}

    def _fake_blender_parallel(
        proj_d: Path,
        *,
        edl_frame_map: dict[int, int] | None = None,
        cpu_budget: int | None = None,
        overlapped: bool = False,
        threads_per_worker: int = 2,
        force: bool = False,
    ) -> dict[str, Any]:
        timeline["sim_start"] = time.monotonic()
        timeline["lock_exists_at_sim_start"] = (Path(proj_d) / "05_assembly" / "edl_timing_lock.json").is_file()
        timeline["sim_edl_frame_map"] = dict(edl_frame_map or {})
        timeline["sim_overlapped"] = overlapped
        time.sleep(0.14)
        timeline["sim_end"] = time.monotonic()
        return {"all_passed": True, "n_workers": 3, "threads_per_worker": threads_per_worker}

    def _fake_finalize(
        project_id: str,
        voice_preset: str | None = None,
        prosody_mode: str | None = None,
        *,
        cpu_budget: int | None = None,
        preserve_audio_master: bool = False,
    ) -> dict[str, Any]:
        timeline["finalize_start"] = time.monotonic()
        timeline["finalize_preserve_audio_master"] = preserve_audio_master
        timeline["finalize_cpu_budget"] = cpu_budget
        return {"project_id": project_id, "passed": True}

    monkeypatch.setattr(dbo, "run_sharded_diorama_flow_generation", _fake_flow)
    monkeypatch.setattr(dbo, "render_project_brain_simulator_clips_parallel", _fake_blender_parallel)
    monkeypatch.setattr(dbo, "finalize_and_verify_diorama_project", _fake_finalize)

    fin = dbo.generate_and_finalize_diorama_episode(pid, clean_existing=True)
    assert fin["passed"] is True

    # 1. Step 1 strictly precedes both Fork branches
    assert timeline["tts_end"] <= timeline["flow_start"]
    assert timeline["tts_end"] <= timeline["sim_start"]
    assert timeline["lock_exists_at_flow_start"] is True
    assert timeline["wav_exists_at_flow_start"] is True
    assert timeline["lock_exists_at_sim_start"] is True
    assert timeline["flow_include_sim"] is False
    assert timeline["sim_overlapped"] is True
    assert 2 in timeline["sim_edl_frame_map"] and timeline["sim_edl_frame_map"][2] >= 60

    # 2. Step 2 Flow and Blender genuinely overlap in wall-clock time
    assert timeline["flow_start"] < timeline["sim_end"]
    assert timeline["sim_start"] < timeline["flow_end"]

    # 3. Step 3 Assembly starts strictly after BOTH branches join, preserving locked audio_master.wav
    assert max(timeline["flow_end"], timeline["sim_end"]) <= timeline["finalize_start"]
    assert timeline["finalize_preserve_audio_master"] is True
    assert timeline["finalize_cpu_budget"] == 8


def test_diorama_batch_defaults_to_overlapped_pipeline_and_supports_sequential_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_specs = [{"index": 1, "wave": 1, "project_id": "p1", "slug": "s1", "pillar": "brain_basics"}]
    monkeypatch.setattr(dbo, "select_batch_specs", lambda **_k: list(fake_specs))

    called_pipeline: list[dict[str, Any]] = []

    def _fake_pipeline(**kwargs: Any) -> dict[str, Any]:
        called_pipeline.append(kwargs)
        return {"mode": "pipeline", "completed_in_run": 1, "total_completed_overall": 1, "results": [{"project_id": "p1"}]}

    monkeypatch.setattr(dpr, "run_diorama_pipeline", _fake_pipeline)

    rep_pipe = dbo.run_diorama_batch(wave="1", sequential=False)
    assert rep_pipe["mode"] == "pipeline"
    assert len(called_pipeline) == 1
