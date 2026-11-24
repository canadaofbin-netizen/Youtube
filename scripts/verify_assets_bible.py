#!/usr/bin/env python3
"""
Deterministic generator & drift checker (`--check`) for:
  1. docs/assets_preview/ALL_ABOUT_BRAIN_GOLDEN_STYLE_SHEET.jpg
  2. docs/LOCKED_ASSETS_AND_REFERENCES_BIBLE.md

Strictly zero Google Flow / browser / network / paid API calls, and strictly
zero mutations to canonical_assets/, .agents/, pipeline/, or tests/.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

import av
from PIL import Image, ImageDraw, ImageFont

WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from pipeline import config as cfg  # noqa: E402

CHANNEL_ROOT = WORKSPACE_ROOT / "BCI_Shorts_Channel"
CANONICAL_ROOT = CHANNEL_ROOT / "canonical_assets"
DOCS_DIR = WORKSPACE_ROOT / "docs"
PREVIEW_DIR = DOCS_DIR / "assets_preview"
GOLDEN_SHEET_PATH = PREVIEW_DIR / "ALL_ABOUT_BRAIN_GOLDEN_STYLE_SHEET.jpg"
BIBLE_MD_PATH = DOCS_DIR / "LOCKED_ASSETS_AND_REFERENCES_BIBLE.md"
MASTER_PIPELINE_PATH = DOCS_DIR / "ALL_ABOUT_BRAIN_MASTER_PIPELINE.md"

FONT_BOLD_PATH = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
FONT_REG_PATH = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
FONT_MONO_PATH = Path("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf")

LOCKED_FONT_RELS: tuple[tuple[str, str], ...] = (
    ("BCI_Shorts_Channel/assets/fonts/AABCondensed-Black.ttf", "Primary `HookTitle` (`118pt`) & ASS Body Subtitles (`82pt`)"),
    ("BCI_Shorts_Channel/assets/fonts/Inter-Variable.ttf", "`R70-M` Data Stamp chart axis/data labels & clean UI body font"),
    ("pipeline/assets/fonts/PatrickHand-Regular.ttf", "`R81` XL brain anatomy callouts (`72–84px`) & Data Stamp chart headers"),
    ("pipeline/assets/fonts/Caveat-Variable.ttf", "Handwritten chart annotations & secondary stamp callouts"),
)

GOLDEN_EP31_ORDER: tuple[tuple[str, str, str], ...] = (
    ("ep31_orig_mode1_head_9x16.png", "Ep #31 Orig 1: Mode 1 Head (t=11.00s)", "Translucent light-gray shell + #27D8FF vessels"),
    ("ep31_orig_mode2_dorsal_9x16.png", "Ep #31 Orig 2: Mode 2 Dorsal (t=68.65s)", "Top-down gypsum cortex over flat #040711 void"),
    ("ep31_orig_mode2_lateral_9x16.png", "Ep #31 Orig 3: Mode 2 Lateral (t=39.33s)", "Cool matte gypsum + thick #27D8FF sulcal tubes"),
    ("ep31_orig_mode2_vessel_macro_9x16.png", "Ep #31 Orig 4: Vessel Macro (t=30.20s)", "Deep Y-sulcal opaque sky-blue vessels, 0 VFX"),
)

GOLDEN_CANONICAL_REPS: tuple[tuple[str, str, str], ...] = (
    ("J01_hook_mode1_daily_action_xray_alert", "J01 [v1.2 Hook]", "Daily Action + Mode 1 X-Ray"),
    ("A01_mode1_translucent_head_lateral", "A01 [v1 Brain]", "Mode 1 Translucent Head"),
    ("A02_mode2_whole_brain_lateral", "A02 [v1 Brain]", "Mode 2 Whole Brain Lateral"),
    ("A14_neuron_synapse_junction_macro", "A14 [v1.1 Brain]", "Synapse Junction Macro"),
    ("E07_mri_suite_staged", "E07 [v1 Env]", "Staged fMRI Scanner Suite"),
    ("G03_unlabeled_amber_pill_bottle_and_capsules", "G03 [v1.1 Prop]", "Amber Lab Pill Bottle"),
    ("D01_drone_university_campus_120ft", "D01 [v1 Drone]", "120ft University Aerial"),
    ("K03_contrast_twin_tabletop_stimulus_ab", "K03 [v1.2 Contrast]", "Non-Spatial Twin Tray A/B"),
    ("K05_contrast_scale_flat_vs_internal_surge_split", "K05 [v1.2 Contrast]", "0-Change Scale vs Brain Dome"),
    ("C01b_spatial_corridor_with_anchor_prop", "C01b [v1.2 Spatial]", "Prop-Anchored #FF2525 Route"),
    ("I01_data_stamp_backdrop_warm_tabletop_low30", "I01 [v1.1 Layout]", "Data Stamp Tabletop (Low 30%)"),
    ("I02_data_stamp_backdrop_dark_brain_low38", "I02 [v1.1 Layout]", "Data Stamp Brain (Low 38%)"),
)
GOLDEN_K06_SLOT = "K06_contrast_a12_dual_brain_state_transition_pair"

VERSIONS: tuple[str, ...] = ("v1", "v1_1", "v1_2")


def compute_sha256(path: Path) -> str:
    """Computes lowercase hex SHA-256 of a file without loading large binaries into memory at once."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_font(path: Path, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(path), size=size)


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _file_link(rel_or_abs: Path, label: str | None = None) -> str:
    p = rel_or_abs if rel_or_abs.is_absolute() else (WORKSPACE_ROOT / rel_or_abs)
    name = label or p.name
    return f"[{name}](file://{p.as_posix()})"


def _md_cell(text: str) -> str:
    return str(text or "").replace("\r", " ").replace("\n", " ").replace("|", "/").strip()


def _probe_mp3_info(path: Path) -> dict[str, Any]:
    with av.open(str(path)) as container:
        stream = container.streams.audio[0]
        dur = float(container.duration / av.time_base) if container.duration else 0.0
        return {
            "duration_sec": round(dur, 3),
            "sample_rate_hz": int(stream.sample_rate or 0),
            "channels": int(stream.channels or 0),
            "bit_rate": int(container.bit_rate or 0),
        }


