"""
Stage 6: Publish Packaging, A/B Thumbnail Variants & Metadata Export
Prepares YouTube Shorts metadata, SEO tags, AI content declarations,
and 3 high-impact thumbnail variants for sequential A/B testing.
"""

import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont, ImageOps

from pipeline.config import (
    BANNED_COMMENT_VIOLENCE_TOKENS,
    DIORAMA_V7_STYLE_PROFILE,
    EXPRESSIVE_25D_V8_STYLE_PROFILE,
    FONT_CONDENSED_BLACK_PATH,
    FONT_FALLBACK_PATH,
    FONT_PRIMARY_PATH,
    PRE_R68H_FROZEN_V8_PROJECTS,
    PROJECTS_DIR,
    R68_DESCRIPTION_HASHTAG_MAX,
    R68_TITLE_MAX_CHARS,
    R68_TITLE_MAX_WORDS,
    R68_TITLE_MIN_WORDS,
    R68D_BANNED_AI_CLICHES,
    R68D_DESCRIPTION_WORD_RANGE,
    RGB_DANGER_RED,
    RGB_DEEP_NAVY,
    RGB_NEUTRAL_WHITE,
    RGB_SECONDARY_TEAL,
    RGB_SIGNAL_GOLD,
    SHORTS_EXPRESSIVE_V8_DURATION_MIN_SEC,
    SHORTS_EXPRESSIVE_V8_PROFILE,
    TITLE_MAX_CHARS_DIORAMA,
    VIDEO_HEIGHT,
    VIDEO_WIDTH,
    is_diorama_profile,
    is_diorama_v7_plan,
    is_expressive_v8_plan,
)
from pipeline.storage import ProjectStorage, numeric_clip_sort_key
from pipeline.studio.config import (
    BANNED_OFF_TOPIC_TECH_TAGS,
    CHANNEL_RESIDENCE_COUNTRY,
    CHANNEL_RESIDENCE_COUNTRY_NAME,
    DEFAULT_FALLBACK_PILLAR,
    DEFAULT_VIDEO_CATEGORY,
    TARGET_AUDIENCE_REGION,
    TITLE_DESCRIPTION_LANGUAGE_CODE,
    TITLE_DESCRIPTION_LANGUAGE_LABEL,
    VIDEO_LANGUAGE_CODE,
    VIDEO_LANGUAGE_LABEL,
)


_TAG_STOPWORDS: frozenset[str] = frozenset({
    "the", "and", "for", "with", "from", "that", "this", "your", "their", "into",
    "over", "under", "when", "what", "why", "how", "can", "cant", "does", "did",
    "one", "two", "three", "four", "five", "more", "less", "than", "after", "before",
    "about", "have", "has", "had", "were", "was", "are", "been", "being", "even",
    "never", "every", "still", "just", "only", "make", "makes", "made", "stop",
})

_DOMAIN_CLEAN_TAG_PAIRS: dict[str, tuple[str, ...]] = {
    "habits": ("habits", "self control", "willpower"),
    "sleep": ("sleep science", "insomnia", "sleep"),
    "memory": ("memory", "cognitive psychology", "learning"),
    "anxiety": ("emotions", "anxiety", "fear response"),
    "emotions": ("emotions", "emotional regulation", "social psychology"),
    "decisions": ("decision making", "behavioral psychology", "choice paradox"),
    "decision_making": ("decision making", "behavioral psychology", "choice paradox"),
    "social": ("social psychology", "human behavior", "everyday psychology"),
    "attention": ("attention", "focus", "cognitive psychology"),
}

_PILLAR_CLEAN_TAG_PAIRS: dict[str, tuple[str, ...]] = {
    "brain_mysteries": ("cognitive psychology", "brain facts"),
    "brain_basics": ("everyday psychology", "brain facts"),
    "brain_health": ("sleep science", "everyday psychology"),
    "brain_history": ("psychology experiment", "cognitive psychology"),
    "brain_news": ("neuroscience research", "brain facts"),
    "bci_ethics": ("cognitive psychology", "decision making"),
    "bci_tech": ("neural engineering", "neurotechnology"),
}

_KNOWN_ANATOMY_PHRASES: tuple[str, ...] = (
    "prefrontal cortex",
    "amygdala",
    "hippocampus",
    "cerebellum",
    "brainstem",
    "basal ganglia",
    "nucleus accumbens",
    "anterior cingulate cortex",
    "insula",
    "hypothalamus",
    "thalamus",
    "motor cortex",
    "somatosensory cortex",
    "visual cortex",
    "vagus nerve",
    "dopamine",
)


def _contains_banned_tech_tag(tag: str) -> str | None:
    low = re.sub(r"\s+", " ", str(tag or "").strip().lower())
    if not low:
        return None
    if low in BANNED_OFF_TOPIC_TECH_TAGS:
        return low
    for banned in BANNED_OFF_TOPIC_TECH_TAGS:
        pat = r"\b" + r"\s+".join(re.escape(part) for part in banned.split()) + r"\b"
        if re.search(pat, low):
            return banned
    return None


def validate_episode_tags_hygiene(
    tags: list[str] | tuple[str, ...] | None,
    pillar: str = DEFAULT_FALLBACK_PILLAR,
    *,
    raise_on_error: bool = True,
) -> list[str]:
    """
    Rule R75 Episode Tag Hygiene Gate:
      - Requires `8..12` clean episode tags (`<= 480` Studio tag chars total)
      - Must include `"shorts"` (case-insensitive)
      - Zero `#` prefixes and zero Hangul characters
      - Hard-blocks `BANNED_OFF_TOPIC_TECH_TAGS` whenever `pillar != "bci_tech"`
      Returns normalized `list[str]` when valid; raises `ValueError` when `raise_on_error=True`
      (or returns list of error strings when `raise_on_error=False`).
    """
    errors: list[str] = []
    if not isinstance(tags, (list, tuple)) or not tags:
        errors.append("[r75_tags] tags list is empty or missing (requires 8..12 clean tags including 'shorts')")
        if raise_on_error:
            raise ValueError("; ".join(errors))
        return errors

    eff_pillar = str(pillar or DEFAULT_FALLBACK_PILLAR).strip().lower()
    cleaned: list[str] = []
    seen_low: set[str] = set()
    for raw_t in tags:
        t = re.sub(r"\s+", " ", str(raw_t or "").strip())
        if not t:
            continue
        if "#" in t:
            errors.append(f"[r75_tags] '#' forbidden inside YouTube Studio tag chip: {t!r}")
        if re.search(r"[\uAC00-\uD7A3\u3130-\u318F]", t):
            errors.append(f"[r75_tags] non-English Hangul forbidden in tag chip: {t!r}")
        if eff_pillar != "bci_tech":
            hit_banned = _contains_banned_tech_tag(t)
            if hit_banned is not None:
                errors.append(
                    f"[r75_tags] banned off-topic hardware/tech tag {t!r} (matched {hit_banned!r}) forbidden for pillar={eff_pillar!r}"
                )
        low_t = t.lower()
        if low_t not in seen_low:
            seen_low.add(low_t)
            cleaned.append(t)

    if not (8 <= len(cleaned) <= 12):
        errors.append(f"[r75_tags] tag count {len(cleaned)} outside required 8..12 range: {cleaned}")
    if "shorts" not in seen_low:
        errors.append("[r75_tags] tags must include 'shorts' routing tag")
    total_chars = sum(len(t) for t in cleaned) + max(0, len(cleaned) - 1) * 2
    if total_chars > 480:
        errors.append(f"[r75_tags] total Studio tag char count {total_chars} exceeds 480/500 safety cap")

    if errors:
        if raise_on_error:
            raise ValueError("; ".join(errors))
        return errors
    return cleaned if raise_on_error else []


def build_clean_episode_tags(
    pillar: str = DEFAULT_FALLBACK_PILLAR,
    script_doc: dict[str, Any] | None = None,
    dossier: Path | str | dict[str, Any] | None = None,
    *,
    project_id: str = "",
    script: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
    brain_regions: list[str] | tuple[str, ...] | None = None,
    title: str = "",
    everyday_domain: str = "",
    extra_tags: list[str] | tuple[str, ...] | None = None,
    target_count: int = 10,
) -> list[str]:
    """
    Deterministic Rule R75 Episode Tag Builder (`8..12` clean psychology + neuroscience tags + `"shorts"`).
    Guarantees zero `BANNED_OFF_TOPIC_TECH_TAGS` whenever `pillar != "bci_tech"`.
    """
    _ = project_id
    s_doc = script_doc if isinstance(script_doc, dict) else (script if isinstance(script, dict) else {})
    m_doc = metadata if isinstance(metadata, dict) else {}
    eff_pillar = (
        str(pillar or s_doc.get("pillar") or m_doc.get("pillar") or DEFAULT_FALLBACK_PILLAR).strip().lower()
        or DEFAULT_FALLBACK_PILLAR
    )
    if eff_pillar == "bci_tech" and not s_doc.get("pillar") and not m_doc.get("pillar") and pillar == DEFAULT_FALLBACK_PILLAR:
        eff_pillar = DEFAULT_FALLBACK_PILLAR

    bundle = _load_dossier_bundle(
        dossier or s_doc.get("dossier") or s_doc.get("dossier_slug") or m_doc.get("dossier_slug") or m_doc.get("dossier")
    )
    d_meta = bundle.get("dossier") if isinstance(bundle.get("dossier"), dict) else {}

    eff_title = str(title or s_doc.get("title") or m_doc.get("title") or d_meta.get("title") or "").strip()
    eff_domain = str(
        everyday_domain
        or s_doc.get("everyday_domain")
        or m_doc.get("everyday_domain")
        or d_meta.get("everyday_domain")
        or ""
    ).strip().lower()

    candidates: list[str] = [
        "psychology",
        "neuroscience",
        "human behavior",
        "brain science",
    ]
    if eff_domain in _DOMAIN_CLEAN_TAG_PAIRS:
        candidates.extend(_DOMAIN_CLEAN_TAG_PAIRS[eff_domain])
    if eff_pillar in _PILLAR_CLEAN_TAG_PAIRS:
        candidates.extend(_PILLAR_CLEAN_TAG_PAIRS[eff_pillar])

    # Extract anatomical circuits mentioned in script/dossier/explicit brain_regions
    corpus_parts: list[str] = [
        eff_title,
        str(s_doc.get("viewer_description") or m_doc.get("description") or ""),
        " ".join(str(x) for x in (s_doc.get("sentences") or []) if str(x).strip()),
        json.dumps(list(brain_regions or []) + list(d_meta.get("brain_regions") or []), ensure_ascii=False),
    ]
    corpus_low = " ".join(corpus_parts).lower()
    for anat in _KNOWN_ANATOMY_PHRASES:
        if anat in corpus_low:
            candidates.append(anat)

    # Caller-provided clean episode tags (filtered through R75 hygiene)
    for ext in extra_tags or s_doc.get("tags") or []:
        t_clean = re.sub(r"[#]+", "", str(ext or "")).strip()
        if t_clean:
            candidates.append(t_clean)

    # Extract 1-2 clean topic words from title / slug
    slug_raw = str(s_doc.get("dossier") or s_doc.get("dossier_slug") or (dossier if isinstance(dossier, str) else "") or "")
    title_words = [
        w.lower()
        for w in re.findall(r"[A-Za-z]{4,}", f"{eff_title} {slug_raw.replace('_', ' ')}")
        if w.lower() not in _TAG_STOPWORDS
        and w.lower() not in {"brain", "science", "psychology", "neuroscience", "shorts", "study", "university", "pilot", "previs"}
    ]
    for tw in title_words[:4]:
        candidates.append(tw)

    fallback_pad = (
        "everyday psychology",
        "cognitive psychology",
        "brain facts",
        "decision making",
        "self control",
        "memory",
        "emotions",
        "social psychology",
    )
    candidates.extend(fallback_pad)

    cap = max(8, min(12, int(target_count)))
    selected: list[str] = []
    seen: set[str] = set()
    for cand in candidates:
        c_norm = re.sub(r"\s+", " ", str(cand or "").strip())
        if not c_norm or "#" in c_norm or re.search(r"[\uAC00-\uD7A3\u3130-\u318F]", c_norm):
            continue
        if len(c_norm) > 32:
            continue
        if eff_pillar != "bci_tech" and _contains_banned_tech_tag(c_norm) is not None:
            continue
        c_low = c_norm.lower()
        if c_low == "shorts" or c_low in seen:
            continue
        seen.add(c_low)
        selected.append(c_norm)
        if len(selected) >= cap - 1:
            break

    selected.append("shorts")
    return validate_episode_tags_hygiene(selected, pillar=eff_pillar, raise_on_error=True)


def build_diorama_paradox_title(clause_1: str, clause_2: str) -> str:
    """
    R60 2-Clause US English Paradox Title Builder (`<= TITLE_MAX_CHARS_DIORAMA`):
      `[Clause 1: Shocking Concrete Anomaly / Number], [Clause 2: Hidden Brain / Psychological Reality]`
    """
    c1 = str(clause_1 or "").strip().rstrip(".,;:")
    c2 = str(clause_2 or "").strip().rstrip(".")
    joined = f"{c1}, {c2}" if (c1 and c2) else (c1 or c2)
    if len(joined) > TITLE_MAX_CHARS_DIORAMA:
        joined = joined[: TITLE_MAX_CHARS_DIORAMA - 3].rstrip() + "..."
    return joined


US_HIGH_CTR_TITLE_ARCHETYPES: tuple[str, ...] = (
    "two_clause_paradox",
    "open_loop_question",
    "year_experiment_stamp",
    "direct_brain_address",
    "numeric_contrast",
)


def classify_us_title_archetype(title: str) -> str | None:
    """Classifies a title into one of the 5 US High-CTR Documentary Title Archetypes (R60)."""
    t = str(title or "").strip()
    t_low = t.lower()
    if not t:
        return None
    has_sep = any(sep in t for sep in (",", "—", " - ", ":"))
    has_q = t.endswith("?") and t_low.startswith(("why ", "how ", "what ", "can ", "when "))
    has_year = bool(re.search(r"\b(18|19|20)\d{2}\b", t))
    has_num = bool(re.search(r"\b\d+\b", t))
    if has_year and (has_sep or has_q):
        return "year_experiment_stamp"
    if has_q and (has_num or has_sep or len(t.split()) >= 6):
        return "open_loop_question"
    if ("your brain" in t_low or "your mind" in t_low) and (has_sep or t.endswith("?")):
        return "direct_brain_address"
    if has_num and has_sep:
        return "numeric_contrast"
    if has_sep:
        return "two_clause_paradox"
    return None


def validate_expressive_v8_title(title: str) -> list[str]:
    """
    Validates R68 Expressive v8 Shorts Title:
      - `4..8` words (`R68_TITLE_MIN_WORDS..R68_TITLE_MAX_WORDS`)
      - `<= 55` characters (`R68_TITLE_MAX_CHARS`)
      - Zero hashtags (`#`) and 100% English (`en-US`, zero Hangul)
    """
    t = str(title or "").strip()
    issues: list[str] = []
    if not t:
        return ["[title] empty title (R68)"]
    if len(t) > R68_TITLE_MAX_CHARS:
        issues.append(f"[title] length {len(t)} > {R68_TITLE_MAX_CHARS} chars (R68)")
    words = [w for w in t.split() if w.strip()]
    if not (R68_TITLE_MIN_WORDS <= len(words) <= R68_TITLE_MAX_WORDS):
        issues.append(
            f"[title] word count {len(words)} outside {R68_TITLE_MIN_WORDS}..{R68_TITLE_MAX_WORDS} words (R68)"
        )
    if re.search(r"[\uAC00-\uD7A3\u3130-\u318F]", t):
        issues.append("[title] non-English Hangul characters forbidden in ALL ABOUT BRAIN title (R36/R68)")
    if "#" in t:
        issues.append("[title] hashtags forbidden in R68 Expressive v8 title")
    return issues


