# 🗓️ ALL ABOUT BRAIN — Multi-Platform QA Schedule & 5-Asset Execution Plan (2026-11-17)

> **Generated**: `2026-11-17 08:00 UTC` | `2026-11-17 17:00 KST` | `2026-11-17 03:00 EST`
> **Overall Decision**: **🟢 GO** | **Guardrails**: `PASS`

## 1. Daily Report Gate Verdict (`HOLD / GO` & Anti-Penalty Summary)

- **Source Report**: `2026-11-17` (`LIVE_CDP_DOM`, age `1.0h`)
- **Channel Pulse**: Subs `61` | IG Followers `0` | Realtime 48h `170` (`60m=32`) | Watch `133.8h` | 3s Hook `74.9%` (Gate `>=70%`) | APV `69.1%` (Gate `>=60%`) | US `67.4%` (Gate `>=45%`) | Shorts Feed `90.6%`

| Platform | Handle | Decision | Optimal Cadence | Next Safe Window (`ET` / `KST`) | Ready Queue |
| :--- | :--- | :---: | :--- | :--- | :---: |
| **YouTube** | `@AllAboutBrainOfficial` | **🟢 GO** | 1 Short / Day @ Slot 4 (19:30 ET) | Longform 16:9: HOLD | `2026-11-17 19:30 EST` / `2026-11-18 09:30 KST` | `1` (`Runway 0d`) |
| **Instagram** | `@allaboutbrain.official` | **🟢 GO** | 1 Reel / Day (warmup 3/10) @ 13:30 ET or 18:15 ET; Carousels 2-3/wk (>=18h Reel gap) | `2026-11-17 13:30 EST` / `2026-11-18 03:30 KST` | `6` Reels · `5` Carousels |
| **TikTok** | `@allaboutbrain_official` | **🟢 GO** | 1 Video / Day (warmup 3/14) @ 15:30 ET or 20:45 ET | `2026-11-17 15:30 EST` / `2026-11-18 05:30 KST` | `6` (`>=61.5s`) |

## 2. Anti-Penalty & Compliance Audit

### YouTube (`GO`)
- ✅ **`YT-REPORT-FRESH`**: Daily Report 2026-11-17 (1.0h old)
- ✅ **`YT-DOM-MODE`**: LIVE_CDP_DOM clean
- ✅ **`YT-NO-SIMULTANEOUS`**: 0 simultaneous releases
- ✅ **`YT-ZERO-QUARANTINE`**: 0 quarantined episodes
- ✅ **`YT-R75-PLAYLIST-BAN`**: 0 playlists verified (R75)
- ✅ **`YT-R75-TAG-HYGIENE`**: 0 banned off-topic tech tags across active episodes
- ✅ **`YT-US-AUDIENCE`**: US 67.4% (>= 45%), Tier-1 69.2%
- ✅ **`YT-SHORTS-FEED`**: Shorts Feed 90.6% (>= 70%)
- ✅ **`YT-3S-HOOK`**: 3s Hook 74.9% (>= 70%)
- ✅ **`YT-APV`**: APV 69.1% (gate >= 60%)
- ✅ **`YT-R35B-SCHEDULED-LINK`**: All unlocked Scheduled Shorts linked to clean Public Anchor

### Instagram (`GO`)
- ✅ **`IG-COOLDOWN`**: 28.2h since last Reel (>= 18h)
- ✅ **`IG-INVENTORY`**: 6 Reel(s) + 5 4:5 Carousel(s) ready
- ✅ **`IG-CAROUSEL-CAP`**: 0/3 Carousels in 7d; locked 4:5 (1080x1350), >=18h Reel gap
- ✅ **`IG-ANTI-SPAM-SPEC`**: Clean 1080x1920 bundle (0 watermark), <=90ch Line-1 hook, AI label ON, Standard Reel (Warmup 0/1000 followers)

