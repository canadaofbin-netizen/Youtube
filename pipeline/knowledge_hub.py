"""
ALL ABOUT BRAIN — Accumulated Episode Knowledge Hub, Analytics & Asset Reuse Engine
===================================================================================
Organizes, indexes, analyzes, and exposes accumulated episode artifacts under
`BCI_Shorts_Channel/knowledge_base/` (paired with `BCI_Shorts_Channel/asset_library/`):

  BCI_Shorts_Channel/knowledge_base/
    README.md
    telemetry/
      episodes_index.jsonl          # 1 row per episode (speed, WPM, duration, QA & R64 clarity)
      clip_clarity_ledger.jsonl     # 1 row per evaluated cut/clip (prompt, grammar, camera, clarity, defects)
      qa_analytics_summary.json     # Aggregate clarity by grammar, camera, act, and top failure modes
      qa_analytics_report.md        # Human-readable analytics dashboard
    reusable_packs/
      prompts_golden_bank.json      # High-clarity verified prompts grouped by grammar & camera_move
      analogies_registry.json       # [Number] -> [Everyday Analogy] phrases, visual staging & clarity
      brain_models_registry.json    # Canonical brain regions, render modes, prompts & reusable clips
      locations_and_props_registry.json  # Verified full-bleed / cutaway location packs
    experiments/                    # Controlled A/B render benchmarks (e.g., 1.00x vs 1.08x vs 1.12x)
"""

from __future__ import annotations

import contextlib
import datetime as dt
import hashlib
import json
import os
import re
import threading
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

try:
    import fcntl as _fcntl
except ImportError:  # pragma: no cover - Windows fallback
    _fcntl = None  # type: ignore[assignment]

import numpy as np

from pipeline.asset_manifest import ASSET_INDEX_PATH, build_asset_manifest, search_library
from pipeline.config import (
    CLIP_CLARITY_LEDGER_FILENAME,
    EPISODES_INDEX_FILENAME,
    EXPERIMENTS_ARCHIVE_DIRNAME,
    KNOWLEDGE_BASE_DIR,
    KNOWLEDGE_TELEMETRY_DIRNAME,
    POSTHOC_SEMANTIC_QA_REPORT_FILENAME,
    PROJECTS_DIR,
    QA_ANALYTICS_SUMMARY_FILENAME,
    REUSABLE_PACKS_DIRNAME,
)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
    except Exception:  # noqa: BLE001
        pass
    return {}


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for ln in path.read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            obj = json.loads(ln)
            if isinstance(obj, dict):
                rows.append(obj)
        except json.JSONDecodeError:
            continue
    return rows


_KB_LOCK_GUARD = threading.Lock()
_KB_LOCKS: dict[str, threading.RLock] = {}


@contextlib.contextmanager
def _kb_file_lock(path: Path):
    resolved = str(Path(path).resolve())
    with _KB_LOCK_GUARD:
        rlock = _KB_LOCKS.setdefault(resolved, threading.RLock())
    with rlock:
        from pipeline.cdp_tab_lease import get_aab_locks_dir

        from pipeline.cdp_tab_lease import acquire_shared_flock

        lock_root = get_aab_locks_dir() if (os.name != "nt" and Path("/tmp").exists()) else path.parent
        lock_root.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha1(resolved.encode("utf-8")).hexdigest()[:16]
        lock_file = lock_root / f"kb_{digest}.lock"
        fh = acquire_shared_flock(lock_file)
        try:
            yield
        finally:
            if fh is not None and _fcntl is not None:
                try:
                    _fcntl.flock(fh.fileno(), _fcntl.LOCK_UN)
                except OSError:
                    pass
            if fh is not None:
                try:
                    fh.close()
                except OSError:
                    pass


def _atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.parent / f".tmp_{os.getpid()}_{threading.get_ident()}_{time.time_ns()}_{path.name}"
    tmp_path.write_text(content, encoding="utf-8")
    for attempt in range(5):
        try:
            os.replace(tmp_path, path)
            return
        except OSError:
            if attempt == 4:
                tmp_path.unlink(missing_ok=True)
                path.write_text(content, encoding="utf-8")
                return
            time.sleep(0.12 * (attempt + 1))


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    text = "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + ("\n" if rows else "")
    _atomic_write_text(path, text)


def _upsert_jsonl(
    path: Path,
    new_rows: list[dict[str, Any]],
    project_id: str | None = None,
    valid_project_ids: set[str] | None = None,
    sort_key: Any = None,
) -> list[dict[str, Any]]:
    """Atomically upserts/prunes JSONL rows under `fcntl.flock` + `.tmp` + `os.replace()`."""
    with _kb_file_lock(path):
        existing = _read_jsonl(path)
        if project_id is not None:
            existing = [r for r in existing if str(r.get("project_id") or "") != project_id]
        if valid_project_ids is not None:
            existing = [r for r in existing if str(r.get("project_id") or "") in valid_project_ids]
        existing.extend(new_rows)
        if sort_key is not None:
            existing.sort(key=sort_key)
        _write_jsonl(path, existing)
        return existing


def _extract_sentences(script_doc: dict[str, Any]) -> list[str]:
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


def _write_kb_readme(readme_path: Path) -> None:
    _atomic_write_text(
        readme_path,
        "# ALL ABOUT BRAIN — Knowledge Base & Reusable Asset Hub\n\n"
        "Structured accumulation layer for cross-episode QA analytics, prompt optimization,\n"
        "Shorts reuse, and 8–15 minute Longform expansion.\n\n"
        "## Directory Layout\n"
        "- `telemetry/episodes_index.jsonl` — Per-episode speed (`1.08x` / `+8%`, `+14Hz` Silk Clean), WPM, duration, DQ1–DQ12, and R64 clarity summary.\n"
        "- `telemetry/clip_clarity_ledger.jsonl` — Every evaluated cut/clip with prompt, grammar, camera move, 5-axis clarity scores, and defects.\n"
        "- `telemetry/qa_analytics_summary.json` & `qa_analytics_report.md` — Aggregated clarity benchmarks by grammar, camera move, and Act.\n"
        "- `reusable_packs/prompts_golden_bank.json` — Verified high-clarity prompts (`>= 82.0`) indexed by grammar & camera move.\n"
        "- `reusable_packs/analogies_registry.json` — Spoken `[Number] -> [Everyday Analogy]` pairs + visual staging recipes.\n"
        "- `reusable_packs/brain_models_registry.json` — Canonical 3D brain region depictions & reusable clip paths.\n"
        "- `reusable_packs/locations_and_props_registry.json` — Verified recurring environments & text-free props.\n"
        "- `experiments/` — Archived controlled A/B render comparisons with provenance manifests.\n\n"
        "## CLI Usage\n"
        "```bash\n"
        "python -X utf8 main.py kb sync\n"
        "python -X utf8 main.py kb stats\n"
        "python -X utf8 main.py kb search --pack prompts --grammar lowpoly_hands_closeup --min-clarity 85\n"
        "python -X utf8 main.py kb search --pack clips --query \"frontal lobe\"\n"
        "```\n",
    )


