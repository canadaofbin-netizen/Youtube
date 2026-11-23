# 🗓️ ALL ABOUT BRAIN — Multi-Platform QA Schedule & 5-Asset Execution Plan (2026-11-18)

> **Generated**: `2026-11-18 08:13 UTC` | `2026-11-18 17:13 KST` | `2026-11-18 03:13 EST`
> **Overall Decision**: **PARTIAL_GO** | **Guardrails**: `PASS`

## 1. Daily Report Gate Verdict (`HOLD / GO` & Anti-Penalty Summary)

- **Source Report**: `2026-11-18` (`LIVE_CDP_DOM`, age `0.2h`)
- **Channel Pulse (Parsed KPIs)**: Subs `61` | IG Followers `0` | Realtime 48h `84` | 3s Hook `73.1%` (Gate `>=70%`) | APV `69.1%` (Gate `>=60%`) | US `64.4%` (Gate `>=45%`) | Shorts Feed `89.3%` *(hardcoded `60m`/`unique_viewers` & 28d-cloned `views`/`watch_hours` excluded)*

| Platform | Handle | Decision | Optimal Cadence | Next Safe Window (`ET` / `KST`) | Ready Queue |
| :--- | :--- | :---: | :--- | :--- | :---: |
| **YouTube** | `@AllAboutBrainOfficial` | **🔴 HOLD** | 1 Short / Day @ Slot 4 (19:30 ET) | Longform 16:9: HOLD | `2026-11-18 19:30 EST` / `2026-11-19 09:30 KST` | `0` (`Runway 0d`) |
| **Instagram** | `@allaboutbrain.official` | **🟢 GO** | 1 Reel / Day (warmup 3/10) @ 13:30 ET or 18:15 ET; Carousels 2-3/wk (>=18h Reel gap) | `2026-11-18 13:30 EST` / `2026-11-19 03:30 KST` | `5` Reels · `5` Carousels |
| **TikTok** | `@allaboutbrain_official` | **🟢 GO** | 1 Video / Day (warmup 3/14) @ 15:30 ET or 20:45 ET | `2026-11-18 15:30 EST` / `2026-11-19 05:30 KST` | `5` (`>=61.5s`) |

## 2. Anti-Penalty & Compliance Audit

### YouTube (`HOLD`)
- ✅ **`YT-REPORT-FRESH`**: Daily Report 2026-11-18 (0.2h old)
- ✅ **`YT-DOM-MODE`**: LIVE_CDP_DOM clean
- ✅ **`YT-NO-SIMULTANEOUS`**: 0 simultaneous releases
- ✅ **`YT-ZERO-QUARANTINE`**: 0 quarantined episodes
- ✅ **`YT-R75-PLAYLIST-BAN`**: 0 playlists verified (R75)
- ✅ **`YT-R75-TAG-HYGIENE`**: 0 banned off-topic tech tags across active episodes
- ✅ **`YT-US-AUDIENCE`**: US 64.4% (>= 45%), Tier-1 66.1%
- ✅ **`YT-SHORTS-FEED`**: Shorts Feed 89.3% (>= 70%)
- ✅ **`YT-3S-HOOK`**: 3s Hook 73.1% (>= 70%)
- ✅ **`YT-APV`**: APV 69.1% (gate >= 60%)
- ✅ **`YT-R35B-SCHEDULED-LINK`**: All unlocked Scheduled Shorts linked to clean Public Anchor
- **Conditions / Warnings**: 0 QA-ready unpublished candidates and buffer is only 0d (< 3d target) -> produce new v8 episode first

### Instagram (`GO`)
- ✅ **`IG-COOLDOWN`**: 52.4h since last Reel (>= 18h)
- ✅ **`IG-INVENTORY`**: 5 Reel(s) + 5 4:5 Carousel(s) ready
- ✅ **`IG-CAROUSEL-CAP`**: 0/3 Carousels in 7d; locked 4:5 (1080x1350), >=18h Reel gap
- ✅ **`IG-ANTI-SPAM-SPEC`**: Clean 1080x1920 bundle (0 watermark), <=90ch Line-1 hook, AI label ON, Standard Reel (Warmup 0/1000 followers)

