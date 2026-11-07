---
name: youtube-studio
description: Gear 5 YouTube Studio CDP operations via Naver Whale - Unlisted staging, <10K Prime-Slot scheduling, R35-B Related video & playlist ring, R35 pinned DOI/debate comments, and Go-Live watchdog.
---

# youtube-studio (AI-Only Spec)

SSOT: [AGENTS.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/AGENTS.md) | [youtube_studio_operations.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/youtube_studio_operations.md) (R4, R30-R36, R35-B, R36-B) | Code: `pipeline/studio/`
Channel: `@AllAboutBrainOfficial` (`UC4FeioYYv9X04Di07_MfZ7g`) | Interpreter: `/home/canadaofbin/hermes-venv/bin/python -X utf8`

## 1. CLI Workflow (Run `--dry-run` before mutating new sequences)
1. `main.py studio-settings` (KR residence + `en-US` metadata lock, R36)
2. `main.py studio-upload --project <id> --visibility unlisted --assign-playlist` (R4 AI disclosure, R8-R10 metadata, R33 Unlisted staging; requires passed `Autopsy` + `DQ1-DQ12` + `R64` + `<= SHORTS_HARD_CEILING_SEC`)
3. `main.py studio-queue --action plan --days 7` (`<10K` subs `daily_prime_only=True`: Slot 2 `12:00 ET`/`16:00 UTC` & Slot 4 `20:00 ET`/`00:00 UTC +1d`, `min_interval_hours=4.0`, R30/R30-B/R34)
4. `main.py studio-link --action apply --assign-playlists` (R35-B `Related video` circular Public seed-rescue ring + 7-Pillar playlist; verify `06_publish/studio_publish_receipt.json`)
5. `main.py studio-pin --project <id>` (R35 1st-person `offcenter_creator_bet` + verified DOI comment)
6. `main.py studio-watchdog [--apply]` (promote elapsed Scheduled Shorts, backfill missing R35 pins & R35-B links)
7. Longform-only thumbnail Z-test (R32; `not_applicable_shorts` on Shorts, which use R65 `cover_frame_sec`): `main.py studio-ab-test --project <id> --evaluate`

## 2. Critical CDP / Polymer Guardrails
- **Tab Isolation**: Never hijack or close non-Studio tabs (`labs.google/fx/tools/flow` etc.). Recycle only own stale `studio.youtube.com` tab every 3 edits (`WhaleSessionController.recycle_studio_tab()`, R36-B).
- **Raw JS Eval**: Always use `rf"""(() => {{ ... }})()"""` in `client.eval(...)` to prevent newline syntax errors.
- **Channel Check**: On `/video/<id>/edit`, verify `a[href*='UC4FeioYYv9X04Di07_MfZ7g']` before `#entity-name` (which holds video title on edit routes).
- **Related Video Picker**: Call `Page.bringToFront` first; read back sidepanel text to skip if `already_linked`; match `ytcp-entity-card` by 11-char `videoId` or `/vi/<id>/` thumb before title prefix; never link a `Public` Short to an `Unlisted`/`Scheduled` target; click outer `ytcp-button#save`.
- **Playlist Dialog**: Check `tp-yt-paper-dialog#dialog` `width > 0 && height > 0`; click enabled `ytcp-button.save-button` before `done-button`.
- **Schedule Save**: Expand `#second-container`, call `set_schedule_datetime_utc`, click `#done-button` (`Schedule`), handle `Publish anyway` precheck modal if shown, click outer `#save` on edit routes, and sync `06_publish/upload_receipt.json` + `staging_queue.json`.
- **24h Seed Window**: Never mutate title/description/`Related video`/visibility within 24h after a Short goes `Public`.
