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


def validate_cold_open_v7(lines: list[str]) -> list[str]:
    """
    R57-H2 Schema v7 3-sentence cold-open (approved HM Plan B structure):
      S1 myth-flip / paradox shock, <= DIORAMA_V7_COLD_OPEN_S1_MAX_WORDS words, ends with '!'  (rush gear)
      S2 contrast opening with Yet/But/..., <= DIORAMA_V7_COLD_OPEN_S2_MAX_WORDS words         (rush gear)
      S3 'This is the true story of <case>.' case stamp                                       (stamp gear)
    """
    from pipeline.config import (
        DIORAMA_COLD_OPEN_S3_BANK,
        DIORAMA_V7_COLD_OPEN_CASE_STAMP_PREFIX,
        DIORAMA_V7_COLD_OPEN_S1_MAX_WORDS,
        DIORAMA_V7_COLD_OPEN_S2_MAX_WORDS,
        DIORAMA_V7_COLD_OPEN_S2_PREFIXES,
    )

    issues: list[str] = []
    if len(lines) < 3:
        return ["[cold_open_v7] script needs >= 3 sentences for the S1 hook / S2 contrast / S3 case stamp cold-open (R57-H2)"]

    def _strip(s: str) -> str:
        return re.sub(r"^[\"'“”‘’\s]+", "", str(s or "")).strip()

    s1, s2, s3 = (_strip(x) for x in lines[:3])
    n1, n2 = len(s1.split()), len(s2.split())
    if n1 > DIORAMA_V7_COLD_OPEN_S1_MAX_WORDS:
        issues.append(f"[cold_open_v7] S1 hook has {n1} words > {DIORAMA_V7_COLD_OPEN_S1_MAX_WORDS} (R57-H2)")
    if not s1.endswith("!"):
        issues.append(f"[cold_open_v7] S1 hook must end with '!' (myth-flip / paradox shock, rush gear): '{s1[:70]}' (R57-H2)")
    if n2 > DIORAMA_V7_COLD_OPEN_S2_MAX_WORDS:
        issues.append(f"[cold_open_v7] S2 contrast has {n2} words > {DIORAMA_V7_COLD_OPEN_S2_MAX_WORDS} (R57-H2)")
    if not s2.lower().startswith(DIORAMA_V7_COLD_OPEN_S2_PREFIXES):
        issues.append(
            f"[cold_open_v7] S2 must open with a contrast word {DIORAMA_V7_COLD_OPEN_S2_PREFIXES}: '{s2[:70]}' (R57-H2)"
        )
    stamp_prefix = DIORAMA_V7_COLD_OPEN_CASE_STAMP_PREFIX.strip().lower()
    valid_prefixes = tuple(
        dict.fromkeys([stamp_prefix] + [p.strip().lower() for p in DIORAMA_COLD_OPEN_S3_BANK if p.strip()])
    )
    s3_core = re.sub(r"[.!?\s]+$", "", s3.lower())
    matched_prefix = next((pref for pref in valid_prefixes if s3_core.startswith(pref)), None)
    if matched_prefix is None:
        issues.append(
            f"[cold_open_v7] S3 must be the case stamp '{stamp_prefix.capitalize()} <case>.' "
            f"(or a registered DIORAMA_COLD_OPEN_S3_BANK opener): '{s3[:70]}' (R57-H2)"
        )
    elif len(s3_core[len(matched_prefix) :].strip()) < 2:
        issues.append(
            f"[cold_open_v7] S3 case stamp must name the case after '{matched_prefix}' (R57-H2)"
        )
    return issues


def _word_ngrams(lines: list[str], n: int = 4) -> set[tuple[str, ...]]:
    toks = re.findall(r"[a-z0-9']+", " ".join(str(x) for x in lines).lower())
    if len(toks) < n:
        return set()
    return {tuple(toks[i : i + n]) for i in range(len(toks) - n + 1)}


def compute_4gram_jaccard(lines_a: list[str], lines_b: list[str]) -> float:
    """Computes word-level 4-gram Jaccard similarity between two scripts (`0.0..1.0`)."""
    ga = _word_ngrams(lines_a, 4)
    gb = _word_ngrams(lines_b, 4)
    if not ga or not gb:
        return 0.0
    return float(len(ga & gb)) / float(len(ga | gb))


def validate_anti_clone_uniqueness(
    lines: list[str],
    adjacent_scripts: list[list[str]] | None = None,
) -> list[str]:
    """
    YPP Anti-Clone Uniqueness Gate (`[US-06]`):
      - Rejects reuse of identical S3 case-stamp opener or final takeaway bridge within `DIORAMA_ADJACENT_OPENER_WINDOW` (4) episodes.
      - Enforces word 4-gram Jaccard `< DIORAMA_MAX_4GRAM_JACCARD` (`0.08`) against adjacent episodes.
    """
    if not lines or not adjacent_scripts:
        return []
    from pipeline.config import (
        DIORAMA_ADJACENT_OPENER_WINDOW,
        DIORAMA_COLD_OPEN_S3_BANK,
        DIORAMA_MAX_4GRAM_JACCARD,
        DIORAMA_TAKEAWAY_BRIDGE_BANK,
    )

    issues: list[str] = []
    window = [sc for sc in adjacent_scripts[:DIORAMA_ADJACENT_OPENER_WINDOW] if sc]
    if not window:
        return []

    s3_low = lines[2].strip().lower() if len(lines) >= 3 else ""
    cur_s3_pref = next((p.strip().lower() for p in DIORAMA_COLD_OPEN_S3_BANK if s3_low.startswith(p.strip().lower())), "")
    last_low = lines[-1].strip().lower()
    cur_end_pref = next((p.strip().lower() for p in DIORAMA_TAKEAWAY_BRIDGE_BANK if last_low.startswith(p.strip().lower())), "")

    for idx_adj, adj in enumerate(window, start=1):
        jac = compute_4gram_jaccard(lines, adj)
        if jac >= DIORAMA_MAX_4GRAM_JACCARD:
            issues.append(
                f"[anti_clone] 4-gram Jaccard {jac:.3f} >= {DIORAMA_MAX_4GRAM_JACCARD} vs adjacent episode #{idx_adj} (R57-C)"
            )
        if cur_s3_pref and len(adj) >= 3:
            adj_s3 = adj[2].strip().lower()
            if adj_s3.startswith(cur_s3_pref):
                issues.append(
                    f"[anti_clone] S3 case-stamp opener '{cur_s3_pref}' reused within adjacent {DIORAMA_ADJACENT_OPENER_WINDOW}-episode window (#{idx_adj}) (R57-H2)"
                )
        if cur_end_pref and adj:
            adj_last = adj[-1].strip().lower()
            if adj_last.startswith(cur_end_pref):
                issues.append(
                    f"[anti_clone] final takeaway bridge '{cur_end_pref}' reused within adjacent {DIORAMA_ADJACENT_OPENER_WINDOW}-episode window (#{idx_adj}) (R57-C)"
                )
    return issues


