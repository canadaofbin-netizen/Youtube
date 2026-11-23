"""Unit tests for Human-in-the-Loop Pre-Fill Mode (`--human-submit` & `--fresh-room`) in `diorama-flow`."""

from __future__ import annotations

import asyncio
import collections
import json
from pathlib import Path
from typing import Any

import pytest

import pipeline.flow_diorama_sharded_worker as worker_mod
from pipeline.flow_diorama_sharded_worker import (
    FlowCircuitBreakerError,
    _run_shard_worker,
    _submit_diorama_prompt_zero_credit,
    _wait_for_human_submit_trigger,
)


class _FakeHumanSubmitCDPClient:
    """Deterministic fake DirectCDPClient recording all CDP sends and JS evals (0 live browser I/O)."""

    def __init__(self, poll_snapshots: list[dict[str, Any]], flow_url: str = "https://flow.google.com/project/test-room") -> None:
        self.flow_url = flow_url
        self.poll_snapshots = list(poll_snapshots)
        self.poll_idx = 0
        self.sent_calls: list[tuple[str, dict[str, Any] | None]] = []
        self.eval_exprs: list[str] = []

    async def __aenter__(self) -> "_FakeHumanSubmitCDPClient":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        return None

    async def send(self, method: str, params: dict[str, Any] | None = None, timeout_sec: float = 90.0) -> dict[str, Any]:
        self.sent_calls.append((method, params))
        if method == "Page.captureScreenshot":
            return {"data": ""}
        return {}

    async def eval(self, expression: str, include_command_line_api: bool = True, await_promise: bool = False) -> Any:
        self.eval_exprs.append(expression)
        if "getEventListeners" in expression:
            raise AssertionError("human_submit=True MUST NEVER evaluate getEventListeners!")
        if expression.strip() == "location.href":
            return self.flow_url
        if "document.querySelector('.cdk-overlay-pane')" in expression:
            return False
        if "document.querySelector('flow-generate-icon-button')" in expression and "Boolean(ed)" in expression:
            return True
        if "document.execCommand('selectAll'" in expression:
            return True
        if "CHECK_CREDIT" in expression or "credit_banner" in expression or "exhausted" in expression:
            return {"exhausted": False, "credit_banner": False}
        if "flow-pending-tile" in expression and "classifyTile" in expression:
            # Gallery snapshot used by _read_human_submit_gallery_snapshot
            idx = min(self.poll_idx, len(self.poll_snapshots) - 1)
            self.poll_idx += 1
            return dict(self.poll_snapshots[idx])
        return {}


