"""
ALL ABOUT BRAIN — Autonomous Studio Go-Live Watchdog (`studio-watchdog`)
-------------------------------------------------------------------------
Monitors `Scheduled -> Public` transitions across `BCI_Shorts_Channel/projects/*/06_publish/`
(and live YouTube watch/Studio status when `--live-check` is enabled):
1. Detects any newly-public Short lacking a verified `community_receipt.json` (`pinned == True`)
   and immediately stages/posts + pins its mobile-first R35 DOI comment (`studio-pin`).
2. Detects any Short lacking a verified `related_video_receipt.json` and runs
   `StudioShortLinker` (`public_targets_only=True`, non-destructive `merge_existing=True`).
3. Audits `staging_queue.json` for broken/duplicate schedule entries.
4. Cleans up idle headless/temporary Naver Whale `about:blank` or closed Studio edit tabs
   while NEVER touching user tabs or active Google Flow / YouTube Studio dashboard tabs.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pipeline.config import CHANNEL_ROOT, PROJECTS_DIR
from pipeline.studio.community import CommunityManager
from pipeline.studio.config import DEFAULT_CDP_PORT, SHORT_LINK_GRAPH_FILE, STAGING_QUEUE_FILE
from pipeline.studio.short_linker import (
    StudioShortLinker,
    is_valid_youtube_video_id,
    normalize_visibility,
    write_studio_publish_receipt,
)


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _parse_iso_utc(raw: str | None) -> datetime | None:
    if not raw:
        return None
    s = str(raw).strip()
    if not s:
        return None
    try:
        if s.endswith("Z"):
            return datetime.fromisoformat(s[:-1] + "+00:00").astimezone(timezone.utc)
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def scan_go_live_transitions(
    *,
    projects_dir: Path | None = None,
    now_utc: datetime | None = None,
) -> dict[str, Any]:
    """
    Scans all project `06_publish/` directories to identify:
    - Scheduled videos whose `scheduled_at_utc` has already passed (`due_for_public_transition`)
    - Public videos missing `community_receipt.json` (`pinned == True`) (`missing_doi_pin`)
    - Public/Scheduled videos missing `related_video_receipt.json` (`verified == True`) (`missing_related_link`)
    """
    p_root = projects_dir or PROJECTS_DIR
    now = now_utc or datetime.now(timezone.utc)

    due_transitions: list[dict[str, Any]] = []
    missing_pins: list[dict[str, Any]] = []
    missing_links: list[dict[str, Any]] = []
    public_count = 0
    scheduled_count = 0

    if not p_root.exists():
        return {
            "scanned_at_utc": now.isoformat(),
            "public_count": 0,
            "scheduled_count": 0,
            "due_for_public_transition": [],
            "missing_doi_pin": [],
            "missing_related_link": [],
        }

    for p_dir in sorted(p_root.iterdir()):
        if not p_dir.is_dir():
            continue
        pid = p_dir.name
        pub_dir = p_dir / "06_publish"
        upload_rec = _load_json(pub_dir / "upload_receipt.json")
        if not upload_rec:
            continue
        vid = str(upload_rec.get("video_id") or "").strip()
        if not is_valid_youtube_video_id(vid):
            continue

        vis = normalize_visibility(upload_rec)
        sched_dt = _parse_iso_utc(
            upload_rec.get("scheduled_at_utc") or upload_rec.get("published_at_utc")
        )
        effective_public = vis == "public"
        if vis == "scheduled" and sched_dt and sched_dt <= now:
            due_transitions.append({
                "project_id": pid,
                "video_id": vid,
                "scheduled_at_utc": sched_dt.isoformat(),
            })
            effective_public = True

        if effective_public:
            public_count += 1
        elif vis == "scheduled":
            scheduled_count += 1

        comm_rec = _load_json(pub_dir / "community_receipt.json")
        rel_rec = _load_json(pub_dir / "related_video_receipt.json")

        if effective_public and not bool(comm_rec.get("pinned")):
            missing_pins.append({
                "project_id": pid,
                "video_id": vid,
                "visibility": "public" if vis == "public" else "scheduled_elapsed",
            })

        if vis in {"public", "scheduled"} and not bool(rel_rec.get("verified")):
            missing_links.append({
                "project_id": pid,
                "video_id": vid,
                "visibility": "public" if effective_public else vis,
            })

    return {
        "scanned_at_utc": now.isoformat(),
        "public_count": public_count,
        "scheduled_count": scheduled_count,
        "due_for_public_transition": due_transitions,
        "missing_doi_pin": missing_pins,
        "missing_related_link": missing_links,
    }


def audit_staging_queue_integrity(
    *,
    queue_file: Path | None = None,
    projects_dir: Path | None = None,
) -> dict[str, Any]:
    """Audits staging_queue.json for duplicate video_ids, duplicate slots, or missing receipts."""
    q_path = queue_file or STAGING_QUEUE_FILE
    p_root = projects_dir or PROJECTS_DIR
    doc = _load_json(q_path)
    items = list(doc.get("scheduled_items") or [])
    seen_pids: set[str] = set()
    seen_slots: set[str] = set()
    duplicate_projects: list[str] = []
    duplicate_slots: list[str] = []
    legacy_psych_items: int = 0

    for item in items:
        if not isinstance(item, dict):
            continue
        pid = str(item.get("project_id") or "").strip()
        slot_key = f"{item.get('date')}_{item.get('slot_id')}"
        if pid:
            if pid in seen_pids:
                duplicate_projects.append(pid)
            seen_pids.add(pid)
            if pid.startswith("psych_"):
                legacy_psych_items += 1
        if item.get("date") and item.get("slot_id") and item.get("status") in {"scheduled", "scheduled_public", "ready_to_stage"}:
            if slot_key in seen_slots:
                duplicate_slots.append(slot_key)
            seen_slots.add(slot_key)

    return {
        "queue_exists": q_path.exists(),
        "total_items": len(items),
        "duplicate_projects": duplicate_projects,
        "duplicate_slots": duplicate_slots,
        "legacy_psych_items": legacy_psych_items,
        "healthy": len(duplicate_projects) == 0 and len(duplicate_slots) == 0,
        "projects_dir_exists": p_root.exists(),
    }


def cleanup_idle_whale_tabs(
    *,
    cdp_port: int = DEFAULT_CDP_PORT,
    dry_run: bool = True,
) -> dict[str, Any]:
    """
    Safely inspects Naver Whale `/json/list` and closes ONLY idle `about:blank` page targets or
    duplicate stale `studio.youtube.com/video/<id>/edit` tabs (keeping at most 1 Studio tab and NEVER
    touching user websites, Google Flow tabs, or the Studio dashboard).
    """
    import urllib.request

    base_url = f"http://127.0.0.1:{int(cdp_port)}"
    try:
        with urllib.request.urlopen(f"{base_url}/json/list", timeout=2.0) as resp:
            targets = json.loads(resp.read().decode("utf-8"))
    except Exception:
        return {"cdp_reachable": False, "candidates": [], "closed": []}

    if not isinstance(targets, list):
        return {"cdp_reachable": False, "candidates": [], "closed": []}

    page_tabs = [t for t in targets if isinstance(t, dict) and str(t.get("type") or "") == "page"]
    studio_edit_tabs = [
        t
        for t in page_tabs
        if "studio.youtube.com/video/" in str(t.get("url") or "") and "/edit" in str(t.get("url") or "")
    ]
    blank_tabs = [
        t
        for t in page_tabs
        if str(t.get("url") or "").strip() in {"about:blank", "chrome://newtab/", "whale://newtab/"}
    ]

    # Always leave at least 1 page tab open in the browser window; keep the newest Studio edit tab if no dashboard exists
    close_candidates: list[dict[str, str]] = []
    if len(page_tabs) > 1:
        for bt in blank_tabs:
            if len(page_tabs) - len(close_candidates) <= 1:
                break
            tid = str(bt.get("id") or "").strip()
            if tid:
                close_candidates.append({"id": tid, "url": str(bt.get("url") or ""), "reason": "idle_blank_tab"})
        for st in studio_edit_tabs[1:]:
            if len(page_tabs) - len(close_candidates) <= 1:
                break
            tid = str(st.get("id") or "").strip()
            if tid:
                close_candidates.append({"id": tid, "url": str(st.get("url") or ""), "reason": "duplicate_studio_edit_tab"})

    closed_ids: list[str] = []
    if not dry_run:
        for cand in close_candidates:
            try:
                with urllib.request.urlopen(f"{base_url}/json/close/{cand['id']}", timeout=2.0):
                    closed_ids.append(cand["id"])
            except Exception:
                pass

    return {
        "cdp_reachable": True,
        "candidates": close_candidates,
        "closed": closed_ids,
    }


def run_studio_watchdog(
    *,
    projects_dir: Path | None = None,
    graph_file: Path | None = None,
    queue_file: Path | None = None,
    cdp_port: int = DEFAULT_CDP_PORT,
    dry_run: bool = True,
    apply_pins: bool = True,
    apply_links: bool = True,
    promote_elapsed_receipts: bool = True,
    cleanup_tabs: bool = True,
    now_utc: datetime | None = None,
) -> dict[str, Any]:
    """
    Executes one autonomous Studio Watchdog pass:
    - Promotes elapsed `Scheduled` receipts to `published_public` locally when `promote_elapsed_receipts` is True
      and `not dry_run`
    - Runs R35 DOI comment pinning on newly-public Shorts missing `pinned == True`
    - Runs non-destructive R35-B `StudioShortLinker` (`public_targets_only=True`) on unlinked Shorts
    - Audits `staging_queue.json`
    - Cleans up idle `about:blank` and duplicate stale Studio edit tabs when `cleanup_tabs` is True
    """
    p_root = projects_dir or PROJECTS_DIR
    g_file = graph_file or SHORT_LINK_GRAPH_FILE
    now = now_utc or datetime.now(timezone.utc)

    scan = scan_go_live_transitions(projects_dir=p_root, now_utc=now)
    promoted: list[str] = []
    if promote_elapsed_receipts and not dry_run:
        for tr in scan["due_for_public_transition"]:
            pid = tr["project_id"]
            rec_path = p_root / pid / "06_publish" / "upload_receipt.json"
            rec = _load_json(rec_path)
            if rec:
                rec["visibility"] = "public"
                rec["status"] = "published_public"
                rec.setdefault("published_at_utc", tr["scheduled_at_utc"])
                rec["watchdog_promoted_at_utc"] = now.isoformat()
                rec_path.write_text(json.dumps(rec, indent=2, ensure_ascii=False), encoding="utf-8")
                write_studio_publish_receipt(pid, projects_dir=p_root)
                promoted.append(pid)

    pin_results: list[dict[str, Any]] = []
    if apply_pins and scan["missing_doi_pin"]:
        cm = CommunityManager(cdp_port=cdp_port, projects_dir=p_root)
        for item in scan["missing_doi_pin"]:
            pid = item["project_id"]
            vid = item["video_id"]
            if dry_run:
                staged = cm.prepare_comment_content(pid)
                pin_results.append({
                    "project_id": pid,
                    "video_id": vid,
                    "status": "dry_run_prepared",
                    "first_line": staged["comment_text"].splitlines()[0] if staged.get("comment_text") else "",
                    "doi_link": staged.get("doi_link", ""),
                })
            else:
                try:
                    res = cm.post_and_pin_comment(project_id=pid, video_id=vid, dry_run=False)
                    pin_results.append(res)
                except Exception as exc:
                    pin_results.append({
                        "project_id": pid,
                        "video_id": vid,
                        "status": f"error:{str(exc)[:120]}",
                        "pinned": False,
                    })

    link_results: list[dict[str, Any]] = []
    if apply_links and scan["missing_related_link"]:
        linker = StudioShortLinker(
            cdp_port=cdp_port,
            projects_dir=p_root,
            graph_file=g_file,
        )
        for item in scan["missing_related_link"]:
            pid = item["project_id"]
            plan_res = linker.run(
                mode="seed_boost",
                assign_playlists=True,
                dry_run=dry_run,
                force=False,
                project_id=pid,
                public_targets_only=True,
            )
            exec_list = plan_res.get("execution_results") or []
            if exec_list:
                link_results.extend(exec_list)
            else:
                link_results.append({
                    "project_id": pid,
                    "video_id": item["video_id"],
                    "status": "no_edge_planned",
                    "verified": False,
                })

    queue_audit = audit_staging_queue_integrity(queue_file=queue_file, projects_dir=p_root)
    tab_cleanup = (
        cleanup_idle_whale_tabs(cdp_port=cdp_port, dry_run=dry_run)
        if cleanup_tabs
        else {"skipped": True, "candidates": [], "closed": []}
    )

    report = {
        "schema_version": 1,
        "executed_at_utc": now.isoformat(),
        "dry_run": dry_run,
        "scan": scan,
        "promoted_projects": promoted,
        "pin_results": pin_results,
        "link_results": link_results,
        "queue_audit": queue_audit,
        "tab_cleanup": tab_cleanup,
    }
    if not dry_run:
        out_path = CHANNEL_ROOT / "reports" / "studio_watchdog_latest.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report
