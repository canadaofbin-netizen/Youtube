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

        # Verify custom reports_dir writes LATEST_DAILY_REPORT.md and LATEST_VIDEO_DETAIL_REPORT.md inside tmp_dir, not global root
        assert Path(res_day2["latest_report_path"]).parent == tmp_dir
        assert Path(res_day2["latest_video_detail_report_path"]).parent == tmp_dir
        assert Path(res_day2["video_detail_markdown_path"]).exists()
        assert Path(res_day2["video_detail_charts_path"]).exists()
        assert Path(res_day2["video_detail_charts_path"]).stat().st_size > 30_000
        v_detail_text = Path(res_day2["video_detail_markdown_path"]).read_text(encoding="utf-8")
        assert "개별 영상 세부 보고서" in v_detail_text
        assert "전 영상 신호등 요약 매트릭스" in v_detail_text
        assert "영상별 심층 진단 카드" in v_detail_text
        assert "2026-10-17_video_detail_charts.png" in v_detail_text
        assert "Cohort #1" in v_detail_text

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


def test_new_studio_insights_uk_english_and_shadow_row_parsing():
    """
    Regression test for YouTube Studio 'Channel insights / Video insights' DOM text
    (UK-English dates, 'Total subscribers', '48-hour views', 'Engaged views 5.4K',
    '75.0%\\nStayed to watch\\n25.0%\\nSwiped away', and pre-label AVD/APV/00:30 retention).
    """
    row_txt = (
        "1:55 How Trying to Fall Asleep Backfires In Public Health 1996 and 2018 studies, "
        "volunteers wired 57 young adults — Public 14 Nov 2026 Published 531 1"
    )
    row_parsed = StudioAnalyticsReporter._parse_video_row_text(row_txt)
    assert row_parsed["views"] == 531
    assert row_parsed["comments"] == 1

    overview_txt = (
        "Channel insights\nViews\n8.5K\nWatch time (hours)\n133.1\nSubscribers\n+61\n"
        "48-hour views\n204\nTotal subscribers\n61\n"
    )
    ov_parsed = StudioAnalyticsReporter._parse_analytics_text_block(overview_txt)
    assert ov_parsed["views_28d"] == 8500
    assert "views_24h" not in ov_parsed
    assert ov_parsed["watch_hours_28d"] == 133.1
    assert ov_parsed["subscribers_total"] == 61
    assert ov_parsed["subscribers_gained_28d"] == 61
    assert ov_parsed["realtime_48h_views"] == 204

    content_txt = (
        "Content\nViews\n8.5K\nEngaged views\n5.4K\nLikes\n370\n"
        "How viewers engaged\nLast 28 days\n75.0%\nStayed to watch\n25.0%\nSwiped away\n"
        "Shorts feed\n90.6%\nYouTube search\n6.5%\n"
    )
    ct_parsed = StudioAnalyticsReporter._parse_analytics_text_block(content_txt)
    assert ct_parsed["engaged_views"] == 5400
    assert ct_parsed["likes_total"] == 370
    assert ct_parsed["viewed_pct"] == 75.0
    assert ct_parsed["swiped_pct"] == 25.0
    assert ct_parsed["traffic_sources_map"]["Shorts feed"] == 90.6

    audience_txt = (
        "Device type\nMobile phone\n78.9%\nTV\n7.4%\n"
        "Watch time from subscribers\n0.7%\nSubscribed\n99.3%\nNot subscribed\n"
        "Top geographies\nUnited States\n66.8%\n"
    )
    aud_parsed = StudioAnalyticsReporter._parse_analytics_text_block(audience_txt)
    assert aud_parsed["tv_device_pct"] == 7.4
    assert aud_parsed["subscribed_watch_pct"] == 0.7
    assert aud_parsed["non_subscribed_watch_pct"] == 99.3
    assert aud_parsed["geographies_map"]["US"] == 66.8

    vid_ov_txt = (
        "Video insights\nViews\n531\nWatch time (hours)\n8.3\nSubscribers\n+6\n"
        "48-hour views\n69\nHow viewers engaged\nSince published\n76.5%\nStayed to watch\n"
        "23.5%\nSwiped away\nLikes\nSince published\n18\n"
    )
    vid_eng_txt = (
        "Engagement\nEngaged views\n375\n"
        "Average view duration\n1:19\n1:07\n2:00\n1:00\n0:00\nAverage view duration\n"
        "Key moments for audience retention\nSince published\n"
        "1:19\nAverage view duration\n69%\nAverage percentage viewed\n"
        "82.2%\nStill watching at 00:30\n"
    )
    pv = StudioAnalyticsReporter._parse_video_analytics_overview(vid_ov_txt)
    pv_eng = StudioAnalyticsReporter._parse_video_analytics_overview(vid_eng_txt)
    for k, v in pv_eng.items():
        pv.setdefault(k, v)
    assert pv["views"] == 531
    assert pv["engaged_views"] == 375
    assert pv["watch_hours"] == 8.3
    assert pv["subs_gained"] == 6
    assert pv["realtime_48h"] == 69
    assert pv["likes"] == 18
    assert pv["viewed_pct"] == 76.5
    assert pv["swiped_pct"] == 23.5
    assert pv["avd_sec"] == 79.0
    assert pv["apv_pct"] == 69.0
    assert pv["ret_30s_mark_pct"] == 82.2


