# 🗓️ ALL ABOUT BRAIN — Multi-Platform QA Schedule & 5-Asset Execution Plan (2026-11-20)

> **Generated**: `2026-11-20 08:01 UTC` | `2026-11-20 17:01 KST` | `2026-11-20 03:01 EST`
> **Overall Decision**: **🔴 HOLD** | **Guardrails**: `PASS`

## 1. Daily Report Gate Verdict (`HOLD / GO` & Anti-Penalty Summary)

- **Source Report**: `2026-11-20` (`LIVE_CDP_DOM`, age `1.03h`)
- **Channel Pulse (Parsed KPIs)**: Subs `62` | IG Followers `0` | Realtime 48h `777` | 3s Hook `72.9%` (Gate `>=70%`) | APV `67.0%` (Gate `>=60%`) | US `64.7%` (Gate `>=45%`) | Shorts Feed `89.1%` *(hardcoded `60m`/`unique_viewers` & 28d-cloned `views`/`watch_hours` excluded)*

| Platform | Handle | Decision | Optimal Cadence | Next Safe Window (`ET` / `KST`) | Ready Queue |
| :--- | :--- | :---: | :--- | :--- | :---: |
| **YouTube** | `@AllAboutBrainOfficial` | **🔴 HOLD** | 1 Short / Day @ Slot 4 (19:30 ET) | Longform 16:9: HOLD | `2026-11-22 19:30 EST` / `2026-11-23 09:30 KST` | `0` (`Runway 2d`) |
| **Instagram** | `@allaboutbrain.official` | **🔴 HOLD** | 1 Reel / Day (warmup 4/10) @ 13:30 ET or 18:15 ET; Carousels 2-3/wk (>=18h Reel gap) | `2026-11-20 18:15 EST` / `2026-11-21 08:15 KST` | `8` Reels · `6` Carousels |
| **TikTok** | `@allaboutbrain_official` | **🔴 HOLD** | 1 Video / Day (warmup 4/14) @ 15:30 ET or 20:45 ET | `2026-11-20 20:45 EST` / `2026-11-21 10:45 KST` | `8` (`>=61.5s`) |

## 2. Anti-Penalty & Compliance Audit

### YouTube (`HOLD`)
- ✅ **`YT-REPORT-FRESH`**: Daily Report 2026-11-20 (1.0h old)
- ✅ **`YT-DOM-MODE`**: LIVE_CDP_DOM clean
- ✅ **`YT-NO-SIMULTANEOUS`**: 0 simultaneous releases
- ✅ **`YT-ZERO-QUARANTINE`**: 0 quarantined episodes
- ✅ **`YT-R75-PLAYLIST-BAN`**: 0 playlists verified (R75)
- ✅ **`YT-R75-TAG-HYGIENE`**: 0 banned off-topic tech tags across active episodes
- ✅ **`YT-US-AUDIENCE`**: US 64.7% (>= 45%), Tier-1 66.4%
- ✅ **`YT-SHORTS-FEED`**: Shorts Feed 89.1% (>= 70%)
- ✅ **`YT-3S-HOOK`**: 3s Hook 72.9% (>= 70%)
- ✅ **`YT-APV`**: APV 67.0% (gate >= 60%)
- ✅ **`YT-R35B-SCHEDULED-LINK`**: All unlocked Scheduled Shorts linked to clean Public Anchor
- **Conditions / Warnings**: 0 QA-ready unpublished candidates and buffer is only 2d (< 3d target) -> produce new v8 episode first

### Instagram (`HOLD`)
- 🛑 **`IG-RATE-LIMIT`**: 1 upload(s) in last 24h (cap 1)
- ✅ **`IG-INVENTORY`**: 8 Reel(s) + 6 4:5 Carousel(s) ready
- ✅ **`IG-CAROUSEL-CAP`**: 0/3 Carousels in 7d; locked 4:5 (1080x1350), >=18h Reel gap
- ✅ **`IG-ANTI-SPAM-SPEC`**: Clean 1080x1920 bundle (0 watermark), <=90ch Line-1 hook, AI label ON, Standard Reel (Warmup 0/1000 followers)
- **Hold / Block Reasons**: IG 24h cap reached (1/1)

