"""
ALL ABOUT BRAIN — YouTube Receipt & Publish-Gate Helpers (`pipeline/studio/queue_manager.py`).
"""

from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any

from pipeline.studio.short_linker import is_valid_youtube_video_id
from pipeline.studio.uploader import (
    _is_legacy_hermetic_test_stub,
    verify_publish_ready_qa_bundle,
)

LIVE_RECEIPT_STATUSES = frozenset({
    "uploaded",
    "published_public",
    "scheduled",
    "scheduled_public",
    "staged_unlisted",
    "uploaded_unlisted",
})


def _parse_scheduled_time_et(raw: Any) -> tuple[str, str]:
    """Extracts ('YYYY-MM-DD', 'HH:MM') from strings like '2026-10-19 12:00 ET'."""
    if raw is None:
        return "", ""
    cleaned = str(raw).replace("ET", "").strip()
    m_full = re.match(r"^(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2})", cleaned)
    if m_full:
        return m_full.group(1), m_full.group(2)
    m_date = re.match(r"^(\d{4}-\d{2}-\d{2})$", cleaned)
    if m_date:
        return m_date.group(1), ""
    return "", ""


def is_live_youtube_receipt(receipt: dict[str, Any] | None) -> bool:
    """True when upload_receipt.json represents an active (non-deleted, non-dry-run) YouTube video."""
    if not isinstance(receipt, dict):
        return False
    status = str(receipt.get("status") or "").strip().lower()
    vid = str(receipt.get("video_id") or "").strip()
    if status not in LIVE_RECEIPT_STATUSES:
        return False
    return is_valid_youtube_video_id(vid)


def passes_v5_publish_gate(
    project_dir: Path,
    allow_legacy_v4: bool = False,
    require_semantic_review: bool = True,
    fast_stat_only: bool = False,
) -> tuple[bool, list[str]]:
    """
    Validates that an unpublished project satisfies Prompt System v5+ (R61/R63)
    AND, when `05_assembly/final_shorts_1080x1920.mp4` is present, passes the mandatory
    post-assembly QA & R64 semantic review lock before Studio upload.
    """
    if allow_legacy_v4:
        return True, []

    p_dir = Path(project_dir)
    vp_path = p_dir / "03_visuals" / "visual_plan.json"
    prompts_path = p_dir / "03_visuals" / "flow_all_in_one_prompts.json"
    script_path = p_dir / "02_script" / "script.json"

    if not vp_path.exists() or not prompts_path.exists():
        return False, ["missing v5 visual_plan.json or flow_all_in_one_prompts.json"]

    try:
        plan = json.loads(vp_path.read_text(encoding="utf-8"))
        prompts_doc = json.loads(prompts_path.read_text(encoding="utf-8"))
        clips = prompts_doc.get("clips") or []
        script_doc = json.loads(script_path.read_text(encoding="utf-8")) if script_path.exists() else {}
        from pipeline.config import is_diorama_profile

        if is_diorama_profile(plan) or is_diorama_profile(script_doc):
            from pipeline.assembler import load_diorama_script_sentences
            from pipeline.prompt_gate import validate_production_diorama_v6

            sentences, s_doc = load_diorama_script_sentences(p_dir)
            issues = list(validate_production_diorama_v6(plan, sentences, clips, script_doc=s_doc))
        else:
            schema_v = int(plan.get("schema") or plan.get("schema_version") or prompts_doc.get("schema") or 0)
            if schema_v < 5:
                return False, ["legacy v4 project blocked from v5+ publish queue"]
            narrations = (script_doc.get("clip_narrations") or []) if script_path.exists() else []
            issues = []
            if not isinstance(clips, list) or len(clips) < 5:
                issues.append("v5 prompts must contain >= 5 clips")
            elif narrations and len(narrations) != len(clips):
                issues.append(f"v5 clip_narrations count {len(narrations)} != clips count {len(clips)}")
            elif any(not str((c.get("prompt") if isinstance(c, dict) else c) or "").strip() for c in clips):
                issues.append("v5 clip missing prompt text")

        if issues:
            return False, issues

        final_mp4 = p_dir / "05_assembly" / "final_shorts_1080x1920.mp4"
        if final_mp4.exists() and not _is_legacy_hermetic_test_stub(p_dir):
            qa_bundle = verify_publish_ready_qa_bundle(
                p_dir,
                require_semantic_review=require_semantic_review,
                fast_stat_only=fast_stat_only,
            )
            if not qa_bundle["passed"]:
                return False, list(qa_bundle["issues"])

        return True, []
    except Exception as exc:
        return False, [f"v5 gate read error: {exc}"]
