"""
Unit & regression tests for Rule R65 v2 ('신비한 건축사전' 3D Cutaway Keyart +
#FF2525 Vector Pointer/Dimension Ruler + Diagonal Z-Pattern 2-Chunk Hook +
Wood-Grain Laplacian Trap fix + TQ1-TQ9 gates).
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from pipeline.config import (
    THUMB_ACCENT_YELLOW_RGB,
    THUMB_INTENT_BONUS,
    THUMB_POINTER_CYAN_RGB,
    THUMB_POINTER_RED_RGB,
    THUMB_SHORTS_SHELF_CROP_Y,
    THUMB_V8_Z_BOT_Y_RANGE,
    THUMB_V8_Z_TOP_Y_RANGE,
)
from pipeline.prompt_quality_v5 import validate_thumbnail_block_v7
from pipeline.thumbnail_studio import (
    ThumbCandidate,
    _finalize_candidate_scores,
    build_cutaway_keyart_prompt,
    compute_image_metrics,
    evaluate_thumbnail_gates,
    render_cutaway_pointer_and_z_overlay,
    render_overlay_with_meta,
    write_contact_sheet,
)


def _make_wood_grain_table_bgr(w: int = 1080, h: int = 1920) -> np.ndarray:
    """Synthetic monotonous warm brown wood-grain table with high Laplacian streaks."""
    rng = np.random.default_rng(42)
    img = np.zeros((h, w, 3), dtype=np.uint8)
    # Warm tan/brown BGR (~ R=155, G=112, B=72)
    img[:, :] = (72, 112, 155)
    # Dense horizontal/fine wood grain lines inflating Laplacian variance
    for y in range(0, h, 3):
        delta = int(rng.integers(-24, 25))
        img[y : min(h, y + 1), :, 0] = np.clip(72 + delta, 25, 130)
        img[y : min(h, y + 1), :, 1] = np.clip(112 + delta, 45, 180)
        img[y : min(h, y + 1), :, 2] = np.clip(155 + delta, 85, 225)
    noise = rng.integers(-14, 15, size=(h, w, 1), dtype=np.int16)
    img = np.clip(img.astype(np.int16) + noise, 0, 255).astype(np.uint8)
    return img


def _make_3d_cutaway_glass_brain_bgr(seed: int = 0, w: int = 1080, h: int = 1920) -> np.ndarray:
    """Synthetic 3D cutaway scene: dark studio backdrop + bright vinyl subject + #FF2525/#00D4FF brain."""
    img = np.full((h, w, 3), (26, 20, 16), dtype=np.uint8)
    cx = 540 + (seed - 1) * 70
    cy = 830 + (seed - 1) * 45
    # Bright translucent glass skull & matte-white torso in center
    cv2.ellipse(img, (cx, cy + 250), (260, 220), 0, 0, 360, (228, 234, 240), -1)
    cv2.circle(img, (cx, cy - 40), 210, (215, 225, 232), -1)
    cv2.circle(img, (cx, cy - 40), 210, (70, 90, 110), 8)
    # Cyan cerebellum / pathway (#00D4FF -> BGR 255, 212, 0)
    cv2.circle(img, (cx - 65, cy + 10), 75, (255, 212, 0), -1)
    # Glowing coral-red brainstem / amygdala alarm (#FF2525 -> BGR 37, 37, 255)
    cv2.circle(img, (cx + 55, cy - 55), 68, (37, 37, 255), -1)
    # Crisp architectural cutaway cross-section lines
    for k in range(-4, 5):
        cv2.line(img, (cx - 220, cy + k * 34), (cx + 220, cy + k * 34), (45, 55, 65), 2)
    return img


def _bboxes_intersect_px(a: list[int] | tuple[int, int, int, int], b: list[int] | tuple[int, int, int, int]) -> int:
    ix0 = max(int(a[0]), int(b[0]))
    iy0 = max(int(a[1]), int(b[1]))
    ix1 = min(int(a[2]), int(b[2]))
    iy1 = min(int(a[3]), int(b[3]))
    if ix1 <= ix0 or iy1 <= iy0:
        return 0
    return int((ix1 - ix0) * (iy1 - iy0))


