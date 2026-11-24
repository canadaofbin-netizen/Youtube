"""
ALL ABOUT BRAIN — R71 / R81 Hand-Drawn Pen Leader-Line Anatomical Callout Overlay (`pipeline/anatomy_overlay.py`).

Preserves 100% of the signature PatrickHand handwritten typography, warm ivory/cyan/gold/crimson/slate ink palette,
and box-free tapered fountain-pen strokes (`style="ink_pen"`) while upgrading:
  1. XL mobile legibility (`82-84px` single-line or automatic 2-line centered hub stack + `56px` subtitle + dark ink rim),
  2. Zero-strikethrough underline geometry (`0px` overlap — underlines placed strictly below rendered glyph descenders),
  3. Zero-lag `1.0x` `DISOpticalFlow` + hue-emission peak centroid lock + zero-phase smoothing + `90°` view-flip guard.
"""

from __future__ import annotations

import json
import math
import subprocess
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from pipeline.anatomy_map import resolve_anatomy_screen_anchor
from pipeline.config import (
    DATA_STAMP_Y_FRAC_RANGE,
    R71_CALLOUT_MODES,
    R81_CALLOUT_UNDERLINE_GAP_PX,
    R81_CALLOUT_XL_SINGLE_LINE_MAX_PX,
    R81_CALLOUT_XL_SINGLE_LINE_MIN_PX,
    R81_CALLOUT_XL_STACK_MAX_PX,
    R81_CALLOUT_XL_STACK_MIN_PX,
    R81_CALLOUT_XL_SUB_MAX_PX,
    R81_CALLOUT_XL_SUB_MIN_PX,
    R81_TRACKING_MAX_Y_PX,
    R81_TRACKING_MIN_Y_PX,
    R81_TRACKING_SMOOTH_SIGMA_FRAMES,
    R81_VIEW_FLIP_FADE_SEC,
    R81_VIEW_FLIP_MIN_SPAN_RATIO,
    UNIVERSAL_SAFE_X_RIGHT_PX,
    VIDEO_HEIGHT,
    VIDEO_WIDTH,
)
from pipeline.stamp_overlay import (
    _draw_text_with_soft_halo,
    _ease_in_out_cubic,
    _ease_out_cubic,
    _ffmpeg_exe,
    _load_hand_font,
    draw_tapered_hand_stroke,
)


def _resolve_cut_callout_mode(
    cam_move: str,
    neural_state: str,
    anc_start: dict[str, Any] | None,
    anc_end: dict[str, Any] | None,
    explicit_mode: str = "",
) -> str:
    mode = str(explicit_mode or "").strip().lower()
    if mode in R71_CALLOUT_MODES:
        if mode in ("pathway_relay", "pathway_severed") and (anc_start is None or anc_end is None):
            return "single_region"
        return mode
    has_distinct_pair = (
        anc_start is not None
        and anc_end is not None
        and anc_start["canonical"] != anc_end["canonical"]
    )
    if has_distinct_pair and neural_state == "severed":
        return "pathway_severed"
    if has_distinct_pair and (cam_move == "neural_tract_relay_flight" or neural_state in ("active", "rerouted")):
        return "pathway_relay"
    return "single_region"


def _load_camera_track(
    cut: dict[str, Any],
    vp_c: dict[str, Any],
    clip_num: int,
    visuals_dir: Path | None,
) -> dict[str, Any] | None:
    """Loads `<clip_stem>_camera_track.json` emitted by Blender 4.2 Brain Simulator (`0.0 px` overlay lock)."""
    candidates: list[Path] = []
    for raw in (cut.get("camera_track_file"), vp_c.get("camera_track_file")):
        if raw:
            candidates.append(Path(str(raw)))
    for raw_clip in (cut.get("clip_file"), vp_c.get("clip_file"), cut.get("video_path")):
        if raw_clip:
            cp = Path(str(raw_clip))
            candidates.append(cp.with_name(f"{cp.stem}_camera_track.json"))
    if visuals_dir is not None:
        vdir = Path(visuals_dir)
        candidates.append(vdir / "brain_simulator_clips" / f"clip_{clip_num}_camera_track.json")
        candidates.append(vdir / "brain_simulator_clips" / f"clip_{clip_num:02d}_camera_track.json")
    for cand in candidates:
        try:
            if cand.is_file():
                doc = json.loads(cand.read_text(encoding="utf-8"))
                if isinstance(doc, dict) and isinstance(doc.get("frames"), list) and doc["frames"]:
                    return doc
        except Exception:  # noqa: BLE001
            continue
    return None


def _interpolate_track_xy(
    track: dict[str, Any] | None,
    anchor_key: str,
    t_in_clip: float,
    width: int,
    height: int,
) -> tuple[float, float] | None:
    """Linearly interpolates `(x_px, y_px)` at clip-local time `t_in_clip` from Blender `camera_track.json`."""
    if not isinstance(track, dict):
        return None
    frames = track.get("frames")
    if not isinstance(frames, list) or not frames:
        return None
    fps = float(track.get("fps") or 30.0)
    f_pos = max(0.0, min(float(len(frames) - 1), float(t_in_clip) * fps))
    i0 = int(math.floor(f_pos))
    i1 = min(len(frames) - 1, i0 + 1)
    frac = f_pos - float(i0)

    def _xy_of(frame_row: Any) -> tuple[float, float] | None:
        if not isinstance(frame_row, dict):
            return None
        anc_map = frame_row.get("anchors")
        if not isinstance(anc_map, dict):
            return None
        node = anc_map.get(anchor_key)
        if not isinstance(node, dict):
            return None
        if "x_norm" in node and "y_norm" in node:
            return (float(node["x_norm"]) * float(width), float(node["y_norm"]) * float(height))
        xyn = node.get("xy_norm")
        if isinstance(xyn, (list, tuple)) and len(xyn) >= 2:
            return (float(xyn[0]) * float(width), float(xyn[1]) * float(height))
        if "x_px" in node and "y_px" in node:
            tw = float(track.get("width") or width or 1080)
            th = float(track.get("height") or height or 1920)
            return (float(node["x_px"]) * float(width) / max(tw, 1.0), float(node["y_px"]) * float(height) / max(th, 1.0))
        xyp = node.get("xy_px")
        if isinstance(xyp, (list, tuple)) and len(xyp) >= 2:
            tw = float(track.get("width") or width or 1080)
            th = float(track.get("height") or height or 1920)
            return (float(xyp[0]) * float(width) / max(tw, 1.0), float(xyp[1]) * float(height) / max(th, 1.0))
        return None

    p0 = _xy_of(frames[i0])
    p1 = _xy_of(frames[i1])
    if p0 is None:
        return p1
    if p1 is None:
        return p0
    return (
        p0[0] + (p1[0] - p0[0]) * frac,
        p0[1] + (p1[1] - p0[1]) * frac,
    )


def _r76_clinical_accent_rgb(role: str, neural_state: str, region_name: str = "") -> tuple[int, int, int]:
    """Matte zero-glow clinical palette aligned with Blender 4.2 Brain Simulator (`R76`)."""
    r_low = str(region_name or "").lower()
    if role == "start":
        if "eyes" in r_low or "inner ear" in r_low or "retina" in r_low or "cochlea" in r_low:
            return (77, 187, 158)   # #4DBB9E Sensory Teal
        if "offline" in r_low or neural_state == "silenced":
            return (109, 119, 133)  # #6D7785 Slate-Muted
        return (88, 156, 232)       # #589CE8 Partner Steel-Blue
    if neural_state in ("severed", "silenced"):
        return (109, 119, 133)      # #6D7785 Muted Slate target
    return (224, 82, 82)            # #E05252 Clinical Coral primary hub


def resolve_anatomy_callout_windows(
    edl: dict[str, Any] | None,
    visual_plan: dict[str, Any] | None = None,
    *,
    visuals_dir: Path | None = None,
) -> list[dict[str, Any]]:
    """
    Extracts `[start_sec, end_sec]` callout specs for `expressive_xray_brain` & `brain_simulator_3d` cuts (`R71` / `R71-B` / `R76` / `R81`):
      - `r78m_dual`: XL dual-hub hand-lettered fountain-pen banner + live DISOpticalFlow / Blender 3D tracked pointers.
      - `single_region`: single pointer ring + curved fountain-pen leader line + `(Signal Offline)` support on `silenced`.
      - `pathway_relay`: 2-node `[Start Region] ──▶ [End Region]` hand-drawn circuit banner + dual pointer rings.
      - `pathway_severed`: 2-node `[Start Region] ── ✕ ── [End Region]` severed circuit banner + crimson/gold `✕` mark.
    """
    if not isinstance(edl, dict):
        return []
    cuts = edl.get("cuts") if isinstance(edl.get("cuts"), list) else []
    vp_clips = (visual_plan or {}).get("clips") if isinstance((visual_plan or {}).get("clips"), list) else []
    vp_by_num = {
        int(c.get("clip_number") or c.get("clip_index") or idx): c
        for idx, c in enumerate(vp_clips, start=1)
        if isinstance(c, dict)
    }

    callouts: list[dict[str, Any]] = []
    for idx_c, c in enumerate(cuts):
        if not isinstance(c, dict):
            continue
        clip_num = int(c.get("clip_index") or (idx_c + 1))
        vp_c = vp_by_num.get(clip_num, {})
        if (
            c.get("callout_enabled") is False
            or vp_c.get("callout_enabled") is False
            or c.get("anatomy_label") is False
            or vp_c.get("anatomy_label") is False
        ):
            continue
        grammar = str(c.get("grammar") or vp_c.get("grammar") or "").strip()
        render_eng = str(c.get("render_engine") or vp_c.get("render_engine") or "").strip().lower()
        r76_sim = bool(grammar == "brain_simulator_3d" or render_eng == "blender_3d_simulator")
        is_stacked_compare = bool(c.get("stacked_cutaway_brain_compare") or vp_c.get("stacked_cutaway_brain_compare"))
        is_sbs_compare = bool(c.get("side_by_side_brain_compare") or vp_c.get("side_by_side_brain_compare") or is_stacked_compare)
        r78m_spec = c.get("r78m_callout") if isinstance(c.get("r78m_callout"), dict) else vp_c.get("r78m_callout")
        if r78m_spec is None and is_sbs_compare and (grammar in ("expressive_xray_brain", "brain_simulator_3d") or r76_sim):
            s_lbl = str(
                c.get("left_cohort_label")
                or vp_c.get("left_cohort_label")
                or c.get("start_brain_region")
                or vp_c.get("start_brain_region")
                or c.get("brain_region")
                or vp_c.get("brain_region")
                or "Group A Brain"
            ).strip().title()
            e_lbl = str(
                c.get("right_cohort_label")
                or vp_c.get("right_cohort_label")
                or c.get("end_brain_region")
                or vp_c.get("end_brain_region")
                or "Control Brain"
            ).strip().title()
            r78m_spec = {
                "left_lbl": s_lbl,
                "right_lbl": e_lbl,
                "arrow": "vs",
                "sub": str(c.get("callout_gloss") or vp_c.get("callout_gloss") or "Expanded Volume  vs  Baseline").strip(),
                "left_rgb": [255, 86, 104],
                "right_rgb": [88, 178, 246] if is_stacked_compare else [175, 198, 230],
                "left_xy": [420, 580] if is_stacked_compare else [265, 1035],
                "right_xy": [720, 1020] if is_stacked_compare else [815, 1035],
                "lock_seed_xy": True,
            }
        elif isinstance(r78m_spec, dict) and is_sbs_compare:
            r78m_spec = {
                "arrow": "vs",
                "left_xy": [420, 580] if is_stacked_compare else [265, 1035],
                "right_xy": [720, 1020] if is_stacked_compare else [815, 1035],
                **r78m_spec,
            }
        if isinstance(r78m_spec, dict) and r78m_spec.get("enabled", True) is not False and (
            grammar in ("expressive_xray_brain", "brain_simulator_3d") or r76_sim
        ):
            cut_s = float(c.get("out_start_sec") or 0.0)
            cut_e = float(c.get("out_end_sec") or 0.0)
            src_s = float(c.get("src_start_sec") or vp_c.get("src_start_sec") or 0.0)
            t0_r = cut_s + 0.14
            t1_r = cut_e - 0.10
            if t1_r - t0_r >= 0.70:
                spec_mode = str(
                    r78m_spec.get("mode") or c.get("callout_style") or vp_c.get("callout_style") or ""
                ).strip().lower()
                has_right_lbl = bool(str(r78m_spec.get("right_lbl") or "").strip())
                is_r78m_single = (not is_sbs_compare) and (spec_mode == "r78m_single" or not has_right_lbl)
                camera_track = _load_camera_track(c, vp_c, clip_num, visuals_dir) if r76_sim else None
                callouts.append(
                    {
                        "cut_index": int(c.get("cut_index") or (idx_c + 1)),
                        "clip_index": clip_num,
                        "cut_start_sec": round(cut_s, 4),
                        "cut_end_sec": round(cut_e, 4),
                        "src_start_sec": round(src_s, 4),
                        "start_sec": round(t0_r, 3),
                        "end_sec": round(t1_r, 3),
                        "duration_sec": round(t1_r - t0_r, 3),
                        "callout_mode": "r78m_single" if is_r78m_single else "r78m_dual",
                        "camera_track": camera_track,
                        "stacked_cutaway_brain_compare": is_stacked_compare,
                        "track_offset_sec": round(src_s + (t0_r - cut_s), 4),
                        "r78m_callout": dict(r78m_spec),
                    }
                )
            continue
        if grammar not in ("expressive_xray_brain", "brain_simulator_3d") and not r76_sim:
            continue
        cam_move = str(
            c.get("camera_move")
            or vp_c.get("camera_move")
            or c.get("camera_movement")
            or vp_c.get("camera_movement")
            or ""
        ).strip().lower()
        if cam_move == "neural_fpv_pullback_out":
            # Rule R74: Keep high-speed pullback exit completely unobstructed by callout ink
            continue

        start_reg_raw = str(
            c.get("start_brain_region")
            or vp_c.get("start_brain_region")
            or c.get("brain_region")
            or vp_c.get("brain_region")
            or c.get("anatomy_label")
            or ""
        ).strip()
        end_reg_raw = str(c.get("end_brain_region") or vp_c.get("end_brain_region") or "").strip()
        neural_state = str(c.get("neural_state") or vp_c.get("neural_state") or "active").strip().lower()
        if neural_state not in ("active", "silenced", "severed", "rerouted"):
            neural_state = "active"
        explicit_mode = str(c.get("callout_mode") or vp_c.get("callout_mode") or "").strip().lower()
        callout_gloss = str(c.get("callout_gloss") or vp_c.get("callout_gloss") or "").strip()

        use_macro = bool(
            (not r76_sim)
            and (
                cam_move in ("neural_fpv_dive_in", "neural_macro_orbit_hold", "neural_tract_relay_flight")
                or c.get("r74_macro_mode")
                or vp_c.get("r74_macro_mode")
            )
        )
        anc_start = resolve_anatomy_screen_anchor(start_reg_raw, macro_mode=use_macro) if start_reg_raw else None
        anc_end = resolve_anatomy_screen_anchor(end_reg_raw, macro_mode=use_macro) if end_reg_raw else None
        callout_mode = _resolve_cut_callout_mode(cam_move, neural_state, anc_start, anc_end, explicit_mode=explicit_mode)

        anchor = (
            anc_end
            if (callout_mode in ("pathway_relay", "pathway_severed") and anc_end is not None)
            else (anc_end if (cam_move == "neural_tract_relay_flight" and anc_end is not None) else anc_start)
        )
        if not anchor:
            continue

        if (not r76_sim) and callout_mode == "single_region" and cam_move == "neural_fpv_dive_in" and idx_c + 1 < len(cuts):
            nxt = cuts[idx_c + 1] if isinstance(cuts[idx_c + 1], dict) else {}
            nxt_clip_num = int(nxt.get("clip_index") or (idx_c + 2))
            nxt_vp = vp_by_num.get(nxt_clip_num, {})
            nxt_cam = str(
                nxt.get("camera_move")
                or nxt_vp.get("camera_move")
                or nxt.get("camera_movement")
                or nxt_vp.get("camera_movement")
                or ""
            ).strip().lower()
            nxt_reg = str(nxt.get("brain_region") or nxt_vp.get("brain_region") or "").strip()
            nxt_anc = resolve_anatomy_screen_anchor(nxt_reg, macro_mode=True) if nxt_reg else None
            if (
                str(nxt.get("grammar") or "") == "expressive_xray_brain"
                and nxt_cam == "neural_macro_orbit_hold"
                and nxt_anc
                and nxt_anc["canonical"] == anchor["canonical"]
            ):
                # Defer R71 callout to the immediately following steady B1 macro hold cut
                continue

        explicit_entry = c.get("portal_entry_sec") if c.get("portal_entry_sec") is not None else vp_c.get("portal_entry_sec")
        if r76_sim:
            entry_delay = max(0.18, float(explicit_entry if explicit_entry is not None else 0.22))
            tail_pad = 0.12
            min_span = 0.80
        elif callout_mode in ("pathway_relay", "pathway_severed"):
            entry_delay = max(0.24, float(explicit_entry if explicit_entry is not None else 0.28))
            tail_pad = 0.10
            min_span = 0.70
        elif cam_move == "neural_fpv_dive_in":
            entry_delay = max(1.25, float(explicit_entry if explicit_entry is not None else 1.25))
            tail_pad = 0.10
            min_span = 0.65
        elif cam_move == "neural_tract_relay_flight":
            entry_delay = max(0.95, float(explicit_entry if explicit_entry is not None else 0.95))
            tail_pad = 0.12
            min_span = 0.70
        elif use_macro:
            entry_delay = max(0.18, float(explicit_entry if explicit_entry is not None else 0.18))
            tail_pad = 0.12
            min_span = 0.70
        else:
            entry_delay = max(0.18, float(explicit_entry if explicit_entry is not None else 0.18))
            tail_pad = 0.14
            min_span = 1.0
        cut_s = float(c.get("out_start_sec") or 0.0)
        cut_e = float(c.get("out_end_sec") or 0.0)
        src_s = float(c.get("src_start_sec") or vp_c.get("src_start_sec") or 0.0)
        t0 = cut_s + entry_delay
        t1 = cut_e - tail_pad
        if t1 - t0 < min_span:
            continue

        anchor_payload = dict(anchor)
        if r76_sim and anc_end is None:
            anchor_payload["accent_rgb"] = _r76_clinical_accent_rgb(
                "end" if neural_state != "active" else "primary",
                neural_state,
                start_reg_raw,
            )
        if callout_mode == "single_region":
            if callout_gloss:
                anchor_payload["short_role"] = callout_gloss
            elif neural_state == "silenced" and "offline" not in str(anchor_payload.get("short_role") or "").lower():
                base_r = str(anchor_payload.get("short_role") or "").strip()
                anchor_payload["short_role"] = f"{base_r} · Signal Offline" if base_r else "Signal Offline"

        camera_track = _load_camera_track(c, vp_c, clip_num, visuals_dir) if r76_sim else None
        row_out: dict[str, Any] = {
            "cut_index": int(c.get("cut_index") or (idx_c + 1)),
            "clip_index": clip_num,
            "cut_start_sec": round(cut_s, 4),
            "cut_end_sec": round(cut_e, 4),
            "src_start_sec": round(src_s, 4),
            "start_sec": round(t0, 3),
            "end_sec": round(t1, 3),
            "duration_sec": round(t1 - t0, 3),
            "macro_mode": use_macro,
            "r76_clinical_matte": r76_sim,
            "camera_track": camera_track,
            "track_offset_sec": round(src_s + entry_delay, 4),
            "camera_move": cam_move,
            "callout_mode": callout_mode,
            "neural_state": neural_state,
            **anchor_payload,
        }
        if callout_mode in ("pathway_relay", "pathway_severed") and anc_start is not None and anc_end is not None:
            if callout_gloss:
                pathway_sub = callout_gloss
            elif callout_mode == "pathway_severed":
                pathway_sub = f"{anc_end['short_role']} · Link Severed"
            elif neural_state == "rerouted":
                pathway_sub = f"Bypass Shortcut · {anc_end['short_role']} Fires!"
            else:
                pathway_sub = f"{anc_start['short_role']} -> {anc_end['short_role']}"
            start_acc_rgb = _r76_clinical_accent_rgb("start", neural_state, start_reg_raw) if r76_sim else anc_start["accent_rgb"]
            end_acc_rgb = _r76_clinical_accent_rgb("end", neural_state, end_reg_raw) if r76_sim else anc_end["accent_rgb"]
            row_out.update(
                {
                    "start_canonical": anc_start["canonical"],
                    "start_display_title": anc_start["display_title"],
                    "start_short_role": anc_start["short_role"],
                    "start_anchor_xy": anc_start["anchor_xy"],
                    "start_accent_rgb": start_acc_rgb,
                    "end_canonical": anc_end["canonical"],
                    "end_display_title": anc_end["display_title"],
                    "end_short_role": anc_end["short_role"],
                    "end_anchor_xy": anc_end["anchor_xy"],
                    "end_accent_rgb": end_acc_rgb,
                    "pathway_subtitle": pathway_sub,
                }
            )
        callouts.append(row_out)
    return callouts


