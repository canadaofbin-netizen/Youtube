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
    rest = n % 1_000_000
    return number_to_words(n // 1_000_000) + " million" + ("" if rest == 0 else " " + number_to_words(rest))


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


def to_tts_text(text: str) -> str:
    """Deterministic TTS normalization: numbers/percent/years to words, unsafe punctuation to commas/periods."""
    t = str(text or "")

    def _abbr(m: re.Match[str]) -> str:
        return _ABBREV_EXPAND.get(m.group(0).lower(), m.group(0))

    t = re.sub(r"\b(?:Dr|Mr|Mrs|Ms|Prof|St|vs|etc|e\.g|i\.e|U\.S|Ph\.D)\.", _abbr, t, flags=re.IGNORECASE)
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

    # 1. 'two thousand [and] <1..99>' -> '2009', '2024', etc.
    def _two_thousand(m: re.Match[str]) -> str:
        tail = (m.group(1) or "").strip()
        if not tail:
            return "2000"
        lo = _two(tail)
        return str(2000 + lo) if lo is not None else m.group(0)

    t = re.sub(
        rf"\btwo\s+thousand(?:\s+(?:and\s+)?({_two_re}))?\b",
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
        rf"\b(a|one|two|three|four|five|six|seven|eight|nine|\d)\s+hundred(?:\s+(?:and\s+)?({_two_re}))?\b",
        _hundreds,
        t,
        flags=re.IGNORECASE,
    )

    # 3. Years 1600-1999: 'eighteen forty-eight' -> '1848', 'nineteen oh four' -> '1904'
    def _year(m: re.Match[str]) -> str:
        century = _teens[m.group(1).lower()]
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
        rf"\b(sixteen|seventeen|eighteen|nineteen)\s+(hundred|oh (?:one|two|three|four|five|six|seven|eight|nine)|{_year_two_re})\b",
        _year,
        t,
        flags=re.IGNORECASE,
    )

    # 4. Compound tens (hyphenated or space-separated): 'twenty-six' / 'twenty six' -> '26'
    def _compound(m: re.Match[str]) -> str:
        tens, ones = m.group(1).lower(), m.group(2).lower()
        return str(_WORD_NUM[tens] + _WORD_NUM[ones])

    t = re.sub(
        r"\b(twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety)[-\s](one|two|three|four|five|six|seven|eight|nine)\b",
        _compound,
        t,
        flags=re.IGNORECASE,
    )

    # 5. Any remaining standalone teens & round tens (10..90) -> digits ('fourteen' -> '14', 'fifteen' -> '15', 'forty percent' -> '40%')
    def _standalone_ten(m: re.Match[str]) -> str:
        w = m.group(1).lower()
        val = _tens_map.get(w) or _teens.get(w)
        return str(val) if val is not None else m.group(0)

    t = re.sub(
        r"\b(ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety)\b",
        _standalone_ten,
        t,
        flags=re.IGNORECASE,
    )
    t = re.sub(r"\b(\d+)\s+percent\b", r"\1%", t, flags=re.IGNORECASE)
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
    return {
        "script_fk_grade": fk_grade(full),
        "max_clip_fk_grade": max((c["fk_grade"] for c in per_clip), default=0.0),
        "jargon_terms": jargon_all,
        "anatomy_terms": anatomy_all,
        "unglossed_anatomy_terms": unglossed,
        "tts_issue_count": sum(len(c["tts_issues"]) for c in per_clip),
        "robotic_openers": sum(1 for c in per_clip if c["robotic_opener"]),
        "paper_voice": sum(1 for c in per_clip if c["paper_voice"]),
        "second_person_clips": sum(1 for c in per_clip if c["second_person"]),
        "clips": per_clip,
    }


def _glossed_elsewhere(region: str, lines: list[str]) -> bool:
    plains = ANATOMY_FUNCTION_MAP.get(region, {}).get("plain", ())
    full = " ".join(lines).lower()
    return any(re.search(rf"(?<![a-z]){re.escape(p.lower())}(?![a-z])", full) for p in plains)


__all__ = [
    "JARGON_LEXICON",
    "analyze_script",
    "count_syllables",
    "find_anatomy_terms",
    "find_jargon",
    "fk_grade",
    "number_to_words",
    "region_named_in",
    "to_display_text",
    "to_tts_text",
    "tts_issues",
    "year_to_words",
]
