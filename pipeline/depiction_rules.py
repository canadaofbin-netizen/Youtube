"""
ALL ABOUT BRAIN — Modular Depiction Rules & Compositional Prompt Engine (Rules R53 & R54).

Mirrors the 5 modular rule files under `.agents/rules/`:
  1. `CastDepictionRule`      -> `.agents/rules/cast_depiction_rules.md`      (R14-A Cast, R45 Cranium, R46 Wardrobe)
  2. `SceneDepictionRule`     -> `.agents/rules/scene_depiction_rules.md`     (R14-A Env, R46, R46-K, R47)
  3. `BrainDepictionRule`     -> `.agents/rules/brain_depiction_rules.md`     (R21, R38, R48, R53 Restrained Signal)
  4. `CameraDepictionRule`    -> `.agents/rules/camera_choreography_rules.md` (R14-D, R14-D v5)
  5. `ReferenceDepictionRule` -> `.agents/rules/reference_depiction_rules.md` (R51, R52)

`PromptComposer` combines these modular depiction blocks deterministically into:
  - Frozen 9:16 / 16:9 reference still-frame prompts (`compose_still_frame_prompt`)
  - Reference-conditioned 8s / 10s video clip prompts (`compose_timed_video_prompt`)
"""

from __future__ import annotations

import re
from typing import Any

from pipeline.config import (
    BRAIN_SETTINGS,
    DIORAMA_V7_BRAIN_RENDER_MODES,
    FLOW_ASPECT_LABELS,
    FLOW_ASPECT_SHORTS,
    FLOW_MOTION_STYLE_V5,
    FLOW_VOICE_PROMPT_DESCRIPTOR_V5,
    GEMINI_APP_MAX_RENDER_SEC,
    PORCELAIN_V7_BRAIN_RENDER_MODES,
    PORCELAIN_V7_VISUAL_GRAMMARS,
    TIMED_BEAT_WINDOWS,
)

# ==============================================================================
# R53 — Banned Flying-Particle / Spark / Fireworks Tokens in Brain Scenes
# ==============================================================================
BANNED_BRAIN_PARTICLE_TOKENS: tuple[str, ...] = (
    "signal particles",
    "glowing particles",
    "green particles",
    "particles",
    "sparks",
    "sparking",
    "scattering",
    "scatters into space",
    "scatter into space",
    "splashing",
    "confetti",
    "fireworks",
    "floating dots",
    "drifting dust",
    "exploding glow",
    "bioluminescent green",
    "electric cyan-blue",
    "cyan-blue",
    "neon green",
    "neon blue",
    "fluorescent green",
)

_BRAIN_SIGNAL_REWRITES: tuple[tuple[re.Pattern[str], str], ...] = (
    # Colliding / scattering particles at severed junctions -> calm halt & dim
    (
        re.compile(
            r"(?:,\s*)?(?:its\s+|and\s+|the\s+|glowing\s+|green\s+)?(?:signal\s+)?particles\s+(?:colliding\s+and\s+)?scatter(?:ing)?\s+into\s+space",
            re.IGNORECASE,
        ),
        " as the internal pulse halts and dims quietly",
    ),
    (
        re.compile(
            r"as\s+(?:signal\s+|the\s+internal\s+tract\s+illumination\s+|internal\s+fiber\s+light\s+pulse\s+)?(?:particles\s+scatter\s+into\s+space|halts\s+cleanly\s+at\s+the\s+severed\s+margin\s+and\s+fades\s+to\s+quiet\s+stillness)",
            re.IGNORECASE,
        ),
        "as the internal pulse halts and dims quietly",
    ),
    (
        re.compile(
            r"and\s+(?:the\s+green\s+particles\s+|the\s+internal\s+fiber\s+light\s+pulse\s+)?(?:scatters?\s+into\s+space|dims\s+quietly\s+into\s+space)",
            re.IGNORECASE,
        ),
        "and the soft internal pulse halts and dims quietly",
    ),
    # Verbose first-pass rewrites -> concise internal fiber pulse without neon green/blue
    (
        re.compile(
            r"sends\s+a\s+smooth(?:,\s+steady)?\s+bioluminescent\s+green\s+(?:light\s+)?pulse\s+(?:gliding\s+cleanly\s+)?inside",
            re.IGNORECASE,
        ),
        "sends a soft warm-ivory light pulse inside",
    ),
    (
        re.compile(
            r"guiding\s+a\s+smooth(?:,\s+steady)?\s+bioluminescent\s+green\s+(?:light\s+)?pulse\s+(?:cleanly\s+)?inside\s+(?:the\s+)?intact\s+(?:fiber\s+bundles|tracts)",
            re.IGNORECASE,
        ),
        "guiding a soft warm-ivory light pulse inside intact tracts",
    ),
    (
        re.compile(
            r"a\s+smooth(?:,\s+steady)?\s+bioluminescent\s+green\s+light\s+pulse\s+glides\s+(?:cleanly\s+)?inside\s+the\s+(?:white-matter\s+)?fiber\s+tracts",
            re.IGNORECASE,
        ),
        "a soft warm-ivory light pulse glides inside the fiber tracts",
    ),
    # Streaming / firing / routing signal particles -> smooth internal subsurface light pulse inside fibers
    (
        re.compile(
            r"\bfires\s+bioluminescent\s+green\s+signal\s+particles\s+along\b",
            re.IGNORECASE,
        ),
        "sends a soft warm-ivory light pulse inside",
    ),
    (
        re.compile(
            r"\brouting\s+bioluminescent\s+green\s+signal\s+particles\s+in\s+a\s+steady\s+collimated\s+flow\b",
            re.IGNORECASE,
        ),
        "guiding a soft warm-ivory light pulse inside intact tracts",
    ),
    (
        re.compile(
            r"\bbioluminescent\s+green\s+signal\s+particles\s+stream(?:\s+in\s+a\s+collimated\s+flow)?\b",
            re.IGNORECASE,
        ),
        "a soft warm-ivory light pulse glides inside the tracts",
    ),
    (
        re.compile(
            r"\ba\s+(?:cue-triggered\s+)?(?:burst|pattern)\s+of\s+bioluminescent\s+green\s+(?:signal\s+)?particles\s+(?:enters|streams)\b",
            re.IGNORECASE,
        ),
        "a calm warm-ivory light pulse glides inside the tracts",
    ),
    (
        re.compile(
            r"\bfine\s+particles\s+drift\s+through\s+the\s+bright\s+air\.?",
            re.IGNORECASE,
        ),
        "Soft rim light traces the cortical folds.",
    ),
    # Neon green / cyan-blue colour tokens -> subtle warm-ivory / warm amber-gold
    (
        re.compile(r"\bbioluminescent\s+green\b", re.IGNORECASE),
        "soft warm-ivory",
    ),
    (
        re.compile(r"\b(?:electric\s+)?cyan-blue\b", re.IGNORECASE),
        "subtle warm amber-gold",
    ),
    (
        re.compile(r"\b(?:neon|fluorescent)\s+(?:green|blue)\b", re.IGNORECASE),
        "soft warm-ivory",
    ),
    (
        re.compile(r"\bsubsurface\s+green\b", re.IGNORECASE),
        "subsurface warm-ivory",
    ),
    (
        re.compile(r"\bgreen\s+light\s+pulse\b", re.IGNORECASE),
        "warm-ivory light pulse",
    ),
    (
        re.compile(r"\bgreen\s+internal\s+light\s+pulses?\b", re.IGNORECASE),
        "warm-ivory internal light pulses",
    ),
    # Generic leftover particle / spark nouns inside brain descriptions
    (
        re.compile(r"\b(?:glowing\s+|green\s+|signal\s+)?particles\b", re.IGNORECASE),
        "light pulse",
    ),
    (
        re.compile(r"\bsparks?\s+scattering\b", re.IGNORECASE),
        "pulse halting",
    ),
    (
        re.compile(r"\bsparks?\b", re.IGNORECASE),
        "subsurface glow",
    ),
    (
        re.compile(r"\bscatter(?:s|ed|ing)?\b", re.IGNORECASE),
        "dims quietly",
    ),
    (
        re.compile(r"\bseahorse-(?:shaped|like)\b", re.IGNORECASE),
        "C-shaped tubular neuroanatomical",
    ),
)


class CastDepictionRule:
    """Rule R14-A (Cast), R45 (Cranium), R46 (Wardrobe & Porcelain Animals)."""

    @staticmethod
    def cranium_clause(visual_mode: str, setting: str = "real_env") -> str:
        mode = str(visual_mode or "NEURO_BIOLOGY").upper()
        if mode == "BEHAVIORAL_PSYCH":
            return "with a smooth opaque matte-white porcelain head"
        if mode == "HYBRID" and setting not in BRAIN_SETTINGS:
            return "with a smooth opaque matte-white porcelain head"
        return "with a translucent frosted-glass cranium softly revealing the matte-white brain gyri inside"

    @staticmethod
    def cast_lock_entries(plan: dict[str, Any]) -> list[dict[str, str]]:
        cast = plan.get("cast") or {}
        wardrobe = cast.get("wardrobe") if isinstance(cast, dict) else None
        if isinstance(wardrobe, dict) and wardrobe:
            return [{"id": str(k), "look": str(v).strip()} for k, v in wardrobe.items() if str(v).strip()]
        entries: list[dict[str, str]] = []
        if isinstance(cast, dict) and cast.get("subject"):
            entries.append({"id": "subject", "look": str(cast["subject"]).strip()})
        for i, other in enumerate((cast.get("others") or []) if isinstance(cast, dict) else []):
            if str(other).strip():
                entries.append({"id": f"other_{i + 1}", "look": str(other).strip()})
        return entries

    @classmethod
    def cast_lock_clause(cls, plan: dict[str, Any], entries: list[dict[str, str]] | None = None) -> str:
        chosen = entries if entries is not None else cls.cast_lock_entries(plan)
        if not chosen:
            return "Every person is an articulated matte-white porcelain mannequin with smooth ball-jointed limbs and zero human skin."
        parts = [f"{e['id'].replace('_', ' ')} in {e['look']}" for e in chosen]
        return (
            "Every person is an articulated matte-white porcelain mannequin, same design in every shot: "
            + "; ".join(parts)
            + "."
        )


