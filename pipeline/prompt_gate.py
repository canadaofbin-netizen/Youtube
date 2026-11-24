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
from pipeline.prompt_builder import (
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
        return issues
  # pure environment / object shot
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


def _resolve_takeaway_bridge_sentence(
    lines: list[str],
    bank: tuple[str, ...],
) -> tuple[str | None, str]:
    """Resolves the closing takeaway/open-verdict bridge sentence across 1-sentence (`S_N`) or 2-sentence (`S_{N-1}` + `S_N ?`) closes."""
    if not lines:
        return None, ""
    last_raw = lines[-1]
    last_clean = re.sub(r"^[\"'“”‘’\s]+", "", last_raw).lower()
    pref_last = next((p.strip().lower() for p in bank if last_clean.startswith(p.strip().lower())), "")
    if pref_last:
        return last_raw, pref_last
    if len(lines) >= 2 and last_raw.strip().endswith("?"):
        prev_raw = lines[-2]
        prev_clean = re.sub(r"^[\"'“”‘’\s]+", "", prev_raw).lower()
        pref_prev = next((p.strip().lower() for p in bank if prev_clean.startswith(p.strip().lower())), "")
        if pref_prev:
            return prev_raw, pref_prev
    return None, ""


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
    _, cur_end_pref = _resolve_takeaway_bridge_sentence(lines, DIORAMA_TAKEAWAY_BRIDGE_BANK)

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
            _, adj_end_pref = _resolve_takeaway_bridge_sentence(adj, DIORAMA_TAKEAWAY_BRIDGE_BANK)
            if adj_end_pref == cur_end_pref:
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
    from pipeline.thumbnail import is_r65_v4_spec, validate_hook_lexical, validate_v4_micro_label

    plan = plan or {}
    script_doc = script_doc or {}
    thumb = plan.get("thumbnail")
    if not isinstance(thumb, dict) or not thumb:
        return ["[thumbnail_v7] visual_plan.thumbnail block is missing (need hook_text + cover_sentence_index in 1..3) (R65)"]

    issues: list[str] = []
    v4_mode = is_r65_v4_spec(thumb)
    top_split_label = str(thumb.get("top_split_label") or "").strip()
    bottom_split_label = str(thumb.get("bottom_split_label") or "").strip()
    top_left_hook = str(thumb.get("top_left_hook") or "").strip()
    bottom_right_hook = str(thumb.get("bottom_right_hook") or "").strip()
    hook_text = str(thumb.get("hook_text") or top_split_label or top_left_hook or "").strip()
    title = str(script_doc.get("title") or plan.get("title") or "").strip()

    if v4_mode:
        tl_eff = top_split_label or top_left_hook or hook_text
        bl_eff = bottom_split_label or bottom_right_hook
        for fld_name, fld_val in (("top_split_label", tl_eff), ("bottom_split_label", bl_eff)):
            for v4_err in validate_v4_micro_label(fld_val):
                issues.append(f"[thumbnail_v8] {fld_name} '{fld_val}' violates R65 v4 ({v4_err})")
    else:
        if not hook_text or hook_text.upper() == "TODO":
            issues.append("[thumbnail_v7] visual_plan.thumbnail.hook_text must be hand-authored (not empty or TODO) (R65)")
        else:
            for lex_err in validate_hook_lexical(hook_text, title=title):
                issues.append(f"[thumbnail_v7] hook_text '{hook_text}' violates TQ7 ({lex_err}) (R65)")

        if top_left_hook or bottom_right_hook:
            for field_name, chunk_val, check_title in (
                ("top_left_hook", top_left_hook, title),
                ("bottom_right_hook", bottom_right_hook, ""),
            ):
                if not chunk_val or chunk_val.upper() == "TODO":
                    issues.append(f"[thumbnail_v8] visual_plan.thumbnail.{field_name} must be hand-authored (R65 v2)")
                else:
                    for lex_err in validate_hook_lexical(chunk_val, title=check_title):
                        issues.append(f"[thumbnail_v8] {field_name} '{chunk_val}' violates TQ7 ({lex_err}) (R65 v2)")
                    if len(chunk_val.split()) > 3:
                        issues.append(f"[thumbnail_v8] {field_name} '{chunk_val}' exceeds 3 words (R65 v2 Z-pattern)")
            p_style = str(thumb.get("pointer_style") or "red_arrow").strip()
            if p_style not in ("red_arrow", "dimension_ruler", "check_cross"):
                issues.append(
                    f"[thumbnail_v8] pointer_style must be one of ('red_arrow', 'dimension_ruler', 'check_cross'), got {p_style!r} (R65 v2)"
                )

    from pipeline.config import is_expressive_v8_plan

    is_v8 = is_expressive_v8_plan(plan, script_doc)
    cover_idx = thumb.get("cover_sentence_index")
    if not isinstance(cover_idx, int) or isinstance(cover_idx, bool) or not (1 <= cover_idx <= 3):
        issues.append(
            f"[thumbnail_v7] cover_sentence_index must be an integer in 1..3 (cold-open), got {cover_idx!r} (R65)"
        )
    elif is_v8:
        if list(plan.get("chapter_headlines") or []) or list(plan.get("top_callouts") or []):
            issues.append(
                "[thumbnail_v8] expressive_25d_v8 forbids top in-video chapter_headlines / top_callouts "
                "(thumbnail hook lives in 06_publish/thumbnail.png; R87 0.00-2.20s HookTitle uses hook_title_text only) (R68/R87)"
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



_ALLOWED_V8_SENTENCE_BEATS: frozenset[str] = frozenset(
    {
        "immediate_brain_shock",
        "bizarre_experiment",
        "paradox_action",
        "paradox_question",
        "myth_flip_claim",
        "sensory_test",
        "action_first_stamp",
        "university_bridge",
        "credibility_bridge",
        "case_stamp",
        "action_open",
        "hook_promise",
        "conflict",
        "setback",
        "escalation",
        "core",
        "evidence",
        "mechanism",
        "payoff",
        "climax_cut",
        "mic_drop",
        "seamless_loop",
        "question",
        "empathy",
        "aggro",
        "cta_question",
        "loop",
    }
)

_V8_YEAR_FIRST_OPENER_RE = re.compile(
    r"^in\s+(?:the\s+year\s+|late\s+|early\s+|the\s+summer\s+of\s+|the\s+winter\s+of\s+|the\s+spring\s+of\s+|the\s+fall\s+of\s+)?"
    r"(?:(?:18|19|20)\d{2}s?|(?:eighteen|nineteen|twenty)\s+\w+|two\s+thousand)\b",
    flags=re.IGNORECASE,
)

_R73_PARADOX_CONDITION_RE = re.compile(
    r"\b(?:why|how|only\s+when|even\s+when|even\s+though|without|while|yet|instead|harder|worse|hating|hate|"
    r"regret|fail|fails|failed|lose|loses|lost|forget|forgets|awake|impossible|can't|cannot|couldn't|won't|"
    r"refuse|refuses|trap|traps|trapped|backfire|backfires|wrong|opposite|less|more\s+tired|more\s+anxious)\b",
    flags=re.IGNORECASE,
)

_R73_SENSORY_TEST_CUE_RE = re.compile(
    r"\b(?:you|your|you're|you've|yourself|try|close|hold|rub|press|touch|stare|tap|blink|clench|say|count|pick|listen|watch)\b",
    flags=re.IGNORECASE,
)

_R73_IMMEDIATE_GLOSS_APPO_RE = re.compile(
    r"(?:\bbrain's\s+(?:[a-z-]+\s+){0,2}(?:alarm|hub|center|builder|brake|switch|detector|predictor|filter|vault|map|guard|relay|scanner|compass|timer|judge|gate|network)\b|"
    r"\byour\s+(?:[a-z-]+\s+){0,2}(?:alarm|hub|center|builder|brake|switch|detector|predictor|filter|vault|map|guard|relay|scanner|compass|timer|judge|gate)\b|"
    r"\b(?:called|known\s+as)\s+the\b)",
    flags=re.IGNORECASE,
)

_V8_CASE_STAMP_YEAR_RE = re.compile(
    r"\b(?:"
    r"(?:18|19|20)\d{2}s?"
    r"|(?:eighteen|nineteen|twenty)\s+(?:"
    r"oh[\s-]+(?:one|two|three|four|five|six|seven|eight|nine)"
    r"|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen"
    r"|(?:twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety)(?:[\s-]+(?:one|two|three|four|five|six|seven|eight|nine))?"
    r"|twenties|thirties|forties|fifties|sixties|seventies|eighties|nineties|hundreds?"
    r")"
    r"|two\s+thousand(?:\s+and)?(?:\s+(?:"
    r"one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen"
    r"|twenty(?:[\s-]+(?:one|two|three|four|five|six|seven|eight|nine))?"
    r"))?"
    r")\b",
    flags=re.IGNORECASE,
)
_V8_CASE_STAMP_DURATION_RE = re.compile(
    r"^(?:for|over)\s+(?:\w+[-\s]+){1,4}years\b",
    flags=re.IGNORECASE,
)
_V8_CASE_STAMP_INSTITUTION_OR_ROLE_RE = re.compile(
    r"\b(?:"
    r"university|college|hospital|clinic|institute|laboratory|labs?|school|medical\s+center|center|department|"
    r"stanford|harvard|mit|caltech|yale|oxford|cambridge|princeton|columbia|berkeley|ucla|nyu|"
    r"cornell|duke|penn|chicago|michigan|minnesota|wisconsin|washington|virginia|rochester|iowa|"
    r"johns\s+hopkins|montreal|mcgill|ucl|london|zurich|tokyo|kyoto|brown|dartmouth|vanderbilt|"
    r"emory|northwestern|georgetown|pittsburgh|boston|vermont|"
    r"patient\s+[a-z](?:\.?[a-z]\.?)?|patient\s+named\s+[a-z]{2,}|"
    r"dr\.?\s+[a-z]{2,}|prof\.?\s+[a-z]{2,}|"
    r"neuroscientists?|psychologists?|psychiatrists?|neurologists?|neurosurgeons?|surgeons?|"
    r"doctors?|physicians?|clinicians?|researchers?|scientists?|investigators?|experimenters?"
    r")\b",
    flags=re.IGNORECASE,
)
_V8_CASE_STAMP_PERSON_NAME_RE = re.compile(
    r"\b[A-Z][a-z]{1,}\s+(?:[A-Z]\.\s+)?"
    r"(?!Test\b|Effect\b|Task\b|Illusion\b|Syndrome\b|Disease\b|Disorder\b|Trial\b|Experiment\b|Study\b|Prize\b|Award\b|Street\b|Room\b|Hall\b|Night\b|Day\b)"
    r"[A-Z][a-z]{1,}\b"
)
_V8_DRY_ABSTRACT_OPENER_RE = re.compile(
    r"\b(?:"
    r"(?:a|the|this)\s+(?:new\s+|landmark\s+|famous\s+)?(?:study|paper|article|report|meta-analysis|review)\s+"
    r"(?:was\s+published|published\s+in|examined|examines|investigated|investigates|explored|explores|analyzed|analyzes|assessed|assesses|evaluated|evaluates|looked\s+at|looks\s+at)"
    r"|researchers\s+published\s+a\s+(?:study|paper)"
    r")\b",
    flags=re.IGNORECASE,
)

_V8_SPOKEN_CITATION_RE = re.compile(
    r"(?:\b(?:dr\.?|doctor|prof\.?|professor)\s+[A-Z][a-z]{2,}\b|"
    r"\b(?:neuroscientist|psychologist|researcher|scientist|psychiatrist)\s+[A-Z][a-z]{2,}\s+[A-Z][a-z]{2,}\b|"
    r"\bet\s+al\.?\b|\bpublished\s+in\b|\bjournal\s+of\b)",
)

_V8_SPOKEN_SAMPLE_COUNT_RE = re.compile(
    r"(?:\bn\s*=\s*\d+\b|"
    r"\b(?:\d+|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|"
    r"twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred)"
    r"(?:[-\s]+(?:one|two|three|four|five|six|seven|eight|nine))?\s+"
    r"(?:healthy\s+|adult\s+|human\s+|college\s+|young\s+)?(?:volunteers|participants|subjects|sleepers|undergraduates)\b)",
    flags=re.IGNORECASE,
)

_V8_RAW_CLINICAL_JARGON_RE = re.compile(
    r"\b(?:polysomnography|electroencephalogram|electroencephalography|magnetoencephalography|"
    r"unihemispheric|slow-wave\s+asymmetry|statistically\s+significant|p-value|"
    r"placebo-controlled|double-blind\s+cohort)\b",
    flags=re.IGNORECASE,
)

_V8_CONFLICT_BEAT_RE = re.compile(
    r"\b(?:but|yet|instead|except|wrong|failed|backfired|refused|laughed|dismissed|"
    r"panicked|trapped|worse|couldn't|can't|never|stopped|froze|crashed|broke|snapped|shocked)\b",
    flags=re.IGNORECASE,
)

_STIFF_UNCONTRACTED_V8_RE = re.compile(
    r"\b(?:cannot|do\s+not|does\s+not|did\s+not|is\s+not|are\s+not|it\s+is|that\s+is|you\s+are|they\s+are|we\s+are|will\s+not|would\s+not)\b",
    flags=re.IGNORECASE,
)

_MYTH_REBUTTAL_OPENER_RE = re.compile(
    r"^(?:wrong\b|nope\b|not\s+quite\b|except\b)",
    flags=re.IGNORECASE,
)

_STANDALONE_MYTH_DENIAL_RE = re.compile(
    r"(?:^and\s+no,\s+it(?:'s|\s+is)\s+not\b|^it(?:'s|\s+is)\s+not\s+(?:the|your|jet\s+lag)\b|^everyone\s+blames\b)",
    flags=re.IGNORECASE,
)

_LOOP_STOPWORDS: frozenset[str] = frozenset(
    {
        "ever",
        "have",
        "what",
        "when",
        "where",
        "which",
        "your",
        "youre",
        "with",
        "from",
        "into",
        "over",
        "that",
        "this",
        "does",
        "would",
        "could",
        "should",
        "about",
        "every",
        "there",
        "their",
    }
)


def _count_v8_myth_flips(lines: list[str], foil_one_based: set[int]) -> int:
    """
    Counts myth-flip beats across `lines`.
    An adjacent `(foil at i, immediate Wrong/Nope/Not quite/Except rebuttal at i+1)` pair counts as 1 myth-flip beat;
    standalone foil lines, standalone rebuttal openers, and explicit opening myth-denial lines ('And no, it's not...') each count as 1.
    """
    count = 0
    consumed: set[int] = set()
    for idx, raw in enumerate(lines, start=1):
        if idx in consumed:
            continue
        clean = re.sub(r"^[\"'“”‘’\s]+", "", str(raw or "")).strip()
        if idx in foil_one_based:
            count += 1
            if idx + 1 <= len(lines):
                nxt_clean = re.sub(r"^[\"'“”‘’\s]+", "", str(lines[idx] or "")).strip()
                if _MYTH_REBUTTAL_OPENER_RE.match(nxt_clean):
                    consumed.add(idx + 1)
            continue
        if _MYTH_REBUTTAL_OPENER_RE.match(clean) or _STANDALONE_MYTH_DENIAL_RE.search(clean):
            count += 1
    return count


def _extract_word_window_around_phrase(sentence: str, phrase: str, window_words: int) -> str:
    """Returns the lowercase +-`window_words` token span surrounding `phrase` inside `sentence`."""
    low_s = str(sentence or "").lower()
    low_p = str(phrase or "").lower().strip()
    if not low_p:
        return low_s
    m = re.search(rf"(?<![a-z-]){re.escape(low_p)}(?![a-z-])", low_s)
    if not m:
        return low_s
    before_tokens = re.findall(r"[a-z0-9'-]+", low_s[: m.start()])
    after_tokens = re.findall(r"[a-z0-9'-]+", low_s[m.end() :])
    span = before_tokens[-window_words:] + re.findall(r"[a-z0-9'-]+", low_p) + after_tokens[:window_words]
    return " ".join(span)


def _validate_r73_jargon_and_gloss(
    lines: list[str],
    max_hard_terms: int,
    window_words: int,
) -> list[str]:
    """
    R73-3 US-Native Jargon Gate:
    1. Caps total distinct hard neuro/anatomy terms per script to `<= max_hard_terms` (2).
    2. Requires every first occurrence of a hard neuro/anatomy term to carry an immediate plain-English
       functional gloss within `+- window_words` (8 words) inside that same sentence ('Plain-First' rule).
    """
    from pipeline.anatomy_map import ANATOMY_FUNCTION_MAP
    from pipeline.plain_language import GLOSSABLE_NEURO_TERMS, find_anatomy_terms, find_jargon

    issues: list[str] = []
    seen_terms: dict[str, tuple[int, str, str]] = {}  # key -> (1-based sentence_idx, display_term, kind)

    for s_idx, s_line in enumerate(lines, start=1):
        for region in find_anatomy_terms(s_line):
            key = f"anat:{region}"
            if key in seen_terms:
                continue
            # Find which alias matched inside s_line for exact +-8w window slicing
            meta = ANATOMY_FUNCTION_MAP.get(region, {})
            aliases = sorted([region, *list(meta.get("aliases") or ())], key=len, reverse=True)
            matched_alias = region
            for al in aliases:
                if re.search(rf"(?<![a-z-]){re.escape(al.lower())}(?![a-z-])", s_line.lower()):
                    matched_alias = al
                    break
            seen_terms[key] = (s_idx, matched_alias, region)
            win = _extract_word_window_around_phrase(s_line, matched_alias, window_words)
            plains = tuple(meta.get("plain") or ())
            has_plain_hit = any(
                re.search(rf"(?<![a-z-]){re.escape(p.lower())}(?![a-z-])", win)
                or re.search(rf"(?<![a-z-]){re.escape(p.lower())}(?![a-z-])", s_line.lower())
                and len(re.findall(r"[A-Za-z0-9'-]+", s_line)) <= window_words * 2 + 4
                for p in plains
            )
            if not (has_plain_hit or _R73_IMMEDIATE_GLOSS_APPO_RE.search(win)):
                issues.append(
                    f"[r73_jargon] sentence {s_idx} introduces neuroanatomy term '{matched_alias}' without an immediate "
                    f"plain-English gloss within {window_words} words ('Plain-First' rule, e.g. \"your brain's {plains[0] if plains else 'control hub'} — the {matched_alias}\") (R73)"
                )

        for jterm in find_jargon(s_line):
            # Skip if already counted as part of an anatomy region in this sentence
            if any(jterm.lower() in disp.lower() or disp.lower() in jterm.lower() for _, disp, _ in seen_terms.values()):
                continue
            key = f"jargon:{jterm.lower()}"
            if key in seen_terms:
                continue
            seen_terms[key] = (s_idx, jterm, jterm.lower())
            win = _extract_word_window_around_phrase(s_line, jterm, window_words)
            cues = tuple(GLOSSABLE_NEURO_TERMS.get(jterm.lower()) or ())
            has_cue = any(re.search(rf"(?<![a-z-]){re.escape(c.lower())}(?![a-z-])", win) for c in cues)
            if not (has_cue or _R73_IMMEDIATE_GLOSS_APPO_RE.search(win)):
                issues.append(
                    f"[r73_jargon] sentence {s_idx} introduces hard technical term '{jterm}' without an immediate "
                    f"plain-English gloss within {window_words} words (R73)"
                )

    if len(seen_terms) > max_hard_terms:
        term_list = [disp for _, disp, _ in seen_terms.values()]
        issues.append(
            f"[r73_jargon] script contains {len(seen_terms)} hard neuro/jargon terms {term_list} > max {max_hard_terms} — "
            "translate extra clinical vocabulary into everyday functional words (R73)"
        )
    return issues



def validate_script_spine_v8_report(
    lines: list[str],
    script_doc: dict[str, Any] | None = None,
    *,
    plan: dict[str, Any] | None = None,
    project_id: str = "",
) -> dict[str, list[str]]:
    """
    R68 / R68-H / R73 `expressive_25d_v8` US-Native Hook + S2-S4 Credibility Bridge + Delayed Core Reveal (60-80%) + Mic-Drop/Loop Climax script validator.
    Returns `{"issues": [...], "advisories": [...]}` where `issues` are hard FAIL gates and `advisories` are non-blocking warnings.
    """
    from pipeline.config import (
        DIORAMA_BANNED_WEAK_HOOK_PREFIXES,
        EXPRESSIVE_V8_ADVISORY_PIVOT_MARKERS,
        EXPRESSIVE_V8_ALLOWED_OPENING_MODES,
        EXPRESSIVE_V8_ALLOWED_SPEAKER_ROLES,
        EXPRESSIVE_V8_BANNED_AI_CLICHES,
        EXPRESSIVE_V8_BANNED_EMPATHY_FILLERS,
        EXPRESSIVE_V8_BANNED_GENERIC_QUESTION_PREFIXES,
        EXPRESSIVE_V8_CASE_STAMP_ANCHOR_WINDOW_WORDS,
        EXPRESSIVE_V8_CORE_REVEAL_FRAC_RANGE,
        EXPRESSIVE_V8_DEFAULT_ENDING_MODE,
        EXPRESSIVE_V8_DEFAULT_OPENING_MODE,
        EXPRESSIVE_V8_ENDING_MODES,
        EXPRESSIVE_V8_FORBID_SPOKEN_CITATIONS,
        EXPRESSIVE_V8_FORBID_SPOKEN_OUTRO_QUESTION,
        EXPRESSIVE_V8_IMMEDIATE_GLOSS_WINDOW_WORDS,
        EXPRESSIVE_V8_MAX_FK_GRADE,
        EXPRESSIVE_V8_MAX_HARD_JARGON_TERMS,
        EXPRESSIVE_V8_MAX_MYTH_FLIPS,
        EXPRESSIVE_V8_MAX_VOICES_PER_EPISODE,
        EXPRESSIVE_V8_MIN_NARRATOR_SHARE,
        EXPRESSIVE_V8_OPENING_ACTION_MAX_WORDS,
        EXPRESSIVE_V8_OPENING_CASE_STAMP_MAX_WORDS,
        EXPRESSIVE_V8_OPENING_CASE_STAMP_MIN_WORDS,
        EXPRESSIVE_V8_OPENING_QUESTION_MAX_WORDS,
        EXPRESSIVE_V8_R73_OPENING_WORD_RANGES,
        EXPRESSIVE_V8_REQUIRE_FOIL,
        EXPRESSIVE_V8_US_NATIVE_OPENING_MODES,
        EXPRESSIVE_V8_US_NATIVE_PIVOT_BRIDGES,
        BANNED_R77N_PSEUDO_JARGON_COMPOUNDS,
        BRAIN_SIM_ONLY_WORD_COUNT_RANGE,
        EXPRESSIVE_V8_R77N_MAX_EXCLAMATIONS,
        EXPRESSIVE_V8_R77N_MAX_FK_GRADE,
        EXPRESSIVE_V8_R77N_MAX_STAMP_SENTENCES,
        PRE_R68H_FROZEN_V8_PROJECTS,
        SHORTS_EXPRESSIVE_V8_LEGACY_SENTENCE_WORDS_MAX,
        SHORTS_EXPRESSIVE_V8_R73_SENTENCE_WORDS_MAX,
        is_brain_sim_only_plan,
        is_r73_us_native_v8_script,
        is_r77n_v8_script,
    )
    from pipeline.stamp_overlay import validate_data_stamps
    from pipeline.prompt_builder import count_words
    from pipeline.plain_language import fk_grade, fk_grade_conversational
    from pipeline.prosody_qa import classify_prosody_gears

    issues: list[str] = []
    advisories: list[str] = []
    if len(lines) < 6:
        return {
            "issues": ["[spine_v8] expressive_25d_v8 script needs >= 6 sentences for the retention spine (R68)"],
            "advisories": [],
        }

    sdoc = script_doc or {}
    pdoc = plan or {}
    eff_project_id = str(project_id or sdoc.get("project_id") or pdoc.get("project_id") or "").strip()
    is_pre_r68h_frozen = bool(eff_project_id) and eff_project_id in PRE_R68H_FROZEN_V8_PROJECTS
    is_r73 = (not is_pre_r68h_frozen) and is_r73_us_native_v8_script(sdoc, pdoc, project_id=eff_project_id)
    is_r77n = (not is_pre_r68h_frozen) and is_r77n_v8_script(sdoc, pdoc, project_id=eff_project_id)
    is_brain_only = is_brain_sim_only_plan(pdoc, sdoc)

    s1 = re.sub(r"^[\"'“”‘’\s]+", "", str(lines[0] or "")).strip()
    s1_low = s1.lower()
    weak_prefixes = ("picture this", "suppose ") if is_pre_r68h_frozen else DIORAMA_BANNED_WEAK_HOOK_PREFIXES
    if any(s1_low.startswith(pref) for pref in weak_prefixes):
        issues.append(
            f"[hook_v8] S1 starts with banned weak hypothetical opener {DIORAMA_BANNED_WEAK_HOOK_PREFIXES}: "
            f"'{s1[:65]}' — open at 0.00s with a viewer-relevant paradox/myth/sensory/action hook (R68-H/R73)"
        )

    from pipeline.config import is_r87_plan as _is_r87_spine

    is_r87 = _is_r87_spine(pdoc, sdoc, project_id=eff_project_id)
    if is_pre_r68h_frozen:
        default_opening_mode = "action"
    elif is_r87:
        default_opening_mode = EXPRESSIVE_V8_DEFAULT_OPENING_MODE
    elif s1.endswith("?"):
        default_opening_mode = "paradox_question"
    else:
        default_opening_mode = EXPRESSIVE_V8_DEFAULT_OPENING_MODE
    raw_opening_mode = str(sdoc.get("opening_mode") or pdoc.get("opening_mode") or default_opening_mode).strip().lower()
    opening_mode = "action" if raw_opening_mode == "situation" else raw_opening_mode
    if is_pre_r68h_frozen and opening_mode in ("case_stamp", *EXPRESSIVE_V8_US_NATIVE_OPENING_MODES):
        opening_mode = "action"

    if is_r73:
        s1_first6 = " ".join(s1.split()[:6])
        if _V8_YEAR_FIRST_OPENER_RE.match(s1) or _V8_CASE_STAMP_YEAR_RE.search(s1_first6):
            issues.append(
                f"[r73_hook] S1 starts with banned chronological 'In [Year]...' opener ('{s1[:65]}') — "
                "open with a viewer-relevant paradox/myth/sensory/action hook and move year/university context to S2-S4 (R73)"
            )
        prev_open = str(sdoc.get("previous_opening_mode") or pdoc.get("previous_opening_mode") or "").strip().lower()
        if prev_open and prev_open == opening_mode:
            issues.append(
                f"[r73_hook] opening_mode '{opening_mode}' repeats previous_opening_mode '{prev_open}' — "
                f"rotate across {list(EXPRESSIVE_V8_US_NATIVE_OPENING_MODES)} on adjacent episodes (R73)"
            )

    if opening_mode not in EXPRESSIVE_V8_ALLOWED_OPENING_MODES:
        issues.append(
            f"[spine_v8] invalid opening_mode '{raw_opening_mode}' (allowed: {list(EXPRESSIVE_V8_ALLOWED_OPENING_MODES)}) (R68/R73)"
        )
    elif opening_mode in EXPRESSIVE_V8_US_NATIVE_OPENING_MODES and (opening_mode != "action" or is_r73):
        s1_wc = count_words(s1)
        lo_w, hi_w = EXPRESSIVE_V8_R73_OPENING_WORD_RANGES[opening_mode]
        if not (lo_w <= s1_wc <= hi_w):
            issues.append(
                f"[r73_hook] S1 ({opening_mode}) has {s1_wc} words outside {lo_w}-{hi_w}w: '{s1[:65]}' (R73)"
            )
        if any(s1_low.startswith(pref) for pref in EXPRESSIVE_V8_BANNED_GENERIC_QUESTION_PREFIXES):
            issues.append(
                f"[r73_hook] S1 starts with banned generic low-curiosity question prefix "
                f"{EXPRESSIVE_V8_BANNED_GENERIC_QUESTION_PREFIXES}: '{s1[:65]}' (R73)"
            )
        if opening_mode in ("immediate_brain_shock", "bizarre_experiment", "paradox_action"):
            if s1.endswith("?"):
                issues.append(
                    f"[r87_h2_hook] opening_mode='{opening_mode}' must be a punchy declarative or '!' hook, not '?' ('{s1[:65]}') (R87-H2)"
                )
        if opening_mode == "action" and s1.endswith("?"):
            issues.append(
                f"[r73_hook] opening_mode='action' must be a concrete physical/everyday moment, not '?' ('{s1[:65]}') (R73/R77-N)"
            )
        if opening_mode == "paradox_question":
            if not s1.endswith("?"):
                issues.append(
                    f"[r73_hook] opening_mode='paradox_question' requires S1 ending with '?' (got '{s1[:65]}') (R73)"
                )
            if not _R73_PARADOX_CONDITION_RE.search(s1):
                issues.append(
                    f"[r73_hook] S1 paradox_question lacks a concrete contradiction/paradox condition ('why/how ... only when/even when/hating/fail/worse'): '{s1[:65]}' (R73)"
                )
        elif opening_mode == "myth_flip_claim":
            if s1.endswith("?"):
                issues.append(
                    f"[r73_hook] opening_mode='myth_flip_claim' must be a punchy declarative or '!' claim, not a '?' question ('{s1[:65]}') (R73)"
                )
        elif opening_mode == "sensory_test":
            if not _R73_SENSORY_TEST_CUE_RE.search(s1):
                issues.append(
                    f"[r73_hook] opening_mode='sensory_test' must cue an immediate 2nd-person or bodily action ('you/your/try/close/hold/rub/pick'): '{s1[:65]}' (R73)"
                )
        elif opening_mode == "action_first_stamp":
            if s1.endswith("?"):
                issues.append(
                    f"[r73_hook] opening_mode='action_first_stamp' must be a concrete declarative/'!' action stamp, not '?' ('{s1[:65]}') (R73)"
                )
            if _V8_DRY_ABSTRACT_OPENER_RE.search(s1):
                issues.append(
                    f"[r73_hook] S1 action_first_stamp uses dry paper-abstract phrasing ('{s1[:65]}') (R73)"
                )
    elif opening_mode == "case_stamp":
        if is_r73:
            issues.append(
                f"[r73_hook] opening_mode='case_stamp' is retired on new R73 episodes — use one of {list(EXPRESSIVE_V8_US_NATIVE_OPENING_MODES)} and move university/study context to S2-S4 (R73)"
            )
        s1_wc = count_words(s1)
        if s1.endswith("?"):
            issues.append(
                f"[spine_v8] S1 in default 'case_stamp' opening_mode must be a declarative or '!' real-case event stamp, not a '?' question ('{s1[:65]}') (R68-H)"
            )
        if not (EXPRESSIVE_V8_OPENING_CASE_STAMP_MIN_WORDS <= s1_wc <= EXPRESSIVE_V8_OPENING_CASE_STAMP_MAX_WORDS):
            issues.append(
                f"[spine_v8] S1 case_stamp cold-open has {s1_wc} words outside "
                f"{EXPRESSIVE_V8_OPENING_CASE_STAMP_MIN_WORDS}-{EXPRESSIVE_V8_OPENING_CASE_STAMP_MAX_WORDS}: '{s1[:65]}' (R68-H)"
            )
        anchor_head = " ".join(s1.split()[:EXPRESSIVE_V8_CASE_STAMP_ANCHOR_WINDOW_WORDS])
        has_time_anchor = bool(
            _V8_CASE_STAMP_YEAR_RE.search(anchor_head)
            or _V8_CASE_STAMP_DURATION_RE.search(anchor_head)
        )
        if not has_time_anchor:
            issues.append(
                f"[spine_v8] S1 case_stamp hook missing first-2-second year/decade or duration stamp within first "
                f"{EXPRESSIVE_V8_CASE_STAMP_ANCHOR_WINDOW_WORDS} words: '{s1[:65]}' (R68-H)"
            )
        has_entity_anchor = bool(
            _V8_CASE_STAMP_INSTITUTION_OR_ROLE_RE.search(s1)
            or _V8_CASE_STAMP_PERSON_NAME_RE.search(s1)
        )
        if not has_entity_anchor:
            issues.append(
                f"[spine_v8] S1 case_stamp hook missing real institution/clinic/place or named researcher/patient anchor: '{s1[:65]}' (R68-H)"
            )
        if _V8_DRY_ABSTRACT_OPENER_RE.search(s1):
            issues.append(
                f"[spine_v8] S1 case_stamp hook uses dry paper-abstract phrasing ('{s1[:65]}') — state the concrete experiment action or clinical event directly (R68-H)"
            )
    elif opening_mode == "action":
        s1_wc = count_words(s1)
        if s1.endswith("?"):
            issues.append(
                f"[spine_v8] S1 in 'action' opening_mode must be a concrete physical/odd action statement, not a '?' question ('{s1[:65]}'); "
                "set opening_mode='question' explicitly only if using an optional question cold-open (R68)"
            )
        if s1_wc > EXPRESSIVE_V8_OPENING_ACTION_MAX_WORDS:
            issues.append(
                f"[spine_v8] S1 action cold-open has {s1_wc} words > max {EXPRESSIVE_V8_OPENING_ACTION_MAX_WORDS}: '{s1[:65]}' (R68)"
            )
    else:
        advisories.append(
            "[spine_v8:advisory] opening_mode='question' is optional — prefer default opening_mode='paradox_question' US-native paradox hook (R68-H/R73)"
        )
        s1_wc = count_words(s1)
        has_second_person = bool(re.search(r"\b(?:you|your|you're|you've|you'd|yourself)\b", s1, flags=re.IGNORECASE))
        has_third_person_subj = bool(re.search(r"\b(?:he|she|they|his|her|their)\b", s1, flags=re.IGNORECASE))
        if not s1.endswith("?"):
            issues.append(
                f"[spine_v8] opening_mode='question' requires S1 ending with '?' (got '{s1[:65]}') (R68)"
            )
        if s1_wc > EXPRESSIVE_V8_OPENING_QUESTION_MAX_WORDS:
            issues.append(
                f"[spine_v8] S1 opening question has {s1_wc} words > max {EXPRESSIVE_V8_OPENING_QUESTION_MAX_WORDS}: '{s1[:65]}' (R68)"
            )
        if not has_second_person or (has_third_person_subj and not has_second_person):
            issues.append(
                f"[spine_v8] S1 opening question must address the viewer in 2nd person ('you'/'your'), got: '{s1[:65]}' (R68)"
            )

    if is_r73:
        # R73-2: University / Lab / Researcher / Clinical Credibility Bridge in S2-S4 (or S1-S4 for action_first_stamp)
        bridge_slice = lines[0 : min(4, len(lines))] if opening_mode == "action_first_stamp" else lines[1 : min(4, len(lines))]
        bridge_txt = " ".join(bridge_slice)
        has_cred_bridge = bool(
            _V8_CASE_STAMP_INSTITUTION_OR_ROLE_RE.search(bridge_txt)
            or _V8_CASE_STAMP_PERSON_NAME_RE.search(bridge_txt)
        )
        if not has_cred_bridge:
            issues.append(
                "[r73_bridge] S2-S4 lacks a university/lab/researcher/clinical credibility bridge "
                "(e.g. 'To test this, Harvard psychologists...') to ground the hook in real science (R73)"
            )
        # R73-3: Plain-First / <=8w Immediate Gloss + <=2 Hard Jargon Terms
        issues.extend(
            _validate_r73_jargon_and_gloss(
                lines,
                EXPRESSIVE_V8_MAX_HARD_JARGON_TERMS,
                EXPRESSIVE_V8_IMMEDIATE_GLOSS_WINDOW_WORDS,
            )
        )
        # R73-4: AI-Cliché Hard Block & FK Grade <= 6.2
        for s_idx, s_line in enumerate(lines, start=1):
            low_line = s_line.lower()
            for cliche in EXPRESSIVE_V8_BANNED_AI_CLICHES:
                if re.search(rf"(?<![a-z]){re.escape(cliche.lower())}(?![a-z])", low_line):
                    issues.append(
                        f"[r73_ai_cliche] sentence {s_idx} contains banned AI cliché '{cliche}' ('{s_line[:65]}') (R73)"
                    )
        if is_r77n:
            fk_conv = fk_grade_conversational(" ".join(lines))
            if fk_conv > EXPRESSIVE_V8_R77N_MAX_FK_GRADE:
                issues.append(
                    f"[r77n_fk_grade] script conversational Flesch-Kincaid grade {fk_conv} > R77-N max {EXPRESSIVE_V8_R77N_MAX_FK_GRADE} — "
                    "use shorter conversational clauses and everyday words (R77-N)"
                )
            for s_idx, s_line in enumerate(lines, start=1):
                low_pj = s_line.lower()
                for bad_pj in BANNED_R77N_PSEUDO_JARGON_COMPOUNDS:
                    if re.search(rf"(?<![a-z-]){re.escape(bad_pj.lower())}(?![a-z-])", low_pj):
                        issues.append(
                            f"[r77n_jargon] sentence {s_idx} uses banned pseudo-jargon '{bad_pj}' ('{s_line[:65]}') — "
                            "use natural plain phrasing ('face detector', 'emotional center', 'reality-checker') or an immediately glossed anatomical term (R77-N)"
                        )
            excl_count = sum(1 for ln in lines if "!" in str(ln))
            if excl_count > EXPRESSIVE_V8_R77N_MAX_EXCLAMATIONS:
                issues.append(
                    f"[r77n_tone] script has {excl_count} exclamation marks ('!') > R77-N max {EXPRESSIVE_V8_R77N_MAX_EXCLAMATIONS} — "
                    "keep conversational curiosity calm instead of fake-hyped (R77-N)"
                )
            r77n_gears = classify_prosody_gears(lines, sdoc)
            stamp_count = sum(1 for g in r77n_gears if g == "stamp")
            if stamp_count > EXPRESSIVE_V8_R77N_MAX_STAMP_SENTENCES:
                issues.append(
                    f"[r77n_prosody] {stamp_count} 'stamp' sentences > R77-N max {EXPRESSIVE_V8_R77N_MAX_STAMP_SENTENCES} — "
                    "limit deliberate dramatic pauses to <= 3 high-impact beats (R77-N)"
                )
        else:
            fk_val = fk_grade(" ".join(lines))
            if fk_val > EXPRESSIVE_V8_MAX_FK_GRADE:
                issues.append(
                    f"[r73_fk_grade] script Flesch-Kincaid grade {fk_val} > R73 max {EXPRESSIVE_V8_MAX_FK_GRADE} — "
                    "use shorter conversational clauses and everyday words (R73)"
                )
    if is_brain_only:
        total_wc = sum(count_words(ln) for ln in lines)
        b_wlo, b_whi = BRAIN_SIM_ONLY_WORD_COUNT_RANGE
        if not (b_wlo <= total_wc <= b_whi):
            issues.append(
                f"[r77_brain_only] word count {total_wc} outside standalone brain_simulator_3d_only range {b_wlo}-{b_whi}w (R77)"
            )

    for s_idx, s_line in enumerate(lines, start=1):
        low_s = s_line.lower()
        for filler in EXPRESSIVE_V8_BANNED_EMPATHY_FILLERS:
            if filler in low_s:
                issues.append(
                    f"[spine_v8] sentence {s_idx} uses banned zero-information empathy filler '{filler}' ('{s_line[:65]}') (R68)"
                )
        if EXPRESSIVE_V8_FORBID_SPOKEN_CITATIONS and not bool(sdoc.get("allow_spoken_citations")):
            m_cit = _V8_SPOKEN_CITATION_RE.search(s_line)
            if m_cit:
                issues.append(
                    f"[spine_v8] sentence {s_idx} speaks academic researcher/citation '{m_cit.group(0)}' — keep DOI & researcher names in metadata.json / R35 pinned comment (R68)"
                )
            m_smp = _V8_SPOKEN_SAMPLE_COUNT_RE.search(s_line)
            if m_smp:
                issues.append(
                    f"[spine_v8] sentence {s_idx} speaks clinical sample count '{m_smp.group(0)}' — move n= sample statistics to metadata.json / R35 pinned comment (R68)"
                )
            m_jrg = _V8_RAW_CLINICAL_JARGON_RE.search(s_line)
            if m_jrg:
                issues.append(
                    f"[spine_v8] sentence {s_idx} uses raw clinical jargon '{m_jrg.group(0)}' — use plain everyday physical language (R68)"
                )

    lo_frac, hi_frac = EXPRESSIVE_V8_CORE_REVEAL_FRAC_RANGE
    n_sents = len(lines)
    min_core_s = max(2, int(round(n_sents * lo_frac)))
    max_core_s = min(n_sents - 1, max(min_core_s, int(round(n_sents * hi_frac)) + 1))
    raw_core_idx = sdoc.get("core_reveal_sentence_index")
    if raw_core_idx is None:
        advisories.append(
            f"[spine_v8:advisory] script.core_reveal_sentence_index not specified (target S{min_core_s}..S{max_core_s} / 60-80% delayed reveal) (R68)"
        )
    elif not bool(sdoc.get("allow_legacy_early_core")):
        try:
            core_idx = int(raw_core_idx)
        except (TypeError, ValueError):
            core_idx = -1
        if not (min_core_s <= core_idx <= max_core_s):
            issues.append(
                f"[spine_v8] core_reveal_sentence_index={raw_core_idx} outside delayed 60-80% reveal window "
                f"S{min_core_s}..S{max_core_s} (for {n_sents} sentences) (R68)"
            )

    sent_word_cap = SHORTS_EXPRESSIVE_V8_R73_SENTENCE_WORDS_MAX if is_r73 else SHORTS_EXPRESSIVE_V8_LEGACY_SENTENCE_WORDS_MAX
    for s_idx, s_line in enumerate(lines, start=1):
        swc = count_words(s_line)
        if swc > sent_word_cap:
            tag = "r73_brevity" if is_r73 else "spine_v8"
            rule_lbl = "R73" if is_r73 else "R68"
            issues.append(
                f"[{tag}] sentence {s_idx} has {swc} words > max {sent_word_cap}: '{s_line[:65]}' ({rule_lbl})"
            )

    speakers = sdoc.get("sentence_speakers")
    foil_indices = sdoc.get("foil_sentence_indices")
    foil_set: set[int] = set()
    has_foil = False
    if isinstance(speakers, list):
        if len(speakers) != len(lines):
            issues.append(
                f"[spine_v8] script.sentence_speakers length {len(speakers)} != sentence count {len(lines)} (R68)"
            )
        norm_sp = [str(x or "narrator").strip().lower() for x in speakers]
        allowed_sp = set(EXPRESSIVE_V8_ALLOWED_SPEAKER_ROLES)
        bad_sp = sorted({x for x in norm_sp if x not in allowed_sp})
        if bad_sp:
            issues.append(
                f"[spine_v8] invalid speaker role(s) {bad_sp} in sentence_speakers (allowed: {list(EXPRESSIVE_V8_ALLOWED_SPEAKER_ROLES)}) (R68)"
            )
        distinct_sp = {x for x in norm_sp if x in allowed_sp}
        if len(distinct_sp) > EXPRESSIVE_V8_MAX_VOICES_PER_EPISODE:
            issues.append(
                f"[spine_v8] {len(distinct_sp)} distinct speaker roles {sorted(distinct_sp)} > max {EXPRESSIVE_V8_MAX_VOICES_PER_EPISODE} voices per episode (R68)"
            )
        if norm_sp:
            narrator_share = sum(1 for x in norm_sp if x == "narrator") / float(len(norm_sp))
            if narrator_share < EXPRESSIVE_V8_MIN_NARRATOR_SHARE - 1e-6:
                issues.append(
                    f"[spine_v8] narrator share {narrator_share:.2f} < min {EXPRESSIVE_V8_MIN_NARRATOR_SHARE:.2f} (R68)"
                )
        char_set = {idx_sp for idx_sp, sp_r in enumerate(norm_sp, start=1) if sp_r != "narrator"}
        foil_set = {idx_sp for idx_sp, sp_r in enumerate(norm_sp, start=1) if sp_r == "foil"}
        has_foil = bool(char_set)
    elif isinstance(foil_indices, list) and foil_indices:
        foil_set = {int(i) for i in foil_indices if isinstance(i, int) and 1 <= i <= len(lines)}
        has_foil = len(foil_set) >= 1
    if not has_foil and EXPRESSIVE_V8_REQUIRE_FOIL:
        issues.append(
            "[spine_v8] multi-role dialogue requires >= 1 character sentence in script.sentence_speakers (or foil_sentence_indices) (R68)"
        )

    issues.extend(validate_data_stamps(sdoc, lines))

    myth_flips = _count_v8_myth_flips(lines, foil_set)
    if myth_flips > EXPRESSIVE_V8_MAX_MYTH_FLIPS:
        issues.append(
            f"[spine_v8] myth-flip pattern repeated {myth_flips} times > max {EXPRESSIVE_V8_MAX_MYTH_FLIPS} — avoid repetitive foil/Wrong loops (R68)"
        )

    if not any(_V8_CONFLICT_BEAT_RE.search(ln) for ln in lines[1:]):
        issues.append(
            "[spine_v8] script lacks a conflict/setback/skeptic beat ('but', 'instead', 'failed', 'backfired', 'refused', 'wrong') (R68)"
        )

    full_low = " ".join(lines).lower()
    pivot_markers = (
        EXPRESSIVE_V8_US_NATIVE_PIVOT_BRIDGES
        if is_r73
        else ("wait, what", "wait—what", "wait - what", "but here's", "but here is", "except ", "instead")
    )
    has_contrast_q_pivot = any(
        bool(re.match(r"^[\"'“”‘’\s]*(?:but|yet)\s+[^?]{2,40}\?", ln, flags=re.IGNORECASE))
        for ln in lines[1:-1]
    )
    if not (any(pm in full_low for pm in pivot_markers) or has_contrast_q_pivot or (not EXPRESSIVE_V8_ADVISORY_PIVOT_MARKERS and "until " in full_low)):
        msg_piv = f"[spine_v8:advisory] script missing conversational escalation pivot ({pivot_markers[:4]} or 'But ...?') (R68)"
        if EXPRESSIVE_V8_ADVISORY_PIVOT_MARKERS:
            advisories.append(msg_piv)
        else:
            issues.append(msg_piv.replace(":advisory", ""))

    stiff_hits: list[str] = []
    for s_idx, s_line in enumerate(lines, start=1):
        m_stiff = _STIFF_UNCONTRACTED_V8_RE.search(s_line)
        if m_stiff:
            stiff_hits.append(f"S{s_idx}:'{m_stiff.group(0)}'")
    if stiff_hits:
        advisories.append(
            f"[spine_v8:advisory] stiff uncontracted phrasing detected ({', '.join(stiff_hits[:4])}) — prefer natural spoken contractions (R68)"
        )

    beats = sdoc.get("sentence_beats")
    if beats is not None:
        if not isinstance(beats, list) or len(beats) != len(lines):
            advisories.append(
                f"[spine_v8:advisory] script.sentence_beats length {len(beats) if isinstance(beats, list) else 0} != {len(lines)} (R68)"
            )
        else:
            bad_beats = [
                f"S{idx_b}:'{b_tag}'"
                for idx_b, b_tag in enumerate(beats, start=1)
                if str(b_tag or "").strip().lower() not in _ALLOWED_V8_SENTENCE_BEATS
            ]
            if bad_beats:
                advisories.append(
                    f"[spine_v8:advisory] unrecognized sentence_beats tag(s) {bad_beats[:4]} (allowed: {sorted(_ALLOWED_V8_SENTENCE_BEATS)}) (R68)"
                )

    last_clean = re.sub(r"^[\"'“”‘’\s]+", "", str(lines[-1] or "")).strip()
    if EXPRESSIVE_V8_FORBID_SPOKEN_OUTRO_QUESTION and not bool(sdoc.get("allow_spoken_outro_question")):
        if last_clean.endswith("?"):
            issues.append(
                f"[spine_v8] final sentence ends with '?' ('{lines[-1][:65]}') — end on a punchy climax cut and move viewer debate question to R35 pinned comment (R68)"
            )

    last_low = last_clean.lower()
    banned_recap_openers = (
        "which proves ",
        "in conclusion",
        "to summarize",
        "overall,",
        "this study proves ",
        "that is why scientists ",
    )
    if last_low.startswith(banned_recap_openers):
        issues.append(
            f"[spine_v8] final sentence starts with lecture-summary recap ('{lines[-1][:65]}') — end with a crisp paradox or climax cut (R68)"
        )

    if is_r73:
        ending_mode = str(sdoc.get("ending_mode") or pdoc.get("ending_mode") or EXPRESSIVE_V8_DEFAULT_ENDING_MODE).strip().lower()
        if ending_mode not in EXPRESSIVE_V8_ENDING_MODES:
            issues.append(
                f"[r73_ending] invalid ending_mode '{ending_mode}' (allowed: {list(EXPRESSIVE_V8_ENDING_MODES)}) (R73)"
            )
        elif ending_mode == "seamless_loop":
            s1_words = {
                w.lower()
                for w in re.findall(r"[A-Za-z]{4,}", s1)
                if w.lower() not in _LOOP_STOPWORDS
            }
            last_words = {
                w.lower()
                for w in re.findall(r"[A-Za-z]{4,}", last_clean)
                if w.lower() not in _LOOP_STOPWORDS
            }
            has_loop_bridge = bool(
                (s1_words & last_words)
                or last_clean.endswith(("...", "—"))
                or last_low.startswith(("and that's why", "which is why", "until ", "right before "))
            )
            if not has_loop_bridge:
                issues.append(
                    f"[r73_ending] ending_mode='seamless_loop' requires final sentence to share a lexical/syntactic bridge back into S1 ('{lines[-1][:65]}') (R73)"
                )

    omit_nicks = [str(n).strip() for n in (sdoc.get("omit_experiment_nicknames") or ()) if str(n).strip()]
    for nick in omit_nicks:
        if re.search(rf"\b{re.escape(nick)}\b", full_low, flags=re.IGNORECASE):
            issues.append(
                f"[spine_v8] spoken script contains omitted experiment nickname '{nick}' — save the academic label for comment curiosity (R68)"
            )
    from pipeline.config import is_r85_flow_31_brain_plan as _is_r85_spine_diet
    if _is_r85_spine_diet(pdoc, sdoc, project_id=project_id):
        kept_issues: list[str] = []
        for iss in issues:
            if any(
                k in iss
                for k in (
                    "Flesch-Kincaid",
                    "exceeds R73",
                    "words > max",
                    "[r73_jargon]",
                    "case_stamp",
                )
            ):
                advisories.append(iss)
            else:
                kept_issues.append(iss)
        issues = kept_issues
    return {"issues": issues, "advisories": advisories}


def validate_script_spine_v8(
    lines: list[str],
    script_doc: dict[str, Any] | None = None,
    *,
    plan: dict[str, Any] | None = None,
    project_id: str = "",
) -> list[str]:
    """Backwards-compatible wrapper returning blocking `issues` from `validate_script_spine_v8_report`."""
    return validate_script_spine_v8_report(lines, script_doc=script_doc, plan=plan, project_id=project_id)["issues"]


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
    script_doc: dict[str, Any] | None = None,
    *,
    project_id: str = "",
    slug: str = "",
) -> list[str]:
    """
    R66.4 Balanced Documentary Pacing & Substantive Visual Relevance Gate for active `porcelain_cinematic_v7` episodes:
      - Clip count in [SHORTS_90S_CLIP_COUNT_MIN (24), SHORTS_90S_CLIP_COUNT_MAX (32)] on default `shorts_90s_v7`
        or [PORCELAIN_V7_TARGET_CLIP_MIN (45), PORCELAIN_V7_TARGET_CLIP_MAX (52)] on `shorts_180s_v7` episodes.
      - Primary clip hold span <= PORCELAIN_V7_MAX_HOLD_SENTENCES (2) (blocks 3+ sentence stagnant holds;
        break longer room/brain moments with same-scene multi-angle coverage).
      - porcelain_literal_analogy count <= PORCELAIN_V7_LITERAL_ANALOGY_MAX_CLIPS (2).
      - Bans stopwatch / kitchen-timer / pocket-watch / wall-clock / measuring-tape / dollhouse / postage-stamp
        filler props unless allow_chronometer_apparatus=True on the plan.
      - Validates explicit split_comparisons left_clip_index / right_clip_index bindings.
    """
    from pipeline.config import (
        DIORAMA_SENTENCE_COUNT_MIN,
        MICRO_SHORT_CUT_MAX,
        MICRO_SHORT_CUT_MIN,
        MICRO_SHORT_PROFILE,
        PORCELAIN_V7_LITERAL_ANALOGY_MAX_CLIPS,
        PORCELAIN_V7_MAX_HOLD_SENTENCES,
        PORCELAIN_V7_TARGET_CLIP_MAX,
        PORCELAIN_V7_TARGET_CLIP_MIN,
        SHORTS_90S_CLIP_COUNT_MAX,
        SHORTS_90S_CLIP_COUNT_MIN,
        SHORTS_90S_PROFILE,
        SHORTS_90S_SENTENCE_COUNT_MIN,
        resolve_shorts_format_profile,
    )

    issues: list[str] = []
    plan = plan or {}
    clips = clips or []
    raw_clips = plan.get("clips") if isinstance(plan.get("clips"), list) else []

    fmt_prof = resolve_shorts_format_profile(
        plan,
        script_doc,
        {"sentences": lines or [], "clips": raw_clips or clips},
        project_id=project_id,
        slug=slug,
    )
    if fmt_prof == MICRO_SHORT_PROFILE:
        target_clip_min = MICRO_SHORT_CUT_MIN
        target_clip_max = MICRO_SHORT_CUT_MAX + 4
        sent_floor_for_clip_min = 10
    elif fmt_prof == SHORTS_90S_PROFILE:
        target_clip_min = SHORTS_90S_CLIP_COUNT_MIN
        target_clip_max = SHORTS_90S_CLIP_COUNT_MAX
        sent_floor_for_clip_min = SHORTS_90S_SENTENCE_COUNT_MIN
    else:
        target_clip_min = PORCELAIN_V7_TARGET_CLIP_MIN
        target_clip_max = PORCELAIN_V7_TARGET_CLIP_MAX
        sent_floor_for_clip_min = DIORAMA_SENTENCE_COUNT_MIN

    n_clips = len(raw_clips) if raw_clips else len(clips)
    if n_clips > target_clip_max:
        issues.append(
            f"[pacing_v7] clip count {n_clips} exceeds balanced documentary ceiling {target_clip_max} ({fmt_prof}) "
            "— merge adjacent short beats into 2-sentence holds (R66.4)"
        )
    if len(lines or []) >= sent_floor_for_clip_min and n_clips < target_clip_min:
        issues.append(
            f"[pacing_v7] clip count {n_clips} below balanced documentary floor {target_clip_min} ({fmt_prof}) "
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
                "expressive_xray_brain",
                "porcelain_living_brain",
                "porcelain_data_sculpture",
                "lowpoly_living_brain",
                "lowpoly_matte_brain",
                "lowpoly_data_sculpture",
                "arch_brain_maquette",
                "frosted_crystal_specimen",
            )
            or bool(mc.get("brain_clip"))
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
                if "brain_master" in rid or "xray_brain" in rid:
                    issues.append(
                        f"clip {clip_id}: [scene_state_v7] non-brain clip binds cutaway brain reference '{rid}' "
                        "(causes severed mannequin/crystal-dome head prop contamination) (R66.4/R67/R68)"
                    )

        st = mc.get("scene_state")
        c_loc_early = str((st.get("location_id") if isinstance(st, dict) else "") or mc.get("location_id") or "").strip()
        if not isinstance(st, dict) and c_loc_early and not is_brain_or_outro:
            for rid in start_rids:
                rspec = ref_map.get(rid)
                r_loc = str((rspec or {}).get("location_id") or "").strip() if isinstance(rspec, dict) else ""
                if r_loc and r_loc != c_loc_early:
                    issues.append(
                        f"clip {clip_id}: [scene_state_v7] start reference '{rid}' location_id='{r_loc}' != "
                        f"clip location_id='{c_loc_early}' (cross-location prop/room leak) (R66.4/R67/R68)"
                    )
            for rid in end_rids:
                rspec = ref_map.get(rid)
                r_loc = str((rspec or {}).get("location_id") or "").strip() if isinstance(rspec, dict) else ""
                if r_loc and r_loc != c_loc_early:
                    issues.append(
                        f"clip {clip_id}: [scene_state_v7] end reference '{rid}' location_id='{r_loc}' != "
                        f"clip location_id='{c_loc_early}' (cross-location prop/room leak) (R66.4/R67/R68)"
                    )

        if ledger_required and not is_brain_or_outro and g_name not in ("porcelain_literal_analogy", "expressive_literal_analogy"):
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
        DOSSIER_SCHEMA_VERSION,
        FROZEN_PRE_SCHEMA_V2_DOSSIER_SLUGS,
        FROZEN_PRE_SCHEMA_V2_PROJECT_PREFIXES,
        PRE_R66_FROZEN_PROJECT_PREFIXES,
        PRE_R68H_FROZEN_V8_PROJECTS,
        EXPRESSIVE_V8_DEFAULT_OPENING_MODE,
        SHORTS_90S_CUT_COUNT_MIN,
        SHORTS_90S_PROFILE,
        SHORTS_90S_SENTENCE_COUNT_MAX,
        SHORTS_90S_SENTENCE_COUNT_MIN,
        SHORTS_90S_WORD_COUNT_MAX,
        SHORTS_90S_WORD_COUNT_MIN,
        SHORTS_EXPRESSIVE_V8_CLIP_COUNT_MAX,
        SHORTS_EXPRESSIVE_V8_CLIP_COUNT_MIN,
        SHORTS_EXPRESSIVE_V8_LEGACY_SENTENCE_WORDS_MAX,
        SHORTS_EXPRESSIVE_V8_PROFILE,
        SHORTS_EXPRESSIVE_V8_R73_SENTENCE_WORDS_MAX,
        SHORTS_EXPRESSIVE_V8_SENTENCE_COUNT_MAX,
        SHORTS_EXPRESSIVE_V8_SENTENCE_COUNT_MIN,
        SHORTS_EXPRESSIVE_V8_SENTENCE_WORDS_MAX,
        SHORTS_EXPRESSIVE_V8_WORD_COUNT_MAX,
        SHORTS_EXPRESSIVE_V8_WORD_COUNT_MIN,
        EXPRESSIVE_V8_LEGACY_CLIP_COUNT_MIN,
        EXPRESSIVE_V8_LEGACY_INDOOR_CLIP_COUNT_RANGE,
        EXPRESSIVE_V8_LEGACY_MAX_FK_GRADE,
        EXPRESSIVE_V8_MAX_FK_GRADE,
        EXPRESSIVE_V8_OPENING_QUESTION_STARTERS,
        BRAIN_SIM_ONLY_CLIP_COUNT_RANGE,
        BRAIN_SIM_ONLY_WORD_COUNT_RANGE,
        EXPRESSIVE_V8_R76_CLIP_COUNT_RANGE,
        is_brain_sim_only_plan,
        is_diorama_v7_plan,
        is_expressive_v8_plan,
        is_porcelain_v7_plan,
        is_r72_open_world_v8_plan,
        is_r73_us_native_v8_script,
        is_r76_v8_plan,
        resolve_shorts_format_profile,
    )
    from pipeline.prompt_builder import count_words, validate_diorama_v6_prompts
    from pipeline.plain_language import find_duplicate_analogy_idioms, validate_number_analogy_pairing

    issues: list[str] = []
    plan = plan or {}
    is_v8 = is_expressive_v8_plan(plan, script_doc, *(clips or []))
    is_v7 = is_v8 or is_diorama_v7_plan(plan) or (isinstance(script_doc, dict) and is_diorama_v7_plan(script_doc))
    lines = [str(n).strip() for n in (narrations or []) if str(n).strip()]

    project_id = str((script_doc or {}).get("project_id") or plan.get("project_id") or "").strip()
    dossier_slug = str(plan.get("dossier") or (script_doc or {}).get("dossier") or "").strip()
    fmt_prof = resolve_shorts_format_profile(
        plan,
        script_doc or {},
        {"sentences": lines, "clips": clips or []},
        slug=dossier_slug,
        project_id=project_id,
    )
    is_micro = fmt_prof == MICRO_SHORT_PROFILE
    is_90s = fmt_prof == SHORTS_90S_PROFILE
    if fmt_prof == SHORTS_EXPRESSIVE_V8_PROFILE:
        is_v8 = True
        is_v7 = True
    prosody_mode = str((script_doc or {}).get("prosody_mode") or plan.get("prosody_mode") or "").strip().lower()

    # 1. R57 / R63 / R68 US English & sentence/word budget ---------------------
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
    is_pre_schema_v2_frozen = (
        is_pre_r66_frozen
        or dossier_slug in FROZEN_PRE_SCHEMA_V2_DOSSIER_SLUGS
        or (bool(project_id) and any(project_id.startswith(pref) for pref in FROZEN_PRE_SCHEMA_V2_PROJECT_PREFIXES))
    )
    is_us_v7 = is_v7 and not is_v8 and not is_pre_r66_frozen and (
        prosody_mode == DIORAMA_V7_US_PROSODY_MODE or bool(plan.get("us_anti_clone_v7"))
    )

    is_brain_only_gate = bool(is_v8 and is_brain_sim_only_plan(plan, script_doc))
    is_r76_gate = bool(is_v8 and is_r76_v8_plan(plan, script_doc, project_id=project_id))
    from pipeline.config import R82_CLIP_COUNT_RANGE, is_r82_dual_speed_pacing_plan

    is_r82_gate = bool(is_v8 and is_r82_dual_speed_pacing_plan(plan, script_doc, project_id=project_id))
    if is_v8:
        v8_sent_min, v8_sent_max = (
            BRAIN_SIM_ONLY_CLIP_COUNT_RANGE
            if is_brain_only_gate
            else (SHORTS_EXPRESSIVE_V8_SENTENCE_COUNT_MIN, SHORTS_EXPRESSIVE_V8_SENTENCE_COUNT_MAX)
        )
        v8_word_min, v8_word_max = (
            BRAIN_SIM_ONLY_WORD_COUNT_RANGE
            if is_brain_only_gate
            else (SHORTS_EXPRESSIVE_V8_WORD_COUNT_MIN, SHORTS_EXPRESSIVE_V8_WORD_COUNT_MAX)
        )
        if not (v8_sent_min <= len(lines) <= v8_sent_max):
            issues.append(
                f"[diorama_script] sentence count {len(lines)} outside "
                f"{v8_sent_min}-{v8_sent_max} ({'brain_simulator_3d_only' if is_brain_only_gate else SHORTS_EXPRESSIVE_V8_PROFILE}) ({'R77-N' if is_brain_only_gate else 'R68'})"
            )
        if not (v8_word_min <= total_words <= v8_word_max):
            issues.append(
                f"[diorama_script] total spoken words {total_words} outside "
                f"{v8_word_min}-{v8_word_max} for {'brain_simulator_3d_only' if is_brain_only_gate else '58-88s expressive_25d_v8'} pacing ({'R77-N' if is_brain_only_gate else 'R68'})"
            )
    elif is_micro:
        if not (10 <= len(lines) <= 18):
            issues.append(f"[micro_short_v7] sentence count {len(lines)} outside 10-18 (R63)")
        if not (MICRO_SHORT_WORD_MIN <= total_words <= MICRO_SHORT_WORD_MAX):
            issues.append(
                f"[micro_short_v7] total spoken words {total_words} outside {MICRO_SHORT_WORD_MIN}-{MICRO_SHORT_WORD_MAX} (R63)"
            )
    elif is_90s:
        if not (SHORTS_90S_SENTENCE_COUNT_MIN <= len(lines) <= SHORTS_90S_SENTENCE_COUNT_MAX):
            issues.append(
                f"[diorama_script] sentence count {len(lines)} outside "
                f"{SHORTS_90S_SENTENCE_COUNT_MIN}-{SHORTS_90S_SENTENCE_COUNT_MAX} ({SHORTS_90S_PROFILE}) (R57)"
            )
        if not (SHORTS_90S_WORD_COUNT_MIN <= total_words <= SHORTS_90S_WORD_COUNT_MAX):
            issues.append(
                f"[diorama_script] total spoken words {total_words} outside "
                f"{SHORTS_90S_WORD_COUNT_MIN}-{SHORTS_90S_WORD_COUNT_MAX} for 90-second Shorts pacing (R57/R63)"
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

    is_pre_r68h_frozen_v8 = is_v8 and bool(project_id) and project_id in PRE_R68H_FROZEN_V8_PROJECTS
    is_r73_v8 = (
        is_v8
        and not is_pre_r68h_frozen_v8
        and is_r73_us_native_v8_script(script_doc, plan, project_id=project_id)
    )
    sent_words_max = (
        (SHORTS_EXPRESSIVE_V8_R73_SENTENCE_WORDS_MAX if is_r73_v8 else SHORTS_EXPRESSIVE_V8_LEGACY_SENTENCE_WORDS_MAX)
        if is_v8
        else (
            DIORAMA_US_SENTENCE_WORDS_MAX
            if (is_us_v7 or is_micro)
            else (DIORAMA_V7_SENTENCE_WORDS_MAX if is_v7 else DIORAMA_SENTENCE_WORDS_MAX)
        )
    )
    for idx, s in enumerate(lines, start=1):
        wc = count_words(s)
        if wc > sent_words_max:
            issues.append(
                f"[diorama_script] sentence {idx} has {wc} words > max {sent_words_max}: '{s[:70]}' (R57/R57-C/R73)"
            )
        if re.search(r"[\uac00-\ud7a3\u3040-\u30ff\u4e00-\u9fff]", s):
            issues.append(f"[en_us_lock] sentence {idx} contains non-English CJK/Korean characters (R36/R57)")

    if not is_micro and not is_v8 and isinstance(script_doc, dict) and isinstance(script_doc.get("acts"), list):
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
            weak_hook_prefixes = (
                ("picture this", "suppose ")
                if is_pre_r68h_frozen_v8
                else DIORAMA_BANNED_WEAK_HOOK_PREFIXES
            )
            if any(s1_low.startswith(pref) for pref in weak_hook_prefixes):
                issues.append(
                    f"[hook_v7] sentence 1 starts with weak hypothetical opener {DIORAMA_BANNED_WEAK_HOOK_PREFIXES}: "
                    f"'{lines[0][:65]}' — open at 0.0s with concrete event/paradox shock (R57-H/R68-H)"
                )
            if is_v8:
                issues.extend(validate_script_spine_v8(lines, script_doc=script_doc, plan=plan, project_id=project_id))
                if not is_pre_r68h_frozen_v8 and isinstance(script_doc, dict) and "viewer_description" in script_doc:
                    from pipeline.publish import validate_v8_viewer_description

                    issues.extend(
                        validate_v8_viewer_description(
                            str(script_doc.get("viewer_description") or ""),
                            project_id=str(project_id or ""),
                        )
                    )
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
    if not is_v8 and bool(plan.get("require_signature_hooks", DIORAMA_REQUIRE_SIGNATURE_HOOKS)) and lines and not is_micro:
        full_low = " ".join(lines).lower()
        if is_v7 and not is_pre_r66_frozen:
            if not any(p.strip().lower() in full_low for p in DIORAMA_CRISIS_BEAT_BANK):
                issues.append("[hooks] missing crisis transition beat from DIORAMA_CRISIS_BEAT_BANK (R57)")
            if not any(p.strip().lower() in full_low for p in DIORAMA_MECHANISM_PIVOT_BANK):
                issues.append("[hooks] missing mechanism pivot phrase from DIORAMA_MECHANISM_PIVOT_BANK (R57)")
            if not any(p.strip().lower() in full_low for p in DIORAMA_EUREKA_REVEAL_BANK):
                issues.append("[hooks] missing breakthrough reveal phrase from DIORAMA_EUREKA_REVEAL_BANK (R57)")
            bridge_sent, _ = _resolve_takeaway_bridge_sentence(lines, DIORAMA_TAKEAWAY_BRIDGE_BANK)
            if bridge_sent is None:
                issues.append(
                    "[hooks] closing beat (S_N, or S_{N-1} before a final '?' open-verdict question) must open with a takeaway bridge from DIORAMA_TAKEAWAY_BRIDGE_BANK (R57)"
                )
            else:
                issues.extend(validate_takeaway_bridge_grammar(bridge_sent))

            explicit_ov = plan.get("require_open_verdict_v2")
            if explicit_ov is None and isinstance(script_doc, dict):
                explicit_ov = script_doc.get("require_open_verdict_v2")
            dossier_schema_ver = int(
                (script_doc or {}).get("dossier_schema_version") or plan.get("dossier_schema_version") or 0
            )
            if explicit_ov is None and not is_pre_schema_v2_frozen and dossier_slug and dossier_schema_ver < DOSSIER_SCHEMA_VERSION:
                try:
                    from pipeline.research_dossier import DOSSIERS_ROOT

                    d_meta_path = DOSSIERS_ROOT / dossier_slug / "dossier.json"
                    if d_meta_path.exists():
                        d_meta_doc = json.loads(d_meta_path.read_text(encoding="utf-8"))
                        dossier_schema_ver = int(d_meta_doc.get("schema_version") or 1)
                except Exception:
                    dossier_schema_ver = 0
            require_open_verdict = (
                bool(explicit_ov)
                if explicit_ov is not None
                else (not is_pre_schema_v2_frozen and dossier_schema_ver >= DOSSIER_SCHEMA_VERSION)
            )
            if require_open_verdict:
                final_s = lines[-1].strip()
                if not final_s.endswith("?") or not re.search(r"\bor\b", final_s, re.IGNORECASE):
                    issues.append(
                        "[open_verdict_v2] Schema v2 episode must close with a binary '... or ...?' open-verdict question (Stage 2 Debate Ignition)"
                    )
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
            is_r72_v8 = is_v8 and is_r72_open_world_v8_plan(plan, script_doc, project_id=project_id)
            min_cuts = (
                (
                    BRAIN_SIM_ONLY_CLIP_COUNT_RANGE[0]
                    if is_brain_only_gate
                    else (
                        R82_CLIP_COUNT_RANGE[0]
                        if is_r82_gate
                        else (
                            EXPRESSIVE_V8_R76_CLIP_COUNT_RANGE[0]
                            if is_r76_gate
                            else (
                                EXPRESSIVE_V8_LEGACY_CLIP_COUNT_MIN
                                if bool(plan.get("allow_legacy_v8_clip_count"))
                                else (
                                    SHORTS_EXPRESSIVE_V8_CLIP_COUNT_MIN
                                    if is_r72_v8
                                    else EXPRESSIVE_V8_LEGACY_INDOOR_CLIP_COUNT_RANGE[0]
                                )
                            )
                        )
                    )
                )
                if is_v8
                else (MICRO_SHORT_CUT_MIN if is_micro else (SHORTS_90S_CUT_COUNT_MIN if is_90s else DIORAMA_TARGET_CUT_MIN))
            )
            if len(clips) < min_cuts:
                issues.append(
                    f"[zero_reuse_v7] zero_clip_reuse=True requires >= {min_cuts} unique clips "
                    f"(got {len(clips)}) so dynamic holds maintain >= {min_cuts} cuts (R63/R68)"
                )
            if is_v8 and len(clips) > SHORTS_EXPRESSIVE_V8_CLIP_COUNT_MAX:
                issues.append(
                    f"[zero_reuse_v7] expressive_25d_v8 clip count {len(clips)} exceeds ceiling {SHORTS_EXPRESSIVE_V8_CLIP_COUNT_MAX} (R68)"
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
                issues.append(f"[zero_reuse_v7] sentences missing clip/hold coverage: {missing_s[:10]} (R63/R68)")
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

    if not is_v8:
        if not str(plan.get("act5_climax_episode") or "").strip():
            issues.append("[diorama_script] visual_plan.act5_climax_episode is empty (Act 5 lab crisis required) (R57)")

        outro_lines = plan.get("outro_title_lines") if isinstance(plan.get("outro_title_lines"), list) else []
        if len([x for x in outro_lines if str(x).strip()]) < 2:
            issues.append("[diorama_script] visual_plan.outro_title_lines needs 2 uppercase English lines for the Act 6 tilt-up outro (R59)")
    elif list(plan.get("outro_title_lines") or []):
        issues.append("[diorama_script] expressive_25d_v8 forbids outro_title_lines (must hard-cut at speech_end + 0.20s for seamless loop) (R68)")

    # 2. R57 / R68 100% [Number] -> [Immediate Everyday Analogy] pairing -------
    issues.extend(validate_number_analogy_pairing(lines))

    # 3. R56 / R63 / R66 / R68 Prompts, World Continuity & Filler Ban ----------
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
            # R63/R68: Enforce A-B-A spatial location continuity (>= 1 return on compact v8, >= 2 on v7)
            seen_locs: dict[str, int] = {}
            aba_returns = 0
            for idx_c, c in enumerate(clips):
                loc = str(c.get("location_id") or "").strip()
                if not loc:
                    continue
                if loc in seen_locs and idx_c - seen_locs[loc] >= 2:
                    aba_returns += 1
                seen_locs[loc] = idx_c
            min_aba = 0 if is_brain_only_gate else (1 if is_v8 else 2)
            if aba_returns < min_aba:
                issues.append(
                    f"[spatial_aba_v7] requires >= {min_aba} A-B-A spatial location_id return(s) across clips "
                    f"(found {aba_returns}) (R63/R68)"
                )
            if is_v8:
                issues.extend(validate_scene_state_continuity(plan, clips))
                from pipeline.config import (
                    EXPRESSIVE_V8_MAX_CONSECUTIVE_BRAIN_CUTS,
                    EXPRESSIVE_V8_NEURAL_DIVE_MOVES,
                    is_r74_neural_dive_v8_plan,
                )

                if (
                    is_r74_neural_dive_v8_plan(plan, script_doc, project_id=project_id)
                    and str(plan.get("visual_mode") or "NEURO_BIOLOGY").strip().upper() != "BEHAVIORAL_PSYCH"
                ):
                    brain_cams: list[str] = []
                    consec_b = 0
                    max_consec_b = 0
                    for c_r74 in clips:
                        is_b_r74 = (
                            bool(c_r74.get("brain_clip"))
                            or str(c_r74.get("grammar") or "") == "expressive_xray_brain"
                        )
                        if is_b_r74:
                            consec_b += 1
                            max_consec_b = max(max_consec_b, consec_b)
                            brain_cams.append(
                                str(c_r74.get("camera_move") or c_r74.get("camera") or "").strip().lower()
                            )
                        else:
                            consec_b = 0
                    if "neural_fpv_dive_in" not in brain_cams:
                        issues.append(
                            "[r74_neural_dive] Rule R74 requires >= 1 'neural_fpv_dive_in' 3D neural FPV dive cut "
                            "(static/distant whole-brain-only sequence forbidden) (R74)"
                        )
                    if "neural_fpv_pullback_out" not in brain_cams:
                        issues.append(
                            "[r74_neural_dive] Rule R74 requires >= 1 'neural_fpv_pullback_out' reverse FPV exit cut "
                            "to bridge deep subcortical macro back out to reality human action (R74)"
                        )
                    if max_consec_b > EXPRESSIVE_V8_MAX_CONSECUTIVE_BRAIN_CUTS:
                        issues.append(
                            f"[r74_neural_dive] {max_consec_b} consecutive brain cuts exceed ceiling "
                            f"{EXPRESSIVE_V8_MAX_CONSECUTIVE_BRAIN_CUTS} (must pull back out to human behavior between cycles) (R74)"
                        )
                issues.extend(
                    validate_r85_drone_and_viewpoint_locks(
                        plan,
                        clips,
                        lines=lines,
                        script_doc=script_doc,
                        project_id=project_id,
                    )
                )
                issues.extend(
                    validate_r86_semantic_beat_contract(
                        plan,
                        clips,
                        lines=lines,
                        script_doc=script_doc,
                        project_id=project_id,
                    )
                )
                issues.extend(
                    validate_r87_hook_contract(
                        plan,
                        clips,
                        lines=lines,
                        script_doc=script_doc,
                        project_id=project_id,
                        _include_turnaround_ban=False,
                    )
                )
                issues.extend(
                    validate_r87_turnaround_sheet_start_frame_ban(
                        plan,
                        clips,
                        script_doc=script_doc,
                        project_id=project_id,
                    )
                )
                issues.extend(
                    validate_r87_spatial_arrow_eligibility(
                        plan,
                        clips,
                        lines=lines,
                        script_doc=script_doc,
                        project_id=project_id,
                    )
                )
                issues.extend(
                    validate_r88_faceless_cast_contract(
                        plan,
                        clips,
                        script_doc=script_doc,
                        project_id=project_id,
                    )
                )
            elif is_porcelain_v7_plan(plan, *(clips or []), script_doc) and not is_pre_r66_frozen and not is_micro:
                issues.extend(
                    validate_substantive_visual_relevance(
                        plan,
                        lines,
                        clips,
                        script_doc=script_doc,
                        project_id=project_id,
                        slug=dossier_slug,
                    )
                )
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
        if not is_micro and not is_v8:
            acts_covered = {int(c.get("act") or 0) for c in clips}
            missing_acts = [a for a in range(1, DIORAMA_ACT_COUNT + 1) if a not in acts_covered]
            if missing_acts:
                issues.append(f"[diorama] base clips missing coverage for Act(s) {missing_acts} (R58)")

    # 4. Plain-language, conversational prosody & anatomy glossing -------------
    _expressive_ok = ("question mark", "exclamation mark", "em dash", "en dash", "ellipsis")
    q_count = sum(1 for s in lines if "?" in s)
    v8_open_mode = str((script_doc or {}).get("opening_mode") or plan.get("opening_mode") or EXPRESSIVE_V8_DEFAULT_OPENING_MODE).strip().lower()
    min_q = (1 if v8_open_mode in ("question", "paradox_question") else 0) if is_v8 else (1 if is_micro else (2 if is_90s else DIORAMA_MIN_CONVERSATIONAL_QUESTIONS))
    if q_count < min_q:
        issues.append(
            f"[storyteller] script has only {q_count} conversational question(s) '?' "
            f"(need >= {min_q} to avoid flat textbook reading) (R57)"
        )
    if is_v7 and not is_micro and not is_v8 and len(lines) >= 20:
        mid_lo = max(0, len(lines) // 3 - 2)
        mid_hi = min(len(lines), (2 * len(lines)) // 3 + 2)
        if not any("?" in s for s in lines[mid_lo:mid_hi]):
            issues.append(
                f"[midpoint_loop_v7] no midpoint open-loop question '?' in sentences {mid_lo + 1}..{mid_hi} "
                "to sustain AVD past 60-90s across the Act 3 -> Act 4 transition (R57-M)"
            )
    a = analyze_script(lines)
    fk_cap = (
        (EXPRESSIVE_V8_MAX_FK_GRADE if is_r73_v8 else EXPRESSIVE_V8_LEGACY_MAX_FK_GRADE)
        if is_v8
        else (DIORAMA_V7_MAX_FK_GRADE if is_us_v7 else READABILITY_SCRIPT_FK_MAX)
    )
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
    eff_jargon_cap = 0 if is_v8 else JARGON_TERMS_MAX
    if len(eff_jargon) > eff_jargon_cap:
        issues.append(f"[plain] {len(eff_jargon)} unglossed technical terms {eff_jargon} > cap {eff_jargon_cap} (R15/R57-C/R68)")
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
    from pipeline.episode_qa import verify_pre_flow_contract

    issues.extend(verify_pre_flow_contract(plan, lines, clips, script_doc=script_doc))
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










_R74B_PATHOLOGY_RE = re.compile(
    r"\b(?:sever(?:ed|ing)?|disconnect(?:ed|ion)?|damag(?:e|ed)|lesion(?:s|ed)?|offline|silenc(?:ed|ing)|"
    r"block(?:ed|ing)|impostor|imposter|blindsight|stroke|bypass(?:es|ed|ing)?|rerout(?:e|ed|ing)|"
    r"shortcut|split[-\s]brain|inhibit(?:ed|ion)?|cut\s+off|broken\s+link)\b",
    flags=re.IGNORECASE,
)





def validate_r76_brain_simulator_and_pacing_contract(
    plan: dict[str, Any] | None,
    clips: list[dict[str, Any]] | None,
    *,
    lines: list[str] | None = None,
    script_doc: dict[str, Any] | None = None,
    project_id: str | None = None,
    edl: dict[str, Any] | None = None,
) -> list[str]:
    """
    Rule R76 & R76-P Contract Validator:
      - Clip count inside `EXPRESSIVE_V8_R76_CLIP_COUNT_RANGE` (`15..22`) for anti-noise breathing room.
      - Solo `Siren` narrator (`100%` `narrator`, `0` foil sentences, `0` `Mini-Cortex` cameos).
      - Zero Google Flow `expressive_xray_brain` or `neural_fpv_*` tunnel filler; every brain shot uses `brain_simulator_3d`
        with `camera_move in EXPRESSIVE_V8_BRAIN_SIM_DRONE_MOVES` and valid MNI152 anatomy region(s).
      - Unified `38%–48%` brain simulator share across psychology & neuroscience (pre-EDL count range `33%–52%`, exact EDL duration `38%–48%`),
        plus `R76-P` cut duration floors (`>= 2.80s` human, `>= 3.80s` brain, `<= 6.50s` max, avg `3.40–5.20s`).
    """
    from pipeline.anatomy_map import resolve_anatomy_screen_anchor
    from pipeline.config import (
        BRAIN_SIM_ONLY_CLIP_COUNT_RANGE,
        DATA_STAMP_MIN_PER_EPISODE,
        EXPRESSIVE_V8_BRAIN_SIM_DRONE_MOVES,
        EXPRESSIVE_V8_NEURAL_DIVE_MOVES,
        EXPRESSIVE_V8_R76_AVG_CUT_TARGET_RANGE,
        EXPRESSIVE_V8_R76_BRAIN_SIM_MIN_CUT_SEC,
        EXPRESSIVE_V8_R76_CLIP_COUNT_RANGE,
        EXPRESSIVE_V8_R76_HUMAN_MIN_CUT_SEC,
        EXPRESSIVE_V8_R76_MAX_CUT_SEC,
        EXPRESSIVE_V8_SPATIAL_RELAY_MIN_CUT_SEC,
        EXPRESSIVE_V8_UNIFIED_BRAIN_SIM_DURATION_RATIO_RANGE,
        R82_AVG_CUT_TARGET_RANGE,
        R82_BRAIN_BANNED_FAST_MOTION_TOKENS,
        R82_BRAIN_CLIP_RATIO_RANGE,
        R82_BRAIN_DURATION_RATIO_RANGE,
        R82_BRAIN_MAX_CUT_SEC,
        R82_BRAIN_MIN_CUT_SEC,
        R82_CLIP_COUNT_RANGE,
        R82_HUMAN_MAX_CUT_SEC,
        R82_HUMAN_MIN_CUT_SEC,
        is_brain_sim_only_plan,
        is_r82_dual_speed_pacing_plan,
    )

    _ = lines
    p = plan if isinstance(plan, dict) else {}
    s = script_doc if isinstance(script_doc, dict) else {}
    is_brain_only = is_brain_sim_only_plan(p, s)
    is_r82 = is_r82_dual_speed_pacing_plan(p, s, project_id=project_id)
    clip_list = clips if isinstance(clips, list) else list(p.get("clips") or [])
    raw_vp_clips = p.get("clips") if isinstance(p.get("clips"), list) else []
    issues: list[str] = []

    if not clip_list:
        return ["[r76] empty clip list"]

    c_lo, c_hi = (
        BRAIN_SIM_ONLY_CLIP_COUNT_RANGE
        if is_brain_only
        else (R82_CLIP_COUNT_RANGE if is_r82 else EXPRESSIVE_V8_R76_CLIP_COUNT_RANGE)
    )
    if not (c_lo <= len(clip_list) <= c_hi):
        issues.append(
            f"[r76_pacing] clip count {len(clip_list)} outside {'brain_simulator_3d_only' if is_brain_only else ('Rule R82 dual-speed' if is_r82 else 'Rule R76-P anti-noise')} range [{c_lo}..{c_hi}] ({'R82' if is_r82 else 'R76-P/R77'})"
        )

    if is_r82:
        stamps_r82 = (
            s.get("data_stamps")
            if isinstance(s.get("data_stamps"), list)
            else (p.get("data_stamps") if isinstance(p.get("data_stamps"), list) else [])
        )
        if len(stamps_r82) < DATA_STAMP_MIN_PER_EPISODE:
            issues.append(
                f"[r82_data_stamps] Rule R82 requires >= {DATA_STAMP_MIN_PER_EPISODE} R70-M data_stamps for empirical comparison clarity (got {len(stamps_r82)}) (R82)"
            )

    speakers = s.get("sentence_speakers")
    if isinstance(speakers, list) and speakers:
        non_narr = [(i + 1, sp) for i, sp in enumerate(speakers) if str(sp or "").strip().lower() != "narrator"]
        if non_narr:
            issues.append(
                f"[r76_solo_voice] Rule R76 locks 100% solo Siren narrator; non-narrator sentences={non_narr[:4]} (R76)"
            )
    if list(s.get("foil_sentence_indices") or []):
        issues.append("[r76_solo_voice] Rule R76 forbids foil_sentence_indices (must be empty) (R76)")

    brain_count = 0
    for idx0, c in enumerate(clip_list):
        if not isinstance(c, dict):
            continue
        vp_c = raw_vp_clips[idx0] if idx0 < len(raw_vp_clips) and isinstance(raw_vp_clips[idx0], dict) else {}
        g = str(c.get("grammar") or vp_c.get("grammar") or "").strip()
        cam = str(c.get("camera_move") or vp_c.get("camera_move") or c.get("camera") or vp_c.get("camera") or "").strip().lower()
        eng = str(c.get("render_engine") or vp_c.get("render_engine") or "").strip().lower()
        is_cameo = bool(c.get("cameo_easter_egg") or vp_c.get("cameo_easter_egg")) or g == "expressive_cameo_world"
        if is_cameo:
            issues.append(f"[r76_cameo_retired] clip {idx0 + 1}: Mini-Cortex cameo is retired under Rule R76 (R76)")
        if g == "expressive_xray_brain" or cam in EXPRESSIVE_V8_NEURAL_DIVE_MOVES:
            issues.append(
                f"[r76_brain_simulator] clip {idx0 + 1}: forbids Google Flow 'expressive_xray_brain' / '{cam}' filler; "
                "use Blender 4.2 / R78-M 'brain_simulator_3d' (R76)"
            )
        is_b = g == "brain_simulator_3d" or eng == "blender_3d_simulator" or bool(c.get("brain_clip") or vp_c.get("brain_clip"))
        if is_b:
            brain_count += 1
            if g != "brain_simulator_3d":
                issues.append(f"[r76_brain_simulator] clip {idx0 + 1}: brain cut must use grammar='brain_simulator_3d', got '{g}' (R76)")
            if cam not in EXPRESSIVE_V8_BRAIN_SIM_DRONE_MOVES:
                issues.append(
                    f"[r76_brain_simulator] clip {idx0 + 1}: brain_simulator_3d camera '{cam}' must be in {list(EXPRESSIVE_V8_BRAIN_SIM_DRONE_MOVES)} (R76)"
                )
            r_start = str(c.get("start_brain_region") or vp_c.get("start_brain_region") or c.get("brain_region") or vp_c.get("brain_region") or "").strip()
            r_end = str(c.get("end_brain_region") or vp_c.get("end_brain_region") or "").strip()
            if not r_start or resolve_anatomy_screen_anchor(r_start) is None:
                issues.append(f"[r76_brain_simulator] clip {idx0 + 1}: missing/unknown start MNI152 brain_region '{r_start}' (R76)")
            if r_end and resolve_anatomy_screen_anchor(r_end) is None:
                issues.append(f"[r76_brain_simulator] clip {idx0 + 1}: unknown end_brain_region '{r_end}' (R76)")
            if is_r82:
                b_txt_low = " ".join(
                    str(x or "")
                    for x in (
                        c.get("r78m_flow_prompt"),
                        vp_c.get("r78m_flow_prompt"),
                        c.get("scene"),
                        vp_c.get("scene"),
                        c.get("action"),
                        vp_c.get("action"),
                    )
                ).lower()
                for bad_tok in R82_BRAIN_BANNED_FAST_MOTION_TOKENS:
                    if bad_tok in b_txt_low:
                        issues.append(
                            f"[r82_calm_brain] clip {idx0 + 1}: brain prompt contains frantic motion token '{bad_tok}' — keep brain camera poised (<=12-15 deg micro-parallax, zero spin) (R82)"
                        )

    cnt_share = brain_count / float(max(1, len(clip_list)))
    cnt_lo, cnt_hi = R82_BRAIN_CLIP_RATIO_RANGE if is_r82 else (0.33, 0.52)
    if is_brain_only:
        if brain_count != len(clip_list):
            issues.append(
                f"[r77_brain_only] brain_simulator_3d_only mode requires 100% brain_simulator_3d clips ({brain_count}/{len(clip_list)}) (R77)"
            )
    elif not (cnt_lo - 1e-6 <= cnt_share <= cnt_hi + 1e-6):
        issues.append(
            f"[r76_brain_share] brain simulator clip share {brain_count}/{len(clip_list)} ({cnt_share:.1%}) "
            f"outside pre-EDL target band [{cnt_lo:.0%}..{cnt_hi:.0%}] ({'R82' if is_r82 else 'R76'})"
        )

    if isinstance(edl, dict) and isinstance(edl.get("cuts"), list):
        cuts = [ct for ct in edl["cuts"] if isinstance(ct, dict) and not ct.get("outro_sky_card")]
        if cuts:
            tot_d = sum(float(ct.get("duration_sec") or 0.0) for ct in cuts)
            b_d = sum(
                float(ct.get("duration_sec") or 0.0)
                for ct in cuts
                if str(ct.get("grammar") or "") == "brain_simulator_3d" or str(ct.get("render_engine") or "") == "blender_3d_simulator"
            )
            dur_share = b_d / float(max(0.01, tot_d))
            sh_lo, sh_hi = (
                (0.99, 1.0)
                if is_brain_only
                else (R82_BRAIN_DURATION_RATIO_RANGE if is_r82 else EXPRESSIVE_V8_UNIFIED_BRAIN_SIM_DURATION_RATIO_RANGE)
            )
            if not (sh_lo - 1e-4 <= dur_share <= sh_hi + 1e-4):
                issues.append(
                    f"[r76_brain_share] unified brain simulator duration share {b_d:.2f}s/{tot_d:.2f}s ({dur_share:.1%}) "
                    f"outside [{sh_lo:.0%}..{sh_hi:.0%}] ({'R82' if is_r82 else 'R76'})"
                )
            for ct in cuts:
                dur_c = float(ct.get("duration_sec") or 0.0)
                is_bc = str(ct.get("grammar") or "") == "brain_simulator_3d" or str(ct.get("render_engine") or "") == "blender_3d_simulator"
                is_sp_relay = (
                    str(ct.get("grammar") or "") == "spatial_3d_arrow_diorama"
                    or bool(ct.get("spatial_relay_cut"))
                )
                if is_brain_only:
                    floor_c, ceil_c = 1.40, 9.50
                elif is_r82:
                    floor_c = R82_BRAIN_MIN_CUT_SEC if is_bc else R82_HUMAN_MIN_CUT_SEC
                    ceil_c = R82_BRAIN_MAX_CUT_SEC if is_bc else R82_HUMAN_MAX_CUT_SEC
                else:
                    floor_c = (
                        EXPRESSIVE_V8_R76_BRAIN_SIM_MIN_CUT_SEC
                        if is_bc
                        else (EXPRESSIVE_V8_SPATIAL_RELAY_MIN_CUT_SEC if is_sp_relay else EXPRESSIVE_V8_R76_HUMAN_MIN_CUT_SEC)
                    )
                    ceil_c = EXPRESSIVE_V8_R76_MAX_CUT_SEC
                if dur_c + 0.002 < floor_c:
                    issues.append(
                        f"[r76_pacing] cut {ct.get('cut_index')}: duration {dur_c:.2f}s < {'brain' if is_bc else ('spatial_relay' if is_sp_relay else 'human')} floor {floor_c:.2f}s ({'R82' if is_r82 else 'R76-P'})"
                    )
                if dur_c > ceil_c + 0.002:
                    issues.append(
                        f"[r76_pacing] cut {ct.get('cut_index')}: duration {dur_c:.2f}s > {'brain' if is_bc else 'human'} ceiling {ceil_c:.2f}s ({'R82' if is_r82 else 'R76-P'})"
                    )
            avg_d = tot_d / float(len(cuts))
            av_lo, av_hi = (
                (2.50, 7.50)
                if is_brain_only
                else (R82_AVG_CUT_TARGET_RANGE if is_r82 else EXPRESSIVE_V8_R76_AVG_CUT_TARGET_RANGE)
            )
            if not (av_lo - 0.005 <= avg_d <= av_hi + 0.005):
                issues.append(
                    f"[r76_pacing] mean cut duration {avg_d:.2f}s outside target [{av_lo:.2f}..{av_hi:.2f}]s ({'R82' if is_r82 else 'R76-P'})"
                )

    return issues



_R85_DRONE_GROUND_VERB_RE = re.compile(
    r"\b(?:walk|walks|walking|walked|stride|strides|striding|stroll|strolls|strolling|beside)\b",
    flags=re.IGNORECASE,
)


def validate_r85_drone_and_viewpoint_locks(
    plan: dict[str, Any] | None,
    clips: list[dict[str, Any]] | None,
    *,
    lines: list[str] | None = None,
    script_doc: dict[str, Any] | None = None,
    project_id: str | None = None,
) -> list[str]:
    """
    Rule R85 Prompt & Anatomy Contract Validator:
      1. Aerial drone / exterior establishing cuts forbid ground-level walking/character verbs
         (`walk|stride|stroll|beside`) and forbid `human_action_relay=True`.
      2. Anatomical Viewpoint Lock (`R85_ANATOMY_VIEWPOINT_RULES`):
         - `insula` -> `lateral_opercular_retracted` ONLY (`midsagittal` strictly forbidden!).
         - `hippocampus` -> `inferior_lateral_cutaway` or `coronal_cutaway` (dorsal callosum highlight forbidden).
         - `thalamus` / `brainstem` / `csf` -> `midsagittal_cutaway` (lateral cortical surface forbidden).
         - `prefrontal cortex` -> `anterior_three_quarter_lateral`.
      3. When `is_r85_flow_31_brain_plan` is active:
         - Forbids `brain_simulator_3d` / `blender_3d_simulator` on-screen clips (100% Google Flow Ep #31 brain).
         - Enforces intra-episode organ-to-color semantics consistency.
    """
    from pipeline.config import (
        DATA_STAMP_MIN_PER_EPISODE,
        PRE_R76_FROZEN_V8_PROJECTS,
        R85_ANATOMY_VIEWPOINT_RULES,
        R85_BRAIN_ANTI_VFX_NEGATIVE_CLAUSE,
        R85_BRAIN_BANNED_VFX_TOKENS,
        R85_DRONE_ALTITUDE_LOCK_CLAUSE,
        R85_FLOW_BRAIN_SHOT_ROTATION,
        R85_RETIRED_DERIVATIVE_BRAIN_ANCHORS,
        is_r85_flow_31_brain_plan,
    )
    from pipeline.depiction_rules import FLOW_CAMERA_HARDWARE_NEGATIVE_GUARD

    _ = lines
    p = plan if isinstance(plan, dict) else {}
    s = script_doc if isinstance(script_doc, dict) else {}
    eff_pid = str(project_id or p.get("project_id") or s.get("project_id") or "").strip()
    if eff_pid in PRE_R76_FROZEN_V8_PROJECTS or bool(p.get("allow_legacy_pre_r76")):
        return []
    if any(tok in eff_pid.lower() for tok in ("_unit_test", "_unit_check", "_synth", "_dryrun", "v8_ep07_unit_test")):
        if not bool(p.get("r85_mode")) and not bool(p.get("enforce_r85_lint")):
            return []

    is_r85 = is_r85_flow_31_brain_plan(p, s, project_id=eff_pid)
    clip_list = clips if isinstance(clips, list) else list(p.get("clips") or [])
    raw_vp_clips = p.get("clips") if isinstance(p.get("clips"), list) else []
    issues: list[str] = []
    organ_color_ledger: dict[tuple[str, str], str] = {}
    vfx_alt = "|".join(re.escape(tok) for tok in sorted(R85_BRAIN_BANNED_VFX_TOKENS, key=len, reverse=True))
    vfx_ban_re = re.compile(rf"(?<![A-Za-z-])(?:{vfx_alt})(?![A-Za-z-])", flags=re.IGNORECASE)
    neg_vfx_guard_re = re.compile(
        rf"\b(?:zero|no|without|never)\s+(?:[A-Za-z-]+\s+){{0,2}}(?:{vfx_alt})\b",
        flags=re.IGNORECASE,
    )

    def _find_r85_vfx_violations(raw_corpus: str) -> list[str]:
        scrubbed = (
            str(raw_corpus or "")
            .replace(FLOW_CAMERA_HARDWARE_NEGATIVE_GUARD, " ")
            .replace(R85_BRAIN_ANTI_VFX_NEGATIVE_CLAUSE, " ")
        )
        scrubbed = neg_vfx_guard_re.sub(" ", scrubbed)
        return sorted({m.group(0).lower() for m in vfx_ban_re.finditer(scrubbed)})

    if is_r85:
        stamps_r85 = (
            s.get("data_stamps")
            if isinstance(s.get("data_stamps"), list)
            else (p.get("data_stamps") if isinstance(p.get("data_stamps"), list) else [])
        )
        if len(stamps_r85) < DATA_STAMP_MIN_PER_EPISODE and not bool(p.get("skip_r85_stamp_count_in_unit_test")):
            issues.append(
                f"[r85_data_stamps] Rule R85 requires >= {DATA_STAMP_MIN_PER_EPISODE} verified study data_stamps (got {len(stamps_r85)}) (R85)"
            )
        speakers = s.get("sentence_speakers")
        if isinstance(speakers, list) and speakers:
            non_narr = [(i + 1, sp) for i, sp in enumerate(speakers) if str(sp or "").strip().lower() != "narrator"]
            if non_narr:
                issues.append(f"[r85_solo_voice] Rule R85 locks 100% solo Siren narrator; got {non_narr[:4]} (R85)")

    for idx0, c in enumerate(clip_list):
        if not isinstance(c, dict):
            continue
        idx = idx0 + 1
        vp_c = raw_vp_clips[idx0] if idx0 < len(raw_vp_clips) and isinstance(raw_vp_clips[idx0], dict) else {}
        g = str(c.get("grammar") or vp_c.get("grammar") or "").strip()
        cam = str(c.get("camera_move") or vp_c.get("camera_move") or c.get("camera") or vp_c.get("camera") or "").strip().lower()
        eng = str(c.get("render_engine") or vp_c.get("render_engine") or "").strip().lower()
        sc_txt = " ".join(
            str(x or "")
            for x in (
                c.get("scene"),
                vp_c.get("scene"),
                c.get("action"),
                vp_c.get("action"),
                c.get("prompt"),
            )
        )
        sc_clean = (
            sc_txt.replace(FLOW_CAMERA_HARDWARE_NEGATIVE_GUARD, " ")
            .replace(R85_DRONE_ALTITUDE_LOCK_CLAUSE, " ")
        )

        # 1. Drone / Exterior Establishing Ground-Verb Ban
        is_aerial_drone = cam in (
            "drone_aerial_approach",
            "drone_landmark_ascend",
            "drone_high_orbit_drop",
            "drone_skyline_pullback",
        ) or g == "expressive_exterior_establishing"
        if is_aerial_drone:
            m_gv = _R85_DRONE_GROUND_VERB_RE.search(sc_clean)
            if m_gv:
                issues.append(
                    f"[r85_drone_ground_verb] clip {idx}: aerial/establishing clip ('{cam or g}') contains ground-level "
                    f"pedestrian/character token '{m_gv.group(0).lower()}'; figures must remain 120ft tiny dots (R85)"
                )
            if bool(c.get("human_action_relay") or vp_c.get("human_action_relay")) and cam in (
                "drone_aerial_approach",
                "drone_landmark_ascend",
                "drone_high_orbit_drop",
                "drone_skyline_pullback",
            ):
                issues.append(
                    f"[r85_drone_relay_conflict] clip {idx}: aerial drone camera '{cam}' cannot set human_action_relay=True (R85)"
                )

        # 2. Blender Screen Render Retirement on R85
        is_brain = g in ("expressive_xray_brain", "brain_simulator_3d") or bool(c.get("brain_clip") or vp_c.get("brain_clip"))
        if is_r85 and (g == "brain_simulator_3d" or eng == "blender_3d_simulator"):
            issues.append(
                f"[r85_blender_retired] clip {idx}: direct Blender '{g or eng}' clip is retired under Rule R85; "
                "render 100% via Google Flow Ep #31 6-Scale brain (R85)"
            )

        # 3. Anatomical Viewpoint & Intra-Episode Color Lock
        callout_obj = c.get("r78m_callout") or vp_c.get("r78m_callout") or {}
        callout_txt = json.dumps(callout_obj, ensure_ascii=False) if isinstance(callout_obj, dict) else str(callout_obj or "")
        reg_raw = " ".join(
            str(x or "")
            for x in (
                c.get("brain_region"),
                vp_c.get("brain_region"),
                c.get("start_brain_region"),
                vp_c.get("start_brain_region"),
                c.get("end_brain_region"),
                vp_c.get("end_brain_region"),
                c.get("anatomy_label"),
                vp_c.get("anatomy_label"),
                callout_txt,
            )
        ).lower()
        vp_val = str(
            c.get("viewpoint")
            or vp_c.get("viewpoint")
            or c.get("surgical_cutaway")
            or vp_c.get("surgical_cutaway")
            or ""
        ).strip().lower()
        view_corpus = f"{vp_val} {sc_txt} {c.get('r78m_flow_prompt') or vp_c.get('r78m_flow_prompt') or ''} {c.get('brain_mode') or ''}".lower()

        if is_brain or vp_val:
            if "insul" in reg_raw:
                if (
                    any(fb in view_corpus for fb in ("midsagittal", "mid-sagittal", "sagittal_midline", "sagittal section", "midline sagittal"))
                    or (is_r85 and vp_val not in R85_ANATOMY_VIEWPOINT_RULES["insula"]["allowed"])
                ):
                    issues.append(
                        f"[r85_anatomy_viewpoint] clip {idx}: insula cannot be depicted in midsagittal cutaway "
                        f"(got viewpoint='{vp_val or 'unspecified'}'); require 'lateral_opercular_retracted' (R85)"
                    )
            if "hippocamp" in reg_raw:
                if (
                    any(fb in view_corpus for fb in R85_ANATOMY_VIEWPOINT_RULES["hippocampus"]["forbidden"])
                    or (is_r85 and vp_val and vp_val not in R85_ANATOMY_VIEWPOINT_RULES["hippocampus"]["allowed"])
                ):
                    issues.append(
                        f"[r85_anatomy_viewpoint] clip {idx}: hippocampus requires 'inferior_lateral_cutaway' or 'coronal_cutaway' "
                        f"(got '{vp_val}') (R85)"
                    )
            if any(tk in reg_raw for tk in ("thalam", "brainstem", "csf")) and "insul" not in reg_raw and "hippocamp" not in reg_raw:
                if (
                    any(fb in view_corpus for fb in R85_ANATOMY_VIEWPOINT_RULES["thalamus"]["forbidden"])
                    or (is_r85 and vp_val and vp_val not in R85_ANATOMY_VIEWPOINT_RULES["csf"]["allowed"])
                ):
                    issues.append(
                        f"[r85_anatomy_viewpoint] clip {idx}: thalamus/brainstem/CSF requires 'midsagittal_cutaway' "
                        f"(got '{vp_val}') (R85)"
                    )
            if is_r85:
                shot_sc = str(c.get("r85_shot_scale") or vp_c.get("r85_shot_scale") or "").strip()
                if shot_sc and shot_sc not in R85_FLOW_BRAIN_SHOT_ROTATION:
                    issues.append(
                        f"[r85_shot_scale] clip {idx}: invalid r85_shot_scale='{shot_sc}' "
                        f"(must be in {list(R85_FLOW_BRAIN_SHOT_ROTATION)}) (R85)"
                    )
                if is_brain:
                    vfx_hits = _find_r85_vfx_violations(
                        " ".join(
                            str(x or "")
                            for x in (
                                c.get("scene"),
                                vp_c.get("scene"),
                                c.get("action"),
                                vp_c.get("action"),
                                c.get("prompt"),
                                c.get("r78m_flow_prompt"),
                                vp_c.get("r78m_flow_prompt"),
                            )
                        )
                    )
                    if vfx_hits:
                        issues.append(
                            f"[r85_brain_banned_vfx] clip {idx}: R85 Episode #31 brain forbids AI VFX/glow/glass token(s) "
                            f"{vfx_hits}; use matte silver-white sculpted gypsum cortex, opaque #27D8FF sulcal tubes, and solid matte structure colors (R85)"
                        )

            # Intra-episode color consistency (catches Ep11 C10/C17/C18 color-role swapping!)
            n_state = str(c.get("neural_state") or vp_c.get("neural_state") or "active").strip().lower()
            if isinstance(callout_obj, dict):
                for side_lbl_k, side_rgb_k in (("left_lbl", "left_rgb"), ("right_lbl", "right_rgb")):
                    lbl_s = str(callout_obj.get(side_lbl_k) or "").strip().lower()
                    rgb_v = callout_obj.get(side_rgb_k)
                    if lbl_s and isinstance(rgb_v, list) and len(rgb_v) == 3:
                        organ_norm = re.sub(r"\b(?:fold|hub|zone|cortex|lobe|area)\b", "", lbl_s).strip()
                        key_oc = (organ_norm or lbl_s, n_state)
                        rgb_sig = f"{int(rgb_v[0])},{int(rgb_v[1])},{int(rgb_v[2])}"
                        prev_sig = organ_color_ledger.get(key_oc)
                        if prev_sig is not None and prev_sig != rgb_sig:
                            issues.append(
                                f"[r85_color_semantics_flip] clip {idx}: structure '{lbl_s}' (state='{n_state}') "
                                f"flipped RGB from [{prev_sig}] to [{rgb_sig}] mid-episode (R85)"
                            )
                        else:
                            organ_color_ledger[key_oc] = rgb_sig
            func_col = str(c.get("functional_highlight_color") or vp_c.get("functional_highlight_color") or "").strip().lower()
            prim_reg = str(c.get("brain_region") or vp_c.get("brain_region") or "").strip().lower()
            if prim_reg and func_col:
                key_fc = (prim_reg, n_state)
                prev_fc = organ_color_ledger.get(key_fc)
                if prev_fc is not None and prev_fc != func_col:
                    issues.append(
                        f"[r85_color_semantics_flip] clip {idx}: brain_region '{prim_reg}' (state='{n_state}') "
                        f"flipped highlight color from '{prev_fc}' to '{func_col}' mid-episode (R85)"
                    )
                else:
                    organ_color_ledger[key_fc] = func_col

    if is_r85:
        for anc in p.get("reference_anchors") or []:
            if not isinstance(anc, dict):
                continue
            if not (bool(anc.get("r85_brain_clip")) or str(anc.get("setting") or "") == "brain_studio"):
                continue
            rid_a = str(anc.get("ref_id") or anc.get("filename") or "brain_anchor")
            anc_vfx = _find_r85_vfx_violations(str(anc.get("prompt") or ""))
            if anc_vfx:
                issues.append(
                    f"[r85_brain_banned_vfx] reference_anchor '{rid_a}': R85 Episode #31 brain keyframe forbids AI VFX/glow/glass token(s) "
                    f"{anc_vfx} (R85)"
                )
            bad_conds = [
                str(cid)
                for cid in (anc.get("conditioned_on") or [])
                if str(cid) in R85_RETIRED_DERIVATIVE_BRAIN_ANCHORS
            ]
            if bad_conds:
                issues.append(
                    f"[r85_retired_brain_anchor] reference_anchor '{rid_a}' conditions on retired 2nd-gen derivative anchor(s) "
                    f"{bad_conds}; use genuine 31_O2CmlKOk anchors (R85)"
                )

    return issues



def validate_r86_semantic_beat_contract(
    plan: dict[str, Any] | None,
    clips: list[dict[str, Any]] | None,
    *,
    lines: list[str] | None = None,
    script_doc: dict[str, Any] | None = None,
    project_id: str | None = None,
) -> list[str]:
    """
    Rule R86 Semantic Beat Contract & Anti-Filler Validator (`Independent Visual Reviewer (Gate 1/2)` Teardown + `Fresh-Room Owner` Schema Lock):
      1. Required per-cut Beat Card fields on R86 plans:
         `claim`, `viewer_must_understand`, `visual_proof_type` (8 types, `decorative` = 0),
         `visual_register` (`story` | `diagram`), `concrete_referent`, `anti_filler_check`.
      2. `concrete_referent` content tokens must appear in `scene`/`action`, and off-claim busywork
         (`Ep12 C23` cutting parcel twine on doorway-cue sentence, `Ep12 C05` reading bench tablet on
         shutting-shoebox-lid sentence, `Ep12 C19` empty-handed forehead clutch in brick ruins on
         two-task memory-slot overload sentence) is hard-rejected.
      3. `< 3` consecutive identical `visual_proof_type` cuts; `<= 2` `reaction` cuts per episode; `0` decorative cuts.
      4. `metaphor_continuity_id` spans `3..5` cuts and requires non-empty `bridge_element` when returning to anatomy.
      5. Consecutive same-`concept_id` cuts require distinct `state_delta`; zero-delta brain repetition (`R84` 7x same
         angle/region/state) is hard-rejected (`[r86_zero_visual_delta]`).
      6. `misconception_flip` requires `mechanism_seed` (or immediate next-cut mechanism/causal_arrow) — pure rejection fails.
    """
    from pipeline.config import (
        R86_MAX_CONSECUTIVE_SAME_PROOF,
        R86_MAX_REACTION_CUTS_PER_EPISODE,
        R86_VISUAL_PROOF_TYPES,
        is_r86_semantic_beat_plan,
    )

    p = plan if isinstance(plan, dict) else {}
    s = script_doc if isinstance(script_doc, dict) else {}
    eff_pid = str(project_id or p.get("project_id") or s.get("project_id") or "").strip()
    enforce_schema = is_r86_semantic_beat_plan(p, s, project_id=eff_pid)
    enforce_anti_filler = enforce_schema or bool(p.get("enforce_r86_anti_filler"))
    if not enforce_anti_filler:
        return []

    clip_list = clips if isinstance(clips, list) else list(p.get("clips") or [])
    raw_vp_clips = p.get("clips") if isinstance(p.get("clips"), list) else []
    sent_lines = list(lines or s.get("sentences") or p.get("sentences") or [])
    issues: list[str] = []

    proof_seq: list[tuple[int, str]] = []
    reaction_cuts: list[int] = []
    metaphor_runs: dict[str, list[int]] = {}
    prev_concept_id = ""
    prev_state_delta = ""
    brain_signatures: dict[tuple[str, str, str, str], list[int]] = {}

    _EN_STOP = {
        "with", "from", "into", "onto", "over", "under", "across", "along", "through", "before", "after",
        "their", "there", "where", "while", "when", "this", "that", "these", "those", "inside", "outside",
        "person", "figure", "character", "woman", "scene", "frame",
    }

    for idx0, c in enumerate(clip_list):
        if not isinstance(c, dict):
            continue
        idx = idx0 + 1
        vp_c = raw_vp_clips[idx0] if idx0 < len(raw_vp_clips) and isinstance(raw_vp_clips[idx0], dict) else {}
        if bool(c.get("outro_sky_card") or vp_c.get("outro_sky_card")):
            continue

        def _f(k: str) -> Any:
            return c.get(k) if c.get(k) is not None else vp_c.get(k)

        g = str(_f("grammar") or "").strip()
        cam = str(_f("camera_move") or _f("camera") or "").strip().lower()
        is_brain = g in ("expressive_xray_brain", "brain_simulator_3d") or bool(_f("brain_clip"))
        s_idx = int(_f("sentence_index") or 0)
        spoken_s = str(sent_lines[s_idx - 1]).strip() if (1 <= s_idx <= len(sent_lines)) else ""
        scene_txt = " ".join(str(x or "") for x in (_f("scene"), _f("action"), c.get("prompt"), _f("r78m_flow_prompt"))).strip()
        scene_low = scene_txt.lower()
        claim = str(_f("claim") or "").strip()
        v_goal = str(_f("viewer_must_understand") or "").strip()
        proof_t = str(_f("visual_proof_type") or "").strip().lower()
        v_reg = str(_f("visual_register") or "").strip().lower()
        c_ref = str(_f("concrete_referent") or "").strip()
        m_cid = str(_f("metaphor_continuity_id") or "").strip()
        bridge_el = str(_f("bridge_element") or "").strip()
        concept_id = str(_f("concept_id") or "").strip()
        st_delta = str(_f("state_delta") or "").strip()
        mech_seed = str(_f("mechanism_seed") or "").strip()
        af_chk = str(_f("anti_filler_check") or "").strip()

        # Anti-busywork / off-claim semantic checks (always run when enforce_anti_filler is True!)
        claim_or_spoken = f"{claim} {spoken_s}".lower()
        if re.search(r"\b(?:say one word out loud|before any door|carry one clue)\b", claim_or_spoken):
            if re.search(r"\b(?:snip\w*|twine|parcel|string|ribbon)\b", scene_low) and not re.search(
                r"\b(?:door\w*|threshold|doorframe)\b", scene_low
            ):
                issues.append(
                    f"[r86_decorative_busywork] clip {idx}: busywork action (cutting twine/parcel at table) fails to depict "
                    "doorway memory-anchoring claim ('carry one clue / say one word before any door') (R86)"
                )
        if re.search(r"\b(?:tucked .* block .* box|shut the lid|closed? the lid)\b", claim_or_spoken):
            if re.search(r"\b(?:bench|tablet|clipboard|newspaper)\b", scene_low) and not re.search(
                r"\b(?:lid|shoebox|box|block)\b", scene_low
            ):
                issues.append(
                    f"[r86_semantic_exhaustion] clip {idx}: off-claim scene ('bench/tablet') omits core experimental condition "
                    "('shutting box lid to hide red block from sight') (R86)"
                )
        if re.search(r"\b(?:holding two tasks|two tasks in mind|zero grip at the door)\b", claim_or_spoken):
            if re.search(r"\b(?:forehead|rubs his temple|clutches his head|cracked brick|ruin)\b", scene_low) and not re.search(
                r"\b(?:two|both arms|stack|slip\w*|drop\w*|tumble\w*)\b", scene_low
            ):
                issues.append(
                    f"[r86_missing_causal_mechanism] clip {idx}: generic head-clutching / ruin reaction omits working-memory "
                    "dual-object overload mechanism at the doorway (R86)"
                )

        # Zero-delta repeated brain cuts check (catches R84's 7 identical-angle gray brain repeats!)
        if is_brain:
            b_reg = str(_f("brain_region") or _f("start_brain_region") or "").strip().lower()
            b_end = str(_f("end_brain_region") or "").strip().lower()
            b_st = str(_f("neural_state") or "active").strip().lower()
            b_vp = str(_f("viewpoint") or _f("r85_shot_scale") or "").strip().lower()
            sig = (f"{b_reg}->{b_end}", cam, b_st, b_vp)
            brain_signatures.setdefault(sig, []).append(idx)

        if not enforce_schema:
            continue

        # 1. Required Beat Card fields
        for req_k, req_v in (
            ("claim", claim),
            ("viewer_must_understand", v_goal),
            ("visual_proof_type", proof_t),
            ("visual_register", v_reg),
            ("concrete_referent", c_ref),
            ("anti_filler_check", af_chk),
        ):
            if not req_v:
                issues.append(f"[r86_missing_field] clip {idx}: missing/blank Beat Card field '{req_k}' (R86)")
        if af_chk and len(af_chk) < 12:
            issues.append(f"[r86_anti_filler_too_short] clip {idx}: anti_filler_check too short (<12 chars) (R86)")

        # 2. Proof type & decorative ban
        if proof_t in ("decorative", "decorative_filler", "filler"):
            issues.append(f"[r86_decorative_forbidden] clip {idx}: decorative filler cuts are strictly forbidden (0 allowed) (R86)")
        elif proof_t and proof_t not in R86_VISUAL_PROOF_TYPES:
            issues.append(
                f"[r86_invalid_proof_type] clip {idx}: visual_proof_type='{proof_t}' must be in {list(R86_VISUAL_PROOF_TYPES)} (R86)"
            )
        if proof_t:
            proof_seq.append((idx, proof_t))
            if proof_t == "reaction":
                reaction_cuts.append(idx)

        # 3. visual_register ('story' vs 'diagram') alternation & overlay discipline
        if v_reg and v_reg not in ("story", "diagram"):
            issues.append(f"[r86_invalid_register] clip {idx}: visual_register='{v_reg}' must be 'story' or 'diagram' (R86)")
        elif v_reg == "story":
            if is_brain or g == "spatial_3d_arrow_diorama" or bool(_f("r78m_callout")) or bool(_f("has_data_stamp")):
                issues.append(
                    f"[r86_register_overlay_conflict] clip {idx}: visual_register='story' must stay 0%-overlay clean "
                    "(move brain/arrow/callout/stamp cuts to visual_register='diagram') (R86)"
                )
        elif v_reg == "diagram":
            if re.search(r"\b(?:cluttered|crowded|messy|packed shelves|busy crowd)\b", scene_low):
                issues.append(
                    f"[r86_diagram_bg_clutter] clip {idx}: visual_register='diagram' requires simplified background (R86)"
                )

        # 4. concrete_referent token presence in scene
        if c_ref and scene_low:
            en_ref_toks = [w for w in re.findall(r"[a-z]{4,}", c_ref.lower()) if w not in _EN_STOP]
            if en_ref_toks and not any(tok[:5] in scene_low for tok in en_ref_toks):
                issues.append(
                    f"[r86_missing_referent_in_scene] clip {idx}: concrete_referent '{c_ref[:60]}' tokens {en_ref_toks[:5]} "
                    "missing from scene description (R86)"
                )

        # 5. Metaphor continuity tracking & concept state_delta
        if m_cid:
            metaphor_runs.setdefault(m_cid, []).append(idx)
        elif idx0 > 0:
            prev_vp_c = raw_vp_clips[idx0 - 1] if idx0 - 1 < len(raw_vp_clips) and isinstance(raw_vp_clips[idx0 - 1], dict) else {}
            prev_mcid = str((clip_list[idx0 - 1] or {}).get("metaphor_continuity_id") or prev_vp_c.get("metaphor_continuity_id") or "").strip()
            if prev_mcid and (is_brain or v_reg == "diagram"):
                prev_bridge = str((clip_list[idx0 - 1] or {}).get("bridge_element") or prev_vp_c.get("bridge_element") or "").strip()
                if not bridge_el and not prev_bridge:
                    issues.append(
                        f"[r86_missing_metaphor_bridge] clip {idx}: returning from metaphor '{prev_mcid}' to diagram/anatomy "
                        "requires non-empty 'bridge_element' shared visual anchor (R86)"
                    )

        if concept_id and concept_id == prev_concept_id:
            if not st_delta:
                issues.append(
                    f"[r86_missing_state_delta] clip {idx}: consecutive cuts sharing concept_id='{concept_id}' "
                    "must specify non-empty 'state_delta' (R86)"
                )
            elif st_delta.lower() == prev_state_delta.lower():
                issues.append(
                    f"[r86_zero_visual_delta] clip {idx}: identical state_delta='{st_delta}' on concept_id='{concept_id}' (R86)"
                )
        prev_concept_id = concept_id
        prev_state_delta = st_delta

        # 6. 3-step misconception_flip check
        if proof_t == "misconception_flip" and not mech_seed:
            next_proof = ""
            if idx0 + 1 < len(clip_list) and isinstance(clip_list[idx0 + 1], dict):
                nvp = raw_vp_clips[idx0 + 1] if idx0 + 1 < len(raw_vp_clips) and isinstance(raw_vp_clips[idx0 + 1], dict) else {}
                next_proof = str(clip_list[idx0 + 1].get("visual_proof_type") or nvp.get("visual_proof_type") or "").strip().lower()
            if next_proof not in ("mechanism", "causal_arrow", "comparison", "data"):
                issues.append(
                    f"[r86_incomplete_misconception_flip] clip {idx}: misconception_flip cannot stop at rejection alone; "
                    "provide 'mechanism_seed' or follow immediately with a mechanism/causal_arrow cut (R86)"
                )

    for sig, sig_clips in brain_signatures.items():
        if len(sig_clips) >= 2:
            issues.append(
                f"[r86_zero_visual_delta] brain cuts {sig_clips} repeat identical anatomy/camera/state/viewpoint signature "
                f"{sig} across distinct sentences (0 visual delta) (R86)"
            )

    if enforce_schema:
        # Check >= 3 consecutive identical visual_proof_type
        run_len = 0
        last_pt = ""
        for c_i, pt in proof_seq:
            if pt == last_pt:
                run_len += 1
                if run_len > R86_MAX_CONSECUTIVE_SAME_PROOF:
                    issues.append(
                        f"[r86_consecutive_proof_cap] clip {c_i}: '{pt}' appears {run_len} cuts in a row "
                        f"(max {R86_MAX_CONSECUTIVE_SAME_PROOF} consecutive allowed) (R86)"
                    )
            else:
                last_pt = pt
                run_len = 1

        if len(reaction_cuts) > R86_MAX_REACTION_CUTS_PER_EPISODE:
            issues.append(
                f"[r86_reaction_cap] {len(reaction_cuts)} 'reaction' cuts {reaction_cuts} exceed episode ceiling "
                f"{R86_MAX_REACTION_CUTS_PER_EPISODE} (R86)"
            )

        for mid, m_cuts in metaphor_runs.items():
            if not (3 <= len(m_cuts) <= 5):
                issues.append(
                    f"[r86_metaphor_dwell] metaphor_continuity_id='{mid}' spans {len(m_cuts)} cuts {m_cuts} "
                    "(require 3-5 cuts before handoff to anatomy) (R86)"
                )

    return issues



_R87_CUT1_STATIC_SIT_RE = re.compile(
    r"\b(?:sits?\s+quietly|sitting\s+on\s+(?:the\s+)?(?:edge\s+of\s+)?(?:a\s+|his\s+|her\s+)?bed|"
    r"rubs?\s+(?:his|her)\s+temples?|pours?\s+tea|pouring\s+tea|"
    r"stares?\s+at\s+(?:two\s+)?frames?|holding\s+two\s+(?:plain\s+)?(?:gray\s+)?(?:picture\s+)?frames?|"
    r"wakes?\s+up\s+in\s+bed|seated\s+calmly|empty\s+wooden\s+desk)\b",
    flags=re.IGNORECASE,
)
_R87_CUT1_XRAY_OR_BIZARRE_RE = re.compile(
    r"\b(?:translucent\s+(?:cranium|skull|head)|mode\s*1|mode\s*2|cutaway\s+brain|ep\s*#?31|gypsum\s+brain|"
    r"ventral\s+striatum|brainstem|clamping|giant\s+headphones|snapping|empty\s+capsule|optical\s+fiber|"
    r"split\s+tabletop|shock)\b",
    flags=re.IGNORECASE,
)
_R87_CANONICAL_HOOK_RE = re.compile(
    r"(?:^|[^a-z0-9]|_)(?:j0[1-6]|a(?:0[1-9]|1[0-9]))(?:_|[^a-z0-9]|$)",
    flags=re.IGNORECASE,
)
_R87_CANONICAL_NONSPATIAL_RE = re.compile(
    r"(?:^|[^a-z0-9]|_)(?:k0[1-6]|a12)(?:_|[^a-z0-9]|$)",
    flags=re.IGNORECASE,
)
_R87_CANONICAL_SPATIAL_CV2_RE = re.compile(
    r"(?:^|[^a-z0-9]|_)c0[1-3]b(?:_|[^a-z0-9]|$)",
    flags=re.IGNORECASE,
)
_R87_TURNAROUND_SHEET_RE = re.compile(
    r"(?:^|[^a-z0-9]|_)b0[1-4]_base_[^/]*turnaround",
    flags=re.IGNORECASE,
)
_R87_BINARY_COMPARISON_RE = re.compile(
    r"\b(?:side\s+by\s+side|versus|vs\.?|against|two\s+groups|compared\s+(?:to|with)|half\b.*\bwhile)\b",
    flags=re.IGNORECASE,
)
_R87_GENERIC_EMPTY_ALLEY_RE = re.compile(
    r"\b(?:sunlit\s+gray\s+architectural\s+stone\s+lane|empty\s+gray\s+alley|"
    r"generic\s+gray\s+(?:alley|corridor|lane)|blank\s+gray\s+alley)\b",
    flags=re.IGNORECASE,
)
_R87_CONCRETE_ARCH_RE = re.compile(
    r"\b(?:london|brick|street|oak|room|doorway|threshold|maze|labyrinth|campus|hallway|"
    r"avenue|embankment|bridge|house|apartment|tabletop|courtyard|plaza|block|road)\b",
    flags=re.IGNORECASE,
)
_R87_CONCRETE_PROP_ACTOR_RE = re.compile(
    r"\b(?:cab|taxi|bus|car|vehicle|walker|figure|subject|box|shoebox|cube|tray|marker|"
    r"door|mannequin|person|driver|pedestrian|mouse|rat|robot)\b",
    flags=re.IGNORECASE,
)
_R87_CONTENT_STOP = frozenset(
    {
        "this", "that", "with", "from", "your", "into", "over", "then", "than",
        "they", "them", "when", "what", "will", "just", "only", "still", "more",
        "very", "some", "does", "have", "been", "were", "here", "there",
    }
)


def _collect_clip_anchor_text(plan: dict[str, Any], clip_obj: dict[str, Any], vp_clip: dict[str, Any], clip_num: int) -> str:
    parts: list[str] = []
    for src in (clip_obj, vp_clip):
        if not isinstance(src, dict):
            continue
        for k in (
            "canonical_slot_id",
            "anchor_slot_id",
            "canonical_anchor",
            "reference_image",
            "secondary_reference_image",
            "end_reference_image",
        ):
            v = str(src.get(k) or "").strip()
            if v:
                parts.append(v)
        for lk in ("reference_images", "conditioned_on", "canonical_slots"):
            lv = src.get(lk)
            if isinstance(lv, list):
                parts.extend(str(x).strip() for x in lv if str(x).strip())
    for anc in plan.get("reference_anchors") or []:
        if not isinstance(anc, dict):
            continue
        if int(anc.get("clip_number") or 0) == clip_num:
            for k in ("ref_id", "filename", "canonical_slot_id", "anchor_slot_id"):
                v = str(anc.get(k) or "").strip()
                if v:
                    parts.append(v)
            if isinstance(anc.get("conditioned_on"), list):
                parts.extend(str(x).strip() for x in anc["conditioned_on"] if str(x).strip())
    return " ".join(parts)


def validate_r87_turnaround_sheet_start_frame_ban(
    plan: dict[str, Any] | None,
    clips: list[dict[str, Any]] | None = None,
    *,
    script_doc: dict[str, Any] | None = None,
    project_id: str | None = None,
) -> list[str]:
    """
    Tier-1 Hard Gate (`[r87_turnaround_sheet_start_frame_ban]`):
      Bans binding 3-view character turnaround sheets (`B01_base_adult_male_turnaround`..
      `B04_base_child_turnaround`) directly as a video clip's Start/End frame (`start_frame_image`,
      `end_frame_image`, `end_reference_image`, `reference_image` with `single_start_frame_lock=True`
      or `flow_input_mode=='VIDEO_FRAMES'`, or `canonical_slot_id` without a separate custom
      single-frame `reference_image`).
      Still allows `B01-B04` inside `conditioned_on` / `Ingredients` (`VIDEO_REFERENCES`) and
      allows single-pose expression anchors (`B05_expr_surprised`..`B10_expr_eureka`).
    """
    from pipeline.config import (
        is_expressive_v8_plan,
        is_r85_flow_31_brain_plan,
        is_r87_plan,
    )

    p = plan if isinstance(plan, dict) else {}
    s = script_doc if isinstance(script_doc, dict) else {}
    clip_list = [c for c in (clips if isinstance(clips, list) else (p.get("clips") or [])) if isinstance(c, dict)]
    raw_vp_clips = [c for c in (p.get("clips") or []) if isinstance(c, dict)]
    if not clip_list:
        return []
    if not (
        is_expressive_v8_plan(p, s, *clip_list)
        or is_r85_flow_31_brain_plan(p, s, project_id=project_id)
        or is_r87_plan(p, s, project_id=project_id)
    ):
        return []

    vp_by_num = {
        int(vc.get("clip_number") or vc.get("clip_index") or (i + 1)): vc
        for i, vc in enumerate(raw_vp_clips)
    }
    issues: list[str] = []
    for idx0, c in enumerate(clip_list):
        clip_num = int(c.get("clip_number") or c.get("clip_index") or (idx0 + 1))
        vp_c = (
            raw_vp_clips[idx0]
            if (len(raw_vp_clips) == len(clip_list) and idx0 < len(raw_vp_clips))
            else vp_by_num.get(clip_num, {})
        )
        start_frame = str(c.get("start_frame_image") or vp_c.get("start_frame_image") or "").strip()
        ref_img = str(c.get("reference_image") or vp_c.get("reference_image") or "").strip()
        end_frame = str(c.get("end_frame_image") or vp_c.get("end_frame_image") or "").strip()
        end_ref = str(c.get("end_reference_image") or vp_c.get("end_reference_image") or "").strip()
        canon_slot = str(c.get("canonical_slot_id") or vp_c.get("canonical_slot_id") or "").strip()
        single_lock = bool(
            c.get("single_start_frame_lock")
            if c.get("single_start_frame_lock") is not None
            else vp_c.get("single_start_frame_lock")
        )
        flow_mode = str(c.get("flow_input_mode") or vp_c.get("flow_input_mode") or "").strip().upper()

        offending: list[str] = []
        if start_frame and _R87_TURNAROUND_SHEET_RE.search(start_frame):
            offending.append(f"start_frame_image='{start_frame}'")
        if end_frame and _R87_TURNAROUND_SHEET_RE.search(end_frame):
            offending.append(f"end_frame_image='{end_frame}'")
        if end_ref and _R87_TURNAROUND_SHEET_RE.search(end_ref):
            offending.append(f"end_reference_image='{end_ref}'")
        if (
            ref_img
            and _R87_TURNAROUND_SHEET_RE.search(ref_img)
            and (single_lock or flow_mode == "VIDEO_FRAMES" or bool(end_ref or end_frame))
        ):
            mode_lbl = flow_mode or ("single_start_frame_lock=True" if single_lock else "VIDEO_FRAMES")
            offending.append(f"reference_image='{ref_img}' ({mode_lbl})")
        if (
            canon_slot
            and _R87_TURNAROUND_SHEET_RE.search(canon_slot)
            and (not ref_img or bool(_R87_TURNAROUND_SHEET_RE.search(ref_img)))
        ):
            offending.append(f"canonical_slot_id='{canon_slot}' without separate custom single-frame reference_image")

        if offending:
            issues.append(
                f"[r87_turnaround_sheet_start_frame_ban] clip {clip_num}: 3-view character turnaround sheet "
                f"({', '.join(offending)}) cannot be bound directly as a Start/End frame — "
                "use B01-B04 inside conditioned_on/Ingredients to generate a single-pose custom 9:16 keyframe, "
                "or bind a single-pose B05-B10 expression anchor (R87)"
            )
    return issues



def validate_r87_hook_contract(
    plan: dict[str, Any] | None,
    clips: list[dict[str, Any]] | None,
    *,
    lines: list[str] | None = None,
    script_doc: dict[str, Any] | None = None,
    project_id: str | None = None,
    edl: dict[str, Any] | None = None,
    _include_turnaround_ban: bool = True,
) -> list[str]:
    """
    Rule R87-H (0.0s–3.0s 3-Second Hook 80%+ Recovery Contract + Lock 3 Canonical Anchor Binding):
      - R87-H1: `hook_visual_mode` in R87_HOOK_VISUAL_MODES; Cut #1 static domestic sitting/tea/temple-rub ban;
        Cut #1 duration `1.90s <= dur <= 2.60s`; `hook_title_text` ALL-CAPS 2–4 words (`<= 24` chars);
        thumbnail <-> Cut #1 / HookTitle referent alignment; Lock 3 Cut #1 `J01–J06` or `A01–A19` canonical anchor.
      - R87-H2: `S01` bans `"Why do/does/did"`, `"How come"`, `"Imagine"`, `"Have you ever"`, `"Did you know"`,
        trailing `'?'`, and enforces `6–12` words + `R87_OPENING_MODES`.
    """
    from pipeline.config import (
        R87_BANNED_S01_OPENING_PREFIXES,
        R87_FIRST_CUT_MAX_SEC,
        R87_FIRST_CUT_MIN_SEC,
        R87_HOOK_TITLE_MAX_CHARS,
        R87_HOOK_TITLE_MAX_WORDS,
        R87_HOOK_VISUAL_MODES,
        R87_OPENING_MODES,
        R87_S01_MAX_WORDS,
        R87_S01_MIN_WORDS,
        is_r87_plan,
    )
    from pipeline.prompt_builder import count_words

    p = plan if isinstance(plan, dict) else {}
    s = script_doc if isinstance(script_doc, dict) else {}
    if not is_r87_plan(p, s, project_id=project_id):
        return []

    issues: list[str] = []
    clip_list = [c for c in (clips if isinstance(clips, list) else (p.get("clips") or [])) if isinstance(c, dict)]
    raw_vp_clips = [c for c in (p.get("clips") or []) if isinstance(c, dict)]

    # 1. R87-H1: hook_visual_mode
    hook_v_mode = str(p.get("hook_visual_mode") or s.get("hook_visual_mode") or "").strip().lower()
    if hook_v_mode not in R87_HOOK_VISUAL_MODES:
        issues.append(
            f"[r87_h1_hook_visual_mode] R87 requires visual_plan['hook_visual_mode'] in {list(R87_HOOK_VISUAL_MODES)}, "
            f"got {hook_v_mode!r} (R87-H1)"
        )

    # 2. R87-H1: Cut #1 visual action, duration, and Lock 3 Category J / A01-A19 binding
    if clip_list:
        c1 = clip_list[0]
        vp1 = raw_vp_clips[0] if raw_vp_clips else {}
        c1_scene = " ".join(
            str(x or "")
            for x in (
                c1.get("scene"),
                vp1.get("scene"),
                c1.get("action"),
                vp1.get("action"),
                c1.get("concrete_referent"),
                vp1.get("concrete_referent"),
            )
        ).strip()
        if _R87_CUT1_STATIC_SIT_RE.search(c1_scene) and not _R87_CUT1_XRAY_OR_BIZARRE_RE.search(c1_scene):
            issues.append(
                f"[r87_h1_cut1_static_sit_ban] Cut #1 depicts passive domestic sitting/waiting without Mode 1/2 brain "
                f"or bizarre intervention prop: '{c1_scene[:90]}' (R87-H1)"
            )

        c1_dur: float | None = None
        if isinstance(edl, dict) and isinstance(edl.get("cuts"), list) and edl["cuts"]:
            first_edl = edl["cuts"][0]
            if isinstance(first_edl, dict) and first_edl.get("duration_sec") is not None:
                c1_dur = float(first_edl["duration_sec"])
        elif c1.get("duration_sec") is not None or vp1.get("duration_sec") is not None:
            c1_dur = float(c1.get("duration_sec") if c1.get("duration_sec") is not None else vp1["duration_sec"])
        elif c1.get("target_duration_sec") is not None or vp1.get("target_duration_sec") is not None:
            c1_dur = float(
                c1.get("target_duration_sec")
                if c1.get("target_duration_sec") is not None
                else vp1["target_duration_sec"]
            )
        if c1_dur is not None and not (R87_FIRST_CUT_MIN_SEC - 0.005 <= c1_dur <= R87_FIRST_CUT_MAX_SEC + 0.005):
            issues.append(
                f"[r87_h1_cut1_duration] Cut #1 duration {c1_dur:.2f}s outside R87-H1 lock "
                f"[{R87_FIRST_CUT_MIN_SEC:.2f}..{R87_FIRST_CUT_MAX_SEC:.2f}]s (R87-H1)"
            )

        # Lock 3: Cut #1 MUST bind to Canonical Category J (J01-J06) or Ep #31 Brain A01-A19
        c1_anchor_txt = _collect_clip_anchor_text(p, c1, vp1, 1)
        if not _R87_CANONICAL_HOOK_RE.search(c1_anchor_txt):
            issues.append(
                f"[r87_lock3_cut1_canonical_anchor] Cut #1 must bind to Canonical v1.2 Category J (J01-J06) "
                f"or Ep #31 Brain anchor (A01-A19), got anchors='{c1_anchor_txt[:90]}' (R87/Lock3)"
            )

    # 3. R87-H1/H3: HookTitle & Thumbnail alignment
    raw_ht = str(p.get("hook_title_text") or p.get("opening_hook_title") or s.get("hook_title_text") or "").strip()
    ht_clean = re.sub(r"(?:\\N|\\n|\r|\n)+", " ", raw_ht).strip()
    ht_words = [w for w in re.split(r"\s+", ht_clean) if w]
    if not ht_clean:
        issues.append("[r87_h3_hook_title_missing] R87 requires visual_plan['hook_title_text'] (2-4 ALL-CAPS words for 0.00-2.20s HookTitle) (R87-H3)")
    else:
        if not (2 <= len(ht_words) <= R87_HOOK_TITLE_MAX_WORDS):
            issues.append(
                f"[r87_h3_hook_title_words] hook_title_text='{ht_clean}' has {len(ht_words)} words "
                f"(require 2..{R87_HOOK_TITLE_MAX_WORDS}) (R87-H3)"
            )
        if len(ht_clean) > R87_HOOK_TITLE_MAX_CHARS:
            issues.append(
                f"[r87_h3_hook_title_chars] hook_title_text='{ht_clean}' has {len(ht_clean)} chars > max {R87_HOOK_TITLE_MAX_CHARS} (R87-H3)"
            )
        if any(ch.islower() for ch in ht_clean):
            issues.append(
                f"[r87_h3_hook_title_caps] hook_title_text='{ht_clean}' must be ALL-CAPS for silent-scroll punch (R87-H3)"
            )

    thumb = p.get("thumbnail") if isinstance(p.get("thumbnail"), dict) else {}
    thumb_txt = " ".join(
        str(thumb.get(k) or "")
        for k in ("hook_text", "top_label", "bottom_label", "left_label", "right_label")
        if str(thumb.get(k) or "").strip().upper() != "TODO"
    ).strip()
    if thumb_txt and (ht_clean or clip_list):
        c1_all = ht_clean
        if clip_list:
            vp1_t = raw_vp_clips[0] if raw_vp_clips else {}
            c1_all += " " + " ".join(
                str(x or "")
                for x in (
                    clip_list[0].get("scene"),
                    vp1_t.get("scene"),
                    clip_list[0].get("action"),
                    vp1_t.get("action"),
                    clip_list[0].get("concrete_referent"),
                    vp1_t.get("concrete_referent"),
                )
            )
        thumb_toks = {
            w[:4]
            for w in re.findall(r"[a-z]{4,}|\d+", thumb_txt.lower())
            if w not in _R87_CONTENT_STOP
        }
        hook_toks = {
            w[:4]
            for w in re.findall(r"[a-z]{4,}|\d+", c1_all.lower())
            if w not in _R87_CONTENT_STOP
        }
        if thumb_toks and hook_toks and not (thumb_toks & hook_toks):
            issues.append(
                f"[r87_h1_thumb_to_cut1_mismatch] Thumbnail '{thumb_txt[:60]}' shares 0 content stems with "
                f"HookTitle/Cut #1 ('{ht_clean[:40]}') — eliminate thumbnail bait-and-switch (R87-H1)"
            )

    # 4. R87-H2: S01 opening mode, prefix ban, zero '?', 6-12 words
    opening_mode = str(s.get("opening_mode") or p.get("opening_mode") or "").strip().lower()
    if opening_mode and opening_mode not in R87_OPENING_MODES:
        issues.append(
            f"[r87_h2_opening_mode] R87 forbids opening_mode='{opening_mode}' — use one of {list(R87_OPENING_MODES)} (R87-H2)"
        )
    s_lines = list(lines or [])
    if not s_lines and isinstance(s.get("sentences"), list):
        s_lines = [str(x) for x in s["sentences"]]
    if s_lines:
        s1 = re.sub(r"^[\"'“”‘’\s]+", "", str(s_lines[0] or "")).strip()
        s1_low = s1.lower()
        for pref in R87_BANNED_S01_OPENING_PREFIXES:
            if s1_low.startswith(pref):
                issues.append(
                    f"[r87_h2_s01_prefix_ban] S01 starts with banned low-retention prefix '{pref}': '{s1[:70]}' (R87-H2)"
                )
                break
        if s1.endswith("?"):
            issues.append(
                f"[r87_h2_s01_question_ban] S01 must be a punchy declarative or '!' hook, not a '?' question: '{s1[:70]}' (R87-H2)"
            )
        wc = count_words(s1)
        if not (R87_S01_MIN_WORDS <= wc <= R87_S01_MAX_WORDS):
            issues.append(
                f"[r87_h2_s01_word_count] S01 has {wc} words outside R87-H2 lock [{R87_S01_MIN_WORDS}..{R87_S01_MAX_WORDS}]: '{s1[:70]}' (R87-H2)"
            )

    if _include_turnaround_ban:
        issues.extend(
            validate_r87_turnaround_sheet_start_frame_ban(
                p,
                clip_list,
                script_doc=s,
                project_id=project_id,
            )
        )

    return issues



def validate_r87_spatial_arrow_eligibility(
    plan: dict[str, Any] | None,
    clips: list[dict[str, Any]] | None,
    *,
    lines: list[str] | None = None,
    script_doc: dict[str, Any] | None = None,
    project_id: str | None = None,
) -> list[str]:
    """
    Rule R87-A (Conditional Spatial Arrow Eligibility + Non-Spatial Replacement + Lock 3 Anchor Binding):
      - Requires explicit boolean `visual_plan['spatial_arrow_eligible']`.
      - When `False`: hard-blocks `spatial_3d_arrow_diorama`, `spatial_relay_cut`, and `r80_mode=True`;
        requires `>= 1` non-spatial contrast cut bound to Canonical Category K (`K01-K06`) or `A12`.
      - When `True`: blocks generic empty gray alleys without study architecture, blocks single-arrow
        `fixed_linear_corridor` on binary comparison narration (`side by side` / `versus` / `two groups`),
        requires miniature prop/vehicle/actor anchor, and enforces Lock 3 `C01b-C03b` binding.
    """
    from pipeline.config import R87_NON_SPATIAL_CONTRAST_GRAMMARS, is_r87_plan

    p = plan if isinstance(plan, dict) else {}
    s = script_doc if isinstance(script_doc, dict) else {}
    if not is_r87_plan(p, s, project_id=project_id):
        return []

    issues: list[str] = []
    elig = p.get("spatial_arrow_eligible")
    if not isinstance(elig, bool):
        issues.append(
            "[r87_a_missing_eligibility] R87-A requires explicit boolean visual_plan['spatial_arrow_eligible'] "
            "(True ONLY for spatial navigation/doorway/maze studies; False for pharmacology/sleep/diet/pain/bias) (R87-A)"
        )
        return issues


    clip_list = [c for c in (clips if isinstance(clips, list) else (p.get("clips") or [])) if isinstance(c, dict)]
    raw_vp_clips = [c for c in (p.get("clips") or []) if isinstance(c, dict)]
    s_lines = list(lines or [])
    if not s_lines and isinstance(s.get("sentences"), list):
        s_lines = [str(x) for x in s["sentences"]]

    if elig is False:
        if p.get("r80_mode") is True:
            issues.append(
                "[r87_a_r80_mode_conflict] spatial_arrow_eligible=False forbids r80_mode=True on non-spatial topics (R87-A)"
            )
        non_spatial_contrast_count = 0
        for idx0, c in enumerate(clip_list):
            idx = idx0 + 1
            vp_c = raw_vp_clips[idx0] if idx0 < len(raw_vp_clips) else {}
            g = str(c.get("grammar") or vp_c.get("grammar") or "").strip().lower()
            is_sp_relay = bool(c.get("spatial_relay_cut") or vp_c.get("spatial_relay_cut"))
            ar_mode = str(c.get("arrow_3d_mode") or vp_c.get("arrow_3d_mode") or "").strip()
            if g == "spatial_3d_arrow_diorama" or is_sp_relay or bool(ar_mode):
                issues.append(
                    f"[r87_a_non_spatial_arrow_banned] clip {idx}: spatial_3d_arrow_diorama / R80 street arrow is "
                    "STRICTLY FORBIDDEN when spatial_arrow_eligible=False — use Category K prop contrast + A12/K06 brain contrast (R87-A)"
                )
            anchor_txt = _collect_clip_anchor_text(p, c, vp_c, idx)
            proof_t = str(c.get("visual_proof_type") or vp_c.get("visual_proof_type") or "").strip().lower()
            is_explicit_contrast = (
                g == "expressive_split_contrast"
                or bool(c.get("non_spatial_contrast_cut") or vp_c.get("non_spatial_contrast_cut"))
                or proof_t == "comparison"
            )
            has_k_or_a12 = bool(_R87_CANONICAL_NONSPATIAL_RE.search(anchor_txt))
            if is_explicit_contrast or has_k_or_a12:
                non_spatial_contrast_count += 1
                # Lock 3: non-spatial contrast cuts MUST bind to Category K (K01-K06) or A12
                if not has_k_or_a12:
                    issues.append(
                        f"[r87_lock3_nonspatial_canonical_anchor] clip {idx}: non-spatial contrast cut must bind to "
                        f"Canonical v1.2 Category K (K01-K06) or A12, got anchors='{anchor_txt[:90]}' (R87-A/Lock3)"
                    )
            elif g in R87_NON_SPATIAL_CONTRAST_GRAMMARS and has_k_or_a12:
                non_spatial_contrast_count += 1
        if clip_list and non_spatial_contrast_count < 1:
            issues.append(
                "[r87_a_missing_nonspatial_contrast] spatial_arrow_eligible=False requires >= 1 non-spatial contrast cut "
                "(Category K K01-K06 physical prop contrast or A12/K06 dual-brain contrast) (R87-A)"
            )
    else:
        # elig is True: validate spatial_3d_arrow_diorama guardrails & Lock 3 C01b-C03b binding
        for idx0, c in enumerate(clip_list):
            idx = idx0 + 1
            vp_c = raw_vp_clips[idx0] if idx0 < len(raw_vp_clips) else {}
            g = str(c.get("grammar") or vp_c.get("grammar") or "").strip().lower()
            if g != "spatial_3d_arrow_diorama":
                continue
            scene_blob = " ".join(
                str(x or "")
                for x in (
                    c.get("scene"),
                    vp_c.get("scene"),
                    c.get("action"),
                    vp_c.get("action"),
                    c.get("environment"),
                    vp_c.get("environment"),
                    c.get("landmark_desc"),
                    vp_c.get("landmark_desc"),
                )
            ).strip()
            if _R87_GENERIC_EMPTY_ALLEY_RE.search(scene_blob) or (
                scene_blob and not _R87_CONCRETE_ARCH_RE.search(scene_blob)
            ):
                issues.append(
                    f"[r87_a_empty_alley_banned] clip {idx}: spatial_3d_arrow_diorama must depict authentic named study "
                    f"architecture (never a generic empty gray alley): '{scene_blob[:90]}' (R87-A)"
                )

            # Gather narration + claim + viewer_must_understand for binary comparison check
            s_idx_raw = c.get("sentence_index") or vp_c.get("sentence_index")
            spoken_line = ""
            if isinstance(s_idx_raw, int) and 1 <= s_idx_raw <= len(s_lines):
                spoken_line = str(s_lines[s_idx_raw - 1] or "")
            elif idx0 < len(s_lines):
                spoken_line = str(s_lines[idx0] or "")
            comp_blob = " ".join(
                str(x or "")
                for x in (
                    spoken_line,
                    c.get("spoken_narration"),
                    vp_c.get("spoken_narration"),
                    c.get("narration"),
                    vp_c.get("narration"),
                    c.get("claim"),
                    vp_c.get("claim"),
                    c.get("viewer_must_understand"),
                    vp_c.get("viewer_must_understand"),
                )
            )
            ar_mode = str(c.get("arrow_3d_mode") or vp_c.get("arrow_3d_mode") or "").strip().lower()
            if _R87_BINARY_COMPARISON_RE.search(comp_blob) and ar_mode in (
                "fixed_linear_corridor",
                "single_lane",
                "single_arrow",
                "",
            ):
                issues.append(
                    f"[r87_a_single_arrow_comparison_ban] clip {idx}: binary comparison narration/claim forbids single-arrow "
                    f"mode '{ar_mode}' — use dual_route_race_lanes (C02b) or A vs B pair (R87-A)"
                )

            prop_blob = " ".join(
                str(x or "")
                for x in (
                    c.get("anchor_prop_a"),
                    vp_c.get("anchor_prop_a"),
                    c.get("anchor_prop_b"),
                    vp_c.get("anchor_prop_b"),
                    c.get("vehicle_or_actor_desc"),
                    vp_c.get("vehicle_or_actor_desc"),
                    c.get("cast"),
                    vp_c.get("cast"),
                    scene_blob,
                )
            )
            if not _R87_CONCRETE_PROP_ACTOR_RE.search(prop_blob):
                issues.append(
                    f"[r87_a_missing_prop_anchor] clip {idx}: spatial_3d_arrow_diorama must anchor a visible study-specific "
                    "miniature prop/vehicle/actor to the arrow path (zero unlabelled mystery arrows) (R87-A)"
                )

            # Lock 3: spatial-eligible arrow cuts MUST bind to C01b-C03b
            anchor_txt = _collect_clip_anchor_text(p, c, vp_c, idx)
            if not _R87_CANONICAL_SPATIAL_CV2_RE.search(anchor_txt):
                issues.append(
                    f"[r87_lock3_spatial_canonical_anchor] clip {idx}: R87 spatial_3d_arrow_diorama must bind to "
                    f"Canonical v1.2 Category C-v2 (C01b-C03b), got anchors='{anchor_txt[:90]}' (R87-A/Lock3)"
                )

    return issues

def validate_r88_faceless_cast_contract(
    plan: dict[str, Any] | None,
    clips: list[dict[str, Any]] | None = None,
    *,
    script_doc: dict[str, Any] | None = None,
    project_id: str | None = None,
) -> list[str]:
    """
    Rule R88: Enforces faceless architectural porcelain cast and bans retired `B01-B15`
    cartoon-face canonical slots and 2D ink facial expression tokens across new `v8_ep13+` / `r88_mode` plans.
    """
    from pipeline.canonical_assets import _matches_retired_r88_slot_ref
    from pipeline.config import R88_BANNED_CARTOON_FACE_TOKENS, is_r88_faceless_cast_plan

    p = plan if isinstance(plan, dict) else {}
    if not is_r88_faceless_cast_plan(p, script_doc=script_doc, project_id=project_id):
        return []

    issues: list[str] = []
    vp_clips = [c for c in (p.get("clips") or []) if isinstance(c, dict)]
    built_clips = [c for c in (clips or vp_clips) if isinstance(c, dict)]
    vp_by_num = {int(vc.get("clip_number") or i): vc for i, vc in enumerate(vp_clips, start=1)}

    ref_keys = (
        "canonical_slot_id",
        "reference_image",
        "secondary_reference_image",
        "start_frame_image",
        "end_frame_image",
        "end_reference_image",
    )
    text_keys = ("action", "scene", "prompt", "cast", "concrete_referent", "state_delta")

    for i, c in enumerate(built_clips, start=1):
        idx = int(c.get("clip_number") or c.get("clip_index") or i)
        vp_c = vp_by_num.get(idx, {})
        seen_slot_errs: set[tuple[str, str]] = set()
        for src_clip in (c, vp_c):
            if not isinstance(src_clip, dict):
                continue
            for k in ref_keys:
                hit = _matches_retired_r88_slot_ref(src_clip.get(k))
                if hit and (k, hit) not in seen_slot_errs:
                    seen_slot_errs.add((k, hit))
                    issues.append(
                        f"[r88_retired_cartoon_cast_ban] clip {idx} {k} references retired cartoon-cast slot '{hit}' (R88)"
                    )
            for cond_item in src_clip.get("conditioned_on") or []:
                hit = _matches_retired_r88_slot_ref(cond_item)
                if hit and ("conditioned_on", hit) not in seen_slot_errs:
                    seen_slot_errs.add(("conditioned_on", hit))
                    issues.append(
                        f"[r88_retired_cartoon_cast_ban] clip {idx} conditioned_on references retired cartoon-cast slot '{hit}' (R88)"
                    )

        blob = " ".join(
            str(src.get(fk) or "")
            for src in (c, vp_c)
            if isinstance(src, dict)
            for fk in text_keys
        ).lower()
        for tok in R88_BANNED_CARTOON_FACE_TOKENS:
            if tok in blob:
                issues.append(
                    f"[r88_retired_cartoon_cast_ban] clip {idx} contains banned cartoon-face token '{tok}' (R88)"
                )

    for anc in p.get("reference_anchors") or []:
        if not isinstance(anc, dict):
            continue
        afn = str(anc.get("filename") or anc.get("ref_id") or "")
        for fk in ("canonical_slot_id", "filename", "ref_id"):
            hit = _matches_retired_r88_slot_ref(anc.get(fk))
            if hit:
                issues.append(
                    f"[r88_retired_cartoon_cast_ban] reference_anchor '{afn}' {fk} references retired cartoon-cast slot '{hit}' (R88)"
                )
        for cond_item in anc.get("conditioned_on") or []:
            hit = _matches_retired_r88_slot_ref(cond_item)
            if hit:
                issues.append(
                    f"[r88_retired_cartoon_cast_ban] reference_anchor '{afn}' conditioned_on retired cartoon-cast slot '{hit}' (R88)"
                )
        anc_prompt = str(anc.get("prompt") or "").lower()
        for tok in R88_BANNED_CARTOON_FACE_TOKENS:
            if tok in anc_prompt:
                issues.append(
                    f"[r88_retired_cartoon_cast_ban] reference_anchor '{afn}' prompt contains banned cartoon-face token '{tok}' (R88)"
                )

    thumb = p.get("thumbnail") if isinstance(p.get("thumbnail"), dict) else {}
    thumb_blob = " ".join(
        str(thumb.get(k) or "") for k in ("top_human_action", "bottom_human_action", "hook_text")
    ).lower()
    for tok in R88_BANNED_CARTOON_FACE_TOKENS:
        if tok in thumb_blob:
            issues.append(
                f"[r88_retired_cartoon_cast_ban] thumbnail spec contains banned cartoon-face token '{tok}' (R88)"
            )

    return issues
