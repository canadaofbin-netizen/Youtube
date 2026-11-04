"""
ALL ABOUT BRAIN — Retired Scheduled Low-Poly Shorts Take-Down & Local State Purifier
------------------------------------------------------------------------------------
Safely unschedules (`delete` forever or switch to `private`) ONLY the 19 unpublished
`Scheduled` legacy `lowpoly_pastel_v7` Shorts (`diorama_08`..`diorama_26`) via visible
Naver Whale CDP (`studio.youtube.com`), while strictly protecting all 13 `Public` videos (`R34`)
and never touching any non-Studio (`labs.google` / user) browser tabs (`R36-B`).
"""

from __future__ import annotations

import asyncio
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from pipeline.config import CHANNEL_ROOT, PROJECTS_DIR, WORKSPACE_ROOT
from pipeline.studio.config import (
    CHANNEL_ID,
    DEFAULT_CDP_PORT,
    SHORT_LINK_GRAPH_FILE,
    STAGING_QUEUE_FILE,
    STUDIO_CONTENT_URL,
)
from pipeline.studio.short_linker import write_studio_publish_receipt
from pipeline.studio.whale_session import _DEEP_QUERY_HELPER_JS, WhaleSessionController

# Ordered earliest-deadline first (diorama_08 -> diorama_26)
RETIRED_LOWPOLY_SCHEDULED_WHITELIST: dict[str, str] = {
    "diorama_08_maguire_london_taxi_hippocampus": "4jNxwVMMxQo",
    "diorama_09_broca_patient_tan_speech_loss": "SpOCgvOojuk",
    "diorama_10_olds_milner_pleasure_center": "BkWoHoGVV_c",
    "diorama_11_blindsight_subcortical_vision": "XvskvBLMqzg",
    "diorama_12_penfield_cortical_homunculus": "RYeASKxFDnk",
    "diorama_13_asch_conformity_pressure": "SAtSICgNPh4",
    "diorama_14_libet_readiness_potential": "6rDiJhK0Nl4",
    "diorama_15_draganski_juggling_gray_matter": "f1BATCCY1Vs",
    "diorama_16_rizzolatti_mirror_neuron_empathy": "Ky3iCjdSJd0",
    "diorama_17_damasio_somatic_marker_decision": "7QM6ZSwrM68",
    "diorama_18_greene_trolley_dilemma_dual_process": "U1JJjr_2EF8",
    "diorama_19_davidson_monk_gamma_synchrony": "219ze8JUb7c",
    "diorama_20_dutton_aron_capilano_bridge": "KqRu_BXLeRc",
    "diorama_21_delgado_stimoceiver_bull": "CUS_CD1UvFw",
    "diorama_22_baars_global_workspace_theater": "kDBafW58J0Q",
    "diorama_23_beck_cognitive_triad_depression": "aNpoZUC_As8",
    "diorama_24_bodamer_prosopagnosia_face_blindness": "B4lcuLzuEgQ",
    "diorama_25_false_memory_elizabeth_loftus": "yp5Qlf0Fo34",
    "diorama_26_clark_doll_experiment_bias": "whXcmzZygN8",
}

ELAPSED_PUBLIC_SYNC_MAP: dict[str, str] = {
    "diorama_04_milgram_obedience_switch": "wUAD5xIpaww",
    "diorama_05_hippocampal_memory_prosthesis": "JJkBqo-hTS8",
    "diorama_06_clive_wearing_seven_second_mind": "ZbjKX8CBt8A",
    "diorama_07_invisible_gorilla_attention": "t8Z_Q8oB9MY",
}

PROTECTED_PUBLIC_VIDEO_IDS: frozenset[str] = frozenset(
    {
        "p4ou90cHt50",  # psych_01
        "p0etX4iMJ7Q",  # psych_02
        "nGNIl26te0w",  # psych_03
        "lZv3_UAWScI",  # psych_05
        "31_O2CmlKOk",  # psych_06
        "Wydl4JpZmAw",  # gage_diorama_v6_dynamic
        "q1lUimnZ-V0",  # diorama_01
        "u5mQNZWNjiw",  # diorama_02
        "PK1opKmokwY",  # diorama_03
        "wUAD5xIpaww",  # diorama_04
        "JJkBqo-hTS8",  # diorama_05
        "ZbjKX8CBt8A",  # diorama_06
        "t8Z_Q8oB9MY",  # diorama_07
    }
)


