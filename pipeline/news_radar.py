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
    EVERYDAY_LONGFORM_DOMAINS,
    LONGFORM_PRODUCTION_PROFILE,
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

EVERYDAY_PSYCH_NEURO_QUERIES: dict[str, tuple[str, ...]] = {
    "sleep": (
        "glymphatic cerebrospinal fluid slow-wave sleep human MRI",
        "insomnia conditioned arousal amygdala sleep deprivation fMRI",
    ),
    "habits": (
        "procrastination emotion regulation amygdala anterior cingulate",
        "habit formation dorsal striatum basal ganglia behavioral",
    ),
    "memory": (
        "hippocampus memory consolidation retrieval spacing prefrontal",
        "cognitive offloading attention working memory parietal cortex",
    ),
    "anxiety": (
        "intolerance of uncertainty insula amygdala prefrontal anxiety",
        "interoception panic autonomic vagal emotion regulation fMRI",
    ),
    "relationships": (
        "social rejection anterior cingulate insula attachment fMRI",
        "co-regulation attachment caregiver amygdala prefrontal human",
    ),
}

_DOMAIN_KEYWORDS: dict[str, tuple[str, ...]] = {
    "sleep": ("sleep", "insomnia", "glymphatic", "circadian", "rem ", "slow-wave", "cerebrospinal", "melatonin", "sedative"),
    "habits": ("habit", "procrastinat", "striatum", "basal ganglia", "routine", "self-control", "dopamine", "impuls"),
    "memory": ("memory", "hippocamp", "recall", "forgetting", "attention", "focus", "amnesia", "consolidation"),
    "anxiety": ("anxiety", "panic", "fear", "uncertainty", "amygdala", "cortisol", "worry", "stress", "threat"),
    "relationships": ("attachment", "rejection", "lonely", "loneliness", "empathy", "social pain", "bonding", "caregiver", "trust"),
}


def classify_everyday_domain(title: str, query_hint: str = "") -> str:
    """Maps a study title / query into one of the 5 everyday Long-Form domains or `'bci_clinical'`."""
    combined = f"{title or ''} {query_hint or ''}".lower()
    if any(k in combined for k in ("brain-computer", "intracortical", "stentrode", "neuroprosthe", "electrode array")):
        return "bci_clinical"
    best_dom = "bci_clinical"
    best_hits = 0
    for dom in EVERYDAY_LONGFORM_DOMAINS:
        hits = sum(1 for kw in _DOMAIN_KEYWORDS.get(dom, ()) if kw in combined)
        if hits > best_hits:
            best_hits = hits
            best_dom = dom
    return best_dom


def _map_canonical_pillar(title_str: str, everyday_domain: str) -> str:
    low = (title_str or "").lower()
    if "interface" in low or "prosthe" in low or "stentrode" in low or "intracortical" in low:
        return "bci_tech"
    if everyday_domain in ("sleep", "anxiety"):
        return "brain_health"
    if everyday_domain in ("habits", "memory"):
        return "brain_basics"
    if everyday_domain == "relationships":
        return "brain_mysteries"
    if any(k in low for k in ("sleep", "therapy", "clinical", "trial", "stroke", "depression", "alzheimer")):
        return "brain_health"
    return "brain_news"


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
    queries: tuple[str, ...] | None = None,
    max_candidates: int = 8,
    offline_items: list[dict[str, Any]] | None = None,
    include_everyday_domains: bool = True,
) -> dict[str, Any]:
    """
    Collects verified DOI / NCT neuroscience & behavioral-psychology candidates across both BCI trials
    and the 5 everyday Long-Form domains (`sleep`, `habits`, `memory`, `anxiety`, `relationships`),
    writing staged HQ review cards into `Completed_Neuro_News_Shorts/news_radar_staging.json` (`hold_from_auto_queue: True`).
    """
    staging_dir = Path(NEURO_NEWS_STAGING_DIR)
    staging_dir.mkdir(parents=True, exist_ok=True)
    cutoff_date = (date.today() - timedelta(days=max(1, int(window_days)))).isoformat()

    query_pairs: list[tuple[str, str]] = []
    if queries is not None:
        query_pairs = [(q, "") for q in queries]
    else:
        query_pairs.extend((q, "bci_clinical") for q in DEFAULT_BCI_NEWS_QUERIES)
        if include_everyday_domains:
            for dom, dom_qs in EVERYDAY_PSYCH_NEURO_QUERIES.items():
                for q in dom_qs:
                    query_pairs.append((q, dom))

    raw_items: list[tuple[dict[str, Any], str]] = []
    if offline_items is not None:
        raw_items = [(dict(it), str(it.get("everyday_domain") or "")) for it in offline_items]
    else:
        for q, dom_hint in query_pairs:
            try:
                for it in _fetch_crossref_recent(q, from_date=cutoff_date, rows=3):
                    raw_items.append((it, dom_hint))
            except Exception:
                continue

    seen_ids: set[str] = set()
    candidates: list[dict[str, Any]] = []
    for item, dom_hint in raw_items:
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
        everyday_domain = (
            dom_hint
            if dom_hint in EVERYDAY_LONGFORM_DOMAINS
            else classify_everyday_domain(title_str, query_hint=dom_hint)
        )
        is_longform_cand = everyday_domain in EVERYDAY_LONGFORM_DOMAINS
        pillar = _map_canonical_pillar(title_str, everyday_domain)

        candidates.append(
            {
                "candidate_rank": len(candidates) + 1,
                "title": title_str,
                "journal": journal_str,
                "doi": doi or None,
                "nct_id": nct_id or None,
                "pillar": pillar,
                "everyday_domain": everyday_domain,
                "longform_candidate": is_longform_cand,
                "three_layer_formula": (
                    {
                        "everyday_problem": everyday_domain,
                        "psychology_layer": "behavioral_experiment_paradox",
                        "neuroscience_layer": "circuit_imaging_mechanism",
                    }
                    if is_longform_cand
                    else None
                ),
                "style_profile": PORCELAIN_V7_STYLE_PROFILE,
                "recommended_format": LONGFORM_PRODUCTION_PROFILE if is_longform_cand else MICRO_SHORT_PROFILE,
                "source_reenactment_eligible": bool(demo_video_url),
                "official_demo_video_url": demo_video_url,
                "hold_from_auto_queue": True,
                "ceo_approval_status": "pending_hq_confirm",
            }
        )
        if len(candidates) >= max_candidates:
            break

    report = {
        "schema": "neuro_news_radar_v2",
        "scanned_at": datetime.now(timezone.utc).isoformat(),
        "window_days": int(window_days),
        "from_pub_date": cutoff_date,
        "staging_dir": str(staging_dir),
        "everyday_domains_enabled": bool(include_everyday_domains),
        "hold_from_auto_queue": True,
        "candidate_count": len(candidates),
        "candidates": candidates,
    }
    out_file = staging_dir / "news_radar_staging.json"
    out_file.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return report
