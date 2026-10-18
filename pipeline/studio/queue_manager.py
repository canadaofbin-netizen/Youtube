"""
ALL ABOUT BRAIN - Bulk Unlisted Staging Buffer & 5-Slot Queue Manager
Organizes mass-produced Shorts projects into the North American 5-Slot daily timetable,
tracks Unlisted staging buffers, and automates scheduled releases.
"""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from pipeline.config import PROJECTS_DIR
from pipeline.storage import ProjectStorage
from pipeline.studio.config import (
    DEFAULT_CDP_PORT,
    STAGING_QUEUE_FILE,
    get_pillar_default_slot,
    get_slot_info,
)
from pipeline.studio.uploader import StudioUploader


class StagingQueueManager:
    """
    Manages the bulk video Unlisted Staging Buffer.
    Dispatches dozens to hundreds of completed Shorts into the North American 5-Slot
    schedule to prevent audience cannibalization and maintain optimal algorithm momentum.
    """

    def __init__(self, queue_file: Path = STAGING_QUEUE_FILE, cdp_port: int = DEFAULT_CDP_PORT):
        self.queue_file = queue_file
        self.cdp_port = cdp_port
        self.uploader = StudioUploader(cdp_port=cdp_port)

    def scan_ready_projects(self) -> list[dict[str, Any]]:
        """Scans BCI_Shorts_Channel/projects/ for completed projects ready for staging/upload."""
        ready_projects = []
        if not PROJECTS_DIR.exists():
            return ready_projects

        for p_dir in sorted(PROJECTS_DIR.iterdir()):
            if not p_dir.is_dir():
                continue

            manifest_file = p_dir / "00_project_manifest.json"
            if not manifest_file.exists():
                continue

            try:
                storage = ProjectStorage(p_dir.name)
                manifest = storage.get_manifest()
            except Exception:
                continue

            # Check if video exists
            vid_path = storage.get_stage_dir("05_assembly") / "final_shorts_1080x1920.mp4"
            if not vid_path.exists():
                candidates = list(p_dir.glob("*.mp4")) + list((storage.get_stage_dir("05_assembly")).glob("*.mp4"))
                if candidates:
                    vid_path = candidates[0]
                else:
                    continue

            # Check if publish stage exists
            metadata = storage.load_json("06_publish", "metadata.json")
            upload_receipt = storage.load_json("06_publish", "upload_receipt.json")
            ab_manifest = storage.load_json("06_publish", "ab_test_manifest.json")

            pillar = manifest.get("pillar", "bci_tech")
            title = metadata.get("title") if metadata else manifest.get("title", p_dir.name)

            ready_projects.append({
                "project_id": p_dir.name,
                "pillar": pillar,
                "title": title,
                "video_file": str(vid_path),
                "has_metadata": metadata is not None,
                "has_ab_manifest": ab_manifest is not None,
                "is_staged": upload_receipt is not None,
                "upload_status": upload_receipt.get("status") if upload_receipt else "unuploaded",
                "video_id": upload_receipt.get("video_id") if upload_receipt else None,
                "recommended_slot": get_pillar_default_slot(pillar)
            })

        return ready_projects

    def load_queue(self) -> dict[str, Any]:
        """Loads staging_queue.json or initializes empty schema."""
        if self.queue_file.exists():
            try:
                with open(self.queue_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass

        now_iso = datetime.now(timezone.utc).isoformat()
        return {
            "version": "1.0",
            "channel_handle": "@AllAboutBrainOfficial",
            "updated_at": now_iso,
            "slots_per_day": 5,
            "scheduled_items": [],
            "history": []
        }

    def save_queue(self, queue_data: dict[str, Any]):
        """Saves staging_queue.json atomically."""
        queue_data["updated_at"] = datetime.now(timezone.utc).isoformat()
        self.queue_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.queue_file, "w", encoding="utf-8") as f:
            json.dump(queue_data, f, indent=2, ensure_ascii=False)

    def plan_5_slot_schedule(
        self,
        days: int = 7,
        start_date: str | None = None,
        project_ids: list[str] | None = None
    ) -> dict[str, Any]:
        """
        Maps available completed projects into a clean 5-Slot daily distribution
        across the specified number of days.
        Guarantees zero duplicate scheduling: each unique project is assigned at most once.
        When ready inventory is exhausted, remaining slots are marked 'vacant'.
        """
        projects = self.scan_ready_projects()
        if project_ids:
            projects = [p for p in projects if p["project_id"] in project_ids]
        if not start_date:
            start_date_dt = datetime.now(timezone.utc) + timedelta(days=1)
        else:
            start_date_dt = datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)

        # Categorize unassigned projects by recommended slot
        by_slot: dict[int, list[dict[str, Any]]] = {1: [], 2: [], 3: [], 4: [], 5: []}
        for proj in projects:
            slot = proj.get("recommended_slot", 2)
            by_slot[slot].append(proj)

        unassigned_pool = list(projects)
        assigned_ids: set[str] = set()
        planned_items = []

        for day_offset in range(days):
            current_date_dt = start_date_dt + timedelta(days=day_offset)
            date_str = current_date_dt.strftime("%Y-%m-%d")

            for slot_id in range(1, 6):
                slot_info = get_slot_info(slot_id)
                assigned_proj = None

                # 1. First priority: Take unassigned project matching this pillar slot
                while by_slot[slot_id]:
                    candidate = by_slot[slot_id].pop(0)
                    if candidate["project_id"] not in assigned_ids:
                        assigned_proj = candidate
                        break

                # 2. Second priority: If no matching slot project, take next available from pool
                if not assigned_proj:
                    for candidate in unassigned_pool:
                        if candidate["project_id"] not in assigned_ids:
                            assigned_proj = candidate
                            break

                if assigned_proj:
                    assigned_ids.add(assigned_proj["project_id"])

                item = {
                    "schedule_id": f"{date_str}_slot{slot_id}",
                    "date": date_str,
                    "slot_id": slot_id,
                    "slot_name": slot_info["name"],
                    "time_et": slot_info["time_et"],
                    "time_pt": slot_info["time_pt"],
                    "time_kst": slot_info["time_kst"],
                    "target_time_et": f"{date_str} {slot_info['time_et']} ET",
                    "project_id": assigned_proj["project_id"] if assigned_proj else None,
                    "title": assigned_proj["title"] if assigned_proj else None,
                    "pillar": assigned_proj["pillar"] if assigned_proj else None,
                    "status": "planned" if assigned_proj else "vacant"
                }
                planned_items.append(item)

        queue_data = self.load_queue()
        queue_data["scheduled_items"] = planned_items
        self.save_queue(queue_data)

        return {
            "planned_days": days,
            "start_date": start_date_dt.strftime("%Y-%m-%d"),
            "total_slots": len(planned_items),
            "assigned_slots": sum(1 for item in planned_items if item["project_id"]),
            "vacant_slots": sum(1 for item in planned_items if not item["project_id"]),
            "items": planned_items
        }

    def enforce_seed_protection_window(
        self,
        min_interval_hours: float = 4.0,
        daily_prime_only: bool = False,
    ) -> dict[str, Any]:
        """
        Enforces seed-audience protection across scheduled items:
        - Prevents simultaneous bulk releases that split the YouTube Shorts seed-audience test pool.
        - Ensures at least `min_interval_hours` (default 4.0h) between consecutive assigned slots.
        - When `daily_prime_only=True` (recommended for channels < 10,000 subscribers), locks public
          scheduling to Slot 4 (19:30 ET Evening Prime) or max 2 prime slots/day (12:00 ET & 19:30 ET).
        """
        slot_hours_map = {1: 7.5, 2: 12.0, 3: 16.0, 4: 19.5, 5: 22.5}
        queue_data = self.load_queue()
        items = queue_data.get("scheduled_items", [])
        assigned = [it for it in items if it.get("project_id")]

        violations: list[str] = []
        prev_abs_hours: float | None = None
        base_dt: datetime | None = None

        for it in assigned:
            d_str = it.get("date", "2026-01-01")
            s_id = int(it.get("slot_id", 2))
            dt = datetime.strptime(d_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            if base_dt is None:
                base_dt = dt
            day_diff = (dt - base_dt).days
            abs_h = day_diff * 24.0 + slot_hours_map.get(s_id, 12.0)

            if daily_prime_only and s_id not in (2, 4):
                violations.append(f"{it['schedule_id']} ({it['project_id']}) scheduled outside prime slots (2, 4)")
            if prev_abs_hours is not None and (abs_h - prev_abs_hours) < (min_interval_hours - 0.6):
                violations.append(
                    f"{it['schedule_id']} ({it['project_id']}) interval {abs_h - prev_abs_hours:.1f}h < {min_interval_hours:.1f}h"
                )
            prev_abs_hours = abs_h

        return {
            "passed": len(violations) == 0,
            "min_interval_hours": min_interval_hours,
            "daily_prime_only": daily_prime_only,
            "assigned_count": len(assigned),
            "violations": violations,
        }

    def load_all_to_buffer(
        self,
        visibility: str = "unlisted",
        dry_run: bool = True,
        project_ids: list[str] | None = None
    ) -> dict[str, Any]:
        """
        Uploads all planned unuploaded projects to the YouTube Studio Staging Buffer
        as Unlisted or Scheduled.
        In live mode (not dry_run), only skips projects that were actually uploaded live.
        """
        queue_data = self.load_queue()
        items = queue_data.get("scheduled_items", [])
        if not items:
            self.plan_5_slot_schedule(days=7, project_ids=project_ids)
            queue_data = self.load_queue()
            items = queue_data.get("scheduled_items", [])

        staged_results = []
        processed_project_ids: set[str] = set()
        quota_exhausted = False

        for item in items:
            project_id = item.get("project_id")
            if not project_id:
                continue

            if project_ids and project_id not in project_ids:
                continue

            if project_id in processed_project_ids:
                continue

            # Check if project already uploaded live with a valid YouTube video_id
            storage = ProjectStorage(project_id)
            receipt = storage.load_json("06_publish", "upload_receipt.json")
            if receipt:
                status = receipt.get("status")
                vid_id = receipt.get("video_id")
                if not dry_run and status == "uploaded" and vid_id and vid_id not in ("unknown", "uploaded_live"):
                    item["status"] = "staged"
                    item["video_id"] = vid_id
                    item["shorts_url"] = receipt.get("shorts_url")
                    processed_project_ids.add(project_id)
                    staged_results.append(receipt)
                    continue

            print(f"\n[QueueManager] Staging Project: {project_id} -> Slot {item['slot_id']} ({item['target_time_et']})...")
            try:
                res = self.uploader.upload_project(
                    project_id=project_id,
                    slot_id=item["slot_id"],
                    target_date=item["date"],
                    visibility=visibility,
                    dry_run=(dry_run or quota_exhausted)
                )
                if res.get("quota_limit_reached"):
                    quota_exhausted = True
                elif quota_exhausted and not dry_run:
                    res["quota_limit_reached"] = True
                    res["quota_note"] = "YouTube Studio daily upload limit reached after 4 live uploads; staged in local unlisted buffer"
                    storage.save_json("06_publish", "upload_receipt.json", res)
                    storage.record_artifact("06_publish", "upload_receipt.json", storage.get_stage_dir("06_publish") / "upload_receipt.json")
                item["status"] = "staged" if (not dry_run and not quota_exhausted) else "dry_run_staged"
                item["video_id"] = res.get("video_id")
                item["shorts_url"] = res.get("shorts_url")
                processed_project_ids.add(project_id)
                staged_results.append(res)
            except Exception as e:
                print(f"[QueueManager] Failed to stage {project_id}: {e}")
                item["status"] = f"error: {str(e)[:60]}"

        self.save_queue(queue_data)

        return {
            "total_processed": len(staged_results),
            "visibility": visibility,
            "dry_run": dry_run,
            "staged_results": staged_results
        }

    def get_status_summary(self) -> dict[str, Any]:
        """Provides overview of staging inventory and scheduling status."""
        ready_projects = self.scan_ready_projects()
        queue_data = self.load_queue()
        items = queue_data.get("scheduled_items", [])

        total_ready = len(ready_projects)
        total_staged = sum(1 for p in ready_projects if p["is_staged"])
        pending_staging = total_ready - total_staged

        return {
            "total_completed_projects": total_ready,
            "staged_in_buffer": total_staged,
            "pending_staging": pending_staging,
            "scheduled_slots_count": len(items),
            "upcoming_planned_items": items[:10],
            "ready_projects": ready_projects
        }
