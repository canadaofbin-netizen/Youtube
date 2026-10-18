# ALL ABOUT BRAIN — YouTube Studio Daily Analytics & Growth Report Master Prompt & Fixed Template (With Visual Graphs)

- **Channel**: ALL ABOUT BRAIN (`@AllAboutBrainOfficial` / `UC4FeioYYv9X04Di07_MfZ7g`)
- **CLI Execution**: `python -X utf8 main.py studio-report`
- **Output Directory**: `BCI_Shorts_Channel/reports/daily/`
  - Markdown Report: `YYYY-MM-DD_daily_studio_report.md`
  - Visual Dashboard PNG: `YYYY-MM-DD_studio_charts.png`
  - Raw Metrics JSON: `YYYY-MM-DD_studio_metrics.json`
- **Latest Report Pointer**: `BCI_Shorts_Channel/reports/LATEST_DAILY_REPORT.md`

---

## PART 1. Daily Execution Master Prompt (복사/스케줄러 실행용 프롬프트 원문)

```markdown
# [MASTER PROMPT] ALL ABOUT BRAIN — YouTube Studio 전 지표 일일 성장 리포트 & 시각화 그래프 생성

당신은 ALL ABOUT BRAIN (@AllAboutBrainOfficial, 채널 ID: UC4FeioYYv9X04Di07_MfZ7g) 전담 수석 데이터 애널리스트이자 파이프라인 오케스트레이터입니다.
가시적 네이버 웨일 브라우저(CDP 포트 9222)와 로컬 파이프라인 데이터를 결합하여, YouTube Studio의 **모든 탭과 개별 Shorts 상세 지표**를 전수 조사하고, **고해상도 6-패널 시각 대시보드 그래프 PNG (`YYYY-MM-DD_studio_charts.png`)** 및 **인라인 Mermaid `xychart-beta` 그래프**가 포함된 **[고정 데일리 리포트 템플릿]** 규격에 맞춰 오늘의 일일 보고서를 작성하십시오.

## 1단계: 데이터 수집 범위 (YouTube Studio 전수 추출 — 누락 금지)
1. **채널 대시보드 & 실시간(Realtime) 지표**:
   - 현재 총 구독자 수(명) 및 전일 대비 순증감(Δ)
   - 실시간 48시간 조회수 / 실시간 60분 조회수 및 실시간 상위 영상 Top 5
2. **채널 분석 [개요(Overview)] 탭 (어제 / 최근 7일 일별 추이 / 최근 28일)**:
   - 총 조회수(Views), 총 시청 시간(Watch Time, Hours), 구독자 순증감(Subscribers), 추정 수익(Estimated Revenue)
   - 최근 7일 일별 조회수 및 시청 시간 시계열 데이터
   - 각 지표의 전일(DoD) 변화량(Δ, %) 및 최근 7일 일평균 대비 증감률(%)
3. **채널 분석 [콘텐츠(Content) -> Shorts] 탭**:
   - **핵심 유지율 지표**: 평균 시청 지속 시간(AVD, 초 / 실제 평균 영상 길이 분모) 및 평균 시청률(APV, %)
   - **초반 훅 방어율 (Viewed vs. Swiped Away)**: '시청함(Viewed %)' 대 '스와이프하여 넘김(Swiped Away %)' 비율
   - **영상 길이 비례 4분위 시청 지속률 해부 (Rule R42 Duration-Proportional Quartiles: Q1 0–25%, Q2 25–50%, Q3 50–75%, Q4 75–100%)**
   - **노출 및 클릭 지표**: 총 노출수(Impressions) 및 노출 클릭률(Impressions CTR %)
   - **참여도 지표**: 좋아요(Likes), 좋아요 비율(%), 댓글(Comments), 공유(Shares), 리믹스(Remixes)
   - **트래픽 소스(How viewers find your Shorts) 전수 비율**: Shorts 피드(%), YouTube 검색(%), 탐색 기능(%), 추천 동영상(%), 채널 페이지(%), 외부 유입(%)
   - **상위 검색어(Top YouTube Search Terms)**: 유입 상위 키워드 Top 5~10 및 비중(%)
4. **채널 분석 [시청자층(Audience)] 탭**:
   - 재방문 시청자(Returning Viewers) vs. 신규 시청자(New Viewers) 및 순 시청자수(Unique Viewers)
   - 구독 여부별 시청 시간 비율: 비구독자(Not Subscribed %) vs. 구독자(Subscribed %)
   - **상위 지역(Top Geographies)**: 미국(US), 영국(UK), 캐나다(CA), 호주(AU), 한국(KR) 등 국가별 시청 비중(%) -> Rule R36 (Tier-1 영어권 타겟팅) 정상 작동 여부 판정
   - **연령 및 성별(Age & Gender)**: 성별 비율(%) 및 연령대별(18-24, 25-34, 35-44, 45+) 분포
   - **시청자 활동 시간대(When your viewers are on YouTube)**: 북미 동부(ET) 기준 피크 시간대와 현재 5-Slot 스케줄(07:30, 12:00, 16:00, 19:30, 22:30 ET)의 정합성
5. **개별 Shorts 영상별 전수 성적표 & 특정 영상 변화 심층 원인 분석 (`/videos/short` & 개별 영상 Analytics)**:
   - 공개 완료된 모든 Shorts 영상에 대해 (DOM 미수집 영상은 `0 (DOM 미수집)`으로 엄격 격리):
     - 프로젝트 ID, 영상 제목, Video ID, 소속 학술 필러(7 Pillars), 배정 슬롯(Slot 1~5)
     - 누적 조회수, 24h 조회수 증감(+Δ), 시청 시간(h), 구독자 기여(+명)
     - **AVD (초 / 총 길이)**, **APV (%)**, **4분위 시청 지속률 곡선 (`Q1 / Q2 / Q3 / Q4`)**
     - **Viewed (%) vs. Swiped Away (%)**, 노출수(Impressions), CTR (%), 좋아요/댓글/공유, 썸네일 A/B/C 테스트 Z-Test 유의성, DOI 고정 댓글 상태
   - **섹션 6-2 특정 영상별 눈에 띄는 변화 감지 및 3축 원인 분석**:
     - `BREAKOUT_SURGE`, `HIGH_VELOCITY_SEED`, `HOOK_AND_DURATION_BOTTLENECK`, `COHORT_DOM_PENDING_ISOLATION` 분류 및 ① 대본/사례/훅(Rule R1/R42), ② 4분위 리텐션/비주얼 해부(Rule R26/R38/R19), ③ 트래픽/검색어/썸네일/슬롯(Rule R30/R32) 3축 원인 규명
6. **파이프라인 운영, 7대 위험 진단 매트릭스(섹션 8-3) & 성공/실패 시그널 레이더 및 증폭 플레이북(섹션 9-1~9-3)**:
   - 금일 발행 완료 및 발행 예정 슬롯(Slot 1~5) 상태(`date >= report_date`), 7대 운영/파이프라인 위험 감사(`RISK-1`~`RISK-7`)
   - **성공 시그널 조기 감지(`SIG-WIN-1..5`)**, **실패 및 위험 시그널 조기 감지(`SIG-FAIL-1..5`)**, **5-Gear 성공 시그널 증폭 플레이북(`AMP-1..5`)**

## 2단계: 필수 그래프 & 시각화 생성 규칙 (6-Panel PNG + Inline Mermaid Charts)
보고서에는 반드시 다음 **2종류의 그래프 레이어**를 모두 포함하십시오:
1. **고해상도 6-패널 종합 대시보드 이미지 (`YYYY-MM-DD_studio_charts.png`)**:
   - 패널 1: 최근 7일 일별 조회수(Views) & 성장 추이 그래프
   - 패널 2: 영상 길이 비례 4분위(`Q1~Q4`) Shorts 시청 지속률 곡선 (Audience Retention Curve vs. 85% 목표선)
   - 패널 3: 개별 영상별 평균 시청률(APV %) & Q4 완주율(%) 비교 막대 그래프
   - 패널 4: 개별 영상별 시청 선택(Viewed %) vs. 스와이프 이탈(Swiped Away %) 누적 막대 그래프 (`70%` 훅 기준선 포함)
   - 패널 5: 트래픽 소스 비중(%) & 영미권 Tier-1 국가별 시청 비중(%) 수평 막대 그래프
   - 패널 6: 72시간 썸네일 A/B/C 테스트 변형별 CTR(%) 비교 및 목표선 그래프
2. **인라인 마크다운 Mermaid `xychart-beta` 그래프 및 게이지 바**:
   - 섹션 2: 최근 7일 일별 조회수 추이 `xychart-beta` (Bar + Line)
   - 섹션 3: 영상 길이 비례 4분위(`Q1~Q4`) 시청 지속률 곡선 `xychart-beta` 및 영상별 APV vs. Viewed `xychart-beta`
   - 섹션 4 & 5: 트래픽 소스 및 국가별 비중 텍스트 프로그레스 게이지 바 (`████████░░`) 및 `xychart-beta`
   - 섹션 8: 썸네일 A/B/C CTR 비교 `xychart-beta`

## 3단계: 실행 및 저장 규격
- `python -X utf8 main.py studio-report`를 실행하여 아래 파일을 생성 및 검증하십시오:
  - 원시 데이터 스냅샷: `BCI_Shorts_Channel/reports/daily/YYYY-MM-DD_studio_metrics.json`
  - 6-패널 시각 그래프 PNG: `BCI_Shorts_Channel/reports/daily/YYYY-MM-DD_studio_charts.png`
  - 고정 양식 마크다운 보고서: `BCI_Shorts_Channel/reports/daily/YYYY-MM-DD_daily_studio_report.md`
  - 최신 리포트 사본: `BCI_Shorts_Channel/reports/LATEST_DAILY_REPORT.md`
- 반드시 아래 **[PART 2. 고정 데일리 리포트 마크다운 템플릿]**의 섹션 순서(1~9번), 표 컬럼, 그래프 블록 구조를 단 하나의 변경 없이 그대로 준수하여 출력하십시오.
```

