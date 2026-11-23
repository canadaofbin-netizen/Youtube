# 🗓️ ALL ABOUT BRAIN — Multi-Platform QA Schedule & Execution Plan (2026-11-14)

> **Generated**: `2026-11-14 10:09 UTC` | `2026-11-14 19:09 KST` | `2026-11-14 05:09 EST`
> **Overall Decision**: **PARTIAL_GO**

## 1. Daily Report Gate Verdict (`HOLD / GO` & Anti-Penalty Summary)

- **Source Report**: `2026-11-14` (`LIVE_CDP_DOM`, age `3.16h`)
- **Channel Pulse**: Subs `6` | Realtime 48h `1411` (`60m=32`) | Watch `126.9h` | 3s Hook `66.0%` (Gate `>=70%`) | APV `66.0%` (Gate `>=60%`) | US `55.6%` (Gate `>=45%`) | Shorts Feed `87.0%`
- **⚠️ DOM Scrape Anomaly Guard**: `views_24h` dropped sharply while `realtime_48h_views` & `watch_hours_24h` remain strong (`measured_video_count=0`). Treated as partial Studio DOM scrape lag, NOT algorithmic shadowban.

| Platform | Handle | Decision | Optimal Cadence | Next Safe Window (`ET` / `KST`) | Ready Queue |
| :--- | :--- | :---: | :--- | :--- | :---: |
| **YouTube** | `@AllAboutBrainOfficial` | **🔴 HOLD** | 1 Short / Day @ Slot 4 (19:30 ET) \| Longform 16:9: HOLD | `2026-11-16 19:30 EST` / `2026-11-17 09:30 KST` | `0` (`Runway 2d`) |
| **Instagram** | `@allaboutbrain.official` | **🟢 GO** | 1 Reel / Day (warmup 1/10) @ 11:45 ET or 18:15 ET | `2026-11-14 11:45 EST` / `2026-11-15 01:45 KST` | `5` Reels · `0` Cards |
| **TikTok** | `@allaboutbrain_official` | **🟢 GO** | 1 Video / Day (warmup 1/14) @ 15:30 ET or 20:45 ET | `2026-11-14 15:30 EST` / `2026-11-15 05:30 KST` | `5` (`>=61.5s`) |

## 2. Anti-Penalty & Compliance Audit

### YouTube (`HOLD`)
- ✅ **`YT-REPORT-FRESH`**: Daily Report `2026-11-14` (`3.2h` old)
- ⚠️ **`YT-DOM-MODE`**: Partial DOM scrape detected (`views_24h=8`, `realtime_48h=1411`, `watch=126.9h`, `measured_videos=0`)
- ✅ **`YT-NO-SIMULTANEOUS`**: `0` simultaneous releases
- ✅ **`YT-ZERO-QUARANTINE`**: `0` quarantined episodes
- ✅ **`YT-R75-PLAYLIST-BAN`**: `0` playlists verified (`R75`)
- ✅ **`YT-US-AUDIENCE`**: US `55.6%` (`>= 45%`), Tier-1 `62.2%`
- ✅ **`YT-SHORTS-FEED`**: Shorts Feed `87.0%` (`>= 70%`)
- ⚠️ **`YT-3S-HOOK`**: 3s Hook `66.0% < 70%` gate (require `<=12w` R68-H hook, keep 1/day cap)
- ✅ **`YT-APV`**: APV `66.0%` (gate `>= 60%`)
- **Hold / Conditions**: YouTube has `2d` scheduled buffer (`v8_ep07` `11-14 19:30 ET`, `v8_ep08` `11-15 19:30 ET`) and `0` QA-ready unpublished episodes remaining -> **HOLD** new YouTube uploads until next v8 episode (`<=88s`, R68-H `<=12w` hook) is produced and passes QA.

### Instagram (`GO`)
- ✅ **`IG-COOLDOWN`**: `52.3h` since last Reel (`>= 18h`)
- ✅ **`IG-INVENTORY`**: `5` Reels ready (`v8_ep04`, `v8_ep05`, `v8_ep06`, `v8_ep07`, `v8_ep08`)
- ✅ **`IG-ANTI-SPAM-SPEC`**: Clean `1080x1920` bundle (`0` watermark), `<=90`ch Line-1 hook, AI label ON, Graph API preferred over datacenter web CDP

### TikTok (`GO`)
- ✅ **`TT-COOLDOWN`**: `52.0h` since last post (`>= 20h`)
- ✅ **`TT-CREATOR-REWARDS-60S`**: `5` candidates `>= 61.5s` with clean bundle
- ✅ **`TT-SECURITY-AIGC`**: NO VPN, AIGC disclosure ON, 4-5 niche tags (`0` `#fyp`/`#viral`), halt cleanly on CAPTCHA

## 3. Today's Chronological Execution Plan

| # | Window (`KST` / `ET`) | Platform | Action | Verdict | Target | Reason |
| :---: | :--- | :---: | :--- | :---: | :--- | :--- |
| 1 | `2026-11-14 19:09 KST` / `2026-11-14 05:09 EST` | `youtube` | `WATCHDOG_SYNC` | **🟢 GO** | `reenact_01`, `v8_ep04..08` | Promote 4 elapsed Scheduled->Public receipts, backfill 3 eligible R35 pins (`>=12h/100v`), link 2 unlocked R35-B Related videos (`v8_ep07`, `v8_ep08`) |
| 2 | `2026-11-14 19:24 KST` / `2026-11-14 05:24 EST` | `youtube` | `HOLD_AND_PRODUCE` | **🔴 HOLD** | `next_v8_episode` | Scheduled runway is `2d` (`< 3d` target) and `0` QA-passed unpublished episodes remain; produce & pass QA for next v8 Short (`<=88s`, R68-H `<=12w` hook) |
| 3 | `2026-11-15 01:45 KST` / `2026-11-14 11:45 EST` | `instagram` | `UPLOAD_IG_REEL` | **🟢 GO** | `v8_ep04_patient_sm_fearless_amygdala` | Staggered US prime Reel (`1 Reel / Day` warmup `1/10`); YT state=`public` |
| 4 | `2026-11-15 05:30 KST` / `2026-11-14 15:30 EST` | `tiktok` | `UPLOAD_TIKTOK` | **🟢 GO** | `v8_ep04_patient_sm_fearless_amygdala` | Creator Rewards `>=61.5s` (`115.0s`), NO VPN, AIGC ON, staggered `3h45m` after IG & `4h` before YT |

## 4. Live YouTube Scheduled Buffer

- `2026-11-14 19:30 ET` (`2026-11-15 09:30 KST`) — `v8_ep07_harvard_reversible_choice_paradox` (`K_9IJVShp90`)
- `2026-11-15 19:30 ET` (`2026-11-16 09:30 KST`) — `v8_ep08_capgras_imposter_delusion` (`_p05nIlU9xs`)
