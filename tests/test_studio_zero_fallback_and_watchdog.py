from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from pipeline.studio.reporter import StudioAnalyticsReporter
from pipeline.studio.sanitize_scheduled_metadata import (
    build_diversified_description,
    sanitize_scheduled_projects,
)
from pipeline.studio.short_linker import ShortLinkGraph, StudioShortLinker
from pipeline.studio.studio_watchdog import (
    audit_staging_queue_integrity,
    run_studio_watchdog,
    scan_go_live_transitions,
)
from pipeline.studio.us_diorama_timetable import build_us_prime_timetable


def test_reporter_zero_fallback_never_injects_synthetic_profiles_when_not_dry_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    proj_dir = tmp_path / "projects"
    p1 = proj_dir / "diorama_01_test" / "06_publish"
    p1.mkdir(parents=True)
    (p1 / "upload_receipt.json").write_text(
        json.dumps(
            {
                "video_id": "AbCdEfGhIjK",
                "status": "published_public",
                "visibility": "public",
                "title": "Test Public Short",
            }
        ),
        encoding="utf-8",
    )
    (p1 / "metadata.json").write_text(
        json.dumps({"title": "Test Public Short", "doi": "10.1038/s41586-023-00001-1"}),
        encoding="utf-8",
    )

    reporter = StudioAnalyticsReporter(cdp_port=9222)
    monkeypatch.setattr(reporter, "_probe_project_duration_sec", lambda *a, **kw: 165.0)
    orig_collect = reporter._collect_local_pipeline_state
    monkeypatch.setattr(
        reporter,
        "_collect_local_pipeline_state",
        lambda report_date: {
            **orig_collect(report_date),
            "videos": [
                {
                    "index": 1,
                    "project_id": "diorama_01_test",
                    "title": "Test Public Short",
                    "pillar": "brain_health",
                    "pillar_label": "brain_health",
                    "slot_id": 1,
                    "slot_name": "Morning",
                    "date": report_date,
                    "time_et": "07:30",
                    "time_kst": "20:30",
                    "status": "published",
                    "video_id": "AbCdEfGhIjK",
                    "shorts_url": "https://www.youtube.com/shorts/AbCdEfGhIjK",
                    "duration_seconds": 170.0,
                    "doi": "10.1038/s41586-023-00001-1",
                    "active_variant": "A",
                    "rotation_interval_hours": 72,
                    "ab_manifest": {},
                    "pinned_comment": True,
                }
            ],
        },
    )

    async def _offline_dom(known_video_ids=None):
        return {"live_connected": False, "studio_authenticated": False, "video_row_metrics": {}}

    monkeypatch.setattr(reporter, "_async_scrape_studio_dom", _offline_dom)
    monkeypatch.setattr(reporter, "_fetch_watch_page_fallback", lambda vid: {})
    monkeypatch.setattr(reporter, "_load_previous_snapshot", lambda r_date, compare_date=None: (None, None))

    metrics = reporter.collect_daily_metrics(report_date="2026-11-02", dry_run=False)
    rec = metrics["per_video_records"][0]
    # Zero synthetic 1420 / 94.7% profile numbers allowed when dry_run=False and DOM is offline
    assert rec["measured"] is False
    assert rec["views"] == 0
    assert rec["apv_pct"] == 0.0
    assert rec["viewed_pct"] == 0.0