def collect_inventory() -> dict[str, Any]:
    """Reads and validates all locked manifests, images, sheets, fonts, audio, and KB packs."""
    manifests: dict[str, dict[str, Any]] = {}
    manifest_meta: dict[str, dict[str, Any]] = {}
    slot_lookup: dict[str, tuple[str, dict[str, Any]]] = {}
    sheets: list[dict[str, Any]] = []
    sha_mismatches: list[str] = []
    missing_files: list[str] = []
    active_locked_slot_count = 0
    retired_r88_slot_count = 0
    deferred_slot_count = 0
    verified_slot_files = 0

    for ver in VERSIONS:
        base_dir = CANONICAL_ROOT / ver
        m_path = base_dir / "manifest.json"
        if not m_path.is_file():
            raise FileNotFoundError(f"Missing canonical manifest: {m_path}")
        doc = _load_json(m_path)
        manifests[ver] = doc
        manifest_meta[ver] = {
            "path": m_path,
            "sha256": compute_sha256(m_path),
            "schema": str(doc.get("schema") or ""),
            "version": str(doc.get("version") or ver),
            "status": str(doc.get("status") or ""),
            "generated_at_utc": str(doc.get("generated_at_utc") or ""),
            "approved_or_locked_utc": str(doc.get("locked_at_utc") or doc.get("approved_at_utc") or ""),
            "total_slots": int(doc.get("total_slots") or len(doc.get("slots") or [])),
            "total_candidate_files": int(doc.get("total_candidate_files") or 0),
        }

        for sl in doc.get("slots") or []:
            sid = str(sl["slot_id"])
            slot_lookup[sid] = (ver, sl)
            status = str(sl.get("status") or "")
            if status in ("approved", "retired_r88_cartoon_face"):
                if status == "approved":
                    active_locked_slot_count += 1
                else:
                    retired_r88_slot_count += 1
                checked_any = False
                for rel_k, sha_k in (
                    ("approved_rel_path", "approved_sha256"),
                    ("approved_start_rel_path", "approved_start_sha256"),
                    ("approved_end_rel_path", "approved_end_sha256"),
                ):
                    rel_val = sl.get(rel_k)
                    exp_sha = str(sl.get(sha_k) or "").strip().lower()
                    if rel_val and exp_sha:
                        checked_any = True
                        fpath = base_dir / str(rel_val)
                        if not fpath.is_file():
                            missing_files.append(f"{ver}/{sid}:{rel_val}")
                        else:
                            actual_sha = compute_sha256(fpath).lower()
                            verified_slot_files += 1
                            if actual_sha != exp_sha:
                                sha_mismatches.append(f"{ver}/{sid}:{rel_val} expected={exp_sha[:12]} got={actual_sha[:12]}")
                if not checked_any:
                    sha_mismatches.append(f"{ver}/{sid}:no_approved_sha_fields")
            else:
                deferred_slot_count += 1

        sheet_dir = base_dir / "sheets"
        if sheet_dir.is_dir():
            for sp in sorted(sheet_dir.glob("*.jpg")):
                with Image.open(sp) as im:
                    w, h = im.size
                sheets.append(
                    {
                        "version": ver,
                        "filename": sp.name,
                        "path": sp,
                        "size_bytes": sp.stat().st_size,
                        "width": w,
                        "height": h,
                        "sha256": compute_sha256(sp),
                    }
                )

    ep31_dir = CANONICAL_ROOT / "v1" / "_reference_31_O2CmlKOk"
    ep31_anchors: list[dict[str, Any]] = []
    v1_anchors = {a["filename"]: a for a in manifests["v1"].get("origin_31_O2CmlKOk_anchors") or []}
    for fname, title, desc in GOLDEN_EP31_ORDER:
        ep_path = ep31_dir / fname
        if not ep_path.is_file():
            missing_files.append(f"ep31/{fname}")
            continue
        actual_sha = compute_sha256(ep_path).lower()
        exp_sha = str((v1_anchors.get(fname) or {}).get("sha256") or "").strip().lower()
        if not exp_sha or actual_sha != exp_sha:
            sha_mismatches.append(f"ep31/{fname} expected={exp_sha[:12]} got={actual_sha[:12]}")
        with Image.open(ep_path) as im:
            w, h = im.size
        ep31_anchors.append(
            {
                "filename": fname,
                "title": title,
                "desc": desc,
                "path": ep_path,
                "size_bytes": ep_path.stat().st_size,
                "width": w,
                "height": h,
                "sha256": actual_sha,
            }
        )

    fonts: list[dict[str, Any]] = []
    for rel_str, role in LOCKED_FONT_RELS:
        fp = WORKSPACE_ROOT / rel_str
        if not fp.is_file() or fp.stat().st_size <= 0:
            missing_files.append(rel_str)
            continue
        fonts.append(
            {
                "rel_path": rel_str,
                "path": fp,
                "filename": fp.name,
                "role": role,
                "size_bytes": fp.stat().st_size,
                "sha256": compute_sha256(fp),
            }
        )

    bgm_dir = CHANNEL_ROOT / "knowledge_base" / "reusable_packs" / "bgm_bank"
    bgms: list[dict[str, Any]] = []
    for mp3 in sorted(bgm_dir.glob("*.mp3")):
        meta = _probe_mp3_info(mp3)
        bgms.append(
            {
                "filename": mp3.name,
                "path": mp3,
                "size_bytes": mp3.stat().st_size,
                "sha256": compute_sha256(mp3),
                **meta,
            }
        )

    lex_path = CHANNEL_ROOT / "assets" / "expression_acting_lexicon.json"
    if not lex_path.is_file():
        missing_files.append(str(lex_path.relative_to(WORKSPACE_ROOT)))
        lex_doc = {}
    else:
        lex_doc = _load_json(lex_path)

    kb_dir = CHANNEL_ROOT / "knowledge_base" / "reusable_packs"
    kb_packs: list[dict[str, Any]] = []
    for kb_p in sorted(kb_dir.glob("*.json")):
        kd = _load_json(kb_p)
        if "total_golden_prompts" in kd:
            entry_count = int(kd["total_golden_prompts"])
            detail = f"{len(kd.get('by_grammar') or {})} grammars"
        elif "count" in kd:
            entry_count = int(kd["count"])
            detail = "registry items"
        elif "cast" in kd:
            entry_count = len(kd.get("cast") or {})
            detail = f"{len(kd.get('actor_body_archetypes') or {})} body archetypes"
        elif "locations" in kd:
            entry_count = len(kd.get("locations") or {})
            detail = "3D previs blockout locations"
        else:
            entry_count = len(kd)
            detail = "top-level keys"
        kb_packs.append(
            {
                "filename": kb_p.name,
                "path": kb_p,
                "size_bytes": kb_p.stat().st_size,
                "sha256": compute_sha256(kb_p),
                "entry_count": entry_count,
                "detail": detail,
                "updated_at_utc": str(kd.get("updated_at_utc") or kd.get("schema") or "locked"),
            }
        )

    return {
        "manifests": manifests,
        "manifest_meta": manifest_meta,
        "slot_lookup": slot_lookup,
        "active_locked_slot_count": active_locked_slot_count,
        "retired_r88_slot_count": retired_r88_slot_count,
        "locked_slot_count": active_locked_slot_count + retired_r88_slot_count,
        "deferred_slot_count": deferred_slot_count,
        "verified_slot_files": verified_slot_files,
        "ep31_anchors": ep31_anchors,
        "sheets": sheets,
        "fonts": fonts,
        "bgms": bgms,
        "lexicon": {
            "path": lex_path,
            "size_bytes": lex_path.stat().st_size if lex_path.is_file() else 0,
            "sha256": compute_sha256(lex_path) if lex_path.is_file() else "",
            "schema_version": lex_doc.get("schema_version"),
            "expressions": len(lex_doc.get("expressions") or {}),
            "speaker_mouth_rules": len(lex_doc.get("speaker_mouth_rules") or {}),
        },
        "kb_packs": kb_packs,
        "missing_files": missing_files,
        "sha_mismatches": sha_mismatches,
    }


def _slot_usage_mode(ver: str, sl: dict[str, Any]) -> str:
    sid = str(sl["slot_id"])
    cat = str(sl.get("category") or "")
    status = str(sl.get("status") or "")
    if status == "retired_r88_cartoon_face":
        if sid.startswith(("B01_", "B02_", "B03_", "B04_")):
            return "[RETIRED R88 — Zero-Deletion Archive] Turnaround (never Start Frame; banned v8_ep13+)"
        return "[RETIRED R88 — Zero-Deletion Archive] Legacy Ep #01–#12 only (banned v8_ep13+)"
    if sid.startswith(("B01_", "B02_", "B03_", "B04_")):
        return "Turnaround Ingredients-Only [Never Start Frame]"
    if cat == "F_transitions" or str(sl.get("asset_type") or "") == "start_end_transition_pair":
        return "Start+End Transition Pair"
    if cat in ("C_arrows_r80", "C_v2_spatial_arrows") or sid.startswith(("C01", "C02", "C03")):
        return "Conditional Spatial-Only (eligible=True)"
    if status != "approved":
        return "Deferred Pending Flow Regen (Unused Ep #13)"
    return "Ingredients / Episode Conditioning Anchor"


