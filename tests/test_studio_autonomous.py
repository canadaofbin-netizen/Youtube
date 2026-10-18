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
    storage = ProjectStorage(test_proj_id, title="Test BCI Mind Reading Shorts", pillar="bci_tech")
    try:
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
    finally:
        # Cleanup temporary test project
        shutil.rmtree(storage.project_dir, ignore_errors=True)


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


import pytest


@pytest.mark.integration
def test_uploader_payload_and_dry_run():
    """Validates StudioUploader payload preparation, localization fields, burn-in option, and dry-run output."""
    uploader = StudioUploader(cdp_port=9222)
    proj_id = "psych_03_split_brain_dual_consciousness"
    proj_dir = PROJECTS_DIR / proj_id
    manifest_path = proj_dir / "00_project_manifest.json"
    orig_manifest = manifest_path.read_bytes() if manifest_path.exists() else None
    receipt_path = proj_dir / "06_publish" / "upload_receipt.json"
    orig_receipt = receipt_path.read_bytes() if receipt_path.exists() else None
    burnin_path: Path | None = None
    try:
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
    finally:
        if burnin_path and "burnin" in burnin_path.name and burnin_path.exists():
            burnin_path.unlink(missing_ok=True)
        for leftover in proj_dir.rglob("*_burnin.mp4"):
            leftover.unlink(missing_ok=True)
        if orig_receipt is not None:
            receipt_path.write_bytes(orig_receipt)
        elif receipt_path.exists():
            receipt_path.unlink(missing_ok=True)
        if orig_manifest is not None:
            manifest_path.write_bytes(orig_manifest)


@pytest.mark.integration
def test_community_manager_comment_payload():
    """Validates CommunityManager dynamic DOI and debate trigger generation."""
    manager = CommunityManager(cdp_port=9222)
    proj_id = "psych_03_split_brain_dual_consciousness"
    proj_dir = PROJECTS_DIR / proj_id
    manifest_path = proj_dir / "00_project_manifest.json"
    orig_manifest = manifest_path.read_bytes() if manifest_path.exists() else None
    comm_receipt = proj_dir / "06_publish" / "community_receipt.json"
    orig_comm = comm_receipt.read_bytes() if comm_receipt.exists() else None
    try:
        comm_data = manager.prepare_comment_content(proj_id)
        assert "10.1093/brain/123.7.1293" in comm_data["comment_text"]
        assert "doi.org" in comm_data["comment_text"]

        receipt = manager.post_and_pin_comment(proj_id, dry_run=True)
        assert receipt["status"] == "dry_run_success"
        assert receipt["pinned"] is True
    finally:
        if orig_comm is not None:
            comm_receipt.write_bytes(orig_comm)
        elif comm_receipt.exists():
            comm_receipt.unlink(missing_ok=True)
        if orig_manifest is not None:
            manifest_path.write_bytes(orig_manifest)


@pytest.mark.integration
def test_ab_tester_sequential_swap_and_eval():
    """Validates A/B tester sequential rotation and statistical evaluation (both challenger and baseline wins)."""
    tester = ThumbnailABTester(cdp_port=9222)
    proj_id = "psych_03_split_brain_dual_consciousness"
    proj_dir = PROJECTS_DIR / proj_id
    manifest_path = proj_dir / "00_project_manifest.json"
    orig_manifest = manifest_path.read_bytes() if manifest_path.exists() else None
    ab_path = proj_dir / "06_publish" / "ab_test_manifest.json"
    orig_ab = ab_path.read_bytes() if ab_path.exists() else None
    ab_report_path = proj_dir / "06_publish" / "ab_test_report.json"
    orig_ab_report = ab_report_path.read_bytes() if ab_report_path.exists() else None
    thumb_path = proj_dir / "06_publish" / "thumbnail.png"
    orig_thumb = thumb_path.read_bytes() if thumb_path.exists() else None
    try:
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
    finally:
        if orig_ab is not None:
            ab_path.write_bytes(orig_ab)
        if orig_ab_report is not None:
            ab_report_path.write_bytes(orig_ab_report)
        elif ab_report_path.exists():
            ab_report_path.unlink(missing_ok=True)
        if orig_thumb is not None:
            thumb_path.write_bytes(orig_thumb)
        if orig_manifest is not None:
            manifest_path.write_bytes(orig_manifest)


@pytest.mark.integration
def test_staging_queue_planner():
    """Validates StagingQueueManager 5-slot calendar distribution with zero duplicate scheduling."""
    queue_mgr = StagingQueueManager(cdp_port=9222)
    orig_queue = queue_mgr.queue_file.read_bytes() if queue_mgr.queue_file.exists() else None
    try:
        ready = queue_mgr.scan_ready_projects()
        assert len(ready) >= 1

        plan = queue_mgr.plan_5_slot_schedule(days=3)
        assert plan["planned_days"] == 3
        assert plan["total_slots"] == 15
        assert plan["assigned_slots"] >= 1

        # Verify ZERO duplicate projects scheduled
        assigned_ids = [item["project_id"] for item in plan["items"] if item["project_id"]]
        assert len(assigned_ids) == len(set(assigned_ids)), f"Duplicate projects found in schedule: {assigned_ids}"
        assert plan["vacant_slots"] == plan["total_slots"] - len(assigned_ids)

        summary = queue_mgr.get_status_summary()
        assert summary["total_completed_projects"] >= 1
    finally:
        if orig_queue is not None:
            queue_mgr.queue_file.write_bytes(orig_queue)


if __name__ == "__main__":
    print("Running YouTube Studio Autonomous Test Suite...")
    test_slot_timetable_and_mapping()
    print(" [PASS] test_slot_timetable_and_mapping")
    test_two_tier_localization_config_and_studio_settings()
    print(" [PASS] test_two_tier_localization_config_and_studio_settings")
    test_publish_stage_thumbnail_variants(None)
    print(" [PASS] test_publish_stage_thumbnail_variants")
    test_z_score_calculation()
    print(" [PASS] test_z_score_calculation")
    test_uploader_payload_and_dry_run()
    print(" [PASS] test_uploader_payload_and_dry_run")
    test_community_manager_comment_payload()
    print(" [PASS] test_community_manager_comment_payload")
    test_ab_tester_sequential_swap_and_eval()
    print(" [PASS] test_ab_tester_sequential_swap_and_eval")
    test_staging_queue_planner()
    print(" [PASS] test_staging_queue_planner")
    print("\nALL 8 TESTS PASSED SUCCESSFULLY!")
