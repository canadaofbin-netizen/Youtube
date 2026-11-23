"""
ALL ABOUT BRAIN — Local SSD Media Staging & Single-Pass Inspection Cache
========================================================================
Eliminates Google Drive FUSE (`gdrive`) random-seek I/O bottlenecks and redundant
multi-pass H.264 decoding / Whisper ASR / OpenCV clip inspection on 2-vCPU servers:

  1. `stage_local_file` / `register_staged_copy`: Stages large media files from FUSE to
     local `/tmp/aab_speed_cache/staged/` at most once per `(resolved_path, size, mtime_ns)`,
     computing `SHA-256` in the same single sequential stream read.
  2. `cached_asr_word_timeline`: Runs `faster-whisper` at most once per `final_mp4_sha256`,
     sharing the exact word timeline across `DQ1-DQ12` and `R64` post-hoc QA.
  3. `cached_by_clip_stat`: Stat + boundary-CRC indexed JSON cache on local SSD so
     source clip CV, pastel grading, duration, and dHash probes run once per clip version.
  4. `SharedMp4DecodeSession`: Single-pass sequential `cv2.VideoCapture` frame harvester
     that simultaneously populates `DQ1-DQ12` + `R64` target frames and caches
     `VideoAutopsyEngine.inspect_video_stream` telemetry from a single decode pass.
"""

from __future__ import annotations

import contextlib
import errno
import hashlib
import json
import os
import shutil
import tempfile
import threading
import time
import zlib
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from pipeline.config import (
    AAB_SHM_MAX_TOTAL_BYTES,
    AAB_SHM_MIN_FREE_BYTES,
    AAB_SHM_MOUNT_ROOT,
    AAB_SHM_SCRATCH_DEFAULT_DIR,
    AAB_SPEED_CACHE_POSTHOC_CV_MAX_BYTES,
    AAB_SPEED_CACHE_SEGMENTS_MAX_BYTES,
    AAB_SPEED_CACHE_STAGED_MAX_BYTES,
    AAB_SPEED_CACHE_TTS_NPZ_MAX_BYTES,
)

_CACHE_LOCK = threading.RLock()
_MEM_JSON_CACHE: dict[str, Any] = {}
_MEM_SHA_CACHE: dict[str, str] = {}
_ACTIVE_FRAME_SESSION: dict[str, Any] | None = None
_SESSION_TLS = threading.local()

_MAX_STAGED_BYTES = AAB_SPEED_CACHE_STAGED_MAX_BYTES      # ~8.0 GB LRU cap in /dev/shm/aab_scratch
MAX_SEGMENTS_BYTES = AAB_SPEED_CACHE_SEGMENTS_MAX_BYTES   # ~6.0 GB LRU cap for segment caches
MAX_TTS_NPZ_BYTES = AAB_SPEED_CACHE_TTS_NPZ_MAX_BYTES     # ~2.5 GB LRU cap for tts_npz
MAX_POSTHOC_CV_BYTES = AAB_SPEED_CACHE_POSTHOC_CV_MAX_BYTES  # ~2.0 GB LRU cap for posthoc_cv


def get_ram_scratch_root() -> Path:
    """
    Returns `/dev/shm/aab_scratch` (`20,000+ MB/s` tmpfs) whenever `/dev/shm` is writable
    with >= `AAB_SHM_MIN_FREE_BYTES` free, falling back cleanly to `<tempdir>/aab_scratch`.
    Honors `AAB_SCRATCH_DIR` override for deterministic testing.
    """
    override = os.environ.get("AAB_SCRATCH_DIR", "").strip()
    if override:
        root = Path(override)
        root.mkdir(parents=True, exist_ok=True)
        return root
    if os.name != "nt" and AAB_SHM_MOUNT_ROOT.is_dir() and os.access(AAB_SHM_MOUNT_ROOT, os.W_OK | os.X_OK):
        try:
            if shutil.disk_usage(AAB_SHM_MOUNT_ROOT).free >= int(AAB_SHM_MIN_FREE_BYTES):
                AAB_SHM_SCRATCH_DEFAULT_DIR.mkdir(parents=True, exist_ok=True)
                return AAB_SHM_SCRATCH_DEFAULT_DIR
        except OSError:
            pass
    fallback = Path(tempfile.gettempdir()) / "aab_scratch"
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback


