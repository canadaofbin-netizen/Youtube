from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any
import pytest

import pipeline.studio.tiktok_uploader as tk_mod
from pipeline.studio.tiktok_uploader import (
    DEFAULT_TIKTOK_BIO_CANDIDATES,
    DEFAULT_TIKTOK_DISPLAY_NAME,
    DEFAULT_TIKTOK_HANDLE_CANDIDATES,
    DEFAULT_TIKTOK_HASHTAGS,
    TIKTOK_BIO_MAX_UTF16_UNITS,
    build_tiktok_caption,
    configure_tiktok_profile_cdp,
    detect_tiktok_birthday_gate,
    detect_tiktok_captcha,
    find_child_google_oauth_targets,
    select_tiktok_bio,
    utf16_code_units,
    validate_tiktok_username_candidate,
)


def test_default_tiktok_handles_and_bio_fit_platform_limits() -> None:
    assert DEFAULT_TIKTOK_DISPLAY_NAME == "ALL ABOUT BRAIN"
    assert DEFAULT_TIKTOK_HANDLE_CANDIDATES[0] == "allaboutbrain.official"
    for cand in DEFAULT_TIKTOK_HANDLE_CANDIDATES:
        cleaned = validate_tiktok_username_candidate(cand)
        assert len(cleaned) <= 24

    bio = select_tiktok_bio(DEFAULT_TIKTOK_BIO_CANDIDATES)
    assert len(bio) <= TIKTOK_BIO_MAX_UTF16_UNITS
    assert utf16_code_units(bio) <= TIKTOK_BIO_MAX_UTF16_UNITS
    assert "DOI verified" in bio
    assert "YouTube" in bio


def test_select_tiktok_bio_falls_back_when_primary_exceeds_utf16_limit() -> None:
    overlong = "🧠" * 45  # 90 UTF-16 code units (> 80)
    fallback = "🧠 Weirdest true brain & psych studies (DOI verified)"
    selected = select_tiktok_bio([overlong, fallback], max_utf16_units=80)
    assert selected == fallback
    assert utf16_code_units(selected) <= 80


def test_validate_tiktok_username_candidate_rejects_invalid_handles() -> None:
    with pytest.raises(ValueError, match="exceeds 24 chars"):
        validate_tiktok_username_candidate("allaboutbrain_official_channel_too_long")
    with pytest.raises(ValueError, match="cannot end with a period"):
        validate_tiktok_username_candidate("allaboutbrain.")
    with pytest.raises(ValueError, match="disallowed characters"):
        validate_tiktok_username_candidate("all-about-brain!")


def test_build_tiktok_caption_marshmallow_inaugural_contract() -> None:
    caption = build_tiktok_caption(
        hook_question="Why did kids eat the marshmallow 4x faster right after an adult lied to them? 🧠🍬",
        story_summary=(
            "At the University of Rochester, psychologists ran the classic marshmallow test with one twist: "
            "half the kids watched the researcher break a promise about bringing a new set of crayons first. "
            "Kids with a reliable adult waited 12 minutes — kids who got lied to gave up in 3 minutes. "
            'What looks like "weak willpower" is often a smart brain adapting to broken trust.'
        ),
        debate_question="Would you wait 15 minutes if you didn't trust the promise? 👇",
        citation_line="Kidd, Palmeri & Aslin (2013), Cognition",
        doi="https://doi.org/10.1016/j.cognition.2012.08.004",
        hashtags=DEFAULT_TIKTOK_HASHTAGS,
    )
    blocks = [b.strip() for b in caption.split("\n\n") if b.strip()]
    assert len(blocks) == 5
    assert blocks[0] == "Why did kids eat the marshmallow 4x faster right after an adult lied to them? 🧠🍬"
    assert "University of Rochester" in blocks[1]
    assert blocks[2] == "Would you wait 15 minutes if you didn't trust the promise? 👇"
    assert blocks[3] == "📄 Study: Kidd, Palmeri & Aslin (2013), Cognition · DOI: 10.1016/j.cognition.2012.08.004"
    assert blocks[4] == "#neuroscience #psychology #brainfacts #humanbehavior #learnontiktok"
    assert len(caption) <= 4000


