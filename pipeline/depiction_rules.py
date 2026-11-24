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
    EXPRESSIVE_V8_DRONE_CAMERA_MOVES,
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


SELECTIVE_COLOR_BACKDROP_CLAUSE = (
    "warm muted low-saturation architectural backdrop isolating the vivid full-color hero prop"
)

ACT_LIGHTING_ARC_HINTS: dict[str, str] = {
    "act_1": "high-key alert daylight illuminating foreground action",
    "act_2": "cool clinical lab contrast lighting",
    "act_3_5": "crisp sculptural studio rim lighting",
    "act_6": "warm golden-hour resolution lighting",
}


def resolve_act_lighting_hint(act_index_or_role: int | str | None) -> str:
    """Resolve concise Act-level lighting direction (P0-2) without bloating context-split prompts."""
    if act_index_or_role is None:
        return "warm cinematic key-and-rim studio lighting"
    if isinstance(act_index_or_role, int) and not isinstance(act_index_or_role, bool):
        if act_index_or_role <= 1:
            return ACT_LIGHTING_ARC_HINTS["act_1"]
        if act_index_or_role == 2:
            return ACT_LIGHTING_ARC_HINTS["act_2"]
        if act_index_or_role <= 5:
            return ACT_LIGHTING_ARC_HINTS["act_3_5"]
        return ACT_LIGHTING_ARC_HINTS["act_6"]
    raw = str(act_index_or_role).strip().lower()
    if not raw:
        return "warm cinematic key-and-rim studio lighting"
    m_num = re.search(r"(?:^|\bact[\s_-]*)([0-9]+)\b", raw)
    if m_num:
        return resolve_act_lighting_hint(int(m_num.group(1)))
    if any(k in raw for k in ("hook", "opener", "opening", "intro", "problem", "symptom", "alert", "cold_open")):
        return ACT_LIGHTING_ARC_HINTS["act_1"]
    if any(k in raw for k in ("context", "setup", "experiment", "study", "lab", "method", "trial", "baseline")):
        return ACT_LIGHTING_ARC_HINTS["act_2"]
    if any(
        k in raw
        for k in (
            "resolution",
            "conclusion",
            "takeaway",
            "outro",
            "closing",
            "payoff",
            "summary",
            "golden",
        )
    ):
        return ACT_LIGHTING_ARC_HINTS["act_6"]
    return ACT_LIGHTING_ARC_HINTS["act_3_5"]


class SceneDepictionRule:
    """Rule R14-A (Environment/Lighting/Scale), R46 (Iconic Scene), R46-K (Key Visual), R47 (Action-Physics)."""

    SELECTIVE_COLOR_BACKDROP_CLAUSE = SELECTIVE_COLOR_BACKDROP_CLAUSE

    @staticmethod
    def clean_clause(text: str) -> str:
        t = str(text or "").strip()
        return t[:-1].strip() if t.endswith(".") else t

    @classmethod
    def selective_color_backdrop_clause(cls, is_brain: bool = False) -> str:
        """Return warm low-saturation backdrop isolation cue for non-brain 2.5D vinyl scenes (P0-2)."""
        return "" if is_brain else cls.SELECTIVE_COLOR_BACKDROP_CLAUSE

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
        if "porcelain mannequin head" not in core.lower() and "featureless matte-white oval porcelain bust" not in core.lower():
            core = (
                "Clean three-quarter profile of a completely featureless matte-white oval porcelain bust (smooth blank egg-shaped "
                "head silhouette with zero eyes, zero nose, zero mouth, zero ears) with an architectural cutaway cranium revealing "
                "a realistic matte-white 3D porcelain brain inside the skull against a high-contrast cool slate-grey studio backdrop. "
                f"{core}"
            )
        still_framing = (
            "Native vertical 9:16 portrait still composition against a high-contrast cool slate-grey studio backdrop, "
            "framing the featureless matte-white porcelain cranial shell and open 3D anatomical brain cross-section."
            if aspect == FLOW_ASPECT_SHORTS
            else "Native horizontal 16:9 widescreen still composition against a high-contrast cool slate-grey studio backdrop, "
            "framing the featureless matte-white porcelain cranial shell and open 3D anatomical brain cross-section."
        )
        return (
            f"{prefix} {core} {still_framing} Minimalist clean porcelain sculpture style, razor-sharp focus, "
            f"soft studio light, zero human facial features, no text, no letters, no watermark."
        )

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
    """Composes Schema v6 Google Flow Omni 1.2 motion clip prompts for `neuro_diorama` (R56, R58)."""

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
    """R66 Tier 3 Grammar: Photorealistic bright high-key world with clothed matte-white porcelain figures & smooth featureless solid matte-white egg-shaped oval heads."""

    @staticmethod
    def compose(
        environment: str,
        action: str,
        lighting: str = "soft bright studio daylight with crisp rim light",
    ) -> str:
        env = SceneDepictionRule.clean_clause(environment)
        act = SceneDepictionRule.clean_clause(action)
        lit = SceneDepictionRule.clean_clause(lighting)
        # Normalize any legacy Schema v4 frosted-glass cranium wording on cast figures to R66/R67 solid matte-white oval heads
        act = re.sub(
            r"\bwith\s+translucent\s+frosted[- ]glass\s+craniums\b",
            "with smooth featureless solid matte-white egg-shaped oval heads",
            act,
            flags=re.IGNORECASE,
        )
        act = re.sub(
            r"\bwith\s+(?:a\s+)?translucent\s+frosted[- ]glass\s+cranium\b",
            "with a smooth featureless solid matte-white egg-shaped oval head",
            act,
            flags=re.IGNORECASE,
        )
        act = re.sub(
            r"\btranslucent\s+frosted[- ]glass\s+craniums\b",
            "smooth featureless solid matte-white egg-shaped oval heads",
            act,
            flags=re.IGNORECASE,
        )
        act = re.sub(
            r"\btranslucent\s+frosted[- ]glass\s+cranium\b",
            "smooth featureless solid matte-white egg-shaped oval head",
            act,
            flags=re.IGNORECASE,
        )
        combined = f"{env} {act}"
        low_combined = combined.lower()
        has_actor = bool(_PORCELAIN_V7_ACTOR_NOUN_RE.search(combined))
        has_head_spec = any(
            tok in low_combined
            for tok in ("oval head", "porcelain head", "featureless", "faceless", "egg-shaped head")
        )
        if not has_actor or ("porcelain" in low_combined and has_head_spec):
            actor_clause = ""
        elif "porcelain" in low_combined:
            actor_clause = ", each figure with a smooth featureless matte-white oval head"
        elif has_head_spec:
            actor_clause = ", staged as clothed matte-white porcelain figures"
        else:
            actor_clause = ", staged as clothed matte-white porcelain figures with smooth featureless solid matte-white egg-shaped oval heads"
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
    *,
    allow_legacy_frosted_cranium: bool = False,
) -> list[str]:
    """R66 Schema v7 `porcelain_cinematic_v7` scene & prompt validator: enforces high-key porcelain cast (solid smooth oval heads) and contained 4-color 3D brain while blocking fluorescent green spill, particles, mist, low-poly, and Escher/face traps."""
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
    if (
        not allow_legacy_frosted_cranium
        and g != "porcelain_living_brain"
        and re.search(r"\bfrosted[- ]glass\s+craniums?\b", low)
    ):
        issues.append(
            f"[porcelain_v7] '{g}' cast scene contains legacy Schema v4 'frosted-glass cranium'; use smooth featureless solid matte-white egg-shaped oval head (R66)"
        )
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


# ==============================================================================
# Schema v8 — Expressive 2.5D Vinyl Cast, 75% X-Ray Brain & Mini-Cortex Cameo (R68)
# ==============================================================================
FLOW_CAMERA_HARDWARE_NEGATIVE_GUARD = (
    "No flying drone, quadcopter, camera rig, camera lens ring or circular vignette border. "
    "No voiceover, no narration, no background music, no lip movement."
)
BANNED_FLOW_CAMERA_HARDWARE_RE = re.compile(
    r"\b(?:drones?|quadcopters?|uavs?|fpv|cameras?|lens(?:es)?|fisheye|gimbals?|tripods?|cranes?|doll(?:y|ies)|camcorders?|viewfinders?)\b",
    re.IGNORECASE,
)


