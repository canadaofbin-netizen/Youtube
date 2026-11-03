# Rule: YouTube Studio Shorts Operations Protocol

Parent Master Index: [AGENTS.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/AGENTS.md) · Code: `pipeline/studio/` (`config.py` `SLOT_TIMETABLE`, `PILLAR_SLOT_MAP`, `AI_CONTENT_DECLARATION`, `CHANNEL_LOCALIZATION_SPEC`)

Studio scheduling values are owned here (source: `pipeline/studio/config.py`); production values live in [production_constants.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/production_constants.md). All Studio work runs in the visible Naver Whale window (CDP).

---

## R30 — North American 5-Slot Timetable & 3-Notification Cap
YouTube allows at most 3 subscriber push notifications per rolling 24 h. Slots 1, 3, 4 notify; slots 2 and 5 are feed-only.

| Slot | US ET (`America/New_York`) | KST (`Asia/Seoul`, EDT / EST) | `notify_subscribers` | Pillars (`PILLAR_SLOT_MAP`) |
|---|---|---|---|---|
| 1 | 07:30 | 20:30 / 21:30 | True | `brain_health` |
| 2 | 12:00 | 01:00 / 02:00 (+1d) | False | `bci_tech`, `brain_news` |
| 3 | 16:00 | 05:00 / 06:00 (+1d) | True | `brain_basics`, `brain_mysteries` |
| 4 | 20:00 | 09:00 / 10:00 (+1d) | True | `brain_history` |
| 5 | 22:30 | 11:30 / 12:30 (+1d) | False | `bci_ethics` |

