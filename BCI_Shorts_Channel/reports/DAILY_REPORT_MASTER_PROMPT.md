# ALL ABOUT BRAIN — Channel-Level Numbers-First Traffic-Light Daily Report Master Prompt & Template

- **Channel**: ALL ABOUT BRAIN (`@AllAboutBrainOfficial` / `UC4FeioYYv9X04Di07_MfZ7g`)
- **CLI Execution**: `/home/canadaofbin/hermes-venv/bin/python -X utf8 main.py studio-report`
- **Output Directory**: `BCI_Shorts_Channel/reports/daily/`
  - Markdown Report: `YYYY-MM-DD_daily_studio_report.md`
  - 4-Panel Visual Dashboard PNG: `YYYY-MM-DD_studio_charts.png`
  - Per-Section Standalone PNG Charts: `YYYY-MM-DD_sec1_channel_growth.png` .. `YYYY-MM-DD_sec4_schedule_inventory.png`
  - Raw Metrics JSON: `YYYY-MM-DD_studio_metrics.json`
- **Latest Report Pointer**: `BCI_Shorts_Channel/reports/LATEST_DAILY_REPORT.md`

---

## 1. Core Principles (Channel-Level Only, Numbers + Traffic Light Only)
- **Zero Individual Video Tables / Schedule Lists**: Do not list individual videos (`psych_01`, `psych_02`, etc.) or per-video schedule queues. All metrics, charts, and diagnostics represent **whole-channel growth and funnel health**.
- **Zero Verbose Grade Words**: Never write wordy labels like `"우수 (주력 엔진 안착)"` or `"주의 (TUNE)"`. Every status cell uses ONLY the traffic light dot (`🟢` / `🟡` / `🔴`) + pure numeric delta or target gap (e.g., `🟢 +6.5%`, `🟡 -2.0%p (목표 70%)`, `🔴 -83.4%`).

---

## 2. Normalized 5-Section Structure
- **0. `🚦 0. 채널 성장 스코어보드 (Channel Growth Pulse)`**:
  - Top-level table showing `구독자 수`, `누적 조회수`, `누적 시청 시간`, `3초 훅 생존율 (Viewed %)`, `평균 시청률 (AVD / APV %)`, `실시간 48h 속도` (`어제` → `오늘` → `전일 대비 DoD Δ` → `7일 누적 성장` → `목표 기준` → `신호 (목표 대비)`).
- **Section 1 — `채널 외형 성장 추이 (Views · Watch Time · Subscribers)` (`sec1_channel_growth.png`)**:
  - 7-day and DoD numeric progression of total views, realtime 48h/60m views, watch hours, unique viewers, subscribers (`명/1K views`), and likes/comments.
- **Section 2 — `채널 시청률 & 구간별 리텐션 추이 (Hook · APV · Q1~Q4)` (`sec2_video_retention_performance.png`)**:
  - Channel-wide `Viewed %`, `Swiped %`, `AVD (초)`, `APV (%)`, and `Q1 (0–25%) ~ Q4 (75–100%)` retention vs. target gates.
- **Section 3 — `채널 유입 엔진 & 타겟 오디언스 지표 (Traffic · Geo · Age)` (`sec3_traffic_audience_growth.png`)**:
  - Channel-wide `Shorts Feed (%)`, `YouTube Search (%)`, `US (%)`, `Tier-1 (%)`, `Age 35+ (%)` + top 5 search queries.
- **Section 4 — `채널 정체/문제 구간 진단 (Bottlenecks & Fixes)` (`sec4_schedule_inventory.png`)**:
  - Identifies stagnant/bottleneck metrics with exact numbers, root causes, and concrete pipeline rule adjustments.
- **Section 5 — `향후 채널 성장 방향 & 7일 목표 수치 (Growth Roadmap)`**:
  - Current channel numbers vs. next 7-day numeric targets across Scale, Watch Rate, and Target Audience + `🔐 Provenance`.
