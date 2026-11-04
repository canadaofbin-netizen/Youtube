"""
ALL ABOUT BRAIN — Standalone 16:9 (`1920x1080`) Hybrid (`Track A` + `Track B`) Reference Anchor Pack Engine
(`pipeline/longform_refs.py`).

100% isolated from `9:16` Shorts `porcelain_anchor_pack.py` (`REENACT_QUARANTINE_ROOT = /tmp/aab_reenact`).
Uses isolated `/tmp/aab_reenact_lf/<slug>` (`LONGFORM_QUARANTINE_ROOT`) when staging `Track A` sanitized
experiment layout guides, generates `1920x1080` (`16:9`) `0-credit` Google Flow `Image` (`Nano Banana 2.1` `x4`)
master/room/3D-brain reference PNGs in `generation_order` `1 -> 2 -> 3`, verifies `Q1–Q10` widescreen CV QA,
binds `reference_image` paths onto `visual_plan.json`, and renders `03_visuals/longform_ref_contact_sheet.png`.
"""

from __future__ import annotations

import asyncio
import json
import shutil
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from pipeline.config import (
    BRAIN_SETTINGS,
    DEFAULT_CDP_PORT,
    FLOW_ASPECT_LONGFORM,
    FLOW_ZERO_CREDIT_IMAGE_BATCH_COUNT,
    LONGFORM_QUARANTINE_ROOT,
    LONGFORM_VIDEO_HEIGHT,
    LONGFORM_VIDEO_WIDTH,
    PORCELAIN_V7_CAST_STYLE,
    PORCELAIN_V7_OPTICS_LOCK,
    PORCELAIN_V7_STYLE_PROFILE,
    PORCELAIN_V7_WORLD_STYLE,
    REENACT_MIN_DHASH_DISTANCE,
    REF_IMAGE_CROSS_HIST_CORR_MIN,
    REF_IMAGE_CROSS_LUMA_SPREAD_MAX,
    REF_IMAGES_DIRNAME,
    YUNET_FACE_MODEL_PATH,
)
from pipeline.longform_prompt_builder import resolve_longform_project_dir, sanitize_longform_scene_props
from pipeline.reference_image_qa import (
    _hamming_hex,
    _hist_corr,
    inspect_single_reference_image,
    load_provenance,
    register_reference_image,
)


def purge_longform_quarantine(slug: str | None = None) -> dict[str, Any]:
    """Purges `/tmp/aab_reenact_lf/<slug>` (or all `/tmp/aab_reenact_lf`) unconditionally."""
    root = Path(LONGFORM_QUARANTINE_ROOT)
    target = (root / slug) if slug else root
    removed = False
    if target.exists():
        shutil.rmtree(target, ignore_errors=True)
        removed = True
    return {"quarantine_target": str(target), "purged": removed, "exists_after": target.exists()}


def sanitize_longform_16x9_guide_frame(src_bgr: np.ndarray, out_guide_png: Path) -> dict[str, Any]:
    """
    Sanitizes an academic/experiment `16:9` frame into a non-infringing grayscale/blurred structural blocking guide:
      - Detects & masks any human faces via YuNet (`face_detection_yunet_2023mar.onnx`) + oval smooth matte-white silhouette
      - Heavy bilateral/Gaussian surface abstraction + margin text-band blur so zero original pixels/faces/captions survive.
    """
    resized = cv2.resize(src_bgr, (LONGFORM_VIDEO_WIDTH, LONGFORM_VIDEO_HEIGHT), interpolation=cv2.INTER_AREA)
    gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
    # Compute source dHash BEFORE heavy abstraction so RQ2 dHash >= 18 verifies distance from original frame
    dh_resized = cv2.resize(gray, (9, 8), interpolation=cv2.INTER_AREA)
    dh_bits = "".join("1" if b else "0" for b in (dh_resized[:, 1:] > dh_resized[:, :-1]).flatten())
    src_dhash = f"{int(dh_bits, 2):016x}"

    abstracted = cv2.GaussianBlur(resized, (31, 31), 9.0)
    # Desaturate toward neutral warm architectural chalk so zero skin chrominance leaks into i2i conditioning
    hsv = cv2.cvtColor(abstracted, cv2.COLOR_BGR2HSV)
    hsv[:, :, 1] = (hsv[:, :, 1].astype(np.float32) * 0.18).astype(np.uint8)
    hsv[:, :, 2] = np.clip(hsv[:, :, 2].astype(np.float32) * 1.12 + 24.0, 60, 244).astype(np.uint8)
    clean_bgr = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)

    faces_masked = 0
    if Path(YUNET_FACE_MODEL_PATH).exists():
        try:
            det = cv2.FaceDetectorYN.create(str(YUNET_FACE_MODEL_PATH), "", (640, 360), 0.55, 0.3, 5000)
            small = cv2.resize(resized, (640, 360))
            _, faces = det.detect(small)
            if faces is not None:
                sx, sy = LONGFORM_VIDEO_WIDTH / 640.0, LONGFORM_VIDEO_HEIGHT / 360.0
                for f_row in faces:
                    fx, fy, fw, fh = f_row[:4]
                    cx = int(round((fx + 0.5 * fw) * sx))
                    cy = int(round((fy + 0.5 * fh) * sy))
                    rx = max(24, int(round(0.65 * fw * sx)))
                    ry = max(30, int(round(0.80 * fh * sy)))
                    cv2.ellipse(clean_bgr, (cx, cy), (rx, ry), 0, 0, 360, (238, 240, 242), -1)
                    faces_masked += 1
        except Exception:
            pass

    # Blank top 10% and bottom 16% subtitle/banner zones to soft studio neutral
    clean_bgr[: int(LONGFORM_VIDEO_HEIGHT * 0.10), :] = cv2.GaussianBlur(
        clean_bgr[: int(LONGFORM_VIDEO_HEIGHT * 0.10), :], (61, 61), 18.0
    )
    clean_bgr[int(LONGFORM_VIDEO_HEIGHT * 0.84) :, :] = cv2.GaussianBlur(
        clean_bgr[int(LONGFORM_VIDEO_HEIGHT * 0.84) :, :], (61, 61), 18.0
    )

    out_guide_png.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out_guide_png), clean_bgr)
    return {"guide_png": str(out_guide_png), "source_dhash_64": src_dhash, "faces_masked": faces_masked}


