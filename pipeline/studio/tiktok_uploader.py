"""
ALL ABOUT BRAIN — Standalone TikTok Official Profile & TikTok Studio Uploader
=============================================================================
Strictly isolated single-tab CDP Web automation (`configure_tiktok_profile_cdp` and
`upload_tiktok_video_cdp` on `127.0.0.1:9222`) for `@allaboutbrain_official`.

Concurrency, Privacy & Anti-CAPTCHA Invariants:
  - Opens at most ONE dedicated background tab via `open_leased_cdp_tab("about:blank", background=True)`
    and communicates exclusively with that `targetId` over `DirectCDPClient`.
  - Google OAuth Popup Exception: When clicking `Continue with Google` or `Add YouTube`, attaches ONLY
    to child `accounts.google.com` popup targets whose `openerId == parent_target_id`.
  - Never touches, inspects, refreshes, navigates, or closes any YouTube Studio, Google Flow,
    Instagram, or personal user tab.
  - Strict Anti-CAPTCHA Rule: NEVER drags, clicks, computes, wait-loops, or interacts with ANY
    CAPTCHA / puzzle slider (`secsdk-captcha`, `verify to continue`, `drag the slider`, etc.).
    If any CAPTCHA or new-account birthday prompt appears, halts immediately, captures a background
    screenshot via `Page.startScreencast` -> `Page.captureScreenshot`, leaves the leased tab open,
    and returns a structured `captcha_verification_needed` / `birthday_input_needed` status.
"""

from __future__ import annotations

import asyncio
import base64
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re
import subprocess
from typing import Any, Sequence
import urllib.request
from zoneinfo import ZoneInfo

from pipeline.cdp_tab_lease import (
    acquire_tab_lease,
    open_leased_cdp_tab,
    release_and_close_leased_tab,
    renew_tab_lease,
)
from pipeline.studio.config import DEFAULT_CDP_HOST, DEFAULT_CDP_PORT
from pipeline.studio.whale_session import DirectCDPClient, cleanup_staged_bridge_files

DEFAULT_GOOGLE_ACCOUNT_EMAIL = "canadaofbin@gmail.com"
DEFAULT_YOUTUBE_CHANNEL_HANDLE = "@AllAboutBrainOfficial"
DEFAULT_YOUTUBE_CHANNEL_URL = "https://www.youtube.com/@AllAboutBrainOfficial"
DEFAULT_TIKTOK_DISPLAY_NAME = "ALL ABOUT BRAIN"
DEFAULT_TIKTOK_HANDLE = "allaboutbrain_official"
DEFAULT_TIKTOK_HANDLE_CANDIDATES: tuple[str, ...] = (
    "allaboutbrain.official",
    "allaboutbrainhq",
    "allaboutbrain.us",
    "allaboutbrain_official",
)
DEFAULT_TIKTOK_BIO_CANDIDATES: tuple[str, ...] = (
    "🧠 Weirdest true brain & psych studies (DOI verified)\n👇 Full videos on YouTube",
    "🧠 True brain & psychology experiments (DOI verified)\n👇 Full videos on YouTube",
    "🧠 Weirdest true brain & psych studies (DOI verified)",
)
DEFAULT_TIKTOK_HASHTAGS: tuple[str, ...] = (
    "#neuroscience",
    "#psychology",
    "#brainfacts",
    "#humanbehavior",
    "#learnontiktok",
)
TIKTOK_BIO_MAX_UTF16_UNITS = 80
TIKTOK_USERNAME_MAX_CHARS = 24
TIKTOK_CAPTION_MAX_CHARS = 4000

TIKTOK_CAPTCHA_MARKERS: tuple[str, ...] = (
    "secsdk-captcha",
    "captcha-verify-container",
    "tiktok-verify-ele",
    "drag the slider",
    "fit the puzzle",
    "verify to continue",
    "select 2 objects",
    "same shape",
    "rotate the image",
    "security verification",
    "/captcha",
    "recaptcha",
    "hcaptcha",
    "turnstile",
    "funcaptcha",
    "arkose",
)

TIKTOK_BIRTHDAY_GATE_MARKERS: tuple[str, ...] = (
    "when’s your birthday",
    "when's your birthday",
    "your birthday won't be shown publicly",
    "your birthday won’t be shown publicly",
)


def utf16_code_units(text: str) -> int:
    """Returns JavaScript `.length` (UTF-16 code unit count, where astral emojis count as 2)."""
    return len((text or "").encode("utf-16-le")) // 2


def select_tiktok_bio(
    candidates: tuple[str, ...] | list[str] = DEFAULT_TIKTOK_BIO_CANDIDATES,
    *,
    max_utf16_units: int = TIKTOK_BIO_MAX_UTF16_UNITS,
) -> str:
    """Selects the highest-priority TikTok bio candidate that fits within `max_utf16_units` (`<= 80`)."""
    for raw in candidates:
        cleaned = (raw or "").strip()
        if cleaned and len(cleaned) <= max_utf16_units and utf16_code_units(cleaned) <= max_utf16_units:
            return cleaned
    raise ValueError(f"No TikTok bio candidate fits within {max_utf16_units} UTF-16 code units")


def validate_tiktok_username_candidate(handle: str) -> str:
    """Validates TikTok username rules (`<= 24` chars, `[A-Za-z0-9_.]`, cannot end with `.`)."""
    clean = (handle or "").strip().lstrip("@")
    if not clean:
        raise ValueError("TikTok username must be non-empty")
    if len(clean) > TIKTOK_USERNAME_MAX_CHARS:
        raise ValueError(f"TikTok username {clean!r} exceeds {TIKTOK_USERNAME_MAX_CHARS} chars ({len(clean)})")
    if clean.endswith("."):
        raise ValueError(f"TikTok username {clean!r} cannot end with a period")
    if not re.fullmatch(r"[A-Za-z0-9_.]+", clean):
        raise ValueError(f"TikTok username {clean!r} contains disallowed characters")
    return clean


def build_tiktok_caption(
    *,
    hook_question: str,
    story_summary: str,
    debate_question: str = "",
    citation_line: str = "",
    doi: str,
    hashtags: tuple[str, ...] | list[str] = DEFAULT_TIKTOK_HASHTAGS,
    max_chars: int = TIKTOK_CAPTION_MAX_CHARS,
) -> str:
    """
    Builds a US English TikTok caption:
      1. Curiosity-gap hook question (`Why did kids eat the marshmallow 4x faster...`).
      2. Plain-English experiment story & brain adaptation takeaway.
      3. Comment-debate prompt.
      4. Peer-reviewed study + `DOI` verification stamp.
      5. Up to 5 niche hashtags (`#neuroscience #psychology #brainfacts #humanbehavior #learnontiktok`).
    """
    h_q = (hook_question or "").strip()
    story = (story_summary or "").strip()
    deb = (debate_question or "").strip()
    cit = (citation_line or "").strip()
    clean_doi = (doi or "").strip()
    if clean_doi.lower().startswith("https://doi.org/"):
        clean_doi = clean_doi[len("https://doi.org/") :].strip()
    elif clean_doi.lower().startswith("http://doi.org/"):
        clean_doi = clean_doi[len("http://doi.org/") :].strip()
    elif clean_doi.lower().startswith("doi:"):
        clean_doi = clean_doi[4:].strip()

    if not h_q or not story or not clean_doi:
        raise ValueError("hook_question, story_summary, and doi are required for TikTok caption")

    norm_tags: list[str] = []
    seen_low: set[str] = set()
    for raw_tag in hashtags:
        t = str(raw_tag or "").strip()
        if not t:
            continue
        if not t.startswith("#"):
            t = f"#{t}"
        t_clean = "#" + re.sub(r"[^A-Za-z0-9_]", "", t[1:])
        if len(t_clean) > 1 and t_clean.lower() not in seen_low:
            seen_low.add(t_clean.lower())
            norm_tags.append(t_clean)
        if len(norm_tags) >= 5:
            break

    study_block = f"📄 Study: {cit} · DOI: {clean_doi}" if cit else f"📄 DOI: {clean_doi}"
    sections = [h_q, story]
    if deb:
        sections.append(deb)
    sections.append(study_block)
    if norm_tags:
        sections.append(" ".join(norm_tags))

    caption = "\n\n".join(sections).strip()
    if len(caption) > max_chars:
        raise ValueError(f"TikTok caption exceeds {max_chars}-char limit ({len(caption)} chars)")
    return caption


