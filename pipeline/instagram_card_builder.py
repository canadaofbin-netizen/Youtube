"""
ALL ABOUT BRAIN - Instagram Card News Builder (4:5 Carousel PNGs + 9:16 Reels PNGs & MP4)
=======================================================================================
Composites clean editorial neuroscience typography over text-free AI/Blender backgrounds
(`03_visuals/flow_native_clips/clip_*.mp4` + `R70-M` Data Stamps) with strict `90px` horizontal
safe margins (`x = 90..990` -> `56px` buffer inside Instagram's `3:4` profile grid crop `x = 34..1046`).
"""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from pipeline.config import FONTS_DIR, PROJECTS_DIR

DISPLAY_FONT_PATH = FONTS_DIR / "AABCondensed-Black.ttf"
BODY_FONT_PATH = FONTS_DIR / "Inter-Variable.ttf"

CAROUSEL_4X5_WIDTH = 1080
CAROUSEL_4X5_HEIGHT = 1350
CAROUSEL_4X5_SAFE_MARGIN_X = 90  # x = 90..990 -> 56px inner margin inside 3:4 profile grid crop (x = 34..1046)
IG_GRID_3X4_CROP_X_RANGE = (34, 1046)

_BANNED_MANYCHAT_CTA_RE = re.compile(
    r"\b(?:manychat|comment\s+['\"]?[a-z0-9_]{2,20}['\"]?\s+(?:below|to\s+get|and\s+i['’]?ll\s+dm|for\s+the\s+link|for\s+my)|dm\s+me\s+['\"]?[a-z0-9_]{2,20}['\"]?)\b",
    flags=re.IGNORECASE,
)

# Brand palette (deep obsidian + electric neuroscience cyan #27D8FF)
ACCENT_CYAN = (39, 216, 255, 255)
ACCENT_CYAN_DIM = (39, 216, 255, 90)
TEXT_WHITE = (248, 250, 252, 255)
TEXT_MUTED = (203, 213, 225, 255)
TEXT_DIM = (148, 163, 184, 255)
PILL_BG = (15, 23, 42, 215)
PILL_BORDER = (39, 216, 255, 160)


@dataclass(frozen=True)
class CardSlide:
    tag: str
    headline: str
    body: str
    bg_image: Path
    footer_note: str = ""


def validate_slide_copy_safety(slide: CardSlide | str) -> None:
    """Hard-blocks ManyChat / comment-keyword DM automation CTAs (permanently ON HOLD)."""
    if isinstance(slide, str):
        combined = slide
    else:
        combined = " | ".join([slide.tag, slide.headline, slide.body, slide.footer_note])
    m = _BANNED_MANYCHAT_CTA_RE.search(combined)
    if m:
        raise ValueError(
            f"Forbidden ManyChat / comment-keyword CTA detected in carousel slide ({m.group(0)!r})."
        )


def _load_font(path: Path, size: int, weight: int | None = None) -> ImageFont.FreeTypeFont:
    font = ImageFont.truetype(str(path), size=size)
    if weight is not None:
        try:
            font.set_variation_by_axes([weight])
        except Exception:
            pass
    return font