---

## PART 2. 고정 데일리 리포트 마크다운 템플릿 (1~9번 섹션 + 그래프 불변 양식)

````markdown
# 📊 ALL ABOUT BRAIN — YouTube Studio 일일 성장 리포트 ({{REPORT_DATE}})

> **채널**: ALL ABOUT BRAIN (`@AllAboutBrainOfficial` / `UC4FeioYYv9X04Di07_MfZ7g`)
> **집계 기준 시각**: `{{GENERATED_AT_ET}} ET` (`{{GENERATED_AT_KST}} KST`) | **비교 기준일**: `{{PREV_REPORT_DATE}}` | **데이터 출처**: `{{DATA_MODE_BADGE}}`
> **채널 상태 요약**: 공개 영상 `{{PUBLISHED_COUNT}}`편 | 예약 대기(`Scheduled`) `{{SCHEDULED_COUNT}}`편 | 비공개 대기(`Unlisted`) `{{UNLISTED_COUNT}}`편 | 격리(`Quarantined`) `{{QUARANTINE_COUNT}}`편 | 스테이징 버퍼 `{{STAGED_BUFFER_COUNT}}`편 (완성 인벤토리 총 `{{TOTAL_COMPLETED_INVENTORY}}`편)

![ALL ABOUT BRAIN Daily Studio Analytics Dashboard]({{CHARTS_IMAGE_PATH}})

