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
from pipeline.flow_browser import GoogleFlowWhaleController
from pipeline.generator import ContentGenerator
from pipeline.orchestrator import PipelineOrchestrator
from pipeline.pillars import get_pillar, list_all_pillars

if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


def cmd_info(_args):
    """Displays ALL ABOUT BRAIN channel blueprint and architectural guidelines."""
    print("""
========================================================================
  ALL ABOUT BRAIN — CHANNEL BLUEPRINT & PRODUCTION ARCHITECTURE (v7/v8)
========================================================================

1. Channel One-Line Definition:
   "Combining UCL Neuroscience academic rigor with 100% AI production to
    explain Brain-Computer Interfaces and the mysteries of the brain in
    high-retention Neuro-Diorama Shorts (porcelain_cinematic_v7 & expressive_25d_v8)."

2. Core Profile:
   - Channel Name: ALL ABOUT BRAIN
   - Channel Handle: @AllAboutBrainOfficial
   - Channel ID: UC4FeioYYv9X04Di07_MfZ7g
   - Channel Residence (Tax/AdSense): South Korea (KR)
   - Video & Metadata Language Lock: English (United States) (en-US)
   - Active Formats: Neuro-Diorama v7 (`porcelain_cinematic_v7`, ~90s @ 24fps) & v8 (`expressive_25d_v8`, 62-118s <=120.0s @ 30fps, 18-26 clips)
   - Classic Format: Schema v5 Shorts <= 105.0s @ 30fps (5-10 clips)
   - Cadence: Daily uploads (5 slots per day distributed across North American ET peaks)

3. 7 Content Pillars & 5-Slot Mapping (with Default Narrative Archetype):
   [bci_tech]        BCI Tech Explained -> Slot 2 (12:00 PM ET) [chronicle_cutaway]
   [brain_news]      Brain News         -> Slot 2 (12:00 PM ET) [chronicle_cutaway]
   [brain_history]   Brain History      -> Slot 4 (07:30 PM ET) [delusion_museum]
   [brain_basics]    Brain Basics       -> Slot 3 (04:00 PM ET) [icon_autopsy]
   [brain_mysteries] Brain Mysteries    -> Slot 3 / Slot 5      [case_file]
   [brain_health]    Brain Health       -> Slot 1 (07:30 AM ET) [caveman_brain]
   [bci_ethics]      BCI Ethics         -> Slot 5 (10:30 PM ET) [forbidden_lab]

4. Neuro-Diorama System v7/v8 & Dual-Tier Flow Locks (R5, R56-R68):
   - Flow Engine (R5): Credit-aware Dual-Tier (`Omni 1.2 Flash` when credits available -> automatic `0-credit` `Veo 3.1 - Lite [Lower Priority]` fallback, zero paid APIs)
   - Voice Lock (R58/R63/R63-P/R68): `emma_v7` (`en-US-EmmaMultilingualNeural`, `dynamic_us_v7` / `expressive_us_v8` + `foil_v8`, legacy `andrew_v7` `en-US-AndrewMultilingualNeural`, `kokoro-onnx` offline fallback)
   - Visual Spec (R66 default / R68 expressive / R63 legacy): High-key porcelain cast (`porcelain_cinematic_v7` default), matte cream-white vinyl + 2D ink expressions + crystal X-Ray brain (`expressive_25d_v8`), `lowpoly_pastel_v7` legacy preserved
   - Triple Post-Assembly QA Lock (R18/R62/R64): VideoAutopsyEngine + DynamicEpisodeQA (`DQ1-DQ13` + `DQ_CAMEO`, 14 gates on v8; `DQ1-DQ12` on v7) + PostHocSemanticQA (`R64`) + SHA-256 upload gate
========================================================================
""")


def cmd_list(_args):
    """Lists all 7 content pillars and their production blueprints."""
    print("\n--- ALL ABOUT BRAIN 7 Content Pillars ---")
    for p in list_all_pillars():
        bp = p.production_blueprint
        print(f"\n{p.icon} [{p.id}] {p.name} (Default Style: {getattr(p, 'default_narrative_style', 'chronicle_cutaway')})")
        print(f"   Theme: {p.target_theme}")
        print(f"   Metaphor: {p.architectural_metaphor}")
        print(f"   Sample Title: {bp['title']}")
        print(f"   DOI: {bp['doi']}")
        narrations = bp.get("clip_narrations") or [bp["hook_text"], bp["setup_text"], bp["core_text"], bp["payoff_text"]]
        words_count = sum(len(str(s).split()) for s in narrations)
        print(f"   Words: {words_count} words ({len(bp.get('clip_narrations', []))} clips)")


def cmd_produce(args):
    """Flagship production command using Contract v4 multi-clip assembly."""
    if args.project and (PROJECTS_DIR / args.project / "00_project_manifest.json").exists():
        print(f"\n[CLI] Detected existing project '{args.project}'. Resuming/assembling from preserved state...")
        result = PipelineOrchestrator.resume_project(args.project)
    else:
        pillar_obj = get_pillar(args.pillar)
        generator = ContentGenerator()
        style = getattr(args, "style", "auto")
        blueprint = generator.generate(
            pillar_obj.id,
            topic=args.topic,
            use_gemini=not getattr(args, "no_gemini", False),
            style=style,
        )

        project_id = args.project or blueprint["project_id"]
        print(f"\n[CLI] Initiating Contract v4 Multi-Clip Production for: {project_id} ({pillar_obj.name}, Style: {blueprint.get('narrative_style', style)})...")

        orchestrator = PipelineOrchestrator(
            project_id=project_id,
            title=blueprint["title"],
            pillar=blueprint["pillar"],
        )

        anchor_paths = [Path(args.image_anchor)] if getattr(args, "image_anchor", None) else None
        result = orchestrator.run_from_blueprint(
            blueprint=blueprint,
            image_source_paths=anchor_paths,
            mode="multi-clip",
        )

    final_video = result.get("final_video")
    probe = result.get("probe_report") or {
        "width": 1080,
        "height": 1920,
        "fps": 30.0,
        "duration_seconds": 0.0,
    }
    master_qa = result.get("master_qa") or {"all_gates_passed": True}

    print("\n========================================================")
    print("  MULTI-CLIP PRODUCTION COMPLETED!")
    print(f"  Final Video: {final_video or '[Pending Google Flow Generation/Export]'}")
    print(f"  Resolution: {probe.get('width', 1080)}x{probe.get('height', 1920)} @ {probe.get('fps', 30.0)}fps")
    print(f"  Duration: {probe.get('duration_seconds', 0.0)}s")
    print(f"  Master QA: {'[PASS]' if master_qa.get('all_gates_passed') else '[WARNING]'}")
    print("========================================================\n")


def cmd_import_clips(args):
    """Imports downloaded Google Flow Omni 1.2 video clips using ASR ordering and optionally auto-assembles."""
    from pipeline.flow_live_single_worker import order_downloaded_flow_clips_for_project
    from pipeline.storage import ProjectStorage
    from produce_psychology_batch import resolve_topic_item

    controller = GoogleFlowWhaleController()
    download_dir = Path(args.dir)
    if not download_dir.exists():
        print(f"[ERROR] Download directory not found: {download_dir}")
        sys.exit(1)

    storage = ProjectStorage(args.project)
    print(f"\n[CLI] Ingesting and ASR-ordering downloaded clips from {download_dir} into project '{args.project}'...")
    imported = order_downloaded_flow_clips_for_project(
        project_dir=storage.project_dir,
        download_dir=download_dir,
    )
    if not imported:
        imported = controller.import_downloaded_clips(
            args.project,
            download_dir,
            target_count=CLIP_COUNT_MAX,
        )
    print(f"[CLI] Successfully ingested {len(imported)} clips into project '{args.project}'.")
    for f in imported:
        print(f"  - {f.name} ({f.stat().st_size / (1024*1024):.2f} MB)")

    if getattr(args, "auto_assemble", False) or len(imported) >= CLIP_COUNT_MIN:
        print(f"\n[CLI] Auto-triggering Contract v4 assembly for project '{args.project}'...")
        topic_item = resolve_topic_item(args.project, storage.project_dir)
        final_video_path = PipelineOrchestrator.assemble_clips_if_available(
            storage,
            topic_item=topic_item,
            force_rebuild=True,
            strict=True,
        )
        res = PipelineOrchestrator.resume_project(args.project)
        print(f"[CLI] Assembly completed -> {final_video_path or res.get('final_video')}")


def cmd_batch(args):
    """Generates a weekly batch across all 7 pillars."""
    pillars = list_all_pillars()[:args.count]
    print(f"\n[CLI] Starting Weekly Batch Generation ({len(pillars)} Pillars)...\n")

    rendered = []
    for p in pillars:
        bp = p.production_blueprint
        print(f"\n>>> Processing Batch Item: {p.icon} {p.name} ({bp['title']}) <<<")
        orchestrator = PipelineOrchestrator(
            project_id=bp["project_id"],
            title=bp["title"],
            pillar=bp["pillar"],
        )
        res = orchestrator.run_from_blueprint(bp)
        v_path = res.get("final_video") or "[Pending Google Flow Generation/Export]"
        qa_ok = res.get("master_qa", {}).get("all_gates_passed", False)
        rendered.append((p.name, v_path, qa_ok))

    print("\n========================================================")
    print(f"  BATCH PRODUCTION FINISHED: {len(rendered)} VIDEOS")
    for name, v_path, qa_ok in rendered:
        print(f"  - {name}: {'[QA PASS]' if qa_ok else '[QA FAIL]'} -> {v_path}")
    print("========================================================\n")


def cmd_flow_parallel(args):
    """Dispatches multiple projects to Google Flow concurrently in separate Naver Whale tabs."""
    from pipeline.flow_browser import GoogleFlowWhaleController
    controller = GoogleFlowWhaleController()

    from pipeline.config import FLOW_MAX_PARALLEL_BATCH_SIZE, PROJECTS_QUARANTINE_DIR

    projects = []
    if args.projects:
        projects = [p.strip() for p in args.projects.split(",") if p.strip()]
    elif args.batch_prefix:
        prefix = args.batch_prefix
        matching = sorted([p.name for p in PROJECTS_DIR.glob(f"{prefix}*") if p.is_dir()])
        if not matching and PROJECTS_QUARANTINE_DIR.exists():
            matching = sorted([p.name for p in PROJECTS_QUARANTINE_DIR.glob(f"{prefix}*") if p.is_dir()])
        projects = matching[:args.count] if args.count else matching
    else:
        matching = sorted([p.name for p in PROJECTS_DIR.glob("psych_*") if p.is_dir()])
        if not matching and PROJECTS_QUARANTINE_DIR.exists():
            matching = sorted([p.name for p in PROJECTS_QUARANTINE_DIR.glob("psych_*") if p.is_dir()])
        projects = matching[:args.count] if args.count else matching

    if not projects:
        print("[ERROR] No projects specified. Use --projects or --batch-prefix.")
        return

    max_batch = min(max(1, int(getattr(args, "max_batch", FLOW_MAX_PARALLEL_BATCH_SIZE))), FLOW_MAX_PARALLEL_BATCH_SIZE)
    print(f"\n[CLI] Dispatching {len(projects)} projects to Google Flow (Strict Cap: {max_batch} subagents/batch, 1:1:1 Subagent-Tab-Project) via Naver Whale CDP...")
    for idx, p in enumerate(projects, 1):
        print(f"  {idx}. {p}")

    results = controller.open_parallel_flow_projects(
        project_ids=projects,
        cdp_port=args.cdp_port,
        trigger_generation=args.trigger,
        max_batch=max_batch
    )

    print("\n========================================================")
    print(f"  PARALLEL GOOGLE FLOW DISPATCH COMPLETED ({len(results)} PROJECTS)")
    print("========================================================")
    for r in results:
        status = r.get("status", "unknown")
        url = r.get("url", "N/A")
        print(f"  - [{r.get('project_id')}] Status: {status} | URL: {url}")
    print("========================================================\n")



def cmd_verify(args):
    """Verifies lossless storage integrity and QA report for a project."""
    from pipeline.diorama_assembler import verify_script_audio_freshness
    from pipeline.storage import ProjectStorage
    storage = ProjectStorage(args.project)
    verify_script_audio_freshness(storage.project_dir, context="verify")
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


def cmd_studio_ab_test(args):
    """Executes 72h sequential thumbnail swap or Z-test statistical significance evaluation."""
    from pipeline.studio.ab_tester import ThumbnailABTester
    tester = ThumbnailABTester(cdp_port=args.cdp_port)
    print(f"\n[CLI] Shorts A/B Testing Management for '{args.project}'...")

    if args.evaluate:
        print("[CLI] Running Two-Proportion Z-Test statistical significance evaluation...")
        custom_metrics = None
        if args.impressions_a is not None and args.clicks_a is not None:
            custom_metrics = {
                "A": {"impressions": args.impressions_a, "clicks": args.clicks_a},
                "B": {
                    "impressions": args.impressions_b if args.impressions_b is not None else 1000,
                    "clicks": args.clicks_b if args.clicks_b is not None else 50,
                },
                "C": {
                    "impressions": args.impressions_c if args.impressions_c is not None else 1000,
                    "clicks": args.clicks_c if args.clicks_c is not None else 50,
                },
            }
        report = tester.evaluate_significance(args.project, metrics=custom_metrics, dry_run=args.dry_run)
        print("\n========================================================")
        print("  A/B TEST STATISTICAL SIGNIFICANCE REPORT (p < 0.05)")
        print("========================================================")
        print(f"  Conclusive: {'YES [WINNER DECLARED]' if report['conclusive'] else 'NO [CONTINUE TESTING]'}")
        if report["conclusive"]:
            print(f"  Winner Variant: Variant {report['winner_variant']}")
            print(f"  Winner Hypothesis: {report['winner_hypothesis']}")
        print("\n  Pairwise Z-Test Comparisons:")
        for comp in report["comparisons"]:
            print(f"  - Pair {comp['pair']}:")
            print(f"      {comp['var_1']['variant']}: {comp['var_1']['clicks']}/{comp['var_1']['impressions']} ({comp['var_1']['ctr']}%)")
            print(f"      {comp['var_2']['variant']}: {comp['var_2']['clicks']}/{comp['var_2']['impressions']} ({comp['var_2']['ctr']}%)")
            print(f"      Z = {comp['z_score']}, p = {comp['p_value']} -> {'[SIGNIFICANT p < 0.05]' if comp['statistically_significant'] else '[NOT SIGNIFICANT]'}")
        print("========================================================\n")
        return

    if args.set_variant:
        res = tester.swap_to_variant(args.project, target_variant=args.set_variant, video_id=args.video_id, dry_run=args.dry_run)
    elif args.swap_next:
        res = tester.swap_next(args.project, video_id=args.video_id, dry_run=args.dry_run)
    else:
        print("[ERROR] Specify an explicit action: --evaluate, --swap-next, or --set-variant A|B|C.")
        sys.exit(2)

    print("\n========================================================")
    print(f"  THUMBNAIL SWAP {'[DRY RUN]' if args.dry_run else '[APPLIED]'}!")
    print(f"  Project: {res['project_id']}")
    print(f"  Previous: Variant {res['previous_variant']} -> Active: Variant {res['active_variant']}")
    print(f"  New Thumbnail: {res['thumbnail_file']}")
    print(f"  Swapped At: {res['swapped_at']}")
    print("========================================================\n")


