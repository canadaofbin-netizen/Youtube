# 미국 6대 공신력 뇌과학·심리학 채널 나레이션 정량 해부 보고서 (`n = 160` Videos)

> [!IMPORTANT]
> **핵심 결론 (Executive Verdict — `160`편 영문 단어 타임스탬프 대본 전수 실측)**:
> 1. **미국 본토 채널은 첫 문장(`S1`, `0.0~3.5s`)에 연도(`"In 1998..."`)를 말하지 않는다**: 미국 6대 공신력 쇼츠(`n = 112`) 중 첫 문장에 연도·날짜를 선행(`S_year_first`)한 비율은 **단 `3.6%`(`n = 4`)**에 불과하며, 중앙값 조회수(`217,500`회, 카탈로그 중앙값 대비 배율 **`1.69x`**)는 연도 없이 실험·사건 행동으로 바로 진입한 `S_action_first`(`1,200,000`회, **`4.37x`**)보다 **`5.5배` 낮다**.
> 2. **질문형 오프닝(`?`)은 '어떤 질문인가'에 따라 타율이 `3.55배` 갈린다**:
>    - 평범한 수사적 질문 **`Q_generic`** (*"Have you ever wondered...?"*, *"Did you know...?"*, `4.5%`)은 카탈로그 배율 **`1.67x`**(샘플 내 배율 중앙값 **`0.45x`**)로 최하위권에 머문다.
>    - 반면 **구체적 물리·인지 역설을 찌르는 질문 `Q_paradox`** (*"What will happen to this weight if you cut the green rope?"*, *"When you lose weight, where does it go?"*, `11.6%`)는 카탈로그 중앙값 배율 **`5.93x` (평균 `16.29x`, 샘플 평균 `3.11x`)**로 **7대 오프닝 중 압도적 1위 타율**을 기록했다.
>    - 여기에 **통념 파괴 단정문 `P_myth_flip`** (`18.8%`, 카탈로그 배율 **`5.17x`**)과 **2인칭 즉시 체험/감각 지시 `T_second_person`** (`18.8%`, 중앙값 조회수 **`3,700,000`회**, 카탈로그 배율 **`4.83x`**)이 미국 쇼츠 최상위 3대 오프닝 공식을 형성한다.
> 3. **대학·논문·학자 권위(`Credibility Stamp`)의 최적 타이밍은 `S1(0초)`이 아니라 `S2~S4(3.5~12.0초)` 브리지다**:
>    - 학술 권위를 `S1`(`0.0~3.5s`)에 즉시 노출한 영상(`10.1%`)은 카탈로그 배율 중앙값 **`4.25x`**(쇼츠 평균 `6.28x`)에 그친 반면, **`S1(0~3.5s)`에서 역설 질문·2인칭 체험·통념 파괴로 시청자의 호기심을 먼저 잠근 뒤 `S2~S4(3.5~12.0s)`에 대학·연구진·실험을 투입한 영상(`21.7%`)은 카탈로그 배율 중앙값 `5.28x` (쇼츠 평균 `8.85x`)로 `+24.2% ~ +40.9%` 더 높은 성과**를 거두었다.
>    - 이는 신규 승인된 **`Rule R72` (오픈월드 드론 외관 -> 실험실 절개 진입)**와 완벽히 맞물린다: **`Cut 1 (0.0~2.8s, S1)`에서 2인칭 일상 역설/질문/감각 테스트를 던진 직후, `Cut 2~3 (2.8~8.5s, S2~S3)`에서 *"To test why, neuroscientists at University College London..."* 나레이션과 동시에 실제 UCL 캠퍼스 드론 비행 -> 천장 절개 실험실 다이브(`K0 -> K1 -> K2`)**를 실행할 때 시각적 스케일과 미국 네이티브 화법이 100% 일치한다.

---

## 1. 조사 설계 및 표본 정규화 (`2,079`편 카탈로그 모집단 & `160`편 `.json3` 정밀 표본)

채널 체급 차이(`@Vsauce` 2,300만 구독자 vs `@HealthyGamerGG` 300만 구독자)로 인한 조회수 왜곡을 차단하기 위해, 먼저 6대 채널 그룹의 쇼츠·롱폼 전체 카탈로그 **`2,079`편**의 메타데이터를 전수 수집하여 채널·포맷별 모집단 중앙값(`Catalog Median Views`)을 산출하고, 각 채널에서 상위 히트작(`Top 50%`)과 중위권·최신작(`25th~85th Percentile`)을 층화 추출한 **`160`편(쇼츠 `112`편 `70.0%` + 롱폼 `48`편 `30.0%`)**의 영문 단어 단위 타임스탬프 자막(`.en.json3` / `.en-orig.json3`)을 전수 파싱했다.

- **이중 정규화 배율(`Dual View Multiplier`) 정의**:
  $$\text{Catalog View Multiplier} = \frac{\text{Video Views}}{\text{Channel-Format Full Catalog Median Views}}$$
  $$\text{Sample View Multiplier} = \frac{\text{Video Views}}{\text{Channel-Format Sampled Cohort Median Views}}$$

| 채널 그룹 (`Channel`) | 권위 배경 (`Credentials`) | 쇼츠 모집단 (`Catalog n`) | 쇼츠 모집단 중앙값 | 쇼츠 정밀 표본 (`n`) | 롱폼 모집단 (`Catalog n`) | 롱폼 모집단 중앙값 | 롱폼 정밀 표본 (`n`) | 합계 (`Total n`) |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **`@Veritasium`** | Derek Muller, PhD (Physics/Science Ed) | `96` | `4,550,000` | **`23`** | `177` | `11,000,000` | **`8`** | **`31`** |
| **`@hubermanlab`** | Dr. Andrew Huberman, PhD (Stanford Neurobiology Prof.) | `98` | `109,000` | **`22`** | `151` | `193,000` | **`8`** | **`30`** |
| **`@InstituteOfHumanAnatomy`** | 실제 인체 해부학 연구소 (`@theanatomylab`) | `260` | `80,500` | **`20`** | `150` | `474,500` | **`8`** | **`28`** |
| **`@HealthyGamerGG`** | Dr. Alok Kanojia, MD (Harvard Medical School Psychiatry) | `260` | `84,000` | **`20`** | `159` | `471,000` | **`8`** | **`28`** |
| **`@Vsauce`** | Michael Stevens (Psychology / Perception / Cognitive Paradox) | `220` | `8,700,000` | **`17`** | `38` | `7,500,000` | **`8`** | **`25`** |
| **`@TEDEd` & `@SciShowPsych`** | 학자 감수 피어리뷰 대본 대조군 (Academic Peer-Reviewed) | `24` | `128,500` | **`10`** | `436` | `447,000` / `89,000` | **`8`** (`4`+`4`) | **`18`** |
| **합계 / 전체 (`Total`)** | **미국 6대 공신력 뇌과학·심리·해부학 벤치마크** | **`958`** | — | **`112` (`70.0%`)** | **`1,111`** | — | **`48` (`30.0%`)** | **`160` (`100.0%`)** |

---

## 2. [핵심 1] 첫 문장(`0.0~3.5s`, `S1`) 오프닝 유형 분류 & 조회수 타율 비교 (`Do They Start With a Question?`)

![미국 6대 채널 S1 오프닝 유형별 조회수 배율 및 점유율 비교](../01_YouTube_CEO/us_narration_opening_multipliers.png)

> [!TIP]
> **인사말·범퍼 제거 기준**: 쇼츠 `112`편 중 **`93.8%`(`105`편)는 인사말이 `0.0초`(완전 생략)**이며, 롱폼에서 등장하는 고정 시그니처(`"Hey, Vsauce, Michael here"`, `"Welcome to Huberman Lab..."`) 및 스폰서 프리롤(`"Thanks to CuriosityStream..."`)은 정규식 파서로 제거하여 **순수 본문 첫 문장(`S1`, `0.0~3.5s` 호흡 단위)**을 기준으로 계측했다.

