---
name: report_youtube
description: Triggers when the user uses `/report_youtube`. Generates the standardized 9-section ALL ABOUT BRAIN Daily YouTube Studio Analytics & Growth Report with duration-proportional retention quartiles, Section 6-2 per-video notable change & root-cause analysis, Section 8-3 7-Risk Compliance Audit Matrix, Section 9-1/9-2/9-3 Success vs. Failure/Risk Signal Detection & Amplification Playbook, a 6-panel dashboard PNG and inline Mermaid xychart-beta graphs, using the visible Naver Whale window (CDP) and local pipeline receipts.
---

# `/report_youtube` — Daily YouTube Studio Analytics & Growth Report

Master: [AGENTS.md](file:///g:/My%20Drive/Kyubin_Yun_Workspace/07_Youtube/.agents/AGENTS.md) · Rule: [youtube_studio_operations.md](file:///g:/My%20Drive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/youtube_studio_operations.md) · Template: [DAILY_REPORT_MASTER_PROMPT.md](file:///g:/My%20Drive/Kyubin_Yun_Workspace/07_Youtube/BCI_Shorts_Channel/reports/DAILY_REPORT_MASTER_PROMPT.md)

---

## 1. Triggers, Execution & 1-Per-Day Artifact Idempotency
| Trigger | Command |
|---|---|
| `/report_youtube` | `python -X utf8 main.py studio-report` (live Whale + local receipts) |
| `/report_youtube YYYY-MM-DD` | `python -X utf8 main.py studio-report --date YYYY-MM-DD` |
| compare to a given day | add `--compare-date YYYY-MM-DD` |
| `/report_youtube --offline` | `python -X utf8 main.py studio-report --dry-run` (no browser) |

Run from `g:\My Drive\Kyubin_Yun_Workspace\07_Youtube`. Entry point: [`StudioAnalyticsReporter.generate_daily_report`](file:///g:/My%20Drive/Kyubin_Yun_Workspace/07_Youtube/pipeline/studio/reporter.py#L2958-L3016).

### Mandatory Outputs & Single Daily Artifact Rule (`Overwrite=True`)
1. **Workspace Dated Report**: `BCI_Shorts_Channel/reports/daily/YYYY-MM-DD_daily_studio_report.md`
2. **Latest Report Pointer**: `BCI_Shorts_Channel/reports/LATEST_DAILY_REPORT.md`
3. **6-Panel Visual Dashboard PNG**: `BCI_Shorts_Channel/reports/daily/YYYY-MM-DD_studio_charts.png` (+ copy `LATEST_STUDIO_CHARTS.png`)
4. **Raw Metrics Snapshot JSON**: `BCI_Shorts_Channel/reports/daily/YYYY-MM-DD_studio_metrics.json`
5. **Single Daily Conversation Artifact (`1일 1개 아티팩트 원칙`)**:
   - Copy `YYYY-MM-DD_studio_charts.png` into the active conversation artifact directory and write/update `YYYY-MM-DD_youtube_daily_report.md` with `Overwrite=True` so re-runs on the same `YYYY-MM-DD` (US ET) update the single daily report artifact in place without creating duplicates.

---

## 2. Invariant 9-Section Schema (+ Section 6-2 Notable Video Shifts, Section 8-3 Risk Audit & Section 9 Signal Amplification)
| # | Section | Content |
|---|---|---|
| Header | Channel Status & 6-Panel Dashboard | ET/KST timestamp, `data_source_mode` (`LIVE_CDP_DOM` vs `LOCAL_SNAPSHOT_BASELINE`), Published / Scheduled / Unlisted / Quarantined inventory counts, embedded `YYYY-MM-DD_studio_charts.png` |
| 1 | Executive Growth Summary | headline (dynamic `/ {avg_video_length_sec}초` denominator), Top 3 improvements, Top 2 bottlenecks, **Notable Video Shifts summary (`🔎 특정 영상 주목할 변화 요약`)**, **Signal Radar summary (`📡 성공 vs. 실패·위험 시그널 감지`)**, **Amplification Playbook summary (`🔥 성공 시그널 증폭 전략 요약`)**, Top 3 action items |
| 2 | Channel Overview & 7-Day Growth Trend | subscribers, 24h views, watch time (h), realtime 48h/60m velocity, unique viewers, revenue; DoD Δ; `[그래프 2-1]` 7-day Mermaid `xychart-beta` |
| 3 | Shorts Algorithm Signals & Retention Curve Anatomy | AVD (`/ {avg_video_length_sec}초`), APV, Viewed vs Swiped Away, Impressions, CTR, Like ratio; **`[표 3-1]` Duration-Proportional Retention Quartiles (`Q1–Q4`)** + `[그래프 3-1]` retention curve + `[그래프 3-2]` per-video APV vs Viewed `xychart-beta` |
| 4 | Traffic Sources & Search Terms | Shorts feed, YouTube search, browse, suggested, channel page, external with Unicode gauge bars (`████████░░░░`) + Top 5 search queries |
| 5 | Audience Geography & Demographics | Rule R36 Tier-1 English share (`US + UK + CA + AU`), `[그래프 5-1]` geography `xychart-beta`, returning/new, subscribed/non-subscribed, gender/age, US ET peak window alignment |
| 6 | Per-Video Performance & Notable Change Root-Cause Analysis | **6-1**: all published Shorts ranked with `views` (`0 (DOM 미수집)` isolation for unscraped videos), `AVD / duration`, `APV`, `Viewed / Swiped`, `Q1 / Q2 / Q3 / Q4` retention, CTR, likes/comments/shares, active thumbnail variant, pinned DOI status<br/>**6-2**: **🔎 Per-Video Notable Change Detection & 3-Axis Root-Cause Attribution (`특정 영상별 눈에 띄는 변화 감지 및 심층 원인 분석`)** — summary matrix + per-video deep-dive cards (`📌 [1]..[N]`) explaining **What Changed** and **Why It Happened** across ① Script/Case Hook (Rule R1/R42), ② Quartile Retention/Visuals (Rule R26/R38/R19), and ③ Traffic/Search/Thumbnail Z-Test/Slot (Rule R30/R32) |
| 7 | 7 Academic Pillars & 5-Slot Matrix | performance across `brain_health`, `bci_tech`, `brain_news`, `brain_basics`, `brain_mysteries`, `brain_history`, `bci_ethics` |
| 8 | 72h Thumbnail A/B/C Z-Test, 5-Slot Queue & Risk Audit | **8-1**: A/B/C Z-Test table + `[그래프 8-1]` CTR `xychart-beta`<br/>**8-2**: Today & Tomorrow 5-Slot schedule (`date >= report_date`) with distinct `✅ Published`, `⏰ Scheduled`, `🔒 Unlisted (Staged)`, `⚠️ Vacant` badges<br/>**8-3**: **🚨 7-Point Channel & Pipeline Risk & Compliance Audit Matrix** (`RISK-1` Data Provenance, `RISK-2` Schedule Vacuum, `RISK-3` Queue Filtering & Badges, `RISK-4` Rule R30-B `>= 4.0h` Seed Protection & Timetable Drift, `RISK-5` Quarantine & Harvest Lock, `RISK-6` Contract v4 R42/R43/R19 Alignment, `RISK-7` Rule R32 `24h` vs `72h` Rotation & R35 DOI Pin) |
| 9 | Deep-Dive Diagnostics, Signal Radar, Amplification Playbook & Provenance | **9-1**: What Improved & Why + **`[표 9-1]` 🟢 Success Signals Early Detection Matrix (`SIG-WIN-1..5`)**<br/>**9-2**: Quartile Drop-Off Autopsy + **`[표 9-2]` 🔴 Failure & Risk Signals Early Detection Matrix (`SIG-FAIL-1..5`)**<br/>**9-3**: Next 24h Prescriptions + **`[표 9-3]` 🚀 5-Gear Success Signal Amplification Playbook (`AMP-1..5`)**<br/>**9-4**: **🔐 Raw Snapshot & Provenance** (JSON path, `data_source_mode`, Whale CDP session state, `provenance_sha256`) |

---

## 3. Retention Quartiles (Section 3, Rule R42)
Videos run from `FINAL_SHORTS_DURATION_MIN_SEC` to `FINAL_SHORTS_DURATION_MAX_SEC`, so fixed-second checkpoints are invalid. Sample retention at **0 %, 25 %, 50 %, 75 %, 100 %** of each video's own duration and label quartiles by role phase (R42):

| Quartile | Role phase | Diagnostic question |
|---|---|---|
| Q1 (0–25 %) | setup → symptom | Does the case hook hold viewers? |
| Q2 (25–50 %) | failure → crisis → pivot | Does the crisis build into the "Instead of" pivot? |
| Q3 (50–75 %) | mechanism steps | Is the brain-interior explanation clear enough to keep watching? |
| Q4 (75–100 %) | breakthrough → conclusion | Do viewers stay through the proof and the conclusion? |

Report each quartile's drop vs the previous snapshot (DoD Δ) with a status badge; compare videos only by quartile, never by absolute second. No hook-without-sound or loop-replay segments — both formats are retired in favor of **Rule R19 Independent Conclusion Ending**.

---

## 4. Per-Video Notable Change Attribution (Section 6-2) & Signal Amplification (Section 9-1..9-3)
1. **Per-Video Notable Change & Root-Cause Attribution (`notable_video_changes` / Section 6-2)**:
   - Classify each video cohort (`BREAKOUT_SURGE`, `HIGH_VELOCITY_SEED`, `HOOK_AND_DURATION_BOTTLENECK`, `COHORT_DOM_PENDING_ISOLATION`).
   - Attribute **why** the change occurred across 3 causal axes using actual project artifacts (`01_ideation/research_card.json`, `02_script/script.json`, `05_assembly/probe_report.json`, `06_publish/ab_test_manifest.json`):
     - **Axis 1 (Script & Case Hook)**: clip/word budget, duration, protagonist, brain regions, first-sentence hook vs. `Q1` Swiped Away.
     - **Axis 2 (Quartile Retention & Visuals)**: `Q1 → Q2` `"Instead of"` pivot rebound (`+pp`), `Q3` brain-interior mechanism hold, `Q4` Rule R19 independent conclusion completion.
     - **Axis 3 (Traffic, Search, Thumbnail Z-Test & Slot)**: top search query matching, Variant A/B/C CTR Z-score (`p < 0.05`), US ET slot timing.
2. **Success vs. Failure/Risk Signal Detection & Amplification (`signal_radar` / Section 9-1..9-3)**:
   - Detect **5 Success Signals (`SIG-WIN-1..5`)** and **5 Failure/Risk Signals (`SIG-FAIL-1..5`)** with explicit metric evidence and threshold gates.
   - Pair every winning signal with an actionable **5-Gear Amplification Strategy (`AMP-1..5`)**: Variant C immediate lock & pre-seeding (`AMP-1`), `75s+` 10-clip full spine & `Q2 "Instead of"` pivot replication (`AMP-2`), evergreen neuroscience search cluster expansion (`AMP-3`), pinned DOI comment cross-linking for `APV 97%` binge loops (`AMP-4`), and North American peak slot (`Slot 1·2·4`) prioritization for top pillars (`AMP-5`).

