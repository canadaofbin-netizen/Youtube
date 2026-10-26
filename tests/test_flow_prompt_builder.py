"""Unit tests for Production Contract v4 flow_prompt_builder and 3,000-topic prompts_db."""

from __future__ import annotations

import json
import re
from pathlib import Path

from pipeline.config import CLIP_ROLE_SEQUENCES, clip_roles, pivot_clip_index
from pipeline.flow_prompt_builder import (
    build_flow_prompts,
    compute_clip_target_duration,
    infer_visual_plan,
    load_visual_plan,
    sanitize_prompt_for_flow,
    validate_character_motion,
    validate_flow_prompts,
    validate_narrations,
)
from pipeline.prompts_db import MANIFEST_JSON_PATH, SQLITE_DB_PATH, lookup_topic_from_db
from pipeline.qa_gates import run_preflight_qa
from pipeline.topics_catalog import ALL_PSYCHOLOGY_100_TOPICS, PSYCHOLOGY_TOPICS

GOLDEN_MD_PATH = Path(
    r"C:\Users\yunky\.gemini\antigravity\brain\a935bacf-5ae3-4e1a-b5e2-7ed23172c727\capgras_delusion_10clip_prompts.md"
)


def _dummy_narrations_for_count(n: int) -> list[str]:
    roles = clip_roles(n)
    has_symptom = "symptom" in roles
    has_breakthrough = "breakthrough" in roles
    out: list[str] = []
    for r in roles:
        if r == "setup":
            out.append(
                "In a quiet clinical room, a patient survived a sudden neural injury and began reporting a deeply unsettling perceptual change to doctors."
            )
        elif r == "symptom":
            out.append(
                "Every familiar stimulus looked clear on the outside, yet the internal emotional signal vanished completely. For his brain, this was a total nightmare."
            )
        elif r == "failure":
            out.append(
                "Standard behavioural reminders and repeated family photographs failed to restore the missing recognition response inside the damaged neural circuit during testing."
            )
        elif r == "crisis":
            if has_symptom:
                out.append(
                    "Here is what went wrong inside the cortex. Structural imaging revealed a severed white-matter pathway between sensory cortex and the deep limbic alarm."
                )
            else:
                out.append(
                    "Structural imaging revealed a severed white-matter pathway between the sensory cortex and the deep limbic alarm. For his brain, this was a total nightmare."
                )
        elif r == "pivot":
            out.append(
                "Instead of a single unified processor, your brain runs two parallel streams: one identifies physical features while the other verifies emotional familiarity."
            )
        elif r in ("mechanism", "step1"):
            if r == "mechanism" and not has_breakthrough:
                out.append(
                    "First, incoming sensory signals race along intact nerve tracts into the sensory cortex. The researchers were left completely stunned."
                )
            else:
                out.append(
                    "First, incoming sensory signals enter the primary receptor organ and race along intact nerve tracts into the primary sensory cortex."
                )
        elif r == "step2":
            out.append(
                "Next, that decoded signal tries to cross the white-matter bridge toward the limbic target, but crashes at the severed junction."
            )
        elif r == "step3":
            out.append(
                "Finally, deprived of autonomic confirmation, the prefrontal cortex resolves the mismatch by concluding that the familiar person must be an impostor."
            )
        elif r == "breakthrough":
            out.append(
                "The researchers were left completely stunned when an alternate sensory channel bypassed the lesion and restored recognition within seconds during controlled trials."
            )
        elif r == "conclusion":
            out.append(
                "Which proves human perception depends on both cortical identification and limbic emotion. Sever the bridge between them, and reality fractures."
            )
    return out


