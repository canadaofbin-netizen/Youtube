"""
Regression test suite for Rule R75 (`tests/test_studio_seed_hygiene_and_playlist_ban.py`):
1. Permanent Codebase Playlist Ban (`STUDIO_PLAYLISTS_ENABLED is False`, `_assign_pillar_playlist_on_edit_page` immediate no-op, zero playlist-missing warnings in `reporter.py`).
2. Triple BCI Tag & Channel Keyword Purification (`CHANNEL_CLEAN_KEYWORDS`, `BANNED_OFF_TOPIC_TECH_TAGS`, `DEFAULT_VIDEO_CATEGORY = "Education"`, `DEFAULT_FALLBACK_PILLAR = "brain_mysteries"`, `build_clean_episode_tags`, `validate_episode_tags_hygiene`, `#shorts` routing).
3. Zero Creator Self-Bounce (`AVD = 0.0s`) Architecture (`BLOCKED_NON_PUBLIC`, `DEFERRED_SEED_PROTECT`, `PRE_DOCUMENT_AUTOPLAY_KILL_JS` before `Page.navigate`, `ALLOW_WATCH_PAGE_FALLBACK is False`, scheduler zero immediate pin).
4. Scheduling Warmup (`MIN_SCHEDULE_WARMUP_MINUTES = 180`), Instant-Public Ban (`allow_instant_public=False`), Pre/Post-Release Metadata Freeze (`3.0h` / `24.0h`), Visibility Monotonicity (`validate_visibility_transition`), and `< 88s` Duration Gate with Pre-R75 Grandfathering (`PRE_R75_DURATION_GRANDFATHER_PROJECTS`).
"""

from __future__ import annotations

import asyncio
import inspect
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pytest

from pipeline import config as cfg
from pipeline.publish import build_clean_episode_tags, validate_episode_tags_hygiene
from pipeline.studio import config as studio_cfg
from pipeline.studio.community import PRE_DOCUMENT_AUTOPLAY_KILL_JS, CommunityManager
from pipeline.studio.reporter import StudioAnalyticsReporter, normalize_pillar_id
from pipeline.studio.sanitize_scheduled_metadata import sanitize_scheduled_projects
from pipeline.studio.short_linker import ShortLinkGraph, StudioShortLinker
from pipeline.studio.unschedule_retired_shorts import _switch_single_scheduled_to_private
from pipeline.studio.uploader import StudioUploader


def test_r75_permanent_playlist_ban_constants_and_noop_dom_helper(tmp_path: Path) -> None:
    assert studio_cfg.STUDIO_PLAYLISTS_ENABLED is False

    class _ExplodingClient:
        async def eval(self, _js: str) -> Any:
            raise AssertionError("_assign_pillar_playlist_on_edit_page must NEVER touch DOM under R75!")

        async def click(self, _sel: Any) -> Any:
            raise AssertionError("_assign_pillar_playlist_on_edit_page must NEVER click DOM under R75!")

    linker = StudioShortLinker(projects_dir=tmp_path, graph_file=tmp_path / "graph.json")
    res = asyncio.run(linker._assign_pillar_playlist_on_edit_page(_ExplodingClient(), "brain_health"))  # type: ignore[arg-type]
    assert res == {
        "assigned": False,
        "playlist_title": None,
        "skipped_reason": "playlists_permanently_disabled_r75",
    }

    # Verify StudioShortLinker defaults both assign_playlist and assign_playlists to False
    sig_single = inspect.signature(StudioShortLinker.link_single_video)
    sig_run = inspect.signature(StudioShortLinker.run)
    assert sig_single.parameters["assign_playlist"].default is False
    assert sig_run.parameters["assign_playlists"].default is False

    # Verify reporter.py contains zero '⚠️ 미배정' playlist warnings or '--assign-playlists' suggestions
    rep_src = inspect.getsource(StudioAnalyticsReporter)
    assert "⚠️ 미배정" not in rep_src
    assert "--assign-playlists" not in rep_src
    assert normalize_pillar_id(None) == "brain_mysteries"