def _slot_semantic_rule(ver: str, sl: dict[str, Any]) -> str:
    sid = str(sl["slot_id"])
    cat = str(sl.get("category") or "")
    status = str(sl.get("status") or "")
    if status == "retired_r88_cartoon_face":
        if sid.startswith(("B01_", "B02_", "B03_", "B04_")):
            return "[RETIRED R88 — Zero-Deletion Archive] Turnaround banned on v8_ep13+ (never direct Start Frame on Ep #01–#12); SHA-256 kept on disk"
        return "[RETIRED R88 — Zero-Deletion Archive] Legacy 2D-ink expression/wardrobe slot retired under R88; v8_ep13+ routes to faceless A/E/J/K slots"
    if cat == "J_hooks":
        if sid.startswith("J04_"):
            return "Deferred; use J01/J03/J06 with clean hands-on prop scale <=25% bottle mouth"
        return "Rotate J01-J06 across adjacent episodes; swap foreground DOI prop & R72-R backdrop"
    if cat == "K_nonspatial_contrast":
        if sid.startswith("K06_"):
            return "Non-spatial Brain A vs B Start+End lock (Omni 1.2 / Veo Lite); pair with PatrickHand callout"
        return "Mandatory when spatial_arrow_eligible=False; swap tray/tube/dial stimulus props per study"
    if cat in ("C_arrows_r80", "C_v2_spatial_arrows"):
        if ver == "v1":
            return "Legacy v1 spatial base; Ep #13+ spatial topics MUST prefer C01b-C03b prop-anchored slots"
        return "ONLY when spatial_arrow_eligible=True; name study architecture & attach moving prop legend"
    if cat == "D_drone_120ft":
        return "Condition on open-license R72-R institution ref; keep 120ft bird-eye scale & 0 ground walk"
    if sid.startswith(("B01_", "B02_", "B03_", "B04_")):
        return "Turnaround sheet: Ingredients/conditioned_on ONLY; custom single-pose start frame required"
    if cat == "B_characters":
        return "Mix expressions/wardrobe with story lighting arc; 0% raw static frame recycling across episodes"
    if cat in ("A_brain", "A_brain_expansion"):
        return "Enforce R85 viewpoint lock + Ep #31 matte/cyan palette + unique study highlight & callout"
    if cat in ("E_environments", "E_environments_expansion"):
        return "Apply Act lighting arc & 1-3 episode-specific props; never hold static room >4.25s"
    if cat == "F_transitions":
        return "Start+End interpolation skeleton ONLY; never recycle identical transition output frames across eps"
    if cat in ("G_experimental_props", "H_misconception_flip_props"):
        return "Swap prop hue/contents to match verified DOI apparatus; 0% gibberish numerals or brand logos"
    if cat == "I_layout_composition_frames":
        return "Reserve clean Y/X safe bands for R87 HookTitle / R70-M Data Stamp / R81 Callout / R65 split"
    return "Ingredients anchor only; inject unique DOI props, location, and Story Lighting Arc per episode"


def _clip_text_to_width(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont,
    max_width: int,
) -> str:
    """Truncates text cleanly with ellipsis if rendered width exceeds max_width."""
    if draw.textlength(text, font=font) <= max_width:
        return text
    ell = "..."
    lo, hi = 0, len(text)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if draw.textlength(text[:mid] + ell, font=font) <= max_width:
            lo = mid
        else:
            hi = mid - 1
    return text[:lo] + ell


def _fit_and_paste_9x16(
    canvas: Image.Image,
    img_path: Path,
    box: tuple[int, int, int, int],
) -> None:
    x0, y0, w, h = box
    with Image.open(img_path) as src:
        rgb = src.convert("RGB")
        resized = rgb.resize((w, h), Image.Resampling.LANCZOS)
    canvas.paste(resized, (x0, y0))


def _draw_palette_and_specs_card(
    canvas: Image.Image,
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    w: int,
    h: int,
    font_bold: ImageFont.FreeTypeFont,
    font_reg: ImageFont.FreeTypeFont,
    font_mono: ImageFont.FreeTypeFont,
) -> None:
    draw.rectangle((x, y, x + w, y + h), fill="#121A2B", outline="#2E3F5E", width=2)
    draw.rectangle((x, y, x + w, y + 48), fill="#1A263E")
    draw.text((x + 14, y + 14), "STYLE NUMBERS & PALETTE", fill="#27D8FF", font=font_bold)

    swatches = [
        ("#C3C9CE", "Ep31 Cortex Matte", "#9CA5AC-#C3C9CE"),
        ("#27D8FF", "Sulcal Vessels", "#27D8FF"),
        ("#040711", "Brain Void BG", "#040711"),
        ("#F5F2EB", "R88 Faceless Porcelain", "#F5F2EB"),
        ("#EAB34B", "Active Amber Hub", "#EAB34B"),
        ("#94A3B8", "Dimmed Slate", "#94A3B8"),
        ("#FF2525", "3D Arrow / Alert", "#FF2525"),
        ("#FFE600", "ASS Key Accent", "#FFE600"),
        ("#FFE14A", "HookTitle Accent", "#FFE14A"),
    ]
    cy = y + 62
    for hex_c, label, code_txt in swatches:
        draw.rectangle((x + 14, cy, x + 48, cy + 28), fill=hex_c, outline="#64748B", width=1)
        draw.text((x + 58, cy + 2), label, fill="#F1F5F9", font=font_reg)
        draw.text((x + 58, cy + 17), code_txt, fill="#94A3B8", font=font_mono)
        cy += 40

    cy += 8
    draw.line((x + 14, cy, x + w - 14, cy), fill="#2E3F5E", width=2)
    cy += 14
    specs = [
        "CANVAS: 1080x1920 @ 30fps (61.5-88s)",
        "HOOK: 118pt HookTitle (MV=238, <=2.2s)",
        "ASS: 82pt #FFE600 (MV=510, <=3w)",
        "CALLOUT: PatrickHand 72-84px (0px hit)",
        "HERO: Low-Angle Framing ~35-45%",
        "PACING: Human 1.9-4.25s | Brain 4.2-6.8s",
        "VOICE: Solo Siren (-14 LUFS / -1.5dBTP)",
        "FLOW: Omni 1.2 -> Veo Lite / NB 2.1",
        "LIB: 84 Active + 15 R88 = 99 Lock (+J04)",
    ]
    f_spec = _load_font(FONT_MONO_PATH, 13)
    for line in specs:
        draw.text((x + 14, cy), _clip_text_to_width(draw, line, f_spec, w - 28), fill="#CBD5E1", font=f_spec)
        cy += 24


