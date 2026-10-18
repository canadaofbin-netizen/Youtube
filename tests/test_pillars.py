"""
Comprehensive Multi-Pillar Test Suite for ALL ABOUT BRAIN (Production Contract v4)
Validates all 7 Content Pillars against Contract v4 word budgets (18-28 words/clip),
12 Master QA Gates, flow_prompt_builder prompt validation, PipelineOrchestrator blueprint execution,
and 2-Track Historical x Academic DOI Research Engine.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

from pipeline.config import (
    CLIP_ROLE_SEQUENCES,
    NARRATIVE_STYLE_SPECS,
    PILLAR_DEFAULT_STYLE_MAP,
    WORKSPACE_ROOT,
    resolve_narrative_style,
    script_word_range,
)
from pipeline.flow_prompt_builder import (
    build_flow_prompts,
    load_visual_plan,
    validate_flow_prompts,
    validate_narrations,
)
from pipeline.generator import ContentGenerator
from pipeline.orchestrator import PipelineOrchestrator
from pipeline.pillars import get_pillar, list_all_pillars
from pipeline.researcher import HISTORICAL_CASE_VAULT, TopicResearcher
from pipeline.scripting import ScriptingStage
from pipeline.storage import ProjectStorage

if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))


def test_all_pillars_compliance():
    """Audits all 7 Content Pillars against Production Contract v4 narration/prompt rules and 12 Master QA Gates."""
    pillars = list_all_pillars()
    assert len(pillars) == 7, f"Expected 7 pillars, found {len(pillars)}"

    dummy_storage = ProjectStorage("temp_audit_pillar_storage")
    scripting_validator = ScriptingStage(dummy_storage)

    try:
        for pillar in pillars:
            bp = pillar.production_blueprint
            p_name = pillar.name

            narrations = bp.get("clip_narrations", [])
            assert 5 <= len(narrations) <= 10, f"Pillar {p_name} missing valid clip_narrations: {len(narrations)}"
            assert validate_narrations(narrations) == [], (
                f"Pillar {p_name} clip_narrations failed Contract v4 validation: {validate_narrations(narrations)}"
            )

            w_min, w_max = script_word_range(len(narrations))
            script_input = {
                "hook": {"text": bp["hook_text"]},
                "setup": {"text": bp["setup_text"]},
                "core": {"text": bp["core_text"]},
                "payoff": {"text": bp["payoff_text"]},
                "clip_narrations": narrations,
            }
            qa_rep = scripting_validator.validate_qa_gates(
                script_input,
                bp.get("fact_citations", []),
                min_words=w_min,
                max_words=w_max,
            )
            assert qa_rep["all_gates_passed"] is True, f"Pillar {p_name} failed QA gates: {qa_rep['gates']}"

            plan = load_visual_plan(topic_item=bp)
            clips = build_flow_prompts(plan, narrations)
            assert validate_flow_prompts(clips) == [], (
                f"Pillar {p_name} flow prompts failed Contract v4 validation: {validate_flow_prompts(clips)}"
            )
    finally:
        shutil.rmtree(dummy_storage.project_dir, ignore_errors=True)


def test_full_pipeline_verification():
    """Executes full pipeline blueprint verification and validates 12 QA gates and lossless storage integrity."""
    pillars = list_all_pillars()
    health_pillar = pillars[5]  # brain_health
    bp_health = health_pillar.production_blueprint
    target_project = "20261008_verify_brain_health_glymphatic"

    orchestrator = PipelineOrchestrator(
        project_id=target_project,
        title=bp_health["title"],
        pillar=bp_health["pillar"],
    )

    try:
        render_result = orchestrator.run_from_blueprint(
            blueprint=bp_health,
            mode="full",
        )

        assert render_result["master_qa"]["all_gates_passed"] is True
        assert render_result["integrity_report"]["all_intact"] is True
        manifest = orchestrator.storage.get_manifest()
        assert manifest["project_id"] == target_project
    finally:
        shutil.rmtree(orchestrator.storage.project_dir, ignore_errors=True)


def test_narrative_router_and_contract_v4_generation():
    """Validates all 6 Historical Storytelling Archetypes, auto-routing, and Contract v4 prompt generation."""
    gen = ContentGenerator()
    dummy_storage = ProjectStorage("temp_audit_narrative_router")
    scripting_validator = ScriptingStage(dummy_storage)

    try:
        for p_id, expected_style in PILLAR_DEFAULT_STYLE_MAP.items():
            pillar_obj = get_pillar(p_id)
            assert pillar_obj.default_narrative_style == expected_style
            assert resolve_narrative_style("auto", pillar_id=p_id, topic="") == expected_style

        assert resolve_narrative_style("auto", pillar_id="bci_tech", topic="Capgras Patient Delusion") == "case_file"
        assert resolve_narrative_style("auto", pillar_id="bci_tech", topic="Ancient Egypt Trepanation") == "delusion_museum"
        assert resolve_narrative_style("auto", pillar_id="bci_tech", topic="Classified Milgram Experiment") == "forbidden_lab"
        assert resolve_narrative_style("auto", pillar_id="bci_tech", topic="Einstein Brain Autopsy") == "icon_autopsy"
        assert resolve_narrative_style("auto", pillar_id="bci_tech", topic="Prehistoric Caveman Dopamine Loop") == "caveman_brain"
        assert resolve_narrative_style("auto", pillar_id="brain_history", topic="Neuralink BCI Electrode") == "chronicle_cutaway"

        edge_topics = [
            "Sleep",
            "Split Brain Consciousness",
            "The Extraordinary Intracortical Microelectrode Array Decoding Subvocalized Speech Signals Instantly",
            None,
        ]
        for style_id in NARRATIVE_STYLE_SPECS:
            for t in edge_topics:
                bp = gen.generate("bci_tech", topic=t, style=style_id)
                assert bp["narrative_style"] == style_id
                assert bp["narrative_spine"] in CLIP_ROLE_SEQUENCES.values()
                assert gen._verify_blueprint(bp) is True, f"Blueprint verification failed for style={style_id}, topic={t}"

                narrations = bp["clip_narrations"]
                assert validate_narrations(narrations) == []
                assert validate_flow_prompts(bp["flow_all_in_one_prompts"]) == []

                w_min, w_max = script_word_range(len(narrations))
                script_input = {
                    "hook": {"text": bp["hook_text"]},
                    "setup": {"text": bp["setup_text"]},
                    "core": {"text": bp["core_text"]},
                    "payoff": {"text": bp["payoff_text"]},
                    "clip_narrations": narrations,
                }
                qa_rep = scripting_validator.validate_qa_gates(
                    script_input,
                    bp.get("fact_citations", []),
                    min_words=w_min,
                    max_words=w_max,
                )
                assert qa_rep["all_gates_passed"] is True, (
                    f"QA gates failed for style={style_id}, topic={t}: {qa_rep['gates']}"
                )
    finally:
        shutil.rmtree(dummy_storage.project_dir, ignore_errors=True)


def test_2_track_topic_researcher_and_news_hunt_report():
    """Verify the 2-Track Historical x Academic DOI Research Engine and 5D scoring rubric."""
    assert len(HISTORICAL_CASE_VAULT) >= 12
    covered_styles = {entry["narrative_style"] for entry in HISTORICAL_CASE_VAULT}
    for style_id in NARRATIVE_STYLE_SPECS:
        assert style_id in covered_styles, f"Missing historical vault coverage for archetype {style_id}"

    researcher = TopicResearcher()
    cards = researcher.research_batch(
        query="delgado bull",
        style="forbidden_lab",
        count=2,
        allow_network=False,
    )
    assert len(cards) == 2
    top = cards[0]
    assert top["narrative_style"] == "forbidden_lab"
    assert top["weighted_score"] >= 3.5
    assert top["passed_threshold"] is True
    assert "story_context" in top and "era_year" in top["story_context"]
    assert "sensory_organ_link" in top["story_context"] and "brain_regions" in top["story_context"]
    assert "visual_plan" in top and isinstance(top["visual_plan"], dict)

    saved_paths = {}
    try:
        saved_paths = researcher.save_news_hunt_report(cards, output_date="9999-12-31")
        assert saved_paths["markdown_path"].exists()
        assert saved_paths["json_path"].exists()
        text = saved_paths["markdown_path"].read_text(encoding="utf-8")
        assert "10.1038/" in text or "10.1126/" in text or "10." in text
    finally:
        for p in saved_paths.values():
            if p and p.exists():
                p.unlink(missing_ok=True)
