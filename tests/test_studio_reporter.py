"""
Unit and integration tests for StudioAnalyticsReporter (pipeline/studio/reporter.py).
Follows Rule R28 (Self-Cleaning Test Hygiene) using temporary directories.
"""

import json
import shutil
import tempfile
from pathlib import Path

from pipeline.studio.reporter import StudioAnalyticsReporter, format_delta, make_gauge_bar


def test_format_delta_and_gauge_bar():
    assert "▲ +1,090회 (+44.0%)" == format_delta(3570, 2480, unit="회", decimals=0)
    assert "▲ +3.6%p" == format_delta(89.9, 86.3, unit="%", is_percent_point=True, decimals=1)
    assert "▲ -2.4%p" == format_delta(27.0, 29.4, unit="%", is_percent_point=True, invert_good=True, decimals=1)
    bar = make_gauge_bar(50.0, width=10)
    assert bar == "`█████░░░░░`"


def test_generate_daily_report_and_charts_self_cleaning():
    tmp_dir = Path(tempfile.mkdtemp(prefix="test_studio_report_"))
    try:
        reporter = StudioAnalyticsReporter(reports_dir=tmp_dir)

        # Day 1 baseline snapshot
        res_day1 = reporter.generate_daily_report(report_date="2026-10-15", dry_run=True)
        assert Path(res_day1["json_path"]).exists()
        assert Path(res_day1["charts_path"]).exists()
        assert Path(res_day1["charts_path"]).stat().st_size > 50_000
        assert Path(res_day1["markdown_path"]).exists()

        # Day 2 comparison against Day 1 (2026-10-17 vs 2026-10-15)
        res_day2 = reporter.generate_daily_report(
            report_date="2026-10-17",
            compare_date="2026-10-15",
            dry_run=True,
        )
        assert res_day2["previous_report_date"] == "2026-10-15"

        md_text = Path(res_day2["markdown_path"]).read_text(encoding="utf-8")
        # Verify all 5 normalized sections exist and zero redundant inline Mermaid charts
        for sec_num in range(1, 6):
            assert f"## {sec_num}." in md_text
        assert "## 6." not in md_text
        assert md_text.count("xychart-beta") == 0
        assert "2026-10-17_studio_charts.png" in md_text

        # Verify JSON schema completeness
        payload = json.loads(Path(res_day2["json_path"]).read_text(encoding="utf-8"))
        assert "channel_kpis" in payload
        assert "retention_kpis" in payload
        assert "trend_7d" in payload
        assert "retention_curves_30s" in payload
        assert "retention_quartiles" in payload
        assert len(payload["retention_quartiles"]) == 4
        assert [q["role_phase"] for q in payload["retention_quartiles"]] == [
            "setup → symptom",
            "failure → crisis → pivot",
            "mechanism steps",
            "breakthrough → conclusion",
        ]
        assert "per_video_records" in payload
        assert "diagnostics" in payload
        assert "risk_audit" in payload
        assert len(payload["risk_audit"]["items"]) == 7
        assert payload["data_source_mode"] in ("LIVE_CDP_DOM", "LOCAL_SNAPSHOT_BASELINE")
        assert len(payload.get("provenance_sha256", "")) == 64

        # Upcoming schedule must filter by date >= report_date (no 2026-10-15 past dates)
        for item in payload["upcoming_schedule"]:
            assert item["date"] >= "2026-10-17"

        # Verify Channel-Level Traffic-Light Scorecard, English numbers-first format, zero redundant '회' units, and Provenance
        assert "🚦 0. Executive Growth Pulse" in md_text
        assert "🟢" in md_text and "🟡" in md_text and "🔴" in md_text
        assert "psych_01" not in md_text
        assert "회" not in md_text
        assert "우수 (" not in md_text
        assert "3초 스와이프 이탈률" not in md_text
        assert "arecibo observatory collapse" not in md_text
        assert "Shown in feed" in md_text
        assert "Engaged Views" in md_text
        assert "Recent 3" in md_text
        assert "Q1→Q2" in md_text and "Q2→Q3" in md_text and "Q3→Q4" in md_text
        assert "Time-to-Seed" in md_text
        assert "Related Video" in md_text
        assert "Unlisted (Staged)" in md_text
        assert "Queue & Operations Health" in md_text
        assert "🔐 Provenance" in md_text
        assert "Q1 (0–25%)" in md_text
        assert "Q4 (75–100%)" in md_text
        assert "/ 30.0초" not in payload["diagnostics"]["executive_headline"]
        assert "뫼비우스 루프" not in md_text

        # Verify unmeasured videos do not leak cyclic dummy APV/CTR/AVD
        unmeasured = [r for r in payload["per_video_records"] if not r.get("measured", True)]
        for r_unm in unmeasured:
            assert r_unm["views"] == 0
            assert r_unm["avd_seconds"] == 0.0
            assert r_unm["apv_pct"] == 0.0
            assert r_unm["ctr_pct"] == 0.0

        # Verify 7-day trend matches KPI table previous and current day views
        assert payload["trend_7d"]["views"][-2] == payload["channel_kpis"]["views_prev"]
        assert payload["trend_7d"]["views"][-1] == payload["channel_kpis"]["views_24h"]
        assert payload["channel_kpis"]["views_24h"] > payload["channel_kpis"]["views_prev"]
        assert "+0.0%" not in payload["diagnostics"]["executive_headline"]

        # Verify custom reports_dir writes LATEST_DAILY_REPORT.md inside tmp_dir, not global root
        assert Path(res_day2["latest_report_path"]).parent == tmp_dir

        # Verify Per-Video Notable Change Detection & 3-Axis Root-Cause Attribution in JSON payload
        assert "notable_video_changes" in payload
        assert len(payload["notable_video_changes"]) >= 3
        change_types = {nc["change_type"] for nc in payload["notable_video_changes"]}
        assert "BREAKOUT_SURGE" in change_types
        assert "HOOK_AND_DURATION_BOTTLENECK" in change_types
        for nc in payload["notable_video_changes"]:
            assert nc.get("what_changed")
            assert nc.get("why_summary")
            assert nc.get("why_script_and_hook")
            assert nc.get("why_retention_and_visuals")
            assert nc.get("why_traffic_and_studio")
            assert nc.get("next_action")

        # Verify Success vs. Failure/Risk Signal Detection & Amplification Playbook in JSON payload
        assert "signal_radar" in payload
        sr = payload["signal_radar"]
        assert len(sr["success_signals"]) == 5
        assert len(sr["failure_risk_signals"]) == 5
        assert len(sr["amplification_strategies"]) == 5
        assert [s["signal_id"] for s in sr["success_signals"]] == [f"SIG-WIN-{i}" for i in range(1, 6)]
        assert [s["signal_id"] for s in sr["failure_risk_signals"]] == [f"SIG-FAIL-{i}" for i in range(1, 6)]
        assert [a["strategy_id"] for a in sr["amplification_strategies"]] == [f"AMP-{i}" for i in range(1, 6)]

        # Verify no broken empty backticks or stale hardcoded counts when unlisted/quarantine/sim_publish == 0
        assert "초기 `` `0`편" not in md_text
        assert "프로젝트(``)" not in md_text
        assert "None 구간 총 0개 슬롯" not in md_text
        if payload["risk_audit"]["unlisted_staged_count"] == 0:
            assert "Unlisted 17개 슬롯" not in md_text
            sig_fail_2 = next(s for s in sr["failure_risk_signals"] if s["signal_id"] == "SIG-FAIL-2")
            assert sig_fail_2["target"] != "`None`"
        if (
            payload["risk_audit"]["simultaneous_publish_count"] == 0
            and not payload["risk_audit"]["schedule_map_drift_slots"]
        ):
            sig_fail_4 = next(s for s in sr["failure_risk_signals"] if s["signal_id"] == "SIG-FAIL-4")
            assert sig_fail_4["severity"] == "LOW"
            assert "PASS" in sig_fail_4["status_badge"]

        # Verify DAILY_REPORT_MASTER_PROMPT.md template is synchronized with the normalized 5-section schema
        master_prompt_text = Path(res_day2["master_prompt_path"]).read_text(encoding="utf-8")
        assert "Normalized 5-Section" in master_prompt_text
        assert "Section 1" in master_prompt_text
        assert "Section 5" in master_prompt_text
        assert "뫼비우스 루프" not in master_prompt_text

        # Edge case: future report_date beyond queue dates falls back to last 10 queue items
        future_state = reporter._collect_local_pipeline_state("2099-12-31")
        assert len(future_state["upcoming_schedule"]) <= 10
        if future_state["raw_queue_items"]:
            assert future_state["upcoming_schedule"] == future_state["raw_queue_items"][-10:]

        # Verify real MP4 / YouTube Studio duration probing, catalog title/hook recovery, and slot4 20:00 ET alignment
        assert payload["retention_kpis"]["avg_video_length_sec"] > 65.0
        for rec in payload["per_video_records"]:
            if rec["video_id"] == "zs2pv1t_0hs":
                assert rec["duration_seconds"] == 47.0
            elif rec["video_id"] == "nGNIl26te0w":
                assert rec["duration_seconds"] == 31.0
            else:
                assert rec["duration_seconds"] > 70.0
            assert rec["title"] and rec["title"] != "N/A"
            assert rec["pillar"] and rec["pillar"] != "N/A"
        assert "19:30 ET" not in md_text
        assert "72h/var` vs Rule R32 `24h/var" not in md_text
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_notable_changes_and_signal_radar_edge_cases():
    """Tests _detect_notable_video_changes and _detect_signals_and_amplification with all-measured, partial Live DOM, and long-format bottleneck records."""
    minimal_data = {
        "report_date": "2026-10-17",
        "channel_kpis": {"views_24h": 500, "views_prev": 400},
        "retention_kpis": {
            "avg_video_length_sec": 45.0,
            "avd_seconds": 40.5,
            "avd_prev_seconds": 38.0,
            "apv_pct": 90.0,
            "apv_prev_pct": 85.0,
            "viewed_pct": 75.0,
            "viewed_prev_pct": 72.0,
        },
        "geographies": [
            {"country": "US", "pct": 55.0},
            {"country": "UK", "pct": 14.0},
            {"country": "CA", "pct": 8.0},
            {"country": "AU", "pct": 5.0},
        ],
        "traffic_sources": [
            {"short_name": "YT Search", "pct": 10.0, "apv_pct": 95.0},
            {"short_name": "Channel Page", "pct": 2.0, "apv_pct": 96.0},
        ],
        "demographics": {"returning_viewers_pct": 25.0, "subscribed_watch_pct": 12.0},
        "search_terms": [],
        "ab_test_rows": [],
        "risk_audit": {
            "unlisted_staged_count": 0,
            "unscraped_video_count": 0,
            "quarantine_count": 0,
            "simultaneous_publish_count": 0,
            "min_publish_gap_hours": 4.5,
            "schedule_map_drift_slots": [],
        },
        "per_video_records": [
            {
                "rank": 1,
                "project_id": "psych_01_test",
                "short_label": "psych_01",
                "title": "Test Title",
                "pillar": "brain_health",
                "slot_id": 1,
                "measured": True,
                "views": 500,
                "views_prev": 400,
                "views_delta_num": 100,
                "views_growth_pct": 25.0,
                "views_24h_delta": "+100 (Live DOM)",
                "watch_hours": 5.6,
                "duration_seconds": 45.0,
                "avd_seconds": 40.5,
                "apv_pct": 93.0,
                "viewed_pct": 75.0,
                "swiped_pct": 25.0,
                "ret_q1_pct": 82.0,
                "ret_q2_pct": 91.0,
                "ret_q3_pct": 89.0,
                "ret_q4_pct": 86.0,
                "ctr_pct": 7.5,
            },
            {
                "rank": 2,
                "project_id": "psych_03_long_format_test",
                "short_label": "psych_03",
                "title": "Long Format Hook Drop Test",
                "pillar": "brain_mysteries",
                "slot_id": 3,
                "measured": True,
                "views": 300,
                "views_prev": 250,
                "views_delta_num": 50,
                "views_growth_pct": 20.0,
                "views_24h_delta": "+50 (Live DOM)",
                "watch_hours": 3.5,
                "duration_seconds": 65.0,
                "avd_seconds": 52.0,
                "apv_pct": 80.0,
                "viewed_pct": 68.0,
                "swiped_pct": 32.0,
                "ret_q1_pct": 74.0,
                "ret_q2_pct": 82.0,
                "ret_q3_pct": 80.0,
                "ret_q4_pct": 76.0,
                "ctr_pct": 5.5,
            },
        ],
    }
    changes = StudioAnalyticsReporter._detect_notable_video_changes(minimal_data)
    assert len(changes) == 2
    assert changes[0]["change_type"] == "BREAKOUT_SURGE"
    assert "Live DOM 조회수 실측 + 4분위 프로필 결합" in changes[0]["what_changed"]
    assert changes[1]["change_type"] == "HOOK_AND_DURATION_BOTTLENECK"
    assert "단축 포맷" not in changes[1]["why_retention_and_visuals"]
    assert not any(c["change_type"] == "COHORT_DOM_PENDING_ISOLATION" for c in changes)

    radar = StudioAnalyticsReporter._detect_signals_and_amplification(minimal_data, changes)
    assert radar["success_signal_count"] == 5
    assert radar["failure_risk_signal_count"] == 5
    assert radar["amplification_strategy_count"] == 5
    sig_fail_4 = next(s for s in radar["failure_risk_signals"] if s["signal_id"] == "SIG-FAIL-4")
    assert sig_fail_4["severity"] == "LOW"