def _clamp_callout_safe_rgba(
    canvas: Image.Image,
    *,
    safe_x_left: float,
    safe_x_right: float,
    safe_y_top: int,
    safe_y_bot: int,
    width: int,
    height: int,
) -> Image.Image:
    bot_y_end = min(height, int(safe_y_bot) + 1)
    left_x0 = max(0, int(round(safe_x_left)))
    right_x_end = min(width, int(round(safe_x_right)) + 1)
    arr = np.asarray(canvas, dtype=np.uint8)
    if (
        np.any(arr[:safe_y_top, :, 3] > 0)
        or (bot_y_end < height and np.any(arr[bot_y_end:, :, 3] > 0))
        or (left_x0 > 0 and np.any(arr[:, :left_x0, 3] > 0))
        or (right_x_end < width and np.any(arr[:, right_x_end:, 3] > 0))
    ):
        arr = arr.copy()
        arr[:safe_y_top, :, :] = 0
        if bot_y_end < height:
            arr[bot_y_end:, :, :] = 0
        if left_x0 > 0:
            arr[:, :left_x0, :] = 0
        if right_x_end < width:
            arr[:, right_x_end:, :] = 0
        canvas = Image.fromarray(arr, mode="RGBA")
    return canvas


# ==============================================================================
# R81 Hand-Ink XL Typography & Zero-Strikethrough Helpers (Box-Free PatrickHand)
# ==============================================================================
def _split_hub_lines(label: str, force_wrap: bool) -> list[str]:
    """Splits multi-word anatomical hub names into balanced 2-line stacks when 1-line XL wouldn't fit."""
    clean = str(label or "").strip()
    words = clean.split()
    if not force_wrap or len(words) <= 1:
        return [clean]
    if len(words) == 2:
        return [words[0], words[1]]
    best_i = 1
    best_diff = 10**9
    for i in range(1, len(words)):
        l1 = " ".join(words[:i])
        l2 = " ".join(words[i:])
        diff = abs(len(l1) - len(l2))
        if diff < best_diff:
            best_diff = diff
            best_i = i
    return [" ".join(words[:best_i]), " ".join(words[best_i:])]


def _measure_ink_block(
    probe: ImageDraw.ImageDraw,
    lines: list[str],
    font: Any,
    *,
    stroke_px: int = 3,
    line_gap: int = 2,
) -> tuple[int, int]:
    widths: list[int] = []
    total_h = 0
    for idx, line in enumerate(lines):
        b = probe.textbbox((0, 0), line, font=font, stroke_width=stroke_px)
        widths.append(max(0, int(b[2] - b[0])))
        total_h += max(0, int(b[3] - b[1]))
        if idx + 1 < len(lines):
            total_h += int(line_gap)
    return (max(widths) if widths else 0), total_h