def validate_takeaway_bridge_grammar(sentence: str) -> list[str]:
    """
    Rejects mechanical bridge-prefix splices on the final takeaway sentence where a
    bridge from `DIORAMA_TAKEAWAY_BRIDGE_BANK` is glued onto an incompatible clause:
      - duplicate spliced phrases (`your brain your brain`, `next time next time`)
      - `so the next time ...` without a temporal `you/we/... , <main clause>` comma boundary
      - `every human brain shares ...` or `your own brain still carries ...` followed by a bare
        independent clause instead of a noun-phrase determiner (`that/this/the/one/two/three/a/an`)
      - `and that is how your brain ...` followed by a new clause subject (`your brain`, `ethics`,
        `smart timing`, `matching design`, `people`, `you`, `we`) instead of a predicate verb
      - `that biological lesson explains ...` without `why/how/what/that` or a noun determiner
      - double-preposition / double-subordinator splices (`that is why whenever`, `in your own life, in daily`)
    """
    issues: list[str] = []
    clean = re.sub(r"^[\"'“”‘’\s]+", "", str(sentence or "")).strip()
    low = clean.lower()
    if not low:
        return issues

    if re.search(r"\b(your brain|that means|next time|in daily life)\s+\1\b", low):
        issues.append(f"[hooks_grammar] duplicate spliced phrase in takeaway sentence: '{clean}'")
    if re.search(
        r"^(?:which is why|and that is why|which proves)\s+(?:whenever|next time|so the next time)\b",
        low,
    ):
        issues.append(f"[hooks_grammar] double-subordinator splice in takeaway sentence: '{clean}'")

    if low.startswith("so the next time "):
        rest = low[len("so the next time ") :].strip()
        if "," not in rest or not re.match(
            r"^(?:you|we|someone|anyone|a\b|an\b|your\s+(?:phone|alarm|mind|eyes|ears|hand|hands|heart|friends|boss|kid|child|voice|feet|legs|body))\b",
            rest,
        ):
            issues.append(
                f"[hooks_grammar] 'So the next time ...' requires 'you/your <noun> ..., <main clause>' structure: '{clean}'"
            )
    elif low.startswith(("every human brain shares ", "your own brain still carries ")):
        pref = "every human brain shares " if low.startswith("every human brain shares ") else "your own brain still carries "
        rest = low[len(pref) :].strip()
        has_det = bool(re.match(r"^(?:that|this|the|one|two|three|a|an|both|same)\b", rest))
        has_finite_clause = bool(
            re.search(
                r"\b(?:is|are|was|were|has|have|had|can|cannot|could|will|would|does|do|did|you|your|we|they|"
                r"depends|shines|split|splits|unlocks|quiet|quiets|wires|beats|tracks|tags|builds|speaks|works)\b",
                rest,
            )
        )
        if not has_det and (has_finite_clause or len(rest.split()) > 5):
            issues.append(
                f"[hooks_grammar] '{pref.strip()}' requires a noun-phrase object ('this/that/one ...'), got bare clause: '{clean}'"
            )
    elif low.startswith("and that is how your brain "):
        rest = low[len("and that is how your brain ") :].strip()
        if re.match(
            r"^(?:your\s+brain|ethics|smart\s+timing|matching\s+design|human|people|crowds|we|you|small|tiny|quiet\s+pauses|hiding|stepping|resetting)\b",
            rest,
        ):
            issues.append(
                f"[hooks_grammar] 'And that is how your brain ...' must be followed by a verb phrase, not a new clause subject: '{clean}'"
            )
    elif low.startswith("that biological lesson explains "):
        rest = low[len("that biological lesson explains ") :].strip()
        if not re.match(r"^(?:why|how|what|where|when|that|the|this|one)\b", rest):
            issues.append(
                f"[hooks_grammar] 'That biological lesson explains ...' requires 'why/how/that' or noun object: '{clean}'"
            )
    return issues


_PRE_R65_ASSEMBLED_DOSSIERS: frozenset[str] = frozenset(
    {
        "phineas_gage_iron_rod",
        "patient_hm_hippocampus",
        "ramachandran_phantom_limb_mirror",
        "alien_hand_syndrome",
        "milgram_obedience_shock",
        "hippocampal_memory_prosthesis",
        "clive_wearing_seven_second_mind",
        "invisible_gorilla_attention",
    }
)


def validate_thumbnail_block_v7(
    plan: dict[str, Any] | None,
    script_doc: dict[str, Any] | None = None,
) -> list[str]:
    """
    R65 Schema v7 thumbnail & in-video cover frame contract:
      - `visual_plan.thumbnail` dict required with `hook_text` and `cover_sentence_index` in `1..3`
      - `hook_text` passes `TQ7` lexical rules (`<= THUMB_HOOK_MAX_WORDS` words, `<= THUMB_HOOK_MAX_CHARS` chars,
        uppercase, non-TODO, and not a word-for-word prefix of `title`)
      - `chapter_headlines` (or `top_callouts`) contains an entry at `cover_sentence_index` matching `hook_text`
    """
    from pipeline.thumbnail_studio import validate_hook_lexical

    plan = plan or {}
    script_doc = script_doc or {}
    thumb = plan.get("thumbnail")
    if not isinstance(thumb, dict) or not thumb:
        return ["[thumbnail_v7] visual_plan.thumbnail block is missing (need hook_text + cover_sentence_index in 1..3) (R65)"]

    issues: list[str] = []
    hook_text = str(thumb.get("hook_text") or "").strip()
    if not hook_text or hook_text.upper() == "TODO":
        issues.append("[thumbnail_v7] visual_plan.thumbnail.hook_text must be hand-authored (not empty or TODO) (R65)")
    else:
        title = str(script_doc.get("title") or plan.get("title") or "").strip()
        for lex_err in validate_hook_lexical(hook_text, title=title):
            issues.append(f"[thumbnail_v7] hook_text '{hook_text}' violates TQ7 ({lex_err}) (R65)")

    cover_idx = thumb.get("cover_sentence_index")
    if not isinstance(cover_idx, int) or isinstance(cover_idx, bool) or not (1 <= cover_idx <= 3):
        issues.append(
            f"[thumbnail_v7] cover_sentence_index must be an integer in 1..3 (cold-open), got {cover_idx!r} (R65)"
        )
    elif hook_text and hook_text.upper() != "TODO":
        headlines = [
            h for h in (list(plan.get("chapter_headlines") or []) + list(plan.get("top_callouts") or []))
            if isinstance(h, dict) and int(h.get("sentence_index") or 0) == cover_idx
        ]
        if not any(str(h.get("text") or "").strip().upper() == hook_text.upper() for h in headlines):
            issues.append(
                f"[thumbnail_v7] chapter_headlines must include text '{hook_text.upper()}' at "
                f"sentence_index={cover_idx} so the in-video cover frame matches the thumbnail hook (R65)"
            )
    return issues


_CHRONOMETER_PROP_RE = re.compile(
    r"\b(?:stopwatch(?:es)?|(?:(?:[a-z0-9]+-)*[a-z0-9]+\s+)?timers?|sandglass(?:es)?|hourglass(?:es)?|pocket\s+watch(?:es)?|wrist\s*watch(?:es)?|(?:wall|alarm|desk|table|mantel|pendulum|analog|digital|flip)\s+clocks?|interval\s+chimes?)\b",
    flags=re.IGNORECASE,
)
_LOW_IMPACT_SCALE_FILLER_RE = re.compile(
    r"\b(?:measuring\s+tapes?|tape\s+measures?|yardsticks?|dollhouses?|postage\s+stamps?|dioramas?|miniature\s+(?:wooden\s+)?(?:rooms?|room\s+bays?|houses?|neighborhoods?|stations?|cities|towns?|villages?|streets?|booths?|buildings?)|five\s+identical\s+miniature|(?:giant|oversized)\s+film\s+reels?|row\s+of\s+empty\s+(?:wooden\s+)?chairs?|empty\s+wooden\s+chairs?\s+in\s+a\s+row)\b",
    flags=re.IGNORECASE,
)


