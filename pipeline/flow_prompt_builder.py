"""
ALL ABOUT BRAIN - Canonical Google Flow Prompt Builder (Production Contract v4).

Single source of truth for every Google Flow (Gemini Omni 1.1) clip prompt:

    {FLOW_PROMPT_PREFIX} <scene 50-80 words> Voice: Puck. Spoken narration: "<line>"

- One clip = one narrative role (config.clip_roles) = one clean camera move.
- Context clips use a narration-matched photoreal environment with matte-white porcelain mannequins;
  brain clips use a realistic matte-white brain on a deep midnight navy void.
- 4-point colour code: crimson-red = crisis, electric cyan-blue = target region,
  warm amber-gold = active/compensatory circuit, bioluminescent green = signal transmission.
- The sanitizer is applied to template-generated scene text only, never to narration.
"""

from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any

from pipeline.config import (
    CLIP_COUNT_MAX,
    CLIP_COUNT_MIN,
    CLIP_WORDS_MAX,
    CLIP_WORDS_MIN,
    FLOW_DEFAULT_VOICE,
    FLOW_PROMPT_PREFIX,
    PROMPT_SCENE_WORDS_MAX,
    PROMPT_SCENE_WORDS_MIN,
    ROLE_SETTINGS,
    clip_roles,
    script_word_range,
)

SCHEMA_VERSION = 4
FLOW_PROMPTS_FILENAME = "flow_all_in_one_prompts.json"
VISUAL_PLAN_FILENAME = "visual_plan.json"

ROLE_CAMERA_MOVES: dict[str, str] = {
    "setup": "wide establishing shot, camera smoothly tracks forward toward the subject",
    "symptom": "close-up, slow orbit around the head revealing colour points through the cranium",
    "failure": "smooth lateral tracking between figures",
    "crisis": "dive through the frosted-glass cranium, glide over the gyri and sulci, zoom into the target",
    "pivot": "smooth orbit around the structures, push in on the compensatory route",
    "mechanism": "macro tracking along the signal path, then pull back to the full circuit",
    "step1": "macro tracking along the signal path",
    "step2": "macro tracking along the signal path",
    "step3": "macro tracking along the signal path, then pull back to the full circuit",
    "breakthrough": "pull out of the brain through the cranium into the real environment",
    "conclusion": "slow pull-back rising to an elevated wide shot",
}

COLOR_CODE: dict[str, str] = {
    "crisis": "crimson-red",
    "target": "electric cyan-blue",
    "active": "warm amber-gold",
    "signal": "bioluminescent green",
}

MEME_CRISIS_PATTERN = re.compile(r"\bthis (?:is|was) a total nightmare\b", re.IGNORECASE)
MEME_AWE_TEXT = "the researchers were left completely stunned"
CONCLUSION_OPENERS = ("Which proves", "Which is why")
PIVOT_MARKER = "instead of"

# Structural tokens are banned anywhere in the prompt (scene and narration).
_STRUCTURAL_BANNED_TOKENS: tuple[str, ...] = (
    "mobius",
    "möbius",
    "seamless loop",
    "loop back",
    "locked-off",
    "tripod",
    "5% push",
    "decoupled kinetic",
    "HUD",
    "telemetry",
    "mute-test",
    "ARRI",
    "Alexa",
    "all about brain",
    "watermark",
)
# Mechanical/toy prop tokens are banned in the visual scene. Narration is canonical script text
# (metaphors are allowed in the script) and is never rewritten, so props are only checked in the scene.
_PROP_BANNED_TOKENS: tuple[str, ...] = (
    "clockwork",
    "gear",
    "gears",
    "tape-reel",
    "tape recorder",
    "brass scale",
    "balance scale",
    "camera shutter",
    "coin",
    "coins",
    "dollar bill",
    "dollar bills",
)
BANNED_PROMPT_TOKENS: tuple[str, ...] = _STRUCTURAL_BANNED_TOKENS + _PROP_BANNED_TOKENS


def _token_regex(token: str) -> re.Pattern[str]:
    return re.compile(rf"(?<![0-9A-Za-zÀ-ÿ]){re.escape(token)}(?![0-9A-Za-zÀ-ÿ])", re.IGNORECASE)


_STRUCTURAL_REGEXES = [(t, _token_regex(t)) for t in _STRUCTURAL_BANNED_TOKENS]
_PROP_REGEXES = [(t, _token_regex(t)) for t in _PROP_BANNED_TOKENS]
_HEX_RE = re.compile(r"#[0-9A-Fa-f]{3,8}\b")
_AUDIO_RE = re.compile(r"\bAudio\s*:", re.IGNORECASE)
_CAMERA_ANGLE_RE = re.compile(r"\bCamera\s+Angle\b", re.IGNORECASE)
_PROMPT_RE = re.compile(
    r'^(?P<scene>.*?) Voice: (?P<voice>[A-Za-z]+)\. Spoken narration: "(?P<narration>[^"]*)"$',
    re.DOTALL,
)


# ==============================================================================
# Scene sanitizer (Contract §3): people-name filter + sensitive-term filter with an allow-list.
# Applied to scene text only. Narration is returned untouched.
# ==============================================================================
SANITIZER_ALLOW_LIST: tuple[str, ...] = (
    # environments and props
    "hospital", "hospital room", "hospital bed", "casino", "lab", "laboratory", "bed", "monitor",
    "EKG", "EKG monitor", "classroom", "courtroom", "clinic", "ward", "office", "kitchen", "prison",
    "prison cell", "cage", "interview room", "living room", "bedroom", "school", "street", "train",
    "operating room", "wheelchair", "telephone", "wall",
    # animals that are legitimate scene subjects
    "rat", "rats", "rabbit", "bull", "sea slug", "aplysia", "monkey", "dog",
    # anatomy
    "amygdala", "fusiform", "fusiform face area", "hippocampus", "prefrontal", "prefrontal cortex",
    "temporal lobe", "white-matter", "white matter", "Broca's area", "Wernicke's area", "thalamus",
    "insula", "striatum", "basal ganglia", "cingulate", "corpus callosum", "cerebellum", "brainstem",
    "occipital cortex", "motor cortex", "somatosensory cortex",
    # crisis wording required by the spec
    "severed", "sever", "severing",
)

