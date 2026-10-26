"""
ALL ABOUT BRAIN - Prompt System v5 production quality gate and audit scorer (R45-R49).

`validate_production_v5(plan, narrations, clips)` returns [] only when a project is ready for Gear 3:
  A. Visual mode + must-have iconic scenes (R45, R46)
  B. Action-Physics acting in every reenactment clip (R47)
  C. Brain clips: mode caps, canonical anatomy, narration <-> scene region link (R48)
  D. Plain-language script: readability, jargon cap, glossed anatomy, everyday hook, no robotic openers (R15)
  E. TTS-safe narration (R49) + v4 structural validators (R40-A/B, R26, R24, R2)

`score_project(project_dir)` produces the 0-100 audit row used by `main.py audit-prompts`; it works on
legacy v4 projects too (mode inferred), so the whole back catalogue can be ranked for re-authoring.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from pipeline.anatomy_map import find_regions, region_named_in, resolve_region
from pipeline.config import (
    BRAIN_SETTINGS,
    ICONIC_SCENE_MAX_CLIP,
    JARGON_TERMS_MAX,
    MAX_ANATOMY_TERMS_BY_MODE,
    MAX_BRAIN_CLIPS_BY_MODE,
    PROMPT_SCENE_WORDS_MAX_V5,
    READABILITY_CLIP_FK_MAX,
    READABILITY_SCRIPT_FK_MAX,
    SECOND_PERSON_CLIPS_MIN,
    VISUAL_MODES,
    clip_roles,
)
from pipeline.flow_prompt_builder import (
    is_v5_plan,
    plan_visual_mode,
    resolve_clip_setting,
    validate_flow_prompts,
    validate_narrations,
)
from pipeline.plain_language import analyze_script

# ------------------------------------------------------------------------------
# R47 Action-Physics vocabulary
# ------------------------------------------------------------------------------
STATIC_ONLY_PATTERNS: tuple[str, ...] = (
    r"\bstands? (?:nearby|beside (?:it|him|her)|still|quietly|by)\b",
    r"\bsits? (?:calmly|upright|still|quietly|at the center)\b",
    r"\bstares?(?: ahead)?\b",
    r"\b(?:is |are )?(?:talking|explaining|listening)\b",
    r"\bhold(?:s)? out\b",
    r"\bsmooth porcelain face\b",
    r"\bpleading gestures?\b",
    r"\bturns? (?:its|his|her) head (?:away|toward)\b",
)
# Concrete, physical verbs. Deliberately excludes reach / point / gesture / wave (the "robot arm" acting of v4).
ACTION_VERBS: tuple[str, ...] = (
    "presses", "press", "pushes", "pulls", "yanks", "flips", "slams", "grabs", "grips", "clutches", "drives", "rams",
    "hammers", "tamps", "strikes", "swings", "throws", "tosses", "catches", "passes", "bounces", "dribbles",
    "lunges", "staggers", "stumbles", "collapses", "recoils", "flinches", "jerks", "twists", "spins", "pounds",
    "thumps", "beats", "rings", "pours", "lifts", "hoists", "drops", "shoves", "sprints", "runs",
    "walks", "strides", "ducks", "trembles", "shakes", "slaps", "kicks", "punches", "hits", "taps",
    "cranks", "writes", "scribbles", "tears", "rips", "snatches", "leaps", "jumps", "climbs", "crawls", "drags",
    "carries", "hands", "eats", "bites", "licks", "drools", "salivates", "sniffs", "barks", "wags", "paces", "rocks",
    "hugs", "clings", "pats", "strokes", "shields", "covers", "slumps", "sags", "bolts", "jolts", "convulses",
    "writhes", "gasps", "winces", "cringes", "shrinks", "rolls", "kneels", "dashes", "fumbles", "squeezes",
    "lowers", "raises", "turns the dial", "twists the dial", "flicks", "wipes", "rubs", "clenches", "stamps",
    "hammering", "pressing", "pulling", "passing", "dribbling", "thumping", "pounding", "walking", "striding",
    "salivating", "drooling", "tamping", "trembling", "staggering",
)
# Visible physical change of an object (verbs / results, not nouns or lighting).
PROP_CHANGE_MARKERS: tuple[str, ...] = (
    "flashes", "flash", "flickers", "sparks", "spark flies", "bursts", "explodes", "blast", "shatters", "spills",
    "splashes", "drips", "drip", "clicks", "clacks", "snaps", "swings", "spins", "rattles", "bounces", "rolls",
    "slides", "tips over", "topples", "lights up", "light up", "needle jumps", "needle swings", "ticks", "rings",
    "buzzes", "chimes", "dings", "smoke", "dust", "debris", "flies", "arcs", "falls", "drops", "crumples",
    "tears", "fills", "overflows", "beads", "bubbles", "steam", "sways", "wobbles", "crackles", "scatters",
    "springs", "pops", "flips", "slams shut", "swings open", "dial turns", "fogs", "trickles", "vibrates",
    "sways", "rises in the tube", "collects", "cracks", "splinters", "skids", "clatters", "thuds",
)
_BRAIN_WORDS_RE = re.compile(r"\b(brain|cranium|cortex|cortical|neurons?|gyri|sulci|hippocamp\w*|amygdala|lobe)\b", re.IGNORECASE)
_CHARACTER_RE = re.compile(
    r"\b(mannequin|figure|figures|man|woman|boy|girl|child|dog|monkey|rat|pigeon|students?|teacher|learner|experimenter|"
    r"volunteer|subject|patient|foreman|worker|player|players|gorilla|doctor|surgeon|nurse|crowd|guard|prisoner)\b",
    re.IGNORECASE,
)


def _has_any(text: str, vocab: tuple[str, ...]) -> list[str]:
    low = text.lower()
    return [v for v in vocab if re.search(rf"(?<![a-z]){re.escape(v)}(?![a-z])", low)]


def check_action_physics(scene: str) -> list[str]:
    """Issues for a reenactment scene: static-only acting, no body verb, no prop physical change."""
    issues: list[str] = []
    if not _CHARACTER_RE.search(scene):
        return issues  # pure environment / object shot
    statics = [p for p in STATIC_ONLY_PATTERNS if re.search(p, scene, re.IGNORECASE)]
    verbs = _has_any(scene, ACTION_VERBS)
    props = _has_any(scene, PROP_CHANGE_MARKERS)
    if not verbs:
        issues.append("no concrete body-action verb (R47)")
    if not props:
        issues.append("no prop with a visible physical change (R47)")
    if statics and len(verbs) < 2:
        issues.append(f"static acting phrase(s) {[re.sub(r'[^a-z ]', '', s)[:24] for s in statics]} without enough action (R47)")
    return issues


def _region_field_issue(name: str, value: Any) -> str | None:
    """A colour-coded region field must resolve to one canonical region (optionally + a white-matter tract)."""
    text = str(value or "").strip()
    if not text:
        return None
    regions = find_regions(text)
    non_wm = [r for r in regions if r != "white matter"]
    if not regions or (len(non_wm) == 0 and "white matter" not in regions):
        return f"visual_plan.{name} '{text}' is not a canonical region (anatomy_map) (R48)"
    if len(non_wm) > (2 if "white matter" in regions else 1):
        return f"visual_plan.{name} '{text}' blends several regions {non_wm} into one invented structure (R48)"
    return None


def _clean_kv(kv: dict[str, Any]) -> str:
    return re.sub(r"\s+", " ", str(kv.get("description") or "")).strip()[:90]


# ------------------------------------------------------------------------------
# Main gate
# ------------------------------------------------------------------------------
def validate_production_v5(
    plan: dict[str, Any] | None,
    narrations: list[str],
    clips: list[dict[str, Any]],
) -> list[str]:
    issues: list[str] = []
    plan = plan or {}
    if not is_v5_plan(plan):
        return [f"visual_plan.visual_mode must be one of {list(VISUAL_MODES)} (R45)"]
    mode = plan_visual_mode(plan)
    lines = [str(n).strip() for n in narrations if str(n).strip()]
    try:
        roles = list(clip_roles(len(lines)))
    except ValueError as exc:
        return [str(exc)]

    # E. structural (v4 contract) ----------------------------------------------
    issues += [f"[narration] {x}" for x in validate_narrations(lines)]
    issues += [f"[prompt] {x}" for x in validate_flow_prompts(clips, scene_words_max=PROMPT_SCENE_WORDS_MAX_V5)]

    # A. must-have scenes ----------------------------------------------------------
    must = plan.get("must_have_scenes") if isinstance(plan.get("must_have_scenes"), list) else []
    must = [m for m in must if isinstance(m, dict) and m.get("id")]
    if not must:
        issues.append("[scene] visual_plan.must_have_scenes is empty: extract them from the dossier visual_reference (R46)")
    iconic = [m for m in must if m.get("iconic")]
    if must and len(iconic) != 1:
        issues.append(f"[scene] exactly one must_have_scene must be iconic=true (got {len(iconic)}) (R46)")
    clip_scene_ids = [str(c.get("scene_id") or "") for c in clips]
    for m in must:
        if str(m["id"]) not in clip_scene_ids:
            issues.append(f"[scene] must-have scene {m['id']} ('{m.get('title', '')}') is not shown in any clip (R46)")
    if iconic:
        iid = str(iconic[0]["id"])
        first = next((i + 1 for i, s in enumerate(clip_scene_ids) if s == iid), None)
        if first is None or first > ICONIC_SCENE_MAX_CLIP:
            issues.append(f"[scene] iconic scene {iid} must appear in clip 1-{ICONIC_SCENE_MAX_CLIP} (found in {first}) (R46)")

    # A2. key visual (money shot) -------------------------------------------------------
    # Mapping a scene id to a clip is not enough: the clip must actually SHOW the moment everybody remembers
    # (the rod through the cranium, the gorilla thumping its chest between the passers, ...).
    from pipeline.scene_blueprint import key_visual_clip_numbers, key_visual_tokens_ok

    if iconic and not isinstance(iconic[0].get("key_visual"), dict):
        issues.append(
            f"[keyshot] iconic scene {iconic[0]['id']} has no key_visual {{description, must_show}}: name the money shot "
            "from the dossier recognition_hook (R46-K)"
        )
    shown = key_visual_clip_numbers(plan, clips)
    for m in must:
        kv = m.get("key_visual")
        if not isinstance(kv, dict):
            continue
        sid = str(m["id"])
        if not shown.get(sid):
            sample = next((str(c.get("scene") or "") for c in clips if str(c.get("scene_id")) == sid), "")
            issues.append(
                f"[keyshot] scene {sid}: no clip shows the key visual '{_clean_kv(kv)}' "
                f"(missing {key_visual_tokens_ok(sample, kv)} in the shot action / prop_change / reaction) (R46-K)"
            )
        elif m.get("iconic") and min(shown[sid]) > ICONIC_SCENE_MAX_CLIP:
            issues.append(f"[keyshot] iconic key visual first shown in clip {min(shown[sid])} > {ICONIC_SCENE_MAX_CLIP} (R46-K)")

    # B/C. per clip ---------------------------------------------------------------
    brain_clips = 0
    for i, (role, clip) in enumerate(zip(roles, clips), start=1):
        scene = str(clip.get("scene") or "")
        setting = str(clip.get("setting") or resolve_clip_setting(plan, role))
        narr = lines[i - 1] if i - 1 < len(lines) else ""
        if setting in BRAIN_SETTINGS:
            brain_clips += 1
        if setting == "real_env":
            if mode == "BEHAVIORAL_PSYCH" and _BRAIN_WORDS_RE.search(scene):
                issues.append(f"[brain] clip {i} ({role}): BEHAVIORAL_PSYCH scenes never show the brain (R45)")
            for x in check_action_physics(scene):
                issues.append(f"[acting] clip {i} ({role}): {x}")
        else:
            from pipeline.depiction_rules import BrainDepictionRule

            if mode == "BEHAVIORAL_PSYCH":
                issues.append(f"[brain] clip {i} ({role}): setting '{setting}' not allowed in BEHAVIORAL_PSYCH (R45)")
            for sig_err in BrainDepictionRule.validate_restrained_signal(scene, setting):
                issues.append(f"[brain] clip {i} ({role}): {sig_err}")
            regions = [r for r in find_regions(scene) if r not in ("white matter", "retina", "optic nerve", "cochlea")]
            if setting in BRAIN_SETTINGS and not regions:
                issues.append(f"[brain] clip {i} ({role}): brain scene names no canonical region (R48)")
            unnamed = [r for r in regions if not region_named_in(r, narr)]
            if setting in BRAIN_SETTINGS and regions and len(unnamed) == len(regions):
                issues.append(
                    f"[brain] clip {i} ({role}): narration never names the on-screen region(s) {regions} "
                    "or their plain names; link the region to the story (R48)"
                )
    cap = MAX_BRAIN_CLIPS_BY_MODE[mode]
    if brain_clips > cap:
        issues.append(f"[brain] {brain_clips} brain clips exceed the {mode} cap of {cap} (R45)")
    for field in ("target_region", "crisis_region", "compensatory_region"):
        if mode != "BEHAVIORAL_PSYCH" and plan.get(field):
            x = _region_field_issue(field, plan.get(field))
            if x:
                issues.append(f"[brain] {x}")
    links = plan.get("brain_link") if isinstance(plan.get("brain_link"), dict) else {}
    for role_key, link in links.items():
        reg = (link or {}).get("region") if isinstance(link, dict) else None
        if reg and not resolve_region(str(reg)):
            issues.append(f"[brain] brain_link[{role_key}].region '{reg}' is not in anatomy_map (R48)")

    # D/E. language ----------------------------------------------------------------
    a = analyze_script(lines, roles)
    if a["script_fk_grade"] > READABILITY_SCRIPT_FK_MAX:
        issues.append(f"[plain] script reading grade {a['script_fk_grade']} > {READABILITY_SCRIPT_FK_MAX} (R15)")
    for c in a["clips"]:
        if c["fk_grade"] > READABILITY_CLIP_FK_MAX:
            issues.append(f"[plain] clip {c['clip']} reading grade {c['fk_grade']} > {READABILITY_CLIP_FK_MAX} (R15)")
        for t in c["tts_issues"]:
            issues.append(f"[tts] clip {c['clip']}: {t} (R49)")
        if c["robotic_opener"]:
            issues.append(f"[plain] clip {c['clip']}: robotic 'Step one/two/three' opener (R26)")
        if c["paper_voice"]:
            issues.append(f"[plain] clip {c['clip']}: paper-style phrasing (R15)")
    if len(a["jargon_terms"]) > JARGON_TERMS_MAX:
        issues.append(f"[plain] {len(a['jargon_terms'])} technical terms {a['jargon_terms']} > cap {JARGON_TERMS_MAX} (R15)")
    acap = MAX_ANATOMY_TERMS_BY_MODE[mode]
    if len(a["anatomy_terms"]) > acap:
        issues.append(f"[plain] {len(a['anatomy_terms'])} brain-region names {a['anatomy_terms']} > {mode} cap {acap} (R15)")
    for r in a["unglossed_anatomy_terms"]:
        issues.append(f"[plain] '{r}' is never explained in everyday words (plain name from anatomy_map) (R48)")
    if a["second_person_clips"] < SECOND_PERSON_CLIPS_MIN:
        issues.append("[plain] no clip connects the story to the viewer's own life ('you / your') (R15)")
    return issues


# ------------------------------------------------------------------------------
# Audit score sheet (works on v4 projects too)
# ------------------------------------------------------------------------------
_CATEGORY_WEIGHTS: dict[str, int] = {
    "scene": 25,    # must-have / iconic reenactment
    "acting": 20,   # action physics
    "brain": 15,    # mode fit + anatomy link
    "plain": 25,    # easy to follow
    "tts": 10,      # voice-safe text
    "structure": 5, # v4 contract
}


_LEGACY_MODE_HINTS: dict[str, tuple[str, ...]] = {
    "BEHAVIORAL_PSYCH": (
        "milgram", "asch", "zimbardo", "darley", "bystander", "mischel", "marshmallow", "rosenthal", "pygmalion",
        "kahneman", "loss_aversion", "dunning", "steele", "stereotype", "deci", "overjustification", "rosenhan",
        "bandura", "bobo", "wegner", "white_bear", "kross", "self_talk", "miller", "magical_number", "shepard",
        "mental_rotation", "inattentional", "gorilla", "loftus", "false_memory",
    ),
    "HYBRID": (
        "pavlov", "skinner", "harlow", "seligman", "schachter", "beck", "posner", "ekman", "libet", "baron_cohen",
        "baars", "csikszentmihalyi", "rizzolatti", "damasio", "ledoux", "greene", "trolley", "dissonance",
        "habit_loop", "emdr", "melzack", "pain_gate", "raichle", "default_mode", "dunbar",
    ),
    "NEURO_BIOLOGY": (
        "gage", "capgras", "patient_hm", "hippocampal", "prosthesis", "inner_speech", "split_brain", "glymphatic",
        "kanwisher", "fusiform", "ramachandran", "phantom", "olds_milner", "pleasure_center",
    ),
}


def _infer_mode(project_dir: Path, plan: dict[str, Any], narrations: list[str]) -> str:
    """Declared v5 mode, else a per-topic table for the legacy catalogue, else a keyword guess."""
    if is_v5_plan(plan):
        return str(plan_visual_mode(plan))
    pid = project_dir.name.lower()
    for mode in ("NEURO_BIOLOGY", "BEHAVIORAL_PSYCH", "HYBRID"):
        if any(k in pid for k in _LEGACY_MODE_HINTS[mode]):
            return mode
    text = (pid + " " + " ".join(narrations)).lower()
    neuro_kw = ("lesion", "surgery", "implant", "electrode", "prosthesis", "skull", "stroke", "callosum", "chip")
    if any(k in text for k in neuro_kw):
        return "NEURO_BIOLOGY"
    return "HYBRID"


def score_project(project_dir: Path) -> dict[str, Any]:
    """Audit row: inferred/declared mode, category issue counts, 0-100 score and the top issues."""
    project_dir = Path(project_dir)
    row: dict[str, Any] = {"project_id": project_dir.name}
    try:
        prompts_doc = json.loads((project_dir / "03_visuals" / "flow_all_in_one_prompts.json").read_text(encoding="utf-8"))
        clips = prompts_doc.get("clips") or []
    except Exception as exc:  # noqa: BLE001
        row.update({"score": 0, "error": f"no prompts file: {str(exc)[:60]}"})
        return row
    narrations: list[str] = []
    try:
        narrations = json.loads((project_dir / "02_script" / "script.json").read_text(encoding="utf-8"))["clip_narrations"]
    except Exception:  # noqa: BLE001
        narrations = [str(c.get("spoken_narration") or "") for c in clips]
        row["note"] = "script.json empty/missing; narration taken from prompts file"
    plan: dict[str, Any] = {}
    vp = project_dir / "03_visuals" / "visual_plan.json"
    if vp.exists():
        try:
            plan = json.loads(vp.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            plan = {}
    mode = _infer_mode(project_dir, plan, narrations)
    eval_plan = dict(plan)
    eval_plan["visual_mode"] = mode
    issues = validate_production_v5(eval_plan, narrations, clips)
    by_cat: dict[str, list[str]] = {k: [] for k in _CATEGORY_WEIGHTS}
    for x in issues:
        m = re.match(r"\[(\w+)\]", x)
        cat = (m.group(1) if m else "structure")
        cat = {"narration": "structure", "prompt": "structure"}.get(cat, cat)
        by_cat.setdefault(cat, []).append(x)
    score = 0.0
    n_clips = max(1, len(clips))
    for cat, weight in _CATEGORY_WEIGHTS.items():
        n = len(by_cat.get(cat, []))
        denom = {"scene": 2, "acting": n_clips, "brain": max(3, n_clips // 2), "plain": 6, "tts": 4, "structure": 4}[cat]
        score += weight * max(0.0, 1.0 - n / denom)
    a = analyze_script(narrations)
    brain_clips = sum(1 for c in clips if str(c.get("setting")) in BRAIN_SETTINGS)
    acting_fail = len({re.search(r"clip (\d+)", x).group(1) for x in by_cat.get("acting", []) if re.search(r"clip (\d+)", x)})
    row.update(
        {
            "mode": mode,
            "mode_declared": is_v5_plan(plan),
            "score": round(score, 1),
            "brain_clips": brain_clips,
            "brain_cap": MAX_BRAIN_CLIPS_BY_MODE[mode],
            "static_acting_clips": acting_fail,
            "fk_grade": a["script_fk_grade"],
            "jargon": a["jargon_terms"],
            "robotic_openers": a["robotic_openers"],
            "tts_issues": a["tts_issue_count"],
            "issue_counts": {k: len(v) for k, v in by_cat.items()},
            "top_issues": issues[:8],
        }
    )
    return row


def audit_projects(projects_root: Path) -> list[dict[str, Any]]:
    rows = [score_project(p) for p in sorted(Path(projects_root).iterdir()) if p.is_dir()]
    return sorted(rows, key=lambda r: r.get("score", 0))


def render_score_sheet_md(rows: list[dict[str, Any]]) -> str:
    out = [
        "# Prompt System v5 — Audit Score Sheet",
        "",
        "Lower score = higher re-authoring priority. Mode is inferred for legacy (v4) projects.",
        "",
        "| # | Project | Mode | Score | Brain clips / cap | Static-acting clips | Reading grade | Jargon | Step-openers | TTS issues |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for i, r in enumerate(rows, start=1):
        if r.get("error"):
            out.append(f"| {i} | {r['project_id']} | — | 0 | — | — | — | — | — | {r['error'][:40]} |")
            continue
        out.append(
            f"| {i} | {r['project_id']} | {r['mode']} | {r['score']} | {r['brain_clips']} / {r['brain_cap']} | "
            f"{r['static_acting_clips']} | {r['fk_grade']} | {', '.join(r['jargon'][:4]) or '—'} | "
            f"{r['robotic_openers']} | {r['tts_issues']} |"
        )
    return "\n".join(out) + "\n"