def ensure_knowledge_base_layout(kb_dir: Path | None = None) -> dict[str, Path]:
    """Creates the canonical `BCI_Shorts_Channel/knowledge_base/` directory tree and `README.md`."""
    root = Path(kb_dir or KNOWLEDGE_BASE_DIR)
    telemetry_dir = root / KNOWLEDGE_TELEMETRY_DIRNAME
    packs_dir = root / REUSABLE_PACKS_DIRNAME
    experiments_dir = root / EXPERIMENTS_ARCHIVE_DIRNAME

    for d in (root, telemetry_dir, packs_dir, experiments_dir):
        d.mkdir(parents=True, exist_ok=True)

    readme_path = root / "README.md"
    if not readme_path.exists():
        _write_kb_readme(readme_path)
    else:
        try:
            if "1.05x" in readme_path.read_text(encoding="utf-8"):
                _write_kb_readme(readme_path)
        except OSError:
            pass

    return {
        "root": root,
        "telemetry_dir": telemetry_dir,
        "packs_dir": packs_dir,
        "experiments_dir": experiments_dir,
        "episodes_index": telemetry_dir / EPISODES_INDEX_FILENAME,
        "clip_ledger": telemetry_dir / CLIP_CLARITY_LEDGER_FILENAME,
        "analytics_json": telemetry_dir / QA_ANALYTICS_SUMMARY_FILENAME,
        "analytics_md": telemetry_dir / "qa_analytics_report.md",
    }


def _detect_style_info(
    visual_plan: dict[str, Any],
    prompts_doc: dict[str, Any],
    script_doc: dict[str, Any],
    manifest_doc: dict[str, Any],
) -> tuple[int, str]:
    """Resolves `(schema_version, style_profile)` with Schema v7 -> `lowpoly_pastel_v7` and v6 -> `dark_ceramic_v6`."""
    schema_ver = int(
        prompts_doc.get("schema_version")
        or visual_plan.get("schema_version")
        or visual_plan.get("schema")
        or script_doc.get("schema_version")
        or script_doc.get("schema")
        or manifest_doc.get("schema_version")
        or 5
    )
    explicit_style = str(
        visual_plan.get("style_profile")
        or prompts_doc.get("style_profile")
        or script_doc.get("style_profile")
        or manifest_doc.get("style_profile")
        or ""
    ).strip()
    if explicit_style:
        style_profile = explicit_style
    elif schema_ver >= 7:
        from pipeline.config import resolve_diorama_v7_style_profile

        style_profile = resolve_diorama_v7_style_profile(visual_plan, prompts_doc, script_doc, manifest_doc)
    elif schema_ver == 6:
        style_profile = "dark_ceramic_v6"
    else:
        style_profile = "classic_v5"
    return schema_ver, style_profile


def _compute_project_kb_signature(p_dir: Path) -> str:
    """
    Fast metadata-only signature (`size` + `mtime_ns`, zero file-byte reads over `fuse.rclone`)
    covering the assembled artifacts & contracts indexed by `sync_project_to_knowledge_base`.
    """
    import hashlib

    parts: list[str] = []
    for rel in (
        "02_script/script.json",
        "03_visuals/visual_plan.json",
        "03_visuals/flow_all_in_one_prompts.json",
        "03_visuals/episode_qa_contract.json",
        "04_audio/voice_report.json",
        "05_assembly/final_shorts_1080x1920.mp4",
        f"05_assembly/{POSTHOC_SEMANTIC_QA_REPORT_FILENAME}",
        "05_assembly/dynamic_episode_qa_report.json",
        "05_assembly/video_autopsy_report.json",
        "06_publish/thumbnail_report.json",
    ):
        fp = p_dir / rel
        try:
            st = fp.stat()
            parts.append(f"{rel}:{st.st_size}:{st.st_mtime_ns}")
        except OSError:
            parts.append(f"{rel}:missing")
    return hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()[:16]


