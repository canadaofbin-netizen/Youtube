"""
ALL ABOUT BRAIN — Pipelined Neuro-Diorama Producer/Consumer Runner (R5, R37, R56-R65)
=====================================================================================
Overlaps browser/network-bound Google Flow clip generation (single-owner main thread on CDP 9222,
`<= FLOW_MAX_PARALLEL_BATCH_SIZE` tabs) with CPU-bound Assembly + 5-Gate QA (`ProcessPoolExecutor`
worker process), with up-front Precheck across all target episodes and per-episode failure isolation.
"""

from __future__ import annotations

import asyncio
import collections
import concurrent.futures
import datetime as dt
import inspect
import json
import multiprocessing
import os
import time
from pathlib import Path
from typing import Any

from pipeline.brain_simulator_blender import render_project_brain_simulator_clips_parallel
from pipeline.config import FLOW_MAX_PARALLEL_BATCH_SIZE, PROJECTS_DIR
from pipeline.diorama_batch_orchestrator import (
    BATCH_STATUS_PATH,
    DIORAMA_DAILY_30_SPECS,
    _collect_auto_heal_plan,
    _is_already_completed,
    _save_batch_status,
    _unlink_sim_clips_for_regen,
    finalize_and_verify_diorama_project,
    has_pending_human_flow_clips,
    lock_episode_audio_and_edl_frames,
    partition_project_clips_by_engine,
    precheck_diorama_project,
    sync_project_from_dossier_diorama,
)
from pipeline.flow_browser import FlowCircuitBreakerError
from pipeline.flow_diorama_sharded_worker import run_sharded_diorama_flow_generation
from pipeline.hardware_profile import resolve_cpu_budget
from pipeline.research_dossier import resolve_dossier_for_project


def parse_pipeline_specs(raw_projects: str) -> list[dict[str, Any]]:
    """
    Parse comma-separated project tokens into normalized spec dicts:
      - `slug:project_id:pillar` (explicit 3-part spec), OR
      - `project_id` resolved from `DIORAMA_DAILY_30_SPECS` or `projects/<project_id>/00_project_manifest.json`.
    """
    by_pid = {str(s["project_id"]): dict(s) for s in DIORAMA_DAILY_30_SPECS}
    specs: list[dict[str, Any]] = []
    tokens = [tok.strip() for tok in str(raw_projects or "").split(",") if tok.strip()]
    if not tokens:
        raise ValueError("No projects provided to parse_pipeline_specs")

    for idx, tok in enumerate(tokens, start=1):
        parts = [p.strip() for p in tok.split(":")]
        if len(parts) == 3:
            slug, pid, pillar = parts
            if not (slug and pid and pillar):
                raise ValueError(f"Invalid slug:project_id:pillar spec: {tok!r}")
            base = by_pid.get(pid, {})
            specs.append(
                {
                    "index": int(base.get("index") or idx),
                    "wave": int(base.get("wave") or 0),
                    "project_id": pid,
                    "slug": slug,
                    "pillar": pillar,
                }
            )
        elif len(parts) == 1:
            pid = parts[0]
            if pid in by_pid:
                specs.append(dict(by_pid[pid]))
                continue
            p_dir = Path(PROJECTS_DIR) / pid
            m_path = p_dir / "00_project_manifest.json"
            s_path = p_dir / "02_script" / "script.json"
            m_doc = json.loads(m_path.read_text(encoding="utf-8")) if m_path.exists() else {}
            s_doc = json.loads(s_path.read_text(encoding="utf-8")) if s_path.exists() else {}
            slug = str(m_doc.get("dossier_slug") or s_doc.get("dossier") or "").strip()
            resolved_d = resolve_dossier_for_project(pid) if not slug else resolve_dossier_for_project(slug)
            if not slug and resolved_d is not None:
                slug = resolved_d.name
            pillar = str(m_doc.get("pillar") or s_doc.get("pillar") or "").strip()
            if not pillar and resolved_d is not None and (resolved_d / "dossier.json").is_file():
                d_doc = json.loads((resolved_d / "dossier.json").read_text(encoding="utf-8"))
                pillar = str(d_doc.get("pillar") or "").strip()
            if not (slug and pillar):
                raise ValueError(
                    f"Cannot resolve slug/pillar for {pid!r}; pass explicit slug:project_id:pillar"
                )
            specs.append(
                {
                    "index": idx,
                    "wave": 0,
                    "project_id": pid,
                    "slug": slug,
                    "pillar": pillar,
                }
            )
        else:
            raise ValueError(
                f"Expected 'slug:project_id:pillar' or 'project_id', got {tok!r}"
            )
    return specs