def ram_tempdir(prefix: str = "aab_") -> tempfile.TemporaryDirectory[str]:
    """Creates an auto-cleaned `TemporaryDirectory` inside `get_ram_scratch_root()` (`/dev/shm/aab_scratch`)."""
    root = get_ram_scratch_root()
    return tempfile.TemporaryDirectory(prefix=prefix, dir=str(root))


def is_ephemeral_scratch_path(path: Path | str) -> bool:
    """
    Guard 2: Recognizes BOTH `/tmp` and `/dev/shm` (plus `tempfile.gettempdir()`, `AAB_SCRATCH_DIR`,
    and `AAB_SPEED_CACHE_DIR`) as ephemeral local scratch so `/dev/shm` files:
      1. Take the fast boundary-CRC32 path in `_file_stat_fingerprint`,
      2. Never trigger FUSE `persistent_sha256_cache.json` `fcntl.flock` writes or dead-path pollution,
      3. Are never redundantly re-copied by `stage_local_file` or `media_integrity` dHash checks.
    """
    try:
        resolved_s = str(Path(path).resolve())
    except OSError:
        resolved_s = os.path.abspath(str(path))
    prefixes: list[str] = ["/tmp", "/dev/shm"]
    with contextlib.suppress(OSError):
        prefixes.append(str(Path(tempfile.gettempdir()).resolve()))
    for env_k in ("AAB_SCRATCH_DIR", "AAB_SPEED_CACHE_DIR"):
        ev = os.environ.get(env_k, "").strip()
        if ev:
            with contextlib.suppress(OSError):
                prefixes.append(str(Path(ev).resolve()))
    for pref in prefixes:
        norm = pref.rstrip("/")
        if not norm:
            continue
        if resolved_s == norm or resolved_s.startswith(norm + "/"):
            return True
    return False


def atomic_commit_from_scratch(
    src: Path | str,
    dst: Path | str,
    *,
    suffix: str | None = None,
    keep_src: bool = False,
) -> Path:
    """
    Guard 1 (`EXDEV`-safe atomic commit):
      - Never calls `os.replace(shm_src, fuse_or_ext4_dst)` directly across filesystems (`Errno 18 EXDEV`).
      - If `src` and `dst.parent` share the same `st_dev` AND `keep_src=False`, performs an instant `os.replace`.
      - Otherwise copies `src` into a hidden sibling `.tmp` file inside `dst.parent` (same mount as `dst`),
        atomically swaps `os.replace(tmp_dst, dst)` with retry backoff for `fuse.rclone`, and cleans up `src`
        unless `keep_src=True`.
    """
    src_p = Path(src)
    dst_p = Path(dst)
    if not src_p.exists():
        raise FileNotFoundError(f"atomic_commit_from_scratch source missing: {src_p}")
    dst_p.parent.mkdir(parents=True, exist_ok=True)
    if src_p.resolve() == dst_p.resolve():
        return dst_p

    if not keep_src:
        try:
            if src_p.stat().st_dev == dst_p.parent.stat().st_dev:
                os.replace(src_p, dst_p)
                return dst_p
        except OSError as same_dev_exc:
            if same_dev_exc.errno != errno.EXDEV:
                pass

    tmp_dst = (
        dst_p.with_suffix(suffix)
        if suffix
        else dst_p.with_name(f".{dst_p.name}.tmp.{os.getpid()}.{threading.get_ident()}")
    )
    try:
        shutil.copy2(src_p, tmp_dst)
        for attempt in range(5):
            try:
                os.replace(tmp_dst, dst_p)
                break
            except OSError:
                if attempt == 4:
                    raise
                time.sleep(0.15 * (attempt + 1))
    except BaseException:
        with contextlib.suppress(OSError):
            tmp_dst.unlink(missing_ok=True)
        raise

    if not keep_src:
        with contextlib.suppress(OSError):
            src_p.unlink(missing_ok=True)
    return dst_p


