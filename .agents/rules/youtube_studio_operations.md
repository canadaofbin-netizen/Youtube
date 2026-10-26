# Rule: YouTube Studio Shorts Operations Protocol

Parent Master Index: [AGENTS.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/AGENTS.md) · Code: `pipeline/studio/` (`config.py` `SLOT_TIMETABLE`, `PILLAR_SLOT_MAP`, `AI_CONTENT_DECLARATION`, `CHANNEL_LOCALIZATION_SPEC`)

Studio scheduling values are owned here (source: `pipeline/studio/config.py`); production values live in [production_constants.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/production_constants.md). All Studio work runs in the visible Naver Whale window (CDP).

---

## R30 — North American 5-Slot Timetable & 3-Notification Cap
YouTube allows at most 3 subscriber push notifications per rolling 24 h. Slots 1, 3, 4 notify; slots 2 and 5 are feed-only.

| Slot | US ET | KST | `notify_subscribers` | Pillars (`PILLAR_SLOT_MAP`) |
|---|---|---|---|---|
| 1 | 07:30 | 21:30 | True | `brain_health` |
| 2 | 12:00 | 02:00 (+1d) | False | `bci_tech`, `brain_news` |
| 3 | 16:00 | 06:00 (+1d) | True | `brain_basics`, `brain_mysteries` |
| 4 | 20:00 | 09:00 (+1d) | True | `brain_history` |
| 5 | 22:30 | 12:30 (+1d) | False | `bci_ethics` |

**R30-B — Seed-audience protection (`StagingQueueManager.enforce_seed_protection_window`):** never publish 2+ Shorts at the same timestamp; keep ≥ 4.0 h between public releases; channels under 10,000 subscribers enforce `daily_prime_only=True` (scheduling only into prime Slots 2 `12:00 ET / 16:00 UTC` and 4 `20:00 ET / 00:00 UTC +1d`, spaced by 8 hours) and keep the rest staged as unlisted.

## R31 — Thumbnails (`PublishStage`)
Three visually distinct portrait variants (`thumbnail_var_A.png` cool blue, `B` crimson alert, `C` emerald/gold question), each > 80 KB, pairwise background diff ≥ 15.0. Optional `--burn-first-frame` prepends variant A as frame 0.

## R32 — 72 h Sequential A/B/C Z-Test (`ThumbnailABTester`)
A (0–24 h) → B (24–48 h) → C (48–72 h). `evaluate_significance` runs a two-proportion Z-test on CTR; |Z| > 1.96 (p < 0.05) locks the winner.

## R33 — Unlisted Staging Vault
Upload as `unlisted` ≥ 24 h before publication so transcoding and suitability checks finish (`upload_receipt.json`).

## R34 — Zero-Duplicate & v5-Gated Queue
`StagingQueueManager` (`BCI_Shorts_Channel/staging_queue.json`) never assigns the same `project_id` to two slots, preserves already-published releases (`published_public` / `published`) in `history`, and blocks legacy v4 drafts (`passes_v5_publish_gate`) from automatic staging unless `--allow-legacy-v4` is explicitly passed.

## R35 — Pinned Editorial Case & DOI Comment (`CommunityManager`)
Post and pin a top editorial commentary comment (`community_receipt.json`) designed so viewers read the full study context while the Short loops in the background:
- **Zero emojis/icons and zero bullet points (`•`)** in the comment body.
- **Line 1 Header**: `[Headline of the Clinical Case or Experiment]`
- **5 Short Editorial Paragraphs** (1–2 sentences each, separated by blank lines, ~110–150 words total):
  1. **Overview / Phenomenon**: What clinical case or neuroscience experiment is drawing attention and what core phenomenon it reveals.
  2. **Experimental Method**: According to the peer-reviewed study (`Author, Year, Journal`), how the researchers conducted the experiment or tested the patient.
  3. **Striking Scene / Neural Mechanism**: The specific test outcome or brain circuit transition that stood out during the study.
  4. **Scientific Nuance / Clarification**: What the finding actually means neurobiologically versus common misconceptions.
  5. **Takeaway + DOI + Viewer Question**: 1-sentence conclusion, clean citation line (`Source: https://doi.org/<doi>`), and one natural viewer question (`social_comment_trigger`).

## R35-B — Short-to-Short `Related video` & 7-Pillar Playlist Ring (`ShortLinkGraph`, `StudioShortLinker`)
- **4-Axis Affinity & Seed-Rescue Ring (`pipeline/studio/short_linker.py`)**: Scores candidate links across canonical neuroanatomy (`0.40`), pillar/visual-mode (`0.25`), lexical/psychological mechanism (`0.20`), and retention quality (`0.15`), redistributing anatomy weight onto pillar + lexical axes when either Short uses `BEHAVIORAL_PSYCH` (R45). `seed_boost` alternates high-view Anchors (`views >= ANCHOR_MIN_VIEWS`) and seed-starved high-retention Shorts (`impressions <= SEED_STARVED_MAX_IMPRESSIONS`) into a closed Hamiltonian ring with zero 2-cycles (`two_cycle_count == 0` for `N >= 3`), prioritizing `published_longform_video_id` when a parent longform documentary is live.
- **Directional Visibility Guard**: `Public` Shorts may link **only** to `Public` targets (never `Unlisted` or `Scheduled`, preventing `"Private video"` dead links when staged items switch to scheduled). `Unlisted` / `Scheduled(T_src)` Shorts may link to `Public` targets or `Scheduled(T_dst)` targets with `T_dst <= T_src`.
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

## Daily Analytics (`07:00 AM` Cron `2e725d86049e`)
`StudioAnalyticsReporter` (`pipeline/studio/reporter.py`) → 9-section daily report (`BCI_Shorts_Channel/reports/LATEST_DAILY_REPORT.md` + `LATEST_STUDIO_CHARTS.png`); procedure in the [`/report_youtube` skill](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/skills/report_youtube/SKILL.md). Automatically executed every morning at **07:00 AM (`0 7 * * *`)** by `@yt-studio` cron job `2e725d86049e` and delivered to Discord `#📊-채널-분석` (`discord:1561516885865005097`) and `@yt-studio` (`bot-chat:yt-studio`).