def _assembly_worker_entry(
    project_id: str,
    voice_preset: str | None = None,
    prosody_mode: str | None = None,
    cpu_budget: int = 6,
    preserve_audio_master: bool = False,
) -> dict[str, Any]:
    """
    Subprocess entrypoint for CPU-bound Assembly + 5-Gate QA (Guard 3).
    Pins per-library inner threads (`OMP`/`MKL`/`OPENBLAS`/`cv2`) to 1 to prevent nested thread
    explosion in a reused worker process, while propagating explicit `cpu_budget` (`6` overlapped
    or `8` standalone) to downstream FFmpeg / CV worker pools.
    """
    os.environ["OMP_NUM_THREADS"] = "1"
    os.environ["MKL_NUM_THREADS"] = "1"
    os.environ["OPENBLAS_NUM_THREADS"] = "1"
    try:
        import cv2

        cv2.setNumThreads(1)
    except Exception:  # noqa: BLE001
        pass

    try:
        fin_kwargs: dict[str, Any] = {
            "cpu_budget": int(cpu_budget),
            "preserve_audio_master": bool(preserve_audio_master),
        }
        if voice_preset:
            fin_kwargs["voice_preset"] = voice_preset
        if prosody_mode:
            fin_kwargs["prosody_mode"] = prosody_mode
        fin_sig = inspect.signature(finalize_and_verify_diorama_project)
        fin_has_varkw = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in fin_sig.parameters.values())
        if not fin_has_varkw:
            fin_kwargs = {k: v for k, v in fin_kwargs.items() if k in fin_sig.parameters}
        fin = finalize_and_verify_diorama_project(project_id, **fin_kwargs)
        return {
            "ok": True,
            "project_id": project_id,
            "cpu_budget": int(cpu_budget),
            "preserve_audio_master": bool(preserve_audio_master),
            "result": fin,
        }
    except Exception as exc:  # noqa: BLE001
        heal_plan = _collect_auto_heal_plan(project_id)
        return {
            "ok": False,
            "project_id": project_id,
            "cpu_budget": int(cpu_budget),
            "preserve_audio_master": bool(preserve_audio_master),
            "error": str(exc),
            "heal_plan": heal_plan,
        }


def _unlink_clips_for_regen(project_id: str, clip_indices: list[int]) -> None:
    p_dir = Path(PROJECTS_DIR) / project_id
    _, sim_idxs = partition_project_clips_by_engine(p_dir)
    sim_set = set(sim_idxs)
    clips_dir = p_dir / "03_visuals" / "flow_native_clips"
    sim_regen: list[int] = []
    for c_idx in clip_indices:
        if int(c_idx) in sim_set:
            sim_regen.append(int(c_idx))
            continue
        for pat in (f"clip_{c_idx:02d}.mp4", f"clip_{c_idx}.mp4"):
            fp = clips_dir / pat
            if fp.exists():
                fp.unlink()
    if sim_regen:
        _unlink_sim_clips_for_regen(p_dir, sim_regen)


