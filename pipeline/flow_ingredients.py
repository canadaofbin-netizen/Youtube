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

from pipeline.config import (
    FLOW_ACTIVE_VIDEO_MODEL,
    FLOW_BANNED_VIDEO_MODEL_MARKERS,
    FLOW_PRIMARY_VIDEO_MODEL,
    FLOW_VIDEO_MODEL_PROFILES,
    FLOW_ZERO_CREDIT_MODEL,
)

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


def _find_file_input_backend_nodes(node: dict[str, Any], out: list[int]) -> None:
    if not isinstance(node, dict):
        return
    if str(node.get("nodeName") or "").upper() == "INPUT":
        attrs = node.get("attributes") or []
        attr_map = {str(attrs[i]).lower(): str(attrs[i + 1]).lower() for i in range(0, len(attrs) - 1, 2)}
        if attr_map.get("type") == "file" and node.get("backendNodeId"):
            out.append(int(node["backendNodeId"]))
    for child in node.get("children") or []:
        _find_file_input_backend_nodes(child, out)
    for sroot in node.get("shadowRoots") or []:
        _find_file_input_backend_nodes(sroot, out)


async def upload_file_to_flow(client: Any, file_path: Path, timeout_sec: float = 20.0) -> bool:
    """Uploads a local PNG / JPG / MP4 into the Flow project (bytes injection via client.send, works across hosts)."""
    path = Path(file_path)
    data_b64 = base64.b64encode(path.read_bytes()).decode()
    mime = mimetypes.guess_type(path.name)[0] or "image/png"
    fn = """function(b64, name, mime) {
      const bin = atob(b64); const u8 = new Uint8Array(bin.length);
      for (let i = 0; i < bin.length; i++) u8[i] = bin.charCodeAt(i);
      const dt = new DataTransfer(); dt.items.add(new File([u8], name, {type: mime}));
      this.files = dt.files;
      this.dispatchEvent(new Event('input', {bubbles: true}));
      this.dispatchEvent(new Event('change', {bubbles: true}));
      return this.files.length; }"""

    await press_escape(client)
    await client.send("Page.enable")
    await client.send("DOM.enable")
    await client.send("Page.setInterceptFileChooserDialog", {"enabled": True})
    try:
        await client.eval("""(() => {
            window.__bci_captured_file_input = null;
            if (!HTMLInputElement.prototype.__bci_orig_click) {
                HTMLInputElement.prototype.__bci_orig_click = HTMLInputElement.prototype.click;
                HTMLInputElement.prototype.click = function(...args) {
                    if ((this.type || '').toLowerCase() === 'file') {
                        window.__bci_captured_file_input = this;
                    }
                    return HTMLInputElement.prototype.__bci_orig_click.apply(this, args);
                };
            }
        })()""")
        await client.eval(f"document.querySelector({json.dumps(ADD_INGREDIENTS_SEL)})?.click()")
        await asyncio.sleep(1.0)
        if not await trusted_click(client, await find_point(client, "flow-add-menu-popover-content button", "Upload media")):
            return False

        loop = asyncio.get_running_loop()
        end = loop.time() + timeout_sec
        obj_id: str | None = None
        while loop.time() < end and not obj_id:
            eval_res = await client.send(
                "Runtime.evaluate",
                {
                    "expression": "window.__bci_captured_file_input || [...document.querySelectorAll('input[type=\"file\"]')].pop() || null",
                    "returnByValue": False,
                },
            )
            rem_obj = (eval_res or {}).get("result") or {}
            if rem_obj.get("objectId") and rem_obj.get("subtype") != "null":
                obj_id = str(rem_obj["objectId"])
                break

            doc_res = await client.send("DOM.getDocument", {"depth": -1, "pierce": True})
            root_node = (doc_res or {}).get("root") or {}
            backend_ids: list[int] = []
            _find_file_input_backend_nodes(root_node, backend_ids)
            if not backend_ids and root_node.get("nodeId"):
                q_res = await client.send(
                    "DOM.querySelectorAll",
                    {"nodeId": int(root_node["nodeId"]), "selector": 'input[type="file"]'},
                )
                node_ids = (q_res or {}).get("nodeIds") or []
                if node_ids:
                    resolved = await client.send("DOM.resolveNode", {"nodeId": int(node_ids[-1])})
                    cand_obj = ((resolved or {}).get("object") or {}).get("objectId")
                    if cand_obj:
                        obj_id = str(cand_obj)
                        break
            if backend_ids:
                resolved = await client.send("DOM.resolveNode", {"backendNodeId": int(backend_ids[-1])})
                cand_obj = ((resolved or {}).get("object") or {}).get("objectId")
                if cand_obj:
                    obj_id = str(cand_obj)
                    break
            await asyncio.sleep(0.25)

        if not obj_id:
            return False

        res = await client.send(
            "Runtime.callFunctionOn",
            {
                "objectId": obj_id,
                "functionDeclaration": fn,
                "returnByValue": True,
                "arguments": [{"value": data_b64}, {"value": path.name}, {"value": mime}],
            },
        )
        return int(((res or {}).get("result") or {}).get("value") or 0) == 1
    finally:
        try:
            await client.eval("""(() => {
                if (HTMLInputElement.prototype.__bci_orig_click) {
                    HTMLInputElement.prototype.click = HTMLInputElement.prototype.__bci_orig_click;
                    delete HTMLInputElement.prototype.__bci_orig_click;
                }
                delete window.__bci_captured_file_input;
            })()""")
        except Exception:
            pass
        try:
            await client.send("Page.setInterceptFileChooserDialog", {"enabled": False})
        except Exception:
            pass
        try:
            await client.send("DOM.disable")
        except Exception:
            pass


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


