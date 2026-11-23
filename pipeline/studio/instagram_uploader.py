"""
ALL ABOUT BRAIN — Standalone Instagram Reels & Creator Profile Operator
=======================================================================
Supports BOTH:
  1. Official Meta/Instagram Graph API Content Publishing (`publish_instagram_reel_graph_api` via
     `https://graph.instagram.com/v21.0/<ig_user_id>/media` — sanctioned cloud-native path that works
     reliably from Google Cloud `AS396982` server IPs without consumer web rate-limiting).
  2. Strictly isolated single-tab CDP Web automation (`configure_instagram_profile_cdp` and
     `upload_instagram_reel_cdp` on `127.0.0.1:9222` when an authenticated residential/session cookie
     is active in Naver Whale).

Concurrency & Security Invariants:
  - Credentials (`IG_USERNAME`, `IG_PASSWORD`, optional `IG_ACCESS_TOKEN`, `IG_USER_ID`) are read ONLY
    from `~/.config/aab/instagram.env` (`0600` permissions) — zero hardcoded secrets anywhere.
  - Opens at most ONE dedicated background tab via `open_leased_cdp_tab("about:blank", background=True)`
    and communicates exclusively with that `targetId` over `DirectCDPClient`.
  - Never touches, inspects, refreshes, navigates, or closes any user or sibling worker tab.
  - Halts cleanly without attempting any bypass if Instagram triggers a 2FA / security-code challenge
    or a datacenter IP edge block (`GraphQL code 1675004` / `HTTP 429`).
"""

from __future__ import annotations

import asyncio
import base64
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import re
import time
from typing import Any, Literal, Sequence
import urllib.error
import urllib.parse
import urllib.request

from PIL import Image

from pipeline.cdp_tab_lease import (
    acquire_tab_lease,
    open_leased_cdp_tab,
    release_and_close_leased_tab,
)
from pipeline.studio.config import DEFAULT_CDP_HOST, DEFAULT_CDP_PORT
from pipeline.studio.whale_session import DirectCDPClient

DEFAULT_INSTAGRAM_ENV_PATH = Path.home() / ".config" / "aab" / "instagram.env"
DEFAULT_YOUTUBE_CHANNEL_URL = "https://www.youtube.com/@AllAboutBrainOfficial"
DEFAULT_HANDLE_CANDIDATES: tuple[str, ...] = (
    "allaboutbrain.official",
    "allaboutbrainhq",
    "allaboutbrain.us",
    "allaboutbrain_official",
)
DEFAULT_US_BIO = (
    "🧠 Weirdest true experiments in neuroscience & psychology\n"
    "📄 100% peer-reviewed studies (DOI verified)\n"
    "👇 Full brain breakdowns on YouTube"
)
DEFAULT_REELS_HASHTAGS: tuple[str, ...] = (
    "#neuroscience",
    "#psychology",
    "#brainfacts",
    "#selfcontrol",
    "#humanbehavior",
)

CHALLENGE_MARKERS: tuple[str, ...] = (
    "two_factor",
    "/challenge/",
    "auth_platform/codeentry",
    "enter the code",
    "security code",
    "6-digit code",
    "enter the 6-digit",
    "check your email",
    "check your whatsapp",
    "check your text messages",
    "we detected an unusual login",
    "suspicious login",
    "confirm your info",
    "confirm it's you",
    "confirm that it's you",
    "verify your account",
    "help us confirm you own this account",
    "captcha",
    "recaptcha",
)

DATACENTER_RATE_LIMIT_MARKERS: tuple[str, ...] = (
    "1675004",
    "rate limit exceeded",
    "http error 429",
    "chrome-error://chromewebdata",
)


def load_instagram_credentials(env_path: Path | str = DEFAULT_INSTAGRAM_ENV_PATH) -> dict[str, str]:
    """
    Loads `IG_USERNAME` and `IG_PASSWORD` (plus optional `IG_ACCESS_TOKEN` / `IG_USER_ID` for Graph API)
    from `~/.config/aab/instagram.env`. Enforces `0600` permissions when owned by the current POSIX user.
    """
    p = Path(env_path).expanduser()
    if not p.exists():
        raise FileNotFoundError(f"Instagram credentials file not found: {p}")

    if os.name != "nt":
        st = p.stat()
        mode = st.st_mode & 0o777
        if st.st_uid == os.getuid() and mode != 0o600:
            os.chmod(p, 0o600)

    parsed: dict[str, str] = {}
    for raw_line in p.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        clean_val = val.strip()
        if len(clean_val) >= 2 and clean_val[0] == clean_val[-1] and clean_val[0] in ("'", '"'):
            clean_val = clean_val[1:-1]
        parsed[key.strip()] = clean_val

    username = parsed.get("IG_USERNAME", "").strip()
    password = parsed.get("IG_PASSWORD", "").strip()
    if not username or not password:
        raise ValueError(f"Missing non-empty IG_USERNAME or IG_PASSWORD in {p}")

    out: dict[str, str] = {"username": username, "password": password}
    if parsed.get("IG_ACCESS_TOKEN", "").strip():
        out["access_token"] = parsed["IG_ACCESS_TOKEN"].strip()
    if parsed.get("IG_USER_ID", "").strip():
        out["user_id"] = parsed["IG_USER_ID"].strip()
    return out


def build_instagram_reels_caption(
    *,
    hook_question: str,
    mechanism_summary: str,
    debate_question: str,
    citation_line: str,
    doi: str,
    save_cta: str = '💾 Save this for later & send it to someone who blames their "weak willpower."',
    hashtags: tuple[str, ...] | list[str] = DEFAULT_REELS_HASHTAGS,
) -> str:
    """
    Builds a high-retention US English Instagram Reels caption:
      1. Curiosity-gap hook question (`<= 125` chars visible above fold).
      2. Plain-English brain mechanism paragraph.
      3. Personal reflection / comment-debate question.
      4. Save & DM-send signal prompt.
      5. Peer-reviewed citation + `DOI` verification stamp.
      6. Up to 5 niche hashtags (`#neuroscience`, `#psychology`, ...).
    """
    h_q = hook_question.strip()
    mech = mechanism_summary.strip()
    deb = debate_question.strip()
    cit = citation_line.strip()
    clean_doi = doi.strip()
    if clean_doi.lower().startswith("https://doi.org/"):
        clean_doi = clean_doi[len("https://doi.org/") :]
    elif clean_doi.lower().startswith("doi:"):
        clean_doi = clean_doi[4:].strip()

    if not h_q or not mech or not clean_doi:
        raise ValueError("hook_question, mechanism_summary, and doi are required for Reels caption")

    norm_tags: list[str] = []
    for raw_tag in hashtags:
        t = str(raw_tag or "").strip()
        if not t:
            continue
        if not t.startswith("#"):
            t = f"#{t}"
        t_clean = "#" + re.sub(r"[^A-Za-z0-9_]", "", t[1:])
        if len(t_clean) > 1 and t_clean.lower() not in {x.lower() for x in norm_tags}:
            norm_tags.append(t_clean)
        if len(norm_tags) >= 5:
            break

    study_block = f"📄 Study: {cit} · DOI: {clean_doi}" if cit else f"📄 DOI: {clean_doi}"
    sections = [h_q, mech]
    if deb:
        sections.append(deb)
    if save_cta.strip():
        sections.append(save_cta.strip())
    sections.append(study_block)
    if norm_tags:
        sections.append(" ".join(norm_tags))

    caption = "\n\n".join(sections).strip()
    if len(caption) > 2200:
        raise ValueError(f"Instagram Reels caption exceeds 2200-char limit ({len(caption)} chars)")
    return caption


def detect_challenge_markers(url: str, body_text: str) -> list[str]:
    """Returns matched 2FA / security challenge / CAPTCHA markers if present on the page."""
    u_low = (url or "").lower()
    b_low = (body_text or "").lower()
    return [m for m in CHALLENGE_MARKERS if m in u_low or m in b_low]


