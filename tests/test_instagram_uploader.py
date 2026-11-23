from __future__ import annotations

import os
from pathlib import Path
import pytest

from pipeline.studio.instagram_uploader import (
    DEFAULT_REELS_HASHTAGS,
    DEFAULT_US_BIO,
    build_instagram_reels_caption,
    detect_challenge_markers,
    detect_datacenter_rate_limit,
    load_instagram_credentials,
)


def test_load_instagram_credentials_reads_env_and_enforces_0600(tmp_path: Path) -> None:
    env_file = tmp_path / "instagram.env"
    env_file.write_text(
        "# Local isolated secret test\nIG_USERNAME=sample_creator\nIG_PASSWORD=placeholder_secret_token\n",
        encoding="utf-8",
    )
    os.chmod(env_file, 0o644)

    creds = load_instagram_credentials(env_file)
    assert creds == {
        "username": "sample_creator",
        "password": "placeholder_secret_token",
    }
    if os.name != "nt":
        assert (env_file.stat().st_mode & 0o777) == 0o600


def test_load_instagram_credentials_optional_graph_api_fields(tmp_path: Path) -> None:
    env_file = tmp_path / "instagram.env"
    env_file.write_text(
        "IG_USERNAME=sample_creator\nIG_PASSWORD=placeholder_secret_token\n"
        "IG_USER_ID=17841400000000\nIG_ACCESS_TOKEN=IGQW_sample_token\n",
        encoding="utf-8",
    )
    creds = load_instagram_credentials(env_file)
    assert creds["user_id"] == "17841400000000"
    assert creds["access_token"] == "IGQW_sample_token"


def test_load_instagram_credentials_rejects_missing_fields(tmp_path: Path) -> None:
    env_file = tmp_path / "instagram.env"
    env_file.write_text("IG_USERNAME=only_user\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Missing non-empty IG_USERNAME or IG_PASSWORD"):
        load_instagram_credentials(env_file)

    with pytest.raises(FileNotFoundError):
        load_instagram_credentials(tmp_path / "does_not_exist.env")


def test_build_instagram_reels_caption_marshmallow_contract() -> None:
    caption = build_instagram_reels_caption(
        hook_question="Why did kids eat the marshmallow 4x faster after ONE broken promise? 🧠",
        mechanism_summary=(
            "Eating early was never weak willpower — it was smart survival math inside an unreliable room. "
            "When trust breaks, your brain's reward center (the nucleus accumbens) fires urgent signals to grab "
            "the sure thing now instead of waiting on an empty promise."
        ),
        debate_question="When your habits slip at night, is the real culprit weak willpower — or broken self-trust?",
        citation_line="Celeste Kidd, Holly Palmeri & Richard N. Aslin (2013), Cognition",
        doi="https://doi.org/10.1016/j.cognition.2012.08.004",
        hashtags=DEFAULT_REELS_HASHTAGS,
    )
    lines = [blk.strip() for blk in caption.split("\n\n") if blk.strip()]
    assert len(lines) == 6
    assert lines[0].startswith("Why did kids eat the marshmallow 4x faster")
    assert "nucleus accumbens" in lines[1]
    assert "broken self-trust?" in lines[2]
    assert "Save this for later" in lines[3]
    assert "DOI: 10.1016/j.cognition.2012.08.004" in lines[4]
    assert lines[5] == "#neuroscience #psychology #brainfacts #selfcontrol #humanbehavior"
    assert len(caption) <= 2200


def test_build_instagram_reels_caption_caps_hashtags_at_five() -> None:
    caption = build_instagram_reels_caption(
        hook_question="Can 5 minutes of writing beat sleeping pills?",
        mechanism_summary="Offloading unfinished tasks quiets prospective memory loops.",
        debate_question="Do you write a to-do list before bed?",
        citation_line="Scullin et al. (2018), JEP: General",
        doi="10.1037/xge0000374",
        hashtags=["neuroscience", "#psychology", "sleep", "brain", "habits", "extra_six", "extra_seven"],
    )
    tag_line = caption.splitlines()[-1]
    assert tag_line.split() == ["#neuroscience", "#psychology", "#sleep", "#brain", "#habits"]


def test_detect_challenge_and_datacenter_rate_limit_markers() -> None:
    assert detect_challenge_markers(
        "https://www.instagram.com/accounts/login/two_factor?next=%2F",
        "Enter the 6-digit security code sent to your email.",
    )
    assert detect_datacenter_rate_limit(
        "https://www.instagram.com/?hl=en",
        "The login information you entered is incorrect.",
        ['{"errors":[{"message":"Rate limit exceeded","severity":"CRITICAL","code":1675004}]}'],
    )
    assert detect_challenge_markers(
        "https://www.instagram.com/?hl=en",
        "Welcome back to Instagram",
    ) == []


def test_default_us_bio_fits_instagram_150_char_limit() -> None:
    assert len(DEFAULT_US_BIO) <= 150
    assert "DOI verified" in DEFAULT_US_BIO
    assert "YouTube" in DEFAULT_US_BIO