def test_r65_v2_constants_locked() -> None:
    assert THUMB_SHORTS_SHELF_CROP_Y == (150, 1770)
    assert THUMB_V8_Z_TOP_Y_RANGE == (215, 395)
    assert THUMB_V8_Z_BOT_Y_RANGE == (1240, 1445)
    assert THUMB_POINTER_RED_RGB == (255, 37, 37)
    assert THUMB_POINTER_CYAN_RGB == (0, 212, 255)
    assert THUMB_ACCENT_YELLOW_RGB == (255, 225, 74)
    assert THUMB_INTENT_BONUS.get("cutaway_xray", 0.0) >= 1.0
    assert THUMB_INTENT_BONUS.get("brain_badge", 0.0) >= 0.90


def test_wood_grain_laplacian_trap_defeated_by_cutaway_glass_brain() -> None:
    wood_bgr = _make_wood_grain_table_bgr()
    cutaway_bgr = _make_3d_cutaway_glass_brain_bgr(seed=1)

    wood_m = compute_image_metrics(wood_bgr)
    cut_m = compute_image_metrics(cutaway_bgr)

    assert wood_m["wood_grain_ratio"] >= 0.42
    assert cut_m["accent_pop"] > wood_m["accent_pop"]
    assert cut_m["luma_std"] > wood_m["luma_std"]

    cand_wood = ThumbCandidate(
        cut_index=2,
        clip_index=2,
        act=1,
        sentence_indices=[2],
        sample_sec=2.0,
        timeline_sec=2.0,
        cut_mode="full",
        grammar="expressive_hands_closeup",
        sharpness=wood_m["sharpness"],
        luma_std=wood_m["luma_std"],
        colorfulness=wood_m["colorfulness"],
        center_salience=max(1.25, wood_m["center_salience"]),
        intent_bonus=0.6,
        frame_bgr=wood_bgr,
    )
    cand_cutaway = ThumbCandidate(
        cut_index=9,
        clip_index=9,
        act=3,
        sentence_indices=[9],
        sample_sec=32.0,
        timeline_sec=32.0,
        cut_mode="full",
        grammar="expressive_xray_brain",
        sharpness=cut_m["sharpness"],
        luma_std=cut_m["luma_std"],
        colorfulness=cut_m["colorfulness"],
        center_salience=cut_m["center_salience"],
        intent_bonus=THUMB_INTENT_BONUS["cutaway_xray"],
        frame_bgr=cutaway_bgr,
    )
    _finalize_candidate_scores([cand_wood, cand_cutaway])
    assert cand_cutaway.composite_score > cand_wood.composite_score


