---
name: youtube-studio-manager
description: Autonomous YouTube Studio operations for ALL ABOUT BRAIN via the visible Naver Whale window (CDP) - KR residence with en-US metadata, North American 5-slot timetable with the 3-notification cap, unlisted staging buffer, zero-duplicate queue, 72h sequential thumbnail Z-test, pinned DOI comment, AI disclosure, and the daily analytics report.
---

# YouTube Studio Manager

Master: [AGENTS.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/AGENTS.md) · Rule: [youtube_studio_operations.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/youtube_studio_operations.md) (R4, R30–R36, R35-B, R36-B) · Metadata: [channel_operations_rules.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/channel_operations_rules.md) (R8–R10) · Code: `pipeline/studio/`

---

## Procedure
| Step | Action | Code | Rule |
|---|---|---|---|
| 1 | Verify channel residence + upload defaults (once per session). | `StudioUploader.configure_studio_localization` | R36 |
| 2 | Upload `05_assembly/final_shorts_1080x1920.mp4` as unlisted with `06_publish/metadata.json`; set AI disclosure. | `StudioUploader` | R33, R4, R8–R10 |
| 3 | Queue into the pillar slot; enforce seed-protection spacing (`min_interval_hours=4.0`, `daily_prime_only=True` for `<10K` subs -> Slots 2 `12:00 ET` & 4 `20:00 ET` only) and v5 gate. | `StagingQueueManager` | R30, R30-B, R34 |
| 4 | Link Short-to-Short `Related video` circular seed-rescue ring + assign 7-Pillar playlist; verify `06_publish/studio_publish_receipt.json`. | `ShortLinkGraph` · `StudioShortLinker` | R35-B, R36-B |
| 5 | Pin the DOI + debate-question comment (`DirectCDPClient`). | `CommunityManager` | R35 |
| 6 | Rotate thumbnails A → B → C and evaluate the Z-test (`DirectCDPClient`). | `ThumbnailABTester` · `PublishStage` | R31, R32 |
| 7 | Daily report. | [`/report_youtube`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/skills/report_youtube/SKILL.md) | — |

Use `--dry-run` first on any new command sequence.

## Commands
```bash
python -X utf8 main.py studio-settings
python -X utf8 main.py studio-upload --project <project_id> --visibility unlisted --burn-first-frame --assign-playlist
python -X utf8 main.py studio-queue --action plan --days 7
python -X utf8 main.py studio-link --action plan --dry-run
python -X utf8 main.py studio-link --action apply --assign-playlists
python -X utf8 main.py studio-pin --project <project_id>
python -X utf8 main.py studio-ab-test --project <project_id> --swap-next
python -X utf8 main.py studio-ab-test --project <project_id> --evaluate
python -X utf8 main.py studio-report
```