def sync_project_to_knowledge_base(
    project_id_or_dir: str | Path,
    posthoc_report: dict[str, Any] | None = None,
    kb_dir: Path | None = None,
    write_asset_library: bool = True,
    recompile_aggregates: bool = True,
) -> dict[str, Any]:
    """
    Indexes a single project's metadata, voice/speed telemetry, R62/R64 QA results, and reusable
    prompts/clips/analogies/brain-models into `knowledge_base/` (and refreshes `asset_manifest.json`).
    """
    paths = ensure_knowledge_base_layout(kb_dir)
    p_dir = Path(project_id_or_dir) if Path(str(project_id_or_dir)).exists() else (Path(PROJECTS_DIR) / str(project_id_or_dir))
    if not p_dir.exists():
        raise FileNotFoundError(f"Project not found for knowledge base sync: {p_dir}")

    pid = p_dir.name
    manifest_doc = _read_json(p_dir / "00_project_manifest.json")
    rcard_doc = _read_json(p_dir / "01_ideation" / "research_card.json")
    script_doc = _read_json(p_dir / "02_script" / "script.json")
    visual_plan = _read_json(p_dir / "03_visuals" / "visual_plan.json")
    prompts_doc = _read_json(p_dir / "03_visuals" / "flow_all_in_one_prompts.json")
    contract_doc = _read_json(p_dir / "03_visuals" / "episode_qa_contract.json")
    voice_rep = _read_json(p_dir / "04_audio" / "voice_report.json")
    audio_spec = _read_json(p_dir / "04_audio" / "audio_master_spec.json")
    edl_doc = _read_json(p_dir / "05_assembly" / "edit_decision_list.json")
    autopsy_rep = _read_json(p_dir / "05_assembly" / "video_autopsy_report.json")
    ep_qa_rep = _read_json(p_dir / "05_assembly" / "dynamic_episode_qa_report.json")
    meta_doc = _read_json(p_dir / "06_publish" / "metadata.json")
    thumb_rep = _read_json(p_dir / "06_publish" / "thumbnail_report.json")
    ph_rep = posthoc_report or _read_json(p_dir / "05_assembly" / POSTHOC_SEMANTIC_QA_REPORT_FILENAME)

    # Refresh asset_manifest.json only when missing or older than final_shorts_1080x1080/flow_all_in_one_prompts
    am_path = p_dir / "05_assembly" / "asset_manifest.json"
    pr_path = p_dir / "03_visuals" / "flow_all_in_one_prompts.json"
    mp4_path = p_dir / "05_assembly" / "final_shorts_1080x1920.mp4"
    if pr_path.exists():
        am_fresh = False
        try:
            if am_path.is_file() and am_path.stat().st_size > 16:
                am_mtime = am_path.stat().st_mtime_ns
                src_mtime = max(
                    pr_path.stat().st_mtime_ns,
                    mp4_path.stat().st_mtime_ns if mp4_path.is_file() else 0,
                )
                am_fresh = am_mtime >= src_mtime
        except OSError:
            am_fresh = False
        if not am_fresh:
            has_live_clips = any((p_dir / "03_visuals" / "flow_native_clips").glob("clip_*.mp4"))
            if has_live_clips or not am_path.exists():
                build_asset_manifest(p_dir, write_library=(write_asset_library and kb_dir is None))

    sentences = _extract_sentences(script_doc)
    if not sentences and isinstance(prompts_doc.get("clips"), list):
        sentences = [
            str(c.get("spoken_narration") or "").strip()
            for c in prompts_doc["clips"]
            if isinstance(c, dict) and str(c.get("spoken_narration") or "").strip()
        ]
    word_count = sum(len(s.split()) for s in sentences)
    autopsy_audio = autopsy_rep.get("audio_stream") if isinstance(autopsy_rep.get("audio_stream"), dict) else {}
    speech_end = float(
        voice_rep.get("speech_end_sec")
        or edl_doc.get("speech_end_sec")
        or autopsy_audio.get("speech_end_sec")
        or audio_spec.get("target_speech_seconds")
        or 0.0
    )
    wpm = round(word_count / (speech_end / 60.0), 1) if speech_end > 1.0 and word_count > 0 else None

    schema_ver, style_profile = _detect_style_info(visual_plan, prompts_doc, script_doc, manifest_doc)
    dossier_slug = str(
        visual_plan.get("dossier")
        or script_doc.get("dossier")
        or manifest_doc.get("dossier_slug")
        or meta_doc.get("dossier_slug")
        or ""
    )
    pillar = str(
        script_doc.get("pillar")
        or meta_doc.get("pillar")
        or manifest_doc.get("pillar")
        or rcard_doc.get("pillar")
        or ""
    )
    doi_val = str(
        script_doc.get("doi")
        or meta_doc.get("doi")
        or manifest_doc.get("doi")
        or rcard_doc.get("doi")
        or ""
    ).strip()
    if not doi_val and meta_doc.get("description"):
        m_doi = re.search(r"10\.\d{4,9}/[-._;()/:A-Za-z0-9]+", str(meta_doc.get("description") or ""))
        if m_doi:
            doi_val = m_doi.group(0).rstrip(".,;)")

    clips_dir = p_dir / "03_visuals" / "flow_native_clips"
    clip_count = len(list(clips_dir.glob("clip_*.mp4"))) if clips_dir.exists() else len(prompts_doc.get("clips") or [])
    ph_sum = ph_rep.get("summary") if isinstance(ph_rep.get("summary"), dict) else {}

    episode_row = {
        "project_id": pid,
        "title": str(
            script_doc.get("title")
            or meta_doc.get("title")
            or manifest_doc.get("title")
            or rcard_doc.get("title")
            or pid
        ),
        "dossier": dossier_slug or None,
        "pillar": pillar or None,
        "doi": doi_val,
        "schema_version": schema_ver,
        "style_profile": style_profile,
        "camera_profile": str(visual_plan.get("camera_profile") or manifest_doc.get("camera_profile") or ""),
        "tts_engine": voice_rep.get("engine") or ("flow_native" if audio_spec.get("voice_profile") else None),
        "tts_voice": voice_rep.get("voice") or prompts_doc.get("voice") or audio_spec.get("voice_profile"),
        "voice_preset": (
            voice_rep.get("voice_preset")
            or script_doc.get("voice_preset")
            or visual_plan.get("voice_preset")
            or ("andrew_v7" if "Andrew" in str(voice_rep.get("voice") or "") else None)
        ),
        "prosody_mode": voice_rep.get("prosody_mode") or script_doc.get("prosody_mode") or visual_plan.get("prosody_mode"),
        "tts_rate": voice_rep.get("rate") or script_doc.get("tts_rate"),
        "tts_speed": voice_rep.get("speed") or audio_spec.get("av_speedup_factor"),
        "atempo_applied": voice_rep.get("atempo_applied"),
        "wpm": wpm,
        "true_rms_voiced_ratio": voice_rep.get("true_rms_voiced_ratio"),
        "duration_sec": edl_doc.get("total_duration_sec") or voice_rep.get("total_duration_sec") or ph_rep.get("duration_sec"),
        "fps": edl_doc.get("fps") or ph_rep.get("fps"),
        "sentence_count": len(sentences),
        "word_count": word_count,
        "clip_count": clip_count,
        "cut_count": edl_doc.get("cut_count") or ph_sum.get("cut_count"),
        "cut_duration_cv": edl_doc.get("cut_duration_cv"),
        "autopsy_passed": autopsy_rep.get("passed"),
        "episode_qa_passed": ep_qa_rep.get("passed"),
        "episode_qa_score": ep_qa_rep.get("score"),
        "posthoc_passed": ph_rep.get("passed"),
        "posthoc_mean_clarity": ph_sum.get("mean_clarity_score"),
        "posthoc_p10_clarity": ph_sum.get("p10_clarity_score"),
        "posthoc_min_clarity": ph_sum.get("min_clarity_score"),
        "posthoc_weak_cuts": ph_sum.get("weak_cut_indices", []),
        "thumbnail_passed": thumb_rep.get("passed"),
        "thumbnail_hook": thumb_rep.get("hook_text"),
        "thumbnail_hook_source": thumb_rep.get("hook_source"),
        "cover_frame_sec": thumb_rep.get("cover_frame_sec"),
        "cover_grammar": ((thumb_rep.get("variants") or {}).get("A") or {}).get("grammar"),
        "cover_score": ((thumb_rep.get("variants") or {}).get("A") or {}).get("total_score"),
        "analogy_locks": contract_doc.get("analogy_locks") or [],
        "kb_sync_sig": _compute_project_kb_signature(p_dir),
        "project_dir": str(p_dir),
        "indexed_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
    }

    _upsert_jsonl(
        paths["episodes_index"],
        [episode_row],
        project_id=pid,
        sort_key=lambda x: str(x.get("project_id") or ""),
    )

    # Upsert per-cut clarity ledger entries
    prompts_by_num = {
        int(c.get("clip_number") or (idx + 1)): c
        for idx, c in enumerate(prompts_doc.get("clips") or [])
        if isinstance(c, dict)
    }
    plan_by_num = {
        int(c.get("clip_number") or (idx + 1)): c
        for idx, c in enumerate(visual_plan.get("clips") or [])
        if isinstance(c, dict)
    }

    new_ledger_rows: list[dict[str, Any]] = []
    for crep in (ph_rep.get("cuts") or []):
        c_num = int(crep.get("clip_index") or 0)
        p_meta = prompts_by_num.get(c_num, {})
        v_meta = plan_by_num.get(c_num, {})
        clip_file = clips_dir / f"clip_{c_num}.mp4"
        new_ledger_rows.append(
            {
                "project_id": pid,
                "dossier": dossier_slug or None,
                "schema_version": schema_ver,
                "style_profile": style_profile,
                "cut_index": int(crep["cut_index"]),
                "clip_index": c_num,
                "act": int(crep.get("act") or 1),
                "grammar": crep.get("grammar"),
                "camera_move": crep.get("camera_move"),
                "location_id": crep.get("location_id") or v_meta.get("location_id"),
                "brain_mode": v_meta.get("brain_mode") or v_meta.get("render_mode"),
                "brain_region": v_meta.get("brain_region") or v_meta.get("region") or v_meta.get("target_region"),
                "analogy_object": v_meta.get("analogy_object"),
                "out_start_sec": crep.get("out_start_sec"),
                "out_end_sec": crep.get("out_end_sec"),
                "duration_sec": crep.get("duration_sec"),
                "passed": bool(crep.get("passed")),
                "clarity_score": crep.get("clarity_score"),
                "sub_scores": crep.get("sub_scores"),
                "defects": crep.get("defects", []),
                "remediation": crep.get("remediation", "none"),
                "spoken_narration": crep.get("spoken_narration"),
                "intended_scene": crep.get("intended_scene"),
                "prompt": p_meta.get("prompt") or "",
                "clip_path": str(clip_file) if clip_file.exists() else None,
            }
        )

    if new_ledger_rows or "cuts" in ph_rep:
        _upsert_jsonl(
            paths["clip_ledger"],
            new_ledger_rows,
            project_id=pid,
            sort_key=lambda x: (str(x.get("project_id") or ""), int(x.get("cut_index") or 0)),
        )

    agg = recompile_knowledge_aggregates(kb_dir=paths["root"], projects_dir=p_dir.parent) if recompile_aggregates else {}
    return {
        "project_id": pid,
        "episode_indexed": True,
        "cuts_indexed": len(new_ledger_rows),
        "posthoc_mean_clarity": episode_row["posthoc_mean_clarity"],
        "aggregates": agg,
    }


