"""
ALL ABOUT BRAIN - Naver Whale CDP Session Controller
Connects to visible Naver Whale browser over Chrome DevTools Protocol (CDP),
reuses active tabs, prunes duplicate windows/tabs, and safely handles Polymer UI.
"""

import asyncio
from datetime import datetime, timezone
from pathlib import Path
import subprocess
import time
from typing import Any
from zoneinfo import ZoneInfo

from playwright.async_api import (
    Browser,
    ElementHandle,
    Page,
)

from pipeline.studio.config import (
    DEFAULT_CDP_HOST,
    DEFAULT_CDP_PORT,
    WHALE_EXECUTABLE,
)

_FLOW_BRIDGE_DIR = Path("/home/canadaofbin/chrome-profile/flow_bridge")
_STAGED_BRIDGE_FILES: set[Path] = set()
_EN_MONTH_ABBR = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def cleanup_staged_bridge_files(max_age_hours: float = 6.0) -> int:
    """
    Removes tracked upload files staged in `/home/canadaofbin/chrome-profile/flow_bridge/`
    and prunes stale `flow_bridge` files older than `max_age_hours` (default 6h).
    """
    removed = 0
    tracked_snapshot = list(_STAGED_BRIDGE_FILES)
    _STAGED_BRIDGE_FILES.clear()
    for p in tracked_snapshot:
        try:
            if p.exists() and p.is_file():
                p.unlink(missing_ok=True)
                removed += 1
        except OSError:
            pass

    if _FLOW_BRIDGE_DIR.exists() and _FLOW_BRIDGE_DIR.is_dir():
        cutoff = time.time() - (float(max_age_hours) * 3600.0)
        try:
            for item in _FLOW_BRIDGE_DIR.iterdir():
                if not item.is_file():
                    continue
                try:
                    if item.stat().st_mtime < cutoff:
                        item.unlink(missing_ok=True)
                        removed += 1
                except OSError:
                    pass
        except OSError:
            pass
    return removed


