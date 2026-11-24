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
    Omni 1.2 Flash = Ingredients (3s-15s) & Frames to Video Start+End (3s-10s), 24 credits.
    Veo 3.1 - Lite [Lower Priority] = 4s/6s/8s, 0 credits (Start+End supported). Production uses Omni 1.2 Flash primary with 0-credit Veo Lite fallback.
"""

from __future__ import annotations

import asyncio
import base64
import json
import mimetypes
import re
from pathlib import Path
from typing import Any

from pipeline.config import (
    FLOW_ACTIVE_VIDEO_MODEL,
    FLOW_BANNED_VIDEO_MODEL_MARKERS,
    FLOW_OMNI_ENABLE_MULTI_INGREDIENTS_V83,
    FLOW_OMNI_MAX_INGREDIENTS_V83,
    FLOW_PRIMARY_OMNI_MODEL_KEY,
    FLOW_PRIMARY_VIDEO_MODEL,
    FLOW_RETIRED_VIDEO_MODELS,
    FLOW_VIDEO_MODEL_PROFILES,
    FLOW_ZERO_CREDIT_IMAGE_BATCH_COUNT,
    FLOW_ZERO_CREDIT_IMAGE_FAMILY_ID,
    FLOW_ZERO_CREDIT_IMAGE_MODEL,
    FLOW_ZERO_CREDIT_MODEL,
    FLOW_ZERO_CREDIT_TEXT,
    REENACT_MIN_DHASH_DISTANCE,
)
from pipeline.flow_browser import FLOW_DETECT_ANTIBOT_HALT_JS

ADD_INGREDIENTS_SEL = 'button[aria-label="Add ingredients to the prompt box"], button[aria-label="Add media menu"]'
FRAME_CHIP_SEL = 'flow-prompt-box button[aria-label="Image ingredient"]'
CHIP_SEL = f'flow-prompt-box button[aria-label="Ingredient"], {FRAME_CHIP_SEL}'

_FIND_JS = r"""((sel, text, exact) => {
  const els = [...document.querySelectorAll(sel)].filter(e => e.getClientRects().length);
  const norm = e => (e.innerText || '').replace(/volume_up|arrow_drop_down/g, '').trim();
  const hit = els.reverse().find(e => exact ? norm(e) === text : norm(e).includes(text));
  if (!hit) return null; const r = hit.getBoundingClientRect(); return {x: r.x + r.width / 2, y: r.y + r.height / 2};
})"""


async def trusted_click(client: Any, point: dict[str, float] | tuple[float, float] | None) -> bool:
    if isinstance(point, dict) and "x" in point and "y" in point:
        px, py = float(point["x"]), float(point["y"])
    elif (
        isinstance(point, (tuple, list))
        and len(point) >= 2
        and isinstance(point[0], (int, float))
        and not isinstance(point[0], bool)
        and isinstance(point[1], (int, float))
        and not isinstance(point[1], bool)
    ):
        px, py = float(point[0]), float(point[1])
    else:
        return False
    await client.send("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": max(4.0, px - 14.0), "y": max(4.0, py - 5.0)})
    await asyncio.sleep(0.025)
    await client.send("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": px, "y": py})
    await asyncio.sleep(0.020)
    await client.send("Input.dispatchMouseEvent", {"type": "mousePressed", "x": px, "y": py, "button": "left", "clickCount": 1})
    await asyncio.sleep(0.045)
    await client.send("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": px, "y": py, "button": "left", "clickCount": 1})
    return True


async def find_point(client: Any, selector: str, text: str, exact: bool = False) -> dict[str, float] | None:
    return await client.eval(f"{_FIND_JS}({json.dumps(selector)}, {json.dumps(text)}, {json.dumps(exact)})")


async def press_escape(client: Any) -> None:
    for t in ("keyDown", "keyUp"):
        await client.send("Input.dispatchKeyEvent", {"type": t, "key": "Escape", "code": "Escape", "windowsVirtualKeyCode": 27})


async def dismiss_flow_overlays(client: Any) -> None:
    """Dismisses lingering .cdk-overlay-backdrop and <flow-add-menu-popover-content> popovers using trusted CDP input only."""
    has_open = bool(
        await client.eval(
            'Boolean(document.querySelector(".cdk-overlay-backdrop, flow-add-menu-popover-content"))'
        )
    )
    if not has_open:
        return
    await press_escape(client)
    await asyncio.sleep(0.25)
    still_pop = await client.eval(
        """(() => {
            const trig = document.querySelector("flow-add-menu-popover-content")
                ? document.querySelector('button[aria-label="Add ingredients to the prompt box"]')
                : document.querySelector(".cdk-overlay-backdrop");
            if (!trig || !trig.getClientRects().length) return null;
            const r = trig.getBoundingClientRect();
            return {x: r.x + r.width / 2, y: r.y + r.height / 2};
        })()"""
    )
    if still_pop:
        await trusted_click(client, still_pop)
        await asyncio.sleep(0.25)


async def count_chips(client: Any) -> int:
    return int(await client.eval(f"document.querySelectorAll({json.dumps(CHIP_SEL)}).length") or 0)


async def clear_prompt_ingredients(client: Any, max_rounds: int = 8) -> int:
    """Removes every ingredient chip (active or errored). Returns the remaining count (0 = clean)."""
    await dismiss_flow_overlays(client)
    await client.eval("""(() => {
        const btns = Array.from(document.querySelectorAll('.cdk-overlay-pane button, [role="dialog"] button'));
        const gs = btns.find(b => /^(get started|got it|continue|close|dismiss)$/i.test((b.innerText || '').trim()));
        if (gs) gs.click();
    })()""")
    await asyncio.sleep(0.35)
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
    rem = await count_chips(client)
    if rem > 0:
        clr_pt = await find_point(client, 'flow-prompt-box button[aria-label="Clear prompt"]', "")
        if clr_pt:
            await trusted_click(client, clr_pt)
            await asyncio.sleep(0.6)
        rem = await count_chips(client)
    return rem


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
        pt_add = await find_point(client, ADD_INGREDIENTS_SEL, "")
        if pt_add:
            await trusted_click(client, pt_add)
        else:
            await client.eval(f"document.querySelector({json.dumps(ADD_INGREDIENTS_SEL)})?.click()")
        await asyncio.sleep(1.0)
        up_pt = (
            await find_point(client, "flow-add-menu-popover-content button, .cdk-overlay-pane button, [role=menuitem]", "Upload media")
            or await find_point(client, "flow-add-menu-popover-content button, .cdk-overlay-pane button, [role=menuitem]", "Upload")
        )
        if not await trusted_click(client, up_pt):
            return False

        loop = asyncio.get_running_loop()
        end = loop.time() + timeout_sec
        obj_id: str | None = None
        while loop.time() < end and not obj_id:
            eval_res = await client.send(
                "Runtime.evaluate",
                {
                    "expression": "[...document.querySelectorAll('input[type=\"file\"]')].pop() || null",
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
            await client.send("Page.setInterceptFileChooserDialog", {"enabled": False})
        except Exception:
            pass
        try:
            await client.send("DOM.disable")
        except Exception:
            pass


async def attach_uploaded_by_name(client: Any, file_name: str, wait_sec: float = 30.0) -> bool:
    """Opens Add ingredients -> Uploads (only if popover not already open), waits out Uploading spinners, and clicks file_name."""
    before = await count_chips(client)
    has_pop = bool(await client.eval('Boolean(document.querySelector("flow-add-menu-popover-content"))'))
    if not has_pop:
        await client.eval(f"document.querySelector({json.dumps(ADD_INGREDIENTS_SEL)})?.click()")
        await asyncio.sleep(1.0)

    loop = asyncio.get_running_loop()
    end = loop.time() + wait_sec
    clicked_uploads_tab = False
    while loop.time() < end:
        st = await client.eval("""(() => {
            const pop = document.querySelector("flow-add-menu-popover-content");
            if (!pop) return {pop: false, uploading: false};
            const txt = pop.innerText || "";
            return {pop: true, uploading: txt.includes("Uploading")};
        })()""") or {}
        if not st.get("pop"):
            await client.eval(f"document.querySelector({json.dumps(ADD_INGREDIENTS_SEL)})?.click()")
            await asyncio.sleep(0.9)
            continue
        if st.get("uploading"):
            await asyncio.sleep(1.0)
            continue
        if not clicked_uploads_tab:
            up_pt = await find_point(
                client,
                "flow-add-menu-popover-content [role=tab], flow-add-menu-popover-content mat-list-item, flow-add-menu-popover-content button",
                "Uploads",
            )
            if up_pt:
                await trusted_click(client, up_pt)
                clicked_uploads_tab = True
                await asyncio.sleep(1.0)

        pt = await client.eval(f"""(() => {{
            const pop = document.querySelector("flow-add-menu-popover-content");
            if (!pop) return null;
            const fn = {json.dumps(file_name)};
            const items = Array.from(pop.querySelectorAll('button[role="option"], [role="option"], .asset-item, button'));
            const hit = items.find(e => (e.innerText || "").includes(fn) && e.getBoundingClientRect().width > 20);
            if (!hit) return null;
            const r = hit.getBoundingClientRect();
            return {{x: r.x + r.width / 2, y: r.y + r.height / 2}};
        }})()""")
        if pt:
            await trusted_click(client, pt)
            for _ in range(8):
                await asyncio.sleep(0.45)
                if await count_chips(client) >= before + 1:
                    await dismiss_flow_overlays(client)
                    return True
        await asyncio.sleep(1.2)

    await dismiss_flow_overlays(client)
    return await count_chips(client) >= before + 1


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
    """Strictly verifies that an observed Flow `videoModelFamilyId` matches `model` (rejecting retired model families)."""
    mdl = str(model or "").strip()
    fam = str(family_id or "").strip().lower()
    if not mdl or not fam:
        return False
    if mdl in FLOW_RETIRED_VIDEO_MODELS:
        return False
    if mdl == FLOW_ZERO_CREDIT_MODEL:
        return fam == "veo_3_1_lite_low_priority"
    if mdl in (FLOW_PRIMARY_VIDEO_MODEL, FLOW_ACTIVE_VIDEO_MODEL, "Omni 1.2 Flash"):
        return fam in (
            FLOW_PRIMARY_OMNI_MODEL_KEY,
            "omni_1_2_flash",
            "omni_1_2",
            "gemini_omni_1_2_flash",
            "gemini-omni-1.2-flash",
            "omni",
        )
    expected = str((FLOW_VIDEO_MODEL_PROFILES.get(mdl) or {}).get("model_family_id") or "").strip().lower()
    if expected:
        return fam == expected
    return False


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
    cur_fam = await read_active_flow_model_family(client)
    if cur_fam and _family_matches_model(model, cur_fam):
        await press_escape(client)
        await asyncio.sleep(0.2)
        return True

    for _attempt in range(3):
        has_open_pane = await client.eval(
            "Array.from(document.querySelectorAll('.cdk-overlay-pane')).some(e => (e.innerText || '').includes('Generating will use') && e.getBoundingClientRect().height > 40)"
        )
        if not has_open_pane:
            await press_escape(client)
            await asyncio.sleep(0.45)
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
            if trig:
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
        if dd:
            await trusted_click(client, dd)
            await asyncio.sleep(0.9)

        menu_item_sel = ".cdk-overlay-pane [role=option], .cdk-overlay-pane [role=menuitem], .cdk-overlay-pane mat-option, .cdk-overlay-pane li"
        opt = (
            await find_point(client, menu_item_sel, model, exact=True)
            or await find_point(client, menu_item_sel, model, exact=False)
            or await find_point(client, ".cdk-overlay-pane button", model, exact=True)
            or await find_point(client, ".cdk-overlay-pane button", model, exact=False)
        )
        if opt:
            await trusted_click(client, opt)
            await asyncio.sleep(1.1)
        family_id = await read_active_flow_model_family(client)
        await press_escape(client)
        await asyncio.sleep(0.25)
        if family_id and _family_matches_model(model, family_id):
            return True
    return False


async def assert_model_settings(client: Any, allow_zero_credit_fallback: bool = True) -> dict[str, Any]:
    """
    Verifies active Flow video model in settings pane + `localStorage['flow-prompt-box-settings']`.
    Recognizes `FLOW_PRIMARY_VIDEO_MODEL` (`Omni 1.2 Flash`) and, when `allow_zero_credit_fallback=True`,
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
    *,
    use_frames_mode: bool = False,
    uploaded_cache: set[str] | None = None,
) -> dict[str, Any]:
    """Clear chips -> upload each file -> attach by name (or VIDEO_FRAMES Start/End slots) -> verify allowed model."""
    if use_frames_mode and files:
        start_f = Path(files[0])
        end_f = Path(files[1]) if len(files) >= 2 else None
        slot_res = await upload_start_end_frames_to_flow(
            client,
            start_frame=start_f,
            end_frame=end_f,
            uploaded_cache=uploaded_cache,
            use_frames_mode=True,
        )
        attached: list[str] = []
        failed: list[str] = []
        (attached if slot_res.get("start_attached") else failed).append(start_f.name)
        if end_f is not None:
            (attached if slot_res.get("end_attached") else failed).append(end_f.name)
        report_f: dict[str, Any] = {
            "cleared": True,
            "attached": attached,
            "failed": failed,
            "input_mode": slot_res.get("input_mode", "VIDEO_FRAMES"),
            "chip_count": int(slot_res.get("chip_count") or 0),
        }
        report_f.update(await assert_model_settings(client, allow_zero_credit_fallback=allow_zero_credit_fallback))
        report_f["ready"] = bool(not failed and report_f["model_ok"])
        return report_f

    if use_frames_mode is False:
        await set_flow_video_input_mode(client, use_frames=False)
    remaining = await clear_prompt_ingredients(client)
    report: dict[str, Any] = {
        "cleared": remaining == 0,
        "attached": [],
        "failed": [],
        "input_mode": "VIDEO_REFERENCES",
    }
    for f in files:
        ok = await upload_file_to_flow(client, Path(f)) and await attach_uploaded_by_name(client, Path(f).name)
        (report["attached"] if ok else report["failed"]).append(Path(f).name)
    report.update(await assert_model_settings(client, allow_zero_credit_fallback=allow_zero_credit_fallback))
    report["ready"] = bool(report["cleared"] and not report["failed"] and report["model_ok"])
    return report