### TikTok (`HOLD`)
- 🛑 **`TT-RATE-LIMIT`**: 1 upload(s) in last 24h (cap 1)
- ✅ **`TT-CREATOR-REWARDS-60S`**: 8 candidate(s) >= 61.5s with clean bundle
- ✅ **`TT-SECURITY-AIGC`**: NO VPN, AIGC disclosure ON, 4-5 niche tags (0 #fyp/#viral), halt cleanly on CAPTCHA
- **Hold / Block Reasons**: TikTok 24h cap reached (1/1)

## 3. 1-Episode -> 5 Automated Assets Ecosystem Stagger (`Workstream 4C v2`)

- **Anchor Episode**: `v8_ep11_open_label_placebo_pain` (`lIvz80VKYPA` | `scheduled_today` @ `2026-11-20 19:30 EST` / `2026-11-21 09:30 KST`)

| Asset | Slot (`ET` / `KST`) | Status | Target / Spec |
| :--- | :--- | :---: | :--- |
| **YouTube Community Quiz Post** | `2026-11-20 16:00 EST` / `2026-11-21 06:00 KST` | **✅ SCHEDULED/DONE** | community_quiz_receipt.json verified (D-Day -3.5h pre-heat) |
| **YouTube Short** | `2026-11-20 19:30 EST` / `2026-11-21 09:30 KST` | **🗓️ SCHEDULED** | Scheduled lIvz80VKYPA @ Slot 4 (2026-11-20 19:30 EST), R75 0 playlists |
| **TikTok >61.5s Original-Audio Video** | `2026-11-20 20:45 EST` / `2026-11-21 10:45 KST` | **🔴 HOLD** | Anchor v8_ep11_open_label_placebo_pain (80.0s >= 61.5s, Original Audio, AIGC ON); Queue ready: reenact_01_ainsworth_strange_situation |
| **Instagram Clean Reel** | `2026-11-21 13:30 EST` / `2026-11-22 03:30 KST` | **🔴 HOLD** | Standard Reel (Warmup 0/1000 followers); D+1 stagger >= +18h post-YT (2026-11-21 13:30 EST); Queue ready now/next slot: reenact_01_ainsworth_strange_situation |
| **Instagram 4:5 (1080x1350) 6-Slide Carousel** | `2026-11-22 13:30 EST` / `2026-11-23 03:30 KST` | **🟢 GO** | Locked 4:5 (1080x1350) (6 slides, center 3:4 safe zone), non-Reel day >= +24h post-Reel (0/3 in 7d) |
| **Daily Zero-Bounce Studio Inbox Check** | `2026-11-20 09:00 EST` / `2026-11-20 23:00 KST` | **⚡ ACTION REQUIRED** | Studio comments/inbox zero-playback heart & reply routine (0 self-bounce) |

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
| 1 | `2026-11-20 17:16 KST` / `2026-11-20 03:16 EST` | `youtube` | `HOLD_AND_PRODUCE` | **🔴 HOLD** | `next_v8_episode` | YouTube scheduled runway is 2d (< 3d target) and 0 QA-passed unpublished episodes remain; produce & pass QA for next v8 Short (<=88s, R68-H <=12w hook) |
| 2 | `2026-11-20 23:00 KST` / `2026-11-20 09:00 EST` | `youtube` | `STUDIO_INBOX_CHECK` | **🟢 GO** | `studio_comments_inbox` | Studio comments/inbox zero-playback heart & reply routine (0 self-bounce) |
| 3 | `2026-11-24 03:30 KST` / `2026-11-23 13:30 EST` | `instagram` | `PUBLISH_IG_CARDS` | **🟡 CONDITIONAL GO** | `reenact_01_ainsworth_strange_situation` | 4:5 (1080x1350) 6-Slide Carousel ready (non-Reel day >=+24h post-Reel, >=18h gap; 0/3 in 7d) |

### Commands

1. **youtube — `HOLD_AND_PRODUCE` (`next_v8_episode`)**:
```bash
/home/canadaofbin/hermes-venv/bin/python -X utf8 main.py diorama-episode --help
```
2. **youtube — `STUDIO_INBOX_CHECK` (`studio_comments_inbox`)**:
```bash
/home/canadaofbin/hermes-venv/bin/python -X utf8 main.py studio-inbox --scan-only
```
3. **instagram — `PUBLISH_IG_CARDS` (`reenact_01_ainsworth_strange_situation`)**:
```bash
# Publish 4:5 (1080x1350) 6-slide carousel in BCI_Shorts_Channel/projects/reenact_01_ainsworth_strange_situation/06_publish/ig_carousel/
```

## 6. Live YouTube Scheduled Buffer

- `2026-11-20 19:30 ET` — `v8_ep11_open_label_placebo_pain` (`lIvz80VKYPA` | `Quiz SCHEDULED/DONE`)
- `2026-11-21 19:30 ET` — `v8_ep12_doorway_effect_memory` (`fGxHHP9IuSE` | `Quiz SCHEDULED/DONE`)

## 7. Blocked / Non-Ready Inventory (Excluded to Prevent Penalty)

- `v8_ep09_maguire_london_taxi_hippocampus_r82`: r85_rebuild_hold (internal_ab_or_render_test), awaiting_r85_ceo_verification

## 8. Evidence & QA/Verify Receipts (R83-5~7 / R85)

- **Input Metrics Report**: `/home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/BCI_Shorts_Channel/reports/daily/2026-11-20_studio_metrics.json`
- **KPI Snapshot (Parsed Only)**: Subs `62`, 48h Views `777`, 3s Hook `72.9%`, APV `67.0%`, US `64.7%`, Shorts Feed `89.1%`
- **`reenact_01_ainsworth_strange_situation`** [READY | CEO Verify PENDING/MISSING]: `manifest`=`/home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/BCI_Shorts_Channel/projects/reenact_01_ainsworth_strange_situation/00_project_manifest.json`, `video_autopsy`=`/home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/BCI_Shorts_Channel/projects/reenact_01_ainsworth_strange_situation/05_assembly/video_autopsy_report.json`, `dynamic_episode_qa`=`/home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/BCI_Shorts_Channel/projects/reenact_01_ainsworth_strange_situation/05_assembly/dynamic_episode_qa_report.json`, `posthoc_semantic_qa`=`/home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/BCI_Shorts_Channel/projects/reenact_01_ainsworth_strange_situation/05_assembly/posthoc_semantic_qa_report.json`, `posthoc_semantic_review`=`/home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/BCI_Shorts_Channel/projects/reenact_01_ainsworth_strange_situation/05_assembly/posthoc_semantic_review.json`
- **`v8_ep07_harvard_reversible_choice_paradox`** [READY | CEO Verify PENDING/MISSING]: `manifest`=`/home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/BCI_Shorts_Channel/projects/v8_ep07_harvard_reversible_choice_paradox/00_project_manifest.json`, `video_autopsy`=`/home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/BCI_Shorts_Channel/projects/v8_ep07_harvard_reversible_choice_paradox/05_assembly/video_autopsy_report.json`, `dynamic_episode_qa`=`/home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/BCI_Shorts_Channel/projects/v8_ep07_harvard_reversible_choice_paradox/05_assembly/dynamic_episode_qa_report.json`, `posthoc_semantic_qa`=`/home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/BCI_Shorts_Channel/projects/v8_ep07_harvard_reversible_choice_paradox/05_assembly/posthoc_semantic_qa_report.json`, `posthoc_semantic_review`=`/home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/BCI_Shorts_Channel/projects/v8_ep07_harvard_reversible_choice_paradox/05_assembly/posthoc_semantic_review.json`
- **`v8_ep09_maguire_london_taxi_hippocampus_r82`** [HOLD: r85_rebuild_hold (internal_ab_or_render_test), awaiting_r85_ceo_verification | CEO Verify PENDING/MISSING]: `manifest`=`/home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/BCI_Shorts_Channel/projects/v8_ep09_maguire_london_taxi_hippocampus_r82/00_project_manifest.json`, `video_autopsy`=`/home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/BCI_Shorts_Channel/projects/v8_ep09_maguire_london_taxi_hippocampus_r82/05_assembly/video_autopsy_report.json`, `dynamic_episode_qa`=`/home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/BCI_Shorts_Channel/projects/v8_ep09_maguire_london_taxi_hippocampus_r82/05_assembly/dynamic_episode_qa_report.json`, `posthoc_semantic_qa`=`/home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/BCI_Shorts_Channel/projects/v8_ep09_maguire_london_taxi_hippocampus_r82/05_assembly/posthoc_semantic_qa_report.json`, `posthoc_semantic_review`=`/home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/BCI_Shorts_Channel/projects/v8_ep09_maguire_london_taxi_hippocampus_r82/05_assembly/posthoc_semantic_review.json`
