"""
Unit & Integration Tests for Cross-Platform QA Scheduler (`pipeline/studio/qa_scheduler.py`).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

from pipeline.studio.qa_scheduler import (
    evaluate_qa_schedule,
    run_qa_scheduler,
)


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _seed_clean_daily_report(
    daily_dir: Path,
    reports_root: Path,
    now_utc: datetime,
    *,
    report_date: str = "2026-11-14",
    age_hours: float = 1.0,
    views_24h: int = 8,
    realtime_48h: int = 1411,
    watch_hours: float = 126.9,
    viewed_pct: float = 66.0,
    apv_pct: float = 66.0,
    us_pct: float = 55.6,
    simultaneous: int = 0,
    quarantine: int = 0,
    measured_video_count: int = 0,
) -> None:
    gen_dt = now_utc - timedelta(hours=age_hours)
    metrics = {
        "report_date": report_date,
        "generated_at_utc": gen_dt.isoformat(),
        "data_source_mode": "LIVE_CDP_DOM",
        "live_scraped_meta": {"live_connected": True, "studio_authenticated": True},
        "inventory_summary": {"published_count": 14, "scheduled_count": 2, "quarantine_count": quarantine},
        "short_link_summary": {"published_total": 14, "related_verified_count": 14, "ring_complete": True},
        "channel_kpis": {
            "subscribers_total": 6,
            "views_24h": views_24h,
            "views_prev": 1480,
            "watch_hours_24h": watch_hours,
            "realtime_48h_views": realtime_48h,
            "realtime_60m_views": 32,
        },
        "retention_kpis": {"viewed_pct": viewed_pct, "apv_pct": apv_pct, "avd_seconds": 52.0},
        "retention_quartiles": [
            {"quartile": "Q1 (0–25%)", "today_pct": 72.0},
            {"quartile": "Q3 (50–75%)", "today_pct": 64.8},
        ],
        "traffic_sources": [{"short_name": "Shorts Feed", "pct": 87.0}],
        "geographies": [{"country": "US", "pct": us_pct}, {"country": "UK", "pct": 5.9}],
        "risk_audit": {
            "measured_video_count": measured_video_count,
            "unscraped_video_count": 14,
            "simultaneous_publish_count": simultaneous,
            "quarantine_count": quarantine,
        },
    }
    _write_json(daily_dir / f"{report_date}_studio_metrics.json", metrics)
    _write_json(reports_root / "studio_playlist_purge_receipt.json", {"remaining_count": 0, "status": "purged_zero_verified"})


def _seed_qa_passed_project(
    projects_dir: Path,
    pid: str,
    *,
    duration_sec: float = 78.0,
    with_bundle: bool = True,
    with_qa: bool = True,
    yt_receipt: dict | None = None,
    ig_receipt: dict | None = None,
    tt_receipt: dict | None = None,
) -> Path:
    p_dir = projects_dir / pid
    (p_dir / "05_assembly").mkdir(parents=True, exist_ok=True)
    (p_dir / "05_assembly" / "final_shorts_1080x1920.mp4").write_bytes(b"mp4data")
    _write_json(p_dir / "05_assembly" / "probe_report.json", {"duration_sec": duration_sec})
    if with_qa:
        _write_json(p_dir / "00_project_manifest.json", {"project_id": pid, "production_profile": "classic"})
        _write_json(p_dir / "05_assembly" / "video_autopsy_report.json", {"passed": True})
    if with_bundle:
        b_dir = p_dir / "06_publish" / "multi_platform_bundle"
        b_dir.mkdir(parents=True, exist_ok=True)
        (b_dir / "video_clean.mp4").write_bytes(b"clean")
        (b_dir / "cover_9x16.png").write_bytes(b"png")
        (b_dir / "tiktok_caption.txt").write_text("Test hook\n\n#neuroscience #psychology #brainfacts #humanbehavior", encoding="utf-8")
        (b_dir / "reels_caption.txt").write_text("Test hook\n\n#neuroscience #psychology #brainfacts #humanbehavior", encoding="utf-8")
        _write_json(b_dir / "upload_checklist.json", {"duration_sec": duration_sec, "tiktok_over_60s_eligible": duration_sec >= 61.5})
    if yt_receipt:
        _write_json(p_dir / "06_publish" / "upload_receipt.json", yt_receipt)
    if ig_receipt:
        _write_json(p_dir / "06_publish" / "instagram_upload_receipt.json", ig_receipt)
    if tt_receipt:
        _write_json(p_dir / "06_publish" / "tiktok_upload_receipt.json", tt_receipt)
    return p_dir


def test_missing_and_stale_daily_report_force_youtube_hold(tmp_path: Path) -> None:
    now = datetime(2026, 11, 14, 8, 0, tzinfo=timezone.utc)
    proj_dir = tmp_path / "projects"
    proj_dir.mkdir()
    rep_root = tmp_path / "reports"
    daily_dir = rep_root / "daily"

    res_missing = evaluate_qa_schedule(
        projects_dir=proj_dir,
        channel_root=tmp_path,
        reports_root=rep_root,
        daily_dir=daily_dir,
        now_utc=now,
    )
    assert res_missing["platforms"]["youtube"]["verdict"] == "HOLD"

    _seed_clean_daily_report(daily_dir, rep_root, now, age_hours=80.0)
    res_stale = evaluate_qa_schedule(
        projects_dir=proj_dir,
        channel_root=tmp_path,
        reports_root=rep_root,
        daily_dir=daily_dir,
        now_utc=now,
    )
    assert res_stale["platforms"]["youtube"]["verdict"] == "HOLD"
    assert any("YT-REPORT-FRESH" in r for r in res_stale["platforms"]["youtube"]["block_reasons"])


def test_simultaneous_publish_forces_youtube_hold(tmp_path: Path) -> None:
    now = datetime(2026, 11, 14, 8, 0, tzinfo=timezone.utc)
    proj_dir = tmp_path / "projects"
    rep_root = tmp_path / "reports"
    daily_dir = rep_root / "daily"
    _seed_clean_daily_report(daily_dir, rep_root, now, simultaneous=2)
    _seed_qa_passed_project(proj_dir, "v8_ep09_test_episode")

    res = evaluate_qa_schedule(
        projects_dir=proj_dir,
        channel_root=tmp_path,
        reports_root=rep_root,
        daily_dir=daily_dir,
        now_utc=now,
    )
    assert res["platforms"]["youtube"]["verdict"] == "HOLD"
    assert any("YT-NO-SIMULTANEOUS" in r for r in res["platforms"]["youtube"]["block_reasons"])


def test_partial_dom_scrape_anomaly_detected_without_false_hold(tmp_path: Path) -> None:
    now = datetime(2026, 11, 14, 8, 0, tzinfo=timezone.utc)
    proj_dir = tmp_path / "projects"
    rep_root = tmp_path / "reports"
    daily_dir = rep_root / "daily"
    _seed_clean_daily_report(daily_dir, rep_root, now, views_24h=8, realtime_48h=1411, watch_hours=126.9, viewed_pct=72.0)
    _seed_qa_passed_project(proj_dir, "v8_ep09_test_episode", duration_sec=76.0)

    res = evaluate_qa_schedule(
        projects_dir=proj_dir,
        channel_root=tmp_path,
        reports_root=rep_root,
        daily_dir=daily_dir,
        now_utc=now,
    )
    assert res["daily_report_summary"]["partial_dom_scrape_anomaly"] is True
    assert res["platforms"]["youtube"]["verdict"] == "CONDITIONAL_GO"
    assert len(res["platforms"]["youtube"]["ready_candidates"]) == 1


def test_instagram_and_tiktok_cooldowns_and_60s_gate(tmp_path: Path) -> None:
    now = datetime(2026, 11, 14, 8, 0, tzinfo=timezone.utc)
    proj_dir = tmp_path / "projects"
    rep_root = tmp_path / "reports"
    daily_dir = rep_root / "daily"
    _seed_clean_daily_report(daily_dir, rep_root, now, viewed_pct=74.0)

    # Recent IG (5h ago) & TikTok (6h ago) should block both on cooldown
    _seed_qa_passed_project(
        proj_dir,
        "v8_ep06_recent",
        duration_sec=80.0,
        yt_receipt={"video_id": "aaaaaaaaaaa", "visibility": "public", "scheduled_at_utc": "2026-11-12T00:30:00Z"},
        ig_receipt={"reel_url": "https://www.instagram.com/reel/ABC/", "uploaded_at_utc": (now - timedelta(hours=5)).isoformat()},
        tt_receipt={"video_url": "https://www.tiktok.com/@x/video/123", "uploaded_at_utc": (now - timedelta(hours=6)).isoformat()},
    )
    # Only candidate is 58s (valid for IG if not on cooldown, invalid for TikTok Creator Rewards >=61.5s)
    _seed_qa_passed_project(proj_dir, "v8_ep09_short", duration_sec=58.0)

    res_cool = evaluate_qa_schedule(
        projects_dir=proj_dir,
        channel_root=tmp_path,
        reports_root=rep_root,
        daily_dir=daily_dir,
        now_utc=now,
    )
    assert res_cool["platforms"]["instagram"]["verdict"] == "HOLD"
    assert res_cool["platforms"]["tiktok"]["verdict"] == "HOLD"
    assert any("v8_ep09_short" in r for r in res_cool["platforms"]["tiktok"]["rejected_under_60s"])

    # Advance 25h -> IG GO for 58s, TikTok still HOLD because 58s < 61.5s
    res_later = evaluate_qa_schedule(
        projects_dir=proj_dir,
        channel_root=tmp_path,
        reports_root=rep_root,
        daily_dir=daily_dir,
        now_utc=now + timedelta(hours=25),
    )
    assert res_later["platforms"]["instagram"]["verdict"] == "GO"
    assert res_later["platforms"]["tiktok"]["verdict"] == "HOLD"


def test_frozen_and_missing_qa_excluded_and_outputs_written(tmp_path: Path) -> None:
    now = datetime(2026, 11, 14, 8, 0, tzinfo=timezone.utc)
    proj_dir = tmp_path / "projects"
    rep_root = tmp_path / "reports"
    daily_dir = rep_root / "daily"
    sched_dir = rep_root / "schedule"
    _seed_clean_daily_report(daily_dir, rep_root, now, views_24h=1500, measured_video_count=14, viewed_pct=75.0)

    # Frozen prefixes + suffix test + missing QA must be excluded
    _seed_qa_passed_project(proj_dir, "psych_99_legacy", duration_sec=80.0)
    _seed_qa_passed_project(proj_dir, "v8_ep08_capgras_r77", duration_sec=80.0)
    _seed_qa_passed_project(proj_dir, "v8_ep09_no_qa", duration_sec=80.0, with_qa=False)
    # Clean ready candidate
    _seed_qa_passed_project(
        proj_dir,
        "v8_ep10_clean_ready",
        duration_sec=80.0,
        yt_receipt={"video_id": "bbbbbbbbbbb", "visibility": "public", "scheduled_at_utc": "2026-11-12T00:30:00Z"},
    )
    _seed_qa_passed_project(proj_dir, "v8_ep11_next_yt", duration_sec=82.0)

    res = run_qa_scheduler(
        target_date="2026-11-14",
        projects_dir=proj_dir,
        channel_root=tmp_path,
        reports_root=rep_root,
        daily_dir=daily_dir,
        schedule_dir=sched_dir,
        now_utc=now,
        write_outputs=True,
    )
    assert res["platforms"]["youtube"]["verdict"] == "GO"
    assert [c["project_id"] for c in res["platforms"]["youtube"]["ready_candidates"]] == ["v8_ep11_next_yt"]
    assert res["platforms"]["instagram"]["verdict"] == "GO"
    assert res["platforms"]["tiktok"]["verdict"] == "GO"

    # Check >= 60m stagger between YT, IG, TT slots
    yt_dt = datetime.fromisoformat(res["platforms"]["youtube"]["next_optimal_slot"]["iso_utc"])
    ig_dt = datetime.fromisoformat(res["platforms"]["instagram"]["next_optimal_slot"]["iso_utc"])
    tt_dt = datetime.fromisoformat(res["platforms"]["tiktok"]["next_optimal_slot"]["iso_utc"])
    assert abs((yt_dt - ig_dt).total_seconds()) >= 3600
    assert abs((yt_dt - tt_dt).total_seconds()) >= 3600
    assert abs((ig_dt - tt_dt).total_seconds()) >= 3600

    # Output files exist
    assert (sched_dir / "2026-11-14_qa_schedule_plan.json").is_file()
    assert (sched_dir / "2026-11-14_qa_schedule_plan.md").is_file()
    assert (rep_root / "LATEST_QA_SCHEDULE_PLAN.json").is_file()
    assert (rep_root / "LATEST_QA_SCHEDULE_PLAN.md").is_file()