class SceneDepictionRule:
    """Rule R14-A (Environment/Lighting/Scale), R46 (Iconic Scene), R46-K (Key Visual), R47 (Action-Physics)."""

    @staticmethod
    def clean_clause(text: str) -> str:
        t = str(text or "").strip()
        return t[:-1].strip() if t.endswith(".") else t

    @classmethod
    def environment_clause(cls, plan: dict[str, Any], shot: dict[str, Any]) -> str:
        env = cls.clean_clause(shot.get("environment") or plan.get("real_environment") or "a bright documentary room")
        return f"{env[:1].upper() + env[1:]}." if env else "Bright high-key documentary setting."

    @classmethod
    def timed_beats_clause(cls, shot: dict[str, Any], fallback_scene: str = "") -> str:
        action = cls.clean_clause(shot.get("action") or "")
        prop = cls.clean_clause(shot.get("prop_change") or "")
        react = cls.clean_clause(shot.get("reaction") or "")
        w0, w1, w2 = TIMED_BEAT_WINDOWS
        beats = []
        if action:
            beats.append(f"{w0[0]}-{w0[1]}s: {action}.")
        if prop:
            beats.append(f"{w1[0]}-{w1[1]}s: {prop}.")
        if react:
            beats.append(f"{w2[0]}-{w2[1]}s: {react}.")
        return " ".join(beats) if beats else cls.clean_clause(fallback_scene) + "."


class BrainDepictionRule:
    """Rule R21 (Restrained Palette), R38 (Semi-Translucent 3D Anatomy & Fracture Physics), R48 (Brain-Story Link), R53 (Restrained Conduction)."""

    RESTRAINT_LOCK = "Subtle subsurface luminance stays smoothly contained inside the matte-white fiber tracts."
    DEEP_SUBCORTICAL_CROSS_SECTION_CLAUSE = (
        "Because the brain is opaque matte-white porcelain, a clean architectural cross-section cut (stepped sagittal "
        "and coronal brain slice) opens the near cerebral hemisphere to expose the flat internal brain cross-section, "
        "corpus callosum arch, and inner ventricular cavity with the 3D deep subcortical structure physically nestled inside."
    )
    DEEP_SUBCORTICAL_TRANSLUCENT_CLAUSE = (
        "Outer cortical hemispheres are rendered in semi-translucent frosted matte-white porcelain/glass so the full 3D "
        "whole-brain silhouette stays intact while revealing the sculpted 3D deep subcortical structure and cerebellar "
        "arbor vitae glowing softly inside."
    )
    DEEP_SUBCORTICAL_CUTAWAY_CLAUSE = DEEP_SUBCORTICAL_CROSS_SECTION_CLAUSE
    PORCELAIN_FRACTURE_CLAUSE = (
        "Tactile porcelain fracture physics (trauma/lesion scenes only): a crisp structural hairline crack splits across "
        "the damaged matte-white porcelain tract with muted crimson-red glowing quietly inside the fracture seam."
    )

    @classmethod
    def fracture_clause_if_damaged(cls, has_lesion_or_trauma: bool) -> str:
        """Returns the porcelain crack/fracture clause ONLY when the clip depicts actual brain trauma, lesion, or severed tracts."""
        return cls.PORCELAIN_FRACTURE_CLAUSE if has_lesion_or_trauma else ""

    @staticmethod
    def sanitize_brain_signal_text(text: str, preserve_cyan_blue: bool = False) -> str:
        """Rewrites any particle/spark/scattering wording in brain scenes into calm internal tract conduction (R53)."""
        out = str(text or "")
        for pat, repl in _BRAIN_SIGNAL_REWRITES:
            if preserve_cyan_blue and repl == "subtle warm amber-gold":
                continue
            out = pat.sub(repl, out)
        out = re.sub(r"\s{2,}", " ", out).strip()
        out = re.sub(r"\s+([.,;:])", r"\1", out)
        return out

    @classmethod
    def format_brain_scene(cls, raw_scene: str, append_restraint_lock: bool = True, preserve_cyan_blue: bool = False) -> str:
        cleaned = cls.sanitize_brain_signal_text(raw_scene, preserve_cyan_blue=preserve_cyan_blue)
        if append_restraint_lock and "subsurface luminance stays smoothly contained" not in cleaned.lower():
            if not cleaned.endswith("."):
                cleaned += "."
            cleaned = f"{cleaned} {cls.RESTRAINT_LOCK}"
        return cleaned

    @staticmethod
    def validate_restrained_signal(scene_text: str, setting: str, allow_cyan_blue: bool = False) -> list[str]:
        """Returns `[brain_signal]` gate errors if a brain clip contains banned flying-particle or spark words (R53)."""
        if str(setting or "") not in BRAIN_SETTINGS:
            return []
        low = str(scene_text or "").lower()
        # Strip negated phrases like "zero flying particles, zero sparks" before checking positive violations
        stripped = re.sub(
            r"\b(?:no|zero|without(?:\s+any)?)\s+(?:flying\s+|glowing\s+|floating\s+|drifting\s+)?(?:signal\s+)?"
            r"(?:particles|sparks|dots|dust|confetti|fireworks)\b",
            "",
            low,
        )
        violations: list[str] = []
        for tok in BANNED_BRAIN_PARTICLE_TOKENS:
            if allow_cyan_blue and tok in ("cyan-blue", "electric cyan-blue"):
                continue
            if re.search(rf"(?<![a-z]){re.escape(tok)}(?![a-z])", stripped):
                violations.append(tok)
        if violations:
            return [
                f"[brain_signal] R53 violation: brain scene contains banned particle/spark VFX wording {violations}; "
                "use smooth internal light pulse gliding inside white-matter tracts instead"
            ]
        return []


class CameraDepictionRule:
    """Rule R14-D & R14-D v5 — Single Clean Camera Move Per Clip."""

    @staticmethod
    def camera_clause(shot: dict[str, Any], default_move: str = "Smooth documentary tracking shot") -> str:
        cam = SceneDepictionRule.clean_clause(shot.get("camera") or default_move)
        return f"{cam[:1].upper() + cam[1:]}."


class ReferenceDepictionRule:
    """Rule R51 & R52 — Still-Frame Prefix & Video Start-Frame Continuity Lock."""

    CONTINUITY_LOCK_BRAIN = (
        "Continue smoothly from the provided anatomical reference image: identical matte-white porcelain mannequin "
        "head and neck with cutaway cranium, full matte-white 3D brain inside the skull, high-contrast cool slate-grey "
        "studio backdrop, and subtle warm-ivory internal tract luminance with zero green or blue neon effects."
    )
    CONTINUITY_LOCK_REAL = (
        "Continue exactly from the provided start image: same porcelain mannequins, period clothes, room, props, and daylight."
    )

    @staticmethod
    def still_prefix(aspect: str = FLOW_ASPECT_SHORTS) -> str:
        label = FLOW_ASPECT_LABELS.get(aspect, FLOW_ASPECT_LABELS[FLOW_ASPECT_SHORTS])
        return f"Generate a single {label} still photograph (one frozen instant, not a video):"


class PromptComposer:
    """Rule R54 — Composes Cast + Scene/Brain + Camera + Reference Depiction Rules into Final Prompts."""

    @staticmethod
    def _aspect_framing_clause(aspect: str = FLOW_ASPECT_SHORTS) -> str:
        if aspect == FLOW_ASPECT_SHORTS:
            return (
                "Native vertical 9:16 portrait composition against a high-contrast cool slate-grey studio backdrop, "
                "with dynamic camera progression from the porcelain head into the open anatomical brain cross-section "
                "tracking the neural circuit."
            )
        return (
            "Native horizontal 16:9 widescreen composition against a high-contrast cool slate-grey studio backdrop, "
            "with dynamic camera progression from the porcelain head into the open anatomical brain cross-section."
        )

    @staticmethod
    def compose_brain_still_prompt(raw_brain_scene: str, aspect: str = FLOW_ASPECT_SHORTS) -> str:
        prefix = ReferenceDepictionRule.still_prefix(aspect)
        core = BrainDepictionRule.format_brain_scene(raw_brain_scene, append_restraint_lock=True)
        core = re.sub(
            r"^The camera dives smoothly through[^.]*?into\s+a\s+bright\s+white\s+studio\s+gallery\s+holding\s+",
            "Against a cool slate-grey studio backdrop, ",
            core,
            flags=re.IGNORECASE,
        )
        core = re.sub(r"\bas the full brain turns slowly in the (?:gallery )?light\b", "in crisp studio light", core, flags=re.IGNORECASE)
        core = re.sub(r"\bThe camera tracks the (?:flowing signal|internal luminance) along\b", "Smooth subsurface luminance traces", core, flags=re.IGNORECASE)
        if "porcelain mannequin head" not in core.lower():
            core = (
                "Clean three-quarter profile of a smooth matte-white porcelain mannequin head and neck with an architectural "
                "cutaway cranium revealing a realistic matte-white 3D porcelain brain inside the skull against a high-contrast "
                f"cool slate-grey studio backdrop. {core}"
            )
        framing = PromptComposer._aspect_framing_clause(aspect)
        return f"{prefix} {core} {framing} Minimalist clean porcelain sculpture style, razor-sharp focus, soft studio light, no text, no watermark."

    @staticmethod
    def compose_brain_video_prompt(
        raw_brain_scene: str,
        narration: str,
        voice_source: str = "tts",
        aspect: str = FLOW_ASPECT_SHORTS,
    ) -> str:
        label = FLOW_ASPECT_LABELS.get(aspect, FLOW_ASPECT_LABELS[FLOW_ASPECT_SHORTS])
        vprefix = f"Generate an {GEMINI_APP_MAX_RENDER_SEC}-second {label} video clip:"
        core = BrainDepictionRule.format_brain_scene(raw_brain_scene, append_restraint_lock=True)
        framing = PromptComposer._aspect_framing_clause(aspect)
        cont = ReferenceDepictionRule.CONTINUITY_LOCK_BRAIN
        if voice_source == "native":
            tail = f'{FLOW_VOICE_PROMPT_DESCRIPTOR_V5} Spoken narration: "{narration.strip()}"'
        else:
            tail = "Audio: subtle room ambience only, no speech, no narration, no music."
        return f"{vprefix} {core} {framing} {cont} {tail}"


