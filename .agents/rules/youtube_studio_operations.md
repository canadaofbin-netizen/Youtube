# Rule: YouTube Studio Shorts Operations Protocol

Parent Master Index: [AGENTS.md](file:///g:/My%20Drive/Kyubin_Yun_Workspace/07_Youtube/.agents/AGENTS.md) · Code: `pipeline/studio/` (`config.py` `SLOT_TIMETABLE`, `PILLAR_SLOT_MAP`, `AI_CONTENT_DECLARATION`, `CHANNEL_LOCALIZATION_SPEC`)

Studio scheduling values are owned here (source: `pipeline/studio/config.py`); production values live in [production_constants.md](file:///g:/My%20Drive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/production_constants.md). All Studio work runs in the visible Naver Whale window (CDP).

---

## R30 — North American 5-Slot Timetable & 3-Notification Cap
YouTube allows at most 3 subscriber push notifications per rolling 24 h. Slots 1, 3, 4 notify; slots 2 and 5 are feed-only.

| Slot | US ET | KST | `notify_subscribers` | Pillars (`PILLAR_SLOT_MAP`) |
|---|---|---|---|---|
| 1 | 07:30 | 21:30 | True | `brain_health` |
| 2 | 12:00 | 02:00 (+1d) | False | `bci_tech`, `brain_news` |
| 3 | 16:00 | 06:00 (+1d) | True | `brain_basics`, `brain_mysteries` |
| 4 | 19:30 | 09:30 (+1d) | True | `brain_history` |
| 5 | 22:30 | 12:30 (+1d) | False | `bci_ethics` |

**R30-B — Seed-audience protection (`StagingQueueManager.enforce_seed_protection_window`):** never publish 2+ Shorts at the same timestamp; keep ≥ 4.0 h between public releases; channels under 10,000 subscribers prefer 1–2 prime slots per day (slot 4, slot 2) and keep the rest staged as unlisted.

## R31 — Thumbnails (`PublishStage`)
Three visually distinct portrait variants (`thumbnail_var_A.png` cool blue, `B` crimson alert, `C` emerald/gold question), each > 80 KB, pairwise background diff ≥ 15.0. Optional `--burn-first-frame` prepends variant A as frame 0.

## R32 — 72 h Sequential A/B/C Z-Test (`ThumbnailABTester`)
A (0–24 h) → B (24–48 h) → C (48–72 h). `evaluate_significance` runs a two-proportion Z-test on CTR; |Z| > 1.96 (p < 0.05) locks the winner.

## R33 — Unlisted Staging Vault
Upload as `unlisted` ≥ 24 h before publication so transcoding and suitability checks finish (`upload_receipt.json`).

## R34 — Zero-Duplicate Queue
`StagingQueueManager` (`BCI_Shorts_Channel/staging_queue.json`) never assigns the same `project_id` to two slots.

## R35 — Pinned DOI Comment (`CommunityManager`)
Post and pin a top comment = `https://doi.org/<doi>` (R1) + one viewer self-test / debate question (`social_comment_trigger`) → `community_receipt.json`.

## R36 — Localization Lock (`StudioUploader.configure_studio_localization`)
| Tier | Setting |
|---|---|
| Channel residence | `CHANNEL_RESIDENCE_COUNTRY` = KR (Korean AdSense tax residency) |
| Video + metadata language | `VIDEO_LANGUAGE_CODE` / `TITLE_DESCRIPTION_LANGUAGE_CODE` = en-US |
| Category | `DEFAULT_VIDEO_CATEGORY_STUDIO` (Science and technology) |

## R4 — AI Disclosure
Every upload sets "Altered or synthetic content" = Yes (`AI_CONTENT_DECLARATION`).

## Daily Analytics
`StudioAnalyticsReporter` (`pipeline/studio/reporter.py`) → 9-section daily report; procedure in the [`/report_youtube` skill](file:///g:/My%20Drive/Kyubin_Yun_Workspace/07_Youtube/.agents/skills/report_youtube/SKILL.md).