def prune_speed_cache_subdir(subdir: str, max_bytes: int) -> int:
    """Prunes oldest files in `/tmp/aab_speed_cache/<subdir>` down to 75% of `max_bytes`."""
    target_dir = get_speed_cache_dir() / subdir
    if not target_dir.exists():
        return 0
    removed = 0
    with _CACHE_LOCK:
        try:
            entries = []
            for p in target_dir.iterdir():
                if p.is_file():
                    with contextlib.suppress(OSError):
                        st = p.stat()
                        entries.append((st.st_mtime, st.st_size, p))
            total = sum(sz for _, sz, _ in entries)
            if total <= max_bytes:
                return 0
            entries.sort(key=lambda item: item[0])
            floor = int(max_bytes * 0.75)
            for _, sz, victim in entries:
                if total <= floor:
                    break
                try:
                    victim.unlink(missing_ok=True)
                    total -= sz
                    removed += 1
                except OSError:
                    continue
        except OSError:
            return removed
    return removed


def get_speed_cache_dir() -> Path:
    override = os.environ.get("AAB_SPEED_CACHE_DIR", "").strip()
    root = Path(override) if override else (get_ram_scratch_root() / "speed_cache")
    root.mkdir(parents=True, exist_ok=True)
    return root


def enforce_ram_scratch_budget(max_total_bytes: int = AAB_SHM_MAX_TOTAL_BYTES) -> dict[str, int]:
    """Prunes `speed_cache` subtrees under `/dev/shm/aab_scratch` so RAM-disk usage stays <= `max_total_bytes` (22 GiB)."""
    removed_staged = prune_speed_cache_subdir("staged", int(_MAX_STAGED_BYTES))
    removed_tts = prune_speed_cache_subdir("tts_npz", int(MAX_TTS_NPZ_BYTES))
    removed_cv = prune_speed_cache_subdir("posthoc_cv", int(MAX_POSTHOC_CV_BYTES))

    # Recursively prune `segments/` across project hashes if over MAX_SEGMENTS_BYTES
    seg_root = get_speed_cache_dir() / "segments"
    removed_segs = 0
    if seg_root.exists():
        with _CACHE_LOCK:
            entries: list[tuple[float, int, Path]] = []
            for p in seg_root.rglob("*"):
                if p.is_file():
                    with contextlib.suppress(OSError):
                        st = p.stat()
                        entries.append((st.st_mtime, st.st_size, p))
            total_seg = sum(sz for _, sz, _ in entries)
            if total_seg > int(MAX_SEGMENTS_BYTES):
                entries.sort(key=lambda item: item[0])
                floor = int(MAX_SEGMENTS_BYTES * 0.75)
                for _, sz, victim in entries:
                    if total_seg <= floor:
                        break
                    with contextlib.suppress(OSError):
                        victim.unlink(missing_ok=True)
                        total_seg -= sz
                        removed_segs += 1

    # Global hard ceiling across entire scratch root (excludes active dirs modified within last 600s)
    scratch_root = get_ram_scratch_root()
    removed_global = 0
    if scratch_root.exists():
        with _CACHE_LOCK:
            now_ts = time.time()
            all_files: list[tuple[float, int, Path]] = []
            total_all = 0
            for p in scratch_root.rglob("*"):
                if p.is_file():
                    with contextlib.suppress(OSError):
                        st = p.stat()
                        total_all += st.st_size
                        if now_ts - st.st_mtime >= 600.0:
                            all_files.append((st.st_mtime, st.st_size, p))
            if total_all > int(max_total_bytes):
                all_files.sort(key=lambda item: item[0])
                floor_all = int(max_total_bytes * 0.80)
                for _, sz, victim in all_files:
                    if total_all <= floor_all:
                        break
                    with contextlib.suppress(OSError):
                        victim.unlink(missing_ok=True)
                        total_all -= sz
                        removed_global += 1

    return {
        "removed_staged": removed_staged,
        "removed_segments": removed_segs,
        "removed_tts_npz": removed_tts,
        "removed_posthoc_cv": removed_cv,
        "removed_global": removed_global,
    }


