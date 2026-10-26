"""
ALL ABOUT BRAIN - Bulk Unlisted Staging Buffer & 5-Slot Queue Manager
Organizes mass-produced Shorts projects into the North American 5-Slot daily timetable,
tracks Unlisted staging buffers, and automates scheduled releases.
"""

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from typing import Any

from pipeline.config import PROJECTS_DIR
from pipeline.prompt_quality_v5 import validate_production_v5
from pipeline.storage import ProjectStorage
from pipeline.studio.config import (
    DEFAULT_CDP_PORT,
    STAGING_QUEUE_FILE,
    get_pillar_default_slot,
    get_slot_info,
)
from pipeline.studio.short_linker import is_valid_youtube_video_id
from pipeline.studio.uploader import StudioUploader, resolve_project_video_path

LIVE_RECEIPT_STATUSES = frozenset({
    "uploaded",
    "published_public",
    "scheduled",
    "scheduled_public",
    "staged_unlisted",
    "uploaded_unlisted",
})


def is_live_youtube_receipt(receipt: dict[str, Any] | None) -> bool:
    """True when upload_receipt.json represents an active (non-deleted, non-dry-run) YouTube video."""
    if not isinstance(receipt, dict):
        return False
    status = str(receipt.get("status") or "").strip().lower()
    vid = str(receipt.get("video_id") or "").strip()
    if status not in LIVE_RECEIPT_STATUSES:
        return False
    return is_valid_youtube_video_id(vid)


def passes_v5_publish_gate(
    project_dir: Path,
    allow_legacy_v4: bool = False,
) -> tuple[bool, list[str]]:
    """
    Validates that an unpublished project satisfies Prompt System v5 (R18-V5) before Studio upload.
    Blocks legacy v4 projects (e.g., deleted_from_studio drafts) unless allow_legacy_v4=True.
    """
    if allow_legacy_v4:
        return True, []

    vp_path = project_dir / "03_visuals" / "visual_plan.json"
    prompts_path = project_dir / "03_visuals" / "flow_all_in_one_prompts.json"
    script_path = project_dir / "02_script" / "script.json"

    if not vp_path.exists() or not prompts_path.exists():
        return False, ["missing v5 visual_plan.json or flow_all_in_one_prompts.json"]

    try:
        plan = json.loads(vp_path.read_text(encoding="utf-8"))
        prompts_doc = json.loads(prompts_path.read_text(encoding="utf-8"))
        clips = prompts_doc.get("clips") or []
        if script_path.exists():
            narrations = json.loads(script_path.read_text(encoding="utf-8")).get("clip_narrations") or []
        else:
            narrations = [str(c.get("spoken_narration") or "") for c in clips]
        issues = validate_production_v5(plan, narrations, clips)
        return len(issues) == 0, issues
    except Exception as exc:
        return False, [f"v5 gate read error: {exc}"]


