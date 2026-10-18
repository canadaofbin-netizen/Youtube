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
        # Verify all 9 standardized sections exist
        for sec_num in range(1, 10):
            assert f"## {sec_num}." in md_text

        # Verify all 5 inline Mermaid xychart-beta graphs exist
        assert md_text.count("xychart-beta") == 5
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

        # Verify Unlisted badge, Q1-Q4 table, Section 8-3 Risk Audit, and Section 9-4 Provenance
        assert "🔒 Unlisted (Staged)" in md_text
        assert "### 8-3. 🚨 채널 운영 및 파이프라인 7대 위험 진단 매트릭스" in md_text
        assert "### 9-4. 🔐 Raw Snapshot & Provenance" in md_text
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

        # Verify Per-Video Notable Change Detection & 3-Axis Root-Cause Attribution (Section 6-2)
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
        assert "### 6-2. 🔎 특정 영상별 눈에 띄는 변화 감지 및 심층 원인 분석" in md_text
        assert "왜 그런 변화가 발생했는가 ① [대본·사례·훅" in md_text
        assert "왜 그런 변화가 발생했는가 ② [4분위 리텐션·비주얼 해부" in md_text
        assert "왜 그런 변화가 발생했는가 ③ [트래픽·검색어·썸네일·슬롯" in md_text

        # Verify Success vs. Failure/Risk Signal Detection & Amplification Playbook (Section 9-1..9-3)
        assert "signal_radar" in payload
        sr = payload["signal_radar"]
        assert len(sr["success_signals"]) == 5
        assert len(sr["failure_risk_signals"]) == 5
        assert len(sr["amplification_strategies"]) == 5
        assert [s["signal_id"] for s in sr["success_signals"]] == [f"SIG-WIN-{i}" for i in range(1, 6)]
        assert [s["signal_id"] for s in sr["failure_risk_signals"]] == [f"SIG-FAIL-{i}" for i in range(1, 6)]
        assert [a["strategy_id"] for a in sr["amplification_strategies"]] == [f"AMP-{i}" for i in range(1, 6)]
        assert "#### 🟢 [표 9-1] 성공 시그널(Success Signals) 조기 감지 매트릭스" in md_text
        assert "#### 🔴 [표 9-2] 실패 및 위험 시그널(Failure & Risk Signals) 조기 감지 매트릭스" in md_text
        assert "#### 🚀 [표 9-3] 성공 시그널 증폭(Success Signal Amplification) 5-Gear 실행 플레이북" in md_text
        for i in range(1, 6):
            assert f"SIG-WIN-{i}" in md_text
            assert f"SIG-FAIL-{i}" in md_text
            assert f"AMP-{i}" in md_text

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

        # Verify DAILY_REPORT_MASTER_PROMPT.md template is synchronized with the 9-section schema
        master_prompt_text = Path(res_day2["master_prompt_path"]).read_text(encoding="utf-8")
        assert "### 6-2." in master_prompt_text
        assert "### 8-3." in master_prompt_text
        assert "[표 9-1]" in master_prompt_text
        assert "[표 9-2]" in master_prompt_text
        assert "[표 9-3]" in master_prompt_text
        assert "뫼비우스 루프" not in master_prompt_text

        # Edge case: future report_date beyond queue dates falls back to last 10 queue items
        future_state = reporter._collect_local_pipeline_state("2099-12-31")
        assert len(future_state["upcoming_schedule"]) <= 10
        if future_state["raw_queue_items"]:
            assert future_state["upcoming_schedule"] == future_state["raw_queue_items"][-10:]
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
