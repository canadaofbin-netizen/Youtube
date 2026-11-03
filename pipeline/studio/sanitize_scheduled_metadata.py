"""
ALL ABOUT BRAIN — Lossless Scheduled Studio Metadata Sanitizer
---------------------------------------------------------------
Sanitizes description boilerplate and rotating editorial copy on NOT-YET-PUBLIC
scheduled Shorts (`diorama_12..26` or any `visibility == "scheduled"` project)
WITHOUT re-uploading or deleting any YouTube video (`R34` lossless metadata-only update).

Never mutates already-Public (`published_public`) videos unless `--include-public` is explicitly passed.
"""

from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pipeline.config import (
    AI_DISCLOSURE_SENTENCE,
    DESCRIPTION_EDITORIAL_TEMPLATES,
    PROJECTS_DIR,
)
from pipeline.studio.config import CHANNEL_ID, DEFAULT_CDP_PORT, RELATED_VIDEO_SELECTORS
from pipeline.studio.short_linker import is_valid_youtube_video_id, normalize_visibility
from pipeline.studio.whale_session import _DEEP_QUERY_HELPER_JS, WhaleSessionController


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _extract_dossier_editorial_summary(project_id: str, script: dict[str, Any]) -> tuple[str, str]:
    """Builds an independent editorial summary + DOI from the research dossier (never copying script sentences)."""
    from pipeline.config import DOSSIERS_DIR
    from pipeline.studio.community import _find_matching_dossier_dir

    slug = str(script.get("dossier") or "").strip()
    d_dir = (Path(DOSSIERS_DIR) / slug) if (slug and (Path(DOSSIERS_DIR) / slug).is_dir()) else _find_matching_dossier_dir(project_id)
    if d_dir is None or not d_dir.is_dir():
        return "", ""

    sources_doc = _load_json(d_dir / "01_sources.json")
    facts_doc = _load_json(d_dir / "02_facts.json")
    brain_path = (d_dir / "06_brain_link.json") if (d_dir / "06_brain_link.json").exists() else (d_dir / "06_brain_links.json")
    brain_doc = _load_json(brain_path)
    dossier_meta = _load_json(d_dir / "dossier.json")

    def _strip_md(val: str) -> str:
        cleaned = re.sub(r"\*\*([^*]+)\*\*", r"\1", str(val or ""))
        cleaned = re.sub(r"\*([^*]+)\*", r"\1", cleaned)
        return " ".join(cleaned.split()).strip()

    src_list = sources_doc.get("primary_sources") or sources_doc.get("sources") or []
    primary = src_list[0] if (isinstance(src_list, list) and src_list and isinstance(src_list[0], dict)) else {}
    doi = str(primary.get("doi") or "").strip()
    raw_cit = _strip_md(str(primary.get("citation") or ""))
    cit_author = raw_cit.split("(")[0].strip().rstrip(",") if "(" in raw_cit else ""
    pc = dossier_meta.get("primary_case") if isinstance(dossier_meta.get("primary_case"), dict) else {}
    pc_people = [str(p.get("name")).strip() for p in (pc.get("people") or []) if isinstance(p, dict) and str(p.get("name") or "").strip()]
    author = (
        str(primary.get("authors") or "").split(",")[0].split(";")[0].strip()
        or cit_author
        or (pc_people[0] if pc_people else "peer-reviewed investigators")
    )
    year = str(primary.get("year") or pc.get("year") or "").strip()
    cit_journal = ""
    if raw_cit:
        cit_parts = [seg.strip() for seg in raw_cit.rstrip(".").split(".") if seg.strip()]
        if len(cit_parts) >= 3:
            cit_journal = cit_parts[-1]
    journal = _strip_md(str(primary.get("journal") or primary.get("venue") or cit_journal or pc.get("place") or "neuroscience literature"))

    claims: list[str] = []
    for item in list(dossier_meta.get("core_facts") or []) + list(facts_doc.get("facts") or []):
        if isinstance(item, dict):
            cl = _strip_md(str(item.get("fact") or item.get("claim") or item.get("plain_claim") or item.get("summary") or "")).rstrip(".")
            if cl and cl not in claims:
                claims.append(cl)
        if len(claims) >= 2:
            break

    region_names: list[str] = []
    for reg in (brain_doc.get("links") or brain_doc.get("regions") or [])[:3]:
        if isinstance(reg, dict):
            rn = _strip_md(str(reg.get("region") or reg.get("canonical_region") or reg.get("name") or ""))
            if rn and rn not in region_names:
                region_names.append(rn)

    topic_lbl = _strip_md(str(dossier_meta.get("topic") or dossier_meta.get("title") or d_dir.name.replace("_", " ")))
    yr_str = f" ({year})" if year else ""
    parts = [f"Grounded in {author}{yr_str} ({journal}) on {topic_lbl}."]
    if claims:
        c0 = claims[0][0].lower() + claims[0][1:] if len(claims[0]) > 1 and claims[0][:2].isalpha() and not claims[0][:2].isupper() else claims[0]
        parts.append(f"Laboratory measurements demonstrate that {c0}.")
    if region_names:
        parts.append(f"Circuit analysis traces signaling across {', '.join(region_names)}.")
    elif len(claims) > 1:
        parts.append(f"{claims[1]}.")
    return " ".join(parts), doi