def _file_stat_fingerprint(
    path: Path,
    sample_boundary_crc: bool = False,
    *,
    byte_source: Path | None = None,
) -> str:
    """
    Builds a fast deterministic cache key from `(resolved_path, st_size, st_mtime_ns)`
    plus an optional boundary CRC32 (always cheap on `/tmp` or `/dev/shm` or small files, or from `byte_source`
    to avoid FUSE read-back) so in-place same-nanosecond mutations in tests immediately invalidate cached entries.
    """
    resolved = path.resolve()
    st = resolved.stat()
    crc_src = Path(byte_source) if byte_source is not None else resolved
    crc_tag = ""
    if sample_boundary_crc or st.st_size <= 131_072 or is_ephemeral_scratch_path(resolved):
        try:
            src_size = crc_src.stat().st_size if byte_source is not None else st.st_size
            with crc_src.open("rb") as fh:
                head = fh.read(4096)
                if src_size > 8192:
                    fh.seek(max(0, src_size - 4096))
                    tail = fh.read(4096)
                else:
                    tail = b""
            crc = zlib.crc32(head + tail) & 0xFFFFFFFF
            crc_tag = f"|{crc:08x}"
        except OSError:
            crc_tag = "|ioerr"
    raw = f"{resolved}|{st.st_size}|{st.st_mtime_ns}{crc_tag}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:24]


def _prune_staged_dir_unlocked(staged_dir: Path) -> None:
    try:
        entries = [p for p in staged_dir.iterdir() if p.is_file() and not p.name.endswith(".sha256")]
        total = sum(p.stat().st_size for p in entries)
        if total <= _MAX_STAGED_BYTES:
            return
        entries.sort(key=lambda p: p.stat().st_mtime)
        for victim in entries:
            if total <= int(_MAX_STAGED_BYTES * 0.75):
                break
            try:
                sz = victim.stat().st_size
                victim.unlink(missing_ok=True)
                (staged_dir / f"{victim.stem}.sha256").unlink(missing_ok=True)
                total -= sz
            except OSError:
                continue
    except OSError:
        return


