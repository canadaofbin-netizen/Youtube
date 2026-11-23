# R68-H 계획서 — 첫 2초 `연도·대학·실존 사건` 직격 오프닝 훅 전환 (`case_stamp`)

**작성 주체**: [`@YouTube_CEO`](conversation://b57c97a8-6324-4c31-a2bb-16b25e28dd55) → 승인 시 [`@Operator`](conversation://1f9808d4-ebac-4b58-a570-45c8f1f00a85) 이관 실행
**적용 범위**: **파이프라인 첫 문장(`S1`) 규칙 및 검증기만 변경** (현재 올라간 `v8_pilot_03` 등 기존 영상은 건드리지 않음)

---

## 1. 변경 배경 및 현행 코드의 문제점 (Root Cause)

채널 실측 데이터([2026-11-10_video_detail_report.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/BCI_Shorts_Channel/reports/daily/2026-11-10_video_detail_report.md))에서 조회수·구독자 전환 1·2위 영상은 모두 **첫 2초에 연도·대학·실존 사건**을 바로 박아 넣었습니다:
- **채널 1위 (`2,015뷰`, 3초 훅 `80.3%`, 완시율 `97.2%`)**: `"In 2013 at the University of Rochester, Maiken Nedergaard's team imaged living brains..."`
- **채널 2위 (`1,608뷰`, 3초 훅 `84.4%`)**: `"In 1999, neuroscientists studied an amnesic patient named Eugene..."`

그러나 현재 `expressive_25d_v8` 검증기 코드는 정반대로 동작하고 있었습니다:
1. **[pipeline/prompt_quality_v5.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/prompt_quality_v5.py#L559-L566)**: 첫 문장(`S1`)이 `"In 2013..."`이나 대학/연구진으로 시작하면 에러로 **차단**하고 있었음.
2. **[pipeline/prompt_quality_v5.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/prompt_quality_v5.py#L1419-L1424)**: `v8`에서만 예외적으로 `"Imagine..."` 금지 목록을 풀어주어 `"Imagine you are four years old..."` 같은 느슨한 가정형 첫 문장이 생성됨.

---

## 2. 핵심 변경 명세 (`R68-H`: First-2-Second Case-Stamp Hook)

다른 파이프라인 설정(길이·차트·카메라·오디오 등)은 일절 건드리지 않고 **오직 `S1`(첫 문장) 오프닝 규칙만 교체**합니다.

### ① `"Imagine..."` 가정형 오프닝 전면 재금지 & `"In [Year] at [Institution]..."` 차단 해제
- **[pipeline/prompt_quality_v5.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/prompt_quality_v5.py)**:
  - `L559–566`의 연도·대학 오프닝 차단 정규식(`S1 opens with a year or academic institution`) **완전 삭제**.
  - `L1419–1424`의 `is_v8` 예외 조항을 제거하여 `DIORAMA_BANNED_WEAK_HOOK_PREFIXES` (`"imagine "`, `"picture this"`, `"have you ever "`, `"what if "`, `"suppose "`)를 `v8`에서도 **100% 하드 차단**.
  - 단, 이미 제작·게시 완료된 기존 파일럿 3편(`PRE_R68H_FROZEN_V8_PROJECTS = ("v8_pilot_01_...", "v8_pilot_02_...", "v8_pilot_03_...")`)은 예외 처리하여 기존 파일 및 회귀 검증이 깨지지 않게 보존.

### ② 신규 기본 오프닝 모드 `opening_mode = "case_stamp"` 신설
- **[pipeline/config.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/config.py)** & **[pipeline/research_dossier.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/research_dossier.py#L1127)**:
  - `EXPRESSIVE_V8_DEFAULT_OPENING_MODE = "case_stamp"` (기존 `"action"`/`"situation"` 대체; `dossier seed --style-profile expressive_25d_v8` 시 자동 적용).
  - `EXPRESSIVE_V8_OPENING_CASE_STAMP_MAX_WORDS = 22` (`10~22`단어로 압축해 늘어짐 방지).
- **`case_stamp` 검증 규칙 (`validate_script_spine_v8_report`)**:
  1. **첫 2초 앵커 (`S1` 앞 8단어 이내)**: **연도/연대**(`In 2013`, `In 1970`, `In the 1960s`, `For 55 years` 등) **+** **실제 대학·병원·기관·지명 또는 실존 연구자/환자명**(`at the University of Rochester`, `at Stanford`, `Patient S.M.` 등)이 즉시 등장해야 통과.
  2. **구체적 사건 결합**: 단순 논문 소개(`"A study examined..."`)가 아니라, 같은 첫 문장 안에 **구체적 실험 행동이나 기이한 임상 사건**이 바로 이어져야 함.
     - ✅ 통과 예시: `"In 2013 at the University of Rochester, researchers broke a promise to four-year-olds right before the Marshmallow Test!"` (`18w`)
     - ✅ 통과 예시: `"In 2011 at the University of Iowa, doctors gave a fearless woman one breath of carbon dioxide — and triggered instant panic!"` (`21w`)
     - ❌ 차단 예시: `"Imagine you are four years old in a university playroom..."` (`Imagine` 가정형 차단)

### ③ 스크립트 작성 스킬 및 SSOT 문서 동기화
- **[.agents/skills/youtube-script/SKILL.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/skills/youtube-script/SKILL.md)**, **[.agents/rules/neuro_diorama_rules.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/neuro_diorama_rules.md)**, **[.agents/rules/production_constants.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/production_constants.md)**:
  - Act 1 `S01` 작성 지침에서 `"Imagine you are..." allowed` 문구를 삭제하고, **`opening_mode: "case_stamp"` (`In [Year] at [University/Clinic], [Shocking Real Action/Event]` `<= 22w`)**를 기본 템플릿으로 명시.
  - 이에 맞춰 첫 클립(`Clip 01` 비주얼 프롬프트)도 막연한 배경이 아니라 **해당 대학 실험실·병실의 핵심 소품 행동이 `0.0s`에 바로 보이는 장면**으로 매칭하도록 가이드 고정.

---

## 3. 수정 대상 파일 및 검증 계획 (`@Operator` 실행 항목)

| 파일 | 변경 내용 |
|---|---|
| [pipeline/config.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/config.py) | `EXPRESSIVE_V8_DEFAULT_OPENING_MODE = "case_stamp"`, `EXPRESSIVE_V8_OPENING_CASE_STAMP_MAX_WORDS = 22`, `PRE_R68H_FROZEN_V8_PROJECTS` 추가 |
| [pipeline/prompt_quality_v5.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/prompt_quality_v5.py) | `L559–566` 연도·대학 시작 차단 삭제, `L1420` `"Imagine..."` 차단 복원, `case_stamp` 앵커 검증 추가 (기존 테스트용 명시적 `opening_mode="action"` 픽스처는 advisory 호환 유지) |
| [pipeline/research_dossier.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/research_dossier.py) | `v8` 시드 생성 시 `"opening_mode": "case_stamp"` 기본값 기록 |
| [youtube-script/SKILL.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/skills/youtube-script/SKILL.md) 외 SSOT 2종 | `R68-H` 첫 2초 연도·대학·실존 사건 직격 공식 반영 |
| `tests/test_r68h_case_stamp_hook.py` (신규) + 기존 스위트 | `"In 2013 at the University of Rochester..."` 통과, `"Imagine you are..."` 차단, `22단어` 초과 차단, 기존 `test_expressive_25d_v8.py` 무결성 검증 |
