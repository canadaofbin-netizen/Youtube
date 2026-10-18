"""
Master Wave Orchestrator for ALL ABOUT BRAIN 100-Video Production & YouTube Studio Scheduling
===============================================================================================
- Processes projects in capped Waves of at most FLOW_MAX_PARALLEL_BATCH_SIZE = 5 projects at a time (R37 Guard 6).
- Each project runs in its own dedicated 1:1:1 Google Flow browser tab via run_live_flow_for_single_project.
- Skips projects that already have a valid 05_assembly/final_shorts_1080x1920.mp4 (>= 1MB).
- Writes live wave progress to BCI_Shorts_Channel/wave_production_status.json.
"""

from __future__ import annotations
import argparse
import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time
import urllib.request
from typing import Any

WORKSPACE_ROOT = Path(__file__).resolve().parents[1] if "scratch" not in str(Path(__file__).resolve()) else Path("/home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube")
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from pipeline.config import (
    FLOW_MAX_PARALLEL_BATCH_SIZE,
    MIN_CLIP_SIZE_BYTES,
    PROJECTS_DIR,
)
from pipeline.flow_live_single_worker import (
    allocate_dedicated_flow_project_tab,
    run_live_flow_for_single_project,
)
from pipeline.topics_catalog import ALL_PSYCHOLOGY_100_TOPICS

STATUS_FILE = WORKSPACE_ROOT / "BCI_Shorts_Channel" / "wave_production_status.json"


def is_project_complete(project_id: str) -> bool:
    pdir = PROJECTS_DIR / project_id
    mp4 = pdir / "05_assembly" / "final_shorts_1080x1920.mp4"
    rep = pdir / "05_assembly" / "video_autopsy_report.json"
    return mp4.exists() and mp4.stat().st_size >= MIN_CLIP_SIZE_BYTES and rep.exists()


def get_completed_projects() -> list[str]:
    return [
        bp["project_id"]
        for bp in ALL_PSYCHOLOGY_100_TOPICS
        if is_project_complete(bp["project_id"])
    ]


def write_status(wave_idx: int, active_projects: list[str], last_event: str, errors: dict[str, str]) -> None:
    completed = get_completed_projects()
    payload = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "total_target": len(ALL_PSYCHOLOGY_100_TOPICS),
        "completed_count": len(completed),
        "completed_projects": completed,
        "current_wave": wave_idx,
        "active_projects": active_projects,
        "last_event": last_event,
        "recent_errors": errors,
    }
    STATUS_FILE.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


async def run_single_project_with_retries(
    project_id: str,
    cdp_port: int = 9222,
    max_attempts: int = 2,
    stagger_sec: float = 0.0,
) -> dict[str, Any]:
    if stagger_sec > 0:
        await asyncio.sleep(stagger_sec)
    last_err = ""
    for attempt in range(1, max_attempts + 1):
        tab_id = None
        try:
            print(f"[WaveWorker] Starting {project_id} (attempt {attempt}/{max_attempts})...", flush=True)
            res = await run_live_flow_for_single_project(
                project_id=project_id,
                cdp_port=cdp_port,
                existing_tab_id=None,
            )
            tab_id = res.get("tab_id")
            print(f"[WaveWorker] SUCCESS {project_id}: Autopsy={res.get('autopsy_score')} MP4={res.get('completed_mp4')}", flush=True)
            return {"project_id": project_id, "status": "SUCCESS", "result": res}
        except Exception as e:
            last_err = f"{type(e).__name__}: {e}"
            print(f"[WaveWorker] ERROR on {project_id} (attempt {attempt}): {last_err}", flush=True)
            if tab_id and not str(tab_id).startswith("RESUMED_"):
                try:
                    urllib.request.urlopen(f"http://127.0.0.1:{cdp_port}/json/close/{tab_id}", timeout=5)
                except Exception:
                    pass
            if is_project_complete(project_id):
                return {"project_id": project_id, "status": "SUCCESS_ON_DISK"}
            await asyncio.sleep(20.0)
    return {"project_id": project_id, "status": "FAILED", "error": last_err}


async def run_waves(start_idx: int = 1, end_idx: int = 100, batch_size: int = FLOW_MAX_PARALLEL_BATCH_SIZE, cdp_port: int = 9222) -> None:
    batch_size = min(batch_size, FLOW_MAX_PARALLEL_BATCH_SIZE)
    selected = ALL_PSYCHOLOGY_100_TOPICS[max(0, start_idx - 1) : min(100, end_idx)]
    pending = [bp["project_id"] for bp in selected if not is_project_complete(bp["project_id"])]
    errors: dict[str, str] = {}

    print(f"=== Master Wave Orchestrator: {len(pending)} pending projects in range {start_idx}..{end_idx} (batch_size={batch_size}) ===", flush=True)
    write_status(0, [], f"Starting wave runner for {len(pending)} pending projects", errors)

    for w_offset in range(0, len(pending), batch_size):
        chunk = pending[w_offset : w_offset + batch_size]
        wave_num = (w_offset // batch_size) + 1
        print(f"\n>>> Launching Wave #{wave_num}: {chunk} <<<", flush=True)
        write_status(wave_num, chunk, f"Running Wave #{wave_num}: {', '.join(chunk)}", errors)

        # Stagger tab allocations by 18.0s each to prevent Google Flow 'unusual activity' rate limits
        tasks = [
            run_single_project_with_retries(pid, cdp_port=cdp_port, max_attempts=2, stagger_sec=i * 18.0)
            for i, pid in enumerate(chunk)
        ]
        results = await asyncio.gather(*tasks)
        for r in results:
            if r.get("status") == "FAILED":
                errors[r["project_id"]] = r.get("error", "Unknown error")
            else:
                errors.pop(r["project_id"], None)
        write_status(wave_num, [], f"Finished Wave #{wave_num}", errors)
        await asyncio.sleep(15.0)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", type=int, default=11)
    parser.add_argument("--end", type=int, default=100)
    parser.add_argument("--batch-size", type=int, default=5)
    parser.add_argument("--cdp-port", type=int, default=9222)
    args = parser.parse_args()
    asyncio.run(run_waves(start_idx=args.start, end_idx=args.end, batch_size=args.batch_size, cdp_port=args.cdp_port))


if __name__ == "__main__":
    main()
