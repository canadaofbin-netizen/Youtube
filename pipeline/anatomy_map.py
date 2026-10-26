"""
ALL ABOUT BRAIN - Verified anatomy -> function -> plain-language table (Rule R48).

Every brain region that appears on screen must be a canonical entry (or alias) of ANATOMY_FUNCTION_MAP,
and the same clip's narration must name it (or its plain-language name) so picture and voice stay linked.
Invented compound regions ("cerebellar and amygdala associative synapse circuit") fail validation.

Reference functions follow standard neuroscience textbooks (Kandel, Principles of Neural Science, 6th ed.;
Purves, Neuroscience, 6th ed.). Keep entries conservative: one primary role per region.
"""

from __future__ import annotations

import re
from typing import Any

# canonical -> {aliases, plain (preferred everyday names), functions, location}
ANATOMY_FUNCTION_MAP: dict[str, dict[str, Any]] = {
    "primary visual cortex": {
        "aliases": ("visual cortex", "occipital cortex", "occipital lobe", "V1"),
        "plain": ("vision center", "the back of the brain", "the back of your brain", "the back of his brain", "the back of her brain"),
        "functions": ("vision", "seeing", "visual processing"),
        "location": "at the very back of the head",
    },
    "fusiform face area": {
        "aliases": ("fusiform gyrus", "fusiform"),
        "plain": ("face-recognition patch", "face patch", "face detector"),
        "functions": ("face recognition",),
        "location": "on the underside of the temporal lobe",
    },
    "amygdala": {
        "aliases": ("amygdalae", "lateral amygdala"),
        "plain": ("alarm", "fear center", "emotional alarm"),
        "functions": ("fear", "emotional significance", "threat detection"),
        "location": "deep inside each temporal lobe",
    },
    "hippocampus": {
        "aliases": ("hippocampal", "hippocampi"),
        "plain": ("memory maker", "memory recorder", "memory center"),
        "functions": ("forming new memories", "spatial navigation"),
        "location": "deep inside each temporal lobe, curved in a smooth C-shaped neural ridge",
    },
    "prefrontal cortex": {
        "aliases": ("prefrontal", "frontal cortex"),
        "plain": ("planner", "brake", "the front of the brain", "behind the forehead"),
        "functions": ("planning", "impulse control", "decision making"),
        "location": "directly behind the forehead",
    },
    "ventromedial prefrontal cortex": {
        "aliases": ("ventromedial", "vmPFC", "orbitofrontal cortex", "orbitofrontal"),
        "plain": ("judgment center", "social brake", "behind the eyes"),
        "functions": ("social judgment", "linking emotion to decisions", "self-control"),
        "location": "just above the eye sockets",
    },
    "dorsolateral prefrontal cortex": {
        "aliases": ("dorsolateral", "dlPFC"),
        "plain": ("working-memory desk", "mental scratchpad"),
        "functions": ("working memory", "holding a plan in mind"),
        "location": "upper sides of the forehead",
    },
    "frontal lobe": {
        "aliases": ("frontal lobes",),
        "plain": ("the front of the brain", "personality center"),
        "functions": ("personality", "planning", "voluntary movement"),
        "location": "the front third of the brain",
    },
    "anterior cingulate cortex": {
        "aliases": ("anterior cingulate", "cingulate"),
        "plain": ("conflict detector", "error alarm"),
        "functions": ("detecting conflict and errors", "pain distress"),
        "location": "on the inner wall between the two halves",
    },
    "motor cortex": {
        "aliases": ("primary motor cortex", "motor strip"),
        "plain": ("movement strip", "movement control strip"),
        "functions": ("voluntary movement",),
        "location": "a strip running over the top of the head",
    },
    "premotor cortex": {
        "aliases": ("premotor", "mirror neuron system", "mirror neurons"),
        "plain": ("action planner", "mirror system"),
        "functions": ("planning movements", "mirroring others' actions"),
        "location": "just in front of the movement strip",
    },
    "somatosensory cortex": {
        "aliases": ("sensory cortex", "primary somatosensory cortex"),
        "plain": ("touch map", "body map"),
        "functions": ("touch", "body sensation"),
        "location": "a strip just behind the movement strip",
    },
    "cerebellum": {
        "aliases": ("cerebellar",),
        "plain": ("little brain", "coordination center", "balance center"),
        "functions": ("motor coordination", "balance", "timing of movements"),
        "location": "at the base of the skull, behind the brainstem",
    },
    "basal ganglia": {
        "aliases": ("striatum", "dorsal striatum", "caudate", "putamen"),
        "plain": ("habit engine", "autopilot", "habit center"),
        "functions": ("habits", "action selection", "reward learning"),
        "location": "deep in the center of the brain",
    },
    "nucleus accumbens": {
        "aliases": ("ventral striatum", "pleasure center", "reward center"),
        "plain": ("reward center", "pleasure center"),
        "functions": ("reward", "motivation", "pleasure"),
        "location": "deep below the front of the brain",
    },
    "thalamus": {
        "aliases": ("thalamic", "thalamic reticular nucleus"),
        "plain": ("relay station", "sensory switchboard", "gatekeeper"),
        "functions": ("relaying senses to the cortex", "gating attention"),
        "location": "in the very center of the brain",
    },
    "hypothalamus": {
        "aliases": ("hypothalamic",),
        "plain": ("body thermostat", "hormone control center"),
        "functions": ("hunger", "body temperature", "stress hormones"),
        "location": "just below the thalamus",
    },
    "brainstem": {
        "aliases": ("brain stem", "medulla", "pons", "salivary nucleus"),
        "plain": ("autopilot", "reflex center", "the top of the spine"),
        "functions": ("breathing", "heart rate", "automatic reflexes like salivation"),
        "location": "where the brain meets the spinal cord",
    },
    "auditory cortex": {
        "aliases": ("primary auditory cortex",),
        "plain": ("hearing center", "sound center"),
        "functions": ("hearing", "processing sounds"),
        "location": "on the side of the head, above the ears",
    },
    "Broca's area": {
        "aliases": ("broca", "brocas area"),
        "plain": ("speech producer", "speech center"),
        "functions": ("producing speech",),
        "location": "left side, behind the temple",
    },
    "Wernicke's area": {
        "aliases": ("wernicke", "wernickes area"),
        "plain": ("language decoder", "word-understanding center"),
        "functions": ("understanding language",),
        "location": "left side, behind the ear",
    },
    "corpus callosum": {
        "aliases": ("callosum",),
        "plain": ("bridge between the two halves", "bridge between hemispheres", "central bridge"),
        "functions": ("connecting the left and right hemispheres",),
        "location": "a thick band in the middle of the brain",
    },
    "insula": {
        "aliases": ("insular cortex",),
        "plain": ("gut-feeling center", "body-feeling center"),
        "functions": ("gut feelings", "disgust", "sensing the body's inner state"),
        "location": "folded deep inside the side of the brain",
    },
    "parietal cortex": {
        "aliases": ("parietal lobe", "posterior parietal cortex", "dorsal parietal cortex", "intraparietal"),
        "plain": ("attention spotlight", "spatial map"),
        "functions": ("directing attention", "spatial awareness"),
        "location": "the upper back of the head",
    },
    "temporal lobe": {
        "aliases": ("temporal lobes", "temporal cortex", "medial temporal lobe"),
        "plain": ("side lobe", "the side of the brain"),
        "functions": ("sound", "memory", "recognizing objects"),
        "location": "on each side, behind the temples",
    },
    "default mode network": {
        "aliases": ("default network",),
        "plain": ("daydream network", "autopilot network"),
        "functions": ("mind-wandering", "thinking about yourself"),
        "location": "a network linking the front and back midline",
    },
    "ventral tegmental area": {
        "aliases": ("VTA", "dopamine neurons"),
        "plain": ("dopamine source", "dopamine factory"),
        "functions": ("releasing dopamine for reward and learning",),
        "location": "in the midbrain",
    },
    "retina": {
        "aliases": ("retinas",),
        "plain": ("back of the eye", "the eye's light sensor"),
        "functions": ("turning light into nerve signals",),
        "location": "lining the back of the eye",
    },
    "optic nerve": {
        "aliases": ("optic nerves", "optic tract"),
        "plain": ("eye cable", "the cable from the eye"),
        "functions": ("carrying signals from the eye to the brain",),
        "location": "from the back of each eye into the brain",
    },
    "cochlea": {
        "aliases": ("auditory nerve",),
        "plain": ("inner ear", "hearing snail"),
        "functions": ("turning sound into nerve signals",),
        "location": "deep inside the ear",
    },
    "white matter": {
        "aliases": ("white-matter tract", "white-matter tracts", "nerve fibers", "uncinate fasciculus"),
        "plain": ("wiring", "cables", "nerve cables"),
        "functions": ("connecting brain regions",),
        "location": "beneath the outer cortex",
    },
}