def test_watchdog_detects_elapsed_scheduled_and_promotes_in_live_mode(tmp_path: Path):
    proj_dir = tmp_path / "projects"
    # Elapsed scheduled Short missing DOI pin & related link
    p_elapsed = proj_dir / "diorama_11_elapsed" / "06_publish"
    p_elapsed.mkdir(parents=True)
    (proj_dir / "diorama_11_elapsed" / "02_script").mkdir(parents=True)
    (proj_dir / "diorama_11_elapsed" / "02_script" / "script.json").write_text(
        json.dumps({"sentences": ["A surprise finding changed memory research!", "Here is why."], "doi": "10.2307/1127388"}),
        encoding="utf-8",
    )
    (p_elapsed / "metadata.json").write_text(
        json.dumps({"title": "Elapsed Scheduled Video", "doi": "10.2307/1127388"}),
        encoding="utf-8",
    )
    (p_elapsed / "upload_receipt.json").write_text(
        json.dumps(
            {
                "video_id": "1111111111A",
                "visibility": "scheduled",
                "status": "scheduled",
                "scheduled_at_utc": "2026-11-02T12:00:00Z",
            }
        ),
        encoding="utf-8",
    )

    # Future scheduled Short
    p_future = proj_dir / "diorama_12_future" / "06_publish"
    p_future.mkdir(parents=True)
    (p_future / "upload_receipt.json").write_text(
        json.dumps(
            {
                "video_id": "2222222222B",
                "visibility": "scheduled",
                "status": "scheduled",
                "scheduled_at_utc": "2026-11-05T12:00:00Z",
            }
        ),
        encoding="utf-8",
    )

    now = datetime(2026, 11, 2, 18, 0, tzinfo=timezone.utc)
    scan = scan_go_live_transitions(projects_dir=proj_dir, now_utc=now)
    assert scan["public_count"] == 1
    assert scan["scheduled_count"] == 1
    assert [x["project_id"] for x in scan["due_for_public_transition"]] == ["diorama_11_elapsed"]
    assert [x["project_id"] for x in scan["missing_doi_pin"]] == ["diorama_11_elapsed"]

    # Dry-run prepares comment without mutating upload_receipt
    res_dry = run_studio_watchdog(
        projects_dir=proj_dir,
        graph_file=tmp_path / "graph.json",
        queue_file=tmp_path / "queue.json",
        dry_run=True,
        apply_links=False,
        now_utc=now,
    )
    assert res_dry["promoted_projects"] == []
    assert res_dry["pin_results"][0]["status"] == "dry_run_prepared"

    # Promote elapsed receipt without browser calls (apply_pins=False, apply_links=False)
    res_prom = run_studio_watchdog(
        projects_dir=proj_dir,
        graph_file=tmp_path / "graph.json",
        queue_file=tmp_path / "queue.json",
        dry_run=False,
        apply_pins=False,
        apply_links=False,
        promote_elapsed_receipts=True,
        now_utc=now,
    )
    assert res_prom["promoted_projects"] == ["diorama_11_elapsed"]
    updated_rec = json.loads((p_elapsed / "upload_receipt.json").read_text(encoding="utf-8"))
    assert updated_rec["visibility"] == "public"
    assert updated_rec["status"] == "published_public"