def validate_substantive_visual_relevance(
    plan: dict[str, Any] | None,
    lines: list[str],
    clips: list[dict[str, Any]],
) -> list[str]:
    """
    R66.4 Balanced Documentary Pacing & Substantive Visual Relevance Gate for active `porcelain_cinematic_v7` episodes:
      - Clip count in [PORCELAIN_V7_TARGET_CLIP_MIN (45), PORCELAIN_V7_TARGET_CLIP_MAX (52)] on full episodes
        (~46-48 cuts, ~3.0-3.2s avg; blocks both <=42 stagnant holds and 60+ hyper-cut flash builds).
      - Primary clip hold span <= PORCELAIN_V7_MAX_HOLD_SENTENCES (2) (blocks 3+ sentence stagnant holds;
        break longer room/brain moments with same-scene multi-angle coverage).
      - porcelain_literal_analogy count <= PORCELAIN_V7_LITERAL_ANALOGY_MAX_CLIPS (2).
      - Bans stopwatch / kitchen-timer / pocket-watch / wall-clock / measuring-tape / dollhouse / postage-stamp
        filler props unless allow_chronometer_apparatus=True on the plan.
      - Validates explicit split_comparisons left_clip_index / right_clip_index bindings.
    """
    from pipeline.config import (
        DIORAMA_SENTENCE_COUNT_MIN,
        PORCELAIN_V7_LITERAL_ANALOGY_MAX_CLIPS,
        PORCELAIN_V7_MAX_HOLD_SENTENCES,
        PORCELAIN_V7_TARGET_CLIP_MAX,
        PORCELAIN_V7_TARGET_CLIP_MIN,
    )

    issues: list[str] = []
    plan = plan or {}
    clips = clips or []
    raw_clips = plan.get("clips") if isinstance(plan.get("clips"), list) else []

    n_clips = len(raw_clips) if raw_clips else len(clips)
    if n_clips > PORCELAIN_V7_TARGET_CLIP_MAX:
        issues.append(
            f"[pacing_v7] clip count {n_clips} exceeds balanced documentary ceiling {PORCELAIN_V7_TARGET_CLIP_MAX} "
            "— merge adjacent short beats into 2-sentence holds (R66.4)"
        )
    if len(lines or []) >= DIORAMA_SENTENCE_COUNT_MIN and n_clips < PORCELAIN_V7_TARGET_CLIP_MIN:
        issues.append(
            f"[pacing_v7] clip count {n_clips} below balanced documentary floor {PORCELAIN_V7_TARGET_CLIP_MIN} "
            "— split stagnant >4.3s holds with same-scene multi-angle coverage (R66.4)"
        )

    total_len = max(len(clips), len(raw_clips))
    merged_clips = [
        {
            **(clips[i] if i < len(clips) and isinstance(clips[i], dict) else {}),
            **(raw_clips[i] if i < len(raw_clips) and isinstance(raw_clips[i], dict) else {}),
        }
        for i in range(total_len)
    ]

    lit_cnt = sum(1 for c in merged_clips if str(c.get("grammar") or "") == "porcelain_literal_analogy")
    if lit_cnt > PORCELAIN_V7_LITERAL_ANALOGY_MAX_CLIPS:
        issues.append(
            f"[analogy_cap_v7] {lit_cnt} clips use porcelain_literal_analogy > max {PORCELAIN_V7_LITERAL_ANALOGY_MAX_CLIPS} "
            "— keep camera inside the case room or 3D brain unless a concrete physical scale analogy demands it (R57/R66.4)"
        )

    allow_chrono = bool(plan.get("allow_chronometer_apparatus"))
    for idx, c in enumerate(merged_clips, start=1):
        clip_id = c.get("clip_number") or c.get("clip_index") or idx
        c_role = str(c.get("cut_role") or "").strip().lower()
        if c_role not in ("outro", "split_right", "split_bottom"):
            s0 = c.get("sentence_index")
            if isinstance(s0, int) and s0 >= 1:
                hold_explicit = int(c.get("hold_sentences") or 1)
                s1 = max(s0, int(c.get("end_sentence_index") or (s0 + hold_explicit - 1)))
                hold_span = max(hold_explicit, s1 - s0 + 1)
                if hold_span > PORCELAIN_V7_MAX_HOLD_SENTENCES:
                    issues.append(
                        f"clip {clip_id}: [pacing_v7] multi-sentence hold spans {hold_span} sentences "
                        f"({s0}..{s1}) > max {PORCELAIN_V7_MAX_HOLD_SENTENCES} — split with same-scene multi-angle coverage (R66.4)"
                    )
        sc_txt = " ".join(
            str(c.get(k) or "")
            for k in (
                "scene",
                "prompt",
                "action",
                "environment",
                "attire_and_hands",
                "prop_action",
                "consequence",
                "structure",
                "internal_mechanism",
                "analogy_world",
                "comparison_action",
                "analogy_scene",
                "analogy_object",
            )
            if c.get(k)
        )
        if not allow_chrono:
            m_chrono = _CHRONOMETER_PROP_RE.search(sc_txt)
            if m_chrono:
                issues.append(
                    f"clip {clip_id}: [filler_ban_v7] low-impact chronometer filler prop '{m_chrono.group(0)}' banned "
                    "unless allow_chronometer_apparatus=True (R66.4)"
                )
        m_scale = _LOW_IMPACT_SCALE_FILLER_RE.search(sc_txt)
        if m_scale:
            issues.append(
                f"clip {clip_id}: [filler_ban_v7] scale-breaking / low-impact filler prop '{m_scale.group(0)}' banned (R66.4)"
            )

    for sp in plan.get("split_comparisons") or []:
        if not isinstance(sp, dict):
            continue
        s_idx = int(sp.get("sentence_index") or 0)
        left_idx = sp.get("left_clip_index") or sp.get("top_clip_index")
        right_idx = sp.get("right_clip_index") or sp.get("bottom_clip_index")
        if left_idx is not None:
            li = int(left_idx)
            if not (1 <= li <= len(merged_clips)):
                issues.append(f"[split_v7] split_comparisons sentence {s_idx} left_clip_index={li} out of range 1..{len(merged_clips)}")
            else:
                lc = merged_clips[li - 1]
                l_role = str(lc.get("cut_role") or "").strip().lower()
                s0 = int(lc.get("sentence_index") or 0)
                s1 = max(s0, int(lc.get("end_sentence_index") or s0))
                if l_role in ("outro", "split_right", "split_bottom") or not (s0 <= s_idx <= s1):
                    issues.append(
                        f"[split_v7] split_comparisons sentence {s_idx} left_clip_index={li} does not cover sentence {s_idx} "
                        f"as a primary clip (got range {s0}..{s1}, role='{l_role}') (R63/R66.4)"
                    )
        if right_idx is not None:
            ri = int(right_idx)
            if not (1 <= ri <= len(merged_clips)):
                issues.append(f"[split_v7] split_comparisons sentence {s_idx} right_clip_index={ri} out of range 1..{len(merged_clips)}")
    return issues