---

## 1. 핵심 요약 및 성장세 한눈에 보기 (Executive Growth Summary)

| 구분 | 핵심 진단 내용 |
| :--- | :--- |
| **🚀 오늘의 핵심 성장세 (Growth Momentum)** | {{EXECUTIVE_GROWTH_HEADLINE}} |
| **✨ 어제보다 나아진 점 (Top Improvements)** | 1. {{IMPROVEMENT_1}}<br/>2. {{IMPROVEMENT_2}}<br/>3. {{IMPROVEMENT_3}} |
| **⚠️ 주요 병목 및 주의 지표 (Key Bottlenecks)** | 1. {{BOTTLENECK_1}}<br/>2. {{BOTTLENECK_2}} |
| **🔎 특정 영상 주목할 변화 요약 (Notable Video Shifts)** | {{EXEC_NOTABLE_SUMMARY}} |
| **📡 성공 vs. 실패·위험 시그널 감지 (Signal Radar)** | {{EXEC_SIGNAL_SUMMARY}} |
| **🔥 성공 시그널 증폭 전략 요약 (Amplification Playbook)** | {{EXEC_AMP_SUMMARY}} |
| **🎯 오늘의 즉시 실행 과제 (Action Items)** | 1. {{ACTION_ITEM_1}}<br/>2. {{ACTION_ITEM_2}}<br/>3. {{ACTION_ITEM_3}} |

---

## 2. 채널 전체 핵심 KPI 및 일별 성장 추이 그래프 (Channel Overview & Growth Trend)

