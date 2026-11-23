from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import pytest

import pipeline.config as cfg
from pipeline.diorama_assembler import build_v7_dynamic_edl
from pipeline.dynamic_episode_qa import compile_episode_qa_contract
from pipeline.flow_prompt_builder import (
    build_diorama_v7_prompts,
    validate_expressive_v8_prompts,
    validate_r72_open_world_drone_and_real_refs,
)
from pipeline.porcelain_anchor_pack import populate_expressive_v8_reference_contract
from pipeline.previs_blender import (
    is_outdoor_or_architectural_clip,
    render_previs_keyframes,
    synthesize_default_previs_spec_for_clip,
)
from pipeline.real_world_reference_builder import (
    build_sanitized_9x16_structural_guide,
    ensure_quarantine_dir,
    evaluate_rq_real_alignment,
    extract_episode_real_world_targets,
    purge_real_world_quarantine,
    resolve_real_world_target_spec,
    verify_zero_raw_leak_in_workspace,
)


def _draw_synthetic_arch_photo(path: Path, *, red_brick: bool = True, stylized_3d: bool = False) -> None:
    """Renders a deterministic architectural facade image (either landscape photo or 9:16 3D miniature)."""
    if not stylized_3d:
        h, w = 900, 1400
        img = np.full((h, w, 3), (232, 212, 186), dtype=np.uint8)
        # Sky gradient
        img[:320, :] = (238, 206, 168)
        # Green courtyard lawn
        img[670:, :] = (86, 152, 92)
        # Building mass + pediment + columns
        facade_col = (68, 86, 168) if red_brick else (196, 204, 212)
        cv2.rectangle(img, (220, 260), (1180, 670), facade_col, -1)
        pts = np.array([[190, 260], [700, 120], [1210, 260]], dtype=np.int32)
        cv2.fillPoly(img, [pts], (182, 194, 204))
        for cx in range(290, 1130, 120):
            cv2.rectangle(img, (cx, 285), (cx + 34, 665), (228, 232, 236), -1)
        # Add fine synthetic sensor grain to mimic raw photo texture
        rng = np.random.default_rng(42)
        noise = rng.integers(-18, 19, size=img.shape, dtype=np.int16)
        img = np.clip(img.astype(np.int16) + noise, 0, 255).astype(np.uint8)
    else:
        h, w = 1920, 1080
        img = np.full((h, w, 3), (242, 224, 198), dtype=np.uint8)
        img[:520, :] = (245, 214, 178)
        img[1420:, :] = (98, 168, 108)
        facade_col = (76, 98, 184) if red_brick else (208, 214, 222)
        cv2.rectangle(img, (90, 640), (990, 1420), facade_col, -1)
        pts = np.array([[65, 640], [540, 440], [1015, 640]], dtype=np.int32)
        cv2.fillPoly(img, [pts], (216, 222, 228))
        for cx in range(150, 950, 150):
            cv2.rectangle(img, (cx, 680), (cx + 46, 1410), (244, 244, 246), -1)
        # Add stylized vinyl figures & tree spheres in courtyard so dHash diverges cleanly (>= 14)
        cv2.circle(img, (210, 1560), 65, (82, 142, 88), -1)
        cv2.circle(img, (870, 1590), 72, (76, 136, 82), -1)
        cv2.ellipse(img, (540, 1640), (42, 58), 0, 0, 360, (235, 242, 245), -1)
    path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(path), img)


