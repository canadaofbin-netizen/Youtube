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

from pipeline.config import FLOW_MAX_PARALLEL_BATCH_SIZE, PROJECTS_DIR
from pipeline.diorama_batch_orchestrator import (
    BATCH_STATUS_PATH,
    DIORAMA_BATCH_20_SPECS,
    _collect_auto_heal_plan,
    _is_already_completed,
    _save_batch_status,
    finalize_and_verify_diorama_project,
    precheck_diorama_project,
)
from pipeline.flow_browser import FlowCircuitBreakerError
from pipeline.flow_diorama_sharded_worker import run_sharded_diorama_flow_generation


def parse_pipeline_specs(raw_projects: str) -> list[dict[str, Any]]:
    """
    Parse comma-separated project tokens into normalized spec dicts:
      - `slug:project_id:pillar` (explicit 3-part spec), OR
      - `project_id` resolved from `DIORAMA_BATCH_20_SPECS` or `projects/<project_id>/00_project_manifest.json`.
    """
    by_pid = {str(s["project_id"]): dict(s) for s in DIORAMA_BATCH_20_SPECS}
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
            pillar = str(m_doc.get("pillar") or s_doc.get("pillar") or "").strip()
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


def _assembly_worker_entry(project_id: str) -> dict[str, Any]:
    """
    Subprocess entrypoint for CPU-bound Assembly + 5-Gate QA.
    Caps OpenMP/OpenCV threads to 2 on a 4-core host so Whale/Flow on the main process stays responsive.
    """
    os.environ.setdefault("OMP_NUM_THREADS", "2")
    os.environ.setdefault("MKL_NUM_THREADS", "2")
    os.environ.setdefault("OPENBLAS_NUM_THREADS", "2")
    try:
        import cv2

        cv2.setNumThreads(2)
    except Exception:  # noqa: BLE001
        pass

    try:
        fin = finalize_and_verify_diorama_project(project_id)
        return {"ok": True, "project_id": project_id, "result": fin}
    except Exception as exc:  # noqa: BLE001
        heal_plan = _collect_auto_heal_plan(project_id)
        return {
            "ok": False,
            "project_id": project_id,
            "error": str(exc),
            "heal_plan": heal_plan,
        }


def _unlink_clips_for_regen(project_id: str, clip_indices: list[int]) -> None:
    clips_dir = Path(PROJECTS_DIR) / project_id / "03_visuals" / "flow_native_clips"
    for c_idx in clip_indices:
        for pat in (f"clip_{c_idx:02d}.mp4", f"clip_{c_idx}.mp4"):
            fp = clips_dir / pat
            if fp.exists():
                fp.unlink()


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
        else {"total_target": 20, "completed": {}, "in_progress": None, "errors": {}}
    )
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

    flow_sig = inspect.signature(run_sharded_diorama_flow_generation)
    extra_flow_kwargs: dict[str, Any] = {}
    if engine_mode is not None and "engine_mode" in flow_sig.parameters:
        extra_flow_kwargs["engine_mode"] = engine_mode

    flow_queue: collections.deque[dict[str, Any]] = collections.deque(
        {
            "spec": sp,
            "project_id": str(sp["project_id"]),
            "only_clips": None,
            "clean_existing": bool(force_regenerate),
            "heal_round": 0,
            "started_at": time.time(),
        }
        for sp in ready_specs
    )
    in_flight: list[tuple[dict[str, Any], concurrent.futures.Future[dict[str, Any]]]] = []
    results: list[dict[str, Any]] = []

    mp_ctx = multiprocessing.get_context("spawn")
    with concurrent.futures.ProcessPoolExecutor(max_workers=1, mp_context=mp_ctx) as asm_pool:

        def _submit_assembly(task_meta: dict[str, Any]) -> None:
            pid_sub = str(task_meta["project_id"])
            print(f"[DioramaPipeline][AssemblyQueue] Queued background assembly+QA for {pid_sub} (heal_round={task_meta['heal_round']})")
            fut = asm_pool.submit(_assembly_worker_entry, pid_sub)
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
                        print(
                            f"[DioramaPipeline][AutoHeal {h_round + 1}/{max_heal_rounds}] {pid_done} needs EDL-only "
                            f"rebuild on cuts {heal_plan.get('edl_only_cuts')}; re-queueing assembly..."
                        )
                        nxt = dict(t_meta)
                        nxt["heal_round"] = h_round + 1
                        fut2 = asm_pool.submit(_assembly_worker_entry, pid_done)
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
                    asyncio.run(
                        run_sharded_diorama_flow_generation(
                            project_id=pid,
                            clean_existing=bool(f_task["clean_existing"]),
                            only_clips=only_clips,
                            max_parallel_tabs=eff_tabs,
                            cdp_port=cdp_port,
                            **extra_flow_kwargs,
                        )
                    )
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
