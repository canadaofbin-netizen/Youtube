"""
Unit tests for `pipeline.search_seo_autocomplete` and schema/integrity tests
for `.agents/research/search_seo_keyword_bank.json` & `.md`.
"""

from __future__ import annotations

import ast
import io
import json
from pathlib import Path
import urllib.error
import urllib.parse

import pytest

from pipeline import search_seo_autocomplete as seo
from pipeline.search_seo_autocomplete import (
    DEFAULT_KEYWORD_BANK_PATH,
    REPO_ROOT,
    SEVEN_PILLARS,
    fetch_public_us_autocomplete,
    filter_neuro_relevant_suggestions,
    load_search_seo_keyword_bank,
    select_episode_primary_search_keyword,
    validate_three_point_seo_alignment,
)


class _FakeHTTPResponse:
    def __init__(self, payload_bytes: bytes) -> None:
        self._stream = io.BytesIO(payload_bytes)

    def read(self) -> bytes:
        return self._stream.read()

    def __enter__(self) -> "_FakeHTTPResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


def test_module_uses_stdlib_http_only_zero_cdp_or_browser() -> None:
    """Ensure zero browser/CDP (`9222`) or `tiktokstudio` scraping exists in module."""
    src_path = Path(seo.__file__).resolve()
    source_text = src_path.read_text(encoding="utf-8")
    tree = ast.parse(source_text)

    imported_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported_names.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_names.add(node.module.split(".")[0])

    forbidden_imports = {"playwright", "selenium", "websocket", "websockets", "pyppeteer"}
    assert imported_names.isdisjoint(forbidden_imports)
    assert "9222" not in source_text
    assert "leased_cdp_tab" not in source_text


def test_fetch_public_us_autocomplete_parses_youtube_and_web(monkeypatch: pytest.MonkeyPatch) -> None:
    captured_urls: list[str] = []

    def fake_urlopen(req, timeout: float = 6.0):
        url = req.full_url if hasattr(req, "full_url") else str(req)
        captured_urls.append(url)
        parsed = urllib.parse.urlparse(url)
        qs = urllib.parse.parse_qs(parsed.query)
        assert qs.get("client") == ["firefox"]
        assert qs.get("hl") == ["en"]
        assert qs.get("gl") == ["us"]

        if qs.get("ds") == ["yt"]:
            body = json.dumps(
                [
                    "capgras delusion",
                    [
                        "capgras delusion",
                        "  Capgras Delusion Patient  ",
                        "<b>capgras delusion</b> explained",
                        "capgras delusion patient",
                    ],
                ]
            ).encode("utf-8")
        else:
            body = json.dumps(
                [
                    "capgras delusion",
                    [
                        "capgras delusion",
                        "capgras delusion cause",
                        "capgras delusion treatment",
                    ],
                ]
            ).encode("utf-8")
        return _FakeHTTPResponse(body)

    monkeypatch.setattr(seo.urllib.request, "urlopen", fake_urlopen)

    yt_res = fetch_public_us_autocomplete("capgras delusion", source="youtube", timeout_sec=4.0)
    assert yt_res == [
        "capgras delusion",
        "Capgras Delusion Patient",
        "capgras delusion explained",
    ]
    assert any("ds=yt" in u for u in captured_urls)

    captured_urls.clear()
    web_res = fetch_public_us_autocomplete("capgras delusion", source="web", timeout_sec=4.0)
    assert web_res == [
        "capgras delusion",
        "capgras delusion cause",
        "capgras delusion treatment",
    ]
    assert all("ds=yt" not in u for u in captured_urls)

    both_res = fetch_public_us_autocomplete("capgras delusion", source="both", timeout_sec=4.0)
    assert both_res == [
        "capgras delusion",
        "Capgras Delusion Patient",
        "capgras delusion explained",
        "capgras delusion cause",
        "capgras delusion treatment",
    ]


def test_fetch_public_us_autocomplete_deterministic_offline_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def raise_offline(req, timeout: float = 6.0):
        raise urllib.error.URLError("simulated network offline")

    monkeypatch.setattr(seo.urllib.request, "urlopen", raise_offline)

    known_first = fetch_public_us_autocomplete("capgras delusion", source="youtube")
    known_second = fetch_public_us_autocomplete("capgras delusion", source="youtube")
    assert known_first == known_second
    assert len(known_first) >= 3
    assert any("capgras" in q.lower() for q in known_first)

    unseen_first = fetch_public_us_autocomplete("cortical spreading aura", source="web")
    unseen_second = fetch_public_us_autocomplete("cortical spreading aura", source="web")
    assert unseen_first == unseen_second
    assert unseen_first[0] == "cortical spreading aura"
    assert "cortical spreading aura explained" in unseen_first

    assert fetch_public_us_autocomplete("   ") == []


def test_fetch_public_us_autocomplete_invalid_source_raises() -> None:
    with pytest.raises(ValueError, match="Unsupported autocomplete source"):
        fetch_public_us_autocomplete("capgras delusion", source="tiktok_private")


def test_filter_neuro_relevant_suggestions_removes_gaming_noise() -> None:
    raw = [
        "capgras delusion",
        "capgras delusion roblox",
        "capgras delusion patient",
        "capgras delusion fortnite meme",
        "capgras delusion explained",
    ]
    cleaned = filter_neuro_relevant_suggestions(raw, seed_query="capgras delusion")
    assert cleaned == [
        "capgras delusion",
        "capgras delusion patient",
        "capgras delusion explained",
    ]


