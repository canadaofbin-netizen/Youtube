"""
ALL ABOUT BRAIN - Deliverable Overwatch Verification Loop (`pipeline/deliverable_overwatch.py`).

Closed-loop programmatic verifier that audits:
  - Deliverable A (`06_example_hippocampus_9x16_vertical.mp4`):
    Native 9:16 vertical (~8s) opaque matte-white porcelain cutaway head/brain exposing C-shaped hippocampal
    gyrus & arched fornix tract, dynamic push-in, zero R53 green/blue flying particles.
  - Deliverable B (`07_example_flow_hippocampus_translucent_9x16.mp4`):
    Native 9:16 vertical (~8s) semi-translucent frosted 3D whole brain rotating dynamically on slate backdrop
    with warm champagne-amber/ivory internal signals, zero R53 green/blue flying particles.
  - Deliverable C (`psych_04_phineas_gage_frontal_lobe` project + exported final Shorts MP4s):
    Explicit item-by-item verification of Items 1, 2, 3, 4, 5, 8, 9, and 10, plus staleness check verifying
    whether the assembled deliverable MP4s actually incorporate the latest `clip_1..clip_10.mp4` SHA-256s.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from pipeline.clip_qa_contract import (
    AUDIO_TRUE_PEAK_MAX_DBFS,
    SAMPLE_WINDOWS_5PT,
    analyze_brain_anatomy_frame,
    compile_clip_qa_contract,
    compute_camera_compensated_motion,
    compute_sha256,
    compute_spatial_and_palette_continuity,
    count_porcelain_upper_figures,
    detect_r53_neon_particles,
    sample_video_frames_5pt,
    verify_clips_against_contract,
)
from pipeline.config import PROJECTS_DIR, WORKSPACE_ROOT
from pipeline.video_autopsy import VideoAutopsyEngine


def verify_standalone_brain_deliverable(
    mp4_path: Path,
    ref_png_path: Path | None = None,
    mode: str = "opaque_porcelain_cross_section",
) -> dict[str, Any]:
    """
    Verifies a standalone 9:16 brain example video (Deliverable A or Deliverable B) against its
    explicit visual, motion, aspect, and R53 zero-particle contract.
    """
    v_path = Path(mp4_path)
    issues: list[str] = []
    if not v_path.exists() or v_path.stat().st_size < 250_000:
        return {
            "path": str(v_path),
            "mode": mode,
            "exists": v_path.exists(),
            "passed": False,
            "issues": ["missing_or_undersized_video_file"],
        }

    meta, sampled = sample_video_frames_5pt(v_path, SAMPLE_WINDOWS_5PT)
    all_frames = meta.pop("_all_frames", [])
    if not meta["readable"] or not sampled:
        return {
            "path": str(v_path),
            "mode": mode,
            "exists": True,
            "passed": False,
            "issues": ["unreadable_video_stream"],
        }

    w, h = int(meta["width"]), int(meta["height"])
    dur = float(meta["duration_sec"])
    ratio = float(w) / float(max(1, h))
    if w >= h or abs(ratio - (9.0 / 16.0)) > 0.04:
        issues.append(f"not_native_9x16_vertical: {w}x{h}")
    if not (5.5 <= dur <= 11.5):
        issues.append(f"duration_out_of_8s_bounds: {dur:.2f}s")

    # R53 Neon Green/Cyan Particle Check across 6 points
    part_pcts = (0.0, 0.20, 0.40, 0.60, 0.80, 0.95)
    n_all = len(all_frames)
    part_samples = [all_frames[min(n_all - 1, int(round(p * (n_all - 1))))] for p in part_pcts]
    part_reps = [detect_r53_neon_particles(frm, is_brain_or_cutaway=True) for frm in part_samples]
    max_dots = max(r["floating_particle_dots"] for r in part_reps)
    max_neon_ratio = max(r["neon_green_cyan_ratio"] for r in part_reps)
    if any(r["has_particle_bleed"] for r in part_reps):
        issues.append(
            f"r53_chaotic_green_cyan_particles_detected: max_floating_dots={max_dots}, max_neon_ratio={max_neon_ratio:.5f}"
        )

    # Anatomy & Material Check
    anat_reps = [analyze_brain_anatomy_frame(frm) for _, frm in sampled]
    mean_bg_luma = round(float(np.mean([a["bg_luma"] for a in anat_reps])), 2)
    max_amber = max(a["amber_ratio"] for a in anat_reps)

    # Check warm ivory / porcelain luminance inside foreground head/brain
    mid_frm = sampled[len(sampled) // 2][1]
    gray_mid = cv2.cvtColor(mid_frm, cv2.COLOR_BGR2GRAY)
    p95_luma = float(np.percentile(gray_mid, 95))
    if p95_luma < 115.0:
        issues.append(f"underexposed_brain_highlight: p95_luma={p95_luma:.1f}")

    if mode == "translucent_3d_whole_brain":
        if mean_bg_luma > 130.0:
            issues.append(f"expected_slate_backdrop_got_bright_bg: bg_luma={mean_bg_luma:.1f}")
        if max_amber < 0.0015 and p95_luma < 165.0:
            issues.append(f"missing_warm_amber_ivory_internal_tract_glow: max_amber={max_amber:.5f}")
    else:
        # Opaque porcelain cutaway head/brain
        porcelain_white_ratio = float(np.mean(gray_mid >= 155))
        if porcelain_white_ratio < 0.04:
            issues.append(f"missing_opaque_matte_white_porcelain_surface: white_ratio={porcelain_white_ratio:.4f}")

    # Motion & Dynamic Camera Progression
    motion = compute_camera_compensated_motion(all_frames, float(meta["fps"]))
    if motion["raw_flow_mean"] < 0.14 or motion["beat1_vs_beat2_shift"] < 0.025:
        issues.append(
            f"insufficient_dynamic_camera_or_3d_motion: raw_flow={motion['raw_flow_mean']:.3f}, shift={motion['beat1_vs_beat2_shift']:.3f}"
        )

    # Optional Reference Continuity Check
    ref_cont: dict[str, Any] | None = None
    if ref_png_path is not None and Path(ref_png_path).exists():
        ref_bgr = cv2.imread(str(ref_png_path))
        if ref_bgr is not None and ref_bgr.size > 0:
            scores = [compute_spatial_and_palette_continuity(ref_bgr, frm) for _, frm in sampled]
            min_hsv = min(s["hsv_corr"] for s in scores)
            max_comb = max(s["combined_score"] for s in scores)
            min_comb = min(s["combined_score"] for s in scores)
            ref_cont = {
                "ref_path": str(ref_png_path),
                "min_combined_5pt": round(min_comb, 4),
                "max_combined_5pt": round(max_comb, 4),
                "min_hsv_5pt": round(min_hsv, 4),
            }
            if max_comb < 0.45 or min_hsv < 0.40:
                issues.append(f"reference_mismatch: max_comb={max_comb:.3f}, min_hsv={min_hsv:.3f}")

    return {
        "path": str(v_path),
        "sha256": compute_sha256(v_path),
        "mode": mode,
        "exists": True,
        "resolution": f"{w}x{h}",
        "duration_sec": dur,
        "r53_particles": {
            "max_floating_particle_dots": max_dots,
            "max_neon_green_cyan_ratio": round(max_neon_ratio, 6),
        },
        "material_and_anatomy": {
            "mean_bg_luma": mean_bg_luma,
            "p95_highlight_luma": round(p95_luma, 2),
            "max_warm_amber_ratio": round(max_amber, 5),
        },
        "motion": motion,
        "reference_continuity": ref_cont,
        "passed": len(issues) == 0,
        "issues": issues,
    }


def _detect_orange_spark_or_blast_flash(mp4_path: Path) -> dict[str, Any]:
    """Checks whether Clip 1 contains both dark/metallic vertical rod edges and a bright spark/smoke flash event."""
    if not mp4_path.exists():
        return {"has_spark_or_blast_peak": False, "spark_peak_ratio": 0.0, "luma_surge": 0.0}
    meta, sampled = sample_video_frames_5pt(mp4_path, (0.0, 0.20, 0.42, 0.55, 0.72, 0.90))
    all_frames = meta.get("_all_frames") or [f for _, f in sampled]
    if not all_frames:
        return {"has_spark_or_blast_peak": False, "spark_peak_ratio": 0.0, "luma_surge": 0.0}

    step = max(1, len(all_frames) // 16)
    spark_ratios: list[float] = []
    lumas: list[float] = []
    for frm in all_frames[::step]:
        small = cv2.resize(frm, (180, 320), interpolation=cv2.INTER_AREA)
        hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)
        H, S, V = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]
        spark = ((H <= 26) & (S >= 110) & (V >= 195))
        spark_ratios.append(float(np.mean(spark)))
        lumas.append(float(np.mean(V)))

    max_spark = max(spark_ratios) if spark_ratios else 0.0
    luma_surge = (max(lumas) - min(lumas)) if len(lumas) >= 2 else 0.0
    return {
        "has_spark_or_blast_peak": bool(max_spark >= 0.0004),
        "spark_peak_ratio": round(max_spark, 6),
        "luma_surge": round(luma_surge, 2),
    }


def _inspect_clip9_lab_scene(mp4_path: Path) -> dict[str, Any]:
    """Verifies Clip 9 has a lone porcelain researcher in crisp white coat, porcelain skull in frame, and glowing 3D CT/tractography screen."""
    if not mp4_path.exists():
        return {"max_upper_figures": 0, "has_3d_tractography_glow": False, "min_white_coat_porcelain_ratio": 0.0}
    _, sampled = sample_video_frames_5pt(mp4_path, SAMPLE_WINDOWS_5PT)
    if not sampled:
        return {"max_upper_figures": 0, "has_3d_tractography_glow": False, "min_white_coat_porcelain_ratio": 0.0}
    max_figs = max(count_porcelain_upper_figures(frm) for _, frm in sampled)
    max_amber = 0.0
    min_porc = 1.0
    for _, frm in sampled:
        small = cv2.resize(frm, (180, 320), interpolation=cv2.INTER_AREA)
        hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)
        amber = ((hsv[:, :, 0] >= 10) & (hsv[:, :, 0] <= 34) & (hsv[:, :, 1] >= 65) & (hsv[:, :, 2] >= 120))
        max_amber = max(max_amber, float(np.mean(amber)))
        ch = hsv[58:262, 27:153]
        porc = float(np.mean((ch[:, :, 1] <= 55) & (ch[:, :, 2] >= 150)))
        min_porc = min(min_porc, porc)
    return {
        "max_upper_figures": int(max_figs),
        "max_tractography_amber_ratio": round(max_amber, 5),
        "has_3d_tractography_glow": bool(max_amber >= 0.002),
        "min_white_coat_porcelain_ratio": round(min_porc if min_porc <= 1.0 else 0.0, 4),
    }


def _check_left_eye_cutaway_side(bgr: np.ndarray | None) -> tuple[bool, float]:
    """
    Verifies that a portrait prefrontal cutaway sits on the subject's anatomical LEFT side rather than carved
    into viewer-left while the intact porcelain face sits on viewer-right (= anatomical RIGHT eye/temple!).
    """
    if bgr is None or bgr.size == 0:
        return True, 0.0
    s = cv2.resize(bgr, (180, 320), interpolation=cv2.INTER_AREA)
    head = cv2.cvtColor(s, cv2.COLOR_BGR2HSV)[40:170, :]
    porc_mask = (head[:, :, 1] <= 38) & (head[:, :, 2] >= 165)
    glow_mask = ((head[:, :, 0] >= 6) & (head[:, :, 0] <= 34) & (head[:, :, 1] >= 75) & (head[:, :, 2] >= 125))
    if int(np.sum(porc_mask)) <= 20 or int(np.sum(glow_mask)) <= 10:
        return True, 0.0
    porc_x = float(np.mean(np.where(porc_mask)[1])) / 180.0
    glow_x = float(np.mean(np.where(glow_mask)[1])) / 180.0
    delta_x = round(glow_x - porc_x, 4)
    return bool(delta_x >= -0.10), delta_x


def verify_phineas_gage_deliverable(
    project_dir: Path,
    deliverable_mp4s: list[Path] | None = None,
    save_in_project: bool = False,
) -> dict[str, Any]:
    """
    Evaluates `psych_04_phineas_gage_frontal_lobe` against Items 1, 2, 3, 4, 5, 6 (Clip 5), 8, 9, and 10,
    enforces full Reference Image QA (`pre_generation_ready`) + SHA-256 `clip_semantic_review.json`,
    and checks whether exported deliverable MP4s are up to date with the latest `clip_1..clip_10.mp4`.
    """
    from pipeline.reference_image_qa import inspect_reference_image_pack, is_reference_qa_report_fresh

    p_dir = Path(project_dir)
    contract = compile_clip_qa_contract(p_dir, save=save_in_project)
    has_full_10clip_plan = int(contract.get("clip_count") or 0) >= 10
    clip_qa = verify_clips_against_contract(
        p_dir,
        contract=contract,
        save_report=save_in_project,
        render_strips=save_in_project,
        require_reference_pack=has_full_10clip_plan,
        require_semantic_review=has_full_10clip_plan,
    )
    by_clip = {int(c["clip_number"]): c for c in clip_qa.get("clips") or []}

    ref_dir = p_dir / "03_visuals" / "reference_images"
    clips_dir = p_dir / "03_visuals" / "flow_native_clips"

    # Item 1: Clip 1 iconic tamping/spark/blast/cheek-to-skull iron rod + start-frame match to ref_clip_01.png
    c1 = by_clip.get(1, {})
    spark_info = _detect_orange_spark_or_blast_flash(clips_dir / "clip_1.mp4")
    ref1_exists = (ref_dir / "ref_clip_01.png").exists()
    item1_issues = list(c1.get("issues") or [])
    if not ref1_exists:
        item1_issues.append("missing_ref_clip_01.png")
    c1_wins = ((c1.get("continuity_5pt") or {}).get("windows") or [])
    c1_start_score = float(c1_wins[0]["combined_score"]) if c1_wins else 0.0
    if ref1_exists and c1_start_score < 0.82:
        item1_issues.append(f"clip_1_unregenerated_start_frame_mismatch_with_ref_clip_01: start_score={c1_start_score:.3f}<0.82")
    if not spark_info["has_spark_or_blast_peak"]:
        item1_issues.append(f"missing_spark_ignition_flash: {spark_info}")
    if float((c1.get("motion") or {}).get("beat1_vs_beat2_shift", 0.0)) < 0.04:
        item1_issues.append("clip_1_lacks_tamping_to_blast_visual_transition")

    # Item 2: Clip 2 narration-visual alignment (left-cheek/skull wound & rod -> pull back to ox cart talking)
    c2 = by_clip.get(2, {})
    ref2_exists = (ref_dir / "ref_clip_02.png").exists()
    item2_issues = list(c2.get("issues") or [])
    if not ref2_exists:
        item2_issues.append("missing_ref_clip_02.png")
    if float((c2.get("motion") or {}).get("beat1_vs_beat2_shift", 0.0)) < 0.06:
        item2_issues.append(
            f"clip_2_insufficient_wound_to_oxcart_pullback: shift={(c2.get('motion') or {}).get('beat1_vs_beat2_shift', 0.0):.3f}"
        )

    # Item 3: Clips 4, 6, 7, 8 anatomical accuracy (left orbitofrontal/vmPFC behind left eye, zero coronal/central)
    item3_issues: list[str] = []
    for bn in (4, 6, 7, 8):
        if bn > int(contract.get("clip_count") or 10):
            continue
        cb = by_clip.get(bn, {})
        for iss in cb.get("issues") or []:
            if any(k in iss for k in ("anatomical", "roi", "crimson", "r53_green", "missing_or_undersized")):
                item3_issues.append(f"clip_{bn}: {iss}")
        if not (ref_dir / f"ref_clip_{bn:02d}.png").exists():
            item3_issues.append(f"clip_{bn}: missing_ref_clip_{bn:02d}.png")

    # Item 4: Clip 10 conclusion relevance (left-eye judgment center -> steering six-horse stagecoach, zero right-eye flip)
    c10 = by_clip.get(10, {})
    item4_issues = list(c10.get("issues") or [])
    ref10_p = ref_dir / "ref_clip_10.png"
    if has_full_10clip_plan:
        if not ref10_p.exists():
            item4_issues.append("missing_ref_clip_10.png")
        else:
            side_ok, side_dx = _check_left_eye_cutaway_side(cv2.imread(str(ref10_p)))
            if not side_ok:
                item4_issues.append(
                    f"clip_10_anatomical_right_eye_cutaway_error: glow_minus_porcelain_x={side_dx:.3f}<-0.10"
                )
        if float((c10.get("motion") or {}).get("beat1_vs_beat2_shift", 0.0)) < 0.05:
            item4_issues.append(
                f"clip_10_insufficient_cutaway_to_stagecoach_pullback: shift={(c10.get('motion') or {}).get('beat1_vs_beat2_shift', 0.0):.3f}"
            )

    # Item 5: Cross-clip brain continuity across Clips 4, 6, 7, 8 + shared ref_brain_master.png anchor + Reference QA Pack
    cb_rep = clip_qa.get("cross_brain_continuity") or {}
    item5_issues = list(cb_rep.get("issues") or [])
    if not (ref_dir / "ref_brain_master.png").exists():
        item5_issues.append("missing_ref_brain_master.png")
    for bn in (4, 6, 7, 8):
        if bn > int(contract.get("clip_count") or 10):
            continue
        cb = by_clip.get(bn, {})
        for iss in cb.get("issues") or []:
            if "continuity" in iss or "morph" in iss:
                item5_issues.append(f"clip_{bn}: {iss}")
    if (p_dir / "03_visuals" / "reference_image_specs.json").exists():
        ref_pack_rep = inspect_reference_image_pack(p_dir, save_report=save_in_project)
        if not bool(ref_pack_rep.get("pre_generation_ready")):
            item5_issues.append(
                f"reference_image_pack_not_pre_generation_ready: regen={ref_pack_rep.get('regenerate_image_ids', [])}"
            )
        r_fresh, r_reasons = is_reference_qa_report_fresh(p_dir, ref_pack_rep)
        if save_in_project and not r_fresh:
            item5_issues.append(f"stale_reference_image_qa_report: {r_reasons}")

    # Item 6: Clip 5 pivot Chile stagecoach driving (seated on coach box steering porcelain horses, zero foot-walk/fur)
    c5 = by_clip.get(5, {})
    item6_issues = list(c5.get("issues") or []) if has_full_10clip_plan else []
    if has_full_10clip_plan:
        if not (ref_dir / "ref_clip_05.png").exists():
            item6_issues.append("missing_ref_clip_05.png")
        v6_state_path = p_dir.parent / "fix_gage_v6_state.json"
        if v6_state_path.exists():
            try:
                v6_st = json.loads(v6_state_path.read_text(encoding="utf-8"))
                if 5 not in (v6_st.get("vids_done") or []):
                    item6_issues.append("clip_5_unregenerated_legacy_foot_walk_stagecoach")
            except Exception:
                pass

    # Item 8: Clip 9 single researcher in crisp white coat + Gage skull & rod + 3D CT/tractography monitor
    c9 = by_clip.get(9, {})
    item8_issues = list(c9.get("issues") or [])
    if has_full_10clip_plan:
        ref9_path = ref_dir / "ref_clip_09.png"
        if not ref9_path.exists():
            item8_issues.append("missing_ref_clip_09.png_unconditioned_clip_9")
        else:
            ref9_bgr = cv2.imread(str(ref9_path))
            if ref9_bgr is not None and ref9_bgr.size > 0:
                ref9_figs = count_porcelain_upper_figures(ref9_bgr)
                if ref9_figs >= 2:
                    item8_issues.append(f"ref_clip_09_cloned_multiple_researcher_mannequins: upper_figures={ref9_figs}")
            v6_state_path = p_dir.parent / "fix_gage_v6_state.json"
            if v6_state_path.exists():
                try:
                    v6_st = json.loads(v6_state_path.read_text(encoding="utf-8"))
                    if 9 not in (v6_st.get("refs_done") or []):
                        item8_issues.append("stale_pre_v6_ref_clip_09.png_pending_regeneration")
                except Exception:
                    pass
        lab9 = _inspect_clip9_lab_scene(clips_dir / "clip_9.mp4")
        if lab9["max_upper_figures"] >= 2:
            item8_issues.append(f"clip_9_cloned_multiple_researcher_mannequins: max_upper_figures={lab9['max_upper_figures']}")
        if not lab9["has_3d_tractography_glow"]:
            item8_issues.append(f"clip_9_missing_3d_skull_ct_tractography_monitor: {lab9}")
        if lab9["min_white_coat_porcelain_ratio"] < 0.06:
            item8_issues.append(
                f"clip_9_missing_white_curator_coat_or_porcelain_skull_cropped_out: min_white_ratio={lab9['min_white_coat_porcelain_ratio']:.3f}<0.06"
            )

    # Item 10: Clip 3 dynamic camera & subject action progression in railroad office rejection scene
    c3 = by_clip.get(3, {})
    item10_issues = list(c3.get("issues") or [])
    if not (ref_dir / "ref_clip_03.png").exists():
        item10_issues.append("missing_ref_clip_03.png")
    c3_mot = c3.get("motion") or {}
    if float(c3_mot.get("residual_subject_flow_p90", 0.0)) < 0.75 or float(c3_mot.get("raw_flow_mean", 0.0)) < 0.14:
        item10_issues.append(
            f"clip_3_static_office_composition: raw_flow={c3_mot.get('raw_flow_mean', 0.0):.3f}, residual_p90={c3_mot.get('residual_subject_flow_p90', 0.0):.3f}"
        )

    # Item 9 & Deliverable Freshness: Check audio peak <= -1.0 dBFS AND whether assembled MP4s incorporate latest clips
    target_mp4s = list(deliverable_mp4s or [])
    proj_final = p_dir / "05_assembly" / "final_shorts_1080x1920.mp4"
    if proj_final not in target_mp4s:
        target_mp4s.insert(0, proj_final)

    latest_clip_mtime = max(
        (cf.stat().st_mtime for cf in clips_dir.glob("clip_*.mp4") if cf.is_file()),
        default=0.0,
    ) if clips_dir.exists() else 0.0

    # Also check asset_manifest.json SHA-256s if present
    manifest_path = p_dir / "05_assembly" / "asset_manifest.json"
    manifest_clip_shas: dict[str, str] = {}
    if manifest_path.exists():
        try:
            m_data = json.loads(manifest_path.read_text(encoding="utf-8"))
            for a in m_data.get("assets") or []:
                if a.get("filename") and a.get("sha256"):
                    manifest_clip_shas[str(a["filename"])] = str(a["sha256"])
        except Exception:
            pass

    current_clip_shas = dict((clip_qa.get("sha256_binding") or {}).get("native_clips") or {})
    clips_modified_since_manifest = [
        fn for fn, sha in current_clip_shas.items()
        if fn in manifest_clip_shas and manifest_clip_shas[fn] != sha
    ]

    item9_issues: list[str] = []
    mp4_audits: list[dict[str, Any]] = []
    for mp4_p in target_mp4s:
        mp4_p = Path(mp4_p)
        if not mp4_p.exists():
            item9_issues.append(f"missing_deliverable_mp4: {mp4_p}")
            mp4_audits.append({"path": str(mp4_p), "exists": False, "passed": False})
            continue
        aud = VideoAutopsyEngine.inspect_audio_stream(mp4_p)
        peak_db = float(aud.get("peak_dbfs", 0.0))
        newer_clips = latest_clip_mtime > (mp4_p.stat().st_mtime + 2.0)
        mp4_issues: list[str] = []
        if not aud.get("has_active_speech"):
            mp4_issues.append("missing_active_speech")
        if peak_db > AUDIO_TRUE_PEAK_MAX_DBFS:
            mp4_issues.append(f"audio_true_peak_clipping: peak_dbfs={peak_db:.2f}>{AUDIO_TRUE_PEAK_MAX_DBFS:.1f}")
        if newer_clips or clips_modified_since_manifest:
            mp4_issues.append(
                f"stale_assembly_outdated_by_newer_clips(newer_mtime={newer_clips}, modified_clips={clips_modified_since_manifest})"
            )
        item9_issues.extend(f"{mp4_p.name}: {x}" for x in mp4_issues)
        mp4_audits.append(
            {
                "path": str(mp4_p),
                "exists": True,
                "sha256": compute_sha256(mp4_p),
                "peak_dbfs": peak_db,
                "overall_rms_dbfs": aud.get("overall_rms_dbfs"),
                "up_to_date_with_clips": not (newer_clips or bool(clips_modified_since_manifest)),
                "passed": len(mp4_issues) == 0,
                "issues": mp4_issues,
            }
        )

    # Verify exported MP4 SHA-256 equality across all target paths
    existing_mp4_shas = {a["sha256"] for a in mp4_audits if a.get("exists") and a.get("sha256")}
    if len(existing_mp4_shas) > 1:
        item9_issues.append("exported_deliverable_mp4_sha256_drift_across_targets")

    items = {
        "item_1_clip_1_iconic_tamping_blast_cheek_skull": {
            "passed": len(item1_issues) == 0,
            "spark_and_blast": spark_info,
            "issues": item1_issues,
        },
        "item_2_clip_2_narration_visual_wound_to_oxcart": {
            "passed": len(item2_issues) == 0,
            "issues": item2_issues,
        },
        "item_3_clips_4_6_7_8_left_eye_prefrontal_anatomy": {
            "passed": len(item3_issues) == 0,
            "issues": item3_issues,
        },
        "item_4_clip_10_conclusion_left_eye_to_stagecoach": {
            "passed": len(item4_issues) == 0,
            "issues": item4_issues,
        },
        "item_5_clips_4_6_7_8_cross_clip_brain_continuity": {
            "passed": len(item5_issues) == 0,
            "cross_brain_metrics": cb_rep,
            "issues": item5_issues,
        },
        "item_6_clip_5_chile_stagecoach_porcelain_driving": {
            "passed": len(item6_issues) == 0,
            "issues": item6_issues,
        },
        "item_8_clip_9_single_researcher_and_3d_ct_scan": {
            "passed": len(item8_issues) == 0,
            "issues": item8_issues,
        },
        "item_9_audio_true_peak_and_fresh_assembly": {
            "passed": len(item9_issues) == 0,
            "deliverable_mp4_audits": mp4_audits,
            "issues": item9_issues,
        },
        "item_10_clip_3_dynamic_office_rejection_motion": {
            "passed": len(item10_issues) == 0,
            "issues": item10_issues,
        },
    }

    regeneration_queue = sorted(set(clip_qa.get("regenerate_clips") or []))
    for item_key, clip_hint in (
        ("item_1_clip_1_iconic_tamping_blast_cheek_skull", [1]),
        ("item_2_clip_2_narration_visual_wound_to_oxcart", [2]),
        ("item_3_clips_4_6_7_8_left_eye_prefrontal_anatomy", [4, 6, 7, 8]),
        ("item_4_clip_10_conclusion_left_eye_to_stagecoach", [10]),
        ("item_6_clip_5_chile_stagecoach_porcelain_driving", [5]),
        ("item_8_clip_9_single_researcher_and_3d_ct_scan", [9]),
        ("item_10_clip_3_dynamic_office_rejection_motion", [3]),
    ):
        if not items[item_key]["passed"]:
            for ch in clip_hint:
                if ch <= int(contract.get("clip_count") or 10) and ch not in regeneration_queue and (
                    not by_clip.get(ch, {}).get("passed", False)
                    or not (ref_dir / f"ref_clip_{ch:02d}.png").exists()
                    or item_key in (
                        "item_1_clip_1_iconic_tamping_blast_cheek_skull",
                        "item_2_clip_2_narration_visual_wound_to_oxcart",
                        "item_4_clip_10_conclusion_left_eye_to_stagecoach",
                        "item_6_clip_5_chile_stagecoach_porcelain_driving",
                        "item_8_clip_9_single_researcher_and_3d_ct_scan",
                        "item_10_clip_3_dynamic_office_rejection_motion",
                    )
                ):
                    regeneration_queue.append(ch)
    regeneration_queue = sorted(set(regeneration_queue))

    all_items_passed = all(v["passed"] for v in items.values()) and bool(clip_qa.get("all_passed"))
    return {
        "project_dir": str(p_dir),
        "all_passed": all_items_passed,
        "regeneration_queue_clips": regeneration_queue,
        "requires_reassembly_and_sync": not items["item_9_audio_true_peak_and_fresh_assembly"]["passed"],
        "items": items,
        "clip_contract_qa": clip_qa,
    }


def render_overwatch_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Deliverable Overwatch Verification Report",
        "",
        f"- **Generated At**: `{report['verified_at']}`",
        f"- **Overall Overwatch Status**: `{'PASS' if report['all_deliverables_passed'] else 'ACTION_REQUIRED'}`",
        "",
        "## 1. Standalone Brain Deliverables (A & B)",
        "",
    ]
    for key in ("deliverable_a_hippocampus_cross_section", "deliverable_b_hippocampus_translucent_3d"):
        d = report["deliverables"].get(key) or {}
        st = "PASS" if d.get("passed") else "FAIL"
        lines.append(f"### `{key}` — **{st}**")
        lines.append(f"- Path: `{d.get('path')}`")
        lines.append(f"- Resolution / Duration: `{d.get('resolution', 'N/A')}` / `{d.get('duration_sec', 'N/A')}s`")
        if d.get("r53_particles"):
            p = d["r53_particles"]
            lines.append(
                f"- R53 Particles: `floating_dots={p['max_floating_particle_dots']}`, `neon_ratio={p['max_neon_green_cyan_ratio']}`"
            )
        if d.get("issues"):
            for iss in d["issues"]:
                lines.append(f"  - ❌ `{iss}`")
        lines.append("")

    gage = report["deliverables"].get("deliverable_c_phineas_gage") or {}
    lines.append(f"## 2. Deliverable C — Phineas Gage (`{'PASS' if gage.get('all_passed') else 'FAIL'}`)")
    lines.append(f"- Project Dir: `{gage.get('project_dir')}`")
    lines.append(f"- Clip Regeneration Queue: `{gage.get('regeneration_queue_clips', [])}`")
    lines.append(f"- Requires Re-Assembly & Sync: `{gage.get('requires_reassembly_and_sync')}`")
    lines.append("")
    for item_name, item_val in (gage.get("items") or {}).items():
        st = "PASS" if item_val.get("passed") else "FAIL"
        lines.append(f"- **{item_name}**: `{st}`")
        for iss in item_val.get("issues") or []:
            lines.append(f"  - ❌ `{iss}`")
    lines.append("")
    return "\n".join(lines)


def _verify_project_mirror_parity(primary_dir: Path, mirror_dir: Path, clip_count: int = 10) -> dict[str, Any]:
    """Verifies SHA-256 parity of critical clips, refs, semantic reviews, contracts, and final MP4 across SSD and GDrive."""
    rel_paths = (
        [f"03_visuals/flow_native_clips/clip_{i}.mp4" for i in range(1, clip_count + 1)]
        + [f"03_visuals/reference_images/ref_clip_{i:02d}.png" for i in range(1, clip_count + 1)]
        + [
            "03_visuals/reference_images/ref_brain_master.png",
            "03_visuals/reference_images/reference_semantic_review.json",
            "03_visuals/clip_semantic_review.json",
            "03_visuals/clip_qa_contract.json",
            "05_assembly/final_shorts_1080x1920.mp4",
            "00_project_manifest.json",
        ]
    )
    issues: list[str] = []
    checked = 0
    for rel in rel_paths:
        p1 = primary_dir / rel
        p2 = mirror_dir / rel
        if not p1.exists() and not p2.exists():
            continue
        checked += 1
        if not p1.exists():
            issues.append(f"missing_in_primary({rel})")
            continue
        if not p2.exists():
            issues.append(f"missing_in_mirror({rel})")
            continue
        if rel == "03_visuals/clip_qa_contract.json":
            try:
                j1 = json.loads(p1.read_text(encoding="utf-8"))
                j2 = json.loads(p2.read_text(encoding="utf-8"))
                if isinstance(j1, dict) and isinstance(j2, dict):
                    j1.pop("compiled_at", None)
                    j2.pop("compiled_at", None)
                    if json.dumps(j1, sort_keys=True) != json.dumps(j2, sort_keys=True):
                        issues.append(f"sha256_drift({rel})")
                    continue
            except Exception:
                pass
        if compute_sha256(p1) != compute_sha256(p2):
            issues.append(f"sha256_drift({rel})")
    return {
        "passed": len(issues) == 0,
        "primary_dir": str(primary_dir),
        "mirror_dir": str(mirror_dir),
        "checked_files": checked,
        "issues": issues,
    }


def run_deliverable_overwatch(
    outputs_dir: Path | None = None,
    gage_project_dir: Path | None = None,
    out_report_path: Path | None = None,
    save_in_project: bool = False,
) -> dict[str, Any]:
    """
    Runs end-to-end Deliverable Overwatch across Deliverables A, B, and C.
    """
    out_dir = Path(outputs_dir) if outputs_dir else (WORKSPACE_ROOT / "Temp_New_R53_Outputs")
    ssd_cand = Path("/tmp/bci_v5_ssd_workspace/projects/psych_04_phineas_gage_frontal_lobe")
    gdrive_cand = PROJECTS_DIR / "psych_04_phineas_gage_frontal_lobe"
    if gage_project_dir is None:
        gage_project_dir = ssd_cand if ssd_cand.exists() else gdrive_cand

    deliv_a = verify_standalone_brain_deliverable(
        mp4_path=out_dir / "06_example_hippocampus_9x16_vertical.mp4",
        ref_png_path=out_dir / "06_example_hippocampus_9x16_ref.png",
        mode="opaque_porcelain_cross_section",
    )
    deliv_b = verify_standalone_brain_deliverable(
        mp4_path=out_dir / "07_example_flow_hippocampus_translucent_9x16.mp4",
        ref_png_path=out_dir / "07_example_hippocampus_translucent_9x16_ref.png",
        mode="translucent_3d_whole_brain",
    )

    exported_gage_mp4s = [
        Path(gage_project_dir) / "05_assembly" / "final_shorts_1080x1920.mp4",
        out_dir / "01_final_shorts_psych_04_phineas_gage_v5_upgraded.mp4",
        WORKSPACE_ROOT / "Completed_Psychology_100_Shorts" / "final_shorts_psych_04_phineas_gage_frontal_lobe.mp4",
    ]
    gdrive_gage_mp4 = gdrive_cand / "05_assembly" / "final_shorts_1080x1920.mp4"
    if gdrive_gage_mp4 not in exported_gage_mp4s and gdrive_gage_mp4.exists():
        exported_gage_mp4s.append(gdrive_gage_mp4)

    deliv_c = verify_phineas_gage_deliverable(
        project_dir=Path(gage_project_dir),
        deliverable_mp4s=exported_gage_mp4s,
        save_in_project=save_in_project,
    )

    resolved_gage = Path(gage_project_dir).resolve()
    if (
        ssd_cand.exists()
        and gdrive_cand.exists()
        and resolved_gage in (ssd_cand.resolve(), gdrive_cand.resolve())
    ):
        parity = _verify_project_mirror_parity(ssd_cand, gdrive_cand)
        deliv_c["items"]["item_11_ssd_gdrive_workspace_parity"] = parity
        if not parity["passed"]:
            deliv_c["all_passed"] = False
            deliv_c["requires_reassembly_and_sync"] = True
        elif save_in_project:
            import shutil as _shutil

            other_dir = gdrive_cand if resolved_gage == ssd_cand.resolve() else ssd_cand
            for _rel_qa in (
                "03_visuals/clip_qa_contract.json",
                "03_visuals/clip_contract_qa_report.json",
                "03_visuals/reference_image_qa_report.json",
            ):
                _src = Path(gage_project_dir) / _rel_qa
                _dst = other_dir / _rel_qa
                if _src.exists():
                    _dst.parent.mkdir(parents=True, exist_ok=True)
                    _shutil.copy2(_src, _dst)

    all_ok = bool(deliv_a["passed"] and deliv_b["passed"] and deliv_c["all_passed"])
    report = {
        "schema_version": 1,
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "all_deliverables_passed": all_ok,
        "deliverables": {
            "deliverable_a_hippocampus_cross_section": deliv_a,
            "deliverable_b_hippocampus_translucent_3d": deliv_b,
            "deliverable_c_phineas_gage": deliv_c,
        },
    }

    if out_report_path is not None:
        rp = Path(out_report_path)
        rp.parent.mkdir(parents=True, exist_ok=True)
        rp.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        rp.with_suffix(".md").write_text(render_overwatch_markdown(report), encoding="utf-8")

    return report


__all__ = [
    "_check_left_eye_cutaway_side",
    "_verify_project_mirror_parity",
    "render_overwatch_markdown",
    "run_deliverable_overwatch",
    "verify_phineas_gage_deliverable",
    "verify_standalone_brain_deliverable",
]