### 2-1. 쇼츠(`n = 112`, `70%`) vs 롱폼(`n = 48`, `30%`) 7대 오프닝 정량 성적표

| 오프닝 코드 (`S1 Category`) | 정의 및 구조적 특징 | 쇼츠 표본 (`n`, `%`) | 쇼츠 중앙값 조회수 (`Mean`) | 쇼츠 카탈로그 배율 중앙값 (`Mean`) | 쇼츠 샘플 내 배율 중앙값 (`Mean`) | 롱폼 표본 (`n`, `%`) | 롱폼 카탈로그 배율 중앙값 (`Mean`) | 전체(`n=160`) 카탈로그 배율 중앙값 (`Mean`) |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **`Q_paradox`** | **구체적 역설·메커니즘 질문 (`?`)**<br>(예: *"What will happen to this weight if you cut the green rope?"*) | **`13`** (`11.6%`) | `2,400,000`<br>(`15,494,769`) | **`5.93x`**<br>(**`16.29x`**) | `0.93x`<br>(**`3.11x`**) | **`5`** (`10.4%`) | `3.20x`<br>(`4.08x`) | **`3.67x`**<br>(**`12.90x`**) |
| **`P_myth_flip`** | **통념 파괴·역설 단정문**<br>(예: *"Mirrors do not show us a 4th dimension, but they do show what it could do to us."*) | **`21`** (`18.8%`) | `1,200,000`<br>(`12,016,142`) | **`5.17x`**<br>(`6.94x`) | `1.07x`<br>(`1.24x`) | **`6`** (`12.5%`) | `2.98x`<br>(`3.18x`) | **`4.83x`**<br>(`6.11x`) |
| **`T_second_person`** | **2인칭 즉시 체험·명령·일상 소환**<br>(예: *"If you drop a slinky dangling under its own weight..."*, *"Close your eyes..."*) | **`21`** (`18.8%`) | **`3,700,000`**<br>(**`15,968,476`**) | **`4.83x`**<br>(`9.97x`) | **`1.12x`**<br>(`2.11x`) | **`2`** (`4.2%`) | `2.37x`<br>(`2.37x`) | **`4.40x`**<br>(`9.31x`) |
| **`S_action_first`** | **연도 없는 사건·실험·행동 직진**<br>(예: *"I've purchased 10,000 shade balls..."*, *"These two chain ladders were dropped..."*) | **`17`** (`15.2%`) | `1,200,000`<br>(`10,601,647`) | **`4.37x`**<br>(`6.17x`) | `0.97x`<br>(`1.34x`) | **`12`** (`25.0%`) | **`6.06x`**<br>(`7.27x`) | **`5.73x`**<br>(`6.62x`) |
| **`F_shock_fact`** | **즉각적 신체·뇌·과학 팩트 제시**<br>(예: *"Fentanyl is extremely effective and dangerous because it binds to mu opioid receptors."*) | **`31`** (`27.7%`) | `602,000`<br>(`5,877,774`) | `4.36x`<br>(`6.06x`) | `0.96x`<br>(`1.15x`) | **`21`** (`43.8%`) | `4.98x`<br>(`7.34x`) | `4.48x`<br>(`6.58x`) |
| **`S_year_first`** | **연도·시대 선행 스탬프 (`"In [Year]..."`)**<br>(예: *"In July 1776, Congress voted..."*, *"Recent data from 2025 shows..."*) | **`4`** (`3.6%`) | `217,500`<br>(`214,000`) | **`1.69x`**<br>(`1.72x`) | `1.10x`<br>(`1.06x`) | **`2`** (`4.2%`) | `13.08x`<br>(`13.08x`) | **`2.39x`**<br>(`5.50x`) |
| **`Q_generic`** | **평범한 수사적 질문 (`"Have you ever...?"`)**<br>(예: *"Have you ever wondered how these form?"*, *"Have you ever noticed...?"*) | **`5`** (`4.5%`) | `1,500,000`<br>(`4,269,200`) | **`1.67x`**<br>(`5.11x`) | **`0.45x`**<br>(`1.05x`) | **`0`** (`0.0%`) | `0.00x` | **`1.67x`**<br>(`5.11x`) |

### 2-2. 핵심 대조 검증 ①: `Q_paradox` (구체적 역설 질문) vs `Q_generic` (수사적 질문)
- **왜 기존의 막연한 질문 금지 규칙이 절반만 맞았는가?**:
  - *"Have you ever wondered why..."*, *"Have you ever noticed..."*, *"Do you ever feel..."*로 시작하는 **`Q_generic`(`n = 5`)은 샘플 내 조회수 배율 중앙값이 `0.45x`(채널 평균의 절반 이하), 카탈로그 배율 중앙값이 `1.67x`로 참패**했다. 시청자가 대답할 필요가 없는 상투적 수사 의문문이기 때문이다.
  - 반면 **`Q_paradox`(`n = 13`)는 첫 문장 안에 '구체적 조건 + 물리적/생리적 결과의 모순'을 압축**하여 시청자의 뇌가 즉각 예측 회로를 가동하게 만든다. 그 결과 카탈로그 배율 중앙값 **`5.93x` (평균 `16.29x`)**, 샘플 내 평균 배율 **`3.11x`**로 `Q_generic` 대비 **`+3.55배` 높은 조회수 폭발력**을 보인다.
- **미국 채널 실측 `Q_paradox` 대표 히트 원문**:
  - `@Veritasium` (`itSkBESLZeY`, **`52,000,000`회**, `11.43x`): *"What will happen to this weight if you cut the green rope? Where is this going to end up?"* (`0.00~3.48s`)
  - `@hubermanlab` (`bGixnNGvSkg`, **`7,100,000`회**, `65.14x` — 채널 전체 쇼츠 1위!): *"Is it true that 'microwave safe' just means the plastic won't melt in the microwave, but it's still leaching into your food?"* (`0.00~4.12s`)
  - `@Veritasium` (`zEmabFZvdqA`, **`3,400,000`회**, `0.75x`): *"What happens if I lower this weight into the water? Is the scale going to go up, down, or stay the same?"* (`0.00~3.85s`)
  - `@Veritasium` (`6U6Z6pb6ewI`, **`1,400,000`회**): *"When you lose weight, where does it actually go?"* (`0.00~2.40s`)
  - `@Vsauce` (`zHL9GP_B30E`, **`24,000,000`회** 롱폼, `3.20x`): *"When something becomes part of the past, can it ever truly be experienced again?"* (`1.40~5.20s`)

