#!/usr/bin/env python3
"""
Upgrade all 65 queued `porcelain_cinematic_v7` episodes to the Dual-Track Research & Reference
Conditioning architecture (`Track A: R67 Archival Reenactment` + `Track B: R66-Anchor Scene-Bible`):

  1. Audits every dossier's `04_media_refs.json` via the 4-Gate CV/Transcript/Metadata suitability
     classifier (`audit_dossier_media_suitability`) and persists `reenactment_track` + `track_subtier`.
  2. Compiles `populate_porcelain_reference_contract` onto every `diorama_v7_porcelain/visual_plan.json`
     (`cast`, `real_environment`, `environment_props`, `default_location_id`, `strict_room_continuity`,
     `reference_anchors`, and selective `~55–68%` `clip["reference_image"]` bindings).
  3. Re-renders `diorama_v7_porcelain/flow_all_in_one_prompts.json` directly (cleaning stale nested
     `diorama_v7_porcelain/03_visuals/` folders) and writes `reference_image_specs.json`.
  4. Syncs updated `visual_plan.json`, `flow_all_in_one_prompts.json`, and `reference_image_specs.json`
     into existing unproduced `BCI_Shorts_Channel/projects/<project_id>` folders (never touching
     published or rendered episodes).
  5. Verifies `validate_scene_state_continuity`, `validate_diorama_v7_prompts`,
     `validate_production_diorama_v6`, and `verify_pre_flow_contract` pass with 0 issues across 65/65.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from collections import Counter
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pipeline import cli, config
from pipeline.dynamic_episode_qa import verify_pre_flow_contract
from pipeline.flow_prompt_builder import (
    build_flow_prompts,
    validate_diorama_v7_prompts,
    write_flow_prompts_json,
)
from pipeline.porcelain_anchor_pack import populate_porcelain_reference_contract
from pipeline.prompt_quality_v5 import (
    validate_production_diorama_v6,
    validate_scene_state_continuity,
)
from pipeline.publish import validate_diorama_paradox_title
from pipeline.reference_image_qa import build_reference_image_specs
from pipeline.research_dossier import audit_dossier_media_suitability, dossier_dir


def _is_unproduced_project(proj_dir: Path) -> bool:
    if not proj_dir.is_dir():
        return False
    if (proj_dir / "06_publish" / "upload_receipt.json").exists():
        return False
    if (proj_dir / "05_assembly" / "final_shorts_1080x1920.mp4").exists():
        return False
    clips_dir = proj_dir / "03_visuals" / "flow_native_clips"
    if clips_dir.is_dir() and any(clips_dir.glob("clip_*.mp4")):
        return False
    ref_dir = proj_dir / "03_visuals" / "reference_images"
    if ref_dir.is_dir() and any(ref_dir.glob("ref_*.png")):
        return False
    return True




def _sync_unproduced_project(draft_dir: Path, project_id: str, *, check_only: bool) -> tuple[bool, list[str]]:
    if not project_id:
        return False, []
    proj_dir = Path(config.PROJECTS_DIR) / project_id
    if not _is_unproduced_project(proj_dir):
        return False, []

    dst_vis = proj_dir / "03_visuals"
    pairs = [
        (draft_dir / "visual_plan.json", dst_vis / "visual_plan.json"),
        (draft_dir / "flow_all_in_one_prompts.json", dst_vis / "flow_all_in_one_prompts.json"),
        (draft_dir / "reference_image_specs.json", dst_vis / "reference_image_specs.json"),
        (draft_dir / "script.json", proj_dir / "02_script" / "script.json"),
    ]
    out_of_sync = [
        dst.name
        for src, dst in pairs
        if src.exists() and ((not dst.exists()) or (src.read_bytes() != dst.read_bytes()))
    ]
    if not out_of_sync:
        return False, []
    if check_only:
        return False, [f"unproduced project {project_id} out of sync on {out_of_sync}"]

    dst_vis.mkdir(parents=True, exist_ok=True)
    (proj_dir / "02_script").mkdir(parents=True, exist_ok=True)
    for src, dst in pairs:
        if src.exists():
            shutil.copy2(src, dst)
    return True, []


def upgrade_one_queued_episode(
    item: dict[str, Any],
    *,
    check_only: bool = False,
    force_cv: bool = False,
) -> dict[str, Any]:
    slug = str(item["slug"]).strip()
    project_id = str(item.get("project_id") or "").strip()
    d_dir = dossier_dir(slug)
    draft_dir = Path(item["porcelain_dir"])
    vp_path = draft_dir / "visual_plan.json"

    suit = audit_dossier_media_suitability(
        d_dir,
        write_back=not check_only,
        use_cached=not force_cv,
    )
    track = str(suit.get("reenactment_track") or "track_b")
    subtier = str(suit.get("track_subtier") or "B_scene_bible_anchor")

    plan = json.loads(vp_path.read_text(encoding="utf-8"))
    before_txt = json.dumps(plan, sort_keys=True, ensure_ascii=False)
    plan["reenactment_track"] = track
    plan["track_subtier"] = subtier
    populate_porcelain_reference_contract(plan, dossier_dir=d_dir)
    after_txt = json.dumps(plan, sort_keys=True, ensure_ascii=False)
    plan_changed = before_txt != after_txt

    _, narrations, script_doc = cli._load_gate_inputs(draft_dir)
    built = build_flow_prompts(plan, narrations)
    specs_payload = build_reference_image_specs(plan, narrations)
    ref_specs = specs_payload.get("all_specs") or []
    specs_txt = json.dumps(specs_payload, indent=2, ensure_ascii=False) + "\n"

    prompts_path = draft_dir / "flow_all_in_one_prompts.json"
    specs_path = draft_dir / "reference_image_specs.json"
    stale_nested = draft_dir / "03_visuals"

    cleaned_nested = False
    if not check_only:
        if plan_changed:
            vp_path.write_text(json.dumps(plan, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        write_flow_prompts_json(draft_dir, built)
        if (not specs_path.exists()) or (specs_path.read_text(encoding="utf-8") != specs_txt):
            specs_path.write_text(specs_txt, encoding="utf-8")
        if stale_nested.is_dir():
            shutil.rmtree(stale_nested, ignore_errors=True)
            cleaned_nested = True

    did_sync, sync_issues = _sync_unproduced_project(draft_dir, project_id, check_only=check_only)

    issues: list[str] = []
    issues.extend(sync_issues)
    issues.extend(validate_scene_state_continuity(plan, built))
    issues.extend(validate_diorama_v7_prompts(built, plan))
    issues.extend(validate_production_diorama_v6(plan, narrations, built, script_doc=script_doc))
    issues.extend(verify_pre_flow_contract(plan, narrations, built, script_doc=script_doc))
    raw_title = str(script_doc.get("title") or plan.get("title") or "").strip()
    if raw_title:
        issues.extend(validate_diorama_paradox_title(raw_title))

    if not (config.MIN_REF_IMAGES_PER_PROJECT <= len(ref_specs) <= 10):
        issues.append(f"ref_specs count={len(ref_specs)} outside {config.MIN_REF_IMAGES_PER_PROJECT}..10")

    clips = [c for c in (plan.get("clips") or []) if isinstance(c, dict)]
    non_outro = [c for c in clips if str(c.get("cut_role") or "").lower() != "outro"]
    anchored = [c for c in non_outro if str(c.get("reference_image") or "").strip()]
    anchored_ratio = round(len(anchored) / max(1, len(non_outro)), 3)
    if not (0.35 <= anchored_ratio <= 0.88):
        issues.append(f"anchored_clip_ratio={anchored_ratio} outside 0.35..0.88")
    if check_only:
        if not prompts_path.exists():
            issues.append("missing direct flow_all_in_one_prompts.json")
        if not specs_path.exists():
            issues.append("missing direct reference_image_specs.json")
        if stale_nested.exists():
            issues.append("stale nested 03_visuals directory still present")
        if plan_changed:
            issues.append("visual_plan.json contract differs from canonical output")

    dedup_issues = list(dict.fromkeys(issues))
    return {
        "slug": slug,
        "project_id": project_id,
        "reenactment_track": track,
        "track_subtier": subtier,
        "primary_track_a_url": (suit.get("primary_track_a_media") or {}).get("url"),
        "clip_count": len(clips),
        "ref_spec_count": len(ref_specs),
        "anchored_clips": len(anchored),
        "anchored_clip_ratio": anchored_ratio,
        "plan_changed": plan_changed,
        "cleaned_nested": cleaned_nested,
        "synced_project": did_sync,
        "issues": dedup_issues,
    }


def main() -> int:
    from concurrent.futures import ThreadPoolExecutor, as_completed

    ap = argparse.ArgumentParser(description="Upgrade all 65 queued porcelain episodes to Dual-Track refs.")
    ap.add_argument("--check-only", action="store_true", help="Verify without writing files.")
    ap.add_argument("--force-cv", action="store_true", help="Recompute CV metrics even if cached in 04_media_refs.json.")
    ap.add_argument("--workers", type=int, default=8, help="Concurrent dossier worker threads.")
    args = ap.parse_args()

    q_path = Path(config.CHANNEL_ROOT) / "porcelain_rebalanced_queue.json"
    q_doc = json.loads(q_path.read_text(encoding="utf-8"))
    queue = q_doc.get("queue") or []

    track_counts: Counter[str] = Counter()
    subtier_counts: Counter[str] = Counter()
    spec_counts: list[int] = []
    anchor_ratios: list[float] = []
    changed_cnt = 0
    cleaned_cnt = 0
    synced_cnt = 0
    failed: list[dict[str, Any]] = []

    results_by_idx: dict[int, dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=max(1, int(args.workers))) as pool:
        fut_map = {
            pool.submit(
                upgrade_one_queued_episode,
                item,
                check_only=bool(args.check_only),
                force_cv=bool(args.force_cv),
            ): idx
            for idx, item in enumerate(queue)
        }
        done_n = 0
        for fut in as_completed(fut_map):
            idx = fut_map[fut]
            rep = fut.result()
            results_by_idx[idx] = rep
            done_n += 1
            status_tag = "FAIL" if rep["issues"] else "OK"
            print(
                f"[{done_n:02d}/{len(queue):02d}] {status_tag} {rep['slug']} -> "
                f"{rep['reenactment_track']} ({rep['track_subtier']}) specs={rep['ref_spec_count']} "
                f"anchored={rep['anchored_clip_ratio']:.2f}",
                file=sys.stderr,
                flush=True,
            )

    for idx, item in enumerate(queue):
        rep = results_by_idx[idx]
        track_counts[rep["reenactment_track"]] += 1
        subtier_counts[rep["track_subtier"]] += 1
        spec_counts.append(rep["ref_spec_count"])
        anchor_ratios.append(rep["anchored_clip_ratio"])
        if rep["plan_changed"]:
            changed_cnt += 1
        if rep["cleaned_nested"]:
            cleaned_cnt += 1
        if rep["synced_project"]:
            synced_cnt += 1
        if rep["issues"]:
            failed.append(rep)

        item["reenactment_track"] = rep["reenactment_track"]
        item["track_subtier"] = rep["track_subtier"]
        item["reference_spec_count"] = rep["ref_spec_count"]
        item["anchored_clip_ratio"] = rep["anchored_clip_ratio"]
        if rep["primary_track_a_url"]:
            item["primary_track_a_url"] = rep["primary_track_a_url"]
        else:
            item.pop("primary_track_a_url", None)

    if not args.check_only:
        q_doc["dual_track_summary"] = {
            "total_episodes": len(queue),
            "track_counts": dict(track_counts),
            "subtier_counts": dict(subtier_counts),
            "reference_spec_count_min_max": [min(spec_counts, default=0), max(spec_counts, default=0)],
            "anchored_clip_ratio_min_max": [min(anchor_ratios, default=0.0), max(anchor_ratios, default=0.0)],
            "anchored_clip_ratio_mean": round(sum(anchor_ratios) / max(1, len(anchor_ratios)), 3),
        }
        for p6 in q_doc.get("pilot_top_6") or []:
            match = next((it for it in queue if it.get("slug") == p6.get("slug")), None)
            if match:
                p6["reenactment_track"] = match["reenactment_track"]
                p6["track_subtier"] = match["track_subtier"]
                p6["reference_spec_count"] = match["reference_spec_count"]
                p6["anchored_clip_ratio"] = match["anchored_clip_ratio"]
        q_path.write_text(json.dumps(q_doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "mode": "check_only" if args.check_only else "upgraded",
                "total_episodes": len(queue),
                "track_counts": dict(track_counts),
                "subtier_counts": dict(subtier_counts),
                "plans_changed": changed_cnt,
                "nested_03_visuals_cleaned": cleaned_cnt,
                "unproduced_projects_synced": synced_cnt,
                "ref_specs_min_max": [min(spec_counts, default=0), max(spec_counts, default=0)],
                "anchored_ratio_min_max": [min(anchor_ratios, default=0.0), max(anchor_ratios, default=0.0)],
                "anchored_ratio_mean": round(sum(anchor_ratios) / max(1, len(anchor_ratios)), 3),
                "failed_count": len(failed),
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    if failed:
        for f in failed[:15]:
            print(f"  FAIL {f['slug']} ({f['project_id']}): {f['issues'][:5]}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
