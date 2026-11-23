"""
ALL ABOUT BRAIN — YouTube Community `Quiz` Post Authoring & Scheduling (`pipeline/studio/community_posts.py`).

Authors and schedules 4-option neuroscience `Quiz` posts (`<= 80` chars per option, 1 correct answer,
`<= 500` char explanation with verified DOI + Tonight's Short CTA) via a background leased CDP tab:
  - Authoring dialog: `https://www.youtube.com/channel/<CHANNEL_ID>/posts?show_create_dialog=1`
  - Studio verification: `https://studio.youtube.com/channel/<CHANNEL_ID>/content/posts`
"""

from __future__ import annotations

import asyncio
import base64
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import re
from typing import Any
from zoneinfo import ZoneInfo

from pipeline.cdp_tab_lease import enable_background_focus_emulation, leased_cdp_tab
from pipeline.config import PROJECTS_DIR
from pipeline.publish import (
    build_youtube_community_quiz_payload,
    validate_youtube_community_quiz_payload,
)
from pipeline.studio.community import PRE_DOCUMENT_AUTOPLAY_KILL_JS
from pipeline.studio.config import CHANNEL_ID, DEFAULT_CDP_PORT
from pipeline.studio.whale_session import _DEEP_QUERY_HELPER_JS

ET_TZ = ZoneInfo("America/New_York")


def resolve_project_dir(project_id_or_dir: Path | str) -> Path:
    raw = Path(project_id_or_dir)
    if raw.exists() or raw.is_absolute():
        return raw
    cand = PROJECTS_DIR / str(project_id_or_dir)
    return cand


def parse_schedule_et(schedule_str: str, *, now_utc: datetime | None = None, enforce_future: bool = True) -> datetime:
    """
    Parses `'YYYY-MM-DD HH:MM ET'` (or `'YYYY-MM-DD HH:MM'` / ISO-8601) into an aware `America/New_York` datetime.
    """
    raw = str(schedule_str or "").strip()
    if not raw:
        raise ValueError("schedule string cannot be empty")

    cleaned = re.sub(r"\s+(?:ET|EST|EDT)$", "", raw, flags=re.IGNORECASE).strip()
    dt_et: datetime | None = None
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%dT%H:%M:%S"):
        try:
            naive = datetime.strptime(cleaned, fmt)
            dt_et = naive.replace(tzinfo=ET_TZ)
            break
        except ValueError:
            continue

    if dt_et is None:
        parsed_iso = datetime.fromisoformat(cleaned)
        dt_et = parsed_iso.replace(tzinfo=ET_TZ) if parsed_iso.tzinfo is None else parsed_iso.astimezone(ET_TZ)

    # Snap minutes to 15-minute increments required by YouTube Community post time picker
    minute_mod = dt_et.minute % 15
    if minute_mod != 0:
        raise ValueError(
            f"YouTube Community schedule time must align to 15-minute increments (:00, :15, :30, :45); got {dt_et.strftime('%H:%M')} ET"
        )

    ref_now = now_utc or datetime.now(timezone.utc)
    if enforce_future and dt_et.astimezone(timezone.utc) <= ref_now + timedelta(minutes=10):
        raise ValueError(
            f"Target schedule time {dt_et.isoformat()} must be >10 minutes in the future (now={ref_now.isoformat()})"
        )
    return dt_et


def convert_utc_to_picker_local(dt_utc: datetime, tz_picker_label: str = "(GMT+0000) Local Time") -> dict[str, Any]:
    """
    Converts `dt_utc` to the exact timezone displayed on `tp-yt-paper-button#timezone-picker`
    (e.g., `(GMT+0000) Local Time`, `(GMT-05:00)`, `(GMT+09:00)`).
    """
    m = re.search(r"GMT\s*([+\-])\s*(\d{2}):?(\d{2})", str(tz_picker_label or ""), flags=re.IGNORECASE)
    offset_min = 0
    if m:
        sign = 1 if m.group(1) == "+" else -1
        offset_min = sign * (int(m.group(2)) * 60 + int(m.group(3)))

    picker_tz = timezone(timedelta(minutes=offset_min))
    dt_local = dt_utc.astimezone(picker_tz)
    hour_12 = (dt_local.hour % 12) or 12
    ampm = "AM" if dt_local.hour < 12 else "PM"
    return {
        "offset_minutes": offset_min,
        "year": dt_local.year,
        "month": dt_local.month,
        "day": dt_local.day,
        "date_label_en": f"{dt_local.strftime('%b')} {dt_local.day}, {dt_local.year}",
        "date_slash": f"{dt_local.month}/{dt_local.day}/{dt_local.year}",
        "date_iso": dt_local.strftime("%Y-%m-%d"),
        "time_12h": f"{hour_12}:{dt_local.minute:02d} {ampm}",
        "time_24h": dt_local.strftime("%H:%M"),
    }


