"""
Rule R82 Regression Suite:
  - Harmonizes R72 (fast open-world human cuts + mandatory institution aerial drone) and R76/R78-M/R81
    (poised 4.20–6.80s anti-spin 3D brain cuts across 42–58% share) with zero rule-vs-rule conflicts.
  - Preserves PRE_R82_FROZEN_V8_PROJECTS (Ep #1..#12) and synthetic test fixtures unchanged.
  - Verifies:
      1. Missing Act-1 university aerial drone shot is caught (`[r82_institution_drone]`).
      2. Brain clips are excluded from human `outdoor_count` (never >100% outdoor ratio).
      3. Sluggish >4.25s human cuts and frantic `racing backward` brain tokens are blocked.
      4. Crisp 2-beat `human_action_relay` cuts (2.1–2.7s) + poised 5.0–5.6s brain cuts (~51% share)
         pass `build_v7_dynamic_edl`, `validate_r76_brain_simulator_and_pacing_contract`, and `compile_episode_qa_contract`.
"""

from __future__ import annotations

from pathlib import Path

import pipeline.config as cfg
from pipeline.assembler import build_v7_dynamic_edl
from pipeline.episode_qa import compile_episode_qa_contract
from pipeline.prompt_builder import validate_flow_prompts, validate_r72_open_world_drone_and_real_refs
from pipeline.prompt_gate import validate_r76_brain_simulator_and_pacing_contract


def test_r82_activation_and_frozen_episode_preservation() -> None:
    for frozen_pid in (
        "v8_ep08_capgras_imposter_delusion_r77",
        "v8_ep09_maguire_london_taxi_hippocampus",
        "v8_ep10_sleep_pill_brain_wash",
        "v8_ep11_open_label_placebo_pain",
        "v8_ep12_doorway_effect_memory",
        "v8_ep09_test_r80",
        "v8_ep99_r79m_unit_check",
    ):
        assert cfg.is_r82_dual_speed_pacing_plan({"schema": 8}, project_id=frozen_pid) is False

    assert cfg.is_r82_dual_speed_pacing_plan({"schema": 8}, project_id="v8_ep09_maguire_london_taxi_hippocampus_r82") is True
    assert cfg.is_r82_dual_speed_pacing_plan({"schema": 8}, project_id="v8_ep13_next_episode") is True
    assert cfg.is_r82_dual_speed_pacing_plan({"schema": 8, "r82_mode": True}, project_id="custom_proj") is True


def test_r82_catches_missing_university_drone_and_frantic_brain_tokens() -> None:
    script_doc = {
        "project_id": "v8_ep09_maguire_london_taxi_hippocampus_r82",
        "r82_mode": True,
        "opening_mode": "myth_flip_claim",
        "sentences": [
            "Ditching phone maps reshapes your adult brain!",
            "To prove it, University College London doctors scanned cabbies.",
            "Trainees ride mopeds in the rain across London.",
        ] + [f"Sentence {i}." for i in range(4, 18)],
        "sentence_speakers": ["narrator"] * 17,
        "data_stamps": [{"sentence_index": 13}],
    }
    bad_clips = [
        {
            "clip_number": 1,
            "sentence_index": 1,
            "grammar": "expressive_vinyl_world",
            "camera_move": "orbital_3d_arc_sweep",
            "location_id": "london_cab_dashboard",
            "environment": "classic black London taxicab seat",
        },
        {
            "clip_number": 2,
            "sentence_index": 2,
            "grammar": "expressive_exterior_establishing",
            "camera_move": "gentle_push_in",
            "location_id": "ucl_garden_walk",
            "environment": "sunlit London gravel garden walkway",
            "real_world_target_id": None,
        },
    ] + [
        {
            "clip_number": i,
            "sentence_index": min(17, i),
            "grammar": "brain_simulator_3d" if i in range(6, 14) else "expressive_exterior_establishing",
            "camera_move": "sensory_to_brain_drone" if i in range(6, 14) else "drone_landmark_ascend",
            "brain_clip": i in range(6, 14),
            "brain_region": "hippocampus" if i in range(6, 14) else None,
            "scene": "Pulses racing backward through the brain" if i == 6 else "Calm exterior London street",
            "environment": "sunlit London street",
            "real_world_target_id": "charing_cross_black_cabs",
        }
        for i in range(3, 21)
    ]
    bad_plan = {
        "schema": 8,
        "project_id": "v8_ep09_maguire_london_taxi_hippocampus_r82",
        "style_profile": "expressive_25d_v8",
        "r82_mode": True,
        "real_world_targets": [
            {"target_id": "ucl_wilkins_portico", "category": "institution"},
            {"target_id": "charing_cross_black_cabs", "category": "urban_setting"},
        ],
        "clips": bad_clips,
    }
    r72_rep = validate_r72_open_world_drone_and_real_refs(bad_plan, script_doc=script_doc)
    assert any("[r82_institution_drone]" in iss for iss in r72_rep["issues"]), r72_rep
    assert r72_rep["outdoor_ratio"] <= 1.0, f"Brain clips leaked into outdoor_ratio: {r72_rep}"

    r76_iss = validate_r76_brain_simulator_and_pacing_contract(
        bad_plan,
        bad_clips,
        script_doc=script_doc,
        project_id=bad_plan["project_id"],
    )
    assert any("[r82_calm_brain]" in x for x in r76_iss), r76_iss
    assert any("[r82_data_stamps]" in x for x in r76_iss), r76_iss