def _draw_ink_text_clean(
    canvas: Image.Image,
    xy: tuple[int, int],
    text: str,
    font: Any,
    fill_rgba: tuple[int, int, int, int],
    *,
    stroke_px: int = 3,
    blur_px: float = 3.2,
) -> tuple[int, int, int, int]:
    """
    Draws box-free `PatrickHand` ink text with a crisp dark ink rim + soft halo (for bright gray cortex legibility
    and DQ10 dark-perimeter compliance) onto `canvas` in-place and returns the exact drawn glyph bounding box.
    """
    alpha = int(fill_rgba[3])
    if alpha <= 2 or not text:
        probe = ImageDraw.Draw(canvas)
        return probe.textbbox(xy, text, font=font, stroke_width=stroke_px)

    probe = ImageDraw.Draw(canvas)
    raw_bb = probe.textbbox(xy, text, font=font, stroke_width=stroke_px + 3)
    pad = max(10, int(math.ceil(blur_px * 3.0)) + 4)
    x0 = max(0, int(raw_bb[0]) - pad)
    y0 = max(0, int(raw_bb[1]) - pad)
    x1 = min(canvas.width, int(raw_bb[2]) + pad)
    y1 = min(canvas.height, int(raw_bb[3]) + pad)
    if x1 <= x0 or y1 <= y0:
        return probe.textbbox(xy, text, font=font, stroke_width=stroke_px)

    loc_w, loc_h = x1 - x0, y1 - y0
    loc_xy = (int(xy[0]) - x0, int(xy[1]) - y0)

    sh_al = max(0, min(255, int(round(alpha * 0.88))))
    rim_al = max(0, min(255, int(round(alpha * 0.94))))
    shadow = Image.new("RGBA", (loc_w, loc_h), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.text(
        loc_xy,
        text,
        font=font,
        fill=(4, 7, 13, sh_al),
        stroke_width=stroke_px + 3,
        stroke_fill=(4, 7, 13, sh_al),
    )
    if blur_px > 0.2:
        shadow = shadow.filter(ImageFilter.GaussianBlur(radius=float(blur_px)))

    fg = Image.new("RGBA", (loc_w, loc_h), (0, 0, 0, 0))
    fd = ImageDraw.Draw(fg)
    fd.text(
        loc_xy,
        text,
        font=font,
        fill=fill_rgba,
        stroke_width=stroke_px,
        stroke_fill=(8, 12, 20, rim_al),
    )
    drawn_loc = fd.textbbox(loc_xy, text, font=font, stroke_width=stroke_px)
    patch = Image.alpha_composite(shadow, fg)
    canvas.alpha_composite(patch, dest=(x0, y0))
    return (
        int(drawn_loc[0] + x0),
        int(drawn_loc[1] + y0),
        int(drawn_loc[2] + x0),
        int(drawn_loc[3] + y0),
    )


def _draw_ink_block_centered(
    canvas: Image.Image,
    lines: list[str],
    cx: float,
    top_ink_y: float,
    font: Any,
    fill_rgba: tuple[int, int, int, int],
    *,
    stroke_px: int = 3,
    line_gap: int = 2,
    blur_px: float = 3.2,
) -> tuple[int, int, int, int]:
    """Draws 1- or 2-line centered `PatrickHand` block and returns exact `(min_x, min_y, max_x, max_y)` of drawn glyphs."""
    probe = ImageDraw.Draw(canvas)
    cur_top = int(round(top_ink_y))
    min_x, min_y, max_x, max_y = 10**9, 10**9, -(10**9), -(10**9)
    for line in lines:
        b0 = probe.textbbox((0, 0), line, font=font, stroke_width=stroke_px)
        lw = b0[2] - b0[0]
        draw_x = int(round(cx - 0.5 * lw - b0[0]))
        draw_y = int(round(cur_top - b0[1]))
        db = _draw_ink_text_clean(
            canvas,
            (draw_x, draw_y),
            line,
            font,
            fill_rgba,
            stroke_px=stroke_px,
            blur_px=blur_px,
        )
        min_x = min(min_x, db[0])
        min_y = min(min_y, db[1])
        max_x = max(max_x, db[2])
        max_y = max(max_y, db[3])
        cur_top = int(db[3]) + int(line_gap)
    if min_x > max_x:
        ix, iy = int(round(cx)), int(round(top_ink_y))
        return (ix, iy, ix, iy)
    return (min_x, min_y, max_x, max_y)


def _select_xl_dual_hub_layout(
    probe: ImageDraw.ImageDraw,
    left_lbl: str,
    right_lbl: str,
    conn_w: float,
    usable_w: float,
    *,
    scale_y: float,
    stroke_px: int,
    line_gap: int,
    single_max_px: int = R81_CALLOUT_XL_SINGLE_LINE_MAX_PX,
    single_min_px: int = R81_CALLOUT_XL_SINGLE_LINE_MIN_PX,
    stack_max_px: int = R81_CALLOUT_XL_STACK_MAX_PX,
    stack_min_px: int = R81_CALLOUT_XL_STACK_MIN_PX,
) -> tuple[int, Any, list[str], list[str], int, int, int]:
    """
    R81 XL layout solver:
      1. Prefers single-line XL (`84 -> 72px`) whenever `[Left] + conn_w + [Right]` fits inside `usable_w`.
      2. Otherwise auto-stacks multi-word hubs into 2 centered lines at XL (`82 -> 64px`) instead of shrinking text!
    """
    s_hi = max(24, int(round(single_max_px * scale_y)))
    s_lo = max(20, int(round(single_min_px * scale_y)))
    step = max(1, int(round(2 * scale_y)))
    for sz in range(s_hi, s_lo - 1, -step):
        f_try = _load_hand_font(sz, expressive_accent=False)
        lw, lh = _measure_ink_block(probe, [left_lbl], f_try, stroke_px=stroke_px, line_gap=line_gap)
        rw, rh = _measure_ink_block(probe, [right_lbl], f_try, stroke_px=stroke_px, line_gap=line_gap)
        if lw + conn_w + rw <= usable_w:
            return sz, f_try, [left_lbl], [right_lbl], lw, rw, max(lh, rh)

    k_hi = max(22, int(round(stack_max_px * scale_y)))
    k_lo = max(18, int(round(stack_min_px * scale_y)))
    l_wrap = _split_hub_lines(left_lbl, force_wrap=True)
    r_wrap = _split_hub_lines(right_lbl, force_wrap=True)
    chosen_fallback: tuple[int, Any, list[str], list[str], int, int, int] | None = None
    for sz in range(k_hi, max(16, k_lo - int(round(22 * scale_y))) - 1, -step):
        f_try = _load_hand_font(sz, expressive_accent=False)
        lw, lh = _measure_ink_block(probe, l_wrap, f_try, stroke_px=stroke_px, line_gap=line_gap)
        rw, rh = _measure_ink_block(probe, r_wrap, f_try, stroke_px=stroke_px, line_gap=line_gap)
        chosen_fallback = (sz, f_try, l_wrap, r_wrap, lw, rw, max(lh, rh))
        if lw + conn_w + rw <= usable_w:
            return chosen_fallback
    assert chosen_fallback is not None
    return chosen_fallback


def _select_xl_single_hub_layout(
    probe: ImageDraw.ImageDraw,
    title_lbl: str,
    usable_w: float,
    *,
    scale_y: float,
    stroke_px: int,
    line_gap: int,
    single_max_px: int = R81_CALLOUT_XL_SINGLE_LINE_MAX_PX,
    single_min_px: int = R81_CALLOUT_XL_SINGLE_LINE_MIN_PX,
    stack_max_px: int = R81_CALLOUT_XL_STACK_MAX_PX,
    stack_min_px: int = R81_CALLOUT_XL_STACK_MIN_PX,
) -> tuple[int, Any, list[str], int, int]:
    """Solves single-hub XL `PatrickHand` sizing inside `usable_w`, falling back cleanly to 2-line wrap."""
    s_hi = max(24, int(round(single_max_px * scale_y)))
    s_lo = max(20, int(round(single_min_px * scale_y)))
    step = max(1, int(round(2 * scale_y)))
    for sz in range(s_hi, s_lo - 1, -step):
        f_try = _load_hand_font(sz, expressive_accent=False)
        tw, th = _measure_ink_block(probe, [title_lbl], f_try, stroke_px=stroke_px, line_gap=line_gap)
        if tw <= usable_w:
            return sz, f_try, [title_lbl], tw, th

    k_hi = max(22, int(round(stack_max_px * scale_y)))
    k_lo = max(18, int(round(stack_min_px * scale_y)))
    wrapped = _split_hub_lines(title_lbl, force_wrap=True)
    chosen_fallback: tuple[int, Any, list[str], int, int] | None = None
    for sz in range(k_hi, max(16, k_lo - int(round(22 * scale_y))) - 1, -step):
        f_try = _load_hand_font(sz, expressive_accent=False)
        tw, th = _measure_ink_block(probe, wrapped, f_try, stroke_px=stroke_px, line_gap=line_gap)
        chosen_fallback = (sz, f_try, wrapped, tw, th)
        if tw <= usable_w:
            return chosen_fallback
    assert chosen_fallback is not None
    return chosen_fallback


def _render_pathway_circuit_rgba(
    canvas: Image.Image,
    callout: dict[str, Any],
    t_rel: float,
    master_alpha: float,
    *,
    width: int,
    height: int,
    safe_x_left: float,
    safe_x_right: float,
    safe_y_top: int,
    safe_y_bot: int,
) -> Image.Image:
    """
    Rule R71-B / R81: Renders XL 2-node fountain-pen neural pathway circuit diagrams inside `X = 48..910px`, `Y = 12%..65%`
    with zero strikethrough (`ul_y` strictly below rendered glyph descenders) and clean dark-rim under-strokes.
    """
    scale_x = width / 1080.0
    scale_y = height / 1920.0
    scale = min(scale_x, scale_y)
    stroke_px = max(1, int(round(3 * scale)))
    line_gap = max(1, int(round(2 * scale_y)))

    def _a(val: int) -> int:
        return max(0, min(255, int(round(val * master_alpha))))

    is_severed = str(callout.get("callout_mode") or "") == "pathway_severed" or str(callout.get("neural_state") or "") == "severed"
    start_title = str(callout.get("start_display_title") or callout.get("display_title") or "Source Hub").strip()
    end_title = str(callout.get("end_display_title") or callout.get("display_title") or "Target Hub").strip()
    sub_raw = str(callout.get("pathway_subtitle") or callout.get("short_role") or "").strip()
    sub_disp = sub_raw

    start_acc: tuple[int, int, int] = tuple(int(x) for x in callout.get("start_accent_rgb", (72, 224, 255)))  # type: ignore[assignment]
    end_acc: tuple[int, int, int] = tuple(int(x) for x in callout.get("end_accent_rgb", (255, 198, 74)))  # type: ignore[assignment]
    if is_severed:
        if callout.get("r76_clinical_matte"):
            bridge_rgb = (186, 156, 72)
            fault_rgb = (239, 68, 68)
            end_ring_rgb = (109, 119, 133)
            sub_rgb = (252, 165, 165)
        else:
            bridge_rgb = (212, 175, 55)
            fault_rgb = (245, 64, 72)
            end_ring_rgb = (168, 180, 198)
            sub_rgb = (252, 165, 165)
    elif str(callout.get("neural_state") or "") == "rerouted":
        bridge_rgb = (255, 198, 74)
        fault_rgb = (255, 198, 74)
        end_ring_rgb = end_acc
        sub_rgb = (253, 230, 138)
    else:
        bridge_rgb = start_acc
        fault_rgb = end_acc
        end_ring_rgb = end_acc
        sub_rgb = (236, 242, 252)

    rim_canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    fg_canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    text_canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    probe = ImageDraw.Draw(text_canvas)

    hdr_left = max(safe_x_left + 30.0 * scale_x, 78.0 * scale_x)
    hdr_right = min(safe_x_right - 6.0 * scale_x, 904.0 * scale_x)
    usable_w = max(260.0 * scale_x, hdr_right - hdr_left)
    center_safe_x = 0.5 * (hdr_left + hdr_right)
    conn_w = (132.0 if is_severed else 124.0) * scale_x

    _hdr_sz, f_node, s_lines, e_lines, sw, ew, block_h = _select_xl_dual_hub_layout(
        probe,
        start_title,
        end_title,
        conn_w,
        usable_w,
        scale_y=scale_y,
        stroke_px=stroke_px,
        line_gap=line_gap,
    )

    f_sub = _load_hand_font(max(18, int(round(R81_CALLOUT_XL_SUB_MAX_PX * scale_y))), expressive_accent=False)
    sub_min_px = max(16, int(round((R81_CALLOUT_XL_SUB_MIN_PX - 6) * scale_y)))
    while sub_disp and f_sub.size > sub_min_px:
        sb_try = probe.textbbox((0, 0), sub_disp, font=f_sub, stroke_width=stroke_px)
        if (sb_try[2] - sb_try[0]) <= usable_w:
            break
        f_sub = _load_hand_font(max(sub_min_px, f_sub.size - max(1, int(round(2 * scale_y)))), expressive_accent=False)

    total_row_w = sw + conn_w + ew
    start_x = max(hdr_left, min(hdr_right - total_row_w, center_safe_x - 0.5 * total_row_w))
    l_cx = start_x + 0.5 * sw
    r_cx = start_x + sw + conn_w + 0.5 * ew
    conn_x0 = start_x + sw + 14.0 * scale_x
    conn_x1 = start_x + sw + conn_w - 14.0 * scale_x

    top_ink_y = max(float(safe_y_top) + 16.0 * scale_y, 246.0 * scale_y)
    _, s_h = _measure_ink_block(probe, s_lines, f_node, stroke_px=stroke_px, line_gap=line_gap)
    _, e_h = _measure_ink_block(probe, e_lines, f_node, stroke_px=stroke_px, line_gap=line_gap)
    s_top = top_ink_y + 0.5 * (block_h - s_h)
    e_top = top_ink_y + 0.5 * (block_h - e_h)
    node_mid_y = float(top_ink_y + 0.5 * block_h)

    p_start = _ease_out_cubic(t_rel / 0.24)
    p_bridge = _ease_in_out_cubic((t_rel - 0.14) / 0.34)
    p_end = _ease_out_cubic((t_rel - 0.34) / 0.30)
    cut_seed = int(callout.get("cut_index") or 0)

    s_al = _a(int(round(252 * max(0.0, p_start))))
    e_al = _a(int(round(252 * max(0.0, p_end))))

    sb_drawn = _draw_ink_block_centered(
        text_canvas,
        s_lines,
        l_cx,
        s_top,
        f_node,
        (255, 252, 242, s_al),
        stroke_px=stroke_px,
        line_gap=line_gap,
        blur_px=3.2 * scale_y,
    )
    end_txt_rgba = (218, 226, 238, e_al) if is_severed else (255, 252, 242, e_al)
    eb_drawn = _draw_ink_block_centered(
        text_canvas,
        e_lines,
        r_cx,
        e_top,
        f_node,
        end_txt_rgba,
        stroke_px=stroke_px,
        line_gap=line_gap,
        blur_px=3.2 * scale_y,
    )

    ul_gap = float(R81_CALLOUT_UNDERLINE_GAP_PX * scale_y)
    ul_y_s = float(sb_drawn[3]) + ul_gap
    ul_y_e = float(eb_drawn[3]) + ul_gap
    ul_y_max = max(ul_y_s, ul_y_e)

    if p_start > 0.02:
        _draw_r78m_pen_curve(
            fg_canvas,
            (float(sb_drawn[0]), ul_y_s),
            (0.5 * float(sb_drawn[0] + sb_drawn[2]), ul_y_s + 1.5 * scale_y),
            (float(sb_drawn[2]), ul_y_s),
            start_acc,
            alpha=s_al,
            base_width=5.8 * scale,
            progress=p_start,
            seed=711 + cut_seed,
            rim_canvas=rim_canvas,
        )
    if p_end > 0.02:
        _draw_r78m_pen_curve(
            fg_canvas,
            (float(eb_drawn[0]), ul_y_e),
            (0.5 * float(eb_drawn[0] + eb_drawn[2]), ul_y_e + 1.5 * scale_y),
            (float(eb_drawn[2]), ul_y_e),
            end_ring_rgb,
            alpha=e_al,
            base_width=5.8 * scale,
            progress=p_end,
            seed=721 + cut_seed,
            rim_canvas=rim_canvas,
        )

    sub_bot_y = ul_y_max
    if sub_disp:
        sb0 = probe.textbbox((0, 0), sub_disp, font=f_sub, stroke_width=stroke_px)
        sub_w = sb0[2] - sb0[0]
        sub_cx = start_x + 0.5 * total_row_w
        sub_x = int(round(max(hdr_left, min(hdr_right - sub_w, sub_cx - 0.5 * sub_w)) - sb0[0]))
        sub_y = int(round(ul_y_max + 13.0 * scale_y - sb0[1]))
        sub_drawn = _draw_ink_text_clean(
            text_canvas,
            (sub_x, sub_y),
            sub_disp,
            f_sub,
            (*sub_rgb, e_al),
            stroke_px=stroke_px,
            blur_px=3.0 * scale_y,
        )
        sub_bot_y = float(sub_drawn[3])

    leader_top_y = float(sub_bot_y + 13.0 * scale_y)

    track = callout.get("camera_track")
    t_in_clip = t_rel + float(callout.get("track_offset_sec") or 0.0)
    live_start = _interpolate_track_xy(track, "start", t_in_clip, width, height)
    live_end = _interpolate_track_xy(track, "end", t_in_clip, width, height)
    if live_start is not None and live_end is not None:
        ax1, ay1 = live_start
        ax2, ay2 = live_end
    else:
        s_ax_f, s_ay_f = callout.get("start_anchor_xy") or (0.31, 0.49)
        e_ax_f, e_ay_f = callout.get("end_anchor_xy") or callout.get("anchor_xy") or (0.63, 0.49)
        ax1, ay1 = float(s_ax_f * width), float(s_ay_f * height)
        ax2, ay2 = float(e_ax_f * width), float(e_ay_f * height)
        if abs(ax2 - ax1) < 0.16 * width:
            ax1 = 0.30 * width
            ax2 = 0.63 * width
        elif ax1 > ax2:
            ax1, ax2 = ax2, ax1

    ring_r = 23.0 * scale
    ring_mx = 34.0 * scale_x
    ring_my = 34.0 * scale_y
    min_ring_y = max(float(safe_y_top) + ring_my, leader_top_y + 34.0 * scale_y)
    max_ring_y = max(min_ring_y, float(safe_y_bot) - ring_my)
    ax1 = max(safe_x_left + ring_mx, min(safe_x_right - ring_mx, ax1))
    ax2 = max(safe_x_left + ring_mx, min(safe_x_right - ring_mx, ax2))
    ay1 = max(min_ring_y, min(max_ring_y, ay1))
    ay2 = max(min_ring_y, min(max_ring_y, ay2))

    if p_start > 0.02:
        _draw_r78m_target_ring(
            fg_canvas,
            ax1,
            ay1,
            start_acc,
            radius=ring_r,
            alpha=_a(244),
            progress=p_start,
            seed=311 + cut_seed,
            scale=scale,
            rim_canvas=rim_canvas,
        )
        l_ctrl_x = max(safe_x_left + 14.0 * scale_x, min(l_cx, ax1) - 20.0 * scale_x)
        _draw_r78m_pen_curve(
            fg_canvas,
            (l_cx, min(float(safe_y_bot) - 18.0 * scale_y, leader_top_y)),
            (l_ctrl_x, 0.50 * (leader_top_y + ay1)),
            (ax1, max(leader_top_y + 12.0 * scale_y, ay1 - ring_r - 2.0 * scale_y)),
            start_acc,
            alpha=_a(236),
            base_width=4.8 * scale,
            progress=p_start,
            seed=511 + cut_seed,
            rim_canvas=rim_canvas,
        )

    if p_bridge > 0.02 and conn_x1 > conn_x0 + 8.0 * scale_x:
        b_al = _a(248)
        mid_cx = 0.5 * (conn_x0 + conn_x1)
        if is_severed:
            gap_px = 18.0 * scale_x
            _draw_r78m_pen_curve(
                fg_canvas,
                (conn_x0, node_mid_y),
                (0.5 * (conn_x0 + mid_cx - gap_px), node_mid_y - 1.5 * scale_y),
                (mid_cx - gap_px, node_mid_y),
                start_acc,
                alpha=b_al,
                base_width=5.4 * scale,
                progress=min(1.0, p_bridge * 1.6),
                seed=801 + cut_seed,
                rim_canvas=rim_canvas,
            )
            if p_bridge > 0.45:
                p_x = min(1.0, (p_bridge - 0.45) / 0.55)
                _draw_r78m_pen_curve(
                    fg_canvas,
                    (mid_cx + gap_px, node_mid_y),
                    (0.5 * (mid_cx + gap_px + conn_x1), node_mid_y + 1.5 * scale_y),
                    (conn_x1, node_mid_y),
                    end_ring_rgb,
                    alpha=_a(216),
                    base_width=5.0 * scale,
                    progress=p_x,
                    seed=802 + cut_seed,
                    rim_canvas=rim_canvas,
                )
                _draw_r78m_x_mark(
                    fg_canvas,
                    mid_cx,
                    node_mid_y,
                    fault_rgb,
                    arm=15.0 * scale,
                    alpha=_a(252),
                    progress=p_x,
                    seed=803 + cut_seed,
                    scale=scale,
                    rim_canvas=rim_canvas,
                )
        else:
            _draw_r78m_pen_curve(
                fg_canvas,
                (conn_x0, node_mid_y),
                (mid_cx, node_mid_y - 2.5 * scale_y),
                (conn_x1 - 4.0 * scale_x, node_mid_y),
                bridge_rgb,
                alpha=b_al,
                base_width=5.6 * scale,
                progress=p_bridge,
                seed=811 + cut_seed,
                rim_canvas=rim_canvas,
            )
            if p_bridge > 0.55:
                ah = 15.0 * scale
                _draw_r78m_pen_curve(
                    fg_canvas,
                    (conn_x1 - ah * 1.2, node_mid_y - ah * 0.8),
                    (conn_x1 - 5.0 * scale_x, node_mid_y - 2.5 * scale_y),
                    (conn_x1, node_mid_y),
                    bridge_rgb,
                    alpha=b_al,
                    base_width=5.2 * scale,
                    seed=812 + cut_seed,
                    rim_canvas=rim_canvas,
                )
                _draw_r78m_pen_curve(
                    fg_canvas,
                    (conn_x1 - ah * 1.2, node_mid_y + ah * 0.8),
                    (conn_x1 - 5.0 * scale_x, node_mid_y + 2.5 * scale_y),
                    (conn_x1, node_mid_y),
                    bridge_rgb,
                    alpha=b_al,
                    base_width=5.2 * scale,
                    seed=813 + cut_seed,
                    rim_canvas=rim_canvas,
                )

    if p_end > 0.02:
        _draw_r78m_target_ring(
            fg_canvas,
            ax2,
            ay2,
            end_ring_rgb,
            radius=ring_r,
            alpha=_a(240),
            progress=p_end,
            seed=321 + cut_seed,
            scale=scale,
            rim_canvas=rim_canvas,
        )
        r_ctrl_x = min(safe_x_right - 14.0 * scale_x, max(r_cx, ax2) + 20.0 * scale_x)
        _draw_r78m_pen_curve(
            fg_canvas,
            (r_cx, min(float(safe_y_bot) - 18.0 * scale_y, leader_top_y)),
            (r_ctrl_x, 0.50 * (leader_top_y + ay2)),
            (ax2, max(leader_top_y + 12.0 * scale_y, ay2 - ring_r - 2.0 * scale_y)),
            end_ring_rgb,
            alpha=_a(232),
            base_width=4.8 * scale,
            progress=p_end,
            seed=521 + cut_seed,
            rim_canvas=rim_canvas,
        )

    strokes = Image.alpha_composite(rim_canvas, fg_canvas)
    out_canvas = Image.alpha_composite(canvas, strokes)
    out_canvas = Image.alpha_composite(out_canvas, text_canvas)
    return _clamp_callout_safe_rgba(
        out_canvas,
        safe_x_left=safe_x_left,
        safe_x_right=safe_x_right,
        safe_y_top=safe_y_top,
        safe_y_bot=safe_y_bot,
        width=width,
        height=height,
    )


def _draw_r78m_pen_curve(
    canvas: Image.Image,
    p0: tuple[float, float],
    ctrl: tuple[float, float],
    p1: tuple[float, float],
    rgb: tuple[int, int, int],
    *,
    alpha: int,
    base_width: float,
    progress: float = 1.0,
    seed: int = 101,
    rim_canvas: Image.Image | None = None,
) -> None:
    if alpha <= 2 or progress <= 0.01:
        return
    ts = np.linspace(0.0, 1.0, 48, dtype=np.float32)
    om = 1.0 - ts
    xs = (om * om) * float(p0[0]) + 2.0 * om * ts * float(ctrl[0]) + (ts * ts) * float(p1[0])
    ys = (om * om) * float(p0[1]) + 2.0 * om * ts * float(ctrl[1]) + (ts * ts) * float(p1[1])
    pts = np.column_stack([xs, ys]).astype(np.float32)
    taper = 0.76 + 0.28 * np.sin(np.pi * ts)
    ws = (float(base_width) * taper).astype(np.float32)
    if rim_canvas is not None:
        rim_ws = ((float(base_width) + 3.6) * taper).astype(np.float32)
        rim_al = max(0, min(255, int(round(alpha * 0.82))))
        draw_tapered_hand_stroke(rim_canvas, pts, rim_ws, (8, 12, 20), alpha=rim_al, progress=progress, style="ink_pen", seed=seed)
    draw_tapered_hand_stroke(canvas, pts, ws, rgb, alpha=alpha, progress=progress, style="ink_pen", seed=seed)


def _draw_r78m_target_ring(
    canvas: Image.Image,
    cx: float,
    cy: float,
    rgb: tuple[int, int, int],
    *,
    radius: float,
    alpha: int,
    progress: float,
    seed: int,
    scale: float,
    rim_canvas: Image.Image | None = None,
) -> None:
    """Renders a natural round hand-drawn fountain-pen target ring (free of 3-lobe triangle distortion)."""
    if alpha <= 2 or progress <= 0.02:
        return
    theta = np.linspace(-0.5 * math.pi, (-0.5 + 2.06 * progress) * math.pi, 44, dtype=np.float32)
    rr = float(radius) * (1.0 + 0.022 * np.sin(2.0 * theta + float(seed % 17)))
    pts = np.column_stack([cx + rr * np.cos(theta), cy + rr * np.sin(theta)]).astype(np.float32)
    taper = 0.72 + 0.32 * np.sin(np.pi * np.linspace(0.0, 1.0, len(theta), dtype=np.float32))
    ws = (5.0 * scale * taper).astype(np.float32)
    if rim_canvas is not None:
        rim_ws = ((5.0 * scale + 3.4 * scale) * taper).astype(np.float32)
        rim_al = max(0, min(255, int(round(alpha * 0.82))))
        draw_tapered_hand_stroke(rim_canvas, pts, rim_ws, (8, 12, 20), alpha=rim_al, progress=1.0, style="ink_pen", seed=seed)
    draw_tapered_hand_stroke(canvas, pts, ws, rgb, alpha=alpha, progress=1.0, style="ink_pen", seed=seed)


def _draw_r78m_x_mark(
    canvas: Image.Image,
    cx: float,
    cy: float,
    rgb: tuple[int, int, int],
    *,
    arm: float,
    alpha: int,
    progress: float,
    seed: int,
    scale: float,
    rim_canvas: Image.Image | None = None,
) -> None:
    if alpha <= 2 or progress <= 0.02:
        return
    for seg_i, (dx0, dy0, dx1, dy1) in enumerate(((-arm, -arm, arm, arm), (arm, -arm, -arm, arm))):
        p0 = (cx + dx0, cy + dy0)
        p1 = (cx + dx1, cy + dy1)
        ctrl = (cx + (0.0 if seg_i == 0 else 2.0 * scale), cy + (-2.0 * scale if seg_i == 0 else 2.0 * scale))
        _draw_r78m_pen_curve(
            canvas,
            p0,
            ctrl,
            p1,
            rgb,
            alpha=alpha,
            base_width=6.0 * scale,
            progress=min(1.0, progress * 1.4),
            seed=seed + seg_i * 7,
            rim_canvas=rim_canvas,
        )


# ==============================================================================
# R81 Zero-Lag 1.0x DISOpticalFlow + Hue-Emission Peak Lock + View-Flip Guard
# ==============================================================================
def _compute_brain_foreground_mask(frame_bgr: np.ndarray) -> np.ndarray:
    """Computes cortical silhouette mask so pointer rings never float in empty black void outside the brain."""
    import cv2

    gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (15, 15), 0)
    mask = (blur > 22).astype(np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((21, 21), np.uint8))
    return mask