### TikTok (`GO`)
- ✅ **`TT-COOLDOWN`**: 52.4h since last post (>= 20h)
- ✅ **`TT-CREATOR-REWARDS-60S`**: 5 candidate(s) >= 61.5s with clean bundle
- ✅ **`TT-SECURITY-AIGC`**: NO VPN, AIGC disclosure ON, 4-5 niche tags (0 #fyp/#viral), halt cleanly on CAPTCHA

## 3. 1-Episode -> 5 Automated Assets Ecosystem Stagger (`Workstream 4C v2`)

- **Anchor Episode**: None scheduled or queued

| Asset | Slot (`ET` / `KST`) | Status | Target / Spec |
| :--- | :--- | :---: | :--- |
| **Daily Zero-Bounce Studio Inbox Check** | `2026-11-18 09:00 EST` / `2026-11-18 23:00 KST` | **⚡ ACTION REQUIRED** | Studio comments/inbox zero-playback heart & reply routine (0 self-bounce) |

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
| 1 | `2026-11-18 17:18 KST` / `2026-11-18 03:18 EST` | `multi_platform` | `PREPARE_BUNDLE` | **🟢 GO** | `reenact_01_ainsworth_strange_situation` | Export clean 9:16 multi_platform_bundle (zero YT hashtag mutation) |
| 2 | `2026-11-18 17:28 KST` / `2026-11-18 03:28 EST` | `youtube` | `HOLD_AND_PRODUCE` | **🔴 HOLD** | `next_v8_episode` | YouTube scheduled runway is 0d (< 3d target) and 0 QA-passed unpublished episodes remain; produce & pass QA for next v8 Short (<=88s, R68-H <=12w hook) |
| 3 | `2026-11-18 23:00 KST` / `2026-11-18 09:00 EST` | `youtube` | `STUDIO_INBOX_CHECK` | **🟢 GO** | `studio_comments_inbox` | Studio comments/inbox zero-playback heart & reply routine (0 self-bounce) |
| 4 | `2026-11-19 03:30 KST` / `2026-11-18 13:30 EST` | `instagram` | `UPLOAD_IG_REEL` | **🟢 GO** | `v8_ep06_bedtime_todo_list_sleep` | Staggered US prime Reel (Standard Reel (Warmup 0/1000 followers)); YT state=public |
| 5 | `2026-11-19 05:30 KST` / `2026-11-18 15:30 EST` | `tiktok` | `UPLOAD_TIKTOK` | **🟢 GO** | `v8_ep06_bedtime_todo_list_sleep` | Creator Rewards >=61.5s (114.3s), Original Audio, NO VPN, AIGC ON, staggered after YT |
| 6 | `2026-11-20 03:30 KST` / `2026-11-19 13:30 EST` | `instagram` | `PUBLISH_IG_CARDS` | **🟡 CONDITIONAL GO** | `v8_ep08_capgras_imposter_delusion_r77` | 4:5 (1080x1350) 6-Slide Carousel ready (non-Reel day >=+24h post-Reel, >=18h gap; 0/3 in 7d) |

### Commands

1. **multi_platform — `PREPARE_BUNDLE` (`reenact_01_ainsworth_strange_situation`)**:
```bash
/home/canadaofbin/hermes-venv/bin/python -X utf8 main.py multi-bundle --project reenact_01_ainsworth_strange_situation
```
2. **youtube — `HOLD_AND_PRODUCE` (`next_v8_episode`)**:
```bash
/home/canadaofbin/hermes-venv/bin/python -X utf8 main.py diorama-episode --help
```
3. **youtube — `STUDIO_INBOX_CHECK` (`studio_comments_inbox`)**:
```bash
/home/canadaofbin/hermes-venv/bin/python -X utf8 main.py studio-inbox --scan-only
```
4. **instagram — `UPLOAD_IG_REEL` (`v8_ep06_bedtime_todo_list_sleep`)**:
```bash
/home/canadaofbin/hermes-venv/bin/python -X utf8 -c "import asyncio; from pathlib import Path; from pipeline.studio.instagram_uploader import upload_instagram_reel_cdp; p=Path('BCI_Shorts_Channel/projects/v8_ep06_bedtime_todo_list_sleep/06_publish/multi_platform_bundle'); print(asyncio.run(upload_instagram_reel_cdp(video_path=p/'video_clean.mp4', cover_path=p/'cover_9x16.png', caption=(p/'reels_caption.txt').read_text(encoding='utf-8'), handle='allaboutbrain.official', receipt_path=p.parent/'instagram_upload_receipt.json')))"
```
5. **tiktok — `UPLOAD_TIKTOK` (`v8_ep06_bedtime_todo_list_sleep`)**:
```bash
/home/canadaofbin/hermes-venv/bin/python -X utf8 -c "import asyncio; from pathlib import Path; from pipeline.studio.tiktok_uploader import upload_tiktok_video_cdp; p=Path('BCI_Shorts_Channel/projects/v8_ep06_bedtime_todo_list_sleep/06_publish/multi_platform_bundle'); print(asyncio.run(upload_tiktok_video_cdp(video_path=p/'video_clean.mp4', cover_path=p/'cover_9x16.png', caption=(p/'tiktok_caption.txt').read_text(encoding='utf-8'), receipt_path=p.parent/'tiktok_upload_receipt.json')))"
```
6. **instagram — `PUBLISH_IG_CARDS` (`v8_ep08_capgras_imposter_delusion_r77`)**:
```bash
# Publish 4:5 (1080x1350) 6-slide carousel in BCI_Shorts_Channel/projects/v8_ep08_capgras_imposter_delusion_r77/06_publish/ig_carousel/
```

## 7. Blocked / Non-Ready Inventory (Excluded to Prevent Penalty)

- `v8_ep09_maguire_london_taxi_hippocampus_r82`: r85_rebuild_hold (internal_ab_or_render_test), dynamic_episode_qa_not_passed, reference_image_qa_not_passed, r85_rebuild_required_r82_r84_held, awaiting_r85_ceo_verification
- `v8_ep10_sleep_pill_brain_wash`: dynamic_episode_qa_not_passed, prosody_qa_not_passed, r85_rebuild_required_r82_r84_held, awaiting_r85_ceo_verification
- `v8_ep11_open_label_placebo_pain`: dynamic_episode_qa_not_passed, r85_rebuild_required_r82_r84_held, awaiting_r85_ceo_verification
- `v8_ep12_doorway_effect_memory`: prosody_qa_not_passed, r85_rebuild_required_r82_r84_held, awaiting_r85_ceo_verification

## 8. Evidence & QA/Verify Receipts (R83-5~7 / R85)

- **Input Metrics Report**: `/home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/BCI_Shorts_Channel/reports/daily/2026-11-18_studio_metrics.json`
- **KPI Snapshot (Parsed Only)**: Subs `61`, 48h Views `84`, 3s Hook `73.1%`, APV `69.1%`, US `64.4%`, Shorts Feed `89.3%`
- **`v8_ep06_bedtime_todo_list_sleep`** [READY | CEO Verify PENDING/MISSING]: `manifest`=`/home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/BCI_Shorts_Channel/projects/v8_ep06_bedtime_todo_list_sleep/00_project_manifest.json`, `video_autopsy`=`/home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/BCI_Shorts_Channel/projects/v8_ep06_bedtime_todo_list_sleep/05_assembly/video_autopsy_report.json`, `dynamic_episode_qa`=`/home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/BCI_Shorts_Channel/projects/v8_ep06_bedtime_todo_list_sleep/05_assembly/dynamic_episode_qa_report.json`, `posthoc_semantic_qa`=`/home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/BCI_Shorts_Channel/projects/v8_ep06_bedtime_todo_list_sleep/05_assembly/posthoc_semantic_qa_report.json`, `posthoc_semantic_review`=`/home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/BCI_Shorts_Channel/projects/v8_ep06_bedtime_todo_list_sleep/05_assembly/posthoc_semantic_review.json`
- **`v8_ep07_harvard_reversible_choice_paradox`** [READY | CEO Verify PENDING/MISSING]: `manifest`=`/home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/BCI_Shorts_Channel/projects/v8_ep07_harvard_reversible_choice_paradox/00_project_manifest.json`, `video_autopsy`=`/home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/BCI_Shorts_Channel/projects/v8_ep07_harvard_reversible_choice_paradox/05_assembly/video_autopsy_report.json`, `dynamic_episode_qa`=`/home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/BCI_Shorts_Channel/projects/v8_ep07_harvard_reversible_choice_paradox/05_assembly/dynamic_episode_qa_report.json`, `posthoc_semantic_qa`=`/home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/BCI_Shorts_Channel/projects/v8_ep07_harvard_reversible_choice_paradox/05_assembly/posthoc_semantic_qa_report.json`, `posthoc_semantic_review`=`/home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/BCI_Shorts_Channel/projects/v8_ep07_harvard_reversible_choice_paradox/05_assembly/posthoc_semantic_review.json`
- **`v8_ep09_maguire_london_taxi_hippocampus_r82`** [HOLD: r85_rebuild_hold (internal_ab_or_render_test), dynamic_episode_qa_not_passed, reference_image_qa_not_passed, r85_rebuild_required_r82_r84_held, awaiting_r85_ceo_verification | CEO Verify PENDING/MISSING]: `manifest`=`/home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/BCI_Shorts_Channel/projects/v8_ep09_maguire_london_taxi_hippocampus_r82/00_project_manifest.json`, `video_autopsy`=`/home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/BCI_Shorts_Channel/projects/v8_ep09_maguire_london_taxi_hippocampus_r82/05_assembly/video_autopsy_report.json`, `dynamic_episode_qa`=`/home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/BCI_Shorts_Channel/projects/v8_ep09_maguire_london_taxi_hippocampus_r82/05_assembly/dynamic_episode_qa_report.json`, `posthoc_semantic_qa`=`/home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/BCI_Shorts_Channel/projects/v8_ep09_maguire_london_taxi_hippocampus_r82/05_assembly/posthoc_semantic_qa_report.json`, `posthoc_semantic_review`=`/home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/BCI_Shorts_Channel/projects/v8_ep09_maguire_london_taxi_hippocampus_r82/05_assembly/posthoc_semantic_review.json`
- **`v8_ep10_sleep_pill_brain_wash`** [HOLD: dynamic_episode_qa_not_passed, prosody_qa_not_passed, r85_rebuild_required_r82_r84_held, awaiting_r85_ceo_verification | CEO Verify PENDING/MISSING]: `manifest`=`/home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/BCI_Shorts_Channel/projects/v8_ep10_sleep_pill_brain_wash/00_project_manifest.json`, `video_autopsy`=`/home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/BCI_Shorts_Channel/projects/v8_ep10_sleep_pill_brain_wash/05_assembly/video_autopsy_report.json`, `dynamic_episode_qa`=`/home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/BCI_Shorts_Channel/projects/v8_ep10_sleep_pill_brain_wash/05_assembly/dynamic_episode_qa_report.json`, `posthoc_semantic_qa`=`/home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/BCI_Shorts_Channel/projects/v8_ep10_sleep_pill_brain_wash/05_assembly/posthoc_semantic_qa_report.json`, `posthoc_semantic_review`=`/home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/BCI_Shorts_Channel/projects/v8_ep10_sleep_pill_brain_wash/05_assembly/posthoc_semantic_review.json`
- **`v8_ep11_open_label_placebo_pain`** [HOLD: dynamic_episode_qa_not_passed, r85_rebuild_required_r82_r84_held, awaiting_r85_ceo_verification | CEO Verify PENDING/MISSING]: `manifest`=`/home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/BCI_Shorts_Channel/projects/v8_ep11_open_label_placebo_pain/00_project_manifest.json`, `video_autopsy`=`/home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/BCI_Shorts_Channel/projects/v8_ep11_open_label_placebo_pain/05_assembly/video_autopsy_report.json`, `dynamic_episode_qa`=`/home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/BCI_Shorts_Channel/projects/v8_ep11_open_label_placebo_pain/05_assembly/dynamic_episode_qa_report.json`, `posthoc_semantic_qa`=`/home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/BCI_Shorts_Channel/projects/v8_ep11_open_label_placebo_pain/05_assembly/posthoc_semantic_qa_report.json`, `posthoc_semantic_review`=`/home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/BCI_Shorts_Channel/projects/v8_ep11_open_label_placebo_pain/05_assembly/posthoc_semantic_review.json`
- **`v8_ep12_doorway_effect_memory`** [HOLD: prosody_qa_not_passed, r85_rebuild_required_r82_r84_held, awaiting_r85_ceo_verification | CEO Verify PENDING/MISSING]: `manifest`=`/home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/BCI_Shorts_Channel/projects/v8_ep12_doorway_effect_memory/00_project_manifest.json`, `video_autopsy`=`/home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/BCI_Shorts_Channel/projects/v8_ep12_doorway_effect_memory/05_assembly/video_autopsy_report.json`, `dynamic_episode_qa`=`/home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/BCI_Shorts_Channel/projects/v8_ep12_doorway_effect_memory/05_assembly/dynamic_episode_qa_report.json`, `posthoc_semantic_qa`=`/home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/BCI_Shorts_Channel/projects/v8_ep12_doorway_effect_memory/05_assembly/posthoc_semantic_qa_report.json`, `posthoc_semantic_review`=`/home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/BCI_Shorts_Channel/projects/v8_ep12_doorway_effect_memory/05_assembly/posthoc_semantic_review.json`
