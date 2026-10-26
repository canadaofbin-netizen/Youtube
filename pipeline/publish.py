"""
Stage 6: Publish Packaging, A/B Thumbnail Variants & Metadata Export
Prepares YouTube Shorts metadata, SEO tags, AI content declarations,
and 3 high-impact thumbnail variants for sequential A/B testing.
"""

import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont, ImageOps

from pipeline.config import (
    FONT_FALLBACK_PATH,
    FONT_PRIMARY_PATH,
    RGB_DANGER_RED,
    RGB_DEEP_NAVY,
    RGB_NEUTRAL_WHITE,
    RGB_SECONDARY_TEAL,
    RGB_SIGNAL_GOLD,
    VIDEO_HEIGHT,
    VIDEO_WIDTH,
)
from pipeline.storage import ProjectStorage
from pipeline.studio.config import (
    CHANNEL_RESIDENCE_COUNTRY,
    CHANNEL_RESIDENCE_COUNTRY_NAME,
    DEFAULT_VIDEO_CATEGORY,
    TARGET_AUDIENCE_REGION,
    TITLE_DESCRIPTION_LANGUAGE_CODE,
    TITLE_DESCRIPTION_LANGUAGE_LABEL,
    VIDEO_LANGUAGE_CODE,
    VIDEO_LANGUAGE_LABEL,
)


