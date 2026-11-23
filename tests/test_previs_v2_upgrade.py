"""
Unit & integration tests for `3D Previs v2` (`P1–P6`):
  - P1: Real Blender 4.2 LTS batch Workbench execution + translucent `0.22` alpha `observation_glass_frame` + gaze visor + floor grid
  - P2: `9:16` vertical HFOV camera frustum solver (`solve_9x16_camera_frustum`) + `evaluate_previs_visibility_gate` auto-pullback
  - P3: Episode-wide `Role-Color Lock`, plural cast expansion (`"two neurologists"`), and compound prop silhouettes (`snake_terrarium`, `mask_tube`, `robot_arm`)
  - P4 & P6: Hybrid `6..10` hero Previs anchors (`daisy_chain_keyframes=False`) + `3..5` `Start+End` `VIDEO_FRAMES` `dual_keyframe_parallax` cuts
  - P5: `inspect_single_reference_image` `E7_previs_conformance` (`IoU`) + `E7_zero_previs_color_leak`
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from pipeline import porcelain_anchor_pack as pap
from pipeline import previs_blender as pb
from pipeline import reference_image_qa as rqa


def test_p1_real_blender42_batch_pack_and_translucent_observation_glass(tmp_path: Path) -> None:
    b_exe = pb.find_blender_executable()
    assert b_exe is not None and pb.is_blender_available(b_exe), f"Blender 4.2 LTS must be runnable, got {b_exe}"

    plan = {
        "style_profile": "expressive_25d_v8",
        "clips": [
            {
                "clip_number": 7,
                "scene_id": "S07",
                "act": 3,
                "grammar": "expressive_vinyl_world",
                "camera_move": "slow_push_in",
                "location_id": "iowa_co2_lab",
                "environment": "clinical CO2 respiratory lab with clear observation window and twin monitors",
                "cast": "two neurologists in white lab coats behind the observation window watching Patient S.M. in a teal cardigan",
                "action": "holds a clear breathing mask connected to a corrugated tube",
            }
        ],
    }
    pb.auto_synthesize_plan_previs_specs(plan, overwrite=True)
    pv = plan["clips"][0]["previs"]
    # Verify plural split produced >= 3 actors (2 neurologists + Patient S.M.)
    assert len(pv["actors"]) >= 3

    # Place an explicit observation_glass_frame directly between camera and neurologists to verify 0.22 alpha translucency
    pv["props"].append(
        {
            "prop_id": "observation_glass_frame",
            "pos_start": [0.0, -0.35, 0.90],
            "pos_end": [0.0, -0.35, 0.90],
            "size_xyz": [1.80, 0.04, 0.95],
            "color_hex": "#5C6B73",
            "color_name": "Slate Steel",
            "alpha": 0.22,
        }
    )

    res = pb.render_visual_plan_previs_pack(
        plan,
        tmp_path / "pv_batch",
        width=270,
        height=480,
        backend="blender",
    )
    assert res["backend_used"] == "blender"
    assert res["rendered_count"] == 1
    start_png = Path(plan["clips"][0]["previs"]["start_previs_png"])
    assert start_png.exists() and start_png.stat().st_size > 2000
    img = cv2.imread(str(start_png))
    assert img is not None and img.shape == (480, 270, 3)

    # Verify the glass region is NOT an opaque flat grey concrete wall (saturation & color variance from actors behind glass)
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    center_band = hsv[140:340, 45:225]
    high_sat_behind_glass = float(np.mean(center_band[:, :, 1] >= 48))
    assert high_sat_behind_glass >= 0.03, f"Actors behind translucent observation glass must remain visible, got sat ratio {high_sat_behind_glass}"


def test_p2_9x16_camera_frustum_solver_and_visibility_gate_pullback() -> None:
    actors = [
        {"role_id": "neurologist_1", "pos_start": [-0.72, 0.15, 0.0], "pos_end": [-0.72, 0.15, 0.0], "height_m": 1.72, "color_hex": "#7B2CBF"},
        {"role_id": "patient_sm", "pos_start": [0.72, 0.15, 0.0], "pos_end": [0.72, 0.15, 0.0], "height_m": 1.66, "color_hex": "#4F772D"},
    ]
    props = [
        {"prop_id": "snake_terrarium", "pos_start": [0.0, -0.05, 0.78], "pos_end": [0.0, -0.05, 0.78], "size_xyz": [0.52, 0.34, 0.34], "color_hex": "#C77D3B"}
    ]
    base_cam = {"pos": [0.0, -1.65, 1.35], "look_at": [0.0, 0.15, 1.15], "fov_deg": 46.0}
    cam_start = pb.solve_9x16_camera_frustum(base_cam, actors, props, phase="start", grammar="expressive_vinyl_world")
    cam_end = pb.solve_9x16_camera_frustum(base_cam, actors, props, phase="end", grammar="expressive_vinyl_world")
    spec = {
        "camera_start": cam_start,
        "camera_end": cam_end,
        "actors": actors,
        "props": props,
        "room_shell": {"width": 4.2, "depth": 4.6, "height": 3.0},
    }
    frm = pb._render_workbench_cpu_frame(spec, phase="start", width=270, height=480)
    gate = pb.evaluate_previs_visibility_gate(frm, spec)
    assert gate["passed"] is True, gate

    # Intentionally over-tight camera clipping side actors -> _pullback_camera_spec rescues visibility
    tight_spec = dict(
        spec,
        camera_start={"pos": [0.0, -1.05, 1.35], "look_at": [0.0, 0.15, 1.25], "fov_deg": 28.0},
    )
    frm_tight = pb._render_workbench_cpu_frame(tight_spec, phase="start", width=270, height=480)
    gate_tight = pb.evaluate_previs_visibility_gate(frm_tight, tight_spec)
    assert gate_tight["passed"] is False
    pulled = dict(tight_spec)
    for _ in range(3):
        pulled["camera_start"] = pb._pullback_camera_spec(pulled["camera_start"])
    frm_rescued = pb._render_workbench_cpu_frame(pulled, phase="start", width=270, height=480)
    gate_rescued = pb.evaluate_previs_visibility_gate(frm_rescued, pulled)
    assert gate_rescued["passed"] is True, gate_rescued


def test_p3_episode_role_color_lock_plural_cast_and_compound_props() -> None:
    plan = {
        "style_profile": "expressive_25d_v8",
        "clips": [
            {
                "clip_number": 1,
                "scene_id": "S01",
                "act": 1,
                "grammar": "expressive_vinyl_world",
                "camera_move": "dolly_zoom_vertigo",
                "cast": "a neurologist in a white lab coat and Patient S.M. in a warm teal cardigan",
                "action": "lifts a green snake above the glass terrarium toward Patient S.M.'s hands",
            },
            {
                "clip_number": 2,
                "scene_id": "S02",
                "act": 1,
                "grammar": "expressive_vinyl_world",
                "camera_move": "slow_push_in",
                "cast": "Patient S.M. in a warm teal cardigan",
                "action": "cradles the green snake above the glass terrarium with calm curiosity",
            },
            {
                "clip_number": 8,
                "scene_id": "S08",
                "act": 4,
                "grammar": "expressive_vinyl_world",
                "camera_move": "crash_zoom_reaction",
                "cast": "two neurologists in white lab coats and Patient S.M. in a warm teal cardigan",
                "action": "inhales one breath through the clear CO2 breathing mask and corrugated tube beside a robotic arm",
            },
        ],
    }
    pb.auto_synthesize_plan_previs_specs(plan, overwrite=True)

    s01_actors = {a["role_id"]: a["color_hex"] for a in plan["clips"][0]["previs"]["actors"]}
    s02_actors = {a["role_id"]: a["color_hex"] for a in plan["clips"][1]["previs"]["actors"]}
    s08_actors = plan["clips"][2]["previs"]["actors"]

    # Patient S.M. keeps exact locked color across S01 (2nd listed) and S02 (1st listed)!
    sm_roles_s01 = [rid for rid in s01_actors if "patient" in rid or "sm" in rid]
    sm_roles_s02 = [rid for rid in s02_actors if "patient" in rid or "sm" in rid]
    assert sm_roles_s01 and sm_roles_s02
    assert s01_actors[sm_roles_s01[0]] == s02_actors[sm_roles_s02[0]]

    # Plural "two neurologists" expands into two distinct neurologist actors + Patient S.M.
    assert len(s08_actors) >= 3

    # Compound props extracted & decomposed into multi-box silhouettes
    s08_prop_ids = [p["prop_id"] for p in plan["clips"][2]["previs"]["props"]]
    assert any("mask" in pid for pid in s08_prop_ids)
    prims = pb.build_prop_primitives(plan["clips"][2]["previs"]["props"][0], phase="start")
    assert len(prims) >= 2


def test_p4_and_p6_hybrid_hero_previs_anchors_and_dual_keyframe_parallax(tmp_path: Path) -> None:
    p_dir = tmp_path / "v8_ep_hybrid"
    (p_dir / "03_visuals").mkdir(parents=True, exist_ok=True)

    moves = [
        "dolly_zoom_vertigo", "slow_push_in", "lateral_truck_parallax", "static_locked",
        "orbital_arc_35", "slow_push_in", "static_locked", "crash_zoom_reaction",
        "fpv_aperture_push", "slow_pull_back", "static_locked", "orbital_arc_right",
        "slow_push_in", "lateral_truck_left", "dolly_in_reveal", "static_locked",
        "slow_push_in", "lateral_truck_parallax", "slow_pull_back", "static_locked",
    ]
    clips = []
    for idx, mv in enumerate(moves, start=1):
        clips.append(
            {
                "clip_number": idx,
                "sentence_index": idx,
                "end_sentence_index": idx,
                "act": min(6, ((idx - 1) // 4) + 1),
                "scene_id": f"S{idx:02d}",
                "grammar": "expressive_xray_brain" if idx in (6, 15) else ("outro_sky_card" if idx == 20 else "expressive_vinyl_world"),
                "camera_move": mv,
                "location_id": "lab_a" if idx <= 10 else "lab_b",
                "environment": "bright neurology lab with glass instruments",
                "cast": "a neurologist in a white lab coat and volunteer in a navy sweater",
                "action": "presses the brass response switch on the desk",
                "consequence": "2D charcoal ink eyes widen in surprise",
            }
        )

    plan = {
        "schema": 8,
        "style_profile": "expressive_25d_v8",
        "daisy_chain_keyframes": False,
        "hybrid_previs_v8": True,
        "enable_dual_keyframe_parallax": True,
        "core_reveal_sentence_index": 15,
        "clips": clips,
    }
    pb.auto_synthesize_plan_previs_specs(plan, overwrite=True)
    pb.render_visual_plan_previs_pack(plan, p_dir / "03_visuals" / "previs", width=180, height=320, backend="workbench_cpu")

    pap.populate_expressive_v8_reference_contract(
        plan,
        project_dir=p_dir,
        synthesize_scene_anchors=True,
    )

    ref_ancs = plan.get("reference_anchors") or []
    start_kfs = [r for r in ref_ancs if str(r.get("ref_id") or "").endswith("_pv_start_9x16")]
    end_kfs = [r for r in ref_ancs if str(r.get("ref_id") or "").endswith("_pv_end_9x16")]
    assert 6 <= len(start_kfs) <= 10, f"Expected 6..10 hybrid hero start keyframes, got {len(start_kfs)}"
    assert 3 <= len(end_kfs) <= 5, f"Expected 3..5 dual parallax end keyframes, got {len(end_kfs)}"

    dual_clips = [c for c in plan["clips"] if c.get("dual_keyframe_parallax")]
    assert 3 <= len(dual_clips) <= 5
    for dc in dual_clips:
        assert dc.get("flow_input_mode") == "VIDEO_FRAMES"
        assert str(dc.get("end_reference_image") or "").endswith("_pv_end_9x16.png")


def test_p5_previs_conformance_and_zero_marker_color_leak_qa(tmp_path: Path) -> None:
    pv_img = np.full((960, 540, 3), 215, dtype=np.uint8)
    # Royal Violet actor marker (#7B2CBF -> BGR (191, 44, 123)) in center
    cv2.rectangle(pv_img, (185, 310), (355, 760), (191, 44, 123), -1)
    cv2.circle(pv_img, (270, 255), 58, (191, 44, 123), -1)
    pv_path = tmp_path / "S01_start_previs.png"
    cv2.imwrite(str(pv_path), pv_img)

    # 1. Clean translated matte cream-white vinyl figure at the same silhouette -> PASSES E7_previs_conformance & E7_zero_previs_color_leak
    good_kf = np.full((1920, 1080, 3), 148, dtype=np.uint8)
    rng = np.random.default_rng(7)
    good_kf = np.clip(good_kf.astype(np.int16) + rng.integers(-18, 19, size=good_kf.shape, dtype=np.int16), 0, 255).astype(np.uint8)
    cv2.rectangle(good_kf, (370, 620), (710, 1520), (118, 92, 58), -1)  # clothed torso
    cv2.circle(good_kf, (540, 510), 116, (236, 240, 244), -1)  # matte cream-white vinyl head
    cv2.circle(good_kf, (505, 500), 14, (22, 24, 28), -1)
    cv2.circle(good_kf, (575, 500), 14, (22, 24, 28), -1)
    good_path = tmp_path / "kf_01_s01_pv_start_9x16.png"
    cv2.imwrite(str(good_path), good_kf)

    spec_entry = {
        "ref_id": "kf_01_s01_pv_start",
        "category": "clip_keyframe_anchor",
        "style_profile": "expressive_25d_v8",
        "filename": good_path.name,
        "previs_guide_png": str(pv_path),
    }
    rep_good = rqa.inspect_single_reference_image(good_path, spec_entry)
    assert rep_good["axes_q1_to_q7"]["E7_previs_conformance"] is True, rep_good
    assert rep_good["axes_q1_to_q7"]["E7_zero_previs_color_leak"] is True, rep_good

    # 2. Raw Previs Royal Violet marker leaked onto head without matte-white translation -> FAILS E7_zero_previs_color_leak
    leak_kf = good_kf.copy()
    cv2.circle(leak_kf, (540, 510), 118, (191, 44, 123), -1)
    cv2.rectangle(leak_kf, (370, 620), (710, 1520), (191, 44, 123), -1)
    leak_path = tmp_path / "kf_01_s01_pv_leak_9x16.png"
    cv2.imwrite(str(leak_path), leak_kf)
    rep_leak = rqa.inspect_single_reference_image(
        leak_path,
        dict(spec_entry, filename=leak_path.name),
    )
    assert rep_leak["axes_q1_to_q7"]["E7_zero_previs_color_leak"] is False, rep_leak
