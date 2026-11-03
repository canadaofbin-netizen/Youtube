from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
import pytest

from pipeline.config import PORCELAIN_V7_STYLE_PROFILE, WORKSPACE_ROOT
from pipeline.reference_image_qa import _dhash_64
from pipeline.source_reenactment import (
    _ensure_outside_workspace,
    compute_5gram_sha256_set,
    render_reenactment_comparison_sheet,
    sanitize_structural_frame_bgr,
    validate_reenactment_non_infringement,
)


def test_quarantine_guard_rejects_workspace_paths():
    with pytest.raises(ValueError, match="quarantine violation"):
        _ensure_outside_workspace(Path(WORKSPACE_ROOT) / "BCI_Shorts_Channel" / "leaked_tmp")


def test_compute_5gram_sha256_set_boundaries():
    assert compute_5gram_sha256_set("") == set()
    assert compute_5gram_sha256_set("only four words here") == set()
    h1 = compute_5gram_sha256_set("Lisa plays quietly on the carpet while her mother reads.")
    h2 = compute_5gram_sha256_set(["lisa plays quietly on the", "carpet, while her mother reads!"])
    assert len(h1) == 6
    assert len(h1 & h2) >= 2


def test_sanitize_structural_frame_bgr_masks_posters_skin_and_expands_916():
    # Synthetic 4:3 (360x480x3 -> h=360, w=480) frame with bright yellow cartoon poster & skin patch
    raw = np.full((360, 480, 3), (210, 214, 218), dtype=np.uint8)
    # Upper-left bright yellow cartoon poster decal
    raw[10:90, 10:90] = (0, 235, 255)
    # Center human warm-skin oval
    cv2.circle(raw, (240, 180), 38, (125, 158, 212), -1)

    san = sanitize_structural_frame_bgr(raw, target_w=720, target_h=1280)
    assert san.shape == (1280, 720, 3)
    # Zero black bars at top or bottom
    assert float(np.mean(san[:24, :])) > 150.0
    assert float(np.mean(san[-24:, :])) > 140.0
    # Upper-left poster region in the scaled middle band is neutralized (low chroma)
    mid_top_y = int(round((1280 - 540) * 0.44))
    poster_patch = san[mid_top_y + 18 : mid_top_y + 70, 18:80]
    hsv_patch = cv2.cvtColor(poster_patch, cv2.COLOR_BGR2HSV)
    assert float(np.mean(hsv_patch[:, :, 1])) < 35.0


