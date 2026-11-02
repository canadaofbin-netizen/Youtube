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

import contextlib
import hashlib
import json
import os
import re
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import fcntl as _fcntl
except ImportError:  # pragma: no cover - Windows fallback
    _fcntl = None  # type: ignore[assignment]

from pipeline.config import ASSET_LIBRARY_DIRNAME, FLOW_ASPECT_SHORTS

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
ASSET_LIBRARY_DIR = WORKSPACE_ROOT / "BCI_Shorts_Channel" / ASSET_LIBRARY_DIRNAME
ASSET_INDEX_PATH = ASSET_LIBRARY_DIR / "index.jsonl"

_ASSET_LOCK_GUARD = threading.Lock()
_ASSET_LOCKS: dict[str, threading.RLock] = {}


@contextlib.contextmanager
def _asset_index_lock(index_path: Path):
    resolved = str(Path(index_path).resolve())
    with _ASSET_LOCK_GUARD:
        rlock = _ASSET_LOCKS.setdefault(resolved, threading.RLock())
    with rlock:
        lock_root = Path("/tmp") if (os.name != "nt" and Path("/tmp").exists()) else index_path.parent
        lock_root.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha1(resolved.encode("utf-8")).hexdigest()[:16]
        lock_file = lock_root / f".aab_asset_idx_{digest}.lock"
        fh = None
        locked = False
        try:
            if _fcntl is not None:
                try:
                    fh = open(lock_file, "a+", encoding="utf-8")
                    _fcntl.flock(fh.fileno(), _fcntl.LOCK_EX)
                    locked = True
                except OSError:
                    if fh is not None:
                        fh.close()
                        fh = None
            yield
        finally:
            if locked and fh is not None and _fcntl is not None:
                try:
                    _fcntl.flock(fh.fileno(), _fcntl.LOCK_UN)
                except OSError:
                    pass
            if fh is not None:
                try:
                    fh.close()
                except OSError:
                    pass


def _atomic_write_text(target: Path, content: str) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = target.parent / f".tmp_{os.getpid()}_{threading.get_ident()}_{time.time_ns()}_{target.name}"
    tmp_path.write_text(content, encoding="utf-8")
    for attempt in range(5):
        try:
            os.replace(tmp_path, target)
            return
        except OSError:
            if attempt == 4:
                tmp_path.unlink(missing_ok=True)
                target.write_text(content, encoding="utf-8")
                return
            time.sleep(0.12 * (attempt + 1))


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


def _edl_clip_usage(project_dir: Path) -> dict[int, dict[str, Any]]:
    """Extracts per-clip timeline usage from Schema v6/v7 `05_assembly/edit_decision_list.json`."""
    edl = _read_json(Path(project_dir) / "05_assembly" / "edit_decision_list.json")
    cuts = edl.get("cuts") if isinstance(edl.get("cuts"), list) else []
    usage: dict[int, dict[str, Any]] = {}
    for c in cuts:
        if not isinstance(c, dict):
            continue
        for key_name in ("clip_index", "secondary_clip_index"):
            c_idx = c.get(key_name)
            if c_idx is None:
                continue
            c_no = int(c_idx)
            if c_no not in usage:
                sec_span = c.get("secondary_src_span")
                if key_name == "secondary_clip_index" and isinstance(sec_span, list) and len(sec_span) == 2:
                    src_in, src_out = float(sec_span[0]), float(sec_span[1])
                else:
                    src_in = float(c.get("src_start_sec") or 0.0)
                    src_out = float(c.get("src_end_sec") or 0.0)
                usage[c_no] = {
                    "cut_index": int(c.get("cut_index") or 0),
                    "source_in_sec": round(src_in, 3),
                    "source_out_sec": round(src_out, 3),
                    "timeline_start_sec": round(float(c.get("out_start_sec") or 0.0), 3),
                    "timeline_end_sec": round(float(c.get("out_end_sec") or 0.0), 3),
                    "mode": str(c.get("mode") or "single"),
                }
    return usage