def resolve_retired_projects(spec: str) -> list[tuple[str, str]]:
    """
    Resolves `--projects` argument (e.g. `diorama_08..26`, `all`, or comma-separated IDs/prefixes)
    strictly against `RETIRED_LOWPOLY_SCHEDULED_WHITELIST` while preserving deadline order.
    """
    raw = str(spec or "").strip()
    if not raw or raw.lower() == "all":
        return list(RETIRED_LOWPOLY_SCHEDULED_WHITELIST.items())

    m_range = re.match(r"^(?:diorama_)?(\d{1,2})\.\.(?:diorama_)?(\d{1,2})$", raw, flags=re.IGNORECASE)
    if m_range:
        lo, hi = int(m_range.group(1)), int(m_range.group(2))
        if lo > hi:
            lo, hi = hi, lo
        wanted_prefixes = tuple(f"diorama_{i:02d}_" for i in range(lo, hi + 1))
        matched = [
            (pid, vid)
            for pid, vid in RETIRED_LOWPOLY_SCHEDULED_WHITELIST.items()
            if pid.startswith(wanted_prefixes)
        ]
        if not matched:
            raise ValueError(f"Range '{raw}' matched zero whitelisted retired scheduled projects.")
        return matched

    tokens = [t.strip() for t in raw.split(",") if t.strip()]
    selected: list[tuple[str, str]] = []
    seen: set[str] = set()
    for tok in tokens:
        found = None
        if tok in RETIRED_LOWPOLY_SCHEDULED_WHITELIST:
            found = (tok, RETIRED_LOWPOLY_SCHEDULED_WHITELIST[tok])
        else:
            matches = [
                (pid, vid)
                for pid, vid in RETIRED_LOWPOLY_SCHEDULED_WHITELIST.items()
                if pid.startswith(tok + "_") or pid == tok or vid == tok
            ]
            if len(matches) == 1:
                found = matches[0]
        if found is None:
            raise ValueError(
                f"Project/video '{tok}' is NOT in the 19-item retired Scheduled whitelist (R34 safety lock)."
            )
        if found[1] in PROTECTED_PUBLIC_VIDEO_IDS:
            raise RuntimeError(f"FATAL: video_id '{found[1]}' is in PROTECTED_PUBLIC_VIDEO_IDS!")
        if found[0] not in seen:
            seen.add(found[0])
            selected.append(found)
    return selected


def _is_scheduled_visibility_label(vis_text: str) -> bool:
    low = str(vis_text or "").strip().lower()
    if not low:
        return False
    # Explicitly reject Public ("공개" without "비공개")
    if "public" in low:
        return False
    if "공개" in low and "비공개" not in low:
        return False
    return ("scheduled" in low) or ("예약" in low)


async def _wait_for_shorts_table(client: Any, timeout_sec: float = 25.0) -> bool:
    await client.send("Page.bringToFront")
    ok = await client.wait_for_element(["ytcp-video-row"], timeout_sec=timeout_sec)
    if ok:
        await asyncio.sleep(1.0)
    return ok


async def _scrape_shorts_rows(client: Any) -> list[dict[str, Any]]:
    rows = await client.eval(
        rf"""(() => {{
            const els = Array.from(document.querySelectorAll('ytcp-video-row'));
            return els.map((r, idx) => {{
                const a = r.querySelector('a[href*="/video/"]');
                const href = a ? (a.getAttribute('href') || '') : '';
                const m = href.match(/\/video\/([\w-]{{11}})\//);
                const video_id = m ? m[1] : '';
                const tEl = r.querySelector('#video-title');
                const title = tEl ? (tEl.innerText || tEl.textContent || '').replace(/\s+/g, ' ').trim() : '';
                const vEl = r.querySelector('.tablecell-visibility, [class*="visibility"]');
                const visibility = vEl ? (vEl.innerText || '').replace(/\s+/g, ' ').trim() : '';
                const dEl = r.querySelector('.tablecell-date');
                const date_text = dEl ? (dEl.innerText || '').replace(/\s+/g, ' ').trim() : '';
                return {{idx, video_id, title, visibility, date_text}};
            }});
        }})()"""
    )
    return list(rows or [])


