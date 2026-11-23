# Stage 2 실행 계획: `Rule R73` 미국 네이티브 나레이션 공식 파이프라인 이식

## Goal Description

Stage 1에서 검증된 미국 6대 공신력 채널 `160`편 실측 결과([us_neuro_psychology_narration_verified_report.md](./us_neuro_psychology_narration_verified_report.md))를 우리 코드베이스에 정식 규칙(**`Rule R73: US Native Spoken Narration & S1->S2 R72 Bridge`**)으로 이식합니다.

기존의 획일적 `"In [Year] at [University]..."` 연도 선행 강제(`case_stamp`, 미국 쇼츠 점유율 `3.6%` / 배율 `1.69x`)를 해제하고, **미국 본토 최상위 4대 오프닝 로테이션 + `S2~S4(3.5~12.0s)` 대학 권위 브리지(`R72` 드론 비행 직결) + `0.42s` 훅 직후 인지 멈춤 + 초등 4~5학년 평이 구어(`FK <= 6.2`) + 전문용어 `Plain-First` 번역(`+2.01x`) + AI 클리셰 전면 차단**을 자동화 게이트로 구축합니다.

---

## User Review Required

> [!IMPORTANT]
> **승인 시 적용 시점 및 호환성 보장**:
> - 기발행·예약 완료된 `Ep #1~#6` 아카이브(`PRE_R73_FROZEN_V8_PROJECTS`) 및 기존 합성 유닛 테스트 픽스처는 100% 하위 호환을 유지합니다.
> - 현재 `@Operator`가 `Rule R72` 엔진 구현 직후 착수할 신규 에피소드부터 즉시 **`Rule R72`(실제 랜드마크 드론 -> 절개 실험실 다이브) × `Rule R73`(미국 네이티브 `S1` 역설 훅 -> `S2` 대학 드론 브리지)** 결합 공식이 적용됩니다!

---

## Proposed Changes

### 1. 미국 최상위 4대 오프닝 로테이션 및 `R72` 연동 상수 정의
#### [MODIFY] [config.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/config.py)
- `EXPRESSIVE_V8_US_NATIVE_OPENING_MODES = ("paradox_question", "myth_flip_claim", "sensory_test", "action_first_stamp")` 신설 및 `EXPRESSIVE_V8_DEFAULT_OPENING_MODE = "paradox_question"` 전환 (`"case_stamp"`는 레거시 호환 모드로만 유지):
  1. **`paradox_question`** (`5.93x` 중앙값 / `16.29x` 평균, 타율 1위): `8~18w`, `?` 종결, 구체적 조건 + 결과 모순 포함 필수, 상투적 `Q_generic` 접두어(`"Have you ever wondered"`, `"Have you ever noticed"`, `"Did you know"`, `"Do you ever feel"`) 하드 차단.
  2. **`myth_flip_claim`** (`5.17x` 중앙값): `8~18w`, 연도 없이 일상 통념을 즉시 뒤집는 단정문.
  3. **`sensory_test`** (`3,700,000`회 중앙값 조회수 1위, `4.83x`): `8~18w`, 시청자가 즉시 해보는 신체 테스트 또는 `"When you lie in bed at 2 AM..."` 2인칭 현장 소환.
  4. **`action_first_stamp`** (`4.37x` 쇼츠 / `6.06x` 롱폼 1위): `8~20w`, 첫 6단어 내 연도(`"In 1998..."`) 낭독 금지 + 기묘한 실험 행동·장면 직진.
