"""
Rule R85 & R86 Regression Suite (`tests/test_r85_r86_qa_honesty_and_semantic_beat.py`):
  1. YuNet Real-Frame Human Leak Gate (`e10c08`, `e09c22`, `e11c24`, `e09c07` -> `leak=True`)
     vs Clean Bald 2.5D Vinyl Keyframes (`3` canonical keyframes -> `leak=False`, zero false positives).
  2. Wikimedia Reference Blocklist (`FEMA` / `hurricane` / `damage` / `ruin` / `Waarschuwing` / `Nateglinide` / `alphabet blocks` -> rejected)
     + `NEUROANATOMY_CUTAWAY_MAP` + `/tmp/aab_real_refs/` off-screen MNI152 silhouette guide.
  3. QA Sign-Off Honesty (`unmanned_cv_verified_signoff`, `>=70%` `intended_scene` prompt-copied summary,
     stale SHA-256 review, and `auto_cv_verified_v7` keyframe sign-off -> ALL fail `posthoc-qa` / `ref-qa`).
  4. R70-M / R85 Data Stamp Integrity (`illustrative` stamp on DOI-backed episode -> fail;
     `29% != 30%` spoken contradiction -> fail; verified dossier numbers in `study` mode -> pass;
     highlight loop zero-occlusion over bar value bboxes -> pass).
  5. R85 Prompt & Anatomy Viewpoint Locks (`drone_aerial_approach` + `walk` -> `prompt-gate` fail;
     `insula` + `midsagittal` -> `prompt-gate` fail; `insula` + `lateral_opercular_retracted` -> pass;
     drift-vulnerable closeup / severed arrow -> `end_reference_image` + `Omni 1.2 Flash` `VIDEO_FRAMES`).
  6. R86 Semantic Beat Contract (`Ep12 C23`, `Ep12 C05`, `Ep12 C19`, `R84` zero-delta brain repeats,
     `>=3` consecutive proof types, `>2` reaction cuts, `decorative` proof, `metaphor_continuity_id` bridge & dwell,
     and incomplete `misconception_flip` -> ALL fail `prompt-gate`).
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import cv2
import numpy as np
import pytest

import pipeline.config as cfg
from pipeline.brain_simulator_blender import render_brain_simulator_clip
from pipeline.data_stamp_overlay import render_data_stamp_rgba_frame, validate_data_stamps
from pipeline.flow_diorama_sharded_worker import verify_v8_yunet_skin_or_hair_leak
from pipeline.flow_prompt_builder import build_expressive_v8_prompts, compose_scene_from_r86_beat_card
from pipeline.porcelain_anchor_pack import build_r85_31_brain_keyframe_spec
from pipeline.posthoc_semantic_qa import (
    auto_signoff_posthoc_semantic_review,
    run_posthoc_semantic_qa,
    validate_posthoc_semantic_review,
)
from pipeline.prompt_quality_v5 import (
    validate_r85_drone_and_viewpoint_locks,
    validate_r86_semantic_beat_contract,
)
from pipeline.real_world_reference_builder import (
    NEUROANATOMY_CUTAWAY_MAP,
    is_commons_candidate_blocked,
     purge_real_world_quarantine,
    render_mni152_guide_silhouette,
)
from pipeline.reference_image_qa import (
    auto_populate_reference_semantic_review,
    validate_semantic_review,
    write_semantic_review_template,
)
from pipeline.source_reenactment import detect_non_porcelain_human_faces_yunet, extract_dq8_scene_roi


FIXTURE_DIR = cfg.WORKSPACE_ROOT / "tests" / "fixtures" / "r85_verify"
TMP_VERIFY_DIR = Path("/tmp/aab_verify")


def _resolve_defect_fixture(name: str) -> Path:
    cand_tmp = TMP_VERIFY_DIR / name
    if cand_tmp.is_file():
        return cand_tmp
    return FIXTURE_DIR / name


def test_r85_constants_and_ssot_locks() -> None:
    assert cfg.UNMANNED_QA_SIGNOFF_DEFAULT is False
    assert cfg.R85_BRAIN_RENDER_ENGINE == "google_flow"
    assert cfg.R85_FLOW_BRAIN_SHOT_ROTATION == (
        "xray_head_dive",
        "split_cutaway",
        "sulcal_cyan_dive",
        "vessel_csf_macro",
        "1p_tract_canyon",
        "3p_shutdown_or_top_bottom",
    )
    assert cfg.is_r85_flow_31_brain_plan({"r85_mode": True}) is True
    assert cfg.is_r76_v8_plan({"r85_mode": True}, project_id="v8_ep09_maguire_london_taxi_hippocampus_r82") is False
    with pytest.raises(RuntimeError, match="retired under Rule R85"):
        render_brain_simulator_clip({"r85_mode": True, "brain_region": "hippocampus"}, "/tmp/r85_blocked.mp4")


def test_r85_1_yunet_real_defect_frames_vs_clean_bald_vinyl_keyframes() -> None:
    # 1. Unmistakable skin/hair defect frames MUST trigger HIGH_SUSPECT (leak=True)
    for fname in ("e10c08.jpg", "e09c22.jpg", "e09c07.jpg"):
        fpath = _resolve_defect_fixture(fname)
        assert fpath.is_file(), f"Missing R85 fixture {fpath}"
        bgr = cv2.imread(str(fpath), cv2.IMREAD_COLOR)
        assert bgr is not None
        roi = extract_dq8_scene_roi(bgr, is_expressive_v8=True)
        boxes = detect_non_porcelain_human_faces_yunet(roi, allow_expressive_2d_ink=False)
        assert len(boxes) >= 1, f"Expected YuNet face box on {fname}, got 0"
        leaks = [verify_v8_yunet_skin_or_hair_leak(roi, bx) for bx in boxes]
        assert any(lk for lk, _ in leaks), f"Expected HIGH_SUSPECT leak=True on {fname}, got {leaks}"

    # 1b. e11c24 (bald cream-white vinyl with subtle vinyl nose/ear contour — Tier-2 allowed):
    #     MUST NOT trigger HIGH_SUSPECT auto-regen (leak=False), while still marked is_suspect=True for Gate 2!
    f_e11 = _resolve_defect_fixture("e11c24.jpg")
    roi_e11 = extract_dq8_scene_roi(cv2.imread(str(f_e11), cv2.IMREAD_COLOR), is_expressive_v8=True)
    boxes_e11 = detect_non_porcelain_human_faces_yunet(roi_e11, allow_expressive_2d_ink=False)
    assert len(boxes_e11) >= 1
    res_e11 = [verify_v8_yunet_skin_or_hair_leak(roi_e11, bx) for bx in boxes_e11]
    assert not any(lk for lk, _ in res_e11), f"e11c24 clean vinyl triggered HIGH_SUSPECT: {res_e11}"
    assert any(m["suspect_tier"] == "MODERATE_SUSPECT" for _, m in res_e11)

    # 2. Canonical clean bald cream-white 2.5D vinyl keyframes (3 distinct images) -> MUST all stay leak=False
    clean_candidates = [
        cfg.CHANNEL_ROOT / "reference_style_anchors" / "expressive_25d_v8_refs" / "species_opt1_sheet.png",
        cfg.CHANNEL_ROOT / "reference_style_anchors" / "expressive_25d_v8_refs" / "cast_sheet_02_clinical_historical_6roles.png",
        cfg.CHANNEL_ROOT / "reference_style_anchors" / "expressive_25d_v8_refs" / "cast_sheet_03_everyday_lifestyle_6roles.png",
    ]
    checked_clean = 0
    for cp in clean_candidates:
        if not cp.is_file():
            continue
        bgr_c = cv2.imread(str(cp), cv2.IMREAD_COLOR)
        assert bgr_c is not None
        roi_c = extract_dq8_scene_roi(bgr_c, is_expressive_v8=True)
        boxes_c = detect_non_porcelain_human_faces_yunet(roi_c, allow_expressive_2d_ink=False)
        leaks_c = [verify_v8_yunet_skin_or_hair_leak(roi_c, bx)[0] for bx in boxes_c]
        assert not any(leaks_c), f"False positive human leak on clean bald vinyl keyframe {cp.name}: {boxes_c}"
        checked_clean += 1
    assert checked_clean == 3


def test_r85_2_wikimedia_fema_disaster_blocklist_and_neuro_guides() -> None:
    bad_titles = [
        'File:FEMA - 33940 - "Old Brick House" Biloxi, Miss..jpg',
        "File:Hurricane Katrina flood damage house.jpg",
        "File:20151214 Waarschuwingstekst MRI-scanner UMCG Groningen NL.jpg",
        "File:Nateglinide 60 mg bottle, Zydus, front view.jpg",
        "File:A pile of alphabet wooden blocks.jpg",
        "File:Anno Domini Harvard Medical School MDCCCCIIII.jpg",
        "File:Destroyed brick ruin after collapse.jpg",
    ]
    for bt in bad_titles:
        blocked, reason = is_commons_candidate_blocked(bt)
        assert blocked is True, f"Expected {bt} to be blocked, got pass"
        assert reason

    # Description/extmetadata disaster check even when title looks innocent
    blocked_meta, reason_meta = is_commons_candidate_blocked(
        "File:Old Brick House Biloxi Mississippi.jpg",
        {"ImageDescription": {"value": "Photograph by FEMA showing hurricane damage to porch roof."}},
    )
    assert blocked_meta is True
    assert "fema" in reason_meta or "hurricane" in reason_meta

    clean_ok, _ = is_commons_candidate_blocked("File:1110SewardEvanstonIL.jpg")
    assert clean_ok is False

    # NEUROANATOMY_CUTAWAY_MAP + off-screen MNI152 silhouette guide strictly in /tmp/aab_real_refs/
    for req_key in ("hippocampus", "thalamus_brainstem_csf", "insula", "prefrontal_cortex"):
        assert req_key in NEUROANATOMY_CUTAWAY_MAP
    try:
        g_ins = render_mni152_guide_silhouette("insula", "r85_pytest_guide")
        assert g_ins["ok"] is True
        assert g_ins["viewpoint"] == "lateral_opercular_retracted"
        gp = Path(g_ins["guide_path"])
        assert gp.is_file()
        assert str(gp).startswith("/tmp/aab_real_refs/")
    finally:
        purge_real_world_quarantine("r85_pytest_guide")


def test_r85_3_posthoc_and_ref_signoff_honesty_gates(tmp_path: Path) -> None:
    # Seed a minimal v8 project on disk
    p_dir = tmp_path / "v8_ep99_honesty_audit"
    (p_dir / "02_script").mkdir(parents=True)
    (p_dir / "03_visuals" / "reference_images").mkdir(parents=True)
    (p_dir / "04_audio").mkdir(parents=True)
    (p_dir / "05_assembly").mkdir(parents=True)

    # Create a tiny valid 2-second 30fps MP4 for SHA-256 & CV binding
    mp4_p = p_dir / "05_assembly" / "final_shorts_1080x1920.mp4"
    vw = cv2.VideoWriter(str(mp4_p), cv2.VideoWriter_fourcc(*"mp4v"), 30.0, (360, 640))
    for fi in range(60):
        frm = np.full((640, 360, 3), (185, 195, 205), dtype=np.uint8)
        cv2.rectangle(frm, (60 + fi, 180), (220 + fi, 440), (238, 240, 242), -1)
        cv2.line(frm, (40, 120), (320, 520), (60, 80, 110), 3)
        vw.write(frm)
    vw.release()

    vp = {
        "schema": 8,
        "profile": "neuro_diorama",
        "style_profile": "expressive_25d_v8",
        "clips": [
            {
                "clip_number": 1,
                "sentence_index": 1,
                "act": 1,
                "grammar": "expressive_vinyl_world",
                "camera_move": "gentle_push_in",
                "scene": "A researcher in a white lab coat places a crimson wooden block inside an open white shoebox on an oak table.",
            }
        ],
    }
    (p_dir / "03_visuals" / "visual_plan.json").write_text(json.dumps(vp), encoding="utf-8")
    (p_dir / "02_script" / "script.json").write_text(
        json.dumps({"schema": 8, "style_profile": "expressive_25d_v8", "sentences": ["One wooden block went into the box."]}),
        encoding="utf-8",
    )
    (p_dir / "04_audio" / "voice_report.json").write_text(json.dumps({"engine": "test_stub"}), encoding="utf-8")
    edl = {
        "schema": 8,
        "fps": 30,
        "total_duration_sec": 2.0,
        "cuts": [
            {
                "cut_index": 1,
                "clip_index": 1,
                "act": 1,
                "mode": "single",
                "grammar": "expressive_vinyl_world",
                "camera_move": "gentle_push_in",
                "sentence_indices": [1],
                "out_start_sec": 0.0,
                "out_end_sec": 2.0,
                "duration_sec": 2.0,
                "src_start_sec": 0.0,
                "src_end_sec": 2.0,
            }
        ],
    }
    (p_dir / "05_assembly" / "edit_decision_list.json").write_text(json.dumps(edl), encoding="utf-8")

    # (a) v8 default require_review is True -> missing review fails
    rep0 = run_posthoc_semantic_qa(p_dir, render_strips=False, run_asr_sync=False, save_report=False)
    assert rep0["require_review"] is True
    assert rep0["passed"] is False

    # (b) unmanned_cv_verified_signoff review -> unconditionally invalid
    fake_pass_qa = {**rep0, "passed": True}
    rev_path = auto_signoff_posthoc_semantic_review(p_dir, qa_report=fake_pass_qa, overwrite_valid_manual=True)
    assert rev_path is not None
    rep_unmanned = run_posthoc_semantic_qa(p_dir, render_strips=False, run_asr_sync=False, save_report=False)
    assert rep_unmanned["passed"] is False
    assert any("unmanned_cv_verified_signoff_forbidden" in x for x in rep_unmanned["semantic_review"]["issues"])

    # (c) Manual origin, but observed_visual_summary copies >=70% of intended_scene -> rejected as prompt copy!
    rev_doc = json.loads(rev_path.read_text(encoding="utf-8"))
    rev_doc["review_origin"] = "manual_vlm_review"
    rev_doc["cuts"][0]["observed_visual_summary"] = (
        "A researcher in a white lab coat places a crimson wooden block inside an open white shoebox on the oak table."
    )
    rev_path.write_text(json.dumps(rev_doc, indent=2), encoding="utf-8")
    val_copied = validate_posthoc_semantic_review(
        p_dir, rep0["final_mp4_sha256"], rep0["edl_sha256"], expected_cut_count=1
    )
    assert val_copied["valid"] is False
    assert any("prompt_copied_into_observed_summary" in x for x in val_copied["issues"])

    # (d) Stale SHA-256 review -> ALWAYS fails even if require_review=False!
    rev_doc["cuts"][0]["observed_visual_summary"] = (
        "Frame strip shows bald cream-white vinyl scientist lowering red cube into cardboard box under bright studio key light."
    )
    rev_doc["final_mp4_sha256"] = "0" * 64
    rev_path.write_text(json.dumps(rev_doc, indent=2), encoding="utf-8")
    rep_stale = run_posthoc_semantic_qa(p_dir, render_strips=False, run_asr_sync=False, require_review=False, save_report=False)
    assert rep_stale["passed"] is False
    assert "stale_review_final_mp4_sha256_mismatch" in rep_stale["semantic_review"]["issues"]

    # (e) Keyframe auto_cv_verified_v7 review -> rejected by validate_semantic_review
    ref_png = p_dir / "03_visuals" / "reference_images" / "kf_test.png"
    cv2.imwrite(str(ref_png), np.full((640, 360, 3), 210, dtype=np.uint8))
    specs = [{"ref_id": "kf_test", "filename": "kf_test.png", "setting": "real_env", "must_include": ["bald vinyl figure"]}]
    sem_p = auto_populate_reference_semantic_review(p_dir, specs=specs)
    sem_check_pending = validate_semantic_review(p_dir, specs)
    assert sem_check_pending["complete"] is False

    # Spoofing auto_cv_verified_v7 reviewer manually -> still rejected as machine signoff
    sdoc = json.loads(sem_p.read_text(encoding="utf-8"))
    sdoc["reviewer"] = "auto_cv_verified_v7"
    sdoc["images"]["kf_test"]["checks"] = {k: True for k in sdoc["images"]["kf_test"]["checks"]}
    sdoc["images"]["kf_test"]["note"] = "Auto-verified kf_test: sharp=88"
    sem_p.write_text(json.dumps(sdoc), encoding="utf-8")
    sem_check_spoof = validate_semantic_review(p_dir, specs)
    assert sem_check_spoof["complete"] is False
    assert "kf_test" in sem_check_spoof["failed"]


def test_r85_4_data_stamp_doi_illustrative_ban_exact_match_and_no_occlusion() -> None:
    sents = [
        "Ninety-seven adults with back pain took open fake pills and cut pain thirty percent.",
        "Walking back to the first room still failed to bring the memory back.",
    ]
    # 1. illustrative stamp on a DOI-backed episode -> MUST fail
    bad_ill_script = {
        "doi": "10.1016/j.cell.2024.11.027",
        "data_stamps": [
            {
                "sentence_index": 1,
                "mode": "illustrative",
                "preset": "bar_compare",
                "title": "Slow NE Pump Waves",
                "concept": "NE wave drop",
                "bars": [
                    {"label": "Natural Sleep", "value": 100.0, "unit": "%"},
                    {"label": "Zolpidem", "value": 50.0, "unit": "%"},
                ],
            },
            {
                "sentence_index": 2,
                "mode": "study",
                "preset": "arc_gauge",
                "title": "Fluid Wash Drop",
                "percent": 30.0,
                "doi": "10.1016/j.cell.2024.11.027",
                "source_citation": "Hauglund et al. (2025)",
            },
        ],
    }
    errs_ill = validate_data_stamps(bad_ill_script, sents, dossier_doc={"doi": "10.1016/j.cell.2024.11.027", "facts": "30% drop"})
    assert any("illustrative ('Concept') mode is forbidden" in e for e in errs_ill), errs_ill

    # 2. 29% vs spoken 30% contradiction -> MUST fail even if 29% is mentioned elsewhere in dossier!
    bad_29_script = {
        "doi": "10.1097/j.pain.0000000000000700",
        "data_stamps": [
            {
                "sentence_index": 1,
                "mode": "study",
                "preset": "arc_gauge",
                "title": "Back Pain Drop",
                "percent": 29.0,
                "doi": "10.1097/j.pain.0000000000000700",
                "source_citation": "Carvalho et al. (2016)",
            }
        ],
    }
    errs_29 = validate_data_stamps(
        bad_29_script,
        sents,
        dossier_doc={"facts": "Usual pain fell 30% while RMDQ disability fell 29% (10.1097/j.pain.0000000000000700)."},
    )
    assert any("contradicts spoken number 30.0" in e for e in errs_29), errs_29

    # 3. Q2 Approved: S2 has no spoken numbers, but study stamp matches exact verified dossier numbers (11%, 14%, 16%) -> PASS!
    ok_dossier_script = {
        "doi": "10.1080/17470218.2011.571267",
        "data_stamps": [
            {
                "sentence_index": 1,
                "mode": "study",
                "preset": "arc_gauge",
                "title": "Usual & Max Back Pain Drop",
                "percent": 30.0,
                "doi": "10.1097/j.pain.0000000000000700",
                "source_citation": "Carvalho et al. (2016)",
            },
            {
                "sentence_index": 2,
                "mode": "study",
                "preset": "bar_compare",
                "title": "Exp. 3 Memory Error Rate",
                "bars": [
                    {"label": "Stay Room", "value": 11.0, "unit": "%"},
                    {"label": "1 Doorway", "value": 14.0, "unit": "%"},
                    {"label": "Return Room", "value": 16.0, "unit": "%"},
                ],
                "doi": "10.1080/17470218.2011.571267",
                "source_citation": "Radvansky et al. (2011)",
            },
        ],
    }
    errs_ok = validate_data_stamps(
        ok_dossier_script,
        [sents[0], " fifth ", " sixth ", " seventh ", sents[1]],
        dossier_doc={"facts": "Exp 3 Table 3 error rates: 11%, 14%, and 16% (DOI 10.1080/17470218.2011.571267)."},
    )
    # Adjust sentence_index=5 on stamp 2 to avoid gap warning and verify 0 errors
    ok_dossier_script["data_stamps"][1]["sentence_index"] = 5
    errs_ok2 = validate_data_stamps(
        ok_dossier_script,
        [sents[0], "Two.", "Three.", "Four.", sents[1]],
        dossier_doc={"facts": "Exp 3 Table 3 error rates: 11%, 14%, and 16% (DOI 10.1080/17470218.2011.571267)."},
    )
    assert errs_ok2 == [], f"Expected 0 errors on dossier-verified study stamp, got {errs_ok2}"

    # Render 100% vs 50% bar_compare with multiplier loop and verify clean RGBA output
    rgba = render_data_stamp_rgba_frame(
        {
            "mode": "study",
            "preset": "bar_compare",
            "title": "Slow NE Pump Waves (Mice)",
            "bars": [
                {"label": "Natural Sleep", "value": 100.0, "unit": "%"},
                {"label": "Zolpidem", "value": 50.0, "unit": "%"},
            ],
            "doi": "10.1016/j.cell.2024.11.027",
            "source_citation": "Hauglund et al. (2025, Cell — mice)",
        },
        t_rel=4.0,
        total_dur=4.5,
    )
    assert rgba.size == (1080, 1920)


def test_r85_5_drone_walk_lint_insula_viewpoint_and_end_frame_omni12_routing() -> None:
    # 1. Drone clip containing 'walk' -> MUST fail R85 lint
    bad_drone_plan = {
        "schema": 8,
        "project_id": "v8_ep12_doorway_effect_memory",
        "r85_mode": True,
        "skip_r85_stamp_count_in_unit_test": True,
        "clips": [
            {
                "clip_number": 3,
                "grammar": "expressive_exterior_establishing",
                "camera_move": "drone_aerial_approach",
                "human_action_relay": True,
                "scene": "Aerial approach glides down toward Golden Dome as two doctors walk briskly along the stone path.",
            },
            {
                "clip_number": 17,
                "grammar": "expressive_xray_brain",
                "camera_move": "gentle_push_in",
                "brain_region": "insula",
                "viewpoint": "midsagittal_cutaway",
                "scene": "Midsagittal cutaway highlighting the insula fold along the medial wall.",
            },
        ],
    }
    errs = validate_r85_drone_and_viewpoint_locks(bad_drone_plan, bad_drone_plan["clips"])
    assert any("[r85_drone_ground_verb]" in e and "walk" in e for e in errs), errs
    assert any("[r85_drone_relay_conflict]" in e for e in errs), errs
    assert any("[r85_anatomy_viewpoint]" in e and "insula" in e for e in errs), errs

    # 2. Insula with lateral_opercular_retracted -> PASSES both keyframe builder and R85 lint!
    with pytest.raises(ValueError, match="Invalid viewpoint"):
        build_r85_31_brain_keyframe_spec(
            clip_number=17,
            brain_region="anterior insula",
            shot_scale="split_cutaway",
            viewpoint="midsagittal_cutaway",
        )
    kf_ok = build_r85_31_brain_keyframe_spec(
        clip_number=17,
        brain_region="anterior insula",
        shot_scale="split_cutaway",
        viewpoint="lateral_opercular_retracted",
    )
    assert kf_ok["viewpoint"] == "lateral_opercular_retracted"
    assert "#DCDFE3" in kf_ok["prompt"] and "#27D8FF" in kf_ok["prompt"]

    clean_r85_plan = {
        "schema": 8,
        "project_id": "v8_ep11_r85_check",
        "style_profile": "expressive_25d_v8",
        "r85_mode": True,
        "skip_r85_stamp_count_in_unit_test": True,
        "clips": [
            {
                "clip_number": i,
                "grammar": (
                    "expressive_exterior_establishing"
                    if i == 1
                    else (
                        "spatial_3d_arrow_diorama"
                        if i == 2
                        else ("expressive_xray_brain" if i == 3 else "expressive_reaction_closeup")
                    )
                ),
                "camera_move": (
                    "drone_aerial_approach"
                    if i == 1
                    else ("topdown_3d_route_glide" if i == 2 else "gentle_push_in")
                ),
                "arrow_3d_mode": "doorway_boundary_sever" if i == 2 else None,
                "brain_region": "insula" if i == 3 else None,
                "viewpoint": "lateral_opercular_retracted" if i == 3 else None,
                "r85_shot_scale": "split_cutaway" if i == 3 else None,
                "reference_image": f"03_visuals/reference_images/kf_c{i:02d}.png",
                "action": (
                    "Sweeps high over sunlit campus dome and tree canopy"
                    if i == 1
                    else (
                        "3D crimson arrow halts cleanly across the doorway gap"
                        if i == 2
                        else (
                            "Lateral operculum retracts to show calm slate insula gyri"
                            if i == 3
                            else "The researcher lifts an unmarked glass bottle to eye level"
                        )
                    )
                ),
            }
            for i in range(1, 19)
        ],
    }
    built = build_expressive_v8_prompts(clean_r85_plan)
    # Clip 1 (drone): gets 120ft altitude lock
    assert cfg.R85_DRONE_ALTITUDE_LOCK_CLAUSE in built[0]["prompt"]
    # Clip 2 (severed arrow) & Clip 4 (human closeup): auto-locked with Start+End VIDEO_FRAMES -> Omni 1.2 Flash!
    assert built[1]["end_reference_image"] == built[1]["reference_image"]
    assert built[1]["flow_input_mode"] == "VIDEO_FRAMES"
    assert built[1]["preferred_flow_model"] == "Omni 1.2 Flash"
    assert built[3]["end_reference_image"] == built[3]["reference_image"]
    assert built[3]["preferred_flow_model"] == "Omni 1.2 Flash"
    assert cfg.R85_HUMAN_IDENTITY_LOCK_SUFFIX in built[3]["prompt"]
    assert validate_r85_drone_and_viewpoint_locks(clean_r85_plan, built) == []


def test_r86_semantic_beat_contract_catches_ep12_filler_and_r84_zero_delta() -> None:
    # 1. Exact Ep12 C05, C19, C23 legacy decorative cuts + R84 repeated brain cuts MUST fail R86 lint!
    ep12_sents = [
        "S1.",
        "S2.",
        "Each person tucked a red block inside their box and shut the lid.",
        "Hippocampus boundary cells snapshot the old room.",
        "That boundary wave wipes the prefrontal goal.",
        "Worse yet, holding two tasks in mind leaves zero grip at the door.",
        "Carry one clue in hand or say one word out loud before any door.",
    ]
    bad_r86_plan = {
        "schema": 8,
        "project_id": "v8_ep12_doorway_effect_memory",
        "r86_mode": True,
        "clips": [
            {
                "clip_number": 5,
                "sentence_index": 3,
                "grammar": "expressive_vinyl_world",
                "camera_move": "gentle_push_in",
                "claim": "Each person tucked a red block inside their box and shut the lid",
                "viewer_must_understand": "Shutting the lid hides the block so subjects rely purely on memory",
                "visual_proof_type": "mechanism",
                "visual_register": "story",
                "concrete_referent": "hands press white shoebox lid shut over red block",
                "anti_filler_check": "Removing this misses that the block was hidden from sight",
                "scene": "A student sits on an outdoor park bench looking down at a white tablet.",
            },
            {
                "clip_number": 9,
                "sentence_index": 4,
                "grammar": "expressive_xray_brain",
                "camera_move": "circuit_cooperation_drone",
                "brain_region": "hippocampus",
                "viewpoint": "inferior_lateral_cutaway",
                "neural_state": "active",
                "claim": "Boundary cells fire",
                "viewer_must_understand": "Hippocampus fires at doorway",
                "visual_proof_type": "mechanism",
                "visual_register": "diagram",
                "concrete_referent": "hippocampus golden pulse",
                "anti_filler_check": "Removing this misses boundary trigger",
                "scene": "Inferior-lateral hippocampus cutaway glows warm gold.",
            },
            {
                "clip_number": 10,
                "sentence_index": 5,
                "grammar": "expressive_xray_brain",
                "camera_move": "circuit_cooperation_drone",
                "brain_region": "hippocampus",
                "viewpoint": "inferior_lateral_cutaway",
                "neural_state": "active",
                "claim": "Wave wipes prefrontal goal",
                "viewer_must_understand": "Prefrontal cortex shuts down",
                "visual_proof_type": "mechanism",
                "visual_register": "diagram",
                "concrete_referent": "hippocampus golden pulse",
                "anti_filler_check": "Removing this misses cortical wipe",
                "scene": "Inferior-lateral hippocampus cutaway glows warm gold.",
            },
            {
                "clip_number": 19,
                "sentence_index": 6,
                "grammar": "expressive_reaction_closeup",
                "camera_move": "gentle_push_in",
                "claim": "Holding two tasks in mind leaves zero grip at the door",
                "viewer_must_understand": "Full working-memory hands drop one item at threshold",
                "visual_proof_type": "reaction",
                "visual_register": "story",
                "concrete_referent": "both arms carry shoebox and clipboard as red block slips at doorway",
                "anti_filler_check": "Removing this misses dual-task overload cause",
                "scene": "A man stands empty-handed inside a cracked brick ruin and presses his palm to his forehead.",
            },
            {
                "clip_number": 23,
                "sentence_index": 7,
                "grammar": "expressive_hands_closeup",
                "camera_move": "gentle_push_in",
                "claim": "Carry one clue in hand or say one word out loud before any door",
                "viewer_must_understand": "Holding a physical cue before crossing locks the goal across the doorway",
                "visual_proof_type": "reaction",
                "visual_register": "story",
                "concrete_referent": "hand raises red block clue at eye level right before sunlit doorway",
                "anti_filler_check": "Removing this misses actionable doorway cue takeaway",
                "scene": "Two vinyl hands use silver scissors to snip brown parcel twine over a kitchen table.",
            },
            {
                "clip_number": 24,
                "sentence_index": 7,
                "grammar": "expressive_reaction_closeup",
                "camera_move": "locked_tripod",
                "claim": "Extra reaction",
                "viewer_must_understand": "Nodding",
                "visual_proof_type": "reaction",
                "visual_register": "story",
                "concrete_referent": "man nods calmly",
                "anti_filler_check": "Extra reaction filler check",
                "scene": "A man nods calmly in the hallway.",
            },
        ],
    }
    r86_errs = validate_r86_semantic_beat_contract(bad_r86_plan, bad_r86_plan["clips"], lines=ep12_sents)
    assert any("[r86_semantic_exhaustion]" in e and "clip 1:" in e for e in r86_errs), r86_errs
    assert any("[r86_missing_causal_mechanism]" in e and "clip 4:" in e for e in r86_errs), r86_errs
    assert any("[r86_decorative_busywork]" in e and "clip 5:" in e for e in r86_errs), r86_errs
    assert any("[r86_zero_visual_delta]" in e for e in r86_errs), r86_errs
    assert any("[r86_consecutive_proof_cap]" in e for e in r86_errs), r86_errs
    assert any("[r86_reaction_cap]" in e for e in r86_errs), r86_errs

    # 2. Valid Beat Card composition & pass check (3-cut metaphor + bridge_element -> diagram anatomy)
    composed = compose_scene_from_r86_beat_card(
        {
            "concrete_referent": "a man carries a white shoebox and notepad across a sunlit oak doorway",
            "state_delta": "one red wooden block slips from his full hands onto the floor",
        }
    )
    assert "shoebox" in composed and "slips" in composed


def test_dq8_65_labeled_fixture_zero_high_fp_and_zero_missed_defects(tmp_path: Path) -> None:
    from pipeline.dq8_suspect_classifier import classify_dq8_yunet_box, save_dq8_suspect_evidence
    from pipeline.posthoc_semantic_qa import init_posthoc_semantic_review_template

    fix_dir = cfg.WORKSPACE_ROOT / "tests" / "fixtures" / "dq8_labeled_65"
    manifest = json.loads((fix_dir / "manifest.json").read_text(encoding="utf-8"))
    assert len(manifest) == 65

    clean_count = 0
    clean_high_fp: list[str] = []
    defect_count = 0
    defect_high = 0
    defect_mod = 0
    defect_missed: list[str] = []
    sample_suspect_items: list[dict] = []

    for entry in manifest:
        img = cv2.imread(str(fix_dir / entry["crop_relpath"]), cv2.IMREAD_COLOR)
        assert img is not None, f"Missing fixture crop {entry['crop_relpath']}"
        res = classify_dq8_yunet_box(
            img,
            entry["bbox_in_crop"],
            float(entry["score"]),
            entry["landmarks_in_crop"],
            is_precrop=True,
            roi_bbox_xywh=entry["bbox_in_roi"],
        )
        if entry["cls"] == "clean_vinyl":
            clean_count += 1
            if res["is_high_suspect"]:
                clean_high_fp.append(entry["id"])
        elif entry["cls"] == "defect":
            defect_count += 1
            if res["tier"] == "HIGH_SUSPECT":
                defect_high += 1
            elif res["tier"] == "MODERATE_SUSPECT":
                defect_mod += 1
            else:
                defect_missed.append(entry["id"])
        if len(sample_suspect_items) < 2 and res["is_suspect"]:
            sample_suspect_items.append(
                {
                    "cut_index": 1,
                    "box_index": len(sample_suspect_items),
                    "timeline_sec": float(entry["ts_sec"]),
                    "src_clip_sec": 0.5,
                    "frame_index": 15,
                    "bbox_in_roi": entry["bbox_in_roi"],
                    "landmarks_in_roi": entry["landmarks_in_crop"],
                    "det_result": res,
                }
            )

    assert clean_count == 40
    assert defect_count == 17
    assert clean_high_fp == [], f"Expected 0 HIGH_SUSPECT false positives on 40 clean vinyl crops, got {clean_high_fp}"
    assert defect_missed == [], f"Expected 0 missed defects across 17 real defects, got {defect_missed}"
    assert defect_high + defect_mod == 17

    # Verify timestamped crop + contact sheet saving & Gate 2 review template propagation
    p_dir = tmp_path / "v8_ep99_dq8_crops"
    (p_dir / "03_visuals").mkdir(parents=True)
    (p_dir / "05_assembly").mkdir(parents=True)
    ev = save_dq8_suspect_evidence(p_dir, sample_suspect_items)
    assert len(ev["suspect_detections"]) == 2
    assert ev["contact_sheet_path"] == "05_assembly/dq8_suspect_contact_sheet.jpg"
    assert (p_dir / ev["contact_sheet_path"]).is_file()
    for sd in ev["suspect_detections"]:
        assert (p_dir / sd["crop_path"]).is_file()
        assert "timeline_sec" in sd and "bbox_in_roi" in sd

    (p_dir / "05_assembly" / "dynamic_episode_qa_report.json").write_text(
        json.dumps({"gates": {"DQ8_zero_uncanny_skin_gore": ev}}), encoding="utf-8"
    )
    (p_dir / "03_visuals" / "visual_plan.json").write_text(
        json.dumps({"schema": 8, "r85_mode": True, "clips": [{"clip_number": 1, "viewer_must_understand": "Test goal"}]}),
        encoding="utf-8",
    )
    fake_qa = {
        "final_mp4_sha256": "a" * 64,
        "edl_sha256": "b" * 64,
        "cuts": [
            {
                "cut_index": 1,
                "clip_index": 1,
                "grammar": "expressive_vinyl_world",
                "camera_move": "gentle_push_in",
                "spoken_narration": "Test line.",
                "intended_scene": "A scientist places a red cube into a box.",
                "clarity_score": 90.0,
                "passed": True,
            }
        ],
    }
    rev_p = init_posthoc_semantic_review_template(p_dir, qa_report=fake_qa, auto_populate_from_cv=False)
    rdoc = json.loads(rev_p.read_text(encoding="utf-8"))
    assert rdoc["cuts"][0]["dq8_suspect_crops"]
    assert rdoc["cuts"][0]["zero_human_skin_or_hair_leak"] is None

    # Signing everything EXCEPT zero_human_skin_or_hair_leak=False -> MUST fail Gate 2!
    rdoc["review_origin"] = "research_vlm_gate2"
    rdoc["reviewer"] = "@Research"
    rdoc["cuts"][0]["auto_populated"] = False
    rdoc["cuts"][0]["observed_visual_summary"] = "Bald vinyl researcher lowers crimson block cleanly onto oak workbench."
    rdoc["cuts"][0]["expresses_intended_meaning"] = True
    rdoc["cuts"][0]["delivers_viewer_must_understand"] = True
    rdoc["cuts"][0]["zero_human_skin_or_hair_leak"] = False
    rev_p.write_text(json.dumps(rdoc, indent=2), encoding="utf-8")
    v_fail = validate_posthoc_semantic_review(p_dir, "a" * 64, "b" * 64, expected_cut_count=1)
    assert v_fail["valid"] is False
    assert any("dq8_gate2_skin_or_hair_review_failed" in x for x in v_fail["issues"])


def test_rules_restructure_under_24kb_frontmatter_and_open_license_lock(tmp_path: Path) -> None:
    import re
    from pipeline.real_world_reference_builder import validate_real_world_refs_manifest

    agents_md = cfg.WORKSPACE_ROOT / ".agents" / "AGENTS.md"
    rules_dir = cfg.WORKSPACE_ROOT / ".agents" / "rules"
    archive_dir = rules_dir / "_archive"

    ag_bytes = agents_md.read_bytes()
    assert 3_000 <= len(ag_bytes) <= 6_500, f"AGENTS.md size {len(ag_bytes)} outside 3-6.5KB target"
    assert not (rules_dir / "neuro_diorama_rules.md").exists(), "Legacy 49KB neuro_diorama_rules.md must be split"

    # CEO-owned governance_roles.md stays compact & always_on (updated to R83 v2 Domain VP charter)
    gov_txt = (rules_dir / "governance_roles.md").read_text(encoding="utf-8")
    assert 2_000 <= len(gov_txt.encode("utf-8")) <= 4_000
    assert "trigger: always_on" in gov_txt

    # Exact 26 active .agents/rules/*.md files + strict size & frontmatter policy
    rule_mds = sorted(rules_dir.glob("*.md"))
    assert len(rule_mds) == 26
    for p in rule_mds:
        b_len = len(p.read_bytes())
        assert b_len < 24_000, f"{p.name} exceeds 24,000 bytes: {b_len}"
        txt = p.read_text(encoding="utf-8")
        if p.name == "production_constants.md":
            assert not txt.startswith("---\n"), "production_constants.md must be direct-read without trigger"
        elif p.name == "governance_roles.md":
            assert "trigger: always_on" in txt
        else:
            assert b_len <= 3_800, f"model_decision {p.name} exceeds 3,800 bytes: {b_len}"
            assert txt.startswith("---\n"), f"{p.name} missing YAML frontmatter"
            fm = txt.split("---\n", 2)[1]
            assert re.search(r"^trigger:\s*model_decision\b", fm, flags=re.MULTILINE), f"{p.name} missing model_decision"
            assert re.search(r"^description:\s*\S+", fm, flags=re.MULTILINE), f"{p.name} missing description"

    # Zero-Deletion archives exist without frontmatter
    for arch_fn in ("retired_rules_2026-11-18.md", "retired_constants_v4_v7_2026-11-18.md"):
        ap = archive_dir / arch_fn
        assert ap.is_file()
        assert not ap.read_text(encoding="utf-8").startswith("---\n")

    # CEO Amendment #1: Tier-1 #3 Open-License + Provenance enforcement on real_world_refs_manifest.json
    proj = tmp_path / "v8_ep99_license_check"
    (proj / "03_visuals").mkdir(parents=True)
    mf = proj / "03_visuals" / "real_world_refs_manifest.json"
    mf.write_text(
        json.dumps(
            {
                "r85_mode": True,
                "targets": [
                    {
                        "target_id": "ucl_main_quad",
                        "commons_title": "File:UCL Portico London.jpg",
                        "license": "All Rights Reserved Proprietary",
                        "source_url": "https://commons.wikimedia.org/wiki/File:UCL_Portico_London.jpg",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    res_bad = validate_real_world_refs_manifest(proj)
    assert res_bad["passed"] is False
    assert any("[real_world_ref_unlicensed]" in x for x in res_bad["issues"])

    mf.write_text(
        json.dumps(
            {
                "r85_mode": True,
                "targets": [
                    {
                        "target_id": "ucl_main_quad",
                        "commons_title": "File:UCL Portico London.jpg",
                        "license": "CC-BY-SA 4.0",
                        "source_url": "https://commons.wikimedia.org/wiki/File:UCL_Portico_London.jpg",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    res_ok = validate_real_world_refs_manifest(proj)
    assert res_ok["passed"] is True


def test_r85_7_ep31_brain_style_fidelity_and_vfx_ban() -> None:
    from pipeline.porcelain_anchor_pack import R85_EP31_MASTER_STYLE_PROMPT, R85_EP31_MODE1_STYLE_PROMPT
    from pipeline.reference_image_qa import evaluate_r85_ep31_brain_style_fidelity

    # 1. Spec builder & prompt lint block banned AI VFX tokens + retired 2nd-gen derivative anchors
    spec_ok = build_r85_31_brain_keyframe_spec(
        clip_number=10,
        brain_region="hippocampus",
        shot_scale="split_cutaway",
        viewpoint="inferior_lateral_cutaway",
    )
    assert spec_ok["canonical_slot_id"] == "A06_hippocampus_cutaway"
    assert "canonical_A06_hippocampus_cutaway.png" in spec_ok["style_reference_anchors"]
    assert "ref_r78m_cut05.png" not in spec_ok["style_reference_anchors"]
    assert "ref_r78m_cut06.png" not in spec_ok["style_reference_anchors"]

    clean_plan = {
        "r85_mode": True,
        "skip_r85_stamp_count_in_unit_test": True,
        "clips": [
            {
                "clip_number": 1,
                "grammar": "expressive_xray_brain",
                "brain_clip": True,
                "r85_brain_clip": True,
                "r85_shot_scale": "split_cutaway",
                "brain_region": "hippocampus",
                "viewpoint": "inferior_lateral_cutaway",
                "scene": "Left-facing matte silver-white sculpted gypsum 3D brain cutaway reveals the solid matte amber-gold hippocampus with opaque sky-blue sulcal tubes.",
            }
        ],
        "reference_anchors": [
            {
                "ref_id": "kf_r85_c01",
                "setting": "brain_studio",
                "r85_brain_clip": True,
                "conditioned_on": ["ep31_orig_mode2_lateral_9x16"],
                "prompt": f"{R85_EP31_MASTER_STYLE_PROMPT} Solid matte amber-gold posterior hippocampus in lower-lateral temporal window.",
            },
            {
                "ref_id": "kf_r85_m1",
                "setting": "brain_studio",
                "r85_brain_clip": True,
                "conditioned_on": ["ep31_orig_mode1_head_9x16"],
                "prompt": f"{R85_EP31_MODE1_STYLE_PROMPT} Short opaque amber-gold segment inside the optic nerve tube.",
            },
        ],
    }
    assert validate_r85_drone_and_viewpoint_locks(clean_plan, clean_plan["clips"]) == []

    bad_vfx_plan = {
        "r85_mode": True,
        "skip_r85_stamp_count_in_unit_test": True,
        "clips": [
            {
                "clip_number": 1,
                "grammar": "expressive_xray_brain",
                "brain_clip": True,
                "r85_brain_clip": True,
                "r85_shot_scale": "split_cutaway",
                "brain_region": "hippocampus",
                "viewpoint": "inferior_lateral_cutaway",
                "scene": "Glowing neon particles and golden embers radiate a luminous light beam halo through smoke around the hippocampus.",
            }
        ],
        "reference_anchors": [
            {
                "ref_id": "kf_r85_bad",
                "setting": "brain_studio",
                "r85_brain_clip": True,
                "conditioned_on": ["ref_r78m_cut06"],
                "prompt": "Glowing neon hippocampus with golden sparks.",
            }
        ],
    }
    vfx_errs = validate_r85_drone_and_viewpoint_locks(bad_vfx_plan, bad_vfx_plan["clips"])
    assert any("[r85_brain_banned_vfx]" in e for e in vfx_errs), vfx_errs
    assert any("[r85_retired_brain_anchor]" in e for e in vfx_errs), vfx_errs

    # 2. Genuine 31_O2CmlKOk anchors MUST pass Q_R85_ep31_brain_fidelity (4/4), while 2nd-gen blue/glow derivatives MUST fail!
    refs_dir = cfg.CHANNEL_ROOT / "reference_style_anchors" / cfg.EXPRESSIVE_V8_REFS_DIRNAME
    for fn in cfg.R85_GENUINE_EP31_ANCHOR_FILES:
        p = refs_dir / fn
        assert p.is_file(), f"Missing genuine Ep31 anchor {p}"
        ev = evaluate_r85_ep31_brain_style_fidelity(
            cv2.imread(str(p), cv2.IMREAD_COLOR),
            mode="mode1" if "mode1" in fn else "mode2",
        )
        assert ev["passed"] is True, f"Genuine 31_O2CmlKOk anchor {fn} failed fidelity gate: {ev}"

    for bad_fn in ("xray_brain75_master.png", "ref_r78m_cut05.png", "ref_r78m_cut06.png"):
        bp = refs_dir / bad_fn
        if bp.is_file():
            bev = evaluate_r85_ep31_brain_style_fidelity(
                cv2.imread(str(bp), cv2.IMREAD_COLOR),
                mode="mode1" if "xray" in bad_fn else "mode2",
            )
            assert bev["passed"] is False, f"Retired 2nd-gen derivative {bad_fn} unexpectedly passed: {bev}"


def test_r85_8_canonical_v1_approved_lock_retired_anchor_ban_and_provenance(tmp_path: Path):
    """
    Verifies Canonical Asset Library v1 lock:
      1. All 42 slots in `canonical_assets/v1/manifest.json` are `status="approved"` with `sha256_locked=True`
         on `cand_01.png` (matching disk SHA-256), while backup `cand_02+` stay `status="candidate"`.
      2. Retired derivative anchors (`xray_brain75_master`, `ref_r78m_*`, unapproved `cand_02.png`) fail
         across `canonical_assets`, `porcelain_anchor_pack`, `flow_prompt_builder`, `source_reenactment`,
         and `reference_image_qa`.
      3. Episode staging writes `canonical_assets_provenance.json` + `00_project_manifest.json` (`canonical_assets_lock`)
         and `inspect_reference_image_pack` enforces SHA-256 provenance integrity.
    """
    from pipeline.canonical_assets import (
        CanonicalAssetError,
        is_retired_derivative_anchor,
        load_canonical_manifest,
        resolve_canonical_approved_slot,
        stage_canonical_slot_to_project,
        validate_project_canonical_provenance,
    )
    from pipeline.flow_prompt_builder import build_diorama_v7_prompts, validate_diorama_v7_prompts
    from pipeline.porcelain_anchor_pack import ensure_expressive_v8_reference_pack
    from pipeline.reference_image_qa import inspect_reference_image_pack
    from pipeline.source_reenactment import resolve_keyframe_conditioning_and_prompt

    # 1. Verify live canonical_assets/v1 manifest & all 42 SHA-256 locks (27 active + 15 Zero-Deletion R88 retired)
    manifest = load_canonical_manifest("v1", require_approved=True)
    assert manifest["status"] == "approved"
    assert len(manifest["slots"]) == 42
    for sl in manifest["slots"]:
        is_b_retired = sl.get("status") == "retired_r88_cartoon_face"
        if is_b_retired:
            with pytest.raises(CanonicalAssetError, match="retired under R88"):
                resolve_canonical_approved_slot(sl["slot_id"], verify_sha256=True)
        res = resolve_canonical_approved_slot(sl["slot_id"], verify_sha256=True, allow_retired_r88=is_b_retired)
        assert res["library_version"] == "v1"
        expected_fn = "cand_02.png" if sl["category"] == "A_brain" else "cand_01.png"
        assert res["approved_filename"] == expected_fn
        assert len(res["sha256"]) == 64
        for c in sl["candidates"]:
            if c["filename"] == expected_fn:
                assert c["status"] == "approved" and c["sha256_locked"] is True
            else:
                assert c["status"] == "candidate" and c["sha256_locked"] is False

    # 2. Retired derivative anchors & unapproved candidate paths MUST fail everywhere
    for retired in (
        "xray_brain75_master.png",
        "xray_brain75_master",
        "ref_r78m_cut05.png",
        "ref_r78m_cut06",
        "cand_04_neutral_master_translucent_glass_9x16.png",
        "BCI_Shorts_Channel/canonical_assets/v1/A_brain/A02_mode2_whole_brain_lateral/cand_01.png",
        "BCI_Shorts_Channel/canonical_assets/v1/B_characters/B01_base_adult_male_turnaround/cand_02.png",
    ):
        assert is_retired_derivative_anchor(retired) is True
        with pytest.raises(CanonicalAssetError):
            resolve_canonical_approved_slot(retired)

    # Unapproved slot or tampered SHA in a sandbox manifest MUST raise CanonicalAssetError
    fake_lib = tmp_path / "fake_canonical_v1"
    (fake_lib / "A_brain" / "A02_mode2_whole_brain_lateral").mkdir(parents=True)
    fake_png = fake_lib / "A_brain" / "A02_mode2_whole_brain_lateral" / "cand_01.png"
    fake_png.write_bytes(b"tampered")
    (fake_lib / "manifest.json").write_text(
        json.dumps(
            {
                "version": "v1",
                "status": "approved",
                "slots": [
                    {
                        "slot_id": "A02_mode2_whole_brain_lateral",
                        "category": "A_brain",
                        "status": "approved",
                        "approved_rel_path": "A_brain/A02_mode2_whole_brain_lateral/cand_01.png",
                        "approved_sha256": "0" * 64,
                        "candidates": [
                            {
                                "rank": 1,
                                "filename": "cand_01.png",
                                "rel_path": "A_brain/A02_mode2_whole_brain_lateral/cand_01.png",
                                "sha256": "0" * 64,
                                "status": "approved",
                                "sha256_locked": True,
                            }
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(CanonicalAssetError, match="SHA-256 lock mismatch"):
        resolve_canonical_approved_slot("A02_mode2_whole_brain_lateral", custom_root=fake_lib, verify_sha256=True)

    # source_reenactment.resolve_keyframe_conditioning_and_prompt MUST raise on ref_r78m_* / xray_brain75_master
    proj = tmp_path / "v8_ep99_canonical_lock_r85"
    (proj / "03_visuals" / "reference_images").mkdir(parents=True)
    (proj / "00_project_manifest.json").write_text(json.dumps({"project_id": proj.name}), encoding="utf-8")
    with pytest.raises(CanonicalAssetError):
        resolve_keyframe_conditioning_and_prompt(
            {"ref_id": "kf_bad", "r85_brain_clip": True, "conditioned_on": ["xray_brain75_master"]},
            {"r85_mode": True},
            tmp_path / "guides",
            proj / "03_visuals" / "reference_images",
        )

    # porcelain_anchor_pack.ensure_expressive_v8_reference_pack MUST raise if plan binds retired anchor
    bad_plan_pack = {
        "style_profile": "expressive_25d_v8",
        "r85_mode": True,
        "clips": [{"clip_number": 1, "grammar": "expressive_xray_brain", "reference_image": "ref_r78m_cut05.png"}],
    }
    (proj / "03_visuals" / "visual_plan.json").write_text(json.dumps(bad_plan_pack), encoding="utf-8")
    with pytest.raises(CanonicalAssetError):
        ensure_expressive_v8_reference_pack(proj)

    # flow_prompt_builder.validate_diorama_v7_prompts MUST emit [canonical_retired_anchor]
    sents = [f"Sentence {i} explains brain maps." for i in range(1, 21)]
    vp_bad = {
        "style_profile": "expressive_25d_v8",
        "r85_mode": True,
        "canonical_assets_version": "v1",
        "skip_r85_stamp_count_in_unit_test": True,
        "clips": [
            {
                "clip_number": i,
                "grammar": "expressive_xray_brain" if i == 10 else "expressive_dialogue_acting",
                "camera_move": "gentle_push_in" if i == 1 else "locked_tripod",
                "action": "Protagonist shifts focus across the wooden table",
                "brain_clip": i == 10,
                "r85_brain_clip": i == 10,
                "r85_shot_scale": "split_cutaway" if i == 10 else "",
                "brain_region": "hippocampus" if i == 10 else "",
                "viewpoint": "inferior_lateral_cutaway" if i == 10 else "",
                "reference_image": "xray_brain75_master.png" if i == 10 else "canonical_E06_laboratory_staged.png",
            }
            for i in range(1, 21)
        ],
    }
    prompts_bad = build_diorama_v7_prompts(vp_bad, sents)
    errs_bad = validate_diorama_v7_prompts(prompts_bad, vp_bad)
    assert any("[canonical_retired_anchor]" in e for e in errs_bad), errs_bad

    # 3. Clean canonical staging records version + SHA-256 provenance and passes audit; tampering fails reference_image_qa!
    clean_proj = tmp_path / "v8_ep98_clean_canonical_r85"
    (clean_proj / "03_visuals" / "reference_images").mkdir(parents=True)
    (clean_proj / "00_project_manifest.json").write_text(json.dumps({"project_id": clean_proj.name}), encoding="utf-8")
    (clean_proj / "03_visuals" / "visual_plan.json").write_text(
        json.dumps({"style_profile": "expressive_25d_v8", "r85_mode": True, "clips": []}),
        encoding="utf-8",
    )
    st_a06 = stage_canonical_slot_to_project(clean_proj, "A06_hippocampus_cutaway")
    st_e06 = stage_canonical_slot_to_project(clean_proj, "E06_laboratory_staged")
    st_d01 = stage_canonical_slot_to_project(clean_proj, "D01_drone_university_campus_120ft")
    with pytest.raises(CanonicalAssetError, match="retired under R88"):
        stage_canonical_slot_to_project(clean_proj, "B01_base_adult_male_turnaround")
    prov_audit = validate_project_canonical_provenance(clean_proj)
    assert prov_audit["passed"] is True, prov_audit
    assert prov_audit["library_version"] == "v1"
    assert prov_audit["locked_file_count"] == 3
    pm_doc = json.loads((clean_proj / "00_project_manifest.json").read_text(encoding="utf-8"))
    assert pm_doc["canonical_assets_lock"]["library_version"] == "v1"
    assert "A06_hippocampus_cutaway" in pm_doc["canonical_assets_lock"]["slots_used"]

    # Tampering with staged file bytes or dropping a retired file in reference_images/ fails reference_image_qa!
    (clean_proj / "03_visuals" / "reference_images" / "ref_r78m_cut05.png").write_bytes(st_a06["staged_path"].read_bytes())
    qa_rep = inspect_reference_image_pack(clean_proj, save_report=False, require_review=False)
    assert qa_rep["canonical_assets_provenance_audit"]["passed"] is False
    assert qa_rep["cv_all_passed"] is False


def test_r85_9_gate2_global_fixes_chart_wcag_callout_targets_seahorse_and_arc_flash() -> None:
    from PIL import Image
    from pipeline.anatomy_label_overlay import _parse_callout_xy_pair, render_anatomy_callout_rgba_frame
    from pipeline.data_stamp_overlay import _build_bright_wall_contrast_card_rgba
    from pipeline.flow_prompt_builder import sanitize_diorama_scene_for_flow

    # 1. Global anti-animal/food metaphor de-literalizer prevents ocean-seahorse hallucinations
    san = sanitize_diorama_scene_for_flow(
        "into the horizontal seahorse-shaped hippocampus and almond-shaped amygdala inside a walnut-like brain"
    )
    assert "seahorse" not in san.lower()
    assert "almond" not in san.lower()
    assert "walnut" not in san.lower()
    assert "smooth rounded c-curved" in san.lower()

    # 2. Bright-wall contrast card achieves WCAG >= 7.0 over cream plaster (luma ~ 140 after dim)
    card = _build_bright_wall_contrast_card_rgba((90, 210, 860, 980), width=1080, height=1920, fade_alpha=1.0)
    bg_wall = Image.new("RGBA", (1080, 1920), (145, 142, 136, 255))
    merged = Image.alpha_composite(bg_wall, card)
    px = merged.getpixel((400, 500))
    u_bg = px[1] / 255.0
    l_bg = u_bg / 12.92 if u_bg <= 0.04045 else ((u_bg + 0.055) / 1.055) ** 2.4
    wcag_white = (1.0 + 0.05) / (l_bg + 0.05)
    assert wcag_white >= 10.0, f"Expected WCAG >= 10.0 (>= 7.0 hard gate), got {wcag_white:.2f}"

    # 3. Normalized `left_target_xy` / `right_target_xy` + stacked top-vs-bottom (`y=0.33` vs `y=0.78`) renders down to y=1498 without clipping
    assert _parse_callout_xy_pair([0.50, 0.78]) == pytest.approx((540.0, 1497.6))
    im_stk = render_anatomy_callout_rgba_frame(
        {
            "cut_index": 17,
            "callout_mode": "r78m_dual",
            "stacked_cutaway_brain_compare": True,
            "r78m_callout": {
                "enabled": True,
                "mode": "r78m_dual",
                "arrow": "vs",
                "stacked_vstack": True,
                "left_lbl": "Cabbie Map",
                "right_lbl": "Bus Baseline",
                "left_rgb": [234, 179, 75],
                "right_rgb": [91, 103, 120],
                "left_target_xy": [0.56, 0.33],
                "right_target_xy": [0.56, 0.78],
            },
        },
        t_rel=1.0,
        total_dur=4.5,
        width=1080,
        height=1920,
    )
    arr_stk = np.array(im_stk)
    # Stacked vstack clamps lower target ring into Y=58-63% (y ~ 1210px at x ~ 605px) so bottom ASS subtitles (Y>=70%, y>=1344px) stay 100% clear
    assert np.count_nonzero(arr_stk[1180:1240, 575:635, 3]) > 80
    assert np.count_nonzero(arr_stk[1344:, :, 3]) == 0


def test_k06_start_end_pair_survives_populate_expressive_v8_reference_contract() -> None:
    from pipeline.flow_prompt_builder import build_expressive_v8_prompts
    from pipeline.porcelain_anchor_pack import populate_expressive_v8_reference_contract

    k06_start = "03_visuals/reference_images/canonical_K06_contrast_a12_dual_brain_state_transition_pair_start.png"
    k06_end = "03_visuals/reference_images/canonical_K06_contrast_a12_dual_brain_state_transition_pair_end.png"
    c09_ref = "03_visuals/reference_images/kf_r87_ep13_c09_striatum_coronal.png"
    plan = {
        "project_id": "v8_k06_preserve_test",
        "style_profile": "expressive_25d_v8",
        "schema_version": 8,
        "r85_mode": True,
        "reference_anchors": [
            {
                "ref_id": "kf_r87_ep13_c09_striatum_coronal",
                "filename": "kf_r87_ep13_c09_striatum_coronal.png",
                "clip_number": 1,
                "frame": "start",
                "setting": "brain_studio",
            },
            {
                "ref_id": "canonical_K06_contrast_a12_dual_brain_state_transition_pair_start",
                "filename": "canonical_K06_contrast_a12_dual_brain_state_transition_pair_start.png",
                "clip_number": 2,
                "frame": "start",
                "setting": "contrast_pair",
                "canonical_slot_id": "K06_contrast_a12_dual_brain_state_transition_pair",
            },
            {
                "ref_id": "canonical_K06_contrast_a12_dual_brain_state_transition_pair_end",
                "filename": "canonical_K06_contrast_a12_dual_brain_state_transition_pair_end.png",
                "clip_number": 2,
                "frame": "end",
                "setting": "contrast_pair",
                "canonical_slot_id": "K06_contrast_a12_dual_brain_state_transition_pair",
            },
        ],
        "clips": [
            {
                "clip_number": 1,
                "act": 2,
                "grammar": "expressive_xray_brain",
                "camera_move": "gentle_push_in",
                "reference_image": c09_ref,
                "brain_region": "nucleus accumbens",
                "scene": "Coronal cutaway brain with warm amber-gold ventral striatum.",
            },
            {
                "clip_number": 2,
                "act": 3,
                "grammar": "expressive_xray_brain",
                "camera_move": "neural_macro_orbit_hold",
                "canonical_slot_id": "K06_contrast_a12_dual_brain_state_transition_pair",
                "lock_start_and_end_keyframes": True,
                "single_start_frame_lock": False,
                "stacked_cutaway_brain_compare": True,
                "reference_image": k06_start,
                "start_frame_image": k06_start,
                "end_reference_image": k06_end,
                "end_frame_image": k06_end,
                "brain_region": "striatum",
                "scene": "Vertically stacked twin Ep #31 chalk-white brains shifting top to amber-gold and bottom to muted cool slate.",
            },
            *[
                {
                    "clip_number": i,
                    "act": min(6, (i - 1) // 3 + 1),
                    "grammar": "expressive_vinyl_world",
                    "camera_move": "gentle_push_in",
                    "reference_image": "03_visuals/reference_images/canonical_E06_laboratory_staged.png",
                    "scene": "Smooth matte porcelain figure in bright clinical room.",
                }
                for i in range(3, 20)
            ],
        ],
    }

    populate_expressive_v8_reference_contract(plan)
    c2 = plan["clips"][1]
    assert c2["reference_image"] == k06_start
    assert c2["end_reference_image"] == k06_end
    assert c2["single_start_frame_lock"] is False
    assert c2.get("neural_dive_relay") is None

    prompts = build_expressive_v8_prompts(plan, ["Stacked brains diverge cleanly."] * 19)
    p2 = prompts[1]
    assert p2["reference_image"] == k06_start
    assert p2["end_reference_image"] == k06_end
    assert p2["portal_to_brain"] is False
    assert p2["keyframe_chain_mode"] == "start_end_interpolation"


def test_r88_overhead_oak_tabletop_hands_only_q4_fidelity(tmp_path: Path) -> None:
    """R88 overhead bird's-eye oak tabletop hands-only POV must pass Q4 when matte-white porcelain hands are present and 0 human faces exist, while still failing if no porcelain is present."""
    from pipeline.reference_image_qa import inspect_single_reference_image

    # Build synthetic 1080x1920 warm oak tabletop (upper-center ~55% in HSV skin band H~12, S~110, V~165 + sunlit highlights)
    oak_hsv = np.full((1920, 1080, 3), (12, 110, 165), dtype=np.uint8)
    oak_hsv[:560, :, 2] = 225  # sunlit upper tabletop highlight outside narrow V<=210 band (~55% remains in skin band)
    img = cv2.cvtColor(oak_hsv, cv2.COLOR_HSV2BGR)
    # Add realistic wood grain edges + dark chocolate cup + matte-white porcelain hands & white analog scale
    for y in range(0, 1920, 40):
        cv2.line(img, (0, y), (1080, y), (80, 115, 150), 2)
    cv2.circle(img, (320, 960), 170, (238, 238, 238), -1)  # white analog scale
    cv2.circle(img, (320, 960), 150, (190, 190, 190), 3)
    cv2.rectangle(img, (680, 780), (920, 1080), (242, 242, 242), -1)  # porcelain hands
    cv2.circle(img, (760, 930), 75, (28, 38, 62), -1)  # chocolate pudding cup
    p_ok = tmp_path / "kf_r88_overhead_hands.png"
    cv2.imwrite(str(p_ok), img)

    spec = {
        "ref_id": "kf_r88_ep13_c07_scale_pudding_hands",
        "filename": p_ok.name,
        "setting": "real_env",
        "role": "reenactment",
        "style_profile": "expressive_25d_v8",
        "prompt": (
            "Strict 85 to 90 degree vertical overhead top-down bird's-eye tabletop photograph onto a sunlit natural oak "
            "counter with zero head, zero neck, and zero torso: white analog scale and ONLY two matte-white porcelain hands."
        ),
    }
    rep_ok = inspect_single_reference_image(p_ok, spec)
    assert "Q4_porcelain_cast_fidelity" not in (rep_ok.get("failed_axes") or []), rep_ok

    # Without any matte-white porcelain (pure warm oak only) -> Q4 MUST still fail
    p_no_porcelain = tmp_path / "kf_r88_overhead_no_porcelain.png"
    cv2.imwrite(str(p_no_porcelain), cv2.cvtColor(oak_hsv, cv2.COLOR_HSV2BGR))
    rep_bad = inspect_single_reference_image(p_no_porcelain, spec)
    assert "Q4_porcelain_cast_fidelity" in (rep_bad.get("failed_axes") or []), rep_bad