def _pull_inside_brain_silhouette(
    pt_xy: tuple[float, float],
    brain_mask: np.ndarray,
    *,
    scale_x: float,
    scale_y: float,
) -> tuple[float, float]:
    """Pulls an out-of-silhouette coordinate smoothly into the nearest cortical interior."""
    h, w = brain_mask.shape[:2]
    y0, y1 = int(round(390 * scale_y)), min(h, int(round(R81_TRACKING_MAX_Y_PX * scale_y)))
    x0, x1 = int(round(78 * scale_x)), min(w, int(round(904 * scale_x)))
    sub = brain_mask[y0:y1, x0:x1]
    ys, xs = np.where(sub > 0)
    if len(xs) < 200:
        return pt_xy

    px = max(float(x0), min(float(x1 - 1), float(pt_xy[0])))
    py = max(float(y0), min(float(y1 - 1), float(pt_xy[1])))
    pad_r = max(4, int(round(18 * min(scale_x, scale_y))))
    ix, iy = int(round(px)), int(round(py))
    patch = brain_mask[max(0, iy - pad_r) : min(h, iy + pad_r + 1), max(0, ix - pad_r) : min(w, ix + pad_r + 1)]
    if patch.size > 0 and float(np.mean(patch > 0)) >= 0.70:
        return (px, py)

    cx = float(x0) + float(np.mean(xs))
    cy = float(y0) + float(np.mean(ys))
    for alpha in np.linspace(0.08, 1.0, 24):
        qx = (1.0 - alpha) * px + alpha * cx
        qy = (1.0 - alpha) * py + alpha * cy
        qix, qiy = int(round(qx)), int(round(qy))
        qpatch = brain_mask[max(0, qiy - pad_r) : min(h, qiy + pad_r + 1), max(0, qix - pad_r) : min(w, qix + pad_r + 1)]
        if qpatch.size > 0 and float(np.mean(qpatch > 0)) >= 0.78:
            return (float(qx), float(qy))
    return (px, py)


def _find_local_hue_emission_peak(
    frame_bgr: np.ndarray,
    seed_xy: tuple[float, float],
    target_rgb: tuple[int, int, int] | None,
    *,
    radius_px: int,
    scale_x: float,
    scale_y: float,
) -> tuple[tuple[float, float], float]:
    """
    Detects glowing crimson/coral, gold/amber, or electric-cyan anatomical emission centroid near `seed_xy`.
    Muted slate markers (`#AFC6E6` for OFF/silenced cortex) return `(seed_xy, 0.0)` so matte cortex tracks purely by optical flow.
    """
    import cv2

    if target_rgb is None:
        return seed_xy, 0.0
    tr, tg, tb = float(target_rgb[0]), float(target_rgb[1]), float(target_rgb[2])
    chroma = max(tr, tg, tb) - min(tr, tg, tb)
    if chroma < 68.0:
        return seed_xy, 0.0

    h, w = frame_bgr.shape[:2]
    sx, sy = int(round(seed_xy[0])), int(round(seed_xy[1]))
    rad = max(24, int(round(radius_px * min(scale_x, scale_y))))
    x0 = max(int(round(78 * scale_x)), sx - rad)
    x1 = min(w - int(round(78 * scale_x)), sx + rad)
    y0 = max(int(round(R81_TRACKING_MIN_Y_PX * scale_y)), sy - rad)
    y1 = min(min(h - 20, int(round(R81_TRACKING_MAX_Y_PX * scale_y))), sy + rad)
    if x1 - x0 < 16 or y1 - y0 < 16:
        return seed_xy, 0.0

    patch = frame_bgr[y0:y1, x0:x1].astype(np.float32)
    b, g, r = patch[:, :, 0], patch[:, :, 1], patch[:, :, 2]
    if tr > tg + 50.0 and tr > tb + 40.0:
        # Crimson / coral active hub
        score = np.maximum(0.0, r - 0.55 * g - 0.35 * b) * (r / 255.0)
    elif tr > 195.0 and tg > 145.0 and tb < 145.0:
        # Warm gold / amber hub (hippocampus / fusiform / tract)
        score = np.maximum(0.0, 0.55 * r + 0.45 * g - 0.68 * b) * ((r + g) / 510.0)
    elif tb > tr + 40.0 and tg > tr + 28.0:
        # Electric cyan pathway / cortical hub
        score = np.maximum(0.0, 0.50 * b + 0.50 * g - 0.65 * r) * ((b + g) / 510.0)
    else:
        return seed_xy, 0.0

    k_sz = max(5, int(round(19 * min(scale_x, scale_y))) | 1)
    score = cv2.GaussianBlur(score, (k_sz, k_sz), 0)
    # Mild Gaussian spatial prior centered on seed_xy so distant unrelated regions don't hijack
    yy, xx = np.mgrid[y0:y1, x0:x1]
    dist2 = ((xx - seed_xy[0]) ** 2 + (yy - seed_xy[1]) ** 2) / max(1.0, float((0.85 * rad) ** 2))
    weighted = score * np.exp(-0.35 * dist2)
    peak_val = float(weighted.max())
    if peak_val < 14.0:
        return seed_xy, peak_val

    mask = weighted >= (0.74 * peak_val)
    mys, mxs = np.where(mask)
    wts = weighted[mask]
    w_sum = float(np.sum(wts))
    if w_sum <= 1e-6:
        return seed_xy, 0.0
    cx = float(x0) + float(np.sum(mxs * wts) / w_sum)
    cy = float(y0) + float(np.sum(mys * wts) / w_sum)
    return (cx, cy), peak_val


def _zero_phase_smooth_1d(vals: np.ndarray, sigma: float = R81_TRACKING_SMOOTH_SIGMA_FRAMES) -> np.ndarray:
    """Symmetric zero-lag Gaussian filter with reflective boundary padding (`0.0` frame phase delay)."""
    n = len(vals)
    if n <= 3 or sigma <= 0.2:
        return vals.copy()
    rad = min(n - 1, max(1, int(math.ceil(3.0 * sigma))))
    kx = np.arange(-rad, rad + 1, dtype=np.float64)
    kern = np.exp(-0.5 * (kx / float(sigma)) ** 2)
    kern /= np.sum(kern)
    padded = np.pad(vals.astype(np.float64), pad_width=rad, mode="reflect")
    return np.convolve(padded, kern, mode="valid")


def _parse_callout_xy_pair(
    raw_val: Any,
    *,
    ref_w: float = 1080.0,
    ref_h: float = 1920.0,
) -> tuple[float, float] | None:
    """Parses normalized `[0..1]` or `1080x1920` pixel `(x, y)` pair from `r78m_callout`."""
    if not isinstance(raw_val, (list, tuple)) or len(raw_val) < 2:
        return None
    try:
        vx, vy = float(raw_val[0]), float(raw_val[1])
    except (TypeError, ValueError):
        return None
    if 0.0 < vx <= 1.05 and 0.0 < vy <= 1.05:
        return (vx * ref_w, vy * ref_h)
    return (vx, vy)


def _auto_seed_r85_functional_targets(
    bgr: np.ndarray,
    *,
    is_stacked_vstack: bool = False,
) -> tuple[tuple[float, float], tuple[float, float]] | None:
    """
    Full-frame Ep #31 functional pigment centroid finder (amber/gold, crimson, slate) in `1080x1920` reference space.
    Protects episodes without manual `left_target_xy` / `right_target_xy` from landing on white cortex.
    """
    import cv2

    h, w = bgr.shape[:2]
    if h < 64 or w < 64:
        return None
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    mask_fg = _compute_brain_foreground_mask(bgr) > 0
    # Warm amber/gold (H in 10..30, S >= 70, V >= 95) or crimson/coral (H <= 9 or >= 168, S >= 75, V >= 90)
    amber = mask_fg & (((hsv[:, :, 0] >= 10) & (hsv[:, :, 0] <= 32) & (hsv[:, :, 1] >= 68) & (hsv[:, :, 2] >= 90)) | (((hsv[:, :, 0] <= 9) | (hsv[:, :, 0] >= 168)) & (hsv[:, :, 1] >= 75) & (hsv[:, :, 2] >= 85)))
    if is_stacked_vstack:
        mid_y = h // 2
        top_amber = amber.copy()
        top_amber[mid_y:, :] = False
        bot_fg = mask_fg.copy()
        bot_fg[:mid_y, :] = False
        # Bottom brain muted slate zone or geometric center
        bot_slate = bot_fg & (hsv[:, :, 1] <= 55) & (hsv[:, :, 2] >= 55) & (hsv[:, :, 2] <= 145)
        ty, tx = np.where(top_amber if np.count_nonzero(top_amber) >= 80 else (mask_fg & (np.arange(h)[:, None] < mid_y)))
        by, bx = np.where(bot_slate if np.count_nonzero(bot_slate) >= 80 else bot_fg)
        if ty.size > 0 and by.size > 0:
            bot_y_clamped = float(np.clip(float(np.median(by)), 0.58 * h, 0.63 * h))
            return (
                (float(np.median(tx)) * 1080.0 / w, float(np.median(ty)) * 1920.0 / h),
                (float(np.median(bx)) * 1080.0 / w, bot_y_clamped * 1920.0 / h),
            )
    if np.count_nonzero(amber) >= 120:
        ys, xs = np.where(amber)
        q25_x, q75_x = float(np.percentile(xs, 28)), float(np.percentile(xs, 72))
        l_mask = xs <= max(q25_x + 8.0, 0.5 * (q25_x + q75_x))
        r_mask = xs >= min(q75_x - 8.0, 0.5 * (q25_x + q75_x))
        if np.any(l_mask) and np.any(r_mask):
            return (
                (float(np.median(xs[l_mask])) * 1080.0 / w, float(np.median(ys[l_mask])) * 1920.0 / h),
                (float(np.median(xs[r_mask])) * 1080.0 / w, float(np.median(ys[r_mask])) * 1920.0 / h),
            )
    return None


