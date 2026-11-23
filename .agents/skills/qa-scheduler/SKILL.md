---
name: qa-scheduler
description: Daily 08:00 cross-platform QA Scheduler chief (v2) for YouTube, Instagram, and TikTok — reads the Daily Report, enforces anti-penalty/anti-shadowban & 6 permanent anti-trap guardrails, derives the 1-Episode -> 5-Asset staggered execution plan, and decides HOLD / THROTTLE / GO.
---

# qa-scheduler v2 (AI-Only Spec)

SSOT: [AGENTS.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/AGENTS.md) | [youtube_studio_operations.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/youtube_studio_operations.md) | Code: [qa_scheduler.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/studio/qa_scheduler.py)
Interpreter: `/home/canadaofbin/hermes-venv/bin/python -X utf8`

## 1. Daily 08:00 Scheduling Workflow
1. Run `/home/canadaofbin/hermes-venv/bin/python -X utf8 main.py qa-scheduler --date YYYY-MM-DD` in `/home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube`.
2. Inspect the generated outputs:
   - `BCI_Shorts_Channel/reports/daily/YYYY-MM-DD_qa_schedule_plan.md` & `.json`
   - `BCI_Shorts_Channel/reports/schedule/YYYY-MM-DD_qa_schedule_plan.md` & `.json`
   - `BCI_Shorts_Channel/reports/LATEST_QA_SCHEDULE_PLAN.md` & `.json`
3. Copy/write `qa_schedule_plan_YYYY-MM-DD.md` (`Overwrite=True`) into `<appDataDir>/brain/<conversation-id>/` so `.agents/hooks.json` mirrors it to `artifacts_archive/` and updates `INDEX.md`.

## 2. 1-Episode -> 5 Automated Assets Stagger (`Workstream 4C v2`)
1. **YouTube Community Quiz Post (`D-Day 16:00 ET`, Short `-3.5h`)**:
   - Anchored to today's/next scheduled Short (`scheduled_at_utc - 3.5h`).
   - Checks `06_publish/community_quiz_receipt.json` (`SCHEDULED/DONE` vs `ACTION_REQUIRED: main.py studio-quiz --project <id>`).
2. **YouTube Short (`D-Day 19:30 ET` / `12:00 ET`)**:
   - Strictly `1 Short / Day` at **Slot 4 (`19:30 ET`)** under `<10K` subs; `16:9` Longform on **HOLD**.
   - `>= 3.0h` warmup, zero simultaneous releases, `0` playlists (`R75`), `0` quarantine, `3h` pre / `24h` post release freeze, `>= 12h` or `>= 100` organic views before `R35` pin.
3. **TikTok `>61.5s` Original-Audio Video (`D-Day 20:45 ET`, `>=20h` warmup cooldown)**:
   - Creator Rewards `>= 61.5s` (`> 60s`), **Original Audio only**, `AIGC ON`, custom cover (`cover_9x16.png`), 3-layer search SEO (`4–5` niche tags, `0` `#fyp`/`#viral`), **NO VPN**, halt immediately on CAPTCHA.
4. **Instagram Clean Reel (`D+1 13:30 ET`, `>= +18h` post-YouTube & `>=18h` cooldown)**:
   - Clean `video_clean.mp4` (`0` watermark), `<= 90` char Line-1 hook, AI label ON, Graph API preferred.
   - `<1,000` followers: `Standard Reel (Warmup)`; `>= 1,000` followers: `Trial Reels (SS_PERFORMANCE)` flag enabled.
5. **Instagram `4:5 (1080x1350)` 6-Slide Carousel (non-Reel day `>= +24h` post-Reel, `2–3/wk` cap)**:
   - Anti-cannibalization lock: `IG_CAROUSEL_MIN_GAP_FROM_REEL_HOURS = 18.0` (never same-day overlap with an IG Reel), tracked via `instagram_carousel_receipt.json` / `instagram_card_receipt.json`.
6. **Daily Zero-Bounce Studio Inbox Check**:
   - Daily checklist step: `main.py studio-inbox --scan-only` (`studio.youtube.com/.../comments/inbox` zero-playback heart & reply routine).

## 3. Permanent Anti-Trap Guardrails (`guardrails`)
Violation emits immediate `WARN` or `HOLD` (`BLOCK`):
- `youtube_srt_cc_upload_banned: True` — Never upload external `.srt`/`.vtt` CC files over burned-in `102pt` ASS Shorts (prevents double captions).
- `youtube_auto_dubbing_burned_ass_off: True` — Keep YouTube Auto-Dubbing OFF while burned-in English ASS is active (prevents audio/text language mismatch).
- `tiktok_commercial_sound_over_60s_banned: True` — Never use TikTok Commercial Music Library on `>60s` videos (prevents full-video mute & CRP disqualification).
- `instagram_carousel_aspect_ratio_locked: "4:5 (1080x1350)"` — Reject `3:4` (`1080x1440`) Graph API rejections; enforce `1080x1350` with center `3:4` safe zone.
- `instagram_notes_deprecated_excluded: True` — Permanently excluded (deprecated Apr 2025; mutual-follow-only zero non-follower reach).
- `on_hold_excluded_features: ["instagram_manychat_comment_dm", "instagram_story_highlights"]` — User-deferred features MUST never be scheduled or executed.
- `r75_studio_hygiene_gates` (`YT-R75-TAG-HYGIENE` BLOCK, `YT-R35B-SCHEDULED-LINK` WARN) — Zero `BANNED_OFF_TOPIC_TECH_TAGS` on non-`bci_tech` projects, every unlocked Scheduled Short linked outbound to a `>=250`-view Public Anchor (`>3.0h` pre-release), `Education -> Academic system = United States`, and `staging_queue.json` synced (`0` elapsed `"scheduled"` rows).
- `r85_and_r83_5_7_evidence_lock` — Hold all pre-R85 R82/R84 builds (`v8_ep09_maguire_london_taxi_hippocampus_r82`, `v8_ep10_*`–`v8_ep12_*`, `*_r82`) until R85 rebuild QA + CEO verification both pass. Per R83-5, CEO cannot write workspace files: `@QA_Scheduler` writes `05_assembly/ceo_verify_receipt.json` **only** via `record_ceo_verify_pass_receipt()` after receiving `@YouTube_CEO`'s `send_message` carrying `[CEO_VERIFY_PASS] <project_id>`, preserving `message_timestamp` and verbatim `message_text` (creating a receipt without that message is forbidden). Include `evidence_bundle` (`metrics_path`, KPI metrics, QA & verify receipt paths) in every HOLD/GO report, and confine code edits strictly to `pipeline/studio/qa_scheduler.py`, its unit tests, and this `SKILL.md` (delegate other `pipeline/*.py` edits to `@Operator`).
