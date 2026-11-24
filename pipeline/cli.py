"""
ALL ABOUT BRAIN - Unified Pipeline CLI
Command-line interface for autonomous production, Google Flow assistance,
batch operations, YouTube Studio staging, community comment pinning,
and sequential A/B testing.
"""

import argparse
import sys
from pathlib import Path
from typing import Any

from pipeline.config import (
    ALLOWED_NARRATIVE_STYLES,
    CLIP_COUNT_MAX,
    CLIP_COUNT_MIN,
    DIORAMA_V7_PROSODY_MODES,
    DIORAMA_VOICE_PRESETS,
    DOSSIERS_DIR,
    PROJECTS_DIR,
    WORKSPACE_ROOT,
)

if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass















def cmd_verify(args):
    """Verifies lossless storage integrity and QA report for a project."""
    from pipeline.assembler import verify_script_audio_freshness
    from pipeline.storage import ProjectStorage
    cand = Path(args.project)
    if cand.is_dir():
        storage = ProjectStorage(cand.name, projects_dir=cand.parent)
    else:
        storage = ProjectStorage(args.project)
    verify_script_audio_freshness(storage.project_dir, context="verify")
    manifest = storage.get_manifest()
    recorded_count = sum(
        len((s_data.get("artifacts") or {}))
        for s_data in (manifest.get("stages") or {}).values()
        if isinstance(s_data, dict)
    )
    if recorded_count == 0 and any(
        fp.is_file()
        for s_name in ("02_script", "03_visuals", "04_audio", "05_assembly", "06_publish")
        if (storage.project_dir / s_name).is_dir()
        for fp in (storage.project_dir / s_name).rglob("*")
    ):
        ProjectStorage.sync_existing_manifest_from_disk(storage.project_dir)
    integrity = storage.verify_integrity()
    manifest = storage.get_manifest()
    print(f"\n--- Project Storage Audit: {args.project} ({manifest.get('title', 'N/A')}) ---")
    print(f"Total Artifacts: {integrity['total_artifacts']}")
    print(f"Verified Intact: {integrity['verified_artifacts']}")
    print(f"Status: {'100% INTACT' if integrity['all_intact'] else 'CORRUPTED/MISSING'}")
    if integrity["corrupted_or_missing"]:
        print("Issues:", integrity["corrupted_or_missing"])

    master_qa = storage.load_json("05_assembly", "master_qa_report.json")
    if master_qa:
        print(f"Master QA Status: {'[ALL GATES PASS]' if master_qa.get('all_gates_passed') else '[FAILED]'}")
    if not integrity["all_intact"] or (master_qa and not master_qa.get("all_gates_passed")):
        sys.exit(1)


def cmd_studio_upload(args):
    """Uploads project Shorts video to YouTube Studio with 5-slot scheduling or unlisted staging."""
    from pipeline.studio.uploader import StudioUploader
    uploader = StudioUploader(cdp_port=args.cdp_port)
    print(f"\n[CLI] Initiating YouTube Studio upload for project '{args.project}'...")
    print(f"      Visibility: {args.visibility.upper()} | Slot: {args.slot or 'Auto-Pillar'} | Dry-Run: {args.dry_run}")

    burn_first_frame = getattr(args, "burn_first_frame", False)
    auto_link = bool(getattr(args, "auto_link", False))
    allow_instant_public = bool(getattr(args, "allow_instant_public", False))
    receipt = uploader.upload_project(
        project_id=args.project,
        slot_id=args.slot,
        target_date=args.date,
        visibility=args.visibility,
        dry_run=args.dry_run,
        burn_first_frame=burn_first_frame,
        auto_link=auto_link,
        assign_playlist=False,
        allow_instant_public=allow_instant_public,
    )
    print("\n========================================================")
    print(f"  YOUTUBE STUDIO UPLOAD {'[DRY RUN]' if args.dry_run else '[LIVE]'} SUCCESS!")
    print(f"  Project: {receipt['project_id']}")
    print(f"  Title: {receipt['title']}")
    print(f"  Video ID: {receipt['video_id']}")
    print(f"  Shorts URL: {receipt['shorts_url']}")
    print(f"  Visibility: {receipt['visibility'].upper()}")
    print(f"  Localization: Video={receipt.get('video_language', 'en-US')} | Metadata={receipt.get('title_description_language', 'en-US')} | Residence={receipt.get('channel_residence_country', 'KR')}")
    if receipt.get("scheduled_time_et"):
        print(f"  Scheduled Time: {receipt['scheduled_time_et']}")
    if receipt.get("related_link_summary"):
        print(f"  Related Video Linked: {receipt['related_link_summary'].get('verified_count', 0)} edge(s)")
    print("  Receipt Artifact: 06_publish/upload_receipt.json")
    print("========================================================\n")


def cmd_studio_settings(args):
    """Configures and verifies Two-Tier Localization, Clean Keywords, Empty Default Tags & Playlist Purge (R36 + R75)."""
    import json
    from pipeline.studio.uploader import StudioUploader

    if (
        getattr(args, "audit_v8_readiness", False)
        or getattr(args, "check_auto_dubbing", False)
        or getattr(args, "lock_auto_dubbing_off", False)
        or getattr(args, "check_home_shelves", False)
    ):
        audit = StudioUploader.audit_v8_channel_readiness()
        uploader = None
        if getattr(args, "check_auto_dubbing", False) or getattr(args, "lock_auto_dubbing_off", False):
            uploader = StudioUploader(cdp_port=getattr(args, "cdp_port", 9222))
            if getattr(args, "lock_auto_dubbing_off", False):
                dub_check = uploader.lock_auto_dubbing_off(dry_run=bool(getattr(args, "dry_run", False)))
                audit["auto_dubbing_lock"] = dub_check
            else:
                dub_check = uploader.inspect_auto_dubbing_settings(dry_run=bool(getattr(args, "dry_run", False)))
            dub_check["multi_language_audio_checklist"] = audit.get("multi_language_audio_checklist", {})
            audit["auto_dubbing_check"] = dub_check
        if getattr(args, "check_home_shelves", False):
            if uploader is None:
                uploader = StudioUploader(cdp_port=getattr(args, "cdp_port", 9222))
            audit["home_shelves_check"] = uploader.inspect_channel_home_shelves(
                dry_run=bool(getattr(args, "dry_run", False))
            )
        print(json.dumps(audit, indent=2, ensure_ascii=False))
        return

    uploader = StudioUploader(cdp_port=args.cdp_port)
    purge_res = None
    if getattr(args, "purge_playlists", False):
        pl_shot = Path(args.playlists_screenshot) if getattr(args, "playlists_screenshot", None) else None
        print("\n[CLI] Purging ALL YouTube Studio Playlists permanently (Rule R75)...")
        purge_res = uploader.purge_all_channel_playlists(dry_run=args.dry_run, screenshot_path=pl_shot)
        print(
            f"[CLI] Playlist Purge Complete: deleted={purge_res.get('deleted_count', 0)} | "
            f"remaining={purge_res.get('remaining_count', 0)}"
        )

    settings_shot = Path(args.settings_screenshot) if getattr(args, "settings_screenshot", None) else None
    print("\n[CLI] Configuring YouTube Studio Localization, Clean Keywords & Empty Upload Defaults (R36 + R75)...")
    res = uploader.configure_studio_localization(dry_run=args.dry_run, screenshot_path=settings_shot)
    audit = StudioUploader.audit_v8_channel_readiness()
    live_art = audit["channel_art_readiness"]["live_channel_art_replaced"]
    print("\n========================================================")
    print(f"  YOUTUBE STUDIO SETTINGS {'[DRY RUN]' if args.dry_run else '[LIVE VERIFIED]'}!")
    print(f"  Channel: {res['channel_name']} ({res['channel_id']})")
    print(f"  Country of Residence: {res['country_of_residence']} ({res['country_of_residence_code']})")
    print(f"  Video Language:       {res['video_language']} ({res['video_language_code']})")
    print(f"  Metadata Language:    {res['title_description_language']} ({res['title_description_language_code']})")
    print(f"  Default Category:     {res['category']}")
    print(f"  Channel Keywords:     {len(res.get('channel_keywords', []))} clean chips")
    print(f"  Upload Default Tags:  {len(res.get('upload_default_tags', []))} chips (0/500 locked)")
    if purge_res is not None:
        print(f"  Playlists Purged:     deleted={purge_res.get('deleted_count', 0)} | remaining={purge_res.get('remaining_count', 0)}")
    print(f"  Changes Saved:        {res['saved_changes']}")
    print(f"  v8 Avatar/Banner:     {len(audit['channel_art_readiness']['avatar_drafts_staged'])} avatars, {len(audit['channel_art_readiness']['banner_drafts_staged'])} banners staged (live_replaced={live_art})")
    print(f"  Format Inventory:     {audit['format_inventory_audit']['shorts_le_89_5s_count']} Shorts <=89.5s | {audit['format_inventory_audit']['legacy_gt_89_5s_count']} legacy >89.5s (frozen)")
    print("========================================================\n")


def cmd_studio_pin(args):
    """Posts academic DOI source & cognitive dissonance question comment and pins it to top."""
    import json
    from pipeline.studio.community import CommunityManager

    manager = CommunityManager(cdp_port=args.cdp_port)
    force_immediate_pin = bool(getattr(args, "force_immediate_pin", False))
    if getattr(args, "all_public", False):
        print(f"\n[CLI] Scanning projects to stage prepared comments and pin unpinned Public Shorts (Dry-Run: {args.dry_run}, Replace-Existing: {args.replace_existing})...")
        summary = manager.pin_all_public_unpinned(
            dry_run=args.dry_run,
            replace_existing=args.replace_existing,
            project_filter={args.project} if args.project else None,
            force_immediate_pin=force_immediate_pin,
        )
        print(json.dumps(summary, indent=2, ensure_ascii=False))
        return

    if not args.project:
        print("[ERROR] Provide --project <project_id> or --all-public.")
        sys.exit(1)

    print(f"\n[CLI] Posting & Pinning DOI verification comment for '{args.project}'...")
    print(f"      Video ID: {args.video_id or 'from receipt'} | Replace-Existing: {args.replace_existing} | Dry-Run: {args.dry_run}")

    receipt = manager.post_and_pin_comment(
        project_id=args.project,
        video_id=args.video_id,
        dry_run=args.dry_run,
        replace_existing=args.replace_existing,
        force_immediate_pin=force_immediate_pin,
    )
    print("\n========================================================")
    print(f"  COMMUNITY COMMENT STATUS: {receipt.get('status', '').upper()} {'[DRY RUN]' if args.dry_run else '[LIVE]'}!")
    print(f"  Project: {receipt['project_id']}")
    print(f"  Shorts URL: {receipt['shorts_url']}")
    print(f"  Pinned Status: {receipt['pinned']} (Deleted Previous: {receipt.get('deleted_previous_count', 0)})")
    print("---------------- Comment Body --------------------------")
    print(receipt["comment_text"])
    print("========================================================\n")






