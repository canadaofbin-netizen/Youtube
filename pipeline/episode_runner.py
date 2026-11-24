"""
ALL ABOUT BRAIN — Fresh-Room Episode Production State Machine (`pipeline/episode_runner.py`).
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from pipeline.batch_runner import (
    has_pending_human_flow_clips,
    lock_episode_audio_and_edl_frames,
)
from pipeline.config import FLOW_MAX_PARALLEL_BATCH_SIZE, PROJECTS_DIR
from pipeline.flow_worker import run_sharded_diorama_flow_generation


def _resolve_root_mp4_path(p_dir: Path, pid: str) -> Path:
    from pipeline.config import PROJECTS_DIR, WORKSPACE_ROOT

    try:
        if p_dir.parent.resolve() == Path(PROJECTS_DIR).resolve():
            return Path(WORKSPACE_ROOT) / f"final_shorts_{pid}.mp4"
    except OSError:
        pass
    if p_dir.parent.name == "projects" and p_dir.parent.parent.name == "BCI_Shorts_Channel":
        return p_dir.parent.parent.parent / f"final_shorts_{pid}.mp4"
    return p_dir.parent / f"final_shorts_{pid}.mp4"


def get_episode_status(project_id_or_dir: str | Path) -> dict[str, Any]:
    """
    Compact `<= 1 KB` episode state-machine probe (`main.py ep status <project_id>`).
    Replaces ad-hoc `python -c` filesystem/JSON state checks across all 5 Gears.
    """
    cand = Path(project_id_or_dir)
    p_dir = cand if cand.is_dir() else (Path(PROJECTS_DIR) / str(project_id_or_dir).strip())
    pid = p_dir.name
    if not p_dir.exists():
        return {"project_id": pid, "exists": False, "stage": "missing"}

    def _jload(rel_p: str) -> dict[str, Any]:
        fp = p_dir / rel_p
        if fp.is_file():
            try:
                d = json.loads(fp.read_text(encoding="utf-8"))
                return d if isinstance(d, dict) else {}
            except Exception:
                return {}
        return {}

    sc_doc = _jload("02_script/script.json")
    vp_doc = _jload("03_visuals/visual_plan.json")
    clips_total = len(vp_doc.get("clips") or [])
    ref_dir = p_dir / "03_visuals" / "reference_images"
    refs_count = len(list(ref_dir.glob("*.png"))) if ref_dir.is_dir() else 0
    ref_qa = _jload("03_visuals/reference_images/reference_image_qa_report.json") or _jload("03_visuals/reference_image_qa_report.json")
    gate1_ready = bool(ref_qa.get("pre_generation_ready"))
    gate1_cv_ok = bool(ref_qa.get("cv_pre_generation_ready"))

    flow_dir = p_dir / "03_visuals" / "flow_native_clips"
    clips_done = len([p for p in flow_dir.glob("clip_*.mp4") if p.stat().st_size >= 10_000]) if flow_dir.is_dir() else 0
    audio_ok = (p_dir / "04_audio" / "audio_master.wav").is_file()
    final_mp4 = p_dir / "05_assembly" / "final_shorts_1080x1920.mp4"
    mp4_ok = final_mp4.is_file() and final_mp4.stat().st_size >= 50_000

    ep_qa = _jload("05_assembly/dynamic_episode_qa_report.json")
    ph_qa = _jload("05_assembly/posthoc_semantic_qa_report.json")
    aut_qa = _jload("05_assembly/video_autopsy_report.json")
    th_qa = _jload("06_publish/thumbnail_report.json")
    pub_rec = _jload("06_publish/upload_receipt.json")
    root_mp4 = _resolve_root_mp4_path(p_dir, pid)

    tier1_ok = bool(mp4_ok and ep_qa.get("passed") and aut_qa.get("passed") and ph_qa.get("cv_passed", ph_qa.get("passed")))
    gate2_ready = bool(tier1_ok and ph_qa.get("passed"))

    if pub_rec.get("video_id"):
        stage = f"published:{pub_rec.get('visibility') or pub_rec.get('status') or 'live'}"
    elif gate2_ready and th_qa.get("passed") and root_mp4.is_file():
        stage = "ready_to_publish"
    elif gate2_ready:
        stage = "gate2_passed_pending_packaging"
    elif tier1_ok and not gate2_ready:
        stage = "gate2_review_pending"
    elif mp4_ok and not tier1_ok:
        stage = "assembled_qa_pending"
    elif clips_total > 0 and clips_done >= clips_total and not mp4_ok:
        stage = "ready_to_assemble"
    elif gate1_ready and clips_done < clips_total:
        stage = "flow_clips_in_progress"
    elif gate1_ready:
        stage = "gate1_passed_ready_for_flow"
    elif refs_count > 0 and not gate1_ready:
        stage = "gate1_review_pending" if gate1_cv_ok else "gate1_qa_failed"
    elif sc_doc and vp_doc:
        stage = "script_and_plan_ready"
    else:
        stage = "initialized"

    return {
        "project_id": pid,
        "exists": True,
        "stage": stage,
        "sentences": len(sc_doc.get("sentences") or []),
        "refs_png": refs_count,
        "gate1_ok": gate1_ready,
        "flow_clips": f"{clips_done}/{clips_total}",
        "audio_ok": audio_ok,
        "final_mp4_ok": mp4_ok,
        "tier1_qa_ok": tier1_ok,
        "gate2_ok": gate2_ready,
        "thumbnail_ok": bool(th_qa.get("passed")),
        "root_mp4_ok": root_mp4.is_file(),
        "video_id": pub_rec.get("video_id"),
    }


def run_episode_until(
    project_id: str,
    *,
    until: str = "ready",
    cdp_port: int = 9222,
    tabs: int = FLOW_MAX_PARALLEL_BATCH_SIZE,
    engine_mode: str = "auto",
) -> dict[str, Any]:
    """
    Deterministic `Fresh-Room` episode state-machine runner (`main.py ep run <id> --until gate1|gate2|ready`).
    Automatically executes deterministic CLI/pipeline steps and pauses cleanly at `Gate 1` or `Gate 2`
    with `12-up` sheet paths whenever independent visual review is required.
    """
    import re as _re
    import shutil
    import subprocess
    import sys

    from pipeline.config import PRE_R68H_FROZEN_V8_PROJECTS, WORKSPACE_ROOT, is_expressive_v8_plan

    cand = Path(project_id)
    p_dir = cand if cand.is_dir() else (Path(PROJECTS_DIR) / str(project_id).strip())
    pid = p_dir.name
    if not p_dir.exists():
        raise FileNotFoundError(f"Project directory not found: {p_dir}")
    if (p_dir / "06_publish" / "upload_receipt.json").is_file():
        raise RuntimeError(f"Refusing to mutate published project {pid}")

    # 1. Prompt-Gate validation + Episode QA contract compilation
    from pipeline import research_dossier as rd
    from pipeline.batch_runner import _PLAQUE_TRIGGER_NOUNS_RE
    from pipeline.cli import _load_gate_inputs
    from pipeline.episode_qa import write_episode_qa_contract
    from pipeline.prompt_builder import build_flow_prompts, is_diorama_v6_plan, validate_flow_credit_safety_lint
    from pipeline.prompt_gate import validate_production_diorama_v6
    from pipeline.publish import validate_diorama_paradox_title, validate_v8_viewer_description

    plan, narrations, script_doc = _load_gate_inputs(p_dir)
    built_clips = build_flow_prompts(plan, narrations)
    is_v8_gate = is_expressive_v8_plan(plan, script_doc)
    pg_issues = list(validate_production_diorama_v6(plan, narrations, built_clips, script_doc=script_doc))
    pg_issues.extend(validate_flow_credit_safety_lint(plan, built_clips))
    raw_title = str(script_doc.get("title") or plan.get("title") or "").strip()
    if raw_title:
        pg_issues.extend(validate_diorama_paradox_title(raw_title, is_expressive_v8=is_v8_gate))
    if is_v8_gate and pid not in PRE_R68H_FROZEN_V8_PROJECTS:
        meta_gate_path = next(
            (p for p in (p_dir / "06_publish" / "metadata.json", p_dir / "metadata.json") if p.exists()),
            None,
        )
        if meta_gate_path is not None:
            meta_gate_doc = json.loads(meta_gate_path.read_text(encoding="utf-8"))
            if isinstance(meta_gate_doc, dict) and "description" in meta_gate_doc:
                for desc_err in validate_v8_viewer_description(
                    str(meta_gate_doc.get("description") or ""),
                    project_id=pid,
                ):
                    if desc_err not in pg_issues:
                        pg_issues.append(desc_err)
    for c in built_clips:
        sc = _re.sub(r"\b(?:without|zero|no)\s+[a-z\s,-]{1,35}", " ", str(c.get("scene") or ""), flags=_re.IGNORECASE)
        for allow_tok in (c.get("diegetic_text_allowlist") or []):
            if str(allow_tok or "").strip():
                sc = _re.sub(_re.escape(str(allow_tok).strip()), " ", sc, flags=_re.IGNORECASE)
        hits = sorted({m.group(0).lower() for m in _PLAQUE_TRIGGER_NOUNS_RE.finditer(sc)})
        if hits:
            pg_issues.append(f"[plaque_lock] clip {c['clip_number']} positive scene contains plaque-trigger word(s) {hits}")
    if plan.get("dossier") and rd.dossier_dir(str(plan["dossier"])).exists():
        pg_issues.extend(rd.check_narration_facts(str(plan["dossier"]), narrations))
    if pg_issues:
        return {"project_id": pid, "status": "PROMPT_GATE_FAILED", "issues": pg_issues[:10]}
    if is_diorama_v6_plan(plan):
        write_episode_qa_contract(p_dir, plan, narrations, built_clips, script_doc=script_doc)

    # 2. Reference Pack & Gate 1 check (idempotent partial-pack completion)
    from pipeline.reference_pack import ensure_porcelain_reference_pack
    from pipeline.ref_qa import inspect_reference_image_pack

    ref_dir = p_dir / "03_visuals" / "reference_images"
    pre_ref_cv_ready = False
    if ref_dir.is_dir() and any(ref_dir.glob("*.png")):
        pre_ref = inspect_reference_image_pack(p_dir, require_review=False, save_report=False)
        pre_ref_cv_ready = bool(pre_ref.get("cv_pre_generation_ready"))
    if not pre_ref_cv_ready:
        ensure_porcelain_reference_pack(p_dir, cdp_port=cdp_port, force=False, require_review=False)
    ref_rep = inspect_reference_image_pack(p_dir, require_review=True, save_report=True)
    if not ref_rep.get("pre_generation_ready") or until == "gate1":
        sheets_script = Path(WORKSPACE_ROOT) / "scripts" / "render_qa_sheets.py"
        sheets: list[str] = []
        if sheets_script.is_file():
            suspects_arg = ",".join(str(x) for x in (ref_rep.get("regenerate_image_ids") or []))
            cmd_s = [sys.executable, "-X", "utf8", str(sheets_script), "--dir", str(p_dir), "--mode", "refs"]
            if suspects_arg:
                cmd_s += ["--suspects", suspects_arg]
            proc_s = subprocess.run(cmd_s, capture_output=True, text=True, check=False)
            if proc_s.returncode == 0 and proc_s.stdout.strip():
                try:
                    s_data = json.loads(proc_s.stdout)
                    sheets = [str(s["path"]) for s in (s_data.get("coarse_sheets") or []) if isinstance(s, dict) and s.get("path")]
                except Exception:
                    sheets = []
        return {
            "project_id": pid,
            "status": "GATE1_READY" if ref_rep.get("pre_generation_ready") else ("PAUSED_AT_GATE1" if ref_rep.get("cv_pre_generation_ready") else "GATE1_QA_FAILED"),
            "cv_ok": bool(ref_rep.get("cv_pre_generation_ready")),
            "regenerate_image_ids": ref_rep.get("regenerate_image_ids") or [],
            "review_file": str(ref_dir / "reference_semantic_review.json"),
            "triage_sheets": sheets,
        }

    # 3. Audio Lock + Sharded Flow Generation
    if not (p_dir / "04_audio" / "audio_master.wav").is_file():
        lock_episode_audio_and_edl_frames(p_dir)
    pending_flow, _ = has_pending_human_flow_clips(p_dir, only_clips=None, clean_existing=False)
    if pending_flow:
        asyncio.run(
            run_sharded_diorama_flow_generation(
                project_id=pid,
                clean_existing=False,
                only_clips=None,
                max_parallel_tabs=min(int(tabs), FLOW_MAX_PARALLEL_BATCH_SIZE),
                cdp_port=cdp_port,
                engine_mode=engine_mode.replace("-", "_"),
            )
        )

    # 3b. Local R88-A Archival Photo Inserts & R89 Archival Video Split-Sync / Viewfinder Rendering
    archival_rendered = False
    ep_dur_est = 75.0
    voice_rep_p = p_dir / "04_audio" / "voice_report.json"
    if voice_rep_p.is_file():
        try:
            vr_doc = json.loads(voice_rep_p.read_text(encoding="utf-8"))
            if float(vr_doc.get("total_duration_sec") or 0.0) > 10.0:
                ep_dur_est = float(vr_doc["total_duration_sec"])
        except Exception:
            pass
    v_dir_ep = p_dir / "03_visuals"
    r88_mf_p = v_dir_ep / "archival_inserts_manifest.json"
    if r88_mf_p.is_file():
        from pipeline.archival_insert import (
            _extract_entries_key as _r88_entries,
            load_verified_archival_insert_clip_map,
            render_archival_insert_clips,
        )

        r88_raw = json.loads(r88_mf_p.read_text(encoding="utf-8"))
        _, r88_items = _r88_entries(r88_raw if isinstance(r88_raw, dict) else {})
        r88_vmap = load_verified_archival_insert_clip_map(v_dir_ep)
        if r88_items and len(r88_vmap) < len(r88_items):
            render_archival_insert_clips(p_dir, episode_duration_sec=ep_dur_est)
            archival_rendered = True

    r89_mf_p = v_dir_ep / "archival_videos_manifest.json"
    if r89_mf_p.is_file():
        from pipeline.archival_video import (
            _extract_entries_key as _r89_entries,
            load_verified_archival_video_clip_map,
            render_archival_video_clips,
        )

        r89_raw = json.loads(r89_mf_p.read_text(encoding="utf-8"))
        _, r89_items = _r89_entries(r89_raw if isinstance(r89_raw, dict) else {})
        r89_vmap = load_verified_archival_video_clip_map(v_dir_ep)
        needs_split_upgrade = any(
            str(it.get("recommended_gear3_mode") or "").strip().lower() == "split_sync"
            and str(it.get("mode") or "").strip().lower() != "split_sync"
            and bool(it.get("split_sync_brain_video_rel_path"))
            and (p_dir / str(it["split_sync_brain_video_rel_path"])).is_file()
            for it in r89_items
        )
        if r89_items and (len(r89_vmap) < len(r89_items) or needs_split_upgrade):
            render_archival_video_clips(p_dir, episode_duration_sec=ep_dur_est)
            archival_rendered = True

    # 4. Assembly (only if needed so signed Gate 2 MP4 SHA-256 is never invalidated!) + Single-Pass QA
    from pipeline.assembler import assemble_diorama_project, verify_script_audio_freshness
    from pipeline.episode_qa import verify_final_mp4_against_contract
    from pipeline.media_cache import release_session_speed_cache, shared_mp4_decode_session
    from pipeline.media_probe import VideoAutopsyEngine
    from pipeline.posthoc_qa import init_posthoc_semantic_review_template, run_posthoc_semantic_qa

    final_mp4_cand = p_dir / "05_assembly" / "final_shorts_1080x1920.mp4"
    need_assemble = pending_flow or archival_rendered or not (final_mp4_cand.is_file() and final_mp4_cand.stat().st_size >= 50_000)
    if not need_assemble:
        try:
            verify_script_audio_freshness(p_dir, context="episode-runner")
        except Exception:
            need_assemble = True

    if need_assemble:
        asm_res = assemble_diorama_project(p_dir, force_rebuild=True, run_posthoc_qa=False, preserve_audio_master=True)
        final_mp4 = Path(asm_res.get("final_mp4") or asm_res.get("final_video") or final_mp4_cand)
    else:
        final_mp4 = final_mp4_cand

    with shared_mp4_decode_session(final_mp4):
        ph_rep = run_posthoc_semantic_qa(p_dir, save_report=True)
        ep_rep = verify_final_mp4_against_contract(p_dir, save_report=True)
        aut_rep = VideoAutopsyEngine.inspect_project(p_dir, save_report=True)
    release_session_speed_cache()

    if not ep_rep.get("passed") or not aut_rep.get("passed") or not ph_rep.get("cv_passed", ph_rep.get("passed")):
        return {
            "project_id": pid,
            "status": "TIER1_QA_FAILED",
            "episode_qa_passed": bool(ep_rep.get("passed")),
            "autopsy_passed": bool(aut_rep.get("passed")),
            "posthoc_cv_passed": bool(ph_rep.get("cv_passed")),
        }

    if not ph_rep.get("passed") or until == "gate2":
        rev_f = p_dir / "05_assembly" / "posthoc_semantic_review.json"
        if not rev_f.is_file():
            init_posthoc_semantic_review_template(p_dir, auto_populate_from_cv=False)
        return {
            "project_id": pid,
            "status": "GATE2_READY" if ph_rep.get("passed") else "PAUSED_AT_GATE2",
            "final_video": str(final_mp4),
            "review_file": str(rev_f),
            "viewer_sheets": list(ph_rep.get("viewer_sheets") or []),
        }

    # 5. Thumbnail + Root MP4 Export + Manifest Sync + Verify Receipt
    from pipeline.storage import ProjectStorage
    from pipeline.studio.scheduler import record_verify_pass_receipt
    from pipeline.thumbnail import run as run_thumbnail_studio

    th_rep = run_thumbnail_studio(p_dir, generate_keyart=True, cdp_port=cdp_port)
    if not th_rep.get("passed"):
        return {
            "project_id": pid,
            "status": "THUMBNAIL_QA_FAILED",
            "failed_gates": list(th_rep.get("failed_gates") or []),
        }
    root_mp4 = _resolve_root_mp4_path(p_dir, pid)
    shutil.copy2(final_mp4, root_mp4)
    storage = ProjectStorage(
        pid,
        title=str(script_doc.get("title") or plan.get("title") or ""),
        pillar=str(script_doc.get("pillar") or plan.get("pillar") or ""),
        projects_dir=p_dir.parent,
    )
    ProjectStorage.sync_existing_manifest_from_disk(p_dir, status="READY_TO_PUBLISH")
    integ = storage.verify_integrity()
    if integ.get("all_intact"):
        record_verify_pass_receipt(project_id=pid, projects_dir=p_dir.parent)
        ProjectStorage.sync_existing_manifest_from_disk(p_dir, status="READY_TO_PUBLISH")
        integ = storage.verify_integrity()
    return {
        "project_id": pid,
        "status": "READY_TO_PUBLISH" if integ.get("all_intact") else "VERIFY_INTEGRITY_FAILED",
        "root_mp4": str(root_mp4),
        "all_intact": bool(integ.get("all_intact")),
    }