def sanitize_flow_viewpoint_hardware_terms(text: str) -> str:
    """Rewrites physical camera/drone/lens hardware nouns into disembodied viewpoint motion (Rule R77)."""
    raw = str(text or "")
    if not raw.strip():
        return ""
    guard_stripped = raw.replace(FLOW_CAMERA_HARDWARE_NEGATIVE_GUARD, "").strip()
    sentinel = "__AAB_RADCLIFFE_ROTUNDA__"
    out = re.sub(r"\bRadcliffe\s+Camera\b", sentinel, guard_stripped, flags=re.IGNORECASE)
    replacements: tuple[tuple[re.Pattern[str], str], ...] = (
        (re.compile(r"\b(?:high-altitude\s+)?(?:3D\s+)?(?:aerial|flying|fpv)?\s*(?:drones?|quadcopters?|uavs?)\b", re.IGNORECASE), "aerial viewpoint"),
        (re.compile(r"\b(?:continuous\s+|vertical\s+)?fpv\b", re.IGNORECASE), "forward-gliding"),
        (re.compile(r"\b(?:locked[-\s]+on\s+|locked[-\s]+)?(?:tripods?|on\s+a\s+tripod)\b", re.IGNORECASE), "locked-off framing"),
        (re.compile(r"\b(?:cinema\s+prime|anamorphic|macro|probe|fisheye)\s+lens(?:es)?\b", re.IGNORECASE), "deep-focus clarity"),
        (re.compile(r"\bacross\s+the\s+lens\b", re.IGNORECASE), "across the frame"),
        (re.compile(r"\blens(?:es)?\b", re.IGNORECASE), "perspective"),
        (re.compile(r"\bfisheye\b", re.IGNORECASE), "wide-angle"),
        (re.compile(r"\b(?:camera\s+)?cranes?\b", re.IGNORECASE), "elevated sweep"),
        (re.compile(r"\bdolly[-\s]*zoom\b", re.IGNORECASE), "vertigo perspective"),
        (re.compile(r"\b(?:doll(?:y|ies)|gimbals?)\b", re.IGNORECASE), "smooth glide"),
        (re.compile(r"\btoward\s+(?:the\s+)?camera\b", re.IGNORECASE), "toward the viewer"),
        (re.compile(r"\bpast\s+(?:the\s+)?camera\b", re.IGNORECASE), "past the foreground"),
        (re.compile(r"\bnear\s+(?:the\s+)?camera\b", re.IGNORECASE), "near the foreground"),
        (re.compile(r"\bto\s+(?:the\s+)?camera\b", re.IGNORECASE), "forward"),
        (re.compile(r"\b(?:camcorders?|viewfinders?|cameras?)\b", re.IGNORECASE), "viewpoint"),
    )
    for pat, repl in replacements:
        out = pat.sub(repl, out)
    out = out.replace(sentinel, "Radcliffe Camera")
    out = re.sub(r"\baerial viewpoint\s+aerial viewpoint\b", "aerial viewpoint", out, flags=re.IGNORECASE)
    out = re.sub(r"\bforward-gliding\s+aerial viewpoint\b", "forward-gliding aerial sweep", out, flags=re.IGNORECASE)
    out = re.sub(r"\s+", " ", out).strip()
    return out


EXPRESSIVE_V8_CAMERA_DESCRIPTORS: dict[str, str] = {
    "locked_tripod": "Crisp locked-off cinema framing with lively multi-beat 2.5D character and prop motion",
    "pan_left": "Smooth continuous horizontal viewpoint pan leftward linking Beat A into Beat B",
    "pan_right": "Smooth continuous horizontal viewpoint pan rightward linking Beat A into Beat B",
    "tilt_up": "Smooth continuous vertical viewpoint tilt upward across the miniature room",
    "tilt_down": "Smooth continuous vertical viewpoint tilt downward onto the physical prop action",
    "gentle_push_in": "Smooth expressive straight-in perspective push-in toward the character reaction",
    "clean_pullback_reveal": "Smooth continuous straight-back viewpoint pullback revealing the full room context",
    "dolly_zoom_vertigo": "Punchy 3D perspective push-in toward the subject while background walls and table stay strictly straight and rigid",
    "whip_pan_occlusion": "Brisk horizontal whip-pan sweeping past a clean foreground room edge onto the subject",
    "orbital_3d_arc_sweep": "Continuous 3D orbital viewpoint arc sweeping smoothly around the subject with strong parallax",
    "crane_swoop_dive": "Dynamic 3D elevated swoop diving from high angle down into the physical prop action",
    "portal_dive_flight": "Continuous 3D forward viewpoint flight diving smoothly from the room into the close-up focal beat",
    "fpv_3d_flight": "Agile continuous 3D forward tracking flight gliding through foreground space onto the subject",
    "axial_portal_dive": "Continuous 90-degree vertical portal dive plunging straight through the foreground aperture",
    "drone_aerial_approach": "High-altitude 3D aerial swoop diving smoothly past foreground tree canopies toward the landmark facade",
    "fpv_window_portal_breach": "Continuous forward-gliding sweep skimming stone columns and breaching cleanly through the sliced architectural facade into the interior lab",
    "drone_high_orbit_drop": "Sweeping elevated 3D orbital arc descending from campus rooftops down onto the courtyard action",
    "vertical_90_topdown_dive": "Continuous 90-degree bird's-eye top-down aerial descent dropping straight onto the street-level scene",
    "drone_skyline_pullback": "Continuous ascending 3D aerial pullback rising away from the scene to reveal the sunlit campus skyline",
    "drone_landmark_ascend": "Fast sweeping 3D aerial arc skimming close past the landmark silhouette before soaring steeply skyward above sunlit rooftops",
    "topdown_3d_route_glide": "Vertical 90-degree bird's-eye top-down glide tracking thick solid matte-crimson 3D extruded directional arrows along sunlit street canyons",
    "neural_fpv_dive_in": "Fast macro viewpoint plunges straight through translucent frosted crystal-glass outer cortex folds into the deep subcortical chamber",
    "neural_macro_orbit_hold": "Close-range 3D macro orbital hold gliding smoothly around the luminous optical-glass subcortical structure inside parted crystal-glass cortical ribs",
    "neural_fpv_pullback_out": "Rapid reverse macro viewpoint pulls straight back out through parted frosted crystal-glass cortical folds into full 3D brain view",
    "neural_tract_relay_flight": "Continuous 3D macro trajectory tracking luminous optical-glass fiber bundles from the first subcortical chamber into the target cortical hub",
    "sensory_to_brain_drone": "Smooth clinical 3D anatomical flight sweeping from the external sensory organ along matte nerve tracts into the primary cortex",
    "circuit_cooperation_drone": "Steady 3D clinical anatomical orbit gliding smoothly from the source MNI152 nucleus along translucent white-matter tracts to the target region",
    "global_system_orbit_drone": "Wide three-quarter clinical 3D anatomical orbit framing the translucent head silhouette, cortex, cerebellum, brainstem, and active neural network",
    "1p_nerve_canyon_drone": "Immersive first-person 3D anatomical flight gliding forward down the shadowed sulcal canyon along braided white-matter nerve bundles",
    "3p_region_shutdown_pullout": "Smooth third-person 3D anatomical pullback revealing the whole cerebral cortex and localized regional shutdown",
}

EXPRESSIVE_V8_COMPACT_CAMERA_DESCRIPTORS: dict[str, str] = {
    "locked_tripod": "Locked-off framing showing brisk multi-beat character and prop motion",
    "pan_left": "Continuous 3D viewpoint pan leftward tracking Beat A into Beat B",
    "pan_right": "Continuous 3D viewpoint pan rightward tracking Beat A into Beat B",
    "tilt_up": "Continuous 3D vertical tilt upward following the motion",
    "tilt_down": "Continuous 3D vertical tilt downward onto the hand action",
    "gentle_push_in": "Continuous 3D perspective push-in gliding toward the subject reaction",
    "clean_pullback_reveal": "Continuous 3D viewpoint pullback revealing the wider spatial action",
    "smooth_pull_back": "Continuous 3D perspective pullback revealing the wider spatial action",
    "hero_low_angle": "Subtle upward low-angle hero framing (~40% frame fill) with smooth disembodied push-in.",
    "dolly_zoom_vertigo": "Punchy 3D push-in toward the subject while background walls and table stay strictly straight and rigid",
    "whip_pan_occlusion": "Brisk 3D whip-pan sweeping past a foreground edge onto the action",
    "orbital_3d_arc_sweep": "3D orbital arc sweeping around the subject with strong parallax",
    "crane_swoop_dive": "3D elevated swoop diving from high angle into the prop action",
    "portal_dive_flight": "3D forward flight diving smoothly into the close-up beat",
    "fpv_3d_flight": "Agile 3D forward tracking flight gliding straight toward the subject",
    "axial_portal_dive": "3D vertical portal dive plunging straight through the aperture",
    "drone_aerial_approach": "High-altitude 3D aerial swoop diving past foreground treetops toward the building facade",
    "fpv_window_portal_breach": "Continuous forward-gliding sweep skimming facade columns into the cutaway interior room",
    "drone_high_orbit_drop": "Elevated 3D orbital arc descending smoothly onto the outdoor courtyard action",
    "vertical_90_topdown_dive": "90-degree vertical bird's-eye descent dropping onto the outdoor scene",
    "drone_skyline_pullback": "Ascending 3D aerial pullback rising over rooftops into the sunlit skyline",
    "drone_landmark_ascend": "Fast 3D aerial sweep skimming the landmark before soaring steeply skyward",
    "topdown_3d_route_glide": "Vertical 90-degree bird's-eye top-down glide tracking thick matte-crimson 3D directional arrows",
    "neural_fpv_dive_in": "Fast macro viewpoint plunges through translucent frosted-glass cortical folds into the deep chamber",
    "neural_macro_orbit_hold": "Close-range 3D macro viewpoint orbits smoothly around the luminous optical-glass subcortical hub",
    "neural_fpv_pullback_out": "Rapid reverse macro viewpoint pulls back through frosted-glass cortical folds into wide 3D brain view",
    "neural_tract_relay_flight": "Continuous 3D macro flight glides along luminous optical-glass fiber bundles between subcortical hubs",
    "sensory_to_brain_drone": "Clinical 3D anatomical sweep glides smoothly from external sensory organ into cortical hub",
    "circuit_cooperation_drone": "Clinical 3D anatomical orbit glides smoothly along translucent MNI152 subcortical pathway",
    "global_system_orbit_drone": "Wide 3D anatomical orbit framing translucent skull, cortex, and coordinated neural hubs",
    "1p_nerve_canyon_drone": "First-person 3D anatomical flight gliding down the sulcal nerve canyon",
    "3p_region_shutdown_pullout": "Third-person 3D anatomical pullback revealing global cortical shutdown",
}

EXPRESSIVE_V8_SUPPLEMENTAL_CAMERA_DESCRIPTORS: dict[str, str] = {
    "smooth_pull_back": "Smooth continuous straight-back perspective pullback revealing surrounding room space",
    "hero_low_angle": "Subtle upward 3D low-angle hero perspective (~40% frame fill) with smooth disembodied push-in",
}

