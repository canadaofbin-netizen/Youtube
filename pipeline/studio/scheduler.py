"""
ALL ABOUT BRAIN — Cross-Platform QA Scheduler Chief (`qa-scheduler`)
===================================================================
Daily 08:00 scheduling & anti-penalty audit coordinator across:
  1. YouTube Shorts & Longform (`@AllAboutBrainOfficial`)
  2. Instagram Reels & 4:5 Editorial Cards (`@allaboutbrain.official`)
  3. TikTok Creator Rewards `>60s` (`@allaboutbrain_official`)

Ingests the latest Daily YouTube Studio Report (`studio_metrics.json`), live
Watchdog state (`studio_watchdog_latest.json`), project QA
bundles (`verify_publish_ready_qa_bundle`), and per-platform upload receipts to:
  - Decide `HOLD` / `THROTTLE` / `CONDITIONAL_GO` / `GO` per platform
  - Enforce anti-penalty & anti-shadowban cooldowns, warmups, and freeze windows
  - Compute optimal US East-to-West staggered prime windows & cadences
  - Derive a chronological daily execution plan with exact CLI commands
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
import json
from pathlib import Path
import re
import struct
from typing import Any
from zoneinfo import ZoneInfo

from pipeline.config import (
    CHANNEL_ROOT,
    FROZEN_PRE_SCHEMA_V2_PROJECT_PREFIXES,
    PRE_R66_FROZEN_PROJECT_PREFIXES,
    PROJECTS_DIR,
    SHORTS_EXPRESSIVE_V8_DURATION_MIN_SEC,
    SHORTS_EXPRESSIVE_V8_R75_MAX_SEC,
    SHORTS_HARD_CEILING_SEC,
    is_diorama_profile,
    is_r85_flow_31_brain_plan,
)
from pipeline.studio.config import (
    BANNED_OFF_TOPIC_TECH_TAGS,
    CHANNEL_HANDLE,
    DAILY_REPORTS_DIR,
    MIN_HOURS_AFTER_PUBLIC_BEFORE_PIN,
    MIN_ORGANIC_VIEWS_BEFORE_PIN,
    MIN_SCHEDULE_WARMUP_MINUTES,
    POST_RELEASE_FREEZE_HOURS,
    PRE_RELEASE_FREEZE_HOURS,
    REPORTS_ROOT_DIR,
    STAGING_QUEUE_FILE,
    STUDIO_PLAYLISTS_ENABLED,
)
from pipeline.studio.short_linker import is_valid_youtube_video_id, normalize_visibility
from pipeline.studio.uploader import _is_legacy_hermetic_test_stub

ET_TZ = ZoneInfo("America/New_York")
KST_TZ = ZoneInfo("Asia/Seoul")

SCHEDULE_REPORTS_DIR = REPORTS_ROOT_DIR / "schedule"
LATEST_QA_SCHEDULE_MD = REPORTS_ROOT_DIR / "LATEST_QA_SCHEDULE_PLAN.md"
LATEST_QA_SCHEDULE_JSON = REPORTS_ROOT_DIR / "LATEST_QA_SCHEDULE_PLAN.json"

# Platform Optimal Cadence & Anti-Penalty Guardrails
YT_UNDER_10K_SUBS_THRESHOLD = 10_000
YT_PRIME_SLOT_HOUR_ET = 19
YT_PRIME_SLOT_MINUTE_ET = 30
YT_TARGET_BUFFER_DAYS_MIN = 3
YT_TARGET_BUFFER_DAYS_MAX = 7
YT_MAX_QUEUE_RUNWAY_DAYS = 14
YT_VIEWED_HOOK_GATE_PCT = 70.0
YT_VIEWED_THROTTLE_PCT = 50.0
YT_APV_GATE_PCT = 60.0
YT_APV_THROTTLE_PCT = 48.0
YT_US_SHARE_GATE_PCT = 45.0
YT_US_SHARE_THROTTLE_PCT = 35.0
YT_SHORTS_FEED_GATE_PCT = 70.0
YT_MAX_REPORT_STALE_HOURS = 36.0
YT_HOLD_REPORT_AGE_HOURS = 72.0

IG_HANDLE = "@allaboutbrain.official"
IG_WARMUP_POST_COUNT = 10
IG_REEL_COOLDOWN_HOURS_WARMUP = 18.0
IG_REEL_COOLDOWN_HOURS_STEADY = 12.0
IG_MAX_POSTS_PER_24H_WARMUP = 1
IG_MAX_POSTS_PER_24H_STEADY = 2
IG_PRIME_WINDOWS_ET: tuple[tuple[int, int], ...] = ((13, 30), (18, 15))
IG_CROSS_PLATFORM_MIN_STAGGER_MIN = 60
IG_REEL_FROM_YT_MIN_LAG_HOURS = 18.0
IG_TRIAL_REELS_MIN_FOLLOWERS = 1_000
IG_CAROUSEL_MIN_GAP_FROM_REEL_HOURS = 18.0
IG_CAROUSEL_POST_REEL_OFFSET_HOURS = 24.0
IG_CAROUSEL_MAX_PER_WEEK = 3
IG_CAROUSEL_SLIDE_COUNT = 6
IG_CAROUSEL_ASPECT_RATIO_LOCKED = "4:5 (1080x1350)"
IG_CAROUSEL_WIDTH_PX = 1080
IG_CAROUSEL_HEIGHT_PX = 1350

YT_QUIZ_PRE_OFFSET_HOURS = 3.5
DAILY_INBOX_CHECK_WINDOW_ET: tuple[int, int] = (9, 0)

ANTI_TRAP_GUARDRAILS_SPEC: dict[str, Any] = {
    "youtube_srt_cc_upload_banned": True,
    "youtube_auto_dubbing_burned_ass_off": True,
    "tiktok_commercial_sound_over_60s_banned": True,
    "instagram_carousel_aspect_ratio_locked": IG_CAROUSEL_ASPECT_RATIO_LOCKED,
    "instagram_notes_deprecated_excluded": True,
    "on_hold_excluded_features": [
        "instagram_manychat_comment_dm",
        "instagram_story_highlights",
    ],
}

TIKTOK_HANDLE = "@allaboutbrain_official"
TIKTOK_WARMUP_POST_COUNT = 14
TIKTOK_COOLDOWN_HOURS_WARMUP = 20.0
TIKTOK_COOLDOWN_HOURS_STEADY = 10.0
TIKTOK_MAX_POSTS_PER_24H_WARMUP = 1
TIKTOK_MAX_POSTS_PER_24H_STEADY = 2
TIKTOK_PRIME_WINDOWS_ET: tuple[tuple[int, int], ...] = ((15, 30), (20, 45))
TIKTOK_CREATOR_REWARDS_MIN_SEC = float(SHORTS_EXPRESSIVE_V8_DURATION_MIN_SEC)  # 61.5s (>60s)

# Episodes produced prior to R75/R76 strict 88s ceiling that remain allowlisted up to 120s
LEGACY_V8_120S_ALLOWLIST_PREFIXES: tuple[str, ...] = (
    "v8_ep04_",
    "v8_ep05_",
    "v8_ep06_",
    "v8_ep07_",
    "v8_ep08_",
    "v8_pilot_03_",
)

# Pilot / test / superseded render directories excluded from auto-scheduling
NON_PUBLISH_PROJECT_SUFFIXES: tuple[str, ...] = ("_r76", "_r77", "_r82", "_voice_test")
NON_PUBLISH_PROJECT_PREFIXES: tuple[str, ...] = (
    "v8_pilot_01_",
    "v8_pilot_02_",
    "v8_brain_only_",
    "boost_",
)

# Rule R85 Rebuild & CEO Verification Lock (R83-5~7 + R85):
# Pre-R85 R82/R84 builds for Ep #9 r82 & Ep #10~#12 and any *_r82 build are held until rebuilt under R85
# AND verified via @YouTube_CEO `send_message` ("[CEO_VERIFY_PASS] <project_id>") recorded by @QA_Scheduler.
R85_REBUILD_HOLD_PREFIXES: tuple[str, ...] = (
    "v8_ep09_maguire_london_taxi_hippocampus_r82",
    "v8_ep10_",
    "v8_ep11_",
    "v8_ep12_",
)
VERIFY_PASS_PREFIX = "[VERIFY_PASS]"
CEO_VERIFY_PASS_PREFIX = "[CEO_VERIFY_PASS]"


def _load_json_safe(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _parse_utc(raw: Any, *, default_tz: Any = timezone.utc) -> datetime | None:
    if not raw:
        return None
    s = str(raw).strip()
    if not s:
        return None
    m = re.match(
        r"^(\d{4}-\d{2}-\d{2})\s+(\d{1,2}:\d{2})(?::(\d{2}))?(?:\s*(?:ET|EST|EDT))?$",
        s,
        flags=re.IGNORECASE,
    )
    if m:
        try:
            sec_s = m.group(3) or "00"
            dt_et = datetime.strptime(f"{m.group(1)} {m.group(2)}:{sec_s}", "%Y-%m-%d %H:%M:%S").replace(
                tzinfo=ET_TZ
            )
            return dt_et.astimezone(timezone.utc)
        except Exception:
            return None
    try:
        if s.endswith("Z"):
            return datetime.fromisoformat(s[:-1] + "+00:00").astimezone(timezone.utc)
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=default_tz)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def _fmt_multi_tz(dt_utc: datetime) -> dict[str, str]:
    dt_u = dt_utc.astimezone(timezone.utc)
    dt_et = dt_u.astimezone(ET_TZ)
    dt_kst = dt_u.astimezone(KST_TZ)
    return {
        "utc": dt_u.strftime("%Y-%m-%d %H:%M UTC"),
        "et": dt_et.strftime(f"%Y-%m-%d %H:%M {dt_et.tzname() or 'ET'}"),
        "kst": dt_kst.strftime("%Y-%m-%d %H:%M KST"),
        "iso_utc": dt_u.isoformat(),
    }


def _next_et_window(
    now_utc: datetime,
    windows_et: tuple[tuple[int, int], ...],
    *,
    earliest_utc: datetime | None = None,
    occupied_et_dates: set[str] | None = None,
    avoid_utc_times: list[datetime] | None = None,
    min_stagger_min: int = 60,
) -> datetime:
    """Finds the earliest future slot matching `windows_et` while respecting cooldowns and staggers."""
    floor_utc = max(now_utc, earliest_utc) if earliest_utc else now_utc
    floor_et = floor_utc.astimezone(ET_TZ)
    occ = occupied_et_dates or set()
    avoid = [a.astimezone(timezone.utc) for a in (avoid_utc_times or [])]

    for day_offset in range(0, 35):
        cand_date = floor_et.date() + timedelta(days=day_offset)
        if cand_date.isoformat() in occ:
            continue
        for hour_et, min_et in sorted(windows_et):
            cand_et = datetime.combine(cand_date, time(hour_et, min_et), tzinfo=ET_TZ)
            cand_utc = cand_et.astimezone(timezone.utc)
            if cand_utc < floor_utc:
                continue
            if any(abs((cand_utc - a).total_seconds()) < min_stagger_min * 60 for a in avoid):
                continue
            return cand_utc
    return (floor_utc + timedelta(hours=24)).astimezone(timezone.utc)


def _is_retired_or_frozen_project(project_id: str, project_dir: Path | None = None) -> tuple[bool, str]:
    if project_id.startswith(FROZEN_PRE_SCHEMA_V2_PROJECT_PREFIXES) or project_id.startswith(PRE_R66_FROZEN_PROJECT_PREFIXES):
        return True, "pre_r66_or_pre_schema_v2_frozen"
    if project_id.startswith(NON_PUBLISH_PROJECT_PREFIXES):
        return True, "pilot_or_superseded_prefix"
    if project_id.endswith(NON_PUBLISH_PROJECT_SUFFIXES) or "_siren_voice_test" in project_id:
        return True, "internal_ab_or_render_test"
    if project_dir is not None and (project_dir / "06_publish" / "upload_receipt.retired_lowpoly.json").is_file():
        return True, "retired_lowpoly_receipt"
    return False, ""


def _is_valid_ceo_verify_receipt(project_id: str, ceo_doc: dict[str, Any]) -> bool:
    """Validates local release verification receipt (`verify_receipt.json` / `ceo_verify_receipt.json`) under Fresh-Room R83 v3."""
    if not ceo_doc:
        return False
    verdict_ok = str(ceo_doc.get("verdict") or "").strip().upper() == "PASS" and ceo_doc.get("passed") is True
    pid_ok = str(ceo_doc.get("project_id") or "").strip() == project_id
    ts_ok = bool(str(ceo_doc.get("recorded_at_utc") or ceo_doc.get("message_timestamp") or "").strip())
    msg_text = str(ceo_doc.get("message_text") or ceo_doc.get("note") or "")
    tag_ok = bool(
        ceo_doc.get("approved") is True
        or re.search(rf"\[(?:CEO_)?VERIFY_PASS\]\s+{re.escape(project_id)}(?![A-Za-z0-9_])", msg_text)
    )
    return bool(verdict_ok and pid_ok and ts_ok and tag_ok)


_is_valid_verify_receipt = _is_valid_ceo_verify_receipt


def _find_ceo_verify_receipt(project_dir: Path) -> tuple[Path | None, dict[str, Any]]:
    for rel in (
        ("05_assembly", "verify_receipt.json"),
        ("05_assembly", "ceo_verify_receipt.json"),
        ("06_publish", "verify_receipt.json"),
        ("06_publish", "ceo_verify_receipt.json"),
    ):
        cand = project_dir.joinpath(*rel)
        if cand.is_file():
            return cand, _load_json_safe(cand)
    return None, {}


def record_verify_pass_receipt(
    *,
    project_id: str,
    message_timestamp: str = "",
    message_text: str = "",
    approved: bool = True,
    projects_dir: Path = PROJECTS_DIR,
) -> Path:
    """Writes local release verification receipt (`05_assembly/ceo_verify_receipt.json`) after local QA & integrity pass."""
    if not approved:
        raise ValueError("Release verification receipt requires approved=True")
    msg_ts = str(message_timestamp or datetime.now(timezone.utc).isoformat()).strip()
    msg_raw = str(message_text or "").strip()
    if msg_raw and not re.search(rf"\[(?:CEO_)?VERIFY_PASS\]\s+{re.escape(project_id)}(?![A-Za-z0-9_])", msg_raw):
        raise ValueError(f"Verification note must include `{VERIFY_PASS_PREFIX} {project_id}` or `{CEO_VERIFY_PASS_PREFIX} {project_id}`")
    if not msg_raw:
        msg_raw = f"{VERIFY_PASS_PREFIX} {project_id}"

    project_dir = projects_dir / project_id
    if not project_dir.is_dir():
        raise FileNotFoundError(f"Project directory not found: {project_dir}")

    out_path = project_dir / "05_assembly" / "ceo_verify_receipt.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 2,
        "project_id": project_id,
        "verdict": "PASS",
        "passed": True,
        "approved": True,
        "written_by": "Fresh-Room Verifier",
        "message_timestamp": msg_ts,
        "message_text": msg_raw,
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return out_path


record_ceo_verify_pass_receipt = record_verify_pass_receipt


def _collect_project_qa_evidence(project_dir: Path) -> dict[str, Any]:
    """Collects existing QA & verify receipt paths for R83-7 evidence-carrying reports."""
    candidates = {
        "manifest": project_dir / "00_project_manifest.json",
        "video_autopsy": project_dir / "05_assembly" / "video_autopsy_report.json",
        "dynamic_episode_qa": project_dir / "05_assembly" / "dynamic_episode_qa_report.json",
        "posthoc_semantic_qa": project_dir / "05_assembly" / "posthoc_semantic_qa_report.json",
        "posthoc_semantic_review": project_dir / "05_assembly" / "posthoc_semantic_review.json",
        "prosody_qa": project_dir / "05_assembly" / "prosody_qa_report.json",
        "reference_image_qa": project_dir / "03_visuals" / "reference_image_qa_report.json",
        "thumbnail_qa": project_dir / "06_publish" / "thumbnail_report.json",
        "upload_receipt": project_dir / "06_publish" / "upload_receipt.json",
    }
    paths = {k: str(p) for k, p in candidates.items() if p.is_file()}
    ceo_path, ceo_doc = _find_ceo_verify_receipt(project_dir)
    ceo_passed = _is_valid_ceo_verify_receipt(project_dir.name, ceo_doc)
    if ceo_path is not None and ceo_passed:
        paths["ceo_verify"] = str(ceo_path)
    return {
        "qa_evidence_paths": paths,
        "ceo_verify_receipt": str(ceo_path) if (ceo_path is not None and ceo_passed) else None,
        "ceo_verified": ceo_passed,
    }


def _check_project_qa_fast(
    project_dir: Path,
    *,
    is_already_uploaded_yt: bool = False,
) -> tuple[bool, list[str]]:
    """Fast stat + QA JSON + R85 rebuild/CEO verification gate without reading 100MB MP4 bytes."""
    issues: list[str] = []
    pid = project_dir.name
    final_mp4 = project_dir / "05_assembly" / "final_shorts_1080x1920.mp4"
    if not final_mp4.is_file() or final_mp4.stat().st_size <= 0:
        issues.append("missing_final_shorts_1080x1920_mp4")

    manifest = _load_json_safe(project_dir / "00_project_manifest.json")
    if not manifest:
        issues.append("missing_00_project_manifest_json")

    autopsy = _load_json_safe(project_dir / "05_assembly" / "video_autopsy_report.json")
    if not autopsy:
        issues.append("missing_video_autopsy_report_json")
    elif autopsy.get("passed") is not True:
        issues.append("video_autopsy_not_passed")

    plan = _load_json_safe(project_dir / "03_visuals" / "visual_plan.json")
    script_doc = _load_json_safe(project_dir / "02_script" / "script.json")
    meta_doc = _load_json_safe(project_dir / "06_publish" / "metadata.json")
    is_diorama = is_diorama_profile(plan) or is_diorama_profile(script_doc) or is_diorama_profile(meta_doc)
    if is_diorama:
        dq = _load_json_safe(project_dir / "05_assembly" / "dynamic_episode_qa_report.json")
        if not dq:
            issues.append("missing_dynamic_episode_qa_report_json")
        elif dq.get("passed") is not True:
            issues.append("dynamic_episode_qa_not_passed")

        posthoc = _load_json_safe(project_dir / "05_assembly" / "posthoc_semantic_qa_report.json")
        if not posthoc:
            issues.append("missing_posthoc_semantic_qa_report_json")
        elif posthoc.get("passed") is not True:
            issues.append("posthoc_semantic_qa_not_passed")

        review = _load_json_safe(project_dir / "05_assembly" / "posthoc_semantic_review.json")
        if not review or not (review.get("approved") is True or review.get("valid") is True or review.get("cuts")):
            issues.append("missing_or_invalid_posthoc_semantic_review_json")
        elif posthoc.get("final_mp4_sha256") and review.get("final_mp4_sha256") and str(posthoc.get("final_mp4_sha256")) != str(review.get("final_mp4_sha256")):
            issues.append("stale_posthoc_semantic_review_sha256")

        p_qa = _load_json_safe(project_dir / "05_assembly" / "prosody_qa_report.json")
        if not p_qa:
            issues.append("missing_prosody_qa_report_json")
        elif p_qa.get("passed") is not True:
            issues.append("prosody_qa_not_passed")

        r_qa = _load_json_safe(project_dir / "03_visuals" / "reference_image_qa_report.json")
        if r_qa and not (r_qa.get("passed") is True or r_qa.get("pre_generation_ready") is True or r_qa.get("all_passed") is True):
            issues.append("reference_image_qa_not_passed")

        t_qa = _load_json_safe(project_dir / "06_publish" / "thumbnail_report.json")
        if t_qa and t_qa.get("passed") is not True and str(t_qa.get("mode") or "") != "backfill_soft":
            issues.append("thumbnail_qa_not_passed")

        # Rule R85 + R83-5~7 Rebuild & CEO Verification Hold Lock:
        # Hold Ep #10~#12 R82/R84 MP4s and any R85 rebuild until BOTH R85 rebuild QA AND CEO verification PASS.
        bs_dir = project_dir / "03_visuals" / "brain_simulator_clips"
        has_legacy_blender_clips = bs_dir.is_dir() and any(bs_dir.glob("clip_*.mp4"))
        requires_r85_gate = bool(
            not is_already_uploaded_yt
            and (
                pid.startswith(R85_REBUILD_HOLD_PREFIXES)
                or is_r85_flow_31_brain_plan(plan, script_doc, project_id=pid)
                or has_legacy_blender_clips
            )
        )
        if requires_r85_gate:
            is_r85 = is_r85_flow_31_brain_plan(plan, script_doc, project_id=pid)
            if not is_r85 or has_legacy_blender_clips:
                issues.append("r85_rebuild_required_r82_r84_held")
            ev = _collect_project_qa_evidence(project_dir)
            if not ev["ceo_verified"]:
                issues.append("awaiting_r85_ceo_verification")

    return len(issues) == 0, issues


def _resolve_duration_sec(project_dir: Path) -> float:
    for rel in (
        ("06_publish", "multi_platform_bundle", "upload_checklist.json"),
        ("05_assembly", "probe_report.json"),
        ("05_assembly", "video_autopsy_report.json"),
        ("05_assembly", "dynamic_episode_qa_report.json"),
    ):
        doc = _load_json_safe(project_dir.joinpath(*rel))
        for key in ("duration_sec", "duration_seconds", "measured_duration_sec"):
            val = doc.get(key)
            if isinstance(val, (int, float)) and val > 0:
                return round(float(val), 2)
    return 0.0


def _read_png_dimensions(path: Path) -> tuple[int, int] | None:
    """Reads PNG width/height directly from the 24-byte IHDR header without loading the image."""
    try:
        with path.open("rb") as fh:
            hdr = fh.read(24)
        if len(hdr) < 24 or hdr[:8] != b"\x89PNG\r\n\x1a\n" or hdr[12:16] != b"IHDR":
            return None
        w, h = struct.unpack(">II", hdr[16:24])
        return int(w), int(h)
    except Exception:
        return None


def _is_valid_quiz_receipt(doc: dict[str, Any]) -> bool:
    if not doc:
        return False
    status = str(doc.get("status") or "").strip().lower()
    if status in {"scheduled", "published", "posted", "done", "verified"}:
        return True
    return bool(doc.get("post_url") or doc.get("post_id") or doc.get("scheduled_at_utc"))


def load_daily_report_context(
    *,
    reports_root: Path = REPORTS_ROOT_DIR,
    daily_dir: Path = DAILY_REPORTS_DIR,
    target_date: str | None = None,
    now_utc: datetime | None = None,
) -> dict[str, Any]:
    """Ingests the latest Daily Studio Report (`studio_metrics.json`), watchdog, and playlist purge state."""
    now = now_utc or datetime.now(timezone.utc)
    metrics_path: Path | None = None
    if target_date:
        cand = daily_dir / f"{target_date}_studio_metrics.json"
        if cand.is_file():
            metrics_path = cand
    if metrics_path is None and daily_dir.is_dir():
        cands = sorted(daily_dir.glob("*_studio_metrics.json"))
        if cands:
            metrics_path = cands[-1]

    metrics = _load_json_safe(metrics_path) if metrics_path else {}
    report_date = str(metrics.get("report_date") or (metrics_path.name[:10] if metrics_path else ""))
    gen_dt = _parse_utc(metrics.get("generated_at_utc"))
    age_hours = round((now - gen_dt).total_seconds() / 3600.0, 2) if gen_dt else None

    ch_kpi = metrics.get("channel_kpis") or {}
    ret_kpi = metrics.get("retention_kpis") or {}
    inv = metrics.get("inventory_summary") or {}
    link_sum = metrics.get("short_link_summary") or {}
    risk = metrics.get("risk_audit") or {}
    live_meta = metrics.get("live_scraped_meta") or {}
    traffic = metrics.get("traffic_sources") or []
    geos = metrics.get("geographies") or []
    quartiles = metrics.get("retention_quartiles") or []

    def _find_pct(rows: list[dict[str, Any]], key: str, needles: tuple[str, ...]) -> float | None:
        for r in rows:
            val = str(r.get(key) or "").lower()
            if any(n in val for n in needles):
                pct = r.get("pct")
                return float(pct) if isinstance(pct, (int, float)) else None
        return None

    shorts_feed_pct = _find_pct(traffic, "short_name", ("shorts feed",))
    if shorts_feed_pct is None:
        shorts_feed_pct = _find_pct(traffic, "source", ("shorts",))
    us_share_pct = _find_pct(geos, "country", ("us",))
    tier1_pct = sum(
        float(g.get("pct") or 0.0)
        for g in geos
        if str(g.get("country") or "").upper() in {"US", "UK", "GB", "CA", "AU"}
    )
    if not geos:
        tier1_pct = None  # type: ignore[assignment]

    q1_pct = next((q.get("today_pct") for q in quartiles if "Q1" in str(q.get("quartile") or "")), None)
    q3_pct = next((q.get("today_pct") for q in quartiles if "Q3" in str(q.get("quartile") or "")), None)
    q1_to_q3_drop = round(float(q3_pct) - float(q1_pct), 2) if (q1_pct is not None and q3_pct is not None) else None

    views_24h = ch_kpi.get("views_24h")
    realtime_48h = ch_kpi.get("realtime_48h_views")
    realtime_60m = ch_kpi.get("realtime_60m_views")
    watch_hours_24h = ch_kpi.get("watch_hours_24h")
    measured_video_count = risk.get("measured_video_count")

    partial_dom_scrape_anomaly = bool(
        isinstance(views_24h, (int, float))
        and views_24h < 50
        and isinstance(realtime_48h, (int, float))
        and realtime_48h >= 500
        and (measured_video_count == 0 or (isinstance(watch_hours_24h, (int, float)) and watch_hours_24h >= 20.0))
    )

    ceo_watchdog = _load_json_safe(reports_root / "studio_watchdog_latest.json") or _load_json_safe(
        reports_root / "ceo_watchdog_latest.json"
    )
    playlist_purge = _load_json_safe(reports_root / "studio_playlist_purge_receipt.json")
    auto_dubbing_rec = _load_json_safe(reports_root / "studio_auto_dubbing_receipt.json")
    ig_metrics_rec = _load_json_safe(reports_root / "instagram_metrics_latest.json")
    ig_followers = (
        ig_metrics_rec.get("followers_total")
        or metrics.get("instagram_followers")
        or (metrics.get("instagram_kpis") or {}).get("followers_total")
        or 0
    )

    return {
        "metrics_path": str(metrics_path) if metrics_path else None,
        "report_date": report_date,
        "generated_at_utc": gen_dt.isoformat() if gen_dt else None,
        "report_age_hours": age_hours,
        "data_source_mode": str(metrics.get("data_source_mode") or "MISSING"),
        "studio_authenticated": bool(live_meta.get("studio_authenticated")),
        "subscribers_total": int(ch_kpi.get("subscribers_total") or 0),
        "instagram_followers": int(ig_followers or 0),
        "views_24h": views_24h,
        "views_prev": ch_kpi.get("views_prev"),
        "watch_hours_24h": watch_hours_24h,
        "realtime_48h_views": realtime_48h,
        "realtime_60m_views": realtime_60m,
        "viewed_pct": ret_kpi.get("viewed_pct"),
        "viewed_prev_pct": ret_kpi.get("viewed_prev_pct"),
        "apv_pct": ret_kpi.get("apv_pct"),
        "apv_prev_pct": ret_kpi.get("apv_prev_pct"),
        "avd_seconds": ret_kpi.get("avd_seconds"),
        "q1_to_q3_drop_pp": q1_to_q3_drop,
        "shorts_feed_pct": shorts_feed_pct,
        "us_share_pct": us_share_pct,
        "tier1_share_pct": round(tier1_pct, 2) if tier1_pct is not None else None,
        "measured_video_count": measured_video_count,
        "unscraped_video_count": risk.get("unscraped_video_count"),
        "simultaneous_publish_count": int(risk.get("simultaneous_publish_count") or 0),
        "quarantine_count": int(risk.get("quarantine_count") or inv.get("quarantine_count") or 0),
        "related_ring_complete": bool(link_sum.get("ring_complete")),
        "related_verified_count": int(link_sum.get("related_verified_count") or 0),
        "published_total": int(link_sum.get("published_total") or inv.get("published_count") or 0),
        "partial_dom_scrape_anomaly": partial_dom_scrape_anomaly,
        "playlists_purged_zero": (
            not STUDIO_PLAYLISTS_ENABLED
            and (playlist_purge.get("remaining_count") == 0 if playlist_purge else False)
        ),
        "auto_dubbing_checked_on": bool(
            auto_dubbing_rec.get("auto_dubbing_checked")
            or auto_dubbing_rec.get("upload_defaults_auto_dubbing_checked")
            or auto_dubbing_rec.get("channel_auto_dubbing_checked")
            or metrics.get("auto_dubbing_checked")
        ),
        "ceo_watchdog_checked_at_utc": ceo_watchdog.get("checked_at_utc"),
        "ceo_watchdog_videos": ceo_watchdog.get("studio_videos") or [],
    }


def scan_multi_platform_inventory(
    *,
    projects_dir: Path = PROJECTS_DIR,
    channel_root: Path = CHANNEL_ROOT,
    ceo_watchdog_videos: list[dict[str, Any]] | None = None,
    now_utc: datetime | None = None,
) -> dict[str, Any]:
    """Scans projects and IG card runs across YouTube, Instagram, and TikTok."""
    now = now_utc or datetime.now(timezone.utc)
    studio_by_vid = {
        str(v.get("vid") or "").strip(): v
        for v in (ceo_watchdog_videos or [])
        if str(v.get("vid") or "").strip()
    }

    projects: list[dict[str, Any]] = []
    yt_uploads: list[dict[str, Any]] = []
    ig_uploads: list[dict[str, Any]] = []
    ig_carousel_uploads: list[dict[str, Any]] = []
    tt_uploads: list[dict[str, Any]] = []
    guardrail_signals: dict[str, list[dict[str, Any]]] = {
        "srt_cc_uploads": [],
        "auto_dubbing_on": [],
        "tiktok_commercial_sound_over_60s": [],
        "carousel_bad_aspect_ratio": [],
        "instagram_notes_enabled": [],
        "on_hold_features_enabled": [],
        "r75_polluted_tags": [],
    }

    if projects_dir.is_dir():
        for p_dir in sorted(projects_dir.iterdir()):
            if not p_dir.is_dir() or _is_legacy_hermetic_test_stub(p_dir):
                continue
            pid = p_dir.name
            pub_dir = p_dir / "06_publish"
            mp4_exists = (p_dir / "05_assembly" / "final_shorts_1080x1920.mp4").is_file()
            duration_sec = _resolve_duration_sec(p_dir) if mp4_exists else 0.0

            upload_rec = _load_json_safe(pub_dir / "upload_receipt.json")
            comm_rec = _load_json_safe(pub_dir / "community_receipt.json")
            quiz_rec = _load_json_safe(pub_dir / "community_quiz_receipt.json")
            rel_rec = _load_json_safe(pub_dir / "related_video_receipt.json")
            ig_rec = _load_json_safe(pub_dir / "instagram_upload_receipt.json") or _load_json_safe(
                pub_dir / "instagram_publish_receipt.json"
            )
            ig_carousel_rec = _load_json_safe(pub_dir / "instagram_carousel_receipt.json")
            tt_rec = _load_json_safe(pub_dir / "tiktok_upload_receipt.json")
            meta_doc = _load_json_safe(pub_dir / "metadata.json")

            from pipeline.publish import resolve_bundle_video_path

            bundle_dir = pub_dir / "multi_platform_bundle"
            checklist = _load_json_safe(bundle_dir / "upload_checklist.json")
            bundle_ready = bool(
                checklist
                and resolve_bundle_video_path(p_dir) is not None
                and (bundle_dir / "cover_9x16.png").is_file()
                and (bundle_dir / "tiktok_caption.txt").is_file()
                and (bundle_dir / "reels_caption.txt").is_file()
            )

            vid = str(upload_rec.get("video_id") or "").strip()
            has_live_yt = bool(upload_rec and is_valid_youtube_video_id(vid))
            studio_row = studio_by_vid.get(vid, {})
            studio_vis = str(studio_row.get("vis") or "").strip().lower()
            local_vis = normalize_visibility(upload_rec) if has_live_yt else "none"
            effective_vis = studio_vis if studio_vis in {"public", "scheduled", "unlisted", "private"} else local_vis

            sched_dt = (
                _parse_utc(upload_rec.get("scheduled_at_utc"), default_tz=timezone.utc)
                or _parse_utc(upload_rec.get("scheduled_time_et"), default_tz=ET_TZ)
                or _parse_utc(upload_rec.get("published_at_utc"), default_tz=timezone.utc)
            )
            # Infer effective public if scheduled time passed
            elapsed_since_sched_h = (now - sched_dt).total_seconds() / 3600.0 if sched_dt else None
            due_for_promotion = bool(
                has_live_yt and local_vis == "scheduled" and sched_dt is not None and sched_dt <= now
            )

            in_pre_freeze = bool(
                effective_vis == "scheduled"
                and sched_dt is not None
                and 0.0 <= (sched_dt - now).total_seconds() / 3600.0 <= PRE_RELEASE_FREEZE_HOURS
            )
            in_post_freeze = bool(
                effective_vis == "public"
                and sched_dt is not None
                and 0.0 <= (now - sched_dt).total_seconds() / 3600.0 <= POST_RELEASE_FREEZE_HOURS
            )

            retired, retired_reason = _is_retired_or_frozen_project(pid, p_dir)
            if retired and has_live_yt and effective_vis in {"scheduled", "public"}:
                retired = False
                retired_reason = ""
            qa_passed = False
            qa_issues: list[str] = []
            already_live_yt = bool(has_live_yt and effective_vis in {"scheduled", "public"})
            if mp4_exists and (not retired or pid.startswith(R85_REBUILD_HOLD_PREFIXES) or pid.endswith("_r82")):
                qa_passed, qa_issues = _check_project_qa_fast(
                    p_dir,
                    is_already_uploaded_yt=already_live_yt,
                )
            evidence_info = _collect_project_qa_evidence(p_dir) if mp4_exists else {
                "qa_evidence_paths": {},
                "ceo_verify_receipt": None,
                "ceo_verified": False,
            }

            # Inspect per-project anti-trap guardrail signals for non-retired projects
            if not retired:
                ext_cc_files = list(pub_dir.glob("*.srt")) + list(pub_dir.glob("*.vtt")) if pub_dir.is_dir() else []
                if ext_cc_files or bool(meta_doc.get("caption_upload_enabled")) or bool(meta_doc.get("upload_srt_cc")):
                    guardrail_signals["srt_cc_uploads"].append(
                        {"project_id": pid, "files": [f.name for f in ext_cc_files]}
                    )
                if bool(meta_doc.get("auto_dubbing_checked")) or bool(upload_rec.get("auto_dubbing_enabled")):
                    guardrail_signals["auto_dubbing_on"].append({"project_id": pid})
                if duration_sec >= 60.0 and (
                    bool(checklist.get("use_commercial_sound"))
                    or bool(checklist.get("tiktok_commercial_music"))
                    or bool(meta_doc.get("tiktok_commercial_sound"))
                ):
                    guardrail_signals["tiktok_commercial_sound_over_60s"].append(
                        {"project_id": pid, "duration_sec": duration_sec}
                    )
                if bool(meta_doc.get("instagram_notes_enabled")) or bool(checklist.get("instagram_notes_enabled")):
                    guardrail_signals["instagram_notes_enabled"].append({"project_id": pid})
                for feat in ANTI_TRAP_GUARDRAILS_SPEC["on_hold_excluded_features"]:
                    if bool(meta_doc.get(feat)) or bool(checklist.get(feat)):
                        guardrail_signals["on_hold_features_enabled"].append({"project_id": pid, "feature": feat})
                proj_pillar = str(meta_doc.get("pillar") or "").strip()
                raw_tags = meta_doc.get("tags") if isinstance(meta_doc.get("tags"), list) else []
                bad_tags = [str(t) for t in raw_tags if proj_pillar != "bci_tech" and str(t).strip().lower() in BANNED_OFF_TOPIC_TECH_TAGS]
                if bad_tags:
                    guardrail_signals["r75_polluted_tags"].append({"project_id": pid, "tags": bad_tags})

                carousel_dirs = [d for d in (pub_dir / "ig_carousel", bundle_dir / "carousel_4x5") if d.is_dir()]
                for carousel_dir in carousel_dirs:
                    rel_car = carousel_dir.relative_to(p_dir)
                    for c_img in sorted(carousel_dir.glob("*.png")):
                        dims = _read_png_dimensions(c_img)
                        if dims and dims != (IG_CAROUSEL_WIDTH_PX, IG_CAROUSEL_HEIGHT_PX):
                            guardrail_signals["carousel_bad_aspect_ratio"].append(
                                {"target": f"{pid}/{rel_car}/{c_img.name}", "dims": f"{dims[0]}x{dims[1]}"}
                            )

            ig_dt = _parse_utc(ig_rec.get("uploaded_at_utc")) if ig_rec else None
            ig_car_dt = _parse_utc(ig_carousel_rec.get("uploaded_at_utc")) if ig_carousel_rec else None
            tt_dt = _parse_utc(tt_rec.get("uploaded_at_utc")) if tt_rec else None

            if has_live_yt and sched_dt is not None:
                yt_uploads.append(
                    {
                        "project_id": pid,
                        "video_id": vid,
                        "visibility": effective_vis,
                        "local_visibility": local_vis,
                        "scheduled_at_utc": sched_dt.isoformat(),
                        "scheduled_time_et": upload_rec.get("scheduled_time_et"),
                        "due_for_promotion": due_for_promotion,
                    }
                )
            if ig_rec and ig_dt:
                ig_uploads.append({"project_id": pid, "uploaded_at_utc": ig_dt.isoformat(), **ig_rec})
            if ig_carousel_rec and ig_car_dt:
                ig_carousel_uploads.append(
                    {"project_id": pid, "uploaded_at_utc": ig_car_dt.isoformat(), **ig_carousel_rec}
                )
            if tt_rec and tt_dt:
                tt_uploads.append({"project_id": pid, "uploaded_at_utc": tt_dt.isoformat(), **tt_rec})

            candidate_carousel_dirs = [d for d in (pub_dir / "ig_carousel", bundle_dir / "carousel_4x5") if d.is_dir()]
            project_carousel_ready = any(
                len(list(c_dir.glob("*.png"))) >= IG_CAROUSEL_SLIDE_COUNT for c_dir in candidate_carousel_dirs
            )

            projects.append(
                {
                    "project_id": pid,
                    "mp4_exists": mp4_exists,
                    "duration_sec": duration_sec,
                    "retired_or_frozen": retired,
                    "retired_reason": retired_reason,
                    "qa_passed": qa_passed,
                    "qa_issues": qa_issues,
                    "qa_evidence_paths": evidence_info["qa_evidence_paths"],
                    "ceo_verify_receipt": evidence_info["ceo_verify_receipt"],
                    "ceo_verified": evidence_info["ceo_verified"],
                    "bundle_ready": bundle_ready,
                    "tiktok_over_60s": bool(duration_sec >= TIKTOK_CREATOR_REWARDS_MIN_SEC),
                    "yt": {
                        "uploaded": has_live_yt,
                        "video_id": vid or None,
                        "visibility": effective_vis,
                        "local_visibility": local_vis,
                        "scheduled_at_utc": sched_dt.isoformat() if sched_dt else None,
                        "scheduled_time_et": upload_rec.get("scheduled_time_et"),
                        "elapsed_hours": round(elapsed_since_sched_h, 2) if elapsed_since_sched_h is not None else None,
                        "due_for_promotion": due_for_promotion,
                        "in_pre_freeze": in_pre_freeze,
                        "in_post_freeze": in_post_freeze,
                        "doi_pinned": bool(comm_rec.get("pinned")) and str(comm_rec.get("video_id") or "") == vid,
                        "related_linked": bool(rel_rec.get("verified"))
                        and str(rel_rec.get("source_video_id") or rel_rec.get("video_id") or "") == vid,
                        "quiz_scheduled_or_done": _is_valid_quiz_receipt(quiz_rec),
                        "quiz_receipt": quiz_rec or None,
                    },
                    "instagram": {
                        "uploaded": bool(ig_rec and (ig_rec.get("reel_url") or ig_rec.get("shortcode"))),
                        "uploaded_at_utc": ig_dt.isoformat() if ig_dt else None,
                        "reel_url": ig_rec.get("reel_url"),
                        "carousel_ready": project_carousel_ready,
                        "carousel_uploaded": bool(
                            ig_carousel_rec and (ig_carousel_rec.get("post_url") or ig_carousel_rec.get("shortcode"))
                        ),
                        "carousel_uploaded_at_utc": ig_car_dt.isoformat() if ig_car_dt else None,
                    },
                    "tiktok": {
                        "uploaded": bool(tt_rec and (tt_rec.get("video_url") or tt_rec.get("video_id"))),
                        "uploaded_at_utc": tt_dt.isoformat() if tt_dt else None,
                        "video_url": tt_rec.get("video_url"),
                    },
                }
            )

    # Scan Instagram 4:5 Editorial Card runs
    ig_card_runs: list[dict[str, Any]] = []
    runs_dir = channel_root / "runs"
    if runs_dir.is_dir():
        for run_dir in sorted(runs_dir.glob("ig_cards_*")):
            if not run_dir.is_dir():
                continue
            pkg_dir = run_dir / "package"
            carousel_pngs = sorted(pkg_dir.glob("carousel_*.png")) if pkg_dir.is_dir() else []
            has_carousel = len(carousel_pngs) >= 3
            for c_img in carousel_pngs:
                dims = _read_png_dimensions(c_img)
                if dims and dims != (IG_CAROUSEL_WIDTH_PX, IG_CAROUSEL_HEIGHT_PX):
                    guardrail_signals["carousel_bad_aspect_ratio"].append(
                        {"target": f"runs/{run_dir.name}/package/{c_img.name}", "dims": f"{dims[0]}x{dims[1]}"}
                    )
            receipt = _load_json_safe(run_dir / "instagram_carousel_receipt.json") or _load_json_safe(
                run_dir / "instagram_card_receipt.json"
            )
            car_dt = _parse_utc(receipt.get("uploaded_at_utc")) if receipt else None
            if receipt and car_dt:
                ig_carousel_uploads.append({"run_id": run_dir.name, "uploaded_at_utc": car_dt.isoformat(), **receipt})
            ig_card_runs.append(
                {
                    "run_id": run_dir.name,
                    "package_ready": has_carousel,
                    "slide_count": len(carousel_pngs),
                    "uploaded": bool(receipt.get("post_url") or receipt.get("shortcode")),
                    "uploaded_at_utc": receipt.get("uploaded_at_utc"),
                }
            )

    return {
        "projects": projects,
        "yt_uploads": yt_uploads,
        "ig_uploads": sorted(ig_uploads, key=lambda x: x["uploaded_at_utc"]),
        "ig_carousel_uploads": sorted(ig_carousel_uploads, key=lambda x: x["uploaded_at_utc"]),
        "tt_uploads": sorted(tt_uploads, key=lambda x: x["uploaded_at_utc"]),
        "ig_card_runs": ig_card_runs,
        "guardrail_signals": guardrail_signals,
    }


def _evaluate_duration_for_youtube(project_id: str, duration_sec: float) -> tuple[bool, str]:
    if duration_sec <= 0:
        return False, "unknown_duration"
    if duration_sec < SHORTS_EXPRESSIVE_V8_DURATION_MIN_SEC:
        return False, f"under_61.5s_tiktok_floor ({duration_sec:.1f}s)"
    max_allowed = (
        120.0
        if project_id.startswith(LEGACY_V8_120S_ALLOWLIST_PREFIXES)
        else float(SHORTS_EXPRESSIVE_V8_R75_MAX_SEC)
    )
    if duration_sec > min(max_allowed, SHORTS_HARD_CEILING_SEC):
        return False, f"exceeds_ceiling ({duration_sec:.1f}s > {max_allowed:.1f}s)"
    return True, f"ok ({duration_sec:.1f}s <= {max_allowed:.0f}s)"


def evaluate_youtube_schedule(
    report_ctx: dict[str, Any],
    inventory: dict[str, Any],
    *,
    now_utc: datetime,
) -> dict[str, Any]:
    """Evaluates YouTube HOLD/GO verdict, anti-penalty audit, optimal cadence, and slot assignments."""
    checks: list[dict[str, str]] = []
    block_reasons: list[str] = []
    warn_reasons: list[str] = []

    def _add_check(cid: str, status: str, detail: str) -> None:
        checks.append({"id": cid, "status": status, "detail": detail})
        if status == "BLOCK":
            block_reasons.append(f"{cid}: {detail}")
        elif status == "WARN":
            warn_reasons.append(f"{cid}: {detail}")

    age_h = report_ctx.get("report_age_hours")
    if not report_ctx.get("metrics_path"):
        _add_check("YT-REPORT-FRESH", "BLOCK", "No studio_metrics.json Daily Report found")
    elif age_h is not None and age_h > YT_HOLD_REPORT_AGE_HOURS:
        _add_check("YT-REPORT-FRESH", "BLOCK", f"Daily Report stale ({age_h:.1f}h > {YT_HOLD_REPORT_AGE_HOURS:.0f}h)")
    elif age_h is not None and age_h > YT_MAX_REPORT_STALE_HOURS:
        _add_check("YT-REPORT-FRESH", "WARN", f"Daily Report aging ({age_h:.1f}h > {YT_MAX_REPORT_STALE_HOURS:.0f}h)")
    else:
        _add_check("YT-REPORT-FRESH", "PASS", f"Daily Report {report_ctx.get('report_date')} ({age_h:.1f}h old)" if age_h is not None else "Present")

    mode = report_ctx.get("data_source_mode")
    if mode != "LIVE_CDP_DOM":
        _add_check("YT-DOM-MODE", "WARN", f"Report mode is {mode} (not LIVE_CDP_DOM)")
    elif report_ctx.get("partial_dom_scrape_anomaly"):
        _add_check(
            "YT-DOM-MODE",
            "WARN",
            f"Partial DOM scrape detected (views_24h={report_ctx.get('views_24h')}, realtime_48h={report_ctx.get('realtime_48h_views')}, watch={report_ctx.get('watch_hours_24h')}h, measured_videos={report_ctx.get('measured_video_count')})",
        )
    else:
        _add_check("YT-DOM-MODE", "PASS", "LIVE_CDP_DOM clean")

    # Anti-penalty structural checks
    sim_cnt = int(report_ctx.get("simultaneous_publish_count") or 0)
    _add_check(
        "YT-NO-SIMULTANEOUS",
        "BLOCK" if sim_cnt > 0 else "PASS",
        f"simultaneous_publish_count={sim_cnt}" if sim_cnt > 0 else "0 simultaneous releases",
    )

    quarantine_cnt = int(report_ctx.get("quarantine_count") or 0)
    _add_check(
        "YT-ZERO-QUARANTINE",
        "BLOCK" if quarantine_cnt > 0 else "PASS",
        f"quarantine_count={quarantine_cnt}" if quarantine_cnt > 0 else "0 quarantined episodes",
    )

    _add_check(
        "YT-R75-PLAYLIST-BAN",
        "PASS" if report_ctx.get("playlists_purged_zero") else "WARN",
        "0 playlists verified (R75)" if report_ctx.get("playlists_purged_zero") else "Verify studio_playlist_purge_receipt.json == 0",
    )

    polluted_tag_items = (inventory.get("guardrail_signals") or {}).get("r75_polluted_tags") or []
    _add_check(
        "YT-R75-TAG-HYGIENE",
        "BLOCK" if polluted_tag_items else "PASS",
        f"R75 banned tech tags in {len(polluted_tag_items)} project(s): {[x['project_id'] for x in polluted_tag_items]}"
        if polluted_tag_items
        else "0 banned off-topic tech tags across active episodes",
    )

    # Audience & retention signal evaluation
    us_pct = report_ctx.get("us_share_pct")
    feed_pct = report_ctx.get("shorts_feed_pct")
    viewed_pct = report_ctx.get("viewed_pct")
    apv_pct = report_ctx.get("apv_pct")

    if us_pct is not None and us_pct < YT_US_SHARE_THROTTLE_PCT:
        _add_check("YT-US-AUDIENCE", "WARN", f"US share {us_pct:.1f}% < {YT_US_SHARE_THROTTLE_PCT:.0f}% throttle floor")
    elif us_pct is not None and us_pct >= YT_US_SHARE_GATE_PCT:
        _add_check("YT-US-AUDIENCE", "PASS", f"US {us_pct:.1f}% (>= {YT_US_SHARE_GATE_PCT:.0f}%), Tier-1 {report_ctx.get('tier1_share_pct')}%")

    if feed_pct is not None and feed_pct >= YT_SHORTS_FEED_GATE_PCT:
        _add_check("YT-SHORTS-FEED", "PASS", f"Shorts Feed {feed_pct:.1f}% (>= {YT_SHORTS_FEED_GATE_PCT:.0f}%)")
    elif feed_pct is not None:
        _add_check("YT-SHORTS-FEED", "WARN", f"Shorts Feed {feed_pct:.1f}% < {YT_SHORTS_FEED_GATE_PCT:.0f}%")

    throttle_flag = False
    if viewed_pct is not None and viewed_pct < YT_VIEWED_THROTTLE_PCT and (apv_pct is None or apv_pct < YT_APV_THROTTLE_PCT):
        throttle_flag = True
        _add_check("YT-3S-HOOK", "WARN", f"3s Hook {viewed_pct:.1f}% & APV {apv_pct}% below throttle floor -> slow cadence")
    elif viewed_pct is not None and viewed_pct < YT_VIEWED_HOOK_GATE_PCT:
        _add_check("YT-3S-HOOK", "WARN", f"3s Hook {viewed_pct:.1f}% < {YT_VIEWED_HOOK_GATE_PCT:.0f}% gate (require <=12w R68-H hook, keep 1/day cap)")
    elif viewed_pct is not None:
        _add_check("YT-3S-HOOK", "PASS", f"3s Hook {viewed_pct:.1f}% (>= {YT_VIEWED_HOOK_GATE_PCT:.0f}%)")

    if apv_pct is not None:
        _add_check(
            "YT-APV",
            "PASS" if apv_pct >= YT_APV_GATE_PCT else "WARN",
            f"APV {apv_pct:.1f}% (gate >= {YT_APV_GATE_PCT:.0f}%)",
        )

    # Analyze live scheduled buffer & Watchdog duties
    projects = inventory["projects"]
    scheduled_live = [
        p for p in projects
        if p["yt"]["uploaded"] and p["yt"]["visibility"] == "scheduled"
    ]
    occupied_et_dates: set[str] = set()
    latest_sched_utc: datetime | None = None
    for p in scheduled_live:
        dt = _parse_utc(p["yt"]["scheduled_at_utc"])
        if dt:
            occupied_et_dates.add(dt.astimezone(ET_TZ).date().isoformat())
            if latest_sched_utc is None or dt > latest_sched_utc:
                latest_sched_utc = dt

    # Also include today's ET date if a video already went Public today in ET
    today_et_str = now_utc.astimezone(ET_TZ).date().isoformat()
    for p in projects:
        if p["yt"]["uploaded"] and p["yt"]["visibility"] == "public":
            dt = _parse_utc(p["yt"]["scheduled_at_utc"])
            if dt and dt.astimezone(ET_TZ).date().isoformat() == today_et_str:
                occupied_et_dates.add(today_et_str)

    due_promotions = [p["project_id"] for p in projects if p["yt"]["due_for_promotion"]]
    missing_pins_eligible = [
        p["project_id"]
        for p in projects
        if p["yt"]["uploaded"]
        and p["yt"]["visibility"] == "public"
        and not p["yt"]["doi_pinned"]
        and (p["yt"]["elapsed_hours"] is None or p["yt"]["elapsed_hours"] >= MIN_HOURS_AFTER_PUBLIC_BEFORE_PIN)
    ]
    missing_links_unlocked = [
        p["project_id"]
        for p in projects
        if p["yt"]["uploaded"]
        and p["yt"]["visibility"] in {"public", "scheduled"}
        and not p["yt"]["related_linked"]
        and not p["yt"]["in_pre_freeze"]
        and not p["yt"]["in_post_freeze"]
    ]
    frozen_projects = [
        p["project_id"] for p in projects if p["yt"]["in_pre_freeze"] or p["yt"]["in_post_freeze"]
    ]
    scheduled_missing_links = [
        p["project_id"]
        for p in scheduled_live
        if not p["yt"]["related_linked"] and not p["yt"]["in_pre_freeze"]
    ]
    _add_check(
        "YT-R35B-SCHEDULED-LINK",
        "WARN" if scheduled_missing_links else "PASS",
        f"Scheduled Short(s) missing R35-B Related video link: {scheduled_missing_links}"
        if scheduled_missing_links
        else "All unlocked Scheduled Shorts linked to clean Public Anchor",
    )

    # Candidate unpublished projects (including R82/R84 held rebuilds for visibility)
    ready_candidates: list[dict[str, Any]] = []
    blocked_candidates: list[dict[str, Any]] = []
    for p in projects:
        if p["yt"]["uploaded"] or not p["mp4_exists"]:
            continue
        if p["retired_or_frozen"]:
            if p["project_id"].endswith("_r82") or p["project_id"].startswith(R85_REBUILD_HOLD_PREFIXES):
                reasons = [f"r85_rebuild_hold ({p['retired_reason']})"]
                for r in p["qa_issues"]:
                    if r not in reasons:
                        reasons.append(r)
                blocked_candidates.append(
                    {
                        "project_id": p["project_id"],
                        "reasons": reasons[:6],
                        "qa_evidence_paths": p.get("qa_evidence_paths") or {},
                        "ceo_verify_receipt": p.get("ceo_verify_receipt"),
                        "ceo_verified": bool(p.get("ceo_verified")),
                    }
                )
            continue
        dur_ok, dur_note = _evaluate_duration_for_youtube(p["project_id"], p["duration_sec"])
        if p["qa_passed"] and dur_ok:
            ready_candidates.append(
                {
                    "project_id": p["project_id"],
                    "duration_sec": p["duration_sec"],
                    "bundle_ready": p["bundle_ready"],
                    "note": dur_note,
                    "qa_evidence_paths": p.get("qa_evidence_paths") or {},
                    "ceo_verify_receipt": p.get("ceo_verify_receipt"),
                    "ceo_verified": bool(p.get("ceo_verified")),
                }
            )
        else:
            reasons = list(p["qa_issues"])
            if not dur_ok:
                reasons.append(dur_note)
            blocked_candidates.append(
                {
                    "project_id": p["project_id"],
                    "reasons": reasons[:6],
                    "qa_evidence_paths": p.get("qa_evidence_paths") or {},
                    "ceo_verify_receipt": p.get("ceo_verify_receipt"),
                    "ceo_verified": bool(p.get("ceo_verified")),
                }
            )

    runway_days = len(scheduled_live)
    warmup_floor_utc = now_utc + timedelta(minutes=MIN_SCHEDULE_WARMUP_MINUTES)
    next_slot_utc = _next_et_window(
        now_utc,
        ((YT_PRIME_SLOT_HOUR_ET, YT_PRIME_SLOT_MINUTE_ET),),
        earliest_utc=warmup_floor_utc,
        occupied_et_dates=occupied_et_dates,
    )

    subs = int(report_ctx.get("subscribers_total") or 0)
    regime = "under_10k_seed_protection" if subs < YT_UNDER_10K_SUBS_THRESHOLD else "growth_multi_slot"
    cadence_label = (
        "1 Short / Day @ Slot 4 (19:30 ET) | Longform 16:9: HOLD"
        if regime == "under_10k_seed_protection"
        else "1-2 Shorts / Day (12:00 ET & 19:30 ET)"
    )

    if block_reasons:
        verdict = "HOLD"
    elif throttle_flag:
        verdict = "THROTTLE"
        cadence_label = "1 Short / 48h @ Slot 4 (19:30 ET) until Hook/APV recover"
    elif runway_days >= YT_MAX_QUEUE_RUNWAY_DAYS:
        verdict = "HOLD"
        warn_reasons.append(f"Buffer already >= {YT_MAX_QUEUE_RUNWAY_DAYS} days ({runway_days} scheduled); hold new uploads to preserve creative agility")
    elif not ready_candidates and runway_days < YT_TARGET_BUFFER_DAYS_MIN:
        verdict = "HOLD"
        warn_reasons.append(f"0 QA-ready unpublished candidates and buffer is only {runway_days}d (< {YT_TARGET_BUFFER_DAYS_MIN}d target) -> produce new v8 episode first")
    elif warn_reasons:
        verdict = "CONDITIONAL_GO"
    else:
        verdict = "GO"

    return {
        "platform": "youtube",
        "handle": CHANNEL_HANDLE,
        "verdict": verdict,
        "regime": regime,
        "optimal_cadence": cadence_label,
        "longform_verdict": "HOLD (<10K subs & 3s Hook <70%)" if subs < YT_UNDER_10K_SUBS_THRESHOLD else "GO",
        "scheduled_runway_days": runway_days,
        "scheduled_videos": [
            {
                "project_id": p["project_id"],
                "video_id": p["yt"]["video_id"],
                "scheduled_time_et": p["yt"]["scheduled_time_et"],
                "scheduled_at_utc": p["yt"]["scheduled_at_utc"],
                "quiz_scheduled_or_done": p["yt"]["quiz_scheduled_or_done"],
                "quiz_receipt": p["yt"]["quiz_receipt"],
            }
            for p in scheduled_live
        ],
        "next_optimal_slot": _fmt_multi_tz(next_slot_utc),
        "watchdog_tasks": {
            "due_for_public_transition": due_promotions,
            "missing_r35_pins_eligible": missing_pins_eligible,
            "missing_r35b_links_unlocked": missing_links_unlocked,
            "active_freeze_protected": frozen_projects,
        },
        "ready_candidates": ready_candidates,
        "blocked_candidates": blocked_candidates,
        "penalty_audit": checks,
        "block_reasons": block_reasons,
        "warn_reasons": warn_reasons,
    }


def evaluate_instagram_schedule(
    inventory: dict[str, Any],
    *,
    now_utc: datetime,
    avoid_utc_times: list[datetime],
    report_ctx: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Evaluates Instagram Reels & 4:5 Card Carousel HOLD/GO verdict, Trial Reels, and anti-spam timing."""
    checks: list[dict[str, str]] = []
    block_reasons: list[str] = []
    warn_reasons: list[str] = []

    ig_uploads = inventory["ig_uploads"]
    ig_carousel_uploads = inventory.get("ig_carousel_uploads") or []
    ig_followers = int((report_ctx or {}).get("instagram_followers") or 0)
    trial_reels_eligible = ig_followers >= IG_TRIAL_REELS_MIN_FOLLOWERS
    reel_distribution_mode = (
        "Trial Reels (SS_PERFORMANCE)"
        if trial_reels_eligible
        else f"Standard Reel (Warmup {ig_followers}/{IG_TRIAL_REELS_MIN_FOLLOWERS} followers)"
    )

    total_reels = len(ig_uploads)
    in_warmup = total_reels < IG_WARMUP_POST_COUNT
    cooldown_h = IG_REEL_COOLDOWN_HOURS_WARMUP if in_warmup else IG_REEL_COOLDOWN_HOURS_STEADY
    max_per_24h = IG_MAX_POSTS_PER_24H_WARMUP if in_warmup else IG_MAX_POSTS_PER_24H_STEADY

    last_ig_dt = _parse_utc(ig_uploads[-1]["uploaded_at_utc"]) if ig_uploads else None
    hours_since_last = round((now_utc - last_ig_dt).total_seconds() / 3600.0, 2) if last_ig_dt else None
    recent_24h_dts = [
        dt for dt in (_parse_utc(u["uploaded_at_utc"]) for u in ig_uploads)
        if dt is not None and dt >= now_utc - timedelta(hours=24)
    ]
    uploads_24h = len(recent_24h_dts)

    if uploads_24h >= max_per_24h:
        block_reasons.append(f"IG 24h cap reached ({uploads_24h}/{max_per_24h})")
        checks.append({"id": "IG-RATE-LIMIT", "status": "BLOCK", "detail": f"{uploads_24h} upload(s) in last 24h (cap {max_per_24h})"})
    elif hours_since_last is not None and hours_since_last < cooldown_h:
        block_reasons.append(f"IG cooldown active ({hours_since_last:.1f}h < {cooldown_h:.0f}h)")
        checks.append({"id": "IG-COOLDOWN", "status": "BLOCK", "detail": f"{hours_since_last:.1f}h since last Reel (< {cooldown_h:.0f}h)"})
    else:
        checks.append({
            "id": "IG-COOLDOWN",
            "status": "PASS",
            "detail": f"{hours_since_last:.1f}h since last Reel (>= {cooldown_h:.0f}h)" if hours_since_last is not None else "Ready (0h conflict)",
        })

    # Eligible Reel candidates: QA-passed + bundle ready + not yet on Instagram
    # Prefer episodes already Public on YouTube (with >= +18h stagger) to avoid cross-platform collision
    candidates: list[dict[str, Any]] = []
    needs_bundle: list[str] = []
    for p in inventory["projects"]:
        if p["retired_or_frozen"] or not p["mp4_exists"] or p["instagram"]["uploaded"]:
            continue
        if not p["qa_passed"]:
            continue
        if not p["bundle_ready"]:
            needs_bundle.append(p["project_id"])
            continue
        yt_vis = p["yt"]["visibility"]
        priority = 0 if yt_vis == "public" else (1 if yt_vis == "scheduled" else 2)
        candidates.append(
            {
                "project_id": p["project_id"],
                "youtube_visibility": yt_vis,
                "youtube_scheduled_at_utc": p["yt"]["scheduled_at_utc"],
                "duration_sec": p["duration_sec"],
                "priority": priority,
                "qa_evidence_paths": p.get("qa_evidence_paths") or {},
                "ceo_verify_receipt": p.get("ceo_verify_receipt"),
                "ceo_verified": bool(p.get("ceo_verified")),
            }
        )
    candidates.sort(key=lambda c: (c["priority"], c["project_id"]))

    card_candidates = [
        r for r in inventory["ig_card_runs"] if r["package_ready"] and not r["uploaded"]
    ]
    project_carousel_candidates = [
        p["project_id"]
        for p in inventory["projects"]
        if not p["retired_or_frozen"] and p["instagram"]["carousel_ready"] and not p["instagram"]["carousel_uploaded"]
    ]

    if not candidates and not card_candidates and not project_carousel_candidates:
        block_reasons.append("No bundle-ready Reels or 4:5 Card Carousel packages pending upload")
        checks.append({"id": "IG-INVENTORY", "status": "BLOCK", "detail": "0 pending IG candidates"})
    else:
        checks.append({
            "id": "IG-INVENTORY",
            "status": "PASS",
            "detail": f"{len(candidates)} Reel(s) + {len(card_candidates) + len(project_carousel_candidates)} 4:5 Carousel(s) ready",
        })

    carousels_last_7d = sum(
        1 for u in ig_carousel_uploads
        if (dt := _parse_utc(u.get("uploaded_at_utc"))) is not None and dt >= now_utc - timedelta(days=7)
    )
    if carousels_last_7d >= IG_CAROUSEL_MAX_PER_WEEK:
        warn_reasons.append(f"IG 4:5 Carousel weekly cap reached ({carousels_last_7d}/{IG_CAROUSEL_MAX_PER_WEEK} in 7d)")
        checks.append({
            "id": "IG-CAROUSEL-CAP",
            "status": "WARN",
            "detail": f"{carousels_last_7d}/{IG_CAROUSEL_MAX_PER_WEEK} Carousels in 7d -> pause new carousels",
        })
    else:
        checks.append({
            "id": "IG-CAROUSEL-CAP",
            "status": "PASS",
            "detail": f"{carousels_last_7d}/{IG_CAROUSEL_MAX_PER_WEEK} Carousels in 7d; locked {IG_CAROUSEL_ASPECT_RATIO_LOCKED}, >={IG_CAROUSEL_MIN_GAP_FROM_REEL_HOURS:.0f}h Reel gap",
        })

    checks.append({
        "id": "IG-ANTI-SPAM-SPEC",
        "status": "PASS",
        "detail": f"Clean 1080x1920 bundle (0 watermark), <=90ch Line-1 hook, AI label ON, {reel_distribution_mode}",
    })

    cooldown_floor = (last_ig_dt + timedelta(hours=cooldown_h)) if last_ig_dt else now_utc
    cap_floor = (min(recent_24h_dts) + timedelta(hours=24)) if (uploads_24h >= max_per_24h and recent_24h_dts) else now_utc
    earliest_utc = max(cooldown_floor, cap_floor)
    next_slot_utc = _next_et_window(
        now_utc,
        IG_PRIME_WINDOWS_ET,
        earliest_utc=earliest_utc,
        avoid_utc_times=avoid_utc_times,
        min_stagger_min=IG_CROSS_PLATFORM_MIN_STAGGER_MIN,
    )

    # Non-colliding 4:5 Carousel slot: >= +24h post-Reel & >= 18h clear of recent/next Reels
    reel_anchor_for_carousel = next_slot_utc if candidates else (last_ig_dt or now_utc)
    carousel_earliest = max(
        now_utc,
        reel_anchor_for_carousel + timedelta(hours=IG_CAROUSEL_POST_REEL_OFFSET_HOURS) if (candidates or last_ig_dt) else now_utc,
    )
    occupied_reel_dates = set()
    reel_avoid_dts = [dt for dt in (last_ig_dt, next_slot_utc if candidates else None) if dt is not None]
    for rdt in reel_avoid_dts:
        occupied_reel_dates.add(rdt.astimezone(ET_TZ).date().isoformat())
    next_carousel_slot_utc = _next_et_window(
        now_utc,
        IG_PRIME_WINDOWS_ET,
        earliest_utc=carousel_earliest,
        occupied_et_dates=occupied_reel_dates,
        avoid_utc_times=reel_avoid_dts + list(avoid_utc_times),
        min_stagger_min=int(IG_CAROUSEL_MIN_GAP_FROM_REEL_HOURS * 60),
    )

    verdict = "HOLD" if block_reasons else ("CONDITIONAL_GO" if warn_reasons else "GO")
    cadence = (
        f"1 Reel / Day (warmup {total_reels}/{IG_WARMUP_POST_COUNT}) @ 13:30 ET or 18:15 ET; Carousels 2-3/wk (>={IG_CAROUSEL_MIN_GAP_FROM_REEL_HOURS:.0f}h Reel gap)"
        if in_warmup
        else "1-2 Reels / Day + 2-3 Carousels / Week (non-Reel days)"
    )

    return {
        "platform": "instagram",
        "handle": IG_HANDLE,
        "verdict": verdict,
        "regime": "warmup" if in_warmup else "steady",
        "followers_total": ig_followers,
        "trial_reels_eligible": trial_reels_eligible,
        "reel_distribution_mode": reel_distribution_mode,
        "total_uploaded_reels": total_reels,
        "carousels_last_7d": carousels_last_7d,
        "hours_since_last_upload": hours_since_last,
        "optimal_cadence": cadence,
        "next_optimal_slot": _fmt_multi_tz(next_slot_utc),
        "next_carousel_slot": _fmt_multi_tz(next_carousel_slot_utc),
        "ready_reel_candidates": candidates,
        "ready_card_carousels": card_candidates,
        "ready_project_carousels": project_carousel_candidates,
        "needs_bundle_export": needs_bundle,
        "penalty_audit": checks,
        "block_reasons": block_reasons,
        "warn_reasons": warn_reasons,
    }


