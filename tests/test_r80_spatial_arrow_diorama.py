from __future__ import annotations

from pathlib import Path

from pipeline.config import (
    EXPRESSIVE_V8_DRONE_CAMERA_MOVES,
    EXPRESSIVE_V8_SPATIAL_RELAY_MIN_CUT_SEC,
    EXPRESSIVE_V8_VISUAL_GRAMMARS,
    R80_3D_ARROW_ACCENT_HEX,
    R80_SPATIAL_FLIGHT_SPEED_RAMP_RANGE,
)
from pipeline.depiction_rules import ExpressiveV8PromptComposer, validate_expressive_v8_scene
from pipeline.diorama_assembler import build_v7_dynamic_edl
from pipeline.prompt_quality_v5 import validate_r76_brain_simulator_and_pacing_contract
from pipeline.real_world_reference_builder import URBAN_LANDMARK_QUERY_MAP
from pipeline.spatial_arrow_guide import (
    build_r80_flow_scene_clause,
    build_r80_keyframe_prompt,
    render_r80_arrow_layout_guide,
    verify_r80_arrow_keyframe_geometry,
)


def test_r80_constants_and_landmark_presets() -> None:
    assert "spatial_3d_arrow_diorama" in EXPRESSIVE_V8_VISUAL_GRAMMARS
    assert "drone_landmark_ascend" in EXPRESSIVE_V8_DRONE_CAMERA_MOVES
    assert "topdown_3d_route_glide" in EXPRESSIVE_V8_DRONE_CAMERA_MOVES
    assert EXPRESSIVE_V8_SPATIAL_RELAY_MIN_CUT_SEC == 2.20
    assert R80_3D_ARROW_ACCENT_HEX == "#FF2525"
    assert R80_SPATIAL_FLIGHT_SPEED_RAMP_RANGE == (1.24, 1.42)
    assert "london_eye_thames_wheel" in URBAN_LANDMARK_QUERY_MAP
    assert "london_red_bus_stop_roundel" in URBAN_LANDMARK_QUERY_MAP


def test_rq_arrow_geometry_zigzag_vs_linear(tmp_path: Path) -> None:
    zigzag_png = tmp_path / "zigzag_guide_9x16.png"
    linear_png = tmp_path / "linear_guide_9x16.png"
    sever_png = tmp_path / "sever_guide_9x16.png"

    render_r80_arrow_layout_guide(zigzag_png, "adaptive_landmark_zigzag")
    render_r80_arrow_layout_guide(linear_png, "fixed_linear_corridor")
    render_r80_arrow_layout_guide(sever_png, "doorway_boundary_sever")

    res_zig = verify_r80_arrow_keyframe_geometry(zigzag_png, "adaptive_landmark_zigzag")
    assert res_zig["passed"] is True, res_zig
    assert res_zig["tortuosity"] >= 1.35
    assert res_zig["turn_count"] >= 2

    res_lin = verify_r80_arrow_keyframe_geometry(linear_png, "fixed_linear_corridor")
    assert res_lin["passed"] is True, res_lin
    assert res_lin["tortuosity"] <= 1.08
    assert res_lin["collinearity_r2"] >= 0.92

    # Cross-check: linear guide MUST fail adaptive_landmark_zigzag and vice-versa
    wrong_zig = verify_r80_arrow_keyframe_geometry(linear_png, "adaptive_landmark_zigzag")
    assert wrong_zig["passed"] is False
    wrong_lin = verify_r80_arrow_keyframe_geometry(zigzag_png, "fixed_linear_corridor")
    assert wrong_lin["passed"] is False

    res_sev = verify_r80_arrow_keyframe_geometry(sever_png, "doorway_boundary_sever")
    assert res_sev["passed"] is True, res_sev
    assert res_sev["sig_components"] >= 2


