"""
Master Plan Phase 1-5 Regression Suite (`tests/test_master_plan_regressions.py`):
1. C1 — FFmpeg `xfade` near-EOF + `v8_curve_ramp` frame count & full video duration == audio/container duration
2. C2 — Studio upload timeout / disabled-Done / click failure raises `RuntimeError` without writing `upload_receipt.json`
3. Phase 2 — Studio tab lease isolation (`WhaleSessionController.get_tab_target`, `open_leased_cdp_tab`, `cleanup_idle_whale_tabs`)
4. Phase 2 — `StagingQueueManager` locked atomic `save_queue` & `load_queue` refusal to wipe corrupt non-empty `staging_queue.json`
5. C3/C4 — `purge_reenactment_quarantine` empty-slug refusal + cross-slug isolation + `/tmp/aab_flow_cand_{slug}_{pid}_...`
6. Phase 2 — `precheck_diorama_project` (`--precheck-only`) zero writes to `research_dossiers/<slug>/` + `_is_already_completed` accepting `andrew_v8`
7. Phase 4 — `audit_workspace_hygiene` live repo pass + synthetic clutter detection
"""

from __future__ import annotations

import asyncio
import hashlib
import inspect
import json
import os
import subprocess
import urllib.request
from pathlib import Path
from typing import Any

import cv2
import imageio_ffmpeg
import numpy as np
import pytest

from pipeline import cdp_tab_lease as ctl
from pipeline import config as cfg
from pipeline import batch_runner as dbo
from pipeline import flow_worker as sw
from pipeline import research_dossier as rd
from pipeline.assembler import (
    _execute_xfade_batch_ffmpeg,
    _probe_segment_frame_count,
    _render_cut_segment,
)
from pipeline.archival_media import purge_reenactment_quarantine
from pipeline.storage import ProjectStorage
from pipeline.studio.config import STUDIO_SELECTORS
from pipeline.studio.watchdog import cleanup_idle_whale_tabs
from pipeline.studio.uploader import StudioUploader
from pipeline.studio.browser_session import WhaleSessionController
from scripts.workspace_hygiene import audit_workspace_hygiene


