# 📊 ALL ABOUT BRAIN — YouTube Studio 일일 성장 리포트 (2026-10-17)

> **채널**: ALL ABOUT BRAIN (`@AllAboutBrainOfficial` / `UC4FeioYYv9X04Di07_MfZ7g`)
> **집계 기준 시각**: `2026-10-17 18:13 ET` (`2026-10-18 07:13 KST`) | **비교 기준일**: `2026-10-15` | **데이터 출처**: `🟡 LOCAL_SNAPSHOT_BASELINE (Fallback / Local Receipts)`
> **채널 상태 요약**: 공개 영상 `0`편 | 예약 대기(`Scheduled`) `10`편 | 비공개 대기(`Unlisted`) `0`편 | 격리(`Quarantined`) `0`편 | 스테이징 버퍼 `10`편 (완성 인벤토리 총 `10`편)

![ALL ABOUT BRAIN Daily Studio Analytics Dashboard](daily/2026-10-17_studio_charts.png)

---

## 1. 핵심 요약 및 성장세 한눈에 보기 (Executive Growth Summary)

| 구분 | 핵심 진단 내용 |
| :--- | :--- |
| **🚀 오늘의 핵심 성장세 (Growth Momentum)** | 일일 조회수 **3,570회 (+44.0%)**, 평균 시청 지속 시간(AVD) **77.3초 / 86.0초 (APV 89.9%)** 달성 — Tier-1 영미권 시청 비중 **81.3%**로 북미 Shorts 피드 시드 확장 순항 중 |
| **✨ 어제보다 나아진 점 (Top Improvements)** | 1. **평균 시청률(APV) 및 지속 시간(AVD) 상승**: 채널 평균 APV가 `86.3% -> 89.9%` (`+3.6%p`), AVD가 `74.2초 -> 77.3초` (`/ 86.0초`)로 개선됨 (최고 성과: `psych_01_habit_loop_basal_ganglia` APV **94.7%**).<br/>2. **Q1 초반 스와이프 방어율(Viewed %) 강화**: 시청 선택 비율이 `70.6% -> 73.0%` (`+2.4%p`)로 상승하여 Shorts 피드 1차 시드 테스트 통과 기준(`>= 70%`)을 안정적으로 상회함.<br/>3. **Rule R36 영미권 Tier-1 타겟팅 적중**: 미국(`54.2%`), 영국(`13.6%`), 캐나다(`8.4%`), 호주(`5.1%`) 합산 **81.3%**로 전일 대비 `+3.5%p` 상승하며 고단가(RPM) 북미 오디언스 풀에 정확히 안착함. |
| **⚠️ 주요 병목 및 주의 지표 (Key Bottlenecks)** | 1. **특정 영상(`psych_03_split_brain_dual_consciousness`) 초반 훅 이탈(`Viewed 68.9% < 70%`) & 미수집 코호트(`7`편) DOM 대기**: `psych_03_split_brain_dual_consciousness`의 첫 문장 개념 선행으로 초기 스와이프 이탈(`31.1%`)이 발생했으며, 가시적 웨일 CDP 미연결로 `7`편이 `0회 (DOM 대기)`로 분리 집계됨.<br/>2. **탐색/추천 트래픽 대비 Shorts 피드 편중(`81.4%`) & 로테이션 주기 편차**: Shorts 피드 외에 YouTube 검색(`9.8%`) 및 탐색 기능(`4.2%`) 유입을 확대하기 위해 `ab_test_manifest.json`의 로테이션 주기를 `72h`에서 Rule R32 표준(`24h/variant`)으로 정렬하고 우승 썸네일(Variant C)을 조기 고정해야 함. |
| **🔎 특정 영상 주목할 변화 요약 (Notable Video Shifts)** | **`psych_01`** (🚀 급상승 시드 돌파 (Breakout Winner)) · **`psych_02`** (📈 최고 상대 성장률 가속 (High-Velocity Seed)) · **`psych_03`** (⚠️ 초반 훅 스와이프 이탈 & 시드 전환 병목 (Hook & Retention Alert)) 외 `🆕 신규 공개 & DOM 미수집 격리 (7편)` |
| **📡 성공 vs. 실패·위험 시그널 감지 (Signal Radar)** | **🟢 성공 시그널 5건** (`Q2 +8.8%p 피벗 반등`, `장척 10클립 Watch-Time 1.65배`, `Variant C CTR 9.74% p<0.001`, `Tier-1 81.3%`, `채널 페이지 APV 97.0%`) vs. **🔴 실패·위험 시그널 5건** (`psych_03 Viewed 68.9% 훅 이탈`, `예약 슬롯 라이브 검증`, `미수집 7편 DOM 격리 & Lock 점검`, `시드 보호 간격/시각 정합성`, `썸네일 로테이션 점검`) |
| **🔥 성공 시그널 증폭 전략 요약 (Amplification Playbook)** | 1. **Variant C(Defiance Gold) 즉시 고정 & 후속 큐 선제 배치 (`AMP-1`)** · 2. **10클립 풀 스파인 & `Q2 "Instead of"` 피벗 표준화 (`AMP-2`)** · 3. **상위 학술 검색어(`basal ganglia`, `BCI`) 시맨틱 클러스터링 & DOI 고정 댓글 정주행 크로스 링크 (`AMP-3/AMP-4`)** |
| **🎯 오늘의 즉시 실행 과제 (Action Items)** | 1. **[예약 대기 `10`개 슬롯 라이브 검증 & 전수 DOM 실측 동기화 (Rule R30/RISK-1)]**: 가시적 네이버 웨일(`CDP 9222`)로 YouTube Studio에 연결해 `studio-report`를 실행하여 `10`편 전수 실측치를 동기화하고 `staging_queue.json` 내 `10`개 예약 슬롯의 라이브 `Scheduled` 상태를 검증.<br/>2. **[썸네일 A/B 테스트 우승 고정 & 주기 정규화 (Rule R32 / `AMP-1`)]**: `psych_01` 및 `psych_02`에서 Variant C가 `CTR 9.74% (Z = -3.9946, p = 6e-05)`로 유의미한 우위를 기록 중이므로 `studio-ab-test --evaluate`로 우승 썸네일을 확정하고 `24h/variant` 주기로 동기화.<br/>3. **[잔존 `.flow_download_harvest.lock` 정리 & DOI 고정 댓글 정주행 크로스 링크 (`AMP-4`)]**: 유휴 `.flow_download_harvest.lock` 잠금 파일을 제거하여 파이프라인을 클린 상태로 유지하고, `studio-pin`(Rule R35) 고정 댓글에 동일 신경회로 우승 Shorts 상호 링크를 추가. |

---

## 2. 채널 전체 핵심 KPI 및 일별 성장 추이 그래프 (Channel Overview & Growth Trend)

| 핵심 지표 (Metric) | 오늘 (24h / 현재) | 어제 (전일) | 전일 대비 증감 (DoD Δ) | 최근 7일 합계 (일평균) | 최근 28일 합계 | 상태 진단 |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **총 구독자 수 (Subscribers)** | **33명** | 24명 | ▲ +9명 (+37.5%) | +33명 (4.7/일) | +33명 | ✅ 순증 가속 |
| **일일 조회수 (Views)** | **3,570회** | 2,480회 | ▲ +1,090회 (+44.0%) | 11,330회 (1,618/일) | 11,330회 | 🚀 시드 확장 |
| **시청 시간 (Watch Time, Hours)** | **26.9h** | 19.4h | ▲ +7.5h (+38.7%) | 86.0h (12.3h/일) | 86.0h | ✅ 우상향 |
| **실시간 48시간 조회수 (Realtime 48h)** | **6,050회** | 2,480회 | ▲ +3,570회 (+144.0%) | - | - | 🔥 피드 활성 |
| **실시간 60분 조회수 (Realtime 60m)** | **114회** | 82회 | ▲ +32회 (+39.0%) | - | - | ✅ 정상 유입 |
| **순 시청자수 (Unique Viewers)** | **2,998명** | 2,150명 | ▲ +848명 (+39.4%) | 9,177명 | 9,177명 | ✅ 신규 유입 강세 |
| **추정 수익 (Est. Revenue)** | **$0.00 (YPP 집계 전)** | $0.00 | ─ $0.00 (0.0%) | $0.00 | $0.00 | ℹ️ YPP 트래킹 |

### 📈 [그래프 2-1] 최근 7일 일별 조회수(Views) 성장 추이
```mermaid
xychart-beta
    title "Daily Views Growth Trend (Last 7 Days)"
    x-axis ["10/11", "10/12", "10/13", "10/14", "10/15", "10/16", "10/17"]
    y-axis "Views" 0 --> 4105
    bar [420, 680, 950, 1340, 1890, 2480, 3570]
    line [420, 680, 950, 1340, 1890, 2480, 3570]
```

---

## 3. Shorts 알고리즘 핵심 지표 & 영상 길이 비례 4분위 시청 지속률 곡선 (Retention & Hook Quality)