# ==============================================================================
# Schema v6 Neuro-Diorama Rules — Ghost-Lab & Pedestal Frosted-Crystal Specimen (R56)
# ==============================================================================
DIORAMA_CAMERA_DESCRIPTORS: dict[str, str] = {
    "smooth_tilt_up": "Smooth vertical camera tilt-up",
    "smooth_tilt_down": "Smooth vertical camera tilt-down",
    "horizontal_tracking_pan": "Slow horizontal tracking pan",
    "isometric_push_in": "Smooth high-angle isometric push-in",
    "locked_macro_gauge": "Locked macro tabletop frame with crisp physical instrument motion",
    "dynamic_dolly_rush_in": "Poised 3D motion-control probe camera gliding smoothly forward along the Z-axis at an unhurried cinematic pace with strong foreground-to-background parallax",
    "orbital_3d_arc_sweep": "Sweeping 3D 45-degree orbital camera arc circling unhurriedly through space with rich volumetric depth parallax",
    "crane_swoop_dive": "Smooth 3D crane descent gliding unhurriedly from an elevated overview down into the miniature interior space with strong parallax",
    "low_angle_chase_track": "Low-angle 3D tracking camera gliding smoothly at a poised cinematic pace alongside the moving action with foreground depth parallax",
    "vertical_rocket_ascent": "Steady vertical 3D tracking camera rising smoothly straight upward alongside the trajectory through deep space",
    "fpv_trench_passthrough": "Immersive 3D macro probe lens gliding unhurriedly forward through the miniature architectural framing and structural beams",
    "pullback_parallax_reveal": "Poised 3D dolly pullback expanding smoothly backward from a macro close-up to reveal the full illuminated scale structure",
}

DYNAMIC_3D_CAMERA_LEADS: dict[str, str] = {
    "dynamic_dolly_rush_in": "Smooth 3D probe-lens dolly glide forward at an unhurried cinematic pace with strong depth parallax:",
    "orbital_3d_arc_sweep": "Unhurried 3D 45-degree orbital arc camera shot sweeping smoothly through volumetric space:",
    "crane_swoop_dive": "Poised 3D crane camera gliding smoothly down into the scene:",
    "low_angle_chase_track": "Smooth low-angle 3D tracking camera gliding unhurriedly alongside the action:",
    "vertical_rocket_ascent": "Steady vertical 3D upward tracking camera rising smoothly through space:",
    "fpv_trench_passthrough": "Immersive 3D macro probe-lens pass-through gliding smoothly inside the miniature:",
    "pullback_parallax_reveal": "Unhurried 3D dolly pullback reveal with layered foreground parallax:",
}

ZERO_FLESH_AND_TEXT_LOCK = (
    "Crafted architectural scale model on a plain unlabelled dark-oak base against a deep midnight-navy backdrop only, "
    "zero bright white walls, zero human skin, zero facial features, zero eyes, zero nose, zero mouth, zero hair, zero gore, "
    "zero plaques, zero nameplates, zero engravings, zero text, zero letters, zero numbers, blank matte surfaces."
)

CRYSTAL_SPECIMEN_NEGATIVE_LOCK = (
    "Sculptural architectural scale artifact on a plain unlabelled dark-oak pedestal against a deep midnight-navy backdrop only, "
    "zero bright white walls, zero human skin, zero facial features, zero eyes, zero nose, zero mouth, zero ears, zero gore, "
    "zero plaques, zero nameplates, zero engravings, zero text, zero letters, zero numbers, blank matte surfaces."
)

BRAIN_DARK_VOID_NEGATIVE_LOCK = (
    "Clean 3D medical neuro-visualization floating isolated in a deep midnight-navy black void only, "
    "zero background tables, zero bright white walls, zero human skin, zero facial features, zero eyes, "
    "zero plaques, zero text, zero letters, zero numbers."
)

_NEGATED_SPAN_RE = re.compile(
    r"\b(?:no|zero|without(?:\s+any)?|uninhabited|empty)\s+"
    r"(?:human\s+|living\s+|photoreal\s+|full-body\s+|visible\s+|in-scene\s+|written\s+|garbled\s+|facial\s+|bright\s+white\s+|roadside\s+)?'"
    r"?(?:people|persons?|humans?|figures?|bystanders?|flesh|skin|faces?|features?|eyes?|eyeballs?|nose|mouth|ears?|hair|anatomy|hands?|fingers?|feet|mannequins?|"
    r"crowds?|animals?|dogs?|horses?|gore|blood|walls?|plaques?|nameplates?|engravings?|ferrules?|markings?|text|letters?|numbers?|signage|signs?|labels?|speech|narration|music|watermark)\b",
    flags=re.IGNORECASE,
)

_ALLOWED_CRYSTAL_PHRASES_RE = re.compile(
    r"\b(?:satin-frosted(?:\s+borosilicate)?\s+optical\s+crystal\s+(?:human\s+|upper\s+)?(?:dome\s+sculpture|head\s+bust|hand\s+sculpture|cranium)|"
    r"translucent\s+crystal\s+(?:cranium|dome\s+sculpture|head\s+bust|hand\s+sculpture)|"
    r"crystal\s+(?:dome\s+sculpture|head\s+bust|hand\s+sculpture|upper\s+cranium|cranium|finger\s+facets?|cheek\s+facet))\b",
    flags=re.IGNORECASE,
)

_CERAMIC_CHARACTER_SCENE_RE = re.compile(
    r"\bbisque-ceramic\b|\bceramic\s+(?:architectural\s+|miniature\s+)?(?:scale\s+)?figures?\b",
    flags=re.IGNORECASE,
)

_ALLOWED_CERAMIC_SCALE_PHRASES_RE = re.compile(
    r"\b(?:(?:clothed\s+|sculpted\s+|small\s+|lone\s+|featureless\s+|smooth\s+|ovoid\s+|matte-white\s+|unglazed\s+)*bisque-ceramic\s+(?:architectural\s+|miniature\s+)?(?:scale\s+)?(?:figures?|bust|models?|dome|crew|crewmates?|driver|physician)?|"
    r"ceramic\s+(?:architectural\s+|miniature\s+)?(?:scale\s+)?(?:figures?|crewmates?|driver|physician|head-and-shoulders\s+scale\s+model|lower\s+head|head|skull|cranium|crown|cheek|hands?|arms?|shoulders?|legs?|knees?|feet|boots?|torso|posture)|"
    r"featureless\s+(?:smooth\s+)?ovoid\s+(?:matte-white\s+)?(?:ceramic\s+)?(?:head|dome|cranium)?|"
    r"(?:simplified\s+)?sculpted\s+(?:matte(?:-white)?\s+)?ceramic\s+(?:hands?|arms?|limbs?|legs?|boots?|coat|clothing|head))\b",
    flags=re.IGNORECASE,
)

_CERAMIC_CONTEXT_LIMBS_RE = re.compile(
    r"\b(?:hand|hands|finger|fingers|wrist|arm|arms|shoulder|shoulders|torso|chest|back|waist|legs?|knees?|foot|feet|footsteps|"
    r"shoes|boots|posture|head|skull|cranium|crown|cheek|cheekbone|forehead|jaw|chin|"
    r"hat|hats|cap|caps|helmet|helmets|bonnet|coat|coats|duster|vest|vests|waistcoat|jacket|shirt|sleeves|trousers|pants|"
    r"apron|gown|suit|collar|tie|belt|gloves|linen\s+head\s+wrap|head\s+wrap|eyeglasses)\b",
    flags=re.IGNORECASE,
)

_BANNED_FLESH_MANNEQUIN_TEXT_RE = re.compile(
    r"\b(?:person|people|human|humans|man|men|woman|women|boy|girl|child|baby|doctor|surgeon|scientist|"
    r"researcher|patient|volunteer|participant|worker|crowd|pedestrian|mannequin|mannequins|"
    r"skin|flesh|eyeball|eyeballs|eyes|mouth|lips|hair|torso|legs|footsteps|shoes|"
    r"dog|dogs|horse|horses|ox|oxen|monkey|monkeys|rat|rats|mouse|mice|cat|cats|gorilla|animal|animals|"
    r"signboard|signage|chalkboard|whiteboard|banner|subtitle|caption|written\s+text|printed\s+letters)\b",
    flags=re.IGNORECASE,
)

_BANNED_BODY_PARTS_OUTSIDE_CRYSTAL_RE = re.compile(
    r"\b(?:face|faces|hand|hands|finger|fingers|wrist|arm|arms|foot|feet)\b",
    flags=re.IGNORECASE,
)


class DioramaCutawayRule:
    """R56 Grammar 1: Architectural cutaway miniature diorama on a dark-oak base in midnight-navy void (supports 40-degree isometric & dynamic 3D probe/crane/low-angle rigs)."""

    @staticmethod
    def compose(
        environment: str,
        kinetic_action: str,
        lighting: str = "warm tungsten interior pools and crisp chiaroscuro rim lighting",
        camera_move: str = "isometric_push_in",
    ) -> str:
        env = SceneDepictionRule.clean_clause(environment)
        act = SceneDepictionRule.clean_clause(kinetic_action)
        lit = SceneDepictionRule.clean_clause(lighting)
        cam_key = str(camera_move or "isometric_push_in").strip().lower()
        if cam_key == "low_angle_chase_track":
            angle_lead = f"Low-angle 3D cinema architectural cutaway miniature model of {env}"
        elif cam_key == "fpv_trench_passthrough":
            angle_lead = f"Immersive 3D probe-lens architectural cross-section miniature model of {env}"
        elif cam_key == "crane_swoop_dive":
            angle_lead = f"Deep multi-level 3D architectural cross-section cutaway miniature model of {env}"
        elif cam_key in ("orbital_3d_arc_sweep", "dynamic_dolly_rush_in", "pullback_parallax_reveal", "vertical_rocket_ascent"):
            angle_lead = f"Sculptural 3D architectural cross-section cutaway miniature model of {env}"
        else:
            angle_lead = f"High-angle 40-degree isometric architectural cross-section cutaway miniature model of {env}"
        return (
            f"{angle_lead} mounted on a thick plain dark-oak diorama base floating in a deep midnight-navy studio void under {lit}. "
            f"{act[:1].upper() + act[1:]}. Cinema macro probe lens with shallow depth of field."
        )


class KineticTracePropRule:
    """R56 Grammar 2: Macro tabletop instruments & matte bisque-ceramic scale figures / self-actuating traces."""

    @staticmethod
    def compose(prop_setup: str, self_actuating_motion: str, physical_consequence: str) -> str:
        s1 = SceneDepictionRule.clean_clause(prop_setup)
        s2 = SceneDepictionRule.clean_clause(self_actuating_motion)
        s3 = SceneDepictionRule.clean_clause(physical_consequence)
        return (
            f"Macro tabletop miniature view against a deep midnight-navy studio void under dramatic chiaroscuro rim lighting: {s1}. "
            f"{s2[:1].upper() + s2[1:]}, while {s3}. Shallow tilt-shift depth of field."
        )


