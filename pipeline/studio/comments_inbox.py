"""
ALL ABOUT BRAIN — Zero-Playback YouTube Studio Comments Inbox Manager (`pipeline/studio/comments_inbox.py`).

Scans unreplied viewer comments and applies human-approved creator hearts + follow-up replies
EXCLUSIVELY on `https://studio.youtube.com/channel/<CHANNEL_ID>/comments/inbox` with a hard
pre-document & runtime click/navigation guard blocking `/watch` and `/shorts/` (`0%` Rule R75
`AVD=0s` self-bounce risk).
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Any

from pipeline.cdp_tab_lease import enable_background_focus_emulation, leased_cdp_tab
from pipeline.config import BANNED_COMMENT_VIOLENCE_TOKENS, CHANNEL_ROOT
from pipeline.studio.community import PRE_DOCUMENT_AUTOPLAY_KILL_JS
from pipeline.studio.config import CHANNEL_ID, DEFAULT_CDP_PORT
from pipeline.studio.browser_session import _DEEP_QUERY_HELPER_JS

STUDIO_COMMENTS_INBOX_URL = f"https://studio.youtube.com/channel/{CHANNEL_ID}/comments/inbox"
DEFAULT_PENDING_REPLIES_PATH = CHANNEL_ROOT / "reports" / "daily" / "pending_comment_replies.json"

_HANGUL_RE = re.compile(r"[\uAC00-\uD7A3\u3130-\u318F]+")

BLOCK_WATCH_SHORTS_NAVIGATION_JS: str = """(() => {
    try {
        const isForbiddenWatchUrl = (raw) => {
            if (!raw) return false;
            const s = String(raw).toLowerCase();
            return s.includes('/watch?') || s.includes('/watch/') || s.includes('/shorts/') || s.includes('youtu.be/');
        };
        const guardClick = (ev) => {
            try {
                const path = (typeof ev.composedPath === 'function') ? ev.composedPath() : [ev.target];
                for (const node of path) {
                    if (!node || !node.tagName) continue;
                    const tag = String(node.tagName).toLowerCase();
                    if (tag === 'ytcp-comment-video-thumbnail') {
                        ev.preventDefault();
                        ev.stopImmediatePropagation();
                        window.__aabBlockedWatchClicks = (window.__aabBlockedWatchClicks || 0) + 1;
                        return false;
                    }
                    if (tag === 'a') {
                        const href = node.getAttribute('href') || node.href || '';
                        if (isForbiddenWatchUrl(href)) {
                            ev.preventDefault();
                            ev.stopImmediatePropagation();
                            window.__aabBlockedWatchClicks = (window.__aabBlockedWatchClicks || 0) + 1;
                            return false;
                        }
                    }
                }
            } catch (_) {}
        };
        window.addEventListener('click', guardClick, true);
        window.addEventListener('auxclick', guardClick, true);
        window.addEventListener('mousedown', guardClick, true);
        const origOpen = window.open;
        window.open = function(url, ...rest) {
            if (isForbiddenWatchUrl(url)) {
                window.__aabBlockedWatchClicks = (window.__aabBlockedWatchClicks || 0) + 1;
                return null;
            }
            return origOpen ? origOpen.call(this, url, ...rest) : null;
        };
        window.__aabWatchGuardInstalled = true;
    } catch (_) {}
})();"""


def compute_comment_key(author: str, video_title: str, comment_text: str) -> str:
    norm = f"{author.strip().lower()}|{video_title.strip().lower()}|{re.sub(r'\\s+', ' ', comment_text.strip().lower())[:160]}"
    return hashlib.sha1(norm.encode("utf-8")).hexdigest()[:16]


def validate_reply_text_safety(reply_text: str) -> list[str]:
    issues: list[str] = []
    txt = str(reply_text or "").strip()
    if not txt:
        issues.append("reply text is empty")
        return issues
    if len(txt) > 450:
        issues.append(f"reply text length {len(txt)} > 450 chars")
    if _HANGUL_RE.search(txt):
        issues.append("reply text contains forbidden Hangul characters")
    low = txt.lower()
    for tok in BANNED_COMMENT_VIOLENCE_TOKENS:
        vt = str(tok).strip().lower()
        if vt and re.search(rf"\b{re.escape(vt)}\b", low):
            issues.append(f"reply text contains banned token '{vt}'")
    if re.search(
        r"\b(?:manychat|dm\s+me|comment\s+['\"]?[a-z0-9_]{2,20}['\"]?\s+(?:below|to\s+get|and\s+i['’]?ll\s+dm|for\s+the\s+link|for\s+my))\b",
        low,
    ):
        issues.append("reply text contains banned DM automation CTA")
    return issues


def synthesize_followup_reply_draft(comment_text: str, video_title: str = "") -> str:
    """
    Synthesizes a concise, plain-English creator reply + curiosity question (`<= 220` chars)
    staged for human review in `pending_comment_replies.json` before any Studio submission.
    """
    low = str(comment_text or "").lower()
    if "don't understand" in low or "dont understand" in low or "confused" in low:
        return (
            "Great catch asking! In short, the body's stress circuit kept firing internally even while outward behavior "
            "looked calm. Which part felt trickiest to picture?"
        )
    if "book" in low or "phantoms" in low or "bonnet" in low or "read" in low:
        return (
            "Phantoms in the Brain is a classic! Charles Bonnet hallucinations show how vivid visual cortex gets when "
            "eye input drops. Have you noticed other sensory quirks like that?"
        )
    if "heart rate" in low or "babies" in low or "strange situation" in low:
        return (
            "Spot on! Their calm faces masked a physiological stress spike that mirrored separation distress. "
            "Did that gap between outward calm and body data surprise you too?"
        )
    clean_topic = re.sub(r"[^A-Za-z0-9 '\-]", "", str(video_title or "")).strip()
    if clean_topic:
        short_t = " ".join(clean_topic.split()[:5])
        return (
            f"Sharp observation on {short_t}! What stood out most to you about how the brain separated those two signals?"
        )
    return (
        "Thoughtful point! When conscious logic and automatic brain wiring pull in opposite directions, "
        "which signal do you think wins first in daily life?"
    )


class StudioCommentsInboxManager:
    """Zero-playback Studio `/comments/inbox` scanner and human-approved reply applicator."""

    def __init__(
        self,
        *,
        channel_id: str = CHANNEL_ID,
        cdp_port: int = DEFAULT_CDP_PORT,
        staging_path: Path | str = DEFAULT_PENDING_REPLIES_PATH,
    ) -> None:
        self.channel_id = str(channel_id)
        self.cdp_port = int(cdp_port)
        self.inbox_url = f"https://studio.youtube.com/channel/{self.channel_id}/comments/inbox"
        self.staging_path = Path(staging_path)

    def _load_existing_staging(self) -> dict[str, dict[str, Any]]:
        if not self.staging_path.is_file():
            return {}
        try:
            doc = json.loads(self.staging_path.read_text(encoding="utf-8"))
            items = doc.get("items") if isinstance(doc, dict) else []
            out: dict[str, dict[str, Any]] = {}
            for it in items or []:
                if isinstance(it, dict) and it.get("comment_key"):
                    out[str(it["comment_key"])] = it
            return out
        except Exception:
            return {}

    async def scan_unreplied_comments_async(self, *, dry_run: bool = False, max_rows: int = 25) -> dict[str, Any]:
        if dry_run:
            return {
                "status": "dry_run",
                "mode": "scan_only",
                "inbox_url": self.inbox_url,
                "staging_path": str(self.staging_path),
                "watch_navigation_guard": True,
                "video_element_count": 0,
                "self_views_triggered": 0,
            }

        async with leased_cdp_tab(
            "about:blank",
            purpose="studio_comments_inbox_scan",
            cdp_port=self.cdp_port,
            background=True,
        ) as (client, _tid, _owner):
            await enable_background_focus_emulation(client)
            await client.send(
                "Page.addScriptToEvaluateOnNewDocument",
                {"source": PRE_DOCUMENT_AUTOPLAY_KILL_JS + "\n" + BLOCK_WATCH_SHORTS_NAVIGATION_JS},
            )
            await client.send(
                "Page.setDeviceMetricsOverride",
                {"width": 1680, "height": 1150, "deviceScaleFactor": 1, "mobile": False},
            )
            await client.send("Page.navigate", {"url": self.inbox_url})
            await asyncio.sleep(5.0)
            await client.eval(BLOCK_WATCH_SHORTS_NAVIGATION_JS)

            scraped = await client.eval(
                rf"""(() => {{
                    {_DEEP_QUERY_HELPER_JS}
                    const url = location.href;
                    const videoCount = __queryAllDeep('video').length;
                    const threads = __queryAllDeep('ytcp-comment-thread').slice(0, {int(max_rows)});
                    const rows = threads.map((th) => {{
                        const anchors = __queryAllDeep('a', th).map(a => ({{
                            href: a.getAttribute('href') || '',
                            txt: (a.innerText || '').trim()
                        }})).filter(a => a.txt || a.href);
                        const authorAnchor = anchors.find(a => a.txt.startsWith('@')) || anchors.find(a => a.href.includes('/@'));
                        const author = authorAnchor ? (authorAnchor.txt || authorAnchor.href.split('/').pop() || '') : '';
                        const titleAnchor = anchors.find(a => a.txt && !a.txt.startsWith('@'));
                        const videoTitle = titleAnchor ? titleAnchor.txt : '';

                        const bodyEl = __queryAllDeep('#content-text, ytcp-comment #content, #comment-content', th)[0];
                        let commentText = bodyEl ? (bodyEl.innerText || '').trim() : '';
                        if (!commentText) {{
                            const fullTxt = (th.innerText || '').replace(/\s+/g, ' ').trim();
                            commentText = fullTxt;
                        }}

                        const showRepliesBtn = __queryAllDeep('#show-replies-button, button', th).find(
                            b => /\b\d+\s+repl(?:y|ies)\b|답글\s*\d+/i.test((b.innerText || '') + ' ' + (b.getAttribute('aria-label') || ''))
                        );
                        const replyLabel = showRepliesBtn ? ((showRepliesBtn.innerText || showRepliesBtn.getAttribute('aria-label') || '').trim()) : '0 replies';
                        const mRep = replyLabel.match(/(\d+)/);
                        const replyCount = mRep ? parseInt(mRep[1], 10) : 0;

                        const heartEl = __queryAllDeep('ytcp-comment-creator-heart', th)[0];
                        const hearted = heartEl ? Boolean(
                            heartEl.hasAttribute('hearted')
                            || /remove heart|하트 삭제/i.test((heartEl.innerText || '') + ' ' + (heartEl.getAttribute('aria-label') || ''))
                        ) : false;

                        return {{
                            author: author.trim(),
                            video_title: videoTitle.trim(),
                            comment_text: commentText.replace(/\s+/g, ' ').trim().slice(0, 500),
                            reply_count: replyCount,
                            hearted,
                        }};
                    }});
                    return {{
                        url,
                        videoCount,
                        blockedWatchClicks: window.__aabBlockedWatchClicks || 0,
                        rows,
                    }};
                }})()"""
            )

        current_url = str((scraped or {}).get("url") or "")
        if "/watch" in current_url or "/shorts/" in current_url:
            raise RuntimeError(f"Zero-playback guard violation: unexpected URL {current_url}")
        video_count = int((scraped or {}).get("videoCount") or 0)
        if video_count != 0:
            raise RuntimeError(f"Zero-playback guard violation: expected 0 <video> elements on inbox, got {video_count}")

        existing_by_key = self._load_existing_staging()
        raw_rows = list((scraped or {}).get("rows") or [])
        staged_items: list[dict[str, Any]] = []
        for row in raw_rows:
            if not isinstance(row, dict):
                continue
            author = str(row.get("author") or "").strip()
            v_title = str(row.get("video_title") or "").strip()
            c_text = str(row.get("comment_text") or "").strip()
            # Clean trailing UI labels if fallback text was used
            c_text = re.sub(r"\s*Reply\s+\d+\s+repl(?:y|ies).*$", "", c_text).strip()
            if author and c_text.startswith(author):
                c_text = re.sub(r"^@\S+\s*•\s*[^•]+?\s+ago\s*", "", c_text).strip()
            if not c_text:
                continue

            ckey = compute_comment_key(author, v_title, c_text)
            prev = existing_by_key.get(ckey, {})
            rep_count = int(row.get("reply_count") or 0)
            if rep_count > 0 and not prev.get("approved"):
                continue

            draft = str(prev.get("draft_reply") or synthesize_followup_reply_draft(c_text, v_title)).strip()
            staged_items.append(
                {
                    "comment_key": ckey,
                    "author": author,
                    "video_title": v_title,
                    "comment_text": c_text,
                    "reply_count": rep_count,
                    "hearted": bool(row.get("hearted")),
                    "draft_reply": draft,
                    "approved": bool(prev.get("approved", False)),
                    "applied": bool(prev.get("applied", False)),
                    "applied_at": prev.get("applied_at"),
                }
            )

        self.staging_path.parent.mkdir(parents=True, exist_ok=True)
        out_doc = {
            "schema_version": 1,
            "scanned_at_utc": datetime.now(timezone.utc).isoformat(),
            "inbox_url": self.inbox_url,
            "zero_playback_verified": True,
            "video_element_count": video_count,
            "blocked_watch_clicks": int((scraped or {}).get("blockedWatchClicks") or 0),
            "unreplied_count": len(staged_items),
            "items": staged_items,
        }
        self.staging_path.write_text(json.dumps(out_doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return {
            "status": "ok",
            "mode": "scan_only",
            "inbox_url": current_url,
            "staging_path": str(self.staging_path),
            "scanned_row_count": len(raw_rows),
            "unreplied_count": len(staged_items),
            "video_element_count": video_count,
            "self_views_triggered": 0,
        }

    async def apply_approved_replies_async(self, *, dry_run: bool = False) -> dict[str, Any]:
        if not self.staging_path.is_file():
            return {
                "status": "no_staging_file",
                "mode": "apply_approved",
                "staging_path": str(self.staging_path),
                "approved_pending_count": 0,
                "applied_count": 0,
            }

        doc = json.loads(self.staging_path.read_text(encoding="utf-8"))
        items = [it for it in (doc.get("items") or []) if isinstance(it, dict)]
        pending = [
            it
            for it in items
            if it.get("approved") is True and it.get("applied") is not True and str(it.get("draft_reply") or "").strip()
        ]

        for it in pending:
            errs = validate_reply_text_safety(str(it.get("draft_reply") or ""))
            if errs:
                raise ValueError(f"Unsafe approved reply for {it.get('comment_key')}: {'; '.join(errs)}")

        if dry_run or not pending:
            return {
                "status": "dry_run" if dry_run else "noop_zero_approved",
                "mode": "apply_approved",
                "staging_path": str(self.staging_path),
                "approved_pending_count": len(pending),
                "applied_count": 0,
                "self_views_triggered": 0,
            }

        applied_keys: list[str] = []
        async with leased_cdp_tab(
            "about:blank",
            purpose="studio_comments_inbox_apply",
            cdp_port=self.cdp_port,
            background=True,
        ) as (client, _tid, _owner):
            await enable_background_focus_emulation(client)
            await client.send(
                "Page.addScriptToEvaluateOnNewDocument",
                {"source": PRE_DOCUMENT_AUTOPLAY_KILL_JS + "\n" + BLOCK_WATCH_SHORTS_NAVIGATION_JS},
            )
            await client.send(
                "Page.setDeviceMetricsOverride",
                {"width": 1680, "height": 1150, "deviceScaleFactor": 1, "mobile": False},
            )
            await client.send("Page.navigate", {"url": self.inbox_url})
            await asyncio.sleep(5.0)
            await client.eval(BLOCK_WATCH_SHORTS_NAVIGATION_JS)

            for target in pending:
                author = str(target.get("author") or "").strip()
                snippet = str(target.get("comment_text") or "").strip()[:60]
                reply_txt = str(target.get("draft_reply") or "").strip()

                res = await client.eval(
                    rf"""(async () => {{
                        {_DEEP_QUERY_HELPER_JS}
                        const authorNeedle = {json.dumps(author)};
                        const textNeedle = {json.dumps(snippet)};
                        const replyBody = {json.dumps(reply_txt)};
                        const threads = __queryAllDeep('ytcp-comment-thread');
                        const th = threads.find(t => {{
                            const txt = (t.innerText || '').replace(/\s+/g, ' ');
                            return (!authorNeedle || txt.includes(authorNeedle)) && (!textNeedle || txt.includes(textNeedle));
                        }});
                        if (!th) return {{ok: false, reason: 'thread_not_found'}};

                        // 1. Creator heart if not hearted
                        const heartHost = __queryAllDeep('ytcp-comment-creator-heart', th)[0];
                        if (heartHost && !heartHost.hasAttribute('hearted')) {{
                            const hBtn = __queryAllDeep('button, tp-yt-paper-icon-button', heartHost)[0] || heartHost;
                            hBtn.click();
                            await new Promise(r => setTimeout(r, 450));
                        }}

                        // 2. Open Reply box
                        const replyBtn = __queryAllDeep('button', th).find(
                            b => /^reply$|^답글$/i.test((b.innerText || b.getAttribute('aria-label') || '').trim())
                        );
                        if (!replyBtn) return {{ok: false, reason: 'reply_btn_not_found'}};
                        replyBtn.click();
                        await new Promise(r => setTimeout(r, 700));

                        // 3. Populate reply input
                        const input = __queryAllDeep('textarea, [contenteditable="true"]', th).find(
                            el => el.getBoundingClientRect().width > 40
                        );
                        if (!input) return {{ok: false, reason: 'reply_input_not_found'}};
                        input.focus();
                        if (input.tagName.toLowerCase() === 'textarea') {{
                            const setter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value')?.set;
                            if (setter) setter.call(input, replyBody);
                            else input.value = replyBody;
                        }} else {{
                            input.textContent = replyBody;
                        }}
                        input.dispatchEvent(new Event('input', {{bubbles: true, composed: true}}));
                        input.dispatchEvent(new Event('change', {{bubbles: true, composed: true}}));
                        await new Promise(r => setTimeout(r, 500));

                        // 4. Click submit Reply button
                        const submitBtns = __queryAllDeep('#submit-button button, ytcp-comment-Creator-reply button, button', th).filter(
                            b => b !== replyBtn && !b.disabled && /^reply$|^답글$/i.test((b.innerText || b.getAttribute('aria-label') || '').trim())
                        );
                        const submitBtn = submitBtns[submitBtns.length - 1];
                        if (!submitBtn) return {{ok: false, reason: 'submit_btn_not_found'}};
                        submitBtn.click();
                        await new Promise(r => setTimeout(r, 1400));
                        return {{ok: true}};
                    }})()"""
                )
                if isinstance(res, dict) and res.get("ok"):
                    target["applied"] = True
                    target["applied_at"] = datetime.now(timezone.utc).isoformat()
                    applied_keys.append(str(target.get("comment_key")))

        doc["updated_at_utc"] = datetime.now(timezone.utc).isoformat()
        self.staging_path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return {
            "status": "ok",
            "mode": "apply_approved",
            "staging_path": str(self.staging_path),
            "approved_pending_count": len(pending),
            "applied_count": len(applied_keys),
            "applied_keys": applied_keys,
            "self_views_triggered": 0,
        }

    def scan_unreplied_comments(self, *, dry_run: bool = False, max_rows: int = 25) -> dict[str, Any]:
        return asyncio.run(self.scan_unreplied_comments_async(dry_run=dry_run, max_rows=max_rows))

    def apply_approved_replies(self, *, dry_run: bool = False) -> dict[str, Any]:
        return asyncio.run(self.apply_approved_replies_async(dry_run=dry_run))