def recompile_knowledge_aggregates(kb_dir: Path | None = None, projects_dir: Path | None = None) -> dict[str, Any]:
    """
    Rebuilds all `reusable_packs/*.json` and `telemetry/qa_analytics_summary.json` + `.md`
    from `episodes_index.jsonl`, `clip_clarity_ledger.jsonl`, and project contracts.
    """
    paths = ensure_knowledge_base_layout(kb_dir)
    episodes = _read_jsonl(paths["episodes_index"])
    ledger = _read_jsonl(paths["clip_ledger"])
    p_root = Path(projects_dir or PROJECTS_DIR)
    ledger_pids = {str(r.get("project_id") or "") for r in ledger}
    on_disk_pids = (
        {d.name for d in p_root.iterdir() if d.is_dir() and not d.name.startswith(".")}
        if p_root.exists()
        else set()
    )

    def _is_archived_off_disk_pid(pid_val: Any) -> bool:
        s_pid = str(pid_val or "").strip()
        return bool(s_pid and s_pid not in ledger_pids and s_pid not in on_disk_pids)

    # 1. prompts_golden_bank.json (passed cuts with clarity >= 82.0, preserving archived off-disk episodes)
    golden_bank_path = paths["packs_dir"] / "prompts_golden_bank.json"
    prev_golden_by_g = (_read_json(golden_bank_path).get("by_grammar") or {})
    golden_cands_by_g: dict[str, list[dict[str, Any]]] = defaultdict(list)
    seen_golden_keys: set[tuple[str, int, int]] = set()
    for row in sorted(ledger, key=lambda r: -float(r.get("clarity_score") or 0.0)):
        if not row.get("passed") or float(row.get("clarity_score") or 0.0) < 82.0 or not row.get("prompt"):
            continue
        g = str(row.get("grammar") or "other")
        gk = (str(row["project_id"]), int(row["cut_index"]), int(row["clip_index"]))
        if gk in seen_golden_keys:
            continue
        seen_golden_keys.add(gk)
        golden_cands_by_g[g].append(
            {
                "project_id": row["project_id"],
                "cut_index": row["cut_index"],
                "clip_index": row["clip_index"],
                "style_profile": row.get("style_profile"),
                "camera_move": row.get("camera_move"),
                "clarity_score": row["clarity_score"],
                "spoken_narration": row.get("spoken_narration"),
                "intended_scene": row.get("intended_scene"),
                "prompt": row["prompt"],
            }
        )
    if isinstance(prev_golden_by_g, dict):
        for g_prev, items_prev in prev_golden_by_g.items():
            if not isinstance(items_prev, list):
                continue
            for it_p in items_prev:
                if not isinstance(it_p, dict) or not _is_archived_off_disk_pid(it_p.get("project_id")):
                    continue
                gk_p = (
                    str(it_p.get("project_id") or ""),
                    int(it_p.get("cut_index") or 0),
                    int(it_p.get("clip_index") or 0),
                )
                if gk_p not in seen_golden_keys:
                    seen_golden_keys.add(gk_p)
                    golden_cands_by_g[str(g_prev)].append(dict(it_p))
    golden_by_grammar: dict[str, list[dict[str, Any]]] = {
        g: sorted(arr, key=lambda x: -float(x.get("clarity_score") or 0.0))[:25]
        for g, arr in sorted(golden_cands_by_g.items())
        if arr
    }
    _atomic_write_text(
        golden_bank_path,
        json.dumps(
            {
                "updated_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
                "total_golden_prompts": sum(len(v) for v in golden_by_grammar.values()),
                "by_grammar": dict(golden_by_grammar),
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
    )

    # 2. analogies_registry.json
    analogies_path = paths["packs_dir"] / "analogies_registry.json"
    prev_analogies = _read_json(analogies_path).get("analogies") or []
    analogies_list: list[dict[str, Any]] = []
    seen_analogies: set[tuple[str, str]] = set()
    for ep in episodes:
        pid = str(ep.get("project_id") or "")
        ep_analogy_locks = ep.get("analogy_locks")
        if not isinstance(ep_analogy_locks, list):
            ep_dir = Path(str(ep["project_dir"])) if ep.get("project_dir") else (p_root / pid)
            ep_analogy_locks = _read_json(ep_dir / "03_visuals" / "episode_qa_contract.json").get("analogy_locks") or []
        ep_cuts = [r for r in ledger if r.get("project_id") == pid]
        for al in ep_analogy_locks:
            key = (pid, str(al.get("spoken_phrase") or ""))
            if key in seen_analogies:
                continue
            seen_analogies.add(key)
            bound_nums = {int(x) for x in (al.get("bound_clip_numbers") or [])}
            matched_cuts = [r for r in ep_cuts if int(r.get("clip_index") or -1) in bound_nums]
            c_score = round(float(np.mean([float(m["clarity_score"]) for m in matched_cuts])), 1) if matched_cuts else None
            analogies_list.append(
                {
                    "project_id": pid,
                    "dossier": ep.get("dossier"),
                    "style_profile": ep.get("style_profile"),
                    "sentence_index": al.get("sentence_index"),
                    "spoken_phrase": al.get("spoken_phrase"),
                    "sentence": al.get("sentence"),
                    "cv_signature": al.get("cv_signature"),
                    "bound_clip_numbers": sorted(bound_nums),
                    "clarity_score": c_score,
                    "sample_prompt": (matched_cuts[0].get("prompt") if matched_cuts else None),
                    "clip_path": (matched_cuts[0].get("clip_path") if matched_cuts else None),
                }
            )
    if isinstance(prev_analogies, list):
        for al_p in prev_analogies:
            if not isinstance(al_p, dict) or not _is_archived_off_disk_pid(al_p.get("project_id")):
                continue
            key_p = (str(al_p.get("project_id") or ""), str(al_p.get("spoken_phrase") or ""))
            if key_p not in seen_analogies:
                seen_analogies.add(key_p)
                analogies_list.append(dict(al_p))
    analogies_list.sort(key=lambda x: (str(x.get("project_id") or ""), int(x.get("sentence_index") or 0)))
    _atomic_write_text(
        analogies_path,
        json.dumps(
            {
                "updated_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
                "count": len(analogies_list),
                "analogies": analogies_list,
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
    )

    # 3. brain_models_registry.json
    brain_path = paths["packs_dir"] / "brain_models_registry.json"
    prev_brains = _read_json(brain_path).get("brain_models") or []
    brain_grammars = {
        "porcelain_living_brain",
        "lowpoly_matte_brain",
        "arch_brain_maquette",
        "frosted_crystal_specimen",
        "brain_void",
        "expressive_xray_brain",
        "vinyl_crystal_brain_reveal",
    }
    brain_entries: list[dict[str, Any]] = []
    seen_brains: set[tuple[str, int, str]] = set()
    for row in ledger:
        if str(row.get("grammar") or "") in brain_grammars:
            bk = (str(row["project_id"]), int(row["clip_index"]), str(row.get("grammar") or ""))
            if bk in seen_brains:
                continue
            seen_brains.add(bk)
            brain_entries.append(
                {
                    "project_id": row["project_id"],
                    "dossier": row.get("dossier"),
                    "style_profile": row.get("style_profile"),
                    "clip_index": row["clip_index"],
                    "grammar": row["grammar"],
                    "brain_mode": row.get("brain_mode"),
                    "brain_region": row.get("brain_region"),
                    "camera_move": row.get("camera_move"),
                    "clarity_score": row.get("clarity_score"),
                    "passed": row.get("passed"),
                    "spoken_narration": row.get("spoken_narration"),
                    "prompt": row.get("prompt"),
                    "clip_path": row.get("clip_path"),
                }
            )
    if isinstance(prev_brains, list):
        for br_p in prev_brains:
            if not isinstance(br_p, dict) or not _is_archived_off_disk_pid(br_p.get("project_id")):
                continue
            bk_p = (
                str(br_p.get("project_id") or ""),
                int(br_p.get("clip_index") or 0),
                str(br_p.get("grammar") or ""),
            )
            if bk_p not in seen_brains:
                seen_brains.add(bk_p)
                brain_entries.append(dict(br_p))
    brain_entries.sort(key=lambda x: (str(x.get("project_id") or ""), int(x.get("clip_index") or 0)))
    _atomic_write_text(
        brain_path,
        json.dumps(
            {
                "updated_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
                "count": len(brain_entries),
                "brain_models": brain_entries,
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
    )

    # 4. locations_and_props_registry.json
    loc_path = paths["packs_dir"] / "locations_and_props_registry.json"
    prev_locs = _read_json(loc_path).get("locations") or []
    loc_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in ledger:
        loc_id = str(row.get("location_id") or "").strip()
        if loc_id:
            loc_groups[loc_id].append(row)
    prev_locs_by_id: dict[str, dict[str, Any]] = {}
    if isinstance(prev_locs, list):
        for lp_entry in prev_locs:
            if not isinstance(lp_entry, dict):
                continue
            lid_p = str(lp_entry.get("location_id") or "").strip()
            archived_pids = [p for p in (lp_entry.get("project_ids") or []) if _is_archived_off_disk_pid(p)]
            if lid_p and archived_pids:
                prev_locs_by_id[lid_p] = {**lp_entry, "project_ids": archived_pids}
    all_loc_ids = sorted(set(loc_groups) | set(prev_locs_by_id))
    locations_list: list[dict[str, Any]] = []
    for loc_id in all_loc_ids:
        items = loc_groups.get(loc_id) or []
        prev_l = prev_locs_by_id.get(loc_id)
        if items:
            scores = [float(x["clarity_score"]) for x in items if x.get("clarity_score") is not None]
            best = max(items, key=lambda x: float(x.get("clarity_score") or 0.0))
            merged_pids = sorted(
                {str(x["project_id"]) for x in items}
                | (set(prev_l.get("project_ids") or []) if prev_l else set())
            )
            merged_styles = sorted(
                {str(x.get("style_profile") or "") for x in items if x.get("style_profile")}
                | ({str(s) for s in (prev_l.get("style_profiles") or []) if s} if prev_l else set())
            )
            locations_list.append(
                {
                    "location_id": loc_id,
                    "project_ids": merged_pids,
                    "style_profiles": merged_styles,
                    "cut_appearances": len(items) + (int(prev_l.get("cut_appearances") or 0) if prev_l else 0),
                    "mean_clarity_score": round(float(np.mean(scores)), 1) if scores else (prev_l.get("mean_clarity_score") if prev_l else None),
                    "sample_scene": best.get("intended_scene") or (prev_l.get("sample_scene") if prev_l else None),
                    "sample_prompt": best.get("prompt") or (prev_l.get("sample_prompt") if prev_l else None),
                    "sample_clip_path": best.get("clip_path") or (prev_l.get("sample_clip_path") if prev_l else None),
                }
            )
        elif prev_l:
            locations_list.append(dict(prev_l))
    _atomic_write_text(
        loc_path,
        json.dumps(
            {
                "updated_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
                "count": len(locations_list),
                "locations": locations_list,
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
    )

    # 5. QA Analytics Summary & Markdown Report
    def _group_stats(key_fn) -> dict[str, dict[str, Any]]:
        buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for r in ledger:
            buckets[str(key_fn(r) or "unknown")].append(r)
        out_s: dict[str, dict[str, Any]] = {}
        for k, arr in sorted(buckets.items()):
            sc = [float(x["clarity_score"]) for x in arr if x.get("clarity_score") is not None]
            weak = sum(1 for x in arr if not x.get("passed"))
            out_s[k] = {
                "cuts": len(arr),
                "weak_cuts": weak,
                "pass_rate_pct": round(100.0 * (len(arr) - weak) / max(1, len(arr)), 1),
                "mean_clarity": round(float(np.mean(sc)), 1) if sc else 0.0,
                "min_clarity": round(float(np.min(sc)), 1) if sc else 0.0,
            }
        return out_s

    by_grammar = _group_stats(lambda r: r.get("grammar"))
    by_camera = _group_stats(lambda r: r.get("camera_move"))
    by_act = _group_stats(lambda r: f"act_{r.get('act')}")
    defect_counter: Counter[str] = Counter()
    for r in ledger:
        for d in (r.get("defects") or []):
            defect_counter[d.split("(")[0].split("=")[0]] += 1

    voice_buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for ep in episodes:
        vp_key = str(ep.get("voice_preset") or "unspecified")
        voice_buckets[vp_key].append(ep)
    by_voice_preset = {
        vp_k: {
            "episodes": len(arr),
            "mean_wpm": round(float(np.mean([float(x["wpm"]) for x in arr if x.get("wpm") is not None])), 1)
            if any(x.get("wpm") is not None for x in arr)
            else None,
            "mean_clarity": round(
                float(np.mean([float(x["posthoc_mean_clarity"]) for x in arr if x.get("posthoc_mean_clarity") is not None])),
                1,
            )
            if any(x.get("posthoc_mean_clarity") is not None for x in arr)
            else None,
        }
        for vp_k, arr in sorted(voice_buckets.items())
    }

    all_scores = [float(r["clarity_score"]) for r in ledger if r.get("clarity_score") is not None]
    analytics = {
        "updated_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "episodes_indexed": len(episodes),
        "total_cuts_evaluated": len(ledger),
        "overall_mean_clarity": round(float(np.mean(all_scores)), 1) if all_scores else None,
        "overall_min_clarity": round(float(np.min(all_scores)), 1) if all_scores else None,
        "golden_prompts_banked": sum(len(v) for v in golden_by_grammar.values()),
        "analogies_indexed": len(analogies_list),
        "brain_models_indexed": len(brain_entries),
        "locations_indexed": len(locations_list),
        "episodes_by_voice_preset": by_voice_preset,
        "clarity_by_grammar": by_grammar,
        "clarity_by_camera_move": by_camera,
        "clarity_by_act": by_act,
        "top_defect_modes": [{"defect": k, "count": v} for k, v in defect_counter.most_common(12)],
    }
    _atomic_write_text(paths["analytics_json"], json.dumps(analytics, indent=2, ensure_ascii=False) + "\n")

    md_lines = [
        "# ALL ABOUT BRAIN — Accumulated QA & Reuse Analytics Report",
        "",
        f"- **Episodes Indexed**: `{len(episodes)}`",
        f"- **Evaluated Cuts in Ledger**: `{len(ledger)}`",
        f"- **Overall Mean Clarity Score**: `{analytics['overall_mean_clarity']}`",
        f"- **Golden Prompts Banked (`>= 82.0`)**: `{analytics['golden_prompts_banked']}`",
        f"- **Reusable Packs**: `{len(analogies_list)}` analogies · `{len(brain_entries)}` brain models · `{len(locations_list)}` locations",
        "",
        "## 1. Indexed Episodes",
        "| Project ID | Schema | Profile | Rate / Speed | WPM | Duration | Cuts | R64 Mean Clarity | Status |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for ep in episodes:
        md_lines.append(
            f"| `{ep.get('project_id')}` | `v{ep.get('schema_version')}` | `{ep.get('style_profile')}` | "
            f"`{ep.get('tts_rate') or 'native'}` (`{ep.get('tts_speed') or 1.0}x`) | `{ep.get('wpm') or '-'}` | "
            f"`{ep.get('duration_sec') or '-'}s` | `{ep.get('cut_count') or '-'}` | "
            f"`{ep.get('posthoc_mean_clarity') or '-'}` | "
            f"`{'PASS' if ep.get('posthoc_passed') else ('PENDING' if ep.get('posthoc_passed') is None else 'WEAK')}` |"
        )
    md_lines.extend(
        [
            "",
            "## 2. Expressive Clarity by Visual Grammar",
            "| Grammar | Cuts | Pass Rate | Mean Clarity | Min Clarity |",
            "|---|---|---|---|---|",
        ]
    )
    for g_name, st in by_grammar.items():
        md_lines.append(
            f"| `{g_name}` | `{st['cuts']}` | `{st['pass_rate_pct']}%` | `{st['mean_clarity']}` | `{st['min_clarity']}` |"
        )
    md_lines.extend(
        [
            "",
            "## 3. Expressive Clarity by Camera Move",
            "| Camera Move | Cuts | Pass Rate | Mean Clarity | Min Clarity |",
            "|---|---|---|---|---|",
        ]
    )
    for c_name, st in by_camera.items():
        md_lines.append(
            f"| `{c_name}` | `{st['cuts']}` | `{st['pass_rate_pct']}%` | `{st['mean_clarity']}` | `{st['min_clarity']}` |"
        )
    _atomic_write_text(paths["analytics_md"], "\n".join(md_lines) + "\n")

    return analytics


def sync_all_projects_to_knowledge_base(
    projects_dir: Path | None = None,
    kb_dir: Path | None = None,
    run_missing_posthoc: bool = False,
    prune_missing_projects: bool = True,
    include_failed: bool = False,
    full_rescan: bool = False,
) -> dict[str, Any]:
    """
    Scans assembled projects under `BCI_Shorts_Channel/projects/` and indexes them into `knowledge_base/`.
    Uses fast mtime/size-gated incremental sync by default (`full_rescan=False`) so unchanged historical
    projects on `fuse.rclone` incur zero file reads or SHA-256 re-hashing.
    """
    p_root = Path(projects_dir or PROJECTS_DIR)
    paths = ensure_knowledge_base_layout(kb_dir)
    synced: list[str] = []
    unchanged_cached: list[str] = []
    newly_synced: list[str] = []
    skipped_incomplete: list[str] = []
    skipped_failed: list[str] = []
    on_disk_names: set[str] = set()
    existing_episodes = _read_jsonl(paths["episodes_index"])
    existing_ep_by_id = {
        str(ep.get("project_id") or ""): ep
        for ep in existing_episodes
        if str(ep.get("project_id") or "")
    }
    existing_ledger_pids = {
        str(r.get("project_id") or "")
        for r in _read_jsonl(paths["clip_ledger"])
        if str(r.get("project_id") or "")
    }
    if p_root.exists():
        from concurrent.futures import ThreadPoolExecutor

        p_dirs = sorted(d for d in p_root.iterdir() if d.is_dir() and not d.name.startswith("."))
        on_disk_names = {d.name for d in p_dirs}

        def _probe_kb_dir(d: Path) -> tuple[Path, bool, bool, str]:
            final_mp4 = d / "05_assembly" / "final_shorts_1080x1920.mp4"
            ph_path = d / "05_assembly" / POSTHOC_SEMANTIC_QA_REPORT_FILENAME
            try:
                has_final_mp4 = final_mp4.is_file() and final_mp4.stat().st_size > 0
            except OSError:
                has_final_mp4 = False
            try:
                has_archived_posthoc = ph_path.is_file() and ph_path.stat().st_size > 0
            except OSError:
                has_archived_posthoc = False
            sig = _compute_project_kb_signature(d) if ((has_final_mp4 or has_archived_posthoc) and not full_rescan) else ""
            return d, has_final_mp4, has_archived_posthoc, sig

        from pipeline.hardware_profile import resolve_cpu_budget

        with ThreadPoolExecutor(max_workers=resolve_cpu_budget()) as pool:
            probed_dirs = list(pool.map(_probe_kb_dir, p_dirs))

        for d, has_final_mp4, has_archived_posthoc, cur_sig in probed_dirs:
            ph_path = d / "05_assembly" / POSTHOC_SEMANTIC_QA_REPORT_FILENAME
            if not has_final_mp4 and not has_archived_posthoc:
                skipped_incomplete.append(d.name)
                continue
            needs_missing_posthoc = bool(run_missing_posthoc and has_final_mp4 and not has_archived_posthoc)
            if not full_rescan and not needs_missing_posthoc:
                prev_ep = existing_ep_by_id.get(d.name)
                has_ledger_cov = (
                    (d.name in existing_ledger_pids)
                    or (prev_ep.get("posthoc_passed") is None)
                    or not int(prev_ep.get("cut_count") or 0)
                ) if prev_ep else False
                if prev_ep is not None and prev_ep.get("kb_sync_sig") == cur_sig and has_ledger_cov:
                    if not include_failed and (
                        prev_ep.get("posthoc_passed") is False or prev_ep.get("autopsy_passed") is False
                    ):
                        skipped_failed.append(d.name)
                        continue
                    unchanged_cached.append(d.name)
                    synced.append(d.name)
                    continue
            ph_rep = None
            if needs_missing_posthoc:
                try:
                    from pipeline.posthoc_qa import resolve_project_final_mp4, run_posthoc_semantic_qa

                    resolve_project_final_mp4(d)
                    ph_rep = run_posthoc_semantic_qa(d, render_strips=True, run_asr_sync=False, save_report=True)
                except Exception:  # noqa: BLE001
                    ph_rep = None
            ph_doc = ph_rep if isinstance(ph_rep, dict) else _read_json(ph_path)
            autopsy_doc = _read_json(d / "05_assembly" / "video_autopsy_report.json")
            if not include_failed:
                if (ph_doc and ph_doc.get("passed") is False) or (autopsy_doc and autopsy_doc.get("passed") is False):
                    skipped_failed.append(d.name)
                    continue
            sync_project_to_knowledge_base(
                d,
                posthoc_report=ph_rep,
                kb_dir=kb_dir,
                write_asset_library=(kb_dir is None),
                recompile_aggregates=False,
            )
            newly_synced.append(d.name)
            synced.append(d.name)

    pruned_any = False
    if prune_missing_projects:
        archived_valid_ids = {
            str(ep.get("project_id") or "")
            for ep in existing_episodes
            if str(ep.get("project_id") or "")
            and str(ep.get("project_id") or "") not in on_disk_names
            and ep.get("posthoc_passed") is not False
        }
        valid_ids = set(synced) | archived_valid_ids
        pruned_any = bool(set(existing_ep_by_id) - valid_ids)
        if newly_synced or full_rescan or pruned_any:
            _upsert_jsonl(
                paths["episodes_index"],
                [],
                valid_project_ids=valid_ids,
                sort_key=lambda x: str(x.get("project_id") or ""),
            )
            _upsert_jsonl(
                paths["clip_ledger"],
                [],
                valid_project_ids=valid_ids,
                sort_key=lambda x: (str(x.get("project_id") or ""), int(x.get("cut_index") or 0)),
            )

    if not newly_synced and not full_rescan and not pruned_any and paths["analytics_json"].is_file():
        agg = _read_json(paths["analytics_json"])
    else:
        agg = recompile_knowledge_aggregates(kb_dir=kb_dir, projects_dir=p_root)
    return {
        "synced_projects": synced,
        "newly_synced_projects": newly_synced,
        "unchanged_cached_projects": unchanged_cached,
        "skipped_incomplete": skipped_incomplete,
        "skipped_failed": skipped_failed,
        "count": len(synced),
        "analytics": agg,
    }


def query_knowledge_base(
    pack: str = "clips",
    query: str = "",
    grammar: str | None = None,
    camera_move: str | None = None,
    min_clarity: float | None = None,
    style_profile: str | None = None,
    limit: int = 20,
    kb_dir: Path | None = None,
    asset_index_path: Path | None = None,
) -> list[dict[str, Any]]:
    """
    Unified search across accumulated reusable assets & QA telemetry:
      - `pack="clips"`: Searches `asset_library/index.jsonl`
      - `pack="prompts"`: Searches `clip_clarity_ledger.jsonl` sorted by `clarity_score`
      - `pack="analogies"`: Searches `reusable_packs/analogies_registry.json`
      - `pack="brain_models"`: Searches `reusable_packs/brain_models_registry.json`
      - `pack="locations"`: Searches `reusable_packs/locations_and_props_registry.json`
    """
    paths = ensure_knowledge_base_layout(kb_dir)
    pack_norm = str(pack or "clips").strip().lower()
    terms = [t for t in re.split(r"\W+", str(query or "").lower()) if t]

    if pack_norm == "clips":
        return search_library(
            query=query,
            index_path=asset_index_path or ASSET_INDEX_PATH,
            limit=limit,
            grammar=grammar,
            min_clarity=min_clarity,
            style_profile=style_profile,
        )

    if pack_norm == "prompts":
        rows = _read_jsonl(paths["clip_ledger"])
    elif pack_norm == "analogies":
        rows = _read_json(paths["packs_dir"] / "analogies_registry.json").get("analogies") or []
    elif pack_norm in ("brain", "brain_models"):
        rows = _read_json(paths["packs_dir"] / "brain_models_registry.json").get("brain_models") or []
    elif pack_norm == "locations":
        rows = _read_json(paths["packs_dir"] / "locations_and_props_registry.json").get("locations") or []
    else:
        raise ValueError(f"Unsupported pack={pack!r}; choose clips | prompts | analogies | brain_models | locations")

    hits: list[tuple[float, dict[str, Any]]] = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        if grammar and str(r.get("grammar") or "").lower() != grammar.strip().lower():
            continue
        if camera_move and str(r.get("camera_move") or "").lower() != camera_move.strip().lower():
            continue
        if style_profile:
            sp = str(r.get("style_profile") or "")
            sps = [str(x).lower() for x in (r.get("style_profiles") or [])]
            if sp.lower() != style_profile.strip().lower() and style_profile.strip().lower() not in sps:
                continue
        if min_clarity is not None:
            cs = r.get("clarity_score") if r.get("clarity_score") is not None else r.get("mean_clarity_score")
            if cs is None or float(cs) < float(min_clarity):
                continue
        hay = json.dumps(r, ensure_ascii=False).lower()
        kw_score = float(sum(hay.count(t) for t in terms)) if terms else 1.0
        if kw_score > 0:
            c_val = float(r.get("clarity_score") or r.get("mean_clarity_score") or 0.0)
            hits.append((kw_score + c_val * 0.02, r))

    hits.sort(key=lambda x: -x[0])
    return [r for _, r in hits[:limit]]


__all__ = [
    "ensure_knowledge_base_layout",
    "query_knowledge_base",
    "recompile_knowledge_aggregates",
    "sync_all_projects_to_knowledge_base",
    "sync_project_to_knowledge_base",
]