def _build_synthetic_reenactment_project(tmp_path: Path) -> tuple[Path, Path, np.ndarray]:
    proj_dir = tmp_path / "reenact_test_proj"
    dos_dir = tmp_path / "ainsworth_test_dossier"
    (proj_dir / "02_script").mkdir(parents=True)
    (proj_dir / "03_visuals" / "reference_images").mkdir(parents=True)
    (proj_dir / "05_assembly").mkdir(parents=True)
    (proj_dir / "06_publish").mkdir(parents=True)
    dos_dir.mkdir(parents=True)

    # Source frame has vertical gradient -> deterministic dHash
    src_gray = np.tile(np.linspace(10, 240, 64, dtype=np.uint8), (64, 1))
    src_dhash = _dhash_64(src_gray)

    # Generated porcelain reference PNG has opposite checkerboard/horizontal structure -> large dHash distance
    yy, xx = np.mgrid[0:1280, 0:720]
    gen_gray = (((xx // 90 + yy // 110) % 2) * 180 + 55).astype(np.uint8)
    gen_bgr = cv2.cvtColor(gen_gray, cv2.COLOR_GRAY2BGR)
    ref_png = proj_dir / "03_visuals" / "reference_images" / "ref_clip_01.png"
    cv2.imwrite(str(ref_png), gen_bgr)

    src_transcript = "Lisa is twelve months old and enters the playroom with her mother for the first time."
    edl_doc = {
        "schema": "source_reenactment_edl_v1",
        "rule": "R67",
        "slug": "ainsworth_test_dossier",
        "shots": [
            {"shot_id": "S01", "camera_motion": "locked_tripod", "active_zones": ["left_chair_zone", "center_floor_playmat"]},
            {"shot_id": "S02", "camera_motion": "lateral_pan_right", "active_zones": ["right_chair_or_door_zone"]},
        ],
        "source_dhash_64_list": [src_dhash],
        "source_5gram_sha256_list": sorted(compute_5gram_sha256_set(src_transcript)),
        "source_personal_names": ["lisa", "lizbeth"],
        "sanitization_verified": True,
    }
    (proj_dir / "03_visuals" / "source_edl.json").write_text(json.dumps(edl_doc), encoding="utf-8")

    # 48 clips: 36 lab clips mapped to S01/S02 (75%), 12 living brain clips (25% >= 20%)
    clips = []
    for i in range(1, 37):
        clips.append(
            {
                "index": i,
                "grammar": "porcelain_cast_action",
                "source_shot_id": "S01" if i % 2 else "S02",
            }
        )
    for i in range(37, 49):
        clips.append(
            {
                "index": i,
                "grammar": "porcelain_living_brain",
                "brain_mode": "sagittal_coronal_cutaway",
            }
        )

    vp = {
        "schema_version": 7,
        "profile": "neuro_diorama",
        "style_profile": PORCELAIN_V7_STYLE_PROFILE,
        "dossier_slug": "ainsworth_test_dossier",
        "clips": clips,
    }
    (proj_dir / "03_visuals" / "visual_plan.json").write_text(json.dumps(vp), encoding="utf-8")
    (proj_dir / "02_script" / "script.json").write_text(
        json.dumps(
            {
                "sentences": [
                    "In 1970, psychologist Mary Ainsworth observed fifty-six one-year-old toddlers across eight brief separations.",
                    "Inside the child's brain, the amygdala triggers an immediate alarm when a caregiver steps outside.",
                ]
            }
        ),
        encoding="utf-8",
    )
    (proj_dir / "06_publish" / "metadata.json").write_text(
        json.dumps({"title": "1970 Strange Situation: How Babies Hide Panic"}),
        encoding="utf-8",
    )
    return proj_dir, dos_dir, src_gray


def test_validate_reenactment_rq1_to_rq5_happy_and_failure_edges(tmp_path: Path):
    proj_dir, dos_dir, src_gray = _build_synthetic_reenactment_project(tmp_path)

    # Render comparison sheet and verify it writes cleanly without triggering RQ1
    edl_doc = json.loads((proj_dir / "03_visuals" / "source_edl.json").read_text(encoding="utf-8"))
    sheet = render_reenactment_comparison_sheet(
        proj_dir,
        edl_doc,
        {"clip_anchors": [{"ref_id": "ref_clip_01", "filename": "ref_clip_01.png", "scene_id": "S01"}]},
    )
    assert sheet.exists()

    rep_ok = validate_reenactment_non_infringement(
        proj_dir,
        dossier_dir=dos_dir,
        require_quarantine_purged=False,
    )
    assert rep_ok["passed"] is True, rep_ok["failed_gates"]

    # RQ5 failure: stagnant >4.50s cut in edit_decision_list.json must fail RQ5
    asm_edl_path = proj_dir / "05_assembly" / "edit_decision_list.json"
    asm_edl_path.write_text(
        json.dumps({"cuts": [{"cut_index": i, "duration_sec": 6.40 if i == 1 else 3.10} for i in range(1, 48)]}),
        encoding="utf-8",
    )
    rep_rq5 = validate_reenactment_non_infringement(proj_dir, dossier_dir=dos_dir, require_quarantine_purged=False)
    assert "RQ5_brain_intercut_and_blocking_alignment" in rep_rq5["failed_gates"]
    asm_edl_path.unlink()

    # RQ1 failure: raw source.mp4 leaked inside dossier
    leaked = dos_dir / "source.mp4"
    leaked.write_bytes(b"fake")
    rep_rq1 = validate_reenactment_non_infringement(proj_dir, dossier_dir=dos_dir, require_quarantine_purged=False)
    assert "RQ1_zero_raw_source_leak" in rep_rq1["failed_gates"]
    leaked.unlink()

    # RQ2 failure: reference image identical to source frame dHash (distance 0 < 18)
    cv2.imwrite(
        str(proj_dir / "03_visuals" / "reference_images" / "ref_bad_copy.png"),
        cv2.cvtColor(src_gray, cv2.COLOR_GRAY2BGR),
    )
    rep_rq2 = validate_reenactment_non_infringement(proj_dir, dossier_dir=dos_dir, require_quarantine_purged=False)
    assert "RQ2_perceptual_dhash_distance" in rep_rq2["failed_gates"]
    (proj_dir / "03_visuals" / "reference_images" / "ref_bad_copy.png").unlink()

    # RQ3 failure: leaked personal name 'Lisa' and 5-gram overlap
    (proj_dir / "02_script" / "script.json").write_text(
        json.dumps({"sentences": ["Lisa is twelve months old and enters the playroom today."]}),
        encoding="utf-8",
    )
    rep_rq3 = validate_reenactment_non_infringement(proj_dir, dossier_dir=dos_dir, require_quarantine_purged=False)
    assert "RQ3_zero_transcript_and_name_overlap" in rep_rq3["failed_gates"]
    assert "lisa" in rep_rq3["gates"]["RQ3_zero_transcript_and_name_overlap"]["leaked_personal_names"]

    # Restore clean script, then test RQ4 cartoon poster brand token leak
    (proj_dir / "02_script" / "script.json").write_text(
        json.dumps({"sentences": ["A toddler explores wooden blocks beside a Tweety poster on the wall."]}),
        encoding="utf-8",
    )
    rep_rq4 = validate_reenactment_non_infringement(proj_dir, dossier_dir=dos_dir, require_quarantine_purged=False)
    assert "RQ4_zero_poster_or_brand_leak" in rep_rq4["failed_gates"]


def test_flow_zero_credit_batch_constants_and_adaptive_planner():
    import asyncio
    from pipeline.config import (
        DEFAULT_REENACT_IMAGE_BACKEND,
        FLOW_ZERO_CREDIT_IMAGE_BATCH_COUNT,
        FLOW_ZERO_CREDIT_IMAGE_FAMILY_ID,
        FLOW_ZERO_CREDIT_IMAGE_MODEL,
        FLOW_ZERO_CREDIT_MAX_CONCURRENT_RENDERS,
        FLOW_ZERO_CREDIT_VIDEO_MAX_BATCH,
        REENACT_IMAGE_BACKENDS,
    )
    from pipeline.flow_diorama_sharded_worker import compute_zero_credit_batch_plan
    from pipeline.flow_live_single_worker import _normalize_engine_mode
    from pipeline.source_reenactment import translate_porcelain_keyframes_async

    assert DEFAULT_REENACT_IMAGE_BACKEND == "flow"
    assert REENACT_IMAGE_BACKENDS == ("flow", "gemini")
    assert FLOW_ZERO_CREDIT_IMAGE_MODEL == "Nano Banana 2.1"
    assert FLOW_ZERO_CREDIT_IMAGE_FAMILY_ID == "beluga_display"
    assert FLOW_ZERO_CREDIT_IMAGE_BATCH_COUNT == 4
    assert FLOW_ZERO_CREDIT_MAX_CONCURRENT_RENDERS == 4
    assert FLOW_ZERO_CREDIT_VIDEO_MAX_BATCH == 4
    assert _normalize_engine_mode("zero_credit") == "zero-credit"
    assert _normalize_engine_mode("zero-credit") == "zero-credit"

    assert compute_zero_credit_batch_plan(0, 5) == (0, 1)
    assert compute_zero_credit_batch_plan(-3, 5) == (0, 1)
    assert compute_zero_credit_batch_plan(1, 5) == (1, 4)
    assert compute_zero_credit_batch_plan(2, 5) == (2, 2)
    assert compute_zero_credit_batch_plan(3, 5) == (3, 1)
    assert compute_zero_credit_batch_plan(64, 5) == (4, 1)
    assert compute_zero_credit_batch_plan(10, 1) == (1, 4)
    assert compute_zero_credit_batch_plan(10, 2) == (2, 2)

    for pending in range(1, 70):
        for req_tabs in (1, 2, 3, 4, 5, 8):
            n_tabs, out_cnt = compute_zero_credit_batch_plan(pending, req_tabs)
            assert 1 <= n_tabs <= FLOW_ZERO_CREDIT_MAX_CONCURRENT_RENDERS
            assert 1 <= out_cnt <= FLOW_ZERO_CREDIT_VIDEO_MAX_BATCH
            assert n_tabs * out_cnt <= FLOW_ZERO_CREDIT_MAX_CONCURRENT_RENDERS

    with pytest.raises(ValueError, match="Unsupported reenactment image backend"):
        asyncio.run(
            translate_porcelain_keyframes_async(
                Path("/tmp/nonexistent_proj"),
                "ainsworth_strange_situation",
                backend="paid_external_api",
            )
        )


def test_dynamic_episode_qa_gate2_enforces_reenactment_dhash_lock(tmp_path: Path):
    from pipeline.dynamic_episode_qa import verify_clip_multimodal_contract, write_episode_qa_contract

    proj_dir, _, src_gray = _build_synthetic_reenactment_project(tmp_path)
    vp = json.loads((proj_dir / "03_visuals" / "visual_plan.json").read_text(encoding="utf-8"))
    sents = ["In 1970, Mary Ainsworth observed toddlers.", "The amygdala triggers an alarm."]
    _, contract = write_episode_qa_contract(
        proj_dir,
        vp,
        sents,
        [{"clip_number": 1, "scene": "Matte-white porcelain figure in cardigan walks across room and sits."}],
    )
    assert "reenactment_dhash_lock" in contract
    assert contract["reenactment_dhash_lock"]["min_dhash_bits"] == 18

    def _write_test_mp4(dst: Path, frame_bgr: np.ndarray) -> None:
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        vw = cv2.VideoWriter(str(dst), fourcc, 12.0, (frame_bgr.shape[1], frame_bgr.shape[0]))
        for _ in range(54):  # 4.5s > 3.5s minimum
            vw.write(frame_bgr)
        vw.release()

    bad_mp4 = tmp_path / "clip_copycat.mp4"
    _write_test_mp4(bad_mp4, cv2.cvtColor(cv2.resize(src_gray, (180, 320)), cv2.COLOR_GRAY2BGR))
    bad_res = verify_clip_multimodal_contract(bad_mp4, 1, contract)
    assert bad_res["passed"] is False
    assert "reenact_dhash_too_close" in str(bad_res.get("reason", ""))

    yy, xx = np.mgrid[0:320, 0:180]
    good_gray = (((xx // 22 + yy // 28) % 2) * 170 + 60).astype(np.uint8)
    good_mp4 = tmp_path / "clip_porcelain.mp4"
    _write_test_mp4(good_mp4, cv2.cvtColor(good_gray, cv2.COLOR_GRAY2BGR))
    good_res = verify_clip_multimodal_contract(good_mp4, 1, contract)
    assert good_res["passed"] is True


def test_production_constants_md_ssot_parity_for_r66_r67_and_zero_credit():
    from pipeline import config as cfg

    md_path = Path(WORKSPACE_ROOT) / ".agents" / "rules" / "production_constants.md"
    md_lines = md_path.read_text(encoding="utf-8").splitlines()
    expected_pairs = [
        ("DEFAULT_DIORAMA_STYLE_PROFILE", cfg.DEFAULT_DIORAMA_STYLE_PROFILE),
        ("FLOW_ZERO_CREDIT_IMAGE_MODEL", cfg.FLOW_ZERO_CREDIT_IMAGE_MODEL),
        ("FLOW_ZERO_CREDIT_IMAGE_BATCH_COUNT", f"`{cfg.FLOW_ZERO_CREDIT_IMAGE_BATCH_COUNT}`"),
        ("FLOW_ZERO_CREDIT_MAX_CONCURRENT_RENDERS", f"`{cfg.FLOW_ZERO_CREDIT_MAX_CONCURRENT_RENDERS}`"),
        ("FLOW_ZERO_CREDIT_VIDEO_MAX_BATCH", f"`{cfg.FLOW_ZERO_CREDIT_VIDEO_MAX_BATCH}`"),
        ("REENACT_MIN_DHASH_DISTANCE", f"`{cfg.REENACT_MIN_DHASH_DISTANCE}`"),
        ("REENACT_BRAIN_RATIO_MIN", f"`{cfg.REENACT_BRAIN_RATIO_MIN:.2f}`"),
        ("DIORAMA_V7_US_PROSODY_MODE", cfg.DIORAMA_V7_US_PROSODY_MODE),
    ]
    for const_name, expected_val in expected_pairs:
        matching_rows = [ln for ln in md_lines if f"`{const_name}`" in ln]
        assert matching_rows, f"Missing constant `{const_name}` in production_constants.md"
        assert any(expected_val in ln for ln in matching_rows), (
            f"Value mismatch for `{const_name}` in production_constants.md: expected {expected_val} in {matching_rows}"
        )