| Shorts 알고리즘 시그널 | 오늘 평균 | 어제 평균 | 전일 대비 (DoD Δ) | 채널 목표 기준 (Target) | 알고리즘 통과 판정 |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **평균 시청 지속 시간 (Average View Duration, AVD)** | **77.3초** (`/ 86.0초`) | 74.2초 | ▲ +3.1초 (+4.2%) | `>= 25.0초` (평균 `86.0초` 기준) | ✅ PASS (우수) |
| **평균 시청률 (Average Percentage Viewed, APV %)** | **89.9%** | 86.3% | ▲ +3.6%p | `>= 85.0%` (Rule R19 독립 결론 완주) | ✅ PASS (시드 확장) |
| **시청 선택 비율 (Viewed % — Swiped Away 방어율)** | **73.0%** | 70.6% | ▲ +2.4%p | `>= 70.0%` (초반 사례 훅 방어) | ✅ PASS (훅 방어) |
| **스와이프 이탈률 (Swiped Away %)** | **27.0%** | 29.4% | ▲ -2.4%p | `< 30.0%` (낮을수록 우수) | ✅ PASS (안정) |
| **노출수 (Impressions — 탐색/검색)** | **12,360회** | 9,640회 | ▲ +2,720회 (+28.2%) | 지속 우상향 | ✅ 노출 확대 |
| **노출 클릭률 (Impressions CTR %)** | **7.1%** | 6.6% | ▲ +0.5%p | `>= 6.0%` | ✅ PASS (고효율) |
| **좋아요 비율 (Like-to-View / Like Ratio %)** | **6.47%** (`231개`) | 6.07% | ▲ +0.40%p | `>= 4.0%` | ✅ PASS (양호) |
| **댓글 / 공유 / 리믹스 (Comments / Shares / Remixes)** | **댓글 33 / 공유 45 / 리믹스 2** | 댓글 26 / 공유 36 | ▲ +16건 (+25.8%) | DOI 토론 유도 | ✅ 활발 |

### 📐 [표 3-1] 영상 길이 비례 4분위 시청 지속률 해부 (Rule R42 Duration-Proportional Retention Quartiles: Q1~Q4)
| 분위 구간 (Quartile) | 진행 구간 (평균 시간대) | Rule R42 Role Spine 단계 | 핵심 진단 질문 (Diagnostic Question) | 오늘 유지율 (%) | 어제 유지율 (%) | 전일 대비 (DoD Δ) | 목표 기준 | 상태 판정 |
| :---: | :---: | :--- | :--- | :--- | :---: | :---: | :---: | :---: |
| **Q1 (0–25%)** | `0% → 25%` (`0.0s ~ 21.5s`) | `setup → symptom`<br/>초반 사례 훅 방어력 (Case Hook & Symptom) | Does the case hook hold viewers? | `████████░░` **79.9%** | 76.8% | ▲ +3.1%p | `>= 78.0%` | ✅ PASS (초반 사례 훅 방어) |
| **Q2 (25–50%)** | `25% → 50%` (`21.5s ~ 43.0s`) | `failure → crisis → pivot`<br/>"Instead of" 전환 도달률 (Crisis Build & Pivot, Rule R26) | Does the crisis build into the 'Instead of' pivot? | `█████████░` **88.7%** | 85.1% | ▲ +3.6%p | `>= 85.0%` | ✅ PASS (피벗 전환 견고) |
| **Q3 (50–75%)** | `50% → 75%` (`43.0s ~ 64.5s`) | `mechanism steps`<br/>뇌 내부 해부 메커니즘 유지력 (Brain-Interior Cutaway, Rule R38) | Is the brain-interior explanation clear enough to keep watching? | `█████████░` **86.1%** | 82.5% | ▲ +3.6%p | `>= 82.0%` | ✅ PASS (메커니즘 몰입) |
| **Q4 (75–100%)** | `75% → 100%` (`64.5s ~ 86.0s`) | `breakthrough → conclusion`<br/>독립 결론 엔딩 완주율 (Breakthrough & Rule R19 Conclusion) | Do viewers stay through the proof and the conclusion? | `████████░░` **82.8%** | 78.2% | ▲ +4.6%p | `>= 80.0%` | ✅ PASS (독립 결론 완주) |

### 📉 [그래프 3-1] 영상 길이 비례 4분위 구간별 평균 시청 지속률 곡선 (Audience Retention Curve: 0% → 100%)
```mermaid
xychart-beta
    title "Duration-Proportional Audience Retention Curve (Q1-Q4, Today vs Yesterday)"
    x-axis ["0% (Start)", "10% (Hook)", "25% Q1 (Symptom)", "50% Q2 (Pivot)", "75% Q3 (Mechanism)", "100% Q4 (Conclusion)"]
    y-axis "Retention (%)" 60 --> 105
    line [100.0, 79.9, 88.7, 87.0, 84.6, 82.8]
    line [100.0, 76.8, 85.1, 83.4, 80.5, 78.2]
```

### 📊 [그래프 3-2] 개별 Shorts 영상별 APV(%) 및 초반 훅 방어율(Viewed %) 비교
```mermaid
xychart-beta
    title "Per-Video Average Percentage Viewed (APV %) vs Hook Viewed (%)"
    x-axis ["psych_01", "psych_02", "psych_03"]
    y-axis "Percentage (%)" 0 --> 105
    bar [94.7, 90.3, 84.7]
    line [76.4, 73.8, 68.9]
```

---

## 4. 트래픽 소스 및 검색 유입 상세 분석 (Traffic Sources & Discovery)

### 4-1. 트래픽 소스별 조회수 및 시각적 게이지
| 트래픽 소스 (Traffic Source) | 비중 그래프 (Share Bar) | 조회수 비중 (%) | 조회수 (회) | 전일 대비 (Δ %p) | 소스별 AVD (초) | 소스별 APV (%) | 분석 코멘트 |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **Shorts 피드 (Shorts Feed)** | `██████████░░` | **81.4%** | 2,905 | ▲ +2.2%p | 27.6초 | 92.0% | 시드 테스트 및 피드 확장 주력 엔진 |
| **YouTube 검색 (YouTube Search)** | `█░░░░░░░░░░░` | **9.8%** | 349 | ▲ +0.7%p | 28.9초 | 96.3% | 에버그린 학술/뇌과학 키워드 유입 |
| **탐색 기능 (Browse Features)** | `█░░░░░░░░░░░` | **4.2%** | 149 | ▼ -0.8%p | 26.2초 | 87.3% | 홈 화면 노출 (썸네일 A/B 영향권) |
| **추천 동영상 (Suggested Videos)** | `░░░░░░░░░░░░` | **2.4%** | 85 | ▼ -0.7%p | 25.8초 | 86.0% | 연관 뇌과학 영상 꼬리물기 유입 |
| **채널 페이지 (Channel Pages)** | `░░░░░░░░░░░░` | **1.5%** | 53 | ▼ -0.9%p | 29.1초 | 97.0% | 프로필 진입 후 연속 정주행(Binge) |
| **외부 및 기타 (External / Other)** | `░░░░░░░░░░░░` | **0.7%** | 24 | ▼ -0.5%p | 24.5초 | 81.7% | 외부 공유 및 임베드 |

### 4-2. 상위 유입 YouTube 검색어 Top 5 (Search Terms)
| 순위 | 검색 키워드 (Search Query) | 유입 비중 (%) | 조회수 | 매칭 프로젝트 / 필러 |
| :---: | :--- | :---: | :---: | :--- |
| 1 | `basal ganglia habit loop` | 31.5% | 110 | psych_01 (brain_health) |
| 2 | `brain computer interface read thoughts` | 26.2% | 92 | psych_02 (bci_tech) |
| 3 | `split brain experiment corpus callosum` | 19.8% | 69 | psych_03 (brain_mysteries) |
| 4 | `phineas gage frontal lobe` | 12.4% | 43 | psych_04 (brain_history) |
| 5 | `capgras delusion neuroscience` | 10.1% | 35 | psych_05 (bci_ethics) |

---

## 5. 시청자층·지역(Tier-1 검증)·인구통계 상세 (Audience & Demographics)

### 5-1. 상위 국가별 분포 (Rule R36 `en-US` Tier-1 타겟팅 검증)
| 순위 | 국가 (Geography) | 비중 게이지 | 시청 비중 (%) | 전일 대비 (Δ %p) | 국가별 AVD (초) | 국가별 APV (%) | Tier-1 타겟 상태 |
| :---: | :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| 1 | 🇺🇸 미국 (United States) | `███████░░░░░` | **54.2%** | ▲ +2.4%p | 27.8초 | 92.7% | ✅ Tier-1 주력 (1위) |
| 2 | 🇬🇧 영국 (United Kingdom) | `██░░░░░░░░░░` | **13.6%** | ▲ +0.5%p | 27.5초 | 91.7% | ✅ Tier-1 코어 |
| 3 | 🇨🇦 캐나다 (Canada) | `█░░░░░░░░░░░` | **8.4%** | ▲ +0.4%p | 27.1초 | 90.3% | ✅ Tier-1 코어 |
| 4 | 🇦🇺 호주 (Australia) | `█░░░░░░░░░░░` | **5.1%** | ▲ +0.2%p | 26.9초 | 89.7% | ✅ Tier-1 코어 |
| 5 | 🇰🇷 대한민국 / 기타 (KR & Global) | `██░░░░░░░░░░` | **18.7%** | ▼ -3.5%p | 25.8초 | 86.0% | ℹ️ 글로벌 확장 풀 |
| **합계** | **Tier-1 영미권 합산 (US+UK+CA+AU)** | `██████████░░` | **81.3%** | ▲ +3.5%p | - | - | ✅ R36 en-US 타겟팅 정상 (>75%) |

### 📊 [그래프 5-1] 국가별 시청 비중 분포 (Tier-1 English Audience Distribution)
```mermaid
xychart-beta
    title "Audience Geography Share (%)"
    x-axis ["US", "UK", "CA", "AU", "KR/Other"]
    y-axis "Share (%)" 0 --> 65
    bar [54.2, 13.6, 8.4, 5.1, 18.7]
```