def test_r75_channel_keywords_tag_hygiene_and_education_category() -> None:
    assert studio_cfg.DEFAULT_VIDEO_CATEGORY == "Education"
    assert studio_cfg.DEFAULT_FALLBACK_PILLAR == "brain_mysteries"
    assert len(studio_cfg.CHANNEL_CLEAN_KEYWORDS) == 15
    for kw in studio_cfg.CHANNEL_CLEAN_KEYWORDS:
        assert kw.strip().lower() not in studio_cfg.BANNED_OFF_TOPIC_TECH_TAGS

    tags_sleep = build_clean_episode_tags(
        pillar="brain_basics",
        everyday_domain="sleep",
        title="How Trying to Fall Asleep Backfires",
        brain_regions=["hippocampus", "prefrontal cortex"],
    )
    assert 8 <= len(tags_sleep) <= 12
    assert "shorts" in [t.lower() for t in tags_sleep]
    assert validate_episode_tags_hygiene(tags_sleep, "brain_basics", raise_on_error=False) == []

    # Polluted BCI/AI/neurotech tags MUST fail on any non-bci_tech pillar
    polluted = ["psychology", "neuroscience", "BCI", "neural interface", "AI", "neurotech", "brain science", "shorts"]
    issues = validate_episode_tags_hygiene(polluted, "brain_health", raise_on_error=False)
    assert issues != []
    with pytest.raises(ValueError, match=r"(?i)r75"):
        validate_episode_tags_hygiene(polluted, "brain_health", raise_on_error=True)

    # Genuine bci_tech pillar allows BCI tags when count & shorts requirements are met
    bci_ok = [
        "psychology",
        "neuroscience",
        "brain science",
        "human behavior",
        "BCI",
        "neural interface",
        "cognitive psychology",
        "shorts",
    ]
    assert validate_episode_tags_hygiene(bci_ok, "bci_tech", raise_on_error=False) == []

    dry_settings = StudioUploader(cdp_port=9222).configure_studio_localization(dry_run=True)
    assert dry_settings["upload_default_title"] == ""
    assert dry_settings["upload_default_description"] == ""
    assert dry_settings["upload_default_tags"] == []
    assert dry_settings["category"] == "Education"


def test_r75_on_disk_metadata_and_live_purification_receipts() -> None:
    root = cfg.WORKSPACE_ROOT
    projects_dir = cfg.PROJECTS_DIR
    for pid in (
        "v8_pilot_03_marshmallow_trust_previs",
        "v8_ep04_patient_sm_fearless_amygdala",
        "v8_ep05_ucl_tickle_delay_robot",
        "v8_ep06_bedtime_todo_list_sleep",
    ):
        meta = json.loads((projects_dir / pid / "06_publish" / "metadata.json").read_text(encoding="utf-8"))
        assert meta["category"] == "Education"
        assert meta["hashtags"] == ["#shorts"]
        assert str(meta["description"]).endswith("#shorts")
        assert validate_episode_tags_hygiene(meta["tags"], meta["pillar"], raise_on_error=False) == []

    pl_receipt = root / "reports" / "studio_playlist_purge_receipt.json"
    assert pl_receipt.is_file()
    pl_doc = json.loads(pl_receipt.read_text(encoding="utf-8"))
    assert pl_doc["status"] == "purged_zero_verified"
    assert pl_doc["remaining_count"] == 0
    assert pl_doc["deleted_count"] == 7

    vid_receipt = root / "reports" / "studio_r75_video_tag_purification_receipt.json"
    assert vid_receipt.is_file()
    vid_doc = json.loads(vid_receipt.read_text(encoding="utf-8"))
    assert vid_doc["status"] == "verified_live"
    assert vid_doc["protected_untouched_seed_video_id"] == "7W8zIOMKPrQ"
    assert vid_doc["videos_purified_count"] == 3
    for v_row in vid_doc["videos"]:
        assert v_row["after_category"] == "Education"
        assert v_row["has_shorts_hashtag"] is True
        assert validate_episode_tags_hygiene(v_row["after_tags"], "brain_mysteries", raise_on_error=False) == []


