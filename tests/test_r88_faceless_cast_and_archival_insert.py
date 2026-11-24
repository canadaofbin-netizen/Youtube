"""
Track 2 Tests (`R88-A`): Legal Archival Photo Insert Pipeline, License Classifier Fix,
Assembler/DQ8 Integration & R68-D CC-BY Description Credits.

Covers:
  1. `classify_media_license` & `validate_real_world_refs_manifest` (`"cc-by-nc"` / `"cc-by-nd"` substring bypass fix).
  2. `archival_insert_builder`: YuNet `0-Face` privacy gate, pre-1931 PD portrait exemption, duration/count/share
     caps (`<= 2` inserts, `2.0..4.0s`, `<= 8%` episode share), `cc-by-sa` copyleft rejection, Flow upload=0 lock,
     `1080x1920 @ 30fps` Ken Burns (`1.00x -> 1.08x`) rendering over `#080C16` museum matte, `CC-BY` visual pill,
     and `load_verified_archival_insert_clip_map` byte-for-byte SHA-256 tamper verification.
  3. `diorama_assembler._resolve_diorama_clip_files` & `dynamic_episode_qa.py` (`DQ8`) integration:
     verified archival skin-hue apparatus cut passes and is recorded in `verified_archival_insert_cuts`, while AI
     skin-leak cut AND tampered/unexempt archival face cut both fail `DQ8`.
  4. `publish.py`: `extract_cc_by_archival_credits`, `format_v8_viewer_story_description`,
     `validate_v8_viewer_description`, and `PublishStage.run` (`Image credit:` line only for `direct_insert_cc_by`).
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import wave
from pathlib import Path

import av
import cv2
import numpy as np
from PIL import Image
import pytest

from pipeline.archival_insert import (
    ARCHIVAL_CLIPS_DIRNAME,
    ARCHIVAL_MANIFEST_REL,
    R88A_CLIP_DURATION_RANGE,
    R88A_FPS,
    R88A_MAX_EPISODE_DURATION_SHARE,
    R88A_MAX_INSERTS_PER_EPISODE,
    load_verified_archival_insert_clip_map,
    render_archival_insert_clips,
    validate_archival_inserts_manifest,
)
from pipeline.canonical_assets import (
    CanonicalAssetError,
    resolve_canonical_approved_slot,
    select_canonical_character_slot,
)
from pipeline.config import (
    PRE_R88_FROZEN_V8_PROJECTS,
    R88_RETIRED_CARTOON_CAST_SLOTS,
    WORKSPACE_ROOT,
)
from pipeline.assembler import _resolve_diorama_clip_files
from pipeline.episode_qa import verify_final_mp4_against_contract
from pipeline.flow_worker import compute_porcelain_flesh_leak_ratio
from pipeline.posthoc_qa import (
    detect_circular_lens_border_intrusion,
    evaluate_cut_temporal_smoothness,
)
from pipeline.prompt_gate import validate_r88_faceless_cast_contract
from pipeline.publish import (
    PublishStage,
    extract_cc_by_archival_credits,
    format_v8_viewer_story_description,
    validate_v8_viewer_description,
)
from pipeline.real_world_refs import (
    classify_media_license,
    validate_real_world_refs_manifest,
)
from pipeline.storage import ProjectStorage


def _make_clean_apparatus_photo(path: Path, *, warm_wood_tone: bool = True, seed: int = 11) -> str:
    """Writes a textured non-face laboratory apparatus photo (warm skin-hue wood/brass when requested)."""
    rng = np.random.default_rng(seed)
    base_bgr = (142, 168, 212) if warm_wood_tone else (175, 165, 150)
    arr = np.zeros((720, 960, 3), dtype=np.float32)
    arr[:, :] = base_bgr
    arr += rng.normal(0.0, 22.0, size=arr.shape)
    img = np.clip(arr, 0, 255).astype(np.uint8)
    # Draw crisp laboratory dial/apparatus geometry (zero facial symmetry)
    cv2.rectangle(img, (110, 140), (850, 610), (70, 95, 130), 8)
    cv2.rectangle(img, (180, 230), (460, 520), (55, 70, 95), -1)
    cv2.line(img, (210, 490), (430, 260), (220, 230, 240), 5)
    cv2.rectangle(img, (540, 260), (780, 480), (92, 118, 160), -1)
    cv2.line(img, (540, 370), (780, 370), (40, 55, 80), 4)
    path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(path), img)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _make_human_face_photo(path: Path, *, seed: int = 22) -> str:
    """Writes a deterministic photo with realistic YuNet-detectable human facial features & flesh tones."""
    rng = np.random.default_rng(seed)
    arr = np.zeros((720, 720, 3), dtype=np.float32)
    arr[:, :] = (205, 210, 218)
    arr += rng.normal(0.0, 4.0, size=arr.shape)
    frm = np.clip(arr, 0, 255).astype(np.uint8)
    cx, cy = 360, 360
    cv2.ellipse(frm, (cx, cy), (105, 138), 0, 0, 360, (140, 175, 220), -1)
    cv2.ellipse(frm, (cx, cy - 115), (108, 52), 0, 180, 360, (42, 46, 52), -1)
    cv2.ellipse(frm, (cx - 38, cy - 18), (24, 15), 0, 0, 360, (110, 128, 178), -1)
    cv2.ellipse(frm, (cx + 38, cy - 18), (24, 15), 0, 0, 360, (110, 128, 178), -1)
    cv2.ellipse(frm, (cx - 38, cy - 38), (24, 7), 0, 180, 360, (45, 45, 48), 4)
    cv2.ellipse(frm, (cx + 38, cy - 38), (24, 7), 0, 180, 360, (45, 45, 48), 4)
    cv2.circle(frm, (cx - 38, cy - 18), 11, (245, 245, 245), -1)
    cv2.circle(frm, (cx + 38, cy - 18), 11, (245, 245, 245), -1)
    cv2.circle(frm, (cx - 38, cy - 18), 6, (30, 32, 36), -1)
    cv2.circle(frm, (cx + 38, cy - 18), 6, (30, 32, 36), -1)
    cv2.line(frm, (cx, cy - 18), (cx - 5, cy + 28), (112, 138, 180), 4)
    cv2.circle(frm, (cx - 9, cy + 32), 4, (85, 102, 135), -1)
    cv2.circle(frm, (cx + 9, cy + 32), 4, (85, 102, 135), -1)
    cv2.ellipse(frm, (cx, cy + 68), (28, 10), 0, 0, 180, (95, 105, 155), 5)
    path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(path), frm)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_solid_mp4(path: Path, frame_bgr: np.ndarray, *, fps: int = 30, n_frames: int = 90) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    container = av.open(str(path), mode="w", format="mp4")
    try:
        stream = container.add_stream("libx264", rate=fps)
        stream.width = frame_bgr.shape[1]
        stream.height = frame_bgr.shape[0]
        stream.pix_fmt = "yuv420p"
        stream.options = {"crf": "20", "preset": "ultrafast"}
        for fi in range(n_frames):
            f = frame_bgr.copy()
            # Subtle motion bar so non-DQ7 freeze check stays realistic when needed
            x_bar = (fi * 6) % max(20, frame_bgr.shape[1] - 40)
            cv2.rectangle(f, (x_bar, 1480), (x_bar + 36, 1520), (190, 210, 230), -1)
            vf = av.VideoFrame.from_ndarray(f, format="bgr24")
            for pkt in stream.encode(vf):
                container.mux(pkt)
        for pkt in stream.encode():
            container.mux(pkt)
    finally:
        container.close()


def _write_stereo_wav(path: Path, *, duration_sec: float = 9.0, sr: int = 44100) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    n_samples = int(round(duration_sec * sr))
    rng = np.random.default_rng(123)
    left = (rng.normal(0.0, 0.08, n_samples) * 32767.0).astype(np.int16)
    right = (rng.normal(0.0, 0.08, n_samples) * 32767.0).astype(np.int16)
    stereo = np.stack([left, right], axis=1)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(stereo.tobytes())


def test_classify_media_license_and_real_world_refs_nc_nd_fix(tmp_path: Path) -> None:
    for lic in (
        "",
        "   ",
        "cc-by-nc",
        "CC BY-NC 4.0",
        "cc_by_nc",
        "cc-by-nd",
        "CC BY-ND 4.0",
        "CC-BY-NC-SA 4.0",
        "NonCommercial",
        "No-Derivs",
        "No Derivatives",
        "All Rights Reserved",
        "Fair Use",
        "Copyrighted",
        "Proprietary",
        "Editorial Only",
        "Getty Images",
        "Shutterstock",
        "Alamy",
    ):
        assert classify_media_license(lic) == "banned", f"Expected banned for {lic!r}"

    for lic in (
        "cc-by-sa",
        "CC BY-SA 4.0",
        "cc_by_sa",
        "Attribution-ShareAlike 3.0",
        "GFDL",
        "wikimedia_open",
        "open_license",
    ):
        assert classify_media_license(lic) == "flow_guide_only_cc_by_sa", f"Expected SA tier for {lic!r}"

    for lic in (
        "Public Domain",
        "CC0",
        "cc-0",
        "PDM 1.0",
        "pd-old-100",
        "USGov",
        "NIH",
        "NIMH",
        "CDC",
        "NASA",
        "pre-1931",
        "pre1931",
    ):
        assert classify_media_license(lic) == "direct_insert_pd_cc0", f"Expected PD/CC0 tier for {lic!r}"

    for lic in (
        "CC BY 4.0",
        "cc-by-4.0",
        "CC-BY 3.0",
        "CC BY 2.5",
        "CC BY 2.0",
        "cc-by",
        "Creative Commons Attribution 4.0 International",
    ):
        assert classify_media_license(lic) == "direct_insert_cc_by", f"Expected CC-BY tier for {lic!r}"

    proj = tmp_path / "v8_r85_license_fix"
    (proj / "03_visuals").mkdir(parents=True)
    mf = proj / "03_visuals" / "real_world_refs_manifest.json"

    # Must reject substring bypasses like "cc-by-nc" and "cc-by-nd"
    for bad_lic in ("cc-by-nc", "cc-by-nd"):
        mf.write_text(
            json.dumps(
                {
                    "r85_mode": True,
                    "targets": [
                        {
                            "target_id": "ucl_main_quad",
                            "commons_title": "File:UCL Portico London.jpg",
                            "license": bad_lic,
                            "source_url": "https://commons.wikimedia.org/wiki/File:UCL_Portico_London.jpg",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        res = validate_real_world_refs_manifest(proj)
        assert res["passed"] is False
        assert any("[real_world_ref_unlicensed]" in issue for issue in res["issues"])

    # Must continue passing all open R72-R/R85 licenses
    for ok_lic in ("public domain", "cc0", "cc-by", "cc-by-sa", "nih", "wikimedia_open", "open_license"):
        mf.write_text(
            json.dumps(
                {
                    "r85_mode": True,
                    "targets": [
                        {
                            "target_id": "ucl_main_quad",
                            "commons_title": "File:UCL Portico London.jpg",
                            "license": ok_lic,
                            "source_url": "https://commons.wikimedia.org/wiki/File:UCL_Portico_London.jpg",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        res = validate_real_world_refs_manifest(proj)
        assert res["passed"] is True, f"Expected pass for {ok_lic!r}, got {res['issues']}"


def test_archival_insert_validation_privacy_and_ken_burns_render(tmp_path: Path) -> None:
    assert R88A_MAX_INSERTS_PER_EPISODE == 2
    assert R88A_CLIP_DURATION_RANGE == (2.0, 4.0)
    assert R88A_MAX_EPISODE_DURATION_SHARE == 0.08
    assert R88A_FPS == 30

    proj = tmp_path / "v8_r88a_unit"
    raw_dir = proj / "03_visuals" / "archival_sources"
    apparatus_img = raw_dir / "apparatus.png"
    face_img = raw_dir / "living_face.png"
    app_sha = _make_clean_apparatus_photo(apparatus_img, warm_wood_tone=True)
    face_sha = _make_human_face_photo(face_img)

    def _write_manifest(entries: list[dict]) -> Path:
        mf_p = proj / ARCHIVAL_MANIFEST_REL
        mf_p.parent.mkdir(parents=True, exist_ok=True)
        mf_p.write_text(json.dumps({"inserts": entries}, indent=2), encoding="utf-8")
        return mf_p

    # 1. Living face photo rejected by YuNet 0-Face Gate
    _write_manifest(
        [
            {
                "clip_number": 3,
                "duration_sec": 3.0,
                "license": "Public Domain",
                "source_url": "https://commons.wikimedia.org/wiki/File:Lab_Portrait.jpg",
                "image_path": "03_visuals/archival_sources/living_face.png",
                "image_sha256": face_sha,
                "flow_upload_count": 0,
            }
        ]
    )
    res_face = validate_archival_inserts_manifest(proj, episode_duration_sec=75.0)
    assert res_face["passed"] is False
    assert any("[r88a_privacy_human_face_detected]" in i for i in res_face["issues"])

    # 2. Pre-1931 PD deceased portrait allowed when explicitly opted in + PD/CC0 + year < 1931
    _write_manifest(
        [
            {
                "clip_number": 3,
                "duration_sec": 3.0,
                "license": "Public Domain",
                "source_url": "https://commons.wikimedia.org/wiki/File:Pre1931_Portrait.jpg",
                "image_path": "03_visuals/archival_sources/living_face.png",
                "image_sha256": face_sha,
                "allow_deceased_pre1931_portrait": True,
                "publication_year": 1924,
                "flow_upload_count": 0,
            }
        ]
    )
    res_pre1931 = validate_archival_inserts_manifest(proj, episode_duration_sec=75.0)
    assert res_pre1931["passed"] is True, res_pre1931["issues"]

    # 3. Rejects > 8% episode share (e.g. 2 * 3.5s = 7.0s > 6.0s of 75s)
    _write_manifest(
        [
            {
                "clip_number": 3,
                "duration_sec": 3.5,
                "license": "Public Domain",
                "source_url": "https://commons.wikimedia.org/wiki/File:App1.jpg",
                "image_path": "03_visuals/archival_sources/apparatus.png",
                "image_sha256": app_sha,
                "flow_upload_count": 0,
            },
            {
                "clip_number": 4,
                "duration_sec": 3.5,
                "license": "Public Domain",
                "source_url": "https://commons.wikimedia.org/wiki/File:App2.jpg",
                "image_path": "03_visuals/archival_sources/apparatus.png",
                "image_sha256": app_sha,
                "flow_upload_count": 0,
            },
        ]
    )
    res_share = validate_archival_inserts_manifest(proj, episode_duration_sec=75.0)
    assert res_share["passed"] is False
    assert any("[r88a_episode_share_exceeded]" in i for i in res_share["issues"])

    # 4. Rejects > 2 inserts, out-of-range duration, cc-by-sa, and flow_upload_count > 0
    _write_manifest(
        [
            {
                "clip_number": 1,
                "duration_sec": 2.0,
                "license": "CC BY-SA 4.0",
                "source_url": "https://commons.wikimedia.org/wiki/File:SA.jpg",
                "image_path": "03_visuals/archival_sources/apparatus.png",
                "image_sha256": app_sha,
                "flow_upload_count": 1,
            },
            {
                "clip_number": 2,
                "duration_sec": 1.5,
                "license": "CC BY 4.0",
                "source_url": "https://commons.wikimedia.org/wiki/File:B.jpg",
                "image_path": "03_visuals/archival_sources/apparatus.png",
                "flow_upload_count": 0,
            },
            {
                "clip_number": 3,
                "duration_sec": 2.0,
                "license": "Public Domain",
                "source_url": "https://commons.wikimedia.org/wiki/File:C.jpg",
                "image_path": "03_visuals/archival_sources/apparatus.png",
                "flow_upload_count": 0,
            },
        ]
    )
    res_bad = validate_archival_inserts_manifest(proj, episode_duration_sec=100.0)
    assert res_bad["passed"] is False
    joined_err = "\n".join(res_bad["issues"])
    assert "[r88a_too_many_inserts]" in joined_err
    assert "[r88a_copyleft_sharealike_forbidden]" in joined_err
    assert "[r88a_flow_upload_forbidden]" in joined_err
    assert "[r88a_duration_out_of_range]" in joined_err
    assert "[r88a_cc_by_missing_author]" in joined_err

    # 5. Valid PD + CC-BY pair -> render 1080x1920 @ 30fps Ken Burns clips + CC-BY credit pill
    _write_manifest(
        [
            {
                "clip_number": 2,
                "duration_sec": 2.5,
                "license": "Public Domain",
                "source_url": "https://commons.wikimedia.org/wiki/File:Old_Apparatus.jpg",
                "image_path": "03_visuals/archival_sources/apparatus.png",
                "image_sha256": app_sha,
                "flow_upload_count": 0,
            },
            {
                "clip_number": 4,
                "duration_sec": 3.0,
                "license": "CC BY 4.0",
                "author": "Wellcome Collection",
                "license_uri": "https://creativecommons.org/licenses/by/4.0/",
                "source_url": "https://commons.wikimedia.org/wiki/File:Lab_Apparatus_CCBY.jpg",
                "image_path": "03_visuals/archival_sources/apparatus.png",
                "image_sha256": app_sha,
                "flow_upload_count": 0,
            },
        ]
    )
    render_res = render_archival_insert_clips(proj, episode_duration_sec=75.0)
    assert render_res["passed"] is True
    assert len(render_res["rendered_clips"]) == 2

    mp4_pd = proj / "03_visuals" / ARCHIVAL_CLIPS_DIRNAME / "clip_02.mp4"
    mp4_ccby = proj / "03_visuals" / ARCHIVAL_CLIPS_DIRNAME / "clip_04.mp4"
    assert mp4_pd.is_file() and mp4_ccby.is_file()

    # Check 1080x1920 @ 30fps + real Ken Burns inter-frame motion + zero circular lens border intrusion
    for clip_p, exp_dur in ((mp4_pd, 2.5), (mp4_ccby, 3.0)):
        cap = cv2.VideoCapture(str(clip_p))
        assert cap.isOpened()
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = float(cap.get(cv2.CAP_PROP_FPS))
        fc = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        ok0, f0 = cap.read()
        cap.set(cv2.CAP_PROP_POS_FRAMES, fc - 1)
        ok1, f_last = cap.read()
        cap.release()
        assert (w, h) == (1080, 1920)
        assert abs(fps - 30.0) <= 0.1
        assert fc == int(round(exp_dur * 30))
        assert ok0 and ok1 and f0 is not None and f_last is not None
        assert float(np.mean(np.abs(f0.astype(np.float32) - f_last.astype(np.float32)))) > 0.5
        assert detect_circular_lens_border_intrusion([f0, f_last])["detected"] is False
        sm = evaluate_cut_temporal_smoothness(
            clip_p,
            [{"cut_index": 1, "out_start_sec": 0.0, "out_end_sec": exp_dur, "camera_move": "gentle_push_in"}],
        )
        assert sm[1]["passed"] is True
        assert sm[1]["frozen_frames"] == 0

    # Verify CC-BY pill is burned ONLY in y=1140..1210 safe band (subtitle & top bands remain clean #080C16 matte)
    cap_a = cv2.VideoCapture(str(mp4_pd))
    cap_b = cv2.VideoCapture(str(mp4_ccby))
    _, f_pd0 = cap_a.read()
    _, f_cc0 = cap_b.read()
    cap_a.release()
    cap_b.release()
    matte = np.array([22, 12, 8], dtype=np.float32)
    pd_pill_band_err = float(np.max(np.abs(f_pd0[1140:1210, 60:920].astype(np.float32) - matte)))
    cc_pill_band_diff = float(np.mean(np.abs(f_cc0[1140:1210, 60:920].astype(np.float32) - matte)))
    cc_sub_band_err = float(np.max(np.abs(f_cc0[1240:1450, :].astype(np.float32) - matte)))
    cc_top_band_err = float(np.max(np.abs(f_cc0[120:290, :].astype(np.float32) - matte)))
    assert pd_pill_band_err <= 3.0
    assert cc_pill_band_diff > 1.5
    assert cc_sub_band_err <= 3.0
    assert cc_top_band_err <= 3.0

    # Verified clip map enforces byte-for-byte SHA-256 & license check
    vmap = load_verified_archival_insert_clip_map(proj / "03_visuals")
    assert set(vmap.keys()) == {2, 4}

    # Tamper clip_04.mp4 -> excluded from verified map
    mp4_ccby.write_bytes(mp4_ccby.read_bytes() + b"\x00")
    vmap_tampered = load_verified_archival_insert_clip_map(proj / "03_visuals")
    assert set(vmap_tampered.keys()) == {2}


def test_assembler_clip_resolution_and_dq8_archival_vs_ai_skin_gates(tmp_path: Path) -> None:
    proj = tmp_path / "v8_r88a_dq8_e2e"
    for d in ("02_script", "03_visuals/flow_native_clips", "03_visuals/archival_sources", "04_audio", "05_assembly"):
        (proj / d).mkdir(parents=True, exist_ok=True)

    # Confirm _resolve_diorama_clip_files picks up verified archival clip over unpadded flow clip
    _write_solid_mp4(proj / "03_visuals/flow_native_clips/clip_1.mp4", np.full((1920, 1080, 3), (185, 192, 198), dtype=np.uint8))
    _write_solid_mp4(proj / "03_visuals/flow_native_clips/clip_2.mp4", np.full((1920, 1080, 3), (185, 192, 198), dtype=np.uint8))
    _write_solid_mp4(proj / "03_visuals/flow_native_clips/clip_3.mp4", np.full((1920, 1080, 3), (40, 80, 120), dtype=np.uint8))

    app_img = proj / "03_visuals/archival_sources/warm_wood_apparatus.png"
    app_sha = _make_clean_apparatus_photo(app_img, warm_wood_tone=True)
    # Confirm raw apparatus photo actually has warm skin-hue tones that would fail AI porcelain skin check if unexempted
    raw_app_bgr = cv2.imread(str(app_img))
    assert raw_app_bgr is not None and compute_porcelain_flesh_leak_ratio(raw_app_bgr) > 0.10

    mf_path = proj / ARCHIVAL_MANIFEST_REL
    mf_path.write_text(
        json.dumps(
            {
                "inserts": [
                    {
                        "clip_number": 2,
                        "duration_sec": 2.4,
                        "license": "CC BY 4.0",
                        "author": "Science Museum",
                        "license_uri": "https://creativecommons.org/licenses/by/4.0/",
                        "source_url": "https://commons.wikimedia.org/wiki/File:Wood_Rig.jpg",
                        "image_path": "03_visuals/archival_sources/warm_wood_apparatus.png",
                        "image_sha256": app_sha,
                        "flow_upload_count": 0,
                    }
                ]
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    render_archival_insert_clips(proj, episode_duration_sec=35.0)
    resolved_clips = _resolve_diorama_clip_files(proj / "03_visuals")
    assert [p.name for p in resolved_clips] == ["clip_1.mp4", "clip_02.mp4", "clip_3.mp4"]
    assert resolved_clips[1].parent.name == ARCHIVAL_CLIPS_DIRNAME

    # Build minimal non-synth v8 episode artifacts for real DQ8 verification
    sentences = [
        "Scientists built a quiet wooden apparatus in the laboratory.",
        "This archival rig measured reactions without a brain scan.",
        "Deep brain wiring fired milliseconds later.",
    ] + [f"Sentence {i} explains another step in the laboratory circuit." for i in range(4, 15)]
    script_doc = {
        "schema": 8,
        "style_profile": "expressive_25d_v8",
        "format_profile": "shorts_expressive_v8",
        "project_id": proj.name,
        "allow_legacy_v8_clip_count": True,
        "sentences": sentences,
    }
    vp_clips = [
        {"clip_number": 1, "sentence_index": 1, "grammar": "expressive_vinyl_world", "location_id": "lab_room", "camera_move": "gentle_push_in", "scene": "Bald cream-white vinyl researcher adjusts a dial at the lab desk."},
        {"clip_number": 2, "sentence_index": 2, "grammar": "expressive_vinyl_world", "location_id": "archive_rig", "camera_move": "gentle_push_in", "scene": "Archival wooden laboratory apparatus on a dark museum backdrop."},
        {"clip_number": 3, "sentence_index": 3, "grammar": "expressive_xray_brain", "location_id": "brain_mode2", "camera_move": "clean_pullback_reveal", "brain_clip": True, "scene": "Ep #31 matte silver-white 3D cutaway brain highlights the cortex."},
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
        for i in range(4, 15)
    ]
    vp_doc = {
        "schema": 8,
        "style_profile": "expressive_25d_v8",
        "format_profile": "shorts_expressive_v8",
        "allow_legacy_v8_clip_count": True,
        "clips": vp_clips,
    }
    edl_doc = {
        "schema": 8,
        "fps": 30,
        "total_duration_sec": 7.2,
        "zero_clip_reuse": True,
        "max_clip_reuse": 1,
        "allow_legacy_v8_clip_count": True,
        "cuts": [
            {"cut_index": 1, "clip_index": 1, "clip_file": "clip_1.mp4", "sentence_index": 1, "end_sentence_index": 1, "out_start_sec": 0.0, "out_end_sec": 2.4, "duration_sec": 2.4, "src_start_sec": 0.0, "main_speed": 1.0, "camera_move": "gentle_push_in", "grammar": "expressive_vinyl_world", "location_id": "lab_room"},
            {"cut_index": 2, "clip_index": 2, "clip_file": "clip_02.mp4", "sentence_index": 2, "end_sentence_index": 2, "out_start_sec": 2.4, "out_end_sec": 4.8, "duration_sec": 2.4, "src_start_sec": 0.0, "main_speed": 1.0, "camera_move": "gentle_push_in", "grammar": "expressive_vinyl_world", "location_id": "archive_rig"},
            {"cut_index": 3, "clip_index": 3, "clip_file": "clip_3.mp4", "sentence_index": 3, "end_sentence_index": 3, "out_start_sec": 4.8, "out_end_sec": 7.2, "duration_sec": 2.4, "src_start_sec": 0.0, "main_speed": 1.0, "camera_move": "clean_pullback_reveal", "grammar": "expressive_xray_brain", "location_id": "brain_mode2"},
        ],
    }
    (proj / "02_script/script.json").write_text(json.dumps(script_doc, indent=2), encoding="utf-8")
    (proj / "03_visuals/visual_plan.json").write_text(json.dumps(vp_doc, indent=2), encoding="utf-8")
    (proj / "05_assembly/edit_decision_list.json").write_text(json.dumps(edl_doc, indent=2), encoding="utf-8")
    (proj / "04_audio/subtitles.ass").write_text("[Script Info]\n[V4+ Styles]\nStyle: Default,AAB Condensed Black,82,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,5.5,1.5,2,80,165,510,1\n[Events]\n", encoding="utf-8")
    _write_stereo_wav(proj / "04_audio/audio_master.wav", duration_sec=7.2)
    (proj / "04_audio/voice_report.json").write_text(
        json.dumps({"engine": "elevenlabs_v4", "active_speech_ratio": 0.92, "true_rms_voiced_ratio": 0.92, "speech_end_sec": 7.0}),
        encoding="utf-8",
    )
    # Ensure audio_master.wav mtime >= script.json mtime
    os.utime(proj / "04_audio/audio_master.wav", None)

    def _assemble_from_clips(clip_paths: list[Path], out_mp4: Path) -> None:
        container = av.open(str(out_mp4), mode="w", format="mp4")
        try:
            stream = container.add_stream("libx264", rate=30)
            stream.width = 1080
            stream.height = 1920
            stream.pix_fmt = "yuv420p"
            stream.options = {"crf": "20", "preset": "ultrafast"}
            for cp in clip_paths:
                cap_c = cv2.VideoCapture(str(cp))
                for _ in range(72):
                    ok_f, fr_f = cap_c.read()
                    if not ok_f or fr_f is None:
                        break
                    vf = av.VideoFrame.from_ndarray(fr_f, format="bgr24")
                    for pkt in stream.encode(vf):
                        container.mux(pkt)
                cap_c.release()
            for pkt in stream.encode():
                container.mux(pkt)
        finally:
            container.close()

    final_mp4 = proj / "05_assembly/final_shorts_1080x1920.mp4"
    _assemble_from_clips(resolved_clips, final_mp4)

    # Case A: Clean AI cut 1 + verified archival apparatus cut 2 + brain cut 3 -> DQ8 passes!
    qa_pass = verify_final_mp4_against_contract(proj, run_asr_sync=False, save_report=False)
    dq8_pass = qa_pass["gates"]["DQ8_zero_uncanny_skin_gore"]
    assert dq8_pass["passed"] is True, dq8_pass
    assert 2 in dq8_pass["verified_archival_insert_cuts"]
    assert 2 not in dq8_pass["skin_leak_cuts"]

    # Case B: Non-archival AI cut 1 has uncanny human face -> DQ8 STILL rejects AI skin/face leak!
    face_src = tmp_path / "face_tile.png"
    _make_human_face_photo(face_src)
    face_tile = cv2.imread(str(face_src))
    ai_face_frame = np.full((1920, 1080, 3), (185, 192, 198), dtype=np.uint8)
    ai_face_frame[300:1020, 180:900] = face_tile
    _write_solid_mp4(proj / "03_visuals/flow_native_clips/clip_1.mp4", ai_face_frame, n_frames=72)
    _assemble_from_clips(resolved_clips, final_mp4)
    qa_ai_fail = verify_final_mp4_against_contract(proj, run_asr_sync=False, save_report=False)
    dq8_ai_fail = qa_ai_fail["gates"]["DQ8_zero_uncanny_skin_gore"]
    assert dq8_ai_fail["passed"] is False
    assert 1 in dq8_ai_fail["yunet_human_face_cuts"]
    assert 1 in dq8_ai_fail["skin_leak_cuts"]

    # Restore clean AI clip 1, then Case C: tampered/face archival clip on non-exempt cut 2 -> DQ8 rejects!
    _write_solid_mp4(proj / "03_visuals/flow_native_clips/clip_1.mp4", np.full((1920, 1080, 3), (185, 192, 198), dtype=np.uint8), n_frames=72)
    arch_mp4 = proj / "03_visuals" / ARCHIVAL_CLIPS_DIRNAME / "clip_02.mp4"
    _write_solid_mp4(arch_mp4, ai_face_frame, n_frames=72)
    tampered_sha = hashlib.sha256(arch_mp4.read_bytes()).hexdigest()
    mf_doc = json.loads(mf_path.read_text(encoding="utf-8"))
    mf_doc["inserts"][0]["rendered_clip_sha256"] = tampered_sha
    mf_path.write_text(json.dumps(mf_doc, indent=2), encoding="utf-8")
    _assemble_from_clips(resolved_clips, final_mp4)
    qa_arch_face_fail = verify_final_mp4_against_contract(proj, run_asr_sync=False, save_report=False)
    dq8_arch_face = qa_arch_face_fail["gates"]["DQ8_zero_uncanny_skin_gore"]
    assert dq8_arch_face["passed"] is False
    assert 2 in dq8_arch_face["yunet_human_face_cuts"]
    assert 2 in dq8_arch_face["skin_leak_cuts"]


def test_publish_cc_by_archival_credits_and_v8_validation(tmp_path: Path) -> None:
    proj = tmp_path / "v8_r88a_publish"
    storage = ProjectStorage(proj.name, projects_dir=tmp_path)
    for d in ("02_script", "03_visuals", "05_assembly", "06_publish"):
        (proj / d).mkdir(parents=True, exist_ok=True)

    # PD + CC-BY manifest: ONLY CC-BY produces an Image credit line
    mf_path = proj / ARCHIVAL_MANIFEST_REL
    mf_path.write_text(
        json.dumps(
            {
                "inserts": [
                    {
                        "clip_number": 2,
                        "duration_sec": 2.5,
                        "license": "Public Domain",
                        "source_url": "https://commons.wikimedia.org/wiki/File:Old.jpg",
                    },
                    {
                        "clip_number": 4,
                        "duration_sec": 3.0,
                        "license": "CC BY 4.0",
                        "author": "Wellcome Collection",
                        "license_uri": "https://creativecommons.org/licenses/by/4.0/",
                        "source_url": "https://commons.wikimedia.org/wiki/File:App.jpg",
                    },
                ]
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    credits = extract_cc_by_archival_credits(proj)
    assert credits == ["Image credit: Wellcome Collection, CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/)."]

    # Near-ceiling (~128 words) R68-D base copy must still validate when optional Image credit line is appended
    base_vd = (
        "Patient S.M. lived for decades with rare damage to both sides of her amygdala, "
        "the part of the brain usually linked to fear. Doctors at the University of Iowa "
        "took her to exotic pet stores, handed her live snakes, showed her horror movies, "
        "and walked her through a haunted house. She stayed curious the whole time and "
        "never once felt scared.\n\n"
        "That changed in a breathing lab. One harmless breath of 35% carbon dioxide gave "
        "her a full panic attack in seconds, the first fear she had felt since childhood. "
        "Outside threats go through the amygdala, while suffocation alarms sit much deeper "
        "in the brainstem, which explains why sudden panic can hit your body even when the "
        "room around you looks completely safe.\n\n"
        "Research: Feinstein et al., University of Iowa (2011, 2013)."
    )
    desc_with_credit = format_v8_viewer_story_description(
        {"viewer_description": base_vd},
        archival_credits=credits,
    )
    assert desc_with_credit.endswith(credits[0])
    assert validate_v8_viewer_description(desc_with_credit + "\n\n#shorts", project_id=proj.name) == []

    # Invalid credit line inside story or malformed license must fail
    assert any(
        "[r88a_image_credit]" in err
        for err in validate_v8_viewer_description(
            base_vd + "\nImage credit: Bad Author, CC BY-NC 4.0 (https://example.com)."
        )
    )

    # End-to-end PublishStage.run picks up archival_inserts_manifest.json automatically
    script_doc = {
        "schema": 8,
        "style_profile": "expressive_25d_v8",
        "format_profile": "shorts_expressive_v8",
        "project_id": proj.name,
        "title": "Why Sudden Panic Happens Safely",
        "doi": "10.1038/nn.3323",
        "viewer_description": base_vd,
        "debate_question": "Have you ever felt sudden panic in a calm room?",
        "sentences": ["Doctors tested a patient who never felt fear.", "Carbon dioxide triggered panic in seconds."],
    }
    storage.save_json("02_script", "script.json", script_doc)
    storage.save_json("03_visuals", "visual_plan.json", {"schema": 8, "style_profile": "expressive_25d_v8", "format_profile": "shorts_expressive_v8"})
    storage.save_json("05_assembly", "probe_report.json", {"duration_sec": 74.0, "width": 1080, "height": 1920})
    thumb = tmp_path / "thumb.png"
    Image.new("RGB", (1080, 1920), (30, 50, 90)).save(thumb, format="PNG")

    PublishStage(storage).run(
        title=script_doc["title"],
        hashtags=["#Shorts"],
        doi=script_doc["doi"],
        source_summary="Feinstein et al. (2013) tested CO2 inhalation.",
        thumbnail_source_img=thumb,
    )
    meta = storage.load_json("06_publish", "metadata.json")
    assert credits[0] in meta["description"]
    assert validate_v8_viewer_description(meta["description"], project_id=proj.name) == []

    # Zero CC-BY entries (PD only) -> zero Image credit lines emitted
    mf_path.write_text(
        json.dumps({"inserts": [{"clip_number": 2, "duration_sec": 2.5, "license": "Public Domain", "source_url": "https://commons.wikimedia.org/wiki/File:Old.jpg"}]}),
        encoding="utf-8",
    )
    PublishStage(storage).run(
        title=script_doc["title"],
        hashtags=["#Shorts"],
        doi=script_doc["doi"],
        source_summary="Feinstein et al. (2013) tested CO2 inhalation.",
        thumbnail_source_img=thumb,
    )
    meta_pd = storage.load_json("06_publish", "metadata.json")
    assert "Image credit:" not in meta_pd["description"]
    assert meta_pd["description"] == base_vd + "\n\n#shorts"


def test_r88_cast_lock_ep13_prompt_gate_and_brand_identity_pack() -> None:
    # 1. B01-B15 default block + Zero-Deletion SHA-256 preservation + faceless slot routing
    assert len(R88_RETIRED_CARTOON_CAST_SLOTS) == 15
    for b_slot in R88_RETIRED_CARTOON_CAST_SLOTS:
        with pytest.raises(CanonicalAssetError, match="retired under R88"):
            resolve_canonical_approved_slot(b_slot, verify_sha256=True)
        preserved = resolve_canonical_approved_slot(b_slot, verify_sha256=True, allow_retired_r88=True)
        assert preserved["abs_path"].is_file()

    assert select_canonical_character_slot(role_hint="neuroscience lab") == "E06_laboratory_staged"
    assert select_canonical_character_slot(role_hint="fmri scanner") == "E07_mri_suite_staged"
    assert select_canonical_character_slot(role_hint="breakfast coffee") == "E10_kitchen_staged"
    assert select_canonical_character_slot(role_hint="everyday figure") == "A01_mode1_translucent_head_lateral"

    # 2. validate_r88_faceless_cast_contract blocks cartoon eyes & B05 on v8_ep13+, preserves frozen Ep #1-#12
    bad_plan = {
        "style_profile": "expressive_25d_v8",
        "clips": [
            {
                "clip_number": 1,
                "canonical_slot_id": "B05_expr_surprised",
                "reference_image": "canonical_B05_expr_surprised.png",
                "scene": "Bald 2.5D vinyl researcher with 2D black ink eyes reacts in shock.",
            }
        ],
    }
    ep13_issues = validate_r88_faceless_cast_contract(bad_plan, project_id="v8_ep13_new_episode")
    assert any("[r88_retired_cartoon_cast_ban]" in msg and "B05_expr_surprised" in msg for msg in ep13_issues), ep13_issues
    assert any("[r88_retired_cartoon_cast_ban]" in msg and "2d black ink" in msg for msg in ep13_issues), ep13_issues

    for frozen_pid in ("v8_ep09_maguire_london_taxi_hippocampus", "v8_ep12_doorway_effect_memory"):
        assert frozen_pid in PRE_R88_FROZEN_V8_PROJECTS
        assert validate_r88_faceless_cast_contract(bad_plan, project_id=frozen_pid) == []

    # 3. Ep #13 main.py prompt-gate PASS
    ep13_dir = Path(WORKSPACE_ROOT) / "BCI_Shorts_Channel" / "projects" / "v8_ep13_snack_reward_rewiring"
    pg_proc = subprocess.run(
        [sys.executable, "-X", "utf8", "main.py", "prompt-gate", "--dir", str(ep13_dir)],
        cwd=str(WORKSPACE_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert pg_proc.returncode == 0, f"Ep #13 prompt-gate failed:\n{pg_proc.stdout}\n{pg_proc.stderr}"
    pg_rep = json.loads(pg_proc.stdout)
    assert pg_rep.get("passed") is True
    assert pg_rep.get("issues") == []

    # 4. scripts/verify_brand_assets.py --check (800x800 logos + 2560x1440 banner inside [507..2053, 508..931])
    brand_proc = subprocess.run(
        [sys.executable, "-X", "utf8", "scripts/verify_brand_assets.py", "--check"],
        cwd=str(WORKSPACE_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert brand_proc.returncode == 0, f"verify_brand_assets.py --check failed:\n{brand_proc.stdout}\n{brand_proc.stderr}"
    brand_rep = json.loads(brand_proc.stdout)
    assert brand_rep.get("passed") is True
    assert brand_rep.get("sha256_matches") is True
    assert brand_rep.get("void_seam_ok") is True
    assets = brand_rep.get("assets") or {}
    assert len(assets) == 38
    for logo_key in ("logo_A", "logo_A_red", "logo_A_ted_red", "logo_A_crimson_studio", "logo_B", "logo_C"):
        assert assets[logo_key]["size"] == "800x800"
        assert assets[logo_key]["sha256_match"] is True
    for banner_key in (
        "banner",
        "banner_red",
        "banner_matrix_10slice_A",
        "banner_matrix_10slice_B",
        "banner_crimson_echo_A",
        "banner_crimson_echo_B",
        "banner_mri_glass_A",
        "banner_mri_glass_B",
        "banner_jh1_lightbox",
        "banner_jh2_crimson_darkroom",
        "banner_jh3_human_element",
        "banner_jh3_yt_upload",
        "banner_jh4_fmri_tunnel",
        "banner_jh5_investigator_desk",
        "banner_jh2a_wave_stream",
        "banner_jh2b_multi_angle",
        "banner_jh2c_mri_strip",
        "banner_jh2d_echo_panorama",
        "banner_jh2e_cortical_horizon",
        "banner_rc1_pure_type",
        "banner_rc2_type_plus_brain",
        "banner_rc3_stacked_3d_poster",
    ):
        assert assets[banner_key]["size"] == "2560x1440"
        assert assets[banner_key]["sha256_match"] is True
    assert 0 < int(assets["banner_jh3_yt_upload"]["bytes"]) <= 5_500_000
    assert brand_rep.get("yt_banner_6mb_safe_ok") is True
    for sheet_key in (
        "comparison_sheet",
        "logo_A_cyan_vs_red_sheet",
        "logo_ted_red_bg_sheet",
        "banner_matrix_10slice_sheet",
        "banner_crimson_echo_sheet",
        "banner_mri_glass_sheet",
        "banner_jh5_collection_sheet",
        "banner_jh2_5opts_sheet",
        "banner_ricks_clips_3opts_sheet",
        "brand_final_lock_sheet",
    ):
        assert assets[sheet_key]["sha256_match"] is True
    assert brand_rep.get("logo_a_red_zero_pink_bleed_ok") is True
    assert brand_rep.get("ted_red_zero_navy_fringe_ok") is True
    assert brand_rep.get("matrix_10slice_banners_ok") is True
    assert brand_rep.get("crimson_echo_banners_ok") is True
    assert brand_rep.get("mri_glass_banners_ok") is True
    assert brand_rep.get("jh5_collection_ok") is True
    assert brand_rep.get("jh2_5opts_ok") is True
    assert brand_rep.get("ricks_clips_3opts_ok") is True
    assert brand_rep.get("final_lock_ok") is True
    rc_checks = brand_rep.get("banner_ricks_clips_checks") or {}
    assert len(rc_checks) == 3
    for rc_k in ("banner_rc1_pure_type", "banner_rc2_type_plus_brain", "banner_rc3_stacked_3d_poster"):
        rc_chk = rc_checks.get(rc_k) or {}
        assert rc_chk.get("safe_bounds_ok") is True
        assert rc_chk.get("pure_vivid_red_wings_ok") is True
        assert rc_chk.get("chunky_3d_pop_type_ok") is True
        assert rc_chk.get("variant_feature_ok") is True
    jh5_checks = brand_rep.get("banner_jh5_checks") or {}
    assert len(jh5_checks) == 5
    for jh_k in (
        "banner_jh1_lightbox",
        "banner_jh2_crimson_darkroom",
        "banner_jh3_human_element",
        "banner_jh4_fmri_tunnel",
        "banner_jh5_investigator_desk",
    ):
        jh_chk = jh5_checks.get(jh_k) or {}
        assert jh_chk.get("safe_bounds_ok") is True
        assert jh_chk.get("zero_cartoon_faces_ok") is True
        assert jh_chk.get("zero_hard_seams_ok") is True
        assert jh_chk.get("cinema_grain_and_depth_ok") is True
    jh2_checks = brand_rep.get("banner_jh2_5opts_checks") or {}
    assert len(jh2_checks) == 5
    for jh2_k in (
        "banner_jh2a_wave_stream",
        "banner_jh2b_multi_angle",
        "banner_jh2c_mri_strip",
        "banner_jh2d_echo_panorama",
        "banner_jh2e_cortical_horizon",
    ):
        jh2_chk = jh2_checks.get(jh2_k) or {}
        assert jh2_chk.get("safe_bounds_ok") is True
        assert jh2_chk.get("zero_cartoon_faces_ok") is True
        assert jh2_chk.get("wide_blue_hologram_ok") is True
        assert jh2_chk.get("crimson_darkroom_and_grain_ok") is True
    for mx_chk_key in ("banner_matrix_10slice_A_check", "banner_matrix_10slice_B_check"):
        mx_chk = brand_rep.get(mx_chk_key) or {}
        assert mx_chk.get("text_bounds_ok") is True
        assert mx_chk.get("hero_10slice_mobile_and_wings_ok") is True
    for ce_chk_key in ("banner_crimson_echo_A_check", "banner_crimson_echo_B_check"):
        ce_chk = brand_rep.get(ce_chk_key) or {}
        assert ce_chk.get("title_only_bounds_ok") is True
        assert ce_chk.get("whole_brain_unclipped_ok") is True
        assert ce_chk.get("cyan_echoes_ok") is True
        assert ce_chk.get("crimson_atmosphere_ok") is True
    for mri_chk_key in ("banner_mri_glass_A_check", "banner_mri_glass_B_check"):
        mri_chk = brand_rep.get(mri_chk_key) or {}
        assert mri_chk.get("title_only_bounds_ok") is True
        assert mri_chk.get("slices_9_unclipped_ok") is True
        assert mri_chk.get("anatomy_and_wings_ok") is True
        assert mri_chk.get("crimson_atmosphere_ok") is True
    for sz_key in ("banner_safe_zone_check", "banner_red_safe_zone_check"):
        sz_chk = brand_rep.get(sz_key) or {}
        assert sz_chk.get("safe_zone_box") == [507, 508, 2053, 931]
        assert sz_chk.get("manifest_bounds_ok") is True
        assert sz_chk.get("rendered_pixel_bounds_ok") is True
        ux0, uy0, ux1, uy1 = sz_chk["combined_ink_union"]
        assert 507 <= ux0 and uy0 >= 508 and ux1 <= 2053 and uy1 <= 931


def test_finish_jh_banner_cli_on_synthetic_16x9(tmp_path: Path) -> None:
    from PIL import Image

    src_16x9 = tmp_path / "synthetic_backdrop_16x9.png"
    arr = Image.new("RGB", (1920, 1080), (24, 62, 79))
    arr.save(src_16x9)

    script_path = Path(WORKSPACE_ROOT) / "scripts" / "verify_brand_assets.py"
    out_notes = tmp_path / "out_jh_notes.png"
    out_clean = tmp_path / "out_jh_no_notes.png"

    for out_p, notes_flag, expected_notes in (
        (out_notes, "--notes", True),
        (out_clean, "--no-notes", False),
    ):
        proc = subprocess.run(
            [
                sys.executable,
                "-X",
                "utf8",
                str(script_path),
                "--finish-jh-banner",
                str(src_16x9),
                "--out",
                str(out_p),
                notes_flag,
            ],
            cwd=str(WORKSPACE_ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        assert proc.returncode == 0, f"--finish-jh-banner failed:\n{proc.stdout}\n{proc.stderr}"
        rep = json.loads(proc.stdout)
        assert rep["width"] == 2560
        assert rep["height"] == 1440
        assert rep["with_notes"] is expected_notes
        assert rep["safe_zone_box"] == [507, 508, 2053, 931]
        ux0, uy0, ux1, uy1 = rep["text_bboxes"]["combined_ink_union"]
        assert 507 <= ux0 and uy0 >= 508 and ux1 <= 2053 and uy1 <= 931
        with Image.open(out_p) as finished_im:
            assert finished_im.size == (2560, 1440)
            assert finished_im.mode == "RGB"


def test_r65_v4_thumbnail_prompt_honors_r88_faceless_cast_and_preserves_legacy() -> None:
    from pipeline.config import R88_BANNED_CARTOON_FACE_TOKENS
    from pipeline.thumbnail import build_r65_v4_in_skull_split_prompt

    r88_plan = {
        "r88_mode": True,
        "cast_profile": "r88_faceless_porcelain",
        "thumbnail": {
            "profile": "dark_void_paradox_v4",
            "top_split_label": "0 LB GAINED",
            "bottom_split_label": "BRAIN REWIRED?!",
            "top_human_action": "smooth featureless matte-white architectural porcelain figure beside scale",
            "bottom_human_action": "same smooth featureless matte-white architectural porcelain figure lifting spoon",
            "target_anatomy": "ventral striatum",
            "render_micro_labels": False,
        },
    }
    prompt_r88 = build_r65_v4_in_skull_split_prompt(
        r88_plan,
        {"title": "Snack Rewiring"},
        project_id="v8_ep13_snack_reward_rewiring",
    )
    low_r88 = prompt_r88.lower()
    assert "smooth featureless matte-white architectural porcelain figure" in low_r88
    assert "real expressive human" not in low_r88
    assert "never a white mannequin" not in low_r88
    for tok in R88_BANNED_CARTOON_FACE_TOKENS:
        assert tok.lower() not in low_r88

    explicit_r88 = build_r65_v4_in_skull_split_prompt(
        {"r88_mode": True, "thumbnail": {"in_skull_split_prompt": "50/50 split brain cutaway visual"}},
        project_id="v8_ep13_snack_reward_rewiring",
    ).lower()
    assert "smooth featureless matte-white architectural porcelain figure" in explicit_r88
    assert "real expressive human" not in explicit_r88
    assert "never a white mannequin" not in explicit_r88

    legacy_prompt = build_r65_v4_in_skull_split_prompt(
        {
            "allow_legacy_pre_r88": True,
            "thumbnail": {
                "profile": "in_skull_cutaway_split_v4",
                "top_human_action": "calm volunteer",
                "bottom_human_action": "shocked volunteer",
            },
        },
        project_id="v8_ep12_legacy_stub",
    ).lower()
    assert "real expressive human" in legacy_prompt
    assert "never a white mannequin" in legacy_prompt


def test_thumbnail_studio_propagates_flow_circuit_breaker_and_captures_warning_png(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import asyncio
    import base64
    import io
    from pipeline import flow_ingredients
    from pipeline import thumbnail as ts
    from pipeline.flow_browser import FlowCircuitBreakerError

    proj = tmp_path / "v8_ep13_thumb_halt"
    (proj / "02_script").mkdir(parents=True)
    (proj / "03_visuals").mkdir(parents=True)
    (proj / "06_publish").mkdir(parents=True)
    (proj / "02_script" / "script.json").write_text(json.dumps({"title": "Snack Paradox"}), encoding="utf-8")
    (proj / "03_visuals" / "visual_plan.json").write_text(
        json.dumps(
            {
                "r88_mode": True,
                "thumbnail": {
                    "profile": "dark_void_paradox_v4",
                    "top_split_label": "0 LB GAINED",
                    "bottom_split_label": "BRAIN REWIRED?!",
                    "top_human_action": "matte-white porcelain silhouette beside yogurt bowl",
                    "bottom_human_action": "matte-white porcelain silhouette lifting pudding spoon",
                },
            }
        ),
        encoding="utf-8",
    )
    (proj / "06_publish" / "metadata.json").write_text(json.dumps({"title": "Snack Paradox"}), encoding="utf-8")

    buf = io.BytesIO()
    Image.new("RGB", (64, 64), (240, 60, 60)).save(buf, format="PNG")
    dummy_b64 = base64.b64encode(buf.getvalue()).decode("ascii")

    class _CaptchaStubClient:
        async def eval(
            self, expr: str, timeout_sec: float = 10.0, await_promise: bool = False
        ) -> object:
            if "edLen:" in expr:
                return {"edLen": 0, "pending": 0}
            if "action: 'listener_invoked'" in expr:
                return {"action": "listener_invoked", "x": 400, "y": 800, "disabled": False}
            if "errCount" in expr and "failedTileCount" in expr:
                return {"urls": [], "errCount": 0, "failedTileCount": 0}
            if "flow-pending-tile').length" in expr and "urls" not in expr:
                return 0
            if "Boolean(document.querySelector('button.prompt-warning-button'))" in expr:
                return False
            if "flow-pending-tile" in expr and "urls" in expr:
                return {
                    "urls": [],
                    "pending": 0,
                    "errTiles": 1,
                    "failedTileCount": 0,
                    "topErrText": "CAPTCHA: verify you are human",
                    "haltWarn": True,
                    "haltText": "CAPTCHA: verify you are human",
                }
            return True

        async def send(self, method: str, params: dict | None = None) -> dict:
            if method == "Page.captureScreenshot":
                return {"data": dummy_b64}
            return {}

    async def _fast_sleep(_sec: float, result: object = None) -> object:
        return result

    async def _noop_clear(_c: object) -> None:
        return None

    async def _fake_cfg(*_a: object, **_kw: object) -> dict:
        return {"image_model": "Nano Banana 2.1", "output_count": 2, "zero_credit_verified": True}

    async def _fake_find(_c: object, *_a: object, **_kw: object) -> tuple[int, int]:
        return (200, 300)

    async def _fake_click(_c: object, *_a: object, **_kw: object) -> None:
        return None

    monkeypatch.setattr(flow_ingredients.asyncio, "sleep", _fast_sleep)
    monkeypatch.setattr(flow_ingredients, "clear_prompt_ingredients", _noop_clear)
    monkeypatch.setattr(flow_ingredients, "configure_flow_zero_credit_image_mode", _fake_cfg)
    monkeypatch.setattr(flow_ingredients, "find_point", _fake_find)
    monkeypatch.setattr(flow_ingredients, "trusted_click", _fake_click)

    res_img = asyncio.run(
        flow_ingredients.generate_flow_image_batch(
            _CaptchaStubClient(),
            prompt="test r88 split",
            out_path=proj / "06_publish" / "keyart_candidates" / "keyart_winner.png",
            batch_count=2,
            aspect="9:16",
            project_dir=proj,
        )
    )
    assert res_img["ok"] is False
    assert res_img["reason"] == "flow_unusual_activity_blocked"
    warn_shot = Path(str(res_img["warning_screenshot"]))
    assert warn_shot.is_file()
    assert warn_shot.name == "flow_warning_capture_image.png"

    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.setattr(
        ts,
        "collect_candidates",
        lambda *_a, **_kw: [
            ts.ThumbCandidate(
                cut_index=1,
                clip_index=1,
                act=1,
                sentence_index=1,
                end_sentence_index=1,
                out_sec=1.0,
                offset_in_cut_sec=0.2,
                src_sec=1.0,
                grammar="porcelain_pov_hands",
                cut_dict={},
                image=np.zeros((1920, 1080, 3), dtype=np.uint8),
                raw_metrics={"sharpness": 50.0, "contrast": 45.0, "center_salience": 1.2},
            )
        ],
    )

    class _FakeCDPContext:
        def __init__(self, _ws: str) -> None:
            pass

        async def __aenter__(self) -> _CaptchaStubClient:
            return _CaptchaStubClient()

        async def __aexit__(self, *args: object) -> None:
            return None

    async def _fake_alloc_thumb(**_kw: object) -> dict:
        return {
            "tab_id": "FAKE_THUMB_TAB",
            "ws_url": "ws://127.0.0.1:9222/devtools/page/FAKE_THUMB_TAB",
            "project_url": "https://flow.google.com/project/thumb-halt-test",
            "lease_owner_id": "test:thumb",
        }

    async def _fake_rename(_c: object, _title: str) -> bool:
        return True

    released: list[str] = []
    monkeypatch.setattr("pipeline.flow_single_worker.allocate_dedicated_flow_project_tab", _fake_alloc_thumb)
    monkeypatch.setattr("pipeline.flow_workspace.rename_active_flow_project", _fake_rename)
    monkeypatch.setattr("pipeline.studio.browser_session.DirectCDPClient", _FakeCDPContext)
    monkeypatch.setattr("pipeline.flow_ingredients.generate_flow_image_batch", lambda *_a, **_kw: asyncio.sleep(0, result=res_img))
    monkeypatch.setattr(
        "pipeline.cdp_tab_lease.release_and_close_leased_tab",
        lambda tid, **_kw: released.append(tid) or True,
    )

    with pytest.raises(FlowCircuitBreakerError, match="FLOW_HALT_GUARD on thumbnail keyart"):
        ts.run(proj, force=True, generate_keyart=True)
    assert released == ["FAKE_THUMB_TAB"]


def test_flow_diorama_room_receipt_seeding_and_zero_bypass_halt_guard(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import asyncio
    import base64
    import io
    from pipeline import flow_worker as fdsw
    from pipeline import flow_single_worker as flsw
    from pipeline.cdp_tab_lease import get_tab_lease, release_tab_lease
    from pipeline.flow_browser import FlowCircuitBreakerError

    # 1. allocate_dedicated_flow_project_tab directly reuses an unleased open tab matching existing_project_url
    room_url = "https://flow.google.com/project/8d5a1772-daf4-4e6e-acc4-4d1a67627c6f"
    fake_tabs = [
        {
            "id": "PARKED_EP13_TAB",
            "url": room_url,
            "title": "Google Flow",
            "webSocketDebuggerUrl": "ws://127.0.0.1:9222/devtools/page/PARKED_EP13_TAB",
        }
    ]

    class _FakeResp:
        def __init__(self, data: bytes) -> None:
            self._data = data

        def __enter__(self) -> "_FakeResp":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def read(self) -> bytes:
            return self._data

    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda *_a, **_kw: _FakeResp(json.dumps(fake_tabs).encode("utf-8")),
    )
    monkeypatch.setenv("AAB_CDP_LEASES_PATH", str(tmp_path / "aab_cdp_leases.json"))
    monkeypatch.setenv("AAB_LOCKS_DIR", str(tmp_path / "aab_locks"))

    try:
        alloc = asyncio.run(
            flsw.allocate_dedicated_flow_project_tab(
                cdp_port=9222,
                project_id="v8_ep13_snack_reward_rewiring",
                lease_owner_id="test:ep13_reuse",
                existing_project_url=room_url,
            )
        )
        assert alloc["tab_id"] == "PARKED_EP13_TAB"
        assert alloc["project_url"] == room_url
        assert get_tab_lease("PARKED_EP13_TAB", cdp_port=9222) is not None
    finally:
        release_tab_lease("PARKED_EP13_TAB", owner_id="test:ep13_reuse", cdp_port=9222)

    # 2. run_sharded_diorama_flow_generation seeds existing_project_url from flow_room_receipt.json & halts with 0 sleeps/retries
    proj = tmp_path / "v8_ep13_halt_unit"
    (proj / "02_script").mkdir(parents=True)
    ref_img = proj / "03_visuals" / "reference_images" / "ref_01.png"
    ref_img.parent.mkdir(parents=True)
    rng = np.random.default_rng(13)
    cv2.imwrite(str(ref_img), rng.integers(30, 220, size=(128, 72, 3), dtype=np.uint8))

    (proj / "02_script" / "script.json").write_text(json.dumps({"sentences": ["Short test hook."]}), encoding="utf-8")
    clip_spec = {
        "clip_number": 1,
        "sentence_index": 0,
        "grammar": "porcelain_pov_hands",
        "reference_image": "03_visuals/reference_images/ref_01.png",
        "prompt": "smooth featureless matte-white architectural porcelain figure hands on table",
    }
    (proj / "03_visuals" / "visual_plan.json").write_text(
        json.dumps({"schema_version": 8, "r88_mode": True, "clips": [clip_spec]}),
        encoding="utf-8",
    )
    (proj / "03_visuals" / "flow_room_receipt.json").write_text(
        json.dumps({"room_url": room_url}),
        encoding="utf-8",
    )

    seen_alloc_urls: list[str] = []
    submit_count = {"n": 0}
    sleep_secs: list[float] = []

    buf = io.BytesIO()
    Image.new("RGB", (64, 64), (200, 40, 40)).save(buf, format="PNG")
    dummy_png_b64 = base64.b64encode(buf.getvalue()).decode("ascii")

    async def _fake_alloc_worker(**kw: object) -> dict:
        seen_alloc_urls.append(str(kw.get("existing_project_url") or ""))
        return {
            "tab_id": "PARKED_EP13_TAB",
            "ws_url": "ws://127.0.0.1:9222/devtools/page/PARKED_EP13_TAB",
            "project_url": str(kw.get("existing_project_url") or room_url),
            "lease_owner_id": "test:shard1",
        }

    async def _fake_submit(*_a: object, submission_meta_out: dict | None = None, **_kw: object) -> bool:
        submit_count["n"] += 1
        if isinstance(submission_meta_out, dict):
            submission_meta_out.update(
                {
                    "flow_model": "Omni 1.2 Flash",
                    "credit_tier": "omni_monthly_credit",
                    "reference_attached": True,
                    "attached_chip_count": 1,
                    "input_mode": "VIDEO_REFERENCES",
                }
            )
        return True

    class _HaltShardClient:
        def __init__(self, _ws: str) -> None:
            pass

        async def __aenter__(self) -> "_HaltShardClient":
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

        async def send(self, method: str, params: dict | None = None, timeout_sec: float = 10.0) -> dict:
            if method == "Page.captureScreenshot":
                return {"data": dummy_png_b64}
            return {}

        async def eval(self, expr: str, timeout_sec: float = 10.0) -> object:
            if "credit_banner" in expr:
                return {"credit_banner": False}
            if "flow-video-tile" in expr and "hasNewSrc" in expr:
                return {
                    "ready": 0,
                    "rendering": 0,
                    "hasNewSrc": False,
                    "topKey": "",
                    "hadErr": True,
                    "errText": "We noticed some unusual activity. Wait a few moments.",
                    "haltWarn": True,
                    "haltText": "We noticed some unusual activity. Wait a few moments.",
                }
            return {}

    async def _fast_guard_sleep(sec: float, result: object = None) -> object:
        assert float(sec) < 30.0, f"Zero-Bypass Halt Guard must never sleep for cooldown ({sec}s)"
        sleep_secs.append(float(sec))
        return result

    monkeypatch.setattr(fdsw.asyncio, "sleep", _fast_guard_sleep)
    monkeypatch.setattr(fdsw, "load_diorama_script_sentences", lambda _p: (["Short test hook."], {}))
    monkeypatch.setattr(fdsw, "build_diorama_v6_prompts", lambda _vp, _s: [dict(clip_spec)])
    monkeypatch.setattr(fdsw, "write_flow_prompts_json", lambda _p, _c: None)
    monkeypatch.setattr("pipeline.episode_qa.write_episode_qa_contract", lambda *_a: (None, {}))
    monkeypatch.setattr(fdsw, "allocate_dedicated_flow_project_tab", _fake_alloc_worker)
    monkeypatch.setattr(fdsw, "DirectCDPClient", _HaltShardClient)
    monkeypatch.setattr(fdsw, "rename_active_flow_project", lambda *_a, **_kw: asyncio.sleep(0, result=True))
    monkeypatch.setattr(fdsw, "probe_flow_account_credits", lambda *_a, **_kw: asyncio.sleep(0, result={"credits_remaining": 1000, "exhausted": False}))
    monkeypatch.setattr(fdsw, "_configure_diorama_tab_engine", lambda *_a, **_kw: asyncio.sleep(0, result={"flow_model": "Omni 1.2 Flash", "credit_tier": "omni_monthly_credit", "settings_summary": "Video"}))
    monkeypatch.setattr(fdsw, "_submit_diorama_prompt_zero_credit", _fake_submit)
    monkeypatch.setattr(fdsw, "release_and_close_leased_tab", lambda *_a, **_kw: False)
    monkeypatch.setattr(fdsw, "reap_orphan_pipeline_tabs", lambda *_a, **_kw: None)
    monkeypatch.setattr(fdsw, "FLOW_AUTO_CLEANUP_ON_SUCCESS", False)

    with pytest.raises(FlowCircuitBreakerError, match="FLOW_HALT_GUARD on Clip 1"):
        asyncio.run(fdsw.run_sharded_diorama_flow_generation(proj, max_parallel_tabs=1, engine_mode="auto"))

    assert seen_alloc_urls == [room_url]
    assert submit_count["n"] == 1
    warn_clip_png = proj / "03_visuals" / "flow_screenshots" / "flow_warning_capture_clip_01.png"
    assert warn_clip_png.is_file() and warn_clip_png.stat().st_size > 20


def test_flow_antibot_modal_filter_and_dynamic_omni_episode_cap() -> None:
    import subprocess
    from pipeline.config import FLOW_OMNI_CREDIT_COST_WITH_REF, compute_dynamic_omni_episode_budget
    from pipeline.flow_browser import FLOW_DETECT_ANTIBOT_HALT_JS
    from pipeline.flow_worker import resolve_effective_clip_engine_mode

    # 1. Verify errSnips precedence + passive anchor ignore + visible interactive bframe detection via Node
    node_script = f"""