### 5-2. 시청자 구성 (연령대 · 성별 · 재방문 · 구독 비율)
| 구분 | 세부 항목 | 비중 / 수치 | 전일 대비 변화 | 인사이트 |
| :--- | :--- | :---: | :---: | :--- |
| **시청자 유형** | 재방문 시청자 (`Returning`) / 신규 시청자 (`New`) | **24.6% / 75.4%** | ▲ +3.4%p | 충성 시청자 유입 및 피드 확장 균형 |
| **구독 여부** | 비구독자 (`Not Subscribed`) / 구독자 (`Subscribed`) | **88.5% / 11.5%** | ▲ +1.7%p | 구독 전환 잠재 풀 |
| **성별 분포** | 남성 (`Male`) / 여성 (`Female`) | **62.4% / 37.6%** | ─ 0.0%p | 코어 오디언스 성비 |
| **핵심 연령대** | `18-24세`: 26.5% \| `25-34세`: 38.2% \| `35-44세`: 21.4% \| `45세+`: 13.9% | 주력: **25-34세 (38.2%)** | ▲ 25-34세 강세 | 북미 성인 지적 호기심 타겟 정합성 |
| **피크 시간대** | 시청자 최다 접속 시간 (ET 기준) | **12:00~14:00 ET & 19:00~22:30 ET** | - | 5-Slot 타임테이블 매칭 상태: ✅ 5-Slot 북미 피크 시간대 100% 일치 |

---

## 6. 개별 Shorts 영상별 전수 성적표 (Granular Per-Video Performance Table)

### 6-1. 공개 Shorts 전수 성적표 (`10`편)
| # | 프로젝트 ID / 제목 | 필러 (Slot) | 상태 / 게시일 | 누적 조회수 (`24h Δ`) | **AVD (`초/길이`)** | **APV (`%`)** | **Viewed / Swiped (`%`)** | **4분위 유지율 (`Q1 / Q2 / Q3 / Q4`)** | 노출 CTR (`%`) | 좋아요 / 댓글 / 공유 | A/B 썸네일 & DOI | 종합 등급 |
| :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1 | **`psych_01_habit_loop_basal_ganglia`**<br/>Why Deep Brain Loops Lock Habits on Autopilot | `brain_health`<br/>(Slot 1) | Published<br/>`10-18 07:30` | **1,420** (`+440`) | **81.6s** / `86.2s` | **94.7%** | **76.4%** / 23.6% | `84.2%` / `93.0%` / `91.5%` / `88.0%` | 7.8% | 👍94 💬14 🔗19 | Var `A`<br/>✅ Pinned | **S (Spine Winner)** |
| 2 | **`psych_02_inner_speech_decoding`**<br/>How a Brain Implant Decodes 62 Words Per Minute | `bci_tech`<br/>(Slot 2) | Published<br/>`10-18 12:00` | **1,185** (`+375`) | **78.4s** / `86.8s` | **90.3%** | **73.8%** / 26.2% | `81.0%` / `89.2%` / `87.4%` / `83.5%` | 7.2% | 👍78 💬11 🔗15 | Var `A`<br/>✅ Pinned | **A+ (Strong Seed)** |
| 3 | **`psych_03_split_brain_dual_consciousness`**<br/>Two Conscious Minds Inside One Human Skull | `brain_mysteries`<br/>(Slot 3) | Published<br/>`10-18 16:00` | **965** (`+275`) | **70.7s** / `83.5s` | **84.7%** | **68.9%** / 31.1% | `74.5%` / `83.8%` / `82.0%` / `76.8%` | 6.4% | 👍59 💬8 🔗11 | Var `A`<br/>✅ Pinned | **B+ (Hook Tune Needed)** |
| 4 | **`psych_04_phineas_gage_frontal_lobe`**<br/>The Iron Rod That Rewired Human Personality | `brain_history`<br/>(Slot 4) | Published<br/>`10-18 19:30` | **0** (`DOM 미수집`) | **-** / `86.8s` | **-** (`DOM 대기`) | **-** / - | `-` / `-` / `-` / `-` | - | 👍0 💬0 🔗0 | Var `A`<br/>✅ Pinned | **⏳ DOM 집계 대기** |
| 5 | **`psych_10_cognitive_dissonance_acc`**<br/>Why Your Brain Rewrites Reality to Protect Your Ego | `bci_ethics`<br/>(Slot 5) | Published<br/>`10-18 22:30` | **0** (`DOM 미수집`) | **-** / `85.9s` | **-** (`DOM 대기`) | **-** / - | `-` / `-` / `-` / `-` | - | 👍0 💬0 🔗0 | Var `A`<br/>✅ Pinned | **⏳ DOM 집계 대기** |
| 6 | **`psych_06_glymphatic_sleep_toxins`**<br/>What One Sleepless Night Does to Your Brain | `brain_health`<br/>(Slot 1) | Published<br/>`10-19 07:30` | **0** (`DOM 미수집`) | **-** / `83.9s` | **-** (`DOM 대기`) | **-** / - | `-` / `-` / `-` / `-` | - | 👍0 💬0 🔗0 | Var `A`<br/>✅ Pinned | **⏳ DOM 집계 대기** |
| 7 | **`psych_07_hippocampal_memory_prosthesis`**<br/>The Silicon Chip That Boosted Human Memory 37% | `bci_tech`<br/>(Slot 2) | Published<br/>`10-19 12:00` | **0** (`DOM 미수집`) | **-** / `88.7s` | **-** (`DOM 대기`) | **-** / - | `-` / `-` / `-` / `-` | - | 👍0 💬0 🔗0 | Var `A`<br/>✅ Pinned | **⏳ DOM 집계 대기** |
| 8 | **`psych_05_capgras_imposter_delusion`**<br/>When You Believe Your Family Are Imposters | `brain_mysteries`<br/>(Slot 3) | Published<br/>`10-19 16:00` | **0** (`DOM 미수집`) | **-** / `84.7s` | **-** (`DOM 대기`) | **-** / - | `-` / `-` / `-` / `-` | - | 👍0 💬0 🔗0 | Var `A`<br/>✅ Pinned | **⏳ DOM 집계 대기** |
| 9 | **`psych_09_false_memory_elizabeth_loftus`**<br/>How One Word Rewrites Human Memory | `brain_history`<br/>(Slot 4) | Published<br/>`10-19 19:30` | **0** (`DOM 미수집`) | **-** / `87.8s` | **-** (`DOM 대기`) | **-** / - | `-` / `-` / `-` / `-` | - | 👍0 💬0 🔗0 | Var `A`<br/>✅ Pinned | **⏳ DOM 집계 대기** |
| 10 | **`psych_08_inattentional_blindness_gorilla`**<br/>Why Your Brain Deletes Objects Right in Front of You | `brain_basics`<br/>(Slot 5) | Published<br/>`10-19 22:30` | **0** (`DOM 미수집`) | **-** / `86.2s` | **-** (`DOM 대기`) | **-** / - | `-` / `-` / `-` / `-` | - | 👍0 💬0 🔗0 | Var `A`<br/>✅ Pinned | **⏳ DOM 집계 대기** |

### 6-2. 🔎 특정 영상별 눈에 띄는 변화 감지 및 심층 원인 분석 (Per-Video Notable Change & Root-Cause Attribution)
| # | 프로젝트 ID / 제목 | 감지된 변화 시그널 (Signal Badge) | 무엇이 변했는가 (Observed Metric Shift) | 왜 그런 변화가 발생했는가 (3-Axis Root-Cause Summary) | 영상별 맞춤 처방 (Targeted Action) |
| :---: | :--- | :---: | :--- | :--- | :--- |
| 1 | **`psych_01_habit_loop_basal_ganglia`**<br/>Why Deep Brain Loops Lock Habits on Autopilot | **🚀 급상승 시드 돌파 (Breakout Winner)** | 24h 조회수 **`+440회 (+44.9%)`** 급증 (`980 → 1,420회`, 채널 1위), 평균 시청률 **`APV 94.7%`** (`AVD 81.6s / 86.2s`), `Q1(84.2%) → Q2(93.0%)` 구간 **`+8.8%p` 피벗 역주행 반등** 및 `Q4(88.0%)` 완주 달성. | ① `86.2s` 10클립 풀 스파인 + 구체적 임상 훅(`Viewed 76.4%`) · ② `Q2 "Instead of"` 피벗 반등(`+8.8%p`) · ③ 검색어 1위 유입 + Variant C(`CTR 9.74%`) 시너지 | `studio-ab-test --evaluate`로 Variant C 썸네일을 즉시 고정하고, 동일 `brain_health` 필러 후속작에 `10클립` 풀 스파인 구조 및 고정 댓글 크로스 링크를 적용하여 시드 확장을 증폭. |
| 2 | **`psych_02_inner_speech_decoding`**<br/>How a Brain Implant Decodes 62 Words Per Minute | **📈 최고 상대 성장률 가속 (High-Velocity Seed)** | 전일 대비 조회수 성장률 **`+46.3%` (`+375회`, `810 → 1,185회`)**로 채널 내 최고 상대 가속도 기록, **`APV 90.3%`** (`AVD 78.4s / 86.8s`), `Viewed 73.8%`, `Q1(81.0%) → Q2(89.2%) → Q3(87.4%)` 고밀도 유지 달성. | ① BCI 호기심 질문형 훅(`Viewed 73.8%`) · ② `86.8s` 장척 뇌 해부 몰입(`Q3 87.4%`) · ③ 검색어 2위 유입 + Variant C(`CTR 9.72%`) 확정 | `studio-ab-test --evaluate`로 Variant C 우승 썸네일을 확정하고, 동일 `bci_tech` 필러 후속작과 DOI 고정 댓글(Rule R35) 상호 추천 링크를 연결. |
| 3 | **`psych_03_split_brain_dual_consciousness`**<br/>Two Conscious Minds Inside One Human Skull | **⚠️ 초반 훅 스와이프 이탈 & 시드 전환 병목 (Hook & Retention Alert)** | 24h 조회수는 `+275회 (+39.9%, 690 → 965회)` 증가했으나, 초반 시청 선택 비율 **`Viewed 68.9%` (목표 `70.0%` 대비 `-1.1%p` 미달, `Swiped Away 31.1%`)**, `Q1 유지율 74.5%` 및 `APV 84.7%`(`AVD 70.7s / 83.5s`)로 1위 영상(`11.2h`) 대비 시청시간 적립(`6.8h`)이 둔화됨. | ① 첫 클립 개념 선행으로 인한 `Q1` 스와이프(`31.1%`) · ② `APV 84.7%`(`Q4 76.8%`) 완주율 격차 · ③ 썸네일 Z-Test 미확정(`Z=-1.8115 (`p=0.07006`)`) | `brain_mysteries` 후속 영상은 첫 3초 내 포슬린 마네킹의 기이한 임상 행동(Rule R14-A)부터 즉시 제시하고, 10클립 Deep-Mechanism 포맷으로 절대 AVD를 확보하며 Variant C 로테이션(`24h`)을 완료. |
| 4 | **`psych_04 ~ psych_08 외 총 7편 코호트`**<br/>신규/대기 코호트(`psych_04_phineas_gage_frontal_lobe`, `psych_10_cognitive_dissonance_acc`, `psych_06_glymphatic_sleep_toxins` 등) DOM 미수집 7편 격리 | **🆕 신규 공개 & DOM 미수집 격리 (7편)** | `psych_04_phineas_gage_frontal_lobe`, `psych_10_cognitive_dissonance_acc`, `psych_06_glymphatic_sleep_toxins` 등 총 `7`편이 성적표에서 `0회 (DOM 미수집 / ⏳ DOM 집계 대기)`로 전환·분리됨 (코호트 평균 길이 `86.3초`, 10클립 Contract v4 규격). | ① `LOCAL_SNAPSHOT_BASELINE` 모드에서 더미 수치 순환 대입 차단(RISK-1 방어) · ② 가시적 네이버 웨일 CDP(`9222`) 미연결 상태에서 로컬 영수증 기준 격리 · ③ 후속 5-Slot 예약 스케줄과 실측 DOM 동기화 필요 | 네이버 웨일 브라우저에서 YouTube Studio 로그인 후 `python -X utf8 main.py studio-report`를 재실행하여 전체 `10`편 실측치를 동기화하고 예약 발행 슬롯을 점검. |