def test_build_tiktok_caption_deduplicates_and_caps_hashtags_at_five() -> None:
    caption = build_tiktok_caption(
        hook_question="Can a 5-minute bedtime list help you fall asleep faster?",
        story_summary="Writing tomorrow's tasks offloads prospective memory from the hippocampus.",
        debate_question="Do you keep a notepad by your bed?",
        citation_line="Scullin et al. (2018), JEP: General",
        doi="doi:10.1037/xge0000374",
        hashtags=["neuroscience", "#Neuroscience", "psychology", "sleep", "brainfacts", "learnontiktok", "extra"],
    )
    assert caption.splitlines()[-1].split() == [
        "#neuroscience",
        "#psychology",
        "#sleep",
        "#brainfacts",
        "#learnontiktok",
    ]


def test_detect_tiktok_captcha_and_birthday_gate() -> None:
    markers = detect_tiktok_captcha(
        "https://www.tiktok.com/login?lang=en",
        "Verify to continue\nDrag the slider to fit the puzzle",
        ["dom:#captcha-verify-container-main-page"],
    )
    assert "captcha-verify-container" in markers
    assert "drag the slider" in markers
    assert "fit the puzzle" in markers
    assert "verify to continue" in markers
    assert "dom:#captcha-verify-container-main-page" in markers
    assert detect_tiktok_captcha("https://www.tiktok.com/@allaboutbrain.official", "ALL ABOUT BRAIN") == []

    assert detect_tiktok_birthday_gate(
        "https://www.tiktok.com/signup",
        "When's your birthday? Your birthday won't be shown publicly.",
    )


def test_find_child_google_oauth_targets_enforces_exact_opener_isolation() -> None:
    targets: list[dict[str, Any]] = [
        {"id": "USER_TAB", "type": "page", "url": "https://www.tiktok.com/", "openerId": ""},
        {"id": "SIBLING_STUDIO", "type": "page", "url": "https://studio.youtube.com/", "openerId": ""},
        {
            "id": "FOREIGN_OAUTH",
            "type": "page",
            "url": "https://accounts.google.com/o/oauth2/v2/auth",
            "openerId": "OTHER_AGENT_TAB",
        },
        {
            "id": "OUR_OAUTH",
            "type": "page",
            "url": "https://accounts.google.com/o/oauth2/v2/auth?client_id=tiktok",
            "openerId": "OUR_TIKTOK_TAB",
        },
    ]
    matched = find_child_google_oauth_targets(targets, parent_target_id="OUR_TIKTOK_TAB")
    assert [t["id"] for t in matched] == ["OUR_OAUTH"]


def test_configure_tiktok_profile_cdp_halts_immediately_on_captcha(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    closed_tabs: list[str] = []

    def _fake_open(url: str, **kwargs: Any) -> dict[str, Any]:
        return {"id": "LEASED_TT_1", "url": url, "webSocketDebuggerUrl": "ws://127.0.0.1:9222/devtools/page/LEASED_TT_1"}

    def _fake_close(tid: str, **kwargs: Any) -> bool:
        closed_tabs.append(tid)
        return True

    class _FakeClient:
        def __init__(self, ws_url: str) -> None:
            self.ws_url = ws_url

        async def __aenter__(self) -> "_FakeClient":
            return self

        async def __aexit__(self, *args: Any) -> None:
            return None

        async def send(self, method: str, params: dict[str, Any] | None = None, timeout_sec: float = 10.0) -> dict[str, Any]:
            if method == "Page.captureScreenshot":
                # 1x1 PNG base64
                return {
                    "data": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
                }
            return {}

        async def eval(self, expression: str, **kwargs: Any) -> Any:
            return {
                "url": "https://www.tiktok.com/profile?lang=en",
                "title": "TikTok",
                "bodyText": "Verify to continue — Drag the slider to fit the puzzle",
                "domCaptcha": ["dom:.secsdk-captcha-drag-icon"],
            }

    monkeypatch.setattr(tk_mod, "open_leased_cdp_tab", _fake_open)
    monkeypatch.setattr(tk_mod, "renew_tab_lease", lambda *a, **kw: True)
    monkeypatch.setattr(tk_mod, "release_and_close_leased_tab", _fake_close)
    monkeypatch.setattr(tk_mod, "DirectCDPClient", _FakeClient)

    async def _fast_sleep(_sec: float) -> None:
        return None

    monkeypatch.setattr(tk_mod.asyncio, "sleep", _fast_sleep)

    shot_file = tmp_path / "tiktok_verification_needed.png"
    res = asyncio.run(
        configure_tiktok_profile_cdp(
            verification_screenshot_path=shot_file,
            close_tab_on_finish=True,
        )
    )
    assert res["status"] == "captcha_verification_needed"
    assert res["target_id"] == "LEASED_TT_1"
    assert shot_file.exists()
    # Tab MUST remain open for user inspection when CAPTCHA appears
    assert closed_tabs == []
