# 미국 6대 공신력 뇌과학·심리학 채널 나레이션 정량 해부 보고서 (`n = 160` Videos)

> [!IMPORTANT]
> **핵심 결론 요약 (`2,079`편 모집단 정규화 + `160`편 영문 단어 타임스탬프 `.json3` 전수 실측)**:
> 1. **"처음에 질문(`?`)으로 시작하나?"에 대한 정답**: **무조건 질문이 좋은 것이 아니라, '어떤 질문인가'에 따라 조회수 타율이 `3.55배` 갈린다.**
>    - 상투적 수사 질문 **`Q_generic`** (*"Have you ever wondered...?"*, *"Did you know...?"*, `4.5%`)은 채널 샘플 내 배율 중앙값 **`0.45x`**(카탈로그 배율 **`1.67x`**)로 **7대 오프닝 중 꼴찌**를 기록했다.
>    - 반면 **구체적 조건과 물리·생리적 모순을 압축한 역설 질문 `Q_paradox`** (*"Why can't you tickle yourself?"*, *"What will happen to this weight if you cut the green rope?"*, `11.6%`)는 카탈로그 배율 중앙값 **`5.93x` (평균 `16.29x`)**, 중앙값 조회수 **`2,400,000`회**로 **전체 1위 폭발력**을 기록했다.
> 2. **현재 우리 기본값(`"In 1998 at UCL..."` 연도 선행 `case_stamp`)의 한계 입증**: 미국 6대 채널 쇼츠 `112`편 중 첫 문장에 연도를 먼저 말한 `S_year_first`는 **단 `3.6%`(`4`편)**뿐이며(`@Vsauce`, `@Veritasium`, `@hubermanlab`, `@HealthyGamerGG` 쇼츠 `82`편 중 **`0`편!**), 중앙값 조회수(`217,500`회, **`1.69x`**)가 연도 없이 행동·사건으로 직진한 `S_action_first`(`1,200,000`회, **`4.37x`**)보다 **`5.5배` 낮다**.
> 3. **대학교·논문 권위(`Credibility Stamp`) 최적 등장 시점은 `0초(S1)`가 아니라 `3.5~12.0초(S2~S4)` 브리지다**: `S1(0~3.5s)`에서 **역설 질문(`Q_paradox`) · 통념 파괴(`P_myth_flip`, `5.17x`) · 2인칭 즉시 체험(`T_second_person`, 중앙값 `3.70M`회 1위, `4.83x`)**으로 호기심을 먼저 잠근 뒤, **`S2~S4(3.5~12.0s)`에서 *"To find out why, neuroscientists at [University]..."*로 진입할 때 쇼츠 평균 배율이 `8.85x`(`S1` 즉시 투입 `6.28x` 대비 `+40.9%` 상승)**로 치솟으며, 이는 방금 승인된 **`Rule R72` 실제 대학 드론 비행(`Cut 02~03`)**과 1:1로 맞물린다.

---

## 1. 조사 설계 및 이중 정규화 표본 (`2,079`편 모집단 → `160`편 `.json3` 정밀 표본)

채널 규모 차이(`@Vsauce` 2,300만 구독자 vs `@HealthyGamerGG` 300만 구독자)로 인한 착시를 제거하기 위해 6대 채널의 쇼츠·롱폼 카탈로그 **`2,079`편** 전체 조회수 중앙값을 먼저 구한 뒤, 상위 히트작과 중위권 표본을 층화 추출한 **`160`편(쇼츠 `112`편 `70%` + 롱폼 `48`편 `30%`)**의 단어 단위 타임스탬프 자막을 파싱했다 (`@Research` 상세 로그: [us_neuro_psychology_narration_report.md](../02_Research/us_neuro_psychology_narration_report.md)).

$$\text{Catalog View Multiplier} = \frac{\text{Video Views}}{\text{Channel-Format Full Catalog Median Views}}$$