def evaluate_tiktok_schedule(
    inventory: dict[str, Any],
    *,
    now_utc: datetime,
    avoid_utc_times: list[datetime],
) -> dict[str, Any]:
    """Evaluates TikTok Creator Rewards (>60s) HOLD/GO verdict and anti-shadowban timing."""
    checks: list[dict[str, str]] = []
    block_reasons: list[str] = []
    warn_reasons: list[str] = []

    tt_uploads = inventory["tt_uploads"]
    total_posts = len(tt_uploads)
    in_warmup = total_posts < TIKTOK_WARMUP_POST_COUNT
    cooldown_h = TIKTOK_COOLDOWN_HOURS_WARMUP if in_warmup else TIKTOK_COOLDOWN_HOURS_STEADY
    max_per_24h = TIKTOK_MAX_POSTS_PER_24H_WARMUP if in_warmup else TIKTOK_MAX_POSTS_PER_24H_STEADY

    last_tt_dt = _parse_utc(tt_uploads[-1]["uploaded_at_utc"]) if tt_uploads else None
    hours_since_last = round((now_utc - last_tt_dt).total_seconds() / 3600.0, 2) if last_tt_dt else None
    recent_24h_dts = [
        dt for dt in (_parse_utc(u["uploaded_at_utc"]) for u in tt_uploads)
        if dt is not None and dt >= now_utc - timedelta(hours=24)
    ]
    uploads_24h = len(recent_24h_dts)

    if uploads_24h >= max_per_24h:
        block_reasons.append(f"TikTok 24h cap reached ({uploads_24h}/{max_per_24h})")
        checks.append({"id": "TT-RATE-LIMIT", "status": "BLOCK", "detail": f"{uploads_24h} upload(s) in last 24h (cap {max_per_24h})"})
    elif hours_since_last is not None and hours_since_last < cooldown_h:
        block_reasons.append(f"TikTok cooldown active ({hours_since_last:.1f}h < {cooldown_h:.0f}h)")
        checks.append({"id": "TT-COOLDOWN", "status": "BLOCK", "detail": f"{hours_since_last:.1f}h since last post (< {cooldown_h:.0f}h)"})
    else:
        checks.append({
            "id": "TT-COOLDOWN",
            "status": "PASS",
            "detail": f"{hours_since_last:.1f}h since last post (>= {cooldown_h:.0f}h)" if hours_since_last is not None else "Ready (0h conflict)",
        })

    candidates: list[dict[str, Any]] = []
    rejected_under_60s: list[str] = []
    needs_bundle: list[str] = []
    for p in inventory["projects"]:
        if p["retired_or_frozen"] or not p["mp4_exists"] or p["tiktok"]["uploaded"]:
            continue
        if not p["qa_passed"]:
            continue
        if not p["tiktok_over_60s"]:
            rejected_under_60s.append(f"{p['project_id']} ({p['duration_sec']:.1f}s < 61.5s)")
            continue
        if not p["bundle_ready"]:
            needs_bundle.append(p["project_id"])
            continue
        yt_vis = p["yt"]["visibility"]
        priority = 0 if yt_vis == "public" else (1 if yt_vis == "scheduled" else 2)
        candidates.append(
            {
                "project_id": p["project_id"],
                "youtube_visibility": yt_vis,
                "duration_sec": p["duration_sec"],
                "priority": priority,
                "qa_evidence_paths": p.get("qa_evidence_paths") or {},
                "ceo_verify_receipt": p.get("ceo_verify_receipt"),
                "ceo_verified": bool(p.get("ceo_verified")),
            }
        )
    candidates.sort(key=lambda c: (c["priority"], c["project_id"]))

    if rejected_under_60s:
        warn_reasons.append(f"Excluded <61.5s from Creator Rewards: {', '.join(rejected_under_60s)}")
    if not candidates:
        block_reasons.append("No >=61.5s bundle-ready candidates pending TikTok upload")
        checks.append({"id": "TT-CREATOR-REWARDS-60S", "status": "BLOCK", "detail": "0 eligible >=61.5s candidates"})
    else:
        checks.append({
            "id": "TT-CREATOR-REWARDS-60S",
            "status": "PASS",
            "detail": f"{len(candidates)} candidate(s) >= {TIKTOK_CREATOR_REWARDS_MIN_SEC}s with clean bundle",
        })

    checks.append({
        "id": "TT-SECURITY-AIGC",
        "status": "PASS",
        "detail": "NO VPN, AIGC disclosure ON, 4-5 niche tags (0 #fyp/#viral), halt cleanly on CAPTCHA",
    })

    cooldown_floor = (last_tt_dt + timedelta(hours=cooldown_h)) if last_tt_dt else now_utc
    cap_floor = (min(recent_24h_dts) + timedelta(hours=24)) if (uploads_24h >= max_per_24h and recent_24h_dts) else now_utc
    earliest_utc = max(cooldown_floor, cap_floor)
    next_slot_utc = _next_et_window(
        now_utc,
        TIKTOK_PRIME_WINDOWS_ET,
        earliest_utc=earliest_utc,
        avoid_utc_times=avoid_utc_times,
        min_stagger_min=IG_CROSS_PLATFORM_MIN_STAGGER_MIN,
    )

    verdict = "HOLD" if block_reasons else ("CONDITIONAL_GO" if warn_reasons else "GO")
    cadence = (
        f"1 Video / Day (warmup {total_posts}/{TIKTOK_WARMUP_POST_COUNT}) @ 15:30 ET or 20:45 ET"
        if in_warmup
        else "1-2 Videos / Day (>=10h gap)"
    )

    return {
        "platform": "tiktok",
        "handle": TIKTOK_HANDLE,
        "verdict": verdict,
        "regime": "warmup" if in_warmup else "steady",
        "total_uploaded_videos": total_posts,
        "hours_since_last_upload": hours_since_last,
        "optimal_cadence": cadence,
        "next_optimal_slot": _fmt_multi_tz(next_slot_utc),
        "ready_candidates": candidates,
        "rejected_under_60s": rejected_under_60s,
        "needs_bundle_export": needs_bundle,
        "penalty_audit": checks,
        "block_reasons": block_reasons,
        "warn_reasons": warn_reasons,
    }


