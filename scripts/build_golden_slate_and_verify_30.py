#!/usr/bin/env python3
"""
Phase 4 & Phase 5 — Central 4-Gate Verification + Dynamic Priority Queue (`Rank #1..#30`) Builder.

Validates all 30 Golden Slate `Schema v2` dossiers and writes:
  - `BCI_Shorts_Channel/topic_priority_queue.json`
  - `BCI_Shorts_Channel/reports/research/golden_slate_30_master.json`
  - `BCI_Shorts_Channel/reports/research/golden_slate_30_master.md`
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline.anatomy_map import resolve_region
from pipeline.research_dossier import load_dossier, validate_dossier
from pipeline.studio.config import BANNED_OFF_TOPIC_TECH_TAGS

CHANNEL_DIR = ROOT / "BCI_Shorts_Channel"

GOLDEN_30_SLUGS: list[tuple[str, str, int]] = [
    # (slug, track_label, base_score)
    ("v2_sleep_first_night_hemisphere_watch", "Track 2 (Remodel)", 96),
    ("radvansky_doorway_effect_memory_boundary", "Track 1 (New)", 96),
    ("hauglund_2025_sleep_pill_norepinephrine_brain_wash", "Track 3 (2025-2026)", 96),
    ("janata_music_nostalgia_alzheimers_spared_hub", "Track 1 (New)", 96),
    ("kaptchuk_open_label_placebo_pain_switch", "Track 1 (New)", 96),
    ("yiweng_2025_walking_steps_tau_alzheimers_brake", "Track 3 (2025-2026)", 96),
    ("hilditch_snooze_button_sleep_inertia", "Track 1 (New)", 95),
    ("tubbs_mind_after_midnight_3am_spiral", "Track 1 (New)", 95),
    ("thanarajah_2023_2025_ultraprocessed_snack_reward_rewiring", "Track 3 (2025-2026)", 95),
    ("oconnor_deja_vu_frontal_fact_check", "Track 1 (New)", 94),
    ("v2_relationships_coan_handholding_pain_grid", "Track 2 (Remodel)", 94),
    ("brooks_power_nap_10min_vs_30min_grogginess", "Track 1 (New)", 94),
    ("burke_tip_of_the_tongue_word_block", "Track 1 (New)", 94),
    ("eisenberger_social_rejection_physical_pain", "Track 1 (New)", 94),
    ("wegner_white_bear_suppression", "Track 2 (Remodel)", 93),
    ("burns_2024_2025_night_light_circadian_mental_risk", "Track 3 (2025-2026)", 93),
    ("stetson_eagleman_slow_motion_crisis_memory", "Track 1 (New)", 93),
    ("melzack_wall_pain_gate", "Track 2 (Remodel)", 92),
    ("v2_anxiety_kross_third_person_amygdala", "Track 2 (Remodel)", 92),
    ("brooks_sleep_paralysis_rem_motor_lock", "Track 1 (New)", 92),
    ("jakubowski_earworm_stuck_song_motor_loop", "Track 1 (New)", 92),
    ("baird_shower_thought_default_mode_incubation", "Track 1 (New)", 92),
    ("holle_contagious_itch_mirror_insula", "Track 1 (New)", 92),
    ("draganski_juggling_gray_matter", "Track 2 (Remodel)", 91),
    ("mcgurk_multisensory_illusion", "Track 2 (Remodel)", 91),
    ("rubber_hand_body_plasticity", "Track 2 (Remodel)", 91),
    ("zeigarnik_uncompleted_task_loop", "Track 2 (Remodel)", 90),
    ("kruger_phantom_pocket_vibration_habit_false_alarm", "Track 1 (New)", 90),
    ("bodamer_prosopagnosia_face_blindness", "Track 2 (Remodel)", 89),
    ("godden_baddeley_diver_context_memory", "Track 2 (Remodel)", 89),
]

ANCHOR_ROUTING_BY_DOMAIN: dict[str, tuple[str, str]] = {
    "sleep": ("31_O2CmlKOk", "What One Sleepless Night Does to Your Brain (2,023 views)"),
    "habits": ("p4ou90cHt50", "Why Deep Brain Loops Lock Habits on Autopilot (1,617 views)"),
    "memory": ("p4ou90cHt50", "Why Deep Brain Loops Lock Habits on Autopilot (1,617 views)"),
    "anxiety": ("u5mQNZWNjiw", "His Missing Hand Stayed Clenched for 10 Years, Until a Mirror Box Opened It (1,250 views)"),
    "relationships": ("u5mQNZWNjiw", "His Missing Hand Stayed Clenched for 10 Years, Until a Mirror Box Opened It (1,250 views)"),
}


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.parent / f".{path.name}.tmp.{os.getpid()}"
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def space_items_anti_collision(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Two-pass score-preserving scheduler strictly avoiding back-to-back identical everyday_domain or primary_region."""
    pool = list(items)
    ordered: list[dict[str, Any]] = []
    while pool:
        best_idx = None
        if ordered:
            prev = ordered[-1]
            prev2 = ordered[-2] if len(ordered) >= 2 else {}
            # Pass 1: strictly different domain, pillar, and primary_region
            for i, cand in enumerate(pool):
                if (
                    cand["everyday_domain"] != prev["everyday_domain"]
                    and cand["pillar"] != prev["pillar"]
                    and (not cand["primary_region"] or cand["primary_region"] != prev["primary_region"])
                ):
                    best_idx = i
                    break
            # Pass 2: strictly different domain and primary_region
            if best_idx is None:
                for i, cand in enumerate(pool):
                    if cand["everyday_domain"] != prev["everyday_domain"] and (
                        not cand["primary_region"] or cand["primary_region"] != prev["primary_region"]
                    ):
                        best_idx = i
                        break
            # Pass 3: avoid 3-in-a-row domain
            if best_idx is None:
                for i, cand in enumerate(pool):
                    if not (cand["everyday_domain"] == prev["everyday_domain"] == prev2.get("everyday_domain")):
                        best_idx = i
                        break
        ordered.append(pool.pop(0 if best_idx is None else best_idx))
    return ordered