def validate_scene_state_continuity(
    plan: dict[str, Any] | None,
    clips: list[dict[str, Any]],
) -> list[str]:
    """
    R66.4 / R67 Spatial & Entrance Continuity Ledger Gate (`scene_state`):
      - Blocks duplicate-actor entrances (`entering_cast` overlapping `present_cast_start` or start reference `present_cast`).
      - Blocks simultaneous start+end scene reference images on entrance/exit transitions.
      - Blocks unauthorized ghost cast in bound reference images (`ref_spec.present_cast` must be subset of `present_cast_start` / `present_cast_end`).
      - Blocks cross-location reference leaks (`ref_spec.location_id != clip.location_id`) and `ref_brain_master` on room clips.
      - Enforces sequential cross-clip room state continuity across consecutive clips in the same `location_id`
        (departed actors cannot reappear without `entering_cast` or `scene_reset`/`protocol_phase_jump`, and
        actors already inside `location_id` cannot re-enter through the door without exiting first).
    """
    issues: list[str] = []
    plan = plan or {}
    clips = clips or []
    raw_clips = plan.get("clips") if isinstance(plan.get("clips"), list) else []
    total_len = max(len(clips), len(raw_clips))
    merged_clips = [
        {
            **(clips[i] if i < len(clips) and isinstance(clips[i], dict) else {}),
            **(raw_clips[i] if i < len(raw_clips) and isinstance(raw_clips[i], dict) else {}),
        }
        for i in range(total_len)
    ]

    ref_map: dict[str, dict[str, Any]] = {}
    for rspec in list(plan.get("reference_anchors") or []) + list(plan.get("reference_specs") or []):
        if isinstance(rspec, dict):
            rid = str(rspec.get("ref_id") or "").strip()
            fname = str(rspec.get("filename") or "").strip()
            if rid:
                ref_map[rid] = rspec
                ref_map[f"{rid}.png"] = rspec
            if fname:
                ref_map[fname] = rspec
                if fname.endswith(".png"):
                    ref_map[fname[:-4]] = rspec

    ledger_required = bool(
        plan.get("require_scene_state_ledger")
        or plan.get("source_edl")
        or any(isinstance(mc.get("scene_state"), dict) or mc.get("source_shot_id") for mc in merged_clips)
    )
    strict_room_continuity = bool(plan.get("strict_room_continuity") or plan.get("source_edl"))
    loc_state: dict[str, dict[str, Any]] = {}

    def _norm_rid(val: Any) -> str:
        s = str(val or "").strip().replace("\\", "/")
        if not s:
            return ""
        base = s.rsplit("/", 1)[-1]
        return base[:-4] if base.lower().endswith(".png") else base

    for idx, mc in enumerate(merged_clips, start=1):
        clip_id = mc.get("clip_number") or mc.get("clip_index") or idx
        g_name = str(mc.get("grammar") or "")
        c_role = str(mc.get("cut_role") or "").strip().lower()
        is_brain_or_outro = (
            g_name in (
                "porcelain_living_brain",
                "porcelain_data_sculpture",
                "lowpoly_living_brain",
                "lowpoly_matte_brain",
                "lowpoly_data_sculpture",
                "arch_brain_maquette",
                "frosted_crystal_specimen",
            )
            or bool(mc.get("brain_mode"))
            or c_role == "outro"
        )

        start_rids: list[str] = []
        end_rids: list[str] = []
        for k_s in ("reference_image", "start_reference_image"):
            nr = _norm_rid(mc.get(k_s))
            if nr and nr not in start_rids:
                start_rids.append(nr)
        for item_r in mc.get("reference_images") or []:
            nr = _norm_rid(item_r)
            if nr and nr not in start_rids:
                start_rids.append(nr)
        nr_end = _norm_rid(mc.get("end_reference_image"))
        if nr_end:
            end_rids.append(nr_end)

        if not is_brain_or_outro:
            for rid in start_rids + end_rids:
                if "brain_master" in rid:
                    issues.append(
                        f"clip {clip_id}: [scene_state_v7] non-brain clip binds cutaway brain reference '{rid}' "
                        "(causes severed mannequin head prop contamination) (R66.4/R67)"
                    )

        st = mc.get("scene_state")
        if ledger_required and not is_brain_or_outro and g_name != "porcelain_literal_analogy":
            if not isinstance(st, dict):
                issues.append(
                    f"clip {clip_id}: [scene_state_v7] room/cast clip missing scene_state ledger dict "
                    "(location_id, present_cast_start, entering_cast, exiting_cast, present_cast_end) (R66.4/R67)"
                )
                continue

        if not isinstance(st, dict):
            continue

        loc_id = str(st.get("location_id") or mc.get("location_id") or "").strip()
        p_start = [str(x).strip() for x in (st.get("present_cast_start") or []) if str(x).strip()]
        entering = [str(x).strip() for x in (st.get("entering_cast") or []) if str(x).strip()]
        exiting = [str(x).strip() for x in (st.get("exiting_cast") or []) if str(x).strip()]
        expected_end = (set(p_start) | set(entering)) - set(exiting)
        p_end = (
            [str(x).strip() for x in (st.get("present_cast_end") or []) if str(x).strip()]
            if "present_cast_end" in st
            else sorted(expected_end)
        )

        overlap_enter = sorted(set(entering) & set(p_start))
        if overlap_enter:
            issues.append(
                f"clip {clip_id}: [scene_state_v7] entering_cast {overlap_enter} already in present_cast_start {p_start} "
                "(causes duplicate-actor entrance) (R66.4/R67)"
            )

        missing_exit = sorted(set(exiting) - (set(p_start) | set(entering)))
        if missing_exit:
            issues.append(
                f"clip {clip_id}: [scene_state_v7] exiting_cast {missing_exit} not present in room {p_start} (R66.4/R67)"
            )

        if "present_cast_end" in st and set(p_end) != expected_end:
            issues.append(
                f"clip {clip_id}: [scene_state_v7] present_cast_end {sorted(p_end)} != "
                f"(present_cast_start | entering_cast) - exiting_cast {sorted(expected_end)} (R66.4/R67)"
            )

        if loc_id and not is_brain_or_outro and c_role not in ("split_right", "split_bottom"):
            has_phase_reset = bool(st.get("scene_reset") or st.get("protocol_phase_jump"))
            prev_loc = loc_state.get(loc_id)
            if prev_loc is not None and not has_phase_reset:
                ghost_returns = sorted(set(p_start) & prev_loc["departed"])
                if ghost_returns:
                    issues.append(
                        f"clip {clip_id}: [scene_state_v7] departed cast {ghost_returns} reappeared in "
                        f"present_cast_start {p_start} at '{loc_id}' without entering_cast or scene_reset/protocol_phase_jump "
                        f"(after exiting in clip {prev_loc['last_exit_clip']}) (R66.4/R67)"
                    )
                dup_reentries = sorted(set(entering) & prev_loc["present_end"])
                if dup_reentries:
                    issues.append(
                        f"clip {clip_id}: [scene_state_v7] entering_cast {dup_reentries} was already inside '{loc_id}' "
                        f"at end of clip {prev_loc['prev_clip_id']} ({sorted(prev_loc['present_end'])}) without exiting or "
                        "scene_reset/protocol_phase_jump (R66.4/R67)"
                    )
                if (
                    strict_room_continuity
                    and g_name == "porcelain_fullbleed_world"
                    and prev_loc.get("prev_fullbleed_end") is not None
                    and not bool(st.get("camera_framing_subset"))
                    and set(p_start) != prev_loc["prev_fullbleed_end"]
                ):
                    issues.append(
                        f"clip {clip_id}: [scene_state_v7] sequential room occupancy mismatch at '{loc_id}': "
                        f"present_cast_start {sorted(p_start)} != previous fullbleed present_cast_end "
                        f"{sorted(prev_loc['prev_fullbleed_end'])} (clip {prev_loc['prev_fullbleed_clip']}) "
                        "— declare entering_cast/exiting_cast or protocol_phase_jump/scene_reset (R66.4/R67)"
                    )

            new_departed = (
                set(exiting)
                if (prev_loc is None or bool(st.get("scene_reset")))
                else ((prev_loc["departed"] - set(entering)) | set(exiting))
            )
            explicit_absent = {str(x).strip() for x in (st.get("absent_cast") or []) if str(x).strip()}
            new_departed |= (explicit_absent - set(p_end))
            loc_state[loc_id] = {
                "present_end": set(p_end),
                "departed": new_departed,
                "prev_clip_id": clip_id,
                "last_exit_clip": (clip_id if exiting else (prev_loc["last_exit_clip"] if prev_loc else clip_id)),
                "prev_fullbleed_end": (
                    set(p_end)
                    if g_name == "porcelain_fullbleed_world"
                    else (prev_loc.get("prev_fullbleed_end") if prev_loc and not has_phase_reset else None)
                ),
                "prev_fullbleed_clip": (
                    clip_id
                    if g_name == "porcelain_fullbleed_world"
                    else (prev_loc.get("prev_fullbleed_clip") if prev_loc and not has_phase_reset else None)
                ),
            }

        if entering or exiting:
            scene_refs = [
                r
                for r in (start_rids + end_rids)
                if not r.startswith("ref_cast")
                and str((ref_map.get(r) or {}).get("role") or "") not in ("character", "cast")
            ]
            if (start_rids and end_rids) or len(scene_refs) > 1:
                issues.append(
                    f"clip {clip_id}: [scene_state_v7] entrance/exit clip binds multiple scene keyframes {scene_refs} "
                    "(never combine start + end scene keyframes across an entrance or exit) (R66.4/R67)"
                )

        for rid in start_rids:
            rspec = ref_map.get(rid)
            if not isinstance(rspec, dict):
                continue
            r_loc = str(rspec.get("location_id") or "").strip()
            if r_loc and loc_id and r_loc != loc_id:
                issues.append(
                    f"clip {clip_id}: [scene_state_v7] start reference '{rid}' location_id='{r_loc}' != "
                    f"clip location_id='{loc_id}' (cross-location prop/room leak) (R66.4/R67)"
                )
            if rspec.get("present_cast") is not None:
                ref_cast = {str(x).strip() for x in (rspec.get("present_cast") or []) if str(x).strip()}
                unauthorized = sorted(ref_cast - set(p_start))
                if unauthorized:
                    issues.append(
                        f"clip {clip_id}: [scene_state_v7] start reference '{rid}' depicts {unauthorized} "
                        f"not in present_cast_start {p_start} (causes pre-seated duplicate or ghost stranger) (R66.4/R67)"
                    )

        for rid in end_rids:
            rspec = ref_map.get(rid)
            if not isinstance(rspec, dict):
                continue
            r_loc = str(rspec.get("location_id") or "").strip()
            if r_loc and loc_id and r_loc != loc_id:
                issues.append(
                    f"clip {clip_id}: [scene_state_v7] end reference '{rid}' location_id='{r_loc}' != "
                    f"clip location_id='{loc_id}' (cross-location prop/room leak) (R66.4/R67)"
                )
            if rspec.get("present_cast") is not None:
                ref_cast = {str(x).strip() for x in (rspec.get("present_cast") or []) if str(x).strip()}
                unauthorized_end = sorted(ref_cast - set(p_end))
                if unauthorized_end:
                    issues.append(
                        f"clip {clip_id}: [scene_state_v7] end reference '{rid}' depicts {unauthorized_end} "
                        f"not in present_cast_end {p_end} (causes ghost actor in reunion/exit) (R66.4/R67)"
                    )

    return issues