| 채널 그룹 (`Channel`) | 전문성 및 권위 배경 (`Credentials`) | 쇼츠 모집단 (`n` / 중앙값) | 쇼츠 표본 (`n`) | 롱폼 모집단 (`n` / 중앙값) | 롱폼 표본 (`n`) | 합계 (`Total n`) |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **`@Veritasium`** | Derek Muller, PhD (행동심리·인지착각·과학 다큐 1위) | `96` / `4.55M` | **`23`** | `177` / `11.00M` | **`8`** | **`31`** |
| **`@hubermanlab`** | Dr. Andrew Huberman, PhD (스탠퍼드대 신경생물학 교수) | `98` / `109K` | **`22`** | `151` / `193K` | **`8`** | **`30`** |
| **`@InstituteOfHumanAnatomy`** | 실제 인체 해부학 연구소 (`@theanatomylab`) | `260` / `80.5K` | **`20`** | `150` / `474.5K` | **`8`** | **`28`** |
| **`@HealthyGamerGG`** | Dr. Alok Kanojia, MD (하버드 의대 정신과 전문의) | `260` / `84K` | **`20`** | `159` / `471K` | **`8`** | **`28`** |
| **`@Vsauce`** | Michael Stevens (인지·지각·뇌 역설 쇼츠 절대 강자) | `220` / `8.70M` | **`17`** | `38` / `7.50M` | **`8`** | **`25`** |
| **`@TEDEd` & `@SciShowPsych`** | 학자 감수 피어리뷰 스크립트 대조군 | `24` / `128.5K` | **`10`** | `436` / `447K·89K` | **`8`** | **`18`** |
| **합계 (`Total`)** | **미국 6대 공신력 뇌과학·심리학·해부학 벤치마크** | **`958`** | **`112` (`70%`)** | **`1,111`** | **`48` (`30%`)** | **`160` (`100%`)** |

---

## 2. 첫 문장(`0.0~3.5s`, `S1`) 오프닝 7대 유형 성적표

![미국 6대 채널 첫 문장 오프닝 유형별 조회수 배율 및 점유율](./us_narration_opening_multipliers.png)

미국 쇼츠 `112`편 중 **`93.8%`(`105`편)는 인사말이 `0.0초`(완전 생략)**이며, 첫 `3.5초` 안에 아래 상위 4대 오프닝(`Q_paradox`, `P_myth_flip`, `T_second_person`, `S_action_first` — 합계 점유율 `64.4%`)으로 즉시 진입한다.

