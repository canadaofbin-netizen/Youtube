#!/usr/bin/env python3
"""
Weekly Rolling Topic Research & Dynamic Queue Re-Ranker (`R44` / `R75-C`).

Scheduled every Monday at `09:30 UTC` (`30 9 * * 1` — right after the `08:00` Daily Report & QA Scheduler,
with ZERO CDP `9222` browser usage):
1. Reads local `BCI_Shorts_Channel/reports/daily/*_studio_metrics.json` to compute 7-day domain performance
   multipliers (`sleep`, `habits`, `memory`, `anxiety`, `relationships`).
2. Prunes already-uploaded/scheduled episodes from `BCI_Shorts_Channel/topic_priority_queue.json`.
3. Re-ranks the remaining unproduced queue with fresh domain weights + anti-collision spacing.
4. Queries Crossref Public REST API (`from-pub-date` recent 60 days across `Nature`, `Science`, `PNAS`,
   `Current Biology`, `Nature Human Behaviour`, `Sleep`, `JAMA Neurology`) for fresh human brain discoveries,
   filtering out Gate-0 unsafe or R75 hardware-only papers and staging top candidates (`<= 7`) under the
   `35`-item Champion-Challenger ceiling.
5. Writes `BCI_Shorts_Channel/reports/research/<YYYY-MM-DD>_weekly_topic_refresh.{json,md}`.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.verify_topic_slate import space_items_anti_collision

CHANNEL_DIR = ROOT / "BCI_Shorts_Channel"
UA = "AllAboutBrainWeeklyRadar/2.0 (mailto:research@allaboutbrain.org)"
UNSAFE_RE = re.compile(
    r"\b(suicide|murder|homicide|corpse|autopsy|rats?|mice|mouse|rodents?|drosophila|zebrafish|macaques?|monkeys?)\b",
    re.IGNORECASE,
)
TECH_ONLY_WORDS = ("brain-computer interface", "intracortical electrode", "microelectrode array", "neuralink", "stentrode")


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.parent / f".{path.name}.tmp.{os.getpid()}"
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def compute_domain_multipliers() -> dict[str, float]:
    """Derives subtle data-driven priority bonuses (+0.0 to +3.0 pts) from recent Studio metrics snapshots."""
    bonuses = {"sleep": 2.0, "habits": 1.6, "memory": 1.5, "anxiety": 1.0, "relationships": 1.0}
    daily_dir = CHANNEL_DIR / "reports" / "daily"
    snaps = sorted(daily_dir.glob("*_studio_metrics.json"))[-7:]
    if not snaps:
        return bonuses
    domain_views: dict[str, int] = {k: 0 for k in bonuses}
    for sp in snaps:
        try:
            doc = json.loads(sp.read_text(encoding="utf-8"))
            for v in doc.get("videos") or doc.get("top_videos") or []:
                if not isinstance(v, dict):
                    continue
                ttl = str(v.get("title") or "").lower()
                vws = int(v.get("views") or 0)
                if any(w in ttl for w in ("sleep", "night", "nap", "snooze", "awake")):
                    domain_views["sleep"] = max(domain_views["sleep"], vws)
                elif any(w in ttl for w in ("habit", "autopilot", "loop", "choice")):
                    domain_views["habits"] = max(domain_views["habits"], vws)
                elif any(w in ttl for w in ("forgot", "memory", "taxi", "remember")):
                    domain_views["memory"] = max(domain_views["memory"], vws)
                elif any(w in ttl for w in ("hand", "pain", "fear", "breath")):
                    domain_views["anxiety"] = max(domain_views["anxiety"], vws)
        except Exception:
            continue
    max_v = max(domain_views.values()) if any(domain_views.values()) else 0
    if max_v > 0:
        for k, v in domain_views.items():
            bonuses[k] = round(0.5 + 2.5 * (v / max_v), 2)
    return bonuses


def discover_published_dois_and_slugs() -> tuple[set[str], set[str]]:
    pub_dois: set[str] = set()
    pub_slugs: set[str] = set()
    for rec_p in sorted((CHANNEL_DIR / "projects").glob("*/06_publish/upload_receipt.json")):
        try:
            r = json.loads(rec_p.read_text(encoding="utf-8"))
            if not r.get("video_id"):
                continue
            proj_dir = rec_p.parent.parent
            meta_p = rec_p.parent / "metadata.json"
            if meta_p.exists():
                m = json.loads(meta_p.read_text(encoding="utf-8"))
                for k in ("doi", "secondary_doi", "mechanism_doi"):
                    if m.get(k):
                        pub_dois.add(str(m[k]).lower().strip())
            plan_p = proj_dir / "02_script" / "visual_plan.json"
            if plan_p.exists():
                vp = json.loads(plan_p.read_text(encoding="utf-8"))
                if vp.get("dossier"):
                    pub_slugs.add(str(vp["dossier"]).strip())
        except Exception:
            continue
    return pub_dois, pub_slugs


def scan_fresh_crossref_candidates(days_back: int = 90, blacklist_dois: set[str] | None = None) -> list[dict[str, Any]]:
    blacklist = blacklist_dois or set()
    since_str = (date.today() - timedelta(days=days_back)).isoformat()
    queries = [
        ("sleep", "human sleep memory prefrontal hippocampus fMRI"),
        ("memory", "human episodic memory aging cognitive reserve hippocampus"),
        ("habits", "human habit dopamine striatum decision attention"),
        ("anxiety", "human emotion regulation amygdala placebo pain insula"),
    ]
    candidates: list[dict[str, Any]] = []
    seen = set(blacklist)
    for dom, q in queries:
        url = (
            f"https://api.crossref.org/works?rows=6&filter=from-pub-date:{since_str},type:journal-article"
            f"&query.bibliographic={urllib.parse.quote(q)}"
        )
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                items = ((json.loads(resp.read().decode("utf-8")).get("message") or {}).get("items")) or []
            for it in items:
                doi = str(it.get("DOI") or "").strip()
                raw_title = str((it.get("title") or [""])[0])
                title = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", raw_title)).strip()
                blob = f"{title} {str(it.get('abstract') or '')}".lower()
                if not doi or doi.lower() in seen or not title:
                    continue
                if UNSAFE_RE.search(blob) or any(bad in blob for bad in TECH_ONLY_WORDS):
                    continue
                seen.add(doi.lower())
                journal = str((it.get("container-title") or [""])[0])
                r80_hint = (
                    "split_hemisphere_watch"
                    if dom == "sleep"
                    else (
                        "adaptive_landmark_zigzag"
                        if dom == "memory"
                        else ("dual_speed_race_lanes" if dom == "anxiety" else "fixed_linear_corridor")
                    )
                )
                candidates.append(
                    {
                        "everyday_domain": dom,
                        "title": title,
                        "journal": journal,
                        "doi": doi,
                        "url": f"https://doi.org/{doi}",
                        "r80_arrow_3d_mode_hint": r80_hint,
                    }
                )
        except Exception:
            continue
    return candidates[:7]


def main() -> int:
    queue_path = CHANNEL_DIR / "topic_priority_queue.json"
    if not queue_path.exists():
        print(f"[WeeklyResearch] Queue file not found yet: {queue_path}")
        return 0

    q_doc = json.loads(queue_path.read_text(encoding="utf-8"))
    pub_dois, pub_slugs = discover_published_dois_and_slugs()
    bonuses = compute_domain_multipliers()

    active_items = []
    pruned = []
    for it in q_doc.get("items") or []:
        if it.get("slug") in pub_slugs or str(it.get("primary_doi") or "").lower() in pub_dois:
            pruned.append(it["slug"])
            continue
        dom = str(it.get("everyday_domain") or "habits")
        it["effective_score"] = round(float(it.get("base_score", 90)) + bonuses.get(dom, 1.0), 2)
        active_items.append(it)

    active_items.sort(key=lambda x: (-float(x["effective_score"]), x["slug"]))
    spaced = space_items_anti_collision(active_items)

    today_dt = date.today()
    for idx, it in enumerate(spaced, start=1):
        it["queue_rank"] = idx
        it["suggested_slot_et"] = f"{(today_dt + timedelta(days=idx)).isoformat()} 19:30 ET"

    used_dois = pub_dois | {str(x.get("primary_doi") or "").lower() for x in spaced}
    fresh_radar = scan_fresh_crossref_candidates(days_back=90, blacklist_dois=used_dois)

    now_iso = datetime.now(timezone.utc).isoformat()
    q_doc["updated_at_utc"] = now_iso
    q_doc["domain_velocity_bonuses"] = bonuses
    q_doc["items"] = spaced
    atomic_write_text(queue_path, json.dumps(q_doc, indent=2, ensure_ascii=False) + "\n")

    today_str = today_dt.isoformat()
    rep_json = CHANNEL_DIR / "reports" / "research" / f"{today_str}_weekly_topic_refresh.json"
    rep_md = CHANNEL_DIR / "reports" / "research" / f"{today_str}_weekly_topic_refresh.md"
    rep_payload = {
        "date": today_str,
        "generated_at_utc": now_iso,
        "pruned_published_slugs": pruned,
        "remaining_ready_queue_count": len(spaced),
        "queue_ceiling": int(q_doc.get("queue_ceiling", 35)),
        "slots_open_for_new_dossiers": max(0, min(7, int(q_doc.get("queue_ceiling", 35)) - len(spaced))),
        "domain_velocity_bonuses": bonuses,
        "top5_next_up": [
            {"rank": x["queue_rank"], "slug": x["slug"], "effective_score": x["effective_score"], "domain": x["everyday_domain"]}
            for x in spaced[:5]
        ],
        "fresh_crossref_radar_candidates": fresh_radar,
    }
    atomic_write_text(rep_json, json.dumps(rep_payload, indent=2, ensure_ascii=False) + "\n")

    md = [
        f"# Weekly Rolling Topic Research Refresh (`{today_str}`)",
        "",
        f"- **Remaining Ready `Schema v2` Queue**: **`{len(spaced)}`** (Ceiling: `{rep_payload['queue_ceiling']}`, Open Replenishment Slots: `{rep_payload['slots_open_for_new_dossiers']}`)",
        f"- **Auto-Pruned Published Slugs**: `{pruned}`",
        f"- **7-Day Studio Domain Bonuses**: `{json.dumps(bonuses)}`",
        "",
        "## Top 5 Next-Up Priority Queue",
    ]
    for x in spaced[:5]:
        md.append(f"1. **#{x['queue_rank']} `{x['slug']}`** (`{x['effective_score']} pts`, `{x['everyday_domain']}`) — {x['topic']}")
    md.append("")
    md.append("## Fresh 90-Day Crossref Human Neuro Radar Candidates")
    for c in fresh_radar:
        md.append(f"- **[{c['everyday_domain']}]** *{c['title']}* ({c['journal']}) — `{c['doi']}`")
    atomic_write_text(rep_md, "\n".join(md) + "\n")
    print(f"[WeeklyResearch] Queue re-ranked ({len(spaced)} ready) + radar report saved -> {rep_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
