"""
Unit & regression tests for Rule R65 v4 (`in_skull_cutaway_split_v4`):
  - Default `9:16` Shorts 50/50 In-Skull 3D Brain Cutaway Split architecture
  - Zero mannequin conditioning (`conditioning_paths=None` in `_generate_zero_credit_thumb_keyart_async`)
  - Clean `r65_v4_in_skull_split` upper-left micro-labels (zero 2D arrows/pills/bottom text)
  - `TQ1–TQ9` high-key luma (`>= 105`), 50/50 split + bottom-vs-top brain activation delta, and `y >= 1520` title-band safety
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image, ImageDraw

from pipeline import config as cfg
from pipeline import thumbnail_studio as ts
from pipeline.prompt_quality_v5 import validate_thumbnail_block_v7


def _make_synthetic_r65_v4_split_bgr(*, bright: bool = True, active_bottom: bool = True, seed: int = 0) -> np.ndarray:
    """Builds a synthetic 1080x1920 50/50 split-screen R65 v4 cover frame."""
    bg_val = 236 if bright else 42
    img = np.full((1920, 1080, 3), bg_val, dtype=np.uint8)
    rng = np.random.default_rng(100 + seed)

    # Crisp 6px white horizontal 50/50 divider at y = 960
    img[957:963, :] = 255

    # Top 50%: dark hair + calm human face + dark lab collar + dormant cool-grey in-skull brain cutaway
    cx = 640 + seed * 18
    cv2.ellipse(img, (cx + 15, 440), (225, 250), 0, 0, 360, (28, 32, 38), -1)
    cv2.ellipse(img, (cx, 520), (185, 235), 0, 0, 360, (182, 198, 218), -1)
    cv2.ellipse(img, (cx, 895), (320, 145), 0, 0, 360, (34, 42, 54), -1)
    # Dormant grey brain window
    cv2.ellipse(img, (cx + 35, 390), (145, 105), 0, 0, 360, (148, 142, 136), -1)
    cv2.ellipse(img, (cx + 35, 390), (145, 105), 0, 0, 360, (40, 44, 50), 6)
    for k in range(-3, 4):
        cv2.line(img, (cx - 80, 390 + k * 22), (cx + 150, 390 + k * 22), (72, 70, 68), 3)

    # Bottom 50%: dark hair + expressive reaction + dark lab collar + fiery crimson/cyan brain cutaway + 3D red arrow
    cv2.ellipse(img, (cx + 15, 1350), (230, 255), 0, 0, 360, (26, 30, 36), -1)
    cv2.ellipse(img, (cx, 1420), (190, 240), 0, 0, 360, (176, 192, 214), -1)
    cv2.ellipse(img, (cx, 1815), (335, 150), 0, 0, 360, (36, 44, 58), -1)
    if active_bottom:
        # Fiery crimson/orange + electric-cyan activation (BGR)
        cv2.ellipse(img, (cx + 35, 1270), (150, 110), 0, 0, 360, (28, 42, 245), -1)
        cv2.circle(img, (cx + 75, 1295), 58, (250, 215, 10), -1)
        # Volumetric 3D red arrow on left-center (above y=1500)
        pts = np.array([[220, 1460], [380, 1340], [360, 1315], [445, 1310], [420, 1395], [400, 1370], [250, 1490]], np.int32)
        cv2.fillPoly(img, [pts], (30, 35, 242))
    else:
        cv2.ellipse(img, (cx + 35, 1270), (150, 110), 0, 0, 360, (145, 142, 138), -1)

    for k in range(-3, 4):
        cv2.line(img, (cx - 80, 1270 + k * 22), (cx + 150, 1270 + k * 22), (55, 40, 120), 3)

    # Subtle texture grain so PNG size > 80 KB
    grain = rng.integers(-9, 10, size=img.shape, dtype=np.int16)
    img = np.clip(img.astype(np.int16) + grain, 0, 255).astype(np.uint8)
    img[957:963, :] = 255
    return img


def test_r65_v4_default_constants_and_agents_md_budget() -> None:
    assert cfg.R65_V4_THUMBNAIL_PROFILE == "in_skull_cutaway_split_v4"
    assert cfg.DEFAULT_SHORTS_THUMBNAIL_PROFILE == "in_skull_cutaway_split_v4"
    assert cfg.THUMB_V4_OVERLAY_MODE == "r65_v4_in_skull_split"
    assert cfg.THUMB_V4_MIN_MEAN_LUMA == 105.0
    assert cfg.THUMB_V4_BOTTOM_TITLE_SAFE_Y == 1520

    agents_md = Path(cfg.WORKSPACE_ROOT) / ".agents" / "AGENTS.md"
    raw_bytes = agents_md.read_bytes()
    lines = raw_bytes.decode("utf-8").splitlines()
    assert len(raw_bytes) < 10_240, f"AGENTS.md byte budget exceeded: {len(raw_bytes)}"
    assert len(lines) <= 78, f"AGENTS.md line budget exceeded: {len(lines)}"


def test_zero_mannequin_conditioning_in_keyart_generator(tmp_path: Path, monkeypatch: Any) -> None:
    """Verifies `_generate_zero_credit_thumb_keyart_async` NEVER attaches `cast_*.png` (`conditioning_paths=None`)."""
    p_dir = tmp_path / "v8_ep99_test"
    ref_dir = p_dir / "03_visuals" / "reference_images"
    ref_dir.mkdir(parents=True, exist_ok=True)
    # Plant cast_01.png & brain_01.png decoys that legacy v2 used to attach
    dummy = _make_synthetic_r65_v4_split_bgr()
    cv2.imwrite(str(ref_dir / "cast_01.png"), dummy)
    cv2.imwrite(str(ref_dir / "brain_01.png"), dummy)
    (p_dir / "03_visuals" / "flow_provenance_receipt.json").write_text(
        '{"flow_project_url": "https://flow.google.com/project/mock-room"}',
        encoding="utf-8",
    )

    captured: dict[str, Any] = {}

    class _DummyClient:
        async def eval(self, expr: str) -> str:
            _ = expr
            return "https://flow.google.com/project/mock-room"

    @asynccontextmanager
    async def _fake_lease(*args: Any, **kwargs: Any):
        _ = (args, kwargs)
        yield _DummyClient(), "tid_mock", "owner_mock"

    async def _fake_gen_batch(client: Any, **kwargs: Any) -> dict[str, Any]:
        _ = client
        captured.update(kwargs)
        out_p = Path(kwargs["out_path"])
        out_p.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(out_p), dummy)
        return {"saved_candidate_paths": [str(out_p)]}

    import pipeline.cdp_tab_lease as lease_mod
    import pipeline.flow_ingredients as ing_mod

    async def _noop_sleep(_s: float) -> None:
        return None

    monkeypatch.setattr(lease_mod, "leased_cdp_tab", _fake_lease)
    monkeypatch.setattr(ing_mod, "generate_flow_image_batch", _fake_gen_batch)
    monkeypatch.setattr(asyncio, "sleep", _noop_sleep)

    plan = {
        "title": "Why One Breath Terrified a Fearless Woman",
        "thumbnail": {
            "profile": "in_skull_cutaway_split_v4",
            "top_split_label": "NO FEAR",
            "bottom_split_label": "1 BREATH: PANIC!",
            "cover_sentence_index": 1,
        },
    }
    cands = asyncio.run(
        ts._generate_zero_credit_thumb_keyart_async(p_dir, plan=plan, script={"title": plan["title"]}, cdp_port=9222)
    )
    assert captured["conditioning_paths"] is None
    assert "never a white mannequin" in captured["prompt"].lower()
    assert "50/50" in captured["prompt"]
    assert len(cands) == 1
    assert cands[0].grammar == "r65_v4_in_skull_split_keyart"


def test_r65_v4_overlay_and_tq1_tq9_gates_positive_and_negative(tmp_path: Path) -> None:
    spec = {
        "profile": "in_skull_cutaway_split_v4",
        "top_split_label": "NO FEAR",
        "bottom_split_label": "1 BREATH: PANIC!",
        "render_micro_labels": True,
        "cover_sentence_index": 1,
    }
    clean_bgr = _make_synthetic_r65_v4_split_bgr(bright=True, active_bottom=True, seed=0)
    pil_img, meta = ts.render_overlay_with_meta(clean_bgr, "NO FEAR", thumb_spec=spec)
    assert meta["mode"] == "r65_v4_in_skull_split"
    assert meta["pointer_bbox"] is None
    assert meta["text_bbox"][3] < 1500

    vp = tmp_path / "var_A.png"
    ts._atomic_save_pil_png(pil_img, vp, max_bytes=cfg.SHORTS_THUMB_MAX_BYTES)
    m = ts.compute_image_metrics(clean_bgr)
    gates = ts.evaluate_thumbnail_gates(
        {"A": {"sharpness": m["sharpness"], "luma_std": m["luma_std"], "center_salience": m["center_salience"], "overlay": meta}},
        {"A": vp},
        hook_text="NO FEAR",
        title="Why One Breath Terrified a Fearless Woman",
        thumb_spec=spec,
    )
    assert all(g["passed"] for g in gates.values()), gates

    # Negative 1: Dark background (Mean Luma < 105) must fail TQ3
    dark_bgr = _make_synthetic_r65_v4_split_bgr(bright=False, active_bottom=True, seed=1)
    pil_dark, meta_dark = ts.render_overlay_with_meta(dark_bgr, "NO FEAR", thumb_spec=spec)
    vp_dark = tmp_path / "var_dark.png"
    ts._atomic_save_pil_png(pil_dark, vp_dark, max_bytes=cfg.SHORTS_THUMB_MAX_BYTES)
    m_dark = ts.compute_image_metrics(dark_bgr)
    gates_dark = ts.evaluate_thumbnail_gates(
        {"A": {"sharpness": m_dark["sharpness"], "luma_std": max(45.0, m_dark["luma_std"]), "center_salience": 1.3, "overlay": meta_dark}},
        {"A": vp_dark},
        hook_text="NO FEAR",
        thumb_spec=spec,
    )
    assert gates_dark["TQ3_sharpness_and_contrast"]["passed"] is False

    # Negative 2: Dormant bottom brain (zero activation delta) must fail TQ8
    dead_bgr = _make_synthetic_r65_v4_split_bgr(bright=True, active_bottom=False, seed=2)
    pil_dead, meta_dead = ts.render_overlay_with_meta(dead_bgr, "NO FEAR", thumb_spec=spec)
    vp_dead = tmp_path / "var_dead.png"
    ts._atomic_save_pil_png(pil_dead, vp_dead, max_bytes=cfg.SHORTS_THUMB_MAX_BYTES)
    m_dead = ts.compute_image_metrics(dead_bgr)
    gates_dead = ts.evaluate_thumbnail_gates(
        {"A": {"sharpness": m_dead["sharpness"], "luma_std": m_dead["luma_std"], "center_salience": 1.3, "overlay": meta_dead}},
        {"A": vp_dead},
        hook_text="NO FEAR",
        thumb_spec=spec,
    )
    assert gates_dead["TQ8_zero_head_occlusion"]["passed"] is False

    # Negative 3: Text stamped inside bottom Shorts UI title safe zone (y >= 1520) must fail TQ4 & TQ9
    bad_title_pil = pil_img.copy()
    d_bad = ImageDraw.Draw(bad_title_pil)
    fnt = ImageDraw.Draw(bad_title_pil).getfont()
    _ = fnt
    from PIL import ImageFont

    big_f = ImageFont.truetype(str(ts._resolve_v7_font_path()), 92)
    d_bad.text((120, 1620), "BOTTOM OVERLAP", fill=(255, 255, 255), font=big_f, stroke_width=10, stroke_fill=(8, 10, 14))
    vp_bad = tmp_path / "var_bad_bottom.png"
    ts._atomic_save_pil_png(bad_title_pil, vp_bad, max_bytes=cfg.SHORTS_THUMB_MAX_BYTES)
    meta_bad = dict(meta)
    meta_bad.pop("v4_split_metrics", None)
    gates_bad = ts.evaluate_thumbnail_gates(
        {"A": {"sharpness": m["sharpness"], "luma_std": m["luma_std"], "center_salience": 1.3, "overlay": meta_bad}},
        {"A": vp_bad},
        hook_text="NO FEAR",
        thumb_spec=spec,
    )
    assert gates_bad["TQ4_safe_zone_geometry"]["passed"] is False
    assert gates_bad["TQ9_pointer_text_non_overlap"]["passed"] is False


def test_prompt_gate_validates_r65_v4_thumbnail_block() -> None:
    plan_ok = {
        "style_profile": "expressive_25d_v8",
        "title": "Why One Breath Terrified a Fearless Woman",
        "thumbnail": {
            "profile": "in_skull_cutaway_split_v4",
            "top_split_label": "NO FEAR",
            "bottom_split_label": "1 BREATH: PANIC!",
            "cover_sentence_index": 1,
        },
    }
    assert validate_thumbnail_block_v7(plan_ok, {"title": plan_ok["title"], "style_profile": "expressive_25d_v8"}) == []

    plan_too_long = {
        "style_profile": "expressive_25d_v8",
        "title": "Why One Breath Terrified a Fearless Woman",
        "thumbnail": {
            "profile": "in_skull_cutaway_split_v4",
            "top_split_label": "THIS TOP LABEL IS WAY TOO LONG",
            "bottom_split_label": "1 BREATH: PANIC!",
            "cover_sentence_index": 1,
        },
    }
    errs = validate_thumbnail_block_v7(plan_too_long, {"title": plan_too_long["title"], "style_profile": "expressive_25d_v8"})
    assert any("top_split_label" in e for e in errs)


def test_r65_v4_shorts_2x3_shelf_crop_safe_zone_and_audit_fixes(tmp_path: Path) -> None:
    """
    Verifies @Research / @YouTube_CEO forensic audit fixes:
      1. Top micro-label stamped at y >= 176 (inside 2:3 Shorts shelf crop y = 150..1770) and y < 150 fails TQ4.
      2. Fallback video frames (VAR B/C) stamp BOTH top (y >= 176) and bottom (y >= 1016) labels cleanly.
      3. `build_r65_v4_in_skull_split_prompt` reads `top_human_action`, `bottom_human_action`, `target_anatomy`, `thumbnail_profile`, and supports `dark_void_paradox_v4` (Mode B).
      4. `_load_cached_keyart_candidates` single-candidate normalization does not collapse all axis scores to 0.5.
    """
    assert cfg.THUMB_V4_TOP_LABEL_Y_RANGE[0] >= 170
    spec = {
        "thumbnail_profile": "in_skull_cutaway_split_v4",
        "top_split_label": "NO FEAR",
        "bottom_split_label": "1 BREATH: PANIC!",
        "top_human_action": "Smiling woman holding a green venomous snake inches from her face",
        "bottom_human_action": "Same woman in terror taking one inhalation from a clear CO2 breathing mask",
        "target_anatomy": "bilateral amygdala vs brainstem panic circuit",
        "render_micro_labels": True,
        "cover_sentence_index": 1,
    }
    prompt_a = ts.build_r65_v4_in_skull_split_prompt({"thumbnail": spec}, {"title": "Fearless"})
    assert "green venomous snake" in prompt_a
    assert "clear CO2 breathing mask" in prompt_a
    assert "bilateral amygdala" in prompt_a
    assert "mean luminance >= 110" in prompt_a

    # Fallback video frame (VAR B/C) stamps BOTH top (y >= 176) and bottom (y >= 1016) labels
    clean_bgr = _make_synthetic_r65_v4_split_bgr(bright=True, active_bottom=True, seed=3)
    pil_fb, meta_fb = ts.render_overlay_with_meta(clean_bgr, "NO FEAR", thumb_spec=spec, is_fallback_video_frame=True)
    assert meta_fb["top_chunk_bbox"][1] >= 170
    assert meta_fb["bottom_chunk_bbox"] is not None
    assert meta_fb["bottom_chunk_bbox"][1] >= 1000
    assert len(meta_fb["lines"]) >= 2

    # Baked text clipped above y = 150 (e.g. y = 60) must FAIL TQ4 (safe_y_lo == 150)
    clipped_bgr = clean_bgr.copy()
    pil_clip = Image.fromarray(cv2.cvtColor(clipped_bgr, cv2.COLOR_BGR2RGB))
    d_clip = ImageDraw.Draw(pil_clip)
    from PIL import ImageFont

    fnt = ImageFont.truetype(str(ts._resolve_v7_font_path()), 96)
    d_clip.text((56, 62), "NO FEAR", fill=(255, 255, 255), font=fnt, stroke_width=10, stroke_fill=(8, 10, 14))
    d_clip.text((56, 1020), "PANIC!", fill=(255, 255, 255), font=fnt, stroke_width=10, stroke_fill=(8, 10, 14))
    clipped_baked_bgr = cv2.cvtColor(np.array(pil_clip, dtype=np.uint8), cv2.COLOR_RGB2BGR)
    baked_spec = dict(spec, render_micro_labels=False, labels_baked_in_keyart=True)
    pil_b, meta_b = ts.render_overlay_with_meta(clipped_baked_bgr, "NO FEAR", thumb_spec=baked_spec)
    vp_b = tmp_path / "clipped_top.png"
    ts._atomic_save_pil_png(pil_b, vp_b, max_bytes=cfg.SHORTS_THUMB_MAX_BYTES)
    m_b = ts.compute_image_metrics(clipped_baked_bgr)
    gates_b = ts.evaluate_thumbnail_gates(
        {"A": {"sharpness": m_b["sharpness"], "luma_std": m_b["luma_std"], "center_salience": 1.3, "overlay": meta_b}},
        {"A": vp_b},
        hook_text="NO FEAR",
        thumb_spec=baked_spec,
    )
    assert gates_b["TQ4_safe_zone_geometry"]["safe_y_range"][0] == 150
    assert gates_b["TQ4_safe_zone_geometry"]["passed"] is False

    # Mode B (`dark_void_paradox_v4`) permits dark void backdrop when explicitly requested
    dark_spec = dict(spec, thumbnail_profile="dark_void_paradox_v4")
    prompt_b = ts.build_r65_v4_in_skull_split_prompt({"thumbnail": dark_spec}, {"title": "Archival Paradox"})
    assert "dark studio void" in prompt_b
    dark_bgr = _make_synthetic_r65_v4_split_bgr(bright=False, active_bottom=True, seed=4)
    pil_dm, meta_dm = ts.render_overlay_with_meta(dark_bgr, "NO FEAR", thumb_spec=dark_spec)
    vp_dm = tmp_path / "dark_mode_b.png"
    ts._atomic_save_pil_png(pil_dm, vp_dm, max_bytes=cfg.SHORTS_THUMB_MAX_BYTES)
    m_dm = ts.compute_image_metrics(dark_bgr)
    gates_dm = ts.evaluate_thumbnail_gates(
        {"A": {"sharpness": m_dm["sharpness"], "luma_std": max(45.0, m_dm["luma_std"]), "center_salience": 1.3, "overlay": meta_dm}},
        {"A": vp_dm},
        hook_text="NO FEAR",
        thumb_spec=dark_spec,
    )
    assert gates_dm["TQ3_sharpness_and_contrast"]["passed"] is True

    # Single-candidate cached keyart normalization does not collapse all 4 axis scores to 0.5
    cand_dir = tmp_path / "ep_single" / "06_publish" / "keyart_candidates"
    cand_dir.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(cand_dir / "keyart_01.png"), clean_bgr)
    single_cands = ts._load_cached_keyart_candidates(tmp_path / "ep_single", {"thumbnail": spec})
    assert len(single_cands) == 1
    axis_vals = [single_cands[0].scores[k] for k in ("sharpness", "contrast", "colorfulness", "center_salience")]
    assert not all(abs(v - 0.5) < 1e-6 for v in axis_vals)

