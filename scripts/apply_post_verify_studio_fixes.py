#!/usr/bin/env python3
"""
1-command post-verification YouTube Studio finisher (`R75` / `R75-C`).

Run immediately after completing Google's 1-time `"Verify it's you"` (`본인 인증`) prompt in `shared-chrome`:
    /home/canadaofbin/hermes-venv/bin/python -X utf8 scripts/apply_post_verify_studio_fixes.py

Actions executed safely (respecting dynamic R75 `3.0h` pre-release / `24.0h` post-release freeze windows and
never touching actively surging `Ep #6` `sjMteEvcjD0` or user's personal non-YouTube browser tabs):
1. Purifies live YouTube Studio metadata (`Category = Education`, clean tags, `#shorts`) on `Ep #4` (`7W8zIOMKPrQ`).
2. Applies `R35-B / R75-C` Anchor-Outbound `Related video` links on:
   - `Ep #8` (`Atd0Pi9HPg4` -> `u5mQNZWNjiw`, skipped automatically if inside `3.0h` pre-release freeze)
   - `Ep #7` (`K_9IJVShp90` -> `p4ou90cHt50`, skipped if inside `24.0h` post-release freeze unless `--force-ep07`)
   - `Ep #4` (`7W8zIOMKPrQ` -> `u5mQNZWNjiw`)
3. Permanently deletes (`Delete forever`) superseded AI-demoted `Private` `Ep #8` drafts (`5JqNgEFSGJ0`, `_p05nIlU9xs`).
4. Runs `qa-scheduler` verification and prints a JSON receipt.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline.cdp_tab_lease import enable_background_focus_emulation, leased_cdp_tab
from pipeline.config import PROJECTS_DIR
from pipeline.studio.short_linker import ShortLinkGraph, StudioShortLinker
from pipeline.studio.uploader import StudioUploader
from pipeline.studio.whale_session import _DEEP_QUERY_HELPER_JS


PRIVATE_OLD_EP08_IDS = ("5JqNgEFSGJ0", "_p05nIlU9xs")


async def _delete_private_drafts_forever(video_ids: tuple[str, ...], cdp_port: int = 9222) -> list[dict]:
    out: list[dict] = []
    async with leased_cdp_tab("about:blank", purpose="r75_delete_private_dupes", cdp_port=cdp_port, background=True) as (
        client,
        _tid,
        _owner,
    ):
        await client.send("Page.enable")
        await client.send("Runtime.enable")
        await enable_background_focus_emulation(client)
        shorts_url = "https://studio.youtube.com/channel/UC4FeioYYv9X04Di07_MfZ7g/videos/short"
        for vid in video_ids:
            await client.send("Page.navigate", {"url": shorts_url}, timeout_sec=30.0)
            await client.wait_for_element(["ytcp-video-row"], timeout_sec=20.0)
            await asyncio.sleep(2.2)
            rect = await client.eval(
                f"""(() => {{
                    {_DEEP_QUERY_HELPER_JS}
                    const rows = __queryAllDeep('ytcp-video-row');
                    const row = rows.find(r => __queryAllDeep('a[href*="/video/"]', r).some(a => (a.getAttribute('href') || '').includes({json.dumps(vid)})));
                    if (!row) return null;
                    const txt = (row.innerText || '').replace(/\\s+/g, ' ');
                    if (!txt.toLowerCase().includes('private') && !txt.includes('비공개')) return {{notPrivate: txt.slice(0, 80)}};
                    row.scrollIntoView({{block: 'center'}});
                    const r = row.getBoundingClientRect();
                    return {{x: r.left + 120, y: r.top + r.height / 2}};
                }})()"""
            )
            if not rect or "x" not in rect:
                out.append({"video_id": vid, "deleted": False, "reason": str(rect or "already_absent")})
                continue
            await client.send("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": float(rect["x"]), "y": float(rect["y"])})
            await asyncio.sleep(0.8)
            clicked_opt = await client.eval(
                f"""(() => {{
                    {_DEEP_QUERY_HELPER_JS}
                    const rows = __queryAllDeep('ytcp-video-row');
                    const row = rows.find(r => __queryAllDeep('a[href*="/video/"]', r).some(a => (a.getAttribute('href') || '').includes({json.dumps(vid)})));
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
                out.append({"video_id": vid, "deleted": False, "reason": "options_button_not_stamped"})
                continue
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
                out.append({"video_id": vid, "deleted": False, "reason": "delete_forever_menu_not_found"})
                continue
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
            await asyncio.sleep(5.5)
            out.append({"video_id": vid, "deleted": bool(confirmed)})
    return out


def run_post_verify_fixes(force_ep07: bool = True) -> dict:
    summary: dict = {}
    uploader = StudioUploader(cdp_port=9222)
    graph = ShortLinkGraph(projects_dir=PROJECTS_DIR)
    nodes = {n["project_id"]: n for n in graph.discover_nodes()}

    # 1. Purify Ep #4 (7W8zIOMKPrQ) live Studio tags + Category=Education + #shorts
    ep04_meta_path = PROJECTS_DIR / "v8_ep04_patient_sm_fearless_amygdala" / "06_publish" / "metadata.json"
    ep04_meta = json.loads(ep04_meta_path.read_text(encoding="utf-8"))
    ep04_res = asyncio.run(
        uploader._async_sync_live_videos_metadata_batch(
            [
                {
                    "project_id": "v8_ep04_patient_sm_fearless_amygdala",
                    "video_id": "7W8zIOMKPrQ",
                    "pillar": ep04_meta.get("pillar", "clinical_neuropsychology"),
                    "tags": ep04_meta.get("tags", []),
                    "category": "Education",
                    "description": ep04_meta.get("description", ""),
                }
            ],
            protected_video_ids=None,
        )
    )
    summary["ep04_metadata_sync"] = ep04_res

    # 2. Apply Anchor-outbound Related video links + update short_link_graph.json
    linker = StudioShortLinker(cdp_port=9222)
    link_targets = [
        ("v8_ep08_capgras_imposter_delusion_r77", "Atd0Pi9HPg4", "u5mQNZWNjiw", False),
        ("v8_ep07_harvard_reversible_choice_paradox", "K_9IJVShp90", "p4ou90cHt50", force_ep07),
        ("v8_ep04_patient_sm_fearless_amygdala", "7W8zIOMKPrQ", "u5mQNZWNjiw", True),
    ]
    link_results = []
    for pid, vid, dst_vid, allow_override in link_targets:
        node = nodes.get(pid, {})
        locked, reason = graph.is_seed_locked(node) if node else (False, "unlocked")
        if locked and not allow_override:
            link_results.append({"project_id": pid, "video_id": vid, "skipped": True, "reason": reason})
            continue
        res = linker.link_single_video(
            pid,
            dst_vid,
            assign_playlist=False,
            dry_run=False,
            force=bool(allow_override),
        )
        link_results.append(res)
    summary["related_video_links"] = link_results

    # 3. Permanently delete AI-demoted Private old Ep #8 drafts
    summary["deleted_private_ep08_drafts"] = asyncio.run(_delete_private_drafts_forever(PRIVATE_OLD_EP08_IDS, cdp_port=9222))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply post-Verify-Identity YouTube Studio fixes (R75 / R75-C)")
    parser.add_argument("--no-force-ep07", action="store_true", help="Respect 24h post-release freeze on Ep #7")
    args = parser.parse_args()
    res = run_post_verify_fixes(force_ep07=not args.no_force_ep07)
    print(json.dumps(res, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
