"""
ALL ABOUT BRAIN - Short-to-Short Related Video & 7-Pillar Playlist Automation (R35-B)

Provides:
1. ShortLinkGraph:
   - 4-axis topic/retention affinity scoring (canonical anatomy, pillar/visual_mode,
     lexical plain-language overlap, and retention/seed-rescue boost) with dynamic
     weight redistribution for BEHAVIORAL_PSYCH topics.
   - Directional visibility safety guard (Public -> Public ONLY; Scheduled(T_src) -> Public
     or Scheduled(T_dst <= T_src); Unlisted -> Public/Scheduled/Unlisted; zero self-links).
   - 24h newly-published seed-pool indexing lock (SEED_PROTECTION_LOCK_HOURS).
   - 2-cycle prevention (A <-> B forbidden for N >= 3) and alternating Anchor -> Starved
     seed-rescue ring construction plus automatic longform bridge priority.
2. StudioShortLinker:
   - Visible Naver Whale DirectCDPClient automation on https://studio.youtube.com/video/<id>/edit.
   - Exact YouTube videoId matching on ytcp-entity-card (with search + title fallback).
   - Automatic 7-Pillar playlist creation (Public) & assignment.
   - DOM read-back verification, #save completion wait, R36-B Studio tab recycling every 3 edits,
     and lossless receipt persistence (related_video_receipt.json + studio_publish_receipt.json).
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Any, Callable
from zoneinfo import ZoneInfo

from pipeline.anatomy_map import find_regions, resolve_region
from pipeline.config import CHANNEL_ROOT
from pipeline.studio.config import (
    AFFINITY_WEIGHTS,
    ANCHOR_MIN_VIEWS,
    CHANNEL_ID,
    DAILY_REPORTS_DIR,
    DEFAULT_CDP_HOST,
    DEFAULT_CDP_PORT,
    PILLAR_PLAYLIST_MAP,
    PLAYLIST_SELECTORS,
    RELATED_VIDEO_SELECTORS,
    SEED_PROTECTION_LOCK_HOURS,
    SEED_STARVED_MAX_IMPRESSIONS,
    SHORT_LINK_GRAPH_FILE,
    STUDIO_CONTENT_URL,
    STUDIO_TAB_RECYCLE_INTERVAL,
    YOUTUBE_WATCH_BASE_URL,
)
from pipeline.studio.whale_session import DirectCDPClient, WhaleSessionController

_YOUTUBE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")

_STOPWORDS = frozenset({
    "about", "across", "actually", "after", "again", "against", "almost", "along",
    "also", "always", "among", "another", "around", "because", "before", "behind",
    "being", "below", "between", "brain", "brains", "built", "called", "cannot",
    "cases", "catch", "cause", "causes", "change", "changes", "channel", "circuit",
    "circuits", "clinical", "comment", "comments", "could", "daily", "didnt",
    "disclosure", "discovered", "doesnt", "during", "education", "every", "exact",
    "exploring", "experiment", "experiments", "first", "found", "frontiers", "happen",
    "happened", "happens", "human", "humans", "inside", "instead", "later", "makes",
    "making", "means", "might", "neural", "neuroscience", "never", "other", "pathway",
    "pathways", "patient", "patients", "people", "place", "point", "psychology",
    "really", "region", "regions", "research", "researchers", "revealed", "reveals",
    "right", "scientists", "scientist", "share", "shorts", "shown", "shows",
    "signal", "signals", "since", "small", "sound", "source", "still", "study",
    "studies", "synthesized", "system", "systems", "their", "there", "these", "thing",
    "things", "think", "those", "three", "through", "today", "under", "until",
    "using", "verification", "video", "visuals", "voice", "watch", "where", "which",
    "while", "whole", "within", "without", "world", "would", "years", "your",
})

_ANATOMY_FAMILIES: dict[str, frozenset[str]] = {
    "frontal_control": frozenset({
        "prefrontal cortex",
        "ventromedial prefrontal cortex",
        "dorsolateral prefrontal cortex",
        "frontal lobe",
        "anterior cingulate cortex",
    }),
    "limbic_memory_emotion": frozenset({
        "amygdala",
        "hippocampus",
        "insula",
        "hypothalamus",
    }),
    "striatal_habit_reward": frozenset({
        "basal ganglia",
        "nucleus accumbens",
        "substantia nigra",
        "ventral tegmental area",
    }),
    "sensorimotor_speech": frozenset({
        "motor cortex",
        "premotor cortex",
        "somatosensory cortex",
        "broca's area",
        "wernicke's area",
        "cerebellum",
    }),
    "perceptual_callosal": frozenset({
        "primary visual cortex",
        "fusiform face area",
        "corpus callosum",
        "white matter",
        "thalamus",
    }),
}

_COMPLEMENTARY_PILLARS: frozenset[frozenset[str]] = frozenset({
    frozenset({"brain_health", "brain_basics"}),
    frozenset({"brain_mysteries", "brain_history"}),
    frozenset({"bci_tech", "brain_news"}),
    frozenset({"bci_tech", "bci_ethics"}),
    frozenset({"brain_basics", "brain_mysteries"}),
})

_DELETED_OR_INACTIVE_STATUSES = frozenset({
    "deleted_from_studio",
    "deleted",
    "quarantined",
    "failed",
    "dry_run",
    "error",
})


def is_valid_youtube_video_id(video_id: str | None) -> bool:
    """True when video_id is a real 11-character YouTube ID (not a dry-run placeholder)."""
    if not video_id:
        return False
    vid = str(video_id).strip()
    if vid.upper().startswith("DRY_RUN"):
        return False
    return bool(_YOUTUBE_ID_RE.match(vid))


def _load_json_safe(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _parse_datetime_utc(raw: str | None) -> datetime | None:
    """Parses ISO-8601 UTC/offset timestamps or 'YYYY-MM-DD HH:MM ET' strings into UTC."""
    if not raw:
        return None
    s = str(raw).strip()
    if not s:
        return None
    try:
        if s.endswith("Z"):
            return datetime.fromisoformat(s[:-1] + "+00:00").astimezone(timezone.utc)
        if "T" in s:
            dt = datetime.fromisoformat(s)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
    except Exception:
        pass

    et_match = re.match(r"^(\d{4}-\d{2}-\d{2})\s+(\d{1,2}:\d{2})(?:\s*ET)?$", s, flags=re.IGNORECASE)
    if et_match:
        try:
            dt_naive = datetime.strptime(f"{et_match.group(1)} {et_match.group(2)}", "%Y-%m-%d %H:%M")
            dt_et = dt_naive.replace(tzinfo=ZoneInfo("America/New_York"))
            return dt_et.astimezone(timezone.utc)
        except Exception:
            pass

    date_only = re.match(r"^(\d{4}-\d{2}-\d{2})$", s)
    if date_only:
        try:
            dt_naive = datetime.strptime(date_only.group(1), "%Y-%m-%d")
            return dt_naive.replace(hour=16, minute=0, tzinfo=timezone.utc)
        except Exception:
            pass
    return None


_BOILERPLATE_LINE_PREFIXES = (
    "source & verification",
    "ai disclosure",
    "all about brain",
)


def _strip_boilerplate_for_lexical(text: str) -> str:
    """Removes identical channel description footers, URLs/DOIs, hashtags, and R24 signature memes."""
    if not text:
        return ""
    kept_lines: list[str] = []
    for raw_line in text.splitlines():
        ln = raw_line.strip()
        if not ln:
            continue
        low = ln.lower()
        if low.startswith(_BOILERPLATE_LINE_PREFIXES) or low.startswith("#"):
            continue
        if (
            "visuals and voice synthesized with ai" in low
            or "exploring the frontiers of neuroscience" in low
            or "verified peer-reviewed neuroscience journal" in low
            or "measured in controlled human clinical trials" in low
        ):
            continue
        kept_lines.append(ln)
    cleaned = " ".join(kept_lines)
    cleaned = re.sub(r"https?://\S+|doi\.org/\S+|10\.\d{4,9}/\S+", " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"#[A-Za-z0-9_]+", " ", cleaned)
    cleaned = re.sub(
        r"\b(?:did you catch that|your brain was built by survival,?\s*not truth|your brain never asked your permission)\b",
        " ",
        cleaned,
        flags=re.IGNORECASE,
    )
    return cleaned


def _tokenize_lexical(text: str) -> set[str]:
    stripped = _strip_boilerplate_for_lexical(text)
    words = re.findall(r"[a-z]{4,}", stripped.lower())
    return {w for w in words if w not in _STOPWORDS}


def normalize_visibility(upload_receipt: dict[str, Any]) -> str:
    """Normalizes visibility + status from upload_receipt.json into canonical Studio visibility."""
    status = str(upload_receipt.get("status") or "").strip().lower()
    if status in _DELETED_OR_INACTIVE_STATUSES:
        return "deleted"
    vis = str(upload_receipt.get("visibility") or "").strip().lower()
    if status == "published_public" or vis == "public":
        return "public"
    if status in {"scheduled", "queued_scheduled"} or vis in {"schedule", "scheduled"}:
        return "scheduled"
    if status in {"uploaded_unlisted", "staged_unlisted"} or vis == "unlisted":
        return "unlisted"
    if vis == "private":
        return "private"
    return vis or "unknown"


def write_studio_publish_receipt(
    project_id: str,
    projects_dir: Path | None = None,
) -> Path:
    """
    Consolidates upload, related_video, playlist, community_pin, and ab_test receipts
    into 06_publish/studio_publish_receipt.json (Stage 5 SSOT artifact).
    """
    root = projects_dir or (CHANNEL_ROOT / "projects")
    pub_dir = root / project_id / "06_publish"
    pub_dir.mkdir(parents=True, exist_ok=True)

    upload_rec = _load_json_safe(pub_dir / "upload_receipt.json")
    related_rec = _load_json_safe(pub_dir / "related_video_receipt.json")
    community_rec = _load_json_safe(pub_dir / "community_receipt.json")
    ab_rec = _load_json_safe(pub_dir / "ab_test_manifest.json")
    meta = _load_json_safe(pub_dir / "metadata.json")

    video_id = str(upload_rec.get("video_id") or related_rec.get("source_video_id") or "").strip()
    visibility = normalize_visibility(upload_rec) if upload_rec else str(related_rec.get("source_visibility") or "unknown")
    shorts_url = str(upload_rec.get("shorts_url") or (f"{YOUTUBE_WATCH_BASE_URL}{video_id}" if is_valid_youtube_video_id(video_id) else ""))

    playlist_title = str(
        related_rec.get("playlist_title")
        or upload_rec.get("playlist_title")
        or ""
    ).strip()
    playlist_verified = bool(
        related_rec.get("playlist_verified")
        or upload_rec.get("playlist_assigned")
    )
    related_verified = bool(related_rec.get("verified")) and is_valid_youtube_video_id(
        related_rec.get("target_video_id")
    )

    consolidated = {
        "schema_version": 1,
        "project_id": project_id,
        "video_id": video_id,
        "shorts_url": shorts_url,
        "title": str(upload_rec.get("title") or meta.get("title") or "").strip(),
        "pillar": str(meta.get("pillar") or upload_rec.get("pillar") or related_rec.get("source_pillar") or "").strip(),
        "visibility": visibility,
        "status": str(upload_rec.get("status") or "").strip(),
        "stage_5_complete": bool(is_valid_youtube_video_id(video_id) and related_verified),
        "upload": upload_rec,
        "related_video": {
            "linked": related_verified,
            "target_project_id": related_rec.get("target_project_id"),
            "target_video_id": related_rec.get("target_video_id"),
            "target_title": related_rec.get("target_title"),
            "target_type": related_rec.get("target_type", "short"),
            "link_reason": related_rec.get("link_reason"),
            "affinity_score": related_rec.get("affinity_score"),
            "dom_readback_text": related_rec.get("dom_readback_text"),
            "verified_at_utc": related_rec.get("verified_at_utc"),
        },
        "playlist": {
            "assigned": playlist_verified,
            "playlist_title": playlist_title,
        },
        "community_pin": {
            "pinned": bool(community_rec.get("pinned"))
            or str(community_rec.get("status") or "").lower() in {"pinned", "posted_unpinned"},
            "status": community_rec.get("status") or ("pinned" if community_rec.get("pinned") else None),
            "doi_included": community_rec.get("doi_included"),
        },
        "ab_test": {
            "initialized": bool(ab_rec),
            "active_variant": ab_rec.get("active_variant") or ab_rec.get("current_active_variant"),
            "status": ab_rec.get("status"),
        },
        "updated_at_utc": datetime.now(timezone.utc).isoformat(),
    }

    out_path = pub_dir / "studio_publish_receipt.json"
    out_path.write_text(json.dumps(consolidated, indent=2, ensure_ascii=False), encoding="utf-8")
    return out_path


class ShortLinkGraph:
    """
    Computes directional, cycle-safe, seed-aware Related Video links across ALL ABOUT BRAIN Shorts.
    """

    def __init__(
        self,
        projects_dir: Path | None = None,
        dossiers_dir: Path | None = None,
        reports_dir: Path | None = None,
        graph_file: Path | None = None,
        nodes: list[dict[str, Any]] | None = None,
        now_utc: datetime | None = None,
    ):
        self.projects_dir = projects_dir or (CHANNEL_ROOT / "projects")
        self.dossiers_dir = dossiers_dir or (CHANNEL_ROOT / "research_dossiers")
        self.reports_dir = reports_dir or DAILY_REPORTS_DIR
        self.graph_file = graph_file or SHORT_LINK_GRAPH_FILE
        self.now_utc = now_utc or datetime.now(timezone.utc)
        self._explicit_nodes = nodes

    def _load_latest_metrics_by_video(self) -> dict[str, dict[str, Any]]:
        if not self.reports_dir or not self.reports_dir.exists():
            return {}
        metric_files = sorted(self.reports_dir.glob("*_studio_metrics.json"))
        if not metric_files:
            return {}
        latest = _load_json_safe(metric_files[-1])
        by_key: dict[str, dict[str, Any]] = {}
        for rec in latest.get("per_video_records", []):
            if not isinstance(rec, dict):
                continue
            vid = str(rec.get("video_id") or "").strip()
            pid = str(rec.get("project_id") or "").strip()
            if vid:
                by_key[vid] = rec
            if pid:
                by_key[pid] = rec
        return by_key

    def _build_dossier_index(self) -> dict[str, Path]:
        """Maps project_id (and dossier slug) -> dossier directory."""
        idx: dict[str, Path] = {}
        if not self.dossiers_dir or not self.dossiers_dir.exists():
            return idx
        for d_dir in sorted(self.dossiers_dir.iterdir()):
            if not d_dir.is_dir():
                continue
            idx[d_dir.name] = d_dir
            d_json = _load_json_safe(d_dir / "dossier.json")
            for lp in d_json.get("linked_projects", []) or []:
                if isinstance(lp, str) and lp.strip():
                    idx[lp.strip()] = d_dir
        return idx

    def _match_dossier_dir(
        self,
        project_id: str,
        dossier_idx: dict[str, Path],
        dossier_slug: str = "",
    ) -> Path | None:
        if dossier_slug and dossier_slug in dossier_idx:
            return dossier_idx[dossier_slug]
        if project_id in dossier_idx:
            return dossier_idx[project_id]
        stripped = re.sub(r"^psych_\d+_", "", project_id)
        if stripped in dossier_idx:
            return dossier_idx[stripped]
        proj_tokens = set(stripped.split("_"))
        best_dir: Path | None = None
        best_overlap = 0
        for slug, d_dir in dossier_idx.items():
            if slug.startswith("psych_"):
                continue
            slug_tokens = set(slug.split("_"))
            overlap = len(proj_tokens & slug_tokens)
            if overlap >= 2 and overlap > best_overlap:
                best_overlap = overlap
                best_dir = d_dir
        return best_dir

    def discover_nodes(self) -> list[dict[str, Any]]:
        """Discovers all Shorts with live/staged/scheduled YouTube Studio receipts."""
        if self._explicit_nodes is not None:
            return [self._normalize_explicit_node(n) for n in self._explicit_nodes]

        if not self.projects_dir.exists():
            return []

        metrics_idx = self._load_latest_metrics_by_video()
        dossier_idx = self._build_dossier_index()
        nodes: list[dict[str, Any]] = []

        for p_dir in sorted(self.projects_dir.iterdir()):
            if not p_dir.is_dir():
                continue
            pid = p_dir.name
            pub_dir = p_dir / "06_publish"
            upload_rec = _load_json_safe(pub_dir / "upload_receipt.json")
            if not upload_rec:
                continue

            vid = str(upload_rec.get("video_id") or "").strip()
            vis = normalize_visibility(upload_rec)
            if not is_valid_youtube_video_id(vid) or vis in {"deleted", "private", "unknown"}:
                continue

            manifest = _load_json_safe(p_dir / "00_project_manifest.json")
            meta = _load_json_safe(pub_dir / "metadata.json")
            script = _load_json_safe(p_dir / "02_script" / "script.json")
            vplan = _load_json_safe(p_dir / "03_visuals" / "visual_plan.json")
            idea = _load_json_safe(p_dir / "01_ideation" / "idea_card.json")
            rel_rec = _load_json_safe(pub_dir / "related_video_receipt.json")

            dossier_slug = str(manifest.get("dossier_slug") or meta.get("dossier_slug") or "").strip()
            dossier_dir = self._match_dossier_dir(pid, dossier_idx, dossier_slug=dossier_slug)
            dossier_json = _load_json_safe(dossier_dir / "dossier.json") if dossier_dir else {}
            plain_json = _load_json_safe(dossier_dir / "05_plain_language.json") if dossier_dir else {}
            brain_json = _load_json_safe(dossier_dir / "06_brain_link.json") if dossier_dir else {}
            longform_json = _load_json_safe(dossier_dir / "07_longform_outline.json") if dossier_dir else {}

            pillar = str(
                meta.get("pillar")
                or manifest.get("pillar")
                or dossier_json.get("pillar")
                or script.get("pillar")
                or idea.get("pillar")
                or "brain_basics"
            ).strip()

            visual_mode = str(
                vplan.get("visual_mode")
                or brain_json.get("visual_mode")
                or dossier_json.get("visual_mode")
                or "NEURO_BIOLOGY"
            ).strip().upper()

            title = str(upload_rec.get("title") or meta.get("title") or pid).strip()

            # Collect canonical brain regions
            text_blobs: list[str] = [
                title,
                str(meta.get("description") or ""),
                json.dumps(script.get("clip_narrations") or script.get("narrations") or "", ensure_ascii=False),
                json.dumps(vplan, ensure_ascii=False),
            ]
            region_set: list[str] = []
            for link_item in brain_json.get("links", []) or []:
                if isinstance(link_item, dict) and link_item.get("region"):
                    canon = resolve_region(str(link_item["region"]))
                    if canon and canon not in region_set:
                        region_set.append(canon)
            for found in find_regions(" ".join(text_blobs)):
                if found not in region_set:
                    region_set.append(found)

            # Collect lexical tokens (topic-specific plain language, script narrations, hooks & misconceptions)
            raw_narrs = script.get("clip_narrations") or script.get("narrations") or []
            if isinstance(raw_narrs, list):
                narr_text = " ".join(
                    str(n.get("text") or n.get("narration") or "") if isinstance(n, dict) else str(n)
                    for n in raw_narrs
                )
            elif isinstance(raw_narrs, dict):
                narr_text = " ".join(str(v) for v in raw_narrs.values())
            else:
                narr_text = str(raw_narrs)

            lex_blobs: list[str] = [
                title,
                str(meta.get("description") or ""),
                narr_text,
                str(dossier_json.get("topic") or ""),
                " ".join(str(x) for x in (dossier_json.get("everyday_hooks") or [])),
                str(plain_json.get("one_sentence_story") or ""),
                str(plain_json.get("so_what_for_you") or ""),
            ]
            for mc in dossier_json.get("misconceptions", []) or []:
                if isinstance(mc, dict):
                    lex_blobs.append(f"{mc.get('myth', '')} {mc.get('truth', '')}")
                elif mc:
                    lex_blobs.append(str(mc))
            for jm in plain_json.get("jargon_map", []) or []:
                if isinstance(jm, dict):
                    lex_blobs.append(f"{jm.get('term', '')} {jm.get('plain', '')}")
            lexical_tokens = sorted(_tokenize_lexical("\n".join(lex_blobs)))

            # Longform bridge target if published
            lf_vid = str(
                longform_json.get("published_longform_video_id")
                or dossier_json.get("published_longform_video_id")
                or ""
            ).strip()
            lf_title = str(
                longform_json.get("published_longform_title")
                or dossier_json.get("published_longform_title")
                or ""
            ).strip()

            metric = metrics_idx.get(vid) or metrics_idx.get(pid) or {}
            pub_raw = (
                upload_rec.get("published_at_utc")
                or upload_rec.get("scheduled_at_utc")
                or upload_rec.get("scheduled_time_et")
                or (f"{metric.get('date')} {metric.get('time_et', '12:00')} ET" if metric.get("date") else None)
            )
            pub_dt = _parse_datetime_utc(str(pub_raw)) if pub_raw else None

            nodes.append({
                "project_id": pid,
                "video_id": vid,
                "title": title,
                "pillar": pillar,
                "visual_mode": visual_mode,
                "visibility": vis,
                "status": str(upload_rec.get("status") or ""),
                "published_at_utc": pub_dt.isoformat() if pub_dt else None,
                "regions": region_set,
                "lexical_tokens": lexical_tokens,
                "views": int(metric.get("views", 0) or 0),
                "impressions": int(metric.get("impressions", 0) or 0),
                "apv_pct": float(metric.get("apv_pct", 0.0) or 0.0),
                "viewed_pct": float(metric.get("viewed_pct", 0.0) or 0.0),
                "published_longform_video_id": lf_vid if is_valid_youtube_video_id(lf_vid) else "",
                "published_longform_title": lf_title,
                "existing_target_video_id": str(rel_rec.get("target_video_id") or "").strip() if rel_rec.get("verified") else "",
                "existing_playlist_verified": bool(rel_rec.get("playlist_verified")),
                "dossier_slug": dossier_dir.name if dossier_dir else "",
            })

        return nodes

    def _normalize_explicit_node(self, raw: dict[str, Any]) -> dict[str, Any]:
        node = dict(raw)
        node.setdefault("project_id", str(raw.get("video_id") or "unknown"))
        node["video_id"] = str(raw.get("video_id") or "").strip()
        node.setdefault("title", node["project_id"])
        node.setdefault("pillar", "brain_basics")
        node["visual_mode"] = str(raw.get("visual_mode") or "NEURO_BIOLOGY").upper()
        node["visibility"] = str(raw.get("visibility") or normalize_visibility(raw)).lower()
        raw_ts = (
            raw.get("published_at_utc")
            or raw.get("published_at")
            or raw.get("scheduled_at_utc")
            or raw.get("scheduled_time_et")
        )
        if isinstance(raw_ts, datetime):
            pub_dt = raw_ts.astimezone(timezone.utc) if raw_ts.tzinfo else raw_ts.replace(tzinfo=timezone.utc)
        else:
            pub_dt = _parse_datetime_utc(raw_ts)
        node["published_at_utc"] = pub_dt.isoformat() if pub_dt else None

        raw_regions = raw.get("regions")
        if raw_regions is None:
            raw_regions = find_regions(f"{node.get('title', '')} {raw.get('text', '')}")
        else:
            resolved = []
            for r in raw_regions:
                canon = resolve_region(str(r)) or str(r).lower().strip()
                if canon and canon not in resolved:
                    resolved.append(canon)
            raw_regions = resolved
        node["regions"] = list(raw_regions)

        raw_lex = raw.get("lexical_tokens")
        if raw_lex is None:
            raw_lex = sorted(_tokenize_lexical(f"{node.get('title', '')} {raw.get('text', '')}"))
        node["lexical_tokens"] = list(raw_lex)

        node["views"] = int(raw.get("views", 0) or 0)
        node["impressions"] = int(raw.get("impressions", 0) or 0)
        node["apv_pct"] = float(raw.get("apv_pct", 0.0) or 0.0)
        node["viewed_pct"] = float(raw.get("viewed_pct", 0.0) or 0.0)
        lf_vid = str(raw.get("published_longform_video_id") or raw.get("longform_video_id") or "").strip()
        node["published_longform_video_id"] = lf_vid if is_valid_youtube_video_id(lf_vid) else ""
        node["published_longform_title"] = str(raw.get("published_longform_title") or "").strip()
        node["existing_target_video_id"] = str(raw.get("existing_target_video_id") or "").strip()
        node["existing_playlist_verified"] = bool(raw.get("existing_playlist_verified", False))
        return node

    @staticmethod
    def is_valid_link_direction(src: dict[str, Any], dst: dict[str, Any]) -> bool:
        """
        Enforces directional visibility safety so viewers never hit an Unlisted/Private/Future video:
        - No self-links.
        - Public -> Public ONLY.
        - Scheduled(T_src) -> Public OR Scheduled(T_dst <= T_src) (fail-closed if timestamps missing).
        - Unlisted -> Public, Scheduled, or Unlisted.
        """
        if src.get("project_id") == dst.get("project_id"):
            return False
        src_vid = str(src.get("video_id") or "").strip()
        dst_vid = str(dst.get("video_id") or "").strip()
        if not is_valid_youtube_video_id(src_vid) or not is_valid_youtube_video_id(dst_vid):
            return False
        if src_vid == dst_vid:
            return False

        src_vis = str(src.get("visibility") or "").lower()
        dst_vis = str(dst.get("visibility") or "").lower()
        if dst_vis in {"private", "deleted", "unknown", ""}:
            return False

        if src_vis == "public":
            return dst_vis == "public"

        if src_vis == "scheduled":
            if dst_vis == "public":
                return True
            if dst_vis == "scheduled":
                raw_s = src.get("published_at_utc") or src.get("scheduled_at_utc") or src.get("scheduled_time_et")
                raw_d = dst.get("published_at_utc") or dst.get("scheduled_at_utc") or dst.get("scheduled_time_et")
                src_dt = raw_s if isinstance(raw_s, datetime) else _parse_datetime_utc(raw_s)
                dst_dt = raw_d if isinstance(raw_d, datetime) else _parse_datetime_utc(raw_d)
                if src_dt and dst_dt:
                    return dst_dt <= src_dt
                return False
            return False

        if src_vis == "unlisted":
            return dst_vis in {"public", "scheduled", "unlisted"}

        return False

    def is_seed_locked(
        self,
        node: dict[str, Any],
        force: bool = False,
    ) -> tuple[bool, str]:
        """
        Protects newly published Public Shorts during their initial 24h seed-pool indexing window.
        """
        if force:
            return False, ""
        if str(node.get("visibility") or "").lower() != "public":
            return False, ""
        raw_p = node.get("published_at_utc") or node.get("published_at")
        pub_dt = raw_p if isinstance(raw_p, datetime) else _parse_datetime_utc(raw_p)
        if not pub_dt:
            return False, ""
        elapsed_hours = (self.now_utc - pub_dt).total_seconds() / 3600.0
        if 0.0 <= elapsed_hours < SEED_PROTECTION_LOCK_HOURS:
            return True, f"deferred_seed_lock ({elapsed_hours:.1f}h < {SEED_PROTECTION_LOCK_HOURS:.1f}h)"
        return False, ""

    @staticmethod
    def is_anchor(node: dict[str, Any]) -> bool:
        return (
            str(node.get("visibility") or "").lower() == "public"
            and int(node.get("views", 0) or 0) >= ANCHOR_MIN_VIEWS
        )

    @staticmethod
    def is_seed_starved(node: dict[str, Any]) -> bool:
        return (
            str(node.get("visibility") or "").lower() == "public"
            and int(node.get("views", 0) or 0) < ANCHOR_MIN_VIEWS
            and 0 < int(node.get("impressions", 0) or 0) <= SEED_STARVED_MAX_IMPRESSIONS
        )

    def compute_affinity(
        self,
        src: dict[str, Any],
        dst: dict[str, Any],
        mode: str = "semantic_chain",
    ) -> dict[str, Any]:
        """
        Computes 4-axis affinity score in [0.0, 1.0].
        Automatically redistributes anatomy weight to pillar_mode + lexical when either node is BEHAVIORAL_PSYCH.
        """
        w_anat = float(AFFINITY_WEIGHTS["anatomy"])
        w_pillar = float(AFFINITY_WEIGHTS["pillar_mode"])
        w_lex = float(AFFINITY_WEIGHTS["lexical"])
        w_ret = float(AFFINITY_WEIGHTS["retention_seed"])

        src_mode = str(src.get("visual_mode") or "NEURO_BIOLOGY").upper()
        dst_mode = str(dst.get("visual_mode") or "NEURO_BIOLOGY").upper()
        behavioral_pair = (src_mode == "BEHAVIORAL_PSYCH" or dst_mode == "BEHAVIORAL_PSYCH")
        if behavioral_pair:
            half = w_anat / 2.0
            w_pillar += half
            w_lex += (w_anat - half)
            w_anat = 0.0

        # 1. Anatomy overlap
        r_src = set(src.get("regions") or [])
        r_dst = set(dst.get("regions") or [])
        if r_src and r_dst:
            jacc = len(r_src & r_dst) / len(r_src | r_dst)
            fam_src = {f for f, members in _ANATOMY_FAMILIES.items() if r_src & members}
            fam_dst = {f for f, members in _ANATOMY_FAMILIES.items() if r_dst & members}
            fam_bonus = 0.25 if (fam_src & fam_dst) else 0.0
            anatomy_score = min(1.0, jacc + fam_bonus)
        else:
            anatomy_score = 0.0

        # 2. Pillar + Visual Mode compatibility
        p_src = str(src.get("pillar") or "")
        p_dst = str(dst.get("pillar") or "")
        if p_src and p_src == p_dst:
            p_base = 0.70
        elif frozenset({p_src, p_dst}) in _COMPLEMENTARY_PILLARS:
            p_base = 0.35
        else:
            p_base = 0.15
        m_bonus = 0.30 if src_mode == dst_mode else 0.15
        pillar_mode_score = min(1.0, p_base + m_bonus)

        # 3. Lexical / plain-language token overlap (scaled Sorensen-Dice; non-saturating on large token sets)
        l_src = set(src.get("lexical_tokens") or [])
        l_dst = set(dst.get("lexical_tokens") or [])
        if l_src and l_dst:
            dice = (2.0 * len(l_src & l_dst)) / (len(l_src) + len(l_dst))
            lexical_score = min(1.0, 1.35 * dice)
        else:
            lexical_score = 0.0

        # 4. Retention / Seed-rescue axis
        dst_quality = max(float(dst.get("apv_pct", 0.0) or 0.0), float(dst.get("viewed_pct", 0.0) or 0.0))
        q_norm = min(1.0, dst_quality / 90.0) if dst_quality > 0 else 0.55
        src_anchor = self.is_anchor(src)
        dst_anchor = self.is_anchor(dst)
        src_starved = self.is_seed_starved(src)
        dst_starved = self.is_seed_starved(dst)

        if mode == "seed_boost":
            if src_anchor and dst_starved:
                retention_seed_score = min(1.0, 0.70 + 0.30 * q_norm)
            elif src_starved and dst_anchor:
                retention_seed_score = min(1.0, 0.65 + 0.35 * q_norm)
            elif dst_starved and p_src == p_dst:
                retention_seed_score = min(1.0, 0.60 + 0.30 * q_norm)
            else:
                retention_seed_score = min(1.0, 0.50 * q_norm + (0.30 if dst_anchor else 0.10))
        else:
            retention_seed_score = min(1.0, 0.60 * q_norm + (0.40 if dst_anchor else 0.15))

        total = (
            w_anat * anatomy_score
            + w_pillar * pillar_mode_score
            + w_lex * lexical_score
            + w_ret * retention_seed_score
        )
        return {
            "total": round(total, 4),
            "anatomy": round(anatomy_score, 4),
            "pillar_mode": round(pillar_mode_score, 4),
            "lexical": round(lexical_score, 4),
            "retention_seed": round(retention_seed_score, 4),
            "behavioral_reweighted": behavioral_pair,
        }

    def plan_links(
        self,
        mode: str = "seed_boost",
        force: bool = False,
        project_filter: set[str] | None = None,
        explicit_target_video_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Plans cycle-safe directional Related Video assignments across all discovered nodes.
        - Priority 1: explicit_target_video_id (when --project and --target are passed).
        - Priority 2: dossier published_longform_video_id (longform bridge).
        - Priority 3 (seed_boost): alternating Anchor -> Seed-Starved -> Next-Anchor ring,
          plus affinity-driven attachment for remaining nodes with strict 2-cycle prevention (N >= 3).
        """
        nodes = self.discover_nodes()
        by_pid = {n["project_id"]: n for n in nodes}
        by_vid = {n["video_id"]: n for n in nodes}

        assigned_target_pid: dict[str, str] = {}
        edge_meta: dict[str, dict[str, Any]] = {}
        in_degree: dict[str, int] = {n["project_id"]: 0 for n in nodes}

        # Explicit override for targeted CLI run
        if explicit_target_video_id and project_filter:
            target_node = by_vid.get(explicit_target_video_id) or by_pid.get(explicit_target_video_id)
            for pid in sorted(project_filter):
                src = by_pid.get(pid)
                if not src:
                    continue
                if target_node:
                    if not self.is_valid_link_direction(src, target_node):
                        edge_meta[pid] = {
                            "status": "blocked_invalid_direction",
                            "reason": f"Illegal visibility direction: {src['visibility']} -> {target_node['visibility']}",
                        }
                        continue
                    aff = self.compute_affinity(src, target_node, mode=mode)
                    assigned_target_pid[pid] = target_node["project_id"]
                    edge_meta[pid] = {
                        "target_type": "short",
                        "target_project_id": target_node["project_id"],
                        "target_video_id": target_node["video_id"],
                        "target_title": target_node["title"],
                        "affinity": aff,
                        "link_reason": "explicit_target_override",
                    }
                elif is_valid_youtube_video_id(explicit_target_video_id):
                    edge_meta[pid] = {
                        "target_type": "external_channel_video",
                        "target_project_id": None,
                        "target_video_id": explicit_target_video_id,
                        "target_title": explicit_target_video_id,
                        "affinity": {"total": 1.0},
                        "link_reason": "explicit_video_id_override",
                    }

        # Priority 2: Published longform video bridge
        for src in nodes:
            pid = src["project_id"]
            if pid in edge_meta:
                continue
            lf_vid = src.get("published_longform_video_id") or ""
            if is_valid_youtube_video_id(lf_vid) and lf_vid != src["video_id"]:
                edge_meta[pid] = {
                    "target_type": "longform",
                    "target_project_id": None,
                    "target_video_id": lf_vid,
                    "target_title": src.get("published_longform_title") or lf_vid,
                    "affinity": {"total": 1.0},
                    "link_reason": "published_longform_bridge",
                }

        # Priority 3A: Alternating Anchor -> Seed-Starved Hamiltonian cycle in seed_boost mode
        public_short_nodes = [
            n for n in nodes
            if n["visibility"] == "public" and n["project_id"] not in edge_meta
        ]
        if mode == "seed_boost" and len(public_short_nodes) >= 3:
            anchors = sorted(
                [n for n in public_short_nodes if self.is_anchor(n)],
                key=lambda x: (-int(x.get("views", 0)), x["project_id"]),
            )
            starved = sorted(
                [n for n in public_short_nodes if self.is_seed_starved(n)],
                key=lambda x: (-float(x.get("apv_pct", 0.0)), -float(x.get("viewed_pct", 0.0)), x["project_id"]),
            )
            k = min(len(anchors), len(starved))
            if k >= 2:
                for idx in range(k):
                    a_node = anchors[idx]
                    s_node = starved[idx]
                    next_a = anchors[(idx + 1) % k]

                    aff_as = self.compute_affinity(a_node, s_node, mode=mode)
                    assigned_target_pid[a_node["project_id"]] = s_node["project_id"]
                    in_degree[s_node["project_id"]] += 1
                    edge_meta[a_node["project_id"]] = {
                        "target_type": "short",
                        "target_project_id": s_node["project_id"],
                        "target_video_id": s_node["video_id"],
                        "target_title": s_node["title"],
                        "affinity": aff_as,
                        "link_reason": "seed_rescue_anchor_to_starved",
                    }

                    reason_sa = "binge_loop_closure" if idx == k - 1 else "anchor_handoff"
                    aff_sa = self.compute_affinity(s_node, next_a, mode=mode)
                    assigned_target_pid[s_node["project_id"]] = next_a["project_id"]
                    in_degree[next_a["project_id"]] += 1
                    edge_meta[s_node["project_id"]] = {
                        "target_type": "short",
                        "target_project_id": next_a["project_id"],
                        "target_video_id": next_a["video_id"],
                        "target_title": next_a["title"],
                        "affinity": aff_sa,
                        "link_reason": reason_sa,
                    }
            elif k == 1:
                a_node = anchors[0]
                s_node = starved[0]
                others = [
                    n for n in public_short_nodes
                    if n["project_id"] not in {a_node["project_id"], s_node["project_id"]}
                ]
                if others:
                    others_sorted = sorted(
                        others,
                        key=lambda c: (-self.compute_affinity(s_node, c, mode=mode)["total"], c["project_id"]),
                    )
                    m_node = others_sorted[0]
                    for u_node, v_node, r_label in (
                        (a_node, s_node, "seed_rescue_anchor_to_starved"),
                        (s_node, m_node, "seed_bridge_to_peer"),
                        (m_node, a_node, "binge_loop_closure"),
                    ):
                        aff_uv = self.compute_affinity(u_node, v_node, mode=mode)
                        assigned_target_pid[u_node["project_id"]] = v_node["project_id"]
                        in_degree[v_node["project_id"]] += 1
                        edge_meta[u_node["project_id"]] = {
                            "target_type": "short",
                            "target_project_id": v_node["project_id"],
                            "target_video_id": v_node["video_id"],
                            "target_title": v_node["title"],
                            "affinity": aff_uv,
                            "link_reason": r_label,
                        }

        # Priority 3B: General affinity assignment with strict 2-cycle prevention (for N >= 3)
        for src in nodes:
            pid = src["project_id"]
            if pid in edge_meta:
                continue

            valid_candidates = [
                dst for dst in nodes
                if self.is_valid_link_direction(src, dst)
            ]
            if not valid_candidates:
                edge_meta[pid] = {
                    "status": "no_valid_target",
                    "reason": f"No valid target satisfies visibility guard for {src['visibility']}",
                }
                continue

            non_two_cycle = [
                dst for dst in valid_candidates
                if assigned_target_pid.get(dst["project_id"]) != pid
            ]
            pool = non_two_cycle if non_two_cycle else valid_candidates

            best_dst: dict[str, Any] | None = None
            best_aff: dict[str, Any] = {}
            best_rank_score = -1e9
            for dst in pool:
                aff = self.compute_affinity(src, dst, mode=mode)
                deg = in_degree.get(dst["project_id"], 0)
                if mode == "seed_boost" and self.is_seed_starved(dst) and deg < 2:
                    deg_penalty = 0.0
                else:
                    deg_penalty = 0.06 * deg
                rank_score = aff["total"] - deg_penalty
                if rank_score > best_rank_score:
                    best_rank_score = rank_score
                    best_dst = dst
                    best_aff = aff

            assert best_dst is not None
            assigned_target_pid[pid] = best_dst["project_id"]
            in_degree[best_dst["project_id"]] = in_degree.get(best_dst["project_id"], 0) + 1

            if mode == "seed_boost" and self.is_seed_starved(best_dst):
                reason = (
                    "same_pillar_seed_handoff"
                    if src.get("pillar") == best_dst.get("pillar")
                    else "seed_rescue_handoff"
                )
            elif src.get("pillar") == best_dst.get("pillar"):
                reason = "same_pillar_semantic_chain"
            else:
                reason = "cross_pillar_affinity_bridge"

            edge_meta[pid] = {
                "target_type": "short",
                "target_project_id": best_dst["project_id"],
                "target_video_id": best_dst["video_id"],
                "target_title": best_dst["title"],
                "affinity": best_aff,
                "link_reason": reason,
            }

        # Assemble final edges list
        edges: list[dict[str, Any]] = []
        for src in nodes:
            pid = src["project_id"]
            if project_filter and pid not in project_filter:
                continue
            meta = edge_meta.get(pid, {})
            target_vid = meta.get("target_video_id")
            seed_locked, lock_reason = self.is_seed_locked(src, force=force)
            playlist_spec = PILLAR_PLAYLIST_MAP.get(src.get("pillar", ""), {})

            if not target_vid:
                action = meta.get("status", "skipped")
            elif seed_locked:
                action = "deferred_seed_lock"
            elif (
                not force
                and src.get("existing_target_video_id") == target_vid
            ):
                action = "already_linked"
            else:
                action = "apply_link"

            edges.append({
                "source_project_id": pid,
                "source_video_id": src["video_id"],
                "source_title": src["title"],
                "source_pillar": src["pillar"],
                "source_visual_mode": src["visual_mode"],
                "source_visibility": src["visibility"],
                "source_views": src["views"],
                "source_impressions": src["impressions"],
                "target_type": meta.get("target_type"),
                "target_project_id": meta.get("target_project_id"),
                "target_video_id": target_vid,
                "target_title": meta.get("target_title"),
                "affinity_score": (meta.get("affinity") or {}).get("total", 0.0),
                "affinity_breakdown": meta.get("affinity") or {},
                "link_reason": lock_reason if seed_locked else meta.get("link_reason") or meta.get("reason", ""),
                "playlist_title": playlist_spec.get("title", ""),
                "existing_playlist_verified": bool(src.get("existing_playlist_verified")),
                "action": action,
            })

        # Verify 2-cycle count across planned edges
        pair_map = {
            e["source_video_id"]: e["target_video_id"]
            for e in edges
            if e.get("source_video_id") and e.get("target_video_id")
        }
        two_cycles: list[tuple[str, str]] = []
        for u_vid, v_vid in pair_map.items():
            if pair_map.get(v_vid) == u_vid and u_vid < v_vid:
                two_cycles.append((u_vid, v_vid))

        plan_doc = {
            "schema_version": 1,
            "generated_at_utc": self.now_utc.isoformat(),
            "mode": mode,
            "node_count": len(nodes),
            "edge_count": len(edges),
            "two_cycle_count": len(two_cycles),
            "two_cycles": two_cycles,
            "nodes": [
                {
                    "project_id": n["project_id"],
                    "video_id": n["video_id"],
                    "title": n["title"],
                    "pillar": n["pillar"],
                    "visual_mode": n["visual_mode"],
                    "visibility": n["visibility"],
                    "views": n["views"],
                    "impressions": n["impressions"],
                    "apv_pct": n["apv_pct"],
                    "regions": n["regions"],
                }
                for n in nodes
            ],
            "edges": edges,
        }
        return plan_doc

    def save_graph(self, plan_doc: dict[str, Any]) -> Path:
        self.graph_file.parent.mkdir(parents=True, exist_ok=True)
        self.graph_file.write_text(json.dumps(plan_doc, indent=2, ensure_ascii=False), encoding="utf-8")
        return self.graph_file