## CDP & DOM Pitfalls
- **Short-to-Short `Related video` picker (`#linked-video-editor-link` -> `ytcp-video-pick-dialog`)**: On `/video/<id>/edit`, always call `Page.bringToFront` first (otherwise Polymer's `IronOverlayBehavior` pauses `requestAnimationFrame` on background tabs and `tp-yt-paper-dialog` stays `display: none`), click `#linked-video-editor-link ytcp-dropdown-trigger`, filter via `ytcp-video-pick-dialog input#search-yours`, and match `ytcp-entity-card` by exact 11-char `(card.video?.videoId || card.data?.videoId)` (or `/vi/<id>/` thumbnail URL) before falling back to normalized title text (avoiding duplicate legacy uploads or live title emoji edits). Click `#content` once (never double-click both outer card and `#content`), verify `#linked-video-editor-link` read-back text before clicking `ytcp-button#save`, and never point a `Public` Short at an `Unlisted` or `Scheduled` target (`R35-B`).
- **7-Pillar Playlist dialog (`ytcp-playlist-dialog` `Save` vs `Done`)**: `ytcp-playlist-dialog` and `ytcp-playlist-creation-dialog` are `0px`-tall Shady-DOM shells when closed — always check `tp-yt-paper-dialog#dialog` with `width > 0 && height > 0`. When a playlist checkbox is toggled or newly created, YouTube Studio enables `ytcp-button.save-button` (`Save`); when already checked, `save-button` stays disabled and `ytcp-button.done-button` (`Done`) closes the dialog. Prioritize visible + enabled `save-button` before `done-button`.
- **Channel anchor check on `/video/<id>/edit`**: On individual video edit routes, `#entity-name` holds the **video title**, not the channel name. Always check `a[href*='UC4FeioYYv9X04Di07_MfZ7g']` first before inspecting `#entity-name` so `_ensure_all_about_brain_channel` never opens `#avatar-btn` unnecessarily.
- **Stage-gated scheduling (`daily_prime_only=True` under 10K subscribers)**: For channels under 10,000 subscribers, always schedule into prime slots only — **Slot 2 (`12:00 ET` / `16:00 UTC`)** and **Slot 4 (`20:00 ET` / `00:00 UTC +1d`)** — with `min_interval_hours=4.0`, keeping any extra finished videos in the `Unlisted` buffer or rolling them to the next day's Slots 2 & 4 so consecutive uploads never collide inside YouTube's 1–6h initial seed-audience test window.
- **Rescheduling an already-uploaded video on `/video/<id>/edit`**: Navigate to `https://studio.youtube.com/video/<video_id>/edit`, click the visibility trigger (`ytcp-video-metadata-visibility #select-button, ytcp-video-metadata-visibility ytcp-button, #visibility-button`), call `await cdp.set_schedule_datetime_utc(date_utc, time_utc)`, click the popup confirmation (`ytcp-video-visibility-select #save-button button, #save-button button, ytcp-button#done-button button`), and then click the page-level Save button (`ytcp-video-metadata-editor #save button, ytcp-button#save button, #save button`) — without the outer Save click, the new schedule is discarded.
- **Sync local queue and receipts after CDP schedule changes**: Whenever schedules are changed via CDP, update each project's `06_publish/upload_receipt.json` (`visibility: 'scheduled'`) and `staging_queue.json` via `StagingQueueManager.load_queue()` / `save_queue()`, then verify with `qm.enforce_seed_protection_window(min_interval_hours=4.0, daily_prime_only=True)` (`passed: True`, `violations: []`).
- **Schedule accordion (`#second-container`)**: On YouTube Studio's Visibility step, the Schedule option is an expandable container (`#second-container` / `#second-container-expand-button`), not a `tp-yt-paper-radio-button`. Expand `#second-container`, set the UTC date/time via `cdp.set_schedule_datetime_utc(date_label, time_24h)` (e.g. `'20 Oct 2026'`, `'23:30'`), verify `#done-button` text switches from `Save` to `Schedule`, then click `ytcp-button#done-button button, #done-button`.
- **Prechecks warning modal (`Publish anyway`)**: If copyright/suitability prechecks are still running when clicking `Schedule`, YouTube Studio intercepts the save with a confirmation modal; always check for and click a visible `Publish anyway` (`무시하고 게시`) button after `#done-button`, then verify the row status in `/videos/short` changes from `Draft` to `Scheduled`.
- **Deleting residual Draft rows**: In `/videos/short`, `Draft` rows expose inline action buttons (`button[aria-label="Delete video"]`, `button[aria-label="Cancel upload"]`, `button[aria-label="Edit draft"]`) directly on the row rather than behind the 3-dot `#options-button` menu. Click `button[aria-label="Delete video"]` directly, check `#confirm-checkbox`, and click `#confirm-button`.
- **Recovering from CDP WebSocket timeouts after uploads**: Use `WhaleSessionController.recycle_studio_tab()` to open a fresh `studio.youtube.com` tab before closing the stale `studio.youtube.com` tab every 3 edits/uploads (`R36-B`), never touching non-YouTube tabs.
- **Fast public metadata & view-count fallback (`ytInitialPlayerResponse`)**: When YouTube Studio's `/videos/short` or analytics Reach tab renders `Oops, something went wrong. | Retry` over CDP, fetch `https://www.youtube.com/watch?v=<video_id>` via standard HTTP and parse `var ytInitialPlayerResponse = ({...});` to read `videoDetails` (`viewCount`, `lengthSeconds`, `title`) and `microformat.playerMicroformatRenderer` (`publishDate`, `uploadDate`, `isUnlisted`) without waiting on the Studio SPA.
- **24h seed-pool indexing window for newly public Shorts**: Do not edit a newly published Short's title, description, `Related video`, or visibility within the first 24 hours of going `Public` (especially Extended Shorts `>60s` or same-day scheduled uploads) because metadata edits reset YouTube's initial seed-pool indexing pipeline before the first 6–24h exploration wave fires.
- **Shorts A/B/C thumbnail layout & frame extraction (`PublishStage`)**: Place all thumbnail text badges in the top safe zone (`y=185..445`) rather than the lower third (`y>=1350`), which collides with YouTube's mobile Shorts Shelf title/views overlay. Compress hooks to 2–4 uppercase keywords at `96–108px`, draw a central anatomical HUD reticle (`NEURAL LOCUS` / `3D CUTAWAY SCAN` / `ANOMALY DETECTED` around `y=960..980`) to leave the middle 3D anatomy unobstructed, and fall back to `03_visuals/_staged_clip_*.mp4` when `03_visuals/flow_native_clips/*.mp4` is empty so Variants A/B/C extract distinct video frames (`MAE >= 18.0`).