# Multi-word, case-sensitive person names only (Contract §3). Single surnames are never rewritten.
_PERSON_NAMES: dict[str, str] = {
    "Patient H.M.": "an amnesic patient",
    "Patient HM": "an amnesic patient",
    "Henry Molaison": "an amnesic patient",
    "Phineas Gage": "a railroad foreman",
    "Clive Wearing": "an amnesic musician",
    "Little Albert": "an infant",
    "Elizabeth Loftus": "a memory researcher",
    "Ivan Pavlov": "a physiologist",
    "B.F. Skinner": "a behavioral researcher",
    "B. F. Skinner": "a behavioral researcher",
    "Burrhus Frederic Skinner": "a behavioral researcher",
    "Solomon Asch": "a social psychologist",
    "Olds and Milner": "two researchers",
    "Brenda Milner": "a neuropsychologist",
    "James Olds": "a researcher",
    "George Miller": "a cognitive psychologist",
    "Harry Harlow": "a primate researcher",
    "Stanley Milgram": "a social psychologist",
    "Albert Bandura": "a psychologist",
    "Stanley Schachter": "a psychologist",
    "Jerome Singer": "a psychologist",
    "Schachter and Singer": "two psychologists",
    "Schachter & Singer": "two psychologists",
    "Aaron Beck": "a psychiatrist",
    "Robert Rosenthal": "a psychologist",
    "Lenore Jacobson": "a school principal",
    "Rosenthal & Jacobson": "two researchers",
    "Ronald Melzack": "a pain researcher",
    "Patrick Wall": "a pain researcher",
    "Melzack & Wall": "two pain researchers",
    "Martin Seligman": "a psychologist",
    "Steven Maier": "a neuroscientist",
    "Seligman & Maier": "two researchers",
    "John Darley": "a social psychologist",
    "Bibb Latané": "a social psychologist",
    "Bibb Latane": "a social psychologist",
    "Darley & Latané": "two social psychologists",
    "Walter Mischel": "a psychologist",
    "Philip Zimbardo": "a psychologist",
    "Roger Shepard": "a cognitive scientist",
    "Jacqueline Metzler": "a cognitive scientist",
    "Shepard & Metzler": "two cognitive scientists",
    "Edward Deci": "a psychologist",
    "Richard Ryan": "a psychologist",
    "David Rosenhan": "a psychologist",
    "Daniel Kahneman and Amos Tversky": "two researchers",
    "Kahneman & Tversky": "two researchers",
    "Kahneman and Tversky": "two researchers",
    "Daniel Kahneman": "a psychologist",
    "Amos Tversky": "a psychologist",
    "Michael Posner": "a neuroscientist",
    "Paul Ekman": "a psychologist",
    "Benjamin Libet": "a neuroscientist",
    "Simon Baron-Cohen": "a psychologist",
    "Daniel Wegner": "a psychologist",
    "Francine Shapiro": "a psychologist",
    "Bernard Baars": "a cognitive scientist",
    "Mihaly Csikszentmihalyi": "a psychologist",
    "Giacomo Rizzolatti": "a neuroscientist",
    "Robin Dunbar": "an anthropologist",
    "Antonio Damasio": "a neuroscientist",
    "Steele & Aronson": "two psychologists",
    "Joseph LeDoux": "a neuroscientist",
    "Nancy Kanwisher": "a neuroscientist",
    "V.S. Ramachandran": "a neuroscientist",
    "V. S. Ramachandran": "a neuroscientist",
    "Kruger & Dunning": "two psychologists",
    "Marcus Raichle": "a neuroscientist",
    "Joshua Greene": "a neuroscientist",
    "Ethan Kross": "a psychologist",
    "John Ridley Stroop": "a psychologist",
    "Bluma Zeigarnik": "a psychologist",
    "John B. Watson": "a behavioral researcher",
    "Rosalie Rayner": "a researcher",
    "Hermann Ebbinghaus": "a memory researcher",
    "Edward Thorndike": "a psychologist",
    "Peter Wason": "a psychologist",
    "Harry McGurk": "a psychologist",
    "John MacDonald": "a researcher",
    "Matthew Botvinick": "a neuroscientist",
    "Jonathan Cohen": "a neuroscientist",
    "Lawrence Weiskrantz": "a neuropsychologist",
    "Joachim Bodamer": "a neurologist",
    "Josef Zihl": "a neuropsychologist",
    "Paul Broca": "a surgeon",
    "Carl Wernicke": "a neurologist",
    "Jules Cotard": "a neurologist",
    "Wilder Penfield": "a neurosurgeon",
    "Jose Delgado": "a neuroscientist",
    "José Delgado": "a neuroscientist",
    "Roger Sperry": "a neuroscientist",
    "David Hubel": "a neuroscientist",
    "Torsten Wiesel": "a neuroscientist",
    "Hubel & Wiesel": "two neuroscientists",
    "Eric Kandel": "a neuroscientist",
    "John O'Keefe": "a neuroscientist",
    "Edvard Moser": "a neuroscientist",
    "May-Britt Moser": "a neuroscientist",
    "Donald Hebb": "a psychologist",
    "George Sperling": "a psychologist",
    "Colin Cherry": "a cognitive scientist",
    "Anne Treisman": "a psychologist",
    "Alan Baddeley": "a psychologist",
    "Endel Tulving": "a psychologist",
    "Fergus Craik": "a psychologist",
    "Robert Lockhart": "a psychologist",
    "Craik & Lockhart": "two psychologists",
    "Leon Festinger": "a social psychologist",
    "Merrill Carlsmith": "a social psychologist",
    "Kenneth Clark": "a psychologist",
    "Mamie Clark": "a psychologist",
    "Henri Tajfel": "a social psychologist",
    "Robert Cialdini": "a psychologist",
    "Jonathan Freedman": "a psychologist",
    "Scott Fraser": "a psychologist",
    "Ellen Langer": "a psychologist",
    "Donald Dutton": "a psychologist",
    "Arthur Aron": "a psychologist",
    "Robert Zajonc": "a psychologist",
    "Robert Trivers": "a biologist",
    "Leda Cosmides": "a psychologist",
    "John Tooby": "an anthropologist",
    "Adrian Raine": "a criminologist",
    "Richard Davidson": "a neuroscientist",
    "Eleanor Maguire": "a neuroscientist",
    "Bogdan Draganski": "a neuroscientist",
    "Wolfram Schultz": "a neuroscientist",
    "Stanislas Dehaene": "a neuroscientist",
}