- [`is_r72_open_world_v8_plan`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/config.py#L1518-L1573) 업데이트: 위 4개 신규 `R73` 오프닝 모드가 `R72` 오픈월드 드론 검사를 우회하지 않고 100% 정식 활성화되도록 연동(또한 `Cut 01`에서 2.4초 이내 2인칭 감각 훅 제시 후 `Cut 02~03`에서 `K0->K1->K2` 실제 대학 드론 릴레이로 진입하는 패턴과 `Cut 01~02` 즉시 드론 진입 패턴 모두 정식 허용).
- 문장·어휘·호흡 상수 신설:
  - `SHORTS_EXPRESSIVE_V8_R73_SENTENCE_WORDS_MAX = 22` (권장 `8~17w`, 기존 `30w` 비대 문장 차단)
  - `EXPRESSIVE_V8_MAX_FK_GRADE = 6.2` (미국 초등 4~6학년 구어 가독성 상한; 실측 중앙값 `4.60`)
  - `EXPRESSIVE_V8_POST_HOOK_PAUSE_SEC = 0.42` (`S1` 역설/질문 직후 `0.42s` 인지 여백)
  - `EXPRESSIVE_V8_MAX_HARD_JARGON_TERMS = 2`

---

### 2. `S2~S4` 권위 브리지, `Plain-First` 전문용어, AI 클리셰 차단 게이트 구현
#### [MODIFY] [prompt_quality_v5.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/prompt_quality_v5.py)
- [`validate_script_spine_v8_report`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/prompt_quality_v5.py#L657-L900) 고도화 (`Rule R73`):
  1. **4대 오프닝 문법 & 연속 중복 방지 검증**: `S1` 첫머리의 기계적 연도 스탬프(`^In (?:19|20)\d{2}` / `^In (?:nineteen|twenty)`)를 신규 에피소드에서 차단하고, 직전 에피소드와 동일한 `opening_mode` 연속 재사용 시 경고/차단하여 채널 피드 내 훅 다양성 확보.
  2. **`B2` 대학·실험 브리지 타이밍 게이트 (`S2~S4` / `3.5~12.0s`)**: `S1` 훅 직후 `S2~S4`(또는 `action_first_stamp`의 `S1` 말미~`S3`) 내에 실제 대학·기관·연구진·임상 앵커(`Harvard`, `UCL`, `Stanford`, `neuroscientists`, `psychologists` 등)가 등장하도록 강제하여 `R72` 캠퍼스 드론 컷과 음성-영상 일치를 보장.
  3. **`Plain-First` / `<=8w Immediate Gloss` 전문용어 게이트 (`+2.01x` 타율 공식)**: `amygdala`, `cerebellum`, `hippocampus`, `prefrontal cortex`, `striatum`, `insula`, `locus coeruleus` 등 해부학·임상 전문용어 첫 등장 시 앞뒤 `8`단어 이내에 평이한 일상 기능 표현(`"brain's movement predictor"`, `"threat alarm"`, `"memory hub"`, `"called the..."`)이 없으면 하드 에러 발생.
  4. **미국 대형 채널 `0.0%` AI 클리셰 하드 블록 & 네이티브 전환구 확대**: `delve into`, `testament to`, `crucial/pivotal/paramount role`, `plays a vital role`, `shed light on`, `in conclusion`, `paradigm shift`, `furthermore`, `moreover`, `tapestry`, `it is important to note` 등 AI 티가 나는 상투어를 즉시 차단하고, 미국 실측 Top 20 구어 브리지(`in fact`, `that's because`, `in other words`, `instead`, `except`, `until`, `but here's`, `which means`, `turns out`)를 `pivot_markers`에 정식 반영.
  5. **결말(`ending_mode`) 검증**: 기본 `mic_drop`(단정형 반전 명제 종결) 및 선택적 `seamless_loop`(마지막 절이 `S1` 첫 문장과 문맥상 이어지는 무한 루프 설계)를 지원하고, 오디오 내 댓글 유도 질문은 계속 엄격 금지(`R35` 고정 댓글 전용).

---

### 3. `S1` 고속 진입(`rush`) + `0.42s` 인지 멈춤(`Post-Hook Pause`) 오디오 호흡 반영
#### [MODIFY] [audio_gen.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/audio_gen.py) & [prosody_qa.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/prosody_qa.py)
- `expressive_us_v8` 프로소디 기어에서 `S1` 오프닝(`paradox_question` / `myth_flip_claim` / `sensory_test` / `action_first_stamp`) 발화 직후 `S2` 대학 브리지 진입 전에 **`0.42s` (`0.38~0.48s` 허용 창) 의도적 인지 멈춤(`Post-Hook Cognitive Pause`)**이 삽입되도록 설정하여 `@Vsauce`·`@Veritasium`의 첫 문장 여운 호흡(`0.45s` 중앙값)을 구현.

---

### 4. 대본 작성 스킬(`youtube-script`) 및 룰 문서 동기화
#### [MODIFY] [SKILL.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/skills/youtube-script/SKILL.md), [neuro_diorama_rules.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/neuro_diorama_rules.md), [content_quality_rules.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/content_quality_rules.md), [AGENTS.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/AGENTS.md)
- 미국 6대 채널 실측 예시 문장 뱅크(`Q_paradox`, `P_myth_flip`, `T_second_person`, `S_action_first` + `B2` 대학 드론 브리지 Top 10 + 네이티브 전환구 Top 20)를 `youtube-script` 스킬에 내장하여 이후 모든 자동 대본 생성 시 100% 미국 본토 다큐·크리에이터 톤으로 집필되도록 고정 (`AGENTS.md` `< 10,240 bytes` / `<= 78 lines` 엄수).

---

## Verification Plan

### Automated Verification
- 신규 단위 테스트 [`tests/test_r73_us_native_narration.py`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/tests/test_r73_us_native_narration.py) 추가:
  1. `paradox_question` 통과 vs `Q_generic` (*"Have you ever wondered...?"*) 하드 차단 검증
  2. 신규 에피소드 `"In 1998 at..."` 연도 선행 차단 vs `S2~S4` 대학 브리지(`B2`) 통과 검증
  3. `Plain-First` (*"your brain's threat alarm — the amygdala"*) 통과 vs 무설명 `amygdala` 직투입 차단 검증
  4. AI 클리셰(`delve into`, `plays a vital role` 등) 차단 및 `FK Grade <= 6.2` / `<= 22w` 문장 길이 검증
  5. `PRE_R73_FROZEN_V8_PROJECTS` 하위 호환 및 전체 `pytest -v` 100% 통과 검증
