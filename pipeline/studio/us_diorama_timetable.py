"""
ALL ABOUT BRAIN — North American East-to-West Prime-Slot Timetable (`pipeline/studio/us_diorama_timetable.py`).

Applies `ZoneInfo("America/New_York")` (automatic EST/EDT DST handling) day-of-week prime windows starting after
the existing `2026-11-13` live buffer:
  - Mon / Tue / Wed: `11:30 ET` (`Micro-Short` seed discovery) + `20:30 ET` (`Flagship Porcelain Diorama / Reenactment`)
  - Thu / Fri / Sat: `15:30 ET` (East afternoon + West lunch) + `21:00 ET` (US CTV & evening prime)
  - Sunday: `09:30 ET` (`16:9 4K Long-Form` CTV feature, or `Flagship Diorama` until Long-Form pilot is queued) + `19:30 ET` (`Flagship Diorama`)

Hard invariants:
  - Strictly `<= MAX_DAILY_SUBSCRIBER_NOTIFICATIONS` (`3`) uploads per 24h (`R30-B`).
  - Refuses legacy `psych_*` projects unless `allow_legacy_psych=True` (`R34`).
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from pipeline.config import MAX_DAILY_SUBSCRIBER_NOTIFICATIONS, MICRO_SHORT_PROFILE

US_EASTERN_TZ = ZoneInfo("America/New_York")
SEOUL_TZ = ZoneInfo("Asia/Seoul")
DEFAULT_US_TIMETABLE_CUTOVER = date(2026, 11, 14)

WEEKDAY_PRIME_SLOTS_ET: dict[int, list[dict[str, Any]]] = {
    # 0=Mon, 1=Tue, 2=Wed
    0: [
        {"slot_code": "MON_AM", "hour": 11, "minute": 30, "preferred_format": MICRO_SHORT_PROFILE, "notify_subs": False},
        {"slot_code": "MON_PM", "hour": 20, "minute": 30, "preferred_format": "neuro_diorama", "notify_subs": True},
    ],
    1: [
        {"slot_code": "TUE_AM", "hour": 11, "minute": 30, "preferred_format": MICRO_SHORT_PROFILE, "notify_subs": False},
        {"slot_code": "TUE_PM", "hour": 20, "minute": 30, "preferred_format": "neuro_diorama", "notify_subs": True},
    ],
    2: [
        {"slot_code": "WED_AM", "hour": 11, "minute": 30, "preferred_format": MICRO_SHORT_PROFILE, "notify_subs": False},
        {"slot_code": "WED_PM", "hour": 20, "minute": 30, "preferred_format": "neuro_diorama", "notify_subs": True},
    ],
    # 3=Thu, 4=Fri, 5=Sat
    3: [
        {"slot_code": "THU_AFT", "hour": 15, "minute": 30, "preferred_format": MICRO_SHORT_PROFILE, "notify_subs": False},
        {"slot_code": "THU_PRIME", "hour": 21, "minute": 0, "preferred_format": "neuro_diorama", "notify_subs": True},
    ],
    4: [
        {"slot_code": "FRI_AFT", "hour": 15, "minute": 30, "preferred_format": MICRO_SHORT_PROFILE, "notify_subs": False},
        {"slot_code": "FRI_PRIME", "hour": 21, "minute": 0, "preferred_format": "neuro_diorama", "notify_subs": True},
    ],
    5: [
        {"slot_code": "SAT_AFT", "hour": 15, "minute": 30, "preferred_format": MICRO_SHORT_PROFILE, "notify_subs": False},
        {"slot_code": "SAT_PRIME", "hour": 21, "minute": 0, "preferred_format": "neuro_diorama", "notify_subs": True},
    ],
    # 6=Sun
    6: [
        {"slot_code": "SUN_CTV_LONG", "hour": 9, "minute": 30, "preferred_format": "longform_4k", "notify_subs": True},
        {"slot_code": "SUN_PRIME", "hour": 19, "minute": 30, "preferred_format": "neuro_diorama", "notify_subs": True},
    ],
}


def build_us_prime_timetable(
    episodes: list[dict[str, Any]],
    start_date: str | date = DEFAULT_US_TIMETABLE_CUTOVER,
    days: int = 14,
    allow_legacy_psych: bool = False,
) -> dict[str, Any]:
    cur_date = date.fromisoformat(start_date) if isinstance(start_date, str) else start_date
    clean_eps: list[dict[str, Any]] = []
    for ep in episodes:
        pid = str(ep.get("project_id") or "")
        if pid.startswith("psych_") and not allow_legacy_psych:
            raise ValueError(f"Legacy psych_* project '{pid}' blocked from US v7 Prime Timetable (R34).")
        clean_eps.append(dict(ep))

    remaining = list(clean_eps)
    scheduled_slots: list[dict[str, Any]] = []

    for d_offset in range(max(1, int(days))):
        day = cur_date + timedelta(days=d_offset)
        day_specs = WEEKDAY_PRIME_SLOTS_ET[day.weekday()]
        if len(day_specs) > MAX_DAILY_SUBSCRIBER_NOTIFICATIONS:
            raise RuntimeError("Daily slot specification exceeds MAX_DAILY_SUBSCRIBER_NOTIFICATIONS")

        daily_notif_count = 0
        for s_idx, spec in enumerate(day_specs, start=1):
            dt_et = datetime.combine(day, time(int(spec["hour"]), int(spec["minute"])), tzinfo=US_EASTERN_TZ)
            dt_kst = dt_et.astimezone(SEOUL_TZ)
            pref_fmt = str(spec["preferred_format"])

            picked_i = next(
                (i for i, e in enumerate(remaining) if str(e.get("format_profile") or "neuro_diorama") == pref_fmt),
                0 if remaining else None,
            )
            chosen = remaining.pop(picked_i) if picked_i is not None else None
            notify = bool(spec.get("notify_subs")) and (daily_notif_count < MAX_DAILY_SUBSCRIBER_NOTIFICATIONS)
            if notify:
                daily_notif_count += 1

            scheduled_slots.append(
                {
                    "date": day.isoformat(),
                    "weekday": day.strftime("%a"),
                    "slot_index": s_idx,
                    "slot_code": spec["slot_code"],
                    "time_et": dt_et.strftime("%H:%M"),
                    "iso_et": dt_et.isoformat(),
                    "iso_kst": dt_kst.isoformat(),
                    "tz_abbr": dt_et.tzname() or "ET",
                    "preferred_format": pref_fmt,
                    "notify_subscribers": notify,
                    "project_id": chosen.get("project_id") if chosen else None,
                    "pillar": chosen.get("pillar") if chosen else None,
                }
            )

    return {
        "schema": "us_diorama_prime_timetable_v1",
        "start_date": cur_date.isoformat(),
        "days": int(days),
        "max_daily_notifications": MAX_DAILY_SUBSCRIBER_NOTIFICATIONS,
        "assigned_count": sum(1 for s in scheduled_slots if s["project_id"]),
        "total_slots": len(scheduled_slots),
        "slots": scheduled_slots,
    }