async def read_active_flow_model_family(client: Any) -> str:
    """Reads `videoModelFamilyId` from `localStorage['flow-prompt-box-settings']` cleanly."""
    val = await client.eval(
        """(() => {
            try {
                return JSON.parse(localStorage.getItem("flow-prompt-box-settings") || "{}").videoModelFamilyId || "";
            } catch (e) {
                return "";
            }
        })()"""
    )
    return str(val or "").strip()


def _family_matches_model(model: str, family_id: str) -> bool:
    fam = str(family_id or "").strip().lower()
    if model == FLOW_ZERO_CREDIT_MODEL:
        return fam == "veo_3_1_lite_low_priority"
    if model in (FLOW_PRIMARY_VIDEO_MODEL, FLOW_ACTIVE_VIDEO_MODEL):
        return fam in ("omni", "omni_1_1_flash") or fam.startswith("omni")
    expected = str((FLOW_VIDEO_MODEL_PROFILES.get(model) or {}).get("model_family_id") or "").strip().lower()
    if expected:
        return fam == expected or (expected.startswith("omni") and fam.startswith("omni"))
    return bool(fam)


async def read_settings_pane(client: Any) -> str:
    """Opens the settings pane, returns its text, closes it."""
    await press_escape(client)
    trig = await find_point(client, "flow-prompt-box button.settings-trigger-button", "x")
    if not trig:
        trig = await client.eval(
            """(() => {
                const b = document.querySelector('flow-prompt-box button.settings-trigger-button, button.settings-trigger-button');
                if (!b || !b.getClientRects().length) return null;
                const r = b.getBoundingClientRect();
                return {x: r.x + r.width / 2, y: r.y + r.height / 2};
            })()"""
        )
    await trusted_click(client, trig)
    await asyncio.sleep(0.9)
    text = await client.eval("[...document.querySelectorAll('.cdk-overlay-pane')].map(e => e.innerText || '').join('\\n')") or ""
    await press_escape(client)
    return str(text)


