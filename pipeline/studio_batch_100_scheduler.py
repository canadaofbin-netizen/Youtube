"""
ALL ABOUT BRAIN — 100-Video YouTube Studio Staging & 2-Per-Day Public Scheduler
-------------------------------------------------------------------------------
Implements Phase 3 of the 100-Video Production Plan:
- Maps all 100 projects (psych_01 .. psych_100) across 50 consecutive days at
  2 videos per day:
    * Video 1 of Day d -> Slot 2 (12:00 PM US ET / 02:00 AM KST+1)
    * Video 2 of Day d -> Slot 4 (07:30 PM US ET / 09:30 AM KST+1)
- Saves the complete 100-video schedule to BCI_Shorts_Channel/staging_queue.json.
- Uploads ready projects to YouTube Studio (@AllAboutBrainOfficial) with:
    * Private/Unlisted staging or Scheduled Public release at the assigned Slot 2 / Slot 4 date & time
    * R4 AI altered/synthetic content disclosure
    * R36 Two-Tier Localization lock (KR residence, en-US video & metadata language)
    * R31 9:16 custom thumbnail Variant A (plus first-frame burn-in fallback)
    * R35 Pinned academic DOI comment
"""

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from pipeline.config import PROJECTS_DIR
from pipeline.storage import ProjectStorage
from pipeline.studio.community import CommunityManager
from pipeline.studio.config import (
    DEFAULT_CDP_PORT,
    STAGING_QUEUE_FILE,
    get_slot_info,
)
from pipeline.studio.queue_manager import StagingQueueManager
from pipeline.studio.uploader import StudioUploader
from pipeline.topics_catalog import ALL_PSYCHOLOGY_100_TOPICS


def build_100_video_2_per_day_schedule(
    start_date: str | None = None,
    save_to_queue: bool = True,
) -> dict[str, Any]:
    """
    Assigns all 100 catalog projects (psych_01 .. psych_100) to 50 days × 2 slots/day
    (Slot 2: 12:00 PM ET, Slot 4: 07:30 PM ET).
    """
    if not start_date:
        start_dt = datetime.now(timezone.utc) + timedelta(days=1)
    else:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)

    daily_slots = [2, 4]  # 2 videos per day: 12:00 PM ET and 07:30 PM ET
    planned_items: list[dict[str, Any]] = []

    for idx, topic_obj in enumerate(ALL_PSYCHOLOGY_100_TOPICS[:100]):
        pid = topic_obj.get("project_id") or topic_obj.get("id")
        pillar = topic_obj["pillar"]
        day_offset = idx // 2
        slot_id = daily_slots[idx % 2]
        slot_info = get_slot_info(slot_id)

        cur_dt = start_dt + timedelta(days=day_offset)
        date_str = cur_dt.strftime("%Y-%m-%d")

        storage = ProjectStorage(pid)
        metadata = storage.load_json("06_publish", "metadata.json") or {}
        receipt = storage.load_json("06_publish", "upload_receipt.json")
        vid_path = storage.get_stage_dir("05_assembly") / "final_shorts_1080x1920.mp4"

        title = metadata.get("title") or topic_obj.get("topic") or pid
        item_status = "staged" if receipt else ("ready_to_stage" if vid_path.exists() else "awaiting_render")

        planned_items.append({
            "schedule_id": f"{date_str}_slot{slot_id}",
            "sequence_number": idx + 1,
            "day_number": day_offset + 1,
            "date": date_str,
            "slot_id": slot_id,
            "slot_name": slot_info["name"],
            "time_et": slot_info["time_et"],
            "time_et_12h": slot_info.get("time_et_12h", slot_info["time_et"]),
            "time_pt": slot_info["time_pt"],
            "time_kst": slot_info["time_kst"],
            "target_time_et": f"{date_str} {slot_info['time_et']} ET",
            "project_id": pid,
            "title": title,
            "pillar": pillar,
            "doi": topic_obj.get("source_doi", ""),
            "video_ready": vid_path.exists(),
            "status": item_status,
            "video_id": receipt.get("video_id") if receipt else None,
            "shorts_url": receipt.get("shorts_url") if receipt else None,
        })

    queue_payload = {
        "version": "2.0-100video-2perday",
        "channel_handle": "@AllAboutBrainOfficial",
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "slots_per_day": 2,
        "daily_slots_et": ["12:00", "19:30"],
        "total_days": 50,
        "total_videos": len(planned_items),
        "start_date": start_dt.strftime("%Y-%m-%d"),
        "end_date": (start_dt + timedelta(days=49)).strftime("%Y-%m-%d"),
        "scheduled_items": planned_items,
        "history": [],
    }

    if save_to_queue:
        STAGING_QUEUE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(STAGING_QUEUE_FILE, "w", encoding="utf-8") as f:
            json.dump(queue_payload, f, indent=2, ensure_ascii=False)

    return queue_payload