# Sensitive generic terms (case-insensitive) that Flow's safety layer tends to reject in visual text.
_SENSITIVE_TERMS: tuple[tuple[str, str], ...] = (
    (r"\bslicing\b", "cross-sectioning"),
    (r"\bsliced\b", "cross-sectioned"),
    (r"\bslice\b", "cross-section"),
    (r"\bblood\b", "crimson fluid"),
    (r"\bbleeding\b", "glowing"),
    (r"\bcorpse\b", "anatomical model"),
    (r"\bcadaver\b", "anatomical specimen"),
    (r"\btorture\b", "extreme stress"),
    (r"\bcruelty\b", "harshness"),
    (r"\bmental breakdown\b", "cognitive exhaustion"),
    (r"\bsuicide\b", "severe clinical crisis"),
    (r"\bmurderers\b", "forensic subjects"),
    (r"\bmurderer\b", "forensic subject"),
    (r"\bmurder\b", "forensic incident"),
    (r"\bkilling\b", "deactivating"),
    (r"\bkill\b", "deactivate"),
    (r"\bdead\b", "dormant"),
    (r"\bdeath\b", "shutdown"),
    (r"\bdying\b", "fading"),
    (r"\bvictim\b", "individual"),
    (r"\bseizure\b", "involuntary motor storm"),
    (r"\bfatal\b", "critical"),
    (r"\bviolent\b", "intense"),
    (r"\bviolence\b", "high-energy impact"),
    (r"\baggression\b", "high-energy motor activation"),
    (r"\bexplosion\b", "rapid energetic surge"),
    (r"\bexploding\b", "surging"),
    (r"\bstabbing\b", "penetrating"),
    (r"\biron rod\b", "metal rod"),
    (r"\btamping iron\b", "steel rod"),
    (r"\bskull fracture\b", "cranial cross-section"),
    (r"\btraumatic\b", "high-intensity"),
    (r"\btrauma\b", "neurological disruption"),
    (r"\belectroshock\b", "electrical stimulation"),
    (r"\blobotomy\b", "prefrontal disconnection"),
    (r"\bcharging bull\b", "running bull"),
)


def _protect_allow_list(text: str) -> tuple[str, list[str]]:
    """Masks allow-listed phrases so no replacement can touch them."""
    kept: list[str] = []
    out = text
    for term in sorted(SANITIZER_ALLOW_LIST, key=len, reverse=True):
        rx = re.compile(rf"(?<![A-Za-z]){re.escape(term)}(?![A-Za-z])", re.IGNORECASE)

        def _mask(m: re.Match[str]) -> str:
            kept.append(m.group(0))
            return f"\ue000{len(kept) - 1}\ue001"

        out = rx.sub(_mask, out)
    return out, kept


def _restore_allow_list(text: str, kept: list[str]) -> str:
    return re.sub(r"\ue000(\d+)\ue001", lambda m: kept[int(m.group(1))], text)


def sanitize_prompt_for_flow(text: str, is_spoken_dialogue: bool = False) -> str:
    """
    Cleans visual scene text for Google Flow. Narration (is_spoken_dialogue=True) is returned unchanged:
    it is the canonical script and must match subtitles word for word.
    """
    if is_spoken_dialogue:
        return text
    out, kept = _protect_allow_list(text)
    for name in sorted(_PERSON_NAMES, key=len, reverse=True):
        out = re.sub(rf"(?<![A-Za-z]){re.escape(name)}(?![A-Za-z])", _PERSON_NAMES[name], out)
    for pattern, repl in _SENSITIVE_TERMS:
        out = re.sub(pattern, repl, out, flags=re.IGNORECASE)
    out = _HEX_RE.sub("", out)
    out = re.sub(r"\b(?:Setting|Subject|Protagonist figure|Location)\s*:\s*", "", out, flags=re.IGNORECASE)
    out = re.sub(r"\b\d+(?:\.\d+)?x\b", "rapid", out, flags=re.IGNORECASE)
    out = re.sub(r"\b\d+\s*fps\b", "fluid", out, flags=re.IGNORECASE)
    out = re.sub(r"\(\s*X\s*=\s*\d+%?\s*,?\s*Y\s*=\s*\d+%?\s*\)", "", out, flags=re.IGNORECASE)
    out = re.sub(r"\bX\s*=\s*\d+%?\s*,?\s*Y\s*=\s*\d+%?", "", out, flags=re.IGNORECASE)
    out = re.sub(r"\b\d+\s*mm\b", "tiny", out, flags=re.IGNORECASE)
    out = _restore_allow_list(out, kept)
    out = re.sub(r"\(\s*\)", "", out)
    out = re.sub(r"\s+([,.;:])", r"\1", out)
    out = re.sub(r"\s{2,}", " ", out).strip()
    return out


# ==============================================================================
# Text helpers
# ==============================================================================
def count_words(text: str) -> int:
    """Whitespace word count used by every budget check (scene 50-80, narration 18-28)."""
    return len(str(text or "").split())


def _clean(text: Any) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip().rstrip(".").strip()


def _cap_words(text: str, limit: int) -> str:
    words = _clean(text).split()
    if len(words) <= limit:
        return " ".join(words)
    words = words[:limit]
    while words and words[-1].lower().strip(",;") in {"with", "and", "of", "the", "a", "an", "to", "in", "on", "at", "for", "from", "as", "while"}:
        words.pop()
    return " ".join(words).rstrip(",;")


def _strip_article(text: str) -> str:
    return re.sub(r"^(?:a|an|the)\s+", "", _clean(text), flags=re.IGNORECASE)


def _with_article(text: str) -> str:
    t = _clean(text)
    if not t:
        return t
    if re.match(r"^(?:a|an|the|two|three|several|many|his|her|its|their)\s", t, flags=re.IGNORECASE):
        return t
    return ("an " if t[0].lower() in "aeiou" else "a ") + t