### 2-3. 핵심 대조 검증 ②: `S_action_first` (연도 없는 사건·실험 직진) vs `S_year_first` (`"In [Year]..."` 연도 선행)
- **현재 우리 `v8` 기본값(`case_stamp`: `"In nineteen ninety-eight at University College London..."`)의 결정적 한계**:
  - 미국 6대 채널 쇼츠 `112`편 중 첫 10단어 이내에 연도(`19xx`, `20xx`)를 말한 영상(`S_year_first`)은 **`@TEDEd` 역사/교양 쇼츠 3편(`xDNzz8yAH7I`, `_XQTOuSw3d4`, `KP-9g4Q8PRA`)과 `@InstituteOfHumanAnatomy` 최신 통계 쇼츠 1편(`1MLSGmnQLNg`, `43,000`회, `0.53x`) 단 4편(`3.6%`)뿐**이다.
  - `@Vsauce`, `@Veritasium`, `@hubermanlab`, `@HealthyGamerGG`의 쇼츠 `82`편 중 **`S1`을 `"In [Year]..."`로 시작한 쇼츠는 `0`편(`0.0%`)**이다!
  - 대신 실험이나 실제 사례로 시작할 때 미국 채널들은 **연도를 빼고 기묘한 실험 행동·장면부터 직진(`S_action_first`, 쇼츠 `15.2%` / 롱폼 `25.0%`)**하여 쇼츠 중앙값 **`1,200,000`회(`4.37x`)**, 롱폼 중앙값 **`3,850,000`회(`6.06x`)**를 기록한다:
    - `@Veritasium` (`n8WxkqMRgS4`, **`53,000,000`회**, `11.65x`): *"These two chain ladders were dropped at exactly the same time, by Cornell Professor Andy Ruina."* (연도 없음! 두 사슬 사다리가 동시에 떨어지는 물리적 장면 먼저 제시 -> 문장 끝에 코넬대 교수 스탬프)
    - `@Veritasium` (`zQ2ZJuUJeyo`, **`64,000,000`회**, `14.07x`): *"I've purchased 10,000 shade balls to try to swim in."* (`0.00~2.80s`)
    - `@hubermanlab` (`Ky-ZJ9SS-x4`, **`865,000`회**, `7.94x`): *"'Every night, for some strange reason at 2:45 AM, I wake up, and it happens three or four nights a week.'"* (`0.00~4.10s`)
    - `@TEDEd` (`eEWa7cpiyD8`, **`10,000,000`회**, `22.37x`): *"While most people avoid spending the night in jail, Jean Béliveau jumped at the opportunity."* (`0.00~5.10s`)

---

## 3. [핵심 2] 대학교·논문·학자 권위(`Credibility / Study Stamp`) 등장 타이밍 분포

![미국 6대 채널 권위 스탬프 등장 타이밍, WPM 호흡, 전문용어 도입 및 엔딩 공식](../01_YouTube_CEO/us_citation_timing_and_pacing.png)

### 3-1. 학술 권위(`University / Professor / Study / Researchers / Clinical Case`) 첫 등장 타임스탬프 분포 (`n = 69`)

전체 `160`편 중 대학명(`Harvard`, `Stanford`, `Cornell`, `Kyoto University`, `McGill` 등), 연구자/의사 실명, 혹은 실험·논문(`study`, `paper`, `researchers`, `patients`, `lab`)을 명시적으로 언급한 영상은 총 **`69`편(쇼츠 `22`편 + 롱폼 `47`편)**이다.

| 권위 등장 구간 (`Credibility Stamp Bucket`) | 등장 문장 및 초(`sec`) 범위 | 쇼츠 (`n=22`) 비중 | 쇼츠 카탈로그 배율 (`Mean` / `Med`) | 롱폼 (`n=47`) 비중 | 롱폼 카탈로그 배율 (`Mean` / `Med`) | 전체 (`n=69`) 비중 | 전체 카탈로그 배율 (`Mean` / `Med`) | 전체 샘플 내 배율 (`Med`) |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **`B1: S1 Immediate`** | `S1` (`0.0 ~ 3.5s` 즉시 투입) | `2` (`9.1%`) | `6.28x` / `6.28x` | `5` (`10.6%`) | `4.78x` / `4.25x` | **`7` (`10.1%`)** | `5.21x` / **`4.25x`** | `1.21x` |
| **`B2: S2–S4 Bridge`** | **`S2~S4` (`3.5 ~ 12.0s` 훅 직후 브리지)** | **`6` (`27.3%`)** | **`8.85x`** / `6.00x` | **`9` (`19.1%`)** | **`5.55x`** / **`4.98x`** | **`15` (`21.7%`)** | **`6.87x`** / **`5.28x`** | `0.99x` |
| **`B3: S5–S8 Setup`** | `S5~S8` (`12.0 ~ 25.0s` 빌드업 구간) | `2` (`9.1%`) | `5.87x` / `5.87x` | `3` (`6.4%`) | `13.90x` / `8.22x` | **`5` (`7.2%`)** | **`10.69x`** / **`6.81x`** | `1.16x` |
| **`B4: Mid-Body Proof`** | 중반 이후 (`> 25.0s`, 쇼츠 중앙값 `27.02s` / `42.7%`) | **`12` (`54.5%`)** | `6.57x` / **`7.59x`** | **`30` (`63.8%`)** | `6.48x` / `4.64x` | **`42` (`60.9%`)** | `6.50x` / `5.14x` | `1.01x` |

> [!NOTE]
> **핵심 발견 — 왜 미국 채널들은 대학·논문 이름을 `0초(S1)`가 아니라 `3.5~12.0초(S2~S4)` 또는 `27초(Mid-Body)`에 꺼내는가?**
> - **0~3.5초(`S1`)의 유일한 임무는 '스크롤 정지(Thumb-Stop)와 호기심 공백 생성'**이다. `0.0s`부터 `"In 1998 at University College London..."`을 낭독하면 시청자는 이를 '학술 강의/교과서 요약'으로 분류해 이탈한다(`S_year_first` 쇼츠 배율 `1.69x`).
> - 반면 **`S1(0~3.5s)`에서 "왜 내 손으로는 아무리 간지럽혀도 안 간지러울까?"(`Q_paradox`) 또는 "지금 손바닥을 스스로 간지럽혀 보세요."(`T_second_person`)로 뇌를 먼저 자극한 뒤, `S2~S3(3.5~9.0s)`에서 *"To find out why, neuroscientists at UCL built a tickle robot..."*으로 연결(`B2: S2–S4 Bridge`)**하면 쇼츠 평균 카탈로그 배율이 **`8.85x`**로 치솟는다!

### 3-2. 미국 채널 실측 `S1(훅) -> S2~S4(대학·논문·실험 진입)` 네이티브 연결 문장 패턴 Top 10 (원문 인용)

