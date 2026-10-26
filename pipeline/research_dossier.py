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
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pipeline.anatomy_map import resolve_region
from pipeline.config import RESEARCH_DOSSIERS_DIRNAME, VISUAL_MODES

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
DOSSIERS_ROOT = WORKSPACE_ROOT / "BCI_Shorts_Channel" / RESEARCH_DOSSIERS_DIRNAME

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


def resolve_dossier_for_project(project_id_or_dir: str | Path, root: Path | None = None) -> Path | None:
    """Resolve the research dossier directory for a project ID or project directory (supports legacy slug aliases via linked_projects)."""
    raw = Path(str(project_id_or_dir)).name if isinstance(project_id_or_dir, Path) or "/" in str(project_id_or_dir) else str(project_id_or_dir)
    pid = raw.strip()
    if not pid:
        return None
    base = Path(root) if root is not None else DOSSIERS_ROOT
    if not base.is_dir():
        return None
    for cand_slug in (slugify(pid), slugify(re.sub(r"^psych_\d+_", "", pid, flags=re.IGNORECASE))):
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
        for lp in meta.get("linked_projects") or []:
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
    if isinstance(v, (list, dict, str)):
        return len(v) > 0
    return True


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
    sources = (ds.get("01_sources.json") or {}).get("sources") or []
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
        if isinstance(s, dict) and s.get("type") not in SOURCE_TYPES:
            issues.append(f"source {s.get('id')}: unknown type '{s.get('type')}'")
    primary_ok = any(
        isinstance(s, dict)
        and s.get("type") in ("primary", "primary_historical")
        and s.get("verified")
        and (s.get("doi") or (s.get("type") == "primary_historical" and s.get("url")))
        for s in sources
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
        "follow_up": any(t in ("replication", "follow_up", "review") for t in stypes),
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
    return {"dir": ds["_dir"], "ready": all(checklist.values()) and not any("invalid JSON" in i for i in issues),
            "checklist": checklist, "issues": issues}


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
    srcs = [s for s in sources if isinstance(s, dict)]
    src_ids = {str(s.get("id")) for s in srcs if s.get("id")}
    if len(srcs) < DOSSIER_MIN_SOURCES:
        issues.append(f"{len(srcs)} sources < {DOSSIER_MIN_SOURCES}")
    fu = sum(1 for s in srcs if s.get("type") in ("replication", "follow_up", "review"))
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
        if kf_dir.exists() and len(list(kf_dir.glob("*.jpg"))) >= DOSSIER_MIN_KEYFRAMES:
            analysed += 1
    if analysed < DOSSIER_MIN_ANALYZED_MEDIA:
        issues.append(
            f"{analysed} media analysed on disk (media/<id>/keyframes >= {DOSSIER_MIN_KEYFRAMES}) < {DOSSIER_MIN_ANALYZED_MEDIA}: "
            "run `dossier yt-analyze` on the original footage"
        )
    iconic = [s for s in scenes if isinstance(s, dict) and s.get("iconic")]
    if iconic:
        ic = iconic[0]
        lay = ic.get("layout") if isinstance(ic.get("layout"), dict) else {}
        pos = [p for p in (lay.get("positions") or []) if isinstance(p, dict) and p.get("who") and p.get("where")]
        if len(pos) < DOSSIER_MIN_ICONIC_POSITIONS:
            issues.append(f"iconic layout.positions {len(pos)} < {DOSSIER_MIN_ICONIC_POSITIONS} (who / where / facing)")
        props = [p for p in (ic.get("props") or []) if isinstance(p, dict) and p.get("period_detail") and p.get("physical_behavior")]
        if len(props) < DOSSIER_MIN_ICONIC_PROPS:
            issues.append(f"iconic props with period_detail + physical_behavior {len(props)} < {DOSSIER_MIN_ICONIC_PROPS}")
        kv = ic.get("key_visual")
        if not (isinstance(kv, dict) and kv.get("description") and kv.get("must_show")):
            issues.append("iconic scene has no key_visual {description, must_show}: the money shot viewers remember (R46-K)")
        for f in ("wardrobe", "lighting", "sources"):
            if not _nonempty(ic.get(f)):
                issues.append(f"iconic scene: {f} is empty")
    return {"passed": not issues, "issues": issues}


def check_narration_facts(slug_or_dir: str | Path, narrations: list[str], root: Path | None = None) -> list[str]:
    """Every number shown in the subtitles must appear somewhere in the dossier (facts, story, sources)."""
    from pipeline.plain_language import to_display_text

    ds = load_dossier(slug_or_dir, root)
    corpus = json.dumps(
        [ds.get("dossier.json"), ds.get("01_sources.json"), ds.get("03_visual_reference.json"), ds.get("04_media_refs.json")],
        ensure_ascii=False,
    ) + " " + str(ds.get("02_master_story.md") or "")
    corpus_digits = set(re.findall(r"\d+(?:\.\d+)?", corpus.replace(",", "")))
    issues = []
    for i, line in enumerate(narrations, 1):
        for num in re.findall(r"\d+(?:\.\d+)?", to_display_text(str(line)).replace(",", "")):
            if num not in corpus_digits:
                issues.append(f"[fact] clip {i}: number {num} is not found anywhere in the dossier (add it with a source id)")
    return issues


# ------------------------------------------------------------------------------
# Dossier -> v5 visual_plan seed
# ------------------------------------------------------------------------------
def plan_seed_from_dossier(slug_or_dir: str | Path, root: Path | None = None) -> dict[str, Any]:
    """Draft v5 visual_plan fields (mode, must_have_scenes, cast hints, brain_link) for bci-script-gen to finish."""
    ds = load_dossier(slug_or_dir, root)
    meta = ds.get("dossier.json") or {}
    scenes = (ds.get("03_visual_reference.json") or {}).get("scenes") or []
    links = (ds.get("06_brain_link.json") or {}).get("links") or []
    must = [
        {
            "id": s.get("id"),
            "title": s.get("title"),
            "iconic": bool(s.get("iconic")),
            "recognition_hook": s.get("recognition_hook"),
            "era": s.get("era"),
            **({"key_visual": dict(s["key_visual"])} if isinstance(s.get("key_visual"), dict) else {}),
        }
        for s in sorted(scenes, key=lambda s: (not s.get("iconic"), s.get("shorts_priority", 99)))
        if isinstance(s, dict) and s.get("shorts_priority", 1) is not None and int(s.get("shorts_priority", 1) or 1) <= 3
    ]
    return {
        "schema": 5,
        "visual_mode": str(meta.get("visual_mode") or "HYBRID").upper(),
        "dossier": slugify(meta.get("slug") or Path(ds["_dir"]).name),
        "must_have_scenes": must,
        "brain_link": {str(l.get("role") or l.get("scene_id") or i): l for i, l in enumerate(links) if isinstance(l, dict)},
        "shots": {},
        "scenes": {},
    }


# ------------------------------------------------------------------------------
# Free reference tools
# ------------------------------------------------------------------------------
def verify_doi(doi: str, timeout: float = 10.0) -> dict[str, Any]:
    """Crossref lookup (free, no key). Returns {'verified', 'title', 'journal', 'year', 'authors'}."""
    clean = re.sub(r"^https?://(dx\.)?doi\.org/", "", str(doi or "").strip(), flags=re.IGNORECASE)
    if not clean:
        return {"verified": False, "error": "empty DOI"}
    url = "https://api.crossref.org/works/" + urllib.parse.quote(clean, safe="/")
    req = urllib.request.Request(url, headers={"User-Agent": "AllAboutBrain-Research/1.0 (mailto:kbforuni@gmail.com)"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            msg = json.loads(resp.read().decode("utf-8")).get("message", {})
    except Exception as exc:  # noqa: BLE001
        return {"verified": False, "doi": clean, "error": str(exc)}
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


def _ffmpeg() -> str:
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    import imageio_ffmpeg  # type: ignore

    return imageio_ffmpeg.get_ffmpeg_exe()


def search_youtube(query: str, limit: int = 10) -> list[dict[str, Any]]:
    """yt-dlp flat search: title, url, channel, duration, views (no download)."""
    import yt_dlp  # type: ignore

    opts = {"quiet": True, "skip_download": True, "extract_flat": True, "no_warnings": True}
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(f"ytsearch{int(limit)}:{query}", download=False)
    out = []
    for e in (info or {}).get("entries") or []:
        out.append(
            {
                "title": e.get("title"),
                "url": e.get("url") if str(e.get("url", "")).startswith("http") else f"https://www.youtube.com/watch?v={e.get('id')}",
                "channel": e.get("channel") or e.get("uploader"),
                "duration_sec": e.get("duration"),
                "views": e.get("view_count"),
            }
        )
    return out


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
    out_dir, optionally transcribes speech with faster-whisper, and deletes the video unless keep_video.
    section: optional "*00:30-01:10" yt-dlp download-section to analyse only the iconic moment.
    The keyframes are for the agent to read blocking / props / actions; they are never used in videos.
    """
    import yt_dlp  # type: ignore

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="aab_ref_"))
    opts: dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "format": "bv*[height<=480]+ba/b[height<=480]/b",
        "noprogress": True,
        "outtmpl": str(tmp / "ref.%(ext)s"),
        "merge_output_format": "mp4",
        "ffmpeg_location": _ffmpeg(),
    }
    if section:
        from yt_dlp.utils import download_range_func  # type: ignore

        m = re.match(r"\*?(\d+):(\d+)-(\d+):(\d+)", section)
        if m:
            a = int(m.group(1)) * 60 + int(m.group(2))
            b = int(m.group(3)) * 60 + int(m.group(4))
            opts["download_ranges"] = download_range_func(None, [(a, b)])
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
    video = next(iter(sorted(tmp.glob("ref.*"))), None)
    if video is None:
        raise RuntimeError(f"download failed for {url}")
    ff = _ffmpeg()
    kf_dir = out_dir / "keyframes"
    kf_dir.mkdir(exist_ok=True)
    subprocess.run(
        [ff, "-nostdin", "-hide_banner", "-loglevel", "error", "-y", "-i", str(video),
         "-vf", f"select='gt(scene,{scene_threshold})',scale=480:-2,showinfo", "-vsync", "vfr",
         "-frames:v", str(max_keyframes), str(kf_dir / "kf_%03d.jpg")],
        check=False, capture_output=True, timeout=600, stdin=subprocess.DEVNULL,
    )
    if len(list(kf_dir.glob("kf_*.jpg"))) < 8:  # static footage: fall back to a frame every 3 seconds
        subprocess.run(
            [ff, "-nostdin", "-hide_banner", "-loglevel", "error", "-y", "-i", str(video), "-vf", "fps=1/3,scale=480:-2",
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
    if transcribe:
        try:
            from faster_whisper import WhisperModel  # type: ignore

            model = WhisperModel("base.en", device="cpu", compute_type="int8")
            segs, _ = model.transcribe(str(video), vad_filter=True)
            lines = [f"[{s.start:7.2f}-{s.end:7.2f}] {s.text.strip()}" for s in segs]
            transcript_path = out_dir / "transcript.txt"
            transcript_path.write_text("\n".join(lines), encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            (out_dir / "transcript_error.txt").write_text(str(exc), encoding="utf-8")
    meta = {
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
    (out_dir / "analysis.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    if keep_video:
        shutil.copy2(video, out_dir / video.name)
    shutil.rmtree(tmp, ignore_errors=True)
    return meta


__all__ = [
    "DOSSIERS_ROOT",
    "DOSSIER_FILES",
    "RESEARCH_CHECKLIST",
    "analyze_reference_video",
    "dossier_dir",
    "init_dossier",
    "load_dossier",
    "plan_seed_from_dossier",
    "resolve_dossier_for_project",
    "search_youtube",
    "slugify",
    "validate_dossier",
    "verify_doi",
]
