"""
Rule R76 & R76-P Regression Suite:
  - Solo `Siren` (`eXpIbVcVbLo8ZJQDlDnl`) narrator lock & `Mini-Cortex` cameo retirement
  - Frozen `PRE_R76_FROZEN_V8_PROJECTS` preservation (`Ep #1..#8 v1`)
  - MNI152 3D neuroanatomy atlas (`36` regions incl. `eyes` & `inner ear`, `12` tracts)
  - Real `Blender 4.2` deterministic brain simulator render (`SQ1..SQ6` + `0.0 px` `camera_track.json` live overlay)
  - `Rule R76-P` Anti-Noise Pacing (`15–22` cuts, `>=2.80s` human / `>=3.80s` brain / `<=6.50s` max, `38–48%` unified brain share, `0` mid-sentence splits)
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

import pipeline.config as cfg
from pipeline.anatomy_label_overlay import (
    _interpolate_track_xy,
    render_anatomy_callout_rgba_frame,
    resolve_anatomy_callout_windows,
)
from pipeline.brain_simulator_blender import (
    ATLAS_MANIFEST_PATH,
    ATLAS_NPZ_PATH,
    render_brain_simulator_clip,
)
from pipeline.elevenlabs_tts import DEFAULT_CAST_REGISTRY, FEMALE_FALLBACK_VOICE_CHAIN
from pipeline.prompt_quality_v5 import validate_r76_brain_simulator_and_pacing_contract


ROOT = cfg.WORKSPACE_ROOT


def test_r76_solo_siren_narrator_and_cast_registry_lock() -> None:
    assert cfg.ELEVENLABS_VOICE_SIREN_ID == "eXpIbVcVbLo8ZJQDlDnl"
    assert cfg.EXPRESSIVE_V8_R76_VOICE_PRESET == "el_siren_v4"
    assert cfg.EXPRESSIVE_V8_FOIL_SENTENCE_RANGE == (0, 0)
    assert cfg.EXPRESSIVE_V8_REQUIRE_FOIL is False
    assert cfg.EXPRESSIVE_V8_CAMEO_COUNT_PER_EPISODE == 0
    assert DEFAULT_CAST_REGISTRY["cast"]["narrator"]["elevenlabs_voice_id"] == cfg.ELEVENLABS_VOICE_SIREN_ID
    assert DEFAULT_CAST_REGISTRY["cast"]["narrator"]["voice_preset"] == cfg.EXPRESSIVE_V8_R76_VOICE_PRESET
    assert "Siren" in DEFAULT_CAST_REGISTRY["cast"]["narrator"]["display_name"]
    assert FEMALE_FALLBACK_VOICE_CHAIN[0] == cfg.ELEVENLABS_VOICE_SIREN_ID

    cast_path = cfg.CHANNEL_ROOT / "knowledge_base" / "reusable_packs" / "cast_registry.json"
    cast_doc = json.loads(cast_path.read_text(encoding="utf-8"))
    assert cast_doc["cast"]["narrator"]["elevenlabs_voice_id"] == cfg.ELEVENLABS_VOICE_SIREN_ID
    assert "Siren" in cast_doc["cast"]["narrator"]["display_name"]


def test_r76_plan_activation_and_frozen_exemptions() -> None:
    assert "v8_ep08_capgras_imposter_delusion" in cfg.PRE_R76_FROZEN_V8_PROJECTS
    for pid in cfg.PRE_R76_FROZEN_V8_PROJECTS:
        assert cfg.is_r76_v8_plan({"schema": 8, "style_profile": "expressive_25d_v8"}, project_id=pid) is False

    assert cfg.is_r76_v8_plan({"schema": 8}, project_id="v8_ep08_capgras_imposter_delusion_r76") is True
    assert cfg.is_r76_v8_plan({"schema": 8}, project_id="v8_ep09_future_episode") is False
    assert cfg.is_r76_v8_plan({"schema": 8, "r76_mode": True}, project_id="v8_ep09_future_episode") is True
    assert cfg.is_r76_v8_plan({"r76_mode": True}) is True
    assert cfg.is_r76_v8_plan({"clips": [{"grammar": "brain_simulator_3d"}]}) is True


def test_r76_mni152_atlas_bounds_and_ap_orientation() -> None:
    assert ATLAS_MANIFEST_PATH.is_file(), f"Missing {ATLAS_MANIFEST_PATH}"
    assert ATLAS_NPZ_PATH.is_file(), f"Missing {ATLAS_NPZ_PATH}"
    mf = json.loads(ATLAS_MANIFEST_PATH.read_text(encoding="utf-8"))
    regions = mf["regions"]
    tracts = mf["tracts"]
    assert len(regions) >= 36
    for req in (
        "eyes",
        "inner ear",
        "primary visual cortex",
        "fusiform face area",
        "amygdala",
        "auditory cortex",
        "prefrontal cortex",
    ):
        assert req in regions, f"Missing atlas region {req}"
    assert len(tracts) >= 12
    assert mf["verification"]["anterior_posterior_order_ok"] is True

    # Sensory eyes must be strictly anterior (larger +Y in MNI) to primary visual cortex
    assert regions["eyes"]["centroid_mni"][1] > regions["primary visual cortex"]["centroid_mni"][1] + 80.0


def test_r76_blender_render_sq_and_live_camera_track_overlay(tmp_path: Path) -> None:
    out_mp4 = tmp_path / "brain_simulator_clips" / "clip_3.mp4"
    res = render_brain_simulator_clip(
        {
            "start_brain_region": "fusiform face area",
            "end_brain_region": "amygdala",
            "neural_state": "severed",
            "camera_move": "circuit_cooperation_drone",
            "duration_sec": 3.8,
        },
        out_mp4,
        timeout_sec=300,
    )
    assert out_mp4.is_file()
    sim_qa = res["sim_qa"]
    assert sim_qa["passed"] is True, f"SQ failure: {sim_qa}"
    for gate_name in (
        "SQ1_genuine_atlas_meshes",
        "SQ2_head_and_cortex_context",
        "SQ3_tract_connectivity",
        "SQ4_viewport_safe_framing",
        "SQ5_smooth_drone_motion",
        "SQ6_zero_glow_clinical_exposure",
    ):
        assert sim_qa["gates"][gate_name] is True, f"{gate_name} failed: {sim_qa}"

    track_path = Path(res["camera_track_path"])
    assert track_path.is_file()
    track = json.loads(track_path.read_text(encoding="utf-8"))
    frames = track["frames"]
    assert len(frames) >= 110
    assert frames[0]["anchors"]["start"]["x_norm"] < frames[0]["anchors"]["end"]["x_norm"]
    assert frames[-1]["anchors"]["start"]["x_norm"] < frames[-1]["anchors"]["end"]["x_norm"]

    edl = {
        "schema": 8,
        "cuts": [
            {
                "cut_index": 1,
                "clip_index": 3,
                "sentence_index": 3,
                "out_start_sec": 0.0,
                "out_end_sec": 3.8,
                "duration_sec": 3.8,
                "src_start_sec": 0.0,
                "src_end_sec": 3.8,
                "main_speed": 1.0,
                "grammar": "brain_simulator_3d",
                "render_engine": "blender_3d_simulator",
                "camera_move": "circuit_cooperation_drone",
                "start_brain_region": "fusiform face area",
                "end_brain_region": "amygdala",
                "callout_mode": "pathway_severed",
                "neural_state": "severed",
                "brain_region": "fusiform face area",
            }
        ],
    }
    windows = resolve_anatomy_callout_windows(
        edl,
        None,
        visuals_dir=tmp_path,
    )
    assert len(windows) == 1
    w0 = windows[0]
    assert w0.get("camera_track") is not None
    assert len(w0["camera_track"]["frames"]) == len(frames)
    pt0 = _interpolate_track_xy(w0["camera_track"], "start", 0.0, 1080, 1920)
    assert pt0 is not None
    assert abs(pt0[0] - frames[0]["anchors"]["start"]["x_px"]) < 0.2
    assert abs(pt0[1] - frames[0]["anchors"]["start"]["y_px"]) < 0.2
    rgba_img = render_anatomy_callout_rgba_frame(w0, 1.9, 3.8, width=1080, height=1920)
    rgba = np.asarray(rgba_img)
    assert rgba.shape == (1920, 1080, 4)
    assert int(np.count_nonzero(rgba[:, :, 3] > 20)) > 1500


def test_r76_validator_anti_noise_pacing_and_doc_sync() -> None:
    clips = []
    cuts = []
    t_cur = 0.0
    for i in range(1, 18):
        is_brain = i in (4, 6, 8, 9, 12, 13, 16)
        dur = 4.2 if is_brain else 3.8
        c = {
            "clip_number": i,
            "sentence_index": i,
            "grammar": "brain_simulator_3d" if is_brain else ("expressive_exterior_establishing" if i in (2, 5, 10) else "expressive_vinyl_world"),
            "render_engine": "blender_3d_simulator" if is_brain else "google_flow",
            "camera_move": "circuit_cooperation_drone" if is_brain else "gentle_push_in",
            "cameo_easter_egg": False,
        }
        if is_brain:
            c["start_brain_region"] = "fusiform face area"
            c["end_brain_region"] = "amygdala"
            c["neural_state"] = "severed" if i == 8 else "active"
            c["callout_mode"] = "pathway_severed" if i == 8 else "pathway_relay"
        clips.append(c)
        cuts.append(
            {
                "cut_index": i,
                "clip_index": i,
                "sentence_index": i,
                "out_start_sec": t_cur,
                "out_end_sec": t_cur + dur,
                "duration_sec": dur,
                "grammar": c["grammar"],
                "render_engine": c["render_engine"],
            }
        )
        t_cur += dur

    script_doc = {
        "schema": 8,
        "r76_mode": True,
        "voice_preset": "el_siren_v4",
        "sentence_speakers": ["narrator"] * 17,
        "foil_sentence_indices": [],
    }
    plan = {"schema": 8, "r76_mode": True, "clips": clips}
    edl = {"schema": 8, "total_duration_sec": t_cur, "cuts": cuts}

    ok_issues = validate_r76_brain_simulator_and_pacing_contract(plan, clips, script_doc=script_doc, edl=edl)
    assert ok_issues == [], f"Unexpected R76 issues: {ok_issues}"

    # Cameo, Flow X-ray, short human cut, and foil speaker must all be rejected
    bad_clips = [dict(c) for c in clips]
    bad_clips[0]["cameo_easter_egg"] = True
    bad_clips[3]["grammar"] = "expressive_xray_brain"
    bad_cuts = [dict(ct) for ct in cuts]
    bad_cuts[0]["duration_sec"] = 2.10
    bad_script = {**script_doc, "sentence_speakers": ["narrator"] * 16 + ["foil"]}
    bad_issues = validate_r76_brain_simulator_and_pacing_contract(
        plan, bad_clips, script_doc=bad_script, edl={"cuts": bad_cuts}
    )
    joined = "\n".join(bad_issues)
    assert "cameo" in joined.lower()
    assert "expressive_xray_brain" in joined
    assert "solo siren" in joined.lower()
    assert "human floor" in joined.lower()

    # Documentation sync checks
    constants_md = (ROOT / ".agents" / "rules" / "production_constants.md").read_text(encoding="utf-8")
    rules_md = "\n".join(
        (ROOT / ".agents" / "rules" / fn).read_text(encoding="utf-8")
        for fn in (
            "hook_pacing_beatcard_rules.md",
            "arrows_callouts_motion_rules.md",
            "diorama_assembly_subtitles_rules.md",
            "real_world_drone_refs_rules.md",
            "_archive/retired_rules_2026-11-18.md",
        )
    )
    agents_md = (ROOT / ".agents" / "AGENTS.md").read_text(encoding="utf-8")
    for tok in (
        "ELEVENLABS_VOICE_SIREN_ID",
        "EXPRESSIVE_V8_UNIFIED_BRAIN_SIM_DURATION_RATIO_RANGE",
        "EXPRESSIVE_V8_R76_HUMAN_MIN_CUT_SEC",
        "EXPRESSIVE_V8_R76_BRAIN_SIM_MIN_CUT_SEC",
        "EXPRESSIVE_V8_CAMEO_COUNT_PER_EPISODE",
        "PRE_R76_FROZEN_V8_PROJECTS",
    ):
        assert tok in constants_md, f"Missing {tok} in production_constants.md"
    assert "## R76 / R76-P" in rules_md
    assert "R76" in agents_md and len(agents_md.splitlines()) <= 60