| 순위 | 패턴 명칭 (`Native Bridge Pattern`) | 타임스탬프 (`sec`) | 채널 및 영상 ID (`조회수`, `배율`) | 실제 영문 대본 원문 (`S1 Hook -> S2~S4 Credibility Bridge`) |
| :---: | :--- | :---: | :--- | :--- |
| **1** | **How-To Promise -> Year + Scientist Stamp** | `S1 (0.0s) -> S2 (3.44s)` | `@Vsauce` `7JEh43xPIxk`<br>(`25,000,000`회, `2.87x`) | **S1**: *"Here's how to become scary good at finding Waldo."*<br>**S2 (`3.44s`)**: *"In 2015, data scientist Randal Olson used all 68 'Where's Waldo' illustrations to..."* |
| **2** | **Myth Flip -> "It's not. So, there's a paper from [Journal]..."** | `S1 (0.0s) -> S2 (4.40s)` | `@HealthyGamerGG` `06O2mC2SW8g`<br>(`565,000`회, `6.73x`) | **S1**: *"Depression is a chemical imbalance — chemical, mental, spiritual, all why?"*<br>**S2 (`4.40s`)**: *"It's not. So, there's a great paper from Molecular Psychiatry..."* |
| **3** | **Exterior City Establishing -> University Institute Reveal (`R72` 원형!)** | `S1 (0.0s) -> S2 (6.84s)` | `@Vsauce` `ktkjUjcZid0`<br>(`21,000,000`회, `2.80x`) | **S1**: *"This is Inuyama, Japan, a historic city home to Japan's oldest original wooden castle."*<br>**S2 (`6.84s`)**: *"It is also home to Kyoto University's Primate Research Institute."* |
| **4** | **Action First -> "...by [University] Professor [Name]" Clause Tail** | `S1 초반 -> S1 말미 (2.40s)` | `@Veritasium` `n8WxkqMRgS4`<br>(`53,000,000`회, `11.65x`) | **S1**: *"These two chain ladders were dropped at exactly the same time, by Cornell Professor Andy Ruina."*<br>**S2 (`3.80s`)**: *"The one on the right remains in free-fall, but the one on the left will hit the table first."* |
| **5** | **1st-Person Stunt -> "Now, there is a scientific way to test this..."** | `S1 (0.0s) -> S2 (2.85s)` | `@Veritasium` `zQ2ZJuUJeyo`<br>(`64,000,000`회, `14.07x`) | **S1**: *"I've purchased 10,000 shade balls to try to swim in."*<br>**S2 (`2.85s`)**: *"Now, there is a scientific and safe way to test this..."* |
| **6** | **Counter-Intuitive Claim -> "I'm a [Harvard] Psychiatrist..."** | `S1 (0.0s) -> S3 (5.04s)` | `@HealthyGamerGG` `SY0BNyFeQ9Q`<br>(`834,000`회, `1.77x`) | **S1**: *"It turns out that women don't actually like ripped dudes, and I'm going to explain to you why."*<br>**S3 (`5.04s`)**: *"I'm Dr. K and I'm a Harvard-trained psychiatrist..."* |
| **7** | **Clinical Disorder Hook -> "So they did a really interesting study..."** | `S1 (0.0s) -> S4 (5.96s)` | `@HealthyGamerGG` `7vo-HiUqi0k`<br>(`2,400,000`회, `28.57x`) | **S1**: *"There's a particular illness called borderline personality disorder. Have you ever heard of this?"*<br>**S4 (`5.96s`)**: *"But the thing about people with BPD — so they did a really interesting study..."* |
| **8** | **Common Belief Flip -> "So, there's a study that blew my mind."** | `S1 (0.0s) -> S4 (9.40s)` | `@HealthyGamerGG` `H6AVZgYZ2MQ`<br>(`767,000`회, `9.13x`) | **S1**: *"Big thing that a lot of people don't understand... we started to think mental illness is..."*<br>**S4 (`9.40s`)**: *"So, there's a study that like blew my mind."* |
| **9** | **High-Stakes Crisis -> Historical Agency/Decade Stamp** | `S1 (0.0s) -> S2 (4.72s)` | `@Veritasium` `sE-RUu9ClsU`<br>(`24,000,000`회, `5.28x`) | **S1**: *"Congress is about to make a huge mistake in space."*<br>**S2 (`4.72s`)**: *"In the 1990s, NASA launched four telescopes called the Great Observatories..."* |
| **10** | **2nd-Person Exam Dilemma -> Ancient/Scientific Method Bridge** | `S1 (0.0s) -> S2 (7.84s)` | `@TEDEd` `idrbwnWLJ7w`<br>(`7,200,000`회, `16.11x`) | **S1**: *"You’re just one Roman Empire history final away from a relaxing spring break."*<br>**S2 (`7.84s`)**: *"But you still have so much to study! So you decide to follow in the footsteps of..."* |

---

## 4. [핵심 3] 미국 히트 쇼츠(`45~100s`) 전체 나레이션 아크 & 호흡 수치 (`WPM`, 문장 길이, 어휘 난이도, `Pause`)

### 4-1. 6대 채널 쇼츠(`n = 112`) 발화 속도(`WPM`), 문장 호흡, 어휘 평이도 및 의도적 멈춤(`Pause >= 0.30s`) 실측표

| 채널 (`Channel`) | 쇼츠 중앙값 길이 (`sec`) | 첫 5초 훅 발화 속도 (`0~5s WPM`) | 본문 발화 속도 (`5s~End WPM`) | 전체 평균 발화 속도 (`Overall WPM`) | 훅 대비 본문 감속 폭 (`Δ WPM`) | 호흡 단위당 단어 수 (`Words / Clause`) | `1~2`음절 평이 어휘 비율 (`%`) | 읽기 난이도 (`FK Grade`) | 분당 의도적 멈춤 (`Pauses >= 0.30s / min`) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **`@HealthyGamerGG`** | `91.2s` | **`216.0 WPM`** | `209.4 WPM` | `210.4 WPM` | `-6.6 WPM` | `9.0w` | `91.9%` | **`4.0`** | `15.6회/분` |
| **`@InstituteOfHumanAnatomy`** | `74.2s` | **`198.0 WPM`** | `182.8 WPM` | `182.6 WPM` | **`-15.2 WPM`** | `9.9w` | `89.3%` | `5.2` | `18.1회/분` |
| **`@Veritasium`** | `58.3s` | **`192.0 WPM`** | `171.3 WPM` | `171.0 WPM` | **`-20.7 WPM`** | `9.2w` | **`93.8%`** | **`3.4`** | `17.8회/분` |
| **`@Vsauce`** | `59.2s` | **`192.0 WPM`** | `192.1 WPM` | `192.0 WPM` | `+0.1 WPM` | `10.8w` | `92.9%` | `4.9` | **`20.5회/분`** |
| **`@hubermanlab`** | `55.3s` | `180.0 WPM` | `187.4 WPM` | `188.5 WPM` | `+7.4 WPM` | `10.5w` | `91.4%` | `4.9` | `6.9회/분` |
| **`@TEDEd`** | `50.4s` | `138.0 WPM` | `145.5 WPM` | `139.6 WPM` | `+7.5 WPM` | `7.9w` | `88.1%` | `5.8` | `18.9회/분` |
| **미국 쇼츠 전체 (`n = 112`)** | **`58.8s`** | **중앙값 `186.0`**<br>(**평균 `192.5`**) | **중앙값 `187.0`**<br>(**평균 `183.8`**) | **중앙값 `188.5`**<br>(`IQR 164.4~205.7`) | **평균 `-8.7 WPM`**<br>(상위 3채널 `-14.2`) | **중앙값 `9.0w`**<br>(`IQR 6.0~13.0w`) | **중앙값 `91.6%`**<br>(평균 `91.0%`) | **중앙값 `4.60`**<br>(초등 4~5학년) | **중앙값 `15.7회/분`**<br>(멈춤 길이 중앙값 `0.45s`) |

### 4-2. 미국 히트 쇼츠(`60~90s` 기준) 5단계 시간 배분 아크 (`Arc Blueprint`) 및 멈춤(`Pause`) 위치

```mermaid
flowchart LR
    A["1. Hook (0~8% / 0.0~5.5s)\n192.5 WPM Fast Entry\nQ_paradox / T_second_person / P_myth_flip\n+ Pause #1 (0.45s)"] --> B["2. Lab / Setup Bridge (8~28% / 5.5~20s)\n182 WPM Setup\nUniversity / Experiment / Specimen\n(R72 Drone -> Lab Cutaway)"]
    B --> C["3. Twist Pivot (28~48% / 20~36s)\n'But here's the catch / Instead'\nCounter-Intuitive Result\n+ Pause #2 (0.50s)"]
    C --> D["4. Brain Mechanism & Analogy (48~88% / 36~66s)\nPlain-First Neuro Gloss\n1-2 Syllable Analogy (FK Grade 4.6)"]
    D --> E["5. Mic-Drop / Loop Payoff (88~100% / Last 5~8s)\nDeclarative Twist (87.5%) or\nSeamless Loop Tail->Head (7.25x)"]
```

1. **초등 4~5학년 수준(`FK Grade 4.60`, `1~2`음절 단어 `91.6%`)의 극단적 구어 평이성**:
   - 물리학 박사(`@Veritasium`, **`FK 3.4`**, 1~2음절 **`93.8%`**), 하버드 정신과 전문의(`@HealthyGamerGG`, **`FK 4.0`**, **`91.9%`**), 스탠퍼드 신경생물학 교수(`@hubermanlab`, **`FK 4.9`**, **`91.4%`**) 모두 어려운 학술 주제를 다룰수록 문장 구조는 **호흡 단위당 `9.0단어`(완결 문장 기준 `11~15단어`)**의 짧은 단문과 1~2음절 일상 동사(`drop`, `cut`, `look`, `hide`, `bind`, `fire`, `wake`, `trap`)로 구사한다.
