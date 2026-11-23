"""
Zero-login public US search autocomplete client, curated neuroscience/psychology
SEO keyword bank loader, and 3-point cross-platform search alignment validator.

Safety & isolation invariants:
- Pure Python standard library HTTP (`urllib.request`) against public unauthenticated
  OpenSearch suggest endpoints (`hl=en`, `gl=us`).
- ZERO browser / CDP connections and ZERO logged-in Studio session scraping
  (prevents TikTok `secsdk-captcha` and session taint).
- Deterministic offline fallback backed by `.agents/research/search_seo_keyword_bank.json`.
"""

from __future__ import annotations

import functools
import json
import math
from pathlib import Path
import re
from typing import Any
import urllib.error
import urllib.parse
import urllib.request

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_KEYWORD_BANK_PATH = REPO_ROOT / ".agents" / "research" / "search_seo_keyword_bank.json"

GOOGLE_SUGGEST_ENDPOINT = "https://suggestqueries.google.com/complete/search"
PUBLIC_SUGGEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) "
        "Gecko/20100101 Firefox/128.0"
    ),
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "en-US,en;q=0.9",
}

SEVEN_PILLARS: tuple[str, ...] = (
    "brain_mysteries",
    "brain_health",
    "brain_basics",
    "brain_history",
    "bci_tech",
    "brain_news",
    "bci_ethics",
)

BANNED_GENERIC_HASHTAGS: frozenset[str] = frozenset(
    {
        "#fyp",
        "#foryou",
        "#foryoupage",
        "#viral",
        "#viralvideo",
        "#trending",
        "#explore",
        "#explorepage",
        "#fypシ",
        "#fy",
    }
)

NOISE_AUTOCOMPLETE_TOKENS: frozenset[str] = frozenset(
    {
        "roblox",
        "fortnite",
        "minecraft",
        "valorant",
        "gta",
        "elden ring",
        "skyrim",
        "lyrics",
        "karaoke",
        "chords",
        "meme",
        "memes",
        "tiktok",
        "fanfic",
        "cosplay",
        "ost",
        "soundtrack",
    }
)

_STOPWORDS: frozenset[str] = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "but",
        "by",
        "can",
        "did",
        "do",
        "does",
        "for",
        "from",
        "had",
        "has",
        "have",
        "he",
        "her",
        "his",
        "how",
        "if",
        "in",
        "into",
        "is",
        "it",
        "its",
        "my",
        "of",
        "on",
        "or",
        "our",
        "out",
        "she",
        "so",
        "that",
        "the",
        "their",
        "them",
        "they",
        "this",
        "to",
        "up",
        "was",
        "we",
        "were",
        "what",
        "when",
        "where",
        "which",
        "who",
        "why",
        "with",
        "you",
        "your",
    }
)

_HTML_TAG_RE = re.compile(r"<[^>]+>")
_WORD_RE = re.compile(r"[a-z0-9]+(?:'[a-z0-9]+)?", re.IGNORECASE)
_HASHTAG_RE = re.compile(r"(?:^|(?<=\s))(#[A-Za-z0-9_\u3040-\u30ff]+)", re.UNICODE)


def _clean_whitespace(text: str) -> str:
    cleaned = _HTML_TAG_RE.sub("", text or "")
    return re.sub(r"\s+", " ", cleaned).strip()


def _normalize_phrase(text: str) -> str:
    tokens = [tok.lower().replace("'", "") for tok in _WORD_RE.findall(text or "")]
    return " ".join(tok for tok in tokens if tok)


def _stem_token(token: str) -> str:
    t = token.lower().replace("'", "").strip()
    if len(t) <= 3:
        return t
    if t.endswith("ies") and len(t) > 4:
        return t[:-3] + "y"
    if t.endswith("es") and len(t) > 4 and t[-3] in "sxz":
        return t[:-2]
    if t.endswith("s") and not t.endswith(("ss", "us", "is")) and len(t) > 4:
        return t[:-1]
    return t


def extract_core_keyword_tokens(phrase: str) -> list[str]:
    """Extract ordered, deduplicated content tokens (stem-normalized) from a search phrase."""
    raw_tokens = [tok.lower().replace("'", "") for tok in _WORD_RE.findall(phrase or "")]
    content = [tok for tok in raw_tokens if tok and tok not in _STOPWORDS]
    if not content:
        content = [tok for tok in raw_tokens if tok]
    seen: set[str] = set()
    ordered: list[str] = []
    for tok in content:
        stem = _stem_token(tok)
        if stem and stem not in seen:
            seen.add(stem)
            ordered.append(stem)
    return ordered


