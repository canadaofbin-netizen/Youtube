"""
ALL ABOUT BRAIN — Coarse-to-Fine 2-Stage VLM Triage Sheet Builder (Tier S-3).

Standalone local-only utility & CLI (0 Google Flow / 0 network calls):
  - Stage 1 (Coarse): packs up to 12 images (4x3) onto exact 1536x1536 square JPEG contact
    sheets (~1,032-1,120 Gemini vision tokens each) with crisp tile borders & ID headers.
  - Stage 2 (Fine): extracts <= 384x384 square JPEG ROI crops (<= 258 tokens each) on
    suspect images or normalized bounding boxes without upscaling past 384x384.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys
from typing import Any, Mapping, Sequence

from PIL import Image, ImageDraw, ImageFont, ImageOps

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

_IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".webp")


def _load_triage_font(size: int = 18) -> ImageFont.ImageFont | ImageFont.FreeTypeFont:
    font_candidates = (
        WORKSPACE_ROOT / "BCI_Shorts_Channel" / "assets" / "fonts" / "Inter-Variable.ttf",
        WORKSPACE_ROOT / "BCI_Shorts_Channel" / "assets" / "fonts" / "AABCondensed-Black.ttf",
        WORKSPACE_ROOT / "pipeline" / "assets" / "fonts" / "PatrickHand-Regular.ttf",
    )
    for fp in font_candidates:
        if fp.exists():
            try:
                return ImageFont.truetype(str(fp), size=size)
            except OSError:
                continue
    return ImageFont.load_default()


def _natural_sort_key(path: Path) -> tuple[Any, ...]:
    parts = re.split(r"([0-9]+)", path.name.lower())
    return tuple(int(p) if p.isdigit() else p for p in parts)


def _safe_slug(text: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]+", "_", str(text or "item")).strip("_")[:48] or "item"


def render_coarse_triage_sheets(
    image_paths: Sequence[str | Path],
    out_dir: str | Path,
    *,
    labels: Sequence[str] | None = None,
    grid_cols: int = 4,
    grid_rows: int = 3,
    canvas_size: int = 1536,
) -> list[dict[str, Any]]:
    """
    Render up to `grid_cols * grid_rows` (default 4x3 = 12) images onto exact `canvas_size x canvas_size`
    (default 1536x1536) square JPEG triage sheets with crisp tile borders and ID headers.
    """
    paths = [Path(p) for p in (image_paths or ()) if Path(p).exists()]
    if not paths:
        return []
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    cols = max(1, int(grid_cols))
    rows = max(1, int(grid_rows))
    size = max(128, int(canvas_size))
    per_sheet = cols * rows
    cell_w = size // cols
    cell_h = size // rows
    header_h = max(24, min(36, cell_h // 12))
    border_px = 3
    font = _load_triage_font(size=max(13, min(18, header_h - 8)))

    resolved_labels: list[str] = []
    for idx, p in enumerate(paths):
        lbl = str(labels[idx]).strip() if (labels and idx < len(labels) and str(labels[idx]).strip()) else f"{idx + 1:02d}:{p.stem[:20]}"
        resolved_labels.append(lbl)

    sheets: list[dict[str, Any]] = []
    for sheet_idx, start in enumerate(range(0, len(paths), per_sheet), start=1):
        batch_paths = paths[start : start + per_sheet]
        batch_labels = resolved_labels[start : start + per_sheet]
        canvas = Image.new("RGB", (size, size), (16, 19, 25))
        draw = ImageDraw.Draw(canvas)
        items_meta: list[dict[str, Any]] = []

        for local_i, (img_p, lbl) in enumerate(zip(batch_paths, batch_labels)):
            r = local_i // cols
            c = local_i % cols
            x0 = c * cell_w
            y0 = r * cell_h
            x1 = size if c == cols - 1 else (x0 + cell_w)
            y1 = size if r == rows - 1 else (y0 + cell_h)

            # Crisp cell border + header bar
            draw.rectangle([x0 + 1, y0 + 1, x1 - 2, y1 - 2], fill=(22, 26, 34), outline=(72, 82, 98), width=border_px)
            draw.rectangle([x0 + border_px, y0 + border_px, x1 - border_px - 1, y0 + border_px + header_h], fill=(28, 34, 45))
            draw.text((x0 + border_px + 6, y0 + border_px + 4), lbl[:28], fill=(245, 248, 255), font=font)

            body_x0 = x0 + border_px + 2
            body_y0 = y0 + border_px + header_h + 2
            body_w = max(8, (x1 - border_px - 2) - body_x0)
            body_h = max(8, (y1 - border_px - 2) - body_y0)

            with Image.open(img_p) as im:
                rgb = ImageOps.exif_transpose(im).convert("RGB")
                fitted = ImageOps.contain(rgb, (body_w, body_h), method=Image.Resampling.LANCZOS)
            paste_x = body_x0 + (body_w - fitted.width) // 2
            paste_y = body_y0 + (body_h - fitted.height) // 2
            canvas.paste(fitted, (paste_x, paste_y))
            items_meta.append({"index": start + local_i, "label": lbl, "source": str(img_p)})

        sheet_file = out_path / f"triage_coarse_{sheet_idx:02d}.jpg"
        canvas.save(sheet_file, format="JPEG", quality=88, optimize=True)
        sheets.append(
            {
                "sheet_path": str(sheet_file),
                "sheet_index": sheet_idx,
                "width": size,
                "height": size,
                "tile_count": len(batch_paths),
                "items": items_meta,
            }
        )
    return sheets


def _resolve_bbox_norm(
    idx: int,
    label: str,
    stem: str,
    bboxes_norm: Sequence[Any] | Mapping[Any, Any] | None,
) -> tuple[float, float, float, float] | None:
    if bboxes_norm is None:
        return None
    raw: Any = None
    if isinstance(bboxes_norm, Mapping):
        for key in (idx, str(idx), label, stem):
            if key in bboxes_norm:
                raw = bboxes_norm[key]
                break
    elif isinstance(bboxes_norm, Sequence) and idx < len(bboxes_norm):
        raw = bboxes_norm[idx]
    if not isinstance(raw, (list, tuple)) or len(raw) != 4:
        return None
    x0, y0, x1, y1 = (float(v) for v in raw)
    x0, x1 = max(0.0, min(1.0, min(x0, x1))), max(0.0, min(1.0, max(x0, x1)))
    y0, y1 = max(0.0, min(1.0, min(y0, y1))), max(0.0, min(1.0, max(y0, y1)))
    if x1 <= x0 or y1 <= y0:
        return None
    return (x0, y0, x1, y1)


def render_fine_suspect_crops(
    image_paths: Sequence[str | Path],
    out_dir: str | Path,
    *,
    crop_size: int = 384,
    bboxes_norm: Sequence[Any] | Mapping[Any, Any] | None = None,
    labels: Sequence[str] | None = None,
) -> list[dict[str, Any]]:
    """
    Extract square fine-inspection JPEG crops (<= `crop_size x crop_size`, default <= 384x384,
    <= 258 Gemini vision tokens) centered on target/specified normalized ROIs without upscaling.
    """
    paths = [Path(p) for p in (image_paths or ()) if Path(p).exists()]
    if not paths:
        return []
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    max_side = max(32, int(crop_size))

    crops: list[dict[str, Any]] = []
    for idx, img_p in enumerate(paths):
        lbl = str(labels[idx]).strip() if (labels and idx < len(labels) and str(labels[idx]).strip()) else img_p.stem
        bbox = _resolve_bbox_norm(idx, lbl, img_p.stem, bboxes_norm)
        with Image.open(img_p) as im:
            rgb = ImageOps.exif_transpose(im).convert("RGB")
            w, h = rgb.size
            if bbox is not None:
                bx0, by0, bx1, by1 = bbox
                rx0, ry0 = int(round(bx0 * w)), int(round(by0 * h))
                rx1, ry1 = int(round(bx1 * w)), int(round(by1 * h))
                rw = max(1, rx1 - rx0)
                rh = max(1, ry1 - ry0)
                side = max(rw, rh)
                cx = (rx0 + rx1) // 2
                cy = (ry0 + ry1) // 2
                side = min(side, max(w, h))
                sx0 = max(0, min(max(0, w - min(side, w)), cx - side // 2))
                sy0 = max(0, min(max(0, h - min(side, h)), cy - side // 2))
                sx1 = min(w, sx0 + side)
                sy1 = min(h, sy0 + side)
                region = rgb.crop((sx0, sy0, sx1, sy1))
                cw, ch = region.size
                sq_side = min(max(cw, ch), max_side) if max(cw, ch) > max_side else max(cw, ch)
                if cw != ch:
                    # Aspect-preserving center pad into exact square without upscaling smaller axis
                    target_sq = Image.new("RGB", (max(cw, ch), max(cw, ch)), (16, 19, 25))
                    target_sq.paste(region, ((max(cw, ch) - cw) // 2, (max(cw, ch) - ch) // 2))
                    region = target_sq
                if region.width > max_side or region.height > max_side:
                    region = region.resize((sq_side, sq_side), Image.Resampling.LANCZOS)
                bbox_px = [sx0, sy0, sx1, sy1]
            else:
                min_dim = min(w, h)
                roi_side = min(min_dim, max(max_side, min_dim // 2)) if min_dim >= max_side else min_dim
                sx0 = max(0, (w - roi_side) // 2)
                sy0 = max(0, (h - roi_side) // 2)
                sx1 = min(w, sx0 + roi_side)
                sy1 = min(h, sy0 + roi_side)
                region = rgb.crop((sx0, sy0, sx1, sy1))
                if region.width > max_side or region.height > max_side:
                    region = region.resize((max_side, max_side), Image.Resampling.LANCZOS)
                bbox_px = [sx0, sy0, sx1, sy1]

        crop_file = out_path / f"triage_fine_{idx + 1:02d}_{_safe_slug(lbl)}.jpg"
        region.save(crop_file, format="JPEG", quality=90, optimize=True)
        crops.append(
            {
                "crop_path": str(crop_file),
                "label": lbl,
                "source": str(img_p),
                "width": region.width,
                "height": region.height,
                "bbox_px": bbox_px,
            }
        )
    return crops


def _collect_project_images(project_dir: Path, mode: str) -> list[Path]:
    if mode == "refs":
        for rel in ("03_visuals/reference_images", "reference_images"):
            cand = project_dir / rel
            if cand.is_dir():
                imgs = [p for p in cand.iterdir() if p.is_file() and p.suffix.lower() in _IMAGE_EXTS]
                if imgs:
                    return sorted(imgs, key=_natural_sort_key)
    elif mode == "cuts":
        for rel in (
            "05_assembly/posthoc_viewer_strips",
            "03_visuals/clip_previews",
            "03_visuals/clip_frames",
        ):
            cand = project_dir / rel
            if cand.is_dir():
                imgs = [p for p in cand.iterdir() if p.is_file() and p.suffix.lower() in _IMAGE_EXTS]
                if imgs:
                    return sorted(imgs, key=_natural_sort_key)
    return []


def _matches_suspect(path: Path, idx: int, tokens: Sequence[str]) -> bool:
    stem_l = path.stem.lower()
    idx_1 = f"{idx + 1:02d}"
    for tok in tokens:
        t = tok.strip().lower()
        if not t:
            continue
        if t in stem_l:
            return True
        m_num = re.fullmatch(r"c0*([0-9]+)|0*([0-9]+)", t)
        if m_num:
            num = int(m_num.group(1) or m_num.group(2))
            if f"{num:02d}" == idx_1 or re.search(rf"(?:^|[^0-9])0*{num}(?:[^0-9]|$)", stem_l):
                return True
    return False


def _compact_cli_manifest(
    *,
    mode: str,
    source_count: int,
    coarse_sheets: list[dict[str, Any]],
    fine_crops: list[dict[str, Any]],
    max_bytes: int = 1500,
) -> dict[str, Any]:
    manifest: dict[str, Any] = {
        "mode": mode,
        "source_count": source_count,
        "coarse_sheet_count": len(coarse_sheets),
        "coarse_sheets": [
            {"path": s["sheet_path"], "size": f"{s['width']}x{s['height']}", "tiles": s["tile_count"]}
            for s in coarse_sheets
        ],
        "fine_crop_count": len(fine_crops),
        "fine_crops": [
            {"path": c["crop_path"], "label": c["label"], "size": f"{c['width']}x{c['height']}"}
            for c in fine_crops
        ],
    }
    while len(json.dumps(manifest, ensure_ascii=False).encode("utf-8")) > max_bytes:
        if manifest["fine_crops"]:
            manifest["fine_crops"].pop()
            manifest["fine_crops_truncated"] = True
        elif manifest["coarse_sheets"]:
            manifest["coarse_sheets"].pop()
            manifest["coarse_sheets_truncated"] = True
        else:
            break
    return manifest


def _resolve_project_dir(project: str | None, explicit_dir: str | None) -> Path | None:
    if explicit_dir:
        return Path(explicit_dir)
    if project:
        cand = Path(project)
        if cand.is_dir():
            return cand
        return WORKSPACE_ROOT / "BCI_Shorts_Channel" / "projects" / project
    return None


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render 1536x1536 4x3 coarse & <=384x384 fine VLM triage JPEGs.")
    parser.add_argument("--project", default=None, help="Project ID or path")
    parser.add_argument("--dir", default=None, help="Explicit project directory override")
    parser.add_argument("--mode", choices=["refs", "cuts", "files"], default=None, help="Image collection mode")
    parser.add_argument("--files", nargs="+", default=None, help="Explicit image paths (mode=files)")
    parser.add_argument("--suspects", default="", help="Comma-separated suspect IDs/labels (e.g. c01,c05)")
    parser.add_argument("--out-dir", default=None, help="Output directory for generated JPEGs")
    parser.add_argument("--grid-cols", type=int, default=4, help="Coarse sheet columns (default: 4)")
    parser.add_argument("--grid-rows", type=int, default=3, help="Coarse sheet rows (default: 3)")
    parser.add_argument("--canvas-size", type=int, default=1536, help="Coarse square sheet side px (default: 1536)")
    parser.add_argument("--crop-size", type=int, default=384, help="Max fine square crop side px (default: 384)")
    args = parser.parse_args(argv)

    mode = args.mode or ("files" if args.files else "refs")
    p_dir = _resolve_project_dir(args.project, args.dir)
    if args.files:
        images = [Path(f) for f in args.files if Path(f).exists()]
    elif p_dir is not None:
        images = _collect_project_images(p_dir, mode)
    else:
        images = []

    if args.out_dir:
        out_dir = Path(args.out_dir)
    elif p_dir is not None:
        out_dir = p_dir / "05_assembly" / "vlm_triage_sheets"
    else:
        out_dir = Path("/tmp/vlm_triage_sheets")

    coarse_sheets = render_coarse_triage_sheets(
        images,
        out_dir,
        grid_cols=args.grid_cols,
        grid_rows=args.grid_rows,
        canvas_size=args.canvas_size,
    )

    suspect_tokens = [tok.strip() for tok in str(args.suspects or "").split(",") if tok.strip()]
    fine_crops: list[dict[str, Any]] = []
    if suspect_tokens and images:
        matched = [p for idx, p in enumerate(images) if _matches_suspect(p, idx, suspect_tokens)]
        if matched:
            fine_crops = render_fine_suspect_crops(
                matched,
                out_dir / "fine",
                crop_size=args.crop_size,
            )

    manifest = _compact_cli_manifest(
        mode=mode,
        source_count=len(images),
        coarse_sheets=coarse_sheets,
        fine_crops=fine_crops,
        max_bytes=1500,
    )
    print(json.dumps(manifest, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