### TikTok (`GO`)
- ✅ **`TT-COOLDOWN`**: 28.2h since last post (>= 20h)
- ✅ **`TT-CREATOR-REWARDS-60S`**: 6 candidate(s) >= 61.5s with clean bundle
- ✅ **`TT-SECURITY-AIGC`**: NO VPN, AIGC disclosure ON, 4-5 niche tags (0 #fyp/#viral), halt cleanly on CAPTCHA

## 3. 1-Episode -> 5 Automated Assets Ecosystem Stagger (`Workstream 4C v2`)

- **Anchor Episode**: `v8_ep11_open_label_placebo_pain` (`queued` | `ready_candidate` @ `2026-11-17 19:30 EST` / `2026-11-18 09:30 KST`)

| Asset | Slot (`ET` / `KST`) | Status | Target / Spec |
| :--- | :--- | :---: | :--- |
| **YouTube Community Quiz Post** | `2026-11-17 16:00 EST` / `2026-11-18 06:00 KST` | **⚡ ACTION REQUIRED** | ACTION_REQUIRED: main.py studio-quiz --project v8_ep11_open_label_placebo_pain |
| **YouTube Short** | `2026-11-17 19:30 EST` / `2026-11-18 09:30 KST` | **🟢 GO** | YouTube verdict=GO |
| **TikTok >61.5s Original-Audio Video** | `2026-11-17 20:45 EST` / `2026-11-18 10:45 KST` | **🟢 GO** | Anchor v8_ep11_open_label_placebo_pain (80.0s >= 61.5s, Original Audio, AIGC ON); Queue ready: v8_ep06_bedtime_todo_list_sleep |
| **Instagram Clean Reel** | `2026-11-18 13:30 EST` / `2026-11-19 03:30 KST` | **🟢 GO** | Standard Reel (Warmup 0/1000 followers); D+1 stagger >= +18h post-YT (2026-11-18 13:30 EST); Queue ready now/next slot: v8_ep06_bedtime_todo_list_sleep |
| **Instagram 4:5 (1080x1350) 6-Slide Carousel** | `2026-11-19 13:30 EST` / `2026-11-20 03:30 KST` | **🟢 GO** | Locked 4:5 (1080x1350) (6 slides, center 3:4 safe zone), non-Reel day >= +24h post-Reel (0/3 in 7d) |
| **Daily Zero-Bounce Studio Inbox Check** | `2026-11-17 09:00 EST` / `2026-11-17 23:00 KST` | **⚡ ACTION REQUIRED** | Studio comments/inbox zero-playback heart & reply routine (0 self-bounce) |

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
| 1 | `2026-11-17 17:00 KST` / `2026-11-17 03:00 EST` | `youtube` | `WATCHDOG_SYNC` | **🟢 GO** | `v8_ep08_capgras_imposter_delusion_r77, v8_ep09_maguire_london_taxi_hippocampus` | Promote 1 elapsed Scheduled->Public, backfill 1 eligible R35 pins (>=12h/100v), link 0 unlocked R35-B Related videos |
| 2 | `2026-11-17 17:05 KST` / `2026-11-17 03:05 EST` | `multi_platform` | `PREPARE_BUNDLE` | **🟢 GO** | `diorama_02_ramachandran_phantom_mirror` | Export clean 9:16 multi_platform_bundle (zero YT hashtag mutation) |
| 3 | `2026-11-17 17:05 KST` / `2026-11-17 03:05 EST` | `multi_platform` | `PREPARE_BUNDLE` | **🟢 GO** | `diorama_03_alien_hand_syndrome` | Export clean 9:16 multi_platform_bundle (zero YT hashtag mutation) |
| 4 | `2026-11-17 17:05 KST` / `2026-11-17 03:05 EST` | `multi_platform` | `PREPARE_BUNDLE` | **🟢 GO** | `diorama_04_milgram_obedience_switch` | Export clean 9:16 multi_platform_bundle (zero YT hashtag mutation) |
| 5 | `2026-11-17 17:05 KST` / `2026-11-17 03:05 EST` | `multi_platform` | `PREPARE_BUNDLE` | **🟢 GO** | `diorama_05_hippocampal_memory_prosthesis` | Export clean 9:16 multi_platform_bundle (zero YT hashtag mutation) |
| 6 | `2026-11-17 17:05 KST` / `2026-11-17 03:05 EST` | `multi_platform` | `PREPARE_BUNDLE` | **🟢 GO** | `diorama_06_clive_wearing_seven_second_mind` | Export clean 9:16 multi_platform_bundle (zero YT hashtag mutation) |
| 7 | `2026-11-17 17:05 KST` / `2026-11-17 03:05 EST` | `multi_platform` | `PREPARE_BUNDLE` | **🟢 GO** | `diorama_07_invisible_gorilla_attention` | Export clean 9:16 multi_platform_bundle (zero YT hashtag mutation) |
| 8 | `2026-11-17 17:05 KST` / `2026-11-17 03:05 EST` | `multi_platform` | `PREPARE_BUNDLE` | **🟢 GO** | `reenact_01_ainsworth_strange_situation` | Export clean 9:16 multi_platform_bundle (zero YT hashtag mutation) |
| 9 | `2026-11-17 23:00 KST` / `2026-11-17 09:00 EST` | `youtube` | `STUDIO_INBOX_CHECK` | **🟢 GO** | `studio_comments_inbox` | Studio comments/inbox zero-playback heart & reply routine (0 self-bounce) |
| 10 | `2026-11-18 03:30 KST` / `2026-11-17 13:30 EST` | `instagram` | `UPLOAD_IG_REEL` | **🟢 GO** | `v8_ep06_bedtime_todo_list_sleep` | Staggered US prime Reel (Standard Reel (Warmup 0/1000 followers)); YT state=public |
| 11 | `2026-11-18 05:30 KST` / `2026-11-17 15:30 EST` | `tiktok` | `UPLOAD_TIKTOK` | **🟢 GO** | `v8_ep06_bedtime_todo_list_sleep` | Creator Rewards >=61.5s (114.3s), Original Audio, NO VPN, AIGC ON, staggered after YT |
| 12 | `2026-11-18 06:00 KST` / `2026-11-17 16:00 EST` | `youtube` | `YT_COMMUNITY_QUIZ` | **🟢 GO** | `v8_ep11_open_label_placebo_pain` | ACTION_REQUIRED: main.py studio-quiz --project v8_ep11_open_label_placebo_pain |
| 13 | `2026-11-18 09:30 KST` / `2026-11-17 19:30 EST` | `youtube` | `UPLOAD_YT_SCHEDULED` | **🟢 GO** | `v8_ep11_open_label_placebo_pain` | Stage into next vacant Slot 4 (19:30 ET) >=3h warmup; extend runway beyond 0d |
| 14 | `2026-11-19 03:30 KST` / `2026-11-18 13:30 EST` | `instagram` | `PUBLISH_IG_CARDS` | **🟡 CONDITIONAL GO** | `v8_ep08_capgras_imposter_delusion_r77` | 4:5 (1080x1350) 6-Slide Carousel ready (non-Reel day >=+24h post-Reel, >=18h gap; 0/3 in 7d) |

### Commands

1. **youtube — `WATCHDOG_SYNC` (`v8_ep08_capgras_imposter_delusion_r77, v8_ep09_maguire_london_taxi_hippocampus`)**:
```bash
/home/canadaofbin/hermes-venv/bin/python -X utf8 main.py studio-watchdog --apply
```
2. **multi_platform — `PREPARE_BUNDLE` (`diorama_02_ramachandran_phantom_mirror`)**:
```bash
/home/canadaofbin/hermes-venv/bin/python -X utf8 main.py multi-bundle --project diorama_02_ramachandran_phantom_mirror
```
3. **multi_platform — `PREPARE_BUNDLE` (`diorama_03_alien_hand_syndrome`)**:
```bash
/home/canadaofbin/hermes-venv/bin/python -X utf8 main.py multi-bundle --project diorama_03_alien_hand_syndrome
```
4. **multi_platform — `PREPARE_BUNDLE` (`diorama_04_milgram_obedience_switch`)**:
```bash
/home/canadaofbin/hermes-venv/bin/python -X utf8 main.py multi-bundle --project diorama_04_milgram_obedience_switch
```
5. **multi_platform — `PREPARE_BUNDLE` (`diorama_05_hippocampal_memory_prosthesis`)**:
```bash
/home/canadaofbin/hermes-venv/bin/python -X utf8 main.py multi-bundle --project diorama_05_hippocampal_memory_prosthesis
```
6. **multi_platform — `PREPARE_BUNDLE` (`diorama_06_clive_wearing_seven_second_mind`)**:
```bash
/home/canadaofbin/hermes-venv/bin/python -X utf8 main.py multi-bundle --project diorama_06_clive_wearing_seven_second_mind
```
7. **multi_platform — `PREPARE_BUNDLE` (`diorama_07_invisible_gorilla_attention`)**:
```bash
/home/canadaofbin/hermes-venv/bin/python -X utf8 main.py multi-bundle --project diorama_07_invisible_gorilla_attention
```
8. **multi_platform — `PREPARE_BUNDLE` (`reenact_01_ainsworth_strange_situation`)**:
```bash
/home/canadaofbin/hermes-venv/bin/python -X utf8 main.py multi-bundle --project reenact_01_ainsworth_strange_situation
```
9. **youtube — `STUDIO_INBOX_CHECK` (`studio_comments_inbox`)**:
```bash
/home/canadaofbin/hermes-venv/bin/python -X utf8 main.py studio-inbox --scan-only
```
10. **instagram — `UPLOAD_IG_REEL` (`v8_ep06_bedtime_todo_list_sleep`)**:
```bash
/home/canadaofbin/hermes-venv/bin/python -X utf8 -c "import asyncio; from pathlib import Path; from pipeline.studio.instagram_uploader import upload_instagram_reel_cdp; p=Path('BCI_Shorts_Channel/projects/v8_ep06_bedtime_todo_list_sleep/06_publish/multi_platform_bundle'); print(asyncio.run(upload_instagram_reel_cdp(video_path=p/'video_clean.mp4', cover_path=p/'cover_9x16.png', caption=(p/'reels_caption.txt').read_text(encoding='utf-8'), handle='allaboutbrain.official', receipt_path=p.parent/'instagram_upload_receipt.json')))"
```
11. **tiktok — `UPLOAD_TIKTOK` (`v8_ep06_bedtime_todo_list_sleep`)**:
```bash
/home/canadaofbin/hermes-venv/bin/python -X utf8 -c "import asyncio; from pathlib import Path; from pipeline.studio.tiktok_uploader import upload_tiktok_video_cdp; p=Path('BCI_Shorts_Channel/projects/v8_ep06_bedtime_todo_list_sleep/06_publish/multi_platform_bundle'); print(asyncio.run(upload_tiktok_video_cdp(video_path=p/'video_clean.mp4', cover_path=p/'cover_9x16.png', caption=(p/'tiktok_caption.txt').read_text(encoding='utf-8'), receipt_path=p.parent/'tiktok_upload_receipt.json')))"
```
12. **youtube — `YT_COMMUNITY_QUIZ` (`v8_ep11_open_label_placebo_pain`)**:
```bash
/home/canadaofbin/hermes-venv/bin/python -X utf8 main.py studio-quiz --project v8_ep11_open_label_placebo_pain
```
13. **youtube — `UPLOAD_YT_SCHEDULED` (`v8_ep11_open_label_placebo_pain`)**:
```bash
/home/canadaofbin/hermes-venv/bin/python -X utf8 main.py studio-upload --project v8_ep11_open_label_placebo_pain --visibility scheduled --slot 4 --date 2026-11-17
```
14. **instagram — `PUBLISH_IG_CARDS` (`v8_ep08_capgras_imposter_delusion_r77`)**:
```bash
# Publish 4:5 (1080x1350) 6-slide carousel in BCI_Shorts_Channel/projects/v8_ep08_capgras_imposter_delusion_r77/06_publish/ig_carousel/
```

## 7. Blocked / Non-Ready Inventory (Excluded to Prevent Penalty)

- `v8_ep10_sleep_pill_brain_wash`: prosody_qa_not_passed
- `v8_ep12_doorway_effect_memory`: prosody_qa_not_passed