| 순위 | 오프닝 유형 (`S1 Category`) | 쇼츠 비중 (`n=112`) | 쇼츠 중앙값 조회수 | 쇼츠 카탈로그 배율 중앙값 (`평균`) | 롱폼 비중 (`n=48`) | 롱폼 카탈로그 배율 중앙값 | 실제 미국 히트 원문 예시 (`Verbatim S1`) |
| :---: | :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **1** | **`Q_paradox`**<br>(구체적 역설·예측 질문 `?`) | `13`편 (`11.6%`) | `2,400,000` | **`5.93x`** (`16.29x`) | `5`편 (`10.4%`) | `3.20x` | • `@Veritasium` (`52M`): *"What will happen to this weight if you cut the green rope?"*<br>• `@hubermanlab` (`7.1M`, `65.1x`): *"Is it true that 'microwave safe' just means the plastic won't melt...?"*<br>• `@Veritasium` (`1.4M`): *"When you lose weight, where does it actually go?"* |
| **2** | **`P_myth_flip`**<br>(통념 파괴·역설 단정문) | `21`편 (`18.8%`) | `1,200,000` | **`5.17x`** (`6.94x`) | `6`편 (`12.5%`) | `2.98x` | • `@Vsauce`: *"Mirrors do not show us a 4th dimension, but they do show what it could do to us."*<br>• `@HealthyGamerGG`: *"It turns out that women don't actually like ripped dudes..."* |
| **3** | **`T_second_person`**<br>(2인칭 즉시 체험·상황 소환) | `21`편 (`18.8%`) | **`3,700,000`** | **`4.83x`** (`9.97x`) | `2`편 (`4.2%`) | `2.37x` | • `@Veritasium` (`36M`): *"If you drop a slinky dangling under its own weight..."*<br>• `@TEDEd` (`7.2M`): *"You're just one Roman Empire history final away from spring break."* |
| **4** | **`S_action_first`**<br>(연도 없는 기묘한 실험·사건 직진) | `17`편 (`15.2%`) | `1,200,000` | **`4.37x`** (`6.17x`) | `12`편 (`25.0%`) | **`6.06x`** (롱폼 1위) | • `@Veritasium` (`53M`): *"These two chain ladders were dropped at exactly the same time, by Cornell Professor Andy Ruina."* |
| **5** | **`F_shock_fact`**<br>(즉각적 신체·뇌 팩트) | `31`편 (`27.7%`) | `602,000` | `4.36x` (`6.06x`) | `21`편 (`43.8%`) | `4.98x` | • `@InstituteOfHumanAnatomy`: *"Fentanyl is extremely effective and dangerous because it binds to mu opioid receptors."* |
| **6** | **`S_year_first`**<br>(`"In [Year]..."` 연도 선행 — **현행 `v8` 기본값**) | **`4`편 (`3.6%`)** | **`217,500`** | **`1.69x`** (`1.72x`) | `2`편 (`4.2%`) | `13.08x` | • `@TEDEd` 역사 쇼츠 3편 + `@InstituteOfHumanAnatomy` 1편(`43K`, `0.53x`). 상위 4개 크리에이터 채널 `82`편 중 **`0`편(`0.0%`)**! |
| **7** | **`Q_generic`**<br>(`"Have you ever...?"` 수사적 질문) | **`5`편 (`4.5%`)** | `1,500,000` | **`1.67x`** (샘플 `0.45x`) | `0`편 (`0.0%`) | — | • *"Have you ever wondered how these form?"* — 시청자 뇌의 예측 회로를 깨우지 못해 샘플 중앙값 **`0.45x`**로 참패. |

---

## 3. 권위 스탬프(`University / Study`) 타이밍, 발화 호흡(`WPM`), 전문용어 및 엔딩 공식

![미국 6대 채널 대학·논문 인용 타이밍, WPM 호흡, 전문용어 Plain-First 격차 및 마지막 5초 공식](./us_citation_timing_and_pacing.png)

### 3-1. 대학·연구진 스탬프 등장 타이밍 (`n = 69`) & `Rule R72` 결합
- **`B1: S1 즉시 투입 (`0.0~3.5s`)`** (`10.1%`): 전체 배율 중앙값 `4.25x` / 쇼츠 평균 `6.28x`.
- **`B2: S2~S4 브리지 투입 (`3.5~12.0s`)`** (`21.7%`): 전체 배율 중앙값 **`5.28x`** / **쇼츠 평균 `8.85x` (`+40.9%` 우위)**!
  - 대표 실측 패턴:
    - `@Vsauce` (`25M`): **S1 (`0.0s`)** *"Here's how to become scary good at finding Waldo."* → **S2 (`3.44s`)** *"In 2015, data scientist Randal Olson used..."*
    - `@Vsauce` (`21M`): **S1 (`0.0s`)** *"This is Inuyama, Japan..."* → **S2 (`6.84s`)** *"It is also home to Kyoto University's Primate Research Institute."*
    - `@HealthyGamerGG` (`565K`, `6.73x`): **S1 (`0.0s`)** *"Depression is a chemical imbalance... why?"* → **S2 (`4.40s`)** *"It's not. So, there's a great paper from Molecular Psychiatry..."*
