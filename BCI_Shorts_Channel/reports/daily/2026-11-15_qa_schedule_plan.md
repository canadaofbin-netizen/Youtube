# 🗓️ ALL ABOUT BRAIN — Multi-Platform QA Schedule & 5-Asset Execution Plan (2026-11-15)

> **Generated**: `2026-11-15 21:13 UTC` | `2026-11-16 06:13 KST` | `2026-11-15 16:13 EST`
> **Overall Decision**: **PARTIAL_GO** | **Guardrails**: `PASS`

## 1. Daily Report Gate Verdict (`HOLD / GO` & Anti-Penalty Summary)

- **Source Report**: `2026-11-15` (`LIVE_CDP_DOM`, age `14.19h`)
- **Channel Pulse**: Subs `6` | IG Followers `0` | Realtime 48h `1411` (`60m=32`) | Watch `132.6h` | 3s Hook `76.0%` (Gate `>=70%`) | APV `76.0%` (Gate `>=60%`) | US `55.6%` (Gate `>=45%`) | Shorts Feed `87.0%`
- **⚠️ DOM Scrape Anomaly Guard**: `views_24h` dropped sharply while `realtime_48h_views` & `watch_hours_24h` remain strong (`measured_video_count=0`). Treated as partial Studio DOM scrape lag, NOT algorithmic shadowban.

| Platform | Handle | Decision | Optimal Cadence | Next Safe Window (`ET` / `KST`) | Ready Queue |
| :--- | :--- | :---: | :--- | :--- | :---: |
| **YouTube** | `@AllAboutBrainOfficial` | **🔴 HOLD** | 1 Short / Day @ Slot 4 (19:30 ET) | Longform 16:9: HOLD | `2026-11-17 19:30 EST` / `2026-11-18 09:30 KST` | `0` (`Runway 2d`) |
| **Instagram** | `@allaboutbrain.official` | **🟢 GO** | 1 Reel / Day (warmup 2/10) @ 13:30 ET or 18:15 ET; Carousels 2-3/wk (>=18h Reel gap) | `2026-11-15 18:15 EST` / `2026-11-16 08:15 KST` | `6` Reels · `2` Carousels |
| **TikTok** | `@allaboutbrain_official` | **🟢 GO** | 1 Video / Day (warmup 2/14) @ 15:30 ET or 20:45 ET | `2026-11-15 20:45 EST` / `2026-11-16 10:45 KST` | `6` (`>=61.5s`) |

## 2. Anti-Penalty & Compliance Audit

### YouTube (`HOLD`)
- ✅ **`YT-REPORT-FRESH`**: Daily Report 2026-11-15 (14.2h old)
- ⚠️ **`YT-DOM-MODE`**: Partial DOM scrape detected (views_24h=8, realtime_48h=1411, watch=132.6h, measured_videos=0)
- ✅ **`YT-NO-SIMULTANEOUS`**: 0 simultaneous releases
- ✅ **`YT-ZERO-QUARANTINE`**: 0 quarantined episodes
- ✅ **`YT-R75-PLAYLIST-BAN`**: 0 playlists verified (R75)
- ✅ **`YT-R75-TAG-HYGIENE`**: 0 banned off-topic tech tags across active episodes
- ✅ **`YT-US-AUDIENCE`**: US 55.6% (>= 45%), Tier-1 62.2%
- ✅ **`YT-SHORTS-FEED`**: Shorts Feed 87.0% (>= 70%)
- ✅ **`YT-3S-HOOK`**: 3s Hook 76.0% (>= 70%)
- ✅ **`YT-APV`**: APV 76.0% (gate >= 60%)
- ✅ **`YT-R35B-SCHEDULED-LINK`**: All unlocked Scheduled Shorts linked to clean Public Anchor
- **Conditions / Warnings**: YT-DOM-MODE: Partial DOM scrape detected (views_24h=8, realtime_48h=1411, watch=132.6h, measured_videos=0); 0 QA-ready unpublished candidates and buffer is only 2d (< 3d target) -> produce new v8 episode first

### Instagram (`GO`)
- ✅ **`IG-COOLDOWN`**: 34.8h since last Reel (>= 18h)
- ✅ **`IG-INVENTORY`**: 6 Reel(s) + 2 4:5 Carousel(s) ready
- ✅ **`IG-CAROUSEL-CAP`**: 0/3 Carousels in 7d; locked 4:5 (1080x1350), >=18h Reel gap
- ✅ **`IG-ANTI-SPAM-SPEC`**: Clean 1080x1920 bundle (0 watermark), <=90ch Line-1 hook, AI label ON, Standard Reel (Warmup 0/1000 followers)