def _fit_cover_image(img_path: Path, target_w: int, target_h: int, vertical_bias: float = 0.42) -> Image.Image:
    with Image.open(img_path) as im:
        rgb = im.convert("RGB")
    src_w, src_h = rgb.size
    scale = max(target_w / src_w, target_h / src_h)
    new_w = max(target_w, int(round(src_w * scale)))
    new_h = max(target_h, int(round(src_h * scale)))
    resized = rgb.resize((new_w, new_h), Image.Resampling.LANCZOS)
    left = max(0, (new_w - target_w) // 2)
    top = int(round(max(0, new_h - target_h) * vertical_bias))
    top = min(top, max(0, new_h - target_h))
    return resized.crop((left, top, left + target_w, top + target_h)).convert("RGBA")


def _apply_scrim(
    canvas: Image.Image,
    top_end_ratio: float,
    bottom_start_ratio: float,
    top_alpha: int = 205,
    bottom_alpha: int = 242,
) -> Image.Image:
    w, h = canvas.size
    alpha = np.zeros((h, w), dtype=np.uint8)
    y = np.linspace(0.0, 1.0, h, dtype=np.float32)[:, None]

    if top_end_ratio > 0:
        t_mask = np.clip(1.0 - (y / top_end_ratio), 0.0, 1.0) ** 1.35
        alpha = np.maximum(alpha, (t_mask * top_alpha).astype(np.uint8))

    if bottom_start_ratio < 1.0:
        b_span = max(1e-4, 1.0 - bottom_start_ratio)
        b_mask = np.clip((y - bottom_start_ratio) / b_span, 0.0, 1.0) ** 1.15
        alpha = np.maximum(alpha, (b_mask * bottom_alpha).astype(np.uint8))

    overlay_arr = np.zeros((h, w, 4), dtype=np.uint8)
    overlay_arr[..., 0] = 6
    overlay_arr[..., 1] = 10
    overlay_arr[..., 2] = 20
    overlay_arr[..., 3] = alpha
    overlay = Image.fromarray(overlay_arr, mode="RGBA")
    return Image.alpha_composite(canvas, overlay)


def _wrap_lines(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    words = text.split()
    if not words:
        return []
    lines: list[str] = []
    cur = words[0]
    for w in words[1:]:
        cand = f"{cur} {w}"
        bbox = draw.textbbox((0, 0), cand, font=font)
        if (bbox[2] - bbox[0]) <= max_width:
            cur = cand
        else:
            lines.append(cur)
            cur = w
    lines.append(cur)
    return lines


def _measure_lines_height(draw: ImageDraw.ImageDraw, lines: list[str], font: ImageFont.FreeTypeFont, line_gap: int) -> int:
    if not lines:
        return 0
    total = 0
    for idx, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=font)
        total += bbox[3] - bbox[1]
        if idx < len(lines) - 1:
            total += line_gap
    return total


def _truncate_to_pixel_width(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont,
    max_width: int,
) -> str:
    candidate = text.strip()
    if not candidate:
        return ""
    bbox = draw.textbbox((0, 0), candidate, font=font)
    if (bbox[2] - bbox[0]) <= max_width:
        return candidate
    while len(candidate) > 8:
        candidate = candidate[:-2].rstrip(" ·,;:-")
        trial = f"{candidate}..."
        tb = draw.textbbox((0, 0), trial, font=font)
        if (tb[2] - tb[0]) <= max_width:
            return trial
    return candidate


def _render_single_slide(
    slide: CardSlide,
    index: int,
    total: int,
    *,
    width: int,
    height: int,
    margin_left: int,
    margin_right: int,
    top_y: int,
    bottom_anchor_y: int,
    brand_label: str,
    is_reel: bool,
    show_footer: bool = True,
) -> Image.Image:
    validate_slide_copy_safety(slide)
    canvas = _fit_cover_image(slide.bg_image, width, height, vertical_bias=0.38)
    if is_reel:
        canvas = _apply_scrim(canvas, top_end_ratio=0.25, bottom_start_ratio=0.46, top_alpha=215, bottom_alpha=245)
    else:
        canvas = _apply_scrim(canvas, top_end_ratio=0.24, bottom_start_ratio=0.44, top_alpha=195, bottom_alpha=244)

    draw = ImageDraw.Draw(canvas)
    content_w = width - margin_left - margin_right

    # 1. Segmented progress bar
    seg_gap = 10
    seg_h = 6
    seg_w = (content_w - seg_gap * (total - 1)) / max(1, total)
    for i in range(total):
        sx0 = int(round(margin_left + i * (seg_w + seg_gap)))
        sx1 = min(width - margin_right, int(round(sx0 + seg_w)))
        fill = ACCENT_CYAN if i <= index else (255, 255, 255, 58)
        draw.rounded_rectangle((sx0, top_y, sx1, top_y + seg_h), radius=3, fill=fill)

    # 2. Tag pill + slide counter
    tag_y = top_y + 26
    tag_font = _load_font(BODY_FONT_PATH, 23, weight=600)
    cnt_font = _load_font(BODY_FONT_PATH, 23, weight=600)
    tag_text = slide.tag.strip().upper()
    tb = draw.textbbox((0, 0), tag_text, font=tag_font)
    pill_w = min(content_w - 130, (tb[2] - tb[0]) + 34)
    pill_h = (tb[3] - tb[1]) + 20
    draw.rounded_rectangle(
        (margin_left, tag_y, margin_left + pill_w, tag_y + pill_h),
        radius=pill_h // 2,
        fill=PILL_BG,
        outline=PILL_BORDER,
        width=2,
    )
    draw.text((margin_left + 17, tag_y + 8 - tb[1]), tag_text, font=tag_font, fill=ACCENT_CYAN)

    cnt_text = f"{index + 1:02d} / {total:02d}"
    cb = draw.textbbox((0, 0), cnt_text, font=cnt_font)
    draw.text((width - margin_right - (cb[2] - cb[0]), tag_y + 8 - cb[1]), cnt_text, font=cnt_font, fill=TEXT_MUTED)

    # 3. Bottom editorial block (auto-sized headline + accent bar + body + footer)
    headline_size = 74 if is_reel else 78
    headline_font = _load_font(DISPLAY_FONT_PATH, headline_size)
    head_lines = _wrap_lines(draw, slide.headline.strip(), headline_font, content_w)
    while len(head_lines) > 3 and headline_size > 52:
        headline_size -= 4
        headline_font = _load_font(DISPLAY_FONT_PATH, headline_size)
        head_lines = _wrap_lines(draw, slide.headline.strip(), headline_font, content_w)

    body_size = 30 if is_reel else 31
    body_font = _load_font(BODY_FONT_PATH, body_size, weight=400)
    body_lines = _wrap_lines(draw, slide.body.strip(), body_font, content_w)
    while len(body_lines) > 4 and body_size > 24:
        body_size -= 2
        body_font = _load_font(BODY_FONT_PATH, body_size, weight=400)
        body_lines = _wrap_lines(draw, slide.body.strip(), body_font, content_w)

    head_gap = 11
    body_gap = 11
    head_h = _measure_lines_height(draw, head_lines, headline_font, head_gap)
    body_h = _measure_lines_height(draw, body_lines, body_font, body_gap)

    footer_font = _load_font(BODY_FONT_PATH, 21, weight=500)
    footer_h = 34 if show_footer else 0
    footer_gap = 34 if show_footer else 0
    total_block_h = head_h + 22 + 5 + 22 + body_h + footer_gap + footer_h
    cur_y = bottom_anchor_y - total_block_h

    for line in head_lines:
        lb = draw.textbbox((0, 0), line, font=headline_font)
        draw.text((margin_left, cur_y + 3 - lb[1]), line, font=headline_font, fill=(0, 0, 0, 155))
        draw.text((margin_left, cur_y - lb[1]), line, font=headline_font, fill=TEXT_WHITE)
        cur_y += (lb[3] - lb[1]) + head_gap

    cur_y += 22 - head_gap
    draw.rounded_rectangle((margin_left, cur_y, margin_left + 72, cur_y + 5), radius=2, fill=ACCENT_CYAN)
    cur_y += 5 + 22

    for line in body_lines:
        lb = draw.textbbox((0, 0), line, font=body_font)
        draw.text((margin_left, cur_y - lb[1]), line, font=body_font, fill=TEXT_MUTED)
        cur_y += (lb[3] - lb[1]) + body_gap

    if show_footer:
        footer_y = bottom_anchor_y - footer_h
        draw.line((margin_left, footer_y - 14, width - margin_right, footer_y - 14), fill=(255, 255, 255, 42), width=1)
        raw_left_footer = slide.footer_note.strip() or brand_label
        right_footer = (
            "SWIPE ->"
            if (index < total - 1 and not is_reel)
            else ("SAVE & SHARE" if index == total - 1 else brand_label)
        )

        rfb = draw.textbbox((0, 0), right_footer, font=footer_font)
        right_w = rfb[2] - rfb[0]
        max_left_w = max(180, content_w - right_w - 28)
        left_footer = _truncate_to_pixel_width(draw, raw_left_footer, footer_font, max_left_w)

        lfb = draw.textbbox((0, 0), left_footer, font=footer_font)
        draw.text((margin_left, footer_y - lfb[1]), left_footer, font=footer_font, fill=TEXT_DIM)
        draw.text(
            (width - margin_right - right_w, footer_y - rfb[1]),
            right_footer,
            font=footer_font,
            fill=ACCENT_CYAN,
        )
    return canvas.convert("RGB")


def render_carousel_4x5_slides(
    slides: Sequence[CardSlide],
    output_dir: Path,
    *,
    brand_label: str = "@ALLABOUTBRAIN · PEER-REVIEWED NEUROSCIENCE",
) -> list[Path]:
    """
    Renders `1080x1350` (`4:5`) Instagram feed carousel PNGs into `<output_dir>/carousel_4x5/`
    using `90px` horizontal margins (`x = 90..990` -> `56px` safety inside IG's `3:4` profile grid crop).
    """
    if not slides:
        raise ValueError("slides cannot be empty")
    dir_4x5 = Path(output_dir) / "carousel_4x5"
    dir_4x5.mkdir(parents=True, exist_ok=True)
    paths_4x5: list[Path] = []
    total = len(slides)
    for idx, slide in enumerate(slides):
        img_4x5 = _render_single_slide(
            slide,
            idx,
            total,
            width=CAROUSEL_4X5_WIDTH,
            height=CAROUSEL_4X5_HEIGHT,
            margin_left=CAROUSEL_4X5_SAFE_MARGIN_X,
            margin_right=CAROUSEL_4X5_SAFE_MARGIN_X,
            top_y=64,
            bottom_anchor_y=1280,
            brand_label=brand_label,
            is_reel=False,
        )
        p4 = dir_4x5 / f"slide_{idx + 1:02d}.png"
        img_4x5.save(p4, format="PNG", optimize=True)
        paths_4x5.append(p4)
    return paths_4x5


def render_reel_mp4_from_slides(
    slide_paths: Sequence[Path],
    out_mp4: Path,
    *,
    slide_duration_sec: float = 3.8,
    fade_duration_sec: float = 0.35,
    fps: int = 30,
) -> Path:
    """Renders a silent 9:16 H.264 Reels MP4 with smooth crossfades so users can pick audio inside Instagram."""
    if len(slide_paths) < 2:
        raise ValueError("At least 2 slides are required to render a Reel MP4")

    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    cmd: list[str] = ["ffmpeg", "-y"]
    for sp in slide_paths:
        cmd.extend(["-loop", "1", "-t", f"{slide_duration_sec:.2f}", "-i", str(sp)])

    cmd.extend(["-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100"])

    filter_parts: list[str] = []
    n = len(slide_paths)
    for i in range(n):
        filter_parts.append(f"[{i}:v]fps={fps},format=yuv420p,setsar=1[v{i}]")

    prev_label = "v0"
    for i in range(1, n):
        offset = i * (slide_duration_sec - fade_duration_sec)
        out_label = f"xf{i}" if i < n - 1 else "vout"
        filter_parts.append(
            f"[{prev_label}][v{i}]xfade=transition=fade:duration={fade_duration_sec:.2f}:offset={offset:.2f}[{out_label}]"
        )
        prev_label = out_label

    audio_idx = n
    cmd.extend([
        "-filter_complex", ";".join(filter_parts),
        "-map", "[vout]",
        "-map", f"{audio_idx}:a",
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "18",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "128k",
        "-shortest",
        "-movflags", "+faststart",
        str(out_mp4),
    ])
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg failed ({proc.returncode}): {proc.stderr[-1200:]}")
    return out_mp4


def build_instagram_card_package(
    slides: Sequence[CardSlide],
    output_dir: Path,
    *,
    brand_label: str = "@ALLABOUTBRAIN · PEER-REVIEWED NEUROSCIENCE",
    slide_duration_sec: float = 3.8,
) -> dict[str, object]:
    """
    Generates BOTH Instagram formats from the same 6-slide storyboard:
      1. 4:5 Feed Carousel PNGs (`carousel_4x5/slide_01.png` .. `slide_06.png`, 1080x1350, `90px` horizontal safe margin)
      2. 9:16 Reels Safe-Zone PNGs (`reels_9x16/slide_01.png` .. `slide_06.png`, 1080x1920)
      3. 9:16 Silent Reels MP4 (`reel_9x16.mp4`) ready for in-app Instagram audio selection.
    """
    if not slides:
        raise ValueError("slides cannot be empty")

    output_dir = Path(output_dir)
    paths_4x5 = render_carousel_4x5_slides(slides, output_dir, brand_label=brand_label)

    dir_9x16 = output_dir / "reels_9x16"
    dir_9x16.mkdir(parents=True, exist_ok=True)
    paths_9x16: list[Path] = []
    total = len(slides)

    for idx, slide in enumerate(slides):
        img_9x16 = _render_single_slide(
            slide,
            idx,
            total,
            width=1080,
            height=1920,
            margin_left=CAROUSEL_4X5_SAFE_MARGIN_X,
            margin_right=170,
            top_y=240,
            bottom_anchor_y=1470,
            brand_label=brand_label,
            is_reel=True,
        )
        p9 = dir_9x16 / f"slide_{idx + 1:02d}.png"
        img_9x16.save(p9, format="PNG", optimize=True)
        paths_9x16.append(p9)

    reel_mp4 = render_reel_mp4_from_slides(
        paths_9x16,
        output_dir / "reel_9x16.mp4",
        slide_duration_sec=slide_duration_sec,
    )
    return {
        "carousel_4x5": [str(p) for p in paths_4x5],
        "reels_9x16": [str(p) for p in paths_9x16],
        "reel_mp4": str(reel_mp4),
    }


# ---------------------------------------------------------------------------
# Episode -> 6-Slide 4:5 Carousel Extractor (`0` extra Google Flow credits)
# ---------------------------------------------------------------------------


def _clean_plain_ascii_copy(text: str) -> str:
    cleaned = str(text or "")
    cleaned = cleaned.replace("—", ", ").replace("–", "-")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


_DANGLING_HEADLINE_END_WORDS = {
    "A", "AN", "THE", "OF", "TO", "IN", "ON", "AT", "BY", "FOR", "WITH", "FROM",
    "INTO", "UNTIL", "BECAUSE", "THAT", "WHICH", "WHO", "WHEN", "WHILE", "AND",
    "OR", "BUT", "YET", "SO", "AS", "IF", "HIS", "HER", "THEIR", "YOUR", "OUR", "MY",
    "OWN", "IS", "WAS", "WERE", "ARE", "BEEN", "ALSO",
}


def _derive_uppercase_headline(sentence: str, fallback: str, max_words: int = 6) -> str:
    s = _clean_plain_ascii_copy(sentence)
    if not s:
        return fallback.upper()
    # Preserve crisp episode titles / short questions intact when <= 42 chars
    if len(s) <= 42 and len(s.split()) <= 9:
        full_up = s.rstrip(".,;:").upper()
        if len(full_up) >= 8:
            return full_up

    s = re.sub(r"^(?:yet|but|however|meanwhile|instead|and|that['’]?s\s+because|because)\s*,?\s*", "", s, flags=re.IGNORECASE)
    s = re.sub(r"^after\s+a\s+[a-z0-9\-\s]{3,42}?,\s*(?:a\s+)?", "", s, flags=re.IGNORECASE)
    s = re.sub(r"^(?:on\s+[a-z\s]{3,20}?,\s*|scans\s+showed\s+)", "", s, flags=re.IGNORECASE)
    s = re.sub(r"^(?:(?:a|the)\s+)?patient\s+told\s+doctors\s+(?:that\s+)?", "", s, flags=re.IGNORECASE)
    # Convert spelled-out ratio phrases like "sixteen of seventeen cases" -> "16 OF 17 CASES" stays crisp if complete
    words = [re.sub(r"^[^A-Za-z0-9]+|[^A-Za-z0-9%'-]+$", "", w) for w in s.split()]
    words = [w for w in words if w]
    if len(words) < 3:
        return fallback.upper()
    picked_words = words[:max_words]
    while len(picked_words) > 3 and picked_words[-1].upper() in _DANGLING_HEADLINE_END_WORDS:
        picked_words.pop()
    picked = " ".join(picked_words).upper()
    return picked[:44].rstrip(" ,;:-") or fallback.upper()


def _grab_clean_clip_frame(clip_path: Path, out_png: Path, ratio: float = 0.46) -> bool:
    if not clip_path.is_file():
        return False
    try:
        import cv2  # local import so Pillow-only environments never fail on import

        cap = cv2.VideoCapture(str(clip_path))
        if not cap.isOpened():
            return False
        try:
            n_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
            target_idx = max(0, min(max(0, n_frames - 1), int(round(n_frames * ratio)))) if n_frames > 2 else 0
            if target_idx > 0:
                cap.set(cv2.CAP_PROP_POS_FRAMES, target_idx)
            ok, frame_bgr = cap.read()
            if not ok or frame_bgr is None:
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ok, frame_bgr = cap.read()
            if not ok or frame_bgr is None:
                return False
            rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
            out_png.parent.mkdir(parents=True, exist_ok=True)
            Image.fromarray(rgb).save(out_png, format="PNG")
            return True
        finally:
            cap.release()
    except Exception:
        return False


def _render_obsidian_cyan_fallback_bg(out_png: Path, *, variant: int = 0, dark_cyan_anchor: bool = False) -> Path:
    w, h = CAROUSEL_4X5_WIDTH, CAROUSEL_4X5_HEIGHT
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    cx = w * (0.50 if dark_cyan_anchor else (0.38 + 0.05 * (variant % 3)))
    cy = h * (0.34 if dark_cyan_anchor else 0.36)
    dist = np.sqrt(((xx - cx) / (w * 0.46)) ** 2 + ((yy - cy) / (h * 0.38)) ** 2)
    glow = np.clip(1.0 - dist, 0.0, 1.0) ** (1.8 if dark_cyan_anchor else 2.2)

    arr = np.zeros((h, w, 3), dtype=np.uint8)
    arr[..., 0] = np.clip(7 + glow * (16 if dark_cyan_anchor else 22), 0, 255).astype(np.uint8)
    arr[..., 1] = np.clip(12 + glow * (112 if dark_cyan_anchor else 86), 0, 255).astype(np.uint8)
    arr[..., 2] = np.clip(24 + glow * (158 if dark_cyan_anchor else 128), 0, 255).astype(np.uint8)
    out_png.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(arr, mode="RGB").save(out_png, format="PNG")
    return out_png


def _composite_data_stamp_on_slide_bg(
    base_bg: Path,
    project_path: Path,
    script_doc: dict[str, Any],
    out_png: Path,
) -> Path:
    """
    Composites an `R70-M` hand-drawn Data Stamp (`05_assembly/chart_previews/` or live RGBA render)
    into the upper visual hero window (`y = 140..640`) of Slide 04 so it stays 100% clear of the
    lower editorial headline/body block.
    """
    canvas = _fit_cover_image(base_bg, CAROUSEL_4X5_WIDTH, CAROUSEL_4X5_HEIGHT, vertical_bias=0.36)
    stamp_rgba: Image.Image | None = None

    preview_dir = project_path / "05_assembly" / "chart_previews"
    if preview_dir.is_dir():
        for cand in sorted(preview_dir.glob("*.png")):
            try:
                with Image.open(cand) as im:
                    if im.mode == "RGBA":
                        stamp_rgba = im.copy()
                        break
            except Exception:
                continue

    if stamp_rgba is None:
        raw_stamps = script_doc.get("data_stamps")
        if isinstance(raw_stamps, list) and raw_stamps and isinstance(raw_stamps[0], dict):
            try:
                from pipeline.data_stamp_overlay import render_data_stamp_rgba_frame

                stamp_rgba = render_data_stamp_rgba_frame(
                    raw_stamps[0],
                    3.5,
                    5.0,
                    width=1080,
                    height=1920,
                )
            except Exception:
                stamp_rgba = None

    if stamp_rgba is None:
        out_png.parent.mkdir(parents=True, exist_ok=True)
        canvas.convert("RGB").save(out_png, format="PNG")
        return out_png

    alpha_arr = np.asarray(stamp_rgba, dtype=np.uint8)[..., 3]
    ys, xs = np.where(alpha_arr > 8)
    if ys.size == 0 or xs.size == 0:
        out_png.parent.mkdir(parents=True, exist_ok=True)
        canvas.convert("RGB").save(out_png, format="PNG")
        return out_png

    crop_box = (
        max(0, int(xs.min()) - 16),
        max(0, int(ys.min()) - 16),
        min(stamp_rgba.width, int(xs.max()) + 16),
        min(stamp_rgba.height, int(ys.max()) + 16),
    )
    cropped = stamp_rgba.crop(crop_box)

    # Softly dim/blur upper hero window so hand-drawn strokes pop cleanly
    blurred = canvas.filter(ImageFilter.GaussianBlur(radius=8))
    dim_arr = (np.asarray(blurred, dtype=np.float32) * np.array([0.48, 0.50, 0.54, 1.0], dtype=np.float32)).astype(np.uint8)
    upper_bg = Image.fromarray(dim_arr, mode="RGBA")
    mask = Image.new("L", (CAROUSEL_4X5_WIDTH, CAROUSEL_4X5_HEIGHT), 0)
    mdraw = ImageDraw.Draw(mask)
    mdraw.rounded_rectangle((90, 140, 990, 645), radius=28, fill=225)
    mask = mask.filter(ImageFilter.GaussianBlur(radius=14))
    canvas = Image.composite(upper_bg, canvas, mask)

    max_w, max_h = 840, 460
    scale = min(max_w / max(1, cropped.width), max_h / max(1, cropped.height))
    nw = max(1, int(round(cropped.width * scale)))
    nh = max(1, int(round(cropped.height * scale)))
    resized_stamp = cropped.resize((nw, nh), Image.Resampling.LANCZOS)
    paste_x = (CAROUSEL_4X5_WIDTH - nw) // 2
    paste_y = 152 + max(0, (max_h - nh) // 2)
    canvas.alpha_composite(resized_stamp, dest=(paste_x, paste_y))

    out_png.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(out_png, format="PNG")
    return out_png


def extract_episode_carousel_slides(
    project_dir: Path | str,
    *,
    frames_dir: Path | None = None,
) -> list[CardSlide]:
    """
    Extracts a 6-slide `4:5` Instagram Carousel storyboard from an episode project at `0` extra Flow credits:
      - Slide 01 (`THE PARADOX`): Act 1 primary human hook cut + paradox hook headline
      - Slide 02 (`CLINICAL CASE`): Case setup human/exterior cut + real clinical case summary
      - Slide 03 (`INSIDE THE BRAIN`): `R78-M` `#27D8FF` 3D brain simulator cut + neural circuit mechanism
      - Slide 04 (`BROKEN RELAY · DATA`): 2nd brain cut or `R70-M` data-stamp composite + numeric finding/analogy
      - Slide 05 (`YOUR BRAIN DAILY`): Act 5/6 everyday insight cut + takeaway
      - Slide 06 (`PEER-REVIEWED SOURCE`): Dark-cyan brain anchor + debate question + `Study: ... · DOI: ...` + `SAVE & SHARE`
    """
    raw_p = Path(project_dir)
    p_dir = raw_p if raw_p.exists() or raw_p.is_absolute() else (PROJECTS_DIR / str(project_dir))
    if not p_dir.exists() and (PROJECTS_DIR / raw_p.name).exists():
        p_dir = PROJECTS_DIR / raw_p.name

    def _read_json(path: Path) -> dict[str, Any]:
        if not path.is_file():
            return {}
        try:
            d = json.loads(path.read_text(encoding="utf-8"))
            return d if isinstance(d, dict) else {}
        except Exception:
            return {}

    script_doc = _read_json(p_dir / "02_script" / "script.json")
    vp_doc = _read_json(p_dir / "03_visuals" / "visual_plan.json")
    meta_doc = _read_json(p_dir / "06_publish" / "metadata.json")
    res_doc = _read_json(p_dir / "01_research" / "research_packet.json")

    src_frames_dir = Path(frames_dir) if frames_dir is not None else (p_dir / "05_assembly" / "carousel_source_frames")
    src_frames_dir.mkdir(parents=True, exist_ok=True)

    # Parse sentences by index and act
    raw_sents = script_doc.get("sentences") or []
    sent_items: list[dict[str, Any]] = []
    for idx, item in enumerate(raw_sents, start=1):
        if isinstance(item, dict):
            txt = _clean_plain_ascii_copy(str(item.get("text") or item.get("narration") or ""))
            if txt:
                sent_items.append(
                    {
                        "sentence_index": int(item.get("sentence_index") or idx),
                        "act_id": int(item.get("act_id") or 0),
                        "text": txt,
                    }
                )
        elif isinstance(item, str) and item.strip():
            sent_items.append({"sentence_index": idx, "act_id": 0, "text": _clean_plain_ascii_copy(item)})

    def _sent_at(idx_1b: int, default: str) -> str:
        if 1 <= idx_1b <= len(sent_items):
            return sent_items[idx_1b - 1]["text"]
        return default

    # Map visual_plan clips into human/exterior vs 3D brain simulator cuts
    clips_dir = p_dir / "03_visuals" / "flow_native_clips"
    vp_clips = [c for c in (vp_doc.get("clips") or []) if isinstance(c, dict)]

    human_clip_indices: list[int] = []
    brain_clip_indices: list[int] = []
    for i, c in enumerate(vp_clips, start=1):
        c_idx = int(c.get("clip_index") or c.get("clip_number") or c.get("id") or i)
        cat = " ".join(
            str(c.get(k) or "")
            for k in ("scene_category", "grammar", "visual_grammar", "render_engine")
        ).strip().lower()
        is_brain = bool(c.get("brain_clip") is True) or ("brain_simulator" in cat) or ("brain_only" in cat) or ("blender" in cat)
        if is_brain:
            brain_clip_indices.append(c_idx)
        else:
            human_clip_indices.append(c_idx)

    if not human_clip_indices and clips_dir.is_dir():
        avail = sorted(
            int(m.group(1))
            for p in clips_dir.glob("clip_*.mp4")
            if (m := re.match(r"^clip_(\d+)\.mp4$", p.name))
        )
        human_clip_indices = avail

    all_avail = sorted(set(human_clip_indices + brain_clip_indices))

    # Pick 6 distinct clip indices across the episode arc (Human Hook -> Clinical Case -> 3D Brain -> Data Stamp -> Human Daily -> 3D Brain Finale)
    c_s1 = human_clip_indices[0] if human_clip_indices else 1
    c_s2 = human_clip_indices[min(2, len(human_clip_indices) - 1)] if len(human_clip_indices) >= 2 else 2
    c_s3 = brain_clip_indices[0] if brain_clip_indices else 3
    c_s4 = (
        human_clip_indices[min(4, len(human_clip_indices) - 1)]
        if len(human_clip_indices) >= 4
        else (brain_clip_indices[min(1, len(brain_clip_indices) - 1)] if len(brain_clip_indices) >= 2 else 4)
    )
    c_s5 = human_clip_indices[-1] if len(human_clip_indices) >= 3 else 5
    c_s6 = brain_clip_indices[-1] if brain_clip_indices else 6

    raw_picks = [c_s1, c_s2, c_s3, c_s4, c_s5, c_s6]
    chosen_clips: list[int] = []
    used_clips: set[int] = set()
    for idx_pick in raw_picks:
        if idx_pick not in used_clips:
            chosen_clips.append(idx_pick)
            used_clips.add(idx_pick)
        else:
            replacement = next((x for x in all_avail if x not in used_clips), idx_pick)
            chosen_clips.append(replacement)
            used_clips.add(replacement)

    # Candidate still image fallbacks if raw flow_native_clips are absent (e.g. unit tests)
    ref_dir = p_dir / "03_visuals" / "reference_images"
    still_fallbacks: list[Path] = []
    if ref_dir.is_dir():
        still_fallbacks.extend(sorted(ref_dir.glob("*.png")))
    for extra_img in (p_dir / "cover_src.png", p_dir / "06_publish" / "thumbnail_clean.png"):
        if extra_img.is_file():
            still_fallbacks.append(extra_img)

    bg_paths: list[Path] = []
    for slot_zero, clip_idx in enumerate(chosen_clips):
        out_frame = src_frames_dir / f"bg_slide_{slot_zero + 1:02d}.png"
        clip_mp4 = clips_dir / f"clip_{clip_idx}.mp4"
        if _grab_clean_clip_frame(clip_mp4, out_frame):
            bg_paths.append(out_frame)
        elif still_fallbacks and slot_zero < 5:
            fb_src = still_fallbacks[slot_zero % len(still_fallbacks)]
            with Image.open(fb_src) as im:
                im.convert("RGB").save(out_frame, format="PNG")
            bg_paths.append(out_frame)
        else:
            _render_obsidian_cyan_fallback_bg(
                out_frame,
                variant=slot_zero,
                dark_cyan_anchor=(slot_zero in (2, 5)),
            )
            bg_paths.append(out_frame)

    # Darken/tint Slide 06 into a rich dark-cyan brain anchor
    with Image.open(bg_paths[5]) as s6_im:
        s6_arr = np.asarray(s6_im.convert("RGB"), dtype=np.float32)
        s6_tinted = np.zeros_like(s6_arr)
        s6_tinted[..., 0] = np.clip(s6_arr[..., 0] * 0.42 + 6.0, 0, 255)
        s6_tinted[..., 1] = np.clip(s6_arr[..., 1] * 0.68 + 18.0, 0, 255)
        s6_tinted[..., 2] = np.clip(s6_arr[..., 2] * 0.82 + 32.0, 0, 255)
        Image.fromarray(s6_tinted.astype(np.uint8), mode="RGB").save(bg_paths[5], format="PNG")

    # Composite R70-M Data Stamp onto Slide 04 upper hero window when available
    bg_paths[3] = _composite_data_stamp_on_slide_bg(
        bg_paths[3],
        p_dir,
        script_doc,
        src_frames_dir / "bg_slide_04_stamped.png",
    )

    # Editorial text extraction per slide
    ep_title = _clean_plain_ascii_copy(
        str(meta_doc.get("title") or script_doc.get("title") or vp_doc.get("title") or p_dir.name.replace("_", " "))
    )
    s1_body = _sent_at(
        1,
        "A baffling real-world paradox reveals how two separate brain circuits build human reality.",
    )
    s1_head = _derive_uppercase_headline(ep_title or s1_body, "THE BRAIN PARADOX", max_words=6)

    act2_sents = [s["text"] for s in sent_items if s["act_id"] in (1, 2) and s["sentence_index"] >= 2]
    s2_body = (
        " ".join(act2_sents[:2])
        if act2_sents
        else _sent_at(2, "Doctors documented a striking clinical case where normal perception split cleanly in two.")
    )
    s2_body = _clean_plain_ascii_copy(s2_body)[:220]
    s2_head = _derive_uppercase_headline(act2_sents[0] if act2_sents else s2_body, "REAL CLINICAL CASE", max_words=5)

    core_idx = int(script_doc.get("core_reveal_sentence_index") or 0)
    act3_sents = [s["text"] for s in sent_items if s["act_id"] == 3]
    s3_body = (
        _sent_at(core_idx, "")
        or (" ".join(act3_sents[:2]) if act3_sents else "")
        or _sent_at(min(6, max(1, len(sent_items))), "Deep inside the cortex, a dedicated relay links sensory recognition to gut emotion.")
    )
    s3_body = _clean_plain_ascii_copy(s3_body)[:220]
    s3_head = _derive_uppercase_headline(s3_body, "INSIDE THE CIRCUIT", max_words=5)

    stamps = [st for st in (script_doc.get("data_stamps") or []) if isinstance(st, dict)]
    stamp0 = stamps[0] if stamps else {}
    stamp_s_idx = int(stamp0.get("sentence_index") or 0)
    act4_sents = [s["text"] for s in sent_items if s["act_id"] == 4]
    s4_body = (
        _sent_at(stamp_s_idx, "")
        or (" ".join(act4_sents[:2]) if act4_sents else "")
        or _sent_at(min(9, max(1, len(sent_items))), "Lab measurements confirmed the exact break between conscious recognition and automatic physiological response.")
    )
    s4_body = _clean_plain_ascii_copy(s4_body)[:220]
    stamp_title = _clean_plain_ascii_copy(str(stamp0.get("title") or stamp0.get("accent_Callout") or ""))
    s4_head = (
        stamp_title.upper()[:44]
        if stamp_title
        else _derive_uppercase_headline(s4_body, "MEASURED IN THE LAB", max_words=5)
    )

    act5_sents = [s["text"] for s in sent_items if s["act_id"] in (5, 6)]
    s5_body = (
        " ".join(act5_sents[:2])
        if act5_sents
        else _sent_at(max(1, len(sent_items) - 1), "Every day, your brain fuses identity with automatic emotional signals before you decide what feels real.")
    )
    s5_body = _clean_plain_ascii_copy(s5_body)[:220]
    s5_head = _derive_uppercase_headline(s5_body, "YOUR BRAIN EVERY DAY", max_words=5)

    raw_debate = _clean_plain_ascii_copy(
        str(
            meta_doc.get("debate_question")
            or script_doc.get("debate_question")
            or "When your eyes and your gut disagree, which signal do you trust first?"
        )
    )
    if not raw_debate.endswith("?"):
        raw_debate = raw_debate.rstrip(".!") + "?"

    doi = _clean_plain_ascii_copy(
        str(
            meta_doc.get("primary_doi")
            or meta_doc.get("doi")
            or script_doc.get("doi")
            or res_doc.get("primary_doi")
            or res_doc.get("doi")
            or ""
        )
    )
    doi = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", doi, flags=re.IGNORECASE).strip()

    study_short = _clean_plain_ascii_copy(str(stamp0.get("source_citation") or ""))
    if not study_short:
        desc = str(meta_doc.get("description") or script_doc.get("viewer_description") or "")
        m_res = re.search(r"^Research:\s*([^\n]+)", desc, flags=re.MULTILINE)
        if m_res:
            study_short = _clean_plain_ascii_copy(m_res.group(1)).rstrip(".")
        else:
            m_src = re.search(r"Primary Peer-Reviewed Sources:\s*\n-\s*([^()\n]+?\(\d{4}\))", desc)
            if m_src:
                study_short = _clean_plain_ascii_copy(m_src.group(1))
    if not study_short:
        study_short = "Peer-Reviewed Clinical Study"

    s6_footer = f"Study: {study_short} · DOI: {doi}" if doi else f"Study: {study_short}"

    slides = [
        CardSlide(
            tag="THE PARADOX",
            headline=s1_head,
            body=s1_body,
            bg_image=bg_paths[0],
        ),
        CardSlide(
            tag="CLINICAL CASE",
            headline=s2_head,
            body=s2_body,
            bg_image=bg_paths[1],
        ),
        CardSlide(
            tag="INSIDE THE BRAIN",
            headline=s3_head,
            body=s3_body,
            bg_image=bg_paths[2],
        ),
        CardSlide(
            tag="BROKEN RELAY · DATA",
            headline=s4_head,
            body=s4_body,
            bg_image=bg_paths[3],
        ),
        CardSlide(
            tag="YOUR BRAIN DAILY",
            headline=s5_head,
            body=s5_body,
            bg_image=bg_paths[4],
        ),
        CardSlide(
            tag="PEER-REVIEWED SOURCE",
            headline="TRUST YOUR EYES OR GUT?",
            body=raw_debate,
            bg_image=bg_paths[5],
            footer_note=s6_footer,
        ),
    ]
    for sl in slides:
        validate_slide_copy_safety(sl)
    return slides