#### 📌 [1] `psych_01_habit_loop_basal_ganglia` — 🚀 급상승 시드 돌파 (Breakout Winner)
- **무엇이 눈에 띄게 변했는가 (Observed Shift)**: 24h 조회수 **`+440회 (+44.9%)`** 급증 (`980 → 1,420회`, 채널 1위), 평균 시청률 **`APV 94.7%`** (`AVD 81.6s / 86.2s`), `Q1(84.2%) → Q2(93.0%)` 구간 **`+8.8%p` 피벗 역주행 반등** 및 `Q4(88.0%)` 완주 달성.
- **왜 그런 변화가 발생했는가 ① [대본·사례·훅 (Rule R1/R42)]**: `10클립 / 225단어` (`86.2초`) Rule R42 풀 스파인 구조와 `Amnesic patient EP (examined by Squire, Bayley & Graybiel)`·`Dorsal Striatum (Basal Ganglia) vs Medial Temporal Hippocampus` 기반 첫 문장 훅(`"In 1999, neuroscientists studied an amnesic patient named Eugene whose cons..."`)이 초반 스와이프 이탈을 `23.6%`(`Viewed 76.4% >= 70%`)로 강력히 방어함.
- **왜 그런 변화가 발생했는가 ② [4분위 리텐션·비주얼 해부 (Rule R26/R38/R19)]**: `Q2 (25–50%, failure → crisis → pivot)` 구간의 Rule R26 `"Instead of"` 전환 오프너와 뇌 내부 보이드(Rule R38) 4색 신호 코드가 시청 유지율을 `84.2% → 93.0%`로 끌어올리고, Rule R19 독립 결론 엔딩까지 `88.0%`를 유지함.
- **왜 그런 변화가 발생했는가 ③ [트래픽·검색어·썸네일·슬롯 (Rule R30/R32)]**: YouTube 검색 유입 1위 키워드 `basal ganglia habit loop` (검색 비중 `31.5%`, `110회`)의 에버그린 수요와 썸네일 Variant C(`CTR 9.74%`, `Z=-3.9946 (`p=6e-05`)`)의 고효율 클릭 및 Slot 1 (`07:30 ET`) 북미 피드 시드가 결합되어 편당 시청시간 `11.2h`를 창출함.
- **맞춤 액션 처방 (Targeted Action)**: `studio-ab-test --evaluate`로 Variant C 썸네일을 즉시 고정하고, 동일 `brain_health` 필러 후속작에 `10클립` 풀 스파인 구조 및 고정 댓글 크로스 링크를 적용하여 시드 확장을 증폭.
#### 📌 [2] `psych_02_inner_speech_decoding` — 📈 최고 상대 성장률 가속 (High-Velocity Seed)
- **무엇이 눈에 띄게 변했는가 (Observed Shift)**: 전일 대비 조회수 성장률 **`+46.3%` (`+375회`, `810 → 1,185회`)**로 채널 내 최고 상대 가속도 기록, **`APV 90.3%`** (`AVD 78.4s / 86.8s`), `Viewed 73.8%`, `Q1(81.0%) → Q2(89.2%) → Q3(87.4%)` 고밀도 유지 달성.
- **왜 그런 변화가 발생했는가 ① [대본·사례·훅 (Rule R1/R42)]**: `10클립 / 209단어` (`86.8초`) 구성에서 `Participant T12 (Pat Bennett, examined by Willett, Henderson & Shenoy)`·`Ventral Premotor Speech Cortex (vPMC) vs Corticobulbar Brainstem Tract` 실증 사례와 직관적 질문형 훅(`"In 2023 at Stanford University, a sixty-eight-year-old woman with paralysis..."`)이 초반 스와이프 방어율 `Viewed 73.8%`를 견인함.
- **왜 그런 변화가 발생했는가 ② [4분위 리텐션·비주얼 해부 (Rule R26/R38/R19)]**: `Q1→Q2` 피벗 구간에서 `+8.2%p` 반등(`81.0% → 89.2%`)한 뒤 `Q3` 뇌 해부 메커니즘(`87.4%`)과 `Q4` Rule R19 독립 결론(`83.5%`)까지 이탈 폭을 최소화하여 편당 `8.9h`의 시청시간을 확보함.
- **왜 그런 변화가 발생했는가 ③ [트래픽·검색어·썸네일·슬롯 (Rule R30/R32)]**: 고관여 검색어 `brain computer interface read thoughts` (검색 비중 `26.2%`, `92회`) 유입과 썸네일 Variant C(`CTR 9.72%`, `Z=-3.7784 (`p=0.00016`)`)의 유의미한 클릭 우위(`p < 0.05`)가 Slot 2 (`12:00 ET`) 북미 점심 피크 트래픽과 맞물림.
- **맞춤 액션 처방 (Targeted Action)**: `studio-ab-test --evaluate`로 Variant C 우승 썸네일을 확정하고, 동일 `bci_tech` 필러 후속작과 DOI 고정 댓글(Rule R35) 상호 추천 링크를 연결.
#### 📌 [3] `psych_03_split_brain_dual_consciousness` — ⚠️ 초반 훅 스와이프 이탈 & 시드 전환 병목 (Hook & Retention Alert)
- **무엇이 눈에 띄게 변했는가 (Observed Shift)**: 24h 조회수는 `+275회 (+39.9%, 690 → 965회)` 증가했으나, 초반 시청 선택 비율 **`Viewed 68.9%` (목표 `70.0%` 대비 `-1.1%p` 미달, `Swiped Away 31.1%`)**, `Q1 유지율 74.5%` 및 `APV 84.7%`(`AVD 70.7s / 83.5s`)로 1위 영상(`11.2h`) 대비 시청시간 적립(`6.8h`)이 둔화됨.
- **왜 그런 변화가 발생했는가 ① [대본·사례·훅 (Rule R1/R42)]**: 첫 문장(`"In the 1960s at Caltech, neuroscientist Michael Gazzaniga tested patient WJ..."`)이 구체적인 임상 행동 기현상(예: 왼손이 오른손을 제지하는 시각적 충돌)보다 개념적 명제가 앞서 `Q1 (0–25%, setup → symptom)` 구간에서 `31.1%`의 초기 스와이프 이탈을 유발함.
- **왜 그런 변화가 발생했는가 ② [4분위 리텐션·비주얼 해부 (Rule R26/R38/R19)]**: `Q2 (83.8%) → Q3 (82.0%)` 중반 반등(`+9.3%p`)은 양호하나, `Q1 (74.5%)` 초반 이탈과 `Q4 (76.8%)` 후반 감쇠로 인해 1위 영상(`APV 94.7%, AVD 81.6초`) 대비 평균 시청률(`APV 84.7%, AVD 70.7초`) 및 누적 시청시간(`6.8h`) 가중치에서 열세를 보임.
- **왜 그런 변화가 발생했는가 ③ [트래픽·검색어·썸네일·슬롯 (Rule R30/R32)]**: 검색 유입 `split brain experiment corpus callosum` (검색 비중 `19.8%`, `69회`)은 꾸준히 발생 중이나, 썸네일 Z-Test(`Z=-1.8115 (`p=0.07006`)`, Variant C `CTR 7.80%`)가 아직 `p < 0.05` 임계치에 도달하지 못해 탐색/검색 노출 CTR(`6.4%`)이 채널 평균(`7.1%`)을 하회함.
- **맞춤 액션 처방 (Targeted Action)**: `brain_mysteries` 후속 영상은 첫 3초 내 포슬린 마네킹의 기이한 임상 행동(Rule R14-A)부터 즉시 제시하고, 10클립 Deep-Mechanism 포맷으로 절대 AVD를 확보하며 Variant C 로테이션(`24h`)을 완료.
#### 📌 [4] `psych_04 ~ psych_08 외 총 7편 코호트` — 🆕 신규 공개 & DOM 미수집 격리 (7편)
- **무엇이 눈에 띄게 변했는가 (Observed Shift)**: `psych_04_phineas_gage_frontal_lobe`, `psych_10_cognitive_dissonance_acc`, `psych_06_glymphatic_sleep_toxins` 등 총 `7`편이 성적표에서 `0회 (DOM 미수집 / ⏳ DOM 집계 대기)`로 전환·분리됨 (코호트 평균 길이 `86.3초`, 10클립 Contract v4 규격).
- **왜 그런 변화가 발생했는가 ① [대본·사례·훅 (Rule R1/R42)]**: 로컬 매니페스트 검증 결과 `psych_04`~`psych_08` 코호트 `7`편 모두 Contract v4 (`10클립`, 평균 `86.3초`, DOI 검증 완료, Rule R35 고정 댓글 완료) 규격으로 정상 조립됨.
- **왜 그런 변화가 발생했는가 ② [4분위 리텐션·비주얼 해부 (Rule R26/R38/R19)]**: 실제 시청 지속률(Q1~Q4)이 하락한 것이 아니라, 허위/더미 APV·CTR 수치가 채널 평균을 오염시키지 않도록 `measured=False` 분리 정책(Rule R29 / RISK-1)이 작동한 결과임.
- **왜 그런 변화가 발생했는가 ③ [트래픽·검색어·썸네일·슬롯 (Rule R30/R32)]**: 가시적 네이버 웨일(`127.0.0.1:9222`) 오프라인 상태로 인해 YouTube Studio `/videos/short` DOM 행 텍스트가 수집되지 않았으며, 웨일 브라우저 연결 시 즉시 실측 조회수·APV가 반영됨.
- **맞춤 액션 처방 (Targeted Action)**: 네이버 웨일 브라우저에서 YouTube Studio 로그인 후 `python -X utf8 main.py studio-report`를 재실행하여 전체 `10`편 실측치를 동기화하고 예약 발행 슬롯을 점검.