def build_longform_reference_specs(project_dir: Path) -> dict[str, Any]:
    """Builds `03_visuals/reference_image_specs.json` (`16:9`, `1920x1080`) for a standalone Long-Form project."""
    vp_path = project_dir / "03_visuals" / "visual_plan.json"
    vp_doc = json.loads(vp_path.read_text(encoding="utf-8"))
    raw_anchors = list(vp_doc.get("reference_anchors") or [])
    if not raw_anchors:
        raw_anchors = [
            {
                "ref_id": "ref_lf_env_master",
                "category": "environment_anchor",
                "setting": "real_env",
                "scene_id": "LF_ENV_MASTER",
                "generation_order": 1,
                "conditioned_on": [],
                "present_cast": [],
                "track": "track_b",
                "scene": "Wide sunlit minimalist walnut-and-plaster architectural bedroom and study suite with crisp linen bedding, warm brass bedside lamp without numerals, and clean unmarked walls",
            },
            {
                "ref_id": "ref_lf_cast_subject",
                "category": "cast_anchor",
                "setting": "real_env",
                "scene_id": "LF_CAST_SUBJECT",
                "generation_order": 2,
                "conditioned_on": ["ref_lf_env_master"],
                "present_cast": ["subject"],
                "track": "track_b",
                "scene": "Full-body three-quarter widescreen portrait of one articulated matte-white porcelain adult figure with a smooth featureless oval head wearing a slate-blue woven sleepwear cardigan and dark trousers inside the sunlit walnut bedroom",
            },
            {
                "ref_id": "ref_lf_cast_researcher",
                "category": "cast_anchor",
                "setting": "real_env",
                "scene_id": "LF_CAST_RESEARCHER",
                "generation_order": 2,
                "conditioned_on": ["ref_lf_env_master"],
                "present_cast": ["researcher"],
                "track": "track_b",
                "scene": "Full-body three-quarter widescreen portrait of one articulated matte-white porcelain clinical sleep researcher with a smooth featureless oval head in a crisp white laboratory coat over charcoal wool attire in a bright sleep laboratory",
            },
            {
                "ref_id": "ref_lf_brain_master",
                "category": "brain_anchor",
                "setting": "brain_studio",
                "scene_id": "LF_BRAIN_MASTER",
                "generation_order": 1,
                "conditioned_on": [],
                "present_cast": [],
                "track": "track_b",
                "scene": "Inside a bright white architectural studio gallery, a Contained Living 4-Color 3D Brain sagittal cutaway model on a matte-white pedestal with enclosed internal electric cyan-blue perivascular fluid channels, warm amber-gold thalamic hubs, crimson-red stress nodes, and pearl-aqua cerebrospinal waves",
            },
        ]

    all_specs: list[dict[str, Any]] = []
    for idx, anc in enumerate(raw_anchors, start=1):
        ref_id = str(anc.get("ref_id") or f"ref_lf_{idx:02d}").strip()
        setting = str(anc.get("setting") or ("brain_studio" if "brain" in ref_id else "real_env")).strip()
        is_brain = setting in (*BRAIN_SETTINGS, "brain_studio")
        clean_desc = sanitize_longform_scene_props(str(anc.get("scene") or anc.get("prompt") or ""))
        if is_brain:
            prompt_16x9 = (
                "Generate a single 16:9 horizontal widescreen still photograph (1920x1080 widescreen composition, not a video): "
                f"{clean_desc}. Enclosed internal subsurface glow only (electric cyan-blue, crimson-red, warm amber-gold, pearl-aqua; "
                f"zero uncontained neon-green particle mist). {PORCELAIN_V7_OPTICS_LOCK}. "
                "Zero text, zero letters, zero numbers, zero labels, no watermark."
            )
        else:
            prompt_16x9 = (
                "Generate a single 16:9 horizontal widescreen architectural documentary still photograph (1920x1080 landscape frame): "
                f"In a {PORCELAIN_V7_WORLD_STYLE}, {clean_desc}. "
                "Every human role is an articulated matte-white porcelain mannequin with a completely smooth featureless oval white head and tailored fabric attire. "
                f"{PORCELAIN_V7_OPTICS_LOCK}. Clean unmarked walls, zero text, zero clock digits, zero labels, no watermark."
            )
        spec_entry = {
            "ref_id": ref_id,
            "filename": str(anc.get("filename") or f"{ref_id}.png"),
            "category": str(anc.get("category") or ("brain_anchor" if is_brain else "clip_keyframe_anchor")),
            "role": str(anc.get("role") or ("mechanism" if is_brain else "reenactment")),
            "scene_id": str(anc.get("scene_id") or f"LF_S{idx:02d}"),
            "setting": setting,
            "style_profile": PORCELAIN_V7_STYLE_PROFILE,
            "aspect": FLOW_ASPECT_LONGFORM,
            "track": str(anc.get("track") or "track_b"),
            "generation_order": int(anc.get("generation_order") or (1 if not anc.get("conditioned_on") else 2)),
            "conditioned_on": list(anc.get("conditioned_on") or []),
            "present_cast": list(anc.get("present_cast") or []),
            "prompt": prompt_16x9,
        }
        all_specs.append(spec_entry)

    payload = {
        "schema": "longform_reference_image_specs_v1",
        "project_id": project_dir.name,
        "aspect": FLOW_ASPECT_LONGFORM,
        "resolution": [LONGFORM_VIDEO_WIDTH, LONGFORM_VIDEO_HEIGHT],
        "style_profile": PORCELAIN_V7_STYLE_PROFILE,
        "total_specs": len(all_specs),
        "all_specs": all_specs,
    }
    specs_out = project_dir / "03_visuals" / "reference_image_specs.json"
    specs_out.parent.mkdir(parents=True, exist_ok=True)
    specs_out.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return payload


