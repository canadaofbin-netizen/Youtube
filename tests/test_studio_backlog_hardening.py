"""
Unit tests for Studio Backlog Hardening (`tests/test_studio_backlog_hardening.py`):
1. `pipeline/studio/community.py` (`_resolve_organic_views_and_elapsed_hours`):
   - Collects all valid view readings across `upload_rec`, `SHORT_LINK_GRAPH_FILE`, and
     latest `DAILY_REPORTS_DIR/*_studio_metrics.json` (`per_video_records` AND `videos`)
     and selects `max()`, fixing stale `views: 0` shadowing and missing `per_video_records` key.
   - Respects explicit `known_organic_views` caller override verbatim.
2. `pipeline/studio/instagram_uploader.py`:
   - `detect_instagram_rate_limit_429` detects HTTP 429 / "This page isn't working" /
     "too many requests" / "rate limit" / "429" while returning `None` on normal profiles.
   - `upload_instagram_reel_cdp` and `upload_instagram_carousel_cdp` fail fast with
     `status == "rate_limited_429"` right after `Page.navigate` without waiting for Create `+`.
   - `attach_instagram_file_input_with_polling` polls delayed inputs, falls back across
     priority selectors, and times out cleanly.
3. `pipeline/studio/tiktok_uploader.py`:
   - `click_tiktok_confirm_modal_button` scopes strictly inside modal overlays
     (`[role="dialog"], .TUXModal, [class*="modal"], [class*="Modal"]`), uses trusted mouse
     dispatch, and refuses any modal matching CAPTCHA markers via `detect_tiktok_captcha`.
   - `upload_tiktok_video_cdp` post-submit loop clicks a delayed `"Post now"` modal appearing
     >2.0s after submit and completes cleanly once `/tiktokstudio/content` appears.
   - CAPTCHA appearing during the publish loop immediately halts with
     `status == "captcha_verification_needed"` without clicking any modal button.

Strictly 100% offline — zero real Chrome/CDP/Google Flow calls.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest
from PIL import Image

import pipeline.studio.community as comm_mod
import pipeline.studio.instagram_uploader as ig_mod
import pipeline.studio.tiktok_uploader as tk_mod
from pipeline.studio.community import CommunityManager
from pipeline.studio.instagram_uploader import (
    INSTAGRAM_IMAGE_FILE_INPUT_SELECTORS,
    INSTAGRAM_VIDEO_FILE_INPUT_SELECTORS,
    attach_instagram_file_input_with_polling,
    detect_instagram_rate_limit_429,
    upload_instagram_carousel_cdp,
    upload_instagram_reel_cdp,
)
from pipeline.studio.tiktok_uploader import (
    TIKTOK_MODAL_CONTAINER_SELECTOR,
    click_tiktok_confirm_modal_button,
    upload_tiktok_video_cdp,
)


# ---------------------------------------------------------------------------
# Patch 1: pipeline/studio/community.py
# ---------------------------------------------------------------------------


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def test_community_resolve_views_stale_graph_zero_overridden_by_per_video_records(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    graph_file = tmp_path / "short_link_graph.json"
    reports_dir = tmp_path / "daily"
    _write_json(
        graph_file,
        {
            "nodes": [
                {"project_id": "v8_ep08_capgras", "video_id": "VID_CAPGRAS", "views": 0},
            ]
        },
    )
    _write_json(
        reports_dir / "2026-11-20_studio_metrics.json",
        {
            "per_video_records": [
                {"project_id": "v8_ep08_capgras", "video_id": "VID_CAPGRAS", "views": 115},
            ]
        },
    )
    _write_json(
        reports_dir / "2026-11-21_studio_metrics.json",
        {
            "per_video_records": [
                {"project_id": "v8_ep08_capgras", "video_id": "VID_CAPGRAS", "views": 412},
            ]
        },
    )

    monkeypatch.setattr(comm_mod, "SHORT_LINK_GRAPH_FILE", graph_file)
    monkeypatch.setattr(comm_mod, "DAILY_REPORTS_DIR", reports_dir)

    cm = CommunityManager(projects_dir=None)
    views, _elapsed = cm._resolve_organic_views_and_elapsed_hours(
        "v8_ep08_capgras",
        "VID_CAPGRAS",
        {"status": "published_public"},
        now_utc=datetime(2026, 11, 21, 12, 0, tzinfo=timezone.utc),
    )
    assert views == 412


def test_community_resolve_views_takes_max_between_graph_and_legacy_videos_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    graph_file = tmp_path / "short_link_graph.json"
    reports_dir = tmp_path / "daily"
    _write_json(
        graph_file,
        {
            "nodes": [
                {"project_id": "v8_ep09_mirror", "video_id": "VID_MIRROR", "views": 520},
            ]
        },
    )
    _write_json(
        reports_dir / "2026-11-21_studio_metrics.json",
        {
            "videos": [
                {"project_id": "v8_ep09_mirror", "video_id": "VID_MIRROR", "views": 310},
            ]
        },
    )

    monkeypatch.setattr(comm_mod, "SHORT_LINK_GRAPH_FILE", graph_file)
    monkeypatch.setattr(comm_mod, "DAILY_REPORTS_DIR", reports_dir)

    cm = CommunityManager(projects_dir=None)
    views, _ = cm._resolve_organic_views_and_elapsed_hours(
        "v8_ep09_mirror",
        "VID_MIRROR",
        {},
    )
    assert views == 520


def test_community_resolve_views_stale_upload_rec_zero_does_not_block_metrics(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    graph_file = tmp_path / "missing_graph.json"
    reports_dir = tmp_path / "daily"
    _write_json(
        reports_dir / "2026-11-21_studio_metrics.json",
        {
            "per_video_records": [
                {"project_id": "other_slug", "video_id": "VID_UPLOAD_ZERO", "views": 88},
            ]
        },
    )

    monkeypatch.setattr(comm_mod, "SHORT_LINK_GRAPH_FILE", graph_file)
    monkeypatch.setattr(comm_mod, "DAILY_REPORTS_DIR", reports_dir)

    cm = CommunityManager(projects_dir=None)
    views, _ = cm._resolve_organic_views_and_elapsed_hours(
        "v8_ep10_sleep",
        "VID_UPLOAD_ZERO",
        {"views": 0, "organic_views": 0},
    )
    assert views == 88


def test_community_resolve_views_explicit_known_organic_views_overrides_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    graph_file = tmp_path / "short_link_graph.json"
    reports_dir = tmp_path / "daily"
    _write_json(
        graph_file,
        {"nodes": [{"project_id": "v8_ep11_override", "video_id": "VID_OVR", "views": 999}]},
    )
    _write_json(
        reports_dir / "2026-11-21_studio_metrics.json",
        {"per_video_records": [{"project_id": "v8_ep11_override", "video_id": "VID_OVR", "views": 1200}]},
    )

    monkeypatch.setattr(comm_mod, "SHORT_LINK_GRAPH_FILE", graph_file)
    monkeypatch.setattr(comm_mod, "DAILY_REPORTS_DIR", reports_dir)

    cm = CommunityManager(projects_dir=None)
    views_15, _ = cm._resolve_organic_views_and_elapsed_hours(
        "v8_ep11_override",
        "VID_OVR",
        {"views": 500},
        known_organic_views=15,
    )
    assert views_15 == 15

    views_zero, _ = cm._resolve_organic_views_and_elapsed_hours(
        "v8_ep11_override",
        "VID_OVR",
        {"views": 500},
        known_organic_views=0,
    )
    assert views_zero == 0


# ---------------------------------------------------------------------------
# Patch 2: pipeline/studio/instagram_uploader.py
# ---------------------------------------------------------------------------


def test_detect_instagram_rate_limit_429_markers_and_normal_profile_clean() -> None:
    assert (
        detect_instagram_rate_limit_429(
            "www.instagram.com",
            "This page isn't working\nwww.instagram.com is currently unable to handle this request.\nHTTP ERROR 429",
            "https://www.instagram.com/allaboutbrain.official/?hl=en",
        )
        is not None
    )
    assert (
        detect_instagram_rate_limit_429(
            "www.instagram.com",
            "This page isn\u2019t working right now",
            "https://www.instagram.com/allaboutbrain.official/?hl=en",
        )
        is not None
    )
    assert (
        detect_instagram_rate_limit_429(
            "429 Too Many Requests",
            "Please wait before trying again.",
            "https://www.instagram.com/allaboutbrain.official/?hl=en",
        )
        is not None
    )
    assert (
        detect_instagram_rate_limit_429(
            "Error",
            "Rate limit exceeded for this endpoint.",
            "https://www.instagram.com/allaboutbrain.official/?hl=en",
        )
        is not None
    )
    assert (
        detect_instagram_rate_limit_429(
            "429",
            "Error 429",
            "chrome-error://chromewebdata/",
        )
        is not None
    )
    assert detect_instagram_rate_limit_429("", "429", "") is not None

    # Normal profile page (even containing the digits 429 in follower count) must return None
    assert (
        detect_instagram_rate_limit_429(
            "ALL ABOUT BRAIN (@allaboutbrain.official) • Instagram photos and videos",
            "allaboutbrain.official\n12 posts\n429 followers\n8 following\nReels\nTagged",
            "https://www.instagram.com/allaboutbrain.official/?hl=en",
        )
        is None
    )


def test_upload_instagram_reel_cdp_fails_fast_on_429_without_create_lookup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    vid = tmp_path / "reel.mp4"
    vid.write_bytes(b"\x00\x00\x00\x18ftypmp42")
    cov = tmp_path / "cover.png"
    Image.new("RGB", (1080, 1920), (16, 24, 36)).save(cov, format="PNG")

    eval_queries: list[str] = []
    closed_tabs: list[str] = []

    class _Fake429Client:
        def __init__(self, ws_url: str) -> None:
            self.ws_url = ws_url

        async def __aenter__(self) -> "_Fake429Client":
            return self

        async def __aexit__(self, *args: Any) -> None:
            return None

        async def send(self, method: str, params: dict[str, Any] | None = None, **kw: Any) -> dict[str, Any]:
            return {}

        async def eval(self, expression: str, **kw: Any) -> Any:
            eval_queries.append(expression)
            if "New post" in expression or "Create" in expression:
                raise AssertionError("Must fail fast on HTTP 429 BEFORE searching for Create (+) button!")
            return {
                "title": "www.instagram.com",
                "bodyText": "This page isn't working\nHTTP ERROR 429",
                "url": "https://www.instagram.com/allaboutbrain.official/?hl=en",
            }

        @staticmethod
        def cleanup_staged_bridge_files() -> None:
            return None

    async def _fast_sleep(_sec: float) -> None:
        return None

    monkeypatch.setattr(
        ig_mod,
        "open_leased_cdp_tab",
        lambda *a, **kw: {"id": "IG_TAB_429", "webSocketDebuggerUrl": "ws://127.0.0.1:9222/devtools/page/IG_TAB_429"},
    )
    monkeypatch.setattr(ig_mod, "release_and_close_leased_tab", lambda tid, **kw: closed_tabs.append(tid))
    monkeypatch.setattr(ig_mod, "DirectCDPClient", _Fake429Client)
    monkeypatch.setattr(ig_mod.asyncio, "sleep", _fast_sleep)

    res = asyncio.run(
        upload_instagram_reel_cdp(
            video_path=vid,
            cover_path=cov,
            caption="Why your brain remembers broken promises · DOI: 10.1016/j.cognition.2012.08.004",
            handle="@allaboutbrain.official",
            close_tab_on_finish=True,
        )
    )
    assert res["status"] == "rate_limited_429"
    assert res["handle"] == "allaboutbrain.official"
    assert "429" in res["reason"] or "working" in res["reason"]
    assert res["url"] == "https://www.instagram.com/allaboutbrain.official/?hl=en"
    assert len(eval_queries) == 1
    assert closed_tabs == ["IG_TAB_429"]


def test_upload_instagram_carousel_cdp_fails_fast_on_429(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    slides: list[Path] = []
    for idx in range(1, 3):
        sp = tmp_path / f"slide_{idx:02d}.png"
        Image.new("RGB", (1080, 1350), (16, 24, 36)).save(sp, format="PNG")
        slides.append(sp)

    class _FakeCarousel429Client:
        def __init__(self, ws_url: str) -> None:
            self.ws_url = ws_url

        async def __aenter__(self) -> "_FakeCarousel429Client":
            return self

        async def __aexit__(self, *args: Any) -> None:
            return None

        async def send(self, method: str, params: dict[str, Any] | None = None, **kw: Any) -> dict[str, Any]:
            return {}

        async def eval(self, expression: str, **kw: Any) -> Any:
            if "New post" in expression or "Create" in expression:
                raise AssertionError("Carousel uploader must fail fast on HTTP 429 before Create (+) lookup!")
            return {
                "title": "www.instagram.com",
                "bodyText": "This page isn't working\nHTTP ERROR 429",
                "url": "https://www.instagram.com/allaboutbrain.official/?hl=en",
                "inputs": [],
            }

        @staticmethod
        def cleanup_staged_bridge_files() -> None:
            return None

    async def _fast_sleep(_sec: float) -> None:
        return None

    monkeypatch.setattr(
        ig_mod,
        "open_leased_cdp_tab",
        lambda *a, **kw: {"id": "IG_CAR_429", "webSocketDebuggerUrl": "ws://127.0.0.1:9222/devtools/page/IG_CAR_429"},
    )
    monkeypatch.setattr(ig_mod, "release_and_close_leased_tab", lambda *a, **kw: True)
    monkeypatch.setattr(ig_mod, "DirectCDPClient", _FakeCarousel429Client)
    monkeypatch.setattr(ig_mod.asyncio, "sleep", _fast_sleep)

    res = asyncio.run(
        upload_instagram_carousel_cdp(
            slide_paths=slides,
            caption="Brain carousel · DOI: 10.1016/j.cognition.2012.08.004",
            handle="@allaboutbrain.official",
        )
    )
    assert res["status"] == "rate_limited_429"
    assert res["handle"] == "allaboutbrain.official"


def test_attach_instagram_file_input_with_polling_delayed_fallback_and_timeout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    vid = tmp_path / "video.mp4"
    vid.write_bytes(b"\x00\x00\x00\x18ftypmp42")
    sleep_calls: list[float] = []

    async def _record_sleep(sec: float) -> None:
        sleep_calls.append(sec)

    monkeypatch.setattr(ig_mod.asyncio, "sleep", _record_sleep)

    # 1. Succeeds on delayed 3rd poll when primary dialog input mounts late
    class _DelayedPrimaryClient:
        def __init__(self) -> None:
            self.calls: list[str] = []
            self.primary_tries = 0

        async def set_file_input(self, file_path: Path, selector: str) -> bool:
            assert file_path == vid
            self.calls.append(selector)
            if selector == "div[role='dialog'] input[type='file']":
                self.primary_tries += 1
                return self.primary_tries >= 3
            return False

    c_delay = _DelayedPrimaryClient()
    ok, matched = asyncio.run(
        attach_instagram_file_input_with_polling(
            c_delay,
            vid,
            selectors=INSTAGRAM_VIDEO_FILE_INPUT_SELECTORS,
            timeout_sec=12.0,
            poll_interval_sec=0.5,
        )
    )
    assert ok is True
    assert matched == "div[role='dialog'] input[type='file']"
    assert c_delay.primary_tries == 3
    assert len(sleep_calls) == 2

    # 2. Falls back cleanly to form input[type='file'] when dialog input is absent
    class _FallbackFormClient:
        async def set_file_input(self, file_path: Path, selector: str) -> bool:
            return selector == "form input[type='file']"

    ok_form, matched_form = asyncio.run(
        attach_instagram_file_input_with_polling(
            _FallbackFormClient(),
            vid,
            selectors=INSTAGRAM_VIDEO_FILE_INPUT_SELECTORS,
            timeout_sec=2.0,
            poll_interval_sec=0.5,
        )
    )
    assert (ok_form, matched_form) == (True, "form input[type='file']")

    # 3. Falls back cleanly to accept*='video' when dialog and form inputs are absent
    class _FallbackVideoAcceptClient:
        async def set_file_input(self, file_path: Path, selector: str) -> bool:
            return selector == "input[type='file'][accept*='video']"

    ok_acc, matched_acc = asyncio.run(
        attach_instagram_file_input_with_polling(
            _FallbackVideoAcceptClient(),
            vid,
            selectors=INSTAGRAM_VIDEO_FILE_INPUT_SELECTORS,
            timeout_sec=2.0,
            poll_interval_sec=0.5,
        )
    )
    assert (ok_acc, matched_acc) == (True, "input[type='file'][accept*='video']")

    # 4. Times out cleanly when no selector ever mounts
    class _NeverFoundClient:
        def __init__(self) -> None:
            self.attempts = 0

        async def set_file_input(self, file_path: Path, selector: str) -> bool:
            self.attempts += 1
            return False

    c_miss = _NeverFoundClient()
    ok_miss, matched_miss = asyncio.run(
        attach_instagram_file_input_with_polling(
            c_miss,
            vid,
            selectors=INSTAGRAM_IMAGE_FILE_INPUT_SELECTORS,
            timeout_sec=1.5,
            poll_interval_sec=0.5,
        )
    )
    assert (ok_miss, matched_miss) == (False, "")
    assert c_miss.attempts == 4 * len(INSTAGRAM_IMAGE_FILE_INPUT_SELECTORS)


# ---------------------------------------------------------------------------
# Patch 3: pipeline/studio/tiktok_uploader.py
# ---------------------------------------------------------------------------


def test_click_tiktok_confirm_modal_button_modal_scoping_and_captcha_refusal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _fast_sleep(_sec: float) -> None:
        return None

    monkeypatch.setattr(tk_mod.asyncio, "sleep", _fast_sleep)

    # 1. Clean confirmation modal inside [role="dialog"] -> dispatches trusted click & verifies JS modal scoping
    class _CleanModalClient:
        def __init__(self) -> None:
            self.eval_exprs: list[str] = []
            self.sent: list[tuple[str, dict[str, Any]]] = []

        async def eval(self, expression: str, **kw: Any) -> Any:
            self.eval_exprs.append(expression)
            return {
                "url": "https://www.tiktok.com/tiktokstudio/upload?lang=en",
                "modals": [
                    {"modalText": "Continue to post? Copyright check is still running.", "domCaptcha": []},
                ],
                "candidates": [
                    {
                        "priority": 0,
                        "label": "Post now",
                        "x": 620.0,
                        "y": 540.0,
                        "w": 120.0,
                        "h": 40.0,
                        "modalText": "Continue to post? Copyright check is still running.",
                        "domCaptcha": [],
                    }
                ],
            }

        async def send(self, method: str, params: dict[str, Any] | None = None, **kw: Any) -> dict[str, Any]:
            self.sent.append((method, dict(params or {})))
            return {}

    c_clean = _CleanModalClient()
    res = asyncio.run(click_tiktok_confirm_modal_button(c_clean))  # type: ignore[arg-type]
    assert res is not None
    assert res["clicked"] is True
    assert res["label"] == "Post now"
    assert res["x"] == pytest.approx(680.0)
    assert res["y"] == pytest.approx(560.0)
    # Verify trusted mouse event sequence
    mouse_types = [p.get("type") for m, p in c_clean.sent if m == "Input.dispatchMouseEvent"]
    assert mouse_types == ["mouseMoved", "mousePressed", "mouseReleased"]
    # Verify JS query strictly scopes buttons inside modal containers (NEVER document-level button search)
    js_src = c_clean.eval_exprs[0]
    assert json.dumps(TIKTOK_MODAL_CONTAINER_SELECTOR) in js_src
    assert "document.querySelectorAll(modalSel)" in js_src
    assert "modal.querySelectorAll(" in js_src
    assert "document.querySelectorAll('button" not in js_src

    # 2. Modal containing CAPTCHA text or DOM marker -> refuses click completely (0 mouse events)
    class _CaptchaModalClient:
        def __init__(self) -> None:
            self.sent: list[tuple[str, dict[str, Any]]] = []

        async def eval(self, expression: str, **kw: Any) -> Any:
            return {
                "url": "https://www.tiktok.com/tiktokstudio/upload?lang=en",
                "modals": [
                    {
                        "modalText": "Verify to continue — Drag the slider to fit the puzzle",
                        "domCaptcha": ["dom:#captcha-verify-container-main-page"],
                    }
                ],
                "candidates": [
                    {
                        "priority": 0,
                        "label": "Post now",
                        "x": 600.0,
                        "y": 500.0,
                        "w": 100.0,
                        "h": 40.0,
                        "modalText": "Verify to continue — Drag the slider to fit the puzzle",
                        "domCaptcha": ["dom:#captcha-verify-container-main-page"],
                    }
                ],
            }

        async def send(self, method: str, params: dict[str, Any] | None = None, **kw: Any) -> dict[str, Any]:
            self.sent.append((method, dict(params or {})))
            return {}

    c_cap = _CaptchaModalClient()
    res_cap = asyncio.run(click_tiktok_confirm_modal_button(c_cap))  # type: ignore[arg-type]
    assert res_cap is None
    assert c_cap.sent == []


def _make_tiktok_upload_test_harness(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    scenario: str,
) -> tuple[Path, Path, dict[str, Any]]:
    """Builds offline fixtures & mocked DirectCDPClient for TikTok post-submit loop scenarios."""
    vid = tmp_path / "tiktok_ep.mp4"
    vid.write_bytes(b"\x00\x00\x00\x18ftypmp42")
    cov = tmp_path / "tiktok_cover.png"
    Image.new("RGB", (1080, 1920), (16, 24, 36)).save(cov, format="PNG")

    state: dict[str, Any] = {
        "post_clicked": False,
        "post_poll_count": 0,
        "modal_clicks": [],
        "closed_tabs": [],
        "mouse_events_after_captcha": 0,
        "captcha_emitted": False,
    }

    class _FakeTikTokClient:
        def __init__(self, ws_url: str) -> None:
            self.ws_url = ws_url

        async def __aenter__(self) -> "_FakeTikTokClient":
            return self

        async def __aexit__(self, *args: Any) -> None:
            return None

        async def set_file_input(self, file_path: Path, selector: str) -> bool:
            return True

        async def send(self, method: str, params: dict[str, Any] | None = None, **kw: Any) -> dict[str, Any]:
            if state["captcha_emitted"] and method == "Input.dispatchMouseEvent":
                state["mouse_events_after_captcha"] += 1
            if method == "Page.captureScreenshot":
                return {
                    "data": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
                }
            return {}

        async def eval(self, expression: str, **kw: Any) -> Any:
            # 1. Page inspection (_inspect_tiktok_page)
            if "const captchaSelectors" in expression and "domCaptcha" in expression and "modalSel" not in expression:
                if not state["post_clicked"]:
                    return {
                        "url": "https://www.tiktok.com/tiktokstudio/upload?lang=en",
                        "title": "TikTok Studio",
                        "bodyText": "Uploaded",
                        "domCaptcha": [],
                    }
                state["post_poll_count"] += 1
                poll_n = state["post_poll_count"]
                if scenario == "delayed_modal":
                    # Polls 1..2: initial ~2.0s short poll (no modal yet)
                    # Polls 3..4: main loop iterations 1..2 (still processing, no modal yet)
                    # Poll 5: main loop iteration 3 -> delayed modal appears!
                    # Poll 6+: after modal clicked, redirects to /tiktokstudio/content!
                    if state["modal_clicks"]:
                        return {
                            "url": "https://www.tiktok.com/tiktokstudio/content",
                            "title": "TikTok Studio",
                            "bodyText": "Manage your posts",
                            "domCaptcha": [],
                        }
                    return {
                        "url": "https://www.tiktok.com/tiktokstudio/upload?lang=en",
                        "title": "TikTok Studio",
                        "bodyText": f"Publishing... poll {poll_n}",
                        "domCaptcha": [],
                    }
                if scenario == "captcha_during_publish":
                    if poll_n >= 3:
                        state["captcha_emitted"] = True
                        return {
                            "url": "https://www.tiktok.com/tiktokstudio/upload?lang=en",
                            "title": "TikTok Studio",
                            "bodyText": "Verify to continue\nDrag the slider to fit the puzzle",
                            "domCaptcha": ["dom:#tiktok-verify-ele"],
                        }
                    return {
                        "url": "https://www.tiktok.com/tiktokstudio/upload?lang=en",
                        "title": "TikTok Studio",
                        "bodyText": "Submitting...",
                        "domCaptcha": [],
                    }

            # 2. Upload ready check
            if "public-DraftEditor-content" in expression and "postEnabled" in expression:
                return True

            # 3. Caption editor / cover / visibility / AIGC checks
            if "video_visibility_container" in expression:
                return True
            if "aigc_container" in expression and "aria-checked" in expression:
                return True
            if "aigc_container" in expression and "getBoundingClientRect" in expression:
                return True
            if "cover_container" in expression:
                return None

            # 4. Post button click
            if 'post_video_button' in expression and "scrollIntoView" in expression:
                state["post_clicked"] = True
                return {"x": 500.0, "y": 800.0, "w": 120.0, "h": 44.0}

            # 5. Modal confirmation probe (click_tiktok_confirm_modal_button)
            if "modalSel" in expression and "modalSummaries" in expression:
                if state["captcha_emitted"]:
                    raise AssertionError("click_tiktok_confirm_modal_button must NEVER be called after CAPTCHA!")
                if scenario == "delayed_modal" and state["post_poll_count"] == 5 and not state["modal_clicks"]:
                    return {
                        "url": "https://www.tiktok.com/tiktokstudio/upload?lang=en",
                        "modals": [
                            {"modalText": "Continue to post? Copyright check is still in progress.", "domCaptcha": []}
                        ],
                        "candidates": [
                            {
                                "priority": 0,
                                "label": "Post now",
                                "x": 640.0,
                                "y": 520.0,
                                "w": 110.0,
                                "h": 38.0,
                                "modalText": "Continue to post? Copyright check is still in progress.",
                                "domCaptcha": [],
                            }
                        ],
                    }
                return {"url": "https://www.tiktok.com/tiktokstudio/upload?lang=en", "modals": [], "candidates": []}

            # 6. Profile video link lookup after publish
            if 'a[href*="/video/"]' in expression:
                return ["https://www.tiktok.com/@allaboutbrain_official/video/74999888777"]

            return None

    orig_click_modal = tk_mod.click_tiktok_confirm_modal_button

    async def _tracking_click_modal(client: Any, labels: tuple[str, ...] = tk_mod.TIKTOK_CONFIRM_MODAL_LABELS):
        out = await orig_click_modal(client, labels=labels)
        if out and out.get("clicked"):
            state["modal_clicks"].append(out)
        return out

    async def _fast_sleep(_sec: float) -> None:
        return None

    monkeypatch.setattr(
        tk_mod,
        "open_leased_cdp_tab",
        lambda *a, **kw: {"id": "TT_TAB_1", "webSocketDebuggerUrl": "ws://127.0.0.1:9222/devtools/page/TT_TAB_1"},
    )
    monkeypatch.setattr(tk_mod, "renew_tab_lease", lambda *a, **kw: True)
    monkeypatch.setattr(tk_mod, "release_and_close_leased_tab", lambda tid, **kw: state["closed_tabs"].append(tid))
    monkeypatch.setattr(tk_mod, "DirectCDPClient", _FakeTikTokClient)
    monkeypatch.setattr(tk_mod, "click_tiktok_confirm_modal_button", _tracking_click_modal)
    monkeypatch.setattr(tk_mod.asyncio, "sleep", _fast_sleep)

    return vid, cov, state


def test_tiktok_upload_delayed_confirmation_modal_in_publish_loop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    vid, cov, state = _make_tiktok_upload_test_harness(tmp_path, monkeypatch, scenario="delayed_modal")

    res = asyncio.run(
        upload_tiktok_video_cdp(
            video_path=vid,
            cover_path=cov,
            caption="Why your brain deletes room memories · DOI: 10.1080/17470218.2011.571267 #neuroscience",
            duration_override_sec=72.4,
            close_tab_on_finish=True,
        )
    )
    assert res["status"] == "published"
    assert res["video_id"] == "74999888777"
    assert len(state["modal_clicks"]) == 1
    assert state["modal_clicks"][0]["label"] == "Post now"
    # Delayed modal appeared on poll 5 (>2.0s after submit, iteration 3 of main publish loop)
    assert state["post_poll_count"] == 6
    assert state["closed_tabs"] == ["TT_TAB_1"]


def test_tiktok_upload_captcha_during_publish_loop_halts_without_modal_click(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    vid, cov, state = _make_tiktok_upload_test_harness(tmp_path, monkeypatch, scenario="captcha_during_publish")
    shot_path = tmp_path / "captcha_shot.png"

    res = asyncio.run(
        upload_tiktok_video_cdp(
            video_path=vid,
            cover_path=cov,
            caption="Why your brain deletes room memories · DOI: 10.1080/17470218.2011.571267 #neuroscience",
            duration_override_sec=72.4,
            verification_screenshot_path=shot_path,
            close_tab_on_finish=True,
        )
    )
    assert res["status"] == "captcha_verification_needed"
    assert res["target_id"] == "TT_TAB_1"
    assert any("slider" in m or "tiktok-verify-ele" in m for m in res["markers"])
    assert shot_path.is_file()
    assert state["modal_clicks"] == []
    assert state["mouse_events_after_captcha"] == 0
    # Leased tab MUST stay open for manual user inspection/verification
    assert state["closed_tabs"] == []