def detect_datacenter_rate_limit(url: str, body_text: str, network_snippets: list[str] | None = None) -> list[str]:
    """Detects Meta GraphQL `code: 1675004` (`Rate limit exceeded`) or `HTTP 429` edge blocks on cloud IPs."""
    haystack = "\n".join(
        [
            (url or "").lower(),
            (body_text or "").lower(),
            *(s.lower() for s in (network_snippets or [])),
        ]
    )
    return [m for m in DATACENTER_RATE_LIMIT_MARKERS if m in haystack]


INSTAGRAM_RATE_LIMIT_429_MARKERS: tuple[str, ...] = (
    "http error 429",
    "this page isn't working",
    "too many requests",
    "rate limit",
)

INSTAGRAM_VIDEO_FILE_INPUT_SELECTORS: tuple[str, ...] = (
    "div[role='dialog'] input[type='file']",
    "form input[type='file']",
    "input[type='file'][accept*='video']",
)

INSTAGRAM_IMAGE_FILE_INPUT_SELECTORS: tuple[str, ...] = (
    "div[role='dialog'] input[type='file']",
    "form input[type='file']",
    "input[type='file'][accept*='image']",
)


def detect_instagram_rate_limit_429(title: str, body_text: str, url: str = "") -> str | None:
    """
    Detects Chrome/Instagram HTTP 429 rate-limit error pages immediately after navigation
    (`HTTP ERROR 429`, `This page isn't working`, `too many requests`, `rate limit`, or HTTP 429 status).
    Returns the matched reason string, or `None` on a normal Instagram page.
    """
    def _norm(val: str) -> str:
        return (val or "").replace("\u2019", "'").replace("\u2018", "'").lower()

    t_low = _norm(title)
    b_low = _norm(body_text)
    u_low = _norm(url)
    combined = f"{t_low}\n{b_low}\n{u_low}"

    for marker in INSTAGRAM_RATE_LIMIT_429_MARKERS:
        if marker in combined:
            return marker

    if re.search(r"\b(?:http(?:\s+error)?|error|status|code)\s*[:=]?\s*429\b", combined):
        return "http 429"
    if t_low.strip() == "429" or b_low.strip() == "429":
        return "429"
    if re.search(r"\b429\b", t_low) and "instagram photos" not in t_low and "@" not in t_low:
        return "429"
    if u_low.startswith("chrome-error://") and "429" in combined:
        return "http 429"
    return None


async def attach_instagram_file_input_with_polling(
    client: Any,
    file_path: Path,
    *,
    selectors: tuple[str, ...],
    timeout_sec: float = 12.0,
    poll_interval_sec: float = 0.5,
) -> tuple[bool, str]:
    """
    Polls up to `timeout_sec`, attempting `client.set_file_input(file_path, sel)` across
    `selectors` in priority order. Returns `(True, matched_selector)` immediately on success,
    or `(False, "")` if timeout elapses without attaching.
    """
    if not selectors:
        return False, ""
    eff_timeout = max(0.0, float(timeout_sec))
    eff_interval = max(0.0, float(poll_interval_sec))
    deadline = time.monotonic() + eff_timeout
    max_attempts = (
        max(1, int(math.ceil(eff_timeout / eff_interval)) + 1)
        if eff_interval > 0.0
        else 1
    )
    for attempt in range(max_attempts):
        for sel in selectors:
            if await client.set_file_input(file_path, sel):
                return True, sel
        if attempt + 1 >= max_attempts:
            break
        remaining = deadline - time.monotonic()
        if remaining <= 0.0:
            break
        await asyncio.sleep(min(eff_interval, remaining))
    return False, ""


TRIAL_REELS_MIN_FOLLOWERS: int = 1000
INSTAGRAM_CAROUSEL_MIN_SLIDES: int = 2
INSTAGRAM_CAROUSEL_MAX_SLIDES: int = 10
INSTAGRAM_CAROUSEL_MIN_ASPECT_RATIO: float = 0.80
INSTAGRAM_CAROUSEL_MAX_ASPECT_RATIO: float = 1.91
_VIDEO_EXTENSIONS: frozenset[str] = frozenset({".mp4", ".mov", ".m4v", ".webm", ".avi", ".mkv"})


def fetch_instagram_followers_count(
    *,
    ig_user_id: str,
    access_token: str,
    api_version: str = "v21.0",
) -> int:
    """Queries `GET /{ig_user_id}?fields=followers_count` via the official Instagram Graph API."""
    base = f"https://graph.instagram.com/{api_version.strip('/')}"
    qs = urllib.parse.urlencode({"fields": "followers_count", "access_token": access_token.strip()})
    with urllib.request.urlopen(f"{base}/{ig_user_id.strip()}?{qs}", timeout=20.0) as resp:
        doc = json.loads(resp.read().decode("utf-8"))
    return int(doc.get("followers_count") or 0)


def validate_instagram_carousel_slides(
    slide_paths: Sequence[Path | str] | None = None,
    *,
    slide_dimensions: Sequence[tuple[int, int]] | None = None,
) -> list[tuple[int, int]]:
    """
    Validates Instagram Carousel items BEFORE any network/browser upload:
      - `2 <= count <= 10` slides
      - Strictly static PNG/JPEG images (zero MP4/MOV video mixing to prevent audio cutoff bugs)
      - Aspect ratio `0.80 <= width / height <= 1.91` (`4:5` `1080x1350 = 0.80` passes; `3:4` `0.75` raises `ValueError`)
    """
    dims: list[tuple[int, int]] = []
    if slide_paths is not None:
        if not (INSTAGRAM_CAROUSEL_MIN_SLIDES <= len(slide_paths) <= INSTAGRAM_CAROUSEL_MAX_SLIDES):
            raise ValueError(
                f"Instagram Carousel requires {INSTAGRAM_CAROUSEL_MIN_SLIDES}..{INSTAGRAM_CAROUSEL_MAX_SLIDES} slides, got {len(slide_paths)}"
            )
        for idx, raw_p in enumerate(slide_paths, start=1):
            p = Path(raw_p)
            if p.suffix.lower() in _VIDEO_EXTENSIONS:
                raise ValueError(
                    f"Video file {p.name} forbidden in static 4:5 Instagram Carousel (slide {idx}); do not mix MP4 and PNG slides"
                )
            if not p.is_file():
                raise FileNotFoundError(f"Carousel slide {idx} missing: {p}")
            with Image.open(p) as im:
                w, h = im.size
            dims.append((int(w), int(h)))
    elif slide_dimensions is not None:
        if not (INSTAGRAM_CAROUSEL_MIN_SLIDES <= len(slide_dimensions) <= INSTAGRAM_CAROUSEL_MAX_SLIDES):
            raise ValueError(
                f"Instagram Carousel requires {INSTAGRAM_CAROUSEL_MIN_SLIDES}..{INSTAGRAM_CAROUSEL_MAX_SLIDES} slides, got {len(slide_dimensions)}"
            )
        dims = [(int(w), int(h)) for w, h in slide_dimensions]
    else:
        raise ValueError("Either slide_paths or slide_dimensions must be provided")

    for idx, (w, h) in enumerate(dims, start=1):
        if w <= 0 or h <= 0:
            raise ValueError(f"Invalid dimensions {w}x{h} on carousel slide {idx}")
        ratio = w / float(h)
        if ratio < (INSTAGRAM_CAROUSEL_MIN_ASPECT_RATIO - 1e-6) or ratio > (INSTAGRAM_CAROUSEL_MAX_ASPECT_RATIO + 1e-6):
            raise ValueError(
                f"Carousel slide {idx} aspect ratio {ratio:.4f} ({w}x{h}) outside Meta Graph API bounds "
                f"[{INSTAGRAM_CAROUSEL_MIN_ASPECT_RATIO:.2f}, {INSTAGRAM_CAROUSEL_MAX_ASPECT_RATIO:.2f}] (use 4:5 1080x1350, never 3:4)"
            )
    return dims


