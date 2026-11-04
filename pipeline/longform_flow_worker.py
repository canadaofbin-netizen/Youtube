"""
ALL ABOUT BRAIN — Standalone 16:9 (`1920x1080 @ 24fps`) Chapter-Sharded Google Flow Video Worker
(`pipeline/longform_flow_worker.py`).

100% isolated from `9:16` Shorts `flow_diorama_sharded_worker.py`.
Executes `flow_longform_prompts.json` in memory-safe shards (`<= 14` clips/shard across `<= 3` dedicated Flow tabs),
conditioning on verified `1920x1080` (`16:9`) `reference_images/*.png`, enforcing `16:9` (`width > height`),
inter-frame motion, anti-human-skin, plaque/text-edge, and neon-green CV gates on every `clip_NNN.mp4`,
and supporting exact shard/clip resume and `--dry-run` plan verification.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import tempfile
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from pipeline.config import (
    DEFAULT_CDP_PORT,
    FLOW_ASPECT_LONGFORM,
    FLOW_PRIMARY_VIDEO_MODEL,
    FLOW_ZERO_CREDIT_MODEL,
    LONGFORM_SHARD_MAX_CLIPS,
    PORCELAIN_REF_NEON_GREEN_MAX,
    REF_IMAGE_HUMAN_SKIN_MAX,
    WORKSPACE_ROOT,
)
from pipeline.longform_prompt_builder import build_flow_shards, resolve_longform_project_dir
from pipeline.source_reenactment import detect_human_faces_yunet


def parse_longform_clip_spec(spec: str | list[int] | set[int] | tuple[int, ...] | None) -> list[int] | None:
    """Parses clip selectors like `'1-2'`, `'1,2,5-8'`, or `[1, 2]` into sorted unique 1-based clip numbers."""
    if spec is None:
        return None
    if isinstance(spec, (list, set, tuple)):
        out = sorted({int(x) for x in spec if int(x) > 0})
        return out or None
    raw = str(spec).strip()
    if not raw:
        return None
    nums: set[int] = set()
    for part in raw.split(","):
        tok = part.strip()
        if not tok:
            continue
        if "-" in tok:
            lo_s, hi_s = tok.split("-", 1)
            lo, hi = int(lo_s.strip()), int(hi_s.strip())
            if hi < lo:
                lo, hi = hi, lo
            for k in range(lo, hi + 1):
                if k > 0:
                    nums.add(k)
        else:
            val = int(tok)
            if val > 0:
                nums.add(val)
    return sorted(nums) if nums else None


def inspect_longform_16x9_clip_cv(
    mp4_path: Path,
    min_duration_sec: float = 3.2,
    grammar: str = "",
    reference_path: Path | None = None,
) -> dict[str, Any]:
    """Runs 6-gate CV verification (including reference anchor correlation for 3D brain clips) on a `16:9` Flow MP4."""
    p = Path(mp4_path)
    if not p.exists() or p.stat().st_size < 25_000:
        return {"passed": False, "reason": "missing_or_tiny_mp4", "path": str(p)}

    cap = cv2.VideoCapture(str(p))
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 24.0)
    fc = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    dur = (fc / fps) if (fps > 0 and fc > 0) else 0.0

    sample_indices = sorted({0, max(0, fc // 4), max(0, fc // 2), max(0, (3 * fc) // 4), max(0, fc - 2)})
    frames: list[np.ndarray] = []
    for f_i in sample_indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, f_i)
        ok, frm = cap.read()
        if ok and frm is not None:
            frames.append(frm)
    cap.release()

    if not frames or w <= h:
        return {
            "passed": False,
            "reason": f"non_landscape_aspect_{w}x{h}",
            "width": w,
            "height": h,
            "duration_sec": round(dur, 3),
        }

    aspect_ok = abs((w / float(h)) - (16.0 / 9.0)) <= 0.06
    dur_ok = dur >= (min_duration_sec - 0.15)
    g_norm = str(grammar or "").strip().lower()
    is_brain_clip = "living_brain" in g_norm

    diffs: list[float] = []
    skin_ratios: list[float] = []
    neon_ratios: list[float] = []
    margin_text_edges: list[float] = []
    face_counts: list[int] = []

    for idx_f, bgr in enumerate(frames):
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        if idx_f > 0:
            prev_g = cv2.cvtColor(frames[idx_f - 1], cv2.COLOR_BGR2GRAY)
            diffs.append(float(np.mean(np.abs(gray.astype(np.float32) - prev_g.astype(np.float32)))))
        if not is_brain_clip:
            face_counts.append(len(detect_human_faces_yunet(bgr)))
        hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
        hy0, hy1 = int(h * 0.15), int(h * 0.55)
        hx0, hx1 = int(w * 0.20), int(w * 0.80)
        hh = hsv[hy0:hy1, hx0:hx1]
        ycc = cv2.cvtColor(bgr[hy0:hy1, hx0:hx1], cv2.COLOR_BGR2YCrCb)
        skin = (
            (hh[:, :, 0] >= 3)
            & (hh[:, :, 0] <= 14)
            & (hh[:, :, 1] >= 52)
            & (hh[:, :, 1] <= 155)
            & (hh[:, :, 2] >= 95)
            & (hh[:, :, 2] <= 242)
            & (ycc[:, :, 1] >= 152)
            & (ycc[:, :, 1] <= 178)
            & (ycc[:, :, 2] >= 92)
            & (ycc[:, :, 2] <= 118)
        )
        skin_ratios.append(float(np.mean(skin)))
        neon = (hsv[:, :, 1] >= 75) & (hsv[:, :, 2] >= 70) & (hsv[:, :, 0] >= 36) & (hsv[:, :, 0] <= 82)
        neon_ratios.append(float(np.mean(neon)))
        edges = cv2.Canny(gray, 70, 170)
        margin_text_edges.append(float(np.mean(edges[int(h * 0.90) :, :] > 0)))

    motion_mean = round(float(np.mean(diffs)) if diffs else 0.0, 3)
    max_skin = round(max(skin_ratios) if skin_ratios else 0.0, 4)
    max_neon = round(max(neon_ratios) if neon_ratios else 0.0, 4)
    max_bot_edges = round(max(margin_text_edges) if margin_text_edges else 0.0, 4)
    max_faces = max(face_counts) if face_counts else 0
    max_ref_corr: float | None = None

    if reference_path is not None and Path(reference_path).exists() and is_brain_clip:
        ref_bgr = cv2.imread(str(reference_path))
        if ref_bgr is not None:
            ref_hsv = cv2.cvtColor(cv2.resize(ref_bgr, (640, 360)), cv2.COLOR_BGR2HSV)
            rmask = (ref_hsv[:, :, 1] >= 22).astype(np.uint8) * 255
            if float(np.mean(rmask > 0)) >= 0.03:
                ref_hs = cv2.calcHist([ref_hsv], [0, 1], rmask, [24, 16], [0, 180, 22, 256])
                cv2.normalize(ref_hs, ref_hs)
                ref_vh = cv2.calcHist([ref_hsv], [2], None, [16], [0, 256])
                cv2.normalize(ref_vh, ref_vh)
                corrs: list[float] = []
                for bgr in frames:
                    f_hsv = cv2.cvtColor(cv2.resize(bgr, (640, 360)), cv2.COLOR_BGR2HSV)
                    fmask = (f_hsv[:, :, 1] >= 22).astype(np.uint8) * 255
                    if float(np.mean(fmask > 0)) < 0.01:
                        corrs.append(0.0)
                        continue
                    f_hs = cv2.calcHist([f_hsv], [0, 1], fmask, [24, 16], [0, 180, 22, 256])
                    cv2.normalize(f_hs, f_hs)
                    f_vh = cv2.calcHist([f_hsv], [2], None, [16], [0, 256])
                    cv2.normalize(f_vh, f_vh)
                    c_hs = float(cv2.compareHist(ref_hs, f_hs, cv2.HISTCMP_CORREL))
                    c_v = float(cv2.compareHist(ref_vh, f_vh, cv2.HISTCMP_CORREL))
                    corrs.append(0.5 * c_hs + 0.5 * c_v)
                if corrs:
                    max_ref_corr = round(max(corrs), 3)

    skin_cap = 0.65 if is_brain_clip else float(REF_IMAGE_HUMAN_SKIN_MAX)
    failed_gates: list[str] = []
    if not aspect_ok:
        failed_gates.append(f"aspect_{w}x{h}")
    if not dur_ok:
        failed_gates.append(f"short_duration_{dur:.2f}s")
    if motion_mean < 0.35:
        failed_gates.append(f"frozen_frame_motion_{motion_mean}")
    if max_skin > skin_cap:
        failed_gates.append(f"human_skin_leak_{max_skin}")
    if not is_brain_clip and max_faces > 0:
        failed_gates.append(f"human_skin_or_face_leak_yunet_{max_faces}")
    if max_neon > PORCELAIN_REF_NEON_GREEN_MAX * 1.5:
        failed_gates.append(f"neon_green_spill_{max_neon}")
    if max_bot_edges > 0.38:
        failed_gates.append(f"bottom_hud_pollution_{max_bot_edges}")
    if max_ref_corr is not None and max_ref_corr < 0.39:
        failed_gates.append(f"unanchored_brain_hallucination_{max_ref_corr:.3f}")

    out_rep: dict[str, Any] = {
        "passed": len(failed_gates) == 0,
        "failed_gates": failed_gates,
        "width": w,
        "height": h,
        "fps": round(fps, 2),
        "duration_sec": round(dur, 3),
        "motion_mean": motion_mean,
        "max_human_skin_ratio": max_skin,
        "max_neon_green_ratio": max_neon,
        "max_yunet_faces": max_faces,
    }
    if max_ref_corr is not None:
        out_rep["max_ref_hist_corr"] = max_ref_corr
    return out_rep


def _reinforce_longform_yunet_retry_prompt(
    prompt_text: str,
    grammar: str = "",
    cv_reason: str = "",
) -> str:
    """
    Grammar-aware retry reinforcement after a YuNet CV gate failure:
      - `porcelain_hands_closeup` / `porcelain_pov_hands`: locks strictly macro tabletop hands/forearms
        with zero heads or busts (never instructing Veo to render a head surface in a hands-only shot).
      - Cast/world grammars: reinforces 100% smooth featureless blank egg-shaped matte-white porcelain heads
        (`zero eyes, zero nose, zero mouth, zero sculpted facial features`) without priming anatomical sculpt nouns.
    """
    if "yunet" not in str(cv_reason or "").lower():
        return prompt_text
    g_norm = str(grammar or "").strip().lower()
    if "living_brain" in g_norm:
        return prompt_text
    if g_norm in ("porcelain_hands_closeup", "porcelain_pov_hands"):
        extra = (
            "Frame strictly articulated matte-white porcelain hands and tailored fabric sleeves over clean tabletop props "
            "(zero heads, zero busts, zero faces, zero face-like reflections anywhere in frame)."
        )
    else:
        extra = (
            "Keep every figure's head 100% smooth featureless blank egg-shaped matte-white porcelain "
            "(zero eyes, zero nose, zero mouth, zero sculpted facial features)."
        )
    if extra.lower() in prompt_text.lower():
        return prompt_text
    return f"{prompt_text.rstrip()} {extra}"


async def _dismiss_agent_mode_chip(client: Any) -> None:
    """Closes any open Agent side panel and untoggles `button.agent-mode-chip[aria-pressed='true']`."""
    res = await client.eval("""(() => {
        const closeBtn = document.querySelector('.agent-panel-header button[aria-label="Close"]');
        if (closeBtn) { try { closeBtn.click(); } catch (e) {} }
        const chip = document.querySelector('button.agent-mode-chip[aria-pressed="true"]');
        if (chip) {
            try { chip.click(); } catch (e) {}
            const r = chip.getBoundingClientRect();
            return { hadChip: true, x: r.width > 0 ? r.x + r.width / 2 : 0, y: r.height > 0 ? r.y + r.height / 2 : 0 };
        }
        return { hadChip: false, x: 0, y: 0 };
    })()""") or {}
    if res.get("hadChip"):
        await asyncio.sleep(0.35)
        still_pressed = await client.eval(
            """Boolean(document.querySelector('button.agent-mode-chip[aria-pressed="true"]'))"""
        )
        if still_pressed and float(res.get("x") or 0) > 0:
            mx, my = int(res["x"]), int(res["y"])
            await client.send("Input.dispatchMouseEvent", {"type": "mousePressed", "x": mx, "y": my, "button": "left", "clickCount": 1})
            await client.send("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": mx, "y": my, "button": "left", "clickCount": 1})
            await asyncio.sleep(0.35)


def _stage_16x9_ref_upload_file(start_ref: Path) -> Path:
    """
    Stages a compact `1280x720` (`16:9`) JPEG copy in `/tmp` for multi-MB `1920x1080` PNG anchors so CDP
    upload + Flow attachment completes in `< 1s` without altering the canonical `start_ref.name` provenance.
    """
    try:
        if start_ref.stat().st_size <= 400_000:
            return start_ref
        raw = start_ref.read_bytes()
        sha8 = hashlib.sha1(raw).hexdigest()[:8]
        staged = Path(tempfile.gettempdir()) / f"lf16x9_{sha8}.jpg"
        if staged.exists() and staged.stat().st_size > 10_000:
            return staged
        bgr = cv2.imread(str(start_ref))
        if bgr is None:
            return start_ref
        h0, w0 = bgr.shape[:2]
        if max(h0, w0) > 1280:
            sc = 1280.0 / float(max(h0, w0))
            bgr = cv2.resize(
                bgr,
                (max(1, int(round(w0 * sc))), max(1, int(round(h0 * sc)))),
                interpolation=cv2.INTER_AREA,
            )
        cv2.imwrite(str(staged), bgr, [cv2.IMWRITE_JPEG_QUALITY, 92])
        return staged if staged.exists() else start_ref
    except Exception:
        return start_ref


async def _configure_longform_video_16x9_tab(
    client: Any,
    *,
    engine_mode: str = "auto",
    credit_exhausted_event: asyncio.Event | None = None,
) -> dict[str, Any]:
    """
    Configures a dedicated Google Flow tab strictly for `Video` + `Ingredients` (not `Frames`) +
    `16:9` (`Landscape`) + `8s` + `x1` under the Dual-Tier Engine Policy (`auto` | `omni` | `zero-credit`),
    never selecting `9:16`.
    """
    from pipeline.flow_diorama_sharded_worker import CHECK_CREDIT_EXHAUSTION_JS, DISMISS_CREDIT_DIALOG_JS
    from pipeline.flow_ingredients import press_escape, read_active_flow_model_family, select_flow_video_model

    norm_mode = str(engine_mode or "auto").strip().lower().replace("_", "-")
    use_zero = norm_mode == "zero-credit" or (
        norm_mode == "auto" and credit_exhausted_event is not None and credit_exhausted_event.is_set()
    )
    target_model = FLOW_ZERO_CREDIT_MODEL if use_zero else FLOW_PRIMARY_VIDEO_MODEL

    await _dismiss_agent_mode_chip(client)
    await client.eval(
        "window.__bci_flow_forbid_credit_approve = true;"
        if use_zero
        else "window.__bci_flow_forbid_credit_approve = false;"
    )
    await client.eval(DISMISS_CREDIT_DIALOG_JS)

    async def _lock_video_ingredients_16x9_8s(model_name: str) -> dict[str, Any]:
        await press_escape(client)
        await asyncio.sleep(0.2)
        await client.eval("""(() => {
            const st = document.querySelector('button.settings-trigger-button');
            if (st) st.click();
        })()""")
        await asyncio.sleep(0.4)
        # Switch out of Image mode into Video + Ingredients FIRST so video models populate the dropdown
        await client.eval("""(() => {
            const btns = Array.from(document.querySelectorAll('flow-prompt-box-settings button, .cdk-overlay-pane button'));
            const vidBtn = btns.find(b => (b.innerText || '').includes('Video'));
            if (vidBtn && !vidBtn.disabled) vidBtn.click();
        })()""")
        await asyncio.sleep(0.35)
        await client.eval("""(() => {
            const btns = Array.from(document.querySelectorAll('flow-prompt-box-settings button, .cdk-overlay-pane button'));
            const ingBtn = btns.find(b => (b.innerText || '').includes('Ingredients'));
            if (ingBtn && !ingBtn.disabled) ingBtn.click();
            const aspBtn = btns.find(b => {
                const t = (b.innerText || '').trim();
                return t.includes('16:9') || t.toLowerCase().includes('landscape');
            });
            if (aspBtn && !aspBtn.disabled) aspBtn.click();
            const d8 = btns.find(b => (b.innerText || '').trim() === '8s');
            if (d8 && !d8.disabled) d8.click();
            const x1 = btns.find(b => (b.innerText || '').trim() === 'x1');
            if (x1 && !x1.disabled) x1.click();
        })()""")
        await asyncio.sleep(0.3)

        await select_flow_video_model(client, model=model_name)
        await asyncio.sleep(0.35)

        # Re-assert Ingredients (never Frames) + 16:9 + 8s + x1 after model selection and close overlay
        await client.eval("""(() => {
            const box = document.querySelector('flow-prompt-box-settings, .cdk-overlay-pane');
            const st = document.querySelector('button.settings-trigger-button');
            if (!box && st) st.click();
        })()""")
        await asyncio.sleep(0.3)
        await client.eval("""(() => {
            const btns = Array.from(document.querySelectorAll('flow-prompt-box-settings button, .cdk-overlay-pane button'));
            const vidBtn = btns.find(b => (b.innerText || '').includes('Video'));
            if (vidBtn && !vidBtn.disabled) vidBtn.click();
            const ingBtn = btns.find(b => (b.innerText || '').includes('Ingredients'));
            if (ingBtn && !ingBtn.disabled) ingBtn.click();
            const aspBtn = btns.find(b => {
                const t = (b.innerText || '').trim();
                return t.includes('16:9') || t.toLowerCase().includes('landscape');
            });
            if (aspBtn && !aspBtn.disabled) aspBtn.click();
            const d8 = btns.find(b => (b.innerText || '').trim() === '8s');
            if (d8 && !d8.disabled) d8.click();
            const x1 = btns.find(b => (b.innerText || '').trim() === 'x1');
            if (x1 && !x1.disabled) x1.click();
            const bd = document.querySelector('.cdk-overlay-backdrop');
            if (bd) bd.click();
        })()""")
        await asyncio.sleep(0.3)
        state = await client.eval("""(() => ({
            summary: (document.querySelector('button.settings-trigger-button')?.innerText || '').trim(),
            ls: (() => { try { return JSON.parse(localStorage.getItem('flow-prompt-box-settings') || '{}'); } catch (e) { return {}; } })()
        }))()""") or {}
        return state

    st_res = await _lock_video_ingredients_16x9_8s(target_model)
    cred_chk = await client.eval(CHECK_CREDIT_EXHAUSTION_JS) or {}
    if not use_zero and bool(cred_chk.get("exhausted")):
        if norm_mode == "omni":
            raise RuntimeError(f"Omni 1.1 Flash credits exhausted in longform-flow: {cred_chk}")
        if credit_exhausted_event is not None:
            credit_exhausted_event.set()
        use_zero = True
        target_model = FLOW_ZERO_CREDIT_MODEL
        await client.eval("window.__bci_flow_forbid_credit_approve = true;")
        st_res = await _lock_video_ingredients_16x9_8s(target_model)
        cred_chk = await client.eval(CHECK_CREDIT_EXHAUSTION_JS) or {}

    fam = await read_active_flow_model_family(client)
    ls_obj = st_res.get("ls") or {}
    summary_str = str(st_res.get("summary") or "")
    has_warn = bool(cred_chk.get("has_warning_btn"))
    return {
        "flow_model": target_model,
        "model_family": fam,
        "aspect": FLOW_ASPECT_LONGFORM,
        "mode": str(ls_obj.get("mode") or ""),
        "aspect_ratio": str(ls_obj.get("aspectRatio") or ""),
        "has_warning_btn": has_warn,
        "zero_credit_verified": bool(use_zero and fam == "veo_3_1_lite_low_priority" and not has_warn),
        "settings_summary": summary_str,
    }


async def _generate_single_longform_16x9_clip_in_tab(
    *,
    client: Any,
    clip_num: int,
    prompt_text: str,
    out_mp4: Path,
    start_ref: Path | None,
    uploaded_cache: set[str],
    seen_video_urls: set[str],
    flow_dl_dir: Path,
    seen_global_shas: set[str],
    shard_id: int = 1,
    project_slug: str = "",
    engine_mode: str = "auto",
    credit_exhausted_event: asyncio.Event | None = None,
    tab_upload_lock: asyncio.Lock | None = None,
) -> dict[str, Any]:
    """
    Submits one `16:9` Long-Form video prompt in an open Flow project tab.
    Fail-closed reference contract: when `start_ref` is bound (`start_ref is not None`), dismisses any active
    Agent mode chip, locks `Ingredients` + `Video` + `16:9` (`Landscape`) + `8s` + `0-credit` model WITH
    `start_ref` attached (`count_chips >= 1` verified right before clicking Generate), and NEVER drops
    `start_ref` to submit unanchored.
    """
    from pipeline.flow_diorama_sharded_worker import (
        CHECK_CREDIT_EXHAUSTION_JS,
        DISMISS_CREDIT_DIALOG_JS,
        _download_newest_ready_tile,
    )
    from pipeline.flow_ingredients import (
        attach_uploaded_by_name,
        clear_prompt_ingredients,
        count_chips,
        press_escape,
        read_active_flow_model_family,
        upload_file_to_flow,
    )
    from pipeline.flow_live_single_worker import FLOW_TILE_CLASSIFIER_JS

    ref_name: str | None = start_ref.name if start_ref is not None else None
    if start_ref is not None and not start_ref.exists():
        return {
            "ok": False,
            "reason": "ref_attach_or_0cred_lock_failed",
            "clip_number": clip_num,
            "reference_image": ref_name,
            "reference_attached": False,
        }

    await _dismiss_agent_mode_chip(client)
    if await count_chips(client) > 0:
        await clear_prompt_ingredients(client)
        if await count_chips(client) > 0:
            return {
                "ok": False,
                "reason": "stale_chip_clear_failed",
                "clip_number": clip_num,
                "reference_image": ref_name,
                "reference_attached": False,
            }

    async def _has_healthy_attached_chip() -> bool:
        if (await count_chips(client)) < 1:
            return False
        healthy_dom = await client.eval("""(() => {
            const chips = Array.from(document.querySelectorAll('flow-prompt-box button[aria-label="Ingredient"]'));
            if (!chips.length) return true;
            return chips.every(ch => {
                const t = ((ch.innerText || '') + ' ' + (ch.getAttribute('title') || '')).toLowerCase();
                return !t.includes('uploading') && !t.includes('error') && !t.includes('failed');
            });
        })()""")
        return bool(healthy_dom)

    cfg = await _configure_longform_video_16x9_tab(
        client,
        engine_mode=engine_mode,
        credit_exhausted_event=credit_exhausted_event,
    )
    active_model = str(cfg.get("flow_model") or FLOW_ZERO_CREDIT_MODEL)

    # Settle any in-flight tile and clear stale error tiles before submitting
    settle_js = f"""(() => {{
        const classifyTile = {FLOW_TILE_CLASSIFIER_JS};
        const scrollers = Array.from(document.querySelectorAll('*')).filter(el => el.scrollHeight > el.clientHeight + 80);
        for (const s of scrollers) {{ try {{ s.scrollTop = 0; }} catch (e) {{}} }}
        document.querySelectorAll('flow-error-tile').forEach(et => {{
            const b = Array.from(et.querySelectorAll('button')).find(x => (x.innerText || x.getAttribute('aria-label') || '').toLowerCase().includes('delete'));
            if (b) {{ try {{ b.click(); }} catch (e) {{}} }}
        }});
        const allTiles = Array.from(document.querySelectorAll('flow-video-tile'));
        let ready = 0;
        let rendering = 0;
        const srcs = [];
        let topKey = '';
        for (const el of allTiles) {{
            const cls = classifyTile(el);
            if (cls.isError) {{
                const b = Array.from(el.querySelectorAll('button')).find(x => (x.innerText || x.getAttribute('aria-label') || '').toLowerCase().includes('delete'));
                if (b) {{ try {{ b.click(); }} catch (e) {{}} }}
                continue;
            }}
            if (cls.isReady) {{
                ready += 1;
                const v = el.querySelector('video[src^="https://"]');
                if (v && v.src) {{
                    srcs.push(v.src);
                    if (!topKey) topKey = v.src;
                }}
            }} else {{
                rendering += 1;
            }}
        }}
        return {{ ready, rendering, srcs, topKey }};
    }})()"""

    pre_info: dict[str, Any] = {}
    settle_deadline = time.monotonic() + 90.0
    while time.monotonic() < settle_deadline:
        pre_info = await client.eval(settle_js) or {}
        if int(pre_info.get("rendering") or 0) == 0:
            break
        await asyncio.sleep(2.5)

    if int(pre_info.get("rendering") or 0) != 0:
        return {
            "ok": False,
            "reason": "stale_rendering_tile",
            "clip_number": clip_num,
            "reference_image": ref_name,
            "reference_attached": False,
        }

    prev_ready = int(pre_info.get("ready") or 0)
    prev_top_key = str(pre_info.get("topKey") or "")
    for su in (pre_info.get("srcs") or []):
        seen_video_urls.add(str(su))

    # Fail-closed 16:9 reference anchor attachment + post-chip Ingredients / 16:9 / 0-credit re-lock
    if start_ref is not None:
        await _dismiss_agent_mode_chip(client)
        upload_target = await asyncio.to_thread(_stage_16x9_ref_upload_file, start_ref)

        from pipeline.flow_ingredients import trusted_click

        async def _click_add_to_prompt_if_enabled() -> bool:
            pt_add = await client.eval("""(() => {
                const pop = document.querySelector('flow-add-menu-popover-content');
                if (!pop) return null;
                const addBtn = Array.from(pop.querySelectorAll('button')).find(
                    b => (b.innerText || '').trim().toLowerCase().includes('add to prompt') && !b.disabled
                );
                if (!addBtn) return null;
                const r = addBtn.getBoundingClientRect();
                return r.width > 0 ? {x: r.x + r.width / 2, y: r.y + r.height / 2} : null;
            })()""")
            if isinstance(pt_add, dict) and "x" in pt_add:
                await trusted_click(client, pt_add)
                await asyncio.sleep(1.0)
                return await _has_healthy_attached_chip()
            return False

        async def _wait_upload_ready(fname: str, max_wait_sec: float = 28.0) -> str:
            if not await client.eval("Boolean(document.querySelector('flow-add-menu-popover-content'))"):
                await press_escape(client)
                await client.eval(
                    'document.querySelector(\'button[aria-label="Add ingredients to the prompt box"]\')?.click()'
                )
                await asyncio.sleep(0.5)
            deadline = time.monotonic() + max_wait_sec
            last_status = "missing"
            while time.monotonic() < deadline:
                if await _has_healthy_attached_chip():
                    return "attached"
                st_up = await client.eval(f"""(() => {{
                    const pop = document.querySelector('flow-add-menu-popover-content');
                    if (!pop) return 'no_dom';
                    const items = Array.from(pop.querySelectorAll('button, [role="option"]'));
                    const matches = items.filter(el => (el.innerText || '').includes({json.dumps(fname)}));
                    if (!matches.length) return 'missing';
                    const anyReady = matches.some(
                        el => !((el.innerText || '').toLowerCase().includes('uploading')) && !el.disabled
                    );
                    return anyReady ? 'ready' : 'uploading';
                }})()""")
                if not isinstance(st_up, str):
                    break
                last_status = str(st_up or "no_dom")
                if last_status == "ready":
                    if await _click_add_to_prompt_if_enabled():
                        return "attached"
                    break
                if last_status == "no_dom":
                    break
                await asyncio.sleep(0.8)
            await press_escape(client)
            return last_status

        async def _attach_ref() -> bool:
            chip_ok = False
            if upload_target.name not in uploaded_cache:
                if await upload_file_to_flow(client, upload_target):
                    uploaded_cache.add(upload_target.name)
                    if await _has_healthy_attached_chip():
                        chip_ok = True
                    else:
                        up_st = await _wait_upload_ready(upload_target.name, max_wait_sec=28.0)
                        if up_st == "attached" or await _has_healthy_attached_chip():
                            chip_ok = True
            if not chip_ok:
                chip_ok = await attach_uploaded_by_name(client, upload_target.name, wait_sec=16.0)
                if not chip_ok and not await _has_healthy_attached_chip():
                    chip_ok = await _click_add_to_prompt_if_enabled()
            if not chip_ok and not await _has_healthy_attached_chip():
                up_state = await _wait_upload_ready(upload_target.name, max_wait_sec=15.0)
                if up_state == "attached":
                    chip_ok = True
                elif up_state == "ready":
                    chip_ok = await attach_uploaded_by_name(client, upload_target.name, wait_sec=12.0)
                    if not chip_ok and not await _has_healthy_attached_chip():
                        chip_ok = await _click_add_to_prompt_if_enabled()
                elif up_state in ("missing", "no_dom"):
                    uploaded_cache.discard(upload_target.name)
                    if await upload_file_to_flow(client, upload_target):
                        uploaded_cache.add(upload_target.name)
                        if await _has_healthy_attached_chip():
                            chip_ok = True
                        else:
                            up_st2 = await _wait_upload_ready(upload_target.name, max_wait_sec=28.0)
                            if up_st2 == "attached" or await _has_healthy_attached_chip():
                                chip_ok = True
                            else:
                                chip_ok = await attach_uploaded_by_name(client, upload_target.name, wait_sec=16.0)
                                if not chip_ok and not await _has_healthy_attached_chip():
                                    chip_ok = await _click_add_to_prompt_if_enabled()
            await press_escape(client)
            return bool(chip_ok and await _has_healthy_attached_chip())

        if tab_upload_lock is not None:
            async with tab_upload_lock:
                attached = await _attach_ref()
        else:
            attached = await _attach_ref()

        if not attached or not await _has_healthy_attached_chip():
            await press_escape(client)
            return {
                "ok": False,
                "reason": "ref_attach_or_0cred_lock_failed",
                "clip_number": clip_num,
                "reference_image": ref_name,
                "reference_attached": False,
            }

        # Re-lock Video + Ingredients (not Frames) + 16:9 + 8s + model WITH start_ref chip kept attached
        lock_ok = False
        for _lock_try in range(2):
            await _dismiss_agent_mode_chip(client)
            cfg = await _configure_longform_video_16x9_tab(
                client,
                engine_mode=engine_mode,
                credit_exhausted_event=credit_exhausted_event,
            )
            active_model = str(cfg.get("flow_model") or active_model)
            if not await _has_healthy_attached_chip():
                break
            mode_now = str(cfg.get("mode") or "")
            aspect_now = str(cfg.get("aspect_ratio") or "")
            summary_now = str(cfg.get("settings_summary") or "")
            ingredients_ok = mode_now != "VIDEO_FRAMES" and mode_now != "IMAGE"
            landscape_ok = (aspect_now == "LANDSCAPE") or ("16:9" in summary_now) or ("16_9" in summary_now)
            if active_model == FLOW_ZERO_CREDIT_MODEL:
                cred_chip = await client.eval(CHECK_CREDIT_EXHAUSTION_JS) or {}
                fam_chip = await read_active_flow_model_family(client)
                zero_ok = (not bool(cred_chip.get("has_warning_btn"))) and (fam_chip == "veo_3_1_lite_low_priority")
                if zero_ok and ingredients_ok and landscape_ok:
                    lock_ok = True
                    break
                await asyncio.sleep(0.5)
            else:
                if ingredients_ok and landscape_ok:
                    lock_ok = True
                    break
                await asyncio.sleep(0.5)

        if not lock_ok or not await _has_healthy_attached_chip():
            return {
                "ok": False,
                "reason": "ref_attach_or_0cred_lock_failed",
                "clip_number": clip_num,
                "reference_image": ref_name,
                "reference_attached": False,
            }

    focused = await client.eval("""(() => {
        const ed = document.querySelector('.ProseMirror[contenteditable="true"]');
        if (!ed) return false;
        ed.focus();
        document.execCommand('selectAll', false, null);
        document.execCommand('delete', false, null);
        return true;
    })()""")
    if not focused:
        await press_escape(client)
        return {
            "ok": False,
            "reason": "editor_not_ready",
            "clip_number": clip_num,
            "reference_image": ref_name,
            "reference_attached": False,
        }

    await client.send("Input.insertText", {"text": prompt_text})
    await asyncio.sleep(0.3)
    await client.eval(f"""(() => {{
        const ed = document.querySelector('.ProseMirror[contenteditable="true"]');
        if (!ed) return false;
        if ((ed.innerText || '').trim().length < 15) {{
            ed.focus();
            document.execCommand('selectAll', false, null);
            document.execCommand('insertText', false, {json.dumps(prompt_text)});
        }}
        ed.dispatchEvent(new InputEvent('input', {{ bubbles: true, cancelable: true, inputType: 'insertText' }}));
        ed.dispatchEvent(new Event('change', {{ bubbles: true }}));
        return true;
    }})()""")
    await asyncio.sleep(0.3)

    # Final pre-submit gate right before clicking Generate: verify chip state + 16:9 Landscape + 0-credit lock
    await _dismiss_agent_mode_chip(client)
    if start_ref is not None:
        if not await _has_healthy_attached_chip():
            return {
                "ok": False,
                "reason": "ref_attach_or_0cred_lock_failed",
                "clip_number": clip_num,
                "reference_image": ref_name,
                "reference_attached": False,
            }
    else:
        if (await count_chips(client)) > 0:
            return {
                "ok": False,
                "reason": "unexpected_stale_chip_on_unbound_clip",
                "clip_number": clip_num,
                "reference_image": ref_name,
                "reference_attached": False,
            }

    pre_sub_state = await client.eval("""(() => ({
        summary: (document.querySelector('button.settings-trigger-button')?.innerText || '').trim(),
        ls: (() => { try { return JSON.parse(localStorage.getItem('flow-prompt-box-settings') || '{}'); } catch (e) { return {}; } })()
    }))()""") or {}
    ls_pre = pre_sub_state.get("ls") or {}
    mode_pre = str(ls_pre.get("mode") or "")
    aspect_pre = str(ls_pre.get("aspectRatio") or "")
    sum_pre = str(pre_sub_state.get("summary") or "")
    pre_ingredients_ok = mode_pre not in ("VIDEO_FRAMES", "IMAGE")
    pre_landscape_ok = (aspect_pre == "LANDSCAPE") or ("16:9" in sum_pre) or ("16_9" in sum_pre)
    if not (pre_ingredients_ok and pre_landscape_ok):
        return {
            "ok": False,
            "reason": "ref_attach_or_0cred_lock_failed" if start_ref is not None else "landscape_16x9_lock_failed",
            "clip_number": clip_num,
            "reference_image": ref_name,
            "reference_attached": False,
        }

    if active_model == FLOW_ZERO_CREDIT_MODEL:
        cred_pre = await client.eval(CHECK_CREDIT_EXHAUSTION_JS) or {}
        fam_pre = await read_active_flow_model_family(client)
        if bool(cred_pre.get("has_warning_btn")) or fam_pre != "veo_3_1_lite_low_priority":
            return {
                "ok": False,
                "reason": "ref_attach_or_0cred_lock_failed" if start_ref is not None else "zero_credit_lock_failed",
                "clip_number": clip_num,
                "reference_image": ref_name,
                "reference_attached": False,
            }

    sub_res = await client.eval("""(() => {
        const fg = document.querySelector('flow-generate-icon-button');
        const btn = document.querySelector('button[aria-label="Start generation"], button.generate-icon-button');
        const r = btn ? btn.getBoundingClientRect() : null;
        const fn = typeof getEventListeners === 'function' && fg ? getEventListeners(fg)?.generate?.[0]?.listener : null;
        if (fn) {
            fn({isTrusted: true});
            return { action: 'listener_invoked', x: r ? r.x + r.width / 2 : 0, y: r ? r.y + r.height / 2 : 0 };
        }
        if (btn && !btn.disabled && r && r.width > 0) {
            return { action: 'needs_mouse_click', x: r.x + r.width / 2, y: r.y + r.height / 2 };
        }
        return { action: 'not_ready', x: 0, y: 0 };
    })()""") or {}

    if sub_res.get("action") == "needs_mouse_click" and sub_res.get("x", 0) > 0:
        mx, my = int(sub_res["x"]), int(sub_res["y"])
        await client.send("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": mx, "y": my})
        await client.send("Input.dispatchMouseEvent", {"type": "mousePressed", "x": mx, "y": my, "button": "left", "clickCount": 1})
        await asyncio.sleep(0.08)
        await client.send("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": mx, "y": my, "button": "left", "clickCount": 1})
    elif sub_res.get("action") == "not_ready":
        return {
            "ok": False,
            "reason": "generate_button_not_ready",
            "clip_number": clip_num,
            "reference_image": ref_name,
            "reference_attached": False,
        }

    # Confirm ProseMirror cleared (dispatch direct mouse click fallback if listener_invoked was a no-op)
    submitted_ok = False
    for wait_sub in range(8):
        await asyncio.sleep(0.55)
        await client.eval(DISMISS_CREDIT_DIALOG_JS)
        ed_len = await client.eval("""(() => {
            const ed = document.querySelector('.ProseMirror[contenteditable="true"]');
            return ed ? (ed.innerText || '').trim().length : 0;
        })()""")
        if int(ed_len or 0) == 0:
            submitted_ok = True
            break
        if wait_sub in (2, 5) and float(sub_res.get("x") or 0) > 0:
            mx, my = int(sub_res["x"]), int(sub_res["y"])
            await client.send("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": mx, "y": my})
            await client.send("Input.dispatchMouseEvent", {"type": "mousePressed", "x": mx, "y": my, "button": "left", "clickCount": 1})
            await asyncio.sleep(0.08)
            await client.send("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": mx, "y": my, "button": "left", "clickCount": 1})

    if not submitted_ok:
        return {
            "ok": False,
            "reason": "submit_not_accepted",
            "clip_number": clip_num,
            "reference_image": ref_name,
            "reference_attached": False,
        }

    render_deadline = time.monotonic() + 240.0
    tile_ready = False
    saw_rendering = False
    while time.monotonic() < render_deadline:
        await asyncio.sleep(3.5)
        await client.eval(DISMISS_CREDIT_DIALOG_JS)
        poll = await client.eval(f"""(() => {{
            const classifyTile = {FLOW_TILE_CLASSIFIER_JS};
            const scrollers = Array.from(document.querySelectorAll('*')).filter(el => el.scrollHeight > el.clientHeight + 80);
            for (const s of scrollers) {{ try {{ s.scrollTop = 0; }} catch (e) {{}} }}
            const seen = new Set({json.dumps(list(seen_video_urls))});
            const errEls = Array.from(document.querySelectorAll('flow-error-tile'));
            let hadErr = errEls.length > 0;
            errEls.forEach(et => {{
                const b = Array.from(et.querySelectorAll('button')).find(x => (x.innerText || x.getAttribute('aria-label') || '').toLowerCase().includes('delete'));
                if (b) {{ try {{ b.click(); }} catch (e) {{}} }}
            }});
            const allTiles = Array.from(document.querySelectorAll('flow-video-tile'));
            let ready = 0;
            let rendering = 0;
            let topKey = '';
            let hasNewSrc = false;
            for (const el of allTiles) {{
                const cls = classifyTile(el);
                if (cls.isError) {{
                    hadErr = true;
                    const b = Array.from(el.querySelectorAll('button')).find(x => (x.innerText || x.getAttribute('aria-label') || '').toLowerCase().includes('delete'));
                    if (b) {{ try {{ b.click(); }} catch (e) {{}} }}
                    continue;
                }}
                if (cls.isReady) {{
                    ready += 1;
                    const v = el.querySelector('video[src^="https://"]');
                    if (v && v.src) {{
                        if (!topKey) topKey = v.src;
                        if (!seen.has(v.src)) hasNewSrc = true;
                    }}
                }} else {{
                    rendering += 1;
                }}
            }}
            return {{ ready, rendering, hasNewSrc, topKey, hadErr }};
        }})()""") or {}

        if int(poll.get("rendering") or 0) > 0:
            saw_rendering = True
        cur_top = str(poll.get("topKey") or "")
        top_changed = bool(cur_top and cur_top != prev_top_key)
        if int(poll.get("rendering") or 0) == 0 and (
            bool(poll.get("hasNewSrc")) or top_changed or int(poll.get("ready") or 0) > prev_ready
        ) and (saw_rendering or top_changed or bool(poll.get("hasNewSrc"))):
            tile_ready = True
            break
        if bool(poll.get("hadErr")) and int(poll.get("rendering") or 0) == 0:
            return {
                "ok": False,
                "reason": "flow_tile_error",
                "clip_number": clip_num,
                "reference_image": ref_name,
                "reference_attached": bool(start_ref is not None),
            }

    if not tile_ready:
        return {
            "ok": False,
            "reason": "render_timeout",
            "clip_number": clip_num,
            "reference_image": ref_name,
            "reference_attached": bool(start_ref is not None),
        }

    dl_meta = await _download_newest_ready_tile(
        client=client,
        dst_mp4=out_mp4,
        flow_dl_dir=flow_dl_dir,
        seen_global_shas=seen_global_shas,
        seen_tab_srcs=seen_video_urls,
        shard_id=shard_id,
        project_slug=project_slug,
        max_candidates=1,
    )
    if dl_meta and out_mp4.exists():
        return {
            "ok": True,
            "clip_number": clip_num,
            "flow_model": active_model,
            "credit_tier": "zero_credit_fallback" if active_model == FLOW_ZERO_CREDIT_MODEL else "omni_monthly_credit",
            "zero_credit_verified": bool(active_model == FLOW_ZERO_CREDIT_MODEL),
            "reference_image": ref_name,
            "reference_attached": bool(start_ref is not None),
            **dl_meta,
        }
    return {
        "ok": False,
        "reason": "download_failed",
        "clip_number": clip_num,
        "reference_image": ref_name,
        "reference_attached": bool(start_ref is not None),
    }


def _resolve_clip_ref_path(p_dir: Path, ref_rel: Any) -> Path | None:
    raw = str(ref_rel or "").strip()
    if not raw:
        return None
    cand = Path(raw)
    if cand.is_absolute():
        return cand
    p_local = p_dir / raw
    if p_local.exists():
        return p_local
    p_ws = Path(WORKSPACE_ROOT) / raw
    if p_ws.exists():
        return p_ws
    return p_local


async def run_longform_sharded_flow_generation(
    project_id_or_dir: str | Path,
    *,
    tabs: int = 3,
    shard_index: int | None = None,
    only_clips: list[int] | str | None = None,
    cdp_port: int = DEFAULT_CDP_PORT,
    engine_mode: str = "auto",
    force: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    """
    Executes or dry-run validates `16:9` chapter-sharded Google Flow clip generation into
    `03_visuals/flow_native_clips/clip_001.mp4 .. clip_NNN.mp4`, recording cryptographic provenance
    (including `reference_image` and `reference_attached`) in `03_visuals/flow_provenance_receipt.json`.
    """
    p_dir = resolve_longform_project_dir(project_id_or_dir, create=False)
    vis_dir = p_dir / "03_visuals"
    prompts_path = vis_dir / "flow_longform_prompts.json"
    if not prompts_path.exists():
        raise FileNotFoundError(f"Missing flow_longform_prompts.json: {prompts_path}")

    p_doc = json.loads(prompts_path.read_text(encoding="utf-8"))
    clips_all = list(p_doc.get("clips") or [])
    clips_by_num = {int(c["clip_number"]): c for c in clips_all}
    shards = list(p_doc.get("shards") or build_flow_shards(clips_all, max_per_shard=LONGFORM_SHARD_MAX_CLIPS))
    clips_dir = vis_dir / "flow_native_clips"
    flow_dl_dir = vis_dir / "flow_downloads"
    clips_dir.mkdir(parents=True, exist_ok=True)
    flow_dl_dir.mkdir(parents=True, exist_ok=True)
    prov_path = vis_dir / "flow_provenance_receipt.json"

    parsed_only = parse_longform_clip_spec(only_clips)
    target_set: set[int] = {int(c["clip_number"]) for c in clips_all}
    if shard_index is not None:
        matched_sh = [s for s in shards if int(s["shard_index"]) == int(shard_index)]
        if not matched_sh:
            raise ValueError(f"Shard {shard_index} not found (valid: 1..{len(shards)})")
        target_set &= {int(n) for n in matched_sh[0]["clip_numbers"]}
    if parsed_only:
        target_set &= set(parsed_only)

    selected_clips = [c for c in clips_all if int(c["clip_number"]) in target_set]
    eff_tabs = max(1, min(3, int(tabs)))

    # Load prior provenance entries so partial `--clips` runs and resumes preserve verified metadata
    existing_prov_clips: dict[int, dict[str, Any]] = {}
    prev_shard_urls: list[str] = []
    prev_shard_tabs: list[str] = []
    if prov_path.exists():
        try:
            prev_prov = json.loads(prov_path.read_text(encoding="utf-8"))
            if isinstance(prev_prov, dict):
                prev_shard_urls = [str(u) for u in (prev_prov.get("shard_urls") or []) if u]
                prev_shard_tabs = [str(t) for t in (prev_prov.get("shard_tab_ids") or []) if t]
                for entry in (prev_prov.get("clips") or []):
                    if isinstance(entry, dict):
                        c_idx = int(entry.get("clip_index") or entry.get("clip_number") or 0)
                        if c_idx > 0:
                            existing_prov_clips[c_idx] = dict(entry)
        except Exception:
            pass

    already_ready: list[int] = []
    pending_clips: list[dict[str, Any]] = []
    seen_global_shas: set[str] = set()

    # Seed global SHA set from all existing valid clips on disk (including outside target_set on partial runs)
    for existing_mp4 in sorted(clips_dir.glob("clip_*.mp4")):
        m_num = re.match(r"^clip_(\d+)\.mp4$", existing_mp4.name)
        if not m_num or not existing_mp4.is_file():
            continue
        ex_num = int(m_num.group(1))
        if force and ex_num in target_set:
            continue
        if existing_mp4.stat().st_size >= 25_000:
            seen_global_shas.add(hashlib.sha256(existing_mp4.read_bytes()).hexdigest().lower())

    for c in selected_clips:
        c_num = int(c["clip_number"])
        out_mp4 = clips_dir / f"clip_{c_num:03d}.mp4"
        if out_mp4.exists() and not force:
            cv_rep = inspect_longform_16x9_clip_cv(
                out_mp4,
                min_duration_sec=float(c.get("target_duration_sec") or 3.2),
                grammar=str(c.get("grammar") or ""),
                reference_path=_resolve_clip_ref_path(p_dir, c.get("reference_image")),
            )
            if cv_rep.get("passed"):
                already_ready.append(c_num)
                continue
        pending_clips.append(c)

    live_prov_clips: dict[int, dict[str, Any]] = {}
    live_shard_urls: list[str] = []
    live_shard_tabs: list[str] = []
    t_run_start = time.time()

    def _persist_provenance_snapshot(*, partial: bool) -> dict[str, Any]:
        merged: dict[int, dict[str, Any]] = {}
        for k_idx, old_rec in existing_prov_clips.items():
            if (clips_dir / f"clip_{k_idx:03d}.mp4").exists():
                merged[k_idx] = dict(old_rec)
        for k_idx, new_rec in live_prov_clips.items():
            if (clips_dir / f"clip_{k_idx:03d}.mp4").exists():
                comb = dict(merged.get(k_idx) or {})
                comb.update(new_rec)
                merged[k_idx] = comb

        for mp4_f in sorted(clips_dir.glob("clip_*.mp4")):
            m_idx = re.match(r"^clip_(\d+)\.mp4$", mp4_f.name)
            if not m_idx or not mp4_f.is_file() or mp4_f.stat().st_size < 25_000:
                continue
            idx = int(m_idx.group(1))
            prior = merged.get(idx) or {}
            c_spec_d = clips_by_num.get(idx) or {}
            bound_ref = _resolve_clip_ref_path(p_dir, c_spec_d.get("reference_image"))
            default_model = FLOW_ZERO_CREDIT_MODEL if str(engine_mode).lower().replace("_", "-") == "zero-credit" else FLOW_PRIMARY_VIDEO_MODEL
            used_m = str(prior.get("flow_model") or prior.get("model") or default_model)
            c_tier = str(
                prior.get("credit_tier")
                or ("zero_credit_fallback" if used_m == FLOW_ZERO_CREDIT_MODEL else "omni_monthly_credit")
            )
            sha_hex = str(prior.get("sha256") or hashlib.sha256(mp4_f.read_bytes()).hexdigest().lower())
            st_f = mp4_f.stat()
            ref_img_val = prior.get("reference_image") if "reference_image" in prior else (bound_ref.name if bound_ref is not None else None)
            ref_att_val = bool(prior["reference_attached"]) if "reference_attached" in prior else False
            entry: dict[str, Any] = {
                "clip_index": idx,
                "clip_number": idx,
                "filename": mp4_f.name,
                "aspect": FLOW_ASPECT_LONGFORM,
                "sha256": sha_hex,
                "file_size_bytes": st_f.st_size,
                "source_download_filename": str(prior.get("source_download_filename") or f"flow_direct_{mp4_f.name}"),
                "downloaded_at_epoch": prior.get("downloaded_at_epoch") or round(st_f.st_mtime, 3),
                "flow_model": used_m,
                "model": used_m,
                "credit_tier": c_tier,
                "zero_credit_verified": bool(c_tier == "zero_credit_fallback" or used_m == FLOW_ZERO_CREDIT_MODEL),
                "reference_image": ref_img_val,
                "reference_attached": ref_att_val,
            }
            if prior.get("cv_qa"):
                entry["cv_qa"] = prior["cv_qa"]
            merged[idx] = entry

        ordered_entries = [merged[k] for k in sorted(merged)]
        seen_models: list[str] = []
        for ce in ordered_entries:
            mv = str(ce.get("flow_model") or "").strip()
            if mv and mv not in seen_models:
                seen_models.append(mv)
        default_top_m = FLOW_ZERO_CREDIT_MODEL if str(engine_mode).lower().replace("_", "-") == "zero-credit" else FLOW_PRIMARY_VIDEO_MODEL
        resolved_model = seen_models[0] if len(seen_models) == 1 else (" -> ".join(seen_models) if seen_models else default_top_m)
        zero_verified = bool(ordered_entries and all(bool(ce.get("zero_credit_verified")) for ce in ordered_entries))
        merged_urls = list(dict.fromkeys([*live_shard_urls, *prev_shard_urls]))
        merged_tabs = list(dict.fromkeys([*live_shard_tabs, *prev_shard_tabs]))

        prov_doc: dict[str, Any] = {
            "schema": "longform_flow_provenance_receipt_v1",
            "project_id": p_dir.name,
            "worker_id": f"subagent-{p_dir.name}",
            "subagent_1_to_1_bound": True,
            "aspect": FLOW_ASPECT_LONGFORM,
            "engine_mode": engine_mode,
            "flow_model": resolved_model,
            "model": resolved_model,
            "zero_credit_verified": zero_verified,
            "zero_clip_reuse": True,
            "partial_receipt": bool(partial or (len(ordered_entries) < len(clips_all))),
            "flow_project_url": merged_urls[0] if merged_urls else "",
            "tab_target_id": merged_tabs[0] if merged_tabs else "",
            "shard_urls": merged_urls,
            "shard_tab_ids": merged_tabs,
            "prompts_submitted_count": len(ordered_entries),
            "elapsed_sec": round(time.time() - t_run_start, 1),
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "clips": ordered_entries,
        }
        tmp_p = prov_path.with_suffix(f".json.tmp.{os.getpid()}.{int(time.time() * 1000000)}")
        tmp_p.write_text(json.dumps(prov_doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        os.replace(tmp_p, prov_path)
        return prov_doc

    if dry_run or not pending_clips:
        receipt = {
            "schema": "longform_flow_receipt_v1",
            "project_id": p_dir.name,
            "aspect": FLOW_ASPECT_LONGFORM,
            "tabs_capped": eff_tabs,
            "shard_count": len(shards),
            "selected_count": len(selected_clips),
            "cached_ready_count": len(already_ready),
            "pending_count": len(pending_clips),
            "completed_clips": sorted(already_ready),
            "failed_clips": [],
            "passed": len(pending_clips) == 0,
            "dry_run": bool(dry_run),
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }
        if not dry_run:
            _persist_provenance_snapshot(partial=len(already_ready) < len(clips_all))
            (vis_dir / "flow_generation_receipt.json").write_text(
                json.dumps(receipt, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
        return receipt

    from pipeline.flow_diorama_sharded_worker import (
        _reinforce_porcelain_cv_retry_prompt,
        _soften_veo_false_positive_words,
    )
    from pipeline.flow_live_single_worker import allocate_dedicated_flow_project_tab
    from pipeline.studio.whale_session import DirectCDPClient

    completed: list[int] = list(already_ready)
    failed: list[int] = []
    credit_exhausted_event = asyncio.Event()
    if str(engine_mode or "").strip().lower().replace("_", "-") == "zero-credit":
        credit_exhausted_event.set()
    tab_open_lock = asyncio.Lock()
    sem = asyncio.Semaphore(eff_tabs)

    def _close_tab(tid: str | None) -> None:
        if not tid:
            return
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{cdp_port}/json/close/{tid}", timeout=5):
                pass
        except Exception:
            pass

    eff_shard_size = min(
        LONGFORM_SHARD_MAX_CLIPS,
        max(1, (len(pending_clips) + eff_tabs - 1) // max(1, eff_tabs)),
    )
    shard_batches = [
        pending_clips[sh_start : sh_start + eff_shard_size]
        for sh_start in range(0, len(pending_clips), eff_shard_size)
    ]

    async def _run_single_shard(sh_idx: int, shard_batch: list[dict[str, Any]]) -> None:
        async with sem:
            tab_id: str | None = None
            cm = None
            try:
                async with tab_open_lock:
                    alloc = await allocate_dedicated_flow_project_tab(cdp_port=cdp_port)
                    tab_id = str(alloc["tab_id"])
                    proj_url = str(alloc.get("project_url") or "")
                    if proj_url and proj_url not in live_shard_urls:
                        live_shard_urls.append(proj_url)
                    if tab_id and tab_id not in live_shard_tabs:
                        live_shard_tabs.append(tab_id)
                    await asyncio.sleep(0.5)
                cm = DirectCDPClient(str(alloc["ws_url"]))
                client = await cm.__aenter__()
                await client.send("Page.enable")
                await _configure_longform_video_16x9_tab(
                    client,
                    engine_mode=engine_mode,
                    credit_exhausted_event=credit_exhausted_event,
                )

                uploaded_cache: set[str] = set()
                seen_urls: set[str] = set()
                for item_pos, c_spec in enumerate(shard_batch, start=1):
                    c_num = int(c_spec["clip_number"])
                    grammar = str(c_spec.get("grammar") or "")
                    out_mp4 = clips_dir / f"clip_{c_num:03d}.mp4"
                    ref_path = _resolve_clip_ref_path(p_dir, c_spec.get("reference_image"))
                    ok_clip = False
                    last_cv_reason = ""
                    base_prompt = str(c_spec["prompt"])
                    for _attempt in range(4):
                        if _attempt == 2:
                            try:
                                await client.send("Page.reload", {"ignoreCache": False})
                                await asyncio.sleep(5.5)
                                await _configure_longform_video_16x9_tab(
                                    client,
                                    engine_mode=engine_mode,
                                    credit_exhausted_event=credit_exhausted_event,
                                )
                            except Exception:
                                pass

                        eff_prompt = base_prompt
                        if _attempt >= 1:
                            eff_prompt = _soften_veo_false_positive_words(
                                eff_prompt,
                                style_profile="porcelain_cinematic_v7",
                                grammar=grammar,
                            )
                            if last_cv_reason:
                                eff_prompt = _reinforce_porcelain_cv_retry_prompt(
                                    eff_prompt,
                                    grammar=grammar,
                                    cv_reason=last_cv_reason,
                                )
                                eff_prompt = _reinforce_longform_yunet_retry_prompt(
                                    eff_prompt,
                                    grammar=grammar,
                                    cv_reason=last_cv_reason,
                                )

                        print(
                            f"[LF-Shard {sh_idx}] Clip {c_num:03d} ({item_pos}/{len(shard_batch)}, "
                            f"try {_attempt + 1}/4, ref={ref_path.name if ref_path else 'none'})...",
                            flush=True,
                        )
                        try:
                            res_c = await _generate_single_longform_16x9_clip_in_tab(
                                client=client,
                                clip_num=c_num,
                                prompt_text=eff_prompt,
                                out_mp4=out_mp4,
                                start_ref=ref_path,
                                uploaded_cache=uploaded_cache,
                                seen_video_urls=seen_urls,
                                flow_dl_dir=flow_dl_dir,
                                seen_global_shas=seen_global_shas,
                                shard_id=sh_idx,
                                project_slug=p_dir.name,
                                engine_mode=engine_mode,
                                credit_exhausted_event=credit_exhausted_event,
                                tab_upload_lock=tab_open_lock,
                            )
                        except Exception as tab_exc:
                            print(f"[LF-Shard {sh_idx}] Clip {c_num:03d} transient exception ({tab_exc}); rotating tab...", flush=True)
                            try:
                                if cm is not None:
                                    await cm.__aexit__(None, None, None)
                            except Exception:
                                pass
                            _close_tab(tab_id)
                            tab_id = None
                            cm = None
                            for _rot_try in range(3):
                                try:
                                    await asyncio.sleep(1.5 + _rot_try * 2.0)
                                    async with tab_open_lock:
                                        alloc = await allocate_dedicated_flow_project_tab(cdp_port=cdp_port)
                                        tab_id = str(alloc["tab_id"])
                                        proj_url = str(alloc.get("project_url") or "")
                                        if proj_url and proj_url not in live_shard_urls:
                                            live_shard_urls.append(proj_url)
                                        if tab_id and tab_id not in live_shard_tabs:
                                            live_shard_tabs.append(tab_id)
                                        await asyncio.sleep(0.5)
                                    cm = DirectCDPClient(str(alloc["ws_url"]))
                                    client = await cm.__aenter__()
                                    await client.send("Page.enable")
                                    await _configure_longform_video_16x9_tab(
                                        client,
                                        engine_mode=engine_mode,
                                        credit_exhausted_event=credit_exhausted_event,
                                    )
                                    break
                                except Exception as rot_exc:
                                    print(f"[LF-Shard {sh_idx}] Tab rotation retry {_rot_try + 1}/3 failed ({rot_exc})", flush=True)
                                    _close_tab(tab_id)
                                    tab_id = None
                            uploaded_cache.clear()
                            seen_urls.clear()
                            res_c = {"ok": False, "reason": f"tab_rotated_after_{type(tab_exc).__name__}"}

                        if res_c.get("ok") and out_mp4.exists():
                            cv_chk = inspect_longform_16x9_clip_cv(
                                out_mp4,
                                min_duration_sec=float(c_spec.get("target_duration_sec") or 3.2),
                                grammar=grammar,
                                reference_path=ref_path,
                            )
                            if cv_chk.get("passed"):
                                sha_now = str(res_c.get("sha256") or hashlib.sha256(out_mp4.read_bytes()).hexdigest().lower())
                                seen_global_shas.add(sha_now)
                                st_now = out_mp4.stat()
                                used_m = str(
                                    res_c.get("flow_model")
                                    or (FLOW_ZERO_CREDIT_MODEL if credit_exhausted_event.is_set() else FLOW_PRIMARY_VIDEO_MODEL)
                                )
                                c_tier = str(
                                    res_c.get("credit_tier")
                                    or ("zero_credit_fallback" if used_m == FLOW_ZERO_CREDIT_MODEL else "omni_monthly_credit")
                                )
                                live_prov_clips[c_num] = {
                                    "clip_index": c_num,
                                    "clip_number": c_num,
                                    "filename": out_mp4.name,
                                    "aspect": FLOW_ASPECT_LONGFORM,
                                    "sha256": sha_now,
                                    "file_size_bytes": st_now.st_size,
                                    "source_download_filename": str(
                                        res_c.get("source_download_filename") or f"flow_direct_{out_mp4.name}"
                                    ),
                                    "downloaded_at_epoch": round(st_now.st_mtime, 3),
                                    "flow_model": used_m,
                                    "model": used_m,
                                    "credit_tier": c_tier,
                                    "zero_credit_verified": bool(
                                        res_c.get("zero_credit_verified") or used_m == FLOW_ZERO_CREDIT_MODEL
                                    ),
                                    "reference_image": ref_path.name if ref_path is not None else None,
                                    "reference_attached": bool(
                                        res_c.get("reference_attached") if "reference_attached" in res_c else (ref_path is not None)
                                    ),
                                    "cv_qa": cv_chk,
                                }
                                completed.append(c_num)
                                _persist_provenance_snapshot(partial=True)
                                print(
                                    f"[LF-Shard {sh_idx}] DONE Clip {c_num:03d} "
                                    f"({cv_chk['width']}x{cv_chk['height']}, {cv_chk['duration_sec']}s, "
                                    f"motion={cv_chk['motion_mean']}, ref_attached={live_prov_clips[c_num]['reference_attached']})",
                                    flush=True,
                                )
                                ok_clip = True
                                break
                            last_cv_reason = ",".join(cv_chk.get("failed_gates") or [])
                            print(
                                f"[LF-Shard {sh_idx}] Clip {c_num:03d} failed CV ({last_cv_reason}); regenerating...",
                                flush=True,
                            )
                            out_mp4.unlink(missing_ok=True)
                        else:
                            fail_r = str(res_c.get("reason") or "unknown")
                            print(
                                f"[LF-Shard {sh_idx}] Clip {c_num:03d} attempt {_attempt + 1} failed ({fail_r})",
                                flush=True,
                            )
                            if fail_r == "flow_tile_error":
                                await asyncio.sleep(10.0 * (_attempt + 1))
                            else:
                                await asyncio.sleep(2.5)
                    if not ok_clip:
                        failed.append(c_num)
            finally:
                if cm is not None:
                    try:
                        await cm.__aexit__(None, None, None)
                    except Exception:
                        pass
                _close_tab(tab_id)

    await asyncio.gather(*(_run_single_shard(idx_s, b) for idx_s, b in enumerate(shard_batches, start=1)))

    prov_doc = _persist_provenance_snapshot(
        partial=(len(failed) > 0)
    )
    receipt = {
        "schema": "longform_flow_receipt_v1",
        "project_id": p_dir.name,
        "aspect": FLOW_ASPECT_LONGFORM,
        "tabs_capped": eff_tabs,
        "engine_mode": engine_mode,
        "zero_credit_verified": bool(prov_doc.get("zero_credit_verified")),
        "provenance_receipt": str(prov_path),
        "completed_clips": sorted(set(completed)),
        "failed_clips": sorted(set(failed)),
        "passed": len(failed) == 0,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }
    (vis_dir / "flow_generation_receipt.json").write_text(
        json.dumps(receipt, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description="Standalone 16:9 Google Flow chapter-sharded worker")
    parser.add_argument("--project", required=True, help="Target Long-Form project_id or path")
    parser.add_argument("--tabs", type=int, default=3, help="Max concurrent Flow tabs (capped <= 3)")
    parser.add_argument("--shard", type=int, default=None, help="Optional 1-based shard index")
    parser.add_argument("--clips", default="", help="Optional clip selector (e.g. '1-2' or '1,2,5-8')")
    parser.add_argument("--cdp-port", type=int, default=DEFAULT_CDP_PORT, help="Whale DevTools CDP port")
    parser.add_argument("--engine", default="auto", choices=["auto", "omni", "zero-credit"], help="Flow engine mode")
    parser.add_argument("--dry-run", action="store_true", default=False, help="Dry-run shard plan")
    parser.add_argument("--force", action="store_true", default=False, help="Regenerate existing clips")
    args = parser.parse_args()

    res = asyncio.run(
        run_longform_sharded_flow_generation(
            args.project,
            tabs=int(args.tabs),
            shard_index=args.shard,
            only_clips=args.clips or None,
            cdp_port=int(args.cdp_port),
            engine_mode=str(args.engine),
            force=bool(args.force),
            dry_run=bool(args.dry_run),
        )
    )
    print(json.dumps(res, indent=2, ensure_ascii=False))
    if not args.dry_run and res.get("failed_clips"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
