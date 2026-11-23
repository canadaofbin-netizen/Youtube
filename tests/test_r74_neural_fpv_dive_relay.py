"""
Unit tests for Rule R74:
3D Neural FPV Dive, Subcortical Macro Lock (`B0 <-> B1`), Arrival-Locked R71 Callouts & `-21.0 dBFS` Velvet Glass-Whoosh.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from pipeline import config as cfg
from pipeline.anatomy_label_overlay import resolve_anatomy_callout_windows
from pipeline.anatomy_map import resolve_anatomy_screen_anchor
from pipeline.diorama_assembler import _synthesize_expressive_v8_ambience_and_foley
from pipeline.flow_prompt_builder import build_flow_prompts, validate_expressive_v8_prompts
from pipeline.porcelain_anchor_pack import populate_expressive_v8_reference_contract
from pipeline.previs_blender import (
    find_blender_executable,
    is_blender_available,
    render_previs_keyframes,
    synthesize_default_previs_spec_for_clip,
)
from pipeline.prompt_quality_v5 import validate_production_diorama_v6


def _make_r74_lines() -> list[str]:
    return [
        "Why do you hate your own choice only when you can swap it later?",
        "To test this, Harvard psychologists had students print two favorite photos in a darkroom.",
        "Half had to pick one print for good right on the spot.",
        "The other half got five full days to swap their photo.",
        "Almost everyone picked the five-day swap deal without thinking twice.",
        "Everyone expects a backup option to bring peace of mind.",
        "Instead, the swap group liked their chosen photo way less!",
        "Wait, why does keeping an exit door open ruin what you picked?",
        "Inside your head, an open choice keeps your brain's conflict alarm — the anterior cingulate — wide awake.",
        "Each time they walked past the desk, they hunted for tiny flaws.",
        "Meanwhile, students stuck with a final choice felt way happier within two days.",
        "Once a door locks, your brain's satisfaction builder — the prefrontal cortex — goes to work.",
        "It highlights every good detail in the photo you already own.",
        "Endless return windows keep you stuck in buyer's remorse.",
        "Lock in small daily choices fast so your brain can start loving them.",
    ]


def test_r74_two_cycle_b0_b1_shared_video_frames_relay_and_validator(tmp_path: Path) -> None:
    """R74-1/R74-2: B0 -> B1_acc -> B0 -> B1_pfc binds exact shared Start/End VIDEO_FRAMES and blocks static-only brain plans."""
    lines = _make_r74_lines()
    script_doc: dict[str, Any] = {
        "schema_version": 8,
        "production_profile": "shorts_expressive_v8",
        "style_profile": "expressive_25d_v8",
        "voice_preset": "elevenlabs_v4",
        "opening_mode": "paradox_question",
        "ending_mode": "mic_drop",
        "r72_mode": True,
        "r73_mode": True,
        "r74_mode": True,
        "core_reveal_sentence_index": 9,
        "lines": lines,
        "script": " ".join(lines),
    }

    clips_in: list[dict[str, Any]] = []
    for i in range(24):
        c_num = i + 1
        s_idx = min(len(lines), (i * len(lines)) // 24 + 1)
        grammar = "expressive_vinyl_world"
        cam = "gentle_push_in"
        loc = f"harvard_room_{(i // 2) % 4}"
        b_reg = None
        trans = "daisy_chain_bridge"
        scene = "Student holds two framed silver prints over the oak tray as gloved fingers tap and ink eyes narrow."

        if c_num == 1:
            grammar = "expressive_hands_closeup"
            cam = "gentle_push_in"
            loc = "harvard_darkroom_tray"
        elif c_num == 2:
            grammar = "expressive_exterior_establishing"
            cam = "drone_aerial_approach"
            loc = "harvard_yard_aerial"
            trans = "seamless_relay_cut"
            scene = "High FPV drone sweeps over red brick Harvard towers and green lawn courtyard in crisp morning sun."
        elif c_num == 3:
            grammar = "architectural_cutaway_portal"
            cam = "fpv_window_portal_breach"
            loc = "harvard_memorial_cutaway"
            scene = "FPV drone glides through the tall arched window as brick facade slices open into the warm photography darkroom."
        elif c_num in (6, 8, 13, 16, 20, 23):
            grammar = "expressive_exterior_establishing"
            cam = "drone_high_orbit_drop" if c_num % 2 == 0 else "drone_skyline_pullback"
            loc = f"cambridge_quad_{c_num}"
            scene = "Fast FPV drone arcs above sunlit brick campus walkways as vinyl students carry framed prints across the quad."
        elif c_num == 10:
            # Cycle 1 Dive-In: B0 -> B1 (anterior cingulate cortex)
            s_idx = 9
            grammar = "expressive_xray_brain"
            cam = "neural_fpv_dive_in"
            loc = "brain_studio"
            b_reg = "anterior cingulate cortex"
            scene = (
                "Fast FPV macro probe plunges through frosted borosilicate crystal cortical folds into the central fissure "
                "until the glowing crimson-red crystal arch fills the frame."
            )
        elif c_num == 11:
            # Cycle 1 Macro Hold: B1 (anterior cingulate cortex)
            s_idx = 9
            grammar = "expressive_xray_brain"
            cam = "neural_macro_orbit_hold"
            loc = "brain_studio"
            b_reg = "anterior cingulate cortex"
            scene = (
                "Tight macro orbit holds right in front of the glowing crimson-red crystal cingulate arch as sharp "
                "amber-gold conflict pulses ripple across optical glass ribs."
            )
        elif c_num == 12:
            # Cycle 1 Pullback-Out: B1 -> B0
            s_idx = 10
            grammar = "expressive_xray_brain"
            cam = "neural_fpv_pullback_out"
            loc = "brain_studio"
            b_reg = "anterior cingulate cortex"
            scene = (
                "Rapid FPV reverse pullback rockets backward from the crimson crystal arch out through parted frosted "
                "cortical glass walls into the full luminous 3D glass brain."
            )
        elif c_num == 17:
            # Cycle 2 Dive-In: B0 -> B1 (prefrontal cortex)
            s_idx = 12
            grammar = "expressive_xray_brain"
            cam = "neural_fpv_dive_in"
            loc = "brain_studio"
            b_reg = "prefrontal cortex"
            scene = (
                "Fast FPV macro probe plunges straight through frosted crystal frontal folds until sculpted warm "
                "amber-gold prefrontal glass ridges fill the chamber."
            )
        elif c_num == 18:
            # Cycle 2 Pullback-Out: B1 -> B0
            s_idx = 13
            grammar = "expressive_xray_brain"
            cam = "neural_fpv_pullback_out"
            loc = "brain_studio"
            b_reg = "prefrontal cortex"
            scene = (
                "Rapid FPV reverse pullback glides out from the warm amber-gold prefrontal crystal ridges through "
                "frosted glass gyri back to the full 3D glass brain."
            )
        elif c_num == 21:
            grammar = "expressive_cameo_world"
            cam = "locked_tripod"
            loc = "harvard_dorm_desk"
            scene = "Student hangs one framed photo on the wall while a tiny 4cm Mini-Cortex figurine perches on the desk shelf nodding once."

        entry: dict[str, Any] = {
            "id": c_num,
            "clip_number": c_num,
            "sentence_index": s_idx,
            "act": min(6, (i * 6) // 24 + 1),
            "visual_grammar": grammar,
            "grammar": grammar,
            "camera": cam,
            "camera_move": cam,
            "location_id": loc,
            "cast_roles": [] if grammar == "expressive_xray_brain" else ["protagonist"],
            "cameo_easter_egg": c_num == 21,
            "transition_out": trans,
            "scene": scene,
        }
        if b_reg:
            entry["brain_region"] = b_reg
        clips_in.append(entry)

    plan: dict[str, Any] = {
        "project_id": "v8_ep07_test_r74",
        "schema_version": 8,
        "production_profile": "shorts_expressive_v8",
        "style_profile": "expressive_25d_v8",
        "opening_mode": "paradox_question",
        "ending_mode": "mic_drop",
        "r72_mode": True,
        "r73_mode": True,
        "r74_mode": True,
        "core_reveal_sentence_index": 9,
        "zero_clip_reuse": True,
        "real_world_targets": [
            {"target_id": "harvard_memorial_hall", "category": "institution", "query": "Memorial Hall Harvard University"},
            {"target_id": "harvard_square_street", "category": "urban_setting", "query": "Harvard Square Cambridge street"},
            {"target_id": "darkroom_enlarger_rig", "category": "scientific_apparatus", "query": "Photographic darkroom enlarger"},
        ],
        "thumbnail": {
            "profile": "in_skull_cutaway_split_v4",
            "top_split_label": "FINAL PICK",
            "bottom_split_label": "5 DAYS TO SWAP!",
            "in_skull_split_prompt": (
                "Bright high-key 50/50 vertical split of the same expressive young college student holding a framed photo, "
                "top half calm smiling with serene cool-cyan 3D glass brain cutaway, bottom half stressed frowning with "
                "fiery crimson-red 3D glass brain cutaway and bold red downward arrow."
            ),
            "cover_sentence_index": 1,
        },
        "clips": clips_in,
    }

    pdir = tmp_path / "v8_ep07_test_r74"
    (pdir / "02_script").mkdir(parents=True)
    (pdir / "03_visuals").mkdir(parents=True)

    populated = populate_expressive_v8_reference_contract(
        plan,
        project_dir=pdir,
        synthesize_scene_anchors=True,
        daisy_chain_keyframes=True,
    )
    ref_pack = {r["ref_id"]: r for r in populated["reference_anchors"]}

    assert "ref_brain_B0_wide_9x16" in ref_pack
    assert ref_pack["ref_brain_B0_wide_9x16"]["r74_relay_stage"] == "B0"
    assert "ref_brain_B1_anterior_cingulate_cortex_macro_9x16" in ref_pack
    assert "ref_brain_B1_prefrontal_cortex_macro_9x16" in ref_pack
    b1_acc = ref_pack["ref_brain_B1_anterior_cingulate_cortex_macro_9x16"]
    assert b1_acc["r74_relay_stage"] == "B1"
    assert b1_acc["is_r74_macro_anchor"] is True
    assert b1_acc["conditioned_on"] == ["ref_brain_B0_wide_9x16"]

    by_num = {int(c["clip_number"]): c for c in populated["clips"]}
    # Cycle 1 shared keyframe relay: B0 -> B1_acc -> B1_acc (hold) -> B1_acc -> B0/world
    assert by_num[10]["reference_image"] == "03_visuals/reference_images/ref_brain_B0_wide_9x16.png"
    assert by_num[10]["end_reference_image"] == "03_visuals/reference_images/ref_brain_B1_anterior_cingulate_cortex_macro_9x16.png"
    assert by_num[10]["dual_keyframe_parallax"] is True
    assert by_num[11]["reference_image"] == "03_visuals/reference_images/ref_brain_B1_anterior_cingulate_cortex_macro_9x16.png"
    assert by_num[11].get("end_reference_image") in (None, "")
    assert by_num[12]["reference_image"] == "03_visuals/reference_images/ref_brain_B1_anterior_cingulate_cortex_macro_9x16.png"
    assert by_num[12]["dual_keyframe_parallax"] is True
    assert by_num[12].get("end_reference_image")

    # Cycle 2 shared keyframe relay: B0 -> B1_pfc -> B0/world
    assert by_num[17]["reference_image"] == "03_visuals/reference_images/ref_brain_B0_wide_9x16.png"
    assert by_num[17]["end_reference_image"] == "03_visuals/reference_images/ref_brain_B1_prefrontal_cortex_macro_9x16.png"
    assert by_num[18]["reference_image"] == "03_visuals/reference_images/ref_brain_B1_prefrontal_cortex_macro_9x16.png"
    assert by_num[18].get("end_reference_image")

    built = build_flow_prompts(populated, lines)
    v8_issues = validate_expressive_v8_prompts(built, plan=populated)
    assert [x for x in v8_issues if "xray_timing_v8" in x or "r74" in x] == []
    d6_issues = validate_production_diorama_v6(populated, lines, built, script_doc=script_doc)
    r74_issues = [x for x in d6_issues if "[r74_neural_dive]" in x]
    assert r74_issues == [], f"Unexpected R74 validator issues: {r74_issues}"

    # Static-only brain plan must fail [r74_neural_dive]
    bad_plan = {
        **populated,
        "clips": [
            (
                {**c, "camera": "gentle_push_in", "camera_move": "gentle_push_in", "camera_movement": "gentle_push_in"}
                if c.get("grammar") == "expressive_xray_brain"
                else dict(c)
            )
            for c in populated["clips"]
        ],
    }
    bad_built = build_flow_prompts(bad_plan, lines)
    bad_issues = validate_production_diorama_v6(bad_plan, lines, bad_built, script_doc=script_doc)
    assert any("[r74_neural_dive]" in x for x in bad_issues)


def test_r74_previs_v23_cortical_glass_shell_and_subcortical_visibility(tmp_path: Path) -> None:
    """R74-2: Previs v2.3 renders 0.20-alpha cortical glass shell + collision-safe subcortical target across regions."""
    for idx, region in enumerate(("hippocampus", "amygdala", "prefrontal cortex"), start=1):
        clip_spec = {
            "clip_number": idx,
            "grammar": "expressive_xray_brain",
            "visual_grammar": "expressive_xray_brain",
            "camera_move": "neural_fpv_dive_in",
            "brain_region": region,
            "scene": f"Fast FPV macro probe plunges into the translucent crystal brain toward the {region}.",
        }
        pv_spec = synthesize_default_previs_spec_for_clip(clip_spec, idx)
        assert pv_spec["neural_cutaway_stage"] is True
        assert pv_spec["r74_brain_region"] == region
        block_ids = {b["block_id"] for b in pv_spec["room_blocks"]}
        assert "cortical_glass_shell" in block_ids

        res_cpu = render_previs_keyframes(
            pv_spec,
            out_dir=tmp_path / f"cpu_{idx}",
            cut_id=f"R74_{idx:02d}",
            backend="workbench_cpu",
        )
        assert Path(res_cpu["start_png"]).is_file()
        assert Path(res_cpu["end_png"]).is_file()
        assert res_cpu["visibility_gate_start"]["passed"] is True
        assert res_cpu["visibility_gate_end"]["passed"] is True

    b_exe = find_blender_executable()
    if b_exe is not None and is_blender_available(b_exe):
        pv_hippo = synthesize_default_previs_spec_for_clip(
            {
                "clip_number": 99,
                "grammar": "expressive_xray_brain",
                "camera_move": "neural_fpv_dive_in",
                "brain_region": "hippocampus",
                "scene": "Fast FPV macro probe plunges into the translucent crystal brain toward the hippocampus.",
            },
            99,
        )
        res_bl = render_previs_keyframes(
            pv_hippo,
            out_dir=tmp_path / "blender_hippo",
            cut_id="R74_BL_HIPPO",
            backend="blender",
        )
        assert res_bl["backend_used"] == "blender"
        assert res_bl["visibility_gate_start"]["passed"] is True
        assert res_bl["visibility_gate_end"]["passed"] is True


def test_r74_arrival_locked_macro_callouts_and_pullback_suppression() -> None:
    """R74-3: R71 callouts defer to paired macro hold (or lock >=1.25s on standalone dive) and suppress on pullback."""
    macro_hippo = resolve_anatomy_screen_anchor("hippocampus", macro_mode=True)
    wide_hippo = resolve_anatomy_screen_anchor("hippocampus", macro_mode=False)
    assert macro_hippo is not None and wide_hippo is not None
    assert macro_hippo["anchor_xy"] == macro_hippo["macro_anchor_xy"]
    assert wide_hippo["anchor_xy"] != macro_hippo["anchor_xy"]

    edl = {
        "cuts": [
            # Cut 1 (Dive-In paired with Cut 2 Macro Hold on hippocampus -> deferred to Cut 2!)
            {
                "cut_index": 1,
                "clip_index": 1,
                "grammar": "expressive_xray_brain",
                "camera_move": "neural_fpv_dive_in",
                "brain_region": "hippocampus",
                "out_start_sec": 10.0,
                "out_end_sec": 12.4,
            },
            # Cut 2 (Steady Macro Hold -> receives macro callout immediately at 12.4 + 0.18s)
            {
                "cut_index": 2,
                "clip_index": 2,
                "grammar": "expressive_xray_brain",
                "camera_move": "neural_macro_orbit_hold",
                "brain_region": "hippocampus",
                "out_start_sec": 12.4,
                "out_end_sec": 14.8,
            },
            # Cut 3 (Pullback-Out -> callout completely suppressed!)
            {
                "cut_index": 3,
                "clip_index": 3,
                "grammar": "expressive_xray_brain",
                "camera_move": "neural_fpv_pullback_out",
                "brain_region": "hippocampus",
                "out_start_sec": 14.8,
                "out_end_sec": 17.0,
            },
            # Cut 4 (Standalone Dive-In on prefrontal cortex without hold -> arrival-locked at >= +1.25s!)
            {
                "cut_index": 4,
                "clip_index": 4,
                "grammar": "expressive_xray_brain",
                "camera_move": "neural_fpv_dive_in",
                "brain_region": "prefrontal cortex",
                "out_start_sec": 24.0,
                "out_end_sec": 26.5,
            },
        ]
    }
    windows = resolve_anatomy_callout_windows(edl)
    by_cut = {w["cut_index"]: w for w in windows}
    assert 1 not in by_cut, "Dive-in paired with macro hold should defer callout to macro hold cut"
    assert 3 not in by_cut, "Pullback-out must suppress callout ink completely"
    assert 2 in by_cut
    assert abs(by_cut[2]["start_sec"] - 12.58) < 1e-3
    assert tuple(by_cut[2]["anchor_xy"]) == macro_hippo["macro_anchor_xy"]
    assert 4 in by_cut
    assert by_cut[4]["start_sec"] >= 24.0 + 1.25 - 1e-6


def test_r74_velvet_whoosh_synthesis_and_frozen_ep1_to_ep6_exemption() -> None:
    """R74-3/R74-4: Synthesizes -21.0 dBFS 0.36s velvet glass-whoosh and exempts frozen Ep #1..#6 archives."""
    sr = 24000
    n_samples = sr * 8
    edl: dict[str, Any] = {
        "style_profile": "expressive_25d_v8",
        "bgm_mode": "room_tone",
        "cuts": [
            {"cut_index": 1, "camera_move": "gentle_push_in", "out_start_sec": 0.0, "out_end_sec": 2.2},
            {"cut_index": 2, "camera_move": "neural_fpv_dive_in", "out_start_sec": 2.2, "out_end_sec": 4.6},
            {"cut_index": 3, "camera_move": "neural_fpv_pullback_out", "out_start_sec": 4.6, "out_end_sec": 6.8},
        ],
    }
    st = _synthesize_expressive_v8_ambience_and_foley(n_samples, sr, speech_end_sec=7.5, edl=edl)
    assert st.shape == (n_samples, 2)
    assert np.isfinite(st).all()
    events = edl.get("neural_whoosh_events") or []
    assert len(events) == 2
    assert [e["camera_move"] for e in events] == ["neural_fpv_dive_in", "neural_fpv_pullback_out"]
    for ev in events:
        assert abs(ev["duration_sec"] - cfg.NEURAL_WHOOSH_DURATION_SEC) < 0.02
        assert ev["gain_dbfs"] == cfg.NEURAL_WHOOSH_GAIN_DB

    for frozen_pid in cfg.PRE_R74_FROZEN_V8_PROJECTS:
        assert cfg.is_r74_neural_dive_v8_plan({"project_id": frozen_pid}, project_id=frozen_pid) is False
    assert cfg.is_r74_neural_dive_v8_plan(
        {"project_id": "v8_ep07_harvard_reversible_choice_paradox"},
        project_id="v8_ep07_harvard_reversible_choice_paradox",
    ) is True
