# ALL ABOUT BRAIN — YouTube Studio Daily Analytics & Growth Report Master Prompt & Fixed Template (Normalized 5-Section Schema)

- **Channel**: ALL ABOUT BRAIN (`@AllAboutBrainOfficial` / `UC4FeioYYv9X04Di07_MfZ7g`)
- **CLI Execution**: `python -X utf8 main.py studio-report`
- **Output Directory**: `BCI_Shorts_Channel/reports/daily/`
  - Markdown Report: `YYYY-MM-DD_daily_studio_report.md`
  - Visual Dashboard PNG: `YYYY-MM-DD_studio_charts.png`
  - Raw Metrics JSON: `YYYY-MM-DD_studio_metrics.json`
- **Latest Report Pointer**: `BCI_Shorts_Channel/reports/LATEST_DAILY_REPORT.md`

---

## PART 1. Daily Execution Master Prompt (Normalized 5-Section Channel-Level Traffic-Light Schema)

```markdown
# [MASTER PROMPT] ALL ABOUT BRAIN — YouTube Studio Channel-Level Daily Growth Report (Normalized 5-Section)

You are the lead analytics & pipeline orchestrator for ALL ABOUT BRAIN (@AllAboutBrainOfficial, channel ID: UC4FeioYYv9X04Di07_MfZ7g).
Using the visible Naver Whale browser (CDP port 9222) and local pipeline receipts, generate the Normalized 5-Section channel-level traffic-light daily report (`🟢` / `🟡` / `🔴` + pure numeric deltas/gaps, zero individual video tables) and standalone section PNG charts.

## Normalized 5-Section Structure
- **Section 0**: `🚦 0. Executive Growth Pulse` — Overall traffic-light status, 7d pulse banner, 5-axis summary table, and top priority action.
- **Section 1**: `1. Channel Volume & Exposure Funnel (Shown in feed → Viewed → Engaged Views)` — `sec1_channel_growth.png` + W-1 / D-3 / D-1 / D-0 horizon deltas.
- **Section 2**: `2. Retention & Cohort Quartile Drop-Off (Q1–Q4 & ΔQ)` — `sec2_video_retention_performance.png` + All vs Recent 3 vs Latest retention & Q1→Q2 / Q2→Q3 / Q3→Q4 drop-off.
- **Section 3**: `3. High-Signal Traffic & Tier-1 Audience Share` — `sec3_traffic_audience_growth.png` + Shorts Feed share and US / Tier-1 English share.
- **Section 4**: `4. Queue & Operations Health (Seed Velocity, Related Video & 5-Gear Calibration)` — `sec4_schedule_inventory.png` + Time-to-Seed, Unlisted (Staged) / Scheduled queue health, Related Video ring, and 5-Gear numeric calibration.
- **Section 5**: `5. 7-Day Target Roadmap & 🔐 Provenance` — Next 7-day numeric targets and cryptographic SHA-256 provenance receipt (Rule R19 independent conclusion ending).
```
