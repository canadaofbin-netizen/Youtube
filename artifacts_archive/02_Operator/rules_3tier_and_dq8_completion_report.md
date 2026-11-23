# `[RULES_DQ8_DONE]` — `DQ8` 2단계 의심 분류·크롭 추출 재설계 및 규칙 3등급 구조재편 완료 보고서

> [!IMPORTANT]
> **거버넌스 및 크론 창 안전성 확인 (`R83-5 ~ R83-7`)**
> - CEO 소유 [governance_roles.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/governance_roles.md) (`2,595 B`, `30`줄, `trigger: always_on`)는 **무수정 100% 보존**되었습니다.
> - 모든 파일 쓰기는 `tempfile.mkstemp(dir=...) + os.replace(...)` 원자적 교체로 완료되었으며, `06:50 UTC` 정기 크론 창 이전에 코드·규칙·픽스처 편집을 완전히 종료했습니다.
> - `Phase 3`(`R86 Beat Card` 병합 및 4편 Google Flow / `Ep10` TTS 재구축)와 기공개 영상(`tWjrK5enOoM`)은 절대 건드리지 않고 `@YouTube_CEO`의 별도 `Phase 3 GO`를 대기합니다.

---

## 1. `DQ8` 2단계(`HIGH_SUSPECT` / `MODERATE_SUSPECT`) 재설계 및 실측 증빙

