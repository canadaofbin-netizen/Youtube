# 🗓️ ALL ABOUT BRAIN — Multi-Platform QA Schedule & 5-Asset Execution Plan (2026-11-16)

> **Generated**: `2026-11-16 08:00 UTC` | `2026-11-16 17:00 KST` | `2026-11-16 03:00 EST`
> **Overall Decision**: **🔴 HOLD** | **Guardrails**: `PASS`

## 1. Daily Report Gate Verdict (`HOLD / GO` & Anti-Penalty Summary)

- **Source Report**: `2026-11-16` (`LIVE_CDP_DOM`, age `0.25h`)
- **Channel Pulse**: Subs `61` | IG Followers `0` | Realtime 48h `204` (`60m=32`) | Watch `133.1h` | 3s Hook `75.0%` (Gate `>=70%`) | APV `69.2%` (Gate `>=60%`) | US `66.8%` (Gate `>=45%`) | Shorts Feed `90.6%`

| Platform | Handle | Decision | Optimal Cadence | Next Safe Window (`ET` / `KST`) | Ready Queue |
| :--- | :--- | :---: | :--- | :--- | :---: |
| **YouTube** | `@AllAboutBrainOfficial` | **🔴 HOLD** | 1 Short / Day @ Slot 4 (19:30 ET) | Longform 16:9: HOLD | `2026-11-17 19:30 EST` / `2026-11-18 09:30 KST` | `0` (`Runway 1d`) |
| **Instagram** | `@allaboutbrain.official` | **🔴 HOLD** | 1 Reel / Day (warmup 3/10) @ 13:30 ET or 18:15 ET; Carousels 2-3/wk (>=18h Reel gap) | `2026-11-17 13:30 EST` / `2026-11-18 03:30 KST` | `5` Reels · `2` Carousels |
| **TikTok** | `@allaboutbrain_official` | **🔴 HOLD** | 1 Video / Day (warmup 3/14) @ 15:30 ET or 20:45 ET | `2026-11-17 15:30 EST` / `2026-11-18 05:30 KST` | `5` (`>=61.5s`) |

## 2. Anti-Penalty & Compliance Audit

### YouTube (`HOLD`)
- ✅ **`YT-REPORT-FRESH`**: Daily Report 2026-11-16 (0.2h old)
- ✅ **`YT-DOM-MODE`**: LIVE_CDP_DOM clean
- ✅ **`YT-NO-SIMULTANEOUS`**: 0 simultaneous releases
- ✅ **`YT-ZERO-QUARANTINE`**: 0 quarantined episodes
- ✅ **`YT-R75-PLAYLIST-BAN`**: 0 playlists verified (R75)
- ✅ **`YT-R75-TAG-HYGIENE`**: 0 banned off-topic tech tags across active episodes
- ✅ **`YT-US-AUDIENCE`**: US 66.8% (>= 45%), Tier-1 68.6%
- ✅ **`YT-SHORTS-FEED`**: Shorts Feed 90.6% (>= 70%)
- ✅ **`YT-3S-HOOK`**: 3s Hook 75.0% (>= 70%)
- ✅ **`YT-APV`**: APV 69.2% (gate >= 60%)
- ✅ **`YT-R35B-SCHEDULED-LINK`**: All unlocked Scheduled Shorts linked to clean Public Anchor
- **Conditions / Warnings**: 0 QA-ready unpublished candidates and buffer is only 1d (< 3d target) -> produce new v8 episode first

### Instagram (`HOLD`)
- 🛑 **`IG-RATE-LIMIT`**: 1 upload(s) in last 24h (cap 1)
- ✅ **`IG-INVENTORY`**: 5 Reel(s) + 2 4:5 Carousel(s) ready
- ✅ **`IG-CAROUSEL-CAP`**: 0/3 Carousels in 7d; locked 4:5 (1080x1350), >=18h Reel gap
- ✅ **`IG-ANTI-SPAM-SPEC`**: Clean 1080x1920 bundle (0 watermark), <=90ch Line-1 hook, AI label ON, Standard Reel (Warmup 0/1000 followers)
- **Hold / Block Reasons**: IG 24h cap reached (1/1)

