"""
Unit tests for Workstream 2:
- `pipeline/studio/community_posts.py`: `parse_schedule_et` (`15`-min increments, `ET -> UTC`), `convert_utc_to_picker_local` (`(GMT+0000)` & `(GMT-0500)`), and `YouTubeCommunityPostManager` `dry_run=True`
- `pipeline/studio/comments_inbox.py`: `BLOCK_WATCH_SHORTS_NAVIGATION_JS` zero-playback lock, `validate_reply_text_safety`, `StudioCommentsInboxManager` `dry_run=True` & `apply_approved_replies` zero-approved noop
- `pipeline/studio/uploader.py`: `lock_auto_dubbing_off(dry_run=True)` and `inspect_channel_home_shelves(dry_run=True)`
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from pipeline.publish import build_youtube_community_quiz_payload
from pipeline.studio.comments_inbox import (
    BLOCK_WATCH_SHORTS_NAVIGATION_JS,
    StudioCommentsInboxManager,
    compute_comment_key,
    synthesize_followup_reply_draft,
    validate_reply_text_safety,
)
from pipeline.studio.community_posts import (
    YouTubeCommunityPostManager,
    convert_utc_to_picker_local,
    parse_schedule_et,
)
from pipeline.studio.uploader import StudioUploader


def test_parse_schedule_et_and_picker_timezone_conversion() -> None:
    dt_et = parse_schedule_et("2026-11-15 16:00 ET", enforce_future=False)
    assert dt_et.hour == 16 and dt_et.minute == 0
    dt_utc = dt_et.astimezone(timezone.utc)
    # Nov 15 is EST (UTC-5) -> 16:00 ET == 21:00 UTC
    assert dt_utc == datetime(2026, 11, 15, 21, 0, tzinfo=timezone.utc)

    spec_gmt0 = convert_utc_to_picker_local(dt_utc, "(GMT+0000) Local Time")
    assert spec_gmt0["date_label_en"] == "Nov 15, 2026"
    assert spec_gmt0["time_12h"] == "9:00 PM"
    assert spec_gmt0["time_24h"] == "21:00"

    spec_est = convert_utc_to_picker_local(dt_utc, "(GMT-0500) Eastern Time")
    assert spec_est["date_label_en"] == "Nov 15, 2026"
    assert spec_est["time_12h"] == "4:00 PM"
    assert spec_est["time_24h"] == "16:00"

    with pytest.raises(ValueError, match="15-minute increments"):
        parse_schedule_et("2026-11-15 16:07 ET", enforce_future=False)


def test_community_post_manager_dry_run(tmp_path: Path) -> None:
    p_dir = tmp_path / "v8_ep08_capgras_quiz_dryrun"
    (p_dir / "02_script").mkdir(parents=True, exist_ok=True)
    (p_dir / "06_publish" / "multi_platform_bundle").mkdir(parents=True, exist_ok=True)
    (p_dir / "02_script" / "script.json").write_text(
        json.dumps(
            {
                "title": "Why Your Brain Calls Loved Ones Imposters",
                "doi": "10.1098/rspb.1997.0092",
                "sentences": [
                    {"sentence_index": 1, "text": "He swore his own parents were imposters!"},
                    {"sentence_index": 2, "text": "His fusiform face area disconnected from the amygdala."},
                ],
            }
        ),
        encoding="utf-8",
    )
    (p_dir / "06_publish" / "metadata.json").write_text(
        json.dumps(
            {
                "title": "Why Your Brain Calls Loved Ones Imposters",
                "description": "Hirstein & Ramachandran (1997) DOI: 10.1098/rspb.1997.0092",
            }
        ),
        encoding="utf-8",
    )
    payload = build_youtube_community_quiz_payload(p_dir)
    (p_dir / "06_publish" / "multi_platform_bundle" / "youtube_quiz_post.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )

    mgr = YouTubeCommunityPostManager(cdp_port=9222)
    res = mgr.publish_or_schedule_quiz(p_dir, schedule_et="2026-12-20 16:00 ET", dry_run=True)
    assert res["status"] == "dry_run"
    assert res["mode"] == "scheduled"
    assert res["picker_preview_utc"]["time_12h"] == "9:00 PM"


def test_zero_playback_comments_inbox_guards_and_staging(tmp_path: Path) -> None:
    assert "/watch" in BLOCK_WATCH_SHORTS_NAVIGATION_JS
    assert "/shorts/" in BLOCK_WATCH_SHORTS_NAVIGATION_JS
    assert "ytcp-comment-video-thumbnail" in BLOCK_WATCH_SHORTS_NAVIGATION_JS

    draft = synthesize_followup_reply_draft(
        "Wait so the face recognition part still works?!",
        "Why Your Brain Calls Loved Ones Imposters",
    )
    assert draft.endswith("?")
    assert validate_reply_text_safety(draft) == []
    assert validate_reply_text_safety("Comment 'BRAIN' below and I'll DM you the PDF!") != []

    staging_file = tmp_path / "pending_comment_replies.json"
    mgr = StudioCommentsInboxManager(cdp_port=9222, staging_path=staging_file)

    scan_dry = mgr.scan_unreplied_comments(dry_run=True)
    assert scan_dry["status"] == "dry_run"
    assert scan_dry["self_views_triggered"] == 0

    # Seed unapproved item -> apply_approved_replies should be a safe zero-action noop without browser launch
    ck = compute_comment_key("@viewer1", "Capgras Short", "Incredible brain study!")
    staging_file.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "items": [
                    {
                        "comment_key": ck,
                        "author": "@viewer1",
                        "video_title": "Capgras Short",
                        "comment_text": "Incredible brain study!",
                        "draft_reply": draft,
                        "approved": False,
                        "applied": False,
                    }
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    app_noop = mgr.apply_approved_replies(dry_run=False)
    assert app_noop["status"] == "noop_zero_approved"
    assert app_noop["applied_count"] == 0
    assert app_noop["self_views_triggered"] == 0


def test_uploader_auto_dubbing_lock_and_home_shelves_dry_run() -> None:
    up = StudioUploader(cdp_port=9222)
    dub = up.lock_auto_dubbing_off(dry_run=True)
    assert dub["dry_run"] is True
    assert dub["lock_action"] == "dry_run"
    assert dub["locked_off"] is True

    shelves = up.inspect_channel_home_shelves(dry_run=True)
    assert shelves["status"] == "dry_run"
    assert shelves["channel_trailer_untouched"] is True
    assert shelves["live_studio_mutated"] is False


def test_community_quiz_schedule_action_menu_scoped_to_composer_dialog_and_fail_fast(tmp_path: Path, monkeypatch) -> None:
    """Regression for studio-quiz `no_dtp` bug: Action menu MUST be scoped inside the active composer dialog (never feed posts' '...' Delete menu) and fail fast if Schedule picker fails to mount."""
    import asyncio
    from contextlib import asynccontextmanager
    import inspect
    import pipeline.studio.community_posts as cp_mod

    src = inspect.getsource(cp_mod.YouTubeCommunityPostManager.publish_or_schedule_quiz_async)
    assert "__queryAllDeep('button', composerDlg)" in src
    assert "menuBtns[menuBtns.length - 1]" not in src
    assert "composer_action_menu_not_found" in src
    assert "schedule_post_menu_item_not_found" in src

    p_dir = tmp_path / "v8_ep12_quiz_mock"
    (p_dir / "02_script").mkdir(parents=True, exist_ok=True)
    (p_dir / "06_publish" / "multi_platform_bundle").mkdir(parents=True, exist_ok=True)
    (p_dir / "02_script" / "script.json").write_text(
        json.dumps(
            {
                "title": "How Walking Through Doorways Wipes Your Memory",
                "doi": "10.1080/17470218.2011.571267",
                "sentences": [
                    {"sentence_index": 1, "text": "Walking through a doorway jumped errors from 23% to 28%."},
                ],
            }
        ),
        encoding="utf-8",
    )
    (p_dir / "06_publish" / "metadata.json").write_text(
        json.dumps(
            {
                "title": "How Walking Through Doorways Wipes Your Memory",
                "description": "Radvansky et al. (2011) DOI: 10.1080/17470218.2011.571267",
            }
        ),
        encoding="utf-8",
    )
    payload = build_youtube_community_quiz_payload(p_dir)
    (p_dir / "06_publish" / "multi_platform_bundle" / "youtube_quiz_post.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )

    async def _fast_sleep(_sec: float) -> None:
        return None

    monkeypatch.setattr(cp_mod.asyncio, "sleep", _fast_sleep)

    async def _noop_focus(_client) -> None:
        return None

    monkeypatch.setattr(cp_mod, "enable_background_focus_emulation", _noop_focus)

    class _FakeCDPClient:
        def __init__(self, *, fail_schedule_item: bool = False) -> None:
            self.fail_schedule_item = fail_schedule_item
            self.eval_scripts: list[str] = []
            self.sent_cmds: list[tuple[str, dict]] = []

        async def send(self, method: str, params: dict | None = None):
            self.sent_cmds.append((method, dict(params or {})))
            if method == "Page.captureScreenshot":
                return {"data": ""}
            return {}

        async def eval(self, expr: str):
            self.eval_scripts.append(expr)
            if "quizOpen" in expr:
                return {"quizOpen": True}
            if "add answer|add another" in expr:
                return {"count": 4, "addBtn": None}
            if "expected_4_option_rows_got_" in expr:
                return {"ok": True, "questionSet": payload["question"], "optionValues": ["a", "b", "c", "d"], "explanationLen": 80}
            if "composer_action_menu_not_found" in expr:
                return {"ok": True, "countInDlg": 1, "x": 868, "y": 938}
            if "schedule_post_menu_item_not_found" in expr:
                if self.fail_schedule_item:
                    return {"ok": False, "err": "schedule_post_menu_item_not_found", "visibleItems": ["Delete"]}
                return {"ok": True, "tag": "YTD-MENU-SERVICE-ITEM-RENDERER", "text": "Schedule post"}
            if "tzLabel:" in expr:
                return {"ok": True, "tzLabel": "(GMT+0000) Local Time"}
            if "no_calendar_picker" in expr:
                return {"ok": True, "focusedInput": True, "labelAfterForm": "Dec 20, 2026"}
            if "targetDayStr" in expr:
                return "Dec 20, 2026"
            if "time_item_not_found" in expr:
                return {"ok": True, "timeAfter": "9:00 PM"}
            if "expected_schedule_button_got_" in expr:
                return {"ok": True, "clickedLabel": "Schedule"}
            if "matchingRows" in expr:
                return {"found": True, "matchingRows": [payload["question"]], "bodyPreview": payload["question"]}
            return None

    # 1) Fail-fast when Schedule post menu item is missing (e.g. wrong menu opened)
    fake_fail = _FakeCDPClient(fail_schedule_item=True)

    @asynccontextmanager
    async def _lease_fail(*_args, **_kwargs):
        yield fake_fail, "T1", "test"

    monkeypatch.setattr(cp_mod, "leased_cdp_tab", _lease_fail)
    mgr = YouTubeCommunityPostManager(cdp_port=9222)
    with pytest.raises(RuntimeError, match="schedule_post_menu_item_not_found"):
        asyncio.run(mgr.publish_or_schedule_quiz_async(p_dir, schedule_et="2026-12-20 16:00 ET", dry_run=False))

    # 2) Happy path with composer-scoped Action menu opening ytd-date-time-picker-renderer
    fake_ok = _FakeCDPClient(fail_schedule_item=False)

    @asynccontextmanager
    async def _lease_ok(*_args, **_kwargs):
        yield fake_ok, "T2", "test"

    monkeypatch.setattr(cp_mod, "leased_cdp_tab", _lease_ok)
    receipt = asyncio.run(mgr.publish_or_schedule_quiz_async(p_dir, schedule_et="2026-12-20 16:00 ET", dry_run=False))
    assert receipt["status"] == "scheduled"
    assert receipt["verified_on_studio_posts"] is True
    assert receipt["picker_applied"]["menu_open_result"]["countInDlg"] == 1
    assert receipt["picker_applied"]["schedule_menu_click"]["text"] == "Schedule post"
    assert receipt["picker_applied"]["time_label_after"] == "9:00 PM"
    assert any(m == "Input.dispatchKeyEvent" and p.get("key") == "Enter" for m, p in fake_ok.sent_cmds)