### 1.1 구현 아키텍처 요약
1. **워커 `skin_ratio` 무한 재시도 루프 제거**:
   - [flow_diorama_sharded_worker.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/flow_diorama_sharded_worker.py#L979-L1050)에서 `expressive_25d_v8` 컷의 `mean_porcelain_flesh` / `skin_ratio >= 0.45` 차단을 제거하고, 다중 프레임 지속성(`>= 2` 프레임 & `>= 35%`)을 만족하는 `HIGH_SUSPECT`에만 자동 재생성을 발동합니다.
2. **2단계 의심 분류기 + 타임코드·랜드마크 크롭 영구 저장**:
   - 신설 모듈: [dq8_suspect_classifier.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/dq8_suspect_classifier.py) (`detect_yunet_boxes_with_landmarks`, `classify_dq8_yunet_box`, `save_dq8_suspect_evidence`).
   - 무자막 원본 클립(`03_visuals/flow_native_clips/*.mp4` 또는 `03_visuals/clips/*.mp4`)의 실제 사용 구간을 `0.25s` 간격으로 스캔하고 파레이돌리아 필터(`min_dim >= 65px & l_med >= 85 & non_ink_frac >= 0.15`)를 선적용해 무인 건축물·창문·화살표 오검출을 원천 제거합니다.
   - **`HIGH_SUSPECT` (복합 A안 + 상단 박스 모발 구분 `upper_box_dark >= 0.16` + 컷 내 다중 프레임 지속성)**: 자동 재생성 및 `DQ8_zero_uncanny_skin_gore.passed = False` 트리거.
   - **`MODERATE_SUSPECT` (나머지 모든 유효 YuNet 헤드 후보 + 단일 프레임 블링크 스파이크)**: `DQ8` CV 게이트를 단독 차단하지 않고, 타임코드·5점 랜드마크·수치 배너가 찍힌 개별 크롭(`05_assembly/dq8_suspect_crops/cut_XX_tYY.YYs_srcZZ.ZZs_bN_mod.png`)과 종합 시트(`05_assembly/dq8_suspect_contact_sheet.jpg`)를 저장해 `@Research` Gate 2로 전달합니다.
3. **`@Research` Gate 2 직결 ([posthoc_semantic_qa.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/posthoc_semantic_qa.py))**:
   - `init_posthoc_semantic_review_template()`가 각 컷에 `dq8_suspect_tier`, `dq8_suspect_crops`, 그리고 필수 서명 키 `zero_human_skin_or_hair_leak: null`을 주입하며, `@Research`가 `false`로 판정하면 `validate_posthoc_semantic_review()`가 즉시 `dq8_gate2_skin_or_hair_review_failed`로 반려합니다.

### 1.2 고정 65박스 라벨 픽스처 회귀 검증 결과 (`tests/fixtures/dq8_labeled_65/`)
- 픽스처 매니페스트: [manifest.json](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/tests/fixtures/dq8_labeled_65/manifest.json) (`65`장 = 정상 비닐 `40` + 실결함 `17` + 무인 사물 `8`)
- 회귀 테스트: `tests/test_r85_r86_qa_honesty_and_semantic_beat.py::test_dq8_65_labeled_fixture_zero_high_fp_and_zero_missed_defects` → **`PASSED`**
  - **정상 대머리 크림 비닐 (`40`장)**: `HIGH_SUSPECT = 0/40` (**오탐 `0.0%`**), `MODERATE_SUSPECT = 40/40`
  - **실제 얼굴·모발·수염 결함 (`17`장)**: `HIGH_SUSPECT = 12/17`, `MODERATE_SUSPECT = 5/17`, **`NON_HUMAN_PAREIDOLIA` 누락 = `0/17` (`100.0%` 전수 포착)**
  - **무인 사물 파레이돌리아 (`8`장)**: 원본 무자막 클립 기준 **`8/8` (`100%`) 제거**

### 1.3 4편 라이브 에피소드 `verify_final_mp4_against_contract` 실측 및 육안 검수 메모
실측 로그 원본: [dq8_live_4ep_verification.json](file:///home/canadaofbin/.gemini/antigravity-cli/brain/1f9808d4-ebac-4b58-a570-45c8f1f00a85/scratch/dq8_live_4ep_verification.json) (`task-13042`)

| 에피소드 (`project_id`) | `DQ8.passed` | `HIGH_SUSPECT` 컷 (자동 차단) | `MODERATE_SUSPECT` 컷 (Gate 2 이관) | 저장 크롭 수 | 육안 검수 메모 (`dq8_suspect_contact_sheet.jpg` 전수 확인) |
|---|---|---|---|---:|---|
| `v8_ep09_maguire_london_taxi_hippocampus_r82` | **`False`** | **`[7, 8, 22]`** | `[1, 2, 4, 5, 6, 19, 23]` | `16`장 | 붉은 `[HIGH]` 박스는 `C07` 회색 모발, `C08` 실사 남녀 측면 2인, `C22` 갈색 모발·3D 피부 2인만 정확히 표적(`5/5` 진양성). `C01·C02·C23` 트위드 모자·`C06` 정상 비닐 오탐 `0건`, `C04` 백색 비닐 단발은 `[MOD]`로 Gate 2 이관, `C16` 황동 옷걸이 파레이돌리아 완전 제거. |
| `v8_ep10_sleep_pill_brain_wash` | **`False`** | **`[5, 8]`** | `[1, 2, 4, 6, 7, 12, 23, 24]` | `15`장 | 붉은 `[HIGH]` 박스는 `C05` 갈색 조형 모발 2건과 `C08` 실사 백인 남성만 표적(`3/3` 진양성). `C04` 3D 얼굴·모발과 `C06` 단발은 `[MOD]` 크롭으로 Gate 2 이관, `C23` 미세 윤곽 정상 비닐 오탐 `0건`, `C14·C15` 창문·화살표 파레이돌리아 완전 제거. |
| `v8_ep11_open_label_placebo_pain` | **`False`** | **`[4]`** | `[1, 5, 6, 8, 19, 20, 23, 24]` | `13`장 | 붉은 `[HIGH]` 박스는 `C04` 갈색 단발 모발 2건만 표적(`2/2` 진양성). `C01` 턱 수염 얼룩 패치 2건은 `[MOD]` 크롭으로 Gate 2 이관, `C08` 어두운 책장 앞 정상 비닐·`C24` 미세 귀·코 비닐 오탐 `0건`, `C16` 벽돌 창문 파레이돌리아 완전 제거. |
| `v8_ep12_doorway_effect_memory` | **`True`** | **`[]` (`0`건)** | `[1, 2, 3, 4, 5, 6, 7, 18, 19, 22, 23]` | `14`장 | **실결함이 없는 에피소드로 `HIGH_SUSPECT` 오탐 `0건` 달성** (기존 CEO 지적 `C1, C5, C6, C22` 및 `C2` 전등갓 1프레임 스파이크 포함 14장 전부 황색 `[MOD]`로만 기록, `C12` 항공·`C14` 집 앞 파레이돌리아 완전 제거). |

````carousel
![Ep09 라이브 DQ8 의심 크롭 시트 (HIGH: C07, C08, C22 진양성만 포착)](./dq8_live_suspect_sheet_ep09.jpg)
<!-- slide -->
![Ep10 라이브 DQ8 의심 크롭 시트 (HIGH: C05, C08 진양성만 포착)](./dq8_live_suspect_sheet_ep10.jpg)
<!-- slide -->
![Ep11 라이브 DQ8 의심 크롭 시트 (HIGH: C04 진양성만 포착, C01 턱 얼룩 MOD 포착)](./dq8_live_suspect_sheet_ep11.jpg)
<!-- slide -->
![Ep12 라이브 DQ8 의심 크롭 시트 (정상 비닐 에피소드 HIGH 오탐 0건)](./dq8_live_suspect_sheet_ep12.jpg)
````

---

## 2. 규칙 구조 재편 (`< 24,000 B` · `model_decision` · Zero-Deletion) 증빙

전체 감사 JSON 원본: [rules_restructure_audit.json](file:///home/canadaofbin/.gemini/antigravity-cli/brain/1f9808d4-ebac-4b58-a570-45c8f1f00a85/scratch/rules_restructure_audit.json) (`missing_r_ids: []`, `governance_roles_untouched_2595B: true`)

### 2.1 파일별 Before vs After 크기 (`wc -l -c` 실측) 및 `frontmatter` 표

| 파일 경로 | 이전 크기 (`Bytes` / 줄) | 변경 후 크기 (`Bytes` / 줄) | `< 24,000 B` | `trigger` | 비고 |
|---|---:|---:|:---:|---|---|
| [AGENTS.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/AGENTS.md) | `10,106 B` (`76`줄) | **`7,776 B` (`49`줄)** | ✅ (`6–8 KB`) | 없음 (기본 인덱스) | 개정 불변 정체성 4종 + 6채팅방 + 5-Gear + `R1–R86` 전체 매핑 목차 |
| [governance_roles.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/governance_roles.md) | `2,595 B` (`30`줄) | **`2,595 B` (`30`줄)** | ✅ | `always_on` | **CEO 소유 파일 — 무수정 불변** |
| `neuro_diorama_rules.md` *(분할 삭제)* | `49,313 B` (`171`줄) | *(아래 3개 파일로 분할)* | — | — | 구 `49.3 KB` 단일 비대 파일 제거 |
| [neuro_diorama_core_r56_r65.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/neuro_diorama_core_r56_r65.md) *(신설 1)* | — | **`6,949 B` (`49`줄)** | ✅ | `model_decision` | `R56–R65` 코어 조립·자막·`DQ` 트리아지·`R65 v4` 썸네일 |
| [neuro_diorama_v8_world_data_r66_r75.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/neuro_diorama_v8_world_data_r66_r75.md) *(신설 2)* | — | **`7,554 B` (`43`줄)** | ✅ | `model_decision` | `R66–R75` 오픈월드·데이터 스탬프·오픈 라이선스 provenance |
| [neuro_diorama_pacing_brain_r76_r86.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/neuro_diorama_pacing_brain_r76_r86.md) *(신설 3)* | — | **`7,031 B` (`43`줄)** | ✅ | `model_decision` | `R76–R86` 솔로 `Siren`·3D 화살표·31번 AI 뇌·`R86` Beat Card |
| [production_constants.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/production_constants.md) | `74,677 B` (`497`줄) | **`14,030 B` (`26`줄)** | ✅ | 없음 (직접 참조용) | [config.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/config.py) 1:1 참조 색인 (`v4–v7` 구 해설은 `_archive/` 보존) |
| [audio_assembly_rules.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/audio_assembly_rules.md) | `4,824 B` (`18`줄) | **`1,947 B` (`13`줄)** | ✅ | `model_decision` | `R49, R58, R59, R63-P` |
| [brain_depiction_rules.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/brain_depiction_rules.md) | `7,778 B` (`45`줄) | **`3,030 B` (`23`줄)** | ✅ | `model_decision` | `R21, R38(뇌 내부 한정), R48, R53, R85, R85-R` |
| [camera_choreography_rules.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/camera_choreography_rules.md) | `2,492 B` (`22`줄) | **`1,725 B` (`14`줄)** | ✅ | `model_decision` | `R66, R68, R72, R82, R85` |
| [cast_depiction_rules.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/cast_depiction_rules.md) | `1,803 B` (`12`줄) | **`1,736 B` (`13`줄)** | ✅ | `model_decision` | `R56, R68, R85` (비닐 미세 귀·코 2등급 허용 반영) |
| [channel_operations_rules.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/channel_operations_rules.md) | `7,483 B` (`50`줄) | **`7,764 B` (`55`줄)** | ✅ | `model_decision` | `R8–R12, R19, R28, R29, R83` |
| [content_quality_rules.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/content_quality_rules.md) | `4,230 B` (`19`줄) | **`2,244 B` (`17`줄)** | ✅ | `model_decision` | `R1, R3, R15(2등급), R49-T, R73` |
| [pillars_domain_rules.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/pillars_domain_rules.md) | `1,957 B` (`17`줄) | **`2,224 B` (`22`줄)** | ✅ | `model_decision` | `P1, R20` (2등급 배치 다양성) |
| [qa_gates_rules.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/qa_gates_rules.md) | `5,523 B` (`34`줄) | **`3,374 B` (`21`줄)** | ✅ | `model_decision` | 1등급 12개 하드 블록(오픈 라이선스 포함) vs 2등급 점수화 |
| [reference_depiction_rules.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/reference_depiction_rules.md) | `3,209 B` (`15`줄) | **`2,613 B` (`19`줄)** | ✅ | `model_decision` | `R44-M, R66, R67, R72-R, R85` + 오픈 라이선스 provenance 필수 |
| [research_dossier_rules.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/research_dossier_rules.md) | `5,114 B` (`29`줄) | **`5,398 B` (`34`줄)** | ✅ | `model_decision` | `R44, R44-D, R44-M, R50, R50-B` |
| [scene_depiction_rules.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/scene_depiction_rules.md) | `2,369 B` (`15`줄) | **`2,634 B` (`20`줄)** | ✅ | `model_decision` | `R14-A, R47, R68, R86` |
| [visual_prompt_spec.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/visual_prompt_spec.md) | `5,371 B` (`22`줄) | **`2,612 B` (`19`줄)** | ✅ | `model_decision` | `R5, R14-B(locked-off 금지 해제), R38(뇌 컷 한정)` |
| [youtube_studio_operations.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/youtube_studio_operations.md) | `8,771 B` (`37`줄) | **`3,917 B` (`24`줄)** | ✅ | `model_decision` | `R4, R30/30-B, R32, R34–R36-B, R75/75-C/75-S` |
| [retired_rules_2026-11-18.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/_archive/retired_rules_2026-11-18.md) *(보존)* | — | **`94,339 B` (`462`줄)** | 아카이브 | 없음 (`0 B` 주입) | 3등급 퇴역 조항 및 분할 전 원문 Zero-Deletion 보존 |
| [retired_constants_v4_v7_2026-11-18.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/_archive/retired_constants_v4_v7_2026-11-18.md) *(보존)* | — | **`74,901 B` (`499`줄)** | 아카이브 | 없음 (`0 B` 주입) | 구 `production_constants.md` 전문 Zero-Deletion 보존 |

- **상시 컨텍스트 자동 주입량 감축**: 기존 `197,615 B` → **`10,371 B`** (`AGENTS.md` `7,776 B` + `governance_roles.md` `2,595 B`, **`94.8%` 절감**).

### 2.2 전체 규칙 번호(`R1–R86` 및 `P1`) → 새 파일 매핑표 (`누락 0` 증명)
- 이전 전체 고유 규칙 ID `154`개 전수 대조 결과: **`missing_r_ids = []` (`0`개 누락, 신규 세부 ID 포함 `159`개 매핑 완료)**.

| 규칙 범위 / ID | 등급 | 배치된 활성 규칙 파일 (`.agents/rules/`) | 원문 아카이브 보존 |
|---|---|---|---|
| `P1, R20` | 2등급 | `pillars_domain_rules.md` | — |
| `R1, R3, R49-T, R73` / `R15` | 1등급 / 2등급 | `content_quality_rules.md` | `retired_rules_2026-11-18.md` |
| `R2, R2-B, R24, R26, R42` | 3등급(퇴역) | *(활성 게이트 제거; 레거시 분기만 유지)* | `retired_rules_2026-11-18.md` |
| `R4, R30, R30-B, R32, R34, R35, R35-B, R36, R36-B, R75, R75-C, R75-S` | 1등급 / 운영 | `youtube_studio_operations.md` | `retired_rules_2026-11-18.md` |
| `R31, R33` | 3등급(퇴역) | *(활성 규칙 제거)* | `retired_rules_2026-11-18.md` |
| `R5, R14-B(AI 텍스트 금지), R38(뇌 내부 한정)` | 1등급 | `visual_prompt_spec.md`, `brain_depiction_rules.md` | `retired_rules_2026-11-18.md` |
| `R8, R9, R10, R11, R12, R19, R28, R29` | 운영 SSOT | `channel_operations_rules.md` | `retired_rules_2026-11-18.md` |
| `R13, R16, R17, R39, R40-A..C, R41, R43-A/B` | 3등급(퇴역) | *(구 Flow Puck 음성/자막 체인 퇴역)* | `retired_rules_2026-11-18.md` |
| `R14-A, R46, R47` | 2등급 / 연출 | `scene_depiction_rules.md`, `cast_depiction_rules.md` | `retired_rules_2026-11-18.md` |
| `R14-D v4, R45(<=4 뇌 상한), R51, R52, R54, R55, R56-B..M` | 3등급(퇴역) | *(구 `v4–v6` 제한 퇴역)* | `retired_rules_2026-11-18.md` |
| `R18-B, R25, R37` | 1등급 | `qa_gates_rules.md` | `retired_rules_2026-11-18.md` |
| `R21, R48, R53` | 1등급 | `brain_depiction_rules.md` | `retired_rules_2026-11-18.md` |
| `R44, R44-D, R44-M, R46-K, R50, R50-B` | 1등급 | `research_dossier_rules.md`, `reference_depiction_rules.md` | `retired_rules_2026-11-18.md` |
| `R49, R58, R59, R63-P` | 1·2등급 | `audio_assembly_rules.md`, `neuro_diorama_core_r56_r65.md` | `retired_rules_2026-11-18.md` |
| `R56, R57, R60, R61, R62, R63, R64, R65` (`R57-H2` 퇴역) | 1·2등급 | `neuro_diorama_core_r56_r65.md`, `cast_depiction_rules.md`, `qa_gates_rules.md` | `retired_rules_2026-11-18.md` |
| `R66, R67, R68(R55-B, R58-K, R68-A/D), R70/R70-M(M1..M9), R71/R71-B, R72/R72-R, R73` (`R68-H, R74/74-B` 퇴역) | 1·2등급 | `neuro_diorama_v8_world_data_r66_r75.md`, `camera_choreography_rules.md`, `reference_depiction_rules.md` | `retired_rules_2026-11-18.md` |
| `R76(R76-1), R77/R77-N, R78-M/H/V, R79-M, R80, R81, R82, R85/R85-R, R86` (`R76-2/3, R84` 퇴역) | 1·2등급 | `neuro_diorama_pacing_brain_r76_r86.md`, `brain_depiction_rules.md`, `scene_depiction_rules.md` | `retired_rules_2026-11-18.md` |
| `R83, R83-1..7` | 1등급 (`always_on`) | `governance_roles.md`, `channel_operations_rules.md` | — |

### 2.3 3등급 분류표 + CEO 추가 수정(`오픈 라이선스 + provenance`) 코드 반영 요약
- **1등급 #3 오픈 라이선스 + 출처 강제**: [real_world_reference_builder.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/real_world_reference_builder.py) (`validate_real_world_refs_manifest`) 및 [reference_image_qa.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/reference_image_qa.py) (`inspect_reference_image_pack`)에서 `Public Domain / CC0 / CC-BY / CC-BY-SA` 라이선스 및 `source_url`/`reference_provenance.json` 누락 시 즉시 `passed = False` 차단(`test_rules_restructure_under_24kb_frontmatter_and_open_license_lock` 검증 통과).
- **불변 정체성 완화(귀·코 미세 비닐 윤곽 2등급 허용)**: [config.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/config.py) `R85_HUMAN_IDENTITY_LOCK_SUFFIX`, [depiction_rules.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/depiction_rules.py), [flow_prompt_builder.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/flow_prompt_builder.py) 반영 완료.
- **2등급 게이트 점수·경고 전환 및 3등급 활성 차단 해제**:
  - `reference_image_qa.py`: `Q2, Q3, Q5, Q6, Q8, Q9, Q10` → `advisory_warnings` + `reference_qa_score` 감점만 기록(`Q1, Q4, Q7, Q11` + 오픈 라이선스만 하드 블록).
  - `dynamic_episode_qa.py`: `DQ2, DQ4, DQ5, DQ_R76_unified_brain_share, DQ_R79_human_character_motion` → `advisory_gates` 분리; `DQ1, DQ12(3종 강제), DQ_CAMEO, DQ_R76_brain_simulator_sq, DQ_R76_anti_noise_pacing` 활성 차단 해제(레거시 동결 프로젝트 분기 유지).
  - `prosody.py`: `P7, P9`만 1등급 차단 유지, `P1–P6, P8, P10, P11`은 `advisory_gates` + `prosody_score`로 기록.
  - `thumbnail_studio.py`: `TQ4, TQ6, TQ7, TQ8, TQ9` 1등급 차단 유지, `TQ1–TQ3` 2등급 경고화, Shorts `TQ5` 3종 차이 강제 해제.
  - `prompt_quality_v5.py` & `depiction_rules.py`: `R38` 일상 비유 소품 금지를 뇌 해부 컷 내부로 축소, `R57-H2`·`R68-H`·`R74-B` 활성 차단 해제, `FK<=6.5`·단어수 상한 경고화.

---

## 3. 테스트 및 워크스페이스 위생 검증 결과

1. **신규·핵심 회귀 스위트**:
   - 명령: `/home/canadaofbin/hermes-venv/bin/python -X utf8 -m pytest tests/test_r85_r86_qa_honesty_and_semantic_beat.py tests/test_shorts90s_cdp_lease_and_flow_workspace.py tests/test_artifacts_archive_sync.py -k "r85 or r86 or dq8 or rules_restructure or item5 or agents_md" -v`
   - 결과: **`10 passed in 3.44s`**
2. **워크스페이스 위생 점검 (`task-13052`)**:
   - 명령: `/home/canadaofbin/hermes-venv/bin/python -X utf8 scripts/workspace_hygiene.py --check`
   - 결과: **`"passed": true, "issue_count": 0`**
3. **전체 `pytest -v` 스위트 (`task-13053`)**:
   - 명령: `/home/canadaofbin/hermes-venv/bin/python -X utf8 -m pytest -v`
   - 결과: **`549 passed, 14 deselected, 0 failed in 827.44s (0:13:47)`**
   - 전체 로그: [output.txt](file:///home/canadaofbin/.gemini/antigravity-cli/brain/1f9808d4-ebac-4b58-a570-45c8f1f00a85/.system_generated/steps/13053/output.txt)
