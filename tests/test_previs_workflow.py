"""
Phase 5.5 Regression & Unit Tests — 3D Blockout Previs Keyframe Generator (`tests/test_previs_workflow.py`).

Verifies:
1. Rule 1 (Subtraction / 빼기): 3-chunk actor dummies (`lower_body` + `torso` + `head`) & real-scale prop bounding boxes.
2. Rule 2 (Collision-Free Color Coding / 색 표시): `PREVIS_SAFE_PALETTE` safety & rejection of porcelain/vinyl white + 4-color Brain collisions.
3. Mathematical Camera Seam Continuity: `propagate_previs_camera_continuity` (`End(i) == Start(i+1)`) + `0.0` pixel MAE across chained `9:16` previs PNGs.
4. Blender Script Generation: `ast.parse`-valid `BLENDER_WORKBENCH` (`STUDIO`, `OBJECT`, `9:16`) Python script generation.
5. Flow Keyframe Translation Wiring: `resolve_keyframe_conditioning_and_prompt` (`<= 2` ingredients: Previs PNG + Cast Sheet, color-to-subject prompt mapping) + `populate_expressive_v8_reference_contract` propagation.
6. Portable Blender CLI Render (`skipif` when Blender binary / host GL libs are absent).
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import pytest

from pipeline.porcelain_anchor_pack import populate_expressive_v8_reference_contract
from pipeline.previs_blender import (
    PREVIS_FORBIDDEN_COLORS,
    PREVIS_SAFE_PALETTE,
    assign_previs_palette,
    build_prop_box_primitive,
    build_three_chunk_actor_primitives,
    generate_blender_workbench_script,
    is_blender_available,
    propagate_previs_camera_continuity,
    render_previs_keyframes,
    render_visual_plan_previs_pack,
    validate_previs_color_safety,
)
from pipeline.reference_image_qa import build_reference_image_specs
from pipeline.source_reenactment import resolve_keyframe_conditioning_and_prompt


def test_rule1_three_chunk_actor_and_prop_bounding_box_subtraction() -> None:
    """Rule 1: Humans decompose strictly into 3 primitives (lower_body, torso, head); props into 1 bounding box."""
    actor = {
        "role_id": "hotel_sleeper",
        "label": "Traveler in navy hoodie",
        "pos_start": [-0.3, 0.2, 0.0],
        "pos_end": [0.1, 0.0, 0.0],
        "height_m": 1.70,
        "yaw_deg": 15.0,
        "color_hex": "#7B2CBF",
    }
    chunks_start = build_three_chunk_actor_primitives(actor, phase="start")
    chunks_end = build_three_chunk_actor_primitives(actor, phase="end")
    assert len(chunks_start) == 3
    assert [c["chunk_id"] for c in chunks_start] == [
        "hotel_sleeper_lower_body",
        "hotel_sleeper_torso",
        "hotel_sleeper_head",
    ]
    assert [c["shape"] for c in chunks_start] == ["box", "box", "sphere"]
    assert chunks_start[0]["center"][0] == pytest.approx(-0.3)
    assert chunks_end[0]["center"][0] == pytest.approx(0.1)

    prop = {
        "prop_id": "brass_alarm",
        "label": "Vintage brass alarm clock",
        "pos_start": [0.4, -0.3, 0.72],
        "size_xyz": [0.18, 0.12, 0.20],
        "color_hex": "#8C5A2B",
        "back_color_hex": "#2B3A67",
    }
    p_box = build_prop_box_primitive(prop, phase="start")
    assert p_box["shape"] == "box"
    assert p_box["size_xyz"] == pytest.approx([0.18, 0.12, 0.20])
    assert p_box["back_color_hex"] == "#2B3A67"


def test_rule2_palette_safety_and_forbidden_brain_or_white_collision_rejection() -> None:
    """Rule 2: Safe palette avoids porcelain/vinyl whites and all 4 Brain colors; colliding colors raise ValueError."""
    assert len(PREVIS_SAFE_PALETTE) >= 6
    for c_name, c_hex in PREVIS_SAFE_PALETTE:
        ok, msg = validate_previs_color_safety(c_hex)
        assert ok is True, f"Safe palette color {c_name} ({c_hex}) failed safety check: {msg}"

    for forb_name, forb_hex in PREVIS_FORBIDDEN_COLORS.items():
        ok_f, msg_f = validate_previs_color_safety(forb_hex)
        assert ok_f is False, f"Forbidden color {forb_name} ({forb_hex}) was not rejected!"
        assert forb_name in msg_f or "collides" in msg_f

    with pytest.raises(ValueError, match="collides with forbidden"):
        assign_previs_palette([{"role_id": "hero", "label": "Hero", "color_hex": "#00D4FF"}])  # Brain Cyan-Blue

    with pytest.raises(ValueError, match="collides with forbidden"):
        assign_previs_palette([{"role_id": "hero", "label": "Hero", "color_hex": "#F5F2EB"}])  # Vinyl Cream-White

    with pytest.raises(ValueError, match="collides with forbidden"):
        assign_previs_palette([{"prop_id": "orb", "label": "Orb", "color_hex": "#7B2CBF", "back_color_hex": "#DC1E32"}])


def test_camera_continuity_propagation_and_zero_mae_seam_render(tmp_path: Path) -> None:
    """Same-location cuts copy camera_end -> next.camera_start and render pixel-identical End(i) == Start(i+1) PNGs."""
    visual_plan: dict[str, Any] = {
        "schema_version": 8,
        "style_profile": "expressive_25d_v8",
        "default_location_id": "hotel_room",
        "clips": [
            {
                "clip_number": 1,
                "scene_id": "S01",
                "location_id": "hotel_room",
                "previs": {
                    "camera_start": {"pos": [0.0, -2.8, 2.9], "look_at": [0.0, 0.1, 1.1], "fov_deg": 52.0},
                    "camera_end": {"pos": [0.35, -1.65, 1.32], "look_at": [0.05, 0.1, 1.28], "fov_deg": 47.0},
                    "actors": [
                        {
                            "role_id": "sleeper",
                            "label": "Sleeper protagonist",
                            "pos_start": [-0.25, 0.15, 0.0],
                            "pos_end": [0.10, 0.05, 0.0],
                            "height_m": 1.72,
                        }
                    ],
                    "props": [
                        {
                            "prop_id": "watch",
                            "label": "Wristwatch on nightstand",
                            "pos_start": [0.42, -0.35, 0.72],
                            "pos_end": [0.42, -0.35, 0.72],
                            "size_xyz": [0.22, 0.18, 0.14],
                        }
                    ],
                    "room_blocks": [
                        {"block_id": "floor", "pos": [0.0, 0.2, -0.06], "size_xyz": [4.2, 4.2, 0.12], "color_hex": "#6E737B"},
                        {"block_id": "wall", "pos": [0.0, 2.1, 1.5], "size_xyz": [4.2, 0.14, 3.0], "color_hex": "#8A8F98"},
                    ],
                },
            },
            {
                "clip_number": 2,
                "scene_id": "S02",
                "location_id": "hotel_room",
                "previs": {
                    # Intentionally mismatched initial camera_start & pos_start -> continuity propagation must overwrite!
                    "camera_start": {"pos": [-1.9, -3.0, 0.6], "look_at": [0.0, 0.0, 0.5], "fov_deg": 60.0},
                    "camera_end": {"pos": [-0.85, -1.50, 0.78], "look_at": [0.10, 0.05, 1.38], "fov_deg": 45.0},
                    "actors": [
                        {
                            "role_id": "sleeper",
                            "label": "Sleeper protagonist",
                            "pos_start": [-1.0, 0.8, 0.0],
                            "pos_end": [0.18, -0.05, 0.0],
                            "height_m": 1.72,
                        }
                    ],
                    "props": [
                        {
                            "prop_id": "watch",
                            "label": "Wristwatch on nightstand",
                            "pos_start": [0.42, -0.35, 0.72],
                            "pos_end": [0.42, -0.35, 0.72],
                            "size_xyz": [0.22, 0.18, 0.14],
                        }
                    ],
                    "room_blocks": [
                        {"block_id": "floor", "pos": [0.0, 0.2, -0.06], "size_xyz": [4.2, 4.2, 0.12], "color_hex": "#6E737B"},
                        {"block_id": "wall", "pos": [0.0, 2.1, 1.5], "size_xyz": [4.2, 0.14, 3.0], "color_hex": "#8A8F98"},
                    ],
                },
            },
            {
                "clip_number": 3,
                "scene_id": "S03",
                "location_id": "rooftop_exterior",  # Different location -> must NOT overwrite camera_start!
                "previs": {
                    "camera_start": {"pos": [0.0, -3.4, 2.2], "look_at": [0.0, 0.0, 1.2], "fov_deg": 55.0},
                    "camera_end": {"pos": [0.0, -2.1, 1.4], "look_at": [0.0, 0.0, 1.3], "fov_deg": 48.0},
                    "actors": [{"role_id": "sleeper", "label": "Sleeper protagonist", "pos_start": [0.0, 0.0, 0.0]}],
                },
            },
        ],
    }

    pack = render_visual_plan_previs_pack(visual_plan, out_dir=tmp_path / "guides", backend="workbench_cpu")
    assert pack["rendered_count"] == 3

    pv1 = visual_plan["clips"][0]["previs"]
    pv2 = visual_plan["clips"][1]["previs"]
    pv3 = visual_plan["clips"][2]["previs"]

    assert pv2["camera_start"] == pv1["camera_end"]
    assert pv2["continuity_chained_from_cut"] == 1
    assert pv2["actors"][0]["pos_start"] == pytest.approx([0.10, 0.05, 0.0])
    # Role color carries consistently across cuts
    assert pv1["color_role_legend"]["sleeper"]["color_hex"] == pv2["color_role_legend"]["sleeper"]["color_hex"]
    assert pv1["color_role_legend"]["sleeper"]["color_hex"] == pv3["color_role_legend"]["sleeper"]["color_hex"]
    # Different location preserved its own start camera
    assert pv3["camera_start"]["pos"] == pytest.approx([0.0, -3.4, 2.2])

    end_cut1 = cv2.imread(pv1["end_previs_png"])
    start_cut2 = cv2.imread(pv2["start_previs_png"])
    start_cut1 = cv2.imread(pv1["start_previs_png"])
    assert end_cut1 is not None and start_cut2 is not None and start_cut1 is not None
    assert end_cut1.shape == (960, 540, 3)
    seam_mae = float(np.mean(np.abs(end_cut1.astype(np.float32) - start_cut2.astype(np.float32))))
    motion_mae = float(np.mean(np.abs(start_cut1.astype(np.float32) - end_cut1.astype(np.float32))))
    assert seam_mae == 0.0, f"Expected exact 0.0 MAE across chained previs seam, got {seam_mae}"
    assert motion_mae > 1.0, "Start and End frames of moving camera cut should visually differ"


def test_blender_script_ast_validity_and_aspect_guard(tmp_path: Path) -> None:
    """Generated Blender script is syntactically valid Python targeting BLENDER_WORKBENCH @ 9:16."""
    spec = {
        "camera_start": {"pos": [0.0, -2.5, 1.5], "look_at": [0.0, 0.0, 1.2], "fov_deg": 50.0},
        "camera_end": {"pos": [0.4, -1.7, 1.3], "look_at": [0.0, 0.0, 1.3], "fov_deg": 46.0},
        "actors": [{"role_id": "subject_a", "label": "Subject A", "pos_start": [0.0, 0.0, 0.0]}],
        "props": [{"prop_id": "lamp", "label": "Desk lamp", "pos_start": [0.3, -0.2, 0.7], "size_xyz": [0.2, 0.2, 0.35]}],
    }
    script_txt = generate_blender_workbench_script(
        spec,
        start_png=tmp_path / "S01_start_previs.png",
        end_png=tmp_path / "S01_end_previs.png",
    )
    tree = ast.parse(script_txt)
    assert isinstance(tree, ast.Module)
    assert 'scene.render.engine = "BLENDER_WORKBENCH"' in script_txt
    assert 'scene.display.shading.light = "STUDIO"' in script_txt
    assert 'scene.display.shading.color_type = "OBJECT"' in script_txt
    assert "_lower_body" in script_txt and "_torso" in script_txt and "_head" in script_txt
    assert "_bbox" in script_txt

    with pytest.raises(ValueError, match="9:16"):
        render_previs_keyframes(spec, out_dir=tmp_path, width=1920, height=1080, backend="workbench_cpu")


def test_previs_keyframe_translation_prompt_and_two_attachment_cap(tmp_path: Path) -> None:
    """translate_porcelain_keyframes helper caps attachments at <= 2 (Previs + Cast Sheet) and maps marker colors."""
    guides_dir = tmp_path / "guides"
    ref_dir = tmp_path / "03_visuals" / "reference_images"
    guides_dir.mkdir(parents=True)
    ref_dir.mkdir(parents=True)

    pv_res = render_previs_keyframes(
        {
            "camera_start": {"pos": [0.0, -2.4, 2.6], "look_at": [0.0, 0.0, 1.1], "fov_deg": 50.0},
            "camera_end": {"pos": [0.0, -1.6, 1.3], "look_at": [0.0, 0.0, 1.25], "fov_deg": 48.0},
            "actors": [{"role_id": "traveler", "label": "Exhausted traveler in navy hoodie", "pos_start": [0.0, 0.0, 0.0]}],
            "props": [{"prop_id": "suitcase", "label": "Hard-shell carry-on suitcase", "pos_start": [0.45, -0.2, 0.0], "size_xyz": [0.38, 0.24, 0.56]}],
        },
        out_dir=guides_dir,
        cut_id="S01",
        backend="workbench_cpu",
    )

    # Populate 3 reference sheets in ref_dir -> resolver MUST cap cond_paths to strictly 2: [previs_png, species_opt1_sheet.png]
    for fname in ("ref_env_master.png", "species_opt1_sheet.png", "ref_prop_hero.png"):
        (ref_dir / fname).write_bytes(b"\x89PNG\r\n\x1a\n")

    plan: dict[str, Any] = {
        "schema_version": 8,
        "profile": "neuro_diorama",
        "style_profile": "expressive_25d_v8",
        "default_location_id": "hotel_room",
        "real_environment": "warm boutique hotel bedroom at night",
        "clips": [
            {
                "clip_number": 1,
                "scene_id": "S01",
                "location_id": "hotel_room",
                "environment": "warm boutique hotel bedroom at night",
                "action": "setting down a suitcase beside the bed",
                "previs": {
                    "camera_start": {"pos": [0.0, -2.4, 2.6], "look_at": [0.0, 0.0, 1.1], "fov_deg": 50.0},
                    "camera_end": {"pos": [0.0, -1.6, 1.3], "look_at": [0.0, 0.0, 1.25], "fov_deg": 48.0},
                    "actors": [{"role_id": "traveler", "label": "Exhausted traveler in navy hoodie", "pos_start": [0.0, 0.0, 0.0]}],
                    "props": [{"prop_id": "suitcase", "label": "Hard-shell carry-on suitcase", "pos_start": [0.45, -0.2, 0.0], "size_xyz": [0.38, 0.24, 0.56]}],
                    "start_previs_png": pv_res["start_png"],
                    "color_role_legend": pv_res["color_role_legend"],
                },
            }
        ],
    }
    populate_expressive_v8_reference_contract(plan, synthesize_scene_anchors=True, daisy_chain_keyframes=True)
    specs_payload = build_reference_image_specs(plan, ["At two AM, she dropped her suitcase beside the hotel bed."])
    clip_spec = next(s for s in specs_payload["all_specs"] if s.get("clip_number") == 1)
    clip_spec["conditioned_on"] = ["ref_env_master", "species_opt1_sheet", "ref_prop_hero"]

    cond_paths, full_prompt, has_guide = resolve_keyframe_conditioning_and_prompt(
        spec=clip_spec,
        plan=plan,
        guides_dir=guides_dir,
        ref_dir=ref_dir,
    )
    assert has_guide is True
    assert len(cond_paths) == 2
    assert cond_paths[0] == Path(pv_res["start_png"])
    assert cond_paths[1] == ref_dir / "species_opt1_sheet.png"
    assert "Attachment 1" in full_prompt
    assert "Attachment 2 character sheet" in full_prompt
    assert "Royal Violet (#7B2CBF)" in full_prompt
    assert "Exhausted traveler in navy hoodie" in full_prompt
    assert "Hard-shell carry-on suitcase" in full_prompt
    assert "position markers ONLY" in full_prompt

    # Standalone / final moving-camera cut with end_previs_png must also wire an explicit End keyframe anchor!
    plan_with_end: dict[str, Any] = {
        "schema_version": 8,
        "profile": "neuro_diorama",
        "style_profile": "expressive_25d_v8",
        "default_location_id": "hotel_room",
        "real_environment": "warm boutique hotel bedroom at night",
        "clips": [
            {
                "clip_number": 1,
                "scene_id": "S01",
                "location_id": "hotel_room",
                "environment": "warm boutique hotel bedroom at night",
                "action": "setting down a suitcase beside the bed",
                "previs": {
                    "camera_start": {"pos": [0.0, -2.4, 2.6], "look_at": [0.0, 0.0, 1.1], "fov_deg": 50.0},
                    "camera_end": {"pos": [0.0, -1.6, 1.3], "look_at": [0.0, 0.0, 1.25], "fov_deg": 48.0},
                    "actors": [{"role_id": "traveler", "label": "Exhausted traveler in navy hoodie", "pos_start": [0.0, 0.0, 0.0]}],
                    "props": [{"prop_id": "suitcase", "label": "Hard-shell carry-on suitcase", "pos_start": [0.45, -0.2, 0.0], "size_xyz": [0.38, 0.24, 0.56], "back_color_hex": "#FF007F"}],
                    "start_previs_png": pv_res["start_png"],
                    "end_previs_png": pv_res["end_png"],
                    "color_role_legend": pv_res["color_role_legend"],
                },
            }
        ],
    }
    populate_expressive_v8_reference_contract(plan_with_end, synthesize_scene_anchors=True, daisy_chain_keyframes=True)
    c1_wired = plan_with_end["clips"][0]
    assert str(c1_wired.get("end_reference_image") or "").endswith("_end_9x16.png")
    assert c1_wired["end_reference_image"] != c1_wired["reference_image"]

    # Directory-discovered previs PNG without spec['color_role_legend'] falls back to plan['clips'][i]['previs']['color_role_legend']
    bare_spec = {
        "ref_id": "kf_01_start",
        "filename": "kf_01_start.png",
        "clip_number": 1,
        "scene_id": "S01",
        "frame": "start",
        "setting": "real_env",
        "conditioned_on": ["species_opt1_sheet"],
        "prompt": "Single full-bleed vertical 9:16 3D miniature diorama scene.",
    }
    _, fallback_prompt, has_fb_guide = resolve_keyframe_conditioning_and_prompt(
        spec=bare_spec,
        plan=plan_with_end,
        guides_dir=guides_dir,
        ref_dir=ref_dir,
    )
    assert has_fb_guide is True
    assert "Exhausted traveler in navy hoodie" in fallback_prompt

    # Blender Workbench script includes rear-face plate when back_color_hex is specified
    bl_script = generate_blender_workbench_script(
        plan_with_end["clips"][0]["previs"],
        start_png=tmp_path / "b_s.png",
        end_png=tmp_path / "b_e.png",
    )
    assert "_bbox_back" in bl_script


@pytest.mark.skipif(
    not is_blender_available(),
    reason="Portable/system Blender binary or required host OpenGL/X11 shared libs are not installed on this machine",
)
def test_headless_blender_cli_workbench_execution(tmp_path: Path) -> None:
    """Executes real `blender -b --factory-startup -P` when portable Blender is runnable on the host."""
    res = render_previs_keyframes(
        {
            "camera_start": {"pos": [0.0, -2.5, 1.5], "look_at": [0.0, 0.0, 1.2], "fov_deg": 50.0},
            "camera_end": {"pos": [0.3, -1.7, 1.3], "look_at": [0.0, 0.0, 1.25], "fov_deg": 48.0},
            "actors": [{"role_id": "hero", "label": "Protagonist", "pos_start": [0.0, 0.0, 0.0]}],
        },
        out_dir=tmp_path,
        cut_id="BL01",
        backend="blender",
    )
    assert res["backend_used"] == "blender"
    assert Path(res["start_png"]).is_file()
    assert Path(res["end_png"]).is_file()
