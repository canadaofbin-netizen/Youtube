from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import pytest

from pipeline import cli, config, flow_ingredients, source_reenactment


class _StubFlowCDPClient:
    """Offline fake DirectCDPClient with optional stuck outputCount and error-tile simulation."""

    def __init__(
        self,
        *,
        pane_text: str = "Generating will use 0 credits",
        initial_output_count: int = 4,
        stuck_output_count: int | None = None,
        rendered_urls: list[str] | None = None,
        err_tiles: int = 0,
        top_err_text: str = "",
    ) -> None:
        self.pane_text = pane_text
        self.output_count = int(initial_output_count)
        self.stuck_output_count = stuck_output_count
        self.rendered_urls = list(rendered_urls or [])
        self.err_tiles = int(err_tiles)
        self.top_err_text = top_err_text
        self.clicked_counts: list[int] = []
        self._poll_calls = 0

    async def __aenter__(self) -> "_StubFlowCDPClient":
        return self

    async def __aexit__(self, *args: Any) -> None:
        return None

    async def eval(self, expr: str, **_kwargs: Any) -> Any:
        if "localStorage.getItem('flow-prompt-box-settings')" in expr and "txt:" not in expr:
            eff_cnt = self.stuck_output_count if self.stuck_output_count is not None else self.output_count
            return {"imageModelFamilyId": "beluga_display", "mode": "IMAGE", "outputCount": eff_cnt}
        if "txt:" in expr and "localStorage.getItem('flow-prompt-box-settings')" in expr:
            eff_cnt = self.stuck_output_count if self.stuck_output_count is not None else self.output_count
            return {
                "txt": self.pane_text,
                "warn": False,
                "ls": {
                    "mode": "IMAGE",
                    "imageModelFamilyId": "beluga_display",
                    "aspectRatio": "PORTRAIT",
                    "outputCount": eff_cnt,
                },
            }
        if "bCnt" in expr and "bAsp" in expr:
            m_cnt = re.search(r'"x([1-4])"', expr)
            if m_cnt:
                clicked = int(m_cnt.group(1))
                self.clicked_counts.append(clicked)
                if self.stuck_output_count is None:
                    self.output_count = clicked
            return {"txt": self.pane_text, "warn": False, "clicked": True}
        if "button.settings-trigger-button')?.innerText" in expr:
            eff_cnt = self.stuck_output_count if self.stuck_output_count is not None else self.output_count
            return f"Image · 9:16 · x{eff_cnt}"
        if "errCount" in expr and "failedTileCount" in expr:
            return {"urls": [], "errCount": 0, "failedTileCount": 0}
        if "action: 'listener_invoked'" in expr:
            return {"action": "listener_invoked", "x": 400, "y": 800, "disabled": False}
        if "edLen:" in expr:
            return {"edLen": 0, "pending": 0}
        if "flow-pending-tile').length" in expr and "urls" not in expr:
            return 0
        if "flow-pending-tile" in expr and "urls" in expr:
            self._poll_calls += 1
            return {
                "urls": list(self.rendered_urls),
                "pending": 0,
                "errTiles": self.err_tiles,
                "failedTileCount": 0,
                "topErrText": self.top_err_text,
            }
        if "Boolean(document.querySelector('button.prompt-warning-button'))" in expr:
            return False
        return True

    async def send(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        return {}


def _make_clean_png_bytes(seed: int = 7) -> bytes:
    rng = np.random.default_rng(seed)
    bgr = rng.integers(40, 225, size=(1920, 1080, 3), dtype=np.uint8)
    ok_enc, buf = cv2.imencode(".png", bgr)
    assert ok_enc and len(buf) > 8_000
    return buf.tobytes()


def test_resolve_flow_image_batch_count_matrix() -> None:
    assert config.FLOW_ZERO_CREDIT_IMAGE_BATCH_COUNT == 1
    assert config.FLOW_ZERO_CREDIT_IMAGE_RETRY_BATCH_COUNT == 2
    assert config.FLOW_ZERO_CREDIT_IMAGE_THUMBNAIL_BATCH_COUNT == 2

    # 1st pass default -> x1
    assert config.resolve_flow_image_batch_count(None) == 1
    assert config.resolve_flow_image_batch_count(None, is_retry=False, force=False) == 1
    # Retry / --force -> x2
    assert config.resolve_flow_image_batch_count(None, is_retry=True) == 2
    assert config.resolve_flow_image_batch_count(None, force=True) == 2
    assert config.resolve_flow_image_batch_count(None, is_retry=True, force=True) == 2
    assert config.resolve_flow_image_batch_count(None, is_retry=True, retry_batch_count=3) == 3
    # Explicit override always wins over retry/force and clamps to 1..4
    assert config.resolve_flow_image_batch_count(3) == 3
    assert config.resolve_flow_image_batch_count(3, is_retry=True, force=True) == 3
    assert config.resolve_flow_image_batch_count(0) == 1
    assert config.resolve_flow_image_batch_count(-5) == 1
    assert config.resolve_flow_image_batch_count(9) == 4


def test_configure_flow_zero_credit_image_mode_fails_closed_when_output_count_stuck_at_4(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _fast_sleep(_sec: float) -> None:
        return None

    async def _fake_find_point(_c: Any, _sel: str, _text: str = "", exact: bool = False) -> tuple[int, int] | None:
        return (200, 300)

    async def _fake_click(_c: Any, _pt: tuple[int, int]) -> None:
        return None

    monkeypatch.setattr(flow_ingredients.asyncio, "sleep", _fast_sleep)
    monkeypatch.setattr(flow_ingredients, "find_point", _fake_find_point)
    monkeypatch.setattr(flow_ingredients, "trusted_click", _fake_click)

    # Stuck localStorage.outputCount=4 when x1 is requested MUST fail closed (never silently submit x4!)
    client_stuck = _StubFlowCDPClient(initial_output_count=4, stuck_output_count=4)
    with pytest.raises(RuntimeError, match="Failed to verify 0-credit Google Flow Image mode"):
        asyncio.run(flow_ingredients.configure_flow_zero_credit_image_mode(client_stuck, aspect="9:16", batch_count=1))
    assert client_stuck.clicked_counts == [1]

    # When Flow honors the x1 click (outputCount -> 1), configuration passes cleanly with output_count=1
    client_ok = _StubFlowCDPClient(initial_output_count=4, stuck_output_count=None)
    cfg_res = asyncio.run(flow_ingredients.configure_flow_zero_credit_image_mode(client_ok, aspect="9:16", batch_count=1))
    assert cfg_res["zero_credit_verified"] is True
    assert cfg_res["output_count"] == 1


def test_generate_flow_image_batch_slices_x1_strictly_and_halts_on_unusual_activity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def _fast_sleep(_sec: float) -> None:
        return None

    async def _noop_clear(_c: Any) -> None:
        return None

    async def _fake_find_point(_c: Any, _sel: str, _text: str = "", exact: bool = False) -> tuple[int, int] | None:
        return (200, 300)

    async def _fake_click(_c: Any, _pt: tuple[int, int]) -> None:
        return None

    monkeypatch.setattr(flow_ingredients.asyncio, "sleep", _fast_sleep)
    monkeypatch.setattr(flow_ingredients, "clear_prompt_ingredients", _noop_clear)
    monkeypatch.setattr(flow_ingredients, "find_point", _fake_find_point)
    monkeypatch.setattr(flow_ingredients, "trusted_click", _fake_click)

    # Make monotonic advance cleanly so the poll loop breaks right away once URLs appear
    t_counter = {"v": 0.0}

    def _fake_monotonic() -> float:
        t_counter["v"] += 12.0
        return t_counter["v"]

    import time as _time

    monkeypatch.setattr(_time, "monotonic", _fake_monotonic)

    # 1) Even if 4 URLs appear in DOM, batch_count=1 MUST strictly slice to <= 1 URL!
    png_bytes = _make_clean_png_bytes(seed=11)
    downloaded_urls: list[str] = []

    class _FakeResp:
        def __enter__(self) -> "_FakeResp":
            return self

        def __exit__(self, *args: Any) -> None:
            return None

        def read(self) -> bytes:
            return png_bytes

    import urllib.request

    def _fake_urlopen(req: Any, timeout: float = 20.0) -> _FakeResp:
        downloaded_urls.append(getattr(req, "full_url", str(req)))
        return _FakeResp()

    monkeypatch.setattr(urllib.request, "urlopen", _fake_urlopen)

    four_urls = [
        "https://flow-content.google/image/tile_01.png",
        "https://flow-content.google/image/tile_02.png",
        "https://flow-content.google/image/tile_03.png",
        "https://flow-content.google/image/tile_04.png",
    ]
    client_x1 = _StubFlowCDPClient(initial_output_count=4, rendered_urls=four_urls)
    out_png = tmp_path / "kf_x1.png"
    res_x1 = asyncio.run(
        flow_ingredients.generate_flow_image_batch(
            client_x1,
            prompt="Minimalist sunlit studio bench",
            out_path=out_png,
            batch_count=1,
            aspect="9:16",
            project_dir=None,
        )
    )
    assert res_x1["ok"] is True
    assert res_x1["saved"] is True
    assert res_x1["candidate_count"] == 1
    assert downloaded_urls == ["https://flow-content.google/image/tile_01.png"]
    assert out_png.is_file()

    # 2) "We noticed some unusual activity" (even combined with "try again later") -> flow_unusual_activity_blocked
    client_err = _StubFlowCDPClient(
        initial_output_count=4,
        rendered_urls=[],
        err_tiles=1,
        top_err_text="We noticed some unusual activity. Check for browser extensions that modify your requests, or try again later.",
    )
    res_err = asyncio.run(
        flow_ingredients.generate_flow_image_batch(
            client_err,
            prompt="Minimalist sunlit studio bench",
            out_path=tmp_path / "kf_blocked.png",
            batch_count=1,
            aspect="9:16",
            project_dir=None,
        )
    )
    assert res_err["ok"] is False
    assert res_err["reason"] == "flow_unusual_activity_blocked"
    assert "unusual activity" in res_err["error_text"].lower()
    assert client_err._poll_calls == 1


def _setup_minimal_project(tmp_path: Path, ref_ids: list[str]) -> Path:
    proj_dir = tmp_path / "ep_test_x1_x2"
    (proj_dir / "02_script").mkdir(parents=True)
    (proj_dir / "03_visuals" / "reference_images").mkdir(parents=True)
    (proj_dir / "02_script" / "script.json").write_text(
        json.dumps({"sentences": ["A researcher slides a cup across an oak desk."]}),
        encoding="utf-8",
    )
    (proj_dir / "03_visuals" / "visual_plan.json").write_text(
        json.dumps(
            {
                "style_profile": "expressive_25d_v8",
                "dossier_slug": "test_slug",
                "clips": [{"clip_number": 1, "sentence_index": 1, "scene": "Lab bench scene"}],
                "reference_anchors": [
                    {
                        "ref_id": rid,
                        "filename": f"{rid}.png",
                        "generation_order": idx,
                        "setting": "real_env",
                        "prompt": f"Clean sunlit diorama frame {rid}",
                    }
                    for idx, rid in enumerate(ref_ids, start=1)
                ],
            }
        ),
        encoding="utf-8",
    )
    return proj_dir


def test_translate_porcelain_keyframes_x1_first_x2_retry_force_and_unusual_activity_hard_halt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import pipeline.cdp_tab_lease as lease_mod
    import pipeline.flow_live_single_worker as worker_mod
    import pipeline.flow_workspace as ws_mod
    import pipeline.studio.whale_session as whale_mod

    async def _noop_async(*_a: Any, **_kw: Any) -> Any:
        return None

    async def _fake_alloc(**_kw: Any) -> dict[str, Any]:
        return {
            "tab_id": "fake_tab_1",
            "lease_owner_id": "fake_owner_1",
            "ws_url": "ws://127.0.0.1:9222/devtools/page/fake",
            "project_url": "https://labs.google/fx/tools/flow/project/fake",
        }

    class _FakeDirectCDP:
        def __init__(self, _ws: str) -> None:
            pass

        async def __aenter__(self) -> "_FakeDirectCDP":
            return self

        async def __aexit__(self, *args: Any) -> None:
            return None

        async def send(self, *_a: Any, **_kw: Any) -> dict[str, Any]:
            return {}

    monkeypatch.setattr(worker_mod, "allocate_dedicated_flow_project_tab", _fake_alloc)
    monkeypatch.setattr(whale_mod, "DirectCDPClient", _FakeDirectCDP)
    monkeypatch.setattr(lease_mod, "enable_background_focus_emulation", _noop_async)
    monkeypatch.setattr(lease_mod, "release_and_close_leased_tab", lambda *a, **kw: True)
    monkeypatch.setattr(ws_mod, "rename_active_flow_project", _noop_async)
    monkeypatch.setattr(source_reenactment, "_normalize_generated_png_916", lambda _p: None)
    monkeypatch.setattr(source_reenactment, "register_reference_image", lambda *a, **kw: None)
    monkeypatch.setattr(source_reenactment, "render_reenactment_comparison_sheet", lambda p, *a: p / "sheet.png")
    monkeypatch.setattr(
        source_reenactment,
        "resolve_keyframe_conditioning_and_prompt",
        lambda **kw: ([], str(kw["spec"].get("prompt") or "clean prompt"), False),
    )

    def _fake_specs(ref_ids: list[str]) -> dict[str, Any]:
        return {
            "all_specs": [
                {
                    "ref_id": rid,
                    "filename": f"{rid}.png",
                    "generation_order": idx,
                    "setting": "real_env",
                    "prompt": f"Prompt for {rid}",
                }
                for idx, rid in enumerate(ref_ids, start=1)
            ]
        }

    # --- Scenario A: attempt=0 uses x1, CV fails -> attempt=1 retries with x2 and passes ---
    proj_a = _setup_minimal_project(tmp_path / "case_a", ["kf_01"])
    monkeypatch.setattr(source_reenactment, "build_reference_image_specs", lambda *_a: _fake_specs(["kf_01"]))
    monkeypatch.setattr(source_reenactment, "write_reference_image_specs", lambda *_a: None)

    calls_a: list[dict[str, Any]] = []
    inspect_calls = {"n": 0}

    async def _fake_gen_a(**kwargs: Any) -> dict[str, Any]:
        calls_a.append({"batch_count": kwargs["batch_count"], "image_model": kwargs["image_model"]})
        out_p = Path(kwargs["out_path"])
        out_p.write_bytes(b"fake_png")
        return {"ok": True, "saved": True, "candidate_count": kwargs["batch_count"], "selected_index": 0}

    def _fake_inspect_a(_p: Path, _spec: dict[str, Any]) -> dict[str, Any]:
        inspect_calls["n"] += 1
        if inspect_calls["n"] == 1:
            return {"passed": False, "failed_axes": ["Q2_sharpness"], "dhash_64": "0000000000000000"}
        return {"passed": True, "failed_axes": [], "dhash_64": "ffffffffffffffff"}

    monkeypatch.setattr(flow_ingredients, "generate_flow_image_batch", _fake_gen_a)
    monkeypatch.setattr(source_reenactment, "inspect_single_reference_image", _fake_inspect_a)

    res_a = asyncio.run(
        source_reenactment.translate_porcelain_keyframes_async(
            project_dir=proj_a,
            slug="test_slug",
            force=False,
            batch_count=None,
        )
    )
    assert [c["batch_count"] for c in calls_a] == [1, 2]
    assert res_a["batch_count"] == 1
    assert res_a["retry_batch_count"] == 2
    assert res_a["generated_count"] == 1
    assert res_a["failed_ids"] == []

    # --- Scenario B: force=True calls x2 immediately on attempt=0 ---
    proj_b = _setup_minimal_project(tmp_path / "case_b", ["kf_01"])
    calls_b: list[int] = []

    async def _fake_gen_b(**kwargs: Any) -> dict[str, Any]:
        calls_b.append(int(kwargs["batch_count"]))
        Path(kwargs["out_path"]).write_bytes(b"fake_png")
        return {"ok": True, "saved": True, "candidate_count": kwargs["batch_count"], "selected_index": 0}

    monkeypatch.setattr(flow_ingredients, "generate_flow_image_batch", _fake_gen_b)
    monkeypatch.setattr(
        source_reenactment,
        "inspect_single_reference_image",
        lambda _p, _spec: {"passed": True, "failed_axes": [], "dhash_64": "ffffffffffffffff"},
    )
    res_b = asyncio.run(
        source_reenactment.translate_porcelain_keyframes_async(
            project_dir=proj_b,
            slug="test_slug",
            force=True,
            batch_count=None,
        )
    )
    assert calls_b == [2]
    assert res_b["batch_count"] == 2
    assert res_b["generated_count"] == 1

    # --- Scenario C: flow_unusual_activity_blocked halts ENTIRE batch with 0 retries & 0 model hopping ---
    proj_c = _setup_minimal_project(tmp_path / "case_c", ["kf_01", "kf_02", "kf_03"])
    monkeypatch.setattr(
        source_reenactment,
        "build_reference_image_specs",
        lambda *_a: _fake_specs(["kf_01", "kf_02", "kf_03"]),
    )
    calls_c: list[dict[str, Any]] = []

    async def _fake_gen_c(**kwargs: Any) -> dict[str, Any]:
        calls_c.append({"batch_count": kwargs["batch_count"], "image_model": kwargs["image_model"], "out": Path(kwargs["out_path"]).name})
        return {
            "ok": False,
            "reason": "flow_unusual_activity_blocked",
            "image_model": kwargs["image_model"],
            "error_text": "We noticed some unusual activity",
        }

    monkeypatch.setattr(flow_ingredients, "generate_flow_image_batch", _fake_gen_c)
    res_c = asyncio.run(
        source_reenactment.translate_porcelain_keyframes_async(
            project_dir=proj_c,
            slug="test_slug",
            force=False,
            batch_count=None,
        )
    )
    assert len(calls_c) == 1, f"Expected 0 retries and 0 model hopping on unusual activity, got {calls_c}"
    assert calls_c[0]["batch_count"] == 1
    assert calls_c[0]["image_model"] == config.FLOW_ZERO_CREDIT_IMAGE_MODEL
    assert res_c["unusual_activity_halted"] is True
    assert res_c["halted_reason"] == "flow_unusual_activity_blocked"
    assert res_c["generated_count"] == 0
    assert res_c["failed_ids"] == ["kf_01", "kf_02", "kf_03"]


def test_cli_defaults_and_zero_hardcoded_batch_count_4_across_codebase(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import sys

    # 1) 100% Google Flow Native lock
    assert config.DEFAULT_REENACT_IMAGE_BACKEND == "flow"
    assert config.REENACT_IMAGE_BACKENDS == ("flow",)

    # 2) CLI defaults: --batch-count defaults to None (auto x1/x2), porcelain-refs accepts --refs
    captured: dict[str, Any] = {}
    monkeypatch.setattr(cli, "cmd_reenact_refs", lambda ns: captured.__setitem__("rr", ns))
    monkeypatch.setattr(cli, "cmd_porcelain_refs", lambda ns: captured.__setitem__("pr", ns))
    monkeypatch.setattr(cli, "cmd_longform_refs", lambda ns: captured.__setitem__("lf", ns))

    monkeypatch.setattr(sys, "argv", ["main.py", "reenact-refs", "--project", "p1", "--slug", "s1"])
    cli.main()
    assert captured["rr"].batch_count is None

    monkeypatch.setattr(
        sys,
        "argv",
        ["main.py", "porcelain-refs", "--project", "p1", "--refs", "kf_c05,kf_c12", "--force"],
    )
    cli.main()
    assert captured["pr"].batch_count is None
    assert captured["pr"].refs == "kf_c05,kf_c12"
    assert captured["pr"].force is True

    monkeypatch.setattr(sys, "argv", ["main.py", "longform-refs", "--project", "lf1"])
    cli.main()
    assert captured["lf"].batch_count is None

    # 3) Zero hardcoded `batch_count=4` remaining anywhere in pipeline/ or scripts/
    repo_root = Path(config.WORKSPACE_ROOT)
    pat = re.compile(r"\bbatch_count\s*=\s*4\b")
    offenders: list[str] = []
    for folder in ("pipeline", "scripts"):
        for py_file in sorted((repo_root / folder).rglob("*.py")):
            text = py_file.read_text(encoding="utf-8", errors="ignore")
            for lineno, line in enumerate(text.splitlines(), start=1):
                if pat.search(line):
                    offenders.append(f"{py_file.relative_to(repo_root)}:{lineno}: {line.strip()}")
    assert offenders == [], f"Found hardcoded batch_count=4 calls: {offenders}"