def test_r88_overhead_hands_yunet_cocoa_pareidolia_vs_real_skin_face(tmp_path: Path, monkeypatch) -> None:
    """R88 overhead hands-only POV classifies low-conf (<0.75) dark-cocoa+porcelain pareidolia as Gate-1 advisory while still hard-failing real skin faces or conf>=0.75."""
    import pipeline.source_reenactment as sr_mod
    from pipeline.reference_image_qa import inspect_single_reference_image

    oak_hsv = np.full((1920, 1080, 3), (12, 110, 165), dtype=np.uint8)
    oak_hsv[:560, :, 2] = 225
    img = cv2.cvtColor(oak_hsv, cv2.COLOR_HSV2BGR)
    cv2.circle(img, (300, 960), 170, (238, 238, 238), -1)  # white analog scale
    cv2.rectangle(img, (680, 780), (920, 1080), (242, 242, 242), -1)  # matte-white porcelain hands
    cv2.circle(img, (780, 920), 95, (22, 30, 50), -1)  # glossy dark cocoa bowl inside bbox
    p_cocoa = tmp_path / "kf_r88_overhead_cocoa_pareidolia.png"
    cv2.imwrite(str(p_cocoa), img)

    spec = {
        "ref_id": "kf_r88_ep13_c07_scale_pudding_hands",
        "filename": p_cocoa.name,
        "setting": "real_env",
        "role": "reenactment",
        "style_profile": "expressive_25d_v8",
        "prompt": (
            "Strict 85 to 90 degree vertical overhead top-down bird's-eye tabletop photograph onto a sunlit natural oak "
            "counter with zero head, zero neck, and zero torso: white analog scale and ONLY two matte-white porcelain hands."
        ),
    }

    # (a) Low-conf (0.636) YuNet pareidolia over dark cocoa cup + porcelain hands -> passes CV Q4 as Gate-1 advisory
    monkeypatch.setattr(sr_mod, "detect_non_porcelain_human_faces_yunet", lambda *a, **kw: [(690, 820, 180, 200, 0.636)])
    rep_par = inspect_single_reference_image(p_cocoa, spec)
    assert "Q4_porcelain_cast_fidelity" not in (rep_par.get("failed_axes") or []), rep_par
    assert rep_par["yunet_human_face_count"] == 0
    assert rep_par["yunet_pareidolia_advisory_count"] == 1

    # (b) High-conf (>=0.75) YuNet box -> MUST still hard-fail Q4 even over dark prop
    monkeypatch.setattr(sr_mod, "detect_non_porcelain_human_faces_yunet", lambda *a, **kw: [(690, 820, 180, 200, 0.78)])
    rep_hi = inspect_single_reference_image(p_cocoa, spec)
    assert "Q4_porcelain_cast_fidelity" in (rep_hi.get("failed_axes") or []), rep_hi
    assert rep_hi["yunet_human_face_count"] == 1

    # (c) Real human skin face inside overhead frame (even at conf=0.636) -> MUST hard-fail Q4!
    img_skin = img.copy()
    skin_patch = cv2.cvtColor(np.full((200, 180, 3), (11, 110, 168), dtype=np.uint8), cv2.COLOR_HSV2BGR)
    img_skin[820:1020, 690:870] = skin_patch
    p_skin = tmp_path / "kf_r88_overhead_real_skin_face.png"
    cv2.imwrite(str(p_skin), img_skin)
    monkeypatch.setattr(sr_mod, "detect_non_porcelain_human_faces_yunet", lambda *a, **kw: [(690, 820, 180, 200, 0.636)])
    rep_skin = inspect_single_reference_image(p_skin, spec)
    assert "Q4_porcelain_cast_fidelity" in (rep_skin.get("failed_axes") or []), rep_skin
    assert rep_skin["yunet_human_face_count"] == 1