class WhaleSessionController:
    """
    Controls visible Naver Whale browser via Chrome DevTools Protocol (CDP: 127.0.0.1:9222).
    Strictly follows the Visible Naver Whale Browser Protocol:
    - Never uses headless chromium.
    - Reuses open tabs and cleans up leftover automation tabs.
    - Employs CDP Input.insertText for strict CSP / Trusted Types bypass.
    """

    def __init__(self, cdp_port: int = DEFAULT_CDP_PORT, cdp_host: str = DEFAULT_CDP_HOST):
        self.cdp_port = cdp_port
        self.cdp_host = cdp_host
        self.cdp_url = f"http://{cdp_host}:{cdp_port}"
        self.whale_exe = WHALE_EXECUTABLE

    def launch_whale_with_cdp(self) -> bool:
        """Launches visible Naver Whale with --remote-debugging-port enabled if not already active."""
        if not self.whale_exe.exists():
            print(f"[WhaleSession] Warning: Naver Whale not found at {self.whale_exe}")
            return False

        cmd = [
            str(self.whale_exe),
            f"--remote-debugging-port={self.cdp_port}",
            "--remote-allow-origins=*"
        ]
        print(f"[WhaleSession] Launching visible Naver Whale with CDP on port {self.cdp_port}...")
        try:
            subprocess.Popen(cmd)
            time.sleep(2.5)
            return True
        except Exception as e:
            print(f"[WhaleSession] Error launching Naver Whale: {e}")
            return False

    async def connect(self, playwright_instance: Any) -> Browser:
        """Connects to Naver Whale over CDP."""
        try:
            browser = await playwright_instance.chromium.connect_over_cdp(self.cdp_url)
            return browser
        except Exception as e:
            # Attempt to launch Whale if connection refused
            print(f"[WhaleSession] Initial CDP connection to {self.cdp_url} failed ({e}). Attempting launch...")
            self.launch_whale_with_cdp()
            await asyncio.sleep(2.0)
            return await playwright_instance.chromium.connect_over_cdp(self.cdp_url)

    def get_tab_target(self, url_match_pattern: str, default_url: str | None = None) -> dict[str, Any]:
        """
        Finds an open page target in Whale matching url_match_pattern via CDP HTTP API.
        If none found and default_url is given, opens a new tab via PUT /json/new.
        """
        import json
        import urllib.request

        try:
            res = urllib.request.urlopen(f"{self.cdp_url}/json/list", timeout=5).read().decode("utf-8")
            targets = json.loads(res)
        except Exception as e:
            print(f"[WhaleSession] Could not fetch CDP targets from {self.cdp_url}: {e}. Launching Whale...")
            self.launch_whale_with_cdp()
            time.sleep(2.0)
            res = urllib.request.urlopen(f"{self.cdp_url}/json/list", timeout=5).read().decode("utf-8")
            targets = json.loads(res)

        matching = [
            t for t in targets
            if t.get("type") == "page" and url_match_pattern.lower() in t.get("url", "").lower()
        ]
        for t in matching:
            if "UC4FeioYYv9X04Di07_MfZ7g" in t.get("url", ""):
                return t
        if matching:
            return matching[0]

        if default_url:
            import urllib.parse
            encoded_url = urllib.parse.quote(default_url, safe="")
            req = urllib.request.Request(f"{self.cdp_url}/json/new?{encoded_url}", method="PUT")
            res = urllib.request.urlopen(req, timeout=5).read().decode("utf-8")
            return json.loads(res)

        raise RuntimeError(f"No tab matching '{url_match_pattern}' found in Whale browser.")

    def get_direct_client(self, url_match_pattern: str, default_url: str | None = None) -> "DirectCDPClient":
        """Returns a DirectCDPClient connected to the target tab websocket."""
        target = self.get_tab_target(url_match_pattern, default_url)
        ws_url = target.get("webSocketDebuggerUrl")
        if not ws_url:
            raise RuntimeError(f"Target '{target.get('title')}' has no webSocketDebuggerUrl.")
        return DirectCDPClient(ws_url)

    def open_temp_direct_client(self, target_url: str) -> tuple["DirectCDPClient", str]:
        """
        Opens a dedicated temporary tab via PUT /json/new?<encoded_url> and returns
        (DirectCDPClient, target_id) so callers can close ONLY that temporary tab
        without hijacking or touching existing user tabs (R36-B).
        """
        import json
        import urllib.parse
        import urllib.request

        encoded_url = urllib.parse.quote(target_url, safe="")
        try:
            req = urllib.request.Request(f"{self.cdp_url}/json/new?{encoded_url}", method="PUT")
            raw = urllib.request.urlopen(req, timeout=8).read().decode("utf-8")
        except Exception as e:
            print(f"[WhaleSession] Could not open temp tab on {self.cdp_url}: {e}. Launching Whale...")
            self.launch_whale_with_cdp()
            time.sleep(2.0)
            req = urllib.request.Request(f"{self.cdp_url}/json/new?{encoded_url}", method="PUT")
            raw = urllib.request.urlopen(req, timeout=8).read().decode("utf-8")
        target = json.loads(raw)
        ws_url = target.get("webSocketDebuggerUrl")
        target_id = str(target.get("id") or "")
        if not ws_url or not target_id:
            raise RuntimeError(f"Temporary tab for '{target_url}' missing webSocketDebuggerUrl or id.")
        return DirectCDPClient(ws_url), target_id

    def close_tab_by_id(self, target_id: str) -> bool:
        """Closes a specific CDP page target by exact target_id."""
        if not target_id:
            return False
        import urllib.request
        try:
            urllib.request.urlopen(f"{self.cdp_url}/json/close/{target_id}", timeout=5).read()
            return True
        except Exception:
            return False

    def recycle_studio_tab(
        self,
        target_id: str | None = None,
        reopen_url: str | None = None,
    ) -> dict[str, Any]:
        """
        Recycles a YouTube Studio tab via CDP HTTP endpoints (R36-B memory hygiene).
        Strictly refuses to close any tab outside studio.youtube.com so active user tabs are untouched.
        Opens the replacement Studio tab BEFORE closing the stale Studio tab.
        """
        import json
        import urllib.parse
        import urllib.request
        from pipeline.studio.config import STUDIO_CONTENT_URL

        next_url = reopen_url or STUDIO_CONTENT_URL
        res = urllib.request.urlopen(f"{self.cdp_url}/json/list", timeout=5).read().decode("utf-8")
        targets = json.loads(res)

        stale_studio_ids: list[str] = []
        for t in targets:
            if t.get("type") != "page":
                continue
            t_id = str(t.get("id") or "")
            t_url = str(t.get("url") or "").lower()
            if "studio.youtube.com" not in t_url:
                continue
            if target_id is None or t_id == target_id:
                if t_id:
                    stale_studio_ids.append(t_id)

        encoded_next = urllib.parse.quote(next_url, safe="")
        req = urllib.request.Request(f"{self.cdp_url}/json/new?{encoded_next}", method="PUT")
        new_raw = urllib.request.urlopen(req, timeout=8).read().decode("utf-8")
        new_target = json.loads(new_raw)
        new_id = str(new_target.get("id") or "")

        for old_id in stale_studio_ids:
            if old_id and old_id != new_id:
                try:
                    urllib.request.urlopen(f"{self.cdp_url}/json/close/{old_id}", timeout=5).read()
                except Exception:
                    pass
        return new_target

    @staticmethod
    def cleanup_staged_bridge_files(max_age_hours: float = 6.0) -> int:
        """Delegates to module-level `cleanup_staged_bridge_files`."""
        return cleanup_staged_bridge_files(max_age_hours=max_age_hours)


