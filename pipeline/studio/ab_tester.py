"""
ALL ABOUT BRAIN - YouTube Shorts 72-Hour Sequential Thumbnail A/B Tester
Manages sequential thumbnail rotation (Variant A -> B -> C), parses Search & Browse CTR,
and executes Two-Proportion Z-Test statistical significance evaluations (p < 0.05).
"""

import asyncio
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pipeline.storage import ProjectStorage
from pipeline.studio.config import (
    CHANNEL_ID,
    DEFAULT_CDP_PORT,
    THUMBNAIL_SWAP_SELECTORS,
)
from pipeline.studio.short_linker import write_studio_publish_receipt
from pipeline.studio.whale_session import WhaleSessionController


class ThumbnailABTester:
    """
    Coordinates sequential thumbnail swapping for Shorts and performs
    two-proportion Z-test statistical significance analysis on Search & Browse CTR.
    """

    def __init__(self, cdp_port: int = DEFAULT_CDP_PORT, projects_dir: Path | None = None):
        self.cdp_port = cdp_port
        self.projects_dir = projects_dir
        self.session = WhaleSessionController(cdp_port=cdp_port)

    @staticmethod
    def calculate_z_score(
        clicks_1: int,
        impressions_1: int,
        clicks_2: int,
        impressions_2: int
    ) -> dict[str, Any]:
        """
        Calculates two-proportion Z-test and two-tailed p-value.
        H0: p1 == p2
        H1: p1 != p2
        """
        if impressions_1 <= 0 or impressions_2 <= 0:
            return {
                "z_score": 0.0,
                "p_value": 1.0,
                "statistically_significant": False,
                "ctr_1": 0.0,
                "ctr_2": 0.0,
                "winner": None
            }

        p1 = clicks_1 / impressions_1
        p2 = clicks_2 / impressions_2
        ctr_1 = round(p1 * 100.0, 2)
        ctr_2 = round(p2 * 100.0, 2)

        # Pooled sample proportion
        pooled_p = (clicks_1 + clicks_2) / (impressions_1 + impressions_2)

        if pooled_p == 0 or pooled_p == 1:
            return {
                "z_score": 0.0,
                "p_value": 1.0,
                "statistically_significant": False,
                "ctr_1": ctr_1,
                "ctr_2": ctr_2,
                "winner": None
            }

        se = math.sqrt(pooled_p * (1 - pooled_p) * ((1 / impressions_1) + (1 / impressions_2)))
        if se == 0:
            z = 0.0
        else:
            z = (p1 - p2) / se

        # Two-tailed p-value using math.erf
        p_val = 2.0 * (1.0 - 0.5 * (1.0 + math.erf(abs(z) / math.sqrt(2.0))))

        is_significant = p_val < 0.05 and abs(z) >= 1.96
        winner = None
        if is_significant:
            winner = "var_1" if p1 > p2 else "var_2"

        return {
            "z_score": round(z, 4),
            "p_value": round(p_val, 5),
            "statistically_significant": is_significant,
            "ctr_1": ctr_1,
            "ctr_2": ctr_2,
            "winner": winner
        }

    def load_manifest(self, project_id: str) -> tuple[dict[str, Any], ProjectStorage]:
        """Loads ab_test_manifest.json for the project."""
        storage = ProjectStorage(project_id, projects_dir=self.projects_dir)
        manifest = storage.load_json("06_publish", "ab_test_manifest.json")
        if not manifest:
            raise FileNotFoundError(f"ab_test_manifest.json not found in project '{project_id}'. Run PublishStage first.")
        return manifest, storage

    def get_next_variant(self, current: str) -> str:
        """Determines next variant in sequence (A -> B -> C -> A)."""
        rotation = {"A": "B", "B": "C", "C": "A"}
        return rotation.get(current.upper(), "A")

    async def _async_swap_thumbnail(
        self,
        video_id: str,
        new_thumb_path: Path,
        dry_run: bool = False
    ) -> bool:
        """Navigates to Studio video edit page via DirectCDPClient and uploads replacement thumbnail."""
        if dry_run:
            print(f"[ThumbnailABTester] [DRY RUN] Simulating thumbnail swap to {new_thumb_path.name} on video {video_id}...")
            return True

        from pipeline.studio.whale_session import _DEEP_QUERY_HELPER_JS

        studio_edit_url = f"https://studio.youtube.com/video/{video_id}/edit"
        print(f"[ThumbnailABTester] Navigating to Video Details via DirectCDPClient: {studio_edit_url}...")

        client = self.session.get_direct_client("studio.youtube.com", default_url=studio_edit_url)
        async with client:
            await client.send("Page.enable")
            await client.send("Runtime.enable")
            await client.send("Page.bringToFront")
            await client.send("Page.navigate", {"url": studio_edit_url})
            ready = await client.wait_for_element(["ytcp-video-metadata-editor"], timeout_sec=20.0)
            if not ready:
                print("[ThumbnailABTester] Warning: Studio video edit page timed out.")
                return False
            await asyncio.sleep(1.8)

            has_channel = await client.eval(
                f"""(() => {{
                    {_DEEP_QUERY_HELPER_JS}
                    if (location.href.includes('{CHANNEL_ID}')) return true;
                    return __queryAllDeep('a[href*="{CHANNEL_ID}"]').length > 0;
                }})()"""
            )
            if not has_channel:
                print("[ThumbnailABTester] Warning: Active Studio tab is not on ALL ABOUT BRAIN channel.")
                return False

            shorts_thumb_locked = await client.eval(
                f"""(() => {{
                    {_DEEP_QUERY_HELPER_JS}
                    const host = __queryAllDeep(
                        'ytcp-thumbnails-compact-editor, ytcp-thumbnails-compact-editor-uploader, ytcp-video-thumbnail-editor, ytcp-still-picker'
                    )[0];
                    const bodyTxt = ((host ? host.innerText : '') || (document.body ? document.body.innerText : '') || '');
                    if (/can't change the thumbnail on your Short|cannot change the thumbnail on your Short|for now, you can't change the thumbnail|Shorts에서는 아직 썸네일을 변경할 수 없|모바일 YouTube 앱에서 썸네일/i.test(bodyTxt)) {{
                        return bodyTxt.slice(0, 180).trim();
                    }}
                    if (host && (host.hasAttribute('disabled') || host.getAttribute('aria-disabled') === 'true')) {{
                        return 'shorts_desktop_thumbnail_uploader_disabled';
                    }}
                    return '';
                }})()"""
            )
            if shorts_thumb_locked:
                print(
                    f"[ThumbnailABTester] Desktop custom thumbnail upload is disabled by YouTube Studio for Shorts ({shorts_thumb_locked}). Skipping gracefully."
                )
                return False

            if await client.find_element(THUMBNAIL_SWAP_SELECTORS["thumbnail_options_menu"]):
                await client.click(THUMBNAIL_SWAP_SELECTORS["thumbnail_options_menu"])
                await asyncio.sleep(0.8)
                await client.click(THUMBNAIL_SWAP_SELECTORS["change_thumbnail_item"])
                await asyncio.sleep(0.8)

            try:
                uploaded = await client.set_file_input(
                    new_thumb_path,
                    selector="input#file-loader, input[type='file'][accept*='image'], ytcp-thumbnail-editor input[type='file'], ytcp-thumbnails-compact-editor-uploader input[type='file']",
                )
            except Exception as exc:
                print(f"[ThumbnailABTester] Warning: Custom thumbnail file input unavailable ({exc}).")
                return False
            if not uploaded:
                print("[ThumbnailABTester] Warning: Could not locate thumbnail file input in Studio edit page.")
                return False

            await asyncio.sleep(2.0)
            saved = await client.click(THUMBNAIL_SWAP_SELECTORS["details_save_button"])
            if saved:
                for _ in range(24):
                    await asyncio.sleep(0.5)
                    disabled = await client.eval(
                        f"""(() => {{
                            {_DEEP_QUERY_HELPER_JS}
                            const btn = __queryAllDeep('ytcp-button#save, #save')[0];
                            if (!btn) return false;
                            return btn.hasAttribute('disabled') || btn.getAttribute('aria-disabled') === 'true';
                        }})()"""
                    )
                    if disabled:
                        break
            return bool(saved)

    def _is_shorts_video(self, storage: ProjectStorage) -> bool:
        """Returns True when the project is a Short (`<= SHORTS_HARD_CEILING_SEC` or `neuro_diorama` Shorts profile)."""
        from pipeline.config import SHORTS_HARD_CEILING_SEC, is_diorama_profile

        vp = storage.load_json("03_visuals", "visual_plan.json") or {}
        sc = storage.load_json("02_script", "script.json") or {}
        meta = storage.load_json("06_publish", "metadata.json") or {}
        if is_diorama_profile(vp) or is_diorama_profile(sc) or is_diorama_profile(meta):
            return True
        edl = storage.load_json("05_assembly", "edit_decision_list.json") or {}
        if edl.get("total_duration_sec") and float(edl["total_duration_sec"]) <= SHORTS_HARD_CEILING_SEC:
            return True
        final_mp4 = storage.get_stage_dir("05_assembly") / "final_shorts_1080x1920.mp4"
        if final_mp4.exists():
            try:
                import cv2

                cap = cv2.VideoCapture(str(final_mp4))
                fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
                fc = float(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0.0)
                cap.release()
                if fps > 0 and fc > 0 and (fc / fps) <= SHORTS_HARD_CEILING_SEC:
                    return True
            except Exception:
                return True
        return False

    def swap_to_variant(
        self,
        project_id: str,
        target_variant: str,
        video_id: str | None = None,
        dry_run: bool = False
    ) -> dict[str, Any]:
        """
        Swaps active thumbnail to a specific target variant ('A', 'B', or 'C') for long-form videos.
        R32 / R65: Desktop YouTube Studio locks custom thumbnail swapping on Shorts (`<= SHORTS_HARD_CEILING_SEC`),
        so live Shorts swaps and `neuro_diorama` Shorts return `status='not_applicable_shorts'` without opening CDP.
        """
        from pipeline.config import is_diorama_profile

        p_dir = (self.projects_dir / project_id) if self.projects_dir else None
        storage_probe = ProjectStorage(project_id, projects_dir=self.projects_dir) if p_dir else ProjectStorage(project_id)
        vp = storage_probe.load_json("03_visuals", "visual_plan.json") or {}
        sc = storage_probe.load_json("02_script", "script.json") or {}
        is_diorama = is_diorama_profile(vp) or is_diorama_profile(sc)
        if is_diorama or (not dry_run and self._is_shorts_video(storage_probe)):
            now_iso = datetime.now(timezone.utc).isoformat()
            manifest_opt = storage_probe.load_json("06_publish", "ab_test_manifest.json") or {}
            cur_var = manifest_opt.get("current_active_variant", "A")
            return {
                "project_id": project_id,
                "status": "not_applicable_shorts",
                "previous_variant": cur_var,
                "active_variant": cur_var,
                "swapped_at": now_iso,
                "swap_success": False,
                "reason": "Desktop YouTube Studio locks custom thumbnail rotation on Shorts (R32 applies to long-form only; use R65 cover_frame_sec).",
            }

        manifest, storage = self.load_manifest(project_id)
        target = target_variant.upper()
        if target not in manifest["variants"]:
            raise ValueError(f"Unknown variant '{target}'. Available: {list(manifest['variants'].keys())}")

        if not video_id:
            receipt = storage.load_json("06_publish", "upload_receipt.json") or {}
            video_id = receipt.get("video_id", f"sim_{project_id[:11]}")

        target_file = storage.get_stage_dir("06_publish") / manifest["variants"][target]["file"]
        if not target_file.exists():
            raise FileNotFoundError(f"Thumbnail file not found: {target_file}")

        success = asyncio.run(self._async_swap_thumbnail(video_id, target_file, dry_run=dry_run))

        now_iso = datetime.now(timezone.utc).isoformat()
        prev_variant = manifest.get("current_active_variant", "A")

        if not success and not dry_run:
            print(f"[ThumbnailABTester] Warning: Live thumbnail swap failed for {project_id}. Manifest retained at Variant {prev_variant}.")
            return {
                "project_id": project_id,
                "video_id": video_id,
                "previous_variant": prev_variant,
                "active_variant": prev_variant,
                "thumbnail_file": str(target_file),
                "swapped_at": now_iso,
                "swap_success": False
            }

        # Update schedule items
        for item in manifest.get("schedule", []):
            if item["variant"] == prev_variant and item.get("status") == "active":
                item["status"] = "completed"
                item["ended_at"] = now_iso
            elif item["variant"] == target:
                item["status"] = "active"
                item["started_at"] = now_iso
                item["ended_at"] = None

        manifest["current_active_variant"] = target
        manifest["last_swapped_at"] = now_iso
        manifest["status"] = f"active_testing_var_{target}"

        storage.save_json("06_publish", "ab_test_manifest.json", manifest)
        if not dry_run:
            write_studio_publish_receipt(project_id, projects_dir=self.projects_dir)

        return {
            "project_id": project_id,
            "video_id": video_id,
            "previous_variant": prev_variant,
            "active_variant": target,
            "thumbnail_file": str(target_file),
            "swapped_at": now_iso,
            "swap_success": success
        }

    def swap_next(
        self,
        project_id: str,
        video_id: str | None = None,
        dry_run: bool = False
    ) -> dict[str, Any]:
        """Rotates to the next variant in the 72h sequence."""
        manifest, _ = self.load_manifest(project_id)
        current = manifest.get("current_active_variant", "A")
        next_var = self.get_next_variant(current)
        return self.swap_to_variant(project_id, target_variant=next_var, video_id=video_id, dry_run=dry_run)

    def evaluate_significance(
        self,
        project_id: str,
        metrics: dict[str, dict[str, int]] | None = None,
        dry_run: bool = False
    ) -> dict[str, Any]:
        """
        Evaluates Search & Browse CTR data across variants using Two-Proportion Z-Test.
        Declares statistically significant winner when p < 0.05 (|Z| >= 1.96).
        Correctly evaluates whether Variant A (baseline) or a challenger (Variant B / C) wins.
        """
        manifest, storage = self.load_manifest(project_id)

        if not metrics:
            manifest_vars = manifest.get("variants") or {}
            extracted_metrics: dict[str, dict[str, int]] = {}
            for v_key in ("A", "B", "C"):
                v_obj = manifest_vars.get(v_key) or {}
                extracted_metrics[v_key] = {
                    "impressions": int(v_obj.get("impressions") or 0),
                    "clicks": int(v_obj.get("clicks") or 0),
                }
            has_real_metrics = any(v["impressions"] > 0 for v in extracted_metrics.values())
            if has_real_metrics:
                metrics = extracted_metrics
            elif not dry_run:
                return {
                    "project_id": project_id,
                    "status": "awaiting_real_metrics",
                    "significant": False,
                    "conclusive": False,
                    "locked": False,
                    "winner_variant": None,
                }
            else:
                # Demo metrics ONLY when dry_run=True explicitly
                metrics = {
                    "A": {"impressions": 1250, "clicks": 68},   # 5.44% CTR
                    "B": {"impressions": 1180, "clicks": 98},   # 8.31% CTR
                    "C": {"impressions": 1150, "clicks": 112}   # 9.74% CTR
                }

        pairs = [("A", "B"), ("A", "C"), ("B", "C")]
        comparisons = []
        pair_results: dict[str, dict[str, Any]] = {}

        for var1, var2 in pairs:
            m1 = metrics.get(var1, {"impressions": 0, "clicks": 0})
            m2 = metrics.get(var2, {"impressions": 0, "clicks": 0})

            z_res = self.calculate_z_score(
                clicks_1=m1["clicks"],
                impressions_1=m1["impressions"],
                clicks_2=m2["clicks"],
                impressions_2=m2["impressions"]
            )

            pair_winner = None
            if z_res["statistically_significant"]:
                pair_winner = var1 if z_res["winner"] == "var_1" else var2

            comp_record = {
                "pair": f"{var1}_vs_{var2}",
                "var_1": {"variant": var1, "impressions": m1["impressions"], "clicks": m1["clicks"], "ctr": z_res["ctr_1"]},
                "var_2": {"variant": var2, "impressions": m2["impressions"], "clicks": m2["clicks"], "ctr": z_res["ctr_2"]},
                "z_score": z_res["z_score"],
                "p_value": z_res["p_value"],
                "statistically_significant": z_res["statistically_significant"],
                "pair_winner": pair_winner,
                "significance_threshold_p": 0.05
            }
            comparisons.append(comp_record)
            pair_results[f"{var1}_vs_{var2}"] = comp_record

        # Rank all variants by observed CTR
        def get_ctr(v: str) -> float:
            m = metrics.get(v, {"impressions": 0, "clicks": 0})
            return (m["clicks"] / m["impressions"]) if m.get("impressions", 0) > 0 else 0.0

        ranked_variants = sorted(["A", "B", "C"], key=get_ctr, reverse=True)
        top_var = ranked_variants[0]

        winner_candidate = None

        if top_var == "A":
            # Baseline A wins if it is statistically significantly superior to BOTH B and C
            a_vs_b = pair_results.get("A_vs_B", {})
            a_vs_c = pair_results.get("A_vs_C", {})
            b_sig = a_vs_b.get("statistically_significant") and a_vs_b.get("pair_winner") == "A"
            c_sig = a_vs_c.get("statistically_significant") and a_vs_c.get("pair_winner") == "A"
            if b_sig and c_sig:
                winner_candidate = "A"
        else:
            # Challenger (B or C) wins if it is statistically significantly superior to baseline A
            vs_a_key = f"A_vs_{top_var}"
            vs_a = pair_results.get(vs_a_key, {})
            beats_a_sig = vs_a.get("statistically_significant") and vs_a.get("pair_winner") == top_var

            # And check against the other challenger
            other_challenger = "C" if top_var == "B" else "B"
            b_vs_c_key = "B_vs_C"
            b_vs_c = pair_results.get(b_vs_c_key, {})
            # Did the other challenger beat top_var? No, top_var has higher or equal CTR
            other_beat_top = b_vs_c.get("statistically_significant") and b_vs_c.get("pair_winner") == other_challenger

            if beats_a_sig and not other_beat_top:
                winner_candidate = top_var

        now_iso = datetime.now(timezone.utc).isoformat()
        is_conclusive = winner_candidate is not None

        report = {
            "project_id": project_id,
            "evaluated_at": now_iso,
            "status": "conclusive" if is_conclusive else "inconclusive",
            "metric": "Search & Browse CTR",
            "statistical_test": "Two-Proportion Z-Test",
            "alpha_threshold": 0.05,
            "z_critical": 1.96,
            "significant": is_conclusive,
            "conclusive": is_conclusive,
            "locked": is_conclusive and not dry_run,
            "winner_variant": winner_candidate if is_conclusive else None,
            "winner_hypothesis": manifest["variants"][winner_candidate].get("hypothesis", "Cognitive dissonance & provocative defiance trigger; high-CTR curiosity gap.") if is_conclusive else None,
            "comparisons": comparisons,
            "metrics_input": metrics
        }

        # Update manifest
        manifest.setdefault("statistical_evaluation", {})
        manifest["statistical_evaluation"]["winner_variant"] = winner_candidate
        manifest["statistical_evaluation"]["locked"] = is_conclusive
        manifest["statistical_evaluation"]["last_evaluated_at"] = now_iso
        if is_conclusive:
            manifest["status"] = f"completed_winner_{winner_candidate}"
            # Lock the winner thumbnail as standard thumbnail.png
            winner_file = storage.get_stage_dir("06_publish") / manifest["variants"][winner_candidate]["file"]
            default_thumb = storage.get_stage_dir("06_publish") / "thumbnail.png"
            if winner_file.exists():
                import shutil
                shutil.copy2(winner_file, default_thumb)
                storage.record_artifact("06_publish", "thumbnail.png", default_thumb)

        storage.save_json("06_publish", "ab_test_report.json", report)
        storage.save_json("06_publish", "ab_test_manifest.json", manifest)

        return report
