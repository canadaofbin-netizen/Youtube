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
        lock_root = Path("/tmp") if (os.name != "nt" and Path("/tmp").exists()) else path.parent
        lock_root.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha1(resolved.encode("utf-8")).hexdigest()[:16]
        lock_file = lock_root / f".aab_kb_{digest}.lock"
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

    # Refresh asset_manifest.json (so per-clip clarity_score is persisted into asset_manifest & asset_library)
    if (p_dir / "03_visuals" / "flow_all_in_one_prompts.json").exists():
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

    # 1. prompts_golden_bank.json (passed cuts with clarity >= 82.0)
    golden_by_grammar: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in sorted(ledger, key=lambda r: -float(r.get("clarity_score") or 0.0)):
        if not row.get("passed") or float(row.get("clarity_score") or 0.0) < 82.0 or not row.get("prompt"):
            continue
        g = str(row.get("grammar") or "other")
        if len(golden_by_grammar[g]) < 25:
            golden_by_grammar[g].append(
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
    golden_bank_path = paths["packs_dir"] / "prompts_golden_bank.json"
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
    analogies_list: list[dict[str, Any]] = []
    seen_analogies: set[tuple[str, str]] = set()
    for ep in episodes:
        pid = str(ep.get("project_id") or "")
        ep_dir = Path(str(ep["project_dir"])) if ep.get("project_dir") else (p_root / pid)
        c_doc = _read_json(ep_dir / "03_visuals" / "episode_qa_contract.json")
        ep_cuts = [r for r in ledger if r.get("project_id") == pid]
        for al in (c_doc.get("analogy_locks") or []):
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
    analogies_path = paths["packs_dir"] / "analogies_registry.json"
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
    brain_grammars = {
        "porcelain_living_brain",
        "lowpoly_matte_brain",
        "arch_brain_maquette",
        "frosted_crystal_specimen",
        "brain_void",
    }
    brain_entries: list[dict[str, Any]] = []
    for row in ledger:
        if str(row.get("grammar") or "") in brain_grammars:
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
    brain_path = paths["packs_dir"] / "brain_models_registry.json"
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
    loc_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in ledger:
        loc_id = str(row.get("location_id") or "").strip()
        if loc_id:
            loc_groups[loc_id].append(row)
    locations_list: list[dict[str, Any]] = []
    for loc_id, items in sorted(loc_groups.items()):
        scores = [float(x["clarity_score"]) for x in items if x.get("clarity_score") is not None]
        best = max(items, key=lambda x: float(x.get("clarity_score") or 0.0))
        locations_list.append(
            {
                "location_id": loc_id,
                "project_ids": sorted({str(x["project_id"]) for x in items}),
                "style_profiles": sorted({str(x.get("style_profile") or "") for x in items if x.get("style_profile")}),
                "cut_appearances": len(items),
                "mean_clarity_score": round(float(np.mean(scores)), 1) if scores else None,
                "sample_scene": best.get("intended_scene"),
                "sample_prompt": best.get("prompt"),
                "sample_clip_path": best.get("clip_path"),
            }
        )
    loc_path = paths["packs_dir"] / "locations_and_props_registry.json"
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
) -> dict[str, Any]:
    """
    Scans assembled projects under `BCI_Shorts_Channel/projects/` and indexes them into `knowledge_base/`.
    Skips draft/incomplete directories lacking `05_assembly/final_shorts_1080x1920.mp4` and skips projects
    that explicitly failed `posthoc_semantic_qa_report.json` or `video_autopsy_report.json` unless `include_failed=True`.
    """
    p_root = Path(projects_dir or PROJECTS_DIR)
    paths = ensure_knowledge_base_layout(kb_dir)
    synced: list[str] = []
    skipped_incomplete: list[str] = []
    skipped_failed: list[str] = []
    if p_root.exists():
        p_dirs = sorted(d for d in p_root.iterdir() if d.is_dir() and not d.name.startswith("."))
        for d in p_dirs:
            final_mp4 = d / "05_assembly" / "final_shorts_1080x1920.mp4"
            if not final_mp4.exists() or final_mp4.stat().st_size == 0:
                skipped_incomplete.append(d.name)
                continue
            ph_path = d / "05_assembly" / POSTHOC_SEMANTIC_QA_REPORT_FILENAME
            ph_rep = None
            if run_missing_posthoc and not ph_path.exists():
                try:
                    from pipeline.posthoc_semantic_qa import resolve_project_final_mp4, run_posthoc_semantic_qa

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
            synced.append(d.name)

    if prune_missing_projects:
        valid_ids = set(synced)
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

    agg = recompile_knowledge_aggregates(kb_dir=kb_dir, projects_dir=p_root)
    return {
        "synced_projects": synced,
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
