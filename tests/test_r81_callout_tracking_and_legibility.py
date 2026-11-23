"""Rule R81 tests: XL PatrickHand sizing, 0px strikethrough underlines, 1.0x DISOpticalFlow tracking, and cross-cut buffer."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from pipeline import anatomy_label_overlay as alo
from pipeline import config as cfg
from pipeline import dynamic_episode_qa as dq
from pipeline.diorama_assembler import resolve_overlay_window_conflicts
from pipeline.flow_prompt_builder import build_expressive_v8_prompts


def test_r81_xl_typography_auto_stack_and_zero_strikethrough() -> None:
    # Case 1: Short labels ("Check OFF" vs "Warmth ON") -> single-line XL (>= 72px) + zero strikethrough
    short_cal = {
        "cut_index": 14,
        "callout_mode": "r78m_dual",
        "r78m_callout": {
            "left_lbl": "Check OFF",
            "right_lbl": "Warmth ON",
            "arrow": "vs",
            "sub": "Reality Check Offline",
            "left_rgb": [175, 198, 230],
            "right_rgb": [255, 86, 104],
            "left_xy": [255, 910],
            "right_xy": [520, 1080],
        },
    }
    im_short = alo.render_anatomy_callout_rgba_frame(short_cal, t_rel=1.2, total_dur=3.8)
    arr_s = np.asarray(im_short, dtype=np.uint8)
    ys_s, xs_s = np.where(arr_s[:, :, 3] > 0)
    assert int(ys_s.min()) >= 231
    assert int(ys_s.max()) < 1306
    assert int(xs_s.min()) >= 75
    assert int(xs_s.max()) <= cfg.UNIVERSAL_SAFE_X_RIGHT_PX

    # Verify underline pixels (crimson R>=220, G<=120) sit strictly BELOW white header glyph rows (R>240 & G>240 & B>230)
    header_band = arr_s[235:430, 480:905]
    white_rows = np.where(
        np.any(
            (header_band[:, :, 3] > 200)
            & (header_band[:, :, 0] > 240)
            & (header_band[:, :, 1] > 240)
            & (header_band[:, :, 2] > 230),
            axis=1,
        )
    )[0]
    crimson_ul_rows = np.where(
        np.sum(
            (header_band[:, :, 3] > 180)
            & (header_band[:, :, 0] > 215)
            & (header_band[:, :, 1] < 125),
            axis=1,
        )
        >= 40
    )[0]
    assert len(white_rows) >= 38, f"Expected XL header glyph height >= 38px, got {len(white_rows)}"
    assert len(crimson_ul_rows) >= 2, "Expected visible crimson underline stroke"
    # The first header block (before subtitle) ends strictly above crimson_ul_rows.min()!
    gaps = np.where(np.diff(white_rows) > 8)[0]
    hdr_only_max_row = int(white_rows[gaps[0]]) if len(gaps) > 0 else int(white_rows.max())
    assert int(crimson_ul_rows.min()) > hdr_only_max_row, (
        f"Underline struck through header glyphs: ul_min={crimson_ul_rows.min()} <= hdr_max={hdr_only_max_row}"
    )

    # Case 2: Long multi-word labels ("Vision Stream" -> "Fusiform Match") -> auto 2-line XL stack + DQ10 safe margins
    long_cal = {
        "cut_index": 6,
        "callout_mode": "r78m_dual",
        "r78m_callout": {
            "left_lbl": "Vision Stream",
            "right_lbl": "Fusiform Match",
            "arrow": "fwd",
            "sub": "100% Face Match",
            "left_rgb": [72, 224, 255],
            "right_rgb": [246, 196, 95],
            "left_xy": [262, 990],
            "right_xy": [588, 1072],
        },
    }
    im_long = alo.render_anatomy_callout_rgba_frame(long_cal, t_rel=1.2, total_dur=4.5)
    arr_l = np.asarray(im_long, dtype=np.uint8)
    bg = np.full((1920, 1080, 3), (15, 8, 5), dtype=np.uint8)
    al_f = arr_l[:, :, 3:4].astype(np.float32) / 255.0
    comp = np.clip(bg.astype(np.float32) * (1.0 - al_f) + arr_l[:, :, [2, 1, 0]].astype(np.float32) * al_f, 0, 255).astype(np.uint8)
    w_hdr, lm, rm = dq.measure_chapter_headline_bbox(comp, min_glyph_h_px=24)
    assert w_hdr > 0
    assert lm >= 75 and rm >= 75 and w_hdr <= 920


def test_r81_zero_lag_dis_optical_flow_tracks_large_150px_motion(tmp_path: Path) -> None:
    vid_p = tmp_path / "moving_brain.mp4"
    fps = 30
    n_frames = 45
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(vid_p), fourcc, float(fps), (1080, 1920))
    assert writer.isOpened()
    try:
        for i in range(n_frames):
            fr = np.full((1920, 1080, 3), (12, 10, 8), dtype=np.uint8)
            # Textured gray brain ellipse translating +150px right and +110px down (exceeds old ±75px clamp!)
            dx = int(round(150.0 * (i / float(n_frames - 1))))
            dy = int(round(110.0 * (i / float(n_frames - 1))))
            cv2.ellipse(fr, (480 + dx // 2, 920 + dy // 2), (340, 290), 0, 0, 360, (92, 96, 102), -1, cv2.LINE_AA)
            # Glowing cyan left hub & glowing crimson right hub moving +150px, +110px
            lx_true, ly_true = 280 + dx, 880 + dy
            rx_true, ry_true = 620 + dx, 960 + dy
            cv2.circle(fr, (lx_true, ly_true), 34, (255, 224, 72), -1, cv2.LINE_AA)   # BGR cyan
            cv2.circle(fr, (rx_true, ry_true), 34, (90, 76, 255), -1, cv2.LINE_AA)    # BGR crimson
            writer.write(fr)
    finally:
        writer.release()

    pts = alo._track_r78m_callout_points_on_video(
        vid_p,
        cut_start_sec=0.0,
        t0=0.0,
        t1=1.45,
        fps=fps,
        left_xy=(280.0, 880.0),
        right_xy=(620.0, 960.0),
        n_frames=44,
        width=1080,
        height=1920,
        left_rgb=(72, 224, 255),
        right_rgb=(255, 86, 104),
    )
    assert len(pts) == 44
    (lx_end, ly_end), (rx_end, ry_end) = pts[-1]
    # Old 0.12x tracker moved < 25px and clamped at +85/+75px; R81 1.0x tracker follows full +145px/+105px!
    assert abs(lx_end - 426.0) <= 22.0, f"Left X lagged behind moving cyan hub: {lx_end}"
    assert abs(ly_end - 987.0) <= 22.0, f"Left Y lagged behind moving cyan hub: {ly_end}"
    assert abs(rx_end - 766.0) <= 22.0, f"Right X lagged behind moving crimson hub: {rx_end}"
    assert abs(ry_end - 1067.0) <= 22.0, f"Right Y lagged behind moving crimson hub: {ry_end}"


def test_r81_cross_cut_buffer_preserves_adjacent_cut_callout_and_flow_parallax_guard() -> None:
    stamps = [{"start_sec": 63.76, "end_sec": 67.61}]
    callouts = [
        {
            "cut_index": 14,
            "cut_start_sec": 58.3667,
            "cut_end_sec": 63.70,
            "start_sec": 58.507,
            "end_sec": 63.60,
            "duration_sec": 5.093,
            "callout_mode": "r78m_dual",
        }
    ]
    kept, conflicts = resolve_overlay_window_conflicts(stamps, callouts)
    assert len(kept) == 1
    assert conflicts == []
    assert kept[0]["end_sec"] == 63.60

    # Verify Flow prompt builder injects <= 20-degree single-plane parallax guard on r78m_flow_prompt clips
    plan = {
        "project_id": "v8_r81_prompt_test",
        "clips": [
            {
                "clip_number": idx,
                "act": min(6, (idx - 1) // 3 + 1),
                "grammar": "brain_simulator_3d",
                "camera_move": "circuit_cooperation_drone",
                "r78m_flow_prompt": "Sagittal frosted slate brain cutaway with glowing golden hippocampus.",
            }
            for idx in range(1, 16)
        ],
    }
    prompts = build_expressive_v8_prompts(plan, ["His hippocampus wove a live mental map."])
    assert "no 90-degree sagittal-to-coronal head spin" in prompts[0]["prompt"]


def test_r78m_single_callout_never_renders_target_hub_and_tracks_single_hub(tmp_path: Path) -> None:
    edl = {
        "cuts": [
            {
                "cut_index": 18,
                "clip_index": 18,
                "grammar": "expressive_xray_brain",
                "camera_move": "gentle_push_in",
                "out_start_sec": 68.0,
                "out_end_sec": 73.4,
                "callout_enabled": True,
                "callout_style": "r78m_single",
                "r78m_callout": {
                    "enabled": True,
                    "style": "ink_pen",
                    "mode": "r78m_single",
                    "left_lbl": "Prefrontal Control",
                    "left_rgb": [39, 216, 255],
                    "left_target_xy": [0.35, 0.38],
                    "lock_seed_xy": True,
                },
            }
        ]
    }
    wins = alo.resolve_anatomy_callout_windows(edl)
    assert len(wins) == 1
    assert wins[0]["callout_mode"] == "r78m_single"

    im_single = alo.render_anatomy_callout_rgba_frame(wins[0], t_rel=1.5, total_dur=5.1)
    arr = np.asarray(im_single, dtype=np.uint8)
    ys, xs = np.where(arr[:, :, 3] > 0)
    assert len(xs) > 500
    assert int(xs.min()) >= 75
    assert int(xs.max()) <= cfg.UNIVERSAL_SAFE_X_RIGHT_PX
    # Header is a single centered block (~X=220..760), NOT a 2-column "Prefrontal Control -> Target Hub" spanning ~X=800..904 right arrow zone
    bg = np.full((1920, 1080, 3), (15, 8, 5), dtype=np.uint8)
    al_f = arr[:, :, 3:4].astype(np.float32) / 255.0
    comp = np.clip(bg.astype(np.float32) * (1.0 - al_f) + arr[:, :, [2, 1, 0]].astype(np.float32) * al_f, 0, 255).astype(np.uint8)
    w_hdr, lm, rm = dq.measure_chapter_headline_bbox(comp, min_glyph_h_px=24)
    assert w_hdr > 0 and lm >= 75 and rm >= 75 and w_hdr <= 700
    # Target ring is centered near (0.35*1080=378, 0.38*1920=730) with zero bogus right ring around x=720, y=960
    assert not np.any(arr[920:1000, 680:760, 3] > 180)
    assert np.any(arr[695:765, 345:415, 3] > 180)

    # Single-point DISOpticalFlow tracking on moving cyan PFC without bogus flip detection
    vid_p = tmp_path / "single_pfc.mp4"
    fps = 30
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(vid_p), fourcc, float(fps), (1080, 1920))
    assert writer.isOpened()
    try:
        for i in range(45):
            fr = np.full((1920, 1080, 3), (12, 10, 8), dtype=np.uint8)
            dx = int(round(60.0 * (i / 44.0)))
            dy = int(round(45.0 * (i / 44.0)))
            cv2.ellipse(fr, (520 + dx // 2, 820 + dy // 2), (320, 270), 0, 0, 360, (108, 112, 118), -1, cv2.LINE_AA)
            cv2.circle(fr, (378 + dx, 730 + dy), 32, (255, 216, 39), -1, cv2.LINE_AA)
            writer.write(fr)
    finally:
        writer.release()

    pts, meta = alo._track_r78m_callout_points_on_video(
        vid_p,
        cut_start_sec=0.0,
        t0=0.0,
        t1=1.45,
        fps=fps,
        left_xy=(378.0, 730.0),
        right_xy=(378.0, 730.0),
        n_frames=44,
        width=1080,
        height=1920,
        left_rgb=(39, 216, 255),
        right_rgb=(39, 216, 255),
        lock_seed_xy=True,
        single_point=True,
        return_meta=True,
    )
    assert len(pts) == 44
    assert meta["flip_rel_sec"] is None
    (tx_end, ty_end), _ = pts[-1]
    assert abs(tx_end - 438.0) <= 22.0
    assert abs(ty_end - 775.0) <= 22.0


def test_r78m_stacked_cutaway_k06_header_and_lower_pointer_safe_ybands(tmp_path: Path) -> None:
    edl = {
        "cuts": [
            {
                "cut_index": 10,
                "clip_index": 10,
                "grammar": "expressive_xray_brain",
                "camera_move": "gentle_push_in",
                "out_start_sec": 31.4,
                "out_end_sec": 35.83,
                "callout_enabled": True,
                "stacked_cutaway_brain_compare": True,
                "r78m_callout": {
                    "enabled": True,
                    "style": "ink_pen",
                    "mode": "r78m_dual",
                    "left_lbl": "Sweet Snack Surge",
                    "left_rgb": [234, 179, 75],
                    "right_lbl": "Plain Food Dulled",
                    "right_rgb": [148, 163, 184],
                    "left_target_xy": [0.38, 0.28],
                    "right_target_xy": [0.38, 0.72],
                    "lock_seed_xy": True,
                    "stacked_vstack": True,
                },
            }
        ]
    }
    wins = alo.resolve_anatomy_callout_windows(edl)
    assert len(wins) == 1
    assert wins[0]["callout_mode"] == "r78m_dual"
    assert wins[0]["stacked_cutaway_brain_compare"] is True

    im = alo.render_anatomy_callout_rgba_frame(wins[0], t_rel=2.0, total_dur=4.2)
    arr = np.asarray(im, dtype=np.uint8)
    # 1. Header text ink lies cleanly inside Y=5-10% (103..159px), zero dorsal cortex overlap
    white_hdr = (arr[:, :, 0] >= 220) & (arr[:, :, 1] >= 220) & (arr[:, :, 2] >= 210) & (arr[:, :, 3] >= 160)
    hdr_ys, _ = np.where(white_hdr)
    assert hdr_ys.size >= 4000
    assert int(hdr_ys.min()) >= int(0.05 * 1920)
    assert int(hdr_ys.max()) <= int(0.10 * 1920)
    # 2. Lower-brain pointer ring sits inside Y=58-63% (1113..1210px +/- 22px ring radius) and leaves Y >= 66% (ASS zone Y >= 70%) 100% clear!
    assert np.any(arr[1090:1235, 385:435, 3] > 180)
    assert not np.any(arr[int(0.66 * 1920) :, :, 3] > 40)

    # 3. Tracker keeps stacked lower target inside Y=58-63% across motion frames
    vid_p = tmp_path / "k06_stacked.mp4"
    writer = cv2.VideoWriter(str(vid_p), cv2.VideoWriter_fourcc(*"mp4v"), 30.0, (1080, 1920))
    assert writer.isOpened()
    try:
        for i in range(30):
            fr = np.full((1920, 1080, 3), (17, 7, 4), dtype=np.uint8)
            dy = int(round(35.0 * (i / 29.0)))
            cv2.ellipse(fr, (520, 520 + dy), (300, 190), 0, 0, 360, (180, 185, 190), -1, cv2.LINE_AA)
            cv2.ellipse(fr, (520, 1340 + dy), (300, 190), 0, 0, 360, (140, 145, 150), -1, cv2.LINE_AA)
            writer.write(fr)
    finally:
        writer.release()

    pts = alo._track_r78m_callout_points_on_video(
        vid_p,
        cut_start_sec=0.0,
        t0=0.0,
        t1=0.95,
        fps=30,
        left_xy=(410.0, 538.0),
        right_xy=(410.0, 1380.0),
        n_frames=28,
        width=1080,
        height=1920,
        lock_seed_xy=True,
        is_stacked_vstack=True,
    )
    assert len(pts) == 28
    assert all(0.58 * 1920.0 - 0.1 <= r_pt[1] <= 0.63 * 1920.0 + 0.1 for _, r_pt in pts)

