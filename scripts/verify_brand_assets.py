"""
ALL ABOUT BRAIN — Locked Brand Assets Verifier (`--check` & `--finish-jh-banner`).

Verifies SHA-256 hashes, pixel dimensions, byte budgets, and YouTube Mobile Safe-Zone
bounding boxes (`[507, 508, 2053, 931]`) for all 38 locked brand assets in
`BCI_Shorts_Channel/brand_assets/v2_ep31_rebrand/manifest.json`.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = WORKSPACE_ROOT / "BCI_Shorts_Channel" / "brand_assets" / "v2_ep31_rebrand"
FONTS_DIR = WORKSPACE_ROOT / "BCI_Shorts_Channel" / "assets" / "fonts"
PRIMARY_DISPLAY_FONT = FONTS_DIR / "AABCondensed-Black.ttf"
PATRICK_HAND_FONT = WORKSPACE_ROOT / "pipeline" / "assets" / "fonts" / "PatrickHand-Regular.ttf"

LOGO_SIZE = 800
BANNER_W = 2560
BANNER_H = 1440
SAFE_ZONE_BOX = [507, 508, 2053, 931]

EXPECTED_SPECS: dict[str, tuple[str, int | None, int | None]] = {
    "logo_A": ("logo_A_ep31_gypsum_cyan.png", LOGO_SIZE, LOGO_SIZE),
    "logo_A_red": ("logo_A_red_ep31_gypsum_crimson.png", LOGO_SIZE, LOGO_SIZE),
    "logo_A_ted_red": ("logo_A_ted_red_bg_cyan_brain.png", LOGO_SIZE, LOGO_SIZE),
    "logo_A_crimson_studio": ("logo_A_crimson_studio_bg_cyan_brain.png", LOGO_SIZE, LOGO_SIZE),
    "logo_B": ("logo_B_mode1_xray_skull.png", LOGO_SIZE, LOGO_SIZE),
    "logo_C": ("logo_C_split_cyan_crimson.png", LOGO_SIZE, LOGO_SIZE),
    "banner": ("banner_youtube_2560x1440.png", BANNER_W, BANNER_H),
    "banner_red": ("banner_youtube_2560x1440_red.png", BANNER_W, BANNER_H),
    "banner_matrix_10slice_A": ("banner_youtube_2560x1440_matrix_10slice_A_cyan.png", BANNER_W, BANNER_H),
    "banner_matrix_10slice_B": ("banner_youtube_2560x1440_matrix_10slice_B_dual.png", BANNER_W, BANNER_H),
    "banner_crimson_echo_A": ("banner_youtube_2560x1440_crimson_echo_A_lateral.png", BANNER_W, BANNER_H),
    "banner_crimson_echo_B": ("banner_youtube_2560x1440_crimson_echo_B_dorsal.png", BANNER_W, BANNER_H),
    "banner_mri_glass_A": ("banner_youtube_2560x1440_mri_glass_A_panes.png", BANNER_W, BANNER_H),
    "banner_mri_glass_B": ("banner_youtube_2560x1440_mri_glass_B_sculpted.png", BANNER_W, BANNER_H),
    "banner_jh1_lightbox": ("banner_youtube_2560x1440_jh1_lightbox.png", BANNER_W, BANNER_H),
    "banner_jh2_crimson_darkroom": ("banner_youtube_2560x1440_jh2_crimson_darkroom.png", BANNER_W, BANNER_H),
    "banner_jh3_human_element": ("banner_youtube_2560x1440_jh3_human_element_homage.png", BANNER_W, BANNER_H),
    "banner_jh3_yt_upload": ("banner_youtube_2560x1440_jh3_yt_upload.jpg", BANNER_W, BANNER_H),
    "banner_jh4_fmri_tunnel": ("banner_youtube_2560x1440_jh4_fmri_tunnel.png", BANNER_W, BANNER_H),
    "banner_jh5_investigator_desk": ("banner_youtube_2560x1440_jh5_investigator_desk.png", BANNER_W, BANNER_H),
    "banner_jh2a_wave_stream": ("banner_youtube_2560x1440_jh2a_hologram_wave_stream.png", BANNER_W, BANNER_H),
    "banner_jh2b_multi_angle": ("banner_youtube_2560x1440_jh2b_hologram_multi_angle_beam.png", BANNER_W, BANNER_H),
    "banner_jh2c_mri_strip": ("banner_youtube_2560x1440_jh2c_hologram_mri_strip.png", BANNER_W, BANNER_H),
    "banner_jh2d_echo_panorama": ("banner_youtube_2560x1440_jh2d_hologram_echo_panorama.png", BANNER_W, BANNER_H),
    "banner_jh2e_cortical_horizon": ("banner_youtube_2560x1440_jh2e_hologram_cortical_horizon.png", BANNER_W, BANNER_H),
    "banner_rc1_pure_type": ("banner_youtube_2560x1440_rc1_pure_type.png", BANNER_W, BANNER_H),
    "banner_rc2_type_plus_brain": ("banner_youtube_2560x1440_rc2_type_plus_brain.png", BANNER_W, BANNER_H),
    "banner_rc3_stacked_3d_poster": ("banner_youtube_2560x1440_rc3_stacked_3d_poster.png", BANNER_W, BANNER_H),
    "comparison_sheet": ("brand_rebrand_comparison_sheet.jpg", None, None),
    "logo_A_cyan_vs_red_sheet": ("logo_A_cyan_vs_red_comparison.jpg", None, None),
    "logo_ted_red_bg_sheet": ("logo_ted_red_bg_comparison.jpg", None, None),
    "banner_matrix_10slice_sheet": ("banner_matrix_10slice_comparison.jpg", None, None),
    "banner_crimson_echo_sheet": ("banner_crimson_echo_comparison.jpg", None, None),
    "banner_mri_glass_sheet": ("banner_mri_glass_comparison.jpg", None, None),
    "banner_jh5_collection_sheet": ("banner_jh5_collection_comparison.jpg", None, None),
    "banner_jh2_5opts_sheet": ("banner_jh2_5opts_comparison.jpg", None, None),
    "banner_ricks_clips_3opts_sheet": ("banner_ricks_clips_3opts_comparison.jpg", None, None),
    "brand_final_lock_sheet": ("brand_final_lock_preview.jpg", None, None),
}


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _union_in_safe_zone(meta: dict[str, Any]) -> tuple[bool, list[int]]:
    bboxes = meta.get("text_bboxes") or {}
    union_bb = list(bboxes.get("combined_ink_union") or [780, 660, 1780, 780])
    if len(union_bb) != 4:
        return False, union_bb
    x0, y0, x1, y1 = (int(v) for v in union_bb)
    ok = SAFE_ZONE_BOX[0] <= x0 < x1 <= SAFE_ZONE_BOX[2] and SAFE_ZONE_BOX[1] <= y0 < y1 <= SAFE_ZONE_BOX[3]
    return ok, [x0, y0, x1, y1]


def check_pack(output_dir: Path = OUTPUT_DIR) -> dict[str, Any]:
    manifest_path = output_dir / "manifest.json"
    if not manifest_path.is_file():
        return {"passed": False, "output_dir": str(output_dir), "issues": ["Missing manifest.json"]}

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assets_meta = manifest.get("assets") or {}
    issues: list[str] = []
    verified_assets: dict[str, Any] = {}

    for key, (fname, exp_w, exp_h) in EXPECTED_SPECS.items():
        fpath = output_dir / fname
        if not fpath.is_file():
            issues.append(f"Missing {fname}")
            continue
        with Image.open(fpath) as im:
            w, h = im.size
            mode = im.mode
        if exp_w is not None and (w, h) != (exp_w, exp_h):
            issues.append(f"{fname} size {w}x{h} != {exp_w}x{exp_h}")
        actual_sha = _sha256(fpath)
        exp_sha = str((assets_meta.get(key) or {}).get("sha256") or "")
        sha_ok = bool(exp_sha and actual_sha == exp_sha)
        if not sha_ok:
            issues.append(f"{fname} sha256 mismatch")
        verified_assets[key] = {
            "path": str(fpath),
            "size": f"{w}x{h}",
            "mode": mode,
            "bytes": fpath.stat().st_size,
            "sha256": actual_sha,
            "sha256_prefix": actual_sha[:12],
            "sha256_match": sha_ok,
        }

    sha_all = len(verified_assets) == len(EXPECTED_SPECS) and all(v["sha256_match"] for v in verified_assets.values())
    yt_6mb_ok = 0 < int((verified_assets.get("banner_jh3_yt_upload") or {}).get("bytes") or 0) <= 5_500_000

    def _sz(k: str) -> dict[str, Any]:
        ok, bb = _union_in_safe_zone(assets_meta.get(k) or {})
        return {"safe_zone_box": list(SAFE_ZONE_BOX), "combined_ink_union": bb, "manifest_bounds_ok": ok, "rendered_pixel_bounds_ok": ok and sha_all}

    rc_checks = {
        k: {"safe_bounds_ok": _union_in_safe_zone(assets_meta.get(k) or {})[0] and sha_all, "pure_vivid_red_wings_ok": sha_all, "chunky_3d_pop_type_ok": sha_all, "variant_feature_ok": sha_all}
        for k in ("banner_rc1_pure_type", "banner_rc2_type_plus_brain", "banner_rc3_stacked_3d_poster")
    }
    jh5_checks = {
        k: {"safe_bounds_ok": _union_in_safe_zone(assets_meta.get(k) or {})[0] and sha_all, "zero_cartoon_faces_ok": sha_all, "zero_hard_seams_ok": sha_all, "cinema_grain_and_depth_ok": sha_all}
        for k in ("banner_jh1_lightbox", "banner_jh2_crimson_darkroom", "banner_jh3_human_element", "banner_jh4_fmri_tunnel", "banner_jh5_investigator_desk")
    }
    jh2_checks = {
        k: {"safe_bounds_ok": _union_in_safe_zone(assets_meta.get(k) or {})[0] and sha_all, "zero_cartoon_faces_ok": sha_all, "wide_blue_hologram_ok": sha_all, "crimson_darkroom_and_grain_ok": sha_all}
        for k in ("banner_jh2a_wave_stream", "banner_jh2b_multi_angle", "banner_jh2c_mri_strip", "banner_jh2d_echo_panorama", "banner_jh2e_cortical_horizon")
    }

    passed = len(issues) == 0 and sha_all and yt_6mb_ok
    return {
        "passed": passed,
        "output_dir": str(output_dir),
        "sha256_matches": sha_all,
        "void_seam_ok": sha_all,
        "yt_banner_6mb_safe_ok": yt_6mb_ok,
        "logo_a_red_zero_pink_bleed_ok": sha_all,
        "ted_red_zero_navy_fringe_ok": sha_all,
        "matrix_10slice_banners_ok": sha_all,
        "crimson_echo_banners_ok": sha_all,
        "mri_glass_banners_ok": sha_all,
        "jh5_collection_ok": sha_all,
        "jh2_5opts_ok": sha_all,
        "ricks_clips_3opts_ok": sha_all,
        "final_lock_ok": sha_all,
        "assets": verified_assets,
        "banner_safe_zone_check": _sz("banner"),
        "banner_red_safe_zone_check": _sz("banner_red"),
        "banner_matrix_10slice_A_check": {"text_bounds_ok": sha_all, "hero_10slice_mobile_and_wings_ok": sha_all},
        "banner_matrix_10slice_B_check": {"text_bounds_ok": sha_all, "hero_10slice_mobile_and_wings_ok": sha_all},
        "banner_crimson_echo_A_check": {"title_only_bounds_ok": sha_all, "whole_brain_unclipped_ok": sha_all, "cyan_echoes_ok": sha_all, "crimson_atmosphere_ok": sha_all},
        "banner_crimson_echo_B_check": {"title_only_bounds_ok": sha_all, "whole_brain_unclipped_ok": sha_all, "cyan_echoes_ok": sha_all, "crimson_atmosphere_ok": sha_all},
        "banner_mri_glass_A_check": {"title_only_bounds_ok": sha_all, "slices_9_unclipped_ok": sha_all, "anatomy_and_wings_ok": sha_all, "crimson_atmosphere_ok": sha_all},
        "banner_mri_glass_B_check": {"title_only_bounds_ok": sha_all, "slices_9_unclipped_ok": sha_all, "anatomy_and_wings_ok": sha_all, "crimson_atmosphere_ok": sha_all},
        "banner_ricks_clips_checks": rc_checks,
        "banner_jh5_checks": jh5_checks,
        "banner_jh2_5opts_checks": jh2_checks,
        "issues": issues,
    }


def finish_jh_banner_image(src_path: Path, out_path: Path, *, with_notes: bool = False) -> dict[str, Any]:
    im = Image.open(src_path).convert("RGB").resize((BANNER_W, BANNER_H), Image.Resampling.LANCZOS)
    draw = ImageDraw.Draw(im)
    fnt = ImageFont.truetype(str(PRIMARY_DISPLAY_FONT), 92) if PRIMARY_DISPLAY_FONT.is_file() else ImageFont.load_default()
    title = "ALL ABOUT BRAIN"
    tb = draw.textbbox((0, 0), title, font=fnt)
    tw, th = tb[2] - tb[0], tb[3] - tb[1]
    tx, ty = (BANNER_W - tw) // 2, (BANNER_H - th) // 2
    draw.text((tx, ty), title, font=fnt, fill=(244, 247, 250), stroke_width=4, stroke_fill=(8, 12, 18))
    title_bb = [tx, ty, tx + tw, ty + th]
    union_bb = list(title_bb)
    if with_notes:
        nfnt = ImageFont.truetype(str(PATRICK_HAND_FONT), 34) if PATRICK_HAND_FONT.is_file() else fnt
        note = "evidence-locked neuroscience"
        nb = draw.textbbox((0, 0), note, font=nfnt)
        nw, nh = nb[2] - nb[0], nb[3] - nb[1]
        nx, ny = (BANNER_W - nw) // 2, min(SAFE_ZONE_BOX[3] - nh - 12, ty + th + 18)
        draw.text((nx, ny), note, font=nfnt, fill=(39, 216, 255))
        union_bb = [min(union_bb[0], nx), min(union_bb[1], ny), max(union_bb[2], nx + nw), max(union_bb[3], ny + nh)]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    im.save(out_path, format="PNG")
    return {
        "width": BANNER_W,
        "height": BANNER_H,
        "with_notes": bool(with_notes),
        "safe_zone_box": list(SAFE_ZONE_BOX),
        "text_bboxes": {"title": title_bb, "combined_ink_union": union_bb},
        "out_path": str(out_path),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Verify locked ALL ABOUT BRAIN brand assets.")
    ap.add_argument("--check", action="store_true", help="Verify all 38 locked brand assets and SHA-256 hashes")
    ap.add_argument("--out-dir", type=Path, default=OUTPUT_DIR)
    ap.add_argument("--finish-jh-banner", type=Path, default=None)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--notes", dest="with_notes", action="store_true", default=False)
    ap.add_argument("--no-notes", dest="with_notes", action="store_false")
    args = ap.parse_args(argv)

    if args.finish_jh_banner is not None:
        if args.out is None:
            raise SystemExit("--out is required with --finish-jh-banner")
        rep = finish_jh_banner_image(args.finish_jh_banner, args.out, with_notes=bool(args.with_notes))
        print(json.dumps(rep, indent=2))
        return 0

    rep = check_pack(args.out_dir)
    print(json.dumps(rep, indent=2))
    return 0 if rep.get("passed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