EXPRESSIVE_V8_ALTERNATING_NON_BRAIN_MOVES: tuple[str, ...] = (
    "gentle_push_in",
    "smooth_pull_back",
    "hero_low_angle",
)
_EXPRESSIVE_V8_ALTERNATING_BRAIN_MOVES: tuple[str, ...] = (
    "neural_fpv_dive_in",
    "neural_macro_orbit_hold",
)


def resolve_alternating_camera_move(
    clip_index: int,
    is_brain: bool = False,
    explicit_move: str | None = None,
) -> str:
    """Alternate non-brain push-in / pull-back / hero low-angle moves (P1-4), preserving explicit moves."""
    if explicit_move is not None and str(explicit_move).strip():
        return str(explicit_move).strip()
    idx = max(0, int(clip_index))
    if is_brain:
        return _EXPRESSIVE_V8_ALTERNATING_BRAIN_MOVES[idx % len(_EXPRESSIVE_V8_ALTERNATING_BRAIN_MOVES)]
    return EXPRESSIVE_V8_ALTERNATING_NON_BRAIN_MOVES[idx % len(EXPRESSIVE_V8_ALTERNATING_NON_BRAIN_MOVES)]

EXPRESSIVE_V8_WORLD_LEAD = (
    "Stylized 3D cinematic miniature diorama filling the full-bleed vertical frame "
    "with tactile architectural surfaces and cinema key-and-rim lighting"
)

EXPRESSIVE_V8_OPTICS_TAIL = (
    "Clean 3D architectural rendering, tack-sharp deep-focus clarity on smooth featureless matte-white architectural porcelain figures, hands-only or silhouette framing, woven fabric, and warm wood."
)

EXPRESSIVE_V8_XRAY_OPTICS_TAIL = (
    "Clean 3D architectural rendering, tack-sharp deep-focus clarity on the crystal-clear glass cranium dome, bounded 4-color 3D brain circuits, "
    "and smooth featureless matte-white architectural porcelain figure."
)

EXPRESSIVE_V8_TRANSITION_CLAUSES: dict[str, str] = {
    "daisy_chain_bridge": "Holding a clean unobstructed ending pose for seamless next-shot continuity",
    "seamless_relay_cut": "Arriving smoothly on the exact shared keyframe composition for an unbroken one-take relay",
    "occlusion_wipe": "Ending as a foreground architectural pillar or sleeve sweeps cleanly across the frame",
    "action_impact_cut": "Culminating on a crisp physical prop impact at the final beat",
    "dissolve_6f": "Settling into a composed atmospheric beat for a smooth cross-dissolve",
    "dissolve_8f": "Settling into a calm atmospheric beat for a smooth cross-dissolve",
    "dissolve_12f": "Settling into a composed spatial beat for a smooth background dissolve",
    "dissolve_15f": "Settling into a steady spatial beat for a smooth 15-frame dissolve",
    "match_cut_bridge": "Ending centered on the primary geometric prop silhouette for a graphic match cut",
    "split_screen_wipe": "Framing balanced opposing left-and-right visual zones across the room",
    "portal_crash_zoom_10f": "Pushing smoothly inward toward the character cranium silhouette at the final beat",
    "whip_pan_blur_8f": "Accelerating into a brisk lateral viewpoint sweep across a foreground room edge at the final beat",
}

EXPRESSIVE_V8_COMPACT_TRANSITION_CLAUSES: dict[str, str] = {
    "daisy_chain_bridge": "Holds clean ending pose for next cut",
    "seamless_relay_cut": "Locks exact shared keyframe for seamless relay",
    "occlusion_wipe": "Foreground edge sweeps cleanly across the frame at end",
    "action_impact_cut": "Ends on crisp physical prop impact",
    "dissolve_6f": "Settles smoothly for brief dissolve",
    "dissolve_8f": "Settles smoothly for 8-frame dissolve",
    "dissolve_12f": "Settles smoothly for 12-frame background dissolve",
    "dissolve_15f": "Settles smoothly for 15-frame background dissolve",
    "match_cut_bridge": "Ends centered on prop silhouette for match cut",
    "split_screen_wipe": "Balances opposing left-and-right motion zones",
    "portal_crash_zoom_10f": "Pushes inward onto cranium silhouette at end",
    "whip_pan_blur_8f": "Accelerates into brisk lateral edge sweep at end",
}

_EXPRESSIVE_V8_GRAMMAR_SLOT_MAP: dict[str, str] = {
    "expressive_vinyl_world": "expressive_vinyl_world",
    "expressive_exterior_establishing": "expressive_exterior_establishing",
    "exterior_establishing": "expressive_exterior_establishing",
    "architectural_cutaway_portal": "architectural_cutaway_portal",
    "spatial_3d_arrow_diorama": "spatial_3d_arrow_diorama",
    "expressive_hands_closeup": "expressive_hands_closeup",
    "expressive_pov_hands": "expressive_pov_hands",
    "expressive_xray_brain": "expressive_xray_brain",
    "expressive_literal_analogy": "expressive_literal_analogy",
    "expressive_cameo_world": "expressive_cameo_world",
    "expressive_split_contrast": "expressive_split_contrast",
    "expressive_reaction_closeup": "expressive_reaction_closeup",
    "reaction_closeup": "expressive_reaction_closeup",
    "axial_portal_dive": "axial_portal_dive",
    "xray_peel_micro": "xray_peel_micro",
    "ghost_twin_offset": "ghost_twin_offset",
    "lid_lift_reveal": "lid_lift_reveal",
    "locked_exploded_vs_shatter": "locked_exploded_vs_shatter",
    "blueprint_3d_extrusion": "blueprint_3d_extrusion",
    "expressive_character_action": "expressive_vinyl_world",
    "expressive_macro_prop": "expressive_hands_closeup",
    "porcelain_fullbleed_world": "expressive_vinyl_world",
    "porcelain_hands_closeup": "expressive_hands_closeup",
    "porcelain_pov_hands": "expressive_pov_hands",
    "porcelain_living_brain": "expressive_xray_brain",
    "porcelain_literal_analogy": "expressive_literal_analogy",
    "porcelain_cutaway_section": "expressive_split_contrast",
    "fullbleed_world": "expressive_vinyl_world",
    "hands_closeup": "expressive_hands_closeup",
    "pov_hands": "expressive_pov_hands",
    "xray_brain": "expressive_xray_brain",
    "living_brain": "expressive_xray_brain",
    "literal_analogy": "expressive_literal_analogy",
    "cameo_world": "expressive_cameo_world",
    "split_contrast": "expressive_split_contrast",
}

_EXPRESSIVE_V8_BANNED_STYLE_RE = re.compile(
    r"\b(?:low-poly|low\s+poly|flat-shaded|flat\s+shaded|polygon\s+facets?|"
    r"pastel\s+clay|museum\s+plinth|bisque-ceramic|"
    r"featureless\s+(?:solid\s+)?(?:matte-white\s+)?(?:egg-shaped\s+)?oval\s+heads?|"
    r"smooth\s+featureless\s+mannequin|faceless\s+mannequins?)\b",
    flags=re.IGNORECASE,
)

_EXPRESSIVE_V8_HUMAN_FLESH_RE = re.compile(
    r"\b(?:photorealistic\s+human\s+skin|flesh-toned|human\s+flesh|skin\s+pores|stubble|facial\s+hair|bearded|"
    r"flowing\s+hair|human\s+ears|human\s+nose|blood\s+splatter|gore)\b",
    flags=re.IGNORECASE,
)


def normalize_expressive_v8_grammar(grammar: str | None, *, cameo_easter_egg: bool = False) -> str:
    """Maps generic or v7 grammar slot names onto canonical `expressive_*` v8 grammars (R68)."""
    if cameo_easter_egg:
        raw_c = str(grammar or "").strip().lower()
        if raw_c in ("expressive_xray_brain", "porcelain_living_brain", "xray_brain", "living_brain"):
            return "expressive_xray_brain"
        return "expressive_cameo_world"
    raw = str(grammar or "").strip()
    if not raw:
        return "expressive_vinyl_world"
    return _EXPRESSIVE_V8_GRAMMAR_SLOT_MAP.get(raw.lower(), raw)


class ExpressiveVinylWorldRule:
    """R68 Grammar: Stylized 3D diorama world with clothed 2.5D matte cream-white vinyl characters & bold 2D ink expressions."""

    @staticmethod
    def compose(
        environment: str,
        action: str,
        lighting: str = "warm cinematic key-and-rim studio lighting",
        *,
        cameo_prop_note: str = "",
        diegetic_text_allowlist: list[str] | tuple[str, ...] | None = None,
        selective_color: bool = True,
    ) -> str:
        env = SceneDepictionRule.clean_clause(environment)
        act = SceneDepictionRule.clean_clause(action)
        lit = SceneDepictionRule.clean_clause(lighting)
        combined_low = f"{env} {act}".lower()
        has_actor = bool(_PORCELAIN_V7_ACTOR_NOUN_RE.search(f"{env} {act}"))
        has_vinyl_spec = (
            ("vinyl" in combined_low and ("2d" in combined_low or "ink" in combined_low))
            or (
                "porcelain" in combined_low
                and any(tok in combined_low for tok in ("featureless", "silhouette", "hands-only", "x-ray"))
            )
        )
        actor_clause = (
            ""
            if (not has_actor or has_vinyl_spec)
            else (
                ", staged as clothed smooth featureless matte-white architectural porcelain figures framed via "
                "back or three-quarter silhouette, hands-only close-up, or translucent Mode 1 x-ray cranium, "
                "with four-fingered matte-white porcelain hands"
            )
        )
        allow_list = [str(t).strip() for t in (diegetic_text_allowlist or ()) if str(t).strip()][:2]
        allow_clause = ""
        if allow_list and not all(tok.lower() in combined_low for tok in allow_list):
            quoted = ", ".join(f"'{tok}'" for tok in allow_list)
            allow_clause = f" Crisp physical prop stencil displays {quoted} only."
        cameo_clause = ""
        if cameo_prop_note:
            cn = SceneDepictionRule.clean_clause(cameo_prop_note)
            cameo_clause = f" {cn[:1].upper() + cn[1:]}."
        sc_clause = ""
        if (
            selective_color
            and "low-saturation" not in combined_low
            and "isolating the vivid" not in combined_low
        ):
            sc_clause = f", {SceneDepictionRule.SELECTIVE_COLOR_BACKDROP_CLAUSE}"
        return (
            f"{EXPRESSIVE_V8_WORLD_LEAD}: full-bleed view of {env}{sc_clause} in {lit}. "
            f"{act[:1].upper() + act[1:]}{actor_clause}.{allow_clause}{cameo_clause} {EXPRESSIVE_V8_OPTICS_TAIL}"
        )


