"""
ALL ABOUT BRAIN — Cross-Process CDP Tab Lease & Anti-Tab-Stealing Isolation
===========================================================================
Prevents concurrent subagents, sharded Google Flow workers, and YouTube Studio
watchdogs sharing Naver Whale (`127.0.0.1:9222`) from hijacking, navigating,
or closing one another's tabs or pre-existing user personal tabs.

Core Guarantees:
  1. File-locked (`fcntl.flock`) JSON registry in `/tmp/aab_cdp_leases.json`.
  2. Automatic eviction of dead OS PIDs (`os.kill(pid, 0)` + Linux zombie state check) and
     expired heartbeats (`ttl_sec`).
  3. Fail-closed conflict detection (`TabLeaseConflictError`) when a tab is leased by another
     active `owner_id`.
  4. Background tab creation via CDP `Target.createTarget({"url": ..., "background": True})`
     paired with per-tab `Emulation.setFocusEmulationEnabled({"enabled": True})` so background
     workers never steal window/tab focus from the user or sibling agents.
  5. `release_and_close_leased_tab()` strictly refuses to close:
       - unleased tabs (e.g. pre-existing user tabs),
       - tabs where `created_by_pipeline == False`, or
       - tabs leased by another active `owner_id` / live PID.
"""

from __future__ import annotations

import asyncio
import contextlib
import inspect
import json
import os
import tempfile
import threading
import time
import urllib.parse
import urllib.request
import uuid
from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from typing import Any

try:
    import fcntl as _fcntl
except ImportError:  # pragma: no cover - Windows fallback
    _fcntl = None  # type: ignore[assignment]

DEFAULT_TAB_LEASE_TTL_SEC: float = 900.0
DEFAULT_CDP_LEASES_FILENAME: str = "aab_cdp_leases.json"
_PROC_LOCK = threading.RLock()


class TabLeaseConflictError(RuntimeError):
    """Raised when attempting to claim a CDP page target already leased by another live owner."""


def get_aab_locks_dir() -> Path:
    """Returns the centralized `/tmp/aab_locks` directory (`0o1777` sticky bit) so `/tmp` root stays clean."""
    override = os.environ.get("AAB_LOCKS_DIR", "").strip()
    root = Path(override) if override else (Path(tempfile.gettempdir()) / "aab_locks")
    root.mkdir(parents=True, exist_ok=True)
    if os.name != "nt":
        with contextlib.suppress(OSError):
            if root.stat().st_uid == os.getuid():
                os.chmod(root, 0o1777)
    return root


def acquire_shared_flock(lock_path: Path, *, retries: int = 3, backoff_sec: float = 0.04) -> Any:
    """
    Opens `lock_path` in `a+` mode, ensures `0o666` permissions when owned, and acquires an
    exclusive `fcntl.flock`. Raises `OSError` on failure — NEVER falls back to unlocked execution.
    """
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    if _fcntl is None:
        return open(lock_path, "a+", encoding="utf-8")
    last_err: OSError | None = None
    for attempt in range(max(1, int(retries))):
        fh = None
        try:
            fh = open(lock_path, "a+", encoding="utf-8")
            if os.name != "nt":
                with contextlib.suppress(OSError):
                    if lock_path.stat().st_uid == os.getuid():
                        os.chmod(lock_path, 0o666)
            _fcntl.flock(fh.fileno(), _fcntl.LOCK_EX)
            return fh
        except OSError as exc:
            last_err = exc
            if fh is not None:
                with contextlib.suppress(OSError):
                    fh.close()
            if attempt + 1 < max(1, int(retries)):
                time.sleep(backoff_sec * (attempt + 1))
    assert last_err is not None
    raise last_err


def get_cdp_leases_path(cdp_port: int = 9222) -> Path:
    """
    Returns the canonical cross-process CDP tab lease registry path
    (`/tmp/aab_locks/aab_cdp_leases_<cdp_port>.json`), respecting `AAB_CDP_LEASES_PATH`
    (explicit file override) or `AAB_LOCKS_DIR` (hermetic tests).
    """
    explicit = os.environ.get("AAB_CDP_LEASES_PATH", "").strip()
    if explicit:
        p = Path(explicit)
        p.parent.mkdir(parents=True, exist_ok=True)
        return p
    locks_dir = get_aab_locks_dir()
    return locks_dir / f"aab_cdp_leases_{int(cdp_port)}.json"