const detectHalt = {FLOW_DETECT_ANTIBOT_HALT_JS};
global.window = {{
  innerWidth: 1280,
  innerHeight: 900,
  getComputedStyle: (el) => el._cs || {{ display: 'block', visibility: 'visible', opacity: '1' }},
}};
let mockFrames = [];
let mockDialogs = [];
global.document = {{
  querySelectorAll: (sel) => {{
    if (sel.includes('iframe')) return mockFrames;
    if (sel.includes('[role="dialog"]')) return mockDialogs;
    return [];
  }},
}};
const mkFrame = (src, rect, cs) => ({{
  src,
  _cs: cs || {{ display: 'block', visibility: 'visible', opacity: '1' }},
  getAttribute: (k) => (k === 'src' ? src : ''),
  getBoundingClientRect: () => rect,
}});

// Passive corner badge anchor (even 256x60 or 70x70) must NOT false-trigger halt
mockFrames = [
  mkFrame('https://www.google.com/recaptcha/enterprise/anchor?k=abc', {{ width: 256, height: 60, top: 800, left: 1000, bottom: 860, right: 1256 }}),
  mkFrame('https://www.google.com/recaptcha/enterprise/bframe?k=abc', {{ width: 400, height: 580, top: 100, left: 200, bottom: 680, right: 600 }}, {{ display: 'none', visibility: 'visible', opacity: '1' }}),
];
const rPassive = detectHalt(['temporary render timeout']);
if (rPassive.haltWarn) throw new Error('Passive anchor false positive: ' + JSON.stringify(rPassive));