class ExpressiveHandsActionRule:
    """R68 Grammar: Tight close-up or POV of four-fingered matte cream-white vinyl hands in tailored cloth cuffs."""

    @staticmethod
    def compose(
        attire_and_hands: str,
        prop_action: str,
        consequence: str,
        *,
        pov: bool = False,
        diegetic_text_allowlist: list[str] | tuple[str, ...] | None = None,
    ) -> str:
        att = SceneDepictionRule.clean_clause(attire_and_hands)
        act = SceneDepictionRule.clean_clause(prop_action)
        con = SceneDepictionRule.clean_clause(consequence)
        lead = (
            "first-person POV looking down at smooth matte cream-white four-fingered vinyl hands in tailored cloth cuffs"
            if pov
            else "tight close-up showing smooth matte cream-white four-fingered vinyl hands in tailored cloth cuffs"
        )
        allow_list = [str(t).strip() for t in (diegetic_text_allowlist or ()) if str(t).strip()][:2]
        combined_low = f"{att} {act} {con}".lower()
        allow_clause = ""
        if allow_list and not all(tok.lower() in combined_low for tok in allow_list):
            quoted = ", ".join(f"'{tok}'" for tok in allow_list)
            allow_clause = f" Crisp physical prop stencil shows {quoted}."
        return (
            f"{EXPRESSIVE_V8_WORLD_LEAD}: {lead} ({att}). "
            f"{act[:1].upper() + act[1:]}, while {con}.{allow_clause} {EXPRESSIVE_V8_OPTICS_TAIL}"
        )


class ExpressiveLiteralAnalogyRule:
    """R68 Grammar: Concrete everyday 1-object physical analogy in stylized 3D miniature cinema."""

    @staticmethod
    def compose(
        analogy_world: str,
        comparison_action: str,
        *,
        lighting: str = "crisp dramatic studio key-and-rim lighting",
    ) -> str:
        aw = SceneDepictionRule.clean_clause(analogy_world)
        act = SceneDepictionRule.clean_clause(comparison_action)
        lit = SceneDepictionRule.clean_clause(lighting)
        has_actor = bool(_PORCELAIN_V7_ACTOR_NOUN_RE.search(f"{aw} {act}"))
        has_cast_mat = any(k in f"{aw} {act}".lower() for k in ("vinyl", "porcelain"))
        actor_tail = (
            " Clothed smooth featureless matte-white architectural porcelain figure in back or three-quarter silhouette reacts clearly."
            if (has_actor and not has_cast_mat)
            else ""
        )
        return (
            f"{EXPRESSIVE_V8_WORLD_LEAD}: everyday physical analogy scene in {aw} under {lit}. "
            f"{act[:1].upper() + act[1:]}.{actor_tail} {EXPRESSIVE_V8_OPTICS_TAIL}"
        )


class ExpressiveXRayBrainRule:
    """R68 [70–85%] Mechanism Reveal Grammar: Golden forehead ring seam opens into crystal-clear glass dome with bounded 4-color 3D brain."""

    @staticmethod
    def compose(
        brain_scene: str | None = None,
        *,
        environment: str = "dimly lit cozy bedroom or clinical observation room",
        character_reaction: str = "the smooth featureless matte-white architectural porcelain figure turns in three-quarter silhouette",
        brain_region: str | None = None,
    ) -> str:
        env = SceneDepictionRule.clean_clause(environment)
        react = SceneDepictionRule.clean_clause(character_reaction)
        reg = SceneDepictionRule.clean_clause(brain_region or "")
        reg_focus = f" across the {reg}" if reg else ""
        if brain_scene:
            sc_clause = f"{SceneDepictionRule.clean_clause(brain_scene)} strictly inside enclosed anatomical pathways."
        else:
            sc_clause = "Electric cyan-blue and amber-gold neural pulses travel strictly inside enclosed anatomical pathways."
        return (
            f"{EXPRESSIVE_V8_WORLD_LEAD}: inside {env}, {react} as a thin golden forehead ring seam smoothly transitions "
            f"the upper matte vinyl cranium into a crystal-clear glass dome revealing a bounded 4-color glowing 3D brain{reg_focus}. "
            f"{sc_clause[:1].upper() + sc_clause[1:]} {EXPRESSIVE_V8_XRAY_OPTICS_TAIL}"
        )


class ExpressiveCameoWorldRule:
    """R68 Hybrid Signature Cameo (`안 1 + 안 3 결합형`, 1 cut/episode): subtle 4cm 4-color vinyl `Mini-Cortex` background Easter-egg."""

    @staticmethod
    def compose(
        environment: str,
        action: str,
        cameo_placement: str = "a tiny 4cm glowing 4-color translucent vinyl Mini-Cortex figurine sits quietly on the background nightstand shelf",
        lighting: str = "warm cinematic key-and-rim studio lighting",
        *,
        diegetic_text_allowlist: list[str] | tuple[str, ...] | None = None,
    ) -> str:
        cp = SceneDepictionRule.clean_clause(cameo_placement)
        if "mini-cortex" not in cp.lower():
            cp = f"a tiny 4cm glowing 4-color translucent vinyl Mini-Cortex figurine rests quietly beside {cp}"
        return ExpressiveVinylWorldRule.compose(
            environment=environment,
            action=action,
            lighting=lighting,
            cameo_prop_note=cp,
            diegetic_text_allowlist=diegetic_text_allowlist,
        )


def load_expression_acting_lexicon() -> dict[str, Any]:
    """Loads `BCI_Shorts_Channel/assets/expression_acting_lexicon.json` (`F1~F5` 12-archetype 2.5D ink acting lexicon)."""
    import json
    from pipeline.config import EXPRESSIVE_ACTING_LEXICON_PATH

    p = EXPRESSIVE_ACTING_LEXICON_PATH
    if p.is_file():
        try:
            doc = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(doc, dict) and isinstance(doc.get("expressions"), dict):
                return doc
        except Exception:
            pass
    return {"expressions": {}, "speaker_mouth_rules": {}}


def format_expression_acting_clause(
    expression_id: str | None = None,
    *,
    speaker_role: str = "narrator",
    compact: bool = True,
) -> str:
    """
    Composes the `F1~F5` 2.5D charcoal-ink micro-acting transition (`State A -> State B` + `Saccade` + `<=10°` head pose)
    paired with the `F5` Speaker-Synced Mouth Rule (`Hope`/`Laura`/`foil` speaking vs `Roger` narrator closed reactive mouth).
    """
    lex = load_expression_acting_lexicon()
    exprs = lex.get("expressions") or {}
    mouth_rules = lex.get("speaker_mouth_rules") or {}
    role_key = str(speaker_role or "narrator").strip().lower()
    if role_key in ("researcher", "mini_cortex", "foil"):
        mouth_clause = str(
            mouth_rules.get(role_key)
            or mouth_rules.get("on_camera_mouth_clause")
            or "animated 2D black ink mouth speaking crisply"
        )
    else:
        mouth_clause = str(
            mouth_rules.get("narrator")
            or mouth_rules.get("narrator_mouth_clause")
            or "closed reactive 2D black ink mouth"
        )

    default_snap = f"crisp 2D black ink eyebrows and mouth snap cleanly on the smooth matte cream-white head with {mouth_clause}"
    exp_key = str(expression_id or "").strip().lower()
    entry = exprs.get(exp_key) if exp_key in exprs else None
    if not isinstance(entry, dict):
        return default_snap
    if compact:
        clause = str(entry.get("compact_prompt_clause") or "").strip().rstrip(".")
        clause = re.sub(r"\b(?:charcoal\s+)?ink\s+eyes\s+shift\b", "2D black ink eyebrows and mouth snap cleanly", clause, flags=re.IGNORECASE)
        return f"{clause}, {mouth_clause}" if clause else default_snap
    st_a = str(entry.get("state_a") or "").strip()
    st_b = str(entry.get("state_b") or "").strip()
    sac = sanitize_flow_viewpoint_hardware_terms(str(entry.get("saccade_and_head_pose") or "").strip())
    return f"crisp 2D black ink face snaps cleanly from {st_a} into {st_b} with {sac} and {mouth_clause}"


_EXPLICIT_SUBJECT_START_RE = re.compile(
    r"^(?:the|a|an|two|both|three|young|older|female|male|clothed|2\.5d|"
    r"doctor|dr\.|neurologist|clinician|researcher|mother|father|son|daughter|woman|man|patient|subject|figure|protagonist)\b",
    flags=re.IGNORECASE,
)