class StudioShortLinker:
    """
    Executes Related Video + 7-Pillar Playlist assignments inside visible Naver Whale
    over DirectCDPClient (/video/<video_id>/edit).
    """

    def __init__(
        self,
        cdp_port: int = DEFAULT_CDP_PORT,
        cdp_host: str = DEFAULT_CDP_HOST,
        projects_dir: Path | None = None,
        graph_file: Path | None = None,
        cdp_client_factory: Callable[[str], Any] | None = None,
        recycle_tab_fn: Callable[..., Any] | None = None,
    ):
        self.whale = WhaleSessionController(cdp_port=cdp_port, cdp_host=cdp_host)
        self.session = self.whale
        self.projects_dir = projects_dir or (CHANNEL_ROOT / "projects")
        self.graph_file = graph_file or SHORT_LINK_GRAPH_FILE
        self._cdp_client_factory = cdp_client_factory
        self._recycle_tab_fn = recycle_tab_fn
        self._edits_since_recycle = 0

    def _open_client(self, edit_url: str) -> Any:
        if self._cdp_client_factory is not None:
            return self._cdp_client_factory(edit_url)
        return self.whale.get_direct_client("studio.youtube.com", default_url=edit_url)

    async def _ensure_channel_safe(self, client: DirectCDPClient) -> bool:
        """
        Verifies the active Studio tab belongs to ALL ABOUT BRAIN (UC4FeioYYv9X04Di07_MfZ7g).
        Checks anchor hrefs FIRST so /video/<id>/edit sidebar #entity-name (video title) never triggers a false switch.
        """
        matched = await client.eval(
            f"""(() => {{
                const cid = {json.dumps(CHANNEL_ID)};
                if (location.href.includes(cid)) return true;
                if (document.querySelector(`a[href*="${{cid}}"]`)) return true;
                return false;
            }})()"""
        )
        return bool(matched)

    async def _assign_pillar_playlist_on_edit_page(
        self,
        client: DirectCDPClient,
        pillar: str,
    ) -> dict[str, Any]:
        spec = PILLAR_PLAYLIST_MAP.get(pillar)
        if not spec:
            return {"assigned": False, "playlist_title": "", "reason": f"unknown_pillar:{pillar}"}

        playlist_title = spec["title"]
        playlist_prefix = playlist_title.split("|")[0].strip()
        playlist_desc = spec["description"]

        # Read current playlist box text
        initial_text = str(await client.eval(
            """(() => {
                const el = document.querySelector('ytcp-video-metadata-playlists');
                return el ? (el.innerText || '').trim() : '';
            })()"""
        ) or "")
        if playlist_title in initial_text or (playlist_prefix and playlist_prefix in initial_text):
            return {
                "assigned": True,
                "created": False,
                "already_present": True,
                "playlist_title": playlist_title,
                "readback_text": initial_text,
            }

        clicked_trigger = await client.click(PLAYLIST_SELECTORS["trigger"])
        if not clicked_trigger:
            return {"assigned": False, "playlist_title": playlist_title, "reason": "playlist_trigger_not_found"}

        if not await client.wait_for_element(PLAYLIST_SELECTORS["dialog"], timeout_sec=10.0):
            return {"assigned": False, "playlist_title": playlist_title, "reason": "playlist_dialog_timeout"}

        await asyncio.sleep(1.0)

        # Try to find and check existing playlist inside ytcp-playlist-dialog
        check_state = await client.eval(
            f"""(() => {{
                const fullTitle = {json.dumps(playlist_title)};
                const prefixTitle = {json.dumps(playlist_prefix)};
                const dlg = document.querySelector('ytcp-playlist-dialog');
                if (!dlg) return {{ found: false }};
                const labels = Array.from(dlg.querySelectorAll('ytcp-checkbox-group li, tp-yt-paper-checkbox, ytcp-checkbox-lit, label'));
                for (const row of labels) {{
                    const txt = (row.innerText || row.textContent || '').trim();
                    if (!txt) continue;
                    if (txt.includes(fullTitle) || (prefixTitle && txt.includes(prefixTitle))) {{
                        const cb = row.matches('tp-yt-paper-checkbox, ytcp-checkbox-lit')
                            ? row
                            : row.querySelector('tp-yt-paper-checkbox, ytcp-checkbox-lit, input[type="checkbox"]');
                        const isChecked = cb
                            ? (cb.checked === true || cb.hasAttribute('checked') || cb.getAttribute('aria-checked') === 'true')
                            : false;
                        if (!isChecked) {{
                            (cb || row).scrollIntoView({{ block: 'center' }});
                            (cb || row).click();
                        }}
                        return {{ found: true, wasChecked: isChecked, matchedText: txt.slice(0, 120) }};
                    }}
                }}
                return {{ found: false }};
            }})()"""
        )

        created_new = False
        if not (isinstance(check_state, dict) and check_state.get("found")):
            # Create the playlist automatically
            opened_new = await client.click(PLAYLIST_SELECTORS["new_playlist_button"])
            if not opened_new:
                await client.eval("document.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', bubbles: true}))")
                return {"assigned": False, "playlist_title": playlist_title, "reason": "new_playlist_button_not_found"}

            await asyncio.sleep(0.8)
            if not await client.find_element(PLAYLIST_SELECTORS["creation_dialog"]):
                await client.click(PLAYLIST_SELECTORS["new_playlist_menu_item"])
                await asyncio.sleep(0.8)

            if not await client.wait_for_element(PLAYLIST_SELECTORS["creation_dialog"], timeout_sec=8.0):
                await client.eval("document.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', bubbles: true}))")
                return {"assigned": False, "playlist_title": playlist_title, "reason": "playlist_creation_dialog_timeout"}

            typed_title = await client.type_into(PLAYLIST_SELECTORS["creation_title_input"], playlist_title)
            if not typed_title:
                await client.eval("document.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', bubbles: true}))")
                return {"assigned": False, "playlist_title": playlist_title, "reason": "playlist_title_input_failed"}

            await asyncio.sleep(0.3)
            await client.type_into(PLAYLIST_SELECTORS["creation_description_input"], playlist_desc)
            await asyncio.sleep(0.4)

            submitted = await client.click(PLAYLIST_SELECTORS["creation_submit_button"])
            if not submitted:
                return {"assigned": False, "playlist_title": playlist_title, "reason": "playlist_create_submit_failed"}
            created_new = True
            await asyncio.sleep(2.2)

        # Close ytcp-playlist-dialog via Done
        await client.click(PLAYLIST_SELECTORS["done_button"])
        await asyncio.sleep(1.0)

        readback = str(await client.eval(
            """(() => {
                const el = document.querySelector('ytcp-video-metadata-playlists');
                return el ? (el.innerText || '').trim() : '';
            })()"""
        ) or "")
        verified = (
            playlist_title in readback
            or (bool(playlist_prefix) and playlist_prefix in readback)
            or (readback not in {"", "Select", "선택"} and "playlist" in readback.lower())
            or ("개" in readback)
        )
        return {
            "assigned": bool(verified),
            "created": created_new,
            "already_present": False,
            "playlist_title": playlist_title,
            "readback_text": readback,
        }

    async def _select_related_video_on_edit_page(
        self,
        client: DirectCDPClient,
        target_video_id: str,
        target_title: str,
    ) -> dict[str, Any]:
        # Check if trigger exists and whether Advanced Features lock is active
        trigger_probe = await client.eval(
            """(() => {
                const el = document.querySelector('#linked-video-editor-link')
                    || document.querySelector('ytcp-video-metadata-related-video');
                if (!el) return { exists: false };
                const txt = (el.innerText || '').trim();
                const disabled = el.hasAttribute('disabled') || el.getAttribute('aria-disabled') === 'true';
                return { exists: true, text: txt, disabled };
            })()"""
        )
        if not isinstance(trigger_probe, dict) or not trigger_probe.get("exists"):
            return {"verified": False, "status": "related_trigger_missing", "dom_readback_text": ""}
        if trigger_probe.get("disabled"):
            return {
                "verified": False,
                "status": "advanced_features_required",
                "dom_readback_text": str(trigger_probe.get("text") or ""),
            }

        clicked = await client.click(RELATED_VIDEO_SELECTORS["trigger"])
        if not clicked:
            return {"verified": False, "status": "related_trigger_click_failed", "dom_readback_text": ""}

        if not await client.wait_for_element(RELATED_VIDEO_SELECTORS["picker_dialog"], timeout_sec=10.0):
            return {"verified": False, "status": "picker_dialog_timeout", "dom_readback_text": ""}

        # Wait up to 6s for ytcp-entity-card list to render
        await client.wait_for_element(RELATED_VIDEO_SELECTORS["entity_card"], timeout_sec=6.0)
        await asyncio.sleep(0.6)

        async def _try_click_card() -> dict[str, Any]:
            res = await client.eval(
                f"""(() => {{
                    const targetVid = {json.dumps(target_video_id)};
                    const targetTitle = {json.dumps((target_title or '').strip().lower())};
                    const dlg = document.querySelector('ytcp-video-pick-dialog') || document;
                    const cards = Array.from(dlg.querySelectorAll('ytcp-entity-card'));
                    const extractVid = (c) => {{
                        try {{
                            if (c.video && c.video.videoId) return c.video.videoId;
                            if (c.data && c.data.videoId) return c.data.videoId;
                            if (c.__data && c.__data.video && c.__data.video.videoId) return c.__data.video.videoId;
                            const thumb = c.querySelector('.thumbnail');
                            const bg = thumb ? (thumb.getAttribute('style') || '') : '';
                            const m = bg.match(/\\/vi\\/([A-Za-z0-9_-]{{11}})\\//);
                            if (m) return m[1];
                        }} catch (e) {{}}
                        return '';
                    }};
                    const selectCard = (card, vid, matchMode, cardTitle) => {{
                        card.scrollIntoView({{ block: 'center' }});
                        const aria = card.getAttribute('aria-label') || '';
                        const alreadySelected = card.getAttribute('aria-selected') === 'true'
                            || (aria.includes('Selected') && !aria.includes('Not selected'));
                        if (alreadySelected) {{
                            const closeBtn = dlg.querySelector ? dlg.querySelector('#close-button button, #close-button') : null;
                            if (closeBtn) closeBtn.click();
                            return {{ matched: true, matchMode, videoId: vid, cardTitle, alreadySelected: true }};
                        }}
                        const hit = card.querySelector('#content') || card;
                        hit.click();
                        return {{ matched: true, matchMode, videoId: vid, cardTitle, alreadySelected: false }};
                    }};
                    // Pass 1: Exact YouTube videoId match (immune to duplicate titles / emoji edits)
                    for (const card of cards) {{
                        const vid = extractVid(card);
                        if (vid && vid === targetVid) {{
                            const cardTitle = (card.querySelector('.title') ? card.querySelector('.title').innerText : card.innerText || '').split('\\n')[0].trim();
                            return selectCard(card, vid, 'video_id', cardTitle);
                        }}
                    }}
                    // Pass 2: Normalized title fallback ONLY when card exposes no conflicting videoId
                    if (targetTitle) {{
                        for (const card of cards) {{
                            const vid = extractVid(card);
                            if (vid && vid !== targetVid) continue;
                            const rawText = (card.innerText || '').trim();
                            if (rawText.toLowerCase().includes(targetTitle)) {{
                                const cardTitle = rawText.split('\\n')[0].trim();
                                return selectCard(card, vid || targetVid, 'title_fallback', cardTitle);
                            }}
                        }}
                    }}
                    return {{ matched: false, cardCount: cards.length }};
                }})()"""
            )
            return res if isinstance(res, dict) else {"matched": False}

        pick_result = await _try_click_card()
        if not pick_result.get("matched") and target_title:
            search_query = re.sub(r"[^\w\s]", " ", target_title).strip()[:36]
            if search_query:
                typed = await client.type_into(RELATED_VIDEO_SELECTORS["search_input"], search_query)
                if typed:
                    await asyncio.sleep(1.6)
                    pick_result = await _try_click_card()

        if not pick_result.get("matched"):
            await client.click(["ytcp-video-pick-dialog #close-button", "ytcp-video-pick-dialog [aria-label='Close']"])
            await client.eval("document.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', bubbles: true}))")
            return {
                "verified": False,
                "status": "target_card_not_found",
                "card_count": pick_result.get("cardCount", 0),
                "dom_readback_text": "",
            }

        await asyncio.sleep(1.2)
        readback_info = await client.eval(
            """(() => {
                const el = document.querySelector('#linked-video-editor-link')
                    || document.querySelector('ytcp-video-metadata-related-video');
                if (!el) return { text: '', linkedId: '' };
                let linkedId = '';
                try {
                    const host = document.querySelector('ytcp-shorts-content-links') || el;
                    if (host.linkedVideo && host.linkedVideo.videoId) linkedId = host.linkedVideo.videoId;
                    else if (host.data && host.data.videoId) linkedId = host.data.videoId;
                } catch (e) {}
                return { text: (el.innerText || '').replace(/\\s+/g, ' ').trim(), linkedId };
            })()"""
        )
        readback_text = str((readback_info or {}).get("text") or "").strip()
        linked_id = str((readback_info or {}).get("linkedId") or "").strip()
        matched_card_title = str(pick_result.get("cardTitle") or "").strip()

        empty_markers = ("related video none", "관련 동영상 없음")
        is_non_empty = bool(readback_text) and readback_text.lower() not in empty_markers
        title_confirmed = (
            (bool(matched_card_title) and matched_card_title[:24].lower() in readback_text.lower())
            or (bool(target_title) and target_title[:24].lower() in readback_text.lower())
            or (linked_id == target_video_id)
        )
        verified = bool(is_non_empty and title_confirmed)
        return {
            "verified": verified,
            "status": "verified" if verified else "readback_mismatch",
            "match_mode": pick_result.get("matchMode"),
            "matched_card_title": matched_card_title,
            "dom_readback_text": readback_text,
        }

    async def _save_editor_changes(self, client: DirectCDPClient) -> dict[str, Any]:
        save_state = await client.eval(
            """(() => {
                const btn = document.querySelector('ytcp-video-metadata-editor ytcp-button#save')
                    || document.querySelector('ytcp-button#save')
                    || document.querySelector('#save');
                if (!btn) return { exists: false, disabled: true };
                const inner = btn.querySelector('button') || (btn.shadowRoot && btn.shadowRoot.querySelector('button'));
                const disabled = btn.hasAttribute('disabled')
                    || btn.getAttribute('aria-disabled') === 'true'
                    || (inner ? inner.disabled === true : false);
                return { exists: true, disabled };
            })()"""
        )
        if not isinstance(save_state, dict) or not save_state.get("exists"):
            return {"saved": False, "dirty": False, "reason": "save_button_not_found"}

        if save_state.get("disabled"):
            return {"saved": True, "dirty": False, "reason": "no_unsaved_changes"}

        clicked = await client.click(RELATED_VIDEO_SELECTORS["save_button"])
        if not clicked:
            return {"saved": False, "dirty": True, "reason": "save_click_failed"}

        # Wait up to 15s for #save to transition back to disabled
        for _ in range(30):
            await asyncio.sleep(0.5)
            done_now = await client.eval(
                """(() => {
                    const btn = document.querySelector('ytcp-video-metadata-editor ytcp-button#save')
                        || document.querySelector('ytcp-button#save')
                        || document.querySelector('#save');
                    if (!btn) return false;
                    const inner = btn.querySelector('button') || (btn.shadowRoot && btn.shadowRoot.querySelector('button'));
                    return btn.hasAttribute('disabled')
                        || btn.getAttribute('aria-disabled') === 'true'
                        || (inner ? inner.disabled === true : false);
                })()"""
            )
            if done_now:
                return {"saved": True, "dirty": True, "reason": "saved_and_confirmed"}

        return {"saved": False, "dirty": True, "reason": "save_confirmation_timeout"}

    async def apply_edge_async(
        self,
        edge: dict[str, Any],
        assign_playlist: bool = True,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        src_pid = str(edge.get("source_project_id") or "")
        src_vid = str(edge.get("source_video_id") or "")
        dst_vid = str(edge.get("target_video_id") or "")
        dst_title = str(edge.get("target_title") or "")
        pillar = str(edge.get("source_pillar") or "")
        action = str(edge.get("action") or "")

        if action in {"deferred_seed_lock", "blocked_invalid_direction", "no_valid_target", "skipped"}:
            return {
                "project_id": src_pid,
                "source_video_id": src_vid,
                "target_video_id": dst_vid,
                "status": action,
                "reason": edge.get("link_reason", ""),
                "verified": False,
            }

        if dry_run:
            return {
                "project_id": src_pid,
                "source_video_id": src_vid,
                "target_video_id": dst_vid,
                "target_title": dst_title,
                "playlist_title": edge.get("playlist_title", ""),
                "status": "dry_run_ready",
                "verified": False,
            }

        edit_url = f"https://studio.youtube.com/video/{src_vid}/edit"
        async with self._open_client(edit_url) as client:
            await client.send("Page.enable")
            await client.send("Runtime.enable")
            await client.send("Page.bringToFront")
            await client.send("Page.navigate", {"url": edit_url})
            ready = await client.wait_for_element(
                ["#linked-video-editor-link", "ytcp-video-metadata-editor"],
                timeout_sec=22.0,
            )
            if not ready:
                return {
                    "project_id": src_pid,
                    "source_video_id": src_vid,
                    "target_video_id": dst_vid,
                    "status": "edit_page_load_timeout",
                    "verified": False,
                }
            await asyncio.sleep(1.5)
            await client.send("Page.bringToFront")

            if not await self._ensure_channel_safe(client):
                return {
                    "project_id": src_pid,
                    "source_video_id": src_vid,
                    "target_video_id": dst_vid,
                    "status": "wrong_studio_channel",
                    "verified": False,
                }

            # Clear any stray open modal or menu before interacting
            await client.click(["ytcp-video-pick-dialog #close-button", "ytcp-playlist-creation-dialog #close-button"])
            await client.eval("document.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', bubbles: true}))")
            await asyncio.sleep(0.3)

            playlist_res: dict[str, Any] = {"assigned": False, "playlist_title": ""}
            if assign_playlist and pillar:
                playlist_res = await self._assign_pillar_playlist_on_edit_page(client, pillar)

            rel_res = await self._select_related_video_on_edit_page(client, dst_vid, dst_title)
            save_res = await self._save_editor_changes(client)

        verified = bool(rel_res.get("verified") and save_res.get("saved"))
        receipt = {
            "schema_version": 1,
            "project_id": src_pid,
            "source_video_id": src_vid,
            "source_title": edge.get("source_title"),
            "source_pillar": pillar,
            "source_visibility": edge.get("source_visibility"),
            "target_type": edge.get("target_type", "short"),
            "target_project_id": edge.get("target_project_id"),
            "target_video_id": dst_vid,
            "target_title": dst_title,
            "matched_card_title": rel_res.get("matched_card_title", ""),
            "match_mode": rel_res.get("match_mode", ""),
            "affinity_score": edge.get("affinity_score", 0.0),
            "link_reason": edge.get("link_reason", ""),
            "dom_readback_text": rel_res.get("dom_readback_text", ""),
            "playlist_title": playlist_res.get("playlist_title", ""),
            "playlist_verified": bool(playlist_res.get("assigned")),
            "playlist_created": bool(playlist_res.get("created")),
            "playlist_readback_text": playlist_res.get("readback_text", ""),
            "save_result": save_res,
            "status": "linked_verified" if verified else str(rel_res.get("status") or save_res.get("reason") or "failed"),
            "verified": verified,
            "verified_at_utc": datetime.now(timezone.utc).isoformat(),
        }

        if src_pid and (self.projects_dir / src_pid).exists():
            pub_dir = self.projects_dir / src_pid / "06_publish"
            pub_dir.mkdir(parents=True, exist_ok=True)
            (pub_dir / "related_video_receipt.json").write_text(
                json.dumps(receipt, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            write_studio_publish_receipt(src_pid, projects_dir=self.projects_dir)

        self._edits_since_recycle += 1
        if self._edits_since_recycle >= STUDIO_TAB_RECYCLE_INTERVAL:
            recycle_fn = self._recycle_tab_fn or (
                self.whale.recycle_studio_tab if self._cdp_client_factory is None else None
            )
            if recycle_fn is not None:
                try:
                    recycle_fn(reopen_url=STUDIO_CONTENT_URL)
                    self._edits_since_recycle = 0
                except Exception:
                    pass

        return receipt

    def run(
        self,
        mode: str = "seed_boost",
        assign_playlists: bool = True,
        dry_run: bool = False,
        force: bool = False,
        project_id: str | None = None,
        target_video_id: str | None = None,
        nodes: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        graph = ShortLinkGraph(
            projects_dir=self.projects_dir,
            graph_file=self.graph_file,
            nodes=nodes,
        )
        p_filter = {project_id} if project_id else None
        plan_doc = graph.plan_links(
            mode=mode,
            force=force,
            project_filter=p_filter,
            explicit_target_video_id=target_video_id,
        )
        if not dry_run:
            graph.save_graph(plan_doc)

        async def _run_batch() -> list[dict[str, Any]]:
            results: list[dict[str, Any]] = []
            for edge in plan_doc.get("edges", []):
                if (
                    edge.get("action") == "already_linked"
                    and not force
                    and (not assign_playlists or edge.get("existing_playlist_verified"))
                ):
                    src_pid = str(edge.get("source_project_id") or "")
                    if not dry_run and src_pid and (self.projects_dir / src_pid).exists():
                        pub_dir = self.projects_dir / src_pid / "06_publish"
                        rel_file = pub_dir / "related_video_receipt.json"
                        if rel_file.exists():
                            rel_data = _load_json_safe(rel_file)
                            if rel_data.get("affinity_score") != edge.get("affinity_score"):
                                rel_data["affinity_score"] = edge.get("affinity_score", 0.0)
                                rel_file.write_text(
                                    json.dumps(rel_data, indent=2, ensure_ascii=False),
                                    encoding="utf-8",
                                )
                        write_studio_publish_receipt(src_pid, projects_dir=self.projects_dir)
                    results.append({
                        "project_id": edge["source_project_id"],
                        "source_video_id": edge["source_video_id"],
                        "target_video_id": edge["target_video_id"],
                        "playlist_verified": bool(edge.get("existing_playlist_verified")),
                        "status": "already_linked",
                        "verified": True,
                    })
                    continue
                res = await self.apply_edge_async(
                    edge,
                    assign_playlist=assign_playlists,
                    dry_run=dry_run,
                )
                results.append(res)
            return results

        results = asyncio.run(_run_batch())
        plan_doc["execution_results"] = results
        plan_doc["verified_count"] = sum(1 for r in results if r.get("verified"))
        if not dry_run:
            graph.save_graph(plan_doc)
        return plan_doc