# Non-anatomical tokens that legitimately appear in brain-scene text and must not be read as regions.
_GENERIC_BRAIN_WORDS = ("brain", "cortex", "neuron", "neurons", "circuit", "lobe", "region", "nucleus")


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9' -]", " ", str(text or "").lower())).strip()


def _all_names(canonical: str) -> list[str]:
    entry = ANATOMY_FUNCTION_MAP[canonical]
    return [canonical, *entry.get("aliases", ())]


# Longest names first so "ventromedial prefrontal cortex" wins over "prefrontal cortex".
_NAME_INDEX: list[tuple[str, str]] = sorted(
    ((_norm(name), canon) for canon in ANATOMY_FUNCTION_MAP for name in _all_names(canon)),
    key=lambda kv: len(kv[0]),
    reverse=True,
)


def resolve_region(name: str) -> str | None:
    """Returns the canonical region for a name or alias (exact or contained match), else None."""
    n = _norm(name)
    if not n:
        return None
    for alias, canon in _NAME_INDEX:
        if n == alias:
            return canon
    for alias, canon in _NAME_INDEX:
        if re.search(rf"(?<![a-z]){re.escape(alias)}(?![a-z])", n):
            return canon
    return None


def find_regions(text: str) -> list[str]:
    """Canonical regions mentioned in free text (longest-match, non-overlapping, order of appearance)."""
    n = _norm(text)
    found: list[tuple[int, str]] = []
    taken: list[tuple[int, int]] = []
    for alias, canon in _NAME_INDEX:
        if len(alias) < 3 and alias.upper() != alias:
            continue
        for m in re.finditer(rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])", n):
            s, e = m.span()
            if any(not (e <= ts or s >= te) for ts, te in taken):
                continue
            taken.append((s, e))
            found.append((s, canon))
    out: list[str] = []
    for _, canon in sorted(found):
        if canon not in out:
            out.append(canon)
    return out


def region_named_in(region: str, narration: str) -> bool:
    """True when the narration names the region by canonical name, alias, or plain-language name."""
    canon = resolve_region(region) or region
    n = _norm(narration)
    entry = ANATOMY_FUNCTION_MAP.get(canon, {})
    names = [canon, *entry.get("aliases", ()), *entry.get("plain", ())]
    return any(re.search(rf"(?<![a-z]){re.escape(_norm(x))}(?![a-z])", n) for x in names if _norm(x))


def plain_name(region: str) -> str:
    canon = resolve_region(region)
    if not canon:
        return region
    plains = ANATOMY_FUNCTION_MAP[canon].get("plain") or (canon,)
    return str(plains[0])


def describe(region: str) -> dict[str, Any] | None:
    canon = resolve_region(region)
    if not canon:
        return None
    entry = ANATOMY_FUNCTION_MAP[canon]
    return {"canonical": canon, **{k: list(v) if isinstance(v, tuple) else v for k, v in entry.items()}}
