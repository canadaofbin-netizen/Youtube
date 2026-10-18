"""
ALL ABOUT BRAIN - Naver Whale CDP Session Controller
Connects to visible Naver Whale browser over Chrome DevTools Protocol (CDP),
reuses active tabs, prunes duplicate windows/tabs, and safely handles Polymer UI.
"""

import asyncio
from pathlib import Path
import subprocess
import time
from typing import Any

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
            req = urllib.request.Request(f"{self.cdp_url}/json/new?{default_url}", method="PUT")
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


class DirectCDPClient:
    """
    Direct WebSocket CDP Client for Naver Whale.
    Bypasses Playwright connect_over_cdp multi-target hanging issues on Chromium 150.
    """
    def __init__(self, ws_url: str):
        self.ws_url = ws_url
        self.ws = None
        self.msg_id = 0

    async def __aenter__(self):
        import websockets
        self._ctx = websockets.connect(self.ws_url, max_size=25_000_000, ping_interval=None, open_timeout=30.0)
        self.ws = await self._ctx.__aenter__()
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
        from pipeline.config import MAX_LOOP_ITERATIONS
        self.msg_id += 1
        cur_id = self.msg_id
        req = {"id": cur_id, "method": method}
        if params:
            req["params"] = params
        await asyncio.wait_for(self.ws.send(json.dumps(req)), timeout=timeout_sec)
        for _ in range(MAX_LOOP_ITERATIONS * 10):
            raw = await asyncio.wait_for(self.ws.recv(), timeout=timeout_sec)
            resp = json.loads(raw)
            if resp.get("id") == cur_id:
                if "error" in resp:
                    raise RuntimeError(f"CDP Error ({method}): {resp['error']}")
                return resp.get("result", {})
        raise TimeoutError(f"CDP response loop exceeded max iterations for method {method}")

    async def eval(self, expression: str, include_command_line_api: bool = True) -> Any:
        res = await self.send("Runtime.evaluate", {
            "expression": expression,
            "returnByValue": True,
            "includeCommandLineAPI": include_command_line_api,
        })
        return res.get("result", {}).get("value")

    async def find_element(self, selectors: list[str] | str) -> bool:
        if isinstance(selectors, str):
            selectors = [selectors]
        import json
        js = f"""
        (() => {{
            const selList = {json.dumps(selectors)};
            for (const sel of selList) {{
                try {{
                    if (sel.includes(':has-text(')) {{
                        const m = sel.match(/^(.*?):has-text\\(['"](.*?)['"]\\)$/);
                        if (m) {{
                            const baseSel = m[1] || '*';
                            const text = m[2];
                            const els = Array.from(document.querySelectorAll(baseSel));
                            const match = els.find(e => e.innerText && e.innerText.includes(text));
                            if (match && match.offsetParent !== null) return true;
                        }}
                    }} else {{
                        const el = document.querySelector(sel);
                        if (el && (el.offsetParent !== null || (el.getClientRects && el.getClientRects().length > 0) || sel.includes("input") || sel.includes("textbox"))) return true;
                    }}
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
            const selList = {json.dumps(selectors)};
            for (const sel of selList) {{
                try {{
                    let target = null;
                    if (sel.includes(':has-text(')) {{
                        const m = sel.match(/^(.*?):has-text\\(['"](.*?)['"]\\)$/);
                        if (m) {{
                            const baseSel = m[1] || '*';
                            const text = m[2];
                            const els = Array.from(document.querySelectorAll(baseSel));
                            target = els.find(e => e.innerText && e.innerText.includes(text));
                        }}
                    }} else {{
                        target = document.querySelector(sel);
                    }}
                    if (target) {{
                        target.scrollIntoView({{block: 'center'}});
                        target.click();
                        return true;
                    }}
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
        js = f"""
        (() => {{
            const selList = {json.dumps(selectors)};
            for (const sel of selList) {{
                try {{
                    const el = document.querySelector(sel);
                    if (el) {{
                        el.focus();
                        document.execCommand('selectAll', false, null);
                        document.execCommand('insertText', false, {json.dumps(text)});
                        el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                        el.dispatchEvent(new Event('change', {{ bubbles: true }}));
                        return true;
                    }}
                }} catch (e) {{}}
            }}
            return false;
        }})()
        """
        return bool(await self.eval(js))

    async def set_file_input(
        self,
        file_path: Path,
        selector: str = "input[type='file'][name='Filedata'], input[type='file']"
    ) -> bool:
        import os
        import shutil
        resolved_path = file_path.resolve()
        cdp_file_str = str(resolved_path)
        if os.name != "nt":
            host_dl_dir = Path("/home/canadaofbin/chrome-profile/flow_bridge")
            host_dl_dir.mkdir(parents=True, exist_ok=True)
            staged_name = f"studio_upload_{resolved_path.parent.parent.name}_{resolved_path.name}"
            host_staged = host_dl_dir / staged_name
            if resolved_path != host_staged:
                shutil.copy2(resolved_path, host_staged)
            cdp_file_str = f"/home/seluser/chrome-profile/flow_bridge/{staged_name}"

        # 1. Primary: Fast & 100% reliable objectId resolution via Runtime.evaluate
        try:
            eval_res = await self.send("Runtime.evaluate", {
                "expression": f"document.querySelector({json.dumps(selector)})",
                "returnByValue": False
            })
            obj_id = eval_res.get("result", {}).get("objectId")
            if obj_id:
                await self.send("DOM.setFileInputFiles", {
                    "files": [cdp_file_str],
                    "objectId": obj_id
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
                "selector": selector
            })
            node_id = input_node.get("nodeId")
            if node_id:
                await self.send("DOM.setFileInputFiles", {
                    "files": [cdp_file_str],
                    "nodeId": node_id
                })
                return True
        except Exception:
            pass

        return False


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
