# YouTube Studio Operations (`R4`, `R30–R36-B`)

Index: [AGENTS.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/AGENTS.md) | Numbers: [production_constants.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/production_constants.md) | Skills: [youtube-studio](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/skills/youtube-studio/SKILL.md), [youtube-report](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/skills/youtube-report/SKILL.md) | Code: `pipeline/studio/` (`config.py`, `uploader.py`, `staging_queue.py`, `community.py`, `short_linker.py`, `studio_watchdog.py`, `whale_session.py`, `reporter.py`)

## R30 & R30-B — US ET 5-Slot Timetable, `<10K` Prime Lock & Pre-Upload Gate
`SLOT_TIMETABLE` (`America/New_York` -> DST-aware `Asia/Seoul`, `<= MAX_DAILY_SUBSCRIBER_NOTIFICATIONS` = 3/24h):
| Slot | US ET | KST (EDT/EST) | Notify | `PILLAR_SLOT_MAP` |
|---|---|---|---|---|
| 1 | `07:30` | `20:30 / 21:30` | `True` | `brain_health` |
| 2 (Prime) | `12:00` | `01:00 / 02:00 (+1d)` | `False` | `bci_tech`, `brain_news` |
| 3 | `16:00` | `05:00 / 06:00 (+1d)` | `True` | `brain_basics`, `brain_mysteries` |
| 4 (Prime) | `20:00` | `09:00 / 10:00 (+1d)` | `True` | `brain_history` |
| 5 | `22:30` | `11:30 / 12:30 (+1d)` | `False` | `bci_ethics` |

- **R30-B (`enforce_seed_protection_window`)**: Zero simultaneous releases; `>= 4.0h` gap; `<10K` subs enforce `daily_prime_only=True` (Prime Slots `12:00 ET` & `20:00 ET`, 8h apart; hold `16:9` Longform until Shorts scale; rest staged `unlisted`). (`us_diorama_timetable.py` handles multi-format ET windows when enabled.)
- **Pre-Upload QA Bundle Lock (`verify_publish_ready_qa_bundle`)**: Blocks upload/queue unless SHA-256-bound `video_autopsy_report.json` (`passed`), plus on `neuro_diorama`: `dynamic_episode_qa_report.json` (`DQ1–DQ12`), `posthoc_semantic_qa_report.json` (`R64`), `posthoc_semantic_review.json` (`valid`), and `06_publish/thumbnail_report.json` (`R65` `TQ1–TQ7`).

## R31 & R32 — Thumbnails, `cover_frame_sec` & Shorts A/B Lock
- **R31 (`R65`, `pipeline/thumbnail_studio.py`)**: Scores clean frames across eligible EDL cuts (excluding `THUMB_EXCLUDE_MODES` & outro), renders top-3 distinct `thumbnail_var_A/B/C.png` (`> THUMB_MIN_FILE_BYTES`, pairwise diff `>= THUMB_MIN_PAIRWISE_DIFF`) with `visual_plan.thumbnail.hook_text` in `AABCondensed-Black` (`THUMB_HOOK_STROKE_PX` stroke, `TQ1–TQ7`), and records `cover_frame_sec` in `upload_receipt.json` (`--burn-first-frame` skipped on `neuro_diorama`).
- **R32 (`ThumbnailABTester` — Longform Only)**: Desktop Studio disables custom Shorts thumbnail swaps (`<= SHORTS_HARD_CEILING_SEC`); `swap_to_variant` returns `status: "not_applicable_shorts"` without opening CDP. Z-test (`|Z| > 1.96`, `p < 0.05`) is reserved for `> SHORTS_HARD_CEILING_SEC` longform.

## R33, R34, R36, R4 & R36-B — Staging, Localization, AI Disclosure & CDP Hygiene
- **R33 / R34 (`StagingQueueManager`, `staging_queue.json`)**: Stage `unlisted` `>= 24h` pre-publish (`upload_receipt.json`); zero duplicate `project_id`, preserve `published_public` history, block legacy v4 (`passes_v5_publish_gate`) & `PRE_R66_FROZEN_PROJECT_PREFIXES` (`studio_batch_100_scheduler.py` / `sanitize_scheduled_metadata.py`).
- **R36 & R4 (`configure_studio_localization`)**: `CHANNEL_RESIDENCE_COUNTRY="KR"`, `VIDEO_LANGUAGE_CODE="en-US"`, `TITLE_DESCRIPTION_LANGUAGE_CODE="en-US"`, category `DEFAULT_VIDEO_CATEGORY_STUDIO` (`Science and technology`), `"Altered or synthetic content" = Yes` (`AI_CONTENT_DECLARATION`).
- **R36-B (`DirectCDPClient`, `recycle_studio_tab`)**: Recursively pierces open Polymer/Lit `shadowRoot` trees to click inner `<button class="ytcpButtonShapeImplHost">` (`#done-button`, `#next-button`, `#save`, `#action-1`); recycles **only** self-owned `studio.youtube.com` tabs every `STUDIO_TAB_RECYCLE_INTERVAL` (3) ops without touching sibling/user tabs.

## R35 & R35-B — Pinned DOI Debate Comment & `Public`-Only `Related video` Ring
- **R35 (`CommunityManager`, `community_receipt.json`)**: Conversational US English, zero emojis/bullets (`•`), zero `BANNED_COMMENT_VIOLENCE_TOKENS`:
  - Line 1 (`<= PINNED_COMMENT_LINE1_MAX_CHARS`, above mobile 3-line fold): `offcenter_creator_bet` (`<= DEBATE_CREATOR_BET_MAX_PREFIX_CHARS`) + binary/personal debate question ending in `?`.
  - Line 3: Complete case headline -> 5 short paragraphs (`~110–155w`: Phenomenon -> Method `Author, Year, Journal` -> Striking Scene/Mechanism -> Myth vs Reality -> Takeaway + `Source: https://doi.org/<doi>`).
- **R35-B (`ShortLinkGraph`, `StudioShortLinker`)**: 4-axis affinity (`0.40` anatomy, `0.25` pillar/mode, `0.20` lexical, `0.15` retention; redistributes anatomy on `BEHAVIORAL_PSYCH`) + `seed_boost` Hamiltonian ring (`two_cycle_count == 0` for `N >= 3`). Links **`Public` targets only** (`dst_vis == "public"`), defers `< 24.0h` new uploads (`deferred_seed_lock` unless `--force`), upserts `short_link_graph.json` non-destructively, assigns `PILLAR_PLAYLIST_MAP` playlist, and verifies DOM read-back (`related_video_receipt.json`, `studio_publish_receipt.json`).

## Daily Report & Go-Live Watchdog (`studio-report`, `studio-watchdog`)
- **Zero-Fallback Report (`reporter.py`)**: Writes `reports/daily/` (`LATEST_DAILY_REPORT.md` + PNG charts when requested); returns `status: "unavailable_cdp_offline"` with `None`/`"N/A"` when Studio CDP is offline — never fabricates metrics.
- **Watchdog (`studio_watchdog.py`)**: Promotes elapsed `Scheduled` -> `published_public`, runs missing `R35` pins + `R35-B` `Related video` links, audits `staging_queue.json`, and closes idle `about:blank` / stale Studio edit tabs.