class YouTubeCommunityPostManager:
    """Authors and schedules YouTube Community `Quiz` posts over leased background CDP tabs."""

    def __init__(
        self,
        *,
        channel_id: str = CHANNEL_ID,
        cdp_port: int = DEFAULT_CDP_PORT,
    ) -> None:
        self.channel_id = str(channel_id)
        self.cdp_port = int(cdp_port)
        self.authoring_url = f"https://www.youtube.com/channel/{self.channel_id}/posts?show_create_dialog=1"
        self.studio_posts_url = f"https://studio.youtube.com/channel/{self.channel_id}/content/posts"

    def load_or_build_quiz_payload(self, project_dir: Path | str) -> dict[str, Any]:
        p_dir = resolve_project_dir(project_dir)
        quiz_json = p_dir / "06_publish" / "multi_platform_bundle" / "youtube_quiz_post.json"
        if quiz_json.is_file():
            payload = json.loads(quiz_json.read_text(encoding="utf-8"))
        else:
            payload = build_youtube_community_quiz_payload(p_dir)
            quiz_json.parent.mkdir(parents=True, exist_ok=True)
            quiz_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

        errs = validate_youtube_community_quiz_payload(payload)
        if errs:
            raise ValueError(f"Invalid youtube_quiz_post.json: {'; '.join(errs)}")
        return payload

    async def publish_or_schedule_quiz_async(
        self,
        project_dir: Path | str,
        *,
        schedule_et: str | None = None,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        p_dir = resolve_project_dir(project_dir)
        payload = self.load_or_build_quiz_payload(p_dir)

        dt_et: datetime | None = None
        dt_utc: datetime | None = None
        if schedule_et:
            dt_et = parse_schedule_et(schedule_et, enforce_future=not dry_run)
            dt_utc = dt_et.astimezone(timezone.utc)

        if dry_run:
            preview_picker = convert_utc_to_picker_local(dt_utc) if dt_utc else None
            return {
                "status": "dry_run",
                "project_id": payload.get("project_id") or p_dir.name,
                "mode": "scheduled" if dt_et else "immediate",
                "schedule_et": dt_et.isoformat() if dt_et else None,
                "schedule_utc": dt_utc.isoformat() if dt_utc else None,
                "picker_preview_utc": preview_picker,
                "authoring_url": self.authoring_url,
                "verification_url": self.studio_posts_url,
                "payload": payload,
            }

        pub_dir = p_dir / "06_publish"
        pub_dir.mkdir(parents=True, exist_ok=True)
        screenshot_path = pub_dir / "community_quiz_scheduled_proof.png"
        receipt_path = pub_dir / "community_quiz_receipt.json"

        question = str(payload["question"]).strip()
        options = list(payload["options"])
        explanation = str(payload["explanation"]).strip()
        correct_idx = next(i for i, o in enumerate(options) if o.get("is_correct") is True)

        async with leased_cdp_tab(
            "about:blank",
            purpose="youtube_community_quiz_schedule",
            cdp_port=self.cdp_port,
            background=True,
        ) as (client, _tid, _owner):
            await enable_background_focus_emulation(client)
            await client.send("Page.addScriptToEvaluateOnNewDocument", {"source": PRE_DOCUMENT_AUTOPLAY_KILL_JS})
            await client.send(
                "Emulation.setDeviceMetricsOverride",
                {"width": 1680, "height": 1220, "deviceScaleFactor": 1, "mobile": False},
            )
            await client.send("Page.navigate", {"url": self.authoring_url})
            await asyncio.sleep(5.5)

            # 1. Switch dialog into Quiz mode (try visible Quiz button first; if Answer 1 still hidden, try all Quiz buttons + trusted click)
            for attempt in range(3):
                q_state = await client.eval(
                    "(() => {"
                    + _DEEP_QUERY_HELPER_JS
                    + f"""
                        const visibleTa = __queryAllDeep('yt-posts-creation-option-view-model textarea').find(
                            t => t.getBoundingClientRect().width > 0
                        );
                        if (visibleTa) return {{quizOpen: true}};
                        const qBtns = __queryAllDeep('button').filter(
                            b => /add a quiz|^quiz$|퀴즈/i.test((b.getAttribute('aria-label') || '') + ' ' + (b.innerText || b.textContent || '').trim())
                        );
                        if (!qBtns.length) return {{quizOpen: false, err: 'quiz_button_not_found'}};
                        const visBtn = qBtns.find(b => b.getBoundingClientRect().width > 0);
                        const target = ({attempt} === 1 && qBtns.length > 1) ? qBtns[qBtns.length - 1] : (visBtn || qBtns[0]);
                        const r = target.getBoundingClientRect();
                        target.click();
                        return {{
                            quizOpen: false,
                            clicked: true,
                            x: r.width > 0 ? Math.round(r.left + r.width / 2) : 0,
                            y: r.height > 0 ? Math.round(r.top + r.height / 2) : 0,
                        }};
                    }})()"""
                )
                if isinstance(q_state, dict) and q_state.get("quizOpen"):
                    break
                if attempt == 2 and isinstance(q_state, dict) and q_state.get("x", 0) > 0:
                    qx, qy = float(q_state["x"]), float(q_state["y"])
                    await client.send("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": qx, "y": qy})
                    await client.send("Input.dispatchMouseEvent", {"type": "mousePressed", "x": qx, "y": qy, "button": "left", "clickCount": 1})
                    await client.send("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": qx, "y": qy, "button": "left", "clickCount": 1})
                await asyncio.sleep(1.8)

            # Click visible 'Add answer' until 4 visible answer textareas exist
            for _ in range(5):
                add_info = await client.eval(
                    "(() => {"
                    + _DEEP_QUERY_HELPER_JS
                    + """
                        const visTas = __queryAllDeep('yt-posts-creation-option-view-model textarea').filter(
                            el => el.getBoundingClientRect().width > 0
                        );
                        if (visTas.length >= 4) return {count: visTas.length, addBtn: null};
                        const addBtn = __queryAllDeep('button, [role="button"]').find(b => {
                            const r = b.getBoundingClientRect();
                            if (r.width <= 0 || r.height <= 0) return false;
                            const label = ((b.innerText || b.textContent || '') + ' ' + (b.getAttribute('aria-label') || '')).replace(/\\s+/g, ' ').trim();
                            return /add answer|add another|add option|답변 추가|옵션 추가/i.test(label);
                        });
                        if (!addBtn) return {count: visTas.length, addBtn: null};
                        addBtn.scrollIntoView({block: 'center'});
                        const r = addBtn.getBoundingClientRect();
                        addBtn.click();
                        return {count: visTas.length, addBtn: {x: Math.round(r.left + r.width / 2), y: Math.round(r.top + r.height / 2)}};
                    })()"""
                )
                cur_count = int((add_info or {}).get("count") or 0)
                if cur_count >= 4:
                    break
                btn_xy = (add_info or {}).get("addBtn")
                if isinstance(btn_xy, dict):
                    await asyncio.sleep(0.35)
                    recheck = await client.eval(
                        "(() => {"
                        + _DEEP_QUERY_HELPER_JS
                        + """
                            return __queryAllDeep('yt-posts-creation-option-view-model textarea').filter(
                                el => el.getBoundingClientRect().width > 0
                            ).length;
                        })()"""
                    )
                    if isinstance(recheck, int) and recheck <= cur_count:
                        bx, by = float(btn_xy["x"]), float(btn_xy["y"])
                        await client.send("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": bx, "y": by})
                        await client.send("Input.dispatchMouseEvent", {"type": "mousePressed", "x": bx, "y": by, "button": "left", "clickCount": 1})
                        await client.send("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": bx, "y": by, "button": "left", "clickCount": 1})
                await asyncio.sleep(0.65)

            # 2. Populate Question, 4 Options, Correct Answer mark, and Explanation inside activeDlg
            fill_res = await client.eval(
                "(() => {"
                + _DEEP_QUERY_HELPER_JS
                + f"""
                    const optRows = __queryAllDeep('yt-posts-creation-option-view-model').filter(
                        r => __queryAllDeep('textarea', r).some(ta => ta.getBoundingClientRect().width > 0)
                    );
                    if (optRows.length < 4) return {{ok: false, err: 'expected_4_option_rows_got_' + optRows.length}};
                    const dlg = __queryAllDeep('tp-yt-paper-dialog').find(d => d.getBoundingClientRect().width > 0)
                        || __queryAllDeep('ytd-backstage-post-dialog-renderer').filter(d => d.getBoundingClientRect().width > 0).slice(-1)[0]
                        || document.body;

                    const setTextarea = (ta, text) => {{
                        ta.focus();
                        const setter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value')?.set;
                        if (setter) setter.call(ta, '');
                        else ta.value = '';
                        ta.dispatchEvent(new Event('input', {{bubbles: true, composed: true}}));
                        const okExec = document.execCommand && document.execCommand('insertText', false, text);
                        if (!okExec || ta.value !== text) {{
                            if (setter) setter.call(ta, text);
                            else ta.value = text;
                            ta.dispatchEvent(new InputEvent('input', {{bubbles: true, composed: true, data: text, inputType: 'insertText'}}));
                            ta.dispatchEvent(new Event('change', {{bubbles: true, composed: true}}));
                        }}
                    }};

                    // Question contenteditable (visible Quiz box)
                    const qBox = __queryAllDeep('#contenteditable-root').find(
                        el => el.getBoundingClientRect().width > 0 && /quiz/i.test(el.getAttribute('aria-label') || '')
                    ) || __queryAllDeep('#contenteditable-root', dlg).find(el => el.getBoundingClientRect().width > 0);
                    if (!qBox) return {{ok: false, err: 'question_box_not_found'}};
                    qBox.focus();
                    qBox.textContent = '';
                    qBox.dispatchEvent(new Event('input', {{bubbles: true, composed: true}}));
                    const qText = {json.dumps(question)};
                    if (!document.execCommand || !document.execCommand('insertText', false, qText)) {{
                        qBox.textContent = qText;
                        qBox.dispatchEvent(new InputEvent('input', {{bubbles: true, composed: true, data: qText, inputType: 'insertText'}}));
                    }}

                    // 4 option rows
                    const optTexts = {json.dumps([str(o["text"]) for o in options])};
                    for (let i = 0; i < 4; i++) {{
                        const ta = __queryAllDeep('textarea', optRows[i]).find(el => el.getBoundingClientRect().width > 0)
                            || __queryAllDeep('textarea', optRows[i])[0];
                        if (!ta) return {{ok: false, err: 'missing_textarea_row_' + i}};
                        setTextarea(ta, optTexts[i]);
                    }}

                    // Mark correct answer
                    const targetIdx = {int(correct_idx)};
                    const targetRow = optRows[targetIdx];
                    const markBtn = __queryAllDeep('button', targetRow).find(
                        b => /mark as correct|marked as correct|정답/i.test(b.getAttribute('aria-label') || '')
                    );
                    if (!markBtn) return {{ok: false, err: 'mark_correct_btn_not_found'}};
                    if (!/marked as correct|정답으로 표시됨/i.test(markBtn.getAttribute('aria-label') || '')) {{
                        markBtn.click();
                    }}

                    // Explanation textarea
                    const expBox = __queryAllDeep('textarea').find(
                        ta => ta.getBoundingClientRect().width > 0 && /explanation|설명/i.test(ta.getAttribute('placeholder') || ta.getAttribute('aria-label') || '')
                    );
                    if (!expBox) return {{ok: false, err: 'explanation_box_not_found'}};
                    setTextarea(expBox, {json.dumps(explanation)});

                    return {{
                        ok: true,
                        questionSet: (qBox.innerText || '').trim(),
                        optionValues: optRows.slice(0, 4).map(r => (__queryAllDeep('textarea', r)[0]?.value || '')),
                        explanationLen: expBox.value.length,
                    }};
                }})()"""
            )
            if not isinstance(fill_res, dict) or not fill_res.get("ok"):
                raise RuntimeError(f"Failed to fill Quiz fields: {fill_res}")
            await asyncio.sleep(1.0)

            picker_applied: dict[str, Any] | None = None
            if dt_utc is not None:
                # 3. Open Action menu STRICTLY inside the active composer dialog (never pick published feed posts' '...' menu below!)
                menu_open_res = await client.eval(
                    "(() => {"
                    + _DEEP_QUERY_HELPER_JS
                    + """
                        const composerDlg = __queryAllDeep('tp-yt-paper-dialog').find(
                            d => d.getBoundingClientRect().width > 0 && __queryAllDeep('yt-posts-creation-option-view-model, #contenteditable-root', d).some(el => el.getBoundingClientRect().width > 0)
                        )
                            || __queryAllDeep('ytd-backstage-post-dialog-renderer').filter(d => d.getBoundingClientRect().width > 0).slice(-1)[0]
                            || __queryAllDeep('tp-yt-paper-dialog').find(d => d.getBoundingClientRect().width > 0);
                        if (!composerDlg) return {ok: false, err: 'composer_dialog_not_found'};
                        const menuBtns = __queryAllDeep('button', composerDlg).filter(
                            b => b.getBoundingClientRect().width > 0 && /action menu|더보기|추가 작업/i.test(b.getAttribute('aria-label') || '')
                        );
                        if (!menuBtns.length) return {ok: false, err: 'composer_action_menu_not_found'};
                        const menuBtn = menuBtns[0];
                        if (menuBtn.disabled || menuBtn.getAttribute('aria-disabled') === 'true') {
                            return {ok: false, err: 'composer_action_menu_disabled'};
                        }
                        menuBtn.click();
                        const r = menuBtn.getBoundingClientRect();
                        return {ok: true, countInDlg: menuBtns.length, x: Math.round(r.left), y: Math.round(r.top)};
                    })()"""
                )
                if not isinstance(menu_open_res, dict) or not menu_open_res.get("ok"):
                    raise RuntimeError(f"Failed to open composer Action menu for Community Quiz scheduling: {menu_open_res}")
                await asyncio.sleep(0.9)

                sched_click_res = await client.eval(
                    "(() => {"
                    + _DEEP_QUERY_HELPER_JS
                    + """
                        const items = __queryAllDeep('ytd-menu-service-item-renderer, tp-yt-paper-item, yt-list-item-view-model, [role="menuitem"]').filter(
                            e => e.getBoundingClientRect().width > 0
                        );
                        const item = items.find(
                            e => /schedule post|게시물 예약/i.test((e.innerText || e.textContent || '').trim())
                        );
                        if (!item) {
                            return {
                                ok: false,
                                err: 'schedule_post_menu_item_not_found',
                                visibleItems: items.slice(-8).map(e => (e.innerText || e.textContent || '').replace(/\\s+/g, ' ').trim()),
                            };
                        }
                        item.click();
                        return {ok: true, tag: item.tagName, text: (item.innerText || item.textContent || '').trim()};
                    })()"""
                )
                if not isinstance(sched_click_res, dict) or not sched_click_res.get("ok"):
                    raise RuntimeError(f"Failed to click 'Schedule post' menu item for Community Quiz: {sched_click_res}")

                # Wait for visible ytd-date-time-picker-renderer to mount (fail fast with clear error instead of downstream no_dtp)
                dtp_ready: dict[str, Any] | None = None
                for _wait_i in range(8):
                    await asyncio.sleep(0.5)
                    dtp_probe = await client.eval(
                        "(() => {"
                        + _DEEP_QUERY_HELPER_JS
                        + """
                            const dtp = __queryAllDeep('ytd-date-time-picker-renderer').find(d => d.getBoundingClientRect().width > 0)
                                || __queryAllDeep('ytd-date-time-picker-renderer')[0];
                            if (!dtp) return {ok: false, err: 'no_dtp'};
                            const tzBtn = __queryAllDeep('#timezone-picker', dtp)[0];
                            return {
                                ok: true,
                                tzLabel: tzBtn ? (tzBtn.innerText || '').trim() : '(GMT+0000) Local Time',
                            };
                        })()"""
                    )
                    if isinstance(dtp_probe, dict) and dtp_probe.get("ok"):
                        dtp_ready = dtp_probe
                        break
                if not isinstance(dtp_ready, dict) or not dtp_ready.get("ok"):
                    raise RuntimeError(
                        f"Community Quiz schedule date-time picker did not open after clicking Schedule post "
                        f"(menu={menu_open_res}, sched={sched_click_res})"
                    )
                tz_label = str(dtp_ready.get("tzLabel") or "(GMT+0000) Local Time")
                picker_spec = convert_utc_to_picker_local(dt_utc, tz_label)

                # Set Date inside ytd-calendar-date-picker
                await client.eval(
                    "(() => {"
                    + _DEEP_QUERY_HELPER_JS
                    + """
                        const dtp = __queryAllDeep('ytd-date-time-picker-renderer').find(d => d.getBoundingClientRect().width > 0)
                            || __queryAllDeep('ytd-date-time-picker-renderer')[0];
                        const dp = dtp ? __queryAllDeep('#date-picker', dtp)[0] : null;
                        if (dp) dp.click();
                    })()"""
                )
                await asyncio.sleep(0.8)

                date_set_res = await client.eval(
                    "(() => {"
                    + _DEEP_QUERY_HELPER_JS
                    + f"""
                        const dtp = __queryAllDeep('ytd-date-time-picker-renderer').find(d => d.getBoundingClientRect().width > 0)
                            || __queryAllDeep('ytd-date-time-picker-renderer')[0];
                        const cp = dtp ? __queryAllDeep('ytd-calendar-date-picker', dtp)[0] : null;
                        if (!cp) return {{ok: false, err: 'no_calendar_picker'}};
                        const tb = __queryAllDeep('input#textbox, input', cp)[0];
                        const targetDateEn = {json.dumps(picker_spec["date_label_en"])};
                        let focusedInput = false;
                        if (tb) {{
                            tb.focus();
                            focusedInput = true;
                            const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')?.set;
                            if (setter) setter.call(tb, targetDateEn);
                            else tb.value = targetDateEn;
                            tb.dispatchEvent(new Event('input', {{bubbles: true, composed: true}}));
                            tb.dispatchEvent(new Event('change', {{bubbles: true, composed: true}}));
                            const form = __queryAllDeep('form#date-input', cp)[0];
                            if (form) form.dispatchEvent(new Event('submit', {{bubbles: true, cancelable: true, composed: true}}));
                        }}
                        return {{ok: true, focusedInput, labelAfterForm: (__queryAllDeep('#date-label-text', cp)[0]?.innerText || '').trim()}};
                    }})()"""
                )
                await asyncio.sleep(0.5)
                # Send Enter key ONLY when the calendar textbox actually took focus (never dismiss an unfocused modal)
                if isinstance(date_set_res, dict) and date_set_res.get("ok") and date_set_res.get("focusedInput"):
                    await client.send(
                        "Input.dispatchKeyEvent",
                        {"type": "keyDown", "key": "Enter", "code": "Enter", "windowsVirtualKeyCode": 13},
                    )
                    await client.send(
                        "Input.dispatchKeyEvent",
                        {"type": "keyUp", "key": "Enter", "code": "Enter", "windowsVirtualKeyCode": 13},
                    )
                    await asyncio.sleep(0.7)

                # Verify date-label-text; if still not matching target day, click day cell directly in calendar grid!
                date_verify = await client.eval(
                    "(() => {"
                    + _DEEP_QUERY_HELPER_JS
                    + f"""
                        const dtp = __queryAllDeep('ytd-date-time-picker-renderer').find(d => d.getBoundingClientRect().width > 0)
                            || __queryAllDeep('ytd-date-time-picker-renderer')[0];
                        const cp = dtp ? __queryAllDeep('ytd-calendar-date-picker', dtp)[0] : __queryAllDeep('ytd-calendar-date-picker')[0];
                        if (!cp) return '';
                        let lbl = (__queryAllDeep('#date-label-text', cp)[0]?.innerText || '').trim();
                        const targetLabel = {json.dumps(picker_spec["date_label_en"])};
                        const targetDayStr = String({int(picker_spec["day"])});
                        if (lbl !== targetLabel) {{
                            const dp = __queryAllDeep('#date-picker', cp)[0];
                            if (dp) dp.click();
                            const cells = __queryAllDeep('.calendar-day, span, div, button', cp).filter(e => {{
                                const r = e.getBoundingClientRect();
                                return r.width > 16 && r.width < 60 && r.height > 16 && r.height < 60
                                    && (e.innerText || '').trim() === targetDayStr
                                    && !String(e.className || '').includes('disabled')
                                    && !String(e.className || '').includes('other-month');
                            }});
                            if (cells.length > 0) cells[0].click();
                            lbl = (__queryAllDeep('#date-label-text', cp)[0]?.innerText || '').trim();
                        }}
                        return lbl;
                    }})()"""
                )

                # Set Time inside #time-picker listbox
                await client.eval(
                    "(() => {"
                    + _DEEP_QUERY_HELPER_JS
                    + """
                        const dtp = __queryAllDeep('ytd-date-time-picker-renderer').find(d => d.getBoundingClientRect().width > 0)
                            || __queryAllDeep('ytd-date-time-picker-renderer')[0];
                        const tp = dtp ? __queryAllDeep('#time-picker', dtp)[0] : null;
                        if (tp) tp.click();
                    })()"""
                )
                await asyncio.sleep(0.9)
                time_verify = await client.eval(
                    "(() => {"
                    + _DEEP_QUERY_HELPER_JS
                    + f"""
                        const dtp = __queryAllDeep('ytd-date-time-picker-renderer').find(d => d.getBoundingClientRect().width > 0)
                            || __queryAllDeep('ytd-date-time-picker-renderer')[0];
                        if (!dtp) return {{ok: false, err: 'no_dtp'}};
                        const t12 = {json.dumps(picker_spec["time_12h"])}.toLowerCase();
                        const t24 = {json.dumps(picker_spec["time_24h"])}.toLowerCase();
                        const items = __queryAllDeep('tp-yt-paper-item, [role="option"]', dtp);
                        const match = items.find(it => {{
                            const s = (it.innerText || it.textContent || '').replace(/\\s+/g, ' ').trim().toLowerCase();
                            return s === t12 || s === t24;
                        }});
                        if (!match) return {{ok: false, err: 'time_item_not_found', sample: items.slice(0, 8).map(i => (i.innerText || '').trim())}};
                        match.scrollIntoView({{block: 'center'}});
                        match.click();
                        const afterTxt = (__queryAllDeep('#time-picker', dtp)[0]?.innerText || '').replace(/\\s+/g, ' ').trim();
                        return {{ok: true, timeAfter: afterTxt}};
                    }})()"""
                )
                if not isinstance(time_verify, dict) or not time_verify.get("ok"):
                    raise RuntimeError(f"Failed to set Community Quiz schedule time ({picker_spec}): {time_verify}")
                await asyncio.sleep(0.8)

                picker_applied = {
                    "menu_open_result": menu_open_res,
                    "schedule_menu_click": sched_click_res,
                    "tz_picker_label": tz_label,
                    "picker_spec": picker_spec,
                    "date_label_after": date_verify,
                    "time_label_after": time_verify.get("timeAfter"),
                    "date_form_result": date_set_res,
                }

            # 4. Submit ('Schedule' when scheduled, 'Post' when immediate) inside active modal
            submit_res = await client.eval(
                "(() => {"
                + _DEEP_QUERY_HELPER_JS
                + f"""
                    const wantSchedule = {json.dumps(bool(dt_utc is not None))};
                    const activeDlg = __queryAllDeep('tp-yt-paper-dialog').find(d => d.getBoundingClientRect().width > 0)
                        || __queryAllDeep('ytd-backstage-post-dialog-renderer').filter(d => d.getBoundingClientRect().width > 0).slice(-1)[0]
                        || document.body;
                    const visBtns = __queryAllDeep('ytd-button-renderer#submit-button button, ytd-button-renderer#post-button button, button', activeDlg).filter(
                        b => b.getBoundingClientRect().width > 0
                    );
                    const btn = (wantSchedule ? visBtns.find(b => /^schedule$|^예약$/i.test((b.innerText || b.textContent || b.getAttribute('aria-label') || '').trim())) : null)
                        || visBtns.find(b => /^schedule$|^post$|^예약$|^게시$/i.test((b.innerText || b.textContent || b.getAttribute('aria-label') || '').trim()));
                    if (!btn) return {{ok: false, err: 'submit_button_not_found'}};
                    if (btn.disabled || btn.getAttribute('aria-disabled') === 'true') {{
                        return {{ok: false, err: 'submit_button_disabled', txt: (btn.innerText || '').trim()}};
                    }}
                    const label = (btn.innerText || btn.textContent || btn.getAttribute('aria-label') || '').trim();
                    if (wantSchedule && !/schedule|예약/i.test(label)) {{
                        return {{ok: false, err: 'expected_schedule_button_got_' + label}};
                    }}
                    btn.click();
                    return {{ok: true, clickedLabel: label}};
                }})()"""
            )
            if not isinstance(submit_res, dict) or not submit_res.get("ok"):
                raise RuntimeError(f"Community Quiz submit failed: {submit_res}")
            await asyncio.sleep(4.5)

            # 5. Navigate to Studio /content/posts to verify Scheduled row & capture proof screenshot
            await client.send("Page.navigate", {"url": self.studio_posts_url})
            await asyncio.sleep(5.5)

            q_needle = question[:42]
            posts_verify = await client.eval(
                "(() => {"
                + _DEEP_QUERY_HELPER_JS
                + f"""
                    const needle = {json.dumps(q_needle)};
                    const bodyTxt = (document.body?.innerText || '').replace(/\\s+/g, ' ');
                    const found = bodyTxt.includes(needle);
                    const rows = __queryAllDeep('ytcp-post-row, ytcp-entity-row, tr, [role="row"]')
                        .map(r => (r.innerText || '').replace(/\\s+/g, ' ').trim())
                        .filter(t => t.includes(needle))
                        .slice(0, 3);
                    return {{found, matchingRows: rows, bodyPreview: bodyTxt.slice(0, 600)}};
                }})()"""
            )

            shot = await client.send("Page.captureScreenshot", {"format": "png"})
            b64_data = (shot.get("result") or {}).get("data") if isinstance(shot, dict) and "result" in shot else (shot.get("data") if isinstance(shot, dict) else None)
            if b64_data:
                screenshot_path.write_bytes(base64.b64decode(b64_data))

        verified_on_studio = bool(isinstance(posts_verify, dict) and posts_verify.get("found"))
        if not verified_on_studio:
            raise RuntimeError(
                f"Submitted Community Quiz did not appear on {self.studio_posts_url}: {posts_verify}"
            )

        receipt_doc = {
            "status": "scheduled" if dt_et else "published",
            "verified_on_studio_posts": verified_on_studio,
            "project_id": payload.get("project_id") or p_dir.name,
            "channel_id": self.channel_id,
            "schedule_et": dt_et.isoformat() if dt_et else None,
            "schedule_utc": dt_utc.isoformat() if dt_utc else None,
            "picker_applied": picker_applied,
            "submit_result": submit_res,
            "studio_posts_verification": posts_verify,
            "screenshot_path": str(screenshot_path),
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "payload": payload,
        }
        receipt_path.write_text(json.dumps(receipt_doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return receipt_doc

    def publish_or_schedule_quiz(
        self,
        project_dir: Path | str,
        *,
        schedule_et: str | None = None,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        return asyncio.run(
            self.publish_or_schedule_quiz_async(
                project_dir,
                schedule_et=schedule_et,
                dry_run=dry_run,
            )
        )
