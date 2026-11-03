"""
ALL ABOUT BRAIN — 16:9 4K CTV Long-Form Chapter Plan Compiler (`pipeline/longform_prompt_builder.py`).

Compiles `07_longform_outline.json`, `dossier.json`, `01_sources.json`, and reusable clip intelligence from
`BCI_Shorts_Channel/knowledge_base/` (`R50-B`) into a native `16:9` `porcelain_cinematic_v7` (`R66`)
8–12 minute (`160–168 WPM`) documentary plan for living-room Smart TV (CTV) & YPP 4,000h watch-time growth.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pipeline.config import (
    DEFAULT_DIORAMA_VOICE_PRESET,
    DIORAMA_V7_US_PROSODY_MODE,
    DOSSIERS_DIR,
    FLOW_ASPECT_LONGFORM,
    LONGFORM_CHAPTER_FADE_SEC,
    LONGFORM_TARGET_LUFS,
    LONGFORM_VIDEO_FPS,
    LONGFORM_VIDEO_HEIGHT,
    LONGFORM_VIDEO_WIDTH,
    PORCELAIN_V7_CAST_STYLE,
    PORCELAIN_V7_OPTICS_LOCK,
    PORCELAIN_V7_STYLE_PROFILE,
    PORCELAIN_V7_WORLD_STYLE,
)
from pipeline.knowledge_hub import query_knowledge_base


def compile_longform_plan_from_dossier(
    slug_or_dir: str | Path,
    voice_preset: str = DEFAULT_DIORAMA_VOICE_PRESET,
    target_wpm: int = 164,
    save: bool = True,
) -> dict[str, Any]:
    d_dir = Path(slug_or_dir) if Path(slug_or_dir).is_dir() else (Path(DOSSIERS_DIR) / str(slug_or_dir))
    if not d_dir.exists():
        raise FileNotFoundError(f"Dossier directory not found: {d_dir}")

    dossier = json.loads((d_dir / "dossier.json").read_text(encoding="utf-8"))
    outline_path = d_dir / "07_longform_outline.json"
    if not outline_path.exists():
        raise FileNotFoundError(f"Missing 07_longform_outline.json in {d_dir}")
    outline = json.loads(outline_path.read_text(encoding="utf-8"))

    slug = str(dossier.get("slug") or d_dir.name)
    target_minutes = max(8, min(12, int(outline.get("target_minutes") or 10)))
    target_total_words = target_minutes * int(target_wpm)

    chapters_raw = list(outline.get("chapters") or [])
    n_ch = max(1, len(chapters_raw))
    words_per_chapter = max(180, target_total_words // n_ch)

    reusable_hits = query_knowledge_base(
        pack="clips",
        query=slug.replace("_", " "),
        style_profile=PORCELAIN_V7_STYLE_PROFILE,
        limit=16,
    )

    compiled_chapters: list[dict[str, Any]] = []
    clip_counter = 1
    for idx, ch in enumerate(chapters_raw, start=1):
        beats = list(ch.get("beats") or ["Historical setup", "Neural circuit mechanism", "Human consequence"])
        shots_needed = list(ch.get("new_shots_needed") or [])
        ch_clips: list[dict[str, Any]] = []
        for b_i, beat_txt in enumerate(beats):
            is_brain = (b_i == len(beats) - 1) or ("brain" in str(beat_txt).lower()) or ("cortex" in str(beat_txt).lower())
            grammar = "porcelain_living_brain" if is_brain else "porcelain_fullbleed_world"
            ch_clips.append(
                {
                    "clip_number": clip_counter,
                    "chapter_number": idx,
                    "aspect": FLOW_ASPECT_LONGFORM,
                    "style_profile": PORCELAIN_V7_STYLE_PROFILE,
                    "grammar": grammar,
                    "brain_mode": "sagittal_coronal_cutaway" if is_brain else None,
                    "camera": "gentle_push_in" if is_brain else "locked_tripod",
                    "beat_summary": str(beat_txt),
                    "prompt": (
                        f"Widescreen 16:9 4K architectural neuroscience documentary shot in {PORCELAIN_V7_WORLD_STYLE}. "
                        f"{PORCELAIN_V7_CAST_STYLE}. Beat: {beat_txt}. {PORCELAIN_V7_OPTICS_LOCK}"
                    ),
                }
            )
            clip_counter += 1
        for extra_shot in shots_needed[:2]:
            ch_clips.append(
                {
                    "clip_number": clip_counter,
                    "chapter_number": idx,
                    "aspect": FLOW_ASPECT_LONGFORM,
                    "style_profile": PORCELAIN_V7_STYLE_PROFILE,
                    "grammar": "porcelain_hands_closeup",
                    "camera": "macro_rack_focus",
                    "beat_summary": str(extra_shot),
                    "prompt": (
                        f"Widescreen 16:9 4K macro architectural documentary close-up in {PORCELAIN_V7_WORLD_STYLE}. "
                        f"Detail: {extra_shot}. {PORCELAIN_V7_OPTICS_LOCK}"
                    ),
                }
            )
            clip_counter += 1

        compiled_chapters.append(
            {
                "chapter_number": idx,
                "title": str(ch.get("title") or f"Chapter {idx}"),
                "target_words": words_per_chapter,
                "midroll_valley_after_sec": LONGFORM_CHAPTER_FADE_SEC if idx < n_ch else 0.0,
                "beats": beats,
                "clips": ch_clips,
            }
        )

    plan_doc: dict[str, Any] = {
        "schema": "longform_v7_porcelain_plan_v1",
        "slug": slug,
        "topic": dossier.get("topic"),
        "pillar": dossier.get("pillar"),
        "aspect": FLOW_ASPECT_LONGFORM,
        "resolution": [LONGFORM_VIDEO_WIDTH, LONGFORM_VIDEO_HEIGHT],
        "fps": LONGFORM_VIDEO_FPS,
        "target_lufs": LONGFORM_TARGET_LUFS,
        "style_profile": PORCELAIN_V7_STYLE_PROFILE,
        "prosody_mode": DIORAMA_V7_US_PROSODY_MODE,
        "voice_preset": voice_preset,
        "target_minutes": target_minutes,
        "target_wpm": target_wpm,
        "target_total_words": target_total_words,
        "reusable_kb_clips_found": len(reusable_hits),
        "chapters": compiled_chapters,
        "total_planned_clips": clip_counter - 1,
        "compiled_at": datetime.now(timezone.utc).isoformat(),
    }

    if save:
        out_dir = d_dir / "longform_v7_porcelain"
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "longform_plan.json").write_text(
            json.dumps(plan_doc, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    return plan_doc