def render_golden_style_sheet(inv: dict[str, Any], out_path: Path) -> dict[str, Any]:
    """Renders ALL_ABOUT_BRAIN_GOLDEN_STYLE_SHEET.jpg deterministically via Pillow."""
    canvas_w = 2160
    margin_x = 60
    header_h = 148
    sec_a_hdr_h = 56

    # Section A: 4 Ep #31 originals across 2040px
    a_gap = 32
    a_card_w = 486
    a_img_w = 468
    a_img_h = 832  # exact 9:16
    a_card_pad = (a_card_w - a_img_w) // 2
    a_footer_h = 84
    a_card_h = a_card_pad + a_img_h + a_footer_h

    # Section B: 5-column x 3-row grid (12 singles + 1 2-col K06 pair + 1 palette/numbers card)
    sec_b_hdr_h = 62
    b_gap_x = 30
    b_gap_y = 28
    b_card_w = 384
    b_img_w = 360
    b_img_h = 640  # exact 9:16
    b_card_pad = (b_card_w - b_img_w) // 2
    b_footer_h = 74
    b_card_h = b_card_pad + b_img_h + b_footer_h

    footer_bar_h = 64
    canvas_h = (
        header_h
        + sec_a_hdr_h
        + a_card_h
        + 36
        + sec_b_hdr_h
        + 3 * b_card_h
        + 2 * b_gap_y
        + 28
        + footer_bar_h
    )

    img = Image.new("RGB", (canvas_w, canvas_h), "#0B101B")
    draw = ImageDraw.Draw(img)

    f_title = _load_font(FONT_BOLD_PATH, 38)
    f_sub = _load_font(FONT_REG_PATH, 21)
    f_sec = _load_font(FONT_BOLD_PATH, 26)
    f_card_title = _load_font(FONT_BOLD_PATH, 19)
    f_card_sub = _load_font(FONT_REG_PATH, 16)
    f_badge = _load_font(FONT_BOLD_PATH, 15)
    f_mono = _load_font(FONT_MONO_PATH, 14)

    # Top Title Banner
    draw.rectangle((0, 0, canvas_w, header_h - 12), fill="#11192B")
    draw.line((0, header_h - 12, canvas_w, header_h - 12), fill="#27D8FF", width=3)
    draw.text(
        (margin_x, 26),
        "ALL ABOUT BRAIN — GOLDEN STYLE CANARY SHEET (Ep #31 + Canonical v1/v1.1/v1.2)",
        fill="#FFFFFF",
        font=f_title,
    )
    draw.text(
        (margin_x, 82),
        "84 Active + 15 Retired R88 = 99 SHA-256 Locked (v1/v1.1/v1.2, J04 Deferred)  |  100% Google Flow Native (Omni 1.2 Flash + Veo 3.1 Lite + Nano Banana 2.1)",
        fill="#94A3B8",
        font=f_sub,
    )

    # Section A Header
    y_cursor = header_h + 10
    draw.text(
        (margin_x, y_cursor),
        "SECTION A — 4 GENUINE EPISODE #31 (31_O2CmlKOk) ORIGINALS (IMMUTABLE BRAIN ANCHORS)",
        fill="#FFE14A",
        font=f_sec,
    )
    y_cursor += sec_a_hdr_h - 10

    for idx, ep in enumerate(inv["ep31_anchors"]):
        cx = margin_x + idx * (a_card_w + a_gap)
        cy = y_cursor
        draw.rectangle((cx, cy, cx + a_card_w, cy + a_card_h), fill="#121A2B", outline="#27D8FF", width=2)
        _fit_and_paste_9x16(img, ep["path"], (cx + a_card_pad, cy + a_card_pad, a_img_w, a_img_h))
        ty = cy + a_card_pad + a_img_h + 10
        draw.text((cx + a_card_pad, ty), _clip_text_to_width(draw, ep["title"], f_card_title, a_img_w), fill="#FFFFFF", font=f_card_title)
        draw.text((cx + a_card_pad, ty + 24), _clip_text_to_width(draw, ep["desc"], f_card_sub, a_img_w), fill="#E2E8F0", font=f_card_sub)
        draw.text(
            (cx + a_card_pad, ty + 46),
            _clip_text_to_width(draw, f"{ep['filename']}  [{ep['sha256'][:12]}]", f_mono, a_img_w),
            fill="#94A3B8",
            font=f_mono,
        )

    y_cursor += a_card_h + 36
    draw.text(
        (margin_x, y_cursor),
        "SECTION B — 13 LOCKED CANONICAL REPRESENTATIVES (v1 / v1.1 / v1.2) + STYLE NUMBERS",
        fill="#27D8FF",
        font=f_sec,
    )
    y_cursor += sec_b_hdr_h

    slot_lookup = inv["slot_lookup"]
    # Rows 1 & 2 (10 singles), Row 3 cols 0..1 (2 singles), Row 3 cols 2..3 (K06 Start->End), Row 3 col 4 (Palette/Numbers)
    for idx, (sid, short_tag, subtitle) in enumerate(GOLDEN_CANONICAL_REPS):
        ver, sl = slot_lookup[sid]
        rel_path = str(sl["approved_rel_path"])
        img_path = CANONICAL_ROOT / ver / rel_path
        row = idx // 5
        col = idx % 5
        cx = margin_x + col * (b_card_w + b_gap_x)
        cy = y_cursor + row * (b_card_h + b_gap_y)

        draw.rectangle((cx, cy, cx + b_card_w, cy + b_card_h), fill="#121A2B", outline="#2E3F5E", width=2)
        _fit_and_paste_9x16(img, img_path, (cx + b_card_pad, cy + b_card_pad, b_img_w, b_img_h))
        ty = cy + b_card_pad + b_img_h + 10
        draw.text((cx + b_card_pad, ty), _clip_text_to_width(draw, short_tag, f_card_title, b_img_w), fill="#FFE600", font=f_card_title)
        draw.text((cx + b_card_pad, ty + 24), _clip_text_to_width(draw, subtitle, f_card_sub, b_img_w), fill="#E2E8F0", font=f_card_sub)
        sid_tag = _clip_text_to_width(draw, sid, f_mono, b_img_w - 115)
        draw.text(
            (cx + b_card_pad, ty + 45),
            f"{sid_tag} [{str(sl['approved_sha256'])[:10]}]",
            fill="#94A3B8",
            font=f_mono,
        )

    # K06 spanning cols 2..3 on Row 3
    k_ver, k_sl = slot_lookup[GOLDEN_K06_SLOT]
    k_start_path = CANONICAL_ROOT / k_ver / str(k_sl["approved_start_rel_path"])
    k_end_path = CANONICAL_ROOT / k_ver / str(k_sl["approved_end_rel_path"])
    kx = margin_x + 2 * (b_card_w + b_gap_x)
    ky = y_cursor + 2 * (b_card_h + b_gap_y)
    kw = 2 * b_card_w + b_gap_x  # 798px
    kh = b_card_h

    draw.rectangle((kx, ky, kx + kw, ky + kh), fill="#121A2B", outline="#EAB34B", width=2)
    pair_img_w = 356
    pair_img_h = 632  # exact 356 * 16 / 9 = 632.88 (~9:16)
    pair_pad_y = b_card_pad + 4
    s_x = kx + 18
    e_x = kx + kw - 18 - pair_img_w
    _fit_and_paste_9x16(img, k_start_path, (s_x, ky + pair_pad_y, pair_img_w, pair_img_h))
    _fit_and_paste_9x16(img, k_end_path, (e_x, ky + pair_pad_y, pair_img_w, pair_img_h))

    # Badges & arrow between Start and End
    draw.rectangle((s_x + 8, ky + pair_pad_y + 8, s_x + 124, ky + pair_pad_y + 34), fill="#0F172A", outline="#27D8FF", width=1)
    draw.text((s_x + 14, ky + pair_pad_y + 13), "START (A12)", fill="#27D8FF", font=f_badge)
    draw.rectangle((e_x + 8, ky + pair_pad_y + 8, e_x + 168, ky + pair_pad_y + 34), fill="#0F172A", outline="#EAB34B", width=1)
    draw.text((e_x + 14, ky + pair_pad_y + 13), "END (Gold/Slate)", fill="#EAB34B", font=f_badge)
    mid_x = kx + kw // 2
    mid_y = ky + pair_pad_y + pair_img_h // 2
    draw.text((mid_x - 14, mid_y - 16), "->", fill="#FFE14A", font=f_sec)

    k_ty = ky + b_card_pad + b_img_h + 10
    draw.text((kx + 18, k_ty), "K06 [v1.2 Start+End Transition Pair]", fill="#FFE600", font=f_card_title)
    k_sub = _clip_text_to_width(
        draw,
        "A12 Dual Brain State Lock (Start+End)  |  S: "
        + str(k_sl["approved_start_sha256"])[:10]
        + "  ->  E: "
        + str(k_sl["approved_end_sha256"])[:10],
        f_card_sub,
        kw - 36,
    )
    draw.text((kx + 18, k_ty + 24), k_sub, fill="#E2E8F0", font=f_card_sub)
    draw.text((kx + 18, k_ty + 45), _clip_text_to_width(draw, GOLDEN_K06_SLOT, f_mono, kw - 36), fill="#94A3B8", font=f_mono)

    # Col 4 on Row 3: Style Palette & Numeric Specs Card
    px = margin_x + 4 * (b_card_w + b_gap_x)
    py = ky
    _draw_palette_and_specs_card(img, draw, px, py, b_card_w, b_card_h, f_card_title, f_card_sub, f_mono)

    # Bottom Footer Bar
    fy = canvas_h - footer_bar_h
    draw.rectangle((0, fy, canvas_w, canvas_h), fill="#11192B")
    draw.line((0, fy, canvas_w, fy), fill="#2E3F5E", width=2)
    draw.text(
        (margin_x, fy + 20),
        "SSOT: pipeline/config.py  |  Bible: docs/LOCKED_ASSETS_AND_REFERENCES_BIBLE.md  |  Mute & Hide Name Test: 0.5s Brand Identity + Visual Story Clarity",
        fill="#94A3B8",
        font=f_card_sub,
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=str(out_path.parent), prefix=".tmp_golden_", suffix=".jpg")
    os.close(fd)
    tmp_p = Path(tmp_name)
    try:
        img.save(tmp_p, format="JPEG", quality=92, optimize=True)
        os.replace(tmp_p, out_path)
    finally:
        if tmp_p.exists():
            tmp_p.unlink(missing_ok=True)

    return {
        "path": str(out_path),
        "width": canvas_w,
        "height": canvas_h,
        "size_bytes": out_path.stat().st_size,
        "sha256": compute_sha256(out_path),
    }


