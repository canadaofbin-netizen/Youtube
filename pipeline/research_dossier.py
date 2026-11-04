"""
ALL ABOUT BRAIN - Research Dossier system (R44) + reference-media analysis tools.

One dossier per topic in BCI_Shorts_Channel/research_dossiers/<slug>/, written at LONGFORM depth so the
Short is an extract (Hook + Core experiment + Twist) and an 8-15 min longform can be built from the same file.

    dossier.json               topic, visual_mode (+reason), case, core / wow facts, misconceptions, everyday hooks
    01_sources.json            primary paper, replications / follow-ups, critiques, reviews, books, archives, museums
    02_master_story.md         longform storyline (background -> people -> event -> experiment -> result -> twist -> after -> you)
    03_visual_reference.json   must-have scenes: era, layout (blocking), props, physical actions, reactions, recognition hook
    04_media_refs.json         YouTube / archive film / photos with timecodes and shot notes (analysis only, never reused)
    05_plain_language.json     jargon -> plain word -> analogy, one-sentence story, "so what for you"
    06_brain_link.json         region <-> plain name <-> function <-> scene <-> narration bridge (anatomy_map verified)
    07_longform_outline.json   chapters, scene ids, reusable Shorts roles, new shots / bridge clips needed
    media/<media_id>/          keyframes, contact sheet, transcript produced by analyze_reference_video()

Tools are free and local: Crossref REST (DOI check), yt-dlp (search / download), ffmpeg (scene keyframes),
faster-whisper (transcript). Downloaded reference videos are deleted after analysis unless keep_video=True.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pipeline.anatomy_map import resolve_region
from pipeline.config import RESEARCH_DOSSIERS_DIRNAME, VISUAL_MODES

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
DOSSIERS_ROOT = WORKSPACE_ROOT / "BCI_Shorts_Channel" / RESEARCH_DOSSIERS_DIRNAME
_DOI_SYNTAX_RE = re.compile(r"^10\.\d{4,9}/\S+$")
_VIDEO_FILE_EXTS = frozenset({".mp4", ".mkv", ".webm", ".mov"})
_FACT_META_EXCLUDED_KEYS = frozenset(
    {
        "created_at",
        "updated_at",
        "doi",
        "url",
        "schema",
        "schema_version",
        "shorts_priority",
        "id",
        "source_id",
        "media_id",
        "published_longform_video_id",
        "slug",
        "linked_projects",
        "local_dir",
        "t",
    }
)

DOSSIER_FILES: tuple[str, ...] = (
    "dossier.json",
    "01_sources.json",
    "02_master_story.md",
    "03_visual_reference.json",
    "04_media_refs.json",
    "05_plain_language.json",
    "06_brain_link.json",
    "07_longform_outline.json",
)
SOURCE_TYPES: tuple[str, ...] = (
    "primary", "primary_historical", "replication", "follow_up", "critique", "review", "book", "biography",
    "archive", "museum", "news", "documentary",
)
SCENE_REQUIRED_FIELDS: tuple[str, ...] = ("era", "layout", "props", "actions", "reactions")

# Research checklist (what every dossier must cover). Used by validate_dossier and shown to agents.
RESEARCH_CHECKLIST: tuple[tuple[str, str], ...] = (
    ("primary_source", "Original paper / report with verified DOI (or verified archival URL for pre-DOI history)"),
    ("method_details", "Exact procedure: apparatus, room, durations, numbers, who stood where"),
    ("follow_up", "Replication, follow-up or modern imaging study"),
    ("critique", "Criticism, controversy, failed replication or common misconception"),
    ("people", "Biographies of researchers and subjects, era context"),
    ("visual_media", "Original footage / archive photos / museum artefacts / famous recreations with timecodes"),
    ("iconic_scene", "The 'I know this!' scene broken down into era, layout, props, actions, reactions"),
    ("wow_facts", "At least 3 ranked 'no way!' facts for retention"),
    ("everyday_hook", "How this shows up in the viewer's own life"),
    ("plain_language", "Jargon map with everyday words and analogies"),
    ("brain_link", "Region <-> function <-> scene links (NEURO / HYBRID) verified against anatomy_map"),
    ("longform", "8-15 min chapter outline with Shorts extract (hook, core experiment, twist)"),
)


# ------------------------------------------------------------------------------
# Scaffold
# ------------------------------------------------------------------------------
def slugify(text: str) -> str:
    return re.sub(r"_+", "_", re.sub(r"[^a-z0-9]+", "_", str(text).lower())).strip("_")[:64]


def dossier_dir(slug: str, root: Path | None = None) -> Path:
    return Path(root or DOSSIERS_ROOT) / slugify(slug)


_EXPLICIT_PROJECT_SLUG_MAP: dict[str, str] = {
    "diorama_02_ramachandran_phantom_mirror": "ramachandran_phantom_limb_mirror",
    "diorama_04_milgram_obedience_switch": "milgram_obedience_shock",
    "diorama_14_libet_readiness_potential": "libet_readiness_potential_free_will",
    "diorama_20_dutton_aron_capilano_bridge": "dutton_aron_capilano_bridge_arousal",
    "diorama_21_delgado_stimoceiver_bull": "delgado_stimoceiver_bull_stop",
    "diorama_22_wernicke_fluent_aphasia": "wernicke_sensory_aphasia",
    "diorama_23_sperry_split_brain_corpus_callosum": "split_brain_corpus_callosum",
}


def resolve_dossier_for_project(project_id_or_dir: str | Path, root: Path | None = None) -> Path | None:
    """Resolve the research dossier directory for a project ID or project directory (supports legacy slug aliases via linked_projects)."""
    raw = Path(str(project_id_or_dir)).name if isinstance(project_id_or_dir, Path) or "/" in str(project_id_or_dir) else str(project_id_or_dir)
    pid = raw.strip()
    if not pid:
        return None
    base = Path(root) if root is not None else DOSSIERS_ROOT
    if not base.is_dir():
        return None
    mapped_slug = _EXPLICIT_PROJECT_SLUG_MAP.get(pid.lower())
    stripped_slug = slugify(re.sub(r"^(?:psych|diorama|reenact|news|longform)_\d+_", "", pid, flags=re.IGNORECASE))
    for cand_slug in (mapped_slug, slugify(pid), stripped_slug):
        if cand_slug and (base / cand_slug / "dossier.json").is_file():
            return base / cand_slug
    pid_lower = pid.lower()
    for d in sorted(base.iterdir()):
        meta_path = d / "dossier.json"
        if not meta_path.is_file():
            continue
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        linked = (
            list(meta.get("linked_projects") or [])
            + list(meta.get("shorts_projects") or [])
            + list(meta.get("longform_projects") or [])
        )
        for lp in linked:
            lp_str = str(lp).strip().lower()
            if lp_str == pid_lower or lp_str.startswith(pid_lower + " "):
                return d
    return None


def _templates(slug: str, topic: str, pillar: str, visual_mode: str) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return {
        "dossier.json": {
            "schema_version": 1,
            "slug": slug,
            "topic": topic,
            "pillar": pillar,
            "created_at": now,
            "status": "draft",
            "visual_mode": visual_mode,
            "visual_mode_reason": "",
            "primary_case": {"title": "", "year": None, "place": "", "people": []},
            "core_facts": [],
            "wow_facts": [],
            "misconceptions": [],
            "everyday_hooks": [],
            "offcenter_creator_bet": "",
            "debate_ignition": {
                "offcenter_creator_bet": "",
                "open_verdict_question": "",
            },
            "linked_projects": [],
        },
        "01_sources.json": {"sources": []},
        "02_master_story.md": (
            f"# {topic} — Master Story (longform depth)\n\n"
            "## 1. Cold open (the iconic moment)\n\n## 2. World before (era, place, why it mattered)\n\n"
            "## 3. People\n\n## 4. The event / experiment, step by step\n\n## 5. Results (numbers as reported)\n\n"
            "## 6. Twist, controversy, misconceptions\n\n## 7. What happened after (follow-ups, modern science)\n\n"
            "## 8. What it means for you\n\n## Sources\n"
        ),
        "03_visual_reference.json": {"scenes": []},
        "04_media_refs.json": {"media": []},
        "05_plain_language.json": {"one_sentence_story": "", "so_what_for_you": "", "jargon_map": []},
        "06_brain_link.json": {"visual_mode": visual_mode, "links": []},
        "07_longform_outline.json": {
            "target_minutes": 10,
            "published_longform_video_id": "",
            "published_longform_title": "",
            "shorts_extract": {"hook": "", "core_experiment": "", "twist": ""},
            "chapters": [],
        },
    }


def init_dossier(
    slug: str,
    topic: str,
    pillar: str = "",
    visual_mode: str = "HYBRID",
    root: Path | None = None,
    overwrite: bool = False,
) -> Path:
    """Creates the dossier folder with empty, schema-shaped files (never overwrites authored files unless asked)."""
    mode = visual_mode.upper()
    if mode not in VISUAL_MODES:
        raise ValueError(f"visual_mode must be one of {VISUAL_MODES}")
    d = dossier_dir(slug, root)
    (d / "media").mkdir(parents=True, exist_ok=True)
    for name, content in _templates(slugify(slug), topic, pillar, mode).items():
        path = d / name
        if path.exists() and not overwrite:
            continue
        if isinstance(content, str):
            path.write_text(content, encoding="utf-8")
        else:
            path.write_text(json.dumps(content, indent=2, ensure_ascii=False), encoding="utf-8")
    return d


def load_dossier(slug_or_dir: str | Path, root: Path | None = None) -> dict[str, Any]:
    d = Path(slug_or_dir) if Path(str(slug_or_dir)).is_dir() else dossier_dir(str(slug_or_dir), root)
    out: dict[str, Any] = {"_dir": str(d)}
    for name in DOSSIER_FILES:
        p = d / name
        if not p.exists():
            out[name] = None
            continue
        if name.endswith(".json"):
            try:
                out[name] = json.loads(p.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                out[name] = {"_error": str(exc)}
        else:
            out[name] = p.read_text(encoding="utf-8")
    return out


# ------------------------------------------------------------------------------
# Validation
# ------------------------------------------------------------------------------
def _nonempty(v: Any) -> bool:
    if v is None:
        return False
    if isinstance(v, str):
        return bool(v.strip())
    if isinstance(v, (list, dict)):
        return len(v) > 0
    return True


def _is_valid_doi_syntax(raw_doi: Any) -> bool:
    clean = str(raw_doi or "").strip()
    return bool(clean and _DOI_SYNTAX_RE.match(clean))


def _is_valid_source_record(entry: Any, *, require_title_key: bool = False) -> bool:
    if not isinstance(entry, dict):
        return False
    claimed_doi = str(entry.get("doi") or "").strip()
    if claimed_doi and not _is_valid_doi_syntax(claimed_doi):
        return False
    has_title = (
        _nonempty(entry.get("title"))
        if require_title_key
        else (_nonempty(entry.get("title")) or _nonempty(entry.get("citation")))
    )
    has_locator = bool(claimed_doi and _is_valid_doi_syntax(claimed_doi)) or _nonempty(entry.get("url"))
    return bool(has_title and has_locator)


def validate_dossier(slug_or_dir: str | Path, root: Path | None = None) -> dict[str, Any]:
    """Returns {'ready': bool, 'checklist': {item: bool}, 'issues': [...]} for the R44 completeness gate."""
    ds = load_dossier(slug_or_dir, root)
    issues: list[str] = []
    for name in DOSSIER_FILES:
        if ds.get(name) is None:
            issues.append(f"missing file {name}")
        elif isinstance(ds.get(name), dict) and ds[name].get("_error"):
            issues.append(f"{name}: invalid JSON ({ds[name]['_error']})")
    meta = ds.get("dossier.json") or {}
    sources_doc = ds.get("01_sources.json") or {}
    sources = sources_doc.get("sources") or []
    extra_followups = sources_doc.get("followups_replications_critiques") or []
    scenes = (ds.get("03_visual_reference.json") or {}).get("scenes") or []
    media = (ds.get("04_media_refs.json") or {}).get("media") or []
    plain = ds.get("05_plain_language.json") or {}
    brain = ds.get("06_brain_link.json") or {}
    longform = ds.get("07_longform_outline.json") or {}
    story = ds.get("02_master_story.md") or ""
    mode = str(meta.get("visual_mode") or "").upper()

    if mode not in VISUAL_MODES:
        issues.append(f"dossier.visual_mode must be one of {VISUAL_MODES}")
    if not _nonempty(meta.get("visual_mode_reason")):
        issues.append("dossier.visual_mode_reason is empty (why this topic needs / avoids the brain)")

    stypes = [str(s.get("type")) for s in sources if isinstance(s, dict)]
    for s in sources:
        if not isinstance(s, dict):
            continue
        if s.get("type") not in SOURCE_TYPES:
            issues.append(f"source {s.get('id')}: unknown type '{s.get('type')}'")
        claimed_doi = str(s.get("doi") or "").strip()
        if claimed_doi and not _is_valid_doi_syntax(claimed_doi):
            issues.append(f"source {s.get('id')}: invalid DOI syntax '{claimed_doi}'")
    for idx_fu, fu_entry in enumerate(extra_followups, start=1):
        if not isinstance(fu_entry, dict):
            continue
        claimed_doi = str(fu_entry.get("doi") or "").strip()
        if claimed_doi and not _is_valid_doi_syntax(claimed_doi):
            issues.append(f"followups_replications_critiques[{idx_fu}]: invalid DOI syntax '{claimed_doi}'")

    valid_sources = [s for s in sources if _is_valid_source_record(s, require_title_key=False)]
    valid_extra_followups = [f for f in extra_followups if _is_valid_source_record(f, require_title_key=True)]

    primary_ok = any(
        s.get("type") in ("primary", "primary_historical")
        and s.get("verified")
        and (_is_valid_doi_syntax(s.get("doi")) or (s.get("type") == "primary_historical" and _nonempty(s.get("url"))))
        for s in valid_sources
    )
    method_ok = sum(1 for s in scenes if isinstance(s, dict) and _nonempty(s.get("layout"))) >= 1 and len(story) > 1500
    people_ok = len((meta.get("primary_case") or {}).get("people") or []) >= 1
    iconic = [s for s in scenes if isinstance(s, dict) and s.get("iconic")]
    iconic_ok = len(iconic) == 1 and all(_nonempty(iconic[0].get(f)) for f in SCENE_REQUIRED_FIELDS) and _nonempty(
        iconic[0].get("recognition_hook")
    )
    for s in scenes:
        if not isinstance(s, dict):
            continue
        missing = [f for f in SCENE_REQUIRED_FIELDS if not _nonempty(s.get(f))]
        if missing:
            issues.append(f"visual_reference scene {s.get('id')}: missing {missing}")
    if len(iconic) != 1:
        issues.append(f"visual_reference needs exactly one iconic scene (got {len(iconic)})")

    links = brain.get("links") or []
    brain_ok = True
    if mode in ("HYBRID", "NEURO_BIOLOGY"):
        brain_ok = len(links) >= 1
    for link in links:
        if not isinstance(link, dict):
            continue
        if not resolve_region(str(link.get("region") or "")):
            brain_ok = False
            issues.append(f"brain_link region '{link.get('region')}' is not in anatomy_map")
        for f in ("plain", "function", "narration_bridge"):
            if not _nonempty(link.get(f)):
                brain_ok = False
                issues.append(f"brain_link '{link.get('region')}': missing {f}")
    if mode == "BEHAVIORAL_PSYCH" and links:
        issues.append("BEHAVIORAL_PSYCH dossiers should not plan on-screen brain links (move them to longform notes)")

    chapters = longform.get("chapters") or []
    extract = longform.get("shorts_extract") or {}
    lf_vid = str(longform.get("published_longform_video_id") or meta.get("published_longform_video_id") or "").strip()
    lf_vid_ok = True
    if lf_vid and not re.match(r"^[A-Za-z0-9_-]{11}$", lf_vid):
        lf_vid_ok = False
        issues.append(f"published_longform_video_id '{lf_vid}' must be an 11-character YouTube video ID")
    longform_ok = lf_vid_ok and len(chapters) >= 5 and all(_nonempty(extract.get(k)) for k in ("hook", "core_experiment", "twist"))

    checklist = {
        "primary_source": primary_ok,
        "method_details": method_ok,
        "follow_up": (
            any(s.get("type") in ("replication", "follow_up", "review") for s in valid_sources)
            or len(valid_extra_followups) >= 1
        ),
        "critique": any(t == "critique" for t in stypes) or len(meta.get("misconceptions") or []) >= 1,
        "people": people_ok,
        "visual_media": len(media) >= 1,
        "iconic_scene": iconic_ok,
        "wow_facts": len(meta.get("wow_facts") or []) >= 3,
        "everyday_hook": len(meta.get("everyday_hooks") or []) >= 1 and _nonempty(plain.get("so_what_for_you")),
        "plain_language": _nonempty(plain.get("one_sentence_story")) and isinstance(plain.get("jargon_map"), list),
        "brain_link": brain_ok,
        "longform": longform_ok,
    }
    depth = research_depth_report(ds, sources, scenes, media, meta, story)
    checklist["depth_standard"] = depth["passed"]
    issues += [f"[depth] {x}" for x in depth["issues"]]
    for key, ok in checklist.items():
        if not ok and key in dict(RESEARCH_CHECKLIST):
            desc = dict(RESEARCH_CHECKLIST)[key]
            issues.append(f"checklist '{key}' incomplete: {desc}")
    has_fatal_source_issue = any("invalid DOI syntax" in i for i in issues)
    return {
        "dir": ds["_dir"],
        "ready": all(checklist.values()) and not has_fatal_source_issue and not any("invalid JSON" in i for i in issues),
        "checklist": checklist,
        "issues": issues,
    }


# ------------------------------------------------------------------------------
# Research depth standard (how detailed is "detailed enough")
# ------------------------------------------------------------------------------
def research_depth_report(
    ds: dict[str, Any],
    sources: list[Any],
    scenes: list[Any],
    media: list[Any],
    meta: dict[str, Any],
    story: str,
) -> dict[str, Any]:
    """
    The depth bar every dossier must clear before Gear 2 (numbers live in config / production_constants):
    enough independent sources, every core fact traceable to a source id, the original footage actually
    analysed (keyframes on disk + timecoded shot notes), and an iconic scene concrete enough to stage
    (positions, props with look + physical behaviour, a key visual with must_show tokens).
    """
    from pipeline.config import (
        DOSSIER_MIN_ANALYZED_MEDIA,
        DOSSIER_MIN_CORE_FACTS,
        DOSSIER_MIN_FOLLOWUP_SOURCES,
        DOSSIER_MIN_ICONIC_POSITIONS,
        DOSSIER_MIN_ICONIC_PROPS,
        DOSSIER_MIN_KEYFRAMES,
        DOSSIER_MIN_MEDIA,
        DOSSIER_MIN_MEDIA_TIMECODES,
        DOSSIER_MIN_SOURCES,
        DOSSIER_MIN_STORY_CHARS,
    )

    issues: list[str] = []
    d = Path(ds["_dir"])
    raw_srcs = [s for s in sources if isinstance(s, dict)]
    sources_doc = ds.get("01_sources.json") or {}
    extra_followups = [
        f for f in (sources_doc.get("followups_replications_critiques") or []) if isinstance(f, dict)
    ]
    for s in raw_srcs:
        if s.get("type") in ("primary", "primary_historical", "replication", "follow_up", "review"):
            claimed_doi = str(s.get("doi") or "").strip()
            if claimed_doi and not _is_valid_doi_syntax(claimed_doi):
                issues.append(f"source {s.get('id')}: invalid DOI syntax '{claimed_doi}'")
    for idx_fu, fu_entry in enumerate(extra_followups, start=1):
        claimed_doi = str(fu_entry.get("doi") or "").strip()
        if claimed_doi and not _is_valid_doi_syntax(claimed_doi):
            issues.append(f"followups_replications_critiques[{idx_fu}]: invalid DOI syntax '{claimed_doi}'")
    srcs = [s for s in raw_srcs if _is_valid_source_record(s, require_title_key=False)]
    valid_extra_fu = [f for f in extra_followups if _is_valid_source_record(f, require_title_key=True)]
    src_ids = {str(s.get("id")) for s in srcs if s.get("id")}
    total_valid_sources = len(srcs) + len(valid_extra_fu)
    if total_valid_sources < DOSSIER_MIN_SOURCES:
        issues.append(f"{total_valid_sources} valid sources < {DOSSIER_MIN_SOURCES}")
    fu = sum(1 for s in srcs if s.get("type") in ("replication", "follow_up", "review")) + len(valid_extra_fu)
    if fu < DOSSIER_MIN_FOLLOWUP_SOURCES:
        issues.append(f"{fu} follow-up / replication / review sources < {DOSSIER_MIN_FOLLOWUP_SOURCES}")
    facts = [f for f in (meta.get("core_facts") or []) if isinstance(f, dict)]
    if len(facts) < DOSSIER_MIN_CORE_FACTS:
        issues.append(f"{len(facts)} core_facts < {DOSSIER_MIN_CORE_FACTS} (each {{fact, source_id}})")
    orphan = [f.get("fact", "")[:50] for f in facts if str(f.get("source_id")) not in src_ids]
    if orphan:
        issues.append(f"{len(orphan)} core_facts cite a source_id missing from 01_sources.json, e.g. '{orphan[0]}'")
    if len(story) < DOSSIER_MIN_STORY_CHARS:
        issues.append(f"master story {len(story)} chars < {DOSSIER_MIN_STORY_CHARS}")
    mlist = [m for m in media if isinstance(m, dict)]
    if len(mlist) < DOSSIER_MIN_MEDIA:
        issues.append(f"{len(mlist)} media refs < {DOSSIER_MIN_MEDIA}")
    analysed = 0
    edl_p = d / "08_reenactment_edl.json"
    has_reenact_edl = False
    if edl_p.exists():
        try:
            edl_data = json.loads(edl_p.read_text(encoding="utf-8"))
            has_reenact_edl = int(edl_data.get("shot_count") or len(edl_data.get("shots") or [])) >= 3
        except Exception:
            has_reenact_edl = False
    for m in mlist:
        tcs = [t for t in (m.get("timecodes") or []) if isinstance(t, dict) and t.get("t") and t.get("what")]
        is_still = str(m.get("kind") or "") in ("photo", "image", "museum_artefact", "museum_object", "still") or (
            bool(tcs) and all(str(t.get("t")).lower() == "still" for t in tcs)
        )
        need = 1 if is_still else DOSSIER_MIN_MEDIA_TIMECODES
        if len(tcs) < need:
            issues.append(f"media {m.get('id')}: {len(tcs)} shot notes < {need}")
        local = (m.get("analysis") or {}).get("local_dir") if isinstance(m.get("analysis"), dict) else None
        kf_dir = (d / local / "keyframes") if local else (d / "media" / str(m.get("id")) / "keyframes")
        has_kf_jpgs = kf_dir.exists() and len(list(kf_dir.glob("*.jpg"))) >= DOSSIER_MIN_KEYFRAMES
        if has_kf_jpgs:
            analysed += 1
    if has_reenact_edl and analysed == 0:
        analysed = 1
    if analysed < DOSSIER_MIN_ANALYZED_MEDIA:
        issues.append(
            f"{analysed} media analysed on disk (media/<id>/keyframes >= {DOSSIER_MIN_KEYFRAMES} or 08_reenactment_edl.json >= 3 shots) < {DOSSIER_MIN_ANALYZED_MEDIA}: "
            "run `dossier yt-analyze` or `reenact-extract` on the original footage"
        )
    iconic = [s for s in scenes if isinstance(s, dict) and s.get("iconic")]
    if iconic:
        ic = iconic[0]
        lay = ic.get("layout") if isinstance(ic.get("layout"), dict) else {}
        pos = [p for p in (lay.get("positions") or []) if isinstance(p, dict) and p.get("who") and p.get("where")]
        if len(pos) < DOSSIER_MIN_ICONIC_POSITIONS:
            issues.append(f"iconic layout.positions {len(pos)} < {DOSSIER_MIN_ICONIC_POSITIONS} (who / where / facing)")
        props = [
            p
            for p in (ic.get("props") or [])
            if isinstance(p, dict)
            and bool(str(p.get("name") or p.get("item") or "").strip())
            and p.get("period_detail")
            and p.get("physical_behavior")
        ]
        if len(props) < DOSSIER_MIN_ICONIC_PROPS:
            issues.append(f"iconic props with name/item + period_detail + physical_behavior {len(props)} < {DOSSIER_MIN_ICONIC_PROPS}")
        kv = ic.get("key_visual")
        if not (isinstance(kv, dict) and kv.get("description") and kv.get("must_show")):
            issues.append("iconic scene has no key_visual {description, must_show}: the money shot viewers remember (R46-K)")
        for f in ("wardrobe", "lighting", "sources"):
            if not _nonempty(ic.get(f)):
                issues.append(f"iconic scene: {f} is empty")
    return {"passed": not issues, "issues": issues}


def _extract_dossier_prose_chunks(node: Any, out: list[str]) -> None:
    if isinstance(node, dict):
        for k, v in node.items():
            if str(k) in _FACT_META_EXCLUDED_KEYS:
                continue
            _extract_dossier_prose_chunks(v, out)
    elif isinstance(node, list):
        for item in node:
            _extract_dossier_prose_chunks(item, out)
    elif isinstance(node, str):
        if node.strip():
            out.append(node.strip())
    elif isinstance(node, (int, float)) and not isinstance(node, bool):
        out.append(str(node))


def check_narration_facts(slug_or_dir: str | Path, narrations: list[str], root: Path | None = None) -> list[str]:
    """Every number shown in the subtitles must appear somewhere in the dossier (facts, story, sources)."""
    from pipeline.plain_language import to_display_text

    ds = load_dossier(slug_or_dir, root)
    prose_chunks: list[str] = []
    for doc_name in (
        "dossier.json",
        "01_sources.json",
        "03_visual_reference.json",
        "04_media_refs.json",
        "05_plain_language.json",
        "06_brain_link.json",
        "07_longform_outline.json",
    ):
        _extract_dossier_prose_chunks(ds.get(doc_name), prose_chunks)
    prose_chunks.append(str(ds.get("02_master_story.md") or ""))
    raw_corpus = " ".join(prose_chunks)
    norm_corpus = to_display_text(raw_corpus)
    corpus_digits = set(re.findall(r"\d+(?:\.\d+)?", norm_corpus.replace(",", "")))
    issues = []
    for i, line in enumerate(narrations, 1):
        for num in re.findall(r"\d+(?:\.\d+)?", to_display_text(str(line)).replace(",", "")):
            if num not in corpus_digits:
                issues.append(f"[fact] clip {i}: number {num} is not found anywhere in the dossier (add it with a source id)")
    return issues


def normalize_scene_prop(raw_prop: Any) -> dict[str, Any] | None:
    """Normalizes `03_visual_reference.json` prop entries across legacy `item` and canonical `name` keys."""
    if not isinstance(raw_prop, dict):
        return None
    name_val = str(raw_prop.get("name") or raw_prop.get("item") or "").strip()
    if not name_val:
        return None
    out = dict(raw_prop)
    out["name"] = name_val
    return out


# ------------------------------------------------------------------------------
# Dossier -> v5 / v7 visual_plan seed
# ------------------------------------------------------------------------------
def plan_seed_from_dossier(slug_or_dir: str | Path, root: Path | None = None) -> dict[str, Any]:
    """Draft v5 visual_plan fields (mode, must_have_scenes, cast hints, brain_link) for bci-script-gen to finish."""
    raw_str = str(slug_or_dir)
    target_dir = Path(slug_or_dir) if Path(raw_str).is_dir() else dossier_dir(raw_str, root)
    if not target_dir.exists():
        raise FileNotFoundError(f"Research dossier directory not found: {target_dir}")
    ds = load_dossier(target_dir, root)
    meta = ds.get("dossier.json") or {}
    scenes = (ds.get("03_visual_reference.json") or {}).get("scenes") or []
    links = (ds.get("06_brain_link.json") or {}).get("links") or []
    must = []
    for s in sorted(scenes, key=lambda s: (not s.get("iconic"), s.get("shorts_priority", 99))):
        if not isinstance(s, dict) or s.get("shorts_priority", 1) is None or int(s.get("shorts_priority", 1) or 1) > 3:
            continue
        norm_props = [np_p for np_p in (normalize_scene_prop(p) for p in (s.get("props") or [])) if np_p]
        entry: dict[str, Any] = {
            "id": s.get("id"),
            "title": s.get("title"),
            "iconic": bool(s.get("iconic")),
            "recognition_hook": s.get("recognition_hook"),
            "era": s.get("era"),
        }
        if isinstance(s.get("key_visual"), dict):
            entry["key_visual"] = dict(s["key_visual"])
        if norm_props:
            entry["props"] = norm_props
        must.append(entry)
    brain_link_map: dict[str, Any] = {}
    for i, l in enumerate(links):
        if not isinstance(l, dict):
            continue
        role_key = str(l.get("role") or l.get("scene_id") or i)
        if role_key not in brain_link_map:
            brain_link_map[role_key] = l
        elif isinstance(brain_link_map[role_key], list):
            brain_link_map[role_key].append(l)
        else:
            brain_link_map[role_key] = [brain_link_map[role_key], l]
    return {
        "schema": 5,
        "visual_mode": str(meta.get("visual_mode") or "HYBRID").upper(),
        "dossier": slugify(meta.get("slug") or Path(ds["_dir"]).name),
        "must_have_scenes": must,
        "brain_link": brain_link_map,
        "shots": {},
        "scenes": {},
    }


def diorama_seed_from_dossier(
    slug_or_dir: str | Path,
    root: Path | None = None,
    schema_version: int = 7,
    style_profile: str | None = None,
) -> dict[str, Any]:
    """Draft Schema v7 (`porcelain_cinematic_v7` default or `lowpoly_pastel_v7`) or Schema v6 `neuro_diorama` visual_plan seed."""
    from pipeline.config import (
        DEFAULT_DIORAMA_STYLE_PROFILE,
        DIORAMA_CLIP_COUNT_DEFAULT,
        PORCELAIN_V7_STYLE_PROFILE,
        PROMPT_SCHEMA_VERSION_V6,
        PROMPT_SCHEMA_VERSION_V7,
        resolve_diorama_v7_style_profile,
    )

    raw_str = str(slug_or_dir)
    target_dir = Path(slug_or_dir) if Path(raw_str).is_dir() else dossier_dir(raw_str, root)
    base = plan_seed_from_dossier(slug_or_dir, root=root)
    if int(schema_version) >= PROMPT_SCHEMA_VERSION_V7:
        resolved_style = resolve_diorama_v7_style_profile(
            {"style_profile": style_profile} if style_profile else None,
            fallback=DEFAULT_DIORAMA_STYLE_PROFILE,
        )
        iconic_scenes = [s for s in (base.get("must_have_scenes") or []) if isinstance(s, dict) and s.get("iconic")]
        cover_brief = ""
        if iconic_scenes:
            kv = iconic_scenes[0].get("key_visual") if isinstance(iconic_scenes[0].get("key_visual"), dict) else {}
            cover_brief = str(kv.get("description") or iconic_scenes[0].get("title") or "").strip()
        seed_clip_count = DIORAMA_CLIP_COUNT_DEFAULT if resolved_style == PORCELAIN_V7_STYLE_PROFILE else 61
        seeded_v7: dict[str, Any] = {
            "schema": PROMPT_SCHEMA_VERSION_V7,
            "schema_version": PROMPT_SCHEMA_VERSION_V7,
            "profile": "neuro_diorama",
            "style_profile": resolved_style,
            "camera_profile": "orthogonal_tripod_v7",
            "zero_clip_reuse": True,
            "require_signature_hooks": True,
            "visual_mode": base["visual_mode"],
            "dossier": base["dossier"],
            "thumbnail": {
                "hook_text": "TODO",
                "cover_sentence_index": 3,
                "cover_brief": cover_brief,
            },
            "act5_climax_episode": "",
            "must_have_scenes": base["must_have_scenes"],
            "brain_link": base["brain_link"],
            "chapter_headlines": [{"sentence_index": 3, "text": "TODO"}],
            "split_comparisons": [],
            "target_clip_count": seed_clip_count,
            "clips": [],
            "outro_title_lines": ["", ""],
        }
        if resolved_style == PORCELAIN_V7_STYLE_PROFILE:
            from pipeline.config import DEFAULT_DIORAMA_VOICE_PRESET, DIORAMA_V7_US_PROSODY_MODE
            from pipeline.porcelain_anchor_pack import populate_porcelain_reference_contract

            seeded_v7["voice_preset"] = DEFAULT_DIORAMA_VOICE_PRESET
            seeded_v7["prosody_mode"] = DIORAMA_V7_US_PROSODY_MODE
            seeded_v7["us_anti_clone_v7"] = True
            populate_porcelain_reference_contract(seeded_v7, dossier_dir=target_dir)
        return seeded_v7
    return {
        "schema": PROMPT_SCHEMA_VERSION_V6,
        "schema_version": PROMPT_SCHEMA_VERSION_V6,
        "profile": "neuro_diorama",
        "camera_profile": "dynamic_3d_cinema_rig",
        "zero_clip_reuse": True,
        "require_signature_hooks": True,
        "visual_mode": base["visual_mode"],
        "dossier": base["dossier"],
        "motif_prop": {
            "id": "analog_gauge_motif",
            "object": "a clear unprinted glass water tumbler beside a brushed-brass apothecary beam scale on a dark walnut workbench",
            "tokens": ["water tumbler", "beam scale"],
            "states": {
                "baseline": "calm mirror-flat surface",
                "crisis": "concentric high-frequency ripples across the water surface",
                "pivot": "steady rhythmic pulse",
                "breakthrough": "settled crystal-still reflection",
            },
        },
        "act5_climax_episode": "",
        "must_have_scenes": base["must_have_scenes"],
        "brain_link": base["brain_link"],
        "target_clip_count": 61,
        "clips": [],
        "top_callouts": [],
        "outro_title_lines": ["", ""],
    }


seed_diorama_visual_plan = diorama_seed_from_dossier


# ------------------------------------------------------------------------------
# 4-Gate Archival Reenactment Suitability Classifier (Dual-Track Gear 1)
# ------------------------------------------------------------------------------
_EXPLAINER_TITLE_MARKERS: tuple[str, ...] = (
    "ted talk",
    "tedx",
    "ted-ed",
    "crash course",
    "2-minute neuroscience",
    "2 minute neuroscience",
    "in 2 minutes",
    "explained in",
    "animated",
    "animation",
    "cartoon",
    "full lecture",
    "class lecture",
    "lecture:",
    "lecture ",
    "full interview",
    "interview with",
    "on the future of",
    "in conversation",
    "book talk",
    "book summary",
    "new free",
    "demo of a",
    "iconic memory test",
    "keynote",
    "colloquium",
    "webinar",
    "podcast",
    "audiobook",
    "slide deck",
    "powerpoint",
)

_COURSE_CODE_RE = re.compile(
    r"\b(?:psy|psyc|psych|neuro|bio|biol|cog|cogs|soc|anth|mit|yale|stanf)\s*[-_]?\s*\d{3,4}\b",
    re.IGNORECASE,
)

_ARCHIVAL_POSITIVE_CUES: tuple[str, ...] = (
    "archive",
    "archival",
    "original footage",
    "original experiment",
    "original film",
    "clinical footage",
    "experiment footage",
    "clinical trial",
    "nature video",
    "smoke filled room",
    "cat experiment",
    "puzzle box",
    "skinner",
    "16mm",
    "1920",
    "1930",
    "1940",
    "1950",
    "1960",
    "1961",
    "1962",
    "1963",
    "1970",
    "1971",
    "braingate",
    "bobo doll",
    "strange situation",
    "milgram",
    "harlow",
    "little albert",
    "pavlov",
    "split brain",
    "gazzaniga",
    "rubber hand",
    "invisible gorilla",
    "marshmallow test",
    "mcgurk",
)


def _format_mmss(sec: float) -> str:
    sec_i = max(0, int(round(sec)))
    if sec_i >= 3600:
        return f"{sec_i // 3600}:{(sec_i % 3600) // 60:02d}:{sec_i % 60:02d}"
    return f"{sec_i // 60:02d}:{sec_i % 60:02d}"


def _parse_tc_token_sec(tok: str) -> float | None:
    s = str(tok or "").strip().lstrip("*")
    if not s or s.lower() == "still":
        return None
    if "-" in s:
        s = s.split("-", 1)[0].strip()
    parts = s.split(":")
    try:
        if len(parts) == 1:
            return float(parts[0])
        if len(parts) == 2:
            return int(parts[0]) * 60.0 + float(parts[1])
        if len(parts) == 3:
            return int(parts[0]) * 3600.0 + int(parts[1]) * 60.0 + float(parts[2])
    except ValueError:
        return None
    return None


def _derive_recommended_section(
    timecodes: list[dict[str, Any]],
    duration_sec: float,
) -> str:
    action_spans: list[tuple[float, float]] = []
    all_secs: list[float] = []
    for tc in timecodes:
        if not isinstance(tc, dict):
            continue
        raw_t = str(tc.get("t") or "").strip().lstrip("*")
        t_val = _parse_tc_token_sec(raw_t)
        if t_val is None:
            continue
        t_end = t_val + 14.0
        if "-" in raw_t:
            rhs_val = _parse_tc_token_sec(raw_t.split("-", 1)[1])
            if rhs_val is not None and rhs_val > t_val:
                t_end = rhs_val
        all_secs.append(t_val)
        what_low = str(tc.get("what") or "").lower()
        if not any(
            w in what_low
            for w in (
                "interview", "presenter", "host", "title card", "credits",
                "subscribe", "talking head", "dark-backdrop stage", "studio camera frame",
            )
        ):
            action_spans.append((t_val, t_end))
    if action_spans:
        # Prefer the longest contiguous action span or bounded early-action window (<= 75s)
        best_span = max(action_spans, key=lambda sp: sp[1] - sp[0])
        if (best_span[1] - best_span[0]) >= 18.0:
            t0 = max(0.0, best_span[0] - 1.0)
            t1 = min(best_span[1] + 2.0, t0 + 90.0)
        else:
            t0 = max(0.0, action_spans[0][0] - 2.0)
            reachable = [sp[1] for sp in action_spans if sp[1] <= t0 + 88.0]
            t1 = max(t0 + 24.0, (max(reachable) + 4.0) if reachable else (t0 + 45.0))
        if duration_sec > 5.0:
            t1 = min(duration_sec, max(t0 + 10.0, t1))
        return f"{_format_mmss(t0)}-{_format_mmss(t1)}"
    if all_secs:
        t0 = max(0.0, min(all_secs) - 2.0)
        t1 = max(t0 + 24.0, min(max(all_secs) + 12.0, t0 + 75.0))
        if duration_sec > 5.0:
            t1 = min(duration_sec, max(t0 + 10.0, t1))
        return f"{_format_mmss(t0)}-{_format_mmss(t1)}"
    end_cap = min(max(30.0, duration_sec), 75.0) if duration_sec > 0 else 60.0
    return f"00:05-{_format_mmss(end_cap)}"


def _matches_reject_channel(channel_text: str) -> str | None:
    from pipeline.config import MEDIA_REJECT_CHANNEL_PATTERNS

    low = str(channel_text or "").strip().lower()
    if not low:
        return None
    for pat in MEDIA_REJECT_CHANNEL_PATTERNS:
        p = pat.lower().strip()
        if len(p) <= 4:
            if re.search(rf"\b{re.escape(p)}\b", low):
                return pat
        elif p in low:
            return pat
    return None


def evaluate_media_reenactment_suitability(
    media_entry: dict[str, Any],
    analysis_dir: str | Path | None = None,
    primary_year: int | None = None,
    has_reenact_edl: bool = False,
) -> dict[str, Any]:
    """
    4-Gate Archival Reenactment Suitability Classifier (`suitable_track_a` | `needs_section_window` | `reject_track_b_only`):
      - Gate 1: Kind / Channel / Title / Course-Code / Pre-Cinema Era (`< MEDIA_MIN_CINEMA_YEAR`) filter
      - Gate 2: Dark Stage / Void filter (`median(Y < 35) <= MEDIA_MAX_DARK_VOID_RATIO`)
      - Gate 3: Static Slide / Frozen Cover motion floor (`median_motion >= MEDIA_MIN_MOTION_DIFF`) +
                True 16mm B&W (`p90(HSV S) <= MEDIA_BW_FRAME_P90_SAT_MAX`) vs Flat Slide / 2D Vector (`<= MEDIA_MAX_FLAT_SLIDE_RATIO`)
      - Gate 4: YuNet Talking-Head Monologue + Transcript Speech Density & Mixed Host/B-Roll Windowing
    """
    import cv2
    import numpy as np
    from pipeline.config import (
        MEDIA_BW_ARCHIVAL_SAT_MAX,
        MEDIA_BW_FRAME_P90_SAT_MAX,
        MEDIA_MAX_DARK_VOID_RATIO,
        MEDIA_MAX_FLAT_SLIDE_RATIO,
        MEDIA_MAX_UNWINDOWED_DURATION_SEC,
        MEDIA_MIN_CINEMA_YEAR,
        MEDIA_MIN_MOTION_DIFF,
    )
    from pipeline.source_reenactment import detect_human_faces_yunet

    analysis_meta: dict[str, Any] = {}
    a_dir = Path(analysis_dir) if analysis_dir is not None else None
    if a_dir is not None and (a_dir / "analysis.json").exists():
        try:
            analysis_meta = json.loads((a_dir / "analysis.json").read_text(encoding="utf-8"))
        except Exception:
            analysis_meta = {}

    kind = str(media_entry.get("kind") or "").strip().lower()
    title = str(media_entry.get("title") or analysis_meta.get("title") or "").strip()
    channel = str(media_entry.get("channel") or analysis_meta.get("channel") or "").strip()
    url = str(media_entry.get("url") or analysis_meta.get("url") or "").strip()
    notes = str(media_entry.get("notes") or media_entry.get("description") or "").strip()
    dur_raw = media_entry.get("duration_sec") or analysis_meta.get("duration_sec") or 0.0
    try:
        duration_sec = float(dur_raw or 0.0)
    except (TypeError, ValueError):
        duration_sec = 0.0
    explicit_section = str(
        media_entry.get("reenactment_section")
        or media_entry.get("section")
        or ""
    ).strip().lstrip("*")
    timecodes = [t for t in (media_entry.get("timecodes") or []) if isinstance(t, dict)]

    # --- Gate 1: Metadata, Kind, Channel & Pre-Cinema Era ---
    is_still = kind in {
        "photo", "image", "still", "museum_artefact", "museum_object",
        "podcast", "audio", "diagram", "slides", "animation", "cartoon",
    } or (bool(timecodes) and all(str(t.get("t") or "").strip().lower() == "still" for t in timecodes))
    if is_still:
        return {
            "suitability": "reject_track_b_only",
            "reason": f"gate1_non_video_or_animation_kind({kind or 'still'})",
            "recommended_section": None,
            "metrics": {"gate_failed": 1},
        }
    if kind in {"lecture", "interview", "talk", "panel", "podcast_video", "explainer"}:
        return {
            "suitability": "reject_track_b_only",
            "reason": f"gate1_lecture_or_talking_head_kind({kind})",
            "recommended_section": None,
            "metrics": {"gate_failed": 1},
        }
    if primary_year is not None and 0 < int(primary_year) < MEDIA_MIN_CINEMA_YEAR and kind not in {"recreation_film", "archival_recreation"}:
        return {
            "suitability": "reject_track_b_only",
            "reason": f"gate1_pre_cinema_era({primary_year})",
            "recommended_section": None,
            "metrics": {"gate_failed": 1, "primary_year": int(primary_year)},
        }

    bad_chan = _matches_reject_channel(channel)
    if bad_chan:
        return {
            "suitability": "reject_track_b_only",
            "reason": f"gate1_rejected_explainer_channel({bad_chan})",
            "recommended_section": None,
            "metrics": {"gate_failed": 1, "matched_channel": bad_chan},
        }

    title_low = title.lower()
    blob_low = f"{title} {channel} {notes}".lower()
    is_archival_kind = kind in {
        "archive_film", "archival_footage", "clinical_footage", "experiment_footage",
    }
    has_strong_archival_cue = is_archival_kind or any(cue in blob_low for cue in _ARCHIVAL_POSITIVE_CUES)

    if _COURSE_CODE_RE.search(title_low):
        return {
            "suitability": "reject_track_b_only",
            "reason": "gate1_university_course_slide_lecture",
            "recommended_section": None,
            "metrics": {"gate_failed": 1},
        }

    if re.search(r"\(\d{1,3}/\d{1,3}\)", title_low) and not (
        is_archival_kind and ("archival" in title_low or "footage" in title_low or "original" in title_low)
    ):
        return {
            "suitability": "reject_track_b_only",
            "reason": "gate1_oral_history_series_clip",
            "recommended_section": None,
            "metrics": {"gate_failed": 1},
        }

    for marker in _EXPLAINER_TITLE_MARKERS:
        if marker in title_low and not (
            is_archival_kind
            and ("original" in title_low or "archival" in title_low or "footage" in title_low)
        ):
            return {
                "suitability": "reject_track_b_only",
                "reason": f"gate1_explainer_or_lecture_title({marker})",
                "recommended_section": None,
                "metrics": {"gate_failed": 1, "matched_title_marker": marker},
            }

    # --- Gates 2, 3, 4 on extracted keyframes + transcript (when present) ---
    kf_files = sorted((a_dir / "keyframes").glob("*.jpg")) if (a_dir is not None and (a_dir / "keyframes").exists()) else []
    words_per_sec = 0.0
    if a_dir is not None and (a_dir / "transcript.txt").exists():
        try:
            t_lines = (a_dir / "transcript.txt").read_text(encoding="utf-8").splitlines()
            spans: list[tuple[float, float]] = []
            w_total = 0
            for ln in t_lines:
                m_ts = re.match(r"^\[\s*(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)\s*\]\s*(.*)$", ln.strip())
                if m_ts:
                    spans.append((float(m_ts.group(1)), float(m_ts.group(2))))
                    w_total += len(re.findall(r"[A-Za-z0-9']+", m_ts.group(3)))
                else:
                    w_total += len(re.findall(r"[A-Za-z0-9']+", ln))
            dur_span = (max(s[1] for s in spans) - min(s[0] for s in spans)) if spans else max(duration_sec, 1.0)
            words_per_sec = round(w_total / max(dur_span, 5.0), 3)
        except Exception:
            words_per_sec = 0.0

    if kf_files:
        from concurrent.futures import ThreadPoolExecutor

        dark_ratios: list[float] = []
        gray_sat_ratios: list[float] = []
        p90_sats: list[float] = []
        flat_patch_ratios: list[float] = []
        small_grays: list[np.ndarray] = []
        talking_head_flags: list[bool] = []
        non_head_indices: list[int] = []

        sample_count = min(8, len(kf_files))
        sample_idxs = sorted({int(x) for x in np.linspace(0, len(kf_files) - 1, sample_count, dtype=int).tolist()})
        sampled_paths = [kf_files[i] for i in sample_idxs]

        def _decode_kf(p: Path) -> np.ndarray | None:
            try:
                raw_b = p.read_bytes()
                if not raw_b:
                    return None
                arr = np.frombuffer(raw_b, dtype=np.uint8)
                return cv2.imdecode(arr, cv2.IMREAD_COLOR)
            except Exception:
                return cv2.imread(str(p))

        with ThreadPoolExecutor(max_workers=min(8, max(1, len(sampled_paths)))) as pool:
            decoded_frames = list(pool.map(_decode_kf, sampled_paths))

        for idx_f, bgr in zip(sample_idxs, decoded_frames):
            if bgr is None or bgr.size == 0:
                continue
            h_f, w_f = bgr.shape[:2]
            gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
            hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
            small_grays.append(cv2.resize(gray, (160, 120), interpolation=cv2.INTER_AREA))
            dark_ratios.append(float(np.mean(gray < 35)))
            gray_sat_ratios.append(float(np.mean(hsv[:, :, 1] < MEDIA_BW_ARCHIVAL_SAT_MAX)))
            # Trim 4% outer overscan/tracking border before measuring p90 chroma so 2px green VHS lines don't skew B&W film
            my, mx = max(1, int(h_f * 0.04)), max(1, int(w_f * 0.04))
            inner_s = hsv[my : h_f - my, mx : w_f - mx, 1]
            p90_sats.append(float(np.percentile(inner_s if inner_s.size else hsv[:, :, 1], 90)))

            # 16x16 patch texture std for Gate 3 flat slide / vector cartoon detection
            bh = max(1, h_f // 16)
            bw = max(1, w_f // 16)
            cropped_g = gray[: bh * 16, : bw * 16].reshape(bh, 16, bw, 16)
            patch_stds = np.std(cropped_g.astype(np.float32), axis=(1, 3))
            flat_patch_ratios.append(float(np.mean(patch_stds < 4.5)))

            faces = detect_human_faces_yunet(bgr, score_threshold=0.46)
            is_th = False
            if faces:
                faces_by_area = sorted(faces, key=lambda b: b[2] * b[3], reverse=True)
                fx, fy, fw, fh, _sc = faces_by_area[0]
                dom_area = float(fw * fh)
                second_area = float(faces_by_area[1][2] * faces_by_area[1][3]) if len(faces_by_area) > 1 else 0.0
                if len(faces_by_area) == 1 or dom_area >= 2.0 * max(1.0, second_area):
                    area_ratio = dom_area / max(1.0, float(w_f * h_f))
                    cx_norm = (fx + fw * 0.5) / max(1.0, float(w_f))
                    if area_ratio >= 0.038 or (area_ratio >= 0.022 and 0.22 <= cx_norm <= 0.78):
                        is_th = True
            talking_head_flags.append(is_th)
            if not is_th:
                non_head_indices.append(idx_f)

        if dark_ratios:
            motion_diffs = [
                float(np.mean(np.abs(small_grays[i + 1].astype(np.float32) - small_grays[i].astype(np.float32))))
                for i in range(len(small_grays) - 1)
            ]
            med_motion = round(float(np.median(motion_diffs)), 3) if motion_diffs else 99.0
            max_motion = round(float(max(motion_diffs)), 3) if motion_diffs else 99.0
            med_dark = round(float(np.median(dark_ratios)), 4)
            med_gray_sat = round(float(np.median(gray_sat_ratios)), 4)
            med_p90_sat = round(float(np.median(p90_sats)), 2) if p90_sats else 0.0
            min_p90_sat = round(float(min(p90_sats)), 2) if p90_sats else 0.0
            max_p90_sat = round(float(max(p90_sats)), 2) if p90_sats else 0.0
            med_flat = round(float(np.median(flat_patch_ratios)), 4)
            # True 1920s–60s B&W 16mm film has low frame-wide p90 chroma across ALL frames (not blank >92% white test screen)
            is_bw_archival = bool(
                med_gray_sat >= 0.82
                and med_p90_sat <= MEDIA_BW_FRAME_P90_SAT_MAX
                and max_p90_sat <= 52.0
                and med_flat <= 0.92
            )
            is_mixed_bw_and_color = bool(min_p90_sat < 25.0 and max_p90_sat >= 75.0)
            talking_head_ratio = round(
                sum(1 for fl in talking_head_flags if fl) / max(1, len(talking_head_flags)),
                4,
            )
            shot_notes_low = " ".join(
                str(x) for x in ((media_entry.get("analysis") or {}).get("shot_notes") or [])
            ).lower()
            metrics = {
                "keyframe_count": len(kf_files),
                "median_dark_ratio": med_dark,
                "median_gray_sat_ratio": med_gray_sat,
                "median_p90_sat": med_p90_sat,
                "max_p90_sat": max_p90_sat,
                "is_bw_archival": is_bw_archival,
                "is_mixed_bw_and_color": is_mixed_bw_and_color,
                "median_flat_patch_ratio": med_flat,
                "median_motion_diff": med_motion,
                "talking_head_ratio": talking_head_ratio,
                "words_per_sec": words_per_sec,
                "has_strong_archival_cue": has_strong_archival_cue,
            }

            # Gate 2: Dark Stage / Void Filter
            if med_dark > MEDIA_MAX_DARK_VOID_RATIO:
                return {
                    "suitability": "reject_track_b_only",
                    "reason": f"gate2_dark_stage_void(median_dark={med_dark}>{MEDIA_MAX_DARK_VOID_RATIO})",
                    "recommended_section": None,
                    "metrics": {**metrics, "gate_failed": 2},
                }

            # Gate 3a: Static Slide / Frozen Book Cover / Audio Upload Filter
            if len(motion_diffs) >= 2 and (med_motion < MEDIA_MIN_MOTION_DIFF or max_motion < 1.8):
                return {
                    "suitability": "reject_track_b_only",
                    "reason": f"gate3_static_slide_or_frozen_cover(med_motion={med_motion}<{MEDIA_MIN_MOTION_DIFF})",
                    "recommended_section": None,
                    "metrics": {**metrics, "gate_failed": 3},
                }

            # Gate 3b: B&W-Safe Flat Slide / 2D Cartoon Filter
            if (not is_bw_archival and med_flat > MEDIA_MAX_FLAT_SLIDE_RATIO) or med_flat > 0.92:
                return {
                    "suitability": "reject_track_b_only",
                    "reason": f"gate3_flat_slide_or_2d_cartoon(median_flat={med_flat}>{MEDIA_MAX_FLAT_SLIDE_RATIO})",
                    "recommended_section": None,
                    "metrics": {**metrics, "gate_failed": 3},
                }

            # Gate 4: Talking-Head Monologue vs Silent Archival Subject vs Mixed Documentary
            is_silent_archival_subject = bool(
                (is_archival_kind or is_bw_archival or has_strong_archival_cue)
                and words_per_sec < 1.05
            )
            if talking_head_ratio >= 0.62 and not is_silent_archival_subject:
                return {
                    "suitability": "reject_track_b_only",
                    "reason": f"gate4_talking_head_monologue(ratio={talking_head_ratio},wps={words_per_sec})",
                    "recommended_section": None,
                    "metrics": {**metrics, "gate_failed": 4},
                }

            has_embedded_bw_archival = bool(
                is_mixed_bw_and_color and med_p90_sat <= MEDIA_BW_FRAME_P90_SAT_MAX
            )
            if not is_bw_archival and not has_strong_archival_cue and not has_embedded_bw_archival:
                if (
                    words_per_sec >= 2.1
                    or ("speaker/interview recording" in shot_notes_low and words_per_sec >= 1.6)
                    or (talking_head_ratio >= 0.25 and words_per_sec >= 1.75)
                ):
                    return {
                        "suitability": "reject_track_b_only",
                        "reason": f"gate4_modern_monologue_without_archival_footage(wps={words_per_sec},th={talking_head_ratio})",
                        "recommended_section": None,
                        "metrics": {**metrics, "gate_failed": 4},
                    }

            needs_window = (
                (0.25 <= talking_head_ratio < 0.62 and not explicit_section and not is_bw_archival)
                or (is_mixed_bw_and_color and not explicit_section)
                or (duration_sec > MEDIA_MAX_UNWINDOWED_DURATION_SEC and not explicit_section)
                or (
                    kind in {"documentary", "news", "tv_segment", "video"}
                    and not is_bw_archival
                    and duration_sec > 180.0
                    and not explicit_section
                )
            )
            if needs_window:
                rec_sec = _derive_recommended_section(timecodes, duration_sec)
                return {
                    "suitability": "needs_section_window",
                    "reason": "gate4_mixed_commentary_or_unwindowed_long_video",
                    "recommended_section": rec_sec,
                    "metrics": metrics,
                }

            return {
                "suitability": "suitable_track_a",
                "reason": "passed_gates_1_to_4_with_keyframes",
                "recommended_section": explicit_section or None,
                "metrics": metrics,
            }

    # --- Metadata-only path when keyframes have not been extracted yet ---
    if has_reenact_edl:
        return {
            "suitability": "suitable_track_a",
            "reason": "verified_08_reenactment_edl_present",
            "recommended_section": explicit_section or None,
            "metrics": {"has_reenact_edl": True},
        }

    has_video_url = bool(url and url.startswith("http"))
    if has_video_url and is_archival_kind and has_strong_archival_cue:
        if duration_sec > MEDIA_MAX_UNWINDOWED_DURATION_SEC and not explicit_section:
            return {
                "suitability": "needs_section_window",
                "reason": "archival_source_exceeds_unwindowed_duration_cap",
                "recommended_section": _derive_recommended_section(timecodes, duration_sec),
                "metrics": {"duration_sec": duration_sec, "archival_cue": True},
            }
        return {
            "suitability": "suitable_track_a",
            "reason": "archival_or_experiment_video_metadata_match",
            "recommended_section": explicit_section or None,
            "metrics": {"duration_sec": duration_sec, "archival_cue": True},
        }

    if has_video_url and has_strong_archival_cue and timecodes:
        return {
            "suitability": "needs_section_window",
            "reason": "unanalyzed_archival_url_requires_section_window",
            "recommended_section": explicit_section or _derive_recommended_section(timecodes, duration_sec),
            "metrics": {"duration_sec": duration_sec, "archival_cue": True, "unanalyzed": True},
        }

    if has_video_url and kind in {"demonstration", "recreation_film"} and timecodes:
        return {
            "suitability": "needs_section_window",
            "reason": "demonstration_or_recreation_requires_action_window",
            "recommended_section": explicit_section or _derive_recommended_section(timecodes, duration_sec),
            "metrics": {"duration_sec": duration_sec},
        }

    return {
        "suitability": "reject_track_b_only",
        "reason": "no_verified_archival_or_experiment_footage_for_track_a",
        "recommended_section": None,
        "metrics": {"duration_sec": duration_sec},
    }


def audit_dossier_media_suitability(
    slug_or_dir: str | Path,
    root: Path | None = None,
    write_back: bool = False,
    use_cached: bool = False,
) -> dict[str, Any]:
    """
    Audits all entries in `<dossier>/04_media_refs.json` via `evaluate_media_reenactment_suitability`
    and classifies the episode into `track_a` (`A1a_ready_keyframes` / `A1b_archive_url` / `A2_section_window`)
    or `track_b` (`B_scene_bible_anchor`).
    """
    from pipeline.config import MEDIA_SUITABILITY_SCHEMA_VERSION

    raw_str = str(slug_or_dir)
    d_dir = Path(slug_or_dir) if Path(raw_str).is_dir() else dossier_dir(raw_str, root)
    if not d_dir.exists():
        raise FileNotFoundError(f"Research dossier directory not found: {d_dir}")

    ds = load_dossier(d_dir, root)
    meta = ds.get("dossier.json") or {}
    sources_doc = ds.get("01_sources.json") or {}
    media_doc = ds.get("04_media_refs.json") or {}
    media_list = [m for m in (media_doc.get("media") or []) if isinstance(m, dict)]

    # Infer primary case year (for pre-1895 cinema check)
    primary_year: int | None = None
    p_case = meta.get("primary_case") if isinstance(meta.get("primary_case"), dict) else {}
    if p_case.get("year"):
        m_yr = re.search(r"\b(1[5-9]\d{2}|20\d{2})\b", str(p_case.get("year")))
        if m_yr:
            primary_year = int(m_yr.group(1))
    if primary_year is None:
        for s in sources_doc.get("sources") or []:
            if isinstance(s, dict) and s.get("type") in ("primary", "primary_historical") and s.get("year"):
                m_yr = re.search(r"\b(1[5-9]\d{2}|20\d{2})\b", str(s.get("year")))
                if m_yr:
                    primary_year = int(m_yr.group(1))
                    break

    edl_p = d_dir / "08_reenactment_edl.json"
    has_reenact_edl = edl_p.exists()
    cached_schema_ok = int(media_doc.get("suitability_schema_version") or 0) == MEDIA_SUITABILITY_SCHEMA_VERSION

    evaluated_media: list[dict[str, Any]] = []
    primary_track_a_media: dict[str, Any] | None = None
    best_subtier = "B_scene_bible_anchor"
    best_score_tuple = (0, 0)

    for idx_m, m in enumerate(media_list):
        m_id = str(m.get("id") or f"M{idx_m + 1}")
        local_rel = (m.get("analysis") or {}).get("local_dir") if isinstance(m.get("analysis"), dict) else None
        a_dir = (d_dir / local_rel) if local_rel else (d_dir / "media" / m_id)
        has_kfs = (a_dir / "keyframes").exists() and len(list((a_dir / "keyframes").glob("*.jpg"))) >= 4
        cached_cls = str(m.get("reenactment_suitability") or "").strip()
        if use_cached and cached_schema_ok and cached_cls in ("suitable_track_a", "needs_section_window", "reject_track_b_only"):
            rec_s = str(m.get("reenactment_section") or m.get("recommended_section") or "").strip().lstrip("*") or None
            res = {
                "suitability": cached_cls,
                "reason": str(m.get("reenactment_suitability_reason") or "cached_audit"),
                "recommended_section": rec_s,
                "metrics": dict(m.get("reenactment_suitability_metrics") or {}),
            }
        else:
            res = evaluate_media_reenactment_suitability(
                m,
                analysis_dir=a_dir if a_dir.exists() else None,
                primary_year=primary_year,
                has_reenact_edl=(has_reenact_edl and idx_m == 0),
            )
        suit_cls = str(res["suitability"])
        if write_back:
            m["reenactment_suitability"] = suit_cls
            m["reenactment_suitability_reason"] = res["reason"]
            m["reenactment_suitability_metrics"] = dict(res.get("metrics") or {})
            if res.get("recommended_section"):
                m["recommended_section"] = str(res["recommended_section"]).lstrip("*")
            else:
                m.pop("recommended_section", None)

        row = {
            "id": m_id,
            "kind": m.get("kind"),
            "title": m.get("title"),
            "channel": m.get("channel"),
            "url": m.get("url"),
            "has_keyframes_on_disk": has_kfs,
            **res,
        }
        evaluated_media.append(row)

        # Prefer keyframe-verified media (`has_kfs=1`) over unanalyzed URLs (`has_kfs=0`)
        if suit_cls == "suitable_track_a":
            cand_tier = "A1a_ready_keyframes" if (has_kfs or has_reenact_edl) else "A1b_archive_url"
            cand_score = (3 if (has_kfs or has_reenact_edl) else 1, 1 if has_kfs else 0)
            if cand_score > best_score_tuple:
                best_score_tuple = cand_score
                best_subtier = cand_tier
                primary_track_a_media = row
        elif suit_cls == "needs_section_window":
            cand_score = (2 if has_kfs else 1, 1 if has_kfs else 0)
            if cand_score > best_score_tuple:
                best_score_tuple = cand_score
                best_subtier = "A2_section_window"
                primary_track_a_media = row

    if has_reenact_edl and best_subtier == "B_scene_bible_anchor":
        best_subtier = "A1a_ready_keyframes"

    track = "track_a" if best_subtier.startswith("A") else "track_b"

    if write_back:
        if isinstance(media_doc, dict) and (d_dir / "04_media_refs.json").exists():
            media_doc["suitability_schema_version"] = MEDIA_SUITABILITY_SCHEMA_VERSION
            media_doc["reenactment_track"] = track
            media_doc["track_subtier"] = best_subtier
            (d_dir / "04_media_refs.json").write_text(
                json.dumps(media_doc, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
        if isinstance(meta, dict) and (d_dir / "dossier.json").exists():
            meta["reenactment_track"] = track
            meta["reenactment_track_subtier"] = best_subtier
            (d_dir / "dossier.json").write_text(
                json.dumps(meta, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )

    return {
        "slug": d_dir.name,
        "dossier_dir": str(d_dir),
        "primary_year": primary_year,
        "has_reenact_edl": has_reenact_edl,
        "reenactment_track": track,
        "track_subtier": best_subtier,
        "primary_track_a_media": primary_track_a_media,
        "media_evaluations": evaluated_media,
    }


# ------------------------------------------------------------------------------
# Free reference tools
# ------------------------------------------------------------------------------
def _parse_section_bounds(section: str) -> tuple[int, int]:
    """Parses optional '*MM:SS-MM:SS' or '*HH:MM:SS-HH:MM:SS' into (start_sec, end_sec)."""
    raw = str(section or "").strip()
    m = re.match(r"^\*?(?:(\d+):)?(\d{1,2}):(\d{2})-(?:(\d+):)?(\d{1,2}):(\d{2})$", raw)
    if not m:
        raise ValueError(
            f"Invalid section format {section!r}; expected 'MM:SS-MM:SS' or 'HH:MM:SS-HH:MM:SS'"
        )
    h1, m1, s1, h2, m2, s2 = m.groups()
    sec1, sec2 = int(s1), int(s2)
    min1, min2 = int(m1), int(m2)
    if sec1 >= 60 or sec2 >= 60 or (h1 is not None and min1 >= 60) or (h2 is not None and min2 >= 60):
        raise ValueError(f"Invalid section clock bounds in {section!r}")
    start_sec = (int(h1) * 3600 if h1 is not None else 0) + min1 * 60 + sec1
    end_sec = (int(h2) * 3600 if h2 is not None else 0) + min2 * 60 + sec2
    if end_sec <= start_sec:
        raise ValueError(f"Invalid section range {section!r}: end ({end_sec}s) must exceed start ({start_sec}s)")
    return start_sec, end_sec


def verify_doi(doi: str, timeout: float = 10.0) -> dict[str, Any]:
    """Crossref lookup with doi.org/api/handles fallback (DataCite/non-Crossref DOIs)."""
    clean = re.sub(r"^https?://(dx\.)?doi\.org/", "", str(doi or "").strip(), flags=re.IGNORECASE)
    if not clean:
        return {"verified": False, "error": "empty DOI"}
    if not _is_valid_doi_syntax(clean):
        return {"verified": False, "doi": clean, "error": f"invalid DOI syntax: {clean}"}
    headers = {"User-Agent": "AllAboutBrain-Research/1.0 (mailto:kbforuni@gmail.com)"}
    url = "https://api.crossref.org/works/" + urllib.parse.quote(clean, safe="/")
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            msg = json.loads(resp.read().decode("utf-8")).get("message", {})
        year = None
        for key in ("published-print", "published-online", "issued", "created"):
            parts = (msg.get(key) or {}).get("date-parts") or []
            if parts and parts[0]:
                year = parts[0][0]
                break
        return {
            "verified": True,
            "doi": clean,
            "title": (msg.get("title") or [""])[0],
            "journal": (msg.get("container-title") or [""])[0],
            "year": year,
            "authors": [f"{a.get('given', '')} {a.get('family', '')}".strip() for a in (msg.get("author") or [])][:8],
        }
    except urllib.error.HTTPError as exc:
        if exc.code != 404:
            return {"verified": False, "doi": clean, "error": str(exc)}
    except Exception as exc:  # noqa: BLE001
        return {"verified": False, "doi": clean, "error": str(exc)}

    handle_url = "https://doi.org/api/handles/" + urllib.parse.quote(clean, safe="/")
    handle_req = urllib.request.Request(handle_url, headers=headers)
    try:
        with urllib.request.urlopen(handle_req, timeout=timeout) as resp:
            handle_doc = json.loads(resp.read().decode("utf-8"))
        if int(handle_doc.get("responseCode", 0) or 0) == 1 and handle_doc.get("values"):
            return {
                "verified": True,
                "doi": clean,
                "title": "",
                "journal": "",
                "year": None,
                "authors": [],
                "resolver": "doi.org",
            }
        return {
            "verified": False,
            "doi": clean,
            "error": f"doi.org handle responseCode={handle_doc.get('responseCode')}",
        }
    except Exception as exc:  # noqa: BLE001
        return {"verified": False, "doi": clean, "error": str(exc)}


def _ffmpeg() -> str:
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    import imageio_ffmpeg  # type: ignore

    return imageio_ffmpeg.get_ffmpeg_exe()


def _score_archival_youtube_entry(entry: dict[str, Any]) -> int:
    title = str(entry.get("title") or "")
    channel = str(entry.get("channel") or "")
    dur = float(entry.get("duration_sec") or 0.0)
    blob = f"{title} {channel}".lower()

    score = 0
    if _matches_reject_channel(channel):
        score -= 55
    for bad in _EXPLAINER_TITLE_MARKERS:
        if bad in title.lower():
            score -= 40
            break
    for good in (
        "archival",
        "archive",
        "original footage",
        "original experiment",
        "original film",
        "16mm",
        "clinical",
        "footage",
        "experiment",
        "192",
        "193",
        "194",
        "195",
        "196",
        "197",
    ):
        if good in blob:
            score += 18
    if 15.0 <= dur <= 480.0:
        score += 10
    elif dur > 1800.0:
        score -= 20
    return score


def search_youtube(query: str, limit: int = 10) -> list[dict[str, Any]]:
    """yt-dlp flat search ranked by archival/experiment footage suitability (`archival_score` descending)."""
    import yt_dlp  # type: ignore

    fetch_n = max(int(limit), min(25, int(limit) * 2))
    opts = {"quiet": True, "skip_download": True, "extract_flat": True, "no_warnings": True}
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(f"ytsearch{fetch_n}:{query}", download=False)
    out = []
    for e in (info or {}).get("entries") or []:
        row = {
            "title": e.get("title"),
            "url": e.get("url") if str(e.get("url", "")).startswith("http") else f"https://www.youtube.com/watch?v={e.get('id')}",
            "channel": e.get("channel") or e.get("uploader"),
            "duration_sec": e.get("duration"),
            "views": e.get("view_count"),
        }
        row["archival_score"] = _score_archival_youtube_entry(row)
        out.append(row)
    out.sort(key=lambda r: (int(r.get("archival_score") or 0), int(r.get("views") or 0)), reverse=True)
    return out[: int(limit)]


def analyze_reference_video(
    url: str,
    out_dir: Path,
    max_keyframes: int = 24,
    scene_threshold: float = 0.30,
    transcribe: bool = True,
    keep_video: bool = False,
    section: str | None = None,
) -> dict[str, Any]:
    """
    Downloads a reference video (<=480p) to /tmp, extracts scene-change keyframes (+ one contact sheet) into
    out_dir, optionally transcribes speech with faster-whisper, evaluates 4-Gate `reenactment_suitability`
    (writing back to `<dossier>/04_media_refs.json` when inside a dossier), and deletes the video unless keep_video.
    """
    import yt_dlp  # type: ignore

    section_bounds: tuple[int, int] | None = None
    if section is not None and str(section).strip() != "":
        section_bounds = _parse_section_bounds(section)
    elif section is not None:
        raise ValueError(f"Invalid empty section format: {section!r}")

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="aab_ref_"))
    try:
        opts: dict[str, Any] = {
            "quiet": True,
            "no_warnings": True,
            "format": "bv*[height<=480]+ba/b[height<=480]/b",
            "noprogress": True,
            "outtmpl": str(tmp / "ref.%(ext)s"),
            "merge_output_format": "mp4",
            "ffmpeg_location": _ffmpeg(),
        }
        if section_bounds is not None:
            from yt_dlp.utils import download_range_func  # type: ignore

            opts["download_ranges"] = download_range_func(None, [section_bounds])
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
        video_candidates = [
            p
            for p in sorted(tmp.glob("ref.*"))
            if p.is_file()
            and p.suffix.lower() in _VIDEO_FILE_EXTS
            and not p.name.lower().endswith(".part")
        ]
        video = video_candidates[0] if video_candidates else None
        if video is None:
            raise RuntimeError(f"download failed for {url}")
        ff = _ffmpeg()
        kf_dir = out_dir / "keyframes"
        kf_dir.mkdir(exist_ok=True)
        for stale_kf in kf_dir.glob("kf_*.jpg"):
            stale_kf.unlink(missing_ok=True)
        subprocess.run(
            [ff, "-nostdin", "-hide_banner", "-loglevel", "error", "-y", "-i", str(video),
             "-vf", f"select='gt(scene,{scene_threshold})',scale=480:-2,showinfo", "-vsync", "vfr",
             "-frames:v", str(max_keyframes), str(kf_dir / "kf_%03d.jpg")],
            check=False, capture_output=True, timeout=600, stdin=subprocess.DEVNULL,
        )
        if len(list(kf_dir.glob("kf_*.jpg"))) < 8:
            for partial_kf in kf_dir.glob("kf_*.jpg"):
                partial_kf.unlink(missing_ok=True)
            clip_dur = (
                float(section_bounds[1] - section_bounds[0])
                if section_bounds is not None
                else float((info or {}).get("duration") or 0.0)
            )
            fps_val = max(1.0 / 3.0, 9.0 / max(1.0, clip_dur)) if clip_dur > 0 else (1.0 / 3.0)
            subprocess.run(
                [ff, "-nostdin", "-hide_banner", "-loglevel", "error", "-y", "-i", str(video),
                 "-vf", f"fps={fps_val:.6f},scale=480:-2",
                 "-frames:v", str(max_keyframes), str(kf_dir / "kf_%03d.jpg")],
                check=False, capture_output=True, timeout=600, stdin=subprocess.DEVNULL,
            )
        frames = sorted(kf_dir.glob("kf_*.jpg"))
        sheet = out_dir / "contact_sheet.jpg"
        if frames:
            cols = 4
            rows = (len(frames) + cols - 1) // cols
            subprocess.run(
                [ff, "-nostdin", "-hide_banner", "-loglevel", "error", "-y", "-pattern_type", "glob", "-i", str(kf_dir / "kf_*.jpg"),
                 "-vf", f"scale=320:-2,tile={cols}x{rows}:padding=4", "-frames:v", "1", str(sheet)],
                check=False, capture_output=True, timeout=300, stdin=subprocess.DEVNULL,
            )
        transcript_path = None
        asr_error: str | None = None
        if transcribe:
            try:
                from faster_whisper import WhisperModel  # type: ignore

                model = WhisperModel("base.en", device="cpu", compute_type="int8")
                segs, _ = model.transcribe(str(video), vad_filter=True)
                lines = [f"[{s.start:7.2f}-{s.end:7.2f}] {s.text.strip()}" for s in segs]
                transcript_path = out_dir / "transcript.txt"
                transcript_path.write_text("\n".join(lines), encoding="utf-8")
            except Exception as exc:  # noqa: BLE001
                asr_error = str(exc)
                (out_dir / "transcript_error.txt").write_text(asr_error, encoding="utf-8")
        meta: dict[str, Any] = {
            "url": url,
            "title": (info or {}).get("title"),
            "channel": (info or {}).get("channel") or (info or {}).get("uploader"),
            "duration_sec": (info or {}).get("duration"),
            "section": section,
            "keyframes": [str(f.relative_to(out_dir)) for f in frames],
            "contact_sheet": str(sheet.relative_to(out_dir)) if sheet.exists() else None,
            "transcript": str(transcript_path.relative_to(out_dir)) if transcript_path else None,
            "analyzed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "usage": "analysis only - never reused in channel videos",
        }
        if asr_error is not None:
            meta["asr_error"] = asr_error

        suit_res = evaluate_media_reenactment_suitability(meta, analysis_dir=out_dir)
        meta["reenactment_suitability"] = suit_res["suitability"]
        meta["reenactment_suitability_reason"] = suit_res["reason"]
        if suit_res.get("recommended_section"):
            meta["recommended_section"] = suit_res["recommended_section"]

        (out_dir / "analysis.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")

        # Write back into `<dossier>/04_media_refs.json` when `out_dir` is `<dossier>/media/<media_id>`
        if out_dir.parent.name == "media" and (out_dir.parent.parent / "04_media_refs.json").exists():
            d_root = out_dir.parent.parent
            m_refs_path = d_root / "04_media_refs.json"
            try:
                m_doc = json.loads(m_refs_path.read_text(encoding="utf-8"))
                m_id = out_dir.name
                updated = False
                for m_item in m_doc.get("media") or []:
                    if isinstance(m_item, dict) and (
                        str(m_item.get("id") or "") == m_id or str(m_item.get("url") or "") == url
                    ):
                        m_item["reenactment_suitability"] = suit_res["suitability"]
                        m_item["reenactment_suitability_reason"] = suit_res["reason"]
                        if suit_res.get("recommended_section"):
                            m_item["recommended_section"] = suit_res["recommended_section"]
                        m_item.setdefault("analysis", {})
                        if isinstance(m_item["analysis"], dict):
                            m_item["analysis"]["local_dir"] = f"media/{m_id}"
                            m_item["analysis"]["keyframe_count"] = len(frames)
                        updated = True
                        break
                if updated:
                    m_refs_path.write_text(json.dumps(m_doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            except Exception:
                pass

        if keep_video:
            shutil.copy2(video, out_dir / video.name)
        return meta
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


__all__ = [
    "DOSSIERS_ROOT",
    "DOSSIER_FILES",
    "RESEARCH_CHECKLIST",
    "analyze_reference_video",
    "audit_dossier_media_suitability",
    "diorama_seed_from_dossier",
    "dossier_dir",
    "evaluate_media_reenactment_suitability",
    "init_dossier",
    "load_dossier",
    "normalize_scene_prop",
    "plan_seed_from_dossier",
    "resolve_dossier_for_project",
    "search_youtube",
    "seed_diorama_visual_plan",
    "slugify",
    "validate_dossier",
    "verify_doi",
]