class SensorMotifRule:
    """R56 Grammar 3: Recurring physical analog gauge / water-glass sensor motif in midnight-navy void."""

    @staticmethod
    def compose(motif_object: str, state_transition: str) -> str:
        obj = SceneDepictionRule.clean_clause(motif_object)
        st = SceneDepictionRule.clean_clause(state_transition)
        return (
            f"Macro studio close-up of {obj} resting on a dark walnut workbench against a deep midnight-navy studio void "
            f"under crisp chiaroscuro rim lighting. {st[:1].upper() + st[1:]}. Shallow tilt-shift miniature depth of field."
        )


class TactileTokenGridRule:
    """R56 Grammar 4: Turned-oak token grids, hourglasses & translucent acrylic tabletop ratios in midnight-navy void."""

    @staticmethod
    def compose(token_layout: str, ratio_animation: str) -> str:
        lay = SceneDepictionRule.clean_clause(token_layout)
        anim = SceneDepictionRule.clean_clause(ratio_animation)
        return (
            f"Clean overhead-angled macro view of {lay} arranged on a dark oak drafting plinth floating in a deep "
            f"midnight-navy studio void under dramatic rim lighting. {anim[:1].upper() + anim[1:]}."
        )


class LiteralAnalogyCutawayRule:
    """R57-V Grammar 5: Literal 1:1 everyday physical analogy diorama (football stadium field, bowling ball, baseball bat, coffee cup) in midnight-navy void."""

    @staticmethod
    def compose(
        analogy_scene: str,
        comparison_motion: str,
        camera_move: str = "orbital_3d_arc_sweep",
    ) -> str:
        sc = SceneDepictionRule.clean_clause(analogy_scene)
        mot = SceneDepictionRule.clean_clause(comparison_motion)
        cam_key = str(camera_move or "orbital_3d_arc_sweep").strip().lower()
        if cam_key == "low_angle_chase_track":
            lead = f"Low-angle 3D cinema miniature scale comparison diorama of {sc}"
        elif cam_key in ("crane_swoop_dive", "pullback_parallax_reveal"):
            lead = f"Elevated 3D architectural scale comparison diorama of {sc}"
        else:
            lead = f"Sculptural 3D miniature scale comparison diorama of {sc}"
        return (
            f"{lead} mounted on a plain dark-oak diorama base floating in a deep midnight-navy studio void under crisp chiaroscuro rim lighting. "
            f"{mot[:1].upper() + mot[1:]}. Cinema macro probe lens with shallow depth of field."
        )


class ArchitecturalBrainMaquetteRule:
    """R56 Grammar 5: 2-Mode Isolated Dark-Void 3D Brain Visualization (Opaque Matte-White Cortical Sulcal-Glow vs Semi-Translucent Smoked-Glass Subcortical X-Ray)."""

    _SUBCORTICAL_HINT_RE = re.compile(
        r"\b(?:amygdala|amygdalae|hippocampus|hippocampi|hippocampal|thalamus|thalamic|striatum|basal\s+ganglia|"
        r"limbic|subcortical|substantia\s+nigra|nucleus\s+accumbens|hypothalamus|internal\s+fiber|deep\s+hub)\b",
        flags=re.IGNORECASE,
    )

    @classmethod
    def compose(cls, maquette_or_bci_scene: str, brain_mode: str = "auto") -> str:
        cleaned = BrainDepictionRule.format_brain_scene(
            maquette_or_bci_scene,
            append_restraint_lock=True,
            preserve_cyan_blue=True,
        )
        mode_norm = str(brain_mode or "auto").strip().lower()
        use_xray = (
            mode_norm in ("translucent_smoked_glass_subcortical_xray", "subcortical_xray", "xray", "translucent")
            or (mode_norm == "auto" and bool(cls._SUBCORTICAL_HINT_RE.search(cleaned)))
        )
        if "midnight-navy" not in cleaned.lower() and "midnight navy" not in cleaned.lower() and "black void" not in cleaned.lower():
            if use_xray:
                cleaned = (
                    "Clean 3D medical X-ray neuro-visualization isolated in a deep midnight-navy black void with zero "
                    "background furniture: an intact whole 3D anatomical brain rendered with a semi-translucent frosted "
                    "smoked-glass outer cerebral cortex and cerebellum with delicate rim-lit gyri contours, revealing "
                    f"deep internal 3D subcortical anatomy. {cleaned}"
                )
            else:
                cleaned = (
                    "Clean 3D medical neuro-visualization isolated in a deep midnight-navy black void with zero "
                    "background furniture: an anatomically accurate opaque sculpted matte-white 3D whole brain with "
                    "smooth chalk-white gyri, deep sulcal grooves, cerebellum, and brainstem floating cleanly in dark space. "
                    f"{cleaned}"
                )
        return cleaned


class CrystalSpecimenRule:
    """R56 Grammar 6: Faceless pedestal-mounted matte bisque-ceramic & satin-frosted optical crystal scale sculpture in midnight-navy void."""

    @staticmethod
    def compose(specimen_kind: str, mount_detail: str, trajectory_or_neural_action: str) -> str:
        raw_kind = str(specimen_kind or "").lower()
        mount = SceneDepictionRule.clean_clause(mount_detail or "a plain unlabelled dark-oak pedestal block without plaques")
        act = BrainDepictionRule.sanitize_brain_signal_text(
            SceneDepictionRule.clean_clause(trajectory_or_neural_action),
            preserve_cyan_blue=True,
        )
        if "hand" in raw_kind:
            subject_desc = "a satin-frosted borosilicate optical crystal hand sculpture"
        else:
            subject_desc = (
                "a faceless smooth ovoid matte-white bisque-ceramic and satin-frosted borosilicate optical crystal dome sculpture "
                "(zero eyes, zero nose, zero mouth, zero ears, zero plaques)"
            )
        return (
            f"Macro tabletop shot against a deep midnight-navy studio void under dramatic chiaroscuro rim lighting: "
            f"{subject_desc} mounted on {mount}. {act[:1].upper() + act[1:]}. "
            f"Shallow tilt-shift miniature depth of field. {BrainDepictionRule.RESTRAINT_LOCK}"
        )


class DioramaCameraRule:
    """R56 single-axis smooth camera move resolver."""

    @staticmethod
    def clause(camera_move: str) -> str:
        key = str(camera_move or "isometric_push_in").strip().lower()
        if key in DIORAMA_CAMERA_DESCRIPTORS:
            return DIORAMA_CAMERA_DESCRIPTORS[key]
        cleaned = SceneDepictionRule.clean_clause(camera_move)
        return cleaned[:1].upper() + cleaned[1:] if cleaned else DIORAMA_CAMERA_DESCRIPTORS["isometric_push_in"]


class DioramaPromptComposer:
    """Composes Schema v6 Google Flow Omni 1.1 motion clip prompts for `neuro_diorama` (R56, R58)."""

    @staticmethod
    def compose_clip_prompt(
        scene_body: str,
        grammar: str,
        camera_move: str = "isometric_push_in",
        aspect: str = FLOW_ASPECT_SHORTS,
        render_sec: int = 8,
    ) -> str:
        # Avoid literal '9:16' digits in prompt text so Veo never engraves '9:16' onto wooden plinths (UI already sets crop_9_16)
        label = "vertical portrait" if aspect == FLOW_ASPECT_SHORTS else "horizontal widescreen"
        cam_key = str(camera_move or "isometric_push_in").strip().lower()
        dyn_lead = f" {DYNAMIC_3D_CAMERA_LEADS[cam_key]}" if cam_key in DYNAMIC_3D_CAMERA_LEADS else ""
        prefix = f"Generate an {int(render_sec)}-second {label} video clip:{dyn_lead}"
        body = SceneDepictionRule.clean_clause(scene_body)
        # Empirically block museum/exhibit words from positive scene body so Veo never engraves brass nameplates
        body = re.sub(r"\bmuseums?\b", "gallery", body, flags=re.IGNORECASE)
        body = re.sub(r"\bexhibits?\b", "showcase", body, flags=re.IGNORECASE)
        if grammar in ("arch_brain_maquette", "frosted_crystal_specimen"):
            body = BrainDepictionRule.sanitize_brain_signal_text(body, preserve_cyan_blue=True)
        cam = DioramaCameraRule.clause(camera_move)
        if grammar == "frosted_crystal_specimen":
            neg = CRYSTAL_SPECIMEN_NEGATIVE_LOCK
        elif grammar == "arch_brain_maquette":
            neg = BRAIN_DARK_VOID_NEGATIVE_LOCK
        else:
            neg = ZERO_FLESH_AND_TEXT_LOCK
        audio_lock = "Audio: subtle physical room ambience only, no speech, no narration, no music."
        return f"{prefix} {body}. {cam}. {neg} {audio_lock}"


def validate_zero_flesh_and_crystal_specimen(
    scene_or_prompt: str,
    grammar: str = "arch_cutaway_diorama",
) -> list[str]:
    """
    R56 validator:
      1. Blocks all human flesh, faces, eyes, full-body mannequins, crowds, animals, and in-scene text tokens.
      2. Allows partial human head bust / hand sculpture ONLY when `grammar == 'frosted_crystal_specimen'`,
         and requires both `satin-frosted ... optical crystal` and a `plinth / pedestal / stand` mount.
    """
    from pipeline.config import DIORAMA_CAMERA_MOVES, DIORAMA_VISUAL_GRAMMARS

    issues: list[str] = []
    g = str(grammar or "").strip()
    if g not in DIORAMA_VISUAL_GRAMMARS:
        issues.append(f"[diorama] unknown grammar '{g}' (must be one of {list(DIORAMA_VISUAL_GRAMMARS)}) (R56)")
    raw = str(scene_or_prompt or "")
    has_ceramic_cast = bool(_CERAMIC_CHARACTER_SCENE_RE.search(raw))
    scrubbed = _NEGATED_SPAN_RE.sub(" ", raw)
    # Remove approved ceramic architectural scale figure phrases before scanning for human/mannequin/body-part leaks
    scrubbed = _ALLOWED_CERAMIC_SCALE_PHRASES_RE.sub(" ", scrubbed)
    if has_ceramic_cast:
        # R56-M: When a featureless matte-white bisque-ceramic miniature figure is explicitly staged,
        # expressive miniature human limb/posture/action motions are allowed (zero uncanny valley),
        # while 'face', 'skin', 'flesh', 'eyes', 'mouth', 'hair', and 'mannequin' remain strictly blocked!
        scrubbed = _CERAMIC_CONTEXT_LIMBS_RE.sub(" ", scrubbed)
    # Remove standard non-scene boilerplate before scanning positive tokens
    scrubbed = re.sub(r"\bclock\s+face\b|\btypeface\b|\bsurface\b|\bsurfaces\b|\bfacade\b|\bfacet\b|\bfacets\b", " ", scrubbed, flags=re.IGNORECASE)
    if g == "frosted_crystal_specimen":
        low = raw.lower()
        if "satin-frosted" not in low or "optical crystal" not in low:
            issues.append(
                "[crystal] frosted_crystal_specimen must specify 'satin-frosted ... optical crystal' material (R56)"
            )
        if not re.search(r"\b(?:plinth|pedestal|stand|mount|mounted)\b", low):
            issues.append(
                "[crystal] frosted_crystal_specimen must be mounted on a plinth / pedestal / stand (no floating body parts) (R56)"
            )
        scrubbed = _ALLOWED_CRYSTAL_PHRASES_RE.sub(" ", scrubbed)
    else:
        body_hits = sorted({m.group(0).lower() for m in _BANNED_BODY_PARTS_OUTSIDE_CRYSTAL_RE.finditer(scrubbed)})
        if body_hits:
            issues.append(
                f"[zero_flesh] grammar '{g}' contains body-part token(s) {body_hits}; use self-actuating automata "
                "or declare grammar='frosted_crystal_specimen' on a plinth (R56)"
            )

    flesh_hits = sorted({m.group(0).lower() for m in _BANNED_FLESH_MANNEQUIN_TEXT_RE.finditer(scrubbed)})
    if flesh_hits:
        issues.append(
            f"[zero_flesh] scene contains banned human/mannequin/animal/signage token(s) {flesh_hits} (R56)"
        )
    if g in ("arch_brain_maquette", "frosted_crystal_specimen"):
        issues.extend(BrainDepictionRule.validate_restrained_signal(raw, "brain_void", allow_cyan_blue=True))
    _ = DIORAMA_CAMERA_MOVES
    return issues