def _extract_script_sentences(script_doc: dict[str, Any]) -> list[str]:
    if isinstance(script_doc.get("sentences"), list) and script_doc["sentences"]:
        return [str(s).strip() for s in script_doc["sentences"] if str(s).strip()]
    if isinstance(script_doc.get("acts"), list):
        return [
            str(s).strip()
            for act in script_doc["acts"]
            if isinstance(act, dict)
            for s in (act.get("sentences") or [])
            if str(s).strip()
        ]
    if isinstance(script_doc.get("clip_narrations"), list):
        return [str(s).strip() for s in script_doc["clip_narrations"] if str(s).strip()]
    return []


def build_asset_manifest(project_dir: Path, write_library: bool = True) -> dict[str, Any]:
    from pipeline.config import POSTHOC_SEMANTIC_QA_REPORT_FILENAME

    project_dir = Path(project_dir)
    prompts = _read_json(project_dir / "03_visuals" / "flow_all_in_one_prompts.json")
    plan = _read_json(project_dir / "03_visuals" / "visual_plan.json")
    script_doc = _read_json(project_dir / "02_script" / "script.json")
    receipt = _read_json(project_dir / "03_visuals" / "flow_provenance_receipt.json")
    voice = _read_json(project_dir / "04_audio" / "voice_report.json")
    posthoc = _read_json(project_dir / "05_assembly" / POSTHOC_SEMANTIC_QA_REPORT_FILENAME)

    sentences = _extract_script_sentences(script_doc)
    plan_clips = plan.get("clips") if isinstance(plan.get("clips"), list) else []
    plan_by_num = {
        int(pc.get("clip_number") or (idx + 1)): pc
        for idx, pc in enumerate(plan_clips)
        if isinstance(pc, dict)
    }
    posthoc_by_clip = {
        int(sc["clip_number"]): sc
        for sc in (posthoc.get("source_clips") or [])
        if isinstance(sc, dict) and sc.get("clip_number") is not None
    }

    clips = prompts.get("clips") or []
    topic_slug = str(plan.get("dossier") or script_doc.get("dossier") or project_dir.name)
    style_profile = str(plan.get("style_profile") or prompts.get("style_profile") or script_doc.get("style_profile") or "")
    schema_ver = int(prompts.get("schema_version") or plan.get("schema_version") or plan.get("schema") or 5)

    ranges = _concat_ranges(project_dir)
    edl_usage = _edl_clip_usage(project_dir)
    native_dir = project_dir / "03_visuals" / "flow_native_clips"
    timeline = 0.0
    assets: list[dict[str, Any]] = []
    receipt_clips = receipt.get("clips") if isinstance(receipt.get("clips"), list) else []
    receipt_by_clip: dict[int, dict[str, Any]] = {}
    for rc_item in receipt_clips:
        if isinstance(rc_item, dict) and (rc_item.get("clip_index") is not None or rc_item.get("clip_number") is not None):
            try:
                c_key = int(rc_item.get("clip_index") or rc_item.get("clip_number") or 0)
            except (TypeError, ValueError):
                c_key = 0
            if c_key > 0:
                receipt_by_clip[c_key] = rc_item

    shots_by_role = plan.get("shots") if isinstance(plan.get("shots"), dict) else {}

    for i, c in enumerate(clips):
        n = int(c.get("clip_number") or i + 1)
        p_spec = plan_by_num.get(n, {})
        grammar = str(c.get("grammar") or p_spec.get("grammar") or c.get("setting") or "")
        role = str(c.get("role") or p_spec.get("cut_role") or grammar or f"clip{n}")
        role_shot = shots_by_role.get(role) if isinstance(shots_by_role.get(role), dict) else {}
        shot_type = str(c.get("shot_type") or role_shot.get("shot_type") or grammar or "shot")
        location_id = str(c.get("location_id") or p_spec.get("location_id") or c.get("scene_id") or role_shot.get("scene_id") or "")
        act_no = c.get("act") or p_spec.get("act")
        f = native_dir / f"clip_{n}.mp4"
        r = ranges[i] if i < len(ranges) else {}
        rc = receipt_by_clip.get(n)
        if rc is None and i < len(receipt_clips) and isinstance(receipt_clips[i], dict):
            cand_rc = receipt_clips[i]
            if cand_rc.get("clip_index") is None and cand_rc.get("clip_number") is None:
                rc = cand_rc
        rc = rc or {}

        spoken = c.get("spoken_narration")
        if not spoken:
            s0 = c.get("sentence_index") or p_spec.get("sentence_index")
            s1 = c.get("end_sentence_index") or p_spec.get("end_sentence_index") or s0
            if isinstance(s0, int) and 1 <= s0 <= len(sentences):
                spoken = " ".join(sentences[k - 1] for k in range(s0, min(len(sentences), int(s1 or s0)) + 1))

        dur_out = None
        used_info: dict[str, Any] | None = None
        if n in edl_usage:
            used_info = edl_usage[n]
        elif r:
            dur_out = round(float(r.get("source_out_sec", 0.0)) - float(r.get("source_in_sec", 0.0)), 3)
            used_info = {**r, "timeline_start_sec": round(timeline, 3)}

        ph_entry = posthoc_by_clip.get(n, {})
        clarity_score = ph_entry.get("mean_clarity_score")
        posthoc_passed = ph_entry.get("passed")

        is_brain_or_analogy = grammar in (
            "brain_void",
            "drill_down",
            "lowpoly_matte_brain",
            "lowpoly_literal_analogy",
            "porcelain_living_brain",
            "porcelain_literal_analogy",
            "arch_brain_maquette",
            "frosted_crystal_specimen",
        ) or c.get("setting") in ("brain_void", "brain_studio", "drill_down")

        assets.append(
            {
                "asset_id": re.sub(r"[^a-z0-9_]+", "_", f"{topic_slug}_c{n:02d}_{role}_{shot_type}".lower()) if schema_ver >= 6 else re.sub(r"[^a-z0-9_]+", "_", f"{topic_slug}_{role}_{shot_type}".lower()),
                "project_id": project_dir.name,
                "dossier": plan.get("dossier") or script_doc.get("dossier"),
                "schema_version": schema_ver,
                "style_profile": style_profile or None,
                "clip_number": n,
                "act": int(act_no) if act_no is not None else None,
                "role": role,
                "grammar": grammar or None,
                "location_id": location_id or None,
                "scene_id": c.get("scene_id") or location_id or None,
                "visual_mode": c.get("visual_mode") or prompts.get("visual_mode") or plan.get("visual_mode"),
                "setting": c.get("setting") or grammar or None,
                "shot_type": shot_type,
                "camera_move": c.get("camera_move") or p_spec.get("camera"),
                "aspect": c.get("aspect") or FLOW_ASPECT_SHORTS,
                "file": str(f) if f.exists() else None,
                "sha256": _sha256(f) if f.exists() else None,
                "scene": c.get("scene"),
                "spoken_narration": spoken,
                "prompt": c.get("prompt"),
                "flow_model": rc.get("model") or receipt.get("model") or receipt.get("flow_model"),
                "seed": rc.get("seed") or receipt.get("seed"),
                "generated_at": rc.get("generated_at") or receipt.get("generated_at") or receipt.get("created_at"),
                "used_in_short": used_info,
                "clarity_score": clarity_score,
                "posthoc_passed": posthoc_passed,
                "voice_source": voice.get("source", "native"),
                "longform_reuse": "reuse_or_regen_16x9" if is_brain_or_analogy else "regen_16x9_preferred",
            }
        )
        if dur_out:
            timeline += dur_out

    manifest = {
        "schema_version": 2,
        "project_id": project_dir.name,
        "topic_slug": topic_slug,
        "dossier": plan.get("dossier") or script_doc.get("dossier"),
        "prompt_schema_version": schema_ver,
        "style_profile": style_profile or None,
        "visual_mode": prompts.get("visual_mode") or plan.get("visual_mode"),
        "flow_project_url": receipt.get("flow_project_url"),
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "assets": assets,
    }
    out = project_dir / "05_assembly" / "asset_manifest.json"
    _atomic_write_text(out, json.dumps(manifest, indent=2, ensure_ascii=False))
    from pipeline.storage import ProjectStorage

    ProjectStorage.record_if_manifest_tracks_stages(project_dir, "05_assembly", "asset_manifest.json", out)
    if write_library:
        ws_root = WORKSPACE_ROOT.resolve()
        idx_target = Path(ASSET_INDEX_PATH).resolve()
        proj_resolved = project_dir.resolve()
        if not idx_target.is_relative_to(ws_root) or proj_resolved.is_relative_to(ws_root):
            upsert_library(assets)
    return manifest


