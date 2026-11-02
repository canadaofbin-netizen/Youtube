---
name: report_youtube
description: Triggers when the user uses `/report_youtube`. Generates the channel-level, numbers-first ALL ABOUT BRAIN Daily YouTube Studio Traffic-Light Growth Report (🟢/🟡/🔴 + pure numeric deltas/gaps, zero individual video tables) and standalone channel-level PNG charts.
---

# `/report_youtube` — Channel-Level Numbers-First Traffic-Light Daily Report

Master: [AGENTS.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/AGENTS.md) · Rule: [youtube_studio_operations.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/youtube_studio_operations.md) · Template: [DAILY_REPORT_MASTER_PROMPT.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/BCI_Shorts_Channel/reports/DAILY_REPORT_MASTER_PROMPT.md)

---

## 1. Triggers, Execution & 1-Per-Day Artifact Idempotency
| Trigger | Command |
|---|---|
| `/report_youtube` | `/home/canadaofbin/hermes-venv/bin/python -X utf8 main.py studio-report` (live Whale + local receipts) |
| `/report_youtube YYYY-MM-DD` | `/home/canadaofbin/hermes-venv/bin/python -X utf8 main.py studio-report --date YYYY-MM-DD` |
| compare to a given day | add `--compare-date YYYY-MM-DD` |
| `/report_youtube --offline` | `/home/canadaofbin/hermes-venv/bin/python -X utf8 main.py studio-report --dry-run` (no browser) |

Run from `/home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube`. Always invoke `/home/canadaofbin/hermes-venv/bin/python3 -m pipeline.cli studio-report` (valid flags: `--date YYYY-MM-DD`, `--compare-date YYYY-MM-DD`, `--dry-run`, `--cdp-port 9222`; do not pass unsupported flags like `--period`, `--skip-collect`, or `--sync-wiki`, and set `timeout=600` for live CDP runs since full multi-video DOM scraping takes 3–4 minutes). Entry point: `StudioAnalyticsReporter.generate_daily_report(report_date=..., compare_date=..., dry_run=False)` in `pipeline.studio.studio_reporter`.

> **Pitfall (Channel-Level Only & Numbers-First Traffic Lights)**: Do not include individual video tables (`psych_01`, `psych_02`, etc.) or per-video schedule lists. Never write verbose labels like `"우수 (주력 엔진 안착)"` — pair `🟢` / `🟡` / `🔴` strictly with intuitive numbers (`🟢 +6.5%`, `🟡 -2.0%p (목표 70%)`, `🔴 -83.4%`).
> **Pitfall (Verify `data_source_mode == "LIVE_CDP_DOM"` & Clear Stale Harvest Lock)**: Beforerunning `studio-report`, remove any zero-byte `BCI_Shorts_Channel/.flow_download_harvest.lock` leftover when no harvest process is active so the report does not flag a false lock warning. After generation, verify `"data_source_mode": "LIVE_CDP_DOM"` in `YYYY-MM-DD_studio_metrics.json` — if a transient CDP hiccup caused a fallback to `PUBLIC_WATCH_PAGE_PROBED` or `LOCAL_SNAPSHOT_BASELINE`, re-run `studio-report` against active CDP port `9222` so channel-level analytics (`Shown in feed`, `Engaged views`, `APV %`, `US/Tier-1 share`) reflect live Studio DOM metrics.
> **Pitfall (Multi-Location Skill Sync)**: Whenever updating `report_youtube/SKILL.md`, keep all three copies synchronized (`/home/canadaofbin/.hermes/skills/youtube-pipeline/report_youtube/SKILL.md`, `/home/canadaofbin/.hermes/profiles/yt-studio/skills/youtube-pipeline/report_youtube/SKILL.md`, and `/home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/skills/report_youtube/SKILL.md`).

