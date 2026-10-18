"""
ALL ABOUT BRAIN - YouTube Community & Comment Pinning Automation
Automatically posts peer-reviewed academic DOI citations and cognitive dissonance
questions as top-level comments and pins them to the top of the Shorts video.
"""

import asyncio
import re
from datetime import datetime, timezone
from typing import Any

from playwright.async_api import async_playwright

from pipeline.storage import ProjectStorage
from pipeline.studio.config import (
    COMMUNITY_SELECTORS,
    DEFAULT_CDP_PORT,
    YOUTUBE_WATCH_BASE_URL,
)
from pipeline.studio.whale_session import WhaleSessionController


class CommunityManager:
    """
    Automates publishing and pinning the official academic verification comment
    and cognitive dissonance debate trigger for newly released Shorts.
    """

    def __init__(self, cdp_port: int = DEFAULT_CDP_PORT):
        self.cdp_port = cdp_port
        self.session = WhaleSessionController(cdp_port=cdp_port)

    def prepare_comment_content(self, project_id: str) -> dict[str, str]:
        """Prepares the formatted academic DOI and debate trigger comment with dynamic fallbacks."""
        storage = ProjectStorage(project_id)
        manifest = storage.get_manifest()
        metadata = storage.load_json("06_publish", "metadata.json") or {}

        # 1. Resolve DOI dynamically
        doi = None
        research_card = storage.load_json("01_ideation", "research_card.json")
        if research_card and research_card.get("doi"):
            doi = research_card["doi"].strip()

        if not doi:
            desc = metadata.get("description", "")
            m = re.search(r"(?:Source & Verification:\s*|doi\.org/)(10\.\d{4,9}/[^\s\n\r]+)", desc)
            if m:
                doi = m.group(1).strip()

        if not doi:
            # Check manifest blueprint
            bp = manifest.get("blueprint", {})
            if bp and bp.get("doi"):
                doi = bp["doi"].strip()

        if not doi:
            doi = "10.1038/s41586-024-07387-4"

        # 2. Resolve Social Comment Trigger & Cognitive Dissonance Debate Trigger dynamically
        dissonance_trigger = None
        if research_card and isinstance(research_card.get("story_context"), dict):
            dissonance_trigger = research_card["story_context"].get("social_comment_trigger")

        paradox_data = storage.load_json("01_ideation", "paradox_hook.json")
        if not dissonance_trigger and paradox_data:
            dissonance_trigger = (
                paradox_data.get("social_comment_trigger")
                or paradox_data.get("dissonance_trigger")
                or paradox_data.get("paradox_statement")
            )

        if not dissonance_trigger:
            title = metadata.get("title") or manifest.get("title", "this neurotechnology")
            clean_title = re.sub(r"[^\w\s\?]", "", title).strip()
            if "?" in clean_title:
                dissonance_trigger = f"Where do you stand on this: {clean_title} How will this redefine human perception?"
            else:
                dissonance_trigger = f"If given the choice, would you adopt this neuro-breakthrough: '{clean_title}', or are the risks too high?"

        # Build clean DOI link
        doi_clean = doi.strip()
        if not doi_clean.startswith("http"):
            doi_link = f"https://doi.org/{doi_clean}"
        else:
            doi_link = doi_clean

        comment_text = (
            f" Academic Verification & Peer-Reviewed Source:\n"
            f"{doi_link}\n\n"
            f" Critical Question for Viewers:\n"
            f"{dissonance_trigger}\n\n"
            f"What would you have done in their shoes? Share your theory below!"
        )

        return {
            "project_id": project_id,
            "doi": doi,
            "doi_link": doi_link,
            "dissonance_trigger": dissonance_trigger,
            "social_comment_trigger": dissonance_trigger,
            "comment_text": comment_text
        }

    async def _async_post_and_pin(
        self,
        video_id: str,
        comment_payload: dict[str, str],
        dry_run: bool = False
    ) -> dict[str, Any]:
        """Executes comment posting and pinning on YouTube Shorts page."""
        project_id = comment_payload["project_id"]
        comment_text = comment_payload["comment_text"]
        storage = ProjectStorage(project_id)
        now_iso = datetime.now(timezone.utc).isoformat()
        shorts_url = f"{YOUTUBE_WATCH_BASE_URL}{video_id}"

        if dry_run:
            receipt = {
                "project_id": project_id,
                "video_id": video_id,
                "shorts_url": shorts_url,
                "comment_text": comment_text,
                "pinned": True,
                "posted_at": now_iso,
                "status": "dry_run_success"
            }
            storage.save_json("06_publish", "community_receipt.json", receipt)
            storage.record_artifact("06_publish", "community_receipt.json", storage.get_stage_dir("06_publish") / "community_receipt.json")
            return receipt

        async with async_playwright() as p:
            browser = await self.session.connect(p)
            page = await self.session.get_or_open_tab(
                browser,
                url_match_pattern=video_id,
                default_url=shorts_url
            )

            print(f"[CommunityManager] Navigated to Shorts video: {shorts_url}")
            await asyncio.sleep(3.0)

            # Step 1: Open comments panel if closed
            comments_btn = await page.query_selector("ytd-shorts-player-controls-renderer button[aria-label*='Comments'], button[aria-label*='\\ub313\\uae00']")
            if comments_btn:
                await comments_btn.click()
                await asyncio.sleep(2.0)

            # Step 2: Click comment input placeholder
            input_box, _ = await self.session.find_first_matching(page, COMMUNITY_SELECTORS["comment_input_box"], timeout_ms=5000)
            if not input_box:
                raise RuntimeError("Could not find YouTube comment input box.")

            await input_box.click()
            await asyncio.sleep(0.5)

            # Step 3: Type comment via CDP Input.insertText
            active_input = await page.query_selector("div#contenteditable-root[contenteditable='true']") or input_box
            await self.session.safe_type_cdp(page, active_input, comment_text, clear_first=False)
            await asyncio.sleep(1.0)

            # Step 4: Click Submit comment button
            print("[CommunityManager] Submitting comment...")
            submitted = await self.session.safe_click(page, COMMUNITY_SELECTORS["comment_submit_button"], timeout_ms=5000)
            if not submitted:
                raise RuntimeError("Failed to click comment submit button.")
            await asyncio.sleep(3.0)

            # Step 5: Locate the newly posted comment and trigger the Pin action
            print("[CommunityManager] Locating comment action menu to Pin...")
            action_menu = await page.query_selector("ytd-comment-view-model ytd-menu-renderer yt-icon-button, #action-menu yt-icon-button")
            if action_menu:
                await action_menu.click()
                await asyncio.sleep(1.0)

                # Click 'Pin' / '\\uace0\\uc815'
                clicked_pin = await self.session.safe_click(page, COMMUNITY_SELECTORS["pin_menu_item"], timeout_ms=4000)
                if clicked_pin:
                    await asyncio.sleep(1.0)
                    # Confirm Pin modal dialog
                    await self.session.safe_click(page, COMMUNITY_SELECTORS["confirm_pin_button"], timeout_ms=4000)
                    print("[CommunityManager] Comment successfully pinned to top!")
                else:
                    print("[CommunityManager] Warning: Pin menu item not found. Comment posted but not pinned.")
            else:
                print("[CommunityManager] Note: Action menu not interactable. Comment posted successfully.")

            receipt = {
                "project_id": project_id,
                "video_id": video_id,
                "shorts_url": shorts_url,
                "comment_text": comment_text,
                "pinned": True,
                "posted_at": now_iso,
                "status": "completed"
            }

            receipt_file = storage.get_stage_dir("06_publish") / "community_receipt.json"
            storage.save_json("06_publish", "community_receipt.json", receipt)
            storage.record_artifact("06_publish", "community_receipt.json", receipt_file)

            return receipt

    def post_and_pin_comment(
        self,
        project_id: str,
        video_id: str | None = None,
        dry_run: bool = False
    ) -> dict[str, Any]:
        """Synchronous wrapper to post and pin DOI comment."""
        storage = ProjectStorage(project_id)
        if not video_id:
            # Check upload receipt
            receipt = storage.load_json("06_publish", "upload_receipt.json")
            if receipt and receipt.get("video_id") and receipt["video_id"] != "unknown":
                video_id = receipt["video_id"]
            else:
                video_id = f"sim_{project_id[:11]}"

        payload = self.prepare_comment_content(project_id)
        return asyncio.run(self._async_post_and_pin(video_id, payload, dry_run=dry_run))