def upsert_library(assets: list[dict[str, Any]], index_path: Path | None = None) -> Path:
    """Replaces existing lines with the same (project_id, clip_number) and appends the rest atomically under flock."""
    index_path = Path(index_path or ASSET_INDEX_PATH)
    index_path.parent.mkdir(parents=True, exist_ok=True)
    slim_keys = (
        "asset_id",
        "project_id",
        "dossier",
        "schema_version",
        "style_profile",
        "clip_number",
        "act",
        "role",
        "grammar",
        "location_id",
        "scene_id",
        "visual_mode",
        "setting",
        "shot_type",
        "camera_move",
        "aspect",
        "file",
        "sha256",
        "scene",
        "spoken_narration",
        "prompt",
        "used_in_short",
        "clarity_score",
        "posthoc_passed",
        "voice_source",
        "longform_reuse",
    )
    new_keys = {(a["project_id"], a["clip_number"]) for a in assets}
    new_lines = [json.dumps({k: a.get(k) for k in slim_keys}, ensure_ascii=False) for a in assets]
    with _asset_index_lock(index_path):
        keep: list[str] = []
        if index_path.exists():
            for line in index_path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if (row.get("project_id"), row.get("clip_number")) not in new_keys:
                    keep.append(line)
        keep.extend(new_lines)
        payload = ("\n".join(keep) + "\n") if keep else ""
        _atomic_write_text(index_path, payload)
    return index_path