def _lease_paths(cdp_port: int = 9222) -> tuple[Path, Path]:
    locks_dir = get_aab_locks_dir()
    json_path = get_cdp_leases_path(cdp_port=cdp_port)
    return (
        locks_dir / f"aab_cdp_leases_{int(cdp_port)}.lock",
        json_path,
    )


def make_lease_owner_id(process_tag: str = "worker", *, pid: int | None = None) -> str:
    """Generates a unique per-worker/per-shard lease owner token."""
    eff_pid = int(os.getpid() if pid is None else pid)
    clean_tag = "".join(ch if (ch.isalnum() or ch in ("_", "-", ":")) else "_" for ch in str(process_tag or "worker"))[:48]
    return f"pid:{eff_pid}:{clean_tag}:{uuid.uuid4().hex[:8]}"


def default_process_owner_id(process_tag: str = "default", *, pid: int | None = None) -> str:
    """Deterministic per-PID owner token for single-tab callers within the same process."""
    eff_pid = int(os.getpid() if pid is None else pid)
    clean_tag = "".join(ch if (ch.isalnum() or ch in ("_", "-", ":")) else "_" for ch in str(process_tag or "default"))[:48]
    return f"pid:{eff_pid}:{clean_tag}"


def _read_proc_start_ticks(pid: int) -> int | None:
    """Reads Linux `/proc/<pid>/stat` field 22 (`starttime` clock ticks) to guard against OS PID reuse."""
    p = int(pid or 0)
    if p <= 0:
        return None
    proc_stat = Path(f"/proc/{p}/stat")
    if not proc_stat.exists():
        return None
    with contextlib.suppress(OSError, ValueError):
        raw = proc_stat.read_text(encoding="utf-8", errors="ignore")
        rparen = raw.rfind(")")
        if rparen > 0:
            rest = raw[rparen + 1 :].strip().split()
            if len(rest) > 19:
                return int(rest[19])
    return None


