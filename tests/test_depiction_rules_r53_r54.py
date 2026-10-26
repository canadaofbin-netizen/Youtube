"""Unit tests for Modular Depiction Rules & Compositional Prompt Engine (Rules R53 & R54)."""

from __future__ import annotations

from pipeline.depiction_rules import (
    BrainDepictionRule,
    CastDepictionRule,
    PromptComposer,
)
from pipeline.flow_prompt_builder import build_flow_prompts
from pipeline.prompt_quality_v5 import validate_production_v5
from pipeline.scene_blueprint import still_frame_prompt, timed_video_prompt


def test_r53_sanitizes_particle_and_spark_phrasing_in_brain_scenes() -> None:
    raw = (
        "Inside the matte-white brain, the amygdala pulses electric cyan-blue and fires bioluminescent green signal "
        "particles along the tract; at the crimson-red gap, signal particles scatter into space and sparks fly."
    )
    cleaned = BrainDepictionRule.sanitize_brain_signal_text(raw)
    assert "particles" not in cleaned.lower()
    assert "sparks" not in cleaned.lower()
    assert "scatter" not in cleaned.lower()
    assert "bioluminescent green" not in cleaned.lower()
    assert "cyan-blue" not in cleaned.lower()
    assert "light pulse" in cleaned.lower()
    assert BrainDepictionRule.validate_restrained_signal(cleaned, "brain_void") == []


def test_r53_gate_rejects_raw_particles_in_brain_clip() -> None:
    bad_scene = "Macro view inside the matte-white brain as glowing particles and sparks scatter into space."
    errs = BrainDepictionRule.validate_restrained_signal(bad_scene, "brain_void")
    assert len(errs) == 1
    assert "[brain_signal]" in errs[0]


def test_r54_brain_video_prompt_excludes_mannequin_motion_suffix() -> None:
    plan = {
        "visual_mode": "NEURO_BIOLOGY",
        "real_environment": "an 1848 Vermont granite railroad cut",
        "cast": {"wardrobe": {"foreman": "rolled-up white linen shirtsleeves and dark waistcoat"}},
        "shots": {"step1": {"setting": "brain_void", "scene_id": "S1"}},
    }
    raw_brain = (
        "Macro view inside the architectural cross-section cutaway of the matte-white brain in bright studio daylight. "
        "Bioluminescent green signal particles stream into the ventromedial prefrontal cortex."
    )
    vp = timed_video_prompt(plan, "step1", "First, picture the judgment center behind your eyes.", "tts", "9:16", raw_brain)
    assert "particles" not in vp.lower()
    assert "sparks" not in vp.lower()
    assert "subsurface luminance stays smoothly contained" in vp.lower()
    assert "porcelain figures move" not in vp.lower()
    assert "same mannequins" not in vp.lower()

    sp = still_frame_prompt(plan, "step1", "start", "9:16", raw_brain)
    assert "particles" not in sp.lower()
    assert "sparks" not in sp.lower()
    assert "subsurface luminance stays smoothly contained" in sp.lower()


def test_cast_cranium_clause_respects_visual_mode() -> None:
    assert "opaque" in CastDepictionRule.cranium_clause("BEHAVIORAL_PSYCH", "real_env")
    assert "opaque" in CastDepictionRule.cranium_clause("HYBRID", "real_env")
    assert "translucent frosted-glass" in CastDepictionRule.cranium_clause("HYBRID", "brain_void")
    assert "translucent frosted-glass" in CastDepictionRule.cranium_clause("NEURO_BIOLOGY", "real_env")
