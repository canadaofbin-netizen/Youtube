from __future__ import annotations

import argparse
import asyncio
import json
import math
import struct
import wave
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import pytest

from pipeline import cli, config, flow_ingredients, news_radar, thumbnail as thumbnail_studio
from pipeline.config import (
    DOSSIERS_DIR,
    FLOW_ZERO_CREDIT_IMAGE_MODEL,
    LONGFORM_VIDEO_FPS,
    LONGFORM_VIDEO_HEIGHT,
    LONGFORM_VIDEO_WIDTH,
    PILLAR_DEFAULT_STYLE_MAP,
    TITLE_MAX_CHARS_DIORAMA,
)
from pipeline.batch_runner import build_editorial_description_from_dossier
from pipeline.prompt_gate import validate_production_diorama_v6
from pipeline.ref_qa import _dhash_64
from pipeline.studio.community import CommunityManager, _find_matching_dossier_dir
from pipeline.studio.watchdog import cleanup_idle_whale_tabs


class _FakeFlowImageCDPClient:
    """Deterministic fake DirectCDPClient exercising configure_flow_zero_credit_image_mode & generate_flow_image_batch."""

    def __init__(
        self,
        *,
        pane_text: str = "Generating will use 0 credits",
        warn: bool = False,
        initial_family: str = "",
        after_click_family: str = "beluga_display",
        rendered_urls: list[str] | None = None,
        initial_output_count: int = 4,
    ) -> None:
        self.pane_text = pane_text
        self.warn = warn
        self.family = initial_family
        self.after_click_family = after_click_family
        self.rendered_urls = list(rendered_urls or [])
        self.output_count = int(initial_output_count)
        self.clicked_dropdown = False
        self.selected_model = False

    async def eval(self, expr: str, **_kwargs: Any) -> Any:
        if "localStorage.getItem('flow-prompt-box-settings')" in expr and "txt:" not in expr:
            return {"imageModelFamilyId": self.family, "mode": "IMAGE", "outputCount": self.output_count}
        if "txt:" in expr and "localStorage.getItem('flow-prompt-box-settings')" in expr:
            return {
                "txt": self.pane_text,
                "warn": self.warn,
                "ls": {
                    "mode": "IMAGE",
                    "imageModelFamilyId": self.family,
                    "outputCount": self.output_count,
                },
            }
        if "bCnt" in expr and "bAsp" in expr:
            import re as _re

            m_cnt = _re.search(r'"x([1-4])"', expr)
            if m_cnt:
                self.output_count = int(m_cnt.group(1))
            return {"txt": self.pane_text, "warn": self.warn, "clicked": True}
        if "button.settings-trigger-button')?.innerText" in expr:
            return f"Image · 9:16 · x{self.output_count}"
        if "action: 'listener_invoked'" in expr:
            return {"action": "listener_invoked", "x": 400, "y": 800, "disabled": False}
        if "ed.innerText || '').trim().length : 0" in expr:
            return 0
        if "flow-pending-tile" in expr and "urls" in expr:
            return {"urls": list(self.rendered_urls), "pending": 0, "errTiles": 0}
        if "Boolean(document.querySelector('button.prompt-warning-button'))" in expr:
            return self.warn
        if ".filter(im => im.naturalWidth >= 300" in expr:
            return []
        return True

    async def send(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        return {}


def test_configure_flow_zero_credit_image_mode_selects_model_when_unset_and_rejects_paid(
    monkeypatch: pytest.MonkeyPatch,
):
    async def _fast_sleep(_sec: float) -> None:
        return None

    monkeypatch.setattr(flow_ingredients.asyncio, "sleep", _fast_sleep)

    client_paid = _FakeFlowImageCDPClient(
        pane_text="Generating will use 4 credits",
        warn=False,
        initial_family="beluga_display",
    )

    async def _fake_find_point_paid(c: Any, sel: str, text: str = "", exact: bool = False) -> tuple[int, int] | None:
        return (200, 300)

    async def _fake_click_paid(c: Any, pt: tuple[int, int]) -> None:
        return None

    monkeypatch.setattr(flow_ingredients, "find_point", _fake_find_point_paid)
    monkeypatch.setattr(flow_ingredients, "trusted_click", _fake_click_paid)

    # Even without button.prompt-warning-button and with family_ok=True, explicit non-zero credit text MUST fail closed
    with pytest.raises(RuntimeError, match="Failed to verify 0-credit Google Flow Image mode"):
        asyncio.run(flow_ingredients.configure_flow_zero_credit_image_mode(client_paid, aspect="9:16", batch_count=4))

    # When imageModelFamilyId starts unset (""), dropdown MUST be opened and Nano Banana 2.1 selected
    client_unset = _FakeFlowImageCDPClient(
        pane_text="Generating will use 0 credits",
        warn=False,
        initial_family="",
    )
    selected_targets: list[str] = []

    async def _fake_find_point_ok(c: Any, sel: str, text: str = "", exact: bool = False) -> tuple[int, int] | None:
        if text == FLOW_ZERO_CREDIT_IMAGE_MODEL:
            selected_targets.append(text)
            c.family = c.after_click_family
        return (220, 340)

    monkeypatch.setattr(flow_ingredients, "find_point", _fake_find_point_ok)
    cfg = asyncio.run(flow_ingredients.configure_flow_zero_credit_image_mode(client_unset, aspect="9:16", batch_count=4))
    assert FLOW_ZERO_CREDIT_IMAGE_MODEL in selected_targets
    assert cfg["zero_credit_verified"] is True
    assert cfg["output_count"] == 4


def test_generate_flow_image_batch_refuses_to_save_or_register_when_candidates_fail_dhash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    async def _fast_sleep(_sec: float) -> None:
        return None

    monkeypatch.setattr(flow_ingredients.asyncio, "sleep", _fast_sleep)

    # Build a 1080x1920 image with rich high-frequency noise so PNG > 8KB, then pass its exact dHash as forbidden source
    rng = np.random.default_rng(42)
    bgr = rng.integers(30, 230, size=(1920, 1080, 3), dtype=np.uint8)
    ok_enc, png_buf = cv2.imencode(".png", bgr)
    assert ok_enc and len(png_buf) > 8_000
    png_bytes = png_buf.tobytes()
    forbidden_dhash = _dhash_64(cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY))

    fake_urls = [
        "https://flow-content.google/image/cand_1.png",
        "https://flow-content.google/image/cand_2.png",
    ]
    client = _FakeFlowImageCDPClient(
        pane_text="Generating will use 0 credits",
        warn=False,
        initial_family="beluga_display",
        rendered_urls=fake_urls,
    )

    class _FakeResp:
        def __enter__(self) -> "_FakeResp":
            return self

        def __exit__(self, *args: Any) -> None:
            return None

        def read(self) -> bytes:
            return png_bytes

    import urllib.request

    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=20: _FakeResp())
    registered_calls: list[str] = []
    import pipeline.ref_qa as rqa

    async def _noop_clear(_c: Any) -> None:
        return None

    monkeypatch.setattr(flow_ingredients, "clear_prompt_ingredients", _noop_clear)
    monkeypatch.setattr(rqa, "register_reference_image", lambda *a, **kw: registered_calls.append("called"))

    out_png = tmp_path / "ref_s01_start.png"
    res = asyncio.run(
        flow_ingredients.generate_flow_image_batch(
            client,
            prompt="Porcelain figure seated in bright laboratory room",
            out_path=out_png,
            aspect="9:16",
            batch_count=2,
            project_dir=tmp_path,
            source_dhashes=[forbidden_dhash],
        )
    )
    assert res["ok"] is False
    assert res["saved"] is False
    assert not out_png.exists()
    assert registered_calls == []