def test_capgras_golden_builds_and_validates_cleanly() -> None:
    golden = next(t for t in PSYCHOLOGY_TOPICS if str(t.get("project_id", "")).startswith("psych_05"))
    narrations = [str(s) for s in golden["clip_narrations"]]
    plan = load_visual_plan(topic_item=golden)
    clips = build_flow_prompts(plan, narrations)

    assert len(clips) == 10
    assert validate_narrations(narrations) == []
    assert validate_flow_prompts(clips) == []
    assert clips[0]["role"] == "setup"
    assert clips[4]["role"] == "pivot"
    assert clips[9]["role"] == "conclusion"

    if GOLDEN_MD_PATH.exists():
        md_text = GOLDEN_MD_PATH.read_text(encoding="utf-8")
        blocks = re.findall(r"```\r?\n(.*?)\r?\n```", md_text, flags=re.DOTALL)
        assert len(blocks) == 10
        for idx, block in enumerate(blocks):
            assert clips[idx]["prompt"] == block.strip(), f"Clip {idx + 1} diverged from golden reference"


def test_all_100_psychology_topics_validate_across_5_to_10_clips() -> None:
    assert len(ALL_PSYCHOLOGY_100_TOPICS) == 100
    for n in (5, 6, 7, 8, 9, 10):
        narrations = _dummy_narrations_for_count(n)
        assert validate_narrations(narrations) == []
        for topic_item in ALL_PSYCHOLOGY_100_TOPICS[:15]:
            plan = load_visual_plan(topic_item=topic_item)
            clips = build_flow_prompts(plan, narrations)
            assert len(clips) == n
            assert validate_flow_prompts(clips) == [], f"Failed for {topic_item.get('project_id')} n={n}"


def test_validator_rejects_banned_tokens_and_invalid_structures() -> None:
    golden = next(t for t in PSYCHOLOGY_TOPICS if str(t.get("project_id", "")).startswith("psych_05"))
    narrations = [str(s) for s in golden["clip_narrations"]]
    plan = load_visual_plan(topic_item=golden)
    base_clips = build_flow_prompts(plan, narrations)

    for bad_snippet in (
        "clockwork gears spinning inside the cortex",
        "shot on ARRI Alexa 85mm lens",
        "glowing #00F0FF neural pathway",
        "Audio: deep sub-bass drone",
        "ALL ABOUT BRAIN watermark",
    ):
        mutated = [dict(c) for c in base_clips]
        mutated[0]["prompt"] = mutated[0]["prompt"].replace(
            "Bright daylight lighting.",
            f"Bright daylight lighting with {bad_snippet}.",
        )
        errs = validate_flow_prompts(mutated)
        assert errs, f"Expected validator to reject snippet: {bad_snippet}"


def test_role_sequences_and_pivot_mapping_5_to_10() -> None:
    expected_pivots = {5: 2, 6: 2, 7: 3, 8: 3, 9: 3, 10: 4}
    for n, expected_pivot in expected_pivots.items():
        roles = clip_roles(n)
        assert len(roles) == n
        assert roles == CLIP_ROLE_SEQUENCES[n]
        assert pivot_clip_index(n) == expected_pivot
        assert roles[expected_pivot] == "pivot"


def test_sanitizer_preserves_allow_listed_anatomy_and_environments() -> None:
    raw = "A brightly lit hospital room with a hospital bed and an EKG monitor. Patient H.M. sits near the severed amygdala and hippocampus."
    cleaned = sanitize_prompt_for_flow(raw, is_spoken_dialogue=False)
    assert "hospital room" in cleaned
    assert "EKG monitor" in cleaned
    assert "severed" in cleaned
    assert "amygdala" in cleaned
    assert "hippocampus" in cleaned
    assert "Patient H.M." not in cleaned

    spoken = 'Spoken narration: "Patient H.M. lost his hippocampus in 1953."'
    assert sanitize_prompt_for_flow(spoken, is_spoken_dialogue=True) == spoken