async def _delete_single_scheduled_row(
    client: Any,
    *,
    project_id: str,
    video_id: str,
    expected_title: str,
) -> dict[str, Any]:
    if video_id in PROTECTED_PUBLIC_VIDEO_IDS:
        raise RuntimeError(f"Refusing to touch protected Public video '{video_id}'")
    if RETIRED_LOWPOLY_SCHEDULED_WHITELIST.get(project_id) != video_id:
        raise RuntimeError(f"Whitelist mismatch for {project_id}: {video_id}")

    await client.send("Page.bringToFront")
    opened_menu = await client.eval(
        rf"""(() => {{
            {_DEEP_QUERY_HELPER_JS}
            const rows = Array.from(document.querySelectorAll('ytcp-video-row'));
            const row = rows.find(r => Boolean(r.querySelector('a[href*="/video/{video_id}/"]')));
            if (!row) return {{ok: false, reason: 'row_not_found'}};
            const vEl = row.querySelector('.tablecell-visibility, [class*="visibility"]');
            const visText = vEl ? (vEl.innerText || '').replace(/\s+/g, ' ').trim() : '';
            const tEl = row.querySelector('#video-title');
            const rowTitle = tEl ? (tEl.innerText || tEl.textContent || '').replace(/\s+/g, ' ').trim() : '';
            const lowVis = visText.toLowerCase();
            if (lowVis.includes('public') || (visText.includes('공개') && !visText.includes('비공개'))) {{
                return {{ok: false, reason: 'abort_public_row:' + visText, visText, rowTitle}};
            }}
            if (!(lowVis.includes('scheduled') || visText.includes('예약'))) {{
                return {{ok: false, reason: 'not_scheduled:' + visText, visText, rowTitle}};
            }}
            row.scrollIntoView({{block: 'center'}});
            const cell = row.querySelector('ytcp-video-list-cell-video') || row;
            for (const ev of ['mouseenter', 'mouseover', 'mousemove']) {{
                row.dispatchEvent(new MouseEvent(ev, {{bubbles: true, composed: true}}));
                cell.dispatchEvent(new MouseEvent(ev, {{bubbles: true, composed: true}}));
            }}
            const roots = [];
            __collectRoots(row, roots);
            let optBtn = null;
            for (const rt of roots) {{
                if (!rt.querySelectorAll) continue;
                for (const b of rt.querySelectorAll('ytcp-icon-button, button')) {{
                    const aria = (b.getAttribute('aria-label') || '').trim();
                    if (aria === 'Options' || aria === '옵션' || b.id === 'options-button') {{
                        optBtn = b;
                        break;
                    }}
                }}
                if (optBtn) break;
            }}
            if (!optBtn) return {{ok: false, reason: 'options_button_not_mounted', visText, rowTitle}};
            const inner = optBtn.querySelector('button') || (optBtn.shadowRoot && optBtn.shadowRoot.querySelector('button')) || optBtn;
            inner.click();
            return {{ok: true, visText, rowTitle}};
        }})()"""
    )
    if not isinstance(opened_menu, dict) or not opened_menu.get("ok"):
        # Retry once after 0.6s hover settle if options_button_not_mounted
        if isinstance(opened_menu, dict) and opened_menu.get("reason") == "options_button_not_mounted":
            await asyncio.sleep(0.6)
            opened_menu = await client.eval(
                rf"""(() => {{
                    {_DEEP_QUERY_HELPER_JS}
                    const rows = Array.from(document.querySelectorAll('ytcp-video-row'));
                    const row = rows.find(r => Boolean(r.querySelector('a[href*="/video/{video_id}/"]')));
                    if (!row) return {{ok: false, reason: 'row_not_found'}};
                    const vEl = row.querySelector('.tablecell-visibility, [class*="visibility"]');
                    const visText = vEl ? (vEl.innerText || '').replace(/\s+/g, ' ').trim() : '';
                    const tEl = row.querySelector('#video-title');
                    const rowTitle = tEl ? (tEl.innerText || tEl.textContent || '').replace(/\s+/g, ' ').trim() : '';
                    const roots = [];
                    __collectRoots(row, roots);
                    for (const rt of roots) {{
                        if (!rt.querySelectorAll) continue;
                        for (const b of rt.querySelectorAll('ytcp-icon-button, button')) {{
                            const aria = (b.getAttribute('aria-label') || '').trim();
                            if (aria === 'Options' || aria === '옵션' || b.id === 'options-button') {{
                                const inner = b.querySelector('button') || (b.shadowRoot && b.shadowRoot.querySelector('button')) || b;
                                inner.click();
                                return {{ok: true, visText, rowTitle}};
                            }}
                        }}
                    }}
                    return {{ok: false, reason: 'options_button_not_mounted_retry', visText, rowTitle}};
                }})()"""
            )
    if not isinstance(opened_menu, dict) or not opened_menu.get("ok"):
        return {
            "project_id": project_id,
            "video_id": video_id,
            "deleted": False,
            "error": (opened_menu or {}).get("reason", "menu_open_failed"),
        }

    row_title = str(opened_menu.get("rowTitle") or expected_title).strip()
    await asyncio.sleep(0.7)

    # Click "Delete forever" / "완전 삭제" in the open popup menu
    clicked_delete_item = False
    for _ in range(10):
        res_item = await client.eval(
            rf"""(() => {{
                {_DEEP_QUERY_HELPER_JS}
                const items = __queryAllDeep('tp-yt-paper-item');
                for (const it of items) {{
                    if (!__isVisibleEl(it, 'tp-yt-paper-item')) continue;
                    const txt = (it.innerText || it.textContent || '').replace(/\s+/g, ' ').trim().toLowerCase();
                    if (txt === 'delete forever' || txt.includes('delete forever') || txt.includes('완전 삭제')) {{
                        it.click();
                        return true;
                    }}
                }}
                return false;
            }})()"""
        )
        if res_item:
            clicked_delete_item = True
            break
        await asyncio.sleep(0.35)

    if not clicked_delete_item:
        await client.send("Input.dispatchKeyEvent", {"type": "keyDown", "key": "Escape", "code": "Escape", "windowsVirtualKeyCode": 27})
        await client.send("Input.dispatchKeyEvent", {"type": "keyUp", "key": "Escape", "code": "Escape", "windowsVirtualKeyCode": 27})
        return {
            "project_id": project_id,
            "video_id": video_id,
            "deleted": False,
            "error": "delete_forever_menu_item_not_found",
        }

    await asyncio.sleep(0.8)

    # Wait for confirmation dialog and verify title prefix inside dialog
    title_prefix = row_title[:24].lower().strip()
    confirmed = None
    for _ in range(12):
        confirmed = await client.eval(
            rf"""(() => {{
                {_DEEP_QUERY_HELPER_JS}
                const dlgs = __queryAllDeep('ytcp-dialog, tp-yt-paper-dialog');
                const visibleDlgs = dlgs.filter(d => __isVisibleEl(d, 'tp-yt-paper-dialog'));
                const targetDlg = visibleDlgs.find(d => {{
                    const t = (d.innerText || '').toLowerCase();
                    return t.includes('permanently delete') || t.includes('delete forever') || t.includes('영구적으로 삭제') || t.includes('완전 삭제');
                }});
                if (!targetDlg) return {{ready: false}};
                const dlgText = (targetDlg.innerText || '').replace(/\s+/g, ' ').trim();
                const prefix = {json.dumps(title_prefix)};
                if (prefix && !dlgText.toLowerCase().includes(prefix)) {{
                    return {{ready: true, mismatch: true, dlgText: dlgText.slice(0, 220)}};
                }}
                const cbs = __queryAllDeep('#confirm-checkbox, ytcp-checkbox-lit#confirm-checkbox, #confirm-checkbox #checkbox', targetDlg);
                let cbClicked = false;
                for (const cb of cbs) {{
                    const ariaChecked = cb.getAttribute('aria-checked');
                    if (ariaChecked === 'true' || cb.checked === true) {{
                        cbClicked = true;
                        break;
                    }}
                    cb.click();
                    cbClicked = true;
                    break;
                }}
                return {{ready: true, mismatch: false, cbClicked, dlgText: dlgText.slice(0, 180)}};
            }})()"""
        )
        if isinstance(confirmed, dict) and confirmed.get("ready"):
            break
        await asyncio.sleep(0.4)

    if not isinstance(confirmed, dict) or not confirmed.get("ready"):
        return {
            "project_id": project_id,
            "video_id": video_id,
            "deleted": False,
            "error": "confirm_dialog_not_opened",
        }
    if confirmed.get("mismatch"):
        await client.click(["#cancel-button", "ytcp-button#cancel-button"])
        raise RuntimeError(
            f"Confirmation modal title mismatch for {video_id} ('{title_prefix}' not in '{confirmed.get('dlgText')}')"
        )

    await asyncio.sleep(0.45)

    # Ensure checkbox is checked and click #confirm-button
    clicked_confirm = False
    for _ in range(10):
        res_btn = await client.eval(
            rf"""(() => {{
                {_DEEP_QUERY_HELPER_JS}
                const cbs = __queryAllDeep('#confirm-checkbox, ytcp-checkbox-lit#confirm-checkbox, #confirm-checkbox #checkbox');
                for (const cb of cbs) {{
                    if (!__isVisibleEl(cb, '#confirm-checkbox')) continue;
                    const innerBox = cb.querySelector('#checkbox') || (cb.shadowRoot && cb.shadowRoot.querySelector('#checkbox'));
                    const isChecked = cb.checked === true
                        || cb.getAttribute('aria-checked') === 'true'
                        || (innerBox && innerBox.getAttribute('aria-checked') === 'true');
                    if (!isChecked) {{
                        (innerBox || cb).click();
                        return 'toggled_checkbox';
                    }}
                }}
                const btns = __queryAllDeep('ytcp-button#confirm-button, #confirm-button');
                for (const b of btns) {{
                    if (!__isVisibleEl(b, '#confirm-button')) continue;
                    const disabled = b.disabled === true || b.hasAttribute('disabled') || b.getAttribute('aria-disabled') === 'true';
                    const inner = b.querySelector('button') || (b.shadowRoot && b.shadowRoot.querySelector('button'));
                    const innerDisabled = inner && (inner.disabled === true || inner.hasAttribute('disabled') || inner.getAttribute('aria-disabled') === 'true');
                    if (!disabled && !innerDisabled) {{
                        (inner || b).click();
                        return 'clicked_confirm';
                    }}
                }}
                return 'waiting';
            }})()"""
        )
        if res_btn == "clicked_confirm":
            clicked_confirm = True
            break
        await asyncio.sleep(0.4)

    if not clicked_confirm:
        return {
            "project_id": project_id,
            "video_id": video_id,
            "deleted": False,
            "error": "confirm_button_remained_disabled",
        }

    # Poll until the row disappears from /videos/short
    removed = False
    for _ in range(50):
        await asyncio.sleep(0.5)
        still_present = await client.eval(
            f"Boolean(document.querySelector('a[href*=\"/video/{video_id}/\"]'))"
        )
        if not still_present:
            removed = True
            break

    await asyncio.sleep(0.8)
    return {
        "project_id": project_id,
        "video_id": video_id,
        "row_title": row_title,
        "row_visibility": opened_menu.get("visText"),
        "deleted": removed,
        "error": None if removed else "row_still_present_after_timeout",
    }