# ==============================================================================
# Schema v7 — Full-Bleed Low-Poly Pastel Architecture Rules (R63)
# ==============================================================================
DIORAMA_V7_CAMERA_DESCRIPTORS: dict[str, str] = {
    "locked_tripod": "Static locked-off tripod shot with crisp internal mechanical and figure motion",
    "pan_left": "Smooth steady orthogonal horizontal camera pan leftward across the scene",
    "pan_right": "Smooth steady orthogonal horizontal camera pan rightward across the scene",
    "tilt_up": "Smooth steady vertical camera tilt upward toward the bright pastel sky",
    "tilt_down": "Smooth steady vertical camera tilt downward across the structure",
    "gentle_push_in": "Restrained smooth straight-in camera glide forward",
    "clean_pullback_reveal": "Restrained smooth straight-back camera pullback reveal",
}

LOWPOLY_V7_SHADER_LEAD = (
    "Untextured flat-shaded matte low-poly 3D animation filling the entire full-bleed vertical viewport "
    "under bright diffused pastel daylight with soft desaturated slate, sage, pale sand, and sky-blue tones"
)

LOWPOLY_V7_OPTICS_TAIL = (
    "Razor-sharp infinite deep focus from foreground to distant horizon with clean geometric polygon facets "
    "and smooth blank unlabelled solid-color matte surfaces."
)

_V7_BANNED_LEGACY_STYLE_RE = re.compile(
    r"\b(?:midnight-navy|midnight\s+navy|studio\s+void|black\s+void|dark-oak|dark\s+oak|museum\s+plinth|"
    r"shallow\s+depth\s+of\s+field|shallow\s+tilt-shift|tilt-shift|bokeh|porcelain\s+mannequin|"
    r"bisque-ceramic|smoked-glass|borosilicate|chiaroscuro)\b",
    flags=re.IGNORECASE,
)

_V7_PINK_ELEPHANT_NEGATION_RE = re.compile(
    r"\bzero\s+(?:eyes?|nose|mouth|ears?|hair|skin|flesh|plaques?|nameplates?|engravings?|text|letters?|numbers?|skirts?|dresses?)\b",
    flags=re.IGNORECASE,
)

_V7_BANNED_IN_SCENE_TEXT_RE = re.compile(
    r"\b(?:signboard|signage|nameplate|plaque|chalkboard|whiteboard|banner|engraved\s+letters|printed\s+text|written\s+words|"
    r"graduated\s+(?:glass|beaker|cylinder|flask)|playing\s+cards?|pocket\s+compass|compass\s+dial|numbered\s+dial|"
    r"(?:ten|twenty|twenty-five|thirty|forty|fifty|\d+)[-\s]+yard[-\s]+lines?)\b",
    flags=re.IGNORECASE,
)

_V7_VERB_TRAP_AND_FACE_RE = re.compile(
    r"\b(?:rockets|rocketing|rocketed|missiles?|torpedoes?|front-facing|staring\s+at\s+camera|human\s+face|facial\s+features|bearded|"
    r"surgical\s+instruments?|scalpels?|forceps|tweezers?|tongs?|prongs?|clamps?|pincers?|scissors?)\b",
    flags=re.IGNORECASE,
)

_V7_MULTI_LIMB_CLOSEUP_TRAP_RE = re.compile(
    r"\b(?:two\s+pairs\s+of\b[^.;,]{0,40}\bsleeves|four\s+(?:steady\s+)?low-poly\s+hands|four\s+hands)\b",
    flags=re.IGNORECASE,
)


class LowPolyWorldRule:
    """R63 Tier 3 Grammar: Full-bleed bright pastel low-poly 3D world with hatted & clothed miniature crew."""

    @staticmethod
    def compose(
        environment: str,
        action: str,
        lighting: str = "soft overcast-bright pastel daylight",
    ) -> str:
        env = SceneDepictionRule.clean_clause(environment)
        act = SceneDepictionRule.clean_clause(action)
        lit = SceneDepictionRule.clean_clause(lighting)
        return (
            f"{LOWPOLY_V7_SHADER_LEAD}: full-bleed wide architectural view of {env} lit by {lit}. "
            f"{act[:1].upper() + act[1:]}. {LOWPOLY_V7_OPTICS_TAIL}"
        )


class LowPolyHandsActionRule:
    """R63 Tier 1 & Tier 2 Grammar: Neck-down or first-person POV matte low-poly forearms & hands operating solid props."""

    @staticmethod
    def compose(
        attire_and_hands: str,
        prop_action: str,
        consequence: str,
        pov: bool = False,
    ) -> str:
        att = SceneDepictionRule.clean_clause(attire_and_hands)
        act = SceneDepictionRule.clean_clause(prop_action)
        con = SceneDepictionRule.clean_clause(consequence)
        tier_lead = (
            "first-person POV looking down at untextured matte low-poly forearms and geometric hands"
            if pov
            else "tight neck-down work close-up framed strictly below the collar showing untextured matte low-poly forearms and geometric hands"
        )
        return (
            f"{LOWPOLY_V7_SHADER_LEAD}: {tier_lead} ({att}). "
            f"{act[:1].upper() + act[1:]}, while {con}. {LOWPOLY_V7_OPTICS_TAIL}"
        )


class LowPolyCutawaySectionRule:
    """R63 Cutaway Grammar (<= 15% of cuts): Full-bleed clean architectural geological/structural cross-section."""

    @staticmethod
    def compose(structure: str, internal_mechanism: str) -> str:
        st = SceneDepictionRule.clean_clause(structure)
        mech = SceneDepictionRule.clean_clause(internal_mechanism)
        return (
            f"{LOWPOLY_V7_SHADER_LEAD}: full-bleed architectural cross-section diagram of {st} spanning edge-to-edge. "
            f"{mech[:1].upper() + mech[1:]}. {LOWPOLY_V7_OPTICS_TAIL}"
        )


class LowPolyLiteralAnalogyRule:
    """R63 Literal 1:1 Everyday Physical Analogy Grammar in the exact same bright pastel low-poly 3D world."""

    @staticmethod
    def compose(analogy_world: str, comparison_action: str) -> str:
        aw = SceneDepictionRule.clean_clause(analogy_world)
        act = SceneDepictionRule.clean_clause(comparison_action)
        return (
            f"{LOWPOLY_V7_SHADER_LEAD}: full-bleed physical scale comparison scene in {aw}. "
            f"{act[:1].upper() + act[1:]}. {LOWPOLY_V7_OPTICS_TAIL}"
        )


class MatteArchitecturalBrainRule:
    """R63 Unified Bright-Studio Matte Low-Poly 3D Architectural Brain Model (Cortical vs Sagittal Cutaway)."""

    VALID_BRAIN_MODES: tuple[str, ...] = DIORAMA_V7_BRAIN_RENDER_MODES
    _MODE_ALIASES: dict[str, str] = {
        "auto": "matte_pastel_cortical_model",
        "cortical": "matte_pastel_cortical_model",
        "cortical_model": "matte_pastel_cortical_model",
        "sagittal": "matte_pastel_sagittal_cutaway",
        "cutaway": "matte_pastel_sagittal_cutaway",
        "sagittal_cutaway": "matte_pastel_sagittal_cutaway",
        "matte_pastel_fiber_tract": "matte_pastel_sagittal_cutaway",
    }

    @classmethod
    def resolve_brain_mode(cls, brain_mode: str | None) -> str:
        raw = str(brain_mode or DIORAMA_V7_BRAIN_RENDER_MODES[0]).strip().lower()
        resolved = cls._MODE_ALIASES.get(raw, raw)
        if resolved not in DIORAMA_V7_BRAIN_RENDER_MODES:
            raise ValueError(
                f"Invalid v7 brain_mode {brain_mode!r}; must be one of {list(DIORAMA_V7_BRAIN_RENDER_MODES)}"
            )
        return resolved

    @classmethod
    def compose(cls, brain_scene: str, brain_mode: str = "matte_pastel_cortical_model") -> str:
        sc = SceneDepictionRule.clean_clause(brain_scene)
        sc = re.sub(r"\b(?:light-|pale-)?birch\b", "pale-wood", sc, flags=re.IGNORECASE)
        mode_norm = cls.resolve_brain_mode(brain_mode)
        if mode_norm == "matte_pastel_sagittal_cutaway":
            lead = (
                "sunlit pale-sand architectural studio room filling the full frame: strict flat lateral side-profile view "
                "of a single half-brain hemisphere matte warm-ivory low-poly 3D mid-sagittal cross-section model resting on "
                "a clean pale-wood stand exposing its flat cut-open medial interior face and corpus callosum arch"
            )
        else:
            lead = (
                "sunlit pale-sand architectural studio room filling the full frame: three-quarter lateral side view of a "
                "whole untextured flat-shaded matte warm-ivory low-poly 3D anatomical brain model resting on a clean "
                "pale-wood stand with crisp geometric lobes, folded cerebellum, and brainstem"
            )
        return f"{LOWPOLY_V7_SHADER_LEAD}: {lead}. {sc[:1].upper() + sc[1:]}. {LOWPOLY_V7_OPTICS_TAIL}"