def diversify_clone_title(title: str, *, index_seed: int = 0) -> str:
    """
    Rewrites repetitive `'You Think <A>, Yet <B>'` clone titles across the 5 canonical `R60` US High-CTR
    archetypes (`<= TITLE_MAX_CHARS_DIORAMA` chars) while capping any overlong title at word boundary.
    """
    from pipeline.config import TITLE_MAX_CHARS_DIORAMA

    clean = " ".join(str(title or "").split()).strip()
    m = re.match(r"^You\s+Think\s+(.+?),\s*(?:Yet|But)\s+(.+?)[.!?]?$", clean, flags=re.IGNORECASE)
    if not m:
        if len(clean) > TITLE_MAX_CHARS_DIORAMA:
            return clean[: TITLE_MAX_CHARS_DIORAMA].rsplit(" ", 1)[0].rstrip(",:;-")
        return clean

    clause_a = m.group(1).strip().rstrip(".!?")
    clause_b = m.group(2).strip().rstrip(".!?")
    cap_b = clause_b[0].upper() + clause_b[1:] if len(clause_b) > 1 else clause_b.upper()
    low_b = clause_b[0].lower() + clause_b[1:] if len(clause_b) > 1 else clause_b.lower()
    slot = int(index_seed) % 5

    candidates = {
        0: clean,
        1: f"Why {cap_b}?",
        2: f"What Happens When {cap_b}?",
        3: f"The Brain Paradox: {cap_b}",
        4: f"How {cap_b} ({clause_a[:22].strip()})" if len(cap_b) <= 36 else f"How {cap_b}",
    }
    chosen = candidates.get(slot, clean)
    if len(chosen) > TITLE_MAX_CHARS_DIORAMA:
        for alt in (f"Why {cap_b}?", f"How {cap_b}", f"Brain Paradox: {cap_b}", f"Why {low_b[:58].rsplit(' ', 1)[0]}?"):
            if 16 <= len(alt) <= TITLE_MAX_CHARS_DIORAMA:
                return alt
        return chosen[: TITLE_MAX_CHARS_DIORAMA].rsplit(" ", 1)[0].rstrip(",:;-")
    return chosen


def build_diversified_description(
    *,
    project_id: str,
    metadata: dict[str, Any],
    script: dict[str, Any],
    index_seed: int = 0,
) -> str:
    """
    Rebuilds a scheduled video's description using rotating editorial templates
    (`DESCRIPTION_EDITORIAL_TEMPLATES`) + dossier-backed academic summary + DOI + AI disclosure,
    eliminating script-copying and identical channel boilerplate across consecutive scheduled uploads.
    """
    existing_desc = str(metadata.get("description") or "").strip()
    title = str(metadata.get("title") or script.get("title") or project_id).strip()
    dossier_summary, dossier_doi = _extract_dossier_editorial_summary(project_id, script)
    doi = str(metadata.get("doi") or script.get("doi") or script.get("source_doi") or dossier_doi or "").strip()
    if not doi:
        m = re.search(r"(10\.\d{4,9}/[^\s\n\r]+)", existing_desc)
        if m:
            doi = m.group(1).strip().rstrip(".")
    doi_url = doi if doi.startswith("http") else (f"https://doi.org/{doi}" if doi else "")

    if dossier_summary:
        lead_summary = dossier_summary
    else:
        sents: list[str] = []
        for s in script.get("sentences") or []:
            txt = str(s.get("text") if isinstance(s, dict) else s).strip()
            if txt:
                sents.append(txt)
            if len(sents) >= 3:
                break
        lead_summary = " ".join(sents[:2]).strip() or title

    raw_tags = metadata.get("hashtags") or ["#Shorts", "#Neuroscience", "#BrainScience", "#Psychology"]
    if isinstance(raw_tags, list):
        tag_list = [str(t).strip() for t in raw_tags if str(t).strip()]
    else:
        tag_list = [t.strip() for t in str(raw_tags).split() if t.strip()]

    from pipeline.publish import render_editorial_description

    return render_editorial_description(
        title=title,
        doi_or_url=doi_url or doi,
        source_summary=lead_summary,
        hashtags=tag_list[:5],
        seed=index_seed,
    )


