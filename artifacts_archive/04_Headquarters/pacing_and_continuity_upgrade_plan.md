# 장면 전환 호흡 · 핵심 장면 밀도 · 공간 연속성 파이프라인 개선 계획서 (`/plan`)

## Goal Description

대표님께서 완성본([reenact_01_strange_situation_test_1080x1920.mp4](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/reenact_01_strange_situation_test_1080x1920.mp4))을 직접 시청하시고 짚어주신 3가지 핵심 연출 문제를 코드·타임라인(EDL)·63개 전체 렌더 시트 기준으로 전수 역추적했습니다.

- **고정 사항 (변경 `0%`)**: 대표님께서 만족하신 **성우(`emma_v7`)와 말하기 속도(`dynamic_us_v7`, 마스터 오디오 `147.25초`)는 단 1프레임도 건드리지 않고 그대로 유지**합니다. (자막과 상단 헤드라인은 오디오 타임스탬프에 직접 물려 있어 화면 컷 수만 줄여도 싱크가 100% 유지됩니다.)

---

### 1. 테스트 영상 정밀 부검: 왜 이 3가지 문제가 발생했는가?

````carousel
![실제 적발 사례 1 (sheet_03.jpg 3행 Cut #15, 33.38~36.17s) — 좌측 의자에 이미 회색 정장 인물이 앉아 있는데 문을 열고 또 다른 정장 인물이 들어오는 연속성 파괴 및 상단 인형의 집(Cut #13) 필러](./sheet_03.jpg)
<!-- slide -->
![실제 적발 사례 2 (sheet_02.jpg 1행 Cut #07, 9.08~15.29s) — 우측에 이미 엄마와 아기가 앉아 있는데 문으로 두 번째 엄마와 아기가 또 들어오는 현상 + 줄자(Cut #09)·필름 릴(Cut #11)·점심 시계(Cut #12) 필러 컷](./sheet_02.jpg)
````

#### 원인 ① 장면 전환이 너무 빠른 이유 (`147.25초` 동안 무려 `63컷` = 평균 `2.3초`, 최단 `0.67초`)
1. **원본 대비 9.2배 과속 편집**: *Strange Situation* 원본 영상(`QTsewNrHUHU`, `194.5초`)은 **단 9개의 롱테이크(평균 `21.6초`)**로 아기의 시선·울음·회피 행동을 차분히 관찰하게 합니다. 반면 우리 파이프라인([config.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/config.py#L526-L652))은 `DIORAMA_CLIP_COUNT_DEFAULT = 60`, 최소 컷 수 `DIORAMA_TARGET_CUT_MIN = 52`를 강제해 Google Flow가 뽑아준 `7.92초` 클립의 **70%를 잘라 버리고 평균 `2.34초`마다 화면을 넘겼습니다.**
2. **문장 쪼개기 + 강제 플래시 컷 루프**: [`diorama_assembler.py:1039-1105`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/diorama_assembler.py#L1039-L1105)의 `CV(컷 길이 변동계수 >= 0.36)` 보정 루프가 수치를 맞추려고 멀쩡한 `2.6초` 문장을 `30% : 70%`로 강제 절단하여 **`0.67초~1.17초`짜리 초단타 플래시 컷을 10개나 양산**했습니다(오프닝 9초 동안에만 6번 전환).
3. **`split_hstack` 좌우 비교 컷 버그 적발**: [`diorama_assembler.py:869-880`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/diorama_assembler.py#L869-L880)이 `left_clip_index`를 무시해, 가장 임팩트 있어야 할 `Cut #44`(`OUTSIDE: SILENT` vs `INSIDE: RACING`)가 잘못된 좌측 클립을 단 **`0.83초`**만 비추고 사라졌습니다.

#### 원인 ② 스톱워치 같은 불필요한 장면이 대거 들어간 이유 (총 `13개` 필러 인서트 적발)
1. **일상 숫자에까지 비유·소품 컷을 강제한 코드 규칙 (`R57-V` & `DQ1`)**: [`plain_language.py:568-625`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/plain_language.py#L568-L625)의 `validate_number_analogy_pairing`이 연도·나이를 제외한 **모든 숫자(`30초`, `20분`, `9피트`, `8단계`, `41명`)** 뒤에 무조건 일상 사물 비유(`"like a quick check"`, `"shorter than lunch"`, `"like a small rug"`)를 붙이게 강제했고, [`dynamic_episode_qa.py`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/dynamic_episode_qa.py#L285-L345)(`DQ1`)가 그 사물을 화면으로 보여줄 것을 요구했습니다.
2. **결과**: 대표님이 정확히 지적하신 **30초 스톱워치/주방 타이머(`Cut #05`, `Cut #18 [0.67s]`, `Cut #55`, `Cut #57`)**를 비롯해 바닥 줄자(`Cut #09`), 점심 식탁 시계(`Cut #10`/`#12`), 거대 필름 릴(`Cut #11`), 8칸 인형의 집(`Cut #13`), 나무 수레(`Cut #28`), 빈 의자 나열(`Cut #32`, `#35`, `#41`) 등 **실험 몰입을 깨는 13개 필러 장면이 전체 러닝타임의 25% 이상을 낭비**했습니다. (대기 중인 미렌더링 65편 초안에도 동일한 타이머/소품 필러가 들어 있어 함께 교정해야 합니다.)

#### 원인 ③ 이미 의자에 앉아 있는데 또 문을 열고 들어오는 연속성 오류 (총 `11건` 전수 적발)
1. **입장 동작에 ‘입장 완료 후 프레임’을 시작 이미지로 잘못 결합**:
   - **`Cut #15` (`33.38~36.17s`, 대표님 지적 장면)**: *"낯선 사람이 들어와 의자에 앉는다"*는 장면에, 낯선 사람이 들어오기 전 빈 의자 이미지(`ref_s03_start.png`)가 아니라 **이미 낯선 사람이 좌측 의자에 앉아 있는 `ref_s06_start.png`(원본 `76.08초` 시점)**를 시작 레퍼런스로 넣었습니다. 그 결과 AI가 **좌측 의자에 앉아 있는 낯선 사람을 그대로 둔 채 문으로 또 한 명의 낯선 사람을 입장**시켰습니다.
   - **`Cut #07` (`9.08~15.29s`)**: 엄마와 아기가 입장하는 장면에 이미 엄마·아기가 착석해 있는 `ref_s01_start.png`를 물려 **두 번째 엄마와 아기가 또 걸어 들어오는 현상**이 `6.21초`간 발생했습니다.
2. **좌/우 의자 역할 반전으로 인한 ‘유령 낯선 사람’ 오염**: 원본 영상에서는 엄마가 좌측 의자에 앉았으나 `visual_plan.json`이 엄마를 우측, 낯선 사람을 좌측으로 뒤집는 바람에, 엄마 혼자 있어야 할 재결합 레퍼런스([ref_s08_start.png](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/BCI_Shorts_Channel/projects/reenact_01_ainsworth_strange_situation/03_visuals/reference_images/ref_s08_start.png), [ref_s09_end.png](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/BCI_Shorts_Channel/projects/reenact_01_ainsworth_strange_situation/03_visuals/reference_images/ref_s09_end.png)) 좌측 의자에 **회색 정장 낯선 사람이 남아 있다가 컷마다 나타났다 사라지는 현상(`Cuts #20~27, #33~34`)** 및 빈 의자 위 마네킹 머리 잔상(`Cut #61`)이 발생했습니다.
3. **시맨틱 QA(`R51 Q11` & `R64`)의 인물 수 검증 부재**: 기존 이미지·영상 QA가 화질·밝기·움직임만 수치로 재고 **“이 장면에 누가 몇 명 있어야 하는가 / 이전 컷과 인물이 이어지는가”**를 검사하지 않아 복제 인물이 그대로 통과했습니다.

---

## User Review Required

> [!IMPORTANT]
> **음성(`emma_v7`) 및 오디오 속도(`dynamic_us_v7`) 100% 보존 & 생성 효율 2배 향상:**
> - `reenact_01`의 기존 오디오([audio_master.wav](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/BCI_Shorts_Channel/projects/reenact_01_ainsworth_strange_situation/04_audio/audio_master.wav), `147.25초`)는 그대로 유지합니다.
> - 에피소드당 목표 클립 수를 기존 `60개(평균 2.3초)` → **`30~34개(평균 4.4~5.0초)`**로 개편하면 시청 몰입도가 높아질 뿐 아니라, **앞으로 모든 에피소드의 Google Flow 생성 시간도 절반(`~50%`)으로 단축**됩니다.

물리적 클립 길이 및 Flow 레퍼런스 첨부 관련 기술적 안전장치입니다:

> [!WARNING]
> **Google Flow `0-credit` 물리 한계(`7.72s`) 및 단일 사전 상태 프레임 원칙:**
> 1. `Veo 3.1 - Lite` 원본 클립은 `7.92초`(앞뒤 트림 제외 유효 구간 **`7.72초`**)이므로, 단일 롱테이크 최대 길이는 **`7.20초`**로 제한해야 정지 프레임(`tpad` 프리즈) 없이 자연스러운 `1.00x` 실사 움직임이 유지됩니다(`DQ7` 준수).
> 2. `0-credit` 모드에서 ‘빈 의자 이미지 + 앉아 있는 이미지’ 2장을 동시에 Ingredient 칩으로 넣으면 두 이미지를 합성해 오히려 복제 인물을 만듭니다. 따라서 **모든 입장·퇴장 컷은 반드시 ‘행동 직전 상태의 단일 시작 프레임 1장’만 바인딩**하도록 규칙을 잠급니다.

---

## Open Questions

계획 실행 전 아래 **3가지 항목**만 컨펌해 주시면 즉시 코드 반영 및 수정본 테스트 영상 제작에 들어가겠습니다. *(전 항목 **권장안 A** 일괄 승인 가능)*

| 번호 | 확인 안건 | **(권장) 옵션 A** | 대안 옵션 B |
|---|---|---|---|
| **결정 1** | **새로운 표준 장면 전환 호흡** | **시네마틱 다큐 호흡 (`28~34컷`, 평균 `4.4~5.0초`, 최소 `1.8초` 이상, 핵심 실험 장면 `4.5~7.0초` 롱테이크 유지)** | 중간 호흡 (`40~44컷`, 평균 `3.3~3.7초`, 최소 `1.4초`) |
| **결정 2** | **`reenact_01` 테스트 영상 수정 방식** | **오디오(`147.25s`, `emma_v7`) 100% 보존 + 필러 13컷 전면 제거 + 오염 레퍼런스 2장 및 핵심 동선 클립 `~8~10개`만 깨끗하게 재생성하여 `~31컷` 완성본 재조립** (최상단 MP4 즉시 교체) | 대본에서 `"shorter than lunch"` 같은 비유 문구 자체까지 덜어내고 `emma_v7` 오디오도 새로 합성 후 재조립 |
| **결정 3** | **대기 중인 65편 큐(`porcelain_rebalanced_queue.json`) 동시 반영** | 이번 **‘`30~34컷` 호흡 + 시계/타이머 필러 제거 + 인물 연속성 원장’을 대기 중인 65편 포슬린 큐에도 일괄 업데이트** (성우는 기존 기본값 유지 또는 `emma_v7` 확대 선택 가능) | 우선 파이프라인 코드와 `reenact_01` 영상부터 완성해 보고 65편 큐는 그다음 일괄 재생성 |

---

## Proposed Changes

### Component 1: 시네마틱 장면 호흡 개편 (`63컷/2.3s` → `30~34컷/4.6s` & `split_hstack` 복원)

#### [MODIFY] [config.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/config.py)
- 과속 컷 전환을 강제하던 상수를 다큐멘터리 호흡으로 재조정하고 [production_constants.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/production_constants.md)와 1:1 동기화합니다.

```python
# pipeline/config.py (장면 전환 호흡 개편)
DIORAMA_CLIP_COUNT_DEFAULT = 32                 # 기존 60: 불필요한 필러 제거 및 Flow 생성 시간 50% 단축
DIORAMA_TARGET_CUT_MIN = 26                     # 기존 52: 2.5분 영상 기준 28~36컷 시네마틱 호흡 허용
DIORAMA_V7_RAPID_CUT_MIN_SEC = 1.80             # 기존 0.68: 1초 미만 플래시 컷 영구 폐지
DIORAMA_V7_MID_ACT_MAX_CUT_SEC = 6.20           # 기존 4.60: 단일 문장 충분한 호흡 허용
DIORAMA_V7_LONG_TAKE_MAX_SEC = 7.20             # 기존 6.50: 2~3문장 연속 실험 관찰 롱테이크 (7.72s 유효창 이내)
DIORAMA_V7_CUT_CV_MIN = 0.22                    # 기존 0.36: 인위적 문장 쪼개기 없이 자연스러운 완급 유지
```

#### [MODIFY] [diorama_assembler.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/diorama_assembler.py)
- **강제 플래시 컷 절단 루프 제거 (`L1039-1105`):** `cur_cv`를 맞추려고 멀쩡한 문장을 `0.30 : 0.70`(`0.67s`)으로 쪼개던 루프를 제거합니다.
- **2~3문장 롱테이크 유지 & 뇌 해부 라벨 보존:** 같은 공간에서 이어지는 인물의 행동·감정선은 `end_sentence_index`로 묶어 `4.0~7.0초` 동안 끊김 없이 보여주되, ① 콜드오픈 `S1·S2·S3`는 문장당 1컷(`2.3~3.1초`), ② 서로 다른 뇌 부위 배지(`AnatomyLabel`)가 붙는 `porcelain_living_brain` 문장은 각각 독립 컷(`~2.5초`)으로 유지합니다.
- **`split_hstack` 좌우 클립 바인딩 버그 수정 (`L869-880`, `L1119-1125`):** `left_clip_index`와 `right_clip_index`를 모두 정확히 예약·매핑하고 문장 전체 길이(`2.5초+`) 동안 분할 화면을 온전히 유지합니다.

#### [MODIFY] [dynamic_episode_qa.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/dynamic_episode_qa.py)
- `DQ5` 템포 계약(`avg_cut_max_sec = 5.60`, `min_cuts = DIORAMA_TARGET_CUT_MIN`), [prompt_quality_v5.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/prompt_quality_v5.py)(`L496`), [video_autopsy.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/video_autopsy.py)(`L1711`), [source_reenactment.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/source_reenactment.py)(`L964` `RQ5`)의 컷 수 및 평균 길이 기준을 새 상수에 맞춰 일원화합니다 (`diorama_01..26` 기발행본은 레거시 예외 유지).

---

### Component 2: 스톱워치·타이머·인형의 집 등 저임팩트 필러 컷 원천 차단 (`Substantive Visual Gate`)

#### [MODIFY] [plain_language.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/plain_language.py)
- `analyze_number_analogies`(`L568-609`)에서 **직관적인 일상 단위(`seconds`, `minutes`, `hours`, `days`, `feet/foot room`, 소수 인원·횟수 `two..fifty`, 단순 퍼센트 `%`)를 의무 비유 대상에서 면제**합니다.
- 오직 시청자가 직관적으로 체감하기 어려운 **미세·거시 과학 단위(`milliseconds`, `Hz`, `microvolts`, `micrometers`, `cubic millimeters`, 특수 물리량)**에만 일상 비유를 요구하도록 정교화합니다.

#### [MODIFY] [prompt_quality_v5.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/prompt_quality_v5.py)
- **필러 인서트 차단 게이트(`validate_substantive_visual_relevance`) 신설:**
  1. 단순 시간·횟수 언급 때문에 본 실험 공간을 벗어나 **스톱워치, 주방 타이머, 벽시계, 줄자, 빈 의자 나열**을 비추는 `porcelain_literal_analogy` / 소품 클로즈업 프롬프트를 차단합니다(에피소드당 `porcelain_literal_analogy` 최대 `1회` 이하, 핵심 과학 역설 설명 시에만 허용).
  2. 임상·행동 재현 에피소드에서 실사 1:1 스케일을 깨뜨리는 미니어처 인형의 집 / 거대 손 / 거대 필름 릴(`porcelain_cutaway_section` 오남용)을 금지하고, `"30초"` 같은 실험 규칙 언급 시에는 **실제 실험실 속 아기와 엄마/연구자의 핵심 행동 장면**을 계속 보여주도록 강제합니다.

---

### Component 3: 공간·인물 상태 연속성 원장(`Scene-State Continuity Ledger`) & QA 고도화

#### [MODIFY] [prompt_quality_v5.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/prompt_quality_v5.py)
- 모든 실내 장면 클립 스펙(`visual_plan.json`)에 **`scene_state`**(`location_id`, `present_cast_start`, `entering_cast`, `exiting_cast`, `present_cast_end`)를 선언하고 Google Flow 생성 전 `prompt-gate`에서 3대 연속성 불변식을 강제 검증합니다:
  1. **입장 불변식 (`Entrance Invariant`):** `entering_cast`에 포함된 인물은 절대 `present_cast_start` 및 바인딩된 `reference_image`의 기존 착석 인물에 존재할 수 없음 (`Cut #07`, `Cut #15` 복제 입장 원천 차단).
  2. **퇴장·부재 불변식 (`Exit / Absence Invariant`):** 이전 장면에서 퇴장한 인물(예: 혼자 남은 아기 장면의 낯선 사람)이 포함된 레퍼런스 이미지를 후속 독백·재결합 컷에 바인딩하는 것을 즉시 차단 (`Cut #21~27` 유령 인물 출몰 차단).
  3. **시대·공간 잠금 (`Era/Location Lock`):** 다른 연도·장소(`1993_regensburg_lab`, `modern_home`) 컷에 `1970_playroom` 레퍼런스 이미지를 재사용하는 것을 차단 (`Cut #50, #58` 오염 차단).

#### [MODIFY] [source_reenactment.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/source_reenactment.py)
- **장기 테이크 내부 상태 전환 서브 키프레임 추출 (`extract_source_edl`):** `12초` 이상의 원본 롱테이크(`S07 = 47.2s`, `S09 = 51.1s`)에서는 시작/끝 2장만 뽑지 않고 **문 열림·입장 전·착석 후·퇴장 직후(혼자 남은 아기)·재결합 포옹** 이벤트 경계별 서브 키프레임을 추출합니다.
- **좌/우 좌석 역할 1:1 잠금 (`translate_porcelain_keyframes_async`):** 원본 구조 가이드의 좌/우 의자 배정과 `visual_plan.json`의 인물 좌석을 절대 뒤바꾸지 않도록 잠그고, Google Flow `Nano Banana 2.1` 변환 프롬프트에 `exact_actor_count` 및 빈 의자 조건(`"left wooden chair strictly empty, zero other adults"`)을 명시합니다.

#### [MODIFY] [reference_image_qa.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/reference_image_qa.py) & [posthoc_semantic_qa.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/posthoc_semantic_qa.py)
- `R51 Q11`(`reference_semantic_review.json`)에 `expected_cast` 및 `actor_count_exact` 검증 필드를 추가해 잘못된 인물이 찍힌 레퍼런스 PNG를 영상 생성 전에 걸러냅니다.
- `R64`(`posthoc_semantic_review.json`)에 `zero_duplicate_actors`, `no_severed_parts`, `spatial_continuity_with_prev_cut` 항목을 추가해 복제 입장이나 잔상 아티팩트가 있는 클립은 자동 불합격 처리합니다.

---

### Component 4: 1호 테스트 영상(`reenact_01`) 정밀 리컷·재생성 & 대기 큐 반영

#### [MODIFY] [visual_plan.json](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/BCI_Shorts_Channel/projects/reenact_01_ainsworth_strange_situation/03_visuals/visual_plan.json)
- 기존 `63컷(평균 2.34초)` 구성을 **`~31컷(평균 4.75초, 최소 2.0초 ~ 최대 7.0초)`** 핵심 장면 중심 플랜으로 재편성합니다:
  1. **필러·스케일 붕괴 13개 클립 완전 삭제**: 스톱워치(`#05`, `#18`), 줄자(`#09`), 점심 타이머(`#10`), 거대 필름 릴(`#11`), 8단 다이얼(`#12`), 인형의 집(`#13`), 나무 수레(`#28`), 빈 의자 모형(`#32`, `#35`, `#41`), 벽시계(`#55`), 주방 타이머(`#57`)를 모두 걷어냅니다.
  2. **기존 고품질 클립 ~21개는 `4.0~6.8초` 풀 호흡으로 재활용**: 아기 블록 탐색, 일방경 관찰실, 문고리 클로즈업, 심전도 기록계, 봉입형 4색 3D 뇌(`AMYGDALA`, `HYPOTHALAMUS`, `PREFRONTAL CORTEX`), 좌우 분할(`Clip #46 + #47` `OUTSIDE: SILENT` vs `INSIDE: RACING` 온전한 `2.5초+` 유지)은 이미 생성된 선명한 `7.92초` 원본을 길게 살려 씁니다.
  3. **오염 레퍼런스 2장(`ref_s08_start`, `ref_s09_end` 빈 좌측 의자) + 핵심 동선 클립 `~9개`만 Google Flow `0-credit` 정밀 재생성**:
     - 엄마·아기 첫 입장(`ref_env_master` 빈 방에서 시작 → 중복 인물 `0%`),
     - 낯선 사람 입장(`ref_s03_start` 빈 좌측 의자 상태에서 시작 → 중복 인물 `0%`),
     - 30초 울음 구간(스톱워치 대신 문 앞에서 우는 아기와 즉시 문을 열고 들어와 안아주는 엄마의 실제 핵심 감정 장면),
     - 낯선 사람 없는 깨끗한 혼자 남은 아기 & 재결합 포옹 롱테이크,
     - 30초 기다림 육아 팁 구간(주방 타이머 대신 장난감을 향해 손을 뻗는 아기 옆에서 부모가 차분히 미소 지으며 30초간 지켜봐 주는 실제 장면).
- 재조립 완료 즉시 워크스페이스 최상단 [reenact_01_strange_situation_test_1080x1920.mp4](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/reenact_01_strange_situation_test_1080x1920.mp4)를 업데이트합니다.

---

## Verification Plan

### Automated Tests
```bash
# 1. 신규 장면 전환 호흡 · 필러 차단 · 인물 연속성 원장 유닛 테스트 및 기존 전체 회귀 검증
/home/canadaofbin/hermes-venv/bin/python -X utf8 -m pytest tests -q

# 2. reenact_01 새 플랜 사전 연속성 & 필러 차단 검증 (입장 중복 0건, 타이머 필러 0건 확인)
/home/canadaofbin/hermes-venv/bin/python -X utf8 main.py prompt-gate --dir BCI_Shorts_Channel/projects/reenact_01_ainsworth_strange_situation
/home/canadaofbin/hermes-venv/bin/python -X utf8 main.py ref-qa --project reenact_01_ainsworth_strange_situation

# 3. 재조립 후 전 게이트 검증 (오디오 147.25s 불변, 컷 수 ~31개, 최소 컷 >= 1.80s, DQ1~12, R64, RQ1~5)
/home/canadaofbin/hermes-venv/bin/python -X utf8 main.py verify --project reenact_01_ainsworth_strange_situation
/home/canadaofbin/hermes-venv/bin/python -X utf8 main.py prosody-qa --project reenact_01_ainsworth_strange_situation
/home/canadaofbin/hermes-venv/bin/python -X utf8 main.py episode-qa --project reenact_01_ainsworth_strange_situation
/home/canadaofbin/hermes-venv/bin/python -X utf8 main.py posthoc-qa --project reenact_01_ainsworth_strange_situation --require-review
/home/canadaofbin/hermes-venv/bin/python -X utf8 main.py reenact-qa --project reenact_01_ainsworth_strange_situation
/home/canadaofbin/hermes-venv/bin/python -X utf8 main.py qa --project reenact_01_ainsworth_strange_situation
```

### Manual Verification
1. **컷별 시트 100% 육안 전수 대조**: 재조립된 `posthoc_viewer_strips/sheet_*.jpg` 전 컷을 직접 확인하여 ① 모든 입장/퇴장 장면에서 의자 위 중복 인물·유령 인물·잘린 마네킹 머리가 `0건`인지, ② 스톱워치·주방 타이머·인형의 집 필러가 완전히 사라지고 실제 실험 장면으로 채워졌는지, ③ `OUTSIDE: SILENT` vs `INSIDE: RACING` 좌우 비교 화면이 충분히 읽히는지 확인합니다.
2. **최상단 MP4 시청 검수**: [reenact_01_strange_situation_test_1080x1920.mp4](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/reenact_01_strange_situation_test_1080x1920.mp4)를 재생해 기존 성우·속도는 그대로인 상태에서 화면 호흡이 편안하고 몰입감 있게 바뀌었는지 대표님께서 직접 확인하십니다.