async def _switch_single_scheduled_to_private(
    client: Any,
    *,
    project_id: str,
    video_id: str,
) -> dict[str, Any]:
    if video_id in PROTECTED_PUBLIC_VIDEO_IDS:
        raise RuntimeError(f"Refusing to touch protected Public video '{video_id}'")
    edit_url = f"https://studio.youtube.com/video/{video_id}/edit"
    await client.send("Page.navigate", {"url": edit_url})
    ready = await client.wait_for_element(["ytcp-video-metadata-editor"], timeout_sec=20.0)
    if not ready:
        return {"project_id": project_id, "video_id": video_id, "switched_private": False, "error": "edit_page_timeout"}
    await asyncio.sleep(1.2)
    await client.send("Page.bringToFront")
    await client.click(["ytcp-video-metadata-visibility #select-button", "ytcp-video-metadata-visibility ytcp-button", "#visibility-button"])
    await asyncio.sleep(0.8)
    await client.click(["tp-yt-paper-radio-button[name='PRIVATE']"])
    await asyncio.sleep(0.6)
    await client.click(["ytcp-video-visibility-select #save-button", "ytcp-button#done-button", "#save-button"])
    await asyncio.sleep(0.8)
    saved = await client.click(["ytcp-video-metadata-editor #save", "ytcp-button#save", "#save"])
    await asyncio.sleep(2.5)
    await client.send("Page.navigate", {"url": STUDIO_CONTENT_URL})
    await _wait_for_shorts_table(client, timeout_sec=20.0)
    return {"project_id": project_id, "video_id": video_id, "switched_private": bool(saved)}