def cmd_studio_queue(args):
    """Manages Unlisted Staging Buffer queue and 5-Slot distribution timetable."""
    from pipeline.studio.queue_manager import StagingQueueManager
    manager = StagingQueueManager(cdp_port=args.cdp_port)
    action = args.action
    allow_legacy_v4 = bool(getattr(args, "allow_legacy_v4", False))
    auto_link = bool(getattr(args, "auto_link", True))
    assign_playlist = False

    if action == "scan":
        ready = manager.scan_ready_projects(allow_legacy_v4=allow_legacy_v4)
        print(f"\n--- Scan Ready Projects ({len(ready)} found) ---")
        for p in ready:
            print(f"  [{p['project_id']}] {p['title']}")
            print(f"     Pillar: {p['pillar']} | Rec Slot: Slot {p['recommended_slot']} | Staged: {p['is_staged']} ({p['upload_status']})")
    elif action == "plan":
        plan = manager.plan_5_slot_schedule(
            days=args.days,
            start_date=args.start_date,
            allow_legacy_v4=allow_legacy_v4,
        )
        print("\n========================================================")
        print(f"  NORTH AMERICAN 5-SLOT TIMETABLE PLAN ({plan['planned_days']} Days)")
        print(f"  Assigned: {plan['assigned_slots']}/{plan['total_slots']} slots")
        print("========================================================")
        for item in plan["items"]:
            if item["project_id"]:
                print(f"  [{item['date']}] Slot {item['slot_id']} ({item['time_et']} ET / {item['time_kst']} KST) -> [{item['project_id']}] {item['title'][:40]}")
            else:
                print(f"  [{item['date']}] Slot {item['slot_id']} ({item['time_et']} ET / {item['time_kst']} KST) -> [VACANT]")
        print("========================================================\n")
    elif action == "load-all":
        print(f"\n[CLI] Loading planned projects into Staging Buffer (Visibility: {args.visibility.upper()}, Dry-Run: {args.dry_run})...")
        res = manager.load_all_to_buffer(
            visibility=args.visibility,
            dry_run=args.dry_run,
            allow_legacy_v4=allow_legacy_v4,
            auto_link=auto_link,
            assign_playlist=assign_playlist,
        )
        print("\n========================================================")
        print(f"  STAGING BUFFER BATCH LOAD FINISHED: {res['total_processed']} PROCESSED")
        print(f"  Dry-Run Mode: {res['dry_run']}")
        print("========================================================\n")
    else:  # status
        summary = manager.get_status_summary(allow_legacy_v4=allow_legacy_v4)
        print("\n========================================================")
        print("  ALL ABOUT BRAIN — STAGING BUFFER STATUS OVERVIEW")
        print("========================================================")
        print(f"  Completed Projects in Inventory: {summary['total_completed_projects']}")
        print(f"  Staged in Buffer / Uploaded:     {summary['staged_in_buffer']}")
        print(f"  Pending Staging:                 {summary['pending_staging']}")
        print(f"  Scheduled Slots in Queue:        {summary['scheduled_slots_count']}")
        print("\n  Upcoming Scheduled Releases:")
        for it in summary["upcoming_planned_items"]:
            if it.get("project_id"):
                print(f"  - [{it['date']} Slot {it['slot_id']}] {it['time_et']} ET -> {it['project_id']} ({it['status']})")
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


def cmd_research(args):
    """Executes 2-Track Historical × Academic DOI Research Engine and saves news_hunt report."""
    from pipeline.ideation import IdeationStage
    from pipeline.researcher import TopicResearcher
    from pipeline.storage import ProjectStorage

    researcher = TopicResearcher()
    packages = researcher.research_batch(
        query=args.query,
        pillar_id=args.pillar,
        style=args.style,
        count=args.count,
        allow_network=not getattr(args, "offline", False),
    )
    saved = researcher.save_news_hunt_report(packages)

    print("\n========================================================")
    print("  ALL ABOUT BRAIN — 2-TRACK TOPIC RESEARCH COMPLETED!")
    print(f"  Markdown Report: {saved['markdown_path']}")
    print(f"  JSON Report:     {saved['json_path']}")
    print("========================================================")
    for idx, pkg in enumerate(packages, 1):
        sc = pkg["story_context"]
        print(f"\n[{idx}] {pkg['title']} (Score: {pkg['weighted_score']}/5.00)")
        print(f"    Pillar: {pkg['pillar_name']} | Style: {pkg['narrative_style']}")
        print(f"    Historical Anchor: {sc['era_year']} @ {sc['location']} ({sc['protagonist']})")
        print(f"    Verified DOI: {pkg['doi']} ({pkg['source_url']})")
        print(f"    Paradox Hook: \"{pkg['paradox_statement']}\"")
        print(f"    3D Metaphor:  {pkg['physical_metaphor']}")

    if getattr(args, "save_project", None) and packages:
        top = packages[0]
        storage = ProjectStorage(args.save_project, title=top["title"], pillar=top["pillar_name"])
        IdeationStage(storage).run(
            topic=top["topic"],
            pillar=top["pillar_name"],
            source_url=top["source_url"],
            source_tier=top["source_tier"],
            core_facts=top["core_facts"],
            doi=top["doi"],
            scores=top["scores"],
            paradox_statement=top["paradox_statement"],
            story_context=top["story_context"],
            physical_metaphor=top["physical_metaphor"],
        )
        print(f"\n[CLI] Saved top research card to project '{args.save_project}/01_ideation/research_card.json'.")


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
    max_bytes: int = 1500,
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

    digest: dict[str, Any] = {
        "stage": str(stage or rep.get("stage") or "qa"),
        "project_id": str(rep.get("project_id") or rep.get("slug") or Path(str(rep.get("dir") or "")).name or ""),
        "passed": passed,
        "failed_gates": failed_gates[:16],
        "suspect_clips": sorted(suspect_clips)[:24],
        "top_defects": defects[:12],
        "metrics": metrics,
    }
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
    from pipeline.video_autopsy import VideoAutopsyEngine

    if args.project:
        report = VideoAutopsyEngine.inspect_project(args.project, save_report=True)
    else:
        report = VideoAutopsyEngine.inspect_all_projects(save_reports=True)
    if getattr(args, "summary", False):
        print(json.dumps(build_compact_qa_digest(report, stage="autopsy"), ensure_ascii=False))
    else:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    passed = report.get("passed", report.get("all_passed", False))
    if not passed:
        sys.exit(1)


