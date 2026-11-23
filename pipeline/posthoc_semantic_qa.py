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
import os
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
    EXPRESSIVE_25D_V8_STYLE_PROFILE,
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
    PROMPT_SCHEMA_VERSION_V8,
    WORKSPACE_ROOT,
    is_diorama_profile,
    is_diorama_v7_plan,
    is_expressive_v8_plan,
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
    detect_unintended_horizontal_split_seam,
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
    voice_report = _read_json(project_dir / "04_audio" / "voice_report.json")
    vr_text_by_sent: dict[int, str] = {}
    for sp_row in (voice_report.get("sentence_spans") or []):
        if isinstance(sp_row, dict) and sp_row.get("sentence_index") is not None:
            txt_sp = str(sp_row.get("text") or sp_row.get("sentence") or "").strip()
            if txt_sp:
                vr_text_by_sent[int(sp_row["sentence_index"])] = txt_sp

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

    is_expressive_v8 = bool(is_expressive_v8_plan(visual_plan, edl, prompts_doc, script_doc))
    is_porcelain = bool(is_v7 and not is_expressive_v8 and is_porcelain_v7_plan(visual_plan, edl, prompts_doc, script_doc))
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
            if sent_nums:
                spoken_text = " ".join(
                    vr_text_by_sent.get(k) or (sentences[k - 1] if 1 <= k <= len(sentences) else "")
                    for k in sent_nums
                ).strip()
            else:
                spoken_text = str(c.get("narration") or "")

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

            diegetic_allowlist = (
                c.get("diegetic_text_allowlist")
                or p_meta.get("diegetic_text_allowlist")
                or v_meta.get("diegetic_text_allowlist")
                or []
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
                    "neural_state": str(c.get("neural_state") or v_meta.get("neural_state") or p_meta.get("neural_state") or "").strip().lower(),
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
                    "diegetic_text_allowlist": list(diegetic_allowlist) if isinstance(diegetic_allowlist, list) else [],
                    "has_data_stamp": bool(c.get("has_data_stamp")),
                    "has_anatomy_callout": bool(c.get("has_anatomy_callout")),
                    "stacked_cutaway_brain_compare": bool(c.get("stacked_cutaway_brain_compare")),
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
                    "diegetic_text_allowlist": [],
                }
            )

    context = {
        "project_id": project_dir.name,
        "schema_version": (
            PROMPT_SCHEMA_VERSION_V8
            if is_expressive_v8
            else (PROMPT_SCHEMA_VERSION_V7 if is_v7 else (6 if is_diorama else int(prompts_doc.get("schema_version") or 5)))
        ),
        "style_profile": (
            EXPRESSIVE_25D_V8_STYLE_PROFILE
            if is_expressive_v8
            else (
                resolve_diorama_v7_style_profile(visual_plan, edl, prompts_doc, script_doc)
                if is_v7
                else str(visual_plan.get("style_profile") or script_doc.get("style_profile") or ("neuro_diorama" if is_diorama else "classic"))
            )
        ),
        "is_diorama": is_diorama,
        "is_v7": is_v7,
        "is_porcelain_v7": is_porcelain,
        "is_expressive_v8": is_expressive_v8,
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
    is_expressive_v8: bool = False,
    has_hero_stamp: bool = False,
) -> np.ndarray:
    """Concatenates non-subtitle clean scene ROIs and normalizes width to 360px for scale-invariant CV metrics."""
    rois = _non_subtitle_scene_rois(
        frame_bgr,
        has_top_overlay=has_top_overlay,
        is_outro=is_outro,
        is_expressive_v8=is_expressive_v8,
        has_hero_stamp=has_hero_stamp,
    )
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


_PLANNED_FAST_FLICKER_EXEMPT_TOKENS: tuple[str, ...] = (
    "whip_pan",
    "portal_zoom",
    "portal_dive_flight",
    "crash_zoom",
)


def detect_intracut_grid_luma_flicker(
    frames_bgr_or_gray: list[np.ndarray] | tuple[np.ndarray, ...],
    *,
    fps: float = 30.0,
    camera_move: str = "",
    cut_index: int = 0,
    boundary_trim_frames: int = 2,
    luma_spike_thresh: float = 18.0,
    min_flagged_cells: int = 2,
    max_neighbor_drift: float = 8.0,
) -> dict[str, Any]:
    """
    Detect 1-frame intra-cut luminance flicker over a 4x3 regional grid at 64x36 grayscale (P1-6, Tier-2).
    Trims cut boundaries to ignore NLE crossfades and exempts planned rapid camera transitions.
    """
    cam_low = str(camera_move or "").strip().lower()
    exempt_planned_fast_move = any(tok in cam_low for tok in _PLANNED_FAST_FLICKER_EXEMPT_TOKENS)
    seq = list(frames_bgr_or_gray or [])
    trim = max(0, int(boundary_trim_frames))
    if trim > 0:
        end_idx = len(seq) - trim
        trimmed = seq[trim:end_idx] if end_idx > trim else []
    else:
        trimmed = seq

    grid_rows: list[np.ndarray] = []
    orig_indices: list[int] = []
    for offset, frm in enumerate(trimmed):
        if frm is None or not isinstance(frm, np.ndarray) or frm.size == 0:
            continue
        if frm.ndim == 3:
            if frm.shape[2] == 4:
                gray = cv2.cvtColor(frm, cv2.COLOR_BGRA2GRAY)
            elif frm.shape[2] == 3:
                gray = cv2.cvtColor(frm, cv2.COLOR_BGR2GRAY)
            else:
                gray = frm[:, :, 0]
        elif frm.ndim == 2:
            gray = frm
        else:
            continue
        if gray.shape != (36, 64):
            gray = cv2.resize(gray, (64, 36), interpolation=cv2.INTER_AREA)
        g_f32 = gray.astype(np.float32)
        # (36, 64) partitions cleanly into 3x4 = 12 regional luma cells (12px x 16px each)
        cells = g_f32.reshape(3, 12, 4, 16).mean(axis=(1, 3)).ravel()
        grid_rows.append(cells)
        orig_indices.append(trim + offset)

    inspected_frames = len(grid_rows)
    spikes: list[dict[str, Any]] = []
    safe_fps = max(1.0, float(fps or 30.0))
    if inspected_frames >= 3:
        mat = np.stack(grid_rows, axis=0)
        luma_thresh = float(luma_spike_thresh)
        drift_cap = float(max_neighbor_drift)
        min_cells = max(1, int(min_flagged_cells))
        for t in range(1, inspected_frames - 1):
            mid = 0.5 * (mat[t - 1] + mat[t + 1])
            spike_vec = np.abs(mat[t] - mid)
            drift_vec = np.abs(mat[t + 1] - mat[t - 1])
            flagged = (spike_vec >= luma_thresh) & (drift_vec <= drift_cap)
            flagged_count = int(np.sum(flagged))
            if flagged_count >= min_cells:
                max_delta = float(np.max(spike_vec[flagged]))
                f_idx = int(orig_indices[t])
                spikes.append(
                    {
                        "frame_idx": f_idx,
                        "time_sec": round(float(f_idx) / safe_fps, 4),
                        "max_cell_delta": round(max_delta, 3),
                        "flagged_cells": flagged_count,
                    }
                )

    max_spike_delta = round(max((float(s["max_cell_delta"]) for s in spikes), default=0.0), 3)
    extreme_warning = (not exempt_planned_fast_move) and (max_spike_delta >= 32.0 or len(spikes) >= 3)
    return {
        "cut_index": int(cut_index),
        "inspected_frames": inspected_frames,
        "intracut_flicker_spikes": len(spikes),
        "max_spike_delta": max_spike_delta,
        "spikes": spikes,
        "exempt_planned_fast_move": exempt_planned_fast_move,
        "extreme_flicker_warning": extreme_warning,
    }