def compute_stream_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(2 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def get_persistent_sha_cache_path() -> Path:
    override = os.environ.get("AAB_PERSISTENT_SHA_CACHE_PATH", "").strip()
    if override:
        return Path(override)
    from pipeline.config import CHANNEL_ROOT

    return CHANNEL_ROOT / ".cache" / "persistent_sha256_cache.json"


def _should_persist_sha_for_path(path: Path) -> bool:
    resolved_s = str(path.resolve())
    if resolved_s == "/dev/shm" or resolved_s.startswith("/dev/shm/"):
        return False
    if os.environ.get("AAB_PERSISTENT_SHA_CACHE_PATH", "").strip():
        return True
    return not is_ephemeral_scratch_path(path)


def _load_persistent_sha_entry(fp: str) -> str | None:
    cache_path = get_persistent_sha_cache_path()
    if not cache_path.exists():
        return None
    try:
        doc = json.loads(cache_path.read_text(encoding="utf-8"))
        entries = doc.get("entries") if isinstance(doc, dict) else None
        if isinstance(entries, dict):
            rec = entries.get(fp)
            if isinstance(rec, str) and len(rec) == 64:
                return rec
            if isinstance(rec, list) and len(rec) >= 1 and isinstance(rec[0], str) and len(rec[0]) == 64:
                return rec[0]
    except Exception:  # noqa: BLE001
        return None
    return None


def _store_persistent_sha_entry(fp: str, sha_val: str) -> None:
    import time as _time
    from pipeline.cdp_tab_lease import get_aab_locks_dir
    from pipeline.config import PERSISTENT_SHA_CACHE_MAX_ENTRIES

    try:
        import fcntl as _fcntl
    except ImportError:  # pragma: no cover
        _fcntl = None  # type: ignore[assignment]

    from pipeline.cdp_tab_lease import acquire_shared_flock

    cache_path = get_persistent_sha_cache_path()
    lock_path = get_aab_locks_dir() / "persistent_sha.lock"
    with _CACHE_LOCK:
        fh = None
        try:
            fh = acquire_shared_flock(lock_path)
            entries: dict[str, list[Any]] = {}
            if cache_path.exists():
                with contextlib.suppress(Exception):
                    loaded = json.loads(cache_path.read_text(encoding="utf-8"))
                    raw_e = loaded.get("entries") if isinstance(loaded, dict) else None
                    if isinstance(raw_e, dict):
                        for k, v in raw_e.items():
                            if isinstance(v, list) and len(v) >= 2 and isinstance(v[0], str):
                                entries[str(k)] = [v[0], float(v[1])]
                            elif isinstance(v, str) and len(v) == 64:
                                entries[str(k)] = [v, 0.0]
            entries[fp] = [sha_val, round(_time.time(), 2)]
            max_cap = max(256, int(PERSISTENT_SHA_CACHE_MAX_ENTRIES))
            if len(entries) > max_cap:
                keep_n = int(max_cap * 0.85)
                ordered = sorted(entries.items(), key=lambda kv: float(kv[1][1]), reverse=True)[:keep_n]
                entries = dict(ordered)
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            tmp_p = cache_path.parent / f".tmp_{os.getpid()}_{threading.get_ident()}_{cache_path.name}"
            payload = json.dumps({"version": 1, "entries": entries}, separators=(",", ":"))
            try:
                tmp_p.write_text(payload, encoding="utf-8")
                os.replace(tmp_p, cache_path)
            except OSError:
                tmp_p.unlink(missing_ok=True)
                raise
        except OSError as exc:
            import logging

            logging.getLogger("media_cache").warning("Persistent SHA cache update failed for %s: %s", cache_path, exc)
        finally:
            if fh is not None and _fcntl is not None:
                with contextlib.suppress(OSError):
                    _fcntl.flock(fh.fileno(), _fcntl.LOCK_UN)
            if fh is not None:
                with contextlib.suppress(OSError):
                    fh.close()


def clear_in_memory_sha_cache() -> None:
    """Clears in-process `_MEM_SHA_CACHE` (used in tests to verify persistent disk cache hits)."""
    with _CACHE_LOCK:
        _MEM_SHA_CACHE.clear()


def fast_file_sha256(path: Path) -> str:
    """
    Stat + boundary-CRC indexed SHA-256 lookup backed by in-memory `_MEM_SHA_CACHE`
    plus the compact persistent JSON store (`persistent_sha256_cache.json`), surviving
    `/tmp` speed-cache purges without creating thousands of tiny `.txt` files.
    Note: Forensic `ProjectStorage.verify_integrity()` intentionally bypasses this
    and always reads raw disk bytes to detect silent storage bit-rot.
    """
    p = Path(path)
    fp = _file_stat_fingerprint(p, sample_boundary_crc=True)
    with _CACHE_LOCK:
        hit = _MEM_SHA_CACHE.get(fp)
        if hit:
            return hit
    persist_ok = _should_persist_sha_for_path(p)
    if persist_ok:
        disk_hit = _load_persistent_sha_entry(fp)
        if disk_hit:
            with _CACHE_LOCK:
                _MEM_SHA_CACHE[fp] = disk_hit
            return disk_hit
    val = compute_stream_sha256(p)
    if persist_ok:
        _store_persistent_sha_entry(fp, val)
    with _CACHE_LOCK:
        if len(_MEM_SHA_CACHE) > 16384:
            _MEM_SHA_CACHE.clear()
        _MEM_SHA_CACHE[fp] = val
    return val


def stage_local_file(src_path: Path) -> tuple[Path, str]:
    """
    Ensures `src_path` is staged on local `/dev/shm` RAM-disk (or `/tmp` fallback) and returns `(local_path, sha256)`.
    If `src_path` is already under ephemeral scratch (`/tmp` or `/dev/shm`), hashes once without duplicating the file.
    """
    src = Path(src_path)
    resolved = src.resolve()
    st_size = resolved.stat().st_size
    if is_ephemeral_scratch_path(resolved):
        return resolved, fast_file_sha256(resolved)

    fp = _file_stat_fingerprint(resolved, sample_boundary_crc=False)
    staged_dir = get_speed_cache_dir() / "staged"
    staged_dir.mkdir(parents=True, exist_ok=True)
    ext = resolved.suffix.lower() or ".bin"
    dst = staged_dir / f"{fp}{ext}"
    sha_sidecar = staged_dir / f"{fp}.sha256"

    with _CACHE_LOCK:
        if dst.exists() and sha_sidecar.exists():
            try:
                if dst.stat().st_size == st_size:
                    sha_val = sha_sidecar.read_text(encoding="utf-8").strip()
                    if len(sha_val) == 64:
                        os.utime(dst, None)
                        return dst, sha_val
            except OSError:
                pass

    tmp_dst = staged_dir / f".tmp_{os.getpid()}_{threading.get_ident()}_{fp}{ext}"
    h = hashlib.sha256()
    with resolved.open("rb") as rfh, tmp_dst.open("wb") as wfh:
        for chunk in iter(lambda: rfh.read(2 * 1024 * 1024), b""):
            h.update(chunk)
            wfh.write(chunk)
    sha_val = h.hexdigest()

    fp_crc = _file_stat_fingerprint(resolved, sample_boundary_crc=True)
    with _CACHE_LOCK:
        try:
            os.replace(tmp_dst, dst)
            sha_sidecar.write_text(sha_val, encoding="utf-8")
            _MEM_SHA_CACHE[fp_crc] = sha_val
            _prune_staged_dir_unlocked(staged_dir)
        except OSError:
            tmp_dst.unlink(missing_ok=True)
            if _should_persist_sha_for_path(resolved):
                _store_persistent_sha_entry(fp_crc, sha_val)
            return resolved, sha_val
    if _should_persist_sha_for_path(resolved):
        _store_persistent_sha_entry(fp_crc, sha_val)
    return dst, sha_val


def register_staged_copy(local_src: Path, dest_path: Path) -> str:
    """
    Registers an already-rendered local `/tmp` file (`local_src`) as the staged cache entry
    for `dest_path` immediately after copying `local_src -> dest_path`, avoiding any FUSE read-back.
    """
    dest = Path(dest_path).resolve()
    sha_val = compute_stream_sha256(local_src)
    try:
        fp = _file_stat_fingerprint(dest, sample_boundary_crc=False, byte_source=local_src)
        fp_crc = _file_stat_fingerprint(dest, sample_boundary_crc=True, byte_source=local_src)
        staged_dir = get_speed_cache_dir() / "staged"
        staged_dir.mkdir(parents=True, exist_ok=True)
        ext = dest.suffix.lower() or ".bin"
        dst = staged_dir / f"{fp}{ext}"
        sha_sidecar = staged_dir / f"{fp}.sha256"
        with _CACHE_LOCK:
            shutil.copy2(local_src, dst)
            sha_sidecar.write_text(sha_val, encoding="utf-8")
            _MEM_SHA_CACHE[fp_crc] = sha_val
            _prune_staged_dir_unlocked(staged_dir)
        if _should_persist_sha_for_path(dest):
            _store_persistent_sha_entry(fp_crc, sha_val)
    except OSError as exc:
        import logging

        logging.getLogger("media_cache").warning("register_staged_copy failed for %s: %s", dest, exc)
    return sha_val


def get_cached_json(namespace: str, key: str) -> Any | None:
    mem_k = f"{namespace}:{key}"
    with _CACHE_LOCK:
        if mem_k in _MEM_JSON_CACHE:
            return json.loads(json.dumps(_MEM_JSON_CACHE[mem_k]))
    path = get_speed_cache_dir() / "json" / namespace / f"{key}.json"
    if not path.exists():
        return None
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
        with _CACHE_LOCK:
            if len(_MEM_JSON_CACHE) > 2048:
                _MEM_JSON_CACHE.clear()
            _MEM_JSON_CACHE[mem_k] = doc
        return json.loads(json.dumps(doc))
    except Exception:  # noqa: BLE001
        return None


def put_cached_json(namespace: str, key: str, payload: Any) -> None:
    mem_k = f"{namespace}:{key}"
    serialized = json.dumps(payload, ensure_ascii=False)
    cloned = json.loads(serialized)
    with _CACHE_LOCK:
        if len(_MEM_JSON_CACHE) > 2048:
            _MEM_JSON_CACHE.clear()
        _MEM_JSON_CACHE[mem_k] = cloned
    out_dir = get_speed_cache_dir() / "json" / namespace
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        tmp_p = out_dir / f".tmp_{os.getpid()}_{threading.get_ident()}_{key}.json"
        tmp_p.write_text(serialized, encoding="utf-8")
        os.replace(tmp_p, out_dir / f"{key}.json")
    except OSError:
        return


def cached_by_clip_stat(
    clip_path: Path,
    namespace: str,
    compute_fn: Callable[[Path], Any],
    extra_key: str = "",
    stage_on_miss: bool = True,
) -> Any:
    """
    Evaluates `compute_fn(local_clip_path)` at most once per `(clip_path, size, mtime_ns, boundary_crc, extra_key)`.
    Stages `clip_path` onto local `/tmp` on cache miss so OpenCV/FFmpeg never random-seeks over FUSE.
    """
    p = Path(clip_path)
    if not p.exists():
        return compute_fn(p)
    fp = _file_stat_fingerprint(p, sample_boundary_crc=True)
    key = hashlib.sha1(f"{fp}|{extra_key}".encode("utf-8")).hexdigest()[:24]
    hit = get_cached_json(namespace, key)
    if hit is not None:
        return hit
    target = stage_local_file(p)[0] if stage_on_miss else p
    res = compute_fn(target)
    put_cached_json(namespace, key, res)
    return res


def cached_asr_word_timeline(mp4_path: Path, *, cpu_threads: int | None = None) -> list[tuple[float, float, str]]:
    """
    Runs `faster-whisper` word-timestamp alignment at most once per unique `mp4_sha256`,
    sharing the exact word timeline across `DQ1-DQ12` and `R64` post-hoc QA.
    """
    import inspect
    import re
    import subprocess

    from pipeline.voice_fallback import _ffmpeg, _whisper_model

    local_mp4, sha256 = stage_local_file(Path(mp4_path))
    hit = get_cached_json("mp4_asr_v2", sha256)
    if isinstance(hit, list):
        return [(float(x[0]), float(x[1]), str(x[2])) for x in hit]

    with ram_tempdir(prefix="aab_shared_asr_") as td:
        raw_f32 = Path(td) / "aud16k.f32"
        res = subprocess.run(
            [
                _ffmpeg(), "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
                "-i", str(local_mp4), "-vn", "-ac", "1", "-ar", "16000", "-f", "f32le", str(raw_f32),
            ],
            capture_output=True,
            check=False,
            timeout=120,
            stdin=subprocess.DEVNULL,
        )
        if res.returncode != 0 or not raw_f32.exists():
            return []
        pcm16 = np.frombuffer(raw_f32.read_bytes(), dtype=np.float32).copy()

    wm_sig = inspect.signature(_whisper_model)
    wm = _whisper_model(cpu_threads) if ("cpu_threads" in wm_sig.parameters and cpu_threads) else _whisper_model()
    segs, _ = wm.transcribe(
        pcm16,
        word_timestamps=True,
        language="en",
        condition_on_previous_text=False,
    )
    words = [
        (float(w.start), float(w.end), re.sub(r"[^a-z0-9]", "", str(w.word).lower()))
        for s in segs
        for w in (s.words or [])
        if str(w.word).strip()
    ]
    put_cached_json("mp4_asr_v2", sha256, [[t0, t1, tok] for t0, t1, tok in words])
    return words


@contextlib.contextmanager
def shared_mp4_decode_session(
    mp4_path: Path,
    frame_indices: set[int] | None = None,
) -> Iterator[dict[str, Any]]:
    """
    Context manager that decodes `mp4_path` from local `/tmp` in ONE sequential pass,
    caching requested full-res BGR frames in thread-local memory for the duration of the `with` block
    (e.g., across `verify_final_mp4_against_contract` + `run_posthoc_semantic_qa` + `VideoAutopsyEngine`),
    and immediately freeing frame memory on exit without colliding across concurrent worker threads.
    """
    local_mp4, sha256 = stage_local_file(Path(mp4_path))
    cap = cv2.VideoCapture(str(local_mp4))
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 24.0)
    total_fc = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    frames_map: dict[int, np.ndarray] = {}
    even_small_bgr: dict[int, np.ndarray] = {}
    decoded_fc = 0

    wanted = {max(0, min(max(0, total_fc - 1), int(i))) for i in (frame_indices or set())} if total_fc > 0 else set()
    if cap.isOpened():
        while True:
            ok, frm = cap.read()
            if not ok or frm is None:
                break
            cur_i = decoded_fc
            decoded_fc += 1
            if cur_i % 2 == 0:
                even_small_bgr[cur_i] = cv2.resize(frm, (180, 320), interpolation=cv2.INTER_AREA)
            if cur_i in wanted:
                frames_map[cur_i] = frm
        cap.release()

    session = {
        "sha256": sha256,
        "local_mp4": local_mp4,
        "fps": fps,
        "header_fc": total_fc,
        "decoded_fc": decoded_fc,
        "frames": frames_map,
        "even_small_bgr": even_small_bgr,
    }
    prev = getattr(_SESSION_TLS, "active_frame_session", None)
    _SESSION_TLS.active_frame_session = session
    try:
        yield session
    finally:
        _SESSION_TLS.active_frame_session = prev
        frames_map.clear()
        even_small_bgr.clear()