| 핵심 지표 (Metric) | 오늘 (24h / 현재) | 어제 (전일) | 전일 대비 증감 (DoD Δ) | 최근 7일 합계 (일평균) | 최근 28일 합계 | 상태 진단 |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **총 구독자 수 (Subscribers)** | **{{SUBS_TOTAL}}명** | {{SUBS_PREV}}명 | {{SUBS_DOD_DELTA}} | +{{SUBS_7D}}명 ({{SUBS_7D_AVG}}/일) | +{{SUBS_28D}}명 | {{SUBS_STATUS}} |
| **일일 조회수 (Views)** | **{{VIEWS_24H}}회** | {{VIEWS_PREV}}회 | {{VIEWS_DOD_DELTA}} | {{VIEWS_7D}}회 ({{VIEWS_7D_AVG}}/일) | {{VIEWS_28D}}회 | {{VIEWS_STATUS}} |
| **시청 시간 (Watch Time, Hours)** | **{{WATCH_HOURS_24H}}h** | {{WATCH_HOURS_PREV}}h | {{WATCH_HOURS_DOD_DELTA}} | {{WATCH_HOURS_7D}}h ({{WATCH_HOURS_7D_AVG}}h/일) | {{WATCH_HOURS_28D}}h | {{WATCH_STATUS}} |
| **실시간 48시간 조회수 (Realtime 48h)** | **{{REALTIME_48H}}회** | {{REALTIME_48H_PREV}}회 | {{REALTIME_48H_DELTA}} | - | - | {{REALTIME_48H_STATUS}} |
| **실시간 60분 조회수 (Realtime 60m)** | **{{REALTIME_60M}}회** | {{REALTIME_60M_PREV}}회 | {{REALTIME_60M_DELTA}} | - | - | {{REALTIME_60M_STATUS}} |
| **순 시청자수 (Unique Viewers)** | **{{UNIQUE_VIEWERS_24H}}명** | {{UNIQUE_VIEWERS_PREV}}명 | {{UNIQUE_VIEWERS_DELTA}} | {{UNIQUE_VIEWERS_7D}}명 | {{UNIQUE_VIEWERS_28D}}명 | {{UNIQUE_STATUS}} |
| **추정 수익 (Est. Revenue)** | **${{REVENUE_24H}}** | ${{REVENUE_PREV}} | {{REVENUE_DELTA}} | ${{REVENUE_7D}} | ${{REVENUE_28D}} | {{REVENUE_STATUS}} |

### 📈 [그래프 2-1] 최근 7일 일별 조회수(Views) 성장 추이
```mermaid
xychart-beta
    title "Daily Views Growth Trend (Last 7 Days)"
    x-axis [{{TREND_7D_DATES}}]
    y-axis "Views" 0 --> {{TREND_7D_MAX_Y}}
    bar [{{TREND_7D_VIEWS}}]
    line [{{TREND_7D_VIEWS}}]
```

---

## 3. Shorts 알고리즘 핵심 지표 & 영상 길이 비례 4분위 시청 지속률 곡선 (Retention & Hook Quality)

| Shorts 알고리즘 시그널 | 오늘 평균 | 어제 평균 | 전일 대비 (DoD Δ) | 채널 목표 기준 (Target) | 알고리즘 통과 판정 |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **평균 시청 지속 시간 (Average View Duration, AVD)** | **{{AVD_SECONDS}}초** (`/ {{AVG_VIDEO_LENGTH}}초`) | {{AVD_PREV}}초 | {{AVD_DELTA}} | `>= 25.0초` (평균 `{{AVG_VIDEO_LENGTH}}초` 기준) | {{AVD_GATE_BADGE}} |
| **평균 시청률 (Average Percentage Viewed, APV %)** | **{{APV_PCT}}%** | {{APV_PREV_PCT}}% | {{APV_DELTA}} | `>= 85.0%` (Rule R19 독립 결론 완주) | {{APV_GATE_BADGE}} |
| **시청 선택 비율 (Viewed % — Swiped Away 방어율)** | **{{VIEWED_PCT}}%** | {{VIEWED_PREV_PCT}}% | {{VIEWED_DELTA}} | `>= 70.0%` (초반 사례 훅 방어) | {{VIEWED_GATE_BADGE}} |
| **스와이프 이탈률 (Swiped Away %)** | **{{SWIPED_PCT}}%** | {{SWIPED_PREV_PCT}}% | {{SWIPED_DELTA}} | `< 30.0%` (낮을수록 우수) | {{SWIPED_GATE_BADGE}} |
| **노출수 (Impressions — 탐색/검색)** | **{{IMPRESSIONS_24H}}회** | {{IMPRESSIONS_PREV}}회 | {{IMPRESSIONS_DELTA}} | 지속 우상향 | {{IMPRESSIONS_BADGE}} |
| **노출 클릭률 (Impressions CTR %)** | **{{CTR_PCT}}%** | {{CTR_PREV_PCT}}% | {{CTR_DELTA}} | `>= 6.0%` | {{CTR_GATE_BADGE}} |
| **좋아요 비율 (Like-to-View / Like Ratio %)** | **{{LIKE_RATIO_PCT}}%** (`{{LIKES_24H}}개`) | {{LIKE_RATIO_PREV_PCT}}% | {{LIKE_RATIO_DELTA}} | `>= 4.0%` | {{LIKE_GATE_BADGE}} |
| **댓글 / 공유 / 리믹스 (Comments / Shares / Remixes)** | **댓글 {{COMMENTS_24H}} / 공유 {{SHARES_24H}} / 리믹스 {{REMIXES_24H}}** | 댓글 {{COMMENTS_PREV}} / 공유 {{SHARES_PREV}} | {{ENGAGEMENT_DELTA}} | DOI 토론 유도 | {{ENGAGEMENT_BADGE}} |

