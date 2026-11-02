"""
ALL ABOUT BRAIN — Rule R64 Post-Hoc Clip-by-Clip Expressive Clarity Verification QA
===================================================================================
Inspects BOTH the finished assembled Short (`05_assembly/final_shorts_1080x1920.mp4`) AND each
underlying clip (`03_visuals/flow_native_clips/clip_*.mp4` + `05_assembly/edit_decision_list.json`)
after assembly to verify whether what each clip/cut intends to express is visually clear, legible,
temporally coherent, and aligned with its spoken narration and visual grammar.

Outputs (saved under `05_assembly/`):
  - `posthoc_semantic_qa_report.json`: Per-cut & per-source-clip expressive clarity scores (`0..100`),
    5-axis sub-scores, defect diagnostics, source-vs-assembly root-cause attribution, Act-level
    trajectory, and `regenerate_clip_indices` / `shift_window_recommendations`.
  - `posthoc_viewer_strips/sheet_01.jpg..sheet_NN.jpg`: Multi-cut visual review sheets (`6` cuts per
    sheet, `[Start | Mid | End]` frames + spoken sentence + intended scene + sub-score bars).
  - `posthoc_semantic_review.json` (optional `--init-review` / `--require-review`): SHA-256-bound
    per-cut semantic sign-off ledger enforcing anti-boilerplate `observed_visual_summary` rules.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import re
import shutil
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from pipeline.config import (
    DIORAMA_V7_LUMA_RANGE,
    PORCELAIN_V7_BRAIN_MARGIN_SAT_MAX,
    PORCELAIN_V7_HUMAN_SKIN_MAX,
    PORCELAIN_V7_LUMA_RANGE,
    PORCELAIN_V7_NEON_GREEN_SPILL_MAX,
    POSTHOC_ANALOGY_SYNC_TOLERANCE_SEC,
    POSTHOC_BRAIN_HIGHLIGHT_MIN_CHROMA,
    POSTHOC_CUTS_PER_VIEWER_SHEET,
    POSTHOC_LOCKED_TRIPOD_MIN_P95_DIFF,
    POSTHOC_MAX_IDENTICAL_REVIEW_NOTES,
    POSTHOC_MAX_STEP_HIST_JUMP,
    POSTHOC_MIN_CUT_CLARITY_SCORE,
    POSTHOC_MIN_EDGE_DENSITY,
    POSTHOC_MIN_EPISODE_MEAN_CLARITY_SCORE,
    POSTHOC_MIN_FG_BG_CONTRAST_DE,
    POSTHOC_MIN_MOVING_CAM_DIFF,
    POSTHOC_MIN_REVIEW_NOTE_CHARS,
    POSTHOC_MIN_SHARPNESS_LAPLACIAN,
    POSTHOC_SEMANTIC_QA_REPORT_FILENAME,
    POSTHOC_SEMANTIC_REVIEW_FILENAME,
    POSTHOC_SPLIT_PANE_MIN_DIFF,
    POSTHOC_VIEWER_STRIPS_DIRNAME,
    PROJECTS_DIR,
    PROMPT_SCHEMA_VERSION_V7,
    WORKSPACE_ROOT,
    is_diorama_profile,
    is_diorama_v7_plan,
    is_porcelain_v7_plan,
    resolve_diorama_v7_style_profile,
)
from pipeline.depiction_rules import normalize_porcelain_v7_brain_mode, normalize_porcelain_v7_grammar
from pipeline.dynamic_episode_qa import (
    _asr_word_timeline_from_mp4,
    _non_subtitle_scene_rois,
    _parse_ass_ts_sec,
    compile_episode_qa_contract,
    compute_green_turf_ratio,
)
_ORIG_ASR_WORD_TIMELINE_FN = _asr_word_timeline_from_mp4
from pipeline.flow_diorama_sharded_worker import (
    _max_horizontal_plaque_glyph_run,
    compute_brain_margin_saturation,
    compute_neon_green_spill_ratio,
    compute_porcelain_flesh_leak_ratio,
    detect_escher_dual_edge_closeup,
    detect_transient_top_intrusion_pov,
)
from pipeline.storage import numeric_clip_sort_key

_MOVING_CAMERA_KEYWORDS = (
    "pan_",
    "pan ",
    "tilt_",
    "tilt ",
    "push",
    "pull",
    "dolly",
    "orbit",
    "crane",
    "swoop",
    "track",
    "ascent",
    "zoom",
    "glide",
    "sweep",
)

_HIGHLIGHT_SIGNAL_KEYWORDS = (
    "lesion",
    "damage",
    "crimson",
    "coral",
    "amber",
    "cyan",
    "tract",
    "pathway",
    "glow",
    "trajectory",
    "tunnel",
    "cavity",
    "severed",
)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
    except Exception:  # noqa: BLE001
        pass
    return {}


def _sha256_file(path: Path) -> str:
    from pipeline.media_cache import fast_file_sha256

    return fast_file_sha256(path)


def _resolve_project_dir(project_id_or_dir: str | Path) -> Path:
    cand = Path(str(project_id_or_dir))
    if cand.exists() and cand.is_dir():
        return cand.resolve()
    p_dir = (Path(PROJECTS_DIR) / str(project_id_or_dir)).resolve()
    if p_dir.exists():
        return p_dir
    raise FileNotFoundError(f"Project directory not found: {project_id_or_dir}")


def resolve_project_final_mp4(project_dir: Path) -> Path:
    """Resolves the assembled final MP4 inside `05_assembly/`, project root, or `Completed_Psychology_100_Shorts/`."""
    candidates = (
        project_dir / "05_assembly" / "final_shorts_1080x1920.mp4",
        project_dir / f"final_shorts_{project_dir.name}.mp4",
        Path(WORKSPACE_ROOT) / "Completed_Psychology_100_Shorts" / f"final_shorts_{project_dir.name}.mp4",
    )
    for c in candidates:
        if c.exists() and c.is_file() and c.stat().st_size > 10_000:
            return c
    raise FileNotFoundError(
        f"Assembled final MP4 not found for {project_dir.name} (checked 05_assembly/ and Completed_Psychology_100_Shorts/)"
    )


def _extract_sentences_from_script(script_doc: dict[str, Any]) -> list[str]:
    if isinstance(script_doc.get("sentences"), list) and script_doc["sentences"]:
        return [str(s).strip() for s in script_doc["sentences"] if str(s).strip()]
    if isinstance(script_doc.get("acts"), list) and script_doc["acts"]:
        return [
            str(s).strip()
            for act in script_doc["acts"]
            if isinstance(act, dict)
            for s in (act.get("sentences") or [])
            if str(s).strip()
        ]
    if isinstance(script_doc.get("clip_narrations"), list):
        return [str(s).strip() for s in script_doc["clip_narrations"] if str(s).strip()]
    return []


def _is_moving_camera(camera_move: str) -> bool:
    cm = str(camera_move or "").strip().lower()
    if not cm or "locked" in cm or "static" in cm or "tripod" in cm:
        return False
    return any(k in cm for k in _MOVING_CAMERA_KEYWORDS)


def _probe_video_duration_and_fps(mp4_path: Path) -> tuple[float, float, int]:
    try:
        if not mp4_path.exists() or mp4_path.stat().st_size < 1024:
            return 0.0, 0.0, 0
    except OSError:
        return 0.0, 0.0, 0
    cap = cv2.VideoCapture(str(mp4_path))
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 24.0)
    fc = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    cap.release()
    dur = (fc / fps) if (fps > 0 and fc > 0) else 0.0
    return dur, fps, fc


def _parse_ffmpeg_concat_list(concat_path: Path) -> list[dict[str, Any]]:
    """
    Parses ffmpeg concat demuxer `05_assembly/concat_list.txt` (`file` / `inpoint` / `outpoint` / `duration`)
    into ordered per-cut source windows so classic v4/v5 Shorts align with true cut boundaries.
    """
    if not concat_path.exists():
        return []
    entries: list[dict[str, Any]] = []
    cur: dict[str, Any] | None = None
    try:
        lines = concat_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    for raw_ln in lines:
        ln = raw_ln.strip()
        if not ln or ln.startswith("#"):
            continue
        if ln.startswith("file "):
            if cur is not None:
                entries.append(cur)
            raw_p = ln[5:].strip().strip("'").strip('"')
            m_num = re.search(r"clip_(\d+)", Path(raw_p).stem, flags=re.IGNORECASE)
            cur = {
                "file_path": raw_p,
                "clip_index": int(m_num.group(1)) if m_num else (len(entries) + 1),
                "inpoint": 0.0,
                "outpoint": None,
                "duration": None,
            }
        elif cur is not None and ln.startswith("inpoint "):
            try:
                cur["inpoint"] = max(0.0, float(ln.split()[1]))
            except (IndexError, ValueError):
                pass
        elif cur is not None and ln.startswith("outpoint "):
            try:
                cur["outpoint"] = max(0.0, float(ln.split()[1]))
            except (IndexError, ValueError):
                pass
        elif cur is not None and ln.startswith("duration "):
            try:
                cur["duration"] = max(0.0, float(ln.split()[1]))
            except (IndexError, ValueError):
                pass
    if cur is not None:
        entries.append(cur)
    return entries


def extract_cut_intent_specs(
    project_dir: Path,
    final_mp4_duration_sec: float | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """
    Compiles unified per-cut intent specifications for BOTH:
      1. Schema v6/v7 `neuro_diorama` (`05_assembly/edit_decision_list.json`), and
      2. Classic v4/v5 5-10 clip Shorts (`05_assembly/concat_list.txt` or `flow_native_clips/clip_*.mp4`).
    """
    script_doc = _read_json(project_dir / "02_script" / "script.json") or _read_json(project_dir / "script.json")
    visual_plan = _read_json(project_dir / "03_visuals" / "visual_plan.json") or _read_json(project_dir / "visual_plan.json")
    prompts_doc = _read_json(project_dir / "03_visuals" / "flow_all_in_one_prompts.json")
    edl = _read_json(project_dir / "05_assembly" / "edit_decision_list.json")
    contract = _read_json(project_dir / "03_visuals" / "episode_qa_contract.json")

    prompts_clips = prompts_doc.get("clips") if isinstance(prompts_doc.get("clips"), list) else []
    plan_clips = visual_plan.get("clips") if isinstance(visual_plan.get("clips"), list) else []

    sentences = _extract_sentences_from_script(script_doc)
    if not sentences and prompts_clips:
        sentences = [
            str(c.get("spoken_narration") or "").strip()
            for c in prompts_clips
            if isinstance(c, dict) and str(c.get("spoken_narration") or "").strip()
        ]
    is_diorama = is_diorama_profile(visual_plan) or is_diorama_profile(script_doc) or bool(edl.get("cuts"))
    is_v7 = is_diorama_v7_plan(visual_plan) or is_diorama_v7_plan(script_doc) or int(edl.get("schema") or 0) >= PROMPT_SCHEMA_VERSION_V7

    if is_diorama and not contract and sentences and (prompts_clips or plan_clips):
        try:
            from pipeline.flow_prompt_builder import build_flow_prompts

            built_clips = prompts_clips if prompts_clips else build_flow_prompts(visual_plan, sentences)
            contract = compile_episode_qa_contract(visual_plan, sentences, built_clips, script_doc=script_doc)
        except Exception:  # noqa: BLE001
            contract = {}

    prompt_by_num: dict[int, dict[str, Any]] = {}
    for idx, c in enumerate(prompts_clips, start=1):
        if isinstance(c, dict):
            c_no = int(c.get("clip_number") or idx)
            prompt_by_num[c_no] = c

    plan_by_num: dict[int, dict[str, Any]] = {}
    for idx, c in enumerate(plan_clips, start=1):
        if isinstance(c, dict):
            c_no = int(c.get("clip_number") or idx)
            plan_by_num[c_no] = c

    analogy_by_sent: dict[int, list[dict[str, Any]]] = {}
    for a_lock in (contract.get("analogy_locks") or []):
        if isinstance(a_lock, dict) and a_lock.get("sentence_index") is not None:
            analogy_by_sent.setdefault(int(a_lock["sentence_index"]), []).append(a_lock)

    anatomy_by_sent: dict[int, list[dict[str, Any]]] = {}
    for an_lock in (contract.get("anatomy_locks") or []):
        if isinstance(an_lock, dict) and an_lock.get("sentence_index") is not None:
            anatomy_by_sent.setdefault(int(an_lock["sentence_index"]), []).append(an_lock)

    cast_clip_nums = {
        int(x["clip_number"])
        for x in (contract.get("cast_clip_locks") or [])
        if isinstance(x, dict) and x.get("clip_number") is not None
    }

    is_porcelain = bool(is_v7 and is_porcelain_v7_plan(visual_plan, edl, prompts_doc, script_doc))
    cuts_out: list[dict[str, Any]] = []
    if isinstance(edl.get("cuts"), list) and edl["cuts"]:
        for c in edl["cuts"]:
            cut_idx = int(c.get("cut_index") or (len(cuts_out) + 1))
            clip_idx = int(c.get("clip_index") or cut_idx)
            p_meta = prompt_by_num.get(clip_idx, {})
            v_meta = plan_by_num.get(clip_idx, {})
            if isinstance(c.get("sentence_indices"), list):
                sent_nums = [int(k) for k in c["sentence_indices"] if 1 <= int(k) <= len(sentences)]
            else:
                s_start_i = int(c.get("sentence_index") or v_meta.get("sentence_index") or 0)
                s_end_i = int(c.get("end_sentence_index") or v_meta.get("end_sentence_index") or s_start_i)
                sent_nums = [k for k in range(s_start_i, max(s_start_i, s_end_i) + 1) if 1 <= k <= len(sentences)]
            spoken_text = " ".join(sentences[k - 1] for k in sent_nums) if sent_nums else str(c.get("narration") or "")

            grammar = str(c.get("grammar") or p_meta.get("grammar") or v_meta.get("grammar") or "unknown")
            camera_move = str(
                c.get("camera_move")
                or p_meta.get("camera_move")
                or v_meta.get("camera_move")
                or v_meta.get("camera")
                or "locked_tripod"
            )
            scene_text = str(
                p_meta.get("scene")
                or v_meta.get("scene")
                or " ".join(
                    str(v_meta.get(k) or "")
                    for k in ("environment", "cast", "action", "consequence", "analogy_object", "region")
                    if v_meta.get(k)
                )
            ).strip()
            prompt_text = str(p_meta.get("prompt") or "")
            bound_analogies = [al for sn in sent_nums for al in analogy_by_sent.get(sn, [])]
            bound_anatomy = [an for sn in sent_nums for an in anatomy_by_sent.get(sn, [])]
            is_outro = (
                bool(c.get("outro_sky_card"))
                or str(c.get("mode") or "") == "outro"
                or str(v_meta.get("cut_role") or "") == "outro"
            )
            if is_porcelain and normalize_porcelain_v7_grammar(grammar) == "porcelain_living_brain":
                if c.get("brain_mode") or c.get("render_mode"):
                    resolved_bmode = normalize_porcelain_v7_brain_mode(
                        c.get("brain_mode"),
                        render_mode=c.get("render_mode"),
                        scene_text=scene_text,
                    )
                elif p_meta.get("brain_mode") or p_meta.get("render_mode"):
                    p_norm = normalize_porcelain_v7_brain_mode(
                        p_meta.get("brain_mode"),
                        render_mode=p_meta.get("render_mode"),
                    )
                    if p_norm == "cortical_vascular_whole" and not v_meta.get("brain_mode"):
                        resolved_bmode = normalize_porcelain_v7_brain_mode(
                            None,
                            render_mode=v_meta.get("render_mode"),
                            scene_text=scene_text,
                        )
                    else:
                        resolved_bmode = p_norm
                else:
                    resolved_bmode = normalize_porcelain_v7_brain_mode(
                        v_meta.get("brain_mode"),
                        render_mode=v_meta.get("render_mode"),
                        scene_text=scene_text,
                    )
            else:
                resolved_bmode = str(
                    c.get("brain_mode")
                    or p_meta.get("brain_mode")
                    or v_meta.get("brain_mode")
                    or v_meta.get("render_mode")
                    or ""
                )

            cuts_out.append(
                {
                    "cut_index": cut_idx,
                    "clip_index": clip_idx,
                    "secondary_clip_index": (int(c["secondary_clip_index"]) if c.get("secondary_clip_index") is not None else None),
                    "act": int(c.get("act") or v_meta.get("act") or 1),
                    "mode": str(c.get("mode") or "single"),
                    "grammar": grammar,
                    "camera_move": camera_move,
                    "location_id": str(c.get("location_id") or v_meta.get("location_id") or ""),
                    "brain_mode": resolved_bmode,
                    "brain_region": str(c.get("brain_region") or v_meta.get("brain_region") or p_meta.get("brain_region") or ""),
                    "is_outro": is_outro,
                    "out_start_sec": round(float(c.get("out_start_sec") or 0.0), 3),
                    "out_end_sec": round(float(c.get("out_end_sec") or 0.0), 3),
                    "duration_sec": round(float(c.get("duration_sec") or 0.0), 3),
                    "src_start_sec": round(float(c.get("src_start_sec") or 0.0), 3),
                    "src_end_sec": round(float(c.get("src_end_sec") or 0.0), 3),
                    "sentence_indices": sent_nums,
                    "spoken_narration": spoken_text,
                    "intended_scene": scene_text,
                    "prompt": prompt_text,
                    "analogy_locks": bound_analogies,
                    "anatomy_locks": bound_anatomy,
                    "cast_locked": (clip_idx in cast_clip_nums),
                }
            )
    else:
        # Classic v4/v5 5-10 clip Short: prefer exact cut boundaries from 05_assembly/concat_list.txt
        clips_dir = project_dir / "03_visuals" / "flow_native_clips"
        clip_files = sorted(clips_dir.glob("clip_*.mp4"), key=numeric_clip_sort_key)
        concat_entries = _parse_ffmpeg_concat_list(project_dir / "05_assembly" / "concat_list.txt")

        source_windows: list[tuple[int, float, float]] = []
        if concat_entries:
            for idx_e, ent in enumerate(concat_entries, start=1):
                c_no = int(ent.get("clip_index") or idx_e)
                in_s = float(ent.get("inpoint") or 0.0)
                if ent.get("outpoint") is not None and float(ent["outpoint"]) > in_s + 0.05:
                    out_s_src = float(ent["outpoint"])
                elif ent.get("duration") is not None and float(ent["duration"]) > 0.05:
                    out_s_src = in_s + float(ent["duration"])
                else:
                    cand_cf = Path(str(ent.get("file_path") or ""))
                    if not cand_cf.exists():
                        cand_cf = clips_dir / f"clip_{c_no}.mp4"
                    d_i, _, _ = _probe_video_duration_and_fps(cand_cf)
                    out_s_src = in_s + max(1.0, d_i if d_i > 0 else 6.0)
                source_windows.append((c_no, in_s, out_s_src))
        else:
            n_clips = max(1, len(clip_files) or len(prompts_clips) or len(sentences))
            for idx in range(1, n_clips + 1):
                cf = clips_dir / f"clip_{idx}.mp4"
                if cf.exists():
                    d_i, _, _ = _probe_video_duration_and_fps(cf)
                    source_windows.append((idx, 0.0, max(1.0, d_i if d_i > 0 else 6.0)))
                else:
                    source_windows.append((idx, 0.0, 6.0))

        n_cuts = len(source_windows)
        raw_durs = [max(0.1, s_e - s_s) for _, s_s, s_e in source_windows]
        tot_raw = max(1e-6, sum(raw_durs))
        tot_out = float(final_mp4_duration_sec or tot_raw)
        cursor = 0.0
        shots_map = visual_plan.get("shots") if isinstance(visual_plan.get("shots"), dict) else {}
        scenes_map = visual_plan.get("scenes") if isinstance(visual_plan.get("scenes"), dict) else {}
        for cut_pos, (c_no, src_s, src_e) in enumerate(source_windows, start=1):
            seg_dur = tot_out * (raw_durs[cut_pos - 1] / tot_raw)
            out_s = round(cursor, 3)
            out_e = round(tot_out if cut_pos == n_cuts else (cursor + seg_dur), 3)
            cursor += seg_dur
            p_meta = prompt_by_num.get(c_no, {})
            role = str(p_meta.get("role") or f"clip_{c_no}")
            shot_meta = shots_map.get(role) if isinstance(shots_map.get(role), dict) else {}
            setting = str(p_meta.get("setting") or shot_meta.get("setting") or "real_environment")
            cam = str(p_meta.get("camera_move") or shot_meta.get("camera") or "slow_push_in")
            scene_txt = str(p_meta.get("scene") or scenes_map.get(role) or shot_meta.get("action") or "")
            narr = str(
                p_meta.get("spoken_narration")
                or (sentences[c_no - 1] if c_no - 1 < len(sentences) else "")
            ).strip()
            cuts_out.append(
                {
                    "cut_index": cut_pos,
                    "clip_index": c_no,
                    "secondary_clip_index": None,
                    "act": min(6, ((cut_pos - 1) * 6) // max(1, n_cuts) + 1),
                    "mode": "single",
                    "grammar": setting,
                    "camera_move": cam,
                    "location_id": str(shot_meta.get("scene_id") or role),
                    "brain_mode": "",
                    "brain_region": str(p_meta.get("brain_region") or ""),
                    "is_outro": False,
                    "out_start_sec": out_s,
                    "out_end_sec": out_e,
                    "duration_sec": round(max(0.1, out_e - out_s), 3),
                    "src_start_sec": round(src_s, 3),
                    "src_end_sec": round(src_e, 3),
                    "sentence_indices": ([c_no] if c_no <= len(sentences) else []),
                    "spoken_narration": narr,
                    "intended_scene": scene_txt,
                    "prompt": str(p_meta.get("prompt") or ""),
                    "analogy_locks": [],
                    "anatomy_locks": [],
                    "cast_locked": (setting != "brain_void"),
                }
            )

    context = {
        "project_id": project_dir.name,
        "schema_version": (PROMPT_SCHEMA_VERSION_V7 if is_v7 else (6 if is_diorama else int(prompts_doc.get("schema_version") or 5))),
        "style_profile": (
            resolve_diorama_v7_style_profile(visual_plan, edl, prompts_doc, script_doc)
            if is_v7
            else str(visual_plan.get("style_profile") or script_doc.get("style_profile") or ("neuro_diorama" if is_diorama else "classic"))
        ),
        "is_diorama": is_diorama,
        "is_v7": is_v7,
        "is_porcelain_v7": is_porcelain,
        "dossier": str(visual_plan.get("dossier") or script_doc.get("dossier") or ""),
        "sentences": sentences,
        "edl": edl,
        "contract": contract,
    }
    return cuts_out, context


def _concat_clean_roi_360(
    frame_bgr: np.ndarray,
    has_top_overlay: bool = False,
    is_outro: bool = False,
) -> np.ndarray:
    """Concatenates non-subtitle clean scene ROIs and normalizes width to 360px for scale-invariant CV metrics."""
    rois = _non_subtitle_scene_rois(frame_bgr, has_top_overlay=has_top_overlay, is_outro=is_outro)
    if not rois:
        h, w = frame_bgr.shape[:2]
        patch = frame_bgr[int(h * 0.20) : int(h * 0.58), int(w * 0.04) : int(w * 0.96)]
    elif len(rois) == 1:
        patch = rois[0]
    else:
        min_w = min(r.shape[1] for r in rois)
        patch = np.vstack([r[:, :min_w] for r in rois])
    ph, pw = patch.shape[:2]
    if pw <= 0 or ph <= 0:
        return np.zeros((320, 360, 3), dtype=np.uint8)
    target_w = 360
    target_h = max(64, int(round(ph * (target_w / float(pw)))))
    return cv2.resize(patch, (target_w, target_h), interpolation=cv2.INTER_AREA)


def _compute_fg_bg_contrast_de(clean_bgr_360: np.ndarray) -> float:
    """
    Computes CIE LAB perceptual contrast `deltaE` separating foreground subject articulation
    from background/periphery on the clean 360px-wide scene patch.
    Combines center-vs-border separation with 5x5 block 90th-vs-median spatial separation
    so compact specimens and dual-pane subjects are measured accurately while blank/washed-out cuts fail.
    """
    lab = cv2.cvtColor(clean_bgr_360, cv2.COLOR_BGR2LAB).astype(np.float32)
    h, w = lab.shape[:2]
    cy0, cy1 = int(h * 0.22), int(h * 0.78)
    cx0, cx1 = int(w * 0.22), int(w * 0.78)
    core = lab[cy0:cy1, cx0:cx1]
    mask_border = np.ones((h, w), dtype=bool)
    mask_border[cy0:cy1, cx0:cx1] = False
    border = lab[mask_border]
    core_border_de = 0.0
    if core.size >= 30 and border.size >= 30:
        c_mean = np.mean(core.reshape(-1, 3), axis=0)
        b_mean = np.mean(border.reshape(-1, 3), axis=0)
        core_border_de = float(np.linalg.norm(c_mean - b_mean))

    grid_means: list[np.ndarray] = []
    gh, gw = max(1, h // 5), max(1, w // 5)
    for gy in range(5):
        for gx in range(5):
            cell = lab[gy * gh : min(h, (gy + 1) * gh), gx * gw : min(w, (gx + 1) * gw)]
            if cell.size >= 12:
                grid_means.append(np.mean(cell.reshape(-1, 3), axis=0))
    spatial_de = 0.0
    if len(grid_means) >= 4:
        gm = np.stack(grid_means, axis=0)
        med = np.median(gm, axis=0)
        dists = np.linalg.norm(gm - med, axis=1)
        spatial_de = float(np.percentile(dists, 90))
    return round(max(core_border_de, spatial_de), 2)


def _compute_hist_step_jump(bgr_a: np.ndarray, bgr_b: np.ndarray) -> float:
    hsv_a = cv2.cvtColor(bgr_a, cv2.COLOR_BGR2HSV)
    hsv_b = cv2.cvtColor(bgr_b, cv2.COLOR_BGR2HSV)
    ha = cv2.calcHist([hsv_a], [0, 1], None, [18, 16], [0, 180, 0, 256])
    hb = cv2.calcHist([hsv_b], [0, 1], None, [18, 16], [0, 180, 0, 256])
    cv2.normalize(ha, ha, alpha=1.0, beta=0.0, norm_type=cv2.NORM_L1)
    cv2.normalize(hb, hb, alpha=1.0, beta=0.0, norm_type=cv2.NORM_L1)
    return round(float(cv2.compareHist(ha, hb, cv2.HISTCMP_BHATTACHARYYA)), 4)


def _compute_brain_highlight_chroma(clean_bgr_360: np.ndarray) -> float:
    lab = cv2.cvtColor(clean_bgr_360, cv2.COLOR_BGR2LAB).astype(np.float32)
    chroma = np.hypot(lab[:, :, 1] - 128.0, lab[:, :, 2] - 128.0)
    return round(float(np.percentile(chroma, 99.5) - np.percentile(chroma, 50)), 2)


def _detect_nonfrontal_brain_localization_defect(
    clean_bgr_360: np.ndarray,
    brain_region: str,
    mode: str,
) -> str | None:
    """
    Detects unintended anterior-frontal/cingulate reference tint bleed or anterior-only misplaced
    illumination on single-pane Schema v7 `lowpoly_matte_brain` cuts targeting non-frontal structures.
    """
    if str(mode or "").startswith("split") or not brain_region:
        return None
    reg = brain_region.strip().lower()
    if any(k in reg for k in ("prefrontal", "frontal", "cingulate", "broca", "motor")):
        return None
    lab = cv2.cvtColor(clean_bgr_360, cv2.COLOR_BGR2LAB).astype(np.float32)
    L, a, b = lab[:, :, 0], lab[:, :, 1], lab[:, :, 2]
    h, w = L.shape
    if h < 16 or w < 16:
        return None
    pink_ex = (a - 128.0) - 0.23 * np.maximum(0.0, b - 128.0)
    coral = (L >= 115.0) & (pink_ex > 6.5) & (a > 138.0)
    slate = (L >= 95.0) & (L <= 215.0) & (b < 123.5)
    ant_upper = np.zeros((h, w), dtype=bool)
    ant_upper[int(h * 0.12) : int(h * 0.45), int(w * 0.06) : int(w * 0.36)] = True
    coral_ant_ratio = float((coral & ant_upper).sum()) / float(h * w)
    slate_ant_ratio = float((slate & ant_upper).sum()) / float(h * w)
    if coral_ant_ratio >= 0.008:
        return f"unintended_prefrontal_coral_bleed(region={reg},ant_coral={coral_ant_ratio:.4f})"
    if slate_ant_ratio >= 0.010 and "temporal" not in reg:
        return f"unintended_anterior_cingulate_slate_bleed(region={reg},ant_slate={slate_ant_ratio:.4f})"
    if any(k in reg for k in ("cerebellum", "occipital", "brainstem")):
        bzone = np.zeros((h, w), dtype=bool)
        bzone[int(h * 0.14) : int(h * 0.66), int(w * 0.08) : int(w * 0.92)] = True
        d_iv = np.hypot(a - 131.0, b - 146.0)
        sal = bzone & (L >= 90.0) & (L <= 222.0) & (d_iv >= 18.0)
        if int(sal.sum()) >= 60:
            med_x = float(np.median(np.where(sal)[1] / float(w)))
            if med_x < 0.35:
                return f"misplaced_anterior_highlight_for_posterior_region(region={reg},med_x={med_x:.2f})"
    return None


def _compute_optical_flow_summary(clean_a: np.ndarray, clean_b: np.ndarray) -> tuple[float, float]:
    ga = cv2.resize(cv2.cvtColor(clean_a, cv2.COLOR_BGR2GRAY), (160, 160), interpolation=cv2.INTER_AREA)
    gb = cv2.resize(cv2.cvtColor(clean_b, cv2.COLOR_BGR2GRAY), (160, 160), interpolation=cv2.INTER_AREA)
    flow = cv2.calcOpticalFlowFarneback(ga, gb, None, 0.5, 2, 13, 2, 5, 1.1, 0)
    dx = round(float(np.median(flow[..., 0])), 3)
    dy = round(float(np.median(flow[..., 1])), 3)
    return dx, dy


def _inspect_source_clip_windows(clip_path: Path) -> dict[str, Any]:
    """Evaluates a native source clip across 4 candidate windows to distinguish bad Flow clips vs sub-optimal EDL slicing."""
    if not clip_path.exists():
        return {
            "exists": False,
            "corrupted": False,
            "sharpness": 0.0,
            "motion_p95": 0.0,
            "motion_p95_raw": 0.0,
            "focal_edges": 0.0,
            "best_window_sec": None,
            "defects": [],
        }
    try:
        fsize = clip_path.stat().st_size
    except OSError:
        fsize = 0
    if fsize < 512:
        return {
            "exists": True,
            "corrupted": True,
            "duration_sec": 0.0,
            "sharpness": 0.0,
            "motion_p95": 0.0,
            "motion_p95_raw": 0.0,
            "focal_edges": 0.0,
            "best_window_sec": None,
            "defects": ["corrupted_or_unreadable_source_clip"],
        }
    from pipeline.media_cache import cached_by_clip_stat

    def _probe_src_windows(local_clip: Path) -> dict[str, Any]:
        cap = cv2.VideoCapture(str(local_clip))
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 24.0)
        fc = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        dur = (fc / fps) if (fps > 0 and fc > 0) else 0.0
        if dur < 1.0 or fc < 4:
            cap.release()
            return {
                "exists": True,
                "corrupted": True,
                "duration_sec": round(dur, 2),
                "sharpness": 0.0,
                "motion_p95": 0.0,
                "motion_p95_raw": 0.0,
                "focal_edges": 0.0,
                "best_window_sec": None,
                "defects": ["corrupted_or_unreadable_source_clip"],
            }

        cand_windows = [
            (0.15, min(dur - 0.08, 2.55)),
            (min(dur * 0.25, max(0.2, dur - 2.4)), min(dur - 0.08, dur * 0.25 + 2.4)),
            (min(dur * 0.50, max(0.2, dur - 2.4)), min(dur - 0.08, dur * 0.50 + 2.4)),
            (max(0.2, dur - 2.65), max(0.7, dur - 0.08)),
        ]
        best_win: tuple[float, float] | None = None
        best_score = -1.0
        best_sharp = 0.0
        best_p95 = 0.0
        best_p95_raw = 0.0
        best_focal = 0.0
        decoded_any = False

        for w0, w1 in cand_windows:
            if w1 - w0 < 0.4:
                continue
            fa_idx = max(0, min(fc - 1, int(round(w0 * fps))))
            fm_idx = max(0, min(fc - 1, int(round(0.5 * (w0 + w1) * fps))))
            fb_idx = max(0, min(fc - 1, int(round(w1 * fps))))
            cap.set(cv2.CAP_PROP_POS_FRAMES, fa_idx)
            oka, fa = cap.read()
            cap.set(cv2.CAP_PROP_POS_FRAMES, fm_idx)
            okm, fm = cap.read()
            cap.set(cv2.CAP_PROP_POS_FRAMES, fb_idx)
            okb, fb = cap.read()
            if not (oka and okb and fa is not None and fb is not None):
                continue
            decoded_any = True
            ca = cv2.resize(fa, (360, 640), interpolation=cv2.INTER_AREA)[60:580, 15:345]
            cb = cv2.resize(fb, (360, 640), interpolation=cv2.INTER_AREA)[60:580, 15:345]
            cm_full = cv2.resize(fm if (okm and fm is not None) else fb, (360, 640), interpolation=cv2.INTER_AREA)
            ga = cv2.cvtColor(ca, cv2.COLOR_BGR2GRAY)
            gb = cv2.cvtColor(cb, cv2.COLOR_BGR2GRAY)
            focal_gray = cv2.cvtColor(cm_full[int(640 * 0.22) : int(640 * 0.56), int(360 * 0.08) : int(360 * 0.92)], cv2.COLOR_BGR2GRAY)
            focal_edges = float(np.mean(cv2.Canny(focal_gray, 45, 135) > 0))
            sharp = float(max(cv2.Laplacian(ga, cv2.CV_64F).var(), cv2.Laplacian(gb, cv2.CV_64F).var()))
            diff_arr = np.abs(ga.astype(np.float32) - gb.astype(np.float32))
            p95_raw = float(np.percentile(diff_arr, 95))
            p99_loc = float(np.percentile(diff_arr, 99))
            sc = min(40.0, sharp * 0.7) + min(40.0, p99_loc * 3.5) + min(25.0, focal_edges * 1400.0)
            if sc > best_score:
                best_score = sc
                best_sharp = round(sharp, 2)
                best_p95 = round(p99_loc, 2)
                best_p95_raw = round(p95_raw, 2)
                best_focal = round(focal_edges, 5)
                best_win = (round(w0, 2), round(w1, 2))
        cap.release()
        if not decoded_any:
            return {
                "exists": True,
                "corrupted": True,
                "duration_sec": round(dur, 2),
                "sharpness": 0.0,
                "motion_p95": 0.0,
                "motion_p95_raw": 0.0,
                "focal_edges": 0.0,
                "best_window_sec": None,
                "defects": ["corrupted_or_unreadable_source_clip"],
            }
        src_defects: list[str] = []
        if best_sharp < POSTHOC_MIN_SHARPNESS_LAPLACIAN:
            src_defects.append(f"source_blurry_focus={best_sharp:.1f}<{POSTHOC_MIN_SHARPNESS_LAPLACIAN}")
        if best_p95 < POSTHOC_LOCKED_TRIPOD_MIN_P95_DIFF:
            src_defects.append(f"source_static_dead_frame={best_p95:.2f}<{POSTHOC_LOCKED_TRIPOD_MIN_P95_DIFF}")
        return {
            "exists": True,
            "corrupted": False,
            "duration_sec": round(dur, 2),
            "sharpness": best_sharp,
            "motion_p95": best_p95,
            "motion_p95_raw": best_p95_raw,
            "focal_edges": best_focal,
            "best_window_sec": list(best_win) if best_win else None,
            "defects": src_defects,
        }

    return cached_by_clip_stat(
        clip_path,
        namespace="src_clip_win_v1",
        compute_fn=_probe_src_windows,
    )


_STRIP_STYLE_PREFIX_RE = re.compile(
    r"^(?:"
    r"Photorealistic bright high-key documentary cinema:\s*"
    r"|Untextured flat-shaded matte low-poly 3D animation[^.]*\.\s*"
    r"(?:Full-bleed eye-level or elevated-three-quarter low-poly world[^.]*\.\s*)?"
    r"(?:Tight macro low-poly framing[^.]*\.\s*)?"
    r"(?:First-person POV low-poly hands[^.]*\.\s*)?"
    r"(?:Centered studio low-poly anatomical brain model[^.]*\.\s*)?"
    r"|Crafted architectural dark-oak cutaway diorama[^.]*\.\s*"
    r")",
    re.IGNORECASE,
)


def _concise_scene_for_strip(scene_text: str) -> str:
    txt = str(scene_text or "").strip()
    cleaned = _STRIP_STYLE_PREFIX_RE.sub("", txt).strip()
    return cleaned if len(cleaned) >= 12 else txt


def _wrap_text_lines(text: str, max_chars: int, max_lines: int = 2) -> list[str]:
    words = str(text or "").strip().split()
    if not words:
        return [""]
    lines: list[str] = []
    cur = ""
    for w in words:
        cand = f"{cur} {w}".strip() if cur else w
        if len(cand) <= max_chars:
            cur = cand
        else:
            if cur:
                lines.append(cur)
            cur = w[:max_chars]
            if len(lines) >= max_lines:
                break
    if len(lines) < max_lines and cur:
        lines.append(cur)
    if len(lines) == max_lines and len(" ".join(lines)) < len(" ".join(words)):
        lines[-1] = lines[-1][: max(1, max_chars - 3)].rstrip() + "..."
    return lines


def render_posthoc_viewer_strips(
    cut_reports: list[dict[str, Any]],
    sample_thumbs_by_cut: dict[int, list[np.ndarray]],
    out_dir: Path,
    cuts_per_sheet: int = POSTHOC_CUTS_PER_VIEWER_SHEET,
) -> list[str]:
    """
    Renders crisp multi-cut diagnostic contact sheets (`sheet_01.jpg..sheet_NN.jpg`) under
    `05_assembly/posthoc_viewer_strips/` so humans and VLM agents can visually verify every cut's
    Start/Mid/End frames alongside its spoken sentence, intended scene, and 5-axis clarity bars.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    for stale in out_dir.glob("sheet_*.jpg"):
        stale.unlink(missing_ok=True)

    if not cut_reports:
        return []

    row_h = 236
    sheet_w = 1340
    thumb_w, thumb_h = 124, 220
    written: list[str] = []

    total_sheets = int(math.ceil(len(cut_reports) / float(max(1, cuts_per_sheet))))
    for s_idx in range(total_sheets):
        batch = cut_reports[s_idx * cuts_per_sheet : (s_idx + 1) * cuts_per_sheet]
        header_h = 46
        canvas = np.full((header_h + len(batch) * row_h, sheet_w, 3), (24, 28, 36), dtype=np.uint8)
        cv2.putText(
            canvas,
            f"ALL ABOUT BRAIN — R64 Post-Hoc Clip-by-Clip Expressive Clarity Sheet {s_idx + 1:02d}/{total_sheets:02d}",
            (18, 31),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.68,
            (235, 240, 248),
            2,
            cv2.LINE_AA,
        )

        for r_i, crep in enumerate(batch):
            y0 = header_h + r_i * row_h
            bg_col = (32, 38, 48) if (r_i % 2 == 0) else (27, 32, 42)
            if not crep["passed"]:
                bg_col = (34, 30, 56)
            canvas[y0 : y0 + row_h - 2, :] = bg_col

            thumbs = sample_thumbs_by_cut.get(int(crep["cut_index"]), [])
            labels = ("START", "MID", "END")
            for t_k in range(3):
                tx = 12 + t_k * (thumb_w + 8)
                ty = y0 + 8
                if t_k < len(thumbs) and thumbs[t_k] is not None:
                    im_t = cv2.resize(thumbs[t_k], (thumb_w, thumb_h), interpolation=cv2.INTER_AREA)
                else:
                    im_t = np.zeros((thumb_h, thumb_w, 3), dtype=np.uint8)
                canvas[ty : ty + thumb_h, tx : tx + thumb_w] = im_t
                cv2.rectangle(canvas, (tx, ty), (tx + thumb_w, ty + 20), (16, 18, 24), -1)
                cv2.putText(
                    canvas,
                    labels[t_k],
                    (tx + 6, ty + 15),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.42,
                    (220, 230, 245),
                    1,
                    cv2.LINE_AA,
                )

            px = 418
            score = float(crep["clarity_score"])
            passed = bool(crep["passed"])
            badge_col = (72, 188, 110) if passed else (68, 82, 228)
            cv2.rectangle(canvas, (px, y0 + 10), (px + 152, y0 + 38), badge_col, -1)
            cv2.putText(
                canvas,
                f"{'PASS' if passed else 'WEAK'} {score:5.1f}/100",
                (px + 10, y0 + 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.52,
                (255, 255, 255),
                2,
                cv2.LINE_AA,
            )

            hdr = (
                f"Cut #{crep['cut_index']:02d} | Clip #{crep['clip_index']:02d} "
                f"[{crep['out_start_sec']:.2f}-{crep['out_end_sec']:.2f}s] | "
                f"{crep['grammar']} | cam={crep['camera_move']}"
            )
            cv2.putText(
                canvas,
                hdr[:92],
                (px + 164, y0 + 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.50,
                (238, 242, 248),
                1,
                cv2.LINE_AA,
            )

            # 5 sub-score mini-bars
            subs = crep["sub_scores"]
            sub_items = [
                ("Legib", subs["visual_legibility"]),
                ("Act/Cam", subs["action_and_camera"]),
                ("Temporal", subs["temporal_coherence"]),
                ("Intent", subs["intent_grammar_alignment"]),
                ("Sync", subs["composition_and_sync"]),
            ]
            for b_i, (b_lbl, b_val) in enumerate(sub_items):
                bx = px + b_i * 176
                by = y0 + 50
                cv2.putText(canvas, f"{b_lbl}:{b_val:.0f}", (bx, by + 12), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (190, 204, 222), 1, cv2.LINE_AA)
                cv2.rectangle(canvas, (bx + 82, by + 2), (bx + 164, by + 13), (55, 62, 74), -1)
                fill_w = int(round(82.0 * max(0.0, min(100.0, float(b_val))) / 100.0))
                bar_c = (86, 196, 120) if b_val >= 75.0 else ((64, 180, 240) if b_val >= 55.0 else (70, 80, 230))
                cv2.rectangle(canvas, (bx + 82, by + 2), (bx + 82 + fill_w, by + 13), bar_c, -1)

            spoken_lines = _wrap_text_lines(f"Spoken: {crep['spoken_narration'] or '(Outro / Music Swell)'}", 104, max_lines=2)
            for l_i, ln in enumerate(spoken_lines):
                cv2.putText(
                    canvas,
                    ln,
                    (px, y0 + 90 + l_i * 22),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.47,
                    (245, 236, 190),
                    1,
                    cv2.LINE_AA,
                )

            scene_lines = _wrap_text_lines(f"Intent: {_concise_scene_for_strip(crep['intended_scene'])}", 104, max_lines=2)
            for l_i, ln in enumerate(scene_lines):
                cv2.putText(
                    canvas,
                    ln,
                    (px, y0 + 140 + l_i * 22),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.45,
                    (205, 218, 232),
                    1,
                    cv2.LINE_AA,
                )

            diag_str = (
                f"Defects: {', '.join(crep['defects'])} -> {crep['remediation']}"
                if crep["defects"]
                else (
                    f"Metrics: sharp={crep['metrics']['sharpness_laplacian']:.1f} "
                    f"edge={crep['metrics']['edge_density']:.4f} "
                    f"dE={crep['metrics']['fg_bg_contrast_de']:.1f} "
                    f"mot_mean={crep['metrics']['mean_motion_diff']:.2f} "
                    f"mot_p95={crep['metrics']['p95_motion_diff']:.2f} "
                    f"histJump={crep['metrics']['max_step_hist_jump']:.2f}"
                )
            )
            diag_col = (110, 145, 255) if crep["defects"] else (155, 198, 170)
            cv2.putText(
                canvas,
                diag_str[:112],
                (px, y0 + 206),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.44,
                diag_col,
                1,
                cv2.LINE_AA,
            )

        sheet_path = out_dir / f"sheet_{s_idx + 1:02d}.jpg"
        cv2.imwrite(str(sheet_path), canvas, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
        written.append(str(sheet_path))
    return written


_AUTO_CV_BOILERPLATE_RE = re.compile(
    r"^Cut\s+#\d+\s*\(Clip\s+#\d+[^)]*\):\s*sharp=[\d.]+,\s*contrast_dE=[\d.]+",
    re.IGNORECASE,
)


def init_posthoc_semantic_review_template(
    project_id_or_dir: str | Path,
    qa_report: dict[str, Any] | None = None,
    auto_populate_from_cv: bool = False,
) -> Path:
    """
    Creates or refreshes `05_assembly/posthoc_semantic_review.json` bound by SHA-256 to the
    assembled MP4 and EDL, pre-filling per-cut context so a VLM agent or human producer can
    record structured `observed_visual_summary` & `expresses_intended_meaning` sign-offs.
    Note: `auto_populate_from_cv=True` pre-fills CV baseline telemetry (`auto_populated=True`)
    as a drafting scaffold ONLY and will NOT pass `--require-review` until replaced with genuine
    human/VLM visual observations (`auto_populated=False`).
    """
    p_dir = _resolve_project_dir(project_id_or_dir)
    if qa_report is None:
        rep_path = p_dir / "05_assembly" / POSTHOC_SEMANTIC_QA_REPORT_FILENAME
        qa_report = _read_json(rep_path) if rep_path.exists() else run_posthoc_semantic_qa(p_dir)

    review_path = p_dir / "05_assembly" / POSTHOC_SEMANTIC_REVIEW_FILENAME
    cuts_payload: list[dict[str, Any]] = []
    for c in qa_report.get("cuts", []):
        c_idx = int(c["cut_index"])
        sheet_no = ((c_idx - 1) // POSTHOC_CUTS_PER_VIEWER_SHEET) + 1
        if auto_populate_from_cv:
            m = c.get("metrics", {})
            obs = (
                f"Cut #{c_idx:02d} (Clip #{int(c['clip_index']):02d}, {c['grammar']}, {c['camera_move']}): "
                f"sharp={m.get('sharpness_laplacian', 0):.1f}, contrast_dE={m.get('fg_bg_contrast_de', 0):.1f}, "
                f"motion_p95={m.get('p95_motion_diff', 0):.2f} aligned with '{str(c.get('spoken_narration') or 'outro')[:48]}'."
            )
            expresses = bool(c.get("passed"))
        else:
            obs = ""
            expresses = None
        cuts_payload.append(
            {
                "cut_index": c_idx,
                "clip_index": int(c["clip_index"]),
                "viewer_sheet": f"sheet_{sheet_no:02d}.jpg",
                "grammar": c["grammar"],
                "camera_move": c["camera_move"],
                "spoken_narration": c["spoken_narration"],
                "intended_scene": c["intended_scene"],
                "cv_clarity_score": c["clarity_score"],
                "auto_populated": bool(auto_populate_from_cv),
                "observed_visual_summary": obs,
                "expresses_intended_meaning": expresses,
                "action_needed": ("none" if c.get("passed") else c.get("remediation", "regenerate_flow_clip")),
            }
        )

    payload = {
        "project_id": p_dir.name,
        "schema": "R64_posthoc_semantic_review_v1",
        "review_origin": ("auto_populated_cv_baseline" if auto_populate_from_cv else "manual_or_vlm_template"),
        "review_instructions": (
            "Inspect posthoc_viewer_strips/sheet_*.jpg, write a unique >=20-char observed_visual_summary per cut, "
            "set auto_populated=false, and set expresses_intended_meaning=true/false."
        ),
        "created_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "final_mp4_sha256": qa_report.get("final_mp4_sha256", ""),
        "edl_sha256": qa_report.get("edl_sha256", ""),
        "cut_count": len(cuts_payload),
        "cuts": cuts_payload,
    }
    review_path.parent.mkdir(parents=True, exist_ok=True)
    review_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    from pipeline.storage import ProjectStorage

    ProjectStorage.record_if_manifest_tracks_stages(p_dir, "05_assembly", POSTHOC_SEMANTIC_REVIEW_FILENAME, review_path)
    return review_path


def validate_posthoc_semantic_review(
    project_dir: Path,
    final_mp4_sha256: str,
    edl_sha256: str,
    expected_cut_count: int,
) -> dict[str, Any]:
    """
    Validates `05_assembly/posthoc_semantic_review.json` against R64 anti-boilerplate & provenance locks:
      - SHA-256 match against current `final_shorts_1080x1920.mp4` and `edit_decision_list.json` / `concat_list.txt`
      - 100% cut coverage (`1..expected_cut_count`)
      - Rejects unreviewed CV auto-populated templates (`auto_populated == True` or CV metric boilerplate string)
      - `len(observed_visual_summary.strip()) >= POSTHOC_MIN_REVIEW_NOTE_CHARS` (`20`)
      - Identical summary repetition `<= POSTHOC_MAX_IDENTICAL_REVIEW_NOTES` (`3`)
      - Explicit boolean `expresses_intended_meaning == True` on every cut
    """
    review_path = project_dir / "05_assembly" / POSTHOC_SEMANTIC_REVIEW_FILENAME
    if not review_path.exists():
        return {
            "present": False,
            "valid": False,
            "issues": ["missing_posthoc_semantic_review_json"],
            "rejected_cuts": [],
            "rejected_actions": {},
        }

    doc = _read_json(review_path)
    issues: list[str] = []
    if str(doc.get("final_mp4_sha256") or "") != str(final_mp4_sha256):
        issues.append("stale_review_final_mp4_sha256_mismatch")
    if edl_sha256 and str(doc.get("edl_sha256") or "") != str(edl_sha256):
        issues.append("stale_review_edl_sha256_mismatch")

    rows = doc.get("cuts") if isinstance(doc.get("cuts"), list) else []
    seen_cuts = {int(r["cut_index"]) for r in rows if isinstance(r, dict) and r.get("cut_index") is not None}
    missing = [i for i in range(1, expected_cut_count + 1) if i not in seen_cuts]
    if missing:
        issues.append(f"missing_review_cuts:{missing[:10]}")

    norm_notes: list[str] = []
    short_note_cuts: list[int] = []
    auto_populated_cuts: list[int] = []
    rejected_cuts: list[int] = []
    rejected_actions: dict[int, str] = {}
    unset_cuts: list[int] = []

    for r in rows:
        if not isinstance(r, dict):
            continue
        c_idx = int(r.get("cut_index") or 0)
        note = str(r.get("observed_visual_summary") or "").strip()
        if bool(r.get("auto_populated")) or bool(_AUTO_CV_BOILERPLATE_RE.search(note)):
            auto_populated_cuts.append(c_idx)
        if len(note) < POSTHOC_MIN_REVIEW_NOTE_CHARS:
            short_note_cuts.append(c_idx)
        else:
            norm_notes.append(re.sub(r"\s+", " ", note.lower()))
        exp_val = r.get("expresses_intended_meaning")
        if not isinstance(exp_val, bool):
            unset_cuts.append(c_idx)
        elif exp_val is False:
            rejected_cuts.append(c_idx)
            act_need = str(r.get("action_needed") or "").strip()
            if act_need and act_need != "none":
                rejected_actions[c_idx] = act_need

    if auto_populated_cuts:
        issues.append(f"auto_populated_cv_baseline_not_semantically_verified:cuts={auto_populated_cuts[:10]}")
    if short_note_cuts:
        issues.append(f"review_notes_too_short_lt_{POSTHOC_MIN_REVIEW_NOTE_CHARS}chars:cuts={short_note_cuts[:10]}")
    if unset_cuts:
        issues.append(f"expresses_intended_meaning_not_bool:cuts={unset_cuts[:10]}")
    if rejected_cuts:
        issues.append(f"reviewer_flagged_unclear_expression:cuts={rejected_cuts}")

    counts = Counter(norm_notes)
    boilerplate = [(txt[:40], cnt) for txt, cnt in counts.items() if cnt > POSTHOC_MAX_IDENTICAL_REVIEW_NOTES]
    if boilerplate:
        issues.append(f"boilerplate_identical_review_notes_gt_{POSTHOC_MAX_IDENTICAL_REVIEW_NOTES}:{boilerplate[:3]}")

    # F-4: templated notes (same sentence skeleton once digits, cut/clip ids and the cut's own plan fields are removed)
    skel_prefixes: list[str] = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        note = str(r.get("observed_visual_summary") or "").lower()
        own_tokens = set(
            re.findall(
                r"[a-z][a-z_\-]+",
                " ".join(str(r.get(k) or "") for k in ("grammar", "camera_move", "viewer_sheet", "intended_scene", "spoken_narration")).lower(),
            )
        )
        words = [w for w in re.findall(r"[a-z][a-z_\-]+", re.sub(r"\d+", " ", note)) if w not in own_tokens]
        if len(words) >= 4:
            skel_prefixes.append(" ".join(words[:8]))
    if skel_prefixes:
        top_skel, top_n = Counter(skel_prefixes).most_common(1)[0]
        if top_n > max(POSTHOC_MAX_IDENTICAL_REVIEW_NOTES, int(0.30 * len(skel_prefixes))):
            issues.append(f"templated_review_notes:{top_n}/{len(skel_prefixes)}_share_skeleton:'{top_skel[:60]}'")

    return {
        "present": True,
        "valid": len(issues) == 0,
        "issues": issues,
        "rejected_cuts": sorted(set(rejected_cuts)),
        "rejected_actions": rejected_actions,
        "reviewed_cuts": len(rows),
    }


def _can_shift_source_window(s_diag: dict[str, Any], defects: list[str]) -> bool:
    if not s_diag.get("exists") or s_diag.get("corrupted") or not s_diag.get("best_window_sec"):
        return False
    if any(k in d for d in defects for k in ("neon_green", "brain_margin", "human_skin", "escher", "plaque", "intrusion")):
        return False
    if float(s_diag.get("sharpness") or 0.0) < POSTHOC_MIN_SHARPNESS_LAPLACIAN * 1.4:
        return False
    if (
        float(s_diag.get("motion_p95") or 0.0) >= POSTHOC_LOCKED_TRIPOD_MIN_P95_DIFF * 1.4
        and any("static" in d or "stalled" in d or "blurry" in d for d in defects)
    ):
        return True
    if float(s_diag.get("focal_edges") or 0.0) >= 0.008 and any("empty_upper_center_focal_zone" in d for d in defects):
        return True
    return False


def _is_source_clip_unhealthy(s_diag: dict[str, Any]) -> bool:
    if not s_diag.get("exists"):
        return False
    if s_diag.get("corrupted"):
        return True
    if float(s_diag.get("sharpness") or 0.0) < POSTHOC_MIN_SHARPNESS_LAPLACIAN:
        return True
    if float(s_diag.get("motion_p95") or 0.0) < POSTHOC_LOCKED_TRIPOD_MIN_P95_DIFF:
        return True
    if float(s_diag.get("focal_edges") or 0.0) < 0.0025:
        return True
    return False


def run_posthoc_semantic_qa(
    project_id_or_dir: str | Path,
    render_strips: bool | None = None,
    run_asr_sync: bool = True,
    require_review: bool = False,
    save_report: bool = True,
    sync_knowledge_base: bool = False,
) -> dict[str, Any]:
    """
    Executes Rule R64 Post-Hoc Clip-by-Clip Expressive Clarity Verification QA on an assembled project.
    """
    do_render_strips = bool(save_report) if render_strips is None else bool(render_strips)
    from pipeline.media_cache import (
        decode_needed_frames,
        get_active_mp4_session,
        get_cached_json,
        get_speed_cache_dir,
        put_cached_json,
        stage_local_file,
    )

    p_dir = _resolve_project_dir(project_id_or_dir)
    final_mp4 = resolve_project_final_mp4(p_dir)
    local_mp4, final_mp4_sha = stage_local_file(final_mp4)
    edl_path = p_dir / "05_assembly" / "edit_decision_list.json"
    concat_path = p_dir / "05_assembly" / "concat_list.txt"
    edl_sha = _sha256_file(edl_path) if edl_path.exists() else (_sha256_file(concat_path) if concat_path.exists() else "")
    ass_path = p_dir / "04_audio" / "subtitles.ass"
    ass_sha = _sha256_file(ass_path) if ass_path.exists() else ""
    vp_cand = next((p for p in (p_dir / "03_visuals" / "visual_plan.json", p_dir / "visual_plan.json") if p.exists()), None)
    sc_cand = next((p for p in (p_dir / "02_script" / "script.json", p_dir / "script.json") if p.exists()), None)
    vp_sha = _sha256_file(vp_cand) if vp_cand else ""
    sc_sha = _sha256_file(sc_cand) if sc_cand else ""
    eqc_path = p_dir / "03_visuals" / "episode_qa_contract.json"
    eqc_sha = _sha256_file(eqc_path) if eqc_path.exists() else ""
    prompts_path = p_dir / "03_visuals" / "flow_all_in_one_prompts.json"
    prompts_sha = _sha256_file(prompts_path) if prompts_path.exists() else ""
    vr = _read_json(p_dir / "04_audio" / "voice_report.json")
    is_synth_test = vr.get("engine") == "kokoro-onnx" and not (p_dir / "04_audio" / "tts_diorama" / "clip_1.wav").exists()
    is_custom_asr = _asr_word_timeline_from_mp4 is not _ORIG_ASR_WORD_TIMELINE_FN

    cv_cache_key = hashlib.sha1(
        f"v3_r66cal|{final_mp4_sha}|{edl_sha}|{ass_sha}|{vp_sha}|{sc_sha}|{eqc_sha}|{prompts_sha}|{int(bool(run_asr_sync))}|{int(bool(is_synth_test))}".encode("utf-8")
    ).hexdigest()[:28]
    thumbs_npz_path = get_speed_cache_dir() / "posthoc_cv" / f"{cv_cache_key}.npz"
    cached_cv = None if is_custom_asr else get_cached_json("posthoc_cv_v1", cv_cache_key)

    cut_reports: list[dict[str, Any]] = []
    sample_thumbs_by_cut: dict[int, list[np.ndarray]] = {}
    used_clip_indices: set[int] = set()

    if isinstance(cached_cv, dict) and isinstance(cached_cv.get("cut_reports"), list):
        fps = float(cached_cv["fps"])
        mp4_dur = float(cached_cv["mp4_dur"])
        ctx = dict(cached_cv["ctx"])
        cut_reports = list(cached_cv["cut_reports"])
        used_clip_indices = {int(x) for x in cached_cv.get("used_clip_indices", [])}
    else:
        ass_txt = ass_path.read_text(encoding="utf-8") if ass_path.exists() else ""
        chapter_spans: list[tuple[float, float]] = []
        default_sub_spans: list[tuple[float, float]] = []
        for ln in ass_txt.splitlines():
            if ln.startswith("Dialogue:"):
                parts = ln.split(",", 9)
                if len(parts) >= 10:
                    t_a, t_b = _parse_ass_ts_sec(parts[1]), _parse_ass_ts_sec(parts[2])
                    if ",ChapterHeadline," in ln or ",AnatomyLabel," in ln:
                        chapter_spans.append((t_a, t_b))
                    elif ",Default," in ln:
                        default_sub_spans.append((t_a, t_b))

        sess = get_active_mp4_session(final_mp4_sha)
        if sess is not None:
            fps = float(sess["fps"])
            total_fc = int(sess["header_fc"] or sess["decoded_fc"])
        else:
            cap_hdr = cv2.VideoCapture(str(local_mp4))
            fps = float(cap_hdr.get(cv2.CAP_PROP_FPS) or 24.0)
            total_fc = int(cap_hdr.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
            cap_hdr.release()
        mp4_dur = (total_fc / fps) if (fps > 0 and total_fc > 0) else 0.0

        cuts_spec, ctx = extract_cut_intent_specs(p_dir, final_mp4_duration_sec=mp4_dur)
        is_v7 = bool(ctx["is_v7"])

        asr_words: list[tuple[float, float, str]] = []
        if run_asr_sync and not is_synth_test and any(c["analogy_locks"] for c in cuts_spec):
            try:
                asr_words = _asr_word_timeline_from_mp4(local_mp4)
            except Exception:  # noqa: BLE001
                asr_words = []

        def _sec_to_fidx(t_s: float) -> int:
            return max(0, min(max(0, total_fc - 1), int(round(t_s * fps))))

        cut_sample_fidxs: dict[int, list[int]] = {}
        needed_fidxs: set[int] = set()
        for c in cuts_spec:
            c_s = float(c["out_start_sec"])
            c_e = max(c_s + 0.12, min(mp4_dur if mp4_dur > 0 else float(c["out_end_sec"]), float(c["out_end_sec"])))
            pad = min(0.08, 0.15 * (c_e - c_s))
            t0 = c_s + pad
            t1 = max(t0 + 0.04, c_e - pad)
            fracs = (0.0, 0.25, 0.50, 0.75, 1.0)
            f_list = [_sec_to_fidx(t0 + fr * (t1 - t0)) for fr in fracs]
            cut_sample_fidxs[int(c["cut_index"])] = f_list
            needed_fidxs.update(f_list)

        _, _, frame_cache = decode_needed_frames(local_mp4, final_mp4_sha, needed_fidxs)

        sent_cuts_map: dict[int, list[dict[str, Any]]] = {}
        for c_pre in cuts_spec:
            for s_k in (c_pre.get("sentence_indices") or []):
                sent_cuts_map.setdefault(int(s_k), []).append(c_pre)

        for c in cuts_spec:
            c_idx = int(c["cut_index"])
            clip_idx = int(c["clip_index"])
            sec_clip_idx = int(c["secondary_clip_index"]) if c.get("secondary_clip_index") is not None else None
            used_clip_indices.add(clip_idx)
            if sec_clip_idx is not None:
                used_clip_indices.add(sec_clip_idx)

            f_idxs = cut_sample_fidxs.get(c_idx, [])
            frames = [frame_cache.get(fi) for fi in f_idxs if frame_cache.get(fi) is not None]
            if len(frames) < 2:
                cut_reports.append(
                    {
                        "cut_index": c_idx,
                        "clip_index": clip_idx,
                        "secondary_clip_index": sec_clip_idx,
                        "offending_clip_indices": [clip_idx] + ([sec_clip_idx] if sec_clip_idx and sec_clip_idx != clip_idx else []),
                        "act": c["act"],
                        "mode": str(c.get("mode") or "single"),
                        "grammar": c["grammar"],
                        "camera_move": c["camera_move"],
                        "location_id": c["location_id"],
                        "is_outro": bool(c.get("is_outro")),
                        "out_start_sec": c["out_start_sec"],
                        "out_end_sec": c["out_end_sec"],
                        "duration_sec": c["duration_sec"],
                        "src_start_sec": c["src_start_sec"],
                        "src_end_sec": c["src_end_sec"],
                        "sentence_indices": c.get("sentence_indices", []),
                        "spoken_narration": c["spoken_narration"],
                        "intended_scene": c["intended_scene"],
                        "passed": False,
                        "clarity_score": 0.0,
                        "sub_scores": {
                            "visual_legibility": 0.0,
                            "action_and_camera": 0.0,
                            "temporal_coherence": 0.0,
                            "intent_grammar_alignment": 0.0,
                            "composition_and_sync": 0.0,
                        },
                        "metrics": {},
                        "defects": ["frame_decode_failure"],
                        "remediation": "regenerate_flow_clip",
                        "recommended_src_window_sec": None,
                    }
                )
                continue

            f_start = frames[0]
            f_mid = frames[len(frames) // 2]
            f_end = frames[-1]
            sample_thumbs_by_cut[c_idx] = [
                cv2.resize(f_start, (180, 320), interpolation=cv2.INTER_AREA),
                cv2.resize(f_mid, (180, 320), interpolation=cv2.INTER_AREA),
                cv2.resize(f_end, (180, 320), interpolation=cv2.INTER_AREA),
            ]

            is_outro = bool(c["is_outro"])
            c_s, c_e = float(c["out_start_sec"]), float(c["out_end_sec"])
            has_top_ov = (
                c.get("mode") in ("split_hstack", "split_vstack")
                or any(cs0 < c_e - 0.04 and cs1 > c_s + 0.04 for cs0, cs1 in chapter_spans)
            )

            clean_seq = [_concat_clean_roi_360(f, has_top_overlay=has_top_ov, is_outro=is_outro) for f in frames]
            clean_mid = clean_seq[len(clean_seq) // 2]
            gray_seq = [cv2.cvtColor(cf, cv2.COLOR_BGR2GRAY) for cf in clean_seq]
            gray_mid = gray_seq[len(gray_seq) // 2]

            defects: list[str] = []

            # 1. Visual Legibility & Subject Separation (25%)
            sharp_lap = round(float(cv2.Laplacian(gray_mid, cv2.CV_64F).var()), 2)
            edge_dens = round(float(np.mean(cv2.Canny(gray_mid, 45, 135) > 0)), 5)
            fg_bg_de = _compute_fg_bg_contrast_de(clean_mid)
            mean_luma = round(float(np.mean(gray_mid)), 2)

            if is_outro:
                legib_score = 92.0 if mean_luma >= 75.0 else 65.0
            else:
                s_part = min(1.0, sharp_lap / max(1.0, POSTHOC_MIN_SHARPNESS_LAPLACIAN * 2.2)) * 38.0
                e_part = min(1.0, edge_dens / max(1e-4, POSTHOC_MIN_EDGE_DENSITY * 2.5)) * 30.0
                c_part = min(1.0, fg_bg_de / max(1.0, POSTHOC_MIN_FG_BG_CONTRAST_DE * 2.5)) * 32.0
                legib_score = round(min(100.0, s_part + e_part + c_part), 1)
                if not is_synth_test:
                    if sharp_lap < POSTHOC_MIN_SHARPNESS_LAPLACIAN:
                        defects.append(f"blurry_focus_laplacian={sharp_lap:.1f}<{POSTHOC_MIN_SHARPNESS_LAPLACIAN}")
                        legib_score = min(legib_score, 52.0)
                    if edge_dens < POSTHOC_MIN_EDGE_DENSITY:
                        defects.append(f"low_structural_edges={edge_dens:.4f}<{POSTHOC_MIN_EDGE_DENSITY}")
                        legib_score = min(legib_score, 52.0)
                    if fg_bg_de < POSTHOC_MIN_FG_BG_CONTRAST_DE:
                        defects.append(f"weak_fg_bg_separation_dE={fg_bg_de:.1f}<{POSTHOC_MIN_FG_BG_CONTRAST_DE}")
                        legib_score = min(legib_score, 55.0)

            # 2. Action & Camera Fidelity (25%)
            diff_se = np.abs(gray_seq[0].astype(np.float32) - gray_seq[-1].astype(np.float32))
            diff_sm = np.abs(gray_seq[0].astype(np.float32) - gray_mid.astype(np.float32))
            step_arrs = [
                np.abs(gray_seq[i].astype(np.float32) - gray_seq[i + 1].astype(np.float32))
                for i in range(len(gray_seq) - 1)
            ]
            step_diffs = [float(np.mean(sa)) for sa in step_arrs]
            step_p95s = [float(np.percentile(sa, 95)) for sa in step_arrs]
            step_p99s = [float(np.percentile(sa, 99)) for sa in step_arrs]
            mean_mot = round(max(float(np.mean(diff_se)), float(np.mean(step_diffs)) if step_diffs else 0.0), 3)
            p95_raw_mot = round(
                max(
                    float(np.percentile(diff_se, 95)),
                    float(np.percentile(diff_sm, 95)),
                    max(step_p95s, default=0.0),
                ),
                3,
            )
            p95_mot = round(
                max(
                    float(np.percentile(diff_se, 99)),
                    float(np.percentile(diff_sm, 99)),
                    max(step_p99s, default=0.0),
                ),
                3,
            )
            flow_dx, flow_dy = _compute_optical_flow_summary(clean_seq[0], clean_seq[-1])

            moving_cam = _is_moving_camera(c["camera_move"])
            if moving_cam:
                if mean_mot >= POSTHOC_MIN_MOVING_CAM_DIFF:
                    act_cam_score = round(min(100.0, 74.0 + min(26.0, (mean_mot - POSTHOC_MIN_MOVING_CAM_DIFF) * 4.5)), 1)
                elif is_outro and mean_mot >= 0.35:
                    act_cam_score = 84.0
                else:
                    defects.append(f"moving_camera_stalled:{c['camera_move']}(mean_diff={mean_mot:.2f}<{POSTHOC_MIN_MOVING_CAM_DIFF})")
                    act_cam_score = round(max(20.0, 60.0 * (mean_mot / max(0.1, POSTHOC_MIN_MOVING_CAM_DIFF))), 1)
            else:
                if p95_mot >= POSTHOC_LOCKED_TRIPOD_MIN_P95_DIFF:
                    act_cam_score = round(min(100.0, 76.0 + min(24.0, (p95_mot - POSTHOC_LOCKED_TRIPOD_MIN_P95_DIFF) * 2.5)), 1)
                else:
                    defects.append(
                        f"locked_tripod_static_dead_frame(p95_diff={p95_mot:.2f}<{POSTHOC_LOCKED_TRIPOD_MIN_P95_DIFF})"
                    )
                    act_cam_score = round(max(18.0, 58.0 * (p95_mot / max(0.1, POSTHOC_LOCKED_TRIPOD_MIN_P95_DIFF))), 1)

            # 3. Temporal Coherence — Zero Mid-Cut Morph / Stall (20%)
            hist_jumps = [_compute_hist_step_jump(clean_seq[i], clean_seq[i + 1]) for i in range(len(clean_seq) - 1)]
            max_hist_jump = max(hist_jumps, default=0.0)
            intra_freeze = (
                not is_synth_test
                and not is_outro
                and float(c["duration_sec"]) >= 2.20
                and len(step_diffs) >= 4
                and (sum(1 for sd in step_diffs if sd < 0.28) >= 2 or (max(step_diffs) < 2.0 and float(np.median(step_diffs)) < 1.45))
            )
            if max_hist_jump > POSTHOC_MAX_STEP_HIST_JUMP:
                defects.append(f"mid_cut_morph_hist_jump={max_hist_jump:.2f}>{POSTHOC_MAX_STEP_HIST_JUMP}")
                temp_score = round(max(20.0, 55.0 - (max_hist_jump - POSTHOC_MAX_STEP_HIST_JUMP) * 120.0), 1)
            elif intra_freeze:
                defects.append("intra_cut_motion_freeze_stall")
                temp_score = 45.0
            else:
                temp_score = round(max(76.0, 100.0 - max_hist_jump * 28.0), 1)

            # 4. Grammar & Semantic Intent Alignment (20%)
            intent_score = 92.0
            raw_grammar = str(c["grammar"])
            grammar = normalize_porcelain_v7_grammar(raw_grammar) if ctx.get("is_porcelain_v7") else raw_grammar
            mode = str(c["mode"])
            pane_diff_val: float | None = None
            brain_chroma_val: float | None = None

            if mode in ("split_hstack", "split_vstack"):
                fh, fw = f_mid.shape[:2]
                if mode == "split_hstack":
                    pad_x = max(8, int(fw * 0.04))
                    half_w = fw // 2
                    p_left = cv2.resize(f_mid[int(fh * 0.24) : int(fh * 0.56), pad_x : half_w - pad_x], (160, 200))
                    p_right = cv2.resize(f_mid[int(fh * 0.24) : int(fh * 0.56), half_w + pad_x : 2 * half_w - pad_x], (160, 200))
                    div_gray = cv2.cvtColor(f_mid[int(fh * 0.30) : int(fh * 0.55), half_w - 2 : half_w + 2], cv2.COLOR_BGR2GRAY)
                    divider_ok = float(np.mean(div_gray)) <= 24.0
                else:
                    pad_y = max(8, int(fh * 0.04))
                    half_h = fh // 2
                    p_left = cv2.resize(f_mid[pad_y : half_h - pad_y, 40 : fw - 40], (200, 160))
                    p_right = cv2.resize(f_mid[half_h + pad_y : 2 * half_h - pad_y, 40 : fw - 40], (200, 160))
                    divider_ok = True
                pane_diff_val = round(float(np.mean(np.abs(p_left.astype(np.float32) - p_right.astype(np.float32)))), 2)
                if pane_diff_val < POSTHOC_SPLIT_PANE_MIN_DIFF:
                    defects.append(f"split_panes_visually_identical(diff={pane_diff_val:.1f}<{POSTHOC_SPLIT_PANE_MIN_DIFF})")
                    intent_score = min(intent_score, 35.0)
                if not divider_ok:
                    defects.append("split_hstack_divider_missing")
                    intent_score = min(intent_score, 45.0)

            if grammar in ("porcelain_living_brain", "lowpoly_matte_brain", "arch_brain_maquette", "frosted_crystal_specimen", "brain_void"):
                brain_chroma_val = _compute_brain_highlight_chroma(clean_mid)
                combined_intent_low = f"{c['spoken_narration']} {c['intended_scene']} {c['prompt']}".lower()
                expects_highlight = any(kw in combined_intent_low for kw in _HIGHLIGHT_SIGNAL_KEYWORDS)
                if expects_highlight and not is_synth_test and brain_chroma_val < POSTHOC_BRAIN_HIGHLIGHT_MIN_CHROMA:
                    defects.append(
                        f"weak_brain_lesion_or_tract_highlight(chroma={brain_chroma_val:.1f}<{POSTHOC_BRAIN_HIGHLIGHT_MIN_CHROMA})"
                    )
                    intent_score = min(intent_score, 52.0)
                if is_v7 and bool(ctx.get("is_porcelain_v7")) and not is_synth_test and grammar == "porcelain_living_brain":
                    ng_ratio = max((compute_neon_green_spill_ratio(cf) for cf in clean_seq), default=0.0)
                    if ng_ratio > PORCELAIN_V7_NEON_GREEN_SPILL_MAX:
                        defects.append(f"neon_green_spill(ratio={ng_ratio:.4f}>{PORCELAIN_V7_NEON_GREEN_SPILL_MAX})")
                        intent_score = min(intent_score, 32.0)
                    bmode_cut = normalize_porcelain_v7_brain_mode(
                        c.get("brain_mode"),
                        scene_text=str(c.get("intended_scene") or ""),
                    )
                    cam_cut = str(c.get("camera_move") or "").strip().lower()
                    if (
                        mode not in ("split_hstack", "split_vstack")
                        and bmode_cut == "cortical_vascular_whole"
                    ):
                        margin_samples = [compute_brain_margin_saturation(sf) for sf in (f_start, f_mid, f_end)]
                        msat = (
                            float(np.mean(margin_samples))
                            if cam_cut in ("gentle_push_in", "clean_pullback_reveal")
                            else max(margin_samples, default=0.0)
                        )
                        if msat > PORCELAIN_V7_BRAIN_MARGIN_SAT_MAX:
                            defects.append(f"brain_margin_glow_spill(margin_sat={msat:.1f}>{PORCELAIN_V7_BRAIN_MARGIN_SAT_MAX})")
                            intent_score = min(intent_score, 36.0)
                if is_v7 and not is_synth_test and grammar == "lowpoly_matte_brain":
                    loc_defect = _detect_nonfrontal_brain_localization_defect(
                        clean_mid,
                        str(c.get("brain_region") or ""),
                        mode,
                    )
                    if loc_defect:
                        defects.append(loc_defect)
                        intent_score = min(intent_score, 45.0)

            for a_lock in c["analogy_locks"]:
                s_idx_al = int(a_lock.get("sentence_index") or 0)
                sib_cuts = sent_cuts_map.get(s_idx_al) or [c]
                al_s = min(float(sc["out_start_sec"]) for sc in sib_cuts)
                al_e = max(float(sc["out_end_sec"]) for sc in sib_cuts)
                req_nouns = [str(n).lower() for n in (a_lock.get("required_any_nouns") or []) if str(n).strip()]
                cut_txt_low = f"{c['intended_scene']} {c['prompt']}".lower()
                any_sib_has_noun = bool(req_nouns) and any(
                    any(rn in f"{sc['intended_scene']} {sc['prompt']}".lower() for rn in req_nouns) for sc in sib_cuts
                )
                this_cut_has_noun = (len(sib_cuts) <= 1) or (not any_sib_has_noun) or any(rn in cut_txt_low for rn in req_nouns)

                sig = str(a_lock.get("cv_signature") or "")
                if sig == "green_stadium_turf" and this_cut_has_noun:
                    g_ratio = compute_green_turf_ratio(f_mid, exclude_bottom_subtitles=True)
                    if g_ratio < 0.018:
                        defects.append(f"analogy_visual_missing_green_turf({g_ratio:.4f}<0.018)")
                        intent_score = min(intent_score, 40.0)
                if asr_words:
                    kw_toks = [re.sub(r"[^a-z0-9]", "", w.lower()) for w in str(a_lock.get("spoken_phrase") or "").split() if w.strip()]
                    if kw_toks:
                        hits = [t0 for t0, _t1, tok in asr_words if tok == kw_toks[0] and (al_s - 2.0) <= t0 <= (al_e + 2.0)]
                        if hits:
                            nearest = min(hits, key=lambda x: abs(x - 0.5 * (al_s + al_e)))
                            if not (al_s - POSTHOC_ANALOGY_SYNC_TOLERANCE_SEC <= nearest <= al_e + POSTHOC_ANALOGY_SYNC_TOLERANCE_SEC):
                                defects.append(
                                    f"analogy_audio_visual_desync('{a_lock.get('spoken_phrase')}'@{nearest:.2f}s vs [{al_s:.2f},{al_e:.2f}])"
                                )
                                intent_score = min(intent_score, 48.0)

            if not is_synth_test:
                if is_v7 and grammar in ("lowpoly_hands_closeup", "lowpoly_pov_hands", "porcelain_hands_closeup", "porcelain_pov_hands"):
                    if any(detect_escher_dual_edge_closeup(f, grammar) for f in (f_start, f_mid, f_end)):
                        defects.append("escher_dual_edge_closeup_intrusion")
                        intent_score = min(intent_score, 30.0)
                    if detect_transient_top_intrusion_pov(frames, grammar):
                        defects.append("transient_top_border_arm_intrusion")
                        intent_score = min(intent_score, 30.0)

                if (
                    is_v7
                    and bool(ctx.get("is_porcelain_v7"))
                    and not is_outro
                    and grammar in ("porcelain_hands_closeup", "porcelain_pov_hands", "porcelain_fullbleed_world")
                ):
                    flesh_cap_r64 = (
                        0.24
                        if grammar == "porcelain_fullbleed_world"
                        else (PORCELAIN_V7_HUMAN_SKIN_MAX + 0.04)
                    )
                    max_peach = max((compute_porcelain_flesh_leak_ratio(cf) for cf in clean_seq), default=0.0)
                    if max_peach > flesh_cap_r64:
                        defects.append(f"human_skin_or_face_leak(peach={max_peach:.3f}>{flesh_cap_r64:.2f})")
                        intent_score = min(intent_score, 35.0)

                rois_for_plaque = [
                    r
                    for sf in (f_start, f_mid, f_end)
                    for r in _non_subtitle_scene_rois(sf, has_top_overlay=has_top_ov, is_outro=is_outro)
                ]
                plaque_run = max((_max_horizontal_plaque_glyph_run(r) for r in rois_for_plaque), default=0)
                if plaque_run >= (5 if is_v7 else 8):
                    defects.append(f"in_scene_gibberish_plaque_text(run={plaque_run})")
                    intent_score = min(intent_score, 35.0)

                if is_v7 and not is_outro:
                    lo_y, hi_y = PORCELAIN_V7_LUMA_RANGE if ctx.get("is_porcelain_v7") else DIORAMA_V7_LUMA_RANGE
                    if mean_luma < max(72.0, lo_y - 32.0):
                        defects.append(f"dark_void_exposure_drop(luma={mean_luma:.1f})")
                        intent_score = min(intent_score, 48.0)

            # 5. Composition & Subtitle Non-Occlusion / Sync (10%)
            comp_score = 94.0
            fh_m, fw_m = f_mid.shape[:2]
            main_band = cv2.cvtColor(f_mid[int(fh_m * 0.22) : int(fh_m * 0.56), int(fw_m * 0.08) : int(fw_m * 0.92)], cv2.COLOR_BGR2GRAY)
            main_edges = float(np.mean(cv2.Canny(main_band, 45, 135) > 0))
            if not is_outro and not is_synth_test and main_edges < 0.0025:
                defects.append(f"empty_upper_center_focal_zone(edges={main_edges:.4f})")
                comp_score = 52.0
            if not is_outro and c["spoken_narration"] and default_sub_spans:
                has_sub = any(s0 < c_e - 0.05 and s1 > c_s + 0.05 for s0, s1 in default_sub_spans)
                if not has_sub:
                    defects.append("missing_burned_subtitle_over_speech_cut")
                    comp_score = min(comp_score, 55.0)

            clarity_score = round(
                0.25 * legib_score
                + 0.25 * act_cam_score
                + 0.20 * temp_score
                + 0.20 * intent_score
                + 0.10 * comp_score,
                1,
            )
            if defects:
                clarity_score = round(min(clarity_score, POSTHOC_MIN_CUT_CLARITY_SCORE - 1.0), 1)
            cut_passed = (clarity_score >= POSTHOC_MIN_CUT_CLARITY_SCORE) and (len(defects) == 0)

            cut_reports.append(
                {
                    "cut_index": c_idx,
                    "clip_index": clip_idx,
                    "secondary_clip_index": sec_clip_idx,
                    "offending_clip_indices": ([] if cut_passed else [clip_idx]),
                    "act": c["act"],
                    "mode": mode,
                    "grammar": grammar,
                    "camera_move": c["camera_move"],
                    "location_id": c["location_id"],
                    "brain_region": str(c.get("brain_region") or ""),
                    "is_outro": is_outro,
                    "out_start_sec": c["out_start_sec"],
                    "out_end_sec": c["out_end_sec"],
                    "duration_sec": c["duration_sec"],
                    "src_start_sec": c["src_start_sec"],
                    "src_end_sec": c["src_end_sec"],
                    "sentence_indices": c["sentence_indices"],
                    "spoken_narration": c["spoken_narration"],
                    "intended_scene": c["intended_scene"],
                    "passed": cut_passed,
                    "clarity_score": clarity_score,
                    "sub_scores": {
                        "visual_legibility": legib_score,
                        "action_and_camera": act_cam_score,
                        "temporal_coherence": temp_score,
                        "intent_grammar_alignment": intent_score,
                        "composition_and_sync": comp_score,
                    },
                    "metrics": {
                        "sharpness_laplacian": sharp_lap,
                        "edge_density": edge_dens,
                        "fg_bg_contrast_de": fg_bg_de,
                        "mean_luma": mean_luma,
                        "mean_motion_diff": mean_mot,
                        "p95_motion_diff": p95_mot,
                        "p95_raw_motion_diff": p95_raw_mot,
                        "optical_flow_dx": flow_dx,
                        "optical_flow_dy": flow_dy,
                        "max_step_hist_jump": max_hist_jump,
                        "split_pane_diff": pane_diff_val,
                        "brain_highlight_chroma": brain_chroma_val,
                        "main_focal_edge_density": round(main_edges, 5),
                    },
                    "defects": defects,
                    "remediation": "none",
                    "recommended_src_window_sec": None,
                }
            )

        if not is_custom_asr:
            put_cached_json(
                "posthoc_cv_v1",
                cv_cache_key,
                {
                    "fps": fps,
                    "mp4_dur": mp4_dur,
                    "ctx": {
                        "schema_version": ctx["schema_version"],
                        "style_profile": ctx["style_profile"],
                        "dossier": ctx["dossier"],
                        "is_v7": bool(ctx["is_v7"]),
                        "is_porcelain_v7": bool(ctx.get("is_porcelain_v7")),
                    },
                    "cut_reports": cut_reports,
                    "used_clip_indices": sorted(used_clip_indices),
                },
            )
            if sample_thumbs_by_cut:
                try:
                    thumbs_npz_path.parent.mkdir(parents=True, exist_ok=True)
                    np.savez_compressed(
                        thumbs_npz_path,
                        **{f"c{k}": np.stack(v, axis=0) for k, v in sample_thumbs_by_cut.items() if len(v) == 3},
                    )
                except OSError:
                    pass

    # Pure CV status before applying semantic review overrides
    cv_scores = [float(x["clarity_score"]) for x in cut_reports]
    cv_weak = [int(x["cut_index"]) for x in cut_reports if not x["passed"]]
    cv_passed = (
        len(cut_reports) > 0
        and len(cv_weak) == 0
        and (round(float(np.mean(cv_scores)), 1) if cv_scores else 0.0) >= POSTHOC_MIN_EPISODE_MEAN_CLARITY_SCORE
    )

    # Source clip attribution across BOTH primary and split secondary clips
    clips_dir = p_dir / "03_visuals" / "flow_native_clips"
    clip_files = sorted(clips_dir.glob("clip_*.mp4"), key=numeric_clip_sort_key) if clips_dir.exists() else []
    source_diag_cache: dict[int, dict[str, Any]] = {}

    def _get_src_diag(c_no: int) -> dict[str, Any]:
        if c_no not in source_diag_cache:
            source_diag_cache[c_no] = _inspect_source_clip_windows(clips_dir / f"clip_{c_no}.mp4")
        return source_diag_cache[c_no]

    for crep in cut_reports:
        if crep["passed"]:
            continue
        c_num = int(crep["clip_index"])
        sec_num = int(crep["secondary_clip_index"]) if crep.get("secondary_clip_index") is not None else None
        s_diag = _get_src_diag(c_num)
        sec_diag = _get_src_diag(sec_num) if (sec_num is not None and sec_num != c_num) else None

        if any("desync" in d or "subtitle" in d or "divider" in d for d in crep["defects"]) or (
            sec_num == c_num and any("split_panes_visually_identical" in d for d in crep["defects"])
        ):
            crep["remediation"] = "rebuild_assembly_edl_or_subtitles"
            crep["offending_clip_indices"] = []
        elif sec_diag is not None:
            pri_bad = _is_source_clip_unhealthy(s_diag)
            sec_bad = _is_source_clip_unhealthy(sec_diag)
            if sec_bad and not pri_bad:
                if _can_shift_source_window(sec_diag, crep["defects"]):
                    crep["remediation"] = "shift_edl_source_window"
                    crep["recommended_src_window_sec"] = sec_diag.get("best_window_sec")
                else:
                    crep["remediation"] = "regenerate_flow_clip"
                crep["offending_clip_indices"] = [sec_num]
            elif pri_bad and not sec_bad:
                if _can_shift_source_window(s_diag, crep["defects"]):
                    crep["remediation"] = "shift_edl_source_window"
                    crep["recommended_src_window_sec"] = s_diag.get("best_window_sec")
                else:
                    crep["remediation"] = "regenerate_flow_clip"
                crep["offending_clip_indices"] = [c_num]
            elif _can_shift_source_window(s_diag, crep["defects"]):
                crep["remediation"] = "shift_edl_source_window"
                crep["recommended_src_window_sec"] = s_diag.get("best_window_sec")
                crep["offending_clip_indices"] = [c_num]
            elif _can_shift_source_window(sec_diag, crep["defects"]):
                crep["remediation"] = "shift_edl_source_window"
                crep["recommended_src_window_sec"] = sec_diag.get("best_window_sec")
                crep["offending_clip_indices"] = [sec_num]
            else:
                crep["remediation"] = "regenerate_flow_clip"
                crep["offending_clip_indices"] = sorted({c_num, sec_num})
        elif _can_shift_source_window(s_diag, crep["defects"]):
            crep["remediation"] = "shift_edl_source_window"
            crep["recommended_src_window_sec"] = s_diag.get("best_window_sec")
            crep["offending_clip_indices"] = [c_num]
        else:
            crep["remediation"] = "regenerate_flow_clip"
            crep["offending_clip_indices"] = [c_num]

    # Validate SHA-256-bound semantic review BEFORE aggregating summaries & rendering viewer strips
    review_status = validate_posthoc_semantic_review(
        project_dir=p_dir,
        final_mp4_sha256=final_mp4_sha,
        edl_sha256=edl_sha,
        expected_cut_count=len(cut_reports),
    )
    review_sha_fresh = not any(x.startswith("stale_review_") for x in review_status.get("issues", []))
    if review_sha_fresh and review_status.get("rejected_cuts"):
        rej_actions = review_status.get("rejected_actions") or {}
        for crep in cut_reports:
            c_idx_r = int(crep["cut_index"])
            if c_idx_r in review_status["rejected_cuts"]:
                crep["passed"] = False
                if "reviewer_flagged_unclear_expression" not in crep["defects"]:
                    crep["defects"].append("reviewer_flagged_unclear_expression")
                crep["clarity_score"] = round(min(float(crep["clarity_score"]), POSTHOC_MIN_CUT_CLARITY_SCORE - 1.0), 1)
                prescribed = rej_actions.get(c_idx_r)
                if prescribed in ("shift_edl_source_window", "regenerate_flow_clip", "rebuild_assembly_edl_or_subtitles"):
                    crep["remediation"] = prescribed
                elif crep.get("remediation") in (None, "", "none"):
                    crep["remediation"] = "regenerate_flow_clip"
                if not crep.get("offending_clip_indices") and crep["remediation"] != "rebuild_assembly_edl_or_subtitles":
                    crep["offending_clip_indices"] = [int(crep["clip_index"])]

    # Aggregate per-source-clip clarity map (including standalone CV inspection of unused/corrupted source clips)
    cuts_by_clip: dict[int, list[dict[str, Any]]] = {}
    for crep in cut_reports:
        cuts_by_clip.setdefault(int(crep["clip_index"]), []).append(crep)
        if crep.get("secondary_clip_index") is not None:
            cuts_by_clip.setdefault(int(crep["secondary_clip_index"]), []).append(crep)

    source_clips_summary: list[dict[str, Any]] = []
    all_clip_nums = sorted(
        used_clip_indices
        | {
            int(re.search(r"(\d+)", cf.stem).group(1))
            for cf in clip_files
            if re.search(r"(\d+)", cf.stem)
        }
    )
    for c_num in all_clip_nums:
        cf = clips_dir / f"clip_{c_num}.mp4"
        s_diag = _get_src_diag(c_num) if cf.exists() else {"exists": False, "corrupted": False, "defects": []}
        linked = cuts_by_clip.get(c_num, [])
        if linked:
            # For split cuts where ONLY the other clip offended, do not falsely fail the healthy partner clip
            relevant_failed = [
                x
                for x in linked
                if not x["passed"]
                and (not x.get("offending_clip_indices") or c_num in x["offending_clip_indices"])
            ]
            c_score = round(float(np.mean([x["clarity_score"] for x in linked])), 1)
            c_passed = (len(relevant_failed) == 0) and not bool(s_diag.get("corrupted"))
            c_defects = sorted(
                {d for x in relevant_failed for d in x["defects"]} | set(s_diag.get("defects") or [])
            )
            if s_diag.get("corrupted"):
                c_score = 0.0
        elif cf.exists():
            if s_diag.get("corrupted"):
                c_score = 0.0
                c_passed = False
                c_defects = list(s_diag.get("defects") or ["corrupted_or_unreadable_source_clip"])
            else:
                sh_v = float(s_diag.get("sharpness") or 0.0)
                mo_v = float(s_diag.get("motion_p95") or 0.0)
                fo_v = float(s_diag.get("focal_edges") or 0.0)
                c_defects = list(s_diag.get("defects") or [])
                raw_sc = (
                    min(40.0, (sh_v / max(1.0, POSTHOC_MIN_SHARPNESS_LAPLACIAN * 2.2)) * 40.0)
                    + min(35.0, (mo_v / max(0.5, POSTHOC_LOCKED_TRIPOD_MIN_P95_DIFF * 2.2)) * 35.0)
                    + min(25.0, (fo_v / 0.02) * 25.0)
                )
                c_score = round(min(raw_sc, POSTHOC_MIN_CUT_CLARITY_SCORE - 1.0) if c_defects else raw_sc, 1)
                c_passed = (len(c_defects) == 0) and (c_score >= POSTHOC_MIN_CUT_CLARITY_SCORE)
        else:
            c_score = None
            c_passed = None
            c_defects = []
        source_clips_summary.append(
            {
                "clip_number": c_num,
                "file_exists": cf.exists(),
                "used_in_assembled_video": bool(linked),
                "cut_indices": [int(x["cut_index"]) for x in linked],
                "mean_clarity_score": c_score,
                "passed": c_passed,
                "source_sharpness": s_diag.get("sharpness") if cf.exists() else None,
                "source_motion_p95": s_diag.get("motion_p95") if cf.exists() else None,
                "best_window_sec": s_diag.get("best_window_sec") if cf.exists() else None,
                "defects": c_defects,
            }
        )

    # Render viewer contact strips (reflecting any reviewer rejections)
    strips_dir = p_dir / "05_assembly" / POSTHOC_VIEWER_STRIPS_DIRNAME
    viewer_sheets: list[str] = []
    if do_render_strips and cut_reports:
        rej_sig = sorted(review_status.get("rejected_cuts") or []) if review_sha_fresh else []
        strips_state_key = hashlib.sha1(
            f"{cv_cache_key}|{rej_sig}|{POSTHOC_CUTS_PER_VIEWER_SHEET}|{strips_dir.resolve()}".encode("utf-8")
        ).hexdigest()[:24]
        prev_strips_state = get_cached_json("posthoc_strips_v1", strips_state_key)
        reused_existing = False
        if isinstance(prev_strips_state, list) and prev_strips_state:
            existing_paths: list[str] = []
            all_match = True
            for item in prev_strips_state:
                sp = Path(item["path"])
                try:
                    st = sp.stat()
                    if st.st_size != int(item["size"]) or st.st_mtime_ns != int(item["mtime_ns"]):
                        all_match = False
                        break
                    existing_paths.append(str(sp))
                except OSError:
                    all_match = False
                    break
            if all_match and len(list(strips_dir.glob("sheet_*.jpg"))) == len(existing_paths):
                viewer_sheets = existing_paths
                reused_existing = True
        if not reused_existing:
            if not sample_thumbs_by_cut and thumbs_npz_path.exists():
                try:
                    with np.load(thumbs_npz_path) as zf:
                        for k in zf.files:
                            if k.startswith("c") and k[1:].isdigit():
                                arr = zf[k]
                                sample_thumbs_by_cut[int(k[1:])] = [arr[0], arr[1], arr[2]]
                except Exception:  # noqa: BLE001
                    pass
            viewer_sheets = render_posthoc_viewer_strips(
                cut_reports=cut_reports,
                sample_thumbs_by_cut=sample_thumbs_by_cut,
                out_dir=strips_dir,
                cuts_per_sheet=POSTHOC_CUTS_PER_VIEWER_SHEET,
            )
            state_items = []
            for vs_str in viewer_sheets:
                vp_s = Path(vs_str)
                try:
                    st_v = vp_s.stat()
                    state_items.append({"path": str(vp_s), "size": st_v.st_size, "mtime_ns": st_v.st_mtime_ns})
                except OSError:
                    pass
            if len(state_items) == len(viewer_sheets):
                put_cached_json("posthoc_strips_v1", strips_state_key, state_items)
    elif strips_dir.exists():
        viewer_sheets = [str(p) for p in sorted(strips_dir.glob("sheet_*.jpg"))]

    # Act-by-Act & Grammar-by-Grammar clarity analytics
    act_summary: dict[str, dict[str, Any]] = {}
    grammar_summary: dict[str, dict[str, Any]] = {}
    for crep in cut_reports:
        a_key = f"act_{crep['act']}"
        act_summary.setdefault(a_key, {"cuts": 0, "scores": [], "weak_cuts": 0})
        act_summary[a_key]["cuts"] += 1
        act_summary[a_key]["scores"].append(crep["clarity_score"])
        if not crep["passed"]:
            act_summary[a_key]["weak_cuts"] += 1

        g_key = str(crep["grammar"])
        grammar_summary.setdefault(g_key, {"cuts": 0, "scores": [], "weak_cuts": 0})
        grammar_summary[g_key]["cuts"] += 1
        grammar_summary[g_key]["scores"].append(crep["clarity_score"])
        if not crep["passed"]:
            grammar_summary[g_key]["weak_cuts"] += 1

    for d_map in (act_summary, grammar_summary):
        for k, v in d_map.items():
            arr = v.pop("scores")
            v["mean_clarity_score"] = round(float(np.mean(arr)), 1) if arr else 0.0
            v["min_clarity_score"] = round(float(np.min(arr)), 1) if arr else 0.0

    scores_all = [float(x["clarity_score"]) for x in cut_reports]
    mean_clarity = round(float(np.mean(scores_all)), 1) if scores_all else 0.0
    min_clarity = round(float(np.min(scores_all)), 1) if scores_all else 0.0
    p10_clarity = round(float(np.percentile(scores_all, 10)), 1) if scores_all else 0.0
    weak_cuts = sorted(int(x["cut_index"]) for x in cut_reports if not x["passed"])
    regen_clips = sorted(
        {
            int(c_id)
            for x in cut_reports
            if not x["passed"] and x.get("remediation") == "regenerate_flow_clip"
            for c_id in (x.get("offending_clip_indices") or [x["clip_index"]])
        }
    )
    shift_recommendations = [
        {
            "cut_index": int(x["cut_index"]),
            "clip_index": int((x.get("offending_clip_indices") or [x["clip_index"]])[0]),
            "current_src_window_sec": [x["src_start_sec"], x["src_end_sec"]],
            "recommended_src_window_sec": x["recommended_src_window_sec"],
        }
        for x in cut_reports
        if not x["passed"]
        and x.get("remediation") == "shift_edl_source_window"
        and x.get("recommended_src_window_sec") is not None
    ]

    cuts_all_clear = (
        len(cut_reports) > 0
        and len(weak_cuts) == 0
        and mean_clarity >= POSTHOC_MIN_EPISODE_MEAN_CLARITY_SCORE
    )
    overall_passed = cuts_all_clear and (bool(review_status["valid"]) if require_review else True)

    report = {
        "project_id": p_dir.name,
        "rule": "R64",
        "schema_version": ctx["schema_version"],
        "style_profile": ctx["style_profile"],
        "dossier": ctx["dossier"],
        "evaluated_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "final_mp4": str(final_mp4),
        "final_mp4_sha256": final_mp4_sha,
        "edl_sha256": edl_sha,
        "fps": round(fps, 2),
        "duration_sec": round(mp4_dur, 3),
        "passed": overall_passed,
        "cv_passed": cv_passed,
        "require_review": require_review,
        "semantic_review": review_status,
        "summary": {
            "cut_count": len(cut_reports),
            "passed_cuts": len(cut_reports) - len(weak_cuts),
            "weak_cut_count": len(weak_cuts),
            "weak_cut_indices": weak_cuts,
            "regenerate_clip_indices": regen_clips,
            "shift_window_recommendations": shift_recommendations,
            "mean_clarity_score": mean_clarity,
            "p10_clarity_score": p10_clarity,
            "min_clarity_score": min_clarity,
            "unused_source_clips": [
                int(s["clip_number"]) for s in source_clips_summary if s["file_exists"] and not s["used_in_assembled_video"]
            ],
            "corrupted_source_clips": [
                int(s["clip_number"])
                for s in source_clips_summary
                if "corrupted_or_unreadable_source_clip" in s.get("defects", [])
            ],
        },
        "act_clarity_summary": act_summary,
        "grammar_clarity_summary": grammar_summary,
        "viewer_sheets": viewer_sheets,
        "source_clips": source_clips_summary,
        "cuts": cut_reports,
    }

    if save_report:
        from pipeline.storage import ProjectStorage

        out_path = p_dir / "05_assembly" / POSTHOC_SEMANTIC_QA_REPORT_FILENAME
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        ProjectStorage.record_if_manifest_tracks_stages(p_dir, "05_assembly", POSTHOC_SEMANTIC_QA_REPORT_FILENAME, out_path)
        rev_f = p_dir / "05_assembly" / POSTHOC_SEMANTIC_REVIEW_FILENAME
        if rev_f.exists():
            ProjectStorage.record_if_manifest_tracks_stages(p_dir, "05_assembly", POSTHOC_SEMANTIC_REVIEW_FILENAME, rev_f)
        if do_render_strips:
            keep_rels: set[str] = set()
            for vs_str in viewer_sheets:
                vs_p = Path(vs_str)
                if vs_p.exists():
                    rel_vs = vs_p.relative_to(p_dir / "05_assembly").as_posix()
                    keep_rels.add(rel_vs)
                    ProjectStorage.record_if_manifest_tracks_stages(p_dir, "05_assembly", rel_vs, vs_p)
            ProjectStorage.prune_manifest_stage_prefix(p_dir, "05_assembly", "posthoc_viewer_strips/sheet_", keep_rels)

    if sync_knowledge_base:
        from pipeline.knowledge_hub import sync_project_to_knowledge_base

        sync_project_to_knowledge_base(p_dir, posthoc_report=report)

    return report


__all__ = [
    "extract_cut_intent_specs",
    "init_posthoc_semantic_review_template",
    "render_posthoc_viewer_strips",
    "resolve_project_final_mp4",
    "run_posthoc_semantic_qa",
    "validate_posthoc_semantic_review",
]