def test_r72_real_world_three_category_resolution_quarantine_and_rq_real(tmp_path: Path) -> None:
    # 1. Verify all 3 categories resolve cleanly (`institution`, `urban_setting`, `scientific_apparatus`)
    inst_ucl = resolve_real_world_target_spec("ucl")
    inst_harvard = resolve_real_world_target_spec("harvard")
    urban_sq = resolve_real_world_target_spec("harvard_square", fallback_category="urban_setting")
    app_darkroom = resolve_real_world_target_spec("darkroom_enlarger", fallback_category="scientific_apparatus")

    assert inst_ucl["category"] == "institution"
    assert "Wilkins" in inst_ucl["label"]
    assert inst_harvard["category"] == "institution"
    assert "Harvard" in inst_harvard["label"]
    assert urban_sq["category"] == "urban_setting"
    assert app_darkroom["category"] == "scientific_apparatus"

    # Automatic multi-category extraction from plan + dossier metadata
    targets = extract_episode_real_world_targets(
        dossier={"institution": "Harvard University", "topic": "Photographic darkroom course & gourmet jam booth"},
        visual_plan={
            "real_world_targets": ["harvard", "harvard_square", "charles_river_footbridge", "darkroom_enlarger"],
        },
    )
    cats = {t["category"] for t in targets}
    assert {"institution", "urban_setting", "scientific_apparatus"}.issubset(cats)

    # 2. Quarantine strictly refuses paths inside WORKSPACE_ROOT
    with pytest.raises(ValueError, match="MUST reside outside WORKSPACE_ROOT"):
        ensure_quarantine_dir("illegal_inside_repo", quarantine_root=cfg.WORKSPACE_ROOT / "tmp_leak")

    # 3. Valid external quarantine + full-span 9:16 structural guide + RQ-Real alignment + zero-leak purge
    ext_qroot = tmp_path / "ext_quarantine"
    q_dir = ensure_quarantine_dir("unit_r72_harvard", quarantine_root=ext_qroot)
    raw_jpg = q_dir / "raw" / "harvard.jpg"
    guide_png = q_dir / "guides" / "harvard_9x16.png"
    _draw_synthetic_arch_photo(raw_jpg, red_brick=True, stylized_3d=False)

    guide_meta = build_sanitized_9x16_structural_guide(raw_jpg, guide_png)
    assert guide_meta["shape"] == [1080, 1920]
    assert Path(guide_meta["guide_path"]).exists()

    proj_dir = tmp_path / "proj_r72_harvard"
    rendered_kf = proj_dir / "03_visuals" / "references" / "kf_01_r72_k1_facade_9x16.png"
    _draw_synthetic_arch_photo(rendered_kf, red_brick=True, stylized_3d=True)

    rq = evaluate_rq_real_alignment(guide_meta, rendered_kf)
    assert rq["dhash_non_infringement_ok"] is True, f"Expected dHash >= 14: {rq}"
    assert rq["structural_alignment_ok"] is True, f"Expected coarse edge alignment >= 0.30: {rq}"
    assert rq["rq_real_passed"] is True

    leak_audit = verify_zero_raw_leak_in_workspace(
        proj_dir,
        raw_sha256_list=[guide_meta["guide_sha256"]],
        raw_dhash_hex_list=[guide_meta["raw_dhash64_hex"]],
    )
    assert leak_audit["zero_raw_leak_verified"] is True

    purge_res = purge_real_world_quarantine("unit_r72_harvard", quarantine_root=ext_qroot)
    assert purge_res["purged"] is True
    assert not q_dir.exists()


def test_r72_previs_v22_open_world_drone_trajectory_and_k1_relay_seam(tmp_path: Path) -> None:
    clip_01 = {
        "index": 1,
        "location_id": "campus_quad_aerial_01",
        "grammar": "expressive_exterior_establishing",
        "camera_move": "drone_aerial_approach",
        "cast": ["researcher"],
        "action_2beat": "Sweeps from high campus aerial down toward arched brick facade.",
    }
    clip_02 = {
        "index": 2,
        "location_id": "architectural_cutaway_portal_01",
        "grammar": "architectural_cutaway_portal",
        "camera_move": "fpv_window_portal_breach",
        "cast": ["researcher", "student"],
        "action_2beat": "Glides straight through sliced brick facade into bright darkroom lab.",
    }
    assert is_outdoor_or_architectural_clip(clip_01) is True
    assert is_outdoor_or_architectural_clip(clip_02) is True

    # Verify indoor 3.75m frustum clamp is bypassed on aerial drone shots (z=13.5m preserved!)
    pv_01 = synthesize_default_previs_spec_for_clip(clip_01, 1)
    pv_02 = synthesize_default_previs_spec_for_clip(clip_02, 2)

    assert pv_01["camera_start"]["pos"][2] >= 12.0, f"Aerial start height was clamped: {pv_01['camera_start']}"
    assert pv_01["camera_end"]["pos"] == pv_02["camera_start"]["pos"], (
        f"Clip 1 End (K1) and Clip 2 Start (K1) camera positions must match 1:1! "
        f"{pv_01['camera_end']['pos']} vs {pv_02['camera_start']['pos']}"
    )
    assert pv_02["camera_end"]["pos"][1] > pv_02["camera_start"]["pos"][1]

    res_01 = render_previs_keyframes(pv_01, out_dir=tmp_path, cut_id="S01", backend="workbench_cpu")
    res_02 = render_previs_keyframes(pv_02, out_dir=tmp_path, cut_id="S02", backend="workbench_cpu")
    assert res_01["visibility_gate_start"]["passed"] is True
    assert res_02["visibility_gate_end"]["passed"] is True
    for p_str in (res_01["start_png"], res_01["end_png"], res_02["end_png"]):
        img = cv2.imread(p_str, cv2.IMREAD_COLOR)
        assert img is not None and img.shape in ((960, 540, 3), (1920, 1080, 3))