def test_r80_flow_prompt_clean_and_hardware_ban_safe() -> None:
    kf_p = build_r80_keyframe_prompt(
        "adaptive_landmark_zigzag",
        landmark_desc="three circular London landmark beacons",
        vehicle_or_actor_desc="a miniature glossy black London cab",
    )
    assert "#FF2525" in kf_p
    assert "9:16" in kf_p

    for cam, phase, mode in (
        ("drone_landmark_ascend", "landmark_ascend", "adaptive_landmark_zigzag"),
        ("topdown_3d_route_glide", "topdown_arrow", "adaptive_landmark_zigzag"),
        ("topdown_3d_route_glide", "topdown_arrow", "fixed_linear_corridor"),
    ):
        clause = build_r80_flow_scene_clause(mode, cut_phase=phase)
        prompt = ExpressiveV8PromptComposer.compose_clip_prompt(
            clause,
            grammar="spatial_3d_arrow_diorama",
            camera_move=cam,
            context_split=True,
        )
        errs = validate_expressive_v8_scene(
            prompt,
            grammar="spatial_3d_arrow_diorama",
            camera_move=cam,
            image_conditioned=True,
        )
        assert errs == [], f"Unexpected prompt errs for {cam}/{mode}: {errs}"


def test_r80_2cut_subsentence_edl_and_r76p_floor(tmp_path: Path) -> None:
    # 16 sentences -> 18 clips (S9 split into 2.50s + 2.53s, S10 split into 2.80s + 3.20s; 7 brain clips)
    clip_files = []
    clip_durs = []
    for i in range(1, 19):
        p = tmp_path / f"clip_{i}.mp4"
        p.write_bytes(b"\x00" * 1024)
        clip_files.append(p)
        clip_durs.append(8.0)

    # Total 83.10s across 16 sentences matching Ep #9 rhythm
    sent_durs = [5.1, 5.4, 5.2, 5.3, 4.3, 5.7, 4.9, 5.4, 5.03, 6.00, 4.8, 4.6, 5.5, 4.9, 5.2, 5.57]
    spans = []
    t_cur = 0.0
    for idx, d in enumerate(sent_durs, start=1):
        spans.append({"sentence_index": idx, "start_sec": round(t_cur, 4), "end_sec": round(t_cur + d, 4)})
        t_cur += d

    brain_sents = {5, 6, 7, 11, 12, 14, 15}
    vp_clips = []
    c_no = 1
    for s_i in range(1, 17):
        if s_i == 9:
            for b_i, (cam, bw) in enumerate((("drone_landmark_ascend", 0.497), ("topdown_3d_route_glide", 0.503)), start=1):
                vp_clips.append(
                    {
                        "id": c_no,
                        "clip_number": c_no,
                        "sentence_index": 9,
                        "end_sentence_index": 9,
                        "beat_index": b_i,
                        "beat_weight": bw,
                        "act": 4,
                        "grammar": "spatial_3d_arrow_diorama",
                        "camera_move": cam,
                        "spatial_relay_cut": True,
                        "arrow_3d_mode": "adaptive_landmark_zigzag",
                        "flight_speed_ramp": 1.34,
                        "location_id": f"london_spatial_{c_no}",
                    }
                )
                c_no += 1
        elif s_i == 10:
            for b_i, (cam, bw) in enumerate((("drone_landmark_ascend", 0.467), ("topdown_3d_route_glide", 0.533)), start=1):
                vp_clips.append(
                    {
                        "id": c_no,
                        "clip_number": c_no,
                        "sentence_index": 10,
                        "end_sentence_index": 10,
                        "beat_index": b_i,
                        "beat_weight": bw,
                        "act": 4,
                        "grammar": "spatial_3d_arrow_diorama",
                        "camera_move": cam,
                        "spatial_relay_cut": True,
                        "arrow_3d_mode": "fixed_linear_corridor",
                        "flight_speed_ramp": 1.30,
                        "location_id": f"london_spatial_{c_no}",
                    }
                )
                c_no += 1
        elif s_i in brain_sents:
            vp_clips.append(
                {
                    "id": c_no,
                    "clip_number": c_no,
                    "sentence_index": s_i,
                    "end_sentence_index": s_i,
                    "act": 3,
                    "grammar": "brain_simulator_3d",
                    "render_engine": "google_flow",
                    "brain_clip": True,
                    "camera_move": "circuit_cooperation_drone",
                    "start_brain_region": "hippocampus",
                    "end_brain_region": "temporal lobe",
                    "location_id": "brain_studio",
                }
            )
            c_no += 1
        else:
            vp_clips.append(
                {
                    "id": c_no,
                    "clip_number": c_no,
                    "sentence_index": s_i,
                    "end_sentence_index": s_i,
                    "act": 1,
                    "grammar": "expressive_exterior_establishing",
                    "camera_move": "gentle_push_in",
                    "location_id": f"loc_{c_no}",
                }
            )
            c_no += 1

    vp = {
        "schema": 8,
        "project_id": "v8_ep09_test_r80",
        "profile": "neuro_diorama",
        "style_profile": "expressive_25d_v8",
        "format_profile": "shorts_expressive_v8",
        "r72_mode": True,
        "r73_mode": True,
        "r76_mode": True,
        "r76_brain_simulator": True,
        "voice_preset": "el_siren_v4",
        "clips": vp_clips,
    }
    script_doc = {
        "schema": 8,
        "style_profile": "expressive_25d_v8",
        "r76_mode": True,
        "voice_preset": "el_siren_v4",
        "sentence_speakers": ["narrator"] * 16,
        "foil_sentence_indices": [],
        "sentences": [f"Sentence {i}." for i in range(1, 17)],
    }

    edl = build_v7_dynamic_edl(
        visual_plan=vp,
        sentence_spans=spans,
        clip_files=clip_files,
        speech_end_sec=round(t_cur, 4),
        total_duration_sec=round(t_cur + 0.20, 4),
        script_doc=script_doc,
        virtual_clip_duration_sec=8.0,
    )
    assert len(edl["cuts"]) == 18
    c09, c10, c11, c12 = edl["cuts"][8], edl["cuts"][9], edl["cuts"][10], edl["cuts"][11]
    assert 2.40 <= c09["duration_sec"] <= 2.65
    assert 2.40 <= c10["duration_sec"] <= 2.65
    assert 2.70 <= c11["duration_sec"] <= 2.95
    assert 3.05 <= c12["duration_sec"] <= 3.35
    assert 1.24 <= c09["main_speed"] <= 1.42
    assert c09["spatial_relay_cut"] is True
    assert c10["arrow_3d_mode"] == "adaptive_landmark_zigzag"
    assert c12["arrow_3d_mode"] == "fixed_linear_corridor"

    r76_issues = validate_r76_brain_simulator_and_pacing_contract(vp, vp_clips, script_doc=script_doc, edl=edl)
    assert r76_issues == [], f"Unexpected R76/R80 issues: {r76_issues}"


