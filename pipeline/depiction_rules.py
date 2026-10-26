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
    FLOW_ASPECT_LABELS,
    FLOW_ASPECT_SHORTS,
    FLOW_MOTION_STYLE_V5,
    FLOW_VOICE_PROMPT_DESCRIPTOR_V5,
    GEMINI_APP_MAX_RENDER_SEC,
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
    def sanitize_brain_signal_text(text: str) -> str:
        """Rewrites any particle/spark/scattering wording in brain scenes into calm internal tract conduction (R53)."""
        out = str(text or "")
        for pat, repl in _BRAIN_SIGNAL_REWRITES:
            out = pat.sub(repl, out)
        out = re.sub(r"\s{2,}", " ", out).strip()
        out = re.sub(r"\s+([.,;:])", r"\1", out)
        return out

    @classmethod
    def format_brain_scene(cls, raw_scene: str, append_restraint_lock: bool = True) -> str:
        cleaned = cls.sanitize_brain_signal_text(raw_scene)
        if append_restraint_lock and "subsurface luminance stays smoothly contained" not in cleaned.lower():
            if not cleaned.endswith("."):
                cleaned += "."
            cleaned = f"{cleaned} {cls.RESTRAINT_LOCK}"
        return cleaned

    @staticmethod
    def validate_restrained_signal(scene_text: str, setting: str) -> list[str]:
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


__all__ = [
    "BANNED_BRAIN_PARTICLE_TOKENS",
    "BrainDepictionRule",
    "CameraDepictionRule",
    "CastDepictionRule",
    "PromptComposer",
    "ReferenceDepictionRule",
    "SceneDepictionRule",
]