def test_3000_prompt_database_manifest_and_lookup() -> None:
    assert SQLITE_DB_PATH.exists()
    assert MANIFEST_JSON_PATH.exists()
    manifest = json.loads(MANIFEST_JSON_PATH.read_text(encoding="utf-8"))
    assert manifest["schema_version"] == 4
    assert manifest["total_topics"] == 3000
    assert manifest["neuroscience_topics"] == 1500
    assert manifest["psychology_topics"] == 1500
    assert manifest["qa_verification"]["all_3000_pass"] is True

    for tid in ("brain_0001", "brain_1500", "psych_0001", "psych_1500"):
        bundle = lookup_topic_from_db(tid)
        assert bundle["topic"]["topic_id"] == tid
        assert len(bundle["flow_10clip_prompts"]) == 10
        assert len(bundle["flow_5clip_prompts"]) == 5
        assert validate_flow_prompts(bundle["flow_10clip_prompts"]) == []
        assert validate_flow_prompts(bundle["flow_5clip_prompts"]) == []


def test_preflight_qa_passes_contract_v4_lock() -> None:
    report = run_preflight_qa(require_live_cdp=False)
    assert report["passed"] is True
    assert report["checks"]["contract_v4_golden_prompt_lock"]["passed"] is True


def test_dynamic_8s_10s_duration_routing_and_cutoff_risk() -> None:
    short_hook = compute_clip_target_duration(
        "In 1923, one man looked at his wife and swore a cold stranger had taken her place.",
        role="setup",
    )
    assert short_hook["target_duration"] == "8s"
    assert short_hook["cutoff_risk"] is False

    dense_mech = compute_clip_target_duration(
        "First, visual signals travel from your retina into the fusiform face area, where the cortex decodes exact facial geometry in milliseconds.",
        role="step1",
    )
    assert dense_mech["target_duration"] == "10s"
    assert dense_mech["target_duration"] == "10s"
    assert dense_mech["cutoff_risk"] is False

    overstuffed = compute_clip_target_duration(
        "Simultaneously, hyper-synchronized electrophysiological oscillations reverberate uncontrollably across interconnected thalamocortical and parahippocampal neuroanatomical pathways during stimulation.",
        role="step2",
    )
    assert overstuffed["target_duration"] == "10s"
    assert overstuffed["cutoff_risk"] is True


def test_character_motion_2beat_actions_and_31_O2CmlKOk_brain_lock() -> None:
    target_prefixes = ("psych_04", "psych_08", "psych_11", "psych_18")
    for prefix in target_prefixes:
        topic_item = next(t for t in ALL_PSYCHOLOGY_100_TOPICS if str(t.get("project_id", "")).startswith(prefix))
        narrations = [str(s) for s in topic_item["clip_narrations"]]
        plan = load_visual_plan(topic_item=topic_item)
        clips = build_flow_prompts(plan, narrations)
        assert validate_flow_prompts(clips, check_character_motion=True) == [], f"Failed for {prefix}"
        assert validate_character_motion(clips) == [], f"Character motion failed for {prefix}"
        for idx in (3, 4):
            assert "bright white studio gallery" in clips[idx]["scene"].lower()
            assert "matte-white brain" in clips[idx]["scene"].lower()
        for idx in (5, 6, 7):
            assert "bioluminescent green" in clips[idx]["scene"].lower()

    inferred_plan = infer_visual_plan(topic="Synaptic Plasticity", pillar_id=1)
    inferred_clips = build_flow_prompts(inferred_plan, _dummy_narrations_for_count(10))
    assert validate_flow_prompts(inferred_clips, check_character_motion=True) == []

    static_mutated = [dict(c) for c in inferred_clips]
    static_mutated[0]["scene"] = (
        "A minimalist bright hospital room with a clinical desk and a glass water cup. "
        "A matte-white porcelain mannequin of a clinical subject sits upright at the table, "
        "its translucent frosted-glass cranium catching the light. A doctor mannequin stands nearby. "
        "Wide establishing shot, camera smoothly tracks forward toward the subject. Bright daylight lighting."
    )
    static_mutated[0]["prompt"] = (
        f'{static_mutated[0]["scene"]} Voice: Consistent deep male baritone documentary narrator. '
        f'Spoken narration: "{_dummy_narrations_for_count(10)[0]}"'
    )
    motion_errs = validate_character_motion(static_mutated)
    assert any("static pose" in e or "physical action verb" in e for e in motion_errs)