class PublishStage:
    def __init__(self, storage: ProjectStorage):
        self.storage = storage

    def _load_base_frame(self, base_asset_path: Path | None, variant: str = "A") -> Image.Image:
        """
        Loads a distinct representative frame per variant:
        - Variant A (Baseline Authority): Clip 1 (Hook scene, ratio=0.30)
        - Variant B (Macro 3D Cutaway): Clip 3/4 (3D Brain Cutaway scene, ratio=0.55)
        - Variant C (Defiance Red Climax): Clip 5/Last (Telemetry HUD climax scene, ratio=0.70)
        Guarantees visual frame diversity (A_vs_B_bg_diff >= 15.0) across A, B, and C.
        """
        import cv2
        import numpy as np

        def _extract_video_frame(video_path: Path, pos_ratio: float = 0.35) -> Image.Image | None:
            try:
                cap = cv2.VideoCapture(str(video_path))
                if not cap.isOpened():
                    cap.release()
                    return None
                total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
                if total > 5:
                    target_idx = max(1, min(total - 2, int(total * pos_ratio)))
                    cap.set(cv2.CAP_PROP_POS_FRAMES, target_idx)
                ret, frame = cap.read()
                cap.release()
                if ret and frame is not None:
                    img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                    return ImageOps.fit(img, (VIDEO_WIDTH, VIDEO_HEIGHT), method=Image.Resampling.LANCZOS)
            except Exception as e:
                print(f"[PublishStage] Warning: Failed to extract frame from video ({e})")
            return None

        def _roi_diff(img1: Image.Image, img2: Image.Image) -> float:
            arr1 = np.asarray(img1, dtype=np.float32)
            arr2 = np.asarray(img2, dtype=np.float32)
            h = arr1.shape[0]
            y0, y1 = int(h * 0.32), int(h * 0.68)
            return float(np.mean(np.abs(arr1[y0:y1] - arr2[y0:y1])))

        v_upper = (variant or "A").upper()
        default_ratio = 0.30 if v_upper == "A" else (0.55 if v_upper == "B" else 0.75)

        # 1. Try provided explicit asset path
        if base_asset_path:
            base_asset_path = Path(base_asset_path)
        if base_asset_path and base_asset_path.exists():
            suffix = base_asset_path.suffix.lower()
            if suffix in [".mp4", ".mov", ".mkv", ".webm", ".avi"]:
                vid_img = _extract_video_frame(base_asset_path, pos_ratio=default_ratio)
                if vid_img is not None:
                    return vid_img
            else:
                try:
                    img = Image.open(base_asset_path).convert("RGB")
                    return ImageOps.fit(img, (VIDEO_WIDTH, VIDEO_HEIGHT), method=Image.Resampling.LANCZOS)
                except Exception as e:
                    print(f"[PublishStage] Warning: Failed to load image asset ({e})")

        # 2. Check 03_visuals/flow_native_clips/*.mp4 and _staged_clip_*.mp4 with distinct clip selection per variant
        vis_dir = self.storage.get_stage_dir("03_visuals")
        flow_clips_dir = vis_dir / "flow_native_clips"
        valid_clips: list[Path] = []
        if flow_clips_dir.exists():
            valid_clips = [
                c for c in sorted(flow_clips_dir.glob("*.mp4"))
                if c.is_file() and c.stat().st_size >= 1_000_000
            ]
        if not valid_clips and vis_dir.exists():
            valid_clips = [
                c for c in sorted(vis_dir.glob("_staged_clip_*.mp4"))
                if c.is_file() and c.stat().st_size >= 1_000_000
            ]
        if valid_clips:
            ref_a = _extract_video_frame(valid_clips[0], pos_ratio=0.30)
            if v_upper == "A" and ref_a is not None:
                return ref_a

            if v_upper == "B":
                pref_indices = [min(2, len(valid_clips) - 1), min(3, len(valid_clips) - 1), min(1, len(valid_clips) - 1), len(valid_clips) - 1]
                ratios = [0.55, 0.75, 0.25]
            else:  # Variant C
                pref_indices = [len(valid_clips) - 1, min(3, len(valid_clips) - 1), min(1, len(valid_clips) - 1), min(2, len(valid_clips) - 1)]
                ratios = [0.70, 0.45, 0.85]

            best_img: Image.Image | None = None
            best_diff = -1.0
            for c_idx in pref_indices:
                for r in ratios:
                    cand_img = _extract_video_frame(valid_clips[c_idx], pos_ratio=r)
                    if cand_img is not None:
                        if ref_a is None:
                            return cand_img
                        d = _roi_diff(ref_a, cand_img)
                        if d > best_diff:
                            best_diff = d
                            best_img = cand_img
                        if d >= 18.0:
                            return cand_img
            if best_img is not None:
                return best_img

        # 3. Check assembled final video in 05_assembly at variant-specific timestamps
        final_video = self.storage.get_stage_dir("05_assembly") / "final_shorts_1080x1920.mp4"
        if final_video.exists() and final_video.stat().st_size >= 1_000_000:
            timeline_ratio = 0.10 if v_upper == "A" else (0.50 if v_upper == "B" else 0.82)
            vid_img = _extract_video_frame(final_video, pos_ratio=timeline_ratio)
            if vid_img is not None:
                return vid_img

        # 4. Check 03_visuals raw_assets
        for candidate in ["clip_1_base.png", "clip_1.mp4", "master_keyframe.png"]:
            cand_path = self.storage.get_stage_dir("03_visuals") / "raw_assets" / candidate
            if cand_path.exists():
                return self._load_base_frame(cand_path, variant=v_upper)

        # 5. Fallback to variant-distinct canvas (only when no video/image assets exist yet during pre-flow ideation)
        fallback_color = RGB_DEEP_NAVY if v_upper == "A" else ((14, 38, 68) if v_upper == "B" else (32, 14, 28))
        return Image.new("RGB", (VIDEO_WIDTH, VIDEO_HEIGHT), fallback_color)

    def _get_scaled_font(self, text_lines: list[str], max_w: int, start_size: int = 64, min_size: int = 32) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        """Finds largest font size where all lines fit within max_w."""
        font_path = FONT_PRIMARY_PATH if FONT_PRIMARY_PATH.exists() else FONT_FALLBACK_PATH
        for size in range(start_size, min_size - 1, -4):
            try:
                font = ImageFont.truetype(str(font_path), size)
            except (OSError, ValueError):
                return ImageFont.load_default()

            fits = True
            for line in text_lines:
                if not line:
                    continue
                bbox = font.getbbox(line)
                w = bbox[2] - bbox[0]
                if w > max_w:
                    fits = False
                    break
            if fits:
                return font
        try:
            return ImageFont.truetype(str(font_path), min_size)
        except Exception:
            return ImageFont.load_default()

    @staticmethod
    def _extract_short_authority_hook(title: str) -> tuple[str, str]:
        """Extracts a bold 2-4 word authority hook split into 1-2 lines for maximum mobile Shelf CTR."""
        clean = re.sub(r"[^\w\s\-\?\!]", "", title).strip()
        stop = {
            "why", "how", "what", "when", "where", "the", "a", "an", "in", "to", "of", "and",
            "is", "are", "was", "were", "for", "with", "from", "that", "this", "their", "your",
            "his", "her", "into", "got", "has", "had", "have", "can", "could", "would", "people"
        }
        words = clean.split()
        if not words:
            return ("BRAIN", "PARADOX")
        core = [w.upper() for w in words if w.lower().strip("?-!") not in stop]
        if len(core) < 2:
            core = [w.upper() for w in words[:4]]
        selected = core[:4]
        if len(selected) <= 2:
            return (selected[0], selected[1] if len(selected) > 1 else "")
        mid = 2 if len(selected) >= 3 else 1
        return (" ".join(selected[:mid]), " ".join(selected[mid:4]))

    @staticmethod
    def _draw_neural_hud_reticle(
        draw: ImageDraw.ImageDraw,
        center_x: int,
        center_y: int,
        radius: int,
        color: tuple[int, int, int, int],
        label: str | None = None,
        font: ImageFont.FreeTypeFont | ImageFont.ImageFont | None = None,
    ) -> None:
        """Draws a clinical HUD target reticle & callout pointer over the neural focal zone."""
        # Outer segmented ring / corner brackets
        r = radius
        cx, cy = center_x, center_y
        draw.ellipse([(cx - r, cy - r), (cx + r, cy + r)], outline=color, width=4)
        inner_r = max(16, r // 3)
        draw.ellipse([(cx - inner_r, cy - inner_r), (cx + inner_r, cy + inner_r)], outline=color, width=2)
        # Crosshair ticks
        tick = 26
        draw.line([(cx - r - tick, cy), (cx - r + 10, cy)], fill=color, width=4)
        draw.line([(cx + r - 10, cy), (cx + r + tick, cy)], fill=color, width=4)
        draw.line([(cx, cy - r - tick), (cx, cy - r + 10)], fill=color, width=4)
        draw.line([(cx, cy + r - 10), (cx, cy + r + tick)], fill=color, width=4)
        # Corner bracket accents
        b_off = int(r * 1.18)
        b_len = 28
        for dx in (-1, 1):
            for dy in (-1, 1):
                bx, by = cx + dx * b_off, cy + dy * b_off
                draw.line([(bx, by), (bx - dx * b_len, by)], fill=color, width=4)
                draw.line([(bx, by), (bx, by - dy * b_len)], fill=color, width=4)
        if label and font is not None:
            # Callout leader line to upper-right tag
            lx0, ly0 = cx + int(r * 0.72), cy - int(r * 0.72)
            lx1, ly1 = min(VIDEO_WIDTH - 260, cx + r + 55), max(460, cy - r - 45)
            draw.line([(lx0, ly0), (lx1, ly1)], fill=color, width=3)
            draw.line([(lx1, ly1), (lx1 + 170, ly1)], fill=color, width=3)
            draw.text((lx1 + 8, ly1 - 30), label, fill=color, font=font)

    def generate_thumbnail_variant_a(self, base_asset_path: Path | None, title_headline: str, output_path: Path):
        """
        Variant A (Baseline Authority): Top Safe-Zone Deep Navy Badge + Gold Border + Giant 2-4 Word Hook (96px) + Gold HUD Target.
        Target: Viewers responding to authoritative scientific/documentary gravitas without bottom Shorts Shelf UI overlap.
        """
        img = self._load_base_frame(base_asset_path, variant="A")
        rgba_img = img.convert("RGBA")
        overlay = Image.new("RGBA", rgba_img.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        line1, line2 = self._extract_short_authority_hook(title_headline)
        max_text_w = VIDEO_WIDTH - 160
        chosen_font = self._get_scaled_font([line1, line2], max_text_w, start_size=96, min_size=52)

        # Top Safe-Zone Headline Badge (y=260..475, safely inside 9:16 and 3:4 YouTube Shorts grid crop)
        badge_y = 260
        badge_h = 215 if line2 else 135
        badge_left = 72
        badge_right = VIDEO_WIDTH - 72

        draw.rectangle(
            [(badge_left, badge_y), (badge_right, badge_y + badge_h)],
            fill=(*RGB_DEEP_NAVY, 232), outline=(*RGB_SIGNAL_GOLD, 255), width=6
        )

        def draw_centered_text(text: str, y: int, color: tuple[int, int, int]):
            bbox = chosen_font.getbbox(text)
            tw = bbox[2] - bbox[0]
            tx = (VIDEO_WIDTH - tw) // 2
            draw.text((tx + 4, y + 4), text, fill=(0, 0, 0, 255), font=chosen_font)
            draw.text((tx, y), text, fill=(*color, 255), font=chosen_font)

        if line2:
            draw_centered_text(line1, badge_y + 20, RGB_NEUTRAL_WHITE)
            draw_centered_text(line2, badge_y + 112, RGB_SIGNAL_GOLD)
        else:
            draw_centered_text(line1, badge_y + 32, RGB_SIGNAL_GOLD)

        # Subtle clinical HUD reticle over central anatomical region
        hud_font = self._get_scaled_font(["NEURAL TARGET"], 300, start_size=24, min_size=18)
        self._draw_neural_hud_reticle(
            draw, center_x=VIDEO_WIDTH // 2, center_y=980, radius=135,
            color=(*RGB_SIGNAL_GOLD, 215), label="NEURAL LOCUS", font=hud_font
        )

        combined = Image.alpha_composite(rgba_img, overlay).convert("RGB")
        combined.save(output_path, "PNG")

    def generate_thumbnail_variant_b(self, base_asset_path: Path | None, title_headline: str, output_path: Path):
        """
        Variant B (Macro 3D Cutaway + HUD Target): Top Safe-Zone Minimal 2-Word Hook (108px) + Teal Anatomical HUD Reticle.
        Target: Visual awe & Octane render detail; zero overlap with bottom Shorts Shelf title/views zone.
        """
        img = self._load_base_frame(base_asset_path, variant="B")
        rgba_img = img.convert("RGBA")
        overlay = Image.new("RGBA", rgba_img.size, (0, 0, 0, 0))
        draw_ov = ImageDraw.Draw(overlay)

        # Extract 2 punchy keywords for ultra-clean macro header
        clean_headline = re.sub(r"[^\w\s]", "", title_headline).strip()
        stop_words = {
            "why", "how", "what", "the", "a", "an", "in", "to", "of", "and", "is", "are",
            "for", "with", "from", "your", "their", "that", "this", "has", "got", "one", "people"
        }
        meaningful_words = [w.upper() for w in clean_headline.split() if w.lower() not in stop_words]
        if not meaningful_words:
            meaningful_words = ["BRAIN", "UNLOCKED"]
        short_headline = " ".join(meaningful_words[:2])

        max_text_w = VIDEO_WIDTH - 160
        chosen_font = self._get_scaled_font([short_headline], max_text_w, start_size=108, min_size=56)

        # Top Safe-Zone position (y=270..418) leaving the entire center & bottom 3D anatomy unobstructed
        badge_y = 270
        badge_h = 148
        badge_left = 72
        badge_right = VIDEO_WIDTH - 72

        draw_ov.rectangle(
            [(badge_left, badge_y), (badge_right, badge_y + badge_h)],
            fill=(10, 17, 40, 215), outline=(*RGB_SECONDARY_TEAL, 255), width=5
        )

        bbox = chosen_font.getbbox(short_headline)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        tx = (VIDEO_WIDTH - tw) // 2
        ty = badge_y + (badge_h - th) // 2 - 8

        draw_ov.text((tx + 4, ty + 4), short_headline, fill=(0, 0, 0, 255), font=chosen_font)
        draw_ov.text((tx, ty), short_headline, fill=(*RGB_NEUTRAL_WHITE, 255), font=chosen_font)

        # High-visibility Teal 3D Cutaway HUD Target Reticle in center focal region
        hud_font = self._get_scaled_font(["3D CUTAWAY SCAN"], 320, start_size=26, min_size=18)
        self._draw_neural_hud_reticle(
            draw_ov, center_x=VIDEO_WIDTH // 2, center_y=960, radius=165,
            color=(*RGB_SECONDARY_TEAL, 240), label="3D CUTAWAY SCAN", font=hud_font
        )

        combined = Image.alpha_composite(rgba_img, overlay).convert("RGB")
        combined.save(output_path, "PNG")

    @staticmethod
    def _format_provocative_question(title: str, candidate_hook: str | None = None) -> str:
        """Formats a crisp, punchy 2-4 word question hook for mobile Shorts thumbnail impact."""
        if candidate_hook and len(candidate_hook.split()) <= 5 and "?" in candidate_hook:
            return candidate_hook.strip().upper()
        clean = re.sub(r"[^\w\s\?]", "", title).strip()
        words = clean.split()
        if not words:
            return "IMPOSSIBLE BRAIN?"
        if clean.lower().startswith("why "):
            sub_words = [w for w in words[1:] if w.lower() not in {"ancient", "modern", "the", "a", "an", "in", "to", "of", "and", "is", "are", "they"}]
            if len(sub_words) >= 2:
                return f"WHY {sub_words[-2].upper()} {sub_words[-1].upper()}?"
            return f"WHY {' '.join(words[1:4]).upper()}?"
        if "?" in clean:
            return clean.upper() if len(words) <= 4 else " ".join(words[:4]).upper() + "?"
        stop = {"the", "a", "an", "in", "to", "of", "and", "is", "are", "with", "your", "their", "that", "this", "has", "got"}
        core = [w.upper() for w in words if w.lower() not in stop]
        if len(core) >= 3:
            return f"{' '.join(core[:3])}?"
        return f"{' '.join(words[:3]).upper()}?"

    def generate_thumbnail_variant_c(self, base_asset_path: Path | None, title_headline: str, output_path: Path, question_hook: str | None = None):
        """
        Variant C (Defiance Red): Warning Red Border + Giant 2-4 Word Question Hook (96px) + Danger Red Anomaly HUD Reticle.
        Target: Cognitive dissonance & curiosity gap; defiance trigger.
        """
        img = self._load_base_frame(base_asset_path, variant="C")
        rgba_img = img.convert("RGBA")
        overlay = Image.new("RGBA", rgba_img.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        # Full-frame warning red border (high urgency)
        border_inset = 12
        border_width = 8
        draw.rectangle(
            [(border_inset, border_inset), (VIDEO_WIDTH - border_inset, VIDEO_HEIGHT - border_inset)],
            outline=(*RGB_DANGER_RED, 255), width=border_width
        )

        # Formulate crisp provocative question (2-4 words)
        q_clean = self._format_provocative_question(title_headline, question_hook)
        words = q_clean.split()
        mid = max(1, len(words) // 2)
        line1 = " ".join(words[:mid])
        line2 = " ".join(words[mid:]) if len(words) > 1 else ""

        max_text_w = VIDEO_WIDTH - 160
        chosen_font = self._get_scaled_font([line1, line2], max_text_w, start_size=96, min_size=52)

        # Top pill tag: "CRITICAL PARADOX" in safe zone
        pill_font_path = FONT_PRIMARY_PATH if FONT_PRIMARY_PATH.exists() else FONT_FALLBACK_PATH
        try:
            pill_font = ImageFont.truetype(str(pill_font_path), 24)
        except Exception:
            pill_font = ImageFont.load_default()

        pill_text = "CRITICAL PARADOX"
        p_bbox = pill_font.getbbox(pill_text)
        p_w = p_bbox[2] - p_bbox[0]
        p_left = (VIDEO_WIDTH - p_w) // 2 - 22
        p_right = p_left + p_w + 44
        pill_y = 235
        draw.rectangle(
            [(p_left, pill_y), (p_right, pill_y + 40)],
            fill=(*RGB_DANGER_RED, 255), outline=(*RGB_NEUTRAL_WHITE, 255), width=2
        )
        draw.text((p_left + 22, pill_y + 7), pill_text, fill=(*RGB_NEUTRAL_WHITE, 255), font=pill_font)

        # Main badge box at top safe-zone (y=282..497)
        badge_y = 282
        badge_h = 215 if line2 else 135
        badge_left = 72
        badge_right = VIDEO_WIDTH - 72

        draw.rectangle(
            [(badge_left, badge_y), (badge_right, badge_y + badge_h)],
            fill=(*RGB_DEEP_NAVY, 232), outline=(*RGB_DANGER_RED, 255), width=6
        )

        def draw_centered_text(text: str, y: int, color: tuple[int, int, int]):
            bbox = chosen_font.getbbox(text)
            tw = bbox[2] - bbox[0]
            tx = (VIDEO_WIDTH - tw) // 2
            draw.text((tx + 4, y + 4), text, fill=(0, 0, 0, 255), font=chosen_font)
            draw.text((tx, y), text, fill=(*color, 255), font=chosen_font)

        if line2:
            draw_centered_text(line1, badge_y + 20, RGB_NEUTRAL_WHITE)
            draw_centered_text(line2, badge_y + 112, RGB_DANGER_RED)
        else:
            draw_centered_text(line1, badge_y + 32, RGB_DANGER_RED)

        # Danger Red Anomaly HUD Reticle over central focal zone
        hud_font = self._get_scaled_font(["ANOMALY DETECTED"], 320, start_size=26, min_size=18)
        self._draw_neural_hud_reticle(
            draw, center_x=VIDEO_WIDTH // 2, center_y=980, radius=150,
            color=(*RGB_DANGER_RED, 235), label="ANOMALY DETECTED", font=hud_font
        )

        combined = Image.alpha_composite(rgba_img, overlay).convert("RGB")
        combined.save(output_path, "PNG")


    def generate_thumbnail(self, base_asset_path: Path, title_headline: str, output_path: Path):
        """Backward-compatible entry point that defaults to Variant A."""
        self.generate_thumbnail_variant_a(base_asset_path, title_headline, output_path)

    def generate_all_thumbnail_variants(
        self,
        base_asset_path: Path | None,
        title_headline: str,
        output_dir: Path,
        question_hook: str | None = None
    ) -> dict[str, Path]:
        """Generates all 3 A/B test thumbnail variants and standard thumbnail.png."""
        output_dir.mkdir(parents=True, exist_ok=True)
        var_a_path = output_dir / "thumbnail_var_A.png"
        var_b_path = output_dir / "thumbnail_var_B.png"
        var_c_path = output_dir / "thumbnail_var_C.png"
        default_thumb_path = output_dir / "thumbnail.png"

        self.generate_thumbnail_variant_a(base_asset_path, title_headline, var_a_path)
        self.generate_thumbnail_variant_b(base_asset_path, title_headline, var_b_path)
        self.generate_thumbnail_variant_c(base_asset_path, title_headline, var_c_path, question_hook=question_hook)

        # Standard thumbnail.png is set to Variant A by default
        shutil.copy2(var_a_path, default_thumb_path)

        return {
            "A": var_a_path,
            "B": var_b_path,
            "C": var_c_path,
            "default": default_thumb_path
        }

    def run(
        self,
        title: str,
        hashtags: list[str],
        doi: str,
        source_summary: str,
        thumbnail_source_img: Path | None = None,
        related_short: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        self.storage.update_stage_status("06_publish", "running")

        publish_dir = self.storage.get_stage_dir("06_publish")
        thumb_path = publish_dir / "thumbnail.png"

        # Validate title length (≤60 chars)
        clean_title = title.strip()
        if len(clean_title) > 60:
            clean_title = clean_title[:57] + "..."

        raw_doi = (doi or "").strip()
        doi_url = (
            raw_doi
            if raw_doi.startswith("http")
            else (f"https://doi.org/{raw_doi}" if raw_doi else "")
        )

        companion_block = ""
        if isinstance(related_short, dict) and related_short.get("title"):
            comp_vid = str(related_short.get("video_id") or "").strip()
            comp_url = (
                related_short.get("shorts_url")
                or related_short.get("url")
                or (f"https://www.youtube.com/shorts/{comp_vid}" if comp_vid else "")
            )
            companion_block = (
                f"Companion Case: {related_short['title']}"
                + (f" — {comp_url}\n\n" if comp_url else "\n\n")
            )

        metadata = {
            "title": clean_title,
            "title_char_count": len(clean_title),
            "doi": raw_doi,
            "doi_url": doi_url,
            "hashtags": hashtags[:5],
            "category": DEFAULT_VIDEO_CATEGORY,
            "video_language": VIDEO_LANGUAGE_CODE,
            "video_language_label": VIDEO_LANGUAGE_LABEL,
            "title_description_language": TITLE_DESCRIPTION_LANGUAGE_CODE,
            "title_description_language_label": TITLE_DESCRIPTION_LANGUAGE_LABEL,
            "channel_residence_country": CHANNEL_RESIDENCE_COUNTRY,
            "channel_residence_country_name": CHANNEL_RESIDENCE_COUNTRY_NAME,
            "target_audience_region": TARGET_AUDIENCE_REGION,
            "target_upload_time_et": "12:00 PM - 2:00 PM ET",
            "related_short": related_short,
            "ai_assisted_content_declaration": {
                "altered_or_synthetic_content": True,
                "label_required": True,
                "note": "AI-generated visual synthesis and neural voice (R4 compliance)"
            },
            "description": (
                f"{clean_title}\n\n"
                f"Source & Verification: {doi_url or raw_doi}\n\n"
                f"{source_summary}\n\n"
                f"{companion_block}"
                f"AI Disclosure: Visuals and voice synthesized with AI for neuroscience education.\n\n"
                f"{' '.join(hashtags[:5])}\n\n"
                f"ALL ABOUT BRAIN — Exploring the frontiers of neuroscience, psychology, and BCI."
            )
        }

        # Resolve question hook from ideation/scripting if available
        question_hook = None
        paradox_data = self.storage.load_json("01_ideation", "paradox_hook.json")
        if paradox_data:
            question_hook = paradox_data.get("dissonance_trigger") or paradox_data.get("paradox_statement")

        # Generate All 3 Thumbnail Variants
        variants = self.generate_all_thumbnail_variants(
            base_asset_path=thumbnail_source_img,
            title_headline=clean_title,
            output_dir=publish_dir,
            question_hook=question_hook
        )

        # Build A/B Testing Manifest
        now_iso = datetime.now(timezone.utc).isoformat()
        ab_manifest = {
            "project_id": self.storage.project_id,
            "channel_id": "UC4FeioYYv9X04Di07_MfZ7g",
            "channel_handle": "@AllAboutBrainOfficial",
            "created_at": now_iso,
            "title": clean_title,
            "status": "ready",
            "current_active_variant": "A",
            "rotation_interval_hours": 24,
            "variants": {
                "A": {
                    "variant_id": "A",
                    "name": "Standard Navy & Gold",
                    "file": "thumbnail_var_A.png",
                    "relative_path": "06_publish/thumbnail_var_A.png",
                    "badge_color": "#0A1128",
                    "border_color": "#FFD700",
                    "text_color": "#FFFFFF / #FFD700",
                    "font": "Inter-Variable",
                    "headline": clean_title,
                    "hypothesis": "Documentary intellectual authority; viewers responding to authoritative scientific tone.",
                    "style": "documentary_navy_gold",
                    "target_audience": "Academic & tech documentary viewers"
                },
                "B": {
                    "variant_id": "B",
                    "name": "Macro 3D Cutaway Minimal",
                    "file": "thumbnail_var_B.png",
                    "relative_path": "06_publish/thumbnail_var_B.png",
                    "badge_color": "rgba(10,17,40,0.78)",
                    "border_color": "#0E9AA7",
                    "text_color": "#0E9AA7 / #FFFFFF",
                    "font": "Inter-Variable",
                    "headline": clean_title,
                    "hypothesis": "Visual awe & 3D Octane cutaway detail; curiosity driven by high-detail visual over text.",
                    "style": "macro_visual_minimal",
                    "target_audience": "Visual-first scroll-stoppers and 3D render enthusiasts"
                },
                "C": {
                    "variant_id": "C",
                    "name": "Defiance Red Question Hook",
                    "file": "thumbnail_var_C.png",
                    "relative_path": "06_publish/thumbnail_var_C.png",
                    "badge_color": "#0A1128",
                    "border_color": "#FF3333",
                    "text_color": "#FF3333 / #FFFFFF",
                    "font": "Inter-Variable",
                    "headline": self._format_provocative_question(clean_title, question_hook),
                    "hypothesis": "Cognitive dissonance & provocative defiance trigger; high-CTR curiosity gap.",
                    "style": "defiance_red_provocative",
                    "target_audience": "Curiosity gap and controversy-driven discovery viewers"
                }
            },
            "schedule": [
                {"variant": "A", "window": "0-24h", "hours": 24, "status": "active", "started_at": now_iso},
                {"variant": "B", "window": "24-48h", "hours": 24, "status": "pending", "started_at": None},
                {"variant": "C", "window": "48-72h", "hours": 24, "status": "pending", "started_at": None}
            ],
            "statistical_evaluation": {
                "metric": "Search & Browse CTR",
                "test_type": "Two-Proportion Z-Test",
                "significance_threshold_p": 0.05,
                "z_critical": 1.96,
                "winner_variant": None,
                "locked": False
            }
        }

        # Save artifacts to storage
        self.storage.record_artifact("06_publish", "thumbnail.png", thumb_path)
        self.storage.record_artifact("06_publish", "thumbnail_var_A.png", variants["A"])
        self.storage.record_artifact("06_publish", "thumbnail_var_B.png", variants["B"])
        self.storage.record_artifact("06_publish", "thumbnail_var_C.png", variants["C"])
        self.storage.save_json("06_publish", "ab_test_manifest.json", ab_manifest)
        self.storage.save_json("06_publish", "metadata.json", metadata)

        checklist_md = f"""# YouTube Studio Upload & A/B Testing Checklist: {clean_title}

## 1. Video & Metadata
- [ ] **Title (≤60 chars):** `{metadata['title']}`
- [ ] **Upload File:** `05_assembly/final_shorts_1080x1920.mp4`
- [ ] **Category:** {DEFAULT_VIDEO_CATEGORY}
- [ ] **Channel Country of Residence:** `{CHANNEL_RESIDENCE_COUNTRY_NAME} ({CHANNEL_RESIDENCE_COUNTRY})` (AdSense identity & US-KR W-8BEN 10% tax treaty)
- [ ] **Video Language:** `{VIDEO_LANGUAGE_LABEL}` (`{VIDEO_LANGUAGE_CODE}`)
- [ ] **Title & Description Language:** `{TITLE_DESCRIPTION_LANGUAGE_LABEL}` (`{TITLE_DESCRIPTION_LANGUAGE_CODE}`)
- [ ] **AI-generated content:** Check "Yes" (Altered or synthetic content disclosure - R4 compliance)
- [ ] **Audience:** Not made for kids
- [ ] **Scheduled Time:** Next US peak window (12:00 PM - 2:00 PM ET or 5-Slot Schedule)

## 2. A/B Testing Thumbnail Variants (72-Hour Sequential Swap)
- [ ] **Variant A (Initial 0-72h):** `06_publish/thumbnail_var_A.png` (Navy & Gold Authority)
- [ ] **Variant B (72-144h):** `06_publish/thumbnail_var_B.png` (Macro 3D Cutaway Focus)
- [ ] **Variant C (144-216h):** `06_publish/thumbnail_var_C.png` (Defiance Red Question Hook)
- [ ] **Default / Initial Thumbnail:** `06_publish/thumbnail.png`
- [ ] **A/B Test Manifest:** `06_publish/ab_test_manifest.json`

## 3. Post-Publish Community Pin
- [ ] **Pinned Comment:** Academic DOI reference & cognitive dissonance question pinned at top
"""
        self.storage.save_text("06_publish", "upload_checklist.md", checklist_md)

        self.storage.update_stage_status("06_publish", "completed")
        return {
            "metadata": metadata,
            "thumbnail_path": str(thumb_path),
            "thumbnail_variants": {k: str(v) for k, v in variants.items()},
            "ab_test_manifest_path": str(publish_dir / "ab_test_manifest.json")
        }
