"""R46-K / R51 / R52 / R44-D: key visual gate, still prompts, provenance, Q4 skin fix, packets, depth checks."""
from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np

from pipeline.config import CLIP_MAX_RENDER_SEC, FLOW_ALLOWED_DURATION_TARGETS
from pipeline.flow_prompt_builder import compute_clip_target_duration
from pipeline.reference_image_qa import (
    build_reference_image_specs,
    inspect_single_reference_image,
    register_reference_image,
    validate_semantic_review,
    write_semantic_review_template,
)
from pipeline.scene_blueprint import (
    build_generation_packets,
    key_visual_clip_numbers,
    key_visual_tokens_ok,
    still_frame_prompt,
    timed_video_prompt,
    validate_scene_blueprints,
)

KV = {"description": "the iron rod shoots up through the left cheek and out of the cranium",
      "must_show": ["iron|rod", "cheek", "cranium|skull"]}


def _plan(prop_change: str) -> dict:
    shots = {}
    from pipeline.config import clip_roles

    roles = list(clip_roles(5))
    for r in roles:
        shots[r] = {
            "scene_id": "S1" if r == "setup" else "S2",
            "setting": "real_env",
            "camera": "Wide shot slowly pushing in",
            "environment": "A granite rock cut beside a railroad grade in bright afternoon light",
            "action": "The porcelain foreman kneels over the drilled hole, turns his head, and tamps the iron bar down",
            "prop_change": prop_change if r == "setup" else "Dust lifts off the stone ledge",
            "reaction": "The two workman mannequins flinch and duck behind the cart",
        }
    return {
        "schema": 5,
        "visual_mode": "BEHAVIORAL_PSYCH",
        "cast": {"subject": "foreman", "wardrobe": {"foreman": "white linen shirtsleeves and a dark waistcoat"}},
        "must_have_scenes": [{"id": "S1", "title": "Blast", "iconic": True, "key_visual": KV},
                             {"id": "S2", "title": "After", "iconic": False}],
        "shots": shots,
        "real_environment": "a granite rock cut beside a railroad grade",
        "environment_props": ["a long tapered iron tamping bar"],
    }


def test_key_visual_detected_only_when_shown() -> None:
    hidden = [{"clip_number": 1, "scene_id": "S1", "scene": "He tamps the iron bar into the hole. Dust lifts."}]
    shown = [{"clip_number": 1, "scene_id": "S1", "scene": "The iron rod shoots up through his left cheek and out of his cranium."}]
    assert key_visual_tokens_ok(hidden[0]["scene"], KV) == ["cheek", "cranium|skull"]
    assert key_visual_clip_numbers({"must_have_scenes": [{"id": "S1", "key_visual": KV}]}, hidden) == {"S1": []}
    assert key_visual_clip_numbers({"must_have_scenes": [{"id": "S1", "key_visual": KV}]}, shown) == {"S1": [1]}


def test_still_prompt_is_a_single_instant_not_a_video() -> None:
    plan = _plan("The iron rod shoots up through his left cheek and out of his cranium")
    p = still_frame_prompt(plan, "setup", "start")
    assert "still photograph" in p and "video clip" not in p and "Voice:" not in p and "pushing in" not in p
    assert "white linen shirtsleeves" in p  # cast lock wording repeated
    key = still_frame_prompt(plan, "setup", "key")
    assert "cheek" in key and "cranium" in key


def test_timed_prompt_tts_mode_has_beats_and_no_speech() -> None:
    plan = _plan("The iron rod shoots up through his left cheek and out of his cranium")
    p = timed_video_prompt(plan, "setup", "In 1848 a foreman was hit.", voice_source="tts")
    assert "0-3s:" in p and "3-6s:" in p and "6-8s:" in p
    assert "no speech" in p and "Spoken narration" not in p
    assert "8-second" in p  # a start image is attached -> Omni / Gemini render 8 s


def test_packets_add_key_frame_and_chain_same_scene() -> None:
    plan = _plan("The iron rod shoots up through his left cheek and out of his cranium")
    narr = ["In 1848 a railroad foreman packed powder into a rock with a long iron bar near the town."] * 5
    packets = build_generation_packets(plan, narr, backend="flow")
    assert packets[0].get("key_frame") and packets[0]["end_frame"]["file"].endswith("_key.png")
    assert packets[1]["start_frame"]["mode"] == "reference_image"       # S1 -> S2: new scene
    assert packets[2]["start_frame"]["mode"] == "chain_previous_last_frame"  # S2 -> S2: chained