def detect_tiktok_captcha(
    url: str,
    body_text: str,
    dom_markers: list[str] | tuple[str, ...] | None = None,
) -> list[str]:
    """
    Detects TikTok puzzle slider / shape-matching / rotation CAPTCHAs (`secsdk-captcha`,
    `Drag the slider to fit the puzzle`, `Verify to continue`) without interacting with them.
    """
    haystack = "\n".join(
        [
            (url or "").lower(),
            (body_text or "").lower(),
            *(str(m or "").lower() for m in (dom_markers or ())),
        ]
    )
    matched = [m for m in TIKTOK_CAPTCHA_MARKERS if m in haystack]
    for dm in dom_markers or ():
        dm_s = str(dm or "").strip()
        if dm_s and dm_s not in matched:
            matched.append(dm_s)
    return matched


def detect_tiktok_birthday_gate(url: str, body_text: str) -> list[str]:
    """Detects brand-new TikTok signup birthday prompts so personal birthdates are never invented."""
    haystack = f"{(url or '').lower()}\n{(body_text or '').lower()}"
    return [m for m in TIKTOK_BIRTHDAY_GATE_MARKERS if m in haystack]


def find_child_google_oauth_targets(
    targets: list[dict[str, Any]],
    *,
    parent_target_id: str,
) -> list[dict[str, Any]]:
    """
    Filters `/json/list` targets strictly to child Google OAuth popups (`accounts.google.com`)
    whose `openerId == parent_target_id`. Never matches unrelated tabs or other agents' popups.
    """
    pid = (parent_target_id or "").strip()
    if not pid:
        return []
    out: list[dict[str, Any]] = []
    for t in targets:
        if not isinstance(t, dict) or t.get("type") != "page":
            continue
        if str(t.get("openerId") or "").strip() != pid:
            continue
        u_low = str(t.get("url") or "").lower()
        if "accounts.google.com" in u_low or "youtube.com/signin" in u_low:
            out.append(t)
    return out


def resolve_avatar_path(avatar_path: Path | str | None) -> Path | None:
    """Resolves `avatar_path`, falling back to canonical `artifacts_archive/06_Channel_Art` if needed."""
    if avatar_path is None:
        return None
    p = Path(avatar_path)
    if p.exists():
        return p.resolve()
    repo_root = Path(__file__).resolve().parents[2]
    for fallback in (
        repo_root / "artifacts_archive" / "06_Channel_Art" / p.name,
        repo_root / "artifacts_archive" / "05_Channel_Art" / p.name,
    ):
        if fallback.exists():
            return fallback.resolve()
    return p


async def capture_background_png(client: DirectCDPClient, screenshot_path: Path) -> Path:
    """
    Wakes background-tab frame generation via `Page.startScreencast` -> `Page.captureScreenshot` ->
    `Page.stopScreencast` so occluded background tabs render cleanly without stealing window focus.
    """
    try:
        await client.send(
            "Page.startScreencast",
            {"format": "png", "maxWidth": 1440, "maxHeight": 1020},
            timeout_sec=5.0,
        )
        await asyncio.sleep(0.55)
    except Exception:
        pass
    try:
        res = await client.send("Page.captureScreenshot", {"format": "png"}, timeout_sec=12.0)
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


async def _inspect_tiktok_page(client: DirectCDPClient) -> dict[str, Any]:
    return (
        await client.eval(
            r"""
            (() => {
                const url = location.href || '';
                const title = document.title || '';
                const bodyText = (document.body ? document.body.innerText : '').slice(0, 6000);
                const captchaSelectors = [
                    '#captcha-verify-container-main-page',
                    '.captcha-verify-container',
                    '#tiktok-verify-ele',
                    '[id*="secsdk-captcha"]',
                    '[class*="secsdk-captcha"]',
                    '[class*="captcha-verify"]',
                    'iframe[src*="captcha"]'
                ];
                const domCaptcha = [];
                for (const sel of captchaSelectors) {
                    const el = document.querySelector(sel);
                    if (el) {
                        const r = el.getBoundingClientRect();
                        if (r.width > 0 && r.height > 0) {
                            domCaptcha.push('dom:' + sel);
                        }
                    }
                }
                return { url, title, bodyText, domCaptcha };
            })()
            """
        )
        or {}
    )


TIKTOK_CONFIRM_MODAL_LABELS: tuple[str, ...] = ("Post now", "Continue to post", "Schedule")
TIKTOK_MODAL_CONTAINER_SELECTOR: str = '[role="dialog"], .TUXModal, [class*="modal"], [class*="Modal"]'


async def _trusted_click_point(client: DirectCDPClient, x: float, y: float, w: float, h: float) -> tuple[float, float]:
    """Dispatches `isTrusted: true` mouseMoved -> mousePressed -> mouseReleased at the rect center."""
    cx = float(x) + float(w) / 2.0
    cy = float(y) + float(h) / 2.0
    await client.send("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": cx, "y": cy})
    await asyncio.sleep(0.06)
    await client.send(
        "Input.dispatchMouseEvent",
        {"type": "mousePressed", "x": cx, "y": cy, "button": "left", "clickCount": 1},
    )
    await asyncio.sleep(0.06)
    await client.send(
        "Input.dispatchMouseEvent",
        {"type": "mouseReleased", "x": cx, "y": cy, "button": "left", "clickCount": 1},
    )
    return cx, cy


async def _trusted_click_js(client: DirectCDPClient, find_rect_js: str) -> dict[str, Any] | None:
    """Dispatches `isTrusted: true` mouseMoved -> mousePressed -> mouseReleased at target center."""
    rect = await client.eval(find_rect_js)
    if not rect or not isinstance(rect, dict) or float(rect.get("w") or 0) <= 0:
        return None
    await _trusted_click_point(client, float(rect["x"]), float(rect["y"]), float(rect["w"]), float(rect["h"]))
    return rect


def _is_tiktok_publish_confirmed(url: str, body_text: str) -> bool:
    """Returns True when TikTok Studio page reflects successful Post or Schedule completion."""
    u_post = (url or "").lower()
    b_post = (body_text or "").lower()
    return (
        "/tiktokstudio/content" in u_post
        or "your video has been uploaded" in b_post
        or "your videos are being uploaded" in b_post
        or "your video has been scheduled" in b_post
        or "manage your posts" in b_post
        or "upload another video" in b_post
    )


async def click_tiktok_confirm_modal_button(
    client: DirectCDPClient,
    labels: tuple[str, ...] = TIKTOK_CONFIRM_MODAL_LABELS,
) -> dict[str, Any] | None:
    """
    Finds and trusted-clicks a visible, enabled confirmation button strictly INSIDE a visible
    modal overlay (`[role="dialog"], .TUXModal, [class*="modal"], [class*="Modal"]`).
    Never clicks background page elements outside a modal container, and explicitly refuses/skips
    any modal whose text or DOM matches CAPTCHA/verification markers via `detect_tiktok_captcha`.
    """
    clean_labels = [str(lbl or "").strip() for lbl in labels if str(lbl or "").strip()]
    if not clean_labels:
        return None

    probe = await client.eval(
        f"""
        (() => {{
            const url = location.href || '';
            const targets = {json.dumps([lbl.lower() for lbl in clean_labels])};
            const modalSel = {json.dumps(TIKTOK_MODAL_CONTAINER_SELECTOR)};
            const captchaSelectors = [
                '#captcha-verify-container-main-page',
                '.captcha-verify-container',
                '#tiktok-verify-ele',
                '[id*="secsdk-captcha"]',
                '[class*="secsdk-captcha"]',
                '[class*="captcha-verify"]',
                'iframe[src*="captcha"]'
            ];
            const modals = Array.from(document.querySelectorAll(modalSel)).filter(m => {{
                const st = window.getComputedStyle ? window.getComputedStyle(m) : null;
                if (st && (st.display === 'none' || st.visibility === 'hidden' || st.opacity === '0')) return false;
                const r = m.getBoundingClientRect();
                return r.width > 0 && r.height > 0;
            }});
            const modalSummaries = [];
            const candidates = [];
            for (const modal of modals) {{
                const modalText = (modal.innerText || modal.textContent || '').slice(0, 2000);
                const domCaptcha = [];
                for (const cSel of captchaSelectors) {{
                    const hit = (modal.matches && modal.matches(cSel)) ? modal : modal.querySelector(cSel);
                    if (hit) {{
                        const hr = hit.getBoundingClientRect();
                        if (hr.width > 0 && hr.height > 0) {{
                            domCaptcha.push('dom:' + cSel);
                        }}
                    }}
                }}
                modalSummaries.push({{ modalText, domCaptcha }});
                if (domCaptcha.length > 0) {{
                    continue;
                }}
                const btns = Array.from(
                    modal.querySelectorAll('button, [role="button"], a[role="button"], [class*="TUXButton"]')
                ).filter(e => {{
                    const st = window.getComputedStyle ? window.getComputedStyle(e) : null;
                    if (st && (st.display === 'none' || st.visibility === 'hidden' || st.pointerEvents === 'none')) return false;
                    const r = e.getBoundingClientRect();
                    return r.width > 0 && r.height > 0 && !e.disabled && e.getAttribute('aria-disabled') !== 'true';
                }});
                for (let idx = 0; idx < targets.length; idx++) {{
                    const t = targets[idx];
                    const match = btns.find(e => (e.innerText || e.textContent || '').trim().toLowerCase() === t);
                    if (match) {{
                        const r = match.getBoundingClientRect();
                        candidates.push({{
                            priority: idx,
                            label: (match.innerText || match.textContent || '').trim(),
                            x: r.left,
                            y: r.top,
                            w: r.width,
                            h: r.height,
                            modalText,
                            domCaptcha,
                        }});
                    }}
                }}
            }}
            candidates.sort((a, b) => a.priority - b.priority);
            return {{ url, modals: modalSummaries, candidates }};
        }})()
        """
    )

    if not isinstance(probe, dict):
        return None

    page_url = str(probe.get("url") or "")
    modals = probe.get("modals") or []
    if isinstance(modals, list):
        for m in modals:
            if not isinstance(m, dict):
                continue
            if detect_tiktok_captcha(
                page_url,
                str(m.get("modalText") or ""),
                m.get("domCaptcha") or [],
            ):
                return None

    candidates = probe.get("candidates") or []
    if not isinstance(candidates, list) or not candidates:
        return None

    for cand in candidates:
        if not isinstance(cand, dict):
            continue
        if float(cand.get("w") or 0) <= 0 or float(cand.get("h") or 0) <= 0:
            continue
        if detect_tiktok_captcha(
            page_url,
            str(cand.get("modalText") or ""),
            cand.get("domCaptcha") or [],
        ):
            return None
        cx, cy = await _trusted_click_point(
            client,
            float(cand["x"]),
            float(cand["y"]),
            float(cand["w"]),
            float(cand["h"]),
        )
        return {
            "clicked": True,
            "label": str(cand.get("label") or ""),
            "x": cx,
            "y": cy,
            "w": float(cand["w"]),
            "h": float(cand["h"]),
        }
    return None


