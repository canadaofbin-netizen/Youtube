"""
Prepares `v8_ep09_maguire_london_taxi_hippocampus` for the 16->18 cut `Rule R80` upgrade:
  1. Backs up v1 files & unpublished Scheduled draft (`7lKtSWvTmpw`) receipts to `/dev/shm/aab_scratch/ep09_v1_backup/`.
  2. Shifts `clip_11.mp4..clip_16.mp4` -> `clip_13.mp4..clip_18.mp4` and shifts `flow_provenance_receipt.json` indices.
  3. Replaces generic driver-seat `Clip 09` & `Clip 10` with the 4-cut `@RicksClips3000` + `신비한 건축사전` 3D arrow spatial relay (`Clip 09..12`).
  4. Rebuilds `flow_all_in_one_prompts.json` + `reference_image_specs.json` (preserving exact `r78m_flow_prompt` on brain cuts).
"""

from __future__ import annotations

import copy
import json
import shutil
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline.flow_prompt_builder import (
    build_flow_prompts,
    write_flow_prompts_json,
)
from pipeline.reference_image_qa import build_reference_image_specs


def _atomic_write_json(path: Path, payload: Any) -> None:
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def main() -> None:
    root = Path("/home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube")
    proj = root / "BCI_Shorts_Channel" / "projects" / "v8_ep09_maguire_london_taxi_hippocampus"
    bkp = Path("/dev/shm/aab_scratch/ep09_v1_backup")
    bkp.mkdir(parents=True, exist_ok=True)

    vp_path = proj / "02_script" / "visual_plan.json"
    vp_vis_path = proj / "03_visuals" / "visual_plan.json"
    sc_path = proj / "02_script" / "script.json"
    prov_path = proj / "03_visuals" / "flow_provenance_receipt.json"
    clips_dir = proj / "03_visuals" / "flow_native_clips"
    pub_dir = proj / "06_publish"

    vp = json.loads(vp_path.read_text(encoding="utf-8"))
    sc = json.loads(sc_path.read_text(encoding="utf-8"))

    # Idempotency guard: if already 18 clips, restore from backup first or re-derive from backup vp
    bkp_vp = bkp / "visual_plan_16cut.json"
    if len(vp.get("clips") or []) == 16 and not bkp_vp.exists():
        shutil.copy2(vp_path, bkp_vp)
        if prov_path.exists():
            shutil.copy2(prov_path, bkp / "flow_provenance_receipt_16cut.json")
        bkp_clips = bkp / "flow_native_clips_16cut"
        bkp_clips.mkdir(parents=True, exist_ok=True)
        for i in range(9, 17):
            cp = clips_dir / f"clip_{i}.mp4"
            if cp.exists():
                shutil.copy2(cp, bkp_clips / f"clip_{i}.mp4")

    # Move unpublished draft `7lKtSWvTmpw` upload receipts into backup so assembler/uploader don't treat v1 draft as immutable live Public
    bkp_pub = bkp / "06_publish_draft_7lKtSWvTmpw"
    bkp_pub.mkdir(parents=True, exist_ok=True)
    for r_name in ("upload_receipt.json", "studio_publish_receipt.json", "related_video_receipt.json"):
        rp = pub_dir / r_name
        if rp.exists():
            shutil.copy2(rp, bkp_pub / r_name)
            rp.unlink()

    base_vp = json.loads(bkp_vp.read_text(encoding="utf-8"))
    old_clips = base_vp["clips"]
    assert len(old_clips) == 16, f"Expected 16 base clips, got {len(old_clips)}"

    # Shift physical MP4 files 16->18 down to 11->13 from clean backup
    bkp_clips = bkp / "flow_native_clips_16cut"
    for old_i in range(16, 10, -1):
        new_i = old_i + 2
        src_mp4 = bkp_clips / f"clip_{old_i}.mp4"
        dst_mp4 = clips_dir / f"clip_{new_i}.mp4"
        shutil.copy2(src_mp4, dst_mp4)
    # Remove old clip_9..clip_12 so only new R80 clips occupy 9..12
    for rm_i in (9, 10, 11, 12):
        p_rm = clips_dir / f"clip_{rm_i}.mp4"
        if p_rm.exists():
            p_rm.unlink()

    # Shift provenance receipt indices 11..16 -> 13..18
    bkp_prov = bkp / "flow_provenance_receipt_16cut.json"
    if bkp_prov.exists():
        prov_doc = json.loads(bkp_prov.read_text(encoding="utf-8"))
        shifted_entries = []
        for entry in prov_doc.get("clips") or []:
            c_idx = int(entry.get("clip_index") or 0)
            if 1 <= c_idx <= 8:
                shifted_entries.append(copy.deepcopy(entry))
            elif 11 <= c_idx <= 16:
                ent_new = copy.deepcopy(entry)
                ent_new["clip_index"] = c_idx + 2
                shifted_entries.append(ent_new)
        prov_doc["clips"] = shifted_entries
        prov_doc["partial_receipt"] = True
        _atomic_write_json(prov_path, prov_doc)

    # Ensure real_world_targets include London Eye & London Red Bus Stop
    rw_targets = list(base_vp.get("real_world_targets") or [])
    existing_ids = {t.get("target_id") for t in rw_targets if isinstance(t, dict)}
    if "london_eye_thames_wheel" not in existing_ids:
        rw_targets.append(
            {
                "target_id": "london_eye_thames_wheel",
                "category": "urban_setting",
                "label": "London Eye Cantilevered Observation Wheel & River Thames Embankment",
                "queries": ["London Eye River Thames embankment", "London Eye South Bank"],
                "architectural_traits": "giant white cantilevered London Eye observation wheel with glass capsules rising beside the sunlit Portland-stone River Thames embankment",
            }
        )
    if "london_red_bus_stop_roundel" not in existing_ids:
        rw_targets.append(
            {
                "target_id": "london_red_bus_stop_roundel",
                "category": "urban_setting",
                "label": "London Iconic Red Bus Stop Flag Post, Glass Shelter & Double-Decker Bus Lane",
                "queries": ["London bus stop roundel red bus", "Red double-decker bus stop London"],
                "architectural_traits": "iconic London red-and-white circular bus stop flag post, glass shelter, and bright red double-decker bus aligned along a straight Portland-stone London avenue",
            }
        )

    r80_clips = [
        {
            "id": 9,
            "clip_number": 9,
            "sentence_index": 9,
            "end_sentence_index": 9,
            "beat_index": 1,
            "beat_weight": 0.497,
            "act": 4,
            "scene_id": "S09A",
            "grammar": "spatial_3d_arrow_diorama",
            "visual_grammar": "spatial_3d_arrow_diorama",
            "camera": "drone_landmark_ascend",
            "camera_move": "drone_landmark_ascend",
            "spatial_relay_cut": True,
            "arrow_3d_mode": "adaptive_landmark_zigzag",
            "flight_speed_ramp": 1.34,
            "location_id": "london_eye_south_bank",
            "environment": "sunlit London South Bank and River Thames embankment beside the giant white cantilevered London Eye wheel",
            "cast": "miniature glossy black London taxicab along the riverside embankment",
            "cast_roles": [],
            "action": "Sweeping 3D aerial arc skims close past the sunlit white London Eye wheel and Portland-stone Thames embankment as a glossy black London cab rolls briskly below, banking steeply skyward above sunlit rooftops",
            "consequence": "sunlit Portland-stone street canyons open wide below with strong foreground parallax",
            "cameo_easter_egg": False,
            "transition_to_next": "whip_pan_blur_8f",
            "transition_out": "whip_pan_blur_8f",
            "style_profile": "expressive_25d_v8",
            "schema_version": 8,
            "reference_image": "03_visuals/reference_images/kf_r80_c09_london_eye_9x16.png",
            "single_start_frame_lock": True,
            "brain_clip": False,
            "render_engine": "google_flow",
            "flow_input_mode": "VIDEO_FRAMES",
            "start_frame_image": "03_visuals/reference_images/kf_r80_c09_london_eye_9x16.png",
            "end_reference_image": None,
            "end_frame_image": None,
            "full_trajectory_span": True,
            "dual_keyframe_parallax": False,
            "real_world_target_id": "london_eye_thames_wheel",
        },
        {
            "id": 10,
            "clip_number": 10,
            "sentence_index": 9,
            "end_sentence_index": 9,
            "beat_index": 2,
            "beat_weight": 0.503,
            "act": 4,
            "scene_id": "S09B",
            "grammar": "spatial_3d_arrow_diorama",
            "visual_grammar": "spatial_3d_arrow_diorama",
            "camera": "topdown_3d_route_glide",
            "camera_move": "topdown_3d_route_glide",
            "spatial_relay_cut": True,
            "arrow_3d_mode": "adaptive_landmark_zigzag",
            "flight_speed_ramp": 1.32,
            "location_id": "london_topdown_zigzag_grid",
            "environment": "vertical 90-degree top-down miniature London Portland-stone street maze with raised matte-crimson 3D zigzag arrows",
            "cast": "miniature glossy black London taxicab weaving through side streets",
            "cast_roles": [],
            "action": "Tiny glossy black London cab weaves sharply left and right through tangled side-street turns following thick solid matte-crimson 3D extruded zigzag directional arrows resting on the sunlit asphalt with crisp dark drop shadows",
            "consequence": "raised 3D crimson arrow blocks connect white circular intersection beacons across the winding street grid",
            "cameo_easter_egg": False,
            "transition_to_next": "whip_pan_blur_8f",
            "transition_out": "whip_pan_blur_8f",
            "style_profile": "expressive_25d_v8",
            "schema_version": 8,
            "reference_image": "03_visuals/reference_images/kf_r80_c10_taxi_zigzag_topdown_9x16.png",
            "single_start_frame_lock": True,
            "brain_clip": False,
            "render_engine": "google_flow",
            "flow_input_mode": "VIDEO_FRAMES",
            "start_frame_image": "03_visuals/reference_images/kf_r80_c10_taxi_zigzag_topdown_9x16.png",
            "end_reference_image": None,
            "end_frame_image": None,
            "full_trajectory_span": True,
            "dual_keyframe_parallax": False,
            "real_world_target_id": "charing_cross_black_cabs",
        },
        {
            "id": 11,
            "clip_number": 11,
            "sentence_index": 10,
            "end_sentence_index": 10,
            "beat_index": 1,
            "beat_weight": 0.467,
            "act": 4,
            "scene_id": "S10A",
            "grammar": "spatial_3d_arrow_diorama",
            "visual_grammar": "spatial_3d_arrow_diorama",
            "camera": "drone_landmark_ascend",
            "camera_move": "drone_landmark_ascend",
            "spatial_relay_cut": True,
            "arrow_3d_mode": "fixed_linear_corridor",
            "flight_speed_ramp": 1.34,
            "location_id": "london_red_bus_stop_curb",
            "environment": "sunlit London Portland-stone avenue curb with iconic circular red bus stop post, glass shelter, and red double-decker bus",
            "cast": "miniature bright red London double-decker bus pulling away from the curb",
            "cast_roles": [],
            "action": "Sweeping 3D aerial arc skims past the circular red London bus stop flag post and glass shelter as a bright red double-decker bus pulls straight out along the sunlit lane, soaring steeply skyward above Portland-stone rooftops",
            "consequence": "the straight central London avenue stretches cleanly ahead under crisp afternoon daylight",
            "cameo_easter_egg": False,
            "transition_to_next": "seamless_relay_cut",
            "transition_out": "seamless_relay_cut",
            "style_profile": "expressive_25d_v8",
            "schema_version": 8,
            "reference_image": "03_visuals/reference_images/kf_r80_c11_bus_stop_9x16.png",
            "single_start_frame_lock": True,
            "brain_clip": False,
            "render_engine": "google_flow",
            "flow_input_mode": "VIDEO_FRAMES",
            "start_frame_image": "03_visuals/reference_images/kf_r80_c11_bus_stop_9x16.png",
            "end_reference_image": None,
            "end_frame_image": None,
            "full_trajectory_span": True,
            "dual_keyframe_parallax": False,
            "real_world_target_id": "london_red_bus_stop_roundel",
        },
        {
            "id": 12,
            "clip_number": 12,
            "sentence_index": 10,
            "end_sentence_index": 10,
            "beat_index": 2,
            "beat_weight": 0.533,
            "act": 4,
            "scene_id": "S10B",
            "grammar": "spatial_3d_arrow_diorama",
            "visual_grammar": "spatial_3d_arrow_diorama",
            "camera": "topdown_3d_route_glide",
            "camera_move": "topdown_3d_route_glide",
            "spatial_relay_cut": True,
            "arrow_3d_mode": "fixed_linear_corridor",
            "flight_speed_ramp": 1.28,
            "location_id": "london_topdown_straight_avenue",
            "environment": "vertical 90-degree top-down sunlit London boulevard with one straight matte-crimson 3D extruded arrow corridor",
            "cast": "miniature bright red London double-decker bus driving straight ahead",
            "cast_roles": [],
            "action": "Miniature bright red London double-decker bus drives straight forward without turning along one single unbroken straight solid matte-crimson 3D extruded directional arrow block casting crisp dark sunlight shadows down the central avenue",
            "consequence": "the straight 3D crimson arrow corridor passes three aligned white circular curb markers toward the top edge",
            "cameo_easter_egg": False,
            "transition_to_next": "daisy_chain_bridge",
            "transition_out": "daisy_chain_bridge",
            "style_profile": "expressive_25d_v8",
            "schema_version": 8,
            "reference_image": "03_visuals/reference_images/kf_r80_c12_bus_straight_topdown_9x16.png",
            "single_start_frame_lock": True,
            "brain_clip": False,
            "render_engine": "google_flow",
            "flow_input_mode": "VIDEO_FRAMES",
            "start_frame_image": "03_visuals/reference_images/kf_r80_c12_bus_straight_topdown_9x16.png",
            "end_reference_image": None,
            "end_frame_image": None,
            "full_trajectory_span": True,
            "dual_keyframe_parallax": False,
            "real_world_target_id": "london_red_bus_stop_roundel",
        },
    ]

    shifted_tail = []
    for c_old in old_clips[10:]:
        c_new = copy.deepcopy(c_old)
        new_num = int(c_old["clip_number"]) + 2
        c_new["id"] = new_num
        c_new["clip_number"] = new_num
        c_new["beat_index"] = new_num
        shifted_tail.append(c_new)

    new_clips = copy.deepcopy(old_clips[:8]) + r80_clips + shifted_tail
    assert len(new_clips) == 18

    # Update reference_anchors for 18 clips
    old_anchors = base_vp.get("reference_anchors") or []
    new_anchors = []
    for anc in old_anchors:
        c_no = int(anc.get("clip_number") or 0)
        if 1 <= c_no <= 8:
            new_anchors.append(copy.deepcopy(anc))
        elif 11 <= c_no <= 16:
            anc_n = copy.deepcopy(anc)
            anc_n["clip_number"] = c_no + 2
            anc_n["title"] = f"Clip {c_no + 2:02d} start anchor"
            new_anchors.append(anc_n)

    r80_anchors = [
        {
            "ref_id": "kf_r80_c09_london_eye_9x16",
            "clip_number": 9,
            "frame": "start",
            "category": "clip_keyframe_anchor",
            "role": "clip_start_keyframe",
            "scene_id": "S09A",
            "setting": "real_env",
            "location_id": "london_eye_south_bank",
            "filename": "kf_r80_c09_london_eye_9x16.png",
            "title": "Clip 09 start anchor",
            "generation_order": 2,
            "conditioned_on": [],
            "style_profile": "expressive_25d_v8",
            "prompt": r80_clips[0]["action"],
            "real_world_target_id": "london_eye_thames_wheel",
        },
        {
            "ref_id": "kf_r80_c10_taxi_zigzag_topdown_9x16",
            "clip_number": 10,
            "frame": "start",
            "category": "clip_keyframe_anchor",
            "role": "clip_start_keyframe",
            "scene_id": "S09B",
            "setting": "real_env",
            "location_id": "london_topdown_zigzag_grid",
            "filename": "kf_r80_c10_taxi_zigzag_topdown_9x16.png",
            "title": "Clip 10 start anchor",
            "generation_order": 2,
            "conditioned_on": [],
            "style_profile": "expressive_25d_v8",
            "prompt": r80_clips[1]["action"],
            "real_world_target_id": "charing_cross_black_cabs",
        },
        {
            "ref_id": "kf_r80_c11_bus_stop_9x16",
            "clip_number": 11,
            "frame": "start",
            "category": "clip_keyframe_anchor",
            "role": "clip_start_keyframe",
            "scene_id": "S10A",
            "setting": "real_env",
            "location_id": "london_red_bus_stop_curb",
            "filename": "kf_r80_c11_bus_stop_9x16.png",
            "title": "Clip 11 start anchor",
            "generation_order": 2,
            "conditioned_on": [],
            "style_profile": "expressive_25d_v8",
            "prompt": r80_clips[2]["action"],
            "real_world_target_id": "london_red_bus_stop_roundel",
        },
        {
            "ref_id": "kf_r80_c12_bus_straight_topdown_9x16",
            "clip_number": 12,
            "frame": "start",
            "category": "clip_keyframe_anchor",
            "role": "clip_start_keyframe",
            "scene_id": "S10B",
            "setting": "real_env",
            "location_id": "london_topdown_straight_avenue",
            "filename": "kf_r80_c12_bus_straight_topdown_9x16.png",
            "title": "Clip 12 start anchor",
            "generation_order": 2,
            "conditioned_on": [],
            "style_profile": "expressive_25d_v8",
            "prompt": r80_clips[3]["action"],
            "real_world_target_id": "london_red_bus_stop_roundel",
        },
    ]
    new_anchors = sorted(new_anchors + r80_anchors, key=lambda x: int(x.get("clip_number") or 0))

    updated_vp = copy.deepcopy(base_vp)
    updated_vp["r80_mode"] = True
    updated_vp["real_world_targets"] = rw_targets
    updated_vp["clips"] = new_clips
    updated_vp["reference_anchors"] = new_anchors

    _atomic_write_json(vp_path, updated_vp)
    _atomic_write_json(vp_vis_path, updated_vp)

    built_clips = build_flow_prompts(updated_vp, sc["sentences"])
    # Preserve r78m_flow_prompt override on Google-Flow brain cuts if used earlier
    for idx0, bc in enumerate(built_clips):
        vp_c = new_clips[idx0]
        if vp_c.get("r78m_flow_prompt"):
            bc["r78m_flow_prompt"] = vp_c["r78m_flow_prompt"]
        if vp_c.get("spatial_relay_cut"):
            bc["spatial_relay_cut"] = True
            bc["arrow_3d_mode"] = vp_c.get("arrow_3d_mode")
    write_flow_prompts_json(proj / "03_visuals", built_clips)

    ref_specs = build_reference_image_specs(updated_vp, sc["sentences"])
    _atomic_write_json(proj / "03_visuals" / "reference_image_specs.json", ref_specs)
    print(f"Prepared 18-clip Ep #9 visual_plan + prompts ({len(built_clips)} clips).")


if __name__ == "__main__":
    main()