async def _async_unschedule_retired_shorts(
    targets: list[tuple[str, str]],
    *,
    mode: str = "delete",
    dry_run: bool = False,
    cdp_port: int = DEFAULT_CDP_PORT,
) -> dict[str, Any]:
    whale = WhaleSessionController(cdp_port=cdp_port)
    client, temp_target_id = whale.open_temp_direct_client(STUDIO_CONTENT_URL)
    results: list[dict[str, Any]] = []
    post_rows: list[dict[str, Any]] = []

    try:
        await client.__aenter__()
        ready = await _wait_for_shorts_table(client, timeout_sec=25.0)
        if not ready:
            raise RuntimeError("Timed out waiting for YouTube Studio /videos/short table.")

        channel_ok = await client.eval(
            f"location.href.includes({json.dumps(CHANNEL_ID)}) || Boolean(document.querySelector('a[href*=\"{CHANNEL_ID}\"]'))"
        )
        if not channel_ok:
            raise RuntimeError(f"Channel mismatch on Studio tab (expected {CHANNEL_ID}).")

        initial_rows = await _scrape_shorts_rows(client)
        by_vid = {r["video_id"]: r for r in initial_rows if r.get("video_id")}

        if dry_run:
            for pid, vid in targets:
                row = by_vid.get(vid)
                vis_txt = str((row or {}).get("visibility") or "")
                sched_ok = _is_scheduled_visibility_label(vis_txt) if row else False
                results.append(
                    {
                        "project_id": pid,
                        "video_id": vid,
                        "mode": mode,
                        "dry_run": True,
                        "row_found": row is not None,
                        "row_title": (row or {}).get("title"),
                        "row_visibility": vis_txt,
                        "row_date": (row or {}).get("date_text"),
                        "verified_scheduled_not_public": sched_ok,
                    }
                )
            post_rows = initial_rows
        else:
            op_count = 0
            for pid, vid in targets:
                # R36-B: Recycle ONLY our own temporary Studio tab every 3 operations, never touching other tabs
                if op_count > 0 and op_count % 3 == 0:
                    await client.__aexit__(None, None, None)
                    new_client, new_target_id = whale.open_temp_direct_client(STUDIO_CONTENT_URL)
                    whale.close_tab_by_id(temp_target_id)
                    client, temp_target_id = new_client, new_target_id
                    await client.__aenter__()
                    ready = await _wait_for_shorts_table(client, timeout_sec=25.0)
                    if not ready:
                        raise RuntimeError("Timed out waiting for recycled YouTube Studio /videos/short tab.")

                cur_rows = await _scrape_shorts_rows(client)
                cur_map = {r["video_id"]: r for r in cur_rows if r.get("video_id")}
                row = cur_map.get(vid)
                if row is None:
                    results.append(
                        {
                            "project_id": pid,
                            "video_id": vid,
                            "mode": mode,
                            "already_absent_from_page": True,
                            "deleted": mode == "delete",
                        }
                    )
                    continue

                vis_txt = str(row.get("visibility") or "")
                if not _is_scheduled_visibility_label(vis_txt):
                    raise RuntimeError(
                        f"Safety abort on {pid} ({vid}): live Studio visibility is '{vis_txt}', expected Scheduled!"
                    )

                if mode == "delete":
                    res = await _delete_single_scheduled_row(
                        client,
                        project_id=pid,
                        video_id=vid,
                        expected_title=str(row.get("title") or ""),
                    )
                elif mode == "private":
                    res = await _switch_single_scheduled_to_private(
                        client,
                        project_id=pid,
                        video_id=vid,
                    )
                else:
                    raise ValueError(f"Unsupported mode: {mode}")

                results.append(res)
                op_count += 1

            # Reload /videos/short once to capture authoritative post-takedown row state
            await client.send("Page.navigate", {"url": STUDIO_CONTENT_URL})
            await _wait_for_shorts_table(client, timeout_sec=25.0)
            post_rows = await _scrape_shorts_rows(client)
    finally:
        try:
            await client.__aexit__(None, None, None)
        except Exception:
            pass
        whale.close_tab_by_id(temp_target_id)

    remaining_scheduled_retired = [
        r["video_id"]
        for r in post_rows
        if r.get("video_id") in set(RETIRED_LOWPOLY_SCHEDULED_WHITELIST.values())
        and _is_scheduled_visibility_label(str(r.get("visibility") or ""))
    ]
    visible_public_ids = [
        r["video_id"]
        for r in post_rows
        if r.get("video_id") in PROTECTED_PUBLIC_VIDEO_IDS
    ]
    return {
        "mode": mode,
        "dry_run": dry_run,
        "requested_count": len(targets),
        "results": results,
        "post_shorts_row_count": len(post_rows),
        "remaining_scheduled_retired_ids": remaining_scheduled_retired,
        "visible_protected_public_count": len(visible_public_ids),
        "visible_protected_public_ids": visible_public_ids,
        "post_rows": post_rows,
    }