async def _trusted_click_labels(client: DirectCDPClient, labels: list[str]) -> dict[str, Any] | None:
    return await _trusted_click_js(
        client,
        f"""
        (() => {{
            const targets = {json.dumps([x.lower() for x in labels])};
            const nodes = Array.from(
                document.querySelectorAll('button, div[role="button"], span[role="button"], a[role="button"], div, span')
            ).filter(e => {{
                const r = e.getBoundingClientRect();
                return r.width > 0 && r.height > 0 && !e.disabled && e.getAttribute('aria-disabled') !== 'true';
            }});
            for (const t of targets) {{
                const exact = nodes.find(e => (e.innerText || '').trim().toLowerCase() === t);
                if (exact) {{
                    exact.scrollIntoView({{block: 'center'}});
                    const r = exact.getBoundingClientRect();
                    return {{ x: r.left, y: r.top, w: r.width, h: r.height, text: (exact.innerText || '').trim() }};
                }}
            }}
            return null;
        }})()
        """,
    )


async def _press_key(client: DirectCDPClient, key: str, code: str, vk: int, modifiers: int = 0) -> None:
    await client.send(
        "Input.dispatchKeyEvent",
        {"type": "keyDown", "modifiers": modifiers, "key": key, "code": code, "windowsVirtualKeyCode": vk},
    )
    await asyncio.sleep(0.04)
    await client.send(
        "Input.dispatchKeyEvent",
        {"type": "keyUp", "modifiers": modifiers, "key": key, "code": code, "windowsVirtualKeyCode": vk},
    )
    await asyncio.sleep(0.06)


async def _trusted_fill_input(client: DirectCDPClient, selectors: list[str], value: str) -> bool:
    rect = await _trusted_click_js(
        client,
        f"""
        (() => {{
            const sels = {json.dumps(selectors)};
            for (const s of sels) {{
                const nodes = Array.from(document.querySelectorAll(s));
                const el = nodes.find(n => n.getBoundingClientRect().width > 0) || nodes[0];
                if (!el) continue;
                el.scrollIntoView({{block: 'center'}});
                const r = el.getBoundingClientRect();
                if (r.width > 0 && r.height > 0) {{
                    return {{ x: r.left, y: r.top, w: r.width, h: r.height, selector: s }};
                }}
            }}
            return null;
        }})()
        """,
    )
    if not rect:
        return False
    await asyncio.sleep(0.15)
    await _press_key(client, "a", "KeyA", 65, modifiers=2)
    await _press_key(client, "Backspace", "Backspace", 8)
    await asyncio.sleep(0.12)
    await client.send("Input.insertText", {"text": value})
    await asyncio.sleep(0.2)
    return True


async def _handle_child_google_oauth_popup(
    *,
    parent_target_id: str,
    account_email: str = DEFAULT_GOOGLE_ACCOUNT_EMAIL,
    cdp_host: str = DEFAULT_CDP_HOST,
    cdp_port: int = DEFAULT_CDP_PORT,
    max_wait_sec: float = 25.0,
) -> dict[str, Any]:
    """
    Waits for and interacts ONLY with a child `accounts.google.com` OAuth popup opened by
    `parent_target_id` (`openerId == parent_target_id`), selecting `account_email` and clicking
    `Continue` / `Allow` until the popup closes on its own.
    """
    deadline = asyncio.get_event_loop().time() + float(max_wait_sec)
    popup_tid = ""
    popup_ws = ""
    while asyncio.get_event_loop().time() < deadline:
        try:
            with urllib.request.urlopen(f"http://{cdp_host}:{int(cdp_port)}/json/list", timeout=4.0) as resp:
                targets = json.loads(resp.read().decode("utf-8"))
        except Exception:
            targets = []
        matches = find_child_google_oauth_targets(targets, parent_target_id=parent_target_id)
        if matches:
            popup_tid = str(matches[0].get("id") or "")
            popup_ws = str(
                matches[0].get("webSocketDebuggerUrl")
                or f"ws://{cdp_host}:{int(cdp_port)}/devtools/page/{popup_tid}"
            )
            break
        await asyncio.sleep(0.8)

    if not popup_tid or not popup_ws:
        return {"handled": False, "reason": "no_child_oauth_popup"}

    steps: list[str] = []
    email_low = account_email.strip().lower()
    for _ in range(18):
        try:
            with urllib.request.urlopen(f"http://{cdp_host}:{int(cdp_port)}/json/list", timeout=4.0) as resp:
                live_targets = json.loads(resp.read().decode("utf-8"))
            if not any(str(t.get("id") or "") == popup_tid for t in live_targets if isinstance(t, dict)):
                return {"handled": True, "popup_target_id": popup_tid, "steps": steps, "closed": True}
        except Exception:
            pass

        try:
            async with DirectCDPClient(popup_ws) as p_client:
                st = await _inspect_tiktok_page(p_client)
                p_captcha = detect_tiktok_captcha(
                    str(st.get("url") or ""),
                    str(st.get("bodyText") or ""),
                    st.get("domCaptcha") or [],
                )
                if p_captcha:
                    return {
                        "handled": False,
                        "reason": "oauth_captcha_detected",
                        "markers": p_captcha,
                        "popup_target_id": popup_tid,
                    }

                action = await p_client.eval(
                    f"""
                    (() => {{
                        const wantEmail = {json.dumps(email_low)};
                        const emailNode = Array.from(document.querySelectorAll('[data-identifier], li, div[role="link"], div[role="button"]'))
                            .find(el => {{
                                const idAttr = (el.getAttribute && (el.getAttribute('data-identifier') || '')).toLowerCase();
                                const txt = (el.innerText || el.textContent || '').toLowerCase();
                                const r = el.getBoundingClientRect();
                                return r.width > 0 && r.height > 0 && (idAttr === wantEmail || txt.includes(wantEmail));
                            }});
                        if (emailNode) {{
                            emailNode.click();
                            return 'clicked_account:' + wantEmail;
                        }}
                        const channelNode = Array.from(document.querySelectorAll('li, div[role="link"], div[role="button"]'))
                            .find(el => {{
                                const txt = (el.innerText || el.textContent || '').toLowerCase();
                                const r = el.getBoundingClientRect();
                                return r.width > 0 && r.height > 0 && (txt.includes('all about brain') || txt.includes('@allaboutbrainofficial'));
                            }});
                        if (channelNode) {{
                            channelNode.click();
                            return 'clicked_channel:all_about_brain';
                        }}
                        const btnLabels = ['continue', 'allow', 'confirm', '계속', '허용', '확인'];
                        const btns = Array.from(document.querySelectorAll('button, div[role="button"], input[type="submit"]'))
                            .filter(el => {{
                                const r = el.getBoundingClientRect();
                                return r.width > 0 && r.height > 0 && !el.disabled;
                            }});
                        for (const want of btnLabels) {{
                            const b = btns.find(el => (el.innerText || el.value || el.textContent || '').trim().toLowerCase() === want)
                                || btns.find(el => (el.innerText || el.value || el.textContent || '').trim().toLowerCase().includes(want));
                            if (b) {{
                                b.click();
                                return 'clicked_btn:' + (b.innerText || el.value || b.textContent || '').trim();
                            }}
                        }}
                        return null;
                    }})()
                    """
                )
                if action:
                    steps.append(str(action))
        except Exception:
            return {"handled": bool(steps), "popup_target_id": popup_tid, "steps": steps, "closed": True}
        await asyncio.sleep(2.0)

    return {"handled": bool(steps), "popup_target_id": popup_tid, "steps": steps, "closed": False}


