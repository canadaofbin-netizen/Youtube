#!/usr/bin/env python3
"""
Safe Scheduled Draft Swap for `Ep #9` (`v8_ep09_maguire_london_taxi_hippocampus`):
  1. Verifies `06_publish/upload_receipt.json` has a newly Scheduled `video_id != '7lKtSWvTmpw'`.
  2. Links `new_video_id`'s `Related video` -> `p4ou90cHt50` (`Why Deep Brain Loops Lock Habits on Autopilot`, 1,617 views).
  3. Verifies on `/videos/short` in a background leased CDP tab that `new_video_id` is `Scheduled`, then
     permanently deletes (`Delete forever`) ONLY the superseded unpublished Scheduled draft `7lKtSWvTmpw`
     so `Private = 0` and `Scheduled = 1` per Rule R75.
  4. Captures background proof screenshot & updates `BCI_Shorts_Channel/staging_queue.json`.
"""

from __future__ import annotations

import asyncio
import base64
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline.cdp_tab_lease import enable_background_focus_emulation, leased_cdp_tab
from pipeline.config import PROJECTS_DIR
from pipeline.studio.short_linker import StudioShortLinker
from pipeline.studio.whale_session import _DEEP_QUERY_HELPER_JS

OLD_DRAFT_ID = "7lKtSWvTmpw"
ANCHOR_TARGET_ID = "p4ou90cHt50"
PROJECT_ID = "v8_ep09_maguire_london_taxi_hippocampus"
ARTIFACT_DIR = Path("/home/canadaofbin/.gemini/antigravity-cli/brain/b57c97a8-6324-4c31-a2bb-16b25e28dd55")