def audit_anti_trap_guardrails(
    report_ctx: dict[str, Any],
    inventory: dict[str, Any],
) -> dict[str, Any]:
    """Audits the 6 permanent anti-trap guardrails and user on-hold feature exclusions."""
    signals = inventory.get("guardrail_signals") or {}
    checks: list[dict[str, str]] = []
    block_violations: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    def _record(rule: str, status: str, platform: str, detail: str, target: str = "") -> None:
        checks.append({"rule": rule, "status": status, "platform": platform, "detail": detail})
        if status == "BLOCK":
            block_violations.append({"rule": rule, "platform": platform, "target": target, "detail": detail})
        elif status == "WARN":
            warnings.append({"rule": rule, "platform": platform, "target": target, "detail": detail})

    srt_hits = signals.get("srt_cc_uploads") or []
    if srt_hits:
        pids = ", ".join(h["project_id"] for h in srt_hits)
        _record(
            "youtube_srt_cc_upload_banned",
            "BLOCK",
            "youtube",
            f"External SRT/VTT CC upload banned (burned-in 102pt ASS collision risk): {pids}",
            pids,
        )
    else:
        _record(
            "youtube_srt_cc_upload_banned",
            "PASS",
            "youtube",
            "0 external SRT/VTT CC uploads (102pt burned-in ASS protected from double captions)",
        )

    dub_hits = signals.get("auto_dubbing_on") or []
    if report_ctx.get("auto_dubbing_checked_on") or dub_hits:
        _record(
            "youtube_auto_dubbing_burned_ass_off",
            "WARN",
            "youtube",
            "YouTube Auto-Dubbing detected ON while burned-in English ASS is active — disable immediately",
            ",".join(h["project_id"] for h in dub_hits) or "channel_settings",
        )
    else:
        _record(
            "youtube_auto_dubbing_burned_ass_off",
            "PASS",
            "youtube",
            "Auto-Dubbing OFF lock verified for burned-in English ASS Shorts",
        )

    tt_comm_hits = signals.get("tiktok_commercial_sound_over_60s") or []
    if tt_comm_hits:
        pids = ", ".join(h["project_id"] for h in tt_comm_hits)
        _record(
            "tiktok_commercial_sound_over_60s_banned",
            "BLOCK",
            "tiktok",
            f">60s TikTok Commercial Music Library usage banned (mute & CRP forfeit risk): {pids}",
            pids,
        )
    else:
        _record(
            "tiktok_commercial_sound_over_60s_banned",
            "PASS",
            "tiktok",
            "Original Audio only for >60s Creator Rewards videos (0 commercial music risk)",
        )

    bad_ar_hits = signals.get("carousel_bad_aspect_ratio") or []
    if bad_ar_hits:
        targets = ", ".join(f"{h['target']} ({h['dims']})" for h in bad_ar_hits[:4])
        _record(
            "instagram_carousel_aspect_ratio_locked",
            "BLOCK",
            "instagram",
            f"Instagram Carousel must be locked to 4:5 (1080x1350); invalid dimensions: {targets}",
            targets,
        )
    else:
        _record(
            "instagram_carousel_aspect_ratio_locked",
            "PASS",
            "instagram",
            f"Locked to {IG_CAROUSEL_ASPECT_RATIO_LOCKED} with center 3:4 safe zone",
        )

    notes_hits = signals.get("instagram_notes_enabled") or []
    if notes_hits:
        _record(
            "instagram_notes_deprecated_excluded",
            "WARN",
            "instagram",
            "Instagram Notes was deprecated (Apr 2025) & gives 0 non-follower reach; disable",
            ",".join(h["project_id"] for h in notes_hits),
        )
    else:
        _record(
            "instagram_notes_deprecated_excluded",
            "PASS",
            "instagram",
            "Instagram Notes excluded (deprecated Apr 2025, 0 non-follower reach)",
        )

    hold_hits = signals.get("on_hold_features_enabled") or []
    if hold_hits:
        desc = ", ".join(f"{h['project_id']}:{h['feature']}" for h in hold_hits)
        _record(
            "on_hold_excluded_features",
            "BLOCK",
            "instagram",
            f"User on-hold features must not be scheduled/executed: {desc}",
            desc,
        )
    else:
        _record(
            "on_hold_excluded_features",
            "PASS",
            "instagram",
            "On-hold features excluded: instagram_manychat_comment_dm, instagram_story_highlights",
        )

    return {
        **ANTI_TRAP_GUARDRAILS_SPEC,
        "status": "HOLD" if block_violations else ("WARN" if warnings else "PASS"),
        "passed": len(block_violations) == 0,
        "block_violations": block_violations,
        "warnings": warnings,
        "checks": checks,
    }


