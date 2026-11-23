"""
ALL ABOUT BRAIN — 8-Core AMD EPYC Genoa & 64GB RAM Hardware Profile SSOT
========================================================================
Centralized hardware capability detection and explicit `cpu_budget` thread/worker
scaling for standalone vs. Google-Flow-overlapped execution on `c3d-highmem-8`
(8 vCPU AVX-512 / AVX-512-VNNI, 64GB RAM, 0B Swap, `/dev/shm/aab_scratch` tmpfs).
"""

from __future__ import annotations

import functools
import os
import shutil
from pathlib import Path
from typing import Any

from pipeline.config import (
    AAB_MAX_STANDALONE_CPU_BUDGET,
    AAB_OVERLAPPED_FLOW_RESERVED_CORES,
    AAB_SHM_MIN_FREE_BYTES,
    AAB_SHM_MOUNT_ROOT,
    AAB_SHM_SCRATCH_DEFAULT_DIR,
    BLENDER_SIM_THREADS_PER_WORKER,
)


@functools.lru_cache(maxsize=1)
def _read_cpuinfo_flags() -> tuple[str, frozenset[str]]:
    model_name = ""
    flags: set[str] = set()
    cpuinfo = Path("/proc/cpuinfo")
    if cpuinfo.is_file():
        try:
            for line in cpuinfo.read_text(encoding="utf-8", errors="ignore").splitlines():
                if not model_name and line.lower().startswith("model name"):
                    model_name = line.split(":", 1)[-1].strip()
                elif line.lower().startswith("flags"):
                    flags.update(line.split(":", 1)[-1].strip().split())
                    if model_name:
                        break
        except OSError:
            pass
    return model_name, frozenset(flags)


def _read_mem_total_bytes() -> int:
    meminfo = Path("/proc/meminfo")
    if meminfo.is_file():
        try:
            for line in meminfo.read_text(encoding="utf-8", errors="ignore").splitlines():
                if line.startswith("MemTotal:"):
                    parts = line.split()
                    if len(parts) >= 2 and parts[1].isdigit():
                        return int(parts[1]) * 1024
        except OSError:
            pass
    return 0


def detect_host_hardware() -> dict[str, Any]:
    """Returns live host CPU, SIMD (`avx512f`/`avx512_vnni`), RAM, and `/dev/shm` telemetry."""
    cpu_count = max(1, int(os.cpu_count() or 2))
    model_name, flags = _read_cpuinfo_flags()
    total_ram = _read_mem_total_bytes()

    shm_total = 0
    shm_free = 0
    shm_available = False
    if os.name != "nt" and AAB_SHM_MOUNT_ROOT.is_dir() and os.access(AAB_SHM_MOUNT_ROOT, os.W_OK | os.X_OK):
        try:
            du = shutil.disk_usage(AAB_SHM_MOUNT_ROOT)
            shm_total = int(du.total)
            shm_free = int(du.free)
            shm_available = shm_free >= int(AAB_SHM_MIN_FREE_BYTES)
        except OSError:
            shm_available = False

    return {
        "cpu_count": cpu_count,
        "cpu_model": model_name or "unknown",
        "has_avx512": "avx512f" in flags,
        "has_avx512_vnni": "avx512_vnni" in flags,
        "has_sha_ni": "sha_ni" in flags,
        "total_ram_bytes": total_ram,
        "total_ram_gib": round(total_ram / float(1024**3), 2) if total_ram else 0.0,
        "shm_mount": str(AAB_SHM_MOUNT_ROOT),
        "shm_scratch_default": str(AAB_SHM_SCRATCH_DEFAULT_DIR),
        "shm_total_bytes": shm_total,
        "shm_free_bytes": shm_free,
        "shm_free_gib": round(shm_free / float(1024**3), 2) if shm_free else 0.0,
        "shm_available": shm_available,
    }