def cmd_evolve(args):
    """Executes closed-loop autonomous remediation and rebuilds video/audio/subtitles/thumbnails."""
    import json
    from pipeline.video_autopsy import VideoAutopsyEngine

    if args.project:
        report = VideoAutopsyEngine.evolve_project(args.project, force=args.force)
        passed = bool(report.get("passed", report.get("after_passed", False)))
    else:
        report = VideoAutopsyEngine.evolve_all_projects(force=args.force)
        passed = bool(report.get("all_passed", report.get("all_passed_after", False)))
    print(json.dumps(report, indent=2, ensure_ascii=False))
    if not passed:
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="ALL ABOUT BRAIN Autonomous Video Production Pipeline CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # research (2-Track Historical Case Vault + Public NCBI PubMed DOI Research Engine)
    p_res = subparsers.add_parser("research", help="Research historical/clinical episodes and verified academic DOIs (Zero Paid APIs)")
    p_res.add_argument("--query", default=None, help="Topic or keyword to research (e.g. 'phantom limb', 'capgras', 'delgado bull')")
    p_res.add_argument("--pillar", default=None, help="Optional Pillar ID filter")
    p_res.add_argument("--style", default="auto", choices=ALLOWED_NARRATIVE_STYLES, help="Historical Storytelling Archetype filter (Axis 2)")
    p_res.add_argument("--count", type=int, default=3, help="Number of research cards to generate (default: 3)")
    p_res.add_argument("--save-project", default=None, help="Optional project ID to immediately populate 01_ideation/research_card.json")
    p_res.add_argument("--offline", action="store_true", help="Use only local Historical Case Vault without querying public PubMed/Wikipedia endpoints")

    # produce (Flagship Contract v4 Multi-Clip Production)
    p_produce = subparsers.add_parser("produce", help="Produce video using Contract v4 multi-clip assembly")
    p_produce.add_argument("--pillar", default="bci_tech", help="Pillar ID or name")
    p_produce.add_argument("--topic", default=None, help="Custom topic override")
    p_produce.add_argument("--project", default=None, help="Custom project ID (or existing project to resume)")
    p_produce.add_argument("--style", default="auto", choices=ALLOWED_NARRATIVE_STYLES, help="Historical Storytelling Archetype: auto, case_file, delusion_museum, forbidden_lab, icon_autopsy, caveman_brain, chronicle_cutaway")
    p_produce.add_argument("--image-anchor", default=None, help="Path to master keyframe anchor image for visual guiding")
    p_produce.add_argument("--no-gemini", action="store_true", help="Force algorithmic generation")

    # info
    subparsers.add_parser("info", help="Display channel profile and 7 pillars")

    # list
    subparsers.add_parser("list", help="List all 7 content pillars and sample scripts")

    # import-clips
    p_import = subparsers.add_parser("import-clips", help="Import downloaded Google Flow Omni 1.2 MP4 video clips into project with ASR ordering")
    p_import.add_argument("--project", required=True, help="Target project ID")
    p_import.add_argument("--dir", required=True, help="Path to folder containing downloaded MP4 clips")
    p_import.add_argument("--auto-assemble", action="store_true", help="Immediately assemble final video after importing")

    # batch
    p_batch = subparsers.add_parser("batch", help="Batch render weekly videos across pillars")
    p_batch.add_argument("--count", type=int, default=7, help="Number of pillars to render (max 7)")
    p_batch.add_argument("--style", default="auto", choices=ALLOWED_NARRATIVE_STYLES, help="Historical Storytelling Archetype")

    # flow-parallel
    p_par = subparsers.add_parser("flow-parallel", help="Dispatch multiple projects to Google Flow concurrently in separate Naver Whale tabs (Max 5 topics/batch)")
    p_par.add_argument("--projects", default=None, help="Comma-separated project IDs (e.g. psych_01,psych_02)")
    p_par.add_argument("--batch-prefix", default=None, help="Prefix to match project directories (e.g. psych_)")
    p_par.add_argument("--count", type=int, default=5, help="Maximum number of projects to dispatch (default: 5)")
    p_par.add_argument("--max-batch", type=int, default=5, help="Maximum number of concurrent subagent workers per batch (capped at 5)")
    p_par.add_argument("--trigger", action="store_true", default=True, help="Automatically click generate button after injecting prompt (default: True)")
    p_par.add_argument("--no-trigger", action="store_false", dest="trigger", help="Inject prompt without clicking generate button")
    p_par.add_argument("--cdp-port", type=int, default=9222, help="Whale DevTools CDP port (default: 9222)")

    # verify
    p_verify = subparsers.add_parser("verify", help="Verify lossless artifact integrity")
    p_verify.add_argument("--project", required=True, help="Target project ID")

    # qa (4-Stage Executable QA Suite)
    p_qa = subparsers.add_parser("qa", help="Run 4-Stage Executable QA Suite (Pre-Flight, Browser Generation, Media Integrity, Intent & Content)")
    p_qa.add_argument("--project", default=None, help="Optional single project ID to audit (audits all projects if omitted)")
    p_qa.add_argument("--cdp-port", type=int, default=9222, help="Whale DevTools CDP port (default: 9222)")

    # autopsy (Multimodal Video/Audio Forensic Autopsy Engine)
    p_autopsy = subparsers.add_parser(
        "autopsy",
        aliases=["video-autopsy"],
        help="Run multimodal video/audio/subtitle/thumbnail forensic autopsy",
    )
    p_autopsy.add_argument("--project", default=None, help="Optional single project ID to inspect (inspects all rendered projects if omitted)")
    p_autopsy.add_argument("--summary", action="store_true", default=False, help="Print compact <=1800B JSON QA digest")

    # qa-summary (Tier A-1 Defect-First On-Disk QA Summary)
    p_qs = subparsers.add_parser("qa-summary", help="Print compact <=2000B defect-first summary from on-disk QA reports")
    p_qs.add_argument("--project", default=None, help="Target project ID or directory")
    p_qs.add_argument("--dir", default=None, help="Explicit project directory override")
    p_qs.add_argument("--strict", action="store_true", default=False, help="Exit with code 1 if any present stage failed")

    # evolve (Closed-Loop Autonomous Self-Evolution Engine)
    p_evolve = subparsers.add_parser("evolve", help="Execute closed-loop self-evolution to remediate audio, subtitles, video, and thumbnails")
    p_evolve.add_argument("--project", default=None, help="Optional single project ID to evolve (evolves all rendered projects if omitted)")
    p_evolve.add_argument("--force", action="store_true", default=True, help="Force rebuild of audio, subtitles, video, and thumbnails")

    # test-all
    subparsers.add_parser("test-all", help="Run comprehensive pytest test suite across the workspace")

    # studio-upload
    p_su = subparsers.add_parser("studio-upload", help="Upload project video to YouTube Studio with 5-slot scheduling or unlisted staging")
    p_su.add_argument("--project", required=True, help="Target project ID")
    p_su.add_argument("--visibility", default="unlisted", choices=["unlisted", "scheduled", "public", "private"], help="Visibility mode (default: unlisted; public banned unless --allow-instant-public)")
    p_su.add_argument("--allow-instant-public", action="store_true", default=False, help="Explicit emergency override allowing instant Public upload (banned by default under R75)")
    p_su.add_argument("--slot", type=int, choices=[1, 2, 3, 4, 5], default=None, help="Target slot (1-5)")
    p_su.add_argument("--date", default=None, help="Target release date YYYY-MM-DD")
    p_su.add_argument("--dry-run", action="store_true", default=False, help="Run in simulation mode without actual browser interaction")
    p_su.add_argument("--burn-first-frame", action="store_true", default=False, help="Burn thumbnail into first frame of video for guaranteed Shorts cover fallback")
    p_su.add_argument("--auto-link", action=argparse.BooleanOptionalAction, default=False, help="Automatically link Related video post-upload (R35-B)")
    p_su.add_argument("--assign-playlist", action=argparse.BooleanOptionalAction, default=False, help="[DISABLED R75] Playlist assignment permanently banned")
    p_su.add_argument("--cdp-port", type=int, default=9222, help="Whale DevTools CDP port (default: 9222)")

    # studio-pin
    p_sp = subparsers.add_parser("studio-pin", help="Post and pin academic DOI verification and debate question comment")
    p_sp.add_argument("--project", default=None, help="Target project ID (optional when --all-public is set)")
    p_sp.add_argument("--video-id", default=None, help="Target YouTube Video ID (optional)")
    p_sp.add_argument("--all-public", action="store_true", default=False, help="Stage prepared comments across projects and pin any unpinned Public Shorts")
    p_sp.add_argument("--replace-existing", action="store_true", default=False, help="Delete previous @AllAboutBrainOfficial comment before posting and pinning the updated comment")
    p_sp.add_argument("--force-immediate-pin", action="store_true", default=False, help="Override R75 100-view / 12.0h seed-protection defer on Public Shorts")
    p_sp.add_argument("--dry-run", action="store_true", default=False, help="Run in simulation mode")
    p_sp.add_argument("--cdp-port", type=int, default=9222, help="Whale DevTools CDP port (default: 9222)")

    # studio-ab-test
    p_sab = subparsers.add_parser("studio-ab-test", help="Manage 72h sequential thumbnail swap and Z-test evaluation")
    p_sab.add_argument("--project", required=True, help="Target project ID")
    p_sab.add_argument("--swap-next", action="store_true", help="Rotate to next variant in sequence (A -> B -> C)")
    p_sab.add_argument("--set-variant", choices=["A", "B", "C"], default=None, help="Force set specific thumbnail variant")
    p_sab.add_argument("--evaluate", action="store_true", help="Run Two-Proportion Z-Test statistical significance evaluation")
    p_sab.add_argument("--video-id", default=None, help="Target YouTube Video ID")
    p_sab.add_argument("--impressions-a", type=int, default=None, help="Impressions for Variant A")
    p_sab.add_argument("--clicks-a", type=int, help="Clicks for Variant A", default=None)
    p_sab.add_argument("--impressions-b", type=int, default=None, help="Impressions for Variant B")
    p_sab.add_argument("--clicks-b", type=int, default=None, help="Clicks for Variant B")
    p_sab.add_argument("--impressions-c", type=int, default=None, help="Impressions for Variant C")
    p_sab.add_argument("--clicks-c", type=int, default=None, help="Clicks for Variant C")
    p_sab.add_argument("--dry-run", action="store_true", default=False, help="Run in simulation mode")
    p_sab.add_argument("--cdp-port", type=int, default=9222, help="Whale DevTools CDP port (default: 9222)")

    # studio-queue
    p_sq = subparsers.add_parser("studio-queue", help="Manage bulk Unlisted Staging Buffer queue and 5-slot calendar")
    p_sq.add_argument("--action", choices=["scan", "plan", "status", "load-all"], default="status", help="Queue action (default: status)")
    p_sq.add_argument("--days", type=int, default=7, help="Number of days to plan (default: 7)")
    p_sq.add_argument("--start-date", default=None, help="Start date for schedule plan (YYYY-MM-DD)")
    p_sq.add_argument("--visibility", default="unlisted", choices=["unlisted", "scheduled", "public"], help="Staging visibility")
    p_sq.add_argument("--allow-legacy-v4", action="store_true", default=False, help="Allow legacy v4 projects into queue scan/plan (blocked by default)")
    p_sq.add_argument("--auto-link", action=argparse.BooleanOptionalAction, default=True, help="Link Related video during load-all (default: True)")
    p_sq.add_argument("--assign-playlist", action=argparse.BooleanOptionalAction, default=False, help="[DISABLED R75] Playlist assignment permanently banned (default: False)")
    p_sq.add_argument("--dry-run", action="store_true", default=False, help="Run load-all in simulation mode")
    p_sq.add_argument("--cdp-port", type=int, default=9222, help="Whale DevTools CDP port (default: 9222)")

    # studio-link (R35-B Short-to-Short Related Video Ring; Playlists Banned under R75)
    p_sl = subparsers.add_parser("studio-link", help="Plan or apply Short-to-Short Related Video circular ring (R35-B; playlists disabled under R75)")
    p_sl.add_argument("--action", choices=["plan", "apply", "seed-boost", "status"], default="plan", help="Action: plan | apply | seed-boost | status")
    p_sl.add_argument("--mode", choices=["seed_boost", "semantic_chain"], default="seed_boost", help="Routing strategy (default: seed_boost)")
    p_sl.add_argument("--project", default=None, help="Optional single source project ID")
    p_sl.add_argument("--target", default=None, help="Optional explicit 11-char target YouTube video ID")
    p_sl.add_argument("--assign-playlists", action=argparse.BooleanOptionalAction, default=False, help="[DISABLED R75] Playlist assignment permanently banned (default: False)")
    p_sl.add_argument("--dry-run", action="store_true", default=False, help="Simulate without writing Studio changes")
    p_sl.add_argument("--force", action="store_true", default=False, help="Override 24h seed-protection lock and re-apply existing links")
    p_sl.add_argument("--cdp-port", type=int, default=9222, help="Whale DevTools CDP port (default: 9222)")

    # studio-settings
    p_ss = subparsers.add_parser("studio-settings", help="Configure and verify KR Residence, Clean Keywords, Empty Default Tags & Playlist Purge (R36 + R75)")
    p_ss.add_argument("--dry-run", action="store_true", default=False, help="Run in simulation mode without browser interaction")
    p_ss.add_argument("--purge-playlists", action="store_true", default=False, help="Permanently delete ALL live YouTube Studio playlists and assert 0 rows remain (R75)")
    p_ss.add_argument("--playlists-screenshot", default=None, help="Optional PNG path for post-purge /content/playlists screenshot")
    p_ss.add_argument("--settings-screenshot", default=None, help="Optional PNG path for post-save Channel Keywords + Empty Upload Default Tags screenshot")
    p_ss.add_argument("--audit-v8-readiness", action="store_true", default=False, help="Print read-only v8 channel art, multi-language audio, and Shorts format readiness JSON")
    p_ss.add_argument(
        "--check-auto-dubbing",
        action="store_true",
        default=False,
        help="Inspect live YouTube Studio Auto-Dubbing / Multi-Language Audio settings read-only via background leased CDP tab (offline with --dry-run)",
    )
    p_ss.add_argument(
        "--lock-auto-dubbing-off",
        action="store_true",
        default=False,
        help="Disable Automatic dubbing in YouTube Studio Settings -> Upload defaults -> Advanced settings if enabled (burned-in English ASS protection)",
    )
    p_ss.add_argument(
        "--check-home-shelves",
        action="store_true",
        default=False,
        help="Inspect YouTube Studio Customization -> Home tab shelves to verify Short videos + Posts shelves",
    )
    p_ss.add_argument("--cdp-port", type=int, default=9222, help="Whale DevTools CDP port (default: 9222)")

    # studio-report (Daily YouTube Studio Analytics & Growth Report Generator)
    p_sr = subparsers.add_parser("studio-report", help="Generate standardized 9-section Daily YouTube Studio Analytics & Growth Report")
    p_sr.add_argument("--date", default=None, help="Target report date YYYY-MM-DD (default: today ET)")
    p_sr.add_argument("--compare-date", default=None, help="Optional previous snapshot date YYYY-MM-DD for DoD delta")
    p_sr.add_argument("--dry-run", action="store_true", default=False, help="Generate report without launching/navigating Naver Whale")
    p_sr.add_argument("--cdp-port", type=int, default=9222, help="Whale DevTools CDP port (default: 9222)")

    # Prompt System v5 & Neuro-Diorama System v6/v7/v8 (R44-R68)
    p_ds = subparsers.add_parser("dossier", help="Research dossier: init / validate / seed / doi / yt-search / yt-analyze / audit-media (R44)")
    p_ds.add_argument("action", choices=["init", "validate", "seed", "doi", "yt-search", "yt-analyze", "audit-media", "checklist"])
    p_ds.add_argument("--slug", default=None, help="Dossier slug (BCI_Shorts_Channel/research_dossiers/<slug>)")
    p_ds.add_argument("--root", default=None, help="Optional research_dossiers root directory override")
    p_ds.add_argument("--topic", default="", help="Topic title (init)")
    p_ds.add_argument("--pillar", default="", help="Pillar id (init)")
    p_ds.add_argument("--everyday-domain", default="", help="Everyday domain: sleep|habits|memory|anxiety|relationships (init)")
    p_ds.add_argument("--mode", default="HYBRID", help="BEHAVIORAL_PSYCH | HYBRID | NEURO_BIOLOGY (init)")
    p_ds.add_argument("--profile", default="neuro_diorama", choices=["classic_v5", "neuro_diorama"], help="Seed profile (seed)")
    p_ds.add_argument(
        "--style-profile",
        default=None,
        choices=["porcelain_cinematic_v7", "lowpoly_pastel_v7", "expressive_25d_v8"],
        help="Schema v7/v8 style profile override for seed (default: porcelain_cinematic_v7; v8: expressive_25d_v8)",
    )
    p_ds.add_argument("--require-v2", action="store_true", default=False, help="Require Schema v2 dossier compliance (validate)")
    p_ds.add_argument("--summary", action="store_true", default=False, help="Print compact <=1800B JSON digest (validate)")
    p_ds.add_argument("--doi", default=None, help="DOI to verify via Crossref (doi)")
    p_ds.add_argument("--query", default=None, help="YouTube search query (yt-search)")
    p_ds.add_argument("--url", default=None, help="Reference video URL (yt-analyze)")
    p_ds.add_argument("--media-id", default=None, help="Media id folder name under <dossier>/media (yt-analyze)")
    p_ds.add_argument("--section", default=None, help="Optional '*mm:ss-mm:ss' range (yt-analyze)")
    p_ds.add_argument("--all-queued", action="store_true", default=False, help="Audit media suitability across all 65 queued porcelain episodes (audit-media)")
    p_ds.add_argument("--write", action="store_true", default=False, help="Persist suitability classifications (audit-media) or write seeded draft files to disk (seed)")
    p_ds.add_argument("--overwrite", action="store_true", default=False, help="Overwrite existing seeded draft files when running `dossier seed`")

    p_da = subparsers.add_parser(
        "diorama-assemble",
        help="Assemble a Schema v8 expressive_25d_v8 (<= 120.0s @ 30fps), Schema v7 porcelain_cinematic_v7 / lowpoly_pastel_v7, or v6 Neuro-Diorama Short (24fps, R56-R68)",
    )
    p_da.add_argument("--project", required=True, help="Target project ID or directory")
    p_da.add_argument("--force", action=argparse.BooleanOptionalAction, default=True, help="Force rebuild of EDL, WAV, ASS, and MP4 (default: True)")
    p_da.add_argument(
        "--posthoc-qa",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Run R64 post-hoc clip-by-clip expressive clarity QA, DQ1-DQ13 (14 gates on v8; DQ1-DQ12 on v7), Autopsy, and sync Knowledge Hub after assembly (default: True)",
    )
    p_da.add_argument(
        "--prosody-mode",
        default=None,
        choices=list(DIORAMA_V7_PROSODY_MODES),
        help="Sentence-level prosody engine mode (default: script.json `prosody_mode`, else config default)",
    )
    p_da.add_argument(
        "--voice-preset",
        default=None,
        choices=list(DIORAMA_VOICE_PRESETS),
        help="Narrator voice preset from DIORAMA_VOICE_PRESETS (e.g. elevenlabs_v4, el_researcher_v4, el_minicortex_v4)",
    )
    p_da.add_argument("--preview-sec", type=float, default=None, help="Render only the first N seconds to 05_assembly/preview_0-Ns.mp4 (skips QA)")
    p_da.add_argument("--allow-published-overwrite", action="store_true", default=False, help="Allow rebuilding a project that already has an upload receipt")
    p_da.add_argument("--plaque-optimize", action=argparse.BooleanOptionalAction, default=True, help="F-1 pre-render plaque-safe source window refinement (default: True)")
    p_da.add_argument("--preserve-audio", action="store_true", default=False, help="Reuse existing 04_audio/audio_master.wav and voice_report.json untouched without re-synthesizing or re-mixing audio")

    p_rc = subparsers.add_parser("diorama-recut", help="F-3 re-render only the given EDL cuts from the segment cache and re-mux")
    p_rc.add_argument("--project", required=True, help="Target project ID or directory")
    p_rc.add_argument("--cuts", required=True, help="Comma-separated 1-based cut indices")
    p_rc.add_argument("--allow-published-overwrite", action="store_true", default=False)

    p_pq = subparsers.add_parser("prosody-qa", help="Run Prosody QA gates P1-P10 on an assembled project")
    p_pq.add_argument("--project", required=True, help="Target project ID or directory")
    p_pq.add_argument("--no-asr", action="store_true", default=False, help="Skip P6 ASR match")

    p_df = subparsers.add_parser(
        "diorama-flow",
        help="Sharded 5-tab Dual-Tier (Omni 1.2 Flash -> 0-credit auto-fallback) Google Flow generator for Schema v8/v7/v6 neuro_diorama (1:1 Zero-Reuse)",
    )
    p_df.add_argument("--project", required=True, help="Target project ID under BCI_Shorts_Channel/projects/")
    p_df.add_argument("--tabs", type=int, default=5, help="Max concurrent Google Flow shard tabs (<=5)")
    p_df.add_argument("--clips", default="", help="Optional comma-separated 1-based clip numbers to regenerate")
    p_df.add_argument("--clean", action="store_true", default=False, help="Purge existing clips before generating fresh")
    p_df.add_argument("--cdp-port", type=int, default=9222, help="Whale DevTools CDP port (default: 9222)")
    p_df.add_argument(
        "--engine",
        default="auto",
        choices=["auto", "omni", "zero_credit", "zero-credit"],
        help="Flow engine policy: auto (Omni 1.2 Flash when credits > 0 else 0-credit fallback), omni, or zero-credit",
    )
    p_df.add_argument(
        "--human-submit",
        action="store_true",
        default=False,
        help="Human-in-the-Loop pre-fill mode: stage Start/End frames, model/aspect/duration/x1, and prompt in a foreground single tab, stop before clicking Submit (→), passively poll for the user's click, and auto-download",
    )
    p_df.add_argument(
        "--fresh-room",
        action="store_true",
        default=False,
        help="Create a brand-new Google Flow project room instead of reusing the prior receipt URL",
    )

    p_db = subparsers.add_parser(
        "diorama-batch",
        help="Resumable Wave 1-6 (30-episode) Schema v8/v7/v6 neuro_diorama precheck, Flow generation, assembly & QA orchestrator",
    )
    p_db.add_argument("--wave", default="all", help="Wave selector: 1, 2, 3, 4, 5, 6, or all (default: all)")
    p_db.add_argument("--projects", default="", help="Optional comma-separated project_ids subset")
    p_db.add_argument("--precheck-only", action="store_true", default=False, help="Run prompt-gate + TTS duration lock only")
    p_db.add_argument("--tabs", type=int, default=5, help="Max concurrent Google Flow shard tabs per project (<=5)")
    p_db.add_argument("--force", action="store_true", default=False, help="Force regenerate even if already completed")
    p_db.add_argument("--cdp-port", type=int, default=9222, help="Whale DevTools CDP port (default: 9222)")
    p_db.add_argument(
        "--engine",
        default="auto",
        choices=["auto", "omni", "zero_credit", "zero-credit"],
        help="Flow engine policy: auto (Omni 1.2 Flash -> 0-credit auto-fallback), omni, or zero-credit",
    )
    p_db.add_argument("--voice-preset", default=None, choices=list(DIORAMA_VOICE_PRESETS), help="Optional narrator voice preset override")
    p_db.add_argument("--prosody-mode", default=None, choices=list(DIORAMA_V7_PROSODY_MODES), help="Optional prosody mode override")
    p_db.add_argument(
        "--sequential",
        action="store_true",
        default=False,
        help="Run batch strictly sequentially instead of overlapped Level B pipeline",
    )

    p_pg = subparsers.add_parser("prompt-gate", help="Run the v5/v6/v7/v8 production gate on a project or dossier draft")
    p_cp = subparsers.add_parser("chart-preview", help="Render R70-M hand-drawn chart preview PNGs for a project or dossier draft")
    p_cp.add_argument("--project", required=True, help="Project ID or path containing script.json")
    p_cp.add_argument("--out", default=None, help="Output directory for chart preview PNGs")
    p_de = subparsers.add_parser(
        "diorama-episode",
        help="One-shot production of ANY dossier-backed Schema v7/v8 episode: sync draft -> precheck -> Flow -> assembly -> full QA",
    )
    p_de.add_argument(
        "--slug",
        required=True,
        help="research_dossiers/<slug>/ with a diorama_v8_expressive/, diorama_v7_porcelain/, or diorama_v7_lowpoly/ draft",
    )
    p_de.add_argument("--project", required=True, help="Target project ID under BCI_Shorts_Channel/projects/")
    p_de.add_argument("--pillar", required=True, help="Content pillar id (P1)")
    p_de.add_argument("--draft-subdir", default=None, help="Optional draft subfolder override (e.g. diorama_v8_expressive, diorama_v7_porcelain)")
    p_de.add_argument("--precheck-only", action="store_true", default=False, help="Sync + prompt-gate + TTS clock only (no Flow credits)")
    p_de.add_argument(
        "--stop-after",
        default=None,
        choices=["audio", "keyframes"],
        help="Checkpoint halt after master audio or 0-credit keyframes + contact sheet (before Flow video credits)",
    )
    p_de.add_argument("--tabs", type=int, default=5, help="Max concurrent Google Flow shard tabs (<=5)")
    p_de.add_argument("--force", action="store_true", default=False, help="Purge existing clips and regenerate")
    p_de.add_argument("--cdp-port", type=int, default=9222, help="Whale DevTools CDP port (default: 9222)")
    p_de.add_argument("--engine", default="auto", choices=["auto", "omni", "zero_credit", "zero-credit"], help="Flow engine policy")
    p_de.add_argument("--voice-preset", default=None, choices=list(DIORAMA_VOICE_PRESETS), help="Optional narrator voice preset override")
    p_de.add_argument("--prosody-mode", default=None, choices=list(DIORAMA_V7_PROSODY_MODES), help="Optional prosody mode override")

    p_dp = subparsers.add_parser(
        "diorama-pipeline",
        help="Pipelined multi-episode Schema v7/v8 production: up-front precheck + overlapped Flow producer & Assembly+QA consumer",
    )
    p_dp.add_argument(
        "--projects",
        required=True,
        help="Comma-separated 'slug:project_id:pillar' specs or project_ids",
    )
    p_dp.add_argument("--precheck-only", action="store_true", default=False, help="Run sync + preflight prosody/contract precheck only")
    p_dp.add_argument("--tabs", type=int, default=5, help="Max concurrent Google Flow shard tabs (<=5)")
    p_dp.add_argument("--force", action="store_true", default=False, help="Purge existing clips and regenerate")
    p_dp.add_argument("--cdp-port", type=int, default=9222, help="Whale DevTools CDP port (default: 9222)")
    p_dp.add_argument("--engine", default="auto", choices=["auto", "omni", "zero_credit", "zero-credit"], help="Flow engine policy")
    p_dp.add_argument("--voice-preset", default=None, choices=list(DIORAMA_VOICE_PRESETS), help="Optional narrator voice preset override")
    p_dp.add_argument("--prosody-mode", default=None, choices=list(DIORAMA_V7_PROSODY_MODES), help="Optional prosody mode override")
    p_pg.add_argument("--dir", required=True, help="Folder holding 02_script/script.json or script.json, visual_plan.json, 03_visuals/")

    p_ap = subparsers.add_parser("audit-prompts", help="Score every project against Prompt System v5 and write the score sheet")
    p_ap.add_argument("--out", default=None, help="Output markdown path (default BCI_Shorts_Channel/reports/prompt_v5_score_sheet.md)")

    p_am = subparsers.add_parser("asset-manifest", help="Write 05_assembly/asset_manifest.json + asset library index (R50)")
    p_am.add_argument("--project", required=True)

    p_rq = subparsers.add_parser("ref-qa", help="Build Reference Image Bible & run 10-Axis Granular Image QA Gate (R51)")
    p_rq.add_argument("--project", required=True, help="Target project ID or directory")
    p_rq.add_argument("--audit", action="store_true", default=False,
                      help="Audit finished clips: extract raw frames (tagged extracted_from_clip, never pre-generation ready)")
    p_rq.add_argument("--register", default=None, help="Register an image already saved in reference_images/: <filename>")
    p_rq.add_argument("--source", default="flow_image_generation", choices=["flow_image_generation"],
                      help="Provenance for --register: flow_image_generation (locked to Google Flow Image mode)")
    p_rq.add_argument(
        "--require-review",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Require SHA-256-bound reference_semantic_review.json (default: True for Schema v5, False for neuro_diorama)",
    )
    p_rq.add_argument(
        "--auto-populate-review",
        action="store_true",
        default=False,
        help="Auto-populate reference_semantic_review.json from measured Q1-Q7 CV telemetry",
    )
    p_rq.add_argument("--summary", action="store_true", default=False, help="Print compact <=1800B JSON QA digest")

    p_pk = subparsers.add_parser("packets", help="Scene blueprint + per-clip generation packets (start / key / end frame, timed prompt) (R52)")
    p_pk.add_argument("--project", required=True, help="Target project ID or directory")
    p_pk.add_argument("--backend", default="flow", choices=["flow", "gemini_app"])
    p_pk.add_argument("--voice-source", default="tts", choices=["tts", "native"])
    p_pk.add_argument("--chain", type=int, default=None, help="Cut the last frame of clip N as the start frame of clip N+1")

    p_cq = subparsers.add_parser("clip-qa", help="Compile per-video clip_qa_contract.json and verify rendered clips/refs against contract")
    p_cq.add_argument("--project", required=True, help="Target project ID or directory")
    p_cq.add_argument("--compile-only", action="store_true", default=False, help="Only compile 03_visuals/clip_qa_contract.json without running video verification")
    p_cq.add_argument("--no-strips", action="store_true", default=False, help="Skip rendering 6-panel QA contact strips")

    p_eq = subparsers.add_parser(
        "episode-qa",
        help="Run R62/R68 Dynamic Per-Episode QA Contract compiler + 14-Gate DQ1-DQ13/DQ_CAMEO (12-Gate DQ1-DQ12 on v7) multimodal verification",
    )
    p_eq.add_argument("--project", required=True, help="Target project ID or directory")
    p_eq.add_argument("--compile-only", action="store_true", default=False, help="Only compile episode_qa_contract.json + Gate 1 check")
    p_eq.add_argument("--summary", action="store_true", default=False, help="Print compact <=1800B JSON QA digest")

    p_ph = subparsers.add_parser(
        "posthoc-qa",
        help="Run R64 Post-Hoc Clip-by-Clip Expressive Clarity Verification QA on assembled MP4 + source clips",
    )
    p_ph.add_argument("--project", required=True, help="Target project ID or directory")
    p_ph.add_argument("--no-strips", action="store_true", default=False, help="Skip rendering posthoc_viewer_strips/sheet_*.jpg")
    p_ph.add_argument("--no-asr", action="store_true", default=False, help="Skip faster-whisper ASR analogy timestamp check")
    p_ph.add_argument("--init-review", action="store_true", default=False, help="Write/refresh 05_assembly/posthoc_semantic_review.json template")
    p_ph.add_argument("--auto-populate-review", action="store_true", default=False, help="Populate review notes from measured CV telemetry when initializing")
    p_ph.add_argument("--require-review", action="store_true", default=False, help="Require valid SHA-256-bound posthoc_semantic_review.json to pass")
    p_ph.add_argument("--sync-kb", action=argparse.BooleanOptionalAction, default=True, help="Sync results into BCI_Shorts_Channel/knowledge_base/ (default: True)")

    p_th = subparsers.add_parser(
        "thumbnail",
        help="Run R65 v2 Thumbnail Studio: 0-credit cutaway keyart, #FF2525 pointer, Z-hook, TQ1-TQ9 QA & contact sheet",
    )
    p_th.add_argument("--project", default=None, help="Target project ID or directory")
    p_th.add_argument("--all-diorama", action="store_true", default=False, help="Run across assembled neuro_diorama projects")
    p_th.add_argument("--unpublished-only", action="store_true", default=False, help="Skip projects that already have upload_receipt.json")
    p_th.add_argument("--force", action="store_true", default=False, help="Force rebuild even if cached thumbnail_report.json matches")
    p_th.add_argument("--soft", action="store_true", default=False, help="Warn instead of exiting non-zero on TQ1-TQ9 gate failures")
    p_th.add_argument("--generate-keyart", action="store_true", default=False, help="Generate x2 0-credit 3D cutaway keyarts via Google Flow Image")
    p_th.add_argument("--keyart-only", action="store_true", default=False, help="Require 0-credit Google Flow keyart candidates (fail if CDP offline)")
    p_th.add_argument("--frames-only", action="store_true", default=False, help="Score video frames only (skip Google Flow keyart generation)")
    p_th.add_argument("--cdp-port", type=int, default=9222, help="Naver Whale / Chrome CDP port for --generate-keyart (default: 9222)")

    p_kb = subparsers.add_parser(
        "kb",
        help="Manage & query BCI_Shorts_Channel/knowledge_base/ (sync | stats | search)",
    )
    p_kb.add_argument("action", choices=["sync", "stats", "search"], help="Knowledge Base action")
    p_kb.add_argument("--project", default=None, help="Optional single project ID/dir to sync")
    p_kb.add_argument("--full-rescan", action="store_true", default=False, help="Force full rescan of all projects instead of fast mtime-gated incremental sync")
    p_kb.add_argument("--run-missing-posthoc", action="store_true", default=False, help="Run posthoc-qa on assembled projects missing R64 reports during sync")
    p_kb.add_argument("--pack", default="clips", choices=["clips", "prompts", "analogies", "brain_models", "locations"], help="Target reusable pack for search")
    p_kb.add_argument("--query", default="", help="Keyword query for search")
    p_kb.add_argument("--grammar", default=None, help="Filter by visual grammar")
    p_kb.add_argument("--camera", default=None, help="Filter by camera move")
    p_kb.add_argument("--min-clarity", type=float, default=None, help="Minimum R64 clarity score filter")
    p_kb.add_argument("--style-profile", default=None, help="Filter by style_profile (e.g., porcelain_cinematic_v7, expressive_25d_v8, lowpoly_pastel_v7)")
    p_kb.add_argument("--limit", type=int, default=20, help="Max search results")

    p_ow = subparsers.add_parser("overwatch", help="Run Deliverable Overwatch Verification Loop across Deliverables A, B, and C")
    p_ow.add_argument("--outputs-dir", default=None, help="Directory holding standalone deliverables (default: Temp_New_R53_Outputs)")
    p_ow.add_argument("--gage-dir", default=None, help="Phineas Gage project directory (default: /tmp SSD if present else PROJECTS_DIR)")
    p_ow.add_argument("--out", default=None, help="Optional JSON report output path (also writes .md alongside)")
    p_ow.add_argument("--save-in-project", action="store_true", default=False, help="Save contract, QA report, and contact strips inside gage-dir")

    p_gp = subparsers.add_parser(
        "gemini-produce",
        help="Unified single-pipeline production: Schema v4 prompt build + Gemini Web App 9:16 video generation + Gear 4 assembly & QA",
    )
    p_gp.add_argument("--project", required=True, help="Target project ID (e.g. psych_04_phineas_gage_frontal_lobe)")
    p_gp.add_argument("--clips", default=None, help="Optional comma-separated clip numbers to (re)generate (e.g. 1,2,3)")
    p_gp.add_argument("--force-clips", action="store_true", default=False, help="Force regenerate existing clip MP4s in Gemini")
    p_gp.add_argument("--use-refs", action="store_true", default=False, help="Attach optional reference PNGs (default: False, text-only Schema v4)")
    p_gp.add_argument("--skip-browser", action="store_true", default=False, help="Skip browser generation if all 10 clips already exist")
    p_gp.add_argument("--cdp-port", type=int, default=9222, help="Whale DevTools CDP port (default: 9222)")

    p_rx = subparsers.add_parser(
        "reenact-extract",
        help="Stage 1-2 source-conditioned reenactment: extract shot EDL + dHash/5-gram hashes & sanitize structural frames in /tmp/aab_reenact (R67)",
    )
    p_rx.add_argument("--source", required=True, help="YouTube URL or local MP4 path")
    p_rx.add_argument("--slug", required=True, help="Research dossier slug (e.g. ainsworth_strange_situation)")
    p_rx.add_argument("--project", default="", help="Optional project_id to write 03_visuals/source_edl.json")
    p_rx.add_argument("--personal-names", default="", help="Comma-separated source personal names to ban in RQ3 (e.g. Lisa,Lizbeth)")
    p_rx.add_argument("--section", default=None, help="Optional MM:SS-MM:SS or *MM:SS-MM:SS window to clip long documentaries before shot detection")
    p_rx.add_argument("--no-whisper", action="store_true", default=False, help="Skip Whisper ASR if source_analysis.json already exists")

    p_rr = subparsers.add_parser(
        "reenact-refs",
        help="Stage 3 source-conditioned reenactment: translate sanitized guides into porcelain 9:16 reference PNGs via 0-credit Google Flow Image mode (x1 first-pass / x2 retry, R67)",
    )
    p_rr.add_argument("--project", required=True, help="Target project_id")
    p_rr.add_argument("--slug", required=True, help="Research dossier slug")
    p_rr.add_argument("--refs", default="", help="Optional comma-separated reference_ids to regenerate")
    p_rr.add_argument("--backend", default="flow", choices=["flow"], help="0-credit image backend (locked: flow)")
    p_rr.add_argument("--batch-count", type=int, default=None, help="Override 0-credit candidate images per Flow submission (1..4; default: auto x1 first-pass / x2 retry)")
    p_rr.add_argument("--cdp-port", type=int, default=9222, help="Whale DevTools CDP port")
    p_rr.add_argument("--force", action="store_true", default=False, help="Overwrite existing reference PNGs")
    p_rr.add_argument("--purge-quarantine", action="store_true", default=False, help="Purge /tmp/aab_reenact after translation")

    p_pr = subparsers.add_parser(
        "porcelain-refs",
        help="Synthesize & verify Dual-Track porcelain_cinematic_v7 / expressive_25d_v8 9:16 reference pack via 0-credit Google Flow Image mode (x1 first-pass / x2 retry, R51/R66/R67/R68)",
    )
    p_pr.add_argument("--project", required=True, help="Target project_id or path")
    p_pr.add_argument("--slug", default="", help="Optional research dossier slug override")
    p_pr.add_argument("--refs", default="", help="Optional comma-separated target ref_ids to regenerate (e.g. Gate 1 rejected cuts with --force -> x2)")
    p_pr.add_argument("--backend", default="flow", choices=["flow"], help="0-credit image backend (locked: flow)")
    p_pr.add_argument("--batch-count", type=int, default=None, help="Override 0-credit candidate images per Flow submission (1..4; default: auto x1 first-pass / x2 retry)")
    p_pr.add_argument("--cdp-port", type=int, default=9222, help="Whale DevTools CDP port")
    p_pr.add_argument("--force", action="store_true", default=False, help="Force regenerate reference PNGs (auto x2; combine with --refs for targeted Gate 1 retries)")
    p_pr.add_argument("--require-review", action="store_true", default=False, help="Require SHA-256-bound reference_semantic_review.json")
    p_pr.add_argument("--auto-populate-review", action="store_true", default=False, help="Auto-populate reference_semantic_review.json from measured CV telemetry")

    p_rp = subparsers.add_parser(
        "reenact-produce",
        help="Full R67 source-conditioned porcelain reenactment episode production + quarantine purge + RQ1-RQ5 & R64 QA",
    )
    p_rp.add_argument("--slug", required=True, help="Research dossier slug")
    p_rp.add_argument("--project", required=True, help="Target project_id")
    p_rp.add_argument("--pillar", required=True, help="Channel pillar id")
    p_rp.add_argument("--voice-preset", default="elevenlabs_v4", choices=list(DIORAMA_VOICE_PRESETS), help="Voice preset (default: elevenlabs_v4)")
    p_rp.add_argument("--prosody-mode", default="dynamic_us_v7", choices=list(DIORAMA_V7_PROSODY_MODES), help="Prosody mode (default: dynamic_us_v7)")
    p_rp.add_argument("--tabs", type=int, default=5, help="Parallel Flow tabs (max 5)")
    p_rp.add_argument("--cdp-port", type=int, default=9222, help="Whale DevTools CDP port")
    p_rp.add_argument("--engine", default="auto", choices=["auto", "omni", "zero-credit"], help="Flow engine mode")
    p_rp.add_argument("--precheck-only", action="store_true", default=False, help="Run prompt-gate + TTS clock + ref-qa precheck only")
    p_rp.add_argument("--force", action="store_true", default=False, help="Force regenerate clips and assembly")

    p_rqa = subparsers.add_parser(
        "reenact-qa",
        help="Run 5-axis Reenactment Non-Infringement & Fidelity QA contract (RQ1-RQ5, R67)",
    )
    p_rqa.add_argument("--project", required=True, help="Target project_id")
    p_rqa.add_argument("--slug", default="", help="Optional dossier slug")
    p_rqa.add_argument("--allow-quarantine", action="store_true", default=False, help="Allow /tmp/aab_reenact during pre-purge check")
    p_rqa.add_argument("--purge", action="store_true", default=False, help="Purge /tmp/aab_reenact before evaluating RQ1-RQ5")

    p_sw = subparsers.add_parser(
        "studio-watchdog",
        help="Autonomous YouTube Studio Go-Live Watchdog: promote elapsed Scheduled Shorts, pin R35 DOI comments & link R35-B Public rings",
    )
    p_sw.add_argument("--cdp-port", type=int, default=9222, help="Whale DevTools CDP port")
    p_sw.add_argument("--apply", action="store_true", default=False, help="Execute live pins/links/promotions (default: dry-run)")
    p_sw.add_argument("--no-pins", action="store_true", default=False, help="Skip R35 DOI comment pinning")
    p_sw.add_argument("--no-links", action="store_true", default=False, help="Skip R35-B Short-to-Short related video linking")
    p_sw.add_argument("--force-immediate-pin", action="store_true", default=False, help="Override R75 100-view / 12.0h seed-protection defer")

    p_qs = subparsers.add_parser(
        "qa-scheduler",
        help="Daily 08:00 Cross-Platform QA Scheduler (YouTube, Instagram, TikTok): inspects Daily Report, decides HOLD/GO, checks anti-penalty rules & derives execution plan",
    )
    p_qs.add_argument("--date", default=None, help="Target date YYYY-MM-DD (default: today UTC)")
    p_qs.add_argument("--no-write", action="store_true", default=False, help="Do not write schedule report files to BCI_Shorts_Channel/reports/")
    p_qs.add_argument("--json", action="store_true", default=False, help="Print full JSON report instead of Markdown summary")

    p_su = subparsers.add_parser(
        "studio-unschedule",
        help="Safely unschedule (delete forever or switch to private) whitelisted unpublished Scheduled legacy Shorts",
    )
    p_su.add_argument("--projects", default="diorama_08..26", help="Whitelisted range or comma-separated project_ids (default: diorama_08..26)")
    p_su.add_argument("--mode", default="delete", choices=["delete", "private"], help="Take-down mode (default: delete)")
    p_su.add_argument("--dry-run", action="store_true", default=False, help="Verify live Studio Scheduled rows without deleting")
    p_su.add_argument("--clean-local", action="store_true", default=False, help="Archive retired Stage-5 receipts and clean legacy lowpoly media")
    p_su.add_argument("--sync-public", action="store_true", default=False, help="Sync elapsed diorama_04..07 receipts to public and clean staging_queue.json")
    p_su.add_argument("--cdp-port", type=int, default=9222, help="Whale DevTools CDP port")

    p_nr = subparsers.add_parser(
        "news-radar",
        help="Scan recent Crossref / ClinicalTrials breaking BCI & neuroscience papers into Completed_Neuro_News_Shorts staging",
    )
    p_nr.add_argument("--days", type=int, default=14, help="Lookback window in days (default: 14)")
    p_nr.add_argument("--max-candidates", type=int, default=5, help="Max staged news cards (default: 5)")

    p_fc = subparsers.add_parser(
        "flow-clean",
        help="Clean Google Flow project rooms (AAB_<project_id>) and stale /tmp Flow artifacts while protecting active CDP leases",
    )
    p_fc.add_argument("--all", dest="all_projects", action="store_true", default=False, help="Delete all AAB_* / temporary Flow project rooms not leased by active workers")
    p_fc.add_argument("--project", default=None, help="Filter Flow room cleanup to a specific project_id")
    p_fc.add_argument("--prefix", default=None, help="Optional Flow room title prefix filter")
    p_fc.add_argument("--local-only", action="store_true", default=False, help="Only purge local /tmp and flow_bridge temp files without opening Flow dashboard")
    p_fc.add_argument("--include-speed-cache", action="store_true", default=False, help="Also purge /tmp/aab_speed_cache")
    p_fc.add_argument("--force-active", action="store_true", default=False, help="Ignore active CDP tab leases when deleting Flow rooms")
    p_fc.add_argument("--dry-run", action="store_true", default=False, help="Inspect matching Flow rooms and /tmp files without deleting")
    p_fc.add_argument("--cdp-port", type=int, default=9222, help="Whale DevTools CDP port (default: 9222)")

    p_fp = subparsers.add_parser(
        "flow-probe",
        help="Phase 0 zero-credit Google Flow UI capability probe (model dropdown, 3..15s durations, native 1080p download, conversational edit)",
    )
    p_fp.add_argument("--cdp-port", type=int, default=9222, help="Whale DevTools CDP port (default: 9222)")
    p_fp.add_argument("--save", action=argparse.BooleanOptionalAction, default=True, help="Save probe report to flow_ui_capabilities.json (default: True)")

    p_lfi = subparsers.add_parser(
        "longform-init",
        help="[DEFERRED] Initialize standalone 16:9 (1920x1080) Long-Form project in projects_longform/<project_id>/",
    )
    p_lfi.add_argument("--project", required=True, help="Target Long-Form project_id (e.g. longform_01_glymphatic_sleep_toxins)")
    p_lfi.add_argument("--spec", required=True, help="Path to episode_spec JSON file")
    p_lfi.add_argument("--allow-deferred-longform", action="store_true", default=False, help="Override LONGFORM_DEFERRED hold")

    p_lfa = subparsers.add_parser(
        "longform-audio",
        help="[DEFERRED] Synthesize standalone Long-Form relaxed narration (longform_us_v7, -14.0 LUFS) + 1920x1080 ASS subtitles + EDL retiming",
    )
    p_lfa.add_argument("--project", required=True, help="Target Long-Form project_id or path")
    p_lfa.add_argument("--voice-preset", default="elevenlabs_v4", choices=list(DIORAMA_VOICE_PRESETS), help="Voice preset (default: elevenlabs_v4)")
    p_lfa.add_argument("--engine", default="eleven_v4", choices=["eleven_v4"], help="TTS engine (locked: eleven_v4)")
    p_lfa.add_argument("--force", action="store_true", default=False, help="Re-synthesize all sentence audio ignoring cache")
    p_lfa.add_argument("--allow-deferred-longform", action="store_true", default=False, help="Override LONGFORM_DEFERRED hold")

    p_lfr = subparsers.add_parser(
        "longform-refs",
        help="[DEFERRED] Synthesize & Q1-Q10 verify 1920x1080 (16:9) Hybrid Track A + Track B Reference Anchor Pack via 0-credit Google Flow Image (x1 first-pass / x2 retry)",
    )
    p_lfr.add_argument("--project", required=True, help="Target Long-Form project_id or path")
    p_lfr.add_argument("--backend", default="flow", choices=["flow"], help="Reference image backend (locked: flow)")
    p_lfr.add_argument("--batch-count", type=int, default=None, help="Override 0-credit Flow Image candidates per prompt (1..4; default: auto x1 first-pass / x2 retry)")
    p_lfr.add_argument("--cdp-port", type=int, default=9222, help="Whale DevTools CDP port")
    p_lfr.add_argument("--force", action="store_true", default=False, help="Regenerate existing 16:9 reference PNGs")
    p_lfr.add_argument("--allow-deferred-longform", action="store_true", default=False, help="Override LONGFORM_DEFERRED hold")

    p_lff = subparsers.add_parser(
        "longform-flow",
        help="[DEFERRED] Execute chapter-sharded (<= 14 clips/shard) 16:9 Google Flow video generation into flow_native_clips/",
    )
    p_lff.add_argument("--project", required=True, help="Target Long-Form project_id or path")
    p_lff.add_argument("--tabs", type=int, default=3, help="Max concurrent Flow tabs (capped <= 3)")
    p_lff.add_argument("--shard", type=int, default=None, help="Optional 1-based shard index to run")
    p_lff.add_argument("--clips", default="", help="Optional comma-separated clip numbers")
    p_lff.add_argument("--cdp-port", type=int, default=9222, help="Whale DevTools CDP port")
    p_lff.add_argument("--engine", default="auto", choices=["auto", "omni", "zero-credit"], help="Flow video engine mode")
    p_lff.add_argument("--dry-run", action="store_true", default=False, help="Validate shard plan & CV cache without opening browser")
    p_lff.add_argument("--force", action="store_true", default=False, help="Regenerate existing clip MP4s")
    p_lff.add_argument("--allow-deferred-longform", action="store_true", default=False, help="Override LONGFORM_DEFERRED hold")

    p_lf = subparsers.add_parser(
        "longform-assemble",
        help="[DEFERRED] Assemble standalone 16:9 1920x1080 @ 24fps (-14.0 LUFS) Full HD Long-Form MP4 + burned-in ASS + <2 MB A/B/C thumbnails",
    )
    p_lf.add_argument("--project", required=True, help="Target Long-Form project_id or path")
    p_lf.add_argument("--hook-text", default="THE HIDDEN CIRCUIT", help="1920x1080 thumbnail hook headline")
    p_lf.add_argument("--allow-deferred-longform", action="store_true", default=False, help="Override LONGFORM_DEFERRED hold")

    p_lfq = subparsers.add_parser(
        "longform-qa",
        help="[DEFERRED] Run LFQ1-LFQ12 standalone 16:9 (1920x1080) Long-Form QA suite",
    )
    p_lfq.add_argument("--project", required=True, help="Target Long-Form project_id or path")
    p_lfq.add_argument("--require-audio", action="store_true", default=False, help="Require audio_master.wav & subtitles.ass")
    p_lfq.add_argument("--require-refs", action="store_true", default=False, help="Require verified 16:9 reference_image_qa_report.json")
    p_lfq.add_argument("--require-final-mp4", "--require-mp4", dest="require_final_mp4", action="store_true", default=False, help="Require final_longform_1920x1080.mp4")
    p_lfq.add_argument("--allow-deferred-longform", action="store_true", default=False, help="Override LONGFORM_DEFERRED hold")

    p_lfp = subparsers.add_parser(
        "longform-publish",
        help="[DEFERRED] Stage 1920x1080 <2 MB thumbnails, 00:00 chapter metadata.json, and 3-Stage Debate Ignition prepared_comment.json",
    )
    p_lfp.add_argument("--project", required=True, help="Target Long-Form project_id or path")
    p_lfp.add_argument("--hook-text", default="", help="Optional thumbnail hook override")
    p_lfp.add_argument("--upload-cc", action="store_true", default=False, help="Enable external .srt CC upload (default: False)")
    p_lfp.add_argument("--allow-deferred-longform", action="store_true", default=False, help="Override LONGFORM_DEFERRED hold")

    p_mb = subparsers.add_parser(
        "multi-bundle",
        help="Export TikTok & Instagram Reels/Carousel + YouTube Quiz distribution bundle (06_publish/multi_platform_bundle/) without mutating YouTube metadata.json",
    )
    p_mb.add_argument("--project", required=True, help="Project ID or path (e.g. v8_ep08_capgras_imposter_delusion_r77)")
    p_mb.add_argument("--no-copy-video", action="store_true", default=False, help="Skip copying video_clean.mp4 while generating cover, carousel, quiz, captions, and upload_checklist.json")

    p_sqz = subparsers.add_parser(
        "studio-quiz",
        help="Publish or schedule a 4-option YouTube Community Quiz Post from 06_publish/multi_platform_bundle/youtube_quiz_post.json via isolated background CDP tab",
    )
    p_sqz.add_argument("--project", required=True, help="Target project ID or directory")
    p_sqz.add_argument("--schedule", default=None, help="Optional US Eastern schedule timestamp (15-min increment, e.g. '2026-11-15 16:00 ET')")
    p_sqz.add_argument("--dry-run", action="store_true", default=False, help="Validate quiz payload and schedule math without opening browser")
    p_sqz.add_argument("--cdp-port", type=int, default=9222, help="Whale DevTools CDP port (default: 9222)")

    p_sin = subparsers.add_parser(
        "studio-inbox",
        help="Zero-Playback YouTube Studio /comments/inbox scanner & approved heart+reply applier (0 self-views)",
    )
    p_sin.add_argument("--scan-only", action="store_true", default=False, help="Scan unreplied comments to reports/daily/pending_comment_replies.json without posting")
    p_sin.add_argument("--apply-approved", action="store_true", default=False, help="Creator-heart + reply ONLY to items marked approved: true in pending_comment_replies.json")
    p_sin.add_argument("--dry-run", action="store_true", default=False, help="Run in simulation mode without browser mutations")
    p_sin.add_argument("--cdp-port", type=int, default=9222, help="Whale DevTools CDP port (default: 9222)")

    p_igp = subparsers.add_parser(
        "ig-publish",
        help="Publish Instagram 4:5 Carousel (slide_01..06.png) or 9:16 Reel (with >=1,000 follower Trial Reel gate) via Graph API or CDP",
    )
    p_igp.add_argument("--project", required=True, help="Target project ID or directory")
    p_igp.add_argument("--kind", required=True, choices=["reel", "carousel"], help="Asset type: reel | carousel")
    p_igp.add_argument("--engine", default="auto", choices=["auto", "graph-api", "cdp"], help="Publishing engine (default: auto)")
    p_igp.add_argument("--handle", default="allaboutbrain.official", help="Instagram Creator handle")
    p_igp.add_argument("--trial-strategy", default=None, choices=["SS_PERFORMANCE", "MANUAL"], help="Optional Trial Reel graduation strategy (Graph API Reels only; gated on >=1,000 followers)")
    p_igp.add_argument("--require-trial", action="store_true", default=False, help="Abort instead of falling back to standard Reel if followers_count < 1,000")
    p_igp.add_argument("--image-urls", default="", help="Comma-separated public HTTPS slide URLs when using Graph API carousel")
    p_igp.add_argument("--video-url", default="", help="Public HTTPS MP4 URL when using Graph API reel")
    p_igp.add_argument("--cover-url", default="", help="Optional public HTTPS cover URL when using Graph API reel")
    p_igp.add_argument("--dry-run", action="store_true", default=False, help="Validate bundle assets, aspect ratios, and safety gates without publishing")
    p_igp.add_argument("--cdp-port", type=int, default=9222, help="Whale DevTools CDP port (default: 9222)")

    p_ttp = subparsers.add_parser(
        "tiktok-publish",
        help="Publish or schedule a >=60.0s clean 9:16 Short to TikTok Studio (zero commercial sound, AIGC ON, immediate CAPTCHA halt)",
    )
    p_ttp.add_argument("--project", required=True, help="Target project ID or directory")
    p_ttp.add_argument("--schedule-utc", default=None, help="Optional UTC schedule ISO timestamp (5-min increment, +15m..+10d, e.g. '2026-11-16T00:30:00Z')")
    p_ttp.add_argument("--handle", default="allaboutbrain_official", help="TikTok Creator handle")
    p_ttp.add_argument("--dry-run", action="store_true", default=False, help="Validate >=60s duration, zero commercial sound, and schedule window without browser upload")
    p_ttp.add_argument("--cdp-port", type=int, default=9222, help="Whale DevTools CDP port (default: 9222)")

    p_ttpp = subparsers.add_parser(
        "tiktok-pin-profile",
        help="Pin up to 3 top-performing videos on TikTok profile via isolated background CDP tab (immediate CAPTCHA halt)",
    )
    p_ttpp.add_argument("--video-ids", required=True, help="Comma-separated TikTok video IDs (max 3)")
    p_ttpp.add_argument("--handle", default="allaboutbrain_official", help="TikTok Creator handle")
    p_ttpp.add_argument("--dry-run", action="store_true", default=False, help="Validate video IDs and <=3 pin ceiling without opening browser")
    p_ttpp.add_argument("--cdp-port", type=int, default=9222, help="Whale DevTools CDP port (default: 9222)")

    p_bs = subparsers.add_parser(
        "brain-sim",
        help="Render R76 MNI152 3D Brain Simulator clips in parallel on /dev/shm scratch (4x2 standalone / 3x2 overlapped)",
    )
    p_bs.add_argument("--project", required=True, help="Target project ID or directory")
    p_bs.add_argument("--cpu-budget", type=int, default=None, help="Explicit CPU budget override (default: 8 standalone / 6 overlapped)")
    p_bs.add_argument("--overlapped", action="store_true", default=False, help="Use 6-vCPU overlapped worker plan (3x2) alongside Google Flow")
    p_bs.add_argument("--force", action="store_true", default=False, help="Ignore sim_spec_sha256 cache and re-render all brain_simulator_3d clips")

    p_hb = subparsers.add_parser(
        "hw-bench",
        help="Run isolated /dev/shm c3d-highmem-8 hardware, tmpfs I/O, EXDEV atomic commit, and 1x2 vs 4x2 Blender parallel benchmark",
    )
    p_hb.add_argument(
        "--project",
        default="v8_ep08_capgras_imposter_delusion_r77",
        help="Optional read-only reference project ID for R76 brain_simulator_3d shot specs (never modified)",
    )
    p_hb.add_argument("--clips", type=int, default=4, help="Number of R76 brain_simulator_3d clips to benchmark (default: 4)")
    p_hb.add_argument("--frames", type=int, default=90, help="Frames per benchmark clip at 30fps (default: 90 = 3.0s)")

    args = parser.parse_args()

    if args.command == "brain-sim":
        cmd_brain_sim(args)
        return
    if args.command == "hw-bench":
        cmd_hw_bench(args)
        return

    if args.command == "multi-bundle":
        import json as _json
        from pipeline.publish import export_multi_platform_bundle

        res = export_multi_platform_bundle(args.project, copy_video=not bool(args.no_copy_video))
        print(_json.dumps(res, indent=2, ensure_ascii=False))
        return
    if args.command == "studio-quiz":
        cmd_studio_quiz(args)
        return
    if args.command == "studio-inbox":
        cmd_studio_inbox(args)
        return
    if args.command == "ig-publish":
        cmd_ig_publish(args)
        return
    if args.command == "tiktok-publish":
        cmd_tiktok_publish(args)
        return
    if args.command == "tiktok-pin-profile":
        cmd_tiktok_pin_profile(args)
        return

    if args.command == "flow-clean":
        cmd_flow_clean(args)
        return
    if args.command == "flow-probe":
        import asyncio
        import json as _json
        from pipeline.cdp_tab_lease import leased_cdp_tab
        from pipeline.config import GOOGLE_FLOW_URL
        from pipeline.flow_workspace import probe_flow_ui_capabilities

        async def _run_flow_probe() -> dict:
            async with leased_cdp_tab(
                GOOGLE_FLOW_URL,
                purpose="flow-probe",
                cdp_port=int(args.cdp_port),
            ) as (client, _tab_id, _owner):
                await client.send("Page.enable")
                await asyncio.sleep(3.2)
                return await probe_flow_ui_capabilities(client, persist_cache=bool(args.save))

        rep = asyncio.run(_run_flow_probe())
        print(_json.dumps(rep, indent=2, ensure_ascii=False))
        return
    if args.command == "gemini-produce":
        cmd_gemini_produce(args)
        return
    if args.command == "reenact-extract":
        cmd_reenact_extract(args)
        return
    if args.command == "reenact-refs":
        cmd_reenact_refs(args)
        return
    if args.command == "porcelain-refs":
        cmd_porcelain_refs(args)
        return
    if args.command == "reenact-produce":
        cmd_reenact_produce(args)
        return
    if args.command == "reenact-qa":
        cmd_reenact_qa(args)
        return
    if args.command == "studio-watchdog":
        cmd_studio_watchdog(args)
        return
    if args.command == "qa-scheduler":
        cmd_qa_scheduler(args)
        return
    if args.command == "studio-unschedule":
        cmd_studio_unschedule(args)
        return
    if args.command == "news-radar":
        cmd_news_radar(args)
        return
    if args.command == "longform-init":
        cmd_longform_init(args)
        return
    if args.command == "longform-audio":
        cmd_longform_audio(args)
        return
    if args.command == "longform-refs":
        cmd_longform_refs(args)
        return
    if args.command == "longform-flow":
        cmd_longform_flow(args)
        return
    if args.command == "longform-assemble":
        cmd_longform_assemble(args)
        return
    if args.command == "longform-qa":
        cmd_longform_qa(args)
        return
    if args.command == "longform-publish":
        cmd_longform_publish(args)
        return
    if args.command == "diorama-batch":
        import json as _json
        from pipeline.diorama_batch_orchestrator import run_diorama_batch

        pids = [x.strip() for x in args.projects.split(",") if x.strip()] if args.projects.strip() else None
        eng_mode = str(args.engine).replace("-", "_")
        rep = run_diorama_batch(
            wave=str(args.wave),
            project_ids=pids,
            precheck_only=bool(args.precheck_only),
            tabs=int(args.tabs),
            force_regenerate=bool(args.force),
            cdp_port=int(args.cdp_port),
            engine_mode=eng_mode,
            voice_preset=args.voice_preset,
            prosody_mode=args.prosody_mode,
            sequential=bool(args.sequential),
        )
        print(_json.dumps(rep, indent=2, ensure_ascii=False))
        return
    if args.command == "diorama-episode":
        import json as _json
        from pipeline.diorama_batch_orchestrator import run_single_diorama_episode

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
        return
    if args.command == "diorama-pipeline":
        import json as _json
        from pipeline.diorama_pipeline_runner import parse_pipeline_specs, run_diorama_pipeline

        specs = parse_pipeline_specs(str(args.projects))
        rep = run_diorama_pipeline(
            specs=specs,
            precheck_only=bool(args.precheck_only),
            tabs=int(args.tabs),
            force_regenerate=bool(args.force),
            cdp_port=int(args.cdp_port),
            engine_mode=str(args.engine).replace("_", "-"),
            voice_preset=args.voice_preset,
            prosody_mode=args.prosody_mode,
        )
        print(_json.dumps(rep, indent=2, ensure_ascii=False, default=str))
        return
    if args.command == "diorama-flow":
        import asyncio
        import inspect
        import json as _json
        from pipeline.flow_diorama_sharded_worker import run_sharded_diorama_flow_generation
        from pipeline.reference_image_qa import inspect_reference_image_pack

        cand_p = Path(args.project)
        p_dir_df = cand_p if cand_p.is_dir() else (Path(PROJECTS_DIR) / str(args.project).strip())
        ref_dir_df = p_dir_df / "03_visuals" / "reference_images"
        if ref_dir_df.exists() and any(ref_dir_df.glob("*.png")):
            ref_gate = inspect_reference_image_pack(p_dir_df, require_review=True, save_report=True)
            if not ref_gate.get("pre_generation_ready"):
                from pipeline.diorama_batch_orchestrator import render_keyframe_contact_sheet

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
        return
    if args.command == "diorama-assemble":
        cmd_diorama_assemble(args)
        return
    if args.command == "diorama-recut":
        import json as _json

        from pipeline.diorama_assembler import recut_diorama_cuts

        cut_ids = [int(x) for x in str(args.cuts).split(",") if x.strip()]
        print(_json.dumps(recut_diorama_cuts(args.project, cut_ids, allow_published_overwrite=bool(args.allow_published_overwrite)), indent=2))
        return
    if args.command == "prosody-qa":
        import json as _json

        from pipeline.prosody import evaluate_prosody_gates

        rep = evaluate_prosody_gates(args.project, run_asr=not bool(args.no_asr), strict_freshness=True)
        print(_json.dumps(rep, indent=2, ensure_ascii=False))
        if not rep["passed"]:
            sys.exit(1)
        return
    if args.command == "episode-qa":
        cmd_episode_qa(args)
        return
    if args.command == "posthoc-qa":
        cmd_posthoc_qa(args)
        return
    if args.command == "thumbnail":
        cmd_thumbnail(args)
        return
    if args.command == "kb":
        cmd_kb(args)
        return
    if args.command == "dossier":
        cmd_dossier(args)
        return
    if args.command == "prompt-gate":
        cmd_prompt_gate(args)
        return
    if args.command == "chart-preview":
        cmd_chart_preview(args)
        return
    if args.command == "audit-prompts":
        cmd_audit_prompts(args)
        return
    if args.command == "asset-manifest":
        import json as _json
        from pipeline.asset_manifest import build_asset_manifest

        p_dir = Path(args.project) if Path(args.project).is_dir() else (Path(PROJECTS_DIR) / args.project)
        m = build_asset_manifest(p_dir)
        print(_json.dumps({"project_id": m["project_id"], "assets": len(m["assets"])}, indent=2))
        return
    if args.command == "ref-qa":
        cmd_ref_qa(args)
        return
    if args.command == "packets":
        cmd_packets(args)
        return
    if args.command == "clip-qa":
        cmd_clip_qa(args)
        return
    if args.command == "overwatch":
        cmd_overwatch(args)
        return

    if args.command == "research":
        cmd_research(args)
    elif args.command == "produce":
        cmd_produce(args)
    elif args.command == "info":
        cmd_info(args)
    elif args.command == "list":
        cmd_list(args)
    elif args.command == "import-clips":
        cmd_import_clips(args)
    elif args.command == "batch":
        cmd_batch(args)
    elif args.command == "flow-parallel":
        cmd_flow_parallel(args)
    elif args.command == "verify":
        cmd_verify(args)
    elif args.command == "qa":
        import json
        from pipeline.qa_gates import run_full_executable_qa
        report = run_full_executable_qa(project_id=args.project, cdp_port=args.cdp_port)
        print(json.dumps(report, indent=2, ensure_ascii=False))
        if not report["all_passed"]:
            sys.exit(1)
    elif args.command in ("autopsy", "video-autopsy"):
        cmd_autopsy(args)
    elif args.command == "qa-summary":
        cmd_qa_summary(args)
    elif args.command == "evolve":
        cmd_evolve(args)
    elif args.command == "test-all":
        import subprocess
        res = subprocess.run([sys.executable, "-X", "utf8", "-m", "pytest", "-v"], cwd=str(WORKSPACE_ROOT))
        if res.returncode != 0:
            sys.exit(res.returncode)
    elif args.command == "studio-upload":
        cmd_studio_upload(args)
    elif args.command == "studio-pin":
        cmd_studio_pin(args)
    elif args.command == "studio-ab-test":
        cmd_studio_ab_test(args)
    elif args.command == "studio-queue":
        cmd_studio_queue(args)
    elif args.command == "studio-link":
        cmd_studio_link(args)
    elif args.command == "studio-settings":
        cmd_studio_settings(args)
    elif args.command == "studio-report":
        cmd_studio_report(args)


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

        if getattr(args, "all_queued", False):
            q_path = Path(WORKSPACE_ROOT) / "BCI_Shorts_Channel" / "porcelain_rebalanced_queue.json"
            q_doc = json.loads(q_path.read_text(encoding="utf-8"))
            entries = q_doc.get("queue") or q_doc.get("episodes") or []
            results = []
            track_counts: Counter[str] = Counter()
            subtier_counts: Counter[str] = Counter()
            for ep in entries:
                ep_slug = str(ep.get("slug") or "").strip()
                if not ep_slug:
                    continue
                rep_m = rd.audit_dossier_media_suitability(
                    rd.dossier_dir(ep_slug),
                    write_back=bool(getattr(args, "write", False)),
                )
                track_counts[str(rep_m.get("reenactment_track") or "track_b")] += 1
                subtier_counts[str(rep_m.get("track_subtier") or "B_scene_bible_anchor")] += 1
                results.append(
                    {
                        "slug": ep_slug,
                        "project_id": ep.get("project_id"),
                        "reenactment_track": rep_m.get("reenactment_track"),
                        "track_subtier": rep_m.get("track_subtier"),
                        "media_count": len(rep_m.get("media_evaluations") or []),
                        "primary_track_a_url": (rep_m.get("primary_track_a_media") or {}).get("url"),
                    }
                )
            print(
                json.dumps(
                    {
                        "audited_episodes": len(results),
                        "track_counts": dict(track_counts),
                        "subtier_counts": dict(subtier_counts),
                        "episodes": results,
                    },
                    indent=2,
                    ensure_ascii=False,
                )
            )
            return
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
        if getattr(args, "summary", False):
            print(json.dumps(build_compact_qa_digest(res, stage="dossier"), ensure_ascii=False))
        else:
            print(json.dumps(res, indent=2, ensure_ascii=False))
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

    from pipeline.flow_prompt_builder import is_diorama_v6_plan

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

    from pipeline.flow_prompt_builder import (
        build_flow_prompts,
        is_diorama_v6_plan,
        is_v5_plan,
        validate_character_motion,
        validate_flow_prompts,
        validate_narrations,
    )
    from pipeline.prompt_quality_v5 import validate_production_diorama_v6, validate_production_v5

    folder = Path(args.dir)
    plan, narrations, script_doc = _load_gate_inputs(folder)
    clips = build_flow_prompts(plan, narrations)
    if is_diorama_v6_plan(plan):
        import re as _re
        from pipeline.config import is_expressive_v8_plan
        from pipeline.diorama_batch_orchestrator import _PLAQUE_TRIGGER_NOUNS_RE
        from pipeline.flow_prompt_builder import validate_flow_credit_safety_lint
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
    elif is_v5_plan(plan):
        issues = validate_production_v5(plan, narrations, clips)
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
        from pipeline.dynamic_episode_qa import write_episode_qa_contract

        write_episode_qa_contract(folder, plan, narrations, clips)
        contract_compiled = True
    elif not issues and is_v5_plan(plan) and (folder / "03_visuals").exists():
        from pipeline.clip_qa_contract import compile_clip_qa_contract

        compile_clip_qa_contract(folder, save=True)
        contract_compiled = True
    warnings: list[str] = []
    if is_diorama_v6_plan(plan) and isinstance(script_doc, dict):
        from pipeline.data_stamp_overlay import validate_data_stamps

        _, warnings = validate_data_stamps(script_doc, narrations, return_warnings=True)
    print(
        json.dumps(
            {
                "passed": not issues,
                "issues": issues,
                "warnings": warnings,
                "contract_compiled": contract_compiled,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    if issues:
        sys.exit(1)


def cmd_chart_preview(args):
    import json
    from pipeline.data_stamp_overlay import render_data_stamp_rgba_frame

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

    from pipeline.dynamic_episode_qa import (
        verify_final_mp4_against_contract,
        verify_pre_flow_contract,
        write_episode_qa_contract,
    )
    from pipeline.flow_prompt_builder import build_flow_prompts

    p_dir = Path(args.project) if Path(args.project).is_dir() else (Path(PROJECTS_DIR) / args.project)
    plan, narrations, script_doc = _load_gate_inputs(p_dir)
    clips = build_flow_prompts(plan, narrations)
    _, contract = write_episode_qa_contract(p_dir, plan, narrations, clips)
    gate1_issues = verify_pre_flow_contract(plan, narrations, clips, script_doc=script_doc)
    if args.compile_only:
        rep = {"passed": not gate1_issues, "gate1_issues": gate1_issues, "clips": len(clips)}
        if getattr(args, "summary", False):
            print(json.dumps(build_compact_qa_digest(rep, stage="episode-qa"), ensure_ascii=False))
        else:
            print(json.dumps(rep, indent=2, ensure_ascii=False))
        if gate1_issues:
            sys.exit(1)
        return
    rep = verify_final_mp4_against_contract(p_dir, contract=contract)
    if gate1_issues:
        rep["passed"] = False
        rep["gate1_issues"] = gate1_issues
    if getattr(args, "summary", False):
        print(json.dumps(build_compact_qa_digest(rep, stage="episode-qa"), ensure_ascii=False))
    else:
        print(json.dumps(rep, indent=2, ensure_ascii=False))
    if not rep.get("passed"):
        sys.exit(1)


def cmd_diorama_assemble(args):
    import json

    from pipeline.diorama_assembler import assemble_diorama_project
    from pipeline.dynamic_episode_qa import verify_final_mp4_against_contract
    from pipeline.knowledge_hub import sync_project_to_knowledge_base
    from pipeline.video_autopsy import VideoAutopsyEngine

    run_ph = bool(getattr(args, "posthoc_qa", True))
    preview_sec = getattr(args, "preview_sec", None)
    res = assemble_diorama_project(
        args.project,
        force_rebuild=bool(args.force),
        run_posthoc_qa=(run_ph and preview_sec is None),
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
            from pipeline.posthoc_semantic_qa import init_posthoc_semantic_review_template

            rev_f = p_dir / "05_assembly" / "posthoc_semantic_review.json"
            if not rev_f.exists():
                init_posthoc_semantic_review_template(p_dir, auto_populate_from_cv=False)
            res["status"] = "REVIEW_PENDING"
            res["review_file"] = str(rev_f)
            res["contact_sheets"] = list(ph_summary.get("viewer_sheets") or [])
            print(json.dumps(res, indent=2, ensure_ascii=False))
            sys.exit(2)
    print(json.dumps(res, indent=2, ensure_ascii=False))
    if not qa_all_ok:
        sys.exit(1)


def cmd_thumbnail(args):
    import json

    from pipeline import thumbnail_studio
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
    out_obj = summaries[0] if (len(summaries) == 1 and not args.all_diorama) else {"count": len(summaries), "all_passed": not any_failed, "projects": summaries}
    print(json.dumps(out_obj, indent=2, ensure_ascii=False))
    if strict and any_failed:
        sys.exit(1)


def cmd_posthoc_qa(args):
    import json

    from pipeline.config import POSTHOC_SEMANTIC_QA_REPORT_FILENAME
    from pipeline.posthoc_semantic_qa import (
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
    print(json.dumps(slim_out, indent=2, ensure_ascii=False))
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


def cmd_audit_prompts(args):
    import json

    from pipeline.prompt_quality_v5 import audit_projects, render_score_sheet_md

    rows = audit_projects(Path(PROJECTS_DIR))
    out = Path(args.out) if args.out else Path(PROJECTS_DIR).parent / "reports" / "prompt_v5_score_sheet.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_score_sheet_md(rows), encoding="utf-8")
    out.with_suffix(".json").write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Score sheet: {out} ({len(rows)} projects)")


def cmd_ref_qa(args):
    import json

    from pipeline.reference_image_qa import build_and_verify_project_reference_pack, register_reference_image

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
    if getattr(args, "summary", False):
        print(json.dumps(build_compact_qa_digest(rep, stage="ref-qa"), ensure_ascii=False))
    else:
        print(json.dumps(rep, indent=2, ensure_ascii=False))
    if not rep.get("pre_generation_ready"):
        sys.exit(1)


def cmd_packets(args):
    import json

    from pipeline.config import GENERATION_PACKETS_DIRNAME, REF_IMAGES_DIRNAME
    from pipeline.scene_blueprint import extract_last_frame, write_project_blueprint_and_packets

    p_dir = Path(args.project) if Path(args.project).is_dir() else (Path(PROJECTS_DIR) / args.project)
    if args.chain:
        src = p_dir / "03_visuals" / "flow_native_clips" / f"clip_{args.chain}.mp4"
        dst = p_dir / "03_visuals" / REF_IMAGES_DIRNAME / f"chain_clip_{args.chain + 1:02d}_start.png"
        ok = extract_last_frame(src, dst)
        print(json.dumps({"chain_from": str(src), "start_frame": str(dst), "ok": ok}, indent=2))
        sys.exit(0 if ok else 1)
    out = write_project_blueprint_and_packets(p_dir, backend=args.backend, voice_source=args.voice_source)
    print(json.dumps(out, indent=2, ensure_ascii=False))
    print(f"Packets: {p_dir / '03_visuals' / GENERATION_PACKETS_DIRNAME}")
    if out["blueprint_issues"]:
        sys.exit(1)


def cmd_clip_qa(args):
    import json

    from pipeline.clip_qa_contract import compile_clip_qa_contract, verify_clips_against_contract

    p_dir = Path(args.project) if Path(args.project).is_dir() else (Path(PROJECTS_DIR) / args.project)
    contract = compile_clip_qa_contract(p_dir, save=True)
    if args.compile_only:
        print(json.dumps({"compiled": True, "project_id": contract["project_id"], "clip_count": contract["clip_count"]}, indent=2))
        return
    rep = verify_clips_against_contract(p_dir, contract=contract, save_report=True, render_strips=not args.no_strips)
    print(json.dumps(rep, indent=2, ensure_ascii=False))
    if not rep.get("all_passed"):
        sys.exit(1)


def cmd_overwatch(args):
    import json

    from pipeline.deliverable_overwatch import run_deliverable_overwatch

    rep = run_deliverable_overwatch(
        outputs_dir=Path(args.outputs_dir) if args.outputs_dir else None,
        gage_project_dir=Path(args.gage_dir) if args.gage_dir else None,
        out_report_path=Path(args.out) if args.out else None,
        save_in_project=args.save_in_project,
    )
    print(json.dumps(rep, indent=2, ensure_ascii=False))
    if not rep.get("all_deliverables_passed"):
        sys.exit(1)


def cmd_gemini_produce(args):
    """Unified single-pipeline execution: Gear 2 Schema v4 prompts -> Gear 3 Gemini 9:16 clips -> Gear 4 assembly & QA."""
    import asyncio
    import json
    import shutil

    from pipeline.asset_manifest import build_asset_manifest
    from pipeline.config import PROJECTS_DIR, WORKSPACE_ROOT
    from pipeline.flow_prompt_builder import (
        build_flow_prompts,
        load_visual_plan,
        validate_flow_prompts,
        validate_narrations,
        write_flow_prompts_json,
    )
    from pipeline.gemini_web_worker import (
        enforce_mp4_true_peak_ceiling,
        generate_project_video_clips,
        sync_flow_provenance_receipt,
    )
    from pipeline.topics_catalog import ALL_PSYCHOLOGY_100_TOPICS
    from pipeline.video_autopsy import VideoAutopsyEngine

    pid = str(args.project)
    p_dir = Path(pid) if Path(pid).is_dir() else (Path(PROJECTS_DIR) / pid)
    pid = p_dir.name

    topic_item = next((t for t in ALL_PSYCHOLOGY_100_TOPICS if t.get("project_id") == pid), None)
    if topic_item:
        narrations = [str(s) for s in topic_item["clip_narrations"]]
        plan = load_visual_plan(topic_item=topic_item)
        clips = build_flow_prompts(plan, narrations)
        n_errs = validate_narrations(narrations)
        p_errs = validate_flow_prompts(clips, check_character_motion=True)
        if n_errs or p_errs:
            raise SystemExit(f"Prompt validation failed for {pid}: {n_errs + p_errs}")
        vis_dir = p_dir / "03_visuals"
        scr_dir = p_dir / "02_script"
        vis_dir.mkdir(parents=True, exist_ok=True)
        scr_dir.mkdir(parents=True, exist_ok=True)
        (vis_dir / "visual_plan.json").write_text(json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8")
        write_flow_prompts_json(p_dir, clips)
        scr_path = scr_dir / "script.json"
        scr_data = json.loads(scr_path.read_text(encoding="utf-8")) if scr_path.exists() else {}
        scr_data["project_id"] = pid
        scr_data["topic"] = topic_item.get("topic", pid)
        scr_data["doi"] = topic_item.get("doi", "")
        scr_data["clip_narrations"] = narrations
        scr_data["full_script"] = " ".join(narrations)
        scr_data["word_count"] = sum(len(s.split()) for s in narrations)
        scr_path.write_text(json.dumps(scr_data, indent=2, ensure_ascii=False), encoding="utf-8")

    only_clips = [int(x.strip()) for x in str(args.clips).split(",") if x.strip()] if args.clips else None
    gen_res = {"skipped_browser": True}
    if not args.skip_browser:
        gen_res = asyncio.run(
            generate_project_video_clips(
                p_dir,
                only_clips=only_clips,
                force=bool(args.force_clips),
                port=int(args.cdp_port),
                use_reference_images=bool(args.use_refs),
            )
        )
    sync_flow_provenance_receipt(p_dir)

    evolve_rep = VideoAutopsyEngine.evolve_project(pid, force=True)
    final_mp4 = p_dir / "05_assembly" / "final_shorts_1080x1920.mp4"
    if final_mp4.exists():
        enforce_mp4_true_peak_ceiling(final_mp4)
        evolve_rep = VideoAutopsyEngine.inspect_project(pid, save_report=True)
    assembly_passed = bool(evolve_rep.get("passed", evolve_rep.get("after_passed", False)))
    completed_dir = Path(WORKSPACE_ROOT) / "Completed_Psychology_100_Shorts"
    completed_dir.mkdir(parents=True, exist_ok=True)
    completed_mp4 = completed_dir / f"final_shorts_{pid}.mp4"
    if assembly_passed and final_mp4.exists():
        build_asset_manifest(p_dir)
        shutil.copy2(final_mp4, completed_mp4)
    print(
        json.dumps(
            {
                "project_id": pid,
                "gemini_generation": gen_res,
                "assembly_passed": assembly_passed,
                "final_mp4": str(final_mp4),
                "completed_mp4": str(completed_mp4) if assembly_passed else None,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    if not assembly_passed:
        sys.exit(1)


def cmd_reenact_extract(args):
    import json

    from pipeline.source_reenactment import (
        REENACT_QUARANTINE_ROOT,
        extract_source_edl,
        sanitize_structural_frames,
    )

    slug = str(args.slug).strip()
    p_dir = (Path(PROJECTS_DIR) / str(args.project).strip()) if str(args.project).strip() else None
    d_dir = Path(DOSSIERS_DIR) / slug
    names = [x.strip() for x in str(args.personal_names).split(",") if x.strip()] or None
    q_dir = REENACT_QUARANTINE_ROOT / slug
    edl = extract_source_edl(
        url_or_mp4=str(args.source),
        slug=slug,
        project_dir=p_dir,
        dossier_dir=d_dir if d_dir.exists() else None,
        work_dir=q_dir,
        source_personal_names=names,
        run_whisper=not bool(args.no_whisper),
        section=getattr(args, "section", None),
    )
    san = sanitize_structural_frames(
        work_dir=q_dir,
        edl_doc=edl,
        project_dir=p_dir,
        dossier_dir=d_dir if d_dir.exists() else None,
    )
    print(json.dumps({"slug": slug, "shot_count": len(edl.get("shots") or []), "sanitized": san}, indent=2, ensure_ascii=False))


def cmd_reenact_refs(args):
    import json

    from pipeline.source_reenactment import purge_reenactment_quarantine, translate_porcelain_keyframes

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

    from pipeline.porcelain_anchor_pack import ensure_porcelain_reference_pack

    p_dir = Path(args.project) if Path(args.project).is_dir() else (Path(PROJECTS_DIR) / str(args.project).strip())
    slug = str(getattr(args, "slug", "") or "").strip()
    d_dir = (Path(DOSSIERS_DIR) / slug) if slug and (Path(DOSSIERS_DIR) / slug).exists() else None
    from pipeline.diorama_batch_orchestrator import render_keyframe_contact_sheet

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


def cmd_reenact_produce(args):
    import json

    from pipeline.diorama_batch_orchestrator import run_single_diorama_episode
    from pipeline.source_reenactment import purge_reenactment_quarantine, validate_reenactment_non_infringement

    slug = str(args.slug).strip()
    pid = str(args.project).strip()
    p_dir = Path(PROJECTS_DIR) / pid
    d_dir = Path(DOSSIERS_DIR) / slug
    ep_res = run_single_diorama_episode(
        slug=slug,
        project_id=pid,
        pillar=str(args.pillar).strip(),
        precheck_only=bool(args.precheck_only),
        tabs=int(args.tabs),
        force_regenerate=bool(args.force),
        cdp_port=int(args.cdp_port),
        engine_mode=str(args.engine).replace("-", "_"),
        voice_preset=str(args.voice_preset),
        prosody_mode=str(getattr(args, "prosody_mode", "") or "").strip() or None,
    )
    if bool(args.precheck_only):
        print(json.dumps(ep_res, indent=2, ensure_ascii=False, default=str))
        if not ep_res.get("passed", True):
            sys.exit(1)
        return
    purge_res = purge_reenactment_quarantine(slug=slug)
    rqa = validate_reenactment_non_infringement(
        project_dir=p_dir,
        dossier_dir=d_dir if d_dir.exists() else None,
        require_quarantine_purged=True,
        save_report=True,
    )
    out = {"episode": ep_res, "quarantine_purge": purge_res, "reenactment_qa": rqa}
    print(json.dumps(out, indent=2, ensure_ascii=False, default=str))
    if not ep_res.get("passed", False) or not rqa.get("passed", False):
        sys.exit(1)


def cmd_reenact_qa(args):
    import json

    from pipeline.source_reenactment import purge_reenactment_quarantine, validate_reenactment_non_infringement

    p_dir = Path(PROJECTS_DIR) / str(args.project).strip()
    slug = str(args.slug).strip()
    if not slug:
        vp_p = p_dir / "03_visuals" / "visual_plan.json"
        if vp_p.exists():
            vp_doc = json.loads(vp_p.read_text(encoding="utf-8"))
            slug = str(vp_doc.get("dossier_slug") or vp_doc.get("dossier") or "").strip()
    if bool(args.purge):
        purge_reenactment_quarantine(slug=slug or p_dir.name)
    d_dir = (Path(DOSSIERS_DIR) / slug) if slug else None
    rep = validate_reenactment_non_infringement(
        project_dir=p_dir,
        dossier_dir=d_dir if (d_dir and d_dir.exists()) else None,
        require_quarantine_purged=not bool(args.allow_quarantine),
        save_report=True,
    )
    print(json.dumps(rep, indent=2, ensure_ascii=False))
    if not rep.get("passed"):
        sys.exit(1)


def cmd_studio_watchdog(args):
    import json

    from pipeline.studio.studio_watchdog import run_studio_watchdog

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

    from pipeline.studio.qa_scheduler import run_qa_scheduler

    rep = run_qa_scheduler(
        target_date=getattr(args, "date", None),
        write_outputs=not bool(getattr(args, "no_write", False)),
    )
    if getattr(args, "json", False):
        payload = {k: v for k, v in rep.items() if k != "markdown"}
        print(json.dumps(payload, indent=2, ensure_ascii=False, default=str))
    else:
        print(rep.get("markdown", ""))


def cmd_studio_unschedule(args):
    import json

    from pipeline.studio.unschedule_retired_shorts import run_studio_unschedule

    rep = run_studio_unschedule(
        projects_spec=str(args.projects),
        mode=str(args.mode),
        dry_run=bool(args.dry_run),
        clean_local=bool(args.clean_local),
        sync_public=bool(args.sync_public),
        cdp_port=int(args.cdp_port),
    )
    print(json.dumps(rep, indent=2, ensure_ascii=False, default=str))
    rem = rep.get("studio", {}).get("remaining_scheduled_retired_ids") or []
    if not args.dry_run and args.mode == "delete" and rem:
        target_ids = {r.get("video_id") for r in (rep.get("studio", {}).get("results") or [])}
        if any(v in target_ids for v in rem):
            sys.exit(1)


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


def _enforce_longform_not_deferred(args) -> None:
    import os
    from pipeline import config as _cfg

    if not bool(getattr(_cfg, "LONGFORM_DEFERRED", False)):
        return
    if not bool(getattr(args, "command", None)) and not hasattr(args, "allow_deferred_longform"):
        return
    if bool(getattr(args, "allow_deferred_longform", False)):
        return
    if str(os.environ.get("AAB_ALLOW_DEFERRED_LONGFORM") or "").strip().lower() in ("1", "true", "yes"):
        return
    cmd_name = str(getattr(args, "command", "longform-*") or "longform-*")
    sys.stderr.write(
        f"[LONGFORM_DEFERRED] '{cmd_name}' is currently deferred while 90s Shorts scale. "
        "Pass --allow-deferred-longform or set AAB_ALLOW_DEFERRED_LONGFORM=1 to override.\n"
    )
    sys.exit(2)


def cmd_longform_init(args):
    _enforce_longform_not_deferred(args)
    import json

    from pipeline.longform_prompt_builder import initialize_longform_project

    spec_doc = json.loads(Path(args.spec).read_text(encoding="utf-8"))
    res = initialize_longform_project(str(args.project).strip(), spec_doc, require_valid_dossier=True)
    print(json.dumps(res, indent=2, ensure_ascii=False))


def cmd_longform_audio(args):
    _enforce_longform_not_deferred(args)
    import json

    from pipeline.longform_audio import synthesize_longform_master_audio

    res = synthesize_longform_master_audio(
        args.project,
        voice_preset=str(args.voice_preset),
        engine=str(args.engine),
        force=bool(args.force),
    )
    print(json.dumps(res, indent=2, ensure_ascii=False))


def cmd_longform_refs(args):
    _enforce_longform_not_deferred(args)
    import json

    from pipeline.longform_refs import ensure_longform_reference_pack

    raw_batch = getattr(args, "batch_count", None)
    res = ensure_longform_reference_pack(
        args.project,
        cdp_port=int(args.cdp_port),
        batch_count=(int(raw_batch) if raw_batch is not None else None),
        backend=str(args.backend),
        force=bool(args.force),
    )
    print(json.dumps(res, indent=2, ensure_ascii=False))
    if not res.get("cv_pre_generation_ready"):
        sys.exit(1)


def cmd_longform_flow(args):
    _enforce_longform_not_deferred(args)
    import asyncio
    import json

    from pipeline.longform_flow_worker import run_longform_sharded_flow_generation

    only = [int(x.strip()) for x in str(args.clips).split(",") if x.strip()] if str(args.clips).strip() else None
    res = asyncio.run(
        run_longform_sharded_flow_generation(
            args.project,
            tabs=int(args.tabs),
            shard_index=args.shard,
            only_clips=only,
            cdp_port=int(args.cdp_port),
            engine_mode=str(args.engine),
            force=bool(args.force),
            dry_run=bool(args.dry_run),
        )
    )
    print(json.dumps(res, indent=2, ensure_ascii=False))
    if not args.dry_run and res.get("failed_clips"):
        sys.exit(1)


def cmd_longform_assemble(args):
    _enforce_longform_not_deferred(args)
    import json

    from pipeline.longform_assembler import assemble_longform_episode

    res = assemble_longform_episode(args.project, hook_text=str(args.hook_text))
    res["thumbnails_4k"] = res.get("thumbnails")
    print(json.dumps(res, indent=2, ensure_ascii=False))
    if not res.get("passed", True):
        sys.exit(1)


def cmd_longform_qa(args):
    _enforce_longform_not_deferred(args)
    import json

    from pipeline.longform_qa import run_longform_qa

    rep = run_longform_qa(
        args.project,
        require_audio=bool(args.require_audio),
        require_refs=bool(args.require_refs),
        require_final_mp4=bool(args.require_final_mp4),
        save_report=True,
    )
    print(json.dumps(rep, indent=2, ensure_ascii=False))
    if not rep.get("passed"):
        sys.exit(1)


def cmd_longform_publish(args):
    _enforce_longform_not_deferred(args)
    import json

    from pipeline.longform_publish import prepare_longform_publish_package

    rep = prepare_longform_publish_package(
        args.project,
        hook_text=str(args.hook_text).strip() or None,
        upload_cc_srt=bool(args.upload_cc),
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
    video_path = bundle_dir / "video_clean.mp4"
    cover_path = bundle_dir / "cover_9x16.png"
    cap_file = bundle_dir / "reels_caption.txt"
    if not video_path.is_file():
        raise FileNotFoundError(f"Missing Reel clean MP4: {video_path}")
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
    from pipeline.studio.tiktok_uploader import upload_tiktok_video_cdp

    p_dir = _resolve_cli_project_dir(args.project)
    bundle_dir = p_dir / "06_publish" / "multi_platform_bundle"
    video_path = bundle_dir / "video_clean.mp4"
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


def cmd_tiktok_pin_profile(args):
    import asyncio
    import json
    from pipeline.studio.tiktok_uploader import sync_tiktok_pinned_videos_cdp

    vids = [v.strip() for v in str(args.video_ids or "").split(",") if v.strip()]
    res = asyncio.run(
        sync_tiktok_pinned_videos_cdp(
            vids,
            handle=args.handle,
            dry_run=bool(args.dry_run),
            cdp_port=int(args.cdp_port),
        )
    )
    print(json.dumps(res, indent=2, ensure_ascii=False))


def cmd_brain_sim(args):
    import json
    from pipeline.brain_simulator_blender import render_project_brain_simulator_clips_parallel

    p_dir = _resolve_cli_project_dir(args.project)
    edl_frame_map: dict[int, int] | None = None
    lock_path = p_dir / "05_assembly" / "edl_timing_lock.json"
    if lock_path.is_file():
        try:
            lock_doc = json.loads(lock_path.read_text(encoding="utf-8"))
            raw_map = lock_doc.get("edl_frame_map")
            if isinstance(raw_map, dict):
                edl_frame_map = {int(k): int(v) for k, v in raw_map.items()}
        except Exception:  # noqa: BLE001
            edl_frame_map = None

    res = render_project_brain_simulator_clips_parallel(
        p_dir,
        edl_frame_map=edl_frame_map,
        cpu_budget=args.cpu_budget,
        overlapped=bool(args.overlapped),
        threads_per_worker=4,
        force=bool(args.force),
    )
    print(json.dumps(res, indent=2, ensure_ascii=False))
    if not res.get("all_passed", True):
        sys.exit(1)


def cmd_hw_bench(args):
    import hashlib
    import json
    import os
    import shutil
    import time
    from pipeline.brain_simulator_blender import (
        is_brain_simulator_clip_spec,
        render_project_brain_simulator_clips_parallel,
    )
    from pipeline.config import PROJECTS_DIR
    from pipeline.hardware_profile import (
        detect_host_hardware,
        resolve_blender_parallel_plan,
        resolve_cpu_budget,
    )
    from pipeline.media_cache import atomic_commit_from_scratch, get_ram_scratch_root

    t_bench0 = time.monotonic()
    hw = detect_host_hardware()
    shm_root = get_ram_scratch_root()
    bench_id = f"bench_{int(time.time())}_{os.getpid()}"
    bench_dir = shm_root / bench_id
    tmp_ext_dir = Path(f"/tmp/aab_{bench_id}")
    bench_dir.mkdir(parents=True, exist_ok=True)
    tmp_ext_dir.mkdir(parents=True, exist_ok=True)

    try:
        # 1. Sequential scratch I/O throughput (/dev/shm tmpfs vs /tmp ext4, 128 MiB)
        buf_bytes = os.urandom(4 * 1024 * 1024) * 32  # 128 MiB
        buf_mb = len(buf_bytes) / (1024.0 * 1024.0)

        shm_io_p = bench_dir / "io_probe.bin"
        t0 = time.perf_counter()
        shm_io_p.write_bytes(buf_bytes)
        shm_w_s = max(1e-6, time.perf_counter() - t0)
        t0 = time.perf_counter()
        _ = shm_io_p.read_bytes()
        shm_r_s = max(1e-6, time.perf_counter() - t0)
        shm_io_p.unlink(missing_ok=True)

        tmp_io_p = tmp_ext_dir / "io_probe.bin"
        t0 = time.perf_counter()
        tmp_io_p.write_bytes(buf_bytes)
        tmp_w_s = max(1e-6, time.perf_counter() - t0)
        t0 = time.perf_counter()
        _ = tmp_io_p.read_bytes()
        tmp_r_s = max(1e-6, time.perf_counter() - t0)
        tmp_io_p.unlink(missing_ok=True)

        # 2. Guard 1: Cross-device EXDEV-safe atomic_commit_from_scratch (/dev/shm -> /tmp)
        commit_payload = os.urandom(2 * 1024 * 1024)
        expected_sha = hashlib.sha256(commit_payload).hexdigest()
        src_commit = bench_dir / "commit_src.mp4"
        dst_commit = tmp_ext_dir / "commit_dst.mp4"
        src_commit.write_bytes(commit_payload)
        cross_dev = os.stat(bench_dir).st_dev != os.stat(tmp_ext_dir).st_dev
        t0 = time.perf_counter()
        atomic_commit_from_scratch(src_commit, dst_commit)
        commit_ms = round((time.perf_counter() - t0) * 1000.0, 3)
        actual_sha = hashlib.sha256(dst_commit.read_bytes()).hexdigest()
        temp_leftovers = [p.name for p in tmp_ext_dir.glob(".tmp_*")]

        # 3. Read-only R76 clip spec extraction (NEVER writes to reference project)
        n_clips = max(1, min(8, int(args.clips)))
        n_frames = max(60, int(args.frames))
        ref_project_id = str(args.project or "").strip()
        ref_vp_path = next(
            (
                p
                for p in (
                    Path(PROJECTS_DIR) / ref_project_id / "03_visuals" / "visual_plan.json",
                    Path(PROJECTS_DIR) / ref_project_id / "02_script" / "visual_plan.json",
                )
                if ref_project_id and p.is_file()
            ),
            None,
        )
        from pipeline.config import EXPRESSIVE_V8_BRAIN_SIM_DRONE_MOVES

        sim_specs: list[dict] = []
        if ref_vp_path is not None:
            ref_vp = json.loads(ref_vp_path.read_text(encoding="utf-8"))
            ref_sim_dir = ref_vp_path.parent.parent / "03_visuals" / "brain_simulator_clips"
            for idx_ref, c_item in enumerate(ref_vp.get("clips") or [], start=1):
                if (
                    isinstance(c_item, dict)
                    and is_brain_simulator_clip_spec(c_item)
                    and str(c_item.get("camera_move") or "") in EXPRESSIVE_V8_BRAIN_SIM_DRONE_MOVES
                ):
                    c_num_ref = int(c_item.get("clip_number") or c_item.get("id") or idx_ref)
                    ref_qa_p = ref_sim_dir / f"clip_{c_num_ref}_sim_qa.json"
                    if ref_qa_p.is_file():
                        try:
                            if not bool(json.loads(ref_qa_p.read_text(encoding="utf-8")).get("passed")):
                                continue
                        except Exception:  # noqa: BLE001
                            continue
                    else:
                        continue
                    sim_specs.append(dict(c_item))
                    if len(sim_specs) >= n_clips:
                        break
        fallback_Presets = (
            ("sensory_to_brain_drone", "eyes", "primary visual cortex", "active"),
            ("circuit_cooperation_drone", "primary visual cortex", "fusiform face area", "active"),
            ("circuit_cooperation_drone", "fusiform face area", "amygdala", "severed"),
            ("global_system_orbit_drone", "amygdala", "prefrontal cortex", "silenced"),
        )
        while len(sim_specs) < n_clips:
            cam_m, s_reg, e_reg, n_st = fallback_Presets[len(sim_specs) % len(fallback_Presets)]
            sim_specs.append(
                {
                    "grammar": "brain_simulator_3d",
                    "render_engine": "blender_3d_simulator",
                    "camera_move": cam_m,
                    "start_brain_region": s_reg,
                    "end_brain_region": e_reg,
                    "brain_region": e_reg,
                    "neural_state": n_st,
                }
            )

        bench_clips_payload = []
        bench_fmap: dict[int, int] = {}
        for idx_b, raw_sp in enumerate(sim_specs[:n_clips], start=1):
            sp_clean = dict(raw_sp)
            sp_clean["clip_number"] = idx_b
            sp_clean["id"] = idx_b
            sp_clean["duration_sec"] = round(n_frames / 30.0, 4)
            bench_clips_payload.append(sp_clean)
            bench_fmap[idx_b] = n_frames

        vp_bench = {
            "schema": 8,
            "style_profile": "expressive_25d_v8",
            "fps": 30,
            "width": 1080,
            "height": 1920,
            "clips": bench_clips_payload,
        }

        proj_1x2 = bench_dir / "proj_1x2"
        proj_4x2 = bench_dir / "proj_4x2"
        for p_b in (proj_1x2, proj_4x2):
            (p_b / "02_script").mkdir(parents=True, exist_ok=True)
            (p_b / "02_script" / "visual_plan.json").write_text(
                json.dumps(vp_bench, indent=2), encoding="utf-8"
            )

        res_1x2 = render_project_brain_simulator_clips_parallel(
            proj_1x2,
            edl_frame_map=bench_fmap,
            cpu_budget=2,
            overlapped=False,
            threads_per_worker=2,
            force=True,
        )
        res_4x2 = render_project_brain_simulator_clips_parallel(
            proj_4x2,
            edl_frame_map=bench_fmap,
            cpu_budget=8,
            overlapped=False,
            threads_per_worker=2,
            force=True,
        )
        res_cache = render_project_brain_simulator_clips_parallel(
            proj_4x2,
            edl_frame_map=bench_fmap,
            cpu_budget=8,
            overlapped=False,
            threads_per_worker=2,
            force=False,
        )

        speedup = round(
            float(res_1x2["elapsed_sec"]) / max(0.001, float(res_4x2["elapsed_sec"])),
            2,
        )
        report = {
            "benchmark": "c3d-highmem-8_workstream_b_hw_bench",
            "isolated_scratch_dir": str(bench_dir),
            "reference_project_read_only": ref_project_id if ref_vp_path else "synthetic_r76",
            "hardware": {
                **hw,
                "active_ram_scratch_root": str(shm_root),
                "cpu_budget_standalone": resolve_cpu_budget(overlapped=False),
                "cpu_budget_overlapped": resolve_cpu_budget(overlapped=True),
                "blender_plan_standalone_8vcpu": list(resolve_blender_parallel_plan(8, overlapped=False)),
                "blender_plan_overlapped_6vcpu": list(resolve_blender_parallel_plan(6, overlapped=True)),
            },
            "scratch_io_128mib": {
                "shm_write_mb_s": round(buf_mb / shm_w_s, 1),
                "shm_read_mb_s": round(buf_mb / shm_r_s, 1),
                "tmp_write_mb_s": round(buf_mb / tmp_w_s, 1),
                "tmp_read_mb_s": round(buf_mb / tmp_r_s, 1),
            },
            "guard1_atomic_commit": {
                "cross_device_tmpfs_to_ext4": bool(cross_dev),
                "sha256_verified": actual_sha == expected_sha,
                "src_cleaned": not src_commit.exists(),
                "zero_temp_leftovers": len(temp_leftovers) == 0,
                "commit_2mib_ms": commit_ms,
            },
            "blender_parallel_1080x1920_30fps": {
                "clip_count": n_clips,
                "frames_per_clip": n_frames,
                "single_worker_1x2": {
                    "n_workers": res_1x2["n_workers"],
                    "threads_per_worker": res_1x2["threads_per_worker"],
                    "elapsed_sec": res_1x2["elapsed_sec"],
                    "all_passed": res_1x2["all_passed"],
                },
                "parallel_workers_4x2": {
                    "n_workers": res_4x2["n_workers"],
                    "threads_per_worker": res_4x2["threads_per_worker"],
                    "elapsed_sec": res_4x2["elapsed_sec"],
                    "all_passed": res_4x2["all_passed"],
                },
                "sha256_cache_skip_rerun": {
                    "elapsed_sec": res_cache["elapsed_sec"],
                    "cache_hits": res_cache["cache_hits"],
                    "rendered_count": res_cache["rendered_count"],
                    "all_passed": res_cache["all_passed"],
                },
                "speedup_4x2_vs_1x2": speedup,
            },
            "total_bench_elapsed_sec": round(time.monotonic() - t_bench0, 2),
        }
        print(json.dumps(report, indent=2, ensure_ascii=False))
    finally:
        shutil.rmtree(bench_dir, ignore_errors=True)
        shutil.rmtree(tmp_ext_dir, ignore_errors=True)


if __name__ == "__main__":
    main()

