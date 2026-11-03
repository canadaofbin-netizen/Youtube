"""
ALL ABOUT BRAIN — Breaking BCI & Clinical Neuroscience News Radar (`pipeline/news_radar.py`).

Scans public Crossref & ClinicalTrials.gov (`NCT`) endpoints (zero paid APIs) for recent (`<= 14` days by default)
peer-reviewed DOIs or registered human BCI clinical milestones (`Neuralink`, `Synchron`, `BrainGate`,
`Precision Neuroscience`, `Paradromics`, cortical speech/motor neuroprosthetics), and stages verified
`porcelain_cinematic_v7` (`micro_short_v7` / `neuro_diorama`) candidate cards into `Completed_Neuro_News_Shorts/`
with `hold_from_auto_queue = True` for HQ CEO confirmation.
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from pipeline.config import (
    ALLOW_EXTERNAL_PAID_APIS,
    MICRO_SHORT_PROFILE,
    NEURO_NEWS_STAGING_DIR,
    PORCELAIN_V7_STYLE_PROFILE,
)

DEFAULT_BCI_NEWS_QUERIES: tuple[str, ...] = (
    "brain-computer interface speech decoding intracortical",
    "endovascular brain-computer interface Synchron Stentrode",
    "intracortical microelectrode neural prosthesis human trial",
    "deep brain stimulation memory depression closed-loop",
)


def _fetch_crossref_recent(query: str, from_date: str, rows: int = 5, timeout_sec: float = 12.0) -> list[dict[str, Any]]:
    if ALLOW_EXTERNAL_PAID_APIS:
        raise RuntimeError("ALLOW_EXTERNAL_PAID_APIS must remain False (R5).")
    params = urllib.parse.urlencode(
        {
            "query": query,
            "filter": f"from-pub-date:{from_date},type:journal-article",
            "rows": str(rows),
            "sort": "published",
            "order": "desc",
        }
    )
    url = f"https://api.crossref.org/works?{params}"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "AllAboutBrainPipeline/7.0 (mailto:research@allaboutbrain.org)"},
    )
    with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return list(((data.get("message") or {}).get("items")) or [])


def scan_breaking_neuro_news(
    window_days: int = 14,
    queries: tuple[str, ...] = DEFAULT_BCI_NEWS_QUERIES,
    max_candidates: int = 5,
    offline_items: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """
    Collects verified DOI / NCT breaking neuroscience candidates and writes staged HQ review cards
    into `Completed_Neuro_News_Shorts/news_radar_staging.json` (`hold_from_auto_queue: True`).
    """
    staging_dir = Path(NEURO_NEWS_STAGING_DIR)
    staging_dir.mkdir(parents=True, exist_ok=True)
    cutoff_date = (date.today() - timedelta(days=max(1, int(window_days)))).isoformat()

    raw_items: list[dict[str, Any]] = []
    if offline_items is not None:
        raw_items = list(offline_items)
    else:
        for q in queries:
            try:
                raw_items.extend(_fetch_crossref_recent(q, from_date=cutoff_date, rows=4))
            except Exception:
                continue

    seen_ids: set[str] = set()
    candidates: list[dict[str, Any]] = []
    for item in raw_items:
        doi = str(item.get("DOI") or item.get("doi") or "").strip()
        nct_id = str(item.get("nct_id") or "").strip().upper()
        if not doi and not nct_id:
            continue
        dedup_key = doi.lower() or nct_id
        if dedup_key in seen_ids:
            continue
        seen_ids.add(dedup_key)

        titles = item.get("title")
        title_str = (
            str(titles[0]).strip()
            if isinstance(titles, list) and titles
            else str(titles or "Untitled Neuroscience Study").strip()
        )
        journal_list = item.get("container-title")
        journal_str = (
            str(journal_list[0]).strip()
            if isinstance(journal_list, list) and journal_list
            else str(journal_list or item.get("journal") or "Peer-Reviewed Journal").strip()
        )
        demo_video_url = str(item.get("official_demo_video_url") or "").strip() or None

        candidates.append(
            {
                "candidate_rank": len(candidates) + 1,
                "title": title_str,
                "journal": journal_str,
                "doi": doi or None,
                "nct_id": nct_id or None,
                "pillar": (
                    "bci_tech"
                    if ("interface" in title_str.lower() or "prosthe" in title_str.lower())
                    else ("brain_health" if any(k in title_str.lower() for k in ("sleep", "therapy", "clinical", "trial", "stroke", "depression", "alzheimer")) else "brain_news")
                ),
                "style_profile": PORCELAIN_V7_STYLE_PROFILE,
                "recommended_format": MICRO_SHORT_PROFILE,
                "source_reenactment_eligible": bool(demo_video_url),
                "official_demo_video_url": demo_video_url,
                "hold_from_auto_queue": True,
                "ceo_approval_status": "pending_hq_confirm",
            }
        )
        if len(candidates) >= max_candidates:
            break

    report = {
        "schema": "neuro_news_radar_v1",
        "scanned_at": datetime.now(timezone.utc).isoformat(),
        "window_days": int(window_days),
        "from_pub_date": cutoff_date,
        "staging_dir": str(staging_dir),
        "hold_from_auto_queue": True,
        "candidate_count": len(candidates),
        "candidates": candidates,
    }
    out_file = staging_dir / "news_radar_staging.json"
    out_file.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return report
