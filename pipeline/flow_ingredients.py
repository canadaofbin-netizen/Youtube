"""
ALL ABOUT BRAIN - Google Flow reference-frame plumbing (R51 / R52), verified live on 2026-10-24.

Facts this module relies on (checked in the Milgram Flow tab):
  * The browser runs on another host behind CDP port 9222, so DOM.setFileInputFiles with a local path does not
    work. Files are injected as bytes: trusted click on "Upload media" with Page.setInterceptFileChooserDialog,
    then a File built from base64 is assigned to the hidden <input type=file> and 'change' is dispatched.
  * Uploaded files appear under Add ingredients -> Uploads with their file name; clicking the tile adds it to
    the prompt box as an "Ingredient" chip. Clicking an active chip removes it.
  * Old chips survive between generations (two errored video chips were still sitting in the prompt box), so
    the box is cleared before every clip.
  * Settings pane: Video -> Frames | Ingredients, 9:16, model, 4s / 6s / 8s, x1..x4 and the cost line.
    Omni 1.1 Flash = 4s/6s/8s/10s, 12 credits; with an ingredient attached "Length based on ingredient · 8s", 20 credits.
    Veo 3.1 - Lite [Lower Priority] = 4s/6s/8s, 0 credits. Production uses Omni only; Veo is refused.
"""

from __future__ import annotations

import asyncio
import base64
import json
import mimetypes
from pathlib import Path
from typing import Any

from pipeline.config import FLOW_ACTIVE_VIDEO_MODEL, FLOW_BANNED_VIDEO_MODEL_MARKERS

ADD_INGREDIENTS_SEL = 'button[aria-label="Add ingredients to the prompt box"]'
CHIP_SEL = 'flow-prompt-box button[aria-label="Ingredient"]'

_FIND_JS = r"""((sel, text, exact) => {
  const els = [...document.querySelectorAll(sel)].filter(e => e.getClientRects().length);
  const norm = e => (e.innerText || '').replace(/volume_up|arrow_drop_down/g, '').trim();
  const hit = els.reverse().find(e => exact ? norm(e) === text : norm(e).includes(text));
  if (!hit) return null; const r = hit.getBoundingClientRect(); return {x: r.x + r.width / 2, y: r.y + r.height / 2};
})"""


async def trusted_click(client: Any, point: dict[str, float] | None) -> bool:
    if not point:
        return False
    for t in ("mousePressed", "mouseReleased"):
        await client.send("Input.dispatchMouseEvent", {"type": t, "x": point["x"], "y": point["y"], "button": "left", "clickCount": 1})
    return True


async def find_point(client: Any, selector: str, text: str, exact: bool = False) -> dict[str, float] | None:
    return await client.eval(f"{_FIND_JS}({json.dumps(selector)}, {json.dumps(text)}, {json.dumps(exact)})")


async def press_escape(client: Any) -> None:
    for t in ("keyDown", "keyUp"):
        await client.send("Input.dispatchKeyEvent", {"type": t, "key": "Escape", "code": "Escape", "windowsVirtualKeyCode": 27})


async def count_chips(client: Any) -> int:
    return int(await client.eval(f"document.querySelectorAll({json.dumps(CHIP_SEL)}).length") or 0)


async def clear_prompt_ingredients(client: Any, max_rounds: int = 8) -> int:
    """Removes every ingredient chip (active or errored). Returns the remaining count (0 = clean)."""
    await press_escape(client)
    for _ in range(max_rounds):
        pt = await client.eval(
            f"""(() => {{ const c = [...document.querySelectorAll({json.dumps(CHIP_SEL)})].pop();
            if (!c) return null; const r = c.getBoundingClientRect(); return {{x: r.x + r.width/2, y: r.y + r.height/2}}; }})()"""
        )
        if not pt:
            return 0
        await trusted_click(client, pt)
        await asyncio.sleep(0.7)
    return await count_chips(client)


async def upload_file_to_flow(client: Any, file_path: Path, timeout_sec: float = 20.0) -> bool:
    """Uploads a local PNG / JPG / MP4 into the Flow project (bytes injection, works across hosts)."""
    path = Path(file_path)
    data_b64 = base64.b64encode(path.read_bytes()).decode()
    mime = mimetypes.guess_type(path.name)[0] or "image/png"
    await press_escape(client)
    await client.send("Page.enable")
    await client.send("DOM.enable")
    await client.send("Page.setInterceptFileChooserDialog", {"enabled": True})
    try:
        await client.eval(f"document.querySelector({json.dumps(ADD_INGREDIENTS_SEL)})?.click()")
        await asyncio.sleep(1.0)
        if not await trusted_click(client, await find_point(client, "flow-add-menu-popover-content button", "Upload media")):
            return False
        backend = None
        loop = asyncio.get_event_loop()
        end = loop.time() + timeout_sec
        while loop.time() < end and backend is None:
            try:
                msg = json.loads(await asyncio.wait_for(client.ws.recv(), timeout=2.0))
            except (asyncio.TimeoutError, TimeoutError):
                continue
            if msg.get("method") == "Page.fileChooserOpened":
                backend = msg["params"].get("backendNodeId")
        if backend is None:
            return False
        obj = (await client.send("DOM.resolveNode", {"backendNodeId": backend}))["object"]["objectId"]
        fn = """function(b64, name, mime) {
          const bin = atob(b64); const u8 = new Uint8Array(bin.length);
          for (let i = 0; i < bin.length; i++) u8[i] = bin.charCodeAt(i);
          const dt = new DataTransfer(); dt.items.add(new File([u8], name, {type: mime}));
          this.files = dt.files;
          this.dispatchEvent(new Event('input', {bubbles: true}));
          this.dispatchEvent(new Event('change', {bubbles: true}));
          return this.files.length; }"""
        res = await client.send("Runtime.callFunctionOn", {
            "objectId": obj, "functionDeclaration": fn, "returnByValue": True,
            "arguments": [{"value": data_b64}, {"value": path.name}, {"value": mime}],
        })
        return int((res.get("result") or {}).get("value") or 0) == 1
    finally:
        await client.send("Page.setInterceptFileChooserDialog", {"enabled": False})