def test_studio_reporter_period_separation_dom_honesty_and_outlier_masking(tmp_path: Path):
    """
    Regression test for [STUDIO_REPORTER_FIX_DONE]:
      1. Period-specific URLs (`period-week` vs `period-default`) in `STUDIO_ANALYTICS_URLS`
         and zero `views_24h = views_28d` or `7d == 28d == cumulative` cloning.
      2. Zero hardcoded fake `realtime_60m_views: 32` or `unique_viewers_*: 1200` (`None` when absent,
         parsed integers when present in DOM).
      3. Missing-'K' corrupted historical snapshots (`views=8, subs=6` with `watch_hours>=120`)
         masked as `None` outliers in `trend_7d` and `snapshot_3d_ago` / `snapshot_7d_ago`.
    """
    from pipeline.studio.config import STUDIO_ANALYTICS_URLS

    assert "period-week" in STUDIO_ANALYTICS_URLS["analytics_overview_7d"]
    assert "period-default" in STUDIO_ANALYTICS_URLS["analytics_overview_28d"]
    assert "period-week" in STUDIO_ANALYTICS_URLS["analytics_audience_7d"]

    # 1. Period-specific DOM parsing (7d vs 28d, plus realtime 60m & unique viewers)
    ov_7d = StudioAnalyticsReporter._parse_analytics_text_block(
        "Your channel got 1.4K views in the last 7 days\nWatch time (hours)\n21.5\n"
        "Subscribers\n+9\n60-minute views\n11\nUnique viewers\n980\n",
        period_hint="7d",
    )
    assert ov_7d["views_7d"] == 1400
    assert "views_24h" not in ov_7d
    assert "views_28d" not in ov_7d
    assert ov_7d["watch_hours_7d"] == 21.5
    assert ov_7d["subscribers_gained_7d"] == 9
    assert ov_7d["realtime_60m_views"] == 11
    assert ov_7d["unique_viewers_7d"] == 980

    ov_28d = StudioAnalyticsReporter._parse_analytics_text_block(
        "Your channel got 8.9K views in the last 28 days\nWatch time (hours)\n133.8\n"
        "Subscribers\n+61\nUnique viewers\n6.2K\n",
        period_hint="28d",
    )
    assert ov_28d["views_28d"] == 8900
    assert "views_24h" not in ov_28d
    assert ov_28d["watch_hours_28d"] == 133.8
    assert ov_28d["subscribers_gained_28d"] == 61
    assert ov_28d["unique_viewers_28d"] == 6200

    # 2 & 3. Missing-K outlier masking (11/13..11/15 views=8, subs=6) + None when 60m/unique unscraped
    seed_snaps = {
        "2026-11-12": {"views": 8668, "subs": 55, "wh": 127.4},
        "2026-11-13": {"views": 8, "subs": 6, "wh": 127.3},
        "2026-11-14": {"views": 8, "subs": 6, "wh": 126.9},
        "2026-11-15": {"views": 8, "subs": 6, "wh": 132.6},
        "2026-11-16": {"views": 8804, "subs": 61, "wh": 133.1},
        "2026-11-17": {"views": 8857, "subs": 61, "wh": 133.8},
    }
    for d_iso, vals in seed_snaps.items():
        (tmp_path / f"{d_iso}_studio_metrics.json").write_text(
            json.dumps(
                {
                    "report_date": d_iso,
                    "data_source_mode": "LIVE_CDP_DOM",
                    "channel_kpis": {
                        "views_24h": vals["views"],
                        "subscribers_total": vals["subs"],
                        "watch_hours_24h": vals["wh"],
                        "realtime_48h_views": 180,
                        "realtime_60m_views": 32,
                        "unique_viewers_24h": 1200,
                    },
                    "retention_kpis": {"viewed_pct": 72.0, "avd_seconds": 54.0, "apv_pct": 66.0},
                    "traffic_sources": [{"short_name": "Shorts Feed", "pct": 88.0}],
                    "geographies": [{"country": "US", "pct": 58.0}],
                }
            ),
            encoding="utf-8",
        )

    rep = StudioAnalyticsReporter(reports_dir=tmp_path)
    out = rep.generate_daily_report(report_date="2026-11-18", compare_date="2026-11-17", dry_run=True)
    payload = json.loads(Path(out["json_path"]).read_text(encoding="utf-8"))
    ck = payload["channel_kpis"]
    t7 = payload["trend_7d"]

    # Hardcoded 32 and 1200 must be gone (None when unscraped)
    assert ck["realtime_60m_views"] is None
    assert ck["realtime_60m_prev"] is None
    assert ck["unique_viewers_24h"] is None
    assert ck["unique_viewers_7d"] is None
    assert ck["unique_viewers_28d"] is None

    # Explicit separated cumulative vs 1d delta vs 7d vs 28d keys (zero blind cloning!)
    assert "views_cumulative" in ck and "views_delta_1d" in ck
    assert ck["views_7d"] != ck["views_cumulative"]
    assert ck["subscribers_7d"] != ck["subscribers_total"]
    assert ck["subscribers_28d"] is None

    # 11/13, 11/14, 11/15 corrupted views=8/subs=6 MUST be masked as None outliers!
    assert t7["masked_outlier_dates"] == ["2026-11-13", "2026-11-14", "2026-11-15"]
    assert t7["views"][1:4] == [None, None, None]
    assert t7["subscribers"][1:4] == [None, None, None]
    assert t7["snapshot_3d_ago"]["outlier_masked"] is True
    assert t7["snapshot_3d_ago"]["views"] is None
    assert t7["snapshot_3d_ago"]["subscribers"] is None