def is_pid_alive(pid: int) -> bool:
    """Returns True iff OS process `pid` exists and is not a Linux zombie ('Z')."""
    p = int(pid or 0)
    if p <= 0:
        return False
    if p == os.getpid():
        return True
    try:
        os.kill(p, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        pass
    except OSError:
        return False

    proc_stat = Path(f"/proc/{p}/stat")
    if proc_stat.exists():
        with contextlib.suppress(OSError):
            raw = proc_stat.read_text(encoding="utf-8", errors="ignore")
            rparen = raw.rfind(")")
            if rparen > 0:
                rest = raw[rparen + 1 :].strip().split()
                if rest and rest[0].upper() == "Z":
                    return False
    return True


@contextlib.contextmanager
def _locked_lease_registry(cdp_port: int = 9222) -> Iterator[tuple[dict[str, Any], Path]]:
    lock_path, json_path = _lease_paths(cdp_port)
    with _PROC_LOCK:
        fh = acquire_shared_flock(lock_path)
        try:
            state: dict[str, Any] = {"version": 1, "cdp_port": int(cdp_port), "leases": {}}
            if json_path.exists():
                raw_size = 0
                with contextlib.suppress(OSError):
                    raw_size = json_path.stat().st_size
                if raw_size > 0:
                    loaded: Any = None
                    last_parse_err: Exception | None = None
                    for r_try in range(3):
                        try:
                            txt = json_path.read_text(encoding="utf-8")
                            if not txt.strip():
                                loaded = None
                                break
                            loaded = json.loads(txt)
                            last_parse_err = None
                            break
                        except Exception as exc:  # noqa: BLE001
                            last_parse_err = exc
                            if r_try < 2:
                                time.sleep(0.03 * (r_try + 1))
                    if last_parse_err is not None or (
                        loaded is not None
                        and (not isinstance(loaded, dict) or not isinstance(loaded.get("leases"), dict))
                    ):
                        backup_p = json_path.with_suffix(f".corrupt.{int(time.time())}.json")
                        with contextlib.suppress(OSError):
                            os.replace(json_path, backup_p)
                        raise RuntimeError(
                            f"Corrupt non-empty CDP lease registry {json_path} (backed up to {backup_p}): {last_parse_err}"
                        )
                    if isinstance(loaded, dict) and isinstance(loaded.get("leases"), dict):
                        state = loaded
            yield state, json_path
        finally:
            if fh is not None and _fcntl is not None:
                with contextlib.suppress(OSError):
                    _fcntl.flock(fh.fileno(), _fcntl.LOCK_UN)
            if fh is not None:
                with contextlib.suppress(OSError):
                    fh.close()


def _write_registry_unlocked(state: dict[str, Any], json_path: Path) -> None:
    state["updated_at"] = round(time.time(), 3)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = json_path.parent / f".tmp_{os.getpid()}_{threading.get_ident()}_{time.time_ns()}_{json_path.name}"
    try:
        tmp_path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(tmp_path, json_path)
    except OSError:
        with contextlib.suppress(OSError):
            tmp_path.unlink(missing_ok=True)
        raise


def _prune_dead_leases_unlocked(
    state: dict[str, Any],
    *,
    now: float | None = None,
    live_target_ids: set[str] | None = None,
) -> int:
    cur = float(time.time() if now is None else now)
    leases = state.setdefault("leases", {})
    orphans = state.setdefault("orphan_pipeline_tabs", {})
    if not isinstance(orphans, dict):
        orphans = {}
        state["orphan_pipeline_tabs"] = orphans
    if live_target_ids is not None:
        for otid in list(orphans):
            if otid not in live_target_ids:
                orphans.pop(otid, None)
    evicted: list[tuple[str, dict[str, Any] | None, bool]] = []
    for tid, rec in list(leases.items()):
        if not isinstance(rec, dict):
            evicted.append((tid, None, False))
            continue
        if live_target_ids is not None and tid not in live_target_ids:
            evicted.append((tid, rec, False))
            continue
        pid = int(rec.get("pid") or 0)
        if not is_pid_alive(pid):
            evicted.append((tid, rec, True))
            continue
        recorded_ticks = rec.get("proc_start_ticks")
        if isinstance(recorded_ticks, int) and recorded_ticks > 0:
            cur_ticks = _read_proc_start_ticks(pid)
            if cur_ticks is not None and cur_ticks != recorded_ticks:
                evicted.append((tid, rec, True))
                continue
        hb = float(rec.get("heartbeat_at") or rec.get("acquired_at") or 0.0)
        ttl = max(5.0, float(rec.get("ttl_sec") or DEFAULT_TAB_LEASE_TTL_SEC))
        if (cur - hb) > ttl:
            evicted.append((tid, rec, True))
    for tid, rec, maybe_orphan in evicted:
        leases.pop(tid, None)
        if maybe_orphan and isinstance(rec, dict) and bool(rec.get("created_by_pipeline")):
            orphans[tid] = {
                "target_id": tid,
                "cdp_port": int(rec.get("cdp_port") or 9222),
                "purpose": str(rec.get("purpose") or ""),
                "url": str(rec.get("url") or ""),
                "initial_url": str(rec.get("initial_url") or ""),
                "evicted_at": round(cur, 3),
            }
    if len(orphans) > 64:
        oldest = sorted(
            orphans.items(),
            key=lambda kv: float((kv[1] or {}).get("evicted_at") or 0.0) if isinstance(kv[1], dict) else 0.0,
        )
        for old_tid, _ in oldest[: len(orphans) - 64]:
            orphans.pop(old_tid, None)
    return len(evicted)


def reap_orphan_pipeline_tabs(
    *,
    cdp_port: int = 9222,
    cdp_host: str = "127.0.0.1",
    extra_pipeline_tab_ids: list[str] | tuple[str, ...] | set[str] = (),
    project_id: str | None = None,
    dry_run: bool = False,
    timeout: float = 3.0,
) -> list[str]:
    """
    Safely closes crashed/evicted pipeline-created browser tabs (`created_by_pipeline=True` in
    `orphan_pipeline_tabs` or explicit `extra_pipeline_tab_ids` from a project's `flow_provenance_receipt.json`
    that are no longer actively leased and point to a Flow/blank URL). Never touches personal user tabs.
    """
    candidates_from_registry: set[str] = set()
    extra_unleased: set[str] = set()
    pid_filter = str(project_id or "").strip()

    with _locked_lease_registry(cdp_port) as (state, json_path):
        removed = _prune_dead_leases_unlocked(state)
        leases = state.get("leases", {})
        orphans = state.get("orphan_pipeline_tabs", {})
        if isinstance(orphans, dict):
            for tid, rec in list(orphans.items()):
                if tid in leases or not isinstance(rec, dict):
                    continue
                if int(rec.get("cdp_port") or cdp_port) != int(cdp_port):
                    continue
                if pid_filter:
                    meta_blob = f"{rec.get('purpose') or ''} {rec.get('url') or ''}"
                    if pid_filter not in meta_blob and rec.get("purpose"):
                        continue
                candidates_from_registry.add(str(tid))
        for raw_tid in (extra_pipeline_tab_ids or ()):
            s_tid = str(raw_tid or "").strip()
            if s_tid and s_tid not in leases:
                extra_unleased.add(s_tid)
        if removed > 0:
            _write_registry_unlocked(state, json_path)

    all_candidates = candidates_from_registry | extra_unleased
    if not all_candidates:
        return []

    try:
        with urllib.request.urlopen(f"http://{cdp_host}:{int(cdp_port)}/json/list", timeout=timeout) as resp:
            tabs = json.loads(resp.read().decode("utf-8"))
    except Exception:
        tabs = []

    live_pages_by_id: dict[str, dict[str, Any]] = {}
    for t in (tabs or []):
        if isinstance(t, dict) and t.get("type") == "page" and t.get("id"):
            live_pages_by_id[str(t["id"])] = t

    closed: list[str] = []
    vanished: set[str] = {tid for tid in candidates_from_registry if tid not in live_pages_by_id}
    for tid in sorted(all_candidates):
        page = live_pages_by_id.get(tid)
        if page is None:
            continue
        url_l = str(page.get("url") or "").strip().lower()
        title_s = str(page.get("title") or "").strip()
        if tid not in candidates_from_registry:
            is_pipeline_flow_page = (
                url_l in ("", "about:blank")
                or "flow.google.com/project/" in url_l
                or "/fx/tools/flow/project/" in url_l
            ) and (not title_s or "AAB_" in title_s or (pid_filter and pid_filter in title_s) or "Google Flow" in title_s)
            if not is_pipeline_flow_page:
                continue
        if dry_run:
            closed.append(tid)
            continue
        try:
            with urllib.request.urlopen(f"http://{cdp_host}:{int(cdp_port)}/json/close/{tid}", timeout=timeout):
                pass
            closed.append(tid)
        except Exception:
            pass

    if not dry_run and (closed or vanished):
        with _locked_lease_registry(cdp_port) as (state, json_path):
            orphans = state.get("orphan_pipeline_tabs")
            if isinstance(orphans, dict):
                changed = False
                for tid in (*closed, *vanished):
                    if tid in orphans:
                        orphans.pop(tid, None)
                        changed = True
                if changed:
                    _write_registry_unlocked(state, json_path)
        if closed:
            time.sleep(0.25)
    return closed


def prune_dead_leases(
    *,
    cdp_port: int = 9222,
    live_target_ids: set[str] | None = None,
    close_orphan_tabs: bool = False,
) -> int:
    """Evicts dead-PID, recycled-PID, expired-TTL, and vanished-target leases from the registry."""
    with _locked_lease_registry(cdp_port) as (state, json_path):
        removed = _prune_dead_leases_unlocked(state, live_target_ids=live_target_ids)
        if removed > 0:
            _write_registry_unlocked(state, json_path)
    if close_orphan_tabs:
        reap_orphan_pipeline_tabs(cdp_port=cdp_port)
    return removed


def acquire_tab_lease(
    target_id: str,
    *,
    owner_id: str | None = None,
    purpose: str = "",
    cdp_port: int = 9222,
    ttl_sec: float = DEFAULT_TAB_LEASE_TTL_SEC,
    created_by_pipeline: bool = False,
    initial_url: str = "",
    url: str = "",
    pid_override: int | None = None,
) -> dict[str, Any]:
    """
    Acquires (or renews if already held by `owner_id`) an exclusive lease on `target_id`.
    Raises `TabLeaseConflictError` if another live `owner_id` holds `target_id`.
    """
    tid = str(target_id or "").strip()
    if not tid:
        raise ValueError("target_id must be non-empty")
    eff_pid = int(os.getpid() if pid_override is None else pid_override)
    eff_owner = str(owner_id or default_process_owner_id(purpose or "default", pid=eff_pid)).strip()
    eff_ttl = max(5.0, float(ttl_sec or DEFAULT_TAB_LEASE_TTL_SEC))
    now = round(time.time(), 3)
    start_ticks = _read_proc_start_ticks(eff_pid) if pid_override is None else None
    eff_init_url = str(initial_url or url or "")
    eff_cur_url = str(url or initial_url or "")

    with _locked_lease_registry(cdp_port) as (state, json_path):
        _prune_dead_leases_unlocked(state, now=now)
        leases = state.setdefault("leases", {})
        existing = leases.get(tid)
        if (
            isinstance(existing, dict)
            and int(existing.get("cdp_port") or cdp_port) == int(cdp_port)
            and existing.get("owner_id") != eff_owner
        ):
            raise TabLeaseConflictError(
                f"CDP tab {tid} is already leased by live owner={existing.get('owner_id')!r} "
                f"(pid={existing.get('pid')}, purpose={existing.get('purpose')!r})"
            )

        prev_ticks = (existing or {}).get("proc_start_ticks") if isinstance(existing, dict) else None
        rec: dict[str, Any] = {
            "target_id": tid,
            "owner_id": eff_owner,
            "pid": eff_pid,
            "cdp_port": int(cdp_port),
            "purpose": str(purpose or (existing or {}).get("purpose") or ""),
            "initial_url": str((existing or {}).get("initial_url") or eff_init_url),
            "url": str(eff_cur_url or (existing or {}).get("url") or (existing or {}).get("initial_url") or ""),
            "created_by_pipeline": bool(
                created_by_pipeline or (isinstance(existing, dict) and existing.get("created_by_pipeline"))
            ),
            "acquired_at": float((existing or {}).get("acquired_at") or now),
            "heartbeat_at": now,
            "ttl_sec": eff_ttl,
        }
        if start_ticks is not None:
            rec["proc_start_ticks"] = start_ticks
        elif isinstance(prev_ticks, int) and prev_ticks > 0:
            rec["proc_start_ticks"] = prev_ticks
        leases[tid] = rec
        orphans = state.get("orphan_pipeline_tabs")
        if isinstance(orphans, dict):
            orphans.pop(tid, None)
        _write_registry_unlocked(state, json_path)
        return dict(rec)


def try_acquire_tab_lease(
    target_id: str,
    *,
    owner_id: str | None = None,
    purpose: str = "",
    cdp_port: int = 9222,
    ttl_sec: float = DEFAULT_TAB_LEASE_TTL_SEC,
    created_by_pipeline: bool = False,
    initial_url: str = "",
    url: str = "",
    pid_override: int | None = None,
) -> dict[str, Any] | None:
    """Non-raising variant of `acquire_tab_lease`; returns `None` on conflict."""
    try:
        return acquire_tab_lease(
            target_id,
            owner_id=owner_id,
            purpose=purpose,
            cdp_port=cdp_port,
            ttl_sec=ttl_sec,
            created_by_pipeline=created_by_pipeline,
            initial_url=initial_url,
            url=url,
            pid_override=pid_override,
        )
    except TabLeaseConflictError:
        return None


def renew_tab_lease(
    target_id: str,
    *,
    owner_id: str | None = None,
    cdp_port: int = 9222,
    ttl_sec: float | None = None,
    url: str | None = None,
) -> bool:
    """Refreshes `heartbeat_at` (and optional `url`) on `target_id` if still owned by `owner_id`."""
    tid = str(target_id or "").strip()
    if not tid:
        return False
    now = round(time.time(), 3)
    with _locked_lease_registry(cdp_port) as (state, json_path):
        _prune_dead_leases_unlocked(state, now=now)
        rec = state.get("leases", {}).get(tid)
        if not isinstance(rec, dict):
            return False
        if int(rec.get("cdp_port") or cdp_port) != int(cdp_port):
            return False
        if owner_id is not None and rec.get("owner_id") != owner_id:
            return False
        if owner_id is None and int(rec.get("pid") or 0) != os.getpid():
            return False
        rec["heartbeat_at"] = now
        if ttl_sec is not None:
            rec["ttl_sec"] = max(5.0, float(ttl_sec))
        if url:
            rec["url"] = str(url)
        _write_registry_unlocked(state, json_path)
        return True


def get_tab_lease(target_id: str, *, cdp_port: int = 9222) -> dict[str, Any] | None:
    tid = str(target_id or "").strip()
    if not tid:
        return None
    with _locked_lease_registry(cdp_port) as (state, json_path):
        removed = _prune_dead_leases_unlocked(state)
        if removed > 0:
            _write_registry_unlocked(state, json_path)
        rec = state.get("leases", {}).get(tid)
        if not isinstance(rec, dict):
            return None
        if int(rec.get("cdp_port") or cdp_port) != int(cdp_port):
            return None
        return dict(rec)


def list_active_tab_leases(
    *,
    cdp_port: int = 9222,
    live_target_ids: set[str] | None = None,
) -> dict[str, dict[str, Any]]:
    with _locked_lease_registry(cdp_port) as (state, json_path):
        removed = _prune_dead_leases_unlocked(state, live_target_ids=live_target_ids)
        if removed > 0:
            _write_registry_unlocked(state, json_path)
        return {
            str(k): dict(v)
            for k, v in (state.get("leases") or {}).items()
            if isinstance(v, dict) and int(v.get("cdp_port") or cdp_port) == int(cdp_port)
        }


def is_tab_leased_by_other(
    target_id: str,
    *,
    owner_id: str | None = None,
    cdp_port: int = 9222,
) -> bool:
    """
    Returns True if `target_id` is actively leased by another live owner.
    When `owner_id` is omitted, checks whether the lease belongs to a different live OS PID.
    """
    rec = get_tab_lease(target_id, cdp_port=cdp_port)
    if rec is None:
        return False
    if owner_id is not None:
        return str(rec.get("owner_id") or "") != str(owner_id)
    return int(rec.get("pid") or 0) != os.getpid()


def release_tab_lease(
    target_id: str,
    *,
    owner_id: str | None = None,
    cdp_port: int = 9222,
) -> bool:
    """Releases a lease record without closing the browser tab."""
    tid = str(target_id or "").strip()
    if not tid:
        return False
    with _locked_lease_registry(cdp_port) as (state, json_path):
        _prune_dead_leases_unlocked(state)
        leases = state.get("leases", {})
        rec = leases.get(tid)
        if not isinstance(rec, dict):
            return False
        if int(rec.get("cdp_port") or cdp_port) != int(cdp_port):
            return False
        if owner_id is not None and rec.get("owner_id") != owner_id:
            return False
        if owner_id is None and int(rec.get("pid") or 0) != os.getpid():
            return False
        leases.pop(tid, None)
        _write_registry_unlocked(state, json_path)
        return True


def release_and_close_leased_tab(
    target_id: str | None,
    *,
    owner_id: str | None = None,
    cdp_port: int = 9222,
    cdp_host: str = "127.0.0.1",
    timeout: float = 5.0,
) -> bool:
    """
    Atomically verifies ownership + `created_by_pipeline == True`, releases the lease,
    and closes `target_id` over CDP HTTP.
    Refuses (returns False) to close:
      - any unleased tab (protecting all pre-existing user personal tabs),
      - any tab with `created_by_pipeline == False`, or
      - any tab leased by a different live `owner_id` or live OS PID.
    """
    tid = str(target_id or "").strip()
    if not tid:
        return False

    can_close = False
    with _locked_lease_registry(cdp_port) as (state, json_path):
        _prune_dead_leases_unlocked(state)
        leases = state.get("leases", {})
        rec = leases.get(tid)
        if not isinstance(rec, dict):
            return False
        if int(rec.get("cdp_port") or cdp_port) != int(cdp_port):
            return False
        if owner_id is not None and rec.get("owner_id") != owner_id:
            return False
        if owner_id is None and int(rec.get("pid") or 0) != os.getpid():
            return False
        can_close = bool(rec.get("created_by_pipeline", False))
        leases.pop(tid, None)
        _write_registry_unlocked(state, json_path)

    if not can_close:
        return False

    try:
        with urllib.request.urlopen(f"http://{cdp_host}:{int(cdp_port)}/json/close/{tid}", timeout=timeout):
            pass
        return True
    except Exception:
        return False


async def enable_background_focus_emulation(client: Any) -> bool:
    """
    Enables CDP `Emulation.setFocusEmulationEnabled({enabled: True})` on a page session
    so `document.hasFocus()` and Angular/Polymer focus handlers work in background tabs
    without ever calling `Page.bringToFront` or stealing user window focus.
    """
    if client is None or not hasattr(client, "send"):
        return False
    try:
        sig = inspect.signature(client.send)
        accepts_timeout = "timeout_sec" in sig.parameters or any(
            p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()
        )
        if accepts_timeout:
            await client.send("Emulation.setFocusEmulationEnabled", {"enabled": True}, timeout_sec=5.0)
        else:
            await client.send("Emulation.setFocusEmulationEnabled", {"enabled": True})
        return True
    except Exception:
        return False


def _run_coro_sync(coro: Any) -> Any:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    box: list[Any] = []
    err: list[BaseException] = []

    def _worker() -> None:
        try:
            box.append(asyncio.run(coro))
        except BaseException as exc:  # noqa: BLE001
            err.append(exc)

    th = threading.Thread(target=_worker, daemon=True)
    th.start()
    th.join()
    if err:
        raise err[0]
    return box[0]


def _create_target_via_browser_ws(
    target_url: str,
    *,
    cdp_host: str = "127.0.0.1",
    cdp_port: int = 9222,
    background: bool = True,
    timeout: float = 8.0,
) -> dict[str, Any] | None:
    """
    Creates a new page target via browser-level CDP `Target.createTarget` with `background=True`
    so the visible browser window never switches away from the user's active tab.
    Returns `None` if browser-level WebSocket metadata is unavailable (allowing `/json/new` fallback).
    """
    try:
        with urllib.request.urlopen(
            f"http://{cdp_host}:{int(cdp_port)}/json/version",
            timeout=min(4.0, float(timeout)),
        ) as v_resp:
            ver_doc = json.loads(v_resp.read().decode("utf-8"))
        browser_ws = str((ver_doc or {}).get("webSocketDebuggerUrl") or "").strip()
        if not browser_ws:
            return None
    except Exception:
        return None

    async def _send_create() -> str:
        import websockets

        async with websockets.connect(
            browser_ws,
            max_size=4_000_000,
            ping_interval=None,
            open_timeout=min(5.0, float(timeout)),
        ) as ws:
            payload = {
                "id": 1,
                "method": "Target.createTarget",
                "params": {"url": str(target_url), "background": bool(background)},
            }
            await asyncio.wait_for(ws.send(json.dumps(payload)), timeout=min(5.0, float(timeout)))
            deadline = time.monotonic() + min(6.0, float(timeout))
            while True:
                rem = deadline - time.monotonic()
                if rem <= 0:
                    raise TimeoutError("Target.createTarget timed out")
                raw = await asyncio.wait_for(ws.recv(), timeout=rem)
                msg = json.loads(raw)
                if msg.get("id") == 1:
                    if "error" in msg:
                        raise RuntimeError(f"Target.createTarget error: {msg['error']}")
                    return str((msg.get("result") or {}).get("targetId") or "").strip()

    try:
        tid = _run_coro_sync(_send_create())
    except Exception:
        return None
    if not tid:
        return None

    # Resolve page WebSocket URL from /json/list (or construct canonical page WS endpoint)
    try:
        with urllib.request.urlopen(
            f"http://{cdp_host}:{int(cdp_port)}/json/list",
            timeout=min(4.0, float(timeout)),
        ) as l_resp:
            tabs = json.loads(l_resp.read().decode("utf-8"))
        if isinstance(tabs, list):
            for t in tabs:
                if isinstance(t, dict) and str(t.get("id") or "") == tid:
                    out_t = dict(t)
                    out_t.setdefault("webSocketDebuggerUrl", f"ws://{cdp_host}:{int(cdp_port)}/devtools/page/{tid}")
                    out_t["background"] = bool(background)
                    return out_t
    except Exception:
        pass

    return {
        "id": tid,
        "type": "page",
        "url": str(target_url),
        "webSocketDebuggerUrl": f"ws://{cdp_host}:{int(cdp_port)}/devtools/page/{tid}",
        "background": bool(background),
    }


def has_inflight_tab_creations(*, cdp_port: int = 9222, grace_sec: float = 15.0) -> bool:
    """Returns True if any pipeline worker is actively mid-creation of a new CDP tab within `grace_sec`."""
    now = time.time()
    with _locked_lease_registry(cdp_port) as (state, json_path):
        inflight = state.get("inflight_creations")
        if not isinstance(inflight, dict) or not inflight:
            return False
        dirty = False
        active_any = False
        for k, rec in list(inflight.items()):
            if not isinstance(rec, dict):
                inflight.pop(k, None)
                dirty = True
                continue
            exp = float(rec.get("expires_at") or (float(rec.get("started_at") or 0.0) + grace_sec))
            pid_val = int(rec.get("pid") or 0)
            if now > exp or (pid_val > 0 and not is_pid_alive(pid_val)):
                inflight.pop(k, None)
                dirty = True
            else:
                active_any = True
        if dirty:
            _write_registry_unlocked(state, json_path)
        return active_any


def open_leased_cdp_tab(
    target_url: str,
    *,
    owner_id: str | None = None,
    purpose: str = "",
    cdp_port: int = 9222,
    cdp_host: str = "127.0.0.1",
    timeout: float = 10.0,
    ttl_sec: float = DEFAULT_TAB_LEASE_TTL_SEC,
    background: bool = True,
) -> dict[str, Any]:
    """
    Opens a brand-new CDP tab in the background via `Target.createTarget({"url": ..., "background": True})`
    (falling back to `PUT /json/new?<encoded_url>` only when browser-level WS is unavailable) and
    immediately registers a `created_by_pipeline=True` lease in the port-scoped lease registry.
    Closes the newly created target immediately on any lease acquisition failure so zero tabs leak.
    """
    eff_owner = str(owner_id or make_lease_owner_id(purpose or "cdp_tab")).strip()
    creation_token = f"{os.getpid()}:{uuid.uuid4().hex[:10]}"
    now_start = time.time()
    with _locked_lease_registry(cdp_port) as (state, json_path):
        inflight = state.setdefault("inflight_creations", {})
        if not isinstance(inflight, dict):
            inflight = {}
            state["inflight_creations"] = inflight
        inflight[creation_token] = {
            "owner_id": eff_owner,
            "pid": os.getpid(),
            "target_url": str(target_url),
            "started_at": round(now_start, 3),
            "expires_at": round(now_start + max(15.0, float(timeout) + 5.0), 3),
        }
        _write_registry_unlocked(state, json_path)

    tid = ""
    try:
        target = _create_target_via_browser_ws(
            target_url,
            cdp_host=cdp_host,
            cdp_port=cdp_port,
            background=background,
            timeout=timeout,
        )
        if target is None:
            encoded_url = urllib.parse.quote(str(target_url), safe="")
            req = urllib.request.Request(f"http://{cdp_host}:{int(cdp_port)}/json/new?{encoded_url}", method="PUT")
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                target = json.loads(resp.read().decode("utf-8"))
        tid = str(target.get("id") or "").strip()
        if not tid:
            raise RuntimeError(f"CDP tab creation did not return a target id for {target_url!r}: {target}")
        try:
            lease = acquire_tab_lease(
                tid,
                owner_id=eff_owner,
                purpose=purpose or f"open:{target_url[:48]}",
                cdp_port=cdp_port,
                ttl_sec=ttl_sec,
                created_by_pipeline=True,
                initial_url=target_url,
            )
        except BaseException:
            with contextlib.suppress(Exception):
                with urllib.request.urlopen(
                    f"http://{cdp_host}:{int(cdp_port)}/json/close/{tid}",
                    timeout=min(4.0, float(timeout)),
                ):
                    pass
            raise
        out = dict(target)
        out["lease_owner_id"] = lease["owner_id"]
        out.setdefault("background", bool(background))
        return out
    finally:
        with contextlib.suppress(Exception):
            with _locked_lease_registry(cdp_port) as (state, json_path):
                inflight = state.get("inflight_creations")
                if isinstance(inflight, dict) and creation_token in inflight:
                    inflight.pop(creation_token, None)
                    _write_registry_unlocked(state, json_path)


@contextlib.asynccontextmanager
async def leased_cdp_tab(
    target_url: str,
    *,
    owner_id: str | None = None,
    purpose: str = "",
    cdp_port: int = 9222,
    cdp_host: str = "127.0.0.1",
    ttl_sec: float = DEFAULT_TAB_LEASE_TTL_SEC,
    background: bool = True,
) -> AsyncIterator[tuple[Any, str, str]]:
    """
    Async context manager that opens a dedicated background-leased CDP tab, enables
    `Emulation.setFocusEmulationEnabled({enabled: True})`, maintains a background
    heartbeat, yields `(DirectCDPClient, target_id, lease_owner_id)`, and guarantees
    safe `release_and_close_leased_tab` cleanup on exit.
    """
    from pipeline.studio.browser_session import DirectCDPClient

    eff_owner = str(owner_id or make_lease_owner_id(purpose or "leased_tab")).strip()
    target = await asyncio.to_thread(
        open_leased_cdp_tab,
        target_url,
        owner_id=eff_owner,
        purpose=purpose,
        cdp_port=cdp_port,
        cdp_host=cdp_host,
        ttl_sec=ttl_sec,
        background=background,
    )
    tid = str(target["id"])
    ws_url = str(target.get("webSocketDebuggerUrl") or "")
    if not ws_url:
        await asyncio.to_thread(
            release_and_close_leased_tab,
            tid,
            owner_id=eff_owner,
            cdp_port=cdp_port,
            cdp_host=cdp_host,
        )
        raise RuntimeError(f"Leased tab {tid} missing webSocketDebuggerUrl")

    hb_interval = max(5.0, min(30.0, float(ttl_sec) / 3.0))

    async def _heartbeat_loop() -> None:
        while True:
            await asyncio.sleep(hb_interval)
            await asyncio.to_thread(renew_tab_lease, tid, owner_id=eff_owner, cdp_port=cdp_port)

    hb_task = asyncio.create_task(_heartbeat_loop())
    try:
        async with DirectCDPClient(ws_url) as client:
            await enable_background_focus_emulation(client)
            yield client, tid, eff_owner
    finally:
        hb_task.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await hb_task
        await asyncio.to_thread(
            release_and_close_leased_tab,
            tid,
            owner_id=eff_owner,
            cdp_port=cdp_port,
            cdp_host=cdp_host,
        )