class ExpressiveReactionCloseupRule:
    """F2 / M5 / R79-M Grammar (`expressive_reaction_closeup`): Bust-up reaction shot foregrounding subject + snappy physical action + smudge-free 2D ink step-snap."""

    @staticmethod
    def compose(
        environment: str = "studio observation room",
        character_desc: str = "clothed 2.5D matte cream-white vinyl character",
        expression_id: str = "double_blink_shock",
        *,
        speaker_role: str = "narrator",
        action: str = "",
        prop_detail: str = "",
        compact: bool = True,
    ) -> str:
        env = SceneDepictionRule.clean_clause(environment)
        char_c = SceneDepictionRule.clean_clause(character_desc)
        act_clause = format_expression_acting_clause(expression_id, speaker_role=speaker_role, compact=compact)
        phys_c = SceneDepictionRule.clean_clause(action or prop_detail)
        if phys_c:
            phys_c = re.sub(
                r"^first\s*,?\s+(?=(?:the|a|an|two|both|three|2\.5d|doctor|neurologist|clinician|researcher|pharmacist|patient|woman|man|subject|four-fingered)\b)",
                "",
                phys_c,
                flags=re.IGNORECASE,
            ).strip()
            if phys_c:
                phys_c = phys_c[:1].upper() + phys_c[1:]
            if _EXPLICIT_SUBJECT_START_RE.search(phys_c) or "2.5d" in phys_c[:68].lower() or bool(_PORCELAIN_V7_ACTOR_NOUN_RE.search(phys_c[:68])):
                subj_action = phys_c
            else:
                subj_action = f"{char_c} {phys_c[:1].lower() + phys_c[1:]}"
            if compact:
                return f"Bust-up close-up: {subj_action}, and {act_clause}"
            return (
                f"{EXPRESSIVE_V8_WORLD_LEAD}: bust-up close-up in {env} where {subj_action}, "
                f"and {act_clause}. {EXPRESSIVE_V8_OPTICS_TAIL}"
            )
        if compact:
            return f"Bust-up close-up in {env}: {char_c} leans sharply as {act_clause}"
        return (
            f"{EXPRESSIVE_V8_WORLD_LEAD}: bust-up close-up in {env} framing {char_c} leaning sharply as {act_clause}. "
            f"{EXPRESSIVE_V8_OPTICS_TAIL}"
        )


class ExpressiveRigidPhysicsRule:
    """M7 (`R68-A`) 6 Rigid Diorama Physics Grammars inspired by architectural/medical breakdown documentaries."""

    RIGID_GRAMMARS: tuple[str, ...] = (
        "axial_portal_dive",
        "xray_peel_micro",
        "ghost_twin_offset",
        "lid_lift_reveal",
        "locked_exploded_vs_shatter",
        "blueprint_3d_extrusion",
        "architectural_cutaway_portal",
    )

    @classmethod
    def compose(
        cls,
        grammar: str,
        subject_or_structure: str = "Subject",
        mechanism_action: str = "separates along rigid mechanical seams",
        *,
        subject: str | None = None,
        action: str | None = None,
        compact: bool = True,
    ) -> str:
        g = str(grammar or "axial_portal_dive").strip().lower()
        subj = SceneDepictionRule.clean_clause(subject or subject_or_structure)
        act = SceneDepictionRule.clean_clause(action or mechanism_action)
        templates_compact = {
            "axial_portal_dive": f"90-degree vertical portal dive plunging straight through {subj} as {act}, tack-sharp f/8 deep focus",
            "xray_peel_micro": f"Rigid outer shell of {subj} slides cleanly aside to expose translucent internal 3D pathways as {act}",
            "ghost_twin_offset": f"Translucent amber-gold ghost twin silhouette slides smoothly beside {subj} to compare {act}",
            "lid_lift_reveal": f"Rigid architectural ceiling lid of {subj} lifts vertically upward in clean mechanical unison revealing {act}",
            "locked_exploded_vs_shatter": f"Locked-off view of {subj} separating into weightless aligned exploded-view layers while {act}",
            "blueprint_3d_extrusion": f"Crisp white 3D wireframe brain and rigid geometry extrude vertically upward from {subj} as {act}",
            "architectural_cutaway_portal": f"Exterior masonry facade of {subj} slices cleanly open into a 3D architectural cross-section revealing {act}",
        }
        clause = templates_compact.get(g, templates_compact["axial_portal_dive"])
        if compact:
            return clause
        return f"{EXPRESSIVE_V8_WORLD_LEAD}: {clause}. {EXPRESSIVE_V8_OPTICS_TAIL}"


class ExpressiveV8PromptComposer:
    """Composes Schema v8 `expressive_25d_v8` 8-second multi-beat prompts with keyframe trajectory & transition choreography (R68)."""

    @staticmethod
    def compose_clip_prompt(
        scene_body: str,
        grammar: str = "expressive_vinyl_world",
        camera_move: str = "gentle_push_in",
        transition_out: str | None = None,
        aspect: str = FLOW_ASPECT_SHORTS,
        render_sec: int = 8,
        keyframe_bridge_clause: str | None = None,
        *,
        context_split: bool = False,
        r85_mode: bool = False,
    ) -> str:
        from pipeline.config import (
            EXPRESSIVE_V8_CONTEXT_SPLIT_WORDS_RANGE,
            EXPRESSIVE_V8_TRANSITION_TYPES,
            EXPRESSIVE_V8_VISUAL_GRAMMARS,
            PROMPT_SCENE_WORDS_MAX,
        )

        g = grammar if grammar in EXPRESSIVE_V8_VISUAL_GRAMMARS else "expressive_vinyl_world"
        label = "vertical portrait" if aspect == FLOW_ASPECT_SHORTS else "horizontal widescreen"
        cam_key = str(camera_move or "gentle_push_in").strip().lower()
        body = SceneDepictionRule.clean_clause(scene_body)
        body = re.sub(r"\bmuseums?\b", "studio", body, flags=re.IGNORECASE).rstrip(".")
        body = sanitize_flow_viewpoint_hardware_terms(body)
        guard_tail = "" if g == "brain_simulator_3d" else f" {FLOW_CAMERA_HARDWARE_NEGATIVE_GUARD}"

        if context_split:
            lo_w, hi_w = EXPRESSIVE_V8_CONTEXT_SPLIT_WORDS_RANGE
            cam_clause = EXPRESSIVE_V8_COMPACT_CAMERA_DESCRIPTORS.get(
                cam_key, EXPRESSIVE_V8_COMPACT_CAMERA_DESCRIPTORS["gentle_push_in"]
            ).rstrip(".")
            if r85_mode and g == "expressive_xray_brain":
                cam_clause = (
                    cam_clause.replace("translucent frosted-glass cortical folds", "matte silver-white sculpted gypsum cortical folds")
                    .replace("frosted-glass cortical folds", "matte silver-white cortical folds")
                    .replace("luminous optical-glass subcortical hub", "solid matte-shaded subcortical hub")
                    .replace("luminous optical-glass fiber bundles", "opaque sulcal and white-matter tubes")
                )
            # Prompt Diet: Flow UI already sets 9:16, 8s, and Start/End Frames, and dissolve happens in NLE assembly.
            # Strip `8s vertical video.`, `Bridges opening...`, and `Settles smoothly...` so Veo focuses 100% on action.
            audio_tail = "Silent voice track."
            core_body = body[:1].upper() + body[1:] if body else "Subject shifts posture crisply with smooth matte-white porcelain arms and four-fingered hands"
            if r85_mode and g == "expressive_xray_brain" and ":" in core_body and core_body.lower().startswith("episode #31 mode"):
                head_ep31, motion_ep31 = core_body.rsplit(":", 1)
                motion_clean = motion_ep31.strip()
                if len(motion_clean.split()) >= 8:
                    hl = head_ep31.lower()
                    if "mode 1" in hl:
                        compact_head = "Episode #31 Mode 1 clear-cranium X-ray mannequin bust revealing matte white gypsum 3D brain"
                    elif "dual-specimen" in hl or "two complete" in hl:
                        compact_head = "Episode #31 Mode 2 dual-specimen matte white gypsum 3D brains over dark navy void"
                    elif "canyon" in hl:
                        compact_head = "Episode #31 Mode 2 macro sulcal canyon inside matte white gypsum 3D brain"
                    elif "coronal" in hl:
                        compact_head = "Episode #31 Mode 2 front-facing coronal matte white gypsum 3D brain cutaway"
                    else:
                        compact_head = "Episode #31 Mode 2 matte white gypsum 3D brain over dark navy void"
                    core_body = f"{compact_head}: {motion_clean}"
            req_tail = ""
            if g == "expressive_xray_brain" and not (
                any(k in core_body.lower() for k in ("3d brain", "3d human brain", "hemisphere", "cerebral", "cutaway", "cortical"))
                and any(
                    k in core_body.lower()
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
                )
            ):
                req_tail = (
                    "Matte silver-white 3D brain reveals thick sky-blue branching surface vessel tubes."
                    if r85_mode
                    else "Translucent frosted-glass 3D brain reveals internal tracts."
                )
            elif g == "expressive_cameo_world" and "mini-cortex" not in core_body.lower():
                req_tail = "Tiny 4cm Mini-Cortex rests nearby."
            tail_block = f"{req_tail} {audio_tail}".strip() if req_tail else audio_tail
            draft = f"{cam_clause}. {core_body}. {tail_block}"
            draft = re.sub(r"\s+", " ", draft).strip()
            words_cur = draft.split()
            if len(words_cur) < lo_w:
                from pipeline.config import EXPRESSIVE_V8_DRONE_CAMERA_MOVES, EXPRESSIVE_V8_NEURAL_DIVE_MOVES

                is_arch_or_drone = g in (
                    "expressive_exterior_establishing",
                    "architectural_cutaway_portal",
                    "spatial_3d_arrow_diorama",
                ) or cam_key in (
                    *EXPRESSIVE_V8_DRONE_CAMERA_MOVES,
                    "drone_pullback_skyline",
                )
                if cam_key in EXPRESSIVE_V8_NEURAL_DIVE_MOVES or g == "expressive_xray_brain":
                    pad_detail = (
                        "Matte silver-white sculpted gypsum gyri and thick sky-blue branching surface vessel tubes glide past with clean 3D parallax."
                        if r85_mode
                        else "Frosted borosilicate crystal-glass cortical ribs sweep past foreground edges with crisp optical parallax."
                    )
                elif is_arch_or_drone:
                    pad_detail = "Crisp sunlight casts sharp architectural shadows across foreground tree canopies, masonry columns, and walkways."
                else:
                    pad_detail = "Smooth matte-white architectural porcelain arms and four-fingered hands complete the prop motion crisply."
                draft = f"{cam_clause}. {core_body}. {pad_detail} {tail_block}"
                draft = re.sub(r"\s+", " ", draft).strip()
                words_cur = draft.split()
            max_core_w = hi_w
            if guard_tail:
                guard_words = len(guard_tail.split())
                if PROMPT_SCENE_WORDS_MAX - guard_words >= lo_w:
                    max_core_w = min(hi_w, PROMPT_SCENE_WORDS_MAX - guard_words)
            if len(words_cur) > max_core_w:
                fixed_prefix = f"{cam_clause}."
                fixed_suffix = tail_block
                budget = max(10, max_core_w - len(fixed_prefix.split()) - len(fixed_suffix.split()))
                trimmed_body = _trim_v8_body_clause_safe(core_body, budget)
                if g == "expressive_xray_brain":
                    tb_low = trimmed_body.lower()
                    has_brain_noun = any(
                        k in tb_low
                        for k in ("3d brain", "3d human brain", "hemisphere", "cerebral", "cutaway", "cortical")
                    )
                    has_xray_mat = any(
                        k in tb_low
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
                    )
                    if not (has_brain_noun and has_xray_mat):
                        anchor_tail = (
                            "Inside matte silver-white 3D brain cutaway."
                            if r85_mode
                            else "Inside translucent frosted-glass 3D brain."
                        )
                        trimmed_body = _trim_v8_body_clause_safe(core_body, max(10, budget - len(anchor_tail.split())))
                        trimmed_body = f"{trimmed_body} {anchor_tail}".strip()
                draft = re.sub(r"\s+", " ", f"{fixed_prefix} {trimmed_body} {fixed_suffix}").strip()
            return f"{draft}{guard_tail}".strip()

        cam_clause = (
            EXPRESSIVE_V8_CAMERA_DESCRIPTORS.get(cam_key)
            or EXPRESSIVE_V8_SUPPLEMENTAL_CAMERA_DESCRIPTORS.get(cam_key)
            or EXPRESSIVE_V8_CAMERA_DESCRIPTORS["gentle_push_in"]
        ).rstrip(".")
        bridge_clause = ""
        if keyframe_bridge_clause and str(keyframe_bridge_clause).strip():
            bc = SceneDepictionRule.clean_clause(str(keyframe_bridge_clause))
            bc = re.sub(r"\bmuseums?\b", "studio", bc, flags=re.IGNORECASE).rstrip(".")
            bc = sanitize_flow_viewpoint_hardware_terms(bc)
            if bc and bc.lower() not in body.lower():
                bridge_clause = f" {bc[:1].upper() + bc[1:]}."
        trans_key = str(transition_out or "").strip().lower()
        trans_clause = ""
        if trans_key in EXPRESSIVE_V8_TRANSITION_TYPES and trans_key in EXPRESSIVE_V8_TRANSITION_CLAUSES:
            tc = EXPRESSIVE_V8_TRANSITION_CLAUSES[trans_key].rstrip(".")
            if tc.lower() not in body.lower() and tc.lower() not in bridge_clause.lower():
                trans_clause = f" {tc}."
        audio_clause = "Crisp tactile physical foley and subtle room ambience only, silent voice track."
        return f"Generate an {int(render_sec)}-second {label} video clip. {cam_clause}. {body}.{bridge_clause}{trans_clause} {audio_clause}{guard_tail}"