def test_spatial_3d_arrow_diorama_allows_outdoor_lawn_greenery_without_neon_spill_false_positive(tmp_path):
    """Outdoor spatial_3d_arrow_diorama aerial quads (e.g. collegiate lawns ~20% green) must not falsely trip neon_green_fluorescent_spill."""
    import cv2
    import numpy as np
    from pipeline.flow_diorama_sharded_worker import inspect_diorama_clip_cv

    mp4_path = tmp_path / "outdoor_quad_arrow.mp4"
    w, h, fps = 720, 1280, 12
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    vw = cv2.VideoWriter(str(mp4_path), fourcc, fps, (w, h))
    # Build synthetic 5s 720x1280 moving sunlit limestone walkway + flanking ~28% outdoor sunlit grass lawns + red 3D bar
    for f_idx in range(fps * 5):
        img = np.full((h, w, 3), (200, 210, 220), dtype=np.uint8)  # limestone walkway
        shift = (f_idx * 12) % 80
        # Left & right green sunlit grass lawns (~28% area, bright natural green BGR)
        img[:, 40:145] = (40, 180, 55)
        img[:, w - 145 : w - 40] = (40, 180, 55)
        # Moving architectural stone paving lines for crisp motion & sharpness
        for y_line in range(shift, h, 80):
            cv2.line(img, (145, y_line), (w - 145, y_line), (120, 130, 140), 4)
        # Matte crimson 3D bar halted at y=50%
        cv2.rectangle(img, (w // 2 - 28, h // 2), (w // 2 + 28, h - 80), (37, 37, 225), -1)
        vw.write(img)
    vw.release()

    res_outdoor = inspect_diorama_clip_cv(
        mp4_path,
        grammar="spatial_3d_arrow_diorama",
        style_profile="expressive_25d_v8",
    )
    assert res_outdoor["passed"] is True, res_outdoor
    assert res_outdoor["neon_green_ratio"] > 0.15, res_outdoor

    # Same 28% green spill on a brain clip MUST still be blocked by neon_green_fluorescent_spill
    res_brain = inspect_diorama_clip_cv(
        mp4_path,
        grammar="expressive_xray_brain",
        style_profile="expressive_25d_v8",
    )
    assert res_brain["passed"] is False
    assert "neon_green_fluorescent_spill" in str(res_brain.get("reason") or ""), res_brain


def test_spatial_3d_arrow_diorama_allows_doorway_partition_wall_while_blocking_true_split_screen(tmp_path):
    """Top-down doorway partition wall with open central gap (~0.78 seam) passes on spatial_3d_arrow_diorama, while full edge-to-edge split screen (>=0.92) still fails."""
    import cv2
    import numpy as np
    from pipeline.flow_diorama_sharded_worker import (
        detect_unintended_horizontal_split_seam,
        inspect_diorama_clip_cv,
    )

    w, h, fps = 720, 1280, 12
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")

    # 1) Top-down architectural doorway partition wall at y=50% with open central doorway gap (22% width)
    wall_mp4 = tmp_path / "doorway_wall.mp4"
    vw = cv2.VideoWriter(str(wall_mp4), fourcc, fps, (w, h))
    max_wall_seam = 0.0
    for f_idx in range(fps * 5):
        img = np.full((h, w, 3), (170, 195, 220), dtype=np.uint8)  # warm oak floor
        shift = (f_idx * 14) % 80
        # Moving vertical oak floorboards (creates clean horizontal motion without fake full-width horizontal scanlines)
        for x_col in range(shift, w, 80):
            cv2.rectangle(img, (x_col, 0), (min(w - 1, x_col + 22), h), (130, 155, 185), -1)
        # Crisp white horizontal partition wall with dark shadow lip on left & right, open doorway in center
        y_wall = int(h * 0.48)
        gap_l, gap_r = int(w * 0.39), int(w * 0.61)
        cv2.rectangle(img, (0, y_wall - 14), (gap_l, y_wall + 14), (242, 245, 248), -1)
        cv2.rectangle(img, (gap_r, y_wall - 14), (w, y_wall + 14), (242, 245, 248), -1)
        cv2.line(img, (0, y_wall + 15), (gap_l, y_wall + 15), (90, 95, 100), 4)
        cv2.line(img, (gap_r, y_wall + 15), (w, y_wall + 15), (90, 95, 100), 4)
        # Matte crimson 3D bar halted right at doorway threshold
        cv2.rectangle(img, (w // 2 - 26, y_wall + 16), (w // 2 + 26, h - 80), (37, 37, 225), -1)
        max_wall_seam = max(max_wall_seam, detect_unintended_horizontal_split_seam(img))
        vw.write(img)
    vw.release()
    assert 0.72 <= max_wall_seam < 0.90, f"expected doorway wall seam in [0.72, 0.90), got {max_wall_seam}"

    res_wall_arrow = inspect_diorama_clip_cv(
        wall_mp4,
        grammar="spatial_3d_arrow_diorama",
        style_profile="expressive_25d_v8",
    )
    assert res_wall_arrow["passed"] is True, res_wall_arrow

    # Same 0.78 seam on a regular fullbleed scene MUST still fail the strict 0.72 threshold
    res_wall_fullbleed = inspect_diorama_clip_cv(
        wall_mp4,
        grammar="expressive_fullbleed_scene",
        style_profile="expressive_25d_v8",
    )
    assert res_wall_fullbleed["passed"] is False
    assert "unintended_horizontal_split_screen" in str(res_wall_fullbleed.get("reason") or ""), res_wall_fullbleed

    # 2) Full 100% edge-to-edge artificial 2-panel split-screen MUST STILL FAIL even on spatial_3d_arrow_diorama
    split_mp4 = tmp_path / "full_split_screen.mp4"
    vw2 = cv2.VideoWriter(str(split_mp4), fourcc, fps, (w, h))
    for f_idx in range(fps * 5):
        img = np.full((h, w, 3), (225, 228, 232), dtype=np.uint8)
        img[int(h * 0.48) :, :] = (115, 125, 140)
        shift = (f_idx * 14) % 80
        for x_col in range(shift, w, 80):
            cv2.rectangle(img, (x_col, 0), (min(w - 1, x_col + 22), int(h * 0.48) - 2), (175, 180, 186), -1)
            cv2.rectangle(img, (x_col, int(h * 0.48) + 2), (min(w - 1, x_col + 22), h), (80, 90, 105), -1)
        vw2.write(img)
    vw2.release()

    res_split_arrow = inspect_diorama_clip_cv(
        split_mp4,
        grammar="spatial_3d_arrow_diorama",
        style_profile="expressive_25d_v8",
    )
    assert res_split_arrow["passed"] is False
    assert "unintended_horizontal_split_screen" in str(res_split_arrow.get("reason") or ""), res_split_arrow