def test_r82_dual_speed_edl_fast_human_relays_and_poised_51pct_brain(tmp_path: Path) -> None:
    # 17 sentences -> 23 clips (15 crisp human cuts ~2.55s + 8 poised brain cuts ~5.2s = ~52% brain share!)
    clip_files = []
    for i in range(1, 24):
        p = tmp_path / f"clip_{i}.mp4"
        p.write_bytes(b"\x00" * 1024)
        clip_files.append(p)

    sent_durs = [4.4, 4.9, 4.7, 4.2, 4.9, 5.2, 5.2, 5.2, 4.7, 5.0, 5.6, 5.3, 3.9, 4.7, 5.2, 3.5, 4.0]
    spans = []
    t_cur = 0.0
    for idx, d in enumerate(sent_durs, start=1):
        spans.append({"sentence_index": idx, "start_sec": round(t_cur, 4), "end_sec": round(t_cur + d, 4)})
        t_cur += d

    brain_sents = {5, 6, 7, 8, 11, 12, 14, 15}
    relay_sents = {1, 2, 3, 4, 9, 10}
    vp_clips = []
    c_no = 1
    for s_i in range(1, 18):
        if s_i in relay_sents:
            for b_i in (1, 2):
                is_sp = s_i in (9, 10)
                cam = (
                    ("drone_aerial_approach" if b_i == 1 else "fpv_window_portal_breach")
                    if s_i == 2
                    else (("drone_landmark_ascend" if b_i == 1 else "topdown_3d_route_glide") if is_sp else "gentle_push_in")
                )
                vp_clips.append(
                    {
                        "id": c_no,
                        "clip_number": c_no,
                        "sentence_index": s_i,
                        "end_sentence_index": s_i,
                        "beat_index": b_i,
                        "beat_weight": 0.5,
                        "grammar": "spatial_3d_arrow_diorama" if is_sp else "expressive_exterior_establishing",
                        "camera_move": cam,
                        "human_action_relay": not is_sp,
                        "spatial_relay_cut": is_sp,
                        "location_id": f"loc_{s_i}_{b_i}",
                        "environment": "sunlit outdoor London Portland-stone plaza",
                        "real_world_target_id": "ucl_wilkins_portico" if (s_i == 2 and b_i == 1) else "charing_cross_black_cabs",
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
                    "beat_index": 1,
                    "grammar": "brain_simulator_3d",
                    "camera_move": "circuit_cooperation_drone",
                    "brain_clip": True,
                    "brain_region": "hippocampus",
                    "start_brain_region": "hippocampus",
                    "end_brain_region": "primary visual cortex",
                    "scene": "Poised 3D MNI152 coronal brain cutaway under 12 degrees of gentle micro-parallax",
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
                    "beat_index": 1,
                    "grammar": "expressive_vinyl_world",
                    "camera_move": "pan_right",
                    "location_id": "ucl_mri_suite" if s_i in (13, 17) else "ucl_test_desk",
                    "environment": "bright UCL brain imaging suite",
                }
            )
            c_no += 1

    assert len(vp_clips) == 23
    script_doc = {
        "schema": 8,
        "project_id": "v8_ep09_maguire_london_taxi_hippocampus_r82",
        "style_profile": "expressive_25d_v8",
        "r82_mode": True,
        "sentences": [
            "Ditching phone maps reshapes your adult brain!",
            "To prove it, University College London doctors scanned cabbies.",
        ] + [f"Sentence {i}." for i in range(3, 18)],
        "sentence_speakers": ["narrator"] * 17,
        "data_stamps": [{"sentence_index": 13}, {"sentence_index": 17}],
    }
    visual_plan = {
        "schema": 8,
        "project_id": "v8_ep09_maguire_london_taxi_hippocampus_r82",
        "profile": "neuro_diorama",
        "style_profile": "expressive_25d_v8",
        "format_profile": "shorts_expressive_v8",
        "r72_mode": True,
        "r76_mode": True,
        "r82_mode": True,
        "zero_clip_reuse": True,
        "real_world_targets": [
            {"target_id": "ucl_wilkins_portico", "category": "institution"},
            {"target_id": "charing_cross_black_cabs", "category": "urban_setting"},
        ],
        "clips": vp_clips,
    }
    edl = build_v7_dynamic_edl(
        total_duration_sec=round(t_cur + 0.20, 4),
        speech_end_sec=round(t_cur, 4),
        sentence_spans=spans,
        clip_files=clip_files,
        visual_plan=visual_plan,
        script_doc=script_doc,
        virtual_clip_duration_sec=8.0,
    )
    assert edl["cut_count"] == 23
    human_durs = [c["duration_sec"] for c in edl["cuts"] if c["grammar"] != "brain_simulator_3d"]
    brain_durs = [c["duration_sec"] for c in edl["cuts"] if c["grammar"] == "brain_simulator_3d"]
    assert max(human_durs) <= cfg.R82_HUMAN_MAX_CUT_SEC + 0.01, human_durs
    assert min(human_durs) >= cfg.R82_HUMAN_MIN_CUT_SEC - 0.01, human_durs
    assert min(brain_durs) >= cfg.R82_BRAIN_MIN_CUT_SEC - 0.01, brain_durs
    brain_share = sum(brain_durs) / sum(c["duration_sec"] for c in edl["cuts"])
    assert 0.48 <= brain_share <= 0.56, f"Expected ~51% brain share, got {brain_share:.3f}"

    r76_issues = validate_r76_brain_simulator_and_pacing_contract(
        visual_plan,
        vp_clips,
        script_doc=script_doc,
        project_id=visual_plan["project_id"],
        edl=edl,
    )
    assert r76_issues == [], r76_issues

    r72_rep = validate_r72_open_world_drone_and_real_refs(visual_plan, script_doc=script_doc)
    assert r72_rep["passed"] is True, r72_rep

    contract = compile_episode_qa_contract(visual_plan, script_doc["sentences"], vp_clips, script_doc=script_doc)
    assert contract["tempo_targets"]["first_cut_max_sec"] == cfg.R82_FIRST_CUT_MAX_SEC
    assert contract["tempo_targets"]["first_15s_min_cuts"] == cfg.R82_FIRST_15S_MIN_CUTS