async def configure_tiktok_profile_cdp(
    *,
    avatar_path: Path | str | None = None,
    display_name: str = DEFAULT_TIKTOK_DISPLAY_NAME,
    handle_candidates: tuple[str, ...] | list[str] = DEFAULT_TIKTOK_HANDLE_CANDIDATES,
    bio_candidates: tuple[str, ...] | list[str] = DEFAULT_TIKTOK_BIO_CANDIDATES,
    google_account_email: str = DEFAULT_GOOGLE_ACCOUNT_EMAIL,
    link_youtube: bool = True,
    allow_google_login_if_logged_out: bool = True,
    verification_screenshot_path: Path | str | None = None,
    branded_screenshot_path: Path | str | None = None,
    cdp_host: str = DEFAULT_CDP_HOST,
    cdp_port: int = DEFAULT_CDP_PORT,
    existing_target_id: str | None = None,
    owner_id: str | None = None,
    close_tab_on_finish: bool = False,
) -> dict[str, Any]:
    """
    Configures the official `ALL ABOUT BRAIN` TikTok creator profile in an isolated background CDP tab:
      1. Verifies existing `.tiktok.com` login session (or runs `Continue with Google` if logged out).
      2. Halts immediately without interacting if any CAPTCHA or birthday prompt appears.
      3. Opens `Edit profile` via trusted CDP mouse events and applies avatar, username,
         display name (`ALL ABOUT BRAIN`), and `<= 80`-char DOI-verified bio.
      4. Confirms `[data-e2e="set-username-popup-confirm"]` and saves `branded_screenshot_path`.
    """
    validated_handles = [validate_tiktok_username_candidate(h) for h in handle_candidates]
    chosen_bio = select_tiktok_bio(bio_candidates)
    resolved_avatar = resolve_avatar_path(avatar_path)

    eff_owner = owner_id or f"pid:{os.getpid()}:tiktok_setup_operator"
    if existing_target_id:
        tid = existing_target_id
        acquire_tab_lease(
            tid,
            owner_id=eff_owner,
            purpose="tiktok_setup_operator",
            cdp_port=cdp_port,
            created_by_pipeline=True,
        )
        ws_url = f"ws://{cdp_host}:{int(cdp_port)}/devtools/page/{tid}"
    else:
        opened = open_leased_cdp_tab(
            "about:blank",
            owner_id=eff_owner,
            purpose="tiktok_setup_operator",
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
                {"width": 1440, "height": 960, "deviceScaleFactor": 1, "mobile": False},
            )
            await client.send("Page.navigate", {"url": "https://www.tiktok.com/profile?lang=en"})
            await asyncio.sleep(6.0)
            renew_tab_lease(tid, owner_id=eff_owner, cdp_port=cdp_port)

            st = await _inspect_tiktok_page(client)
            cap = detect_tiktok_captcha(
                str(st.get("url") or ""),
                str(st.get("bodyText") or ""),
                st.get("domCaptcha") or [],
            )
            if cap:
                keep_open = True
                shot = (
                    str(await capture_background_png(client, Path(verification_screenshot_path)))
                    if verification_screenshot_path
                    else None
                )
                return {
                    "status": "captcha_verification_needed",
                    "target_id": tid,
                    "lease_owner_id": eff_owner,
                    "markers": cap,
                    "screenshot_path": shot,
                }

            bday = detect_tiktok_birthday_gate(str(st.get("url") or ""), str(st.get("bodyText") or ""))
            if bday:
                keep_open = True
                shot = (
                    str(await capture_background_png(client, Path(verification_screenshot_path)))
                    if verification_screenshot_path
                    else None
                )
                return {
                    "status": "birthday_input_needed",
                    "target_id": tid,
                    "lease_owner_id": eff_owner,
                    "markers": bday,
                    "screenshot_path": shot,
                }

            cur_url = str(st.get("url") or "")
            is_logged_out = "/login" in cur_url.lower() or not bool(
                await client.eval(
                    r"""
                    (() => Boolean(
                        document.querySelector('[data-e2e="edit-profile-entrance"]')
                        || document.querySelector('[data-e2e="user-title"]')
                        || /tiktok\.com\/@[^/?#]+/i.test(location.href)
                    ))()
                    """
                )
            )
            oauth_result: dict[str, Any] | None = None
            if is_logged_out and allow_google_login_if_logged_out:
                await client.send("Page.navigate", {"url": "https://www.tiktok.com/login?lang=en"})
                await asyncio.sleep(4.5)
                st = await _inspect_tiktok_page(client)
                cap = detect_tiktok_captcha(
                    str(st.get("url") or ""),
                    str(st.get("bodyText") or ""),
                    st.get("domCaptcha") or [],
                )
                if cap:
                    keep_open = True
                    shot = (
                        str(await capture_background_png(client, Path(verification_screenshot_path)))
                        if verification_screenshot_path
                        else None
                    )
                    return {
                        "status": "captcha_verification_needed",
                        "target_id": tid,
                        "lease_owner_id": eff_owner,
                        "markers": cap,
                        "screenshot_path": shot,
                    }
                await _trusted_click_labels(client, ["Continue with Google"])
                oauth_result = await _handle_child_google_oauth_popup(
                    parent_target_id=tid,
                    account_email=google_account_email,
                    cdp_host=cdp_host,
                    cdp_port=cdp_port,
                )
                await asyncio.sleep(5.0)
                await client.send("Page.navigate", {"url": "https://www.tiktok.com/profile?lang=en"})
                await asyncio.sleep(5.5)

            opened_edit = bool(
                await _trusted_click_js(
                    client,
                    r"""(() => {
                        const el = document.querySelector('[data-e2e="edit-profile-entrance"]');
                        if (!el) return null;
                        const r = el.getBoundingClientRect();
                        return { x: r.left, y: r.top, w: r.width, h: r.height };
                    })()""",
                )
                or await _trusted_click_labels(client, ["Edit profile"])
            )
            await asyncio.sleep(2.5)

            # 1. Avatar upload + crop modal Apply
            avatar_applied = False
            if opened_edit and resolved_avatar and resolved_avatar.exists():
                avatar_applied = await client.set_file_input(
                    resolved_avatar,
                    '[data-e2e="edit-profile-avatar-edit-icon"] input[type="file"], [data-e2e="edit-profile-avatar"] input[type="file"], input[type="file"][accept*="image"], input[type="file"]',
                )
                if avatar_applied:
                    await asyncio.sleep(2.8)
                    await _trusted_click_labels(client, ["Apply"])
                    await asyncio.sleep(2.2)

            # 2. Username selection (in priority order, ignoring static tip text)
            current_handle = str(
                await client.eval(
                    r"""
                    (() => {
                        const m = location.pathname.match(/^\/@([^/?#]+)/);
                        if (m) return m[1];
                        const sub = document.querySelector('[data-e2e="user-subtitle"]');
                        return sub ? (sub.innerText || '').trim().replace(/^@/, '') : '';
                    })()
                    """
                )
                or ""
            ).strip()

            selected_handle = current_handle
            if opened_edit and current_handle.lower() not in {h.lower() for h in validated_handles}:
                for cand in validated_handles:
                    ok_u = await _trusted_fill_input(
                        client,
                        [
                            '[data-e2e="edit-profile-username-input"] input',
                            'input[placeholder*="Username"]',
                        ],
                        cand,
                    )
                    if not ok_u:
                        break
                    await asyncio.sleep(3.0)
                    unavailable = bool(
                        await client.eval(
                            r"""
                            (() => {
                                const box = document.querySelector('[data-e2e="edit-profile-username-input"]');
                                if (!box) return false;
                                const txt = (box.innerText || '').toLowerCase();
                                return (
                                    txt.includes("isn't available")
                                    || txt.includes("not available")
                                    || txt.includes("already taken")
                                    || txt.includes("can't use this username")
                                    || txt.includes("can only be changed once")
                                );
                            })()
                            """
                        )
                    )
                    if not unavailable:
                        selected_handle = cand
                        break

            # 3. Display Name
            name_applied = False
            if opened_edit and display_name.strip():
                name_applied = await _trusted_fill_input(
                    client,
                    [
                        '[data-e2e="edit-profile-name-input"] input',
                        'input[placeholder*="Name"]',
                    ],
                    display_name.strip(),
                )
                await asyncio.sleep(0.8)

            # 4. Bio (<= 80 UTF-16 code units)
            bio_applied = False
            if opened_edit and chosen_bio:
                for b_cand in [chosen_bio, *bio_candidates]:
                    b_clean = (b_cand or "").strip()
                    if not b_clean or utf16_code_units(b_clean) > TIKTOK_BIO_MAX_UTF16_UNITS:
                        continue
                    ok_b = await _trusted_fill_input(
                        client,
                        [
                            'textarea[data-e2e="edit-profile-bio-input"]',
                            '[data-e2e="edit-profile-bio-input"] textarea',
                            'textarea[placeholder*="Bio"]',
                        ],
                        b_clean,
                    )
                    if not ok_b:
                        break
                    await asyncio.sleep(0.8)
                    chosen_bio = b_clean
                    bio_applied = True
                    break

            # 5. Optional Social -> Add YouTube OAuth link (when exposed on platform)
            youtube_link_result: dict[str, Any] | None = None
            if opened_edit and link_youtube:
                yt_clicked = await _trusted_click_labels(client, ["Add YouTube"])
                if yt_clicked:
                    youtube_link_result = await _handle_child_google_oauth_popup(
                        parent_target_id=tid,
                        account_email=google_account_email,
                        cdp_host=cdp_host,
                        cdp_port=cdp_port,
                    )
                    await asyncio.sleep(2.5)

            # 6. Click Save + confirm `[data-e2e="set-username-popup-confirm"]`
            if opened_edit:
                saved_btn = await _trusted_click_js(
                    client,
                    r"""(() => {
                        const el = document.querySelector('[data-e2e="edit-profile-save"]');
                        if (!el || el.disabled || el.getAttribute('aria-disabled') === 'true') return null;
                        const r = el.getBoundingClientRect();
                        return { x: r.left, y: r.top, w: r.width, h: r.height };
                    })()""",
                )
                if saved_btn:
                    await asyncio.sleep(2.5)
                    await _trusted_click_js(
                        client,
                        r"""(() => {
                            const el = document.querySelector('[data-e2e="set-username-popup-confirm"]');
                            if (!el) return null;
                            const r = el.getBoundingClientRect();
                            return { x: r.left, y: r.top, w: r.width, h: r.height };
                        })()""",
                    ) or await _trusted_click_labels(client, ["Confirm", "Set username"])
                    await asyncio.sleep(6.0)

            await client.send("Page.navigate", {"url": "https://www.tiktok.com/profile?lang=en"})
            await asyncio.sleep(5.5)
            st_after = await _inspect_tiktok_page(client)
            cap_after = detect_tiktok_captcha(
                str(st_after.get("url") or ""),
                str(st_after.get("bodyText") or ""),
                st_after.get("domCaptcha") or [],
            )
            if cap_after:
                keep_open = True
                shot = (
                    str(await capture_background_png(client, Path(verification_screenshot_path)))
                    if verification_screenshot_path
                    else None
                )
                return {
                    "status": "captcha_verification_needed",
                    "target_id": tid,
                    "lease_owner_id": eff_owner,
                    "markers": cap_after,
                    "screenshot_path": shot,
                }

            profile_meta: dict[str, Any] = (
                await client.eval(
                    r"""
                    (() => {
                        const m = location.pathname.match(/^\/@([^/?#]+)/);
                        const handle = m ? m[1] : (document.querySelector('[data-e2e="user-subtitle"]')?.innerText || '').trim().replace(/^@/, '');
                        const title = (document.querySelector('[data-e2e="user-title"]')?.innerText || '').trim();
                        const bio = (document.querySelector('[data-e2e="user-bio"]')?.innerText || '').trim();
                        return { url: location.href, handle, display_name: title, bio };
                    })()
                    """
                )
                or {}
            )

            verified_shot = (
                str(await capture_background_png(client, Path(branded_screenshot_path)))
                if branded_screenshot_path
                else None
            )
            return {
                "status": "ok",
                "target_id": tid,
                "lease_owner_id": eff_owner,
                "handle": f"@{str(profile_meta.get('handle') or selected_handle).lstrip('@')}",
                "display_name": str(profile_meta.get("display_name") or display_name),
                "bio": str(profile_meta.get("bio") or chosen_bio),
                "profile_url": str(profile_meta.get("url") or ""),
                "avatar_applied": avatar_applied,
                "name_applied": name_applied,
                "bio_applied": bio_applied,
                "oauth_login": oauth_result,
                "youtube_link": youtube_link_result,
                "screenshot_path": verified_shot,
            }
    finally:
        cleanup_staged_bridge_files()
        if close_tab_on_finish and not keep_open:
            release_and_close_leased_tab(tid, owner_id=eff_owner, cdp_port=cdp_port, cdp_host=cdp_host)