def cmd_studio_link(args):
    """Plans or applies Short-to-Short Related Video circular ring & 7-Pillar playlists (R35-B)."""
    import json
    from pipeline.studio.short_linker import ShortLinkGraph, StudioShortLinker

    action = args.action
    mode = "seed_boost" if action == "seed-boost" else getattr(args, "mode", "seed_boost")
    p_filter = {args.project} if args.project else None

    if action == "status":
        graph = ShortLinkGraph()
        nodes = graph.discover_nodes()
        rows = []
        for n in nodes:
            rows.append({
                "project_id": n["project_id"],
                "video_id": n["video_id"],
                "visibility": n["visibility"],
                "views": n["views"],
                "impressions": n["impressions"],
                "existing_target_video_id": n.get("existing_target_video_id"),
                "playlist_verified": bool(n.get("existing_playlist_verified")),
            })
        print(json.dumps({"node_count": len(rows), "nodes": rows}, indent=2, ensure_ascii=False))
        return

    if action == "plan":
        graph = ShortLinkGraph()
        plan_doc = graph.plan_links(
            mode=mode,
            force=args.force,
            project_filter=p_filter,
            explicit_target_video_id=args.target,
        )
        if not args.dry_run:
            graph.save_graph(plan_doc)
        print(json.dumps(plan_doc, indent=2, ensure_ascii=False))
        return

    linker = StudioShortLinker(cdp_port=args.cdp_port)
    res = linker.run(
        mode=mode,
        assign_playlists=False,
        dry_run=args.dry_run,
        force=args.force,
        project_id=args.project,
        target_video_id=args.target,
    )
    print(json.dumps(res, indent=2, ensure_ascii=False))
    if not args.dry_run:
        failed = [
            r for r in res.get("execution_results", [])
            if r.get("status") not in ("linked_verified", "verified", "already_linked", "deferred_seed_lock")
        ]
        if failed:
            sys.exit(1)




def _shrink_json_payload(payload: dict[str, Any], *, max_bytes: int) -> dict[str, Any]:
    """Iteratively trims list fields so serialized JSON fits strictly within `max_bytes` UTF-8 bytes."""
    import json

    def _size(obj: dict[str, Any]) -> int:
        return len(json.dumps(obj, ensure_ascii=False).encode("utf-8"))

    out = dict(payload)
    if _size(out) <= max_bytes:
        return out
    for list_key in ("top_defects", "failed_gates", "suspect_clips"):
        vals = out.get(list_key)
        if isinstance(vals, list):
            while vals and _size(out) > max_bytes:
                vals = vals[:-1]
                out[list_key] = vals
                if vals and list_key == "top_defects":
                    out["truncated_defects"] = True
    if _size(out) > max_bytes and isinstance(out.get("metrics"), dict):
        out["metrics"] = {}
    if _size(out) > max_bytes and isinstance(out.get("stages"), dict):
        out["stages"] = {
            k: {"passed": v.get("passed")} if isinstance(v, dict) else v
            for k, v in out["stages"].items()
        }
    while _size(out) > max_bytes and isinstance(out.get("top_defects"), list) and out["top_defects"]:
        out["top_defects"].pop()
    if _size(out) > max_bytes:
        out = {
            "project_id": str(out.get("project_id") or "")[:64],
            "passed": bool(out.get("passed")),
            "failed_gates": list(out.get("failed_gates") or [])[:5],
            "suspect_clips": list(out.get("suspect_clips") or [])[:10],
            "top_defects": [],
        }
    return out


def build_compact_qa_digest(
    report: dict[str, Any],
    *,
    stage: str = "",
    max_bytes: int = 1800,
    report_path: str | Path | None = None,
) -> dict[str, Any]:
    """Build a compact defect-first JSON QA digest strictly bounded to `<= max_bytes` bytes (Tier A-1)."""
    rep = report if isinstance(report, dict) else {}
    if "passed" in rep:
        passed = bool(rep.get("passed"))
    elif "all_passed" in rep:
        passed = bool(rep.get("all_passed"))
    elif "pre_generation_ready" in rep:
        passed = bool(rep.get("pre_generation_ready"))
    elif "ready" in rep:
        passed = bool(rep.get("ready"))
    else:
        passed = False

    failed_gates: list[str] = []
    gates_obj = rep.get("gates")
    if isinstance(gates_obj, dict):
        for g_name, g_val in gates_obj.items():
            if isinstance(g_val, dict):
                if g_val.get("passed") is False or str(g_val.get("status") or "").lower() in ("fail", "failed", "error"):
                    failed_gates.append(str(g_name)[:48])
            elif g_val is False:
                failed_gates.append(str(g_name)[:48])
    checklist_obj = rep.get("checklist")
    if isinstance(checklist_obj, dict):
        for c_name, c_val in checklist_obj.items():
            if c_val is False:
                failed_gates.append(str(c_name)[:48])

    defects: list[str] = []
    for dk in ("gate1_issues", "defects", "issues", "blocking_issues", "errors", "failed_reasons"):
        raw_list = rep.get(dk)
        if isinstance(raw_list, list):
            for item in raw_list:
                if isinstance(item, dict):
                    txt = str(item.get("message") or item.get("reason") or item.get("issue") or item.get("gate") or item)
                else:
                    txt = str(item)
                txt = " ".join(txt.split())[:140]
                if txt and txt not in defects:
                    defects.append(txt)
                    if len(defects) >= 12:
                        break
        if len(defects) >= 12:
            break

    suspect_clips: set[int] = set()
    summary_obj = rep.get("summary") if isinstance(rep.get("summary"), dict) else {}
    for sk in ("suspect_clips", "weak_cut_indices", "regenerate_clip_indices"):
        for container in (rep, summary_obj):
            vals = container.get(sk)
            if isinstance(vals, list):
                for v in vals:
                    try:
                        suspect_clips.add(int(v))
                    except (TypeError, ValueError):
                        pass
    for list_k in ("cuts", "clips", "specs", "slots"):
        entries = rep.get(list_k)
        if isinstance(entries, list):
            for entry in entries:
                if isinstance(entry, dict) and (entry.get("passed") is False or entry.get("ready") is False):
                    cnum = entry.get("clip_number") or entry.get("cut_index") or entry.get("clip_index")
                    if cnum is not None:
                        try:
                            suspect_clips.add(int(cnum))
                        except (TypeError, ValueError):
                            pass

    metrics: dict[str, Any] = {}
    for mk in ("autopsy_score", "schema_version", "ready", "pre_generation_ready", "clips", "defect_count"):
        if mk in rep and not isinstance(rep[mk], (list, dict)):
            metrics[mk] = rep[mk]
    for smk in ("cut_count", "passed_cuts", "weak_cut_count", "mean_clarity_score"):
        if smk in summary_obj and not isinstance(summary_obj[smk], (list, dict)):
            metrics[smk] = summary_obj[smk]

    warnings_out: list[str] = []
    raw_warns = rep.get("warnings")
    if isinstance(raw_warns, list):
        for w_it in raw_warns:
            w_txt = " ".join(str(w_it).split())[:120]
            if w_txt and w_txt not in warnings_out:
                warnings_out.append(w_txt)
                if len(warnings_out) >= 10:
                    break

    digest: dict[str, Any] = {
        "stage": str(stage or rep.get("stage") or "qa"),
        "project_id": str(rep.get("project_id") or rep.get("slug") or Path(str(rep.get("dir") or "")).name or ""),
        "passed": passed,
        "issues": defects[:10],
        "warnings": warnings_out[:10],
        "failed_gates": failed_gates[:16],
        "suspect_clips": sorted(suspect_clips)[:24],
        "top_defects": defects[:10],
        "metrics": metrics,
    }
    eff_rp = str(report_path or rep.get("report_path") or "").strip()
    if eff_rp:
        digest["report_path"] = eff_rp
    for keep_k in ("ready", "pre_generation_ready", "contract_compiled", "status", "verdict", "cover_frame_sec"):
        if keep_k in rep and not isinstance(rep[keep_k], (list, dict)):
            digest[keep_k] = rep[keep_k]
    return _shrink_json_payload(digest, max_bytes=int(max_bytes))


def collect_project_qa_summary(project_dir: Path, *, max_bytes: int = 1500) -> dict[str, Any]:
    """Read on-disk QA reports in `project_dir` and return a <=1500B defect-first summary (Tier A-1)."""
    import json

    p_dir = Path(project_dir)
    stage_candidates: tuple[tuple[str, tuple[str, ...]], ...] = (
        ("ref_qa", ("03_visuals/reference_image_qa_report.json", "03_visuals/reference_images/reference_image_qa_report.json", "03_visuals/reference_qa_report.json", "reference_qa_report.json")),
        ("real_world_refs", ("03_visuals/real_world_refs_manifest.json", "real_world_refs_manifest.json")),
        (
            "prosody",
            (
                "05_assembly/prosody_qa_report.json",
                "04_audio/prosody_qa_report.json",
                "04_audio/prosody_preflight_report.json",
                "prosody_qa_report.json",
                "prosody_preflight_report.json",
                "04_audio/prosody_report.json",
                "prosody_report.json",
            ),
        ),
        ("episode_qa", ("05_assembly/dynamic_episode_qa_report.json", "dynamic_episode_qa_report.json")),
        ("posthoc_qa", ("05_assembly/posthoc_semantic_qa_report.json", "posthoc_semantic_qa_report.json")),
        ("autopsy", ("05_assembly/video_autopsy_report.json", "05_assembly/autopsy_report.json", "autopsy_report.json")),
        ("thumbnail_qa", ("06_publish/thumbnail_qa_report.json", "06_publish/thumbnail_report.json", "thumbnail_qa_report.json")),
    )

    stages: dict[str, dict[str, Any]] = {}
    failed_gates: list[str] = []
    top_defects: list[str] = []
    suspect_clips: set[int] = set()
    any_present = False
    all_present_passed = True

    for st_name, rels in stage_candidates:
        found: Path | None = None
        parsed_data: Any = None
        parse_err: Exception | None = None
        for rel in rels:
            cand = p_dir / rel
            if not (cand.exists() and cand.is_file()):
                continue
            try:
                cand_data = json.loads(cand.read_text(encoding="utf-8"))
            except Exception as exc:
                found = cand
                parse_err = exc
                break
            if (
                cand.name == "prosody_report.json"
                and isinstance(cand_data, dict)
                and not any(
                    k in cand_data
                    for k in ("passed", "all_passed", "gates", "ready", "pre_generation_ready")
                )
            ):
                continue
            found = cand
            parsed_data = cand_data
            break
        if found is None:
            stages[st_name] = {"present": False, "passed": None}
            continue
        any_present = True
        if parse_err is not None:
            all_present_passed = False
            stages[st_name] = {"present": True, "passed": False}
            failed_gates.append(f"{st_name}:parse_error")
            top_defects.append(f"{st_name}: invalid JSON ({parse_err})"[:140])
            continue
        data = parsed_data
        if not isinstance(data, dict):
            all_present_passed = False
            stages[st_name] = {"present": True, "passed": False}
            failed_gates.append(f"{st_name}:invalid_format")
            continue

        if st_name == "real_world_refs" and "passed" not in data and "pre_generation_ready" not in data and "ready" not in data:
            if "all_rq_real_passed" in data:
                st_passed = bool(data.get("all_rq_real_passed"))
            else:
                st_issues = data.get("issues") or data.get("missing") or []
                st_passed = not bool(st_issues)
        else:
            st_digest = build_compact_qa_digest(data, stage=st_name, max_bytes=1200)
            st_passed = bool(st_digest["passed"])
            for fg in st_digest.get("failed_gates", []):
                tag = f"{st_name}:{fg}"
                if tag not in failed_gates:
                    failed_gates.append(tag)
            for td in st_digest.get("top_defects", []):
                msg = f"[{st_name}] {td}"[:140]
                if msg not in top_defects:
                    top_defects.append(msg)
            for sc in st_digest.get("suspect_clips", []):
                suspect_clips.add(int(sc))

        if not st_passed:
            all_present_passed = False
            if not any(g.startswith(f"{st_name}:") for g in failed_gates):
                failed_gates.append(st_name)
        stages[st_name] = {"present": True, "passed": st_passed}

    overall_passed = bool(any_present and all_present_passed)
    if not any_present:
        failed_gates.append("no_qa_reports_found")

    summary: dict[str, Any] = {
        "project_id": p_dir.name,
        "passed": overall_passed,
        "stages": stages,
        "failed_gates": failed_gates[:20],
        "suspect_clips": sorted(suspect_clips)[:24],
        "top_defects": top_defects[:12],
    }
    return _shrink_json_payload(summary, max_bytes=int(max_bytes))