def _build_r72_24_clip_plan_and_sentences() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    sentences: list[dict[str, Any]] = []
    for idx in range(1, 19):
        if idx == 1:
            txt = "In 2002 at Harvard University, photography students surrendered their favorite darkroom print forever!"
        elif idx == 9:
            txt = "Hold on, why did keeping a five-day swap option make students miserable?"
        else:
            txt = f"Harvard researchers tracked group {idx} across campus courtyards and bright darkroom trays."
        sentences.append(
            {
                "index": idx,
                "act": min(6, ((idx - 1) // 3) + 1),
                "speaker": "mini_cortex" if idx == 9 else ("researcher" if idx == 3 else "narrator"),
                "prosody_gear": "rush" if idx <= 2 else ("stamp" if idx in (11, 15, 18) else "brisk"),
                "text": txt,
            }
        )

    outdoor_locs = [
        "campus_quad_aerial_01",
        "architectural_cutaway_portal_01",
        "harvard_square_crosswalk_01",
        "campus_courtyard_steps_01",
        "outdoor_market_pavilion_01",
        "river_footbridge_walk_01",
        "city_park_bench_01",
    ]
    indoor_locs = ["lab_a", "gallery_desk_b", "kitchen_counter", "study_desk", "xray_chamber"]
    drone_moves = list(cfg.EXPRESSIVE_V8_DRONE_CAMERA_MOVES)
    other_moves = ["gentle_push_in", "orbital_3d_arc_sweep", "locked_tripod", "clean_pullback_reveal"]

    clips: list[dict[str, Any]] = []
    for c_idx in range(1, 25):
        s_idx = min(18, ((c_idx - 1) * 18 // 24) + 1)
        if c_idx == 1:
            loc = "campus_quad_aerial_01"
            gram = "expressive_exterior_establishing"
            cam = "drone_aerial_approach"
            rwt = "harvard_memorial_yard"
        elif c_idx == 2:
            loc = "architectural_cutaway_portal_01"
            gram = "architectural_cutaway_portal"
            cam = "fpv_window_portal_breach"
            rwt = "harvard_memorial_yard"
        elif c_idx == 14:
            loc = "xray_chamber"
            gram = "expressive_xray_brain"
            cam = "gentle_push_in"
            rwt = ""
        elif c_idx == 16:
            loc = "campus_courtyard_steps_01"
            gram = "expressive_cameo_world"
            cam = "locked_tripod"
            rwt = ""
        elif c_idx % 2 == 1:
            loc = outdoor_locs[(c_idx // 2) % len(outdoor_locs)]
            gram = "expressive_exterior_establishing"
            cam = drone_moves[(c_idx // 2) % len(drone_moves)]
            rwt = "harvard_square_brick" if "square" in loc else ""
        else:
            loc = indoor_locs[(c_idx // 2) % len(indoor_locs)]
            gram = "expressive_reaction_closeup" if cam == "locked_tripod" else "expressive_vinyl_world"
            cam = other_moves[(c_idx // 2) % len(other_moves)]
            if cam == "locked_tripod":
                gram = "expressive_reaction_closeup"
            rwt = "harvard_darkroom_enlarger_rig" if loc == "lab_a" else ""

        clip_obj: dict[str, Any] = {
            "index": c_idx,
            "clip_number": c_idx,
            "act": sentences[s_idx - 1]["act"],
            "sentence_index": s_idx,
            "sentence_indices": [s_idx],
            "grammar": gram,
            "location_id": loc,
            "camera_move": cam,
            "transition_out": "seamless_relay_cut" if c_idx == 1 else "daisy_chain_bridge",
            "cast": ["researcher"] if gram != "expressive_xray_brain" else [],
            "cameo_easter_egg": c_idx == 16,
            "action_2beat": "Sweeps toward sunlit red-brick Harvard archway, then glides into active experiment.",
        }
        if rwt:
            clip_obj["real_world_target_id"] = rwt
        clips.append(clip_obj)

    plan: dict[str, Any] = {
        "schema": 8,
        "project_id": "v8_ep07_unit_test",
        "style_profile": "expressive_25d_v8",
        "format_profile": "shorts_expressive_v8",
        "voice_preset": "elevenlabs_v4",
        "opening_mode": "case_stamp",
        "core_reveal_sentence_index": 14,
        "r72_mode": True,
        "real_world_targets": ["harvard", "harvard_square", "darkroom_enlarger"],
        "thumbnail": {
            "profile": "in_skull_cutaway_split_v4",
            "top_split_label": "LOCKED CHOICE",
            "bottom_split_label": "REFUND TRAP",
            "in_skull_split_prompt": (
                "Bright high-key 50/50 horizontal split portrait of the same expressive young woman, "
                "top half calm satisfied smile with serene cyan-blue 3D glass brain cutaway, "
                "bottom half stressed furrowed brow holding receipts with fiery crimson-red 3D glass brain cutaway."
            ),
            "render_micro_labels": True,
            "cover_sentence_index": 1,
        },
        "clips": clips,
    }
    return sentences, plan


def test_r72_k0_k1_k2_contract_validation_and_frozen_backward_compatibility(tmp_path: Path) -> None:
    sentences, plan = _build_r72_24_clip_plan_and_sentences()
    populated = populate_expressive_v8_reference_contract(plan)

    c1, c2 = populated["clips"][0], populated["clips"][1]
    assert c1["flow_input_mode"] == "VIDEO_FRAMES"
    assert c2["flow_input_mode"] == "VIDEO_FRAMES"
    assert str(c1["start_frame_image"]).endswith("kf_01_r72_k0_aerial_9x16.png")
    assert str(c1["end_frame_image"]).endswith("kf_01_r72_k1_facade_9x16.png")
    assert c1["end_frame_image"] == c2["start_frame_image"], "Shared K1 relay frame must match 1:1!"
    assert str(c2["end_frame_image"]).endswith("kf_02_r72_k2_cutaway_9x16.png")
    assert c1["transition_out"] == "seamless_relay_cut"

    rep = validate_r72_open_world_drone_and_real_refs(populated, script_doc={"sentences": sentences})
    assert rep["passed"] is True, f"Valid R72 plan failed gate: {rep}"

    # Mutate Clip 1 to indoor lab -> must fail R72-1
    bad_indoor_open = json.loads(json.dumps(populated))
    bad_indoor_open["clips"][0]["location_id"] = "lab_a"
    bad_indoor_open["clips"][0]["grammar"] = "expressive_vinyl_world"
    bad_indoor_open["clips"][0]["camera_move"] = "gentle_push_in"
    bad_indoor_open["clips"][0].pop("real_world_target_id", None)
    rep_bad1 = validate_r72_open_world_drone_and_real_refs(bad_indoor_open, script_doc={"sentences": sentences})
    assert rep_bad1["passed"] is False
    assert any("R72-1" in issue for issue in rep_bad1["issues"])

    # Mutate 3 consecutive clips to same indoor room -> must fail R72-3
    bad_consec = json.loads(json.dumps(populated))
    for k in (3, 4, 5):
        bad_consec["clips"][k]["location_id"] = "lab_a"
        bad_consec["clips"][k]["grammar"] = "expressive_vinyl_world"
        bad_consec["clips"][k].pop("real_world_target_id", None)
    rep_bad3 = validate_r72_open_world_drone_and_real_refs(bad_consec, script_doc={"sentences": sentences})
    assert rep_bad3["passed"] is False
    assert any("R72-3" in issue for issue in rep_bad3["issues"])

    # Verify frozen Ep #4..#6 projects remain 100% exempt from retroactive R72 failure
    for frozen_pid in ("v8_ep04_patient_sm_fearless_amygdala", "v8_ep05_ucl_tickle_delay_robot", "v8_ep06_bedtime_todo_list_sleep"):
        assert cfg.is_r72_open_world_v8_plan({"project_id": frozen_pid, "style_profile": "expressive_25d_v8"}, project_id=frozen_pid) is False


def test_r72_fast_cut_dynamic_edl_and_qa_contract_bounds(tmp_path: Path) -> None:
    sentences, plan = _build_r72_24_clip_plan_and_sentences()
    populated = populate_expressive_v8_reference_contract(plan)

    # Synthesize realistic ~76s sentence timeline across 18 sentences (~4.2s per sentence + gaps)
    timings: list[dict[str, Any]] = []
    cursor = 0.0
    for idx in range(1, 19):
        dur = 3.6 if idx <= 2 else 3.9
        timings.append(
            {
                "index": idx,
                "sentence_index": idx,
                "start_sec": round(cursor, 3),
                "end_sec": round(cursor + dur, 3),
                "duration_sec": dur,
                "text": sentences[idx - 1]["text"],
            }
        )
        cursor += dur + 0.34
    total_audio = round(cursor + 0.20, 3)

    # Create 30 clip slots (18 sentence clips + 12 spare visual B-roll cuts so fast-cut subdivision kicks in!)
    while len(populated["clips"]) < 30:
        nxt_i = len(populated["clips"]) + 1
        s_bind = min(18, (nxt_i % 18) + 1)
        populated["clips"].append(
            {
                "index": nxt_i,
                "clip_number": nxt_i,
                "act": 4,
                "sentence_index": s_bind,
                "sentence_indices": [s_bind],
                "grammar": "expressive_exterior_establishing" if nxt_i % 2 == 0 else "expressive_vinyl_world",
                "location_id": "harvard_square_crosswalk_01" if nxt_i % 2 == 0 else "gallery_desk_b",
                "camera_move": "drone_high_orbit_drop" if nxt_i % 2 == 0 else "gentle_push_in",
                "transition_out": "daisy_chain_bridge",
                "cast": ["researcher"],
                "cameo_easter_egg": False,
                "action_2beat": "Tracks briskly across sunlit brick courtyard toward darkroom bench.",
            }
        )

    clip_files = [tmp_path / f"clip_{i:02d}.mp4" for i in range(1, len(populated["clips"]) + 1)]
    edl = build_v7_dynamic_edl(
        visual_plan=populated,
        sentence_spans=timings,
        clip_files=clip_files,
        speech_end_sec=round(cursor - 0.34, 3),
        total_duration_sec=total_audio,
    )
    cuts = edl["cuts"]
    assert len(cuts) >= cfg.SHORTS_EXPRESSIVE_V8_CUT_COUNT_MIN, f"Expected >= 28 fast cuts, got {len(cuts)}"
    assert cuts[0]["duration_sec"] <= cfg.EXPRESSIVE_V8_FIRST_CUT_MAX_SEC + 0.05
    assert cuts[0]["transition_out"] == "seamless_relay_cut"
    avg_cut = sum(float(c["duration_sec"]) for c in cuts) / len(cuts)
    assert cfg.EXPRESSIVE_V8_AVG_CUT_MIN_SEC <= avg_cut <= cfg.EXPRESSIVE_V8_AVG_CUT_MAX_SEC, (
        f"Expected avg_cut in [2.05, 3.30]s, got {avg_cut:.3f}s"
    )

    sent_texts = [s["text"] for s in sentences]
    rendered_prompts = build_diorama_v7_prompts(populated, sent_texts)
    contract = compile_episode_qa_contract(
        populated,
        sent_texts,
        rendered_prompts,
        script_doc={"schema": 8, "style_profile": "expressive_25d_v8", "sentences": sent_texts},
    )
    tt = contract["tempo_targets"]
    assert tt["first_cut_max_sec"] == cfg.EXPRESSIVE_V8_FIRST_CUT_MAX_SEC
    assert tt["first_15s_min_cuts"] == cfg.EXPRESSIVE_V8_FIRST_15S_MIN_CUTS
    assert tt["max_single_sentence_cut_sec"] == cfg.EXPRESSIVE_V8_MAX_CUT_SEC
    assert [tt["avg_cut_min_sec"], tt["avg_cut_max_sec"]] == list(cfg.EXPRESSIVE_V8_AVG_CUT_TARGET_RANGE)