def _dedupe_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for raw in items:
        if not isinstance(raw, str):
            continue
        cleaned = _clean_whitespace(raw)
        if not cleaned:
            continue
        key = cleaned.lower()
        if key not in seen:
            seen.add(key)
            out.append(cleaned)
    return out


def filter_neuro_relevant_suggestions(
    suggestions: list[str],
    *,
    seed_query: str = "",
) -> list[str]:
    """Remove gaming/pop-culture autocomplete noise while keeping genuine viewer intent."""
    seed_lower = _clean_whitespace(seed_query).lower()
    filtered: list[str] = []
    for item in _dedupe_preserve_order(suggestions):
        low = item.lower()
        has_noise = False
        for noise in NOISE_AUTOCOMPLETE_TOKENS:
            if noise in seed_lower:
                continue
            if re.search(rf"\b{re.escape(noise)}\b", low):
                has_noise = True
                break
        if not has_noise:
            filtered.append(item)
    return filtered


@functools.lru_cache(maxsize=4)
def _load_bank_cached(resolved_path: str) -> dict[str, Any]:
    path = Path(resolved_path)
    if not path.is_file():
        return {"schema_version": "1.0.0", "topics": []}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict) and isinstance(payload.get("topics"), list):
            return payload
    except (OSError, json.JSONDecodeError):
        pass
    return {"schema_version": "1.0.0", "topics": []}


def load_search_seo_keyword_bank(bank_path: Path | None = None) -> dict[str, Any]:
    """Load the curated North American neuroscience/psychology search keyword bank."""
    target = Path(bank_path) if bank_path is not None else DEFAULT_KEYWORD_BANK_PATH
    return _load_bank_cached(str(target.resolve()))


def clear_keyword_bank_cache() -> None:
    """Clear the in-memory keyword bank cache (useful after regenerating bank files)."""
    _load_bank_cached.cache_clear()


def _offline_autocomplete_fallback(
    seed_query: str,
    *,
    source: str = "youtube",
    bank_path: Path | None = None,
) -> list[str]:
    """Deterministic offline fallback when public suggest HTTP is unreachable."""
    clean_seed = _clean_whitespace(seed_query).lower()
    if not clean_seed:
        return []

    bank = load_search_seo_keyword_bank(bank_path)
    seed_stems = set(extract_core_keyword_tokens(clean_seed))

    best_entry: dict[str, Any] | None = None
    best_score = 0
    for entry in bank.get("topics", []):
        pk = str(entry.get("primary_keyword", "")).lower()
        aliases = [str(a).lower() for a in entry.get("aliases", [])]
        pk_stems = set(extract_core_keyword_tokens(pk))
        score = 0
        if clean_seed == pk or clean_seed in aliases:
            score += 120
        elif pk and (pk in clean_seed or clean_seed in pk):
            score += 80
        elif any(len(a) >= 6 and a in clean_seed for a in aliases):
            score += 70

        entry_stems = set(pk_stems)
        for alias in aliases:
            entry_stems.update(extract_core_keyword_tokens(alias))
        overlap = len(seed_stems & entry_stems)
        pk_overlap = len(seed_stems & pk_stems)
        if score == 0:
            # Require strong multi-token identity + primary_keyword overlap when no phrase matched
            if overlap >= 2 and pk_overlap >= 1 and (overlap / max(1, len(seed_stems))) >= 0.66:
                score += overlap * 20
        else:
            score += overlap * 15

        if score > best_score:
            best_score = score
            best_entry = entry

    if best_entry is not None and best_score >= 40:
        yt_list = list(best_entry.get("youtube_suggestions", []))
        web_list = list(best_entry.get("web_suggestions", []))
        lt_list = list(best_entry.get("longtail_queries", []))
        if source in ("youtube", "yt"):
            merged = yt_list + lt_list + web_list
        elif source in ("web", "google"):
            merged = web_list + lt_list + yt_list
        else:
            merged = yt_list + web_list + lt_list
        deduped = _dedupe_preserve_order(merged)
        if deduped:
            return deduped[:10]

    return _dedupe_preserve_order(
        [
            clean_seed,
            f"{clean_seed} explained",
            f"what causes {clean_seed}",
            f"{clean_seed} brain",
            f"{clean_seed} psychology",
        ]
    )