def test_reference_specs_order_cast_sheets_and_key_frame() -> None:
    plan = _plan("The iron rod shoots up through his left cheek and out of his cranium")
    narr = ["In 1848 a railroad foreman packed powder into a rock with a long iron bar near the town."] * 5
    specs = build_reference_image_specs(plan, narr)
    ids = [s["ref_id"] for s in specs["all_specs"]]
    assert ids[0] == "ref_env_master" and "ref_cast_foreman" in ids and "ref_clip_01_key" in ids
    assert all("video clip" not in s["prompt"] for s in specs["all_specs"])


def test_q4_rejects_human_skin_even_with_porcelain(tmp_path: Path) -> None:
    img = np.full((1280, 720, 3), 235, np.uint8)
    for y in range(0, 1280, 40):
        cv2.line(img, (0, y), (719, y), (90, 90, 90), 2)
    hsv_skin = np.uint8([[[11, 110, 170]]])
    skin_bgr = cv2.cvtColor(hsv_skin, cv2.COLOR_HSV2BGR)[0, 0].tolist()
    cv2.rectangle(img, (230, 220), (490, 600), skin_bgr, -1)  # a large skin-coloured face in the head zone
    p = tmp_path / "face.png"
    cv2.imwrite(str(p), img)
    rep = inspect_single_reference_image(p, {"ref_id": "x", "setting": "real_env"})
    assert rep["human_skin_ratio"] > 0.12
    assert "Q4_porcelain_cast_fidelity" in rep["failed_axes"]


def test_semantic_review_pending_then_pass(tmp_path: Path) -> None:
    specs = [{"ref_id": "ref_clip_01_key", "filename": "ref_clip_01_key.png", "setting": "real_env", "must_include": ["cheek"]}]
    (tmp_path / "03_visuals").mkdir()
    path = write_semantic_review_template(tmp_path, specs)
    assert validate_semantic_review(tmp_path, specs)["pending"] == ["ref_clip_01_key"]
    data = json.loads(path.read_text())
    data["images"]["ref_clip_01_key"]["checks"] = {k: True for k in data["images"]["ref_clip_01_key"]["checks"]}
    path.write_text(json.dumps(data))
    res = validate_semantic_review(tmp_path, specs)
    assert res["complete"] and not res["failed"]
    register_reference_image(tmp_path, "ref_clip_01_key.png", "extracted_from_clip")
    prov = json.loads((tmp_path / "03_visuals/reference_images/provenance.json").read_text())
    assert prov["ref_clip_01_key.png"] == "extracted_from_clip"


def test_blueprint_requires_key_visual_and_evidence() -> None:
    bp = {"cast_lock": [{"id": "a", "look": "b"}], "scenes": [
        {"scene_id": "S1", "iconic": True, "space": "room", "props": [{"name": "rod"}],
         "beats": [{"action": "x", "evidence": []}], "evidence": [], "key_visual": None}]}
    issues = " ".join(validate_scene_blueprints(bp))
    assert "key_visual" in issues and "no source" in issues and "media timecode" in issues


def test_omni_only_and_render_ceilings() -> None:
    from pipeline.config import ALLOWED_FLOW_MODELS, FLOW_ACTIVE_VIDEO_MODEL
    from pipeline.scene_blueprint import render_ceiling_sec

    assert FLOW_ACTIVE_VIDEO_MODEL == "Omni 1.1 Flash" and FLOW_ACTIVE_VIDEO_MODEL in ALLOWED_FLOW_MODELS
    assert FLOW_ALLOWED_DURATION_TARGETS == ("4s", "6s", "8s", "10s") and CLIP_MAX_RENDER_SEC == 10
    assert render_ceiling_sec("flow", has_reference=False) == 10
    assert render_ceiling_sec("flow", has_reference=True) == 8 and render_ceiling_sec("gemini_app") == 8
    assert compute_clip_target_duration("A short hook line.", role="setup")["target_duration"] in FLOW_ALLOWED_DURATION_TARGETS