def test_vacant_null_slots_and_legacy_v4_inventory_filtering():
    """
    Regression test for:
    1) JSON `project_id: null` / `"None"` / `status: "vacant"` slots and stale unuploaded
       `ready_to_stage` drafts in `staging_queue.json` must NEVER inflate `scheduled_count`,
       `upcoming_schedule`, or `per_video_records`.
    2) Unpublished/deleted legacy v4 MP4s in `projects/` and `Completed_Psychology_100_Shorts/`
       must be excluded from `total_completed_inventory` and `staged_buffer_count` (matching
       `StagingQueueManager.get_status_summary()`).
    """
    from pipeline.studio.queue_manager import StagingQueueManager

    tmp_dir = Path(tempfile.mkdtemp(prefix="test_reporter_vacant_v4_"))
    try:
        projects_dir = tmp_dir / "BCI_Shorts_Channel" / "projects"
        reports_dir = tmp_dir / "BCI_Shorts_Channel" / "reports" / "daily"
        queue_file = tmp_dir / "BCI_Shorts_Channel" / "staging_queue.json"
        link_graph_file = tmp_dir / "BCI_Shorts_Channel" / "short_link_graph.json"
        archive_dir = tmp_dir / "Completed_Psychology_100_Shorts"
        projects_dir.mkdir(parents=True, exist_ok=True)
        archive_dir.mkdir(parents=True, exist_ok=True)

        # 1. Live published project (counted even without v5 visual_plan because it is live on YouTube)
        live_dir = projects_dir / "test_01_live_pub"
        (live_dir / "05_assembly").mkdir(parents=True)
        (live_dir / "00_project_manifest.json").write_text(
            json.dumps({"project_id": "test_01_live_pub", "pillar": "everyday_neuro", "title": "Why Basal Ganglia Habits Lock Your Brain"}),
            encoding="utf-8",
        )
        (live_dir / "05_assembly" / "final_shorts_1080x1920.mp4").write_bytes(b"\x00" * 1024)
        (live_dir / "02_script").mkdir(parents=True)
        (live_dir / "02_script" / "script.json").write_text(
            json.dumps({
                "title": "Why Basal Ganglia Habits Lock Your Brain",
                "pillar": "everyday_neuro",
                "clip_narrations": ["Hook sentence."] * 10,
                "doi": "10.1038/nature12345",
            }),
            encoding="utf-8",
        )
        (live_dir / "06_publish").mkdir(parents=True)
        (live_dir / "06_publish" / "upload_receipt.json").write_text(
            json.dumps({
                "project_id": "test_01_live_pub",
                "video_id": "p4ou90cHt50",
                "status": "published_public",
                "visibility": "public",
                "related_video_verified": True,
                "related_target_project_id": "test_01_live_pub",
                "playlist_verified": True,
                "playlist_title": "Everyday Brain & Neuro-Hacks",
            }),
            encoding="utf-8",
        )
        (archive_dir / "final_shorts_test_01_live_pub.mp4").write_bytes(b"\x00" * 1024)

        # 2. Deleted legacy v4 project (has MP4 in both 05_assembly and Completed_Psychology_100_Shorts)
        del_dir = projects_dir / "test_04_deleted_v4"
        (del_dir / "05_assembly").mkdir(parents=True)
        (del_dir / "00_project_manifest.json").write_text(
            json.dumps({"project_id": "test_04_deleted_v4", "pillar": "neuro_history"}),
            encoding="utf-8",
        )
        (del_dir / "05_assembly" / "final_shorts_1080x1920.mp4").write_bytes(b"\x00" * 1024)
        (del_dir / "06_publish").mkdir(parents=True)
        (del_dir / "06_publish" / "upload_receipt.json").write_text(
            json.dumps({
                "project_id": "test_04_deleted_v4",
                "video_id": None,
                "status": "deleted_from_studio",
                "visibility": "deleted",
            }),
            encoding="utf-8",
        )
        (archive_dir / "final_shorts_test_04_deleted_v4.mp4").write_bytes(b"\x00" * 1024)

        # 3. Unpublished legacy v4 project without receipt (fails passes_v5_publish_gate)
        unpub_v4_dir = projects_dir / "test_07_unpub_v4"
        (unpub_v4_dir / "05_assembly").mkdir(parents=True)
        (unpub_v4_dir / "00_project_manifest.json").write_text(
            json.dumps({"project_id": "test_07_unpub_v4", "pillar": "brain_mysteries"}),
            encoding="utf-8",
        )
        (unpub_v4_dir / "05_assembly" / "final_shorts_1080x1920.mp4").write_bytes(b"\x00" * 1024)
        (archive_dir / "final_shorts_test_07_unpub_v4.mp4").write_bytes(b"\x00" * 1024)

        # 4. Orphan legacy archive MP4 with no project folder at all
        (archive_dir / "final_shorts_test_99_orphan_v4.mp4").write_bytes(b"\x00" * 1024)

        # 5. staging_queue.json with 6 vacant/null/string-"None" slots + blocked/deleted/nonexistent ready_to_stage entries
        queue_payload = {
            "channel_id": "UC4FeioYYv9X04Di07_MfZ7g",
            "scheduled_items": [
                {"schedule_id": "2026-10-27_slot2", "project_id": None, "title": None, "pillar": None, "date": "2026-10-27", "slot_id": 2, "time_et": "12:00", "status": "vacant"},
                {"schedule_id": "2026-10-27_slot4", "project_id": "None", "title": None, "pillar": None, "date": "2026-10-27", "slot_id": 4, "time_et": "20:00", "status": "vacant"},
                {"schedule_id": "2026-10-28_slot2", "project_id": "null", "title": None, "pillar": None, "date": "2026-10-28", "slot_id": 2, "time_et": "12:00", "status": "vacant"},
                {"schedule_id": "2026-10-28_slot4", "project_id": "   ", "title": None, "pillar": None, "date": "2026-10-28", "slot_id": 4, "time_et": "20:00", "status": "vacant"},
                {"schedule_id": "2026-10-29_slot2", "project_id": None, "date": "2026-10-29", "slot_id": 2, "time_et": "12:00", "status": "vacant"},
                {"schedule_id": "2026-10-29_slot4", "project_id": None, "date": "2026-10-29", "slot_id": 4, "time_et": "20:00", "status": "vacant"},
                {"schedule_id": "2026-10-30_slot2", "project_id": "test_04_deleted_v4", "date": "2026-10-30", "slot_id": 2, "time_et": "12:00", "status": "blocked_legacy_v4"},
                {"schedule_id": "2026-10-30_slot4", "project_id": "test_04_deleted_v4", "date": "2026-10-30", "slot_id": 4, "time_et": "20:00", "status": "deleted_from_studio"},
                {"schedule_id": "2026-10-31_slot2", "project_id": "test_55_nonexistent_draft", "date": "2026-10-31", "slot_id": 2, "time_et": "12:00", "status": "ready_to_stage"},
            ],
            "history": [
                {
                    "schedule_id": "2026-10-21_slot2",
                    "project_id": "test_01_live_pub",
                    "video_id": "p4ou90cHt50",
                    "title": "Why Basal Ganglia Habits Lock Your Brain",
                    "pillar": "everyday_neuro",
                    "date": "2026-10-21",
                    "slot_id": 2,
                    "time_et": "12:00",
                    "status": "published",
                }
            ],
        }
        queue_file.write_text(json.dumps(queue_payload, indent=2), encoding="utf-8")
        link_graph_file.write_text(json.dumps({"edges": [{"source": "test_01_live_pub"}], "two_cycle_count": 0}), encoding="utf-8")

        qm = StagingQueueManager(queue_file=queue_file, projects_dir=projects_dir)
        q_summary = qm.get_status_summary()
        assert q_summary["scheduled_slots_count"] == 0
        assert q_summary["vacant_slots_count"] == 6
        assert q_summary["total_completed_projects"] == 1
        assert q_summary["staged_in_buffer"] == 0

        reporter = StudioAnalyticsReporter(
            reports_dir=reports_dir,
            projects_dir=projects_dir,
            queue_file=queue_file,
            short_link_graph_file=link_graph_file,
        )
        local_state = reporter._collect_local_pipeline_state("2026-10-25")
        assert local_state["published_count"] == 1
        assert local_state["scheduled_count"] == 0
        assert local_state["vacant_slot_count"] == 6
        assert local_state["staged_buffer_count"] == 0
        assert local_state["total_completed_inventory"] == 1
        assert local_state["blocked_legacy_v4_count"] == 3
        assert local_state["upcoming_schedule"] == []
        assert local_state["raw_queue_items"] == []
        assert [v["project_id"] for v in local_state["videos"]] == ["test_01_live_pub"]

        res = reporter.generate_daily_report(report_date="2026-10-25", dry_run=True)
        payload = json.loads(Path(res["json_path"]).read_text(encoding="utf-8"))
        md_text = Path(res["markdown_path"]).read_text(encoding="utf-8")

        assert payload["inventory_summary"]["published_count"] == 1
        assert payload["inventory_summary"]["scheduled_count"] == 0
        assert payload["inventory_summary"]["vacant_slot_count"] == 6
        assert payload["inventory_summary"]["staged_buffer_count"] == 0
        assert payload["inventory_summary"]["total_completed_inventory"] == 1
        assert payload["inventory_summary"]["blocked_legacy_v4_count"] == 3
        assert payload["upcoming_schedule"] == []
        assert [r["project_id"] for r in payload["per_video_records"]] == ["test_01_live_pub"]

        risk_2 = next(i for i in payload["risk_audit"]["items"] if i["risk_id"] == "RISK-2")
        assert risk_2["severity"] == "MEDIUM"
        assert "QUEUE EMPTY" in risk_2["status_badge"]
        assert "공백 없음" not in risk_2["status_badge"]

        assert "📅 **Scheduled** `0 (0.0d)`" in md_text
        assert "예약 0개" in md_text
        assert "예약 0건" in md_text
        assert "예약 6" not in md_text
        assert "**Scheduled** `6" not in md_text
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_mixed_queue_with_v5_ready_project_and_vacant_slots():
    """
    Verifies that when a genuine Prompt System v5 unpublished project exists alongside
    vacant (`project_id: null`) slots and legacy v4 projects, both `StagingQueueManager`
    and `StudioAnalyticsReporter` count the v5 project accurately while excluding
    vacant slots and legacy v4 artifacts.
    """
    from pipeline.studio.queue_manager import StagingQueueManager
    from tests.test_studio_autonomous import _seed_hermetic_studio_project

    tmp_dir = Path(tempfile.mkdtemp(prefix="test_reporter_mixed_v5_"))
    try:
        projects_dir = tmp_dir / "BCI_Shorts_Channel" / "projects"
        reports_dir = tmp_dir / "BCI_Shorts_Channel" / "reports" / "daily"
        queue_file = tmp_dir / "BCI_Shorts_Channel" / "staging_queue.json"
        link_graph_file = tmp_dir / "BCI_Shorts_Channel" / "short_link_graph.json"
        archive_dir = tmp_dir / "Completed_Psychology_100_Shorts"
        projects_dir.mkdir(parents=True, exist_ok=True)
        archive_dir.mkdir(parents=True, exist_ok=True)

        # 1. Live published project (legacy v4 schema, allowed because live on YouTube)
        _seed_hermetic_studio_project(
            projects_dir,
            "test_01_live_pub",
            title="Why Basal Ganglia Habits Lock Your Brain",
            pillar="everyday_neuro",
            v5_ready=False,
            live_receipt={
                "project_id": "test_01_live_pub",
                "video_id": "p4ou90cHt50",
                "status": "published_public",
                "visibility": "public",
            },
        )

        # 2. Genuine v5-passing unpublished project whose MP4 lives ONLY in Completed_Psychology_100_Shorts
        v5_storage = _seed_hermetic_studio_project(
            projects_dir,
            "test_08_gage_v5",
            title="How an Iron Rod Rewired Human Personality",
            pillar="brain_history",
            v5_ready=True,
        )
        v5_asm_mp4 = v5_storage.get_stage_dir("05_assembly") / "final_shorts_1080x1920.mp4"
        shutil.move(str(v5_asm_mp4), str(archive_dir / "final_shorts_test_08_gage_v5.mp4"))

        # 3. Blocked legacy v4 project (unpublished, v5_ready=False)
        _seed_hermetic_studio_project(
            projects_dir,
            "test_09_legacy_v4",
            pillar="brain_mysteries",
            v5_ready=False,
        )

        queue_payload = {
            "channel_id": "UC4FeioYYv9X04Di07_MfZ7g",
            "scheduled_items": [
                {
                    "schedule_id": "2026-10-27_slot2",
                    "project_id": "test_08_gage_v5",
                    "video_id": "AbCdEfGhI12",
                    "title": "How an Iron Rod Rewired Human Personality",
                    "pillar": "brain_history",
                    "date": "2026-10-27",
                    "slot_id": 2,
                    "time_et": "12:00",
                    "status": "scheduled",
                },
                {"schedule_id": "2026-10-27_slot4", "project_id": None, "date": "2026-10-27", "slot_id": 4, "time_et": "20:00", "status": "vacant"},
                {"schedule_id": "2026-10-28_slot2", "project_id": None, "date": "2026-10-28", "slot_id": 2, "time_et": "12:00", "status": "vacant"},
            ],
            "history": [
                {
                    "schedule_id": "2026-10-21_slot2",
                    "project_id": "test_01_live_pub",
                    "video_id": "p4ou90cHt50",
                    "title": "Why Basal Ganglia Habits Lock Your Brain",
                    "pillar": "everyday_neuro",
                    "date": "2026-10-21",
                    "slot_id": 2,
                    "time_et": "12:00",
                    "status": "published",
                }
            ],
        }
        queue_file.write_text(json.dumps(queue_payload, indent=2), encoding="utf-8")
        link_graph_file.write_text(json.dumps({"edges": [], "two_cycle_count": 0}), encoding="utf-8")

        qm = StagingQueueManager(queue_file=queue_file, projects_dir=projects_dir)
        q_summary = qm.get_status_summary()
        assert q_summary["scheduled_slots_count"] == 1
        assert q_summary["vacant_slots_count"] == 2
        assert q_summary["total_completed_projects"] == 2

        reporter = StudioAnalyticsReporter(
            reports_dir=reports_dir,
            projects_dir=projects_dir,
            queue_file=queue_file,
            short_link_graph_file=link_graph_file,
        )
        res = reporter.generate_daily_report(report_date="2026-10-25", dry_run=True)
        payload = json.loads(Path(res["json_path"]).read_text(encoding="utf-8"))

        assert payload["inventory_summary"]["published_count"] == 1
        assert payload["inventory_summary"]["scheduled_count"] == 1
        assert payload["inventory_summary"]["vacant_slot_count"] == 2
        assert payload["inventory_summary"]["staged_buffer_count"] == 1
        assert payload["inventory_summary"]["total_completed_inventory"] == 2
        assert payload["inventory_summary"]["blocked_legacy_v4_count"] == 1
        assert len(payload["upcoming_schedule"]) == 1
        assert payload["upcoming_schedule"][0]["project_id"] == "test_08_gage_v5"

        risk_2 = next(i for i in payload["risk_audit"]["items"] if i["risk_id"] == "RISK-2")
        assert risk_2["severity"] == "OK"
        assert "1`개 슬롯 배정" in risk_2["status_badge"]
        assert "빈 슬롯 `2`개" in risk_2["status_badge"]
        assert "공백 없음" not in risk_2["status_badge"]
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_archived_history_preserves_cohort_timestamps_slots_and_link_metadata():
    """
    Regression test for:
    1) `StagingQueueManager.plan_5_slot_schedule()` archiving live `upload_receipt.json`
       entries (which store `scheduled_time_et` + `slot_id` without separate `date`/`time_et`)
       into `history`, ensuring `StudioAnalyticsReporter` preserves real cohort dates,
       slot IDs, multi-day elapsed hours, and `min_publish_gap_hours`.
    2) `related_video_receipt.json` (`link_reason`, `playlist_assigned`) populating
       `related_link_role` and `playlist_verified`.
    3) Zero stale hardcoded schedule/upload claims in `signal_radar` and `diagnostics`
       when `scheduled_count == 0`, and `simultaneous_publish_count == 0` when unique.
    """
    from pipeline.studio.queue_manager import StagingQueueManager
    from tests.test_studio_autonomous import _seed_hermetic_studio_project

    tmp_dir = Path(tempfile.mkdtemp(prefix="test_reporter_history_ts_"))
    try:
        projects_dir = tmp_dir / "BCI_Shorts_Channel" / "projects"
        reports_dir = tmp_dir / "BCI_Shorts_Channel" / "reports" / "daily"
        queue_file = tmp_dir / "BCI_Shorts_Channel" / "staging_queue.json"
        link_graph_file = tmp_dir / "BCI_Shorts_Channel" / "short_link_graph.json"
        projects_dir.mkdir(parents=True, exist_ok=True)

        s1 = _seed_hermetic_studio_project(
            projects_dir,
            "test_01_oct19",
            title="Why Basal Ganglia Habits Lock Your Brain",
            pillar="everyday_neuro",
            v5_ready=False,
            live_receipt={
                "project_id": "test_01_oct19",
                "video_id": "p4ou90cHt50",
                "status": "published_public",
                "visibility": "public",
                "slot_id": 2,
                "scheduled_time_et": "2026-10-19 12:00 ET",
            },
        )
        s2 = _seed_hermetic_studio_project(
            projects_dir,
            "test_02_oct21",
            title="How Dopamine Prediction Errors Drive Craving",
            pillar="brain_basics",
            v5_ready=False,
            live_receipt={
                "project_id": "test_02_oct21",
                "video_id": "sP9VZqK1Lm2",
                "status": "published_public",
                "visibility": "public",
                "slot_id": 2,
                "scheduled_time_et": "2026-10-21 12:00 ET",
            },
        )
        for st_obj, target_pid in ((s1, "test_02_oct21"), (s2, "test_01_oct19")):
            (st_obj.get_stage_dir("06_publish") / "related_video_receipt.json").write_text(
                json.dumps({
                    "verified": True,
                    "target_project_id": target_pid,
                    "link_reason": "seed_rescue_from_starved_to_anchor",
                    "playlist_assigned": True,
                    "playlist_title": "Everyday Brain & Neuro-Hacks",
                }),
                encoding="utf-8",
            )

        link_graph_file.write_text(
            json.dumps({
                "edges": [
                    {"source": "test_01_oct19", "target": "test_02_oct21"},
                    {"source": "test_02_oct21", "target": "test_01_oct19"},
                ],
                "two_cycle_count": 1,
            }),
            encoding="utf-8",
        )

        qm = StagingQueueManager(queue_file=queue_file, projects_dir=projects_dir)
        qm.plan_5_slot_schedule(days=3, start_date="2026-10-27", daily_prime_only=True)

        saved_queue = json.loads(queue_file.read_text(encoding="utf-8"))
        hist_by_pid = {h["project_id"]: h for h in saved_queue.get("history", [])}
        assert hist_by_pid["test_01_oct19"]["date"] == "2026-10-19"
        assert hist_by_pid["test_01_oct19"]["time_et"] == "12:00"
        assert hist_by_pid["test_01_oct19"]["slot_id"] == 2
        assert hist_by_pid["test_02_oct21"]["date"] == "2026-10-21"
        assert hist_by_pid["test_02_oct21"]["slot_id"] == 2

        reporter = StudioAnalyticsReporter(
            reports_dir=reports_dir,
            projects_dir=projects_dir,
            queue_file=queue_file,
            short_link_graph_file=link_graph_file,
        )
        res = reporter.generate_daily_report(report_date="2026-10-25", dry_run=True)
        payload = json.loads(Path(res["json_path"]).read_text(encoding="utf-8"))
        md_text = Path(res["markdown_path"]).read_text(encoding="utf-8")

        recs_by_pid = {r["project_id"]: r for r in payload["per_video_records"]}
        assert recs_by_pid["test_01_oct19"]["date"] == "2026-10-19"
        assert recs_by_pid["test_01_oct19"]["time_et"] == "12:00"
        assert recs_by_pid["test_01_oct19"]["slot_id"] == 2
        assert recs_by_pid["test_01_oct19"]["published_slot_str"] == "10-19 12:00"
        assert recs_by_pid["test_01_oct19"]["related_link_role"] == "seed_rescue_from_starved_to_anchor"
        assert recs_by_pid["test_01_oct19"]["playlist_verified"] is True

        assert recs_by_pid["test_02_oct21"]["date"] == "2026-10-21"
        assert recs_by_pid["test_02_oct21"]["published_slot_str"] == "10-21 12:00"

        assert "`10-19 12:00`" in md_text
        assert "`10-21 12:00`" in md_text
        assert "+144h" in md_text
        assert "+96h" in md_text
        assert "`10-25 12:00`" not in md_text
        assert "(+1h)" not in md_text

        assert payload["risk_audit"]["simultaneous_publish_count"] == 0
        assert payload["risk_audit"]["min_publish_gap_hours"] == 48.0
        risk_4 = next(i for i in payload["risk_audit"]["items"] if i["risk_id"] == "RISK-4")
        assert "``" not in risk_4["evidence"]

        serialized = json.dumps(payload["signal_radar"], ensure_ascii=False) + json.dumps(
            payload["diagnostics"], ensure_ascii=False
        )
        assert "2편 Scheduled" not in serialized
        assert "psych_04_phineas_gage_frontal_lobe" not in serialized
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_scheduled_upload_receipt_reconciles_vacant_and_stale_unlisted_queue_slots():
    """
    Verifies mutual exclusivity and vacant-slot subtraction when a project is uploaded via
    `studio-upload --visibility scheduled` while `staging_queue.json` still holds `vacant`
    (`project_id: null`) or stale `unlisted` status on that slot.
    """
    from pipeline.studio.queue_manager import StagingQueueManager
    from tests.test_studio_autonomous import _seed_hermetic_studio_project

    tmp_dir = Path(tempfile.mkdtemp(prefix="test_reporter_sched_receipt_"))
    try:
        projects_dir = tmp_dir / "BCI_Shorts_Channel" / "projects"
        reports_dir = tmp_dir / "BCI_Shorts_Channel" / "reports" / "daily"
        queue_file = tmp_dir / "BCI_Shorts_Channel" / "staging_queue.json"
        link_graph_file = tmp_dir / "BCI_Shorts_Channel" / "short_link_graph.json"
        projects_dir.mkdir(parents=True, exist_ok=True)
        link_graph_file.write_text(json.dumps({"edges": [], "two_cycle_count": 0}), encoding="utf-8")

        _seed_hermetic_studio_project(
            projects_dir,
            "test_01_pub",
            pillar="everyday_neuro",
            v5_ready=False,
            live_receipt={
                "project_id": "test_01_pub",
                "video_id": "p4ou90cHt50",
                "status": "published_public",
                "visibility": "public",
                "slot_id": 2,
                "scheduled_time_et": "2026-10-21 12:00 ET",
            },
        )
        _seed_hermetic_studio_project(
            projects_dir,
            "test_02_sched",
            title="How Split Brains Reveal Dual Consciousness",
            pillar="brain_mysteries",
            v5_ready=True,
            live_receipt={
                "project_id": "test_02_sched",
                "video_id": "ScHeDuLeD12",
                "status": "uploaded",
                "visibility": "scheduled",
                "slot_id": 2,
                "scheduled_time_et": "2026-10-27 12:00 ET",
            },
        )

        # Case A: Queue still shows 2026-10-27_slot2 as vacant (`project_id: null`) + 3 other vacant slots
        queue_file.write_text(
            json.dumps({
                "channel_id": "UC4FeioYYv9X04Di07_MfZ7g",
                "scheduled_items": [
                    {"schedule_id": "2026-10-27_slot2", "project_id": None, "date": "2026-10-27", "slot_id": 2, "time_et": "12:00", "status": "vacant"},
                    {"schedule_id": "2026-10-27_slot4", "project_id": None, "date": "2026-10-27", "slot_id": 4, "time_et": "20:00", "status": "vacant"},
                    {"schedule_id": "2026-10-28_slot2", "project_id": None, "date": "2026-10-28", "slot_id": 2, "time_et": "12:00", "status": "vacant"},
                    {"schedule_id": "2026-10-28_slot4", "project_id": None, "date": "2026-10-28", "slot_id": 4, "time_et": "20:00", "status": "vacant"},
                ],
                "history": [],
            }),
            encoding="utf-8",
        )

        qm = StagingQueueManager(queue_file=queue_file, projects_dir=projects_dir)
        q_sum = qm.get_status_summary()
        assert q_sum["scheduled_slots_count"] == 1
        assert q_sum["vacant_slots_count"] == 3
        assert q_sum["staged_in_buffer"] == 1
        assert q_sum["total_completed_projects"] == 2

        reporter = StudioAnalyticsReporter(
            reports_dir=reports_dir,
            projects_dir=projects_dir,
            queue_file=queue_file,
            short_link_graph_file=link_graph_file,
        )
        st_a = reporter._collect_local_pipeline_state("2026-10-25")
        assert st_a["published_count"] == 1
        assert st_a["scheduled_count"] == 1
        assert st_a["unlisted_staged_count"] == 0
        assert st_a["staged_buffer_count"] == 1
        assert st_a["vacant_slot_count"] == 3
        assert len(st_a["upcoming_schedule"]) == 1
        assert st_a["upcoming_schedule"][0]["project_id"] == "test_02_sched"
        assert st_a["upcoming_schedule"][0]["slot_id"] == 2

        # Case B: Queue has stale `status: "unlisted"` on 2026-10-27_slot2 while receipt is `scheduled`
        queue_file.write_text(
            json.dumps({
                "channel_id": "UC4FeioYYv9X04Di07_MfZ7g",
                "scheduled_items": [
                    {"schedule_id": "2026-10-27_slot2", "project_id": "test_02_sched", "date": "2026-10-27", "slot_id": 2, "time_et": "12:00", "status": "unlisted"},
                    {"schedule_id": "2026-10-27_slot4", "project_id": None, "date": "2026-10-27", "slot_id": 4, "time_et": "20:00", "status": "vacant"},
                ],
                "history": [],
            }),
            encoding="utf-8",
        )
        st_b = reporter._collect_local_pipeline_state("2026-10-25")
        assert st_b["scheduled_count"] == 1
        assert st_b["unlisted_staged_count"] == 0
        assert st_b["staged_buffer_count"] == 1
        assert st_b["vacant_slot_count"] == 1
        assert len(st_b["upcoming_schedule"]) == 1
        assert st_b["upcoming_schedule"][0]["status"] == "scheduled"
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_unrendered_awaiting_render_and_error_queue_items_excluded():
    """
    Verifies that unrendered Gear-2 v5 drafts (`status: "awaiting_render"`, no MP4) and
    failed upload queue entries (`status: "error: ..."`) never inflate `scheduled_count`,
    `upcoming_schedule`, or `total_completed_inventory`.
    """
    from pipeline.studio.queue_manager import StagingQueueManager
    from tests.test_studio_autonomous import _seed_hermetic_studio_project

    tmp_dir = Path(tempfile.mkdtemp(prefix="test_reporter_awaiting_render_"))
    try:
        projects_dir = tmp_dir / "BCI_Shorts_Channel" / "projects"
        reports_dir = tmp_dir / "BCI_Shorts_Channel" / "reports" / "daily"
        queue_file = tmp_dir / "BCI_Shorts_Channel" / "staging_queue.json"
        link_graph_file = tmp_dir / "BCI_Shorts_Channel" / "short_link_graph.json"
        projects_dir.mkdir(parents=True, exist_ok=True)
        link_graph_file.write_text(json.dumps({"edges": [], "two_cycle_count": 0}), encoding="utf-8")

        # 1. Gear-2 v5 draft without rendered MP4
        draft_storage = _seed_hermetic_studio_project(
            projects_dir,
            "test_03_gear2_draft",
            pillar="brain_history",
            v5_ready=True,
        )
        (draft_storage.get_stage_dir("05_assembly") / "final_shorts_1080x1920.mp4").unlink()

        # 2. Rendered v5 project whose upload attempt failed (`error: cdp timeout`)
        _seed_hermetic_studio_project(
            projects_dir,
            "test_04_upload_failed",
            pillar="bci_tech",
            v5_ready=True,
        )

        queue_file.write_text(
            json.dumps({
                "channel_id": "UC4FeioYYv9X04Di07_MfZ7g",
                "scheduled_items": [
                    {"schedule_id": "2026-10-27_slot2", "project_id": "test_03_gear2_draft", "date": "2026-10-27", "slot_id": 2, "time_et": "12:00", "status": "awaiting_render"},
                    {"schedule_id": "2026-10-27_slot4", "project_id": "test_04_upload_failed", "date": "2026-10-27", "slot_id": 4, "time_et": "20:00", "status": "error: cdp timeout"},
                ],
                "history": [],
            }),
            encoding="utf-8",
        )

        qm = StagingQueueManager(queue_file=queue_file, projects_dir=projects_dir)
        q_sum = qm.get_status_summary()
        assert q_sum["scheduled_slots_count"] == 0
        assert q_sum["staged_in_buffer"] == 0
        assert q_sum["total_completed_projects"] == 1
        assert q_sum["v5_ready_unpublished_count"] == 1
        assert q_sum["pending_staging"] == 1

        reporter = StudioAnalyticsReporter(
            reports_dir=reports_dir,
            projects_dir=projects_dir,
            queue_file=queue_file,
            short_link_graph_file=link_graph_file,
        )
        st = reporter._collect_local_pipeline_state("2026-10-25")
        assert st["published_count"] == 0
        assert st["scheduled_count"] == 0
        assert st["unlisted_staged_count"] == 0
        assert st["total_completed_inventory"] == 1
        assert st["staged_buffer_count"] == 1
        assert st["upcoming_schedule"] == []
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

