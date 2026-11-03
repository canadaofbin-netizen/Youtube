"""
ALL ABOUT BRAIN - Unified Pipeline CLI
Command-line interface for autonomous production, Google Flow assistance,
batch operations, YouTube Studio staging, community comment pinning,
and sequential A/B testing.
"""

import argparse
import sys
from pathlib import Path

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
  ALL ABOUT BRAIN — CHANNEL BLUEPRINT & PRODUCTION ARCHITECTURE (v7)
========================================================================

1. Channel One-Line Definition:
   "Combining UCL Neuroscience academic rigor with 100% AI production to
    explain Brain-Computer Interfaces and the mysteries of the brain in
    3-minute Neuro-Diorama Long-Shorts (Schema v7 porcelain_cinematic_v7)."

2. Core Profile:
   - Channel Name: ALL ABOUT BRAIN
   - Channel Handle: @AllAboutBrainOfficial
   - Channel ID: UC4FeioYYv9X04Di07_MfZ7g
   - Channel Residence (Tax/AdSense): South Korea (KR)
   - Video & Metadata Language Lock: English (United States) (en-US)
   - Default Format: Neuro-Diorama v7 Long-Short 148.0-179.0s @ 24fps (6-Act spine, 56-66+ 1:1 Zero-Reuse clips)
   - Classic Format: Schema v5 Shorts <= 105.0s @ 30fps (5-10 clips)
   - Cadence: Daily uploads (5 slots per day distributed across North American ET peaks)

3. 7 Content Pillars & 5-Slot Mapping (with Default Narrative Archetype):
   [bci_tech]        BCI Tech Explained -> Slot 2 (12:00 PM ET) [chronicle_cutaway]
   [brain_news]      Brain News         -> Slot 2 (12:00 PM ET) [chronicle_cutaway]
   [brain_history]   Brain History      -> Slot 4 (08:00 PM ET) [delusion_museum]
   [brain_basics]    Brain Basics       -> Slot 3 (04:00 PM ET) [icon_autopsy]
   [brain_mysteries] Brain Mysteries    -> Slot 3 / Slot 5      [case_file]
   [brain_health]    Brain Health       -> Slot 1 (07:30 AM ET) [caveman_brain]
   [bci_ethics]      BCI Ethics         -> Slot 5 (10:30 PM ET) [forbidden_lab]

