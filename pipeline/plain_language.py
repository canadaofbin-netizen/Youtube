"""
ALL ABOUT BRAIN - Plain-language and TTS-safe narration guardrails (R15 quantified, R49).

- Jargon cap: non-anatomical technical terms (lexicon, alphanumeric codes like CA3, unexplained acronyms)
  are capped per script; anatomical names are capped separately and must carry a plain-language gloss.
- Readability: Flesch-Kincaid grade per clip and per script.
- TTS-safe: spoken narration contains no digits, '%', '!', '?', em/en dashes, ';', parentheses or
  abbreviations that make the narrator's pitch jump; `to_tts_text` normalizes, `to_display_text` restores
  compact numerals for subtitles (Display script vs TTS script split).
"""

from __future__ import annotations

import re
from typing import Any

from pipeline.anatomy_map import ANATOMY_FUNCTION_MAP, find_regions, region_named_in

# Non-anatomical technical vocabulary that reads like a paper. Extend as new topics surface.
JARGON_LEXICON: tuple[str, ...] = (
    "nonlinear", "multi-input", "multi-output", "algorithm", "paradigm", "stimulus", "stimuli",
    "unconditioned", "conditioned stimulus", "conditioned response", "synaptic", "synapse", "synapses",
    "subfield", "subfields", "electrophysiological", "neurotransmitter", "neurotransmitters", "potentiation",
    "spike pattern", "spike patterns", "microelectrode", "microelectrodes", "depth electrode", "depth electrodes",
    "inhibitory", "excitatory", "efferent", "afferent", "neuroplasticity", "plasticity", "cognitive dissonance",
    "inattentional", "operant", "reinforcement schedule", "heuristic", "metacognitive", "somatic marker",
    "attentional", "top-down", "bottom-up", "salience", "encoding", "consolidation", "lesion", "lesions",
    "participants", "subjects demonstrated", "statistically", "significant", "correlation", "methodology",
    "neural code", "transfer code", "prosthetic", "prosthetics", "autonomic", "contralateral", "ipsilateral",
)
# Short words that are not acronyms of jargon.
_ACRONYM_ALLOW: frozenset[str] = frozenset({"I", "A", "US", "USA", "UK", "TV", "OK", "DNA", "AI", "ID", "IQ", "MRI", "CEO", "NASA", "WWII", "NBA"})
_CODE_RE = re.compile(r"\b(?=[A-Za-z]*\d)(?=\d*[A-Za-z])[A-Za-z0-9]{2,6}\b")  # CA3, V1, H2
_ACRONYM_RE = re.compile(r"\b[a-z]{0,2}[A-Z][A-Za-z]*[A-Z]+[A-Za-z]*\b")  # MIMO, fMRI, DBS, vmPFC
_ROBOTIC_OPENERS_RE = re.compile(r"\bstep (?:one|two|three|four|1|2|3|4)\b", re.IGNORECASE)
_PAPER_VOICE_RE = re.compile(
    r"\b(participants|subjects) (?:demonstrated|exhibited|displayed)\b|\bit was (?:found|observed|demonstrated)\b",
    re.IGNORECASE,
)

# TTS-unsafe characters (pitch jumps, odd pauses, read-outs).
_TTS_UNSAFE_CHARS: dict[str, str] = {
    "!": "exclamation mark",
    "?": "question mark",
    "—": "em dash",
    "–": "en dash",
    ";": "semicolon",
    "(": "parenthesis",
    ")": "parenthesis",
    "%": "percent sign",
    "&": "ampersand",
    "/": "slash",
    "…": "ellipsis",
}
_ABBREV_RE = re.compile(r"\b(Dr|Mr|Mrs|Ms|Prof|St|vs|etc|e\.g|i\.e|U\.S|Ph\.D)\.", re.IGNORECASE)
_DIGIT_RE = re.compile(r"\d")

_ONES = ("zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven",
         "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen")