// Visible interactive challenge iframe MUST trigger haltWarn
mockFrames.push(mkFrame('https://www.google.com/recaptcha/enterprise/bframe?k=abc', {{ width: 400, height: 580, top: 100, left: 200, bottom: 680, right: 600 }}));
const rModal = detectHalt([]);
if (!rModal.haltWarn || rModal.haltText !== 'anti_bot_captcha_iframe') throw new Error('Expected modal halt: ' + JSON.stringify(rModal));

// errSnips unusual activity MUST take priority over generic anti_bot_captcha_iframe
const rErrFirst = detectHalt(['We noticed some unusual activity. Wait a few moments.']);
if (!rErrFirst.haltWarn || !rErrFirst.haltText.includes('unusual activity')) throw new Error('errSnips must win precedence: ' + JSON.stringify(rErrFirst));
console.log('ANTIBOT_FILTER_OK');
"""
    proc = subprocess.run(["node", "-e", node_script], capture_output=True, text=True, check=True)
    assert "ANTIBOT_FILTER_OK" in proc.stdout

    # 2. Verify dynamic episode_cap allows 360 live credits in --engine auto to route 14 Omni clips (> 200 cap)
    dyn = compute_dynamic_omni_episode_budget(360, clip_count=19, cost_per_clip=FLOW_OMNI_CREDIT_COST_WITH_REF)
    assert dyn["budget_credits"] == 340
    assert dyn["max_omni_clips"] == 14
    m_14, r_14 = resolve_effective_clip_engine_mode(
        "auto",
        None,
        episode_omni_credits_spent=312,
        clip_omni_cost=24,
        episode_cap=dyn["budget_credits"],
    )
    assert m_14 == "auto" and r_14 is None
    m_15, r_15 = resolve_effective_clip_engine_mode(
        "auto",
        None,
        episode_omni_credits_spent=336,
        clip_omni_cost=24,
        episode_cap=dyn["budget_credits"],
    )
    assert m_15 == "zero-credit" and "episode_omni_cap_reached" in str(r_15)


def test_dq8_glossy_chocolate_bowl_routes_to_moderate_gate2_without_weakening_skin_high_suspect() -> None:
    from pipeline.skin_qa import classify_dq8_yunet_box

    # 1. Mixed dark chocolate (V<75) + lit brown swirls (V>=75, high a*) in white ceramic bowl -> MODERATE_SUSPECT
    bowl = np.full((300, 300, 3), 235, dtype=np.uint8)  # bright white ceramic outer rim
    cv2.circle(bowl, (150, 150), 95, (18, 24, 58), -1)   # dark chocolate base (raw_l_med < 83)
    cv2.rectangle(bowl, (85, 85), (215, 130), (54, 72, 134), -1)  # lit cocoa swirl (non_ink l_med >= 85, high hemoglobin)
    cv2.circle(bowl, (128, 125), 8, (245, 245, 245), -1)  # glossy specular glare spot
    cv2.circle(bowl, (172, 125), 7, (245, 245, 245), -1)  # specular glare spot 2
    res_bowl = classify_dq8_yunet_box(
        bowl,
        [70, 70, 160, 160],
        0.72,
        [[128, 125], [172, 125], [150, 155], [130, 185], [170, 185]],
        is_precrop=True,
    )
    assert res_bowl["metrics"]["raw_l_med"] < 83.0
    assert res_bowl["metrics"]["l_med"] >= 85.0
    assert res_bowl["metrics"]["hemoglobin_index"] >= 6.0
    assert res_bowl["tier"] == "MODERATE_SUSPECT"
    assert res_bowl["is_high_suspect"] is False
    assert res_bowl["is_suspect"] is True
    assert "glossy_bowl_or_liquid_pareidolia_for_gate2" in res_bowl["reasons"]

    # 1b. Closeup chocolate bowl where ceramic rim lifts raw_l_med into 83..92 -> STILL MODERATE_SUSPECT
    closeup_bowl = np.full((300, 300, 3), 240, dtype=np.uint8)
    closeup_bowl[65:235, 65:235] = (50, 72, 122)  # warm cocoa fill (raw_l_med ~ 86..89, high b* & a*)
    cv2.circle(closeup_bowl, (150, 145), 18, (248, 248, 248), -1)  # glossy specular glare (>= 2% of crop)
    res_closeup = classify_dq8_yunet_box(
        closeup_bowl,
        [60, 60, 180, 180],
        0.70,
        [[128, 125], [172, 125], [150, 155], [130, 185], [170, 185]],
        is_precrop=True,
    )
    assert 83.0 <= res_closeup["metrics"]["raw_l_med"] <= 92.0
    assert res_closeup["metrics"]["outer_ceramic_rim_frac"] >= 0.20
    assert res_closeup["metrics"]["specular_glare_frac"] >= 0.020
    assert res_closeup["tier"] == "MODERATE_SUSPECT"
    assert res_closeup["is_high_suspect"] is False
    assert "glossy_bowl_or_liquid_pareidolia_for_gate2" in res_closeup["reasons"]

    # 1c. Oversized overhead oak tabletop + ceramic trays/porcelain hand pareidolia -> STILL MODERATE_SUSPECT
    tabletop = np.full((1500, 1080, 3), (105, 132, 185), dtype=np.uint8)  # warm oak tabletop
    tabletop[:260, :] = (238, 238, 238)  # white ceramic tray rim
    tabletop[1180:, :] = (238, 238, 238)
    tabletop[900:1360, :440] = (238, 238, 238)  # matte porcelain hand + bowl glare inside ROI (>= 0.20)
    cv2.circle(tabletop, (220, 620), 140, (32, 48, 96), -1)  # chocolate bowl pareidolia under landmark
    res_tabletop = classify_dq8_yunet_box(
        tabletop,
        [0, 200, 760, 1150],
        0.70,
        [[180, 620], [560, 620], [380, 900], [230, 1120], [530, 1120]],
    )
    assert res_tabletop["metrics"]["min_dim"] >= 620.0
    assert res_tabletop["metrics"]["hemoglobin_index"] >= 6.0
    assert res_tabletop["metrics"]["chroma_heterogeneity"] >= 12.0
    assert res_tabletop["tier"] == "MODERATE_SUSPECT"
    assert res_tabletop["is_high_suspect"] is False
    assert res_tabletop["is_suspect"] is True
    assert "glossy_bowl_or_liquid_pareidolia_for_gate2" in res_tabletop["reasons"]

    # 2. Photoreal warm human skin face (raw_l_med >= 95, hemoglobin >= 7) MUST stay HIGH_SUSPECT
    skin = np.full((300, 300, 3), 180, dtype=np.uint8)
    skin[40:260, 50:250] = (128, 152, 205)  # warm reddish peach BGR (L ~ 166, a > 138 -> high hemoglobin)
    res_skin = classify_dq8_yunet_box(
        skin,
        [60, 50, 180, 200],
        0.85,
        [[120, 120], [180, 120], [150, 155], [125, 195], [175, 195]],
        is_precrop=True,
    )
    assert res_skin["tier"] == "HIGH_SUSPECT"
    assert res_skin["is_high_suspect"] is True