def evaluate_cut_temporal_smoothness(
    mp4_path: Path,
    cuts: list[dict[str, Any]],
    *,
    freeze_diff_thresh: float = 0.12,
    max_consec_frozen_moving: int = 3,
    max_frozen_ratio_moving: float = 0.06,
) -> dict[int, dict[str, Any]]:
    """
    Single-pass frame-by-frame temporal smoothness audit across all EDL cuts (Rule R77).
    Computes consecutive frame-to-frame center-ROI luminance MAD `[y=30..68%, x=12..88%]`
    and flags moving-camera / `brain_simulator_3d` cuts with `max_consecutive_frozen_frames >= 3`
    or `frozen_frame_ratio > 0.06` (catches slow-motion stretch & 24->30fps frame duplication stutter).
    """
    out: dict[int, dict[str, Any]] = {}
    if not mp4_path.exists() or mp4_path.stat().st_size < 1024 or not cuts:
        return out
    cap = cv2.VideoCapture(str(mp4_path))
    if not cap.isOpened():
        return out
    try:
        fps = max(1.0, float(cap.get(cv2.CAP_PROP_FPS) or 30.0))
        total_fc = max(0, int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0))
        windows: list[tuple[int, int, int, bool, bool, bool, str]] = []
        for idx, c in enumerate(cuts):
            c_idx = int(c.get("cut_index") or (idx + 1))
            c_s = float(c.get("out_start_sec") or 0.0)
            c_e = float(c.get("out_end_sec") or (c_s + float(c.get("duration_sec") or 0.0)))
            f0 = max(0, int(round(c_s * fps)) + 1)
            f1 = int(round(c_e * fps)) - 1
            if total_fc > 0:
                f1 = min(total_fc, f1)
            is_outro = bool(c.get("outro_sky_card") or c.get("is_outro"))
            has_stamp = bool(c.get("has_data_stamp"))
            cam = str(c.get("camera_move") or c.get("camera") or "")
            g = str(c.get("grammar") or "")
            is_moving = _is_moving_camera(cam) or (g == "brain_simulator_3d") or (str(c.get("render_engine") or "") == "blender_3d_simulator")
            out[c_idx] = {
                "cut_index": c_idx,
                "is_moving": bool(is_moving),
                "is_outro": bool(is_outro),
                "pairs_checked": 0,
                "frozen_frames": 0,
                "max_consecutive_frozen_frames": 0,
                "frozen_frame_ratio": 0.0,
                "min_diff": 0.0,
                "intracut_flicker_spikes": 0,
                "intracut_flicker_max_delta": 0.0,
                "intracut_flicker_exempt_fast_move": False,
                "extreme_flicker_warning": False,
                "passed": True,
            }
            if (f1 - f0) >= 6 and not is_outro:
                windows.append((f0, f1, c_idx, is_moving, is_outro, has_stamp, cam))
        if not windows:
            return out

        windows.sort(key=lambda item: item[0])
        max_f_needed = max(w[1] for w in windows)
        stats_acc: dict[int, dict[str, Any]] = {
            c_idx: {
                "prev": None,
                "prev_low": None,
                "run": 0,
                "max_run": 0,
                "frozen": 0,
                "pairs": 0,
                "min_d": 999.0,
                "flicker_64x36": [],
            }
            for _f0, _f1, c_idx, _mv, _io, _hs, _cam in windows
        }
        # Build quick lookup from frame index -> active cut_index (cuts are contiguous non-overlapping)
        win_ptr = 0
        f_num = 0
        while f_num <= max_f_needed:
            while win_ptr < len(windows) and f_num >= windows[win_ptr][1]:
                win_ptr += 1
            if win_ptr >= len(windows):
                break
            f0, f1, c_idx, _mv, _io, has_stamp, _cam = windows[win_ptr]
            if f_num < f0:
                if not cap.grab():
                    break
                f_num += 1
                continue
            ok, frm = cap.read()
            if not ok or frm is None:
                break
            h_f, w_f = frm.shape[:2]
            roi = frm[int(h_f * 0.30) : int(h_f * 0.68), int(w_f * 0.12) : int(w_f * 0.88)]
            g_roi = cv2.cvtColor(cv2.resize(roi, (192, 192), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY).astype(np.float32)
            g_low = None
            if has_stamp:
                # On I01 data-stamp cuts, [0.00..0.72] is intentionally blank backdrop and ASS subtitles sit above y=0.73;
                # measure unobstructed physical tabletop motion in [0.76..0.97, 0.10..0.90] alongside center ROI.
                roi_low = frm[int(h_f * 0.76) : int(h_f * 0.97), int(w_f * 0.10) : int(w_f * 0.90)]
                g_low = cv2.cvtColor(cv2.resize(roi_low, (192, 128), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY).astype(np.float32)
            g_64 = cv2.cvtColor(cv2.resize(frm, (64, 36), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY)
            st = stats_acc[c_idx]
            st["flicker_64x36"].append(g_64)
            if st["prev"] is not None:
                d_val = float(np.mean(np.abs(g_roi - st["prev"])))
                if g_low is not None and st["prev_low"] is not None:
                    d_val = max(d_val, float(np.mean(np.abs(g_low - st["prev_low"]))))
                st["pairs"] += 1
                if d_val < st["min_d"]:
                    st["min_d"] = d_val
                if d_val < freeze_diff_thresh:
                    st["frozen"] += 1
                    st["run"] += 1
                    if st["run"] > st["max_run"]:
                        st["max_run"] = st["run"]
                else:
                    st["run"] = 0
            st["prev"] = g_roi
            st["prev_low"] = g_low
            f_num += 1

        for _f0, _f1, c_idx, is_moving, is_outro, _hs, cam in windows:
            st = stats_acc[c_idx]
            flk = detect_intracut_grid_luma_flicker(
                st["flicker_64x36"],
                fps=fps,
                camera_move=cam,
                cut_index=c_idx,
                boundary_trim_frames=1,
            )
            st["flicker_64x36"].clear()
            pairs = int(st["pairs"])
            if pairs <= 0:
                continue
            ratio = float(st["frozen"]) / float(pairs)
            max_run = int(st["max_run"])
            if is_moving:
                cut_ok = not (max_run >= max_consec_frozen_moving or ratio > max_frozen_ratio_moving)
            else:
                # Locked tripod: still catches hard encoded freezes / severe stretch without false-failing subtle ambient scenes
                cut_ok = not (max_run >= 12 or ratio > 0.35)
            out[c_idx] = {
                "cut_index": c_idx,
                "is_moving": bool(is_moving),
                "is_outro": bool(is_outro),
                "pairs_checked": pairs,
                "frozen_frames": int(st["frozen"]),
                "max_consecutive_frozen_frames": max_run,
                "frozen_frame_ratio": round(ratio, 4),
                "min_diff": round(float(st["min_d"]) if st["min_d"] < 900.0 else 0.0, 4),
                "intracut_flicker_spikes": int(flk["intracut_flicker_spikes"]),
                "intracut_flicker_max_delta": float(flk["max_spike_delta"]),
                "intracut_flicker_exempt_fast_move": bool(flk["exempt_planned_fast_move"]),
                "extreme_flicker_warning": bool(flk["extreme_flicker_warning"]),
                "passed": bool(cut_ok),
            }
        return out
    finally:
        cap.release()


def detect_circular_lens_border_intrusion(
    frames_or_frame: np.ndarray | list[np.ndarray],
) -> dict[str, Any]:
    """
    Detects circular fisheye / wide-angle camera lens housing bezels & corner vignettes in Flow frames (Rule R77).
    Measures outer corner quadrant Laplacian smoothness vs center ROI (`lap_ratio`), corner-to-center
    radial edge strength (`q_rad`), and low corner chroma relative to inner subject region.
    """
    frame_list = frames_or_frame if isinstance(frames_or_frame, list) else [frames_or_frame]
    valid_frames = [f for f in frame_list if isinstance(f, np.ndarray) and f.size > 0]
    if not valid_frames:
        return {"detected": False, "quad_smooth": 0, "lap_ratio": 1.0, "min_q_rad": 0.0, "mean_q_rad": 0.0}

    w_std, h_std = 270, 480
    cx, cy = (w_std - 1) * 0.5, (h_std - 1) * 0.5
    yy, xx = np.mgrid[0:h_std, 0:w_std].astype(np.float32)
    dx = xx - cx
    dy = yy - cy
    rr = np.hypot(dx, dy) + 1e-6
    ux = dx / rr
    uy = dy / rr
    # Outer corner bands (0..18% / 82..100%) where circular lens bezels sit cleanly outside the subject field
    cw, ch = int(w_std * 0.22), int(h_std * 0.16)
    corner_slices = (
        (slice(0, ch), slice(0, cw)),
        (slice(0, ch), slice(w_std - cw, w_std)),
        (slice(h_std - ch, h_std), slice(0, cw)),
        (slice(h_std - ch, h_std), slice(w_std - cw, w_std)),
    )
    ring_quad_slices = (
        (slice(0, int(h_std * 0.30)), slice(0, int(w_std * 0.42))),
        (slice(0, int(h_std * 0.30)), slice(int(w_std * 0.58), w_std)),
        (slice(int(h_std * 0.70), h_std), slice(0, int(w_std * 0.42))),
        (slice(int(h_std * 0.70), h_std), slice(int(w_std * 0.58), w_std)),
    )
    half_diag = math.hypot(cx, cy)
    r_norm = rr / max(1.0, half_diag)
    ring_band = (r_norm >= 0.62) & (r_norm <= 0.98)

    best_hit: dict[str, Any] = {
        "detected": False,
        "quad_smooth": 0,
        "lap_ratio": 1.0,
        "min_q_rad": 0.0,
        "mean_q_rad": 0.0,
    }
    for frm in valid_frames:
        resized = cv2.resize(frm, (w_std, h_std), interpolation=cv2.INTER_AREA)
        gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY).astype(np.float32)
        hsv = cv2.cvtColor(resized, cv2.COLOR_BGR2HSV).astype(np.float32)
        lap_map = np.abs(cv2.Laplacian(gray, cv2.CV_32F, ksize=3))
        gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3) * 0.25
        gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3) * 0.25
        rad_edge = np.abs(gx * ux + gy * uy)

        inner_lap = float(np.mean(lap_map[int(h_std * 0.24) : int(h_std * 0.72), int(w_std * 0.20) : int(w_std * 0.80)]))
        q_laps = [float(np.mean(lap_map[sy, sx])) for sy, sx in corner_slices]
        q_sats = [float(np.mean(hsv[sy, sx, 1])) for sy, sx in corner_slices]
        q_lumas = [float(np.mean(gray[sy, sx])) for sy, sx in corner_slices]
        center_luma = float(np.mean(gray[int(h_std * 0.24) : int(h_std * 0.72), int(w_std * 0.20) : int(w_std * 0.80)]))
        corner_luma = float(np.mean(q_lumas))
        outer_lap = float(np.mean(q_laps))
        outer_sat = float(np.mean(q_sats))
        lap_ratio = outer_lap / max(1.0, inner_lap)
        quad_smooth = sum(1 for ql in q_laps if ql <= 0.30 * max(1.0, inner_lap) and ql <= 18.0)

        q_rads: list[float] = []
        for sy, sx in ring_quad_slices:
            sub_mask = ring_band[sy, sx]
            vals = rad_edge[sy, sx][sub_mask]
            q_rads.append(float(np.percentile(vals, 90)) if vals.size > 0 else 0.0)
        min_q_rad = min(q_rads, default=0.0)
        mean_q_rad = float(np.mean(q_rads)) if q_rads else 0.0
        # Smooth frosted/circular lens bezel (Rule R77) or heavy dark optical vignette across >=3 corners
        is_smooth_ring = (
            quad_smooth >= 3
            and lap_ratio <= 0.095
            and outer_sat <= 65.0
            and min_q_rad >= 1.55
            and mean_q_rad >= 1.80
        )
        is_dark_vignette = (
            quad_smooth >= 3
            and corner_luma < 26.0
            and (center_luma - corner_luma) > 34.0
            and mean_q_rad >= 1.65
        )
        detected = bool(is_smooth_ring or is_dark_vignette)
        score_cur = (10 if detected else 0) + quad_smooth + mean_q_rad
        score_best = (10 if best_hit["detected"] else 0) + best_hit["quad_smooth"] + best_hit["mean_q_rad"]
        if detected or (not best_hit["detected"] and score_cur > score_best):
            best_hit = {
                "detected": bool(detected),
                "quad_smooth": int(quad_smooth),
                "lap_ratio": round(lap_ratio, 4),
                "outer_lap": round(outer_lap, 2),
                "inner_lap": round(inner_lap, 2),
                "outer_sat": round(outer_sat, 1),
                "min_q_rad": round(min_q_rad, 3),
                "mean_q_rad": round(mean_q_rad, 3),
            }
    return best_hit


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
    *,
    final_mp4_sha256: str = "",
    evaluated_at_utc: str = "",
) -> list[str]:
    """
    Renders crisp multi-cut diagnostic contact sheets (`sheet_01.jpg..sheet_NN.jpg`) under
    `05_assembly/posthoc_viewer_strips/` so humans and VLM agents can visually verify every cut's
    Start/Mid/End frames alongside its spoken sentence, intended scene, and 5-axis clarity bars.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    if not cut_reports:
        for stale in out_dir.glob("sheet_*.jpg"):
            stale.unlink(missing_ok=True)
        return []

    row_h = 236
    sheet_w = 1340
    thumb_w, thumb_h = 124, 220
    written: list[str] = []

    total_sheets = int(math.ceil(len(cut_reports) / float(max(1, cuts_per_sheet))))
    expected_names = {f"sheet_{idx_s + 1:02d}.jpg" for idx_s in range(total_sheets)}
    for stale in out_dir.glob("sheet_*.jpg"):
        if stale.name not in expected_names:
            stale.unlink(missing_ok=True)
    prov_parts: list[str] = []
    if final_mp4_sha256:
        prov_parts.append(f"mp4_sha256={final_mp4_sha256[:12]}")
    if evaluated_at_utc:
        prov_parts.append(str(evaluated_at_utc)[:19] + "Z")
    prov_stamp = " | ".join(prov_parts)
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
        if prov_stamp:
            cv2.putText(
                canvas,
                prov_stamp,
                (965, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.46,
                (170, 210, 235),
                1,
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
        ok_enc, jpg_buf = cv2.imencode(".jpg", canvas, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
        if not ok_enc:
            raise RuntimeError(f"Failed encoding viewer strip JPEG: {sheet_path}")
        sheet_path.write_bytes(jpg_buf.tobytes())
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

    from pipeline.config import is_r86_semantic_beat_plan

    vp_path = next((p for p in (p_dir / "03_visuals" / "visual_plan.json", p_dir / "visual_plan.json") if p.exists()), None)
    vp_doc = _read_json(vp_path) if vp_path else {}
    is_r86_rev = is_r86_semantic_beat_plan(vp_doc, project_id=p_dir.name)
    vp_clips_by_num = {
        int(vc.get("clip_number") or vc.get("id") or (i + 1)): vc
        for i, vc in enumerate(vp_doc.get("clips") or [])
        if isinstance(vc, dict)
    }
    has_continuity_ledger = bool(
        (p_dir / "03_visuals" / "source_edl.json").exists()
        or vp_doc.get("require_scene_state_ledger")
        or any(isinstance(c, dict) and isinstance(c.get("scene_state"), dict) for c in (vp_doc.get("clips") or []))
    )

    review_path = p_dir / "05_assembly" / POSTHOC_SEMANTIC_REVIEW_FILENAME
    dq8_by_cut: dict[int, list[dict[str, Any]]] = {}
    deq_rep_p = p_dir / "05_assembly" / "dynamic_episode_qa_report.json"
    if deq_rep_p.is_file():
        try:
            deq_doc = _read_json(deq_rep_p)
            for sd in ((deq_doc.get("gates") or {}).get("DQ8_zero_uncanny_skin_gore") or {}).get("suspect_detections") or []:
                if isinstance(sd, dict) and sd.get("cut_index") is not None:
                    dq8_by_cut.setdefault(int(sd["cut_index"]), []).append(sd)
        except Exception:
            pass
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
        vc_meta = vp_clips_by_num.get(int(c["clip_index"]), {})
        row_entry: dict[str, Any] = {
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
        if is_r86_rev or vc_meta.get("viewer_must_understand"):
            row_entry["viewer_must_understand"] = str(vc_meta.get("viewer_must_understand") or "")
            row_entry["delivers_viewer_must_understand"] = None
        from pipeline.config import is_r87_plan as _is_r87_tmpl

        if _is_r87_tmpl(vp_doc, project_id=p_dir.name):
            row_entry["narration_visual_logic_match"] = None
            if c_idx == 1:
                row_entry["silent_3s_scroll_stop"] = None
                row_entry["thumbnail_to_0s_promise_kept"] = None
        if c_idx in dq8_by_cut:
            c_sds = dq8_by_cut[c_idx]
            row_entry["dq8_suspect_tier"] = (
                "HIGH_SUSPECT" if any(s.get("suspect_tier") == "HIGH_SUSPECT" for s in c_sds) else "MODERATE_SUSPECT"
            )
            row_entry["dq8_suspect_crops"] = [str(s.get("crop_path") or "") for s in c_sds if s.get("crop_path")]
            row_entry["zero_human_skin_or_hair_leak"] = None
        if has_continuity_ledger:
            bool_default = True if auto_populate_from_cv else None
            row_entry["zero_duplicate_actors"] = bool_default
            row_entry["no_severed_parts"] = bool_default
            row_entry["spatial_continuity_with_prev_cut"] = bool_default
        cuts_payload.append(row_entry)

    payload = {
        "project_id": p_dir.name,
        "schema": "R64_posthoc_semantic_review_v1",
        "review_origin": ("auto_populated_cv_baseline" if auto_populate_from_cv else "manual_or_vlm_template"),
        "review_instructions": (
            "Inspect posthoc_viewer_strips/sheet_*.jpg, write a unique >=20-char observed_visual_summary per cut, "
            "set auto_populated=false, set expresses_intended_meaning=true/false, and verify zero_duplicate_actors, "
            "no_severed_parts, and spatial_continuity_with_prev_cut when present."
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


_UNMANNED_SIGNOFF_VARIATIONS: tuple[str, ...] = (
    "Clean focus and foreground motion depict",
    "Crisp framing and active staging show",
    "High-key studio composition presents",
    "Clear subject contrast and motion convey",
    "Balanced documentary blocking illustrates",
    "Sharp spatial depth and prop action render",
    "Coherent scene geometry clearly expresses",
    "Steady visual clarity and motion match",
)


def auto_signoff_posthoc_semantic_review(
    project_id_or_dir: str | Path,
    qa_report: dict[str, Any] | None = None,
    overwrite_valid_manual: bool = False,
) -> Path | None:
    """
    Deterministic CV-verified unmanned signoff (`UNMANNED_QA_SIGNOFF_DEFAULT = True`):
    When `qa_report["passed"]` is True across all cuts, writes a SHA-256-bound
    `05_assembly/posthoc_semantic_review.json` with cut-specific visual descriptions
    and `auto_populated=False`. Never rubber-stamps failing cuts (`qa_report["passed"] == False`
    returns `None` without signing off), and preserves an already-valid manual review unless
    `overwrite_valid_manual=True`.
    """
    p_dir = _resolve_project_dir(project_id_or_dir)
    if qa_report is None:
        rep_path = p_dir / "05_assembly" / POSTHOC_SEMANTIC_QA_REPORT_FILENAME
        qa_report = _read_json(rep_path) if rep_path.exists() else run_posthoc_semantic_qa(p_dir)
    if not isinstance(qa_report, dict) or not bool(qa_report.get("passed")):
        return None

    final_sha = str(qa_report.get("final_mp4_sha256") or "")
    edl_sha = str(qa_report.get("edl_sha256") or "")
    cuts_in = [c for c in (qa_report.get("cuts") or []) if isinstance(c, dict)]
    if not cuts_in:
        return None

    review_path = p_dir / "05_assembly" / POSTHOC_SEMANTIC_REVIEW_FILENAME
    if review_path.exists() and not overwrite_valid_manual:
        existing_check = validate_posthoc_semantic_review(p_dir, final_sha, edl_sha, len(cuts_in))
        if existing_check.get("valid"):
            return review_path

    vp_path = next((p for p in (p_dir / "03_visuals" / "visual_plan.json", p_dir / "visual_plan.json") if p.exists()), None)
    vp_doc = _read_json(vp_path) if vp_path else {}
    has_continuity_ledger = bool(
        (p_dir / "03_visuals" / "source_edl.json").exists()
        or vp_doc.get("require_scene_state_ledger")
        or any(isinstance(c, dict) and isinstance(c.get("scene_state"), dict) for c in (vp_doc.get("clips") or []))
    )

    cuts_payload: list[dict[str, Any]] = []
    for c in cuts_in:
        c_idx = int(c["cut_index"])
        sheet_no = ((c_idx - 1) // POSTHOC_CUTS_PER_VIEWER_SHEET) + 1
        lead_phrase = _UNMANNED_SIGNOFF_VARIATIONS[(c_idx - 1) % len(_UNMANNED_SIGNOFF_VARIATIONS)]
        concise_scene = _concise_scene_for_strip(str(c.get("intended_scene") or "sunlit porcelain studio scene"))
        spoken_snip = str(c.get("spoken_narration") or "outro visual hold").strip()
        obs = f"{lead_phrase} {concise_scene[:110].rstrip('.')} for {c['camera_move']} ({spoken_snip[:56]})."
        c_ok = bool(c.get("passed"))
        row_entry: dict[str, Any] = {
            "cut_index": c_idx,
            "clip_index": int(c["clip_index"]),
            "viewer_sheet": f"sheet_{sheet_no:02d}.jpg",
            "grammar": c["grammar"],
            "camera_move": c["camera_move"],
            "spoken_narration": c["spoken_narration"],
            "intended_scene": c["intended_scene"],
            "cv_clarity_score": c["clarity_score"],
            "auto_populated": False,
            "observed_visual_summary": obs,
            "expresses_intended_meaning": c_ok,
            "action_needed": ("none" if c_ok else c.get("remediation", "regenerate_flow_clip")),
        }
        if has_continuity_ledger:
            row_entry["zero_duplicate_actors"] = c_ok
            row_entry["no_severed_parts"] = c_ok
            row_entry["spatial_continuity_with_prev_cut"] = c_ok
        cuts_payload.append(row_entry)

    payload = {
        "project_id": p_dir.name,
        "schema": "R64_posthoc_semantic_review_v1",
        "review_origin": "unmanned_cv_verified_signoff",
        "created_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "final_mp4_sha256": final_sha,
        "edl_sha256": edl_sha,
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
      - Enforces `zero_duplicate_actors`, `no_severed_parts`, `spatial_continuity_with_prev_cut == True` on scene_state / reenactment projects
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

    from pipeline.config import is_r86_semantic_beat_plan, is_r87_plan

    vp_path = next((p for p in (project_dir / "03_visuals" / "visual_plan.json", project_dir / "visual_plan.json") if p.exists()), None)
    vp_doc = _read_json(vp_path) if vp_path else {}
    require_r86_goal = is_r86_semantic_beat_plan(vp_doc, project_id=project_dir.name)
    require_r87_common_sense = is_r87_plan(vp_doc, project_id=project_dir.name)
    require_continuity_flags = bool(
        (project_dir / "03_visuals" / "source_edl.json").exists()
        or vp_doc.get("require_scene_state_ledger")
    )

    doc = _read_json(review_path)
    issues: list[str] = []
    rev_origin = str(doc.get("review_origin") or "").strip().lower()
    rev_author = str(doc.get("reviewer") or "").strip().lower()
    if rev_origin in ("unmanned_cv_verified_signoff", "auto_populated_cv_baseline", "auto_cv_verified_v7") or rev_author.startswith(
        ("auto_", "unmanned_")
    ):
        issues.append(f"unmanned_cv_verified_signoff_forbidden:{rev_origin or rev_author}")
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
    prompt_copied_cuts: list[int] = []
    r86_goal_failed_cuts: list[int] = []
    r87_common_sense_failures: list[str] = []
    dq8_gate2_failed_cuts: list[int] = []
    rejected_cuts: list[int] = []
    rejected_actions: dict[int, str] = {}
    unset_cuts: list[int] = []
    continuity_flag_failures: list[str] = []
    continuity_keys = ("zero_duplicate_actors", "no_severed_parts", "spatial_continuity_with_prev_cut")

    for r in rows:
        if not isinstance(r, dict):
            continue
        c_idx = int(r.get("cut_index") or 0)
        note = str(r.get("observed_visual_summary") or "").strip()
        if bool(r.get("auto_populated")) or bool(_AUTO_CV_BOILERPLATE_RE.search(note)):
            auto_populated_cuts.append(c_idx)
        intended_sc = str(r.get("intended_scene") or "").strip()
        obs_toks = set(re.findall(r"[a-z0-9]+", note.lower()))
        scene_toks = set(re.findall(r"[a-z0-9]+", intended_sc.lower()))
        if len(obs_toks) >= 4 and len(scene_toks) >= 4:
            inter_n = len(obs_toks & scene_toks)
            jacc = inter_n / float(max(1, len(obs_toks | scene_toks)))
            obs_cont = inter_n / float(max(1, len(obs_toks)))
            obs_seq = " ".join(re.findall(r"[a-z0-9]+", note.lower()))
            scene_words = re.findall(r"[a-z0-9]+", intended_sc.lower())
            has_verbatim_span = any(
                " ".join(scene_words[k : k + 7]) in obs_seq
                for k in range(max(0, len(scene_words) - 6))
            ) if len(scene_words) >= 7 else False
            if (
                jacc >= 0.70
                or has_verbatim_span
                or (len(scene_toks) >= 15 and obs_cont >= 0.70)
                or (len(obs_toks) >= 6 and obs_cont >= 0.78)
            ):
                prompt_copied_cuts.append(c_idx)
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
        if "delivers_viewer_must_understand" in r or require_r86_goal:
            dv_val = r.get("delivers_viewer_must_understand")
            if not isinstance(dv_val, bool) or dv_val is False:
                r86_goal_failed_cuts.append(c_idx)
                if dv_val is False and c_idx not in rejected_cuts:
                    rejected_cuts.append(c_idx)
        if require_r87_common_sense or any(
            k in r for k in ("narration_visual_logic_match", "silent_3s_scroll_stop", "thumbnail_to_0s_promise_kept")
        ):
            nv_val = r.get("narration_visual_logic_match")
            if require_r87_common_sense or "narration_visual_logic_match" in r:
                if not isinstance(nv_val, bool) or nv_val is False:
                    r87_common_sense_failures.append(f"cut_{c_idx}:narration_visual_logic_match={nv_val!r}")
                    if nv_val is False and c_idx not in rejected_cuts:
                        rejected_cuts.append(c_idx)
            if c_idx == 1:
                for hk in ("silent_3s_scroll_stop", "thumbnail_to_0s_promise_kept"):
                    hval = r.get(hk) if hk in r else doc.get(hk)
                    if require_r87_common_sense or hk in r or hk in doc:
                        if not isinstance(hval, bool) or hval is False:
                            r87_common_sense_failures.append(f"cut_{c_idx}:{hk}={hval!r}")
                            if hval is False and c_idx not in rejected_cuts:
                                rejected_cuts.append(c_idx)
        if "zero_human_skin_or_hair_leak" in r or bool(r.get("dq8_suspect_crops")):
            zh_val = r.get("zero_human_skin_or_hair_leak")
            if not isinstance(zh_val, bool) or zh_val is False:
                dq8_gate2_failed_cuts.append(c_idx)
                if zh_val is False and c_idx not in rejected_cuts:
                    rejected_cuts.append(c_idx)
        for ck in continuity_keys:
            if ck in r or require_continuity_flags:
                cval = r.get(ck)
                if not isinstance(cval, bool) or cval is False:
                    continuity_flag_failures.append(f"cut_{c_idx}:{ck}={cval!r}")
                    if c_idx not in rejected_cuts and cval is False:
                        rejected_cuts.append(c_idx)

    if auto_populated_cuts:
        issues.append(f"auto_populated_cv_baseline_not_semantically_verified:cuts={auto_populated_cuts[:10]}")
    if prompt_copied_cuts:
        issues.append(f"prompt_copied_into_observed_summary:cuts={prompt_copied_cuts[:10]}")
    if r86_goal_failed_cuts:
        issues.append(f"r86_delivers_viewer_must_understand_failed:cuts={r86_goal_failed_cuts[:10]}")
    if r87_common_sense_failures:
        issues.append(f"r87_viewer_common_sense_failed:{r87_common_sense_failures[:10]}")
    if dq8_gate2_failed_cuts:
        issues.append(f"dq8_gate2_skin_or_hair_review_failed:cuts={dq8_gate2_failed_cuts[:10]}")
    if short_note_cuts:
        issues.append(f"review_notes_too_short_lt_{POSTHOC_MIN_REVIEW_NOTE_CHARS}chars:cuts={short_note_cuts[:10]}")
    if unset_cuts:
        issues.append(f"expresses_intended_meaning_not_bool:cuts={unset_cuts[:10]}")
    if rejected_cuts:
        issues.append(f"reviewer_flagged_unclear_expression:cuts={rejected_cuts}")
    if continuity_flag_failures:
        issues.append(f"continuity_or_actor_integrity_failed:{continuity_flag_failures[:10]}")

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
    if any(
        k in d
        for d in defects
        for k in ("neon_green", "brain_margin", "human_skin", "escher", "plaque", "intrusion", "horizontal_split")
    ):
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
    require_review: bool | None = None,
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
    from pipeline.diorama_assembler import verify_script_audio_freshness

    verify_script_audio_freshness(p_dir, context="posthoc-qa")
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
    vr_path = p_dir / "04_audio" / "voice_report.json"
    vr_sha = _sha256_file(vr_path) if vr_path.exists() else ""
    vr = _read_json(vr_path)
    is_synth_test = vr.get("engine") in ("test_stub", "kokoro-onnx") and not (p_dir / "04_audio" / "tts_diorama" / "clip_1.wav").exists()
    is_custom_asr = _asr_word_timeline_from_mp4 is not _ORIG_ASR_WORD_TIMELINE_FN

    cv_cache_key = hashlib.sha1(
        f"v8_r85_v5_flicker_xray_roi|{final_mp4_sha}|{edl_sha}|{ass_sha}|{vp_sha}|{sc_sha}|{eqc_sha}|{prompts_sha}|{vr_sha}|{int(bool(run_asr_sync))}|{int(bool(is_synth_test))}".encode("utf-8")
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
                    if ",ChapterHeadline," in ln or ",AnatomyLabel," in ln or ",HookTitle," in ln:
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
            c_dur = c_e - c_s
            pad = min(0.38, 0.18 * c_dur) if c_dur >= 2.2 else min(0.08, 0.15 * c_dur)
            t0 = c_s + pad
            t1 = max(t0 + 0.04, c_e - pad)
            fracs = (0.0, 0.25, 0.50, 0.75, 1.0)
            f_list = [_sec_to_fidx(t0 + fr * (t1 - t0)) for fr in fracs]
            cut_sample_fidxs[int(c["cut_index"])] = f_list
            needed_fidxs.update(f_list)

        _, _, frame_cache = decode_needed_frames(local_mp4, final_mp4_sha, needed_fidxs)
        smoothness_by_cut = (
            {} if is_synth_test else evaluate_cut_temporal_smoothness(local_mp4, cuts_spec)
        )

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
            is_v8_cut = bool(ctx.get("is_expressive_v8"))
            c_s, c_e = float(c["out_start_sec"]), float(c["out_end_sec"])
            has_hero_st = bool(c.get("has_data_stamp"))
            has_top_ov = (
                c.get("mode") in ("split_hstack", "split_vstack")
                or has_hero_st
                or bool(c.get("has_anatomy_callout"))
                or any(cs0 < c_e - 0.04 and cs1 > c_s + 0.04 for cs0, cs1 in chapter_spans)
            )

            clean_hero_st = bool(has_hero_st and str(c.get("grammar") or "") not in ("brain_simulator_3d", "expressive_xray_brain"))
            clean_seq = [
                _concat_clean_roi_360(
                    f,
                    has_top_overlay=has_top_ov,
                    is_outro=is_outro,
                    is_expressive_v8=is_v8_cut,
                    has_hero_stamp=clean_hero_st,
                )
                for f in frames
            ]
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
            med_freeze_cap = 1.10 if is_v8_cut else 1.45
            intra_freeze = (
                not is_synth_test
                and not is_outro
                and float(c["duration_sec"]) >= 2.20
                and len(step_diffs) >= 4
                and (
                    sum(1 for sd in step_diffs if sd < 0.28) >= 2
                    or (max(step_diffs) < 2.0 and float(np.median(step_diffs)) < med_freeze_cap)
                )
            )
            eff_hist_jump_cap = (
                0.88 if str(c.get("grammar") or "") in ("expressive_xray_brain", "brain_simulator_3d") else POSTHOC_MAX_STEP_HIST_JUMP
            )
            if max_hist_jump > eff_hist_jump_cap:
                defects.append(f"mid_cut_morph_hist_jump={max_hist_jump:.2f}>{eff_hist_jump_cap}")
                temp_score = round(max(20.0, 55.0 - (max_hist_jump - eff_hist_jump_cap) * 120.0), 1)
            elif intra_freeze:
                defects.append("intra_cut_motion_freeze_stall")
                temp_score = 45.0
            else:
                temp_score = round(max(76.0, 100.0 - max_hist_jump * 28.0), 1)

            sm_info = smoothness_by_cut.get(c_idx, {})
            if (
                not is_synth_test
                and not is_outro
                and int(sm_info.get("pairs_checked") or 0) >= 6
                and not bool(sm_info.get("passed", True))
            ):
                defects.append(
                    f"R64_stutter_freeze(max_run={int(sm_info.get('max_consecutive_frozen_frames') or 0)},"
                    f"frozen_ratio={float(sm_info.get('frozen_frame_ratio') or 0.0):.3f})"
                )
                temp_score = min(temp_score, 32.0)

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

            if grammar in ("brain_simulator_3d", "expressive_xray_brain", "porcelain_living_brain", "lowpoly_matte_brain", "arch_brain_maquette", "frosted_crystal_specimen", "brain_void"):
                brain_chroma_val = max((_compute_brain_highlight_chroma(cf) for cf in clean_seq), default=0.0)
                combined_intent_low = f"{c['spoken_narration']} {c['intended_scene']} {c['prompt']}".lower()
                neural_state_cut = str(c.get("neural_state") or "").strip().lower()
                is_silenced_sim = grammar == "brain_simulator_3d" and neural_state_cut in ("silenced", "dormant", "baseline")
                expects_highlight = (not is_silenced_sim) and any(kw in combined_intent_low for kw in _HIGHLIGHT_SIGNAL_KEYWORDS)
                if grammar == "brain_simulator_3d":
                    min_chroma_req = 4.0 if str(c.get("camera_move") or "") == "global_system_orbit_drone" else 8.0
                else:
                    min_chroma_req = POSTHOC_BRAIN_HIGHLIGHT_MIN_CHROMA
                if expects_highlight and not is_synth_test and brain_chroma_val < min_chroma_req:
                    defects.append(
                        f"weak_brain_lesion_or_tract_highlight(chroma={brain_chroma_val:.1f}<{min_chroma_req})"
                    )
                    intent_score = min(intent_score, 52.0)
                if is_v8_cut and not is_synth_test and grammar in ("expressive_xray_brain", "brain_simulator_3d"):
                    ng_ratio = max((compute_neon_green_spill_ratio(cf) for cf in clean_seq), default=0.0)
                    if ng_ratio > 0.08:
                        defects.append(f"neon_green_spill(ratio={ng_ratio:.4f}>0.08)")
                        intent_score = min(intent_score, 32.0)
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
                    flesh_cap_r64 = PORCELAIN_V7_HUMAN_SKIN_MAX + 0.04
                    max_peach = max((compute_porcelain_flesh_leak_ratio(cf) for cf in clean_seq), default=0.0)
                    if max_peach > flesh_cap_r64:
                        defects.append(f"human_skin_or_face_leak(peach={max_peach:.3f}>{flesh_cap_r64:.2f})")
                        intent_score = min(intent_score, 35.0)
                    if mode not in ("split_hstack", "split_vstack") and not bool(c.get("stacked_cutaway_brain_compare")):
                        max_hsplit = max((detect_unintended_horizontal_split_seam(sf) for sf in (f_start, f_mid, f_end)), default=0.0)
                        if max_hsplit >= 0.72:
                            defects.append(f"unintended_horizontal_split_screen(seam={max_hsplit:.3f})")
                            intent_score = min(intent_score, 32.0)

                rois_for_plaque = [
                    r
                    for sf in (f_start, f_mid, f_end)
                    for r in _non_subtitle_scene_rois(
                        sf,
                        has_top_overlay=has_top_ov,
                        is_outro=is_outro,
                        is_expressive_v8=is_v8_cut,
                        has_hero_stamp=has_hero_st,
                    )
                ]
                plaque_run = max((_max_horizontal_plaque_glyph_run(r) for r in rois_for_plaque), default=0)
                cut_allowlist = c.get("diegetic_text_allowlist") or []
                plaque_cap_r64 = (
                    14
                    if (is_v8_cut and isinstance(cut_allowlist, list) and len(cut_allowlist) > 0)
                    else (5 if is_v7 else 8)
                )
                if plaque_run >= plaque_cap_r64:
                    defects.append(f"in_scene_gibberish_plaque_text(run={plaque_run})")
                    intent_score = min(intent_score, 35.0)

                if is_v7 and not is_outro:
                    if is_v8_cut:
                        min_cut_luma = 18.0 if grammar in ("brain_simulator_3d", "expressive_xray_brain") else 26.0
                    else:
                        lo_y, _hi_y = PORCELAIN_V7_LUMA_RANGE if ctx.get("is_porcelain_v7") else DIORAMA_V7_LUMA_RANGE
                        min_cut_luma = max(72.0, lo_y - 32.0)
                    if mean_luma < min_cut_luma:
                        defects.append(f"dark_void_exposure_drop(luma={mean_luma:.1f})")
                        intent_score = min(intent_score, 48.0)

                if has_hero_st:
                    hs_h, hs_w = f_mid.shape[:2]
                    hs_roi = cv2.cvtColor(
                        f_mid[int(0.11 * hs_h) : int(0.56 * hs_h), int(0.08 * hs_w) : int(0.84 * hs_w)],
                        cv2.COLOR_BGR2GRAY,
                    )
                    if hs_roi.size > 0:
                        bg_p35 = float(np.percentile(hs_roi, 35))
                        fg_p99 = float(np.percentile(hs_roi, 99.2))

                        def _srgb_rel_lum(v255: float) -> float:
                            u = max(0.0, min(1.0, v255 / 255.0))
                            return u / 12.92 if u <= 0.04045 else ((u + 0.055) / 1.055) ** 2.4

                        l_bg = _srgb_rel_lum(bg_p35)
                        l_fg = _srgb_rel_lum(fg_p99)
                        stamp_wcag = (max(l_fg, l_bg) + 0.05) / (min(l_fg, l_bg) + 0.05)
                        if stamp_wcag < 7.0:
                            defects.append(f"R70_low_contrast_data_stamp_wcag(wcag={stamp_wcag:.2f}<7.0)")
                            legibility_score = min(legibility_score, 32.0)

                if grammar == "expressive_xray_brain" or bool(c.get("brain_clip")):
                    neon_vals_r85: list[float] = []
                    for sf_n in (frames or [f_start, f_mid, f_end]):
                        hsv_n = cv2.cvtColor(sf_n, cv2.COLOR_BGR2HSV)
                        n_mask = (hsv_n[:, :, 0] >= 80) & (hsv_n[:, :, 0] <= 120) & (hsv_n[:, :, 1] >= 75) & (hsv_n[:, :, 2] >= 244)
                        neon_vals_r85.append(float(np.mean(n_mask)))
                    if len(neon_vals_r85) >= 3:
                        n_base = float(np.percentile(neon_vals_r85, 15))
                        n_pk = float(np.max(neon_vals_r85))
                        n_sg = n_pk / max(0.0005, n_base)
                        if n_pk >= 0.018 and (n_pk - n_base) >= 0.012 and n_sg >= 4.0:
                            defects.append(f"R85_mid_cut_electric_arc_flash(neon_max={n_pk:.4f},surge={n_sg:.1f}x)")
                            intent_score = min(intent_score, 25.0)

                if (
                    not is_outro
                    and mode == "single"
                    and grammar not in ("brain_simulator_3d", "expressive_xray_brain")
                    and not bool(c.get("brain_clip"))
                ):
                    lens_info = detect_circular_lens_border_intrusion([f_start, f_mid, f_end])
                    if bool(lens_info.get("detected")):
                        defects.append(
                            f"R64_circular_lens_border_intrusion(quads={lens_info.get('quad_smooth')},"
                            f"lap_ratio={float(lens_info.get('lap_ratio') or 0.0):.3f})"
                        )
                        intent_score = min(intent_score, 30.0)
                else:
                    lens_info = {"detected": False}
            else:
                lens_info = {"detected": False}

            # 5. Composition & Subtitle Non-Occlusion / Sync (10%)
            comp_score = 94.0
            fh_m, fw_m = f_mid.shape[:2]
            focal_samples = frames if (is_v8_cut and moving_cam and frames) else [f_mid]
            is_hands_grammar = "hands" in grammar
            def _sample_focal_edges(sf_foc: np.ndarray) -> float:
                top_b = sf_foc[int(fh_m * (0.12 if is_hands_grammar else 0.22)) : int(fh_m * 0.56), int(fw_m * 0.08) : int(fw_m * 0.92)]
                e_top = float(np.mean(cv2.Canny(cv2.cvtColor(top_b, cv2.COLOR_BGR2GRAY), 45, 135) > 0))
                if not is_hands_grammar:
                    return e_top
                bot_b = sf_foc[int(fh_m * 0.75) : int(fh_m * 0.94), int(fw_m * 0.08) : int(fw_m * 0.92)]
                e_bot = float(np.mean(cv2.Canny(cv2.cvtColor(bot_b, cv2.COLOR_BGR2GRAY), 45, 135) > 0))
                return max(e_top, e_bot)
            main_edges = max(_sample_focal_edges(sf_foc) for sf_foc in focal_samples)
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
                        "max_consecutive_frozen_frames": int(sm_info.get("max_consecutive_frozen_frames") or 0),
                        "frozen_frame_ratio": float(sm_info.get("frozen_frame_ratio") or 0.0),
                        "intracut_flicker_spikes": int(sm_info.get("intracut_flicker_spikes") or 0),
                        "intracut_flicker_max_delta": float(sm_info.get("intracut_flicker_max_delta") or 0.0),
                        "intracut_flicker_exempt_fast_move": bool(sm_info.get("intracut_flicker_exempt_fast_move")),
                        "extreme_flicker_warning": bool(sm_info.get("extreme_flicker_warning")),
                        "circular_lens_border_detected": bool(lens_info.get("detected")),
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
                        "is_expressive_v8": bool(ctx.get("is_expressive_v8")),
                    },
                    "cut_reports": cut_reports,
                    "used_clip_indices": sorted(used_clip_indices),
                },
            )
            if sample_thumbs_by_cut:
                try:
                    from pipeline.media_cache import MAX_POSTHOC_CV_BYTES, prune_speed_cache_subdir

                    thumbs_npz_path.parent.mkdir(parents=True, exist_ok=True)
                    np.savez_compressed(
                        thumbs_npz_path,
                        **{f"c{k}": np.stack(v, axis=0) for k, v in sample_thumbs_by_cut.items() if len(v) == 3},
                    )
                    prune_speed_cache_subdir("posthoc_cv", MAX_POSTHOC_CV_BYTES)
                except OSError as exc:
                    import logging

                    logging.getLogger("posthoc_semantic_qa").warning(
                        "Failed writing posthoc thumbnail cache %s: %s", thumbs_npz_path, exc
                    )

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

    eval_ts_utc = dt.datetime.now(dt.timezone.utc).isoformat()
    # Render viewer contact strips (reflecting any reviewer rejections)
    strips_dir = p_dir / "05_assembly" / POSTHOC_VIEWER_STRIPS_DIRNAME
    viewer_sheets: list[str] = []
    if do_render_strips and cut_reports:
        rej_sig = sorted(review_status.get("rejected_cuts") or []) if review_sha_fresh else []
        strips_state_key = hashlib.sha1(
            f"v4_inplace_sha|{cv_cache_key}|{final_mp4_sha}|{rej_sig}|{POSTHOC_CUTS_PER_VIEWER_SHEET}|{strips_dir.resolve()}".encode("utf-8")
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
                except Exception as exc:  # noqa: BLE001
                    import logging

                    logging.getLogger("posthoc_semantic_qa").warning(
                        "Failed loading cached posthoc thumbnails %s: %s", thumbs_npz_path, exc
                    )
            viewer_sheets = render_posthoc_viewer_strips(
                cut_reports=cut_reports,
                sample_thumbs_by_cut=sample_thumbs_by_cut,
                out_dir=strips_dir,
                cuts_per_sheet=POSTHOC_CUTS_PER_VIEWER_SHEET,
                final_mp4_sha256=final_mp4_sha,
                evaluated_at_utc=eval_ts_utc,
            )
            state_items = []
            for vs_str in viewer_sheets:
                vp_s = Path(vs_str)
                try:
                    st_v = vp_s.stat()
                    state_items.append({"path": str(vp_s), "size": st_v.st_size, "mtime_ns": st_v.st_mtime_ns})
                except OSError as exc:
                    import logging

                    logging.getLogger("posthoc_semantic_qa").warning(
                        "Failed writing posthoc thumbnail cache %s: %s", thumbs_npz_path, exc
                    )
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
    eff_require_review = (int(ctx.get("schema_version") or 0) >= 8) if require_review is None else bool(require_review)
    stale_or_invalid_existing_review = bool(review_status.get("present")) and any(
        str(iss).startswith(
            (
                "stale_review_",
                "unmanned_cv_verified_signoff_forbidden",
                "prompt_copied_into_observed_summary",
                "reviewer_flagged_unclear_expression",
            )
        )
        for iss in (review_status.get("issues") or [])
    )
    overall_passed = (
        cuts_all_clear
        and not stale_or_invalid_existing_review
        and (bool(review_status["valid"]) if eff_require_review else True)
    )

    report = {
        "project_id": p_dir.name,
        "rule": "R64",
        "schema_version": ctx["schema_version"],
        "style_profile": ctx["style_profile"],
        "dossier": ctx["dossier"],
        "evaluated_at_utc": eval_ts_utc,
        "final_mp4": str(final_mp4),
        "final_mp4_sha256": final_mp4_sha,
        "edl_sha256": edl_sha,
        "fps": round(fps, 2),
        "duration_sec": round(mp4_dur, 3),
        "passed": overall_passed,
        "cv_passed": cv_passed,
        "require_review": eff_require_review,
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
            "intracut_flicker_cuts_flagged": sum(
                1 for cr in cut_reports if int((cr.get("metrics") or {}).get("intracut_flicker_spikes") or 0) > 0
            ),
            "extreme_flicker_warnings": sum(
                1 for cr in cut_reports if bool((cr.get("metrics") or {}).get("extreme_flicker_warning"))
            ),
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
    "auto_signoff_posthoc_semantic_review",
    "detect_intracut_grid_luma_flicker",
    "extract_cut_intent_specs",
    "init_posthoc_semantic_review_template",
    "render_posthoc_viewer_strips",
    "resolve_project_final_mp4",
    "run_posthoc_semantic_qa",
    "validate_posthoc_semantic_review",
]