class DioramaV7PromptComposer:
    """Composes Schema v7 positive-only low-poly prompts with a single camera clause (zero Pink-Elephant lists)."""

    @staticmethod
    def compose_clip_prompt(
        scene_body: str,
        grammar: str,
        camera_move: str = "locked_tripod",
        aspect: str = FLOW_ASPECT_SHORTS,
        render_sec: int = 8,
    ) -> str:
        from pipeline.config import DIORAMA_V7_VISUAL_GRAMMARS

        _ = grammar if grammar in DIORAMA_V7_VISUAL_GRAMMARS else "lowpoly_fullbleed_world"
        label = "vertical portrait" if aspect == FLOW_ASPECT_SHORTS else "horizontal widescreen"
        cam_key = str(camera_move or "locked_tripod").strip().lower()
        cam_clause = DIORAMA_V7_CAMERA_DESCRIPTORS.get(cam_key, DIORAMA_V7_CAMERA_DESCRIPTORS["locked_tripod"]).rstrip(".")
        body = SceneDepictionRule.clean_clause(scene_body)
        body = re.sub(r"\bmuseums?\b", "studio", body, flags=re.IGNORECASE)
        body = re.sub(r"\bexhibits?\b", "display", body, flags=re.IGNORECASE)
        body = body.rstrip(".")
        audio_clause = "Subtle crisp physical foley and quiet daylight ambience only, silent voice track."
        return f"Generate an {int(render_sec)}-second {label} video clip. {cam_clause}. {body}. {audio_clause}"


def validate_lowpoly_v7_scene(
    scene_or_prompt: str,
    grammar: str = "lowpoly_fullbleed_world",
    camera_move: str = "",
) -> list[str]:
    """R63 Schema v7 scene & prompt validator: enforces low-poly deep-focus world and blocks dark-void/Pink-Elephant/Escher/tilt-onto-face tokens."""
    from pipeline.config import DIORAMA_V7_VISUAL_GRAMMARS

    issues: list[str] = []
    g = str(grammar or "").strip()
    cam_norm = str(camera_move or "").strip().lower()
    if g not in DIORAMA_V7_VISUAL_GRAMMARS:
        issues.append(f"[lowpoly_v7] invalid grammar '{g}' (must be in {list(DIORAMA_V7_VISUAL_GRAMMARS)}) (R63)")
    raw = str(scene_or_prompt or "")
    low = raw.lower()
    if "low-poly" not in low and "low poly" not in low:
        issues.append("[lowpoly_v7] scene missing 'low-poly' matte 3D shader anchor (R63)")
    if "deep focus" not in low:
        issues.append("[lowpoly_v7] scene missing 'deep focus' infinite optics lock (R63)")
    legacy_hits = sorted({m.group(0).lower() for m in _V7_BANNED_LEGACY_STYLE_RE.finditer(raw)})
    if legacy_hits:
        issues.append(
            f"[lowpoly_v7] scene contains banned legacy dark-void/plinth/bokeh token(s) {legacy_hits} (R63)"
        )
    neg_hits = sorted({m.group(0).lower() for m in _V7_PINK_ELEPHANT_NEGATION_RE.finditer(raw)})
    if neg_hits:
        issues.append(
            f"[lowpoly_v7] scene contains banned T5 Pink-Elephant negative noun phrase(s) {neg_hits}; use positive phrasing only (R63)"
        )
    txt_hits = sorted({m.group(0).lower() for m in _V7_BANNED_IN_SCENE_TEXT_RE.finditer(raw)})
    if txt_hits:
        issues.append(f"[lowpoly_v7] scene contains banned in-scene signage/text-trigger token(s) {txt_hits} (R63)")
    trap_hits = sorted({m.group(0).lower() for m in _V7_VERB_TRAP_AND_FACE_RE.finditer(raw)})
    if trap_hits:
        issues.append(f"[lowpoly_v7] scene contains banned projectile/prong verb-trap or front-facing face token(s) {trap_hits} (R63)")
    if g in ("lowpoly_hands_closeup", "lowpoly_pov_hands"):
        multi_hits = sorted({m.group(0).lower() for m in _V7_MULTI_LIMB_CLOSEUP_TRAP_RE.finditer(raw)})
        if multi_hits:
            issues.append(
                f"[lowpoly_v7] close-up grammar '{g}' contains multi-actor disembodied-limb trigger(s) {multi_hits}; stage a single pair of hands or use 'lowpoly_fullbleed_world' (R63)"
            )
    if g == "lowpoly_hands_closeup":
        if "tight neck-down work close-up" in low and re.search(r"\bfrom\s+(?:the\s+)?bottom\s+frame\b", low):
            issues.append(
                "[lowpoly_v7] neck-down 'lowpoly_hands_closeup' cannot combine with 'from bottom frame' (causes Escher dual-edge torso+arms); use 'lowpoly_pov_hands' instead (R63)"
            )
        if cam_norm == "tilt_up" or DIORAMA_V7_CAMERA_DESCRIPTORS["tilt_up"].lower() in low:
            issues.append(
                "[lowpoly_v7] neck-down 'lowpoly_hands_closeup' cannot combine with 'tilt_up' camera (tilts above collar onto head/face); use 'locked_tripod', 'pan_left', 'pan_right', or 'tilt_down' (R63)"
            )
    return issues


# ==============================================================================
# Schema v7 — Porcelain Cinematic World & Contained Living 4-Color 3D Brain (R66)
# ==============================================================================
PORCELAIN_V7_CAMERA_DESCRIPTORS: dict[str, str] = {
    "locked_tripod": "Static locked-off tripod shot with crisp internal mechanical and figure motion",
    "pan_left": "Smooth steady orthogonal horizontal camera pan leftward across the scene",
    "pan_right": "Smooth steady orthogonal horizontal camera pan rightward across the scene",
    "tilt_up": "Smooth steady vertical camera tilt upward across the bright sunlit scene",
    "tilt_down": "Smooth steady vertical camera tilt downward across the structure",
    "gentle_push_in": "Restrained smooth straight-in camera glide forward",
    "clean_pullback_reveal": "Restrained smooth straight-back camera pullback reveal",
}

PORCELAIN_V7_WORLD_LEAD = (
    "Photorealistic bright high-key documentary cinema filling the full-bleed vertical frame "
    "in soft studio daylight and rim light"
)

PORCELAIN_V7_OPTICS_TAIL = (
    "Crisp cinema prime lens clarity on tactile porcelain, metal, glass, and wood with unmarked walls."
)

PORCELAIN_V7_BRAIN_OPTICS_TAIL = (
    "Crisp cinema prime lens clarity with sharp anatomical relief, enclosed translucent vessel walls, "
    "and a clean unmarked bright studio backdrop."
)

_PORCELAIN_V7_GRAMMAR_SLOT_MAP: dict[str, str] = {
    "porcelain_fullbleed_world": "porcelain_fullbleed_world",
    "porcelain_hands_closeup": "porcelain_hands_closeup",
    "porcelain_pov_hands": "porcelain_pov_hands",
    "porcelain_cutaway_section": "porcelain_cutaway_section",
    "porcelain_literal_analogy": "porcelain_literal_analogy",
    "porcelain_living_brain": "porcelain_living_brain",
    "fullbleed_world": "porcelain_fullbleed_world",
    "hands_closeup": "porcelain_hands_closeup",
    "pov_hands": "porcelain_pov_hands",
    "cutaway_section": "porcelain_cutaway_section",
    "literal_analogy": "porcelain_literal_analogy",
    "living_brain": "porcelain_living_brain",
    "matte_brain": "porcelain_living_brain",
    "lowpoly_fullbleed_world": "porcelain_fullbleed_world",
    "lowpoly_hands_closeup": "porcelain_hands_closeup",
    "lowpoly_pov_hands": "porcelain_pov_hands",
    "lowpoly_cutaway_section": "porcelain_cutaway_section",
    "lowpoly_literal_analogy": "porcelain_literal_analogy",
    "lowpoly_matte_brain": "porcelain_living_brain",
}

_PORCELAIN_V7_BANNED_STYLE_RE = re.compile(
    r"\b(?:low-poly|low\s+poly|flat-shaded|flat\s+shaded|polygon\s+facets?|"
    r"faceted\s+(?:geometric|matte|pastel|clay|head|jaw|hands?|forearms?|figures?)|lower\s+geometric\s+jaw|"
    r"pastel\s+clay|midnight-navy|midnight\s+navy|studio\s+void|black\s+void|dark-oak|dark\s+oak|"
    r"museum\s+plinth|bisque-ceramic|chiaroscuro)\b",
    flags=re.IGNORECASE,
)

_PORCELAIN_V7_BANNED_GLOBAL_TOXIC_RE = re.compile(
    r"\b(?:bioluminescent\s+green|bioluminescent|fluorescent\s+green|fluorescent|neon\s+green|neon\s+blue|"
    r"radioactive|slime|ooze|oozing|spores?|confetti|fireworks?|drifting\s+dust|floating\s+dots)\b",
    flags=re.IGNORECASE,
)

_PORCELAIN_V7_BRAIN_UNCONTAINED_SPILL_RE = re.compile(
    r"\b(?:mist|fog|haze|smoke|smoky|particles?|sparks?|sparking|splatter(?:s|ing|ed)?|"
    r"scatter(?:s|ing|ed)?|spray(?:s|ing|ed)?|splashing)\b",
    flags=re.IGNORECASE,
)

_PORCELAIN_V7_PINK_ELEPHANT_RE = re.compile(
    r"\b(?:zero|no)\s+(?:eyes?|nose|mouth|ears?|faces?|hair|skin|flesh|blood|gore|plaques?|nameplates?|"
    r"engravings?|text|letters?|numbers?|skirts?|dresses?|particles?|mist|sparks?|slime|fog)\b",
    flags=re.IGNORECASE,
)

_PORCELAIN_V7_BANNED_IN_SCENE_TEXT_RE = re.compile(
    r"\b(?:signboard|signage|nameplate|plaque|chalkboard|blackboard|whiteboard|banner|engraved\s+letters|"
    r"printed\s+text|written\s+words|newspapers?|headlines?|textbooks?|ledgers?|labelled|labeled|inscribed|"
    r"graduated\s+(?:glass|beaker|cylinder|flask)|playing\s+cards?|pocket\s+compass|compass\s+dial|numbered\s+dial|"
    r"(?:ten|twenty|twenty-five|thirty|forty|fifty|\d+)[-\s]+yard[-\s]+lines?)\b",
    flags=re.IGNORECASE,
)

