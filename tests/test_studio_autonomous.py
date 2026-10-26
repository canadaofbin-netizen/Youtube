"""
Unit and Integration Test Suite for YouTube Studio Autonomous Operations Package
Tests:
1. Stage 6 Publish Thumbnail Variants (A, B, C) & A/B Manifest
2. StudioUploader Payload Preparation & Scheduling Validation
3. CommunityManager DOI Citation & Discussion Question Formatting
4. ThumbnailABTester Two-Proportion Z-Test & Sequential Swap Logic
5. StagingQueueManager 5-Slot Timetable Planning & Bulk Staging Buffer
"""

import json
import shutil
import sys
from pathlib import Path

# Add project root to sys.path
WORKSPACE_ROOT = Path(r"g:\My Drive\Kyubin_Yun_Workspace\07_Youtube")
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from pipeline.config import PROJECTS_DIR
from pipeline.publish import PublishStage
from pipeline.storage import ProjectStorage
from pipeline.studio.ab_tester import ThumbnailABTester
from pipeline.studio.community import CommunityManager
from pipeline.studio.config import (
    CHANNEL_ID,
    CHANNEL_LOCALIZATION_SPEC,
    CHANNEL_RESIDENCE_COUNTRY,
    CHANNEL_RESIDENCE_COUNTRY_NAME,
    SLOT_TIMETABLE,
    STUDIO_SETTINGS_SELECTORS,
    TITLE_DESCRIPTION_LANGUAGE_CODE,
    VIDEO_LANGUAGE_CODE,
    VIDEO_LANGUAGE_LABEL,
    get_pillar_default_slot,
    get_slot_info,
)
from pipeline.studio.queue_manager import StagingQueueManager
from pipeline.studio.uploader import StudioUploader


def test_slot_timetable_and_mapping():
    """Validates North American 5-Slot configuration, 12h times, and pillar mappings."""
    assert len(SLOT_TIMETABLE) == 5
    for s_id in range(1, 6):
        info = get_slot_info(s_id)
        assert info["slot_id"] == s_id
        assert "time_et" in info
        assert "time_et_12h" in info
        assert "time_kst" in info
        assert len(info["recommended_pillars"]) >= 1

    # Check default slot mapping
    assert get_pillar_default_slot("brain_health") == 1
    assert get_pillar_default_slot("bci_tech") == 2
    assert get_pillar_default_slot("brain_news") == 2
    assert get_pillar_default_slot("brain_basics") == 3
    assert get_pillar_default_slot("brain_history") == 4
    assert get_pillar_default_slot("bci_ethics") == 5

    # Check emoji / decorated name mapping
    assert get_pillar_default_slot(" Brain Health") == 1
    assert get_pillar_default_slot(" BCI Tech") == 2
    assert get_pillar_default_slot(" Brain History") == 4


def test_two_tier_localization_config_and_studio_settings():
    """Validates R36 Two-Tier Localization (KR Residence + en-US Upload Language Lock), dry-run, and strict live DOM verification guard."""
    import asyncio

    assert CHANNEL_RESIDENCE_COUNTRY == "KR"
    assert CHANNEL_RESIDENCE_COUNTRY_NAME == "South Korea"
    assert VIDEO_LANGUAGE_CODE == "en-US"
    assert VIDEO_LANGUAGE_LABEL == "English (United States)"
    assert TITLE_DESCRIPTION_LANGUAGE_CODE == "en-US"
    assert CHANNEL_LOCALIZATION_SPEC["channel_residence_country_code"] == "KR"
    assert CHANNEL_LOCALIZATION_SPEC["video_language_code"] == "en-US"
    assert CHANNEL_LOCALIZATION_SPEC["title_description_language_code"] == "en-US"
    assert "country_of_residence_trigger" in STUDIO_SETTINGS_SELECTORS
    assert "audio_language_trigger" in STUDIO_SETTINGS_SELECTORS
    assert "metadata_language_trigger" in STUDIO_SETTINGS_SELECTORS

    uploader = StudioUploader(cdp_port=9222)
    res = uploader.configure_studio_localization(dry_run=True)
    assert res["status"] == "dry_run_success"
    assert res["country_of_residence_code"] == "KR"
    assert res["country_of_residence"] == "South Korea"
    assert res["video_language_code"] == "en-US"
    assert res["title_description_language_code"] == "en-US"

    # Verify that empty/mismatched live DOM values raise RuntimeError instead of silently falling back to constants
    class _StubFailingCDPClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            return False

        async def eval(self, expr: str):
            if "entity-name" in expr:
                return {"url": f"https://studio.youtube.com/channel/{CHANNEL_ID}", "entityName": "ALL ABOUT BRAIN", "isOops": False}
            if "audioLang" in expr:
                return {"audioLang": "English", "metaLang": "English", "category": "Science and technology", "canSave": False}
            if "country-of-residence-select" in expr:
                return "United Kingdom"
            return False

        async def click(self, selectors):
            return True

    orig_get_client = uploader.session.get_direct_client
    uploader.session.get_direct_client = lambda *a, **kw: _StubFailingCDPClient()
    try:
        raised = False
        try:
            asyncio.run(uploader._async_configure_studio_localization(dry_run=False))
        except RuntimeError as exc:
            raised = True
            assert "verification failed" in str(exc)
        assert raised, "Expected RuntimeError when live DOM does not match KR / en-US localization"
    finally:
        uploader.session.get_direct_client = orig_get_client