_DEEP_QUERY_HELPER_JS = r"""
const __collectRoots = (node, out) => {
    if (!node) return;
    out.push(node);
    const tree = node.querySelectorAll ? node.querySelectorAll('*') : [];
    for (const el of tree) {
        if (el.shadowRoot) __collectRoots(el.shadowRoot, out);
    }
};
const __queryInScope = (scopeNode, simpleSel) => {
    const roots = [];
    if (scopeNode === document) {
        __collectRoots(document, roots);
    } else {
        if (scopeNode.shadowRoot) __collectRoots(scopeNode.shadowRoot, roots);
        __collectRoots(scopeNode, roots);
    }
    const seen = new Set();
    const out = [];
    for (const r of roots) {
        try {
            for (const el of r.querySelectorAll(simpleSel)) {
                if (!seen.has(el)) { seen.add(el); out.push(el); }
            }
        } catch (e) {}
    }
    return out;
};
const __splitDescendantSelector = (sel) => {
    const parts = [];
    let cur = '';
    let depthBracket = 0;
    let depthParen = 0;
    let quote = null;
    for (let i = 0; i < sel.length; i++) {
        const ch = sel[i];
        if (quote) {
            cur += ch;
            if (ch === quote && sel[i - 1] !== '\\') quote = null;
            continue;
        }
        if (ch === '"' || ch === "'") { quote = ch; cur += ch; continue; }
        if (ch === '[') { depthBracket++; cur += ch; continue; }
        if (ch === ']') { depthBracket = Math.max(0, depthBracket - 1); cur += ch; continue; }
        if (ch === '(') { depthParen++; cur += ch; continue; }
        if (ch === ')') { depthParen = Math.max(0, depthParen - 1); cur += ch; continue; }
        if (ch === ' ' && depthBracket === 0 && depthParen === 0) {
            if (cur.trim()) parts.push(cur.trim());
            cur = '';
            continue;
        }
        cur += ch;
    }
    if (cur.trim()) parts.push(cur.trim());
    return parts;
};
const __queryAllDeep = (rawSel, rootScope) => {
    if (!rawSel) return [];
    const startScope = rootScope || document;
    let baseSel = rawSel;
    let textNeedle = null;
    if (rawSel.includes(':has-text(')) {
        const m = rawSel.match(/^(.*?):has-text\(['"](.*?)['"]\)$/);
        if (m) {
            baseSel = (m[1] || '*').trim() || '*';
            textNeedle = m[2];
        }
    }
    let matches = __queryInScope(startScope, baseSel);
    if (matches.length === 0 && baseSel.includes(' ') && !baseSel.includes(',')) {
        const parts = __splitDescendantSelector(baseSel);
        if (parts.length > 1) {
            let current = [startScope];
            for (const part of parts) {
                const next = [];
                const seen = new Set();
                for (const scope of current) {
                    for (const el of __queryInScope(scope, part)) {
                        if (!seen.has(el)) { seen.add(el); next.push(el); }
                    }
                }
                current = next;
                if (current.length === 0) break;
            }
            matches = current;
        }
    }
    if (textNeedle !== null) {
        matches = matches.filter(e => ((e.innerText || e.textContent || '')).includes(textNeedle));
    }
    return matches;
};
const deepQueryAll = __queryAllDeep;
const __isVisibleEl = (el, sel) => {
    if (!el) return false;
    if (sel && (sel.includes("type='file'") || sel.includes('type="file"'))) return true;
    const style = window.getComputedStyle ? window.getComputedStyle(el) : null;
    if (style && (style.display === 'none' || style.visibility === 'hidden')) return false;
    const r = el.getBoundingClientRect ? el.getBoundingClientRect() : null;
    if (r) {
        return r.width > 0 && r.height > 0;
    }
    return el.offsetParent !== null;
};
"""