def test_community_line1_question_above_fold_and_reenact_dossier_lookup():
    d_dir = _find_matching_dossier_dir("reenact_01_ainsworth_strange_situation")
    if d_dir is None or not (Path(config.PROJECTS_DIR) / "reenact_01_ainsworth_strange_situation").exists():
        pytest.skip("Optional fixture reenact_01_ainsworth_strange_situation not present on disk")
    assert d_dir is not None and d_dir.name == "ainsworth_strange_situation"

    cm = CommunityManager()
    pkg = cm.prepare_comment_content("reenact_01_ainsworth_strange_situation")
    comment = pkg["comment_text"]
    lines = [ln.strip() for ln in comment.splitlines() if ln.strip()]
    assert len(lines) >= 2
    assert lines[0].endswith("?"), f"Line 1 must be the viewer question above mobile fold, got: {lines[0]!r}"
    assert "https://doi.org/10.2307/1127388" in comment


def test_editorial_description_and_metadata_sanitizer_parse_real_dossier_citations():
    desc, tags, doi = build_editorial_description_from_dossier(
        project_id="diorama_78_ramachandran_synesthesia_cross_wiring",
        pillar="brain_basics",
        slug="ramachandran_synesthesia_cross_wiring",
        script_doc={"doi": "10.1098/rspb.2000.1576"},
    )
    assert "Ramachandran" in desc
    assert ". . ." not in desc
    assert "-  (" not in desc
    assert "fusiform face area" in desc or "primary visual cortex" in desc
    assert doi == "10.1098/rspb.2000.1576"
    assert "#Shorts" in tags