def _fetch_opensearch_suggestions(
    seed_query: str,
    *,
    ds: str,
    timeout_sec: float,
) -> list[str]:
    params: dict[str, str] = {
        "client": "firefox",
        "hl": "en",
        "gl": "us",
        "q": seed_query,
    }
    if ds:
        params["ds"] = ds
    url = f"{GOOGLE_SUGGEST_ENDPOINT}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers=PUBLIC_SUGGEST_HEADERS, method="GET")
    with urllib.request.urlopen(req, timeout=max(0.5, float(timeout_sec))) as resp:
        raw_bytes = resp.read()
    payload = json.loads(raw_bytes.decode("utf-8", errors="replace"))
    if not isinstance(payload, list) or len(payload) < 2 or not isinstance(payload[1], list):
        raise ValueError("Invalid OpenSearch autocomplete payload shape")
    return _dedupe_preserve_order([str(item) for item in payload[1] if isinstance(item, str)])


def fetch_public_us_autocomplete(
    seed_query: str,
    *,
    source: str = "youtube",
    timeout_sec: float = 6.0,
) -> list[str]:
    """
    Query zero-login US English (`hl=en`, `gl=us`) public search autocomplete.

    Args:
        seed_query: Seed topic or search phrase (e.g., `"capgras delusion"`).
        source: `"youtube"` (`ds=yt`), `"web"` / `"google"`, or `"both"`.
        timeout_sec: Socket timeout in seconds.

    Returns:
        Ordered list of real North American viewer search suggestions, or a
        deterministic local fallback list if offline / unreachable.
    """
    clean_seed = _clean_whitespace(seed_query)
    if not clean_seed:
        return []

    src = (source or "youtube").strip().lower()
    if src in ("youtube", "yt"):
        ds_targets = ("yt",)
    elif src in ("web", "google"):
        ds_targets = ("",)
    elif src in ("both", "all"):
        ds_targets = ("yt", "")
    else:
        raise ValueError(
            f"Unsupported autocomplete source {source!r}; expected 'youtube', 'web', or 'both'."
        )

    collected: list[str] = []
    for ds in ds_targets:
        try:
            remote_items = _fetch_opensearch_suggestions(
                clean_seed,
                ds=ds,
                timeout_sec=timeout_sec,
            )
            collected.extend(remote_items)
        except (urllib.error.URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError):
            continue

    deduped = _dedupe_preserve_order(collected)
    if deduped:
        return deduped
    return _offline_autocomplete_fallback(clean_seed, source=src)


def _score_bank_entry(
    entry: dict[str, Any],
    *,
    query_norm: str,
    query_raw_slug: str,
    query_stems: set[str],
    pillar_norm: str,
) -> int:
    score = 0
    phrase_hit = False
    topic_id = str(entry.get("topic_id", "")).strip().lower()
    dossier_slug = str(entry.get("dossier_slug", "")).strip().lower()
    pk = _normalize_phrase(str(entry.get("primary_keyword", "")))
    aliases = [_normalize_phrase(str(a)) for a in entry.get("aliases", [])]

    if query_raw_slug and query_raw_slug in (topic_id, dossier_slug):
        score += 120
        phrase_hit = True
    elif topic_id and topic_id.replace("_", " ") in query_norm:
        score += 95
        phrase_hit = True
    elif dossier_slug and dossier_slug.replace("_", " ") in query_norm:
        score += 95
        phrase_hit = True

    if pk and pk in query_norm:
        score += 80
        phrase_hit = True

    for alias in aliases:
        if len(alias) >= 5 and alias in query_norm:
            score += 60
            phrase_hit = True

    pk_stems = set(extract_core_keyword_tokens(pk))
    entry_stems: set[str] = set(pk_stems)
    entry_stems.update(extract_core_keyword_tokens(topic_id.replace("_", " ")))
    entry_stems.update(extract_core_keyword_tokens(dossier_slug.replace("_", " ")))
    for alias in aliases:
        entry_stems.update(extract_core_keyword_tokens(alias))

    generic_neuro = {
        "brain",
        "syndrome",
        "effect",
        "disorder",
        "delusion",
        "memory",
        "mind",
        "test",
        "experiment",
        "cortical",
        "neural",
        "sensory",
        "motor",
        "visual",
        "blindness",
        "sleep",
        "pain",
        "fear",
        "speech",
    }
    shared = query_stems & entry_stems
    distinctive_hits = sum(1 for st in shared if st not in generic_neuro)
    pk_hits = len(query_stems & pk_stems)

    if not phrase_hit:
        # Without an explicit phrase/alias hit, require distinctive entity overlap
        # plus coverage of the entry's primary keyword stems to prevent cross-syndrome drift.
        if distinctive_hits == 0 or (len(shared) < 2) or (pk_hits == 0 and distinctive_hits < 2):
            return 0

    for stem in shared:
        score += 6 if stem in generic_neuro else 20

    if score > 0 and pillar_norm and str(entry.get("pillar", "")).strip().lower() == pillar_norm:
        score += 6
    return score