TIKTOK_MIN_DURATION_SEC: float = 60.0
TIKTOK_MAX_PINNED_VIDEOS: int = 3


def probe_tiktok_video_duration_sec(video_path: Path | str) -> float:
    p = Path(video_path)
    if not p.is_file():
        return 0.0
    try:
        import cv2

        cap = cv2.VideoCapture(str(p))
        if cap.isOpened():
            fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
            frames = float(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0.0)
            cap.release()
            if fps > 0.0 and frames > 0.0:
                return round(frames / fps, 3)
        else:
            cap.release()
    except Exception:
        pass
    try:
        proc = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(p),
            ],
            capture_output=True,
            text=True,
            timeout=10.0,
            check=False,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            return round(float(proc.stdout.strip()), 3)
    except Exception:
        pass
    return 0.0


def validate_tiktok_over_60s_and_sound_lock(
    video_path: Path | str,
    *,
    min_duration_sec: float = TIKTOK_MIN_DURATION_SEC,
    commercial_sound_id: str | None = None,
    duration_override_sec: float | None = None,
) -> float:
    """
    Enforces TikTok `>= 60.0s` Creator Rewards duration floor and permanent ban on adding
    `1-3%` commercial/trending sounds to `>60s` videos (which triggers 60s audio mutes).
    """
    if commercial_sound_id and str(commercial_sound_id).strip():
        raise ValueError(
            "Adding commercial or trending sounds to >60s TikTok videos is strictly prohibited "
            "(triggers 60s UMG/commercial audio mute and Creator Rewards disqualification)."
        )
    dur = (
        float(duration_override_sec)
        if duration_override_sec is not None
        else probe_tiktok_video_duration_sec(video_path)
    )
    if min_duration_sec > 0.0 and dur < float(min_duration_sec):
        raise ValueError(
            f"TikTok video duration {dur:.2f}s is below required {float(min_duration_sec):.1f}s Creator Rewards floor."
        )
    return dur


def parse_tiktok_schedule_utc(
    schedule_at_utc: datetime | str,
    *,
    now_utc: datetime | None = None,
    enforce_future: bool = True,
) -> datetime:
    if isinstance(schedule_at_utc, datetime):
        dt = (
            schedule_at_utc.replace(tzinfo=timezone.utc)
            if schedule_at_utc.tzinfo is None
            else schedule_at_utc.astimezone(timezone.utc)
        )
    else:
        raw = str(schedule_at_utc or "").strip()
        if not raw:
            raise ValueError("schedule_at_utc cannot be empty")
        cleaned = re.sub(r"\s+UTC$", "", raw, flags=re.IGNORECASE).replace("Z", "+00:00")
        dt_parsed: datetime | None = None
        for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%dT%H:%M:%S"):
            try:
                dt_parsed = datetime.strptime(cleaned, fmt).replace(tzinfo=timezone.utc)
                break
            except ValueError:
                continue
        if dt_parsed is None:
            iso_dt = datetime.fromisoformat(cleaned)
            dt_parsed = iso_dt.replace(tzinfo=timezone.utc) if iso_dt.tzinfo is None else iso_dt.astimezone(timezone.utc)
        dt = dt_parsed

    if dt.minute % 5 != 0:
        raise ValueError(
            f"TikTok Studio schedule time must align to 5-minute increments (:00, :05, ...); got {dt.strftime('%H:%M')} UTC"
        )
    ref_now = now_utc or datetime.now(timezone.utc)
    if enforce_future:
        if dt < ref_now + timedelta(minutes=15):
            raise ValueError("TikTok Studio schedule time must be at least 15 minutes in the future")
        if dt > ref_now + timedelta(days=10):
            raise ValueError("TikTok Studio desktop scheduler supports up to 10 days in advance")
    return dt


