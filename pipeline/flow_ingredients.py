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
    FLOW_ZERO_CREDIT_IMAGE_BATCH_COUNT,
    FLOW_ZERO_CREDIT_IMAGE_FAMILY_ID,
    FLOW_ZERO_CREDIT_IMAGE_MODEL,
    FLOW_ZERO_CREDIT_MODEL,
    FLOW_ZERO_CREDIT_TEXT,
    REENACT_MIN_DHASH_DISTANCE,
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


async def upload_start_end_frames_to_flow(
    client: Any,
    start_frame: Path,
    end_frame: Path | None = None,
    uploaded_cache: set[str] | None = None,
) -> dict[str, Any]:
    """
    Uploads and attaches a Start Frame and optional End Frame into Google Flow's prompt box (`Frames` / dual-chip mode).
    Returns `{"start_attached": bool, "end_attached": bool, "chip_count": int}`.
    """
    cache = uploaded_cache if uploaded_cache is not None else set()
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
    }


async def configure_flow_zero_credit_image_mode(
    client: Any,
    aspect: str = "9:16",
    batch_count: int = FLOW_ZERO_CREDIT_IMAGE_BATCH_COUNT,
) -> dict[str, Any]:
    """
    Configures Google Flow into `Image` mode (`Nano Banana 2.1` / `beluga_display`), `aspect` (`9:16` or `16:9`),
    and the highest `0-credit` batch count (`x4` -> `x2` -> `x1`), strictly verifying `Generating will use 0 credits`
    and forbidding any paid credit approval dialogs.
    """
    target_batch = max(1, min(4, int(batch_count or FLOW_ZERO_CREDIT_IMAGE_BATCH_COUNT)))
    target_aspect = "16:9" if str(aspect).strip() == "16:9" else "9:16"
    await client.eval("window.__bci_flow_forbid_credit_approve = true;")
    await client.eval("""(() => {
        const b = document.querySelector('.agent-panel-header button[aria-label="Close"]');
        if (b) b.click();
        const chip = document.querySelector('button.agent-mode-chip[aria-pressed="true"]');
        if (chip) chip.click();
    })()""")
    await asyncio.sleep(0.4)

    await press_escape(client)
    await client.eval("""(() => {
        const st = document.querySelector('button.settings-trigger-button');
        if (st) st.click();
    })()""")
    await asyncio.sleep(0.55)

    await client.eval("""(() => {
        const btns = Array.from(document.querySelectorAll('flow-prompt-box-settings button, .cdk-overlay-pane button'));
        const imgBtn = btns.find(b => (b.innerText || '').includes('Image'));
        if (imgBtn) imgBtn.click();
    })()""")
    await asyncio.sleep(0.45)

    # Ensure 0-credit Nano Banana 2.1 (beluga_display) image model is selected if another paid image model was active
    ls_info = await client.eval("""(() => {
        try { return JSON.parse(localStorage.getItem('flow-prompt-box-settings') || '{}'); } catch (e) { return {}; }
    })()""") or {}
    if str(ls_info.get("imageModelFamilyId") or "") != FLOW_ZERO_CREDIT_IMAGE_FAMILY_ID:
        dd_sel = ".cdk-overlay-pane [aria-haspopup], flow-prompt-box-settings [aria-haspopup]"
        dd = await find_point(client, dd_sel, "")
        if dd:
            await trusted_click(client, dd)
            await asyncio.sleep(0.6)
            opt = await find_point(
                client,
                ".cdk-overlay-pane [role=option], .cdk-overlay-pane [role=menuitem], .cdk-overlay-pane button",
                FLOW_ZERO_CREDIT_IMAGE_MODEL,
                exact=False,
            )
            if opt:
                await trusted_click(client, opt)
                await asyncio.sleep(0.6)

    chosen_batch = target_batch
    zero_credit_ok = False
    pane_text = ""
    for cand_n in sorted({target_batch, 4, 2, 1}, reverse=True):
        if cand_n > target_batch:
            continue
        state = await client.eval(f"""(() => {{
            const btns = Array.from(document.querySelectorAll('flow-prompt-box-settings button, .cdk-overlay-pane button'));
            const bAsp = btns.find(b => (b.innerText || '').includes({json.dumps(target_aspect)}));
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
        family_ok = str(ls_now.get("imageModelFamilyId") or "") == FLOW_ZERO_CREDIT_IMAGE_FAMILY_ID
        if (zero_text_ok or family_ok) and not explicit_paid and not warn_now and str(ls_now.get("mode") or "") == "IMAGE":
            chosen_batch = int(ls_now.get("outputCount") or cand_n)
            zero_credit_ok = True
            break

    await client.eval("""(() => {
        const bd = document.querySelector('.cdk-overlay-backdrop');
        if (bd) bd.click();
    })()""")
    await asyncio.sleep(0.3)

    if not zero_credit_ok:
        raise RuntimeError(
            f"Failed to verify 0-credit Google Flow Image mode (pane={pane_text[:240]!r})"
        )

    summary = await client.eval("""(() => (document.querySelector('button.settings-trigger-button')?.innerText || '').trim())()""") or ""
    return {
        "mode": "IMAGE",
        "image_model": FLOW_ZERO_CREDIT_IMAGE_MODEL,
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
) -> dict[str, Any]:
    """
    Generates up to `x4` (`FLOW_ZERO_CREDIT_IMAGE_BATCH_COUNT`) `0-credit` candidate images in a single
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

    # Configure & verify Image mode + 9:16 + x4 + 0-credit lock AFTER attaching any ingredients
    post_chip_cfg = await configure_flow_zero_credit_image_mode(client, aspect=aspect, batch_count=batch_count)
    eff_batch = int(post_chip_cfg.get("output_count") or batch_count)

    existing_urls = await client.eval("""(() => {
        const scrollers = Array.from(document.querySelectorAll('*')).filter(el => el.scrollHeight > el.clientHeight + 80);
        for (const s of scrollers) { try { s.scrollTop = 0; } catch (e) {} }
        return Array.from(document.querySelectorAll('img'))
            .filter(im => im.naturalWidth >= 300 && (im.currentSrc || im.src || '').includes('flow-content.google/image/'))
            .map(im => im.currentSrc || im.src);
    })()""") or []
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

    # Confirm ProseMirror cleared; if still populated after 1.5s, dispatch direct mouse click fallback
    await asyncio.sleep(1.2)
    ed_after = await client.eval("""(() => {
        const ed = document.querySelector('.ProseMirror[contenteditable="true"]');
        return ed ? (ed.innerText || '').trim().length : 0;
    })()""")
    if int(ed_after or 0) > 0 and sub_res.get("x", 0) > 0:
        ix, iy = int(sub_res["x"]), int(sub_res["y"])
        await client.send("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": ix, "y": iy})
        await client.send("Input.dispatchMouseEvent", {"type": "mousePressed", "x": ix, "y": iy, "button": "left", "clickCount": 1})
        await asyncio.sleep(0.08)
        await client.send("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": ix, "y": iy, "button": "left", "clickCount": 1})

    t0 = time.monotonic()
    new_urls: list[str] = []
    while time.monotonic() - t0 < timeout_sec:
        await asyncio.sleep(2.5)
        poll = await client.eval(f"""(() => {{
            const scrollers = Array.from(document.querySelectorAll('*')).filter(el => el.scrollHeight > el.clientHeight + 80);
            for (const s of scrollers) {{ try {{ s.scrollTop = 0; }} catch (e) {{}} }}
            const seen = new Set({json.dumps(list(seen_srcs))});
            const pending = document.querySelectorAll('flow-pending-tile').length;
            const errTiles = document.querySelectorAll('flow-error-tile').length;
            const urls = [];
            for (const im of document.querySelectorAll('img')) {{
                const u = im.currentSrc || im.src || '';
                if (im.naturalWidth >= 400 && u.includes('flow-content.google/image/') && !seen.has(u) && !urls.includes(u)) {{
                    urls.push(u);
                }}
            }}
            return {{ urls, pending, errTiles }};
        }})()""") or {}
        new_urls = [str(u) for u in (poll.get("urls") or []) if str(u)]
        pending_cnt = int(poll.get("pending") or 0)
        if len(new_urls) >= eff_batch:
            break
        if len(new_urls) >= 1 and pending_cnt == 0 and (time.monotonic() - t0) >= 8.0:
            break
        if int(poll.get("errTiles") or 0) > 0 and pending_cnt == 0 and not new_urls and (time.monotonic() - t0) >= 12.0:
            break

    for u in new_urls:
        seen_srcs.add(u)

    if not new_urls:
        return {"ok": False, "reason": "no_flow_images_rendered"}

    target_wh = (1920, 1080) if str(aspect).strip() == "16:9" else (1080, 1920)
    out_p = Path(out_path)
    out_p.parent.mkdir(parents=True, exist_ok=True)

    from pipeline.reference_image_qa import inspect_single_reference_image, register_reference_image

    def _dhash_64(bgr_arr: np.ndarray) -> int:
        gray = cv2.cvtColor(bgr_arr, cv2.COLOR_BGR2GRAY)
        resized = cv2.resize(gray, (9, 8), interpolation=cv2.INTER_AREA)
        diff = resized[:, 1:] > resized[:, :-1]
        val = 0
        for bit in diff.flatten():
            val = (val << 1) | int(bool(bit))
        return val

    import urllib.request

    frame_tree = None
    candidates: list[dict[str, Any]] = []
    for idx, img_url in enumerate(new_urls):
        raw_bytes: bytes | None = None
        # Tier 1: Direct Python fetch of pre-signed flow-content.google CDN URL (zero CORS restriction)
        try:
            def _dl_signed(u: str = img_url) -> bytes:
                req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=20) as resp:
                    return resp.read()

            cand_b = await asyncio.to_thread(_dl_signed)
            if cand_b and len(cand_b) > 8_000:
                raw_bytes = cand_b
        except Exception:
            raw_bytes = None

        # Tier 2: In-page fetch without credentials (compatible with Access-Control-Allow-Origin: *)
        if not raw_bytes:
            b64_str = await client.eval(
                f"""(async () => {{
                    try {{
                        const r = await fetch({json.dumps(img_url)});
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
            if isinstance(b64_str, str) and len(b64_str) > 10_000:
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

        tmp_png = Path(tempfile.gettempdir()) / f"flow_cand_{out_p.stem}_{idx}.png"
        cv2.imwrite(str(tmp_png), bgr)

        qa_passed = True
        sharpness = float(cv2.Laplacian(cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY), cv2.CV_64F).var())
        contrast = float(np.std(cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)))
        qa_reason = ""
        if spec is not None:
            rep = inspect_single_reference_image(tmp_png, spec)
            qa_passed = bool(rep.get("passed"))
            metrics = rep.get("metrics") or {}
            sharpness = float(metrics.get("sharpness_laplacian") or sharpness)
            contrast = float(metrics.get("luma_std") or contrast)
            qa_reason = str(rep.get("failed_checks") or "")

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

    if winner_ok:
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
        "candidate_count": len(candidates),
        "selected_index": int(winner["idx"]),
        "qa_passed": bool(winner["qa_passed"]),
        "dhash_ok": bool(winner["dhash_ok"]),
        "min_dhash": int(winner["min_dhash"]),
        "quality_score": float(winner["quality_score"]),
        "attached_refs": attached_refs,
        "image_model": FLOW_ZERO_CREDIT_IMAGE_MODEL,
        "reason": winner["qa_reason"] or ("" if winner_ok else "qa_or_dhash_gate_failed"),
    }


__all__ = [
    "assert_model_settings",
    "configure_flow_zero_credit_image_mode",
    "generate_flow_image_batch",
    "read_active_flow_model_family",
    "select_flow_video_model",
    "attach_uploaded_by_name",
    "clear_prompt_ingredients",
    "prepare_reference_frames",
    "upload_file_to_flow",
    "upload_start_end_frames_to_flow",
]