**R30-B — Seed-audience protection & DST-aware scheduling (`StagingQueueManager.enforce_seed_protection_window`):** never publish 2+ Shorts at the same timestamp; keep ≥ 4.0 h between public releases; channels under 10,000 subscribers enforce `daily_prime_only=True` (scheduling only into prime Slots 2 `12:00 ET` and 4 `20:00 ET`, spaced by 8 hours, dynamically converted from `ZoneInfo("America/New_York")` into the browser's `ZoneInfo("Asia/Seoul")` local schedule picker across US DST transitions) and keep the rest staged as unlisted.

**Pre-Upload QA Bundle Lock (`verify_publish_ready_qa_bundle`):** `StudioUploader` and `StagingQueueManager` block uploading or queueing any Short unless `05_assembly/final_shorts_1080x1920.mp4` passes SHA-256-bound `video_autopsy_report.json` (`passed == True`), and for `neuro_diorama` projects also `dynamic_episode_qa_report.json` (`DQ1–DQ12` `passed == True`), `posthoc_semantic_qa_report.json` (`R64` `passed == True`), `posthoc_semantic_review.json` (`valid == True`), and SHA-256-bound `06_publish/thumbnail_report.json` (`R65` `TQ1–TQ7` `passed == True` on production builds).

## R31 — Thumbnails & In-Video Cover Frame (`thumbnail_studio` / `PublishStage`)
- **Flagship `neuro_diorama` Shorts (`R65`, `pipeline/thumbnail_studio.py`)**: Scores clean frames across every eligible EDL cut (`THUMB_CANDIDATE_SAMPLES_PER_CUT`, excluding `THUMB_EXCLUDE_MODES` and outro), selects top-3 visually distinct cuts (`thumbnail_var_A/B/C.png`, each `> THUMB_MIN_FILE_BYTES`, pairwise ROI diff `>= THUMB_MIN_PAIRWISE_DIFF`), overlays the hand-authored `visual_plan.thumbnail.hook_text` in bundled `AABCondensed-Black` (`THUMB_HOOK_STROKE_PX` dark stroke + soft halo, zero legacy v6 boxes/pills), and enforces `TQ1–TQ7` (`06_publish/thumbnail_report.json` + `thumbnail_contact_sheet.png`). When desktop Studio locks custom Shorts thumbnail uploads, `upload_receipt.json` records `cover_frame_sec` (aligned with the cold-open stamp headline) for 1-tap mobile frame selection. `--burn-first-frame` is deprecated and skipped on `neuro_diorama` to protect the `R57-H2` cold-open.
- **Legacy v4/v5 (`PublishStage`)**: Retains three portrait variants (`A`, `B`, `C`) for backward compatibility.

## R32 — Sequential A/B/C Z-Test (`ThumbnailABTester` — Long-Form Only)
Desktop YouTube Studio disables custom thumbnail swapping on Shorts (`<= SHORTS_HARD_CEILING_SEC`). `ThumbnailABTester.swap_to_variant` returns `status: "not_applicable_shorts"` without opening CDP on Shorts; `evaluate_significance` (two-proportion Z-test, `|Z| > 1.96`, `p < 0.05`) is reserved for long-form documentaries (`> SHORTS_HARD_CEILING_SEC`). Shorts cover optimization accumulates cross-episode hook/grammar telemetry in `BCI_Shorts_Channel/knowledge_base/`.

## R33 — Unlisted Staging Vault
Upload as `unlisted` ≥ 24 h before publication so transcoding and suitability checks finish (`upload_receipt.json`).

## R34 — Zero-Duplicate & v5-Gated Queue
`StagingQueueManager` (`BCI_Shorts_Channel/staging_queue.json`) never assigns the same `project_id` to two slots, preserves already-published releases (`published_public` / `published`) in `history`, and blocks legacy v4 drafts (`passes_v5_publish_gate`) from automatic staging unless `--allow-legacy-v4` is explicitly passed.

## R35 — Pinned Editorial Case & DOI Comment (`CommunityManager` — Mobile-Fold First + `YouTube Natural Script` Tone)
Post and pin a top editorial commentary comment (`community_receipt.json`) written in **human-sounding, ear-first conversational US English** (adapted from `/natural_script`: zero AI-essay clichés, zero stiff medical jargon like *rostrocaudal resection* or *efference-copy*, smooth `—` explanatory clauses) so viewers see the engagement question immediately above YouTube mobile's 3-line `Read more` fold and can read the full study story below:
- **Zero emojis/icons and zero bullet points (`•`)** in the comment body.
- **Line 1 Above Mobile Fold**: A **specific A-vs-B or concrete personal-experience debate question** (`social_comment_trigger` ending in `?`) so mobile Shorts viewers see the prompt without tapping `Read more`.
- **Line 3 Case Header**: `[Concise, Complete Case Headline — never mid-word truncated]`
- **5 Short Conversational Paragraphs** (1–2 sentences each, separated by blank lines, ~110–155 words total):
  1. **Overview / Phenomenon**: Concrete human story & what makes the clinical case or experiment astonishing.
  2. **Experimental Method**: Cleanly attributed peer-reviewed study (`Author, Year, Journal` parsed accurately from `citation` or `authors`) explaining in plain language what the team actually tested.
  3. **Striking Scene / Neural Mechanism**: The most memorable concrete moment from the experiment and the brain pathway behind it.
  4. **Myth vs. Reality**: What people usually assume versus what the data actually proved, explained conversationally without textbook jargon.
  5. **Everyday Takeaway + DOI**: 1-sentence human takeaway followed by a clean citation line (`Source: https://doi.org/<doi>`).

## R35-B — Short-to-Short `Related video` & 7-Pillar Playlist Ring (`ShortLinkGraph`, `StudioShortLinker`)
- **4-Axis Affinity & Seed-Rescue Ring (`pipeline/studio/short_linker.py`)**: Scores candidate links across canonical neuroanatomy (`0.40`), pillar/visual-mode (`0.25`), lexical/psychological mechanism (`0.20`), and retention quality (`0.15`), redistributing anatomy weight onto pillar + lexical axes when either Short uses `BEHAVIORAL_PSYCH` (R45). `seed_boost` alternates high-view Anchors (`views >= ANCHOR_MIN_VIEWS`) and seed-starved high-retention Shorts (`impressions <= SEED_STARVED_MAX_IMPRESSIONS`) into a closed Hamiltonian ring with zero 2-cycles (`two_cycle_count == 0` for `N >= 3`), prioritizing `published_longform_video_id` when a parent longform documentary is live.
- **Public-Only Target Guard**: Both `Public` and `Scheduled` Shorts select **`Public` targets only** (`dst_vis == "public"`, prioritizing same-pillar `16:9` Long-Form documentaries and top-performing `Public` Anchor Shorts), because YouTube Studio's `ytcp-video-pick-dialog` hides `Scheduled` and `Unlisted` items and linking non-Public targets causes dead or unselectable links.
- **Non-Destructive Graph Upsert**: Single-project runs (`--project <id>`) merge/upsert that project's edge into `BCI_Shorts_Channel/short_link_graph.json` without overwriting existing channel edges.
- **24h Seed-Pool Lock**: Newly public Shorts (`< 24.0h` elapsed) defer `Related video` edits (`deferred_seed_lock`) unless `--force` is passed.
- **7-Pillar Playlist & Consolidated Receipt**: Assigns (and auto-creates if absent) the canonical `PILLAR_PLAYLIST_MAP` playlist, verifies the saved `Related video` via DOM read-back (`06_publish/related_video_receipt.json`), writes `BCI_Shorts_Channel/short_link_graph.json`, and updates `06_publish/studio_publish_receipt.json`.

## R36 — Localization Lock (`StudioUploader.configure_studio_localization`)
| Tier | Setting |
|---|---|
| Channel residence | `CHANNEL_RESIDENCE_COUNTRY` = KR (Korean AdSense tax residency) |
| Video + metadata language | `VIDEO_LANGUAGE_CODE` / `TITLE_DESCRIPTION_LANGUAGE_CODE` = en-US |
| Category | `DEFAULT_VIDEO_CATEGORY_STUDIO` (Science and technology) |

## R4 — AI Disclosure
Every upload sets "Altered or synthetic content" = Yes (`AI_CONTENT_DECLARATION`).

## R36-B — Polymer / Shadow-DOM Click & Tab Memory Hygiene (`DirectCDPClient`, `WhaleSessionController.recycle_studio_tab`)
- YouTube Studio's `ytcp-button` elements (`#done-button`, `#next-button`, `#save`, `#action-1`) and nested Lit/Polymer dialogs (`ytcp-video-pick-dialog`, `ytcp-playlist-dialog`) render inside open `shadowRoot` trees and wrap an inner native `<button class="ytcpButtonShapeImplHost">`. `DirectCDPClient` (`pipeline/studio/whale_session.py`) pierces open shadow roots recursively and clicks the inner `<button>` so final `Publish` / `Schedule` / `Save` submissions never stall.
- During multi-video batch uploads or edits (> 3 videos), `WhaleSessionController.recycle_studio_tab()` recycles **only** the `studio.youtube.com` tab every `STUDIO_TAB_RECYCLE_INTERVAL` (3) operations so Chromium renderer heap stays clean while leaving all non-YouTube user tabs untouched.

## Daily Analytics & Zero-Fallback Telemetry (`07:00 AM` Cron `2e725d86049e`)
- `StudioAnalyticsReporter` (`pipeline/studio/reporter.py`) → 9-section daily report (`BCI_Shorts_Channel/reports/LATEST_DAILY_REPORT.md` + `LATEST_STUDIO_CHARTS.png`); procedure in the [`/report_youtube` skill](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/skills/report_youtube/SKILL.md).
- **Zero-Fallback Policy**: Never injects synthetic or placeholder numbers (including never fabricating `engaged_views = views * apv`) when live YouTube Studio CDP telemetry is unavailable (`status: "unavailable_cdp_offline"` with `None` / `"N/A"` fields instead of fabricated counts).

## Autonomous Go-Live Watchdog, US Prime Timetable & Frozen Legacy Lock
- **Studio Watchdog (`pipeline/studio/studio_watchdog.py`, `main.py studio-watchdog`)**: Detects `Scheduled` Shorts whose UTC publish timestamp has elapsed, promotes their local receipt status to `published_public`, triggers missing **R35** DOI comment pins (`CommunityManager`), updates **R35-B** `Public`-only `Related video` rings (`StudioShortLinker` preserving existing valid links), audits `staging_queue.json`, and cleans up idle temporary `about:blank` / stale Studio edit tabs in Naver Whale.
- **US East-to-West Prime Timetable (`pipeline/studio/us_diorama_timetable.py`)**: Schedules in `ZoneInfo("America/New_York")` (`Mon–Wed 11:30 ET` Micro-Short / `20:30 ET` Flagship Diorama, `Thu–Sat 15:30 ET` Micro-Short / `21:00 ET` Flagship Diorama, `Sunday 09:30 ET` `16:9` 4K CTV Long-Form / `19:30 ET` Flagship Diorama), converting automatically across US DST transitions with `<= 2` daily subscriber notifications.
- **Frozen Pre-R66 Queue Protection (`PRE_R66_FROZEN_PROJECT_PREFIXES`)**: `studio_batch_100_scheduler.py` blocks overwriting the active queue with legacy `psych_01..100` items unless `--force-legacy-psych` is explicitly passed, and `pipeline/studio/sanitize_scheduled_metadata.py` replaces clone titles and script-copy descriptions on scheduled Shorts with dossier-backed editorial summaries.