def _the(text: str) -> str:
    return "the " + _strip_article(text)


def _cap_first(text: str) -> str:
    return text[:1].upper() + text[1:] if text else text


def _join(items: list[str]) -> str:
    items = [i for i in items if i]
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    return ", ".join(items[:-1]) + " and " + items[-1]


def _bare_figure(text: str) -> str:
    t = _strip_article(text)
    t = re.sub(r"\b(?:matte-white|porcelain)\s+", "", t, flags=re.IGNORECASE)
    t = re.sub(r"\s*\bmannequins?\b\s*", " ", t, flags=re.IGNORECASE)
    return _clean(t) or "person"


def _env_short(environment: str) -> str:
    t = _strip_article(environment)
    t = re.split(r"\s+(?:with|where|filled|lined|under|beside|near|at|on|in)\s+", t, maxsplit=1)[0]
    words = t.split()
    return " ".join(words[-2:]) if len(words) > 2 else t


# ==============================================================================
# visual_plan normalization
# ==============================================================================
_DEFAULT_ACTIONS: dict[str, str] = {
    "setup": "sits upright and slowly turns its head toward the light",
    "symptom": "stares ahead with a frozen, puzzled expression",
    "failure": "turns its head away and lowers its hands",
    "breakthrough": "lifts its head and leans forward in recognition",
    "conclusion": "sits calmly at the center of the room",
}


def normalize_visual_plan(visual_plan: dict[str, Any] | None) -> dict[str, Any]:
    """Returns a complete, length-capped visual_plan so every role template stays within 50-80 words."""
    vp = dict(visual_plan or {})
    cast = vp.get("cast") if isinstance(vp.get("cast"), dict) else {}
    others_raw = cast.get("others") or []
    if isinstance(others_raw, str):
        others_raw = [others_raw]
    actions_raw = vp.get("mannequin_actions") if isinstance(vp.get("mannequin_actions"), dict) else {}
    actions = {k: _cap_words(actions_raw.get(k) or v, 14) for k, v in _DEFAULT_ACTIONS.items()}

    environment = _cap_words(vp.get("real_environment") or "a dimly lit clinical examination room", 9)
    props = [_cap_words(p, 4) for p in (vp.get("environment_props") or []) if _clean(p)][:3]
    if not props:
        props = ["examination table", "desk lamp"]
    target = _cap_words(vp.get("target_region") or "prefrontal cortex", 6)
    crisis_region = _cap_words(vp.get("crisis_region") or target, 9)
    compensatory = _cap_words(vp.get("compensatory_region") or "prefrontal cortex", 7)
    path = [_cap_words(p, 4) for p in (vp.get("signal_path") or []) if _clean(p)]
    if len(path) < 2:
        path = ["sensory nerve", "thalamus", target]
    steps = [_cap_words(s, 26) for s in (vp.get("mechanism_steps") or []) if _clean(s)]
    while len(steps) < 3:
        steps.append(
            [
                f"A pattern of bioluminescent green particles streams into the {target}",
                f"The signal reaches the {crisis_region} and scatters into darkness",
                f"The {compensatory} lights warm amber-gold as it reroutes the signal",
            ][len(steps)]
        )
    descriptors_raw = vp.get("anatomy_descriptors") if isinstance(vp.get("anatomy_descriptors"), dict) else {}
    descriptors = {str(k): _cap_words(v, 7) for k, v in descriptors_raw.items() if _clean(v)}
    hardware = vp.get("bci_hardware")
    scenes = vp.get("scenes") if isinstance(vp.get("scenes"), dict) else {}

    return {
        "real_environment": environment,
        "environment_short": _cap_words(vp.get("environment_short") or _env_short(environment), 3),
        "environment_props": props,
        "scale_anchor_object": _cap_words(vp.get("scale_anchor_object") or "", 7),
        "subject": _cap_words(_bare_figure(cast.get("subject") or "person"), 3),
        "others": [_cap_words(_bare_figure(o), 3) for o in others_raw if _clean(o)][:2],
        "mannequin_actions": actions,
        "target_region": _strip_article(target),
        "crisis_region": _strip_article(crisis_region),
        "crisis_lesion": _cap_words(vp.get("crisis_lesion") or "disrupted", 3),
        "compensatory_region": _strip_article(compensatory),
        "signal_path": [_strip_article(p) for p in path][:5],
        "mechanism_steps": steps[:3],
        "anatomy_descriptors": descriptors,
        "bci_hardware": _cap_words(hardware, 8) if _clean(hardware) else None,
        "scenes": {str(k): str(v).strip() for k, v in scenes.items() if str(v or "").strip()},
    }


# ==============================================================================
# Role templates (one clean camera move per clip)
# ==============================================================================
_REAL_ENV_FILLERS = (
    "Cinematic chiaroscuro lighting.",
    "Strong rim light traces the porcelain contours.",
    "Soft volumetric haze hangs in the air.",
    "The rest of the room falls into deep shadow.",
)
_BRAIN_FILLERS = (
    "Strong rim light grazes the folds of the cortex.",
    "Fine particles drift through the dark void.",
    "The rest of the brain stays matte white in soft shadow.",
    "Cinematic chiaroscuro lighting.",
)


def _fit_scene(parts: list[tuple[str, str]], fillers: tuple[str, ...]) -> str:
    """parts = [(sentence, 'req'|'opt')]. Drops trailing optional sentences above the max, adds fillers below the min."""
    sentences = [(s.strip(), kind) for s, kind in parts if s and s.strip()]

    def _words(items: list[tuple[str, str]]) -> int:
        return sum(count_words(s) for s, _ in items)

    while _words(sentences) > PROMPT_SCENE_WORDS_MAX and any(k == "opt" for _, k in sentences):
        last_opt = max(i for i, (_, k) in enumerate(sentences) if k == "opt")
        sentences.pop(last_opt)
    for filler in fillers:
        if _words(sentences) >= PROMPT_SCENE_WORDS_MIN:
            break
        if _words(sentences) + count_words(filler) <= PROMPT_SCENE_WORDS_MAX and filler not in [s for s, _ in sentences]:
            sentences.append((filler, "fill"))
    return " ".join(s for s, _ in sentences)