def cmd_qa_summary(args):
    """Prints a compact defect-first summary of all on-disk QA reports for a project directory."""
    import json

    raw_dir = getattr(args, "dir", None)
    raw_proj = getattr(args, "project", None)
    if raw_dir:
        p_dir = Path(raw_dir)
    elif raw_proj:
        p_dir = Path(raw_proj) if Path(raw_proj).is_dir() else (Path(PROJECTS_DIR) / raw_proj)
    else:
        print(json.dumps({"passed": False, "error": "Specify --project or --dir"}))
        sys.exit(1)
    rep = collect_project_qa_summary(p_dir, max_bytes=1500)
    print(json.dumps(rep, ensure_ascii=False))
    if getattr(args, "strict", False) and not rep.get("passed"):
        sys.exit(1)


def cmd_autopsy(args):
    """Runs multimodal video/audio/subtitle/thumbnail forensic autopsy on one or all projects."""
    import json
    from pipeline.media_probe import VideoAutopsyEngine

    if args.project:
        report = VideoAutopsyEngine.inspect_project(args.project, save_report=True)
    else:
        report = VideoAutopsyEngine.inspect_all_projects(save_reports=True)
    if getattr(args, "verbose_json", False):
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        rp_aut = str((Path(PROJECTS_DIR) / str(args.project) / "05_assembly/video_autopsy_report.json")) if args.project else ""
        print(json.dumps(build_compact_qa_digest(report, stage="autopsy", report_path=rp_aut), ensure_ascii=False))
    passed = report.get("passed", report.get("all_passed", False))
    if not passed:
        sys.exit(1)