def test_studio_reporter_7d_dom_period_guard_blocks_28d_leakage(tmp_path: Path):
    """
    Regression test for [STUDIO_REPORTER_7D_FIX_ORDER]:
      1. When `period_hint='7d'` receives a DOM still showing `Last 28 days` / `지난 28일`
         (e.g. Studio SPA ignoring `/period-week`), `views_7d`, `watch_hours_7d`,
         `subscribers_gained_7d`, and `unique_viewers_7d` MUST stay absent (`None`).
      2. `+55 in the last 28 days` NEVER leaks into `subscribers_gained_7d`, and
         `+9 in the last 7 days` NEVER leaks into `subscribers_gained_28d`.
      3. Korean `지난 7일` DOM succeeds cleanly while `지난 28일` DOM is blocked under `7d`.
      4. `sec1_channel_growth.png` renders cleanly with `N/A` labels on masked outlier dates.
    """
    # 1. English 28d DOM mistakenly passed under period_hint='7d' (exact 2026-11-19 failure mode)
    stale_28d_dom = (
        "Channel analytics\nLast 28 days\n"
        "Your channel got 7.3K views in the last 28 days\n"
        "Views\n7.3K\n"
        "Watch time (hours)\n120.0\n"
        "Subscribers\n+55\n+55 in the last 28 days\n"
        "Unique viewers\n5.1K\n"
    )
    res_7d_guarded = StudioAnalyticsReporter._parse_analytics_text_block(stale_28d_dom, period_hint="7d")
    assert "views_7d" not in res_7d_guarded
    assert "watch_hours_7d" not in res_7d_guarded
    assert "subscribers_gained_7d" not in res_7d_guarded
    assert "unique_viewers_7d" not in res_7d_guarded
    assert "views_28d" not in res_7d_guarded
    assert "subscribers_gained_28d" not in res_7d_guarded

    # 2. Korean 28d DOM under period_hint='7d' -> blocked; Korean 7d DOM -> accepted
    ko_28d_dom = "채널 분석\n지난 28일\n조회수\n7.3천\n시청 시간(단위: 시간)\n120.0\n구독자\n+55\n순 시청자\n5.1천\n"
    res_ko_28_as_7 = StudioAnalyticsReporter._parse_analytics_text_block(ko_28d_dom, period_hint="7d")
    assert "views_7d" not in res_ko_28_as_7
    assert "watch_hours_7d" not in res_ko_28_as_7
    assert "subscribers_gained_7d" not in res_ko_28_as_7
    assert "unique_viewers_7d" not in res_ko_28_as_7

    ko_7d_dom = "채널 분석\n지난 7일\n조회수\n1.2천\n시청 시간(단위: 시간)\n18.4\n구독자\n+7\n순 시청자\n890\n"
    res_ko_7d = StudioAnalyticsReporter._parse_analytics_text_block(ko_7d_dom, period_hint="7d")
    assert res_ko_7d["views_7d"] == 1200
    assert res_ko_7d["watch_hours_7d"] == 18.4
    assert res_ko_7d["subscribers_gained_7d"] == 7
    assert res_ko_7d["unique_viewers_7d"] == 890

    # 3. Unmarked DOM (no Last 7 days header at all) under period_hint='7d' -> refused
    unmarked_dom = "Views\n7.3K\nWatch time (hours)\n120.0\nSubscribers\n+55\n"
    res_unmarked = StudioAnalyticsReporter._parse_analytics_text_block(unmarked_dom, period_hint="7d")
    assert "views_7d" not in res_unmarked
    assert "watch_hours_7d" not in res_unmarked
    assert "subscribers_gained_7d" not in res_unmarked

    # 4. Explicit 7d subscriber delta under period_hint='28d' never contaminates subscribers_gained_28d
    mixed_28d = "Last 28 days\n+9 in the last 7 days\n+55 in the last 28 days\nWatch time (hours)\n120.0\n"
    res_28d = StudioAnalyticsReporter._parse_analytics_text_block(mixed_28d, period_hint="28d")
    assert res_28d["subscribers_gained_7d"] == 9
    assert res_28d["subscribers_gained_28d"] == 55
    assert res_28d["watch_hours_28d"] == 120.0

    # 4b. New YouTube Studio Insights Hub (`hub_overview`) DOM where Key metrics is switched to `7 days`
    # while lower `Top content` still prints `Last 28 days`:
    hub_7d_dom = (
        "Channel insights\nKey metrics\n7 days\n28 days\n90 days\nMore\n"
        "Views\n811\nNov 11, 2026\nNov 17, 2026\n"
        "Watch time (hours)\n9.9\nSubscribers\n+6\n48-hour views\n47\n"
        "Top content\nViews • Last 28 days\nSome Video\n2.0K\n"
    )
    # Without live chip verification (`verified_dom_period=None`), lower `Last 28 days` blocks accidental 7d capture
    res_hub_unverified = StudioAnalyticsReporter._parse_analytics_text_block(hub_7d_dom, period_hint="7d")
    assert "views_7d" not in res_hub_unverified
    assert "watch_hours_7d" not in res_hub_unverified
    assert "subscribers_gained_7d" not in res_hub_unverified
    # With live chip verification (`verified_dom_period='7d'` from aria-selected='true'), exact 7d KPIs are extracted
    res_hub_verified = StudioAnalyticsReporter._parse_analytics_text_block(
        hub_7d_dom,
        period_hint="7d",
        verified_dom_period="7d",
    )
    assert res_hub_verified["views_7d"] == 811
    assert res_hub_verified["watch_hours_7d"] == 9.9
    assert res_hub_verified["subscribers_gained_7d"] == 6
    assert "views_28d" not in res_hub_verified

    # 5. Chart generation with masked outlier dates produces sec1_channel_growth.png cleanly
    for d_iso, v_val in (("2026-11-12", 8668), ("2026-11-13", 8), ("2026-11-14", 8), ("2026-11-15", 8), ("2026-11-17", 8857)):
        (tmp_path / f"{d_iso}_studio_metrics.json").write_text(
            json.dumps(
                {
                    "report_date": d_iso,
                    "data_source_mode": "LIVE_CDP_DOM",
                    "channel_kpis": {"views_24h": v_val, "subscribers_total": 61 if v_val > 100 else 6, "watch_hours_24h": 133.0},
                    "retention_kpis": {"viewed_pct": 72.0, "avd_seconds": 54.0, "apv_pct": 66.0},
                    "traffic_sources": [{"short_name": "Shorts Feed", "pct": 88.0}],
                    "geographies": [{"country": "US", "pct": 58.0}],
                }
            ),
            encoding="utf-8",
        )
    rep = StudioAnalyticsReporter(reports_dir=tmp_path)
    out = rep.generate_daily_report(report_date="2026-11-18", compare_date="2026-11-17", dry_run=True)
    sec1_png = tmp_path / "2026-11-18_sec1_channel_growth.png"
    assert sec1_png.is_file() and sec1_png.stat().st_size > 10_000
    assert Path(out["json_path"]).is_file()

    md_txt = Path(out["markdown_path"]).read_text(encoding="utf-8")
    assert "`outlier`" in md_txt
    assert "`unscraped`" in md_txt