_TENS = ("", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety")


def count_syllables(word: str) -> int:
    w = re.sub(r"[^a-z]", "", word.lower())
    if not w:
        return 0
    if len(w) <= 3:
        return 1
    w = re.sub(r"(?:[^laeiouy]es|ed|[^laeiouy]e)$", "", w)
    w = re.sub(r"^y", "", w)
    return max(1, len(re.findall(r"[aeiouy]{1,2}", w)))


def _words(text: str) -> list[str]:
    return re.findall(r"[A-Za-z][A-Za-z'-]*|\d+", str(text or ""))


def _sentences(text: str) -> list[str]:
    return [s for s in re.split(r"(?<=[.!?])\s+", str(text or "").strip()) if s.strip()]


def fk_grade(text: str) -> float:
    """Flesch-Kincaid grade level."""
    words = _words(text)
    if not words:
        return 0.0
    sents = max(1, len(_sentences(text)))
    syl = sum(count_syllables(w) for w in words)
    return round(0.39 * (len(words) / sents) + 11.8 * (syl / len(words)) - 15.59, 2)


def find_jargon(text: str) -> list[str]:
    """Non-anatomical technical terms: lexicon hits, alphanumeric codes, unexplained acronyms."""
    t = str(text or "")
    low = t.lower()
    hits: list[str] = []
    for term in sorted(JARGON_LEXICON, key=len, reverse=True):
        if re.search(rf"(?<![a-z-]){re.escape(term)}(?![a-z-])", low) and not any(term in h for h in hits):
            hits.append(term)
    for m in _CODE_RE.finditer(t):
        tok = m.group(0)
        if tok.isdigit() or re.fullmatch(r"\d+s|\d+(?:st|nd|rd|th)|3D|2D", tok, re.IGNORECASE) or tok in hits:
            continue
        hits.append(tok)
    for m in _ACRONYM_RE.finditer(t):
        tok = m.group(0)
        if tok in _ACRONYM_ALLOW or tok in hits:
            continue
        uppers = sum(1 for ch in tok if ch.isupper())
        # Acronym-like (MIMO, fMRI, vmPFC) rather than a camel-case surname (McDonald).
        if uppers >= 2 and uppers / len(tok) >= 0.5:
            hits.append(tok)
    return hits


def find_anatomy_terms(text: str) -> list[str]:
    return find_regions(text)


def tts_issues(text: str) -> list[str]:
    """Reasons a narration line is unsafe for consistent TTS / Flow voice delivery."""
    t = str(text or "")
    issues: list[str] = []
    if _DIGIT_RE.search(t):
        issues.append("contains digits (spell numbers out, e.g. 'thirty-seven percent')")
    for ch, name in _TTS_UNSAFE_CHARS.items():
        if ch in t:
            issues.append(f"contains {name} '{ch}'")
    if _ABBREV_RE.search(t):
        issues.append("contains an abbreviation with a period (write 'Doctor', 'United States')")
    if "--" in t:
        issues.append("contains a double hyphen dash")
    return issues


def number_to_words(n: int) -> str:
    if n < 0:
        return "minus " + number_to_words(-n)
    if n < 20:
        return _ONES[n]
    if n < 100:
        return _TENS[n // 10] + ("" if n % 10 == 0 else "-" + _ONES[n % 10])
    if n < 1000:
        rest = n % 100
        return _ONES[n // 100] + " hundred" + ("" if rest == 0 else " " + number_to_words(rest))
    if n < 1_000_000:
        rest = n % 1000
        return number_to_words(n // 1000) + " thousand" + ("" if rest == 0 else " " + number_to_words(rest))
    if n < 1_000_000_000:
        rest = n % 1_000_000
        return number_to_words(n // 1_000_000) + " million" + ("" if rest == 0 else " " + number_to_words(rest))
    rest = n % 1_000_000_000
    return number_to_words(n // 1_000_000_000) + " billion" + ("" if rest == 0 else " " + number_to_words(rest))


def year_to_words(n: int) -> str:
    """1848 -> 'eighteen forty-eight', 2005 -> 'two thousand five', 1900 -> 'nineteen hundred'."""
    if 2000 <= n <= 2009:
        return number_to_words(n)
    hi, lo = divmod(n, 100)
    if lo == 0:
        return number_to_words(hi) + " hundred"
    return number_to_words(hi) + " " + (("oh " + _ONES[lo]) if lo < 10 else number_to_words(lo))


_ABBREV_EXPAND = {
    "dr.": "Doctor", "mr.": "Mister", "mrs.": "Missus", "ms.": "Miz", "prof.": "Professor", "st.": "Saint",
    "vs.": "versus", "etc.": "and so on", "e.g.": "for example", "i.e.": "that is", "u.s.": "United States",
    "ph.d.": "doctorate",
}

_PROPER_NOUN_TTS_RULES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\b([A-Z])\.\s*([A-Z])\.(?=\s|['’,.!?;:—–-]|$)"), r"\1 \2"),
    (re.compile(r"\b([A-Z])\.\s+(?=[A-Z][a-z])"), r"\1 "),
    (re.compile(r"\bPhineas\b", re.IGNORECASE), "Fin-ee-us"),
    (re.compile(r"\bMolaison\b", re.IGNORECASE), "Mo-lay-zon"),
    (re.compile(r"\bScoville\b", re.IGNORECASE), "Sko-vil"),
    (re.compile(r"\bLeborgne\b", re.IGNORECASE), "Luh-born"),
    (re.compile(r"\bBroca's\b", re.IGNORECASE), "Bro-kuz"),
    (re.compile(r"\bBroca\b", re.IGNORECASE), "Bro-kuh"),
    (re.compile(r"\bWernicke's\b", re.IGNORECASE), "Ver-ni-keez"),
    (re.compile(r"\bWernicke\b", re.IGNORECASE), "Ver-ni-kee"),
    (re.compile(r"\bCapgras\b", re.IGNORECASE), "Kap-grah"),
    (re.compile(r"\bRamachandran\b", re.IGNORECASE), "Rah-mah-chan-dran"),
    (re.compile(r"\bKorsakoff\b", re.IGNORECASE), "Kor-suh-koff"),
    (re.compile(r"\bWeiskrantz\b", re.IGNORECASE), "Vise-krants"),
    (re.compile(r"\bGazzaniga\b", re.IGNORECASE), "Gah-zuh-nee-guh"),
)


def _apply_proper_noun_tts(text: str) -> str:
    t = text
    for pat, repl in _PROPER_NOUN_TTS_RULES:
        t = pat.sub(repl, t)
    return t


def to_tts_text(text: str) -> str:
    """Deterministic TTS normalization: numbers/percent/years to words, unsafe punctuation to commas/periods."""
    t = str(text or "")

    def _abbr(m: re.Match[str]) -> str:
        return _ABBREV_EXPAND.get(m.group(0).lower(), m.group(0))

    t = re.sub(r"\b(?:Dr|Mr|Mrs|Ms|Prof|St|vs|etc|e\.g|i\.e|U\.S|Ph\.D)\.", _abbr, t, flags=re.IGNORECASE)
    t = _apply_proper_noun_tts(t)
    t = re.sub(r"(\d+(?:\.\d+)?)\s*%", lambda m: m.group(1) + " percent", t)

    def _num(m: re.Match[str]) -> str:
        raw = m.group(0).replace(",", "")
        if "." in raw:
            whole, frac = raw.split(".", 1)
            return number_to_words(int(whole)) + " point " + " ".join(_ONES[int(d)] for d in frac)
        val = int(raw)
        if 1100 <= val <= 2099 and len(raw) == 4:
            return year_to_words(val)
        return number_to_words(val)

    t = re.sub(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?", _num, t)
    t = t.replace("&", " and ").replace("/", " or ")
    t = re.sub(r"\s*[—–]\s*|\s*--\s*", ", ", t)
    t = re.sub(r"\s*;\s*", ", ", t)
    t = re.sub(r"\s*\(([^)]*)\)\s*", lambda m: ", " + m.group(1) + ", ", t)
    t = re.sub(r"[!?]+", ".", t)
    t = t.replace("…", ".")
    t = re.sub(r",\s*,", ",", t)
    t = re.sub(r",\s*\.", ".", t)
    t = re.sub(r"\s+([,.])", r"\1", t)
    t = re.sub(r"\s{2,}", " ", t).strip()
    return t


def to_expressive_tts_text(text: str) -> str:
    """
    Conversational neural TTS normalizer for `edge-tts` (`neuro_diorama`):
    Expands abbreviations, percentages, proper-noun phonetics, and digits into clean spoken English words
    WHILE preserving expressive prosody punctuation (`?`, `!`, `—`, `...`) so the
    narrator delivers natural question inflections, asides, and dramatic pauses.
    """
    t = str(text or "")

    def _abbr(m: re.Match[str]) -> str:
        return _ABBREV_EXPAND.get(m.group(0).lower(), m.group(0))

    t = re.sub(r"\b(?:Dr|Mr|Mrs|Ms|Prof|St|vs|etc|e\.g|i\.e|U\.S|Ph\.D)\.", _abbr, t, flags=re.IGNORECASE)
    t = _apply_proper_noun_tts(t)
    t = re.sub(r"(\d+(?:\.\d+)?)\s*%", lambda m: m.group(1) + " percent", t)

    def _num(m: re.Match[str]) -> str:
        raw = m.group(0).replace(",", "")
        if "." in raw:
            whole, frac = raw.split(".", 1)
            return number_to_words(int(whole)) + " point " + " ".join(_ONES[int(d)] for d in frac)
        val = int(raw)
        if 1100 <= val <= 2099 and len(raw) == 4:
            return year_to_words(val)
        return number_to_words(val)

    t = re.sub(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?", _num, t)
    t = t.replace("&", " and ").replace("/", " or ")
    t = t.replace("…", "...")
    t = re.sub(r"\s*--\s*", " — ", t)
    t = re.sub(r"\s*;\s*", ", ", t)
    t = re.sub(r"\s*\(([^)]*)\)\s*", lambda m: ", " + m.group(1) + ", ", t)
    t = re.sub(r"\s{2,}", " ", t).strip()
    return t


_WORD_NUM = {w: i for i, w in enumerate(_ONES)}
_WORD_NUM.update({w: i * 10 for i, w in enumerate(_TENS) if w})


def to_display_text(text: str) -> str:
    """Subtitle-friendly form: 'thirty-seven percent' -> '37%', 'eighteen forty-eight' -> '1848', 'four hundred fifty' -> '450'."""
    _teens = {w: i for i, w in enumerate(_ONES) if i >= 10}
    _units = {w: i for i, w in enumerate(_ONES) if 1 <= i <= 9}
    _tens_map = {w: i * 10 for i, w in enumerate(_TENS) if w}

    def _two(word: str) -> int | None:
        w = word.lower().strip()
        if w.isdigit():
            return int(w)
        if w in _units:
            return _units[w]
        if w in _teens:
            return _teens[w]
        if w in _tens_map:
            return _tens_map[w]
        m = re.fullmatch(
            r"(twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety)[-\s](one|two|three|four|five|six|seven|eight|nine)",
            w,
        )
        if m:
            return _tens_map[m.group(1)] + _units[m.group(2)]
        return None

    _two_re = (
        r"(?:(?:twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety)(?:[-\s](?:one|two|three|four|five|six|seven|eight|nine))?"
        r"|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen"
        r"|one|two|three|four|five|six|seven|eight|nine|\d{1,2})"
    )

    # 1. 'two thousand [and] <1..99>' -> '2009', '2024', etc. (not when followed by 'hundred')
    def _two_thousand(m: re.Match[str]) -> str:
        tail = (m.group(1) or "").strip()
        if not tail:
            return "2000"
        lo = _two(tail)
        return str(2000 + lo) if lo is not None else m.group(0)

    t = re.sub(
        rf"\btwo\s+thousand(?:\s+(?:and\s+)?({_two_re}))?(?![-\w]|\s+hundred\b)",
        _two_thousand,
        str(text or ""),
        flags=re.IGNORECASE,
    )

    # 2. '<a|1..9> hundred [and] <1..99>' -> '374', '450', '100', etc.
    def _hundreds(m: re.Match[str]) -> str:
        h_word = m.group(1).lower()
        h_val = 1 if h_word == "a" else (int(h_word) if h_word.isdigit() else _units.get(h_word, 0))
        if not h_val:
            return m.group(0)
        tail = (m.group(2) or "").strip()
        if not tail:
            return str(h_val * 100)
        lo = _two(tail)
        return str(h_val * 100 + lo) if lo is not None else m.group(0)

    t = re.sub(
        rf"\b(a|one|two|three|four|five|six|seven|eight|nine|\d)\s+hundred(?:\s+(?:and\s+)?({_two_re})(?![-\w]))?\b",
        _hundreds,
        t,
        flags=re.IGNORECASE,
    )

    # 2b. '<N> thousand [and] [<1..999>]' -> '10,000', '1,024', '25,000', etc.
    def _thousands(m: re.Match[str]) -> str:
        head_raw = m.group(1).strip().lower()
        k_val: int | None
        if head_raw == "a":
            k_val = 1
        elif head_raw.isdigit():
            k_val = int(head_raw)
        else:
            k_val = _two(head_raw)
        if not k_val:
            return m.group(0)
        tail_raw = (m.group(2) or "").strip()
        if not tail_raw:
            return f"{k_val * 1000:,}"
        lo_val = int(tail_raw) if tail_raw.isdigit() else _two(tail_raw)
        if lo_val is None:
            return m.group(0)
        return f"{k_val * 1000 + lo_val:,}"

    t = re.sub(
        rf"\b(a|{_two_re}|\d{{1,3}})\s+thousand(?:\s+(?:and\s+)?(\d{{1,3}}|{_two_re})(?![-\w]))?(?![-\w])",
        _thousands,
        t,
        flags=re.IGNORECASE,
    )

    # 3. Years 1600-2099: 'eighteen forty-eight' -> '1848', 'twenty twelve' -> '2012', 'nineteen oh four' -> '1904'
    # Guard (?![-\w]) prevents merging hyphenated modifiers like 'twenty ten-dollar' -> '20 10-dollar' (not '2010-dollar').
    _centuries = {**_teens, "twenty": 20}

    def _year(m: re.Match[str]) -> str:
        century = _centuries[m.group(1).lower()]
        tail = m.group(2).lower()
        if tail == "hundred":
            return str(century * 100)
        if tail.startswith("oh "):
            return str(century * 100 + _units[tail[3:]])
        lo = _two(tail)
        return str(century * 100 + lo) if lo is not None and lo >= 10 else m.group(0)

    _year_two_re = (
        r"(?:(?:twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety)(?:[-\s](?:one|two|three|four|five|six|seven|eight|nine))?"
        r"|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen)"
    )
    t = re.sub(
        rf"\b(sixteen|seventeen|eighteen|nineteen|twenty)\s+(hundred|oh (?:one|two|three|four|five|six|seven|eight|nine)|{_year_two_re})(?![-\w])",
        _year,
        t,
        flags=re.IGNORECASE,
    )

    # 4. Compound tens (hyphenated or space-separated): 'twenty-six' / 'twenty six' -> '26'
    def _compound(m: re.Match[str]) -> str:
        tens = m.group(1).lower()
        ones = (m.group(2) or m.group(3)).lower()
        return str(_WORD_NUM[tens] + _WORD_NUM[ones])

    t = re.sub(
        r"\b(twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety)(?:-(one|two|three|four|five|six|seven|eight|nine)\b|\s+(one|two|three|four|five|six|seven|eight|nine)(?![-\w]))",
        _compound,
        t,
        flags=re.IGNORECASE,
    )

    # 5. Any remaining standalone teens & round tens (10..90) -> digits ('fourteen' -> '14', 'fifteen' -> '15', 'forty percent' -> '40%')
    def _standalone_ten(m: re.Match[str]) -> str:
        w = m.group(1).lower()
        val = _tens_map.get(w) or _teens.get(w)
        return str(val if val is not None else m.group(0))

    t = re.sub(
        r"\b(ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety)\b",
        _standalone_ten,
        t,
        flags=re.IGNORECASE,
    )
    # 6. Convert '<1..999> thousand' ('25 thousand' -> '25,000', 'one thousand' -> '1,000')
    def _thousands_compact(m: re.Match[str]) -> str:
        head = m.group(1).lower()
        k_val = int(head) if head.isdigit() else _units.get(head, 1 if head == "a" else 0)
        if not k_val:
            return m.group(0)
        return f"{k_val:,},000" if k_val >= 1000 else f"{k_val * 1000:,}"

    t = re.sub(
        r"\b(a|one|two|three|four|five|six|seven|eight|nine|\d{1,3})\s+thousand\b",
        _thousands_compact,
        t,
        flags=re.IGNORECASE,
    )

    # 7. Convert standalone single-digit words ('one'..'nine') when followed by quantitative measurement units
    _single_digit_units_re = (
        r"feet|foot|inches|inch|meters?|millimeters?|centimeters?|kilometers?|miles?|"
        r"seconds?|milliseconds?|minutes?|hours?|days?|weeks?|months?|years?|decades?|"
        r"pounds?|kilograms?|grams?|ounces?|tons?|volts?|watts?|hertz|"
        r"liters?|gallons?|cups?|degrees?|percent|times|trials?|patients?|"
        r"drops?|threads?|channels?|electrodes?|dollars?|cents?"
    )
    t = re.sub(
        rf"(?<![-\w])(one|two|three|four|five|six|seven|eight|nine)(\s+|-)({_single_digit_units_re})\b",
        lambda m: f"{_units[m.group(1).lower()]}{m.group(2)}{m.group(3)}",
        t,
        flags=re.IGNORECASE,
    )
    t = re.sub(r"\b(\d+)\s+percent\b", r"\1%", t, flags=re.IGNORECASE)
    t = re.sub(r"\s*[—–]\s*", ", ", t)
    t = t.replace("…", "...")
    t = re.sub(r"\s{2,}", " ", t).strip()
    return t


def analyze_script(narrations: list[str], roles: list[str] | tuple[str, ...] | None = None) -> dict[str, Any]:
    """Per-clip and script-level plain-language metrics used by validators and the audit score sheet."""
    lines = [str(n or "").strip() for n in narrations]
    full = " ".join(lines)
    per_clip = []
    for i, line in enumerate(lines):
        per_clip.append(
            {
                "clip": i + 1,
                "role": (roles[i] if roles and i < len(roles) else None),
                "fk_grade": fk_grade(line),
                "jargon": find_jargon(line),
                "anatomy_terms": find_anatomy_terms(line),
                "tts_issues": tts_issues(line),
                "robotic_opener": bool(_ROBOTIC_OPENERS_RE.search(line)),
                "paper_voice": bool(_PAPER_VOICE_RE.search(line)),
                "second_person": bool(re.search(r"\byou(?:r|rs|rself)?\b", line, re.IGNORECASE)),
            }
        )
    jargon_all: list[str] = []
    for c in per_clip:
        for j in c["jargon"]:
            if j.lower() not in [x.lower() for x in jargon_all]:
                jargon_all.append(j)
    anatomy_all: list[str] = []
    for c in per_clip:
        for a in c["anatomy_terms"]:
            if a not in anatomy_all:
                anatomy_all.append(a)
    unglossed = []
    for c in per_clip:
        for a in c["anatomy_terms"]:
            plains = ANATOMY_FUNCTION_MAP.get(a, {}).get("plain", ())
            if not any(re.search(rf"(?<![a-z]){re.escape(p.lower())}(?![a-z])", lines[c["clip"] - 1].lower()) for p in plains):
                if a not in unglossed and not _glossed_elsewhere(a, lines):
                    unglossed.append(a)
    unglossed_jargon = [j for j in jargon_all if not _jargon_glossed_in_script(j, lines)]
    glossed_jargon = [j for j in jargon_all if _jargon_glossed_in_script(j, lines)]
    return {
        "script_fk_grade": fk_grade(full),
        "max_clip_fk_grade": max((c["fk_grade"] for c in per_clip), default=0.0),
        "jargon_terms": jargon_all,
        "glossed_jargon_terms": glossed_jargon,
        "unglossed_jargon_terms": unglossed_jargon,
        "anatomy_terms": anatomy_all,
        "unglossed_anatomy_terms": unglossed,
        "tts_issue_count": sum(len(c["tts_issues"]) for c in per_clip),
        "robotic_openers": sum(1 for c in per_clip if c["robotic_opener"]),
        "paper_voice": sum(1 for c in per_clip if c["paper_voice"]),
        "second_person_clips": sum(1 for c in per_clip if c["second_person"]),
        "clips": per_clip,
    }


GLOSSABLE_NEURO_TERMS: dict[str, tuple[str, ...]] = {
    "synapse": ("gap", "bridge", "junction", "connection", "spark", "wire", "link", "relay"),
    "synapses": ("gap", "bridge", "junction", "connection", "spark", "wire", "link", "relay"),
    "synaptic": ("gap", "bridge", "junction", "connection", "spark", "wire", "link", "relay"),
    "consolidation": ("lock", "save", "cement", "permanent", "long-term", "storage", "file", "write"),
    "encoding": ("record", "write", "capture", "stamp", "log", "register"),
    "lesion": ("scar", "wound", "damage", "damaged", "hole", "dead", "destroyed", "stroke", "cut"),
    "lesions": ("scar", "wound", "damage", "damaged", "hole", "dead", "destroyed", "stroke", "cut"),
    "neurotransmitter": ("chemical", "messenger", "fuel", "signal", "dopamine", "drop"),
    "neurotransmitters": ("chemical", "messenger", "fuel", "signal", "dopamine", "drop"),
    "plasticity": ("rewire", "rewiring", "grow", "regrow", "adapt", "reshape", "expand", "rebuild"),
    "neuroplasticity": ("rewire", "rewiring", "grow", "regrow", "adapt", "reshape", "expand", "rebuild"),
    "inhibitory": ("brake", "stop", "quiet", "hush", "block", "red light", "clamp"),
    "excitatory": ("gas", "pedal", "spark", "fire", "accelerate", "green light"),
    "prosthetic": ("artificial", "implant", "bionic", "robotic", "chip", "bypass", "device"),
    "prosthetics": ("artificial", "implant", "bionic", "robotic", "chip", "bypass", "device"),
    "inattentional": ("blind", "blindness", "spotlight", "miss", "invisible", "filter", "ignore"),
    "contralateral": ("opposite", "cross", "crossed"),
    "subcortical": ("deep", "ancient", "reflex", "beneath", "shortcut"),
    "ca1": ("memory", "hippocampus", "relay", "hub", "vault", "archivist", "loop", "circuit"),
    "ca3": ("memory", "hippocampus", "relay", "hub", "vault", "archivist", "loop", "circuit"),
    "v1": ("visual", "vision", "sight", "screen", "eye", "cortex"),
    "fmri": ("scan", "scanner", "blood", "glow", "lit up", "imaging"),
    "eeg": ("wave", "waves", "cap", "scalp", "electrical", "rhythm"),
    "dbs": ("pacemaker", "pulse", "wire", "electrode", "deep"),
}


def _jargon_glossed_in_script(term: str, lines: list[str]) -> bool:
    cues = GLOSSABLE_NEURO_TERMS.get(term.lower())
    if not cues:
        return False
    full_low = " ".join(lines).lower()
    return any(re.search(rf"(?<![a-z]){re.escape(c.lower())}(?![a-z])", full_low) for c in cues)


def _glossed_elsewhere(region: str, lines: list[str]) -> bool:
    plains = ANATOMY_FUNCTION_MAP.get(region, {}).get("plain", ())
    full = " ".join(lines).lower()
    return any(re.search(rf"(?<![a-z]){re.escape(p.lower())}(?![a-z])", full) for p in plains)


_QUANT_METRIC_RE = re.compile(
    r"\b(?:\d+(?:\.\d+)?)\s*(?:%|percent|grams?|g\b|kilograms?|kg\b|pounds?|lbs?\b|ounces?|oz\b|"
    r"millimeters?|mm\b|centimeters?|cm\b|meters?|kilometers?|km\b|inches|inch|feet|foot|ft\b|miles?|"
    r"milliseconds?|ms\b|seconds?|minutes?|hours?|months?|decades?|"
    r"volts?|v\b|watts?|hertz|hz\b|drops?|trials?|threads?|channels?|electrodes?)\b",
    flags=re.IGNORECASE,
)

_EVERYDAY_ANALOGY_CUE_RE = re.compile(
    r"\b(?:like\s+(?:a|an|the|your|dropping|walking|driving|flipping|holding|carrying|cutting|snapping|steering|pulling)|"
    r"as\s+(?:heavy|light|fast|slow|thin|thick|wide|tall|long|small|large|loud|quiet)\s+as|"
    r"(?:slower|faster|heavier|lighter|thinner|thicker|wider|longer|shorter|louder|quieter|smaller|larger|bigger)\s+than|"
    r"the\s+(?:size|weight|width|length|height|thickness|speed|pace|span|volume|cost)\s+of|"
    r"enough\s+to|barely\s+(?:wider|thicker|heavier|longer|slower|faster)|"
    r"(?:twice|half|ten\s+times|three\s+times|four\s+times|five\s+times|hundred\s+times)\s+(?:as|the|faster|slower|thinner|heavier)|"
    r"nickel|dime|penny|quarter|coin|broomstick|crowbar|javelin|pencil|human\s+hair|spiderweb|eyelash|"
    r"bowling\s+ball|baseball\s+bat|soccer\s+fields?|football\s+fields?|basketball\s+courts?|school\s+zone|blink|heartbeat|breath|"
    r"sugar\s+cube|teaspoon|coffee\s+cup|walnut|almond|seahorse|fist|postage\s+stamp|playing\s+card|baby)\b",
    flags=re.IGNORECASE,
)


def analyze_number_analogies(
    sentences: list[str],
    max_gap: int = 1,
) -> dict[str, Any]:
    """
    R57 quantitative-metric -> everyday-analogy pairing analyzer.
    Every sentence containing a measurable physical quantity (after `to_display_text` normalization,
    excluding standalone 4-digit calendar years and ordinal step labels) must be paired within
    `0..max_gap` sentences with a concrete everyday physical comparison.
    """
    norm_lines = [to_display_text(str(s or "").strip()) for s in sentences if str(s or "").strip()]
    paired: list[dict[str, Any]] = []
    unpaired: list[dict[str, Any]] = []
    glossed_metrics: set[str] = set()
    for idx, disp in enumerate(norm_lines):
        matches = [m.group(0) for m in _QUANT_METRIC_RE.finditer(disp)]
        if not matches:
            continue
        window = " ".join(norm_lines[idx : min(len(norm_lines), idx + max_gap + 1)])
        cue = _EVERYDAY_ANALOGY_CUE_RE.search(window)
        norm_keys = [re.sub(r"\s+", " ", m.strip().lower()) for m in matches]
        already_glossed = bool(norm_keys) and all(k in glossed_metrics for k in norm_keys)
        entry = {
            "sentence_index": idx + 1,
            "metrics": matches,
            "sentence": disp,
            "analogy_cue": cue.group(0) if cue else ("previously_glossed" if already_glossed else None),
        }
        if cue:
            glossed_metrics.update(norm_keys)
            paired.append(entry)
        elif already_glossed:
            paired.append(entry)
        else:
            unpaired.append(entry)
    return {
        "metric_sentence_count": len(paired) + len(unpaired),
        "paired_count": len(paired),
        "unpaired_count": len(unpaired),
        "paired": paired,
        "unpaired": unpaired,
    }


def validate_number_analogy_pairing(
    sentences: list[str],
    max_gap: int | None = None,
) -> list[str]:
    """Returns `[analogy]` issues for any quantitative metric lacking an immediate everyday analogy (R57)."""
    from pipeline.config import DIORAMA_NUMBER_ANALOGY_MAX_SENTENCE_GAP

    gap = DIORAMA_NUMBER_ANALOGY_MAX_SENTENCE_GAP if max_gap is None else int(max_gap)
    rep = analyze_number_analogies(sentences, max_gap=gap)
    issues: list[str] = []
    for item in rep["unpaired"]:
        issues.append(
            f"[analogy] sentence {item['sentence_index']} metric {item['metrics']} has no everyday physical analogy "
            f"within {gap} sentence(s): '{item['sentence']}' (R57)"
        )
    return issues


_STOCK_ANALOGY_IDIOMS: tuple[str, ...] = (
    "faster than a blink",
    "blink of an eye",
    "like a broken record",
    "tip of the iceberg",
    "needle in a haystack",
    "like flipping a switch",
    "flipping a light switch",
    "thinner than a human hair",
    "weight of a bowling ball",
    "size of a walnut",
    "size of an almond",
    "size of a seahorse",
)


def find_duplicate_analogy_idioms(sentences: list[str]) -> list[str]:
    """Detects stock analogy idioms repeated >= 2 times across distinct sentences of the same script (R57-C)."""
    lows = [str(s or "").lower() for s in sentences if str(s or "").strip()]
    dups: list[str] = []
    for idiom in _STOCK_ANALOGY_IDIOMS:
        hits = sum(1 for s in lows if idiom in s)
        if hits >= 2:
            dups.append(f"'{idiom}' repeated {hits}x")
    return dups


def find_ai_cliches_and_seminar_isms(text: str) -> dict[str, list[str]]:
    """
    YouTube Natural Script spoken-tone filter (adapted from `/natural_script`, R57-C):
    Flags AI-essay giveaway words/transitions (`DIORAMA_BANNED_AI_CLICHES`) AND
    academic slide-seminar transitions (`DIORAMA_BANNED_SEMINAR_TRANSITIONS`).
    """
    from pipeline.config import DIORAMA_BANNED_AI_CLICHES, DIORAMA_BANNED_SEMINAR_TRANSITIONS

    low = str(text or "").lower()
    cliches = [
        p for p in DIORAMA_BANNED_AI_CLICHES
        if re.search(rf"(?<![a-z]){re.escape(p.lower())}(?![a-z])", low)
    ]
    seminar_isms = [
        p for p in DIORAMA_BANNED_SEMINAR_TRANSITIONS
        if re.search(rf"(?<![a-z]){re.escape(p.lower())}(?![a-z])", low)
    ]
    return {"ai_cliches": cliches, "seminar_isms": seminar_isms}


__all__ = [
    "GLOSSABLE_NEURO_TERMS",
    "JARGON_LEXICON",
    "analyze_number_analogies",
    "analyze_script",
    "count_syllables",
    "find_ai_cliches_and_seminar_isms",
    "find_anatomy_terms",
    "find_duplicate_analogy_idioms",
    "find_jargon",
    "fk_grade",
    "number_to_words",
    "region_named_in",
    "to_display_text",
    "to_expressive_tts_text",
    "to_tts_text",
    "tts_issues",
    "validate_number_analogy_pairing",
    "year_to_words",
]