_EXPRESSIVE_V8_CONTEXT_SPLIT_BLOAT_RE = re.compile(
    r"(?:stylized\s+3d\s+cinematic\s+miniature\s+diorama\s+filling|"
    r"tactile\s+architectural\s+surfaces\s+and\s+cinema\s+key-and-rim|"
    r"crisp\s+cinema\s+prime\s+lens\s+clarity|"
    r"smooth\s+earless\s+hairless\s+noseless\s+oval\s+heads)",
    flags=re.IGNORECASE,
)

_R79M_BANNED_INK_SMUDGE_RE = re.compile(
    r"\b(?:(?:charcoal[-\s]+)?ink\s+eyes\s+shift|pupils?\s+dart|eyes\s+slowly\s+widen|eyebrows?\s+morph|facial\s+lines?\s+flow)\b",
    flags=re.IGNORECASE,
)

_R79M_BANNED_WALL_WARP_RE = re.compile(
    r"\b(?:warping\s+background\s+depth|perspective\s+warp\s+compressing\s+background)\b",
    flags=re.IGNORECASE,
)

_R79M_DANGLING_TRUNCATION_RE = re.compile(
    r"\b(?:in|on|at|to|of|for|with|from|into|onto|across|toward|towards|through|under|over|"
    r"between|behind|beside|beneath|the|a|an|his|her|their|its|and|or|but|as|while|2d|unblinking)\s*\.(?:\s|$)",
    flags=re.IGNORECASE,
)

_R79M_TRAILING_DANGLING_WORD_RE = re.compile(
    r"^(?:in|on|at|to|of|for|with|from|into|onto|across|toward|towards|through|under|over|"
    r"between|behind|beside|beneath|the|a|an|his|her|their|its|and|or|but|as|while|2d|flat|unblinking|matte|cream-white|charcoal-black)$",
    flags=re.IGNORECASE,
)

_R79M_PHYSICAL_ACTION_VERB_RE = re.compile(
    r"\b(?:recoils?|leans?|raises?|lifts?|sets?|places?|flips?|pushes?|pulls?|steps?|walks?|strides?|"
    r"turns?|nods?|shakes?|folds?|crosses?|reaches?|hands?|takes?|presses?|grips?|grabs?|taps?|opens?|"
    r"closes?|shuts?|swings?|spreads?|slides?|points?|gestures?|stands?|sits?|drops?|catches?|holds?|"
    r"tilts?|draws?|shifts?|snaps?|blinks?|reacts?|waves?|slams?|spins?|twists?|bows?|kneels?|crouches?|"
    r"backs?|jerks?|jumps?|springs?|pivots?|glances?|peers?|smiles?|frowns?|squints?|furrows?|perks?|"
    r"shines?|writes?|checks?|clicks?|locks?|adjusts?|moves?|passes?|offers?|cradles?|clutches?|rests?|"
    r"sweeps?|separates?|extrudes?|slices?|softens?|curves?|darts?|speaks?|speaking)\b",
    flags=re.IGNORECASE,
)


def _trim_v8_body_clause_safe(core_body: str, budget: int) -> str:
    """
    Trims an over-budget context-split body strictly on complete clause boundaries
    while preserving subject + core physical action verb and stripping any dangling trailing stopword (Rule R79-M).
    """
    txt = str(core_body or "").strip().rstrip(".")
    if len(txt.split()) <= budget:
        return f"{txt}."

    clause_seps = ("; ", ". ", ", and ", ", while ", ", as ", ", then ", ", ")
    cur = txt
    for sep in clause_seps:
        while len(cur.split()) > budget and sep in cur:
            head, _ = cur.rsplit(sep, 1)
            head_clean = head.strip(" ,;:")
            if len(head_clean.split()) >= 8 and _R79M_PHYSICAL_ACTION_VERB_RE.search(head_clean):
                cur = head_clean
            else:
                break
        if len(cur.split()) <= budget:
            break

    words = cur.split()
    if len(words) > budget:
        words = words[:budget]
    while len(words) > 6:
        w_last = words[-1].rstrip(".,;:")
        if _R79M_TRAILING_DANGLING_WORD_RE.match(w_last):
            words.pop()
        else:
            break
    out = " ".join(words).rstrip(".,;:")
    return f"{out}."


def _strip_allowlisted_diegetic_tokens(text: str, allowlist: list[str] | tuple[str, ...] | None) -> str:
    cleaned = str(text or "")
    for raw_tok in allowlist or ():
        tok = str(raw_tok or "").strip()
        if not tok:
            continue
        cleaned = re.sub(re.escape(tok), " ", cleaned, flags=re.IGNORECASE)
    # Also strip neutral prompt phrasing introducing allowlisted prop stencils
    cleaned = re.sub(r"\bprop\s+stencil\s+(?:displays|shows)\b", " ", cleaned, flags=re.IGNORECASE)
    return cleaned