- **`B4: 중반 증거 투입 (`>25.0s`, 쇼츠 중앙값 `27.0s`)`** (`60.9%`): 현상과 메커니즘 궁금증을 최고조로 끌어올린 뒤 중반부에 결정적 실험 증거를 제시(쇼츠 중앙값 배율 **`7.59x`**).

### 3-2. 미국 쇼츠 발화 속도(`WPM`), 초등 4~5학년 어휘 평이도(`FK 4.6`), 멈춤(`Pause`)의 법칙
- **빠른 훅 진입 후 본문 감속 (`Fast-In, Clear-Body`)**: 첫 5초 평균 **`192.5 WPM`** → 본문 평균 **`183.8 WPM`** (`@Veritasium` `192 → 171 WPM`, `@InstituteOfHumanAnatomy` `198 → 183 WPM`).
- **초단문 & 1~2음절 일상어 `91.6%`**: 절(Clause) 당 중앙값 **`9.0단어`**, 읽기 난이도 **Flesch-Kincaid Grade 중앙값 `4.60`**(미국 초등학교 4~5학년 수준; `@Veritasium` `3.4`, `@HealthyGamerGG` `4.0`).
- **의도적 침묵(`Pause >= 0.30s`)**: 분당 중앙값 **`15.7회`**, 멈춤 길이 중앙값 **`0.45s`**. 특히 **`S1` 질문/역설 직후(`~3.0s`)**와 **`"But here's the catch"` 반전 직전**에 `0.40~0.50s` 멈춤을 주어 시청자가 머릿속으로 답을 예측하게 만든다.

### 3-3. 미국 네이티브 전환구 Top 10 vs `0.0%` AI 클리셰

| 미국 6대 채널 실제 최다 구어 전환구 (`160`편 빈도) | `160`편에서 **`0~1`회(`0.0~0.6%`)** 나온 금지 대상 AI 클리셰 |
| :--- | :--- |
| 1. **`in fact` / `actually`** (`477`회, 영상의 `48.8%`)<br>2. **`in other words / essentially / basically`** (`195`회, `26.9%`)<br>3. **`and that's why / that's because`** (`183`회, `28.7%`)<br>4. **`for example / like if`** (`110`회, `23.8%`)<br>5. **`except / until`** (`102`회, `20.6%`)<br>6. **`even though / even if`** (`92`회, `21.9%`)<br>7. **`instead (of)`** (`78`회, `21.9%`)<br>8. **`think about (it / how)`** (`50`회, `11.2%`)<br>9. **`but here's (the thing / why / how)`** (`39`회, `17.5%`)<br>10. **`(it) turns out` / `which means`** (`32`회 / `26`회) | • `delve into / delve deeper` (**`0`회**)<br>• `testament to` (**`0`회**)<br>• `crucial / pivotal / paramount role` (**`0`회**)<br>• `plays a vital role` (**`0`회**)<br>• `shed(s) light on` (**`0`회**)<br>• `in conclusion / to summarize` (**`0`회**)<br>• `paradigm shift` (**`0`회**)<br>• `furthermore / moreover` (`1`회, `0.6%`)<br>• `tapestry / symphony / embark` (`1`회, `0.6%`) |

### 3-4. 전문용어 `Plain-First` 공식 (`+2.01x` 격차) & 마지막 5초(`Mic-Drop` / `Loop`)
- **전문용어 도입**: 전체 영상의 **`75.0%`는 어려운 해부학 용어 없이 일상어만 사용**하며, 용어를 쓸 때는 **`Plain-First`(*"a part of the brain called the amygdala"*, `7.59x`) + `8단어 내 즉각 일상어 번역`(`10.62x`) 그룹(통합 `8.55x`)이 무설명 직투입(`Term-First Raw`, `4.25x`) 대비 `2.01배` 높은 조회수 배율**을 기록했다.
- **마지막 5초**: **`87.5%`가 군더더기 없는 단정형 반전 명제(`Mic-Drop Twist Statement`, 평균 `8.40x`)**로 끝나며, 첫 문장으로 다시 이어지는 **`Seamless Loop`(`33,000,000`회 중앙값, 샘플 배율 `1.94x`)**가 초고조회수를 견인한다. 오디오 나레이션 안에서 *"What do you think? Comment below!"*를 말한 영상은 **`112`편 중 `0`편(`0.0%`)**이다(참여 질문은 `R35` 고정 댓글로만 분리).