def build_expressive_v8_pinned_comment(
    *,
    doi: str = "",
    debate_question: str = "",
    cameo_prompt: str = "",
    include_doi: bool = False,
) -> str:
    """
    Builds R68-D zero-hashtag, zero-AI-smell casual pinned comment:
      - Plain 1-sentence everyday viewer question ending with '?'
      - Strips creator-bet prefixes ('My bet:', 'Hot take:', etc.), em-dashes ('—' / ' -- '),
        hashtags, Hangul, markdown, and raw DOIs unless `include_doi=True` (frozen pilots).
      - Includes `cameo_prompt` only when explicitly non-empty.
    """
    raw_doi = str(doi or "").strip()
    doi_url = raw_doi if raw_doi.startswith("http") else (f"https://doi.org/{raw_doi}" if raw_doi else "")

    def _clean_pin_piece(val: str) -> str:
        s = re.sub(r"#\w+", "", str(val or ""))
        s = re.sub(r"[\uAC00-\uD7A3\u3130-\u318F]+", "", s)
        s = s.replace("**", "").replace("*", "").replace("`", "")
        if not include_doi:
            s = re.sub(r"https?://(?:dx\.)?doi\.org/\S+", "", s, flags=re.IGNORECASE)
            s = re.sub(r"\b10\.\d{4,9}/\S+", "", s)
        s = re.sub(r"\s+", " ", s).strip()
        if not include_doi and s:
            bet_pref_re = r"^(?:my honest bet|my bet|hot take|honest take|hard take)\s*:\s*"
            if re.match(bet_pref_re, s, flags=re.IGNORECASE):
                if "—" in s:
                    s = s.split("—", 1)[1].strip()
                elif " -- " in s:
                    s = s.split(" -- ", 1)[1].strip()
                else:
                    s = re.sub(bet_pref_re, "", s, flags=re.IGNORECASE).strip()
            s = re.sub(r"\s*—\s*", ", ", s)
            s = re.sub(r"\s+--\s+", ", ", s)
            s = re.sub(r",\s*,", ",", s)
            s = re.sub(r"\s+,", ",", s)
            s = re.sub(r"\s+", " ", s).strip(" ,;-")
            if s and s[0].islower():
                s = s[0].upper() + s[1:]
        return s

    parts: list[str] = []
    q_clean = _clean_pin_piece(debate_question)
    if q_clean and not q_clean.endswith("?"):
        q_clean = q_clean.rstrip(".!,:; ") + "?"
    c_clean = _clean_pin_piece(cameo_prompt)
    if q_clean:
        parts.append(q_clean)
    if c_clean and c_clean not in q_clean:
        parts.append(c_clean)
    if include_doi and doi_url:
        parts.append(f"Primary peer-reviewed study: {doi_url}")
    return "\n\n".join(parts).strip()


def validate_diorama_paradox_title(
    title: str,
    *,
    adjacent_titles: list[str] | None = None,
    is_expressive_v8: bool = False,
) -> list[str]:
    """
    Validates R60 US High-CTR Documentary Title (`100% ASCII/en-US`, `<= TITLE_MAX_CHARS_DIORAMA`,
    matching one of the 5 US CTR archetypes, and optional adjacent-slot archetype diversity),
    or R68 (`4..8` words, `<= 55` chars, `0` hashtags) when `is_expressive_v8=True`.
    """
    if is_expressive_v8:
        return validate_expressive_v8_title(title)
    t = str(title or "").strip()
    issues: list[str] = []
    if not t:
        return ["[title] empty title (R60)"]
    if len(t) > TITLE_MAX_CHARS_DIORAMA:
        issues.append(f"[title] length {len(t)} > {TITLE_MAX_CHARS_DIORAMA} chars (R60)")
    if re.search(r"[\uAC00-\uD7A3\u3130-\u318F]", t):
        issues.append("[title] non-English Hangul characters forbidden in ALL ABOUT BRAIN title (R36/R60)")
    archetype = classify_us_title_archetype(t)
    if archetype is None:
        issues.append(
            "[title] Title must match one of the 5 US High-CTR Archetypes (2-clause comma/dash/colon paradox, "
            "Why/How...? open-loop question, year/experiment stamp, 'Your Brain...' direct address, or numeric contrast) (R60)"
        )
    if "#" in t:
        issues.append("[title] inline hashtags forbidden in Neuro-Diorama Title (R60)")
    if adjacent_titles and archetype is not None:
        adj_archs = [classify_us_title_archetype(at) for at in adjacent_titles if str(at or "").strip()]
        if len(adj_archs) >= 2 and all(a == archetype for a in adj_archs[-2:]):
            issues.append(
                f"[title] 3 consecutive episodes share identical title archetype '{archetype}' — rotate US CTR archetypes (R60)"
            )
    return issues


_INTERNAL_PIPELINE_TOKENS_RE = re.compile(
    r"\b(?:expressive_25d_v8|shorts_expressive_v8|expressive_us_v8|foil_v8|porcelain_cinematic_v7|"
    r"lowpoly_pastel_v7|neuro_diorama|classic_v5|dynamic_rush_v7|dynamic_us_v7|"
    r"schema_version|R57-H2|R63-P|R68|DQ1-DQ12|TQ1-TQ7|RQ1-RQ5|andrew_v7|emma_v7|ava_v7|aria_v7|christopher_v7)\b",
    flags=re.IGNORECASE,
)


