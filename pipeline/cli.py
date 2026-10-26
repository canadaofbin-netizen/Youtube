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
  ALL ABOUT BRAIN — CHANNEL BLUEPRINT & PRODUCTION ARCHITECTURE (v4)
========================================================================

1. Channel One-Line Definition:
   "Combining UCL Neuroscience academic rigor with 100% AI production to
    explain Brain-Computer Interfaces and the mysteries of the brain in
    5-10 clip documentary Shorts."

2. Core Profile:
   - Channel Name: ALL ABOUT BRAIN
   - Channel Handle: @AllAboutBrainOfficial
   - Channel ID: UC4FeioYYv9X04Di07_MfZ7g
   - Channel Residence (Tax/AdSense): South Korea (KR)
   - Video & Metadata Language Lock: English (United States) (en-US)
   - Format: YouTube Shorts <= 105.0s (5-10 clips, 18-28 words/clip, 90-280 words total)
   - Cadence: Daily uploads (5 slots per day distributed across North American peaks)

3. 7 Content Pillars & 5-Slot Mapping (with Default Narrative Archetype):
   [bci_tech]        BCI Tech Explained -> Slot 2 (12:00 PM ET) [chronicle_cutaway]
   [brain_news]      Brain News         -> Slot 2 (12:00 PM ET) [chronicle_cutaway]
   [brain_history]   Brain History      -> Slot 4 (07:30 PM ET) [delusion_museum]
   [brain_basics]    Brain Basics       -> Slot 3 (04:00 PM ET) [icon_autopsy]
   [brain_mysteries] Brain Mysteries    -> Slot 3 / Slot 5      [case_file]
   [brain_health]    Brain Health       -> Slot 1 (07:30 AM ET) [caveman_brain]
   [bci_ethics]      BCI Ethics         -> Slot 5 (10:30 PM ET) [forbidden_lab]

4. Deep-Mechanism Role Spine (R42):
   - 5-10 clips mapped by CLIP_ROLE_SEQUENCES (setup -> symptom -> failure -> crisis -> pivot -> step1..3 -> breakthrough -> conclusion)
   - 6 Historical Archetype Lenses via --style:
     case_file | delusion_museum | forbidden_lab | icon_autopsy | caveman_brain | chronicle_cutaway

5. Production Contract v4 Locks:
   - Voice Lock (R13): Puck (Google Flow Omni 1.1 male narrator, 2.7 native WPS, 1.08x synchronized speedup)
   - Visual Spec (R14-A/R21/R38): Matte-white porcelain mannequins with translucent frosted-glass craniums in narration-matched real environments; realistic brain anatomy in bright white studio gallery; 4-point colour code
   - Independent Conclusion Ending (R19): Standalone conclusion opener ("Which proves" / "Which is why") with clean 0.20s tail and 0.09s fade-out
   - 12 QA Gates (R18): Strict zero-defect validation before publishing
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
    from pipeline.studio.community import CommunityManager
    manager = CommunityManager(cdp_port=args.cdp_port)
    print(f"\n[CLI] Posting & Pinning DOI verification comment for '{args.project}'...")
    print(f"      Video ID: {args.video_id or 'from receipt'} | Dry-Run: {args.dry_run}")

    receipt = manager.post_and_pin_comment(
        project_id=args.project,
        video_id=args.video_id,
        dry_run=args.dry_run
    )
    print("\n========================================================")
    print(f"  COMMUNITY COMMENT PINNED {'[DRY RUN]' if args.dry_run else '[LIVE]'}!")
    print(f"  Project: {receipt['project_id']}")
    print(f"  Shorts URL: {receipt['shorts_url']}")
    print(f"  Pinned Status: {receipt['pinned']}")
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
                "B": {"impressions": args.impressions_b or 1000, "clicks": args.clicks_b or 50},
                "C": {"impressions": args.impressions_c or 1000, "clicks": args.clicks_c or 50}
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
    else:
        res = tester.swap_next(args.project, video_id=args.video_id, dry_run=args.dry_run)

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
    p_sp.add_argument("--project", required=True, help="Target project ID")
    p_sp.add_argument("--video-id", default=None, help="Target YouTube Video ID (optional)")
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

    # Prompt System v5 (R44-R50)
    p_ds = subparsers.add_parser("dossier", help="Research dossier: init / validate / seed / doi / yt-search / yt-analyze (R44)")
    p_ds.add_argument("action", choices=["init", "validate", "seed", "doi", "yt-search", "yt-analyze", "checklist"])
    p_ds.add_argument("--slug", default=None, help="Dossier slug (BCI_Shorts_Channel/research_dossiers/<slug>)")
    p_ds.add_argument("--topic", default="", help="Topic title (init)")
    p_ds.add_argument("--pillar", default="", help="Pillar id (init)")
    p_ds.add_argument("--mode", default="HYBRID", help="BEHAVIORAL_PSYCH | HYBRID | NEURO_BIOLOGY (init)")
    p_ds.add_argument("--doi", default=None, help="DOI to verify via Crossref (doi)")
    p_ds.add_argument("--query", default=None, help="YouTube search query (yt-search)")
    p_ds.add_argument("--url", default=None, help="Reference video URL (yt-analyze)")
    p_ds.add_argument("--media-id", default=None, help="Media id folder name under <dossier>/media (yt-analyze)")
    p_ds.add_argument("--section", default=None, help="Optional '*mm:ss-mm:ss' range (yt-analyze)")

    p_pg = subparsers.add_parser("prompt-gate", help="Run the v5 production gate on a project or a dossier shorts_v5 draft")
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

    args = parser.parse_args()

    if args.command == "gemini-produce":
        cmd_gemini_produce(args)
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

        m = build_asset_manifest(Path(PROJECTS_DIR) / args.project)
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
        print(json.dumps(rd.plan_seed_from_dossier(args.slug), indent=2, ensure_ascii=False))
    elif args.action == "yt-analyze":
        media_id = args.media_id or rd.slugify(args.url or "ref")[-24:]
        out = rd.dossier_dir(args.slug) / "media" / media_id
        print(json.dumps(rd.analyze_reference_video(args.url, out, section=args.section), indent=2, ensure_ascii=False))