def test_select_episode_primary_search_keyword_bank_and_heuristic() -> None:
    capgras = select_episode_primary_search_keyword(
        topic="capgras_imposter_delusion",
        title="He Swore His Mother Was Replaced Overnight",
        pillar="brain_mysteries",
    )
    assert capgras["primary_keyword"] == "capgras delusion"
    assert 3 <= len(capgras["cover_badge_phrase"].split()) <= 4
    assert capgras["caption_lead_question"].endswith("?")
    assert capgras["matched_topic_id"] == "capgras_delusion"

    sleep_par = select_episode_primary_search_keyword(
        topic="REM Atonia Waking Up Paralyzed",
        pillar="brain_health",
    )
    assert sleep_par["primary_keyword"] == "sleep paralysis demon"

    phantom = select_episode_primary_search_keyword(
        topic="Ramachandran Mirror Therapy Missing Arm",
        pillar="brain_mysteries",
    )
    assert phantom["primary_keyword"] == "phantom limb pain"

    # Unseen topic deterministic synthesis + guaranteed 3-point SEO alignment
    unseen = select_episode_primary_search_keyword(
        topic="Anton Babinski Cortical Blindness Denial",
        pillar="brain_mysteries",
    )
    assert unseen["matched_topic_id"] == "heuristic_fallback"
    assert 2 <= len(unseen["primary_keyword"].split()) <= 5
    assert 3 <= len(unseen["cover_badge_phrase"].split()) <= 4
    assert unseen["caption_lead_question"].endswith("?")

    check = validate_three_point_seo_alignment(
        primary_keyword=unseen["primary_keyword"],
        spoken_intro_text=unseen["spoken_hook_clause"],
        cover_text=unseen["cover_badge_phrase"],
        caption_text=unseen["caption_lead_question"] + "\n\n" + " ".join(unseen["seo_hashtags"]),
    )
    assert check["score"] == 3
    assert check["passed"] is True


def test_validate_three_point_seo_alignment_scoring_and_banned_tags() -> None:
    perfect = validate_three_point_seo_alignment(
        primary_keyword="capgras delusion",
        spoken_intro_text="Doctors call this terrifying brain short-circuit the Capgras delusion.",
        cover_text="THE CAPGRAS DELUSION",
        caption_text=(
            "What causes Capgras delusion to convince a healthy brain that family members are imposters?\n\n"
            "#capgrasdelusion #neuroscience #brainfacts"
        ),
    )
    assert perfect["score"] == 3
    assert perfect["missing_surfaces"] == []
    assert perfect["has_banned_hashtags"] is False
    assert perfect["passed"] is True

    missing_two = validate_three_point_seo_alignment(
        primary_keyword="phantom limb pain",
        spoken_intro_text="He lost his arm ten years ago, yet his fingers still clenched.",
        cover_text="PHANTOM LIMB PAIN",
        caption_text="Why did a wooden box with a cheap mirror stop the agony?\n\n#phantomlimbpain #neuroscience",
    )
    assert missing_two["score"] == 1
    assert set(missing_two["missing_surfaces"]) == {"spoken_intro", "caption_lead"}
    assert missing_two["passed"] is False

    banned_tag_case = validate_three_point_seo_alignment(
        primary_keyword="sleep paralysis demon",
        spoken_intro_text="That shadowy sleep paralysis demon is your dreaming brain waking early.",
        cover_text="SLEEP PARALYSIS DEMON",
        caption_text="Why do you see a sleep paralysis demon in bed? #sleepparalysis #FYP #viral #foryou",
    )
    assert banned_tag_case["score"] == 3
    assert banned_tag_case["aligned"] is True
    assert banned_tag_case["has_banned_hashtags"] is True
    assert set(banned_tag_case["banned_hashtags_found"]) == {"#fyp", "#viral", "#foryou"}
    assert banned_tag_case["passed"] is False


def test_generated_keyword_bank_schema_and_35_plus_topics_integrity() -> None:
    md_path = REPO_ROOT / ".agents" / "research" / "search_seo_keyword_bank.md"
    assert DEFAULT_KEYWORD_BANK_PATH.is_file(), f"Missing {DEFAULT_KEYWORD_BANK_PATH}"
    assert md_path.is_file(), f"Missing {md_path}"
    assert md_path.stat().st_size > 2000

    bank = load_search_seo_keyword_bank(DEFAULT_KEYWORD_BANK_PATH)
    topics = bank.get("topics", [])
    assert len(topics) >= 35, f"Expected >= 35 topics, got {len(topics)}"

    seen_ids: set[str] = set()
    seen_keywords: set[str] = set()
    pillars_seen: set[str] = set()

    for entry in topics:
        tid = entry["topic_id"]
        pk = entry["primary_keyword"]
        pillar = entry["pillar"]

        assert tid not in seen_ids, f"Duplicate topic_id: {tid}"
        assert pk not in seen_keywords, f"Duplicate primary_keyword: {pk}"
        seen_ids.add(tid)
        seen_keywords.add(pk)
        assert pillar in SEVEN_PILLARS
        pillars_seen.add(pillar)

        assert 2 <= len(pk.split()) <= 5, f"{tid} primary_keyword word count out of range: {pk}"
        assert 3 <= len(entry["cover_badge_phrase"].split()) <= 4, f"{tid} cover_badge_phrase out of range"
        assert entry["caption_lead_question"].endswith("?")
        assert isinstance(entry["longtail_queries"], list) and len(entry["longtail_queries"]) >= 2

        alignment = validate_three_point_seo_alignment(
            primary_keyword=pk,
            spoken_intro_text=entry["spoken_hook_clause"],
            cover_text=entry["cover_badge_phrase"],
            caption_text=entry["caption_lead_question"] + "\n\n" + " ".join(entry["seo_hashtags"]),
        )
        assert alignment["passed"] is True, f"Bank entry failed 3-point SEO gate: {tid} -> {alignment}"

    assert pillars_seen == set(SEVEN_PILLARS)
    assert "capgras delusion" in seen_keywords