### 📐 [표 3-1] 영상 길이 비례 4분위 시청 지속률 해부 (Rule R42 Duration-Proportional Retention Quartiles: Q1~Q4)
| 분위 구간 (Quartile) | 진행 구간 (평균 시간대) | Rule R42 Role Spine 단계 | 핵심 진단 질문 (Diagnostic Question) | 오늘 유지율 (%) | 어제 유지율 (%) | 전일 대비 (DoD Δ) | 목표 기준 | 상태 판정 |
| :---: | :---: | :--- | :--- | :--- | :---: | :---: | :---: | :---: |
| {{RETENTION_QUARTILE_ROWS}} |

### 📉 [그래프 3-1] 영상 길이 비례 4분위 구간별 평균 시청 지속률 곡선 (Audience Retention Curve: 0% → 100%)
```mermaid
xychart-beta
    title "Duration-Proportional Audience Retention Curve (Q1-Q4, Today vs Yesterday)"
    x-axis ["0% (Start)", "10% (Hook)", "25% Q1 (Symptom)", "50% Q2 (Pivot)", "75% Q3 (Mechanism)", "100% Q4 (Conclusion)"]
    y-axis "Retention (%)" 60 --> 105
    line [{{RETENTION_CURVE_TODAY}}]
    line [{{RETENTION_CURVE_PREV}}]
```

### 📊 [그래프 3-2] 개별 Shorts 영상별 APV(%) 및 초반 훅 방어율(Viewed %) 비교
```mermaid
xychart-beta
    title "Per-Video Average Percentage Viewed (APV %) vs Hook Viewed (%)"
    x-axis [{{VIDEO_LABELS}}]
    y-axis "Percentage (%)" 0 --> 105
    bar [{{VIDEO_APV_LIST}}]
    line [{{VIDEO_VIEWED_LIST}}]
```

---

## 4. 트래픽 소스 및 검색 유입 상세 분석 (Traffic Sources & Discovery)

### 4-1. 트래픽 소스별 조회수 및 시각적 게이지
| 트래픽 소스 (Traffic Source) | 비중 그래프 (Share Bar) | 조회수 비중 (%) | 조회수 (회) | 전일 대비 (Δ %p) | 소스별 AVD (초) | 소스별 APV (%) | 분석 코멘트 |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| {{TRAFFIC_SOURCE_ROWS}} |

### 4-2. 상위 유입 YouTube 검색어 Top 5 (Search Terms)
| 순위 | 검색 키워드 (Search Query) | 유입 비중 (%) | 조회수 | 매칭 프로젝트 / 필러 |
| :---: | :--- | :---: | :---: | :--- |
| {{SEARCH_TERM_ROWS}} |

---

## 5. 시청자층·지역(Tier-1 검증)·인구통계 상세 (Audience & Demographics)

### 5-1. 상위 국가별 분포 (Rule R36 `en-US` Tier-1 타겟팅 검증)
| 순위 | 국가 (Geography) | 비중 게이지 | 시청 비중 (%) | 전일 대비 (Δ %p) | 국가별 AVD (초) | 국가별 APV (%) | Tier-1 타겟 상태 |
| :---: | :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| {{GEOGRAPHY_ROWS}} |

