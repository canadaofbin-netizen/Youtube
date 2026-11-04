"""
ALL ABOUT BRAIN — North American East-to-West Prime-Slot Timetable (`pipeline/studio/us_diorama_timetable.py`).

Applies `ZoneInfo("America/New_York")` (automatic EST/EDT DST handling) daily 1-Short/Day prime window starting
`2026-11-04`:
  - Mon–Sat: `19:30 ET` (`09:30 KST +1d` in EST — single daily Flagship Porcelain Diorama / Reenactment Short)
  - Sunday: `09:30 ET` (`16:9 Long-Form` CTV feature, 10h separated) + `19:30 ET` (`Flagship Porcelain Short`)

Hard invariants:
  - Strictly `1 Short / Day` at `19:30 ET` (`<= MAX_DAILY_SUBSCRIBER_NOTIFICATIONS`).
  - Refuses legacy `psych_*` projects unless `allow_legacy_psych=True` (`R34`).
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from pipeline.config import LONGFORM_PRODUCTION_PROFILE, MAX_DAILY_SUBSCRIBER_NOTIFICATIONS

US_EASTERN_TZ = ZoneInfo("America/New_York")
SEOUL_TZ = ZoneInfo("Asia/Seoul")
DEFAULT_US_TIMETABLE_CUTOVER = date(2026, 11, 4)

WEEKDAY_PRIME_SLOTS_ET: dict[int, list[dict[str, Any]]] = {
    0: [{"slot_code": "MON_PRIME", "hour": 19, "minute": 30, "preferred_format": "neuro_diorama", "notify_subs": True}],
    1: [{"slot_code": "TUE_PRIME", "hour": 19, "minute": 30, "preferred_format": "neuro_diorama", "notify_subs": True}],
    2: [{"slot_code": "WED_PRIME", "hour": 19, "minute": 30, "preferred_format": "neuro_diorama", "notify_subs": True}],
    3: [{"slot_code": "THU_PRIME", "hour": 19, "minute": 30, "preferred_format": "neuro_diorama", "notify_subs": True}],
    4: [{"slot_code": "FRI_PRIME", "hour": 19, "minute": 30, "preferred_format": "neuro_diorama", "notify_subs": True}],
    5: [{"slot_code": "SAT_PRIME", "hour": 19, "minute": 30, "preferred_format": "neuro_diorama", "notify_subs": True}],
    6: [
        {"slot_code": "SUN_CTV_LONG", "hour": 9, "minute": 30, "preferred_format": "longform_4k", "notify_subs": True},
        {"slot_code": "SUN_PRIME", "hour": 19, "minute": 30, "preferred_format": "neuro_diorama", "notify_subs": True},
    ],
}


def build_us_prime_timetable(
    episodes: list[dict[str, Any]],
    start_date: str | date = DEFAULT_US_TIMETABLE_CUTOVER,
    days: int = 31,
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

            if pref_fmt == "longform_4k":
                picked_i = next(
                    (
                        i
                        for i, e in enumerate(remaining)
                        if str(e.get("format_profile") or "") in ("longform_4k", LONGFORM_PRODUCTION_PROFILE)
                    ),
                    None,
                )
            else:
                picked_i = next(
                    (
                        i
                        for i, e in enumerate(remaining)
                        if str(e.get("format_profile") or "neuro_diorama") not in ("longform_4k", LONGFORM_PRODUCTION_PROFILE)
                    ),
                    None,
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