async def read_active_flow_input_mode(client: Any) -> str:
    """Reads `mode` (`VIDEO_FRAMES`, `VIDEO_REFERENCES`, `IMAGE`) from `localStorage['flow-prompt-box-settings']`."""
    val = await client.eval(
        """(() => {
            try {
                return JSON.parse(localStorage.getItem("flow-prompt-box-settings") || "{}").mode || "";
            } catch (e) {
                return "";
            }
        })()"""
    )
    return str(val or "").strip()


async def set_flow_video_input_mode(client: Any, use_frames: bool = True) -> bool:
    """
    Switches Google Flow's video input mode cleanly between `Frames` (`VIDEO_FRAMES`, `"Start"` + `"End"` slots)
    and `Ingredients` (`VIDEO_REFERENCES`, `ADD_INGREDIENTS_SEL`), verifying DOM slot rendering and `localStorage`.
    """
    want_ls = "VIDEO_FRAMES" if use_frames else "VIDEO_REFERENCES"
    want_btn = "Frames" if use_frames else "Ingredients"

    async def _mode_matches() -> bool:
        st = await client.eval(
            f"""(() => {{
                let lsMode = "";
                try {{
                    lsMode = JSON.parse(localStorage.getItem("flow-prompt-box-settings") || "{{}}").mode || "";
                }} catch (e) {{}}
                const addIng = Boolean(document.querySelector({json.dumps(ADD_INGREDIENTS_SEL)}));
                const boxBtns = [...document.querySelectorAll("flow-prompt-box button")]
                    .filter(e => e.getClientRects().length)
                    .map(e => ((e.innerText || "").trim() + "|" + (e.getAttribute("aria-label") || "")));
                const hasFramesUi = boxBtns.some(t =>
                    t.startsWith("Start|") || t.startsWith("End|") || t.includes("Swap first and last frames") || t.includes("|Image ingredient")
                );
                return {{lsMode, addIng, hasFramesUi}};
            }})()"""
        ) or {}
        if use_frames:
            return st.get("lsMode") == want_ls and bool(st.get("hasFramesUi"))
        return st.get("lsMode") == want_ls and bool(st.get("addIng"))

    if await _mode_matches():
        return True

    for _attempt in range(3):
        await dismiss_flow_overlays(client)
        await press_escape(client)
        trig = await find_point(client, "flow-prompt-box button.settings-trigger-button, button.settings-trigger-button", "")
        if not trig:
            trig = await client.eval(
                """(() => {
                    const b = document.querySelector('flow-prompt-box button.settings-trigger-button, button.settings-trigger-button');
                    if (!b || !b.getClientRects().length) return null;
                    const r = b.getBoundingClientRect();
                    return {x: r.x + r.width / 2, y: r.y + r.height / 2};
                })()"""
            )
        if trig:
            await trusted_click(client, trig)
            await asyncio.sleep(0.65)
        pane_sel = ".cdk-overlay-pane button, flow-prompt-box-settings button"
        vid_pt = await find_point(client, pane_sel, "Video")
        if vid_pt:
            await trusted_click(client, vid_pt)
            await asyncio.sleep(0.35)
        mode_pt = await find_point(client, pane_sel, want_btn)
        if mode_pt:
            await trusted_click(client, mode_pt)
            await asyncio.sleep(0.55)
        else:
            fb_pt = await client.eval(
                f"""(() => {{
                    const btns = [...document.querySelectorAll('.cdk-overlay-pane button, flow-prompt-box-settings button')];
                    const hit = btns.find(b => b.getClientRects().length && (b.innerText || '').includes({json.dumps(want_btn)}));
                    if (!hit) return null;
                    const r = hit.getBoundingClientRect();
                    return {{x: r.x + r.width / 2, y: r.y + r.height / 2}};
                }})()"""
            )
            if fb_pt:
                await trusted_click(client, fb_pt)
                await asyncio.sleep(0.55)
        await press_escape(client)
        await dismiss_flow_overlays(client)
        if await _mode_matches():
            return True
    return (await read_active_flow_input_mode(client)) == want_ls