def publish_instagram_reel_graph_api(
    *,
    ig_user_id: str,
    access_token: str,
    video_url: str,
    caption: str,
    cover_url: str | None = None,
    share_to_feed: bool = True,
    trial_graduation_strategy: Literal["SS_PERFORMANCE", "MANUAL"] | None = None,
    require_trial: bool = False,
    receipt_path: Path | str | None = None,
    api_version: str = "v21.0",
    poll_interval_sec: float = 5.0,
    max_wait_sec: float = 180.0,
) -> dict[str, Any]:
    """
    Publishes a Reel via Meta's official Instagram Graph API (`graph.instagram.com`), with an automatic
    `>= 1,000` follower eligibility gate whenever `trial_graduation_strategy` (`Trial Reels`) is requested.
    """
    if not ig_user_id.strip() or not access_token.strip() or not video_url.strip():
        raise ValueError("ig_user_id, access_token, and video_url are required for Graph API Reel publishing")

    trial_enabled = False
    trial_skipped_reason: str | None = None
    followers_count: int | None = None

    if trial_graduation_strategy is not None:
        if trial_graduation_strategy not in ("SS_PERFORMANCE", "MANUAL"):
            raise ValueError(
                f"trial_graduation_strategy must be 'SS_PERFORMANCE' or 'MANUAL', got {trial_graduation_strategy!r}"
            )
        followers_count = fetch_instagram_followers_count(
            ig_user_id=ig_user_id,
            access_token=access_token,
            api_version=api_version,
        )
        if followers_count < TRIAL_REELS_MIN_FOLLOWERS:
            trial_skipped_reason = "followers_below_1000"
            if require_trial:
                return {
                    "status": "aborted_trial_ineligible",
                    "trial_enabled": False,
                    "trial_skipped_reason": trial_skipped_reason,
                    "followers_count": followers_count,
                    "min_followers_required": TRIAL_REELS_MIN_FOLLOWERS,
                }
        else:
            trial_enabled = True

    base = f"https://graph.instagram.com/{api_version.strip('/')}"
    create_params: dict[str, str] = {
        "media_type": "REELS",
        "video_url": video_url.strip(),
        "caption": caption,
        "access_token": access_token.strip(),
    }
    if trial_enabled and trial_graduation_strategy is not None:
        create_params["trial_params"] = json.dumps({"graduation_strategy": trial_graduation_strategy})
    else:
        create_params["share_to_feed"] = "true" if share_to_feed else "false"
    if cover_url:
        create_params["cover_url"] = cover_url.strip()

    req = urllib.request.Request(
        f"{base}/{ig_user_id.strip()}/media",
        data=urllib.parse.urlencode(create_params).encode("utf-8"),
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30.0) as resp:
        creation_doc = json.loads(resp.read().decode("utf-8"))
    creation_id = str(creation_doc.get("id") or "").strip()
    if not creation_id:
        raise RuntimeError(f"Instagram Graph API did not return creation_id: {creation_doc}")

    deadline = time.monotonic() + float(max_wait_sec)
    while time.monotonic() < deadline:
        status_qs = urllib.parse.urlencode(
            {"fields": "status_code,status", "access_token": access_token.strip()}
        )
        with urllib.request.urlopen(f"{base}/{creation_id}?{status_qs}", timeout=20.0) as s_resp:
            st_doc = json.loads(s_resp.read().decode("utf-8"))
        code = str(st_doc.get("status_code") or "").upper()
        if code == "FINISHED":
            break
        if code in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"Instagram media container {creation_id} failed: {st_doc}")
        time.sleep(poll_interval_sec)
    else:
        raise TimeoutError(f"Timed out waiting for Instagram media container {creation_id} to finish processing")

    pub_req = urllib.request.Request(
        f"{base}/{ig_user_id.strip()}/media_publish",
        data=urllib.parse.urlencode(
            {"creation_id": creation_id, "access_token": access_token.strip()}
        ).encode("utf-8"),
        method="POST",
    )
    with urllib.request.urlopen(pub_req, timeout=30.0) as p_resp:
        pub_doc = json.loads(p_resp.read().decode("utf-8"))
    media_id = str(pub_doc.get("id") or "").strip()

    permalink = ""
    shortcode = ""
    if media_id:
        perm_qs = urllib.parse.urlencode(
            {"fields": "permalink,shortcode", "access_token": access_token.strip()}
        )
        try:
            with urllib.request.urlopen(f"{base}/{media_id}?{perm_qs}", timeout=20.0) as m_resp:
                m_doc = json.loads(m_resp.read().decode("utf-8"))
                permalink = str(m_doc.get("permalink") or "")
                shortcode = str(m_doc.get("shortcode") or "")
        except urllib.error.URLError:
            pass

    receipt: dict[str, Any] = {
        "status": "published",
        "creation_id": creation_id,
        "media_id": media_id,
        "reel_url": permalink,
        "shortcode": shortcode,
        "trial_enabled": trial_enabled,
        "uploaded_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    if followers_count is not None:
        receipt["followers_count"] = followers_count
    if trial_enabled and trial_graduation_strategy is not None:
        receipt["trial_graduation_strategy"] = trial_graduation_strategy
    if trial_skipped_reason is not None:
        receipt["trial_skipped_reason"] = trial_skipped_reason

    if receipt_path:
        rp = Path(receipt_path)
        rp.parent.mkdir(parents=True, exist_ok=True)
        rp.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return receipt


def publish_instagram_carousel_graph_api(
    *,
    ig_user_id: str,
    access_token: str,
    image_urls: Sequence[str],
    caption: str,
    slide_paths: Sequence[Path | str] | None = None,
    slide_dimensions: Sequence[tuple[int, int]] | None = None,
    receipt_path: Path | str | None = None,
    api_version: str = "v21.0",
    poll_interval_sec: float = 4.0,
    max_wait_sec: float = 180.0,
) -> dict[str, Any]:
    """
    Publishes a `4:5` (`1080x1350`) multi-slide Carousel via Meta's official Instagram Graph API:
      1. Validates `2..10` static images and aspect ratio `0.80 <= w/h <= 1.91` (`3:4` `0.75` rejected pre-flight).
      2. Creates child item containers (`is_carousel_item=true`).
      3. Creates parent `CAROUSEL` container (`children=...`, `caption=...`).
      4. Polls parent container until `FINISHED` and calls `media_publish`.
      5. Saves `06_publish/instagram_carousel_receipt.json` when `receipt_path` is provided.
    """
    if not ig_user_id.strip() or not access_token.strip():
        raise ValueError("ig_user_id and access_token are required for Graph API Carousel publishing")
    if not (INSTAGRAM_CAROUSEL_MIN_SLIDES <= len(image_urls) <= INSTAGRAM_CAROUSEL_MAX_SLIDES):
        raise ValueError(
            f"Instagram Carousel requires {INSTAGRAM_CAROUSEL_MIN_SLIDES}..{INSTAGRAM_CAROUSEL_MAX_SLIDES} image_urls, got {len(image_urls)}"
        )
    for idx, u in enumerate(image_urls, start=1):
        u_clean = str(u or "").strip()
        if not u_clean:
            raise ValueError(f"Carousel image_url {idx} is empty")
        url_path = urllib.parse.urlparse(u_clean).path.lower()
        if any(url_path.endswith(ext) for ext in _VIDEO_EXTENSIONS):
            raise ValueError(f"Video URL forbidden in static Instagram Carousel (slide {idx}): {u_clean}")

    checked_dims: list[tuple[int, int]] = []
    if slide_paths is not None or slide_dimensions is not None:
        checked_dims = validate_instagram_carousel_slides(slide_paths, slide_dimensions=slide_dimensions)
        if len(checked_dims) != len(image_urls):
            raise ValueError(
                f"Mismatch between len(image_urls)={len(image_urls)} and validated slides={len(checked_dims)}"
            )

    base = f"https://graph.instagram.com/{api_version.strip('/')}"
    token = access_token.strip()
    uid = ig_user_id.strip()

    child_ids: list[str] = []
    for idx, img_url in enumerate(image_urls, start=1):
        c_req = urllib.request.Request(
            f"{base}/{uid}/media",
            data=urllib.parse.urlencode(
                {
                    "image_url": img_url.strip(),
                    "is_carousel_item": "true",
                    "access_token": token,
                }
            ).encode("utf-8"),
            method="POST",
        )
        with urllib.request.urlopen(c_req, timeout=30.0) as c_resp:
            c_doc = json.loads(c_resp.read().decode("utf-8"))
        cid = str(c_doc.get("id") or "").strip()
        if not cid:
            raise RuntimeError(f"Instagram Graph API did not return child creation_id for slide {idx}: {c_doc}")
        child_ids.append(cid)

    parent_req = urllib.request.Request(
        f"{base}/{uid}/media",
        data=urllib.parse.urlencode(
            {
                "media_type": "CAROUSEL",
                "children": ",".join(child_ids),
                "caption": caption,
                "access_token": token,
            }
        ).encode("utf-8"),
        method="POST",
    )
    with urllib.request.urlopen(parent_req, timeout=30.0) as p_resp:
        p_doc = json.loads(p_resp.read().decode("utf-8"))
    parent_id = str(p_doc.get("id") or "").strip()
    if not parent_id:
        raise RuntimeError(f"Instagram Graph API did not return parent CAROUSEL creation_id: {p_doc}")

    deadline = time.monotonic() + float(max_wait_sec)
    while time.monotonic() < deadline:
        status_qs = urllib.parse.urlencode({"fields": "status_code,status", "access_token": token})
        with urllib.request.urlopen(f"{base}/{parent_id}?{status_qs}", timeout=20.0) as s_resp:
            st_doc = json.loads(s_resp.read().decode("utf-8"))
        code = str(st_doc.get("status_code") or "").upper()
        if code in ("FINISHED", ""):
            break
        if code in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"Instagram CAROUSEL container {parent_id} failed: {st_doc}")
        time.sleep(poll_interval_sec)
    else:
        raise TimeoutError(f"Timed out waiting for Instagram CAROUSEL container {parent_id}")

    pub_req = urllib.request.Request(
        f"{base}/{uid}/media_publish",
        data=urllib.parse.urlencode({"creation_id": parent_id, "access_token": token}).encode("utf-8"),
        method="POST",
    )
    with urllib.request.urlopen(pub_req, timeout=30.0) as pub_resp:
        pub_doc = json.loads(pub_resp.read().decode("utf-8"))
    media_id = str(pub_doc.get("id") or "").strip()

    permalink = ""
    shortcode = ""
    if media_id:
        perm_qs = urllib.parse.urlencode({"fields": "permalink,shortcode", "access_token": token})
        try:
            with urllib.request.urlopen(f"{base}/{media_id}?{perm_qs}", timeout=20.0) as m_resp:
                m_doc = json.loads(m_resp.read().decode("utf-8"))
                permalink = str(m_doc.get("permalink") or "")
                shortcode = str(m_doc.get("shortcode") or "")
        except urllib.error.URLError:
            pass

    receipt = {
        "status": "published",
        "kind": "carousel",
        "engine": "graph_api",
        "child_creation_ids": child_ids,
        "creation_id": parent_id,
        "media_id": media_id,
        "post_url": permalink,
        "shortcode": shortcode,
        "slide_count": len(image_urls),
        "validated_dimensions": [f"{w}x{h}" for w, h in checked_dims] if checked_dims else [],
        "uploaded_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    if receipt_path:
        rp = Path(receipt_path)
        rp.parent.mkdir(parents=True, exist_ok=True)
        rp.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return receipt


async def _capture_png(client: DirectCDPClient, screenshot_path: Path) -> Path:
    """
    Wakes background-tab frame generation via `Page.startScreencast` -> `Page.captureScreenshot` ->
    `Page.stopScreencast` so occluded background tabs render cleanly without stealing window focus.
    """
    try:
        await client.send("Page.startScreencast", {"format": "png", "maxWidth": 1366, "maxHeight": 960}, timeout_sec=5.0)
        await asyncio.sleep(0.45)
    except Exception:
        pass
    try:
        res = await client.send("Page.captureScreenshot", {"format": "png"}, timeout_sec=10.0)
    finally:
        try:
            await client.send("Page.stopScreencast", timeout_sec=5.0)
        except Exception:
            pass
    raw_b64 = res.get("data", "")
    screenshot_path.parent.mkdir(parents=True, exist_ok=True)
    if raw_b64:
        screenshot_path.write_bytes(base64.b64decode(raw_b64))
    return screenshot_path


async def _inspect_page(client: DirectCDPClient) -> dict[str, Any]:
    return (
        await client.eval(
            r"""
            (() => {
                const url = location.href;
                const title = document.title || '';
                const bodyText = (document.body ? document.body.innerText : '').slice(0, 4000);
                const inputs = Array.from(document.querySelectorAll('input, textarea')).map(i => ({
                    tag: i.tagName,
                    name: i.name || '',
                    type: i.type || '',
                    placeholder: i.placeholder || '',
                    ariaLabel: i.getAttribute('aria-label') || '',
                    visible: i.getBoundingClientRect().width > 0 && i.getBoundingClientRect().height > 0,
                }));
                return { url, title, bodyText, inputs };
            })()
            """
        )
        or {}
    )


async def _click_button_text(client: DirectCDPClient, labels: list[str]) -> str | None:
    return await client.eval(
        f"""
        (() => {{
            const targets = {json.dumps([x.lower() for x in labels])};
            const nodes = Array.from(
                document.querySelectorAll('button, div[role="button"], span[role="button"], a[role="button"], a[role="link"]')
            ).filter(e => e.getBoundingClientRect().width > 0 && e.getBoundingClientRect().height > 0);
            for (const t of targets) {{
                const exact = nodes.find(e => (e.innerText || e.textContent || '').trim().toLowerCase() === t);
                if (exact) {{
                    exact.click();
                    return (exact.innerText || exact.textContent || '').trim();
                }}
            }}
            for (const t of targets) {{
                const sub = nodes.find(e => (e.innerText || e.textContent || '').trim().toLowerCase().includes(t));
                if (sub) {{
                    sub.click();
                    return (sub.innerText || sub.textContent || '').trim();
                }}
            }}
            return null;
        }})()
        """
    )


async def configure_instagram_profile_cdp(
    *,
    env_path: Path | str = DEFAULT_INSTAGRAM_ENV_PATH,
    avatar_path: Path | str | None = None,
    handle_candidates: tuple[str, ...] | list[str] = DEFAULT_HANDLE_CANDIDATES,
    display_name: str = "ALL ABOUT BRAIN | Neuroscience & Psychology",
    bio: str = DEFAULT_US_BIO,
    website_url: str = DEFAULT_YOUTUBE_CHANNEL_URL,
    verification_screenshot_path: Path | str | None = None,
    after_screenshot_path: Path | str | None = None,
    cdp_host: str = DEFAULT_CDP_HOST,
    cdp_port: int = DEFAULT_CDP_PORT,
    existing_target_id: str | None = None,
    close_tab_on_finish: bool = False,
) -> dict[str, Any]:
    """
    Connects to a single isolated CDP tab, verifies Instagram session (halting cleanly on 2FA or
    datacenter `1675004`/`429` edge rate-limiting), and updates profile bio/avatar/name/handle/link.
    """
    creds = load_instagram_credentials(env_path)
    owner_id = f"pid:{os.getpid()}:ig_profile_config"
    if existing_target_id:
        tid = existing_target_id
        acquire_tab_lease(
            tid,
            owner_id=owner_id,
            purpose="instagram_profile_config",
            cdp_port=cdp_port,
            created_by_pipeline=True,
        )
        ws_url = f"ws://{cdp_host}:{int(cdp_port)}/devtools/page/{tid}"
    else:
        opened = open_leased_cdp_tab(
            "about:blank",
            owner_id=owner_id,
            purpose="instagram_profile_config",
            cdp_port=cdp_port,
            cdp_host=cdp_host,
            background=True,
        )
        tid = str(opened["id"])
        ws_url = str(opened.get("webSocketDebuggerUrl") or f"ws://{cdp_host}:{int(cdp_port)}/devtools/page/{tid}")

    keep_open = False
    try:
        async with DirectCDPClient(ws_url) as client:
            await client.send(
                "Emulation.setDeviceMetricsOverride",
                {"width": 1366, "height": 960, "deviceScaleFactor": 1, "mobile": False},
            )
            await client.send("Page.navigate", {"url": "https://www.instagram.com/accounts/edit/?hl=en"})
            await asyncio.sleep(5.0)
            st = await _inspect_page(client)
            rl_markers = detect_datacenter_rate_limit(str(st.get("url") or ""), str(st.get("bodyText") or ""))
            if rl_markers:
                keep_open = True
                shot = str(await _capture_png(client, Path(verification_screenshot_path))) if verification_screenshot_path else None
                return {
                    "status": "datacenter_ip_rate_limited",
                    "target_id": tid,
                    "markers": rl_markers,
                    "screenshot_path": shot,
                }
            markers = detect_challenge_markers(str(st.get("url") or ""), str(st.get("bodyText") or ""))
            if markers:
                keep_open = True
                shot = str(await _capture_png(client, Path(verification_screenshot_path))) if verification_screenshot_path else None
                return {
                    "status": "verification_needed",
                    "target_id": tid,
                    "markers": markers,
                    "screenshot_path": shot,
                    "prompt_excerpt": str(st.get("bodyText") or "")[:600],
                }

            if avatar_path and Path(avatar_path).exists():
                await client.set_file_input(Path(avatar_path), "input[type='file']")
                await asyncio.sleep(4.0)

            if bio:
                await client.type_into(["textarea", "textarea[id*='pepBio']"], bio)
                await asyncio.sleep(0.8)
                await _click_button_text(client, ["Submit", "Save"])
                await asyncio.sleep(3.0)

            after_shot = str(await _capture_png(client, Path(after_screenshot_path))) if after_screenshot_path else None
            return {
                "status": "ok",
                "target_id": tid,
                "configured_for": creds["username"],
                "requested_handles": list(handle_candidates),
                "display_name": display_name,
                "website_url": website_url,
                "screenshot_path": after_shot,
            }
    finally:
        if close_tab_on_finish and not keep_open:
            release_and_close_leased_tab(tid, owner_id=owner_id, cdp_port=cdp_port, cdp_host=cdp_host)


async def _click_xy(client: DirectCDPClient, x: float, y: float) -> None:
    await client.send("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": x, "y": y})
    await asyncio.sleep(0.06)
    await client.send(
        "Input.dispatchMouseEvent",
        {"type": "mousePressed", "x": x, "y": y, "button": "left", "clickCount": 1},
    )
    await asyncio.sleep(0.06)
    await client.send(
        "Input.dispatchMouseEvent",
        {"type": "mouseReleased", "x": x, "y": y, "button": "left", "clickCount": 1},
    )