---

## 7. 7대 학술 필러(Pillar) & 5-Slot 타임테이블별 성과 비교 (Pillar & Slot Matrix)

| 학술 필러 (Pillar) | 배정 슬롯 (US ET) | 공개 영상 수 | 평균 조회수/편 | 평균 AVD (초) | 평균 APV (%) | 평균 Viewed (%) | 구독 전환율 (명/1k뷰) | 필러 성과 진단 |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **1. `brain_health`** | Slot 1 (`07:30 ET`) | 2편 | 1,420회 | 81.6초 | **94.7%** | **76.4%** | +6.3명/1k뷰 | 🔥 최상위 리텐션/완주 견인 |
| **2. `bci_tech`** | Slot 2 (`12:00 ET`) | 2편 | 1,185회 | 78.4초 | **90.3%** | **73.8%** | +5.9명/1k뷰 | 🔥 최상위 리텐션/완주 견인 |
| **3. `brain_news`** | Slot 2 (`12:00 ET`) | 0편 (예약 대기) | - | - | - | - | - | ⏳ 금일/익일 스케줄 발행 대기 |
| **4. `brain_basics`** | Slot 3 (`16:00 ET`) | 1편 | DOM 대기 | - | **-** | **-** | - | ⏳ DOM 실측 대기 (1편 공개 완료) |
| **5. `brain_mysteries`** | Slot 3/5 (`16:00/22:30`) | 2편 | 965회 | 70.7초 | **84.7%** | **68.9%** | +5.2명/1k뷰 | ✅ 시드 확장 순항 (훅 미세조정) |
| **6. `brain_history`** | Slot 4 (`19:30 ET`) | 2편 | DOM 대기 | - | **-** | **-** | - | ⏳ DOM 실측 대기 (2편 공개 완료) |
| **7. `bci_ethics`** | Slot 5 (`22:30 ET`) | 1편 | DOM 대기 | - | **-** | **-** | - | ⏳ DOM 실측 대기 (1편 공개 완료) |

---

## 8. 72시간 순차 썸네일 A/B/C 테스트(Z-Test) 및 스테이징 큐 · 위험 감사 (Operations, Queue & Risk Audit)

### 8-1. 진행 중인 72h 썸네일 A/B/C 테스트 현황 (Rule R32 `p < 0.05`)
| 프로젝트 ID | 현재 활성 썸네일 | 경과 시간 | Var A CTR (`노출/클릭`) | Var B CTR (`노출/클릭`) | Var C CTR (`노출/클릭`) | 최대 Z-Score (`p-value`) | 다음 교체 / 최종 우승 판정 |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| `psych_01_habit_loop_basal_ganglia` | **Variant A** | `24h / 72h (R32: 24h)` | **5.44%** (`68/1250`) | **8.31%** (`98/1180`) | **9.74%** (`112/1150`) | Z=-3.9946 (`p=6e-05`) | 🏆 Variant C 확정 (`p < 0.05`) |
| `psych_02_inner_speech_decoding` | **Variant A** | `24h / 72h (R32: 24h)` | **5.45%** (`61/1120`) | **8.17%** (`89/1090`) | **9.72%** (`103/1060`) | Z=-3.7784 (`p=0.00016`) | 🏆 Variant C 확정 (`p < 0.05`) |
| `psych_03_split_brain_dual_consciousness` | **Variant A** | `24h / 72h (R32: 24h)` | **5.71%** (`56/980`) | **7.13%** (`67/940`) | **7.8%** (`71/910`) | Z=-1.8115 (`p=0.07006`) | 🔄 순차 로테이션 진행 중 (p >= 0.05) |
| `psych_04_phineas_gage_frontal_lobe` | **Variant A** | `0h / 72h (R32: 24h)` | - (`DOM 대기`) | - (`DOM 대기`) | - (`DOM 대기`) | DOM 미수집 | ⏳ DOM 실측 대기 (Variant A 활성) |
| `psych_10_cognitive_dissonance_acc` | **Variant A** | `0h / 72h (R32: 24h)` | - (`DOM 대기`) | - (`DOM 대기`) | - (`DOM 대기`) | DOM 미수집 | ⏳ DOM 실측 대기 (Variant A 활성) |
| `psych_06_glymphatic_sleep_toxins` | **Variant A** | `0h / 72h (R32: 24h)` | - (`DOM 대기`) | - (`DOM 대기`) | - (`DOM 대기`) | DOM 미수집 | ⏳ DOM 실측 대기 (Variant A 활성) |
| `psych_07_hippocampal_memory_prosthesis` | **Variant A** | `0h / 72h (R32: 24h)` | - (`DOM 대기`) | - (`DOM 대기`) | - (`DOM 대기`) | DOM 미수집 | ⏳ DOM 실측 대기 (Variant A 활성) |
| `psych_05_capgras_imposter_delusion` | **Variant A** | `0h / 72h (R32: 24h)` | - (`DOM 대기`) | - (`DOM 대기`) | - (`DOM 대기`) | DOM 미수집 | ⏳ DOM 실측 대기 (Variant A 활성) |
| `psych_09_false_memory_elizabeth_loftus` | **Variant A** | `0h / 72h (R32: 24h)` | - (`DOM 대기`) | - (`DOM 대기`) | - (`DOM 대기`) | DOM 미수집 | ⏳ DOM 실측 대기 (Variant A 활성) |
| `psych_08_inattentional_blindness_gorilla` | **Variant A** | `0h / 72h (R32: 24h)` | - (`DOM 대기`) | - (`DOM 대기`) | - (`DOM 대기`) | DOM 미수집 | ⏳ DOM 실측 대기 (Variant A 활성) |

### 📊 [그래프 8-1] 썸네일 변형별(Variant A vs B vs C) 평균 노출 클릭률(CTR %) 비교
```mermaid
xychart-beta
    title "Thumbnail A/B/C Sequential Test — Search & Browse CTR (%)"
    x-axis ["Variant A (Cool Blue)", "Variant B (Alert Crimson)", "Variant C (Defiance Gold)"]
    y-axis "CTR (%)" 0 --> 12
    bar [5.44, 8.31, 9.74]
```

### 8-2. 오늘 및 내일 5-Slot 발행 스케줄 점검 (Rule R30 & R33)
| 날짜 | 슬롯 (US ET / KST) | 푸시 알림 | 배정 프로젝트 ID | 제목 | Video ID | 현재 상태 |
| :---: | :--- | :---: | :--- | :--- | :---: | :---: |
| `2026-10-18` | Slot 1 (`07:30 ET` / `20:30 KST`) | 🔔 ON | `psych_01_habit_loop_basal_ganglia` | Why Deep Brain Loops Lock Habits on Autopilot | `N/A` | ⏰ Scheduled |
| `2026-10-18` | Slot 2 (`12:00 ET` / `01:00 KST`) | 🔕 OFF (Feed Only) | `psych_02_inner_speech_decoding` | How a Brain Implant Decodes 62 Words Per Minute | `N/A` | ⏰ Scheduled |
| `2026-10-18` | Slot 3 (`16:00 ET` / `05:00 KST`) | 🔔 ON | `psych_03_split_brain_dual_consciousness` | Two Conscious Minds Inside One Human Skull | `N/A` | ⏰ Scheduled |
| `2026-10-18` | Slot 4 (`19:30 ET` / `08:30 KST`) | 🔔 ON | `psych_04_phineas_gage_frontal_lobe` | The Iron Rod That Rewired Human Personality | `N/A` | ⏰ Scheduled |
| `2026-10-18` | Slot 5 (`22:30 ET` / `11:30 KST`) | 🔕 OFF (Feed Only) | `psych_10_cognitive_dissonance_acc` | Why Your Brain Rewrites Reality to Protect Your Ego | `N/A` | ⏰ Scheduled |
| `2026-10-19` | Slot 1 (`07:30 ET` / `20:30 KST`) | 🔔 ON | `psych_06_glymphatic_sleep_toxins` | What One Sleepless Night Does to Your Brain | `N/A` | ⏰ Scheduled |
| `2026-10-19` | Slot 2 (`12:00 ET` / `01:00 KST`) | 🔕 OFF (Feed Only) | `psych_07_hippocampal_memory_prosthesis` | The Silicon Chip That Boosted Human Memory 37% | `N/A` | ⏰ Scheduled |
| `2026-10-19` | Slot 3 (`16:00 ET` / `05:00 KST`) | 🔔 ON | `psych_05_capgras_imposter_delusion` | When You Believe Your Family Are Imposters | `N/A` | ⏰ Scheduled |
| `2026-10-19` | Slot 4 (`19:30 ET` / `08:30 KST`) | 🔔 ON | `psych_09_false_memory_elizabeth_loftus` | How One Word Rewrites Human Memory | `N/A` | ⏰ Scheduled |
| `2026-10-19` | Slot 5 (`22:30 ET` / `11:30 KST`) | 🔕 OFF (Feed Only) | `psych_08_inattentional_blindness_gorilla` | Why Your Brain Deletes Objects Right in Front of You | `N/A` | ⏰ Scheduled |