def test_human_submit_never_dispatches_click_enter_or_listener_and_writes_waiting_status(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    status_file = tmp_path / "aab_human_submit_status.json"
    observed_waiting_state: list[dict[str, Any]] = []

    base_snap = {
        "ready": 2,
        "rendering": 0,
        "pending": 0,
        "errCount": 0,
        "errText": "",
        "topKey": "https://cdn/old_2.mp4",
        "srcs": ["https://cdn/old_1.mp4", "https://cdn/old_2.mp4"],
        "edLen": 48,
        "haltWarn": False,
        "haltText": "",
    }
    after_human_click_snap = {
        **base_snap,
        "rendering": 1,
        "pending": 1,
        "edLen": 0,
    }
    client = _FakeHumanSubmitCDPClient([base_snap, base_snap, after_human_click_snap])

    async def _fake_count_chips(_c: Any) -> int:
        return 0

    async def _fake_cfg_engine(_c: Any, **_kw: Any) -> dict[str, Any]:
        return {"flow_model": "Omni 1.2 Flash", "credit_tier": "omni_monthly_credit"}

    orig_sleep = asyncio.sleep

    async def _spy_sleep(delay: float) -> None:
        if status_file.exists():
            observed_waiting_state.append(json.loads(status_file.read_text(encoding="utf-8")))
        await orig_sleep(0)

    monkeypatch.setattr(worker_mod, "count_chips", _fake_count_chips)
    monkeypatch.setattr(worker_mod, "_configure_diorama_tab_engine", _fake_cfg_engine)
    monkeypatch.setattr(worker_mod.asyncio, "sleep", _spy_sleep)

    sub_meta: dict[str, Any] = {}
    ok = asyncio.run(
        _submit_diorama_prompt_zero_credit(
            client=client,  # type: ignore[arg-type]
            prompt_text="Slow cinematic push-in on translucent porcelain brain diorama.",
            short_ref_path=None,
            ref_state={"uploaded_in_tab": set(), "zero_credit_output_count": 1},
            engine_mode="omni",
            submission_meta_out=sub_meta,
            human_submit=True,
            human_submit_clip_index=1,
            human_submit_project_id="v8_ep13_test",
            human_submit_flow_url="https://flow.google.com/project/test-room",
            human_submit_timeout_sec=10.0,
            human_submit_poll_sec=0.05,
            human_submit_status_path=status_file,
        )
    )

    assert ok is True
    assert sub_meta["human_submitted"] is True
    assert sub_meta["human_submit_trigger"] == "new_rendering_tile"
    assert sub_meta["flow_model"] == "Omni 1.2 Flash"

    # (a) MUST NEVER synthesize Submit mouse clicks, Enter keys, or getEventListeners
    methods = [m for m, _ in client.sent_calls]
    assert "Input.insertText" in methods
    assert "Input.dispatchMouseEvent" not in methods
    assert "Input.dispatchKeyEvent" not in methods
    assert not any("getEventListeners" in ex for ex in client.eval_exprs)

    # (b) Published waiting_for_human_click while polling, then transitioned to rendering_detected
    assert any(
        s.get("state") == "waiting_for_human_click"
        and s.get("clip_index") == 1
        and s.get("project_id") == "v8_ep13_test"
        and s.get("flow_url") == "https://flow.google.com/project/test-room"
        and bool(s.get("updated_at"))
        for s in observed_waiting_state
    ), observed_waiting_state
    final_status = json.loads(status_file.read_text(encoding="utf-8"))
    assert final_status["state"] == "rendering_detected"
    assert final_status["clip_index"] == 1


def test_human_submit_halt_guard_and_timeout_no_bypass(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    status_file = tmp_path / "status_halt.json"
    base = {"ready": 0, "rendering": 0, "pending": 0, "errCount": 0, "topKey": "", "srcs": [], "haltWarn": False, "haltText": ""}
    halt_snap = {**base, "errCount": 1, "haltWarn": True, "haltText": "We noticed some unusual activity."}
    client = _FakeHumanSubmitCDPClient([halt_snap])

    async def _fast_sleep(_d: float) -> None:
        return None

    monkeypatch.setattr(worker_mod.asyncio, "sleep", _fast_sleep)

    with pytest.raises(FlowCircuitBreakerError, match="FLOW_HALT_GUARD"):
        asyncio.run(
            _wait_for_human_submit_trigger(
                client=client,  # type: ignore[arg-type]
                baseline=base,
                clip_index=7,
                project_id="v8_ep13_test",
                flow_url="https://flow.google.com/project/test-room",
                timeout_sec=5.0,
                poll_sec=0.05,
                status_path=status_file,
            )
        )
    st_halt = json.loads(status_file.read_text(encoding="utf-8"))
    assert st_halt["state"] == "halted"
    assert "unusual activity" in st_halt["detail"].lower()

    # Timeout case: no click synthesized, cleanly writes state="timeout"
    status_to = tmp_path / "status_timeout.json"
    client_to = _FakeHumanSubmitCDPClient([base])
    ticks = iter([0.0, 0.5, 2.0, 5.0])
    monkeypatch.setattr(worker_mod.time, "monotonic", lambda: next(ticks, 10.0))
    res_to = asyncio.run(
        _wait_for_human_submit_trigger(
            client=client_to,  # type: ignore[arg-type]
            baseline=base,
            clip_index=10,
            project_id="v8_ep13_test",
            flow_url="https://flow.google.com/project/test-room",
            timeout_sec=1.0,
            poll_sec=0.05,
            status_path=status_to,
        )
    )
    assert res_to["triggered"] is False
    assert res_to["reason"] == "timeout"
    assert json.loads(status_to.read_text(encoding="utf-8"))["state"] == "timeout"
    assert not any(m in ("Input.dispatchMouseEvent", "Input.dispatchKeyEvent") for m, _ in client_to.sent_calls)


def test_human_submit_shard_worker_resumes_download_and_marks_downloaded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    proj_dir = tmp_path / "v8_ep13_test"
    (proj_dir / "03_visuals" / "flow_native_clips").mkdir(parents=True, exist_ok=True)
    status_file = tmp_path / "aab_human_submit_status.json"

    alloc_calls: list[dict[str, Any]] = []

    async def _fake_alloc(**kwargs: Any) -> dict[str, str]:
        alloc_calls.append(dict(kwargs))
        return {
            "tab_id": "TAB_HUMAN_1",
            "ws_url": "ws://127.0.0.1:9222/devtools/page/TAB_HUMAN_1",
            "project_url": "https://flow.google.com/project/fresh-human-room",
            "lease_owner_id": "owner-human",
        }

    class _WorkerFakeClient(_FakeHumanSubmitCDPClient):
        def __init__(self, _ws_url: str) -> None:
            super().__init__(
                [
                    {
                        "ready": 0,
                        "rendering": 0,
                        "srcs": [],
                        "topKey": "",
                        "hasNewSrc": False,
                        "hadErr": False,
                        "errText": "",
                        "haltWarn": False,
                        "haltText": "",
                    },
                    {
                        "ready": 1,
                        "rendering": 0,
                        "srcs": ["https://cdn/clip_1_new.mp4"],
                        "topKey": "https://cdn/clip_1_new.mp4",
                        "hasNewSrc": True,
                        "hadErr": False,
                        "errText": "",
                        "haltWarn": False,
                        "haltText": "",
                    },
                ],
                flow_url="https://flow.google.com/project/fresh-human-room",
            )

        async def eval(self, expression: str, include_command_line_api: bool = True, await_promise: bool = False) -> Any:
            if "readyTiles" in expression and "hasNewSrc" in expression:
                return dict(self.poll_snapshots[-1])
            if "readyTiles" in expression and "srcs" in expression:
                return dict(self.poll_snapshots[0])
            return await super().eval(expression, include_command_line_api, await_promise)

    async def _noop(*_a: Any, **_kw: Any) -> Any:
        return {}

    async def _fake_submit(
        client: Any,
        prompt_text: str,
        short_ref_path: Any,
        ref_state: Any,
        *,
        submission_meta_out: dict[str, Any] | None = None,
        human_submit: bool = False,
        human_submit_clip_index: int | None = None,
        human_submit_status_path: Path | None = None,
        **_kw: Any,
    ) -> bool:
        assert human_submit is True
        assert human_submit_clip_index == 1
        assert human_submit_status_path == status_file
        worker_mod.write_human_submit_status(
            state="rendering_detected",
            clip_index=human_submit_clip_index,
            project_id="v8_ep13_test",
            flow_url="https://flow.google.com/project/fresh-human-room",
            status_path=human_submit_status_path,
        )
        if submission_meta_out is not None:
            submission_meta_out.update(
                {
                    "flow_model": "Omni 1.2 Flash",
                    "credit_tier": "omni_monthly_credit",
                    "reference_attached": False,
                    "attached_chip_count": 0,
                    "input_mode": "VIDEO_FRAMES",
                    "human_submitted": True,
                }
            )
        return True

    async def _fake_download(**kwargs: Any) -> dict[str, Any]:
        dst_mp4 = Path(kwargs["dst_mp4"])
        dst_mp4.parent.mkdir(parents=True, exist_ok=True)
        dst_mp4.write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"A" * 200_000)
        return {"source_download_filename": "flow_human_clip_1.mp4"}

    async def _fake_cfg_tab(*_a: Any, **_kw: Any) -> dict[str, Any]:
        return {"flow_model": "Omni 1.2 Flash"}

    async def _fake_probe(*_a: Any, **_kw: Any) -> dict[str, Any]:
        return {"credits_remaining": 18000, "exhausted": False}

    monkeypatch.setattr(worker_mod, "allocate_dedicated_flow_project_tab", _fake_alloc)
    monkeypatch.setattr(worker_mod, "DirectCDPClient", _WorkerFakeClient)
    monkeypatch.setattr(worker_mod, "enable_background_focus_emulation", _noop)
    monkeypatch.setattr(worker_mod, "rename_active_flow_project", _noop)
    monkeypatch.setattr(worker_mod, "_configure_diorama_tab_engine", _fake_cfg_tab)
    monkeypatch.setattr(worker_mod, "probe_flow_account_credits", _fake_probe)
    monkeypatch.setattr(worker_mod, "_submit_diorama_prompt_zero_credit", _fake_submit)
    monkeypatch.setattr(worker_mod, "_download_newest_ready_tile", _fake_download)
    monkeypatch.setattr(worker_mod, "_invoke_inspect_diorama_clip_cv", lambda *_a, **_kw: {"passed": True, "max_frame_diff": 8.0, "mean_luma": 130.0, "plaque_glyph_run": 0})
    monkeypatch.setattr(worker_mod, "_ensure_min_clip_size_if_needed", lambda _p: None)
    monkeypatch.setattr(worker_mod.asyncio, "sleep", lambda _d: _noop())

    c_spec = {
        "clip_number": 1,
        "grammar": "expressive_vinyl_world",
        "prompt": "Smooth slow push-in on porcelain figure.",
        "schema_version": 8,
    }
    res = asyncio.run(
        _run_shard_worker(
            shard_idx=1,
            shard_clips=[],
            project_id="v8_ep13_test",
            project_dir=proj_dir,
            short_ref_map={},
            tab_open_lock=asyncio.Lock(),
            opened_tabs=[],
            seen_global_shas=set(),
            engine_mode="omni",
            shared_clip_queue=collections.deque([c_spec]),
            flow_rate_state={"probed_live_credits": True},
            human_submit=True,
            fresh_room=True,
            human_submit_status_path=status_file,
        )
    )

    assert len(alloc_calls) == 1
    assert alloc_calls[0].get("foreground") is True
    assert alloc_calls[0].get("force_fresh_room") is True
    assert (proj_dir / "03_visuals" / "flow_native_clips" / "clip_1.mp4").is_file()
    assert len(res["clips"]) == 1
    final_st = json.loads(status_file.read_text(encoding="utf-8"))
    assert final_st["state"] == "downloaded"
    assert final_st["clip_index"] == 1
    assert "clip_1.mp4" in final_st["detail"]


def test_cli_diorama_flow_accepts_human_submit_and_fresh_room() -> None:
    import subprocess
    import sys

    proc = subprocess.run(
        [sys.executable, "main.py", "diorama-flow", "--help"],
        cwd=str(Path(__file__).resolve().parent.parent),
        capture_output=True,
        text=True,
        check=True,
    )
    assert "--human-submit" in proc.stdout
    assert "--fresh-room" in proc.stdout