### Mandatory Outputs & Dual Daily Artifact Rule (`Overwrite=True`)
1. **Workspace Channel Executive Report**: `BCI_Shorts_Channel/reports/daily/YYYY-MM-DD_daily_studio_report.md` (+ `LATEST_DAILY_REPORT.md`)
2. **Workspace Per-Video Detail Report**: `BCI_Shorts_Channel/reports/daily/YYYY-MM-DD_video_detail_report.md` (+ `LATEST_VIDEO_DETAIL_REPORT.md`)
3. **Channel & Per-Video PNG Charts**:
   - Channel: `BCI_Shorts_Channel/reports/daily/YYYY-MM-DD_studio_charts.png` (+ `LATEST_STUDIO_CHARTS.png`) and standalone section charts `YYYY-MM-DD_sec1_channel_growth.png` .. `YYYY-MM-DD_sec4_schedule_inventory.png`
   - Per-Video: `BCI_Shorts_Channel/reports/daily/YYYY-MM-DD_video_detail_charts.png` (+ `LATEST_VIDEO_DETAIL_CHARTS.png`)
4. **Raw Metrics Snapshot JSON**: `BCI_Shorts_Channel/reports/daily/YYYY-MM-DD_studio_metrics.json`
5. **Dual Daily Conversation Artifacts (`매일 아침 두 보고서만 제공 원칙`)**:
   - Copy generated PNG charts into the active conversation artifact directory.
   - Write/update **both** artifacts with `Overwrite=True`:
     1. `youtube_daily_report_YYYY_MM_DD.md` (채널 종합 보고서)
     2. `youtube_video_detail_report_YYYY_MM_DD.md` (개별 영상 세부 보고서)
   - When reporting to the user every morning, present **ONLY** these two report links concisely without extra file clutter.

---

## 2. Channel-Level 5-Section Schema (Zero-Redundancy & High-Precision Pipeline Feedback)
| # | Section | Content (Whole-Channel Metrics + Pure Numeric Traffic Lights) |
|---|---|---|
| 0 | `🚦 0. 오늘의 채널 종합 진단 (Executive Health Summary)` | At-a-glance overall traffic-light verdict (`🟢 순항 중 / 🟡 점검 필요 / 🔴 경고`), 1-line `🚦 0. Executive Growth Pulse (7d)` banner, 5-axis traffic-light summary table (`① 조회·구독 성장`, `② 초반 3초 훅`, `③ 끝까지 시청률`, `④ 북미·피드 타겟`, `⑤ 시드·예약 큐`), and 1-line top priority action |
| 1 | `채널 볼륨 & 피드 노출 퍼널 스코어보드 (Shown → Viewed → Engaged)` | `sec1_channel_growth.png` + unified multi-horizon (`W-1 → D-3 → D-1 → D-0`, `1d Δ`, `7d Δ`) table separating **① Shown in feed**, **② Views (Viewed)**, **③ Engaged Views**, Watch Hours, Subscribers (`/1K`), Realtime 48h/60m |
| 2 | `채널 시청률 & 최근 코호트 분리 · 구간별 낙폭(ΔQ) 분석` | `sec2_video_retention_performance.png` + `Viewed %` (redundant `Swiped %` removed), `AVD`, `APV %`, `Q1~Q4` comparing **Channel Cumulative (`All`) vs Recent 3 Cohort (`Recent 3`) vs Latest** + explicit **Inter-Quartile Drop-Off (`ΔQ` & bottleneck clip range)** |
| 3 | `데일리 핵심 유입원 & 북미/Tier-1 타겟 비중 (High-Signal Snapshot)` | `sec3_traffic_audience_growth.png` + **Shorts Feed Share (%)** and **US / Tier-1 English Share (%)** only (lagged 28d search term tail and age brackets deferred to Weekly report) |
| 4 | `인벤토리 · 시드 타이밍 트래커 (Seed & Queue) & 파이프라인 반영안` | **4-1**: `Seed & Queue Mini-Tracker` (Staged/Scheduled counts + latest 3 cohorts' elapsed hours, `Shown → Views`, `Time-to-Seed`, `Related Video` bridge, `72h Z-Test`) · **4-2**: `sec4_schedule_inventory.png` + bottleneck root cause & 5-Gear numeric calibration |
| 5 | `향후 채널 성장 방향 & 주간(7일) 목표 로드맵` | Current cumulative/cohort numbers vs. next 7-day numeric targets across Exposure Funnel/Seed Velocity, Retention/`ΔQ`, and US/Tier-1 Market + `🔐 Provenance` |