### TikTok (`HOLD`)
- 🛑 **`TT-RATE-LIMIT`**: 1 upload(s) in last 24h (cap 1)
- ✅ **`TT-CREATOR-REWARDS-60S`**: 5 candidate(s) >= 61.5s with clean bundle
- ✅ **`TT-SECURITY-AIGC`**: NO VPN, AIGC disclosure ON, 4-5 niche tags (0 #fyp/#viral), halt cleanly on CAPTCHA
- **Hold / Block Reasons**: TikTok 24h cap reached (1/1)

## 3. 1-Episode -> 5 Automated Assets Ecosystem Stagger (`Workstream 4C v2`)

- **Anchor Episode**: `v8_ep09_maguire_london_taxi_hippocampus` (`YGKTFbKsFH8` | `scheduled_today` @ `2026-11-16 19:30 EST` / `2026-11-17 09:30 KST`)

| Asset | Slot (`ET` / `KST`) | Status | Target / Spec |
| :--- | :--- | :---: | :--- |
| **YouTube Community Quiz Post** | `2026-11-16 16:00 EST` / `2026-11-17 06:00 KST` | **⚡ ACTION REQUIRED** | ACTION_REQUIRED: main.py studio-quiz --project v8_ep09_maguire_london_taxi_hippocampus |
| **YouTube Short** | `2026-11-16 19:30 EST` / `2026-11-17 09:30 KST` | **🗓️ SCHEDULED** | Scheduled YGKTFbKsFH8 @ Slot 4 (2026-11-16 19:30 EST), R75 0 playlists |
| **TikTok >61.5s Original-Audio Video** | `2026-11-17 15:30 EST` / `2026-11-18 05:30 KST` | **🔴 HOLD** | Anchor v8_ep09_maguire_london_taxi_hippocampus (83.1s >= 61.5s, Original Audio, AIGC ON); Queue ready: v8_ep06_bedtime_todo_list_sleep |
| **Instagram Clean Reel** | `2026-11-17 13:30 EST` / `2026-11-18 03:30 KST` | **🔴 HOLD** | Standard Reel (Warmup 0/1000 followers); D+1 stagger >= +18h post-YT (2026-11-17 13:30 EST); Queue ready now/next slot: v8_ep06_bedtime_todo_list_sleep |
| **Instagram 4:5 (1080x1350) 6-Slide Carousel** | `2026-11-18 13:30 EST` / `2026-11-19 03:30 KST` | **🟢 GO** | Locked 4:5 (1080x1350) (6 slides, center 3:4 safe zone), non-Reel day >= +24h post-Reel (0/3 in 7d) |
| **Daily Zero-Bounce Studio Inbox Check** | `2026-11-16 09:00 EST` / `2026-11-16 23:00 KST` | **⚡ ACTION REQUIRED** | Studio comments/inbox zero-playback heart & reply routine (0 self-bounce) |

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
| 1 | `2026-11-16 17:05 KST` / `2026-11-16 03:05 EST` | `multi_platform` | `PREPARE_BUNDLE` | **🟢 GO** | `diorama_02_ramachandran_phantom_mirror` | Export clean 9:16 multi_platform_bundle (zero YT hashtag mutation) |
| 2 | `2026-11-16 17:05 KST` / `2026-11-16 03:05 EST` | `multi_platform` | `PREPARE_BUNDLE` | **🟢 GO** | `diorama_03_alien_hand_syndrome` | Export clean 9:16 multi_platform_bundle (zero YT hashtag mutation) |
| 3 | `2026-11-16 17:05 KST` / `2026-11-16 03:05 EST` | `multi_platform` | `PREPARE_BUNDLE` | **🟢 GO** | `diorama_04_milgram_obedience_switch` | Export clean 9:16 multi_platform_bundle (zero YT hashtag mutation) |
| 4 | `2026-11-16 17:05 KST` / `2026-11-16 03:05 EST` | `multi_platform` | `PREPARE_BUNDLE` | **🟢 GO** | `diorama_05_hippocampal_memory_prosthesis` | Export clean 9:16 multi_platform_bundle (zero YT hashtag mutation) |
| 5 | `2026-11-16 17:05 KST` / `2026-11-16 03:05 EST` | `multi_platform` | `PREPARE_BUNDLE` | **🟢 GO** | `diorama_06_clive_wearing_seven_second_mind` | Export clean 9:16 multi_platform_bundle (zero YT hashtag mutation) |
| 6 | `2026-11-16 17:05 KST` / `2026-11-16 03:05 EST` | `multi_platform` | `PREPARE_BUNDLE` | **🟢 GO** | `diorama_07_invisible_gorilla_attention` | Export clean 9:16 multi_platform_bundle (zero YT hashtag mutation) |
| 7 | `2026-11-16 17:05 KST` / `2026-11-16 03:05 EST` | `multi_platform` | `PREPARE_BUNDLE` | **🟢 GO** | `reenact_01_ainsworth_strange_situation` | Export clean 9:16 multi_platform_bundle (zero YT hashtag mutation) |
| 8 | `2026-11-16 17:15 KST` / `2026-11-16 03:15 EST` | `youtube` | `HOLD_AND_PRODUCE` | **🔴 HOLD** | `next_v8_episode` | YouTube scheduled runway is 1d (< 3d target) and 0 QA-passed unpublished episodes remain; produce & pass QA for next v8 Short (<=88s, R68-H <=12w hook) |
| 9 | `2026-11-16 23:00 KST` / `2026-11-16 09:00 EST` | `youtube` | `STUDIO_INBOX_CHECK` | **🟢 GO** | `studio_comments_inbox` | Studio comments/inbox zero-playback heart & reply routine (0 self-bounce) |
| 10 | `2026-11-17 06:00 KST` / `2026-11-16 16:00 EST` | `youtube` | `YT_COMMUNITY_QUIZ` | **🟢 GO** | `v8_ep09_maguire_london_taxi_hippocampus` | ACTION_REQUIRED: main.py studio-quiz --project v8_ep09_maguire_london_taxi_hippocampus |
| 11 | `2026-11-19 03:30 KST` / `2026-11-18 13:30 EST` | `instagram` | `PUBLISH_IG_CARDS` | **🟡 CONDITIONAL GO** | `v8_ep08_capgras_imposter_delusion_r77` | 4:5 (1080x1350) 6-Slide Carousel ready (non-Reel day >=+24h post-Reel, >=18h gap; 0/3 in 7d) |

### Commands

1. **multi_platform — `PREPARE_BUNDLE` (`diorama_02_ramachandran_phantom_mirror`)**:
```bash
/home/canadaofbin/hermes-venv/bin/python -X utf8 main.py multi-bundle --project diorama_02_ramachandran_phantom_mirror
```
2. **multi_platform — `PREPARE_BUNDLE` (`diorama_03_alien_hand_syndrome`)**:
```bash
/home/canadaofbin/hermes-venv/bin/python -X utf8 main.py multi-bundle --project diorama_03_alien_hand_syndrome
```
3. **multi_platform — `PREPARE_BUNDLE` (`diorama_04_milgram_obedience_switch`)**:
```bash
/home/canadaofbin/hermes-venv/bin/python -X utf8 main.py multi-bundle --project diorama_04_milgram_obedience_switch
```
4. **multi_platform — `PREPARE_BUNDLE` (`diorama_05_hippocampal_memory_prosthesis`)**:
```bash
/home/canadaofbin/hermes-venv/bin/python -X utf8 main.py multi-bundle --project diorama_05_hippocampal_memory_prosthesis
```
5. **multi_platform — `PREPARE_BUNDLE` (`diorama_06_clive_wearing_seven_second_mind`)**:
```bash
/home/canadaofbin/hermes-venv/bin/python -X utf8 main.py multi-bundle --project diorama_06_clive_wearing_seven_second_mind
```
6. **multi_platform — `PREPARE_BUNDLE` (`diorama_07_invisible_gorilla_attention`)**:
```bash
/home/canadaofbin/hermes-venv/bin/python -X utf8 main.py multi-bundle --project diorama_07_invisible_gorilla_attention
```
7. **multi_platform — `PREPARE_BUNDLE` (`reenact_01_ainsworth_strange_situation`)**:
```bash
/home/canadaofbin/hermes-venv/bin/python -X utf8 main.py multi-bundle --project reenact_01_ainsworth_strange_situation
```
8. **youtube — `HOLD_AND_PRODUCE` (`next_v8_episode`)**:
```bash
/home/canadaofbin/hermes-venv/bin/python -X utf8 main.py diorama-episode --help
```
9. **youtube — `STUDIO_INBOX_CHECK` (`studio_comments_inbox`)**:
```bash
/home/canadaofbin/hermes-venv/bin/python -X utf8 main.py studio-inbox --scan-only
```
10. **youtube — `YT_COMMUNITY_QUIZ` (`v8_ep09_maguire_london_taxi_hippocampus`)**:
```bash
/home/canadaofbin/hermes-venv/bin/python -X utf8 main.py studio-quiz --project v8_ep09_maguire_london_taxi_hippocampus
```
11. **instagram — `PUBLISH_IG_CARDS` (`v8_ep08_capgras_imposter_delusion_r77`)**:
```bash
# Publish 4:5 (1080x1350) 6-slide carousel in BCI_Shorts_Channel/projects/v8_ep08_capgras_imposter_delusion_r77/06_publish/ig_carousel/
```

## 6. Live YouTube Scheduled Buffer

- `2026-11-16 19:30 ET` — `v8_ep09_maguire_london_taxi_hippocampus` (`YGKTFbKsFH8` | `Quiz ACTION_REQUIRED`)