def _descriptor_sentence(plan: dict[str, Any], region: str) -> str:
    for name, desc in plan["anatomy_descriptors"].items():
        if _strip_article(name).lower() in region.lower():
            return f"The {_strip_article(name)} appears as {_with_article(desc)}."
    return ""


def _others_phrase(plan: dict[str, Any], article: str = "the") -> str:
    others = plan["others"]
    if not others:
        return ""
    if article == "a":
        return _join([f"{_with_article(o)} mannequin" for o in others])
    if len(others) == 1:
        return f"the {others[0]} mannequin"
    return f"the {_join(others)} mannequins"


def _hardware_sentence(plan: dict[str, Any]) -> str:
    hw = plan["bci_hardware"]
    if not hw:
        return ""
    return f"A realistic {_strip_article(hw)} rests on the {plan['target_region']}, its fine contacts flickering bioluminescent green."


def _scene_setup(plan: dict[str, Any]) -> str:
    props = [_with_article(p) for p in plan["environment_props"]]
    anchor = plan["scale_anchor_object"]
    anchor_listed = bool(anchor) and any(_strip_article(anchor).lower().startswith(_strip_article(p).lower()) for p in plan["environment_props"])
    others = _others_phrase(plan, article="a")
    verb = "stands" if len(plan["others"]) == 1 else "stand"
    return _fit_scene(
        [
            (f"{_cap_first(_with_article(plan['real_environment']))} with {_join(props)}.", "req"),
            (
                f"A matte-white porcelain mannequin of {_with_article(plan['subject'])} {plan['mannequin_actions']['setup']}, "
                "its translucent frosted-glass cranium catching the light.",
                "req",
            ),
            (f"{_cap_first(others)} {verb} nearby." if others else "", "opt"),
            (f"{_cap_first(_with_article(anchor))} anchors the scale in the foreground." if anchor and not anchor_listed else "", "opt"),
            ("Wide establishing shot, camera smoothly tracks forward toward the subject.", "req"),
            ("Cinematic chiaroscuro lighting.", "req"),
        ],
        _REAL_ENV_FILLERS,
    )


def _scene_symptom(plan: dict[str, Any]) -> str:
    return _fit_scene(
        [
            (f"Close-up on the {plan['subject']} mannequin's smooth porcelain face as it {plan['mannequin_actions']['symptom']}.", "req"),
            (
                "The camera slowly orbits the head, revealing the brain through the translucent frosted-glass cranium: "
                f"the {plan['target_region']} glows electric cyan-blue while the {plan['crisis_region']} fades to dim crimson-red.",
                "req",
            ),
            (f"Strong rim light traces the porcelain contours; the {plan['environment_short']} falls into shadow.", "req"),
        ],
        _REAL_ENV_FILLERS,
    )


def _scene_failure(plan: dict[str, Any]) -> str:
    subj = plan["subject"]
    if plan["others"]:
        others = _others_phrase(plan)
        verb = "reaches" if len(plan["others"]) == 1 else "reach"
        parts = [
            (f"In the same {plan['environment_short']}, {others} {verb} toward the {subj} mannequin with pleading gestures.", "req"),
            (f"The {subj} mannequin {plan['mannequin_actions']['failure']}.", "req"),
            ("The camera tracks smoothly sideways between the figures, capturing the distance.", "req"),
            (f"Warm amber light falls on the other figures while the {subj} mannequin stays in cool shadow.", "req"),
        ]
    else:
        props = _join([_the(p) for p in plan["environment_props"][:2]])
        parts = [
            (f"In the same {plan['environment_short']}, the {subj} mannequin {plan['mannequin_actions']['failure']}.", "req"),
            (f"Nearby, {props} stand unused.", "req"),
            ("The camera tracks smoothly sideways past the props toward the lone figure, capturing its isolation.", "req"),
            ("Cool shadow surrounds the porcelain figure while warm light spills across the empty room.", "req"),
        ]
    return _fit_scene(parts, _REAL_ENV_FILLERS)


def _scene_crisis(plan: dict[str, Any]) -> str:
    return _fit_scene(
        [
            (
                f"The camera dives smoothly through the {plan['subject']} mannequin's translucent frosted-glass cranium into a deep "
                "midnight navy void holding a realistic matte-white brain with visible gyri and sulci.",
                "req",
            ),
            (
                f"It glides over the cortex and zooms into the {plan['target_region']}, which pulses electric cyan-blue, while the "
                f"{plan['crisis_region']} is {plan['crisis_lesion']} and glowing crimson-red, its signal particles scattering into darkness.",
                "req",
            ),
            (_descriptor_sentence(plan, plan["crisis_region"]) or _descriptor_sentence(plan, plan["target_region"]), "opt"),
        ],
        _BRAIN_FILLERS,
    )


def _scene_pivot(plan: dict[str, Any]) -> str:
    return _fit_scene(
        [
            (
                "Inside the matte-white brain on a deep midnight navy void, the camera smoothly orbits the "
                f"{plan['target_region']} glowing electric cyan-blue and the {plan['crisis_region']} dimmed crimson-red.",
                "req",
            ),
            (f"Nearby, the {plan['compensatory_region']} ignites warm amber-gold, opening an intact alternative route.", "req"),
            ("The camera slowly pushes in on the glowing amber-gold route.", "req"),
            (_descriptor_sentence(plan, plan["compensatory_region"]), "opt"),
        ],
        _BRAIN_FILLERS,
    )


def _path_sentence(plan: dict[str, Any]) -> str:
    path = plan["signal_path"]
    middle = _join([_the(p) for p in path[1:-1]])
    via = f" through {middle}" if middle else ""
    return f"Bioluminescent green signal particles flow like fluid from the {path[0]}{via} into the {path[-1]}."


