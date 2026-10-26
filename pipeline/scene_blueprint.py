"""
ALL ABOUT BRAIN - Source-to-Prompt architecture (Rule R52).

How raw research turns into a generated clip, in one place:

    research dossier (text, YouTube / archive video, photos)            <- Gear 1 (R44)
        |  03_visual_reference.json  (era, layout positions, props, actions, reactions, wardrobe, lighting)
        |  04_media_refs.json        (timecoded shot notes + media/<id>/keyframes, contact sheet, transcript)
        |  01_sources.json / dossier.json core_facts (numbers with source ids)
        v
    scene_blueprint.json   build_scene_blueprints()                     <- this module
        every scene: camera, space, cast (who / where / facing / wardrobe), props (look + physical behaviour),
        beats (who / action / evidence), must_be_visible, must_not, timecode evidence, render span
        v
    reference frames       still_frame_prompt()  -> reference_image_qa (Q1..Q10 + semantic review)
        environment plate, one cast sheet per wardrobe key, hero prop, start frame (and end frame) per clip
        v
    generation packets     build_generation_packets()
        per clip: start frame (or "chain from previous clip's last frame"), optional end frame,
        timed-beat video prompt (0-3 s action, 3-6 s prop change, 6-8 s reaction), audio line by voice source,
        backend notes for Google Flow (Frames / Ingredients, 0-credit model) or the Gemini app (start image only)

Raw archival footage and real photos are NEVER uploaded to the generator: they show real people (the output drifts
to photoreal humans or trips safety filters) and they are third-party material. They are converted into text
(blueprint) and into our own porcelain reference frames, which are the only images the generator sees.
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any

from pipeline.config import (
    BRAIN_SETTINGS,
    CLIP_MAX_RENDER_SEC,
    DEFAULT_VOICE_SOURCE,
    FLOW_ASPECT_SHORTS,
    FLOW_MOTION_STYLE_V5,
    FLOW_VOICE_PROMPT_DESCRIPTOR_V5,
    FLOW_ACTIVE_VIDEO_MODEL,
    GENERATION_BACKENDS,
    GENERATION_PACKETS_DIRNAME,
    REF_IMAGES_DIRNAME,
    SCENE_BLUEPRINT_FILENAME,
    TIMED_BEAT_WINDOWS,
    VOICE_SOURCES,
    clip_roles,
)

MUST_NOT_DEFAULT: tuple[str, ...] = (
    "real human faces or skin (every person is a matte-white porcelain mannequin)",
    "on-screen text, captions, logos or watermarks",
    "modern objects outside the era",
)
_STOP = set(
    "the a an and or of to in on at for with from by as is are was were be been it its this that these those "
    "into onto over under then than while when where who whom which what very just only also both each every "
    "his her their them they he she we you your our out off up down left right center centre frame shot".split()
)


# ------------------------------------------------------------------------------
# Small text helpers
# ------------------------------------------------------------------------------
def _clean(text: Any) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _sentence(text: Any) -> str:
    t = _clean(text).rstrip(" ,;")
    if not t:
        return ""
    t = t[0].upper() + t[1:]
    return t if t.endswith((".", "!", "?")) else t + "."


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z][a-z\-]{3,}", text.lower()) if w not in _STOP}


def _first_clause(text: str) -> str:
    """'walks in from the right, stops dead center, faces the camera' -> 'walks in from the right'."""
    t = _clean(text)
    parts = re.split(r",\s+(?:and\s+|then\s+)?|\s+then\s+|;\s+", t)
    return parts[0] if parts else t


def _opening_still_action(text: str) -> str:
    """
    Preserves full opening action + prop/wardrobe participial clauses (e.g. ', gripping and tamping a long
    tapered iron bar...') for start-frame stills while stripping sequential beats ('then ...', 'until ...')
    and camera-movement verbs ('pushing in', 'pulling back', 'as the camera ...').
    """
    t = _clean(text)
    if not t:
        return ""
    # Strip multi-beat temporal continuations while keeping descriptive comma clauses
    t = re.split(r"(?:,\s*|\s+)(?:then|until|before|afterwards)\s+|;\s+", t, maxsplit=1, flags=re.I)[0]
    # Strip trailing camera motion clauses if embedded in action text
    t = re.sub(
        r",?\s*(?:as\s+the\s+camera|while\s+the\s+camera|pushing\s+in|pulling\s+back|zooming\s+in|zooming\s+out|panning\s+\w+|orbiting\s+\w+)\b.*$",
        "",
        t,
        flags=re.I,
    )
    # If comma separates two finite verb clauses ('walks in from the right, stops dead center'), stop before second finite verb
    m_seq = re.match(
        r"^([^,]+),\s+(?:stops|turns|walks|runs|slams|drops|falls|throws|collapses|exits|leaves|jumps)\b.*$",
        t,
        flags=re.I,
    )
    if m_seq:
        t = m_seq.group(1)
    return _clean(t).rstrip(" ,;")


def _last_clause(text: str) -> str:
    t = _clean(text)
    parts = [p for p in re.split(r",\s+(?:and\s+|then\s+)?|\s+then\s+|;\s+|,?\s+and\s+", t) if p.strip()]
    return parts[-1] if parts else t


def _parse_span_sec(t: str) -> float | None:
    m = re.match(r"\s*(\d+):(\d+)\s*[-–]\s*(\d+):(\d+)", str(t or ""))
    if not m:
        return None
    a = int(m.group(1)) * 60 + int(m.group(2))
    b = int(m.group(3)) * 60 + int(m.group(4))
    return float(b - a) if b > a else None


def still_prefix(aspect: str = FLOW_ASPECT_SHORTS) -> str:
    orient = "vertical" if aspect == "9:16" else "horizontal"
    return f"Generate a single {aspect} {orient} still photograph (one frozen instant, not a video):"


def video_prefix(aspect: str = FLOW_ASPECT_SHORTS, seconds: int = 8) -> str:
    orient = "vertical" if aspect == "9:16" else "horizontal"
    return f"Generate an {seconds}-second {aspect} {orient} video clip:"


# ------------------------------------------------------------------------------
# Cast lock (identical wording in every image and clip = the cheapest consistency win)
# ------------------------------------------------------------------------------
def cast_lock_entries(plan: dict[str, Any]) -> list[dict[str, str]]:
    cast = plan.get("cast") if isinstance(plan.get("cast"), dict) else {}
    wardrobe = cast.get("wardrobe") if isinstance(cast.get("wardrobe"), dict) else {}
    out: list[dict[str, str]] = []
    for key, look in wardrobe.items():
        if _clean(look):
            out.append({"id": str(key), "look": _clean(look)})
    if not out and _clean(cast.get("subject")):
        out.append({"id": "subject", "look": _clean(cast.get("subject"))})
    return out


def _scene_era(plan: dict[str, Any], scene_id: Any) -> str:
    for m in plan.get("must_have_scenes") or []:
        if isinstance(m, dict) and str(m.get("id")) == str(scene_id):
            return _clean(m.get("era"))
    return ""


def cast_for_shot(plan: dict[str, Any], role: str | None) -> list[dict[str, str]]:
    """
    Cast entries that belong in this shot: explicit shots[role].cast keys win; otherwise wardrobe keys whose
    words appear in the shot text, and era-variant keys (foreman_1848 / foreman_1850_chile) only when their year
    matches the scene era. Listing every costume in every prompt confused the generator (two foremen in clip 1).
    """
    entries = cast_lock_entries(plan)
    if not role:
        return entries
    shot = _shot(plan, role)
    if isinstance(shot.get("cast"), list) and shot["cast"]:
        keep = {str(k) for k in shot["cast"]}
        return [e for e in entries if e["id"] in keep] or entries[:1]
    text = " ".join(_clean(shot.get(k)) for k in ("camera", "environment", "action", "prop_change", "reaction")).lower()
    era = (_scene_era(plan, shot.get("scene_id")) + " " + text).lower()
    out = []
    for e in entries:
        parts = e["id"].lower().split("_")
        years = [x for x in parts if re.fullmatch(r"1[5-9]\d\d|20\d\d", x)]
        words = [x for x in parts if len(x) > 2 and not x.isdigit()]
        if words and any(re.search(rf"\b{re.escape(w)}", text) for w in words) and (not years or any(y in era for y in years)):
            out.append(e)
    return out or entries[:1]


def cast_lock_sentence(plan: dict[str, Any], max_entries: int = 4, role: str | None = None) -> str:
    entries = cast_for_shot(plan, role)[:max_entries]
    if not entries:
        return "Every person is an articulated matte-white porcelain mannequin."
    body = "; ".join(f"{e['id'].replace('_', ' ')} in {e['look']}" for e in entries)
    return f"Every person is an articulated matte-white porcelain mannequin, same design in every shot: {body}."


# ------------------------------------------------------------------------------
# Blueprint
# ------------------------------------------------------------------------------
def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None


def _scene_text(scene: dict[str, Any]) -> str:
    parts = [scene.get("title"), scene.get("recognition_hook")]
    for a in scene.get("actions") or []:
        parts.append(a.get("verb_sequence") if isinstance(a, dict) else a)
    lay = scene.get("layout")
    if isinstance(lay, dict):
        parts.append(lay.get("description"))
    return " ".join(_clean(p) for p in parts if p)


def _match_evidence(scene: dict[str, Any], media: list[dict[str, Any]], min_overlap: int = 4) -> list[dict[str, Any]]:
    ref_words = _words(_scene_text(scene))
    hits: list[dict[str, Any]] = []
    for m in media:
        if not isinstance(m, dict):
            continue
        for tc in m.get("timecodes") or []:
            if not isinstance(tc, dict):
                continue
            overlap = len(ref_words & _words(str(tc.get("what") or "")))
            if overlap >= min_overlap:
                hits.append(
                    {
                        "media_id": m.get("id"),
                        "t": tc.get("t"),
                        "what": _clean(tc.get("what"))[:400],
                        "overlap": overlap,
                        "span_sec": _parse_span_sec(str(tc.get("t") or "")),
                    }
                )
    hits.sort(key=lambda h: -h["overlap"])
    return hits[:6]


def _blueprint_for_scene(scene: dict[str, Any], media: list[dict[str, Any]], plan: dict[str, Any]) -> dict[str, Any]:
    lay = scene.get("layout") if isinstance(scene.get("layout"), dict) else {"description": scene.get("layout")}
    evidence = _match_evidence(scene, media)
    src_ids = [str(s) for s in (scene.get("sources") or [])]
    beats: list[dict[str, Any]] = []
    for a in scene.get("actions") or []:
        if isinstance(a, dict):
            beats.append({"who": a.get("who"), "action": _clean(a.get("verb_sequence") or a.get("action")), "kind": "action"})
        elif _clean(a):
            beats.append({"who": None, "action": _clean(a), "kind": "action"})
    for r in scene.get("reactions") or []:
        if isinstance(r, dict):
            beats.append({"who": r.get("who"), "action": _clean(r.get("reaction")), "kind": "reaction"})
        elif _clean(r):
            beats.append({"who": None, "action": _clean(r), "kind": "reaction"})
    for b in beats:
        b["evidence"] = [f"{e['media_id']}@{e['t']}" for e in evidence[:2]] + src_ids[:2]
    props = []
    for p in scene.get("props") or []:
        if isinstance(p, dict):
            props.append({"name": p.get("name"), "look": _clean(p.get("period_detail")), "behaviour": _clean(p.get("physical_behavior"))})
        elif _clean(p):
            props.append({"name": _clean(p), "look": "", "behaviour": ""})
    spans = [e["span_sec"] for e in evidence if e.get("span_sec")]
    from pipeline.config import CLIP_MAX_RENDER_SEC_WITH_REFERENCE

    render_span = max(spans) if spans else float(CLIP_MAX_RENDER_SEC_WITH_REFERENCE)
    must_visible = [p["name"] for p in props if p.get("name")][:4]
    for pos in (lay.get("positions") or [])[:4]:
        if isinstance(pos, dict) and pos.get("who"):
            must_visible.append(_clean(pos.get("who")).split("(")[0].strip())
    return {
        "scene_id": scene.get("id"),
        "title": scene.get("title"),
        "iconic": bool(scene.get("iconic")),
        "era": scene.get("era"),
        "space": _clean(lay.get("description")),
        "lighting": _clean(scene.get("lighting")),
        "wardrobe": scene.get("wardrobe"),
        "positions": [p for p in (lay.get("positions") or []) if isinstance(p, dict)],
        "props": props,
        "beats": beats,
        "recognition_hook": scene.get("recognition_hook"),
        "key_visual": scene.get("key_visual") or key_visual_for_scene(plan, scene.get("id")),
        "evidence": evidence,
        "sources": src_ids,
        "render_span_sec": render_span,
        "clips_needed": max(1, math.ceil(render_span / float(CLIP_MAX_RENDER_SEC_WITH_REFERENCE))),  # reference-conditioned clips = 8 s
        "must_be_visible": must_visible,
        "must_not": list(MUST_NOT_DEFAULT),
    }


def build_scene_blueprints(dossier_dir: Path, plan: dict[str, Any] | None = None) -> dict[str, Any]:
    d = Path(dossier_dir)
    plan = plan or {}
    scenes = (_load_json(d / "03_visual_reference.json") or {}).get("scenes") or []
    media = (_load_json(d / "04_media_refs.json") or {}).get("media") or []
    wanted = {str(m.get("id")) for m in (plan.get("must_have_scenes") or []) if isinstance(m, dict)}
    out = []
    for s in scenes:
        if not isinstance(s, dict):
            continue
        if wanted and str(s.get("id")) not in wanted and not s.get("iconic"):
            continue
        out.append(_blueprint_for_scene(s, media, plan))
    return {
        "schema_version": 1,
        "dossier": d.name,
        "visual_mode": plan.get("visual_mode"),
        "cast_lock": cast_lock_entries(plan),
        "clip_max_render_sec": CLIP_MAX_RENDER_SEC,
        "scenes": out,
    }


def validate_scene_blueprints(bp: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    scenes = bp.get("scenes") or []
    if not scenes:
        return ["[blueprint] no scenes: 03_visual_reference.json has no must-have scenes"]
    iconic = [s for s in scenes if s.get("iconic")]
    if len(iconic) != 1:
        issues.append(f"[blueprint] exactly one iconic scene required (got {len(iconic)})")
    if not bp.get("cast_lock"):
        issues.append("[blueprint] visual_plan.cast.wardrobe is empty: no cast lock wording for consistency")
    for s in scenes:
        sid = s.get("scene_id")
        if not s.get("space"):
            issues.append(f"[blueprint] {sid}: layout description (space) is empty")
        if not s.get("beats"):
            issues.append(f"[blueprint] {sid}: no actions / reactions to stage")
        if not s.get("props"):
            issues.append(f"[blueprint] {sid}: no props")
        for b in s.get("beats") or []:
            if not b.get("evidence"):
                issues.append(f"[blueprint] {sid}: beat '{(b.get('action') or '')[:50]}' has no source or media timecode")
        if s.get("iconic") and not isinstance(s.get("key_visual"), dict):
            issues.append(
                f"[blueprint] {sid}: iconic scene has no key_visual (the money shot everyone remembers, "
                "e.g. the iron rod passing through the cranium) with must_show tokens (R46-K)"
            )
        if s.get("iconic") and not s.get("evidence"):
            issues.append(
                f"[blueprint] {sid}: iconic scene has no matching media timecode; analyse the original footage "
                "(dossier yt-analyze) and write timecoded shot notes in 04_media_refs.json"
            )
    return issues


# ------------------------------------------------------------------------------
# Reference frame prompts (stills) and clip packets
# ------------------------------------------------------------------------------
def _shot(plan: dict[str, Any], role: str) -> dict[str, Any]:
    shots = plan.get("shots") if isinstance(plan.get("shots"), dict) else {}
    s = shots.get(role)
    return s if isinstance(s, dict) else {}


def key_visual_for_scene(plan: dict[str, Any], scene_id: Any) -> dict[str, Any] | None:
    """The scene's money shot (R46-K) from visual_plan.must_have_scenes[*].key_visual."""
    for m in plan.get("must_have_scenes") or []:
        if isinstance(m, dict) and str(m.get("id")) == str(scene_id) and isinstance(m.get("key_visual"), dict):
            return m["key_visual"]
    return None


def key_visual_tokens_ok(text: str, key_visual: dict[str, Any]) -> list[str]:
    """Returns the must_show token groups missing from text. A group 'cranium|skull' passes on either word."""
    low = str(text or "").lower()
    missing = []
    for group in key_visual.get("must_show") or []:
        alts = [a.strip().lower() for a in str(group).split("|") if a.strip()]
        if alts and not any(re.search(rf"\b{re.escape(a)}", low) for a in alts):
            missing.append(str(group))
    return missing


def key_visual_clip_numbers(plan: dict[str, Any], clips: list[dict[str, Any]]) -> dict[str, list[int]]:
    """scene_id -> clip numbers whose scene text actually shows the key visual."""
    out: dict[str, list[int]] = {}
    for m in plan.get("must_have_scenes") or []:
        if not (isinstance(m, dict) and isinstance(m.get("key_visual"), dict)):
            continue
        sid = str(m.get("id"))
        out[sid] = [
            int(c["clip_number"]) for c in clips
            if str(c.get("scene_id")) == sid and not key_visual_tokens_ok(str(c.get("scene") or ""), m["key_visual"])
        ]
    return out


def still_frame_prompt(plan: dict[str, Any], role: str, which: str = "start", aspect: str = FLOW_ASPECT_SHORTS,
                       fallback_scene: str = "") -> str:
    """
    Compositional still-frame prompt (R51 + R53 + R54):
    - Brain clips (`drill_down`, `brain_void`, `pull_out`) compose `BrainDepictionRule` (matte-white studio gallery
      brain cutaway + 4-colour subsurface glow + zero flying particles/sparks).
    - Reenactment clips (`real_env`) compose `SceneDepictionRule` + `CastDepictionRule` + ONE frozen instant.
    """
    from pipeline.depiction_rules import BrainDepictionRule, PromptComposer
    from pipeline.flow_prompt_builder import resolve_clip_setting

    shot = _shot(plan, role)
    setting = str(shot.get("setting") or resolve_clip_setting(plan, role))
    if setting in BRAIN_SETTINGS or not shot.get("action"):
        raw = re.sub(r"^[^.]*?(shot|orbit|tracking|dolly|push|pull)[^.]*\.\s*", "", _clean(fallback_scene), count=1, flags=re.I)
        if setting in BRAIN_SETTINGS:
            return _clean(PromptComposer.compose_brain_still_prompt(BrainDepictionRule.sanitize_brain_signal_text(raw), aspect=aspect))
        body = _sentence(raw)
        return _clean(f"{still_prefix(aspect)} {body} Razor-sharp focus, bright even light, no text, no watermark.")
    kv = key_visual_for_scene(plan, shot.get("scene_id")) if which == "key" else None
    if kv:
        instant, label = _clean(kv.get("description")), "key"
    elif which == "end":
        instant, label = _clean(shot.get("reaction")) or _last_clause(shot.get("action")), "final"
    else:
        instant, label = _opening_still_action(shot.get("action")), "opening"
    env_text = _clean(shot.get("environment"))
    if not env_text and _clean(shot.get("camera")):
        cam_loc = re.sub(
            r"^(?:wide|medium|close-up|smooth|dynamic|slow|macro|elevated|low-angle|lateral|over-the-shoulder|"
            r"establishing|tracking|orbiting|push-in|pull-back|rising|to|an|angle|shot|across|along|inside|on|in|over|"
            r"gliding|following|pan|from)\s+",
            "",
            _clean(shot.get("camera")),
            flags=re.I,
        )
        # Iteratively strip leading camera motion phrases up to a location preposition
        m_loc = re.search(r"\b(?:on|along|across|inside|in|over)\s+(an?\s+.+|the\s+.+)$", _clean(shot.get("camera")), flags=re.I)
        if m_loc:
            cam_loc = re.sub(r"\s+as\s+the\s+camera\b.*$", "", m_loc.group(1), flags=re.I).strip()
        if len(cam_loc.split()) >= 4:
            env_text = cam_loc
    parts = [
        still_prefix(aspect),
        _sentence(env_text or plan.get("real_environment")),
        cast_lock_sentence(plan, role=role),
        _sentence(f"Frozen {label} moment: {instant}"),
        "Razor-sharp focus, bright even documentary light, no real human faces, no text, no watermark.",
    ]
    return _clean(" ".join(p for p in parts if p))


def timed_video_prompt(plan: dict[str, Any], role: str, narration: str, voice_source: str = DEFAULT_VOICE_SOURCE,
                       aspect: str = FLOW_ASPECT_SHORTS, fallback_scene: str = "", has_start_image: bool = True) -> str:
    """
    Compositional timed video prompt (R52 + R53 + R54):
    - Brain clips compose `BrainDepictionRule` + `ReferenceDepictionRule.CONTINUITY_LOCK_BRAIN` (never mannequin acting
      suffixes, never flying particles/sparks).
    - Reenactment clips compose `CameraDepictionRule` + `SceneDepictionRule` + `CastDepictionRule` + timed 0-3s/3-6s/6-8s beats.
    """
    from pipeline.depiction_rules import BrainDepictionRule, ReferenceDepictionRule
    from pipeline.flow_prompt_builder import resolve_clip_setting

    shot = _shot(plan, role)
    setting = str(shot.get("setting") or resolve_clip_setting(plan, role))
    secs = 8 if has_start_image else CLIP_MAX_RENDER_SEC

    if setting in BRAIN_SETTINGS:
        brain_body = BrainDepictionRule.format_brain_scene(_clean(fallback_scene), append_restraint_lock=True)
        lock = ReferenceDepictionRule.CONTINUITY_LOCK_BRAIN if has_start_image else ""
        if voice_source == "native":
            audio = f'Voice: {FLOW_VOICE_PROMPT_DESCRIPTOR_V5}. Spoken narration: "{_clean(narration)}"'
        else:
            audio = "Audio: subtle room ambience only, no speech, no narration, no music."
        return _clean(f"{video_prefix(aspect, secs)} {brain_body} {lock} {audio}")

    if shot.get("action"):
        w = TIMED_BEAT_WINDOWS
        beats = [
            f"{w[0][0]}-{w[0][1]}s: {_clean(shot.get('action'))}.",
            f"{w[1][0]}-{w[1][1]}s: {_clean(shot.get('prop_change'))}." if shot.get("prop_change") else "",
            f"{w[2][0]}-{w[2][1]}s: {_clean(shot.get('reaction'))}." if shot.get("reaction") else "",
        ]
        body = " ".join(
            p for p in [_sentence(shot.get("camera")), _sentence(shot.get("environment")), cast_lock_sentence(plan, role=role), *beats] if p
        )
    else:
        body = _clean(fallback_scene)
    lock = (
        "Continue exactly from the provided start image: same mannequins, clothes, room, props and lighting."
        if has_start_image else ""
    )
    if voice_source == "native":
        audio = f'Voice: {FLOW_VOICE_PROMPT_DESCRIPTOR_V5}. Spoken narration: "{_clean(narration)}"'
    else:
        audio = "Audio: natural room ambience and prop sounds only, no speech, no narration, no music."
    return _clean(f"{video_prefix(aspect, secs)} {body} {lock} {FLOW_MOTION_STYLE_V5} {audio}")


def build_generation_packets(
    plan: dict[str, Any],
    narrations: list[str],
    backend: str = "gemini_app",
    voice_source: str = DEFAULT_VOICE_SOURCE,
    aspect: str = FLOW_ASPECT_SHORTS,
) -> list[dict[str, Any]]:
    if backend not in GENERATION_BACKENDS:
        raise ValueError(f"backend must be one of {GENERATION_BACKENDS}")
    if voice_source not in VOICE_SOURCES:
        raise ValueError(f"voice_source must be one of {VOICE_SOURCES}")
    from pipeline.flow_prompt_builder import build_flow_prompts

    lines = [str(n).strip() for n in narrations if str(n).strip()]
    built = build_flow_prompts(plan, lines, aspect=aspect)
    roles = clip_roles(len(lines))
    key_clips = {min(nums) for nums in key_visual_clip_numbers(plan, built).values() if nums}
    packets: list[dict[str, Any]] = []
    prev: dict[str, Any] | None = None
    for c, role in zip(built, roles):
        n = int(c["clip_number"])
        setting = str(c.get("setting") or "real_env")
        scene_id = c.get("scene_id")
        chain = bool(
            prev is not None and scene_id and prev.get("scene_id") == scene_id
            and setting not in BRAIN_SETTINGS and prev.get("setting") not in BRAIN_SETTINGS
        )
        start_file = f"{REF_IMAGES_DIRNAME}/ref_clip_{n:02d}.png"
        packet = {
            "clip_number": n,
            "role": role,
            "setting": setting,
            "scene_id": scene_id,
            "backend": backend,
            "voice_source": voice_source,
            "render_sec": render_ceiling_sec(backend, has_reference=True),
            "start_frame": {
                "mode": "chain_previous_last_frame" if chain else "reference_image",
                "file": f"{REF_IMAGES_DIRNAME}/chain_clip_{n:02d}_start.png" if chain else start_file,
                "prompt": None if chain else still_frame_prompt(plan, role, "start", aspect, c.get("scene", "")),
            },
            "end_frame": (
                {"file": f"{REF_IMAGES_DIRNAME}/ref_clip_{n:02d}_end.png",
                 "prompt": still_frame_prompt(plan, role, "end", aspect, c.get("scene", ""))}
                if backend == "flow" and setting not in BRAIN_SETTINGS and _shot(plan, role).get("action") else None
            ),
            "video_prompt": timed_video_prompt(plan, role, c["spoken_narration"], voice_source, aspect, c.get("scene", "")),
            "narration": c["spoken_narration"],
            "backend_steps": _backend_steps(backend),
        }
        if n in key_clips:
            key_frame = {"file": f"{REF_IMAGES_DIRNAME}/ref_clip_{n:02d}_key.png",
                         "prompt": still_frame_prompt(plan, role, "key", aspect, c.get("scene", "")),
                         "must_show": (key_visual_for_scene(plan, scene_id) or {}).get("must_show")}
            packet["key_frame"] = key_frame
            if backend == "flow":
                packet["end_frame"] = {"file": key_frame["file"], "prompt": key_frame["prompt"]}
        packets.append(packet)
        prev = packet
    return packets


def render_ceiling_sec(backend: str, has_reference: bool = True) -> int:
    """Gemini app: 8 s. Flow Omni 1.1 Flash: 10 s, but locked to 8 s once a reference image is attached."""
    from pipeline.config import CLIP_MAX_RENDER_SEC_WITH_REFERENCE, GEMINI_APP_MAX_RENDER_SEC

    if backend != "flow":
        return GEMINI_APP_MAX_RENDER_SEC
    return CLIP_MAX_RENDER_SEC_WITH_REFERENCE if has_reference else CLIP_MAX_RENDER_SEC


def _backend_steps(backend: str) -> list[str]:
    if backend == "flow":
        return [
            "Clear every ingredient chip in the prompt box (stale / errored chips break generation).",
            f"Settings: Video -> Frames (start + end) or Ingredients -> 9:16 -> {FLOW_ACTIVE_VIDEO_MODEL} -> x1 "
            "(Omni locks 8s once a reference image is attached; 10s only without one).",
            "Abort if the settings pane shows any Veo model (Omni only).",
            "Upload start (and end) frame PNG, select it by file name, paste video_prompt, generate.",
        ]
    return [
        "Gemini app -> Video: attach the start-frame PNG (one image only), paste video_prompt, generate (8 s).",
        "Download the MP4 as clip_<n>.mp4 into 03_visuals/flow_native_clips/ (import-clips handles ordering).",
        "If the next clip chains from this one, run `main.py packets --project <id> --chain <n>` to cut its last frame.",
    ]


def extract_last_frame(mp4_path: Path, out_png: Path) -> bool:
    import cv2

    cap = cv2.VideoCapture(str(mp4_path))
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    frame = None
    for i in range(max(0, n - 3), n):
        cap.set(cv2.CAP_PROP_POS_FRAMES, i)
        ok, f = cap.read()
        if ok and f is not None:
            frame = f
    cap.release()
    if frame is None:
        return False
    out_png.parent.mkdir(parents=True, exist_ok=True)
    return bool(cv2.imwrite(str(out_png), frame))


def render_packet_markdown(p: dict[str, Any]) -> str:
    lines = [
        f"# Clip {p['clip_number']:02d} — {p['role']} ({p['setting']}, scene {p.get('scene_id')})",
        "",
        f"Backend: **{p['backend']}** · voice: **{p['voice_source']}** · render: {p['render_sec']} s",
        "",
        "## 1. Start frame",
        f"- mode: `{p['start_frame']['mode']}` → `{p['start_frame']['file']}`",
    ]
    if p["start_frame"].get("prompt"):
        lines += ["", "```text", p["start_frame"]["prompt"], "```"]
    if p.get("key_frame"):
        lines += ["", "## 1b. KEY FRAME (money shot - must appear in the clip)", f"`{p['key_frame']['file']}` · must show: {p['key_frame'].get('must_show')}",
                  "", "```text", p["key_frame"]["prompt"], "```"]
    if p.get("end_frame"):
        lines += ["", "## 2. End frame (Flow Frames mode)", f"`{p['end_frame']['file']}`", "", "```text", p["end_frame"]["prompt"], "```"]
    lines += ["", "## 3. Video prompt", "", "```text", p["video_prompt"], "```", "", "## 4. Narration (TTS / subtitles)", "", p["narration"], "", "## Steps"]
    lines += [f"{i}. {s}" for i, s in enumerate(p["backend_steps"], 1)]
    return "\n".join(lines) + "\n"


def write_project_blueprint_and_packets(
    project_dir: Path,
    dossier_dir: Path | None = None,
    backend: str = "gemini_app",
    voice_source: str = DEFAULT_VOICE_SOURCE,
) -> dict[str, Any]:
    from pipeline.flow_prompt_builder import load_visual_plan

    p_dir = Path(project_dir)
    plan = load_visual_plan(project_dir=p_dir)
    narrations = json.loads((p_dir / "02_script" / "script.json").read_text(encoding="utf-8"))["clip_narrations"]
    if dossier_dir is None and plan.get("dossier"):
        for cand in (p_dir.parent.parent / "research_dossiers" / str(plan["dossier"]),):
            if cand.exists():
                dossier_dir = cand
    if dossier_dir is None:
        from pipeline.research_dossier import resolve_dossier_for_project

        dossier_dir = resolve_dossier_for_project(str(plan.get("dossier") or p_dir.name), root=p_dir.parent.parent / "research_dossiers")
    vis = p_dir / "03_visuals"
    vis.mkdir(parents=True, exist_ok=True)
    bp: dict[str, Any] = {"scenes": []}
    issues: list[str] = []
    if dossier_dir and Path(dossier_dir).exists():
        bp = build_scene_blueprints(Path(dossier_dir), plan)
        issues = validate_scene_blueprints(bp)
        (vis / SCENE_BLUEPRINT_FILENAME).write_text(json.dumps(bp, indent=2, ensure_ascii=False), encoding="utf-8")
    else:
        issues.append("[blueprint] visual_plan.dossier is not linked to an existing research dossier")
    from pipeline.clip_qa_contract import compile_clip_qa_contract

    contract = compile_clip_qa_contract(p_dir, dossier_dir=dossier_dir, save=True)
    packets = build_generation_packets(plan, narrations, backend=backend, voice_source=voice_source)
    pk_dir = vis / GENERATION_PACKETS_DIRNAME
    pk_dir.mkdir(parents=True, exist_ok=True)
    for p in packets:
        (pk_dir / f"clip_{p['clip_number']:02d}.md").write_text(render_packet_markdown(p), encoding="utf-8")
    (pk_dir / "packets.json").write_text(json.dumps(packets, indent=2, ensure_ascii=False), encoding="utf-8")
    return {
        "blueprint_issues": issues,
        "scenes": len(bp.get("scenes") or []),
        "packets": len(packets),
        "qa_contract_clips": len(contract.get("clips") or []),
        "packets_dir": str(pk_dir),
        "chained_clips": [p["clip_number"] for p in packets if p["start_frame"]["mode"] != "reference_image"],
    }


__all__ = [
    "build_generation_packets",
    "build_scene_blueprints",
    "cast_lock_sentence",
    "extract_last_frame",
    "still_frame_prompt",
    "timed_video_prompt",
    "validate_scene_blueprints",
    "write_project_blueprint_and_packets",
]