async def _inspect_composer_dialogs(client: DirectCDPClient) -> dict[str, Any]:
    return (
        await client.eval(
            r"""
            (() => {
                const dlgs = Array.from(document.querySelectorAll('div[role="dialog"]'))
                    .filter(d => d.getBoundingClientRect().width > 180 && d.getBoundingClientRect().height > 120);
                const allText = dlgs.map(d => (d.innerText || '').trim()).join('\n---\n').slice(0, 2600);
                const btns = [];
                for (const d of dlgs) {
                    for (const e of d.querySelectorAll('button, div[role="button"], span[role="button"], a[role="link"], span, div')) {
                        const r = e.getBoundingClientRect();
                        if (r.width <= 0 || r.height <= 0 || r.height > 95) continue;
                        const svg = e.querySelector(':scope > svg[aria-label]') || (e.tagName === 'svg' ? e : null);
                        const ownTxt = Array.from(e.childNodes)
                            .filter(n => n.nodeType === 3)
                            .map(n => n.textContent.trim())
                            .join(' ')
                            .trim() || ((e.children.length === 0) ? (e.innerText || '').trim() : '');
                        const role = e.getAttribute('role') || '';
                        const aria = e.getAttribute('aria-label') || (svg ? svg.getAttribute('aria-label') : '') || '';
                        if (
                            e.tagName === 'BUTTON' ||
                            role === 'button' ||
                            aria ||
                            ['OK', '9:16', 'Original', '1:1', '4:5', '16:9', 'Next', 'Share',
                             'Select from computer', 'Advanced settings', 'Accessibility'].includes(ownTxt)
                        ) {
                            btns.push({
                                text: (ownTxt || (e.innerText || '').replace(/\s+/g, ' ').trim()).slice(0, 60),
                                aria,
                                x: Math.round(r.left + r.width / 2),
                                y: Math.round(r.top + r.height / 2),
                            });
                        }
                    }
                }
                const dlgFileInputs = Array.from(document.querySelectorAll('div[role="dialog"] input[type="file"]')).length;
                return { dlgCount: dlgs.length, allText, btns: btns.slice(0, 80), dlgFileInputs };
            })()
            """
        )
        or {}
    )