def _track_r78m_callout_points_on_video(
    video_in: Path,
    cut_start_sec: float,
    t0: float,
    t1: float,
    fps: int,
    left_xy: tuple[float, float],
    right_xy: tuple[float, float],
    n_frames: int,
    *,
    width: int,
    height: int,
    left_rgb: tuple[int, int, int] | None = None,
    right_rgb: tuple[int, int, int] | None = None,
    lock_seed_xy: bool = False,
    preserve_order: bool = False,
    is_stacked_vstack: bool = False,
    auto_seed_when_default: bool = False,
    single_point: bool = False,
    return_meta: bool = False,
) -> Any:
    """
    Rule R81 Zero-Drift Tracker:
      1. Snaps initial frame-0 anchors inside the cortical silhouette + local hue-emission peak (or honors explicit target coords).
      2. Integrates `1.0x` real-speed `cv2.DISOpticalFlow` across `y in [395..1350px]` (`1620px` on `stacked_vstack`).
      3. Applies zero-phase bidirectional Gaussian smoothing (`0.0` frame lag).
      4. Detects `90°` out-of-plane Google Flow head spins (`flip_rel_sec`) so leader lines fade gracefully before tangling.
    """
    import cv2

    scale_x = width / 1080.0
    scale_y = height / 1920.0
    lx0 = float(left_xy[0]) * scale_x
    ly0 = float(left_xy[1]) * scale_y
    rx0 = float(right_xy[0]) * scale_x
    ry0 = float(right_xy[1]) * scale_y
    keep_exact_pair_order = bool(lock_seed_xy or preserve_order or is_stacked_vstack or single_point)
    if not keep_exact_pair_order and lx0 > rx0:
        lx0, rx0 = rx0, lx0
        ly0, ry0 = ry0, ly0

    x_lo, x_hi = 84.0 * scale_x, 896.0 * scale_x
    max_track_y = (0.63 * 1920.0) if is_stacked_vstack else float(R81_TRACKING_MAX_Y_PX)
    y_lo = (0.14 * height) if is_stacked_vstack else (float(R81_TRACKING_MIN_Y_PX) * scale_y)
    y_hi = max_track_y * scale_y
    min_sep = 34.0 * scale_x

    def _clamp_pair(lx: float, ly: float, rx: float, ry: float) -> tuple[tuple[float, float], tuple[float, float]]:
        lx_c = max(x_lo, min(x_hi, lx))
        rx_c = max(x_lo, min(x_hi, rx))
        ly_c = max(y_lo, min(0.46 * height if is_stacked_vstack else y_hi, ly))
        ry_c = max(0.58 * height if is_stacked_vstack else y_lo, min(y_hi, ry))
        if not keep_exact_pair_order and lx_c + min_sep > rx_c:
            mid = 0.5 * (lx_c + rx_c)
            lx_c = max(x_lo, min(x_hi - min_sep, mid - 0.5 * min_sep))
            rx_c = min(x_hi, max(x_lo + min_sep, lx_c + min_sep))
        return ((round(lx_c, 2), round(ly_c, 2)), (round(rx_c, 2), round(ry_c, 2)))

    base_pair = _clamp_pair(lx0, ly0, rx0, ry0)
    fallback = [base_pair for _ in range(n_frames)]
    meta_out: dict[str, Any] = {"flip_rel_sec": None}
    if not video_in.is_file():
        return (fallback, meta_out) if return_meta else fallback

    cap = cv2.VideoCapture(str(video_in))
    if not cap.isOpened():
        return (fallback, meta_out) if return_meta else fallback

    try:
        vid_fps = float(cap.get(cv2.CAP_PROP_FPS) or fps or 30.0)
        total_f = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        # Anchor frame-0 at callout start `t0` (or `cut_start_sec + 0.14s`) so hard-cut boundaries never pollute flow!
        anchor_sec = max(float(cut_start_sec) + 0.04, float(t0))
        start_f = max(0, min(max(0, total_f - 1), int(round(anchor_sec * vid_fps))))
        cap.set(cv2.CAP_PROP_POS_FRAMES, start_f)
        ok, prev_bgr = cap.read()
        if not ok or prev_bgr is None:
            return (fallback, meta_out) if return_meta else fallback
        if prev_bgr.shape[1] != width or prev_bgr.shape[0] != height:
            prev_bgr = cv2.resize(prev_bgr, (width, height), interpolation=cv2.INTER_LINEAR)

        # Step 1: Cortical silhouette containment + gentle frame-0 hue-emission snap (or explicit target lock)
        if auto_seed_when_default:
            auto_pts = _auto_seed_r85_functional_targets(prev_bgr, is_stacked_vstack=is_stacked_vstack)
            if auto_pts is not None:
                lx0 = float(auto_pts[0][0]) * scale_x
                ly0 = float(auto_pts[0][1]) * scale_y
                rx0 = float(auto_pts[1][0]) * scale_x
                ry0 = float(auto_pts[1][1]) * scale_y
                keep_exact_pair_order = True
        if keep_exact_pair_order:
            lx_s, ly_s = lx0, ly0
            rx_s, ry_s = rx0, ry0
        else:
            mask0 = _compute_brain_foreground_mask(prev_bgr)
            lx_s, ly_s = _pull_inside_brain_silhouette((lx0, ly0), mask0, scale_x=scale_x, scale_y=scale_y)
            rx_s, ry_s = _pull_inside_brain_silhouette((rx0, ry0), mask0, scale_x=scale_x, scale_y=scale_y)
            if not lock_seed_xy:
                l_peak0, l_sc0 = _find_local_hue_emission_peak(
                    prev_bgr, (lx_s, ly_s), left_rgb, radius_px=78, scale_x=scale_x, scale_y=scale_y
                )
                r_peak0, r_sc0 = _find_local_hue_emission_peak(
                    prev_bgr, (rx_s, ry_s), right_rgb, radius_px=78, scale_x=scale_x, scale_y=scale_y
                )
                if l_sc0 >= 24.0:
                    lx_s = 0.65 * lx_s + 0.35 * l_peak0[0]
                    ly_s = 0.65 * ly_s + 0.35 * l_peak0[1]
                if r_sc0 >= 24.0:
                    rx_s = 0.65 * rx_s + 0.35 * r_peak0[0]
                    ry_s = 0.65 * ry_s + 0.35 * r_peak0[1]
        (lx_s, ly_s), (rx_s, ry_s) = _clamp_pair(lx_s, ly_s, rx_s, ry_s)
        if single_point:
            rx_s, ry_s = lx_s, ly_s
        raw_init_dx = float(rx_s - lx_s)
        init_span_x = max(60.0 * scale_x, raw_init_dx)

        # Half-resolution dense DISOpticalFlow (`540x960`) for fast, drift-free 1.0x surface tracking
        hw = max(120, width // 2)
        hh = max(200, height // 2)
        sx_h = float(hw) / float(width)
        sy_h = float(hh) / float(height)
        prev_g_full = cv2.cvtColor(prev_bgr, cv2.COLOR_BGR2GRAY)
        prev_g = cv2.resize(prev_g_full, (hw, hh), interpolation=cv2.INTER_AREA)
        roi_y0, roi_y1 = int(round(0.24 * hh)), int(round(0.68 * hh))
        roi_x0, roi_x1 = int(round(0.10 * hw)), int(round(0.90 * hw))
        ref_roi = prev_g[roi_y0:roi_y1, roi_x0:roi_x1].astype(np.float32)
        ref_roi -= float(np.mean(ref_roi))
        ref_norm = float(np.linalg.norm(ref_roi)) + 1e-6

        dis = cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_MEDIUM)
        l_pos = np.array([lx_s, ly_s], dtype=np.float64)
        r_pos = np.array([rx_s, ry_s], dtype=np.float64)
        track_by_time: list[tuple[float, tuple[float, float], tuple[float, float]]] = [
            (float(start_f) / vid_fps, (float(l_pos[0]), float(l_pos[1])), (float(r_pos[0]), float(r_pos[1])))
        ]

        end_f = min(max(start_f + 1, int(math.ceil((t1 + 0.06) * vid_fps))), max(start_f + 1, total_f - 1))
        patch_r = max(4, int(round(7 * min(scale_x, scale_y))))
        max_step_px = 46.0 * min(scale_x, scale_y)
        flip_detected_t: float | None = None

        f_cur = start_f
        while f_cur < end_f:
            ok_n, nxt_bgr = cap.read()
            if not ok_n or nxt_bgr is None:
                break
            f_cur += 1
            t_cur = float(f_cur) / vid_fps
            if nxt_bgr.shape[1] != width or nxt_bgr.shape[0] != height:
                nxt_bgr = cv2.resize(nxt_bgr, (width, height), interpolation=cv2.INTER_LINEAR)
            nxt_g_full = cv2.cvtColor(nxt_bgr, cv2.COLOR_BGR2GRAY)
            nxt_g = cv2.resize(nxt_g_full, (hw, hh), interpolation=cv2.INTER_AREA)

            flow_fwd = dis.calc(prev_g, nxt_g, None)
            flow_bwd = dis.calc(nxt_g, prev_g, None)

            cur_roi = nxt_g[roi_y0:roi_y1, roi_x0:roi_x1].astype(np.float32)
            cur_roi -= float(np.mean(cur_roi))
            corr0 = float(np.sum(ref_roi * cur_roi) / (ref_norm * (float(np.linalg.norm(cur_roi)) + 1e-6)))

            fb_errs: list[float] = []
            track_pairs = ((l_pos, left_rgb),) if single_point else ((l_pos, left_rgb), (r_pos, right_rgb))
            for pos_ref, rgb_ref in track_pairs:
                hx = int(round(pos_ref[0] * sx_h))
                hy = int(round(pos_ref[1] * sy_h))
                px0 = max(0, hx - patch_r)
                px1 = min(hw, hx + patch_r + 1)
                py0 = max(0, hy - patch_r)
                py1 = min(hh, hy + patch_r + 1)
                sub_flow = flow_fwd[py0:py1, px0:px1]
                if sub_flow.size >= 2:
                    med_hx = float(np.median(sub_flow[:, :, 0]))
                    med_hy = float(np.median(sub_flow[:, :, 1]))
                    qx = max(0, min(hw - 1, int(round(hx + med_hx))))
                    qy = max(0, min(hh - 1, int(round(hy + med_hy))))
                    bwd_v = flow_bwd[qy, qx]
                    fb_e = math.hypot(med_hx + float(bwd_v[0]), med_hy + float(bwd_v[1])) / max(sx_h, 1e-6)
                    fb_errs.append(fb_e)
                    dx_full = med_hx / max(sx_h, 1e-6)
                    dy_full = med_hy / max(sy_h, 1e-6)
                    step_mag = math.hypot(dx_full, dy_full)
                    if step_mag > max_step_px:
                        scale_step = max_step_px / step_mag
                        dx_full *= scale_step
                        dy_full *= scale_step
                    if fb_e <= 22.0:
                        pos_ref[0] += dx_full
                        pos_ref[1] += dy_full

                # Soft hue-emission centroid lock (keeps ring centered on glowing core during zooms without tract hijack)
                if (not lock_seed_xy) and rgb_ref is not None and (not fb_errs or fb_errs[-1] <= 14.0):
                    pk_xy, pk_sc = _find_local_hue_emission_peak(
                        nxt_bgr,
                        (float(pos_ref[0]), float(pos_ref[1])),
                        rgb_ref,
                        radius_px=56,
                        scale_x=scale_x,
                        scale_y=scale_y,
                    )
                    if pk_sc >= 24.0:
                        pos_ref[0] = 0.92 * pos_ref[0] + 0.08 * pk_xy[0]
                        pos_ref[1] = 0.92 * pos_ref[1] + 0.08 * pk_xy[1]

            if single_point:
                r_pos[0], r_pos[1] = l_pos[0], l_pos[1]

            # Detect true 90-degree out-of-plane head spin (View-Flip Guard) after initial 1.25s establish window;
            # never false-trigger on vertically stacked/aligned targets or steady single-plane push-ins!
            cur_span_x = float(r_pos[0] - l_pos[0])
            if flip_detected_t is None and (t_cur - float(t0)) >= 1.25 and not is_stacked_vstack:
                if (not single_point) and raw_init_dx >= 90.0 * scale_x and (
                    cur_span_x < float(R81_VIEW_FLIP_MIN_SPAN_RATIO) * init_span_x
                    or (corr0 < 0.28 and cur_span_x < 0.42 * init_span_x)
                ):
                    flip_detected_t = round(t_cur - float(t0), 3)
                elif corr0 < (0.05 if single_point else 0.14) and max(fb_errs or [0.0]) > (32.0 if single_point else 22.0):
                    flip_detected_t = round(t_cur - float(t0), 3)

            pos_l_c = (
                max(x_lo, min(x_hi, float(l_pos[0]))),
                max(y_lo, min(y_hi, float(l_pos[1]))),
            )
            pos_r_c = (
                max(x_lo, min(x_hi, float(r_pos[0]))),
                max(y_lo, min(y_hi, float(r_pos[1]))),
            )
            l_pos[0], l_pos[1] = pos_l_c
            r_pos[0], r_pos[1] = pos_r_c
            prev_g = nxt_g
            track_by_time.append((t_cur, pos_l_c, pos_r_c))

        meta_out["flip_rel_sec"] = flip_detected_t
    finally:
        cap.release()

    if len(track_by_time) < 2:
        return (fallback, meta_out) if return_meta else fallback

    ts_arr = np.array([row[0] for row in track_by_time], dtype=np.float64)
    l_xs = _zero_phase_smooth_1d(np.array([row[1][0] for row in track_by_time], dtype=np.float64))
    l_ys = _zero_phase_smooth_1d(np.array([row[1][1] for row in track_by_time], dtype=np.float64))
    r_xs = _zero_phase_smooth_1d(np.array([row[2][0] for row in track_by_time], dtype=np.float64))
    r_ys = _zero_phase_smooth_1d(np.array([row[2][1] for row in track_by_time], dtype=np.float64))

    out: list[tuple[tuple[float, float], tuple[float, float]]] = []
    for f_i in range(n_frames):
        tq = float(t0) + float(f_i) / float(max(1, fps))
        lx_q = float(np.interp(tq, ts_arr, l_xs))
        ly_q = float(np.interp(tq, ts_arr, l_ys))
        rx_q = float(np.interp(tq, ts_arr, r_xs))
        ry_q = float(np.interp(tq, ts_arr, r_ys))
        out.append(_clamp_pair(lx_q, ly_q, rx_q, ry_q))
    return (out, meta_out) if return_meta else out


def _render_r78m_dual_callout_rgba(
    canvas: Image.Image,
    callout: dict[str, Any],
    t_rel: float,
    master_alpha: float,
    *,
    width: int,
    height: int,
    safe_x_left: float,
    safe_x_right: float,
    safe_y_top: int,
    safe_y_bot: int,
    frame_index: int | None = None,
) -> Image.Image:
    """
    Rule R78-H / R81: Renders XL hand-lettered `PatrickHand` fountain-pen callout header inside `X = 78..904px`
    (`82-84px` single-line or automatic 2-line centered hub stack + `56px` subtitle, `0px` strikethrough, zero background box)
    with dark-rimmed tapered fountain-pen leader lines locked onto `1.0x` tracked brain hubs.
    """
    spec = callout.get("r78m_callout") if isinstance(callout.get("r78m_callout"), dict) else {}
    scale_x = width / 1080.0
    scale_y = height / 1920.0
    scale = min(scale_x, scale_y)
    stroke_px = max(1, int(round(3 * scale)))
    line_gap = max(1, int(round(2 * scale_y)))

    def _a(val: int) -> int:
        return max(0, min(255, int(round(val * master_alpha))))

    left_lbl = str(spec.get("left_lbl") or "Source Hub").strip()
    right_lbl = str(spec.get("right_lbl") or "Target Hub").strip()
    sub_lbl = str(spec.get("sub") or "").strip()
    arrow_kind = str(spec.get("arrow") or "fwd").strip().lower()
    left_rgb: tuple[int, int, int] = tuple(int(v) for v in spec.get("left_rgb", (72, 224, 255)))[:3]  # type: ignore[assignment]
    right_rgb: tuple[int, int, int] = tuple(int(v) for v in spec.get("right_rgb", (255, 86, 94)))[:3]  # type: ignore[assignment]
    left_mark = str(spec.get("left_mark") or "ring").strip().lower()
    right_mark = str(spec.get("right_mark") or "ring").strip().lower()

    # Priority 1: Blender 4.2 3D exact `camera_track.json` (`0.0px` lock); Priority 2: R81 `1.0x` DISOpticalFlow + peak lock
    track_3d = callout.get("camera_track")
    scene_hint = str(callout.get("scene") or callout.get("action") or "").lower()
    exp_l = _parse_callout_xy_pair(spec.get("left_target_xy")) or _parse_callout_xy_pair(spec.get("left_xy"))
    exp_r = _parse_callout_xy_pair(spec.get("right_target_xy")) or _parse_callout_xy_pair(spec.get("right_xy"))
    has_explicit_targets = bool(spec.get("left_target_xy") or spec.get("right_target_xy") or spec.get("lock_seed_xy"))
    is_stacked_vstack = bool(
        callout.get("stacked_cutaway_brain_compare")
        or spec.get("stacked_vstack")
        or "dual-specimen" in scene_hint
        or "two complete" in scene_hint
        or (exp_l is not None and exp_r is not None and abs(exp_r[1] - exp_l[1]) >= 460.0)
        or (isinstance(track_3d, dict) and str(track_3d.get("layout") or "") == "stacked_vstack")
    )
    t_in_clip = t_rel + float(callout.get("track_offset_sec") or 0.0)
    left_anc_key = str(spec.get("left_anchor") or "").strip()
    right_anc_key = str(spec.get("right_anchor") or "").strip()
    if not left_anc_key or not right_anc_key:
        if isinstance(track_3d, dict) and not is_stacked_vstack:
            s_reg = str(track_3d.get("start_region") or "").lower()
            e_reg = str(track_3d.get("end_region") or "").lower()
            l_low = left_lbl.lower()
            r_low = right_lbl.lower()
            # Auto-align when left_lbl names end_region and right_lbl names start_region (e.g. `arrow="rev"`)
            if s_reg and e_reg and s_reg != e_reg:
                s_toks = [w for w in s_reg.split() if len(w) >= 4]
                e_toks = [w for w in e_reg.split() if len(w) >= 4]
                l_hits_e = any(w in l_low for w in e_toks) or ("rear" in l_low and "posterior" in str(track_3d.get("morph_mode") or ""))
                r_hits_s = any(w in r_low for w in s_toks) or ("vision" in r_low and "visual" in s_reg) or ("place" in r_low and "parietal" in s_reg)
                if (l_hits_e or r_hits_s) and arrow_kind == "rev":
                    left_anc_key = left_anc_key or "end"
                    right_anc_key = right_anc_key or "start"
        left_anc_key = left_anc_key or "start"
        right_anc_key = right_anc_key or "end"

    live_l = _interpolate_track_xy(track_3d, left_anc_key, t_in_clip, width, height)
    live_r = _interpolate_track_xy(track_3d, right_anc_key, t_in_clip, width, height)
    tracked = callout.get("_r78m_tracked_pts")
    if live_l is not None and live_r is not None:
        lx, ly = live_l
        rx, ry = live_r
    elif isinstance(tracked, list) and tracked:
        q_idx = max(0, min(len(tracked) - 1, int(frame_index if frame_index is not None else 0)))
        (lx, ly), (rx, ry) = tracked[q_idx]
    else:
        raw_lxy = exp_l or (320.0, 960.0)
        raw_rxy = exp_r or (720.0, 960.0)
        lx, ly = float(raw_lxy[0]) * scale_x, float(raw_lxy[1]) * scale_y
        rx, ry = float(raw_rxy[0]) * scale_x, float(raw_rxy[1]) * scale_y

    # Enforce strict DQ10 left/right safe margin (`>= 75px` both sides) & `<= 910px` right UI rail
    hdr_left = max(safe_x_left + 30.0 * scale_x, 78.0 * scale_x)
    hdr_right = min(safe_x_right - 6.0 * scale_x, 904.0 * scale_x)
    usable_hdr_w = max(260.0 * scale_x, hdr_right - hdr_left)
    center_x = 0.5 * (hdr_left + hdr_right)

    rim_canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    fg_canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    text_canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    probe = ImageDraw.Draw(text_canvas)

    conn_w = float(136 if arrow_kind == "broken" else (104 if arrow_kind == "vs" else 132)) * scale_x
    layout_kwargs: dict[str, Any] = {}
    if is_stacked_vstack:
        layout_kwargs = {
            "single_max_px": 60,
            "single_min_px": 46,
            "stack_max_px": 48,
            "stack_min_px": 36,
        }
    hdr_sz, f_hdr, l_lines, r_lines, lw, rw_txt, block_h = _select_xl_dual_hub_layout(
        probe,
        left_lbl,
        right_lbl,
        conn_w,
        usable_hdr_w,
        scale_y=scale_y,
        stroke_px=stroke_px,
        line_gap=line_gap,
        **layout_kwargs,
    )

    f_sub = _load_hand_font(max(18, int(round(R81_CALLOUT_XL_SUB_MAX_PX * scale_y))), expressive_accent=False)
    sub_min_px = max(16, int(round(R81_CALLOUT_XL_SUB_MIN_PX * scale_y)))
    while sub_lbl and f_sub.size > sub_min_px:
        sb_try = probe.textbbox((0, 0), sub_lbl, font=f_sub, stroke_width=stroke_px)
        if (sb_try[2] - sb_try[0]) <= usable_hdr_w:
            break
        f_sub = _load_hand_font(max(sub_min_px, f_sub.size - max(1, int(round(2 * scale_y)))), expressive_accent=False)

    row_w = lw + conn_w + rw_txt
    row_x0 = max(hdr_left, min(hdr_right - row_w, center_x - 0.5 * row_w))
    l_cx = row_x0 + 0.5 * lw
    r_cx = row_x0 + lw + conn_w + 0.5 * rw_txt
    conn_x0 = row_x0 + lw + 15.0 * scale_x
    conn_x1 = row_x0 + lw + conn_w - 15.0 * scale_x

    # Stacked dual-brain (K06): anchor header cleanly in Y=5-10% above dorsal cortex
    top_ink_y = (
        max(0.05 * float(height), min(0.095 * float(height) - float(block_h), 0.052 * float(height)))
        if is_stacked_vstack
        else max(float(safe_y_top) + 16.0 * scale_y, 246.0 * scale_y)
    )
    _, l_h = _measure_ink_block(probe, l_lines, f_hdr, stroke_px=stroke_px, line_gap=line_gap)
    _, r_h = _measure_ink_block(probe, r_lines, f_hdr, stroke_px=stroke_px, line_gap=line_gap)
    l_top = top_ink_y + 0.5 * (block_h - l_h)
    r_top = top_ink_y + 0.5 * (block_h - r_h)
    mid_y = float(top_ink_y + 0.5 * block_h)

    p_text = _ease_out_cubic(t_rel / 0.22)
    p_conn = _ease_out_cubic((t_rel - 0.06) / 0.22)
    p_lines = _ease_in_out_cubic((t_rel - 0.12) / 0.30)
    p_rings = _ease_out_cubic((t_rel - 0.22) / 0.22)
    seed_base = 801 + int(callout.get("cut_index") or 1) * 19

    # R81 View-Flip Guard: fade ONLY leader lines & target rings smoothly if Google Flow spins brain 90° mid-cut
    flip_rel_sec = callout.get("_r81_flip_rel_sec")
    leader_flip_fade = 1.0
    if isinstance(flip_rel_sec, (int, float)) and float(flip_rel_sec) > 0.0 and t_rel > float(flip_rel_sec):
        leader_flip_fade = max(0.0, 1.0 - (t_rel - float(flip_rel_sec)) / max(0.08, float(R81_VIEW_FLIP_FADE_SEC)))

    # 1. XL PatrickHand hub blocks + zero-strikethrough colored fountain-pen underlines + XL subtitle
    t_al = _a(int(round(254 * max(0.0, p_text))))
    lb_drawn = _draw_ink_block_centered(
        text_canvas,
        l_lines,
        l_cx,
        l_top,
        f_hdr,
        (255, 252, 242, t_al),
        stroke_px=stroke_px,
        line_gap=line_gap,
        blur_px=3.2 * scale_y,
    )
    rb_drawn = _draw_ink_block_centered(
        text_canvas,
        r_lines,
        r_cx,
        r_top,
        f_hdr,
        (255, 252, 242, t_al),
        stroke_px=stroke_px,
        line_gap=line_gap,
        blur_px=3.2 * scale_y,
    )

    ul_gap = float(R81_CALLOUT_UNDERLINE_GAP_PX * scale_y)
    ul_y_l = float(lb_drawn[3]) + ul_gap
    ul_y_r = float(rb_drawn[3]) + ul_gap
    ul_y_max = max(ul_y_l, ul_y_r)

    if p_text > 0.02:
        _draw_r78m_pen_curve(
            fg_canvas,
            (float(lb_drawn[0]) + 2.0 * scale_x, ul_y_l),
            (0.5 * float(lb_drawn[0] + lb_drawn[2]), ul_y_l + 1.5 * scale_y),
            (float(lb_drawn[2]) - 2.0 * scale_x, ul_y_l),
            left_rgb,
            alpha=t_al,
            base_width=6.0 * scale,
            progress=p_text,
            seed=seed_base,
            rim_canvas=rim_canvas,
        )
        _draw_r78m_pen_curve(
            fg_canvas,
            (float(rb_drawn[0]) + 2.0 * scale_x, ul_y_r),
            (0.5 * float(rb_drawn[0] + rb_drawn[2]), ul_y_r + 1.5 * scale_y),
            (float(rb_drawn[2]) - 2.0 * scale_x, ul_y_r),
            right_rgb,
            alpha=t_al,
            base_width=6.0 * scale,
            progress=p_text,
            seed=seed_base + 1,
            rim_canvas=rim_canvas,
        )

    sub_bot_y = ul_y_max
    if sub_lbl:
        sb0 = probe.textbbox((0, 0), sub_lbl, font=f_sub, stroke_width=stroke_px)
        sub_w = sb0[2] - sb0[0]
        sub_cx = row_x0 + 0.5 * row_w
        sub_x = int(round(max(hdr_left, min(hdr_right - sub_w, sub_cx - 0.5 * sub_w)) - sb0[0]))
        sub_y = int(round(ul_y_max + 13.0 * scale_y - sb0[1]))
        sb_drawn = _draw_ink_text_clean(
            text_canvas,
            (sub_x, sub_y),
            sub_lbl,
            f_sub,
            (238, 244, 255, t_al),
            stroke_px=stroke_px,
            blur_px=3.0 * scale_y,
        )
        sub_bot_y = float(sb_drawn[3])

    leader_y0 = float(sub_bot_y + 13.0 * scale_y)

    # 2. Pure ink-drawn connector between hub blocks (zero missing Unicode box glyphs!)
    if p_conn > 0.02 and conn_x1 > conn_x0 + 8.0 * scale_x:
        c_al = _a(int(round(248 * p_conn)))
        cx_mid = 0.5 * (conn_x0 + conn_x1)
        if arrow_kind == "broken":
            _draw_r78m_pen_curve(
                fg_canvas,
                (conn_x0, mid_y),
                (0.5 * (conn_x0 + cx_mid - 16.0 * scale_x), mid_y - 2.0 * scale_y),
                (cx_mid - 18.0 * scale_x, mid_y),
                (246, 185, 77),
                alpha=c_al,
                base_width=5.6 * scale,
                progress=p_conn,
                seed=seed_base + 2,
                rim_canvas=rim_canvas,
            )
            _draw_r78m_x_mark(
                fg_canvas,
                cx_mid,
                mid_y,
                (255, 68, 85),
                arm=13.5 * scale,
                alpha=c_al,
                progress=p_conn,
                seed=seed_base + 3,
                scale=scale,
                rim_canvas=rim_canvas,
            )
            _draw_r78m_pen_curve(
                fg_canvas,
                (cx_mid + 18.0 * scale_x, mid_y),
                (0.5 * (cx_mid + 18.0 * scale_x + conn_x1), mid_y + 2.0 * scale_y),
                (conn_x1, mid_y),
                (148, 163, 184),
                alpha=c_al,
                base_width=5.2 * scale,
                progress=p_conn,
                seed=seed_base + 4,
                rim_canvas=rim_canvas,
            )
        elif arrow_kind == "vs":
            f_vs = _load_hand_font(max(20, int(round(hdr_sz * 0.66))), expressive_accent=False)
            vb = probe.textbbox((0, 0), "vs", font=f_vs, stroke_width=stroke_px)
            vw, vh = vb[2] - vb[0], vb[3] - vb[1]
            vx = int(round(cx_mid - 0.5 * vw - vb[0]))
            vy = int(round(mid_y - 0.5 * vh - vb[1]))
            _draw_ink_text_clean(
                text_canvas,
                (vx, vy),
                "vs",
                f_vs,
                (224, 233, 248, c_al),
                stroke_px=stroke_px,
                blur_px=2.8 * scale_y,
            )
        elif arrow_kind == "rev":
            _draw_r78m_pen_curve(
                fg_canvas,
                (conn_x1, mid_y),
                (cx_mid, mid_y - 2.5 * scale_y),
                (conn_x0 + 4.0 * scale_x, mid_y),
                (246, 196, 95),
                alpha=c_al,
                base_width=5.8 * scale,
                progress=p_conn,
                seed=seed_base + 5,
                rim_canvas=rim_canvas,
            )
            if p_conn > 0.45:
                head_a = 17.0 * scale
                _draw_r78m_pen_curve(
                    fg_canvas,
                    (conn_x0 + head_a, mid_y - 0.72 * head_a),
                    (conn_x0 + 5.0 * scale_x, mid_y - 2.5 * scale_y),
                    (conn_x0, mid_y),
                    (246, 196, 95),
                    alpha=c_al,
                    base_width=5.4 * scale,
                    seed=seed_base + 6,
                    rim_canvas=rim_canvas,
                )
                _draw_r78m_pen_curve(
                    fg_canvas,
                    (conn_x0 + head_a, mid_y + 0.72 * head_a),
                    (conn_x0 + 5.0 * scale_x, mid_y + 2.5 * scale_y),
                    (conn_x0, mid_y),
                    (246, 196, 95),
                    alpha=c_al,
                    base_width=5.4 * scale,
                    seed=seed_base + 7,
                    rim_canvas=rim_canvas,
                )
        else:  # fwd
            _draw_r78m_pen_curve(
                fg_canvas,
                (conn_x0, mid_y),
                (cx_mid, mid_y - 2.5 * scale_y),
                (conn_x1 - 4.0 * scale_x, mid_y),
                (246, 196, 95),
                alpha=c_al,
                base_width=5.8 * scale,
                progress=p_conn,
                seed=seed_base + 8,
                rim_canvas=rim_canvas,
            )
            if p_conn > 0.45:
                head_a = 17.0 * scale
                _draw_r78m_pen_curve(
                    fg_canvas,
                    (conn_x1 - head_a, mid_y - 0.72 * head_a),
                    (conn_x1 - 5.0 * scale_x, mid_y - 2.5 * scale_y),
                    (conn_x1, mid_y),
                    (246, 196, 95),
                    alpha=c_al,
                    base_width=5.4 * scale,
                    seed=seed_base + 9,
                    rim_canvas=rim_canvas,
                )
                _draw_r78m_pen_curve(
                    fg_canvas,
                    (conn_x1 - head_a, mid_y + 0.72 * head_a),
                    (conn_x1 - 5.0 * scale_x, mid_y + 2.5 * scale_y),
                    (conn_x1, mid_y),
                    (246, 196, 95),
                    alpha=c_al,
                    base_width=5.4 * scale,
                    seed=seed_base + 10,
                    rim_canvas=rim_canvas,
                )

    # Clamp target coordinates inside safe bounds and guarantee uncrossed ordering
    ring_r = (20.0 if is_stacked_vstack else 24.0) * scale
    ring_mx = 32.0 * scale_x
    min_tgt_y = max(leader_y0 + (24.0 if is_stacked_vstack else 36.0) * scale_y, (265.0 if is_stacked_vstack else 395.0) * scale_y)
    max_tgt_y = max(min_tgt_y, float(safe_y_bot) - 34.0 * scale_y)
    lx = max(safe_x_left + ring_mx, min(hdr_right - ring_mx, lx))
    rx = max(safe_x_left + ring_mx, min(hdr_right - ring_mx, rx))
    ly = max(min_tgt_y, min(0.46 * float(height) if is_stacked_vstack else max_tgt_y, ly))
    if is_stacked_vstack:
        ry = max(0.58 * float(height), min(0.63 * float(height), ry))
    else:
        ry = max(min_tgt_y, min(max_tgt_y, ry))
    if not is_stacked_vstack and not has_explicit_targets and live_l is None and lx + 34.0 * scale_x > rx:
        mid_t = 0.5 * (lx + rx)
        lx = max(safe_x_left + ring_mx, mid_t - 17.0 * scale_x)
        rx = min(hdr_right - ring_mx, lx + 34.0 * scale_x)

    # 3. Uncrossed left & right Bezier fountain-pen leader lines + round hand-sketched pointer rings
    left_anchor_x = max(hdr_left + 12.0 * scale_x, l_cx)
    right_anchor_x = min(hdr_right - 12.0 * scale_x, r_cx)
    if left_anchor_x + 40.0 * scale_x > right_anchor_x:
        left_anchor_x = max(hdr_left + 12.0 * scale_x, center_x - 80.0 * scale_x)
        right_anchor_x = min(hdr_right - 12.0 * scale_x, center_x + 80.0 * scale_x)

    if p_lines > 0.01 and leader_flip_fade > 0.02:
        l_al = max(0, min(255, int(round(_a(244) * leader_flip_fade))))
        l_end_y = max(leader_y0 + 14.0 * scale_y, ly - ring_r - 1.5 * scale_y)
        r_end_y = max(leader_y0 + 14.0 * scale_y, ry - ring_r - 1.5 * scale_y)
        if is_stacked_vstack:
            # Top panel pointer goes cleanly into Top Panel; Bottom panel pointer skirts outer right gutter so it never crosses Top brain!
            l_ctrl_x = max(safe_x_left + 14.0 * scale_x, min(hdr_right - 14.0 * scale_x, 0.72 * left_anchor_x + 0.28 * lx))
            r_gutter_x = min(hdr_right + 8.0 * scale_x, 906.0 * scale_x)
            _draw_r78m_pen_curve(
                fg_canvas,
                (left_anchor_x, leader_y0),
                (l_ctrl_x, 0.50 * leader_y0 + 0.50 * l_end_y),
                (lx, l_end_y),
                left_rgb,
                alpha=l_al,
                base_width=4.8 * scale,
                progress=p_lines,
                seed=seed_base + 11,
                rim_canvas=rim_canvas,
            )
            _draw_r78m_pen_curve(
                fg_canvas,
                (right_anchor_x, leader_y0),
                (r_gutter_x, 0.35 * leader_y0 + 0.65 * r_end_y),
                (rx, r_end_y),
                right_rgb,
                alpha=l_al,
                base_width=4.8 * scale,
                progress=p_lines,
                seed=seed_base + 12,
                rim_canvas=rim_canvas,
            )
        else:
            l_ctrl_x = 0.68 * left_anchor_x + 0.32 * lx - 12.0 * scale_x
            r_ctrl_x = 0.68 * right_anchor_x + 0.32 * rx + 12.0 * scale_x
            l_ctrl_x = max(safe_x_left + 14.0 * scale_x, min(hdr_right - 14.0 * scale_x, l_ctrl_x))
            r_ctrl_x = max(safe_x_left + 14.0 * scale_x, min(hdr_right - 14.0 * scale_x, r_ctrl_x))
            _draw_r78m_pen_curve(
                fg_canvas,
                (left_anchor_x, leader_y0),
                (l_ctrl_x, 0.46 * leader_y0 + 0.54 * l_end_y),
                (lx, l_end_y),
                left_rgb,
                alpha=l_al,
                base_width=5.0 * scale,
                progress=p_lines,
                seed=seed_base + 11,
                rim_canvas=rim_canvas,
            )
            _draw_r78m_pen_curve(
                fg_canvas,
                (right_anchor_x, leader_y0),
                (r_ctrl_x, 0.46 * leader_y0 + 0.54 * r_end_y),
                (rx, r_end_y),
                right_rgb,
                alpha=l_al,
                base_width=5.0 * scale,
                progress=p_lines,
                seed=seed_base + 12,
                rim_canvas=rim_canvas,
            )

    if p_rings > 0.02 and leader_flip_fade > 0.02:
        r_al = max(0, min(255, int(round(_a(248) * leader_flip_fade))))
        r_sub_al = max(0, min(255, int(round(_a(165) * leader_flip_fade))))
        if left_mark in ("x", "x_mark"):
            _draw_r78m_x_mark(
                fg_canvas, lx, ly, left_rgb, arm=18.0 * scale, alpha=r_al, progress=p_rings, seed=seed_base + 13, scale=scale, rim_canvas=rim_canvas
            )
            _draw_r78m_target_ring(
                fg_canvas, lx, ly, left_rgb, radius=27.0 * scale, alpha=r_sub_al, progress=p_rings, seed=seed_base + 14, scale=0.85 * scale, rim_canvas=rim_canvas
            )
        else:
            _draw_r78m_target_ring(
                fg_canvas, lx, ly, left_rgb, radius=ring_r, alpha=r_al, progress=p_rings, seed=seed_base + 15, scale=scale, rim_canvas=rim_canvas
            )

        if right_mark in ("x", "x_mark"):
            _draw_r78m_x_mark(
                fg_canvas, rx, ry, right_rgb, arm=18.0 * scale, alpha=r_al, progress=p_rings, seed=seed_base + 16, scale=scale, rim_canvas=rim_canvas
            )
            _draw_r78m_target_ring(
                fg_canvas, rx, ry, right_rgb, radius=27.0 * scale, alpha=r_sub_al, progress=p_rings, seed=seed_base + 17, scale=0.85 * scale, rim_canvas=rim_canvas
            )
        else:
            _draw_r78m_target_ring(
                fg_canvas, rx, ry, right_rgb, radius=ring_r, alpha=r_al, progress=p_rings, seed=seed_base + 18, scale=scale, rim_canvas=rim_canvas
            )

    strokes = Image.alpha_composite(rim_canvas, fg_canvas)
    out_canvas = Image.alpha_composite(canvas, strokes)
    out_canvas = Image.alpha_composite(out_canvas, text_canvas)
    return _clamp_callout_safe_rgba(
        out_canvas,
        safe_x_left=safe_x_left,
        safe_x_right=safe_x_right,
        safe_y_top=safe_y_top,
        safe_y_bot=safe_y_bot,
        width=width,
        height=height,
    )


def _render_r78m_single_callout_rgba(
    canvas: Image.Image,
    callout: dict[str, Any],
    t_rel: float,
    master_alpha: float,
    *,
    width: int,
    height: int,
    safe_x_left: float,
    safe_x_right: float,
    safe_y_top: int,
    safe_y_bot: int,
    frame_index: int | None = None,
) -> Image.Image:
    """
    Renders a centered XL `PatrickHand` single-hub callout (`r78m_single`) with colored fountain-pen underline,
    one curved tapered leader line, and one tracked pointer ring onto `canvas` (zero 'Target Hub' placeholder).
    """
    spec = callout.get("r78m_callout") if isinstance(callout.get("r78m_callout"), dict) else {}
    scale_x = width / 1080.0
    scale_y = height / 1920.0
    scale = min(scale_x, scale_y)
    stroke_px = max(1, int(round(3 * scale)))
    line_gap = max(1, int(round(2 * scale_y)))

    def _a(val: int) -> int:
        return max(0, min(255, int(round(val * master_alpha))))

    title_lbl = str(
        spec.get("left_lbl")
        or spec.get("title")
        or callout.get("anatomy_label")
        or callout.get("display_title")
        or "Brain Region"
    ).strip()
    sub_lbl = str(spec.get("sub") or "").strip()
    left_rgb: tuple[int, int, int] = tuple(
        int(v) for v in spec.get("left_rgb", spec.get("rgb", (72, 224, 255)))
    )[:3]  # type: ignore[assignment]
    left_mark = str(spec.get("left_mark") or spec.get("mark") or "ring").strip().lower()

    track_3d = callout.get("camera_track")
    exp_pt = (
        _parse_callout_xy_pair(spec.get("left_target_xy"))
        or _parse_callout_xy_pair(spec.get("target_xy"))
        or _parse_callout_xy_pair(spec.get("left_xy"))
        or _parse_callout_xy_pair(spec.get("xy"))
    )
    t_in_clip = t_rel + float(callout.get("track_offset_sec") or 0.0)
    live_pt = _interpolate_track_xy(track_3d, str(spec.get("left_anchor") or "start"), t_in_clip, width, height)
    tracked = callout.get("_r78m_tracked_pts")
    if live_pt is not None:
        tx, ty = live_pt
    elif isinstance(tracked, list) and tracked:
        q_idx = max(0, min(len(tracked) - 1, int(frame_index if frame_index is not None else 0)))
        tx, ty = tracked[q_idx][0]
    else:
        raw_xy = exp_pt or (540.0, 960.0)
        tx, ty = float(raw_xy[0]) * scale_x, float(raw_xy[1]) * scale_y

    hdr_left = max(safe_x_left + 30.0 * scale_x, 78.0 * scale_x)
    hdr_right = min(safe_x_right - 6.0 * scale_x, 904.0 * scale_x)
    usable_hdr_w = max(260.0 * scale_x, hdr_right - hdr_left)
    center_x = 0.5 * (hdr_left + hdr_right)

    rim_canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    fg_canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    text_canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    probe = ImageDraw.Draw(text_canvas)

    _hdr_sz, f_hdr, t_lines, _tw, _th = _select_xl_single_hub_layout(
        probe,
        title_lbl,
        usable_hdr_w,
        scale_y=scale_y,
        stroke_px=stroke_px,
        line_gap=line_gap,
    )
    f_sub = _load_hand_font(max(18, int(round(R81_CALLOUT_XL_SUB_MAX_PX * scale_y))), expressive_accent=False)
    sub_min_px = max(16, int(round(R81_CALLOUT_XL_SUB_MIN_PX * scale_y)))
    while sub_lbl and f_sub.size > sub_min_px:
        sb_try = probe.textbbox((0, 0), sub_lbl, font=f_sub, stroke_width=stroke_px)
        if (sb_try[2] - sb_try[0]) <= usable_hdr_w:
            break
        f_sub = _load_hand_font(max(sub_min_px, f_sub.size - max(1, int(round(2 * scale_y)))), expressive_accent=False)

    top_ink_y = max(float(safe_y_top) + 16.0 * scale_y, 246.0 * scale_y)
    p_text = _ease_out_cubic(t_rel / 0.22)
    p_lines = _ease_in_out_cubic((t_rel - 0.12) / 0.30)
    p_rings = _ease_out_cubic((t_rel - 0.22) / 0.22)
    seed_base = 801 + int(callout.get("cut_index") or 1) * 19

    flip_rel_sec = callout.get("_r81_flip_rel_sec")
    leader_flip_fade = 1.0
    if isinstance(flip_rel_sec, (int, float)) and float(flip_rel_sec) > 0.0 and t_rel > float(flip_rel_sec):
        leader_flip_fade = max(0.0, 1.0 - (t_rel - float(flip_rel_sec)) / max(0.08, float(R81_VIEW_FLIP_FADE_SEC)))

    t_al = _a(int(round(254 * max(0.0, p_text))))
    tb_drawn = _draw_ink_block_centered(
        text_canvas,
        t_lines,
        center_x,
        top_ink_y,
        f_hdr,
        (255, 252, 242, t_al),
        stroke_px=stroke_px,
        line_gap=line_gap,
        blur_px=3.2 * scale_y,
    )
    ul_gap = float(R81_CALLOUT_UNDERLINE_GAP_PX * scale_y)
    ul_y = float(tb_drawn[3]) + ul_gap
    if p_text > 0.02:
        _draw_r78m_pen_curve(
            fg_canvas,
            (float(tb_drawn[0]) + 2.0 * scale_x, ul_y),
            (0.5 * float(tb_drawn[0] + tb_drawn[2]), ul_y + 1.5 * scale_y),
            (float(tb_drawn[2]) - 2.0 * scale_x, ul_y),
            left_rgb,
            alpha=t_al,
            base_width=6.0 * scale,
            progress=p_text,
            seed=seed_base,
            rim_canvas=rim_canvas,
        )

    sub_bot_y = ul_y
    if sub_lbl:
        sb0 = probe.textbbox((0, 0), sub_lbl, font=f_sub, stroke_width=stroke_px)
        sub_w = sb0[2] - sb0[0]
        sub_x = int(round(max(hdr_left, min(hdr_right - sub_w, center_x - 0.5 * sub_w)) - sb0[0]))
        sub_y = int(round(ul_y + 13.0 * scale_y - sb0[1]))
        sb_drawn = _draw_ink_text_clean(
            text_canvas,
            (sub_x, sub_y),
            sub_lbl,
            f_sub,
            (238, 244, 255, t_al),
            stroke_px=stroke_px,
            blur_px=3.0 * scale_y,
        )
        sub_bot_y = float(sb_drawn[3])

    leader_y0 = float(sub_bot_y + 13.0 * scale_y)
    ring_r = 24.0 * scale
    ring_mx = 32.0 * scale_x
    min_tgt_y = max(leader_y0 + 36.0 * scale_y, 395.0 * scale_y)
    max_tgt_y = max(min_tgt_y, float(safe_y_bot) - 34.0 * scale_y)
    tx = max(safe_x_left + ring_mx, min(hdr_right - ring_mx, tx))
    ty = max(min_tgt_y, min(max_tgt_y, ty))

    if p_lines > 0.01 and leader_flip_fade > 0.02:
        l_al = max(0, min(255, int(round(_a(244) * leader_flip_fade))))
        t_end_y = max(leader_y0 + 14.0 * scale_y, ty - ring_r - 1.5 * scale_y)
        ctrl_x = max(safe_x_left + 14.0 * scale_x, min(hdr_right - 14.0 * scale_x, 0.65 * center_x + 0.35 * tx))
        _draw_r78m_pen_curve(
            fg_canvas,
            (center_x, leader_y0),
            (ctrl_x, 0.46 * leader_y0 + 0.54 * t_end_y),
            (tx, t_end_y),
            left_rgb,
            alpha=l_al,
            base_width=5.0 * scale,
            progress=p_lines,
            seed=seed_base + 11,
            rim_canvas=rim_canvas,
        )

    if p_rings > 0.02 and leader_flip_fade > 0.02:
        r_al = max(0, min(255, int(round(_a(248) * leader_flip_fade))))
        r_sub_al = max(0, min(255, int(round(_a(165) * leader_flip_fade))))
        if left_mark in ("x", "x_mark"):
            _draw_r78m_x_mark(
                fg_canvas, tx, ty, left_rgb, arm=18.0 * scale, alpha=r_al, progress=p_rings, seed=seed_base + 13, scale=scale, rim_canvas=rim_canvas
            )
            _draw_r78m_target_ring(
                fg_canvas, tx, ty, left_rgb, radius=27.0 * scale, alpha=r_sub_al, progress=p_rings, seed=seed_base + 14, scale=0.85 * scale, rim_canvas=rim_canvas
            )
        else:
            _draw_r78m_target_ring(
                fg_canvas, tx, ty, left_rgb, radius=ring_r, alpha=r_al, progress=p_rings, seed=seed_base + 15, scale=scale, rim_canvas=rim_canvas
            )

    strokes = Image.alpha_composite(rim_canvas, fg_canvas)
    out_canvas = Image.alpha_composite(canvas, strokes)
    out_canvas = Image.alpha_composite(out_canvas, text_canvas)
    return _clamp_callout_safe_rgba(
        out_canvas,
        safe_x_left=safe_x_left,
        safe_x_right=safe_x_right,
        safe_y_top=safe_y_top,
        safe_y_bot=safe_y_bot,
        width=width,
        height=height,
    )


def render_anatomy_callout_rgba_frame(
    callout: dict[str, Any],
    t_rel: float,
    total_dur: float,
    *,
    width: int = VIDEO_WIDTH,
    height: int = VIDEO_HEIGHT,
    frame_index: int | None = None,
) -> Image.Image:
    """Renders one `width x height` RGBA frame of a hand-drawn pen anatomical leader-line or 2-node circuit callout."""
    scale_x = width / 1080.0
    scale_y = height / 1920.0
    scale = min(scale_x, scale_y)
    stroke_px = max(1, int(round(3 * scale)))

    fade_in = min(1.0, max(0.0, t_rel / 0.18))
    fade_out = min(1.0, max(0.0, (total_dur - t_rel) / 0.22))
    master_alpha = min(fade_in, fade_out)

    canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    if master_alpha <= 0.01:
        return canvas

    safe_x_left = float(int(round(48 * scale_x)))
    safe_x_right = float(int(round(UNIVERSAL_SAFE_X_RIGHT_PX * scale_x)))
    safe_y_top = int(math.ceil(float(DATA_STAMP_Y_FRAC_RANGE[0]) * height))
    spec_dual = callout.get("r78m_callout") if isinstance(callout.get("r78m_callout"), dict) else {}
    sc_hint = str(callout.get("scene") or callout.get("action") or "").lower()
    el_p = _parse_callout_xy_pair(spec_dual.get("left_target_xy")) or _parse_callout_xy_pair(spec_dual.get("left_xy"))
    er_p = _parse_callout_xy_pair(spec_dual.get("right_target_xy")) or _parse_callout_xy_pair(spec_dual.get("right_xy"))
    is_stk_dual = bool(
        callout.get("stacked_cutaway_brain_compare")
        or spec_dual.get("stacked_vstack")
        or "dual-specimen" in sc_hint
        or "two complete" in sc_hint
        or (el_p is not None and er_p is not None and abs(er_p[1] - el_p[1]) >= 460.0)
    )
    safe_y_bot_dual = int(round((1635.0 if is_stk_dual else float(R81_TRACKING_MAX_Y_PX)) * scale_y))
    safe_y_bot = int(round(0.65 * height))

    if str(callout.get("callout_mode") or "") == "r78m_single":
        return _render_r78m_single_callout_rgba(
            canvas,
            callout,
            t_rel,
            master_alpha,
            width=width,
            height=height,
            safe_x_left=safe_x_left,
            safe_x_right=safe_x_right,
            safe_y_top=safe_y_top,
            safe_y_bot=safe_y_bot_dual,
            frame_index=frame_index,
        )

    if str(callout.get("callout_mode") or "") == "r78m_dual":
        return _render_r78m_dual_callout_rgba(
            canvas,
            callout,
            t_rel,
            master_alpha,
            width=width,
            height=height,
            safe_x_left=safe_x_left,
            safe_x_right=safe_x_right,
            safe_y_top=(int(round(0.045 * height)) if is_stk_dual else safe_y_top),
            safe_y_bot=safe_y_bot_dual,
            frame_index=frame_index,
        )

    if str(callout.get("callout_mode") or "single_region") in ("pathway_relay", "pathway_severed"):
        return _render_pathway_circuit_rgba(
            canvas,
            callout,
            t_rel,
            master_alpha,
            width=width,
            height=height,
            safe_x_left=safe_x_left,
            safe_x_right=safe_x_right,
            safe_y_top=safe_y_top,
            safe_y_bot=safe_y_bot,
        )

    def _a(val: int) -> int:
        return max(0, min(255, int(round(val * master_alpha))))

    track = callout.get("camera_track")
    t_in_clip = t_rel + float(callout.get("track_offset_sec") or 0.0)
    live_pt = _interpolate_track_xy(track, "end", t_in_clip, width, height) or _interpolate_track_xy(track, "start", t_in_clip, width, height)
    if live_pt is not None:
        ax, ay = live_pt
    else:
        ax_f, ay_f = callout["anchor_xy"]
        ax, ay = float(ax_f * width), float(ay_f * height)
    lx_f, ly_f = callout["label_xy"]
    accent_rgb: tuple[int, int, int] = tuple(int(x) for x in callout.get("accent_rgb", (72, 224, 255)))  # type: ignore[assignment]
    lx, ly = float(lx_f * width), float(ly_f * height)

    rim_canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    fg_canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    text_canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    probe_draw = ImageDraw.Draw(text_canvas)

    title_txt = str(callout.get("display_title") or "Brain Region").strip()
    role_txt = str(callout.get("short_role") or "").strip()
    role_disp = f"({role_txt})" if role_txt else ""

    max_allowed_w = max(int(round(180 * scale_x)), int(round(safe_x_right - safe_x_left - 44 * scale_x)))
    f_title = _load_hand_font(max(20, int(round(72 * scale_y))), expressive_accent=False)
    for pt_t in (72, 66, 60, 54, 48):
        f_title = _load_hand_font(max(18, int(round(pt_t * scale_y))), expressive_accent=False)
        tb = probe_draw.textbbox((0, 0), title_txt, font=f_title, stroke_width=stroke_px)
        if (tb[2] - tb[0]) <= max_allowed_w:
            break
    tb = probe_draw.textbbox((0, 0), title_txt, font=f_title, stroke_width=stroke_px)
    tw, th = tb[2] - tb[0], tb[3] - tb[1]

    f_role = _load_hand_font(max(16, int(round(50 * scale_y))), expressive_accent=False)
    for pt_r in (50, 46, 42, 36):
        f_role = _load_hand_font(max(15, int(round(pt_r * scale_y))), expressive_accent=False)
        rb = probe_draw.textbbox((0, 0), role_disp, font=f_role, stroke_width=stroke_px) if role_disp else (0, 0, 0, 0)
        if not role_disp or (rb[2] - rb[0]) <= max_allowed_w:
            break
    rb = probe_draw.textbbox((0, 0), role_disp, font=f_role, stroke_width=stroke_px) if role_disp else (0, 0, 0, 0)
    rw, rh = rb[2] - rb[0], rb[3] - rb[1]

    bar_w = min(int(round(safe_x_right - safe_x_left - 32 * scale_x)), max(tw, rw) + int(round(16 * scale_x)))
    pad_x = 18.0 * scale_x
    pad_top = int(round(16 * scale_y))
    half_span = 0.5 * float(bar_w) + pad_x
    if safe_x_left + half_span <= safe_x_right - half_span:
        lx = max(safe_x_left + half_span, min(safe_x_right - half_span, lx))
    else:
        lx = 0.5 * (safe_x_left + safe_x_right)

    total_txt_h = th + (int(round(10 * scale_y)) + rh if role_disp else 0) + int(round(24 * scale_y))
    min_top_y = float(safe_y_top + pad_top)
    max_top_y = float(max(min_top_y, safe_y_bot - total_txt_h - int(round(28 * scale_y))))
    top_y = max(min_top_y, min(max_top_y, ly - float(th)))

    ring_r = 23.0 * scale
    ring_margin_x = 32.0 * scale_x
    ring_margin_y = 32.0 * scale_y
    ax = max(safe_x_left + ring_margin_x, min(safe_x_right - ring_margin_x, ax))
    ay = max(float(safe_y_top) + ring_margin_y, min(float(safe_y_bot) - ring_margin_y, ay))

    p_ring = _ease_out_cubic(t_rel / 0.22)
    p_line = _ease_in_out_cubic((t_rel - 0.08) / 0.36)
    p_text = _ease_out_cubic((t_rel - 0.30) / 0.26)
    cut_seed = int(callout.get("cut_index") or 0)

    t_al = _a(int(round(252 * max(0.0, p_text))))
    tb_drawn = _draw_ink_block_centered(
        text_canvas,
        [title_txt],
        lx,
        top_y,
        f_title,
        (255, 252, 242, t_al),
        stroke_px=stroke_px,
        blur_px=3.2 * scale_y,
    )
    bot_ink_y = float(tb_drawn[3])
    if role_disp:
        rb_drawn = _draw_ink_block_centered(
            text_canvas,
            [role_disp],
            lx,
            bot_ink_y + 8.0 * scale_y,
            f_role,
            (*accent_rgb, t_al),
            stroke_px=stroke_px,
            blur_px=3.0 * scale_y,
        )
        bot_ink_y = float(rb_drawn[3])

    line_end_y = min(float(safe_y_bot) - 18.0 * scale_y, bot_ink_y + float(R81_CALLOUT_UNDERLINE_GAP_PX * scale_y))
    if p_text > 0.02:
        _draw_r78m_pen_curve(
            fg_canvas,
            (lx - 0.5 * bar_w, line_end_y),
            (lx, line_end_y + 1.8 * scale_y),
            (lx + 0.5 * bar_w, line_end_y),
            accent_rgb,
            alpha=t_al,
            base_width=5.4 * scale,
            progress=p_text,
            seed=701 + cut_seed,
            rim_canvas=rim_canvas,
        )

    if p_ring > 0.02:
        _draw_r78m_target_ring(
            fg_canvas,
            ax,
            ay,
            accent_rgb,
            radius=ring_r,
            alpha=_a(244),
            progress=p_ring,
            seed=301 + cut_seed,
            scale=scale,
            rim_canvas=rim_canvas,
        )

    if p_line > 0.01:
        p0y = max(float(safe_y_top) + 16.0 * scale_y, ay - ring_r - 1.5 * scale_y)
        p3y = min(float(safe_y_bot) - 14.0 * scale_y, line_end_y + 8.0 * scale_y)
        ctrl_x = max(safe_x_left + 14.0 * scale_x, min(safe_x_right - 14.0 * scale_x, 0.55 * lx + 0.45 * ax - 16.0 * scale_x))
        ctrl_y = 0.50 * (p0y + p3y)
        _draw_r78m_pen_curve(
            fg_canvas,
            (ax, p0y),
            (ctrl_x, ctrl_y),
            (lx, p3y),
            (252, 248, 238),
            alpha=_a(242),
            base_width=5.0 * scale,
            progress=p_line,
            seed=501 + cut_seed,
            rim_canvas=rim_canvas,
        )

    strokes = Image.alpha_composite(rim_canvas, fg_canvas)
    out_canvas = Image.alpha_composite(canvas, strokes)
    out_canvas = Image.alpha_composite(out_canvas, text_canvas)
    return _clamp_callout_safe_rgba(
        out_canvas,
        safe_x_left=safe_x_left,
        safe_x_right=safe_x_right,
        safe_y_top=safe_y_top,
        safe_y_bot=safe_y_bot,
        width=width,
        height=height,
    )


def composite_anatomy_labels_on_video(
    video_in: Path,
    video_out: Path,
    callouts: list[dict[str, Any]],
    *,
    fps: int = 30,
    width: int = VIDEO_WIDTH,
    height: int = VIDEO_HEIGHT,
) -> list[tuple[float, float]]:
    """Composites progressive R71/R81 hand-drawn pen leader-line callouts onto `video_in` -> `video_out`."""
    if not callouts:
        return []
    from pipeline.media_cache import atomic_commit_from_scratch, ram_tempdir

    ff = _ffmpeg_exe()
    applied: list[tuple[float, float]] = []
    with ram_tempdir(prefix="aab_anat_label_") as td:
        td_p = Path(td)
        cmd: list[str] = [ff, "-nostdin", "-hide_banner", "-loglevel", "error", "-y", "-i", str(video_in)]
        filter_parts: list[str] = []
        prev_lbl = "0:v"

        # Precompute 1D studio top-lighting falloff (Y = 0..515px scaled) for cuts where bright 3D cortex rises into header band
        scale_y_comp = height / 1920.0
        vig_y_flat = int(round(345.0 * scale_y_comp))
        vig_y_end = min(height, int(round(520.0 * scale_y_comp)))
        vig_profile = np.zeros((height, 1), dtype=np.float32)
        if vig_y_end > vig_y_flat > 0:
            vig_profile[:vig_y_flat, 0] = 1.0
            u_vig = np.linspace(0.0, 1.0, vig_y_end - vig_y_flat, dtype=np.float32)
            vig_profile[vig_y_flat:vig_y_end, 0] = 0.5 * (1.0 + np.cos(np.pi * u_vig))

        def _needs_studio_header_falloff(vid_p: Path, s_t: float, e_t: float) -> float:
            """Returns adaptive studio top-falloff peak alpha [0.0..0.76] when bright cortex intrudes into Y=11%..24%."""
            import cv2

            cap_v = cv2.VideoCapture(str(vid_p))
            if not cap_v.isOpened():
                return 0.0
            try:
                v_fps = float(cap_v.get(cv2.CAP_PROP_FPS) or fps or 30.0)
                tot_v = int(cap_v.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
                max_p92 = 0.0
                hy0, hy1 = int(round(0.11 * height)), int(round(0.24 * height))
                hx0, hx1 = int(round(0.08 * width)), int(round(0.84 * width))
                for q_t in (s_t + 0.15, 0.5 * (s_t + e_t), max(s_t + 0.15, e_t - 0.25)):
                    fi = max(0, min(max(0, tot_v - 1), int(round(q_t * v_fps))))
                    cap_v.set(cv2.CAP_PROP_POS_FRAMES, fi)
                    ok_v, bgr_v = cap_v.read()
                    if not ok_v or bgr_v is None:
                        continue
                    if bgr_v.shape[1] != width or bgr_v.shape[0] != height:
                        bgr_v = cv2.resize(bgr_v, (width, height), interpolation=cv2.INTER_AREA)
                    g_band = cv2.cvtColor(bgr_v[hy0:hy1, hx0:hx1], cv2.COLOR_BGR2GRAY)
                    if g_band.size > 0:
                        max_p92 = max(max_p92, float(np.percentile(g_band, 92)))
                if max_p92 <= 44.0:
                    return 0.0
                return min(0.76, max(0.38, (max_p92 - 36.0) / 245.0))
            finally:
                cap_v.release()

        for idx, cal in enumerate(callouts):
            t0 = float(callout_start := cal["start_sec"])
            t1 = float(cal["end_sec"])
            dur = max(0.8, t1 - t0)
            n_frames = max(10, int(math.ceil(dur * fps)))
            cal_run = cal
            cal_mode_r = str(cal.get("callout_mode") or "")
            if cal_mode_r in ("r78m_dual", "r78m_single") and not isinstance(cal.get("camera_track"), dict):
                is_single_r = cal_mode_r == "r78m_single"
                spec_r = cal.get("r78m_callout") if isinstance(cal.get("r78m_callout"), dict) else {}
                sc_hint_r = str(cal.get("scene") or cal.get("action") or "").lower()
                exp_l_r = (
                    _parse_callout_xy_pair(spec_r.get("left_target_xy"))
                    or _parse_callout_xy_pair(spec_r.get("target_xy"))
                    or _parse_callout_xy_pair(spec_r.get("left_xy"))
                    or _parse_callout_xy_pair(spec_r.get("xy"))
                )
                exp_r_r = _parse_callout_xy_pair(spec_r.get("right_target_xy")) or _parse_callout_xy_pair(spec_r.get("right_xy"))
                has_explicit_r = bool(
                    spec_r.get("left_target_xy")
                    or spec_r.get("target_xy")
                    or spec_r.get("right_target_xy")
                    or spec_r.get("lock_seed_xy")
                )
                is_stk_r = (not is_single_r) and bool(
                    cal.get("stacked_cutaway_brain_compare")
                    or spec_r.get("stacked_vstack")
                    or "dual-specimen" in sc_hint_r
                    or "two complete" in sc_hint_r
                    or (exp_l_r is not None and exp_r_r is not None and abs(exp_r_r[1] - exp_l_r[1]) >= 460.0)
                )
                lxy = exp_l_r or ((540.0, 960.0) if is_single_r else (320.0, 960.0))
                rxy = lxy if is_single_r else (exp_r_r or (720.0, 960.0))
                l_rgb = tuple(int(v) for v in spec_r.get("left_rgb", spec_r.get("rgb", (72, 224, 255))))[:3]  # type: ignore[assignment]
                r_rgb = l_rgb if is_single_r else tuple(int(v) for v in spec_r.get("right_rgb", (255, 86, 94)))[:3]  # type: ignore[assignment]
                tracked_pts, track_meta = _track_r78m_callout_points_on_video(
                    Path(video_in),
                    float(cal.get("cut_start_sec") if cal.get("cut_start_sec") is not None else t0),
                    t0,
                    t1,
                    fps,
                    (float(lxy[0]), float(lxy[1])),
                    (float(rxy[0]), float(rxy[1])),
                    n_frames,
                    width=width,
                    height=height,
                    left_rgb=l_rgb,
                    right_rgb=r_rgb,
                    lock_seed_xy=bool(spec_r.get("lock_seed_xy") or has_explicit_r),
                    preserve_order=has_explicit_r,
                    is_stacked_vstack=is_stk_r,
                    auto_seed_when_default=(exp_l_r is None and (is_single_r or exp_r_r is None)),
                    single_point=is_single_r,
                    return_meta=True,
                )
                cal_run = {
                    **cal,
                    "_r78m_tracked_pts": tracked_pts,
                    "_r81_flip_rel_sec": track_meta.get("flip_rel_sec"),
                }
            vig_peak = _needs_studio_header_falloff(Path(video_in), t0, t1)
            seq_dir = td_p / f"anat_{idx}"
            seq_dir.mkdir(parents=True, exist_ok=True)
            for f_i in range(n_frames):
                t_rel_f = f_i / float(fps)
                im = render_anatomy_callout_rgba_frame(
                    cal_run,
                    t_rel=t_rel_f,
                    total_dur=dur,
                    width=width,
                    height=height,
                    frame_index=f_i,
                )
                if vig_peak > 0.01 and vig_y_end > 0:
                    m_al = min(min(1.0, max(0.0, t_rel_f / 0.18)), min(1.0, max(0.0, (dur - t_rel_f) / 0.22)))
                    if m_al > 0.01:
                        scrim_arr = np.zeros((height, width, 4), dtype=np.uint8)
                        scrim_arr[:vig_y_end, :, 0] = 5
                        scrim_arr[:vig_y_end, :, 1] = 8
                        scrim_arr[:vig_y_end, :, 2] = 15
                        row_a = np.clip(np.round(255.0 * vig_peak * m_al * vig_profile[:vig_y_end, 0]), 0, 255).astype(np.uint8)
                        scrim_arr[:vig_y_end, :, 3] = row_a[:, None]
                        im = Image.alpha_composite(Image.fromarray(scrim_arr, mode="RGBA"), im)
                im.save(seq_dir / f"f_{f_i:04d}.png", format="PNG", compress_level=1)
            cmd.extend(["-framerate", str(fps), "-i", str(seq_dir / "f_%04d.png")])
            in_idx = idx + 1
            ov_lbl = f"an_pts_{idx}"
            out_lbl = f"an_out_{idx}"
            filter_parts.append(f"[{in_idx}:v]setpts=PTS-STARTPTS+{callout_start:.4f}/TB[{ov_lbl}]")
            filter_parts.append(
                f"[{prev_lbl}][{ov_lbl}]overlay=0:0:eof_action=pass:enable='between(t,{t0:.4f},{t1:.4f})'[{out_lbl}]"
            )
            prev_lbl = out_lbl
            applied.append((round(t0, 3), round(t1, 3)))

        tmp_out = td_p / "anatlabel_out.mp4"
        cmd.extend(
            [
                "-filter_complex",
                ";".join(filter_parts),
                "-map",
                f"[{prev_lbl}]",
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "17",
                "-pix_fmt",
                "yuv420p",
                str(tmp_out),
            ]
        )
        res = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=240, stdin=subprocess.DEVNULL)
        if res.returncode != 0 or not tmp_out.is_file():
            tmp_out.unlink(missing_ok=True)
            raise RuntimeError(f"Anatomy label overlay failed (rc={res.returncode}): {(res.stderr or '')[:350]}")
        atomic_commit_from_scratch(tmp_out, video_out)
    return applied