def _build_heuristic_keyword_bundle(
    topic: str,
    title: str = "",
    pillar: str = "",
) -> dict[str, Any]:
    raw_source = _clean_whitespace(topic) or _clean_whitespace(title) or "brain perception paradox"
    raw_words = [
        tok.lower().replace("'", "")
        for tok in _WORD_RE.findall(raw_source.replace("_", " "))
        if tok.lower().replace("'", "") not in _STOPWORDS
    ]
    dedup_words: list[str] = []
    seen_stems: set[str] = set()
    for w in raw_words:
        st = _stem_token(w)
        if st and st not in seen_stems:
            seen_stems.add(st)
            dedup_words.append(w)

    if not dedup_words:
        dedup_words = ["brain", "perception", "paradox"]
    elif len(dedup_words) == 1:
        extra = "circuit" if dedup_words[0] == "brain" else "brain"
        dedup_words = [dedup_words[0], extra]

    kw_words = dedup_words[:4]  # 2..4 words guarantees 3..4 word cover fit
    primary_keyword = " ".join(kw_words)

    if len(kw_words) == 2:
        cover_words = ["THE", kw_words[0].upper(), kw_words[1].upper()]
    else:
        cover_words = [w.upper() for w in kw_words[:4]]
    cover_badge_phrase = " ".join(cover_words)

    spoken_hook_clause = f"Neuroscientists call this hidden neural phenomenon {primary_keyword}."
    caption_lead_question = (
        f"What causes {primary_keyword} to quietly override human perception in seconds?"
    )
    resolved_pillar = pillar.strip().lower() if pillar.strip().lower() in SEVEN_PILLARS else "brain_mysteries"
    compact_tag = "#" + "".join(re.sub(r"[^a-z0-9]", "", w) for w in kw_words[:3])

    return {
        "primary_keyword": primary_keyword,
        "spoken_hook_clause": spoken_hook_clause,
        "cover_badge_phrase": cover_badge_phrase,
        "caption_lead_question": caption_lead_question,
        "pillar": resolved_pillar,
        "matched_topic_id": "heuristic_fallback",
        "dossier_slug": "",
        "longtail_queries": [
            primary_keyword,
            f"{primary_keyword} explained",
            f"what causes {primary_keyword}",
            f"{primary_keyword} psychology",
        ],
        "seo_hashtags": [compact_tag, "#neuroscience", "#brainfacts", "#psychology"],
    }


def select_episode_primary_search_keyword(
    topic: str,
    title: str = "",
    pillar: str = "",
    *,
    bank_path: Path | None = None,
) -> dict[str, Any]:
    """
    Select the optimal North American 3-point search SEO bundle for an episode.

    Returns a dictionary containing:
      - `primary_keyword` (2-5 words core viewer search term)
      - `spoken_hook_clause` (natural S1/S2 opening narration clause)
      - `cover_badge_phrase` (3-4 words uppercase cover badge text)
      - `caption_lead_question` (search-indexed opening `?` sentence for captions)
      - `pillar`, `matched_topic_id`, `dossier_slug`, `longtail_queries`, `seo_hashtags`
    """
    combined = f"{topic or ''} {title or ''}".strip()
    if not combined:
        return _build_heuristic_keyword_bundle("brain perception paradox", title=title, pillar=pillar)

    raw_slug = re.sub(r"[^a-z0-9_]+", "_", (topic or "").strip().lower()).strip("_")
    query_norm = _normalize_phrase(combined.replace("_", " "))
    query_stems = set(extract_core_keyword_tokens(combined.replace("_", " ")))
    pillar_norm = (pillar or "").strip().lower()

    bank = load_search_seo_keyword_bank(bank_path)
    best_entry: dict[str, Any] | None = None
    best_score = 0
    for entry in bank.get("topics", []):
        sc = _score_bank_entry(
            entry,
            query_norm=query_norm,
            query_raw_slug=raw_slug,
            query_stems=query_stems,
            pillar_norm=pillar_norm,
        )
        if sc > best_score:
            best_score = sc
            best_entry = entry

    if best_entry is not None and best_score >= 38:
        return {
            "primary_keyword": str(best_entry["primary_keyword"]),
            "spoken_hook_clause": str(best_entry["spoken_hook_clause"]),
            "cover_badge_phrase": str(best_entry["cover_badge_phrase"]),
            "caption_lead_question": str(best_entry["caption_lead_question"]),
            "pillar": str(best_entry.get("pillar") or pillar_norm or "brain_mysteries"),
            "matched_topic_id": str(best_entry.get("topic_id", "")),
            "dossier_slug": str(best_entry.get("dossier_slug", "")),
            "longtail_queries": list(best_entry.get("longtail_queries", [])),
            "seo_hashtags": list(best_entry.get("seo_hashtags", [])),
        }

    return _build_heuristic_keyword_bundle(topic, title=title, pillar=pillar)