def generate_bible_markdown(inv: dict[str, Any], golden_info: dict[str, Any]) -> str:
    """Builds deterministic Markdown for docs/LOCKED_ASSETS_AND_REFERENCES_BIBLE.md from disk state."""
    lines: list[str] = []
    add = lines.append

    add("# ALL ABOUT BRAIN — Locked Assets & References Bible")
    add("")
    add("> [!IMPORTANT]")
    add("> **Single Source of Truth (`100%` Derived from Disk Manifests — Do Not Hand-Edit)**:")
    add("> Generated deterministically by [`verify_assets_bible.py`](file://" + (WORKSPACE_ROOT / "scripts/verify_assets_bible.py").as_posix() + "). Run `python -X utf8 scripts/verify_assets_bible.py --check` to verify byte-for-byte parity and all SHA-256 locks.")
    add("")
    add("- **Golden Style Canary Sheet**: " + _file_link(GOLDEN_SHEET_PATH, "ALL_ABOUT_BRAIN_GOLDEN_STYLE_SHEET.jpg") + f" (`{golden_info['width']}x{golden_info['height']}` RGB JPEG, `{golden_info['size_bytes']:,}` bytes, SHA-256 `{golden_info['sha256'][:12]}`)")
    add("- **Master Pipeline Blueprint**: " + _file_link(MASTER_PIPELINE_PATH, "ALL_ABOUT_BRAIN_MASTER_PIPELINE.md"))
    add(f"- **Canonical Slot Summary**: **{inv['active_locked_slot_count']} Active Selectable + {inv['retired_r88_slot_count']} Retired R88 (B01–B15 Zero-Deletion Archive) = {inv['locked_slot_count']} SHA-256 Locked + {inv['deferred_slot_count']} J04 Deferred** (`27+15 v1 + 43 v1.1 + 14 v1.2` = `{inv['locked_slot_count'] + inv['deferred_slot_count']}` Total Catalog Slots, `{inv['verified_slot_files']}` SHA-256 verified files on disk)")
    add("")
    add("---")
    add("")

    # Section 1
    add("## §1. Style Guide with Numbers (`pipeline/config.py` SSOT)")
    add("")
    add("### 1.1 Locked Color Palette")
    add("| Token / Role | Exact Hex / Range | Usage & Visual Constraint |")
    add("|---|---|---|")
    add("| **Ep #31 Mode 2 Cortex Matte** | `#9CA5AC` – `#C3C9CE` (highlights `#DCDFE3` – `#ECEFF2`) | Cool matte gypsum-plaster gyri (`S <= 48.0`, `V >= 152.0`, zero steel-blue tint, zero wet gloss) |")
    add("| **Sulcal Vessels & CSF** | `#27D8FF` (specular `#58E4FF`) | Thick opaque cylindrical tubes nestled inside sulcal grooves & CSF pathways (zero neon sparks) |")
    add("| **Brain Void Backdrop** | `#040711` | Solid flat dark navy background (`void_halo_luma_p90 <= 40.0`, `bloom <= 0.040`) |")
    add("| **Warm Amber Active Hub** | `#EAB34B` (variants `#F5A623` / `#F2A93B`) | Solid matte focal highlight on active brain nuclei/structures (`0%` glow halo) |")
    add("| **Dimmed / Shutdown Slate** | `#94A3B8` (deep `#68707A` / `#4A5568`) | Solid matte slate-gray for silenced, inhibited, or control structures |")
    add("| **R88 Faceless Architectural Porcelain Cast** | `#F5F2EB` | R88 Faceless Architectural Porcelain Cast (zero cartoon eyes/mouth; hands-only / silhouette / Mode 1); `B01–B15` retired on `v8_ep13+` |")
    add("| **Default ASS Accent** | `#FFE600` (`ASS &H0000E6FF&`) | Single focal keyword highlight per caption burst on `82pt` body captions |")
    add("| **HookTitle Accent** | `#FFE14A` (`ASS &H004AE1FF&`) | Line-2 / focal punch yellow on `0.00–2.20s` `118pt HookTitle` |")
    add("| **R80 3D Arrow / R65 Alert** | `#FF2525` (`RGB 255, 37, 37`) | Solid matte-crimson 3D extruded spatial arrows (`eligible=True` only) & thumbnail contrast pointer |")
    add("")

    add("### 1.2 Cross-Platform Safe Zones, Typography, Framing & Pacing (`1080×1920 @ 30fps`)")
    add("| Spec Dimension | Locked Value / Range | Notes & Gate Reference |")
    add("|---|---|---|")
    add("| **Canvas & Duration (`v8`)** | `1080×1920 @ 30fps`, `61.5–88.0s` | `SHORTS_EXPRESSIVE_V8_DURATION_MIN_SEC = 61.5`, `SHORTS_EXPRESSIVE_V8_R75_MAX_SEC = 88.0` |")
    add("| **Top Chrome Dead-Zone** | `Y = 0–220 px` (`0–11.5%`) | Strictly empty across YT Shorts, IG Reels, TikTok |")
    add("| **Right Rail Safe Ceiling** | `X <= 910 px` (`84.2%` width) | `UNIVERSAL_SAFE_X_RIGHT_PX = 910` clears all 3 platform right-side action rails |")
    add("| **Bottom UI Dead-Zone** | `Y = 1520–1920 px` (`79.2–100%`) | Strictly empty (`THUMB_V4_BOTTOM_TITLE_SAFE_Y = 1520`) |")
    add(f"| **HookTitle (`R87-H3`)** | `{cfg.R87_HOOK_TITLE_FONT_SIZE}pt` (`96–126pt`), `MarginV={cfg.R87_HOOK_TITLE_MARGIN_V}`, `MarginL={cfg.R87_HOOK_TITLE_MARGIN_L}`, `MarginR={cfg.R87_HOOK_TITLE_MARGIN_R}` | `AAB Condensed Black`, `ScaleX={cfg.R87_HOOK_TITLE_SCALE_X}`, `Outline={cfg.R87_HOOK_TITLE_OUTLINE}`, `Shadow={cfg.R87_HOOK_TITLE_SHADOW}`, `0.00–{cfg.R87_HOOK_TITLE_DURATION_SEC:.2f}s`, `<= {cfg.R87_HOOK_TITLE_MAX_WORDS}w / {cfg.R87_HOOK_TITLE_MAX_CHARS}c` (`{{\\fad(0,120)}}`) |")
    add(f"| **ASS Subtitles (`v8`)** | `{cfg.EXPRESSIVE_V8_SUBTITLE_FONT_SIZE}pt` (`78–86pt`), `MarginV={cfg.EXPRESSIVE_V8_SUBTITLE_MARGIN_V}`, `<= {cfg.EXPRESSIVE_V8_SUBTITLE_MAX_WORDS}w` | `Outline={cfg.EXPRESSIVE_V8_SUBTITLE_OUTLINE_WIDTH}`, `Shadow={cfg.EXPRESSIVE_V8_SUBTITLE_SHADOW_DEPTH}`, `MarginL={cfg.EXPRESSIVE_V8_SUBTITLE_MARGIN_L}`, `MarginR={cfg.EXPRESSIVE_V8_SUBTITLE_MARGIN_R}`, `{cfg.EXPRESSIVE_V8_SUBTITLE_HIGHLIGHT_HEX}` keyword highlight |")
    add(f"| **PatrickHand Callouts (`R81`)** | `72–84px` (`1-line`) / `64–82px` (`2-line`), **`0px` strikethrough** | `PatrickHand-Regular.ttf`, underline gap `+{cfg.R81_CALLOUT_UNDERLINE_GAP_PX}px`, tracking `Y ∈ [{cfg.R81_TRACKING_MIN_Y_PX}, {cfg.R81_TRACKING_MAX_Y_PX}]` |")
    add(f"| **R70-M Data Stamps** | `1×1` panel, `<= {cfg.DATA_STAMP_MAX_PER_EPISODE}`/ep, `Y ∈ [12%, 62%]`, `X <= 910px` | `study` mode required on empirical DOIs (`0` fake `Concept` badges, `0px` glyph overlap) |")
    add("| **Hero Framing (`P1-4`)** | `~35–45%` vertical height (`~40%` hero low-angle) | Low-angle hero human cuts + foreground depth prop, alternating `push-in ↔ pull-back` (`0` `dolly` noun) |")
    add(f"| **Dual-Speed Pacing (`R82`)** | Human `{cfg.R82_HUMAN_MIN_CUT_SEC:.2f}–{cfg.R82_HUMAN_MAX_CUT_SEC:.2f}s` / Brain `{cfg.R82_BRAIN_MIN_CUT_SEC:.2f}–{cfg.R82_BRAIN_MAX_CUT_SEC:.2f}s` (`{round(cfg.R82_BRAIN_DURATION_RATIO_RANGE[0]*100)}–{round(cfg.R82_BRAIN_DURATION_RATIO_RANGE[1]*100)}%`) | `{cfg.R82_CLIP_COUNT_RANGE[0]}–{cfg.R82_CLIP_COUNT_RANGE[1]}` clips, `Cut #1` `{cfg.R87_FIRST_CUT_MIN_SEC:.2f}–{cfg.R87_FIRST_CUT_MAX_SEC:.2f}s`, `S01` `{cfg.R87_S01_MIN_WORDS}–{cfg.R87_S01_MAX_WORDS}w` (`<= {cfg.R87_S01_MAX_SEC:.2f}s`) |")
    add(f"| **Ep #31 CV Gates (`R85`)** | `Cortex Sat <= {cfg.R85_EP31_CORTEX_SAT_MAX}`, `Luma >= {cfg.R85_EP31_CORTEX_LUMA_MIN}` | `Mode 1 Luma >= {cfg.R85_EP31_MODE1_LUMA_MIN}`, `P75 >= {cfg.R85_EP31_MODE1_HEAD_P75_MIN}`, `Sparks <= {cfg.R85_EP31_MAX_SPARK_CLUSTERS}`, `Halo P90 <= {cfg.R85_EP31_MAX_VOID_HALO_P90}` |")
    add("")

    add("### 1.3 100% Google Flow Native Engine Matrix (`0` External Paid Video/Image APIs)")
    add("| Tier / Engine | Model Label & Key | Duration / Batch Contract | Notes |")
    add("|---|---|---|---|")
    add(f"| **Primary Video** | `{cfg.FLOW_PRIMARY_VIDEO_MODEL}` (`{cfg.FLOW_PRIMARY_OMNI_MODEL_KEY}`, `gemini-omni-1.2-flash`) | `Ingredients` `3–15s` (`8s` w/ ref) & `Start+End` `3–10s` | Unified single-Omni tier (`{cfg.FLOW_OMNI_CREDIT_COST_WITH_REF}` cr/clip, cap `{cfg.FLOW_OMNI_EPISODE_CREDIT_CAP}`, margin `{cfg.FLOW_OMNI_BALANCE_SAFETY_MARGIN}`) |")
    add(f"| **0-Credit Video Fallback** | `{cfg.FLOW_ZERO_CREDIT_MODEL}` | `4s / 6s / 8s`, `Start+End` supported (`0` credits) | Seamless fallback when credits hit `0` (`<= {cfg.FLOW_ZERO_CREDIT_SAFE_PARALLEL_TABS}` parallel shard tabs) |")
    add(f"| **0-Credit Keyframe Image** | `{cfg.FLOW_ZERO_CREDIT_IMAGE_MODEL}` (`{cfg.FLOW_ZERO_CREDIT_IMAGE_FAMILY_ID}`) | `x{cfg.FLOW_ZERO_CREDIT_IMAGE_BATCH_COUNT}` 1st-pass / `x{cfg.FLOW_ZERO_CREDIT_IMAGE_RETRY_BATCH_COUNT}` retry & Gate 1 / `x{cfg.FLOW_ZERO_CREDIT_IMAGE_THUMBNAIL_BATCH_COUNT}` R65 thumb | Immediate `0`-retry fail-fast on `\"unusual activity\"` |")
    add(f"| **Retired Video Models** | {', '.join(f'`{m}`' for m in cfg.FLOW_RETIRED_VIDEO_MODELS)} | Retired `2026-12-05` (`0` fallback) | `Veo 2` & external paid image/video APIs permanently banned |")
    add("")
    add("---")
    add("")

    # Section 2
    add("## §2. Golden Style Canary Sheet + `Ep #31` 4 Originals + `15` Contact Sheets Index")
    add("")
    add("### 2.1 Golden Style Canary Sheet")
    add(f"- **Image Preview Sheet**: {_file_link(GOLDEN_SHEET_PATH, 'ALL_ABOUT_BRAIN_GOLDEN_STYLE_SHEET.jpg')} (`{golden_info['width']}x{golden_info['height']}`, `{golden_info['size_bytes']:,}` bytes, SHA-256 `{golden_info['sha256'][:12]}`)")
    add("- **Composition**: Dark navy studio canvas (`#0B101B`) showing **Section A** (all `4` genuine `Ep #31` `31_O2CmlKOk` originals side-by-side) and **Section B** (`13` locked canonical representatives across `v1/v1.1/v1.2`, including `K06` `Start -> End` transition pair, plus numeric palette & safe-zone legend card).")
    add("")
    add("### 2.2 Genuine Episode #31 (`31_O2CmlKOk`) 4 Original Anchors")
    add("| Filename | Source Role & Frame | Dimensions | Bytes | File Link | SHA-256[:12] |")
    add("|---|---|---:|---:|---|---|")
    for ep in inv["ep31_anchors"]:
        add(
            f"| `{ep['filename']}` | {_md_cell(ep['title'])} — {_md_cell(ep['desc'])} | `{ep['width']}x{ep['height']}` | `{ep['size_bytes']:,}` | {_file_link(ep['path'])} | `{ep['sha256'][:12]}` |"
        )
    add("")
    add("### 2.3 Complete `15`-Sheet Contact Index (`v1` + `v1_1` + `v1_2`)")
    add("| Library | Sheet Filename | Dimensions | Bytes | File Link | SHA-256[:12] |")
    add("|---|---|---:|---:|---|---|")
    for sh in inv["sheets"]:
        add(
            f"| `{sh['version']}` | `{sh['filename']}` | `{sh['width']}x{sh['height']}` | `{sh['size_bytes']:,}` | {_file_link(sh['path'])} | `{sh['sha256'][:12]}` |"
        )
    add("")
    add("---")
    add("")

    # Section 3
    add("## §3. Complete `100`-Slot Canonical Catalog (`84` Active Selectable + `15` Retired `R88` = `99` Locked + `1` `J04` Deferred)")
    add("")
    add("### 3.1 Library Manifest Checksums & Lock Metadata")
    add("| Library | Schema | Status | Slots (Active / Retired R88 / Deferred) | Generated / Locked UTC | Manifest Link | Manifest SHA-256[:12] |")
    add("|---|---|---|---:|---|---|---|")
    for ver in VERSIONS:
        mm = inv["manifest_meta"][ver]
        doc = inv["manifests"][ver]
        slots = doc.get("slots") or []
        app_c = sum(1 for s in slots if str(s.get("status")) == "approved")
        ret_c = sum(1 for s in slots if str(s.get("status")) == "retired_r88_cartoon_face")
        def_c = len(slots) - app_c - ret_c
        ts_str = f"`{mm['generated_at_utc']}` / `{mm['approved_or_locked_utc']}`"
        add(
            f"| `{mm['version']}` (`{ver}`) | `{mm['schema']}` | `{mm['status']}` | `{len(slots)}` (`{app_c}` / `{ret_c}` / `{def_c}`) | {ts_str} | {_file_link(mm['path'], f'{ver}/manifest.json')} | `{mm['sha256'][:12]}` |"
        )
    add("")

    for ver in VERSIONS:
        doc = inv["manifests"][ver]
        base_dir = CANONICAL_ROOT / ver
        ver_label = {
            "v1": "Canonical Library v1 (`27` Active + `15` Retired R88 `B01–B15` = `42` SHA-256 Locked)",
            "v1_1": "Canonical Library v1.1 (`43` Active Locked Slots)",
            "v1_2": "Canonical Library v1.2 (`14` Active Locked + `1` `J04` Deferred)",
        }[ver]
        add(f"### 3.{2 + VERSIONS.index(ver)} {ver_label}")
        add("")

        # Group by category preserving manifest order
        cat_order: list[str] = []
        cat_slots: dict[str, list[dict[str, Any]]] = {}
        for sl in doc.get("slots") or []:
            cat = str(sl.get("category") or "uncategorized")
            if cat not in cat_slots:
                cat_order.append(cat)
                cat_slots[cat] = []
            cat_slots[cat].append(sl)

        for cat in cat_order:
            s_list = cat_slots[cat]
            add(f"#### Category `{cat}` ({len(s_list)} slots)")
            add("")
            add("| Slot ID | Status | Purpose | Usage Mode | Semantic ID Variation Rule | File Link | SHA-256[:12] |")
            add("|---|---|---|---|---|---|---|")
            for sl in s_list:
                sid = str(sl["slot_id"])
                status = str(sl.get("status") or "")
                purpose_raw = str(sl.get("when_to_use") or sl.get("title_ko") or "").strip()
                purpose = _md_cell(purpose_raw)
                usage_mode = _md_cell(_slot_usage_mode(ver, sl))
                sem_rule = _md_cell(_slot_semantic_rule(ver, sl))

                is_pair = cat == "F_transitions" or str(sl.get("asset_type") or "") == "start_end_transition_pair"
                if status not in ("approved", "retired_r88_cartoon_face"):
                    file_col = "`None` (deferred; `cand_01..03` excluded)"
                    sha_col = "`None`"
                elif is_pair:
                    s_rel = str(sl.get("approved_start_rel_path") or "")
                    e_rel = str(sl.get("approved_end_rel_path") or "")
                    s_sha = str(sl.get("approved_start_sha256") or "")[:12]
                    e_sha = str(sl.get("approved_end_sha256") or "")[:12]
                    file_col = f"S: {_file_link(base_dir / s_rel, Path(s_rel).name)}<br>E: {_file_link(base_dir / e_rel, Path(e_rel).name)}"
                    sha_col = f"`S:{s_sha}`<br>`E:{e_sha}`"
                else:
                    rel = str(sl.get("approved_rel_path") or "")
                    sha = str(sl.get("approved_sha256") or "")[:12]
                    file_col = _file_link(base_dir / rel, f"{Path(rel).parent.name}/{Path(rel).name}")
                    sha_col = f"`{sha}`"
                add(f"| `{sid}` | `{status}` | {purpose} | {usage_mode} | {sem_rule} | {file_col} | {sha_col} |")
            add("")

    add("---")
    add("")

    # Section 4: Negative Failure Ledger
    add("## §4. Negative Failure Ledger (`오답 노트` — What Cheap / Wrong Looks Like)")
    add("")
    add("### 4.1 `v1_2` Hard Rejections (`10` `[EXCL]` Candidates) & `J04` Deferral Root Cause")
    add("")
    v12_doc = inv["manifests"]["v1_2"]
    j04_sl = next(s for s in v12_doc["slots"] if s["slot_id"] == "J04_hook_paradox_prop_split_tabletop")
    add("> [!WARNING]")
    add("> **`J04_hook_paradox_prop_split_tabletop` Deferral Status (`deferred_flow_unusual_activity`)**:")
    add(f"> - **Manifest Status**: `{j04_sl['status']}` (`sha256_locked: {str(j04_sl['sha256_locked']).lower()}`, unused by `Ep #13`)")
    add("> - **Root Cause #1 (Conditioning Scale Bug)**: Conditioning directly on `H03_pulled_apart_empty_clear_capsule` caused extreme oversized macro capsule scale (`>25–30%` of the amber bottle mouth — `cand_01` ~185×460px glass-cup proportions, `cand_02` 4–5× oversized capsule over a closed white cap, `cand_03` ~230px wide > bottle mouth + 3-finger mitten hand defect).")
    add(f"> - **Root Cause #2 (Rate Limit Halt)**: {_md_cell(str(j04_sl.get('deferred_reason') or ''))}")
    add("> - **Regen Prescription**: Do NOT condition `J04` on oversized `H03`; condition on `G03_unlabeled_amber_pill_bottle_and_capsules` + `I01_data_stamp_backdrop_warm_tabletop_low30` and require miniature capsule width `<= 25–30%` of open bottle mouth, detached white cap placed beside bottle, and 4 distinct matte cream-vinyl fingers.")
    add("")
    add("| # | Slot ID | Rejected File | Verbatim `excluded_reasons` Entry (from `v1_2/manifest.json`) |")
    add("|---:|---|---|---|")
    excl_idx = 0
    for sl in v12_doc.get("slots") or []:
        er = sl.get("excluded_reasons") or {}
        for cand_fn in sorted(er.keys()):
            excl_idx += 1
            add(f"| {excl_idx} | `{sl['slot_id']}` | `{cand_fn}` | {_md_cell(er[cand_fn])} |")
    add("")

    add("### 4.2 `v1_1` Excluded Candidate Summary (`23` Outliers Screened Out)")
    add("")
    add("| Slot ID | Excluded File(s) | Screening Rejection Basis (`v1_1/manifest.json`) |")
    add("|---|---|---|")
    for sl in inv["manifests"]["v1_1"].get("slots") or []:
        ex_cands = sl.get("excluded_candidates") or []
        if ex_cands:
            add(f"| `{sl['slot_id']}` | {', '.join(f'`{c}`' for c in ex_cands)} | {_md_cell(str(sl.get('recommendation_reason') or ''))} |")
    add("")
    add("---")
    add("")

    # Section 5: Locked Audio, Fonts & Knowledge Base
    add("## §5. Locked Audio, Fonts & Knowledge Base Manifest")
    add("")
    add("### 5.1 Voice (`Solo Siren`) & BGM Bank")
    add(f"- **Active Narrator Lock (`R76-1`)**: `DEFAULT_DIORAMA_VOICE_PRESET = \"{cfg.DEFAULT_DIORAMA_VOICE_PRESET}\"`, `EXPRESSIVE_V8_R76_VOICE_PRESET = \"{cfg.EXPRESSIVE_V8_R76_VOICE_PRESET}\"`, `ELEVENLABS_VOICE_SIREN_ID = \"{cfg.ELEVENLABS_VOICE_SIREN_ID}\"` (`100%` solo narrator share, `0` foil/cameo voices, `DIORAMA_TTS_ENGINE = \"{cfg.DIORAMA_TTS_ENGINE}\"`, `EXPRESSIVE_V8_TARGET_LUFS = {cfg.EXPRESSIVE_V8_TARGET_LUFS}`, `EXPRESSIVE_V8_TRUE_PEAK_MAX_DBTP = {cfg.EXPRESSIVE_V8_TRUE_PEAK_MAX_DBTP}`).")
    add("")
    add("| Track Filename | Duration | Sample Rate / Ch | Bytes | File Link | SHA-256[:12] |")
    add("|---|---:|---|---:|---|---|")
    for bgm in inv["bgms"]:
        add(
            f"| `{bgm['filename']}` | `{bgm['duration_sec']:.3f}s` | `{bgm['sample_rate_hz']} Hz` / `{bgm['channels']}ch` | `{bgm['size_bytes']:,}` | {_file_link(bgm['path'])} | `{bgm['sha256'][:12]}` |"
        )
    add("")

    add("### 5.2 Expression Acting Lexicon & `4` Locked TTF Fonts")
    lex = inv["lexicon"]
    add(
        f"- **Expression Acting Lexicon**: {_file_link(lex['path'])} (`schema_version={lex['schema_version']}`, `{lex['expressions']}` 2D-ink expression archetypes, `{lex['speaker_mouth_rules']}` speaker mouth rules, `{lex['size_bytes']:,}` bytes, SHA-256 `{lex['sha256'][:12]}`)."
    )
    add("")
    add("| Font Filename | Pipeline Role | Bytes | File Link | SHA-256[:12] |")
    add("|---|---|---:|---|---|")
    for fnt in inv["fonts"]:
        add(f"| `{fnt['filename']}` | {fnt['role']} | `{fnt['size_bytes']:,}` | {_file_link(fnt['path'])} | `{fnt['sha256'][:12]}` |")
    add("")

    add("### 5.3 Knowledge Base `reusable_packs/` (`6` JSON Packs)")
    add("| Pack Filename | Entries | Notes / Schema | Bytes | Updated / Schema Tag | File Link | SHA-256[:12] |")
    add("|---|---:|---|---:|---|---|---|")
    for kb in inv["kb_packs"]:
        add(
            f"| `{kb['filename']}` | `{kb['entry_count']}` | {kb['detail']} | `{kb['size_bytes']:,}` | `{kb['updated_at_utc']}` | {_file_link(kb['path'])} | `{kb['sha256'][:12]}` |"
        )
    add("")

    return "\n".join(lines).rstrip() + "\n"


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp_bible_", suffix=".md")
    os.close(fd)
    tmp_p = Path(tmp_name)
    try:
        tmp_p.write_text(text, encoding="utf-8")
        os.replace(tmp_p, path)
    finally:
        if tmp_p.exists():
            tmp_p.unlink(missing_ok=True)