2. **`.json3` 단어 타임스탬프 기준 의도적 침묵(`Pause >= 0.30s`)의 법칙**:
   - 미국 쇼츠 나레이터들은 분당 **`15.7회`(약 `3.8초`마다 1회, `Vsauce`는 `2.9초`마다 1회)**에 걸쳐 **중앙값 `0.45s`(평균 `0.57s`)의 의도적 멈춤**을 배치한다.
   - 5분위 타임라인 분포(`Q1 0~20%: 20.9%`, `Q2 20~40%: 20.7%`, `Q3 40~60%: 20.9%`, `Q4 60~80%: 19.3%`, `Q5 80~100%: 18.2%`)에서 확인되듯, **전반부(`0~60%`, `Q1~Q3`)에 멈춤의 `62.5%`가 집중**된다. 특히 ① `S1` 질문/역설 직후(`~3.2s`), ② 실험 조건 제시 직후(`~12s`), ③ `"But here's the thing..."` 반전 접속사 직전(`~25s`)에 `0.40~0.55s`의 숨고르기 여백을 주어 시청자가 스스로 답을 추론할 시간을 강제로 확보한다.

---

## 5. [핵심 4] 미국 네이티브 전환구 사전 (`Native Spoken Pivot Lexicon` Top 20 vs `AI Clichés`)

`160`편(`112` 쇼츠 + `48` 롱폼) 전체 대본에서 실제로 반전·원인·실험 결과·비유를 연결할 때 사용된 구어체 전환구 Top 20과 AI/교과서식 상투어의 실제 출현 빈도를 전수 대조했다.

### 5-1. 미국 6대 채널 실측 구어체 브리지 표현 Top 20 (`n = 160` Videos)

| 순위 | 미국 네이티브 전환구 (`Native Spoken Pivot`) | 총 출현 횟수 (`Occurrences`) | 사용 영상 수 (`n`, `% of 160`) | 서사적 역할 (`Narrative Role`) | 실제 채널 원문 용례 (`Verbatim Transcript Quote`) |
| :---: | :--- | :---: | :---: | :--- | :--- |
| **1** | **`in fact` / `actually`** | **`477`회** | **`78`편 (`48.8%`)** | 통념 부정 & 실제 팩트 강조 | `[Veritasium zQ2ZJuUJeyo]` *"So dangerous, in fact, that he regularly refuses requests..."* |
| **2** | **`and that's why / because / what`** | **`183`회** | **`46`편 (`28.7%`)** | 인과관계 직결 브리지 | `[Veritasium ORxKf1FN3ro]` *"...and slower. That's because from your perspective..."* |
| **3** | **`in other words / essentially / basically`** | **`195`회** | **`43`편 (`26.9%`)** | 어려운 메커니즘의 초등 비유 번역 | `[hubermanlab 62lVH-6xYGY]` *"It's essentially an MRI for how all of our dietary..."* |
| **4** | **`for example / like if`** | **`110`회** | **`38`편 (`23.8%`)** | 2인칭 일상 예시 즉시 소환 | `[Veritasium rL0qEmTRI-I]` *"Like if I heat up this rock, which is kind of like the ground..."* |
| **5** | **`instead (of)`** | **`78`회** | **`35`편 (`21.9%`)** | 예상 결과 기각 & 실제 현상 대조 | `[Veritasium ORxKf1FN3ro]` *"Instead, the rocket ship appears to be slowing down."* |
| **6** | **`even though / even if`** | **`92`회** | **`35`편 (`21.9%`)** | 역설적 조건 강조 | `[Veritasium 2FLqOI9jw-E]` *"...because even if I could speed it up a little bit..."* |
| **7** | **`except (that) / until`** | **`102`회** | **`33`편 (`20.6%`)** | 평형 상태 파괴 & 임계점 트리거 | `[Veritasium k5s1cMNTmGs]` *"...the bottom won't start falling until the whole slinky has collapsed."* |
| **8** | **`but here's / here is (the thing / why / how)`** | **`39`회** | **`28`편 (`17.5%`)** | 핵심 반전(`Twist Pivot`) 시동어 | `[Veritasium 8fNFd2Xswjs]` *"Here's how it works: pick a number."* |
| **9** | **`which means (that)`** | **`26`회** | **`20`편 (`12.5%`)** | 해부학/생리학 특징 -> 실제 체감 결과 | `[InstituteOfHumanAnatomy 0yaMeonjcpA]` *"...which means it crosses the blood-brain barrier rapidly."* |
| **10** | **`at the same time / meanwhile`** | **`35`회** | **`20`편 (`12.5%`)** | 대조군 실험 동시 진행 묘사 | `[Veritasium hPoJWjJ9Ao8]` *"I held onto this ball at the same time to make sure..."* |
| **11** | **`not only ... but`** | **`39`회** | **`20`편 (`12.5%`)** | 2단계 증폭(`Escalation`) | `[Veritasium ORxKf1FN3ro]` *"Not only that, he also appears to be shaking his fist slower."* |
| **12** | **`think about (it / this / how)`** | **`50`회** | **`18`편 (`11.2%`)** | 시청자 능동적 사고 유도 | `[InstituteOfHumanAnatomy 6k3Nb_ihL-4]` *"Now, think about how important the energy storage part is."* |
| **13** | **`wait / hold on / now look`** | **`38`회** | **`18`편 (`11.2%`)** | 시각적 디테일 포인팅 & 흐름 제동 | `[InstituteOfHumanAnatomy WT-tuj5g114]` *"Look at how awesome these two large blood vessels are..."* |
| **14** | **`(the) problem is`** | **`29`회** | **`16`편 (`10.0%`)** | 기존 가설/습관의 한계 폭로 | `[Vsauce vBy0prtj2vw]` *"The problem with old jars is their safety buttons are popped up..."* |
| **15** | **`(it) turns out`** | **`32`회** | **`14`편 (`8.8%`)** | 실험 결과 및 반전 진실 공개 | `[Vsauce vjqt8T3tJIE]` *"Well, as it turns out..."* / `[HealthyGamerGG SY0BNyFeQ9Q]` *"It turns out that..."* |
| **16** | **`believe it or not / strangest / crazy thing`** | **`16`회** | **`12`편 (`7.5%`)** | 반직관적 수치/사실 강조 | `[hubermanlab Ag_a3VAQlgk]` *"Believe it or not, the leaves on trees and grass..."* |
| **17** | **`what's (really) interesting / fascinating is`** | **`15`회** | **`12`편 (`7.5%`)** | 임상/심리 관찰 포인트 전환 | `[HealthyGamerGG mXYihx73OqY]` *"What's really interesting about this is how unsatisfied..."* |
| **18** | **`so what happens (when / if / is)`** | **`23`회** | **`11`편 (`6.9%`)** | 조건 변경 실험(`Act 3`) 진입 | `[Veritasium zEmabFZvdqA]` *"What happens if I lower this weight into the water?"* |
| **19** | **`because when you / because if you`** | **`18`회** | **`11`편 (`6.9%`)** | 2인칭 행동과 뇌 기제의 결합 | `[Vsauce p-VDVI1GMZk]` *"...because when you look into it, you see the pupilla of your..."* |
| **20** | **`the reason (is / why)`** | **`15`회** | **`9`편 (`5.6%`)** | 핵심 원인 단문 선언 | `[Veritasium 4Wrc4fHSCpw]` *"And the reason is very, very simple."* |