class DirectCDPClient:
    """
    Direct WebSocket CDP Client for Naver Whale.
    Bypasses Playwright connect_over_cdp multi-target hanging issues on Chromium 150.
    Supports recursive open Shadow-DOM piercing across Polymer/Lit web components.
    """
    def __init__(self, ws_url: str):
        self.ws_url = ws_url
        self.ws = None
        self.msg_id = 0
        self._send_lock: asyncio.Lock | None = None
        self._staged_bridge_files: set[Path] = set()

    async def __aenter__(self):
        import websockets
        self._ctx = websockets.connect(self.ws_url, max_size=25_000_000, ping_interval=None, open_timeout=30.0)
        self.ws = await self._ctx.__aenter__()
        try:
            await self.send("Page.enable", timeout_sec=10.0)
        except Exception:
            pass
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if hasattr(self, "_ctx") and self._ctx:
            try:
                await self._ctx.__aexit__(exc_type, exc_val, exc_tb)
            except Exception:
                pass
        self.ws = None

    async def send(self, method: str, params: dict | None = None, timeout_sec: float = 90.0) -> dict[str, Any]:
        import json
        if self._send_lock is None:
            self._send_lock = asyncio.Lock()
        async with self._send_lock:
            self.msg_id += 1
            cur_id = self.msg_id
            req = {"id": cur_id, "method": method}
            if params:
                req["params"] = params
            deadline = time.monotonic() + float(timeout_sec)
            send_timeout = max(0.1, deadline - time.monotonic())
            await asyncio.wait_for(self.ws.send(json.dumps(req)), timeout=send_timeout)
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError(f"CDP response timed out after {timeout_sec:.1f}s for method {method}")
                raw = await asyncio.wait_for(self.ws.recv(), timeout=remaining)
                resp = json.loads(raw)
                if resp.get("method") == "Page.javascriptDialogOpening":
                    try:
                        self.msg_id += 1
                        await self.ws.send(json.dumps({
                            "id": self.msg_id,
                            "method": "Page.handleJavaScriptDialog",
                            "params": {"accept": True},
                        }))
                    except Exception:
                        pass
                    continue
                if resp.get("id") == cur_id:
                    if "error" in resp:
                        raise RuntimeError(f"CDP Error ({method}): {resp['error']}")
                    return resp.get("result", {})

    async def eval(
        self,
        expression: str,
        include_command_line_api: bool = True,
        await_promise: bool = False,
    ) -> Any:
        res = await self.send("Runtime.evaluate", {
            "expression": expression,
            "returnByValue": True,
            "includeCommandLineAPI": include_command_line_api,
            "awaitPromise": bool(await_promise),
        })
        return res.get("result", {}).get("value")

    async def find_element(self, selectors: list[str] | str) -> bool:
        if isinstance(selectors, str):
            selectors = [selectors]
        import json
        js = f"""
        (() => {{
            {_DEEP_QUERY_HELPER_JS}
            const selList = {json.dumps(selectors)};
            for (const sel of selList) {{
                try {{
                    const els = __queryAllDeep(sel);
                    if (els.some(el => __isVisibleEl(el, sel))) return true;
                }} catch (e) {{}}
            }}
            return false;
        }})()
        """
        return bool(await self.eval(js))

    async def wait_for_element(self, selectors: list[str] | str, timeout_sec: float = 15.0) -> bool:
        start = asyncio.get_event_loop().time()
        while (asyncio.get_event_loop().time() - start) < timeout_sec:
            try:
                if await self.find_element(selectors):
                    return True
            except Exception:
                pass
            await asyncio.sleep(0.4)
        return False

    async def click(self, selectors: list[str] | str) -> bool:
        if isinstance(selectors, str):
            selectors = [selectors]
        import json
        js = f"""
        (() => {{
            {_DEEP_QUERY_HELPER_JS}
            const selList = {json.dumps(selectors)};
            const __isEnabledEl = (el) => {{
                if (!el) return false;
                if (el.disabled === true || el.hasAttribute('disabled') || el.getAttribute('aria-disabled') === 'true') return false;
                const inner = el.querySelector ? (el.querySelector('button') || (el.shadowRoot && el.shadowRoot.querySelector('button'))) : null;
                if (inner && (inner.disabled === true || inner.hasAttribute('disabled') || inner.getAttribute('aria-disabled') === 'true')) return false;
                return true;
            }};
            const __clickTarget = (target) => {{
                target.scrollIntoView({{block: 'center'}});
                const tag = (target.tagName || '').toUpperCase();
                if (tag === 'YTCP-TEXT-DROPDOWN-TRIGGER') {{
                    const dt = target.querySelector('ytcp-dropdown-trigger') || (target.shadowRoot && target.shadowRoot.querySelector('ytcp-dropdown-trigger'));
                    if (dt) {{ dt.click(); return true; }}
                }}
                const shouldPierceBtn = (
                    tag.startsWith('YTCP-')
                    || tag === 'YTD-BUTTON-RENDERER'
                    || tag === 'YT-BUTTON-SHAPE'
                    || tag === 'YT-ICON-BUTTON'
                    || tag === 'YT-BUTTON-RENDERER'
                );
                const innerBtn = shouldPierceBtn
                    ? (target.querySelector('button') || (target.shadowRoot && target.shadowRoot.querySelector('button')))
                    : null;
                if (innerBtn) {{
                    innerBtn.click();
                }} else {{
                    target.click();
                }}
                return true;
            }};
            // Pass 1: strictly visible AND enabled match across selector priority list
            for (const sel of selList) {{
                try {{
                    const els = __queryAllDeep(sel);
                    const target = els.find(el => __isVisibleEl(el, sel) && __isEnabledEl(el));
                    if (target) return __clickTarget(target);
                }} catch (e) {{}}
            }}
            // Pass 2: visible match fallback
            for (const sel of selList) {{
                try {{
                    const els = __queryAllDeep(sel);
                    const target = els.find(el => __isVisibleEl(el, sel));
                    if (target) return __clickTarget(target);
                }} catch (e) {{}}
            }}
            return false;
        }})()
        """
        return bool(await self.eval(js))

    async def type_into(self, selectors: list[str] | str, text: str) -> bool:
        if isinstance(selectors, str):
            selectors = [selectors]
        import json
        focused = await self.eval(
            f"""(() => {{
                {_DEEP_QUERY_HELPER_JS}
                const selList = {json.dumps(selectors)};
                for (const sel of selList) {{
                    try {{
                        const candidates = __queryAllDeep(sel);
                        const el = candidates.find(e => e.getBoundingClientRect().width > 0) || candidates[0];
                        if (el) {{
                            el.scrollIntoView({{block: 'center'}});
                            el.focus();
                            if (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') {{
                                el.select();
                            }} else {{
                                try {{ document.execCommand('selectAll', false, null); }} catch (e) {{}}
                                const range = document.createRange();
                                range.selectNodeContents(el);
                                const s = window.getSelection();
                                if (s) {{
                                    s.removeAllRanges();
                                    s.addRange(range);
                                }}
                            }}
                            return true;
                        }}
                    }} catch (e) {{}}
                }}
                return false;
            }})()"""
        )
        if not focused:
            return False
        await self.send(
            "Input.dispatchKeyEvent",
            {"type": "keyDown", "modifiers": 2, "key": "a", "code": "KeyA", "windowsVirtualKeyCode": 65},
        )
        await self.send(
            "Input.dispatchKeyEvent",
            {"type": "keyUp", "modifiers": 2, "key": "a", "code": "KeyA", "windowsVirtualKeyCode": 65},
        )
        await asyncio.sleep(0.05)
        await self.send("Input.dispatchKeyEvent", {"type": "keyDown", "key": "Backspace", "code": "Backspace", "windowsVirtualKeyCode": 8})
        await self.send("Input.dispatchKeyEvent", {"type": "keyUp", "key": "Backspace", "code": "Backspace", "windowsVirtualKeyCode": 8})
        await asyncio.sleep(0.1)
        inserted_via_dom = await self.eval(
            f"""(() => {{
                {_DEEP_QUERY_HELPER_JS}
                const selList = {json.dumps(selectors)};
                const targetText = {json.dumps(text)};
                for (const sel of selList) {{
                    try {{
                        const candidates = __queryAllDeep(sel);
                        const el = candidates.find(e => e.getBoundingClientRect().width > 0) || candidates[0];
                        if (el) {{
                            el.focus();
                            if (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') {{
                                const nativeSetter = Object.getOwnPropertyDescriptor(
                                    el.tagName === 'TEXTAREA' ? window.HTMLTextAreaElement.prototype : window.HTMLInputElement.prototype,
                                    'value'
                                )?.set;
                                if (nativeSetter) nativeSetter.call(el, targetText);
                                else el.value = targetText;
                                el.dispatchEvent(new Event('input', {{ bubbles: true, composed: true }}));
                                el.dispatchEvent(new Event('change', {{ bubbles: true, composed: true }}));
                                return true;
                            }} else {{
                                try {{
                                    document.execCommand('selectAll', false, null);
                                    document.execCommand('delete', false, null);
                                }} catch (e) {{}}
                                if ((el.innerText || el.textContent || '').length > 0) {{
                                    el.textContent = '';
                                }}
                                el.focus();
                                let ok = false;
                                try {{
                                    ok = document.execCommand('insertText', false, targetText);
                                }} catch (e) {{ ok = false; }}
                                if (!ok || !(el.innerText || el.textContent || '').trim()) {{
                                    el.textContent = targetText;
                                }}
                                el.dispatchEvent(new InputEvent('input', {{ bubbles: true, composed: true, data: targetText, inputType: 'insertText' }}));
                                el.dispatchEvent(new Event('change', {{ bubbles: true, composed: true }}));
                                el.dispatchEvent(new Event('blur', {{ bubbles: true, composed: true }}));
                                return Boolean((el.innerText || el.textContent || '').trim());
                            }}
                        }}
                    }} catch (e) {{}}
                }}
                return false;
            }})()"""
        )
        await asyncio.sleep(0.15)
        if not inserted_via_dom:
            await self.send("Input.insertText", {"text": text})
            await asyncio.sleep(0.25)
        return True

    async def set_schedule_datetime_utc(
        self,
        date_str_dd_mmm_yyyy: str = "",
        time_24h_utc: str = "",
        *,
        dt_et: datetime | None = None,
    ) -> bool:
        """
        Sets YouTube Studio schedule date & time on `ytcp-visibility-scheduler` in the browser's
        exact resolved timezone (`Intl.DateTimeFormat().resolvedOptions().timeZone`), supporting
        multiple Studio locale date formats (`Oct 30, 2026`, `30 Oct 2026`, `2026. 10. 30.`, `2026-10-30`)
        and both 24-hour (`09:00`) and 12-hour (`9:00 AM`, `오전 9:00`, `오후 12:00`) time pickers.
        """
        import json

        raw_tz = await self.eval("Intl.DateTimeFormat().resolvedOptions().timeZone")
        browser_tz_name = str(raw_tz or "").strip() or "Asia/Seoul"
        try:
            browser_tz = ZoneInfo(browser_tz_name)
        except Exception:
            browser_tz_name = "Asia/Seoul"
            browser_tz = ZoneInfo("Asia/Seoul")

        target_local_dt: datetime | None = None
        if dt_et is not None:
            aware_et = dt_et if dt_et.tzinfo is not None else dt_et.replace(tzinfo=ZoneInfo("America/New_York"))
            target_local_dt = aware_et.astimezone(browser_tz)
        elif date_str_dd_mmm_yyyy and time_24h_utc:
            hm_parts = str(time_24h_utc).strip().split(":")
            hh_u = int(hm_parts[0]) if hm_parts and hm_parts[0].isdigit() else 0
            mm_u = int(hm_parts[1]) if len(hm_parts) > 1 and hm_parts[1].isdigit() else 0
            for fmt in ("%d %b %Y", "%b %d, %Y", "%Y-%m-%d", "%Y. %m. %d."):
                try:
                    d_parsed = datetime.strptime(date_str_dd_mmm_yyyy.strip(), fmt)
                    dt_utc = datetime(d_parsed.year, d_parsed.month, d_parsed.day, hh_u, mm_u, tzinfo=timezone.utc)
                    target_local_dt = dt_utc.astimezone(browser_tz)
                    break
                except ValueError:
                    continue

        if target_local_dt is not None:
            d_loc = target_local_dt.date()
            mon = _EN_MONTH_ABBR[d_loc.month - 1]
            date_candidates = [
                f"{mon} {d_loc.day}, {d_loc.year}",
                f"{d_loc.day} {mon} {d_loc.year}",
                f"{d_loc.year}. {d_loc.month}. {d_loc.day}.",
                f"{d_loc.year:04d}-{d_loc.month:02d}-{d_loc.day:02d}",
                f"{mon} {d_loc.day:02d}, {d_loc.year}",
                f"{d_loc.day:02d} {mon} {d_loc.year}",
                f"{d_loc.year}. {d_loc.month:02d}. {d_loc.day:02d}.",
            ]
            h24 = target_local_dt.hour
            m24 = target_local_dt.minute
            h12 = 12 if (h24 % 12 == 0) else (h24 % 12)
            ampm_en = "AM" if h24 < 12 else "PM"
            ampm_ko = "오전" if h24 < 12 else "오후"
            time_candidates = [
                f"{h24:02d}:{m24:02d}",
                f"{h24}:{m24:02d}",
                f"{h12}:{m24:02d} {ampm_en}",
                f"{h12:02d}:{m24:02d} {ampm_en}",
                f"{ampm_ko} {h12}:{m24:02d}",
                f"{ampm_ko} {h12:02d}:{m24:02d}",
            ]
        else:
            date_candidates = [date_str_dd_mmm_yyyy] if date_str_dd_mmm_yyyy else []
            time_candidates = [time_24h_utc] if time_24h_utc else []

        if not date_candidates or not time_candidates:
            return False

        # 1. Expand Schedule container if collapsed
        await self.eval(
            f"""(() => {{
                {_DEEP_QUERY_HELPER_JS}
                const sched = __queryAllDeep('ytcp-visibility-scheduler')[0];
                if (!sched || sched.getBoundingClientRect().height === 0) {{
                    const btn = __queryAllDeep('#second-container-expand-button, #second-container, tp-yt-paper-radio-button[name="SCHEDULE"]')[0];
                    if (btn) btn.click();
                }}
            }})()"""
        )
        await asyncio.sleep(1.0)

        # 2. Click datepicker-trigger and set date matching Studio's active locale format
        await self.eval(
            f"""(() => {{
                {_DEEP_QUERY_HELPER_JS}
                const dp = __queryAllDeep('ytcp-visibility-scheduler #datepicker-trigger, #datepicker-trigger')[0];
                if (dp) dp.click();
            }})()"""
        )
        await asyncio.sleep(0.8)

        date_ok = bool(await self.eval(
            f"""(() => {{
                {_DEEP_QUERY_HELPER_JS}
                const cands = {json.dumps(date_candidates)};
                const dp = __queryAllDeep('ytcp-date-picker')[0];
                if (!dp) return false;
                const inp = dp.querySelector('input') || __queryAllDeep('ytcp-date-picker input')[0];
                const form = dp.querySelector('form') || __queryAllDeep('ytcp-date-picker form')[0];
                if (!inp) return false;

                const curVal = (inp.value || '').trim();
                let ordered = cands.slice();
                if (/^\\d{{4}}\\.\\s*\\d{{1,2}}\\.\\s*\\d{{1,2}}/.test(curVal)) {{
                    ordered.sort((a, b) => (/^\\d{{4}}\\./.test(b) ? 1 : 0) - (/^\\d{{4}}\\./.test(a) ? 1 : 0));
                }} else if (/^[A-Za-z]{{3}}\\s+\\d{{1,2}},\\s*\\d{{4}}/.test(curVal)) {{
                    ordered.sort((a, b) => (/^[A-Za-z]{{3}}\\s+/.test(b) ? 1 : 0) - (/^[A-Za-z]{{3}}\\s+/.test(a) ? 1 : 0));
                }} else if (/^\\d{{1,2}}\\s+[A-Za-z]{{3}}\\s+\\d{{4}}/.test(curVal)) {{
                    ordered.sort((a, b) => (/^\\d{{1,2}}\\s+[A-Za-z]{{3}}/.test(b) ? 1 : 0) - (/^\\d{{1,2}}\\s+[A-Za-z]{{3}}/.test(a) ? 1 : 0));
                }} else if (/^\\d{{4}}-\\d{{2}}-\\d{{2}}/.test(curVal)) {{
                    ordered.sort((a, b) => (/^\\d{{4}}-\\d{{2}}-\\d{{2}}/.test(b) ? 1 : 0) - (/^\\d{{4}}-\\d{{2}}-\\d{{2}}/.test(a) ? 1 : 0));
                }}

                const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')?.set;
                const isInvalid = () => (
                    dp.hasAttribute('invalid')
                    || inp.hasAttribute('invalid')
                    || inp.getAttribute('aria-invalid') === 'true'
                );

                for (const candidate of ordered) {{
                    inp.focus();
                    if (nativeSetter) nativeSetter.call(inp, candidate);
                    else inp.value = candidate;
                    inp.dispatchEvent(new Event('input', {{ bubbles: true, composed: true }}));
                    inp.dispatchEvent(new Event('change', {{ bubbles: true, composed: true }}));
                    inp.dispatchEvent(new KeyboardEvent('keydown', {{ key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true, composed: true }}));
                    if (form) {{
                        form.dispatchEvent(new Event('submit', {{ bubbles: true, cancelable: true }}));
                    }}
                    if (!isInvalid() && (inp.value || '').trim().length > 0) {{
                        return true;
                    }}
                }}
                return false;
            }})()"""
        ))
        await asyncio.sleep(0.8)

        # 3. Click time-of-day input and select matching 24h or 12h (EN/KO) tp-yt-paper-item
        await self.eval(
            f"""(() => {{
                {_DEEP_QUERY_HELPER_JS}
                const inp = __queryAllDeep('ytcp-visibility-scheduler #time-of-day-container input, #time-of-day-container input')[0];
                if (inp) {{ inp.click(); inp.focus(); }}
            }})()"""
        )
        await asyncio.sleep(0.8)
        time_clicked = bool(await self.eval(
            f"""(() => {{
                {_DEEP_QUERY_HELPER_JS}
                const norm = (s) => (s || '').replace(/\\u202f|\\u00a0/g, ' ').replace(/\\s+/g, ' ').trim().toLowerCase();
                const wanted = new Set({json.dumps([c.lower() for c in time_candidates])}.map(norm));
                const items = __queryAllDeep('tp-yt-paper-item');
                const target = items.find(e => wanted.has(norm(e.innerText || e.textContent || '')));
                if (target) {{
                    target.scrollIntoView({{block: 'center'}});
                    target.click();
                    return true;
                }}
                const inp = __queryAllDeep('ytcp-visibility-scheduler #time-of-day-container input, #time-of-day-container input')[0];
                if (inp) {{
                    const cur = norm(inp.value || '');
                    let pick = {json.dumps(time_candidates[0])};
                    if (/오전|오후/.test(cur)) {{
                        pick = ({json.dumps(time_candidates)}.find(x => /오전|오후/.test(x))) || pick;
                    }} else if (/am|pm/i.test(cur)) {{
                        pick = ({json.dumps(time_candidates)}.find(x => /AM|PM/.test(x))) || pick;
                    }}
                    const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')?.set;
                    inp.focus();
                    if (nativeSetter) nativeSetter.call(inp, pick);
                    else inp.value = pick;
                    inp.dispatchEvent(new Event('input', {{ bubbles: true, composed: true }}));
                    inp.dispatchEvent(new Event('change', {{ bubbles: true, composed: true }}));
                    inp.dispatchEvent(new KeyboardEvent('keydown', {{ key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true, composed: true }}));
                    const host = inp.closest('ytcp-form-input-container, #time-of-day-container');
                    const inv = inp.hasAttribute('invalid')
                        || inp.getAttribute('aria-invalid') === 'true'
                        || (host ? host.hasAttribute('invalid') : false);
                    return !inv && norm(inp.value || '').length > 0;
                }}
                return false;
            }})()"""
        ))
        await asyncio.sleep(0.6)
        return bool(date_ok and time_clicked)

    async def set_file_input(
        self,
        file_path: Path,
        selector: str | list[str] = "input[type='file'][name='Filedata'], input[type='file']"
    ) -> bool:
        import json
        import os
        import shutil
        resolved_path = file_path.resolve()
        cdp_file_str = str(resolved_path)
        if os.name != "nt" and Path("/home/canadaofbin/chrome-profile").exists():
            host_dl_dir = _FLOW_BRIDGE_DIR
            host_dl_dir.mkdir(parents=True, exist_ok=True)
            staged_name = f"studio_upload_{resolved_path.parent.parent.name}_{resolved_path.name}"
            host_staged = host_dl_dir / staged_name
            if resolved_path != host_staged:
                shutil.copy2(resolved_path, host_staged)
                _STAGED_BRIDGE_FILES.add(host_staged)
                self._staged_bridge_files.add(host_staged)
            cdp_file_str = f"/home/seluser/chrome-profile/flow_bridge/{staged_name}"

        if isinstance(selector, list):
            sel_parts = [s.strip() for s in selector if isinstance(s, str) and s.strip()]
            selector_css = ", ".join(sel_parts)
        else:
            sel_parts = [s.strip() for s in selector.split(",") if s.strip()]
            selector_css = selector
        deep_expr = f"""(() => {{
            {_DEEP_QUERY_HELPER_JS}
            const sels = {json.dumps(sel_parts)};
            for (const s of sels) {{
                try {{
                    const found = __queryAllDeep(s);
                    if (found.length > 0) return found[0];
                }} catch (e) {{}}
            }}
            return document.querySelector({json.dumps(selector_css)});
        }})()"""

        # 1. Primary: Fast & Shadow-DOM-piercing objectId resolution via Runtime.evaluate
        try:
            eval_res = await self.send("Runtime.evaluate", {
                "expression": deep_expr,
                "returnByValue": False,
            })
            obj_id = eval_res.get("result", {}).get("objectId")
            if obj_id:
                await self.send("DOM.setFileInputFiles", {
                    "files": [cdp_file_str],
                    "objectId": obj_id,
                })
                return True
        except Exception:
            pass

        # 2. Secondary fallback via DOM.getDocument & nodeId
        try:
            doc = await self.send("DOM.getDocument", {"depth": -1, "pierce": True})
            root_node_id = doc.get("root", {}).get("nodeId")
            input_node = await self.send("DOM.querySelector", {
                "nodeId": root_node_id,
                "selector": selector_css,
            })
            node_id = input_node.get("nodeId")
            if node_id:
                await self.send("DOM.setFileInputFiles", {
                    "files": [cdp_file_str],
                    "nodeId": node_id,
                })
                return True
        except Exception:
            pass

        return False

    @staticmethod
    def cleanup_staged_bridge_files(max_age_hours: float = 6.0) -> int:
        """Delegates to module-level `cleanup_staged_bridge_files`."""
        return cleanup_staged_bridge_files(max_age_hours=max_age_hours)


    async def get_or_open_tab(
        self,
        browser: Browser,
        url_match_pattern: str,
        default_url: str,
        activate: bool = True
    ) -> Page:
        """
        Discovers existing tab matching url_match_pattern across contexts;
        if not found, navigates a new page to default_url.
        """
        context = browser.contexts[0] if browser.contexts else await browser.new_context()

        # Scan existing pages
        for page in context.pages:
            if url_match_pattern.lower() in page.url.lower():
                print(f"[WhaleSession] Reusing existing tab: {page.url[:80]}...")
                if activate:
                    try:
                        await page.bring_to_front()
                    except Exception:
                        pass
                return page

        # No matching tab found; create new tab
        print(f"[WhaleSession] Opening new tab for: {default_url}...")
        page = await context.new_page()
        await page.goto(default_url, wait_until="domcontentloaded", timeout=45000)
        if activate:
            try:
                await page.bring_to_front()
            except Exception:
                pass
        return page

    async def close_extra_tabs(self, browser: Browser, keep_url_keywords: list[str]) -> int:
        """Closes stray, blank or duplicate tabs not matching keep_url_keywords."""
        closed_count = 0
        for ctx in browser.contexts:
            pages = list(ctx.pages)
            if len(pages) <= 1:
                continue
            for page in pages:
                url = page.url.lower()
                keep = any(k.lower() in url for k in keep_url_keywords)
                if not keep and ("about:blank" in url or "chrome://" in url or "whale://" in url):
                    try:
                        await page.close()
                        closed_count += 1
                    except Exception:
                        pass
        return closed_count

    async def find_first_matching(
        self,
        container: Page | ElementHandle,
        selector_list: list[str],
        timeout_ms: int = 5000
    ) -> tuple[ElementHandle | None, str]:
        """Tries a list of fallback selectors until one matches and is visible."""
        start_time = time.time()
        while (time.time() - start_time) * 1000 < timeout_ms:
            for selector in selector_list:
                try:
                    el = await container.query_selector(selector)
                    if el and await el.is_visible():
                        return el, selector
                except Exception:
                    continue
            await asyncio.sleep(0.3)

        # One final check even if not visible (e.g. file inputs are hidden)
        for selector in selector_list:
            try:
                el = await container.query_selector(selector)
                if el:
                    return el, selector
            except Exception:
                continue

        return None, ""

    async def safe_click(
        self,
        container: Page | ElementHandle,
        selector_list: list[str],
        timeout_ms: int = 5000,
        delay_after: float = 0.5
    ) -> bool:
        """Safely clicks the first visible matching element."""
        el, sel = await self.find_first_matching(container, selector_list, timeout_ms=timeout_ms)
        if el:
            try:
                await el.click()
                if delay_after > 0:
                    await asyncio.sleep(delay_after)
                return True
            except Exception as e:
                print(f"[WhaleSession] Click failed on '{sel}': {e}")
        return False

    async def safe_type_cdp(
        self,
        page: Page,
        element: ElementHandle,
        text: str,
        clear_first: bool = True
    ) -> bool:
        """
        Bypasses YouTube Studio Trusted Types CSP and rich Polymer textboxes
        using CDP Input.insertText.
        """
        try:
            await element.click()
            await asyncio.sleep(0.2)
            if clear_first:
                # Select all and backspace
                await page.keyboard.press("Control+A")
                await asyncio.sleep(0.1)
                await page.keyboard.press("Backspace")
                await asyncio.sleep(0.1)

            cdp_session = await page.context.new_cdp_session(page)
            await cdp_session.send("Input.insertText", {"text": text})
            await asyncio.sleep(0.3)
            return True
        except Exception as e:
            print(f"[WhaleSession] CDP safe_type error: {e}")
            try:
                await element.fill(text)
                return True
            except Exception:
                return False