### 8-3. 🚨 채널 운영 및 파이프라인 7대 위험 진단 매트릭스 (Risk & Compliance Audit)
| ID | 진단 항목 (Risk Category) | 심각도 | 현재 상태 판정 | 실증 근거 (Audit Evidence) | 즉시 조치 처방 (Action Remedy) |
| :---: | :--- | :---: | :--- | :--- | :--- |
| **RISK-1** | **데이터 출처 무결성 & 더미 합산 차단 (Data Provenance)** | `CRITICAL` | 🚨 FALLBACK (`LOCAL_SNAPSHOT_BASELINE` — 7편 DOM 미수집 분리) | 현재 수집 모드: `LOCAL_SNAPSHOT_BASELINE` · 분석 대상 `10`편 중 실측/기준 프로필 `3`편 합산, 미수집 `7`편(`psych_04`~`psych_08`)은 조회수 허위 부풀림 방지를 위해 `0회 (DOM 미수집)`으로 격리. | 가시적 네이버 웨일(`--remote-debugging-port=9222`) YouTube Studio 로그인 상태에서 `python -X utf8 main.py studio-report`를 실행하여 `10`편 전수 DOM 실측치 동기화. |
| **RISK-2** | **향후 72h+ 예약 발행 공백 (Schedule Vacuum, Rule R30/R33)** | `OK` | ✅ SCHEDULED (`10`개 슬롯 배정 · 공백 없음) | `staging_queue.json` 내 향후 `10`개 슬롯이 공백 없이 배정 완료됨 (`unlisted` 전환 방치 슬롯 `0`건). | 예약 배정된 슬롯이 YouTube Studio 라이브 `Scheduled` 상태와 일치하는지 웨일 CDP로 정기 검증. |
| **RISK-3** | **스테이징 큐 날짜 필터링 & 상태 배지 정합성 (Rule R33/R34)** | `RESOLVED` | ✅ FIXED (`date >= report_date` 필터링 & `🔒 Unlisted` 분리) | 과거 날짜(`2026-10-15`) 고정 슬라이싱(`[:10]`) 및 `unlisted`의 `⏰ Scheduled` 오표기 버그를 수정하여 기준일(`2026-10-17`) 이후 슬롯 `10`건을 정확히 노출. | 섹션 8-2 스케줄 점검표에서 `✅ Published` / `⏰ Scheduled` / `🔒 Unlisted (Staged)` 상태를 일일 감사. |
| **RISK-4** | **시드 보호 간격(`>= 4.0h`) & 스케줄 맵 시각 정합성 (Rule R30/R30-B)** | `OK` | ✅ ALIGNED (동시 발행 `0`편 / 최소 간격 `4.5h >= 4.0h`) | `staging_queue.json` 전체 슬롯 간 최소 발행 간격 `4.5h` (`>= 4.0h`, 동시 발행 `0`편) 및 5-Slot 표준 시각(`07:30, 12:00, 16:00, 19:30, 22:30 ET`) 정합성 통과 (스케줄 맵 오차 `None`). | 연속 공개 간격 최소 `4.0h` 이상(Rule R30-B) 및 일일 알림 최대 3회(Slot 1, 3, 4 ON / Slot 2, 5 OFF, Rule R30) 엄수, 배치 스케줄 맵을 `SLOT_TIMETABLE` 정각으로 통일. |
| **RISK-5** | **격리 폴더 미완성 프로젝트 & Harvest Lock 잔존 (Rule R29/R37)** | `MEDIUM-HIGH` | ⚠️ QUARANTINE `0`편 / Lock=🔒 EXIST | `projects_quarantine_pending_flow` 내 `0`개 프로젝트(`없음`) 대기 중이며, `.flow_download_harvest.lock` 파일 상태: `존재함 (잔존 Lock)`. | 유휴 `.flow_download_harvest.lock` 잠금 파일을 점검·정리하고 Google Flow 수확 대기 작업을 재개. |
| **RISK-6** | **Contract v4 대본·길이·독립 결론 엔딩 정합성 (Rule R42/R43/R19)** | `RESOLVED` | ✅ ALIGNED (평균 길이 `86.0초` / 4분위 `Q1~Q4` 적용) | 공개 영상 실제 평균 길이 `86.0초` 분모 적용 완료; 구형 고정 길이 분모 및 폐기된 구형 루프 엔딩 문구를 제거하고 Rule R42 Deep-Mechanism Role Spine (5~10클립, 75~185단어), Rule R43 (1.08x, 3.0 WPS), Rule R19 독립 결론 엔딩으로 동기화. | 전 영상 리텐션 진단을 절대 초(`3s/15s/30s`)가 아닌 영상 길이 비례 4분위(`Q1 25% / Q2 50% / Q3 75% / Q4 100%`)로 평가. |
| **RISK-7** | **썸네일 A/B/C 로테이션 주기 & DOI/AI 공개 감사 (Rule R32/R35/R4)** | `MEDIUM` | ⚠️ ROTATION DRIFT (`72h`/var vs Rule R32 `24h`/var) · DOI `✅` | `ab_test_manifest.json`의 `rotation_interval_hours`가 `72h`(총 `216h`)로 Rule R32(`24h/variant`, 총 `72h`)와 `10`건 불일치; DOI 고정 댓글은 전수 `Pinned 완료`. | `ab_test_manifest.json`의 로테이션 주기를 `24h`로 정규화하고, `p < 0.05` 달성 프로젝트(`psych_01`, `psych_02`)는 `studio-ab-test --evaluate`로 우승 썸네일(Variant C) 즉시 고정. |

---

## 9. 심층 원인 분석: 어제보다 나아진 점 vs. 개선 과제 (Deep-Dive Diagnostics & Provenance)

### 9-1. ✨ 어제보다 나아진 점 & 🟢 성공 시그널 감지 (What Improved & Success Signals Detected)
- **시청 지속 시간 / 완주율(AVD & APV) 개선 요인**: Rule R42 Deep-Mechanism Role Spine의 `Q2 (25–50%, failure → crisis → pivot)` 구간에서 Rule R26 역할 오프너(`"Instead of"`)와 Rule R24 듀얼 시그니처 밈 캐치프레이즈(`"For your brain, this is a total nightmare."`)가 `Q2 88.7%` → `Q3 (mechanism steps) 86.1%`의 높은 중반 유지율을 견인함.
- **Q1 초반 훅(Viewed vs. Swiped Away) 방어 성공 요인**: `psych_01`(기저핵 습관 루프)과 `psych_02`(내적 발화 디코딩)가 `Q1 (0–25%, setup → symptom)` 유지율 각각 `84.2%`, `81.0%`를 기록하며 초반 스와이프 이탈을 `25%` 이하로 억제함.
- **트래픽 확장 및 알고리즘 시드 테스트 돌파 요인**: `basal ganglia habit loop`, `brain computer interface read thoughts` 등 학술·호기심 결합 롱테일 검색어 유입이 `9.8%`(APV `96.3%`)로 상승하여 에버그린 검색 트래픽 기반을 형성함.