def sync_elapsed_public_shorts(
    *,
    projects_dir: Path | None = None,
    queue_file: Path | None = None,
    now_utc: datetime | None = None,
) -> dict[str, Any]:
    """
    Syncs already-auto-published `diorama_04..07` local receipts to `"public"` / `"published_public"`
    and cleans `staging_queue.json` (moving `diorama_04..07` into `history` and removing retired `08..26`
    + unrendered placeholder scheduled items).
    """
    p_root = projects_dir or PROJECTS_DIR
    q_path = queue_file or STAGING_QUEUE_FILE
    now = now_utc or datetime.now(timezone.utc)
    et_tz = ZoneInfo("America/New_York")

    synced_pids: list[str] = []
    for pid, expected_vid in ELAPSED_PUBLIC_SYNC_MAP.items():
        p_dir = p_root / pid
        pub_dir = p_dir / "06_publish"
        rec_path = pub_dir / "upload_receipt.json"
        if not rec_path.exists():
            continue
        rec = json.loads(rec_path.read_text(encoding="utf-8"))
        if str(rec.get("video_id") or "").strip() != expected_vid:
            continue
        sched_et = str(rec.get("scheduled_time_et") or "").strip()
        m = re.match(r"^(\d{4}-\d{2}-\d{2})\s+(\d{1,2}:\d{2})", sched_et)
        pub_utc_iso = now.isoformat()
        if m:
            dt_et = datetime.strptime(f"{m.group(1)} {m.group(2)}", "%Y-%m-%d %H:%M").replace(tzinfo=et_tz)
            pub_utc_iso = dt_et.astimezone(timezone.utc).isoformat()
        rec["visibility"] = "public"
        rec["status"] = "published_public"
        rec.setdefault("published_at_utc", pub_utc_iso)
        rec["synced_public_at_utc"] = now.isoformat()
        rec_path.write_text(json.dumps(rec, indent=2, ensure_ascii=False), encoding="utf-8")

        manifest_path = p_dir / "00_project_manifest.json"
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["youtube_upload"] = rec
            manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

        write_studio_publish_receipt(pid, projects_dir=p_root)
        synced_pids.append(pid)

    queue_updated = False
    removed_scheduled = 0
    if q_path.exists():
        q_doc = json.loads(q_path.read_text(encoding="utf-8"))
        history = list(q_doc.get("history") or [])
        hist_pids = {str(h.get("project_id") or "") for h in history if isinstance(h, dict)}
        kept_scheduled: list[dict[str, Any]] = []
        retired_pids = set(RETIRED_LOWPOLY_SCHEDULED_WHITELIST.keys())

        for it in q_doc.get("scheduled_items") or []:
            if not isinstance(it, dict):
                continue
            pid = str(it.get("project_id") or "").strip()
            vid = str(it.get("video_id") or "").strip()
            if pid in ELAPSED_PUBLIC_SYNC_MAP:
                h_copy = dict(it)
                h_copy["status"] = "published_public"
                h_copy["visibility"] = "public"
                if pid not in hist_pids:
                    history.append(h_copy)
                    hist_pids.add(pid)
                removed_scheduled += 1
                continue
            if pid in retired_pids or vid in set(RETIRED_LOWPOLY_SCHEDULED_WHITELIST.values()):
                removed_scheduled += 1
                continue
            # Also drop unuploaded placeholder entries from the old 2-slot 100-item batch plan
            if not vid:
                removed_scheduled += 1
                continue
            kept_scheduled.append(it)

        q_doc["history"] = history
        q_doc["scheduled_items"] = kept_scheduled
        q_doc["slots_per_day"] = 1
        q_doc["daily_slots_et"] = ["19:30"]
        q_doc["updated_at"] = now.isoformat()
        q_path.write_text(json.dumps(q_doc, indent=2, ensure_ascii=False), encoding="utf-8")
        queue_updated = True

    return {
        "synced_public_projects": synced_pids,
        "queue_updated": queue_updated,
        "removed_from_scheduled_items": removed_scheduled,
    }