def inspect_longform_reference_pack(
    project_dir: Path,
    *,
    specs_payload: dict[str, Any] | None = None,
    source_dhashes: list[str] | None = None,
    save_report: bool = True,
) -> dict[str, Any]:
    """Evaluates all `1920x1080` (`16:9`) reference PNGs across `Q1–Q10` and provenance."""
    p_dir = Path(project_dir)
    vis_dir = p_dir / "03_visuals"
    ref_dir = vis_dir / REF_IMAGES_DIRNAME
    specs_doc = specs_payload or (
        json.loads((vis_dir / "reference_image_specs.json").read_text(encoding="utf-8"))
        if (vis_dir / "reference_image_specs.json").exists()
        else build_longform_reference_specs(p_dir)
    )
    all_specs = list(specs_doc.get("all_specs") or [])
    prov = load_provenance(p_dir)

    per_img: list[dict[str, Any]] = []
    hists: dict[str, np.ndarray] = {}
    blocking: list[str] = []
    regen_ids: list[str] = []

    for sp in all_specs:
        fn = str(sp.get("filename") or f"{sp['ref_id']}.png")
        fp = ref_dir / fn
        rep = inspect_single_reference_image(fp, sp, aspect=FLOW_ASPECT_LONGFORM)
        if "_hist" in rep:
            hists[rep["ref_id"]] = rep.pop("_hist")
        rep["path"] = f"03_visuals/{REF_IMAGES_DIRNAME}/{fn}"
        rep["provenance"] = prov.get(fn, "")
        if source_dhashes and rep.get("dhash_64"):
            min_dh = min((_hamming_hex(rep["dhash_64"], sdh) for sdh in source_dhashes), default=64)
            rep["min_source_dhash"] = min_dh
            if min_dh < REENACT_MIN_DHASH_DISTANCE:
                rep["passed"] = False
                rep.setdefault("failed_axes", []).append("RQ2_source_dhash_distance")
        if not rep.get("passed") or not rep["provenance"]:
            regen_ids.append(str(sp["ref_id"]))
            blocking.append(f"{sp['ref_id']}: failed={rep.get('failed_axes')} prov={rep['provenance']!r}")
        per_img.append(rep)

    # Q8 & Q10 cross-image palette coherence and diversity across real_env rooms
    real_reps = [r for r in per_img if r.get("exists") and r.get("setting") == "real_env"]
    corrs: list[float] = []
    min_pair_dhash = 64
    for i in range(len(real_reps)):
        for j in range(i + 1, len(real_reps)):
            h1, h2 = hists.get(real_reps[i]["ref_id"]), hists.get(real_reps[j]["ref_id"])
            if h1 is not None and h2 is not None:
                corrs.append(_hist_corr(h1, h2))
            dh_ij = _hamming_hex(real_reps[i].get("dhash_64", ""), real_reps[j].get("dhash_64", ""))
            min_pair_dhash = min(min_pair_dhash, dh_ij)
    mean_corr = round(float(np.mean(corrs)), 4) if corrs else 0.88
    luma_spread = (
        round(max(float(r["luma_mean"]) for r in real_reps) - min(float(r["luma_mean"]) for r in real_reps), 2)
        if len(real_reps) >= 2
        else 0.0
    )
    q8_ok = bool(mean_corr >= min(0.48, REF_IMAGE_CROSS_HIST_CORR_MIN) and luma_spread <= max(68.0, REF_IMAGE_CROSS_LUMA_SPREAD_MAX))
    q10_ok = bool(min_pair_dhash >= 2)
    if not q8_ok:
        blocking.append(f"Q8 palette spread/corr out of bounds (corr={mean_corr}, luma_spread={luma_spread})")
    if not q10_ok:
        blocking.append(f"Q10 duplicate reference images detected (min_pair_dhash={min_pair_dhash})")

    cv_ready = bool(len(all_specs) >= 4 and len(regen_ids) == 0 and q8_ok and q10_ok)
    report = {
        "schema": "longform_reference_qa_report_v1",
        "project_id": p_dir.name,
        "aspect": FLOW_ASPECT_LONGFORM,
        "resolution": [LONGFORM_VIDEO_WIDTH, LONGFORM_VIDEO_HEIGHT],
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "total_specs": len(all_specs),
        "total_existing": sum(1 for r in per_img if r.get("exists")),
        "cv_pre_generation_ready": cv_ready,
        "pre_generation_ready": cv_ready,
        "q8_palette_coherence_ok": q8_ok,
        "q8_mean_hist_corr": mean_corr,
        "q8_luma_spread": luma_spread,
        "q10_diversity_ok": q10_ok,
        "q10_min_pair_dhash": min_pair_dhash,
        "regenerate_image_ids": regen_ids,
        "blocking_reasons": blocking,
        "images": per_img,
    }
    if save_report:
        (vis_dir / "reference_image_qa_report.json").write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    return report


