"""
ALL ABOUT BRAIN — Google Flow Workspace Lifecycle, Deterministic Room Naming,
and Monthly/Daily Credit Refill Auto-Tier Coordinator
=============================================================================
Normalizes all Google Flow (`https://flow.google.com/`) browser rooms and credit
telemetry across single-tab, sharded-Short, reference-anchor, and Longform workers:

  1. Deterministic Room Naming (`AAB__<project_id>__<role>[_sN][_wM]`):
     Replaces anonymous timestamp room titles (`Nov 05 - 02:19`) via Angular-compatible
     native `.editable-text-input` setter + `InputEvent` / `Enter` / `blur` dispatch.
  2. Monthly & Daily Credit Refill Auto-Tier (`Omni 1.2 Flash` -> `0-credit` `Veo 3.1 - Lite`):
     Persists live `.header-user-button` credit probes (`flow_credit_state.json`),
     automatically resets credit-exhaustion flags on monthly cycle rollover (`YYYY-MM`
     or `Resets on ...`), daily `+50` top-up rollover (`YYYY-MM-DD`), or periodic TTL,
     and coordinates atomic per-clip credit reservations across parallel shards via
     `SharedOmniCreditBudget` so shards never overshoot remaining credits.
  3. Workspace & Local Temp Auto-Cleanup (`clean_flow_workspace` / `main.py flow-clean`):
     Deletes completed Flow project rooms via trusted CDP mouse clicks across paginated
     reloads while protecting rooms actively leased by live sibling workers, and purges
     pipeline-owned `/tmp` & `flow_bridge` staging files without touching user files.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import re
import shutil
import tempfile
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import fcntl as _fcntl
except ImportError:  # pragma: no cover - Windows fallback
    _fcntl = None  # type: ignore[assignment]

from pipeline.cdp_tab_lease import (
    get_aab_locks_dir,
    leased_cdp_tab,
    list_active_tab_leases,
    reap_orphan_pipeline_tabs,
)
from pipeline.config import (
    CHANNEL_ROOT,
    FLOW_OMNI_CREDIT_COST_NO_REF,
    FLOW_OMNI_CREDIT_COST_WITH_REF,
    FLOW_UI_CAPABILITIES_CACHE_FILE,
)

FLOW_ROOM_PREFIX = "AAB_"
FLOW_CREDIT_REPROBE_TTL_SEC = 1800.0

_CREDIT_LOCK = threading.RLock()
_UUID_RE = re.compile(r"([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})")
_ROOM_NAME_RE = re.compile(
    r"^AAB__?(?P<project_id>[A-Za-z0-9_.-]+?)(?:__(?P<role>[A-Za-z0-9_-]+?)(?:_s(?P<shard>\d+))?(?:_w(?P<wave>\d+))?)?$"
)
_CREDITS_COUNT_RE = re.compile(r"(\d[\d,]*)\s+(?:Google\s+Flow|AI|Flow)\s+credits", re.IGNORECASE)
_RESETS_ON_RE = re.compile(r"Resets\s+on\s+([^\r\n]+)", re.IGNORECASE)
_MONTH_MAP = {
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}


def _sanitize_token(raw: str, fallback: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(raw or "").strip()).strip("_")
    return cleaned[:80] if cleaned else fallback


def format_flow_room_name(
    project_id: str,
    role: str = "clips",
    shard_idx: int | None = None,
    wave_idx: int | None = None,
) -> str:
    """
    Builds a canonical Google Flow room title starting with `AAB_<project_id>`:
      - Primary single-room episode: `AAB_<project_id>`
      - Sharded / auxiliary role room: `AAB_<project_id>__<role>[_sN][_wM]`
    """
    pid = _sanitize_token(project_id, "ephemeral")
    raw_role = str(role or "").strip()
    has_shard = shard_idx is not None and int(shard_idx) > 0
    has_wave = wave_idx is not None and int(wave_idx) > 0
    if raw_role in ("", "main", "episode") or (raw_role == "clips" and not has_shard and not has_wave):
        return f"{FLOW_ROOM_PREFIX}{pid}"
    r_tok = re.sub(r"[^A-Za-z0-9-]+", "-", raw_role).strip("-") or "clips"
    suffix = r_tok
    if has_shard:
        suffix += f"_s{int(shard_idx)}"  # type: ignore[arg-type]
    if has_wave:
        suffix += f"_w{int(wave_idx)}"  # type: ignore[arg-type]
    return f"{FLOW_ROOM_PREFIX}{pid}__{suffix}"


def parse_flow_room_name(title: str) -> dict[str, Any] | None:
    """Parses a deterministic `AAB_<project_id>[__<role>[_sN][_wM]]` (or legacy `AAB__...`) room title."""
    raw = str(title or "").strip()
    m = _ROOM_NAME_RE.match(raw)
    if not m:
        return None
    shard_s = m.group("shard")
    wave_s = m.group("wave")
    return {
        "prefix": "AAB",
        "project_id": m.group("project_id"),
        "role": m.group("role") or "clips",
        "shard_idx": int(shard_s) if shard_s is not None else None,
        "wave_idx": int(wave_s) if wave_s is not None else None,
        "raw_title": raw,
    }


def extract_flow_project_uuid(url_or_id: str) -> str:
    """Extracts the lowercase Flow project UUID from `/project/<uuid>` or raw UUID string."""
    m = _UUID_RE.search(str(url_or_id or ""))
    return m.group(1).lower() if m else ""


async def rename_active_flow_project(client: Any, room_name: str) -> bool:
    """
    Sets the active `/project/<uuid>` title input (`.editable-text-input`) using the native
    `HTMLInputElement` value setter so Angular's reactive form persists the room title cleanly.
    """
    clean_name = str(room_name or "").strip()
    if not clean_name:
        return False
    try:
        res = await client.eval(
            f"""(() => {{
                const input = document.querySelector('.editable-text-input');
                if (!input) return false;
                const target = {json.dumps(clean_name)};
                if ((input.value || '').trim() === target) return true;
                const proto = Object.getPrototypeOf(input);
                const desc = Object.getOwnPropertyDescriptor(proto, 'value')
                    || Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value');
                input.focus();
                if (desc && typeof desc.set === 'function') {{
                    desc.set.call(input, target);
                }} else {{
                    input.value = target;
                }}
                input.dispatchEvent(new InputEvent('input', {{ bubbles: true, cancelable: true, data: target }}));
                input.dispatchEvent(new Event('change', {{ bubbles: true }}));
                input.dispatchEvent(new KeyboardEvent('keydown', {{ key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true }}));
                input.dispatchEvent(new KeyboardEvent('keyup', {{ key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true }}));
                input.blur();
                return (input.value || '').trim() === target;
            }})()"""
        )
        return bool(res)
    except Exception:
        return False


# ==============================================================================
# Monthly & Daily Credit Refill State + Shared Shard Budget
# ==============================================================================


def get_flow_credit_state_path() -> Path:
    override = os.environ.get("AAB_FLOW_CREDIT_STATE_PATH", "").strip()
    if override:
        return Path(override)
    return CHANNEL_ROOT / ".cache" / "flow_credit_state.json"


@contextlib.contextmanager
def _locked_credit_state():
    state_path = get_flow_credit_state_path()
    lock_path = get_aab_locks_dir() / "flow_credit_state.lock"
    with _CREDIT_LOCK:
        fh = None
        locked = False
        try:
            if _fcntl is not None:
                try:
                    fh = open(lock_path, "a+", encoding="utf-8")
                    _fcntl.flock(fh.fileno(), _fcntl.LOCK_EX)
                    locked = True
                except OSError:
                    if fh is not None:
                        with contextlib.suppress(OSError):
                            fh.close()
                        fh = None
            doc: dict[str, Any] = {"version": 1}
            if state_path.exists():
                with contextlib.suppress(Exception):
                    loaded = json.loads(state_path.read_text(encoding="utf-8"))
                    if isinstance(loaded, dict):
                        doc = loaded
            yield doc, state_path
        finally:
            if locked and fh is not None and _fcntl is not None:
                with contextlib.suppress(OSError):
                    _fcntl.flock(fh.fileno(), _fcntl.LOCK_UN)
            if fh is not None:
                with contextlib.suppress(OSError):
                    fh.close()


def _write_credit_state_unlocked(doc: dict[str, Any], state_path: Path) -> None:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_p = state_path.parent / f".tmp_{os.getpid()}_{threading.get_ident()}_{time.time_ns()}_{state_path.name}"
    payload = json.dumps(doc, indent=2, sort_keys=True) + "\n"
    try:
        tmp_p.write_text(payload, encoding="utf-8")
        os.replace(tmp_p, state_path)
    except OSError:
        with contextlib.suppress(OSError):
            tmp_p.unlink(missing_ok=True)
        with contextlib.suppress(OSError):
            state_path.write_text(payload, encoding="utf-8")


def load_flow_credit_state() -> dict[str, Any]:
    with _locked_credit_state() as (doc, _):
        return dict(doc)


def parse_flow_credits_overlay_text(text: str, *, now_dt: datetime | None = None) -> dict[str, Any]:
    """
    Parses `.header-user-button` account menu text such as:
      `52 Google Flow credits\\nResets on 17 Nov at 00:03`
    into `credits_remaining`, `resets_on_label`, and `resets_on_iso`.
    """
    blob = str(text or "")
    ref_dt = now_dt or datetime.now(timezone.utc)
    credits_val: int | None = None
    m_c = _CREDITS_COUNT_RE.search(blob)
    if m_c:
        with contextlib.suppress(ValueError):
            credits_val = int(m_c.group(1).replace(",", ""))

    resets_label = ""
    resets_iso = ""
    m_r = _RESETS_ON_RE.search(blob)
    if m_r:
        resets_label = m_r.group(1).strip()
        # Formats seen in Google Flow: "17 Nov at 00:03" or "Nov 17 at 00:03"
        m_dmy = re.search(
            r"(?:(\d{1,2})\s+([A-Za-z]{3,9})|([A-Za-z]{3,9})\s+(\d{1,2}))(?:\s+at\s+(\d{1,2}):(\d{2}))?",
            resets_label,
        )
        if m_dmy:
            day_s = m_dmy.group(1) or m_dmy.group(4)
            mon_s = (m_dmy.group(2) or m_dmy.group(3) or "").lower()
            hh = int(m_dmy.group(5) or 0)
            mm = int(m_dmy.group(6) or 0)
            mon_num = _MONTH_MAP.get(mon_s)
            if day_s and mon_num:
                year = ref_dt.year
                if mon_num < ref_dt.month - 1:
                    year += 1
                with contextlib.suppress(ValueError):
                    dt_parsed = datetime(year, mon_num, int(day_s), hh, mm, tzinfo=timezone.utc)
                    resets_iso = dt_parsed.isoformat()

    return {
        "credits_remaining": credits_val,
        "resets_on_label": resets_label,
        "resets_on_iso": resets_iso,
    }


def record_flow_credit_probe(
    *,
    credits_remaining: int | None,
    resets_on_label: str = "",
    resets_on_iso: str = "",
    min_required_credits: int = FLOW_OMNI_CREDIT_COST_WITH_REF,
    now_ts: float | None = None,
) -> dict[str, Any]:
    cur_ts = float(time.time() if now_ts is None else now_ts)
    dt = datetime.fromtimestamp(cur_ts, tz=timezone.utc)
    with _locked_credit_state() as (doc, state_path):
        doc["last_probed_at_ts"] = round(cur_ts, 3)
        doc["probed_month_ym"] = dt.strftime("%Y-%m")
        doc["probed_day_ymd"] = dt.strftime("%Y-%m-%d")
        if credits_remaining is not None:
            c_int = max(0, int(credits_remaining))
            doc["credits_remaining"] = c_int
            if c_int >= int(min_required_credits):
                doc["exhausted"] = False
                doc["last_reason"] = "live_probe_sufficient_credits"
            else:
                doc["exhausted"] = True
                doc["exhausted_at_ts"] = round(cur_ts, 3)
                doc["exhausted_month_ym"] = dt.strftime("%Y-%m")
                doc["exhausted_day_ymd"] = dt.strftime("%Y-%m-%d")
                doc["last_reason"] = f"live_probe_below_cost({c_int}<{int(min_required_credits)})"
        if resets_on_label:
            doc["resets_on_label"] = str(resets_on_label)
        if resets_on_iso:
            doc["resets_on_iso"] = str(resets_on_iso)
        _write_credit_state_unlocked(doc, state_path)
        return dict(doc)


def record_flow_credit_exhausted(
    *,
    reason: str = "credit_exhausted",
    credits_remaining: int | None = None,
    resets_on_iso: str = "",
    now_ts: float | None = None,
) -> dict[str, Any]:
    cur_ts = float(time.time() if now_ts is None else now_ts)
    dt = datetime.fromtimestamp(cur_ts, tz=timezone.utc)
    with _locked_credit_state() as (doc, state_path):
        doc["exhausted"] = True
        doc["exhausted_at_ts"] = round(cur_ts, 3)
        doc["exhausted_month_ym"] = dt.strftime("%Y-%m")
        doc["exhausted_day_ymd"] = dt.strftime("%Y-%m-%d")
        doc["last_reason"] = str(reason or "credit_exhausted")
        if credits_remaining is not None:
            doc["credits_remaining"] = max(0, int(credits_remaining))
        elif isinstance(doc.get("credits_remaining"), int) and int(doc["credits_remaining"]) >= FLOW_OMNI_CREDIT_COST_NO_REF:
            doc["credits_remaining"] = 0
        if resets_on_iso:
            doc["resets_on_iso"] = str(resets_on_iso)
        _write_credit_state_unlocked(doc, state_path)
        return dict(doc)


def should_reprobe_primary_omni(
    state: dict[str, Any] | None = None,
    *,
    min_required_credits: int = FLOW_OMNI_CREDIT_COST_WITH_REF,
    now_ts: float | None = None,
    reprobe_ttl_sec: float = FLOW_CREDIT_REPROBE_TTL_SEC,
) -> tuple[bool, str]:
    """
    Determines whether `engine='auto'` should attempt `Omni 1.2 Flash` (and probe live credits)
    rather than starting immediately on `0-credit` `Veo 3.1 - Lite [Lower Priority]`.
    Automatically re-enables `Omni 1.2 Flash` on:
      - Monthly billing cycle rollover (`YYYY-MM` changed)
      - Scheduled `resets_on_iso` timestamp elapsed
      - Daily `+50` AI credit refill rollover (`YYYY-MM-DD` changed)
      - Periodic `reprobe_ttl_sec` window
    """
    doc = dict(state) if isinstance(state, dict) else load_flow_credit_state()
    if not doc or not bool(doc.get("exhausted")):
        return True, "not_exhausted"

    cur_ts = float(time.time() if now_ts is None else now_ts)
    cur_dt = datetime.fromtimestamp(cur_ts, tz=timezone.utc)
    cur_ym = cur_dt.strftime("%Y-%m")
    cur_ymd = cur_dt.strftime("%Y-%m-%d")

    cached_c = doc.get("credits_remaining")
    if isinstance(cached_c, int) and cached_c >= int(min_required_credits):
        return True, "sufficient_cached_credits"

    ex_ym = str(doc.get("exhausted_month_ym") or "")
    if ex_ym and cur_ym != ex_ym:
        return True, "monthly_cycle_rollover"

    ex_ts = float(doc.get("exhausted_at_ts") or 0.0)
    resets_iso = str(doc.get("resets_on_iso") or "").strip()
    if resets_iso:
        with contextlib.suppress(ValueError):
            reset_dt = datetime.fromisoformat(resets_iso)
            if reset_dt.tzinfo is None:
                reset_dt = reset_dt.replace(tzinfo=timezone.utc)
            if cur_ts >= reset_dt.timestamp() and ex_ts < reset_dt.timestamp():
                return True, "scheduled_reset_elapsed"

    ex_ymd = str(doc.get("exhausted_day_ymd") or "")
    if ex_ymd and cur_ymd != ex_ymd:
        return True, "daily_credit_refill_rollover"

    if (cur_ts - ex_ts) >= max(60.0, float(reprobe_ttl_sec)):
        return True, "ttl_reprobe_due"

    return False, "exhausted_within_active_window"


async def probe_flow_account_credits(
    client: Any,
    *,
    min_required_credits: int = FLOW_OMNI_CREDIT_COST_WITH_REF,
) -> dict[str, Any]:
    """
    Opens `.header-user-button` briefly to read exact remaining Google Flow credits + reset date,
    closes the overlay cleanly, persists to `flow_credit_state.json`, and returns the parsed state.
    """
    try:
        has_btn = await client.eval("Boolean(document.querySelector('.header-user-button'))")
        if not has_btn:
            return load_flow_credit_state()
        await client.eval("document.querySelector('.header-user-button')?.click()")
        await asyncio.sleep(0.55)
        overlay_txt = await client.eval(
            "(() => (document.querySelector('.cdk-overlay-container')?.innerText || '').trim())()"
        ) or ""
        await client.eval(
            """(() => {
                const bd = document.querySelector('.cdk-overlay-backdrop');
                if (bd) bd.click();
            })()"""
        )
        for ev_t in ("keyDown", "keyUp"):
            with contextlib.suppress(Exception):
                await client.send(
                    "Input.dispatchKeyEvent",
                    {"type": ev_t, "key": "Escape", "code": "Escape", "windowsVirtualKeyCode": 27},
                )
        parsed = parse_flow_credits_overlay_text(str(overlay_txt))
        if parsed.get("credits_remaining") is not None:
            return record_flow_credit_probe(
                credits_remaining=parsed["credits_remaining"],
                resets_on_label=parsed.get("resets_on_label") or "",
                resets_on_iso=parsed.get("resets_on_iso") or "",
                min_required_credits=min_required_credits,
            )
    except Exception:
        pass
    return load_flow_credit_state()


class SharedOmniCreditBudget:
    """
    Coordinates atomic `Omni 1.2 Flash` credit reservations across concurrent shard workers
    so `N` parallel tabs never simultaneously submit more `Omni 1.2 Flash` clips than the
    account's remaining balance (`24` credits per clip).
    When `credits_remaining` is `None` (unprobed), reservations remain open until live UI
    telemetry or a credit banner reports exhaustion.
    """

    def __init__(self, initial_credits: int | None = None) -> None:
        self._lock = threading.RLock()
        self._remaining: int | None = max(0, int(initial_credits)) if initial_credits is not None else None
        self._reserved_total: int = 0

    @property
    def remaining(self) -> int | None:
        with self._lock:
            return self._remaining

    def update_balance(self, credits_remaining: int | None) -> None:
        if credits_remaining is None:
            return
        with self._lock:
            self._remaining = max(0, int(credits_remaining))

    def mark_exhausted(self) -> None:
        with self._lock:
            self._remaining = 0

    def try_reserve(self, cost: int) -> bool:
        need = max(1, int(cost))
        with self._lock:
            if self._remaining is None:
                return True
            if self._remaining < need:
                return False
            self._remaining -= need
            self._reserved_total += need
            return True

    def refund(self, cost: int) -> None:
        amt = max(0, int(cost))
        if amt <= 0:
            return
        with self._lock:
            if self._remaining is not None:
                self._remaining += amt
            self._reserved_total = max(0, self._reserved_total - amt)


# ==============================================================================
# Trusted CDP Clicks + Google Flow Workspace & Local Temp Cleanup
# ==============================================================================


async def _trusted_mouse_click(client: Any, x: float, y: float) -> None:
    mx, my = round(float(x), 1), round(float(y), 1)
    await client.send("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": mx, "y": my})
    await client.send(
        "Input.dispatchMouseEvent",
        {"type": "mousePressed", "x": mx, "y": my, "button": "left", "clickCount": 1},
    )
    await asyncio.sleep(0.06)
    await client.send(
        "Input.dispatchMouseEvent",
        {"type": "mouseReleased", "x": mx, "y": my, "button": "left", "clickCount": 1},
    )


def _is_pipeline_or_temp_flow_title(title: str) -> bool:
    """Returns True if `title` is an AAB canonical/legacy room or an unrenamed Google Flow temporary project."""
    t = str(title or "").strip()
    if not t:
        return True
    if parse_flow_room_name(t) is not None:
        return True
    low = t.lower()
    if low.startswith(("aab_", "diorama_", "boost_", "lf_", "micro_", "test_", "v2_")) or "_shard" in low:
        return True
    if "untitled" in low or low == "new project":
        return True
    # Google Flow default auto-generated timestamp titles before renaming (e.g. "Nov 05 - 06:12" or "05 Nov - 06:12")
    if re.match(r"^(?:[A-Z][a-z]{2}\s+\d{1,2}|\d{1,2}\s+[A-Z][a-z]{2})\s*[-–—]", t):
        return True
    return False


def _discover_active_leased_flow_uuids(cdp_port: int = 9222, exclude_tab_id: str = "") -> set[str]:
    """
    Finds Flow project UUIDs that must NOT be deleted:
      1. Any Flow project URL recorded in `/tmp/aab_cdp_leases.json` for a live leased tab (`!= exclude_tab_id`).
      2. Any Flow project URL currently open in a live browser page tab (`!= exclude_tab_id`), protecting both
         sibling workers and personal user tabs.
    """
    import urllib.request

    protected: set[str] = set()
    active_leases = list_active_tab_leases(cdp_port=cdp_port)
    for tid, rec in active_leases.items():
        if not tid or tid == exclude_tab_id or not isinstance(rec, dict):
            continue
        for k in ("url", "initial_url"):
            uid = extract_flow_project_uuid(str(rec.get(k) or ""))
            if uid:
                protected.add(uid)

    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{int(cdp_port)}/json/list", timeout=4) as resp:
            tabs = json.loads(resp.read().decode("utf-8"))
    except Exception:
        tabs = []
    for t in tabs:
        if t.get("type") != "page":
            continue
        tid = str(t.get("id") or "")
        if not tid or tid == exclude_tab_id:
            continue
        uid = extract_flow_project_uuid(str(t.get("url") or ""))
        if uid:
            protected.add(uid)
    return protected


def _card_matches_filter(
    card: dict[str, Any],
    *,
    all_projects: bool,
    project_id: str | None,
    target_uuids: set[str],
    prefix: str | None,
) -> bool:
    uid = extract_flow_project_uuid(str(card.get("href") or ""))
    title = str(card.get("title") or "").strip()
    if all_projects:
        return _is_pipeline_or_temp_flow_title(title)
    if uid and uid in target_uuids:
        return True
    if prefix and title.startswith(str(prefix)):
        return True
    if project_id:
        pid = _sanitize_token(project_id, "")
        parsed = parse_flow_room_name(title)
        if parsed and parsed.get("project_id") == pid:
            return True
        if pid and (
            title == pid
            or title == f"{FLOW_ROOM_PREFIX}{pid}"
            or title.startswith(f"{pid}_shard")
            or title.startswith(f"{FLOW_ROOM_PREFIX}{pid}__")
            or title.startswith(f"AAB__{pid}__")
        ):
            return True
    return False


def _entry_age_sec(entry: Path, now_ts: float) -> float:
    try:
        return max(0.0, now_ts - float(entry.stat().st_mtime))
    except OSError:
        return 0.0


def purge_local_flow_temp_files(
    *,
    dry_run: bool = False,
    include_speed_cache: bool = False,
    temp_root: Path | None = None,
    bridge_root: Path | None = None,
    project_id: str | None = None,
    min_age_sec: float | None = None,
    cdp_port: int = 9222,
    force_active: bool = False,
) -> dict[str, Any]:
    """
    Purges pipeline-owned temporary Flow staging artifacts in `/tmp` and
    `~/chrome-profile/flow_bridge` while strictly preserving:
      - `/tmp/aab_cdp_leases.json`, `/tmp/aab_locks`, and unrelated user files;
      - active staging/quarantine/bridge files belonging to live sibling workers when `list_active_tab_leases`
        is non-empty (unless `force_active=True` or file age >= `min_age_sec`).
    """
    t_root = Path(temp_root) if temp_root is not None else Path(tempfile.gettempdir())
    b_root = Path(bridge_root) if bridge_root is not None else (Path.home() / "chrome-profile" / "flow_bridge")

    active_leases: dict[str, dict[str, Any]] = {}
    if not force_active:
        if temp_root is None:
            active_leases = list_active_tab_leases(cdp_port=cdp_port)
        else:
            cand_lease_files = [
                t_root / "aab_locks" / f"aab_cdp_leases_{int(cdp_port)}.json",
                t_root / "aab_locks" / "aab_cdp_leases.json",
                t_root / f"aab_cdp_leases_{int(cdp_port)}.json",
                t_root / "aab_cdp_leases.json",
            ]
            found_cand = next((cf for cf in cand_lease_files if cf.exists()), None)
            if found_cand is not None:
                try:
                    raw_l = json.loads(found_cand.read_text(encoding="utf-8"))
                    if isinstance(raw_l, dict) and isinstance(raw_l.get("leases"), dict):
                        active_leases = {
                            str(k): v for k, v in raw_l["leases"].items() if isinstance(v, dict)
                        }
                except Exception:
                    active_leases = {}
            else:
                active_leases = list_active_tab_leases(cdp_port=cdp_port)

    has_live_siblings = bool(active_leases)
    eff_min_age = (
        float(min_age_sec)
        if min_age_sec is not None
        else (1800.0 if has_live_siblings else 0.0)
    )
    rf_min_age = float(min_age_sec) if min_age_sec is not None else eff_min_age
    now_ts = time.time()
    clean_pid = _sanitize_token(project_id, "") if project_id else ""
    pid_leased_active = bool(
        clean_pid
        and any(
            clean_pid in str(rec.get("purpose") or "") or clean_pid in str(rec.get("owner_id") or "")
            for rec in active_leases.values()
        )
    )

    matched_files: list[str] = []
    matched_dirs: list[str] = []
    protected_names = {
        "aab_cdp_leases.json",
        "aab_cdp_leases.lock",
        f"aab_cdp_leases_{int(cdp_port)}.json",
        f"aab_cdp_leases_{int(cdp_port)}.lock",
        "aab_locks",
        "aab_ffmpeg_bin",
        "aab_studio_report.lock",
    }
    if not include_speed_cache:
        protected_names.add("aab_speed_cache")

    file_prefixes = (
        "fimg_",
        "rf_",
        "lf16x9_",
        "flow_cand_",
        "aab_flow_cand_",
        "aab_preflight_voice_",
        "_aab_bitrate_norm_",
        ".aab_asset_idx_",
        ".aab_manifest_",
        ".aab_kb_",
    )
    dir_names = {"aab_reenact", "aab_reenact_lf", "bci_test_projects"}
    if include_speed_cache:
        dir_names.add("aab_speed_cache")

    if t_root.exists():
        for entry in list(t_root.iterdir()):
            name = entry.name
            if name in protected_names or name.endswith(".lock") or name.startswith("aab_cdp_leases"):
                continue
            try:
                age = _entry_age_sec(entry, now_ts)
                belongs_to_pid = bool(clean_pid and clean_pid in name and not pid_leased_active)
                if entry.is_dir() and not entry.is_symlink():
                    if name in dir_names or name.startswith(("aab_shared_asr_", "aab_ref_")):
                        if eff_min_age > 0.0 and age < eff_min_age and not belongs_to_pid:
                            continue
                        matched_dirs.append(str(entry))
                        if not dry_run:
                            shutil.rmtree(entry, ignore_errors=True)
                elif entry.is_file() or entry.is_symlink():
                    if name.startswith(file_prefixes):
                        req_age = rf_min_age if name.startswith("rf_") else eff_min_age
                        if not force_active and req_age > 0.0 and age < req_age and not belongs_to_pid:
                            continue
                        matched_files.append(str(entry))
                        if not dry_run:
                            entry.unlink(missing_ok=True)
            except OSError:
                continue

    if b_root.exists() and b_root.is_dir():
        for entry in list(b_root.iterdir()):
            name = entry.name
            try:
                age = _entry_age_sec(entry, now_ts)
                is_this_pid_shard = bool(
                    clean_pid
                    and not pid_leased_active
                    and (name == f"shard_{clean_pid}" or name.startswith(f"shard_{clean_pid}_"))
                )
                if entry.is_dir() and not entry.is_symlink() and (name.startswith("shard_") or name == "_staging"):
                    if is_this_pid_shard:
                        pass
                    elif clean_pid and not force_active and eff_min_age <= 0.0 and name.startswith("shard_"):
                        # Scoped per-project cleanup should not wipe another project's shard folder unless stale
                        if age < 1800.0:
                            continue
                    elif eff_min_age > 0.0 and age < eff_min_age:
                        continue
                    matched_dirs.append(str(entry))
                    if not dry_run:
                        shutil.rmtree(entry, ignore_errors=True)
                elif entry.is_file() and (name.startswith(file_prefixes) or name.endswith(".crdownload")):
                    if eff_min_age > 0.0 and age < eff_min_age:
                        continue
                    matched_files.append(str(entry))
                    if not dry_run:
                        entry.unlink(missing_ok=True)
            except OSError:
                continue

    if temp_root is None:
        shm_scratch = Path("/dev/shm/aab_scratch")
        if shm_scratch.is_dir():
            for entry in list(shm_scratch.iterdir()):
                name = entry.name
                try:
                    age = _entry_age_sec(entry, now_ts)
                    if name.startswith(("aab_oflow_", "aab_sim_clip_")):
                        if not force_active and eff_min_age > 0.0 and age < eff_min_age:
                            continue
                        if entry.is_dir() and not entry.is_symlink():
                            matched_dirs.append(str(entry))
                            if not dry_run:
                                shutil.rmtree(entry, ignore_errors=True)
                        else:
                            matched_files.append(str(entry))
                            if not dry_run:
                                entry.unlink(missing_ok=True)
                    elif include_speed_cache and name == "speed_cache" and entry.is_dir() and not entry.is_symlink():
                        if not force_active and eff_min_age > 0.0 and age < eff_min_age:
                            continue
                        matched_dirs.append(str(entry))
                        if not dry_run:
                            shutil.rmtree(entry, ignore_errors=True)
                except OSError:
                    continue

    return {
        "dry_run": bool(dry_run),
        "active_leases_detected": len(active_leases),
        "min_age_applied_sec": eff_min_age,
        "removed_files_count": len(matched_files),
        "removed_dirs_count": len(matched_dirs),
        "sample_files": matched_files[:20],
        "sample_dirs": matched_dirs[:20],
    }


async def _scan_dashboard_cards(client: Any) -> list[dict[str, Any]]:
    cards = await client.eval(
        """(() => Array.from(document.querySelectorAll('flow-project-card')).map((card, idx) => {
            const a = card.querySelector('a[href*="/project/"]');
            const titleEl = card.querySelector('.project-title-text');
            const delBtn = card.querySelector('button[aria-label="Delete project"]');
            const r = delBtn ? delBtn.getBoundingClientRect() : null;
            return {
                idx,
                href: a ? (a.getAttribute('href') || a.href || '') : '',
                title: titleEl ? (titleEl.innerText || '').trim() : (card.innerText || '').trim().split('\\n')[0],
                delX: r && r.width > 0 ? r.x + r.width / 2 : 0,
                delY: r && r.height > 0 ? r.y + r.height / 2 : 0
            };
        }))()"""
    )
    return [c for c in (cards or []) if isinstance(c, dict)]


async def _dismiss_cdk_overlays(client: Any) -> None:
    """Closes any open Angular Material menu/dialog backdrop so subsequent card clicks are never swallowed."""
    with contextlib.suppress(Exception):
        await client.eval(
            """(() => {
                const backdrops = document.querySelectorAll('.cdk-overlay-backdrop');
                for (const bd of backdrops) { try { bd.click(); } catch (e) {} }
            })()"""
        )
    for ev_t in ("keyDown", "keyUp"):
        with contextlib.suppress(Exception):
            await client.send(
                "Input.dispatchKeyEvent",
                {"type": ev_t, "key": "Escape", "code": "Escape", "windowsVirtualKeyCode": 27},
            )
    await asyncio.sleep(0.2)


async def _hydrate_and_scan_dashboard_cards(client: Any, *, navigate: bool = False) -> list[dict[str, Any]]:
    """Waits for Google Flow dashboard readiness, scrolls to hydrate lazy cards, and scans `flow-project-card`."""
    if navigate:
        await client.send("Page.navigate", {"url": "https://flow.google.com/"})
    for _w in range(16):
        await asyncio.sleep(0.5)
        ready = await client.eval(
            "Boolean(document.querySelector('button.new-project-button') || document.querySelector('flow-project-card'))"
        )
        if ready:
            break
    await asyncio.sleep(0.8)

    # Scroll grid slightly to hydrate lazy cards on current page
    await client.eval(
        """(() => {
            const scrollers = Array.from(document.querySelectorAll('*')).filter(e => e.scrollHeight > e.clientHeight + 80);
            for (const s of scrollers) { try { s.scrollTop = s.scrollHeight; } catch (e) {} }
        })()"""
    )
    await asyncio.sleep(0.4)
    await client.eval(
        """(() => {
            const scrollers = Array.from(document.querySelectorAll('*')).filter(e => e.scrollHeight > e.clientHeight + 80);
            for (const s of scrollers) { try { s.scrollTop = 0; } catch (e) {} }
        })()"""
    )
    await asyncio.sleep(0.3)
    return await _scan_dashboard_cards(client)


async def clean_flow_workspace_async(
    *,
    cdp_port: int = 9222,
    all_projects: bool = False,
    project_id: str | None = None,
    temp_project_id: str | None = None,
    project_urls: list[str] | tuple[str, ...] | set[str] = (),
    exclude_project_urls: list[str] | tuple[str, ...] | set[str] = (),
    prefix: str | None = None,
    dry_run: bool = False,
    clean_local_temp: bool = True,
    include_speed_cache: bool = False,
    force_active: bool = False,
) -> dict[str, Any]:
    """
    Cleans Google Flow projects on `https://flow.google.com/` inside a dedicated temporary
    leased CDP tab (closing its own tab on exit and never touching user tabs).
    """
    excluded_uuids = {extract_flow_project_uuid(u) for u in (exclude_project_urls or ()) if extract_flow_project_uuid(u)}
    target_uuids = {
        extract_flow_project_uuid(u)
        for u in (project_urls or ())
        if extract_flow_project_uuid(u) and extract_flow_project_uuid(u) not in excluded_uuids
    }
    has_flow_filter = bool(all_projects or project_id or target_uuids or prefix)
    deleted_projects: list[dict[str, str]] = []
    seen_deleted_uuids: set[str] = set()
    skipped_active_uuids: list[str] = []
    matched_preview: list[dict[str, str]] = []
    closed_orphan_tabs: list[str] = []
    remaining_cards = 0

    def _record_deleted(uid: str, title: str) -> None:
        if uid and uid in seen_deleted_uuids:
            return
        if uid:
            seen_deleted_uuids.add(uid)
        deleted_projects.append({"uuid": uid, "title": title})

    if not dry_run:
        closed_orphan_tabs = reap_orphan_pipeline_tabs(
            cdp_port=cdp_port,
            project_id=(None if all_projects else (project_id or temp_project_id)),
            dry_run=False,
        )

    if has_flow_filter:
        async with leased_cdp_tab(
            "https://flow.google.com/",
            purpose=f"flow-clean:{project_id or temp_project_id or ('all' if all_projects else 'targeted')}",
            cdp_port=cdp_port,
        ) as (client, clean_tab_id, _owner):
            await client.send("Page.enable")
            protected_uuids = (
                set(excluded_uuids)
                if force_active
                else (set(excluded_uuids) | _discover_active_leased_flow_uuids(cdp_port=cdp_port, exclude_tab_id=clean_tab_id))
            )

            for round_idx in range(25):
                cards = await _hydrate_and_scan_dashboard_cards(client, navigate=(round_idx > 0))
                remaining_cards = len(cards)
                if not cards:
                    break

                matching_cards: list[dict[str, Any]] = []
                for c in cards:
                    uid = extract_flow_project_uuid(str(c.get("href") or ""))
                    if _card_matches_filter(
                        c,
                        all_projects=all_projects,
                        project_id=project_id,
                        target_uuids=target_uuids,
                        prefix=prefix,
                    ):
                        if uid and uid in protected_uuids:
                            if uid not in skipped_active_uuids:
                                skipped_active_uuids.append(uid)
                            continue
                        matching_cards.append(c)

                if dry_run:
                    for mc in matching_cards:
                        matched_preview.append(
                            {
                                "uuid": extract_flow_project_uuid(str(mc.get("href") or "")),
                                "title": str(mc.get("title") or ""),
                            }
                        )
                    break

                if not matching_cards:
                    break

                # Fast bulk "Delete all projects" ONLY when every visible card matches and zero active rooms are protected
                if all_projects and not protected_uuids and len(matching_cards) == len(cards):
                    more_pt = await client.eval(
                        """(() => {
                            const b = document.querySelector('button[aria-label="More options"]');
                            if (!b) return null;
                            const r = b.getBoundingClientRect();
                            return r.width > 0 ? {x: r.x + r.width / 2, y: r.y + r.height / 2} : null;
                        })()"""
                    )
                    if isinstance(more_pt, dict) and more_pt.get("x", 0) > 0:
                        await _trusted_mouse_click(client, more_pt["x"], more_pt["y"])
                        await asyncio.sleep(0.45)
                        del_all_menu = await client.eval(
                            """(() => {
                                const items = Array.from(document.querySelectorAll('.cdk-overlay-pane button, .cdk-overlay-pane [role="menuitem"], .cdk-overlay-pane flow-menu-item'));
                                const hit = items.find(e => {
                                    if (e.tagName && e.tagName.toLowerCase() === 'flow-menu-item' && e.querySelector('button, [role="menuitem"]')) return false;
                                    if (e.disabled || e.getAttribute('aria-disabled') === 'true' || (e.classList && e.classList.contains('mat-mdc-menu-item-disabled'))) return false;
                                    if (e.querySelector && e.querySelector('button[disabled], [aria-disabled="true"], .mat-mdc-menu-item-disabled')) return false;
                                    if (!(e.innerText || '').toLowerCase().includes('delete all projects')) return false;
                                    const r = e.getBoundingClientRect();
                                    return r.width > 0 && r.height > 0;
                                });
                                if (!hit) return null;
                                const r = hit.getBoundingClientRect();
                                return {x: r.x + r.width / 2, y: r.y + r.height / 2};
                            })()"""
                        )
                        if isinstance(del_all_menu, dict) and del_all_menu.get("x", 0) > 0:
                            await _trusted_mouse_click(client, del_all_menu["x"], del_all_menu["y"])
                            await asyncio.sleep(0.55)
                            confirm_pt = await client.eval(
                                """(() => {
                                    const dlgBtns = Array.from(document.querySelectorAll('mat-dialog-container button'));
                                    const btns = dlgBtns.length ? dlgBtns : Array.from(document.querySelectorAll('.cdk-overlay-pane button, mat-dialog-container button'));
                                    const hit = btns.find(b => {
                                        if (b.disabled || b.getAttribute('aria-disabled') === 'true') return false;
                                        const rawT = (b.innerText || '').trim().toLowerCase();
                                        const t = rawT.replace(/^delete\\s+(?=delete\\b)/i, '');
                                        if (t !== 'delete all' && t !== 'delete') return false;
                                        const r = b.getBoundingClientRect();
                                        return r.width > 0 && r.height > 0;
                                    });
                                    if (!hit) return null;
                                    const r = hit.getBoundingClientRect();
                                    return {x: r.x + r.width / 2, y: r.y + r.height / 2};
                                })()"""
                            )
                            if isinstance(confirm_pt, dict) and confirm_pt.get("x", 0) > 0:
                                await _trusted_mouse_click(client, confirm_pt["x"], confirm_pt["y"])
                                for mc in matching_cards:
                                    _record_deleted(
                                        extract_flow_project_uuid(str(mc.get("href") or "")),
                                        str(mc.get("title") or ""),
                                    )
                                for _bw in range(12):
                                    await asyncio.sleep(0.5)
                                    if not (await _scan_dashboard_cards(client)):
                                        break
                                await asyncio.sleep(0.6)
                                continue
                        await _dismiss_cdk_overlays(client)

                # Targeted per-card deletion (always delete top-most matching card and re-query DOM coordinates)
                deleted_in_round = 0
                for _step in range(len(matching_cards)):
                    live_cards = await _scan_dashboard_cards(client)
                    next_hit = None
                    for lc in live_cards:
                        uid = extract_flow_project_uuid(str(lc.get("href") or ""))
                        if uid and uid in protected_uuids:
                            continue
                        if _card_matches_filter(
                            lc,
                            all_projects=all_projects,
                            project_id=project_id,
                            target_uuids=target_uuids,
                            prefix=prefix,
                        ):
                            next_hit = lc
                            break
                    if next_hit is None:
                        break
                    await client.eval(
                        f"""(() => {{
                            const cards = document.querySelectorAll('flow-project-card');
                            const c = cards[{int(next_hit['idx'])}];
                            if (c) {{
                                c.scrollIntoView({{block: 'center', inline: 'center'}});
                                c.dispatchEvent(new MouseEvent('mouseenter', {{bubbles: true}}));
                                c.dispatchEvent(new MouseEvent('mouseover', {{bubbles: true}}));
                            }}
                        }})()"""
                    )
                    await asyncio.sleep(0.25)
                    btn_pt = await client.eval(
                        f"""(() => {{
                            const cards = document.querySelectorAll('flow-project-card');
                            const c = cards[{int(next_hit['idx'])}];
                            if (!c) return null;
                            const direct = c.querySelector('button[aria-label="Delete project"]');
                            if (direct) {{
                                const r = direct.getBoundingClientRect();
                                if (r.width > 0 && r.height > 0) return {{x: r.x + r.width / 2, y: r.y + r.height / 2, mode: 'direct'}};
                            }}
                            const menuBtn = c.querySelector('button[aria-haspopup="menu"], button[aria-label*="option" i], button[aria-label*="more" i]')
                                || Array.from(c.querySelectorAll('button')).find(b => (b.innerText || '').trim().toLowerCase().includes('more_vert'));
                            if (!menuBtn) return null;
                            const rm = menuBtn.getBoundingClientRect();
                            return rm.width > 0 && rm.height > 0 ? {{x: rm.x + rm.width / 2, y: rm.y + rm.height / 2, mode: 'menu'}} : null;
                        }})()"""
                    )
                    if not isinstance(btn_pt, dict) or btn_pt.get("x", 0) <= 0:
                        break
                    await _trusted_mouse_click(client, btn_pt["x"], btn_pt["y"])
                    await asyncio.sleep(0.4)
                    if btn_pt.get("mode") == "menu":
                        menu_del_pt = await client.eval(
                            """(() => {
                                const items = Array.from(document.querySelectorAll('.cdk-overlay-pane button, .cdk-overlay-pane [role="menuitem"], .cdk-overlay-pane flow-menu-item'));
                                const hit = items.find(e => {
                                    if (e.tagName && e.tagName.toLowerCase() === 'flow-menu-item' && e.querySelector('button, [role="menuitem"]')) return false;
                                    if (e.disabled || e.getAttribute('aria-disabled') === 'true' || (e.classList && e.classList.contains('mat-mdc-menu-item-disabled'))) return false;
                                    if (e.querySelector && e.querySelector('button[disabled], [aria-disabled="true"], .mat-mdc-menu-item-disabled')) return false;
                                    const t = (e.innerText || '').trim().toLowerCase();
                                    if (!t.includes('delete project') && t !== 'delete' && !t.endsWith('\\ndelete')) return false;
                                    const r = e.getBoundingClientRect();
                                    return r.width > 0 && r.height > 0;
                                });
                                if (!hit) return null;
                                const r = hit.getBoundingClientRect();
                                return {x: r.x + r.width / 2, y: r.y + r.height / 2};
                            })()"""
                        )
                        if not isinstance(menu_del_pt, dict) or menu_del_pt.get("x", 0) <= 0:
                            await _dismiss_cdk_overlays(client)
                            break
                        await _trusted_mouse_click(client, menu_del_pt["x"], menu_del_pt["y"])
                        await asyncio.sleep(0.4)
                    conf_pt = await client.eval(
                        """(() => {
                            const dlgBtns = Array.from(document.querySelectorAll('mat-dialog-container button'));
                            const btns = dlgBtns.length ? dlgBtns : Array.from(document.querySelectorAll('.cdk-overlay-pane button, mat-dialog-container button'));
                            const hit = btns.find(b => {
                                if (b.disabled || b.getAttribute('aria-disabled') === 'true') return false;
                                const rawT = (b.innerText || '').trim().toLowerCase();
                                const t = rawT.replace(/^delete\\s+(?=delete\\b)/i, '');
                                if (t !== 'delete project' && t !== 'delete') return false;
                                const r = b.getBoundingClientRect();
                                return r.width > 0 && r.height > 0;
                            });
                            if (!hit) return null;
                            const r = hit.getBoundingClientRect();
                            return {x: r.x + r.width / 2, y: r.y + r.height / 2};
                        })()"""
                    )
                    if not isinstance(conf_pt, dict) or conf_pt.get("x", 0) <= 0:
                        await _dismiss_cdk_overlays(client)
                        break
                    await _trusted_mouse_click(client, conf_pt["x"], conf_pt["y"])
                    _record_deleted(
                        extract_flow_project_uuid(str(next_hit.get("href") or "")),
                        str(next_hit.get("title") or ""),
                    )
                    deleted_in_round += 1
                    await asyncio.sleep(0.85)

                if deleted_in_round == 0:
                    break

            if not dry_run:
                remaining_cards = len(await _hydrate_and_scan_dashboard_cards(client, navigate=True))

    local_rep = (
        purge_local_flow_temp_files(
            dry_run=dry_run,
            include_speed_cache=include_speed_cache,
            project_id=temp_project_id or project_id,
            cdp_port=cdp_port,
            force_active=force_active,
        )
        if clean_local_temp
        else {"dry_run": bool(dry_run), "removed_files_count": 0, "removed_dirs_count": 0}
    )
    return {
        "dry_run": bool(dry_run),
        "all_projects": bool(all_projects),
        "project_id": project_id or "",
        "prefix": prefix or "",
        "deleted_flow_projects_count": len(matched_preview) if dry_run else len(deleted_projects),
        "deleted_flow_projects": matched_preview if dry_run else deleted_projects,
        "skipped_active_leased_uuids": skipped_active_uuids,
        "closed_orphan_tabs": closed_orphan_tabs,
        "remaining_dashboard_cards": int(remaining_cards),
        "local_temp_cleanup": local_rep,
    }


def clean_flow_workspace(
    *,
    cdp_port: int = 9222,
    all_projects: bool = False,
    project_id: str | None = None,
    temp_project_id: str | None = None,
    project_urls: list[str] | tuple[str, ...] | set[str] = (),
    exclude_project_urls: list[str] | tuple[str, ...] | set[str] = (),
    prefix: str | None = None,
    dry_run: bool = False,
    clean_local_temp: bool = True,
    include_speed_cache: bool = False,
    force_active: bool = False,
) -> dict[str, Any]:
    """Synchronous entrypoint for `clean_flow_workspace_async`."""
    coro = clean_flow_workspace_async(
        cdp_port=cdp_port,
        all_projects=all_projects,
        project_id=project_id,
        temp_project_id=temp_project_id,
        project_urls=project_urls,
        exclude_project_urls=exclude_project_urls,
        prefix=prefix,
        dry_run=dry_run,
        clean_local_temp=clean_local_temp,
        include_speed_cache=include_speed_cache,
        force_active=force_active,
    )
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    result_box: list[dict[str, Any]] = []
    err_box: list[BaseException] = []

    def _runner() -> None:
        try:
            result_box.append(asyncio.run(coro))
        except BaseException as exc:  # noqa: BLE001
            err_box.append(exc)

    th = threading.Thread(target=_runner, daemon=True)
    th.start()
    th.join()
    if err_box:
        raise err_box[0]
    return result_box[0]