# ------------------------------------------------------------------------------
# Main gate (v5 + Schema v6 `neuro_diorama` R56-R61)
# ------------------------------------------------------------------------------
def validate_production_diorama_v6(
    plan: dict[str, Any] | None,
    narrations: list[str],
    clips: list[dict[str, Any]],
    script_doc: dict[str, Any] | None = None,
    adjacent_scripts: list[list[str]] | None = None,
) -> list[str]:
    """
    R61 pre-Flow production gate for Schema v6/v7 `neuro_diorama`:
      - R56/R63/R66: Zero-flesh Ghost-Lab / Low-Poly / Porcelain world, zero in-scene AI text, single-axis camera moves.
      - R57/R57-C: 6-Act structure, US English sentence/word budget (430-470w & <=13w/sent on `dynamic_us_v7`;
                   430-505w & <=18w/sent on legacy `dynamic_rush_v7`), rotating Anti-Clone transition banks,
                   100% [Number] -> [Immediate Everyday Analogy] pairing, Act 5 crisis episode, 100% en-US ASCII/Latin.
      - R15/R48/R49-T: Plain language FK grade (<= 5.5 on `dynamic_us_v7`, <= 8.0 legacy), glossed anatomy, TTS-safe spoken text.
    """
    from pipeline.config import (
        DIORAMA_ACT_COUNT,
        DIORAMA_BANNED_SLOGAN_OPENERS,
        DIORAMA_BANNED_WEAK_HOOK_PREFIXES,
        DIORAMA_CRISIS_BEAT_BANK,
        DIORAMA_CRYSTAL_SPECIMEN_MAX_RATIO,
        DIORAMA_EUREKA_REVEAL_BANK,
        DIORAMA_MECHANISM_PIVOT_BANK,
        DIORAMA_MIN_CONVERSATIONAL_QUESTIONS,
        DIORAMA_MOTIF_APPEARANCES_MAX,
        DIORAMA_MOTIF_APPEARANCES_MIN,
        DIORAMA_REQUIRE_SIGNATURE_HOOKS,
        DIORAMA_SENTENCE_COUNT_MAX,
        DIORAMA_SENTENCE_COUNT_MIN,
        DIORAMA_SENTENCE_WORDS_MAX,
        DIORAMA_TAKEAWAY_BRIDGE_BANK,
        DIORAMA_TARGET_CUT_MIN,
        DIORAMA_US_SENTENCE_WORDS_MAX,
        DIORAMA_US_WORD_COUNT_MAX,
        DIORAMA_V7_MAX_FK_GRADE,
        DIORAMA_V7_REQUIRE_COLD_OPEN,
        DIORAMA_V7_SENTENCE_WORDS_MAX,
        DIORAMA_V7_US_PROSODY_MODE,
        DIORAMA_WORD_COUNT_MAX,
        DIORAMA_WORD_COUNT_MIN,
        MICRO_SHORT_CUT_MAX,
        MICRO_SHORT_CUT_MIN,
        MICRO_SHORT_PROFILE,
        MICRO_SHORT_WORD_MAX,
        MICRO_SHORT_WORD_MIN,
        PRE_R66_FROZEN_PROJECT_PREFIXES,
        is_diorama_v7_plan,
        is_porcelain_v7_plan,
    )
    from pipeline.flow_prompt_builder import count_words, validate_diorama_v6_prompts
    from pipeline.plain_language import find_duplicate_analogy_idioms, validate_number_analogy_pairing

    issues: list[str] = []
    plan = plan or {}
    is_v7 = is_diorama_v7_plan(plan) or (isinstance(script_doc, dict) and is_diorama_v7_plan(script_doc))
    lines = [str(n).strip() for n in (narrations or []) if str(n).strip()]

    project_id = str((script_doc or {}).get("project_id") or plan.get("project_id") or "").strip()
    dossier_slug = str(plan.get("dossier") or (script_doc or {}).get("dossier") or "").strip()
    format_profile = str((script_doc or {}).get("format_profile") or plan.get("format_profile") or "").strip().lower()
    is_micro = format_profile == MICRO_SHORT_PROFILE
    prosody_mode = str((script_doc or {}).get("prosody_mode") or plan.get("prosody_mode") or "").strip().lower()

    # 1. R57 / R63 US English & 6-Act sentence/word budget ---------------------
    total_words = sum(count_words(s) for s in lines)
    is_frozen_gage_v7 = is_v7 and (
        project_id == "gage_diorama_v7_lowpoly"
        or (dossier_slug == "phineas_gage_iron_rod" and len(lines) == 56 and total_words == 535)
    )
    is_pre_r66_frozen = (
        is_frozen_gage_v7
        or dossier_slug in _PRE_R65_ASSEMBLED_DOSSIERS
        or (bool(project_id) and any(project_id.startswith(pref) for pref in PRE_R66_FROZEN_PROJECT_PREFIXES))
    )
    is_us_v7 = is_v7 and not is_pre_r66_frozen and (
        prosody_mode == DIORAMA_V7_US_PROSODY_MODE or bool(plan.get("us_anti_clone_v7"))
    )

    if is_micro:
        if not (10 <= len(lines) <= 18):
            issues.append(f"[micro_short_v7] sentence count {len(lines)} outside 10-18 (R63)")
        if not (MICRO_SHORT_WORD_MIN <= total_words <= MICRO_SHORT_WORD_MAX):
            issues.append(
                f"[micro_short_v7] total spoken words {total_words} outside {MICRO_SHORT_WORD_MIN}-{MICRO_SHORT_WORD_MAX} (R63)"
            )
    else:
        max_sents = DIORAMA_SENTENCE_COUNT_MAX
        if not (DIORAMA_SENTENCE_COUNT_MIN <= len(lines) <= max_sents):
            issues.append(
                f"[diorama_script] sentence count {len(lines)} outside {DIORAMA_SENTENCE_COUNT_MIN}-{max_sents} (R57)"
            )
        max_words = 535 if is_frozen_gage_v7 else (DIORAMA_US_WORD_COUNT_MAX if is_us_v7 else DIORAMA_WORD_COUNT_MAX)
        if not (DIORAMA_WORD_COUNT_MIN <= total_words <= max_words):
            issues.append(
                f"[diorama_script] total spoken words {total_words} outside {DIORAMA_WORD_COUNT_MIN}-{max_words} "
                "for poised 3-minute pacing (R57/R63)"
            )

    sent_words_max = (
        DIORAMA_US_SENTENCE_WORDS_MAX
        if (is_us_v7 or is_micro)
        else (DIORAMA_V7_SENTENCE_WORDS_MAX if is_v7 else DIORAMA_SENTENCE_WORDS_MAX)
    )
    for idx, s in enumerate(lines, start=1):
        wc = count_words(s)
        if wc > sent_words_max:
            issues.append(
                f"[diorama_script] sentence {idx} has {wc} words > max {sent_words_max}: '{s[:70]}' (R57/R57-C)"
            )
        if re.search(r"[\uac00-\ud7a3\u3040-\u30ff\u4e00-\u9fff]", s):
            issues.append(f"[en_us_lock] sentence {idx} contains non-English CJK/Korean characters (R36/R57)")

    if not is_micro and isinstance(script_doc, dict) and isinstance(script_doc.get("acts"), list):
        acts = script_doc["acts"]
        if len(acts) != DIORAMA_ACT_COUNT:
            issues.append(f"[diorama_script] script.acts must have {DIORAMA_ACT_COUNT} acts (got {len(acts)}) (R57)")

    if lines:
        s1_norm = re.sub(r"[^a-z\s,]", "", lines[0].lower()).strip()
        if any(op in s1_norm for op in DIORAMA_BANNED_SLOGAN_OPENERS):
            issues.append(
                "[diorama_script] sentence 1 uses a banned channel-slogan opener "
                "('University brain science, made simple.'); must open immediately with the event/paradox hook (R57)"
            )
        if is_v7:
            s1_low = re.sub(r"^[\"'“”‘’\s]+", "", lines[0]).lower()
            if any(s1_low.startswith(pref) for pref in DIORAMA_BANNED_WEAK_HOOK_PREFIXES):
                issues.append(
                    f"[hook_v7] sentence 1 starts with weak hypothetical opener {DIORAMA_BANNED_WEAK_HOOK_PREFIXES}: "
                    f"'{lines[0][:65]}' — open at 0.0s with concrete event/paradox shock (R57-H)"
                )
            if bool(plan.get("require_cold_open_v7", DIORAMA_V7_REQUIRE_COLD_OPEN)) and not is_frozen_gage_v7 and not is_micro:
                issues.extend(validate_cold_open_v7(lines))
            from pipeline.config import DIORAMA_V7_REQUIRE_THUMBNAIL_BLOCK

            has_thumb_block = "thumbnail" in plan
            explicit_req = plan.get("require_thumbnail_v7")
            if explicit_req is True or has_thumb_block or (
                explicit_req is None
                and DIORAMA_V7_REQUIRE_THUMBNAIL_BLOCK
                and not is_frozen_gage_v7
                and not is_micro
                and dossier_slug not in _PRE_R65_ASSEMBLED_DOSSIERS
            ):
                issues.extend(validate_thumbnail_block_v7(plan, script_doc=script_doc))
    for c_item in list(plan.get("top_callouts") or []) + list(plan.get("chapter_headlines") or []):
        if isinstance(c_item, dict):
            c_low = str(c_item.get("text") or "").lower()
            if "university neuroscience" in c_low or "made simple" in c_low or "all about brain" in c_low:
                issues.append(f"[diorama_script] headline/callout contains banned channel-slogan badge: '{c_item.get('text')}' (R57)")
    if bool(plan.get("require_signature_hooks", DIORAMA_REQUIRE_SIGNATURE_HOOKS)) and lines and not is_micro:
        full_low = " ".join(lines).lower()
        if is_v7 and not is_pre_r66_frozen:
            if not any(p.strip().lower() in full_low for p in DIORAMA_CRISIS_BEAT_BANK):
                issues.append("[hooks] missing crisis transition beat from DIORAMA_CRISIS_BEAT_BANK (R57)")
            if not any(p.strip().lower() in full_low for p in DIORAMA_MECHANISM_PIVOT_BANK):
                issues.append("[hooks] missing mechanism pivot phrase from DIORAMA_MECHANISM_PIVOT_BANK (R57)")
            if not any(p.strip().lower() in full_low for p in DIORAMA_EUREKA_REVEAL_BANK):
                issues.append("[hooks] missing breakthrough reveal phrase from DIORAMA_EUREKA_REVEAL_BANK (R57)")
            last_clean = re.sub(r"^[\"'“”‘’\s]+", "", lines[-1]).lower()
            if not any(last_clean.startswith(p.strip().lower()) for p in DIORAMA_TAKEAWAY_BRIDGE_BANK):
                issues.append("[hooks] final sentence must open with a takeaway bridge from DIORAMA_TAKEAWAY_BRIDGE_BANK (R57)")
            else:
                issues.extend(validate_takeaway_bridge_grammar(lines[-1]))
        else:
            if "here is what went wrong" not in full_low:
                issues.append("[hooks] missing R26 diagnostic opener 'Here is what went wrong.' (R57)")
            if "total nightmare" not in full_low:
                issues.append("[hooks] missing R24 crisis signature meme '...a total nightmare.' (R57)")
            if "instead of" not in full_low:
                issues.append("[hooks] missing R26 paradigm-flip pivot 'Instead of...' (R57)")
            if "completely stunned" not in full_low:
                issues.append("[hooks] missing R24 breakthrough signature meme 'The researchers were left completely stunned.' (R57)")
            if not lines[-1].lower().startswith(("which proves", "which is why")):
                issues.append("[hooks] final sentence must open with 'Which proves' or 'Which is why' (R26/R57)")
    if adjacent_scripts and not is_pre_r66_frozen:
        issues.extend(validate_anti_clone_uniqueness(lines, adjacent_scripts))
    if bool(plan.get("zero_clip_reuse", True)) and lines and clips:
        if is_v7:
            min_cuts = MICRO_SHORT_CUT_MIN if is_micro else DIORAMA_TARGET_CUT_MIN
            if len(clips) < min_cuts:
                issues.append(
                    f"[zero_reuse_v7] Schema v7 zero_clip_reuse=True requires >= {min_cuts} unique clips "
                    f"(got {len(clips)}) so dynamic long-take holds + rapid sub-cuts maintain >= {min_cuts} cuts (R63)"
                )
            if is_micro and len(clips) > MICRO_SHORT_CUT_MAX + 4:
                issues.append(
                    f"[micro_short_v7] clip count {len(clips)} exceeds micro-short ceiling {MICRO_SHORT_CUT_MAX + 4} (R63)"
                )
            covered_sentences: set[int] = set()
            for c in clips:
                if str(c.get("cut_role") or "").strip().lower() in ("outro", "split_right", "split_bottom"):
                    continue
                s0 = c.get("sentence_index")
                if isinstance(s0, int) and s0 >= 1:
                    s1 = max(s0, int(c.get("end_sentence_index") or s0))
                    for s_k in range(s0, s1 + 1):
                        covered_sentences.add(s_k)
            missing_s = [i for i in range(1, len(lines) + 1) if i not in covered_sentences]
            if missing_s:
                issues.append(f"[zero_reuse_v7] sentences missing clip/hold coverage: {missing_s[:10]} (R63)")
        else:
            if len(clips) < len(lines) + 1:
                issues.append(
                    f"[zero_reuse] zero_clip_reuse=True requires >= {len(lines) + 1} unique clips "
                    f"(>=1 per sentence + dedicated outro clip; got {len(clips)}) (R58)"
                )
            covered_sentences = {int(c["sentence_index"]) for c in clips if c.get("sentence_index") is not None}
            missing_s = [i for i in range(1, len(lines) + 1) if i not in covered_sentences]
            if missing_s:
                issues.append(f"[zero_reuse] sentences missing dedicated 1:1 clip binding: {missing_s[:10]} (R58)")

    if not str(plan.get("act5_climax_episode") or "").strip():
        issues.append("[diorama_script] visual_plan.act5_climax_episode is empty (Act 5 lab crisis required) (R57)")

    outro_lines = plan.get("outro_title_lines") if isinstance(plan.get("outro_title_lines"), list) else []
    if len([x for x in outro_lines if str(x).strip()]) < 2:
        issues.append("[diorama_script] visual_plan.outro_title_lines needs 2 uppercase English lines for the Act 6 tilt-up outro (R59)")

    # 2. R57 100% [Number] -> [Immediate Everyday Analogy] pairing -------------
    issues.extend(validate_number_analogy_pairing(lines))

    # 3. R56 / R63 / R66 Prompts, World Continuity & Filler Ban ----------------
    issues.extend(validate_diorama_v6_prompts(clips, plan=plan))
    if clips:
        if is_v7:
            # R63: Ban unrelated generic v6 filler motif props (water tumbler / brass beam scale) unless spoken
            for idx_f, c in enumerate(clips, start=1):
                sc_low = str(c.get("scene") or "").lower()
                s_idx = int(c.get("sentence_index") or 0)
                spoken_low = lines[s_idx - 1].lower() if 1 <= s_idx <= len(lines) else ""
                if ("water tumbler" in sc_low or "beam scale" in sc_low) and not (
                    "water" in spoken_low or "scale" in spoken_low
                ):
                    clip_id = c.get("clip_number") or c.get("clip_index") or idx_f
                    issues.append(
                        f"clip {clip_id}: [filler_ban_v7] unrelated generic 'water tumbler / beam scale' "
                        "filler prop banned in Schema v7 (R63)"
                    )
            # R63: Enforce A-B-A spatial location continuity (>= 2 location returns across non-adjacent clips)
            seen_locs: dict[str, int] = {}
            aba_returns = 0
            for idx_c, c in enumerate(clips):
                loc = str(c.get("location_id") or "").strip()
                if not loc:
                    continue
                if loc in seen_locs and idx_c - seen_locs[loc] >= 2:
                    aba_returns += 1
                seen_locs[loc] = idx_c
            if aba_returns < 2:
                issues.append(
                    f"[spatial_aba_v7] Schema v7 requires >= 2 A-B-A spatial location_id returns across clips "
                    f"(found {aba_returns}) (R63)"
                )
            if is_porcelain_v7_plan(plan, *(clips or []), script_doc) and not is_pre_r66_frozen and not is_micro:
                issues.extend(validate_substantive_visual_relevance(plan, lines, clips))
                issues.extend(validate_scene_state_continuity(plan, clips))
        else:
            crystal_cnt = sum(1 for c in clips if str(c.get("grammar")) == "frosted_crystal_specimen")
            max_crystal = int(len(clips) * DIORAMA_CRYSTAL_SPECIMEN_MAX_RATIO + 1e-6)
            if crystal_cnt > max_crystal:
                issues.append(
                    f"[crystal] {crystal_cnt}/{len(clips)} clips use frosted_crystal_specimen > max {max_crystal} "
                    f"({int(DIORAMA_CRYSTAL_SPECIMEN_MAX_RATIO * 100)}% ceiling; >=80% must be Ghost-Lab dioramas) (R56)"
                )
            motif = plan.get("motif_prop") if isinstance(plan.get("motif_prop"), dict) else {}
            if not str(motif.get("object") or "").strip():
                issues.append("[motif] visual_plan.motif_prop.object is empty (recurring analog gauge required) (R56)")
            tokens = [str(t).lower() for t in (motif.get("tokens") or []) if str(t).strip()]
            motif_hits = 0
            for c in clips:
                sc_low = str(c.get("scene") or "").lower()
                if c.get("motif_present") or str(c.get("grammar")) == "recurring_gauge_motif" or (
                    tokens and any(tok in sc_low for tok in tokens)
                ):
                    motif_hits += 1
            if not (DIORAMA_MOTIF_APPEARANCES_MIN <= motif_hits <= DIORAMA_MOTIF_APPEARANCES_MAX):
                issues.append(
                    f"[motif] recurring gauge motif appears in {motif_hits} clips (must be "
                    f"{DIORAMA_MOTIF_APPEARANCES_MIN}-{DIORAMA_MOTIF_APPEARANCES_MAX} across Acts 1-6) (R56)"
                )
        if not is_micro:
            acts_covered = {int(c.get("act") or 0) for c in clips}
            missing_acts = [a for a in range(1, DIORAMA_ACT_COUNT + 1) if a not in acts_covered]
            if missing_acts:
                issues.append(f"[diorama] base clips missing coverage for Act(s) {missing_acts} (R58)")

    # 4. Plain-language, conversational prosody & anatomy glossing -------------
    _expressive_ok = ("question mark", "exclamation mark", "em dash", "en dash", "ellipsis")
    q_count = sum(1 for s in lines if "?" in s)
    min_q = 1 if is_micro else DIORAMA_MIN_CONVERSATIONAL_QUESTIONS
    if q_count < min_q:
        issues.append(
            f"[storyteller] script has only {q_count} conversational question(s) '?' "
            f"(need >= {min_q} to avoid flat textbook reading) (R57)"
        )
    if is_v7 and not is_micro and len(lines) >= 20:
        mid_lo = max(0, len(lines) // 3 - 2)
        mid_hi = min(len(lines), (2 * len(lines)) // 3 + 2)
        if not any("?" in s for s in lines[mid_lo:mid_hi]):
            issues.append(
                f"[midpoint_loop_v7] no midpoint open-loop question '?' in sentences {mid_lo + 1}..{mid_hi} "
                "to sustain AVD past 60-90s across the Act 3 -> Act 4 transition (R57-M)"
            )
    a = analyze_script(lines)
    fk_cap = DIORAMA_V7_MAX_FK_GRADE if is_us_v7 else READABILITY_SCRIPT_FK_MAX
    if a["script_fk_grade"] > fk_cap:
        issues.append(f"[plain] script reading grade {a['script_fk_grade']} > {fk_cap} (R15)")
    for c in a["clips"]:
        for t in c["tts_issues"]:
            if any(k in t for k in _expressive_ok):
                continue
            issues.append(f"[tts] sentence {c['clip']}: {t} (R49-T)")
        if c["robotic_opener"]:
            issues.append(f"[plain] sentence {c['clip']}: robotic 'Step one/two/three' opener (R26)")
    eff_jargon = a["unglossed_jargon_terms"] if is_v7 else a["jargon_terms"]
    if len(eff_jargon) > JARGON_TERMS_MAX:
        issues.append(f"[plain] {len(eff_jargon)} unglossed technical terms {eff_jargon} > cap {JARGON_TERMS_MAX} (R15/R57-C)")
    if is_v7:
        from pipeline.plain_language import find_ai_cliches_and_seminar_isms

        for dup_idiom in find_duplicate_analogy_idioms(lines):
            issues.append(f"[analogy_dup] {dup_idiom} — vary everyday metaphors across Acts (R57-C)")
        for idx_s, s_txt in enumerate(lines, start=1):
            ns = find_ai_cliches_and_seminar_isms(s_txt)
            if ns["ai_cliches"]:
                issues.append(
                    f"[natural_script] sentence {idx_s} uses banned AI-cliché phrasing {ns['ai_cliches']} — "
                    "use natural ear-first spoken US English (R57-C)"
                )
            if ns["seminar_isms"]:
                issues.append(
                    f"[natural_script] sentence {idx_s} uses slide-seminar transition {ns['seminar_isms']} — "
                    "use documentary storyteller bridges instead (R57-C)"
                )
    for r in a["unglossed_anatomy_terms"]:
        issues.append(f"[plain] '{r}' is never explained in everyday words (plain name from anatomy_map) (R48)")
    if a["second_person_clips"] < SECOND_PERSON_CLIPS_MIN:
        issues.append("[plain] no sentence connects the discovery to the viewer ('you / your') (R15)")

    # 5. R62 Dynamic Per-Episode QA Contract (Gate 1: Cast, Trauma, & 1:1 Literal Analogy Cutaways)
    from pipeline.dynamic_episode_qa import verify_pre_flow_contract

    issues.extend(verify_pre_flow_contract(plan, lines, clips, script_doc=script_doc))
    return issues


def validate_production_v5(
    plan: dict[str, Any] | None,
    narrations: list[str],
    clips: list[dict[str, Any]],
) -> list[str]:
    from pipeline.config import is_diorama_profile

    issues: list[str] = []
    plan = plan or {}
    if is_diorama_profile(plan):
        return validate_production_diorama_v6(plan, narrations, clips)
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
        link_items = link if isinstance(link, list) else [link]
        for sub_link in link_items:
            reg = (sub_link or {}).get("region") if isinstance(sub_link, dict) else None
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
    from pipeline.config import is_diorama_profile
    from pipeline.flow_prompt_builder import is_diorama_v6_plan

    project_dir = Path(project_dir)
    row: dict[str, Any] = {"project_id": project_dir.name}
    try:
        prompts_doc = json.loads((project_dir / "03_visuals" / "flow_all_in_one_prompts.json").read_text(encoding="utf-8"))
        clips = prompts_doc.get("clips") or []
    except Exception as exc:  # noqa: BLE001
        row.update({"score": 0, "error": f"no prompts file: {str(exc)[:60]}"})
        return row
    narrations: list[str] = []
    plan: dict[str, Any] = {}
    s_doc: dict[str, Any] = {}
    vp = project_dir / "03_visuals" / "visual_plan.json"
    if vp.exists():
        try:
            plan = json.loads(vp.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            plan = {}
    try:
        s_doc = json.loads((project_dir / "02_script" / "script.json").read_text(encoding="utf-8"))
        if isinstance(s_doc.get("sentences"), list) and s_doc["sentences"]:
            narrations = [
                str(s.get("text") if isinstance(s, dict) else s).strip()
                for s in s_doc["sentences"]
                if str(s.get("text") if isinstance(s, dict) else s).strip()
            ]
        elif isinstance(s_doc.get("acts"), list) and s_doc["acts"]:
            narrations = [
                str(s.get("text") if isinstance(s, dict) else s).strip()
                for act in s_doc["acts"]
                if isinstance(act, dict)
                for s in (act.get("sentences") or [])
                if str(s.get("text") if isinstance(s, dict) else s).strip()
            ]
        elif isinstance(s_doc.get("clip_narrations"), list) and s_doc["clip_narrations"]:
            narrations = [str(s) for s in s_doc["clip_narrations"] if str(s).strip()]
        else:
            narrations = [str(c.get("spoken_narration") or "") for c in clips if str(c.get("spoken_narration") or "").strip()]
    except Exception:  # noqa: BLE001
        s_doc = {}
        narrations = [str(c.get("spoken_narration") or "") for c in clips]
        row["note"] = "script.json empty/missing; narration taken from prompts file"

    diorama_proj = (
        is_diorama_v6_plan(plan)
        or is_diorama_profile(plan)
        or is_diorama_profile(s_doc)
        or isinstance(s_doc.get("sentences"), list)
        or isinstance(s_doc.get("acts"), list)
    )
    declared_mode = str(plan.get("visual_mode") or "").strip().upper()
    if diorama_proj and declared_mode in MAX_BRAIN_CLIPS_BY_MODE:
        mode = declared_mode
    else:
        mode = _infer_mode(project_dir, plan, narrations)
    eval_plan = dict(plan)
    eval_plan["visual_mode"] = mode
    if diorama_proj:
        issues = validate_production_diorama_v6(eval_plan, narrations, clips, script_doc=s_doc or None)
    else:
        issues = validate_production_v5(eval_plan, narrations, clips)
    by_cat: dict[str, list[str]] = {k: [] for k in _CATEGORY_WEIGHTS}
    cat_aliases = {
        "narration": "structure",
        "prompt": "structure",
        "diorama": "scene",
        "diorama_script": "structure",
        "en_us_lock": "plain",
        "hook_v7": "plain",
        "hooks": "structure",
        "zero_reuse": "scene",
        "zero_reuse_v7": "scene",
        "analogy": "plain",
        "filler_ban_v7": "scene",
        "spatial_aba_v7": "scene",
        "pacing_v7": "structure",
        "analogy_cap_v7": "scene",
        "split_v7": "structure",
        "scene_state_v7": "scene",
        "lowpoly_v7": "scene",
        "camera": "acting",
        "world": "scene",
        "crystal": "brain",
        "zero_flesh": "scene",
    }
    for x in issues:
        m = re.search(r"\[(\w+)\]", x)
        cat = (m.group(1) if m else "structure")
        cat = cat_aliases.get(cat, cat)
        if cat not in _CATEGORY_WEIGHTS:
            cat = "structure"
        by_cat.setdefault(cat, []).append(x)
    score = 0.0
    n_clips = max(1, len(clips))
    for cat, weight in _CATEGORY_WEIGHTS.items():
        n = len(by_cat.get(cat, []))
        denom = {"scene": 2, "acting": n_clips, "brain": max(3, n_clips // 2), "plain": 6, "tts": 4, "structure": 4}[cat]
        score += weight * max(0.0, 1.0 - n / denom)
    a = analyze_script(narrations)
    brain_clips = sum(
        1
        for c in clips
        if bool(c.get("brain_clip")) or str(c.get("setting")) in (*BRAIN_SETTINGS, "brain_studio")
    )
    acting_fail = len({re.search(r"clip (\d+)", x).group(1) for x in by_cat.get("acting", []) if re.search(r"clip (\d+)", x)})
    row.update(
        {
            "profile": "neuro_diorama" if diorama_proj else "classic_v5",
            "mode": mode,
            "mode_declared": bool(declared_mode in MAX_BRAIN_CLIPS_BY_MODE) if diorama_proj else is_v5_plan(plan),
            "score": round(score, 1),
            "brain_clips": brain_clips,
            "brain_cap": len(clips) if diorama_proj and mode != "BEHAVIORAL_PSYCH" else MAX_BRAIN_CLIPS_BY_MODE.get(mode, 6),
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