def _write_short_mp4(mp4_path: Path, n_frames: int, fps: int = 24, bgr: tuple[int, int, int] = (80, 120, 175)) -> Path:
    raw_avi = mp4_path.with_suffix(".avi")
    vw = cv2.VideoWriter(str(raw_avi), cv2.VideoWriter_fourcc(*"MJPG"), float(fps), (270, 480))
    for i in range(n_frames):
        frm = np.full((480, 270, 3), bgr, dtype=np.uint8)
        cv2.circle(frm, (70 + (i * 5) % 130, 200 + (i * 3) % 100), 28, (240, 240, 244), -1)
        vw.write(frm)
    vw.release()
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    subprocess.run(
        [ff, "-y", "-i", str(raw_avi), "-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p", str(mp4_path)],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    raw_avi.unlink(missing_ok=True)
    return mp4_path


def test_c1_xfade_near_eof_and_curve_ramp_preserves_full_duration(tmp_path: Path) -> None:
    """C1: Near-EOF source windows + v8_curve_ramp + xfade overlaps never truncate downstream cuts."""
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    fps = 30
    ov_frames = [8, 10, 0]  # Cut 1->2: 8f overlap, Cut 2->3: 10f overlap, Cut 3: final
    xf_kinds = ["fade", "wipeleft", "fade"]
    eff_frames = [60, 66, 54]  # Expected final timeline frames = 60 + 66 + 54 = 180f (6.00s @ 30fps)
    clips_by_num: dict[int, Path] = {}
    batch_inputs: list[tuple[Path, int, str, int]] = []

    for idx in range(3):
        # Source clip is only 2.25s (54 frames @ 24fps), and src_start_sec=0.80s is near EOF (only 1.45s raw left!)
        src_mp4 = _write_short_mp4(tmp_path / f"src_{idx + 1}.mp4", n_frames=54, fps=24, bgr=(60 + idx * 45, 95, 160))
        clips_by_num[idx + 1] = src_mp4
        seg_mp4 = tmp_path / f"seg_{idx + 1}.mp4"
        need_f = eff_frames[idx] + (ov_frames[idx] + 1 if ov_frames[idx] > 0 else 0)
        cut_spec: dict[str, Any] = {
            "cut_index": idx + 1,
            "clip_index": idx + 1,
            "mode": "single",
            "src_start_sec": 0.80,
            "src_end_sec": 2.35,  # intentionally exceeds 2.25s EOF to verify _clamp_source_window_to_eof + tpad clone
            "frames": eff_frames[idx],
            "v8_curve_ramp": True,
            "curve_nominal_frames": need_f,
        }
        _render_cut_segment(
            ff=ff,
            cut=cut_spec,
            clips_by_num=clips_by_num,
            out_seg=seg_mp4,
            fps=fps,
            preset="ultrafast",
            crf=22,
            cwd=tmp_path,
            override_frames=need_f,
        )
        probed_f = _probe_segment_frame_count(seg_mp4)
        assert probed_f >= need_f, f"Segment {idx + 1} truncated: probed {probed_f}f < needed {need_f}f"
        batch_inputs.append((seg_mp4, eff_frames[idx], xf_kinds[idx], ov_frames[idx]))

    merged_mp4 = tmp_path / "merged_xfade.mp4"
    probed_merged = _execute_xfade_batch_ffmpeg(
        ff=ff,
        batch_inputs=batch_inputs,
        out_path=merged_mp4,
        fps=fps,
        target_crf=22,
        burn_start_sec=0.0,
        cwd=tmp_path,
    )
    expected_total_f = sum(eff_frames)
    assert probed_merged == expected_total_f, (
        f"xfade merged video truncated or drifted: got {probed_merged}f vs expected {expected_total_f}f"
    )

    # Also verify _execute_xfade_batch_ffmpeg rejects truncated upstream input rather than silently dropping downstream cuts
    bad_inputs = [(batch_inputs[0][0], 75, "fade", 12), batch_inputs[1]]
    with pytest.raises(RuntimeError, match="frames"):
        _execute_xfade_batch_ffmpeg(
            ff=ff,
            batch_inputs=bad_inputs,
            out_path=tmp_path / "bad_xfade.mp4",
            fps=fps,
            burn_start_sec=0.0,
            cwd=tmp_path,
        )


def test_c2_uploader_aborts_on_step_or_timeout_without_false_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """C2: Failed R4 altered-content click or 180s upload stream timeout raises RuntimeError with zero upload_receipt.json."""

    async def _fast_sleep(_sec: float) -> None:
        return None

    monkeypatch.setattr("pipeline.studio.uploader.asyncio.sleep", _fast_sleep)
    monkeypatch.setattr("pipeline.cdp_tab_lease.enable_background_focus_emulation", lambda *_a, **_kw: _fast_sleep(0.0))

    storage = ProjectStorage("test_c2_upload_guard", projects_dir=tmp_path)
    vid_file = tmp_path / "dummy.mp4"
    vid_file.write_bytes(b"0" * 1024)
    receipt_path = storage.get_stage_dir("06_publish") / "upload_receipt.json"

    class _FakeStudioClient:
        def __init__(self, *, fail_selector: str | None = None, stuck_uploading: bool = False) -> None:
            self.fail_selector = fail_selector
            self.stuck_uploading = stuck_uploading
            self.navigated_urls: list[str] = []

        async def __aenter__(self) -> "_FakeStudioClient":
            return self

        async def __aexit__(self, *_a: object) -> None:
            return None

        async def send(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
            if method == "Page.navigate" and params:
                self.navigated_urls.append(str(params.get("url") or ""))
            return {}

        async def eval(self, expr: str) -> Any:
            if "location.href" in expr:
                return "https://studio.youtube.com/"
            if "ytcp-uploads-dialog, #select-files-button" in expr:
                return True
            if "shorts/" in expr and "youtu.be/" in expr:
                return "https://youtube.com/shorts/AbCdEfGhI12"
            if "stillUploading" in expr:
                if self.stuck_uploading:
                    return {"disabled": True, "stillUploading": True, "pText": "Uploading 42% ..."}
                return {"disabled": False, "stillUploading": False, "pText": "Checks complete"}
            return ""

        async def set_file_input(self, *_a: Any, **_kw: Any) -> bool:
            return True

        async def wait_for_element(self, *_a: Any, **_kw: Any) -> bool:
            return True

        async def type_into(self, *_a: Any, **_kw: Any) -> bool:
            return True

        async def click(self, selector: str, *_a: Any, **_kw: Any) -> bool:
            return selector != self.fail_selector

    class _FakeSession:
        def __init__(self, client: _FakeStudioClient) -> None:
            self._client = client

        def recycle_studio_tab(self, **_kw: Any) -> None:
            return None

        def get_direct_client(self, *_a: Any, **_kw: Any) -> _FakeStudioClient:
            return self._client

    uploader = StudioUploader.__new__(StudioUploader)
    monkeypatch.setattr(uploader, "_ensure_all_about_brain_channel", lambda _c: _fast_sleep(0.0))
    monkeypatch.setattr(uploader, "_ensure_upload_wizard_en_us_language", lambda *_a, **_kw: _fast_sleep(0.0))

    base_payload = {
        "project_id": "test_c2_upload_guard",
        "title": "Your Brain's 3 AM Night Watch",
        "description": "Synthetic AI disclaimer included.",
        "video_path": str(vid_file),
        "thumbnail_path": None,
        "visibility": "unlisted",
        "slot_id": "slot_1_midday",
        "scheduled_time_et": None,
        "storage": storage,
    }

    # Case A: R4 altered_content_checkbox click fails -> raises RuntimeError, zero receipt written
    client_r4_fail = _FakeStudioClient(fail_selector=STUDIO_SELECTORS["altered_content_checkbox"])
    uploader.session = _FakeSession(client_r4_fail)
    with pytest.raises(RuntimeError, match="AI Altered Content"):
        asyncio.run(uploader._async_upload_direct_cdp_inner(dict(base_payload)))
    assert not receipt_path.exists()

    # Case B: Upload stuck at 42% after 180s loop -> raises RuntimeError, never navigates away or writes receipt
    client_timeout = _FakeStudioClient(stuck_uploading=True)
    uploader.session = _FakeSession(client_timeout)
    with pytest.raises(RuntimeError, match="upload timed out after 180s"):
        asyncio.run(uploader._async_upload_direct_cdp_inner(dict(base_payload)))
    assert not receipt_path.exists()
    assert "https://studio.youtube.com/" not in client_timeout.navigated_urls[1:]


def test_phase2_studio_tab_isolation_and_open_lease_cleanup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Phase 2: Studio operations never hijack unleased user tabs, and failed open_leased_cdp_tab closes leaked about:blank."""
    lease_file = tmp_path / "locks" / "leases_9222.json"
    monkeypatch.setenv("AAB_CDP_LEASES_PATH", str(lease_file))

    user_studio_tab = {
        "id": "user_tab_99",
        "type": "page",
        "url": "https://studio.youtube.com/channel/UC4FeioYYv9X04Di07_MfZ7g/videos",
        "webSocketDebuggerUrl": "ws://127.0.0.1:9222/devtools/page/user_tab_99",
    }
    opened_calls: list[str] = []
    closed_ids: list[str] = []

    class _Resp:
        def __init__(self, data: bytes) -> None:
            self._data = data

        def __enter__(self) -> "_Resp":
            return self

        def __exit__(self, *_a: object) -> None:
            return None

        def read(self) -> bytes:
            return self._data

    def _fake_urlopen(req_or_url: Any, timeout: float = 5.0) -> _Resp:
        url = req_or_url.full_url if hasattr(req_or_url, "full_url") else str(req_or_url)
        if "/json/list" in url:
            return _Resp(json.dumps([user_studio_tab]).encode("utf-8"))
        if "/json/new" in url:
            opened_calls.append(url)
            new_t = {
                "id": f"pipe_tab_{len(opened_calls)}",
                "type": "page",
                "url": "about:blank",
                "webSocketDebuggerUrl": f"ws://127.0.0.1:9222/devtools/page/pipe_tab_{len(opened_calls)}",
            }
            return _Resp(json.dumps(new_t).encode("utf-8"))
        if "/json/close/" in url:
            closed_ids.append(url.rsplit("/", 1)[-1])
            return _Resp(b"Target is closing")
        return _Resp(b"{}")

    monkeypatch.setattr(urllib.request, "urlopen", _fake_urlopen)
    monkeypatch.setattr(ctl, "_create_target_via_browser_ws", lambda *_a, **_kw: None)

    ws = WhaleSessionController(cdp_port=9222)
    target = ws.get_tab_target("studio.youtube.com", default_url="https://studio.youtube.com/")
    assert target["id"] == "pipe_tab_1"
    assert target["id"] != "user_tab_99"

    # Now simulate acquire_tab_lease raising inside open_leased_cdp_tab -> must immediately close pipe_tab_2!
    def _boom_acquire(*_a: Any, **_kw: Any) -> dict[str, Any]:
        raise RuntimeError("synthetic lease failure")

    monkeypatch.setattr(ctl, "acquire_tab_lease", _boom_acquire)
    with pytest.raises(RuntimeError, match="synthetic lease failure"):
        ctl.open_leased_cdp_tab("https://studio.youtube.com/", purpose="studio_tab", cdp_port=9222)
    assert "pipe_tab_2" in closed_ids

    # Verify in-flight creation marker prevents cleanup_idle_whale_tabs from closing about:blank mid-open
    with ctl._locked_lease_registry(9222) as (state, reg_path):
        import time as _t

        now_ts = _t.time()
        state["inflight_creations"] = {
            "tok1": {"started_at": now_ts, "expires_at": now_ts + 30.0, "pid": os.getpid()}
        }
        ctl._write_registry_unlocked(state, reg_path)

    def _list_with_blank(req_or_url: Any, timeout: float = 2.0) -> _Resp:
        url = req_or_url.full_url if hasattr(req_or_url, "full_url") else str(req_or_url)
        if "/json/list" in url:
            return _Resp(
                json.dumps(
                    [
                        user_studio_tab,
                        {"id": "inflight_blank_1", "type": "page", "url": "about:blank"},
                    ]
                ).encode("utf-8")
            )
        closed_ids.append(url.rsplit("/", 1)[-1])
        return _Resp(b"Target is closing")

    monkeypatch.setattr(urllib.request, "urlopen", _list_with_blank)
    res_guard = cleanup_idle_whale_tabs(cdp_port=9222, dry_run=False)
    assert res_guard["closed"] == []
    assert "inflight_blank_1" not in closed_ids


def test_c3_c4_quarantine_slug_scoping_and_candidate_filename_isolation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """C3/C4: Quarantine wipe requires explicit slug & isolates sibling episodes; Flow candidate temp files include slug+PID."""
    q_root = tmp_path / "aab_reenact"
    (q_root / "ep_alpha").mkdir(parents=True)
    (q_root / "ep_beta").mkdir(parents=True)
    (q_root / "ep_alpha" / "frame.png").write_bytes(b"A")
    (q_root / "ep_beta" / "frame.png").write_bytes(b"B")
    monkeypatch.setattr("pipeline.archival_media.REENACT_QUARANTINE_ROOT", q_root)

    with pytest.raises(ValueError, match="non-empty episode slug"):
        purge_reenactment_quarantine(slug="")

    res = purge_reenactment_quarantine(slug="ep_alpha")
    assert res["existed"] is True
    assert not (q_root / "ep_alpha").exists()
    assert (q_root / "ep_beta" / "frame.png").exists()

    worker_src = inspect.getsource(sw)
    assert "aab_flow_cand_{safe_slug}_{os.getpid()}_{shard_idx}_{c_num}_{regen_try}.mp4" in worker_src


def test_precheck_zero_dossier_writes_and_valid_non_default_voice_completion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """--precheck-only makes zero writes to research_dossiers/<slug>/, and _is_already_completed accepts andrew_v8."""
    dossiers_root = tmp_path / "research_dossiers"
    projects_root = tmp_path / "projects"
    completed_root = tmp_path / "completed"
    dossiers_root.mkdir(parents=True)
    projects_root.mkdir(parents=True)
    completed_root.mkdir(parents=True)

    monkeypatch.setattr(rd, "DOSSIERS_ROOT", dossiers_root)
    monkeypatch.setattr(cfg, "DOSSIERS_DIR", dossiers_root)
    monkeypatch.setattr(dbo, "PROJECTS_DIR", projects_root)
    monkeypatch.setattr(dbo, "COMPLETED_SHORTS_DIR", completed_root)
    monkeypatch.setattr("pipeline.storage.PROJECTS_DIR", projects_root)

    slug = "precheck_readonly_case"
    rd.init_dossier(slug, "Readonly Precheck Case", pillar="cognitive_illusions", root=dossiers_root)
    draft_dir = dossiers_root / slug / "diorama_v7_porcelain"
    draft_dir.mkdir(parents=True, exist_ok=True)
    sents = [f"Sentence {i} tracks the tabletop illusion in bright daylight." for i in range(1, 21)]
    sents[0] = "Your eyes swear these two wooden tables differ!"
    sents[1] = "Yet a brass ruler proves both edges match."
    (draft_dir / "script.json").write_text(
        json.dumps({"schema": 7, "style_profile": "porcelain_cinematic_v7", "title": "Why Two Equal Tables Trick Your Eyes", "sentences": sents}),
        encoding="utf-8",
    )
    (draft_dir / "visual_plan.json").write_text(
        json.dumps(
            {
                "schema": 7,
                "profile": "neuro_diorama",
                "style_profile": "porcelain_cinematic_v7",
                "dossier": slug,
                "clips": [
                    {
                        "clip_number": i,
                        "sentence_index": i,
                        "act": min(6, ((i - 1) * 6) // 20 + 1),
                        "grammar": "porcelain_world_action",
                        "camera_move": "locked_tripod" if i % 2 == 1 else ("pan_left" if i % 4 == 2 else "pan_right"),
                        "scene": "In a bright studio room, a clothed matte-white porcelain figure in a tweed coat places and slides a brass ruler across two oak tables.",
                    }
                    for i in range(1, 21)
                ],
            }
        ),
        encoding="utf-8",
    )
    (draft_dir / "metadata.json").write_text(
        json.dumps({"title": "Why Two Equal Tables Trick Your Eyes", "description": "Test", "doi": "10.1126/science.2305259"}),
        encoding="utf-8",
    )

    def _snapshot_tree(root: Path) -> dict[str, tuple[int, str]]:
        snap: dict[str, tuple[int, str]] = {}
        for fp in sorted(root.rglob("*")):
            if fp.is_file():
                snap[fp.relative_to(root).as_posix()] = (
                    fp.stat().st_mtime_ns,
                    hashlib.sha256(fp.read_bytes()).hexdigest(),
                )
        return snap

    before_snap = _snapshot_tree(dossiers_root / slug)
    before_proj_snap = _snapshot_tree(projects_root)
    dbo.precheck_diorama_project(
        {"slug": slug, "project_id": "diorama_test_precheck", "pillar": "cognitive_illusions", "wave": 1},
        run_tts_clock=False,
        voice_preset="andrew_v8",
    )
    after_snap = _snapshot_tree(dossiers_root / slug)
    after_proj_snap = _snapshot_tree(projects_root)
    assert after_snap == before_snap, "precheck_diorama_project mutated research_dossiers/<slug>/!"
    assert after_proj_snap == before_proj_snap, "precheck_diorama_project mutated projects/ during read-only precheck!"
    assert not (projects_root / "diorama_test_precheck").exists()

    # Verify _is_already_completed accepts valid non-default preset 'andrew_v8' in DIORAMA_VOICE_PRESETS
    pid = "v8_test_andrew_completed"
    p_dir = projects_root / pid
    for sub in ("02_script", "03_visuals", "04_audio", "05_assembly", "06_publish"):
        (p_dir / sub).mkdir(parents=True, exist_ok=True)
    (completed_root / f"final_shorts_{pid}.mp4").write_bytes(b"V" * 5_500_000)
    d_meta_path = dossiers_root / slug / "dossier.json"
    d_meta = json.loads(d_meta_path.read_text(encoding="utf-8"))
    d_meta["schema_version"] = cfg.DOSSIER_SCHEMA_VERSION
    d_meta_path.write_text(json.dumps(d_meta), encoding="utf-8")

    (p_dir / "02_script" / "script.json").write_text(
        json.dumps({"style_profile": "expressive_25d_v8", "voice_preset": "andrew_v8", "prosody_mode": "expressive_us_v8", "dossier": slug}),
        encoding="utf-8",
    )
    (p_dir / "03_visuals" / "visual_plan.json").write_text(
        json.dumps({"style_profile": "expressive_25d_v8", "voice_preset": "andrew_v8", "prosody_mode": "expressive_us_v8", "dossier": slug}),
        encoding="utf-8",
    )
    (p_dir / "03_visuals" / "reference_image_qa_report.json").write_text(
        json.dumps({"pre_generation_ready": True, "all_passed": True}),
        encoding="utf-8",
    )
    audio_master = p_dir / "04_audio" / "audio_master.wav"
    audio_master.write_bytes(b"RIFF_PROTECTED_AUDIO")
    (p_dir / "04_audio" / "prosody_report.json").write_text(
        json.dumps({"voice_preset": "andrew_v8", "prosody_mode": "expressive_us_v8"}),
        encoding="utf-8",
    )
    for rep_rel in (
        "05_assembly/video_autopsy_report.json",
        "05_assembly/dynamic_episode_qa_report.json",
        "05_assembly/posthoc_semantic_qa_report.json",
        "05_assembly/prosody_qa_report.json",
        "06_publish/thumbnail_report.json",
    ):
        (p_dir / rep_rel).write_text(json.dumps({"passed": True}), encoding="utf-8")

    assert dbo._is_already_completed(pid) is True

    # Running read-only precheck against an already-completed project_id must NEVER delete its 04_audio/audio_master.wav!
    dbo.precheck_diorama_project(
        {"slug": slug, "project_id": pid, "pillar": "cognitive_illusions", "wave": 1},
        run_tts_clock=False,
        voice_preset="emma_v7",
    )
    assert audio_master.read_bytes() == b"RIFF_PROTECTED_AUDIO"

    # Mismatched prosody_report voice_preset ('el_researcher_v4' != 'andrew_v8') must return False
    (p_dir / "04_audio" / "prosody_report.json").write_text(
        json.dumps({"voice_preset": "el_researcher_v4", "prosody_mode": "expressive_us_v8"}),
        encoding="utf-8",
    )
    assert dbo._is_already_completed(pid) is False


def test_c1_multiround_13cut_mixed_timebase_xfade_exact_frames(tmp_path: Path) -> None:
    """C1 multi-round (>4 cuts, 13->4->1) xfade normalizes mixed input timebases (1/15360 vs 1/30000) without truncation."""
    import subprocess
    import imageio_ffmpeg
    from pipeline.assembler import _merge_xfade_group_multistage, _probe_segment_frame_count

    ff = imageio_ffmpeg.get_ffmpeg_exe()
    fps = 30
    grp_inputs: list[tuple[Path, int, str, int]] = []
    effs: list[int] = []
    for i in range(13):
        eff = 45 if i % 2 == 0 else 60
        ov = 8 if i < 12 else 0
        kind = "fade" if ov > 0 else ""
        total_f = eff + (ov + 1 if ov > 0 else 0)
        p = tmp_path / f"cut_{i:02d}.mp4"
        subprocess.run(
            [
                ff, "-y", "-f", "lavfi",
                "-i", f"color=c=0x224466:s=160x288:r={fps}",
                "-frames:v", str(total_f),
                "-c:v", "libx264", "-preset", "ultrafast",
                "-video_track_timescale", "15360",
                "-pix_fmt", "yuv420p",
                str(p),
            ],
            check=True,
            capture_output=True,
        )
        grp_inputs.append((p, eff, kind, ov))
        effs.append(eff)

    out_mp4 = tmp_path / "merged_13cuts.mp4"
    merged_f = _merge_xfade_group_multistage(
        ff, grp_inputs, out_mp4, fps=fps, target_crf=20, burn_start_sec=0.0, cwd=tmp_path
    )
    expected_f = sum(effs)
    assert merged_f == expected_f
    assert _probe_segment_frame_count(out_mp4) == expected_f


def test_whale_session_controller_close_and_about_blank_lease_reuse(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """WhaleSessionController reuses self-leased 'about:blank' Studio tab during navigation and closes self-opened tabs on close()."""
    import io
    import urllib.request
    from pipeline import cdp_tab_lease as ctl
    from pipeline.studio.watchdog import cleanup_idle_whale_tabs
    from pipeline.studio.browser_session import WhaleSessionController

    lease_file = tmp_path / "aab_cdp_leases_9222.json"
    monkeypatch.setenv("AAB_CDP_LEASES_PATH", str(lease_file))

    tabs: list[dict[str, str]] = [
        {"id": "user_studio_personal", "type": "page", "url": "https://studio.youtube.com/channel/UC_USER", "webSocketDebuggerUrl": "ws://127.0.0.1:9222/devtools/page/user_studio_personal"},
    ]
    closed_ids: list[str] = []
    seq = {"n": 0}

    def _fake_urlopen(req_or_url: Any, timeout: float = 5.0) -> Any:
        url = req_or_url.full_url if hasattr(req_or_url, "full_url") else str(req_or_url)
        if "/json/list" in url:
            return io.BytesIO(json.dumps(tabs).encode("utf-8"))
        if "/json/new" in url:
            seq["n"] += 1
            tid = f"leased_studio_{seq['n']}"
            t_obj = {"id": tid, "type": "page", "url": "about:blank", "webSocketDebuggerUrl": f"ws://127.0.0.1:9222/devtools/page/{tid}"}
            tabs.append(t_obj)
            return io.BytesIO(json.dumps(t_obj).encode("utf-8"))
        if "/json/close/" in url:
            cid = url.rsplit("/json/close/", 1)[-1]
            closed_ids.append(cid)
            tabs[:] = [t for t in tabs if t["id"] != cid]
            return io.BytesIO(b"Target is closing")
        raise AssertionError(f"Unexpected URL: {url}")

    monkeypatch.setattr(urllib.request, "urlopen", _fake_urlopen)
    monkeypatch.setattr(ctl, "_create_target_via_browser_ws", lambda *a, **k: None)

    with WhaleSessionController(cdp_port=9222) as controller:
        t1 = controller.get_tab_target("studio.youtube.com", default_url="https://studio.youtube.com/")
        # Even while /json/list still reports url == 'about:blank', second call MUST reuse t1 instead of spawning a 2nd tab!
        t2 = controller.get_tab_target("studio.youtube.com", default_url="https://studio.youtube.com/")
        assert t1["id"] == t2["id"] == "leased_studio_1"
        assert seq["n"] == 1

    # Context exit closed ONLY self-opened 'leased_studio_1', never 'user_studio_personal'
    assert closed_ids == ["leased_studio_1"]
    assert [t["id"] for t in tabs] == ["user_studio_personal"]

    # Also verify cleanup_idle_whale_tabs reaps dead-PID orphan Studio root tabs while skipping user_studio_personal
    tabs.append({"id": "dead_worker_studio", "type": "page", "url": "https://studio.youtube.com/", "webSocketDebuggerUrl": "ws://dead"})
    ctl.acquire_tab_lease(
        "dead_worker_studio",
        owner_id="dead_owner",
        purpose="studio_tab",
        cdp_port=9222,
        created_by_pipeline=True,
        initial_url="https://studio.youtube.com/",
    )
    with ctl._locked_lease_registry(9222) as (state, reg_path):
        state["leases"]["dead_worker_studio"]["pid"] = 99999999
        ctl._write_registry_unlocked(state, reg_path)
    rep = cleanup_idle_whale_tabs(cdp_port=9222, dry_run=False)
    assert rep["closed"] == ["dead_worker_studio"]
    assert [t["id"] for t in tabs] == ["user_studio_personal"]


def test_full_22clip_r68_context_split_episode_passes_all_gate1_validators(tmp_path: Path) -> None:
    """Full 15-sentence / 22-clip R68 context-split episode passes validate_expressive_v8_prompts, validate_production_diorama_v6 & Gate 1."""
    from pipeline.episode_qa import verify_pre_flow_contract
    from pipeline.prompt_builder import build_flow_prompts, validate_expressive_v8_prompts
    from pipeline.reference_pack import populate_expressive_v8_reference_contract
    from pipeline.prompt_gate import validate_production_diorama_v6

    lines = [
        "He taped a small mirror right onto his own front door!",
        "Each time he grabbed the cold brass knob, his own eyes stared back.",
        "Most people walk through a door and forget why they came in.",
        "Your brain treats each door frame like a hard page break.",
        "Step across the line, and the old room gets wiped clean.",
        "So he tried carrying a red mug from the sink to the hall.",
        "Instead, his hand froze in place when the mirror broke his habit!",
        "Wait, what happens inside your head during that sudden blank pause?",
        "Two rival brain hubs fight over what you hold in mind.",
        "Your front control hub clears the old task to map the new space.",
        "That blank stare isn't a flaw—it's a fast safety reset.",
        "Jet pilots use the same visual lock trick before flipping switches.",
        "Touch one solid thing and say your goal before you step through.",
        "Right away, the doorway stops wiping out the task you came to do.",
        "Your goal stays locked in mind because your eyes pinned it in space.",
    ]
    script_doc = {
        "schema_version": 8,
        "production_profile": "shorts_expressive_v8",
        "style_profile": "expressive_25d_v8",
        "voice_preset": "emma_v7",
        "opening_mode": "action",
        "core_reveal_sentence_index": 10,
        "lines": lines,
        "script": " ".join(lines),
    }
    locs = [
        "front_door_foyer", "hallway_threshold", "kitchen_island",
        "street_crosswalk_exterior", "cockpit_instrument_deck", "aerial_rooftop_walkway",
    ]
    cams = [
        "gentle_push_in", "whip_pan_occlusion", "orbital_3d_arc_sweep", "fpv_3d_flight",
        "dolly_zoom_vertigo", "crane_swoop_dive", "portal_dive_flight", "clean_pullback_reveal",
        "pan_left", "pan_right", "tilt_up", "tilt_down", "locked_tripod",
        "orbital_3d_arc_sweep", "portal_dive_flight", "fpv_3d_flight", "crane_swoop_dive",
        "gentle_push_in", "whip_pan_occlusion", "dolly_zoom_vertigo", "orbital_3d_arc_sweep", "clean_pullback_reveal",
    ]
    clips_in = []
    for i in range(22):
        s_idx = min(15, (i * 15) // 22 + 1)
        is_xray = i == 14
        if is_xray:
            s_idx = 10
        is_cameo = i == 18
        grammar = (
            "expressive_xray_brain"
            if is_xray
            else ("expressive_cameo_world" if is_cameo else ("expressive_hands_closeup" if i == 1 else "expressive_vinyl_world"))
        )
        scene_txt = (
            "Protagonist presses a round glass disk onto the oak door panel as gloved fingers tighten and wide ink eyes blink."
            if not is_xray
            else "Golden forehead seam parts into a crystal-clear glass dome revealing the 3D brain as amber front lobes pulse and blue arcs dim."
        )
        if is_cameo:
            scene_txt = "Pilot taps the metal toggle switch while a tiny 4cm Mini-Cortex figurine perches on the console edge nodding once."
        clips_in.append(
            {
                "id": i + 1,
                "sentence_index": s_idx,
                "act": min(6, (i * 6) // 22 + 1),
                "visual_grammar": grammar,  # Also exercises visual_grammar preservation in populate_expressive_v8_reference_contract!
                "camera": cams[i],
                "location_id": locs[i % len(locs)],
                "cast_roles": ["protagonist"] if not is_xray else [],
                "cameo_easter_egg": is_cameo,
                "transition_out": "dissolve_12f" if i in (2, 6, 11) else "daisy_chain_bridge",
                "scene": scene_txt,
            }
        )
    plan = {
        "schema_version": 8,
        "production_profile": "shorts_expressive_v8",
        "style_profile": "expressive_25d_v8",
        "opening_mode": "action",
        "core_reveal_sentence_index": 10,
        "zero_clip_reuse": True,
        "thumbnail": {
            "archetype": "object_paradox",
            "hook_text": "DOORWAY WIPE",
            "cover_sentence_index": 1,
            "cover_frame_sec": 1.2,
        },
        "clips": clips_in,
    }
    pdir = tmp_path / "v8_22clip_gate1"
    (pdir / "02_script").mkdir(parents=True)
    (pdir / "03_visuals").mkdir(parents=True)
    plan = populate_expressive_v8_reference_contract(plan, project_dir=pdir, daisy_chain_keyframes=True)
    built = build_flow_prompts(plan, lines)
    assert validate_expressive_v8_prompts(built, plan=plan) == []
    assert validate_production_diorama_v6(plan, lines, built, script_doc=script_doc) == []
    assert verify_pre_flow_contract(plan, lines, built, script_doc=script_doc) == []


def test_workspace_hygiene_live_pass_and_synthetic_clutter_detection(tmp_path: Path) -> None:
    """Workspace hygiene guard passes on live repo and catches root clutter, .tmp_*, .lock, and legacy pipeline files."""
    live_rep = audit_workspace_hygiene(cfg.WORKSPACE_ROOT)
    assert live_rep["passed"] is True, f"Live workspace failed hygiene check: {live_rep}"

    fake_ws = tmp_path / "fake_ws"
    (fake_ws / "pipeline").mkdir(parents=True)
    (fake_ws / "BCI_Shorts_Channel" / "reports" / "daily").mkdir(parents=True)
    (fake_ws / "unapproved_stray_dump.bak").write_text("x", encoding="utf-8")
    (fake_ws / "pipeline" / "assemble_100_shorts.py").write_text("# legacy", encoding="utf-8")
    (fake_ws / "BCI_Shorts_Channel" / ".flow_download_harvest.lock").write_text("", encoding="utf-8")
    (fake_ws / "BCI_Shorts_Channel" / ".tmp_broken.json").write_text("{}", encoding="utf-8")

    bad_rep = audit_workspace_hygiene(fake_ws)
    assert bad_rep["passed"] is False
    joined = "\n".join(bad_rep["issues"])
    assert "[root_clutter]" in joined
    assert "[legacy_pipeline_file]" in joined
    assert "[channel_lock_file]" in joined
    assert "[tmp_artifact]" in joined