def retire_and_clean_local_lowpoly_projects(
    project_ids: list[str] | None = None,
    *,
    projects_dir: Path | None = None,
    completed_dir: Path | None = None,
    graph_file: Path | None = None,
) -> dict[str, Any]:
    """
    Archives Stage-5 receipts (`*.retired_lowpoly.json`), pops `manifest["youtube_upload"]`,
    resets Stage 4/5 artifact locks, removes retired edges from `short_link_graph.json`,
    and deletes legacy `lowpoly` media across `diorama_08..26` (~5.5 GB freed).
    """
    p_root = projects_dir or PROJECTS_DIR
    comp_dir = completed_dir or (WORKSPACE_ROOT / "Completed_Psychology_100_Shorts")
    g_path = graph_file or SHORT_LINK_GRAPH_FILE
    pids = project_ids if project_ids is not None else list(RETIRED_LOWPOLY_SCHEDULED_WHITELIST.keys())

    for pid in pids:
        if pid not in RETIRED_LOWPOLY_SCHEDULED_WHITELIST:
            raise ValueError(f"Refusing to clean non-whitelisted project '{pid}'")

    bytes_freed = 0
    cleaned_projects: list[dict[str, Any]] = []

    def _dir_bytes(path: Path) -> int:
        total = 0
        if not path.exists():
            return 0
        if path.is_file():
            try:
                return path.stat().st_size
            except OSError:
                return 0
        for sub in path.rglob("*"):
            if sub.is_file():
                try:
                    total += sub.stat().st_size
                except OSError:
                    pass
        return total

    for pid in pids:
        p_dir = p_root / pid
        if not p_dir.is_dir():
            continue
        pub_dir = p_dir / "06_publish"
        archived_receipts: list[str] = []
        for rec_name in (
            "upload_receipt.json",
            "community_receipt.json",
            "related_video_receipt.json",
            "studio_publish_receipt.json",
        ):
            src = pub_dir / rec_name
            if src.exists():
                dst = pub_dir / rec_name.replace(".json", ".retired_lowpoly.json")
                shutil.move(str(src), str(dst))
                archived_receipts.append(dst.name)

        proj_freed = 0
        # Clean 03_visuals legacy clips & screenshots while keeping visual_plan.json & prompts
        vis_dir = p_dir / "03_visuals"
        for sub_name in ("flow_native_clips", "flow_screenshots", "reference_images"):
            sub_p = vis_dir / sub_name
            if sub_p.exists():
                proj_freed += _dir_bytes(sub_p)
                shutil.rmtree(sub_p, ignore_errors=True)
        for f_pat in ("flow_provenance_receipt.json", "episode_qa_contract.json", "reference_image_qa_report.json", "reference_image_review.json"):
            fp = vis_dir / f_pat
            if fp.exists():
                proj_freed += _dir_bytes(fp)
                fp.unlink(missing_ok=True)
        if vis_dir.exists():
            for st_mp4 in vis_dir.glob("_staged_clip_*.mp4"):
                proj_freed += _dir_bytes(st_mp4)
                st_mp4.unlink(missing_ok=True)

        # Clean 04_audio and 05_assembly contents
        for stage_name in ("04_audio", "05_assembly"):
            st_dir = p_dir / stage_name
            if st_dir.exists():
                proj_freed += _dir_bytes(st_dir)
                shutil.rmtree(st_dir, ignore_errors=True)
                st_dir.mkdir(parents=True, exist_ok=True)

        # Clean legacy lowpoly thumbnails & reports in 06_publish
        if pub_dir.exists():
            for pat in ("thumbnail*.png", "thumbnail_report.json", "ab_test_manifest.json", "prepared_comment.json"):
                for fp in pub_dir.glob(pat):
                    proj_freed += _dir_bytes(fp)
                    fp.unlink(missing_ok=True)

        # Clean Completed_Psychology_100_Shorts exported MP4 for this exact retired pid
        if comp_dir.exists():
            for exp_mp4 in comp_dir.glob(f"final_shorts_{pid}*.mp4"):
                proj_freed += _dir_bytes(exp_mp4)
                exp_mp4.unlink(missing_ok=True)

        # Update 00_project_manifest.json cleanly so verify_integrity and regeneration unlock
        manifest_path = p_dir / "00_project_manifest.json"
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            retired_upload = manifest.pop("youtube_upload", None)
            if retired_upload:
                manifest["retired_lowpoly_youtube_upload"] = retired_upload
            stages = manifest.setdefault("stages", {})
            for st_key in ("03_visuals", "04_audio", "05_assembly", "06_publish"):
                if isinstance(stages.get(st_key), dict):
                    stages[st_key]["status"] = "pending"
                    art_map = stages[st_key].get("artifacts")
                    if isinstance(art_map, dict):
                        kept_arts = {
                            k: v
                            for k, v in art_map.items()
                            if (p_dir / st_key / k).exists()
                        }
                        stages[st_key]["artifacts"] = kept_arts
            manifest["updated_at"] = datetime.now(timezone.utc).isoformat()
            manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
            from pipeline.storage import ProjectStorage

            ProjectStorage.sync_existing_manifest_from_disk(p_dir)

        bytes_freed += proj_freed
        cleaned_projects.append(
            {
                "project_id": pid,
                "archived_receipts": archived_receipts,
                "bytes_freed": proj_freed,
                "mb_freed": round(proj_freed / (1024 * 1024), 2),
            }
        )

    # Prune retired video_ids from short_link_graph.json so future link plans never reference deleted videos
    retired_vids = {RETIRED_LOWPOLY_SCHEDULED_WHITELIST[p] for p in pids}
    retired_pid_set = set(pids)
    removed_edges = 0
    if g_path.exists():
        g_doc = json.loads(g_path.read_text(encoding="utf-8"))
        old_edges = list(g_doc.get("edges") or [])
        kept_edges = [
            e
            for e in old_edges
            if isinstance(e, dict)
            and str(e.get("source_project_id") or "") not in retired_pid_set
            and str(e.get("target_project_id") or "") not in retired_pid_set
            and str(e.get("source_video_id") or "") not in retired_vids
            and str(e.get("target_video_id") or "") not in retired_vids
        ]
        removed_edges = len(old_edges) - len(kept_edges)
        if removed_edges > 0:
            g_doc["edges"] = kept_edges
            g_doc["updated_at"] = datetime.now(timezone.utc).isoformat()
            g_path.write_text(json.dumps(g_doc, indent=2, ensure_ascii=False), encoding="utf-8")

    return {
        "cleaned_count": len(cleaned_projects),
        "total_bytes_freed": bytes_freed,
        "total_gb_freed": round(bytes_freed / (1024 ** 3), 3),
        "removed_graph_edges": removed_edges,
        "projects": cleaned_projects,
    }


