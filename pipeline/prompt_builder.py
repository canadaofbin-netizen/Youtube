"""
ALL ABOUT BRAIN - Canonical Google Flow Prompt Builder (Production Contract v4).

Single source of truth for every Google Flow (Gemini Omni 1.2) clip prompt:

    {FLOW_PROMPT_PREFIX} <scene 50-80 words> Voice: Consistent deep male baritone documentary narrator. Spoken narration: "<line>"

- One clip = one narrative role (config.clip_roles) = one clean camera move.
- Context clips use a narration-matched photoreal environment with matte-white porcelain mannequins;
  brain clips use a realistic matte-white brain in a bright white studio gallery.
- 4-point colour code: crimson-red = crisis, electric cyan-blue = target region,
  warm amber-gold = active/compensatory circuit, bioluminescent green = signal transmission.
- The sanitizer is applied to template-generated scene text only, never to narration.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
from typing import Any

from pipeline.config import (
    ALLOWED_SETTINGS_V5,
    BRAIN_SETTINGS,
    CLIP_COUNT_MAX,
    CLIP_COUNT_MIN,
    CLIP_MAX_RENDER_SEC,
    CLIP_WORDS_MAX,
    CLIP_WORDS_MIN,
    FLOW_ALLOWED_DURATION_TARGETS,
    FLOW_ASPECT_LABELS,
    FLOW_ASPECT_SHORTS,
    FLOW_CLIP_DURATION_TARGET,
    FLOW_CLIP_SAFE_MAX_SYLLABLES,
    FLOW_DEFAULT_VOICE,
    FLOW_LEGACY_VOICE_LABELS,
    FLOW_MOTION_STYLE_V5,
    FLOW_OMNI_CREDIT_COST_WITH_REF,
    FLOW_OMNI_EPISODE_CREDIT_CAP,
    FLOW_OMNI_HERO_MAX_CLIPS,
    FLOW_PRIMARY_VIDEO_MODEL,
    FLOW_PROMPT_PREFIX,
    FLOW_RETIRED_VIDEO_MODELS,
    FLOW_SHORT_CLIP_MAX_SYLLABLES,
    FLOW_SHORT_CLIP_MAX_WORDS,
    FLOW_VOICE_PROMPT_DESCRIPTOR,
    FLOW_VOICE_PROMPT_DESCRIPTOR_V5,
    MODE_ROLE_SETTINGS,
    PROMPT_SCENE_WORDS_MAX,
    PROMPT_SCENE_WORDS_MIN,
    PROMPT_SCHEMA_VERSION_V5,
    PROMPT_SCHEMA_VERSION_V6,
    PROMPT_SCHEMA_VERSION_V7,
    PROMPT_SCHEMA_VERSION_V8,
    ROLE_SETTINGS,
    DIORAMA_CAMERA_MOVES,
    DIORAMA_CLIP_COUNT_MAX,
    DIORAMA_CLIP_COUNT_MIN,
    DIORAMA_CLIP_RENDER_SEC,
    DIORAMA_SCENE_WORDS_MAX,
    DIORAMA_SCENE_WORDS_MIN,
    DIORAMA_VISUAL_GRAMMARS,
    DIORAMA_V7_CAMERA_MOVES,
    DIORAMA_V7_CUTAWAY_MAX_RATIO,
    DIORAMA_V7_LOCKED_CAMERA_MIN_RATIO,
    DIORAMA_V7_STYLE_PROFILE,
    DIORAMA_V7_VISUAL_GRAMMARS,
    DIORAMA_V7_ZOOM_CAMERA_MAX_RATIO,
    EXPRESSIVE_25D_V8_STYLE_PROFILE,
    EXPRESSIVE_V8_3D_FLIGHT_MOVES,
    EXPRESSIVE_V8_BRAIN_REVEAL_TOLERANCE_FRAC,
    EXPRESSIVE_V8_CAMEO_COUNT_PER_EPISODE,
    EXPRESSIVE_V8_CAMEO_SHEET_FILENAME,
    EXPRESSIVE_V8_CAMERA_FAST_FPV_MAX_RATIO,
    EXPRESSIVE_V8_CAMERA_LOCKED_MIN_RATIO,
    EXPRESSIVE_V8_CAMERA_MOVES,
    EXPRESSIVE_V8_CAMERA_ORBIT_MAX_RATIO,
    EXPRESSIVE_V8_CAST_SHEET_FILENAMES,
    EXPRESSIVE_V8_CONTEXT_SPLIT_WORDS_RANGE,
    EXPRESSIVE_V8_DRONE_CAMERA_MOVES,
    EXPRESSIVE_V8_LEGACY_CLIP_COUNT_MIN,
    EXPRESSIVE_V8_LEGACY_INDOOR_CLIP_COUNT_RANGE,
    EXPRESSIVE_V8_MAX_CONSECUTIVE_SAME_INDOOR_LOC,
    EXPRESSIVE_V8_MIN_3D_FLIGHT_RATIO,
    EXPRESSIVE_V8_MIN_DISTINCT_LOCATIONS,
    EXPRESSIVE_V8_MIN_DRONE_FLIGHT_RATIO,
    EXPRESSIVE_V8_MIN_OUTDOOR_OR_ARCH_RATIO,
    EXPRESSIVE_V8_REQUIRE_REAL_LANDMARK_REFS,
    EXPRESSIVE_V8_RIGID_PHYSICS_GRAMMARS,
    EXPRESSIVE_V8_SPECIES_SHEET_FILENAME,
    EXPRESSIVE_V8_TRANSITION_TYPES,
    EXPRESSIVE_V8_VISUAL_GRAMMARS,
    PORCELAIN_V7_STYLE_PROFILE,
    PORCELAIN_V7_VISUAL_GRAMMARS,
    REAL_WORLD_REFS_MANIFEST_FILENAME,
    SHORTS_EXPRESSIVE_V8_CLIP_COUNT_MAX,
    SHORTS_EXPRESSIVE_V8_CLIP_COUNT_MIN,
    SHORTS_EXPRESSIVE_V8_PROFILE,
    compute_dynamic_omni_episode_budget,
    is_diorama_profile,
    is_diorama_v7_plan,
    is_expressive_v8_plan,
    is_porcelain_v7_plan,
    is_r72_open_world_v8_plan,
    resolve_diorama_v7_style_profile,
    VISUAL_MODES,
    clip_roles,
    script_word_range,
)
from pipeline.depiction_rules import (
    SELECTIVE_COLOR_BACKDROP_CLAUSE,
    resolve_act_lighting_hint,
    resolve_alternating_camera_move,
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
    "target": "soft cyan-blue",
    "active": "warm amber-gold",
    "signal": "clear cyan-blue",
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
# Mechanical/toy prop tokens and screen-filling particle/spark/negative VFX tokens are banned in the visual scene.
# Narration is canonical script text and is never rewritten, so these are only checked in the scene.
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
    "particles",
    "sparks",
    "scatter into space",
    "crash and scatter",
    "fireworks",
    "flashing",
    "electric",
    "no particles",
    "zero particles",
    "no sparks",
    "zero sparks",
    "never scatter",
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
    r'^(?P<scene>.*?) Voice: (?P<voice>[^.]+)\. Spoken narration: "(?P<narration>[^"]*)"$',
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
    (r"\belectroshock\b", "controlled stimulation"),
    (r"\blobotomy\b", "prefrontal disconnection"),
    (r"\bcharging bull\b", "running bull"),
    (
        r",\s*its\s+signal\s+particles\s+colliding\s+and\s+scattering\s+into\s+space",
        ", where the smooth internal stream pools and fades softly",
    ),
    (
        r",\s*its\s+signal\s+particles\s+scattering\s+into\s+(?:space|darkness|the\s+dark\s+void)",
        ", where the smooth internal stream pools and fades softly",
    ),
    (
        r"\bthe\s+(?:bioluminescent\s+green\s+)?(?:signal\s+)?particles\s+(?:crash|collide)\s+and\s+scatter\s+(?:into\s+space|into\s+the\s+dark\s+void|into\s+darkness|like\s+water\s+hitting\s+a\s+wall)\b",
        "the smooth internal stream pools and fades softly against the closed channel edge",
    ),
    (
        r"\b(?:particles\s+)?(?:crash|collide)\s+and\s+scatter(?:\s+into\s+(?:space|darkness|the\s+dark\s+void))?\b",
        "the smooth internal stream pools and fades softly",
    ),
    (
        r"\bscatters?\s+into\s+(?:space|darkness|the\s+dark\s+void)\b",
        "pools and fades softly inside the channel",
    ),
    (
        r"\bscattering\s+into\s+(?:space|darkness|the\s+dark\s+void)\b",
        "pooling and fading softly inside the channel",
    ),
    (
        r"\bbioluminescent\s+green\s+(?:visual\s+|auditory\s+)?signal\s+particles\b",
        "smooth warm amber-gold channel streams",
    ),
    (
        r"\bbioluminescent\s+green\s+particles\b",
        "smooth warm amber-gold channel streams",
    ),
    (
        r"\bsignal\s+particles\b",
        "internal channel streams",
    ),
    (
        r"\bfine\s+particles\s+drift\s+through\s+the\s+bright\s+air\b",
        "soft studio light traces the internal channels",
    ),
    (
        r"\bholding a realistic matte-white brain\b",
        "holding an architectural cross-section cutaway of a realistic matte-white brain",
    ),
    (r"\bparticles\b", "streams"),
    (r"\bsparks\b", "warm glow"),
    (r"\bfireworks\b", "steady glow"),
    (r"\bflashing\b", "pulsing"),
    (r"\belectric\s+cyan-blue\b", "soft cyan-blue"),
    (r"\belectric\b", "active"),
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
    If called on a full prompt containing 'Voice: <voice>. Spoken narration: "..."', only the visual scene
    portion before 'Voice:' is sanitized and the spoken narration tail is preserved verbatim.
    """
    if is_spoken_dialogue:
        return text
    m_tail = re.search(r'(\s*Voice:\s*[^.]+\.\s*Spoken narration:\s*"[^"]*"\s*)$', text, flags=re.DOTALL)
    if m_tail:
        scene_part = text[: m_tail.start()].strip()
        tail_part = m_tail.group(1).strip()
        tail_part = re.sub(
            r"^Voice:\s*Puck\.",
            f"Voice: {FLOW_VOICE_PROMPT_DESCRIPTOR}.",
            tail_part,
        )
        prefix = ""
        if scene_part.startswith(FLOW_PROMPT_PREFIX):
            prefix = FLOW_PROMPT_PREFIX + " "
            scene_part = scene_part[len(FLOW_PROMPT_PREFIX) :].strip()
        cleaned_scene = sanitize_prompt_for_flow(scene_part, is_spoken_dialogue=False)
        if cleaned_scene and not cleaned_scene.endswith("."):
            cleaned_scene += "."
        return f"{prefix}{cleaned_scene} {tail_part}".strip()

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
    out = re.sub(r"\([\s\-–—/,;:]*\)", "", out)
    out = re.sub(r"\s+([,.;:])", r"\1", out)
    out = re.sub(r"\s{2,}", " ", out).strip()
    return out


_DIORAMA_POLICY_TERMS: tuple[tuple[str, str], ...] = (
    (r"\bgore\b", "impact residue"),
    (r"\bgory\b", "clinical"),
    (r"\bbloody\b", "terracotta-stained"),
    (r"\bbleeding\b", "seeping"),
    (r"\bblood\b", "terracotta stain"),
    (r"\bcorpses\b", "still figures"),
    (r"\bcorpse\b", "still figure"),
    (r"\bcadavers\b", "anatomical models"),
    (r"\bcadaver\b", "anatomical model"),
    (r"\btorture\b", "extreme stress"),
    (r"\bsuicide\b", "severe clinical crisis"),
    (r"\bmurderers\b", "forensic subjects"),
    (r"\bmurderer\b", "forensic subject"),
    (r"\bmurder\b", "forensic incident"),
    (r"\bstabbing\b", "piercing"),
    (r"\bdecapitat\w*\b", "severed"),
    (r"\bdismember\w*\b", "separated"),
    (r"\bmutilat\w*\b", "damaged"),
    # Anti-literal animal/food hallucination guards for 3D neuroanatomy prompts (e.g., ocean seahorse fish in C10)
    (r"\bseahorse[-\s]+shaped\b", "smooth rounded C-curved"),
    (r"\bseahorses?\b", "smooth rounded C-curved medial-temporal cylinder"),
    (r"\balmond[-\s]+shaped\b", "ovoid"),
    (r"\balmonds?\b", "ovoid nucleus"),
    (r"\bwalnut[-\s]+(?:shaped|like)\b", "folded bilateral"),
    (r"\bwalnuts?\b", "folded hemisphere"),
)


def sanitize_diorama_scene_for_flow(text: str) -> str:
    """
    Diorama-safe Google Flow scene sanitizer: removes #hex colour codes and softens violent policy
    triggers while preserving clinical/historical diorama props (e.g., 'iron rod', 'tamping iron',
    'skull', 'mm', 'fps') and low-poly architectural vocabulary.
    """
    out = _HEX_RE.sub("", str(text or ""))
    for pattern, repl in _DIORAMA_POLICY_TERMS:
        out = re.sub(pattern, repl, out, flags=re.IGNORECASE)
    out = re.sub(r"\([\s\-–—/,;:]*\)", "", out)
    out = re.sub(r"\s+([,.;:])", r"\1", out)
    out = re.sub(r"\s{2,}", " ", out).strip()
    return out


# ==============================================================================
# Text helpers
# ==============================================================================
def count_words(text: str) -> int:
    """Whitespace word count used by every budget check (scene 50-80, narration 18-28)."""
    return len(str(text or "").split())


def _expand_digits_for_syllables(raw_text: str) -> str:
    from pipeline.plain_language import number_to_words, year_to_words

    def _repl_num(m: re.Match[str]) -> str:
        tok = m.group(0).replace(",", "")
        if "." in tok:
            left_s, right_s = tok.split(".", 1)
            left_words = number_to_words(int(left_s)) if left_s.isdigit() else left_s
            right_words = " ".join(number_to_words(int(ch)) for ch in right_s if ch.isdigit())
            return f" {left_words} point {right_words} "
        if tok.isdigit():
            val = int(tok)
            if 1100 <= val <= 2099 and val % 100 != 0 and not (2000 <= val <= 2009):
                return f" {year_to_words(val)} "
            return f" {number_to_words(val)} "
        return f" {tok} "

    return re.sub(r"\d+(?:,\d{3})*(?:\.\d+)?", _repl_num, str(raw_text or ""))


def count_english_syllables(text: str) -> int:
    """Estimates spoken English syllable count across a sentence or clip narration."""
    expanded = _expand_digits_for_syllables(str(text or ""))
    total = 0
    for raw_w in expanded.split():
        for sub_w in re.split(r"[-/]", raw_w.lower()):
            w = re.sub(r"[^a-z]", "", sub_w)
            if not w:
                continue
            if len(w) <= 3:
                total += 1
                continue
            w = re.sub(r"(?:es|ed|e)$", "", w)
            groups = re.findall(r"[aeiouy]+", w)
            total += max(1, len(groups))
    return max(1, total)


def compute_clip_target_duration(narration: str, role: str = "") -> dict[str, Any]:
    """
    Dynamically selects '8s' vs '10s' Google Flow (Omni 1.2 Flash) generation duration from spoken syllable density,
    clause pauses, and narrative role so short punchy hooks avoid trailing dead air / prompt bleed
    while dense mechanism explanations never suffer tail speech cut-off.
    """
    clean_narr = str(narration or "").strip()
    wc = count_words(clean_narr)
    syls = count_english_syllables(clean_narr)
    internal_pauses = len(re.findall(r"[,;:—\-]", clean_narr))
    sentence_breaks = max(0, len(re.findall(r"[.!?]", clean_narr)) - 1)
    est_sec = round((syls / 4.5) + (0.18 * internal_pauses) + (0.28 * sentence_breaks) + 0.55, 2)
    is_short_role = role in {"setup", "symptom", "failure", "pivot", ""}
    if is_short_role and wc <= FLOW_SHORT_CLIP_MAX_WORDS and syls <= FLOW_SHORT_CLIP_MAX_SYLLABLES and est_sec <= 6.8:
        target_dur = "8s"
    else:
        target_dur = "10s"
    # Omni 1.2 Flash renders up to CLIP_MAX_RENDER_SEC (10 s) on Frames/no-ingredient (and 3s-15s Ingredients). With a reference image attached
    # Omni locks 8 s, and the Gemini app renders 8 s: native speech must then fit 8 s (see scene_blueprint packets).
    cutoff_risk = bool(syls > FLOW_CLIP_SAFE_MAX_SYLLABLES or est_sec > float(CLIP_MAX_RENDER_SEC) + 0.2)
    return {
        "target_duration": target_dur,
        "word_count": wc,
        "expected_syllables": syls,
        "estimated_speech_sec": est_sec,
        "cutoff_risk": cutoff_risk,
    }


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
    "setup": "reaches across the table to grip the apparatus as the researcher steps closer",
    "symptom": "sweeps its hand across the desk and grips the edge in sudden tension",
    "failure": "pushes the test chart away across the desk and rises from the chair",
    "breakthrough": "lifts the test instrument with steady hands and nods toward the researcher",
    "conclusion": "operates the apparatus with steady hands while the researcher records notes nearby",
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

    environment = _cap_words(vp.get("real_environment") or "a brightly lit clinical examination room", 9)
    props = [_cap_words(p, 4) for p in (vp.get("environment_props") or []) if _clean(p)][:3]
    if not props:
        props = ["examination table", "desk lamp"]
    target = _cap_words(vp.get("target_region") or "prefrontal cortex", 6)
    crisis_region = _cap_words(vp.get("crisis_region") or target, 9)
    compensatory = _cap_words(vp.get("compensatory_region") or "prefrontal cortex", 7)
    path = [_cap_words(p, 4) for p in (vp.get("signal_path") or []) if _clean(p)]
    if len(path) < 2:
        path = ["sensory nerve", "thalamus", target]
    steps = [
        _cap_words(sanitize_prompt_for_flow(s, is_spoken_dialogue=False), 26)
        for s in (vp.get("mechanism_steps") or [])
        if _clean(s)
    ]
    while len(steps) < 3:
        steps.append(
            [
                f"A smooth clear cyan-blue stream flows steadily inside the channel into the {target}",
                f"At the {crisis_region}, the smooth internal stream pools and fades softly against the closed channel edge",
                f"The {compensatory} warms to amber-gold as a steady internal stream glides through the intact channel",
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
    "Bright daylight lighting.",
    "Strong rim light traces the porcelain contours.",
    "Soft volumetric haze hangs in the air.",
    "The rest of the room glows in soft daylight.",
)
_BRAIN_FILLERS = (
    "Strong rim light grazes the folds of the cortex.",
    "Soft studio light traces the internal anatomical channels.",
    "The rest of the brain stays matte white in soft daylight.",
    "Bright daylight lighting.",
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
    joined = " ".join(s for s, _ in sentences)
    if count_words(joined) > PROMPT_SCENE_WORDS_MAX:
        joined = _cap_words(joined, PROMPT_SCENE_WORDS_MAX) + "."
    return joined


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
    return f"A realistic {_strip_article(hw)} rests on the {plan['target_region']}, its fine contacts glowing warm amber-gold."


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
            ("Bright daylight lighting.", "req"),
        ],
        _REAL_ENV_FILLERS,
    )


def _scene_symptom(plan: dict[str, Any]) -> str:
    return _fit_scene(
        [
            (f"Close-up on the {plan['subject']} mannequin's smooth porcelain face as it {plan['mannequin_actions']['symptom']}.", "req"),
            (
                "The camera slowly orbits the head, revealing the brain through the translucent frosted-glass cranium: "
                f"the {plan['target_region']} glows soft cyan-blue while the {plan['crisis_region']} fades to dim crimson-red.",
                "req",
            ),
            (f"Strong rim light traces the porcelain contours; the {plan['environment_short']} glows in daylight.", "req"),
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
            (f"Warm amber light falls on the other figures while the {subj} mannequin sits in soft daylight.", "req"),
        ]
    else:
        props = _join([_the(p) for p in plan["environment_props"][:2]])
        parts = [
            (f"In the same {plan['environment_short']}, the {subj} mannequin {plan['mannequin_actions']['failure']}.", "req"),
            (f"Nearby, {props} stand unused.", "req"),
            ("The camera tracks smoothly sideways past the props toward the lone figure, capturing its isolation.", "req"),
            ("Soft daylight surrounds the porcelain figure while warm light spills across the empty room.", "req"),
        ]
    return _fit_scene(parts, _REAL_ENV_FILLERS)


def _scene_crisis(plan: dict[str, Any]) -> str:
    return _fit_scene(
        [
            (
                f"The camera dives smoothly through the {plan['subject']} mannequin's translucent frosted-glass cranium into a bright "
                "white studio gallery holding an architectural cross-section cutaway of a realistic matte-white brain with visible gyri and sulci.",
                "req",
            ),
            (
                f"It glides into the open cross-section and zooms into the {plan['target_region']} shaded soft cyan-blue alongside the "
                f"{plan['crisis_region']}, which is {plan['crisis_lesion']} and shaded deep crimson-red where the internal channel closes.",
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
                "Inside the architectural cross-section cutaway of the matte-white brain in a bright white studio gallery, the camera smoothly "
                f"orbits the {plan['target_region']} in soft cyan-blue and the {plan['crisis_region']} shaded crimson-red.",
                "req",
            ),
            (
                f"Nearby, the translucent anatomical channels of the {plan['compensatory_region']} warm to amber-gold and open a smooth pathway across the circuit.",
                "req",
            ),
            ("The camera slowly pushes in on the open amber-gold channel.", "req"),
            (_descriptor_sentence(plan, plan["compensatory_region"]), "opt"),
        ],
        _BRAIN_FILLERS,
    )


def _path_sentence(plan: dict[str, Any]) -> str:
    path = plan["signal_path"]
    middle = _join([_the(p) for p in path[1:-1]])
    via = f" through {middle}" if middle else ""
    return f"A smooth clear cyan-blue fluid stream flows steadily inside the translucent channel from the {path[0]}{via} into the {path[-1]}."


def _scene_step(plan: dict[str, Any], role: str) -> str:
    steps = plan["mechanism_steps"]
    if role == "step1":
        parts = [
            ("Macro view inside the translucent channel of the matte-white brain in bright studio daylight.", "req"),
            (_path_sentence(plan), "req"),
            (f"{_cap_first(steps[0])}.", "req"),
            ("The camera tracks smoothly alongside the contained stream inside the channel wall.", "req"),
        ]
    elif role == "step2":
        parts = [
            (
                f"Macro tracking inside the translucent anatomical channel of the matte-white brain in bright studio daylight, following the smooth internal stream from the soft cyan-blue {plan['target_region']}.",
                "req",
            ),
            (f"{_cap_first(steps[1])}.", "req"),
            (_hardware_sentence(plan), "opt"),
            ("The camera slowly orbits the crimson-red channel junction.", "req"),
        ]
    elif role == "step3":
        parts = [
            ("The camera pulls back to reveal the complete circuit inside the architectural cross-section cutaway of the matte-white brain in bright studio daylight.", "req"),
            (
                f"The {plan['target_region']} glows soft cyan-blue, the {plan['crisis_region']} stays crimson-red and the "
                f"{plan['compensatory_region']} channels glow warm amber-gold.",
                "req",
            ),
            (f"{_cap_first(steps[2])}.", "req"),
            ("The cutaway brain turns slowly in the light.", "opt"),
        ]
    else:  # single mechanism clip for 5-7 clip Shorts
        parts = [
            ("Macro view inside the translucent channel of the matte-white cutaway brain in bright studio daylight.", "req"),
            (_path_sentence(plan), "req"),
            (f"{_cap_first(steps[1])}.", "req"),
            (_hardware_sentence(plan), "opt"),
            ("The camera tracks the smooth internal stream, then pulls back to the full circuit.", "req"),
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
                f"Inside its translucent frosted-glass cranium, the {plan['target_region']} glows soft cyan-blue and the "
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
        env = "a brightly lit hospital room"
        props = ["hospital bed", "EKG monitor", "window with open blinds"]
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
        env = "a brightly lit bedroom"
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
        env = "a brightly lit clinical examination room"
        props = ["examination table", "telephone"]
        anchor = "telephone on the table"
        target = "Broca's area"
        crisis = "white-matter tract to Wernicke's area"
        comp = "temporal lobe"
        path = ["auditory nerve", "thalamus", "Wernicke's area", "Broca's area"]
        hw = None
    else:
        env = "a brightly lit clinical laboratory"
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
                f"A smooth clear cyan-blue stream flows steadily inside the channel into the {target} and lights it soft cyan-blue",
                f"At the severed crimson-red {crisis}, the smooth internal stream pools and fades softly against the closed channel edge",
                f"The {comp} warms to amber-gold and guides a steady internal stream smoothly across the intact channel",
            ],
            "anatomy_descriptors": {
                "amygdala": "small almond-shaped nucleus",
                "hippocampus": "curved seahorse-shaped ridge",
            },
            "bci_hardware": hw,
        }
    )