### 5-2. 미국 공신력 채널들이 **절대 쓰지 않는** AI/교과서 클리셰 실측 (`160`편 전수 검색)

| 금지 대상 AI / 교과서식 표현 (`AI / Academic Clichés`) | `160`편 내 총 출현 횟수 | 사용 영상 비율 (`%`) | 미국 네이티브 대체 표현 (`Native Replacement`) |
| :--- | :---: | :---: | :--- |
| **`delve into` / `delve deeper`** | **`0`회** | **`0.0%`** | `"look at"`, `"test"`, `"break down"` |
| **`testament to`** | **`0`회** | **`0.0%`** | `"proves that"`, `"shows just how"` |
| **`crucial / pivotal / paramount role`** | **`0`회** | **`0.0%`** | `"is the key to"`, `"controls"`, `"drives"` |
| **`plays a vital role`** | **`0`회** | **`0.0%`** | `"keeps you..."`, `"is what lets you..."` |
| **`shed(s) light on`** | **`0`회** | **`0.0%`** | `"explains why"`, `"revealed"` |
| **`in conclusion` / `to summarize` / `in summary`** | **`0`회** | **`0.0%`** | `"And that's why..."`, `"Which means..."` |
| **`paradigm shift`** | **`0`회** | **`0.0%`** | `"changed everything"`, `"flipped the rule"` |
| **`furthermore` / `moreover`** | **`1`회** | **`0.6%`** | `"Not only that,"`, `"Plus,"`, `"And worse,"` |
| **`tapestry` / `symphony` / `embark`** | **`1`회** | **`0.6%`** | 구체적 물리 명사로 직설 묘사 |
| **`it is important to note` / `worth noting`** | **`3`회** | **`1.9%`** | `"Here's the catch:"`, `"Notice that..."` |

---

## 6. [핵심 5] 신경해부학·심리학 전문용어 도입 공식 (`Plain-First` vs `Term-First` vs `Zero-Jargon`)

`amygdala`, `prefrontal cortex`, `hippocampus`, `cerebellum`, `dopaminergic`, `serotonergic`, `cortisol`, `mu opioid receptors`, `femoral artery`, `myocardium`, `mitochondria`, `aphantasia` 등 전문 학술 용어가 대본에 등장하는 방식과 조회수 배율을 실측했다.

| 전문용어 도입 방식 (`Jargon Introduction Mode`) | 전체 표본 비중 (`n = 160`) | 용어 사용 영상 내 비중 (`n = 40`) | 중앙값 조회수 (`Med Views`) | 카탈로그 배율 중앙값 (`Catalog Mult`) | 샘플 내 배율 중앙값 (`Sample Mult`) | 구조 공식 및 실제 원문 예시 |
| :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **1. `Plain-First` (`쉬운 기능/위치 선행 -> 용어 후행`)** | `13`편 (`8.1%`) | **`32.5%`** | `921,000` | **`7.59x`** | `0.93x` | **`[일상 기능/위치 묘사] + called the [전문용어]`**<br>• `@HealthyGamerGG` (`xZBuKavD1ss`): *"There is a part of the brain called the **amygdala**, which is where you experience anxiety."*<br>• `@InstituteOfHumanAnatomy` (`WT-tuj5g114`): *"Look at how awesome these two large blood vessels are in the upper portion of the thigh. This is the **femoral artery**..."* |
| **2. `Term-First + Immediate Gloss` (`용어 직후 8단어 내 즉각 번역`)** | `8`편 (`5.0%`) | **`20.0%`** | `1,106,500` | **`10.62x`** | **`1.05x`** | **`[전문용어] + [즉각 1:1 일상어 등치]`**<br>• `@HealthyGamerGG` (`C8_1bJzryGY`): *"...from being **dopaminergic** to **serotonergic** — dopaminergic is pleasure, serotonergic is contentment."*<br>• `@InstituteOfHumanAnatomy` (`TdeRTWEIZ0A`): *"...is **ethyl alcohol or ethanol**, but I'll just refer to it as alcohol from here on out."* |
| **3. `Term-First Raw` (`설명 없는 전문용어 직투입`)** | `19`편 (`11.9%`) | `47.5%` | `984,000` | **`4.25x`** | `0.99x` | **사전 설명 없이 전문용어 바로 사용**<br>• `@hubermanlab` (`oeVfCqlHn_I`): *"...is really to control your **cortisol** levels."* |
| **4. `Zero Hard Jargon` (`100% 일상 기능어만 사용`)** | **`120`편 (`75.0%`)** | — | **`2,050,000`** | `3.93x` | `1.00x` | 전문 해부학 라틴어 대신 `"your brain"`, `"nerves"`, `"memory"`, `"pain"`, `"sleep"` 등 100% 일상 명사로 끝까지 설명 |

> [!TIP]
> **핵심 인사이트 (`2.01x` 타율 격차)**:
> - 전문용어를 아예 쓰지 않거나(`75.0%`), 꼭 써야 할 때는 **`Plain-First`(`7.59x`) 또는 `8단어 이내 즉각 1:1 번역(Immediate Gloss)`(`10.62x`)을 결합한 그룹(`52.5%`, 통합 중앙값 배율 `8.55x`)이 설명 없이 전문용어를 던진 그룹(`Term-First Raw`, `4.25x`)보다 조회수 배율이 `2.01배` 높다!**
> - 즉, 우리 에피소드에서도 한 문장 안에 설명 없는 학술 용어를 2개 이상 넣지 말고, 반드시 **`"your brain's movement predictor — the cerebellum"` (`Plain-First`)**처럼 일상 기능 별명을 먼저 들려준 뒤 해부학 명칭을 붙여야 한다.

---

## 7. [핵심 6] 마지막 5초 결말 공식 (`Seamless Loop` vs `Mic-Drop Twist` vs `Open Question ?`)

현재 우리 파이프라인이 자주 사용하는 마지막 문장 질문형/댓글 유도형 엔딩과 실제 미국 대형 뇌과학·심리학 쇼츠(`n = 112`) 및 롱폼(`n = 48`)의 결말 방식을 전수 비교했다.

| 마지막 5초 결말 유형 (`Final 5s Formula`) | 쇼츠 비중 (`n = 112`) | 쇼츠 중앙값 조회수 | 쇼츠 카탈로그 배율 중앙값 (`Mean`) | 쇼츠 샘플 내 배율 중앙값 | 롱폼 비중 (`n = 48`) | 실제 미국 채널 결말 원문 예시 (`Final 5 Seconds Quote`) |
| :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **1. `Mic-Drop Twist Statement` (`단정형 반전 명제 종결`)** | **`98`편 (`87.5%`)** | `1,100,000` | **`4.05x`**<br>(**`8.40x`**) | `1.02x` | **`46`편 (`95.8%`)** | • `@Veritasium` (`itSkBESLZeY`, `52M`, `11.43x`): *"The weight somehow went up."*<br>• `@Vsauce` (`nbmr2HKNpkg`, `79M`, `9.08x`): *"...turn you into a backward version of yourself."* |
| **2. `Seamless Loop Tail -> Head` (`무한 루프 문장 연결`)** | **`3`편 (`2.7%`)** | **`33,000,000`** | **`7.25x`**<br>(`6.69x`) | **`1.94x`** | `0`편 (`0.0%`) | • `@Veritasium` (`k5s1cMNTmGs`, `36M`, `7.91x`): *"The bottom is turning, but still not falling — until the top crashes into it."* (다시 `0.0s` 슬링키 낙하 장면으로 직결!)<br>• `@Veritasium` (`ORxKf1FN3ro`, `33M`, `7.25x`): *"...gets dimmer and redder until it completely disappears."* (-> `S1`: *"You can never see anything enter a black hole."*) |
| **3. `Open Cliffhanger Question (?)` (`철학적 역설 여운 질문`)** | **`3`편 (`2.7%`)** | `646,000` | **`7.69x`**<br>(`6.66x`) | `1.07x` | `0`편 (`0.0%`) | • `@Veritasium` (`n8WxkqMRgS4`, `53M`, `11.65x`): *"Now, why did that happen?"*<br>• `@HealthyGamerGG` (`lKIg6YaXFnI`, `646K`, `7.69x`): *"And does that mean we should stop trying to brush our teeth because we're depressed?"* |
| **4. `2nd-Person Takeaway / Promo CTA` (`행동 지침·롱폼 유도`)** | **`8`편 (`7.1%`)** | `2,850,000` | **`2.42x`**<br>(`3.53x`) | **`0.57x`** | `2`편 (`4.2%`) | • `@Veritasium` (`za_HO2E3JEU`, `12M`, `2.64x`): *"If you want to know more, check out our long-form video."* |