def search_library(
    query: str,
    index_path: Path | None = None,
    limit: int = 20,
    grammar: str | None = None,
    min_clarity: float | None = None,
    style_profile: str | None = None,
) -> list[dict[str, Any]]:
    """Keyword + metadata search over scene / narration / grammar / location_id for Shorts & longform reuse."""
    index_path = Path(index_path or ASSET_INDEX_PATH)
    if not index_path.exists():
        return []
    terms = [t for t in re.split(r"\W+", str(query or "").lower()) if t]
    hits: list[tuple[float, dict[str, Any]]] = []
    for line in index_path.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if grammar and str(row.get("grammar") or "").lower() != grammar.strip().lower():
            continue
        if style_profile and str(row.get("style_profile") or "").lower() != style_profile.strip().lower():
            continue
        if min_clarity is not None:
            cs = row.get("clarity_score")
            if cs is None or float(cs) < float(min_clarity):
                continue
        hay = " ".join(
            str(row.get(k) or "")
            for k in ("asset_id", "scene", "spoken_narration", "scene_id", "grammar", "location_id", "dossier")
        ).lower()
        score = float(sum(hay.count(t) for t in terms)) if terms else 1.0
        if score > 0:
            clarity_bonus = float(row.get("clarity_score") or 0.0) * 0.01
            hits.append((score + clarity_bonus, row))
    return [r for _, r in sorted(hits, key=lambda x: -x[0])[:limit]]