def test_r75_upload_instant_public_ban_and_3h_schedule_warmup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p_dir = tmp_path / "v8_r75_sched_proj"
    for sub in ("05_assembly", "06_publish"):
        (p_dir / sub).mkdir(parents=True, exist_ok=True)
    (p_dir / "00_project_manifest.json").write_text(
        json.dumps({"project_id": "v8_r75_sched_proj", "pillar": "brain_mysteries"}, indent=2),
        encoding="utf-8",
    )
    (p_dir / "05_assembly" / "final_shorts_1080x1920.mp4").write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"\x01" * 2048)
    (p_dir / "06_publish" / "metadata.json").write_text(
        json.dumps(
            {
                "title": "Why Your Brain Freezes at Doorways",
                "pillar": "brain_mysteries",
                "description": "Doorway memory reset story.\n\n#shorts",
                "doi": "10.1080/17470218.2011.571267",
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    uploader = StudioUploader(cdp_port=9222, projects_dir=tmp_path)

    # 1. Instant visibility="public" is banned unless allow_instant_public=True
    with pytest.raises(ValueError, match="allow_instant_public"):
        uploader.prepare_upload_payload("v8_r75_sched_proj", visibility="public", skip_qa_gate=True)

    allowed_pub = uploader.prepare_upload_payload(
        "v8_r75_sched_proj",
        visibility="public",
        allow_instant_public=True,
        skip_qa_gate=True,
    )
    assert allowed_pub["visibility"] == "public"
    assert allowed_pub["category"] == "Education"
    assert validate_episode_tags_hygiene(allowed_pub["tags"], "brain_mysteries", raise_on_error=False) == []

    # 2. MIN_SCHEDULE_WARMUP_MINUTES == 180 (3.0h):
    # At 17:30 ET (+2.0h before Slot 4 19:30 ET < 3.0h warmup), auto-date roll MUST roll to tomorrow!
    et = ZoneInfo("America/New_York")
    fake_now_et = datetime(2026, 11, 15, 17, 30, tzinfo=et)

    class _FakeDateTime(datetime):
        @classmethod
        def now(cls, tz=None):  # type: ignore[override]
            if tz is None:
                return fake_now_et.replace(tzinfo=None)
            return fake_now_et.astimezone(tz)

    import pipeline.studio.uploader as up_mod

    monkeypatch.setattr(up_mod, "datetime", _FakeDateTime)

    rolled_payload = uploader.prepare_upload_payload(
        "v8_r75_sched_proj",
        slot_id=4,
        visibility="scheduled",
        skip_qa_gate=True,
    )
    assert rolled_payload["target_date"] == "2026-11-16"
    assert rolled_payload["scheduled_time_et"].startswith("2026-11-16 19:30")

    # At 15:00 ET (+4.5h before Slot 4 19:30 ET >= 3.0h warmup), same-day 19:30 ET is preserved!
    fake_now_early = datetime(2026, 11, 15, 15, 0, tzinfo=et)

    class _FakeEarlyDateTime(datetime):
        @classmethod
        def now(cls, tz=None):  # type: ignore[override]
            if tz is None:
                return fake_now_early.replace(tzinfo=None)
            return fake_now_early.astimezone(tz)

    monkeypatch.setattr(up_mod, "datetime", _FakeEarlyDateTime)
    same_day_payload = uploader.prepare_upload_payload(
        "v8_r75_sched_proj",
        slot_id=4,
        visibility="scheduled",
        skip_qa_gate=True,
    )
    assert same_day_payload["target_date"] == "2026-11-15"
    assert same_day_payload["scheduled_time_et"].startswith("2026-11-15 19:30")


def test_r75_zero_self_bounce_pin_guards_and_watch_fallback_disabled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # 1. PRE_DOCUMENT_AUTOPLAY_KILL_JS overrides HTMLMediaElement.prototype.play before frame 0
    assert "HTMLMediaElement.prototype.play" in PRE_DOCUMENT_AUTOPLAY_KILL_JS
    assert "this.pause()" in PRE_DOCUMENT_AUTOPLAY_KILL_JS
    comm_src = inspect.getsource(CommunityManager)
    assert "Page.addScriptToEvaluateOnNewDocument" in comm_src

    # 2. Scheduler never calls post_and_pin_comment right after Scheduled upload
    import pipeline.studio_batch_100_scheduler as sched_mod

    sched_src = inspect.getsource(sched_mod)
    assert "post_and_pin_comment(" not in sched_src

    # 3. reporter.py ALLOW_WATCH_PAGE_FALLBACK is False and _fetch_watch_page_fallback returns {} without HTTP
    assert studio_cfg.ALLOW_WATCH_PAGE_FALLBACK is False
    rep_gen = StudioAnalyticsReporter(cdp_port=9222, reports_dir=tmp_path / "reports")
    assert rep_gen._fetch_watch_page_fallback("7W8zIOMKPrQ") == {}

    # 4. CommunityManager.post_and_pin_comment blocks Scheduled/Unlisted & defers <100 views / <12h Public WITHOUT opening tabs
    pid_sched = "v8_r75_pin_sched"
    pid_pub_fresh = "v8_r75_pin_fresh_pub"
    for pid in (pid_sched, pid_pub_fresh):
        for sub in ("02_script", "06_publish"):
            (tmp_path / pid / sub).mkdir(parents=True, exist_ok=True)
        (tmp_path / pid / "02_script" / "script.json").write_text(
            json.dumps(
                {
                    "schema": 8,
                    "style_profile": "expressive_25d_v8",
                    "format_profile": "shorts_expressive_v8",
                    "title": "Why Your Brain Freezes at Doorways",
                    "doi": "10.1080/17470218.2011.571267",
                    "debate_question": "Have you ever walked into a kitchen and forgotten why you went in?",
                    "sentences": ["You walk through a doorway and forget everything!"],
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        (tmp_path / pid / "06_publish" / "metadata.json").write_text(
            json.dumps({"title": "Why Your Brain Freezes at Doorways", "doi": "10.1080/17470218.2011.571267"}, indent=2),
            encoding="utf-8",
        )

    now_ref = datetime(2026, 11, 12, 12, 0, tzinfo=timezone.utc)
    (tmp_path / pid_sched / "06_publish" / "upload_receipt.json").write_text(
        json.dumps({"status": "scheduled", "visibility": "schedule", "video_id": "SchedVid001"}, indent=2),
        encoding="utf-8",
    )
    (tmp_path / pid_pub_fresh / "06_publish" / "upload_receipt.json").write_text(
        json.dumps(
            {
                "status": "published_public",
                "visibility": "public",
                "video_id": "FreshPub001",
                "published_at_utc": (now_ref - timedelta(hours=3.5)).isoformat(),
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    cm = CommunityManager(projects_dir=tmp_path)
    monkeypatch.setattr(
        cm.session,
        "open_temp_direct_client",
        lambda *_a, **_kw: (_ for _ in ()).throw(AssertionError("Must NOT open any browser tab!")),
    )

    res_sched = cm.post_and_pin_comment(pid_sched, dry_run=False, now_utc=now_ref)
    assert res_sched["status"] == "BLOCKED_NON_PUBLIC"
    assert res_sched["pinned"] is False

    res_fresh = cm.post_and_pin_comment(
        pid_pub_fresh,
        dry_run=False,
        known_organic_views=12,
        now_utc=now_ref,
    )
    assert res_fresh["status"] == "DEFERRED_SEED_PROTECT"
    assert res_fresh["pinned"] is False
    assert res_fresh["organic_views"] == 12


def test_r75_metadata_freeze_windows_visibility_monotonicity_and_duration_gate(tmp_path: Path) -> None:
    now_ref = datetime(2026, 11, 12, 22, 0, tzinfo=timezone.utc)
    graph = ShortLinkGraph(projects_dir=tmp_path, now_utc=now_ref)

    # 1. Pre-release 3.0h freeze on Scheduled video (+2.0h until go-live -> locked; +5.0h -> unlocked)
    locked_sched, reason_sched = graph.is_seed_locked(
        {
            "visibility": "scheduled",
            "scheduled_at_utc": (now_ref + timedelta(hours=2.0)).isoformat(),
        }
    )
    assert locked_sched is True and "pre_release_freeze" in reason_sched

    unlocked_sched, _ = graph.is_seed_locked(
        {
            "visibility": "scheduled",
            "scheduled_at_utc": (now_ref + timedelta(hours=5.0)).isoformat(),
        }
    )
    assert unlocked_sched is False

    # 2. Post-release 24.0h freeze on Public video (+6.0h -> locked; +26.0h -> unlocked)
    locked_pub, reason_pub = graph.is_seed_locked(
        {
            "visibility": "public",
            "published_at_utc": (now_ref - timedelta(hours=6.0)).isoformat(),
        }
    )
    assert locked_pub is True and "24.0h" in reason_pub

    unlocked_pub, _ = graph.is_seed_locked(
        {
            "visibility": "public",
            "published_at_utc": (now_ref - timedelta(hours=26.0)).isoformat(),
        }
    )
    assert unlocked_pub is False

    # 3. sanitize_scheduled_projects skips Scheduled videos within 3.0h of go-live
    pid_imminent = "v8_imminent_sched"
    (tmp_path / pid_imminent / "06_publish").mkdir(parents=True, exist_ok=True)
    (tmp_path / pid_imminent / "02_script").mkdir(parents=True, exist_ok=True)
    (tmp_path / pid_imminent / "06_publish" / "upload_receipt.json").write_text(
        json.dumps(
            {
                "status": "scheduled",
                "visibility": "schedule",
                "video_id": "Imminent001",
                "scheduled_at_utc": (now_ref + timedelta(hours=1.5)).isoformat(),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (tmp_path / pid_imminent / "06_publish" / "metadata.json").write_text(
        json.dumps({"title": "Why Your Brain Freezes at Doorways", "description": "Story.\n\n#shorts"}, indent=2),
        encoding="utf-8",
    )
    (tmp_path / pid_imminent / "02_script" / "script.json").write_text(
        json.dumps({"schema": 8, "title": "Why Your Brain Freezes at Doorways", "sentences": ["Hello!"]}, indent=2),
        encoding="utf-8",
    )
    san_res = sanitize_scheduled_projects(projects_dir=tmp_path, dry_run=True, now_utc=now_ref)
    assert any(s.get("project_id") == pid_imminent and "freeze" in str(s.get("reason")) for s in san_res["skipped"])

    # 4. Visibility monotonicity: public -> unlisted / public -> private blocked unless allow_emergency_demote=True
    with pytest.raises(ValueError, match="R75"):
        studio_cfg.validate_visibility_transition("public", "unlisted")
    with pytest.raises(ValueError, match="R75"):
        studio_cfg.validate_visibility_transition("public", "private")
    assert studio_cfg.validate_visibility_transition("public", "unlisted", allow_emergency_demote=True) is True
    assert studio_cfg.validate_visibility_transition("scheduled", "public") is True

    with pytest.raises(ValueError, match="R75"):
        asyncio.run(
            _switch_single_scheduled_to_private(
                object(),
                project_id="v8_test_pub",
                video_id="CustomPub01",
                current_visibility="public",
            )
        )

    # 5. < 88.0s R75 duration gate for new v8 projects vs <= 120.0s grandfathering for v8_pilot_01..03 & v8_ep04..06
    assert cfg.SHORTS_EXPRESSIVE_V8_DURATION_TARGET_RANGE_SEC == (62.0, 86.0)
    assert cfg.SHORTS_EXPRESSIVE_V8_R75_MAX_SEC == 88.0
    assert cfg.SHORTS_EXPRESSIVE_V8_WORD_COUNT_MIN == 145
    assert cfg.shorts_duration_range_for_profile("shorts_expressive_v8", project_id="v8_ep07_harvard_reversible_choice_paradox") == (
        61.5,
        88.0,
    )
    assert cfg.shorts_duration_range_for_profile("shorts_expressive_v8", project_id="v8_ep06_bedtime_todo_list_sleep") == (
        61.5,
        120.0,
    )
