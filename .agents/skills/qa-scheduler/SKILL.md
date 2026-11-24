---
name: qa-scheduler
description: Daily 08:00 cross-platform QA Scheduler chief (v2) for YouTube, Instagram, and TikTok — reads the Daily Report, enforces anti-penalty/anti-shadowban & 6 permanent anti-trap guardrails, derives the 1-Episode -> 5-Asset staggered execution plan, and decides HOLD / THROTTLE / GO.
---

# qa-scheduler v2 (AI-Only Spec)

SSOT: [AGENTS.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/AGENTS.md) | [youtube_studio_operations.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/youtube_studio_operations.md) | Code: [scheduler.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/studio/scheduler.py)
Interpreter: `/home/canadaofbin/hermes-venv/bin/python -X utf8`

## 1. Daily 08:00 Scheduling Workflow
1. Run `/home/canadaofbin/hermes-venv/bin/python -X utf8 main.py qa-scheduler --date YYYY-MM-DD` (or zero-token headless `scripts/run_daily_ops_headless.sh schedule`).
2. Inspect generated outputs in `BCI_Shorts_Channel/reports/`:
   - `daily/YYYY-MM-DD_qa_schedule_plan.md` & `.json`
   - `schedule/YYYY-MM-DD_qa_schedule_plan.md` & `.json`
   - `LATEST_QA_SCHEDULE_PLAN.md` & `.json`
3. When run interactively, write `qa_schedule_plan_YYYY-MM-DD.md` (`Overwrite=True`) into `<appDataDir>/brain/<conversation-id>/` so `.agents/hooks.json` mirrors it to `artifacts_archive/` and updates `INDEX.md`.

## 2. 1-Episode -> 5 Automated Assets Stagger
1. **YouTube Community Quiz Post (`D-Day 16:00 ET`, Short `-3.5h`)**: Checks `06_publish/community_quiz_receipt.json` (`SCHEDULED/DONE` vs `ACTION_REQUIRED: main.py studio-quiz --project <id>`).
2. **YouTube Short (`D-Day 19:30 ET` Slot 4 / `12:00 ET` Slot 2)**: `1 Short / Day` under `<10K` subs (`16:9` Longform on **HOLD**); `>= 3.0h` warmup, `0` simultaneous releases, `0` playlists (`R75`), `3h` pre / `24h` post release freeze, `>= 12h` or `>= 100` organic views before `R35` pin.
3. **TikTok `>61.5s` Original-Audio Video (`D-Day 20:45 ET`, `>=20h` cooldown)**: Creator Rewards `>= 61.5s`, **Original Audio only**, `AIGC ON`, `cover_9x16.png`, `4–5` niche tags (`0` `#fyp`/`#viral`), **NO VPN**, halt on CAPTCHA (`main.py tiktok-publish --project <id>`).
4. **Instagram Clean Reel (`D+1 13:30 ET`, `>= +18h` post-YouTube & cooldown)**: Resolves `video_clean.mp4` or fallback `05_assembly/final_shorts_1080x1920.mp4` (`copy_video=False` default), `<= 90` char Line-1 hook, AI label ON (`<1,000` followers `Standard Reel`; `>= 1,000` `Trial Reels SS_PERFORMANCE`; `main.py ig-publish --project <id> --kind reel`).
5. **Instagram `4:5 (1080x1350)` 6-Slide Carousel (non-Reel day `>= +24h` post-Reel, `2–3/wk` cap)**: `IG_CAROUSEL_MIN_GAP_FROM_REEL_HOURS = 18.0`, tracked via `instagram_carousel_receipt.json`.
6. **Daily Zero-Bounce Studio Inbox Check**: `main.py studio-inbox --scan-only`.

## 3. Permanent Anti-Trap & Release Guardrails (`guardrails`)
Violation emits immediate `WARN` or `HOLD` (`BLOCK`):
- `youtube_srt_cc_upload_banned: True` — Never upload external `.srt`/`.vtt` CC files over burned-in `82pt` ASS Shorts.
- `youtube_auto_dubbing_burned_ass_off: True` — Keep YouTube Auto-Dubbing OFF while burned-in English ASS is active.
- `tiktok_commercial_sound_over_60s_banned: True` — Never use TikTok Commercial Music Library on `>60s` videos.
- `instagram_carousel_aspect_ratio_locked: "4:5 (1080x1350)"` — Reject `3:4` (`1080x1440`); enforce `1080x1350` with center `3:4` safe zone.
- `instagram_notes_deprecated_excluded: True` & `on_hold_excluded_features: ["instagram_manychat_comment_dm", "instagram_story_highlights"]` — Never schedule or execute.
- `r75_studio_hygiene_gates` — Zero `BANNED_OFF_TOPIC_TECH_TAGS` on non-`bci_tech` projects, Scheduled Shorts linked outbound to `>=250`-view Public Anchors (`>3.0h` pre-release), `Education -> Academic system = United States`, live `studio_watchdog_latest.json` synced.
- `r85_and_fresh_room_verify_lock` — Hold unpublished pre-R85 builds (`v8_ep09_maguire_london_taxi_hippocampus_r82`, `*_r82`) and require both R85/R88 Tier-1 + Gate 2 QA AND a valid `Fresh-Room` local verification receipt (`05_assembly/ceo_verify_receipt.json` written via `record_verify_pass_receipt()` / `main.py ep run <id> --until ready`) before `GO`.