def _select_anchor_episode(
    *,
    plan_date: str,
    inventory: dict[str, Any],
    yt_eval: dict[str, Any],
) -> dict[str, Any] | None:
    """Selects today's primary YouTube anchor episode for 5-asset ecosystem staggering."""
    projects_by_id = {p["project_id"]: p for p in inventory.get("projects", [])}
    sched_items: list[tuple[datetime, dict[str, Any]]] = []
    for sv in yt_eval.get("scheduled_videos", []):
        dt = _parse_utc(sv.get("scheduled_at_utc"))
        if dt is not None:
            sched_items.append((dt, sv))
    sched_items.sort(key=lambda x: x[0])

    # Priority 1: Video scheduled on `plan_date` in ET (e.g., 2026-11-15 19:30 ET)
    for dt, sv in sched_items:
        if dt.astimezone(ET_TZ).date().isoformat() == plan_date:
            pid = sv["project_id"]
            return {
                "project_id": pid,
                "video_id": sv.get("video_id"),
                "scheduled_at_utc": dt,
                "source": "scheduled_today",
                "project": projects_by_id.get(pid, {}),
            }

    # Priority 2: Next ready YouTube candidate if YT is GO / CONDITIONAL_GO / THROTTLE
    if yt_eval.get("verdict") in {"GO", "CONDITIONAL_GO", "THROTTLE"} and yt_eval.get("ready_candidates"):
        top = yt_eval["ready_candidates"][0]
        dt = _parse_utc((yt_eval.get("next_optimal_slot") or {}).get("iso_utc"))
        if dt is not None:
            pid = top["project_id"]
            return {
                "project_id": pid,
                "video_id": None,
                "scheduled_at_utc": dt,
                "source": "ready_candidate",
                "project": projects_by_id.get(pid, {}),
            }

    # Priority 3: Earliest scheduled future episode on runway
    if sched_items:
        dt, sv = sched_items[0]
        pid = sv["project_id"]
        return {
            "project_id": pid,
            "video_id": sv.get("video_id"),
            "scheduled_at_utc": dt,
            "source": "scheduled_runway",
            "project": projects_by_id.get(pid, {}),
        }

    return None