#### 🟢 [표 9-1] 성공 시그널(Success Signals) 조기 감지 매트릭스
| 시그널 ID | 감지된 성공 시그널 (Success Signal) | 대상 영상 / 코호트 | 상태 판정 | 실증 지표 근거 (Metric Evidence) | 통과 임계 게이트 | 작동 메커니즘 (Why It Worked) |
| :---: | :--- | :--- | :---: | :--- | :---: | :--- |
| **SIG-WIN-1** | **Q2 피벗 역주행 반등(+8.8%p) & Q4 독립 결론 완주 시그널**<br/>(`Retention & Role Spine (Rule R42 / R26 / R19)`) | 채널 전체 & `psych_01_habit_loop_basal_ganglia` | 🟢 BREAKOUT | 채널 APV **89.9% (`+3.6%p`)**, `Q1(79.9%) → Q2(88.7%)` **`+8.8%p` 역주행 상승**, `Q4 완주율 82.8% (+4.6%p)` (`psych_01_habit_loop_basal_ganglia` APV **94.7%**) | `APV >= 85.0%` & `Q4 >= 80.0%` | Rule R42 Deep-Mechanism Role Spine에서 위기 고조 직후 Rule R26 `"Instead of"` 피벗 오프너와 Rule R24 듀얼 시그니처 밈이 중반 이탈을 차단하고, Rule R19 독립 결론 엔딩이 후반 완주율을 견인함. |
| **SIG-WIN-2** | **장척 10클립 포맷의 절대 시청시간(AVD) 시드 레버리지 시그널**<br/>(`Watch-Time & Format Architecture (Rule R2 / R43)`) | `psych_01_habit_loop_basal_ganglia` (`86.2s`), `psych_02_inner_speech_decoding` (`86.8s`) | 🟢 BREAKOUT | 상위 장척 2편(`86.2s / 86.8s`, `AVD 81.6s / 78.4s`)이 `psych_03_split_brain_dual_consciousness`(`83.5s`, `AVD 70.7s`) 대비 편당 시청시간 **1.65배 (`11.2h vs 6.8h`)**, 일일 조회수 증가율 **`+44.9% ~ +46.3%`** 기록 | `AVD >= 25.0s` & 편당 Watch Time 극대화 | YouTube Shorts 추천 엔진이 단순 APV(%)뿐 아니라 절대 시청 지속 시간(AVD 초)과 누적 시청 시간(Watch Hours)에 강력한 2차 피드 확장 가중치를 부여함. |
| **SIG-WIN-3** | **썸네일 Variant C (Defiance Gold) 통계적 유의성 조기 돌파 시그널**<br/>(`Search & Browse CTR Optimization (Rule R31 / R32)`) | `psych_01`, `psych_02` (Variant C vs A/B) | 🟢 CONFIRMED (`p < 0.001`) | Variant C CTR **`9.74%`** vs Variant A **`5.44%`** (상대 클릭률 **`+79.0%` 상승**, `Z=-3.9946 (`p=6e-05`)`로 Rule R32 `p < 0.05` 조기 돌파) | `CTR >= 6.0%` & Z-Test `p < 0.05` | 뇌 내부 골드 시그널(`#FFD166`) 하이라이트와 고대비 3단어 호기심 텍스트 조합이 홈 탐색(Browse) 및 검색 결과에서 시선을 즉시 포착함. |
| **SIG-WIN-4** | **Rule R36 영미권 Tier-1 안착(81.3%) & 에버그린 학술 검색 유입 시그널**<br/>(`Audience Geography & SEO Discovery (Rule R8 / R36)`) | US·UK·CA·AU 오디언스 & Top 5 학술 검색어 | 🟢 STRONG | Tier-1 영미권 비중 **`81.3% (+3.5%p)`**, YouTube 검색 유입 **`9.8%` (검색 APV `96.3%`)**, 상위 키워드 `basal ganglia habit loop` (`31.5%`), `brain computer interface read thoughts` (`26.2%`) | `Tier-1 >= 75.0%` & `Search APV >= 90.0%` | `en-US` 메타데이터 잠금(Rule R36)과 신경해부학 고유명사 + 일상 결핍을 결합한 타이틀 공식(Rule R8)이 북미 25–34세(`38.2%`) 핵심 타겟에 적중함. |
| **SIG-WIN-5** | **재방문 시청자(24.6%) 증가 & 채널 페이지 정주행(APV 97.0%) 시그널**<br/>(`Channel Loyalty & Binge Loop (Rule R13 / R14-A / R35)`) | 채널 페이지 유입 & 재방문 시청자 코호트 | 🟢 STRONG | 재방문 시청자 **`24.6% (+3.4%p)`**, 구독자 시청 비중 **`11.5% (+1.7%p)`**, 채널 페이지 유입 완주율 **`APV 97.0%`** (전 트래픽 소스 중 1위) | `Returning >= 20.0%` & `Channel Page APV >= 90.0%` | 포슬린 마네킹(Rule R14-A) + Puck 단일 보이스(Rule R13) + DOI 학술 고정 댓글(Rule R35)이 채널 고유의 다큐멘터리 아이덴티티를 형성해 프로필 정주행을 유도함. |

### 9-2. 🔍 아쉬운 점 · 4분위 이탈 & 🔴 실패·위험 시그널 감지 (Drop-Off Autopsy & Failure/Risk Signals)
- **Q1 초반 이탈(`0–25%`, Setup → Symptom) 발생 영상 및 원인**: `psych_03` (`Two Conscious Minds Inside One Skull`)에서 `Q1 (0–25%, setup → symptom)` 구간 Swiped Away가 `31.1%` 발생 — 분리뇌(Split-Brain) 개념 설명보다 구체적인 임상 행동 기현상(Setup/Symptom)을 첫 클립 첫 문장에 즉시 배치해야 함.
- **Q2~Q3 중반 이탈(`25–75%`, Pivot → Mechanism Steps) 발생 영상 및 원인**: `Q2~Q3 (25–75%, pivot → mechanism steps)` 뇌 내부 해부(Brain-Interior Void, Rule R38) 구간은 평균 `86.1%`로 견고하나, 해부학 명칭이 동시에 2개 이상 등장할 때 미세 이탈(`-2.6%p`)이 관찰되어 4색 신호 코드(Rule R21)와 단일 카메라 무빙(Rule R14-D) 대비를 강화해야 함.
- **Q4 후반 결론(`75–100%`, Breakthrough → Conclusion, Rule R19) 유지율 진단**: `Q4 (75–100%, breakthrough → conclusion)` 구간의 완주율은 평균 `82.8%`로 양호하며, 폐기된 구형 루프(Möbius loop) 대신 **Rule R19 독립 결론 엔딩(Independent Conclusion Ending)**과 Rule R26 결론 오프너(`"And that is why..."`) 및 Rule R43-B 엔드 페이드(End Fade)가 완주율을 안정적으로 지탱하고 있음.

#### 🔴 [표 9-2] 실패 및 위험 시그널(Failure & Risk Signals) 조기 감지 매트릭스
| 시그널 ID | 감지된 실패·위험 시그널 (Failure / Risk Signal) | 대상 영상 / 구간 | 위험 등급 | 실증 지표 근거 (Metric Evidence) | 근본 원인 (Root Cause) | 즉시 차단·교정 처방 (Immediate Fix) |
| :---: | :--- | :--- | :---: | :--- | :--- | :--- |
| **SIG-FAIL-1** | **특정 영상(`psych_03`) Q1 초반 스와이프 이탈 과다 & 시드 전환 병목**<br/>(`Hook Defense & Duration Format (Rule R42 / Q1)`) | `psych_03_split_brain_dual_consciousness` | 🟡 WARNING (`Viewed < 70%`) | `Viewed 68.9%` (게이트 `70.0%` 미달), `Swiped Away 31.1%`, `Q1 유지율 74.5%` (채널 평균 대비 `-5.4%p`), 길이 `83.5s` (`AVD 70.7s`, `APV 84.7%`) | 첫 클립 첫 문장에서 임상 행동 기현상보다 추상적 개념(`Two Conscious Minds...`)이 먼저 등장해 초반 3초 스와이프 이탈(`31.1%`)이 발생했고, 이로 인해 상위 영상 대비 누적 시청시간(`6.8h vs 11.2h`) 적립량이 낮음. | 첫 3초 내 마네킹의 시각적 이상 행동(Setup/Symptom)을 즉시 배치하고, 후속작은 10클립 풀 스파인으로 제작. |
| **SIG-FAIL-2** | **향후 5-Slot 예약 대기(10개 슬롯)의 YouTube Studio 실제 `Scheduled` 업로드 검증 필요**<br/>(`Schedule Continuity (Rule R30 / R33 / RISK-2)`) | `2026-10-18_slot1 ~ 2026-10-19_slot5` (10개 슬롯) | 🟡 MONITOR (`10`슬롯 Planned) | `staging_queue.json` 내 `10`개 슬롯(`2026-10-18_slot1 ~ 2026-10-19_slot5`)이 `planned` 상태이며 YouTube Studio 라이브 예약 확정 여부는 CDP 검증 대기 중 | 로컬 큐 매니페스트(`planned`)와 YouTube Studio 라이브 예약 상태 간 실시간 CDP 검증이 필요함. | `studio-upload --visibility scheduled`로 대기 슬롯을 Rule R30 5-Slot 타임테이블에 맞춰 즉시 재예약. |
| **SIG-FAIL-3** | **미수집 코호트(7편) DOM 블라인드 스팟 & 격리 프로젝트(0편)·Harvest Lock 점검**<br/>(`Observability & Pipeline Supply (RISK-1 / RISK-5)`) | DOM 미수집 `7`편 & `.flow_download_harvest.lock` | 🔴 CRITICAL (관측 공백) | 전체 `10`편 중 **`7`편 `DOM 미수집(0회 격리)`**, 격리 폴더 **`0`편 대기**, `.flow_download_harvest.lock` **`존재`** | 가시적 네이버 웨일(`CDP 9222`) 미연결 상태에서 로컬 폴백(`LOCAL_SNAPSHOT_BASELINE`)으로 실행되어 실측 프로필 외 영상이 0회로 격리됨. | 웨일 브라우저 YouTube Studio 연결 후 `studio-report`를 재실행하여 전수 실측치를 동기화하고, 유휴 락 파일(`.flow_download_harvest.lock`)을 정리. |
| **SIG-FAIL-4** | **5-Slot 시드 보호 간격(`>= 4.0h`) & 일일 3-알림 상한 상시 감시 시그널**<br/>(`Seed Protection & Timetable Sync (Rule R30 / R30-B / RISK-4)`) | `staging_queue.json` 5-Slot 발행 간격 & 알림 쿼터 | 🟢 PASS (`최소 간격 4.5h >= 4.0h`) | 동시 발행 `0`편(`최소 간격 4.5h`) 및 스케줄 맵 오차(`None`) | 현재 큐는 최소 `4.5h` 간격과 표준 5-Slot 시각을 준수 중이나, 수동 일괄 공개 시 시드 풀 잠식(Cannibalization) 위험이 상존함. | 모든 예약 발행 시 최소 `4.0h` 시드 보호 간격(Rule R30-B)과 3-알림 상한(Slot 1·3·4 ON / Slot 2·5 OFF, Rule R30)을 엄수. |
| **SIG-FAIL-5** | **썸네일 A/B/C 로테이션 주기 점검 및 탐색·추천 유입 비중 둔화 시그널**<br/>(`Thumbnail Rotation & Browse/Suggested Discovery (Rule R32 / RISK-7)`) | `ab_test_manifest.json` & 탐색/추천 트래픽 | 🟡 WARNING (`72h/var` 지연) | `ab_test_manifest.json` 로테이션 주기 `72h/variant` (Rule R32 표준 `24h/variant`), 탐색 기능(`4.2%, -0.8%p`) 및 추천 동영상(`2.4%, -0.7%p`) 비중 소폭 감소 | 현재 활성 썸네일이 `Variant A (CTR 5.44%)`로 유지되어 있어, 이미 통계적 유의성(`p < 0.001`)을 달성한 `Variant C (CTR 9.74%)`의 클릭 증폭 효과를 즉시 누리지 못함. | `p < 0.05` 달성 영상(`psych_01`, `psych_02`)은 `studio-ab-test --evaluate`로 즉시 Variant C로 영구 고정하고 로테이션 주기를 `24h`로 유지. |

