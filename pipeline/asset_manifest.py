"""
ALL ABOUT BRAIN - Asset manifest + channel asset library (R50: Shorts -> longform reuse).

Every assembled Short writes 05_assembly/asset_manifest.json and upserts one line per clip into
BCI_Shorts_Channel/asset_library/index.jsonl, so a longform edit can:
  - reuse the 9:16 clip as-is (pillarboxed / blurred-fill) or the exact sub-range used in the Short,
  - re-generate the same scene at 16:9 from the archived prompt (aspect-neutral scene text +
    flow_prompt_prefix("16:9")), or
  - generate only the bridge clips listed in the dossier's 07_longform_outline.json.

asset_id = <topic_slug>_<role>_<shot_type>  (topic_slug = visual_plan.dossier or project id)
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pipeline.config import ASSET_LIBRARY_DIRNAME, FLOW_ASPECT_SHORTS

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
ASSET_LIBRARY_DIR = WORKSPACE_ROOT / "BCI_Shorts_Channel" / ASSET_LIBRARY_DIRNAME
ASSET_INDEX_PATH = ASSET_LIBRARY_DIR / "index.jsonl"


def _read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:  # noqa: BLE001
        return {}


def _sha256(path: Path) -> str | None:
    try:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def _concat_ranges(project_dir: Path) -> list[dict[str, float]]:
    """Per-clip [inpoint, outpoint] (source seconds) used in the Short, from 05_assembly/concat_list.txt."""
    path = Path(project_dir) / "05_assembly" / "concat_list.txt"
    if not path.exists():
        return []
    ranges: list[dict[str, float]] = []
    cur: dict[str, float] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("file "):
            if cur:
                ranges.append(cur)
            cur = {}
        elif line.startswith("inpoint "):
            cur["source_in_sec"] = float(line.split()[1])
        elif line.startswith("outpoint "):
            cur["source_out_sec"] = float(line.split()[1])
    if cur:
        ranges.append(cur)
    return ranges


def build_asset_manifest(project_dir: Path, write_library: bool = True) -> dict[str, Any]:
    project_dir = Path(project_dir)
    prompts = _read_json(project_dir / "03_visuals" / "flow_all_in_one_prompts.json")
    plan = _read_json(project_dir / "03_visuals" / "visual_plan.json")
    receipt = _read_json(project_dir / "03_visuals" / "flow_provenance_receipt.json")
    voice = _read_json(project_dir / "04_audio" / "voice_report.json")
    clips = prompts.get("clips") or []
    topic_slug = str(plan.get("dossier") or project_dir.name)
    ranges = _concat_ranges(project_dir)
    native_dir = project_dir / "03_visuals" / "flow_native_clips"
    timeline = 0.0
    assets: list[dict[str, Any]] = []
    receipt_clips = receipt.get("clips") if isinstance(receipt.get("clips"), list) else []
    for i, c in enumerate(clips):
        n = int(c.get("clip_number") or i + 1)
        role = str(c.get("role") or f"clip{n}")
        shot_type = str(c.get("shot_type") or "shot")
        f = native_dir / f"clip_{n}.mp4"
        r = ranges[i] if i < len(ranges) else {}
        rc = receipt_clips[i] if i < len(receipt_clips) and isinstance(receipt_clips[i], dict) else {}
        dur_out = None
        if r:
            dur_out = round(float(r.get("source_out_sec", 0.0)) - float(r.get("source_in_sec", 0.0)), 3)
        assets.append(
            {
                "asset_id": re.sub(r"[^a-z0-9_]+", "_", f"{topic_slug}_{role}_{shot_type}".lower()),
                "project_id": project_dir.name,
                "clip_number": n,
                "role": role,
                "scene_id": c.get("scene_id"),
                "visual_mode": c.get("visual_mode") or prompts.get("visual_mode"),
                "setting": c.get("setting"),
                "shot_type": shot_type,
                "camera_move": c.get("camera_move"),
                "aspect": c.get("aspect") or FLOW_ASPECT_SHORTS,
                "file": str(f) if f.exists() else None,
                "sha256": _sha256(f) if f.exists() else None,
                "scene": c.get("scene"),
                "spoken_narration": c.get("spoken_narration"),
                "prompt": c.get("prompt"),
                "flow_model": rc.get("model") or receipt.get("model") or receipt.get("flow_model"),
                "seed": rc.get("seed") or receipt.get("seed"),  # Flow does not expose seeds today; kept if it does
                "generated_at": rc.get("generated_at") or receipt.get("generated_at") or receipt.get("created_at"),
                "used_in_short": {**r, "timeline_start_sec": round(timeline, 3)} if r else None,
                "voice_source": voice.get("source", "native"),
                "longform_reuse": "reuse_or_regen_16x9" if c.get("setting") in ("brain_void", "drill_down") else "regen_16x9_preferred",
            }
        )
        if dur_out:
            timeline += dur_out
    manifest = {
        "schema_version": 1,
        "project_id": project_dir.name,
        "topic_slug": topic_slug,
        "dossier": plan.get("dossier"),
        "visual_mode": prompts.get("visual_mode") or plan.get("visual_mode"),
        "flow_project_url": receipt.get("flow_project_url"),
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "assets": assets,
    }
    out = project_dir / "05_assembly" / "asset_manifest.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    if write_library:
        upsert_library(assets)
    return manifest


def upsert_library(assets: list[dict[str, Any]], index_path: Path | None = None) -> Path:
    """Replaces existing lines with the same (project_id, clip_number) and appends the rest."""
    index_path = Path(index_path or ASSET_INDEX_PATH)
    index_path.parent.mkdir(parents=True, exist_ok=True)
    keep: list[str] = []
    new_keys = {(a["project_id"], a["clip_number"]) for a in assets}
    if index_path.exists():
        for line in index_path.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if (row.get("project_id"), row.get("clip_number")) not in new_keys:
                keep.append(line)
    slim_keys = ("asset_id", "project_id", "clip_number", "role", "scene_id", "visual_mode", "setting", "shot_type",
                 "aspect", "file", "sha256", "scene", "spoken_narration", "prompt", "used_in_short", "voice_source",
                 "longform_reuse")
    keep += [json.dumps({k: a.get(k) for k in slim_keys}, ensure_ascii=False) for a in assets]
    index_path.write_text("\n".join(keep) + "\n", encoding="utf-8")
    return index_path


def search_library(query: str, index_path: Path | None = None, limit: int = 20) -> list[dict[str, Any]]:
    """Simple keyword search over scene / narration / asset_id for longform editors."""
    index_path = Path(index_path or ASSET_INDEX_PATH)
    if not index_path.exists():
        return []
    terms = [t for t in re.split(r"\W+", query.lower()) if t]
    hits: list[tuple[int, dict[str, Any]]] = []
    for line in index_path.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        hay = " ".join(str(row.get(k) or "") for k in ("asset_id", "scene", "spoken_narration", "scene_id")).lower()
        score = sum(hay.count(t) for t in terms)
        if score:
            hits.append((score, row))
    return [r for _, r in sorted(hits, key=lambda x: -x[0])[:limit]]