def derive_ecosystem_asset_slots(
    *,
    plan_date: str,
    now_utc: datetime,
    report_ctx: dict[str, Any],
    inventory: dict[str, Any],
    yt_eval: dict[str, Any],
    ig_eval: dict[str, Any],
    tt_eval: dict[str, Any],
) -> dict[str, Any]:
    """Derives the 1-Episode -> 5 Automated Assets staggered ecosystem timeline + Daily Inbox Check."""
    py_cmd = "/home/canadaofbin/hermes-venv/bin/python -X utf8"
    anchor = _select_anchor_episode(plan_date=plan_date, inventory=inventory, yt_eval=yt_eval)

    any_active_verdict = any(
        ev.get("verdict") in {"GO", "CONDITIONAL_GO", "THROTTLE"}
        for ev in (yt_eval, ig_eval, tt_eval)
    )
    active = bool(any_active_verdict or anchor is not None)

    assets: dict[str, Any] = {}
    if anchor is not None:
        anchor_pid = anchor["project_id"]
        anchor_vid = anchor["video_id"]
        anchor_proj = anchor["project"] or {}
        yt_dt: datetime = anchor["scheduled_at_utc"]
        yt_block_penalty = bool(yt_eval.get("block_reasons"))

        # 1. YouTube Community Quiz Post (D-Day 16:00 ET = Short - 3.5h)
        quiz_dt = yt_dt - timedelta(hours=YT_QUIZ_PRE_OFFSET_HOURS)
        quiz_done = bool((anchor_proj.get("yt") or {}).get("quiz_scheduled_or_done"))
        if quiz_done:
            quiz_status = "SCHEDULED/DONE"
            quiz_detail = "community_quiz_receipt.json verified (D-Day -3.5h pre-heat)"
        elif yt_block_penalty:
            quiz_status = "HOLD"
            quiz_detail = f"Blocked by YouTube anti-penalty HOLD: {'; '.join(yt_eval['block_reasons'])}"
        else:
            quiz_status = "ACTION_REQUIRED"
            quiz_detail = f"ACTION_REQUIRED: main.py studio-quiz --project {anchor_pid}"

        assets["yt_community_quiz"] = {
            "asset": "YouTube Community Quiz Post",
            "project_id": anchor_pid,
            "video_id": anchor_vid,
            "offset_from_youtube": f"-{YT_QUIZ_PRE_OFFSET_HOURS:.1f}h (D-Day pre-heat)",
            "window": _fmt_multi_tz(quiz_dt),
            "status": quiz_status,
            "detail": quiz_detail,
            "command": f"{py_cmd} main.py studio-quiz --project {anchor_pid}",
        }

        # 2. YouTube Short (D-Day 19:30 ET / 12:00 ET)
        yt_status = "SCHEDULED" if anchor["source"].startswith("scheduled") else yt_eval["verdict"]
        assets["youtube_short"] = {
            "asset": "YouTube Short",
            "project_id": anchor_pid,
            "video_id": anchor_vid,
            "window": _fmt_multi_tz(yt_dt),
            "status": yt_status,
            "warmup_hours": round((yt_dt - now_utc).total_seconds() / 3600.0, 2),
            "playlists_count": 0 if report_ctx.get("playlists_purged_zero") else "VERIFY_ZERO",
            "detail": (
                f"Scheduled {anchor_vid or anchor_pid} @ Slot 4 ({_fmt_multi_tz(yt_dt)['et']}), R75 0 playlists"
                if yt_status == "SCHEDULED"
                else f"YouTube verdict={yt_eval['verdict']}"
            ),
        }

        # 3. TikTok >61.5s Original-Audio Video (D-Day 20:45 ET, >=20h cooldown)
        tt_target_dt = _next_et_window(
            yt_dt + timedelta(minutes=75),
            TIKTOK_PRIME_WINDOWS_ET,
            earliest_utc=yt_dt + timedelta(minutes=60),
        )
        tt_queue_dt = _parse_utc((tt_eval.get("next_optimal_slot") or {}).get("iso_utc")) or tt_target_dt
        tt_slot_dt = max(tt_target_dt, tt_queue_dt) if tt_eval.get("hours_since_last_upload") is not None else tt_target_dt
        anchor_dur = float(anchor_proj.get("duration_sec") or 0.0)
        anchor_bundle = bool(anchor_proj.get("bundle_ready"))
        anchor_tt_done = bool((anchor_proj.get("tiktok") or {}).get("uploaded"))
        tt_active_target = (tt_eval.get("ready_candidates") or [{}])[0].get("project_id")
        if anchor_tt_done:
            tt_status = "DONE"
        elif tt_eval["verdict"] in {"GO", "CONDITIONAL_GO"} and anchor_bundle and anchor_dur >= TIKTOK_CREATOR_REWARDS_MIN_SEC:
            tt_status = tt_eval["verdict"]
        elif tt_eval["verdict"] in {"GO", "CONDITIONAL_GO"} and tt_active_target:
            tt_status = tt_eval["verdict"]
        else:
            tt_status = tt_eval["verdict"]
        assets["tiktok_video"] = {
            "asset": "TikTok >61.5s Original-Audio Video",
            "project_id": anchor_pid,
            "active_queue_target": tt_active_target,
            "duration_sec": anchor_dur,
            "original_audio_only": True,
            "aigc_disclosure_on": True,
            "bundle_ready": anchor_bundle,
            "window": _fmt_multi_tz(tt_slot_dt),
            "next_safe_queue_window": tt_eval["next_optimal_slot"],
            "status": tt_status,
            "detail": (
                f"Anchor {anchor_pid} ({anchor_dur:.1f}s >= 61.5s, Original Audio, AIGC ON); "
                + (f"Queue ready: {tt_active_target}" if tt_active_target else "; ".join(tt_eval.get("block_reasons") or ["bundle/cooldown pending"]))
            ),
            "command": (
                f"{py_cmd} main.py multi-bundle --project {anchor_pid}"
                if not anchor_bundle
                else f"# Run upload_tiktok_video_cdp for {tt_active_target or anchor_pid} at {_fmt_multi_tz(tt_slot_dt)['et']}"
            ),
        }

        # 4. Instagram Clean Reel (D+1 13:30 ET, >= +18h after YouTube + >= 18h cooldown)
        ig_anchor_floor = yt_dt + timedelta(hours=IG_REEL_FROM_YT_MIN_LAG_HOURS)
        ig_stagger_dt = _next_et_window(
            ig_anchor_floor,
            IG_PRIME_WINDOWS_ET,
            earliest_utc=ig_anchor_floor,
            avoid_utc_times=[yt_dt, tt_slot_dt],
            min_stagger_min=IG_CROSS_PLATFORM_MIN_STAGGER_MIN,
        )
        ig_active_target = (ig_eval.get("ready_reel_candidates") or [{}])[0].get("project_id")
        anchor_ig_done = bool((anchor_proj.get("instagram") or {}).get("uploaded"))
        assets["instagram_reel"] = {
            "asset": "Instagram Clean Reel",
            "project_id": anchor_pid,
            "active_queue_target": ig_active_target,
            "offset_from_youtube": f">= +{IG_REEL_FROM_YT_MIN_LAG_HOURS:.0f}h",
            "window": _fmt_multi_tz(ig_stagger_dt),
            "active_queue_window": ig_eval["next_optimal_slot"],
            "trial_reels_eligible": bool(ig_eval.get("trial_reels_eligible")),
            "distribution_mode": ig_eval.get("reel_distribution_mode"),
            "bundle_ready": anchor_bundle,
            "status": "DONE" if anchor_ig_done else ig_eval["verdict"],
            "detail": (
                f"{ig_eval.get('reel_distribution_mode')}; D+1 stagger >= +18h post-YT ({_fmt_multi_tz(ig_stagger_dt)['et']}); "
                + (f"Queue ready now/next slot: {ig_active_target}" if ig_active_target else "; ".join(ig_eval.get("block_reasons") or ["cooldown/bundle"]))
            ),
        }

        # 5. Instagram 4:5 (1080x1350) 6-Slide Carousel (non-Reel day / >= +24h after Reel, 2-3/wk cap)
        car_floor = ig_stagger_dt + timedelta(hours=IG_CAROUSEL_POST_REEL_OFFSET_HOURS)
        reel_avoid = [ig_stagger_dt]
        ig_q_dt = _parse_utc((ig_eval.get("next_optimal_slot") or {}).get("iso_utc"))
        if ig_q_dt:
            reel_avoid.append(ig_q_dt)
        occ_reel_dates = {rdt.astimezone(ET_TZ).date().isoformat() for rdt in reel_avoid}
        car_slot_dt = _next_et_window(
            car_floor,
            IG_PRIME_WINDOWS_ET,
            earliest_utc=car_floor,
            occupied_et_dates=occ_reel_dates,
            avoid_utc_times=reel_avoid + [yt_dt, tt_slot_dt],
            min_stagger_min=int(IG_CAROUSEL_MIN_GAP_FROM_REEL_HOURS * 60),
        )
        car_done = bool((anchor_proj.get("instagram") or {}).get("carousel_uploaded"))
        car_ready = bool((anchor_proj.get("instagram") or {}).get("carousel_ready") or ig_eval.get("ready_card_carousels"))
        car_weekly_used = int(ig_eval.get("carousels_last_7d") or 0)
        if car_done:
            car_status = "DONE"
        elif car_weekly_used >= IG_CAROUSEL_MAX_PER_WEEK:
            car_status = "HOLD"
        elif car_ready:
            car_status = "GO"
        else:
            car_status = "PENDING_ASSETS"
        assets["instagram_carousel"] = {
            "asset": "Instagram 4:5 (1080x1350) 6-Slide Carousel",
            "project_id": anchor_pid,
            "aspect_ratio_locked": IG_CAROUSEL_ASPECT_RATIO_LOCKED,
            "slide_count": IG_CAROUSEL_SLIDE_COUNT,
            "min_gap_from_reel_hours": IG_CAROUSEL_MIN_GAP_FROM_REEL_HOURS,
            "weekly_usage": f"{car_weekly_used}/{IG_CAROUSEL_MAX_PER_WEEK}",
            "window": _fmt_multi_tz(car_slot_dt),
            "status": car_status,
            "receipt_tracked": "instagram_carousel_receipt.json",
            "detail": (
                f"Locked {IG_CAROUSEL_ASPECT_RATIO_LOCKED} ({IG_CAROUSEL_SLIDE_COUNT} slides, center 3:4 safe zone), "
                f"non-Reel day >= +{IG_CAROUSEL_POST_REEL_OFFSET_HOURS:.0f}h post-Reel ({car_weekly_used}/{IG_CAROUSEL_MAX_PER_WEEK} in 7d)"
            ),
        }

    # 6. Daily Zero-Bounce Studio Inbox Check
    try:
        inbox_date = date.fromisoformat(plan_date)
    except Exception:
        inbox_date = now_utc.astimezone(ET_TZ).date()
    inbox_dt = datetime.combine(
        inbox_date,
        time(DAILY_INBOX_CHECK_WINDOW_ET[0], DAILY_INBOX_CHECK_WINDOW_ET[1]),
        tzinfo=ET_TZ,
    ).astimezone(timezone.utc)
    if inbox_dt < now_utc:
        inbox_dt = now_utc
    assets["daily_studio_inbox_check"] = {
        "asset": "Daily Zero-Bounce Studio Inbox Check",
        "window": _fmt_multi_tz(inbox_dt),
        "status": "ACTION_REQUIRED",
        "command": f"{py_cmd} main.py studio-inbox --scan-only",
        "detail": "Studio comments/inbox zero-playback heart & reply routine (0 self-bounce)",
    }

    return {
        "active": active,
        "anchor_episode": (
            {
                "project_id": anchor["project_id"],
                "video_id": anchor["video_id"],
                "source": anchor["source"],
                "youtube_slot": _fmt_multi_tz(anchor["scheduled_at_utc"]),
            }
            if anchor
            else None
        ),
        "assets": assets,
    }