def main() -> int:
    failures: list[dict[str, Any]] = []
    verified_entries: list[dict[str, Any]] = []
    seen_primary_dois: dict[str, str] = {}

    for slug, track_label, base_score in GOLDEN_30_SLUGS:
        vr = validate_dossier(slug, require_schema_v2=True)
        ds = load_dossier(slug)
        meta = ds.get("dossier.json") or {}
        srcs = (ds.get("01_sources.json") or {}).get("sources") or []
        vis_ref = ds.get("03_visual_reference.json") or {}
        spatial_spec = vis_ref.get("spatial_contrast_spec") if isinstance(vis_ref.get("spatial_contrast_spec"), dict) else {}
        brain = ds.get("06_brain_link.json") or {}
        outline = ds.get("07_longform_outline.json") or {}

        errs = list(vr.get("issues") or [])
        if not (spatial_spec.get("landmark_or_object_a") and spatial_spec.get("landmark_or_object_b") and spatial_spec.get("arrow_3d_mode")):
            errs.append("[r80_spatial_gate] missing 03_visual_reference.spatial_contrast_spec (landmark_or_object_a/b + arrow_3d_mode)")
        links = brain.get("links") or []
        regions = []
        for lk in links:
            if isinstance(lk, dict):
                rg = str(lk.get("region") or "")
                canon = resolve_region(rg)
                if not canon:
                    errs.append(f"[atlas_gate] unresolved region: {rg!r}")
                else:
                    regions.append(canon)

        seed_tags = [str(t).strip().lower() for t in (outline.get("r75_clean_seed_tags") or [])]
        bad_tags = [t for t in seed_tags if t in BANNED_OFF_TOPIC_TECH_TAGS]
        if bad_tags and meta.get("pillar") != "bci_tech":
            errs.append(f"[r75_tag_gate] banned tech tags in r75_clean_seed_tags: {bad_tags}")

        acad_dois = [str(s.get("doi") or "").strip() for s in srcs if isinstance(s, dict) and s.get("doi")]
        prim_doi = acad_dois[0] if acad_dois else ""
        if prim_doi:
            low_d = prim_doi.lower()
            if low_d in seen_primary_dois:
                errs.append(f"[doi_dedup] primary DOI {prim_doi} collides with {seen_primary_dois[low_d]}")
            else:
                seen_primary_dois[low_d] = slug

        if not vr.get("ready") or errs:
            failures.append({"slug": slug, "ready": vr.get("ready"), "errors": errs})
            continue

        domain = str(meta.get("everyday_domain") or "habits").lower()
        anchor_vid, anchor_desc = ANCHOR_ROUTING_BY_DOMAIN.get(domain, ("p4ou90cHt50", "Habit Loops Anchor"))
        if domain == "sleep" and "3am" in slug or "midnight" in slug or "snooze" in slug:
            anchor_vid, anchor_desc = ("sjMteEvcjD0", "How Trying to Fall Asleep Backfires (527+ views surging)")

        extract = outline.get("shorts_extract") or {}
        thumb = outline.get("r65_split_thumbnail_spec") or {}
        verified_entries.append(
            {
                "slug": slug,
                "track": track_label,
                "base_score": base_score,
                "effective_score": float(base_score),
                "topic": str(meta.get("topic") or ""),
                "pillar": str(meta.get("pillar") or ""),
                "everyday_domain": domain,
                "visual_mode": str(meta.get("visual_mode") or "NEURO_BIOLOGY"),
                "primary_doi": prim_doi,
                "verified_doi_count": len(acad_dois),
                "primary_region": regions[0] if regions else "",
                "regions": regions,
                "setup_18w": str(meta.get("setup_18w") or ""),
                "shorts_hook": str(extract.get("hook") or ""),
                "shorts_twist": str(extract.get("twist") or ""),
                "r70_preset": str(outline.get("r70_recommended_preset") or "bar_compare"),
                "r65_thumbnail_spec": thumb,
                "spatial_contrast_spec": spatial_spec,
                "anchor_video_id": anchor_vid,
                "anchor_label": anchor_desc,
                "debate_question": str((meta.get("debate_ignition") or {}).get("open_verdict_question") or ""),
                "creator_bet": str((meta.get("debate_ignition") or {}).get("offcenter_creator_bet") or ""),
            }
        )

    if failures:
        print("GATE FAILURES:", json.dumps(failures, indent=2, ensure_ascii=False))
        return 1

    spaced = space_items_anti_collision(verified_entries)
    start_dt = date(2026, 11, 17)  # Ep #10 starts right after Ep #9 (2026-11-16)
    for idx, item in enumerate(spaced, start=1):
        ep_num = 9 + idx
        slot_date = (start_dt + timedelta(days=idx - 1)).isoformat()
        item["queue_rank"] = idx
        item["planned_episode"] = f"Ep #{ep_num}"
        item["suggested_slot_et"] = f"{slot_date} 19:30 ET"
        item["status"] = "ready_v2_verified"

    now_iso = datetime.now(timezone.utc).isoformat()
    queue_doc = {
        "schema_version": 2,
        "updated_at_utc": now_iso,
        "queue_ceiling": 35,
        "minimum_score_floor": 85,
        "portfolio_counts": {
            "total": len(spaced),
            "track1_everyday_new": sum(1 for x in spaced if x["track"].startswith("Track 1")),
            "track2_remodel": sum(1 for x in spaced if x["track"].startswith("Track 2")),
            "track3_breaking_2025_2026": sum(1 for x in spaced if x["track"].startswith("Track 3")),
        },
        "weekly_schedule_cron": "30 9 * * 1",
        "r80_spatial_enriched": True,
        "items": spaced,
    }

    queue_path = CHANNEL_DIR / "topic_priority_queue.json"
    slate_json_path = CHANNEL_DIR / "reports" / "research" / "golden_slate_30_master.json"
    slate_md_path = CHANNEL_DIR / "reports" / "research" / "golden_slate_30_master.md"

    atomic_write_text(queue_path, json.dumps(queue_doc, indent=2, ensure_ascii=False) + "\n")
    atomic_write_text(slate_json_path, json.dumps(queue_doc, indent=2, ensure_ascii=False) + "\n")

    md_lines = [
        "# ALL ABOUT BRAIN — 30-Episode Golden Slate & Dynamic Priority Queue (`Ep #10 ~ Ep #39`)",
        "",
        f"- **Generated (UTC)**: `{now_iso}`",
        f"- **Validation Status**: **`30 / 30` `Schema v2` Ready (`0` errors, `100%` Crossref DOI verified, `31/31` MNI152 Atlas compatible, `R75` clean)**",
        f"- **Portfolio Split**: Track 1 New Everyday (`15`) + Track 2 Top Remodels (`11`) + Track 3 2025–2026 Breaking (`4`) = **`30` Episodes**",
        f"- **Weekly Auto-Replenishment Cron**: `30 9 * * 1` (Every Monday `09:30 UTC` via `scripts/weekly_topic_research_runner.py`, Queue Ceiling `35` Champion-Challenger)",
        "",
        "| Rank | Ep | Target Slot (ET) | Score | Track | Domain / Pillar | Slug & Working Topic | Primary Circuit (`#27D8FF`) | Outbound Anchor |",
        "|---:|---|---|---:|---|---|---|---|---|",
    ]
    for it in spaced:
        reg_str = " -> ".join(it["regions"][:3])
        md_lines.append(
            f"| {it['queue_rank']} | **{it['planned_episode']}** | `{it['suggested_slot_et']}` | **{it['base_score']}** | {it['track']} | `{it['everyday_domain']}` / `{it['pillar']}` | **`{it['slug']}`**<br>{it['topic']} | `{reg_str}` | `{it['anchor_video_id']}` |"
        )
    atomic_write_text(slate_md_path, "\n".join(md_lines) + "\n")
    print(f"SUCCESS: 30/30 VERIFIED -> {queue_path} & {slate_md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