def test_r82_hospital_clinic_drone_missing_data_stamps_speed_clamp_and_side_by_side_qa(tmp_path: Path) -> None:
    import cv2
    import numpy as np

    from pipeline.stamp_overlay import validate_data_stamps
    from pipeline.prompt_builder import build_expressive_v8_prompts
    from pipeline.ref_qa import inspect_single_reference_image

    # 1. Clinical hospital/clinic case study WITHOUT institution target must NOT bypass [r82_institution_drone] via street drone!
    hosp_script = {
        "project_id": "v8_ep13_mayo_clinic_pain_study",
        "r82_mode": True,
        "opening_mode": "myth_flip_claim",
        "sentences": [
            "Open-label sugar pills still quiet real nerve pain!",
            "Wait, how can a fake pill work when you know it's fake?",
            "Doctors at Mayo Clinic tested patients in chronic back pain.",
            "Every patient knew the bottle held zero medicine.",
        ] + [f"Sentence {i}." for i in range(5, 19)],
        "sentence_speakers": ["narrator"] * 18,
        # Intentionally omit data_stamps entirely (None) to test missing-key loophole!
    }
    street_only_clips = [
        {
            "clip_number": i,
            "sentence_index": min(18, i),
            "grammar": "expressive_exterior_establishing" if i <= 4 else ("brain_simulator_3d" if i in range(6, 13) else "expressive_vinyl_world"),
            "camera_move": "drone_landmark_ascend" if i in (2, 3) else ("circuit_cooperation_drone" if i in range(6, 13) else "gentle_push_in"),
            "brain_clip": i in range(6, 13),
            "brain_region": "hippocampus" if i in range(6, 13) else None,
            "environment": "sunlit downtown street plaza",
            "real_world_target_id": "downtown_street_plaza",
            "crop_zoom": 1.18 if i == 1 else None,
            "flight_speed_ramp": 1.28 if i == 2 else None,
            "full_trajectory_span": i == 2,
        }
        for i in range(1, 19)
    ]
    street_only_plan = {
        "schema": 8,
        "project_id": "v8_ep13_mayo_clinic_pain_study",
        "style_profile": "expressive_25d_v8",
        "r82_mode": True,
        "real_world_targets": [{"target_id": "downtown_street_plaza", "category": "urban_setting"}],
        "clips": street_only_clips,
    }
    r72_hosp = validate_r72_open_world_drone_and_real_refs(street_only_plan, script_doc=hosp_script)
    assert any("[r82_institution_drone]" in iss for iss in r72_hosp["issues"]), r72_hosp

    # Adding category='institution' target on S04 (R73-2 credibility bridge) passes cleanly!
    hosp_ok_plan = {
        **street_only_plan,
        "real_world_targets": [
            {"target_id": "mayo_clinic_plaza", "category": "institution"},
            {"target_id": "downtown_street_plaza", "category": "urban_setting"},
        ],
        "clips": [
            ({**c, "sentence_index": 4, "camera_move": "drone_aerial_approach", "real_world_target_id": "mayo_clinic_plaza"} if c["clip_number"] == 4 else c)
            for c in street_only_clips
        ],
    }
    r72_hosp_ok = validate_r72_open_world_drone_and_real_refs(hosp_ok_plan, script_doc=hosp_script)
    assert not any("[r82_institution_drone]" in iss for iss in r72_hosp_ok["issues"]), r72_hosp_ok

    # 2. Omitted data_stamps (None) is caught by BOTH R76/R82 validator and validate_data_stamps
    r76_missing_ds = validate_r76_brain_simulator_and_pacing_contract(
        hosp_ok_plan, hosp_ok_plan["clips"], script_doc=hosp_script, project_id=hosp_ok_plan["project_id"]
    )
    assert any("[r82_data_stamps]" in x for x in r76_missing_ds), r76_missing_ds
    ds_errs = validate_data_stamps(hosp_script, hosp_script["sentences"])
    assert any("[r82_data_stamps]" in x for x in ds_errs), ds_errs

    # 3. clip_count_range_for_profile & build_expressive_v8_prompts preserve R82 range + crop_zoom / flight_speed_ramp
    assert cfg.clip_count_range_for_profile("shorts_expressive_v8", plan=hosp_ok_plan, script_doc=hosp_script) == cfg.R82_CLIP_COUNT_RANGE
    built = build_expressive_v8_prompts(hosp_ok_plan, hosp_script["sentences"])
    assert built[0]["crop_zoom"] == 1.18
    assert built[1]["flight_speed_ramp"] == 1.28

    # 4. EDL speed clamp: campus drone cut with full_trajectory_span=True & flight_speed_ramp=1.28 stays ~1.28x (never 2.54x!)
    cfiles = []
    for i in range(1, 19):
        cp = tmp_path / f"c_{i}.mp4"
        cp.write_bytes(b"\x00" * 512)
        cfiles.append(cp)
    spans = [{"sentence_index": i, "start_sec": (i - 1) * 4.2, "end_sec": i * 4.2} for i in range(1, 19)]
    edl_hosp = build_v7_dynamic_edl(
        total_duration_sec=18 * 4.2 + 0.2,
        speech_end_sec=18 * 4.2,
        sentence_spans=spans,
        clip_files=cfiles,
        visual_plan=hosp_ok_plan,
        script_doc={**hosp_script, "data_stamps": []},
        virtual_clip_duration_sec=8.0,
    )
    drone_cut = edl_hosp["cuts"][1]
    assert drone_cut["main_speed"] <= cfg.R79M_HUMAN_CUT_MAX_MAIN_SPEED + 0.01, drone_cut

    # 5. Q_side_by_side_complete_brains rejects edge-sliced half-brains and accepts complete side-by-side brains
    sbs_spec = {
        "ref_id": "ref_sbs",
        "category": "brain_anchor",
        "setting": "brain_studio",
        "style_profile": "expressive_25d_v8",
        "side_by_side_brain_compare": True,
    }
    bad_img = np.full((1920, 1080, 3), (15, 8, 5), dtype=np.uint8)
    # Sliced half-brains bleeding off X=0 and X=1080
    cv2.ellipse(bad_img, (40, 1020), (360, 420), 0, 0, 360, (175, 175, 190), -1)
    cv2.circle(bad_img, (180, 1120), 90, (90, 86, 255), -1)
    cv2.ellipse(bad_img, (1040, 1020), (360, 420), 0, 0, 360, (150, 155, 165), -1)
    bad_p = tmp_path / "bad_sbs.png"
    cv2.imwrite(str(bad_p), bad_img)
    rep_bad = inspect_single_reference_image(bad_p, sbs_spec)
    assert rep_bad["axes_q1_to_q7"]["Q_side_by_side_complete_brains"] is False, rep_bad
    assert "Q_side_by_side_complete_brains" in rep_bad["failed_axes"], rep_bad

    good_img = np.full((1920, 1080, 3), (18, 12, 8), dtype=np.uint8)
    # Soft studio radial vignette + two complete multi-tone textured brains cleanly inside X=80..1000
    rng = np.random.default_rng(42)
    yy_g, xx_g = np.mgrid[0:1920, 0:1080]
    rad_glow = np.clip(18.0 * np.exp(-(((xx_g - 540.0) / 480.0) ** 2 + ((yy_g - 1020.0) / 520.0) ** 2)), 0.0, 18.0).astype(np.uint8)
    good_img[:, :, 0] += rad_glow
    good_img[:, :, 1] += (rad_glow // 2)
    noise = rng.integers(0, 75, size=(1920, 1080, 3), dtype=np.uint8)
    for cx_b, is_taxi in ((295, True), (785, False)):
        mask_b = np.zeros((1920, 1080), dtype=np.uint8)
        cv2.ellipse(mask_b, (cx_b, 1020), (195, 250), 0, 0, 360, 255, -1)
        shade = np.clip(125.0 + 60.0 * ((1020.0 - yy_g) / 250.0), 80.0, 210.0).astype(np.uint8)
        good_img[mask_b > 0, 0] = np.clip(shade[mask_b > 0] + noise[mask_b > 0, 0] // 2, 0, 255)
        good_img[mask_b > 0, 1] = np.clip(shade[mask_b > 0] + noise[mask_b > 0, 1] // 2, 0, 255)
        good_img[mask_b > 0, 2] = np.clip(shade[mask_b > 0] + noise[mask_b > 0, 2] // 2, 0, 255)
        for sulc_y in range(820, 1230, 32):
            cv2.line(good_img, (cx_b - 135, sulc_y), (cx_b + 135, sulc_y + 14), (245, 212, 76) if is_taxi else (118, 124, 132), 4)
        if is_taxi:
            cv2.ellipse(good_img, (cx_b, 1110), (74, 48), -15, 0, 360, (92, 86, 255), -1)
        else:
            cv2.ellipse(good_img, (cx_b, 1110), (38, 16), -15, 0, 360, (138, 132, 126), -1)
    good_p = tmp_path / "good_sbs.png"
    cv2.imwrite(str(good_p), good_img, [int(cv2.IMWRITE_PNG_COMPRESSION), 0])
    rep_good = inspect_single_reference_image(good_p, sbs_spec)
    assert rep_good["axes_q1_to_q7"]["Q_side_by_side_complete_brains"] is True, rep_good
    assert rep_good["passed"] is True, rep_good


def test_r82_drone_r79m_decoupling_and_native_sbs_dual_brain_support() -> None:
    from pipeline.anatomy_overlay import resolve_anatomy_callout_windows
    from pipeline.anatomy_map import load_atlas_manifest
    from pipeline.depiction_rules import validate_expressive_v8_scene

    # 1. Aerial campus drone shot NEVER conflicts with R79-M human action verb check even under expressive_vinyl_world
    drone_errs = validate_expressive_v8_scene(
        "Sweeping 3D aerial approach glides over sunlit classical stone columns and green quad lawns. Silent voice track.",
        grammar="expressive_vinyl_world",
        camera_move="drone_aerial_approach",
    )
    assert not any("r79m_missing_action_verb" in e for e in drone_errs), drone_errs

    # 2. Native side_by_side_brain_compare camera plan & XL R81 r78m_dual 'vs' callout auto-synthesis
    mf = load_atlas_manifest()
    assert isinstance(mf, dict) and mf

    edl_sbs = {
        "cuts": [
            {
                "cut_index": 17,
                "clip_index": 17,
                "out_start_sec": 52.0,
                "out_end_sec": 57.2,
                "grammar": "brain_simulator_3d",
                "side_by_side_brain_compare": True,
                "left_cohort_label": "Taxi Hippocampus",
                "right_cohort_label": "Bus Hippocampus",
                "callout_gloss": "Giant Rear Map  vs  Flat Baseline",
            }
        ]
    }
    windows = resolve_anatomy_callout_windows(edl_sbs)
    assert len(windows) == 1
    assert windows[0]["callout_mode"] == "r78m_dual"
    assert windows[0]["r78m_callout"]["arrow"] == "vs"
    assert windows[0]["r78m_callout"]["left_lbl"] == "Taxi Hippocampus"
    assert windows[0]["r78m_callout"]["right_lbl"] == "Bus Hippocampus"
    assert windows[0]["r78m_callout"]["left_xy"] == [265, 1035]
    assert windows[0]["r78m_callout"]["right_xy"] == [815, 1035]


def test_r82_veo31_four_grammar_patches_dedup_delta_drone_sbs_and_arrow() -> None:
    from pipeline.prompt_builder import _prepend_concise_cast_subject, build_expressive_v8_prompts
    from pipeline.arrow_guide import build_r80_flow_scene_clause

    # 1. Duplicate 'First, the 2.5D ...' subject bug eliminated + <=9-word Delta-Only cast compression
    deduped = _prepend_concise_cast_subject(
        "First, the 2.5D sleeper man in a burgundy cardigan lifts the amber bottle.",
        "the 2.5D middle-aged sleeper man in a burgundy cotton cardigan seated on the bed edge with a smooth head",
        "expressive_vinyl_world",
        "orbital_3d_arc_sweep",
    )
    assert "first" not in deduped.lower(), deduped
    assert deduped.lower().count("sleeper man") == 1, deduped

    compressed = _prepend_concise_cast_subject(
        "lifts the amber bottle and sets the glass down.",
        "the 2.5D middle-aged sleeper man in a burgundy cotton cardigan seated on the bed edge with a smooth head",
        "expressive_vinyl_world",
        "orbital_3d_arc_sweep",
    )
    assert "seated on the bed edge" not in compressed.lower(), compressed
    assert "with a smooth" not in compressed.lower(), compressed

    # 2. Campus aerial drone gets 'blank unlabeled stone facades' & SBS dual-brain gets <=6 deg front-coronal lock
    plan = {
        "schema": 8,
        "style_profile": "expressive_25d_v8",
        "r82_mode": True,
        "clips": [
            {
                "clip_number": i,
                "sentence_index": i,
                "grammar": "expressive_exterior_establishing" if i == 1 else ("brain_simulator_3d" if i == 2 else "expressive_vinyl_world"),
                "camera_move": "drone_aerial_approach" if i == 1 else ("circuit_cooperation_drone" if i == 2 else "gentle_push_in"),
                "reference_image": f"03_visuals/reference_images/ref_{i}.png",
                "action": "High-altitude 3D aerial approach descending over sunlit rooftops toward the brick courtyard" if i == 1 else "The 2.5D researcher presses the start button",
                "r78m_flow_prompt": "Sweeping 3D lateral orbit across two matched brains" if i == 2 else None,
                "side_by_side_brain_compare": i == 2,
            }
            for i in range(1, 19)
        ],
    }
    built = build_expressive_v8_prompts(plan, [f"Sentence {i}." for i in range(1, 19)])
    assert "blank unlabeled stone facades" in built[0]["prompt"].lower(), built[0]["prompt"]
    assert "sweeping 3d lateral orbit" not in built[1]["prompt"].lower(), built[1]["prompt"]
    assert "under 6 degrees of subtle single-plane micro-parallax" in built[1]["prompt"].lower(), built[1]["prompt"]

    # 3. R80 spatial arrow tactile ground-contact phrasing
    arrow_clause = build_r80_flow_scene_clause("fixed_linear_corridor", cut_phase="topdown_arrow")
    assert "resting flush on the unmarked ground plane" in arrow_clause.lower(), arrow_clause
    assert "blank unlabeled miniature architecture" in arrow_clause.lower(), arrow_clause