def _extract_caption_lead_region(caption_text: str) -> str:
    """Extract the top search-indexed lead portion of a caption (prior to trailing hashtag wall)."""
    cleaned = (caption_text or "").strip()
    if not cleaned:
        return ""
    lines = [ln.strip() for ln in cleaned.splitlines() if ln.strip()]
    non_tag_lines: list[str] = []
    for ln in lines:
        tokens = ln.split()
        if tokens and all(tok.startswith("#") for tok in tokens):
            break
        non_tag_lines.append(ln)
        if len(" ".join(non_tag_lines)) >= 240:
            break
    lead_block = " ".join(non_tag_lines) if non_tag_lines else lines[0]
    return lead_block[:260]


def _surface_contains_keyword(surface_text: str, primary_keyword: str, core_tokens: list[str]) -> bool:
    if not surface_text or not core_tokens:
        return False
    norm_surface = _normalize_phrase(surface_text)
    norm_kw = _normalize_phrase(primary_keyword)
    if norm_kw and norm_kw in norm_surface:
        return True

    surface_stems = set(extract_core_keyword_tokens(surface_text))
    matched_count = sum(1 for st in core_tokens if st in surface_stems)
    if len(core_tokens) <= 2:
        return matched_count == len(core_tokens)
    required = max(2, math.ceil(len(core_tokens) * 0.75))
    if len(core_tokens) >= 4:
        required = min(required, 3)  # allows 3-4 word cover badges to match 4-5 word phrases
    return matched_count >= required


def _find_banned_hashtags(*texts: str) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()
    for txt in texts:
        for match in _HASHTAG_RE.finditer(txt or ""):
            tag = match.group(1).lower()
            if tag in BANNED_GENERIC_HASHTAGS and tag not in seen:
                seen.add(tag)
                found.append(tag)
    return found


def validate_three_point_seo_alignment(
    *,
    primary_keyword: str,
    spoken_intro_text: str,
    cover_text: str,
    caption_text: str,
) -> dict[str, Any]:
    """
    Validate 3-point search SEO alignment across:
      1. `spoken_intro` (first ~3s spoken cold-open `S1`/`S2` script)
      2. `cover` (first-frame / 9:16 cover text)
      3. `caption_lead` (opening lead sentence of caption body)
    and enforce zero generic spam hashtags (`#fyp`, `#foryou`, `#viral`, etc.).
    """
    clean_kw = _clean_whitespace(primary_keyword).lower()
    core_tokens = extract_core_keyword_tokens(clean_kw)

    caption_lead = _extract_caption_lead_region(caption_text)
    spoken_ok = _surface_contains_keyword(spoken_intro_text, clean_kw, core_tokens)
    cover_ok = _surface_contains_keyword(cover_text, clean_kw, core_tokens)
    caption_ok = _surface_contains_keyword(caption_lead, clean_kw, core_tokens)

    surface_matches = {
        "spoken_intro": spoken_ok,
        "cover": cover_ok,
        "caption_lead": caption_ok,
    }
    missing_surfaces = [name for name, ok in surface_matches.items() if not ok]
    score = sum(1 for ok in surface_matches.values() if ok)

    banned_found = _find_banned_hashtags(caption_text, cover_text, spoken_intro_text)
    has_banned = bool(banned_found)
    aligned = bool(core_tokens) and score == 3

    return {
        "primary_keyword": clean_kw,
        "core_tokens": core_tokens,
        "score": score,
        "max_score": 3,
        "surface_matches": surface_matches,
        "missing_surfaces": missing_surfaces,
        "banned_hashtags_found": banned_found,
        "has_banned_hashtags": has_banned,
        "aligned": aligned,
        "passed": aligned and not has_banned,
    }