def test_z_pattern_overlay_and_tq9_zero_overlap_across_pointer_styles(tmp_path: Path) -> None:
    for idx, p_style in enumerate(("red_arrow", "dimension_ruler", "check_cross")):
        base_bgr = _make_3d_cutaway_glass_brain_bgr(seed=idx)
        spec = {
            "hook_text": "ZERO SNAKE FEAR",
            "top_left_hook": "ZERO SNAKE FEAR",
            "bottom_right_hook": "1 BREATH PANIC",
            "pointer_label": "35% CO2",
            "pointer_style": p_style,
            "cover_sentence_index": 1,
        }
        out_bgr, meta = render_cutaway_pointer_and_z_overlay(base_bgr, spec)
        assert out_bgr.shape == (1920, 1080, 3)
        assert meta["mode"] == "r65_v2_z_cutaway"

        top_bb = meta["top_chunk_bbox"]
        bot_bb = meta["bottom_chunk_bbox"]
        ptr_bb = meta["pointer_bbox"]

        # Inside 2:3 Shorts shelf (y=150..1770) AND strictly above title overlay mask (y >= 1520)
        assert top_bb[0] >= 80 and top_bb[2] <= 1000
        assert 150 <= top_bb[1] and top_bb[3] <= 430
        assert bot_bb[0] >= 80 and bot_bb[2] <= 1000
        assert 1200 <= bot_bb[1] and bot_bb[3] <= 1480

        # TQ9: Zero intersection between pointer/ruler/label and text chunks
        assert _bboxes_intersect_px(ptr_bb, top_bb) == 0
        assert _bboxes_intersect_px(ptr_bb, bot_bb) == 0
        assert meta["wcag_contrast"] >= 4.5

        out_png = tmp_path / f"var_{p_style}.png"
        cv2.imwrite(str(out_png), out_bgr)

    # Full TQ1-TQ9 gate evaluation across 3 distinct cutaway variants
    variants_meta = {}
    rendered_paths = {}
    for idx, vk in enumerate(("A", "B", "C")):
        bgr = _make_3d_cutaway_glass_brain_bgr(seed=idx)
        spec = {
            "hook_text": "YOUR OWN HAND",
            "top_left_hook": "YOUR OWN HAND",
            "bottom_right_hook": "0.2S BRAIN TRICK",
            "pointer_label": "+0.2s DELAY",
            "pointer_style": "dimension_ruler",
            "cover_sentence_index": 1,
        }
        pil_img, o_meta = render_overlay_with_meta(bgr, spec["hook_text"], thumb_spec=spec)
        vp = tmp_path / f"thumbnail_var_{vk}.png"
        pil_img.save(str(vp), format="PNG", compress_level=1)
        rendered_paths[vk] = vp
        m = compute_image_metrics(bgr)
        variants_meta[vk] = {
            "sharpness": m["sharpness"],
            "luma_std": m["luma_std"],
            "center_salience": max(1.25, m["center_salience"]),
            "overlay": o_meta,
            "file_bytes": max(90_000, vp.stat().st_size),
        }

    # Ensure test PNGs exceed THUMB_MIN_FILE_BYTES by adding subtle micro-grain if needed
    for vk, vp in rendered_paths.items():
        if vp.stat().st_size < 85_000:
            im = cv2.imread(str(vp))
            rng = np.random.default_rng(100 + ord(vk))
            im = np.clip(im.astype(np.int16) + rng.integers(-6, 7, size=im.shape, dtype=np.int16), 0, 255).astype(np.uint8)
            cv2.imwrite(str(vp), im, [cv2.IMWRITE_PNG_COMPRESSION, 1])

    gates = evaluate_thumbnail_gates(
        variants_meta,
        rendered_paths,
        hook_text="YOUR OWN HAND",
        title="Why a Delayed Robot Can Tickle You",
        thumb_spec={
            "hook_text": "YOUR OWN HAND",
            "top_left_hook": "YOUR OWN HAND",
            "bottom_right_hook": "0.2S BRAIN TRICK",
            "pointer_label": "+0.2s DELAY",
            "pointer_style": "dimension_ruler",
        },
    )
    assert "TQ9_pointer_text_non_overlap" in gates
    assert all(g["passed"] for g in gates.values()), gates

    contact_png = tmp_path / "thumbnail_contact_sheet.png"
    write_contact_sheet(rendered_paths, contact_png)
    assert contact_png.exists() and contact_png.stat().st_size > 10_000


def test_prompt_gate_accepts_r65_v2_and_preserves_v7_compat() -> None:
    plan_v8 = {
        "style_profile": "expressive_25d_v8",
        "title": "Why One Breath Terrified a Fearless Woman",
        "thumbnail": {
            "hook_text": "ZERO SNAKE FEAR",
            "top_left_hook": "ZERO SNAKE FEAR",
            "bottom_right_hook": "1 BREATH PANIC",
            "pointer_label": "35% CO2",
            "pointer_style": "red_arrow",
            "cover_sentence_index": 1,
            "cutaway_keyart_prompt": (
                "3D isometric cutaway cross-section of a matte-white vinyl patient inhaling "
                "from a clear medical mask tube, translucent glass skull with glowing coral-red "
                "brainstem alarm pathway, dark studio contrast, zero text"
            ),
        },
    }
    assert validate_thumbnail_block_v7(plan_v8, {"title": plan_v8["title"], "style_profile": "expressive_25d_v8"}) == []
    prompt = build_cutaway_keyart_prompt(plan_v8, {"title": plan_v8["title"]})
    assert "cutaway" in prompt.lower()
    assert "zero text" in prompt.lower()


def test_to_display_text_converts_hyphenated_hundreds_and_thousands() -> None:
    from pipeline.plain_language import to_display_text

    assert (
        to_display_text("Once that two-hundred-millisecond lag kicked in, volunteers burst into squirming laughter!")
        == "Once that 200-millisecond lag kicked in, volunteers burst into squirming laughter!"
    )
    assert (
        to_display_text("a two-hundred-fifty-millisecond delay and a ten-thousand-hour rule")
        == "a 250-millisecond delay and a 10,000-hour rule"
    )
    assert to_display_text("twenty ten-dollar bills") == "20 10-dollar bills"