> [!WARNING]
> **결말 공식 핵심 경고 — 나레이션 안에서 *"What do you think? Let me know in the comments!"* 같은 댓글 구걸 질문을 하는 미국 대형 쇼츠는 `112`편 중 `0`편(`0.0%`)이다!**
> - 미국 쇼츠의 **`87.5%`는 마지막 0.2초까지 군더더기 없는 단정형 반전 명제(`Mic-Drop Twist Statement`, 평균 배율 `8.40x`)로 칼같이 끊거나**, `S1`의 첫 장면과 문맥이 맞물리는 **`Seamless Loop`(`33,000,000`회 중앙값, 샘플 배율 `1.94x`)**로 끝난다.
> - 시청자 참여 유도 질문(`debate_question`)은 오디오 나레이션에 넣지 않고 **`R35` 고정 댓글(Pinned Comment)**로만 분리하는 것이 미국 본토 표준이다.

---

## 8. [핵심 7] `@AllAboutBrainOfficial` (`v8` + `R72`) 즉시 이식용 처방전 & 실전 리라이트 3종

### 8-1. 파이프라인 코드 및 대본 규칙 개정 명세 (Stage 2 `@Operator` 이식용 설계안)

1. **[`pipeline/config.py`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/config.py#L1450-L1570) & [`pipeline/prompt_quality_v5.py`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/prompt_quality_v5.py#L667-L729) 오프닝 모드 다변화 (`R68-H v2`)**:
   - 현재 모든 에피소드의 `S1`에 `"In [Year] at [Institution]..."`를 강제하는 단일 `EXPRESSIVE_V8_DEFAULT_OPENING_MODE = "case_stamp"` 락을 해제하고, 미국 6대 채널 실측 상위 4대 오프닝 모드를 정식 허용·권장한다:
     - **`Mode 1: paradox_question` (`Q_paradox`, 타율 1위 `5.93x` / 평균 `16.29x`)**: `S1`(`<= 16w`, `?` 종결)에서 2인칭 구체적 역설/물리·생리적 모순 질문을 던진 뒤(`"Have you ever..."` / `"Did you know..."` 등 `Q_generic` 접두어는 정규식으로 엄격 차단!), **`S2`(`3.0~7.5s`)에서 대학·연구진·실험 스탬프(`R72` 캠퍼스 드론 진입)**를 찍는다.
     - **`Mode 2: sensory_test` (`T_second_person`, 중앙값 조회수 1위 `3.70M`, `4.83x`)**: `S1`(`<= 16w`)에서 시청자가 즉시 따라 할 수 있는 신체 테스트나 `"When you lie in bed at 2 AM..."` 2인칭 상황으로 진입한 뒤, **`S2~S3`(`3.0~9.0s`)에서 대학·실험 스탬프**로 연결한다.
     - **`Mode 3: myth_flip_claim` (`P_myth_flip`, `5.17x`)**: `S1`(`<= 16w`)에서 통념을 정면으로 뒤집는 단정문(*"Trying harder to fall asleep is the exact reason you stay awake."*)을 선언한 뒤, **`S2`(`3.0~7.5s`)에서 실험 증거**를 제시한다.
     - **`Mode 4: action_first_stamp` (`S_action_first`, `4.37x` 쇼츠 / `6.06x` 롱폼)**: `S1` 첫머리의 딱딱한 연도(`"In nineteen ninety-eight..."`)를 제거하고 **기묘한 실험 장치/행동부터 직진**하되, 문장 후반부나 `S2`에 대학·연구소를 결합한다(기존 `case_stamp` 하위 호환 유지).
2. **`Rule R72` (오픈월드 드론 외관 -> 절개 포털 진입) × `S1~S3` 나레이션 완벽 싱크 공식**:
   - **`Cut 01 (0.0~2.8s)` + `S1 (Hook)`**: 시청자의 일상 공간(침실, 거실, 거울 앞, 손바닥 클로즈업)에서 **2인칭 역설 질문(`Q_paradox`) / 즉시 감각 테스트(`T_second_person`) / 통념 파괴(`P_myth_flip`)**를 `190~200 WPM`(`rush` 기어)으로 빠르게 던지고 **`0.40s` 의도적 멈춤(`Pause`)**을 준다.
   - **`Cut 02 (2.8~5.6s)` + `S2 (University Drone Approach, K0 -> K1)`**: *"To find out why, neuroscientists at University College London..."* 나레이션 시작과 동시에 **실제 대학 캠퍼스/도시 랜드마크 상공 드론 비행(`drone_aerial_approach`)** 컷으로 전환한다.
   - **`Cut 03 (5.6~8.5s)` + `S3 (Cutaway Portal Breach, K1 -> K2)`**: 지붕/창문이 열리며 실험실 내부 장비로 다이브(`fpv_window_portal_breach`)하면서 실험 참가자의 구체적 행동을 묘사한다.
3. **문장 호흡(`WPS`), 어휘(`FK Grade`), 전문용어(`Plain-First`), 엔딩(`Mic-Drop`) 게이트**:
   - **문장 길이**: 문장당 목표 단어 수를 기존 `16~25w`에서 **미국 쇼츠 실측치인 `8~16w`(절 단위 `9.0w`, 최대 하드 캡 `<= 22w`)**로 다이어트하고, `Flesch-Kincaid Grade <= 5.5`(`1~2`음절 어휘 `>= 88%`)를 유지한다.
   - **전문용어 `Plain-First` 강제**: `cerebellum`, `amygdala`, `hippocampus`, `prefrontal cortex` 등 해부학 용어 첫 등장 시 앞에 반드시 쉬운 기능어(*"your brain's movement predictor, the cerebellum"*)를 먼저 배치한다.
   - **엔딩(`Final Sentence`)**: 나레이션 내부의 댓글 유도 질문을 금지하고, **단정형 반전 명제(`Mic-Drop Twist Statement`)** 또는 `S1`과 이어지는 **`Seamless Loop` 문장**으로 종결한다.

---

### 8-2. 실전 에피소드 3종 첫 12초(`S1~S4`) Before vs After 영문 대본 비교표

#### ① 에피소드 A: `UCL 간지럼 로봇 실험` (`v8_ep05_ucl_tickle_delay_robot` — Blakemore et al., Nature Neuroscience 1998, DOI `10.1038/2870`)

| 구분 | 기존 `case_stamp` 버전 (`Before` — 현재 [`script.json`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/BCI_Shorts_Channel/projects/v8_ep05_ucl_tickle_delay_robot/02_script/script.json#L100-L105)) | 미국 6대 채널 1위 공식 + `R72` 싱크 버전 (`After` — `T_second_person` + `Q_paradox` -> `S2` UCL Drone Stamp) |
| :--- | :--- | :--- |
| **`S1` (`0.0~2.8s`)**<br>`Cut 01` | *"In nineteen ninety-eight at University College London, neuroscientists built a tickle robot to test why nobody can tickle themselves!"* (`19w`, 연도 선행 선언문) | ***"Run your fingers across the bottom of your own palm right now — why can't you tickle yourself?"*** (`17w`, `T_second_person` 즉시 체험 + `Q_paradox` 질문 + `0.40s` Pause)<br>*[Visual: 손바닥을 스스로 간지럽히지만 무표정한 2.5D 캐릭터 클로즈업]* |
| **`S2` (`2.8~6.0s`)**<br>`Cut 02 (R72 K0->K1)` | *"Volunteers lay in a scanner with one hand on a lever and the other palm open."* (`16w`) | ***"To find out, neuroscientists at University College London built a mechanical tickle robot."*** (`13w`, `B2` 권위 스탬프 브리지)<br>*[Visual: 실제 런던 UCL 포트코(Portico) 돔 캠퍼스 상공 드론 비행 접근]* |
| **`S3` (`6.0~9.0s`)**<br>`Cut 03 (R72 K1->K2)` | *"Push this lever with your right hand, and the foam robot will stroke your left palm."* (`16w`) | ***"When you push a plastic lever with your left hand, a soft foam brush strokes your right palm."*** (`18w`, 2인칭 실험 장치 몰입)<br>*[Visual: UCL 지붕이 절개되며 실험실 내부 간지럼 로봇 레버로 FPV 다이브]* |
| **`S4` (`9.0~12.0s`)**<br>`Cut 04` | *"When the foam tip moved in sync with their fingers, why did volunteers feel almost nothing?"* (`16w`) | ***"As long as the brush moved right away, volunteers felt almost nothing — until researchers added a split-second delay."*** (`18w`, `"until"` 네이티브 반전 트리거) |
| **마지막 문장 (`Ending`)** | *"Next time someone tickles you, remember your cerebellum just missed the prediction."* | ***"Your brain's movement predictor — the cerebellum — only lets you laugh when a touch catches it by surprise, even when the hand is your own."*** (`Plain-First` + `Mic-Drop Twist`) |

---

#### ② 에피소드 B: `취침 전 5분 To-Do 리스트 수면 역설` (`v8_ep06_bedtime_todo_list_sleep` — Scullin et al., Baylor 2018 `10.1037/xge0000374` & Ansfield et al., Virginia 1996 `10.1016/0005-7967(96)00031-9`)

| 구분 | 기존 `case_stamp` 버전 (`Before` — 현재 [`script.json`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/BCI_Shorts_Channel/projects/v8_ep06_bedtime_todo_list_sleep/02_script/script.json#L100-L105)) | 미국 6대 채널 1위 공식 + `R72` 싱크 버전 (`After` — `P_myth_flip` -> `S2` Baylor/Virginia Drone Stamp) |
| :--- | :--- | :--- |
| **`S1` (`0.0~2.8s`)**<br>`Cut 01` | *"In nineteen ninety-six at Virginia, psychologists played brass marches while volunteers tried to sleep!"* (`14w`, 연도 선행 선언문) | ***"Trying harder to fall asleep at 2 AM is the exact reason your brain stays wide awake."*** (`17w`, `P_myth_flip` 통념 파괴 단정문 + `0.42s` Pause)<br>*[Visual: 새벽 2시 침대에서 눈을 질끈 감을수록 머리 위 각성 게이지가 치솟는 장면]* |
| **`S2` (`2.8~6.0s`)**<br>`Cut 02 (R72 K0->K1)` | *"Half tried to fall asleep as fast as possible, while others drifted off whenever they wanted."* (`16w`) | ***"At the University of Virginia, psychologists proved why by playing loud brass marching music while volunteers tried to nap."*** (`19w`, `B2` 권위 스탬프 + 기묘한 실험 대조)<br>*[Visual: 버지니아대 로툰다(Rotunda) 캠퍼스 드론 외관 -> 수면 실험실 절개 진입]* |
| **`S3` (`6.0~9.2s`)**<br>`Cut 03 (R72 K1->K2)` | *"Close your eyes right now and fall asleep as fast as you possibly can."* (`14w`) | ***"People told to fall asleep as fast as possible lay awake more than twice as long as people who didn't try at all."*** (`23w` -> 2호흡 분할) |
| **`S4` (`9.2~12.0s`)**<br>`Cut 04` | *"Yet why did volunteers trying the hardest lie wide awake far longer than everyone else?"* (`15w`) | ***"That's because forcing sleep turns on a mental alarm that keeps checking if you're still awake — but Baylor University found a five-minute fix."*** (`23w`, `"That's because"` 인과 브리지 + Baylor 스탬프) |
| **마지막 문장 (`Ending`)** | *"Write tomorrow's tasks down on paper so your brain stops guarding them all night."* | ***"Writing tomorrow's tasks on paper hands the night watch over to your notebook, so your brain's memory hub — the hippocampus — can finally shut down."*** (`Plain-First` + `Mic-Drop Twist`) |

---

#### ③ 에피소드 C: `하버드 사진 선택 후회 역설` (`gilbert_reversible_choice_paradox` — Gilbert & Ebert, Harvard University 2002, DOI `10.1037/0022-3514.82.4.503`)

| 구분 | 기존 `case_stamp` 공식 적용 시 (`Before` — `"In [Year] at [Univ]..."` 템플릿) | 미국 6대 채널 1위 공식 + `R72` 싱크 버전 (`After` — `Q_paradox` -> `S2` Harvard Drone Stamp) |
| :--- | :--- | :--- |
| **`S1` (`0.0~2.8s`)**<br>`Cut 01` | *"In two thousand and two at Harvard University, psychologists let darkroom students keep one portrait photo to test buyer's remorse!"* (`20w`, 연도 선행 선언문) | ***"Why do you end up hating your own choice only when you're allowed to change your mind?"*** (`17w`, `Q_paradox` 구체적 역설 질문 + `0.45s` Pause)<br>*[Visual: 영수증의 '무료 환불 가능' 도장을 볼수록 손에 든 사진이 빛바래 보이는 2.5D 연출]* |
| **`S2` (`2.8~6.0s`)**<br>`Cut 02 (R72 K0->K1)` | *"Students photographed two favorite things and chose one glossy print to take home right away."* (`15w`) | ***"To test this, Harvard psychologists had students print two favorite photos and pick just one to take home."*** (`18w`, `B2` 하버드대 권위 스탬프 브리지)<br>*[Visual: 실제 하버드 야드(Harvard Yard) 붉은 벽돌 캠퍼스 드론 비행 접근]* |
| **`S3` (`6.0~9.0s`)**<br>`Cut 03 (R72 K1->K2)` | *"You have five days to swap your photo if you change your mind."* (`13w`) | ***"Half were told their choice was final forever, while the other half got five days to swap their photo anytime."*** (`20w`, 대조군 설계)<br>*[Visual: 하버드 윌리엄 제임스 홀(William James Hall) 외벽이 열리며 암실 실험실 내부로 FPV 다이브]* |
| **`S4` (`9.0~12.0s`)**<br>`Cut 04` | *"Why did students who could freely exchange their photo end up hating the picture they kept?"* (`16w`) | ***"Almost nobody actually swapped — yet the students who had the option to change their minds ended up hating the photo they kept."*** (`22w`, `"yet"` 반전 스탬프) |
| **마지막 문장 (`Ending`)** | *"Lock your decision in so your brain synthesizes satisfaction."* | ***"Your brain only manufactures happiness after an exit door locks shut — which means a lifetime return policy traps you in a choice you never learn to love."*** (`which means` + `Mic-Drop Twist`) |