async def upload_instagram_reel_cdp(
    *,
    video_path: Path | str,
    cover_path: Path | str,
    caption: str,
    handle: str,
    receipt_path: Path | str | None = None,
    live_screenshot_path: Path | str | None = None,
    cdp_host: str = DEFAULT_CDP_HOST,
    cdp_port: int = DEFAULT_CDP_PORT,
    existing_target_id: str | None = None,
    close_tab_on_finish: bool = True,
) -> dict[str, Any]:
    """
    Uploads a clean vertical `9:16` (`1080x1920`) MP4 as an Instagram Reel via an isolated CDP tab:
      1. Opens `Create` (`Post` submenu on Creator accounts) and attaches `video_path` strictly inside `div[role='dialog']`.
      2. Dismisses any nested `"Video posts are now shared as reels"` modal and selects `9:16` (`Original`) vertical crop.
      3. Uploads custom `R65 v4` `9:16` cover (`cover_path`) strictly inside `div[role='dialog']`.
      4. Inserts `caption` via Lexical-safe `Input.insertText`, toggles `Add AI label` ON, clicks `Share`, and polls completion.
      5. Verifies live `/reel/<shortcode>/` permalink and writes `instagram_publish_receipt.json`.
    """
    v_path = Path(video_path).resolve()
    c_path = Path(cover_path).resolve()
    if not v_path.exists():
        raise FileNotFoundError(f"Reel video file missing: {v_path}")
    if not c_path.exists():
        raise FileNotFoundError(f"Reel cover file missing: {c_path}")
    if not caption.strip():
        raise ValueError("Reel caption must be non-empty")

    owner_id = f"pid:{os.getpid()}:ig_reel_uploader"
    opened_fresh_tab = existing_target_id is None
    if existing_target_id:
        tid = existing_target_id
        acquire_tab_lease(
            tid,
            owner_id=owner_id,
            purpose="instagram_reel_upload",
            cdp_port=cdp_port,
            created_by_pipeline=True,
        )
        ws_url = f"ws://{cdp_host}:{int(cdp_port)}/devtools/page/{tid}"
    else:
        opened = open_leased_cdp_tab(
            "about:blank",
            owner_id=owner_id,
            purpose="instagram_reel_upload",
            cdp_port=cdp_port,
            cdp_host=cdp_host,
            background=True,
        )
        tid = str(opened["id"])
        ws_url = str(opened.get("webSocketDebuggerUrl") or f"ws://{cdp_host}:{int(cdp_port)}/devtools/page/{tid}")

    succeeded = False
    try:
        async with DirectCDPClient(ws_url) as client:
            await client.send(
                "Emulation.setDeviceMetricsOverride",
                {"width": 1366, "height": 960, "deviceScaleFactor": 1, "mobile": False},
            )
            clean_handle = handle.lstrip("@").strip()
            nav_url = f"https://www.instagram.com/{clean_handle}/?hl=en"
            await client.send("Page.navigate", {"url": nav_url})
            await asyncio.sleep(5.5)

            page_probe = (
                await client.eval(
                    r"""(() => ({
                        title: document.title || '',
                        bodyText: (document.body ? document.body.innerText : '').slice(0, 4000),
                        url: location.href || '',
                    }))()"""
                )
                or {}
            )
            rl_429 = detect_instagram_rate_limit_429(
                str(page_probe.get("title") or ""),
                str(page_probe.get("bodyText") or ""),
                str(page_probe.get("url") or nav_url),
            )
            if rl_429:
                return {
                    "status": "rate_limited_429",
                    "handle": clean_handle,
                    "reason": rl_429,
                    "url": str(page_probe.get("url") or nav_url),
                }

            # Record pre-existing reel shortcodes so we reliably identify the newly published Reel
            before_hrefs: list[str] = (
                await client.eval(
                    r"""(() => Array.from(document.querySelectorAll('a[href*="/reel/"], a[href*="/p/"]'))
                        .map(a => a.getAttribute('href') || '').filter(Boolean))()"""
                )
                or []
            )
            before_codes = {
                m.group(1)
                for h in before_hrefs
                for m in [re.search(r"/(?:reel|p)/([A-Za-z0-9_-]+)", h)]
                if m
            }

            create_btn = await client.eval(
                r"""(() => {
                    const svg = document.querySelector('svg[aria-label="New post"], svg[aria-label="Create"]');
                    const el = svg ? (svg.closest('a, div[role="button"], button, span') || svg) : null;
                    if (!el) return null;
                    const r = el.getBoundingClientRect();
                    return { x: Math.round(r.left + r.width / 2), y: Math.round(r.top + r.height / 2) };
                })()"""
            )
            if not create_btn:
                raise RuntimeError(f"Instagram Create (+) button not found on @{clean_handle} (session may require login)")
            await _click_xy(client, create_btn["x"], create_btn["y"])
            await asyncio.sleep(2.0)

            submenu_post = await client.eval(
                r"""(() => {
                    const dlg = document.querySelector('div[role="dialog"]');
                    if (dlg && dlg.getBoundingClientRect().width > 300) return null;
                    const item = Array.from(document.querySelectorAll('a, div[role="button"], span[role="link"], div[role="menuitem"], span'))
                        .find(e => /^post$/i.test((e.innerText||'').trim()) && e.getBoundingClientRect().width > 0 && e.getBoundingClientRect().height < 60);
                    if (!item) return null;
                    const r = item.getBoundingClientRect();
                    return { x: Math.round(r.left + r.width / 2), y: Math.round(r.top + r.height / 2) };
                })()"""
            )
            if submenu_post:
                await _click_xy(client, submenu_post["x"], submenu_post["y"])
                await asyncio.sleep(2.2)

            t_vid_start = time.monotonic()
            ok_vid, _matched_vid_sel = await attach_instagram_file_input_with_polling(
                client,
                v_path,
                selectors=INSTAGRAM_VIDEO_FILE_INPUT_SELECTORS,
                timeout_sec=12.0,
                poll_interval_sec=0.5,
            )
            if not ok_vid:
                elapsed_vid = time.monotonic() - t_vid_start
                raise RuntimeError(
                    f"Failed to attach Reel MP4 after {elapsed_vid:.1f}s polling selectors "
                    f"{list(INSTAGRAM_VIDEO_FILE_INPUT_SELECTORS)}"
                )
            await asyncio.sleep(7.0)

            st1 = await _inspect_composer_dialogs(client)
            ok_btn = next((b for b in reversed(st1.get("btns", [])) if b["text"].upper() == "OK"), None)
            if ok_btn:
                await _click_xy(client, ok_btn["x"], ok_btn["y"])
                await asyncio.sleep(2.0)

            # Force 9:16 vertical aspect ratio instead of 1:1 square crop
            st2 = await _inspect_composer_dialogs(client)
            crop_btn = next((b for b in st2.get("btns", []) if "select crop" in b["aria"].lower()), None)
            if crop_btn:
                await _click_xy(client, crop_btn["x"], crop_btn["y"])
                await asyncio.sleep(1.4)
                st_crop = await _inspect_composer_dialogs(client)
                crop_choices = [b for b in st_crop.get("btns", []) if b["text"] in ("Original", "1:1", "4:5", "9:16", "16:9")]
                pick = next((b for b in crop_choices if b["text"] == "9:16"), None) or next(
                    (b for b in crop_choices if b["text"] == "Original"), None
                )
                if pick:
                    await _click_xy(client, pick["x"], pick["y"])
                    await asyncio.sleep(1.4)
                    await _click_xy(client, crop_btn["x"], crop_btn["y"])
                    await asyncio.sleep(1.0)

            st_post_crop = await _inspect_composer_dialogs(client)
            next1 = next((b for b in st_post_crop.get("btns", []) if b["text"] == "Next"), None)
            if not next1:
                raise RuntimeError("Next button not found on Instagram Crop step")
            await _click_xy(client, next1["x"], next1["y"])
            await asyncio.sleep(3.2)

            st_edit = await _inspect_composer_dialogs(client)
            if not st_edit.get("dlgFileInputs"):
                sel_btn = next((b for b in st_edit.get("btns", []) if "select from computer" in b["text"].lower()), None)
                if sel_btn:
                    await _click_xy(client, sel_btn["x"], sel_btn["y"])
                    await asyncio.sleep(1.4)
            t_cov_start = time.monotonic()
            cov_ok, _matched_cov_sel = await attach_instagram_file_input_with_polling(
                client,
                c_path,
                selectors=INSTAGRAM_IMAGE_FILE_INPUT_SELECTORS,
                timeout_sec=12.0,
                poll_interval_sec=0.5,
            )
            if not cov_ok:
                elapsed_cov = time.monotonic() - t_cov_start
                raise RuntimeError(
                    f"Failed to attach Reel cover PNG after {elapsed_cov:.1f}s polling selectors "
                    f"{list(INSTAGRAM_IMAGE_FILE_INPUT_SELECTORS)}"
                )
            await asyncio.sleep(3.8)

            st_edit2 = await _inspect_composer_dialogs(client)
            next2 = next((b for b in st_edit2.get("btns", []) if b["text"] == "Next"), None)
            if not next2:
                raise RuntimeError("Next button not found on Instagram Cover step")
            await _click_xy(client, next2["x"], next2["y"])
            await asyncio.sleep(3.5)

            cap_box = await client.eval(
                r"""(() => {
                    const dlgs = Array.from(document.querySelectorAll('div[role="dialog"]'));
                    for (const d of dlgs) {
                        const box = d.querySelector('div[aria-label="Write a caption..."], div[role="textbox"][contenteditable="true"], textarea');
                        if (box && box.getBoundingClientRect().width > 0) {
                            const r = box.getBoundingClientRect();
                            return { x: Math.round(r.left + 60), y: Math.round(r.top + 24) };
                        }
                    }
                    return null;
                })()"""
            )
            if cap_box:
                await _click_xy(client, cap_box["x"], cap_box["y"])
                await asyncio.sleep(0.25)
                await client.send("Input.insertText", {"text": caption.strip()})
                await asyncio.sleep(0.3)
                await client.send("Input.dispatchKeyEvent", {"type": "keyDown", "text": " ", "unmodifiedText": " ", "key": " "})
                await client.send("Input.dispatchKeyEvent", {"type": "keyUp", "key": " "})
                await client.send(
                    "Input.dispatchKeyEvent",
                    {"type": "keyDown", "key": "Backspace", "code": "Backspace", "windowsVirtualKeyCode": 8},
                )
                await client.send(
                    "Input.dispatchKeyEvent",
                    {"type": "keyUp", "key": "Backspace", "code": "Backspace", "windowsVirtualKeyCode": 8},
                )
                await asyncio.sleep(1.0)

            st_cap = await _inspect_composer_dialogs(client)
            adv_btn = next((b for b in st_cap.get("btns", []) if "advanced settings" in b["text"].lower()), None)
            if adv_btn:
                await _click_xy(client, adv_btn["x"], adv_btn["y"])
                await asyncio.sleep(1.4)

            await client.eval(
                r"""(() => {
                    for (const d of document.querySelectorAll('div[role="dialog"]')) {
                        for (const s of d.querySelectorAll('input[type="checkbox"], div[role="switch"]')) {
                            let anc = s.parentElement;
                            let txt = '';
                            for (let depth = 0; depth < 6 && anc && anc !== d; depth++) {
                                const candidate = (anc.innerText || '').replace(/\s+/g, ' ').trim();
                                if (candidate.length > 3 && candidate.length < 280) {
                                    txt = candidate;
                                    break;
                                }
                                anc = anc.parentElement;
                            }
                            const checked = Boolean(s.checked || s.getAttribute('aria-checked') === 'true');
                            if (/add ai label|ai-generated/i.test(txt) && !checked) {
                                s.click();
                                return true;
                            }
                        }
                    }
                    return false;
                })()"""
            )
            await asyncio.sleep(0.8)

            st_ready = await _inspect_composer_dialogs(client)
            share_btn = next((b for b in st_ready.get("btns", []) if b["text"] == "Share"), None)
            if not share_btn:
                raise RuntimeError(f"Share button not found on New reel dialog: {st_ready.get('allText', '')[:300]}")
            await _click_xy(client, share_btn["x"], share_btn["y"])

            shared_ok = False
            for _ in range(60):
                await asyncio.sleep(4.0)
                st_p = await _inspect_composer_dialogs(client)
                b_low = str(st_p.get("allText") or "").lower()
                if "your reel has been shared" in b_low or "reel shared" in b_low or "your post has been shared" in b_low:
                    shared_ok = True
                    break

            if not shared_ok:
                raise TimeoutError("Timed out waiting for 'Your reel has been shared' confirmation")

            await asyncio.sleep(5.0)
            await client.send("Page.navigate", {"url": f"https://www.instagram.com/{clean_handle}/reels/?hl=en"})
            await asyncio.sleep(6.0)
            hrefs: list[str] = (
                await client.eval(
                    r"""
                    (() => Array.from(document.querySelectorAll('a[href*="/reel/"], a[href*="/p/"]'))
                        .map(a => a.getAttribute('href') || '')
                        .filter(Boolean))()
                    """
                )
                or []
            )
            shortcode = ""
            all_codes: list[str] = []
            for h in hrefs:
                m = re.search(r"/(?:reel|p)/([A-Za-z0-9_-]+)", h)
                if m:
                    code = m.group(1)
                    if code not in all_codes:
                        all_codes.append(code)
                    if code not in before_codes and not shortcode:
                        shortcode = code
            if not shortcode and all_codes:
                shortcode = all_codes[0]

            reel_url = f"https://www.instagram.com/reel/{shortcode}/" if shortcode else ""
            if live_screenshot_path:
                if reel_url:
                    await client.send("Page.navigate", {"url": f"{reel_url}?hl=en"})
                    await asyncio.sleep(5.5)
                await _capture_png(client, Path(live_screenshot_path))

            receipt: dict[str, Any] = {
                "handle": f"@{clean_handle}",
                "profile_url": f"https://www.instagram.com/{clean_handle}/",
                "reel_url": reel_url,
                "shortcode": shortcode,
                "uploaded_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "cover_path": str(c_path),
                "video_path": str(v_path),
            }
            if receipt_path:
                rp = Path(receipt_path)
                rp.parent.mkdir(parents=True, exist_ok=True)
                rp.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

            succeeded = True
            return receipt
    finally:
        DirectCDPClient.cleanup_staged_bridge_files()
        if close_tab_on_finish and (succeeded or opened_fresh_tab):
            release_and_close_leased_tab(tid, owner_id=owner_id, cdp_port=cdp_port, cdp_host=cdp_host)