async def _verify_new_and_delete_old(new_vid: str, screenshot_out: Path, cdp_port: int = 9222) -> dict:
    shorts_url = "https://studio.youtube.com/channel/UC4FeioYYv9X04Di07_MfZ7g/videos/short"
    async with leased_cdp_tab("about:blank", purpose="ep09_r80_scheduled_swap", cdp_port=cdp_port, background=True) as (
        client,
        _tid,
        _owner,
    ):
        await client.send("Page.enable")
        await client.send("Runtime.enable")
        await enable_background_focus_emulation(client)
        await client.send("Page.navigate", {"url": shorts_url}, timeout_sec=35.0)
        await client.wait_for_element(["ytcp-video-row"], timeout_sec=25.0)
        await asyncio.sleep(2.5)

        pre_rows = await client.eval(
            f"""(() => {{
                {_DEEP_QUERY_HELPER_JS}
                return __queryAllDeep('ytcp-video-row').map(r => {{
                    const a = __queryAllDeep('a[href*="/video/"]', r)[0];
                    const href = a ? (a.getAttribute('href') || '') : '';
                    const m = href.match(/\\/video\\/([A-Za-z0-9_-]{{11}})/);
                    return {{
                        video_id: m ? m[1] : '',
                        text: (r.innerText || '').replace(/\\s+/g, ' ').trim().slice(0, 600)
                    }};
                }});
            }})()"""
        )
        new_row = next((r for r in (pre_rows or []) if r.get("video_id") == new_vid), None)
        if not new_row:
            raise RuntimeError(f"Refusing to delete {OLD_DRAFT_ID}: new Scheduled video {new_vid} not found on /videos/short!")
        low_new = str(new_row.get("text") or "").lower()
        if not ("scheduled" in low_new or "예약" in low_new):
            raise RuntimeError(f"Refusing to delete {OLD_DRAFT_ID}: new video {new_vid} row is not Scheduled ({new_row})")

        rect = await client.eval(
            f"""(() => {{
                {_DEEP_QUERY_HELPER_JS}
                const rows = __queryAllDeep('ytcp-video-row');
                const row = rows.find(r => __queryAllDeep('a[href*="/video/"]', r).some(a => (a.getAttribute('href') || '').includes({json.dumps(OLD_DRAFT_ID)})));
                if (!row) return null;
                const txt = (row.innerText || '').replace(/\\s+/g, ' ').toLowerCase();
                if (!(txt.includes('scheduled') || txt.includes('private') || txt.includes('unlisted') || txt.includes('예약') || txt.includes('비공개') || txt.includes('일부 공개'))) {{
                    return {{unsafeVisibility: txt.slice(0, 100)}};
                }}
                row.scrollIntoView({{block: 'center'}});
                const r = row.getBoundingClientRect();
                return {{x: r.left + 120, y: r.top + r.height / 2}};
            }})()"""
        )
        deleted_old = False
        del_reason = "ok"
        if not rect:
            del_reason = "already_absent"
        elif "x" not in rect:
            del_reason = str(rect)
        else:
            await client.send("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": float(rect["x"]), "y": float(rect["y"])})
            await asyncio.sleep(0.9)
            clicked_opt = await client.eval(
                f"""(() => {{
                    {_DEEP_QUERY_HELPER_JS}
                    const rows = __queryAllDeep('ytcp-video-row');
                    const row = rows.find(r => __queryAllDeep('a[href*="/video/"]', r).some(a => (a.getAttribute('href') || '').includes({json.dumps(OLD_DRAFT_ID)})));
                    if (!row) return false;
                    const btns = __queryAllDeep('ytcp-icon-button, button', row).filter(b => b.getBoundingClientRect().width > 0);
                    const opt = btns.find(b => (b.id || '').includes('overflow') || (b.getAttribute('aria-label') || '').toLowerCase().includes('option') || (b.getAttribute('aria-label') || '').includes('옵션')) || btns[btns.length - 1];
                    if (!opt) return false;
                    const inner = opt.tagName === 'BUTTON' ? opt : (__queryAllDeep('button', opt)[0] || opt);
                    inner.click();
                    return true;
                }})()"""
            )
            if not clicked_opt:
                del_reason = "options_button_not_stamped"
            else:
                await asyncio.sleep(1.1)
                clicked_del = await client.eval(
                    f"""(() => {{
                        {_DEEP_QUERY_HELPER_JS}
                        const items = __queryAllDeep('tp-yt-paper-item').filter(e => e.getBoundingClientRect().width > 0);
                        const match = items.find(e => {{
                            const t = (e.innerText || '').trim().toLowerCase();
                            return t.includes('delete forever') || t.includes('완전히 삭제');
                        }});
                        if (match) {{ match.click(); return true; }}
                        return false;
                    }})()"""
                )
                if not clicked_del:
                    del_reason = "delete_forever_menu_not_found"
                else:
                    await asyncio.sleep(1.4)
                    await client.eval(
                        f"""(() => {{
                            {_DEEP_QUERY_HELPER_JS}
                            const cbs = __queryAllDeep('ytcp-checkbox-lit#confirm-checkbox, ytcp-checkbox-lit, #confirm-checkbox').filter(e => e.getBoundingClientRect().width > 0);
                            for (const c of cbs) {{
                                const box = __queryAllDeep('#checkbox, [role="checkbox"]', c)[0] || c;
                                box.click();
                            }}
                        }})()"""
                    )
                    await asyncio.sleep(0.8)
                    confirmed = await client.eval(
                        f"""(() => {{
                            {_DEEP_QUERY_HELPER_JS}
                            const btns = __queryAllDeep('ytcp-confirmation-dialog #confirm-button, ytcp-dialog #confirm-button, ytcp-button#confirm-button').filter(b => b.getBoundingClientRect().width > 0);
                            const vis = btns[0];
                            if (!vis) return false;
                            const inner = __queryAllDeep('button', vis)[0] || vis;
                            inner.click();
                            return true;
                        }})()"""
                    )
                    await asyncio.sleep(6.0)
                    deleted_old = bool(confirmed)

        await client.send("Page.navigate", {"url": shorts_url}, timeout_sec=35.0)
        await client.wait_for_element(["ytcp-video-row"], timeout_sec=25.0)
        await asyncio.sleep(2.5)
        post_rows = await client.eval(
            f"""(() => {{
                {_DEEP_QUERY_HELPER_JS}
                return __queryAllDeep('ytcp-video-row').map(r => {{
                    const a = __queryAllDeep('a[href*="/video/"]', r)[0];
                    const href = a ? (a.getAttribute('href') || '') : '';
                    const m = href.match(/\\/video\\/([A-Za-z0-9_-]{{11}})/);
                    return {{
                        video_id: m ? m[1] : '',
                        text: (r.innerText || '').replace(/\\s+/g, ' ').trim().slice(0, 600)
                    }};
                }});
            }})()"""
        )
        # Background screenshot without stealing focus
        try:
            await client.send("Page.startScreencast", {"format": "png", "maxWidth": 1440, "maxHeight": 900})
            await asyncio.sleep(0.4)
            shot = await client.send("Page.captureScreenshot", {"format": "png"}, timeout_sec=15.0)
            await client.send("Page.stopScreencast")
            if isinstance(shot, dict) and shot.get("data"):
                screenshot_out.write_bytes(base64.b64decode(shot["data"]))
        except Exception:
            pass

        private_remaining = [
            r for r in (post_rows or [])
            if "private" in str(r.get("text") or "").lower() or "비공개" in str(r.get("text") or "")
        ]
        old_still_present = any(r.get("video_id") == OLD_DRAFT_ID for r in (post_rows or []))
        return {
            "new_video_id": new_vid,
            "old_draft_id": OLD_DRAFT_ID,
            "deleted_old": deleted_old,
            "delete_reason": del_reason,
            "old_still_present": old_still_present,
            "private_remaining_count": len(private_remaining),
            "top_rows": (post_rows or [])[:5],
        }