def strip_internal_pipeline_tokens(text: str) -> str:
    """Removes internal pipeline identifiers from public-facing descriptions/titles."""
    cleaned = _INTERNAL_PIPELINE_TOKENS_RE.sub("", str(text or ""))
    cleaned = re.sub(r"\(\s*\)|\[\s*\]", "", cleaned)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    cleaned = re.sub(r"[ \t]+\n", "\n", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip(" \t\r\n-|—")


def _scrub_experiment_nicknames(text: str, omit_nicknames: list[str] | None) -> str:
    raw = str(text or "")
    split_match = re.search(r"\b(?:Primary Peer-Reviewed Sources?|Research):", raw)
    head = raw[: split_match.start()] if split_match else raw
    tail = raw[split_match.start() :] if split_match else ""
    cleaned = head
    for nick in omit_nicknames or []:
        n_clean = str(nick or "").strip()
        if n_clean:
            cleaned = re.sub(re.escape(n_clean), "this experiment", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    return (cleaned + tail).strip()


_R68D_DOI_URL_RE = re.compile(r"https?://(?:dx\.)?doi\.org/\S+", flags=re.IGNORECASE)
_R68D_DOI_RAW_RE = re.compile(r"\b10\.\d{4,9}/\S+")
_R68D_HANGUL_RE = re.compile(r"[\uAC00-\uD7A3\u3130-\u318F]+")


def _sanitize_r68d_plain_text(text: str, *, allow_colon: bool = False) -> str:
    s = strip_internal_pipeline_tokens(str(text or ""))
    s = _R68D_HANGUL_RE.sub("", s)
    s = re.sub(r"#\w+", "", s)
    s = s.replace("**", "").replace("*", "").replace("`", "")
    s = _R68D_DOI_URL_RE.sub("", s)
    s = _R68D_DOI_RAW_RE.sub("", s)
    s = re.sub(r"https?://\S+", "", s)
    s = re.sub(r"\s*—\s*", ", ", s)
    s = re.sub(r"\s+--\s+", ", ", s)
    s = re.sub(r"\s*;\s*", ", ", s)
    if not allow_colon:
        s = re.sub(r"(?<!\d):(?!\d)", ",", s)
    for cliche in R68D_BANNED_AI_CLICHES:
        if cliche in ("—", " -- "):
            continue
        s = re.sub(re.escape(cliche), "", s, flags=re.IGNORECASE)
    s = re.sub(r",\s*,", ",", s)
    s = re.sub(r"\s+([,\.\?\!])", r"\1", s)
    s = re.sub(r"[ \t]{2,}", " ", s)
    return s.strip(" \t\r\n,;-")


def _load_dossier_bundle(dossier: Path | str | dict[str, Any] | None) -> dict[str, Any]:
    if isinstance(dossier, dict):
        return dossier
    if dossier is None:
        return {}
    d_path = Path(dossier)
    if not d_path.is_dir():
        try:
            from pipeline import research_dossier as rd

            cand = rd.dossier_dir(str(dossier))
            if cand.is_dir():
                d_path = cand
        except Exception:
            pass
    if not d_path.is_dir():
        return {}

    def _rj(name: str) -> Any:
        fp = d_path / name
        if not fp.is_file():
            return {}
        try:
            return json.loads(fp.read_text(encoding="utf-8"))
        except Exception:
            return {}

    return {
        "dossier": _rj("dossier.json"),
        "sources": _rj("01_sources.json"),
        "facts": _rj("02_facts.json"),
    }


def _build_r68d_research_line(
    script_doc: dict[str, Any],
    dossier: Path | str | dict[str, Any] | None = None,
    *,
    source_summary: str = "",
) -> str:
    explicit = str(script_doc.get("research_line") or "").strip()
    if explicit:
        body = re.sub(r"^research\s*:\s*", "", explicit, flags=re.IGNORECASE)
        body = _sanitize_r68d_plain_text(body, allow_colon=False).rstrip(".")
        if body:
            return f"Research: {body}."

    bundle = _load_dossier_bundle(dossier)
    d_meta = bundle.get("dossier") if isinstance(bundle.get("dossier"), dict) else {}
    s_doc = bundle.get("sources")
    src_list = (
        (s_doc.get("primary_sources") or s_doc.get("sources") or [])
        if isinstance(s_doc, dict)
        else (s_doc if isinstance(s_doc, list) else [])
    )
    primary = src_list[0] if (src_list and isinstance(src_list[0], dict)) else {}
    pc = d_meta.get("primary_case") if isinstance(d_meta.get("primary_case"), dict) else {}

    author_label = ""
    raw_authors = primary.get("authors")
    if isinstance(raw_authors, list) and raw_authors:
        first_a = str(raw_authors[0] or "").strip()
        surname = first_a.split(",")[0].strip().split()[-1] if ("," not in first_a and first_a.split()) else first_a.split(",")[0].strip()
        if surname:
            author_label = f"{surname} et al." if len(raw_authors) > 1 else surname
    elif isinstance(raw_authors, str) and raw_authors.strip():
        raw_a = raw_authors.strip()
        first_chunk = raw_a.split(";")[0].split(",")[0].strip()
        author_label = f"{first_chunk} et al." if ("," in raw_a or ";" in raw_a or " and " in raw_a.lower() or "&" in raw_a) and "et al" not in first_chunk.lower() else first_chunk

    inst = str(pc.get("institution") or pc.get("place") or primary.get("journal") or primary.get("venue") or "").strip()
    inst = _sanitize_r68d_plain_text(inst, allow_colon=False).rstrip(".")
    years: list[str] = []
    for s in src_list[:2]:
        if isinstance(s, dict):
            y = str(s.get("year") or "").strip()
            if re.fullmatch(r"(?:18|19|20)\d{2}", y) and y not in years:
                years.append(y)
    if not years:
        y_pc = str(pc.get("year") or "").strip()
        if re.fullmatch(r"(?:18|19|20)\d{2}", y_pc):
            years.append(y_pc)

    if author_label or inst:
        core_parts = [p for p in (_sanitize_r68d_plain_text(author_label, allow_colon=False), inst) if p]
        yr_str = f" ({', '.join(years)})" if years else ""
        joined = ", ".join(core_parts) + yr_str
        joined = _sanitize_r68d_plain_text(joined, allow_colon=False).rstrip(".")
        if joined:
            return f"Research: {joined}."

    for st in script_doc.get("data_stamps") or []:
        if isinstance(st, dict):
            sc = _sanitize_r68d_plain_text(str(st.get("source_citation") or ""), allow_colon=False).rstrip(".")
            if sc:
                return f"Research: {sc}."

    if source_summary:
        ss_first = str(source_summary).split("\n")[0].strip()
        m_auth_yr = re.search(r"([A-Z][A-Za-z\-\s&]+?(?:et al\.)?)\s*\((\d{4})[^)]*\)", ss_first)
        if m_auth_yr:
            a_clean = _sanitize_r68d_plain_text(m_auth_yr.group(1), allow_colon=False)
            return f"Research: {a_clean} ({m_auth_yr.group(2)})."
        ss_clean = _sanitize_r68d_plain_text(ss_first, allow_colon=False).rstrip(".")
        if ss_clean and len(ss_clean.split()) <= 14:
            return f"Research: {ss_clean}."

    return "Research: Peer-reviewed clinical neuroscience study."


_R88A_CREDIT_LINE_RE = re.compile(
    r"^Image credit:\s+\S.*?,\s*CC[- ]BY(?:[- ][1-4]\.\d)?\s+\(https?://\S+\)\.$"
)
_R89_VIDEO_CREDIT_LINE_RE = re.compile(
    r"^Video credit:\s+Adapted from\s+\S.*?,\s+\S.*?\s+\(\d{4}\),\s+\S.*?,\s*CC[- ]BY(?:[- ][1-4]\.\d)?\s+\(https?://creativecommons\.org/licenses/by/[1-4]\.\d/?\)\s+—\s+cropped & muted\s+\(https?://\S+\)\.$"
)


def extract_cc_by_archival_credits(project_dir_or_manifest: Path | str | dict[str, Any] | None) -> list[str]:
    """
    Extracts viewer-facing `Image credit: <Author>, <License Label> (<URI>).` lines from
    `03_visuals/archival_inserts_manifest.json` ONLY for entries classified as `"direct_insert_cc_by"`.
    Public Domain / CC0 entries emit zero credit lines.
    """
    if project_dir_or_manifest is None:
        return []
    doc: dict[str, Any] | None = None
    if isinstance(project_dir_or_manifest, dict):
        doc = project_dir_or_manifest
    else:
        p = Path(project_dir_or_manifest)
        mf_path: Path | None = None
        if p.is_file() or p.suffix.lower() == ".json":
            mf_path = p if p.is_file() else None
        else:
            for cand in (p / "03_visuals" / "archival_inserts_manifest.json", p / "archival_inserts_manifest.json"):
                if cand.is_file():
                    mf_path = cand
                    break
        if mf_path is not None:
            try:
                loaded = json.loads(mf_path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    doc = loaded
            except Exception:  # noqa: BLE001
                doc = None
    if not isinstance(doc, dict):
        return []

    from pipeline.archival_insert import normalize_cc_by_label
    from pipeline.real_world_refs import classify_media_license

    entries = doc.get("inserts")
    if not isinstance(entries, list):
        entries = doc.get("clips") if isinstance(doc.get("clips"), list) else doc.get("items")
    if not isinstance(entries, list):
        return []

    credits: list[str] = []
    for item in entries:
        if not isinstance(item, dict):
            continue
        lic_raw = str(item.get("license") or item.get("license_short_name") or "").strip()
        if classify_media_license(lic_raw) != "direct_insert_cc_by":
            continue
        author = " ".join(str(item.get("author") or item.get("attribution") or "").split()).strip().rstrip(".")
        uri = " ".join(str(item.get("license_uri") or "").split()).strip()
        if not author or not uri:
            continue
        lic_label = normalize_cc_by_label(lic_raw)
        line = f"Image credit: {author}, {lic_label} ({uri})."
        if line not in credits:
            credits.append(line)
    return credits


def extract_cc_by_archival_video_credits(project_dir_or_manifest: Path | str | dict[str, Any] | None) -> list[str]:
    """
    Extracts R89 `Video credit: Adapted from <Author> et al., <Journal> (<Year>), <Supp. Movie ID>, <CC BY> (<URI>) — cropped & muted (<Article URL>).`
    lines from `03_visuals/archival_videos_manifest.json` ONLY for entries classified as `"direct_insert_cc_by"`.
    Public Domain / CC0 entries emit zero credit lines and zero URLs.
    """
    if project_dir_or_manifest is None:
        return []
    doc: dict[str, Any] | None = None
    if isinstance(project_dir_or_manifest, dict):
        doc = project_dir_or_manifest
    else:
        p = Path(project_dir_or_manifest)
        mf_path: Path | None = None
        if p.is_file() or p.suffix.lower() == ".json":
            mf_path = p if p.is_file() else None
        else:
            for cand in (p / "03_visuals" / "archival_videos_manifest.json", p / "archival_videos_manifest.json"):
                if cand.is_file():
                    mf_path = cand
                    break
        if mf_path is not None:
            try:
                loaded = json.loads(mf_path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    doc = loaded
            except Exception:  # noqa: BLE001
                doc = None
    if not isinstance(doc, dict):
        return []

    from pipeline.archival_insert import normalize_cc_by_label
    from pipeline.real_world_refs import classify_media_license

    entries = doc.get("videos")
    if not isinstance(entries, list):
        for alt_key in ("inserts", "clips", "items"):
            if isinstance(doc.get(alt_key), list):
                entries = doc.get(alt_key)
                break
    if not isinstance(entries, list):
        return []

    credits: list[str] = []
    for item in entries:
        if not isinstance(item, dict):
            continue
        lic_raw = str(item.get("license") or item.get("license_short_name") or "").strip()
        if classify_media_license(lic_raw) != "direct_insert_cc_by":
            continue
        author = " ".join(str(item.get("author") or item.get("attribution") or "").split()).strip().rstrip(".")
        journal = " ".join(str(item.get("journal") or item.get("publisher") or "").split()).strip().rstrip(".")
        year = str(item.get("publication_year") or "").strip()
        movie_id = " ".join(str(item.get("supplementary_movie_id") or "").split()).strip().rstrip(",")
        lic_uri = " ".join(str(item.get("license_uri") or "https://creativecommons.org/licenses/by/4.0/").split()).strip()
        art_url = " ".join(str(item.get("article_url") or "").split()).strip()
        if not art_url:
            doi_val = " ".join(str(item.get("doi") or "").split()).strip()
            if doi_val:
                art_url = doi_val if doi_val.startswith("http") else f"https://doi.org/{doi_val}"
            else:
                art_url = " ".join(str(item.get("source_url") or "").split()).strip()
        if not (author and journal and year and movie_id and lic_uri and art_url):
            continue
        if "et al" not in author.lower():
            author = f"{author} et al."
        lic_label = normalize_cc_by_label(lic_raw)
        line = f"Video credit: Adapted from {author}, {journal} ({year}), {movie_id}, {lic_label} ({lic_uri}) — cropped & muted ({art_url})."
        if line not in credits:
            credits.append(line)
    return credits


def _normalize_r88a_credit_lines(archival_credits: list[str] | None) -> list[str]:
    cleaned: list[str] = []
    for cr in archival_credits or []:
        s = " ".join(str(cr or "").split()).strip()
        if not s:
            continue
        low = s.lower()
        if low.startswith("video credit:"):
            s = "Video credit: " + s[len("video credit:") :].strip()
        elif low.startswith("image credit:"):
            s = "Image credit: " + s[len("image credit:") :].strip()
        else:
            s = f"Image credit: {s}"
        if not s.endswith("."):
            s += "."
        if s not in cleaned:
            cleaned.append(s)
    return cleaned


def format_v8_viewer_story_description(
    script_doc: dict[str, Any] | None,
    dossier: Path | str | dict[str, Any] | None = None,
    *,
    omit_nicknames: list[str] | None = None,
    source_summary: str = "",
    archival_credits: list[str] | None = None,
) -> str:
    """
    R68-D Plain Viewer Story Description Builder (`55..135` words):
      - Renders `script_doc['viewer_description']` (preserving exact concrete plain paragraphs when clean)
        or synthesizes 2 concrete plain declarative paragraphs + 1 `Research: <Author>, <Institution> (<Year>).` line.
      - Optionally appends `Image credit:` (`R88-A`) / `Video credit:` (`R89`) line(s) right after `Research: ...`
        when `direct_insert_cc_by` archival assets are used.
      - Zero raw DOIs in story body, zero em-dashes (`—` / ` -- `), zero semicolons, zero bullets/subheaders,
        zero hashtags/Hangul, zero AI clichés (`R68D_BANNED_AI_CLICHES`), and zero in-body AI disclosure prose.
    """
    s_doc = script_doc if isinstance(script_doc, dict) else {}
    eff_omit = [
        str(x).strip()
        for x in (omit_nicknames if omit_nicknames is not None else (s_doc.get("omit_experiment_nicknames") or []))
        if str(x).strip()
    ]
    clean_credits = _normalize_r88a_credit_lines(archival_credits)

    raw_vd = str(s_doc.get("viewer_description") or "").strip()
    if raw_vd:
        raw_blocks: list[str] = []
        for blk in re.split(r"\n\s*\n", raw_vd):
            kept_lines = [
                ln.strip()
                for ln in blk.splitlines()
                if ln.strip()
                and not re.match(r"^\s*(?:[•\-\*]|\d+[\.\)])\s+", ln)
                and not ln.strip().lower().startswith(("image credit:", "video credit:"))
            ]
            if kept_lines:
                raw_blocks.append(" ".join(kept_lines))
        if raw_blocks and re.match(r"^research\s*:", raw_blocks[-1], flags=re.IGNORECASE):
            prose_raw = raw_blocks[:-1]
            res_body = re.sub(r"^research\s*:\s*", "", raw_blocks[-1], flags=re.IGNORECASE)
            res_clean = _sanitize_r68d_plain_text(res_body, allow_colon=False).rstrip(".")
            research_line = f"Research: {res_clean}." if res_clean else _build_r68d_research_line(s_doc, dossier, source_summary=source_summary)
        else:
            prose_raw = raw_blocks
            research_line = _build_r68d_research_line(s_doc, dossier, source_summary=source_summary)

        clean_paras: list[str] = []
        for p in prose_raw:
            cp = _sanitize_r68d_plain_text(p, allow_colon=False)
            if eff_omit:
                cp = _scrub_experiment_nicknames(cp, eff_omit)
            if cp:
                if cp[-1] not in ".!?":
                    cp += "."
                clean_paras.append(cp)

        if len(clean_paras) >= 3:
            clean_paras = [clean_paras[0], " ".join(clean_paras[1:])]
        elif len(clean_paras) == 1:
            sents_split = [x.strip() for x in re.split(r"(?<=[\.\!\?])\s+", clean_paras[0]) if x.strip()]
            if len(sents_split) >= 2:
                mid = max(1, len(sents_split) // 2)
                clean_paras = [" ".join(sents_split[:mid]), " ".join(sents_split[mid:])]
        if len(clean_paras) == 2:
            tail_block = "\n".join([research_line, *clean_credits]) if clean_credits else research_line
            return f"{clean_paras[0]}\n\n{clean_paras[1]}\n\n{tail_block}"

    # Fallback synthesis from dossier concrete facts and/or spoken sentences
    bundle = _load_dossier_bundle(dossier or s_doc.get("dossier") or s_doc.get("dossier_slug"))
    d_meta = bundle.get("dossier") if isinstance(bundle.get("dossier"), dict) else {}
    f_doc = bundle.get("facts") if isinstance(bundle.get("facts"), dict) else {}

    candidates: list[str] = []
    for item in list(d_meta.get("core_facts") or []) + list(f_doc.get("facts") or []):
        if isinstance(item, dict):
            raw_c = str(item.get("plain_claim") or item.get("fact") or item.get("claim") or item.get("summary") or "").strip()
            if raw_c:
                candidates.append(raw_c)

    if source_summary:
        ss_main = str(source_summary).split("Primary Peer-Reviewed Sources:")[0].strip()
        for piece in re.split(r"(?<=[\.\!\?])\s+", ss_main):
            if piece.strip():
                candidates.append(piece.strip())

    raw_sents = s_doc.get("sentences") if isinstance(s_doc.get("sentences"), list) else []
    for s in raw_sents:
        st = str(s or "").strip()
        if st and not st.endswith("?"):
            candidates.append(st)

    cleaned_pool: list[str] = []
    seen_low: set[str] = set()
    for cand in candidates:
        c = _sanitize_r68d_plain_text(cand, allow_colon=False)
        if eff_omit:
            c = _scrub_experiment_nicknames(c, eff_omit)
        c = c.rstrip("!?.").strip()
        if not c or len(c.split()) < 5:
            continue
        if c[0].islower():
            c = c[0].upper() + c[1:]
        c = f"{c}."
        low_key = c.lower()
        if low_key not in seen_low and not any(tok.lower() in low_key for tok in R68D_BANNED_AI_CLICHES):
            seen_low.add(low_key)
            cleaned_pool.append(c)

    fallback_fillers = [
        "Researchers tracked how the brain responded in real time across controlled laboratory trials.",
        "Instead of a single conscious choice, deep neural pathways adjusted the body's reaction automatically within fractions of a second.",
        "The experiment showed that physical brain wiring shapes everyday perception long before conscious awareness catches up.",
    ]
    for fl in fallback_fillers:
        if fl.lower() not in seen_low:
            cleaned_pool.append(fl)

    research_line = _build_r68d_research_line(s_doc, bundle or dossier, source_summary=source_summary)
    res_words = len(research_line.split())
    lo_w, hi_w = R68D_DESCRIPTION_WORD_RANGE
    target_prose_min = max(48, lo_w - res_words + 4)
    target_prose_max = max(target_prose_min + 10, hi_w - res_words - 3)

    picked: list[str] = []
    running_w = 0
    for sent in cleaned_pool:
        sw = len(sent.split())
        if running_w + sw > target_prose_max and len(picked) >= 2 and running_w >= target_prose_min:
            break
        if running_w + sw <= target_prose_max:
            picked.append(sent)
            running_w += sw
        if running_w >= 78 and len(picked) >= 3:
            break

    if len(picked) < 2:
        picked = cleaned_pool[:2]

    mid = max(1, len(picked) // 2)
    para_1 = " ".join(picked[:mid]).strip()
    para_2 = " ".join(picked[mid:]).strip()
    tail_block = "\n".join([research_line, *clean_credits]) if clean_credits else research_line
    return f"{para_1}\n\n{para_2}\n\n{tail_block}"


def validate_v8_viewer_description(desc: str, *, project_id: str = "") -> list[str]:
    """
    Validates Rule R68-D Zero-AI-Smell Plain Story Description on non-frozen Schema v8 episodes:
      - `55..135` words (`R68D_DESCRIPTION_WORD_RANGE`) across the 2 story paragraphs + `Research:` block
      - 2 plain concrete declarative paragraphs + 1 closing `Research: ...` line (`3` blocks total),
        plus optional trailing `Image credit: <Author>, <License Label> (<URI>).` line(s) (`R88-A`)
      - Zero DOI URLs (`https://doi.org/...`) or raw DOI strings (`10.xxxx/...`)
      - Zero em-dashes (`—`, ` -- `), semicolons (`;`), bullets, or colon subheaders
      - Zero `R68D_BANNED_AI_CLICHES`, hashtags (`#`), or Hangul characters
    """
    if project_id and str(project_id) in PRE_R68H_FROZEN_V8_PROJECTS:
        return []

    raw = str(desc or "")
    clean = raw.strip()
    if not clean:
        return ["[r68d_description] empty viewer description (R68-D)"]

    issues: list[str] = []
    hash_tokens = re.findall(r"#\S+", clean)
    has_trailing_shorts = bool(
        len(hash_tokens) == 1
        and hash_tokens[0].lower() == "#shorts"
        and re.search(r"(?:\n\s*\n|\s+)#shorts\s*$", clean, flags=re.IGNORECASE)
    )
    if len(hash_tokens) > R68_DESCRIPTION_HASHTAG_MAX or (hash_tokens and not has_trailing_shorts):
        issues.append(
            "[r68d_description] hashtags ('#') other than a single trailing '#shorts' forbidden in R68-D YouTube description"
        )

    body_for_structure = (
        re.sub(r"\s*#shorts\s*$", "", clean, flags=re.IGNORECASE).strip()
        if has_trailing_shorts
        else clean
    )

    blocks = [b.strip() for b in re.split(r"\n\s*\n", body_for_structure) if b.strip()]
    trailing_credits: list[str] = []
    while len(blocks) > 3:
        blk_lines = [ln.strip() for ln in blocks[-1].splitlines() if ln.strip()]
        if blk_lines and all(ln.lower().startswith(("image credit:", "video credit:")) for ln in blk_lines):
            trailing_credits = blk_lines + trailing_credits
            blocks.pop()
        else:
            break

    credit_lines: list[str] = []
    core_blocks = list(blocks)
    if core_blocks:
        last_lines = [ln.strip() for ln in core_blocks[-1].splitlines() if ln.strip()]
        if (
            len(last_lines) >= 2
            and last_lines[0].startswith("Research: ")
            and all(ln.lower().startswith(("image credit:", "video credit:")) for ln in last_lines[1:])
        ):
            credit_lines = last_lines[1:] + trailing_credits
            core_blocks[-1] = last_lines[0]
        else:
            credit_lines = trailing_credits
    else:
        credit_lines = trailing_credits

    core_text = "\n\n".join(core_blocks) if core_blocks else body_for_structure
    words = [w for w in core_text.split() if w.strip()]
    lo_w, hi_w = R68D_DESCRIPTION_WORD_RANGE
    if not (lo_w <= len(words) <= hi_w):
        issues.append(f"[r68d_description] word count {len(words)} outside {lo_w}..{hi_w} words (R68-D)")

    if _R68D_DOI_URL_RE.search(core_text) or _R68D_DOI_RAW_RE.search(core_text):
        issues.append("[r68d_description] raw DOI link or identifier forbidden in viewer description (R68-D)")

    raw_low = core_text.lower()
    hit_cliches = [tok for tok in R68D_BANNED_AI_CLICHES if tok.lower() in raw_low]
    if hit_cliches:
        issues.append(f"[r68d_description] banned AI cliché or punctuation found: {hit_cliches} (R68-D)")

    if ";" in body_for_structure:
        issues.append("[r68d_description] semicolons (';') forbidden in plain viewer description (R68-D)")

    for ln in body_for_structure.splitlines():
        if re.match(r"^\s*(?:[•\-\*]|\d+[\.\)])\s+", ln):
            issues.append(f"[r68d_description] bullet or numbered list line forbidden: {ln.strip()[:50]!r} (R68-D)")
            break

    if len(core_blocks) != 3:
        issues.append(
            f"[r68d_description] description must have exactly 3 blocks (2 plain paragraphs + 1 'Research:' line), got {len(core_blocks)} (R68-D)"
        )
    if core_blocks:
        last_blk = core_blocks[-1]
        if not last_blk.startswith("Research: ") or "\n" in last_blk or not last_blk.endswith("."):
            issues.append(
                "[r68d_description] closing block must be a single line formatted as 'Research: <Author> et al., <Institution> (<Year>).' (R68-D)"
            )
        prose_blocks = core_blocks[:-1] if last_blk.startswith("Research:") else core_blocks
        for idx, pb in enumerate(prose_blocks, start=1):
            if "\n" in pb:
                issues.append(f"[r68d_description] paragraph {idx} contains single-newline line break / subheader (R68-D)")
            without_clock = re.sub(r"\b\d{1,2}:\d{2}\b", "", pb)
            if ":" in without_clock:
                issues.append(f"[r68d_description] colon subheader or label forbidden in paragraph {idx} (R68-D)")

    non_emdash_cliches = [tok for tok in R68D_BANNED_AI_CLICHES if tok != "—"]
    for cl in credit_lines:
        cl_low = cl.lower()
        if cl_low.startswith("video credit:"):
            if any(tok.lower() in cl_low for tok in non_emdash_cliches) or not _R89_VIDEO_CREDIT_LINE_RE.match(cl):
                issues.append(
                    f"[r89_video_credit] invalid trailing video credit line {cl!r}; expected "
                    "'Video credit: Adapted from <Lead Author> et al., <Journal> (<Year>), <Supp. Movie ID>, CC BY 4.0 (<URI>) — cropped & muted (<Article URL>).' (R89)"
                )
        elif any(tok.lower() in cl_low for tok in R68D_BANNED_AI_CLICHES) or not _R88A_CREDIT_LINE_RE.match(cl):
            issues.append(
                f"[r88a_image_credit] invalid trailing credit line {cl!r}; expected 'Image credit: <Author>, <License Label> (<URI>).' (R88-A)"
            )

    if _R68D_HANGUL_RE.search(clean):
        issues.append("[r68d_description] Hangul characters forbidden in English viewer description (R36/R68-D)")

    return issues


def render_editorial_description(
    *,
    title: str,
    doi_or_url: str,
    source_summary: str,
    hashtags: list[str],
    companion_block: str = "",
    template_id: str | None = None,
    seed: int = 0,
    zero_hashtags: bool = False,
    omit_nicknames: list[str] | None = None,
) -> str:
    """Renders one of the 4 rotating US editorial description layouts while preserving R4/R9/R10/R68 markers."""
    from pipeline.config import AI_DISCLOSURE_SENTENCE, DESCRIPTION_EDITORIAL_TEMPLATES

    clean_title = strip_internal_pipeline_tokens(title)
    clean_summary = _scrub_experiment_nicknames(strip_internal_pipeline_tokens(source_summary), omit_nicknames) or clean_title
    if zero_hashtags:
        clean_title = re.sub(r"#\w+", "", clean_title).strip()
        clean_summary = re.sub(r"#\w+", "", clean_summary).strip()
    raw_doi = str(doi_or_url or "").strip()
    doi_url = raw_doi if raw_doi.startswith("http") else (f"https://doi.org/{raw_doi}" if raw_doi else "")
    if zero_hashtags or (hashtags is not None and len(hashtags) == 0):
        tags_block = ""
    else:
        tags = " ".join(
            t if str(t).startswith("#") else f"#{t}"
            for t in (hashtags or ["#Shorts", "#Neuroscience", "#BrainScience", "#Psychology"])[:5]
            if str(t).strip()
        )
        tags_block = f"{tags}\n\n" if tags else ""
    chosen = (
        template_id
        if template_id in DESCRIPTION_EDITORIAL_TEMPLATES
        else DESCRIPTION_EDITORIAL_TEMPLATES[int(seed) % len(DESCRIPTION_EDITORIAL_TEMPLATES)]
    )
    comp_raw = re.sub(r"#\w+", "", str(companion_block or "")) if zero_hashtags else str(companion_block or "")
    comp = f"{comp_raw.strip()}\n\n" if comp_raw.strip() else ""
    if chosen == "clinical_brief":
        lead = f"{clean_title}\n\nClinical Case Note — {clean_summary}"
        outro = "ALL ABOUT BRAIN documents peer-reviewed clinical neurology and human brain circuits."
    elif chosen == "experiment_chronicle":
        lead = f"{clean_title}\n\nInside the Study — {clean_summary}"
        outro = "ALL ABOUT BRAIN reconstructs landmark psychology and neuroscience experiments from primary papers."
    elif chosen == "myth_vs_mechanism":
        lead = f"{clean_title}\n\nWhat the Brain Data Actually Shows — {clean_summary}"
        outro = "ALL ABOUT BRAIN separates everyday myths from measured human neurobiology."
    else:
        lead = f"{clean_title}\n\nEveryday Neurobiology — {clean_summary}"
        outro = "ALL ABOUT BRAIN translates peer-reviewed brain and BCI science into clear visual stories."

    return (
        f"{lead}\n\n"
        f"Source & Verification: {doi_url or raw_doi}\n\n"
        f"{comp}"
        f"AI Disclosure: {AI_DISCLOSURE_SENTENCE}\n\n"
        f"{tags_block}"
        f"{outro}"
    ).strip()


class PublishStage:
    def __init__(self, storage: ProjectStorage):
        self.storage = storage

    def _load_base_frame(self, base_asset_path: Path | None, variant: str = "A") -> Image.Image:
        """
        Loads a distinct representative frame per variant:
        - Variant A (Baseline Authority): Clip 1 (Hook scene, ratio=0.30)
        - Variant B (Macro 3D Cutaway): Clip 3/4 (3D Brain Cutaway scene, ratio=0.55)
        - Variant C (Defiance Red Climax): Clip 5/Last (Telemetry HUD climax scene, ratio=0.70)
        Guarantees visual frame diversity (A_vs_B_bg_diff >= 15.0) across A, B, and C.
        """
        import cv2
        import numpy as np

        def _extract_video_frame(video_path: Path, pos_ratio: float = 0.35) -> Image.Image | None:
            try:
                cap = cv2.VideoCapture(str(video_path))
                if not cap.isOpened():
                    cap.release()
                    return None
                total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
                if total > 5:
                    target_idx = max(1, min(total - 2, int(total * pos_ratio)))
                    cap.set(cv2.CAP_PROP_POS_FRAMES, target_idx)
                ret, frame = cap.read()
                cap.release()
                if ret and frame is not None:
                    img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                    return ImageOps.fit(img, (VIDEO_WIDTH, VIDEO_HEIGHT), method=Image.Resampling.LANCZOS)
            except Exception as e:
                print(f"[PublishStage] Warning: Failed to extract frame from video ({e})")
            return None

        def _roi_diff(img1: Image.Image, img2: Image.Image) -> float:
            arr1 = np.asarray(img1, dtype=np.float32)
            arr2 = np.asarray(img2, dtype=np.float32)
            h = arr1.shape[0]
            y0, y1 = int(h * 0.32), int(h * 0.68)
            return float(np.mean(np.abs(arr1[y0:y1] - arr2[y0:y1])))

        v_upper = (variant or "A").upper()
        default_ratio = 0.30 if v_upper == "A" else (0.55 if v_upper == "B" else 0.75)

        # 1. Try provided explicit asset path
        if base_asset_path:
            base_asset_path = Path(base_asset_path)
        if base_asset_path and base_asset_path.exists():
            suffix = base_asset_path.suffix.lower()
            if suffix in [".mp4", ".mov", ".mkv", ".webm", ".avi"]:
                vid_img = _extract_video_frame(base_asset_path, pos_ratio=default_ratio)
                if vid_img is not None:
                    return vid_img
            else:
                try:
                    img = Image.open(base_asset_path).convert("RGB")
                    return ImageOps.fit(img, (VIDEO_WIDTH, VIDEO_HEIGHT), method=Image.Resampling.LANCZOS)
                except Exception as e:
                    print(f"[PublishStage] Warning: Failed to load image asset ({e})")

        # 2. Check 03_visuals/flow_native_clips/*.mp4 and _staged_clip_*.mp4 with distinct clip selection per variant
        vis_dir = self.storage.get_stage_dir("03_visuals")
        flow_clips_dir = vis_dir / "flow_native_clips"
        valid_clips: list[Path] = []
        if flow_clips_dir.exists():
            valid_clips = [
                c for c in sorted(flow_clips_dir.glob("*.mp4"), key=numeric_clip_sort_key)
                if c.is_file() and c.stat().st_size >= 1_000_000
            ]
        if not valid_clips and vis_dir.exists():
            valid_clips = [
                c for c in sorted(vis_dir.glob("_staged_clip_*.mp4"), key=numeric_clip_sort_key)
                if c.is_file() and c.stat().st_size >= 1_000_000
            ]
        if valid_clips:
            n_clips = len(valid_clips)
            ref_a = _extract_video_frame(valid_clips[0], pos_ratio=0.30)
            if v_upper == "A" and ref_a is not None:
                return ref_a

            mid_idx = min(n_clips - 1, n_clips // 2)
            mid_next_idx = min(n_clips - 1, max(mid_idx, int(n_clips * 0.60)))
            climax_idx = min(n_clips - 1, max(0, int(n_clips * 0.85)))
            last_idx = n_clips - 1
            act2_idx = min(n_clips - 1, max(1 if n_clips > 1 else 0, int(n_clips * 0.25)))

            if v_upper == "B":
                pref_indices = list(dict.fromkeys([mid_idx, mid_next_idx, act2_idx, climax_idx, last_idx]))
                ratios = [0.55, 0.75, 0.25]
            else:  # Variant C
                pref_indices = list(dict.fromkeys([climax_idx, last_idx, mid_next_idx, mid_idx, act2_idx]))
                ratios = [0.70, 0.45, 0.85]

            best_img: Image.Image | None = None
            best_diff = -1.0
            for c_idx in pref_indices:
                for r in ratios:
                    cand_img = _extract_video_frame(valid_clips[c_idx], pos_ratio=r)
                    if cand_img is not None:
                        if ref_a is None:
                            return cand_img
                        d = _roi_diff(ref_a, cand_img)
                        if d > best_diff:
                            best_diff = d
                            best_img = cand_img
                        if d >= 18.0:
                            return cand_img
            if best_img is not None:
                return best_img

        # 3. Check assembled final video in 05_assembly at variant-specific timestamps
        final_video = self.storage.get_stage_dir("05_assembly") / "final_shorts_1080x1920.mp4"
        if final_video.exists() and final_video.stat().st_size >= 1_000_000:
            timeline_ratio = 0.10 if v_upper == "A" else (0.50 if v_upper == "B" else 0.82)
            vid_img = _extract_video_frame(final_video, pos_ratio=timeline_ratio)
            if vid_img is not None:
                return vid_img

        # 4. Check 03_visuals raw_assets
        for candidate in ["clip_1_base.png", "clip_1.mp4", "master_keyframe.png"]:
            cand_path = self.storage.get_stage_dir("03_visuals") / "raw_assets" / candidate
            if cand_path.exists():
                return self._load_base_frame(cand_path, variant=v_upper)

        # 5. Fallback to variant-distinct canvas (only when no video/image assets exist yet during pre-flow ideation)
        fallback_color = RGB_DEEP_NAVY if v_upper == "A" else ((14, 38, 68) if v_upper == "B" else (32, 14, 28))
        return Image.new("RGB", (VIDEO_WIDTH, VIDEO_HEIGHT), fallback_color)

    def _resolve_thumbnail_font(self) -> tuple[Path, str]:
        """Selects bundled condensed black font for Schema v7/v8 / Neuro-Diorama parity, falling back to primary."""
        vp_data = self.storage.load_json("03_visuals", "visual_plan.json") or {}
        scr_data = self.storage.load_json("02_script", "script.json") or {}
        use_condensed = (
            is_expressive_v8_plan(vp_data, scr_data)
            or is_diorama_v7_plan(vp_data)
            or is_diorama_v7_plan(scr_data)
            or is_diorama_profile(vp_data)
            or is_diorama_profile(scr_data)
        )
        if use_condensed and FONT_CONDENSED_BLACK_PATH.exists():
            return FONT_CONDENSED_BLACK_PATH, "AABCondensed-Black"
        if FONT_PRIMARY_PATH.exists():
            return FONT_PRIMARY_PATH, "Inter-Variable"
        return FONT_FALLBACK_PATH, "Inter-Variable"

    def _get_scaled_font(self, text_lines: list[str], max_w: int, start_size: int = 64, min_size: int = 32) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        """Finds largest font size where all lines fit within max_w."""
        font_path, _ = self._resolve_thumbnail_font()
        for size in range(start_size, min_size - 1, -4):
            try:
                font = ImageFont.truetype(str(font_path), size)
            except (OSError, ValueError):
                return ImageFont.load_default()

            fits = True
            for line in text_lines:
                if not line:
                    continue
                bbox = font.getbbox(line)
                w = bbox[2] - bbox[0]
                if w > max_w:
                    fits = False
                    break
            if fits:
                return font
        try:
            return ImageFont.truetype(str(font_path), min_size)
        except Exception:
            return ImageFont.load_default()

    @staticmethod
    def _extract_short_authority_hook(title: str) -> tuple[str, str]:
        """Extracts a bold 2-4 word authority hook split into 1-2 lines for maximum mobile Shelf CTR."""
        clean = re.sub(r"[^\w\s\-\?\!]", "", title).strip()
        stop = {
            "why", "how", "what", "when", "where", "the", "a", "an", "in", "to", "of", "and",
            "is", "are", "was", "were", "for", "with", "from", "that", "this", "their", "your",
            "his", "her", "into", "got", "has", "had", "have", "can", "could", "would", "people"
        }
        words = clean.split()
        if not words:
            return ("BRAIN", "PARADOX")
        core = [w.upper() for w in words if w.lower().strip("?-!") not in stop]
        if len(core) < 2:
            core = [w.upper() for w in words[:4]]
        selected = core[:4]
        if len(selected) <= 2:
            return (selected[0], selected[1] if len(selected) > 1 else "")
        mid = 2 if len(selected) >= 3 else 1
        return (" ".join(selected[:mid]), " ".join(selected[mid:4]))

    @staticmethod
    def _draw_neural_hud_reticle(
        draw: ImageDraw.ImageDraw,
        center_x: int,
        center_y: int,
        radius: int,
        color: tuple[int, int, int, int],
        label: str | None = None,
        font: ImageFont.FreeTypeFont | ImageFont.ImageFont | None = None,
    ) -> None:
        """No-op stub retained for API compatibility (R14-C sci-fi HUD reticles permanently removed)."""
        return None

    def generate_thumbnail_variant_a(self, base_asset_path: Path | None, title_headline: str, output_path: Path):
        """
        Variant A (Baseline Authority): Top Safe-Zone Deep Navy Badge + Gold Border + Giant 2-4 Word Hook (96px).
        Target: Viewers responding to authoritative scientific/documentary gravitas without bottom Shorts Shelf UI overlap.
        """
        img = self._load_base_frame(base_asset_path, variant="A")
        rgba_img = img.convert("RGBA")
        overlay = Image.new("RGBA", rgba_img.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        line1, line2 = self._extract_short_authority_hook(title_headline)
        max_text_w = VIDEO_WIDTH - 160
        chosen_font = self._get_scaled_font([line1, line2], max_text_w, start_size=96, min_size=52)

        # Top Safe-Zone Headline Badge (y=260..475, safely inside 9:16 and 3:4 YouTube Shorts grid crop)
        badge_y = 260
        badge_h = 215 if line2 else 135
        badge_left = 72
        badge_right = VIDEO_WIDTH - 72

        draw.rectangle(
            [(badge_left, badge_y), (badge_right, badge_y + badge_h)],
            fill=(*RGB_DEEP_NAVY, 232), outline=(*RGB_SIGNAL_GOLD, 255), width=6
        )

        def draw_centered_text(text: str, y: int, color: tuple[int, int, int]):
            bbox = chosen_font.getbbox(text)
            tw = bbox[2] - bbox[0]
            tx = (VIDEO_WIDTH - tw) // 2
            draw.text((tx + 4, y + 4), text, fill=(0, 0, 0, 255), font=chosen_font)
            draw.text((tx, y), text, fill=(*color, 255), font=chosen_font)

        if line2:
            draw_centered_text(line1, badge_y + 20, RGB_NEUTRAL_WHITE)
            draw_centered_text(line2, badge_y + 112, RGB_SIGNAL_GOLD)
        else:
            draw_centered_text(line1, badge_y + 32, RGB_SIGNAL_GOLD)

        combined = Image.alpha_composite(rgba_img, overlay).convert("RGB")
        combined.save(output_path, "PNG")

    def generate_thumbnail_variant_b(self, base_asset_path: Path | None, title_headline: str, output_path: Path):
        """
        Variant B (Macro 3D Cutaway): Top Safe-Zone Minimal 2-Word Hook (108px) leaving center documentary scene clean.
        Target: Visual awe & documentary render detail; zero overlap with bottom Shorts Shelf title/views zone.
        """
        img = self._load_base_frame(base_asset_path, variant="B")
        rgba_img = img.convert("RGBA")
        overlay = Image.new("RGBA", rgba_img.size, (0, 0, 0, 0))
        draw_ov = ImageDraw.Draw(overlay)

        # Extract 2 punchy keywords for ultra-clean macro header
        clean_headline = re.sub(r"[^\w\s]", "", title_headline).strip()
        stop_words = {
            "why", "how", "what", "the", "a", "an", "in", "to", "of", "and", "is", "are",
            "for", "with", "from", "your", "their", "that", "this", "has", "got", "one", "people"
        }
        meaningful_words = [w.upper() for w in clean_headline.split() if w.lower() not in stop_words]
        if not meaningful_words:
            meaningful_words = ["BRAIN", "UNLOCKED"]
        short_headline = " ".join(meaningful_words[:2])

        max_text_w = VIDEO_WIDTH - 160
        chosen_font = self._get_scaled_font([short_headline], max_text_w, start_size=108, min_size=56)

        # Top Safe-Zone position (y=270..418) leaving the entire center & bottom 3D anatomy unobstructed
        badge_y = 270
        badge_h = 148
        badge_left = 72
        badge_right = VIDEO_WIDTH - 72

        draw_ov.rectangle(
            [(badge_left, badge_y), (badge_right, badge_y + badge_h)],
            fill=(10, 17, 40, 215), outline=(*RGB_SECONDARY_TEAL, 255), width=5
        )

        bbox = chosen_font.getbbox(short_headline)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        tx = (VIDEO_WIDTH - tw) // 2
        ty = badge_y + (badge_h - th) // 2 - 8

        draw_ov.text((tx + 4, ty + 4), short_headline, fill=(0, 0, 0, 255), font=chosen_font)
        draw_ov.text((tx, ty), short_headline, fill=(*RGB_NEUTRAL_WHITE, 255), font=chosen_font)

        combined = Image.alpha_composite(rgba_img, overlay).convert("RGB")
        combined.save(output_path, "PNG")

    @staticmethod
    def _format_provocative_question(title: str, candidate_hook: str | None = None) -> str:
        """Formats a crisp, punchy 2-4 word question hook for mobile Shorts thumbnail impact."""
        if candidate_hook and len(candidate_hook.split()) <= 5 and "?" in candidate_hook:
            return candidate_hook.strip().upper()
        clean = re.sub(r"[^\w\s\?]", "", title).strip()
        words = clean.split()
        if not words:
            return "IMPOSSIBLE BRAIN?"
        if clean.lower().startswith("why "):
            sub_words = [w for w in words[1:] if w.lower() not in {"ancient", "modern", "the", "a", "an", "in", "to", "of", "and", "is", "are", "they"}]
            if len(sub_words) >= 2:
                return f"WHY {sub_words[-2].upper()} {sub_words[-1].upper()}?"
            return f"WHY {' '.join(words[1:4]).upper()}?"
        if "?" in clean:
            return clean.upper() if len(words) <= 4 else " ".join(words[:4]).upper() + "?"
        stop = {"the", "a", "an", "in", "to", "of", "and", "is", "are", "with", "your", "their", "that", "this", "has", "got"}
        core = [w.upper() for w in words if w.lower() not in stop]
        if len(core) >= 3:
            return f"{' '.join(core[:3])}?"
        return f"{' '.join(words[:3]).upper()}?"

    def generate_thumbnail_variant_c(self, base_asset_path: Path | None, title_headline: str, output_path: Path, question_hook: str | None = None):
        """
        Variant C (Defiance Red): Warning Red Border + Giant 2-4 Word Question Hook (96px) + Danger Red Anomaly HUD Reticle.
        Target: Cognitive dissonance & curiosity gap; defiance trigger.
        """
        img = self._load_base_frame(base_asset_path, variant="C")
        rgba_img = img.convert("RGBA")
        overlay = Image.new("RGBA", rgba_img.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        # Full-frame warning red border (high urgency)
        border_inset = 12
        border_width = 8
        draw.rectangle(
            [(border_inset, border_inset), (VIDEO_WIDTH - border_inset, VIDEO_HEIGHT - border_inset)],
            outline=(*RGB_DANGER_RED, 255), width=border_width
        )

        # Formulate crisp provocative question (2-4 words)
        q_clean = self._format_provocative_question(title_headline, question_hook)
        words = q_clean.split()
        mid = max(1, len(words) // 2)
        line1 = " ".join(words[:mid])
        line2 = " ".join(words[mid:]) if len(words) > 1 else ""

        max_text_w = VIDEO_WIDTH - 160
        chosen_font = self._get_scaled_font([line1, line2], max_text_w, start_size=96, min_size=52)

        # Top pill tag: "CRITICAL PARADOX" in safe zone
        pill_font_path, _ = self._resolve_thumbnail_font()
        try:
            pill_font = ImageFont.truetype(str(pill_font_path), 24)
        except Exception:
            pill_font = ImageFont.load_default()

        pill_text = "CRITICAL PARADOX"
        p_bbox = pill_font.getbbox(pill_text)
        p_w = p_bbox[2] - p_bbox[0]
        p_left = (VIDEO_WIDTH - p_w) // 2 - 22
        p_right = p_left + p_w + 44
        pill_y = 235
        draw.rectangle(
            [(p_left, pill_y), (p_right, pill_y + 40)],
            fill=(*RGB_DANGER_RED, 255), outline=(*RGB_NEUTRAL_WHITE, 255), width=2
        )
        draw.text((p_left + 22, pill_y + 7), pill_text, fill=(*RGB_NEUTRAL_WHITE, 255), font=pill_font)

        # Main badge box at top safe-zone (y=282..497)
        badge_y = 282
        badge_h = 215 if line2 else 135
        badge_left = 72
        badge_right = VIDEO_WIDTH - 72

        draw.rectangle(
            [(badge_left, badge_y), (badge_right, badge_y + badge_h)],
            fill=(*RGB_DEEP_NAVY, 232), outline=(*RGB_DANGER_RED, 255), width=6
        )

        def draw_centered_text(text: str, y: int, color: tuple[int, int, int]):
            bbox = chosen_font.getbbox(text)
            tw = bbox[2] - bbox[0]
            tx = (VIDEO_WIDTH - tw) // 2
            draw.text((tx + 4, y + 4), text, fill=(0, 0, 0, 255), font=chosen_font)
            draw.text((tx, y), text, fill=(*color, 255), font=chosen_font)

        if line2:
            draw_centered_text(line1, badge_y + 20, RGB_NEUTRAL_WHITE)
            draw_centered_text(line2, badge_y + 112, RGB_DANGER_RED)
        else:
            draw_centered_text(line1, badge_y + 32, RGB_DANGER_RED)

        combined = Image.alpha_composite(rgba_img, overlay).convert("RGB")
        combined.save(output_path, "PNG")


    def generate_thumbnail(self, base_asset_path: Path, title_headline: str, output_path: Path):
        """Backward-compatible entry point that defaults to Variant A."""
        self.generate_thumbnail_variant_a(base_asset_path, title_headline, output_path)

    def generate_all_thumbnail_variants(
        self,
        base_asset_path: Path | None,
        title_headline: str,
        output_dir: Path,
        question_hook: str | None = None
    ) -> dict[str, Path]:
        """Generates all 3 A/B test thumbnail variants and standard thumbnail.png."""
        output_dir.mkdir(parents=True, exist_ok=True)
        var_a_path = output_dir / "thumbnail_var_A.png"
        var_b_path = output_dir / "thumbnail_var_B.png"
        var_c_path = output_dir / "thumbnail_var_C.png"
        default_thumb_path = output_dir / "thumbnail.png"

        vp_data = self.storage.load_json("03_visuals", "visual_plan.json") or {}
        scr_data = self.storage.load_json("02_script", "script.json") or {}
        if is_diorama_profile(vp_data) or is_diorama_profile(scr_data):
            p_dir = self.storage.project_dir
            edl_exists = (p_dir / "05_assembly" / "edit_decision_list.json").exists()
            clips_exist = any((p_dir / "03_visuals" / "flow_native_clips").glob("*.mp4")) if (p_dir / "03_visuals" / "flow_native_clips").exists() else False
            mp4_exists = (p_dir / "05_assembly" / "final_shorts_1080x1920.mp4").exists()
            if edl_exists or clips_exist or mp4_exists:
                from pipeline import thumbnail as thumbnail_studio

                thumbnail_studio.run(p_dir, force=True, strict=False)
                return {
                    "A": var_a_path,
                    "B": var_b_path,
                    "C": var_c_path,
                    "default": default_thumb_path,
                }

        self.generate_thumbnail_variant_a(base_asset_path, title_headline, var_a_path)
        self.generate_thumbnail_variant_b(base_asset_path, title_headline, var_b_path)
        self.generate_thumbnail_variant_c(base_asset_path, title_headline, var_c_path, question_hook=question_hook)

        # Standard thumbnail.png is set to Variant A by default
        shutil.copy2(var_a_path, default_thumb_path)

        return {
            "A": var_a_path,
            "B": var_b_path,
            "C": var_c_path,
            "default": default_thumb_path
        }

    def run(
        self,
        title: str,
        hashtags: list[str],
        doi: str,
        source_summary: str,
        thumbnail_source_img: Path | None = None,
        related_short: dict[str, str] | None = None,
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        self.storage.update_stage_status("06_publish", "running")

        publish_dir = self.storage.get_stage_dir("06_publish")
        thumb_path = publish_dir / "thumbnail.png"

        # Validate title length (<= 60 chars for classic_v5; <= 55 chars for R68 expressive_25d_v8; <= 95 for R60)
        vp_data = self.storage.load_json("03_visuals", "visual_plan.json") or {}
        scr_data = self.storage.load_json("02_script", "script.json") or {}
        is_v8 = is_expressive_v8_plan(vp_data, scr_data)
        is_diorama = is_v8 or is_diorama_profile(vp_data) or is_diorama_profile(scr_data)
        is_v7 = is_diorama_v7_plan(vp_data) or is_diorama_v7_plan(scr_data)
        resolved_profile = str(
            vp_data.get("profile")
            or scr_data.get("profile")
            or ("neuro_diorama" if is_diorama else "classic_v5")
        )
        from pipeline.config import resolve_diorama_v7_style_profile

        resolved_style_profile = str(
            vp_data.get("style_profile")
            or scr_data.get("style_profile")
            or (EXPRESSIVE_25D_V8_STYLE_PROFILE if is_v8 else (resolve_diorama_v7_style_profile(vp_data) if is_v7 else ""))
        )
        _, resolved_font_label = self._resolve_thumbnail_font()
        max_title_len = R68_TITLE_MAX_CHARS if is_v8 else (TITLE_MAX_CHARS_DIORAMA if is_diorama else 60)
        clean_title = strip_internal_pipeline_tokens(title).strip()
        if is_v8:
            clean_title = re.sub(r"#\w+", "", clean_title).strip()
        if len(clean_title) > max_title_len:
            clean_title = clean_title[: max_title_len - 3].rstrip() + "..."

        raw_doi = (doi or "").strip()
        doi_url = (
            raw_doi
            if raw_doi.startswith("http")
            else (f"https://doi.org/{raw_doi}" if raw_doi else "")
        )

        companion_block = ""
        if isinstance(related_short, dict) and related_short.get("title"):
            comp_vid = str(related_short.get("video_id") or "").strip()
            comp_url = (
                related_short.get("shorts_url")
                or related_short.get("url")
                or (f"https://www.youtube.com/shorts/{comp_vid}" if comp_vid else "")
            )
            companion_block = (
                f"Companion Case: {related_short['title']}"
                + (f" — {comp_url}\n\n" if comp_url else "\n\n")
            )

        desc_seed = sum(ord(ch) for ch in str(self.storage.project_id or clean_title))
        desc_template = (
            vp_data.get("description_template")
            or scr_data.get("description_template")
        )
        manifest_data = self.storage.load_json("", "00_project_manifest.json") or {}
        if not manifest_data and (self.storage.project_dir / "00_project_manifest.json").exists():
            try:
                manifest_data = json.loads((self.storage.project_dir / "00_project_manifest.json").read_text(encoding="utf-8"))
            except Exception:
                manifest_data = {}
        eff_pillar = str(
            scr_data.get("pillar")
            or vp_data.get("pillar")
            or manifest_data.get("pillar")
            or DEFAULT_FALLBACK_PILLAR
        ).strip() or DEFAULT_FALLBACK_PILLAR

        is_frozen_v8 = bool(is_v8 and str(self.storage.project_id or "") in PRE_R68H_FROZEN_V8_PROJECTS)
        eff_hashtags: list[str] = (
            ([] if is_frozen_v8 else ["#shorts"])
            if is_v8
            else list((hashtags or ["#shorts"])[:5])
        )
        omit_nicknames = [
            str(x).strip()
            for x in (scr_data.get("omit_experiment_nicknames") or vp_data.get("omit_experiment_nicknames") or [])
            if str(x).strip()
        ]

        if is_v8 and not is_frozen_v8:
            archival_credits = (
                extract_cc_by_archival_credits(
                    self.storage.project_dir / "03_visuals" / "archival_inserts_manifest.json"
                )
                + extract_cc_by_archival_video_credits(
                    self.storage.project_dir / "03_visuals" / "archival_videos_manifest.json"
                )
            )
            base_v8_desc = format_v8_viewer_story_description(
                scr_data,
                dossier=scr_data.get("dossier") or scr_data.get("dossier_slug") or vp_data.get("dossier"),
                omit_nicknames=omit_nicknames,
                source_summary=source_summary,
                archival_credits=archival_credits or None,
            )
            resolved_description = (
                base_v8_desc
                if base_v8_desc.lower().rstrip().endswith("#shorts")
                else f"{base_v8_desc.rstrip()}\n\n#shorts"
            )
        else:
            resolved_description = render_editorial_description(
                title=clean_title,
                doi_or_url=doi_url or raw_doi,
                source_summary=source_summary,
                hashtags=eff_hashtags,
                companion_block=companion_block,
                template_id=str(desc_template) if desc_template else None,
                seed=desc_seed,
                zero_hashtags=is_v8,
                omit_nicknames=omit_nicknames if is_v8 else None,
            )

        if tags is not None:
            resolved_tags = validate_episode_tags_hygiene(tags, pillar=eff_pillar, raise_on_error=True)
        else:
            resolved_tags = build_clean_episode_tags(
                pillar=eff_pillar,
                script_doc=scr_data,
                dossier=scr_data.get("dossier") or scr_data.get("dossier_slug") or vp_data.get("dossier"),
                title=clean_title,
                everyday_domain=str(scr_data.get("everyday_domain") or vp_data.get("everyday_domain") or ""),
            )

        metadata: dict[str, Any] = {
            "project_id": self.storage.project_id,
            "pillar": eff_pillar,
            "title": clean_title,
            "title_char_count": len(clean_title),
            "doi": raw_doi,
            "doi_url": doi_url,
            "tags": resolved_tags,
            "hashtags": eff_hashtags,
            "category": DEFAULT_VIDEO_CATEGORY,
            "language": VIDEO_LANGUAGE_CODE,
            "profile": resolved_profile,
            "style_profile": resolved_style_profile,
            "video_language": VIDEO_LANGUAGE_CODE,
            "video_language_label": VIDEO_LANGUAGE_LABEL,
            "title_description_language": TITLE_DESCRIPTION_LANGUAGE_CODE,
            "title_description_language_label": TITLE_DESCRIPTION_LANGUAGE_LABEL,
            "channel_residence_country": CHANNEL_RESIDENCE_COUNTRY,
            "channel_residence_country_name": CHANNEL_RESIDENCE_COUNTRY_NAME,
            "target_audience_region": TARGET_AUDIENCE_REGION,
            "target_upload_time_et": "12:00 PM - 2:00 PM ET",
            "related_short": related_short,
            "ai_disclosure": True,
            "ai_content_declaration": True,
            "ai_assisted_content_declaration": {
                "altered_or_synthetic_content": True,
                "label_required": True,
                "note": "AI-generated visual synthesis and neural voice (R4 compliance)"
            },
            "description": resolved_description,
        }
        if is_v8:
            metadata["shorts_format_profile"] = SHORTS_EXPRESSIVE_V8_PROFILE
            if is_frozen_v8:
                metadata["pinned_comment"] = build_expressive_v8_pinned_comment(
                    doi=doi_url or raw_doi,
                    debate_question=str(scr_data.get("debate_question") or vp_data.get("debate_question") or ""),
                    cameo_prompt=str(
                        scr_data.get("cameo_prompt")
                        or vp_data.get("cameo_prompt")
                        or "Did you spot the 4cm Mini-Cortex hiding in the room?"
                    ),
                    include_doi=True,
                )
            else:
                opt_cameo = (
                    str(scr_data.get("cameo_prompt") or vp_data.get("cameo_prompt") or "")
                    if scr_data.get("include_cameo_in_pinned_comment")
                    else ""
                )
                metadata["pinned_comment"] = build_expressive_v8_pinned_comment(
                    doi=doi_url or raw_doi,
                    debate_question=str(scr_data.get("debate_question") or vp_data.get("debate_question") or ""),
                    cameo_prompt=opt_cameo,
                    include_doi=False,
                )

        # Resolve question hook from ideation/scripting if available
        question_hook = None
        paradox_data = self.storage.load_json("01_ideation", "paradox_hook.json")
        if paradox_data:
            question_hook = paradox_data.get("dissonance_trigger") or paradox_data.get("paradox_statement")

        # Generate All 3 Thumbnail Variants
        variants = self.generate_all_thumbnail_variants(
            base_asset_path=thumbnail_source_img,
            title_headline=clean_title,
            output_dir=publish_dir,
            question_hook=question_hook
        )

        # Build A/B Testing Manifest (72h sequential swap per R32: 0-72h, 72-144h, 144-216h)
        now_iso = datetime.now(timezone.utc).isoformat()
        ab_manifest = {
            "project_id": self.storage.project_id,
            "channel_id": "UC4FeioYYv9X04Di07_MfZ7g",
            "channel_handle": "@AllAboutBrainOfficial",
            "created_at": now_iso,
            "title": clean_title,
            "status": "ready",
            "current_active_variant": "A",
            "rotation_interval_hours": 72,
            "variants": {
                "A": {
                    "variant_id": "A",
                    "name": "Standard Navy & Gold",
                    "file": "thumbnail_var_A.png",
                    "relative_path": "06_publish/thumbnail_var_A.png",
                    "badge_color": "#0A1128",
                    "border_color": "#FFD700",
                    "text_color": "#FFFFFF / #FFD700",
                    "font": resolved_font_label,
                    "headline": clean_title,
                    "hypothesis": "Documentary intellectual authority; viewers responding to authoritative scientific tone.",
                    "style": "documentary_navy_gold",
                    "target_audience": "Academic & tech documentary viewers"
                },
                "B": {
                    "variant_id": "B",
                    "name": "Macro 3D Cutaway Minimal",
                    "file": "thumbnail_var_B.png",
                    "relative_path": "06_publish/thumbnail_var_B.png",
                    "badge_color": "rgba(10,17,40,0.78)",
                    "border_color": "#0E9AA7",
                    "text_color": "#0E9AA7 / #FFFFFF",
                    "font": resolved_font_label,
                    "headline": clean_title,
                    "hypothesis": "Visual awe & 3D cutaway detail; curiosity driven by high-detail visual over text.",
                    "style": "macro_visual_minimal",
                    "target_audience": "Visual-first scroll-stoppers and 3D render enthusiasts"
                },
                "C": {
                    "variant_id": "C",
                    "name": "Defiance Red Question Hook",
                    "file": "thumbnail_var_C.png",
                    "relative_path": "06_publish/thumbnail_var_C.png",
                    "badge_color": "#0A1128",
                    "border_color": "#FF3333",
                    "text_color": "#FF3333 / #FFFFFF",
                    "font": resolved_font_label,
                    "headline": self._format_provocative_question(clean_title, question_hook),
                    "hypothesis": "Cognitive dissonance & provocative defiance trigger; high-CTR curiosity gap.",
                    "style": "defiance_red_provocative",
                    "target_audience": "Curiosity gap and controversy-driven discovery viewers"
                }
            },
            "schedule": [
                {"variant": "A", "window": "0-72h", "hours": 72, "status": "active", "started_at": now_iso},
                {"variant": "B", "window": "72-144h", "hours": 72, "status": "pending", "started_at": None},
                {"variant": "C", "window": "144-216h", "hours": 72, "status": "pending", "started_at": None}
            ],
            "statistical_evaluation": {
                "metric": "Search & Browse CTR",
                "test_type": "Two-Proportion Z-Test",
                "significance_threshold_p": 0.05,
                "z_critical": 1.96,
                "winner_variant": None,
                "locked": False
            }
        }

        # Save artifacts to storage
        self.storage.record_artifact("06_publish", "thumbnail.png", thumb_path)
        self.storage.record_artifact("06_publish", "thumbnail_var_A.png", variants["A"])
        self.storage.record_artifact("06_publish", "thumbnail_var_B.png", variants["B"])
        self.storage.record_artifact("06_publish", "thumbnail_var_C.png", variants["C"])
        self.storage.save_json("06_publish", "ab_test_manifest.json", ab_manifest)
        self.storage.save_json("06_publish", "metadata.json", metadata)
        pinned_txt = str(metadata.get("pinned_comment") or "").strip()
        if pinned_txt:
            self.storage.save_text("06_publish", "pinned_comment.txt", pinned_txt + "\n")

        thumb_rep_doc = self.storage.load_json("06_publish", "thumbnail_report.json") or {}
        cover_sec = thumb_rep_doc.get("cover_frame_sec")
        cover_line = (
            f"Select in-video cover frame at `t = {cover_sec}s` in YouTube mobile app (`06_publish/thumbnail_report.json`)"
            if cover_sec is not None
            else "Select in-video cover frame at the cold-open stamp headline in YouTube mobile app (`R65`)"
        )
        checklist_md = f"""# YouTube Studio Upload & Cover Frame Checklist: {clean_title}

## 1. Video & Metadata
- [ ] **Title (≤{max_title_len} chars):** `{metadata['title']}`
- [ ] **Upload File:** `05_assembly/final_shorts_1080x1920.mp4`
- [ ] **Category:** {DEFAULT_VIDEO_CATEGORY}
- [ ] **Channel Country of Residence:** `{CHANNEL_RESIDENCE_COUNTRY_NAME} ({CHANNEL_RESIDENCE_COUNTRY})` (AdSense identity & US-KR W-8BEN 10% tax treaty)
- [ ] **Video Language:** `{VIDEO_LANGUAGE_LABEL}` (`{VIDEO_LANGUAGE_CODE}`)
- [ ] **Title & Description Language:** `{TITLE_DESCRIPTION_LANGUAGE_LABEL}` (`{TITLE_DESCRIPTION_LANGUAGE_CODE}`)
- [ ] **AI-generated content:** Check "Yes" (Altered or synthetic content disclosure - R4 compliance)
- [ ] **Audience:** Not made for kids
- [ ] **Scheduled Time:** Next US peak window (12:00 PM - 2:00 PM ET or 5-Slot Schedule)

## 2. R65 Thumbnail Studio & In-Video Cover Frame (Shorts) / R32 Long-Form A/B
- [ ] **Primary Cover (`Variant A`):** `06_publish/thumbnail_var_A.png` (R65 v7 Condensed Hook + Top-Scored Clean Cut)
- [ ] **Alternates (`B` / `C`):** `06_publish/thumbnail_var_B.png`, `06_publish/thumbnail_var_C.png`
- [ ] **Mobile Shorts Cover Frame:** {cover_line}
- [ ] **QA & Contact Sheet (`TQ1-TQ7`):** `06_publish/thumbnail_report.json`, `06_publish/thumbnail_contact_sheet.png`

## 3. Post-Publish Community Pin
- [ ] **Pinned Comment:** Academic DOI reference & cognitive dissonance question pinned at top
"""
        self.storage.save_text("06_publish", "upload_checklist.md", checklist_md)
        bundle_info = export_multi_platform_bundle(self.storage.project_dir, copy_video=False)

        self.storage.update_stage_status("06_publish", "completed")
        return {
            "metadata": metadata,
            "thumbnail_path": str(thumb_path),
            "thumbnail_variants": {k: str(v) for k, v in variants.items()},
            "ab_test_manifest_path": str(publish_dir / "ab_test_manifest.json"),
            "multi_platform_bundle": bundle_info,
        }


PublishPackager = PublishStage

_HANGUL_RE = re.compile(r"[\uac00-\ud7a3\u1100-\u11ff\u3130-\u318f]+")
_BANNED_SPAM_HASHTAGS: frozenset[str] = frozenset(
    {
        "#fyp",
        "#viral",
        "#foryou",
        "#foryoupage",
        "#trending",
        "#explore",
        "#explorepage",
        "#shorts",
        "#reels",
        "#tiktok",
    }
)
_DOMAIN_NICHE_HASHTAG_MAP: dict[str, str] = {
    "habits": "#habits",
    "sleep": "#sleephealth",
    "memory": "#memory",
    "anxiety": "#mentalhealth",
    "stress": "#mentalhealth",
    "emotions": "#emotionalhealth",
    "relationships": "#socialpsychology",
    "social": "#socialpsychology",
    "focus": "#focus",
    "attention": "#focus",
    "bci_tech": "#neurotech",
    "bci_ethics": "#neuroethics",
    "brain_health": "#brainhealth",
    "brain_basics": "#selfcontrol",
    "brain_mysteries": "#cognitivepsychology",
    "brain_history": "#neurology",
    "brain_news": "#brainresearch",
}


def _strip_hangul_and_hashtags(text: str) -> str:
    cleaned = _HANGUL_RE.sub("", str(text or ""))
    cleaned = re.sub(r"(?:^|\s)#[A-Za-z0-9_]+", "", cleaned)
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    return cleaned.strip()


def _truncate_line_under_limit(text: str, max_chars: int = 90) -> str:
    line = _strip_hangul_and_hashtags(text).replace("\n", " ").strip()
    if len(line) <= max_chars:
        return line
    cut = line[: max_chars - 1].rstrip()
    if " " in cut:
        cut = cut.rsplit(" ", 1)[0].rstrip(" ,;:-—")
    suffix = "?" if line.endswith("?") else "."
    return f"{cut}{suffix}"[:max_chars]


def resolve_bundle_video_path(project_dir: Path | str) -> Path | None:
    """
    Resolves the clean 9:16 MP4 for Instagram Reels / TikTok publishing:
      1. `06_publish/multi_platform_bundle/video_clean.mp4` if present & non-empty
      2. `source_video_relpath` inside `bundle_manifest.json` or `upload_checklist.json`
      3. `05_assembly/final_shorts_1080x1920.mp4` (or `episode_full.mp4` / `final_video.mp4`)
    """
    raw_p = Path(project_dir)
    p_dir = raw_p if raw_p.exists() or raw_p.is_absolute() else (PROJECTS_DIR / str(project_dir))
    if not p_dir.exists() and (PROJECTS_DIR / raw_p.name).exists():
        p_dir = PROJECTS_DIR / raw_p.name

    bundle_dir = p_dir / "06_publish" / "multi_platform_bundle"
    direct_vid = bundle_dir / "video_clean.mp4"
    if direct_vid.is_file() and direct_vid.stat().st_size > 0:
        return direct_vid

    for mf_name in ("bundle_manifest.json", "upload_checklist.json"):
        mf_path = bundle_dir / mf_name
        if mf_path.is_file():
            try:
                doc = json.loads(mf_path.read_text(encoding="utf-8"))
                rel_v = str((doc if isinstance(doc, dict) else {}).get("source_video_relpath") or "").strip()
                if rel_v:
                    cand_v = p_dir / rel_v
                    if cand_v.is_file() and cand_v.stat().st_size > 0:
                        return cand_v
            except Exception:
                pass

    src_video, _, _ = _probe_project_video_metrics(p_dir)
    return src_video


def _probe_project_video_metrics(
    project_dir: Path,
) -> tuple[Path | None, float, str]:
    asm_dir = project_dir / "05_assembly"
    src_video: Path | None = None
    for cand_name in ("final_shorts_1080x1920.mp4", "episode_full.mp4", "final_video.mp4"):
        cand = asm_dir / cand_name
        if cand.is_file() and cand.stat().st_size > 0:
            src_video = cand
            break

    duration_sec = 0.0
    resolution = f"{VIDEO_WIDTH}x{VIDEO_HEIGHT}"

    probe_json = asm_dir / "probe_report.json"
    if probe_json.is_file():
        try:
            p_doc = json.loads(probe_json.read_text(encoding="utf-8"))
            duration_sec = float(p_doc.get("duration_sec") or p_doc.get("format_duration_sec") or 0.0)
            w = int(p_doc.get("width") or 0)
            h = int(p_doc.get("height") or 0)
            if w > 0 and h > 0:
                resolution = f"{w}x{h}"
        except Exception:
            pass

    if src_video is not None and duration_sec <= 0.0:
        try:
            import cv2

            cap = cv2.VideoCapture(str(src_video))
            if cap.isOpened():
                fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
                frames = float(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0.0)
                w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
                h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
                if fps > 0.0 and frames > 0.0:
                    duration_sec = frames / fps
                if w > 0 and h > 0:
                    resolution = f"{w}x{h}"
            cap.release()
        except Exception:
            pass

    if duration_sec <= 0.0:
        edl_path = asm_dir / "edit_decision_list.json"
        if edl_path.is_file():
            try:
                edl_doc = json.loads(edl_path.read_text(encoding="utf-8"))
                duration_sec = float(edl_doc.get("total_duration_sec") or 0.0)
            except Exception:
                pass

    return src_video, round(max(0.0, duration_sec), 3), resolution


def _extract_bundle_sentences(script_doc: dict[str, Any]) -> list[str]:
    raw_sents = script_doc.get("sentences")
    if isinstance(raw_sents, list) and raw_sents:
        out: list[str] = []
        for s in raw_sents:
            if isinstance(s, dict):
                raw_txt = str(s.get("text") or s.get("narration") or "")
            else:
                raw_txt = str(s)
            cs = _strip_hangul_and_hashtags(raw_txt)
            if cs:
                out.append(cs)
        if out:
            return out
    acts = script_doc.get("acts")
    if isinstance(acts, list):
        out_acts: list[str] = []
        for act in acts:
            if isinstance(act, dict):
                for s in act.get("sentences") or []:
                    raw_txt = str(s.get("text") or s.get("narration") or "") if isinstance(s, dict) else str(s)
                    cs = _strip_hangul_and_hashtags(raw_txt)
                    if cs:
                        out_acts.append(cs)
        if out_acts:
            return out_acts
    return []


YOUTUBE_QUIZ_QUESTION_MAX_CHARS = 240
YOUTUBE_QUIZ_OPTION_MAX_CHARS = 80
YOUTUBE_QUIZ_EXPLANATION_TARGET_MAX_CHARS = 450
YOUTUBE_QUIZ_EXPLANATION_HARD_MAX_CHARS = 500
YOUTUBE_QUIZ_RECOMMENDED_OFFSET_MINUTES = -210  # 16:00 ET (3.5h warmup before 19:30 ET Short)
YOUTUBE_QUIZ_CLOSING_CTA = "Tonight's new Short breaks down the exact brain circuit -> @AllAboutBrainOfficial"


def _scrub_comment_violence_tokens(text: str) -> str:
    cleaned = str(text or "")
    replacements = {
        "suicide": "crisis",
        "suicidal": "acute",
        "murder": "tragedy",
        "murdered": "harmed",
        "kill": "silence",
        "killed": "damaged",
        "killing": "halting",
        "deadly": "severe",
        "fatal": "severe",
        "stabbed": "injured",
        "shot": "injured",
        "torture": "distress",
        "blood": "pulse",
        "corpse": "body",
    }
    for tok in BANNED_COMMENT_VIOLENCE_TOKENS:
        t_low = str(tok).strip().lower()
        if not t_low:
            continue
        rep = replacements.get(t_low, "clinical")
        cleaned = re.sub(rf"\b{re.escape(t_low)}\b", rep, cleaned, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", cleaned).strip()


def validate_youtube_community_quiz_payload(payload: dict[str, Any]) -> list[str]:
    """
    Hard-validates `youtube_quiz_post.json`:
      - `question`: non-empty English question `<= 240` chars ending with `?`, zero Hangul, zero banned violence tokens.
      - `options`: 4 options, each `1..80` chars, exactly 1 `is_correct: True`.
      - `explanation`: non-empty `<= 500` chars (target `<= 450` chars), zero Hangul, zero banned violence tokens.
      - `recommended_offset_minutes`: integer (default `-210`).
    """
    issues: list[str] = []
    if not isinstance(payload, dict):
        return ["[quiz] payload must be a JSON object"]

    q = str(payload.get("question") or "").strip()
    if not q:
        issues.append("[quiz] question is empty")
    else:
        if len(q) > YOUTUBE_QUIZ_QUESTION_MAX_CHARS:
            issues.append(f"[quiz] question length {len(q)} > {YOUTUBE_QUIZ_QUESTION_MAX_CHARS}")
        if not q.endswith("?"):
            issues.append("[quiz] question must end with '?'")
        if _HANGUL_RE.search(q):
            issues.append("[quiz] question contains forbidden Hangul characters")

    opts = payload.get("options")
    if not isinstance(opts, list) or len(opts) != 4:
        issues.append(f"[quiz] options must contain exactly 4 items (got {len(opts) if isinstance(opts, list) else 'non-list'})")
    else:
        correct_count = 0
        seen_texts: set[str] = set()
        for idx, opt in enumerate(opts, start=1):
            if not isinstance(opt, dict):
                issues.append(f"[quiz] option {idx} is not an object")
                continue
            ot = str(opt.get("text") or "").strip()
            if not ot:
                issues.append(f"[quiz] option {idx} text is empty")
            elif len(ot) > YOUTUBE_QUIZ_OPTION_MAX_CHARS:
                issues.append(
                    f"[quiz] option {idx} length {len(ot)} exceeds YouTube {YOUTUBE_QUIZ_OPTION_MAX_CHARS}-char limit: {ot!r}"
                )
            if _HANGUL_RE.search(ot):
                issues.append(f"[quiz] option {idx} contains forbidden Hangul")
            low_ot = ot.lower()
            if low_ot in seen_texts:
                issues.append(f"[quiz] duplicate option text on option {idx}: {ot!r}")
            seen_texts.add(low_ot)
            if opt.get("is_correct") is True:
                correct_count += 1
        if correct_count != 1:
            issues.append(f"[quiz] exactly 1 option must have is_correct=True (got {correct_count})")

    exp = str(payload.get("explanation") or "").strip()
    if not exp:
        issues.append("[quiz] explanation is empty")
    elif len(exp) > YOUTUBE_QUIZ_EXPLANATION_HARD_MAX_CHARS:
        issues.append(
            f"[quiz] explanation length {len(exp)} exceeds YouTube {YOUTUBE_QUIZ_EXPLANATION_HARD_MAX_CHARS}-char ceiling"
        )
    if _HANGUL_RE.search(exp):
        issues.append("[quiz] explanation contains forbidden Hangul")

    combined_low = " ".join(
        [
            q,
            exp,
            *(str(o.get("text") or "") for o in (opts if isinstance(opts, list) else []) if isinstance(o, dict)),
        ]
    ).lower()
    for vtok in BANNED_COMMENT_VIOLENCE_TOKENS:
        vt = str(vtok).strip().lower()
        if vt and re.search(rf"\b{re.escape(vt)}\b", combined_low):
            issues.append(f"[quiz] banned violence token '{vt}' found in quiz payload")

    return issues


def build_youtube_community_quiz_payload(project_dir: Path | str) -> dict[str, Any]:
    """
    Builds a non-spoiler English YouTube Community `Quiz` post payload (`youtube_quiz_post.json`)
    designed to warm up feed discovery `3.5h` (`-210` min, `16:00 ET`) before a `19:30 ET` Short.
    """
    raw_p = Path(project_dir)
    p_dir = raw_p if raw_p.exists() or raw_p.is_absolute() else (PROJECTS_DIR / str(project_dir))
    if not p_dir.exists() and (PROJECTS_DIR / raw_p.name).exists():
        p_dir = PROJECTS_DIR / raw_p.name

    def _rj(path: Path) -> dict[str, Any]:
        if not path.is_file():
            return {}
        try:
            d = json.loads(path.read_text(encoding="utf-8"))
            return d if isinstance(d, dict) else {}
        except Exception:
            return {}

    pub_dir = p_dir / "06_publish"
    meta_doc = _rj(pub_dir / "metadata.json")
    script_doc = _rj(p_dir / "02_script" / "script.json")
    vp_doc = _rj(p_dir / "03_visuals" / "visual_plan.json")
    project_id = str(meta_doc.get("project_id") or script_doc.get("project_id") or p_dir.name)

    _cit_str, doi_str = _extract_study_citation(meta_doc, script_doc)

    # Honor explicit quiz override in script.json if present (still hard-validated)
    explicit_quiz = script_doc.get("community_quiz")
    if isinstance(explicit_quiz, dict) and explicit_quiz.get("question") and explicit_quiz.get("options"):
        payload = {
            "project_id": project_id,
            "question": _scrub_comment_violence_tokens(_strip_hangul_and_hashtags(str(explicit_quiz["question"]))),
            "options": [
                {
                    "text": _truncate_line_under_limit(
                        _scrub_comment_violence_tokens(str(o.get("text") or "")),
                        max_chars=YOUTUBE_QUIZ_OPTION_MAX_CHARS,
                    ).rstrip("."),
                    "is_correct": bool(o.get("is_correct") is True),
                }
                for o in list(explicit_quiz.get("options") or [])[:4]
                if isinstance(o, dict)
            ],
            "explanation": _scrub_comment_violence_tokens(
                _strip_hangul_and_hashtags(str(explicit_quiz.get("explanation") or ""))
            ),
            "doi": doi_str,
            "recommended_offset_minutes": int(
                explicit_quiz.get("recommended_offset_minutes", YOUTUBE_QUIZ_RECOMMENDED_OFFSET_MINUTES)
            ),
        }
        errs = validate_youtube_community_quiz_payload(payload)
        if errs:
            raise ValueError("; ".join(errs))
        return payload

    sents = _extract_bundle_sentences(script_doc)
    full_blob_low = " ".join([project_id, str(meta_doc.get("title") or ""), *sents]).lower()

    if "capgras" in full_blob_low or ("fusiform" in full_blob_low and "amygdala" in full_blob_low):
        question = (
            "After a head injury, a patient trusted his mom's voice on the phone right away, "
            "yet insisted she was a look-alike in person. Which brain link broke?"
        )
        options = [
            {"text": "Primary visual cortex lost basic sight", "is_correct": False},
            {"text": "Fusiform face area disconnected from the amygdala", "is_correct": True},
            {"text": "Hippocampus erased childhood family memories", "is_correct": False},
            {"text": "Auditory cortex stopped recognizing familiar voices", "is_correct": False},
        ]
        exp_core = (
            "His fusiform face detector still matched Mom's face, but a severed link to the amygdala "
            "erased the automatic gut warmth of familiarity while phone audio stayed intact."
        )
    else:
        # Derive episode-specific structure + curiosity hook for any neuroscience episode
        detected_anat = ""
        for phrase in _KNOWN_ANATOMY_PHRASES:
            if phrase in full_blob_low:
                detected_anat = phrase
                break
        if not detected_anat:
            for clip in vp_doc.get("clips") or []:
                if isinstance(clip, dict):
                    ts_list = clip.get("target_structures") or []
                    if isinstance(ts_list, list) and ts_list:
                        detected_anat = str(ts_list[0]).replace("_", " ").strip().lower()
                        break
        anat_title = (detected_anat or "subcortical relay").title()

        s1 = _scrub_comment_violence_tokens(sents[0]) if sents else ""
        if s1 and len(s1) <= 170:
            base_setup = s1.rstrip("?!.")
            question = f"{base_setup}. Which hidden brain mechanism drives this?"
        else:
            clean_t = _scrub_comment_violence_tokens(
                _strip_hangul_and_hashtags(str(meta_doc.get("title") or script_doc.get("title") or "this brain paradox"))
            ).rstrip("?!.")
            question = f"Neuroscience quiz: in '{clean_t}', which neural pathway explains the paradox?"
        question = _truncate_line_under_limit(question, max_chars=YOUTUBE_QUIZ_QUESTION_MAX_CHARS)
        if not question.endswith("?"):
            question = question.rstrip(".! ")[: YOUTUBE_QUIZ_QUESTION_MAX_CHARS - 1] + "?"

        correct_opt = _truncate_line_under_limit(
            f"{anat_title} signaling shifts before conscious awareness",
            max_chars=YOUTUBE_QUIZ_OPTION_MAX_CHARS,
        ).rstrip(".")
        distractor_pool = [
            "Complete shutdown of primary visual cortex",
            "Total loss of long-term spinal reflexes",
            "Purely random inner-ear balance drift",
            "Delayed optic nerve pigment bleaching",
        ]
        picked_distractors = [d for d in distractor_pool if anat_title.lower() not in d.lower()][:3]
        options = [
            {"text": picked_distractors[0], "is_correct": False},
            {"text": correct_opt, "is_correct": True},
            {"text": picked_distractors[1], "is_correct": False},
            {"text": picked_distractors[2], "is_correct": False},
        ]

        core_idx_1b = int(script_doc.get("core_reveal_sentence_index") or 0)
        if 1 <= core_idx_1b <= len(sents):
            exp_core = _scrub_comment_violence_tokens(sents[core_idx_1b - 1])
        elif len(sents) >= 3:
            exp_core = _scrub_comment_violence_tokens(sents[2])
        else:
            exp_core = (
                f"Peer-reviewed recordings show {anat_title.lower()} circuits reshape perception before conscious thought catches up."
            )
        if not exp_core.endswith("."):
            exp_core = exp_core.rstrip("!? ") + "."

    doi_piece = f" Verified study DOI: {doi_str}." if doi_str else ""
    explanation = f"{exp_core}{doi_piece} {YOUTUBE_QUIZ_CLOSING_CTA}".strip()
    if len(explanation) > YOUTUBE_QUIZ_EXPLANATION_TARGET_MAX_CHARS:
        budget = YOUTUBE_QUIZ_EXPLANATION_TARGET_MAX_CHARS - len(doi_piece) - len(YOUTUBE_QUIZ_CLOSING_CTA) - 2
        trimmed_core = _truncate_line_under_limit(exp_core, max_chars=max(90, budget))
        explanation = f"{trimmed_core}{doi_piece} {YOUTUBE_QUIZ_CLOSING_CTA}".strip()

    payload = {
        "project_id": project_id,
        "question": _scrub_comment_violence_tokens(question),
        "options": [
            {
                "text": _scrub_comment_violence_tokens(str(o["text"]))[:YOUTUBE_QUIZ_OPTION_MAX_CHARS].strip(),
                "is_correct": bool(o["is_correct"]),
            }
            for o in options
        ],
        "explanation": _scrub_comment_violence_tokens(explanation)[:YOUTUBE_QUIZ_EXPLANATION_HARD_MAX_CHARS].strip(),
        "doi": doi_str,
        "recommended_offset_minutes": YOUTUBE_QUIZ_RECOMMENDED_OFFSET_MINUTES,
    }
    errs = validate_youtube_community_quiz_payload(payload)
    if errs:
        raise ValueError("; ".join(errs))
    return payload


def build_instagram_carousel_caption(
    *,
    hook_line: str,
    slides_summary_lines: list[str],
    citation_str: str,
    doi_str: str,
    debate_question: str,
    hashtags: list[str],
) -> str:
    """
    Builds the 6-slide `4:5` Instagram Carousel caption (`carousel_caption.txt`):
      - Crisp hook line (`<= 90` chars)
      - Compact 6-slide takeaway digest
      - Peer-reviewed study + verified DOI (`Study: ... · DOI: 10.xxxx/...`)
      - Organic Save & Share CTA (STRICT ZERO ManyChat / comment-keyword DM / IG Notes spam)
      - `<= 5` clean niche hashtags
    """
    lead = _truncate_line_under_limit(hook_line, max_chars=90)
    bullet_lines: list[str] = []
    for idx, sl_txt in enumerate(slides_summary_lines[:6], start=1):
        clean_sl = _sanitize_r68d_plain_text(sl_txt, allow_colon=False).rstrip(".")
        if clean_sl:
            bullet_lines.append(f"{idx}/ {_truncate_line_under_limit(clean_sl, max_chars=115)}")
    digest = "\n".join(bullet_lines)

    clean_cit = _sanitize_r68d_plain_text(citation_str, allow_colon=False).rstrip(".")
    source_line = (
        f"Study: {clean_cit} (DOI: {doi_str})"
        if doi_str
        else f"Study: {clean_cit or 'Peer-reviewed clinical neuroscience study'}"
    )
    clean_q = _strip_hangul_and_hashtags(debate_question).replace("—", ", ").strip()
    if clean_q and not clean_q.endswith("?"):
        clean_q = clean_q.rstrip(".! ") + "?"
    cta_line = "Save this 6-slide breakdown for later & share it with someone curious about how the brain works."
    clean_tags = [t for t in hashtags[:5] if t.startswith("#") and t.lower() not in _BANNED_SPAM_HASHTAGS]

    blocks = [b for b in (lead, digest, clean_q, source_line, cta_line, " ".join(clean_tags)) if b]
    return "\n\n".join(blocks) + "\n"


def _evaluate_bundle_safe_zones(
    p_dir: Path,
    cover_path: Path,
    slide_paths: list[Path],
) -> tuple[dict[str, Any], dict[str, Any]]:
    cover_w, cover_h = 0, 0
    if cover_path.is_file():
        try:
            with Image.open(cover_path) as im:
                cover_w, cover_h = im.size
        except Exception:
            pass

    ig_3x4_crop_y = [240, 1680]
    tiktok_safe_box = {"x_min": 40, "x_max": 940, "y_min": 130, "y_max": 1620}
    thumb_report_path = p_dir / "06_publish" / "thumbnail_report.json"
    text_in_ig_crop = True
    text_in_tiktok_safe = True
    if thumb_report_path.is_file():
        try:
            tr = json.loads(thumb_report_path.read_text(encoding="utf-8"))
            tb = tr.get("text_bbox") or tr.get("headline_bbox")
            if isinstance(tb, list) and len(tb) == 4:
                x0, y0, x1, y1 = [int(v) for v in tb]
                text_in_ig_crop = bool(y0 >= ig_3x4_crop_y[0] and y1 <= ig_3x4_crop_y[1])
                text_in_tiktok_safe = bool(
                    y0 >= tiktok_safe_box["y_min"]
                    and y1 <= tiktok_safe_box["y_max"]
                    and x1 <= tiktok_safe_box["x_max"]
                )
        except Exception:
            pass

    cover_check = {
        "width": cover_w,
        "height": cover_h,
        "is_9x16_1080x1920": bool(cover_w == 1080 and cover_h == 1920),
        "ig_profile_3x4_vertical_crop_y_range": ig_3x4_crop_y,
        "tiktok_ui_safe_zone_px": {
            "top_clear_px": 130,
            "bottom_clear_px": 300,
            "right_clear_px": 140,
        },
        "text_within_ig_3x4_crop": text_in_ig_crop,
        "text_within_tiktok_safe_zone": text_in_tiktok_safe,
        "passed": bool(cover_w == 1080 and cover_h == 1920 and text_in_ig_crop and text_in_tiktok_safe),
    }

    slide_dims: list[tuple[int, int]] = []
    for sp in slide_paths:
        if sp.is_file():
            try:
                with Image.open(sp) as sim:
                    slide_dims.append(sim.size)
            except Exception:
                pass
    all_1080x1350 = bool(len(slide_dims) == 6 and all(d == (1080, 1350) for d in slide_dims))
    carousel_check = {
        "slide_count": len(slide_dims),
        "dimensions": "1080x1350",
        "aspect_ratio": 0.80,
        "horizontal_margin_px": 90,
        "safe_text_x_range": [90, 990],
        "ig_profile_3x4_crop_x_range": [34, 1046],
        "inner_safety_buffer_px": 56,
        "passed": all_1080x1350,
    }
    return cover_check, carousel_check


def _derive_primary_search_keyword_and_alignment(
    *,
    raw_title: str,
    sents: list[str],
    caption_line1: str,
    meta_doc: dict[str, Any],
    script_doc: dict[str, Any],
) -> tuple[str, dict[str, Any]]:
    explicit_kw = str(
        script_doc.get("primary_search_keyword") or meta_doc.get("primary_search_keyword") or ""
    ).strip().lower()

    if not explicit_kw:
        _generic_tags = {
            "psychology",
            "neuroscience",
            "brain facts",
            "human behavior",
            "all about brain",
            "everyday psychology",
            "cognitive psychology",
            "shorts",
            "youtube shorts",
            "science",
            "brain",
            "mind",
        }
        tags = [str(t).strip().lower() for t in (meta_doc.get("tags") or []) if str(t).strip()]
        specific_tags = [t for t in tags if t not in _generic_tags and len(t) >= 4]
        if specific_tags:
            explicit_kw = specific_tags[0]
        else:
            project_slug_words = [
                w
                for w in str(meta_doc.get("project_id") or script_doc.get("project_id") or "").lower().split("_")
                if len(w) >= 4 and not re.fullmatch(r"v\d+|ep\d+|r\d+|pilot", w)
            ]
            if len(project_slug_words) >= 2:
                explicit_kw = " ".join(project_slug_words[:2])
            else:
                words = [
                    re.sub(r"[^a-z0-9]", "", w.lower())
                    for w in raw_title.split()
                    if len(re.sub(r"[^a-z0-9]", "", w.lower())) >= 4 and w.lower() not in _TAG_STOPWORDS
                ]
                explicit_kw = " ".join(words[:2]) or "brain circuit"

    kw_tokens = [tok for tok in explicit_kw.split() if len(tok) >= 3]
    hook_s1 = sents[0] if sents else ""

    def _matches_surface(surface: str) -> bool:
        low = surface.lower()
        if explicit_kw in low:
            return True
        return any(tok in low for tok in kw_tokens)

    alignment = {
        "primary_search_keyword": explicit_kw,
        "in_spoken_hook_s1": _matches_surface(hook_s1),
        "in_cover_or_title": _matches_surface(raw_title),
        "in_caption_line1": _matches_surface(caption_line1),
    }
    alignment["aligned_surface_count"] = int(
        sum(
            1
            for k in ("in_spoken_hook_s1", "in_cover_or_title", "in_caption_line1")
            if alignment[k]
        )
    )
    return explicit_kw, alignment


def _extract_study_citation(meta_doc: dict[str, Any], script_doc: dict[str, Any]) -> tuple[str, str]:
    raw_doi = _strip_hangul_and_hashtags(
        str(
            meta_doc.get("primary_doi")
            or meta_doc.get("doi")
            or script_doc.get("doi")
            or ""
        )
    )
    raw_doi = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", raw_doi, flags=re.IGNORECASE).strip()

    desc = str(meta_doc.get("description") or script_doc.get("viewer_description") or "")
    m_res = re.search(r"^Research:\s*([^\n]+)", desc, flags=re.MULTILINE)
    if m_res:
        res_body = _sanitize_r68d_plain_text(m_res.group(1), allow_colon=False).rstrip(".")
        if res_body:
            return res_body[:110], raw_doi

    m_src = re.search(r"Primary Peer-Reviewed Sources:\s*\n-\s*([^\n]+)", desc)
    if m_src:
        bullet = _sanitize_r68d_plain_text(m_src.group(1), allow_colon=False).rstrip(".")
        m_compact = re.match(r"^([^()]+?\(\d{4}\))\.\s+.+?\.\s+([A-Za-z][A-Za-z0-9 &\-]{2,55})$", bullet)
        if m_compact:
            return f"{m_compact.group(1).strip()}, {m_compact.group(2).strip()}", raw_doi
        if bullet:
            return bullet[:110], raw_doi

    for st in script_doc.get("data_stamps") or []:
        if isinstance(st, dict):
            sc = _sanitize_r68d_plain_text(str(st.get("source_citation") or ""), allow_colon=False).rstrip(".")
            if sc:
                return sc, raw_doi

    return "Peer-reviewed neuroscience and psychology research", raw_doi


def _select_niche_hashtags(
    meta_doc: dict[str, Any],
    script_doc: dict[str, Any],
    *,
    target_count: int = 5,
) -> list[str]:
    base = ["#neuroscience", "#psychology", "#brainfacts", "#humanbehavior"]
    domain = str(
        meta_doc.get("everyday_domain")
        or script_doc.get("everyday_domain")
        or meta_doc.get("pillar")
        or script_doc.get("pillar")
        or ""
    ).strip().lower()
    domain_tag = _DOMAIN_NICHE_HASHTAG_MAP.get(domain, "#cognitivepsychology")
    ordered: list[str] = []
    for tag in [*base, domain_tag]:
        low = tag.lower().strip()
        if low.startswith("#") and low not in _BANNED_SPAM_HASHTAGS and low not in ordered:
            ordered.append(low)
    cap = max(3, min(5, int(target_count)))
    if cap == 4 and domain_tag not in ordered[:3]:
        return [*ordered[:3], domain_tag]
    return ordered[:cap]


def export_multi_platform_bundle(
    project_dir: Path | str,
    *,
    copy_video: bool = False,
) -> dict[str, Any]:
    """
    Exports a 3-platform-ready TikTok & Instagram Reels distribution bundle into
    `<project_dir>/06_publish/multi_platform_bundle/` without touching YouTube's R68
    `0`-hashtag `06_publish/metadata.json` contract and without creating POSIX symlinks
    (`fuse.rclone` safe via `shutil.copy2`).
    """
    raw_p = Path(project_dir)
    p_dir = raw_p if raw_p.exists() or raw_p.is_absolute() else (PROJECTS_DIR / str(project_dir))
    if not p_dir.exists() and (PROJECTS_DIR / raw_p.name).exists():
        p_dir = PROJECTS_DIR / raw_p.name

    pub_dir = p_dir / "06_publish"
    bundle_dir = pub_dir / "multi_platform_bundle"
    bundle_dir.mkdir(parents=True, exist_ok=True)

    def _load_opt_json(path: Path) -> dict[str, Any]:
        if not path.is_file():
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    meta_doc = _load_opt_json(pub_dir / "metadata.json")
    script_doc = _load_opt_json(p_dir / "02_script" / "script.json")
    vp_doc = _load_opt_json(p_dir / "03_visuals" / "visual_plan.json")

    project_id = str(meta_doc.get("project_id") or script_doc.get("project_id") or p_dir.name)
    raw_title = _sanitize_r68d_plain_text(
        str(meta_doc.get("title") or script_doc.get("title") or vp_doc.get("title") or project_id.replace("_", " ").title()),
        allow_colon=False,
    )
    hook_line = raw_title
    if hook_line and not hook_line.endswith(("?", "!")):
        if hook_line.lower().startswith(
            (
                "why do ",
                "why does ",
                "why did ",
                "why is ",
                "why are ",
                "how do ",
                "how does ",
                "how can ",
                "what if ",
                "what happens ",
                "can ",
                "do ",
                "does ",
                "is ",
                "are ",
            )
        ):
            hook_line = hook_line.rstrip(".") + "?"

    sents = _extract_bundle_sentences(script_doc)
    core_idx_1b = int(script_doc.get("core_reveal_sentence_index") or 0)
    summary_sentences: list[str] = []
    if sents:
        if 1 <= core_idx_1b <= len(sents):
            prev_idx = max(0, core_idx_1b - 2)
            if prev_idx != (core_idx_1b - 1):
                summary_sentences.append(sents[prev_idx])
            summary_sentences.append(sents[core_idx_1b - 1])
        else:
            summary_sentences.extend(sents[:2])
    else:
        desc_first = _sanitize_r68d_plain_text(
            str(meta_doc.get("description") or "").split("\n\n")[0],
            allow_colon=False,
        )
        if desc_first:
            summary_sentences.append(desc_first)
    if not summary_sentences:
        summary_sentences = [
            "Peer-reviewed neuroscience shows how deep brain pathways shape everyday behavior."
        ]
    twist_summary = _sanitize_r68d_plain_text(" ".join(summary_sentences[:2]).strip(), allow_colon=False)

    citation_str, _doi_str = _extract_study_citation(meta_doc, script_doc)
    clean_cit = _sanitize_r68d_plain_text(citation_str, allow_colon=False).rstrip(".")
    study_line = f"Research: {clean_cit}." if clean_cit else "Research: Peer-reviewed clinical neuroscience study."

    debate_q = build_expressive_v8_pinned_comment(
        debate_question=str(
            meta_doc.get("debate_question")
            or script_doc.get("debate_question")
            or "What do you think drives your brain in moments like this?"
        ),
        include_doi=False,
    )

    tiktok_tags = _select_niche_hashtags(meta_doc, script_doc, target_count=5)
    reels_tags = _select_niche_hashtags(meta_doc, script_doc, target_count=4)

    tiktok_caption = (
        f"{hook_line}\n\n"
        f"{twist_summary}\n\n"
        f"{study_line}\n\n"
        f"{debate_q}\n\n"
        f"{' '.join(tiktok_tags)}\n"
    )

    reels_hook_line1 = _truncate_line_under_limit(hook_line, max_chars=90)
    reels_cta = "Save this for later & send it to someone curious about how the brain works."
    reels_caption = (
        f"{reels_hook_line1}\n\n"
        f"{twist_summary}\n\n"
        f"{debate_q}\n\n"
        f"{reels_cta}\n\n"
        f"{study_line}\n\n"
        f"{' '.join(reels_tags)}\n"
    )

    # 1. Copy assembled clean MP4 (never symlink — fuse.rclone safe)
    src_video, duration_sec, resolution = _probe_project_video_metrics(p_dir)
    dst_video = bundle_dir / "video_clean.mp4"
    if copy_video and src_video is not None and src_video.is_file():
        shutil.copy2(src_video, dst_video)

    # 2. Copy or synthesize 9:16 cover PNG (never symlink)
    dst_cover = bundle_dir / "cover_9x16.png"
    src_cover: Path | None = None
    for cov_name in ("thumbnail.png", "thumbnail_var_A.png"):
        cand_cov = pub_dir / cov_name
        if cand_cov.is_file() and cand_cov.stat().st_size > 0:
            src_cover = cand_cov
            break
    if src_cover is not None:
        shutil.copy2(src_cover, dst_cover)
    elif not dst_cover.is_file():
        stage_tmp = PublishStage(ProjectStorage(p_dir.name, projects_dir=p_dir.parent))
        stage_tmp.generate_thumbnail_variant_a(src_video, raw_title or project_id, dst_cover)

    # 3 & 4. Write platform captions
    dst_tiktok = bundle_dir / "tiktok_caption.txt"
    dst_reels = bundle_dir / "reels_caption.txt"
    dst_tiktok.write_text(tiktok_caption, encoding="utf-8")
    dst_reels.write_text(reels_caption, encoding="utf-8")

    # 5. Render 6-slide 4:5 (1080x1350, 90px margin) Instagram Carousel + carousel_caption.txt
    from pipeline.instagram_cards import (
        extract_episode_carousel_slides,
        render_carousel_4x5_slides,
    )

    carousel_slides = extract_episode_carousel_slides(p_dir)
    slide_paths = render_carousel_4x5_slides(carousel_slides, bundle_dir)

    carousel_tags = _select_niche_hashtags(meta_doc, script_doc, target_count=5)
    carousel_caption = build_instagram_carousel_caption(
        hook_line=hook_line,
        slides_summary_lines=[sl.body for sl in carousel_slides],
        citation_str=citation_str,
        doi_str=_doi_str,
        debate_question=debate_q,
        hashtags=carousel_tags,
    )
    dst_carousel_caption = bundle_dir / "carousel_caption.txt"
    dst_carousel_caption.write_text(carousel_caption, encoding="utf-8")

    # 6. Build & validate YouTube Community Quiz Post payload (16:00 ET / -210 min warmup)
    quiz_payload = build_youtube_community_quiz_payload(p_dir)
    dst_quiz_json = bundle_dir / "youtube_quiz_post.json"
    dst_quiz_json.write_text(json.dumps(quiz_payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # 7. Safe-zone & triple-SEO alignment audits
    cover_safe_zone_check, carousel_safe_zone_check = _evaluate_bundle_safe_zones(
        p_dir, dst_cover, slide_paths
    )
    primary_search_keyword, triple_seo_alignment = _derive_primary_search_keyword_and_alignment(
        raw_title=raw_title,
        sents=sents,
        caption_line1=hook_line,
        meta_doc=meta_doc,
        script_doc=script_doc,
    )

    # 8. Write upload_checklist.json with exact file metadata & Creator Rewards / VPN / AIGC / R75 locks
    dst_checklist = bundle_dir / "upload_checklist.json"

    def _file_entry(p: Path) -> dict[str, Any]:
        exists = p.is_file()
        try:
            rel_p = str(p.relative_to(p_dir)).replace("\\", "/")
        except ValueError:
            rel_p = str(p)
        return {
            "path": rel_p,
            "exists": exists,
            "size_bytes": int(p.stat().st_size) if exists else 0,
        }

    files_map: dict[str, Any] = {
        "video_clean.mp4": _file_entry(dst_video),
        "cover_9x16.png": _file_entry(dst_cover),
        "tiktok_caption.txt": _file_entry(dst_tiktok),
        "reels_caption.txt": _file_entry(dst_reels),
        "carousel_caption.txt": _file_entry(dst_carousel_caption),
        "youtube_quiz_post.json": _file_entry(dst_quiz_json),
    }
    for sp in slide_paths:
        files_map[f"carousel_4x5/{sp.name}"] = _file_entry(sp)
    files_map["upload_checklist.json"] = {
        "path": "06_publish/multi_platform_bundle/upload_checklist.json",
        "exists": True,
        "size_bytes": 0,
    }

    checklist_doc: dict[str, Any] = {
        "bundle_schema_version": 2,
        "project_id": project_id,
        "title": raw_title,
        "language": "en-US",
        "duration_sec": duration_sec,
        "min_duration_required_sec": float(SHORTS_EXPRESSIVE_V8_DURATION_MIN_SEC),
        "tiktok_over_60s_eligible": bool(duration_sec >= float(SHORTS_EXPRESSIVE_V8_DURATION_MIN_SEC)),
        "resolution": resolution,
        "aigc_disclosure_required": True,
        "aigc_disclosure_instructions": {
            "tiktok": "Enable 'AI-generated content' toggle before posting.",
            "instagram_reels": "Enable 'Add AI info' / 'Made with AI' label if prompted.",
            "instagram_carousel": "Enable 'Add AI label' toggle if prompted.",
        },
        "vpn_prohibited_warning": "NEVER use VPN when uploading to TikTok (triggers Security Issue disqualification)",
        "youtube_hashtags_untouched": True,
        "youtube_upload_srt_cc": False,
        "youtube_auto_dubbing_burned_ass": False,
        "tiktok_trending_sound_prohibited": True,
        "manychat_comment_dm_prohibited": True,
        "instagram_notes_prohibited": True,
        "primary_search_keyword": primary_search_keyword,
        "triple_seo_alignment": triple_seo_alignment,
        "cover_safe_zone_check": cover_safe_zone_check,
        "carousel_safe_zone_check": carousel_safe_zone_check,
        "copy_video": bool(copy_video),
        "source_video_relpath": (
            str(src_video.relative_to(p_dir)).replace("\\", "/")
            if (src_video is not None and src_video.is_file() and p_dir in src_video.parents)
            else "05_assembly/final_shorts_1080x1920.mp4"
        ),
        "files": files_map,
    }
    dst_checklist.write_text(json.dumps(checklist_doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    # Stabilize upload_checklist.json's own byte size in `files`
    for _ in range(2):
        checklist_doc["files"]["upload_checklist.json"]["size_bytes"] = int(dst_checklist.stat().st_size)
        dst_checklist.write_text(json.dumps(checklist_doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    ProjectStorage.sync_existing_manifest_from_disk(p_dir)

    return {
        "bundle_dir": str(bundle_dir),
        "checklist_path": str(dst_checklist),
        "checklist": checklist_doc,
        "carousel_slides": [str(sp) for sp in slide_paths],
        "quiz_post_path": str(dst_quiz_json),
    }