def run_check(inv: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    """Read-only verification of all manifests, SHA-256 locks, style sheet, and exact MD parity."""
    errors: list[str] = []
    if inv["missing_files"]:
        errors.extend([f"missing:{x}" for x in inv["missing_files"]])
    if inv["sha_mismatches"]:
        errors.extend([f"sha_mismatch:{x}" for x in inv["sha_mismatches"]])
    if inv["active_locked_slot_count"] != 84:
        errors.append(f"active_locked_slot_count={inv['active_locked_slot_count']} (expected 84)")
    if inv["retired_r88_slot_count"] != 15:
        errors.append(f"retired_r88_slot_count={inv['retired_r88_slot_count']} (expected 15)")
    if inv["locked_slot_count"] != 99:
        errors.append(f"locked_slot_count={inv['locked_slot_count']} (expected 99)")
    if inv["deferred_slot_count"] != 1:
        errors.append(f"deferred_slot_count={inv['deferred_slot_count']} (expected 1)")
    if inv["verified_slot_files"] != 125:
        errors.append(f"verified_slot_files={inv['verified_slot_files']} (expected 125)")
    if len(inv["ep31_anchors"]) != 4:
        errors.append(f"ep31_count={len(inv['ep31_anchors'])} (expected 4)")
    if len(inv["sheets"]) != 15:
        errors.append(f"sheet_count={len(inv['sheets'])} (expected 15)")
    if len(inv["fonts"]) != 4:
        errors.append(f"font_count={len(inv['fonts'])} (expected 4)")
    if len(inv["bgms"]) != 2:
        errors.append(f"bgm_count={len(inv['bgms'])} (expected 2)")
    if len(inv["kb_packs"]) != 6:
        errors.append(f"kb_pack_count={len(inv['kb_packs'])} (expected 6)")

    golden_info = {"width": 0, "height": 0, "size_bytes": 0, "sha256": ""}
    if not GOLDEN_SHEET_PATH.is_file():
        errors.append(f"missing_golden_sheet:{GOLDEN_SHEET_PATH}")
    else:
        gs_bytes = GOLDEN_SHEET_PATH.stat().st_size
        if gs_bytes <= 100_000:
            errors.append(f"golden_sheet_too_small:{gs_bytes}")
        try:
            with Image.open(GOLDEN_SHEET_PATH) as im:
                if im.format != "JPEG" or im.mode != "RGB":
                    errors.append(f"golden_sheet_invalid_format:{im.format}/{im.mode}")
                golden_info = {
                    "width": im.size[0],
                    "height": im.size[1],
                    "size_bytes": gs_bytes,
                    "sha256": compute_sha256(GOLDEN_SHEET_PATH),
                }
        except Exception as exc:  # noqa: BLE001
            errors.append(f"golden_sheet_corrupt:{exc}")

    md_exact_match = False
    if not BIBLE_MD_PATH.is_file():
        errors.append(f"missing_bible_md:{BIBLE_MD_PATH}")
    elif not errors or golden_info["size_bytes"] > 0:
        expected_md = generate_bible_markdown(inv, golden_info)
        actual_md = BIBLE_MD_PATH.read_text(encoding="utf-8")
        md_exact_match = expected_md == actual_md
        if not md_exact_match:
            errors.append("bible_md_drift:byte_mismatch")

    telemetry = {
        "mode": "check",
        "passed": len(errors) == 0,
        "active_locked_slots": inv["active_locked_slot_count"],
        "retired_r88_slots": inv["retired_r88_slot_count"],
        "locked_slots": inv["locked_slot_count"],
        "deferred_slots": inv["deferred_slot_count"],
        "verified_slot_files": inv["verified_slot_files"],
        "ep31_originals": len(inv["ep31_anchors"]),
        "contact_sheets": len(inv["sheets"]),
        "fonts": len(inv["fonts"]),
        "bgm_tracks": len(inv["bgms"]),
        "lexicon_expressions": inv["lexicon"]["expressions"],
        "kb_packs": len(inv["kb_packs"]),
        "golden_sheet_bytes": golden_info["size_bytes"],
        "golden_sheet_sha256": golden_info["sha256"][:12],
        "bible_md_bytes": BIBLE_MD_PATH.stat().st_size if BIBLE_MD_PATH.is_file() else 0,
        "bible_md_exact_match": md_exact_match,
        "master_pipeline_exists": MASTER_PIPELINE_PATH.is_file(),
        "errors": errors,
    }
    return len(errors) == 0, telemetry


def run_build(inv: dict[str, Any]) -> dict[str, Any]:
    """Builds Golden Style Sheet JPEG and LOCKED_ASSETS_AND_REFERENCES_BIBLE.md deterministically."""
    if inv["missing_files"] or inv["sha_mismatches"]:
        raise RuntimeError(f"Canonical asset integrity failure: missing={inv['missing_files']} mismatches={inv['sha_mismatches']}")
    golden_info = render_golden_style_sheet(inv, GOLDEN_SHEET_PATH)
    md_text = generate_bible_markdown(inv, golden_info)
    _atomic_write_text(BIBLE_MD_PATH, md_text)
    return {
        "mode": "build",
        "passed": True,
        "active_locked_slots": inv["active_locked_slot_count"],
        "retired_r88_slots": inv["retired_r88_slot_count"],
        "locked_slots": inv["locked_slot_count"],
        "deferred_slots": inv["deferred_slot_count"],
        "verified_slot_files": inv["verified_slot_files"],
        "ep31_originals": len(inv["ep31_anchors"]),
        "contact_sheets": len(inv["sheets"]),
        "fonts": len(inv["fonts"]),
        "bgm_tracks": len(inv["bgms"]),
        "kb_packs": len(inv["kb_packs"]),
        "golden_sheet_path": str(GOLDEN_SHEET_PATH),
        "golden_sheet_size": f"{golden_info['width']}x{golden_info['height']}",
        "golden_sheet_bytes": golden_info["size_bytes"],
        "golden_sheet_sha256": golden_info["sha256"][:12],
        "bible_md_path": str(BIBLE_MD_PATH),
        "bible_md_bytes": BIBLE_MD_PATH.stat().st_size,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build or drift-check Locked Assets Bible & Golden Style Sheet.")
    parser.add_argument("--check", action="store_true", help="Strictly read-only drift verification (exits 0 on pass, 1 on drift).")
    args = parser.parse_args(argv)

    inv = collect_inventory()
    if args.check:
        ok, telemetry = run_check(inv)
        print(json.dumps(telemetry, indent=2, ensure_ascii=False))
        return 0 if ok else 1

    telemetry = run_build(inv)
    print(json.dumps(telemetry, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
