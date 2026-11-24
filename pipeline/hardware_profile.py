"""
ALL ABOUT BRAIN — 8-Core AMD EPYC Genoa & 64GB Max-RAM Hardware Profile SSOT
============================================================================
Centralized hardware capability detection, `cpu_budget` thread/worker scaling, and
dynamic `MemAvailable >= 12 GiB` OOM-guarded RAM / `/dev/shm` budget allocation on
`c3d-highmem-8` (8 vCPU AVX-512 / AVX-512-VNNI, 62 GiB RAM, 0B Swap, `/dev/shm` tmpfs).
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
)

AAB_MIN_MEM_AVAILABLE_HEADROOM_BYTES: int = 12 * 1024**3  # Strict 12 GiB OOM guard on 0B-Swap host
AAB_SHM_MAX_FRACTION_OF_TMPFS: float = 0.88


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


def _read_meminfo_kb() -> dict[str, int]:
    out: dict[str, int] = {}
    meminfo = Path("/proc/meminfo")
    if meminfo.is_file():
        try:
            for line in meminfo.read_text(encoding="utf-8", errors="ignore").splitlines():
                parts = line.split()
                if len(parts) >= 2 and parts[1].isdigit():
                    out[parts[0].rstrip(":")] = int(parts[1])
        except OSError:
            pass
    return out


def _read_mem_total_bytes() -> int:
    info = _read_meminfo_kb()
    return int(info.get("MemTotal", 0)) * 1024


def read_mem_available_bytes() -> int:
    """Reads live OS `MemAvailable` bytes from `/proc/meminfo` (safe on 0B-Swap Linux hosts)."""
    env_override = os.environ.get("AAB_MEM_AVAILABLE_BYTES_OVERRIDE", "").strip()
    if env_override:
        try:
            return max(0, int(env_override))
        except ValueError:
            pass
    info = _read_meminfo_kb()
    if "MemAvailable" in info:
        return int(info["MemAvailable"]) * 1024
    fallback_kb = int(info.get("MemFree", 0)) + int(info.get("Buffers", 0)) + int(info.get("Cached", 0))
    return fallback_kb * 1024


def resolve_dynamic_ram_budget_bytes(
    min_headroom_bytes: int = AAB_MIN_MEM_AVAILABLE_HEADROOM_BYTES,
) -> int:
    """
    Returns maximum in-memory pool bytes usable while preserving `MemAvailable >= 12 GiB` OOM safety margin.
    On a 62 GiB host with ~51 GiB available, yields ~39 GiB usable RAM (0B Swap safe).
    """
    avail = read_mem_available_bytes()
    headroom = max(0, int(min_headroom_bytes))
    return max(0, avail - headroom)


def resolve_dynamic_shm_budget_bytes(
    min_headroom_bytes: int = AAB_MIN_MEM_AVAILABLE_HEADROOM_BYTES,
) -> int:
    """
    Dynamically scales `/dev/shm/aab_scratch` ceiling up to 88% of `/dev/shm` tmpfs total,
    strictly bounded by `MemAvailable - 12 GiB` so tmpfs pages never starve OS headroom.
    """
    ram_budget = resolve_dynamic_ram_budget_bytes(min_headroom_bytes=min_headroom_bytes)
    if os.name != "nt" and AAB_SHM_MOUNT_ROOT.is_dir():
        try:
            du = shutil.disk_usage(AAB_SHM_MOUNT_ROOT)
            tmpfs_cap = int(du.total * AAB_SHM_MAX_FRACTION_OF_TMPFS)
            used_now = max(0, int(du.total - du.free))
            return max(4 * 1024**3, min(tmpfs_cap, used_now + ram_budget))
        except OSError:
            pass
    return max(4 * 1024**3, ram_budget)


def detect_host_hardware() -> dict[str, Any]:
    """Returns live host CPU, SIMD (`avx512f`/`avx512_vnni`), dynamic Max-RAM, and `/dev/shm` telemetry."""
    cpu_count = max(1, int(os.cpu_count() or 2))
    model_name, flags = _read_cpuinfo_flags()
    total_ram = _read_mem_total_bytes()
    mem_avail = read_mem_available_bytes()
    ram_budget = resolve_dynamic_ram_budget_bytes()

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
        "mem_available_bytes": mem_avail,
        "mem_available_gib": round(mem_avail / float(1024**3), 2) if mem_avail else 0.0,
        "oom_headroom_bytes": AAB_MIN_MEM_AVAILABLE_HEADROOM_BYTES,
        "dynamic_ram_budget_bytes": ram_budget,
        "dynamic_ram_budget_gib": round(ram_budget / float(1024**3), 2) if ram_budget else 0.0,
        "dynamic_shm_budget_bytes": resolve_dynamic_shm_budget_bytes(),
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
    return resolve_cpu_budget(cpu_budget, overlapped=overlapped)


def resolve_xfade_workers(
    cpu_budget: int | None = None,
    *,
    overlapped: bool = False,
) -> int:
    return resolve_cpu_budget(cpu_budget, overlapped=overlapped)


def resolve_ffmpeg_threads_per_worker(
    active_workers: int,
    cpu_budget: int | None = None,
    *,
    overlapped: bool = False,
) -> int:
    budget = resolve_cpu_budget(cpu_budget, overlapped=overlapped)
    eff_w = max(1, int(active_workers))
    return max(1, min(4, budget // eff_w))


def resolve_whisper_threads(
    cpu_budget: int | None = None,
    *,
    overlapped: bool = False,
) -> int:
    return resolve_cpu_budget(cpu_budget, overlapped=overlapped)