_PORCELAIN_V7_MULTI_LIMB_CLOSEUP_TRAP_RE = re.compile(
    r"\b(?:two\s+pairs\s+of\b[^.;,]{0,40}\b(?:sleeves|cuffs)|four\s+(?:smooth\s+|porcelain\s+|matte-white\s+)*hands)\b",
    flags=re.IGNORECASE,
)


def normalize_porcelain_v7_grammar(grammar: str | None) -> str:
    """Maps generic or lowpoly Schema v7 grammar slot names onto canonical `porcelain_*` grammars."""
    raw = str(grammar or "").strip()
    if not raw:
        return "porcelain_fullbleed_world"
    return _PORCELAIN_V7_GRAMMAR_SLOT_MAP.get(raw.lower(), raw)


_PORCELAIN_V7_ACTOR_NOUN_RE = re.compile(
    r"\b(?:figures?(?!\s*-?\s*(?:eight|8|ground))|crew|crewmates?|drivers?|physicians?|doctors?|surgeons?|"
    r"clinicians?|therapists?|psychologists?|psychiatrists?|neurologists?|neuropsychologists?|nurses?|orderlies|"
    r"researchers?|scientists?|examiners?|experimenters?|investigators?|professors?|teachers?|instructors?|"
    r"scholars?|students?|pupils?|patients?|subjects?|participants?|volunteers?|confederates?|bystanders?|"
    r"observers?|witnesses?|spectators?|commuters?|pedestrians?|passersby|shoppers?|leaders?|workers?|"
    r"technicians?|laborers?|assistants?|attendants?|clerks?|archivists?|librarians?|guards?|prisoners?|"
    r"inmates?|officers?|detectives?|pilots?|astronauts?|soldiers?|veterans?|sailors?|divers?|monks?|"
    r"meditators?|jugglers?|cyclists?|runners?|swimmers?|athletes?|players?|musicians?|pianists?|violinists?|"
    r"drummers?|(?:orchestra|choir|train)\s+conductors?|baristas?|chefs?|waiters?|mannequins?|person|people|"
    r"men|women|man|woman|boys?|girls?|child|children|infants?|toddlers?|babies|baby|mothers?|fathers?|"
    r"parents?|husbands?|wives|wife|couples?|twins?|brothers?|sisters?)\b",
    flags=re.IGNORECASE,
)


class PorcelainWorldRule:
    """R66 Tier 3 Grammar: Photorealistic bright high-key world with clothed matte-white porcelain figures & frosted-glass craniums."""

    @staticmethod
    def compose(
        environment: str,
        action: str,
        lighting: str = "soft bright studio daylight with crisp rim light",
    ) -> str:
        env = SceneDepictionRule.clean_clause(environment)
        act = SceneDepictionRule.clean_clause(action)
        lit = SceneDepictionRule.clean_clause(lighting)
        combined = f"{env} {act}"
        low_combined = combined.lower()
        has_actor = bool(_PORCELAIN_V7_ACTOR_NOUN_RE.search(combined))
        has_head_spec = any(
            tok in low_combined
            for tok in ("cranium", "oval head", "porcelain head", "featureless")
        )
        if not has_actor or ("porcelain" in low_combined and has_head_spec):
            actor_clause = ""
        elif "porcelain" in low_combined:
            actor_clause = ", each figure topped by a smooth featureless white head with a translucent frosted-glass cranium"
        else:
            actor_clause = ", staged as clothed matte-white porcelain figures with translucent frosted-glass craniums"
        return (
            f"{PORCELAIN_V7_WORLD_LEAD}: full-bleed high-key view of {env} in {lit}. "
            f"{act[:1].upper() + act[1:]}{actor_clause}. {PORCELAIN_V7_OPTICS_TAIL}"
        )


class PorcelainHandsActionRule:
    """R66 Tier 1 & Tier 2 Grammar: Neck-down or first-person POV matte-white ball-jointed porcelain forearms & hands in tailored cuffs."""

    @staticmethod
    def compose(
        attire_and_hands: str,
        prop_action: str,
        consequence: str,
        pov: bool = False,
    ) -> str:
        att = SceneDepictionRule.clean_clause(attire_and_hands)
        act = SceneDepictionRule.clean_clause(prop_action)
        con = SceneDepictionRule.clean_clause(consequence)
        tier_lead = (
            "first-person POV looking down at smooth matte-white ball-jointed porcelain forearms and articulated hands in tailored cuffs"
            if pov
            else "tight neck-down work close-up framed strictly below the collar showing smooth matte-white ball-jointed porcelain forearms and articulated hands in tailored cuffs"
        )
        return (
            f"{PORCELAIN_V7_WORLD_LEAD}: {tier_lead} ({att}). "
            f"{act[:1].upper() + act[1:]}, while {con}. {PORCELAIN_V7_OPTICS_TAIL}"
        )


class PorcelainCutawaySectionRule:
    """R66 Cutaway Grammar (<= 15% of cuts): Photorealistic high-key architectural/experimental cross-section."""

    @staticmethod
    def compose(structure: str, internal_mechanism: str) -> str:
        st = SceneDepictionRule.clean_clause(structure)
        mech = SceneDepictionRule.clean_clause(internal_mechanism)
        return (
            f"{PORCELAIN_V7_WORLD_LEAD}: clean photorealistic high-key architectural and mechanical cross-section of {st} spanning edge-to-edge. "
            f"{mech[:1].upper() + mech[1:]}. {PORCELAIN_V7_OPTICS_TAIL}"
        )


class PorcelainLiteralAnalogyRule:
    """R66 Literal 1:1 Everyday Physical Analogy Grammar in photorealistic high-key porcelain studio cinema."""

    @staticmethod
    def compose(analogy_world: str, comparison_action: str) -> str:
        aw = SceneDepictionRule.clean_clause(analogy_world)
        act = SceneDepictionRule.clean_clause(comparison_action)
        return (
            f"{PORCELAIN_V7_WORLD_LEAD}: full-bleed high-key physical scale comparison scene in {aw} with crisp tactile studio props. "
            f"{act[:1].upper() + act[1:]}. {PORCELAIN_V7_OPTICS_TAIL}"
        )


class ContainedLiving3DBrainRule:
    """R66 Ultra-Detailed Contained Living 4-Color 3D Brain (`clear cyan-blue`, `deep crimson-red`, `warm amber-gold`, `luminous pearl-aqua` / `champagne-white`)."""

    VALID_BRAIN_MODES: tuple[str, ...] = PORCELAIN_V7_BRAIN_RENDER_MODES
    _MODE_ALIASES: dict[str, str] = {
        "auto": "cortical_vascular_whole",
        "cortical": "cortical_vascular_whole",
        "whole": "cortical_vascular_whole",
        "vascular": "cortical_vascular_whole",
        "cortical_model": "cortical_vascular_whole",
        "matte_pastel_cortical_model": "cortical_vascular_whole",
        "cutaway": "sagittal_coronal_cutaway",
        "sagittal": "sagittal_coronal_cutaway",
        "coronal": "sagittal_coronal_cutaway",
        "sagittal_cutaway": "sagittal_coronal_cutaway",
        "matte_pastel_sagittal_cutaway": "sagittal_coronal_cutaway",
        "matte_pastel_fiber_tract": "sagittal_coronal_cutaway",
        "xray": "frosted_glass_subcortical_xray",
        "x_ray": "frosted_glass_subcortical_xray",
        "frosted_glass": "frosted_glass_subcortical_xray",
        "subcortical": "frosted_glass_subcortical_xray",
        "subcortical_xray": "frosted_glass_subcortical_xray",
        "micro": "bounded_micro_channel",
        "micro_channel": "bounded_micro_channel",
        "channel": "bounded_micro_channel",
        "vessel": "bounded_micro_channel",
        "tract_macro": "bounded_micro_channel",
    }

    @classmethod
    def resolve_brain_mode(cls, brain_mode: str | None) -> str:
        raw = str(brain_mode or PORCELAIN_V7_BRAIN_RENDER_MODES[0]).strip().lower()
        resolved = cls._MODE_ALIASES.get(raw, raw)
        if resolved not in PORCELAIN_V7_BRAIN_RENDER_MODES:
            raise ValueError(
                f"Invalid porcelain v7 brain_mode {brain_mode!r}; must be one of {list(PORCELAIN_V7_BRAIN_RENDER_MODES)}"
            )
        return resolved

    @classmethod
    def compose(
        cls,
        brain_scene: str | None = None,
        brain_mode: str = "cortical_vascular_whole",
        *,
        brain_region: str | None = None,
        active_hub: str | None = None,
        lesion_or_deficit: str | None = None,
        fluid_or_signal_flow: str | None = None,
    ) -> str:
        mode_norm = cls.resolve_brain_mode(brain_mode)
        reg = SceneDepictionRule.clean_clause(brain_region or "")
        reg_focus = f" focusing on the {reg}" if reg else ""
        if brain_scene and str(brain_scene).strip():
            sc = SceneDepictionRule.clean_clause(str(brain_scene))
        else:
            clauses = [
                SceneDepictionRule.clean_clause(part)
                for part in (active_hub, lesion_or_deficit, fluid_or_signal_flow)
                if part and str(part).strip()
            ]
            sc = (
                "; ".join(clauses)
                if clauses
                else "clear cyan-blue cortical channels open while luminous pearl-aqua fluid clears deep crimson-red clusters toward warm amber-gold recovery pathways"
            )
        if mode_norm == "sagittal_coronal_cutaway":
            lead = (
                f"bright white studio gallery: sagittal-coronal cross-section of a matte-white 3D brain{reg_focus} "
                "on an acrylic pedestal with living impulses gliding strictly inside enclosed white-matter sheaths"
            )
        elif mode_norm == "frosted_glass_subcortical_xray":
            lead = (
                f"bright white studio gallery: whole 3D brain with a translucent frosted-glass cortex{reg_focus} "
                "on an acrylic pedestal revealing deep nuclei strictly bounded inside the closed brain silhouette"
            )
        elif mode_norm == "bounded_micro_channel":
            lead = (
                f"bright white studio macro cutaway: folded matte-white cortical tissue{reg_focus} "
                "with enclosed translucent vessel walls where laminar fluid and crisp light travel strictly inside tube walls"
            )
        else:
            lead = (
                f"bright white studio gallery: three-quarter matte-white 3D brain{reg_focus} on an acrylic pedestal "
                "with fine gyri and enclosed translucent perivascular tubes flowing strictly inside anatomical walls"
            )
        return f"{PORCELAIN_V7_WORLD_LEAD}: {lead}. {sc[:1].upper() + sc[1:]}. {PORCELAIN_V7_BRAIN_OPTICS_TAIL}"