def main():
    parser = argparse.ArgumentParser(description="ALL ABOUT BRAIN — Expressive 2.5D v8 Pipeline CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Unified Fresh-Room State Machine (`main.py ep`)
    p_ep = subparsers.add_parser("ep", help="Episode state machine: status <project_id> | run <project_id> --until gate1|gate2|ready")
    p_ep.add_argument("action", choices=["status", "run"])
    p_ep.add_argument("project", help="Target project ID or directory")
    p_ep.add_argument("--until", default="ready", choices=["gate1", "gate2", "ready"])
    p_ep.add_argument("--tabs", type=int, default=5)
    p_ep.add_argument("--cdp-port", type=int, default=9222)
    p_ep.add_argument("--engine", default="auto", choices=["auto", "omni", "zero_credit", "zero-credit"])

    # Gear 1: Research & Dossier
    p_nr = subparsers.add_parser("news-radar", help="Scan recent Crossref / ClinicalTrials neuroscience papers")
    p_nr.add_argument("--days", type=int, default=14)
    p_nr.add_argument("--max-candidates", type=int, default=5)

    p_ds = subparsers.add_parser("dossier", help="Research dossier: init | validate | seed | doi | yt-search | yt-analyze | audit-media")
    p_ds.add_argument("action", choices=["init", "validate", "seed", "doi", "yt-search", "yt-analyze", "audit-media", "checklist"])
    p_ds.add_argument("--slug", default=None)
    p_ds.add_argument("--root", default=None)
    p_ds.add_argument("--topic", default="")
    p_ds.add_argument("--pillar", default="")
    p_ds.add_argument("--everyday-domain", default="")
    p_ds.add_argument("--mode", default="HYBRID")
    p_ds.add_argument("--profile", default="neuro_diorama", choices=["classic_v5", "neuro_diorama"])
    p_ds.add_argument("--style-profile", default=None, choices=["porcelain_cinematic_v7", "lowpoly_pastel_v7", "expressive_25d_v8"])
    p_ds.add_argument("--require-v2", action="store_true", default=False)
    p_ds.add_argument("--summary", action="store_true", default=False)
    p_ds.add_argument("--verbose-json", action="store_true", default=False)
    p_ds.add_argument("--doi", default=None)
    p_ds.add_argument("--query", default=None)
    p_ds.add_argument("--url", default=None)
    p_ds.add_argument("--media-id", default=None)
    p_ds.add_argument("--section", default=None)
    p_ds.add_argument("--write", action="store_true", default=False)
    p_ds.add_argument("--overwrite", action="store_true", default=False)

    # Gear 2: Script, Prompt Gate & Chart Preview
    p_pg = subparsers.add_parser("prompt-gate", help="Validate script, visual_plan, metadata, and R85-R89 contracts")
    p_pg.add_argument("--dir", required=True)
    p_pg.add_argument("--summary", action="store_true", default=False)
    p_pg.add_argument("--verbose-json", action="store_true", default=False)

    p_cp = subparsers.add_parser("chart-preview", help="Render R70-M hand-drawn study Data Stamp preview PNGs")
    p_cp.add_argument("--project", required=True)
    p_cp.add_argument("--out", default=None)

    # Gear 3: Reference Pack & Google Flow Video Generation
    p_pr = subparsers.add_parser("refs", aliases=["porcelain-refs"], help="Synthesize & verify 9:16 reference pack via 0-credit Google Flow Image (x1/x2)")
    p_pr.add_argument("--project", required=True)
    p_pr.add_argument("--slug", default="")
    p_pr.add_argument("--refs", default="")
    p_pr.add_argument("--backend", default="flow", choices=["flow"])
    p_pr.add_argument("--batch-count", type=int, default=None)
    p_pr.add_argument("--cdp-port", type=int, default=9222)
    p_pr.add_argument("--force", action="store_true", default=False)
    p_pr.add_argument("--require-review", action="store_true", default=False)
    p_pr.add_argument("--auto-populate-review", action="store_true", default=False)

    p_rr = subparsers.add_parser("reenact-refs", help="Translate sanitized archival structural guides into 9:16 reference PNGs (x1/x2)")
    p_rr.add_argument("--project", required=True)
    p_rr.add_argument("--slug", required=True)
    p_rr.add_argument("--refs", default="")
    p_rr.add_argument("--backend", default="flow", choices=["flow"])
    p_rr.add_argument("--batch-count", type=int, default=None)
    p_rr.add_argument("--cdp-port", type=int, default=9222)
    p_rr.add_argument("--force", action="store_true", default=False)
    p_rr.add_argument("--purge-quarantine", action="store_true", default=False)

    p_rq = subparsers.add_parser("ref-qa", help="Run Gate 1 Reference Image QA")
    p_rq.add_argument("--project", required=True)
    p_rq.add_argument("--audit", action="store_true", default=False)
    p_rq.add_argument("--register", default=None)
    p_rq.add_argument("--source", default="flow_image_generation", choices=["flow_image_generation"])
    p_rq.add_argument("--require-review", action=argparse.BooleanOptionalAction, default=None)
    p_rq.add_argument("--auto-populate-review", action="store_true", default=False)
    p_rq.add_argument("--summary", action="store_true", default=False)
    p_rq.add_argument("--verbose-json", action="store_true", default=False)

    p_df = subparsers.add_parser("flow", aliases=["diorama-flow"], help="Sharded Dual-Tier (Omni 1.2 Flash -> Veo 3.1 Lite) Google Flow clip generator")
    p_df.add_argument("--project", required=True)
    p_df.add_argument("--tabs", type=int, default=5)
    p_df.add_argument("--clips", default="")
    p_df.add_argument("--clean", action="store_true", default=False)
    p_df.add_argument("--cdp-port", type=int, default=9222)
    p_df.add_argument("--engine", default="auto", choices=["auto", "omni", "zero_credit", "zero-credit"])
    p_df.add_argument("--human-submit", action="store_true", default=False)
    p_df.add_argument("--fresh-room", action="store_true", default=False)

    p_fc = subparsers.add_parser("flow-clean", help="Clean finished Google Flow project rooms and stale /tmp artifacts")
    p_fc.add_argument("--all", dest="all_projects", action="store_true", default=False)
    p_fc.add_argument("--project", default=None)
    p_fc.add_argument("--prefix", default=None)
    p_fc.add_argument("--local-only", action="store_true", default=False)
    p_fc.add_argument("--include-speed-cache", action="store_true", default=False)
    p_fc.add_argument("--force-active", action="store_true", default=False)
    p_fc.add_argument("--dry-run", action="store_true", default=False)
    p_fc.add_argument("--cdp-port", type=int, default=9222)

    # Gear 4: Assembly, QA, Thumbnail & Knowledge Base
    p_da = subparsers.add_parser("assemble", aliases=["diorama-assemble"], help="Assemble expressive_25d_v8 Short @ 30fps (-14 LUFS) + Tier-1 QA")
    p_da.add_argument("--project", required=True)
    p_da.add_argument("--force", action=argparse.BooleanOptionalAction, default=True)
    p_da.add_argument("--posthoc-qa", action=argparse.BooleanOptionalAction, default=True)
    p_da.add_argument("--prosody-mode", default=None, choices=list(DIORAMA_V7_PROSODY_MODES))
    p_da.add_argument("--voice-preset", default=None, choices=list(DIORAMA_VOICE_PRESETS))
    p_da.add_argument("--preview-sec", type=float, default=None)
    p_da.add_argument("--allow-published-overwrite", action="store_true", default=False)
    p_da.add_argument("--plaque-optimize", action=argparse.BooleanOptionalAction, default=True)
    p_da.add_argument("--preserve-audio", action="store_true", default=False)
    p_da.add_argument("--summary", action="store_true", default=False)
    p_da.add_argument("--verbose-json", action="store_true", default=False)

    p_rc = subparsers.add_parser("recut", aliases=["diorama-recut"], help="Re-render selected EDL cuts from segment cache and re-mux")
    p_rc.add_argument("--project", required=True)
    p_rc.add_argument("--cuts", required=True)
    p_rc.add_argument("--allow-published-overwrite", action="store_true", default=False)

    p_de = subparsers.add_parser("diorama-episode", help="End-to-end dossier-backed episode production with optional checkpoint halt")
    p_de.add_argument("--slug", required=True)
    p_de.add_argument("--project", required=True)
    p_de.add_argument("--pillar", required=True)
    p_de.add_argument("--draft-subdir", default=None)
    p_de.add_argument("--precheck-only", action="store_true", default=False)
    p_de.add_argument("--stop-after", default=None, choices=["audio", "keyframes"])
    p_de.add_argument("--tabs", type=int, default=5)
    p_de.add_argument("--force", action="store_true", default=False)
    p_de.add_argument("--cdp-port", type=int, default=9222)
    p_de.add_argument("--engine", default="auto", choices=["auto", "omni", "zero_credit", "zero-credit"])
    p_de.add_argument("--voice-preset", default=None, choices=list(DIORAMA_VOICE_PRESETS))
    p_de.add_argument("--prosody-mode", default=None, choices=list(DIORAMA_V7_PROSODY_MODES))

    p_pq = subparsers.add_parser("prosody-qa", help="Run Prosody QA gates P1-P10")
    p_pq.add_argument("--project", required=True)
    p_pq.add_argument("--no-asr", action="store_true", default=False)
    p_pq.add_argument("--summary", action="store_true", default=False)
    p_pq.add_argument("--verbose-json", action="store_true", default=False)

    p_eq = subparsers.add_parser("episode-qa", help="Run Dynamic Per-Episode QA Contract verification")
    p_eq.add_argument("--project", required=True)
    p_eq.add_argument("--compile-only", action="store_true", default=False)
    p_eq.add_argument("--summary", action="store_true", default=False)
    p_eq.add_argument("--verbose-json", action="store_true", default=False)

    p_ph = subparsers.add_parser("posthoc-qa", help="Run R64 Post-Hoc Gate 2 clarity QA & viewer sheet generation")
    p_ph.add_argument("--project", required=True)
    p_ph.add_argument("--no-strips", action="store_true", default=False)
    p_ph.add_argument("--no-asr", action="store_true", default=False)
    p_ph.add_argument("--init-review", action="store_true", default=False)
    p_ph.add_argument("--auto-populate-review", action="store_true", default=False)
    p_ph.add_argument("--require-review", action="store_true", default=False)
    p_ph.add_argument("--sync-kb", action=argparse.BooleanOptionalAction, default=True)
    p_ph.add_argument("--summary", action="store_true", default=False)
    p_ph.add_argument("--verbose-json", action="store_true", default=False)

    p_autopsy = subparsers.add_parser("autopsy", aliases=["video-autopsy"], help="Run stream/LUFS/subtitle/provenance media probe")
    p_autopsy.add_argument("--project", default=None)
    p_autopsy.add_argument("--summary", action="store_true", default=False)
    p_autopsy.add_argument("--verbose-json", action="store_true", default=False)

    p_qs = subparsers.add_parser("qa-summary", help="Print compact <=1800B defect-first summary from on-disk QA reports")
    p_qs.add_argument("--project", default=None)
    p_qs.add_argument("--dir", default=None)
    p_qs.add_argument("--strict", action="store_true", default=False)

    p_verify = subparsers.add_parser("verify", help="Verify SHA-256 artifact manifest integrity")
    p_verify.add_argument("--project", required=True)

    p_th = subparsers.add_parser("thumbnail", help="Run R65 v4 50/50 In-Skull Cutaway Thumbnail Studio & TQ gates")
    p_th.add_argument("--project", default=None)
    p_th.add_argument("--all-diorama", action="store_true", default=False)
    p_th.add_argument("--unpublished-only", action="store_true", default=False)
    p_th.add_argument("--force", action="store_true", default=False)
    p_th.add_argument("--soft", action="store_true", default=False)
    p_th.add_argument("--generate-keyart", action="store_true", default=False)
    p_th.add_argument("--keyart-only", action="store_true", default=False)
    p_th.add_argument("--frames-only", action="store_true", default=False)
    p_th.add_argument("--cdp-port", type=int, default=9222)
    p_th.add_argument("--summary", action="store_true", default=False)
    p_th.add_argument("--verbose-json", action="store_true", default=False)

    p_kb = subparsers.add_parser("kb", help="Manage & query BCI_Shorts_Channel/knowledge_base/ (sync | stats | search)")
    p_kb.add_argument("action", choices=["sync", "stats", "search"])
    p_kb.add_argument("--project", default=None)
    p_kb.add_argument("--full-rescan", action="store_true", default=False)
    p_kb.add_argument("--run-missing-posthoc", action="store_true", default=False)
    p_kb.add_argument("--pack", default="clips", choices=["clips", "prompts", "analogies", "brain_models", "locations"])
    p_kb.add_argument("--query", default="")
    p_kb.add_argument("--grammar", default=None)
    p_kb.add_argument("--camera", default=None)
    p_kb.add_argument("--min-clarity", type=float, default=None)
    p_kb.add_argument("--style-profile", default=None)
    p_kb.add_argument("--limit", type=int, default=20)

    # Gear 5: Studio, Multi-Platform & Daily Ops
    p_mb = subparsers.add_parser("multi-bundle", help="Export TikTok, Instagram Reels/Carousel & YouTube Quiz bundle")
    p_mb.add_argument("--project", required=True)
    p_mb.add_argument("--copy-video", action="store_true", default=False)
    p_mb.add_argument("--no-copy-video", action="store_true", default=False)

    p_su = subparsers.add_parser("studio-upload", help="Upload Short to YouTube Studio (Unlisted/Scheduled)")
    p_su.add_argument("--project", required=True)
    p_su.add_argument("--visibility", default="unlisted", choices=["unlisted", "scheduled", "public", "private"])
    p_su.add_argument("--allow-instant-public", action="store_true", default=False)
    p_su.add_argument("--slot", type=int, choices=[1, 2, 3, 4, 5], default=None)
    p_su.add_argument("--date", default=None)
    p_su.add_argument("--dry-run", action="store_true", default=False)
    p_su.add_argument("--burn-first-frame", action="store_true", default=False)
    p_su.add_argument("--auto-link", action=argparse.BooleanOptionalAction, default=False)
    p_su.add_argument("--assign-playlist", action=argparse.BooleanOptionalAction, default=False)
    p_su.add_argument("--cdp-port", type=int, default=9222)

    p_sp = subparsers.add_parser("studio-pin", help="Post & pin seed-protected R35 academic DOI + debate comment")
    p_sp.add_argument("--project", default=None)
    p_sp.add_argument("--video-id", default=None)
    p_sp.add_argument("--all-public", action="store_true", default=False)
    p_sp.add_argument("--replace-existing", action="store_true", default=False)
    p_sp.add_argument("--force-immediate-pin", action="store_true", default=False)
    p_sp.add_argument("--dry-run", action="store_true", default=False)
    p_sp.add_argument("--cdp-port", type=int, default=9222)

    p_sl = subparsers.add_parser("studio-link", help="Plan or apply Short-to-Short Related Video circular ring (R35-B)")
    p_sl.add_argument("--action", choices=["plan", "apply", "seed-boost", "status"], default="plan")
    p_sl.add_argument("--mode", choices=["seed_boost", "semantic_chain"], default="seed_boost")
    p_sl.add_argument("--project", default=None)
    p_sl.add_argument("--target", default=None)
    p_sl.add_argument("--assign-playlists", action=argparse.BooleanOptionalAction, default=False)
    p_sl.add_argument("--dry-run", action="store_true", default=False)
    p_sl.add_argument("--force", action="store_true", default=False)
    p_sl.add_argument("--cdp-port", type=int, default=9222)

    p_ss = subparsers.add_parser("studio-settings", help="Verify/configure YouTube Studio channel settings & R75 playlist purge")
    p_ss.add_argument("--dry-run", action="store_true", default=False)
    p_ss.add_argument("--purge-playlists", action="store_true", default=False)
    p_ss.add_argument("--playlists-screenshot", default=None)
    p_ss.add_argument("--settings-screenshot", default=None)
    p_ss.add_argument("--audit-v8-readiness", action="store_true", default=False)
    p_ss.add_argument("--check-auto-dubbing", action="store_true", default=False)
    p_ss.add_argument("--lock-auto-dubbing-off", action="store_true", default=False)
    p_ss.add_argument("--check-home-shelves", action="store_true", default=False)
    p_ss.add_argument("--cdp-port", type=int, default=9222)

    p_sqz = subparsers.add_parser("studio-quiz", help="Publish/schedule 4-option YouTube Community Quiz Post")
    p_sqz.add_argument("--project", required=True)
    p_sqz.add_argument("--schedule", default=None)
    p_sqz.add_argument("--dry-run", action="store_true", default=False)
    p_sqz.add_argument("--cdp-port", type=int, default=9222)

    p_sin = subparsers.add_parser("studio-inbox", help="Zero-playback YouTube Studio comment inbox scanner & applier")
    p_sin.add_argument("--scan-only", action="store_true", default=False)
    p_sin.add_argument("--apply-approved", action="store_true", default=False)
    p_sin.add_argument("--dry-run", action="store_true", default=False)
    p_sin.add_argument("--cdp-port", type=int, default=9222)

    p_sw = subparsers.add_parser("studio-watchdog", help="Go-Live Watchdog: promote elapsed Scheduled Shorts, pin R35 & link R35-B")
    p_sw.add_argument("--cdp-port", type=int, default=9222)
    p_sw.add_argument("--apply", action="store_true", default=False)
    p_sw.add_argument("--no-pins", action="store_true", default=False)
    p_sw.add_argument("--no-links", action="store_true", default=False)
    p_sw.add_argument("--force-immediate-pin", action="store_true", default=False)

    p_sr = subparsers.add_parser("studio-report", help="Generate Daily YouTube Studio Traffic-Light Growth Report")
    p_sr.add_argument("--date", default=None)
    p_sr.add_argument("--compare-date", default=None)
    p_sr.add_argument("--dry-run", action="store_true", default=False)
    p_sr.add_argument("--cdp-port", type=int, default=9222)

    p_qsch = subparsers.add_parser("qa-scheduler", help="Daily 08:00 Cross-Platform QA Scheduler (HOLD/GO & 5-Asset stagger)")
    p_qsch.add_argument("--date", default=None)
    p_qsch.add_argument("--no-write", action="store_true", default=False)
    p_qsch.add_argument("--json", action="store_true", default=False)
    p_qsch.add_argument("--markdown", action="store_true", default=False)
    p_qsch.add_argument("--summary", action="store_true", default=False)
    p_qsch.add_argument("--verbose-json", action="store_true", default=False)

    p_igp = subparsers.add_parser("ig-publish", help="Publish Instagram 4:5 Carousel or 9:16 Reel")
    p_igp.add_argument("--project", required=True)
    p_igp.add_argument("--kind", default="reel", choices=["reel", "carousel"])
    p_igp.add_argument("--engine", default="auto", choices=["auto", "graph-api", "cdp"])
    p_igp.add_argument("--handle", default="allaboutbrain.official")
    p_igp.add_argument("--trial-strategy", default=None, choices=["SS_PERFORMANCE", "MANUAL"])
    p_igp.add_argument("--require-trial", action="store_true", default=False)
    p_igp.add_argument("--image-urls", default="")
    p_igp.add_argument("--video-url", default="")
    p_igp.add_argument("--cover-url", default="")
    p_igp.add_argument("--dry-run", action="store_true", default=False)
    p_igp.add_argument("--cdp-port", type=int, default=9222)

    p_ttp = subparsers.add_parser("tiktok-publish", help="Publish/schedule >=60s 9:16 Short to TikTok Studio")
    p_ttp.add_argument("--project", required=True)
    p_ttp.add_argument("--schedule-utc", default=None)
    p_ttp.add_argument("--handle", default="allaboutbrain_official")
    p_ttp.add_argument("--dry-run", action="store_true", default=False)
    p_ttp.add_argument("--cdp-port", type=int, default=9222)

    args = parser.parse_args()
    cmd = args.command

    if cmd == "ep":
        import json as _json
        from pipeline.episode_runner import get_episode_status, run_episode_until

        if args.action == "status":
            st_rep = get_episode_status(args.project)
            print(_json.dumps(st_rep, ensure_ascii=False))
            if not st_rep.get("exists"):
                sys.exit(1)
        else:
            run_rep = run_episode_until(
                args.project,
                until=str(args.until),
                cdp_port=int(args.cdp_port),
                tabs=int(args.tabs),
                engine_mode=str(args.engine),
            )
            print(_json.dumps(_shrink_json_payload(run_rep, max_bytes=1800), ensure_ascii=False))
            if str(run_rep.get("status") or "").startswith("PAUSED_"):
                sys.exit(2)
            if "FAILED" in str(run_rep.get("status") or ""):
                sys.exit(1)
        return
    if cmd == "news-radar":
        cmd_news_radar(args)
    elif cmd == "dossier":
        cmd_dossier(args)
    elif cmd == "prompt-gate":
        cmd_prompt_gate(args)
    elif cmd == "chart-preview":
        cmd_chart_preview(args)
    elif cmd in ("refs", "porcelain-refs"):
        cmd_porcelain_refs(args)
    elif cmd == "reenact-refs":
        cmd_reenact_refs(args)
    elif cmd == "ref-qa":
        cmd_ref_qa(args)
    elif cmd in ("flow", "diorama-flow"):
        import asyncio
        import inspect
        import json as _json
        from pipeline.flow_worker import run_sharded_diorama_flow_generation
        from pipeline.ref_qa import inspect_reference_image_pack

        cand_p = Path(args.project)
        p_dir_df = cand_p if cand_p.is_dir() else (Path(PROJECTS_DIR) / str(args.project).strip())
        ref_dir_df = p_dir_df / "03_visuals" / "reference_images"
        if ref_dir_df.exists() and any(ref_dir_df.glob("*.png")):
            ref_gate = inspect_reference_image_pack(p_dir_df, require_review=True, save_report=True)
            if not ref_gate.get("pre_generation_ready"):
                from pipeline.batch_runner import render_keyframe_contact_sheet

                sheet_p = render_keyframe_contact_sheet(p_dir_df)
                print(
                    _json.dumps(
                        {
                            "status": "REVIEW_PENDING" if ref_gate.get("cv_pre_generation_ready") else "QA_FAILED",
                            "stage": "Gate1_keyframe_semantic_review",
                            "project_id": p_dir_df.name,
                            "cv_pre_generation_ready": bool(ref_gate.get("cv_pre_generation_ready")),
                            "pre_generation_ready": False,
                            "contact_sheet": str(sheet_p) if sheet_p else None,
                            "review_file": str(ref_dir_df / "reference_semantic_review.json"),
                            "regenerate_image_ids": ref_gate.get("regenerate_image_ids") or [],
                        },
                        indent=2,
                        ensure_ascii=False,
                    )
                )
                sys.exit(2 if ref_gate.get("cv_pre_generation_ready") else 1)

        only = [int(x.strip()) for x in args.clips.split(",") if x.strip()] if args.clips.strip() else None
        eng_mode = str(args.engine).replace("-", "_")
        flow_sig = inspect.signature(run_sharded_diorama_flow_generation)
        flow_kwargs = {
            "project_id": args.project,
            "clean_existing": bool(args.clean),
            "only_clips": only,
            "max_parallel_tabs": int(args.tabs),
        }
        if "cdp_port" in flow_sig.parameters:
            flow_kwargs["cdp_port"] = int(args.cdp_port)
        if "engine_mode" in flow_sig.parameters:
            flow_kwargs["engine_mode"] = eng_mode
        if "human_submit" in flow_sig.parameters:
            flow_kwargs["human_submit"] = bool(getattr(args, "human_submit", False))
        if "fresh_room" in flow_sig.parameters:
            flow_kwargs["fresh_room"] = bool(getattr(args, "fresh_room", False))
        if bool(getattr(args, "human_submit", False)):
            flow_kwargs["max_parallel_tabs"] = 1
        asyncio.run(run_sharded_diorama_flow_generation(**flow_kwargs))
    elif cmd == "flow-clean":
        cmd_flow_clean(args)
    elif cmd in ("assemble", "diorama-assemble"):
        cmd_diorama_assemble(args)
    elif cmd in ("recut", "diorama-recut"):
        import json as _json
        from pipeline.assembler import recut_diorama_cuts

        cut_ids = [int(x) for x in str(args.cuts).split(",") if x.strip()]
        print(_json.dumps(recut_diorama_cuts(args.project, cut_ids, allow_published_overwrite=bool(args.allow_published_overwrite)), indent=2))
    elif cmd == "diorama-episode":
        import json as _json
        from pipeline.batch_runner import run_single_diorama_episode

        rep = run_single_diorama_episode(
            slug=str(args.slug),
            project_id=str(args.project),
            pillar=str(args.pillar),
            precheck_only=bool(args.precheck_only),
            tabs=int(args.tabs),
            force_regenerate=bool(args.force),
            cdp_port=int(args.cdp_port),
            engine_mode=str(args.engine).replace("-", "_"),
            voice_preset=args.voice_preset,
            prosody_mode=args.prosody_mode,
            draft_subdir=getattr(args, "draft_subdir", None),
            stop_after=getattr(args, "stop_after", None),
        )
        print(_json.dumps(rep, indent=2, ensure_ascii=False, default=str))
    elif cmd == "prosody-qa":
        import json as _json
        from pipeline.prosody_qa import evaluate_prosody_gates

        rep = evaluate_prosody_gates(args.project, run_asr=not bool(args.no_asr), strict_freshness=True)
        if getattr(args, "verbose_json", False):
            print(_json.dumps(rep, indent=2, ensure_ascii=False))
        else:
            p_dir_pq = Path(args.project) if Path(args.project).is_dir() else (Path(PROJECTS_DIR) / str(args.project))
            print(_json.dumps(build_compact_qa_digest(rep, stage="prosody-qa", report_path=p_dir_pq / "05_assembly/prosody_qa_report.json"), ensure_ascii=False))
        if not rep["passed"]:
            sys.exit(1)
    elif cmd == "episode-qa":
        cmd_episode_qa(args)
    elif cmd == "posthoc-qa":
        cmd_posthoc_qa(args)
    elif cmd in ("autopsy", "video-autopsy"):
        cmd_autopsy(args)
    elif cmd == "qa-summary":
        cmd_qa_summary(args)
    elif cmd == "verify":
        cmd_verify(args)
    elif cmd == "thumbnail":
        cmd_thumbnail(args)
    elif cmd == "kb":
        cmd_kb(args)
    elif cmd == "multi-bundle":
        import json as _json
        from pipeline.publish import export_multi_platform_bundle

        res = export_multi_platform_bundle(
            args.project,
            copy_video=bool(args.copy_video) and not bool(args.no_copy_video),
        )
        print(_json.dumps(res, indent=2, ensure_ascii=False))
    elif cmd == "studio-upload":
        cmd_studio_upload(args)
    elif cmd == "studio-pin":
        cmd_studio_pin(args)
    elif cmd == "studio-link":
        cmd_studio_link(args)
    elif cmd == "studio-settings":
        cmd_studio_settings(args)
    elif cmd == "studio-quiz":
        cmd_studio_quiz(args)
    elif cmd == "studio-inbox":
        cmd_studio_inbox(args)
    elif cmd == "studio-watchdog":
        cmd_studio_watchdog(args)
    elif cmd == "studio-report":
        cmd_studio_report(args)
    elif cmd == "qa-scheduler":
        cmd_qa_scheduler(args)
    elif cmd == "ig-publish":
        cmd_ig_publish(args)
    elif cmd == "tiktok-publish":
        cmd_tiktok_publish(args)



def cmd_studio_report(args):
    """Generates standardized 9-section YouTube Studio Daily Analytics & Growth Report."""
    from pipeline.studio.reporter import StudioAnalyticsReporter

    reporter = StudioAnalyticsReporter(cdp_port=args.cdp_port)
    print(f"\n[CLI] Generating YouTube Studio Daily Analytics & Growth Report (Dry-Run: {args.dry_run})...")
    res = reporter.generate_daily_report(
        report_date=args.date,
        compare_date=args.compare_date,
        dry_run=args.dry_run,
    )
    metrics = res["metrics"]
    ck = metrics["channel_kpis"]
    rk = metrics["retention_kpis"]
    print("\n========================================================")
    print(f"  YOUTUBE STUDIO DAILY REPORT GENERATED ({res['report_date']})")
    print("========================================================")
    print(f"  Compared Against:    {res['previous_report_date']}")
    print(f"  Subscribers Total:   {ck['subscribers_total']:,} (Prev: {ck['subscribers_prev']:,})")
    print(f"  24h Views:           {ck['views_24h']:,} (Prev: {ck['views_prev']:,})")
    print(f"  Avg View Duration:   {rk['avd_seconds']:.1f}s / {rk['avg_video_length_sec']:.1f}s (APV: {rk['apv_pct']:.1f}%)")
    print(f"  Viewed vs Swiped:    {rk['viewed_pct']:.1f}% Viewed / {rk['swiped_pct']:.1f}% Swiped Away")
    print(f"  Dashboard Charts:    {res['charts_path']}")
    print(f"  Markdown Report:     {res['markdown_path']}")
    print(f"  Latest Report Copy:  {res['latest_report_path']}")
    print(f"  Video Detail Charts: {res['video_detail_charts_path']}")
    print(f"  Video Detail Report: {res['video_detail_markdown_path']}")
    print(f"  Latest Video Detail: {res['latest_video_detail_report_path']}")
    print(f"  Raw JSON Snapshot:   {res['json_path']}")
    print(f"  Master Prompt File:  {res['master_prompt_path']}")
    print("========================================================\n")


# ==============================================================================
# Prompt System v5 commands (R44-R50)
# ==============================================================================
def cmd_dossier(args):
    import json

    from pipeline import research_dossier as rd

    if args.action == "checklist":
        for key, desc in rd.RESEARCH_CHECKLIST:
            print(f"- {key}: {desc}")
        return
    if args.action == "doi":
        print(json.dumps(rd.verify_doi(args.doi or ""), indent=2, ensure_ascii=False))
        return
    if args.action == "yt-search":
        print(json.dumps(rd.search_youtube(args.query or args.topic), indent=2, ensure_ascii=False))
        return
    if args.action == "audit-media":
        from collections import Counter
        from pipeline.config import WORKSPACE_ROOT

        if not args.slug:
            print("--slug or --all-queued is required for audit-media", file=sys.stderr)
            sys.exit(2)
        ds_root = Path(args.root) if getattr(args, "root", None) else None
        print(
            json.dumps(
                rd.audit_dossier_media_suitability(
                    rd.dossier_dir(args.slug, root=ds_root),
                    write_back=bool(getattr(args, "write", False)),
                ),
                indent=2,
                ensure_ascii=False,
            )
        )
        return
    if not args.slug:
        print("--slug is required for this action", file=sys.stderr)
        sys.exit(2)
    ds_root = Path(args.root) if getattr(args, "root", None) else None
    if args.action == "init":
        print(
            rd.init_dossier(
                args.slug,
                args.topic or args.slug,
                pillar=args.pillar,
                visual_mode=args.mode,
                root=ds_root,
                everyday_domain=getattr(args, "everyday_domain", ""),
            )
        )
    elif args.action == "validate":
        res = rd.validate_dossier(
            args.slug,
            root=ds_root,
            require_schema_v2=bool(getattr(args, "require_v2", False)),
        )
        if getattr(args, "verbose_json", False):
            print(json.dumps(res, indent=2, ensure_ascii=False))
        else:
            print(json.dumps(build_compact_qa_digest(res, stage="dossier", report_path=rd.dossier_dir(args.slug, root=ds_root) / "dossier.json"), ensure_ascii=False))
        if not res["ready"]:
            sys.exit(1)
    elif args.action == "seed":
        if getattr(args, "profile", "neuro_diorama") == "neuro_diorama":
            print(
                json.dumps(
                    rd.diorama_seed_from_dossier(
                        args.slug,
                        root=ds_root,
                        style_profile=getattr(args, "style_profile", None),
                        write_draft=True if getattr(args, "write", False) else None,
                        overwrite=bool(getattr(args, "overwrite", False)),
                    ),
                    indent=2,
                    ensure_ascii=False,
                )
            )
        else:
            print(json.dumps(rd.plan_seed_from_dossier(args.slug, root=ds_root), indent=2, ensure_ascii=False))
    elif args.action == "yt-analyze":
        media_id = args.media_id or rd.slugify(args.url or "ref")[-24:]
        out = rd.dossier_dir(args.slug, root=ds_root) / "media" / media_id
        print(json.dumps(rd.analyze_reference_video(args.url, out, section=args.section), indent=2, ensure_ascii=False))


def _load_gate_inputs(folder: Path):
    import json

    from pipeline.prompt_builder import is_diorama_v6_plan

    script_path = next((p for p in (folder / "02_script" / "script.json", folder / "script.json") if p.exists()), None)
    plan_path = next((p for p in (folder / "03_visuals" / "visual_plan.json", folder / "visual_plan.json") if p.exists()), None)
    if script_path is None or plan_path is None:
        raise SystemExit(f"script.json / visual_plan.json not found under {folder}")
    script_doc = json.loads(script_path.read_text(encoding="utf-8"))
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    if is_diorama_v6_plan(plan) or script_doc.get("profile") == "neuro_diorama":
        if isinstance(script_doc.get("sentences"), list) and script_doc["sentences"]:
            narrations = [str(s).strip() for s in script_doc["sentences"] if str(s).strip()]
        elif isinstance(script_doc.get("acts"), list):
            narrations = [
                str(s).strip()
                for act in script_doc["acts"]
                if isinstance(act, dict)
                for s in (act.get("sentences") or [])
                if str(s).strip()
            ]
        else:
            narrations = [str(s).strip() for s in (script_doc.get("clip_narrations") or []) if str(s).strip()]
    else:
        narrations = script_doc["clip_narrations"]
    return plan, narrations, script_doc


def cmd_prompt_gate(args):
    import json

    from pipeline.prompt_builder import (
        build_flow_prompts,
        is_diorama_v6_plan,
        is_v5_plan,
        validate_character_motion,
        validate_flow_prompts,
        validate_narrations,
    )
    from pipeline.prompt_gate import validate_production_diorama_v6

    folder = Path(args.dir)
    plan, narrations, script_doc = _load_gate_inputs(folder)
    clips = build_flow_prompts(plan, narrations)
    if is_diorama_v6_plan(plan):
        import re as _re
        from pipeline.config import is_expressive_v8_plan
        from pipeline.batch_runner import _PLAQUE_TRIGGER_NOUNS_RE
        from pipeline.prompt_builder import validate_flow_credit_safety_lint
        from pipeline.publish import validate_diorama_paradox_title

        is_v8_gate = is_expressive_v8_plan(plan, script_doc)
        issues = validate_production_diorama_v6(plan, narrations, clips, script_doc=script_doc)
        issues.extend(validate_flow_credit_safety_lint(plan, clips))
        raw_title = str(script_doc.get("title") or plan.get("title") or "").strip()
        if raw_title:
            issues.extend(validate_diorama_paradox_title(raw_title, is_expressive_v8=is_v8_gate))
        if is_v8_gate:
            from pipeline.config import PRE_R68H_FROZEN_V8_PROJECTS
            from pipeline.publish import validate_v8_viewer_description

            gate_pid = str(script_doc.get("project_id") or plan.get("project_id") or folder.name or "").strip()
            meta_gate_path = next(
                (p for p in (folder / "06_publish" / "metadata.json", folder / "metadata.json") if p.exists()),
                None,
            )
            if meta_gate_path is not None and gate_pid not in PRE_R68H_FROZEN_V8_PROJECTS:
                meta_gate_doc = json.loads(meta_gate_path.read_text(encoding="utf-8"))
                if isinstance(meta_gate_doc, dict) and "description" in meta_gate_doc:
                    for desc_err in validate_v8_viewer_description(
                        str(meta_gate_doc.get("description") or ""),
                        project_id=gate_pid,
                    ):
                        if desc_err not in issues:
                            issues.append(desc_err)
        for c in clips:
            sc = _re.sub(r"\b(?:without|zero|no)\s+[a-z\s,-]{1,35}", " ", str(c.get("scene") or ""), flags=_re.IGNORECASE)
            for allow_tok in (c.get("diegetic_text_allowlist") or []):
                if str(allow_tok or "").strip():
                    sc = _re.sub(_re.escape(str(allow_tok).strip()), " ", sc, flags=_re.IGNORECASE)
            hits = sorted({m.group(0).lower() for m in _PLAQUE_TRIGGER_NOUNS_RE.finditer(sc)})
            if hits:
                issues.append(f"[plaque_lock] clip {c['clip_number']} positive scene contains plaque-trigger word(s) {hits}")

    else:
        issues = []
        issues.extend(validate_flow_prompts([c["prompt"] for c in clips]))
        issues.extend(validate_narrations(narrations))
        issues.extend(validate_character_motion(clips))
        for c in clips:
            if c.get("cutoff_risk"):
                issues.append(
                    f"Clip {c.get('clip_number')}: cutoff_risk is True ({c.get('estimated_speech_sec')}s > {c.get('target_duration')})"
                )
    if plan.get("dossier"):
        from pipeline import research_dossier as rd

        if rd.dossier_dir(str(plan["dossier"])).exists():
            issues += rd.check_narration_facts(str(plan["dossier"]), narrations)
    contract_compiled = False
    if not issues and is_diorama_v6_plan(plan):
        from pipeline.episode_qa import write_episode_qa_contract

        write_episode_qa_contract(folder, plan, narrations, clips)
        contract_compiled = True
    warnings: list[str] = []
    if is_diorama_v6_plan(plan) and isinstance(script_doc, dict):
        from pipeline.stamp_overlay import validate_data_stamps

        _, warnings = validate_data_stamps(script_doc, narrations, return_warnings=True)
    pg_rep = {
        "project_id": folder.name,
        "passed": not issues,
        "issues": issues,
        "warnings": warnings,
        "contract_compiled": contract_compiled,
    }
    if getattr(args, "verbose_json", False):
        print(json.dumps(pg_rep, indent=2, ensure_ascii=False))
    else:
        print(json.dumps(build_compact_qa_digest(pg_rep, stage="prompt-gate", report_path=folder / "03_visuals/episode_qa_contract.json"), ensure_ascii=False))
    if issues:
        sys.exit(1)


def cmd_chart_preview(args):
    import json
    from pipeline.stamp_overlay import render_data_stamp_rgba_frame

    p_dir = Path(args.project) if Path(args.project).exists() else (Path(PROJECTS_DIR) / args.project)
    _, _, script_doc = _load_gate_inputs(p_dir)
    stamps = script_doc.get("data_stamps") or []
    out_dir = Path(args.out) if args.out else (p_dir / "05_assembly" / "chart_previews")
    out_dir.mkdir(parents=True, exist_ok=True)
    saved: list[str] = []
    for idx, st in enumerate(stamps, start=1):
        im = render_data_stamp_rgba_frame(st, t_rel=3.8, total_dur=4.5)
        out_p = out_dir / f"chart_preview_{idx:02d}.png"
        im.save(out_p, format="PNG")
        saved.append(str(out_p))
    print(json.dumps({"project": str(p_dir), "count": len(saved), "previews": saved}, indent=2, ensure_ascii=False))


def cmd_episode_qa(args):
    import json

    from pipeline.episode_qa import (
        verify_final_mp4_against_contract,
        verify_pre_flow_contract,
        write_episode_qa_contract,
    )
    from pipeline.prompt_builder import build_flow_prompts

    p_dir = Path(args.project) if Path(args.project).is_dir() else (Path(PROJECTS_DIR) / args.project)
    plan, narrations, script_doc = _load_gate_inputs(p_dir)
    clips = build_flow_prompts(plan, narrations)
    _, contract = write_episode_qa_contract(p_dir, plan, narrations, clips)
    gate1_issues = verify_pre_flow_contract(plan, narrations, clips, script_doc=script_doc)
    if args.compile_only:
        rep = {"project_id": p_dir.name, "passed": not gate1_issues, "gate1_issues": gate1_issues, "clips": len(clips)}
        if getattr(args, "verbose_json", False):
            print(json.dumps(rep, indent=2, ensure_ascii=False))
        else:
            print(json.dumps(build_compact_qa_digest(rep, stage="episode-qa", report_path=p_dir / "03_visuals/episode_qa_contract.json"), ensure_ascii=False))
        if gate1_issues:
            sys.exit(1)
        return
    rep = verify_final_mp4_against_contract(p_dir, contract=contract)
    if gate1_issues:
        rep["passed"] = False
        rep["gate1_issues"] = gate1_issues
    if getattr(args, "verbose_json", False):
        print(json.dumps(rep, indent=2, ensure_ascii=False))
    else:
        print(json.dumps(build_compact_qa_digest(rep, stage="episode-qa", report_path=p_dir / "05_assembly/dynamic_episode_qa_report.json"), ensure_ascii=False))
    if not rep.get("passed"):
        sys.exit(1)


def cmd_diorama_assemble(args):
    import json

    from pipeline.assembler import assemble_diorama_project
    from pipeline.episode_qa import verify_final_mp4_against_contract
    from pipeline.knowledge_hub import sync_project_to_knowledge_base
    from pipeline.media_probe import VideoAutopsyEngine

    run_ph = bool(getattr(args, "posthoc_qa", True))
    preview_sec = getattr(args, "preview_sec", None)
    res = assemble_diorama_project(
        args.project,
        force_rebuild=bool(args.force),
        run_posthoc_qa=False,
        prosody_mode=getattr(args, "prosody_mode", None),
        voice_preset=getattr(args, "voice_preset", None),
        preview_sec=preview_sec,
        allow_published_overwrite=bool(getattr(args, "allow_published_overwrite", False)),
        optimize_plaque_windows=bool(getattr(args, "plaque_optimize", True)),
        preserve_audio_master=bool(getattr(args, "preserve_audio", False)),
    )
    if preview_sec is not None:
        print(json.dumps(res, indent=2, ensure_ascii=False))
        return
    p_dir = Path(res["project_dir"])
    qa_all_ok = True
    if run_ph:
        from pipeline.media_cache import shared_mp4_decode_session
        from pipeline.posthoc_qa import run_posthoc_semantic_qa

        final_mp4_p = Path(res.get("final_mp4") or res.get("final_video") or (p_dir / "05_assembly" / "final_shorts_1080x1920.mp4"))
        with shared_mp4_decode_session(final_mp4_p):
            ph_rep = run_posthoc_semantic_qa(p_dir, save_report=True)
            res["posthoc_qa"] = ph_rep
            ep_rep = verify_final_mp4_against_contract(p_dir, save_report=True)
            aut_rep = VideoAutopsyEngine.inspect_project(p_dir, save_report=True)
        ph_summary = res.get("posthoc_qa") or {}
        ph_ok = bool(ph_summary.get("passed", False))
        ph_cv_ok = bool(ph_summary.get("cv_passed", ph_ok))
        ep_ok = bool(ep_rep.get("passed"))
        aut_ok = bool(aut_rep.get("passed"))
        res["episode_qa_passed"] = ep_ok
        res["autopsy_passed"] = aut_ok
        th_file = p_dir / "06_publish" / "thumbnail_report.json"
        if th_file.exists():
            th_doc = json.loads(th_file.read_text(encoding="utf-8"))
            res["thumbnail_passed"] = bool(th_doc.get("passed"))
            res["cover_frame_sec"] = th_doc.get("cover_frame_sec")
        qa_all_ok = ph_ok and ep_ok and aut_ok
        if qa_all_ok:
            res["status"] = "PASSED"
            sync_project_to_knowledge_base(p_dir)
        elif ph_cv_ok and ep_ok and aut_ok and not ph_ok:
            from pipeline.posthoc_qa import init_posthoc_semantic_review_template

            rev_f = p_dir / "05_assembly" / "posthoc_semantic_review.json"
            if not rev_f.exists():
                init_posthoc_semantic_review_template(p_dir, auto_populate_from_cv=False)
            res["status"] = "REVIEW_PENDING"
            res["review_file"] = str(rev_f)
            res["contact_sheets"] = list(ph_summary.get("viewer_sheets") or [])
            if getattr(args, "verbose_json", False):
                print(json.dumps(res, indent=2, ensure_ascii=False))
            else:
                compact_rev = _shrink_json_payload({
                    "stage": "diorama-assemble",
                    "project_id": p_dir.name,
                    "passed": False,
                    "status": "REVIEW_PENDING",
                    "final_video": res.get("final_mp4") or res.get("final_video"),
                    "review_file": res.get("review_file"),
                    "contact_sheets": res.get("contact_sheets") or [],
                    "issues": ["posthoc_semantic_review_pending"],
                    "warnings": [],
                }, max_bytes=1800)
                print(json.dumps(compact_rev, ensure_ascii=False))
            sys.exit(2)
    if getattr(args, "verbose_json", False):
        print(json.dumps(res, indent=2, ensure_ascii=False))
    else:
        asm_rep = {
            "project_id": p_dir.name,
            "passed": bool(qa_all_ok),
            "status": res.get("status", "PASSED" if qa_all_ok else "FAILED"),
            "issues": [] if qa_all_ok else ["assembly_or_post_qa_failed"],
            "warnings": [],
        }
        resolved_fv = str(res.get("final_mp4") or res.get("final_video") or (p_dir / "05_assembly/final_shorts_1080x1920.mp4"))
        dig_asm = build_compact_qa_digest(asm_rep, stage="diorama-assemble", report_path=resolved_fv)
        dig_asm["final_video"] = resolved_fv
        print(json.dumps(_shrink_json_payload(dig_asm, max_bytes=1800), ensure_ascii=False))
    if not qa_all_ok:
        sys.exit(1)


def cmd_thumbnail(args):
    import json

    from pipeline import thumbnail as thumbnail_studio
    from pipeline.config import PROJECTS_DIR, is_diorama_profile
    from pipeline.knowledge_hub import sync_project_to_knowledge_base
    from pipeline.storage import ProjectStorage

    strict = not bool(args.soft)
    mode = "backfill_soft" if args.soft else "production"
    targets: list[Path] = []
    if args.all_diorama:
        for p in sorted(Path(PROJECTS_DIR).iterdir()):
            if not p.is_dir():
                continue
            if not (p / "05_assembly" / "final_shorts_1080x1920.mp4").exists():
                continue
            if args.unpublished_only and (p / "06_publish" / "upload_receipt.json").exists():
                continue
            vp = thumbnail_studio._read_json(p / "03_visuals" / "visual_plan.json")
            sc = thumbnail_studio._read_json(p / "02_script" / "script.json")
            if is_diorama_profile(vp) or is_diorama_profile(sc):
                targets.append(p)
    elif args.project:
        cand = Path(args.project)
        targets.append(cand if cand.exists() else (Path(PROJECTS_DIR) / str(args.project)))
    else:
        raise SystemExit("Pass --project <id> or --all-diorama")

    summaries = []
    any_failed = False
    for p_dir in targets:
        rep = thumbnail_studio.run(
            p_dir,
            force=bool(args.force or getattr(args, "generate_keyart", False) or getattr(args, "keyart_only", False)),
            strict=False,
            mode=mode,
            generate_keyart=bool(getattr(args, "generate_keyart", False)),
            keyart_only=bool(getattr(args, "keyart_only", False)),
            frames_only=bool(getattr(args, "frames_only", False)),
            cdp_port=int(getattr(args, "cdp_port", 9222) or 9222),
        )
        if (p_dir / "00_project_manifest.json").exists():
            ProjectStorage.sync_existing_manifest_from_disk(p_dir)
        try:
            sync_project_to_knowledge_base(p_dir)
        except Exception:
            pass
        if not rep.get("passed"):
            any_failed = True
        summaries.append(
            {
                "project_id": rep["project_id"],
                "passed": rep["passed"],
                "failed_gates": rep["failed_gates"],
                "hook_text": rep["hook_text"],
                "hook_source": rep["hook_source"],
                "cover_frame_sec": rep["cover_frame_sec"],
                "primary_cut_index": rep["variants"]["A"]["cut_index"],
                "primary_clip_index": rep["variants"]["A"]["clip_index"],
                "primary_score": rep["variants"]["A"]["total_score"],
            }
        )
    out_obj = summaries[0] if (len(summaries) == 1 and not args.all_diorama) else {"count": len(summaries), "passed": not any_failed, "all_passed": not any_failed, "projects": summaries}
    if getattr(args, "verbose_json", False):
        print(json.dumps(out_obj, indent=2, ensure_ascii=False))
    elif len(summaries) == 1 and not args.all_diorama:
        s0 = summaries[0]
        th_dig = build_compact_qa_digest(
            {"project_id": s0["project_id"], "passed": s0["passed"], "issues": s0["failed_gates"], "cover_frame_sec": s0["cover_frame_sec"]},
            stage="thumbnail",
            report_path=targets[0] / "06_publish/thumbnail_report.json",
        )
        th_dig["failed_gates"] = list(s0["failed_gates"])[:16]
        th_dig["hook_text"] = s0["hook_text"]
        print(json.dumps(_shrink_json_payload(th_dig, max_bytes=1800), ensure_ascii=False))
    else:
        print(json.dumps(_shrink_json_payload(out_obj, max_bytes=1800), ensure_ascii=False))
    if strict and any_failed:
        sys.exit(1)


def cmd_posthoc_qa(args):
    import json

    from pipeline.config import POSTHOC_SEMANTIC_QA_REPORT_FILENAME
    from pipeline.posthoc_qa import (
        _resolve_project_dir,
        init_posthoc_semantic_review_template,
        run_posthoc_semantic_qa,
        validate_posthoc_semantic_review,
    )

    rep = run_posthoc_semantic_qa(
        project_id_or_dir=args.project,
        render_strips=not bool(args.no_strips),
        run_asr_sync=not bool(args.no_asr),
        require_review=(True if args.require_review else None),
        save_report=True,
        sync_knowledge_base=bool(args.sync_kb),
    )
    if args.init_review:
        rev_path = init_posthoc_semantic_review_template(
            args.project,
            qa_report=rep,
            auto_populate_from_cv=bool(args.auto_populate_review),
        )
        p_dir = _resolve_project_dir(args.project)
        if args.require_review:
            rep = run_posthoc_semantic_qa(
                project_id_or_dir=args.project,
                render_strips=False,
                run_asr_sync=not bool(args.no_asr),
                require_review=True,
                save_report=True,
                sync_knowledge_base=bool(args.sync_kb),
            )
        else:
            rep["semantic_review"] = validate_posthoc_semantic_review(
                p_dir,
                rep.get("final_mp4_sha256", ""),
                rep.get("edl_sha256", ""),
                int(rep["summary"]["cut_count"]),
            )
            (p_dir / "05_assembly" / POSTHOC_SEMANTIC_QA_REPORT_FILENAME).write_text(
                json.dumps(rep, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
        rep["review_template_written"] = str(rev_path)
    slim_out = {
        "project_id": rep["project_id"],
        "rule": rep["rule"],
        "schema_version": rep["schema_version"],
        "style_profile": rep["style_profile"],
        "passed": rep["passed"],
        "cv_passed": rep["cv_passed"],
        "summary": rep["summary"],
        "act_clarity_summary": rep["act_clarity_summary"],
        "grammar_clarity_summary": rep["grammar_clarity_summary"],
        "semantic_review": rep["semantic_review"],
        "viewer_sheets_count": len(rep.get("viewer_sheets") or []),
    }
    if "review_template_written" in rep:
        slim_out["review_template_written"] = rep["review_template_written"]
    if getattr(args, "verbose_json", False):
        print(json.dumps(rep, indent=2, ensure_ascii=False))
    else:
        p_dir_ph = _resolve_project_dir(args.project)
        ph_dig = build_compact_qa_digest(rep, stage="posthoc-qa", report_path=p_dir_ph / f"05_assembly/{POSTHOC_SEMANTIC_QA_REPORT_FILENAME}")
        ph_dig["cv_passed"] = rep.get("cv_passed")
        ph_dig["viewer_sheets_count"] = len(rep.get("viewer_sheets") or [])
        if "review_template_written" in rep:
            ph_dig["review_template_written"] = rep["review_template_written"]
        print(json.dumps(_shrink_json_payload(ph_dig, max_bytes=1800), ensure_ascii=False))
    if not rep.get("passed"):
        sys.exit(1)


def cmd_kb(args):
    import json

    from pipeline.config import QA_ANALYTICS_SUMMARY_FILENAME
    from pipeline.knowledge_hub import (
        ensure_knowledge_base_layout,
        query_knowledge_base,
        recompile_knowledge_aggregates,
        sync_all_projects_to_knowledge_base,
        sync_project_to_knowledge_base,
    )

    if args.action == "sync":
        if args.project:
            res = sync_project_to_knowledge_base(args.project)
        else:
            res = sync_all_projects_to_knowledge_base(
                run_missing_posthoc=bool(args.run_missing_posthoc),
                full_rescan=bool(getattr(args, "full_rescan", False)),
            )
        print(json.dumps(res, indent=2, ensure_ascii=False))
        return

    if args.action == "stats":
        paths = ensure_knowledge_base_layout()
        summary_path = paths["telemetry_dir"] / QA_ANALYTICS_SUMMARY_FILENAME
        if summary_path.exists():
            stats = json.loads(summary_path.read_text(encoding="utf-8"))
        else:
            stats = recompile_knowledge_aggregates()
        print(json.dumps(stats, indent=2, ensure_ascii=False))
        return

    if args.action == "search":
        hits = query_knowledge_base(
            pack=str(args.pack),
            query=str(args.query or ""),
            grammar=args.grammar,
            camera_move=args.camera,
            min_clarity=args.min_clarity,
            style_profile=args.style_profile,
            limit=int(args.limit),
        )
        print(json.dumps({"pack": args.pack, "count": len(hits), "results": hits}, indent=2, ensure_ascii=False))
        return




def cmd_ref_qa(args):
    import json

    from pipeline.ref_qa import build_and_verify_project_reference_pack, register_reference_image

    p_dir = Path(args.project) if Path(args.project).is_dir() else (Path(PROJECTS_DIR) / args.project)
    if args.register:
        register_reference_image(p_dir, args.register, args.source)
    rep = build_and_verify_project_reference_pack(
        p_dir,
        audit_extract_from_clips=args.audit,
        require_review=getattr(args, "require_review", None),
        auto_populate_review=bool(getattr(args, "auto_populate_review", False)),
    )
    rep.pop("images", None)
    if getattr(args, "verbose_json", False):
        print(json.dumps(rep, indent=2, ensure_ascii=False))
    else:
        print(json.dumps(build_compact_qa_digest(rep, stage="ref-qa", report_path=p_dir / "03_visuals/reference_image_qa_report.json"), ensure_ascii=False))
    if not rep.get("pre_generation_ready"):
        sys.exit(1)












def cmd_reenact_refs(args):
    import json

    from pipeline.archival_media import purge_reenactment_quarantine, translate_porcelain_keyframes

    p_dir = Path(PROJECTS_DIR) / str(args.project).strip()
    only_ids = {x.strip() for x in str(args.refs).split(",") if x.strip()} or None
    raw_batch = getattr(args, "batch_count", None)
    res = translate_porcelain_keyframes(
        project_dir=p_dir,
        slug=str(args.slug).strip(),
        cdp_port=int(args.cdp_port),
        only_ref_ids=only_ids,
        force=bool(args.force),
        backend=str(getattr(args, "backend", "flow")),
        batch_count=(int(raw_batch) if raw_batch is not None else None),
    )
    if bool(args.purge_quarantine):
        res["quarantine_purge"] = purge_reenactment_quarantine(slug=str(args.slug).strip())
    print(json.dumps(res, indent=2, ensure_ascii=False))
    if res.get("failed_ids"):
        sys.exit(1)


def cmd_porcelain_refs(args):
    import json

    from pipeline.reference_pack import ensure_porcelain_reference_pack

    p_dir = Path(args.project) if Path(args.project).is_dir() else (Path(PROJECTS_DIR) / str(args.project).strip())
    slug = str(getattr(args, "slug", "") or "").strip()
    d_dir = (Path(DOSSIERS_DIR) / slug) if slug and (Path(DOSSIERS_DIR) / slug).exists() else None
    from pipeline.batch_runner import render_keyframe_contact_sheet

    raw_batch = getattr(args, "batch_count", None)
    raw_refs = str(getattr(args, "refs", "") or "").strip()
    only_ids = {x.strip() for x in raw_refs.split(",") if x.strip()} or None
    res = ensure_porcelain_reference_pack(
        project_dir=p_dir,
        dossier_dir=d_dir,
        cdp_port=int(args.cdp_port),
        backend=str(getattr(args, "backend", "flow")),
        batch_count=(int(raw_batch) if raw_batch is not None else None),
        only_ref_ids=only_ids,
        force=bool(args.force),
        require_review=(True if getattr(args, "require_review", False) else None),
        auto_populate_review=False,
    )
    sheet_p = render_keyframe_contact_sheet(p_dir)
    if sheet_p:
        res["contact_sheet"] = str(sheet_p)
    print(json.dumps(res, indent=2, ensure_ascii=False))
    if not res.get("pre_generation_ready"):
        sys.exit(2 if res.get("cv_pre_generation_ready") else 1)






def cmd_studio_watchdog(args):
    import json

    from pipeline.studio.watchdog import run_studio_watchdog

    rep = run_studio_watchdog(
        cdp_port=int(args.cdp_port),
        dry_run=not bool(args.apply),
        apply_pins=not bool(args.no_pins),
        apply_links=not bool(args.no_links),
        force_immediate_pin=bool(getattr(args, "force_immediate_pin", False)),
    )
    print(json.dumps(rep, indent=2, ensure_ascii=False, default=str))


def cmd_qa_scheduler(args):
    import json

    from pipeline.studio.scheduler import run_qa_scheduler

    rep = run_qa_scheduler(
        target_date=getattr(args, "date", None),
        write_outputs=not bool(getattr(args, "no_write", False)),
    )
    if getattr(args, "markdown", False):
        print(rep.get("markdown", ""))
    elif getattr(args, "verbose_json", False):
        payload = {k: v for k, v in rep.items() if k != "markdown"}
        print(json.dumps(payload, indent=2, ensure_ascii=False, default=str))
    else:
        plats = rep.get("platforms") or {}
        yt_p = plats.get("youtube") or {}
        ig_p = plats.get("instagram") or {}
        tt_p = plats.get("tiktok") or {}
        yt_v = str(yt_p.get("verdict") or "HOLD")
        sched_issues = list(yt_p.get("block_reasons") or []) + list((rep.get("guardrails") or {}).get("violations") or [])
        compact_sched = _shrink_json_payload({
            "stage": "qa-scheduler",
            "target_date": rep.get("target_date"),
            "passed": yt_v in ("GO", "CONDITIONAL_GO"),
            "verdict": {"youtube": yt_v, "instagram": ig_p.get("verdict"), "tiktok": tt_p.get("verdict")},
            "ready_youtube": [c.get("project_id") for c in (yt_p.get("ready_candidates") or [])][:6],
            "issues": [str(x)[:140] for x in sched_issues[:10]],
            "warnings": [],
            "failed_gates": [] if (rep.get("guardrails") or {}).get("passed", True) else ["guardrails_hold"],
            "action_count": len(rep.get("execution_plan") or []),
            "report_path": str((rep.get("output_paths") or {}).get("latest_json") or ""),
        }, max_bytes=1800)
        print(json.dumps(compact_sched, ensure_ascii=False, default=str))




def cmd_news_radar(args):
    import json

    from pipeline.news_radar import scan_breaking_neuro_news

    rep = scan_breaking_neuro_news(
        window_days=int(args.days),
        max_candidates=int(args.max_candidates),
    )
    print(json.dumps(rep, indent=2, ensure_ascii=False))


def cmd_flow_clean(args):
    import json

    from pipeline.flow_workspace import clean_flow_workspace, purge_local_flow_temp_files

    if bool(args.local_only):
        rep = {
            "mode": "local_only",
            "local_temp_cleanup": purge_local_flow_temp_files(
                dry_run=bool(args.dry_run),
                include_speed_cache=bool(args.include_speed_cache),
            ),
        }
    else:
        rep = clean_flow_workspace(
            cdp_port=int(args.cdp_port),
            all_projects=bool(args.all_projects),
            project_id=str(args.project).strip() if args.project else None,
            prefix=str(args.prefix).strip() if args.prefix else None,
            dry_run=bool(args.dry_run),
            clean_local_temp=True,
            include_speed_cache=bool(args.include_speed_cache),
            force_active=bool(args.force_active),
        )
    print(json.dumps(rep, indent=2, ensure_ascii=False))


















def _resolve_cli_project_dir(project_or_path: str) -> Path:
    from pipeline.config import PROJECTS_DIR

    cand = Path(project_or_path)
    if cand.is_dir():
        return cand.resolve()
    proj = PROJECTS_DIR / str(project_or_path).strip()
    if proj.is_dir():
        return proj.resolve()
    raise FileNotFoundError(f"Project directory not found: {project_or_path}")


def cmd_studio_quiz(args):
    import json
    from pipeline.studio.community_posts import YouTubeCommunityPostManager

    p_dir = _resolve_cli_project_dir(args.project)
    mgr = YouTubeCommunityPostManager(cdp_port=int(args.cdp_port))
    res = mgr.publish_or_schedule_quiz(
        p_dir,
        schedule_et=args.schedule,
        dry_run=bool(args.dry_run),
    )
    print(json.dumps(res, indent=2, ensure_ascii=False))


def cmd_studio_inbox(args):
    import json
    from pipeline.studio.comments_inbox import StudioCommentsInboxManager

    mgr = StudioCommentsInboxManager(cdp_port=int(args.cdp_port))
    if getattr(args, "apply_approved", False):
        res = mgr.apply_approved_replies(dry_run=bool(args.dry_run))
    else:
        res = mgr.scan_unreplied_comments(dry_run=bool(args.dry_run))
    print(json.dumps(res, indent=2, ensure_ascii=False))


def cmd_ig_publish(args):
    import asyncio
    import json
    import os
    from pipeline.studio.instagram_uploader import (
        publish_instagram_carousel_graph_api,
        publish_instagram_reel_graph_api,
        upload_instagram_carousel_cdp,
        upload_instagram_reel_cdp,
        validate_instagram_carousel_slides,
    )

    p_dir = _resolve_cli_project_dir(args.project)
    bundle_dir = p_dir / "06_publish" / "multi_platform_bundle"
    receipt_path = p_dir / "06_publish" / f"instagram_{args.kind}_receipt.json"
    shot_path = p_dir / "06_publish" / f"instagram_{args.kind}_live_proof.png"

    ig_user_id = os.environ.get("IG_USER_ID", "").strip()
    ig_token = os.environ.get("IG_ACCESS_TOKEN", "").strip()

    if args.kind == "carousel":
        slides_dir = bundle_dir / "carousel_4x5"
        slide_paths = sorted(slides_dir.glob("slide_*.png"))
        if not slide_paths:
            raise FileNotFoundError(f"No carousel slides found in {slides_dir}; run `multi-bundle` first.")
        dims = validate_instagram_carousel_slides(slide_paths)
        cap_file = bundle_dir / "carousel_caption.txt"
        if not cap_file.is_file():
            raise FileNotFoundError(f"Missing carousel caption file: {cap_file}")
        caption = cap_file.read_text(encoding="utf-8").strip()
        image_urls = [u.strip() for u in str(args.image_urls or "").split(",") if u.strip()]
        use_graph = args.engine == "graph-api" or (args.engine == "auto" and bool(ig_user_id and ig_token and image_urls))

        if args.dry_run:
            res = {
                "status": "dry_run",
                "platform": "instagram",
                "kind": "carousel",
                "selected_engine": "graph_api" if use_graph else "cdp",
                "project_id": p_dir.name,
                "slide_count": len(slide_paths),
                "validated_dimensions": [f"{w}x{h}" for w, h in dims],
                "caption_chars": len(caption),
                "handle": f"@{str(args.handle).lstrip('@')}",
            }
            print(json.dumps(res, indent=2, ensure_ascii=False))
            return

        if use_graph:
            res = publish_instagram_carousel_graph_api(
                ig_user_id=ig_user_id,
                access_token=ig_token,
                image_urls=image_urls,
                caption=caption,
                slide_paths=slide_paths,
                receipt_path=receipt_path,
            )
        else:
            res = asyncio.run(
                upload_instagram_carousel_cdp(
                    slide_paths=slide_paths,
                    caption=caption,
                    handle=args.handle,
                    receipt_path=receipt_path,
                    live_screenshot_path=shot_path,
                    cdp_port=int(args.cdp_port),
                )
            )
        print(json.dumps(res, indent=2, ensure_ascii=False))
        return

    # kind == "reel"
    from pipeline.publish import resolve_bundle_video_path

    video_path = resolve_bundle_video_path(p_dir) or (bundle_dir / "video_clean.mp4")
    cover_path = bundle_dir / "cover_9x16.png"
    cap_file = bundle_dir / "reels_caption.txt"
    if not video_path.is_file():
        raise FileNotFoundError(f"Missing Reel MP4 (checked multi_platform_bundle & 05_assembly): {video_path}")
    if not cover_path.is_file():
        raise FileNotFoundError(f"Missing Reel 9:16 cover PNG: {cover_path}")
    if not cap_file.is_file():
        raise FileNotFoundError(f"Missing Reel caption file: {cap_file}")
    caption = cap_file.read_text(encoding="utf-8").strip()
    video_url = str(args.video_url or "").strip()
    cover_url = str(args.cover_url or "").strip() or None
    use_graph = args.engine == "graph-api" or (args.engine == "auto" and bool(ig_user_id and ig_token and video_url))

    if args.dry_run:
        res = {
            "status": "dry_run",
            "platform": "instagram",
            "kind": "reel",
            "selected_engine": "graph_api" if use_graph else "cdp",
            "project_id": p_dir.name,
            "video_path": str(video_path),
            "cover_path": str(cover_path),
            "caption_chars": len(caption),
            "trial_graduation_strategy": args.trial_strategy,
            "require_trial": bool(args.require_trial),
            "handle": f"@{str(args.handle).lstrip('@')}",
        }
        print(json.dumps(res, indent=2, ensure_ascii=False))
        return

    if use_graph:
        res = publish_instagram_reel_graph_api(
            ig_user_id=ig_user_id,
            access_token=ig_token,
            video_url=video_url,
            caption=caption,
            cover_url=cover_url,
            trial_graduation_strategy=args.trial_strategy,
            require_trial=bool(args.require_trial),
            receipt_path=receipt_path,
        )
    else:
        res = asyncio.run(
            upload_instagram_reel_cdp(
                video_path=video_path,
                cover_path=cover_path,
                caption=caption,
                handle=args.handle,
                receipt_path=receipt_path,
                live_screenshot_path=shot_path,
                cdp_port=int(args.cdp_port),
            )
        )
    print(json.dumps(res, indent=2, ensure_ascii=False))


def cmd_tiktok_publish(args):
    import asyncio
    import json
    from pipeline.publish import resolve_bundle_video_path
    from pipeline.studio.tiktok_uploader import upload_tiktok_video_cdp

    p_dir = _resolve_cli_project_dir(args.project)
    bundle_dir = p_dir / "06_publish" / "multi_platform_bundle"
    video_path = resolve_bundle_video_path(p_dir) or (bundle_dir / "video_clean.mp4")
    if not video_path.is_file():
        raise FileNotFoundError(f"Missing TikTok MP4 (checked multi_platform_bundle & 05_assembly): {video_path}")
    cover_path = bundle_dir / "cover_9x16.png"
    cap_file = bundle_dir / "tiktok_caption.txt"
    if not cap_file.is_file():
        raise FileNotFoundError(f"Missing TikTok caption file: {cap_file}; run `multi-bundle` first.")
    caption = cap_file.read_text(encoding="utf-8").strip()

    res = asyncio.run(
        upload_tiktok_video_cdp(
            video_path=video_path,
            cover_path=cover_path,
            caption=caption,
            handle=args.handle,
            schedule_at_utc=args.schedule_utc,
            dry_run=bool(args.dry_run),
            receipt_path=p_dir / "06_publish" / "tiktok_upload_receipt.json",
            live_screenshot_path=p_dir / "06_publish" / "tiktok_live_proof.png",
            cdp_port=int(args.cdp_port),
        )
    )
    print(json.dumps(res, indent=2, ensure_ascii=False))








if __name__ == "__main__":
    main()