### 📊 [그래프 5-1] 국가별 시청 비중 분포 (Tier-1 English Audience Distribution)
```mermaid
xychart-beta
    title "Audience Geography Share (%)"
    x-axis ["US", "UK", "CA", "AU", "KR/Other"]
    y-axis "Share (%)" 0 --> 65
    bar [{{GEO_PCT_LIST}}]
```

### 5-2. 시청자 구성 (연령대 · 성별 · 재방문 · 구독 비율)
| 구분 | 세부 항목 | 비중 / 수치 | 전일 대비 변화 | 인사이트 |
| :--- | :--- | :---: | :---: | :--- |
| {{DEMOGRAPHIC_ROWS}} |

---

## 6. 개별 Shorts 영상별 전수 성적표 (Granular Per-Video Performance Table)

### 6-1. 공개 Shorts 전수 성적표 (`{{PER_VIDEO_COUNT}}`편)
| # | 프로젝트 ID / 제목 | 필러 (Slot) | 상태 / 게시일 | 누적 조회수 (`24h Δ`) | **AVD (`초/길이`)** | **APV (`%`)** | **Viewed / Swiped (`%`)** | **4분위 유지율 (`Q1 / Q2 / Q3 / Q4`)** | 노출 CTR (`%`) | 좋아요 / 댓글 / 공유 | A/B 썸네일 & DOI | 종합 등급 |
| :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| {{PER_VIDEO_ROWS}} |

### 6-2. 🔎 특정 영상별 눈에 띄는 변화 감지 및 심층 원인 분석 (Per-Video Notable Change & Root-Cause Attribution)
| # | 프로젝트 ID / 제목 | 감지된 변화 시그널 (Signal Badge) | 무엇이 변했는가 (Observed Metric Shift) | 왜 그런 변화가 발생했는가 (3-Axis Root-Cause Summary) | 영상별 맞춤 처방 (Targeted Action) |
| :---: | :--- | :---: | :--- | :--- | :--- |
| {{NOTABLE_VIDEO_CHANGE_ROWS}} |

{{NOTABLE_VIDEO_DETAIL_CARDS}}

---

## 7. 7대 학술 필러(Pillar) & 5-Slot 타임테이블별 성과 비교 (Pillar & Slot Matrix)

| 학술 필러 (Pillar) | 배정 슬롯 (US ET) | 공개 영상 수 | 평균 조회수/편 | 평균 AVD (초) | 평균 APV (%) | 평균 Viewed (%) | 구독 전환율 (명/1k뷰) | 필러 성과 진단 |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| {{PILLAR_MATRIX_ROWS}} |

---

## 8. 72시간 순차 썸네일 A/B/C 테스트(Z-Test) 및 스테이징 큐 · 위험 감사 (Operations, Queue & Risk Audit)

### 8-1. 진행 중인 72h 썸네일 A/B/C 테스트 현황 (Rule R32 `p < 0.05`)
| 프로젝트 ID | 현재 활성 썸네일 | 경과 시간 | Var A CTR (`노출/클릭`) | Var B CTR (`노출/클릭`) | Var C CTR (`노출/클릭`) | 최대 Z-Score (`p-value`) | 다음 교체 / 최종 우승 판정 |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| {{AB_TEST_ROWS}} |

### 📊 [그래프 8-1] 썸네일 변형별(Variant A vs B vs C) 평균 노출 클릭률(CTR %) 비교
```mermaid
xychart-beta
    title "Thumbnail A/B/C Sequential Test — Search & Browse CTR (%)"
    x-axis ["Variant A (Cool Blue)", "Variant B (Alert Crimson)", "Variant C (Defiance Gold)"]
    y-axis "CTR (%)" 0 --> 12
    bar [{{AB_CTR_LIST}}]
```

### 8-2. 오늘 및 내일 5-Slot 발행 스케줄 점검 (Rule R30 & R33)
| 날짜 | 슬롯 (US ET / KST) | 푸시 알림 | 배정 프로젝트 ID | 제목 | Video ID | 현재 상태 |
| :---: | :--- | :---: | :--- | :--- | :---: | :---: |
| {{SCHEDULE_ROWS}} |