async def upload_tiktok_video_cdp(
    *,
    video_path: Path | str,
    cover_path: Path | str,
    caption: str,
    handle: str = DEFAULT_TIKTOK_HANDLE,
    enable_aigc_disclosure: bool = True,
    visibility: str = "Everyone",
    schedule_at_utc: datetime | str | None = None,
    min_duration_sec: float = TIKTOK_MIN_DURATION_SEC,
    commercial_sound_id: str | None = None,
    duration_override_sec: float | None = None,
    dry_run: bool = False,
    caption_save_path: Path | str | None = None,
    receipt_path: Path | str | None = None,
    verification_screenshot_path: Path | str | None = None,
    live_screenshot_path: Path | str | None = None,
    cdp_host: str = DEFAULT_CDP_HOST,
    cdp_port: int = DEFAULT_CDP_PORT,
    existing_target_id: str | None = None,
    owner_id: str | None = None,
    close_tab_on_finish: bool = True,
) -> dict[str, Any]:
    """
    Uploads (or schedules) a clean vertical `9:16` (`1080x1920`, `>= 60.0s`) MP4 to TikTok Studio
    (`tiktok.com/tiktokstudio/upload?lang=en`) with strict zero commercial sound and immediate CAPTCHA halt.
    """
    v_path = Path(video_path).resolve()
    c_path = Path(cover_path).resolve()
    if not v_path.exists():
        raise FileNotFoundError(f"TikTok video file missing: {v_path}")
    if not c_path.exists():
        raise FileNotFoundError(f"TikTok cover file missing: {c_path}")
    clean_caption = (caption or "").strip()
    if not clean_caption:
        raise ValueError("TikTok caption must be non-empty")
    if len(clean_caption) > TIKTOK_CAPTION_MAX_CHARS:
        raise ValueError(f"TikTok caption exceeds {TIKTOK_CAPTION_MAX_CHARS} chars ({len(clean_caption)})")

    duration_sec = validate_tiktok_over_60s_and_sound_lock(
        v_path,
        min_duration_sec=min_duration_sec,
        commercial_sound_id=commercial_sound_id,
        duration_override_sec=duration_override_sec,
    )
    dt_sched_utc = (
        parse_tiktok_schedule_utc(schedule_at_utc, enforce_future=not dry_run)
        if schedule_at_utc is not None
        else None
    )

    if caption_save_path:
        cp = Path(caption_save_path)
        cp.parent.mkdir(parents=True, exist_ok=True)
        cp.write_text(clean_caption + "\n", encoding="utf-8")

    if dry_run:
        return {
            "status": "dry_run",
            "platform": "tiktok",
            "mode": "scheduled" if dt_sched_utc else "immediate",
            "scheduled_at_utc": dt_sched_utc.strftime("%Y-%m-%dT%H:%M:%SZ") if dt_sched_utc else None,
            "duration_sec": duration_sec,
            "commercial_sound_prohibited": True,
            "aigc_disclosure_required": bool(enable_aigc_disclosure),
            "handle": f"@{handle.strip().lstrip('@')}",
            "video_path": str(v_path),
            "cover_path": str(c_path),
            "caption_chars": len(clean_caption),
        }

    eff_owner = owner_id or f"pid:{os.getpid()}:tiktok_setup_operator"
    if existing_target_id:
        tid = existing_target_id
        acquire_tab_lease(
            tid,
            owner_id=eff_owner,
            purpose="tiktok_setup_operator",
            cdp_port=cdp_port,
            created_by_pipeline=True,
        )
        ws_url = f"ws://{cdp_host}:{int(cdp_port)}/devtools/page/{tid}"
    else:
        opened = open_leased_cdp_tab(
            "about:blank",
            owner_id=eff_owner,
            purpose="tiktok_setup_operator",
            cdp_port=cdp_port,
            cdp_host=cdp_host,
            background=True,
        )
        tid = str(opened["id"])
        ws_url = str(opened.get("webSocketDebuggerUrl") or f"ws://{cdp_host}:{int(cdp_port)}/devtools/page/{tid}")

    keep_open = False
    succeeded = False
    clean_handle = handle.strip().lstrip("@")
    try:
        async with DirectCDPClient(ws_url) as client:
            await client.send(
                "Emulation.setDeviceMetricsOverride",
                {"width": 1440, "height": 1020, "deviceScaleFactor": 1, "mobile": False},
            )
            await client.send("Page.navigate", {"url": "https://www.tiktok.com/tiktokstudio/upload?lang=en"})
            await asyncio.sleep(6.5)
            renew_tab_lease(tid, owner_id=eff_owner, cdp_port=cdp_port)

            st = await _inspect_tiktok_page(client)
            cap = detect_tiktok_captcha(
                str(st.get("url") or ""),
                str(st.get("bodyText") or ""),
                st.get("domCaptcha") or [],
            )
            if cap:
                keep_open = True
                shot = (
                    str(await capture_background_png(client, Path(verification_screenshot_path)))
                    if verification_screenshot_path
                    else None
                )
                return {
                    "status": "captcha_verification_needed",
                    "target_id": tid,
                    "lease_owner_id": eff_owner,
                    "markers": cap,
                    "screenshot_path": shot,
                }

            ok_vid = await client.set_file_input(
                v_path,
                'input[type="file"][accept*="video"], input[type="file"]',
            )
            if not ok_vid:
                raise RuntimeError("Failed to attach MP4 to TikTok Studio upload file input")

            upload_ready = False
            for _ in range(90):
                await asyncio.sleep(2.5)
                renew_tab_lease(tid, owner_id=eff_owner, cdp_port=cdp_port)
                st_up = await _inspect_tiktok_page(client)
                cap_up = detect_tiktok_captcha(
                    str(st_up.get("url") or ""),
                    str(st_up.get("bodyText") or ""),
                    st_up.get("domCaptcha") or [],
                )
                if cap_up:
                    keep_open = True
                    shot = (
                        str(await capture_background_png(client, Path(verification_screenshot_path)))
                        if verification_screenshot_path
                        else None
                    )
                    return {
                        "status": "captcha_verification_needed",
                        "target_id": tid,
                        "lease_owner_id": eff_owner,
                        "markers": cap_up,
                        "screenshot_path": shot,
                    }

                ready_state = await client.eval(
                    r"""
                    (() => {
                        const editor = document.querySelector('[data-e2e="caption_container"] .public-DraftEditor-content, .public-DraftEditor-content[contenteditable="true"]');
                        if (!editor) return false;
                        const txt = (document.body ? document.body.innerText : '');
                        const uploaded = /\buploaded\b/i.test(txt);
                        const postBtn = document.querySelector('[data-e2e="post_video_button"]');
                        const postEnabled = Boolean(postBtn && !postBtn.disabled && postBtn.getAttribute('aria-disabled') !== 'true');
                        return uploaded || postEnabled;
                    })()
                    """
                )
                if ready_state:
                    upload_ready = True
                    break

            if not upload_ready:
                raise TimeoutError("Timed out waiting for TikTok Studio MP4 upload to finish processing")

            # Dismiss automatic-checks modal & onboarding tooltips
            for label in ("Turn on", "Got it", "Not now"):
                await _trusted_click_labels(client, [label])
                await asyncio.sleep(0.8)

            # Populate Draft.js caption editor cleanly
            await _trusted_click_js(
                client,
                r"""(() => {
                    const ed = document.querySelector('[data-e2e="caption_container"] .public-DraftEditor-content')
                        || document.querySelector('.public-DraftEditor-content[contenteditable="true"]');
                    if (!ed) return null;
                    ed.scrollIntoView({block: 'center'});
                    const r = ed.getBoundingClientRect();
                    return { x: r.left, y: r.top, w: r.width, h: r.height };
                })()""",
            )
            await asyncio.sleep(0.25)
            await _press_key(client, "a", "KeyA", 65, modifiers=2)
            await _press_key(client, "Backspace", "Backspace", 8)
            await asyncio.sleep(0.25)

            lines = clean_caption.split("\n")
            for idx, line in enumerate(lines):
                if line.strip().startswith("#"):
                    tags = [t.strip() for t in line.strip().split() if t.strip()]
                    for t_idx, tag in enumerate(tags):
                        await client.send("Input.insertText", {"text": tag})
                        await asyncio.sleep(0.75)
                        await _press_key(client, "Escape", "Escape", 27)
                        if t_idx + 1 < len(tags):
                            await client.send("Input.insertText", {"text": " "})
                            await asyncio.sleep(0.12)
                else:
                    if line:
                        await client.send("Input.insertText", {"text": line})
                        await asyncio.sleep(0.12)
                    if idx + 1 < len(lines):
                        await _press_key(client, "Enter", "Enter", 13)
                        await asyncio.sleep(0.08)

            # Custom Cover: Edit cover -> Upload cover -> attach cover_path -> Save
            cover_applied = False
            edit_cov = await _trusted_click_js(
                client,
                r"""(() => {
                    const c = document.querySelector('[data-e2e="cover_container"]');
                    if (!c) return null;
                    c.scrollIntoView({block: 'center'});
                    const r = c.getBoundingClientRect();
                    return { x: r.left, y: r.top, w: r.width, h: r.height };
                })()""",
            )
            if edit_cov:
                await asyncio.sleep(2.0)
                await _trusted_click_labels(client, ["Upload cover"])
                await asyncio.sleep(1.2)
                cover_applied = await client.set_file_input(
                    c_path,
                    'input[type="file"][accept*="image"], input[type="file"][accept*="png"], input[type="file"]:not([accept*="video"])',
                )
                if cover_applied:
                    await asyncio.sleep(3.2)
                    await _trusted_click_labels(client, ["Save", "Confirm", "Apply"])
                    await asyncio.sleep(2.8)

            # Visibility: Everyone (Public)
            if visibility:
                vis_ok = await client.eval(
                    f"""(() => {{
                        const vis = document.querySelector('[data-e2e="video_visibility_container"]');
                        return vis ? (vis.innerText || '').toLowerCase().includes({json.dumps(visibility.lower())}) : false;
                    }})()"""
                )
                if not vis_ok:
                    await _trusted_click_js(
                        client,
                        r"""(() => {
                            const vis = document.querySelector('[data-e2e="video_visibility_container"] [role="combobox"]');
                            if (!vis) return null;
                            vis.scrollIntoView({block: 'center'});
                            const r = vis.getBoundingClientRect();
                            return { x: r.left, y: r.top, w: r.width, h: r.height };
                        })()""",
                    )
                    await asyncio.sleep(0.8)
                    await _trusted_click_labels(client, [visibility])
                    await asyncio.sleep(0.6)

            # Show more -> AI-generated content = ON
            aigc_enabled = False
            if enable_aigc_disclosure:
                aigc_visible = bool(
                    await client.eval(
                        r"""(() => {
                            const aigc = document.querySelector('[data-e2e="aigc_container"]');
                            return Boolean(aigc && aigc.getBoundingClientRect().height > 0);
                        })()"""
                    )
                )
                if not aigc_visible:
                    await _trusted_click_js(
                        client,
                        r"""(() => {
                            const adv = document.querySelector('[data-e2e="advanced_settings_container"]');
                            if (!adv) return null;
                            adv.scrollIntoView({block: 'center'});
                            const r = adv.getBoundingClientRect();
                            return { x: r.left, y: r.top, w: r.width, h: r.height };
                        })()""",
                    )
                    await asyncio.sleep(1.4)

                already_on = bool(
                    await client.eval(
                        r"""(() => {
                            const sw = document.querySelector('[data-e2e="aigc_container"] [role="switch"], [data-e2e="aigc_container"] input[type="checkbox"]');
                            return Boolean(sw && (sw.checked || sw.getAttribute('aria-checked') === 'true'));
                        })()"""
                    )
                )
                if not already_on:
                    await _trusted_click_js(
                        client,
                        r"""(() => {
                            const aigc = document.querySelector('[data-e2e="aigc_container"]');
                            if (!aigc) return null;
                            aigc.scrollIntoView({block: 'center'});
                            const sw = Array.from(aigc.querySelectorAll('div[class*="Switch"], [role="switch"], input[type="checkbox"]'))
                                .find(el => el.getBoundingClientRect().width > 10 && el.getBoundingClientRect().height > 10);
                            if (!sw) return null;
                            const r = sw.getBoundingClientRect();
                            return { x: r.left, y: r.top, w: r.width, h: r.height };
                        })()""",
                    )
                    await asyncio.sleep(1.4)
                    await _trusted_click_labels(client, ["Turn on", "Confirm"])
                    await asyncio.sleep(1.0)

                aigc_enabled = bool(
                    await client.eval(
                        r"""(() => {
                            const sw = document.querySelector('[data-e2e="aigc_container"] [role="switch"], [data-e2e="aigc_container"] input[type="checkbox"]');
                            return Boolean(sw && (sw.checked || sw.getAttribute('aria-checked') === 'true'));
                        })()"""
                    )
                )

            # Optional TikTok Studio desktop Schedule toggle + Date/Time picker
            if dt_sched_utc is not None:
                raw_tz = await client.eval("Intl.DateTimeFormat().resolvedOptions().timeZone")
                try:
                    browser_tz = ZoneInfo(str(raw_tz or "UTC"))
                except Exception:
                    browser_tz = timezone.utc
                dt_local = dt_sched_utc.astimezone(browser_tz)
                sched_date_iso = dt_local.strftime("%Y-%m-%d")
                sched_hh = f"{dt_local.hour:02d}"
                sched_mm = f"{dt_local.minute:02d}"

                await _trusted_click_js(
                    client,
                    r"""(() => {
                        const cands = Array.from(document.querySelectorAll('label, [role="radio"], input[type="radio"], span, div'))
                            .filter(e => /^schedule$/i.test((e.innerText || '').trim()) && e.getBoundingClientRect().width > 10 && e.getBoundingClientRect().height < 60);
                        const el = cands[0];
                        if (!el) return null;
                        el.scrollIntoView({block: 'center'});
                        const r = el.getBoundingClientRect();
                        return { x: r.left, y: r.top, w: r.width, h: r.height };
                    })()""",
                )
                await asyncio.sleep(1.0)
                await _trusted_click_labels(client, ["Allow"])
                await asyncio.sleep(0.6)

                await client.eval(
                    f"""(() => {{
                        const dateStr = {json.dumps(sched_date_iso)};
                        const hhStr = {json.dumps(sched_hh)};
                        const mmStr = {json.dumps(sched_mm)};
                        const inputs = Array.from(document.querySelectorAll('input')).filter(i => i.getBoundingClientRect().width > 20);
                        for (const inp of inputs) {{
                            const v = (inp.value || '').trim();
                            if (/^\\d{{4}}-\\d{{2}}-\\d{{2}}$/.test(v)) {{
                                const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')?.set;
                                if (setter) setter.call(inp, dateStr);
                                else inp.value = dateStr;
                                inp.dispatchEvent(new Event('input', {{bubbles: true}}));
                                inp.dispatchEvent(new Event('change', {{bubbles: true}}));
                            }} else if (/^\\d{{2}}:\\d{{2}}$/.test(v)) {{
                                const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')?.set;
                                if (setter) setter.call(inp, hhStr + ':' + mmStr);
                                else inp.value = hhStr + ':' + mmStr;
                                inp.dispatchEvent(new Event('input', {{bubbles: true}}));
                                inp.dispatchEvent(new Event('change', {{bubbles: true}}));
                            }}
                        }}
                    }})()"""
                )
                await asyncio.sleep(0.8)

            # Click Post / Schedule
            posted_click = await _trusted_click_js(
                client,
                r"""(() => {
                    const b = document.querySelector('[data-e2e="post_video_button"]');
                    if (!b || b.disabled || b.getAttribute('aria-disabled') === 'true') return null;
                    b.scrollIntoView({block: 'center'});
                    const r = b.getBoundingClientRect();
                    return { x: r.left, y: r.top, w: r.width, h: r.height };
                })()""",
            )
            if not posted_click:
                raise RuntimeError("Could not find enabled '[data-e2e=\"post_video_button\"]' on TikTok Studio")

            modal_confirm_clicks = 0
            max_modal_confirm_clicks = 3
            modal_confirm_labels: tuple[str, ...] = (
                ("Schedule", "Post now", "Continue to post")
                if dt_sched_utc is not None
                else TIKTOK_CONFIRM_MODAL_LABELS
            )
            published_ok = False

            # 1. Short initial poll (~2.0s) after post_video_button click: strictly check CAPTCHA
            #    first, then click any immediate confirmation modal inside a modal overlay.
            for _ in range(2):
                await asyncio.sleep(1.0)
                st_init_post = await _inspect_tiktok_page(client)
                cap_init_post = detect_tiktok_captcha(
                    str(st_init_post.get("url") or ""),
                    str(st_init_post.get("bodyText") or ""),
                    st_init_post.get("domCaptcha") or [],
                )
                if cap_init_post:
                    keep_open = True
                    shot = (
                        str(await capture_background_png(client, Path(verification_screenshot_path)))
                        if verification_screenshot_path
                        else None
                    )
                    return {
                        "status": "captcha_verification_needed",
                        "target_id": tid,
                        "lease_owner_id": eff_owner,
                        "markers": cap_init_post,
                        "screenshot_path": shot,
                    }
                if _is_tiktok_publish_confirmed(
                    str(st_init_post.get("url") or ""),
                    str(st_init_post.get("bodyText") or ""),
                ):
                    published_ok = True
                    break
                if modal_confirm_clicks < max_modal_confirm_clicks:
                    confirmed = await click_tiktok_confirm_modal_button(client, labels=modal_confirm_labels)
                    if confirmed:
                        modal_confirm_clicks += 1
                        break

            # 2. Publish completion loop: strictly check CAPTCHA first; if not yet published and
            #    a delayed confirmation modal appears, click it cleanly inside the modal overlay.
            if not published_ok:
                for _ in range(45):
                    await asyncio.sleep(2.5)
                    st_post = await _inspect_tiktok_page(client)
                    cap_post = detect_tiktok_captcha(
                        str(st_post.get("url") or ""),
                        str(st_post.get("bodyText") or ""),
                        st_post.get("domCaptcha") or [],
                    )
                    if cap_post:
                        keep_open = True
                        shot = (
                            str(await capture_background_png(client, Path(verification_screenshot_path)))
                            if verification_screenshot_path
                            else None
                        )
                        return {
                            "status": "captcha_verification_needed",
                            "target_id": tid,
                            "lease_owner_id": eff_owner,
                            "markers": cap_post,
                            "screenshot_path": shot,
                        }
                    if _is_tiktok_publish_confirmed(
                        str(st_post.get("url") or ""),
                        str(st_post.get("bodyText") or ""),
                    ):
                        published_ok = True
                        break
                    if modal_confirm_clicks < max_modal_confirm_clicks:
                        confirmed = await click_tiktok_confirm_modal_button(client, labels=modal_confirm_labels)
                        if confirmed:
                            modal_confirm_clicks += 1

            if not published_ok:
                raise TimeoutError("Timed out waiting for TikTok Studio 'Post'/'Schedule' completion confirmation")

            profile_target_url = (
                f"https://www.tiktok.com/@{clean_handle}?lang=en"
                if clean_handle
                else "https://www.tiktok.com/profile?lang=en"
            )
            video_url = ""
            video_id = ""
            if dt_sched_utc is None:
                for _ in range(8):
                    await client.send("Page.navigate", {"url": profile_target_url})
                    await asyncio.sleep(6.0)
                    found_links: list[str] = (
                        await client.eval(
                            r"""
                            (() => Array.from(document.querySelectorAll('a[href*="/video/"]'))
                                .map(a => a.href || a.getAttribute('href') || '')
                                .filter(Boolean))()
                            """
                        )
                        or []
                    )
                    for href in found_links:
                        m = re.search(r"/@([^/?#]+)/video/(\d+)", href)
                        if m:
                            clean_handle = m.group(1)
                            video_id = m.group(2)
                            video_url = f"https://www.tiktok.com/@{clean_handle}/video/{video_id}"
                            break
                    if video_url:
                        await asyncio.sleep(2.0)
                        break
                    await asyncio.sleep(4.0)

            live_shot = (
                str(await capture_background_png(client, Path(live_screenshot_path)))
                if live_screenshot_path
                else None
            )

            receipt: dict[str, Any] = {
                "status": "scheduled" if dt_sched_utc else "published",
                "platform": "tiktok",
                "handle": f"@{clean_handle}" if clean_handle else handle,
                "profile_url": f"https://www.tiktok.com/@{clean_handle}" if clean_handle else profile_target_url,
                "video_id": video_id,
                "video_url": video_url,
                "visibility": visibility,
                "duration_sec": duration_sec,
                "commercial_sound_prohibited": True,
                "scheduled_at_utc": dt_sched_utc.strftime("%Y-%m-%dT%H:%M:%SZ") if dt_sched_utc else None,
                "aigc_disclosure_enabled": aigc_enabled,
                "custom_cover_applied": cover_applied,
                "video_path": str(v_path),
                "cover_path": str(c_path),
                "caption_chars": len(clean_caption),
                "live_screenshot_path": live_shot,
                "uploaded_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            }
            if receipt_path:
                rp = Path(receipt_path)
                rp.parent.mkdir(parents=True, exist_ok=True)
                rp.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

            succeeded = True
            return receipt
    finally:
        cleanup_staged_bridge_files()
        if close_tab_on_finish and succeeded and not keep_open:
            release_and_close_leased_tab(tid, owner_id=eff_owner, cdp_port=cdp_port, cdp_host=cdp_host)


async def sync_tiktok_pinned_videos_cdp(
    video_ids: Sequence[str],
    *,
    handle: str = DEFAULT_TIKTOK_HANDLE,
    dry_run: bool = False,
    verification_screenshot_path: Path | str | None = None,
    cdp_host: str = DEFAULT_CDP_HOST,
    cdp_port: int = DEFAULT_CDP_PORT,
    owner_id: str | None = None,
    close_tab_on_finish: bool = True,
) -> dict[str, Any]:
    """
    Pins up to `3` top-performing videos (`Pin to profile`) on `https://www.tiktok.com/@<handle>`,
    halting immediately without interaction if `secsdk-captcha` / puzzle verification appears.
    """
    clean_ids = [str(v or "").strip() for v in video_ids if str(v or "").strip()]
    if not clean_ids:
        raise ValueError("video_ids cannot be empty")
    if len(clean_ids) > TIKTOK_MAX_PINNED_VIDEOS:
        raise ValueError(
            f"TikTok allows at most {TIKTOK_MAX_PINNED_VIDEOS} pinned profile videos (got {len(clean_ids)})"
        )
    for vid in clean_ids:
        if not re.fullmatch(r"[A-Za-z0-9_-]{4,32}", vid):
            raise ValueError(f"Invalid TikTok video_id: {vid!r}")

    clean_handle = handle.strip().lstrip("@")
    if dry_run:
        return {
            "status": "dry_run",
            "platform": "tiktok",
            "handle": f"@{clean_handle}",
            "target_video_ids": clean_ids,
            "max_pinned_videos": TIKTOK_MAX_PINNED_VIDEOS,
        }

    eff_owner = owner_id or f"pid:{os.getpid()}:tiktok_pin_operator"
    opened = open_leased_cdp_tab(
        "about:blank",
        owner_id=eff_owner,
        purpose="tiktok_pin_profile",
        cdp_port=cdp_port,
        cdp_host=cdp_host,
        background=True,
    )
    tid = str(opened["id"])
    ws_url = str(opened.get("webSocketDebuggerUrl") or f"ws://{cdp_host}:{int(cdp_port)}/devtools/page/{tid}")

    keep_open = False
    pinned_ids: list[str] = []
    already_pinned_ids: list[str] = []
    try:
        async with DirectCDPClient(ws_url) as client:
            await client.send(
                "Emulation.setDeviceMetricsOverride",
                {"width": 1440, "height": 1020, "deviceScaleFactor": 1, "mobile": False},
            )
            for vid in clean_ids:
                v_url = f"https://www.tiktok.com/@{clean_handle}/video/{vid}?lang=en"
                await client.send("Page.navigate", {"url": v_url})
                await asyncio.sleep(4.5)
                renew_tab_lease(tid, owner_id=eff_owner, cdp_port=cdp_port)

                st = await _inspect_tiktok_page(client)
                cap = detect_tiktok_captcha(
                    str(st.get("url") or ""),
                    str(st.get("bodyText") or ""),
                    st.get("domCaptcha") or [],
                )
                if cap:
                    keep_open = True
                    shot = (
                        str(await capture_background_png(client, Path(verification_screenshot_path)))
                        if verification_screenshot_path
                        else None
                    )
                    return {
                        "status": "captcha_verification_needed",
                        "target_id": tid,
                        "lease_owner_id": eff_owner,
                        "markers": cap,
                        "screenshot_path": shot,
                    }

                await _trusted_click_js(
                    client,
                    r"""(() => {
                        const btn = document.querySelector('[data-e2e="video-setting"], [aria-label="More actions"], [aria-label="More"]');
                        if (!btn) return null;
                        const r = btn.getBoundingClientRect();
                        return { x: r.left, y: r.top, w: r.width, h: r.height };
                    })()""",
                )
                await asyncio.sleep(1.0)
                has_unpin = bool(
                    await client.eval(
                        r"""(() => /unpin from profile|^unpin$/i.test(document.body?.innerText || ''))()"""
                    )
                )
                if has_unpin:
                    already_pinned_ids.append(vid)
                    continue
                clicked_pin = await _trusted_click_labels(client, ["Pin to profile", "Pin"])
                if clicked_pin:
                    pinned_ids.append(vid)
                    await asyncio.sleep(1.2)

        return {
            "status": "ok",
            "platform": "tiktok",
            "handle": f"@{clean_handle}",
            "target_video_ids": clean_ids,
            "pinned_ids": pinned_ids,
            "already_pinned_ids": already_pinned_ids,
        }
    finally:
        if close_tab_on_finish and not keep_open:
            release_and_close_leased_tab(tid, owner_id=eff_owner, cdp_port=cdp_port, cdp_host=cdp_host)
