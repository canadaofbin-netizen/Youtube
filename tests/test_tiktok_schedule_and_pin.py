"""
Unit tests for Workstream 4A (`pipeline/studio/tiktok_uploader.py`):
- `validate_tiktok_over_60s_and_sound_lock`: rejects `< 60.0s` videos and any commercial/trending sound attachment; accepts `>= 60.0s` clean original audio
- `parse_tiktok_schedule_utc`: enforces `5`-minute increments and `+15m .. +10d` schedule window
- `upload_tiktok_video_cdp(..., dry_run=True)`: validates schedule & duration contract offline
- `sync_tiktok_pinned_videos_cdp`: enforces `<= 3` pinned video IDs and halts immediately on `secsdk-captcha` keeping tab open
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest
from PIL import Image

import pipeline.studio.tiktok_uploader as tk_mod
from pipeline.studio.tiktok_uploader import (
    parse_tiktok_schedule_utc,
    sync_tiktok_pinned_videos_cdp,
    upload_tiktok_video_cdp,
    validate_tiktok_over_60s_and_sound_lock,
)


def test_validate_tiktok_over_60s_and_sound_lock(tmp_path: Path) -> None:
    vid = tmp_path / "ep08.mp4"
    vid.write_bytes(b"\x00\x00\x00\x18ftypmp42")

    dur = validate_tiktok_over_60s_and_sound_lock(vid, duration_override_sec=74.8)
    assert dur == pytest.approx(74.8)

    with pytest.raises(ValueError, match="below required 60.0s"):
        validate_tiktok_over_60s_and_sound_lock(vid, duration_override_sec=58.2)

    with pytest.raises(ValueError, match="commercial or trending sounds"):
        validate_tiktok_over_60s_and_sound_lock(
            vid,
            duration_override_sec=74.8,
            commercial_sound_id="729184718293",
        )


def test_parse_tiktok_schedule_utc_window_and_5min_grid() -> None:
    now = datetime(2026, 11, 15, 12, 0, tzinfo=timezone.utc)
    dt_ok = parse_tiktok_schedule_utc("2026-11-15T14:35:00Z", now_utc=now)
    assert dt_ok == datetime(2026, 11, 15, 14, 35, tzinfo=timezone.utc)

    # Off 5-min grid
    with pytest.raises(ValueError, match="5-minute increments"):
        parse_tiktok_schedule_utc("2026-11-15T14:37:00Z", now_utc=now)

    # Too soon (<15 min)
    with pytest.raises(ValueError, match="at least 15 minutes"):
        parse_tiktok_schedule_utc("2026-11-15T12:10:00Z", now_utc=now)

    # Too far (>10 days)
    too_far = (now + timedelta(days=11)).replace(minute=0, second=0)
    with pytest.raises(ValueError, match="up to 10 days"):
        parse_tiktok_schedule_utc(too_far.isoformat(), now_utc=now)


def test_upload_tiktok_video_cdp_dry_run_with_schedule(tmp_path: Path) -> None:
    vid = tmp_path / "video_clean.mp4"
    vid.write_bytes(b"\x00\x00\x00\x18ftypmp42")
    cov = tmp_path / "cover_9x16.png"
    Image.new("RGB", (1080, 1920), (10, 16, 24)).save(cov, format="PNG")

    res = asyncio.run(
        upload_tiktok_video_cdp(
            video_path=vid,
            cover_path=cov,
            caption="Why Your Brain Calls Loved Ones Imposters · DOI: 10.1098/rspb.1997.0092 #neuroscience",
            schedule_at_utc="2026-11-16T00:30:00Z",
            duration_override_sec=73.6,
            dry_run=True,
        )
    )
    assert res["status"] == "dry_run"
    assert res["mode"] == "scheduled"
    assert res["scheduled_at_utc"] == "2026-11-16T00:30:00Z"
    assert res["commercial_sound_prohibited"] is True


def test_sync_tiktok_pinned_videos_ceiling_and_captcha_halt(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(ValueError, match="at most 3"):
        asyncio.run(sync_tiktok_pinned_videos_cdp(["1111", "2222", "3333", "4444"], dry_run=True))

    dry_ok = asyncio.run(sync_tiktok_pinned_videos_cdp(["741111111", "742222222", "743333333"], dry_run=True))
    assert dry_ok["status"] == "dry_run"
    assert len(dry_ok["target_video_ids"]) == 3

    closed_tabs: list[str] = []

    monkeypatch.setattr(
        tk_mod,
        "open_leased_cdp_tab",
        lambda *a, **kw: {"id": "FAKE_PIN_TAB", "webSocketDebuggerUrl": "ws://127.0.0.1:9222/devtools/page/FAKE_PIN_TAB"},
    )
    monkeypatch.setattr(tk_mod, "renew_tab_lease", lambda *a, **kw: None)
    monkeypatch.setattr(tk_mod, "release_and_close_leased_tab", lambda tid, **kw: closed_tabs.append(tid))

    class _FakeClient:
        def __init__(self, ws_url: str) -> None:
            self.ws_url = ws_url

        async def __aenter__(self) -> "_FakeClient":
            return self

        async def __aexit__(self, exc_type, exc, tb) -> bool:
            return False

        async def send(self, method: str, params: dict[str, Any] | None = None, **kw: Any) -> dict[str, Any]:
            return {}

    async def _fake_inspect(client: Any) -> dict[str, Any]:
        return {
            "url": "https://www.tiktok.com/@allaboutbrain_official/video/741111111",
            "bodyText": "Drag the slider to fit the puzzle",
            "domCaptcha": ["#tiktok-verify-ele"],
        }

    async def _fast_sleep(_sec: float) -> None:
        return None

    monkeypatch.setattr(tk_mod, "DirectCDPClient", _FakeClient)
    monkeypatch.setattr(tk_mod, "_inspect_tiktok_page", _fake_inspect)
    monkeypatch.setattr(tk_mod.asyncio, "sleep", _fast_sleep)

    cap_res = asyncio.run(sync_tiktok_pinned_videos_cdp(["741111111"], dry_run=False))
    assert cap_res["status"] == "captcha_verification_needed"
    assert cap_res["target_id"] == "FAKE_PIN_TAB"
    # Tab MUST remain open for manual user solve (never closed or bypassed)
    assert closed_tabs == []