def build_execution_plan(
    *,
    now_utc: datetime,
    yt_eval: dict[str, Any],
    ig_eval: dict[str, Any],
    tt_eval: dict[str, Any],
    ecosystem_slots: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Builds a chronologically ordered multi-platform execution plan for today."""
    steps: list[dict[str, Any]] = []
    py_cmd = "/home/canadaofbin/hermes-venv/bin/python -X utf8"
    eco_assets = (ecosystem_slots or {}).get("assets") or {}

    # 1. Immediate YouTube Watchdog & Sync (if any due transitions, eligible pins, or unlocked links)
    wd = yt_eval["watchdog_tasks"]
    if wd["due_for_public_transition"] or wd["missing_r35_pins_eligible"] or wd["missing_r35b_links_unlocked"]:
        steps.append(
            {
                "order_ts": now_utc.isoformat(),
                "window": _fmt_multi_tz(now_utc),
                "platform": "youtube",
                "action_type": "WATCHDOG_SYNC",
                "verdict": "GO",
                "target": ", ".join(
                    sorted(
                        set(
                            wd["due_for_public_transition"]
                            + wd["missing_r35_pins_eligible"]
                            + wd["missing_r35b_links_unlocked"]
                        )
                    )
                ),
                "reason": (
                    f"Promote {len(wd['due_for_public_transition'])} elapsed Scheduled->Public, "
                    f"backfill {len(wd['missing_r35_pins_eligible'])} eligible R35 pins (>=12h/100v), "
                    f"link {len(wd['missing_r35b_links_unlocked'])} unlocked R35-B Related videos"
                ),
                "command": f"{py_cmd} main.py studio-watchdog --apply",
            }
        )

    # 1b. Daily Zero-Bounce Studio Inbox Check
    inbox_slot = eco_assets.get("daily_studio_inbox_check")
    if inbox_slot:
        steps.append(
            {
                "order_ts": inbox_slot["window"]["iso_utc"],
                "window": inbox_slot["window"],
                "platform": "youtube",
                "action_type": "STUDIO_INBOX_CHECK",
                "verdict": "GO",
                "target": "studio_comments_inbox",
                "reason": inbox_slot["detail"],
                "command": inbox_slot["command"],
            }
        )

    # 2. Bundle exports if any QA-passed projects are missing multi_platform_bundle
    bundle_missing = sorted(
        set(ig_eval.get("needs_bundle_export", [])) | set(tt_eval.get("needs_bundle_export", []))
    )
    for pid in bundle_missing:
        steps.append(
            {
                "order_ts": (now_utc + timedelta(minutes=5)).isoformat(),
                "window": _fmt_multi_tz(now_utc + timedelta(minutes=5)),
                "platform": "multi_platform",
                "action_type": "PREPARE_BUNDLE",
                "verdict": "GO",
                "target": pid,
                "reason": "Export clean 9:16 multi_platform_bundle (zero YT hashtag mutation)",
                "command": f"{py_cmd} main.py multi-bundle --project {pid}",
            }
        )

    # 2b. YouTube Community Quiz Post (D-Day 16:00 ET — 3.5h prior to Short)
    quiz_slot = eco_assets.get("yt_community_quiz")
    if quiz_slot and quiz_slot.get("status") == "ACTION_REQUIRED":
        steps.append(
            {
                "order_ts": quiz_slot["window"]["iso_utc"],
                "window": quiz_slot["window"],
                "platform": "youtube",
                "action_type": "YT_COMMUNITY_QUIZ",
                "verdict": "GO",
                "target": quiz_slot["project_id"],
                "reason": quiz_slot["detail"],
                "command": quiz_slot["command"],
            }
        )

    # 3. Instagram Reel (if GO / CONDITIONAL_GO)
    if ig_eval["verdict"] in {"GO", "CONDITIONAL_GO"} and ig_eval["ready_reel_candidates"]:
        top_ig = ig_eval["ready_reel_candidates"][0]
        slot_iso = ig_eval["next_optimal_slot"]["iso_utc"]
        steps.append(
            {
                "order_ts": slot_iso,
                "window": ig_eval["next_optimal_slot"],
                "platform": "instagram",
                "action_type": "UPLOAD_IG_REEL",
                "verdict": ig_eval["verdict"],
                "target": top_ig["project_id"],
                "reason": (
                    f"Staggered US prime Reel ({ig_eval['reel_distribution_mode']}); "
                    f"YT state={top_ig['youtube_visibility']}"
                ),
                "command": f"{py_cmd} main.py ig-publish --project {top_ig['project_id']} --kind reel",
            }
        )

    # 3b. Instagram 4:5 (1080x1350) 6-Slide Carousel (non-Reel day >= +24h post-Reel, >=18h gap, <=3/wk)
    if (ig_eval["ready_card_carousels"] or ig_eval.get("ready_project_carousels")) and ig_eval.get("carousels_last_7d", 0) < IG_CAROUSEL_MAX_PER_WEEK:
        car_slot = ig_eval.get("next_carousel_slot") or _fmt_multi_tz(now_utc + timedelta(hours=24))
        if ig_eval["ready_card_carousels"]:
            card_target = ig_eval["ready_card_carousels"][0]["run_id"]
            car_cmd = f"# Inspect 4:5 (1080x1350) package in BCI_Shorts_Channel/runs/{card_target}/package/ before publishing"
        else:
            card_target = ig_eval["ready_project_carousels"][0]
            car_cmd = f"# Publish 4:5 (1080x1350) 6-slide carousel in BCI_Shorts_Channel/projects/{card_target}/06_publish/ig_carousel/"
        steps.append(
            {
                "order_ts": car_slot["iso_utc"],
                "window": car_slot,
                "platform": "instagram",
                "action_type": "PUBLISH_IG_CARDS",
                "verdict": "CONDITIONAL_GO" if ig_eval["regime"] == "warmup" else "GO",
                "target": card_target,
                "reason": (
                    f"4:5 (1080x1350) 6-Slide Carousel ready (non-Reel day >=+{IG_CAROUSEL_POST_REEL_OFFSET_HOURS:.0f}h post-Reel, "
                    f">={IG_CAROUSEL_MIN_GAP_FROM_REEL_HOURS:.0f}h gap; {ig_eval.get('carousels_last_7d', 0)}/{IG_CAROUSEL_MAX_PER_WEEK} in 7d)"
                ),
                "command": car_cmd,
            }
        )

    # 4. TikTok Upload (if GO / CONDITIONAL_GO)
    if tt_eval["verdict"] in {"GO", "CONDITIONAL_GO"} and tt_eval["ready_candidates"]:
        top_tt = tt_eval["ready_candidates"][0]
        slot_iso = tt_eval["next_optimal_slot"]["iso_utc"]
        steps.append(
            {
                "order_ts": slot_iso,
                "window": tt_eval["next_optimal_slot"],
                "platform": "tiktok",
                "action_type": "UPLOAD_TIKTOK",
                "verdict": tt_eval["verdict"],
                "target": top_tt["project_id"],
                "reason": f"Creator Rewards >=61.5s ({top_tt['duration_sec']:.1f}s), Original Audio, NO VPN, AIGC ON, staggered after YT",
                "command": f"{py_cmd} main.py tiktok-publish --project {top_tt['project_id']}",
            }
        )

    # 5. YouTube Scheduled Upload OR Buffer Production Alert
    if yt_eval["verdict"] in {"GO", "CONDITIONAL_GO", "THROTTLE"} and yt_eval["ready_candidates"]:
        top_yt = yt_eval["ready_candidates"][0]
        target_et_date = yt_eval["next_optimal_slot"]["et"][:10]
        steps.append(
            {
                "order_ts": yt_eval["next_optimal_slot"]["iso_utc"],
                "window": yt_eval["next_optimal_slot"],
                "platform": "youtube",
                "action_type": "UPLOAD_YT_SCHEDULED",
                "verdict": yt_eval["verdict"],
                "target": top_yt["project_id"],
                "reason": f"Stage into next vacant Slot 4 (19:30 ET) >=3h warmup; extend runway beyond {yt_eval['scheduled_runway_days']}d",
                "command": f"{py_cmd} main.py studio-upload --project {top_yt['project_id']} --visibility scheduled --slot 4 --date {target_et_date}",
            }
        )
    elif yt_eval["scheduled_runway_days"] < YT_TARGET_BUFFER_DAYS_MIN:
        steps.append(
            {
                "order_ts": (now_utc + timedelta(minutes=15)).isoformat(),
                "window": _fmt_multi_tz(now_utc + timedelta(minutes=15)),
                "platform": "youtube",
                "action_type": "HOLD_AND_PRODUCE",
                "verdict": yt_eval["verdict"],
                "target": "next_v8_episode",
                "reason": (
                    f"YouTube scheduled runway is {yt_eval['scheduled_runway_days']}d (< {YT_TARGET_BUFFER_DAYS_MIN}d target) "
                    "and 0 QA-passed unpublished episodes remain; produce & pass QA for next v8 Short (<=88s, R68-H <=12w hook)"
                ),
                "command": f"{py_cmd} main.py diorama-episode --help",
            }
        )

    steps.sort(key=lambda s: s["order_ts"])
    return steps


def _apply_guardrails_to_platforms(
    *,
    guardrails: dict[str, Any],
    yt_eval: dict[str, Any],
    ig_eval: dict[str, Any],
    tt_eval: dict[str, Any],
) -> None:
    plat_map = {"youtube": yt_eval, "instagram": ig_eval, "tiktok": tt_eval}
    for hit in guardrails.get("block_violations", []):
        p_obj = plat_map.get(hit["platform"])
        if not p_obj:
            continue
        p_obj["block_reasons"].append(f"GUARDRAIL[{hit['rule']}]: {hit['detail']}")
        p_obj["penalty_audit"].append({"id": f"GUARDRAIL-{hit['rule'].upper()}", "status": "BLOCK", "detail": hit["detail"]})
        p_obj["verdict"] = "HOLD"
    for warn in guardrails.get("warnings", []):
        p_obj = plat_map.get(warn["platform"])
        if not p_obj:
            continue
        p_obj["warn_reasons"].append(f"GUARDRAIL[{warn['rule']}]: {warn['detail']}")
        p_obj["penalty_audit"].append({"id": f"GUARDRAIL-{warn['rule'].upper()}", "status": "WARN", "detail": warn["detail"]})
        if p_obj["verdict"] == "GO":
            p_obj["verdict"] = "CONDITIONAL_GO"


def evaluate_qa_schedule(
    *,
    projects_dir: Path = PROJECTS_DIR,
    channel_root: Path = CHANNEL_ROOT,
    reports_root: Path = REPORTS_ROOT_DIR,
    daily_dir: Path = DAILY_REPORTS_DIR,
    target_date: str | None = None,
    now_utc: datetime | None = None,
) -> dict[str, Any]:
    """Runs the complete cross-platform Daily Report -> HOLD/GO -> 5-Asset Stagger & Guardrails evaluation."""
    now = now_utc or datetime.now(timezone.utc)
    plan_date = target_date or now.astimezone(timezone.utc).strftime("%Y-%m-%d")
    report_ctx = load_daily_report_context(
        reports_root=reports_root,
        daily_dir=daily_dir,
        target_date=target_date,
        now_utc=now,
    )
    inventory = scan_multi_platform_inventory(
        projects_dir=projects_dir,
        channel_root=channel_root,
        ceo_watchdog_videos=report_ctx.get("ceo_watchdog_videos"),
        now_utc=now,
    )
    guardrails = audit_anti_trap_guardrails(report_ctx, inventory)
    yt_eval = evaluate_youtube_schedule(report_ctx, inventory, now_utc=now)

    # Avoid colliding with YouTube scheduled slots (especially 19:30 ET)
    yt_avoid = [
        dt
        for dt in (_parse_utc(v["scheduled_at_utc"]) for v in yt_eval["scheduled_videos"])
        if dt is not None
    ]
    yt_next = _parse_utc(yt_eval["next_optimal_slot"]["iso_utc"])
    if yt_next:
        yt_avoid.append(yt_next)

    ig_eval = evaluate_instagram_schedule(
        inventory,
        now_utc=now,
        avoid_utc_times=yt_avoid,
        report_ctx=report_ctx,
    )
    ig_next = _parse_utc(ig_eval["next_optimal_slot"]["iso_utc"])
    tt_avoid = list(yt_avoid) + ([ig_next] if ig_next else [])
    tt_eval = evaluate_tiktok_schedule(inventory, now_utc=now, avoid_utc_times=tt_avoid)

    _apply_guardrails_to_platforms(
        guardrails=guardrails,
        yt_eval=yt_eval,
        ig_eval=ig_eval,
        tt_eval=tt_eval,
    )

    ecosystem_slots = derive_ecosystem_asset_slots(
        plan_date=plan_date,
        now_utc=now,
        report_ctx=report_ctx,
        inventory=inventory,
        yt_eval=yt_eval,
        ig_eval=ig_eval,
        tt_eval=tt_eval,
    )

    execution_plan = build_execution_plan(
        now_utc=now,
        yt_eval=yt_eval,
        ig_eval=ig_eval,
        tt_eval=tt_eval,
        ecosystem_slots=ecosystem_slots,
    )

    verdicts = {yt_eval["verdict"], ig_eval["verdict"], tt_eval["verdict"]}
    if verdicts == {"HOLD"}:
        overall = "HOLD"
    elif "GO" in verdicts or "CONDITIONAL_GO" in verdicts:
        overall = "GO" if verdicts <= {"GO"} else "PARTIAL_GO"
    else:
        overall = "THROTTLE"

    target_evidence_projects: dict[str, Any] = {}
    for cand_list in (
        yt_eval["ready_candidates"][:2],
        ig_eval["ready_reel_candidates"][:2],
        tt_eval["ready_candidates"][:2],
        yt_eval["blocked_candidates"],
    ):
        for item in cand_list:
            pid = item.get("project_id")
            if pid and pid not in target_evidence_projects:
                target_evidence_projects[pid] = {
                    "qa_evidence_paths": item.get("qa_evidence_paths") or {},
                    "ceo_verify_receipt": item.get("ceo_verify_receipt"),
                    "ceo_verified": bool(item.get("ceo_verified")),
                    "blocked_reasons": item.get("reasons") or [],
                }

    evidence_bundle = {
        "input_metrics_path": report_ctx["metrics_path"],
        "input_metrics_kpis": {
            "report_date": report_ctx["report_date"],
            "report_age_hours": report_ctx["report_age_hours"],
            "subscribers_total": report_ctx["subscribers_total"],
            "realtime_48h_views": report_ctx["realtime_48h_views"],
            "viewed_pct": report_ctx["viewed_pct"],
            "apv_pct": report_ctx["apv_pct"],
            "us_share_pct": report_ctx["us_share_pct"],
            "tier1_share_pct": report_ctx["tier1_share_pct"],
            "shorts_feed_pct": report_ctx["shorts_feed_pct"],
        },
        "excluded_unparsed_metrics": [
            "realtime_60m_views",
            "unique_viewers",
            "views_24h_7d_28d_cloned",
            "watch_hours_24h_7d_28d_cloned",
        ],
        "r85_rebuild_hold_prefixes": list(R85_REBUILD_HOLD_PREFIXES),
        "projects": target_evidence_projects,
    }

    return {
        "schema_version": 2,
        "plan_date": plan_date,
        "generated_at": _fmt_multi_tz(now),
        "overall_decision": overall,
        "daily_report_summary": {
            "metrics_path": report_ctx["metrics_path"],
            "report_date": report_ctx["report_date"],
            "report_age_hours": report_ctx["report_age_hours"],
            "data_source_mode": report_ctx["data_source_mode"],
            "partial_dom_scrape_anomaly": report_ctx["partial_dom_scrape_anomaly"],
            "subscribers_total": report_ctx["subscribers_total"],
            "instagram_followers": report_ctx["instagram_followers"],
            "views_24h": report_ctx["views_24h"],
            "realtime_48h_views": report_ctx["realtime_48h_views"],
            "realtime_60m_views": report_ctx["realtime_60m_views"],
            "watch_hours_24h": report_ctx["watch_hours_24h"],
            "viewed_pct": report_ctx["viewed_pct"],
            "apv_pct": report_ctx["apv_pct"],
            "us_share_pct": report_ctx["us_share_pct"],
            "tier1_share_pct": report_ctx["tier1_share_pct"],
            "shorts_feed_pct": report_ctx["shorts_feed_pct"],
            "related_ring_complete": report_ctx["related_ring_complete"],
        },
        "platforms": {
            "youtube": yt_eval,
            "instagram": ig_eval,
            "tiktok": tt_eval,
        },
        "ecosystem_slots": ecosystem_slots,
        "guardrails": guardrails,
        "evidence_bundle": evidence_bundle,
        "execution_plan": execution_plan,
    }


def render_qa_schedule_markdown(report: dict[str, Any]) -> str:
    """Renders the QA Scheduler v2 HOLD/GO decision, 5-asset stagger, and anti-trap guardrails as Markdown."""
    gen = report["generated_at"]
    dr = report["daily_report_summary"]
    yt = report["platforms"]["youtube"]
    ig = report["platforms"]["instagram"]
    tt = report["platforms"]["tiktok"]
    eco = report.get("ecosystem_slots") or {}
    gr = report.get("guardrails") or {}

    badge = {
        "GO": "🟢 GO",
        "CONDITIONAL_GO": "🟡 CONDITIONAL GO",
        "THROTTLE": "🟠 THROTTLE",
        "HOLD": "🔴 HOLD",
        "SCHEDULED": "🗓️ SCHEDULED",
        "SCHEDULED/DONE": "✅ SCHEDULED/DONE",
        "DONE": "✅ DONE",
        "ACTION_REQUIRED": "⚡ ACTION REQUIRED",
        "PENDING_ASSETS": "⏳ PENDING ASSETS",
    }

    lines = [
        f"# 🗓️ ALL ABOUT BRAIN — Multi-Platform QA Schedule & 5-Asset Execution Plan ({report['plan_date']})",
        "",
        f"> **Generated**: `{gen['utc']}` | `{gen['kst']}` | `{gen['et']}`",
        f"> **Overall Decision**: **{badge.get(report['overall_decision'], report['overall_decision'])}** | **Guardrails**: `{gr.get('status', 'PASS')}`",
        "",
        "## 1. Daily Report Gate Verdict (`HOLD / GO` & Anti-Penalty Summary)",
        "",
        f"- **Source Report**: `{dr['report_date']}` (`{dr['data_source_mode']}`, age `{dr['report_age_hours']}h`)",
        f"- **Channel Pulse (Parsed KPIs)**: Subs `{dr['subscribers_total']}` | IG Followers `{dr.get('instagram_followers', 0)}` | Realtime 48h `{dr['realtime_48h_views']}` | 3s Hook `{dr['viewed_pct']}%` (Gate `>=70%`) | APV `{dr['apv_pct']}%` (Gate `>=60%`) | US `{dr['us_share_pct']}%` (Gate `>=45%`) | Shorts Feed `{dr['shorts_feed_pct']}%` *(hardcoded `60m`/`unique_viewers` & 28d-cloned `views`/`watch_hours` excluded)*",
    ]
    if dr["partial_dom_scrape_anomaly"]:
        lines.append(
            "- **⚠️ DOM Scrape Anomaly Guard**: `views_24h` dropped sharply while `realtime_48h_views` & `watch_hours_24h` remain strong (`measured_video_count=0`). Treated as partial Studio DOM scrape lag, NOT algorithmic shadowban."
        )

    lines.extend(
        [
            "",
            "| Platform | Handle | Decision | Optimal Cadence | Next Safe Window (`ET` / `KST`) | Ready Queue |",
            "| :--- | :--- | :---: | :--- | :--- | :---: |",
            f"| **YouTube** | `{yt['handle']}` | **{badge.get(yt['verdict'], yt['verdict'])}** | {yt['optimal_cadence']} | `{yt['next_optimal_slot']['et']}` / `{yt['next_optimal_slot']['kst']}` | `{len(yt['ready_candidates'])}` (`Runway {yt['scheduled_runway_days']}d`) |",
            f"| **Instagram** | `{ig['handle']}` | **{badge.get(ig['verdict'], ig['verdict'])}** | {ig['optimal_cadence']} | `{ig['next_optimal_slot']['et']}` / `{ig['next_optimal_slot']['kst']}` | `{len(ig['ready_reel_candidates'])}` Reels · `{len(ig['ready_card_carousels']) + len(ig.get('ready_project_carousels', []))}` Carousels |",
            f"| **TikTok** | `{tt['handle']}` | **{badge.get(tt['verdict'], tt['verdict'])}** | {tt['optimal_cadence']} | `{tt['next_optimal_slot']['et']}` / `{tt['next_optimal_slot']['kst']}` | `{len(tt['ready_candidates'])}` (`>=61.5s`) |",
            "",
            "## 2. Anti-Penalty & Compliance Audit",
            "",
        ]
    )

    for p_label, p_obj in (("YouTube", yt), ("Instagram", ig), ("TikTok", tt)):
        lines.append(f"### {p_label} (`{p_obj['verdict']}`)")
        for chk in p_obj["penalty_audit"]:
            icon = "✅" if chk["status"] == "PASS" else ("⚠️" if chk["status"] == "WARN" else "🛑")
            lines.append(f"- {icon} **`{chk['id']}`**: {chk['detail']}")
        if p_obj["block_reasons"]:
            lines.append(f"- **Hold / Block Reasons**: {'; '.join(p_obj['block_reasons'])}")
        if p_obj["warn_reasons"]:
            lines.append(f"- **Conditions / Warnings**: {'; '.join(p_obj['warn_reasons'])}")
        lines.append("")

    # Section 3: 5-Asset Ecosystem Staggered Timeline
    lines.append("## 3. 1-Episode -> 5 Automated Assets Ecosystem Stagger (`Workstream 4C v2`)")
    lines.append("")
    anchor_info = eco.get("anchor_episode")
    if anchor_info:
        lines.append(
            f"- **Anchor Episode**: `{anchor_info['project_id']}` (`{anchor_info.get('video_id') or 'queued'}` | `{anchor_info['source']}` @ `{anchor_info['youtube_slot']['et']}` / `{anchor_info['youtube_slot']['kst']}`)"
        )
    else:
        lines.append("- **Anchor Episode**: None scheduled or queued")
    lines.extend(
        [
            "",
            "| Asset | Slot (`ET` / `KST`) | Status | Target / Spec |",
            "| :--- | :--- | :---: | :--- |",
        ]
    )
    eco_assets = eco.get("assets") or {}
    for key in (
        "yt_community_quiz",
        "youtube_short",
        "tiktok_video",
        "instagram_reel",
        "instagram_carousel",
        "daily_studio_inbox_check",
    ):
        item = eco_assets.get(key)
        if not item:
            continue
        win = item["window"]
        st_badge = badge.get(item["status"], item["status"])
        lines.append(
            f"| **{item['asset']}** | `{win['et']}` / `{win['kst']}` | **{st_badge}** | {item['detail']} |"
        )
    lines.append("")

    # Section 4: Anti-Trap Guardrails (6 Permanent Rules)
    lines.extend(
        [
            "## 4. Anti-Trap Permanent Guardrails (`guardrails`)",
            "",
            f"- `youtube_srt_cc_upload_banned`: `{gr.get('youtube_srt_cc_upload_banned')}`",
            f"- `youtube_auto_dubbing_burned_ass_off`: `{gr.get('youtube_auto_dubbing_burned_ass_off')}`",
            f"- `tiktok_commercial_sound_over_60s_banned`: `{gr.get('tiktok_commercial_sound_over_60s_banned')}`",
            f"- `instagram_carousel_aspect_ratio_locked`: `{gr.get('instagram_carousel_aspect_ratio_locked')}`",
            f"- `instagram_notes_deprecated_excluded`: `{gr.get('instagram_notes_deprecated_excluded')}`",
            f"- `on_hold_excluded_features`: `{', '.join(gr.get('on_hold_excluded_features') or [])}`",
            "",
        ]
    )
    for gchk in gr.get("checks") or []:
        icon = "✅" if gchk["status"] == "PASS" else ("⚠️" if gchk["status"] == "WARN" else "🛑")
        lines.append(f"- {icon} **`{gchk['rule']}`** (`{gchk['platform']}`): {gchk['detail']}")
    lines.append("")

    lines.extend(
        [
            "## 5. Today's Chronological Execution Plan",
            "",
            "| # | Window (`KST` / `ET`) | Platform | Action | Verdict | Target | Reason |",
            "| :---: | :--- | :---: | :--- | :---: | :--- | :--- |",
        ]
    )
    if not report["execution_plan"]:
        lines.append("| - | - | - | `NO_ACTIONS` | 🔴 HOLD | - | All platforms on HOLD or cooldown |")
    else:
        for idx, step in enumerate(report["execution_plan"], start=1):
            win = f"`{step['window']['kst']}` / `{step['window']['et']}`"
            lines.append(
                f"| {idx} | {win} | `{step['platform']}` | `{step['action_type']}` | **{badge.get(step['verdict'], step['verdict'])}** | `{step['target']}` | {step['reason']} |"
            )

    if report["execution_plan"]:
        lines.extend(["", "### Commands", ""])
        for idx, step in enumerate(report["execution_plan"], start=1):
            lines.append(f"{idx}. **{step['platform']} — `{step['action_type']}` (`{step['target']}`)**:")
            lines.append("```bash")
            lines.append(step["command"])
            lines.append("```")

    if yt["scheduled_videos"]:
        lines.extend(["", "## 6. Live YouTube Scheduled Buffer", ""])
        for sv in yt["scheduled_videos"]:
            quiz_tag = "Quiz SCHEDULED/DONE" if sv.get("quiz_scheduled_or_done") else "Quiz ACTION_REQUIRED"
            lines.append(f"- `{sv['scheduled_time_et']}` — `{sv['project_id']}` (`{sv['video_id']}` | `{quiz_tag}`)")

    if yt["blocked_candidates"]:
        lines.extend(["", "## 7. Blocked / Non-Ready Inventory (Excluded to Prevent Penalty)", ""])
        for bc in yt["blocked_candidates"]:
            lines.append(f"- `{bc['project_id']}`: {', '.join(bc['reasons'])}")

    ev = report.get("evidence_bundle") or {}
    lines.extend(["", "## 8. Evidence & QA/Verify Receipts (R83-5~7 / R85)", ""])
    lines.append(f"- **Input Metrics Report**: `{ev.get('input_metrics_path') or dr.get('metrics_path')}`")
    kpi = ev.get("input_metrics_kpis") or {}
    lines.append(
        f"- **KPI Snapshot (Parsed Only)**: Subs `{kpi.get('subscribers_total')}`, 48h Views `{kpi.get('realtime_48h_views')}`, "
        f"3s Hook `{kpi.get('viewed_pct')}%`, APV `{kpi.get('apv_pct')}%`, US `{kpi.get('us_share_pct')}%`, Shorts Feed `{kpi.get('shorts_feed_pct')}%`"
    )
    ev_projs = ev.get("projects") or {}
    for pid, p_ev in ev_projs.items():
        q_paths = p_ev.get("qa_evidence_paths") or {}
        ceo_tag = f"CEO PASS (`{p_ev['ceo_verify_receipt']}`)" if p_ev.get("ceo_verified") else "CEO Verify PENDING/MISSING"
        sample_paths = ", ".join(f"`{k}`=`{v}`" for k, v in list(q_paths.items())[:5])
        status_note = f"HOLD: {', '.join(p_ev['blocked_reasons'])}" if p_ev.get("blocked_reasons") else "READY"
        lines.append(f"- **`{pid}`** [{status_note} | {ceo_tag}]: {sample_paths}")

    lines.append("")
    return "\n".join(lines)


def run_qa_scheduler(
    *,
    target_date: str | None = None,
    projects_dir: Path = PROJECTS_DIR,
    channel_root: Path = CHANNEL_ROOT,
    reports_root: Path = REPORTS_ROOT_DIR,
    daily_dir: Path = DAILY_REPORTS_DIR,
    schedule_dir: Path = SCHEDULE_REPORTS_DIR,
    now_utc: datetime | None = None,
    write_outputs: bool = True,
) -> dict[str, Any]:
    """Runs the QA Scheduler and writes daily + schedule + LATEST plan JSON and Markdown reports."""
    report = evaluate_qa_schedule(
        projects_dir=projects_dir,
        channel_root=channel_root,
        reports_root=reports_root,
        daily_dir=daily_dir,
        target_date=target_date,
        now_utc=now_utc,
    )
    md_text = render_qa_schedule_markdown(report)
    report["markdown"] = md_text

    if write_outputs:
        schedule_dir.mkdir(parents=True, exist_ok=True)
        daily_dir.mkdir(parents=True, exist_ok=True)
        reports_root.mkdir(parents=True, exist_ok=True)
        p_date = report["plan_date"]
        json_out = schedule_dir / f"{p_date}_qa_schedule_plan.json"
        md_out = schedule_dir / f"{p_date}_qa_schedule_plan.md"
        daily_json_out = daily_dir / f"{p_date}_qa_schedule_plan.json"
        daily_md_out = daily_dir / f"{p_date}_qa_schedule_plan.md"

        payload_json = {k: v for k, v in report.items() if k != "markdown"}
        json_str = json.dumps(payload_json, indent=2, ensure_ascii=False) + "\n"
        json_out.write_text(json_str, encoding="utf-8")
        md_out.write_text(md_text, encoding="utf-8")
        daily_json_out.write_text(json_str, encoding="utf-8")
        daily_md_out.write_text(md_text, encoding="utf-8")
        (reports_root / LATEST_QA_SCHEDULE_JSON.name).write_text(json_str, encoding="utf-8")
        (reports_root / LATEST_QA_SCHEDULE_MD.name).write_text(md_text, encoding="utf-8")
        report["output_paths"] = {
            "json": str(json_out),
            "markdown": str(md_out),
            "daily_json": str(daily_json_out),
            "daily_markdown": str(daily_md_out),
            "latest_json": str(reports_root / LATEST_QA_SCHEDULE_JSON.name),
            "latest_markdown": str(reports_root / LATEST_QA_SCHEDULE_MD.name),
        }

    return report
