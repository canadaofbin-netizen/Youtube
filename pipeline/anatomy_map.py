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
        "plain": ("face detector", "face patch", "face-recognition patch"),
        "functions": ("face recognition",),
        "location": "on the underside of the temporal lobe",
    },
    "amygdala": {
        "aliases": ("amygdalae", "lateral amygdala"),
        "plain": ("emotional center", "fear center", "threat alarm", "alarm"),
        "functions": ("fear", "emotional significance", "threat detection"),
        "location": "deep inside each temporal lobe",
    },
    "hippocampus": {
        "aliases": ("hippocampal", "hippocampi"),
        "plain": ("memory maker", "memory recorder", "memory center", "memory hub"),
        "functions": ("forming new memories", "spatial navigation"),
        "location": "deep inside each temporal lobe, curved in a smooth C-shaped neural ridge",
    },
    "prefrontal cortex": {
        "aliases": ("prefrontal", "frontal cortex"),
        "plain": (
            "planner",
            "planning center",
            "spot behind the forehead",
            "reality-checker",
            "reality check",
            "decision builder",
            "satisfaction builder",
            "happiness builder",
            "choice builder",
            "brake",
            "brakes",
            "mental brake",
            "the front of the brain",
            "behind the forehead",
            "behind your forehead",
        ),
        "functions": ("planning", "impulse control", "decision making"),
        "location": "directly behind the forehead",
    },
    "ventromedial prefrontal cortex": {
        "aliases": ("ventromedial", "vmPFC", "orbitofrontal cortex", "orbitofrontal"),
        "plain": ("judgment center", "reality-checker", "reality check", "spot behind the forehead", "social brake", "behind the eyes"),
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
        "plain": ("conflict detector", "error alarm", "overload alarm", "choice alarm"),
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
        "plain": ("little brain", "coordination center", "balance center", "movement predictor"),
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
        "aliases": ("broca's area", "broca s area", "brocas area", "broca area", "broca's region", "inferior frontal gyrus"),
        "plain": ("speech producer", "speech center"),
        "functions": ("producing speech",),
        "location": "left side, behind the temple",
    },
    "Wernicke's area": {
        "aliases": ("wernicke's area", "wernicke s area", "wernickes area", "wernicke area", "wernicke's region", "superior temporal gyrus"),
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
    if n == "broca":
        return "Broca's area"
    if n == "wernicke":
        return "Wernicke's area"
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


# Normalized (x_frac, y_frac) anatomical region anchors, 3D neural previs coordinates (brain center [0,0,1.50], r=0.26m),
# and R74 B1 ultra-macro callout coordinates + Zero-Flesh optical-glass macro visual specs.
ANATOMY_SCREEN_ANCHORS: dict[str, dict[str, Any]] = {
    "nucleus accumbens": {
        "anchor_xy": (0.53, 0.46),
        "label_xy": (0.50, 0.21),
        "macro_anchor_xy": (0.50, 0.49),
        "macro_label_xy": (0.50, 0.20),
        "pos_3d_brain_xyz": (0.03, -0.07, 1.45),
        "approach_azimuth_deg": -15.0,
        "approach_elevation_deg": -4.0,
        "macro_visual_desc": (
            "giant luminous crimson-ruby optical-glass ventral striatum reward nucleus filling 50% of the deep midnight-navy chamber, "
            "framed by frosted borosilicate crystal-glass cortical ribs along the left and right foreground edges"
        ),
        "accent_rgb": (255, 86, 94),
        "short_role": "Reward Center",
    },
    "prefrontal cortex": {
        "anchor_xy": (0.24, 0.40),
        "label_xy": (0.50, 0.19),
        "macro_anchor_xy": (0.49, 0.48),
        "macro_label_xy": (0.50, 0.19),
        "pos_3d_brain_xyz": (0.00, -0.17, 1.55),
        "approach_azimuth_deg": 0.0,
        "approach_elevation_deg": 10.0,
        "macro_visual_desc": (
            "giant luminous cool sapphire-blue optical-glass prefrontal gyri vault filling 50% of the deep midnight-navy chamber, "
            "framed by frosted borosilicate crystal-glass frontal folds along the outer edges"
        ),
        "accent_rgb": (72, 224, 255),
        "short_role": "Reality-Checker",
    },
    "ventromedial prefrontal cortex": {
        "anchor_xy": (0.24, 0.40),
        "label_xy": (0.50, 0.19),
        "macro_anchor_xy": (0.50, 0.49),
        "macro_label_xy": (0.50, 0.19),
        "pos_3d_brain_xyz": (0.00, -0.16, 1.45),
        "approach_azimuth_deg": -8.0,
        "approach_elevation_deg": -6.0,
        "macro_visual_desc": (
            "giant luminous warm amber-gold and cool sapphire-blue optical-glass ventromedial prefrontal hub filling 50% of the deep midnight-navy chamber, "
            "framed by frosted borosilicate crystal-glass orbital folds along the foreground edges"
        ),
        "accent_rgb": (255, 198, 74),
        "short_role": "Reality-Checker",
    },
    "dorsolateral prefrontal cortex": {
        "anchor_xy": (0.24, 0.38),
        "label_xy": (0.50, 0.19),
        "macro_anchor_xy": (0.49, 0.47),
        "macro_label_xy": (0.50, 0.19),
        "pos_3d_brain_xyz": (-0.11, -0.14, 1.58),
        "approach_azimuth_deg": -34.0,
        "approach_elevation_deg": 16.0,
        "macro_visual_desc": (
            "giant luminous cool sapphire-blue optical-glass dorsolateral prefrontal ridge filling 50% of the deep midnight-navy chamber, "
            "framed by frosted borosilicate crystal-glass cortical ribs along the left and right edges"
        ),
        "accent_rgb": (72, 224, 255),
        "short_role": "Working-Memory Control",
    },
    "amygdala": {
        "anchor_xy": (0.49, 0.51),
        "label_xy": (0.50, 0.21),
        "macro_anchor_xy": (0.50, 0.49),
        "macro_label_xy": (0.50, 0.20),
        "pos_3d_brain_xyz": (-0.10, -0.05, 1.43),
        "approach_azimuth_deg": -62.0,
        "approach_elevation_deg": -8.0,
        "macro_visual_desc": (
            "giant luminous deep crimson-red almond-shaped optical-glass amygdala node filling 50% of the deep temporal midnight-navy chamber, "
            "framed by frosted borosilicate crystal-glass temporal cortex ribs along the foreground edges"
        ),
        "accent_rgb": (255, 86, 94),
        "short_role": "Emotional Center",
    },
    "hippocampus": {
        "anchor_xy": (0.54, 0.52),
        "label_xy": (0.50, 0.21),
        "macro_anchor_xy": (0.51, 0.49),
        "macro_label_xy": (0.50, 0.20),
        "pos_3d_brain_xyz": (-0.12, 0.02, 1.44),
        "approach_azimuth_deg": -76.0,
        "approach_elevation_deg": -6.0,
        "macro_visual_desc": (
            "giant luminous warm amber-gold C-shaped optical-glass seahorse hippocampus arch filling 50% of the deep temporal midnight-navy chamber, "
            "framed by frosted borosilicate crystal-glass temporal gyri walls along the left and right edges"
        ),
        "accent_rgb": (255, 198, 74),
        "short_role": "Memory Hub",
    },
    "anterior cingulate cortex": {
        "anchor_xy": (0.45, 0.38),
        "label_xy": (0.50, 0.19),
        "macro_anchor_xy": (0.50, 0.47),
        "macro_label_xy": (0.50, 0.19),
        "pos_3d_brain_xyz": (0.00, -0.07, 1.57),
        "approach_azimuth_deg": -18.0,
        "approach_elevation_deg": 22.0,
        "macro_visual_desc": (
            "giant luminous warm amber-gold and crimson-rimmed optical-glass anterior cingulate arch filling 50% of the medial midnight-navy chamber, "
            "framed by frosted borosilicate crystal-glass interhemispheric cortical walls along the edges"
        ),
        "accent_rgb": (255, 198, 74),
        "short_role": "Conflict & Pain Alarm",
    },
    "insula": {
        "anchor_xy": (0.48, 0.45),
        "label_xy": (0.50, 0.20),
        "macro_anchor_xy": (0.50, 0.48),
        "macro_label_xy": (0.50, 0.20),
        "pos_3d_brain_xyz": (-0.14, -0.02, 1.50),
        "approach_azimuth_deg": -78.0,
        "approach_elevation_deg": 4.0,
        "macro_visual_desc": (
            "giant luminous pearl-aqua optical-glass insular cortex fold filling 50% of the deep lateral midnight-navy chamber, "
            "framed by parted frosted borosilicate crystal-glass opercular ribs along the foreground edges"
        ),
        "accent_rgb": (110, 238, 214),
        "short_role": "Body-Feeling Hub",
    },
    "basal ganglia": {
        "anchor_xy": (0.49, 0.45),
        "label_xy": (0.50, 0.20),
        "macro_anchor_xy": (0.50, 0.48),
        "macro_label_xy": (0.50, 0.20),
        "pos_3d_brain_xyz": (-0.07, -0.02, 1.51),
        "approach_azimuth_deg": -42.0,
        "approach_elevation_deg": 8.0,
        "macro_visual_desc": (
            "giant luminous warm amber-gold optical-glass striatal loop cluster filling 50% of the deep central midnight-navy chamber, "
            "framed by frosted borosilicate crystal-glass cortical ribs along the left and right edges"
        ),
        "accent_rgb": (255, 198, 74),
        "short_role": "Habit Engine",
    },
    "thalamus": {
        "anchor_xy": (0.51, 0.46),
        "label_xy": (0.50, 0.20),
        "macro_anchor_xy": (0.50, 0.48),
        "macro_label_xy": (0.50, 0.20),
        "pos_3d_brain_xyz": (0.00, 0.01, 1.50),
        "approach_azimuth_deg": -28.0,
        "approach_elevation_deg": 6.0,
        "macro_visual_desc": (
            "giant luminous pearl-aqua paired ovoid optical-glass thalamic relay core filling 50% of the central midnight-navy chamber, "
            "framed by radiating frosted borosilicate crystal-glass tract pillars along the foreground edges"
        ),
        "accent_rgb": (110, 238, 214),
        "short_role": "Sensory Relay",
    },
    "hypothalamus": {
        "anchor_xy": (0.49, 0.52),
        "label_xy": (0.50, 0.21),
        "macro_anchor_xy": (0.50, 0.49),
        "macro_label_xy": (0.50, 0.20),
        "pos_3d_brain_xyz": (0.00, -0.03, 1.43),
        "approach_azimuth_deg": -20.0,
        "approach_elevation_deg": -10.0,
        "macro_visual_desc": (
            "giant luminous warm amber-gold optical-glass hypothalamic control node filling 50% of the deep basal midnight-navy chamber, "
            "framed by frosted borosilicate crystal-glass subcortical arches along the edges"
        ),
        "accent_rgb": (255, 198, 74),
        "short_role": "Hormone Control",
    },
    "motor cortex": {
        "anchor_xy": (0.51, 0.31),
        "label_xy": (0.50, 0.17),
        "macro_anchor_xy": (0.50, 0.46),
        "macro_label_xy": (0.50, 0.18),
        "pos_3d_brain_xyz": (-0.08, 0.01, 1.68),
        "approach_azimuth_deg": -35.0,
        "approach_elevation_deg": 42.0,
        "macro_visual_desc": (
            "giant luminous cool sapphire-blue optical-glass primary motor cortex crown ridge filling 50% of the dorsal midnight-navy chamber, "
            "framed by frosted borosilicate crystal-glass sulcal walls along the foreground edges"
        ),
        "accent_rgb": (72, 224, 255),
        "short_role": "Movement Strip",
    },
    "somatosensory cortex": {
        "anchor_xy": (0.56, 0.32),
        "label_xy": (0.50, 0.17),
        "macro_anchor_xy": (0.50, 0.46),
        "macro_label_xy": (0.50, 0.18),
        "pos_3d_brain_xyz": (-0.08, 0.06, 1.67),
        "approach_azimuth_deg": -45.0,
        "approach_elevation_deg": 40.0,
        "macro_visual_desc": (
            "giant luminous pearl-aqua optical-glass somatosensory gyrus ribbon filling 50% of the dorsal midnight-navy chamber, "
            "framed by frosted borosilicate crystal-glass parietal folds along the edges"
        ),
        "accent_rgb": (110, 238, 214),
        "short_role": "Body-Touch Map",
    },
    "primary visual cortex": {
        "anchor_xy": (0.69, 0.45),
        "label_xy": (0.50, 0.20),
        "macro_anchor_xy": (0.50, 0.48),
        "macro_label_xy": (0.50, 0.20),
        "pos_3d_brain_xyz": (0.00, 0.19, 1.49),
        "approach_azimuth_deg": 168.0,
        "approach_elevation_deg": 6.0,
        "macro_visual_desc": (
            "giant luminous cool sapphire-blue optical-glass occipital visual cortex calcarine vault filling 50% of the posterior midnight-navy chamber, "
            "framed by frosted borosilicate crystal-glass occipital ribs along the edges"
        ),
        "accent_rgb": (72, 224, 255),
        "short_role": "Vision Center",
    },
    "auditory cortex": {
        "anchor_xy": (0.54, 0.47),
        "label_xy": (0.50, 0.20),
        "macro_anchor_xy": (0.50, 0.48),
        "macro_label_xy": (0.50, 0.20),
        "pos_3d_brain_xyz": (-0.18, 0.02, 1.49),
        "approach_azimuth_deg": -86.0,
        "approach_elevation_deg": 2.0,
        "macro_visual_desc": (
            "giant luminous cool sapphire-blue optical-glass superior temporal auditory ridge filling 50% of the lateral midnight-navy chamber, "
            "framed by frosted borosilicate crystal-glass sylvian folds along the foreground edges"
        ),
        "accent_rgb": (72, 224, 255),
        "short_role": "Sound Center",
    },
    "cerebellum": {
        "anchor_xy": (0.63, 0.57),
        "label_xy": (0.50, 0.22),
        "macro_anchor_xy": (0.50, 0.50),
        "macro_label_xy": (0.50, 0.20),
        "pos_3d_brain_xyz": (0.00, 0.15, 1.34),
        "approach_azimuth_deg": 158.0,
        "approach_elevation_deg": -16.0,
        "macro_visual_desc": (
            "giant luminous pearl-aqua finely foliated optical-glass cerebellar hemisphere filling 50% of the posterior-inferior midnight-navy chamber, "
            "framed by frosted borosilicate crystal-glass tentorial arches along the edges"
        ),
        "accent_rgb": (110, 238, 214),
        "short_role": "Balance & Timing",
    },
    "brainstem": {
        "anchor_xy": (0.53, 0.61),
        "label_xy": (0.50, 0.22),
        "macro_anchor_xy": (0.50, 0.51),
        "macro_label_xy": (0.50, 0.20),
        "pos_3d_brain_xyz": (0.00, 0.05, 1.30),
        "approach_azimuth_deg": -135.0,
        "approach_elevation_deg": -18.0,
        "macro_visual_desc": (
            "giant luminous pearl-aqua and crimson-pulsing optical-glass brainstem pillar filling 50% of the basal midnight-navy chamber, "
            "framed by frosted borosilicate crystal-glass cranial tract columns along the edges"
        ),
        "accent_rgb": (110, 238, 214),
        "short_role": "Vital Reflex Stem",
    },
    "default mode network": {
        "anchor_xy": (0.47, 0.38),
        "label_xy": (0.50, 0.18),
        "macro_anchor_xy": (0.50, 0.47),
        "macro_label_xy": (0.50, 0.19),
        "pos_3d_brain_xyz": (0.00, -0.04, 1.58),
        "approach_azimuth_deg": -24.0,
        "approach_elevation_deg": 20.0,
        "macro_visual_desc": (
            "giant luminous warm amber-gold midline optical-glass default-mode hub bridge filling 50% of the medial midnight-navy chamber, "
            "framed by frosted borosilicate crystal-glass cortical arches along the left and right edges"
        ),
        "accent_rgb": (255, 198, 74),
        "short_role": "Daydream Network",
    },
    "fusiform face area": {
        "anchor_xy": (0.58, 0.54),
        "label_xy": (0.50, 0.21),
        "macro_anchor_xy": (0.50, 0.49),
        "macro_label_xy": (0.50, 0.20),
        "pos_3d_brain_xyz": (-0.13, 0.07, 1.40),
        "approach_azimuth_deg": -108.0,
        "approach_elevation_deg": -14.0,
        "glass_visual_desc": "ventral temporal borosilicate crystal fusiform face-recognition ridge glowing cool sapphire-blue",
        "macro_visual_desc": (
            "giant luminous cool sapphire-blue optical-glass fusiform face-recognition ridge filling 50% of the ventral temporal midnight-navy chamber, "
            "framed by frosted borosilicate crystal-glass occipitotemporal ribs along the foreground edges"
        ),
        "accent_rgb": (72, 224, 255),
        "short_role": "Face-Recognition Patch",
    },
    "frontal lobe": {
        "anchor_xy": (0.28, 0.37),
        "label_xy": (0.50, 0.19),
        "macro_anchor_xy": (0.50, 0.47),
        "macro_label_xy": (0.50, 0.19),
        "pos_3d_brain_xyz": (0.00, -0.14, 1.59),
        "approach_azimuth_deg": -12.0,
        "approach_elevation_deg": 18.0,
        "glass_visual_desc": "sculpted anterior frontal borosilicate crystal dome glowing cool sapphire-blue",
        "macro_visual_desc": (
            "giant luminous cool sapphire-blue optical-glass anterior frontal lobe vault filling 50% of the deep midnight-navy chamber, "
            "framed by frosted borosilicate crystal-glass frontal gyri folds along the outer edges"
        ),
        "accent_rgb": (72, 224, 255),
        "short_role": "Planning & Control Hub",
    },
    "premotor cortex": {
        "anchor_xy": (0.44, 0.32),
        "label_xy": (0.50, 0.17),
        "macro_anchor_xy": (0.50, 0.46),
        "macro_label_xy": (0.50, 0.18),
        "pos_3d_brain_xyz": (-0.09, -0.05, 1.66),
        "approach_azimuth_deg": -32.0,
        "approach_elevation_deg": 36.0,
        "glass_visual_desc": "dorsal premotor borosilicate crystal cortical band glowing cool sapphire-blue",
        "macro_visual_desc": (
            "giant luminous cool sapphire-blue optical-glass dorsal premotor planning ridge filling 50% of the superior midnight-navy chamber, "
            "framed by frosted borosilicate crystal-glass sulcal walls along the foreground edges"
        ),
        "accent_rgb": (72, 224, 255),
        "short_role": "Action Planner",
    },
    "Broca's area": {
        "anchor_xy": (0.35, 0.44),
        "label_xy": (0.50, 0.20),
        "macro_anchor_xy": (0.49, 0.48),
        "macro_label_xy": (0.50, 0.20),
        "pos_3d_brain_xyz": (-0.15, -0.09, 1.52),
        "approach_azimuth_deg": -58.0,
        "approach_elevation_deg": 6.0,
        "glass_visual_desc": "left inferior frontal opercular crystal speech node glowing cool sapphire-blue",
        "macro_visual_desc": (
            "giant luminous cool sapphire-blue optical-glass inferior frontal speech-builder fold filling 50% of the lateral midnight-navy chamber, "
            "framed by frosted borosilicate crystal-glass frontal opercular ribs along the foreground edges"
        ),
        "accent_rgb": (72, 224, 255),
        "short_role": "Speech Builder",
    },
    "Wernicke's area": {
        "anchor_xy": (0.59, 0.46),
        "label_xy": (0.50, 0.20),
        "macro_anchor_xy": (0.50, 0.48),
        "macro_label_xy": (0.50, 0.20),
        "pos_3d_brain_xyz": (-0.17, 0.08, 1.51),
        "approach_azimuth_deg": -112.0,
        "approach_elevation_deg": 6.0,
        "glass_visual_desc": "posterior superior temporal crystal comprehension fold glowing pearl-aqua",
        "macro_visual_desc": (
            "giant luminous pearl-aqua optical-glass posterior temporal language-decoder fold filling 50% of the lateral midnight-navy chamber, "
            "framed by frosted borosilicate crystal-glass temporoparietal ribs along the foreground edges"
        ),
        "accent_rgb": (110, 238, 214),
        "short_role": "Language Decoder",
    },
    "corpus callosum": {
        "anchor_xy": (0.48, 0.41),
        "label_xy": (0.50, 0.19),
        "macro_anchor_xy": (0.50, 0.47),
        "macro_label_xy": (0.50, 0.19),
        "pos_3d_brain_xyz": (0.00, -0.01, 1.54),
        "approach_azimuth_deg": -16.0,
        "approach_elevation_deg": 14.0,
        "glass_visual_desc": "arched midline borosilicate crystal fiber bridge connecting left and right hemispheres in warm amber-gold",
        "macro_visual_desc": (
            "giant luminous warm amber-gold arched optical-glass corpus callosum fiber bridge spanning 50% of the central interhemispheric midnight-navy chamber, "
            "framed by twin frosted borosilicate crystal-glass hemisphere walls on left and right"
        ),
        "accent_rgb": (255, 198, 74),
        "short_role": "Left-Right Bridge",
    },
    "parietal cortex": {
        "anchor_xy": (0.61, 0.35),
        "label_xy": (0.50, 0.18),
        "macro_anchor_xy": (0.50, 0.47),
        "macro_label_xy": (0.50, 0.19),
        "pos_3d_brain_xyz": (-0.10, 0.11, 1.64),
        "approach_azimuth_deg": -126.0,
        "approach_elevation_deg": 34.0,
        "glass_visual_desc": "superior parietal borosilicate crystal spatial-map dome glowing pearl-aqua",
        "macro_visual_desc": (
            "giant luminous pearl-aqua optical-glass parietal spatial-map crown filling 50% of the posterodorsal midnight-navy chamber, "
            "framed by frosted borosilicate crystal-glass parietal gyri ribs along the foreground edges"
        ),
        "accent_rgb": (110, 238, 214),
        "short_role": "Space & Body Map",
    },
    "temporal lobe": {
        "anchor_xy": (0.52, 0.50),
        "label_xy": (0.50, 0.21),
        "macro_anchor_xy": (0.50, 0.49),
        "macro_label_xy": (0.50, 0.20),
        "pos_3d_brain_xyz": (-0.16, -0.01, 1.46),
        "approach_azimuth_deg": -84.0,
        "approach_elevation_deg": -4.0,
        "glass_visual_desc": "lateral temporal borosilicate crystal gyri bank glowing warm amber-gold",
        "macro_visual_desc": (
            "giant luminous warm amber-gold optical-glass lateral temporal gyri vault filling 50% of the temporal midnight-navy chamber, "
            "framed by frosted borosilicate crystal-glass sylvian folds along the foreground edges"
        ),
        "accent_rgb": (255, 198, 74),
        "short_role": "Sound & Memory Lobe",
    },
    "ventral tegmental area": {
        "anchor_xy": (0.51, 0.55),
        "label_xy": (0.50, 0.21),
        "macro_anchor_xy": (0.50, 0.50),
        "macro_label_xy": (0.50, 0.20),
        "pos_3d_brain_xyz": (0.00, 0.02, 1.38),
        "approach_azimuth_deg": -30.0,
        "approach_elevation_deg": -14.0,
        "glass_visual_desc": "deep midbrain borosilicate crystal dopamine core glowing crimson-ruby",
        "macro_visual_desc": (
            "giant luminous deep crimson-red and warm amber-gold optical-glass ventral tegmental dopamine core filling 50% of the midbrain midnight-navy chamber, "
            "framed by frosted borosilicate crystal-glass peduncular pillars along the foreground edges"
        ),
        "accent_rgb": (255, 86, 94),
        "short_role": "Dopamine Source",
    },
    "retina": {
        "anchor_xy": (0.20, 0.49),
        "label_xy": (0.50, 0.20),
        "macro_anchor_xy": (0.48, 0.49),
        "macro_label_xy": (0.50, 0.20),
        "pos_3d_brain_xyz": (-0.06, -0.22, 1.44),
        "approach_azimuth_deg": -14.0,
        "approach_elevation_deg": -8.0,
        "glass_visual_desc": "concave anterior borosilicate crystal retinal cup glowing cool sapphire-blue",
        "macro_visual_desc": (
            "giant luminous cool sapphire-blue concave optical-glass retinal sensor cup filling 50% of the anterior midnight-navy chamber, "
            "framed by frosted borosilicate crystal-glass orbital rings along the outer edges"
        ),
        "accent_rgb": (72, 224, 255),
        "short_role": "Light Sensor",
    },
    "optic nerve": {
        "anchor_xy": (0.31, 0.50),
        "label_xy": (0.50, 0.20),
        "macro_anchor_xy": (0.49, 0.49),
        "macro_label_xy": (0.50, 0.20),
        "pos_3d_brain_xyz": (-0.04, -0.14, 1.42),
        "approach_azimuth_deg": -22.0,
        "approach_elevation_deg": -10.0,
        "glass_visual_desc": "bundled anterior borosilicate crystal optic nerve cable glowing cool sapphire-blue",
        "macro_visual_desc": (
            "giant luminous cool sapphire-blue bundled optical-glass optic nerve conduit filling 50% of the basal midnight-navy chamber, "
            "framed by frosted borosilicate crystal-glass chiasm arches along the foreground edges"
        ),
        "accent_rgb": (72, 224, 255),
        "short_role": "Vision Cable",
    },
    "cochlea": {
        "anchor_xy": (0.55, 0.56),
        "label_xy": (0.50, 0.21),
        "macro_anchor_xy": (0.50, 0.50),
        "macro_label_xy": (0.50, 0.20),
        "pos_3d_brain_xyz": (-0.17, 0.04, 1.37),
        "approach_azimuth_deg": -96.0,
        "approach_elevation_deg": -14.0,
        "glass_visual_desc": "spiral borosilicate crystal cochlear shell glowing pearl-aqua",
        "macro_visual_desc": (
            "giant luminous pearl-aqua spiral snail-shell optical-glass cochlea filling 50% of the lateral basal midnight-navy chamber, "
            "framed by frosted borosilicate crystal-glass temporal petrous ribs along the foreground edges"
        ),
        "accent_rgb": (110, 238, 214),
        "short_role": "Spiral Sound Sensor",
    },
    "eyes": {
        "anchor_xy": (0.28, 0.49),
        "label_xy": (0.50, 0.20),
        "macro_anchor_xy": (0.38, 0.49),
        "macro_label_xy": (0.50, 0.20),
        "pos_3d_brain_xyz": (-0.06, -0.22, 1.44),
        "approach_azimuth_deg": -14.0,
        "approach_elevation_deg": -8.0,
        "glass_visual_desc": "bilateral 3D clinical eyeball & lens spheres inside anterior skull sockets",
        "macro_visual_desc": "anterior orbital eyes connecting through optic chiasm into the midbrain",
        "accent_rgb": (77, 187, 158),
        "short_role": "Visual Input",
    },
    "inner ear": {
        "anchor_xy": (0.55, 0.56),
        "label_xy": (0.50, 0.21),
        "macro_anchor_xy": (0.50, 0.50),
        "macro_label_xy": (0.50, 0.20),
        "pos_3d_brain_xyz": (-0.17, 0.04, 1.37),
        "approach_azimuth_deg": -96.0,
        "approach_elevation_deg": -14.0,
        "glass_visual_desc": "spiral cochlear snail-shell + three semicircular canals in temporal bone",
        "macro_visual_desc": "inner ear cochlea & vestibulocochlear nerve feeding the temporal cortex",
        "accent_rgb": (77, 187, 158),
        "short_role": "Auditory Sensor",
    },
    "white matter": {
        "anchor_xy": (0.48, 0.43),
        "label_xy": (0.50, 0.19),
        "macro_anchor_xy": (0.50, 0.48),
        "macro_label_xy": (0.50, 0.19),
        "pos_3d_brain_xyz": (-0.06, 0.00, 1.55),
        "approach_azimuth_deg": -48.0,
        "approach_elevation_deg": 12.0,
        "glass_visual_desc": "sweeping subcortical borosilicate crystal fiber-tract highway glowing warm amber-gold",
        "macro_visual_desc": (
            "giant luminous warm amber-gold sweeping optical-glass white-matter fiber highway filling 50% of the deep subcortical midnight-navy chamber, "
            "framed by frosted borosilicate crystal-glass cortical arches along the left and right edges"
        ),
        "accent_rgb": (255, 198, 74),
        "short_role": "Signal Highway",
    },
}


_SENSORY_SCREEN_ALIASES: dict[str, str] = {
    "eyes": "eyes",
    "eye": "eyes",
    "eyeball": "eyes",
    "eyeballs": "eyes",
    "ocular": "eyes",
    "inner ear": "inner ear",
    "semicircular canals": "inner ear",
    "vestibular canals": "inner ear",
    "auditory vestibule": "inner ear",
}


def resolve_anatomy_screen_anchor(region_text: str, *, macro_mode: bool = False) -> dict[str, Any] | None:
    """Resolves a region string (including multi-region strings) to its canonical display title, plain gloss, 3D previs coords, and 9:16 screen anchor."""
    raw = str(region_text or "").strip()
    if not raw:
        return None
    norm_raw = _norm(raw)
    canon = _SENSORY_SCREEN_ALIASES.get(norm_raw)
    if not canon:
        canon = resolve_region(raw)
    if not canon:
        found = find_regions(raw)
        canon = found[0] if found else None
    if not canon:
        for tok, target_k in _SENSORY_SCREEN_ALIASES.items():
            if re.search(rf"(?<![a-z]){re.escape(tok)}(?![a-z])", norm_raw):
                canon = target_k
                break
    if not canon:
        return None
    # Collapse compound frontal subtypes to clean viewer-friendly Prefrontal Cortex if both appear
    low_raw = raw.lower()
    if "prefrontal" in low_raw and "ventromedial" in low_raw and "dorsolateral" in low_raw:
        canon = "prefrontal cortex"
    spec = dict(ANATOMY_SCREEN_ANCHORS.get(canon) or {
        "anchor_xy": (0.48, 0.44),
        "label_xy": (0.50, 0.20),
        "macro_anchor_xy": (0.50, 0.48),
        "macro_label_xy": (0.50, 0.20),
        "pos_3d_brain_xyz": (0.00, -0.06, 1.50),
        "approach_azimuth_deg": -25.0,
        "approach_elevation_deg": 8.0,
        "macro_visual_desc": (
            f"giant luminous cool sapphire-blue optical-glass {canon} structure filling 50% of the deep midnight-navy chamber, "
            "framed by frosted borosilicate crystal-glass cortical ribs along the foreground edges"
        ),
        "accent_rgb": (72, 224, 255),
        "short_role": plain_name(canon).title(),
    })
    display_title = canon.title() if canon[0].islower() else canon
    wide_anchor = tuple(spec["anchor_xy"])
    wide_label = tuple(spec["label_xy"])
    mac_anchor = tuple(spec.get("macro_anchor_xy") or (0.50, 0.48))
    mac_label = tuple(spec.get("macro_label_xy") or (0.50, 0.20))
    glass_desc = str(
        spec.get("glass_visual_desc")
        or f"sculpted borosilicate crystal-glass {canon} structure ({spec.get('short_role') or plain_name(canon)})"
    )
    return {
        "canonical": canon,
        "display_title": display_title,
        "short_role": str(spec.get("short_role") or plain_name(canon).title()),
        "anchor_xy": mac_anchor if macro_mode else wide_anchor,
        "label_xy": mac_label if macro_mode else wide_label,
        "wide_anchor_xy": wide_anchor,
        "wide_label_xy": wide_label,
        "macro_anchor_xy": mac_anchor,
        "macro_label_xy": mac_label,
        "pos_3d_brain_xyz": tuple(float(v) for v in (spec.get("pos_3d_brain_xyz") or (0.0, -0.06, 1.50))),
        "approach_azimuth_deg": float(spec.get("approach_azimuth_deg") or -25.0),
        "approach_elevation_deg": float(spec.get("approach_elevation_deg") or 8.0),
        "glass_visual_desc": glass_desc,
        "macro_visual_desc": str(spec.get("macro_visual_desc") or ""),
        "accent_rgb": tuple(spec["accent_rgb"]),
    }


def build_neural_state_macro_desc(
    region: str,
    neural_state: str = "active",
    end_region: str | None = None,
) -> str:
    """
    Rule R74-B: Synthesizes a CV-gate-safe (`Q2` luma >= 32, `Q4` crystal/porcelain >= 0.04, `Q6` biolum >= 0.005,
    `R64` highlight chroma >= 6.0) and Zero-Flesh / Zero-Banned-Token `B1` ultra-macro description for all 4
    clinical neural states: `"active" | "silenced" | "severed" | "rerouted"`.
    """
    anc = resolve_anatomy_screen_anchor(region, macro_mode=True) or resolve_anatomy_screen_anchor("hippocampus", macro_mode=True)
    assert anc is not None
    anc_end = resolve_anatomy_screen_anchor(end_region, macro_mode=True) if str(end_region or "").strip() else None
    state = str(neural_state or "active").strip().lower()
    if state not in ("active", "silenced", "severed", "rerouted"):
        state = "active"

    title = anc["display_title"]
    role = anc["short_role"].lower()

    if state == "silenced":
        return (
            f"unlit frosted moonstone-white and pale-slate borosilicate crystal-glass {title} ({role}) resting quiet and unlit "
            "at the center of the deep midnight-navy chamber (50% frame), while subtle warm amber-gold and cool sapphire-blue "
            "optical-glass light flows gently along the intact flanking cortical ribs"
        )
    if state == "severed":
        if anc_end is not None and anc_end["canonical"] != anc["canonical"]:
            end_title = anc_end["display_title"]
            end_role = anc_end["short_role"].lower()
            return (
                f"sculpted borosilicate crystal-glass neural tract bridge from the luminous {title} toward the unlit frosted "
                f"moonstone-slate {end_title} ({end_role}) filling 50% of the deep midnight-navy chamber, cleanly severed mid-span "
                "by a crisp kintsugi gold fracture seam where the incoming cool sapphire-blue optical pulse halts and holds still"
            )
        return (
            f"unlit frosted moonstone-slate borosilicate crystal-glass {title} ({role}) isolated behind a crisp kintsugi gold "
            "fracture seam filling 50% of the deep midnight-navy chamber, where an incoming cool sapphire-blue and warm amber-gold "
            "optical pulse halts cleanly at the golden fault line along the flanking cortical ribs"
        )
    if state == "rerouted":
        if anc_end is not None and anc_end["canonical"] != anc["canonical"]:
            end_title = anc_end["display_title"]
            end_role = anc_end["short_role"].lower()
            return (
                f"arching borosilicate crystal-glass bypass tract sweeping past a quiet frosted moonstone-slate barrier from the "
                f"luminous {title} to ignite the {end_title} ({end_role}) in radiant warm amber-gold and deep crimson-red "
                "optical-glass light filling 50% of the deep midnight-navy chamber"
            )
        return (
            f"radiant warm amber-gold and deep crimson-red optical-glass {title} ({role}) ignited by an arching borosilicate "
            "crystal-glass bypass bridge curving around a quiet frosted moonstone-slate barrier, filling 50% of the deep midnight-navy chamber"
        )

    base = str(anc["macro_visual_desc"]).replace("electric cyan-blue", "cool sapphire-blue").replace("cyan-blue", "cool sapphire-blue")
    if anc_end is not None and anc_end["canonical"] != anc["canonical"]:
        return (
            f"{base}, with a bright warm amber-gold optical-glass tract bridge flowing cleanly toward the luminous "
            f"{anc_end['display_title']} hub"
        )
    return base


def build_neural_state_clip_clause(
    region: str,
    neural_state: str = "active",
    end_region: str | None = None,
) -> str:
    """
    Rule R74-B: Compact (`10-20w`) 2-beat state action clause for `ExpressiveV8PromptComposer` (`18-45w` Prompt Diet).
    """
    anc = resolve_anatomy_screen_anchor(region, macro_mode=True) or resolve_anatomy_screen_anchor("hippocampus", macro_mode=True)
    assert anc is not None
    anc_end = resolve_anatomy_screen_anchor(end_region, macro_mode=True) if str(end_region or "").strip() else None
    state = str(neural_state or "active").strip().lower()
    t_a = anc["display_title"].lower()
    t_b = anc_end["display_title"].lower() if anc_end is not None else t_a

    if state == "silenced":
        return f"Frosted moonstone-slate crystal {t_a} stays unlit and still while subtle amber-gold glow glides along flanking ribs."
    if state == "severed":
        if anc_end is not None and anc_end["canonical"] != anc["canonical"]:
            return f"Sapphire-blue optical pulse races from crystal {t_a} and halts at a kintsugi gold seam before unlit frosted {t_b}."
        return f"Sapphire-blue optical pulse halts cleanly at a kintsugi gold fracture seam before the unlit frosted crystal {t_a}."
    if state == "rerouted":
        if anc_end is not None and anc_end["canonical"] != anc["canonical"]:
            return f"Amber-gold bypass pulse arches from crystal {t_a} around frosted glass to ignite radiant crimson-red {t_b}."
        return f"Arching amber-gold bypass pulse curves past frosted slate glass to ignite the crystal {t_a} in crimson-red glow."
    if anc_end is not None and anc_end["canonical"] != anc["canonical"]:
        return f"Bright sapphire-blue and amber-gold optical pulse glides smoothly along crystal tract from {t_a} into glowing {t_b}."
    return f"Warm amber-gold and sapphire-blue optical pulses ripple smoothly across the luminous borosilicate crystal {t_a}."