async def attach_uploaded_by_name(client: Any, file_name: str, wait_sec: float = 30.0) -> bool:
    """Opens Add ingredients -> Uploads and clicks the tile whose label equals file_name. Verifies a new chip."""
    before = await count_chips(client)
    await press_escape(client)
    await client.eval(f"document.querySelector({json.dumps(ADD_INGREDIENTS_SEL)})?.click()")
    await asyncio.sleep(1.0)
    await trusted_click(client, await find_point(client, "flow-add-menu-popover-content button", "Uploads"))
    loop = asyncio.get_event_loop()
    end = loop.time() + wait_sec
    while loop.time() < end:
        pt = await find_point(client, "flow-add-menu-popover-content button, flow-add-menu-popover-content [role=option]", file_name)
        if pt:
            await trusted_click(client, pt)
            await asyncio.sleep(1.2)
            return await count_chips(client) == before + 1
        await asyncio.sleep(2.0)
    await press_escape(client)
    return False


async def read_settings_pane(client: Any) -> str:
    """Opens the settings pane, returns its text, closes it."""
    await press_escape(client)
    await trusted_click(client, await find_point(client, "flow-prompt-box button.settings-trigger-button", "x"))
    await asyncio.sleep(0.9)
    text = await client.eval("[...document.querySelectorAll('.cdk-overlay-pane')].map(e => e.innerText || '').join('\\n')") or ""
    await press_escape(client)
    return str(text)


async def select_flow_video_model(client: Any, model: str = FLOW_ACTIVE_VIDEO_MODEL) -> bool:
    """Opens settings -> model dropdown -> exact option (trusted clicks; synthetic clicks do not open the list)."""
    await press_escape(client)
    if not await client.eval("document.querySelectorAll('.cdk-overlay-pane').length"):
        await trusted_click(client, await find_point(client, "flow-prompt-box button.settings-trigger-button", "x"))
        await asyncio.sleep(0.9)
    dd = await find_point(client, ".cdk-overlay-pane button, .cdk-overlay-pane [aria-haspopup]", "Veo 3.1") or \
        await find_point(client, ".cdk-overlay-pane button, .cdk-overlay-pane [aria-haspopup]", "Omni")
    await trusted_click(client, dd)
    await asyncio.sleep(0.9)
    opt = await find_point(client, ".cdk-overlay-pane [role=option], .cdk-overlay-pane [role=menuitem], .cdk-overlay-pane button, .cdk-overlay-pane li", model, exact=True)
    await trusted_click(client, opt)
    await asyncio.sleep(1.2)
    text = await client.eval("[...document.querySelectorAll('.cdk-overlay-pane')].map(e => e.innerText || '').join('\\n')") or ""
    return model in str(text)


async def assert_model_settings(client: Any) -> dict[str, Any]:
    """Hard guard: generation may start only with the active Omni model selected; any Veo model is refused."""
    text = await read_settings_pane(client)
    banned = [m for m in FLOW_BANNED_VIDEO_MODEL_MARKERS if m in text]
    ok = FLOW_ACTIVE_VIDEO_MODEL in text and not banned
    return {"model_ok": ok, "banned_seen": banned, "pane": text.replace("\n", " | ")[:400]}


async def prepare_reference_frames(client: Any, files: list[Path]) -> dict[str, Any]:
    """Clear chips -> upload each file -> attach by name -> verify chip count -> verify Omni is selected."""
    remaining = await clear_prompt_ingredients(client)
    report: dict[str, Any] = {"cleared": remaining == 0, "attached": [], "failed": []}
    for f in files:
        ok = await upload_file_to_flow(client, Path(f)) and await attach_uploaded_by_name(client, Path(f).name)
        (report["attached"] if ok else report["failed"]).append(Path(f).name)
    report.update(await assert_model_settings(client))
    report["ready"] = bool(report["cleared"] and not report["failed"] and report["model_ok"])
    return report


__all__ = [
    "assert_model_settings",
    "select_flow_video_model",
    "attach_uploaded_by_name",
    "clear_prompt_ingredients",
    "prepare_reference_frames",
    "upload_file_to_flow",
]