def normalize_porcelain_v7_brain_mode(
    brain_mode: str | None = None,
    *,
    render_mode: str | None = None,
    scene_text: str | None = None,
) -> str:
    """
    Normalizes a `porcelain_living_brain` render mode (`brain_mode`, fallback `render_mode` or `scene_text`)
    through `ContainedLiving3DBrainRule._MODE_ALIASES` without raising on custom/unknown strings.
    """
    for cand in (brain_mode, render_mode):
        raw = str(cand or "").strip().lower()
        if raw:
            return ContainedLiving3DBrainRule._MODE_ALIASES.get(raw, raw)
    sc_low = str(scene_text or "").strip().lower()
    if sc_low:
        if (
            "sagittal-coronal cross-section" in sc_low
            or "sagittal cross-section" in sc_low
            or "coronal cross-section" in sc_low
        ):
            return "sagittal_coronal_cutaway"
        if "translucent frosted-glass cortex" in sc_low:
            return "frosted_glass_subcortical_xray"
        if "studio macro cutaway" in sc_low or "folded matte-white cortical tissue" in sc_low:
            return "bounded_micro_channel"
    return PORCELAIN_V7_BRAIN_RENDER_MODES[0]



class PorcelainV7PromptComposer:
    """Composes Schema v7 `porcelain_cinematic_v7` positive-only high-key porcelain & living-brain prompts (R66)."""

    @staticmethod
    def compose_clip_prompt(
        scene_body: str,
        grammar: str = "porcelain_fullbleed_world",
        camera_move: str = "locked_tripod",
        aspect: str = FLOW_ASPECT_SHORTS,
        render_sec: int = 8,
    ) -> str:
        _ = grammar if grammar in PORCELAIN_V7_VISUAL_GRAMMARS else "porcelain_fullbleed_world"
        label = "vertical portrait" if aspect == FLOW_ASPECT_SHORTS else "horizontal widescreen"
        cam_key = str(camera_move or "locked_tripod").strip().lower()
        cam_clause = PORCELAIN_V7_CAMERA_DESCRIPTORS.get(cam_key, PORCELAIN_V7_CAMERA_DESCRIPTORS["locked_tripod"]).rstrip(".")
        body = SceneDepictionRule.clean_clause(scene_body)
        body = re.sub(r"\bmuseums?\b", "studio", body, flags=re.IGNORECASE)
        body = re.sub(r"\bexhibits?\b", "display", body, flags=re.IGNORECASE)
        body = body.rstrip(".")
        audio_clause = "Subtle crisp physical foley and quiet studio daylight ambience only, silent voice track."
        return f"Generate an {int(render_sec)}-second {label} video clip. {cam_clause}. {body}. {audio_clause}"


def validate_porcelain_v7_scene(
    scene_or_prompt: str,
    grammar: str = "porcelain_fullbleed_world",
    camera_move: str = "",
) -> list[str]:
    """R66 Schema v7 `porcelain_cinematic_v7` scene & prompt validator: enforces high-key porcelain/glass cast and contained 4-color 3D brain while blocking fluorescent green spill, particles, mist, low-poly, and Escher/face traps."""
    issues: list[str] = []
    g = str(grammar or "").strip()
    cam_norm = str(camera_move or "").strip().lower()
    if g not in PORCELAIN_V7_VISUAL_GRAMMARS:
        issues.append(f"[porcelain_v7] invalid grammar '{g}' (must be in {list(PORCELAIN_V7_VISUAL_GRAMMARS)}) (R66)")
    raw = str(scene_or_prompt or "")
    low = raw.lower()
    raw_body = raw
    for boiler_str in (
        PORCELAIN_V7_OPTICS_TAIL,
        PORCELAIN_V7_BRAIN_OPTICS_TAIL,
        "Single focal subject centered in crisp silhouette",
        *PORCELAIN_V7_CAMERA_DESCRIPTORS.values(),
        *DIORAMA_V7_CAMERA_DESCRIPTORS.values(),
    ):
        raw_body = raw_body.replace(boiler_str, " ").replace(boiler_str.rstrip("."), " ")
    low_body = raw_body.lower()
    if not any(tok in low for tok in ("high-key", "bright white", "bright studio")):
        issues.append("[porcelain_v7] scene missing bright high-key documentary/studio lighting anchor (R66)")
    if g == "porcelain_living_brain":
        if "3d brain" not in low and "cortical tissue" not in low:
            issues.append("[porcelain_v7] living brain scene missing '3D brain' or 'cortical tissue' anatomical anchor (R66)")
        if not any(tok in low for tok in ("enclosed", "strictly bounded", "strictly inside", "translucent")):
            issues.append("[porcelain_v7] living brain scene missing vessel/sheath containment anchor ('enclosed' / 'strictly inside') (R66)")
    elif g in ("porcelain_hands_closeup", "porcelain_pov_hands"):
        if "porcelain" not in low_body:
            issues.append(f"[porcelain_v7] '{g}' scene missing 'porcelain' forearms/hands material anchor (R66)")
    elif g == "porcelain_fullbleed_world":
        if _PORCELAIN_V7_ACTOR_NOUN_RE.search(raw_body):
            if "porcelain" not in low_body:
                issues.append(
                    "[porcelain_v7] 'porcelain_fullbleed_world' scene stages human actor(s) without 'porcelain' cast figure anchor (R66)"
                )
        elif "porcelain" not in low:
            issues.append("[porcelain_v7] 'porcelain_fullbleed_world' scene missing 'porcelain' material anchor (R66)")
    style_hits = sorted({m.group(0).lower() for m in _PORCELAIN_V7_BANNED_STYLE_RE.finditer(raw)})
    if style_hits:
        issues.append(
            f"[porcelain_v7] scene contains banned low-poly/flat-shaded/dark-void token(s) {style_hits} (R66)"
        )
    toxic_hits = {m.group(0).lower() for m in _PORCELAIN_V7_BANNED_GLOBAL_TOXIC_RE.finditer(raw)}
    if g == "porcelain_living_brain":
        toxic_hits |= {m.group(0).lower() for m in _PORCELAIN_V7_BRAIN_UNCONTAINED_SPILL_RE.finditer(raw)}
    if toxic_hits:
        issues.append(
            f"[porcelain_v7] scene contains banned uncontained fluorescent/particle/mist/slime token(s) {sorted(toxic_hits)} (R66)"
        )
    neg_hits = sorted({m.group(0).lower() for m in _PORCELAIN_V7_PINK_ELEPHANT_RE.finditer(raw)})
    if neg_hits:
        issues.append(
            f"[porcelain_v7] scene contains banned T5 Pink-Elephant negative noun phrase(s) {neg_hits}; use positive phrasing only (R66)"
        )
    txt_hits = sorted({m.group(0).lower() for m in _PORCELAIN_V7_BANNED_IN_SCENE_TEXT_RE.finditer(raw)})
    if txt_hits:
        issues.append(f"[porcelain_v7] scene contains banned in-scene signage/text-trigger token(s) {txt_hits} (R66)")
    trap_hits = sorted({m.group(0).lower() for m in _V7_VERB_TRAP_AND_FACE_RE.finditer(raw)})
    if trap_hits:
        issues.append(f"[porcelain_v7] scene contains banned projectile/prong verb-trap or front-facing face token(s) {trap_hits} (R66)")
    if g in ("porcelain_hands_closeup", "porcelain_pov_hands"):
        multi_hits = sorted({m.group(0).lower() for m in _PORCELAIN_V7_MULTI_LIMB_CLOSEUP_TRAP_RE.finditer(raw)})
        if multi_hits:
            issues.append(
                f"[porcelain_v7] close-up grammar '{g}' contains multi-actor disembodied-limb trigger(s) {multi_hits}; stage a single pair of hands or use 'porcelain_fullbleed_world' (R66)"
            )
    if g == "porcelain_hands_closeup":
        if re.search(r"\bfrom\s+(?:the\s+)?bottom\s+frame\b", low):
            issues.append(
                "[porcelain_v7] neck-down 'porcelain_hands_closeup' cannot combine with 'from bottom frame' (causes Escher dual-edge torso+arms); use 'porcelain_pov_hands' instead (R66)"
            )
        if cam_norm == "tilt_up" or "camera tilt upward" in low:
            issues.append(
                "[porcelain_v7] neck-down 'porcelain_hands_closeup' cannot combine with 'tilt_up' camera (tilts above collar onto head/face); use 'locked_tripod', 'pan_left', 'pan_right', or 'tilt_down' (R66)"
            )
    return issues


__all__ = [
    "ArchitecturalBrainMaquetteRule",
    "BANNED_BRAIN_PARTICLE_TOKENS",
    "BRAIN_DARK_VOID_NEGATIVE_LOCK",
    "BrainDepictionRule",
    "CRYSTAL_SPECIMEN_NEGATIVE_LOCK",
    "CameraDepictionRule",
    "CastDepictionRule",
    "ContainedLiving3DBrainRule",
    "CrystalSpecimenRule",
    "DIORAMA_CAMERA_DESCRIPTORS",
    "DIORAMA_V7_CAMERA_DESCRIPTORS",
    "DioramaCameraRule",
    "DioramaCutawayRule",
    "DioramaPromptComposer",
    "DioramaV7PromptComposer",
    "KineticTracePropRule",
    "LOWPOLY_V7_OPTICS_TAIL",
    "LOWPOLY_V7_SHADER_LEAD",
    "LiteralAnalogyCutawayRule",
    "LowPolyCutawaySectionRule",
    "LowPolyHandsActionRule",
    "LowPolyLiteralAnalogyRule",
    "LowPolyWorldRule",
    "MatteArchitecturalBrainRule",
    "PORCELAIN_V7_BRAIN_OPTICS_TAIL",
    "PORCELAIN_V7_CAMERA_DESCRIPTORS",
    "PORCELAIN_V7_OPTICS_TAIL",
    "PORCELAIN_V7_WORLD_LEAD",
    "PorcelainCutawaySectionRule",
    "PorcelainHandsActionRule",
    "PorcelainLiteralAnalogyRule",
    "PorcelainV7PromptComposer",
    "PorcelainWorldRule",
    "PromptComposer",
    "ReferenceDepictionRule",
    "SceneDepictionRule",
    "SensorMotifRule",
    "TactileTokenGridRule",
    "ZERO_FLESH_AND_TEXT_LOCK",
    "normalize_porcelain_v7_grammar",
    "validate_lowpoly_v7_scene",
    "validate_porcelain_v7_scene",
    "validate_zero_flesh_and_crystal_specimen",
]


