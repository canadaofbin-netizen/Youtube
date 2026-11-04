"""
ALL ABOUT BRAIN — Standalone 16:9 (`1920x1080`) Long-Form Publish & Debate Package Builder
(`pipeline/longform_publish.py`).

Stages `06_publish/metadata.json` (`00:00` YouTube chapter timestamps, 3-layer DOI bibliography, `R4` AI disclosure,
`upload_cc_srt: False` by default), `< 2 MB` `1920x1080` `thumbnail_var_{A,B,C}.jpg` (`Test & Compare`),
and the 3-Stage Comment Debate Ignition `06_publish/prepared_comment.json`.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pipeline.config import (
    AI_DISCLOSURE_SENTENCE,
    CHANNEL_HANDLE,
    FLOW_ASPECT_LONGFORM,
    LONGFORM_UPLOAD_CC_SRT_DEFAULT,
    LONGFORM_VIDEO_HEIGHT,
    LONGFORM_VIDEO_WIDTH,
)
from pipeline.longform_prompt_builder import resolve_longform_project_dir
from pipeline.studio.community import CommunityManager, validate_debate_pinned_comment_line1
from pipeline.thumbnail_studio import render_longform_thumbnails


def prepare_longform_publish_package(
    project_id_or_dir: str | Path,
    *,
    hook_text: str | None = None,
    upload_cc_srt: bool = LONGFORM_UPLOAD_CC_SRT_DEFAULT,
) -> dict[str, Any]:
    """Generates `06_publish/metadata.json`, `thumbnail_var_{A,B,C}.jpg`, and `prepared_comment.json`."""
    p_dir = resolve_longform_project_dir(project_id_or_dir, create=False)
    script_doc = json.loads((p_dir / "02_script" / "script.json").read_text(encoding="utf-8"))
    vp_doc = json.loads((p_dir / "03_visuals" / "visual_plan.json").read_text(encoding="utf-8"))
    pub_dir = p_dir / "06_publish"
    pub_dir.mkdir(parents=True, exist_ok=True)

    title = str(script_doc.get("title") or vp_doc.get("title") or p_dir.name).strip()
    domain = str(script_doc.get("everyday_domain") or vp_doc.get("everyday_domain") or "sleep").strip().capitalize()
    eff_hook = str(
        hook_text
        or (vp_doc.get("thumbnail") or {}).get("hook_text")
        or "60% BRAIN WASH"
    ).strip()

    chapters = list(script_doc.get("chapters") or vp_doc.get("chapters") or [])
    chapter_lines: list[str] = []
    running_est = 0.0
    for idx, ch in enumerate(chapters):
        ts = ch.get("youtube_timestamp")
        if not ts:
            if idx == 0:
                ts = "00:00"
            else:
                mm = int(running_est // 60)
                ss = int(round(running_est % 60))
                if ss >= 60:
                    mm += 1
                    ss = 0
                ts = f"{mm:02d}:{ss:02d}"
        running_est += max(55.0, float(ch.get("word_count") or 180) / 2.42)
        chapter_lines.append(f"{ts} {ch['title']}")
    if not chapter_lines or not chapter_lines[0].startswith("00:00"):
        chapter_lines.insert(0, "00:00 Cold Open")

    citations = list(vp_doc.get("citation_cards") or script_doc.get("citation_cards") or [])
    cite_lines = [
        f"• {c.get('authors')} ({c.get('year')}), {c.get('journal')} — {c.get('finding')} (https://doi.org/{c.get('doi')})"
        for c in citations
        if c.get("doi")
    ]

    lead_sents = [str(s.get("text") or "") for s in (script_doc.get("sentences") or [])[:3]]
    lead_summary = " ".join(lead_sents).strip()

    description = "\n".join(
        [
            lead_summary,
            "",
            "CHAPTERS:",
            *chapter_lines,
            "",
            "PEER-REVIEWED NEUROSCIENCE & PSYCHOLOGY SOURCES:",
            *(cite_lines or [f"• Primary Study: https://doi.org/{script_doc.get('doi', '')}"]),
            "",
            f"Subscribe to {CHANNEL_HANDLE} for weekly behavioral psychology & circuit neuroscience documentaries.",
            AI_DISCLOSURE_SENTENCE,
            f"#Neuroscience #Psychology #{domain} #BrainScience",
        ]
    ).strip()

    import cv2

    ref_frames = []
    ref_dir = p_dir / "03_visuals" / "reference_images"
    if ref_dir.is_dir():
        ref_pngs = sorted(ref_dir.glob("*.png"))
        if len(ref_pngs) >= 3:
            brain_pngs = [p for p in ref_pngs if "brain" in p.stem]
            room_pngs = [p for p in ref_pngs if "brain" not in p.stem]
            for rp in (brain_pngs[:1] + room_pngs[:2] + ref_pngs)[:3]:
                im = cv2.imread(str(rp))
                if im is not None:
                    ref_frames.append(im)

    thumb_rep = render_longform_thumbnails(p_dir, frames_bgr=ref_frames or None, hook_text=eff_hook)

    cm = CommunityManager(projects_dir=p_dir.parent)
    comm_doc = cm.stage_prepared_comment(p_dir.name)
    staged_comm_path = pub_dir / "prepared_comment.json"
    line1 = comm_doc["comment_text"].splitlines()[0].strip()
    comm_issues = validate_debate_pinned_comment_line1(line1, full_comment=comm_doc["comment_text"])

    metadata_doc = {
        "schema": "longform_publish_metadata_v1",
        "project_id": p_dir.name,
        "title": title,
        "description": description,
        "aspect": FLOW_ASPECT_LONGFORM,
        "resolution": [LONGFORM_VIDEO_WIDTH, LONGFORM_VIDEO_HEIGHT],
        "privacy_status": "unlisted",
        "altered_content_ai_disclosure": True,
        "upload_cc_srt": bool(upload_cc_srt),
        "language": "en-US",
        "everyday_domain": domain.lower(),
        "thumbnails": thumb_rep["jpg_variants"],
        "thumbnail_sizes_bytes": thumb_rep["jpg_sizes_bytes"],
        "prepared_comment_path": str(staged_comm_path),
        "pinned_comment_line1": line1,
        "pinned_comment_valid": len(comm_issues) == 0,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    meta_path = pub_dir / "metadata.json"
    meta_path.write_text(json.dumps(metadata_doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return metadata_doc