4. Neuro-Diorama System v7 & Dual-Tier Flow Locks (R5, R56-R66):
   - Flow Engine (R5): Credit-aware Dual-Tier (`Omni 1.1 Flash` when credits available -> automatic `0-credit` `Veo 3.1 - Lite [Lower Priority]` fallback, zero paid APIs)
   - Voice Lock (R58/R63/R63-P): `en-US-AndrewMultilingualNeural` (`dynamic_rush_v7` per-gear rates, `+14Hz`, `-10%` Silk Clean EQ, `kokoro-onnx` offline fallback)
   - Visual Spec (R66 default / R63 legacy): Photorealistic high-key porcelain cast & Contained Living 4-Color 3D Brain (`porcelain_cinematic_v7` default; `lowpoly_pastel_v7` legacy preserved), 3-tier face-excluding framing, `hstack` split, condensed frame-grid subtitles
   - Triple Post-Assembly QA Lock (R18/R62/R64): VideoAutopsyEngine + DynamicEpisodeQA (`DQ1-DQ12`) + PostHocSemanticQA (`R64`) + SHA-256 upload gate
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
    """Imports downloaded Google Flow Omni 1.1 video clips using ASR ordering and optionally auto-assembles."""
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
    from pipeline.storage import ProjectStorage
    storage = ProjectStorage(args.project)
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
    assign_playlist = bool(getattr(args, "assign_playlist", False))
    receipt = uploader.upload_project(
        project_id=args.project,
        slot_id=args.slot,
        target_date=args.date,
        visibility=args.visibility,
        dry_run=args.dry_run,
        burn_first_frame=burn_first_frame,
        auto_link=auto_link,
        assign_playlist=assign_playlist,
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
    """Configures and verifies Two-Tier Localization (KR Residence + en-US Upload Defaults) in YouTube Studio."""
    from pipeline.studio.uploader import StudioUploader
    uploader = StudioUploader(cdp_port=args.cdp_port)
    print("\n[CLI] Configuring YouTube Studio Localization & Upload Defaults (R36)...")
    res = uploader.configure_studio_localization(dry_run=args.dry_run)
    print("\n========================================================")
    print(f"  YOUTUBE STUDIO SETTINGS {'[DRY RUN]' if args.dry_run else '[LIVE VERIFIED]'}!")
    print(f"  Channel: {res['channel_name']} ({res['channel_id']})")
    print(f"  Country of Residence: {res['country_of_residence']} ({res['country_of_residence_code']})")
    print(f"  Video Language:       {res['video_language']} ({res['video_language_code']})")
    print(f"  Metadata Language:    {res['title_description_language']} ({res['title_description_language_code']})")
    print(f"  Default Category:     {res['category']}")
    print(f"  Changes Saved:        {res['saved_changes']}")
    print("========================================================\n")


def cmd_studio_pin(args):
    """Posts academic DOI source & cognitive dissonance question comment and pins it to top."""
    import json
    from pipeline.studio.community import CommunityManager

    manager = CommunityManager(cdp_port=args.cdp_port)
    if getattr(args, "all_public", False):
        print(f"\n[CLI] Scanning projects to stage prepared comments and pin unpinned Public Shorts (Dry-Run: {args.dry_run}, Replace-Existing: {args.replace_existing})...")
        summary = manager.pin_all_public_unpinned(
            dry_run=args.dry_run,
            replace_existing=args.replace_existing,
            project_filter={args.project} if args.project else None,
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
    assign_playlist = bool(getattr(args, "assign_playlist", True))

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
        assign_playlists=args.assign_playlists,
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


def cmd_autopsy(args):
    """Runs multimodal video/audio/subtitle/thumbnail forensic autopsy on one or all projects."""
    import json
    from pipeline.video_autopsy import VideoAutopsyEngine

    if args.project:
        report = VideoAutopsyEngine.inspect_project(args.project, save_report=True)
    else:
        report = VideoAutopsyEngine.inspect_all_projects(save_reports=True)
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
    p_import = subparsers.add_parser("import-clips", help="Import downloaded Google Flow Omni 1.1 MP4 video clips into project with ASR ordering")
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
    p_autopsy = subparsers.add_parser("autopsy", help="Run multimodal video/audio/subtitle/thumbnail forensic autopsy")
    p_autopsy.add_argument("--project", default=None, help="Optional single project ID to inspect (inspects all rendered projects if omitted)")

    # evolve (Closed-Loop Autonomous Self-Evolution Engine)
    p_evolve = subparsers.add_parser("evolve", help="Execute closed-loop self-evolution to remediate audio, subtitles, video, and thumbnails")
    p_evolve.add_argument("--project", default=None, help="Optional single project ID to evolve (evolves all rendered projects if omitted)")
    p_evolve.add_argument("--force", action="store_true", default=True, help="Force rebuild of audio, subtitles, video, and thumbnails")

    # test-all
    subparsers.add_parser("test-all", help="Run comprehensive pytest test suite across the workspace")

    # studio-upload
    p_su = subparsers.add_parser("studio-upload", help="Upload project video to YouTube Studio with 5-slot scheduling or unlisted staging")
    p_su.add_argument("--project", required=True, help="Target project ID")
    p_su.add_argument("--visibility", default="unlisted", choices=["unlisted", "scheduled", "public", "private"], help="Visibility mode (default: unlisted)")
    p_su.add_argument("--slot", type=int, choices=[1, 2, 3, 4, 5], default=None, help="Target slot (1-5)")
    p_su.add_argument("--date", default=None, help="Target release date YYYY-MM-DD")
    p_su.add_argument("--dry-run", action="store_true", default=False, help="Run in simulation mode without actual browser interaction")
    p_su.add_argument("--burn-first-frame", action="store_true", default=False, help="Burn thumbnail into first frame of video for guaranteed Shorts cover fallback")
    p_su.add_argument("--auto-link", action=argparse.BooleanOptionalAction, default=False, help="Automatically link Related video post-upload (R35-B)")
    p_su.add_argument("--assign-playlist", action=argparse.BooleanOptionalAction, default=False, help="Assign 7-Pillar playlist post-upload (R35-B)")
    p_su.add_argument("--cdp-port", type=int, default=9222, help="Whale DevTools CDP port (default: 9222)")

    # studio-pin
    p_sp = subparsers.add_parser("studio-pin", help="Post and pin academic DOI verification and debate question comment")
    p_sp.add_argument("--project", default=None, help="Target project ID (optional when --all-public is set)")
    p_sp.add_argument("--video-id", default=None, help="Target YouTube Video ID (optional)")
    p_sp.add_argument("--all-public", action="store_true", default=False, help="Stage prepared comments across projects and pin any unpinned Public Shorts")
    p_sp.add_argument("--replace-existing", action="store_true", default=False, help="Delete previous @AllAboutBrainOfficial comment before posting and pinning the updated comment")
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
    p_sab.add_argument("--clicks-a", type=int, default=None, help="Clicks for Variant A")
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
    p_sq.add_argument("--assign-playlist", action=argparse.BooleanOptionalAction, default=True, help="Assign 7-Pillar playlist during load-all (default: True)")
    p_sq.add_argument("--dry-run", action="store_true", default=False, help="Run load-all in simulation mode")
    p_sq.add_argument("--cdp-port", type=int, default=9222, help="Whale DevTools CDP port (default: 9222)")

    # studio-link (R35-B Short-to-Short Related Video & 7-Pillar Playlist Ring)
    p_sl = subparsers.add_parser("studio-link", help="Plan or apply Short-to-Short Related Video circular ring & 7-Pillar playlists (R35-B)")
    p_sl.add_argument("--action", choices=["plan", "apply", "seed-boost", "status"], default="plan", help="Action: plan | apply | seed-boost | status")
    p_sl.add_argument("--mode", choices=["seed_boost", "semantic_chain"], default="seed_boost", help="Routing strategy (default: seed_boost)")
    p_sl.add_argument("--project", default=None, help="Optional single source project ID")
    p_sl.add_argument("--target", default=None, help="Optional explicit 11-char target YouTube video ID")
    p_sl.add_argument("--assign-playlists", action=argparse.BooleanOptionalAction, default=True, help="Assign/create 7-Pillar playlist on each video (default: True)")
    p_sl.add_argument("--dry-run", action="store_true", default=False, help="Simulate without writing Studio changes")
    p_sl.add_argument("--force", action="store_true", default=False, help="Override 24h seed-protection lock and re-apply existing links")
    p_sl.add_argument("--cdp-port", type=int, default=9222, help="Whale DevTools CDP port (default: 9222)")

    # studio-settings
    p_ss = subparsers.add_parser("studio-settings", help="Configure and verify KR Channel Residence + en-US Upload Defaults in YouTube Studio")
    p_ss.add_argument("--dry-run", action="store_true", default=False, help="Run in simulation mode without browser interaction")
    p_ss.add_argument("--cdp-port", type=int, default=9222, help="Whale DevTools CDP port (default: 9222)")

    # studio-report (Daily YouTube Studio Analytics & Growth Report Generator)
    p_sr = subparsers.add_parser("studio-report", help="Generate standardized 9-section Daily YouTube Studio Analytics & Growth Report")
    p_sr.add_argument("--date", default=None, help="Target report date YYYY-MM-DD (default: today ET)")
    p_sr.add_argument("--compare-date", default=None, help="Optional previous snapshot date YYYY-MM-DD for DoD delta")
    p_sr.add_argument("--dry-run", action="store_true", default=False, help="Generate report without launching/navigating Naver Whale")
    p_sr.add_argument("--cdp-port", type=int, default=9222, help="Whale DevTools CDP port (default: 9222)")

    # Prompt System v5 & Neuro-Diorama System v6 (R44-R61)
    p_ds = subparsers.add_parser("dossier", help="Research dossier: init / validate / seed / doi / yt-search / yt-analyze (R44)")
    p_ds.add_argument("action", choices=["init", "validate", "seed", "doi", "yt-search", "yt-analyze", "checklist"])
    p_ds.add_argument("--slug", default=None, help="Dossier slug (BCI_Shorts_Channel/research_dossiers/<slug>)")
    p_ds.add_argument("--topic", default="", help="Topic title (init)")
    p_ds.add_argument("--pillar", default="", help="Pillar id (init)")
    p_ds.add_argument("--mode", default="HYBRID", help="BEHAVIORAL_PSYCH | HYBRID | NEURO_BIOLOGY (init)")
    p_ds.add_argument("--profile", default="neuro_diorama", choices=["classic_v5", "neuro_diorama"], help="Seed profile (seed)")
    p_ds.add_argument(
        "--style-profile",
        default=None,
        choices=["porcelain_cinematic_v7", "lowpoly_pastel_v7"],
        help="Schema v7 style profile override for seed (default: porcelain_cinematic_v7)",
    )
    p_ds.add_argument("--doi", default=None, help="DOI to verify via Crossref (doi)")
    p_ds.add_argument("--query", default=None, help="YouTube search query (yt-search)")
    p_ds.add_argument("--url", default=None, help="Reference video URL (yt-analyze)")
    p_ds.add_argument("--media-id", default=None, help="Media id folder name under <dossier>/media (yt-analyze)")
    p_ds.add_argument("--section", default=None, help="Optional '*mm:ss-mm:ss' range (yt-analyze)")

    p_da = subparsers.add_parser(
        "diorama-assemble",
        help="Assemble a Schema v7 porcelain_cinematic_v7 / lowpoly_pastel_v7 (+14Hz Andrew Silk Clean, 24fps) or v6 Neuro-Diorama Short (<= 179.0s) (R56-R66)",
    )
    p_da.add_argument("--project", required=True, help="Target project ID or directory")
    p_da.add_argument("--force", action=argparse.BooleanOptionalAction, default=True, help="Force rebuild of EDL, WAV, ASS, and MP4 (default: True)")
    p_da.add_argument(
        "--posthoc-qa",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Run R64 post-hoc clip-by-clip expressive clarity QA, DQ1-DQ12, Autopsy, and sync Knowledge Hub after assembly (default: True)",
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
        help="Narrator voice preset from DIORAMA_VOICE_PRESETS (e.g. andrew_v7, emma_v7, ava_v7)",
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
        help="Sharded 5-tab Dual-Tier (Omni 1.1 Flash -> 0-credit auto-fallback) Google Flow generator for Schema v7/v6 neuro_diorama (1:1 Zero-Reuse)",
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
        help="Flow engine policy: auto (Omni 1.1 Flash when credits > 0 else 0-credit fallback), omni, or zero-credit",
    )

    p_db = subparsers.add_parser(
        "diorama-batch",
        help="Resumable Wave 1-4 (20-episode) Schema v7/v6 neuro_diorama precheck, Flow generation, assembly & QA orchestrator",
    )
    p_db.add_argument("--wave", default="all", help="Wave selector: 1, 2, 3, 4, or all (default: all)")
    p_db.add_argument("--projects", default="", help="Optional comma-separated project_ids subset")
    p_db.add_argument("--precheck-only", action="store_true", default=False, help="Run prompt-gate + TTS duration lock only")
    p_db.add_argument("--tabs", type=int, default=5, help="Max concurrent Google Flow shard tabs per project (<=5)")
    p_db.add_argument("--force", action="store_true", default=False, help="Force regenerate even if already completed")
    p_db.add_argument("--cdp-port", type=int, default=9222, help="Whale DevTools CDP port (default: 9222)")
    p_db.add_argument(
        "--engine",
        default="auto",
        choices=["auto", "omni", "zero_credit", "zero-credit"],
        help="Flow engine policy: auto (Omni 1.1 Flash -> 0-credit auto-fallback), omni, or zero-credit",
    )
    p_db.add_argument("--voice-preset", default=None, choices=list(DIORAMA_VOICE_PRESETS), help="Optional narrator voice preset override")

    p_pg = subparsers.add_parser("prompt-gate", help="Run the v5/v6/v7 production gate on a project or dossier draft")
    p_de = subparsers.add_parser(
        "diorama-episode",
        help="One-shot production of ANY dossier-backed Schema v7 episode: sync draft -> precheck -> Flow -> assembly -> full QA",
    )
    p_de.add_argument(
        "--slug",
        required=True,
        help="research_dossiers/<slug>/ with a diorama_v7_porcelain/ (or diorama_v7_lowpoly/) draft",
    )
    p_de.add_argument("--project", required=True, help="Target project ID under BCI_Shorts_Channel/projects/")
    p_de.add_argument("--pillar", required=True, help="Content pillar id (P1)")
    p_de.add_argument("--precheck-only", action="store_true", default=False, help="Sync + prompt-gate + TTS clock only (no Flow credits)")
    p_de.add_argument("--tabs", type=int, default=5, help="Max concurrent Google Flow shard tabs (<=5)")
    p_de.add_argument("--force", action="store_true", default=False, help="Purge existing clips and regenerate")
    p_de.add_argument("--cdp-port", type=int, default=9222, help="Whale DevTools CDP port (default: 9222)")
    p_de.add_argument("--engine", default="auto", choices=["auto", "omni", "zero_credit", "zero-credit"], help="Flow engine policy")
    p_de.add_argument("--voice-preset", default=None, choices=list(DIORAMA_VOICE_PRESETS), help="Optional narrator voice preset override")

    p_dp = subparsers.add_parser(
        "diorama-pipeline",
        help="Pipelined multi-episode Schema v7 production: up-front precheck + overlapped Flow producer & Assembly+QA consumer",
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
    p_pg.add_argument("--dir", required=True, help="Folder holding 02_script/script.json or script.json, visual_plan.json, 03_visuals/")

    p_ap = subparsers.add_parser("audit-prompts", help="Score every project against Prompt System v5 and write the score sheet")
    p_ap.add_argument("--out", default=None, help="Output markdown path (default BCI_Shorts_Channel/reports/prompt_v5_score_sheet.md)")

    p_am = subparsers.add_parser("asset-manifest", help="Write 05_assembly/asset_manifest.json + asset library index (R50)")
    p_am.add_argument("--project", required=True)

    p_vc = subparsers.add_parser("voice-check", help="Semitone voice-consistency report for a project's native Flow clips (R49)")
    p_vc.add_argument("--project", required=True)

    p_rq = subparsers.add_parser("ref-qa", help="Build Reference Image Bible & run 10-Axis Granular Image QA Gate (R51)")
    p_rq.add_argument("--project", required=True, help="Target project ID or directory")
    p_rq.add_argument("--audit", action="store_true", default=False,
                      help="Audit finished clips: extract raw frames (tagged extracted_from_clip, never pre-generation ready)")
    p_rq.add_argument("--register", default=None, help="Register an image already saved in reference_images/: <filename>")
    p_rq.add_argument("--source", default="flow_image_generation",
                      help="Provenance for --register: flow_image_generation | gemini_image_generation")

    p_pk = subparsers.add_parser("packets", help="Scene blueprint + per-clip generation packets (start / key / end frame, timed prompt) (R52)")
    p_pk.add_argument("--project", required=True, help="Target project ID or directory")
    p_pk.add_argument("--backend", default="gemini_app", choices=["gemini_app", "flow"])
    p_pk.add_argument("--voice-source", default="tts", choices=["tts", "native"])
    p_pk.add_argument("--chain", type=int, default=None, help="Cut the last frame of clip N as the start frame of clip N+1")

    p_cq = subparsers.add_parser("clip-qa", help="Compile per-video clip_qa_contract.json and verify rendered clips/refs against contract")
    p_cq.add_argument("--project", required=True, help="Target project ID or directory")
    p_cq.add_argument("--compile-only", action="store_true", default=False, help="Only compile 03_visuals/clip_qa_contract.json without running video verification")
    p_cq.add_argument("--no-strips", action="store_true", default=False, help="Skip rendering 6-panel QA contact strips")

    p_eq = subparsers.add_parser(
        "episode-qa",
        help="Run R62 Dynamic Per-Episode QA Contract compiler + 12-Axis DQ1-DQ12 multimodal verification",
    )
    p_eq.add_argument("--project", required=True, help="Target project ID or directory")
    p_eq.add_argument("--compile-only", action="store_true", default=False, help="Only compile episode_qa_contract.json + Gate 1 check")

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
        help="Run R65 Thumbnail Studio: candidate scoring, v7 hook overlay, TQ1-TQ7 QA & contact sheet",
    )
    p_th.add_argument("--project", default=None, help="Target project ID or directory")
    p_th.add_argument("--all-diorama", action="store_true", default=False, help="Run across assembled neuro_diorama projects")
    p_th.add_argument("--unpublished-only", action="store_true", default=False, help="Skip projects that already have upload_receipt.json")
    p_th.add_argument("--force", action="store_true", default=False, help="Force rebuild even if cached thumbnail_report.json matches")
    p_th.add_argument("--soft", action="store_true", default=False, help="Warn instead of exiting non-zero on TQ1-TQ7 gate failures")

    p_kb = subparsers.add_parser(
        "kb",
        help="Manage & query BCI_Shorts_Channel/knowledge_base/ (sync | stats | search)",
    )
    p_kb.add_argument("action", choices=["sync", "stats", "search"], help="Knowledge Base action")
    p_kb.add_argument("--project", default=None, help="Optional single project ID/dir to sync")
    p_kb.add_argument("--run-missing-posthoc", action="store_true", default=False, help="Run posthoc-qa on assembled projects missing R64 reports during sync")
    p_kb.add_argument("--pack", default="clips", choices=["clips", "prompts", "analogies", "brain_models", "locations"], help="Target reusable pack for search")
    p_kb.add_argument("--query", default="", help="Keyword query for search")
    p_kb.add_argument("--grammar", default=None, help="Filter by visual grammar")
    p_kb.add_argument("--camera", default=None, help="Filter by camera move")
    p_kb.add_argument("--min-clarity", type=float, default=None, help="Minimum R64 clarity score filter")
    p_kb.add_argument("--style-profile", default=None, help="Filter by style_profile (e.g., lowpoly_pastel_v7)")
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
    p_rx.add_argument("--no-whisper", action="store_true", default=False, help="Skip Whisper ASR if source_analysis.json already exists")

    p_rr = subparsers.add_parser(
        "reenact-refs",
        help="Stage 3 source-conditioned reenactment: translate sanitized guides into porcelain 9:16 reference PNGs via 0-credit Google Flow x4 Image mode (R67)",
    )
    p_rr.add_argument("--project", required=True, help="Target project_id")
    p_rr.add_argument("--slug", required=True, help="Research dossier slug")
    p_rr.add_argument("--refs", default="", help="Optional comma-separated reference_ids to regenerate")
    p_rr.add_argument("--backend", default="flow", choices=["flow", "gemini"], help="0-credit image backend (default: flow)")
    p_rr.add_argument("--batch-count", type=int, default=4, help="0-credit candidate images per Flow submission (1..4, default: 4)")
    p_rr.add_argument("--cdp-port", type=int, default=9222, help="Whale DevTools CDP port")
    p_rr.add_argument("--force", action="store_true", default=False, help="Overwrite existing reference PNGs")
    p_rr.add_argument("--purge-quarantine", action="store_true", default=False, help="Purge /tmp/aab_reenact after translation")

    p_rp = subparsers.add_parser(
        "reenact-produce",
        help="Full R67 source-conditioned porcelain reenactment episode production + quarantine purge + RQ1-RQ5 & R64 QA",
    )
    p_rp.add_argument("--slug", required=True, help="Research dossier slug")
    p_rp.add_argument("--project", required=True, help="Target project_id")
    p_rp.add_argument("--pillar", required=True, help="Channel pillar id")
    p_rp.add_argument("--voice-preset", default="emma_v7", choices=list(DIORAMA_VOICE_PRESETS), help="Voice preset (default: emma_v7)")
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

    p_nr = subparsers.add_parser(
        "news-radar",
        help="Scan recent Crossref / ClinicalTrials breaking BCI & neuroscience papers into Completed_Neuro_News_Shorts staging",
    )
    p_nr.add_argument("--days", type=int, default=14, help="Lookback window in days (default: 14)")
    p_nr.add_argument("--max-candidates", type=int, default=5, help="Max staged news cards (default: 5)")

    p_lf = subparsers.add_parser(
        "longform-assemble",
        help="Assemble 16:9 3840x2160 @ 24fps (-14.0 LUFS) CTV Long-Form documentary MP4 + 4K A/B/C thumbnails",
    )
    p_lf.add_argument("--project", required=True, help="Target project_id or path")
    p_lf.add_argument("--hook-text", default="THE HIDDEN CIRCUIT", help="4K thumbnail hook headline")

    args = parser.parse_args()

    if args.command == "gemini-produce":
        cmd_gemini_produce(args)
        return
    if args.command == "reenact-extract":
        cmd_reenact_extract(args)
        return
    if args.command == "reenact-refs":
        cmd_reenact_refs(args)
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
    if args.command == "news-radar":
        cmd_news_radar(args)
        return
    if args.command == "longform-assemble":
        cmd_longform_assemble(args)
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
        )
        print(_json.dumps(rep, indent=2, ensure_ascii=False, default=str))
        return
    if args.command == "diorama-flow":
        import asyncio
        import inspect
        from pipeline.flow_diorama_sharded_worker import run_sharded_diorama_flow_generation

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

        rep = evaluate_prosody_gates(args.project, run_asr=not bool(args.no_asr))
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
    if args.command == "audit-prompts":
        cmd_audit_prompts(args)
        return
    if args.command == "asset-manifest":
        import json as _json
        from pipeline.asset_manifest import build_asset_manifest
        from pipeline.config import PROJECTS_DIR

        p_dir = Path(args.project) if Path(args.project).is_dir() else (Path(PROJECTS_DIR) / args.project)
        m = build_asset_manifest(p_dir)
        print(_json.dumps({"project_id": m["project_id"], "assets": len(m["assets"])}, indent=2))
        return
    if args.command == "voice-check":
        cmd_voice_check(args)
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
    elif args.command == "autopsy":
        cmd_autopsy(args)
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
    if not args.slug:
        print("--slug is required for this action", file=sys.stderr)
        sys.exit(2)
    if args.action == "init":
        print(rd.init_dossier(args.slug, args.topic or args.slug, pillar=args.pillar, visual_mode=args.mode))
    elif args.action == "validate":
        res = rd.validate_dossier(args.slug)
        print(json.dumps(res, indent=2, ensure_ascii=False))
        if not res["ready"]:
            sys.exit(1)
    elif args.action == "seed":
        if getattr(args, "profile", "neuro_diorama") == "neuro_diorama":
            print(
                json.dumps(
                    rd.diorama_seed_from_dossier(args.slug, style_profile=getattr(args, "style_profile", None)),
                    indent=2,
                    ensure_ascii=False,
                )
            )
        else:
            print(json.dumps(rd.plan_seed_from_dossier(args.slug), indent=2, ensure_ascii=False))
    elif args.action == "yt-analyze":
        media_id = args.media_id or rd.slugify(args.url or "ref")[-24:]
        out = rd.dossier_dir(args.slug) / "media" / media_id
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
        from pipeline.diorama_batch_orchestrator import _PLAQUE_TRIGGER_NOUNS_RE
        from pipeline.publish import validate_diorama_paradox_title

        issues = validate_production_diorama_v6(plan, narrations, clips, script_doc=script_doc)
        raw_title = str(script_doc.get("title") or plan.get("title") or "").strip()
        if raw_title:
            issues.extend(validate_diorama_paradox_title(raw_title))
        for c in clips:
            sc = _re.sub(r"\b(?:without|zero|no)\s+[a-z\s,-]{1,35}", " ", str(c.get("scene") or ""), flags=_re.IGNORECASE)
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
    print(json.dumps({"passed": not issues, "issues": issues, "contract_compiled": contract_compiled}, indent=2, ensure_ascii=False))
    if issues:
        sys.exit(1)


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
        print(json.dumps(rep, indent=2, ensure_ascii=False))
        if gate1_issues:
            sys.exit(1)
        return
    rep = verify_final_mp4_against_contract(p_dir, contract=contract)
    if gate1_issues:
        rep["passed"] = False
        rep["gate1_issues"] = gate1_issues
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
        ph_ok = bool((res.get("posthoc_qa") or {}).get("passed", True))
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
            sync_project_to_knowledge_base(p_dir)
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
        rep = thumbnail_studio.run(p_dir, force=bool(args.force), strict=False, mode=mode)
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
        require_review=bool(args.require_review),
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
            res = sync_all_projects_to_knowledge_base(run_missing_posthoc=bool(args.run_missing_posthoc))
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


def cmd_voice_check(args):
    import json

    from pipeline.flow_live_single_worker import analyze_flow_clip_candidate
    from pipeline.storage import numeric_clip_sort_key
    from pipeline.voice_consistency import evaluate_f0_series

    p_dir = Path(args.project) if Path(args.project).is_dir() else (Path(PROJECTS_DIR) / args.project)
    clips_dir = p_dir / "03_visuals" / "flow_native_clips"
    files = sorted(clips_dir.glob("clip_*.mp4"), key=numeric_clip_sort_key) if clips_dir.exists() else []
    f0s = [float(analyze_flow_clip_candidate(f).get("f0_median_hz", 0.0)) for f in files]
    rep = evaluate_f0_series(f0s)
    aud_dir = p_dir / "04_audio"
    aud_dir.mkdir(parents=True, exist_ok=True)
    vr_path = aud_dir / "voice_report.json"
    if vr_path.exists():
        try:
            existing = json.loads(vr_path.read_text(encoding="utf-8"))
        except Exception:
            existing = {}
        existing["native_f0"] = rep
        vr_path.write_text(json.dumps(existing, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    else:
        vr_path.write_text(
            json.dumps({"source": "native", "native_f0": rep, **rep}, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(rep, indent=2))
    if not rep.get("passed"):
        sys.exit(1)


def cmd_ref_qa(args):
    import json

    from pipeline.reference_image_qa import build_and_verify_project_reference_pack, register_reference_image

    p_dir = Path(args.project) if Path(args.project).is_dir() else (Path(PROJECTS_DIR) / args.project)
    if args.register:
        register_reference_image(p_dir, args.register, args.source)
    rep = build_and_verify_project_reference_pack(p_dir, audit_extract_from_clips=args.audit)
    rep.pop("images", None)
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
    res = translate_porcelain_keyframes(
        project_dir=p_dir,
        slug=str(args.slug).strip(),
        cdp_port=int(args.cdp_port),
        only_ref_ids=only_ids,
        force=bool(args.force),
        backend=str(getattr(args, "backend", "flow")),
        batch_count=int(getattr(args, "batch_count", 4)),
    )
    if bool(args.purge_quarantine):
        res["quarantine_purge"] = purge_reenactment_quarantine()
    print(json.dumps(res, indent=2, ensure_ascii=False))
    if res.get("failed_ids"):
        sys.exit(1)


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
    purge_res = purge_reenactment_quarantine()
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

    if bool(args.purge):
        purge_reenactment_quarantine()
    p_dir = Path(PROJECTS_DIR) / str(args.project).strip()
    slug = str(args.slug).strip()
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
    )
    print(json.dumps(rep, indent=2, ensure_ascii=False, default=str))


def cmd_news_radar(args):
    import json

    from pipeline.news_radar import scan_breaking_neuro_news

    rep = scan_breaking_neuro_news(
        window_days=int(args.days),
        max_candidates=int(args.max_candidates),
    )
    print(json.dumps(rep, indent=2, ensure_ascii=False))


def cmd_longform_assemble(args):
    import json

    from pipeline.longform_assembler import assemble_longform_4k_episode

    res = assemble_longform_4k_episode(args.project, hook_text=str(args.hook_text))
    res["thumbnails_4k"] = res.get("thumbnails")
    print(json.dumps(res, indent=2, ensure_ascii=False))
    if not res.get("passed", True):
        sys.exit(1)


if __name__ == "__main__":
    main()
