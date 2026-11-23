"""Regression & contract tests for R89 Archival & Supplementary Experiment Video (`Split-Sync` + `Viewfinder`)."""

from __future__ import annotations

import hashlib
import json
import os
import sys
import wave
from pathlib import Path

import av
import cv2
import numpy as np
import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from pipeline.archival_insert_builder import (  # noqa: E402
    ARCHIVAL_MANIFEST_REL,
    render_archival_insert_clips,
)
from pipeline.archival_video_builder import (  # noqa: E402
    ARCHIVAL_VIDEOS_MANIFEST_REL,
    ARCHIVAL_VIDEO_CLIPS_DIRNAME,
    audit_archival_video_eligibility,
    count_mp4_audio_streams,
    load_verified_archival_video_clip_map,
    render_archival_video_clips,
    render_split_sync_video_clip,
    render_viewfinder_video_clip,
    validate_archival_videos_manifest,
    validate_combined_archival_budget,
)
from pipeline.config import (  # noqa: E402
    R89_MODE1_BOTTOM_BRAIN_BOX,
    R89_MODE1_TOP_VIDEO_BOX,
    R89_MODE2_LOCATOR_BADGE_BOX,
    R89_MODE2_VIEWFINDER_BOX,
)
from pipeline.diorama_assembler import (  # noqa: E402
    _resolve_diorama_clip_files,
    enforce_combined_r88a_r89_edl_contract,
)
from pipeline.dynamic_episode_qa import verify_final_mp4_against_contract  # noqa: E402
from pipeline.publish import (  # noqa: E402
    extract_cc_by_archival_video_credits,
    format_v8_viewer_story_description,
    validate_v8_viewer_description,
)

_MATTE_BGR = np.array([22, 12, 8], dtype=np.uint8)


