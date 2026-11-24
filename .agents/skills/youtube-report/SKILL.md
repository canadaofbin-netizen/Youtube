---
name: youtube-report
description: Channel-level numbers-first ALL ABOUT BRAIN Daily YouTube Studio Traffic-Light Growth Report (🟢/🟡/🔴 + numeric deltas) and PNG chart generation.
---

# youtube-report (AI-Only Spec)

SSOT: [AGENTS.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/AGENTS.md) | [youtube_studio_operations.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/youtube_studio_operations.md) | Template: [DAILY_REPORT_MASTER_PROMPT.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/BCI_Shorts_Channel/reports/DAILY_REPORT_MASTER_PROMPT.md)

## 1. Execution (`timeout=600` for live CDP DOM scrape)
- Live: `/home/canadaofbin/hermes-venv/bin/python -X utf8 main.py studio-report [--date YYYY-MM-DD] [--compare-date YYYY-MM-DD] [--cdp-port 9222]` (or zero-token headless `scripts/run_daily_ops_headless.sh report`).
- Offline snapshot only: add `--dry-run` (never fabricate missing metrics).
- Post-check: verify `"data_source_mode": "LIVE_CDP_DOM"` in `BCI_Shorts_Channel/reports/daily/YYYY-MM-DD_studio_metrics.json` when CDP `9222` is live (compact KPI chips like `8.5K`/`5.4K` scale to full integers `8500`/`5400`); re-run if transient hiccup fell back to `LOCAL_SNAPSHOT_BASELINE`.

## 2. Formatting & Artifact Rules
- **Numbers-First Traffic Lights**: Pair `🟢` / `🟡` / `🔴` strictly with numbers/deltas (`🟢 +6.5%`, `🟡 -2.0%p (목표 70%)`, `🔴 -83.4%`); zero prose adjectives or per-video tables in the channel summary.
- **Outputs in `BCI_Shorts_Channel/reports/`**:
  - `daily/YYYY-MM-DD_daily_studio_report.md` + `LATEST_DAILY_REPORT.md` (6-part schema: `0. 종합 진단`, `1. Shown->Viewed->Engaged 퍼널`, `2. 시청률·코호트·ΔQ`, `3. 피드·북미 비중`, `4. 시드·큐·5-Gear 보정`, `5. 7일 목표 로드맵`)
  - `daily/YYYY-MM-DD_video_detail_report.md` + `LATEST_VIDEO_DETAIL_REPORT.md`
  - `daily/YYYY-MM-DD_studio_charts.png` (`LATEST_STUDIO_CHARTS.png`), `sec1..sec4_*.png`, `YYYY-MM-DD_video_detail_charts.png` (`LATEST_VIDEO_DETAIL_CHARTS.png`)
- **Fresh-Room Auto-Archive**: When run interactively, write `youtube_daily_report_YYYY_MM_DD.md` + `youtube_video_detail_report_YYYY_MM_DD.md` (`Overwrite=True`) in `<appDataDir>/brain/<conversation-id>/` and emit charts via `MEDIA:/abs/path/to/chart.png`; `.agents/hooks.json` (`scripts/sync_archive.py`) mirrors `<2 MiB` artifacts into `artifacts_archive/` and updates `artifacts_archive/INDEX.md`.