### 8-3. 🚨 채널 운영 및 파이프라인 7대 위험 진단 매트릭스 (Risk & Compliance Audit)
| ID | 진단 항목 (Risk Category) | 심각도 | 현재 상태 판정 | 실증 근거 (Audit Evidence) | 즉시 조치 처방 (Action Remedy) |
| :---: | :--- | :---: | :--- | :--- | :--- |
| {{RISK_AUDIT_ROWS}} |

---

## 9. 심층 원인 분석: 어제보다 나아진 점 vs. 개선 과제 (Deep-Dive Diagnostics & Provenance)

### 9-1. ✨ 어제보다 나아진 점 & 🟢 성공 시그널 감지 (What Improved & Success Signals Detected)
- **시청 지속 시간 / 완주율(AVD & APV) 개선 요인**: {{DIAG_IMPROVED_RETENTION}}
- **Q1 초반 훅(Viewed vs. Swiped Away) 방어 성공 요인**: {{DIAG_IMPROVED_HOOK}}
- **트래픽 확장 및 알고리즘 시드 테스트 돌파 요인**: {{DIAG_IMPROVED_TRAFFIC}}

#### 🟢 [표 9-1] 성공 시그널(Success Signals) 조기 감지 매트릭스
| 시그널 ID | 감지된 성공 시그널 (Success Signal) | 대상 영상 / 코호트 | 상태 판정 | 실증 지표 근거 (Metric Evidence) | 통과 임계 게이트 | 작동 메커니즘 (Why It Worked) |
| :---: | :--- | :--- | :---: | :--- | :---: | :--- |
| {{SUCCESS_SIGNAL_ROWS}} |

### 9-2. 🔍 아쉬운 점 · 4분위 이탈 & 🔴 실패·위험 시그널 감지 (Drop-Off Autopsy & Failure/Risk Signals)
- **Q1 초반 이탈(`0–25%`, Setup → Symptom) 발생 영상 및 원인**: {{DIAG_BOTTLENECK_HOOK}}
- **Q2~Q3 중반 이탈(`25–75%`, Pivot → Mechanism Steps) 발생 영상 및 원인**: {{DIAG_BOTTLENECK_MID}}
- **Q4 후반 결론(`75–100%`, Breakthrough → Conclusion, Rule R19) 유지율 진단**: {{DIAG_BOTTLENECK_CONCLUSION}}

#### 🔴 [표 9-2] 실패 및 위험 시그널(Failure & Risk Signals) 조기 감지 매트릭스
| 시그널 ID | 감지된 실패·위험 시그널 (Failure / Risk Signal) | 대상 영상 / 구간 | 위험 등급 | 실증 지표 근거 (Metric Evidence) | 근본 원인 (Root Cause) | 즉시 차단·교정 처방 (Immediate Fix) |
| :---: | :--- | :--- | :---: | :--- | :--- | :--- |
| {{FAILURE_RISK_SIGNAL_ROWS}} |

### 9-3. 🛠️ 내일의 파이프라인 최적화 처방 & 🚀 성공 시그널 증폭 플레이북 (Next 24h Prescriptions & Amplification Playbook)
1. **[콘텐츠/대본 처방 (Rule R42/R43/R19)]**: {{PRESCRIPTION_SCRIPT}}
2. **[비주얼/카메라 처방 (Rule R14-A/R38/R40)]**: {{PRESCRIPTION_VISUAL}}
3. **[스튜디오/스케줄/썸네일 처방 (Rule R30–R36)]**: {{PRESCRIPTION_STUDIO}}

#### 🚀 [표 9-3] 성공 시그널 증폭(Success Signal Amplification) 5-Gear 실행 플레이북
| 전략 ID | 성공 시그널 증폭 전략명 (Amplification Strategy) | 증폭 대상 시그널 | 적용 기어 · 규칙 · 범위 | 구체적 실행 플레이북 (Actionable Playbook) | 기대 성과 (Expected Lift) |
| :---: | :--- | :--- | :--- | :--- | :--- |
| {{AMPLIFICATION_PLAYBOOK_ROWS}} |

### 9-4. 🔐 Raw Snapshot & Provenance
- **Raw Metrics Snapshot JSON**: `{{RAW_METRICS_JSON_PATH}}`
- **Data Source Mode**: `{{DATA_SOURCE_MODE}}`
- **Naver Whale CDP Session**: `{{WHALE_CDP_STATE}}`
- **Payload SHA-256 Digest**: `{{PROVENANCE_SHA256}}`
````

