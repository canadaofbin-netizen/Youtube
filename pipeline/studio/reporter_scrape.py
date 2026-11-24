"""
ALL ABOUT BRAIN - YouTube Studio Daily Analytics & Growth Reporter
Extracts comprehensive channel & per-video Shorts metrics from YouTube Studio
via visible Naver Whale (CDP 9222) and local pipeline manifests, computes
Day-over-Day (DoD) deltas, diagnoses improvements/bottlenecks, generates a
6-panel high-resolution visual dashboard PNG + inline Mermaid xychart-beta
graphs, and outputs a strictly standardized 9-section Markdown daily report.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import hashlib
import json
import re
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

# Ensure hermes-venv site-packages (matplotlib, cv2, numpy) are available even if invoked via /usr/bin/python3
for _venv_sp in sorted(Path("/home/canadaofbin/hermes-venv/lib").glob("python*/site-packages")):
    if str(_venv_sp) not in sys.path:
        sys.path.append(str(_venv_sp))

from pipeline.config import (
    CHANNEL_ROOT,
    FLOW_DOWNLOAD_HARVEST_LOCK_FILE,
    PROJECTS_DIR,
    PROJECTS_QUARANTINE_DIR,
)
from pipeline.storage import ProjectStorage
def _two_prop_z_score(clicks_a: int, imp_a: int, clicks_b: int, imp_b: int) -> dict[str, float]:
    import math as _m
    if imp_a <= 0 or imp_b <= 0:
        return {"z_score": 0.0, "p_value": 1.0}
    p_pool = (clicks_a + clicks_b) / float(imp_a + imp_b)
    se = _m.sqrt(max(1e-12, p_pool * (1.0 - p_pool) * (1.0 / imp_a + 1.0 / imp_b)))
    z = abs((clicks_a / float(imp_a)) - (clicks_b / float(imp_b))) / se if se > 0 else 0.0
    p_val = _m.erfc(z / _m.sqrt(2.0))
    return {"z_score": round(z, 3), "p_value": round(p_val, 4)}


def _load_published_legacy_topics() -> list[dict[str, Any]]:
    from pipeline.config import CHANNEL_ROOT
    p = Path(CHANNEL_ROOT) / "database" / "published_legacy_topics.json"
    if p.is_file():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return data
        except Exception:
            pass
    return []
from pipeline.studio.config import (
    ALLOW_WATCH_PAGE_FALLBACK,
    CHANNEL_HANDLE,
    CHANNEL_ID,
    CHANNEL_NAME,
    DAILY_REPORTS_DIR,
    DEFAULT_CDP_PORT,
    DEFAULT_FALLBACK_PILLAR,
    LATEST_REPORT_FILE,
    MASTER_PROMPT_FILE,
    REPORTS_ROOT_DIR,
    SLOT_TIMETABLE,
    STAGING_QUEUE_FILE,
    STUDIO_ANALYTICS_URLS,
    STUDIO_TAB_RECYCLE_INTERVAL,
    get_pillar_default_slot,
)
from pipeline.studio.browser_session import DirectCDPClient, WhaleSessionController

LATEST_CHARTS_FILE = REPORTS_ROOT_DIR / "LATEST_STUDIO_CHARTS.png"
LATEST_VIDEO_DETAIL_REPORT_FILE = REPORTS_ROOT_DIR / "LATEST_VIDEO_DETAIL_REPORT.md"
LATEST_VIDEO_DETAIL_CHARTS_FILE = REPORTS_ROOT_DIR / "LATEST_VIDEO_DETAIL_CHARTS.png"
_GLOBAL_PROJECT_STAGE_CACHE: dict[str, dict[str, Any]] = {}
_DURATION_CACHE: dict[str, float] = {}

PILLAR_CANONICAL_MAP: dict[str, tuple[str, str]] = {
    "brain_health": ("brain_health", "Slot 1 (`07:30 ET`)"),
    "brain health": ("brain_health", "Slot 1 (`07:30 ET`)"),
    "bci_tech": ("bci_tech", "Slot 2 (`12:00 ET`)"),
    "bci tech explained": ("bci_tech", "Slot 2 (`12:00 ET`)"),
    "brain_news": ("brain_news", "Slot 2 (`12:00 ET`)"),
    "brain news": ("brain_news", "Slot 2 (`12:00 ET`)"),
    "brain_basics": ("brain_basics", "Slot 3 (`16:00 ET`)"),
    "brain basics": ("brain_basics", "Slot 3 (`16:00 ET`)"),
    "brain_mysteries": ("brain_mysteries", "Slot 3/5 (`16:00/22:30`)"),
    "brain mysteries": ("brain_mysteries", "Slot 3/5 (`16:00/22:30`)"),
    "brain_history": ("brain_history", f"Slot 4 (`{SLOT_TIMETABLE.get(4, {}).get('time_et', '20:00')} ET`)"),
    "brain history": ("brain_history", f"Slot 4 (`{SLOT_TIMETABLE.get(4, {}).get('time_et', '20:00')} ET`)"),
    "bci_ethics": ("bci_ethics", "Slot 5 (`22:30 ET`)"),
    "bci ethics": ("bci_ethics", "Slot 5 (`22:30 ET`)"),
}


def normalize_pillar_id(raw_pillar: str | None) -> str:
    """Normalizes display or internal pillar strings to one of the 7 canonical pillar IDs."""
    if not raw_pillar:
        return DEFAULT_FALLBACK_PILLAR
    low = str(raw_pillar).strip().lower()
    if low in PILLAR_CANONICAL_MAP:
        return PILLAR_CANONICAL_MAP[low][0]
    for k, (canon, _) in PILLAR_CANONICAL_MAP.items():
        if k in low or canon in low:
            return canon
    return DEFAULT_FALLBACK_PILLAR


def make_gauge_bar(pct: float, width: int = 12) -> str:
    """Builds a fixed-width Unicode block progress bar (e.g. `████████░░░░`) for tables."""
    clamped = max(0.0, min(100.0, float(pct)))
    filled = int(round((clamped / 100.0) * width))
    empty = max(0, width - filled)
    return f"`{'█' * filled}{'░' * empty}`"


def format_delta(
    current: float | int,
    previous: float | int | None,
    unit: str = "",
    is_percent_point: bool = False,
    invert_good: bool = False,
    decimals: int = 1,
) -> str:
    """Formats Day-over-Day delta with directional arrow and percentage change."""
    if previous is None:
        return "🆕 첫 집계 (Baseline)"
    diff = float(current) - float(previous)
    if abs(diff) < 1e-6:
        return f"─ 0{unit} (0.0%)"

    up_arrow = "▼" if invert_good else "▲"
    down_arrow = "▲" if invert_good else "▼"
    arrow = up_arrow if diff > 0 else down_arrow
    sign = "+" if diff > 0 else ""

    if isinstance(current, int) and isinstance(previous, int) and not is_percent_point:
        val_str = f"{sign}{int(round(diff)):,}{unit}"
    else:
        val_str = f"{sign}{diff:,.{decimals}f}{unit}"

    if is_percent_point:
        return f"{arrow} {val_str}p"

    if float(previous) != 0:
        pct_change = (diff / abs(float(previous))) * 100.0
        return f"{arrow} {val_str} ({sign}{pct_change:.1f}%)"
    return f"{arrow} {val_str}"


def _clean_str(val: Any) -> str:
    """Safely converts optional JSON fields to stripped string, mapping None/'None'/'null' to ''."""
    if val is None:
        return ""
    s = str(val).strip()
    return "" if s.lower() in {"none", "null"} else s


_INACTIVE_QUEUE_STATUSES = frozenset({
    "vacant",
    "blocked_legacy_v4",
    "deleted",
    "deleted_from_studio",
    "dry_run_staged",
    "awaiting_render",
})


def _is_inactive_queue_status(status_val: Any) -> bool:
    """True when a staging_queue item status represents an inactive, unrendered, deleted, or errored slot."""
    st = _clean_str(status_val).lower()
    return st in _INACTIVE_QUEUE_STATUSES or st.startswith("error")


def _extract_slot_date_time(
    item: dict[str, Any],
    rec_info: dict[str, Any] | None = None,
) -> tuple[str, str]:
    """
    Extracts ('YYYY-MM-DD', 'HH:MM') in ET from queue/history fields or upload_receipt.json,
    preserving real publication/schedule timestamps when 'date'/'time_et' are omitted.
    """
    rec = rec_info or {}
    d_str = _clean_str(item.get("date"))
    t_str = _clean_str(item.get("time_et"))
    if d_str and t_str:
        return d_str, t_str

    for raw_et in (
        item.get("scheduled_time_et"),
        item.get("target_time_et"),
        rec.get("scheduled_time_et"),
        rec.get("target_time_et"),
    ):
        cand = _clean_str(raw_et).replace("ET", "").strip()
        if not cand:
            continue
        m = re.match(r"^(\d{4}-\d{2}-\d{2})(?:\s+(\d{2}:\d{2}))?", cand)
        if m:
            if not d_str:
                d_str = m.group(1)
            if not t_str and m.group(2):
                t_str = m.group(2)
            if d_str and t_str:
                return d_str, t_str

    if not d_str:
        d_rec = _clean_str(rec.get("date"))
        if re.match(r"^\d{4}-\d{2}-\d{2}$", d_rec):
            d_str = d_rec
    if not t_str:
        t_rec = _clean_str(rec.get("time_et"))
        if re.match(r"^\d{2}:\d{2}$", t_rec):
            t_str = t_rec
    if d_str and t_str:
        return d_str, t_str

    for raw_iso in (
        item.get("published_at"),
        rec.get("published_at"),
        rec.get("updated_at") if _clean_str(rec.get("visibility")).lower() == "public" else None,
        rec.get("uploaded_at"),
    ):
        iso_s = _clean_str(raw_iso)
        if not iso_s:
            continue
        try:
            dt_parsed = datetime.fromisoformat(iso_s.replace("Z", "+00:00"))
            if dt_parsed.tzinfo is not None:
                dt_et = dt_parsed.astimezone(ZoneInfo("America/New_York"))
            else:
                dt_et = dt_parsed
            if not d_str:
                d_str = dt_et.strftime("%Y-%m-%d")
            if not t_str:
                t_str = dt_et.strftime("%H:%M")
            if d_str and t_str:
                return d_str, t_str
        except Exception:
            pass

    if d_str and not t_str:
        slot_cand = item.get("slot_id") if item.get("slot_id") is not None else rec.get("slot_id")
        try:
            if slot_cand is not None and int(slot_cand) in SLOT_TIMETABLE:
                t_str = SLOT_TIMETABLE[int(slot_cand)]["time_et"]
        except (TypeError, ValueError):
            pass

    return d_str, t_str




class _StudioScrapeMixin:
    @staticmethod
    def _probe_project_duration_sec(proj_id: str, proj_dir: Path, storage: ProjectStorage | None = None) -> float:
        """Resolves accurate video duration (sec) from probe_report.json, assembled MP4, or completed archive."""
        from pipeline.studio.uploader import resolve_project_video_path

        cache_key = f"{proj_dir.resolve()}::{proj_id}"
        if cache_key in _DURATION_CACHE:
            return _DURATION_CACHE[cache_key]

        dur = 0.0
        if storage is not None:
            for stage_name, fname, key_name in (
                ("05_assembly", "probe_report.json", "duration_seconds"),
                ("05_assembly", "edit_decision_list.json", "total_duration_sec"),
                ("05_assembly", "video_autopsy_report.json", "duration_sec"),
                ("04_audio", "prosody_report.json", "duration_sec"),
                ("04_audio", "voice_report.json", "duration_seconds"),
            ):
                try:
                    rep_doc = storage.load_json(stage_name, fname) or {}
                    val = rep_doc.get(key_name) or rep_doc.get("duration_seconds") or rep_doc.get("total_duration_sec")
                    if val and float(val) > 0:
                        dur = round(float(val), 1)
                        break
                except Exception:
                    pass

        if dur <= 0.0:
            resolved_mp4 = resolve_project_video_path(proj_dir, proj_id)
            if resolved_mp4 is not None and resolved_mp4.exists():
                try:
                    import struct
                    fsize = resolved_mp4.stat().st_size
                    if fsize > 64:
                        with resolved_mp4.open("rb") as mf:
                            chunks = [mf.read(min(fsize, 262144))]
                            if fsize > 262144:
                                mf.seek(max(0, fsize - 262144))
                                chunks.append(mf.read(262144))
                        for buf in chunks:
                            idx_m = buf.find(b"mvhd")
                            if idx_m >= 0 and idx_m + 24 <= len(buf):
                                ver = buf[idx_m + 4]
                                if ver == 0 and idx_m + 24 <= len(buf):
                                    ts, d_val = struct.unpack(">II", buf[idx_m + 16 : idx_m + 24])
                                    if ts > 0 and d_val > 0:
                                        dur = round(float(d_val) / float(ts), 1)
                                        break
                                elif ver == 1 and idx_m + 36 <= len(buf):
                                    ts, d_val = struct.unpack(">IQ", buf[idx_m + 24 : idx_m + 36])
                                    if ts > 0 and d_val > 0:
                                        dur = round(float(d_val) / float(ts), 1)
                                        break
                except Exception:
                    pass

        if dur <= 0.0:
            resolved_mp4 = resolve_project_video_path(proj_dir, proj_id)
            if resolved_mp4 is not None and resolved_mp4.exists():
                try:
                    import cv2
                    cap = cv2.VideoCapture(str(resolved_mp4))
                    fps = float(cap.get(cv2.CAP_PROP_FPS) or 30.0)
                    frames = float(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0.0)
                    cap.release()
                    if fps > 0.0 and frames > 0.0:
                        dur = round(frames / fps, 1)
                except Exception:
                    pass

        if dur <= 0.0:
            dur = 85.0
        _DURATION_CACHE[cache_key] = dur
        return dur

    @staticmethod
    def _fetch_watch_page_fallback(
        video_id: str,
        *,
        allow_watch_fallback: bool | None = None,
    ) -> dict[str, Any]:
        """Queries public YouTube watch page ytInitialPlayerResponse only when explicitly enabled (disabled by default per R75)."""
        enabled = ALLOW_WATCH_PAGE_FALLBACK if allow_watch_fallback is None else bool(allow_watch_fallback)
        if not enabled:
            return {}
        if not video_id or len(video_id) != 11 or video_id == "uploaded_live":
            return {}
        try:
            url = f"https://www.youtube.com/watch?v={video_id}"
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Mozilla/5.0", "Accept-Language": "en-US,en;q=0.9"},
            )
            html = urllib.request.urlopen(req, timeout=3.0).read().decode("utf-8", errors="ignore")
            m = re.search(r"var ytInitialPlayerResponse\s*=\s*(\{.*?\});", html)
            if not m:
                return {}
            pdata = json.loads(m.group(1))
            status = pdata.get("playabilityStatus", {}).get("status", "")
            if status != "OK":
                return {"playability_status": status}
            vd = pdata.get("videoDetails", {}) or {}
            mf = pdata.get("microformat", {}).get("playerMicroformatRenderer", {}) or {}
            return {
                "playability_status": "OK",
                "title": vd.get("title", ""),
                "views": int(vd["viewCount"]) if vd.get("viewCount") is not None else None,
                "duration_seconds": float(vd["lengthSeconds"]) if vd.get("lengthSeconds") else None,
                "is_unlisted": bool(mf.get("isUnlisted", False)),
                "publish_date": str(mf.get("publishDate", "")),
            }
        except Exception:
            return {}

    def _collect_local_pipeline_state(self, report_date: str) -> dict[str, Any]:
        """Reads staging_queue.json, upload_receipt.json, and project directories for published/scheduled/unlisted/staged status."""
        from pipeline.studio.config import SHORT_LINK_GRAPH_FILE
        from pipeline.studio.queue_manager import is_live_youtube_receipt, passes_v5_publish_gate
        from pipeline.studio.short_linker import is_valid_youtube_video_id
        from pipeline.studio.uploader import resolve_project_video_path
        ALL_PSYCHOLOGY_100_TOPICS = _load_published_legacy_topics()

        projects_dir = self.projects_dir if self.projects_dir is not None else PROJECTS_DIR
        queue_file = self.queue_file if self.queue_file is not None else STAGING_QUEUE_FILE
        graph_file = (
            self.short_link_graph_file
            if self.short_link_graph_file is not None
            else SHORT_LINK_GRAPH_FILE
        )

        catalog_by_pid: dict[str, dict[str, Any]] = {
            _clean_str(t.get("project_id")): t
            for t in ALL_PSYCHOLOGY_100_TOPICS
            if _clean_str(t.get("project_id"))
        }

        receipts_by_pid: dict[str, dict[str, Any]] = {}
        related_receipts_by_pid: dict[str, dict[str, Any]] = {}
        project_dirs_list: list[Path] = []
        if projects_dir.exists():
            project_dirs_list = [d for d in sorted(projects_dir.iterdir()) if d.is_dir()]

            def _scan_pub_receipts(p_dir: Path):
                r_out = None
                rel_out = None
                pid_r = p_dir.name
                pid_rel = p_dir.name
                pub_d = p_dir / "06_publish"
                r_file = pub_d / "upload_receipt.json"
                rel_file = pub_d / "related_video_receipt.json"
                try:
                    if r_file.exists() and r_file.stat().st_size > 0:
                        r_data = json.loads(r_file.read_text(encoding="utf-8"))
                        pid_r = _clean_str(r_data.get("project_id")) or p_dir.name
                        r_out = r_data
                except Exception:
                    pass
                try:
                    if rel_file.exists() and rel_file.stat().st_size > 0:
                        rel_data = json.loads(rel_file.read_text(encoding="utf-8"))
                        pid_rel = _clean_str(rel_data.get("project_id")) or p_dir.name
                        rel_out = rel_data
                except Exception:
                    pass
                return pid_r, r_out, pid_rel, rel_out

            if len(project_dirs_list) > 4:
                from pipeline.hardware_profile import resolve_cpu_budget

                with concurrent.futures.ThreadPoolExecutor(max_workers=resolve_cpu_budget()) as pool:
                    scan_rows = list(pool.map(_scan_pub_receipts, project_dirs_list))
            else:
                scan_rows = [_scan_pub_receipts(d) for d in project_dirs_list]
            for pid_r, r_out, pid_rel, rel_out in scan_rows:
                if r_out is not None:
                    receipts_by_pid[pid_r] = r_out
                if rel_out is not None:
                    related_receipts_by_pid[pid_rel] = rel_out

        short_link_graph: dict[str, Any] = {}
        if graph_file.exists():
            try:
                short_link_graph = json.loads(graph_file.read_text(encoding="utf-8"))
            except Exception:
                short_link_graph = {}

        queue_data: dict[str, Any] = {"scheduled_items": []}
        if queue_file.exists():
            try:
                queue_data = json.loads(queue_file.read_text(encoding="utf-8"))
            except Exception:
                pass

        raw_scheduled_items = [
            it for it in (queue_data.get("scheduled_items") or [])
            if isinstance(it, dict)
        ]
        raw_vacant_slots = [
            _clean_str(it.get("schedule_id")) or f"{_clean_str(it.get('date'))}_slot{it.get('slot_id')}"
            for it in raw_scheduled_items
            if not _clean_str(it.get("project_id")) or _clean_str(it.get("status")).lower() == "vacant"
        ]
        assigned_scheduled_items = [
            it for it in raw_scheduled_items
            if _clean_str(it.get("project_id"))
            and not _is_inactive_queue_status(it.get("status"))
        ]

        combined_queue_items: list[dict[str, Any]] = []
        seen_queue_pids: set[str] = set()
        active_by_pid: dict[str, dict[str, Any]] = {
            _clean_str(it.get("project_id")): it
            for it in assigned_scheduled_items
            if _clean_str(it.get("project_id"))
        }
        for src_item in list(queue_data.get("history") or []) + list(assigned_scheduled_items):
            if not isinstance(src_item, dict):
                continue
            p_key = _clean_str(src_item.get("project_id"))
            if not p_key or _is_inactive_queue_status(src_item.get("status")):
                continue
            if p_key in seen_queue_pids:
                continue
            seen_queue_pids.add(p_key)
            merged_item = dict(src_item)
            if p_key in active_by_pid and merged_item is not active_by_pid[p_key]:
                st_hist = _clean_str(merged_item.get("status")).lower()
                if st_hist not in {"published", "published_public"}:
                    merged_item.update(active_by_pid[p_key])
            combined_queue_items.append(merged_item)

        for pid_r, r_data in sorted(receipts_by_pid.items()):
            if pid_r in seen_queue_pids:
                continue
            if is_live_youtube_receipt(r_data):
                r_status = _clean_str(r_data.get("status")).lower()
                r_vis = _clean_str(r_data.get("visibility")).lower()
                r_date, r_time = _extract_slot_date_time({}, r_data)
                eff_q_status = (
                    "published"
                    if (r_status == "published_public" or r_vis == "public")
                    else ("unlisted" if (r_vis == "unlisted" or ("unlisted" in r_status and r_vis != "scheduled")) else "scheduled")
                )
                synth_item: dict[str, Any] = {
                    "project_id": pid_r,
                    "title": _clean_str(r_data.get("title")),
                    "video_id": _clean_str(r_data.get("video_id")),
                    "shorts_url": _clean_str(r_data.get("shorts_url")),
                    "slot_id": r_data.get("slot_id"),
                    "scheduled_time_et": _clean_str(r_data.get("scheduled_time_et")),
                    "status": eff_q_status,
                }
                if r_date:
                    synth_item["date"] = r_date
                if r_time:
                    synth_item["time_et"] = r_time
                combined_queue_items.append(synth_item)
                seen_queue_pids.add(pid_r)

        published_items: list[dict[str, Any]] = []
        scheduled_pending: list[dict[str, Any]] = []
        unlisted_staged_items: list[dict[str, Any]] = []

        pub_ts_counts: dict[str, int] = {}
        pub_ts_projects: dict[str, list[str]] = {}
        parsed_pub_datetimes: list[datetime] = []

        for item in combined_queue_items:
            proj_id = _clean_str(item.get("project_id"))
            if not proj_id:
                continue
            cat_info = catalog_by_pid.get(proj_id, {})
            rec_info = receipts_by_pid.get(proj_id, {})

            status = _clean_str(item.get("status")).lower()
            rec_vis = _clean_str(rec_info.get("visibility")).lower()
            rec_status = _clean_str(rec_info.get("status")).lower()
            if _is_inactive_queue_status(status):
                continue
            if rec_status == "deleted_from_studio" or rec_vis == "deleted":
                continue

            if not _clean_str(item.get("title")):
                item["title"] = (
                    _clean_str(rec_info.get("title"))
                    or _clean_str(cat_info.get("title"))
                    or proj_id
                )
            if not _clean_str(item.get("pillar")):
                item["pillar"] = _clean_str(cat_info.get("pillar")) or DEFAULT_FALLBACK_PILLAR
            if not _clean_str(item.get("video_id")) and _clean_str(rec_info.get("video_id")):
                vid_cand = _clean_str(rec_info.get("video_id"))
                if vid_cand and vid_cand != "uploaded_live":
                    item["video_id"] = vid_cand
                    item["shorts_url"] = _clean_str(rec_info.get("shorts_url")) or f"https://www.youtube.com/shorts/{vid_cand}"
            if not _clean_str(item.get("published_at")) and _clean_str(rec_info.get("published_at")):
                item["published_at"] = _clean_str(rec_info.get("published_at"))

            ext_date, ext_time = _extract_slot_date_time(item, rec_info)
            if ext_date:
                item["date"] = ext_date
            if ext_time:
                item["time_et"] = ext_time
            if item.get("slot_id") is None and rec_info.get("slot_id") is not None:
                item["slot_id"] = rec_info.get("slot_id")

            has_live_rec = is_live_youtube_receipt(rec_info)
            has_live_vid = is_valid_youtube_video_id(_clean_str(item.get("video_id")))

            is_effectively_published = (
                rec_vis == "public"
                or rec_status == "published_public"
                or (status in {"published", "published_public"} and rec_vis not in {"scheduled", "unlisted"})
            )

            if not is_effectively_published and not has_live_vid and not has_live_rec:
                cand_pdir = projects_dir / proj_id
                if not cand_pdir.exists() or not (cand_pdir / "00_project_manifest.json").exists():
                    continue
                if resolve_project_video_path(cand_pdir, proj_id) is None:
                    continue
                v5_ok, _ = passes_v5_publish_gate(cand_pdir, allow_legacy_v4=False, fast_stat_only=True)
                if not v5_ok:
                    continue

            is_effectively_unlisted = (
                not is_effectively_published
                and (
                    rec_vis == "unlisted"
                    or ("unlisted" in rec_status and rec_vis != "scheduled")
                    or (rec_vis != "scheduled" and status in {"unlisted", "staged_unlisted", "uploaded_unlisted"})
                )
            )

            if is_effectively_published:
                item["effective_status"] = "published"
                item["status"] = "published"
                published_items.append(item)
                pts = _clean_str(item.get("published_at"))
                if pts:
                    pub_ts_counts[pts] = pub_ts_counts.get(pts, 0) + 1
                    pub_ts_projects.setdefault(pts, []).append(proj_id)
                    try:
                        parsed_pub_datetimes.append(datetime.fromisoformat(pts.replace("Z", "+00:00")))
                    except Exception:
                        pass
                elif ext_date and ext_time:
                    try:
                        dt_et = datetime.strptime(f"{ext_date} {ext_time}", "%Y-%m-%d %H:%M")
                        parsed_pub_datetimes.append(dt_et.replace(tzinfo=timezone.utc))
                    except Exception:
                        pass
            elif is_effectively_unlisted:
                item["effective_status"] = "unlisted"
                item["status"] = "unlisted"
                unlisted_staged_items.append(item)
            else:
                item["effective_status"] = "scheduled"
                item["status"] = "scheduled"
                scheduled_pending.append(item)

        max_pub_same_ts = max(pub_ts_counts.values(), default=0)
        simultaneous_publish_count = max_pub_same_ts if max_pub_same_ts > 1 else 0
        simultaneous_publish_timestamp = ""
        simultaneous_publish_projects: list[str] = []
        if simultaneous_publish_count > 1:
            simultaneous_publish_timestamp = max(pub_ts_counts, key=pub_ts_counts.get)  # type: ignore[arg-type]
            simultaneous_publish_projects = pub_ts_projects.get(simultaneous_publish_timestamp, [])

        min_publish_gap_hours = 4.5
        if simultaneous_publish_count > 1:
            min_publish_gap_hours = 0.0
        elif len(parsed_pub_datetimes) >= 2:
            sorted_dts = sorted(parsed_pub_datetimes)
            gaps = [
                (sorted_dts[i + 1] - sorted_dts[i]).total_seconds() / 3600.0
                for i in range(len(sorted_dts) - 1)
            ]
            if gaps:
                min_publish_gap_hours = round(min(gaps), 2)

        for q_it in scheduled_pending + unlisted_staged_items:
            q_pid = _clean_str(q_it.get("project_id"))
            q_cat = catalog_by_pid.get(q_pid, {})
            q_pillar = normalize_pillar_id(
                _clean_str(q_it.get("pillar")) or _clean_str(q_cat.get("pillar")) or DEFAULT_FALLBACK_PILLAR
            )
            try:
                q_slot = int(q_it.get("slot_id") or get_pillar_default_slot(q_pillar))
            except (TypeError, ValueError):
                q_slot = get_pillar_default_slot(q_pillar)
            q_it["slot_id"] = q_slot
            if not _clean_str(q_it.get("slot_name")):
                q_it["slot_name"] = SLOT_TIMETABLE.get(q_slot, {}).get("name", "Midday Peak")
            if not _clean_str(q_it.get("date")):
                q_it["date"] = report_date
            if not _clean_str(q_it.get("time_et")):
                q_it["time_et"] = SLOT_TIMETABLE.get(q_slot, {}).get("time_et", "12:00")
            if not _clean_str(q_it.get("time_kst")):
                q_it["time_kst"] = SLOT_TIMETABLE.get(q_slot, {}).get("time_kst", "01:00")
            if not _clean_str(q_it.get("schedule_id")):
                q_it["schedule_id"] = f"{q_it['date']}_slot{q_slot}"

        occupied_slot_ids: set[str] = set()
        for q_it in scheduled_pending + unlisted_staged_items:
            sid_q = _clean_str(q_it.get("schedule_id"))
            if sid_q:
                occupied_slot_ids.add(sid_q)
            d_q = _clean_str(q_it.get("date"))
            if d_q and q_it.get("slot_id") is not None:
                occupied_slot_ids.add(f"{d_q}_slot{q_it.get('slot_id')}")

        vacant_slots = [sid for sid in raw_vacant_slots if sid not in occupied_slot_ids]

        vacuum_slots = [
            _clean_str(it.get("schedule_id")) or f"{_clean_str(it.get('date'))}_slot{it.get('slot_id')}"
            for it in unlisted_staged_items
        ]
        if unlisted_staged_items:
            first_u = unlisted_staged_items[0]
            last_u = unlisted_staged_items[-1]
            vacuum_range_str = (
                f"{vacuum_slots[0]} ({first_u.get('date')} {first_u.get('time_et')} ET, {first_u.get('project_id')}) ~ "
                f"{vacuum_slots[-1]} ({last_u.get('date')} {last_u.get('time_et')} ET, {last_u.get('project_id')})"
            )
        else:
            vacuum_range_str = "None"

        all_enrich_items = published_items + scheduled_pending + unlisted_staged_items
        is_global_projects = (projects_dir == PROJECTS_DIR)

        def _preload_proj_bundle(it_row: dict[str, Any]) -> tuple[str, dict[str, Any]]:
            pid_x = _clean_str(it_row.get("project_id"))
            if not pid_x:
                return "", {}
            pdir_x = projects_dir / pid_x
            if is_global_projects and pid_x in _GLOBAL_PROJECT_STAGE_CACHE:
                return pid_x, _GLOBAL_PROJECT_STAGE_CACHE[pid_x]
            out_b: dict[str, Any] = {"exists": pdir_x.exists()}
            st_obj = None
            if out_b["exists"]:
                try:
                    st_obj = ProjectStorage(pid_x) if is_global_projects else ProjectStorage(pid_x, projects_dir=projects_dir)
                    out_b["rc"] = st_obj.load_json("01_ideation", "research_card.json") or {}
                    out_b["sc"] = st_obj.load_json("02_script", "script.json") or {}
                    out_b["vp"] = st_obj.load_json("03_visuals", "visual_plan.json") or {}
                    out_b["edl"] = st_obj.load_json("05_assembly", "edit_decision_list.json") or {}
                    out_b["meta_pub"] = st_obj.load_json("06_publish", "metadata.json") or {}
                    out_b["ab"] = st_obj.load_json("06_publish", "ab_test_manifest.json") or {}
                    out_b["comm"] = st_obj.load_json("06_publish", "community_receipt.json") or {}
                except Exception:
                    pass
            out_b["dur"] = self._probe_project_duration_sec(pid_x, pdir_x, storage=st_obj)
            if is_global_projects:
                _GLOBAL_PROJECT_STAGE_CACHE[pid_x] = out_b
            return pid_x, out_b

        if len(all_enrich_items) > 4:
            from pipeline.hardware_profile import resolve_cpu_budget

            with concurrent.futures.ThreadPoolExecutor(max_workers=resolve_cpu_budget()) as pool:
                preloaded_map = dict(pool.map(_preload_proj_bundle, all_enrich_items))
        else:
            preloaded_map = dict(_preload_proj_bundle(it_r) for it_r in all_enrich_items)

        enriched_videos: list[dict[str, Any]] = []
        rotation_intervals: list[int] = []
        for idx, item in enumerate(all_enrich_items, 1):
            proj_id = _clean_str(item.get("project_id"))
            if not proj_id:
                continue
            proj_dir = projects_dir / proj_id
            cat_info = catalog_by_pid.get(proj_id, {})
            rec_info = receipts_by_pid.get(proj_id, {})

            raw_pillar = _clean_str(item.get("pillar")) or _clean_str(cat_info.get("pillar")) or DEFAULT_FALLBACK_PILLAR
            pillar_canon = normalize_pillar_id(raw_pillar)
            try:
                slot_id = int(item.get("slot_id") or rec_info.get("slot_id") or get_pillar_default_slot(pillar_canon))
            except (TypeError, ValueError):
                slot_id = get_pillar_default_slot(pillar_canon)

            doi_str = _clean_str(cat_info.get("doi")) or "Verified"
            production_profile = "shorts_v4"
            active_variant = "A"
            rotation_interval_hours = 24
            ab_manifest_data: dict[str, Any] = {}
            pinned_comment = False
            clip_count = 10
            word_count = 0
            hook_sentence = ""
            protagonist = ""
            brain_regions = ""
            published_at_iso = _clean_str(item.get("published_at")) or _clean_str(rec_info.get("published_at"))

            cat_ctx = cat_info.get("story_context") or {}
            if isinstance(cat_ctx, dict):
                protagonist = _clean_str(cat_ctx.get("protagonist"))
                brain_regions = _clean_str(cat_ctx.get("brain_regions"))
            cat_narrs = cat_info.get("clip_narrations") or []
            if isinstance(cat_narrs, list) and cat_narrs:
                clip_count = len(cat_narrs)
                word_count = sum(len(str(c).split()) for c in cat_narrs)
                hook_sentence = str(cat_narrs[0]).strip()

            pb = preloaded_map.get(proj_id) or {}
            if pb.get("exists"):
                try:
                    rc = pb.get("rc") or {}
                    if rc.get("doi"):
                        doi_str = str(rc["doi"])
                    story_ctx = rc.get("story_context") or {}
                    if isinstance(story_ctx, dict):
                        protagonist = _clean_str(story_ctx.get("protagonist")) or protagonist
                        brain_regions = _clean_str(story_ctx.get("brain_regions")) or brain_regions

                    sc = pb.get("sc") or {}
                    if sc.get("doi") and doi_str == "Verified":
                        doi_str = _clean_str(sc.get("doi")) or doi_str
                    if sc.get("profile"):
                        production_profile = _clean_str(sc.get("profile")) or production_profile
                    elif sc.get("schema") == 6:
                        production_profile = "neuro_diorama"

                    clip_narrs = sc.get("clip_narrations") or []
                    if isinstance(clip_narrs, list) and clip_narrs:
                        clip_count = len(clip_narrs)
                        word_count = sum(len(str(c).split()) for c in clip_narrs)
                        hook_sentence = str(clip_narrs[0]).strip()
                    elif isinstance(sc.get("acts"), list) and sc.get("acts"):
                        act_sents = [
                            str(s).strip()
                            for act in sc["acts"]
                            if isinstance(act, dict)
                            for s in (act.get("sentences") or [])
                            if str(s).strip()
                        ]
                        if act_sents:
                            clip_count = len(act_sents)
                            word_count = sum(len(s.split()) for s in act_sents)
                            hook_sentence = (
                                act_sents[1]
                                if (len(act_sents) > 1 and "university brain science" in act_sents[0].lower())
                                else act_sents[0]
                            )

                    vp = pb.get("vp") or {}
                    if not protagonist and vp.get("topic"):
                        protagonist = _clean_str(vp.get("topic"))
                    if vp.get("schema") == 5 and production_profile == "shorts_v4":
                        production_profile = "shorts_v5"
                    elif vp.get("schema") == 6:
                        production_profile = "neuro_diorama"

                    edl = pb.get("edl") or {}
                    if edl.get("base_clips_used") or edl.get("cut_count"):
                        clip_count = int(edl.get("base_clips_used") or edl.get("cut_count") or clip_count)

                    meta_pub = pb.get("meta_pub") or {}
                    if meta_pub.get("doi") and doi_str == "Verified":
                        doi_str = _clean_str(meta_pub.get("doi")) or doi_str
                    if meta_pub.get("profile"):
                        production_profile = _clean_str(meta_pub.get("profile")) or production_profile
                    if meta_pub.get("pillar") and not _clean_str(cat_info.get("pillar")):
                        raw_pillar = _clean_str(meta_pub.get("pillar")) or raw_pillar
                        pillar_canon = normalize_pillar_id(raw_pillar)

                    ab_manifest_data = pb.get("ab") or {}
                    if ab_manifest_data.get("current_active_variant"):
                        active_variant = str(ab_manifest_data["current_active_variant"])
                    if ab_manifest_data.get("rotation_interval_hours"):
                        rotation_interval_hours = int(ab_manifest_data["rotation_interval_hours"])
                        rotation_intervals.append(rotation_interval_hours)

                    comm = pb.get("comm") or {}
                    if "pinned" in comm:
                        pinned_comment = bool(comm["pinned"])
                except Exception:
                    pass

            duration_sec = float(pb.get("dur") or self._probe_project_duration_sec(proj_id, proj_dir, storage=None))
            resolved_title = (
                _clean_str(item.get("title"))
                or _clean_str(rec_info.get("title"))
                or _clean_str(cat_info.get("title"))
                or proj_id
            )
            eff_status = (_clean_str(item.get("effective_status")) or _clean_str(item.get("status")) or "published").lower()
            rel_rec = related_receipts_by_pid.get(proj_id, {})
            graph_edges = short_link_graph.get("edges") or []
            planned_edge = next(
                (e for e in graph_edges if isinstance(e, dict) and _clean_str(e.get("source_project_id")) == proj_id),
                {},
            )
            rel_verified = bool(rel_rec.get("verified") or rec_info.get("related_video_verified"))
            rel_target_pid = (
                _clean_str(rel_rec.get("target_project_id"))
                or _clean_str(rec_info.get("related_target_project_id"))
                or _clean_str(planned_edge.get("target_project_id"))
            )
            rel_target_vid = (
                _clean_str(rel_rec.get("target_video_id"))
                or _clean_str(rec_info.get("related_target_video_id"))
                or _clean_str(planned_edge.get("target_video_id"))
            )
            rel_link_role = (
                _clean_str(rel_rec.get("link_role"))
                or _clean_str(rel_rec.get("link_reason"))
                or _clean_str(planned_edge.get("link_role"))
                or _clean_str(planned_edge.get("link_reason"))
            )
            playlist_verified = bool(
                rel_rec.get("playlist_verified")
                or rel_rec.get("playlist_assigned")
                or rec_info.get("playlist_verified")
            )
            playlist_title = _clean_str(rel_rec.get("playlist_title")) or _clean_str(rec_info.get("playlist_title"))

            enriched_videos.append({
                "index": idx,
                "project_id": proj_id,
                "title": resolved_title,
                "pillar": pillar_canon,
                "pillar_label": raw_pillar or pillar_canon,
                "slot_id": slot_id,
                "slot_name": item.get("slot_name") or SLOT_TIMETABLE.get(slot_id, {}).get("name", "Midday Peak"),
                "date": _clean_str(item.get("date")) or report_date,
                "time_et": _clean_str(item.get("time_et")) or "12:00",
                "time_kst": _clean_str(item.get("time_kst")) or SLOT_TIMETABLE.get(slot_id, {}).get("time_kst", "01:00"),
                "published_at": published_at_iso,
                "status": eff_status,
                "video_id": _clean_str(item.get("video_id")),
                "shorts_url": _clean_str(item.get("shorts_url")),
                "production_profile": production_profile,
                "duration_seconds": duration_sec,
                "clip_count": clip_count,
                "word_count": word_count,
                "hook_sentence": hook_sentence,
                "protagonist": protagonist,
                "brain_regions": brain_regions,
                "doi": doi_str,
                "active_variant": active_variant,
                "rotation_interval_hours": rotation_interval_hours,
                "ab_manifest": ab_manifest_data,
                "pinned_comment": pinned_comment,
                "related_verified": rel_verified,
                "related_target_project_id": rel_target_pid,
                "related_target_video_id": rel_target_vid,
                "related_link_role": rel_link_role,
                "playlist_verified": playlist_verified,
                "playlist_title": playlist_title,
            })

        published_pids = {_clean_str(it.get("project_id")) for it in published_items if _clean_str(it.get("project_id"))}
        active_staged_pids = {
            _clean_str(it.get("project_id"))
            for it in (scheduled_pending + unlisted_staged_items)
            if _clean_str(it.get("project_id"))
        }

        completed_pids: set[str] = set()
        blocked_legacy_v4_pids: set[str] = set()
        archive_dir_candidates: list[Path] = []
        for anc in (projects_dir.parent, projects_dir.parent.parent):
            cand_arch = anc / "Completed_Psychology_100_Shorts"
            if cand_arch not in archive_dir_candidates:
                archive_dir_candidates.append(cand_arch)
        if projects_dir.resolve() == PROJECTS_DIR.resolve():
            ws_arch = CHANNEL_ROOT.parent / "Completed_Psychology_100_Shorts"
            if ws_arch not in archive_dir_candidates:
                archive_dir_candidates.insert(0, ws_arch)

        if project_dirs_list:
            known_live_or_active = published_pids | active_staged_pids

            def _classify_project_dir(p_dir: Path) -> tuple[str, str]:
                pid_cand = p_dir.name
                if not (p_dir / "00_project_manifest.json").exists():
                    return pid_cand, "skip"
                if resolve_project_video_path(p_dir, pid_cand) is None:
                    return pid_cand, "skip"
                rec_cand = receipts_by_pid.get(pid_cand, {})
                if is_live_youtube_receipt(rec_cand) or pid_cand in known_live_or_active:
                    return pid_cand, "completed"
                v5_ok, _ = passes_v5_publish_gate(p_dir, allow_legacy_v4=False, fast_stat_only=True)
                return pid_cand, ("completed" if v5_ok else "blocked_v4")

            if len(project_dirs_list) > 4:
                from pipeline.hardware_profile import resolve_cpu_budget

                with concurrent.futures.ThreadPoolExecutor(max_workers=resolve_cpu_budget()) as pool:
                    cls_rows = list(pool.map(_classify_project_dir, project_dirs_list))
            else:
                cls_rows = [_classify_project_dir(d) for d in project_dirs_list]
            for pid_cand, cls_tag in cls_rows:
                if cls_tag == "completed":
                    completed_pids.add(pid_cand)
                elif cls_tag == "blocked_v4":
                    blocked_legacy_v4_pids.add(pid_cand)
        for completed_archive_dir in archive_dir_candidates:
            if completed_archive_dir.exists():
                for mp4_f in completed_archive_dir.glob("final_shorts_*.mp4"):
                    pid_arch = mp4_f.stem.replace("final_shorts_", "", 1)
                    if pid_arch not in completed_pids:
                        blocked_legacy_v4_pids.add(pid_arch)

        completed_pids |= published_pids | active_staged_pids
        blocked_legacy_v4_pids -= completed_pids
        total_completed = len(completed_pids)
        staged_buffer_count = len((completed_pids - published_pids) | active_staged_pids)

        quarantined_projects: list[str] = []
        if PROJECTS_QUARANTINE_DIR.exists() and projects_dir == PROJECTS_DIR:
            quarantined_projects = sorted([
                p.name for p in PROJECTS_QUARANTINE_DIR.iterdir() if p.is_dir()
            ])

        harvest_lock_exists = bool(FLOW_DOWNLOAD_HARVEST_LOCK_FILE.exists()) if projects_dir == PROJECTS_DIR else False

        schedule_map_drift_slots: list[str] = []
        sched_map_file = CHANNEL_ROOT / "scripts" / "batch_ops" / "studio_schedule_map_31_100.json"
        if sched_map_file.exists() and projects_dir == PROJECTS_DIR:
            try:
                smap = json.loads(sched_map_file.read_text(encoding="utf-8"))
                canonical_et = [
                    SLOT_TIMETABLE[s]["time_et"]
                    for s in sorted(SLOT_TIMETABLE.keys())
                ]
                if isinstance(smap, dict) and "slots_et" in smap:
                    slots_cfg = smap.get("slots_et", [])
                    for idx_s, s_time in enumerate(slots_cfg):
                        if idx_s < len(canonical_et) and str(s_time) != canonical_et[idx_s]:
                            schedule_map_drift_slots.append(
                                f"Slot {idx_s + 1}: {s_time} ET != {canonical_et[idx_s]} ET"
                            )
                else:
                    entries = smap.values() if isinstance(smap, dict) else (smap if isinstance(smap, list) else [])
                    seen_slot_nums: set[int] = set()
                    for entry in entries:
                        if not isinstance(entry, dict):
                            continue
                        s_num = int(entry.get("slot", entry.get("slot_num", 0)) or 0)
                        t_str = str(entry.get("time_et", entry.get("time_str", ""))).strip()
                        if 1 <= s_num <= len(canonical_et) and s_num not in seen_slot_nums and t_str:
                            seen_slot_nums.add(s_num)
                            try:
                                dt_parsed = datetime.strptime(t_str, "%I:%M %p")
                                t_24 = dt_parsed.strftime("%H:%M")
                            except ValueError:
                                t_24 = t_str
                            canon_t = canonical_et[s_num - 1]
                            if t_24 != canon_t:
                                schedule_map_drift_slots.append(
                                    f"Slot {s_num}: {t_str} ({t_24} ET) != {canon_t} ET"
                                )
            except Exception:
                pass

        valid_queue_items = sorted(
            list(scheduled_pending) + list(unlisted_staged_items),
            key=lambda x: (_clean_str(x.get("date")), int(x.get("slot_id") or 2)),
        )
        filtered_upcoming = [
            it for it in valid_queue_items
            if _clean_str(it.get("date")) >= report_date
        ][:10]
        upcoming_schedule = filtered_upcoming if filtered_upcoming else valid_queue_items[-10:]

        ab_rotation_interval_hours = max(rotation_intervals, default=72)
        ab_rotation_mismatch_count = sum(1 for r_int in rotation_intervals if r_int not in (24, 72))

        return {
            "published_count": len(published_items),
            "scheduled_count": len(scheduled_pending),
            "vacant_slot_count": len(vacant_slots),
            "vacant_slots": vacant_slots,
            "unlisted_staged_count": len(unlisted_staged_items),
            "total_completed_inventory": total_completed,
            "staged_buffer_count": staged_buffer_count,
            "blocked_legacy_v4_count": len(blocked_legacy_v4_pids),
            "quarantined_projects": quarantined_projects,
            "quarantine_projects": quarantined_projects,
            "quarantine_count": len(quarantined_projects),
            "harvest_lock_exists": harvest_lock_exists,
            "harvest_lock_path": str(FLOW_DOWNLOAD_HARVEST_LOCK_FILE),
            "simultaneous_publish_count": simultaneous_publish_count,
            "simultaneous_publish_timestamp": simultaneous_publish_timestamp,
            "simultaneous_publish_projects": simultaneous_publish_projects,
            "min_publish_gap_hours": min_publish_gap_hours,
            "vacuum_slots": vacuum_slots,
            "vacuum_slot_count": len(vacuum_slots),
            "vacuum_range_str": vacuum_range_str,
            "ab_rotation_interval_hours": ab_rotation_interval_hours,
            "ab_rotation_mismatch_count": ab_rotation_mismatch_count,
            "schedule_map_drift_slots": schedule_map_drift_slots,
            "upcoming_schedule": upcoming_schedule,
            "videos": enriched_videos,
            "raw_queue_items": valid_queue_items,
            "short_link_graph": short_link_graph,
            "related_linked_count": sum(1 for v_it in enriched_videos if v_it.get("related_verified")),
            "playlist_assigned_count": sum(1 for v_it in enriched_videos if v_it.get("playlist_verified")),
        }

    async def _async_scrape_studio_dom(
        self,
        known_video_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        Connects to visible Naver Whale over CDP (port 9222), inspects YouTube Studio
        Analytics & Content tabs, and extracts available live DOM metrics.
        Never uses headless browser; strictly reuses/opens visible Whale tab.
        """
        scraped: dict[str, Any] = {
            "live_connected": False,
            "studio_authenticated": False,
            "channel_subscribers": None,
            "dashboard_metrics": {},
            "overview_metrics": {},
            "content_metrics": {},
            "audience_metrics": {},
            "video_row_metrics": {},
            "per_video_analytics": {},
            "raw_page_snippets": {},
        }

        from pipeline.cdp_tab_lease import enable_background_focus_emulation, leased_cdp_tab
        from pipeline.studio.browser_session import _DEEP_QUERY_HELPER_JS

        try:
            async with leased_cdp_tab(
                STUDIO_ANALYTICS_URLS["dashboard"],
                purpose="studio_daily_report",
                cdp_port=self.session.cdp_port,
                cdp_host=self.session.cdp_host,
                background=True,
            ) as (active_client, _leased_tid, _lease_owner):
                scraped["live_connected"] = True
                await enable_background_focus_emulation(active_client)

                for _ in range(12):
                    await asyncio.sleep(1.0)
                    d_len = await active_client.eval("(document.body ? document.body.innerText : '').length")
                    if d_len and int(d_len) > 600:
                        break
                await asyncio.sleep(1.2)

                current_url = str(await active_client.eval("window.location.href") or "")
                if "accounts.google.com" in current_url or "ServiceLogin" in current_url:
                    print("[StudioReporter] YouTube Studio requires Google sign-in in Whale.")
                    return scraped

                scraped["studio_authenticated"] = "studio.youtube.com" in current_url
                dash_text = str(await active_client.eval("document.body ? document.body.innerText : ''") or "")
                scraped["raw_page_snippets"]["dashboard"] = dash_text[:4000]
                scraped["dashboard_metrics"] = self._parse_analytics_text_block(dash_text)

                await enable_background_focus_emulation(active_client)
                await active_client.send("Page.navigate", {"url": STUDIO_ANALYTICS_URLS["content_shorts"]})
                deep_row_cnt_js = f"(() => {{ {_DEEP_QUERY_HELPER_JS} return __queryAllDeep('ytcp-video-row').length; }})()"
                for _ in range(14):
                    await asyncio.sleep(1.0)
                    row_cnt = await active_client.eval(deep_row_cnt_js)
                    if row_cnt and int(row_cnt) > 0:
                        break
                await asyncio.sleep(1.2)

                rows_js = f"""
                (async () => {{
                    {_DEEP_QUERY_HELPER_JS}
                    const out = {{}};
                    const harvest = () => {{
                        const rows = __queryAllDeep('ytcp-video-row');
                        for (const r of rows) {{
                            const txt = (r.innerText || '').trim();
                            if (!txt) continue;
                            const links = __queryAllDeep('a[href*="/video/"], a[href*="/shorts/"]', r);
                            let vid = '';
                            for (const link of links) {{
                                const href = link.getAttribute('href') || link.href || '';
                                const m = href.match(/\\/(?:video|shorts)\\/([A-Za-z0-9_-]{{11}})/);
                                if (m) {{ vid = m[1]; break; }}
                            }}
                            if (vid) {{
                                out[vid] = txt.replace(/\\s+/g, ' ').slice(0, 2000);
                            }}
                        }}
                    }};
                    harvest();
                    const scrollers = __queryAllDeep('#video-list, ytcp-video-section-content, main');
                    const scroller = scrollers.find(el => el.scrollHeight > el.clientHeight) || document.scrollingElement;
                    if (scroller) {{
                        for (let step = 0; step < 6; step++) {{
                            scroller.scrollBy(0, 900);
                            await new Promise(res => setTimeout(res, 280));
                            harvest();
                        }}
                        scroller.scrollTo(0, 0);
                    }}
                    return out;
                }})()
                """
                video_rows = await active_client.eval(rows_js, await_promise=True)
                if isinstance(video_rows, dict):
                    scraped["video_row_metrics"] = video_rows

                scraped["period_7d_probe_meta"] = {}
                for tab_key, url_key, target_field, p_hint in (
                    ("overview", "analytics_overview", "overview_metrics", "28d"),
                    ("overview_7d", "analytics_overview_7d", "overview_7d_metrics", "7d"),
                    ("content", "analytics_content", "content_metrics", "28d"),
                    ("audience", "analytics_audience", "audience_metrics", "28d"),
                    ("audience_7d", "analytics_audience_7d", "audience_7d_metrics", "7d"),
                ):
                    if url_key not in STUDIO_ANALYTICS_URLS:
                        continue
                    await enable_background_focus_emulation(active_client)
                    await active_client.send("Page.navigate", {"url": STUDIO_ANALYTICS_URLS[url_key]})
                    for _ in range(12):
                        await asyncio.sleep(1.0)
                        txt_len = await active_client.eval("(document.body ? document.body.innerText : '').length")
                        if txt_len and int(txt_len) > 900:
                            break
                    await asyncio.sleep(1.8)
                    verified_period: str | None = None
                    if p_hint == "7d":
                        probe_7d = await self._ensure_studio_analytics_period_7d(active_client)
                        scraped["period_7d_probe_meta"][tab_key] = probe_7d
                        verified_period = probe_7d.get("dom_period") if isinstance(probe_7d, dict) else None
                    tab_text = str(await active_client.eval("document.body ? document.body.innerText : ''") or "")
                    scraped["raw_page_snippets"][tab_key] = tab_text[:4000]
                    scraped[target_field] = self._parse_analytics_text_block(
                        tab_text,
                        period_hint=p_hint,
                        verified_dom_period=verified_period,
                    )

                per_video_analytics: dict[str, dict[str, Any]] = {}
                row_map_now = scraped.get("video_row_metrics") or {}
                candidate_vids = [
                    vk
                    for vk in dict.fromkeys([v for v in (known_video_ids or []) if v] + list(row_map_now.keys()))
                    if "Scheduled" not in str(row_map_now.get(vk) or "")
                    and "예약됨" not in str(row_map_now.get(vk) or "")
                ]
                for vid_key in candidate_vids:
                    try:
                        await enable_background_focus_emulation(active_client)
                        await active_client.send(
                            "Page.navigate",
                            {"url": f"https://studio.youtube.com/video/{vid_key}/analytics/tab-overview/period-default"},
                        )
                        for _ in range(10):
                            await asyncio.sleep(0.7)
                            t_len = await active_client.eval("(document.body ? document.body.innerText : '').length")
                            if t_len and int(t_len) > 900:
                                break
                        await asyncio.sleep(1.0)
                        v_ov_text = str(await active_client.eval("document.body ? document.body.innerText : ''") or "")
                        pv_data = self._parse_video_analytics_overview(v_ov_text)
                        row_parsed = self._parse_video_row_text(str(row_map_now.get(vid_key) or ""))
                        est_views = int(pv_data.get("views") if pv_data.get("views") is not None else (row_parsed.get("views") or 0))
                        if est_views > 0 and (pv_data.get("avd_sec") is None or pv_data.get("apv_pct") is None):
                            await active_client.send(
                                "Page.navigate",
                                {"url": f"https://studio.youtube.com/video/{vid_key}/analytics/tab-interest_viewers/period-default"},
                            )
                            for _ in range(10):
                                await asyncio.sleep(0.7)
                                e_len = await active_client.eval("(document.body ? document.body.innerText : '').length")
                                if e_len and int(e_len) > 900:
                                    break
                            await asyncio.sleep(1.0)
                            v_eng_text = str(await active_client.eval("document.body ? document.body.innerText : ''") or "")
                            eng_data = self._parse_video_analytics_overview(v_eng_text)
                            for ek, ev in eng_data.items():
                                if pv_data.get(ek) is None and ev is not None:
                                    pv_data[ek] = ev
                        per_video_analytics[vid_key] = pv_data
                    except Exception:
                        pass
                scraped["per_video_analytics"] = per_video_analytics

        except Exception as e:
            print(f"[StudioReporter] Live DOM inspection warning: {e}")

        return scraped

    @staticmethod
    def _parse_video_analytics_overview(text: str) -> dict[str, Any]:
        """Extracts real per-video views, engaged views, watch hours, subscribers, likes, Stayed to watch %, AVD, APV, and 30s retention from YouTube Studio Video Analytics/Insights tabs."""
        out: dict[str, Any] = {}
        if not text:
            return out
        m_v = re.search(r"This (?:Short|video) has (?:had|got|gotten)\s+(\d[\d,]*|one)\s+view", text, re.IGNORECASE)
        if m_v:
            raw_v = m_v.group(1).lower()
            out["views"] = 1 if raw_v == "one" else int(raw_v.replace(",", ""))
        else:
            m_vcard = re.search(
                r"(?:^|\n)Views\s*\n\s*(\d[\d,]*(?:\.\d+)?)\s*([KMB])?(?=\s*\n)",
                text,
                re.IGNORECASE,
            )
            if m_vcard:
                out["views"] = _StudioScrapeMixin._scale_compact_count(m_vcard.group(1), m_vcard.group(2))

        m_eng = re.search(
            r"(?:^|\n)Engaged views\s*\n\s*(\d[\d,]*(?:\.\d+)?)\s*([KMB])?(?=\s*\n)",
            text,
            re.IGNORECASE,
        )
        if m_eng:
            out["engaged_views"] = _StudioScrapeMixin._scale_compact_count(m_eng.group(1), m_eng.group(2))

        m_wh = re.search(r"Watch time \(hours\)\s*\n\s*(\d[\d,]*(?:\.\d+)?)", text, re.IGNORECASE)
        if m_wh:
            out["watch_hours"] = round(float(m_wh.group(1).replace(",", "")), 2)

        m_sub = re.search(r"Subscribers\s*\n\s*([+-]?\d[\d,]*)", text, re.IGNORECASE)
        if m_sub:
            out["subs_gained"] = max(0, int(m_sub.group(1).replace(",", "")))

        m_likes = re.search(
            r"(?:^|\n)Likes\s*\n(?:\s*Since published\s*\n)?\s*(\d[\d,]*)",
            text,
            re.IGNORECASE,
        )
        if m_likes:
            out["likes"] = int(m_likes.group(1).replace(",", ""))

        m_stay_before = re.search(
            r"(\d+(?:\.\d+)?)\s*%\s*\n\s*Stayed to watch(?:\s*\n\s*(\d+(?:\.\d+)?)\s*%\s*\n\s*Swiped away)?",
            text,
            re.IGNORECASE,
        )
        if m_stay_before:
            out["viewed_pct"] = round(float(m_stay_before.group(1)), 1)
            out["swiped_pct"] = (
                round(float(m_stay_before.group(2)), 1)
                if m_stay_before.group(2)
                else round(100.0 - out["viewed_pct"], 1)
            )
        else:
            m_stay = re.search(
                r"Stayed to watch\s*\n\s*(\d+(?:\.\d+)?)\s*%(?!\s*\n\s*Swiped away)",
                text,
                re.IGNORECASE,
            )
            if m_stay:
                out["viewed_pct"] = round(float(m_stay.group(1)), 1)
                out["swiped_pct"] = round(100.0 - out["viewed_pct"], 1)

        m_avd = (
            re.search(r"Average view duration\s*\n\s*(\d+):(\d{2})", text, re.IGNORECASE)
            or re.search(r"(?!0:00\b)(\d+):(\d{2})\s*\n\s*Average view duration", text, re.IGNORECASE)
        )
        if m_avd:
            out["avd_sec"] = float(int(m_avd.group(1)) * 60 + int(m_avd.group(2)))

        m_apv = (
            re.search(
                r"Average percentage viewed\s*\n\s*(\d+(?:\.\d+)?)\s*%(?!\s*\n\s*(?:Still watching|Swiped away|Stayed to watch))",
                text,
                re.IGNORECASE,
            )
            or re.search(r"(?!0(?:\.0+)?\s*%)(\d+(?:\.\d+)?)\s*%\s*\n\s*Average percentage viewed", text, re.IGNORECASE)
        )
        if m_apv:
            out["apv_pct"] = round(float(m_apv.group(1)), 1)

        m_30s = (
            re.search(r"(\d+(?:\.\d+)?)\s*%\s*\n\s*Still watching at 0?0:30", text, re.IGNORECASE)
            or re.search(r"(\d+(?:\.\d+)?)%\s+of viewers are still watching at around the 0:30 mark", text, re.IGNORECASE)
        )
        if m_30s:
            out["ret_30s_mark_pct"] = round(float(m_30s.group(1)), 1)

        m_rt = (
            re.search(r"48-hour views\s*\n\s*(\d[\d,]*)", text, re.IGNORECASE)
            or re.search(r"(\d[\d,]*)\s*\n\s*Views\s*·\s*Last 48 hours", text, re.IGNORECASE)
        )
        if m_rt:
            out["realtime_48h"] = int(m_rt.group(1).replace(",", ""))
        return out

    @staticmethod
    def _scale_compact_count(raw_num: str, suffix: str | None = None) -> int:
        val = float(raw_num.replace(",", ""))
        suf = (suffix or "").strip().upper()
        mult_map = {
            "K": 1_000.0,
            "M": 1_000_000.0,
            "B": 1_000_000_000.0,
            "천": 1_000.0,
            "만": 10_000.0,
            "억": 100_000_000.0,
        }
        return int(round(val * mult_map.get(suf, 1.0)))

    @staticmethod
    def _parse_video_row_text(row_text: str) -> dict[str, Any]:
        """Extracts per-video views, comments, and likes from a single- or multi-line ytcp-video-row text block."""
        parsed: dict[str, Any] = {}
        if not row_text:
            return parsed

        views_m = re.search(
            r"(\d[\d,]*(?:\.\d+)?)\s*([KMB천만억])?\s*(?:views|조회수|회)",
            row_text,
            re.IGNORECASE,
        )
        if views_m:
            parsed["views"] = _StudioScrapeMixin._scale_compact_count(views_m.group(1), views_m.group(2))
        else:
            tail_nums = re.findall(
                r"(?:Public|Unlisted|Scheduled|공개|일부 공개|예약됨).*?"
                r"(?:202\d\.\s*\d{1,2}\.\s*\d{1,2}\.?|[A-Za-z]{3,9}\s+\d{1,2}(?:,\s*202\d)?|\d{1,2}\s+[A-Za-z]{3,9}(?:,?\s*202\d)?|202\d[\.\-/]\d{1,2}[\.\-/]\d{1,2}|202\d)"
                r"(?:\s*(?:Published|Scheduled|Uploaded|게시됨|예약됨|업로드됨))?"
                r"\s+(\d[\d,]*(?:\.\d+)?)\s*([KMB천만억])?\s+(\d[\d,]*)",
                row_text,
                re.IGNORECASE | re.DOTALL,
            )
            if tail_nums:
                last_match = tail_nums[-1]
                parsed["views"] = _StudioScrapeMixin._scale_compact_count(last_match[0], last_match[1])
                parsed["comments"] = int(last_match[2].replace(",", ""))

        comm_m = re.search(r"(\d[\d,]*)\s*(?:comments|댓글)", row_text, re.IGNORECASE)
        if comm_m:
            parsed["comments"] = int(comm_m.group(1).replace(",", ""))

        likes_m = re.search(r"(\d[\d,]*)\s*(?:likes|좋아요)", row_text, re.IGNORECASE)
        if likes_m:
            parsed["likes"] = int(likes_m.group(1).replace(",", ""))

        return parsed

    @staticmethod
    async def _ensure_studio_analytics_period_7d(active_client: Any) -> dict[str, Any]:
        """
        Verifies and actively switches the YouTube Studio Analytics SPA tab to `7 days` / `Last 7 days` / `지난 7일`.
        Supports BOTH:
          1. New YouTube Studio Insights Hub (`/analytics/hub_overview`, `/analytics/hub_audience`)
             where `7 days | 28 days | 90 days` are `button[role="tab"]` chips (`aria-selected="true"`).
          2. Classic YouTube Studio Analytics (`yta-time-picker` / `ytcp-dropdown-trigger` -> `Last 7 days`).
        Never relies on `/period-week` URL alone because YouTube Studio SPA redirects `/period-week` to
        `/analytics/hub_overview` defaulting to `28 days`.
        """
        meta: dict[str, Any] = {"switched": False, "method": "unverified", "final_url": "", "dom_period": None}
        deep_helper = """
        const __queryAllDeep = (sel, root = document) => {
            const out = [];
            const walk = (node) => {
                if (!node) return;
                if (node.querySelectorAll) {
                    for (const el of node.querySelectorAll(sel)) out.push(el);
                }
                const kids = node.querySelectorAll ? node.querySelectorAll('*') : [];
                for (const k of kids) {
                    if (k.shadowRoot) walk(k.shadowRoot);
                }
            };
            walk(root);
            return out;
        };
        """
        try:
            # 1) Try new YouTube Studio Insights Hub `7 days` tab chip (button[role="tab"] / ytcp-chip)
            hub_js = f"""
            (async () => {{
                {deep_helper}
                const sevenTabRe = /^(?:7\\s*days|Last\\s+7\\s+days|7일|지난\\s*7일|최근\\s*7일)$/i;
                const tabs = __queryAllDeep('button[role="tab"], ytcp-chip, tp-yt-paper-tab, [role="tab"]');
                let target = null;
                for (const el of tabs) {{
                    const rect = el.getBoundingClientRect ? el.getBoundingClientRect() : null;
                    if (!rect || rect.width < 18 || rect.height < 14) continue;
                    const txt = (el.innerText || el.textContent || '').trim().replace(/\\s+/g, ' ');
                    if (sevenTabRe.test(txt)) {{
                        target = el;
                        break;
                    }}
                }}
                if (!target) {{
                    return {{ found: false }};
                }}
                const wasSelected = target.getAttribute('aria-selected') === 'true';
                const preHead = (document.body ? document.body.innerText : '').slice(0, 1400);
                if (!wasSelected) {{
                    target.click();
                    for (let i = 0; i < 12; i++) {{
                        await new Promise(res => setTimeout(res, 450));
                        const nowSel = target.getAttribute('aria-selected') === 'true';
                        const nowHead = (document.body ? document.body.innerText : '').slice(0, 1400);
                        if (nowSel && nowHead !== preHead) break;
                    }}
                    await new Promise(res => setTimeout(res, 750));
                }}
                const isSelected = target.getAttribute('aria-selected') === 'true';
                return {{
                    found: true,
                    was_selected: wasSelected,
                    is_selected: isSelected,
                    chip_text: (target.innerText || target.textContent || '').trim(),
                    url: window.location.href || '',
                }};
            }})()
            """
            hub_res = await active_client.eval(hub_js, await_promise=True)
            meta["hub_chip"] = hub_res
            if isinstance(hub_res, dict) and hub_res.get("found"):
                meta["final_url"] = str(hub_res.get("url") or "")
                if hub_res.get("is_selected"):
                    meta["switched"] = True
                    meta["method"] = "hub_tab_chip_already_active" if hub_res.get("was_selected") else "hub_tab_chip_click"
                    meta["dom_period"] = "7d"
                    return meta
                meta["dom_period"] = "28d"
                return meta

            # 2) Fallback: classic YouTube Studio Analytics date-range picker dropdown
            cur_text = str(await active_client.eval("document.body ? document.body.innerText : ''") or "")
            cur_url = str(await active_client.eval("window.location.href || ''") or "")
            cur_period = _StudioScrapeMixin._detect_analytics_dom_period(cur_text)
            meta["final_url"] = cur_url
            meta["dom_period"] = cur_period
            if cur_period == "7d":
                meta["switched"] = True
                meta["method"] = "url_native"
                return meta

            click_js = f"""
            (async () => {{
                {deep_helper}
                const periodTriggerRe = /(Last\\s+(?:28|90|365)\\s+days|Lifetime|지난\\s*(?:28|90|365)일|전체\\s*기간)/i;
                const sevenDayRe = /^(?:Last\\s+7\\s+days|지난\\s*7일|최근\\s*7일)$/i;
                const sevenDayLooseRe = /(?:Last\\s+7\\s+days|지난\\s*7일|최근\\s*7일)/i;

                const triggerCandidates = [
                    ...__queryAllDeep('yta-time-picker ytcp-dropdown-trigger'),
                    ...__queryAllDeep('yta-time-picker button, yta-time-picker [role="button"]'),
                    ...__queryAllDeep('ytcp-dropdown-trigger'),
                    ...__queryAllDeep('button, [role="button"]'),
                ];
                let trigger = null;
                for (const el of triggerCandidates) {{
                    const rect = el.getBoundingClientRect ? el.getBoundingClientRect() : null;
                    if (!rect || rect.width < 20 || rect.height < 14 || rect.top > 260) continue;
                    const txt = (el.innerText || el.textContent || el.getAttribute('aria-label') || '').trim();
                    if (periodTriggerRe.test(txt)) {{
                        trigger = el;
                        break;
                    }}
                }}
                if (!trigger) {{
                    return {{ opened: false, clicked_7d: false, reason: 'picker_trigger_not_found' }};
                }}
                trigger.click();
                await new Promise(res => setTimeout(res, 700));

                const optionCandidates = [
                    ...__queryAllDeep('tp-yt-paper-item'),
                    ...__queryAllDeep('ytcp-text-menu tp-yt-paper-item, ytcp-text-menu [role="option"], ytcp-text-menu [role="menuitem"]'),
                    ...__queryAllDeep('[role="option"], [role="menuitem"], ytcp-ve'),
                ];
                let opt = null;
                for (const el of optionCandidates) {{
                    const rect = el.getBoundingClientRect ? el.getBoundingClientRect() : null;
                    if (!rect || rect.width < 20 || rect.height < 14) continue;
                    const txt = (el.innerText || el.textContent || '').trim().replace(/\\s+/g, ' ');
                    if (sevenDayRe.test(txt)) {{
                        opt = el;
                        break;
                    }}
                }}
                if (!opt) {{
                    for (const el of optionCandidates) {{
                        const rect = el.getBoundingClientRect ? el.getBoundingClientRect() : null;
                        if (!rect || rect.width < 20 || rect.height < 14) continue;
                        const txt = (el.innerText || el.textContent || '').trim().replace(/\\s+/g, ' ');
                        if (sevenDayLooseRe.test(txt) && txt.length < 40) {{
                            opt = el;
                            break;
                        }}
                    }}
                }}
                if (!opt) {{
                    document.dispatchEvent(new KeyboardEvent('keydown', {{ key: 'Escape', bubbles: true }}));
                    return {{ opened: true, clicked_7d: false, reason: 'option_7d_not_found' }};
                }}
                opt.click();
                return {{ opened: true, clicked_7d: true, opt_text: (opt.innerText || opt.textContent || '').trim() }};
            }})()
            """
            res = await active_client.eval(click_js, await_promise=True)
            meta["picker_click"] = res
            if isinstance(res, dict) and res.get("clicked_7d"):
                for _ in range(10):
                    await asyncio.sleep(0.8)
                    new_text = str(await active_client.eval("document.body ? document.body.innerText : ''") or "")
                    new_period = _StudioScrapeMixin._detect_analytics_dom_period(new_text)
                    if new_period == "7d":
                        meta["switched"] = True
                        meta["method"] = "date_picker_click"
                        meta["dom_period"] = "7d"
                        meta["final_url"] = str(await active_client.eval("window.location.href || ''") or "")
                        await asyncio.sleep(0.8)
                        return meta
            meta["final_url"] = str(await active_client.eval("window.location.href || ''") or "")
            final_text = str(await active_client.eval("document.body ? document.body.innerText : ''") or "")
            meta["dom_period"] = _StudioScrapeMixin._detect_analytics_dom_period(final_text)
            meta["switched"] = meta["dom_period"] == "7d"
        except Exception as exc:
            meta["error"] = f"{type(exc).__name__}: {exc}"
        return meta

    @staticmethod
    def _detect_analytics_dom_period(text: str) -> str | None:
        """
        Detects the active Analytics date range actually rendered in YouTube Studio DOM text.
        Returns `'7d'` ONLY when explicit 7-day markers (`Last 7 days` / `지난 7일`) appear without
        conflicting 28-day headers (`Last 28 days` / `지난 28일`), `'28d'` when 28-day markers appear,
        `'other'` for 90d/365d/Lifetime, or `None` when ambiguous/unmarked.
        """
        if not text:
            return None
        has_7d = bool(re.search(r"(?:last\s+7\s+days|지난\s*7일|최근\s*7일)", text, re.IGNORECASE))
        has_28d = bool(re.search(r"(?:last\s+28\s+days|지난\s*28일|최근\s*28일)", text, re.IGNORECASE))
        if has_7d and not has_28d:
            return "7d"
        if has_28d and not has_7d:
            return "28d"
        if has_7d and has_28d:
            # Disambiguate using primary headline / top picker header (first 900 chars of DOM)
            head = text[:900]
            head_7d = bool(re.search(r"(?:last\s+7\s+days|지난\s*7일|최근\s*7일)", head, re.IGNORECASE))
            head_28d = bool(re.search(r"(?:last\s+28\s+days|지난\s*28일|최근\s*28일)", head, re.IGNORECASE))
            if head_7d and not head_28d:
                return "7d"
            if head_28d and not head_7d:
                return "28d"
            # Both appear in header/summary -> refuse to treat as clean 7d
            return "28d"
        if re.search(r"(?:last\s+(?:90|365)\s+days|lifetime|지난\s*(?:90|365)일|전체\s*기간)", text, re.IGNORECASE):
            return "other"
        return None

    @staticmethod
    def _parse_analytics_text_block(
        text: str,
        period_hint: str = "28d",
        verified_dom_period: str | None = None,
    ) -> dict[str, Any]:
        """Extracts period-honest numeric KPIs from YouTube Studio Analytics/Insights/Dashboard innerText (never clones 28d -> 7d or 24h)."""
        parsed: dict[str, Any] = {}
        if not text:
            return parsed
        p_key = "7d" if str(period_hint).strip().lower() in ("7d", "week", "period-week") else (
            "24h" if str(period_hint).strip().lower() in ("24h", "day") else "28d"
        )
        dom_period = (
            str(verified_dom_period).strip().lower()
            if verified_dom_period is not None and str(verified_dom_period).strip()
            else _StudioScrapeMixin._detect_analytics_dom_period(text)
        )
        # Strict DOM period agreement guard (R_7D_GUARD):
        # When scraping `7d`, require explicit 7-day DOM confirmation (`Last 7 days` / `지난 7일`,
        # or live verified `aria-selected="true"` on the Insights Hub `7 days` chip)
        # and strictly block recording 7d metrics if `Last 28 days` / `지난 28일` remained on screen.
        allow_period_generic = (dom_period == "7d") if p_key == "7d" else (dom_period != "7d")

        got_views_7d_m = re.search(
            r"got\s+(\d[\d,]*(?:\.\d+)?)\s*([KMB])?\s+views\s+in\s+the\s+last\s+7\s+days",
            text,
            re.IGNORECASE,
        ) or re.search(
            r"지난\s*7일[^\n]{0,40}?조회수[^\d\n]{0,12}(\d[\d,]*(?:\.\d+)?)\s*([KMB천만억])?",
            text,
            re.IGNORECASE,
        )
        got_views_28d_m = re.search(
            r"got\s+(\d[\d,]*(?:\.\d+)?)\s*([KMB])?\s+views\s+in\s+the\s+last\s+28\s+days",
            text,
            re.IGNORECASE,
        ) or re.search(
            r"지난\s*28일[^\n]{0,40}?조회수[^\d\n]{0,12}(\d[\d,]*(?:\.\d+)?)\s*([KMB천만억])?",
            text,
            re.IGNORECASE,
        )
        if got_views_7d_m:
            parsed["views_7d"] = _StudioScrapeMixin._scale_compact_count(got_views_7d_m.group(1), got_views_7d_m.group(2))
        elif got_views_28d_m:
            if p_key != "7d":
                parsed["views_28d"] = _StudioScrapeMixin._scale_compact_count(got_views_28d_m.group(1), got_views_28d_m.group(2))
        elif allow_period_generic:
            views_m = re.search(
                r"(?:^|\n)(?:Views|조회수)\s*[:\n\t]+\s*(\d[\d,]*(?:\.\d+)?)\s*([KMB천만억])?(?![A-Za-z%])",
                text,
                re.IGNORECASE,
            )
            if views_m:
                parsed[f"views_{p_key}"] = _StudioScrapeMixin._scale_compact_count(views_m.group(1), views_m.group(2))

        views_24h_m = (
            re.search(r"24-hour\s+views\s*\n\s*(\d[\d,]*(?:\.\d+)?)\s*([KMB천만억])?", text, re.IGNORECASE)
            or re.search(r"(\d[\d,]*(?:\.\d+)?)\s*([KMB천만억])?\s*\n\s*Views\s*[·•]\s*Last\s+24\s+hours", text, re.IGNORECASE)
        )
        if views_24h_m:
            parsed["views_24h"] = _StudioScrapeMixin._scale_compact_count(views_24h_m.group(1), views_24h_m.group(2))

        eng_m = re.search(
            r"(?:^|\n)(?:Engaged views|유효 조회수)\s*[:\n\t]+\s*(\d[\d,]*(?:\.\d+)?)\s*([KMB천만억])?(?![A-Za-z%])",
            text,
            re.IGNORECASE,
        )
        if eng_m:
            parsed["engaged_views"] = _StudioScrapeMixin._scale_compact_count(eng_m.group(1), eng_m.group(2))

        tv_m = re.search(
            r"(?:^|\n)(?:TV|스마트\s*TV|거실\s*TV)\s*[:\n·\t ]+\s*(\d+(?:\.\d+)?)\s*%",
            text,
            re.IGNORECASE,
        )
        if tv_m:
            parsed["tv_device_pct"] = float(tv_m.group(1))

        ypp_wh_m = re.search(
            r"(\d[\d,]*(?:\.\d+)?)\s*(?:valid public watch hours|공개 시청 시간)",
            text,
            re.IGNORECASE,
        )
        if ypp_wh_m:
            parsed["ypp_longform_watch_hours_365d"] = float(ypp_wh_m.group(1).replace(",", ""))

        ypp_sh_m = re.search(
            r"(\d[\d,]*(?:\.\d+)?)\s*([KM])?\s*(?:public Shorts views|공개 Shorts 조회수)",
            text,
            re.IGNORECASE,
        )
        if ypp_sh_m:
            raw_sh = float(ypp_sh_m.group(1).replace(",", ""))
            sh_suf = (ypp_sh_m.group(2) or "").upper()
            sh_mult = 1_000_000.0 if sh_suf == "M" else (1_000.0 if sh_suf == "K" else 1.0)
            parsed["ypp_shorts_engaged_90d"] = int(round(raw_sh * sh_mult))

        likes_m = re.search(
            r"(?:^|\n)Likes\s*\n\s*(\d[\d,]*)",
            text,
            re.IGNORECASE,
        )
        if likes_m:
            parsed["likes_total"] = int(likes_m.group(1).replace(",", ""))

        if allow_period_generic:
            watch_m = re.search(
                r"(?:Watch time \(hours\)|시청 시간\(단위:\s*시간\))\s*[:\n\t]+\s*(\d[\d,]*(?:\.\d+)?)",
                text,
                re.IGNORECASE,
            )
            if watch_m:
                parsed[f"watch_hours_{p_key}"] = float(watch_m.group(1).replace(",", ""))

        subs_m = (
            re.search(r"(?:Total|Current)\s+subscribers\s*\n\s*(\d[\d,]*)", text, re.IGNORECASE)
            or re.search(r"(\d[\d,]*)\s*\n\s*Subscribers\s*\n\s*(?:See|View)\s+live\s+count", text, re.IGNORECASE)
        )
        if subs_m:
            parsed["subscribers_total"] = int(subs_m.group(1).replace(",", ""))

        # Strict period-isolated subscriber delta matching (zero 28d -> 7d cross-contamination!)
        subs_7d_m = re.search(r"([+-]?\d[\d,]*)\s+in\s+(?:the\s+)?last\s+7\s+days", text, re.IGNORECASE)
        if subs_7d_m:
            parsed["subscribers_gained_7d"] = int(subs_7d_m.group(1).replace(",", ""))

        subs_28d_m = re.search(r"([+-]?\d[\d,]*)\s+in\s+(?:the\s+)?last\s+28\s+days", text, re.IGNORECASE)
        if subs_28d_m and p_key != "7d":
            parsed["subscribers_gained_28d"] = int(subs_28d_m.group(1).replace(",", ""))

        if allow_period_generic and f"subscribers_gained_{p_key}" not in parsed:
            subs_card_m = re.search(r"(?:^|\n)(?:Subscribers|구독자)\s*[:\n]+\s*([+-]\d[\d,]*)", text, re.IGNORECASE)
            if subs_card_m:
                parsed[f"subscribers_gained_{p_key}"] = int(subs_card_m.group(1).replace(",", ""))

        rt48_m = (
            re.search(r"48-hour\s+views\s*\n\s*(\d[\d,]*)", text, re.IGNORECASE)
            or re.search(r"(\d[\d,]*)\s*\n\s*Views\s*[·•]\s*Last\s+48\s+hours", text, re.IGNORECASE)
            or re.search(r"(?:Last 48 hours|지난 48시간)[^\d]{0,40}(\d[\d,]*)", text, re.IGNORECASE)
        )
        if rt48_m:
            parsed["realtime_48h_views"] = int(rt48_m.group(1).replace(",", ""))

        rt60_m = (
            re.search(r"60-minute\s+views\s*\n\s*(\d[\d,]*(?:\.\d+)?)\s*([KMB천만억])?", text, re.IGNORECASE)
            or re.search(r"(\d[\d,]*(?:\.\d+)?)\s*([KMB천만억])?\s*\n\s*Views\s*[·•]\s*Last\s+60\s+minutes", text, re.IGNORECASE)
            or re.search(r"(?:Last 60 minutes|지난 60분)[^\d\n]{0,40}(\d[\d,]*(?:\.\d+)?)\s*([KMB천만억])?", text, re.IGNORECASE)
        )
        if rt60_m:
            parsed["realtime_60m_views"] = _StudioScrapeMixin._scale_compact_count(rt60_m.group(1), rt60_m.group(2))

        if allow_period_generic:
            uniq_m = re.search(
                r"(?:^|\n)(?:Unique viewers|순\s*시청자(?:수)?)\s*[:\n\t]+\s*(\d[\d,]*(?:\.\d+)?)\s*([KMB천만억])?(?![A-Za-z%])",
                text,
                re.IGNORECASE,
            )
            if uniq_m:
                parsed[f"unique_viewers_{p_key}"] = _StudioScrapeMixin._scale_compact_count(uniq_m.group(1), uniq_m.group(2))

        sub_watch_m = re.search(
            r"(\d+(?:\.\d+)?)\s*%\s*\n\s*Subscribed\s*\n\s*(\d+(?:\.\d+)?)\s*%\s*\n\s*Not\s+subscribed",
            text,
            re.IGNORECASE,
        )
        if sub_watch_m:
            parsed["subscribed_watch_pct"] = round(float(sub_watch_m.group(1)), 1)
            parsed["non_subscribed_watch_pct"] = round(float(sub_watch_m.group(2)), 1)

        new_v_m = re.search(
            r"New viewers\s*\n\s*(\d+(?:\.\d+)?)\s*%",
            text,
            re.IGNORECASE,
        )
        if new_v_m:
            new_p = float(new_v_m.group(1))
            parsed["new_viewers_pct"] = round(new_p, 1)
            parsed["returning_viewers_pct"] = round(max(0.0, 100.0 - new_p), 1)
        else:
            ret_v_m = re.search(
                r"(?:Returning viewers|재방문 시청자)[^\d]{0,40}(\d+(?:\.\d+)?)\s*%",
                text,
                re.IGNORECASE,
            )
            if ret_v_m:
                parsed["returning_viewers_pct"] = float(ret_v_m.group(1))

        avd_match = (
            re.search(r"(?:Average view duration|평균 시청 지속 시간)[^\d]{0,40}(\d+):(\d{2})", text, re.IGNORECASE)
            or re.search(r"(?!0:00\b)(\d+):(\d{2})\s*\n\s*(?:Average view duration|평균 시청 지속 시간)", text, re.IGNORECASE)
        )
        if avd_match:
            mins = int(avd_match.group(1))
            secs = int(avd_match.group(2))
            parsed["avd_seconds"] = float(mins * 60 + secs)

        apv_match = (
            re.search(
                r"(?:Average percentage viewed|평균 시청률)\s*[:\n\t]+\s*(\d+(?:\.\d+)?)\s*%(?!\s*\n\s*(?:Still watching|Swiped away|Stayed to watch))",
                text,
                re.IGNORECASE,
            )
            or re.search(r"(?!0(?:\.0+)?\s*%)(\d+(?:\.\d+)?)\s*%\s*\n\s*(?:Average percentage viewed|평균 시청률)", text, re.IGNORECASE)
        )
        if apv_match:
            parsed["apv_pct"] = float(apv_match.group(1))

        stayed_new_m = re.search(
            r"(\d+(?:\.\d+)?)\s*%\s*\n\s*Stayed to watch\s*\n\s*(\d+(?:\.\d+)?)\s*%\s*\n\s*Swiped away",
            text,
            re.IGNORECASE,
        )
        stayed_m = re.search(
            r"(\d+(?:\.\d+)?)\s*%\s*\n\s*(\d+(?:\.\d+)?)\s*%\s*\n\s*Stayed to watch\s*\n\s*Swiped away",
            text,
            re.IGNORECASE,
        )
        if stayed_new_m:
            parsed["viewed_pct"] = round(float(stayed_new_m.group(1)), 1)
            parsed["swiped_pct"] = round(float(stayed_new_m.group(2)), 1)
        elif stayed_m:
            parsed["viewed_pct"] = round(float(stayed_m.group(1)), 1)
            parsed["swiped_pct"] = round(float(stayed_m.group(2)), 1)
        else:
            viewed_match = re.search(
                r"(?:Viewed|Stayed to watch|시청함)[^\d]{0,30}(\d+(?:\.\d+)?)\s*%(?!\s*\n\s*Swiped away)",
                text,
                re.IGNORECASE,
            )
            if viewed_match:
                v_pct = float(viewed_match.group(1))
                if 0.0 < v_pct <= 100.0:
                    parsed["viewed_pct"] = round(v_pct, 1)
                    parsed["swiped_pct"] = round(100.0 - v_pct, 1)

        ctr_match = re.search(
            r"(?:Impressions click-through rate|노출 클릭률)[^\d]{0,40}(\d+(?:\.\d+)?)\s*%",
            text,
            re.IGNORECASE,
        )
        if ctr_match:
            parsed["ctr_pct"] = float(ctr_match.group(1))

        # Traffic sources (from Content tab)
        ts_map: dict[str, float] = {}
        for ts_key in ["Shorts feed", "YouTube search", "Other YouTube features", "Channel pages", "External", "Others"]:
            m_ts = re.search(rf"{re.escape(ts_key)}\s*\n+\s*(\d+(?:\.\d+)?)\s*%", text, re.IGNORECASE)
            if m_ts:
                ts_map[ts_key] = round(float(m_ts.group(1)), 1)
        if ts_map:
            parsed["traffic_sources_map"] = ts_map

        # Geographies (from Audience tab)
        geo_map: dict[str, float] = {}
        for g_name, g_code in [("United States", "US"), ("United Kingdom", "UK"), ("Canada", "CA"), ("Australia", "AU"), ("India", "IN")]:
            m_g = re.search(rf"{re.escape(g_name)}\s*\n+\s*(\d+(?:\.\d+)?)\s*%", text, re.IGNORECASE)
            if m_g:
                geo_map[g_code] = round(float(m_g.group(1)), 1)
        if geo_map:
            parsed["geographies_map"] = geo_map

        # Demographics (from Audience tab)
        m_fem = re.search(r"\bFemale\s*\n\s*(\d+(?:\.\d+)?)\s*%", text, re.IGNORECASE)
        m_male = re.search(r"\bMale\s*\n\s*(\d+(?:\.\d+)?)\s*%", text, re.IGNORECASE)
        if m_fem and m_male:
            parsed["female_pct"] = round(float(m_fem.group(1)), 1)
            parsed["male_pct"] = round(float(m_male.group(1)), 1)

        for age_lbl, age_key in [
            ("18–24 years", "age_18_24"),
            ("25–34 years", "age_25_34"),
            ("35–44 years", "age_35_44"),
            ("45–54 years", "age_45_54"),
            ("55–64 years", "age_55_64"),
            ("65+ years", "age_65_plus"),
        ]:
            m_age = re.search(rf"{re.escape(age_lbl)}\s*\n\s*(\d+(?:\.\d+)?)\s*%", text, re.IGNORECASE)
            if m_age:
                parsed[age_key] = round(float(m_age.group(1)), 1)

        return parsed

    def _load_previous_snapshot(
        self,
        report_date: str,
        compare_date: str | None = None,
    ) -> tuple[str, dict[str, Any] | None]:
        """Finds and loads the previous daily JSON snapshot for Day-over-Day comparison."""
        if compare_date:
            candidate = self.reports_dir / f"{compare_date}_studio_metrics.json"
            if candidate.exists():
                try:
                    return compare_date, json.loads(candidate.read_text(encoding="utf-8"))
                except Exception:
                    pass

        existing_files = sorted(self.reports_dir.glob("*_studio_metrics.json"))
        prior_candidates = [
            f for f in existing_files
            if f.name[:10] < report_date
        ]
        if prior_candidates:
            latest_prior = prior_candidates[-1]
            prior_date = latest_prior.name[:10]
            try:
                return prior_date, json.loads(latest_prior.read_text(encoding="utf-8"))
            except Exception:
                pass

        return "2026-10-14 (Baseline)", None

    def _load_historical_snapshots(self, report_date: str) -> dict[str, dict[str, Any]]:
        """Loads all valid historical `YYYY-MM-DD_studio_metrics.json` snapshots up to `report_date`."""
        snapshots: dict[str, dict[str, Any]] = {}
        if not self.reports_dir.exists():
            return snapshots
        for f in sorted(self.reports_dir.glob("*_studio_metrics.json")):
            d_key = f.name[:10]
            if not re.match(r"^\d{4}-\d{2}-\d{2}$", d_key) or d_key > report_date:
                continue
            try:
                snap = json.loads(f.read_text(encoding="utf-8"))
                if isinstance(snap, dict) and "channel_kpis" in snap:
                    pk = snap.get("channel_kpis") or {}
                    pr = snap.get("retention_kpis") or {}
                    is_synth = snap.get("data_source_mode") != "LIVE_CDP_DOM" and (
                        int(pk.get("views_24h", 0)) >= 3000
                        or int(pk.get("realtime_48h_views", 0)) >= 3000
                        or float(pr.get("apv_pct", 0.0)) >= 85.0
                    )
                    if is_synth:
                        continue
                    snapshots[d_key] = snap
            except Exception:
                continue
        return snapshots