async def select_flow_video_model(client: Any, model: str = FLOW_PRIMARY_VIDEO_MODEL) -> bool:
    """
    Opens settings -> model dropdown -> exact option (trusted clicks; synthetic clicks do not open the list),
    verifying selection via BOTH overlay text AND `localStorage["flow-prompt-box-settings"].videoModelFamilyId`.
    """
    await press_escape(client)
    if not await client.eval("document.querySelectorAll('.cdk-overlay-pane').length"):
        trig = await find_point(client, "flow-prompt-box button.settings-trigger-button", "x")
        if not trig:
            trig = await client.eval(
                """(() => {
                    const b = document.querySelector('flow-prompt-box button.settings-trigger-button, button.settings-trigger-button');
                    if (!b || !b.getClientRects().length) return null;
                    const r = b.getBoundingClientRect();
                    return {x: r.x + r.width / 2, y: r.y + r.height / 2};
                })()"""
            )
        await trusted_click(client, trig)
        await asyncio.sleep(0.9)

    dd_sel = ".cdk-overlay-pane button, .cdk-overlay-pane [aria-haspopup], .cdk-overlay-pane [role=combobox], flow-prompt-box-settings button, flow-prompt-box-settings [aria-haspopup]"
    dd = (
        await find_point(client, dd_sel, "Omni")
        or await find_point(client, dd_sel, "Veo")
        or await find_point(client, dd_sel, "Lite")
    )
    if not dd:
        dd = await client.eval(
            """(() => {
                const cands = [...document.querySelectorAll('.cdk-overlay-pane [aria-haspopup], .cdk-overlay-pane [role="combobox"], flow-prompt-box-settings [aria-haspopup]')].filter(e => e.getClientRects().length);
                const hit = cands[0];
                if (!hit) return null;
                const r = hit.getBoundingClientRect();
                return {x: r.x + r.width / 2, y: r.y + r.height / 2};
            })()"""
        )
    await trusted_click(client, dd)
    await asyncio.sleep(0.9)

    opt_sel = ".cdk-overlay-pane [role=option], .cdk-overlay-pane [role=menuitem], .cdk-overlay-pane button, .cdk-overlay-pane li"
    opt = await find_point(client, opt_sel, model, exact=True) or await find_point(client, opt_sel, model, exact=False)
    await trusted_click(client, opt)
    await asyncio.sleep(1.2)
    text = await client.eval(
        "[...document.querySelectorAll('.cdk-overlay-pane, flow-prompt-box-settings')].map(e => e.innerText || '').join('\\n')"
    ) or ""
    family_id = await read_active_flow_model_family(client)
    return (model in str(text)) and _family_matches_model(model, family_id)


async def assert_model_settings(client: Any, allow_zero_credit_fallback: bool = True) -> dict[str, Any]:
    """
    Verifies active Flow video model in settings pane + `localStorage['flow-prompt-box-settings']`.
    Recognizes `FLOW_PRIMARY_VIDEO_MODEL` (`Omni 1.1 Flash`) and, when `allow_zero_credit_fallback=True`,
    `FLOW_ZERO_CREDIT_MODEL` (`Veo 3.1 - Lite [Lower Priority]`).
    """
    text = await read_settings_pane(client)
    family_id = await read_active_flow_model_family(client)
    banned = [m for m in FLOW_BANNED_VIDEO_MODEL_MARKERS if m in text]

    primary_ok = (FLOW_PRIMARY_VIDEO_MODEL in text) and (
        not family_id or _family_matches_model(FLOW_PRIMARY_VIDEO_MODEL, family_id)
    )
    zero_credit_ok = bool(
        allow_zero_credit_fallback
        and (FLOW_ZERO_CREDIT_MODEL in text)
        and (not family_id or _family_matches_model(FLOW_ZERO_CREDIT_MODEL, family_id))
    )
    active_model = (
        FLOW_PRIMARY_VIDEO_MODEL
        if primary_ok
        else (FLOW_ZERO_CREDIT_MODEL if zero_credit_ok else "")
    )
    ok = bool((primary_ok or zero_credit_ok) and not banned)
    return {
        "model_ok": ok,
        "active_model": active_model,
        "model_family_id": family_id,
        "banned_seen": banned,
        "pane": text.replace("\n", " | ")[:400],
    }


async def prepare_reference_frames(
    client: Any,
    files: list[Path],
    allow_zero_credit_fallback: bool = True,
) -> dict[str, Any]:
    """Clear chips -> upload each file -> attach by name -> verify chip count -> verify allowed model is selected."""
    remaining = await clear_prompt_ingredients(client)
    report: dict[str, Any] = {"cleared": remaining == 0, "attached": [], "failed": []}
    for f in files:
        ok = await upload_file_to_flow(client, Path(f)) and await attach_uploaded_by_name(client, Path(f).name)
        (report["attached"] if ok else report["failed"]).append(Path(f).name)
    report.update(await assert_model_settings(client, allow_zero_credit_fallback=allow_zero_credit_fallback))
    report["ready"] = bool(report["cleared"] and not report["failed"] and report["model_ok"])
    return report


__all__ = [
    "assert_model_settings",
    "read_active_flow_model_family",
    "select_flow_video_model",
    "attach_uploaded_by_name",
    "clear_prompt_ingredients",
    "prepare_reference_frames",
    "upload_file_to_flow",
]