def validate_expressive_v8_scene(
    scene_or_prompt: str,
    grammar: str = "expressive_vinyl_world",
    camera_move: str = "",
    *,
    diegetic_text_allowlist: list[str] | tuple[str, ...] | None = None,
    cameo_easter_egg: bool = False,
    image_conditioned: bool = False,
    allow_legacy_hardware: bool = False,
    allow_legacy_r79m: bool = False,
) -> list[str]:
    """
    R68 Schema v8 `expressive_25d_v8` scene & prompt validator:
      - Enforces 2.5D matte cream-white vinyl cast + bold 2D cartoon ink facial expressions on unconditioned text prompts,
        and Previs Rule ③ Context-Splitting (zero world/material/optics bloat) when `image_conditioned=True`.
      - Enforces crystal-dome golden-seam 4-color 3D brain reveal on `expressive_xray_brain`.
      - Enforces subtle 4cm `Mini-Cortex` background cameo on `expressive_cameo_world` / `cameo_easter_egg=True`.
      - Enforces Rule R77 ban on physical camera/drone/lens hardware terms in non-simulator Flow prompts.
      - Permits <= 2 short uppercase `diegetic_text_allowlist` prop tokens while blocking unrequested signage/paragraphs.
    """
    from pipeline.config import EXPRESSIVE_V8_VISUAL_GRAMMARS, R85_BRAIN_ANTI_VFX_NEGATIVE_CLAUSE

    issues: list[str] = []
    g = str(grammar or "").strip()
    _ = camera_move
    if g not in EXPRESSIVE_V8_VISUAL_GRAMMARS:
        issues.append(f"[expressive_v8] invalid grammar '{g}' (must be in {list(EXPRESSIVE_V8_VISUAL_GRAMMARS)}) (R68)")
    raw = str(scene_or_prompt or "")
    raw_wo_guard = (
        raw.replace(FLOW_CAMERA_HARDWARE_NEGATIVE_GUARD, "")
        .replace(R85_BRAIN_ANTI_VFX_NEGATIVE_CLAUSE + ".", "")
        .replace(R85_BRAIN_ANTI_VFX_NEGATIVE_CLAUSE, "")
        .strip()
    )
    low = raw_wo_guard.lower()

    allow_tokens = [str(t).strip() for t in (diegetic_text_allowlist or ()) if str(t).strip()]
    if len(allow_tokens) > 2:
        issues.append(
            f"[expressive_v8] diegetic_text_allowlist has {len(allow_tokens)} items > max 2 short prop stencils (R68)"
        )
    for tok in allow_tokens:
        if len(tok) > 16 or len(tok.split()) > 3:
            issues.append(
                f"[expressive_v8] diegetic_text_allowlist token '{tok}' exceeds max 3 words / 16 chars (sentences forbidden) (R68)"
            )

    if image_conditioned:
        bloat_hits = sorted({m.group(0).lower() for m in _EXPRESSIVE_V8_CONTEXT_SPLIT_BLOAT_RE.finditer(raw)})
        if bloat_hits:
            issues.append(
                f"[expressive_v8] image-conditioned clip repeats redundant world/material/optics bloat {bloat_hits}; "
                "use Previs Rule 3 context-split prompt (30-60 words: camera trajectory + physical action + hand/expression only) (R68)"
            )

    if g == "brain_simulator_3d":
        if not any(k in low for k in ("mni152", "3d brain", "blender", "clinical", "cortex", "pathway")):
            issues.append("[expressive_v8] 'brain_simulator_3d' missing MNI152 3D clinical simulator specification (R76)")
    elif g == "expressive_xray_brain":
        if not any(k in low for k in ("3d brain", "3d human brain", "hemisphere", "anatomical brain", "cerebral cortex", "cutaway", "cerebral")):
            issues.append("[expressive_v8] 'expressive_xray_brain' missing '3D brain' or 'hemisphere' reveal anchor (R68)")
        if not any(k in low for k in ("glass dome", "crystal-clear", "translucent", "frosted-glass", "golden forehead", "x-ray", "silver-white", "silver-gray", "gypsum", "matte silver", "sulcal", "cutaway")):
            issues.append("[expressive_v8] 'expressive_xray_brain' missing X-Ray or Ep #31 silver-white cutaway anchor (R68/R85)")
    elif not image_conditioned and g in ("expressive_hands_closeup", "expressive_pov_hands"):
        if not any(k in low for k in ("vinyl", "porcelain")):
            issues.append(f"[expressive_v8] '{g}' missing 'vinyl' or 'porcelain' hands material anchor (R68/R88)")
    elif not image_conditioned and g in ("expressive_vinyl_world", "expressive_cameo_world"):
        if _PORCELAIN_V7_ACTOR_NOUN_RE.search(raw) and not any(k in low for k in ("vinyl", "porcelain")):
            issues.append(f"[expressive_v8] '{g}' stages character(s) without 'vinyl'/'porcelain' 2.5D figure anchor (R68/R88)")

    if (g == "expressive_cameo_world" or cameo_easter_egg) and "mini-cortex" not in low:
        issues.append("[expressive_v8] cameo clip missing 'Mini-Cortex' 4cm background Easter-egg figurine anchor (R68)")

    style_hits = sorted({m.group(0).lower() for m in _EXPRESSIVE_V8_BANNED_STYLE_RE.finditer(raw)})
    if style_hits:
        issues.append(
            f"[expressive_v8] scene contains banned legacy low-poly/faceless-mannequin token(s) {style_hits} (R68)"
        )
    flesh_hits = sorted({m.group(0).lower() for m in _EXPRESSIVE_V8_HUMAN_FLESH_RE.finditer(raw)})
    if flesh_hits:
        issues.append(f"[expressive_v8] scene contains banned human-flesh/gore token(s) {flesh_hits} (R68)")

    toxic_hits = {m.group(0).lower() for m in _PORCELAIN_V7_BANNED_GLOBAL_TOXIC_RE.finditer(raw_wo_guard)}
    if g == "expressive_xray_brain":
        toxic_hits |= {m.group(0).lower() for m in _PORCELAIN_V7_BRAIN_UNCONTAINED_SPILL_RE.finditer(raw_wo_guard)}
    if toxic_hits:
        issues.append(
            f"[expressive_v8] scene contains banned uncontained fluorescent/particle/slime token(s) {sorted(toxic_hits)} (R68)"
        )

    neg_hits = sorted({m.group(0).lower() for m in _PORCELAIN_V7_PINK_ELEPHANT_RE.finditer(raw_wo_guard)})
    if neg_hits:
        issues.append(
            f"[expressive_v8] scene contains banned Pink-Elephant negative noun phrase(s) {neg_hits}; use positive phrasing only (R68)"
        )

    if g != "brain_simulator_3d" and not allow_legacy_hardware:
        hw_check = re.sub(r"\bRadcliffe\s+Camera\b", "Radcliffe_Rotunda", raw_wo_guard, flags=re.IGNORECASE)
        hw_match = BANNED_FLOW_CAMERA_HARDWARE_RE.search(hw_check)
        if hw_match:
            issues.append(
                f"[r77_hardware_ban] Flow prompt contains banned physical camera/drone/lens hardware term '{hw_match.group(0)}' "
                "(use disembodied viewpoint motion instead) (R77)"
            )

    stripped_for_text = _strip_allowlisted_diegetic_tokens(raw_wo_guard, allow_tokens)
    txt_hits = sorted({m.group(0).lower() for m in _PORCELAIN_V7_BANNED_IN_SCENE_TEXT_RE.finditer(stripped_for_text)})
    if txt_hits:
        issues.append(f"[expressive_v8] scene contains unallowlisted signage/text-trigger token(s) {txt_hits} (R68)")

    if not allow_legacy_r79m and g != "brain_simulator_3d":
        smudge_hit = _R79M_BANNED_INK_SMUDGE_RE.search(raw_wo_guard)
        if smudge_hit:
            issues.append(
                f"[r79m_ink_smudge_ban] scene contains banned smudge-trigger phrase '{smudge_hit.group(0)}' "
                "(use crisp 2D black ink step-snap phrasing instead) (R79-M)"
            )
        warp_hit = _R79M_BANNED_WALL_WARP_RE.search(raw_wo_guard)
        if warp_hit:
            issues.append(
                f"[r79m_wall_warp_ban] scene contains banned rubber-architecture warp phrase '{warp_hit.group(0)}' "
                "(keep background walls and tables strictly straight and rigid) (R79-M)"
            )
        trunc_hit = _R79M_DANGLING_TRUNCATION_RE.search(raw_wo_guard)
        if trunc_hit:
            issues.append(
                f"[r79m_dangling_truncation] prompt contains mid-sentence truncated ending '{trunc_hit.group(0).strip()}' (R79-M)"
            )
        if g in (
            "expressive_vinyl_world",
            "expressive_reaction_closeup",
            "expressive_hands_closeup",
            "expressive_pov_hands",
            "expressive_cameo_world",
            "expressive_split_contrast",
        ) and str(camera_move or "").strip() not in EXPRESSIVE_V8_DRONE_CAMERA_MOVES:
            body_check = raw_wo_guard
            for cam_desc in (*EXPRESSIVE_V8_CAMERA_DESCRIPTORS.values(), *EXPRESSIVE_V8_COMPACT_CAMERA_DESCRIPTORS.values()):
                body_check = body_check.replace(cam_desc, " ")
            body_check = re.sub(r"silent\s+voice\s+track\.?", " ", body_check, flags=re.IGNORECASE)
            body_check = re.sub(r"\bclose-ups?\b", " ", body_check, flags=re.IGNORECASE)
            if not _R79M_PHYSICAL_ACTION_VERB_RE.search(body_check) and "zero people" not in body_check.lower():
                issues.append(
                    f"[r79m_missing_action_verb] '{g}' human character scene lacks an explicit physical action verb (R79-M)"
                )
    return issues


__all__ = [
    "ACT_LIGHTING_ARC_HINTS",
    "ArchitecturalBrainMaquetteRule",
    "BANNED_BRAIN_PARTICLE_TOKENS",
    "BANNED_FLOW_CAMERA_HARDWARE_RE",
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
    "EXPRESSIVE_V8_ALTERNATING_NON_BRAIN_MOVES",
    "EXPRESSIVE_V8_CAMERA_DESCRIPTORS",
    "EXPRESSIVE_V8_COMPACT_CAMERA_DESCRIPTORS",
    "EXPRESSIVE_V8_COMPACT_TRANSITION_CLAUSES",
    "EXPRESSIVE_V8_OPTICS_TAIL",
    "EXPRESSIVE_V8_SUPPLEMENTAL_CAMERA_DESCRIPTORS",
    "EXPRESSIVE_V8_TRANSITION_CLAUSES",
    "EXPRESSIVE_V8_WORLD_LEAD",
    "EXPRESSIVE_V8_XRAY_OPTICS_TAIL",
    "FLOW_CAMERA_HARDWARE_NEGATIVE_GUARD",
    "ExpressiveCameoWorldRule",
    "ExpressiveHandsActionRule",
    "ExpressiveLiteralAnalogyRule",
    "ExpressiveReactionCloseupRule",
    "ExpressiveRigidPhysicsRule",
    "ExpressiveV8PromptComposer",
    "ExpressiveVinylWorldRule",
    "ExpressiveXRayBrainRule",
    "format_expression_acting_clause",
    "load_expression_acting_lexicon",
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
    "SELECTIVE_COLOR_BACKDROP_CLAUSE",
    "SceneDepictionRule",
    "SensorMotifRule",
    "TactileTokenGridRule",
    "ZERO_FLESH_AND_TEXT_LOCK",
    "normalize_expressive_v8_grammar",
    "normalize_porcelain_v7_grammar",
    "resolve_act_lighting_hint",
    "resolve_alternating_camera_move",
    "sanitize_flow_viewpoint_hardware_terms",
    "validate_expressive_v8_scene",
    "validate_lowpoly_v7_scene",
    "validate_porcelain_v7_scene",
    "validate_zero_flesh_and_crystal_specimen",
]