### TikTok (`GO`)
- ✅ **`TT-COOLDOWN`**: 34.8h since last post (>= 20h)
- ✅ **`TT-CREATOR-REWARDS-60S`**: 6 candidate(s) >= 61.5s with clean bundle
- ✅ **`TT-SECURITY-AIGC`**: NO VPN, AIGC disclosure ON, 4-5 niche tags (0 #fyp/#viral), halt cleanly on CAPTCHA

## 3. 1-Episode -> 5 Automated Assets Ecosystem Stagger (`Workstream 4C v2`)

- **Anchor Episode**: `v8_ep08_capgras_imposter_delusion_r77` (`Atd0Pi9HPg4` | `scheduled_today` @ `2026-11-15 19:30 EST` / `2026-11-16 09:30 KST`)

| Asset | Slot (`ET` / `KST`) | Status | Target / Spec |
| :--- | :--- | :---: | :--- |
| **YouTube Community Quiz Post** | `2026-11-15 16:00 EST` / `2026-11-16 06:00 KST` | **✅ SCHEDULED/DONE** | community_quiz_receipt.json verified (D-Day -3.5h pre-heat) |
| **YouTube Short** | `2026-11-15 19:30 EST` / `2026-11-16 09:30 KST` | **🗓️ SCHEDULED** | Scheduled Atd0Pi9HPg4 @ Slot 4 (2026-11-15 19:30 EST), R75 0 playlists |
| **TikTok >61.5s Original-Audio Video** | `2026-11-15 20:45 EST` / `2026-11-16 10:45 KST` | **🟢 GO** | Anchor v8_ep08_capgras_imposter_delusion_r77 (76.9s >= 61.5s, Original Audio, AIGC ON); Queue ready: v8_ep05_ucl_tickle_delay_robot |
| **Instagram Clean Reel** | `2026-11-16 13:30 EST` / `2026-11-17 03:30 KST` | **🟢 GO** | Standard Reel (Warmup 0/1000 followers); D+1 stagger >= +18h post-YT (2026-11-16 13:30 EST); Queue ready now/next slot: v8_ep05_ucl_tickle_delay_robot |
| **Instagram 4:5 (1080x1350) 6-Slide Carousel** | `2026-11-17 13:30 EST` / `2026-11-18 03:30 KST` | **🟢 GO** | Locked 4:5 (1080x1350) (6 slides, center 3:4 safe zone), non-Reel day >= +24h post-Reel (0/3 in 7d) |
| **Daily Zero-Bounce Studio Inbox Check** | `2026-11-15 16:13 EST` / `2026-11-16 06:13 KST` | **⚡ ACTION REQUIRED** | Studio comments/inbox zero-playback heart & reply routine (0 self-bounce) |

## 4. Anti-Trap Permanent Guardrails (`guardrails`)

- `youtube_srt_cc_upload_banned`: `True`
- `youtube_auto_dubbing_burned_ass_off`: `True`
- `tiktok_commercial_sound_over_60s_banned`: `True`
- `instagram_carousel_aspect_ratio_locked`: `4:5 (1080x1350)`
- `instagram_notes_deprecated_excluded`: `True`
- `on_hold_excluded_features`: `instagram_manychat_comment_dm, instagram_story_highlights`

- ✅ **`youtube_srt_cc_upload_banned`** (`youtube`): 0 external SRT/VTT CC uploads (102pt burned-in ASS protected from double captions)
- ✅ **`youtube_auto_dubbing_burned_ass_off`** (`youtube`): Auto-Dubbing OFF lock verified for burned-in English ASS Shorts
- ✅ **`tiktok_commercial_sound_over_60s_banned`** (`tiktok`): Original Audio only for >60s Creator Rewards videos (0 commercial music risk)
- ✅ **`instagram_carousel_aspect_ratio_locked`** (`instagram`): Locked to 4:5 (1080x1350) with center 3:4 safe zone
- ✅ **`instagram_notes_deprecated_excluded`** (`instagram`): Instagram Notes excluded (deprecated Apr 2025, 0 non-follower reach)
- ✅ **`on_hold_excluded_features`** (`instagram`): On-hold features excluded: instagram_manychat_comment_dm, instagram_story_highlights

## 5. Today's Chronological Execution Plan

| # | Window (`KST` / `ET`) | Platform | Action | Verdict | Target | Reason |
| :---: | :--- | :---: | :--- | :---: | :--- | :--- |
| 1 | `2026-11-16 06:13 KST` / `2026-11-15 16:13 EST` | `youtube` | `WATCHDOG_SYNC` | **🟢 GO** | `v8_ep06_bedtime_todo_list_sleep, v8_ep07_harvard_reversible_choice_paradox` | Promote 0 elapsed Scheduled->Public, backfill 2 eligible R35 pins (>=12h/100v), link 0 unlocked R35-B Related videos |
| 2 | `2026-11-16 06:13 KST` / `2026-11-15 16:13 EST` | `youtube` | `STUDIO_INBOX_CHECK` | **🟢 GO** | `studio_comments_inbox` | Studio comments/inbox zero-playback heart & reply routine (0 self-bounce) |
| 3 | `2026-11-16 06:18 KST` / `2026-11-15 16:18 EST` | `multi_platform` | `PREPARE_BUNDLE` | **🟢 GO** | `diorama_02_ramachandran_phantom_mirror` | Export clean 9:16 multi_platform_bundle (zero YT hashtag mutation) |
| 4 | `2026-11-16 06:18 KST` / `2026-11-15 16:18 EST` | `multi_platform` | `PREPARE_BUNDLE` | **🟢 GO** | `diorama_03_alien_hand_syndrome` | Export clean 9:16 multi_platform_bundle (zero YT hashtag mutation) |
| 5 | `2026-11-16 06:18 KST` / `2026-11-15 16:18 EST` | `multi_platform` | `PREPARE_BUNDLE` | **🟢 GO** | `diorama_04_milgram_obedience_switch` | Export clean 9:16 multi_platform_bundle (zero YT hashtag mutation) |
| 6 | `2026-11-16 06:18 KST` / `2026-11-15 16:18 EST` | `multi_platform` | `PREPARE_BUNDLE` | **🟢 GO** | `diorama_05_hippocampal_memory_prosthesis` | Export clean 9:16 multi_platform_bundle (zero YT hashtag mutation) |
| 7 | `2026-11-16 06:18 KST` / `2026-11-15 16:18 EST` | `multi_platform` | `PREPARE_BUNDLE` | **🟢 GO** | `diorama_06_clive_wearing_seven_second_mind` | Export clean 9:16 multi_platform_bundle (zero YT hashtag mutation) |
| 8 | `2026-11-16 06:18 KST` / `2026-11-15 16:18 EST` | `multi_platform` | `PREPARE_BUNDLE` | **🟢 GO** | `diorama_07_invisible_gorilla_attention` | Export clean 9:16 multi_platform_bundle (zero YT hashtag mutation) |
| 9 | `2026-11-16 06:18 KST` / `2026-11-15 16:18 EST` | `multi_platform` | `PREPARE_BUNDLE` | **🟢 GO** | `reenact_01_ainsworth_strange_situation` | Export clean 9:16 multi_platform_bundle (zero YT hashtag mutation) |
| 10 | `2026-11-16 06:28 KST` / `2026-11-15 16:28 EST` | `youtube` | `HOLD_AND_PRODUCE` | **🔴 HOLD** | `next_v8_episode` | YouTube scheduled runway is 2d (< 3d target) and 0 QA-passed unpublished episodes remain; produce & pass QA for next v8 Short (<=88s, R68-H <=12w hook) |
| 11 | `2026-11-16 08:15 KST` / `2026-11-15 18:15 EST` | `instagram` | `UPLOAD_IG_REEL` | **🟢 GO** | `v8_ep05_ucl_tickle_delay_robot` | Staggered US prime Reel (Standard Reel (Warmup 0/1000 followers)); YT state=public |
| 12 | `2026-11-16 10:45 KST` / `2026-11-15 20:45 EST` | `tiktok` | `UPLOAD_TIKTOK` | **🟢 GO** | `v8_ep05_ucl_tickle_delay_robot` | Creator Rewards >=61.5s (111.6s), Original Audio, NO VPN, AIGC ON, staggered after YT |
| 13 | `2026-11-19 03:30 KST` / `2026-11-18 13:30 EST` | `instagram` | `PUBLISH_IG_CARDS` | **🟡 CONDITIONAL GO** | `v8_ep08_capgras_imposter_delusion_r77` | 4:5 (1080x1350) 6-Slide Carousel ready (non-Reel day >=+24h post-Reel, >=18h gap; 0/3 in 7d) |

### Commands

1. **youtube — `WATCHDOG_SYNC` (`v8_ep06_bedtime_todo_list_sleep, v8_ep07_harvard_reversible_choice_paradox`)**:
```bash
/home/canadaofbin/hermes-venv/bin/python -X utf8 main.py studio-watchdog --apply
```
2. **youtube — `STUDIO_INBOX_CHECK` (`studio_comments_inbox`)**:
```bash
/home/canadaofbin/hermes-venv/bin/python -X utf8 main.py studio-inbox --scan-only
```
3. **multi_platform — `PREPARE_BUNDLE` (`diorama_02_ramachandran_phantom_mirror`)**:
```bash
/home/canadaofbin/hermes-venv/bin/python -X utf8 main.py multi-bundle --project diorama_02_ramachandran_phantom_mirror
```
4. **multi_platform — `PREPARE_BUNDLE` (`diorama_03_alien_hand_syndrome`)**:
```bash
/home/canadaofbin/hermes-venv/bin/python -X utf8 main.py multi-bundle --project diorama_03_alien_hand_syndrome
```
5. **multi_platform — `PREPARE_BUNDLE` (`diorama_04_milgram_obedience_switch`)**:
```bash
/home/canadaofbin/hermes-venv/bin/python -X utf8 main.py multi-bundle --project diorama_04_milgram_obedience_switch
```
6. **multi_platform — `PREPARE_BUNDLE` (`diorama_05_hippocampal_memory_prosthesis`)**:
```bash
/home/canadaofbin/hermes-venv/bin/python -X utf8 main.py multi-bundle --project diorama_05_hippocampal_memory_prosthesis
```
7. **multi_platform — `PREPARE_BUNDLE` (`diorama_06_clive_wearing_seven_second_mind`)**:
```bash
/home/canadaofbin/hermes-venv/bin/python -X utf8 main.py multi-bundle --project diorama_06_clive_wearing_seven_second_mind
```
8. **multi_platform — `PREPARE_BUNDLE` (`diorama_07_invisible_gorilla_attention`)**:
```bash
/home/canadaofbin/hermes-venv/bin/python -X utf8 main.py multi-bundle --project diorama_07_invisible_gorilla_attention
```
9. **multi_platform — `PREPARE_BUNDLE` (`reenact_01_ainsworth_strange_situation`)**:
```bash
/home/canadaofbin/hermes-venv/bin/python -X utf8 main.py multi-bundle --project reenact_01_ainsworth_strange_situation
```
10. **youtube — `HOLD_AND_PRODUCE` (`next_v8_episode`)**:
```bash
/home/canadaofbin/hermes-venv/bin/python -X utf8 main.py diorama-episode --help
```
11. **instagram — `UPLOAD_IG_REEL` (`v8_ep05_ucl_tickle_delay_robot`)**:
```bash
/home/canadaofbin/hermes-venv/bin/python -X utf8 -c "import asyncio; from pathlib import Path; from pipeline.studio.instagram_uploader import upload_instagram_reel_cdp; p=Path('BCI_Shorts_Channel/projects/v8_ep05_ucl_tickle_delay_robot/06_publish/multi_platform_bundle'); print(asyncio.run(upload_instagram_reel_cdp(video_path=p/'video_clean.mp4', cover_path=p/'cover_9x16.png', caption=(p/'reels_caption.txt').read_text(encoding='utf-8'), handle='allaboutbrain.official', receipt_path=p.parent/'instagram_upload_receipt.json')))"
```
12. **tiktok — `UPLOAD_TIKTOK` (`v8_ep05_ucl_tickle_delay_robot`)**:
```bash
/home/canadaofbin/hermes-venv/bin/python -X utf8 -c "import asyncio; from pathlib import Path; from pipeline.studio.tiktok_uploader import upload_tiktok_video_cdp; p=Path('BCI_Shorts_Channel/projects/v8_ep05_ucl_tickle_delay_robot/06_publish/multi_platform_bundle'); print(asyncio.run(upload_tiktok_video_cdp(video_path=p/'video_clean.mp4', cover_path=p/'cover_9x16.png', caption=(p/'tiktok_caption.txt').read_text(encoding='utf-8'), receipt_path=p.parent/'tiktok_upload_receipt.json')))"
```
13. **instagram — `PUBLISH_IG_CARDS` (`v8_ep08_capgras_imposter_delusion_r77`)**:
```bash
# Publish 4:5 (1080x1350) 6-slide carousel in BCI_Shorts_Channel/projects/v8_ep08_capgras_imposter_delusion_r77/06_publish/ig_carousel/
```

## 6. Live YouTube Scheduled Buffer

- `2026-11-15 19:30 ET` — `v8_ep08_capgras_imposter_delusion_r77` (`Atd0Pi9HPg4` | `Quiz SCHEDULED/DONE`)
- `2026-11-16 19:30 ET` — `v8_ep09_maguire_london_taxi_hippocampus` (`7lKtSWvTmpw` | `Quiz ACTION_REQUIRED`)