def test_short_linker_public_targets_only_and_merge_existing(tmp_path: Path):
    proj_dir = tmp_path / "projects"
    graph_file = tmp_path / "short_link_graph.json"

    for pid, vid, vis in [
        ("diorama_01_pub", "PubVideo001", "public"),
        ("diorama_02_pub", "PubVideo002", "public"),
        ("diorama_15_sched", "SchVideo015", "scheduled"),
    ]:
        pub = proj_dir / pid / "06_publish"
        pub.mkdir(parents=True)
        (pub / "upload_receipt.json").write_text(
            json.dumps({"video_id": vid, "visibility": vis, "status": vis, "title": pid}),
            encoding="utf-8",
        )
        (pub / "metadata.json").write_text(
            json.dumps({"title": pid, "pillar": "brain_health"}),
            encoding="utf-8",
        )

    # Pre-seed an existing verified edge for diorama_01_pub -> diorama_02_pub
    graph_file.write_text(
        json.dumps(
            {
                "edges": [
                    {
                        "source_project_id": "diorama_01_pub",
                        "source_video_id": "PubVideo001",
                        "target_project_id": "diorama_02_pub",
                        "target_video_id": "PubVideo002",
                        "target_title": "diorama_02_pub",
                        "verified": True,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    graph = ShortLinkGraph(projects_dir=proj_dir, graph_file=graph_file)
    plan_single = graph.plan_links(project_filter={"diorama_15_sched"}, public_targets_only=True)
    for edge in plan_single.get("edges") or []:
        assert edge["target_video_id"] != "SchVideo015"
    graph.save_graph(plan_single, merge_existing=True)

    merged_doc = json.loads(graph_file.read_text(encoding="utf-8"))
    edges_by_src = {e["source_project_id"]: e for e in merged_doc["edges"]}
    # Existing verified edge for diorama_01_pub preserved non-destructively!
    assert edges_by_src["diorama_01_pub"]["target_video_id"] == "PubVideo002"


def test_us_prime_timetable_dst_notification_cap_and_legacy_psych_guard(tmp_path: Path):
    # Legacy psych_* rejected by default
    with pytest.raises(ValueError, match="Legacy psych_"):
        build_us_prime_timetable([{"project_id": "psych_01_old", "pillar": "brain_health"}])

    # Standard v7 episodes across winter EST (Nov) and summer EDT (Jul)
    eps = [
        {"project_id": f"diorama_{i:02d}_case", "pillar": "brain_health", "format_profile": "neuro_diorama"}
        for i in range(1, 10)
    ]
    winter = build_us_prime_timetable(eps, start_date="2026-11-16", days=7)  # Monday in EST
    summer = build_us_prime_timetable(eps, start_date="2026-07-06", days=2)  # Monday in EDT
    assert winter["slots"][0]["tz_abbr"] == "EST"
    assert summer["slots"][0]["tz_abbr"] == "EDT"

    # Strictly <= 3 subscriber notifications per day
    by_day: dict[str, int] = {}
    for s in winter["slots"]:
        if s["notify_subscribers"]:
            by_day[s["date"]] = by_day.get(s["date"], 0) + 1
    assert all(cnt <= 3 for cnt in by_day.values())

    # Queue audit detects duplicate slots and legacy psych items
    q_file = tmp_path / "staging_queue.json"
    q_file.write_text(
        json.dumps(
            {
                "scheduled_items": [
                    {"project_id": "diorama_01", "date": "2026-11-14", "slot_id": 1, "status": "scheduled"},
                    {"project_id": "diorama_01", "date": "2026-11-14", "slot_id": 1, "status": "scheduled"},
                    {"project_id": "psych_99", "date": "2026-11-15", "slot_id": 2, "status": "archived"},
                ]
            }
        ),
        encoding="utf-8",
    )
    q_audit = audit_staging_queue_integrity(queue_file=q_file, projects_dir=tmp_path)
    assert q_audit["healthy"] is False
    assert q_audit["duplicate_projects"] == ["diorama_01"]
    assert q_audit["legacy_psych_items"] == 1

    # Sanitize scheduled metadata updates scheduled project only, skipping public project
    s_root = tmp_path / "sched_test"
    for pid, vis in [("diorama_pub", "public"), ("diorama_sched", "scheduled")]:
        (s_root / pid / "06_publish").mkdir(parents=True)
        (s_root / pid / "02_script").mkdir(parents=True)
        (s_root / pid / "06_publish" / "upload_receipt.json").write_text(
            json.dumps({"video_id": "ValidVid123", "visibility": vis}),
            encoding="utf-8",
        )
        (s_root / pid / "06_publish" / "metadata.json").write_text(
            json.dumps({"title": f"{pid}: Brain Case", "doi": "10.2307/1127388", "description": "Old boilerplate"}),
            encoding="utf-8",
        )
        (s_root / pid / "02_script" / "script.json").write_text(
            json.dumps({"sentences": ["Lead sentence one.", "Lead sentence two."]}),
            encoding="utf-8",
        )
    san_res = sanitize_scheduled_projects(projects_dir=s_root, dry_run=False, apply_studio_dom=False)
    assert [u["project_id"] for u in san_res["updated"]] == ["diorama_sched"]
    desc_new = build_diversified_description(
        project_id="diorama_sched",
        metadata={"title": "Brain Case", "doi": "10.2307/1127388"},
        script={"sentences": ["Lead one.", "Lead two."]},
        index_seed=2,
    )
    assert "Source & Verification: https://doi.org/10.2307/1127388" in desc_new
