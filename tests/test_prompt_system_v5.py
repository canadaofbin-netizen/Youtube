"""Prompt System v5 tests: anatomy map, plain language / TTS-safe text, voice semitone gate, v5 builder routing,
production gate (iconic scene, action physics, brain caps), research dossier and asset manifest."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from pipeline.anatomy_map import find_regions, region_named_in, resolve_region
from pipeline.config import (
    FLOW_MOTION_STYLE_V5,
    FLOW_PROMPT_PREFIX,
    FLOW_VOICE_PROMPT_DESCRIPTOR_V5,
    MODE_ROLE_SETTINGS,
    VOICE_FALLBACK_MODEL_DIR,
    clip_roles,
)
from pipeline.flow_prompt_builder import (
    build_flow_prompts,
    flow_prompt_prefix,
    resolve_clip_setting,
    validate_flow_prompts,
    validate_narrations,
)
from pipeline.plain_language import analyze_script, find_jargon, fk_grade, to_display_text, to_tts_text, tts_issues
from pipeline.prompt_quality_v5 import _region_field_issue, check_action_physics, validate_production_v5
from pipeline.voice_consistency import evaluate_f0_series, semitones

NARRATIONS = [
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


def _shot(scene_id: str, action: str, prop: str, reaction: str) -> dict:
    return {
        "scene_id": scene_id,
        "shot_type": "cu",
        "camera": "Close-up tracking shot that slowly pushes in on the porcelain teacher's hands",
        "environment": "A cramped nineteen sixties university laboratory with a gray shock generator on a wooden desk",
        "action": action,
        "prop_change": prop,
        "reaction": reaction,
        "detail": "Bright daylight falls across the row of labelled switches",
    }


def _behavioral_plan() -> dict:
    press = "The porcelain teacher in a rolled-up white shirt presses a heavy toggle switch with a trembling hand"
    flash = "A red indicator light flashes and the voltmeter needle jumps across the dial"
    flinch = "His shoulders flinch and he twists in his chair toward the man in the gray lab coat behind him"
    shots = {r: _shot("S1", press, flash, flinch) for r in clip_roles(10)}
    for r in ("crisis", "step1", "step3"):
        shots[r] = _shot(
            "S2",
            "The porcelain experimenter in a gray lab coat taps his clipboard and lowers his pen toward the generator",
            "The pen clicks and a sheet of notes slides off the desk onto the floor",
            "The teacher clenches his fists on the desk and slumps forward",
        )
    return {
        "schema": 5,
        "visual_mode": "BEHAVIORAL_PSYCH",
        "dossier": "test_obedience",
        "must_have_scenes": [
            {"id": "S1", "title": "teacher presses the switch", "iconic": True, "recognition_hook": "the shock board",
             "key_visual": {"description": "the teacher presses a toggle switch on the generator",
                            "must_show": ["teacher", "switch|lever|toggle"]}},
            {"id": "S2", "title": "experimenter says please continue", "iconic": False},
        ],
        "shots": shots,
        "cast": {"subject": "teacher", "wardrobe": {"teacher": "a rolled-up white 1960s shirt",
                                                    "experimenter": "a gray lab coat"}},
    }


# ------------------------------------------------------------------ anatomy
def test_anatomy_resolution_and_invented_regions() -> None:
    assert resolve_region("vmPFC") == "ventromedial prefrontal cortex"
    assert resolve_region("occipital lobe") == "primary visual cortex"
    assert find_regions("the ventromedial prefrontal cortex and the amygdala")[:2] == [
        "ventromedial prefrontal cortex",
        "amygdala",
    ]
    assert region_named_in("hippocampus", "the memory maker deep in your head")
    assert _region_field_issue("compensatory_region", "cerebellar and amygdala associative synapse circuit")
    assert _region_field_issue("crisis_region", "white-matter tract to the amygdala") is None
    assert _region_field_issue("target_region", "fusiform face area") is None


# ------------------------------------------------------------ plain language
def test_tts_normalization_and_display_restore() -> None:
    spoken = to_tts_text("In 1848, Dr. Harlow saw a 13-pound rod (3.5 feet) — memory up 37%! Really?")
    assert not tts_issues(spoken)
    assert "eighteen forty-eight" in spoken and "thirty-seven percent" in spoken and "Doctor" in spoken
    assert to_display_text("in eighteen forty-eight memory rose thirty-seven percent") == "in 1848 memory rose 37%"
    assert to_display_text("In nineteen oh four, Pavlov won the Nobel Prize, yet three hundred seventy-four times.") == (
        "In 1904, Pavlov won the Nobel Prize, yet 374 times."
    )
    assert to_display_text("In two thousand nine, forty percent missed it, while twenty-six of forty pressed thirty switches to four hundred fifty volts.") == (
        "In 2009, 40% missed it, while 26 of 40 pressed 30 switches to 450 volts."
    )
    assert tts_issues("Wow! 37% of people (really)")


def test_jargon_and_readability_detection() -> None:
    jargon = find_jargon("A nonlinear MIMO model maps CA3 spikes to CA1 in the 1990s, patient seen with fMRI.")
    assert {"nonlinear", "MIMO", "CA3", "CA1", "fMRI"} <= set(jargon)
    assert "1990s" not in jargon
    assert fk_grade("The dog heard a click. Then it drooled.") < 4
    a = analyze_script(["Step one: signals enter the cortex.", "You see it."])
    assert a["robotic_openers"] == 1 and a["second_person_clips"] == 1


# --------------------------------------------------------------------- voice
def test_semitone_voice_gate() -> None:
    assert round(semitones(240.0, 120.0), 2) == 12.0
    ok = evaluate_f0_series([118, 120, 119, 121, 117, 120, 119, 118, 120, 121])
    assert ok["passed"] and ok["regenerate_clips"] == []
    bad = evaluate_f0_series([118, 121, 119, 140, 120, 117])
    assert not bad["passed"] and bad["regenerate_clips"] == [4]


# ------------------------------------------------------------------- builder
def test_v5_builder_routes_settings_by_mode_and_renders_v5_prompt() -> None:
    plan = _behavioral_plan()
    clips = build_flow_prompts(plan, NARRATIONS)
    assert all(c["setting"] == "real_env" for c in clips)
    assert all(c["schema_version"] == 5 and c["visual_mode"] == "BEHAVIORAL_PSYCH" for c in clips)
    assert clips[0]["scene_id"] == "S1"
    assert FLOW_MOTION_STYLE_V5 in clips[0]["prompt"]
    assert f"Voice: {FLOW_VOICE_PROMPT_DESCRIPTOR_V5}." in clips[0]["prompt"]
    assert clips[0]["prompt"].startswith(FLOW_PROMPT_PREFIX)
    assert validate_flow_prompts(clips, scene_words_max=95) == []
    wide = build_flow_prompts(plan, NARRATIONS, aspect="16:9")
    assert wide[0]["prompt"].startswith(flow_prompt_prefix("16:9")) and "16:9 horizontal" in wide[0]["prompt"]
    assert validate_flow_prompts(wide, scene_words_max=95) == []

    hybrid = {"visual_mode": "HYBRID"}
    assert [resolve_clip_setting(hybrid, r) for r in clip_roles(10)] == [MODE_ROLE_SETTINGS["HYBRID"][r] for r in clip_roles(10)]
    assert resolve_clip_setting({}, "pivot") == "brain_void"  # v4 unchanged


def test_v5_builder_requires_authored_reenactment() -> None:
    plan = _behavioral_plan()
    del plan["shots"]["symptom"]
    with pytest.raises(ValueError):
        build_flow_prompts(plan, NARRATIONS)


# ---------------------------------------------------------------- production gate
def test_production_gate_passes_good_behavioral_plan() -> None:
    plan = _behavioral_plan()
    assert validate_narrations(NARRATIONS) == []
    clips = build_flow_prompts(plan, NARRATIONS)
    assert validate_production_v5(plan, NARRATIONS, clips) == []


def test_production_gate_catches_static_acting_late_iconic_and_brain_in_behavioral() -> None:
    plan = _behavioral_plan()
    bad = copy.deepcopy(plan)
    bad["scenes"] = {
        "setup": (
            "A bright laboratory with a wooden desk and a gray machine. A porcelain teacher mannequin sits calmly at the "
            "desk while an experimenter mannequin stands nearby. Wide establishing shot, camera smoothly tracks forward "
            "toward the subject. Bright daylight lighting. The rest of the room glows in soft daylight."
        )
    }
    issues = validate_production_v5(bad, NARRATIONS, build_flow_prompts(bad, NARRATIONS))
    assert any(i.startswith("[acting] clip 1") for i in issues)

    late = copy.deepcopy(plan)
    for r in ("setup", "symptom"):
        late["shots"][r]["scene_id"] = "S2"
    issues = validate_production_v5(late, NARRATIONS, build_flow_prompts(late, NARRATIONS))
    assert any("iconic scene S1 must appear in clip 1-2" in i for i in issues)

    brainy = copy.deepcopy(plan)
    brainy["shots"]["pivot"]["setting"] = "brain_void"
    brainy["target_region"] = "amygdala"
    issues = validate_production_v5(brainy, NARRATIONS, build_flow_prompts(brainy, NARRATIONS))
    assert any(i.startswith("[brain]") for i in issues)

    assert check_action_physics("The porcelain man reaches toward the board with pleading gestures.")


def test_legacy_v4_project_prompts_fail_the_v5_gate() -> None:
    from pipeline.flow_prompt_builder import load_visual_plan
    from pipeline.topics_catalog import PSYCHOLOGY_TOPICS

    golden = next(t for t in PSYCHOLOGY_TOPICS if str(t.get("project_id", "")).startswith("psych_05"))
    narrations = [str(s) for s in golden["clip_narrations"]]
    plan = dict(load_visual_plan(topic_item=golden))
    clips = build_flow_prompts(plan, narrations)
    plan["visual_mode"] = "NEURO_BIOLOGY"
    issues = validate_production_v5(plan, narrations, clips)
    assert any(i.startswith("[scene]") for i in issues)
    assert any(i.startswith("[brain]") and "exceed" in i for i in issues)


# ------------------------------------------------------------------- dossier
def test_dossier_scaffold_validate_and_seed(tmp_path: Path) -> None:
    from pipeline.research_dossier import (
        DOSSIER_FILES,
        init_dossier,
        plan_seed_from_dossier,
        resolve_dossier_for_project,
        validate_dossier,
    )

    d = init_dossier("Test Topic", "Test Topic", pillar="brain_history", visual_mode="HYBRID", root=tmp_path)
    assert all((d / f).exists() for f in DOSSIER_FILES)
    res = validate_dossier(d)
    assert res["ready"] is False and res["checklist"]["primary_source"] is False
    vr = {
        "scenes": [
            {
                "id": "S1", "title": "the bell myth", "iconic": True, "shorts_priority": 1, "era": "1900s",
                "layout": {"description": "dog on a stand"}, "props": [{"name": "metronome"}],
                "actions": [{"who": "dog", "verb_sequence": "drools"}], "reactions": [{"who": "dog", "reaction": "licks"}],
                "recognition_hook": "the drooling dog",
                "key_visual": {
                    "description": "a porcelain dog on a wooden stand beside a ticking metronome",
                    "must_show": ["metronome", "stand"],
                    "source": "M1_test@00:05-00:15; SRC1",
                },
            }
        ]
    }
    (d / "03_visual_reference.json").write_text(json.dumps(vr), encoding="utf-8")
    meta = json.loads((d / "dossier.json").read_text(encoding="utf-8"))
    meta["linked_projects"] = ["psych_11_legacy_alias (legacy v4)"]
    (d / "dossier.json").write_text(json.dumps(meta), encoding="utf-8")
    assert validate_dossier(d)["checklist"]["iconic_scene"] is True
    seed = plan_seed_from_dossier(d)
    assert seed["visual_mode"] == "HYBRID" and seed["must_have_scenes"][0]["id"] == "S1"
    assert seed["must_have_scenes"][0]["key_visual"]["must_show"] == ["metronome", "stand"]
    assert resolve_dossier_for_project("psych_99_test_topic", root=tmp_path) == d
    assert resolve_dossier_for_project("psych_11_legacy_alias", root=tmp_path) == d


# ------------------------------------------------------------------- assets
def test_asset_manifest_and_library(tmp_path: Path) -> None:
    from pipeline.asset_manifest import build_asset_manifest, search_library, upsert_library
    from pipeline.flow_prompt_builder import write_flow_prompts_json

    proj = tmp_path / "psych_99_test"
    (proj / "05_assembly").mkdir(parents=True)
    plan = _behavioral_plan()
    (proj / "03_visuals").mkdir(parents=True)
    (proj / "03_visuals" / "visual_plan.json").write_text(json.dumps(plan), encoding="utf-8")
    write_flow_prompts_json(proj, build_flow_prompts(plan, NARRATIONS))
    (proj / "05_assembly" / "concat_list.txt").write_text(
        "file 'a.mp4'\ninpoint 0.3\noutpoint 8.1\nfile 'b.mp4'\ninpoint 0.2\noutpoint 7.0\n", encoding="utf-8"
    )
    m = build_asset_manifest(proj, write_library=False)
    assert len(m["assets"]) == 10
    assert m["assets"][0]["asset_id"] == "test_obedience_setup_cu"
    assert m["assets"][1]["used_in_short"]["timeline_start_sec"] == 7.8
    idx = tmp_path / "index.jsonl"
    upsert_library(m["assets"], idx)
    upsert_library(m["assets"], idx)  # idempotent
    assert len(idx.read_text(encoding="utf-8").splitlines()) == 10
    assert search_library("toggle switch", idx)


# --------------------------------------------------------------- tts fallback
@pytest.mark.skipif(
    not (Path(VOICE_FALLBACK_MODEL_DIR) / "kokoro-v1.0.onnx").exists(), reason="Kokoro model files not installed"
)
def test_kokoro_fallback_synthesizes_one_consistent_line(tmp_path: Path) -> None:
    from pipeline.voice_fallback import synthesize_line

    pcm = synthesize_line("The dog heard a click and started to drool.", sr=48000, cache_dir=tmp_path, clip_no=1)
    assert 1.0 < len(pcm) / 48000 < 6.0
    again = synthesize_line("The dog heard a click and started to drool.", sr=48000, cache_dir=tmp_path, clip_no=1)
    assert len(again) == len(pcm)  # cached


# --------------------------------------------------------------- reference image qa (R51)
def test_reference_image_specs_and_10axis_qa(tmp_path: Path) -> None:
    import cv2
    import numpy as np
    from pipeline.reference_image_qa import (
        build_reference_image_specs,
        inspect_reference_image_pack,
        write_reference_image_specs,
    )

    plan = _behavioral_plan()
    specs = build_reference_image_specs(plan, NARRATIONS)
    # env plate + 2 cast sheets + hero prop, 10 clip start frames + 1 key frame (first clip showing the switch press)
    assert len(specs["master_anchors"]) == 4
    assert len(specs["clip_anchors"]) == 11
    assert specs["total_reference_images"] == 15

    proj = tmp_path / "psych_ref_test"
    ref_dir = proj / "03_visuals" / "reference_images"
    ref_dir.mkdir(parents=True)
    (proj / "03_visuals" / "visual_plan.json").write_text(json.dumps(plan), encoding="utf-8")
    write_reference_image_specs(proj, specs)

    # Create synthetic high-key porcelain reference images with architectural grid lines + porcelain mannequin
    rng = np.random.default_rng(42)
    for idx, sp in enumerate(specs["all_specs"]):
        y_grid = np.linspace(110, 175, 1280, dtype=np.float32)[:, None, None]
        noise = cv2.GaussianBlur(rng.normal(0, 28, (1280, 720, 3)).astype(np.float32), (3, 3), 0.9)
        frame = np.clip(y_grid + noise, 30, 245).astype(np.uint8)
        # Draw architectural background panelling (y=80..1180) and desk/switch details so Canny edge_density >= 0.02
        for gx in range(80, 660, 48):
            cv2.line(frame, (gx, 90), (gx, 1180), (85, 85, 85), 2)
        for gy in range(100, 1180, 52):
            cv2.line(frame, (60, gy), (660, gy), (90, 90, 90), 2)
        # Keep top/bottom 5% margins smooth so Q7 (zero text/UI banner check) passes cleanly
        frame[:70, :] = 140
        frame[1210:, :] = 140
        # Draw distinct porcelain subject & prop geometry per shot so dHash differs across all 13 images
        cx = 90 + idx * 32
        cy = 240 + idx * 38
        cv2.rectangle(frame, (cx, cy), (cx + 180 + (idx % 3) * 25, cy + 420), (235, 235, 235), -1)
        cv2.circle(frame, (cx + 90, cy - 60), 50 + idx * 2, (240, 240, 240), -1)
        # Per-shot props at different positions so every keyframe is a distinct composition (dHash >= 6)
        prng = np.random.default_rng(1000 + idx)
        for _ in range(6):
            x0, y0 = int(prng.integers(60, 560)), int(prng.integers(120, 1050))
            shade = int(prng.integers(40, 120))
            cv2.rectangle(frame, (x0, y0), (x0 + int(prng.integers(40, 140)), y0 + int(prng.integers(40, 160))), (shade,) * 3, -1)
        cv2.imwrite(str(ref_dir / sp["filename"]), frame)

    from pipeline.reference_image_qa import register_reference_image, write_semantic_review_template

    rep = inspect_reference_image_pack(proj, save_report=True)
    assert rep["all_passed"] is False and rep["pre_generation_ready"] is False  # Q11 pending, provenance unknown

    review = write_semantic_review_template(proj, specs["all_specs"])
    data = json.loads(review.read_text(encoding="utf-8"))
    for item in data["images"].values():
        item["checks"] = {k: True for k in item["checks"]}
    review.write_text(json.dumps(data), encoding="utf-8")
    for sp in specs["all_specs"]:
        register_reference_image(proj, sp["filename"], "flow_image_generation")

    rep = inspect_reference_image_pack(proj, save_report=True)
    assert rep["sufficient_count_ok"] is True
    assert rep["all_passed"] is True
    assert rep["pre_generation_ready"] is True
    assert rep["reference_qa_score"] == 100.0
    assert rep["regenerate_image_ids"] == []