def run_studio_unschedule(
    *,
    projects_spec: str = "diorama_08..26",
    mode: str = "delete",
    dry_run: bool = False,
    clean_local: bool = False,
    sync_public: bool = False,
    cdp_port: int = DEFAULT_CDP_PORT,
    receipt_path: Path | None = None,
) -> dict[str, Any]:
    targets = resolve_retired_projects(projects_spec)
    studio_res = asyncio.run(
        _async_unschedule_retired_shorts(
            targets,
            mode=mode,
            dry_run=dry_run,
            cdp_port=cdp_port,
        )
    )

    sync_res: dict[str, Any] | None = None
    clean_res: dict[str, Any] | None = None
    if not dry_run:
        if sync_public:
            sync_res = sync_elapsed_public_shorts()
        if clean_local:
            # Only clean projects whose video_id is confirmed absent from Scheduled rows
            remaining_set = set(studio_res.get("remaining_scheduled_retired_ids") or [])
            confirmed_pids = [pid for pid, vid in targets if vid not in remaining_set]
            clean_res = retire_and_clean_local_lowpoly_projects(confirmed_pids)

    report = {
        "schema": "retired_scheduled_takedown_receipt_v1",
        "executed_at_utc": datetime.now(timezone.utc).isoformat(),
        "mode": mode,
        "dry_run": dry_run,
        "studio": studio_res,
        "public_sync": sync_res,
        "local_cleanup": clean_res,
    }
    if not dry_run:
        out_p = receipt_path or (CHANNEL_ROOT / "reports" / "retired_scheduled_takedown_receipt.json")
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report
