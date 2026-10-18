"""
Test Suite for Psychology Shorts Projects, 5-Slot Timetable Staging, and Contract v4 Flow Prompt Wrapper.
Live on-disk project checks are marked with @pytest.mark.integration so default pytest runs stay hermetic
and never mutate existing completed project directories (Decision D7).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from pipeline.config import PROJECTS_DIR, PROJECTS_QUARANTINE_DIR, WORKSPACE_ROOT
from pipeline.flow_prompt_builder import validate_flow_prompts
from pipeline.topics_catalog import PSYCHOLOGY_TOPICS

QUEUE_FILE = WORKSPACE_ROOT / "BCI_Shorts_Channel" / "staging_queue.json"

EXPECTED_PROJECT_IDS = [
    "psych_01_habit_loop_basal_ganglia",
    "psych_02_inner_speech_decoding",
    "psych_03_split_brain_dual_consciousness",
    "psych_04_phineas_gage_frontal_lobe",
    "psych_05_capgras_imposter_delusion",
    "psych_06_glymphatic_sleep_toxins",
    "psych_07_hippocampal_memory_prosthesis",
    "psych_08_inattentional_blindness_gorilla",
    "psych_09_false_memory_elizabeth_loftus",
    "psych_10_cognitive_dissonance_acc",
]


@pytest.mark.integration
def test_10_psychology_projects_exist_and_pass_qa():
    """Validates that all 10 existing projects on disk have intact manifests, scripts, audio, video, and publish artifacts."""
    assert len(EXPECTED_PROJECT_IDS) == 10

    verified_ids = {
        "psych_01_habit_loop_basal_ganglia",
        "psych_02_inner_speech_decoding",
        "psych_03_split_brain_dual_consciousness",
    }

    for proj_id in EXPECTED_PROJECT_IDS:
        if proj_id in verified_ids:
            p_dir = PROJECTS_DIR / proj_id
            assert p_dir.exists(), f"Verified project missing from PROJECTS_DIR: {proj_id}"
            assert (p_dir / "03_visuals" / "flow_provenance_receipt.json").exists(), (
                f"Missing R37 flow_provenance_receipt.json for {proj_id}"
            )
        else:
            p_dir = (PROJECTS_DIR / proj_id) if (PROJECTS_DIR / proj_id).exists() else (PROJECTS_QUARANTINE_DIR / proj_id)
            assert p_dir.exists(), f"Project directory missing: {proj_id}"

        manifest_file = p_dir / "00_project_manifest.json"
        assert manifest_file.exists(), f"Manifest missing for {proj_id}"

        script_file = p_dir / "02_script" / "script.json"
        qa_file = p_dir / "02_script" / "qa_report.json"
        assert script_file.exists(), f"Script missing for {proj_id}"
        assert qa_file.exists(), f"QA report missing for {proj_id}"
        with open(qa_file, "r", encoding="utf-8") as f:
            qa = json.load(f)
        assert qa["all_gates_passed"] is True, f"QA failed for {proj_id}: {qa['gates']}"

        flow_prompts_file = p_dir / "03_visuals" / "flow_all_in_one_prompts.json"
        assert flow_prompts_file.exists(), f"Google Flow All-in-One prompts missing for {proj_id}"

        audio_wav = p_dir / "04_audio" / "audio_master.wav"
        assert audio_wav.exists() and audio_wav.stat().st_size > 100_000, f"Audio master WAV invalid for {proj_id}"

        subtitles_ass = p_dir / "04_audio" / "subtitles.ass"
        assert subtitles_ass.exists(), f"ASS subtitles missing for {proj_id}"

        video_file = p_dir / "05_assembly" / "final_shorts_1080x1920.mp4"
        assert video_file.exists() and video_file.stat().st_size > 100_000, f"Video file invalid for {proj_id}"

        root_video_file = p_dir / f"final_shorts_{proj_id}.mp4"
        assert root_video_file.exists() and root_video_file.stat().st_size > 100_000, (
            f"R25 single root video missing for {proj_id}"
        )

        pub_dir = p_dir / "06_publish"
        assert (pub_dir / "metadata.json").exists(), f"Metadata missing for {proj_id}"
        assert (pub_dir / "thumbnail_var_A.png").exists(), f"Thumbnail A missing for {proj_id}"
        assert (pub_dir / "thumbnail_var_B.png").exists(), f"Thumbnail B missing for {proj_id}"
        assert (pub_dir / "thumbnail_var_C.png").exists(), f"Thumbnail C missing for {proj_id}"
        assert (pub_dir / "ab_test_manifest.json").exists(), f"A/B manifest missing for {proj_id}"


@pytest.mark.integration
def test_staging_queue_schedule_10_slots():
    """Validates that staging_queue.json contains all 10 psychology projects planned across 2 days."""
    assert QUEUE_FILE.exists(), "staging_queue.json does not exist"
    with open(QUEUE_FILE, "r", encoding="utf-8") as f:
        queue_data = json.load(f)

    scheduled = queue_data.get("scheduled_items", [])
    assert len(scheduled) >= 10, f"Expected at least 10 scheduled items, got {len(scheduled)}"

    scheduled_project_ids = [it.get("project_id") for it in scheduled if it.get("project_id")]
    for expected_id in EXPECTED_PROJECT_IDS:
        assert expected_id in scheduled_project_ids, f"{expected_id} is not scheduled in queue"


def test_contract_v4_flow_prompts_wrapper_and_puck_lock(tmp_path: Path):
    """Validates that build_5_concise_flow_prompts wraps flow_prompt_builder in a hermetic temp project."""
    from pipeline.flow_live_single_worker import build_5_concise_flow_prompts

    for topic_item in PSYCHOLOGY_TOPICS[:3]:
        proj_dir = tmp_path / str(topic_item["project_id"])
        (proj_dir / "02_script").mkdir(parents=True, exist_ok=True)
        (proj_dir / "03_visuals").mkdir(parents=True, exist_ok=True)

        prompts = build_5_concise_flow_prompts(proj_dir, topic_item=topic_item)
        assert 5 <= len(prompts) <= 10

        saved_json = proj_dir / "03_visuals" / "flow_all_in_one_prompts.json"
        assert saved_json.exists()
        payload = json.loads(saved_json.read_text(encoding="utf-8"))
        assert payload.get("schema_version") == 4
        assert validate_flow_prompts(payload["clips"]) == []

        for p in prompts:
            p_low = p.lower()
            assert "voice: puck. spoken narration:" in p_low
            assert "aoede" not in p_low
            assert "all about brain" not in p_low
            assert not re.search(r"#[0-9a-f]{6}\b", p_low), f"Hex code found in Flow prompt: {p}"