def test_watchdog_cleanup_idle_whale_tabs_and_news_radar_canonical_pillars(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    fake_targets = [
        {"id": "t_flow", "type": "page", "url": "https://labs.google/fx/tools/flow/project/abc"},
        {"id": "t_blank", "type": "page", "url": "about:blank"},
        {"id": "t_studio_1", "type": "page", "url": "https://studio.youtube.com/video/VID1/edit"},
        {"id": "t_studio_2", "type": "page", "url": "https://studio.youtube.com/video/VID2/edit"},
    ]
    closed_urls: list[str] = []

    class _Resp:
        def __init__(self, payload: bytes) -> None:
            self._payload = payload

        def __enter__(self) -> "_Resp":
            return self

        def __exit__(self, *a: Any) -> None:
            return None

        def read(self) -> bytes:
            return self._payload

    import urllib.request

    def _fake_urlopen(url: str, timeout: float = 2.0) -> _Resp:
        if url.endswith("/json/list"):
            return _Resp(json.dumps(fake_targets).encode("utf-8"))
        closed_urls.append(url)
        return _Resp(b"Target is closing")

    monkeypatch.setattr(urllib.request, "urlopen", _fake_urlopen)
    # 1) Unleased user Studio tabs (t_studio_1, t_studio_2) must NEVER be closed; only idle about:blank closes
    res = cleanup_idle_whale_tabs(cdp_port=9222, dry_run=False)
    assert res["cdp_reachable"] is True
    assert set(res["closed"]) == {"t_blank"}
    assert not any("t_flow" in u or "t_studio_1" in u or "t_studio_2" in u for u in closed_urls)

    # 2) Evicted pipeline-created Studio edit tab (in orphan_pipeline_tabs) IS closed while user t_studio_1 stays open
    from pipeline.cdp_tab_lease import _locked_lease_registry, _write_registry_unlocked

    fake_targets = [t for t in fake_targets if t["id"] != "t_blank"]
    closed_urls.clear()
    with _locked_lease_registry(9222) as (reg_state, reg_path):
        reg_state.setdefault("orphan_pipeline_tabs", {})["t_studio_2"] = {"evicted_at": 1.0, "owner_id": "dead_worker"}
        _write_registry_unlocked(reg_state, reg_path)
    res_orph = cleanup_idle_whale_tabs(cdp_port=9222, dry_run=False)
    assert set(res_orph["closed"]) == {"t_studio_2"}
    assert not any("t_flow" in u or "t_studio_1" in u for u in closed_urls)

    # Verify news_radar only emits canonical 7 pillars (never 'bci_medicine')
    monkeypatch.setattr(news_radar, "NEURO_NEWS_STAGING_DIR", str(tmp_path / "news_staging"))
    rep = news_radar.scan_breaking_neuro_news(
        offline_items=[
            {"DOI": "10.1038/s41591-026-00001-1", "title": ["Closed-loop deep brain stimulation clinical trial for depression"]},
            {"DOI": "10.1038/s41586-026-00002-2", "title": ["Intracortical brain-computer interface decoding speech"]},
            {"DOI": "10.1126/science.2026.00003", "title": ["Hippocampal sharp-wave ripple consolidation in macaques"]},
        ]
    )
    assert len(rep["candidates"]) == 3
    for cand in rep["candidates"]:
        assert cand["pillar"] in PILLAR_DEFAULT_STYLE_MAP, f"Non-canonical pillar {cand['pillar']!r}"