def _scene_step(plan: dict[str, Any], role: str) -> str:
    steps = plan["mechanism_steps"]
    if role == "step1":
        parts = [
            ("Macro view inside the matte-white brain against deep midnight navy.", "req"),
            (_path_sentence(plan), "req"),
            (f"{_cap_first(steps[0])}.", "req"),
            ("The camera tracks the flowing signal along the pathway.", "req"),
        ]
    elif role == "step2":
        parts = [
            (
                f"Inside the matte-white brain on deep midnight navy, the camera follows the bioluminescent green signal as it "
                f"leaves the electric cyan-blue {plan['target_region']}.",
                "req",
            ),
            (f"{_cap_first(steps[1])}.", "req"),
            (_hardware_sentence(plan), "opt"),
            ("The camera slowly orbits the junction.", "req"),
        ]
    elif role == "step3":
        parts = [
            ("The camera pulls back to reveal the whole circuit inside the matte-white brain against deep midnight navy.", "req"),
            (
                f"The {plan['target_region']} glows electric cyan-blue, the {plan['crisis_region']} crimson-red and the "
                f"{plan['compensatory_region']} warm amber-gold.",
                "req",
            ),
            (f"{_cap_first(steps[2])}.", "req"),
            ("The full brain turns slowly in the void.", "opt"),
        ]
    else:  # single mechanism clip for 5-7 clip Shorts
        parts = [
            ("Macro view inside the matte-white brain against deep midnight navy.", "req"),
            (_path_sentence(plan), "req"),
            (f"{_cap_first(steps[1])}.", "req"),
            (_hardware_sentence(plan), "opt"),
            ("The camera tracks the flowing signal, then pulls back to the full circuit.", "req"),
        ]
    return _fit_scene(parts, _BRAIN_FILLERS)


def _scene_breakthrough(plan: dict[str, Any]) -> str:
    return _fit_scene(
        [
            (
                "The camera pulls smoothly out of the brain, back through the translucent frosted-glass cranium, into the "
                f"{plan['environment_short']}.",
                "req",
            ),
            (f"The {plan['subject']} mannequin {plan['mannequin_actions']['breakthrough']}.", "req"),
            (f"Inside its cranium, the {plan['compensatory_region']} glows warm amber-gold.", "req"),
            ("Warm light bathes the porcelain figure.", "req"),
            (_hardware_sentence(plan).replace("A realistic", "The realistic") if plan["bci_hardware"] else "", "opt"),
        ],
        _REAL_ENV_FILLERS,
    )


def _scene_conclusion(plan: dict[str, Any]) -> str:
    others = _others_phrase(plan)
    verb = "stands" if len(plan["others"]) == 1 else "stand"
    figures = "figures" if plan["others"] else "figure"
    return _fit_scene(
        [
            (f"Wide shot of the {plan['environment_short']}: the {plan['subject']} mannequin {plan['mannequin_actions']['conclusion']}.", "req"),
            (f"{_cap_first(others)} {verb} beside it." if others else "", "opt"),
            (
                f"Inside its translucent frosted-glass cranium, the {plan['target_region']} glows electric cyan-blue and the "
                f"{plan['compensatory_region']} glows warm amber-gold.",
                "req",
            ),
            ("The camera slowly pulls back and rises to an elevated wide shot.", "req"),
            (f"Strong rim light outlines the porcelain {figures}.", "req"),
        ],
        _REAL_ENV_FILLERS,
    )


def compose_scene(role: str, plan: dict[str, Any]) -> str:
    """Fills the role template from a normalized visual_plan (no explicit scene override)."""
    if role == "setup":
        scene = _scene_setup(plan)
    elif role == "symptom":
        scene = _scene_symptom(plan)
    elif role == "failure":
        scene = _scene_failure(plan)
    elif role == "crisis":
        scene = _scene_crisis(plan)
    elif role == "pivot":
        scene = _scene_pivot(plan)
    elif role in ("mechanism", "step1", "step2", "step3"):
        scene = _scene_step(plan, role)
    elif role == "breakthrough":
        scene = _scene_breakthrough(plan)
    elif role == "conclusion":
        scene = _scene_conclusion(plan)
    else:
        raise ValueError(f"Unknown clip role: {role}")
    return sanitize_prompt_for_flow(scene)