def flow_prompt_prefix(aspect: str = FLOW_ASPECT_SHORTS) -> str:
    """FLOW_PROMPT_PREFIX for the requested aspect (9:16 Shorts default, 16:9 for longform re-generation)."""
    if aspect == FLOW_ASPECT_SHORTS:
        return FLOW_PROMPT_PREFIX
    label = FLOW_ASPECT_LABELS.get(aspect)
    if not label:
        raise ValueError(f"Unsupported aspect '{aspect}' (allowed: {sorted(FLOW_ASPECT_LABELS)})")
    return FLOW_PROMPT_PREFIX.replace(FLOW_ASPECT_LABELS[FLOW_ASPECT_SHORTS], label)


def render_prompt(
    scene: str,
    narration: str,
    voice: str = FLOW_DEFAULT_VOICE,
    aspect: str = FLOW_ASPECT_SHORTS,
    style_suffix: str | None = None,
    voice_label: str | None = None,
) -> str:
    """Renders a single Google Flow Omni 1.2 prompt string (v4 when style_suffix/voice_label are None)."""
    clean_scene = _clean(scene)
    if clean_scene and not clean_scene.endswith("."):
        clean_scene += "."
    if style_suffix:
        suf = _clean(style_suffix)
        if suf and not suf.endswith("."):
            suf += "."
        clean_scene = f"{clean_scene} {suf}"
    clean_narr = str(narration or "").strip().replace('"', "'")
    if voice_label is None:
        from pipeline.config import DIORAMA_VOICE_PRESETS

        v_key = str(voice or "").strip().lower()
        matched_anchor: str | None = None
        if v_key and v_key != FLOW_DEFAULT_VOICE.lower():
            for p_id, spec in DIORAMA_VOICE_PRESETS.items():
                if v_key in (
                    p_id,
                    spec["voice"].lower(),
                    str(spec.get("elevenlabs_voice_id") or "").lower(),
                ):
                    raw_anc = re.sub(r"^Voice:\s*", "", str(spec["flow_voice_anchor"]).strip(), flags=re.IGNORECASE)
                    matched_anchor = raw_anc.rstrip(".")
                    break
        if matched_anchor:
            voice_label = matched_anchor
        else:
            voice_label = FLOW_VOICE_PROMPT_DESCRIPTOR if voice == FLOW_DEFAULT_VOICE else voice
    return f'{flow_prompt_prefix(aspect)} {clean_scene} Voice: {voice_label}. Spoken narration: "{clean_narr}"'


# ==============================================================================
# Prompt System v5: visual-mode routing + shot composer (R45-R47)
# ==============================================================================
def is_diorama_v6_plan(visual_plan: dict[str, Any] | None) -> bool:
    """True when visual_plan selects Schema v6 `neuro_diorama`."""
    return isinstance(visual_plan, dict) and is_diorama_profile(visual_plan)


def is_v5_plan(visual_plan: dict[str, Any] | None) -> bool:
    if is_diorama_v6_plan(visual_plan):
        return False
    return isinstance(visual_plan, dict) and str(visual_plan.get("visual_mode") or "").upper() in VISUAL_MODES


def plan_visual_mode(visual_plan: dict[str, Any] | None) -> str | None:
    return str(visual_plan.get("visual_mode")).upper() if is_v5_plan(visual_plan) else None


def resolve_clip_setting(visual_plan: dict[str, Any] | None, role: str) -> str:
    """v5: shots[role].setting (if valid) > MODE_ROLE_SETTINGS[mode][role]; v4: ROLE_SETTINGS[role]."""
    if not is_v5_plan(visual_plan):
        return ROLE_SETTINGS[role]
    shot = _shot(visual_plan, role)
    setting = str(shot.get("setting") or "").strip()
    if setting in ALLOWED_SETTINGS_V5:
        return setting
    return MODE_ROLE_SETTINGS[plan_visual_mode(visual_plan)][role]


def _shot(visual_plan: dict[str, Any], role: str) -> dict[str, Any]:
    shots = visual_plan.get("shots") if isinstance(visual_plan.get("shots"), dict) else {}
    shot = shots.get(role)
    return shot if isinstance(shot, dict) else {}


def _sentence(text: Any) -> str:
    t = _clean(text)
    if not t:
        return ""
    t = _cap_first(t)
    return t if t.endswith((".", "!", "?")) else t + "."


def compose_shot_scene(visual_plan: dict[str, Any], role: str) -> str:
    """
    Action-Physics composer (R47): [camera] + [environment/era] + [body verb action] + [prop physical change]
    + [body-language reaction]. Used when visual_plan.scenes[role] is absent but shots[role] is authored.
    """
    shot = _shot(visual_plan, role)
    parts = [
        _sentence(shot.get("camera")),
        _sentence(shot.get("environment") or ""),
        _sentence(shot.get("action")),
        _sentence(shot.get("prop_change")),
        _sentence(shot.get("reaction")),
        _sentence(shot.get("detail") or ""),
    ]
    return " ".join(p for p in parts if p)


def _v4_template_for_setting(setting: str, role: str, plan: dict[str, Any]) -> str:
    """Brain-setting fallback for v5 HYBRID / NEURO plans that keep v4 region fields."""
    if setting == "drill_down":
        return sanitize_prompt_for_flow(_scene_crisis(plan))
    if setting == "pull_out":
        return sanitize_prompt_for_flow(_scene_breakthrough(plan))
    if role in ("mechanism", "step1", "step2", "step3", "pivot"):
        return compose_scene(role, plan)
    return sanitize_prompt_for_flow(_scene_pivot(plan))


def _compose_diorama_clip_scene(clip_spec: dict[str, Any], motif_prop: dict[str, Any] | None = None) -> str:
    """Composes a Schema v6 `neuro_diorama` scene body from structured fields or an explicit `scene` string."""
    from pipeline.depiction_rules import (
        ArchitecturalBrainMaquetteRule,
        CrystalSpecimenRule,
        DioramaCutawayRule,
        KineticTracePropRule,
        LiteralAnalogyCutawayRule,
        SensorMotifRule,
        TactileTokenGridRule,
    )

    if str(clip_spec.get("scene") or "").strip():
        return str(clip_spec["scene"]).strip()
    grammar = str(clip_spec.get("grammar") or "arch_cutaway_diorama").strip()
    if grammar == "arch_cutaway_diorama":
        return DioramaCutawayRule.compose(
            environment=str(clip_spec.get("environment") or "a historical laboratory chamber"),
            kinetic_action=str(clip_spec.get("kinetic_action") or "mechanical doors seal and analog instruments activate"),
            lighting=str(clip_spec.get("lighting") or "warm directional sunlight"),
            camera_move=str(clip_spec.get("camera") or "isometric_push_in"),
        )
    if grammar == "kinetic_trace_automata":
        return KineticTracePropRule.compose(
            prop_setup=str(clip_spec.get("prop_setup") or "vintage brass laboratory switches on an oak desk"),
            self_actuating_motion=str(clip_spec.get("self_actuating_motion") or "metal toggle switches snap downward one by one"),
            physical_consequence=str(clip_spec.get("physical_consequence") or "red indicator lamps illuminate across the panel"),
        )
    if grammar == "recurring_gauge_motif":
        default_obj = str((motif_prop or {}).get("object") or "a clear glass of water beside a brass gauge")
        return SensorMotifRule.compose(
            motif_object=str(clip_spec.get("motif_object") or default_obj),
            state_transition=str(clip_spec.get("state_transition") or "concentric ripples spread across the water surface"),
        )
    if grammar == "tactile_token_grid":
        return TactileTokenGridRule.compose(
            token_layout=str(clip_spec.get("token_layout") or "forty turned-oak cylinders arranged in a grid"),
            ratio_animation=str(clip_spec.get("ratio_animation") or "twenty-six cylinders illuminate with warm amber light"),
        )
    if grammar == "literal_analogy_cutaway":
        return LiteralAnalogyCutawayRule.compose(
            analogy_scene=str(clip_spec.get("analogy_scene") or clip_spec.get("token_layout") or "a lush green-turf football stadium field miniature with crisp white yard lines"),
            comparison_motion=str(clip_spec.get("comparison_motion") or clip_spec.get("ratio_animation") or "a glowing amber trajectory arc spans cleanly across the first quarter of the field"),
            camera_move=str(clip_spec.get("camera") or "orbital_3d_arc_sweep"),
        )
    if grammar == "arch_brain_maquette":
        return ArchitecturalBrainMaquetteRule.compose(
            str(
                clip_spec.get("maquette_scene")
                or "localized soft cyan-blue subsurface glow illuminates the prefrontal cortex brightest along the recessed sulcal grooves"
            ),
            brain_mode=str(clip_spec.get("brain_mode") or "auto"),
        )
    if grammar == "frosted_crystal_specimen":
        return CrystalSpecimenRule.compose(
            specimen_kind=str(clip_spec.get("specimen_kind") or "human head bust"),
            mount_detail=str(clip_spec.get("mount_detail") or "a dark-oak and brushed-brass museum plinth"),
            trajectory_or_neural_action=str(
                clip_spec.get("trajectory_action")
                or "muted crimson-red luminance dims smoothly inside the translucent prefrontal cortex"
            ),
        )
    return str(clip_spec.get("scene") or "").strip()


def _compose_porcelain_v7_clip_scene(clip_spec: dict[str, Any]) -> str:
    """Composes a Schema v7 `porcelain_cinematic_v7` high-key porcelain & contained 4-color 3D brain scene body (R66)."""
    from pipeline.depiction_rules import (
        ContainedLiving3DBrainRule,
        PorcelainCutawaySectionRule,
        PorcelainHandsActionRule,
        PorcelainLiteralAnalogyRule,
        PorcelainWorldRule,
        normalize_porcelain_v7_grammar,
    )

    if str(clip_spec.get("scene") or "").strip():
        return str(clip_spec["scene"]).strip()
    grammar = normalize_porcelain_v7_grammar(clip_spec.get("grammar") or clip_spec.get("visual_grammar") or "porcelain_fullbleed_world")
    if grammar == "porcelain_hands_closeup":
        return PorcelainHandsActionRule.compose(
            attire_and_hands=str(clip_spec.get("attire_and_hands") or "crisp rolled linen cuffs and smooth matte-white ball-jointed porcelain hands"),
            prop_action=str(clip_spec.get("prop_action") or "the porcelain hands grip and position a precision brushed-steel tool"),
            consequence=str(clip_spec.get("consequence") or "the mechanism shifts cleanly into alignment"),
            pov=False,
        )
    if grammar == "porcelain_pov_hands":
        return PorcelainHandsActionRule.compose(
            attire_and_hands=str(clip_spec.get("attire_and_hands") or "tailored coat cuffs extending from bottom frame"),
            prop_action=str(clip_spec.get("prop_action") or "both porcelain hands guide the tactile instrument steadily"),
            consequence=str(clip_spec.get("consequence") or "the mechanism tracks smoothly along the workbench"),
            pov=True,
        )
    if grammar == "porcelain_cutaway_section":
        return PorcelainCutawaySectionRule.compose(
            structure=str(clip_spec.get("structure") or clip_spec.get("environment") or "a grey granite bedrock trench"),
            internal_mechanism=str(clip_spec.get("internal_mechanism") or clip_spec.get("kinetic_action") or "an iron tamping rod descends into the vertical borehole"),
        )
    if grammar == "porcelain_literal_analogy":
        return PorcelainLiteralAnalogyRule.compose(
            analogy_world=str(clip_spec.get("analogy_world") or clip_spec.get("analogy_scene") or "a bright sunlit green-turf stadium field with crisp turf stripes"),
            comparison_action=str(clip_spec.get("comparison_action") or clip_spec.get("comparison_motion") or "a solid iron rod arcs cleanly across one quarter of the green field"),
        )
    if grammar == "porcelain_living_brain":
        raw_bscene = str(clip_spec.get("brain_scene") or clip_spec.get("maquette_scene") or "").strip()
        return ContainedLiving3DBrainRule.compose(
            brain_scene=raw_bscene or None,
            brain_mode=str(clip_spec.get("brain_mode") or clip_spec.get("render_mode") or "cortical_vascular_whole"),
            brain_region=clip_spec.get("brain_region"),
            active_hub=clip_spec.get("active_hub"),
            lesion_or_deficit=clip_spec.get("lesion_or_deficit"),
            fluid_or_signal_flow=clip_spec.get("fluid_or_signal_flow"),
        )
    return PorcelainWorldRule.compose(
        environment=str(clip_spec.get("environment") or "a bright sunlit clinical research studio with tall glass windows"),
        action=str(
            clip_spec.get("action")
            or clip_spec.get("kinetic_action")
            or "clothed matte-white porcelain researchers with smooth featureless solid matte-white egg-shaped oval heads inspect a precision instrument"
        ),
        lighting=str(clip_spec.get("lighting") or "soft bright studio daylight with crisp rim light"),
    )


def _compose_diorama_v7_clip_scene(clip_spec: dict[str, Any], style_profile: str | None = None) -> str:
    """Composes a Schema v7 (`porcelain_cinematic_v7` or `lowpoly_pastel_v7`) scene body (R63/R66)."""
    if is_porcelain_v7_plan(style_profile) or is_porcelain_v7_plan(clip_spec):
        return _compose_porcelain_v7_clip_scene(clip_spec)
    from pipeline.depiction_rules import (
        LowPolyCutawaySectionRule,
        LowPolyHandsActionRule,
        LowPolyLiteralAnalogyRule,
        LowPolyWorldRule,
        MatteArchitecturalBrainRule,
    )

    if str(clip_spec.get("scene") or "").strip():
        return str(clip_spec["scene"]).strip()
    grammar = str(clip_spec.get("grammar") or clip_spec.get("visual_grammar") or "lowpoly_fullbleed_world").strip()
    if grammar == "lowpoly_hands_closeup":
        return LowPolyHandsActionRule.compose(
            attire_and_hands=str(clip_spec.get("attire_and_hands") or "rolled canvas work sleeves and geometric matte hands"),
            prop_action=str(clip_spec.get("prop_action") or "the geometric hands grip and position a solid metal tool"),
            consequence=str(clip_spec.get("consequence") or "the mechanism shifts cleanly into alignment"),
            pov=False,
        )
    if grammar == "lowpoly_pov_hands":
        return LowPolyHandsActionRule.compose(
            attire_and_hands=str(clip_spec.get("attire_and_hands") or "tan canvas coat sleeves extending from bottom frame"),
            prop_action=str(clip_spec.get("prop_action") or "both low-poly hands pull taut leather reins firmly"),
            consequence=str(clip_spec.get("consequence") or "the wooden carriage wheels track smoothly along the road"),
            pov=True,
        )
    if grammar == "lowpoly_cutaway_section":
        return LowPolyCutawaySectionRule.compose(
            structure=str(clip_spec.get("structure") or clip_spec.get("environment") or "a grey granite bedrock trench"),
            internal_mechanism=str(clip_spec.get("internal_mechanism") or clip_spec.get("kinetic_action") or "an iron tamping rod descends into the vertical borehole"),
        )
    if grammar == "lowpoly_literal_analogy":
        return LowPolyLiteralAnalogyRule.compose(
            analogy_world=str(clip_spec.get("analogy_world") or clip_spec.get("analogy_scene") or "a bright sunlit green-turf football stadium field with crisp yard stripes"),
            comparison_action=str(clip_spec.get("comparison_action") or clip_spec.get("comparison_motion") or "a solid iron rod arcs cleanly across one quarter of the green field"),
        )
    if grammar == "lowpoly_matte_brain":
        return MatteArchitecturalBrainRule.compose(
            brain_scene=str(clip_spec.get("brain_scene") or clip_spec.get("maquette_scene") or "muted terracotta-coral shading marks the left prefrontal cortex while slate-blue cortical pathways stay intact"),
            brain_mode=str(clip_spec.get("brain_mode") or "matte_pastel_cortical_model"),
        )
    return LowPolyWorldRule.compose(
        environment=str(clip_spec.get("environment") or "a sunlit Vermont grey granite railroad cut with pine hills"),
        action=str(clip_spec.get("action") or clip_spec.get("kinetic_action") or "clothed low-poly rail workers in flat caps drill into solid granite"),
        lighting=str(clip_spec.get("lighting") or "soft bright diffused pastel daylight"),
    )


def _compose_expressive_v8_clip_scene(clip_spec: dict[str, Any]) -> str:
    """Composes a Schema v8 `expressive_25d_v8` 2.5D vinyl + 2D ink expression + 75% X-Ray + Mini-Cortex cameo scene body (R68)."""
    from pipeline.depiction_rules import (
        ExpressiveCameoWorldRule,
        ExpressiveHandsActionRule,
        ExpressiveLiteralAnalogyRule,
        ExpressiveReactionCloseupRule,
        ExpressiveRigidPhysicsRule,
        ExpressiveVinylWorldRule,
        ExpressiveXRayBrainRule,
        SceneDepictionRule,
        format_expression_acting_clause,
        normalize_expressive_v8_grammar,
    )

    cameo_flag = bool(clip_spec.get("cameo_easter_egg")) or str(clip_spec.get("grammar") or "") == "expressive_cameo_world"
    allow_list = [str(t).strip() for t in (clip_spec.get("diegetic_text_allowlist") or ()) if str(t).strip()][:2]
    expr_id = str(clip_spec.get("expression_id") or "").strip()
    speaker_role = str(clip_spec.get("speaker_role") or clip_spec.get("voice_role") or "").strip()
    rigid_grammar = str(clip_spec.get("rigid_physics_grammar") or clip_spec.get("physics_grammar") or "").strip()
    explicit_scene = str(clip_spec.get("scene") or "").strip()
    if explicit_scene:
        out = SceneDepictionRule.clean_clause(explicit_scene)
        low_out = out.lower()
        if allow_list and not all(tok.lower() in low_out for tok in allow_list):
            quoted = ", ".join(f"'{tok}'" for tok in allow_list)
            out = f"{out.rstrip('.')}. Crisp physical prop stencil displays {quoted} only."
        if cameo_flag and "mini-cortex" not in low_out:
            cameo_note = SceneDepictionRule.clean_clause(
                str(
                    clip_spec.get("cameo_placement")
                    or "a tiny 4cm glowing 4-color translucent vinyl Mini-Cortex figurine sits quietly on the background shelf"
                )
            )
            out = f"{out.rstrip('.')}. {cameo_note[:1].upper() + cameo_note[1:]}."
        return out

    def _compose_cast_action_beat(default_action: str, *, include_cast: bool = True) -> str:
        cast_txt = SceneDepictionRule.clean_clause(str(clip_spec.get("cast") or "")) if include_cast else ""
        act_txt = SceneDepictionRule.clean_clause(
            str(
                clip_spec.get("action")
                or clip_spec.get("kinetic_action")
                or clip_spec.get("character_reaction")
                or clip_spec.get("comparison_action")
                or clip_spec.get("comparison_motion")
                or clip_spec.get("prop_action")
                or ""
            )
        )
        cons_txt = SceneDepictionRule.clean_clause(str(clip_spec.get("consequence") or ""))
        if not act_txt and expr_id:
            act_txt = format_expression_acting_clause(expr_id, speaker_role=speaker_role, compact=False)
        if not act_txt and not cast_txt and not cons_txt:
            return default_action
        base = act_txt or default_action
        if cast_txt and cast_txt.lower() not in base.lower():
            if base[:1].islower() and not base.lower().startswith(("the ", "a ", "an ", "one ", "two ", "both ", "inside ")):
                base = f"{cast_txt} {base}"
            else:
                base = f"{cast_txt}: {base}"
        if cons_txt and cons_txt.lower() not in base.lower():
            base = f"{base.rstrip('.')}, and {cons_txt[:1].lower() + cons_txt[1:]}"
        return base

    lighting_map = {
        "night_3am": "dramatic low-key 3 AM bedside chiaroscuro with warm amber brass rim-light and cool moonlight shadows",
        "night_interior": "warm nighttime interior key-and-rim cinema lighting with soft amber practical glow",
        "studio_cinema": "warm cinematic key-and-rim studio lighting",
    }
    raw_lmode = str(clip_spec.get("lighting_mode") or "").strip().lower()
    act_hint_key = (
        clip_spec.get("act_index")
        if clip_spec.get("act_index") is not None
        else (clip_spec.get("act") or clip_spec.get("act_role") or clip_spec.get("narrative_act"))
    )
    resolved_lighting = str(
        clip_spec.get("lighting")
        or lighting_map.get(raw_lmode)
        or (resolve_act_lighting_hint(act_hint_key) if act_hint_key is not None and str(act_hint_key).strip() else "")
        or "warm cinematic key-and-rim studio lighting"
    )

    grammar = normalize_expressive_v8_grammar(
        clip_spec.get("grammar") or clip_spec.get("visual_grammar") or "expressive_vinyl_world",
        cameo_easter_egg=cameo_flag,
    )
    if rigid_grammar in EXPRESSIVE_V8_RIGID_PHYSICS_GRAMMARS:
        return ExpressiveRigidPhysicsRule.compose(
            rigid_grammar,
            subject=str(clip_spec.get("cast") or clip_spec.get("subject") or "2.5D figure"),
            action=str(clip_spec.get("action") or clip_spec.get("prop_action") or ""),
            compact=False,
        )
    if grammar == "expressive_reaction_closeup":
        return ExpressiveReactionCloseupRule.compose(
            expression_id=(expr_id or "question_brow_raise"),
            character_desc=str(clip_spec.get("cast") or "clothed 2.5D matte cream-white vinyl character"),
            environment=str(clip_spec.get("environment") or "a softly lit 3D miniature room"),
            speaker_role=speaker_role,
            action=str(clip_spec.get("action") or ""),
            prop_detail=str(clip_spec.get("prop_action") or clip_spec.get("consequence") or ""),
            compact=False,
        )
    if grammar == "expressive_hands_closeup":
        return ExpressiveHandsActionRule.compose(
            attire_and_hands=str(
                clip_spec.get("attire_and_hands")
                or clip_spec.get("cast")
                or "soft cotton pajama cuffs and smooth matte cream-white four-fingered vinyl hands"
            ),
            prop_action=str(
                clip_spec.get("prop_action")
                or clip_spec.get("action")
                or "the vinyl fingers tap and adjust a bedside clock"
            ),
            consequence=str(clip_spec.get("consequence") or "the crisp indicator shifts cleanly across the dial"),
            pov=False,
            diegetic_text_allowlist=allow_list,
        )
    if grammar == "expressive_pov_hands":
        return ExpressiveHandsActionRule.compose(
            attire_and_hands=str(
                clip_spec.get("attire_and_hands")
                or clip_spec.get("cast")
                or "tailored cloth sleeves extending from bottom frame"
            ),
            prop_action=str(
                clip_spec.get("prop_action")
                or clip_spec.get("action")
                or "both four-fingered matte cream-white vinyl hands grip the prop steadily"
            ),
            consequence=str(clip_spec.get("consequence") or "the physical mechanism locks cleanly into place"),
            pov=True,
            diegetic_text_allowlist=allow_list,
        )
    if grammar == "expressive_literal_analogy":
        return ExpressiveLiteralAnalogyRule.compose(
            analogy_world=str(
                clip_spec.get("analogy_world")
                or clip_spec.get("analogy_scene")
                or clip_spec.get("environment")
                or "a quiet nighttime hotel corridor security desk"
            ),
            comparison_action=_compose_cast_action_beat(
                "one clothed 2.5D matte cream-white vinyl night-watch guard shines a warm brass flashlight beam down the dark hall while its partner sleeps"
            ),
            lighting=str(clip_spec.get("lighting") or lighting_map.get(raw_lmode) or "dramatic warm key-and-rim cinema lighting"),
        )
    if grammar == "brain_simulator_3d":
        s_reg = SceneDepictionRule.clean_clause(str(clip_spec.get("start_brain_region") or clip_spec.get("brain_region") or "fusiform face area"))
        e_reg = SceneDepictionRule.clean_clause(str(clip_spec.get("end_brain_region") or s_reg))
        n_state = str(clip_spec.get("neural_state") or "active").strip().lower()
        return (
            f"Deterministic Blender 4.2 MNI152 3D clinical brain simulator view over dark studio slate showing a translucent human head shell, "
            f"bilateral cortex, cerebellum, and brainstem with spotlighted matte anatomical structures linking {s_reg} to {e_reg} "
            f"in '{n_state}' pathway state under steady medical drone framing and crisp cavity depth cues."
        )
    if grammar == "expressive_xray_brain":
        return ExpressiveXRayBrainRule.compose(
            brain_scene=str(clip_spec.get("brain_scene") or clip_spec.get("maquette_scene") or "").strip() or None,
            environment=str(clip_spec.get("environment") or "a dimly lit unfamiliar hotel bedroom"),
            character_reaction=str(
                clip_spec.get("character_reaction")
                or _compose_cast_action_beat(
                    "the smooth featureless matte-white architectural porcelain sleeper turns toward the pillow in three-quarter silhouette",
                    include_cast=False,
                )
            ),
            brain_region=clip_spec.get("brain_region"),
        )
    if grammar == "expressive_cameo_world":
        return ExpressiveCameoWorldRule.compose(
            environment=str(clip_spec.get("environment") or "a cozy miniature bedroom with a wooden nightstand"),
            action=_compose_cast_action_beat(
                "a clothed smooth featureless matte-white architectural porcelain figure in three-quarter silhouette turns toward the bedside lamp"
            ),
            cameo_placement=str(
                clip_spec.get("cameo_placement")
                or "a tiny 4cm glowing 4-color translucent vinyl Mini-Cortex figurine sits quietly on the background nightstand shelf"
            ),
            lighting=resolved_lighting,
            diegetic_text_allowlist=allow_list,
        )
    if grammar == "expressive_split_contrast":
        return ExpressiveVinylWorldRule.compose(
            environment=str(
                clip_spec.get("environment")
                or "a split-contrast 3D miniature stage dividing opposing left and right lighting zones"
            ),
            action=_compose_cast_action_beat(
                "two clothed smooth featureless matte-white architectural porcelain figures in back or three-quarter silhouette gesture in opposing left-and-right room zones"
            ),
            lighting=resolved_lighting,
            diegetic_text_allowlist=allow_list,
        )
    return ExpressiveVinylWorldRule.compose(
        environment=str(clip_spec.get("environment") or "a stylized 3D miniature bedroom with crisp woven bedding"),
        action=_compose_cast_action_beat(
            "a clothed smooth featureless matte-white architectural porcelain figure in three-quarter silhouette reacts briskly with four-fingered porcelain hands"
        ),
        lighting=resolved_lighting,
        diegetic_text_allowlist=allow_list,
    )