def test_r87_lock4_retention_regression_alert_triggered_and_cleared(tmp_path: Path) -> None:
    """Lock 4: +48h & >=15 views consecutive >=2 dip (<70% 3s hook OR <60% APV) triggers alert & top banner."""
    from pipeline.studio.reporter import StudioAnalyticsReporter

    # 1. Triggered: latest 2 qualifying (+48h, views >= 15) videos dip below 70% hook or 60% APV;
    #    young (<48h) and low-view (<15) videos are cleanly excluded from breaking or faking the streak.
    recs_bad = [
        {
            "video_id": "v_ok_1",
            "project_id": "v8_ep06_ok",
            "status": "published",
            "measured": True,
            "date": "2026-11-12",
            "time_et": "12:00",
            "views": 500,
            "viewed_pct": 76.0,
            "apv_pct": 68.0,
        },
        {
            "video_id": "v_dip_1",
            "project_id": "v8_ep07_dip",
            "status": "published",
            "measured": True,
            "date": "2026-11-14",
            "time_et": "12:00",
            "views": 37,
            "viewed_pct": 30.0,
            "apv_pct": 53.5,
        },
        {
            "video_id": "v_dip_2",
            "project_id": "v8_ep08_dip",
            "status": "published",
            "measured": True,
            "date": "2026-11-16",
            "time_et": "12:00",
            "views": 102,
            "viewed_pct": 64.3,
            "apv_pct": 64.0,
        },
        {
            # Only +12h old -> excluded from +48h regression window
            "video_id": "v_fresh",
            "project_id": "v8_ep10_fresh",
            "status": "published",
            "measured": True,
            "date": "2026-11-20",
            "time_et": "00:00",
            "views": 80,
            "viewed_pct": 88.0,
            "apv_pct": 85.0,
        },
        {
            # Views < 15 -> excluded
            "video_id": "v_low",
            "project_id": "v8_ep09_low",
            "status": "published",
            "measured": True,
            "date": "2026-11-17",
            "time_et": "12:00",
            "views": 9,
            "viewed_pct": 90.0,
            "apv_pct": 90.0,
        },
    ]
    alert_on = StudioAnalyticsReporter.detect_retention_regression_alert(
        recs_bad, report_date="2026-11-20", generated_at_et="2026-11-20 12:00 ET"
    )
    assert alert_on["triggered"] is True
    assert alert_on["consecutive_count"] == 2
    assert [v["project_id"] for v in alert_on["affected_videos"]] == ["v8_ep07_dip", "v8_ep08_dip"]
    assert "⚠️ [RETENTION_REGRESSION_ALERT]" in alert_on["banner"]

    # 2. Non-triggered: latest qualifying video recovers (>=70% hook AND >=60% APV)
    recs_recovered = recs_bad[:3] + [
        {
            "video_id": "v_rec_1",
            "project_id": "v8_ep13_recovered",
            "status": "published",
            "measured": True,
            "date": "2026-11-18",
            "time_et": "11:00",
            "views": 180,
            "viewed_pct": 82.5,
            "apv_pct": 71.0,
        }
    ]
    alert_off = StudioAnalyticsReporter.detect_retention_regression_alert(
        recs_recovered, report_date="2026-11-20", generated_at_et="2026-11-20 12:00 ET"
    )
    assert alert_off["triggered"] is False
    assert alert_off["affected_videos"] == []
    assert alert_off["banner"] == ""

    # 3. Markdown top-of-report banner rendering check
    rep = StudioAnalyticsReporter(reports_dir=tmp_path)
    out = rep.generate_daily_report(report_date="2026-11-20", compare_date="2026-11-19", dry_run=True)
    metrics_doc = json.loads(Path(out["json_path"]).read_text(encoding="utf-8"))
    assert "retention_regression_alert" in metrics_doc
    metrics_doc["retention_regression_alert"] = alert_on
    md_with_banner = rep.render_markdown_report(metrics_doc, charts_filename="charts.png")
    first_300 = md_with_banner[:450]
    assert "⚠️ [RETENTION_REGRESSION_ALERT]" in first_300
    assert "v8_ep07_dip" in first_300
    assert "v8_ep08_dip" in first_300