def run_diorama_pipeline(
    specs: list[dict[str, Any]],
    *,
    precheck_only: bool = False,
    tabs: int = FLOW_MAX_PARALLEL_BATCH_SIZE,
    force_regenerate: bool = False,
    cdp_port: int = 9222,
    engine_mode: str | None = "auto",
    max_heal_rounds: int = 2,
    isolate_precheck_failures: bool = True,
    voice_preset: str | None = None,
    prosody_mode: str | None = None,
) -> dict[str, Any]:
    """
    Pipelined multi-episode production:
      1. Refuses published projects (`06_publish/upload_receipt.json`).
      2. Runs `precheck_diorama_project(..., run_tts_clock=True)` up front on all pending episodes
         (warming TTS + Whisper caches and catching Prosody P1-P6/P8/P10 & DQ1/DQ3 issues in ~1 min).
      3. Runs Flow producer on the main thread (`<= 5` tabs, sole owner of CDP port) while overlapping
         `finalize_and_verify_diorama_project` in a single background worker process.
      4. Isolates per-episode failures into `diorama_batch_20_status.json` so healthy episodes continue.
    """
    if not specs:
        raise ValueError("specs must not be empty")
    if voice_preset:
        specs = [{**sp, "voice_preset": voice_preset} for sp in specs]
    if prosody_mode:
        specs = [{**sp, "prosody_mode": prosody_mode} for sp in specs]

    for sp in specs:
        pid = str(sp["project_id"])
        p_dir = Path(PROJECTS_DIR) / pid
        if (p_dir / "06_publish" / "upload_receipt.json").exists():
            raise RuntimeError(
                f"Refusing to (re)produce published project {pid} (upload_receipt.json present)"
            )

    state: dict[str, Any] = (
        json.loads(BATCH_STATUS_PATH.read_text(encoding="utf-8"))
        if BATCH_STATUS_PATH.exists()
        else {"total_target": len(DIORAMA_DAILY_30_SPECS), "completed": {}, "in_progress": None, "errors": {}}
    )
    state["total_target"] = len(DIORAMA_DAILY_30_SPECS)
    state.setdefault("completed", {})
    state.setdefault("errors", {})

    prechecks: list[dict[str, Any]] = []
    ready_specs: list[dict[str, Any]] = []
    run_errors: dict[str, str] = {}

    for sp in specs:
        pid = str(sp["project_id"])
        if not precheck_only and not force_regenerate and _is_already_completed(pid):
            print(f"[DioramaPipeline] Skipping already-completed & verified project: {pid}")
            state["completed"][pid] = state["completed"].get(pid) or {"status": "COMPLETED_RESUMED"}
            _save_batch_status(state)
            continue

        rep = precheck_diorama_project(sp, run_tts_clock=True)
        prechecks.append(rep)
        status_tag = "PASS" if rep["passed"] else "FAIL"
        print(
            f"[Precheck][{status_tag}] {pid} | sents={rep['sentences']} clips={rep['clips']} "
            f"words={rep['words']} tts={rep['tts_duration_sec']}s"
        )
        for iss in rep["issues"]:
            print(f"    - {iss}")

        if rep["passed"]:
            ready_specs.append(sp)
        elif not precheck_only:
            err_msg = f"Precheck failed for {pid}: {rep['issues']}"
            state["errors"][pid] = {
                "stage": "precheck",
                "error": err_msg,
                "failed_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
            }
            _save_batch_status(state)
            run_errors[pid] = err_msg
            if not isolate_precheck_failures:
                raise RuntimeError(err_msg)

    failed_pre = [r for r in prechecks if not r["passed"]]
    if precheck_only:
        if failed_pre:
            raise RuntimeError(
                f"Precheck failed on {len(failed_pre)} project(s): {[r['project_id'] for r in failed_pre]}"
            )
        return {
            "mode": "precheck_only",
            "count": len(prechecks),
            "all_passed": True,
            "projects": prechecks,
        }

    for sp in ready_specs:
        sync_project_from_dossier_diorama(sp, write_back_dossier=True)

    flow_sig = inspect.signature(run_sharded_diorama_flow_generation)
    flow_has_varkw = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in flow_sig.parameters.values())
    extra_flow_kwargs: dict[str, Any] = {}
    if engine_mode is not None and (flow_has_varkw or "engine_mode" in flow_sig.parameters):
        extra_flow_kwargs["engine_mode"] = engine_mode
    if flow_has_varkw or "include_brain_simulator_clips" in flow_sig.parameters:
        extra_flow_kwargs["include_brain_simulator_clips"] = False

    flow_queue: collections.deque[dict[str, Any]] = collections.deque(
        {
            "spec": sp,
            "project_id": str(sp["project_id"]),
            "only_clips": None,
            "clean_existing": bool(force_regenerate),
            "heal_round": 0,
            "started_at": time.time(),
            "edl_frame_map": {},
            "preserve_audio_master": False,
        }
        for sp in ready_specs
    )
    in_flight: list[tuple[dict[str, Any], concurrent.futures.Future[dict[str, Any]]]] = []
    results: list[dict[str, Any]] = []

    mp_ctx = multiprocessing.get_context("spawn")
    with concurrent.futures.ProcessPoolExecutor(max_workers=1, mp_context=mp_ctx) as asm_pool:

        def _submit_assembly(task_meta: dict[str, Any]) -> None:
            pid_sub = str(task_meta["project_id"])
            vp_sub = (task_meta.get("spec") or {}).get("voice_preset") or voice_preset
            pm_sub = (task_meta.get("spec") or {}).get("prosody_mode") or prosody_mode
            eff_budget = resolve_cpu_budget(overlapped=bool(flow_queue))
            preserve_aud = bool(task_meta.get("preserve_audio_master", False))
            print(
                f"[DioramaPipeline][AssemblyQueue] Queued background assembly+QA for {pid_sub} "
                f"(heal_round={task_meta['heal_round']}, cpu_budget={eff_budget}, preserve_audio={preserve_aud})"
            )
            fut = asm_pool.submit(_assembly_worker_entry, pid_sub, vp_sub, pm_sub, eff_budget, preserve_aud)
            in_flight.append((task_meta, fut))

        def _harvest_done_assemblies() -> None:
            still_running: list[tuple[dict[str, Any], concurrent.futures.Future[dict[str, Any]]]] = []
            for t_meta, fut in in_flight:
                if not fut.done():
                    still_running.append((t_meta, fut))
                    continue
                pid_done = str(t_meta["project_id"])
                h_round = int(t_meta["heal_round"])
                try:
                    w_res = fut.result()
                except Exception as worker_crash:  # noqa: BLE001
                    w_res = {
                        "ok": False,
                        "project_id": pid_done,
                        "error": f"Assembly worker crashed: {worker_crash}",
                        "heal_plan": _collect_auto_heal_plan(pid_done),
                    }

                if w_res.get("ok"):
                    fin = dict(w_res["result"])
                    fin["elapsed_min"] = round((time.time() - float(t_meta["started_at"])) / 60.0, 2)
                    state["completed"][pid_done] = fin
                    state["errors"].pop(pid_done, None)
                    _save_batch_status(state)
                    results.append(fin)
                    print(
                        f"[DioramaPipeline] COMPLETED {pid_done} in {fin['elapsed_min']} min -> "
                        f"{fin['completed_mp4']} ({fin['duration_sec']}s, {fin['cut_count']} cuts, INTACT)"
                    )
                    continue

                err_str = str(w_res.get("error") or "unknown assembly/QA error")
                heal_plan = w_res.get("heal_plan") or {}
                if h_round < max_heal_rounds and not heal_plan.get("script_fix_required"):
                    if heal_plan.get("rebuild_only"):
                        eff_budget_heal = resolve_cpu_budget(overlapped=bool(flow_queue))
                        preserve_aud_heal = bool(t_meta.get("preserve_audio_master", False))
                        print(
                            f"[DioramaPipeline][AutoHeal {h_round + 1}/{max_heal_rounds}] {pid_done} needs EDL-only "
                            f"rebuild on cuts {heal_plan.get('edl_only_cuts')} (cpu_budget={eff_budget_heal}); re-queueing assembly..."
                        )
                        nxt = dict(t_meta)
                        nxt["heal_round"] = h_round + 1
                        vp_done = (t_meta.get("spec") or {}).get("voice_preset") or voice_preset
                        pm_done = (t_meta.get("spec") or {}).get("prosody_mode") or prosody_mode
                        fut2 = asm_pool.submit(
                            _assembly_worker_entry,
                            pid_done,
                            vp_done,
                            pm_done,
                            eff_budget_heal,
                            preserve_aud_heal,
                        )
                        still_running.append((nxt, fut2))
                        continue
                    regen_clips = list(heal_plan.get("regenerate_clips") or [])
                    if 1 <= len(regen_clips) <= 10:
                        print(
                            f"[DioramaPipeline][AutoHeal {h_round + 1}/{max_heal_rounds}] {pid_done} flagged clips "
                            f"{regen_clips}; pushing targeted regeneration onto Flow queue..."
                        )
                        _unlink_clips_for_regen(pid_done, regen_clips)
                        nxt_flow = dict(t_meta)
                        nxt_flow["only_clips"] = regen_clips
                        nxt_flow["clean_existing"] = False
                        nxt_flow["heal_round"] = h_round + 1
                        flow_queue.appendleft(nxt_flow)
                        continue

                if heal_plan.get("script_fix_required"):
                    err_str = (
                        f"[script_fix_required] {pid_done} failed script/plan gate "
                        f"({heal_plan.get('script_fix_reasons')}): {err_str}"
                    )
                print(f"[DioramaPipeline][ERROR] {pid_done} failed QA/assembly: {err_str}")
                state["errors"][pid_done] = {
                    "stage": "assembly_qa",
                    "error": err_str,
                    "failed_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
                }
                _save_batch_status(state)
                run_errors[pid_done] = err_str

            in_flight[:] = still_running

        while flow_queue or in_flight:
            _harvest_done_assemblies()

            if flow_queue:
                f_task = flow_queue.popleft()
                pid = str(f_task["project_id"])
                only_clips = f_task["only_clips"]
                if f_task["heal_round"] == 0:
                    f_task["started_at"] = time.time()
                state["in_progress"] = {
                    "project_id": pid,
                    "stage": "flow" if not only_clips else f"flow_autoheal_{f_task['heal_round']}",
                    "only_clips": only_clips,
                    "started_at_epoch": round(time.time(), 1),
                }
                _save_batch_status(state)
                eff_tabs = (
                    min(int(tabs), FLOW_MAX_PARALLEL_BATCH_SIZE, max(1, len(only_clips)))
                    if only_clips
                    else min(int(tabs), FLOW_MAX_PARALLEL_BATCH_SIZE)
                )
                print(
                    f"\n==================== [DioramaPipeline][Flow] {pid} "
                    f"(only_clips={only_clips or 'ALL'}, tabs={eff_tabs}, bg_assemblies={len(in_flight)}) ===================="
                )
                try:
                    p_dir_flow = Path(PROJECTS_DIR) / pid
                    vp_path_flow = p_dir_flow / "03_visuals" / "visual_plan.json"
                    if vp_path_flow.exists():
                        from pipeline.config import is_expressive_v8_plan, is_porcelain_v7_plan
                        from pipeline.porcelain_anchor_pack import ensure_porcelain_reference_pack

                        vp_doc_flow = json.loads(vp_path_flow.read_text(encoding="utf-8"))
                        if is_porcelain_v7_plan(vp_doc_flow) or is_expressive_v8_plan(vp_doc_flow):
                            ref_res = ensure_porcelain_reference_pack(
                                p_dir_flow,
                                cdp_port=cdp_port,
                                force=False,
                                require_review=False,
                                synthesize_scene_anchors=True,
                            )
                            if not ref_res.get("pre_generation_ready"):
                                raise RuntimeError(
                                    f"Reference pack failed pre_generation_ready for {pid}: "
                                    f"regenerate={ref_res.get('regenerate_image_ids')} score={ref_res.get('reference_qa_score')}"
                                )

                    # Step 1 (Guard 4): Lock TTS + P6 + Master EDL frame budget BEFORE Fork
                    if int(f_task["heal_round"]) == 0 or not f_task.get("preserve_audio_master"):
                        vp_flow = (f_task.get("spec") or {}).get("voice_preset") or voice_preset
                        pm_flow = (f_task.get("spec") or {}).get("prosody_mode") or prosody_mode
                        lock_info = lock_episode_audio_and_edl_frames(
                            p_dir_flow,
                            voice_preset=vp_flow,
                            prosody_mode=pm_flow,
                        )
                        f_task["edl_frame_map"] = dict(lock_info["edl_frame_map"])
                        f_task["preserve_audio_master"] = True

                    edl_frame_map_flow = dict(f_task.get("edl_frame_map") or {})
                    human_clip_nums, sim_clip_nums = partition_project_clips_by_engine(p_dir_flow)
                    sim_set_flow = set(sim_clip_nums)
                    sim_needed = (
                        bool(sim_clip_nums)
                        if not only_clips
                        else any(int(c) in sim_set_flow for c in only_clips)
                    )
                    only_human_clips = (
                        [int(c) for c in only_clips if int(c) not in sim_set_flow]
                        if only_clips
                        else None
                    )
                    flow_needed = bool(human_clip_nums) if not only_clips else bool(only_human_clips)
                    pending_flow, _ = (
                        has_pending_human_flow_clips(
                            p_dir_flow,
                            only_clips=only_human_clips,
                            clean_existing=bool(f_task["clean_existing"]),
                        )
                        if flow_needed
                        else (False, 0)
                    )
                    eff_tabs_human = (
                        min(int(tabs), FLOW_MAX_PARALLEL_BATCH_SIZE, max(1, len(only_human_clips)))
                        if only_human_clips
                        else eff_tabs
                    )
                    prior_asm_futs = [fut for _, fut in in_flight if not fut.done()]

                    # Step 2 (Guard 4): Concurrent Fork (Google Flow <=5 tabs + R76 Blender 3x2 / 4x2)
                    if sim_needed and pending_flow:
                        def _run_overlapped_sim(
                            _p_dir: Path = p_dir_flow,
                            _fmap: dict[int, int] = edl_frame_map_flow,
                            _force: bool = bool(f_task["clean_existing"] and not only_clips),
                            _wait_futs: list[concurrent.futures.Future[dict[str, Any]]] = prior_asm_futs,
                        ) -> dict[str, Any]:
                            if _wait_futs:
                                concurrent.futures.wait(_wait_futs)
                            return render_project_brain_simulator_clips_parallel(
                                _p_dir,
                                edl_frame_map=_fmap,
                                overlapped=True,
                                force=_force,
                            )

                        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as fork_pool:
                            sim_fut = fork_pool.submit(_run_overlapped_sim)
                            try:
                                asyncio.run(
                                    run_sharded_diorama_flow_generation(
                                        project_id=pid,
                                        clean_existing=bool(f_task["clean_existing"]),
                                        only_clips=only_human_clips,
                                        max_parallel_tabs=eff_tabs_human,
                                        cdp_port=cdp_port,
                                        **extra_flow_kwargs,
                                    )
                                )
                            finally:
                                sim_res = sim_fut.result()
                        if not sim_res.get("all_passed", True):
                            raise RuntimeError(
                                f"R76 Brain Simulator QA failed during overlapped fork for {pid}: {sim_res}"
                            )
                    elif sim_needed:
                        if flow_needed:
                            asyncio.run(
                                run_sharded_diorama_flow_generation(
                                    project_id=pid,
                                    clean_existing=bool(f_task["clean_existing"]),
                                    only_clips=only_human_clips,
                                    max_parallel_tabs=eff_tabs_human,
                                    cdp_port=cdp_port,
                                    **extra_flow_kwargs,
                                )
                            )
                        if prior_asm_futs:
                            concurrent.futures.wait(prior_asm_futs)
                        sim_res = render_project_brain_simulator_clips_parallel(
                            p_dir_flow,
                            edl_frame_map=edl_frame_map_flow,
                            cpu_budget=resolve_cpu_budget(overlapped=False),
                            overlapped=False,
                            force=bool(f_task["clean_existing"] and not only_clips),
                        )
                        if not sim_res.get("all_passed", True):
                            raise RuntimeError(f"R76 Brain Simulator QA failed for {pid}: {sim_res}")
                    elif flow_needed:
                        asyncio.run(
                            run_sharded_diorama_flow_generation(
                                project_id=pid,
                                clean_existing=bool(f_task["clean_existing"]),
                                only_clips=only_human_clips,
                                max_parallel_tabs=eff_tabs_human,
                                cdp_port=cdp_port,
                                **extra_flow_kwargs,
                            )
                        )

                    _harvest_done_assemblies()
                    state["in_progress"] = None
                    _save_batch_status(state)
                    _submit_assembly(f_task)
                except FlowCircuitBreakerError as cb_exc:
                    cb_msg = f"FlowCircuitBreakerError on {pid}: {cb_exc}"
                    print(f"[DioramaPipeline][CIRCUIT_BREAKER] {cb_msg}; halting remaining Flow queue.")
                    state["errors"][pid] = {
                        "stage": "flow_circuit_breaker",
                        "error": cb_msg,
                        "failed_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
                    }
                    state["in_progress"] = None
                    _save_batch_status(state)
                    run_errors[pid] = cb_msg
                    flow_queue.clear()
                except Exception as flow_exc:  # noqa: BLE001
                    f_msg = str(flow_exc)
                    print(
                        f"[DioramaPipeline][ERROR] Flow failed on {pid}: {f_msg} "
                        f"(isolating failure; {len(flow_queue)} episode(s) remain in Flow queue)"
                    )
                    state["errors"][pid] = {
                        "stage": "flow",
                        "error": f_msg,
                        "failed_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
                    }
                    state["in_progress"] = None
                    _save_batch_status(state)
                    run_errors[pid] = f_msg
                continue

            if in_flight:
                concurrent.futures.wait(
                    [fut for _, fut in in_flight],
                    return_when=concurrent.futures.FIRST_COMPLETED,
                )

    if run_errors:
        raise RuntimeError(
            f"Diorama pipeline finished with {len(run_errors)} failed project(s) "
            f"(completed={len(results)}): {run_errors}"
        )

    return {
        "mode": "pipeline",
        "completed_in_run": len(results),
        "total_completed_overall": len(state.get("completed", {})),
        "results": results,
    }