def resolve_cpu_budget(
    explicit_budget: int | None = None,
    *,
    overlapped: bool = False,
) -> int:
    """
    Resolves the active vCPU budget explicitly (Guard 3):
      - When `explicit_budget` is provided (> 0), honors it directly (clamped >= 1)
        so reused `ProcessPoolExecutor` workers can dynamically scale `6 -> 8` per task.
      - Otherwise checks `AAB_CPU_BUDGET` env override, then defaults to:
          * `8` vCPUs in standalone mode (`min(AAB_MAX_STANDALONE_CPU_BUDGET, os.cpu_count())`)
          * `6` vCPUs in `overlapped=True` mode (reserving `2` vCPUs for main-process CDP + Chrome).
    """
    host_cpus = max(1, int(os.cpu_count() or 2))
    max_cap = max(int(AAB_MAX_STANDALONE_CPU_BUDGET), host_cpus)

    if explicit_budget is not None and int(explicit_budget) > 0:
        return max(1, min(int(explicit_budget), max_cap))

    env_raw = os.environ.get("AAB_CPU_BUDGET", "").strip()
    if env_raw:
        try:
            parsed = int(env_raw)
            if parsed > 0:
                return max(1, min(parsed, max_cap))
        except ValueError:
            pass

    standalone = max(1, min(int(AAB_MAX_STANDALONE_CPU_BUDGET), host_cpus))
    if overlapped and standalone > int(AAB_OVERLAPPED_FLOW_RESERVED_CORES):
        return max(2, standalone - int(AAB_OVERLAPPED_FLOW_RESERVED_CORES))
    return standalone


def resolve_assembler_workers(
    cpu_budget: int | None = None,
    *,
    overlapped: bool = False,
) -> int:
    """Worker count for parallel cut encoding & `DISOpticalFlow` 30fps interpolation (`8` standalone / `6` overlapped)."""
    return resolve_cpu_budget(cpu_budget, overlapped=overlapped)


def resolve_xfade_workers(
    cpu_budget: int | None = None,
    *,
    overlapped: bool = False,
) -> int:
    """Worker count for multi-stage FFmpeg `xfade` group merges (`8` standalone / `6` overlapped)."""
    return resolve_cpu_budget(cpu_budget, overlapped=overlapped)


def resolve_ffmpeg_threads_per_worker(
    active_workers: int,
    cpu_budget: int | None = None,
    *,
    overlapped: bool = False,
) -> int:
    """Prevents `N * 8` x264 thread oversubscription when `N` segment encodes run concurrently."""
    budget = resolve_cpu_budget(cpu_budget, overlapped=overlapped)
    eff_w = max(1, int(active_workers))
    return max(1, min(4, budget // eff_w))


def resolve_whisper_threads(
    cpu_budget: int | None = None,
    *,
    overlapped: bool = False,
) -> int:
    """CTranslate2 `int8` AVX-512-VNNI thread count (`8` standalone / `6` overlapped)."""
    return resolve_cpu_budget(cpu_budget, overlapped=overlapped)


def resolve_blender_parallel_plan(
    cpu_budget: int | None = None,
    *,
    overlapped: bool = False,
    threads_per_worker: int = BLENDER_SIM_THREADS_PER_WORKER,
    clip_count: int | None = None,
) -> tuple[int, int]:
    """
    Computes `(max_workers, threads_per_worker)` for Blender 4.2 `BLENDER_WORKBENCH` (`llvmpipe`):
      - `cpu_budget=8` -> `(4, 2)` (`4 processes * 2 llvmpipe threads = 8 vCPUs`, zero thrash)
      - `cpu_budget=6` -> `(3, 2)` (`3 processes * 2 llvmpipe threads = 6 vCPUs`, 2 vCPUs free for Flow)
    """
    budget = resolve_cpu_budget(cpu_budget, overlapped=overlapped)
    tpw = max(1, min(budget, int(threads_per_worker or BLENDER_SIM_THREADS_PER_WORKER)))
    n_proc = max(1, budget // tpw)
    if clip_count is not None and int(clip_count) > 0:
        n_proc = min(n_proc, int(clip_count))
    return n_proc, tpw