def main() -> int:
    proj_dir = PROJECTS_DIR / PROJECT_ID
    rec_path = proj_dir / "06_publish" / "upload_receipt.json"
    if not rec_path.exists():
        raise FileNotFoundError(f"Missing {rec_path}; run studio-upload first!")
    rec = json.loads(rec_path.read_text(encoding="utf-8"))
    new_vid = str(rec.get("video_id") or "").strip()
    if not new_vid or new_vid == OLD_DRAFT_ID:
        raise RuntimeError(f"Invalid or unchanged video_id in upload_receipt.json: {new_vid!r}")

    # 1. Link new_vid -> Anchor p4ou90cHt50 (skip if already applied for new_vid)
    rel_rec_p = proj_dir / "06_publish" / "related_video_receipt.json"
    rel_rec = json.loads(rel_rec_p.read_text(encoding="utf-8")) if rel_rec_p.exists() else {}
    if rel_rec.get("source_video_id") == new_vid and rel_rec.get("target_video_id") == ANCHOR_TARGET_ID:
        link_res = rel_rec
    else:
        linker = StudioShortLinker(cdp_port=9222)
        link_res = linker.link_single_video(
            PROJECT_ID,
            ANCHOR_TARGET_ID,
            assign_playlist=False,
            dry_run=False,
            force=True,
        )

    # 2. Verify new_vid Scheduled & Delete forever old 7lKtSWvTmpw
    shot_path = ARTIFACT_DIR / "ep09_v2_studio_scheduled_swap_verified.png"
    swap_res = asyncio.run(_verify_new_and_delete_old(new_vid, shot_path, cdp_port=9222))

    # 3. Update staging_queue.json if present
    sq_path = ROOT / "BCI_Shorts_Channel" / "staging_queue.json"
    if sq_path.exists():
        sq = json.loads(sq_path.read_text(encoding="utf-8"))
        changed = False
        for k, v in (sq.get("slots") or {}).items():
            if isinstance(v, dict) and (v.get("video_id") == OLD_DRAFT_ID or v.get("project_id") == PROJECT_ID):
                v["video_id"] = new_vid
                v["studio_url"] = f"https://studio.youtube.com/video/{new_vid}/edit"
                changed = True
        for row in (sq.get("scheduled_items") or sq.get("queue") or sq.get("items") or []):
            if isinstance(row, dict) and (row.get("video_id") == OLD_DRAFT_ID or row.get("project_id") == PROJECT_ID):
                row["video_id"] = new_vid
                if "shorts_url" in row:
                    row["shorts_url"] = f"https://www.youtube.com/shorts/{new_vid}"
                changed = True
        if changed:
            tmp_sq = sq_path.parent / f".{sq_path.name}.tmp.{os.getpid()}"
            tmp_sq.write_text(json.dumps(sq, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            os.replace(tmp_sq, sq_path)

    print(json.dumps({"link_result": link_res, "swap_result": swap_res}, indent=2, ensure_ascii=False))
    return 0 if (not swap_res["old_still_present"] and swap_res["private_remaining_count"] == 0) else 1


if __name__ == "__main__":
    raise SystemExit(main())
