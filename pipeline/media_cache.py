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
import hashlib
import json
import os
import shutil
import tempfile
import threading
import zlib
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import cv2
import numpy as np

_CACHE_LOCK = threading.RLock()
_MEM_JSON_CACHE: dict[str, Any] = {}
_MEM_SHA_CACHE: dict[str, str] = {}
_ACTIVE_FRAME_SESSION: dict[str, Any] | None = None
_SESSION_TLS = threading.local()

_MAX_STAGED_BYTES = 2_600_000_000  # ~2.6 GB LRU cap in /tmp


def get_speed_cache_dir() -> Path:
    override = os.environ.get("AAB_SPEED_CACHE_DIR", "").strip()
    root = Path(override) if override else (Path(tempfile.gettempdir()) / "aab_speed_cache")
    root.mkdir(parents=True, exist_ok=True)
    return root


def _file_stat_fingerprint(path: Path, sample_boundary_crc: bool = False) -> str:
    """
    Builds a fast deterministic cache key from `(resolved_path, st_size, st_mtime_ns)`
    plus an optional boundary CRC32 (always cheap on `/tmp` or small files) so in-place
    same-nanosecond mutations in tests immediately invalidate cached entries.
    """
    resolved = path.resolve()
    st = resolved.stat()
    crc_tag = ""
    if sample_boundary_crc or st.st_size <= 131_072 or str(resolved).startswith("/tmp"):
        try:
            with resolved.open("rb") as fh:
                head = fh.read(4096)
                if st.st_size > 8192:
                    fh.seek(max(0, st.st_size - 4096))
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


def fast_file_sha256(path: Path) -> str:
    """
    Stat-indexed SHA-256 lookup backed by local `/tmp` SSD cache.
    Note: Forensic `ProjectStorage.verify_integrity()` intentionally bypasses this
    and always reads raw disk bytes to detect silent storage bit-rot.
    """
    p = Path(path)
    fp = _file_stat_fingerprint(p, sample_boundary_crc=True)
    with _CACHE_LOCK:
        hit = _MEM_SHA_CACHE.get(fp)
        if hit:
            return hit
    sha_dir = get_speed_cache_dir() / "sha256"
    sha_file = sha_dir / f"{fp}.txt"
    if sha_file.exists():
        try:
            val = sha_file.read_text(encoding="utf-8").strip()
            if len(val) == 64:
                with _CACHE_LOCK:
                    _MEM_SHA_CACHE[fp] = val
                return val
        except OSError:
            pass
    val = compute_stream_sha256(p)
    try:
        sha_dir.mkdir(parents=True, exist_ok=True)
        sha_file.write_text(val, encoding="utf-8")
    except OSError:
        pass
    with _CACHE_LOCK:
        _MEM_SHA_CACHE[fp] = val
    return val


def stage_local_file(src_path: Path) -> tuple[Path, str]:
    """
    Ensures `src_path` is staged on local `/tmp` SSD and returns `(local_path, sha256)`.
    If `src_path` is already under `/tmp`, hashes once without duplicating the file.
    """
    src = Path(src_path)
    resolved = src.resolve()
    st_size = resolved.stat().st_size
    if str(resolved).startswith(str(Path(tempfile.gettempdir()).resolve())):
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

    with _CACHE_LOCK:
        try:
            os.replace(tmp_dst, dst)
            sha_sidecar.write_text(sha_val, encoding="utf-8")
            _MEM_SHA_CACHE[_file_stat_fingerprint(resolved, sample_boundary_crc=True)] = sha_val
            _prune_staged_dir_unlocked(staged_dir)
        except OSError:
            tmp_dst.unlink(missing_ok=True)
            return resolved, sha_val
    return dst, sha_val


def register_staged_copy(local_src: Path, dest_path: Path) -> str:
    """
    Registers an already-rendered local `/tmp` file (`local_src`) as the staged cache entry
    for `dest_path` immediately after copying `local_src -> dest_path`, avoiding any FUSE read-back.
    """
    dest = Path(dest_path).resolve()
    sha_val = compute_stream_sha256(local_src)
    try:
        fp = _file_stat_fingerprint(dest, sample_boundary_crc=False)
        staged_dir = get_speed_cache_dir() / "staged"
        staged_dir.mkdir(parents=True, exist_ok=True)
        ext = dest.suffix.lower() or ".bin"
        dst = staged_dir / f"{fp}{ext}"
        sha_sidecar = staged_dir / f"{fp}.sha256"
        with _CACHE_LOCK:
            shutil.copy2(local_src, dst)
            sha_sidecar.write_text(sha_val, encoding="utf-8")
            _MEM_SHA_CACHE[_file_stat_fingerprint(dest, sample_boundary_crc=True)] = sha_val
            _prune_staged_dir_unlocked(staged_dir)
    except OSError:
        pass
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


def cached_asr_word_timeline(mp4_path: Path) -> list[tuple[float, float, str]]:
    """
    Runs `faster-whisper` word-timestamp alignment at most once per unique `mp4_sha256`,
    sharing the exact word timeline across `DQ1-DQ12` and `R64` post-hoc QA.
    """
    import re
    import subprocess

    from pipeline.voice_fallback import _ffmpeg, _whisper_model

    local_mp4, sha256 = stage_local_file(Path(mp4_path))
    hit = get_cached_json("mp4_asr_v1", sha256)
    if isinstance(hit, list):
        return [(float(x[0]), float(x[1]), str(x[2])) for x in hit]

    with tempfile.TemporaryDirectory(prefix="aab_shared_asr_") as td:
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

    segs, _ = _whisper_model().transcribe(pcm16, word_timestamps=True, language="en")
    words = [
        (float(w.start), float(w.end), re.sub(r"[^a-z0-9]", "", str(w.word).lower()))
        for s in segs
        for w in (s.words or [])
        if str(w.word).strip()
    ]
    put_cached_json("mp4_asr_v1", sha256, [[t0, t1, tok] for t0, t1, tok in words])
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