def test_publish_stage_thumbnail_variants(tmp_path):
    """Validates 3 thumbnail variants (A, B, C), localization metadata, and ab_test_manifest.json."""
    test_proj_id = "test_unit_publish_stage"
    storage = ProjectStorage(test_proj_id, title="Test BCI Mind Reading Shorts", pillar="bci_tech", projects_dir=tmp_path)
    publish = PublishStage(storage)

    result = publish.run(
        title="Can Brain Chips Decode Inner Monologue Thoughts?",
        hashtags=["#Shorts", "#BCI", "#Neuroscience"],
        doi="10.1038/s41586-023-00000-0",
        source_summary="High-density micro-electrode arrays record intracranial voltage dynamics."
    )
    assert "metadata" in result and result["metadata"]["title"].startswith("Can Brain Chips")
    assert result["metadata"]["video_language"] == "en-US"
    assert result["metadata"]["title_description_language"] == "en-US"
    assert result["metadata"]["channel_residence_country"] == "KR"
    assert result["metadata"]["target_audience_region"] == "US"

    publish_dir = storage.get_stage_dir("06_publish")
    thumb_var_a = publish_dir / "thumbnail_var_A.png"
    thumb_var_b = publish_dir / "thumbnail_var_B.png"
    thumb_var_c = publish_dir / "thumbnail_var_C.png"
    thumb_default = publish_dir / "thumbnail.png"
    manifest_file = publish_dir / "ab_test_manifest.json"

    assert thumb_var_a.exists(), "Variant A thumbnail missing"
    assert thumb_var_b.exists(), "Variant B thumbnail missing"
    assert thumb_var_c.exists(), "Variant C thumbnail missing"
    assert thumb_default.exists(), "Default thumbnail missing"
    assert manifest_file.exists(), "ab_test_manifest.json missing"

    with open(manifest_file, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    assert manifest["project_id"] == test_proj_id
    assert manifest["channel_id"] == CHANNEL_ID
    assert manifest["current_active_variant"] == "A"
    assert "A" in manifest["variants"]
    assert "B" in manifest["variants"]
    assert "C" in manifest["variants"]
    assert len(manifest["schedule"]) == 3
    assert manifest["statistical_evaluation"]["metric"] == "Search & Browse CTR"


def test_z_score_calculation():
    """Validates Two-Proportion Z-Test statistical calculations."""
    # Test equal proportions
    res_equal = ThumbnailABTester.calculate_z_score(50, 1000, 50, 1000)
    assert res_equal["z_score"] == 0.0
    assert res_equal["p_value"] == 1.0
    assert not res_equal["statistically_significant"]

    # Test statistically significant difference (p < 0.05, |Z| > 1.96)
    # A: 50 / 1000 = 5.0%, B: 100 / 1000 = 10.0%
    res_sig = ThumbnailABTester.calculate_z_score(50, 1000, 100, 1000)
    assert res_sig["statistically_significant"] is True
    assert res_sig["p_value"] < 0.001
    assert abs(res_sig["z_score"]) > 1.96
    assert res_sig["winner"] == "var_2"


def _seed_hermetic_studio_project(
    projects_dir: Path,
    project_id: str,
    *,
    title: str = "Two Conscious Minds Inside One Human Skull",
    pillar: str = "brain_mysteries",
    doi: str = "10.1093/brain/123.7.1293",
    v5_ready: bool = True,
    live_receipt: dict | None = None,
) -> ProjectStorage:
    """Creates a hermetic Stage-6-ready project inside tmp_path (R28: zero live Drive I/O)."""
    import cv2
    import numpy as np
    from pipeline.config import clip_roles
    from pipeline.flow_prompt_builder import build_flow_prompts

    storage = ProjectStorage(project_id, title=title, pillar=pillar, projects_dir=projects_dir)
    asm_dir = storage.get_stage_dir("05_assembly")
    mp4_path = asm_dir / "final_shorts_1080x1920.mp4"
    writer = cv2.VideoWriter(str(mp4_path), cv2.VideoWriter_fourcc(*"mp4v"), 10.0, (1080, 1920))
    for idx in range(12):
        frame = np.full((1920, 1080, 3), 30 + idx * 10, dtype=np.uint8)
        writer.write(frame)
    writer.release()

    PublishStage(storage).run(
        title=title,
        hashtags=["#Shorts", "#Neuroscience", "#BrainMysteries"],
        doi=doi,
        source_summary="Split-brain corpus callosum severing study on dual hemispheric consciousness.",
    )

    if v5_ready:
        narrations = [
            "In nineteen sixty one, a quiet man at Yale pressed a switch, and a stranger behind the wall screamed in pain.",
            "He kept going, switch after switch, even when the screams stopped. For his brain, this was a total nightmare, yet his hand kept moving.",
            "Before the test, experts guessed that almost nobody would go all the way to the last and most dangerous switch on the board.",
            "Here is what went wrong. A calm man in a gray coat kept saying one short line, please continue, and that was enough.",
            "Instead of asking if it was right, most people asked who was in charge, and they handed the choice to him.",
            "First, the man in charge looked calm and sure, so the room felt safe, even while the cries grew louder behind the wall.",
            "Next, each new switch was only a little stronger than the last one, so stopping felt like saying every earlier choice was wrong.",
            "Finally, when the man in the coat stood close, people obeyed more, and when he left the room, most of them stopped.",
            "The researchers were left completely stunned. Almost two out of three people pressed every switch, all the way to the very end.",
            "Which proves that a calm voice in charge can move your hand, so the next time someone says just continue, you can ask why.",
        ]
        shot_s1 = {
            "scene_id": "S1",
            "shot_type": "cu",
            "camera": "Close-up tracking shot that slowly pushes in on the porcelain teacher's hands",
            "environment": "A cramped nineteen sixties university laboratory with a gray shock generator on a wooden desk",
            "action": "The porcelain teacher in a rolled-up white shirt presses a heavy toggle switch with a trembling hand",
            "prop_change": "A red indicator light flashes and the voltmeter needle jumps across the dial",
            "reaction": "His shoulders flinch and he twists in his chair toward the man in the gray lab coat behind him",
            "detail": "Bright daylight falls across the row of labelled switches",
        }
        shot_s2 = {
            "scene_id": "S2",
            "shot_type": "cu",
            "camera": "Close-up tracking shot that slowly pushes in on the porcelain teacher's hands",
            "environment": "A cramped nineteen sixties university laboratory with a gray shock generator on a wooden desk",
            "action": "The porcelain experimenter in a gray lab coat taps his clipboard and lowers his pen toward the generator",
            "prop_change": "The pen clicks and a sheet of notes slides off the desk onto the floor",
            "reaction": "The teacher clenches his fists on the desk and slumps forward",
            "detail": "Bright daylight falls across the row of labelled switches",
        }
        shots = {r: (shot_s2 if r in ("crisis", "step1", "step3") else shot_s1) for r in clip_roles(10)}
        plan = {
            "schema": 5,
            "visual_mode": "BEHAVIORAL_PSYCH",
            "dossier": "test_obedience",
            "must_have_scenes": [
                {
                    "id": "S1",
                    "title": "teacher presses the switch",
                    "iconic": True,
                    "recognition_hook": "the shock board",
                    "key_visual": {
                        "description": "the teacher presses a toggle switch on the generator",
                        "must_show": ["teacher", "switch|lever|toggle"],
                    },
                },
                {"id": "S2", "title": "experimenter says please continue", "iconic": False},
            ],
            "shots": shots,
            "cast": {
                "subject": "teacher",
                "wardrobe": {"teacher": "a rolled-up white 1960s shirt", "experimenter": "a gray lab coat"},
            },
        }
        clips = build_flow_prompts(plan, narrations)
        storage.save_json("02_script", "script.json", {"clip_narrations": narrations})
        storage.save_json("03_visuals", "visual_plan.json", plan)
        storage.save_json("03_visuals", "flow_all_in_one_prompts.json", {"schema": 5, "clips": clips})

    if live_receipt is not None:
        storage.save_json("06_publish", "upload_receipt.json", live_receipt)

    return storage


def test_uploader_payload_and_dry_run(tmp_path):
    """Validates StudioUploader payload preparation, localization fields, burn-in option, and dry-run output."""
    proj_id = "psych_03_split_brain_dual_consciousness"
    _seed_hermetic_studio_project(tmp_path, proj_id)
    uploader = StudioUploader(cdp_port=9222, projects_dir=tmp_path)

    payload = uploader.prepare_upload_payload(proj_id, visibility="unlisted")
    assert payload["project_id"] == proj_id
    assert payload["visibility"] == "unlisted"
    assert len(payload["title"]) <= 60
    assert payload["video_path"].exists()
    assert payload["thumbnail_path"].exists()
    assert payload["video_language"] == "en-US"
    assert payload["title_description_language"] == "en-US"
    assert payload["channel_residence_country"] == "KR"

    receipt = uploader.upload_project(proj_id, visibility="unlisted", dry_run=True)
    assert receipt["status"] == "dry_run_success"
    assert "shorts_url" in receipt
    assert receipt["ai_altered_content_declared"] is True
    assert receipt["video_language"] == "en-US"
    assert receipt["title_description_language"] == "en-US"
    assert receipt["channel_residence_country"] == "KR"

    # Test first-frame burn-in fallback path
    payload_burn = uploader.prepare_upload_payload(proj_id, visibility="unlisted", burn_first_frame=True)
    burnin_path = payload_burn["video_path"]
    assert burnin_path.exists()
    assert "burnin" in burnin_path.name


def test_community_manager_comment_payload(tmp_path):
    """Validates CommunityManager dynamic DOI and debate trigger generation without touching live Drive."""
    proj_id = "psych_03_split_brain_dual_consciousness"
    _seed_hermetic_studio_project(tmp_path, proj_id, doi="10.1093/brain/123.7.1293")
    manager = CommunityManager(cdp_port=9222, projects_dir=tmp_path, dossiers_root=tmp_path / "empty_dossiers")

    comm_data = manager.prepare_comment_content(proj_id)
    assert "10.1093/brain/123.7.1293" in comm_data["comment_text"]
    assert "doi.org" in comm_data["comment_text"]

    receipt = manager.post_and_pin_comment(proj_id, dry_run=True)
    assert receipt["status"] == "dry_run_success"
    assert receipt["pinned"] is True


def test_ab_tester_sequential_swap_and_eval(tmp_path):
    """Validates A/B tester sequential rotation and statistical evaluation (both challenger and baseline wins)."""
    proj_id = "psych_03_split_brain_dual_consciousness"
    _seed_hermetic_studio_project(tmp_path, proj_id)
    tester = ThumbnailABTester(cdp_port=9222, projects_dir=tmp_path)

    # Test swap to specific variant
    swap_res = tester.swap_to_variant(proj_id, "B", dry_run=True)
    assert swap_res["active_variant"] == "B"

    # Test swap next (B -> C)
    swap_next_res = tester.swap_next(proj_id, dry_run=True)
    assert swap_next_res["active_variant"] == "C"

    # Test statistical significance evaluation: Challenger C wins
    custom_metrics_c_wins = {
        "A": {"impressions": 2000, "clicks": 100},  # 5% CTR
        "B": {"impressions": 2000, "clicks": 160},  # 8% CTR
        "C": {"impressions": 2000, "clicks": 240}   # 12% CTR
    }
    eval_c = tester.evaluate_significance(proj_id, metrics=custom_metrics_c_wins, dry_run=True)
    assert eval_c["conclusive"] is True
    assert eval_c["winner_variant"] == "C"
    assert eval_c["statistical_test"] == "Two-Proportion Z-Test"

    # Test statistical significance evaluation: Baseline A wins
    custom_metrics_a_wins = {
        "A": {"impressions": 2000, "clicks": 200},  # 10% CTR
        "B": {"impressions": 2000, "clicks": 100},  # 5% CTR
        "C": {"impressions": 2000, "clicks": 80}    # 4% CTR
    }
    eval_a = tester.evaluate_significance(proj_id, metrics=custom_metrics_a_wins, dry_run=True)
    assert eval_a["conclusive"] is True, "Baseline Variant A victory failed to conclude"
    assert eval_a["winner_variant"] == "A", f"Expected Variant A winner, got {eval_a['winner_variant']}"


def test_staging_queue_planner(tmp_path):
    """Validates StagingQueueManager prime-slot and 5-slot calendar distribution, v5 gate, and booked-slot preservation."""
    projects_root = tmp_path / "projects"
    tmp_queue = tmp_path / "staging_queue.json"

    # 1. Published live project -> must be archived to history and never re-scheduled (R34)
    _seed_hermetic_studio_project(
        projects_root,
        "psych_01_habit_loop_basal_ganglia",
        pillar="brain_health",
        v5_ready=False,
        live_receipt={
            "project_id": "psych_01_habit_loop_basal_ganglia",
            "video_id": "p4ou90cHt50",
            "shorts_url": "https://www.youtube.com/shorts/p4ou90cHt50",
            "title": "Why Deep Brain Loops Lock Habits on Autopilot",
            "visibility": "public",
            "status": "published_public",
        },
    )
    # 2. Legacy v4 unpublished draft -> must be blocked by default (R18-V5)
    _seed_hermetic_studio_project(
        projects_root,
        "psych_07_stanford_prison_deindividuation",
        pillar="bci_ethics",
        v5_ready=False,
    )
    # 3. Two v5-passing ready projects -> eligible for scheduling
    _seed_hermetic_studio_project(projects_root, "v5_ready_alpha", pillar="bci_tech", v5_ready=True)
    _seed_hermetic_studio_project(projects_root, "v5_ready_beta", pillar="brain_history", v5_ready=True)

    # Seed an upcoming already-booked slot on 2026-10-28 Slot 2 to verify zero double-booking (R30-B)
    tmp_queue.write_text(
        json.dumps({
            "version": "1.0",
            "channel_handle": "@AllAboutBrainOfficial",
            "slots_per_day": 2,
            "scheduled_items": [
                {
                    "schedule_id": "2026-10-28_slot2",
                    "date": "2026-10-28",
                    "slot_id": 2,
                    "slot_name": "Midday_Peak",
                    "time_et": "12:00",
                    "target_time_et": "2026-10-28 12:00 ET",
                    "project_id": "v5_booked_upcoming",
                    "video_id": "BookedVid01",
                    "title": "Already Scheduled Future Short",
                    "pillar": "bci_tech",
                    "status": "scheduled_public",
                }
            ],
            "history": [],
        }),
        encoding="utf-8",
    )

    queue_mgr = StagingQueueManager(queue_file=tmp_queue, cdp_port=9222, projects_dir=projects_root)
    ready = queue_mgr.scan_ready_projects()
    ready_pids = {r["project_id"] for r in ready}
    assert ready_pids == {"v5_ready_alpha", "v5_ready_beta"}
    assert "psych_01_habit_loop_basal_ganglia" not in ready_pids
    assert "psych_07_stanford_prison_deindividuation" not in ready_pids

    # Stage-gated default (daily_prime_only=True -> 2 prime slots/day = 6 slots over 3 days)
    plan_prime = queue_mgr.plan_5_slot_schedule(days=3, start_date="2026-10-28", daily_prime_only=True)
    assert plan_prime["planned_days"] == 3
    assert plan_prime["total_slots"] == 6
    assert plan_prime["preserved_future_slots"] == 1
    assert plan_prime["assigned_slots"] == 3  # 1 preserved booked + 2 new v5 ready

    # First slot (2026-10-28 Slot 2) must remain occupied by v5_booked_upcoming (never overwritten!)
    slot_map = {(it["date"], it["slot_id"]): it for it in plan_prime["items"]}
    assert slot_map[("2026-10-28", 2)]["project_id"] == "v5_booked_upcoming"
    assert slot_map[("2026-10-28", 2)]["status"] == "scheduled_public"

    # Full 5-slot calendar mode (daily_prime_only=False -> 5 slots/day = 15 slots over 3 days)
    plan = queue_mgr.plan_5_slot_schedule(days=3, start_date="2026-10-28", daily_prime_only=False)
    assert plan["planned_days"] == 3
    assert plan["total_slots"] == 15
    assert plan["assigned_slots"] == 3

    # Verify ZERO duplicate projects scheduled & history preserved
    assigned_ids = [item["project_id"] for item in plan["items"] if item["project_id"]]
    assert len(assigned_ids) == len(set(assigned_ids)), f"Duplicate projects found in schedule: {assigned_ids}"
    assert set(assigned_ids) == {"v5_booked_upcoming", "v5_ready_alpha", "v5_ready_beta"}
    assert "psych_01_habit_loop_basal_ganglia" not in assigned_ids
    assert plan["vacant_slots"] == plan["total_slots"] - len(assigned_ids)

    saved_q = queue_mgr.load_queue()
    hist_pids = {h["project_id"] for h in saved_q.get("history", [])}
    assert "psych_01_habit_loop_basal_ganglia" in hist_pids

    summary = queue_mgr.get_status_summary()
    assert summary["total_completed_projects"] == 3
    assert summary["published_or_live_count"] == 1
    assert summary["v5_ready_unpublished_count"] == 2