# ==============================================================================
# Public API (Contract §2): render, build, validate, load, write
# ==============================================================================
def infer_visual_plan(
    topic: str,
    core_facts: str = "",
    pillar_id: str = "brain_basics",
    story_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Deterministically infers a Contract v4 visual_plan from topic metadata."""
    ctx = dict(story_context or {})
    t_low = f"{topic} {core_facts}".lower()

    if "capgras" in t_low or "imposter" in t_low or "impostor" in t_low:
        env = "a dimly lit hospital room"
        props = ["hospital bed", "EKG monitor", "window with drawn blinds"]
        anchor = "EKG monitor beside the bed"
        target = "fusiform face area"
        crisis = "white-matter tract to the amygdala"
        comp = "auditory pathway to the amygdala"
        path = ["retina", "optic nerve", "occipital cortex", "fusiform face area", "amygdala"]
        hw = None
    elif any(k in t_low for k in ("bci", "electrode", "implant", "decoder", "neuralink", "stentrode", "ecog", "utah")):
        env = "a clinical neuroengineering suite"
        props = ["high-back clinical wheelchair", "EKG monitor"]
        anchor = "EKG monitor beside the chair"
        target = "motor cortex"
        crisis = "descending corticospinal tract"
        comp = "prefrontal cortex"
        path = ["retina", "thalamus", "prefrontal cortex", "motor cortex"]
        hw = "micro-electrode array"
    elif any(k in t_low for k in ("sleep", "glymphatic", "dream", "circadian", "insomnia", "rem")):
        env = "a dimly lit bedroom"
        props = ["hospital bed", "EKG monitor"]
        anchor = "EKG monitor beside the bed"
        target = "thalamus"
        crisis = "prefrontal cortex"
        comp = "hippocampus"
        path = ["retina", "thalamus", "hippocampus", "prefrontal cortex"]
        hw = None
    elif any(k in t_low for k in ("memory", "amnesia", "hippocamp", "alzheimer", "hm", "molaison", "ebbinghaus", "loftus")):
        env = "a clinical interview room"
        props = ["examination table", "desk lamp"]
        anchor = "desk lamp on the table"
        target = "hippocampus"
        crisis = "white-matter tract to the prefrontal cortex"
        comp = "basal ganglia"
        path = ["retina", "optic nerve", "thalamus", "hippocampus", "prefrontal cortex"]
        hw = None
    elif any(k in t_low for k in ("fear", "amygdala", "panic", "stress", "phobia", "pavlov", "albert", "conditioning")):
        env = "a clinical laboratory"
        props = ["examination table", "EKG monitor"]
        anchor = "EKG monitor on the table"
        target = "amygdala"
        crisis = "white-matter tract from the prefrontal cortex"
        comp = "prefrontal cortex"
        path = ["retina", "thalamus", "amygdala", "prefrontal cortex"]
        hw = None
    elif any(k in t_low for k in ("speech", "broca", "wernicke", "language", "aphasia", "voice")):
        env = "a dimly lit clinical examination room"
        props = ["examination table", "telephone"]
        anchor = "telephone on the table"
        target = "Broca's area"
        crisis = "white-matter tract to Wernicke's area"
        comp = "temporal lobe"
        path = ["auditory nerve", "thalamus", "Wernicke's area", "Broca's area"]
        hw = None
    else:
        env = "a dimly lit clinical laboratory"
        props = ["examination table", "EKG monitor"]
        anchor = "EKG monitor on the table"
        target = _cap_words(ctx.get("brain_regions") or "prefrontal cortex", 4)
        if not any(a in target.lower() for a in ("cortex", "amygdala", "hippocampus", "thalamus", "striatum", "ganglia", "lobe", "area", "callosum", "cerebellum", "brainstem", "insula")):
            target = "prefrontal cortex"
        crisis = f"white-matter tract to the {target}"
        comp = "basal ganglia" if "prefrontal" in target.lower() else "prefrontal cortex"
        path = ["retina", "optic nerve", "thalamus", target]
        hw = None

    return normalize_visual_plan(
        {
            "real_environment": env,
            "environment_props": props,
            "scale_anchor_object": anchor,
            "cast": {"subject": "adult patient", "others": ["researcher"]},
            "mannequin_actions": dict(_DEFAULT_ACTIONS),
            "target_region": target,
            "crisis_region": crisis,
            "crisis_lesion": "severed",
            "compensatory_region": comp,
            "signal_path": path,
            "mechanism_steps": [
                f"Bioluminescent green signal particles stream into the {target} and light it electric cyan-blue",
                f"At the severed crimson-red {crisis}, the glowing signal particles scatter into darkness",
                f"The {comp} ignites warm amber-gold and routes a clean signal pulse across the circuit",
            ],
            "anatomy_descriptors": {
                "amygdala": "small almond-shaped nucleus",
                "hippocampus": "curved seahorse-shaped ridge",
            },
            "bci_hardware": hw,
        }
    )


def render_prompt(scene: str, narration: str, voice: str = FLOW_DEFAULT_VOICE) -> str:
    """Renders a single Google Flow Omni 1.1 prompt string."""
    clean_scene = _clean(scene)
    if clean_scene and not clean_scene.endswith("."):
        clean_scene += "."
    clean_narr = str(narration or "").strip().replace('"', "'")
    return f'{FLOW_PROMPT_PREFIX} {clean_scene} Voice: {voice}. Spoken narration: "{clean_narr}"'


def build_flow_prompts(
    visual_plan: dict[str, Any] | None,
    narrations: list[str],
    voice: str = FLOW_DEFAULT_VOICE,
) -> list[dict[str, Any]]:
    """
    Builds 5-10 Google Flow clip prompt dicts from a visual_plan and per-clip narrations.
    If visual_plan['scenes'][role] is present, uses that exact scene string verbatim.
    """
    cleaned_narrs = [str(n).strip() for n in (narrations or []) if str(n).strip()]
    n_clips = len(cleaned_narrs)
    roles = clip_roles(n_clips)
    plan = normalize_visual_plan(visual_plan)
    explicit_scenes = (visual_plan or {}).get("scenes") if isinstance((visual_plan or {}).get("scenes"), dict) else {}

    clips: list[dict[str, Any]] = []
    for idx, (role, narr) in enumerate(zip(roles, cleaned_narrs), start=1):
        if role in explicit_scenes and str(explicit_scenes[role]).strip():
            scene = str(explicit_scenes[role]).strip()
        else:
            scene = compose_scene(role, plan)
        prompt_str = render_prompt(scene=scene, narration=narr, voice=voice)
        clips.append(
            {
                "clip_number": idx,
                "role": role,
                "setting": ROLE_SETTINGS[role],
                "camera_move": ROLE_CAMERA_MOVES[role],
                "scene": scene,
                "spoken_narration": narr,
                "prompt": prompt_str,
                "full_prompt": prompt_str,
            }
        )
    return clips


def validate_flow_prompts(prompts: list[str | dict[str, Any]]) -> list[str]:
    """Validates a list of Flow prompts against Production Contract v4. Returns [] on pass."""
    issues: list[str] = []
    if not isinstance(prompts, list) or not (CLIP_COUNT_MIN <= len(prompts) <= CLIP_COUNT_MAX):
        return [f"Prompt count must be {CLIP_COUNT_MIN}-{CLIP_COUNT_MAX} (got {len(prompts) if isinstance(prompts, list) else 0})"]

    for idx, item in enumerate(prompts, start=1):
        p_str = item.get("prompt") or item.get("full_prompt") or "" if isinstance(item, dict) else str(item or "")
        p_str = p_str.strip()
        if not p_str.startswith(FLOW_PROMPT_PREFIX):
            issues.append(f"Clip {idx}: does not start with FLOW_PROMPT_PREFIX")
            continue
        body = p_str[len(FLOW_PROMPT_PREFIX) :].strip()
        m = _PROMPT_RE.match(body)
        if not m:
            issues.append(f"Clip {idx}: missing or malformed 'Voice: <voice>. Spoken narration: \"...\"' tail")
            continue
        if body.count("Voice:") != 1 or body.count("Spoken narration:") != 1:
            issues.append(f"Clip {idx}: must contain exactly one Voice/Spoken narration block")

        scene = m.group("scene").strip()
        voice = m.group("voice").strip()
        narration = m.group("narration").strip()

        if voice != FLOW_DEFAULT_VOICE:
            issues.append(f"Clip {idx}: voice must be '{FLOW_DEFAULT_VOICE}' (got '{voice}')")
        if not narration:
            issues.append(f"Clip {idx}: spoken narration is empty")

        scene_words = count_words(scene)
        if not (PROMPT_SCENE_WORDS_MIN <= scene_words <= PROMPT_SCENE_WORDS_MAX):
            issues.append(
                f"Clip {idx}: scene word count {scene_words} outside {PROMPT_SCENE_WORDS_MIN}-{PROMPT_SCENE_WORDS_MAX}"
            )

        if _HEX_RE.search(p_str):
            issues.append(f"Clip {idx}: contains #hex colour code")
        if _AUDIO_RE.search(p_str):
            issues.append(f"Clip {idx}: contains banned 'Audio:' directive")
        if _CAMERA_ANGLE_RE.search(p_str):
            issues.append(f"Clip {idx}: contains banned 'Camera Angle' label")

        for tok, rx in _STRUCTURAL_REGEXES:
            if rx.search(p_str):
                issues.append(f"Clip {idx}: contains banned structural token '{tok}'")
        for tok, rx in _PROP_REGEXES:
            if rx.search(scene):
                issues.append(f"Clip {idx}: scene contains banned mechanical/toy prop token '{tok}'")

    return issues


def validate_narrations(narrations: list[str]) -> list[str]:
    """
    Validates a 5-10 clip narration list per Contract §0 D1-D2 & §2:
      - 5 to 10 clips
      - 18 to 28 words per clip
      - total words within script_word_range(n)
      - pivot clip contains 'Instead of'
      - conclusion opens with 'Which proves' or 'Which is why'
      - Meme #1 ('this is/was a total nightmare') in symptom or crisis clip
      - Meme #2 ('The researchers were left completely stunned') in breakthrough (or mechanism/conclusion for 5-clip)
    """
    issues: list[str] = []
    if not isinstance(narrations, list):
        return ["narrations must be a list of strings"]
    cleaned = [str(s).strip() for s in narrations if str(s).strip()]
    n = len(cleaned)
    if not (CLIP_COUNT_MIN <= n <= CLIP_COUNT_MAX):
        return [f"Clip count must be {CLIP_COUNT_MIN}-{CLIP_COUNT_MAX} (got {n})"]

    roles = clip_roles(n)
    total_words = 0
    for idx, (role, line) in enumerate(zip(roles, cleaned), start=1):
        wc = count_words(line)
        total_words += wc
        if not (CLIP_WORDS_MIN <= wc <= CLIP_WORDS_MAX):
            issues.append(f"Clip {idx} ({role}): word count {wc} outside {CLIP_WORDS_MIN}-{CLIP_WORDS_MAX}")

    min_total, max_total = script_word_range(n)
    if not (min_total <= total_words <= max_total):
        issues.append(f"Total word count {total_words} outside {min_total}-{max_total}")

    by_role = {r: line for r, line in zip(roles, cleaned)}
    pivot_line = by_role.get("pivot", "")
    if PIVOT_MARKER not in pivot_line.lower():
        issues.append("Pivot clip must contain 'Instead of'")

    conclusion_line = by_role.get("conclusion", "").strip()
    if not any(conclusion_line.lower().startswith(op.lower()) for op in CONCLUSION_OPENERS):
        issues.append("Conclusion clip must open with 'Which proves' or 'Which is why'")

    crisis_Window = " ".join(by_role.get(r, "") for r in ("symptom", "crisis"))
    if not MEME_CRISIS_PATTERN.search(crisis_Window):
        issues.append("Symptom or crisis clip must contain 'this is/was a total nightmare'")

    awe_roles = ("breakthrough",) if "breakthrough" in by_role else ("mechanism", "conclusion")
    awe_window = " ".join(by_role.get(r, "") for r in awe_roles).lower()
    if MEME_AWE_TEXT not in awe_window:
        issues.append(f"Clip in {awe_roles} must contain 'The researchers were left completely stunned'")

    return issues


def load_visual_plan(
    project_dir: Path | None = None,
    topic_item: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Loads visual_plan with precedence:
      1. project_dir / '03_visuals' / 'visual_plan.json'
      2. project_dir / '01_ideation' / 'research_card.json' -> ['visual_plan']
      3. topic_item['visual_plan']
      4. infer_visual_plan(...)
    """
    if project_dir is not None:
        p_dir = Path(project_dir)
        vp_file = p_dir / "03_visuals" / VISUAL_PLAN_FILENAME
        if vp_file.exists():
            try:
                data = json.loads(vp_file.read_text(encoding="utf-8"))
                if isinstance(data, dict) and data:
                    return data
            except Exception:
                pass
        rc_file = p_dir / "01_ideation" / "research_card.json"
        if rc_file.exists():
            try:
                rc = json.loads(rc_file.read_text(encoding="utf-8"))
                if isinstance(rc.get("visual_plan"), dict) and rc["visual_plan"]:
                    return rc["visual_plan"]
            except Exception:
                pass

    if isinstance(topic_item, dict):
        if isinstance(topic_item.get("visual_plan"), dict) and topic_item["visual_plan"]:
            return dict(topic_item["visual_plan"])
        return infer_visual_plan(
            topic=str(topic_item.get("topic") or topic_item.get("title") or "Neural Circuit"),
            core_facts=str(topic_item.get("core_facts") or topic_item.get("summary") or ""),
            pillar_id=str(topic_item.get("pillar") or "brain_basics"),
            story_context=topic_item.get("story_context") if isinstance(topic_item.get("story_context"), dict) else None,
        )

    return infer_visual_plan("Neural Circuit")


def write_flow_prompts_json(project_dir: Path, clips: list[dict[str, Any]], voice: str = FLOW_DEFAULT_VOICE) -> Path:
    """Writes 03_visuals/flow_all_in_one_prompts.json in Schema v4 format."""
    vis_dir = Path(project_dir) / "03_visuals"
    vis_dir.mkdir(parents=True, exist_ok=True)
    out_path = vis_dir / FLOW_PROMPTS_FILENAME
    payload = {
        "schema_version": SCHEMA_VERSION,
        "voice": voice,
        "clips": clips,
        "prompts": [c.get("prompt") or c.get("full_prompt") or "" for c in clips],
    }
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return out_path
