# 🗓️ ALL ABOUT BRAIN — Multi-Platform QA Schedule & Execution Plan (2026-11-14)

> **Generated**: `2026-11-14 10:25 UTC` | `2026-11-14 19:25 KST` | `2026-11-14 05:25 EST`
> **Overall Decision**: **🔴 HOLD**

## 1. Daily Report Gate Verdict (`HOLD / GO` & Anti-Penalty Summary)

- **Source Report**: `2026-11-14` (`LIVE_CDP_DOM`, age `3.43h`)
- **Channel Pulse**: Subs `6` | Realtime 48h `1411` (`60m=32`) | Watch `126.9h` | 3s Hook `66.0%` (Gate `>=70%`) | APV `66.0%` (Gate `>=60%`) | US `55.6%` (Gate `>=45%`) | Shorts Feed `87.0%`
- **⚠️ DOM Scrape Anomaly Guard**: `views_24h` dropped sharply while `realtime_48h_views` & `watch_hours_24h` remain strong (`measured_video_count=0`). Treated as partial Studio DOM scrape lag, NOT algorithmic shadowban.

| Platform | Handle | Decision | Optimal Cadence | Next Safe Window (`ET` / `KST`) | Ready Queue |
| :--- | :--- | :---: | :--- | :--- | :---: |
| **YouTube** | `@AllAboutBrainOfficial` | **🔴 HOLD** | 1 Short / Day @ Slot 4 (19:30 ET) | Longform 16:9: HOLD | `2026-11-16 19:30 EST` / `2026-11-17 09:30 KST` | `0` (`Runway 2d`) |
| **Instagram** | `@allaboutbrain.official` | **🔴 HOLD** | 1 Reel / Day (warmup 2/10) @ 11:45 ET or 18:15 ET | `2026-11-15 11:45 EST` / `2026-11-16 01:45 KST` | `4` Reels · `0` Cards |
| **TikTok** | `@allaboutbrain_official` | **🔴 HOLD** | 1 Video / Day (warmup 2/14) @ 15:30 ET or 20:45 ET | `2026-11-15 15:30 EST` / `2026-11-16 05:30 KST` | `4` (`>=61.5s`) |

## 2. Anti-Penalty & Compliance Audit

### YouTube (`HOLD`)
- ✅ **`YT-REPORT-FRESH`**: Daily Report 2026-11-14 (3.4h old)
- ⚠️ **`YT-DOM-MODE`**: Partial DOM scrape detected (views_24h=8, realtime_48h=1411, watch=126.9h, measured_videos=0)
- ✅ **`YT-NO-SIMULTANEOUS`**: 0 simultaneous releases
- ✅ **`YT-ZERO-QUARANTINE`**: 0 quarantined episodes
- ✅ **`YT-R75-PLAYLIST-BAN`**: 0 playlists verified (R75)
- ✅ **`YT-US-AUDIENCE`**: US 55.6% (>= 45%), Tier-1 62.2%
- ✅ **`YT-SHORTS-FEED`**: Shorts Feed 87.0% (>= 70%)
- ⚠️ **`YT-3S-HOOK`**: 3s Hook 66.0% < 70% gate (require <=12w R68-H hook, keep 1/day cap)
- ✅ **`YT-APV`**: APV 66.0% (gate >= 60%)
- **Conditions / Warnings**: YT-DOM-MODE: Partial DOM scrape detected (views_24h=8, realtime_48h=1411, watch=126.9h, measured_videos=0); YT-3S-HOOK: 3s Hook 66.0% < 70% gate (require <=12w R68-H hook, keep 1/day cap); 0 QA-ready unpublished candidates and buffer is only 2d (< 3d target) -> produce new v8 episode first

### Instagram (`HOLD`)
- 🛑 **`IG-RATE-LIMIT`**: 1 upload(s) in last 24h (cap 1)
- ✅ **`IG-INVENTORY`**: 4 Reel(s) + 0 Card Carousel(s) ready
- ✅ **`IG-ANTI-SPAM-SPEC`**: Clean 1080x1920 bundle (0 watermark), <=90ch Line-1 hook, AI label ON, Graph API preferred over datacenter web CDP
- **Hold / Block Reasons**: IG 24h cap reached (1/1)

### TikTok (`HOLD`)
- 🛑 **`TT-RATE-LIMIT`**: 1 upload(s) in last 24h (cap 1)
- ✅ **`TT-CREATOR-REWARDS-60S`**: 4 candidate(s) >= 61.5s with clean bundle
- ✅ **`TT-SECURITY-AIGC`**: NO VPN, AIGC disclosure ON, 4-5 niche tags (0 #fyp/#viral), halt cleanly on CAPTCHA
- **Hold / Block Reasons**: TikTok 24h cap reached (1/1)

## 3. Today's Chronological Execution Plan

| # | Window (`KST` / `ET`) | Platform | Action | Verdict | Target | Reason |
| :---: | :--- | :---: | :--- | :---: | :--- | :--- |
| 1 | `2026-11-14 19:40 KST` / `2026-11-14 05:40 EST` | `youtube` | `HOLD_AND_PRODUCE` | **🔴 HOLD** | `next_v8_episode` | YouTube scheduled runway is 2d (< 3d target) and 0 QA-passed unpublished episodes remain; produce & pass QA for next v8 Short (<=88s, R68-H <=12w hook) |

### Commands

1. **youtube — `HOLD_AND_PRODUCE` (`next_v8_episode`)**:
```bash
/home/canadaofbin/hermes-venv/bin/python -X utf8 main.py diorama-episode --help
```

## 4. Live YouTube Scheduled Buffer

- `2026-11-14 19:30 ET` — `v8_ep07_harvard_reversible_choice_paradox` (`K_9IJVShp90`)
- `2026-11-15 19:30 ET` — `v8_ep08_capgras_imposter_delusion` (`_p05nIlU9xs`)