def upload_and_schedule_ready_batch(
    visibility: str = "scheduled",
    dry_run: bool = False,
    pin_comments: bool = True,
    cdp_port: int = DEFAULT_CDP_PORT,
) -> dict[str, Any]:
    """
    Uploads all ready projects in staging_queue.json to YouTube Studio as Private/Scheduled
    (releasing Public at 2 videos/day: 12:00 PM ET and 07:30 PM ET) and pins their DOI comments.
    """
    qm = StagingQueueManager(cdp_port=cdp_port)
    queue_data = qm.load_queue()
    if not queue_data.get("scheduled_items") or len(queue_data.get("scheduled_items", [])) < 100:
        queue_data = build_100_video_2_per_day_schedule(save_to_queue=True)

    uploader = StudioUploader(cdp_port=cdp_port)
    pinner = CommunityManager(cdp_port=cdp_port)

    items = queue_data.get("scheduled_items", [])
    results: list[dict[str, Any]] = []
    quota_exhausted = False

    for item in items:
        pid = item.get("project_id")
        if not pid:
            continue

        storage = ProjectStorage(pid)
        vid_path = storage.get_stage_dir("05_assembly") / "final_shorts_1080x1920.mp4"
        if not vid_path.exists():
            continue

        existing_receipt = storage.load_json("06_publish", "upload_receipt.json")
        if existing_receipt and existing_receipt.get("status") == "uploaded" and not dry_run:
            item["status"] = "scheduled_public"
            item["video_id"] = existing_receipt.get("video_id")
            item["shorts_url"] = existing_receipt.get("shorts_url")
            results.append(existing_receipt)
            continue

        print(
            f"\n[Batch100Scheduler] Uploading #{item.get('sequence_number')}/100: {pid} "
            f"-> {item['date']} Slot {item['slot_id']} ({item['target_time_et']}) [visibility={visibility}]"
        )
        try:
            receipt = uploader.upload_project(
                project_id=pid,
                slot_id=item["slot_id"],
                target_date=item["date"],
                visibility=visibility,
                dry_run=(dry_run or quota_exhausted),
                burn_first_frame=False,
            )
            if receipt.get("quota_limit_reached"):
                quota_exhausted = True
            elif quota_exhausted and not dry_run:
                receipt["quota_limit_reached"] = True
                receipt["quota_note"] = (
                    "YouTube Studio daily upload limit reached; staged in local schedule queue "
                    f"for {item['target_time_et']}"
                )
                storage.save_json("06_publish", "upload_receipt.json", receipt)

            item["status"] = "scheduled_public" if not receipt.get("quota_limit_reached") else "quota_staged_scheduled"
            item["video_id"] = receipt.get("video_id")
            item["shorts_url"] = receipt.get("shorts_url")
            results.append(receipt)

            if pin_comments:
                try:
                    pinner.pin_project_comment(
                        project_id=pid,
                        video_id=receipt.get("video_id"),
                        dry_run=(dry_run or quota_exhausted),
                    )
                except Exception as pe:
                    print(f"[Batch100Scheduler] Warning: DOI comment pin deferred for {pid}: {pe}")

        except Exception as e:
            print(f"[Batch100Scheduler] Error uploading {pid}: {e}")
            item["status"] = f"error: {str(e)[:80]}"

    qm.save_queue(queue_data)
    seed_audit = qm.enforce_seed_protection_window(min_interval_hours=4.0, daily_prime_only=True)

    return {
        "processed_count": len(results),
        "quota_exhausted": quota_exhausted,
        "seed_protection_audit": seed_audit,
        "queue_file": str(STAGING_QUEUE_FILE),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="100-Video 2-Per-Day YouTube Studio Scheduler")
    parser.add_argument("--plan-only", action="store_true", help="Generate the 50-day (2/day) schedule JSON only")
    parser.add_argument("--start-date", type=str, default=None, help="YYYY-MM-DD start date (default: tomorrow UTC)")
    parser.add_argument("--visibility", type=str, default="scheduled", choices=["scheduled", "private", "unlisted"])
    parser.add_argument("--dry-run", action="store_true", help="Run in dry-run staging mode")
    args = parser.parse_args()

    q = build_100_video_2_per_day_schedule(start_date=args.start_date, save_to_queue=True)
    print(
        f"[Batch100Scheduler] Built 50-day (2/day) schedule for {q['total_videos']} videos: "
        f"{q['start_date']} .. {q['end_date']} -> {STAGING_QUEUE_FILE}"
    )
    if args.plan_only:
        return 0

    summary = upload_and_schedule_ready_batch(
        visibility=args.visibility,
        dry_run=args.dry_run,
        pin_comments=True,
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