# --- Migrated Scene / Color / Outdoor Location Helpers ---
import json as _json_dr
from pathlib import Path as _Path_dr

_OUTDOOR_ENV_KEYWORDS: tuple[str, ...] = (
    "outdoor", "exterior", "courtyard", "quad", "campus", "portico", "facade", "aerial",
    "crosswalk", "street", "avenue", "plaza", "square", "bridge", "footbridge", "river",
    "park", "walkway", "promenade", "market", "pavilion", "stadium", "bleacher", "rooftop",
    "terrace", "skyline", "subway platform", "underground platform", "station platform",
    "harvard yard", "cutaway",
)


def hex_to_rgb(color_hex: str) -> tuple[int, int, int]:
    """Parses `#RRGGBB` into `(R, G, B)` integers in `0..255`."""
    raw = str(color_hex or "").strip().lstrip("#")
    if len(raw) != 6 or any(c not in "0123456789abcdefABCDEF" for c in raw):
        raise ValueError(f"Invalid hex color {color_hex!r}; expected \x27#RRGGBB\x27")
    return int(raw[0:2], 16), int(raw[2:4], 16), int(raw[4:6], 16)


def load_location_registry(path: _Path_dr | None = None) -> dict[str, Any]:
    from pipeline.config import LOCATION_REGISTRY_PATH

    reg_p = _Path_dr(path) if path is not None else _Path_dr(LOCATION_REGISTRY_PATH)
    if reg_p.is_file():
        try:
            doc = _json_dr.loads(reg_p.read_text(encoding="utf-8"))
            if isinstance(doc, dict) and isinstance(doc.get("locations"), dict):
                return doc
        except Exception:  # noqa: BLE001
            pass
    return {"locations": {}}


def is_outdoor_or_architectural_clip(
    clip_or_loc: dict[str, Any] | str | None,
    *,
    registry: dict[str, Any] | None = None,
) -> bool:
    reg = registry if isinstance(registry, dict) else load_location_registry()
    locs = reg.get("locations") if isinstance(reg.get("locations"), dict) else {}

    if isinstance(clip_or_loc, dict):
        if bool(clip_or_loc.get("outdoor")) or bool(clip_or_loc.get("is_outdoor")):
            return True
        g_raw = str(clip_or_loc.get("grammar") or clip_or_loc.get("visual_grammar") or "").strip().lower()
        if g_raw in ("expressive_exterior_establishing", "architectural_cutaway_portal", "spatial_3d_arrow_diorama"):
            return True
        loc_id = str(clip_or_loc.get("location_id") or "").strip().lower().replace("-", "_")
        env_txt = f"{loc_id} {clip_or_loc.get('environment', '')} {clip_or_loc.get('scene', '')}".lower()
    else:
        loc_id = str(clip_or_loc or "").strip().lower().replace("-", "_")
        env_txt = loc_id

    if loc_id:
        if loc_id in locs and isinstance(locs[loc_id], dict):
            return bool(locs[loc_id].get("outdoor"))
        for k_loc, spec_loc in locs.items():
            if not isinstance(spec_loc, dict):
                continue
            aliases = [str(a).strip().lower() for a in (spec_loc.get("aliases") or [])]
            if k_loc in loc_id or loc_id in k_loc or any(a in loc_id or loc_id in a for a in aliases):
                if bool(spec_loc.get("outdoor")):
                    return True
    return any(kw in env_txt for kw in _OUTDOOR_ENV_KEYWORDS)


def format_previs_color_mapping_prompt(
    color_role_legend: dict[str, dict[str, str]] | None,
    *,
    style_profile: str = "expressive_25d_v8",
    has_character_sheet: bool = True,
) -> str:
    legend = dict(color_role_legend or {})
    mappings: list[str] = []
    for role_id, meta in legend.items():
        c_name = str(meta.get("color_name") or role_id).strip()
        c_hex = str(meta.get("color_hex") or "").strip()
        t_lbl = str(meta.get("target_label") or role_id).strip()
        kind = str(meta.get("entity_kind") or "actor")
        tag = f"{c_name} ({c_hex})" if c_hex else c_name
        if kind == "prop":
            mappings.append(f"{tag} box = real-world {t_lbl}")
        elif has_character_sheet:
            mappings.append(f"{tag} 3-chunk dummy = {t_lbl} (match Attachment 2 character sheet)")
        else:
            mappings.append(f"{tag} 3-chunk dummy = {t_lbl}")
    mapping_clause = f" Color-to-subject mapping: {'; '.join(mappings)}." if mappings else ""
    species_clause = (
        "Replace every dummy marker with smooth matte cream-white vinyl 2.5D characters with bold 2D charcoal ink eyes/mouth and woven fabric clothing"
        if style_profile == "expressive_25d_v8"
        else "Replace every dummy marker with articulated matte-white porcelain figures with smooth featureless oval porcelain heads and woven fabric clothing"
    )
    return (
        "Vertical 9:16 full-bleed cinematic miniature diorama photograph. "
        "Follow camera angle, lens perspective, and 3D spatial placement strictly from Attachment 1 "
        "(3D blockout previs; simple colored 3-chunk dummies and boxes are position markers ONLY — "
        f"do NOT copy blocky geometry or solid marker colors). {species_clause}.{mapping_clause}"
    )


def _clean_sb(text: Any) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def still_prefix(aspect: str = FLOW_ASPECT_SHORTS) -> str:
    orient = "vertical" if aspect == "9:16" else "horizontal"
    return f"Generate a single {aspect} {orient} still photograph (one frozen instant, not a video):"


def cast_lock_entries(plan: dict[str, Any]) -> list[dict[str, str]]:
    cast = plan.get("cast") if isinstance(plan.get("cast"), dict) else {}
    wardrobe = cast.get("wardrobe") if isinstance(cast.get("wardrobe"), dict) else {}
    out: list[dict[str, str]] = []
    for key, look in wardrobe.items():
        if _clean_sb(look):
            out.append({"id": str(key), "look": _clean_sb(look)})
    if not out:
        skip_meta = {"wardrobe", "style", "cast_style", "notes", "cranium", "count", "profile"}
        ordered_keys: list[str] = ["subject"] if "subject" in cast else []
        for k in cast.keys():
            ks = str(k)
            if ks not in skip_meta and ks not in ordered_keys:
                ordered_keys.append(ks)
        for ks in ordered_keys:
            val = cast.get(ks)
            if isinstance(val, str) and _clean_sb(val):
                out.append({"id": ks, "look": _clean_sb(val)})
    return out


def cast_for_shot(plan: dict[str, Any], role: str | None) -> list[dict[str, str]]:
    entries = cast_lock_entries(plan)
    if not role:
        return entries
    shots = plan.get("shots") if isinstance(plan.get("shots"), dict) else {}
    shot = shots.get(role) if isinstance(shots.get(role), dict) else {}
    if isinstance(shot.get("cast"), list) and shot["cast"]:
        keep = {str(k) for k in shot["cast"]}
        return [e for e in entries if e["id"] in keep] or entries[:1]
    return entries[:1]


def cast_lock_sentence(plan: dict[str, Any], max_entries: int = 4, role: str | None = None) -> str:
    entries = cast_for_shot(plan, role)[:max_entries]
    if not entries:
        return "Every person is an articulated matte-white porcelain mannequin."
    body = "; ".join(f"{e['id'].replace('_', ' ')} in {e['look']}" for e in entries)
    return f"Every person is an articulated matte-white porcelain mannequin, same design in every shot: {body}."


def key_visual_for_scene(plan: dict[str, Any], scene_id: Any) -> dict[str, Any] | None:
    for m in plan.get("must_have_scenes") or []:
        if isinstance(m, dict) and str(m.get("id")) == str(scene_id) and isinstance(m.get("key_visual"), dict):
            return m["key_visual"]
    return None


def key_visual_tokens_ok(text: str, key_visual: dict[str, Any]) -> list[str]:
    low = str(text or "").lower()
    missing = []
    for group in key_visual.get("must_show") or []:
        alts = [a.strip().lower() for a in str(group).split("|") if a.strip()]
        if alts and not any(re.search(rf"\b{re.escape(a)}\b", low) for a in alts):
            missing.append(str(group))
    return missing


def key_visual_clip_numbers(plan: dict[str, Any], clips: list[dict[str, Any]]) -> dict[str, list[int]]:
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


def still_frame_prompt(
    plan: dict[str, Any],
    role: str,
    which: str = "start",
    aspect: str = FLOW_ASPECT_SHORTS,
    fallback_scene: str = "",
) -> str:
    body = _clean_sb(fallback_scene or plan.get("real_environment") or "clean sunlit architectural studio scene")
    if not body.endswith("."):
        body += "."
    return _clean_sb(
        f"{still_prefix(aspect)} {body} {cast_lock_sentence(plan, role=role)} "
        "Razor-sharp focus, bright even documentary light, no real human faces, no text, no watermark."
    )