def _write_motion_mp4(
    path: Path,
    *,
    width: int = 640,
    height: int = 360,
    fps: int = 30,
    duration_sec: float = 2.6,
    add_audio: bool = False,
    frozen: bool = False,
    paint_face_marker_left: bool = False,
    paint_face_marker_right: bool = False,
    brain_style: bool = False,
) -> str:
    """Create a synthetic H.264 MP4 (`0` or `1` audio streams) with geometric motion and optional BGR marker blobs."""
    path.parent.mkdir(parents=True, exist_ok=True)
    n_frames = max(6, int(round(duration_sec * fps)))
    container = av.open(str(path), mode="w")
    try:
        v_stream = container.add_stream("libx264", rate=fps)
        v_stream.width = width
        v_stream.height = height
        v_stream.pix_fmt = "yuv420p"
        a_stream = container.add_stream("aac", rate=44100) if add_audio else None

        for idx in range(n_frames):
            t_idx = 0 if frozen else idx
            if brain_style:
                frame = np.full((height, width, 3), (28, 18, 12), dtype=np.uint8)
                cx = width // 2 + int(22 * np.sin(t_idx * 0.25))
                cy = height // 2 + int(16 * np.cos(t_idx * 0.20))
                cv2.ellipse(frame, (cx, cy), (width // 4, height // 4), 0, 0, 360, (195, 190, 185), -1)
                cv2.circle(frame, (cx + 15, cy - 10), max(12, width // 14), (255, 216, 39), -1)
            else:
                frame = np.full((height, width, 3), (42, 58, 76), dtype=np.uint8)
                x0 = int(40 + ((t_idx * 17) % max(40, width - 160)))
                y0 = int(45 + ((t_idx * 9) % max(40, height - 130)))
                cv2.rectangle(frame, (x0, y0), (min(width - 10, x0 + 95), min(height - 10, y0 + 70)), (230, 220, 120), -1)
                cv2.circle(frame, (max(20, width - 80 - (t_idx % 40)), height // 2), 28, (240, 240, 240), -1)

            if paint_face_marker_left:
                cv2.rectangle(frame, (24, 32), (width // 2 - 48, height - 32), (10, 20, 250), -1)
            if paint_face_marker_right:
                cv2.rectangle(frame, (width // 2 + 48, 32), (width - 24, height - 32), (10, 20, 250), -1)

            vf = av.VideoFrame.from_ndarray(frame, format="bgr24")
            for pkt in v_stream.encode(vf):
                container.mux(pkt)

        for pkt in v_stream.encode(None):
            container.mux(pkt)

        if a_stream is not None:
            total_samples = int(round(duration_sec * 44100))
            chunk = 1024
            for start_s in range(0, total_samples, chunk):
                n_s = min(chunk, total_samples - start_s)
                pcm = np.zeros((1, n_s), dtype=np.float32)
                af = av.AudioFrame.from_ndarray(pcm, format="fltp", layout="mono")
                af.sample_rate = 44100
                af.pts = start_s
                for pkt in a_stream.encode(af):
                    container.mux(pkt)
            for pkt in a_stream.encode(None):
                container.mux(pkt)
    finally:
        container.close()
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_stereo_wav(path: Path, *, duration_sec: float = 12.0, sr: int = 24000) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    n = int(round(duration_sec * sr))
    t = np.linspace(0.0, duration_sec, n, endpoint=False)
    left = (np.sin(2.0 * np.pi * 220.0 * t) * 7000).astype(np.int16)
    right = (np.sin(2.0 * np.pi * 224.0 * t + 0.5) * 7000).astype(np.int16)
    interleaved = np.column_stack([left, right]).reshape(-1)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(interleaved.tobytes())


def _write_tiny_png(path: Path, rgb: tuple[int, int, int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    bgr = np.full((1920, 1080, 3), (rgb[2], rgb[1], rgb[0]), dtype=np.uint8)
    cv2.imwrite(str(path), bgr)


def _write_minimal_ass(path: Path, sentences: list[str], total_dur: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "[Script Info]",
        "ScriptType: v4.00+",
        "PlayResX: 1080",
        "PlayResY: 1920",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        "Style: Default,Inter ExtraBold,82,&H00FFFFFF,&H00FFFFFF,&H00080C16,&H00000000,1,0,0,0,100,100,0,0,1,7,0,2,80,80,510,1",
        "Style: HookTitle,Inter Black,118,&H00FFFFFF,&H00FFFFFF,&H00080C16,&H00000000,1,0,0,0,100,100,0,0,1,8,0,8,90,90,340,1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
        "Dialogue: 0,0:00:00.00,0:00:02.10,HookTitle,,0,0,0,,Split-brain visual test",
    ]
    step = total_dur / max(1, len(sentences))
    for i, sent in enumerate(sentences):
        t0 = i * step
        t1 = (i + 1) * step
        lines.append(f"Dialogue: 0,0:00:{t0:05.2f},0:00:{t1:05.2f},Default,,0,0,0,,{sent}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _concat_clips_to_mp4(clip_paths: list[Path], out_mp4: Path, *, fps: int = 30) -> None:
    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    container = av.open(str(out_mp4), mode="w")
    try:
        v_stream = container.add_stream("libx264", rate=fps)
        v_stream.width = 1080
        v_stream.height = 1920
        v_stream.pix_fmt = "yuv420p"
        for cp in clip_paths:
            in_c = av.open(str(cp))
            try:
                for frame in in_c.decode(video=0):
                    bgr = frame.to_ndarray(format="bgr24")
                    if bgr.shape[1] != 1080 or bgr.shape[0] != 1920:
                        bgr = cv2.resize(bgr, (1080, 1920), interpolation=cv2.INTER_AREA)
                    vf = av.VideoFrame.from_ndarray(bgr, format="bgr24")
                    for pkt in v_stream.encode(vf):
                        container.mux(pkt)
            finally:
                in_c.close()
        for pkt in v_stream.encode(None):
            container.mux(pkt)
    finally:
        container.close()


def _plos_ccby_entry(**overrides) -> dict:
    base = {
        "clip_number": 2,
        "mode": "split_sync",
        "duration_sec": 2.4,
        "start_sec": 2.6,
        "license": "CC BY 4.0",
        "license_uri": "https://creativecommons.org/licenses/by/4.0/",
        "author": "Chen",
        "journal": "PLOS Biology",
        "publication_year": 2024,
        "supplementary_movie_id": "Supplementary Movie 1",
        "article_url": "https://journals.plos.org/plosbiology/article?id=10.1371/journal.pbio.3002001",
        "source_url": "https://journals.plos.org/plosbiology/article/file?type=supplementary&id=10.1371/journal.pbio.3002001.s001",
        "article_license_verified": True,
        "flow_upload_count": 0,
    }
    base.update(overrides)
    return base


def _federal_intramural_entry(**overrides) -> dict:
    base = {
        "clip_number": 3,
        "mode": "viewfinder_locator",
        "duration_sec": 2.4,
        "start_sec": 5.0,
        "license": "17 U.S.C. § 105",
        "creator_agency": "NIH / NIMH",
        "is_federal_employee_work": True,
        "source_url": "https://www.nimh.nih.gov/research/intramural/split_task.mp4",
        "flow_upload_count": 0,
    }
    base.update(overrides)
    return base


def test_r89_legal_journal_traps_and_positive_eligibility() -> None:
    # 1. Fair Use ban -> route to R67
    res_fu = audit_archival_video_eligibility(
        _plos_ccby_entry(rights_note="Clip included under Section 107 Fair Use transformativity."),
        check_video_pixels=False,
    )
    assert res_fu["eligible"] is False
    assert res_fu["route_to"] == "R67"
    assert any("r89_fair_use_forbidden" in x for x in res_fu["issues"])

    # 2. Classic restricted behavioral experiment footage traps -> route to R67
    for trap_title in (
        "Milgram obedience shock archival reel",
        "Gazzaniga split-brain patient Joe lateralized task",
        "Walter Mischel Stanford Marshmallow Test room video",
        "Mary Ainsworth Strange Situation infant room tape",
        "B.F. Skinner Foundation Pigeon ping pong film",
        "Harvard Film Archive animal operant conditioning reel",
        "Patient H.M. Brenda Milner Montreal Neurological tape",
        "Harry Harlow cloth mother rhesus surrogate film",
    ):
        r_trap = audit_archival_video_eligibility(
            _federal_intramural_entry(title=trap_title, license="CC0 1.0", creator_agency=""),
            check_video_pixels=False,
        )
        assert r_trap["eligible"] is False, f"Expected classic trap rejection for: {trap_title}"
        assert r_trap["route_to"] == "R67"

    # Exception: genuine federal Project Pigeon without Skinner Foundation / Harvard restriction
    r_pigeon_ok = audit_archival_video_eligibility(
        _federal_intramural_entry(title="WWII Project Pigeon guidance laboratory test"),
        check_video_pixels=False,
    )
    assert r_pigeon_ok["eligible"] is True
    assert r_pigeon_ok["license_class"] == "direct_insert_pd_cc0"

    # 3. Journal & copyleft traps: PNAS, Science Advances, Springer Nature caption carve-out, CC BY-SA
    for bad_item, code_substr in (
        (_plos_ccby_entry(journal="PNAS", license="CC BY-NC-ND 4.0"), "r89_banned_or_sharealike_license"),
        (_plos_ccby_entry(journal="PNAS", article_license_verified=False), "r89_journal_license_unverified"),
        (_plos_ccby_entry(journal="Science Advances", license="CC BY-NC 4.0"), "r89_banned_or_sharealike_license"),
        (_plos_ccby_entry(journal="Science Advances", article_license_verified=False), "r89_journal_license_unverified"),
        (
            _plos_ccby_entry(
                journal="Nature Communications",
                caption="Supplementary Movie 2. Behavioral trial excluded from the CC BY article license; third party permission required.",
            ),
            "r89_caption_carveout_excluded",
        ),
        (_plos_ccby_entry(license="CC BY-SA 4.0", license_uri="https://creativecommons.org/licenses/by-sa/4.0/"), "r89_banned_or_sharealike_license"),
        (
            {
                "clip_number": 2,
                "mode": "viewfinder_locator",
                "duration_sec": 2.4,
                "license": "17 U.S.C. 105",
                "title": "University lab experiment funded by NIH R01 grant",
                "creator_agency": "State University Neuroscience Dept",
                "source_url": "https://example.edu/grant_movie.mp4",
            },
            "r89_grant_funded_not_federal_work",
        ),
        (
            {
                "clip_number": 2,
                "mode": "viewfinder_locator",
                "duration_sec": 2.4,
                "license": "Public Domain",
                "publication_year": 1965,
                "source_url": "https://archive.org/details/exp1965_upload",
            },
            "r89_false_public_domain_trap",
        ),
        (_plos_ccby_entry(contains_minor=True), "r89_minor_or_patient_banned"),
        (_plos_ccby_entry(contains_identifiable_patient=True), "r89_minor_or_patient_banned"),
    ):
        res_bad = audit_archival_video_eligibility(bad_item, check_video_pixels=False)
        assert res_bad["eligible"] is False
        assert any(code_substr in msg for msg in res_bad["issues"]), (bad_item, res_bad)

    # 4. Verified journal & verified intramural positives
    assert audit_archival_video_eligibility(_plos_ccby_entry(), check_video_pixels=False)["eligible"] is True
    assert audit_archival_video_eligibility(
        _plos_ccby_entry(journal="PNAS", article_license_verified=True), check_video_pixels=False
    )["eligible"] is True
    assert audit_archival_video_eligibility(
        _plos_ccby_entry(journal="Science Advances", article_license_verified=True), check_video_pixels=False
    )["eligible"] is True
    assert audit_archival_video_eligibility(_federal_intramural_entry(), check_video_pixels=False)["eligible"] is True


def test_r89_crop_face_privacy_motion_cut_and_budget_gates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _marker_face_detector(bgr: np.ndarray, *, score_threshold: float = 0.42) -> list[list[float]]:
        # Simulate YuNet detecting red face-marker blob inside whichever cropped ROI is inspected.
        mask = (bgr[:, :, 2] > 200) & (bgr[:, :, 1] < 60) & (bgr[:, :, 0] < 60)
        if int(np.sum(mask)) > 200:
            return [[20.0, 20.0, 60.0, 60.0, max(score_threshold + 0.35, 0.85)]]
        return []

    monkeypatch.setattr("pipeline.archival_video_builder.detect_human_faces_yunet", _marker_face_detector)

    face_left_src = tmp_path / "face_left_monitor_right.mp4"
    _write_motion_mp4(face_left_src, paint_face_marker_left=True)

    # Uncropped -> sees left face -> rejected
    uncropped = audit_archival_video_eligibility(_federal_intramural_entry(), video_path=face_left_src)
    assert uncropped["eligible"] is False
    assert uncropped["yunet_faces_detected"] >= 1
    assert any("r89_privacy_human_face_detected" in x for x in uncropped["issues"])

    # Tight privacy crop on right side (x=320..640) excludes left face -> clean 0-Face pass
    cropped = audit_archival_video_eligibility(
        _federal_intramural_entry(crop_box=[320, 0, 640, 360]),
        video_path=face_left_src,
    )
    assert cropped["eligible"] is True
    assert cropped["yunet_faces_detected"] == 0
    assert cropped["max_frame_diff"] >= 0.30

    # Frozen slide -> rejected
    frozen_src = tmp_path / "frozen.mp4"
    _write_motion_mp4(frozen_src, frozen=True)
    res_frozen = audit_archival_video_eligibility(_federal_intramural_entry(), video_path=frozen_src)
    assert res_frozen["eligible"] is False
    assert any("r89_frozen_video_source" in x for x in res_frozen["issues"])

    # Manifest validation: Cut 1 ban, start < 2.20s ban, flow upload ban, combined R88-A + R89 budget
    clean_src = tmp_path / "clean_src.mp4"
    clean_sha = _write_motion_mp4(clean_src)
    brain_src = tmp_path / "brain_src.mp4"
    _write_motion_mp4(brain_src, brain_style=True)

    proj = tmp_path / "ep_manifest_checks"
    (proj / "03_visuals").mkdir(parents=True, exist_ok=True)
    (proj / ARCHIVAL_MANIFEST_REL).write_text(
        json.dumps({"inserts": [{"clip_number": 4, "duration_sec": 4.0}]}),
        encoding="utf-8",
    )
    bad_mf = {
        "videos": [
            _plos_ccby_entry(
                clip_number=1,
                start_sec=1.5,
                flow_upload_count=1,
                video_path=str(clean_src),
                brain_video_path=str(brain_src),
                video_sha256=clean_sha,
            )
        ]
    }
    (proj / ARCHIVAL_VIDEOS_MANIFEST_REL).write_text(json.dumps(bad_mf), encoding="utf-8")
    v_bad = validate_archival_videos_manifest(proj, episode_duration_sec=60.0)
    assert v_bad["passed"] is False
    joined_bad = "\n".join(v_bad["issues"])
    for code in (
        "r89_cut_1_hook_forbidden",
        "r89_start_before_hook_clearance",
        "r89_flow_upload_forbidden",
        "r89_combined_share_exceeded",
    ):
        assert code in joined_bad

    # Combined budget helper directly
    assert validate_combined_archival_budget(1, 3.0, 1, 3.5, episode_duration_sec=70.0) == []
    assert any(
        "r89_combined_cut_cap_exceeded" in x
        for x in validate_combined_archival_budget(1, 2.0, 2, 4.0, episode_duration_sec=80.0)
    )
    assert any(
        "r89_combined_share_exceeded" in x
        for x in validate_combined_archival_budget(1, 4.0, 1, 4.0, episode_duration_sec=65.0)
    )


def test_r89_render_modes_audio_zero_geometry_and_diorama_edl_contract(tmp_path: Path) -> None:
    proj = tmp_path / "ep_render_modes"
    for d in ("03_visuals/archival_sources", "03_visuals/flow_native_clips", "05_assembly"):
        (proj / d).mkdir(parents=True, exist_ok=True)

    src_ok = proj / "03_visuals/archival_sources/exp_motion.mp4"
    src_sha = _write_motion_mp4(src_ok, duration_sec=2.6)
    brain_ok = proj / "03_visuals/archival_sources/brain_ref.mp4"
    _write_motion_mp4(brain_ok, duration_sec=2.6, brain_style=True)

    # Confirm count_mp4_audio_streams catches non-zero audio tracks and passes 0 on muted MP4
    with_audio = proj / "03_visuals/archival_sources/with_audio.mp4"
    _write_motion_mp4(with_audio, duration_sec=2.2, add_audio=True)
    assert count_mp4_audio_streams(with_audio) == 1
    assert count_mp4_audio_streams(src_ok) == 0

    m1_mp4 = proj / "m1.mp4"
    m2_mp4 = proj / "m2_pd.mp4"
    m2_cc_mp4 = proj / "m2_cc.mp4"
    render_split_sync_video_clip(
        src_ok,
        brain_ok,
        m1_mp4,
        duration_sec=2.4,
        credit_text="Adapted from Chen et al., 2024 (CC BY 4.0)",
    )
    render_viewfinder_video_clip(src_ok, m2_mp4, duration_sec=2.4, credit_text=None)
    render_viewfinder_video_clip(
        src_ok,
        m2_cc_mp4,
        duration_sec=2.4,
        credit_text="Adapted from Doe et al., 2023 (CC BY 4.0)",
    )

    for mp4 in (m1_mp4, m2_mp4, m2_cc_mp4):
        assert count_mp4_audio_streams(mp4) == 0
        cap = cv2.VideoCapture(str(mp4))
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = float(cap.get(cv2.CAP_PROP_FPS))
        fc = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        ok0, f0 = cap.read()
        cap.set(cv2.CAP_PROP_POS_FRAMES, fc - 1)
        ok1, f1 = cap.read()
        cap.release()
        assert (w, h) == (1080, 1920)
        assert abs(fps - 30.0) <= 0.1
        assert fc == 72
        assert ok0 and ok1 and f0 is not None and f1 is not None
        # Subtitle & top HookTitle bands remain pure #080C16 matte (no caption/subtitle collision)
        assert float(np.max(np.abs(f0[1240:1450, :].astype(np.float32) - _MATTE_BGR))) <= 3.0
        assert float(np.max(np.abs(f0[120:275, :].astype(np.float32) - _MATTE_BGR))) <= 3.0

    # Inspect Mode 1 top + bottom brain motion viewports
    cap1 = cv2.VideoCapture(str(m1_mp4))
    _, m1_a = cap1.read()
    cap1.set(cv2.CAP_PROP_POS_FRAMES, 60)
    _, m1_b = cap1.read()
    cap1.release()
    tx0, ty0, tx1, ty1 = R89_MODE1_TOP_VIDEO_BOX
    bx0, by0, bx1, by1 = R89_MODE1_BOTTOM_BRAIN_BOX
    assert float(np.mean(np.abs(m1_a[ty0 + 20 : ty1 - 20, tx0 + 20 : tx1 - 20].astype(np.float32) - m1_b[ty0 + 20 : ty1 - 20, tx0 + 20 : tx1 - 20].astype(np.float32)))) > 0.5
    assert float(np.mean(np.abs(m1_a[by0 + 20 : by1 - 20, bx0 + 20 : bx1 - 20].astype(np.float32) - m1_b[by0 + 20 : by1 - 20, bx0 + 20 : bx1 - 20].astype(np.float32)))) > 0.5

    # Inspect Mode 2 viewfinder, A01 locator badge presence, and optional CC-BY pill
    cap2p = cv2.VideoCapture(str(m2_mp4))
    _, m2p_0 = cap2p.read()
    cap2p.release()
    cap2c = cv2.VideoCapture(str(m2_cc_mp4))
    _, m2c_0 = cap2c.read()
    cap2c.release()
    lx0, ly0, lx1, ly1 = R89_MODE2_LOCATOR_BADGE_BOX
    assert float(np.mean(np.abs(m2p_0[ly0:ly1, lx0:lx1].astype(np.float32) - _MATTE_BGR))) > 5.0
    # PD/CC0 Mode 2 leaves credit pill slot clean #080C16 matte; CC-BY Mode 2 draws pill inside 312..896, 1084..1138
    assert float(np.max(np.abs(m2p_0[1084:1138, 320:880].astype(np.float32) - _MATTE_BGR))) <= 3.0
    assert float(np.mean(np.abs(m2c_0[1084:1138, 320:880].astype(np.float32) - _MATTE_BGR))) > 1.5

    # Full manifest render -> _resolve_diorama_clip_files -> enforce_combined_r88a_r89_edl_contract
    for idx in (1, 2, 3, 4):
        _write_motion_mp4(proj / f"03_visuals/flow_native_clips/clip_{idx}.mp4", duration_sec=2.4)
    (proj / ARCHIVAL_VIDEOS_MANIFEST_REL).write_text(
        json.dumps(
            {
                "videos": [
                    _plos_ccby_entry(
                        clip_number=2,
                        start_sec=2.6,
                        duration_sec=2.4,
                        video_path="03_visuals/archival_sources/exp_motion.mp4",
                        brain_video_path="03_visuals/archival_sources/brain_ref.mp4",
                        video_sha256=src_sha,
                    ),
                    _federal_intramural_entry(
                        clip_number=3,
                        start_sec=5.0,
                        duration_sec=2.4,
                        video_path="03_visuals/archival_sources/exp_motion.mp4",
                        video_sha256=src_sha,
                    ),
                ]
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    render_res = render_archival_video_clips(proj, episode_duration_sec=60.0)
    assert render_res["passed"] is True
    resolved = _resolve_diorama_clip_files(proj / "03_visuals")
    assert [p.name for p in resolved] == ["clip_1.mp4", "clip_02.mp4", "clip_03.mp4", "clip_4.mp4"]
    assert resolved[1].parent.name == ARCHIVAL_VIDEO_CLIPS_DIRNAME
    assert resolved[2].parent.name == ARCHIVAL_VIDEO_CLIPS_DIRNAME

    vmap = load_verified_archival_video_clip_map(proj / "03_visuals")
    assert set(vmap.keys()) == {2, 3}

    edl_ok = {
        "total_duration_sec": 60.0,
        "cuts": [
            {"cut_index": 1, "clip_index": 1, "clip_file": "clip_1.mp4", "start": 0.0, "end": 2.5},
            {"cut_index": 2, "clip_index": 2, "clip_file": "03_visuals/archival_video_clips/clip_02.mp4", "start": 2.5, "end": 4.9},
            {"cut_index": 3, "clip_index": 3, "clip_file": "03_visuals/archival_video_clips/clip_03.mp4", "start": 4.9, "end": 7.3},
            {"cut_index": 4, "clip_index": 4, "clip_file": "clip_4.mp4", "start": 7.3, "end": 10.0},
        ],
    }
    edl_ret = enforce_combined_r88a_r89_edl_contract(proj, edl_ok, 60.0)
    assert edl_ret["passed"] is True
    assert len(edl_ret["r89_cuts"]) == 2

    # Exceed combined R88-A + R89 cut cap (>2) -> raises ValueError
    (proj / ARCHIVAL_MANIFEST_REL).write_text(
        json.dumps({"inserts": [{"clip_number": 4, "duration_sec": 1.8}]}),
        encoding="utf-8",
    )
    edl_over = {
        "total_duration_sec": 60.0,
        "cuts": [
            {"cut_index": 1, "clip_index": 1, "clip_file": "clip_1.mp4", "start": 0.0, "end": 2.5},
            {"cut_index": 2, "clip_index": 2, "clip_file": "03_visuals/archival_video_clips/clip_02.mp4", "start": 2.5, "end": 4.9},
            {"cut_index": 3, "clip_index": 3, "clip_file": "03_visuals/archival_video_clips/clip_03.mp4", "start": 4.9, "end": 7.3},
            {"cut_index": 4, "clip_index": 4, "clip_file": "03_visuals/archival_insert_clips/clip_04.mp4", "start": 7.3, "end": 9.1},
        ],
    }
    with pytest.raises(ValueError, match="r89_combined_cut_cap_exceeded"):
        enforce_combined_r88a_r89_edl_contract(proj, edl_over, 60.0)


def _setup_r89_dq_episode(
    tmp_path: Path,
    name: str,
    *,
    mode1_frozen: bool = False,
    face_in_vf: bool = False,
    face_in_badge_only: bool = False,
    clip_on_cut_1: bool = False,
) -> tuple[Path, Path]:
    proj = tmp_path / name
    for d in (
        "02_script",
        "03_visuals/archival_sources",
        "03_visuals/flow_native_clips",
        "04_audio",
        "05_assembly",
        "06_publish",
    ):
        (proj / d).mkdir(parents=True, exist_ok=True)

    src_vid = proj / "03_visuals/archival_sources/clean_behavior.mp4"
    src_sha = _write_motion_mp4(src_vid, duration_sec=2.6, frozen=False)
    brain_vid = proj / "03_visuals/archival_sources/brain_3d.mp4"
    _write_motion_mp4(brain_vid, duration_sec=2.6, brain_style=True)

    c1_clip = proj / "03_visuals/flow_native_clips/clip_1.mp4"
    c4_clip = proj / "03_visuals/flow_native_clips/clip_4.mp4"
    _write_motion_mp4(c1_clip, width=1080, height=1920, duration_sec=2.5, brain_style=True)
    _write_motion_mp4(c4_clip, width=1080, height=1920, duration_sec=2.6, brain_style=True)

    (proj / ARCHIVAL_VIDEOS_MANIFEST_REL).write_text(
        json.dumps(
            {
                "videos": [
                    _plos_ccby_entry(
                        clip_number=2,
                        start_sec=2.5,
                        duration_sec=2.5,
                        video_path="03_visuals/archival_sources/clean_behavior.mp4",
                        brain_video_path="03_visuals/archival_sources/brain_3d.mp4",
                        video_sha256=src_sha,
                    ),
                    _federal_intramural_entry(
                        clip_number=3,
                        start_sec=5.0,
                        duration_sec=2.5,
                        video_path="03_visuals/archival_sources/clean_behavior.mp4",
                        video_sha256=src_sha,
                    ),
                ]
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    render_res = render_archival_video_clips(proj, episode_duration_sec=60.0)
    c2_clip = Path(render_res["rendered_clips"][0]["path"])
    c3_clip = Path(render_res["rendered_clips"][1]["path"])

    # Optionally freeze rendered Mode 1 clip post-render to verify DQ7 detects a stalled R89 cut
    if mode1_frozen:
        in_c2 = av.open(str(c2_clip))
        frames2 = [f.to_ndarray(format="bgr24") for f in in_c2.decode(video=0)]
        in_c2.close()
        out_c2 = av.open(str(c2_clip), mode="w")
        vs2 = out_c2.add_stream("libx264", rate=30)
        vs2.width = 1080
        vs2.height = 1920
        vs2.pix_fmt = "yuv420p"
        for _ in frames2:
            vf2 = av.VideoFrame.from_ndarray(frames2[0], format="bgr24")
            for pkt in vs2.encode(vf2):
                out_c2.mux(pkt)
        for pkt in vs2.encode(None):
            out_c2.mux(pkt)
        out_c2.close()
        mf_doc2 = json.loads((proj / ARCHIVAL_VIDEOS_MANIFEST_REL).read_text(encoding="utf-8"))
        mf_doc2["videos"][0]["rendered_clip_sha256"] = hashlib.sha256(c2_clip.read_bytes()).hexdigest()
        (proj / ARCHIVAL_VIDEOS_MANIFEST_REL).write_text(json.dumps(mf_doc2, indent=2), encoding="utf-8")

    # Optionally paint synthetic face marker in Mode 2 viewfinder or inside the masked A01 badge corner
    if face_in_vf or face_in_badge_only:
        in_c = av.open(str(c3_clip))
        frames = [f.to_ndarray(format="bgr24") for f in in_c.decode(video=0)]
        in_c.close()
        out_c = av.open(str(c3_clip), mode="w")
        vs = out_c.add_stream("libx264", rate=30)
        vs.width = 1080
        vs.height = 1920
        vs.pix_fmt = "yuv420p"
        for fr in frames:
            if face_in_vf:
                vx0, vy0, _, _ = R89_MODE2_VIEWFINDER_BOX
                cv2.rectangle(fr, (vx0 + 220, vy0 + 180), (vx0 + 440, vy0 + 380), (10, 20, 250), -1)
            if face_in_badge_only:
                bx0, by0, bx1, by1 = R89_MODE2_LOCATOR_BADGE_BOX
                cv2.rectangle(fr, (bx0 + 25, by0 + 25), (bx1 - 25, by1 - 25), (10, 20, 250), -1)
            vf = av.VideoFrame.from_ndarray(fr, format="bgr24")
            for pkt in vs.encode(vf):
                out_c.mux(pkt)
        for pkt in vs.encode(None):
            out_c.mux(pkt)
        out_c.close()
        # Update sha256 in manifest to isolate DQ8 frame inspection
        new_sha = hashlib.sha256(c3_clip.read_bytes()).hexdigest()
        mf_doc = json.loads((proj / ARCHIVAL_VIDEOS_MANIFEST_REL).read_text(encoding="utf-8"))
        mf_doc["videos"][1]["rendered_clip_sha256"] = new_sha
        (proj / ARCHIVAL_VIDEOS_MANIFEST_REL).write_text(json.dumps(mf_doc, indent=2), encoding="utf-8")

    cuts = [
        {
            "cut_index": 1,
            "clip_index": (2 if clip_on_cut_1 else 1),
            "clip_file": ("03_visuals/archival_video_clips/clip_02.mp4" if clip_on_cut_1 else "clip_1.mp4"),
            "sentence_index": 1,
            "end_sentence_index": 1,
            "start": 0.0,
            "end": 2.5,
            "out_start_sec": 0.0,
            "out_end_sec": 2.5,
            "duration_sec": 2.5,
            "src_start_sec": 0.0,
            "main_speed": 1.0,
            "camera_move": "gentle_push_in",
            "grammar": "expressive_vinyl_world",
            "location_id": "lab_room",
            "mode": "single",
        },
        {
            "cut_index": 2,
            "clip_index": 2,
            "clip_file": "03_visuals/archival_video_clips/clip_02.mp4",
            "sentence_index": 2,
            "end_sentence_index": 2,
            "start": 2.5,
            "end": 5.0,
            "out_start_sec": 2.5,
            "out_end_sec": 5.0,
            "duration_sec": 2.5,
            "src_start_sec": 0.0,
            "main_speed": 1.0,
            "camera_move": "gentle_pull_back",
            "grammar": "expressive_vinyl_world",
            "location_id": "archive_split",
            "mode": "single",
        },
        {
            "cut_index": 3,
            "clip_index": 3,
            "clip_file": "03_visuals/archival_video_clips/clip_03.mp4",
            "sentence_index": 3,
            "end_sentence_index": 3,
            "start": 5.0,
            "end": 7.5,
            "out_start_sec": 5.0,
            "out_end_sec": 7.5,
            "duration_sec": 2.5,
            "src_start_sec": 0.0,
            "main_speed": 1.0,
            "camera_move": "locked_tripod",
            "grammar": "expressive_vinyl_world",
            "location_id": "archive_vf",
            "mode": "single",
        },
        {
            "cut_index": 4,
            "clip_index": 4,
            "clip_file": "clip_4.mp4",
            "sentence_index": 4,
            "end_sentence_index": 4,
            "start": 7.5,
            "end": 10.1,
            "out_start_sec": 7.5,
            "out_end_sec": 10.1,
            "duration_sec": 2.6,
            "src_start_sec": 0.0,
            "main_speed": 1.0,
            "camera_move": "gentle_push_in",
            "grammar": "expressive_xray_brain",
            "location_id": "brain_mode2",
            "mode": "single",
        },
    ]
    total_dur = 10.1
    final_mp4 = proj / "05_assembly/final_shorts_1080x1920.mp4"
    _concat_clips_to_mp4([c2_clip if clip_on_cut_1 else c1_clip, c2_clip, c3_clip, c4_clip], final_mp4)

    sentences = [
        "Split-brain patients reveal how both hemispheres split visual clues.",
        "Archival recordings capture each silent response inside the booth.",
        "Telemetry viewfinders track intact responses across visual trials.",
        "Real brain wiring lights up as signals cross intact white matter.",
    ] + [f"Sentence {i} explains another step in the laboratory circuit." for i in range(5, 15)]
    (proj / "02_script/script.json").write_text(
        json.dumps(
            {
                "schema": 8,
                "style_profile": "expressive_25d_v8",
                "format_profile": "shorts_expressive_v8",
                "project_id": proj.name,
                "allow_legacy_v8_clip_count": True,
                "sentences": sentences,
            }
        ),
        encoding="utf-8",
    )
    vp_clips = [
        {
            "clip_number": 1,
            "sentence_index": 1,
            "grammar": "expressive_vinyl_world",
            "location_id": "lab_room",
            "camera_move": "gentle_push_in",
            "scene": "Bald cream-white vinyl researcher adjusts a dial at the lab desk.",
        },
        {
            "clip_number": 2,
            "sentence_index": 2,
            "grammar": "expressive_vinyl_world",
            "location_id": "archive_split",
            "camera_move": "gentle_pull_back",
            "scene": "Archival split-sync behavioral recording synced to brain model.",
        },
        {
            "clip_number": 3,
            "sentence_index": 3,
            "grammar": "expressive_vinyl_world",
            "location_id": "archive_vf",
            "camera_move": "locked_tripod",
            "scene": "Archival dark-navy viewfinder monitor with porcelain head locator badge.",
        },
        {
            "clip_number": 4,
            "sentence_index": 4,
            "grammar": "expressive_xray_brain",
            "location_id": "brain_mode2",
            "camera_move": "gentle_push_in",
            "brain_clip": True,
            "scene": "Ep #31 matte silver-white 3D cutaway brain highlights the cortex.",
        },
    ] + [
        {
            "clip_number": i,
            "sentence_index": i,
            "grammar": "expressive_xray_brain" if i % 2 == 0 else "expressive_vinyl_world",
            "location_id": f"loc_{i}",
            "camera_move": "gentle_push_in",
            "brain_clip": (i % 2 == 0),
            "scene": "Bald cream-white vinyl researcher checks notes at the lab table.",
        }
        for i in range(5, 15)
    ]
    (proj / "03_visuals/visual_plan.json").write_text(
        json.dumps(
            {
                "schema": 8,
                "style_profile": "expressive_25d_v8",
                "format_profile": "shorts_expressive_v8",
                "allow_legacy_v8_clip_count": True,
                "clips": vp_clips,
            }
        ),
        encoding="utf-8",
    )
    (proj / "04_audio/voice_report.json").write_text(
        json.dumps(
            {
                "engine": "elevenlabs_v4",
                "actual_wpm": 162.0,
                "active_speech_ratio": 0.92,
                "true_rms_voiced_ratio": 0.92,
                "speech_end_sec": 9.8,
            }
        ),
        encoding="utf-8",
    )
    _write_stereo_wav(proj / "04_audio/audio_master.wav", duration_sec=total_dur)
    os.utime(proj / "04_audio/audio_master.wav", None)
    _write_minimal_ass(proj / "04_audio/subtitles.ass", sentences, total_dur)
    (proj / "05_assembly/edit_decision_list.json").write_text(
        json.dumps(
            {
                "schema": 8,
                "fps": 30,
                "total_duration_sec": 60.0,
                "zero_clip_reuse": True,
                "max_clip_reuse": 1,
                "allow_legacy_v8_clip_count": True,
                "cuts": cuts,
            }
        ),
        encoding="utf-8",
    )
    _write_tiny_png(proj / "06_publish/thumbnail_var_A.png", (10, 40, 90))
    _write_tiny_png(proj / "06_publish/thumbnail_var_B.png", (180, 60, 20))
    _write_tiny_png(proj / "06_publish/thumbnail_var_C.png", (30, 170, 210))
    return proj, final_mp4


def test_r89_dynamic_episode_qa_pass_and_failure_gates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # 1. Clean E2E episode with real YuNet detector (0 false positives)
    proj_ok, _mp4_ok = _setup_r89_dq_episode(tmp_path, "r89_dq_pass")
    res_ok = verify_final_mp4_against_contract(proj_ok)
    g = res_ok["gates"]
    assert g["DQ6_zero_clip_reuse"]["passed"] is True, g["DQ6_zero_clip_reuse"]
    assert g["DQ6_zero_clip_reuse"]["r89_archival_video_ok"] is True
    assert g["DQ7_continuous_motion_no_freeze"]["passed"] is True, g["DQ7_continuous_motion_no_freeze"]
    assert g["DQ8_zero_uncanny_skin_gore"]["passed"] is True, g["DQ8_zero_uncanny_skin_gore"]
    assert g["DQ8_zero_uncanny_skin_gore"]["verified_archival_video_cuts"] == [2, 3]
    assert g["DQ9_zero_background_plaque"]["passed"] is True, g["DQ9_zero_background_plaque"]

    # 2. Cut 1 placement fails DQ6
    proj_c1, _mp4_c1 = _setup_r89_dq_episode(tmp_path, "r89_dq_cut1", clip_on_cut_1=True)
    res_c1 = verify_final_mp4_against_contract(proj_c1)
    assert res_c1["gates"]["DQ6_zero_clip_reuse"]["passed"] is False
    assert any("r89_cut_1_hook_forbidden" in x for x in res_c1["gates"]["DQ6_zero_clip_reuse"]["r89_issues"])

    # 3. Nonzero audio stream on rendered R89 clip fails DQ6
    c2_path = proj_ok / "03_visuals/archival_video_clips/clip_02.mp4"
    _write_motion_mp4(c2_path, width=1080, height=1920, duration_sec=2.5, add_audio=True)
    mf_ok = json.loads((proj_ok / ARCHIVAL_VIDEOS_MANIFEST_REL).read_text(encoding="utf-8"))
    mf_ok["videos"][0]["rendered_clip_sha256"] = hashlib.sha256(c2_path.read_bytes()).hexdigest()
    (proj_ok / ARCHIVAL_VIDEOS_MANIFEST_REL).write_text(json.dumps(mf_ok, indent=2), encoding="utf-8")
    res_aud = verify_final_mp4_against_contract(proj_ok)
    assert res_aud["gates"]["DQ6_zero_clip_reuse"]["passed"] is False
    assert any("r89_nonzero_audio_streams" in x for x in res_aud["gates"]["DQ6_zero_clip_reuse"]["r89_issues"])

    # 4. Frozen R89 clip fails DQ7
    proj_frz, _mp4_frz = _setup_r89_dq_episode(tmp_path, "r89_dq_frozen", mode1_frozen=True)
    res_frz = verify_final_mp4_against_contract(proj_frz)
    assert res_frz["gates"]["DQ7_continuous_motion_no_freeze"]["passed"] is False
    assert 2 in res_frz["gates"]["DQ7_continuous_motion_no_freeze"]["freeze_cuts"]

    # 5. DQ8 YuNet check inspects viewport and MASKS OUT A01 porcelain badge corner
    def _marker_detector(bgr: np.ndarray, *, score_threshold: float = 0.42) -> list[list[float]]:
        mask = (bgr[:, :, 2] > 200) & (bgr[:, :, 1] < 60) & (bgr[:, :, 0] < 60)
        if int(np.sum(mask)) > 150:
            return [[20.0, 20.0, 60.0, 60.0, max(score_threshold + 0.35, 0.88)]]
        return []

    monkeypatch.setattr("pipeline.source_reenactment.detect_human_faces_yunet", _marker_detector)
    proj_badge, _mp4_badge = _setup_r89_dq_episode(tmp_path, "r89_dq_badge_masked", face_in_badge_only=True)
    res_badge = verify_final_mp4_against_contract(proj_badge)
    assert res_badge["gates"]["DQ8_zero_uncanny_skin_gore"]["passed"] is True, res_badge["gates"]["DQ8_zero_uncanny_skin_gore"]

    proj_face, _mp4_face = _setup_r89_dq_episode(tmp_path, "r89_dq_face_vf", face_in_vf=True)
    res_face = verify_final_mp4_against_contract(proj_face)
    assert res_face["gates"]["DQ8_zero_uncanny_skin_gore"]["passed"] is False
    assert 3 in res_face["gates"]["DQ8_zero_uncanny_skin_gore"]["yunet_human_face_cuts"]


def test_r89_publish_cc_by_video_credit_contract(tmp_path: Path) -> None:
    mf_path = tmp_path / ARCHIVAL_VIDEOS_MANIFEST_REL
    mf_path.parent.mkdir(parents=True, exist_ok=True)
    mf_path.write_text(
        json.dumps(
            {
                "videos": [
                    _plos_ccby_entry(clip_number=2),
                    _federal_intramural_entry(clip_number=3),
                ]
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    credits = extract_cc_by_archival_video_credits(tmp_path)
    assert len(credits) == 1
    assert credits[0].startswith("Video credit: Adapted from Chen et al., PLOS Biology (2024), Supplementary Movie 1, CC BY 4.0")
    assert "— cropped & muted (https://journals.plos.org/plosbiology/article?id=10.1371/journal.pbio.3002001)." in credits[0]
    assert "nimh.nih.gov" not in credits[0]

    combined_credits = [
        "Image credit: Wellcome Collection, CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/).",
        *credits,
    ]
    script_doc = {
        "viewer_description": (
            "In 2024, researchers filmed free-moving lab subjects inside a split visual testing booth while "
            "each hemisphere processed a separate cue. The footage showed rapid eye redirection milliseconds "
            "before the behavioral choice was logged.\n\n"
            "Simultaneous brain recordings revealed cross-hemispheric coordination surging along intact "
            "white-matter tracts. This synchronization kept motor responses unified despite divided visual input.\n\n"
            "Research: Chen et al., PLOS Biology (2024)."
        )
    }
    desc = format_v8_viewer_story_description(script_doc, archival_credits=combined_credits)
    val_ok = validate_v8_viewer_description(desc)
    assert val_ok == [], val_ok
    assert "Image credit: Wellcome Collection" in desc
    assert "Video credit: Adapted from Chen et al., PLOS Biology (2024)" in desc

    # Core story body must STILL forbid em-dashes and DOIs
    bad_em = desc.replace("split visual testing booth", "split — visual testing booth")
    val_bad_em = validate_v8_viewer_description(bad_em)
    assert len(val_bad_em) > 0
    assert any("em" in x.lower() or "—" in x for x in val_bad_em)

    bad_doi = desc.replace("divided visual input.", "divided visual input (doi:10.1371/journal.pbio.3002001).")
    val_bad_doi = validate_v8_viewer_description(bad_doi)
    assert len(val_bad_doi) > 0
    assert any("doi" in x.lower() for x in val_bad_doi)
