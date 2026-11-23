"""
ALL ABOUT BRAIN — YouTube Studio Batch Uploader and Scheduler for psych_31 through psych_100.
Enforces:
- 5-Slot North American schedule from studio_schedule_map_31_100.json
- KR Residence + en-US Upload Language Lock
- AI Altered Content Disclosure (R4)
- First-Frame Thumbnail Burn-in (R31)
- 3-Notification rolling quota (Slots 2 & 5 notification OFF)
- Pinned Academic DOI Comment
"""

import argparse
import json
import sys
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
WORKSPACE_ROOT = SCRIPT_DIR.parents[2]  # BCI_Shorts_Channel/scripts/batch_ops -> workspace root
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from pipeline.config import PROJECTS_DIR
from pipeline.storage import ProjectStorage
from pipeline.studio.community import CommunityManager
from pipeline.studio.uploader import StudioUploader

MAP_FILE = SCRIPT_DIR / "studio_schedule_map_31_100.json"


def find_project_dir(batch_num: int) -> Path | None:
    p_prefix = f"psych_{batch_num:02d}_"
    matches = sorted([d for d in PROJECTS_DIR.iterdir() if d.is_dir() and d.name.startswith(p_prefix)])
    if not matches:
        p_prefix = f"psych_{batch_num:02d}"
        matches = sorted([d for d in PROJECTS_DIR.iterdir() if d.is_dir() and d.name.startswith(p_prefix) and (d / "05_assembly" / "final_shorts_1080x1920.mp4").exists()])
    return matches[0] if matches else None


def main():
    parser = argparse.ArgumentParser(description="YouTube Studio Batch Uploader for psych_31..100")
    parser.add_argument("--start", type=int, default=31, help="Start batch number (default: 31)")
    parser.add_argument("--end", type=int, default=100, help="End batch number (default: 100)")
    parser.add_argument("--cdp-port", type=int, default=9222, help="Whale CDP port")
    parser.add_argument("--dry-run", action="store_true", help="Simulate uploads without clicking")
    args = parser.parse_args()

    if not MAP_FILE.exists():
        print(f"[ERROR] Schedule map file not found: {MAP_FILE}")
        sys.exit(1)

    schedule_map = json.loads(MAP_FILE.read_text(encoding="utf-8"))
    uploader = StudioUploader(cdp_port=args.cdp_port)
    community = CommunityManager(cdp_port=args.cdp_port)

    print("========================================================================")
    print(f"  ALL ABOUT BRAIN — YOUTUBE STUDIO BATCH UPLOADER ({args.start}..{args.end})")
    print(f"  Dry-Run: {args.dry_run} | CDP Port: {args.cdp_port}")
    print("========================================================================\n")

    uploaded_count = 0
    skipped_count = 0
    missing_video_count = 0

    for b_num in range(args.start, args.end + 1):
        key = f"psych_{b_num:02d}"
        sched = schedule_map.get(key)
        if not sched:
            print(f"[{key}] No schedule entry found in map. Skipping.")
            continue

        p_dir = find_project_dir(b_num)
        if not p_dir:
            print(f"[{key}] Project directory not found. Skipping.")
            continue

        pid = p_dir.name
        final_mp4 = p_dir / "05_assembly" / "final_shorts_1080x1920.mp4"
        if not final_mp4.exists():
            print(f"[{pid}] Final MP4 not yet assembled ({final_mp4.name} missing). Skipping.")
            missing_video_count += 1
            continue

        # Check existing receipt
        receipt_file = p_dir / "06_publish" / "upload_receipt.json"
        if receipt_file.exists():
            try:
                rc = json.loads(receipt_file.read_text(encoding="utf-8"))
                vid = rc.get("video_id", "")
                if vid and not vid.startswith("sim_") and not args.dry_run:
                    print(f"[{pid}] Already uploaded (Video ID: {vid}, Status: {rc.get('status')}). Skipping.")
                    skipped_count += 1
                    continue
            except Exception:
                pass

        target_date = sched["scheduled_date_iso"]
        slot_id = sched["slot"]
        time_et = sched["time_et"]
        sub_notif = sched["subscriber_notification"]

        print(f"\n>>> Uploading [{b_num}/{args.end}]: {pid} <<<")
        print(f"    Date: {target_date} | Slot: {slot_id} ({time_et}) | Notify Subs: {sub_notif}")

        try:
            receipt = uploader.upload_project(
                project_id=pid,
                slot_id=slot_id,
                target_date=target_date,
                visibility="scheduled",
                dry_run=args.dry_run,
                burn_first_frame=True,
            )

            vid = receipt.get("video_id")
            print(f"[SUCCESS] Uploaded {pid} -> Video ID: {vid} ({receipt.get('shorts_url')})")
            uploaded_count += 1

            # Record DOI verification comment payload artifact
            try:
                comment_payload = community.prepare_comment_content(pid)
                ProjectStorage(pid).save_json("06_publish", "community_comment.json", comment_payload)
                print(f"    Recorded DOI verification comment artifact for {pid}.")
            except Exception as ce:
                print(f"    [WARNING] Comment prep warning: {ce}")

            time.sleep(3.0)

        except Exception as e:
            print(f"[ERROR] Failed to upload {pid}: {e}")

    print("\n========================================================================")
    print(f"  BATCH UPLOAD SUMMARY")
    print(f"  Uploaded: {uploaded_count} | Already Uploaded: {skipped_count} | Missing MP4: {missing_video_count}")
    print("========================================================================")


if __name__ == "__main__":
    main()