class StagingQueueManager:
    """
    Manages the bulk video Unlisted Staging Buffer.
    Dispatches dozens to hundreds of completed Shorts into the North American 5-Slot
    schedule to prevent audience cannibalization and maintain optimal algorithm momentum.
    """

    def __init__(
        self,
        queue_file: Path = STAGING_QUEUE_FILE,
        cdp_port: int = DEFAULT_CDP_PORT,
        projects_dir: Path | None = None,
    ):
        self.queue_file = queue_file
        self.cdp_port = cdp_port
        self.projects_dir = projects_dir or PROJECTS_DIR
        self.uploader = StudioUploader(cdp_port=cdp_port, projects_dir=self.projects_dir)

    def scan_ready_projects(
        self,
        allow_legacy_v4: bool = False,
        include_live: bool = False,
    ) -> list[dict[str, Any]]:
        """
        Scans projects/ for completed projects ready for staging/upload.
        - Resolves MP4 from 05_assembly/ or Completed_Psychology_100_Shorts/ archive.
        - Excludes already-live published/scheduled Shorts by default (R34 zero-duplicate).
        - Blocks legacy v4 unpublished projects unless allow_legacy_v4=True (R18-V5).
        """
        ready_projects: list[dict[str, Any]] = []
        if not self.projects_dir.exists():
            return ready_projects

        for p_dir in sorted(self.projects_dir.iterdir()):
            if not p_dir.is_dir():
                continue

            manifest_file = p_dir / "00_project_manifest.json"
            if not manifest_file.exists():
                continue

            try:
                if self.projects_dir == PROJECTS_DIR:
                    storage = ProjectStorage(p_dir.name)
                    manifest = storage.get_manifest()
                    metadata = storage.load_json("06_publish", "metadata.json")
                    upload_receipt = storage.load_json("06_publish", "upload_receipt.json")
                    ab_manifest = storage.load_json("06_publish", "ab_test_manifest.json")
                else:
                    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
                    pub_dir = p_dir / "06_publish"
                    metadata = json.loads((pub_dir / "metadata.json").read_text(encoding="utf-8")) if (pub_dir / "metadata.json").exists() else None
                    upload_receipt = json.loads((pub_dir / "upload_receipt.json").read_text(encoding="utf-8")) if (pub_dir / "upload_receipt.json").exists() else None
                    ab_manifest = json.loads((pub_dir / "ab_test_manifest.json").read_text(encoding="utf-8")) if (pub_dir / "ab_test_manifest.json").exists() else None
            except Exception:
                continue

            is_live = is_live_youtube_receipt(upload_receipt)
            if is_live and not include_live:
                continue

            vid_path = resolve_project_video_path(p_dir, p_dir.name)
            if vid_path is None:
                continue

            if not is_live:
                v5_ok, _ = passes_v5_publish_gate(p_dir, allow_legacy_v4=allow_legacy_v4)
                if not v5_ok:
                    continue

            pillar = (metadata or {}).get("pillar") or manifest.get("pillar", "bci_tech")
            title = metadata.get("title") if metadata else manifest.get("title", p_dir.name)

            ready_projects.append({
                "project_id": p_dir.name,
                "pillar": pillar,
                "title": title,
                "video_file": str(vid_path),
                "has_metadata": metadata is not None,
                "has_ab_manifest": ab_manifest is not None,
                "is_staged": is_live,
                "is_live": is_live,
                "upload_status": upload_receipt.get("status") if upload_receipt else "unuploaded",
                "video_id": upload_receipt.get("video_id") if upload_receipt else None,
                "recommended_slot": get_pillar_default_slot(pillar),
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
            "history": [],
        }

    def save_queue(self, queue_data: dict[str, Any]):
        """Saves staging_queue.json atomically."""
        queue_data["updated_at"] = datetime.now(timezone.utc).isoformat()
        self.queue_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.queue_file, "w", encoding="utf-8") as f:
            json.dump(queue_data, f, indent=2, ensure_ascii=False)

    def _collect_live_project_ids_and_archive_history(
        self,
        queue_data: dict[str, Any],
        cutoff_date_str: str | None = None,
    ) -> tuple[set[str], dict[tuple[str, int], dict[str, Any]]]:
        """
        Archives past/published items into queue_data['history'], preserves upcoming
        scheduled/staged slots on or after cutoff_date_str so their (date, slot_id)
        cannot be double-booked (R30-B), and returns (live_project_ids, occupied_future_slots).
        """
        live_ids: set[str] = set()
        occupied_slots: dict[tuple[str, int], dict[str, Any]] = {}
        history: list[dict[str, Any]] = list(queue_data.get("history") or [])
        hist_pids = {str(h.get("project_id") or "") for h in history if isinstance(h, dict)}

        future_statuses = {"scheduled", "scheduled_public", "staged", "queued_scheduled", "uploaded_unlisted", "staged_unlisted"}
        published_statuses = {"published", "published_public"}

        for prev in queue_data.get("scheduled_items") or []:
            if not isinstance(prev, dict):
                continue
            pid = str(prev.get("project_id") or "").strip()
            st = str(prev.get("status") or "").strip().lower()
            vid = str(prev.get("video_id") or "").strip()
            item_date = str(prev.get("date") or "").strip()
            slot_raw = prev.get("slot_id")

            is_live_item = bool(
                pid and (st in (published_statuses | future_statuses) or is_valid_youtube_video_id(vid))
            )
            if not is_live_item:
                continue

            live_ids.add(pid)
            is_future_booked = (
                st in future_statuses
                and bool(cutoff_date_str)
                and bool(item_date)
                and item_date >= str(cutoff_date_str)
                and slot_raw is not None
            )
            if is_future_booked:
                try:
                    occupied_slots[(item_date, int(slot_raw))] = dict(prev)
                    continue
                except (TypeError, ValueError):
                    pass

            if pid not in hist_pids:
                history.append(prev)
                hist_pids.add(pid)

        future_booked_pids = {str(v.get("project_id") or "") for v in occupied_slots.values()}

        if self.projects_dir.exists():
            for p_dir in sorted(self.projects_dir.iterdir()):
                if not p_dir.is_dir():
                    continue
                rec_path = p_dir / "06_publish" / "upload_receipt.json"
                if not rec_path.exists():
                    continue
                try:
                    rec = json.loads(rec_path.read_text(encoding="utf-8"))
                except Exception:
                    continue
                if is_live_youtube_receipt(rec):
                    live_ids.add(p_dir.name)
                    if p_dir.name not in hist_pids and p_dir.name not in future_booked_pids:
                        history.append({
                            "project_id": p_dir.name,
                            "video_id": rec.get("video_id"),
                            "shorts_url": rec.get("shorts_url"),
                            "title": rec.get("title"),
                            "status": rec.get("status"),
                            "scheduled_time_et": rec.get("scheduled_time_et"),
                        })
                        hist_pids.add(p_dir.name)

        queue_data["history"] = history
        return live_ids, occupied_slots

    def plan_5_slot_schedule(
        self,
        days: int = 7,
        start_date: str | None = None,
        project_ids: list[str] | None = None,
        daily_prime_only: bool = True,
        allow_legacy_v4: bool = False,
    ) -> dict[str, Any]:
        """
        Maps available completed projects into a clean 5-Slot (or 2-Prime-Slot) daily distribution.
        Guarantees zero duplicate scheduling (R34) and preserves upcoming booked slots so two Shorts
        never collide on the same timestamp (R30-B).
        """
        if not start_date:
            start_date_dt = datetime.now(timezone.utc) + timedelta(days=1)
        else:
            start_date_dt = datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        start_date_str = start_date_dt.strftime("%Y-%m-%d")

        queue_data = self.load_queue()
        live_ids, occupied_slots = self._collect_live_project_ids_and_archive_history(
            queue_data,
            cutoff_date_str=start_date_str,
        )

        projects = [
            p for p in self.scan_ready_projects(allow_legacy_v4=allow_legacy_v4, include_live=False)
            if p["project_id"] not in live_ids
        ]
        if project_ids:
            projects = [p for p in projects if p["project_id"] in project_ids]

        by_slot: dict[int, list[dict[str, Any]]] = {1: [], 2: [], 3: [], 4: [], 5: []}
        for proj in projects:
            slot = proj.get("recommended_slot", 2)
            by_slot[slot].append(proj)

        unassigned_pool = list(projects)
        assigned_ids: set[str] = {
            str(v.get("project_id")) for v in occupied_slots.values() if v.get("project_id")
        }
        planned_items: list[dict[str, Any]] = []
        emitted_keys: set[tuple[str, int]] = set()

        active_slots = (2, 4) if daily_prime_only else (1, 2, 3, 4, 5)
        for day_offset in range(days):
            current_date_dt = start_date_dt + timedelta(days=day_offset)
            date_str = current_date_dt.strftime("%Y-%m-%d")

            for slot_id in active_slots:
                key = (date_str, slot_id)
                emitted_keys.add(key)
                if key in occupied_slots:
                    planned_items.append(occupied_slots[key])
                    continue

                slot_info = get_slot_info(slot_id)
                assigned_proj = None

                while by_slot[slot_id]:
                    candidate = by_slot[slot_id].pop(0)
                    if candidate["project_id"] not in assigned_ids:
                        assigned_proj = candidate
                        break

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
                    "status": "planned" if assigned_proj else "vacant",
                }
                planned_items.append(item)

        # Preserve any already-booked future items beyond the horizon or on custom slots
        for key, booked in sorted(occupied_slots.items()):
            if key not in emitted_keys:
                planned_items.append(booked)

        queue_data["slots_per_day"] = len(active_slots)
        queue_data["scheduled_items"] = planned_items
        self.save_queue(queue_data)

        return {
            "planned_days": days,
            "start_date": start_date_str,
            "daily_prime_only": daily_prime_only,
            "total_slots": len(planned_items),
            "assigned_slots": sum(1 for item in planned_items if item.get("project_id")),
            "vacant_slots": sum(1 for item in planned_items if not item.get("project_id")),
            "preserved_live_count": len(live_ids),
            "preserved_future_slots": len(occupied_slots),
            "items": planned_items,
        }

    def enforce_seed_protection_window(
        self,
        min_interval_hours: float = 4.0,
        daily_prime_only: bool = True,
    ) -> dict[str, Any]:
        """
        Enforces seed-audience protection across scheduled items (R30-B):
        - Prevents simultaneous bulk releases that split the YouTube Shorts seed-audience test pool.
        - Ensures at least `min_interval_hours` (default 4.0h) between consecutive assigned slots.
        - When `daily_prime_only=True` (for channels < 10,000 subscribers), locks public
          scheduling to prime Slots 2 (12:00 ET) and 4 (20:00 ET).
        """
        slot_hours_map = {1: 7.5, 2: 12.0, 3: 16.0, 4: 20.0, 5: 22.5}
        queue_data = self.load_queue()
        items = queue_data.get("scheduled_items", [])
        assigned = sorted(
            [
                it for it in items
                if it.get("project_id")
                and str(it.get("status") or "").lower() not in {"published", "published_public"}
            ],
            key=lambda x: (str(x.get("date") or "2026-01-01"), slot_hours_map.get(int(x.get("slot_id", 2)), 12.0)),
        )

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
        project_ids: list[str] | None = None,
        allow_legacy_v4: bool = False,
        auto_link: bool = True,
        assign_playlist: bool = True,
    ) -> dict[str, Any]:
        """
        Uploads all planned unuploaded v5 projects to the YouTube Studio Staging Buffer
        as Unlisted or Scheduled. Never re-uploads already-live videos (R34).
        """
        queue_data = self.load_queue()
        items = queue_data.get("scheduled_items", [])
        if not items:
            self.plan_5_slot_schedule(days=7, project_ids=project_ids, allow_legacy_v4=allow_legacy_v4)
            queue_data = self.load_queue()
            items = queue_data.get("scheduled_items", [])

        staged_results: list[dict[str, Any]] = []
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

            p_dir = self.projects_dir / project_id
            storage = ProjectStorage(project_id) if self.projects_dir == PROJECTS_DIR else None
            receipt = (
                storage.load_json("06_publish", "upload_receipt.json")
                if storage
                else None
            )
            if is_live_youtube_receipt(receipt) and not dry_run:
                item["status"] = receipt.get("status", "staged")
                item["video_id"] = receipt.get("video_id")
                item["shorts_url"] = receipt.get("shorts_url")
                processed_project_ids.add(project_id)
                staged_results.append(receipt)
                continue

            v5_ok, v5_issues = passes_v5_publish_gate(p_dir, allow_legacy_v4=allow_legacy_v4)
            if not v5_ok:
                item["status"] = "blocked_legacy_v4"
                item["gate_issues"] = v5_issues[:3]
                continue

            print(f"\n[QueueManager] Staging Project: {project_id} -> Slot {item['slot_id']} ({item['target_time_et']})...")
            try:
                res = self.uploader.upload_project(
                    project_id=project_id,
                    slot_id=item["slot_id"],
                    target_date=item["date"],
                    visibility=visibility,
                    dry_run=(dry_run or quota_exhausted),
                    auto_link=auto_link,
                    assign_playlist=assign_playlist,
                )
                if res.get("quota_limit_reached"):
                    quota_exhausted = True
                elif quota_exhausted and not dry_run and storage:
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
            "staged_results": staged_results,
        }

    def get_status_summary(self, allow_legacy_v4: bool = False) -> dict[str, Any]:
        """Provides overview of staging inventory and scheduling status."""
        ready_projects = self.scan_ready_projects(allow_legacy_v4=allow_legacy_v4, include_live=False)
        all_with_live = self.scan_ready_projects(allow_legacy_v4=True, include_live=True)
        live_count = sum(1 for p in all_with_live if p.get("is_live"))
        queue_data = self.load_queue()
        items = [it for it in (queue_data.get("scheduled_items") or []) if isinstance(it, dict)]
        assigned_items = [
            it
            for it in items
            if str(it.get("project_id") or "").strip()
            and str(it.get("project_id") or "").strip().lower() not in {"none", "null"}
            and str(it.get("status") or "").strip().lower()
            not in {"vacant", "blocked_legacy_v4", "deleted", "deleted_from_studio", "dry_run_staged"}
        ]

        total_ready = len(ready_projects)
        total_staged = sum(1 for p in ready_projects if p["is_staged"])
        pending_staging = total_ready - total_staged

        return {
            "total_completed_projects": total_ready + live_count,
            "published_or_live_count": live_count,
            "v5_ready_unpublished_count": total_ready,
            "staged_in_buffer": total_staged,
            "pending_staging": pending_staging,
            "scheduled_slots_count": len(assigned_items),
            "vacant_slots_count": len(items) - len(assigned_items),
            "upcoming_planned_items": assigned_items[:10],
            "ready_projects": ready_projects,
        }