def get_active_mp4_session(sha256: str) -> dict[str, Any] | None:
    sess = getattr(_SESSION_TLS, "active_frame_session", None)
    if sess is not None and sess.get("sha256") == sha256:
        return sess
    return None


def decode_needed_frames(local_mp4: Path, sha256: str, needed_fidxs: set[int]) -> tuple[float, int, dict[int, np.ndarray]]:
    """
    Returns `(fps, total_fc, frame_cache)` using the active `shared_mp4_decode_session`
    when available (retrieving any extra indices on demand), or a single sequential pass.
    """
    sess = get_active_mp4_session(sha256)
    if sess is not None:
        fps = float(sess["fps"])
        total_fc = int(sess["header_fc"] or sess["decoded_fc"])
        cached_frames: dict[int, np.ndarray] = sess["frames"]
        out: dict[int, np.ndarray] = {}
        missing: list[int] = []
        for idx in sorted(needed_fidxs):
            clamped = max(0, min(max(0, total_fc - 1), int(idx)))
            if clamped in cached_frames:
                out[clamped] = cached_frames[clamped]
            else:
                missing.append(clamped)
        if missing:
            cap = cv2.VideoCapture(str(local_mp4))
            max_m = max(missing)
            miss_set = set(missing)
            for cur_i in range(max_m + 1):
                if not cap.grab():
                    break
                if cur_i in miss_set:
                    ok_r, frm_r = cap.retrieve()
                    if ok_r and frm_r is not None:
                        out[cur_i] = frm_r
                        cached_frames[cur_i] = frm_r
            cap.release()
        return fps, total_fc, out

    cap = cv2.VideoCapture(str(local_mp4))
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 24.0)
    total_fc = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    frame_cache: dict[int, np.ndarray] = {}
    if needed_fidxs and total_fc > 0:
        clamped_set = {max(0, min(total_fc - 1, int(i))) for i in needed_fidxs}
        max_f = max(clamped_set)
        for cur_i in range(max_f + 1):
            if not cap.grab():
                break
            if cur_i in clamped_set:
                ok_r, frm_r = cap.retrieve()
                if ok_r and frm_r is not None:
                    frame_cache[cur_i] = frm_r
    cap.release()
    return fps, total_fc, frame_cache