def sanitize_scheduled_projects(
    *,
    projects_dir: Path | None = None,
    project_ids: list[str] | None = None,
    dry_run: bool = True,
    apply_studio_dom: bool = False,
    diversify_titles: bool = True,
    cdp_port: int = DEFAULT_CDP_PORT,
) -> dict[str, Any]:
    """
    Updates local `06_publish/metadata.json` (and optionally YouTube Studio `/video/<id>/edit`
    title & description textboxes via DirectCDPClient) on `scheduled` projects only.
    """
    p_root = projects_dir or PROJECTS_DIR
    candidates: list[Path] = []
    if project_ids:
        for pid in project_ids:
            if (p_root / pid).is_dir():
                candidates.append(p_root / pid)
    elif p_root.exists():
        candidates = sorted(p for p in p_root.iterdir() if p.is_dir())

    updated: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []

    for idx, p_dir in enumerate(candidates):
        pid = p_dir.name
        pub_dir = p_dir / "06_publish"
        upload_rec = _load_json(pub_dir / "upload_receipt.json")
        if not upload_rec:
            continue
        vis = normalize_visibility(upload_rec)
        if vis != "scheduled":
            skipped.append({"project_id": pid, "reason": f"visibility={vis} (only scheduled allowed)"})
            continue
        meta_path = pub_dir / "metadata.json"
        meta = _load_json(meta_path)
        script = _load_json(p_dir / "02_script" / "script.json")
        orig_title = str(meta.get("title") or script.get("title") or pid).strip()
        new_title = diversify_clone_title(orig_title, index_seed=idx) if diversify_titles else orig_title
        meta_for_desc = {**meta, "title": new_title}
        new_desc = build_diversified_description(
            project_id=pid,
            metadata=meta_for_desc,
            script=script,
            index_seed=idx,
        )
        vid = str(upload_rec.get("video_id") or "").strip()
        rec_entry: dict[str, Any] = {
            "project_id": pid,
            "video_id": vid,
            "old_title": orig_title,
            "new_title": new_title,
            "title_changed": new_title != orig_title,
            "template_index": idx % len(DESCRIPTION_EDITORIAL_TEMPLATES),
            "new_description_preview": new_desc[:140],
            "local_saved": False,
            "studio_saved": False,
        }
        if not dry_run and meta:
            meta["title"] = new_title
            meta["description"] = new_desc
            meta["sanitized_at_utc"] = datetime.now(timezone.utc).isoformat()
            meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
            rec_entry["local_saved"] = True

        if not dry_run and apply_studio_dom and is_valid_youtube_video_id(vid):
            rec_entry["studio_saved"] = asyncio.run(
                _push_description_to_studio(
                    video_id=vid,
                    description=new_desc,
                    title=new_title if new_title != orig_title else None,
                    cdp_port=cdp_port,
                )
            )
        updated.append(rec_entry)

    return {
        "dry_run": dry_run,
        "updated_count": len(updated),
        "skipped_count": len(skipped),
        "updated": updated,
        "skipped": skipped,
    }


async def _push_description_to_studio(
    *,
    video_id: str,
    description: str,
    cdp_port: int,
    title: str | None = None,
) -> bool:
    whale = WhaleSessionController(cdp_port=cdp_port)
    edit_url = f"https://studio.youtube.com/video/{video_id}/edit"
    async with whale.get_direct_client("studio.youtube.com", default_url=edit_url) as client:
        await client.send("Page.enable")
        await client.send("Runtime.enable")
        await client.send("Page.navigate", {"url": edit_url})
        ready = await client.wait_for_element(["ytcp-video-metadata-editor"], timeout_sec=20.0)
        if not ready:
            return False
        await asyncio.sleep(1.2)
        channel_ok = await client.eval(
            f"location.href.includes({json.dumps(CHANNEL_ID)}) || Boolean(document.querySelector('a[href*=\"{CHANNEL_ID}\"]'))"
        )
        if not channel_ok:
            return False
        set_ok = await client.eval(
            f"""(() => {{
                {_DEEP_QUERY_HELPER_JS}
                const newTitle = {json.dumps(title)};
                if (newTitle) {{
                    const titleBox = deepQueryAll('#title-textarea #textbox')[0]
                        || deepQueryAll('ytcp-video-title #textbox')[0];
                    if (titleBox) {{
                        titleBox.focus();
                        titleBox.textContent = newTitle;
                        titleBox.dispatchEvent(new InputEvent('input', {{ bubbles: true }}));
                        titleBox.dispatchEvent(new Event('change', {{ bubbles: true }}));
                    }}
                }}
                const descBox = deepQueryAll('#description-textarea #textbox')[0]
                    || deepQueryAll('ytcp-video-description #textbox')[0];
                if (!descBox) return false;
                descBox.focus();
                descBox.textContent = {json.dumps(description)};
                descBox.dispatchEvent(new InputEvent('input', {{ bubbles: true }}));
                descBox.dispatchEvent(new Event('change', {{ bubbles: true }}));
                return true;
            }})()"""
        )
        if not set_ok:
            return False
        await asyncio.sleep(0.6)
        clicked = await client.click(RELATED_VIDEO_SELECTORS["save_button"])
        if not clicked:
            return False
        await asyncio.sleep(2.5)
        return True