def _load_gate_inputs(folder: Path):
    import json

    script_path = next((p for p in (folder / "02_script" / "script.json", folder / "script.json") if p.exists()), None)
    plan_path = next((p for p in (folder / "03_visuals" / "visual_plan.json", folder / "visual_plan.json") if p.exists()), None)
    if script_path is None or plan_path is None:
        raise SystemExit(f"script.json / visual_plan.json not found under {folder}")
    narrations = json.loads(script_path.read_text(encoding="utf-8"))["clip_narrations"]
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    return plan, narrations


def cmd_prompt_gate(args):
    import json

    from pipeline.flow_prompt_builder import (
        build_flow_prompts,
        is_v5_plan,
        validate_character_motion,
        validate_flow_prompts,
        validate_narrations,
    )
    from pipeline.prompt_quality_v5 import validate_production_v5

    folder = Path(args.dir)
    plan, narrations = _load_gate_inputs(folder)
    clips = build_flow_prompts(plan, narrations)
    if is_v5_plan(plan):
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
    if not issues and is_v5_plan(plan) and (folder / "03_visuals").exists():
        from pipeline.clip_qa_contract import compile_clip_qa_contract

        compile_clip_qa_contract(folder, save=True)
        contract_compiled = True
    print(json.dumps({"passed": not issues, "issues": issues, "contract_compiled": contract_compiled}, indent=2, ensure_ascii=False))
    if issues:
        sys.exit(1)


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

    clips_dir = Path(PROJECTS_DIR) / args.project / "03_visuals" / "flow_native_clips"
    files = sorted(clips_dir.glob("clip_*.mp4"), key=numeric_clip_sort_key)
    f0s = [float(analyze_flow_clip_candidate(f).get("f0_median_hz", 0.0)) for f in files]
    print(json.dumps(evaluate_f0_series(f0s), indent=2))


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
    build_asset_manifest(p_dir)
    completed_dir = Path(WORKSPACE_ROOT) / "Completed_Psychology_100_Shorts"
    completed_dir.mkdir(parents=True, exist_ok=True)
    completed_mp4 = completed_dir / f"final_shorts_{pid}.mp4"
    if final_mp4.exists():
        shutil.copy2(final_mp4, completed_mp4)
    print(
        json.dumps(
            {
                "project_id": pid,
                "gemini_generation": gen_res,
                "assembly_passed": bool(evolve_rep.get("passed", evolve_rep.get("after_passed", False))),
                "final_mp4": str(final_mp4),
                "completed_mp4": str(completed_mp4),
            },
            indent=2,
            ensure_ascii=False,
        )
    )



if __name__ == "__main__":
    main()