---

## 4. 우리 실제 에피소드 첫 12초(`S1~S4`) Before vs After 영문 대본 비교

````carousel
### ① UCL 간지럼 로봇 (`v8_ep05` 사례)
- **Before (현행 `case_stamp`)**:
  - `S1`: *"In nineteen ninety-eight at University College London, neuroscientists built a tickle robot to test why nobody can tickle themselves!"* (`연도 선행 선언문`)
- **After (미국 1위 공식 `T_second_person + Q_paradox` → `S2` `R72` UCL 드론 진입)**:
  - `S1 (0.0~2.6s, Cut 01)`: ***"Run your fingers across your own palm right now — why is it impossible to tickle yourself?"*** + `[0.42s Pause]`
  - `S2 (3.0~5.8s, Cut 02 UCL Drone K0->K1)`: ***"To find out, neuroscientists at University College London built a mechanical tickle robot."***
  - `S3 (5.8~8.6s, Cut 03 Lab Cutaway K1->K2)`: ***"When you push a plastic lever with your left hand, a foam brush strokes your right palm."***
  - `Ending`: ***"Your brain's movement predictor — the cerebellum — only lets you laugh when a touch catches it by surprise."***
<!-- slide -->
### ② 취침 전 5분 To-Do 리스트 (`v8_ep06` 사례)
- **Before (현행 `case_stamp`)**:
  - `S1`: *"In nineteen ninety-six at Virginia, psychologists played brass marches while volunteers tried to sleep!"* (`연도 선행 선언문`)
- **After (미국 2위 공식 `P_myth_flip` → `S2` `R72` 캠퍼스 드론 진입)**:
  - `S1 (0.0~2.6s, Cut 01)`: ***"Trying harder to fall asleep at 2 AM is the exact reason your brain stays wide awake."*** + `[0.42s Pause]`
  - `S2 (3.0~6.0s, Cut 02 Virginia Drone K0->K1)`: ***"At the University of Virginia, psychologists proved why by playing loud brass marches while volunteers tried to nap."***
  - `S3 (6.0~8.8s, Cut 03 Lab Cutaway K1->K2)`: ***"People told to fall asleep fast lay awake twice as long as people who didn't try at all."***
  - `Ending`: ***"Writing tomorrow's tasks on paper hands the night watch to your notebook, so your brain's memory hub — the hippocampus — can finally shut down."***
<!-- slide -->
### ③ 하버드 사진 선택 후회 역설 (`Ep #7+` 신규 구조)
- **Before (기존 `case_stamp` 적용 시)**:
  - `S1`: *"In two thousand and two at Harvard University, psychologists let darkroom students keep one portrait photo to test buyer's remorse!"*
- **After (미국 1위 공식 `Q_paradox` → `S2` `R72` 하버드 야드 드론 진입)**:
  - `S1 (0.0~2.6s, Cut 01)`: ***"Why do you end up hating your own choice only when you're allowed to change your mind?"*** + `[0.45s Pause]`
  - `S2 (3.0~5.8s, Cut 02 Harvard Yard Drone K0->K1)`: ***"To test this, Harvard psychologists had students print two favorite photos and pick just one to keep."***
  - `S3 (5.8~8.8s, Cut 03 Darkroom Cutaway K1->K2)`: ***"Half were told their pick was final forever, while the other half got five days to swap anytime."***
  - `Ending`: ***"Your brain only builds happiness after an exit door locks shut — which means a lifetime return policy traps you in a choice you never learn to love."***
````