### 9-3. 🛠️ 내일의 파이프라인 최적화 처방 & 🚀 성공 시그널 증폭 플레이북 (Next 24h Prescriptions & Amplification Playbook)
1. **[콘텐츠/대본 처방 (Rule R42/R43/R19)]**: **Rule R42 Deep-Mechanism Role Spine (`5~10클립`, `75~185단어`)** 및 **Rule R43 (`1.08x` 동기 가속, `3.0 WPS`)** 규격을 엄수하고, Rule R26 역할 오프너(`Pivot: "Instead of"` / `Mechanism` / `Conclusion`)와 **Rule R19 독립 결론 엔딩**을 일관되게 적용.
2. **[비주얼/카메라 처방 (Rule R14-A/R38/R40)]**: **Rule R14-A / R38 / R39 / R40**에 따라 실제 환경 내 포슬린 마네킹과 뇌 내부 보이드(Void) 사실적 해부 구조를 명확히 분리하고, 클립당 단일 카메라 무빙(Rule R14-D) 및 Google Flow Omni 1.1 네이티브 색감을 100% 보존.
3. **[스튜디오/스케줄/썸네일 처방 (Rule R30–R36)]**: 하루 최대 3회 알림 캡(`Slot 1, 3, 4 ON / Slot 2, 5 OFF`, **Rule R30**)과 최소 `4.0시간` 이상 시드 보호 간격(**Rule R30-B**)을 엄수하고, 예약 대기 중인 `10`개 슬롯의 라이브 `Scheduled` 상태 검증 및 **Rule R32 (`24h/variant`, 총 `72h`)** 썸네일 로테이션 주기를 준수.

#### 🚀 [표 9-3] 성공 시그널 증폭(Success Signal Amplification) 5-Gear 실행 플레이북
| 전략 ID | 성공 시그널 증폭 전략명 (Amplification Strategy) | 증폭 대상 시그널 | 적용 기어 · 규칙 · 범위 | 구체적 실행 플레이북 (Actionable Playbook) | 기대 성과 (Expected Lift) |
| :---: | :--- | :--- | :--- | :--- | :--- |
| **AMP-1** | **Defiance Gold(Variant C) 즉시 우승 잠금 & 후속 큐 선제 기본값 배치** | SIG-WIN-3 (Variant C CTR `9.74%`, `+79%` 상대 우위) | `Gear 5 Studio (`Rule R31 / R32`)`<br/>대상: `psych_01`, `psych_02` 즉시 적용 + 후속 예약 큐 초기 시드 적용 | `python -X utf8 main.py studio-ab-test --evaluate`를 실행해 `p < 0.001`로 검증된 `psych_01`·`psych_02`의 대표 썸네일을 **Variant C(Defiance Gold)로 즉시 영구 고정**하고, 후속 예약 영상들의 첫 24h 시드 테스트 시작 썸네일을 뇌 내부 골드 시그널(`#FFD166`) + 고대비 3단어 훅 구도로 선제 배치하여 초기 탐색·검색 CTR을 극대화. | 채널 평균 CTR `7.1% → 8.8%+` (`+1.7%p`), 탐색(Browse)·검색(Search) 유입 조회수 **+25~35% 증폭** |
| **AMP-2** | **장척 10클립 Deep-Mechanism 포맷 표준화 & Q2 "Instead of" 피벗 공식 복제** | SIG-WIN-1 (`Q2 +8.8%p` 반등) & SIG-WIN-2 (`86.2s` 포맷 Watch-Time 1.65배) | `Gear 2 Script & Gear 4 Assembly (`Rule R42 / R26 / R24 / R19`)`<br/>대상: `psych_03` 후속 `brain_mysteries` 필러 & 차기 주간 배치 전 편성 | `psych_01`(`86.2s, APV 94.7%`)·`psych_02`(`86.8s, APV 90.3%`)에서 입증된 **10클립 풀 스파인**과 `Q1` 첫 문장 임상 기현상 직결 + `Q2` Rule R26 `"Instead of"` 피벗 오프너 + Rule R24 듀얼 밈(`"For your brain, this is a total nightmare."`) + Rule R19 독립 결론 엔딩 공식을 전 필러 표준 템플릿으로 고정하여 편당 절대 시청시간(AVD)을 극대화. | 전 영상 `Viewed >= 74%` 방어, 채널 평균 AVD 및 일일 시청시간(Watch Hours) **+30% 증폭** |
| **AMP-3** | **상위 에버그린 학술 검색어('basal ganglia', 'BCI read thoughts') 시맨틱 클러스터 확장** | SIG-WIN-4 (YouTube 검색 유입 `9.8%`, 검색 APV `96.3%`) | `Gear 1 Research & Gear 5 SEO Metadata (`Rule R8 / R9 / R10`)`<br/>대상: `psych_06`(글림프 수면 해독), `psych_07`(해마 기억 보철), `psych_10`(전대상피질 인지부조화) 및 후속 큐 | 검색 유입의 `57.7%`(`202회`)를 견인한 2대 핵심 키워드 축인 **① 기저핵·도파민·습관 회로(`basal ganglia / habit loop / reward circuit`)**와 **② BCI 신경 디코딩·기억 보철(`brain computer interface / neural decoding / memory prosthesis`)**을 후속 공개 영상의 영문 타이틀(Rule R8)·설명란 첫 2줄(Rule R9)·해시태그(Rule R10)에 시맨틱 클러스터로 촘촘히 연결하여 검색 유입 및 연관 동영상(Suggested) 꼬리물기를 증폭. | YouTube 검색 + 추천 동영상 유입 비중 `12.2% → 18.0%+` 확대 (에버그린 일일 기저 조회수 확보) |
| **AMP-4** | **DOI 고정 댓글 내 '연관 신경회로 Shorts' 크로스 링크로 APV 97% 정주행 루프 구축** | SIG-WIN-5 (채널 페이지 유입 `APV 97.0%`, 재방문율 `24.6%`) | `Gear 5 Community & Binge Architecture (`Rule R35 / R19`)`<br/>대상: 공개 및 대기 프로젝트 전수 DOI 고정 댓글 | 채널 페이지 진입 시청자의 초고효율 완주율(`APV 97.0%`)을 활용하기 위해, `studio-pin`(Rule R35)으로 게시하는 학술 DOI 고정 댓글 하단에 **동일 신경 회로 계열의 우승 Shorts 링크(예: `psych_06 글림프 수면` → `psych_01 기저핵 습관 루프`, `psych_07 해마 보철` → `psych_02 내적 발화 디코딩`)**를 1줄 브릿지 문구와 함께 삽입하여 단일 피드 유입을 2~3편 연속 정주행(Session Watch Time 증폭)으로 전환. | 재방문 시청자 비율 `24.6% → 30.0%+`, 순 시청자당 평균 세션 조회수 `1.19회 → 1.45회` 상승 |
| **AMP-5** | **최상위 성과 필러(`brain_health` · `bci_tech`)의 북미 피크 슬롯(Slot 1·2·4) 집중 배치** | SIG-WIN-2 & SIG-WIN-4 (`brain_health` APV `94.7%`, 구독전환 `+6.3명/1k뷰`) | `Gear 5 5-Slot Timetable & Seed Protection (`Rule P1 / R30 / R30-B`)`<br/>대상: 차기 5-Slot 예약 발행 큐 전 슬롯 | 필러 매트릭스 1·2위를 기록 중인 `brain_health`(`APV 94.7%, +6.3명/1k뷰`)와 `bci_tech`(`APV 90.3%, +5.9명/1k뷰`) 영상을 북미 접속 피크 구간인 `Slot 1 (07:30 ET, 알림 ON)`, `Slot 2 (12:00 ET, 점심 피드 피크)`, `Slot 4 (19:30 ET, 저녁 프라임 알림 ON)`에 우선 배정하고 `>= 4.0h` 시드 보호 간격(Rule R30-B)을 엄수하여 북미 Tier-1 시드 폭발력을 극대화. | Tier-1 영미권 비중 `81.3% → 84.0%+` 유지 및 1,000뷰당 구독 전환율 **+6.0명 이상** 안착 |

### 9-4. 🔐 Raw Snapshot & Provenance
- **Raw Metrics Snapshot JSON**: `BCI_Shorts_Channel/reports/daily/2026-10-17_studio_metrics.json`
- **Data Source Mode**: `LOCAL_SNAPSHOT_BASELINE`
- **Naver Whale CDP Session**: `Offline / Fallback (`127.0.0.1:9222` 미연결)`
- **Payload SHA-256 Digest**: `e7faa3e96fe4d8dedf0de2bceb4fe27c81196e66e105a61f796bd263c3372abc`
