"""
Unit & Integration Tests for Cross-Platform QA Scheduler v2 (Workstream 4C):
  - 1-Episode -> 5 Automated Assets ecosystem stagger & offsets
  - Trial Reels >=1,000 follower threshold
  - 4:5 (1080x1350) Carousel anti-cannibalization (>=18h gap) & <=3/wk cap
  - 6 Permanent Anti-Trap Guardrails & On-Hold feature exclusions
  - Daily Zero-Bounce Studio Inbox Check & dual daily/schedule report outputs
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import struct
import zlib

from pipeline.studio.qa_scheduler import (
    IG_CAROUSEL_MIN_GAP_FROM_REEL_HOURS,
    evaluate_qa_schedule,
    run_qa_scheduler,
)


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _write_minimal_png(path: Path, width: int, height: int) -> None:
    """Writes a valid minimal RGBA PNG with exact IHDR width/height (zero deps)."""
    path.parent.mkdir(parents=True, exist_ok=True)

    def _chunk(ctype: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(ctype + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + ctype + data + struct.pack(">I", crc)

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    raw_row = b"\x00" + b"\x00\x00\x00\xff"
    idat = zlib.compress(raw_row)
    png_bytes = b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", ihdr) + _chunk(b"IDAT", idat) + _chunk(b"IEND", b"")
    path.write_bytes(png_bytes)


def _seed_daily_report(
    daily_dir: Path,
    reports_root: Path,
    now_utc: datetime,
    *,
    report_date: str = "2026-11-15",
    instagram_followers: int = 120,
    auto_dubbing_checked: bool = False,
) -> None:
    metrics = {
        "report_date": report_date,
        "generated_at_utc": (now_utc - timedelta(hours=1)).isoformat(),
        "data_source_mode": "LIVE_CDP_DOM",
        "live_scraped_meta": {"live_connected": True, "studio_authenticated": True},
        "inventory_summary": {"published_count": 15, "scheduled_count": 1, "quarantine_count": 0},
        "short_link_summary": {"published_total": 15, "related_verified_count": 15, "ring_complete": True},
        "channel_kpis": {
            "subscribers_total": 12,
            "views_24h": 650,
            "views_prev": 540,
            "watch_hours_24h": 48.0,
            "realtime_48h_views": 1411,
            "realtime_60m_views": 32,
        },
        "instagram_followers": instagram_followers,
        "auto_dubbing_checked": auto_dubbing_checked,
        "retention_kpis": {"viewed_pct": 74.0, "apv_pct": 66.0, "avd_seconds": 52.0},
        "traffic_sources": [{"short_name": "Shorts Feed", "pct": 87.0}],
        "geographies": [{"country": "US", "pct": 58.0}],
        "risk_audit": {
            "measured_video_count": 15,
            "unscraped_video_count": 0,
            "simultaneous_publish_count": 0,
            "quarantine_count": 0,
        },
    }
    _write_json(daily_dir / f"{report_date}_studio_metrics.json", metrics)
    _write_json(reports_root / "studio_playlist_purge_receipt.json", {"remaining_count": 0, "status": "purged_zero_verified"})


def _seed_project(
    projects_dir: Path,
    pid: str,
    *,
    duration_sec: float = 76.87,
    with_bundle: bool = True,
    yt_receipt: dict | None = None,
    quiz_receipt: dict | None = None,
    ig_receipt: dict | None = None,
    carousel_receipt: dict | None = None,
    tt_receipt: dict | None = None,
    carousel_dims: tuple[int, int] | None = None,
    metadata_extra: dict | None = None,
    checklist_extra: dict | None = None,
) -> Path:
    p_dir = projects_dir / pid
    (p_dir / "05_assembly").mkdir(parents=True, exist_ok=True)
    (p_dir / "05_assembly" / "final_shorts_1080x1920.mp4").write_bytes(b"mp4data")
    _write_json(p_dir / "00_project_manifest.json", {"project_id": pid, "production_profile": "classic"})
    _write_json(p_dir / "05_assembly" / "probe_report.json", {"duration_sec": duration_sec})
    _write_json(p_dir / "05_assembly" / "video_autopsy_report.json", {"passed": True})
    if metadata_extra:
        _write_json(p_dir / "06_publish" / "metadata.json", metadata_extra)
    if with_bundle:
        b_dir = p_dir / "06_publish" / "multi_platform_bundle"
        b_dir.mkdir(parents=True, exist_ok=True)
        (b_dir / "video_clean.mp4").write_bytes(b"clean")
        (b_dir / "cover_9x16.png").write_bytes(b"png")
        (b_dir / "tiktok_caption.txt").write_text("Test hook\n\n#neuroscience #psychology #brainfacts #memory", encoding="utf-8")
        (b_dir / "reels_caption.txt").write_text("Test hook\n\n#neuroscience #psychology #brainfacts #memory", encoding="utf-8")
        chk = {"duration_sec": duration_sec, "tiktok_over_60s_eligible": duration_sec >= 61.5}
        if checklist_extra:
            chk.update(checklist_extra)
        _write_json(b_dir / "upload_checklist.json", chk)
    if yt_receipt:
        _write_json(p_dir / "06_publish" / "upload_receipt.json", yt_receipt)
    if quiz_receipt:
        _write_json(p_dir / "06_publish" / "community_quiz_receipt.json", quiz_receipt)
    if ig_receipt:
        _write_json(p_dir / "06_publish" / "instagram_upload_receipt.json", ig_receipt)
    if carousel_receipt:
        _write_json(p_dir / "06_publish" / "instagram_carousel_receipt.json", carousel_receipt)
    if tt_receipt:
        _write_json(p_dir / "06_publish" / "tiktok_upload_receipt.json", tt_receipt)
    if carousel_dims:
        w, h = carousel_dims
        for idx in range(1, 7):
            _write_minimal_png(p_dir / "06_publish" / "ig_carousel" / f"slide_{idx:02d}.png", w, h)
    return p_dir


def test_five_asset_ecosystem_stagger_and_quiz_receipt_state(tmp_path: Path) -> None:
    # 2026-11-15 08:00 UTC = 03:00 EST
    now = datetime(2026, 11, 15, 8, 0, tzinfo=timezone.utc)
    proj_dir = tmp_path / "projects"
    rep_root = tmp_path / "reports"
    daily_dir = rep_root / "daily"
    sched_dir = rep_root / "schedule"
    _seed_daily_report(daily_dir, rep_root, now, instagram_followers=250)

    # Active scheduled Ep #8 tonight at 2026-11-15 19:30 EST (= 2026-11-16T00:30Z)
    _seed_project(
        proj_dir,
        "v8_ep08_capgras_imposter_delusion_r77",
        duration_sec=76.87,
        yt_receipt={
            "video_id": "Atd0Pi9HPg4",
            "visibility": "scheduled",
            "scheduled_time_et": "2026-11-15 19:30 ET",
            "scheduled_at_utc": "2026-11-16T00:30:00+00:00",
        },
        carousel_dims=(1080, 1350),
    )

    res = run_qa_scheduler(
        target_date="2026-11-15",
        projects_dir=proj_dir,
        channel_root=tmp_path,
        reports_root=rep_root,
        daily_dir=daily_dir,
        schedule_dir=sched_dir,
        now_utc=now,
        write_outputs=True,
    )

    assert res["schema_version"] == 2
    eco = res["ecosystem_slots"]
    assert eco["active"] is True
    assert eco["anchor_episode"]["project_id"] == "v8_ep08_capgras_imposter_delusion_r77"
    assets = eco["assets"]

    # 1. Community Quiz at D-Day 16:00 EST (-3.5h from 19:30 EST) -> ACTION_REQUIRED when receipt absent
    quiz = assets["yt_community_quiz"]
    assert "2026-11-15 16:00" in quiz["window"]["et"]
    assert quiz["status"] == "ACTION_REQUIRED"
    assert "main.py studio-quiz --project v8_ep08_capgras_imposter_delusion_r77" in quiz["detail"]

    # 2. YouTube Short at D-Day 19:30 EST
    assert "2026-11-15 19:30" in assets["youtube_short"]["window"]["et"]
    assert assets["youtube_short"]["status"] == "SCHEDULED"

    # 3. TikTok at D-Day 20:45 EST
    assert "2026-11-15 20:45" in assets["tiktok_video"]["window"]["et"]
    assert assets["tiktok_video"]["original_audio_only"] is True

    # 4. IG Clean Reel at D+1 13:30 EST (>= +18h after YT) + Trial Reels False (<1,000 followers)
    ig_reel = assets["instagram_reel"]
    assert "2026-11-16 13:30" in ig_reel["window"]["et"]
    assert ig_reel["trial_reels_eligible"] is False

    # 5. IG 4:5 (1080x1350) 6-Slide Carousel >= +24h after Reel (D+2 2026-11-17 13:30 EST)
    car = assets["instagram_carousel"]
    assert car["aspect_ratio_locked"] == "4:5 (1080x1350)"
    assert car["slide_count"] == 6
    assert car["min_gap_from_reel_hours"] == IG_CAROUSEL_MIN_GAP_FROM_REEL_HOURS
    assert "2026-11-17 13:30" in car["window"]["et"]

    # 6. Daily Zero-Bounce Studio Inbox Check + Quiz step in execution plan
    action_types = [s["action_type"] for s in res["execution_plan"]]
    assert "STUDIO_INBOX_CHECK" in action_types
    assert "YT_COMMUNITY_QUIZ" in action_types
    assert any("main.py studio-inbox --scan-only" in s["command"] for s in res["execution_plan"])

    # Dual daily & schedule outputs written
    assert (daily_dir / "2026-11-15_qa_schedule_plan.json").is_file()
    assert (daily_dir / "2026-11-15_qa_schedule_plan.md").is_file()
    assert (sched_dir / "2026-11-15_qa_schedule_plan.json").is_file()

    # Now add community_quiz_receipt.json -> status becomes SCHEDULED/DONE and YT_COMMUNITY_QUIZ step disappears
    _write_json(
        proj_dir / "v8_ep08_capgras_imposter_delusion_r77" / "06_publish" / "community_quiz_receipt.json",
        {"status": "scheduled", "scheduled_at_utc": "2026-11-15T21:00:00Z"},
    )
    res_done = evaluate_qa_schedule(
        projects_dir=proj_dir,
        channel_root=tmp_path,
        reports_root=rep_root,
        daily_dir=daily_dir,
        target_date="2026-11-15",
        now_utc=now,
    )
    assert res_done["ecosystem_slots"]["assets"]["yt_community_quiz"]["status"] == "SCHEDULED/DONE"
    assert "YT_COMMUNITY_QUIZ" not in [s["action_type"] for s in res_done["execution_plan"]]


def test_trial_reels_flag_and_carousel_weekly_cap_and_gap(tmp_path: Path) -> None:
    now = datetime(2026, 11, 15, 8, 0, tzinfo=timezone.utc)
    proj_dir = tmp_path / "projects"
    rep_root = tmp_path / "reports"
    daily_dir = rep_root / "daily"
    _seed_daily_report(daily_dir, rep_root, now, instagram_followers=1250)

    # Seed 3 carousels already published within the last 7 days (weekly cap = 3)
    for idx in (1, 2, 3):
        _seed_project(
            proj_dir,
            f"v8_ep0{idx}_old",
            carousel_receipt={
                "post_url": f"https://www.instagram.com/p/CAR{idx}/",
                "shortcode": f"CAR{idx}",
                "uploaded_at_utc": (now - timedelta(days=idx)).isoformat(),
            },
        )
    _seed_project(proj_dir, "v8_ep09_ready", duration_sec=72.0, carousel_dims=(1080, 1350))

    res = evaluate_qa_schedule(
        projects_dir=proj_dir,
        channel_root=tmp_path,
        reports_root=rep_root,
        daily_dir=daily_dir,
        target_date="2026-11-15",
        now_utc=now,
    )
    ig = res["platforms"]["instagram"]
    assert ig["trial_reels_eligible"] is True
    assert "Trial Reels (SS_PERFORMANCE)" in ig["reel_distribution_mode"]
    assert ig["carousels_last_7d"] == 3
    assert any(c["id"] == "IG-CAROUSEL-CAP" and c["status"] == "WARN" for c in ig["penalty_audit"])
    assert "PUBLISH_IG_CARDS" not in [s["action_type"] for s in res["execution_plan"]]

    # Carousel slot always >= 18h from Reel slot
    reel_dt = datetime.fromisoformat(ig["next_optimal_slot"]["iso_utc"])
    car_dt = datetime.fromisoformat(ig["next_carousel_slot"]["iso_utc"])
    assert abs((car_dt - reel_dt).total_seconds()) >= IG_CAROUSEL_MIN_GAP_FROM_REEL_HOURS * 3600


def test_anti_trap_six_guardrails_block_and_warn(tmp_path: Path) -> None:
    now = datetime(2026, 11, 15, 8, 0, tzinfo=timezone.utc)
    proj_dir = tmp_path / "projects"
    rep_root = tmp_path / "reports"
    daily_dir = rep_root / "daily"
    _seed_daily_report(daily_dir, rep_root, now, auto_dubbing_checked=True)

    p_dir = _seed_project(
        proj_dir,
        "v8_ep09_trapped",
        duration_sec=75.0,
        carousel_dims=(1080, 1440),  # 3:4 rejected by 4:5 lock!
        metadata_extra={"instagram_notes_enabled": True, "instagram_manychat_comment_dm": True},
        checklist_extra={"use_commercial_sound": True},
    )
    # Also drop an external .srt file in 06_publish/ (banned over 102pt ASS)
    (p_dir / "06_publish" / "captions.srt").write_text("1\n00:00:00,000 --> 00:00:01,000\nHi\n", encoding="utf-8")

    res = evaluate_qa_schedule(
        projects_dir=proj_dir,
        channel_root=tmp_path,
        reports_root=rep_root,
        daily_dir=daily_dir,
        target_date="2026-11-15",
        now_utc=now,
    )
    gr = res["guardrails"]
    assert gr["youtube_srt_cc_upload_banned"] is True
    assert gr["youtube_auto_dubbing_burned_ass_off"] is True
    assert gr["tiktok_commercial_sound_over_60s_banned"] is True
    assert gr["instagram_carousel_aspect_ratio_locked"] == "4:5 (1080x1350)"
    assert gr["instagram_notes_deprecated_excluded"] is True
    assert gr["on_hold_excluded_features"] == ["instagram_manychat_comment_dm", "instagram_story_highlights"]

    assert gr["passed"] is False
    assert gr["status"] == "HOLD"
    assert res["platforms"]["youtube"]["verdict"] == "HOLD"
    assert res["platforms"]["instagram"]["verdict"] == "HOLD"
    assert res["platforms"]["tiktok"]["verdict"] == "HOLD"

    # Excluded / deprecated features never appear in execution_plan
    plan_blob = json.dumps(res["execution_plan"]).lower()
    assert "manychat" not in plan_blob
    assert "story_highlights" not in plan_blob
    assert "instagram_notes" not in plan_blob


def _seed_full_diorama_qa(p_dir: Path, pid: str, *, r85_mode: bool, has_blender_clips: bool, with_ceo_pass: bool) -> None:
    _write_json(p_dir / "00_project_manifest.json", {"project_id": pid, "production_profile": "neuro_diorama"})
    _write_json(
        p_dir / "03_visuals" / "visual_plan.json",
        {"project_id": pid, "production_profile": "neuro_diorama", "style_profile": "expressive_25d_v8", "r85_mode": r85_mode},
    )
    _write_json(p_dir / "02_script" / "script.json", {"project_id": pid, "production_profile": "neuro_diorama", "r85_mode": r85_mode})
    _write_json(p_dir / "05_assembly" / "dynamic_episode_qa_report.json", {"passed": True})
    _write_json(p_dir / "05_assembly" / "posthoc_semantic_qa_report.json", {"passed": True})
    _write_json(p_dir / "05_assembly" / "posthoc_semantic_review.json", {"approved": True})
    _write_json(p_dir / "05_assembly" / "prosody_qa_report.json", {"passed": True})
    if has_blender_clips:
        b_dir = p_dir / "03_visuals" / "brain_simulator_clips"
        b_dir.mkdir(parents=True, exist_ok=True)
        (b_dir / "clip_01.mp4").write_bytes(b"blender")
    if with_ceo_pass:
        from pipeline.studio.qa_scheduler import record_ceo_verify_pass_receipt

        record_ceo_verify_pass_receipt(
            project_id=pid,
            message_timestamp="2026-11-18T02:05:00Z",
            message_text=f"[CEO_VERIFY_PASS] {pid}\nEvidence checked cleanly.",
            projects_dir=p_dir.parent,
        )


def test_r85_rebuild_and_ceo_verification_hold_lock_and_evidence_bundle(tmp_path: Path) -> None:
    import pytest
    from pipeline.studio.qa_scheduler import R85_REBUILD_HOLD_PREFIXES, record_ceo_verify_pass_receipt

    assert "v8_ep09_maguire_london_taxi_hippocampus_r82" in R85_REBUILD_HOLD_PREFIXES

    now = datetime(2026, 11, 18, 2, 0, tzinfo=timezone.utc)
    proj_dir = tmp_path / "projects"
    rep_root = tmp_path / "reports"
    daily_dir = rep_root / "daily"
    _seed_daily_report(daily_dir, rep_root, now)

    # 1. Pre-R85 R82/R84 v8_ep11 + explicit v8_ep09_maguire_london_taxi_hippocampus_r82 must stay HOLD with R85 issues
    ep11 = _seed_project(proj_dir, "v8_ep11_open_label_placebo_pain", duration_sec=80.0)
    _seed_full_diorama_qa(ep11, "v8_ep11_open_label_placebo_pain", r85_mode=False, has_blender_clips=True, with_ceo_pass=False)

    ep09_name = "v8_ep09_maguire_london_taxi_hippocampus_r82"
    ep09_r82 = _seed_project(proj_dir, ep09_name, duration_sec=80.0)
    _seed_full_diorama_qa(ep09_r82, ep09_name, r85_mode=False, has_blender_clips=True, with_ceo_pass=False)

    res_held = evaluate_qa_schedule(
        projects_dir=proj_dir,
        channel_root=tmp_path,
        reports_root=rep_root,
        daily_dir=daily_dir,
        target_date="2026-11-18",
        now_utc=now,
    )
    yt_held = res_held["platforms"]["youtube"]
    assert yt_held["verdict"] == "HOLD"
    assert yt_held["ready_candidates"] == []
    blocked_map = {b["project_id"]: b["reasons"] for b in yt_held["blocked_candidates"]}
    assert "r85_rebuild_required_r82_r84_held" in blocked_map["v8_ep11_open_label_placebo_pain"]
    assert "awaiting_r85_ceo_verification" in blocked_map["v8_ep11_open_label_placebo_pain"]
    assert "r85_rebuild_required_r82_r84_held" in blocked_map[ep09_name]
    assert "awaiting_r85_ceo_verification" in blocked_map[ep09_name]
    assert res_held["evidence_bundle"]["input_metrics_path"].endswith("2026-11-15_studio_metrics.json")

    # 2. Rebuild ep11 under R85 WITHOUT valid CEO message receipt (even a raw stub receipt must be rejected!)
    import shutil
    shutil.rmtree(ep11 / "03_visuals" / "brain_simulator_clips")
    _seed_full_diorama_qa(ep11, "v8_ep11_open_label_placebo_pain", r85_mode=True, has_blender_clips=False, with_ceo_pass=False)
    _write_json(ep11 / "05_assembly" / "ceo_verify_receipt.json", {"verdict": "PASS", "passed": True})
    res_no_ceo = evaluate_qa_schedule(
        projects_dir=proj_dir,
        channel_root=tmp_path,
        reports_root=rep_root,
        daily_dir=daily_dir,
        target_date="2026-11-18",
        now_utc=now,
    )
    assert res_no_ceo["platforms"]["youtube"]["verdict"] == "HOLD"
    blocked_map2 = {b["project_id"]: b["reasons"] for b in res_no_ceo["platforms"]["youtube"]["blocked_candidates"]}
    assert blocked_map2["v8_ep11_open_label_placebo_pain"] == ["awaiting_r85_ceo_verification"]

    # Recording a receipt without CEO sender/verbatim message must fail
    with pytest.raises(ValueError):
        record_ceo_verify_pass_receipt(
            project_id="v8_ep11_open_label_placebo_pain",
            message_timestamp="2026-11-18T02:05:00Z",
            message_text="looks good",
            projects_dir=proj_dir,
        )
    with pytest.raises(ValueError):
        record_ceo_verify_pass_receipt(
            project_id="v8_ep11_open_label_placebo_pain",
            message_timestamp="2026-11-18T02:05:00Z",
            message_text="[CEO_VERIFY_PASS] v8_ep11_open_label_placebo_pain",
            sender_conversation_id="not-ceo",
            projects_dir=proj_dir,
        )

    # 3. @QA_Scheduler records receipt from CEO send_message -> unlocks cleanly to GO with verbatim provenance
    ceo_msg = "[CEO_VERIFY_PASS] v8_ep11_open_label_placebo_pain\nRed-team check passed."
    receipt_path = record_ceo_verify_pass_receipt(
        project_id="v8_ep11_open_label_placebo_pain",
        message_timestamp="2026-11-18T02:06:00Z",
        message_text=ceo_msg,
        projects_dir=proj_dir,
    )
    saved = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert saved["message_timestamp"] == "2026-11-18T02:06:00Z"
    assert saved["message_text"] == ceo_msg
    assert saved["written_by"] == "@QA_Scheduler"

    res_go = evaluate_qa_schedule(
        projects_dir=proj_dir,
        channel_root=tmp_path,
        reports_root=rep_root,
        daily_dir=daily_dir,
        target_date="2026-11-18",
        now_utc=now,
    )
    yt_go = res_go["platforms"]["youtube"]
    from pipeline.studio.qa_scheduler import render_qa_schedule_markdown

    assert yt_go["verdict"] == "GO"
    assert [c["project_id"] for c in yt_go["ready_candidates"]] == ["v8_ep11_open_label_placebo_pain"]
    assert yt_go["ready_candidates"][0]["ceo_verified"] is True
    assert "ceo_verify" in yt_go["ready_candidates"][0]["qa_evidence_paths"]
    assert "realtime_60m_views" in res_go["evidence_bundle"]["excluded_unparsed_metrics"]
    md_out = render_qa_schedule_markdown(res_go)
    assert "60m=32" not in md_out
    assert "60m=" not in md_out
    assert "| Watch `" not in md_out