def _strip_v8_context_split_boilerplate(raw_text: str) -> str:
    """Strips repeated world/lighting/optics/material boilerplate from image-conditioned R68 context-split clips."""
    from pipeline.depiction_rules import (
        EXPRESSIVE_V8_OPTICS_TAIL,
        EXPRESSIVE_V8_WORLD_LEAD,
        EXPRESSIVE_V8_XRAY_OPTICS_TAIL,
    )

    s = str(raw_text or "")
    for boiler in (EXPRESSIVE_V8_WORLD_LEAD, EXPRESSIVE_V8_OPTICS_TAIL, EXPRESSIVE_V8_XRAY_OPTICS_TAIL):
        s = re.sub(re.escape(boiler), " ", s, flags=re.IGNORECASE)
    s = re.sub(
        r"stylized\s+3d\s+cinematic\s+miniature\s+diorama\s+filling[^.:]*[.:]?",
        " ",
        s,
        flags=re.IGNORECASE,
    )
    s = re.sub(
        r",?\s*staged\s+as\s+clothed\s+2\.5d\s+matte\s+cream-white\s+vinyl\s+figures?\s+with\s+smooth\s+earless\s+hairless\s+noseless\s+oval\s+heads?[^.]*",
        "",
        s,
        flags=re.IGNORECASE,
    )
    s = re.sub(r"crisp\s+cinema\s+prime\s+lens\s+clarity[^.]*\.?", " ", s, flags=re.IGNORECASE)
    s = re.sub(r"^\s*:\s*(?:full-bleed\s+view\s+of\s+[^.]+\.\s*)?", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\bclothed\s+2\.5d\s+matte\s+cream-white\s+vinyl\b", "2.5D", s, flags=re.IGNORECASE)
    s = re.sub(r"\bsmooth\s+matte\s+cream-white\s+four-fingered\s+vinyl\s+hands\b", "four-fingered hands", s, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", s).strip(" .,:;")


def _compress_v8_delta_cast_subject(cast_clean: str) -> str:
    """Compresses static start-frame cast descriptions to <=8-word Delta-Only actor identifiers for VIDEO_FRAMES."""
    c = str(cast_clean or "").strip()
    for tail_sep in (
        " with a smooth ",
        " with smooth ",
        " with matte ",
        " with bold ",
        " seated on ",
        " seated at ",
        " seated in ",
        " seated inside ",
        " seated across ",
        " standing in ",
        " standing at ",
        " standing beside ",
        " across from ",
        " beside ",
        " facing ",
    ):
        low_c = c.lower()
        if tail_sep in low_c:
            c = c[: low_c.index(tail_sep)].strip(" ,.;:")
    words = c.split()
    if len(words) > 9:
        c = " ".join(words[:9]).rstrip(" ,.;:")
    return c


def _prepend_concise_cast_subject(act_clause: str, cast_raw: str, grammar: str, camera_move: str = "") -> str:
    """
    Ensures context-split human action clauses always open with an explicit concise cast subject
    instead of subjectless verb fragments (Rule R79-M), while eliminating duplicate 'first the 2.5D...'
    subject collisions and verbose static attire re-description (Rule R82 Veo 3.1 Delta-Only).
    """
    from pipeline.config import EXPRESSIVE_V8_DRONE_CAMERA_MOVES
    from pipeline.depiction_rules import SceneDepictionRule, _PORCELAIN_V7_ACTOR_NOUN_RE

    act = str(act_clause or "").strip()
    if not act:
        return act
    # Strip redundant leading 'First,' / 'First ' before an explicit subject phrase
    act = re.sub(
        r"^first\s*,?\s+(?=(?:the|a|an|two|both|three|2\.5d|doctor|neurologist|clinician|researcher|pharmacist|patient|woman|man|subject|four-fingered)\b)",
        "",
        act,
        flags=re.IGNORECASE,
    ).strip()
    if act:
        act = act[:1].upper() + act[1:]
    cam_k = str(camera_move or "").strip().lower()
    if grammar in ("brain_simulator_3d", "architectural_cutaway_portal", "spatial_3d_arrow_diorama") or cam_k in EXPRESSIVE_V8_DRONE_CAMERA_MOVES:
        return act
    if (
        re.match(
            r"^(?:the|a|an|two|both|three|young|older|female|male|clothed|2\.5d|"
            r"doctor|dr\.|neurologist|clinician|researcher|pharmacist|mother|father|son|daughter|woman|man|patient|subject|figure|protagonist|four-fingered)\b",
            act,
            flags=re.IGNORECASE,
        )
        or "2.5d" in act[:68].lower()
        or bool(_PORCELAIN_V7_ACTOR_NOUN_RE.search(act[:68]))
    ):
        return act
    c_clean = _strip_v8_context_split_boilerplate(SceneDepictionRule.clean_clause(cast_raw))
    if not c_clean:
        return f"The 2.5D character {act[:1].lower() + act[1:]}"
    c_clean = re.sub(r"^(?:a|an|the)\s+2\.5d\s+", "The 2.5D ", c_clean, flags=re.IGNORECASE)
    c_clean = re.sub(r"^2\.5d\s+", "The 2.5D ", c_clean, flags=re.IGNORECASE)
    if not re.match(r"^(?:the|a|an|two|both|three)\b", c_clean, flags=re.IGNORECASE):
        c_clean = f"The {c_clean}"
    c_clean = _compress_v8_delta_cast_subject(c_clean)
    return f"{c_clean} {act[:1].lower() + act[1:]}"


def _compose_expressive_v8_context_split_scene(clip_spec: dict[str, Any]) -> str:
    """
    Previs Rule ③ Context-Splitting (`맥락 나누기`):
    When `VIDEO_FRAMES` or `VIDEO_REFERENCES` images already supply character appearance, room architecture,
    and lighting, emit ONLY subject physical action + 2D expression/hand detail + mandatory reveal/cameo anchors.
    """
    from pipeline.depiction_rules import (
        ExpressiveReactionCloseupRule,
        ExpressiveRigidPhysicsRule,
        SceneDepictionRule,
        format_expression_acting_clause,
        normalize_expressive_v8_grammar,
    )

    cameo_flag = bool(clip_spec.get("cameo_easter_egg")) or str(clip_spec.get("grammar") or "") == "expressive_cameo_world"
    allow_list = [str(t).strip() for t in (clip_spec.get("diegetic_text_allowlist") or ()) if str(t).strip()][:2]
    expr_id = str(clip_spec.get("expression_id") or "").strip()
    speaker_role = str(clip_spec.get("speaker_role") or clip_spec.get("voice_role") or "").strip()
    rigid_grammar = str(clip_spec.get("rigid_physics_grammar") or clip_spec.get("physics_grammar") or "").strip()
    grammar = normalize_expressive_v8_grammar(
        clip_spec.get("grammar") or clip_spec.get("visual_grammar") or "expressive_vinyl_world",
        cameo_easter_egg=cameo_flag,
    )
    explicit_scene = str(clip_spec.get("scene") or "").strip()
    if explicit_scene:
        base = _strip_v8_context_split_boilerplate(SceneDepictionRule.clean_clause(explicit_scene))
    elif rigid_grammar in EXPRESSIVE_V8_RIGID_PHYSICS_GRAMMARS:
        base = _strip_v8_context_split_boilerplate(
            ExpressiveRigidPhysicsRule.compose(
                rigid_grammar,
                subject=str(clip_spec.get("cast") or clip_spec.get("subject") or "Subject"),
                action=str(clip_spec.get("action") or clip_spec.get("prop_action") or ""),
                compact=True,
            )
        )
    elif grammar == "expressive_reaction_closeup":
        base = _strip_v8_context_split_boilerplate(
            ExpressiveReactionCloseupRule.compose(
                expression_id=(expr_id or "curious_head_tilt_perk"),
                character_desc=str(clip_spec.get("cast") or "Subject"),
                environment=str(clip_spec.get("environment") or "a softly lit room"),
                speaker_role=speaker_role,
                action=str(clip_spec.get("action") or ""),
                prop_detail=str(clip_spec.get("prop_action") or ""),
                compact=True,
            )
        )
    elif grammar == "expressive_xray_brain":
        from pipeline.anatomy_map import build_neural_state_clip_clause
        from pipeline.config import EXPRESSIVE_V8_NEURAL_DIVE_MOVES

        cam_mv_cs = str(clip_spec.get("camera_move") or clip_spec.get("camera") or "").strip().lower()
        ns_cs = str(clip_spec.get("neural_state") or "active").strip().lower()
        if ns_cs not in ("active", "silenced", "severed", "rerouted"):
            ns_cs = "active"
        reg = SceneDepictionRule.clean_clause(str(clip_spec.get("brain_region") or "hippocampus"))
        end_reg_raw = str(clip_spec.get("end_brain_region") or "").strip()
        is_r85_brain_cs = bool(clip_spec.get("r85_brain_clip") or clip_spec.get("r85_shot_scale") or clip_spec.get("r85_mode"))
        if ns_cs in ("silenced", "severed", "rerouted") and not clip_spec.get("brain_scene"):
            state_clause = build_neural_state_clip_clause(reg, neural_state=ns_cs, end_region=end_reg_raw or None)
            if is_r85_brain_cs:
                state_clause = (
                    state_clause.replace("glowing", "solid matte")
                    .replace("luminous", "opaque")
                    .replace("glows", "shades")
                    .replace("glow", "matte color")
                )
                base = f"Inside the matte silver-white sculpted gypsum 3D brain cutaway, {state_clause[:1].lower() + state_clause[1:]}"
            else:
                base = f"Inside the translucent frosted-glass 3D brain, {state_clause[:1].lower() + state_clause[1:]}"
        else:
            default_b_sc = (
                "short opaque amber-gold segments move cleanly through thick sky-blue branching surface vessel tubes"
                if is_r85_brain_cs
                else "cool sapphire-blue and amber-gold pulses fire inside enclosed 3D brain pathways"
            )
            b_sc = _strip_v8_context_split_boilerplate(
                SceneDepictionRule.clean_clause(str(clip_spec.get("brain_scene") or default_b_sc))
            )
            if cam_mv_cs in EXPRESSIVE_V8_NEURAL_DIVE_MOVES or bool(clip_spec.get("neural_dive_relay")):
                if is_r85_brain_cs:
                    end_reg = SceneDepictionRule.clean_clause(str(end_reg_raw or "prefrontal cortex"))
                    if cam_mv_cs == "neural_fpv_dive_in":
                        base = f"Matte silver-white sculpted gypsum 3D brain parts along sulcal grooves until the solid matte-shaded {reg} fills center frame as {b_sc}"
                    elif cam_mv_cs == "neural_fpv_pullback_out":
                        base = f"Solid matte-shaded {reg} recedes behind matte silver-white cortical gyri into the full 3D brain cutaway while {b_sc}"
                    elif cam_mv_cs == "neural_tract_relay_flight":
                        base = f"Inside the matte silver-white 3D brain cutaway, opaque tract tubes carry short solid segments from {reg} into {end_reg} as {b_sc}"
                    else:
                        base = f"Inside the matte silver-white 3D brain cutaway, the sculpted {reg} holds solid matte color as {b_sc}"
                elif cam_mv_cs == "neural_fpv_dive_in":
                    base = (
                        f"Translucent frosted-glass 3D brain parts cleanly along crystal-glass cortical folds until the glowing optical-glass {reg} "
                        f"fills the center frame as {b_sc}"
                    )
                elif cam_mv_cs == "neural_fpv_pullback_out":
                    base = (
                        f"Glowing optical-glass {reg} recedes cleanly behind parted crystal-glass cortical ribs into the full translucent frosted-glass 3D brain "
                        f"while {b_sc}"
                    )
                elif cam_mv_cs == "neural_tract_relay_flight":
                    end_reg = SceneDepictionRule.clean_clause(str(end_reg_raw or "prefrontal cortex"))
                    base = (
                        f"Inside the translucent frosted-glass 3D brain, luminous optical-glass tracts carry pulses from {reg} straight into {end_reg} "
                        f"as {b_sc}"
                    )
                else:
                    base = (
                        f"Inside the translucent frosted-glass 3D brain chamber, the giant sculpted optical-glass {reg} pulses crisply "
                        f"as {b_sc}"
                    )
            else:
                react = _strip_v8_context_split_boilerplate(
                    SceneDepictionRule.clean_clause(
                        str(
                            clip_spec.get("character_reaction")
                            or clip_spec.get("action")
                            or (format_expression_acting_clause(expr_id, speaker_role=speaker_role, compact=True) if expr_id else "")
                            or "Subject leans calmly in three-quarter silhouette"
                        )
                    )
                )
                reg_tail = f" across {reg}" if clip_spec.get("brain_region") else ""
                if is_r85_brain_cs:
                    base = (
                        f"{react} across the matte silver-white sculpted gypsum 3D brain cutaway with thick sky-blue branching surface vessel tubes{reg_tail}; "
                        f"{b_sc}"
                    )
                else:
                    base = (
                        f"{react} as isolated semi-transparent frosted-glass 3D human brain reveals glowing internal neural tracts{reg_tail}; "
                        f"{b_sc}"
                    )
    elif grammar == "spatial_3d_arrow_diorama":
        from pipeline.arrow_guide import build_r80_flow_scene_clause

        if clip_spec.get("spatial_arrow_eligible") is False:
            raise ValueError(
                "R87-A forbids spatial_3d_arrow_diorama when spatial_arrow_eligible is False"
            )
        raw_sp_act = str(clip_spec.get("action") or "").strip()
        if raw_sp_act:
            base = _strip_v8_context_split_boilerplate(SceneDepictionRule.clean_clause(raw_sp_act))
        else:
            cam_sp = str(clip_spec.get("camera_move") or clip_spec.get("camera") or "").strip().lower()
            phase_sp = "landmark_ascend" if cam_sp == "drone_landmark_ascend" else "topdown_arrow"
            base = build_r80_flow_scene_clause(
                str(clip_spec.get("arrow_3d_mode") or "adaptive_landmark_zigzag"),
                cut_phase=phase_sp,
                landmark_desc=str(clip_spec.get("environment") or ""),
                vehicle_or_actor_desc=str(clip_spec.get("cast") or ""),
                anchor_prop_a=str(clip_spec.get("anchor_prop_a") or ""),
                anchor_prop_b=str(clip_spec.get("anchor_prop_b") or ""),
            )
    elif grammar in ("expressive_hands_closeup", "expressive_pov_hands"):
        p_act = _strip_v8_context_split_boilerplate(
            SceneDepictionRule.clean_clause(
                str(clip_spec.get("prop_action") or clip_spec.get("action") or "Four-fingered hands grip and shift the physical prop")
            )
        )
        cons = _strip_v8_context_split_boilerplate(
            SceneDepictionRule.clean_clause(
                str(clip_spec.get("consequence") or "the tactile mechanism clicks cleanly into alignment")
            )
        )
        pov_lead = "First-person POV: " if grammar == "expressive_pov_hands" else "Tight hand close-up: "
        base = f"{pov_lead}{p_act}, and {cons[:1].lower() + cons[1:]}"
    else:
        act = _strip_v8_context_split_boilerplate(
            SceneDepictionRule.clean_clause(
                str(
                    clip_spec.get("action")
                    or clip_spec.get("kinetic_action")
                    or clip_spec.get("character_reaction")
                    or clip_spec.get("comparison_action")
                    or clip_spec.get("comparison_motion")
                    or clip_spec.get("prop_action")
                    or (format_expression_acting_clause(expr_id, speaker_role=speaker_role, compact=True) if expr_id else "")
                    or "Subject shifts cleanly as four-fingered matte-white architectural porcelain hands move the prop"
                )
            )
        )
        act = _prepend_concise_cast_subject(
            act,
            str(clip_spec.get("cast") or ""),
            grammar,
            str(clip_spec.get("camera_move") or clip_spec.get("camera") or ""),
        )
        cons = _strip_v8_context_split_boilerplate(SceneDepictionRule.clean_clause(str(clip_spec.get("consequence") or "")))
        base = f"{act}, and {cons[:1].lower() + cons[1:]}" if (cons and cons.lower() not in act.lower()) else act
        cam_aerial = str(clip_spec.get("camera_move") or clip_spec.get("camera") or "").strip().lower()
        if (
            grammar == "expressive_exterior_establishing"
            and cam_aerial in ("drone_aerial_approach", "drone_landmark_ascend", "drone_high_orbit_drop")
            and not any(tok in base.lower() for tok in ("unlabeled", "unmarked", "sign-free", "blank stone", "blank facade"))
        ):
            base = f"{base.rstrip('.')}, across smooth blank unlabeled stone facades"

    low_b = base.lower()
    if grammar == "brain_simulator_3d":
        s_reg = SceneDepictionRule.clean_clause(str(clip_spec.get("start_brain_region") or clip_spec.get("brain_region") or "fusiform face area"))
        e_reg = SceneDepictionRule.clean_clause(str(clip_spec.get("end_brain_region") or s_reg))
        n_state = str(clip_spec.get("neural_state") or "active").strip().lower()
        return (
            f"Deterministic Blender 4.2 MNI152 3D clinical brain simulator view over dark studio slate showing a translucent human head shell, "
            f"bilateral cortex, cerebellum, and brainstem with spotlighted matte anatomical structures linking {s_reg} to {e_reg} "
            f"in '{n_state}' pathway state under steady medical drone framing and crisp cavity depth cues."
        )
    if grammar == "expressive_xray_brain":
        is_r85_cs = bool(clip_spec.get("r85_brain_clip") or clip_spec.get("r85_shot_scale") or clip_spec.get("r85_mode"))
        if not any(k in low_b for k in ("3d brain", "3d human brain", "hemisphere", "cerebral")):
            base = (
                f"{base.rstrip('.')}; matte silver-white gypsum 3D brain reveals opaque sulcal tubes"
                if is_r85_cs
                else f"{base.rstrip('.')}; translucent frosted-glass 3D brain reveals glowing neural tracts"
            )
        elif not any(
            k in low_b
            for k in (
                "glass dome",
                "crystal-clear",
                "translucent",
                "frosted-glass",
                "golden forehead",
                "x-ray",
                "silver-white",
                "silver-gray",
                "gypsum",
                "sulcal",
                "cutaway",
            )
        ):
            base = (
                f"{base.rstrip('.')} inside the matte silver-white 3D brain cutaway"
                if is_r85_cs
                else f"{base.rstrip('.')} inside the translucent frosted-glass 3D brain"
            )
    if allow_list and not all(tok.lower() in base.lower() for tok in allow_list):
        quoted = ", ".join(f"'{tok}'" for tok in allow_list)
        base = f"{base.rstrip('.')}. Prop stencil shows {quoted}"
    if cameo_flag and "mini-cortex" not in base.lower():
        base = f"{base.rstrip('.')}. Tiny 4cm Mini-Cortex figurine rests quietly on background shelf"
    return base.strip(" .")


_CREDIT_SAFETY_MINOR_RE = re.compile(
    r"\b(?:child|children|kid|kids|toddler|toddlers|preschooler|preschoolers|young\s+boy|young\s+girl|little\s+boy|little\s+girl)\b",
    flags=re.IGNORECASE,
)
_CREDIT_SAFETY_ISOLATION_RE = re.compile(
    r"\b(?:left\s+alone|sits?\s+alone|sitting\s+alone|isolated|unattended|locked|trap(?:ped)?|"
    r"shuts?\s+(?:the\s+)?door|clos(?:es?|ing|ed)\s+(?:the\s+)?(?:\w+\s+)?door|behind\s+a\s+closed\s+door)\b",
    flags=re.IGNORECASE,
)
_CREDIT_SAFETY_SKIN_HUE_HEAD_RE = re.compile(
    r"(?:warm\s+afternoon\s+sunbeams?|warm\s+sunlight\s+shifts|peach\s+sunbeams?|flesh[-\s]toned|"
    r"warm\s+amber\s+sunbeams?\s+across\s+the\s+(?:face|head)|"
    r"warm\s+(?:wooden|oak|walnut|tan|beige)\s+(?:door|wall|plaster)\s+(?:directly\s+)?behind\s+(?:his|her|the|their)\s+(?:head|face))",
    flags=re.IGNORECASE,
)


def normalize_clip_engine_tag(val: Any, default: str = "auto") -> str:
    """Normalizes a per-clip engine tag to `'omni'`, `'zero-credit'`, or `'auto'`."""
    raw = str(val or "").strip().lower().replace("_", "-")
    if raw in ("omni", "omni-1.2-flash", "gemini-omni-1.2-flash", "omni-1.1-flash", "primary"):  # legacy 1.1 CLI alias routes to primary Omni 1.2 Flash
        return "omni"
    if raw in ("zero-credit", "lite", "veo-lite", "free"):
        return "zero-credit"
    if raw == "auto":
        return "auto"
    return default


def assign_hero_omni_engines(
    visual_plan: dict[str, Any] | None,
    max_hero_clips: int = FLOW_OMNI_HERO_MAX_CLIPS,
    available_credits: int | None = None,
) -> dict[int, str]:
    """
    Resolves 1-based `clip_number -> engine` (`'omni'` | `'zero-credit'` | `'auto'`):
      - Honors any explicit per-clip `spec['engine']`.
      - When `available_credits` is provided (or `visual_plan['omni_tier']` in `{'all', 'dynamic_all'}`),
        computes `compute_dynamic_omni_episode_budget(available_credits, clip_count)` (`C3`) and routes up to
        `max_omni_clips` in priority order:
          (0) `portal_to_brain` / `expressive_xray_brain`
          (1) 3D flight (`fpv_dive_glide`, `orbital_3d_arc_sweep`) & rigid physics (`R68-A`)
          (2) Hook Cuts 1..3 & Climax / Cameo
          (3) Remaining dialogue cuts
      - When `visual_plan['omni_tier'] == 'hero'` (or `hero_omni_cap` is True), tags up to `max_hero_clips`
        (`8` clips = `160` credits with refs) as `'omni'` and sets remaining untagged cuts to `'zero-credit'`.
      - Otherwise defaults untagged cuts to `'auto'` (bounded by `FLOW_OMNI_EPISODE_CREDIT_CAP` at runtime).
    """
    raw_clips = (visual_plan or {}).get("clips") if isinstance((visual_plan or {}).get("clips"), list) else []
    n_total = len(raw_clips)
    if n_total == 0:
        return {}
    tier_mode = str((visual_plan or {}).get("omni_tier") or "").strip().lower()
    raw_avail = available_credits if available_credits is not None else (visual_plan or {}).get("available_credits")
    dynamic_mode = raw_avail is not None or tier_mode in ("all", "dynamic_all", "v83")
    hero_mode = tier_mode == "hero" or bool((visual_plan or {}).get("hero_omni_cap"))
    core_rev_sent = (visual_plan or {}).get("core_reveal_sentence_index")
    brain_grammars = {
        "expressive_xray_brain",
        "porcelain_living_brain",
        "lowpoly_matte_brain",
        "arch_brain_maquette",
        "frosted_crystal_specimen",
    }
    engine_map: dict[int, str] = {}
    omni_count = 0
    for idx, spec in enumerate(raw_clips, start=1):
        if not isinstance(spec, dict):
            continue
        if str(spec.get("engine") or "").strip():
            tag = normalize_clip_engine_tag(spec.get("engine"), default="auto")
            engine_map[idx] = tag
            if tag == "omni":
                omni_count += 1

    if dynamic_mode:
        budget_info = compute_dynamic_omni_episode_budget(
            int(raw_avail) if raw_avail is not None else None,
            clip_count=n_total,
        )
        dyn_cap = max(0, int(budget_info["max_omni_clips"]))
        dyn_candidates: list[tuple[int, int]] = []
        for idx, spec in enumerate(raw_clips, start=1):
            if idx in engine_map or not isinstance(spec, dict):
                continue
            grammar = str(spec.get("grammar") or spec.get("visual_grammar") or "").strip()
            cam = str(spec.get("camera") or spec.get("camera_move") or "").strip()
            rigid_g = str(spec.get("rigid_physics_grammar") or spec.get("physics_grammar") or "").strip()
            cut_role = str(spec.get("cut_role") or "").strip().lower()
            s0 = spec.get("sentence_index")
            s1 = spec.get("end_sentence_index") or s0
            is_core_sent = False
            if core_rev_sent is not None and isinstance(s0, int):
                try:
                    is_core_sent = int(s0) <= int(core_rev_sent) <= int(s1 or s0)
                except (TypeError, ValueError):
                    is_core_sent = False
            if bool(spec.get("portal_to_brain")) or grammar in brain_grammars or bool(spec.get("brain_clip")) or is_core_sent:
                dyn_candidates.append((0, idx))
            elif cam in EXPRESSIVE_V8_3D_FLIGHT_MOVES or rigid_g in EXPRESSIVE_V8_RIGID_PHYSICS_GRAMMARS:
                dyn_candidates.append((1, idx))
            elif idx in (1, 2, 3) or bool(spec.get("cameo_easter_egg")) or grammar == "expressive_cameo_world" or cut_role in ("climax", "reveal", "twist", "pivot") or idx == n_total:
                dyn_candidates.append((2, idx))
            else:
                dyn_candidates.append((3, idx))
        dyn_candidates.sort(key=lambda pair: (pair[0], pair[1]))
        for _prio, idx in dyn_candidates:
            if omni_count >= dyn_cap:
                break
            engine_map[idx] = "omni"
            omni_count += 1
        for idx in range(1, n_total + 1):
            engine_map.setdefault(idx, "zero-credit")
        return engine_map

    if not hero_mode:
        for idx in range(1, n_total + 1):
            engine_map.setdefault(idx, "auto")
        return engine_map

    # Priority buckets for automatic hero-cut selection up to `max_hero_clips`
    candidates: list[tuple[int, int]] = []
    for idx, spec in enumerate(raw_clips, start=1):
        if idx in engine_map or not isinstance(spec, dict):
            continue
        grammar = str(spec.get("grammar") or spec.get("visual_grammar") or "").strip()
        cut_role = str(spec.get("cut_role") or "").strip().lower()
        s0 = spec.get("sentence_index")
        s1 = spec.get("end_sentence_index") or s0
        is_core_sent = False
        if core_rev_sent is not None and isinstance(s0, int):
            try:
                is_core_sent = int(s0) <= int(core_rev_sent) <= int(s1 or s0)
            except (TypeError, ValueError):
                is_core_sent = False
        if idx in (1, 2, 3):
            candidates.append((0, idx))
        elif grammar in brain_grammars or bool(spec.get("brain_clip")) or is_core_sent:
            candidates.append((1, idx))
        elif bool(spec.get("portal_to_brain")) or bool(spec.get("cameo_easter_egg")) or grammar == "expressive_cameo_world":
            candidates.append((2, idx))
        elif cut_role in ("climax", "reveal", "twist", "pivot") or idx == n_total:
            candidates.append((3, idx))

    candidates.sort(key=lambda pair: (pair[0], pair[1]))
    cap = max(0, int(max_hero_clips))
    for _prio, idx in candidates:
        if omni_count >= cap:
            break
        engine_map[idx] = "omni"
        omni_count += 1

    for idx in range(1, n_total + 1):
        engine_map.setdefault(idx, "zero-credit")
    return engine_map


def validate_flow_credit_safety_lint(
    plan: dict[str, Any] | None,
    clips: list[dict[str, Any]] | None,
) -> list[str]:
    """
    Pre-Flow Credit-Loss Prevention Linter (Task 2):
      1. Minor + isolation/closed-door wording that triggers Google Flow / Veo child-safety false rejections.
      2. Warm peach/amber sunbeams or skin-hued wooden/tan backdrops behind porcelain/vinyl heads that trip YuNet `skin_ratio`.
      3. Explicit `engine='omni'` count exceeding `FLOW_OMNI_EPISODE_CREDIT_CAP` (`200` credits = max `10` ref clips).
    """
    issues: list[str] = []
    max_explicit_omni = max(1, int(FLOW_OMNI_EPISODE_CREDIT_CAP) // max(1, int(FLOW_OMNI_CREDIT_COST_WITH_REF)))
    explicit_omni_clips: list[int] = []

    for anc in (plan or {}).get("reference_anchors") or []:
        if not isinstance(anc, dict):
            continue
        rid = str(anc.get("ref_id") or anc.get("filename") or "anchor")
        desc = " ".join(
            str(anc.get(k) or "")
            for k in ("subject", "environment", "visual_desc", "prompt", "description")
        )
        if _CREDIT_SAFETY_MINOR_RE.search(desc) and _CREDIT_SAFETY_ISOLATION_RE.search(desc):
            issues.append(
                f"[credit_safety_lint:minor_isolation_filter_risk] reference_anchor '{rid}' combines minor/child subject "
                "with isolation/closed-door phrasing (high Veo/Imagen safety rejection risk; rephrase to neutral open-room figure)"
            )
        if _CREDIT_SAFETY_SKIN_HUE_HEAD_RE.search(desc):
            issues.append(
                f"[credit_safety_lint:skin_tone_head_backdrop_risk] reference_anchor '{rid}' places warm sunbeams or "
                "skin-toned wood/tan wall behind a vinyl/porcelain head (YuNet false-positive risk)"
            )

    for idx, c in enumerate(clips or [], start=1):
        if not isinstance(c, dict):
            continue
        c_num = int(c.get("clip_number") or idx)
        if normalize_clip_engine_tag(c.get("engine"), default="auto") == "omni":
            explicit_omni_clips.append(c_num)
        is_brain = bool(c.get("brain_clip")) or str(c.get("grammar") or "") in (
            "expressive_xray_brain",
            "porcelain_living_brain",
            "lowpoly_matte_brain",
            "arch_brain_maquette",
            "frosted_crystal_specimen",
        )
        scene_txt = str(c.get("scene") or "")
        if _CREDIT_SAFETY_MINOR_RE.search(scene_txt) and _CREDIT_SAFETY_ISOLATION_RE.search(scene_txt):
            issues.append(
                f"[credit_safety_lint:minor_isolation_filter_risk] clip {c_num} combines minor/child subject with "
                "isolation/closed-door phrasing (high Veo safety rejection risk; use 'small vinyl character' + open doorway)"
            )
        if not is_brain and _CREDIT_SAFETY_SKIN_HUE_HEAD_RE.search(scene_txt):
            issues.append(
                f"[credit_safety_lint:skin_tone_head_backdrop_risk] clip {c_num} uses warm peach/afternoon sunbeams or "
                "skin-toned backdrop near character head (high YuNet human-skin false-positive risk; use cool/neutral studio daylight)"
            )

    if len(explicit_omni_clips) > max_explicit_omni:
        issues.append(
            f"[credit_safety_lint:omni_budget_exceeded] {len(explicit_omni_clips)} clips tagged engine='omni' "
            f"({explicit_omni_clips}) exceeds episode cap of {max_explicit_omni} clips ({FLOW_OMNI_EPISODE_CREDIT_CAP} credits)"
        )
    return issues


def compose_scene_from_r86_beat_card(spec: dict[str, Any]) -> str:
    """
    Rule R86 Semantic Beat Contract -> Scene Composer:
    Translates `(claim, viewer_must_understand, visual_proof_type, concrete_referent, state_delta, bridge_element)`
    into a single-takeaway visual action description so `scene` prompts never drift into noun-only busywork.
    """
    ref = str(spec.get("concrete_referent") or "").strip().rstrip(".")
    delta = str(spec.get("state_delta") or "").strip().rstrip(".")
    bridge = str(spec.get("bridge_element") or "").strip().rstrip(".")
    env = str(spec.get("environment") or "").strip().rstrip(".")
    parts: list[str] = []
    if ref:
        parts.append(ref[0].upper() + ref[1:] if len(ref) > 1 else ref.upper())
    if delta and delta.lower() not in ref.lower():
        parts.append(delta)
    if bridge and bridge.lower() not in " ".join(parts).lower():
        parts.append(f"matching {bridge}")
    if env and env.lower() not in " ".join(parts).lower():
        parts.append(f"in {env}")
    composed = ", ".join(p for p in parts if p).strip()
    return f"{composed}." if composed and not composed.endswith(".") else composed


def build_expressive_v8_prompts(
    visual_plan: dict[str, Any],
    narrations: list[str] | None = None,
    aspect: str = FLOW_ASPECT_SHORTS,
) -> list[dict[str, Any]]:
    """Renders Schema v8 (`expressive_25d_v8`) 8-second multi-beat clip prompts with Start+End VIDEO_FRAMES keyframe chains & transition hygiene (R68)."""
    from pipeline.config import BRAIN_SIM_ONLY_CLIP_COUNT_RANGE, is_brain_sim_only_plan, is_r76_v8_plan
    from pipeline.depiction_rules import (
        EXPRESSIVE_V8_CAMERA_DESCRIPTORS,
        ExpressiveV8PromptComposer,
        FLOW_CAMERA_HARDWARE_NEGATIVE_GUARD,
        normalize_expressive_v8_grammar,
        sanitize_flow_viewpoint_hardware_terms,
    )

    raw_clips = visual_plan.get("clips") if isinstance(visual_plan.get("clips"), list) else []
    from pipeline.config import (
        PRE_R88_FROZEN_V8_PROJECTS,
        R82_CLIP_COUNT_RANGE,
        R85_DRONE_ALTITUDE_LOCK_CLAUSE,
        R85_HUMAN_IDENTITY_LOCK_SUFFIX,
        R85_LEGACY_HUMAN_IDENTITY_LOCK_SUFFIX,
        is_r82_dual_speed_pacing_plan,
        is_r85_flow_31_brain_plan,
        is_r86_semantic_beat_plan,
    )

    is_brain_only_build = is_brain_sim_only_plan(visual_plan)
    is_r85_build = is_r85_flow_31_brain_plan(visual_plan)
    is_r86_build = is_r86_semantic_beat_plan(visual_plan)
    is_r82_build = is_r82_dual_speed_pacing_plan(visual_plan) or is_r85_build
    is_r76_build = is_r76_v8_plan(visual_plan)
    is_r72_build = is_r72_open_world_v8_plan(visual_plan)
    if bool(visual_plan.get("allow_legacy_v8_clip_count")):
        min_clips = EXPRESSIVE_V8_LEGACY_CLIP_COUNT_MIN
    elif is_brain_only_build:
        min_clips = int(BRAIN_SIM_ONLY_CLIP_COUNT_RANGE[0])
    elif is_r82_build:
        min_clips = int(R82_CLIP_COUNT_RANGE[0])
    elif is_r76_build:
        from pipeline.config import EXPRESSIVE_V8_R76_CLIP_COUNT_RANGE

        min_clips = int(EXPRESSIVE_V8_R76_CLIP_COUNT_RANGE[0])
    elif not is_r72_build:
        min_clips = EXPRESSIVE_V8_LEGACY_INDOOR_CLIP_COUNT_RANGE[0]
    else:
        min_clips = SHORTS_EXPRESSIVE_V8_CLIP_COUNT_MIN
    max_clips = (
        int(BRAIN_SIM_ONLY_CLIP_COUNT_RANGE[1])
        if is_brain_only_build
        else (int(R82_CLIP_COUNT_RANGE[1]) if is_r82_build else SHORTS_EXPRESSIVE_V8_CLIP_COUNT_MAX)
    )
    if not (min_clips <= len(raw_clips) <= max_clips):
        raise ValueError(
            f"Schema v8 expressive_25d_v8 visual_plan.clips must contain "
            f"{min_clips}-{max_clips} clip specs (got {len(raw_clips)})"
        )
    mode = str(visual_plan.get("visual_mode") or "NEURO_BIOLOGY").upper()
    anchor_by_stem: dict[str, dict[str, Any]] = {}
    for anc in visual_plan.get("reference_anchors") or []:
        if not isinstance(anc, dict):
            continue
        raw_fn = str(anc.get("filename") or anc.get("ref_id") or "").strip()
        if raw_fn:
            anchor_by_stem[Path(raw_fn).stem] = anc
        rid_a = str(anc.get("ref_id") or "").strip()
        if rid_a:
            anchor_by_stem.setdefault(rid_a, anc)

    default_cam_cycle = (
        "gentle_push_in",
        "pan_right",
        "locked_tripod",
        "pan_left",
        "tilt_down",
        "clean_pullback_reveal",
        "gentle_push_in",
        "tilt_up",
    )
    engine_map = assign_hero_omni_engines(visual_plan)
    out: list[dict[str, Any]] = []
    for idx, spec in enumerate(raw_clips, start=1):
        if not isinstance(spec, dict):
            raise ValueError(f"Schema v8 clip {idx} must be a dict")
        cameo_flag = bool(spec.get("cameo_easter_egg")) or str(spec.get("grammar") or "") == "expressive_cameo_world"
        grammar = normalize_expressive_v8_grammar(
            spec.get("grammar") or spec.get("visual_grammar") or "expressive_vinyl_world",
            cameo_easter_egg=cameo_flag,
        )
        if grammar == "expressive_cameo_world":
            cameo_flag = True
        is_brain = grammar in ("expressive_xray_brain", "brain_simulator_3d")
        explicit_cam = str(spec.get("camera") or spec.get("camera_move") or "").strip()
        if explicit_cam:
            cam = explicit_cam
        elif bool(visual_plan.get("use_alternating_camera_cycle") or spec.get("use_alternating_camera_cycle")):
            cam = resolve_alternating_camera_move(idx - 1, is_brain=is_brain)
        else:
            cam = default_cam_cycle[(idx - 1) % len(default_cam_cycle)]
        render_engine = str(
            spec.get("render_engine")
            or ("blender_3d_simulator" if grammar == "brain_simulator_3d" else "google_flow")
        ).strip()
        ref_img = spec.get("reference_image")
        sec_ref_img = spec.get("secondary_reference_image")
        end_ref_img = spec.get("end_reference_image")
        start_ref_str = str(ref_img or "").strip()
        sec_ref_str = str(sec_ref_img or "").strip()
        end_ref_str = str(end_ref_img or "").strip()
        drift_end_frame_lock = bool(spec.get("drift_end_frame_lock"))
        is_drift_vulnerable_r85 = is_r85_build and (
            grammar in ("expressive_reaction_closeup", "expressive_hands_closeup", "expressive_hands_macro")
            or (
                grammar == "spatial_3d_arrow_diorama"
                and str(spec.get("arrow_3d_mode") or "") == "doorway_boundary_sever"
            )
        )
        if (
            is_drift_vulnerable_r85
            and not bool(spec.get("single_start_frame_lock"))
            and start_ref_str
            and not end_ref_str
            and not sec_ref_str
            and not start_ref_str.endswith(
                (
                    EXPRESSIVE_V8_CAMEO_SHEET_FILENAME,
                    EXPRESSIVE_V8_SPECIES_SHEET_FILENAME,
                    *EXPRESSIVE_V8_CAST_SHEET_FILENAMES,
                )
            )
        ):
            end_ref_img = ref_img
            end_ref_str = start_ref_str
            drift_end_frame_lock = True
        has_same_end_lock = bool(
            start_ref_str and end_ref_str and start_ref_str == end_ref_str and (drift_end_frame_lock or is_r85_build) and not cameo_flag
        )
        has_distinct_end = bool(start_ref_str and end_ref_str and start_ref_str != end_ref_str and not cameo_flag)
        start_stem = Path(start_ref_str).stem if start_ref_str else ""
        end_stem = Path(end_ref_str).stem if end_ref_str else ""
        start_anc = anchor_by_stem.get(start_stem)
        end_anc = anchor_by_stem.get(end_stem)
        portal_to_brain = bool(spec.get("portal_to_brain")) or (
            is_brain
            and has_distinct_end
            and "xray" not in start_stem.lower()
            and "brain_master" not in start_stem.lower()
            and "brain" not in start_stem.lower()
            and str((start_anc or {}).get("setting") or "") not in ("brain_studio", "contrast_pair")
            and (
                "xray" in end_stem.lower()
                or "brain" in end_stem.lower()
                or str((end_anc or {}).get("setting") or "") == "brain_studio"
            )
        )

        explicit_trans = str(spec.get("transition_out") or spec.get("transition_to_next") or "").strip().lower()
        if explicit_trans in (*EXPRESSIVE_V8_TRANSITION_TYPES, "hard"):
            transition_out = explicit_trans
        elif has_distinct_end and idx < len(raw_clips):
            transition_out = "daisy_chain_bridge"
        else:
            transition_out = "hard"

        if cameo_flag and sec_ref_str:
            flow_input_mode = "VIDEO_REFERENCES"
            keyframe_chain_mode = "dual_reference_ingredients"
        elif has_distinct_end or has_same_end_lock:
            flow_input_mode = "VIDEO_FRAMES"
            keyframe_chain_mode = (
                "start_end_drift_lock"
                if has_same_end_lock
                else ("portal_zoom_to_xray_brain" if portal_to_brain else "start_end_interpolation")
            )
        elif start_ref_str:
            if (
                str(spec.get("flow_input_mode") or "").strip().upper() == "VIDEO_FRAMES"
                or bool(spec.get("single_start_frame_lock"))
            ):
                flow_input_mode = "VIDEO_FRAMES"
                keyframe_chain_mode = "single_start_frame"
            else:
                flow_input_mode = "VIDEO_REFERENCES"
                keyframe_chain_mode = "single_reference_anchor"
        elif end_ref_str:
            flow_input_mode = "VIDEO_FRAMES"
            keyframe_chain_mode = "end_frame_only"
        else:
            flow_input_mode = "TEXT_TO_VIDEO"
            keyframe_chain_mode = "unconditioned"

        is_image_conditioned = flow_input_mode in ("VIDEO_FRAMES", "VIDEO_REFERENCES")
        use_context_split = bool(spec.get("context_split", True)) and is_image_conditioned

        keyframe_bridge_clause: str | None = None
        if has_distinct_end:
            explicit_traj = str(spec.get("keyframe_trajectory") or spec.get("trajectory_bridge") or "").strip()
            s_brief = str(spec.get("start_frame_brief") or "").strip()
            e_brief = str(spec.get("end_frame_brief") or "").strip()
            s_ang = str((start_anc or {}).get("camera_angle_tag") or "").strip().replace("_", " ")
            e_ang = str((end_anc or {}).get("camera_angle_tag") or "").strip().replace("_", " ")
            if explicit_traj:
                keyframe_bridge_clause = explicit_traj
            elif use_context_split:
                if cam == "neural_fpv_dive_in":
                    keyframe_bridge_clause = "Forward-gliding macro trajectory dives from wide 3D glass brain frame into close-up optical-glass subcortical chamber"
                elif cam == "neural_fpv_pullback_out":
                    keyframe_bridge_clause = "Reverse macro pullback sweeps out from subcortical chamber into wide 3D glass brain frame"
                elif cam == "neural_tract_relay_flight":
                    keyframe_bridge_clause = "Smooth macro trajectory glides along optical-glass neural tracts between subcortical chambers"
                elif portal_to_brain:
                    keyframe_bridge_clause = "3D flight bridges opening room frame into closing glass-dome X-Ray brain frame"
                elif grammar == "architectural_cutaway_portal" or cam == "fpv_window_portal_breach":
                    keyframe_bridge_clause = "Forward-gliding sweep breaches landmark facade smoothly into cutaway interior laboratory"
                elif s_ang and e_ang and s_ang != e_ang:
                    keyframe_bridge_clause = f"Bridges opening {s_ang} frame smoothly into closing {e_ang} frame"
                else:
                    keyframe_bridge_clause = "Bridges opening frame smoothly into closing pose"
            elif s_brief and e_brief:
                keyframe_bridge_clause = (
                    f"Continuous 3D trajectory smoothly connecting {s_brief} in the opening frame "
                    f"into {e_brief} in the closing frame"
                )
            elif portal_to_brain:
                keyframe_bridge_clause = (
                    "Continuous 3D push-in trajectory smoothly bridging the opening room character frame "
                    "into the closing crystal-clear glass cranium X-Ray brain frame"
                )
            elif s_ang and e_ang and s_ang != e_ang:
                keyframe_bridge_clause = (
                    f"Continuous 3D trajectory smoothly bridging the opening {s_ang} keyframe "
                    f"into the closing {e_ang} keyframe"
                )
            else:
                keyframe_bridge_clause = (
                    "Continuous 3D trajectory smoothly bridging the opening keyframe composition "
                    "into the closing keyframe pose"
                )

        allow_list = [str(t).strip() for t in (spec.get("diegetic_text_allowlist") or ()) if str(t).strip()][:2]
        act_no = int(spec.get("act") or min(6, ((idx - 1) * 6) // max(1, len(raw_clips)) + 1))
        spec_for_scene = {
            **spec,
            "grammar": grammar,
            "cameo_easter_egg": cameo_flag,
            "diegetic_text_allowlist": allow_list,
        }
        if (
            is_r86_build
            and not str(spec_for_scene.get("scene") or "").strip()
            and not str(spec_for_scene.get("action") or "").strip()
            and str(spec_for_scene.get("concrete_referent") or "").strip()
        ):
            composed_r86 = compose_scene_from_r86_beat_card(spec_for_scene)
            if composed_r86:
                spec_for_scene["scene"] = composed_r86
                spec_for_scene["action"] = composed_r86
        r78m_custom = str(spec.get("r78m_flow_prompt") or "").strip()
        if r78m_custom:
            clean_r78m = sanitize_flow_viewpoint_hardware_terms(r78m_custom)
            clean_r78m = re.sub(
                r"\bsweeping\s+3d\s+(?:lateral\s+)?orbit\b",
                "Poised steady 3D glide",
                clean_r78m,
                flags=re.IGNORECASE,
            )
            scene_body = sanitize_diorama_scene_for_flow(clean_r78m)
            render_sec = int(spec.get("render_sec") or DIORAMA_CLIP_RENDER_SEC)
            if bool(spec.get("side_by_side_brain_compare")):
                plane_tail = (
                    "Maintain poised wide front-coronal framing under 6 degrees of subtle single-plane micro-parallax "
                    "keeping both entire whole brains completely inside the left and right frame margins over pure dark studio slate."
                )
            else:
                plane_tail = (
                    "Maintain one consistent anatomical viewing plane with gentle micro-parallax under 12 degrees "
                    "(no 90-degree sagittal-to-coronal head spin)."
                )
            prompt_str = (
                f"{EXPRESSIVE_V8_CAMERA_DESCRIPTORS.get(cam, '') + ' ' if cam in EXPRESSIVE_V8_CAMERA_DESCRIPTORS else ''}"
                f"Vertical full-bleed 3D motion locked seamlessly to the opening keyframe, "
                f"{scene_body.rstrip('. ')}. "
                f"{plane_tail} "
                f"Upper studio background stays pure unobstructed dark void. Silent voice track. {FLOW_CAMERA_HARDWARE_NEGATIVE_GUARD}"
            ).strip()
        else:
            if grammar == "spatial_3d_arrow_diorama" and visual_plan.get("spatial_arrow_eligible") is False:
                raise ValueError(
                    "R87-A forbids spatial_3d_arrow_diorama when visual_plan['spatial_arrow_eligible'] is False"
                )
            raw_scene_text = (
                _compose_expressive_v8_context_split_scene(spec_for_scene)
                if use_context_split
                else _compose_expressive_v8_clip_scene(spec_for_scene)
            )
            scene_body = sanitize_diorama_scene_for_flow(raw_scene_text)
            render_sec = int(spec.get("render_sec") or DIORAMA_CLIP_RENDER_SEC)
            prompt_str = ExpressiveV8PromptComposer.compose_clip_prompt(
                scene_body=scene_body,
                grammar=grammar,
                camera_move=cam,
                transition_out=transition_out,
                aspect=aspect,
                render_sec=render_sec,
                keyframe_bridge_clause=keyframe_bridge_clause,
                context_split=use_context_split,
                r85_mode=is_r85_build,
            )
            if is_r85_build:
                from pipeline.config import R85_BRAIN_ANTI_VFX_NEGATIVE_CLAUSE

                is_aerial_drone_cut = cam in (
                    "drone_aerial_approach",
                    "drone_landmark_ascend",
                    "drone_high_orbit_drop",
                    "drone_skyline_pullback",
                ) or grammar == "expressive_exterior_establishing"
                if is_brain and R85_BRAIN_ANTI_VFX_NEGATIVE_CLAUSE.lower() not in prompt_str.lower():
                    prompt_str = prompt_str.replace(
                        "Silent voice track.",
                        f"{R85_BRAIN_ANTI_VFX_NEGATIVE_CLAUSE}. Silent voice track.",
                        1,
                    )
                elif is_aerial_drone_cut and R85_DRONE_ALTITUDE_LOCK_CLAUSE.lower() not in prompt_str.lower():
                    prompt_str = prompt_str.replace(
                        "Silent voice track.",
                        f"{R85_DRONE_ALTITUDE_LOCK_CLAUSE}. Silent voice track.",
                        1,
                    )
                elif (
                    not is_brain
                    and not is_aerial_drone_cut
                    and grammar != "spatial_3d_arrow_diorama"
                    and not (
                        not bool(spec.get("cast_roles"))
                        and not str(spec.get("cast") or "").strip()
                        and ("zero people" in scene_body.lower() or "tabletop-only" in scene_body.lower())
                    )
                ):
                    eff_pid_lock = str(visual_plan.get("project_id") or "").strip()
                    human_lock_suffix = (
                        R85_LEGACY_HUMAN_IDENTITY_LOCK_SUFFIX
                        if (eff_pid_lock in PRE_R88_FROZEN_V8_PROJECTS or bool(visual_plan.get("allow_legacy_pre_r88")))
                        else R85_HUMAN_IDENTITY_LOCK_SUFFIX
                    )
                    if (
                        human_lock_suffix.lower() not in prompt_str.lower()
                        and R85_HUMAN_IDENTITY_LOCK_SUFFIX.lower() not in prompt_str.lower()
                        and R85_LEGACY_HUMAN_IDENTITY_LOCK_SUFFIX.lower() not in prompt_str.lower()
                    ):
                        prompt_str = prompt_str.replace(
                            "Silent voice track.",
                            f"{human_lock_suffix}. Silent voice track.",
                            1,
                        )
        ref_imgs = list(spec.get("reference_images") or [])
        if not ref_imgs and ref_img:
            ref_imgs = [ref_img] + ([sec_ref_img] if sec_ref_img else [])
        out.append(
            {
                "clip_number": idx,
                "clip_index": idx,
                "act": act_no,
                "grammar": grammar,
                "role": f"act{act_no}_{grammar}",
                "setting": ("brain_studio" if is_brain else "real_env"),
                "camera_move": cam,
                "transition_out": transition_out,
                "cameo_easter_egg": cameo_flag,
                "diegetic_text_allowlist": allow_list,
                "lighting_mode": str(spec.get("lighting_mode") or ("night_interior" if "night" in scene_body.lower() or "dimly" in scene_body.lower() else "studio_cinema")),
                "foley_cue": spec.get("foley_cue"),
                "target_duration": f"{render_sec}s",
                "expected_syllables": 0,
                "estimated_speech_sec": 0.0,
                "cutoff_risk": False,
                "motif_present": False,
                "location_id": spec.get("location_id"),
                "environment": spec.get("environment"),
                "real_world_target_id": spec.get("real_world_target_id"),
                "scene_id": spec.get("scene_id") or f"act{act_no}_clip{idx}",
                "shot_type": spec.get("shot_type") or _shot_type_from_camera(cam),
                "brain_clip": is_brain,
                "render_engine": render_engine,
                "brain_mode": (
                    "mni152_clinical_3d"
                    if grammar == "brain_simulator_3d"
                    else ("crystal_dome_xray_4color" if is_brain else spec.get("brain_mode"))
                ),
                "start_brain_region": spec.get("start_brain_region") or spec.get("brain_region"),
                "brain_region": spec.get("brain_region"),
                "end_brain_region": spec.get("end_brain_region"),
                "neural_state": spec.get("neural_state"),
                "start_neural_state": spec.get("start_neural_state"),
                "callout_mode": spec.get("callout_mode"),
                "callout_gloss": spec.get("callout_gloss"),
                "neural_dive_relay": bool(spec.get("neural_dive_relay")),
                "r74_macro_mode": bool(spec.get("r74_macro_mode")),
                "portal_entry_sec": spec.get("portal_entry_sec"),
                "anatomy_label": spec.get("anatomy_label"),
                "callout_enabled": spec.get("callout_enabled"),
                "r78m_callout": spec.get("r78m_callout"),
                "r78m_material_mode": spec.get("r78m_material_mode"),
                "r78m_flow_prompt": spec.get("r78m_flow_prompt"),
                "spatial_relay_cut": bool(spec.get("spatial_relay_cut")),
                "human_action_relay": bool(spec.get("human_action_relay")),
                "r72_cold_open_relay": bool(spec.get("r72_cold_open_relay")),
                "side_by_side_brain_compare": bool(spec.get("side_by_side_brain_compare")),
                "stacked_cutaway_brain_compare": bool(spec.get("stacked_cutaway_brain_compare")),
                "surgical_cutaway": spec.get("surgical_cutaway"),
                "dashed_baseline": bool(spec.get("dashed_baseline")),
                "morph_mode": spec.get("morph_mode"),
                "arrow_3d_mode": spec.get("arrow_3d_mode"),
                "flight_speed_ramp": spec.get("flight_speed_ramp"),
                "crop_zoom": spec.get("crop_zoom"),
                "src_start_sec": spec.get("src_start_sec"),
                "src_end_sec": spec.get("src_end_sec"),
                "max_src_end_sec": spec.get("max_src_end_sec"),
                "single_start_frame_lock": bool(spec.get("single_start_frame_lock")),
                "sentence_index": spec.get("sentence_index"),
                "end_sentence_index": spec.get("end_sentence_index"),
                "beat_index": spec.get("beat_index"),
                "beat_weight": spec.get("beat_weight"),
                "cut_role": spec.get("cut_role"),
                "reference_image": ref_img,
                "secondary_reference_image": sec_ref_img,
                "reference_images": ref_imgs,
                "end_reference_image": end_ref_img,
                "drift_end_frame_lock": bool(drift_end_frame_lock or has_same_end_lock),
                "preferred_flow_model": (
                    FLOW_PRIMARY_VIDEO_MODEL
                    if (
                        not str(spec.get("preferred_flow_model") or "").strip()
                        or str(spec.get("preferred_flow_model") or "").strip() in FLOW_RETIRED_VIDEO_MODELS
                    )
                    else str(spec.get("preferred_flow_model")).strip()
                ),
                "r85_shot_scale": spec.get("r85_shot_scale"),
                "viewpoint": spec.get("viewpoint"),
                "functional_highlight_color": spec.get("functional_highlight_color"),
                "claim": spec.get("claim"),
                "viewer_must_understand": spec.get("viewer_must_understand"),
                "visual_proof_type": spec.get("visual_proof_type"),
                "visual_register": spec.get("visual_register"),
                "concrete_referent": spec.get("concrete_referent"),
                "metaphor_continuity_id": spec.get("metaphor_continuity_id"),
                "bridge_element": spec.get("bridge_element"),
                "concept_id": spec.get("concept_id"),
                "state_delta": spec.get("state_delta"),
                "mechanism_seed": spec.get("mechanism_seed"),
                "anti_filler_check": spec.get("anti_filler_check"),
                "full_trajectory_span": bool(spec.get("full_trajectory_span") or end_ref_str),
                "flow_input_mode": flow_input_mode,
                "engine": engine_map.get(idx, "auto"),
                "keyframe_chain_mode": keyframe_chain_mode,
                "portal_to_brain": portal_to_brain,
                "start_anchor_id": (start_stem or None),
                "end_anchor_id": (end_stem or None),
                "source_shot_id": spec.get("source_shot_id"),
                "aspect": aspect,
                "schema_version": PROMPT_SCHEMA_VERSION_V8,
                "style_profile": EXPRESSIVE_25D_V8_STYLE_PROFILE,
                "shorts_format_profile": SHORTS_EXPRESSIVE_V8_PROFILE,
                "profile": "neuro_diorama",
                "visual_mode": mode,
                "scene": scene_body,
                "spoken_narration": "",
                "prompt": prompt_str,
                "full_prompt": prompt_str,
            }
        )
    _ = narrations
    return out


def validate_expressive_v8_prompts(
    clips: list[dict[str, Any]],
    plan: dict[str, Any] | None = None,
) -> list[str]:
    """Structural & R68 forensic prompt validator for Schema v8 (`expressive_25d_v8`)."""
    from pipeline.config import (
        BRAIN_SIM_ONLY_CLIP_COUNT_RANGE,
        EXPRESSIVE_V8_BRAIN_SIM_DRONE_MOVES,
        EXPRESSIVE_V8_NEURAL_DIVE_MOVES,
        EXPRESSIVE_V8_NEURO_BRAIN_REVEAL_WINDOW_FRAC,
        EXPRESSIVE_V8_R76_BRAIN_REVEAL_WINDOW_FRAC,
        PRE_R77_FROZEN_V8_PROJECTS,
        is_brain_sim_only_plan,
        is_r74_neural_dive_v8_plan,
        is_r74b_neuro_pathway_v8_plan,
        is_r76_v8_plan,
        resolve_expressive_v8_topic_focus,
    )
    from pipeline.depiction_rules import (
        EXPRESSIVE_V8_CAMERA_DESCRIPTORS,
        EXPRESSIVE_V8_COMPACT_CAMERA_DESCRIPTORS,
        EXPRESSIVE_V8_SUPPLEMENTAL_CAMERA_DESCRIPTORS,
        FLOW_CAMERA_HARDWARE_NEGATIVE_GUARD,
        validate_expressive_v8_scene,
    )

    issues: list[str] = []
    from pipeline.config import (
        EXPRESSIVE_V8_R76_CLIP_COUNT_RANGE,
        R82_CLIP_COUNT_RANGE,
        is_r82_dual_speed_pacing_plan,
        is_r85_flow_31_brain_plan,
    )

    allow_legacy_clips = bool((plan or {}).get("allow_legacy_v8_clip_count"))
    is_brain_sim_only = is_brain_sim_only_plan(plan)
    is_r82 = is_r82_dual_speed_pacing_plan(plan)
    is_r76_cnt = is_r76_v8_plan(plan)
    is_r72 = is_r72_open_world_v8_plan(plan)
    eff_pid = str((plan or {}).get("project_id") or "").strip()
    is_pre_r77_frozen = bool(eff_pid in PRE_R77_FROZEN_V8_PROJECTS or (plan or {}).get("allow_legacy_pre_r77"))
    if is_brain_sim_only:
        min_clips = int(BRAIN_SIM_ONLY_CLIP_COUNT_RANGE[0])
    elif allow_legacy_clips:
        min_clips = EXPRESSIVE_V8_LEGACY_CLIP_COUNT_MIN
    elif is_r82:
        min_clips = int(R82_CLIP_COUNT_RANGE[0])
    elif is_r76_cnt:
        min_clips = int(EXPRESSIVE_V8_R76_CLIP_COUNT_RANGE[0])
    elif not is_r72:
        min_clips = EXPRESSIVE_V8_LEGACY_INDOOR_CLIP_COUNT_RANGE[0]
    else:
        min_clips = SHORTS_EXPRESSIVE_V8_CLIP_COUNT_MIN
    max_clips = (
        int(BRAIN_SIM_ONLY_CLIP_COUNT_RANGE[1])
        if is_brain_sim_only
        else (int(R82_CLIP_COUNT_RANGE[1]) if is_r82 else SHORTS_EXPRESSIVE_V8_CLIP_COUNT_MAX)
    )
    if not isinstance(clips, list) or not (min_clips <= len(clips) <= max_clips):
        return [
            f"[prompt] Schema v8 expressive_25d_v8 clip count must be "
            f"{min_clips}-{max_clips} "
            f"(got {len(clips) if isinstance(clips, list) else 0}) ({'R77-BrainOnly' if is_brain_sim_only else ('R82' if is_r82 else ('R76-P' if is_r76_cnt else ('R72' if is_r72 else 'R68')))})"
        ]

    n_total = len(clips)
    tol_lo, tol_hi = EXPRESSIVE_V8_BRAIN_REVEAL_TOLERANCE_FRAC
    is_r76 = is_r76_v8_plan(plan)
    is_r74 = is_r74_neural_dive_v8_plan(plan)
    is_neuro_r74b = (
        is_r74b_neuro_pathway_v8_plan(plan)
        and resolve_expressive_v8_topic_focus(plan) == "neuroscience"
    )
    if is_r76:
        eff_premature_floor = float(EXPRESSIVE_V8_R76_BRAIN_REVEAL_WINDOW_FRAC[0])
        tol_lo = eff_premature_floor
        tol_hi = 0.90
    elif is_neuro_r74b:
        eff_premature_floor = EXPRESSIVE_V8_NEURO_BRAIN_REVEAL_WINDOW_FRAC[0]
        tol_hi = max(tol_hi, EXPRESSIVE_V8_NEURO_BRAIN_REVEAL_WINDOW_FRAC[1])
    else:
        eff_premature_floor = 0.36 if is_r74 else tol_lo
    core_rev_sent = (plan or {}).get("core_reveal_sentence_index")
    allow_early_override = bool((plan or {}).get("allow_early_brain_override"))
    allowed_trans = (*EXPRESSIVE_V8_TRANSITION_TYPES, "hard")
    cameo_clips: list[int] = []
    xray_in_window: list[int] = []
    premature_xray: list[int] = []
    core_sent_has_xray = False
    flight_clips = 0
    distinct_locations: set[str] = set()
    cs_lo, cs_hi = EXPRESSIVE_V8_CONTEXT_SPLIT_WORDS_RANGE

    for idx, c in enumerate(clips, start=1):
        if not isinstance(c, dict):
            issues.append(f"[prompt] clip {idx} is not a dict")
            continue
        grammar = str(c.get("grammar") or "")
        cam = str(c.get("camera_move") or "")
        scene = str(c.get("scene") or "")
        prompt_str = str(c.get("prompt") or c.get("full_prompt") or "")
        trans_out = str(c.get("transition_out") or "").strip().lower()
        cameo_flag = bool(c.get("cameo_easter_egg")) or grammar == "expressive_cameo_world"
        loc_val = str(c.get("location_id") or "").strip()
        if loc_val:
            distinct_locations.add(loc_val)
        raw_vp_clips = list((plan or {}).get("clips") or [])
        raw_vp_allow = (
            list((raw_vp_clips[idx - 1] or {}).get("diegetic_text_allowlist") or [])
            if idx - 1 < len(raw_vp_clips) and isinstance(raw_vp_clips[idx - 1], dict)
            else []
        )
        allow_list = raw_vp_allow if len(raw_vp_allow) > len(list(c.get("diegetic_text_allowlist") or [])) else list(c.get("diegetic_text_allowlist") or [])

        if grammar not in EXPRESSIVE_V8_VISUAL_GRAMMARS:
            issues.append(
                f"[prompt] clip {idx}: invalid v8 grammar '{grammar}' (must be in {list(EXPRESSIVE_V8_VISUAL_GRAMMARS)}) (R68)"
            )
        allowed_v8_cams = set(EXPRESSIVE_V8_CAMERA_MOVES) | set(EXPRESSIVE_V8_COMPACT_CAMERA_DESCRIPTORS)
        if cam not in allowed_v8_cams:
            issues.append(f"[prompt] clip {idx}: camera '{cam}' must be one of {sorted(allowed_v8_cams)} (R68)")
        else:
            desc_full = (
                EXPRESSIVE_V8_CAMERA_DESCRIPTORS.get(cam)
                or EXPRESSIVE_V8_SUPPLEMENTAL_CAMERA_DESCRIPTORS.get(cam)
                or ""
            )
            desc_compact = EXPRESSIVE_V8_COMPACT_CAMERA_DESCRIPTORS[cam]
            desc_compact_r85 = (
                desc_compact.replace("translucent frosted-glass cortical folds", "matte silver-white sculpted gypsum cortical folds")
                .replace("frosted-glass cortical folds", "matte silver-white cortical folds")
                .replace("luminous optical-glass subcortical hub", "solid matte-shaded subcortical hub")
                .replace("luminous optical-glass fiber bundles", "opaque sulcal and white-matter tubes")
            )
            cnt = (prompt_str.count(desc_full) if desc_full else 0) + prompt_str.count(desc_compact) + (
                prompt_str.count(desc_compact_r85) if desc_compact_r85 != desc_compact else 0
            )
            if cnt != 1:
                issues.append(f"[prompt] clip {idx}: v8 camera clause must appear exactly once (found {cnt}) (R68)")
        if idx == 1 and cam == "locked_tripod":
            issues.append(
                "[prompt] clip 1: R68 Action Cold-Open requires 3D camera motion from frame 0 (cannot use 'locked_tripod' on clip 1) (R68)"
            )
        if trans_out and trans_out not in allowed_trans:
            issues.append(
                f"[prompt] clip {idx}: transition_out '{trans_out}' must be in {list(allowed_trans)} (R68)"
            )

        multi_panel_v8_sheets = (
            EXPRESSIVE_V8_CAMEO_SHEET_FILENAME,
            EXPRESSIVE_V8_SPECIES_SHEET_FILENAME,
            *EXPRESSIVE_V8_CAST_SHEET_FILENAMES,
        )
        start_ref = str(c.get("reference_image") or "").strip()
        sec_ref = str(c.get("secondary_reference_image") or "").strip()
        end_ref = str(c.get("end_reference_image") or "").strip()
        f_mode = str(c.get("flow_input_mode") or "").strip().upper()
        is_img_cond = f_mode in ("VIDEO_FRAMES", "VIDEO_REFERENCES") or bool(start_ref or end_ref or sec_ref)
        if cam in EXPRESSIVE_V8_3D_FLIGHT_MOVES or bool(end_ref) or f_mode == "VIDEO_FRAMES":
            flight_clips += 1

        if sec_ref and end_ref:
            issues.append(
                f"[keyframe_chain_v8] clip {idx}: cannot combine secondary_reference_image ('{sec_ref}') "
                f"with end_reference_image ('{end_ref}') — Flow VIDEO_REFERENCES and VIDEO_FRAMES modes are mutually exclusive (R68)"
            )
        if is_r85_flow_31_brain_plan(plan) or bool((plan or {}).get("canonical_assets_version")):
            from pipeline.canonical_assets import is_retired_derivative_anchor

            for r_lbl, r_val in (
                ("reference_image", start_ref),
                ("secondary_reference_image", sec_ref),
                ("end_reference_image", end_ref),
            ):
                if r_val and is_retired_derivative_anchor(r_val):
                    issues.append(
                        f"[canonical_retired_anchor] clip {idx}: {r_lbl} '{r_val}' uses retired/unapproved anchor; "
                        "load strictly from canonical_assets/v1 approved slots (R85)"
                    )
        if end_ref.endswith(EXPRESSIVE_V8_CAMEO_SHEET_FILENAME):
            issues.append(
                f"[keyframe_chain_v8] clip {idx}: end_reference_image '{end_ref}' must not bind multi-panel cameo turnaround sheet (R68)"
            )
        elif end_ref.endswith(multi_panel_v8_sheets):
            issues.append(
                f"[keyframe_chain_v8] clip {idx}: end_reference_image '{end_ref}' must not bind multi-panel turnaround/cast sheet in VIDEO_FRAMES End slot (R68)"
            )
        if end_ref and start_ref.endswith(multi_panel_v8_sheets):
            issues.append(
                f"[keyframe_chain_v8] clip {idx}: start reference_image '{start_ref}' must not bind multi-panel turnaround/cast sheet when end_reference_image ('{end_ref}') activates VIDEO_FRAMES Start+End mode (R68)"
            )
        if end_ref and not start_ref:
            issues.append(
                f"[keyframe_chain_v8] clip {idx}: end_reference_image '{end_ref}' requires a non-empty start reference_image (R68)"
            )
        if (
            end_ref
            and start_ref
            and end_ref == start_ref
            and not bool(c.get("drift_end_frame_lock"))
            and not is_r85_flow_31_brain_plan(plan)
        ):
            issues.append(
                f"[keyframe_chain_v8] clip {idx}: end_reference_image '{end_ref}' duplicates start reference_image (degenerate zero-motion keyframe pair) (R68)"
            )

        from pipeline.config import (
            R85_BRAIN_ANTI_VFX_NEGATIVE_CLAUSE,
            R85_DRONE_ALTITUDE_LOCK_CLAUSE,
            R85_HUMAN_IDENTITY_LOCK_SUFFIX,
            R85_LEGACY_HUMAN_IDENTITY_LOCK_SUFFIX,
        )

        prompt_for_wc = (
            prompt_str.replace(FLOW_CAMERA_HARDWARE_NEGATIVE_GUARD, "")
            .replace(R85_HUMAN_IDENTITY_LOCK_SUFFIX + ".", "")
            .replace(R85_HUMAN_IDENTITY_LOCK_SUFFIX, "")
            .replace(R85_LEGACY_HUMAN_IDENTITY_LOCK_SUFFIX + ".", "")
            .replace(R85_LEGACY_HUMAN_IDENTITY_LOCK_SUFFIX, "")
            .replace(R85_DRONE_ALTITUDE_LOCK_CLAUSE + ".", "")
            .replace(R85_DRONE_ALTITUDE_LOCK_CLAUSE, "")
            .replace(R85_BRAIN_ANTI_VFX_NEGATIVE_CLAUSE + ".", "")
            .replace(R85_BRAIN_ANTI_VFX_NEGATIVE_CLAUSE, "")
            .strip()
        )
        if is_img_cond and c.get("context_split", True) is not False and grammar != "brain_simulator_3d":
            p_wc = count_words(prompt_for_wc)
            if not (cs_lo <= p_wc <= cs_hi):
                issues.append(
                    f"[prompt] clip {idx}: image-conditioned context-split prompt word count {p_wc} outside "
                    f"{cs_lo}-{cs_hi} words (strip room/lighting/material bloat and keep only camera + action + hand/expression) (R68)"
                )
        elif grammar != "brain_simulator_3d":
            wc = count_words(scene)
            if not (35 <= wc <= DIORAMA_SCENE_WORDS_MAX + 30):
                issues.append(
                    f"[prompt] clip {idx}: scene word count {wc} outside 35-{DIORAMA_SCENE_WORDS_MAX + 30} (R68)"
                )
        if is_r76 and grammar == "expressive_xray_brain":
            issues.append(
                f"[r76_brain_simulator] clip {idx}: R76 forbids Google Flow 'expressive_xray_brain'; use 'brain_simulator_3d' (R76)"
            )
        if "silent voice track" not in prompt_str.lower():
            issues.append(f"[prompt] clip {idx}: missing silent-voice foley audio clause (R68)")

        pos_frac = (idx - 0.5) / float(max(1, n_total))
        is_xray = grammar in ("expressive_xray_brain", "brain_simulator_3d") or bool(c.get("brain_clip"))
        if is_xray:
            if not is_brain_sim_only and not is_r85_flow_31_brain_plan(plan) and pos_frac < eff_premature_floor and not allow_early_override:
                premature_xray.append(idx)
            if is_brain_sim_only or tol_lo <= pos_frac <= tol_hi or (is_r74 and cam in EXPRESSIVE_V8_NEURAL_DIVE_MOVES and pos_frac >= 0.50):
                xray_in_window.append(idx)
            if core_rev_sent is not None:
                try:
                    cr_i = int(core_rev_sent)
                    s0_c = int(c.get("sentence_index") or 0)
                    s1_c = max(s0_c, int(c.get("end_sentence_index") or s0_c))
                    if s0_c <= cr_i <= s1_c:
                        core_sent_has_xray = True
                except (TypeError, ValueError):
                    pass
        if cameo_flag:
            cameo_clips.append(idx)

        from pipeline.config import is_r79m_character_motion_plan

        is_r79m = is_r79m_character_motion_plan(plan)
        prompt_for_v8_lint = (
            prompt_str.replace(R85_HUMAN_IDENTITY_LOCK_SUFFIX + ".", "")
            .replace(R85_HUMAN_IDENTITY_LOCK_SUFFIX, "")
            .replace(R85_LEGACY_HUMAN_IDENTITY_LOCK_SUFFIX + ".", "")
            .replace(R85_LEGACY_HUMAN_IDENTITY_LOCK_SUFFIX, "")
            .replace(R85_BRAIN_ANTI_VFX_NEGATIVE_CLAUSE + ".", "")
            .replace(R85_BRAIN_ANTI_VFX_NEGATIVE_CLAUSE, "")
            .strip()
        )
        v8_errs = validate_expressive_v8_scene(
            prompt_for_v8_lint,
            grammar=grammar,
            camera_move=cam,
            diegetic_text_allowlist=allow_list,
            cameo_easter_egg=cameo_flag,
            image_conditioned=(is_img_cond and c.get("context_split", True) is not False),
            allow_legacy_hardware=is_pre_r77_frozen,
            allow_legacy_r79m=(is_pre_r77_frozen and not is_r79m),
        )
        for err in v8_errs:
            issues.append(f"clip {idx}: {err}")
        if (
            is_r79m
            and grammar not in ("brain_simulator_3d", "expressive_xray_brain", "spatial_3d_arrow_diorama")
            and not bool(c.get("brain_clip"))
            and str(c.get("visual_register") or "") != "diagram"
            and cam not in EXPRESSIVE_V8_DRONE_CAMERA_MOVES
        ):
            raw_wo_g = prompt_str.replace(FLOW_CAMERA_HARDWARE_NEGATIVE_GUARD, "").strip()
            if not re.search(
                r"\b(?:man|woman|mother|father|son|daughter|doctor|neurologist|clinician|researcher|patient|husband|wife|figure|character|subject|hands|student|guard)\b",
                raw_wo_g,
                flags=re.IGNORECASE,
            ):
                issues.append(f"clip {idx}: [r79m_missing_subject] human character cut lacks an explicit cast subject noun (R79-M)")

    if not allow_legacy_clips and not is_brain_sim_only:
        flight_ratio = flight_clips / float(max(1, n_total))
        if flight_ratio < EXPRESSIVE_V8_MIN_3D_FLIGHT_RATIO:
            issues.append(
                f"[camera] R68 requires >= {int(EXPRESSIVE_V8_MIN_3D_FLIGHT_RATIO * 100)}% 3D flight/VIDEO_FRAMES clips "
                f"(got {flight_clips}/{n_total} = {flight_ratio:.0%}) (R68)"
            )
        if len(distinct_locations) < EXPRESSIVE_V8_MIN_DISTINCT_LOCATIONS:
            issues.append(
                f"[world] R68 requires >= {EXPRESSIVE_V8_MIN_DISTINCT_LOCATIONS} distinct location_id zones across clips "
                f"(got {len(distinct_locations)}: {sorted(distinct_locations)}) (R68)"
            )

    if premature_xray:
        issues.append(
            f"[xray_timing_v8] premature 3D brain reveal in clip(s) {premature_xray} before {int(tol_lo * 100)}% mark "
            "without allow_early_brain_override (R68)"
        )
    if core_rev_sent is not None and not core_sent_has_xray:
        issues.append(
            f"[xray_timing_v8] core_reveal_sentence_index={core_rev_sent} is not mapped to an 'expressive_xray_brain' clip (R68)"
        )
    if not xray_in_window:
        issues.append(
            f"[xray_timing_v8] missing 'expressive_xray_brain' reveal inside [{int(tol_lo * 100)}%-{int(tol_hi * 100)}%] "
            "mechanism window (R68)"
        )
    expected_cameo_count = 0 if (is_r76 or is_r85_flow_31_brain_plan(plan)) else 1
    if len(cameo_clips) != expected_cameo_count:
        issues.append(
            f"[cameo_v8] expected {expected_cameo_count} 'Mini-Cortex' cameo clip per episode, "
            f"got {len(cameo_clips)} ({cameo_clips}) ({'R76' if is_r76 else 'R68'})"
        )
    if bool((plan or {}).get("enforce_v83_camera_balance")) or bool((plan or {}).get("v8_3_mode")):
        issues.extend(validate_v83_camera_and_acting_balance(clips, plan))
    if is_r72 and not allow_legacy_clips:
        issues.extend(_validate_r72_open_world_issues(clips, plan)[0])
    return issues


def _validate_r72_open_world_issues(
    clips: list[dict[str, Any]],
    plan: dict[str, Any] | None = None,
    script_doc: dict[str, Any] | None = None,
) -> tuple[list[str], dict[str, Any]]:
    """
    Core Rule R72 + R72-R Open-World Architectural Scale, Drone Flight & Real-World Landmark Reference Validator:
      - `R72-1`: Supports BOTH Pattern A (`Clip 1` exterior landmark drone `K0->K1` -> `Clip 2` cutaway `K1->K2`)
                 AND Pattern B (`Clip 1` `<=2.60s` R73 US-native hook -> `Clip 2` exterior landmark drone `K0->K1` -> `Clip 3` cutaway `K1->K2`).
      - `R72-2`: `>= 35%` (`EXPRESSIVE_V8_MIN_OUTDOOR_OR_ARCH_RATIO`) outdoor / urban / architectural cutaway cuts.
      - `R72-3`: `<= 2` (`EXPRESSIVE_V8_MAX_CONSECUTIVE_SAME_INDOOR_LOC`) consecutive non-outdoor cuts sharing the same indoor `location_id`.
      - `R72-4`: `>= 35%` (`EXPRESSIVE_V8_MIN_DRONE_FLIGHT_RATIO`) drone/FPV/orbital flight camera moves (with `>= 2` dedicated `EXPRESSIVE_V8_DRONE_CAMERA_MOVES`) + real-world landmark/setting/apparatus reference conditioning (`R72-R`).
    """
    from pipeline.config import (
        EXPRESSIVE_V8_BRAIN_SIM_DRONE_MOVES,
        EXPRESSIVE_V8_R76_MIN_HUMAN_OUTDOOR_RATIO,
        EXPRESSIVE_V8_US_NATIVE_OPENING_MODES,
        is_r76_v8_plan,
        is_r82_dual_speed_pacing_plan,
    )
    from pipeline.depiction_rules import is_outdoor_or_architectural_clip

    issues: list[str] = []
    if not isinstance(clips, list) or len(clips) < 2:
        return issues, {"outdoor_ratio": 0.0, "drone_ratio": 0.0, "max_consec_indoor": 0}

    is_r76 = is_r76_v8_plan(plan, script_doc)
    is_r82 = is_r82_dual_speed_pacing_plan(plan, script_doc)
    n_total = len(clips)
    raw_vp_clips = list((plan or {}).get("clips") or [])
    drone_and_fpv_set = set(EXPRESSIVE_V8_DRONE_CAMERA_MOVES) | set(EXPRESSIVE_V8_BRAIN_SIM_DRONE_MOVES) | {
        "fpv_3d_flight",
        "crane_swoop_dive",
        "portal_dive_flight",
        "axial_portal_dive",
        "orbital_3d_arc_sweep",
        "dolly_zoom_vertigo",
        "whip_pan_occlusion",
    }
    cutaway_cams = (
        *EXPRESSIVE_V8_DRONE_CAMERA_MOVES,
        "portal_dive_flight",
        "axial_portal_dive",
        "fpv_3d_flight",
        "crane_swoop_dive",
    )

    def _merged_clip(idx0: int) -> dict[str, Any]:
        c_cur = clips[idx0] if isinstance(clips[idx0], dict) else {}
        vp_cur = raw_vp_clips[idx0] if idx0 < len(raw_vp_clips) and isinstance(raw_vp_clips[idx0], dict) else {}
        return {**vp_cur, **{k: v for k, v in c_cur.items() if v is not None}}

    vp_open = str((plan or {}).get("opening_mode") or (script_doc or {}).get("opening_mode") or "").strip().lower()
    m1 = _merged_clip(0)
    m2 = _merged_clip(1)
    explicit_bridge = list((plan or {}).get("r72_bridge_clips") or [])
    allow_pattern_b_s1_2cut = (
        len(clips) >= 4
        and (
            explicit_bridge == [3, 4]
            or (
                is_r82
                and int(m1.get("sentence_index") or 1) == 1
                and int(m2.get("sentence_index") or 2) == 1
                and int(_merged_clip(2).get("sentence_index") or 3) == 2
                and is_outdoor_or_architectural_clip(_merged_clip(2))
            )
        )
    )
    allow_pattern_b = (
        not allow_pattern_b_s1_2cut
        and not is_outdoor_or_architectural_clip(m1)
        and len(clips) >= 3
        and (
            vp_open in EXPRESSIVE_V8_US_NATIVE_OPENING_MODES
            or bool(m2.get("r72_cold_open_relay"))
            or explicit_bridge == [2, 3]
        )
        and is_outdoor_or_architectural_clip(m2)
    )
    if allow_pattern_b_s1_2cut:
        ext_m = _merged_clip(2)
        cut_m = _merged_clip(3)
        ext_lbl, cut_lbl = "clip 3", "clip 4"
        for hk_i, hk_m in ((1, m1), (2, m2)):
            if str(hk_m.get("camera_move") or hk_m.get("camera") or "").strip() == "locked_tripod":
                issues.append(
                    f"[r72_cold_open:R72-1] clip {hk_i} R73/R82 hook cannot use static 'locked_tripod' before S2 drone bridge (R72/R82)"
                )
    elif allow_pattern_b:
        ext_m = m2
        cut_m = _merged_clip(2)
        ext_lbl, cut_lbl = "clip 2", "clip 3"
        cam_hook = str(m1.get("camera_move") or m1.get("camera") or "").strip()
        if cam_hook == "locked_tripod":
            issues.append(
                "[r72_cold_open:R72-1] clip 1 R73 hook cannot use static 'locked_tripod' before S2 drone bridge (R72)"
            )
    else:
        ext_m = m1
        cut_m = m2
        ext_lbl, cut_lbl = "clip 1", "clip 2"

    cam_ext = str(ext_m.get("camera_move") or ext_m.get("camera") or "").strip()
    cam_cut = str(cut_m.get("camera_move") or cut_m.get("camera") or "").strip()
    g_cut = str(cut_m.get("grammar") or cut_m.get("visual_grammar") or "").strip()
    if not is_outdoor_or_architectural_clip(ext_m):
        issues.append(
            f"[r72_cold_open:R72-1] {ext_lbl} must open outdoors on an iconic exterior campus/urban landmark "
            "(got indoor/unmarked location_id without exterior environment) (R72)"
        )
    if cam_ext not in drone_and_fpv_set:
        issues.append(
            f"[r72_cold_open:R72-1] {ext_lbl} camera '{cam_ext}' must be an aerial drone or 3D FPV approach move (R72)"
        )
    ext_end = str(ext_m.get("end_reference_image") or ext_m.get("end_frame_image") or "").strip()
    cut_start = str(cut_m.get("reference_image") or cut_m.get("start_frame_image") or "").strip()
    if (plan or {}).get("r72_cold_open_relay") is not False and ext_end and cut_start and ext_end != cut_start:
        issues.append(
            f"[r72_cold_open:R72-1] {ext_lbl} -> {cut_lbl} Cold-Open Relay requires shared K1 keyframe "
            f"({ext_lbl} end '{ext_end}' != {cut_lbl} start '{cut_start}') (R72)"
        )
    if g_cut != "architectural_cutaway_portal" and cam_cut not in cutaway_cams and not is_outdoor_or_architectural_clip(cut_m):
        issues.append(
            f"[r72_cold_open:R72-1] {cut_lbl} must continue the exterior/architectural cutaway breach "
            f"(grammar='{g_cut}', camera='{cam_cut}') (R72)"
        )

    # R72-2, R72-3, R72-4 across full clip timeline
    outdoor_count = 0
    brain_count = 0
    drone_fpv_count = 0
    dedicated_drone_count = 0
    prev_indoor_loc = ""
    consec_indoor = 0
    max_consec_indoor = 0
    worst_indoor_loc = ""
    has_real_target_signal = bool((plan or {}).get("real_world_targets") or (plan or {}).get("primary_institution"))
    for anc in (plan or {}).get("reference_anchors") or []:
        if isinstance(anc, dict) and anc.get("real_world_target_id"):
            has_real_target_signal = True

    for idx0 in range(n_total):
        mc = _merged_clip(idx0)
        g_cur = str(mc.get("grammar") or mc.get("visual_grammar") or "").strip()
        cam_cur = str(mc.get("camera_move") or mc.get("camera") or "").strip()
        loc_cur = str(mc.get("location_id") or "").strip()
        is_brain_c = bool(mc.get("brain_clip")) or g_cur in ("expressive_xray_brain", "brain_simulator_3d")
        if is_brain_c:
            brain_count += 1
        is_out_c = (not is_brain_c if is_r82 else True) and is_outdoor_or_architectural_clip(mc)
        if mc.get("real_world_target_id"):
            has_real_target_signal = True
        if is_out_c:
            outdoor_count += 1
        if cam_cur in EXPRESSIVE_V8_DRONE_CAMERA_MOVES or cam_cur in EXPRESSIVE_V8_BRAIN_SIM_DRONE_MOVES:
            dedicated_drone_count += 1
            drone_fpv_count += 1
        elif cam_cur in drone_and_fpv_set:
            drone_fpv_count += 1

        if not is_out_c and not is_brain_c and loc_cur:
            if loc_cur == prev_indoor_loc:
                consec_indoor += 1
            else:
                prev_indoor_loc = loc_cur
                consec_indoor = 1
            if consec_indoor > max_consec_indoor:
                max_consec_indoor = consec_indoor
                worst_indoor_loc = loc_cur
        else:
            prev_indoor_loc = ""
            consec_indoor = 0

    from pipeline.config import is_r85_flow_31_brain_plan

    is_r85_ow = is_r85_flow_31_brain_plan(plan, script_doc)
    human_denom = max(1, n_total - brain_count) if (is_r76 or is_r85_ow) else max(1, n_total)
    outdoor_ratio = outdoor_count / float(human_denom)
    eff_min_out = float(
        EXPRESSIVE_V8_R76_MIN_HUMAN_OUTDOOR_RATIO
        if (is_r76 or is_r85_ow)
        else EXPRESSIVE_V8_MIN_OUTDOOR_OR_ARCH_RATIO
    )
    if not is_r85_ow and outdoor_ratio + 1e-6 < eff_min_out:
        issues.append(
            f"[r72_open_world_scale:R72-2] outdoor/architectural cuts {outdoor_count}/{human_denom} ({outdoor_ratio:.0%}) "
            f"< required {int(eff_min_out * 100)}% Open-World minimum ({'R76' if is_r76 else 'R72'})"
        )
    if not is_r85_ow and max_consec_indoor > EXPRESSIVE_V8_MAX_CONSECUTIVE_SAME_INDOOR_LOC:
        issues.append(
            f"[r72_indoor_stagnation:R72-3] {max_consec_indoor} consecutive indoor cuts share location_id "
            f"'{worst_indoor_loc}' (max allowed {EXPRESSIVE_V8_MAX_CONSECUTIVE_SAME_INDOOR_LOC}) (R72)"
        )
    drone_ratio = drone_fpv_count / float(n_total)
    if not is_r85_ow and (drone_ratio + 1e-6 < EXPRESSIVE_V8_MIN_DRONE_FLIGHT_RATIO or dedicated_drone_count < 2):
        issues.append(
            f"[r72_drone_flight:R72-4] drone/FPV flight ratio {drone_fpv_count}/{n_total} ({drone_ratio:.0%}, "
            f"dedicated_drone_moves={dedicated_drone_count}) below required "
            f"{int(EXPRESSIVE_V8_MIN_DRONE_FLIGHT_RATIO * 100)}% & >=2 dedicated drone moves (R72)"
        )

    if is_r82:
        inst_target_ids = {
            str(t.get("target_id") or "").strip()
            for t in ((plan or {}).get("real_world_targets") or [])
            if isinstance(t, dict) and str(t.get("category") or "").strip().lower() == "institution" and str(t.get("target_id") or "").strip()
        }
        sents_bridge = " ".join(str(x) for x in (((script_doc or {}).get("sentences") or [])[:4])).lower()
        inst_kw_hit = any(
            k in sents_bridge
            for k in (
                "university",
                "college",
                "institute",
                "hospital",
                "clinic",
                "medical center",
                "medical school",
                "school of medicine",
                "laboratory",
                "harvard",
                "stanford",
                "oxford",
                "cambridge",
                "johns hopkins",
                "mayo",
                "caltech",
                "yale",
                "columbia",
            )
        ) or bool(re.search(r"\b(ucl|mit|nih|ucla|ucsf|nyu)\b", sents_bridge))
        if inst_target_ids or inst_kw_hit:
            aerial_inst_cams = ("drone_aerial_approach", "drone_landmark_ascend", "drone_high_orbit_drop")
            has_act1_inst_drone = False
            if inst_target_ids:
                for idx0 in range(n_total):
                    mc_i = _merged_clip(idx0)
                    s_no_i = int(mc_i.get("sentence_index") or (idx0 + 1))
                    cam_i = str(mc_i.get("camera_move") or mc_i.get("camera") or "").strip()
                    tgt_i = str(mc_i.get("real_world_target_id") or "").strip()
                    if s_no_i <= 4 and cam_i in aerial_inst_cams and tgt_i in inst_target_ids:
                        has_act1_inst_drone = True
                        break
            if not has_act1_inst_drone:
                issues.append(
                    f"[r82_institution_drone] S01-S04 credibility bridge requires a dedicated aerial campus/institution drone shot "
                    f"({list(aerial_inst_cams)}) bound to a category='institution' real_world_target_id "
                    f"(declared={sorted(inst_target_ids)}) (R82)"
                )

    if EXPRESSIVE_V8_REQUIRE_REAL_LANDMARK_REFS and (plan or {}).get("require_real_landmark_refs", True) is not False:
        if not has_real_target_signal:
            issues.append(
                "[r72_real_world_refs:R72-R] episode lacks real-world landmark/setting/apparatus reference target "
                "(declare 'real_world_targets' or 'real_world_target_id' on clips/anchors) (R72-R)"
            )
        p_dir_hint = (plan or {}).get("_project_dir") or (plan or {}).get("project_dir")
        if p_dir_hint:
            mf_p = Path(str(p_dir_hint)) / "03_visuals" / REAL_WORLD_REFS_MANIFEST_FILENAME
            if mf_p.is_file():
                try:
                    mf_doc = json.loads(mf_p.read_text(encoding="utf-8"))
                    if not bool(mf_doc.get("quarantine_purged")):
                        issues.append("[r72_real_world_refs:R72-R] real_world_refs_manifest.json reports quarantine_purged=False (R72-R)")
                    if mf_doc.get("all_rq_real_passed") is False:
                        issues.append("[r72_real_world_refs:R72-R] real_world_refs_manifest.json reports all_rq_real_passed=False (R72-R)")
                except Exception:
                    issues.append("[r72_real_world_refs:R72-R] corrupt real_world_refs_manifest.json (R72-R)")
    metrics = {
        "outdoor_count": outdoor_count,
        "outdoor_ratio": round(outdoor_ratio, 4),
        "drone_fpv_count": drone_fpv_count,
        "dedicated_drone_count": dedicated_drone_count,
        "drone_ratio": round(drone_ratio, 4),
        "max_consec_indoor": max_consec_indoor,
        "relay_pattern": "pattern_b_s2_s3" if allow_pattern_b else "pattern_a_s1_s2",
    }
    return issues, metrics


def validate_r72_open_world_drone_and_real_refs(
    clips_or_plan: list[dict[str, Any]] | dict[str, Any],
    plan: dict[str, Any] | None = None,
    *,
    script_doc: dict[str, Any] | None = None,
) -> Any:
    """
    Public R72 + R72-R validator:
      - When passed a `visual_plan` dict as first argument (`validate_r72_open_world_drone_and_real_refs(plan, script_doc=...)`),
        returns a structured report dict `{"passed": bool, "issues": [...], ...}`.
      - When passed `(clips_list, plan_dict)`, returns `list[str]` of issues.
    """
    if isinstance(clips_or_plan, dict):
        vp_dict = clips_or_plan
        c_list = list(vp_dict.get("clips") or [])
        iss, met = _validate_r72_open_world_issues(c_list, vp_dict, script_doc=script_doc)
        return {"passed": len(iss) == 0, "issues": iss, **met}
    iss, _ = _validate_r72_open_world_issues(clips_or_plan, plan, script_doc=script_doc)
    return iss


def validate_v83_camera_and_acting_balance(
    clips: list[dict[str, Any]],
    plan: dict[str, Any] | None = None,
) -> list[str]:
    """
    Enforces Schema v8.3 (`R55-B`, `C4`) camera balance & gaze-lock rules:
      1. Fast `fpv_dive_glide` ratio `<= EXPRESSIVE_V8_CAMERA_FAST_FPV_MAX_RATIO` (`25%`).
      2. `orbital_3d_arc_sweep` ratio `<= EXPRESSIVE_V8_CAMERA_ORBIT_MAX_RATIO` (`30%`), and forbids combining
         `orbital_3d_arc_sweep` with `portal_to_brain` (multi-scale zoom + orbit collision).
      3. Locked / reaction close-up cuts (`locked_tripod`, `tilt_up`, `tilt_down`, or `grammar == 'expressive_reaction_closeup'`)
         ratio `>= EXPRESSIVE_V8_CAMERA_LOCKED_MIN_RATIO` (`15%`).
    """
    issues: list[str] = []
    if not isinstance(clips, list) or not clips:
        return issues
    n_total = len(clips)
    fpv_count = 0
    orbit_count = 0
    locked_or_reaction_count = 0
    for idx, c in enumerate(clips, start=1):
        if not isinstance(c, dict):
            continue
        cam = str(c.get("camera_move") or c.get("camera") or "").strip()
        grammar = str(c.get("grammar") or "").strip()
        portal = bool(c.get("portal_to_brain"))
        if cam == "fpv_dive_glide":
            fpv_count += 1
        if cam == "orbital_3d_arc_sweep":
            orbit_count += 1
            if portal:
                issues.append(
                    f"[camera_v83:R55-B] clip {idx} combines 'orbital_3d_arc_sweep' with portal_to_brain "
                    "(use 'fpv_dive_glide' or 'gentle_push_in' for axial portal dives; keep orbit single-scale)"
                )
        if cam in ("locked_tripod", "tilt_up", "tilt_down") or grammar == "expressive_reaction_closeup":
            locked_or_reaction_count += 1

    fpv_ratio = fpv_count / float(n_total)
    orbit_ratio = orbit_count / float(n_total)
    locked_ratio = locked_or_reaction_count / float(n_total)
    if fpv_ratio > EXPRESSIVE_V8_CAMERA_FAST_FPV_MAX_RATIO + 1e-6:
        issues.append(
            f"[camera_v83:R55-B] fast 'fpv_dive_glide' ratio {fpv_count}/{n_total} ({fpv_ratio:.0%}) "
            f"exceeds {int(EXPRESSIVE_V8_CAMERA_FAST_FPV_MAX_RATIO * 100)}% ceiling (use gentle_push_in for calm Z-axis push)"
        )
    if orbit_ratio > EXPRESSIVE_V8_CAMERA_ORBIT_MAX_RATIO + 1e-6:
        issues.append(
            f"[camera_v83:R55-B] 'orbital_3d_arc_sweep' ratio {orbit_count}/{n_total} ({orbit_ratio:.0%}) "
            f"exceeds {int(EXPRESSIVE_V8_CAMERA_ORBIT_MAX_RATIO * 100)}% ceiling"
        )
    if locked_ratio + 1e-6 < EXPRESSIVE_V8_CAMERA_LOCKED_MIN_RATIO:
        issues.append(
            f"[camera_v83:R55-B] locked/reaction cuts {locked_or_reaction_count}/{n_total} ({locked_ratio:.0%}) "
            f"below {int(EXPRESSIVE_V8_CAMERA_LOCKED_MIN_RATIO * 100)}% floor"
        )
    _ = plan
    return issues


def build_diorama_v7_prompts(
    visual_plan: dict[str, Any],
    narrations: list[str] | None = None,
    aspect: str = FLOW_ASPECT_SHORTS,
) -> list[dict[str, Any]]:
    """Renders Schema v7/v8 (`porcelain_cinematic_v7`, `lowpoly_pastel_v7`, or `expressive_25d_v8`) clip prompts (R63/R66/R68)."""
    if is_expressive_v8_plan(visual_plan):
        return build_expressive_v8_prompts(visual_plan, narrations=narrations, aspect=aspect)
    from pipeline.depiction_rules import (
        ContainedLiving3DBrainRule,
        DioramaV7PromptComposer,
        PorcelainV7PromptComposer,
        normalize_porcelain_v7_brain_mode,
        normalize_porcelain_v7_grammar,
    )

    from pipeline.config import MICRO_SHORT_CUT_MIN, MICRO_SHORT_PROFILE, resolve_shorts_format_profile

    raw_clips = visual_plan.get("clips") if isinstance(visual_plan.get("clips"), list) else []
    min_v7_clips = (
        MICRO_SHORT_CUT_MIN
        if resolve_shorts_format_profile(visual_plan) == MICRO_SHORT_PROFILE
        else DIORAMA_CLIP_COUNT_MIN
    )
    if not (min_v7_clips <= len(raw_clips) <= DIORAMA_CLIP_COUNT_MAX):
        raise ValueError(
            f"Schema v7 visual_plan.clips must contain {min_v7_clips}-{DIORAMA_CLIP_COUNT_MAX} clip specs "
            f"(got {len(raw_clips)})"
        )
    use_porcelain = is_porcelain_v7_plan(visual_plan)
    resolved_style = resolve_diorama_v7_style_profile(visual_plan)
    mode = str(visual_plan.get("visual_mode") or "NEURO_BIOLOGY").upper()
    thumb_cfg = visual_plan.get("thumbnail") if isinstance(visual_plan.get("thumbnail"), dict) else {}
    cover_sent_idx = int(thumb_cfg.get("cover_sentence_index") or 0) if thumb_cfg else 0
    hero_clause = (
        "Single focal subject centered in crisp silhouette against a clean bright high-key studio backdrop"
        if use_porcelain
        else "Single focal subject centered in crisp silhouette against an uncluttered pastel backdrop"
    )
    default_cam_cycle = (
        "locked_tripod",
        "pan_right",
        "locked_tripod",
        "gentle_push_in",
        "pan_left",
        "locked_tripod",
        "tilt_up",
        "locked_tripod",
        "tilt_down",
        "clean_pullback_reveal",
    )
    engine_map = assign_hero_omni_engines(visual_plan)
    out: list[dict[str, Any]] = []
    for idx, spec in enumerate(raw_clips, start=1):
        if not isinstance(spec, dict):
            raise ValueError(f"Schema v7 clip {idx} must be a dict")
        if use_porcelain:
            raw_g = str(spec.get("grammar") or spec.get("visual_grammar") or "porcelain_fullbleed_world").strip()
            grammar = normalize_porcelain_v7_grammar(raw_g)
        else:
            grammar = str(spec.get("grammar") or spec.get("visual_grammar") or "lowpoly_fullbleed_world").strip()
        explicit_cam = str(spec.get("camera") or spec.get("camera_move") or "").strip()
        if explicit_cam:
            cam = explicit_cam
        elif str(spec.get("cut_role") or "").strip().lower() == "outro":
            cam = "tilt_up"
        else:
            cam = default_cam_cycle[(idx - 1) % len(default_cam_cycle)]
            if grammar in ("lowpoly_hands_closeup", "porcelain_hands_closeup") and cam in ("tilt_up", "clean_pullback_reveal"):
                cam = "locked_tripod" if cam == "tilt_up" else "gentle_push_in"
        act_no = int(spec.get("act") or min(6, ((idx - 1) * 6) // max(1, len(raw_clips)) + 1))
        spec_for_scene = {**spec, "grammar": grammar}
        scene_body = sanitize_diorama_scene_for_flow(_compose_diorama_v7_clip_scene(spec_for_scene, style_profile=resolved_style))
        if (
            cover_sent_idx > 0
            and int(spec.get("sentence_index") or 0) == cover_sent_idx
            and grammar in ("lowpoly_fullbleed_world", "porcelain_fullbleed_world")
            and hero_clause.lower() not in scene_body.lower()
            and count_words(scene_body) + count_words(hero_clause) <= DIORAMA_SCENE_WORDS_MAX + 18
        ):
            scene_body = f"{scene_body.rstrip('.')}. {hero_clause}."
        render_sec = int(spec.get("render_sec") or DIORAMA_CLIP_RENDER_SEC)
        if use_porcelain:
            prompt_str = PorcelainV7PromptComposer.compose_clip_prompt(
                scene_body=scene_body,
                grammar=grammar,
                camera_move=cam,
                aspect=aspect,
                render_sec=render_sec,
            )
            explicit_bm = spec.get("brain_mode") if spec.get("brain_mode") else spec.get("render_mode")
            if grammar == "porcelain_living_brain":
                brain_mode_val = (
                    ContainedLiving3DBrainRule.resolve_brain_mode(explicit_bm)
                    if explicit_bm
                    else normalize_porcelain_v7_brain_mode(scene_text=scene_body)
                )
            else:
                brain_mode_val = spec.get("brain_mode")
        else:
            prompt_str = DioramaV7PromptComposer.compose_clip_prompt(
                scene_body=scene_body,
                grammar=grammar,
                camera_move=cam,
                aspect=aspect,
                render_sec=render_sec,
            )
            brain_mode_val = spec.get("brain_mode")
        is_brain = grammar in ("lowpoly_matte_brain", "porcelain_living_brain")
        out.append(
            {
                "clip_number": idx,
                "clip_index": idx,
                "act": act_no,
                "grammar": grammar,
                "role": f"act{act_no}_{grammar}",
                "setting": ("brain_studio" if is_brain else "real_env"),
                "camera_move": cam,
                "target_duration": f"{render_sec}s",
                "expected_syllables": 0,
                "estimated_speech_sec": 0.0,
                "cutoff_risk": False,
                "motif_present": False,
                "location_id": spec.get("location_id"),
                "environment": spec.get("environment"),
                "real_world_target_id": spec.get("real_world_target_id"),
                "scene_id": spec.get("scene_id") or f"act{act_no}_clip{idx}",
                "shot_type": spec.get("shot_type") or _shot_type_from_camera(cam),
                "brain_clip": is_brain,
                "brain_mode": brain_mode_val,
                "brain_region": spec.get("brain_region"),
                "anatomy_label": spec.get("anatomy_label"),
                "sentence_index": spec.get("sentence_index"),
                "end_sentence_index": spec.get("end_sentence_index"),
                "beat_index": spec.get("beat_index"),
                "beat_weight": spec.get("beat_weight"),
                "cut_role": spec.get("cut_role"),
                "reference_image": spec.get("reference_image"),
                "end_reference_image": spec.get("end_reference_image"),
                "engine": engine_map.get(idx, "auto"),
                "source_shot_id": spec.get("source_shot_id"),
                "aspect": aspect,
                "schema_version": PROMPT_SCHEMA_VERSION_V7,
                "style_profile": resolved_style,
                "profile": "neuro_diorama",
                "visual_mode": mode,
                "scene": scene_body,
                "spoken_narration": "",
                "prompt": prompt_str,
                "full_prompt": prompt_str,
            }
        )
    _ = narrations
    return out


def validate_diorama_v7_prompts(
    clips: list[dict[str, Any]],
    plan: dict[str, Any] | None = None,
) -> list[str]:
    """Structural & R63/R66/R68 forensic prompt validator for Schema v7/v8 (`porcelain_cinematic_v7`, `lowpoly_pastel_v7`, or `expressive_25d_v8`)."""
    if is_expressive_v8_plan(plan, *(clips if isinstance(clips, list) else ())):
        return validate_expressive_v8_prompts(clips, plan=plan)
    from pipeline.config import MICRO_SHORT_CUT_MIN, MICRO_SHORT_PROFILE, resolve_shorts_format_profile
    from pipeline.depiction_rules import (
        DIORAMA_V7_CAMERA_DESCRIPTORS,
        PORCELAIN_V7_CAMERA_DESCRIPTORS,
        validate_lowpoly_v7_scene,
        validate_porcelain_v7_scene,
    )

    issues: list[str] = []
    min_v7_clips = (
        MICRO_SHORT_CUT_MIN
        if resolve_shorts_format_profile(plan) == MICRO_SHORT_PROFILE
        else DIORAMA_CLIP_COUNT_MIN
    )
    if not isinstance(clips, list) or not (min_v7_clips <= len(clips) <= DIORAMA_CLIP_COUNT_MAX):
        return [
            f"[prompt] Schema v7 clip count must be {min_v7_clips}-{DIORAMA_CLIP_COUNT_MAX} "
            f"(got {len(clips) if isinstance(clips, list) else 0}) (R63)"
        ]
    grammars_present = [str(c.get("grammar") or "") for c in clips if isinstance(c, dict)]
    has_porcelain_g = any(g in PORCELAIN_V7_VISUAL_GRAMMARS or g.startswith("porcelain_") for g in grammars_present)
    has_lowpoly_g = any(g in DIORAMA_V7_VISUAL_GRAMMARS or g.startswith("lowpoly_") for g in grammars_present)
    porcelain_flags = [is_porcelain_v7_plan(c) for c in clips if isinstance(c, dict)]
    use_porcelain = is_porcelain_v7_plan(plan) if isinstance(plan, dict) else (has_porcelain_g or any(porcelain_flags))
    if (has_porcelain_g and has_lowpoly_g) or (any(porcelain_flags) and not all(porcelain_flags)):
        issues.append(
            "[prompt] episode mixes porcelain_cinematic_v7 and lowpoly_pastel_v7 grammars/profiles "
            f"(clips must be uniformly {PORCELAIN_V7_STYLE_PROFILE} or {DIORAMA_V7_STYLE_PROFILE}) (R66)"
        )
    elif isinstance(plan, dict):
        expected_style = PORCELAIN_V7_STYLE_PROFILE if use_porcelain else DIORAMA_V7_STYLE_PROFILE
        if (use_porcelain and (has_lowpoly_g or (porcelain_flags and not any(porcelain_flags)))) or (
            (not use_porcelain) and (has_porcelain_g or any(porcelain_flags))
        ):
            actual_style = DIORAMA_V7_STYLE_PROFILE if use_porcelain else PORCELAIN_V7_STYLE_PROFILE
            issues.append(
                f"[prompt] visual_plan style_profile '{expected_style}' mismatches rendered clips style_profile '{actual_style}'; "
                "re-render flow_all_in_one_prompts.json after changing style_profile (R63/R66)"
            )
    allowed_grammars = PORCELAIN_V7_VISUAL_GRAMMARS if use_porcelain else DIORAMA_V7_VISUAL_GRAMMARS
    cutaway_grammar = "porcelain_cutaway_section" if use_porcelain else "lowpoly_cutaway_section"
    cam_descriptors = PORCELAIN_V7_CAMERA_DESCRIPTORS if use_porcelain else DIORAMA_V7_CAMERA_DESCRIPTORS
    rule_tag = "R66" if use_porcelain else "R63"
    cam_counts: dict[str, int] = {m: 0 for m in DIORAMA_V7_CAMERA_MOVES}
    cutaway_count = 0
    for idx, c in enumerate(clips, start=1):
        if not isinstance(c, dict):
            issues.append(f"[prompt] clip {idx} is not a dict")
            continue
        grammar = str(c.get("grammar") or "")
        cam = str(c.get("camera_move") or "")
        scene = str(c.get("scene") or "")
        prompt_str = str(c.get("prompt") or c.get("full_prompt") or "")
        if grammar not in allowed_grammars:
            issues.append(f"[prompt] clip {idx}: invalid v7 grammar '{grammar}' (must be in {list(allowed_grammars)}) ({rule_tag})")
        if grammar == cutaway_grammar:
            cutaway_count += 1
        if cam not in DIORAMA_V7_CAMERA_MOVES:
            issues.append(f"[prompt] clip {idx}: camera '{cam}' must be one of {list(DIORAMA_V7_CAMERA_MOVES)} ({rule_tag})")
        else:
            cam_counts[cam] = cam_counts.get(cam, 0) + 1
            desc = cam_descriptors[cam]
            alt_desc = DIORAMA_V7_CAMERA_DESCRIPTORS[cam]
            cnt = prompt_str.count(desc)
            if cnt == 0 and alt_desc != desc:
                cnt = prompt_str.count(alt_desc)
            if cnt != 1:
                issues.append(f"[prompt] clip {idx}: camera clause must appear exactly once (found {cnt}) ({rule_tag})")
        wc = count_words(scene)
        if not (DIORAMA_SCENE_WORDS_MIN <= wc <= DIORAMA_SCENE_WORDS_MAX + 20):
            issues.append(
                f"[prompt] clip {idx}: scene word count {wc} outside {DIORAMA_SCENE_WORDS_MIN}-{DIORAMA_SCENE_WORDS_MAX + 20} ({rule_tag})"
            )
        if "silent voice track" not in prompt_str.lower():
            issues.append(f"[prompt] clip {idx}: missing silent-voice ambient audio clause ({rule_tag})")
        if use_porcelain:
            from pipeline.config import FROZEN_PRE_SCHEMA_V2_DOSSIER_SLUGS, FROZEN_PRE_SCHEMA_V2_PROJECT_PREFIXES

            plan_pid = str((plan or {}).get("project_id") or "").strip().lower()
            plan_slug = str((plan or {}).get("dossier") or "").strip().lower()
            is_frozen_pre_v2 = bool(
                any(plan_pid.startswith(pfx.lower()) for pfx in FROZEN_PRE_SCHEMA_V2_PROJECT_PREFIXES)
                or (plan_slug and plan_slug in FROZEN_PRE_SCHEMA_V2_DOSSIER_SLUGS and not plan_pid)
            )
            v7_errs = validate_porcelain_v7_scene(
                prompt_str,
                grammar=grammar,
                camera_move=cam,
                allow_legacy_frosted_cranium=is_frozen_pre_v2,
            )
        else:
            v7_errs = validate_lowpoly_v7_scene(prompt_str, grammar=grammar, camera_move=cam)
        for v7_err in v7_errs:
            issues.append(f"clip {idx}: {v7_err}")

    n_total = max(1, len(clips))
    locked_ratio = cam_counts.get("locked_tripod", 0) / float(n_total)
    zoom_ratio = (cam_counts.get("gentle_push_in", 0) + cam_counts.get("clean_pullback_reveal", 0)) / float(n_total)
    cutaway_ratio = cutaway_count / float(n_total)
    if locked_ratio < DIORAMA_V7_LOCKED_CAMERA_MIN_RATIO:
        issues.append(
            f"[camera] locked_tripod ratio {locked_ratio:.2f} < {DIORAMA_V7_LOCKED_CAMERA_MIN_RATIO:.2f} "
            f"(need ~40% tripod lock-off for internal prop/hand focus) ({rule_tag})"
        )
    if zoom_ratio > DIORAMA_V7_ZOOM_CAMERA_MAX_RATIO:
        issues.append(
            f"[camera] push/pull zoom ratio {zoom_ratio:.2f} > {DIORAMA_V7_ZOOM_CAMERA_MAX_RATIO:.2f} ({rule_tag})"
        )
    if cam_counts.get("pan_left", 0) == 0 or cam_counts.get("pan_right", 0) == 0:
        issues.append(
            f"[camera] pan direction imbalance: pan_left={cam_counts.get('pan_left', 0)}, pan_right={cam_counts.get('pan_right', 0)} "
            f"(both left and right orthogonal pans required) ({rule_tag})"
        )
    if cutaway_ratio > DIORAMA_V7_CUTAWAY_MAX_RATIO:
        issues.append(
            f"[world] {cutaway_grammar} ratio {cutaway_ratio:.2f} > max {DIORAMA_V7_CUTAWAY_MAX_RATIO:.2f} "
            f"(>=85% of cuts must be full-bleed world/hands/brain scenes) ({rule_tag})"
        )
    return issues


def build_diorama_v6_prompts(
    visual_plan: dict[str, Any],
    narrations: list[str] | None = None,
    aspect: str = FLOW_ASPECT_SHORTS,
) -> list[dict[str, Any]]:
    """
    Renders Schema v6 (`neuro_diorama`) or Schema v7 (`porcelain_cinematic_v7` / `lowpoly_pastel_v7`) base motion clip prompts.
    """
    if is_diorama_v7_plan(visual_plan):
        return build_diorama_v7_prompts(visual_plan, narrations=narrations, aspect=aspect)
    from pipeline.config import DEFAULT_DIORAMA_CAMERA_PROFILE, DIORAMA_DYNAMIC_3D_CAMERA_MOVES
    from pipeline.depiction_rules import DioramaPromptComposer

    raw_clips = visual_plan.get("clips") if isinstance(visual_plan.get("clips"), list) else []
    if not (DIORAMA_CLIP_COUNT_MIN <= len(raw_clips) <= DIORAMA_CLIP_COUNT_MAX):
        raise ValueError(
            f"neuro_diorama visual_plan.clips must contain {DIORAMA_CLIP_COUNT_MIN}-{DIORAMA_CLIP_COUNT_MAX} base clip specs "
            f"(got {len(raw_clips)})"
        )
    motif_prop = visual_plan.get("motif_prop") if isinstance(visual_plan.get("motif_prop"), dict) else {}
    mode = str(visual_plan.get("visual_mode") or "NEURO_BIOLOGY").upper()
    cam_profile = str(visual_plan.get("camera_profile") or DEFAULT_DIORAMA_CAMERA_PROFILE).strip().lower()
    engine_map = assign_hero_omni_engines(visual_plan)
    out: list[dict[str, Any]] = []
    for idx, spec in enumerate(raw_clips, start=1):
        if not isinstance(spec, dict):
            raise ValueError(f"neuro_diorama clip {idx} must be a dict")
        grammar = str(spec.get("grammar") or "arch_cutaway_diorama").strip()
        explicit_cam = str(spec.get("camera") or "").strip()
        if explicit_cam:
            cam = explicit_cam
        elif str(spec.get("cut_role") or "").strip().lower() == "outro":
            cam = "smooth_tilt_up"
        elif cam_profile == "dynamic_3d_cinema_rig":
            if grammar in ("arch_brain_maquette", "frosted_crystal_specimen"):
                cam = ("orbital_3d_arc_sweep", "dynamic_dolly_rush_in", "vertical_rocket_ascent", "crane_swoop_dive")[(idx - 1) % 4]
            elif grammar in ("recurring_gauge_motif", "tactile_token_grid"):
                cam = ("dynamic_dolly_rush_in", "orbital_3d_arc_sweep", "pullback_parallax_reveal", "low_angle_chase_track")[(idx - 1) % 4]
            else:
                cam = DIORAMA_DYNAMIC_3D_CAMERA_MOVES[(idx - 1) % len(DIORAMA_DYNAMIC_3D_CAMERA_MOVES)]
        else:
            cam = "isometric_push_in"
        spec_with_cam = {**spec, "camera": cam}
        act_no = int(spec.get("act") or min(6, ((idx - 1) * 6) // max(1, len(raw_clips)) + 1))
        scene_body = sanitize_diorama_scene_for_flow(_compose_diorama_clip_scene(spec_with_cam, motif_prop=motif_prop))
        render_sec = int(spec.get("render_sec") or DIORAMA_CLIP_RENDER_SEC)
        prompt_str = DioramaPromptComposer.compose_clip_prompt(
            scene_body=scene_body,
            grammar=grammar,
            camera_move=cam,
            aspect=aspect,
            render_sec=render_sec,
        )
        clip_entry: dict[str, Any] = {
            "clip_number": idx,
            "clip_index": idx,
            "act": act_no,
            "grammar": grammar,
            "role": f"act{act_no}_{grammar}",
            "setting": ("brain_void" if grammar in ("arch_brain_maquette", "frosted_crystal_specimen") else "real_env"),
            "camera_move": cam,
            "target_duration": f"{render_sec}s",
            "expected_syllables": 0,
            "estimated_speech_sec": 0.0,
            "cutoff_risk": False,
            "motif_present": bool(spec.get("motif_present") or grammar == "recurring_gauge_motif"),
            "scene_id": spec.get("scene_id") or f"act{act_no}_clip{idx}",
            "shot_type": spec.get("shot_type") or _shot_type_from_camera(cam),
            "brain_clip": grammar in ("arch_brain_maquette", "frosted_crystal_specimen"),
            "brain_mode": spec.get("brain_mode"),
            "sentence_index": spec.get("sentence_index"),
            "beat_index": spec.get("beat_index"),
            "cut_role": spec.get("cut_role"),
            "reference_image": spec.get("reference_image"),
            "engine": engine_map.get(idx, "auto"),
            "aspect": aspect,
            "schema_version": PROMPT_SCHEMA_VERSION_V6,
            "profile": "neuro_diorama",
            "visual_mode": mode,
            "scene": scene_body,
            "spoken_narration": "",
            "prompt": prompt_str,
            "full_prompt": prompt_str,
        }
        out.append(clip_entry)
    _ = narrations
    return out


def validate_diorama_v6_prompts(
    clips: list[dict[str, Any]],
    plan: dict[str, Any] | None = None,
) -> list[str]:
    """Structural & R56/R63/R66 prompt validator for Schema v6 or Schema v7 `neuro_diorama` clip prompts."""
    if (isinstance(plan, dict) and is_diorama_v7_plan(plan)) or (
        isinstance(clips, list)
        and clips
        and any(int(c.get("schema_version") or 0) >= PROMPT_SCHEMA_VERSION_V7 for c in clips if isinstance(c, dict))
    ):
        return validate_diorama_v7_prompts(clips, plan=plan)
    from pipeline.depiction_rules import validate_zero_flesh_and_crystal_specimen

    issues: list[str] = []
    if not isinstance(clips, list) or not (DIORAMA_CLIP_COUNT_MIN <= len(clips) <= DIORAMA_CLIP_COUNT_MAX):
        return [
            f"[prompt] neuro_diorama clip count must be {DIORAMA_CLIP_COUNT_MIN}-{DIORAMA_CLIP_COUNT_MAX} "
            f"(got {len(clips) if isinstance(clips, list) else 0}) (R58)"
        ]
    for idx, c in enumerate(clips, start=1):
        if not isinstance(c, dict):
            issues.append(f"[prompt] clip {idx} is not a dict")
            continue
        grammar = str(c.get("grammar") or "")
        cam = str(c.get("camera_move") or "")
        scene = str(c.get("scene") or "")
        prompt_str = str(c.get("prompt") or c.get("full_prompt") or "")
        if grammar not in DIORAMA_VISUAL_GRAMMARS:
            issues.append(f"[prompt] clip {idx}: invalid grammar '{grammar}' (must be in {list(DIORAMA_VISUAL_GRAMMARS)}) (R56)")
        if cam not in DIORAMA_CAMERA_MOVES:
            issues.append(f"[prompt] clip {idx}: camera '{cam}' must be one of {list(DIORAMA_CAMERA_MOVES)} (R56)")
        wc = count_words(scene)
        if not (DIORAMA_SCENE_WORDS_MIN <= wc <= DIORAMA_SCENE_WORDS_MAX):
            issues.append(
                f"[prompt] clip {idx}: scene word count {wc} outside {DIORAMA_SCENE_WORDS_MIN}-{DIORAMA_SCENE_WORDS_MAX} (R56)"
            )
        if "zero text, zero letters" not in prompt_str.lower():
            issues.append(f"[prompt] clip {idx}: missing zero-in-scene-text negative lock (R56)")
        if "no speech, no narration" not in prompt_str.lower():
            issues.append(f"[prompt] clip {idx}: missing ambient-only audio lock (R58)")
        for z_err in validate_zero_flesh_and_crystal_specimen(scene, grammar=grammar):
            issues.append(f"clip {idx}: {z_err}")
    return issues


def build_flow_prompts(
    visual_plan: dict[str, Any] | None,
    narrations: list[str],
    voice: str = FLOW_DEFAULT_VOICE,
    aspect: str = FLOW_ASPECT_SHORTS,
) -> list[dict[str, Any]]:
    """
    Builds 5-10 Google Flow clip prompt dicts from a visual_plan and per-clip narrations,
    or Schema v6/v7 `neuro_diorama` base motion clip dicts when `is_diorama_v6_plan(visual_plan)` is True.
    """
    if is_diorama_v7_plan(visual_plan):
        return build_diorama_v7_prompts(visual_plan or {}, narrations=narrations, aspect=aspect)
    if is_diorama_v6_plan(visual_plan):
        return build_diorama_v6_prompts(visual_plan or {}, narrations=narrations, aspect=aspect)
    cleaned_narrs = [str(n).strip() for n in (narrations or []) if str(n).strip()]
    n_clips = len(cleaned_narrs)
    roles = clip_roles(n_clips)
    plan = normalize_visual_plan(visual_plan)
    explicit_scenes = (visual_plan or {}).get("scenes") if isinstance((visual_plan or {}).get("scenes"), dict) else {}
    v5 = is_v5_plan(visual_plan)
    mode = plan_visual_mode(visual_plan)

    clips: list[dict[str, Any]] = []
    for idx, (role, narr) in enumerate(zip(roles, cleaned_narrs), start=1):
        setting = resolve_clip_setting(visual_plan, role)
        shot = _shot(visual_plan, role) if v5 else {}
        if role in explicit_scenes and str(explicit_scenes[role]).strip():
            scene = str(explicit_scenes[role]).strip()
            if setting in BRAIN_SETTINGS and "architectural cross-section cutaway" not in scene.lower():
                cand = re.sub(
                    r"\bholding a realistic matte-white brain(?:\s+with\s+visible\s+gyri\s+and\s+sulci)?\b",
                    "holding an architectural cross-section cutaway of a matte-white brain",
                    scene,
                )
                if count_words(cand) <= PROMPT_SCENE_WORDS_MAX:
                    scene = cand
            if any(rx.search(scene) for _, rx in _PROP_REGEXES):
                scene = sanitize_prompt_for_flow(scene, is_spoken_dialogue=False)
                fillers = _BRAIN_FILLERS if setting in BRAIN_SETTINGS else _REAL_ENV_FILLERS
                for filler in fillers:
                    if count_words(scene) >= PROMPT_SCENE_WORDS_MIN:
                        break
                    if count_words(scene) + count_words(filler) <= PROMPT_SCENE_WORDS_MAX and filler not in scene:
                        scene = f"{scene.rstrip('.')}." + f" {filler}"
                if count_words(scene) > PROMPT_SCENE_WORDS_MAX:
                    scene = _cap_words(scene, PROMPT_SCENE_WORDS_MAX) + "."
        elif v5 and shot.get("action"):
            scene = compose_shot_scene(visual_plan, role)
        elif v5 and setting == "real_env":
            raise ValueError(
                f"v5 plan clip {idx} ({role}) is a real_env reenactment: author visual_plan.scenes['{role}'] "
                f"or visual_plan.shots['{role}'] (camera, action, prop_change, reaction)."
            )
        elif v5:
            scene = _v4_template_for_setting(setting, role, plan)
        else:
            scene = compose_scene(role, plan)
        if v5:
            from pipeline.depiction_rules import BrainDepictionRule

            if setting in BRAIN_SETTINGS:
                scene = BrainDepictionRule.sanitize_brain_signal_text(scene)
                v5_suffix = BrainDepictionRule.RESTRAINT_LOCK
            else:
                v5_suffix = FLOW_MOTION_STYLE_V5
            prompt_str = render_prompt(
                scene=scene,
                narration=narr,
                voice=voice,
                aspect=aspect,
                style_suffix=v5_suffix,
                voice_label=FLOW_VOICE_PROMPT_DESCRIPTOR_V5,
            )
        else:
            prompt_str = render_prompt(scene=scene, narration=narr, voice=voice, aspect=aspect)
        dur_meta = compute_clip_target_duration(narr, role=role)
        clip = {
            "clip_number": idx,
            "role": role,
            "setting": setting,
            "camera_move": (shot.get("camera") if v5 and shot.get("camera") else ROLE_CAMERA_MOVES[role]),
            "target_duration": dur_meta["target_duration"],
            "expected_syllables": dur_meta["expected_syllables"],
            "estimated_speech_sec": dur_meta["estimated_speech_sec"],
            "cutoff_risk": dur_meta["cutoff_risk"],
            "scene": scene,
            "spoken_narration": narr,
            "prompt": prompt_str,
            "full_prompt": prompt_str,
        }
        if v5:
            clip.update(
                {
                    "schema_version": PROMPT_SCHEMA_VERSION_V5,
                    "visual_mode": mode,
                    "scene_id": shot.get("scene_id"),
                    "shot_type": shot.get("shot_type") or _shot_type_from_camera(clip["camera_move"]),
                    "brain_clip": setting in BRAIN_SETTINGS,
                    "aspect": aspect,
                }
            )
        clips.append(clip)
    return clips


def _shot_type_from_camera(camera: str) -> str:
    c = str(camera or "").lower()
    for key, label in (
        ("extreme close", "ecu"), ("close-up", "cu"), ("close up", "cu"), ("macro", "macro"), ("wide", "wide"),
        ("establishing", "wide"), ("over-the-shoulder", "ots"), ("medium", "medium"), ("dive", "dive"),
        ("pull", "pullout"), ("orbit", "orbit"), ("track", "track"), ("low-angle", "low"), ("overhead", "overhead"),
    ):
        if key in c:
            return label
    return "shot"


_CHARACTER_ROLES: frozenset[str] = frozenset({"setup", "symptom", "failure", "breakthrough", "conclusion"})
_DYNAMIC_ACTION_VERBS_RE = re.compile(
    r"\b(?:drives?|tamps?|slams?|sweeps?|strikes?|knocks?|pushes?|pulls?|lifts?|grips?|grasps?|presses?|"
    r"flips?|reaches?|holds?|points?|traces?|places?|sets?|steers?|passes?|catches?|thumps?|writes?|"
    r"records?|opens?|closes?|shakes?|turns?|rises?|steps?|walks?|leans?|tilts?|taps?|recoils?|flinches?|"
    r"drops?|sparks?|launches?|slides?|nods?|waves?|snatches?|jerks?|twists?|clenches?|operates?|"
    r"releases?|extends?|withdraws?|inspects?|examines?|striking|tamping|slamming|sweeping|pushing|"
    r"pulling|lifting|gripping|pressing|flipping|reaching|holding|pointing|tracing|placing|steering|"
    r"passing|catching|thumping|writing|recording|opening|closing|shaking|turning|rising|stepping|"
    r"walking|leaning|tilting|tapping|recoiling|flinching|dropping|launching|sliding|nodding)\b",
    re.IGNORECASE,
)
_STATIC_POSE_ONLY_RE = re.compile(
    r"\b(?:sits upright in the (?:wooden )?(?:examination )?chair|stares ahead with a frozen|"
    r"sits calmly (?:at|beside|in)|stands quietly beside|sits composed in the wooden chair)\b",
    re.IGNORECASE,
)


def validate_character_motion(prompts: list[str | dict[str, Any]]) -> list[str]:
    """
    Validates that character clips (setup, symptom, failure, breakthrough, conclusion) use a 2-Beat
    expressive physical action chain (at least two active hand/arm/body verbs and no static-only pose).
    """
    issues: list[str] = []
    if not isinstance(prompts, list) or not (CLIP_COUNT_MIN <= len(prompts) <= CLIP_COUNT_MAX):
        return issues
    roles = clip_roles(len(prompts))
    prefixes = [flow_prompt_prefix(a) for a in FLOW_ASPECT_LABELS]
    for idx, (default_role, item) in enumerate(zip(roles, prompts), start=1):
        role = str(item.get("role") or default_role) if isinstance(item, dict) else default_role
        if role not in _CHARACTER_ROLES:
            continue
        if isinstance(item, dict) and item.get("scene"):
            scene = str(item["scene"]).strip()
        else:
            p_str = (item.get("prompt") or item.get("full_prompt") or "") if isinstance(item, dict) else str(item or "")
            p_str = p_str.strip()
            prefix = next((p for p in prefixes if p_str.startswith(p)), None)
            body = p_str[len(prefix) :].strip() if prefix else p_str
            m = _PROMPT_RE.match(body)
            scene = m.group("scene").strip() if m else body
        # Strip camera movement sentences and non-verb framing/adjective phrases before counting character action verbs
        actor_text = re.sub(
            r"[^.]*\b(?:wide establishing shot|the camera\b|camera smoothly|slow pull-back|strong rim light|bright daylight lighting)[^.]*\.?",
            " ",
            scene,
            flags=re.IGNORECASE,
        )
        actor_text = re.sub(r"\bclose[-\s]+ups?\b", " ", actor_text, flags=re.IGNORECASE)
        actor_text = re.sub(
            r"\b(?:an?|the|with|in|on|at|by|from|into|through|beside|under|over|near)\s+(?:wide[-\s]+|half[-\s]+)?open\s+[a-z]+\b",
            " ",
            actor_text,
            flags=re.IGNORECASE,
        )
        actor_text = re.sub(
            r"\bopen\s+(?:cabinet|cabinets|door|doors|doorway|window|windows|blinds|shutter|shutters|"
            r"drawer|drawers|book|books|ledger|notebook|folder|box|case|crate|jar|bottle|palm|palms|"
            r"cranium|ward|room|air|field|court|space|view)\b",
            " ",
            actor_text,
            flags=re.IGNORECASE,
        )
        verbs = _DYNAMIC_ACTION_VERBS_RE.findall(actor_text)
        if _STATIC_POSE_ONLY_RE.search(actor_text):
            issues.append(
                f"Clip {idx} ({role}): contains static pose phrase ('{_STATIC_POSE_ONLY_RE.search(actor_text).group(0)}'); "
                "use a 2-Beat physical action chain"
            )
        elif len(verbs) < 2:
            issues.append(
                f"Clip {idx} ({role}): found {len(verbs)} physical action verb(s) {verbs}; "
                "requires >= 2 verbs for a 2-Beat physical action chain"
            )
    return issues


def validate_flow_prompts(
    prompts: list[str | dict[str, Any]],
    scene_words_max: int = PROMPT_SCENE_WORDS_MAX,
    check_character_motion: bool = False,
) -> list[str]:
    """Validates a list of Flow prompts against Production Contract v4 (v5 voice/aspect/suffix accepted). Returns [] on pass."""
    issues: list[str] = []
    if not isinstance(prompts, list) or not (CLIP_COUNT_MIN <= len(prompts) <= CLIP_COUNT_MAX):
        return [f"Prompt count must be {CLIP_COUNT_MIN}-{CLIP_COUNT_MAX} (got {len(prompts) if isinstance(prompts, list) else 0})"]

    prefixes = [flow_prompt_prefix(a) for a in FLOW_ASPECT_LABELS]
    for idx, item in enumerate(prompts, start=1):
        p_str = item.get("prompt") or item.get("full_prompt") or "" if isinstance(item, dict) else str(item or "")
        p_str = p_str.strip()
        prefix = next((p for p in prefixes if p_str.startswith(p)), None)
        if prefix is None:
            issues.append(f"Clip {idx}: does not start with FLOW_PROMPT_PREFIX")
            continue
        body = p_str[len(prefix) :].strip()
        m = _PROMPT_RE.match(body)
        if not m:
            issues.append(f"Clip {idx}: missing or malformed 'Voice: <voice>. Spoken narration: \"...\"' tail")
            continue
        if body.count("Voice:") != 1 or body.count("Spoken narration:") != 1:
            issues.append(f"Clip {idx}: must contain exactly one Voice/Spoken narration block")

        scene = m.group("scene").strip()
        voice = m.group("voice").strip()
        narration = m.group("narration").strip()
        from pipeline.depiction_rules import BrainDepictionRule

        suf_clean = _clean(FLOW_MOTION_STYLE_V5)
        restraint_clean = _clean(BrainDepictionRule.RESTRAINT_LOCK)
        for suf_candidate in (
            FLOW_MOTION_STYLE_V5,
            f"{suf_clean}.",
            suf_clean,
            BrainDepictionRule.RESTRAINT_LOCK,
            f"{restraint_clean}.",
            restraint_clean,
        ):
            if suf_candidate and scene.endswith(suf_candidate):
                scene = scene[: -len(suf_candidate)].strip()
                break

        allowed_voice_labels = {FLOW_DEFAULT_VOICE, FLOW_VOICE_PROMPT_DESCRIPTOR_V5, *FLOW_LEGACY_VOICE_LABELS}
        if voice not in allowed_voice_labels:
            issues.append(f"Clip {idx}: voice must be '{FLOW_VOICE_PROMPT_DESCRIPTOR_V5}' (got '{voice}')")
        if not narration:
            issues.append(f"Clip {idx}: spoken narration is empty")

        scene_words = count_words(scene)
        if not (PROMPT_SCENE_WORDS_MIN <= scene_words <= scene_words_max):
            issues.append(
                f"Clip {idx}: scene word count {scene_words} outside {PROMPT_SCENE_WORDS_MIN}-{scene_words_max}"
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

    if check_character_motion:
        issues.extend(validate_character_motion(prompts))

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

    from pipeline.config import (
        DIORAMA_CRISIS_BEAT_BANK,
        DIORAMA_EUREKA_REVEAL_BANK,
        DIORAMA_MECHANISM_PIVOT_BANK,
        DIORAMA_TAKEAWAY_BRIDGE_BANK,
    )

    by_role = {r: line for r, line in zip(roles, cleaned)}
    pivot_line = by_role.get("pivot", "")
    pivot_low = pivot_line.lower()
    if PIVOT_MARKER not in pivot_low and not any(p.strip().lower() in pivot_low for p in DIORAMA_MECHANISM_PIVOT_BANK):
        issues.append("Pivot clip must contain 'Instead of' or a registered mechanism pivot phrase")

    conclusion_line = by_role.get("conclusion", "").strip()
    conclusion_low = conclusion_line.lower()
    if not any(conclusion_low.startswith(op.lower()) for op in CONCLUSION_OPENERS) and not any(
        conclusion_low.startswith(op.strip().lower()) for op in DIORAMA_TAKEAWAY_BRIDGE_BANK
    ):
        issues.append("Conclusion clip must open with 'Which proves', 'Which is why', or a registered takeaway bridge")

    crisis_Window = " ".join(by_role.get(r, "") for r in ("symptom", "crisis"))
    crisis_low = crisis_Window.lower()
    if not MEME_CRISIS_PATTERN.search(crisis_Window) and not any(
        p.strip().lower() in crisis_low for p in DIORAMA_CRISIS_BEAT_BANK
    ):
        issues.append("Symptom or crisis clip must contain 'this is/was a total nightmare' or a registered crisis beat")

    awe_roles = ("breakthrough",) if "breakthrough" in by_role else ("mechanism", "conclusion")
    awe_window = " ".join(by_role.get(r, "") for r in awe_roles).lower()
    if MEME_AWE_TEXT not in awe_window and not any(p.strip().lower() in awe_window for p in DIORAMA_EUREKA_REVEAL_BANK):
        issues.append(f"Clip in {awe_roles} must contain 'The researchers were left completely stunned' or a registered eureka reveal")

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
    """Writes flow_all_in_one_prompts.json (to 03_visuals/ for project dirs, or directly inside draft dirs)."""
    p = Path(project_dir)
    if p.name == "03_visuals" or (
        (p / VISUAL_PLAN_FILENAME).exists() and not (p / "03_visuals" / VISUAL_PLAN_FILENAME).exists()
    ):
        vis_dir = p
    else:
        vis_dir = p / "03_visuals"
    vis_dir.mkdir(parents=True, exist_ok=True)
    out_path = vis_dir / FLOW_PROMPTS_FILENAME
    v8 = any(int(c.get("schema_version") or 0) >= PROMPT_SCHEMA_VERSION_V8 for c in clips)
    v7 = any(int(c.get("schema_version") or 0) >= PROMPT_SCHEMA_VERSION_V7 for c in clips)
    v6 = (not v7) and any(int(c.get("schema_version") or 0) == PROMPT_SCHEMA_VERSION_V6 for c in clips)
    v5 = (not v7) and (not v6) and any(int(c.get("schema_version") or 0) == PROMPT_SCHEMA_VERSION_V5 for c in clips)
    schema_ver = (
        PROMPT_SCHEMA_VERSION_V8
        if v8
        else (PROMPT_SCHEMA_VERSION_V7 if v7 else (PROMPT_SCHEMA_VERSION_V6 if v6 else (PROMPT_SCHEMA_VERSION_V5 if v5 else SCHEMA_VERSION)))
    )
    from pipeline.config import DEFAULT_DIORAMA_VOICE_PRESET, DIORAMA_VOICE_PRESETS

    default_diorama_voice = DIORAMA_VOICE_PRESETS[DEFAULT_DIORAMA_VOICE_PRESET]["voice"]
    payload: dict[str, Any] = {
        "schema_version": schema_ver,
        "voice": (default_diorama_voice if (v7 or v6) else voice),
        "clips": clips,
        "prompts": [c.get("prompt") or c.get("full_prompt") or "" for c in clips],
    }
    if v7 or v6:
        payload["profile"] = "neuro_diorama"
        if v7:
            payload["style_profile"] = resolve_diorama_v7_style_profile(clips[0] if clips else None)
            if v8:
                payload["shorts_format_profile"] = SHORTS_EXPRESSIVE_V8_PROFILE
        payload["visual_mode"] = clips[0].get("visual_mode")
        payload["aspect"] = clips[0].get("aspect")
    elif v5:
        payload["visual_mode"] = clips[0].get("visual_mode")
        payload["aspect"] = clips[0].get("aspect")
    payload_txt = json.dumps(payload, indent=2, ensure_ascii=False)
    tmp_path = vis_dir / f".tmp_{os.getpid()}_{out_path.name}"
    try:
        tmp_path.write_text(payload_txt, encoding="utf-8")
        os.replace(tmp_path, out_path)
    except OSError:
        tmp_path.unlink(missing_ok=True)
        out_path.write_text(payload_txt, encoding="utf-8")
    finally:
        tmp_path.unlink(missing_ok=True)
    return out_path