async def upload_instagram_carousel_cdp(
    *,
    slide_paths: Sequence[Path | str],
    caption: str,
    handle: str,
    receipt_path: Path | str | None = None,
    live_screenshot_path: Path | str | None = None,
    cdp_host: str = DEFAULT_CDP_HOST,
    cdp_port: int = DEFAULT_CDP_PORT,
    existing_target_id: str | None = None,
    close_tab_on_finish: bool = True,
) -> dict[str, Any]:
    """
    Uploads a `4:5` (`1080x1350`) multi-PNG Instagram Carousel via an isolated background CDP tab:
      - Strictly validates `2..10` static PNG/JPEG slides (`0.80 <= w/h <= 1.91`, zero MP4 mixing).
      - Halts cleanly without attempting any bypass on 2FA/security challenges or datacenter edge blocks.
      - Selects `4:5` (`Original` / `4:5`) crop, inserts `caption`, toggles `Add AI label` ON, and clicks `Share`.
    """
    import shutil
    from pipeline.studio.config import CONTAINER_BROWSER_BRIDGE_DIR, HOST_BROWSER_BRIDGE_DIR

    checked_dims = validate_instagram_carousel_slides(slide_paths)
    resolved_slides = [Path(p).resolve() for p in slide_paths]
    if not caption.strip():
        raise ValueError("Carousel caption must be non-empty")

    owner_id = f"pid:{os.getpid()}:ig_carousel_uploader"
    opened_fresh_tab = existing_target_id is None
    if existing_target_id:
        tid = existing_target_id
        acquire_tab_lease(
            tid,
            owner_id=owner_id,
            purpose="instagram_carousel_upload",
            cdp_port=cdp_port,
            created_by_pipeline=True,
        )
        ws_url = f"ws://{cdp_host}:{int(cdp_port)}/devtools/page/{tid}"
    else:
        opened = open_leased_cdp_tab(
            "about:blank",
            owner_id=owner_id,
            purpose="instagram_carousel_upload",
            cdp_port=cdp_port,
            cdp_host=cdp_host,
            background=True,
        )
        tid = str(opened["id"])
        ws_url = str(opened.get("webSocketDebuggerUrl") or f"ws://{cdp_host}:{int(cdp_port)}/devtools/page/{tid}")

    staged_host_files: list[Path] = []
    succeeded = False
    try:
        cdp_files: list[str] = []
        for idx, sp in enumerate(resolved_slides, start=1):
            if os.name != "nt" and HOST_BROWSER_BRIDGE_DIR.parent.exists():
                HOST_BROWSER_BRIDGE_DIR.mkdir(parents=True, exist_ok=True)
                staged_name = f"ig_carousel_{os.getpid()}_{idx:02d}_{sp.name}"
                host_staged = HOST_BROWSER_BRIDGE_DIR / staged_name
                shutil.copy2(sp, host_staged)
                staged_host_files.append(host_staged)
                cdp_files.append(f"{CONTAINER_BROWSER_BRIDGE_DIR.rstrip('/')}/{staged_name}")
            else:
                cdp_files.append(str(sp))

        async with DirectCDPClient(ws_url) as client:
            await client.send(
                "Emulation.setDeviceMetricsOverride",
                {"width": 1366, "height": 960, "deviceScaleFactor": 1, "mobile": False},
            )
            clean_handle = handle.lstrip("@").strip()
            nav_url = f"https://www.instagram.com/{clean_handle}/?hl=en"
            await client.send("Page.navigate", {"url": nav_url})
            await asyncio.sleep(5.5)

            st_init = await _inspect_page(client)
            rl_429 = detect_instagram_rate_limit_429(
                str(st_init.get("title") or ""),
                str(st_init.get("bodyText") or ""),
                str(st_init.get("url") or nav_url),
            )
            if rl_429:
                return {
                    "status": "rate_limited_429",
                    "handle": clean_handle,
                    "reason": rl_429,
                    "url": str(st_init.get("url") or nav_url),
                    "target_id": tid,
                }
            rl_markers = detect_datacenter_rate_limit(str(st_init.get("url") or ""), str(st_init.get("bodyText") or ""))
            if rl_markers:
                return {
                    "status": "datacenter_ip_rate_limited",
                    "target_id": tid,
                    "markers": rl_markers,
                }
            ch_markers = detect_challenge_markers(str(st_init.get("url") or ""), str(st_init.get("bodyText") or ""))
            if ch_markers:
                return {
                    "status": "verification_needed",
                    "target_id": tid,
                    "markers": ch_markers,
                }

            before_hrefs: list[str] = (
                await client.eval(
                    r"""(() => Array.from(document.querySelectorAll('a[href*="/p/"], a[href*="/reel/"]'))
                        .map(a => a.getAttribute('href') || '').filter(Boolean))()"""
                )
                or []
            )
            before_codes = {
                m.group(1)
                for h in before_hrefs
                for m in [re.search(r"/(?:p|reel)/([A-Za-z0-9_-]+)", h)]
                if m
            }

            create_btn = await client.eval(
                r"""(() => {
                    const svg = document.querySelector('svg[aria-label="New post"], svg[aria-label="Create"]');
                    const el = svg ? (svg.closest('a, div[role="button"], button, span') || svg) : null;
                    if (!el) return null;
                    const r = el.getBoundingClientRect();
                    return { x: Math.round(r.left + r.width / 2), y: Math.round(r.top + r.height / 2) };
                })()"""
            )
            if not create_btn:
                raise RuntimeError(f"Instagram Create (+) button not found on @{clean_handle}")
            await _click_xy(client, create_btn["x"], create_btn["y"])
            await asyncio.sleep(2.0)

            submenu_post = await client.eval(
                r"""(() => {
                    const dlg = document.querySelector('div[role="dialog"]');
                    if (dlg && dlg.getBoundingClientRect().width > 300) return null;
                    const item = Array.from(document.querySelectorAll('a, div[role="button"], span[role="link"], div[role="menuitem"], span'))
                        .find(e => /^post$/i.test((e.innerText||'').trim()) && e.getBoundingClientRect().width > 0 && e.getBoundingClientRect().height < 60);
                    if (!item) return null;
                    const r = item.getBoundingClientRect();
                    return { x: Math.round(r.left + r.width / 2), y: Math.round(r.top + r.height / 2) };
                })()"""
            )
            if submenu_post:
                await _click_xy(client, submenu_post["x"], submenu_post["y"])
                await asyncio.sleep(2.2)

            t_car_start = time.monotonic()
            car_deadline = t_car_start + 12.0
            obj_id = None
            for attempt in range(25):
                for sel in INSTAGRAM_IMAGE_FILE_INPUT_SELECTORS:
                    eval_inp = await client.send(
                        "Runtime.evaluate",
                        {
                            "expression": f"document.querySelector({json.dumps(sel)})",
                            "returnByValue": False,
                        },
                    )
                    cand_id = (eval_inp.get("result") or {}).get("objectId")
                    if cand_id:
                        obj_id = cand_id
                        break
                if obj_id or attempt + 1 >= 25 or time.monotonic() >= car_deadline:
                    break
                await asyncio.sleep(0.5)
            if not obj_id:
                elapsed_car = time.monotonic() - t_car_start
                raise RuntimeError(
                    f"Failed to find file input for Carousel upload after {elapsed_car:.1f}s "
                    f"polling selectors {list(INSTAGRAM_IMAGE_FILE_INPUT_SELECTORS)}"
                )
            await client.send("DOM.setFileInputFiles", {"files": cdp_files, "objectId": obj_id})
            await asyncio.sleep(4.5)

            # Select 4:5 (or Original since inputs are already 1080x1350 = 4:5)
            st_crop0 = await _inspect_composer_dialogs(client)
            crop_btn = next((b for b in st_crop0.get("btns", []) if "select crop" in b["aria"].lower()), None)
            if crop_btn:
                await _click_xy(client, crop_btn["x"], crop_btn["y"])
                await asyncio.sleep(1.2)
                st_crop = await _inspect_composer_dialogs(client)
                crop_choices = [b for b in st_crop.get("btns", []) if b["text"] in ("4:5", "Original", "1:1", "16:9")]
                pick = next((b for b in crop_choices if b["text"] == "4:5"), None) or next(
                    (b for b in crop_choices if b["text"] == "Original"), None
                )
                if pick:
                    await _click_xy(client, pick["x"], pick["y"])
                    await asyncio.sleep(1.0)
                    await _click_xy(client, crop_btn["x"], crop_btn["y"])
                    await asyncio.sleep(0.8)

            # Next (Crop -> Filter) -> Next (Filter -> Caption)
            for step_label in ("Crop", "Filter"):
                st_step = await _inspect_composer_dialogs(client)
                nxt = next((b for b in st_step.get("btns", []) if b["text"] == "Next"), None)
                if not nxt:
                    raise RuntimeError(f"Next button not found on Instagram Carousel {step_label} step")
                await _click_xy(client, nxt["x"], nxt["y"])
                await asyncio.sleep(2.4)

            cap_box = await client.eval(
                r"""(() => {
                    const dlgs = Array.from(document.querySelectorAll('div[role="dialog"]'));
                    for (const d of dlgs) {
                        const box = d.querySelector('div[aria-label="Write a caption..."], div[role="textbox"][contenteditable="true"], textarea');
                        if (box && box.getBoundingClientRect().width > 0) {
                            const r = box.getBoundingClientRect();
                            return { x: Math.round(r.left + 60), y: Math.round(r.top + 24) };
                        }
                    }
                    return null;
                })()"""
            )
            if cap_box:
                await _click_xy(client, cap_box["x"], cap_box["y"])
                await asyncio.sleep(0.25)
                await client.send("Input.insertText", {"text": caption.strip()})
                await asyncio.sleep(0.8)

            st_cap = await _inspect_composer_dialogs(client)
            adv_btn = next((b for b in st_cap.get("btns", []) if "advanced settings" in b["text"].lower()), None)
            if adv_btn:
                await _click_xy(client, adv_btn["x"], adv_btn["y"])
                await asyncio.sleep(1.2)
                await client.eval(
                    r"""(() => {
                        for (const d of document.querySelectorAll('div[role="dialog"]')) {
                            for (const s of d.querySelectorAll('input[type="checkbox"], div[role="switch"]')) {
                                const txt = ((s.parentElement?.parentElement?.innerText || '')).replace(/\s+/g, ' ');
                                const checked = Boolean(s.checked || s.getAttribute('aria-checked') === 'true');
                                if (/add ai label|ai-generated/i.test(txt) && !checked) {
                                    s.click();
                                    return true;
                                }
                            }
                        }
                        return false;
                    })()"""
                )
                await asyncio.sleep(0.6)

            st_ready = await _inspect_composer_dialogs(client)
            share_btn = next((b for b in st_ready.get("btns", []) if b["text"] == "Share"), None)
            if not share_btn:
                raise RuntimeError("Share button not found on Instagram Carousel dialog")
            await _click_xy(client, share_btn["x"], share_btn["y"])

            shared_ok = False
            for _ in range(45):
                await asyncio.sleep(3.0)
                st_p = await _inspect_composer_dialogs(client)
                b_low = str(st_p.get("allText") or "").lower()
                if "your post has been shared" in b_low or "post shared" in b_low:
                    shared_ok = True
                    break
            if not shared_ok:
                raise TimeoutError("Timed out waiting for 'Your post has been shared' confirmation")

            await asyncio.sleep(4.0)
            await client.send("Page.navigate", {"url": f"https://www.instagram.com/{clean_handle}/?hl=en"})
            await asyncio.sleep(5.0)
            after_hrefs: list[str] = (
                await client.eval(
                    r"""(() => Array.from(document.querySelectorAll('a[href*="/p/"]'))
                        .map(a => a.getAttribute('href') || '').filter(Boolean))()"""
                )
                or []
            )
            shortcode = ""
            for h in after_hrefs:
                m = re.search(r"/p/([A-Za-z0-9_-]+)", h)
                if m and m.group(1) not in before_codes:
                    shortcode = m.group(1)
                    break

            post_url = f"https://www.instagram.com/p/{shortcode}/" if shortcode else ""
            if live_screenshot_path:
                await _capture_png(client, Path(live_screenshot_path))

            receipt = {
                "status": "published",
                "kind": "carousel",
                "engine": "cdp",
                "handle": f"@{clean_handle}",
                "post_url": post_url,
                "shortcode": shortcode,
                "slide_count": len(resolved_slides),
                "validated_dimensions": [f"{w}x{h}" for w, h in checked_dims],
                "uploaded_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            }
            if receipt_path:
                rp = Path(receipt_path)
                rp.parent.mkdir(parents=True, exist_ok=True)
                rp.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            succeeded = True
            return receipt
    finally:
        for sf in staged_host_files:
            try:
                sf.unlink(missing_ok=True)
            except Exception:
                pass
        DirectCDPClient.cleanup_staged_bridge_files()
        if close_tab_on_finish and (succeeded or opened_fresh_tab):
            release_and_close_leased_tab(tid, owner_id=owner_id, cdp_port=cdp_port, cdp_host=cdp_host)