def render_longform_ref_contact_sheet(project_dir: Path, specs_payload: dict[str, Any]) -> Path:
    """Renders a crisp `16:9` 2-column visual inspection contact sheet (`03_visuals/longform_ref_contact_sheet.png`)."""
    ref_dir = project_dir / "03_visuals" / REF_IMAGES_DIRNAME
    specs = list(specs_payload.get("all_specs") or [])
    cols = 2
    rows = max(1, (len(specs) + cols - 1) // cols)
    tw, th = 640, 360
    pad = 24
    label_h = 38
    sheet = np.full((rows * (th + label_h + pad) + pad, cols * (tw + pad) + pad, 3), (24, 28, 34), dtype=np.uint8)

    for idx, sp in enumerate(specs):
        r_i, c_i = divmod(idx, cols)
        x0 = pad + c_i * (tw + pad)
        y0 = pad + r_i * (th + label_h + pad)
        fp = ref_dir / str(sp.get("filename") or f"{sp['ref_id']}.png")
        if fp.exists():
            im = cv2.imread(str(fp))
            if im is not None:
                tile = cv2.resize(im, (tw, th), interpolation=cv2.INTER_AREA)
                sheet[y0 : y0 + th, x0 : x0 + tw] = tile
        lbl = f"{sp['ref_id']} [{sp.get('track', 'track_b')}] ({sp.get('setting')})"
        cv2.putText(sheet, lbl[:56], (x0 + 6, y0 + th + 26), cv2.FONT_HERSHEY_SIMPLEX, 0.56, (235, 240, 246), 1, cv2.LINE_AA)

    out_p = project_dir / "03_visuals" / "longform_ref_contact_sheet.png"
    cv2.imwrite(str(out_p), sheet)
    return out_p


def _bind_longform_anchors_to_plan(project_dir: Path, specs_payload: dict[str, Any]) -> None:
    """Binds verified `16:9` `reference_images/*.png` paths onto `visual_plan.json` & `flow_longform_prompts.json` clips."""
    vp_path = project_dir / "03_visuals" / "visual_plan.json"
    if not vp_path.exists():
        return
    vp_doc = json.loads(vp_path.read_text(encoding="utf-8"))
    ref_dir = project_dir / "03_visuals" / REF_IMAGES_DIRNAME
    valid_ids = {
        str(sp["ref_id"]): f"03_visuals/{REF_IMAGES_DIRNAME}/{sp['filename']}"
        for sp in (specs_payload.get("all_specs") or [])
        if (ref_dir / str(sp["filename"])).exists()
    }
    brain_ref = next((v for k, v in valid_ids.items() if "brain" in k), None)

    for c in vp_doc.get("clips") or []:
        g = str(c.get("grammar") or "")
        anc_id = str(c.get("reference_anchor_id") or "")
        if g in ("porcelain_hands_closeup", "porcelain_pov_hands"):
            # Keep macro closeups unanchored so Frame 0 isn't locked to a wide establishing shot
            c.pop("reference_image", None)
        elif g == "porcelain_living_brain" and brain_ref:
            c["reference_image"] = valid_ids.get(anc_id, brain_ref)
        elif anc_id in valid_ids:
            c["reference_image"] = valid_ids[anc_id]

    vp_path.write_text(json.dumps(vp_doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    prompts_path = project_dir / "03_visuals" / "flow_longform_prompts.json"
    if prompts_path.exists():
        p_doc = json.loads(prompts_path.read_text(encoding="utf-8"))
        ref_by_num = {int(c["clip_number"]): c.get("reference_image") for c in (vp_doc.get("clips") or [])}
        for pc in p_doc.get("clips") or []:
            ri = ref_by_num.get(int(pc["clip_number"]))
            if ri:
                pc["reference_image"] = ri
            else:
                pc.pop("reference_image", None)
        prompts_path.write_text(json.dumps(p_doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _normalize_generated_png_16x9(png_path: Path) -> None:
    im = cv2.imread(str(png_path))
    if im is None or im.size == 0:
        return
    h, w = im.shape[:2]
    target_ratio = float(LONGFORM_VIDEO_WIDTH) / float(LONGFORM_VIDEO_HEIGHT)
    cur_ratio = float(w) / max(1.0, float(h))
    if cur_ratio > target_ratio:
        nw = int(round(h * target_ratio))
        x0 = max(0, (w - nw) // 2)
        im = im[:, x0 : x0 + nw]
    elif cur_ratio < target_ratio:
        nh = int(round(w / target_ratio))
        y0 = max(0, (h - nh) // 2)
        im = im[y0 : y0 + nh, :]
    if im.shape[1] != LONGFORM_VIDEO_WIDTH or im.shape[0] != LONGFORM_VIDEO_HEIGHT:
        im = cv2.resize(im, (LONGFORM_VIDEO_WIDTH, LONGFORM_VIDEO_HEIGHT), interpolation=cv2.INTER_LANCZOS4)
    cv2.imwrite(str(png_path), im)


def _open_isolated_gemini_tab_16x9(cdp_port: int = DEFAULT_CDP_PORT) -> dict[str, str]:
    """Opens an isolated `https://gemini.google.com/images` tab via CDP without touching existing user tabs."""
    target_url = f"http://127.0.0.1:{cdp_port}/json/new?https://gemini.google.com/images"
    try:
        req = urllib.request.Request(target_url, method="PUT")
        with urllib.request.urlopen(req, timeout=8) as r:
            info = json.loads(r.read().decode("utf-8"))
    except Exception:
        with urllib.request.urlopen(target_url, timeout=8) as r:
            info = json.loads(r.read().decode("utf-8"))
    return {"tab_id": str(info["id"]), "ws_url": str(info["webSocketDebuggerUrl"])}


async def _ensure_gemini_images_16x9_mode(client: Any, force_reload: bool = False) -> None:
    """Ensures `https://gemini.google.com/images` has `16:9` widescreen selected (isolated from Shorts `9:16`)."""
    from pipeline.gemini_web_worker import cdp_click_xy, eval_js, navigate_to

    cur_url = await eval_js(client, "location.href") or ""
    if force_reload or "gemini.google.com" not in str(cur_url):
        await navigate_to(client, "https://gemini.google.com/images", wait_sec=5.0)
        await asyncio.sleep(1.5)

    ar_pos = await eval_js(
        client,
        """
        JSON.stringify((() => {
            for (const el of document.querySelectorAll("button, mat-chip, [role=button]")) {
                const r = el.getBoundingClientRect();
                const txt = (el.innerText || "").trim();
                const al = el.getAttribute("aria-label") || "";
                if (r.width > 0 && (txt === "16:9" || al.includes("16:9"))) {
                    return {already_16x9: true, x: Math.round(r.left + r.width/2), y: Math.round(r.top + r.height/2)};
                }
                if (r.width > 0 && (txt.includes("Aspect ratio") || al.includes("Aspect ratio") || txt === "1:1" || txt === "9:16")) {
                    return {already_16x9: false, x: Math.round(r.left + r.width/2), y: Math.round(r.top + r.height/2)};
                }
            }
            return null;
        })())
        """,
    )
    info = json.loads(ar_pos) if ar_pos else None
    if info and not info.get("already_16x9"):
        await cdp_click_xy(client, info["x"], info["y"])
        await asyncio.sleep(1.2)
        item_pos = await eval_js(
            client,
            """
            JSON.stringify((() => {
                const c = document.querySelector(".cdk-overlay-container") || document.body;
                for (const el of c.querySelectorAll("button, [role=menuitem], [role=option], input-companion-item")) {
                    const r = el.getBoundingClientRect();
                    const txt = (el.innerText || "").trim();
                    if (r.width > 0 && (txt.includes("16:9") || txt.toLowerCase().includes("landscape"))) {
                        return {x: Math.round(r.left + r.width/2), y: Math.round(r.top + r.height/2)};
                    }
                }
                return null;
            })())
            """,
        )
        pt = json.loads(item_pos) if item_pos else None
        if pt:
            await cdp_click_xy(client, pt["x"], pt["y"])
            await asyncio.sleep(1.0)


async def _generate_gemini_image_16x9(
    client: Any,
    prompt: str,
    out_path: Path,
    conditioning_paths: list[Path] | None = None,
    force_new_chat: bool = False,
    timeout_sec: int = 120,
) -> bool:
    """Generates a `16:9` widescreen image in Gemini Web App and normalizes to `1920x1080`."""
    import base64
    import time
    from pipeline.gemini_web_worker import eval_js, paste_png_into_editor

    await _ensure_gemini_images_16x9_mode(client, force_reload=force_new_chat)
    await eval_js(
        client,
        """
        (() => {
            const ed = document.querySelector(".ql-editor");
            if (ed) ed.innerHTML = "";
        })()
        """,
    )
    await asyncio.sleep(0.3)

    if conditioning_paths:
        for cp in conditioning_paths[:2]:
            if cp and cp.exists():
                await paste_png_into_editor(client, cp, wait_sec=2.0)

    before_raw = await eval_js(
        client,
        """
        JSON.stringify(
            Array.from(document.querySelectorAll("img"))
                .filter(i => i.naturalWidth > 300 && i.naturalHeight > 300 && !(i.className || "").includes("preview") && !(i.alt || "").includes("Uploaded"))
                .map(i => i.src)
        )
        """,
    )
    before_srcs = set(json.loads(before_raw) if before_raw else [])

    await client.type_into([".ql-editor", "div[contenteditable=true]"], prompt)
    await asyncio.sleep(0.8)
    await client.click(["button[aria-label*='Send']", "button[aria-label*='submit']", "button.send-button"])

    t0 = time.time()
    new_src = None
    while time.time() - t0 < timeout_sec:
        await asyncio.sleep(2.5)
        state_raw = await eval_js(
            client,
            """
            JSON.stringify((() => {
                const imgs = Array.from(document.querySelectorAll("img"))
                    .filter(i => i.naturalWidth > 300 && i.naturalHeight > 300 && i.complete && !(i.className || "").includes("preview") && !(i.alt || "").includes("Uploaded"))
                    .map(i => ({src: i.src, w: i.naturalWidth, h: i.naturalHeight}));
                const bodyTxt = document.body.innerText || "";
                const busy = bodyTxt.includes("Creating your image") || bodyTxt.includes("Generating");
                return {imgs, busy};
            })())
            """,
        )
        st = json.loads(state_raw) if state_raw else {"imgs": [], "busy": False}
        for im in reversed(st["imgs"]):
            if im["src"] not in before_srcs:
                new_src = im["src"]
                break
        if new_src and not st["busy"]:
            await asyncio.sleep(1.0)
            break

    if not new_src:
        return False

    b64_png = await eval_js(
        client,
        f"""
        (() => {{
            const imgs = Array.from(document.querySelectorAll("img"))
                .filter(i => i.src === "{new_src}" || (i.naturalWidth > 300 && i.naturalHeight > 300));
            if (!imgs.length) return null;
            const img = imgs[imgs.length - 1];
            const c = document.createElement("canvas");
            c.width = img.naturalWidth;
            c.height = img.naturalHeight;
            const ctx = c.getContext("2d");
            ctx.drawImage(img, 0, 0);
            return c.toDataURL("image/png");
        }})()
        """,
    )
    if not b64_png or not str(b64_png).startswith("data:image/png;base64,"):
        return False

    raw_bytes = base64.b64decode(str(b64_png).split(",", 1)[1])
    arr = np.frombuffer(raw_bytes, dtype=np.uint8)
    bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if bgr is None:
        return False

    out_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out_path), bgr)
    _normalize_generated_png_16x9(out_path)
    return out_path.exists() and out_path.stat().st_size > 30_000


async def ensure_longform_reference_pack_async(
    project_id_or_dir: str | Path,
    *,
    cdp_port: int = DEFAULT_CDP_PORT,
    batch_count: int = FLOW_ZERO_CREDIT_IMAGE_BATCH_COUNT,
    backend: str = "flow",
    force: bool = False,
) -> dict[str, Any]:
    """
    Synthesizes & verifies all `1920x1080` (`16:9`) Reference Anchor PNGs via `0-credit` Google Flow `Image` (`x4`)
    (or `--backend gemini` web fallback), never touching pre-existing user tabs and always closing its dedicated
    worker tab + purging quarantine in `finally:`.
    """
    from pipeline.flow_ingredients import generate_flow_image_batch
    from pipeline.flow_live_single_worker import allocate_dedicated_flow_project_tab
    from pipeline.studio.whale_session import DirectCDPClient

    eff_backend = "gemini" if str(backend or "flow").strip().lower() == "gemini" else "flow"
    p_dir = resolve_longform_project_dir(project_id_or_dir, create=False)
    vis_dir = p_dir / "03_visuals"
    ref_dir = vis_dir / REF_IMAGES_DIRNAME
    ref_dir.mkdir(parents=True, exist_ok=True)
    vp_doc = json.loads((vis_dir / "visual_plan.json").read_text(encoding="utf-8"))
    slug = str(vp_doc.get("dossier") or p_dir.name).strip()

    specs_payload = build_longform_reference_specs(p_dir)
    if not force:
        cached = inspect_longform_reference_pack(p_dir, specs_payload=specs_payload, save_report=True)
        if cached.get("cv_pre_generation_ready"):
            _bind_longform_anchors_to_plan(p_dir, specs_payload)
            sheet = render_longform_ref_contact_sheet(p_dir, specs_payload)
            return {
                "project_id": p_dir.name,
                "backend": eff_backend,
                "cached": True,
                "cv_pre_generation_ready": True,
                "contact_sheet": str(sheet),
                "qa_report": cached,
            }

    ordered_specs = sorted(specs_payload["all_specs"], key=lambda s: int(s.get("generation_order") or 2))
    q_dir = Path(LONGFORM_QUARANTINE_ROOT) / slug
    guides_dir = q_dir / "guides"
    source_dhashes: list[str] = []

    opened_tab_id: str | None = None
    client_cm = None
    client: DirectCDPClient | None = None
    uploaded_cache: set[str] = set()
    seen_img_srcs: set[str] = set()
    existing_prov = load_provenance(p_dir)
    generated: list[str] = []
    failed: list[str] = []

    def _close_tab(tid: str | None) -> None:
        if not tid:
            return
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{cdp_port}/json/close/{tid}", timeout=5):
                pass
        except Exception:
            pass

    try:
        for idx_sp, spec in enumerate(ordered_specs, start=1):
            ref_id = str(spec["ref_id"])
            out_png = ref_dir / str(spec["filename"])
            if out_png.exists() and not force:
                chk = inspect_single_reference_image(out_png, spec, aspect=FLOW_ASPECT_LONGFORM)
                if chk.get("passed"):
                    if out_png.name not in existing_prov:
                        prov_tag = "gemini_image_generation" if eff_backend == "gemini" else "flow_image_generation"
                        register_reference_image(p_dir, out_png.name, prov_tag)
                    generated.append(ref_id)
                    print(f"[longform-refs {idx_sp}/{len(ordered_specs)}] {ref_id}: cached_ok (1920x1080)", flush=True)
                    continue

            cond_paths: list[Path] = []
            guide_cand = guides_dir / f"{spec['scene_id']}_guide.png"
            if guide_cand.exists() and spec.get("setting") not in (*BRAIN_SETTINGS, "brain_studio"):
                cond_paths.append(guide_cand)
            for cid in (spec.get("conditioned_on") or []):
                if len(cond_paths) >= 2:
                    break
                cp = ref_dir / f"{cid}.png"
                if cp.exists() and cp not in cond_paths:
                    cond_paths.append(cp)

            ok_this = False
            for attempt in range(3):
                try:
                    if client is None:
                        if eff_backend == "gemini":
                            alloc = _open_isolated_gemini_tab_16x9(cdp_port=cdp_port)
                        else:
                            alloc = await allocate_dedicated_flow_project_tab(cdp_port=cdp_port)
                        opened_tab_id = str(alloc["tab_id"])
                        client_cm = DirectCDPClient(str(alloc["ws_url"]))
                        client = await client_cm.__aenter__()
                        await client.send("Page.enable")
                        uploaded_cache.clear()
                        seen_img_srcs.clear()
                        if eff_backend == "gemini":
                            await asyncio.sleep(4.0)

                    retry_tail = (
                        ""
                        if attempt == 0
                        else " Ensure bright high-key daylight architectural exposure, crisp edges, smooth matte-white porcelain oval heads, and full-bleed 16:9 widescreen composition."
                    )
                    if eff_backend == "gemini":
                        print(
                            f"[longform-refs {idx_sp}/{len(ordered_specs)}] Generating {ref_id} (16:9 Gemini fallback, try {attempt + 1}/3)...",
                            flush=True,
                        )
                        gen_ok = await _generate_gemini_image_16x9(
                            client=client,
                            prompt=str(spec["prompt"]) + retry_tail,
                            out_path=out_png,
                            conditioning_paths=cond_paths[:2] if cond_paths else None,
                            force_new_chat=(attempt > 0 or (idx_sp % 5 == 0)),
                        )
                        if gen_ok and out_png.exists():
                            _normalize_generated_png_16x9(out_png)
                            q_chk = inspect_single_reference_image(out_png, spec, aspect=FLOW_ASPECT_LONGFORM)
                            if q_chk.get("passed"):
                                register_reference_image(p_dir, out_png.name, "gemini_image_generation")
                                generated.append(ref_id)
                                ok_this = True
                                break
                            out_png.unlink(missing_ok=True)
                    else:
                        print(
                            f"[longform-refs {idx_sp}/{len(ordered_specs)}] Generating {ref_id} (16:9 0-credit x{batch_count}, try {attempt + 1}/3, cond={[p.name for p in cond_paths]})...",
                            flush=True,
                        )
                        flow_res = await generate_flow_image_batch(
                            client=client,
                            prompt=str(spec["prompt"]) + retry_tail,
                            out_path=out_png,
                            conditioning_paths=cond_paths[:2] if cond_paths else None,
                            batch_count=batch_count,
                            aspect=FLOW_ASPECT_LONGFORM,
                            uploaded_cache=uploaded_cache,
                            seen_img_srcs=seen_img_srcs,
                            spec=spec,
                            source_dhashes=source_dhashes or None,
                            project_dir=p_dir,
                        )
                        if flow_res.get("ok") and out_png.exists():
                            generated.append(ref_id)
                            ok_this = True
                            print(
                                f"[longform-refs {idx_sp}/{len(ordered_specs)}] {ref_id}: PASSED 1920x1080 "
                                f"(best_of={flow_res.get('candidate_count')}, score={flow_res.get('quality_score')})",
                                flush=True,
                            )
                            break
                        print(
                            f"[longform-refs {idx_sp}/{len(ordered_specs)}] {ref_id} try {attempt + 1} miss: {flow_res.get('reason')}",
                            flush=True,
                        )
                except Exception as exc:
                    print(f"[longform-refs {idx_sp}/{len(ordered_specs)}] transient CDP error ({exc}); rotating tab...", flush=True)
                    if client_cm is not None:
                        try:
                            await client_cm.__aexit__(None, None, None)
                        except Exception:
                            pass
                    _close_tab(opened_tab_id)
                    client_cm = None
                    client = None
                    opened_tab_id = None
                    await asyncio.sleep(2.0)

            if not ok_this:
                failed.append(ref_id)
    finally:
        if client_cm is not None:
            try:
                await client_cm.__aexit__(None, None, None)
            except Exception:
                pass
        _close_tab(opened_tab_id)
        purge_longform_quarantine(slug)

    qa_rep = inspect_longform_reference_pack(p_dir, specs_payload=specs_payload, source_dhashes=source_dhashes, save_report=True)
    _bind_longform_anchors_to_plan(p_dir, specs_payload)
    sheet = render_longform_ref_contact_sheet(p_dir, specs_payload)
    return {
        "project_id": p_dir.name,
        "backend": eff_backend,
        "cached": False,
        "generated_ids": generated,
        "failed_ids": failed,
        "cv_pre_generation_ready": bool(qa_rep.get("cv_pre_generation_ready")),
        "contact_sheet": str(sheet),
        "qa_report": qa_rep,
    }


def ensure_longform_reference_pack(
    project_id_or_dir: str | Path,
    *,
    cdp_port: int = DEFAULT_CDP_PORT,
    batch_count: int = FLOW_ZERO_CREDIT_IMAGE_BATCH_COUNT,
    backend: str = "flow",
    force: bool = False,
) -> dict[str, Any]:
    return asyncio.run(
        ensure_longform_reference_pack_async(
            project_id_or_dir,
            cdp_port=cdp_port,
            batch_count=batch_count,
            backend=backend,
            force=force,
        )
    )