async def _find_frame_slot_button_point(client: Any, slot_label: str) -> dict[str, float] | None:
    """Finds the visible `"Start"` or `"End"` slot trigger button inside `flow-prompt-box` in `VIDEO_FRAMES` mode."""
    return await client.eval(
        f"""(() => {{
            const want = {json.dumps(slot_label)};
            const btns = [...document.querySelectorAll('flow-prompt-box button')].filter(e => e.getClientRects().length);
            const hit = btns.find(b => {{
                const txt = (b.innerText || '').replace(/add|image|crop_free/gi, '').trim();
                const raw = (b.innerText || '').trim();
                return raw === want || txt === want || raw.endsWith('\\n' + want) || raw.startsWith(want + '\\n');
            }});
            if (!hit) return null;
            const r = hit.getBoundingClientRect();
            return {{x: r.x + r.width / 2, y: r.y + r.height / 2}};
        }})()"""
    )


async def _inject_bytes_into_open_upload_media(
    client: Any,
    file_path: Path,
    timeout_sec: float = 20.0,
) -> bool:
    """Clicks `'Upload media'` inside an already-open Flow asset/frame popover and injects `file_path` bytes."""
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

    await client.send("Page.enable")
    await client.send("DOM.enable")
    await client.send("Page.setInterceptFileChooserDialog", {"enabled": True})
    try:
        up_pt = await find_point(
            client,
            "flow-add-menu-popover-content button, .cdk-overlay-pane button",
            "Upload media",
        )
        if not await trusted_click(client, up_pt):
            return False

        loop = asyncio.get_running_loop()
        end = loop.time() + timeout_sec
        obj_id: str | None = None
        while loop.time() < end and not obj_id:
            eval_res = await client.send(
                "Runtime.evaluate",
                {
                    "expression": "[...document.querySelectorAll('input[type=\"file\"]')].pop() || null",
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
            await client.send("Page.setInterceptFileChooserDialog", {"enabled": False})
        except Exception:
            pass
        try:
            await client.send("DOM.disable")
        except Exception:
            pass


async def attach_frame_slot_by_name(
    client: Any,
    slot_label: str,
    file_path: Path,
    uploaded_cache: set[str] | None = None,
    wait_sec: float = 26.0,
) -> bool:
    """
    Attaches `file_path` into Google Flow's `VIDEO_FRAMES` `"Start"` or `"End"` slot:
      1. Ensures `VIDEO_FRAMES` mode is active.
      2. Clicks the `"Start"` or `"End"` slot button inside `flow-prompt-box`.
      3. Uploads `file_path` via `"Upload media"` if not yet uploaded in this tab.
      4. Selects `file_path.name` in `"Select a frame image"` (`Uploads` / `Recent`) and clicks `"Add to prompt"`
         when required, verifying `button[aria-label="Image ingredient"]` chip count increments by 1.
    """
    fp = Path(file_path)
    if not fp.exists():
        return False
    cache = uploaded_cache if uploaded_cache is not None else set()
    await set_flow_video_input_mode(client, use_frames=True)
    before = await count_chips(client)

    async def _open_slot_popover() -> bool:
        pt = await _find_frame_slot_button_point(client, slot_label)
        if not pt:
            return False
        await trusted_click(client, pt)
        await asyncio.sleep(0.85)
        return bool(
            await client.eval(
                "Boolean(document.querySelector('flow-add-menu-popover-content, .cdk-overlay-pane'))"
            )
        )

    if fp.name not in cache:
        await dismiss_flow_overlays(client)
        await press_escape(client)
        if await _open_slot_popover():
            if await _inject_bytes_into_open_upload_media(client, fp):
                cache.add(fp.name)
                for _ in range(16):
                    await asyncio.sleep(0.55)
                    if await count_chips(client) >= before + 1:
                        await dismiss_flow_overlays(client)
                        return True
                    uploading = await client.eval(
                        """(() => {
                            const p = document.querySelector('flow-add-menu-popover-content, .cdk-overlay-pane');
                            return p ? (p.innerText || '').includes('Uploading') : false;
                        })()"""
                    )
                    if not uploading:
                        break

    if await count_chips(client) >= before + 1:
        await dismiss_flow_overlays(client)
        return True

    loop = asyncio.get_running_loop()
    end_t = loop.time() + wait_sec
    clicked_uploads_tab = False
    while loop.time() < end_t:
        st = await client.eval(
            """(() => {
                const pop = document.querySelector('flow-add-menu-popover-content, .cdk-overlay-pane');
                if (!pop) return {pop: false, uploading: false};
                const txt = pop.innerText || '';
                return {pop: true, uploading: txt.includes('Uploading')};
            })()"""
        ) or {}
        if not st.get("pop"):
            if await count_chips(client) >= before + 1:
                return True
            if not await _open_slot_popover():
                await asyncio.sleep(0.6)
                continue
        if st.get("uploading"):
            await asyncio.sleep(0.8)
            continue
        if not clicked_uploads_tab:
            up_tab = await find_point(
                client,
                "flow-add-menu-popover-content [role=tab], flow-add-menu-popover-content button, .cdk-overlay-pane [role=tab], .cdk-overlay-pane button",
                "Uploads",
            )
            if up_tab:
                await trusted_click(client, up_tab)
                clicked_uploads_tab = True
                await asyncio.sleep(0.8)

        tile_pt = await client.eval(
            f"""(() => {{
                const pop = document.querySelector('flow-add-menu-popover-content, .cdk-overlay-pane');
                if (!pop) return null;
                const fn = {json.dumps(fp.name)};
                const items = Array.from(pop.querySelectorAll('button[role="option"], [role="option"], .asset-item, button, [role="gridcell"], div'));
                const hits = items.filter(e => {{
                    const r = e.getBoundingClientRect();
                    if (r.width < 24 || r.height < 24 || r.width > 520 || r.height > 520) return false;
                    const t = (e.innerText || '') + ' ' + (e.getAttribute('aria-label') || '') + ' ' + (e.getAttribute('title') || '');
                    return t.includes(fn);
                }});
                const hit = hits.sort((a, b) => (a.getBoundingClientRect().width * a.getBoundingClientRect().height) - (b.getBoundingClientRect().width * b.getBoundingClientRect().height))[0];
                if (!hit) return null;
                const r = hit.getBoundingClientRect();
                return {{x: r.x + r.width / 2, y: r.y + r.height / 2}};
            }})()"""
        )
        if tile_pt:
            await trusted_click(client, tile_pt)
            await asyncio.sleep(0.55)
            if await count_chips(client) >= before + 1:
                await dismiss_flow_overlays(client)
                return True
            add_pt = await client.eval(
                """(() => {
                    const pop = document.querySelector('flow-add-menu-popover-content, .cdk-overlay-pane');
                    if (!pop) return null;
                    const btns = Array.from(pop.querySelectorAll('button')).filter(b => b.getClientRects().length && !b.disabled);
                    const hit = btns.find(b => (b.innerText || '').includes('Add to prompt'));
                    if (!hit) return null;
                    const r = hit.getBoundingClientRect();
                    return {x: r.x + r.width / 2, y: r.y + r.height / 2};
                })()"""
            )
            if add_pt:
                await trusted_click(client, add_pt)
            for _ in range(8):
                await asyncio.sleep(0.45)
                if await count_chips(client) >= before + 1:
                    await dismiss_flow_overlays(client)
                    return True
        await asyncio.sleep(0.9)

    await dismiss_flow_overlays(client)
    return await count_chips(client) >= before + 1


async def upload_start_end_frames_to_flow(
    client: Any,
    start_frame: Path,
    end_frame: Path | None = None,
    uploaded_cache: set[str] | None = None,
    use_frames_mode: bool = True,
) -> dict[str, Any]:
    """
    Uploads and attaches a Start Frame and optional End Frame into Google Flow's prompt box:
      - `use_frames_mode=True` (default): switches to `VIDEO_FRAMES` (`Frames` mode), attaches `start_frame` into
        the `"Start"` slot and `end_frame` into the `"End"` slot (`button[aria-label="Image ingredient"]` + `"Add to prompt"`).
      - `use_frames_mode=False`: switches to `VIDEO_REFERENCES` (`Ingredients` mode) for multi-panel reference sheets.
    Returns `{"start_attached": bool, "end_attached": bool, "chip_count": int, "input_mode": str}`.
    """
    cache = uploaded_cache if uploaded_cache is not None else set()
    if use_frames_mode:
        await set_flow_video_input_mode(client, use_frames=True)
        await clear_prompt_ingredients(client)
        start_ok = await attach_frame_slot_by_name(
            client,
            slot_label="Start",
            file_path=Path(start_frame),
            uploaded_cache=cache,
        )
        end_ok = False
        if (
            start_ok
            and end_frame
            and Path(end_frame).exists()
            and Path(end_frame).resolve() != Path(start_frame).resolve()
        ):
            end_ok = await attach_frame_slot_by_name(
                client,
                slot_label="End",
                file_path=Path(end_frame),
                uploaded_cache=cache,
            )
        chips = await count_chips(client)
        return {
            "start_attached": bool(start_ok),
            "end_attached": bool(end_ok),
            "chip_count": int(chips),
            "input_mode": "VIDEO_FRAMES",
        }

    await set_flow_video_input_mode(client, use_frames=False)
    await clear_prompt_ingredients(client)

    async def _attach_one(frame_p: Path, target_chip_min: int) -> bool:
        if not frame_p or not Path(frame_p).exists():
            return False
        fp = Path(frame_p)
        ready = False
        if fp.name not in cache:
            if await upload_file_to_flow(client, fp):
                cache.add(fp.name)
                for _ in range(8):
                    await asyncio.sleep(0.5)
                    if await count_chips(client) >= target_chip_min:
                        ready = True
                        break
        if not ready:
            ready = await attach_uploaded_by_name(client, fp.name, wait_sec=20.0)
            if not ready and await count_chips(client) >= target_chip_min:
                ready = True
            if not ready:
                await press_escape(client)
                await asyncio.sleep(1.0)
                ready = await attach_uploaded_by_name(client, fp.name, wait_sec=15.0)
        return bool(ready)

    start_ok = await _attach_one(Path(start_frame), 1)
    end_ok = False
    if start_ok and end_frame and Path(end_frame).exists() and Path(end_frame).name != Path(start_frame).name:
        end_ok = await _attach_one(Path(end_frame), 2)
    chips = await count_chips(client)
    return {
        "start_attached": bool(start_ok),
        "end_attached": bool(end_ok),
        "chip_count": int(chips),
        "input_mode": "VIDEO_REFERENCES",
    }


def close_gemini_tabs(cdp_port: int = 9222, owner_id: str | None = None) -> list[str]:
    """
    Closes pipeline-leased `gemini.google.com` page tabs owned by `owner_id` (or the current process)
    on `cdp_port`, while strictly preserving unleased personal user tabs, sibling-leased tabs,
    YouTube Studio, and Google Flow tabs.
    """
    import urllib.request

    from pipeline.cdp_tab_lease import get_tab_lease, is_tab_leased_by_other, release_and_close_leased_tab

    closed: list[str] = []
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{int(cdp_port)}/json/list", timeout=4) as resp:
            tabs = json.loads(resp.read().decode("utf-8"))
    except Exception:
        return closed

    for t in tabs:
        if t.get("type") != "page":
            continue
        url = str(t.get("url") or "").lower()
        tid = str(t.get("id") or "")
        if not tid or "gemini.google.com" not in url:
            continue
        if is_tab_leased_by_other(tid, owner_id=owner_id, cdp_port=cdp_port):
            continue
        if get_tab_lease(tid, cdp_port=cdp_port) is not None:
            if release_and_close_leased_tab(tid, owner_id=owner_id, cdp_port=cdp_port):
                closed.append(tid)
    return closed


async def configure_flow_zero_credit_image_mode(
    client: Any,
    aspect: str = "9:16",
    batch_count: int = FLOW_ZERO_CREDIT_IMAGE_BATCH_COUNT,
    image_model: str | None = None,
) -> dict[str, Any]:
    """
    Configures Google Flow into `Image` mode (`Nano Banana 2.1` / `Nano Banana Pro` / `Nano Banana 2 Lite`),
    `aspect` (`9:16` PORTRAIT or `16:9` LANDSCAPE), and the requested `0-credit` batch count (`x1` first-pass / `x2` retry;
    never exceeding `batch_count`), strictly verifying `mode == 'IMAGE'`, `aspectRatio`, `outputCount <= target_batch`,
    and `Generating will use 0 credits`, while forbidding paid credit dialogs.
    """
    target_model = str(image_model or FLOW_ZERO_CREDIT_IMAGE_MODEL).strip() or FLOW_ZERO_CREDIT_IMAGE_MODEL
    target_batch = max(1, min(4, int(batch_count or FLOW_ZERO_CREDIT_IMAGE_BATCH_COUNT)))
    target_aspect = "16:9" if str(aspect).strip() == "16:9" else "9:16"
    expected_ls_aspect = "LANDSCAPE" if target_aspect == "16:9" else "PORTRAIT"
    await client.eval("window.__bci_flow_forbid_credit_approve = true;")
    await client.eval("""(() => {
        const b = document.querySelector('.agent-panel-header button[aria-label="Close"]');
        if (b) b.click();
        const chip = document.querySelector('button.agent-mode-chip[aria-pressed="true"]');
        if (chip) chip.click();
    })()""")
    await asyncio.sleep(0.35)

    await dismiss_flow_overlays(client)
    await client.eval("""(() => {
        const btns = Array.from(document.querySelectorAll('.cdk-overlay-pane button, [role="dialog"] button'));
        const gs = btns.find(b => /^(get started|got it|continue|close|dismiss)$/i.test((b.innerText || '').trim()));
        if (gs) gs.click();
    })()""")
    await asyncio.sleep(0.35)
    await press_escape(client)
    st_pt = await find_point(client, "button.settings-trigger-button", "")
    if st_pt:
        await trusted_click(client, st_pt)
    else:
        await client.eval("""(() => {
            const st = document.querySelector('button.settings-trigger-button');
            if (st) st.click();
        })()""")
    await asyncio.sleep(0.55)

    img_pt = await find_point(client, "flow-prompt-box-settings button, .cdk-overlay-pane button", "Image", exact=False)
    if img_pt:
        await trusted_click(client, img_pt)
    else:
        await client.eval("""(() => {
            const btns = Array.from(document.querySelectorAll('flow-prompt-box-settings button, .cdk-overlay-pane button'));
            const imgBtn = btns.find(b => (b.innerText || '').includes('Image'));
            if (imgBtn) imgBtn.click();
        })()""")
    await asyncio.sleep(0.45)

    # Ensure the requested 0-credit Flow image model is selected in the dropdown
    cur_pane_txt = str(
        await client.eval("""(() => Array.from(document.querySelectorAll('flow-prompt-box-settings, .cdk-overlay-pane')).map(e => e.innerText || '').join('\\n'))()""")
        or ""
    )
    if target_model not in cur_pane_txt:
        dd_sel = ".cdk-overlay-pane [aria-haspopup], flow-prompt-box-settings [aria-haspopup]"
        dd = await find_point(client, dd_sel, "")
        if dd:
            await trusted_click(client, dd)
            await asyncio.sleep(0.55)
            opt = await find_point(
                client,
                ".cdk-overlay-pane [role=option], .cdk-overlay-pane [role=menuitem], .cdk-overlay-pane button",
                target_model,
                exact=False,
            )
            if opt:
                await trusted_click(client, opt)
                await asyncio.sleep(0.55)
            else:
                await client.eval(f"""(() => {{
                    const opts = Array.from(document.querySelectorAll('.cdk-overlay-pane [role=option], .cdk-overlay-pane [role=menuitem], .cdk-overlay-pane button'));
                    const hit = opts.find(el => (el.innerText || '').includes({json.dumps(target_model)}));
                    if (hit) hit.click();
                }})()""")
                await asyncio.sleep(0.55)

    chosen_batch = target_batch
    last_ls_count: int | None = None
    zero_credit_ok = False
    pane_text = ""
    asp_labels = ("Landscape", "16:9", "crop_16_9") if target_aspect == "16:9" else ("Portrait", "9:16", "crop_9_16")
    for cand_n in sorted({target_batch, 4, 2, 1}, reverse=True):
        if cand_n > target_batch:
            continue
        for asp_lbl in asp_labels:
            asp_pt = await find_point(client, "flow-prompt-box-settings button, .cdk-overlay-pane button", asp_lbl, exact=False)
            if asp_pt:
                await trusted_click(client, asp_pt)
                await asyncio.sleep(0.25)
                break
        cnt_pt = await find_point(client, "flow-prompt-box-settings button, .cdk-overlay-pane button", f"x{cand_n}", exact=True)
        if cnt_pt:
            await trusted_click(client, cnt_pt)
            await asyncio.sleep(0.25)

        state = await client.eval(f"""(() => {{
            const btns = Array.from(document.querySelectorAll('flow-prompt-box-settings button, .cdk-overlay-pane button'));
            const aspKey = {json.dumps(target_aspect)};
            const bAsp = btns.find(b => {{
                const t = (b.innerText || '');
                return t.includes(aspKey) || (aspKey === '16:9' && (t.includes('Landscape') || t.includes('crop_16_9'))) || (aspKey === '9:16' && (t.includes('Portrait') || t.includes('crop_9_16')));
            }});
            if (bAsp && !bAsp.disabled) bAsp.click();
            const bCnt = btns.find(b => (b.innerText || '').trim() === {json.dumps(f"x{cand_n}")});
            if (bCnt && !bCnt.disabled) bCnt.click();
            const txt = Array.from(document.querySelectorAll('flow-prompt-box-settings, .cdk-overlay-pane')).map(e => e.innerText || '').join('\\n');
            const warn = Boolean(document.querySelector('button.prompt-warning-button'));
            return {{ txt, warn, clicked: Boolean(bCnt && !bCnt.disabled) }};
        }})()""") or {}
        await asyncio.sleep(0.35)
        check = await client.eval("""(() => ({
            txt: Array.from(document.querySelectorAll('flow-prompt-box-settings, .cdk-overlay-pane')).map(e => e.innerText || '').join('\\n'),
            warn: Boolean(document.querySelector('button.prompt-warning-button')),
            ls: JSON.parse(localStorage.getItem('flow-prompt-box-settings') || '{}')
        }))()""") or {}
        pane_text = str(check.get("txt") or state.get("txt") or "")
        warn_now = bool(check.get("warn"))
        ls_now = check.get("ls") or {}
        pane_lower = pane_text.lower()
        explicit_paid = ("generating will use" in pane_lower) and (FLOW_ZERO_CREDIT_TEXT.lower() not in pane_lower)
        zero_text_ok = FLOW_ZERO_CREDIT_TEXT in pane_text
        family_ok = (target_model == FLOW_ZERO_CREDIT_IMAGE_MODEL) and (str(ls_now.get("imageModelFamilyId") or "") == FLOW_ZERO_CREDIT_IMAGE_FAMILY_ID)
        ls_aspect_now = str(ls_now.get("aspectRatio") or "").upper()
        aspect_ok = (ls_aspect_now == expected_ls_aspect) or (not ls_aspect_now)
        ls_count = int(ls_now.get("outputCount") or cand_n)
        last_ls_count = ls_count
        count_ok = 1 <= ls_count <= target_batch
        if (
            (zero_text_ok or family_ok)
            and not explicit_paid
            and not warn_now
            and str(ls_now.get("mode") or "") == "IMAGE"
            and aspect_ok
            and count_ok
        ):
            chosen_batch = ls_count
            zero_credit_ok = True
            break

    await client.eval("""(() => {
        const bd = document.querySelector('.cdk-overlay-backdrop');
        if (bd) bd.click();
    })()""")
    await asyncio.sleep(0.3)

    if not zero_credit_ok:
        raise RuntimeError(
            f"Failed to verify 0-credit Google Flow Image mode ({target_model} / {target_aspect} / {expected_ls_aspect} / target_batch=x{target_batch}, outputCount={last_ls_count}, pane={pane_text[:240]!r})"
        )

    summary = await client.eval("""(() => (document.querySelector('button.settings-trigger-button')?.innerText || '').trim())()""") or ""
    return {
        "mode": "IMAGE",
        "aspect": target_aspect,
        "image_model": target_model,
        "output_count": chosen_batch,
        "zero_credit_verified": True,
        "settings_summary": summary,
    }


async def generate_flow_image_batch(
    client: Any,
    prompt: str,
    out_path: Path,
    conditioning_paths: list[Path] | None = None,
    batch_count: int = FLOW_ZERO_CREDIT_IMAGE_BATCH_COUNT,
    aspect: str = "9:16",
    uploaded_cache: set[str] | None = None,
    seen_img_srcs: set[str] | None = None,
    spec: dict[str, Any] | None = None,
    source_dhashes: list[int] | None = None,
    project_dir: Path | None = None,
    timeout_sec: float = 95.0,
    save_all_candidates_dir: Path | None = None,
    image_model: str | None = None,
) -> dict[str, Any]:
    """
    Generates `x1` first-pass / `x2` retry (`FLOW_ZERO_CREDIT_IMAGE_BATCH_COUNT`) `0-credit` candidate images in a single
    Google Flow `Image` submission (`Nano Banana 2.1`), evaluates every candidate against `Q1..Q7`
    (`inspect_single_reference_image`) and `RQ2 dHash >= REENACT_MIN_DHASH_DISTANCE`, saves the #1
    highest-scoring candidate to `out_path` (`1080x1920` or `1920x1080`), and registers
    `flow_image_generation` provenance.
    """
    import hashlib
    import tempfile
    import time

    import cv2
    import numpy as np

    cache = uploaded_cache if uploaded_cache is not None else set()
    seen_srcs = seen_img_srcs if seen_img_srcs is not None else set()

    await clear_prompt_ingredients(client)
    attached_refs: list[str] = []
    for cond_p in (conditioning_paths or [])[:2]:
        cp = Path(cond_p)
        if not cp.exists():
            continue
        sha6 = hashlib.sha1(cp.read_bytes()).hexdigest()[:6]
        staged_jpg = Path(tempfile.gettempdir()) / f"fimg_{sha6}.jpg"
        if not staged_jpg.exists():
            bgr = cv2.imread(str(cp))
            if bgr is not None:
                h0, w0 = bgr.shape[:2]
                if max(h0, w0) > 1280:
                    sc = 1280.0 / float(max(h0, w0))
                    bgr = cv2.resize(bgr, (max(1, int(round(w0 * sc))), max(1, int(round(h0 * sc)))), interpolation=cv2.INTER_AREA)
                cv2.imwrite(str(staged_jpg), bgr, [cv2.IMWRITE_JPEG_QUALITY, 92])
            else:
                staged_jpg = cp
        target_min = len(attached_refs) + 1
        ok_att = False
        if staged_jpg.name not in cache:
            if await upload_file_to_flow(client, staged_jpg):
                cache.add(staged_jpg.name)
                for _ in range(8):
                    await asyncio.sleep(0.45)
                    if await count_chips(client) >= target_min:
                        ok_att = True
                        break
        if not ok_att:
            ok_att = await attach_uploaded_by_name(client, staged_jpg.name, wait_sec=18.0)
        if ok_att:
            attached_refs.append(cp.name)

    # Configure & verify Image mode + 9:16 + xN + 0-credit lock AFTER attaching any ingredients
    post_chip_cfg = await configure_flow_zero_credit_image_mode(
        client,
        aspect=aspect,
        batch_count=batch_count,
        image_model=image_model,
    )
    active_image_model = str(post_chip_cfg.get("image_model") or image_model or FLOW_ZERO_CREDIT_IMAGE_MODEL)
    eff_batch = int(post_chip_cfg.get("output_count") or batch_count)

    # Drain any in-flight `flow-pending-tile` from a prior prompt/retry so late images never shift into this slot
    for _ in range(30):
        rem_pending = int(await client.eval("document.querySelectorAll('flow-pending-tile').length") or 0)
        if rem_pending == 0:
            break
        await asyncio.sleep(1.5)
    await asyncio.sleep(0.8)

    # CRITICAL: await_promise=True so raw_existing actually resolves the Promise (never leaving seen_srcs empty!),
    # and snapshot initial error-tile count AFTER conditioning uploads so newly failed tiles fail fast.
    pre_snap = await client.eval(
        """(async () => {
            const scrollers = Array.from(document.querySelectorAll('*')).filter(el => el.scrollHeight > el.clientHeight + 80);
            if (scrollers.length) {
                for (const s of scrollers) { try { s.scrollTop = 0; } catch (e) {} }
                await new Promise(r => setTimeout(r, 850));
            }
            const urls = Array.from(document.querySelectorAll('img'))
                .filter(im => {
                    if (im.closest('.cdk-overlay-pane, flow-add-menu-popover-content, flow-prompt-box')) return false;
                    const u = im.currentSrc || im.src || '';
                    return u.includes('flow-content.google/image/') || (u.includes('flow.google.com/asb/') && Boolean(im.closest('flow-image-tile')));
                })
                .map(im => im.currentSrc || im.src);
            const errCount = document.querySelectorAll('flow-error-tile').length;
            const failedTileCount = Array.from(document.querySelectorAll('flow-image-tile')).filter(t => (t.innerText || '').includes('Failed')).length;
            return { urls, errCount, failedTileCount };
        })()""",
        await_promise=True,
    ) or {}
    existing_urls = pre_snap.get("urls") if isinstance(pre_snap, dict) and isinstance(pre_snap.get("urls"), list) else []
    initial_err_tiles = int(pre_snap.get("errCount") or 0) if isinstance(pre_snap, dict) else 0
    initial_failed_tiles = int(pre_snap.get("failedTileCount") or 0) if isinstance(pre_snap, dict) else 0
    for u in existing_urls:
        seen_srcs.add(str(u))

    clean_prompt = " ".join(str(prompt or "").split())
    await client.eval("""(() => {
        const ed = document.querySelector('.ProseMirror[contenteditable="true"]');
        if (!ed) return false;
        ed.focus();
        document.execCommand('selectAll', false, null);
        document.execCommand('delete', false, null);
        return true;
    })()""")
    await client.send("Input.insertText", {"text": clean_prompt})
    await asyncio.sleep(0.35)
    await client.eval(f"""(() => {{
        const ed = document.querySelector('.ProseMirror[contenteditable="true"]');
        if (!ed) return false;
        if ((ed.innerText || '').trim().length < 12) {{
            ed.focus();
            document.execCommand('selectAll', false, null);
            document.execCommand('insertText', false, {json.dumps(clean_prompt)});
        }}
        ed.dispatchEvent(new InputEvent('input', {{ bubbles: true, cancelable: true, inputType: 'insertText' }}));
        ed.dispatchEvent(new Event('change', {{ bubbles: true }}));
        return true;
    }})()""")
    await asyncio.sleep(0.35)

    warn_pre = bool(await client.eval("Boolean(document.querySelector('button.prompt-warning-button'))"))
    if warn_pre:
        raise RuntimeError("Refusing to submit Flow Image prompt: prompt-warning-button detected (non-zero credit risk)")

    sub_res = await client.eval("""(() => {
        const fg = document.querySelector('flow-generate-icon-button');
        const b = document.querySelector('button.generate-icon-button, button[aria-label="Start generation"], flow-generate-icon-button button');
        const r = b ? b.getBoundingClientRect() : null;
        const fn = typeof getEventListeners === 'function' && fg ? getEventListeners(fg)?.generate?.[0]?.listener : null;
        if (fn) {
            fn({isTrusted: true});
            return { action: 'listener_invoked', x: r ? r.x + r.width / 2 : 0, y: r ? r.y + r.height / 2 : 0, disabled: Boolean(b && b.disabled) };
        }
        if (b && !b.disabled && r && r.width > 0) {
            return { action: 'needs_mouse_click', x: r.x + r.width / 2, y: r.y + r.height / 2, disabled: false };
        }
        return { action: 'not_ready', x: 0, y: 0, disabled: true };
    })()""") or {}
    if sub_res.get("action") == "not_ready":
        return {"ok": False, "reason": "submit_button_unavailable"}

    if sub_res.get("action") == "needs_mouse_click" and sub_res.get("x", 0) > 0:
        ix, iy = int(sub_res["x"]), int(sub_res["y"])
        await client.send("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": ix, "y": iy})
        await client.send("Input.dispatchMouseEvent", {"type": "mousePressed", "x": ix, "y": iy, "button": "left", "clickCount": 1})
        await asyncio.sleep(0.08)
        await client.send("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": ix, "y": iy, "button": "left", "clickCount": 1})

    # Confirm ProseMirror cleared AND zero pending tiles started before ever clicking a fallback second time
    await asyncio.sleep(2.0)
    post_submit_state = await client.eval("""(() => {
        const ed = document.querySelector('.ProseMirror[contenteditable="true"]');
        const pending = document.querySelectorAll('flow-pending-tile').length;
        return { edLen: ed ? (ed.innerText || '').trim().length : 0, pending };
    })()""") or {}
    if (
        int(post_submit_state.get("edLen") or 0) > 0
        and int(post_submit_state.get("pending") or 0) == 0
        and sub_res.get("x", 0) > 0
    ):
        ix, iy = int(sub_res["x"]), int(sub_res["y"])
        await client.send("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": ix, "y": iy})
        await client.send("Input.dispatchMouseEvent", {"type": "mousePressed", "x": ix, "y": iy, "button": "left", "clickCount": 1})
        await asyncio.sleep(0.08)
        await client.send("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": ix, "y": iy, "button": "left", "clickCount": 1})

    t0 = time.monotonic()
    new_urls: list[str] = []
    saw_pending = False
    usage_limit_hit = False
    unusual_activity_hit = False
    newest_err_text = ""
    _unusual_activity_markers = (
        "unusual activity",
        "wait a few moments",
        "browser extensions that modify",
        "captcha",
        "verify you are human",
        "recaptcha",
        "turnstile",
        "are you a robot",
        "human verification",
    )
    _usage_limit_markers = ("usage limit", "try again later", "rate limit", "quota")
    seen_base_list = [re.sub(r"=s\d+[^/?#]*$", "", str(u).split("?")[0]) for u in seen_srcs if str(u)]
    while time.monotonic() - t0 < timeout_sec:
        await asyncio.sleep(2.5)
        poll = await client.eval(f"""(() => {{
            const scrollers = Array.from(document.querySelectorAll('*')).filter(el => el.scrollHeight > el.clientHeight + 80);
            for (const s of scrollers) {{ try {{ s.scrollTop = 0; }} catch (e) {{}} }}
            const seen = new Set({json.dumps(list(seen_srcs))});
            const seenBase = new Set({json.dumps(seen_base_list)});
            const pending = document.querySelectorAll('flow-pending-tile').length;
            const errNodeList = Array.from(document.querySelectorAll('flow-error-tile'));
            const errTiles = errNodeList.length;
            const failedTiles = Array.from(document.querySelectorAll('flow-image-tile')).filter(t => (t.innerText || '').includes('Failed'));
            const topErrText = (errNodeList[0]?.innerText || failedTiles[0]?.innerText || '').trim().slice(0, 260);
            const detectHalt = {FLOW_DETECT_ANTIBOT_HALT_JS};
            const haltInfo = detectHalt([topErrText]);
            const haltWarn = Boolean(haltInfo && haltInfo.haltWarn);
            const haltText = String((haltInfo && haltInfo.haltText) || '');
            const items = [];
            for (const im of document.querySelectorAll('img')) {{
                if (im.closest('.cdk-overlay-pane, flow-add-menu-popover-content, flow-prompt-box')) continue;
                const u = im.currentSrc || im.src || '';
                const b = u.split('?')[0].replace(/=s\\d+[^/?#]*$/, '');
                const isLegacy = im.naturalWidth >= 400 && u.includes('flow-content.google/image/');
                const isAsbTile = im.naturalWidth >= 200 && u.includes('flow.google.com/asb/') && Boolean(im.closest('flow-image-tile'));
                if ((isLegacy || isAsbTile) && !seen.has(u) && !seenBase.has(b)) {{
                    const r = im.getBoundingClientRect();
                    items.push({{ u, top: r.top, left: r.left }});
                }}
            }}
            items.sort((a, b) => (Math.abs(a.top - b.top) > 12 ? a.top - b.top : a.left - b.left));
            const urls = [];
            for (const it of items) {{
                if (!urls.includes(it.u)) urls.push(it.u);
            }}
            return {{ urls, pending, errTiles, failedTileCount: failedTiles.length, topErrText, haltWarn, haltText }};
        }})()""") or {}
        new_urls = [str(u) for u in (poll.get("urls") or []) if str(u)]
        pending_cnt = int(poll.get("pending") or 0)
        err_now = int(poll.get("errTiles") or 0)
        failed_now = int(poll.get("failedTileCount") or 0)
        top_err_txt = str(poll.get("topErrText") or "")
        if bool(poll.get("haltWarn")) and not new_urls:
            newest_err_text = str(poll.get("haltText") or top_err_txt or "flow_antibot_halt")
            unusual_activity_hit = True
            break
        if pending_cnt > 0:
            saw_pending = True
        elapsed_poll = time.monotonic() - t0
        new_failure_detected = (err_now > initial_err_tiles) or (failed_now > initial_failed_tiles)
        low_err = top_err_txt.lower()
        if new_failure_detected and not new_urls and any(m in low_err for m in _unusual_activity_markers):
            newest_err_text = top_err_txt
            unusual_activity_hit = True
            break
        if new_failure_detected and pending_cnt == 0 and not new_urls:
            newest_err_text = top_err_txt
            if any(m in low_err for m in _unusual_activity_markers):
                unusual_activity_hit = True
            elif any(m in low_err for m in _usage_limit_markers):
                usage_limit_hit = True
            break
        if len(new_urls) >= eff_batch and pending_cnt == 0 and (saw_pending or elapsed_poll >= 8.5):
            break
        if len(new_urls) >= eff_batch and elapsed_poll >= 45.0:
            break
        if len(new_urls) >= 1 and pending_cnt == 0 and elapsed_poll >= 11.0:
            break
        if (err_now > 0 or failed_now > 0) and pending_cnt == 0 and not new_urls and elapsed_poll >= 12.0:
            newest_err_text = top_err_txt
            if any(m in low_err for m in _unusual_activity_markers):
                unusual_activity_hit = True
            elif any(m in low_err for m in _usage_limit_markers):
                usage_limit_hit = True
            break

    if unusual_activity_hit and not new_urls:
        warn_shot_str = ""
        if project_dir is not None and hasattr(client, "send"):
            try:
                ss_dir = Path(project_dir) / "03_visuals" / "flow_screenshots"
                ss_dir.mkdir(parents=True, exist_ok=True)
                warn_png = ss_dir / "flow_warning_capture_image.png"
                ss_res = await client.send("Page.captureScreenshot", {"format": "png"})
                if isinstance(ss_res, dict) and ss_res.get("data"):
                    warn_png.write_bytes(base64.b64decode(ss_res["data"]))
                    warn_shot_str = str(warn_png)
            except Exception:
                pass
        return {
            "ok": False,
            "reason": "flow_unusual_activity_blocked",
            "image_model": active_image_model,
            "error_text": newest_err_text,
            "warning_screenshot": warn_shot_str,
        }

    if usage_limit_hit and not new_urls:
        return {
            "ok": False,
            "reason": "flow_usage_limit_reached",
            "image_model": active_image_model,
            "error_text": newest_err_text,
        }

    for u in new_urls:
        seen_srcs.add(u)
    new_urls = new_urls[:eff_batch]

    if not new_urls:
        if newest_err_text:
            return {
                "ok": False,
                "reason": "flow_generation_error",
                "image_model": active_image_model,
                "error_text": newest_err_text,
            }
        return {"ok": False, "reason": "no_flow_images_rendered", "image_model": active_image_model}

    target_wh = (1920, 1080) if str(aspect).strip() == "16:9" else (1080, 1920)
    out_p = Path(out_path)
    out_p.parent.mkdir(parents=True, exist_ok=True)

    from pipeline.ref_qa import inspect_single_reference_image, register_reference_image

    def _dhash_64(bgr_arr: np.ndarray) -> int:
        gray = cv2.cvtColor(bgr_arr, cv2.COLOR_BGR2GRAY)
        resized = cv2.resize(gray, (9, 8), interpolation=cv2.INTER_AREA)
        diff = resized[:, 1:] > resized[:, :-1]
        val = 0
        for bit in diff.flatten():
            val = (val << 1) | int(bool(bit))
        return val

    import urllib.request

    sibling_or_cond_dhashes: list[int] = []
    seen_guard_paths: set[Path] = set()
    extra_ref_guards: list[Path] = []
    if project_dir is not None:
        proj_ref_dir = Path(project_dir) / "03_visuals" / "reference_images"
        if proj_ref_dir.is_dir() and proj_ref_dir.resolve() != out_p.parent.resolve():
            extra_ref_guards = sorted(proj_ref_dir.glob("*.png"))
    for gp in (
        list(conditioning_paths or [])
        + (sorted(out_p.parent.glob("*.png")) if out_p.parent.is_dir() else [])
        + extra_ref_guards
    ):
        gp_p = Path(gp)
        if not gp_p.is_file() or gp_p.name == out_p.name or gp_p in seen_guard_paths:
            continue
        seen_guard_paths.add(gp_p)
        g_bgr = cv2.imread(str(gp_p), cv2.IMREAD_COLOR)
        if g_bgr is not None and g_bgr.size > 0:
            sibling_or_cond_dhashes.append(_dhash_64(g_bgr))

    frame_tree = None
    candidates: list[dict[str, Any]] = []
    for idx, img_url in enumerate(new_urls):
        raw_bytes: bytes | None = None
        is_asb_url = "flow.google.com/asb/" in str(img_url)
        fetch_url = re.sub(r"=s\d+[^/?#]*$", "=s0", str(img_url)) if is_asb_url else str(img_url)
        # Tier 1: Direct Python fetch of pre-signed flow-content.google CDN URL (zero CORS restriction)
        if not is_asb_url:
            try:
                def _dl_signed(u: str = fetch_url) -> bytes:
                    req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})
                    with urllib.request.urlopen(req, timeout=20) as resp:
                        return resp.read()

                cand_b = await asyncio.to_thread(_dl_signed)
                if cand_b and len(cand_b) > 8_000:
                    raw_bytes = cand_b
            except Exception:
                raw_bytes = None

        # Tier 2: In-page fetch (credentials: include for same-origin /asb/=s0; no credentials for CORS CDN)
        if not raw_bytes:
            fetch_opts = "{ credentials: 'include' }" if is_asb_url else "{}"
            b64_str = await client.eval(
                f"""(async () => {{
                    try {{
                        const r = await fetch({json.dumps(fetch_url)}, {fetch_opts});
                        if (!r.ok) return '';
                        const buf = await r.arrayBuffer();
                        const bytes = new Uint8Array(buf);
                        let bin = '';
                        const chunk = 0x8000;
                        for (let i = 0; i < bytes.length; i += chunk) {{
                            bin += String.fromCharCode.apply(null, bytes.subarray(i, i + chunk));
                        }}
                        return btoa(bin);
                    }} catch (e) {{
                        return '';
                    }}
                }})()""",
                await_promise=True,
            ) or ""
            if isinstance(b64_str, str) and len(b64_str) > 4_000:
                raw_bytes = base64.b64decode(b64_str)

        # Tier 3: Chromium CDP Page.getResourceContent directly from browser cache
        if not raw_bytes:
            try:
                if frame_tree is None:
                    ft_res = await client.send("Page.getResourceTree")
                    frame_tree = ((ft_res or {}).get("frameTree") or {}).get("frame") or {}
                fid = str(frame_tree.get("id") or "")
                if fid:
                    rc_res = await client.send("Page.getResourceContent", {"frameId": fid, "url": img_url})
                    rc_content = (rc_res or {}).get("content") or ""
                    if rc_content:
                        raw_bytes = (
                            base64.b64decode(rc_content)
                            if (rc_res or {}).get("base64Encoded")
                            else str(rc_content).encode("latin1")
                        )
            except Exception:
                raw_bytes = None

        if not raw_bytes:
            continue
        arr = np.frombuffer(raw_bytes, dtype=np.uint8)
        bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if bgr is None:
            continue
        if (bgr.shape[1], bgr.shape[0]) != target_wh:
            src_h, src_w = bgr.shape[:2]
            dst_w, dst_h = target_wh
            target_ar = dst_w / float(dst_h)
            src_ar = src_w / float(max(src_h, 1))
            if abs(src_ar - target_ar) > 0.02:
                if src_ar > target_ar:
                    crop_w = max(1, int(round(src_h * target_ar)))
                    x0 = max(0, (src_w - crop_w) // 2)
                    bgr = bgr[:, x0 : x0 + crop_w]
                else:
                    crop_h = max(1, int(round(src_w / target_ar)))
                    y0 = max(0, (src_h - crop_h) // 2)
                    bgr = bgr[y0 : y0 + crop_h, :]
            bgr = cv2.resize(bgr, target_wh, interpolation=cv2.INTER_LANCZOS4)

        cand_dh = _dhash_64(bgr)
        if sibling_or_cond_dhashes and min((cand_dh ^ sdh).bit_count() for sdh in sibling_or_cond_dhashes) <= 2:
            continue

        tmp_png = Path(tempfile.gettempdir()) / f"flow_cand_{time.monotonic_ns()}_{out_p.stem}_{idx}.png"
        cv2.imwrite(str(tmp_png), bgr)

        qa_passed = True
        sharpness = float(cv2.Laplacian(cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY), cv2.CV_64F).var())
        contrast = float(np.std(cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)))
        qa_reason = ""
        if spec is not None:
            rep = inspect_single_reference_image(tmp_png, spec, aspect=aspect)
            qa_passed = bool(rep.get("passed"))
            metrics = rep.get("metrics") or {}
            sharpness = float(
                rep.get("laplacian_sharpness")
                or metrics.get("sharpness_laplacian")
                or sharpness
            )
            contrast = float(
                rep.get("luma_std")
                or metrics.get("luma_std")
                or contrast
            )
            qa_reason = str(rep.get("failed_axes") or rep.get("failed_checks") or "")

        min_dhash = 64
        dhash_ok = True
        if source_dhashes:
            dh = _dhash_64(bgr)
            parsed_shs = [int(sh, 16) if isinstance(sh, str) else int(sh) for sh in source_dhashes if str(sh).strip()]
            if parsed_shs:
                min_dhash = min((dh ^ psh).bit_count() for psh in parsed_shs)
                dhash_ok = min_dhash >= REENACT_MIN_DHASH_DISTANCE

        candidates.append(
            {
                "idx": idx,
                "tmp_png": tmp_png,
                "qa_passed": qa_passed,
                "dhash_ok": dhash_ok,
                "min_dhash": min_dhash,
                "quality_score": round(min(sharpness, 600.0) * 0.4 + contrast * 2.0, 2),
                "qa_reason": qa_reason,
            }
        )

    if not candidates:
        return {"ok": False, "saved": False, "reason": "candidate_fetch_failed"}

    candidates.sort(
        key=lambda c: (
            bool(c["qa_passed"] and c["dhash_ok"]),
            bool(c["qa_passed"]),
            bool(c["dhash_ok"]),
            float(c["quality_score"]),
        ),
        reverse=True,
    )
    winner = candidates[0]
    winner_ok = bool(winner["qa_passed"] and winner["dhash_ok"])
    import shutil

    saved_candidate_paths: list[str] = []
    if save_all_candidates_dir is not None:
        cand_dir = Path(save_all_candidates_dir)
        cand_dir.mkdir(parents=True, exist_ok=True)
        for rank_i, c in enumerate(candidates[:4], start=1):
            dst_cand = cand_dir / f"keyart_{rank_i:02d}.png"
            shutil.copy2(c["tmp_png"], dst_cand)
            saved_candidate_paths.append(str(dst_cand))

    if winner_ok:
        if out_p.suffix.lower() in (".jpg", ".jpeg"):
            win_bgr = cv2.imread(str(winner["tmp_png"]), cv2.IMREAD_COLOR)
            if win_bgr is not None:
                cv2.imwrite(str(out_p), win_bgr, [int(cv2.IMWRITE_JPEG_QUALITY), 93])
            else:
                shutil.copy2(winner["tmp_png"], out_p)
        else:
            shutil.copy2(winner["tmp_png"], out_p)
    for c in candidates:
        Path(c["tmp_png"]).unlink(missing_ok=True)

    if winner_ok and project_dir is not None:
        register_reference_image(
            Path(project_dir),
            out_p.name,
            "flow_image_generation",
        )

    return {
        "ok": winner_ok,
        "saved": winner_ok,
        "out_path": str(out_p) if winner_ok else "",
        "saved_candidate_paths": saved_candidate_paths,
        "candidate_count": len(candidates),
        "selected_index": int(winner["idx"]),
        "qa_passed": bool(winner["qa_passed"]),
        "dhash_ok": bool(winner["dhash_ok"]),
        "min_dhash": int(winner["min_dhash"]),
        "quality_score": float(winner["quality_score"]),
        "attached_refs": attached_refs,
        "image_model": active_image_model,
        "reason": winner["qa_reason"] or ("" if winner_ok else "qa_or_dhash_gate_failed"),
    }


__all__ = [
    "assert_model_settings",
    "attach_frame_slot_by_name",
    "close_gemini_tabs",
    "configure_flow_zero_credit_image_mode",
    "dismiss_flow_overlays",
    "generate_flow_image_batch",
    "read_active_flow_input_mode",
    "read_active_flow_model_family",
    "select_flow_video_model",
    "set_flow_video_input_mode",
    "attach_uploaded_by_name",
    "clear_prompt_ingredients",
    "prepare_reference_frames",
    "upload_file_to_flow",
    "upload_start_end_frames_to_flow",
]

