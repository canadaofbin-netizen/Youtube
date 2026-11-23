# `DQ8` 재설계 실측 · 규칙 3등급 구조재편 · `R86` 통합 실행 계획서 (`[PLANS_READY]`)

> [!IMPORTANT]
> **작업 상태 고지 (`Judge & Verify` 절차 준수)**
> 본 문서는 **분석·실측 및 즉시 실행 가능한 구현 설계서**이며, 프로덕션 워크스페이스 코드·규칙 파일 수정은 `0건` 상태입니다. `@YouTube_CEO` 검토 후 실행 `GO` 수신 즉시 아래 순서대로 원자적(atomic) 반영 및 `pytest` 검증을 수행합니다.

---

## Part 1. `DQ8` 얼굴·머리카락 검출기 재설계 계획 및 65개 라벨 데이터셋 실측

### 1.1 4편 전수(`Ep09_r82` ~ `Ep12`) 라벨 데이터셋 구축 (`65`개 고유 박스 + 픽스처 `5`개)
`face_detection_yunet_2023mar.onnx`(`score >= 0.62`, 5점 랜드마크 포함)로 4편의 비(非)뇌 컷 전체(`0.25s` 간격)에서 검출된 **고유 바운딩 박스 `65`개**를 전수 추출·육안 라벨링했습니다(확정된 3등급 기준 반영: `Ep11 C24`, `Ep10 C23` 등 미세 비닐 귀·코 윤곽과 천 모자 착용 비닐은 `clean_vinyl` 정상 분류; 실사 피부·실사 눈구멍·머리카락·턱 수염 얼룩은 `defect` 분류).

- **정상 대머리 크림 비닐 (`clean_vinyl`)**: **`40`장** (목표 `>= 30`장 초과 달성 — 난색 조명 비닐, 트위드 모자 착용 비닐 3장, 미세 귀·코 조형 비닐 포함)
- **실제 결함 (`defect`)**: **`17`장** (목표 `>= 8`장 2배 초과 — 실사 백인 남성 `ep10_c08_b0`, **실사 대머리 남녀 측면 `ep09_c08_b0/b1`**, 3D 복숭아빛 인간 얼굴 `ep10_c04_b0/b1`, 갈색 조형 모발 `ep09_c22_b0/b1`·`ep10_c05_b0/b1`·`ep10_c06_b0`·`ep11_c04_b0/b1`, 회색 모발 `ep09_c07_b0`, 흰색 단발 모발 `ep09_c04_b0`, 스탬프 뒤 암색 모발 `ep09_c23_b1`, 턱 갈색 수염 패치 글리치 `ep11_c01_b0/b1`)
- **무인·사물 오검출 (`non_human` 파레이돌리아)**: **`8`장** (`ep09_c16` 황동 옷걸이, `ep10_c14` 병원 야간 창문, `ep10_c15` 붉은 화살표, `ep11_c16` 벽돌 창문, `ep11_c19_b1` 에코백+자막, `ep12_c12` 고딕 기숙사 창문)
- 재현 데이터 및 정밀도/재현율 산출 스크립트:
  - [dq8_labeled_feature_table.json](file:///home/canadaofbin/.gemini/antigravity-cli/brain/1f9808d4-ebac-4b58-a570-45c8f1f00a85/scratch/dq8_labeled_feature_table.json)
  - [dq8_feature_benchmark_summary.json](file:///home/canadaofbin/.gemini/antigravity-cli/brain/1f9808d4-ebac-4b58-a570-45c8f1f00a85/scratch/dq8_feature_benchmark_summary.json)

````carousel
![Ep09 YuNet 17개 박스 및 5점 랜드마크 실측 시트](./dq8_labeled_sheet_ep09.jpg)
<!-- slide -->
![Ep10 YuNet 18개 박스 및 5점 랜드마크 실측 시트](./dq8_labeled_sheet_ep10.jpg)
<!-- slide -->
![Ep11 YuNet 14개 박스 및 5점 랜드마크 실측 시트](./dq8_labeled_sheet_ep11.jpg)
<!-- slide -->
![Ep12 YuNet 16개 박스 및 5점 랜드마크 실측 시트](./dq8_labeled_sheet_ep12.jpg)
````

### 1.2 후보 판별 특징별 Precision · Recall · 오탐률(`FPR`) 실측표 (`N = 65`)

| # | 후보 판별 특징 / 분류기 (`pareidolia_gate`: `min_dim>=65px, L_med>=85, non_ink>=0.15` 선적용) | AUROC | Precision | 결함 Recall (`17`장 중) | **정상 비닐 오탐률 (`40`장 중)** | 무인 사물 오탐률 (`8`장 중) |
|---:|---|---:|---:|---:|---:|---:|
| 0 | **현행 `R85` (`skin_ratio >= 0.45`)** *(기준선)* | `0.594` | `27.9%` | `100.0%` (`17/17`) | **`90.0%` (`36/40`)** | `100.0%` (`8/8`) |
| 1 | 파레이돌리아 크기·노출 필터 단독 (`min_dim >= 65px & L >= 85`) | `0.394` | `29.3%` | `100.0%` (`17/17`) | `100.0%` (`40/40`) | **`12.5%` (`1/8`)** *(원본 클립 기준 `0/8`)* |
| 2 | **YuNet 눈 랜드마크 3D 실사 눈구멍 적색 중명도 (`eye_3d_flesh_socket >= 0.35`)** | `0.681` | **`100.0%`** | `35.3%` (`6/17`) | **`0.0%` (`0/40`)** | **`0.0%` (`0/8`)** |
| 3 | **볼 모공·수염 고주파 잔차 (`cheek_pore_hf >= 0.55`, 잉크선 마스킹)** | `0.735` | **`100.0%`** | `29.4%` (`5/17`) | **`0.0%` (`0/40`)** | **`0.0%` (`0/8`)** |
| 4 | 조명보정 헤모글로빈 적색도 (`Lab a*_p85 - 0.28 * b*_med >= 2.5`) | `0.729` | `87.5%` | `41.2%` (`7/17`) | `2.5%` (`1/40`) | `0.0%` (`0/8`) |
| 5 | 관자놀이+정수리 어두운 모발 래핑 (`dark_hair_wrap >= 0.12`) | `0.649` | `52.9%` | `52.9%` (`9/17`) | `17.5%` (`7/40`) *(트위드 모자·어두운 배경)* | `12.5%` (`1/8`) |
| 6 | 두피 모발 결 고주파 (`scalp_strand_energy >= 2.0`) | `0.654` | `63.6%` | `41.2%` (`7/17`) | `10.0%` (`4/40`) *(트위드 직물 결)* | `0.0%` (`0/8`) |
| 7 | 얼굴 내 색차 불균일도 (`chroma_heterogeneity >= 6.5`) | `0.549` | `31.2%` | `29.4%` (`5/17`) | `27.5%` (`11/40`) | `0.0%` (`0/8`) |
| 8 | 턱 수염·얼룩 색차 변이 (`jaw_beard_anomaly >= 0.45`) | `0.499` | `18.2%` | `11.8%` (`2/17`) | `22.5%` (`9/40`) *(턱 밑 난색 그림자)* | `0.0%` (`0/8`) |
| 9 | 2D 검은 잉크 눈 이진 대비 부재 (`eye_2d_bimodal < 0.06`) | `0.431` | `41.7%` | `29.4%` (`5/17`) | `17.5%` (`7/40`) *(실눈·측면 비닐)* | `0.0%` (`0/8`) |
| 10 | **복합 A안 (`HIGH_SUSPECT`: `#2 eye3d>=0.35` OR `#3 pore>=0.55` OR `wrap>=0.24 & strand<=8.5`)** | **`0.872`** | **`92.9%`** | **`76.5%` (`13/17`)** | **`0.0%` (`0/40`)** | `12.5%` (`1/8` -> 원본 클립 `0.0%`) |
| 11 | **복합 B안 (`MODERATE_SUSPECT` 포함 의심 추출선)** | `0.794` | `48.5%` | **`94.1%` (`16/17`)** | `40.0%` (`16/40`) | `12.5%` (`1/8` -> 원본 클립 `0.0%`) |
| 12 | **에피소드 교차검증 (`LOEO-CV` 로지스틱 회귀 — `Recall 100%` 고정 시)** | `0.775` | `30.4%` | `100.0%` (`17/17`) | **`95.0%` (`38/40`)** | `12.5%` (`1/8`) |
| 13 | **에피소드 교차검증 (`LOEO-CV` 로지스틱 회귀 — `Vinyl FPR <= 5%` 고정 시)** | `0.775` | `71.4%` | **`29.4%` (`5/17`)** | **`2.5%` (`1/40`)** | `12.5%` (`1/8`) |

### 1.3 실측 결론 및 채택 설계안: **『의심 컷 2단계 표시 + 타임코드·박스 증거 크롭 저장 → `@Research` Gate 2 최종 판정』**

1. **왜 단일·복합 픽셀 임계값으로 `Recall 100% + 정상 비닐 오탐 <= 5%` 동시 달성이 불가능한가 (물리적 원인 3가지)**:
   - **동일 재질 백색 모발(`ep09_c04_b0`)**: 얼굴과 **100% 동일한 매끈한 크림 비닐 색상·질감으로 조형된 흰색 단발머리**라 색상·주파수·랜드마크 모든 수치에서 대머리 크림 비닐과 차이가 `0`임(의미론적 형태 인식이 필수).
   - **천 모자·배경 창틀 vs 실제 모발(`ep09_c02_b0`, `ep12_c03_b1`)**: 택시 창틀 앞 트위드 모자(`wrap=0.51, strand=10.71`)가 실제 갈색 단발(`ep10_c05_b0`, `wrap=0.125`)보다 어두운 영역과 직물 고주파 에너지를 더 크게 만듦.
   - **턱 밑 난색 조명 그림자 vs 턱 갈색 패치 글리치(`ep10_c23_b0` vs `ep11_c01_b0`)**: 황색 실내등 아래 정상 비닐의 턱 그림자 색차(`jaw=0.901`)가 실제 턱 얼룩 결함(`jaw=0.575`)을 상회함.
2. **채택 아키텍처 (CEO 지시 조건부 설계안 그대로 적용)**:
   - **원본 클립 전용 샘플링 + 파레이돌리아 원천 제거**: 자막(`"with back"`)이나 데이터 스탬프(`"30%"`)가 구워진 최종 MP4 대신 **무자막 원본 클립(`03_visuals/clips/*.mp4`)의 실제 사용 구간 `[src_start_sec .. src_end_sec]`을 `0.25s` 간격**으로 스캔하고 `min_dim >= 65px & L_med >= 85 & non_ink_frac >= 0.15` 필터를 선적용해 무인 사물 오검출(`ep09_c16`, `ep10_c14`, `ep11_c19_b1`, `ep12_c12` 등 `8/8`건)을 `0%`로 제거합니다.
   - **`DQ8` 역할 전환 (`Hard Block` 해제 → `HIGH_SUSPECT / MODERATE_SUSPECT` 표시 + 증거 크롭 영구 저장)**:
     - `pipeline/source_reenactment.py`: `detect_human_faces_yunet_with_landmarks()` 추가(5점 랜드마크 반환, 기존 함수 시그니처 100% 호환 유지).
     - `pipeline/flow_diorama_sharded_worker.py`: 워커 생성 단계(`inspect_diorama_clip_cv`)에서 정상 난색 비닐을 무한 재시도시켜 `Omni 1.2` 크레딧을 낭비하던 `skin_ratio >= 0.45` 차단을 제거하고, 클립 리포트에 `dq8_suspects` 텔레메트리만 기록합니다.
     - `pipeline/dynamic_episode_qa.py` (`DQ8_zero_uncanny_skin_gore`):
       * 각 의심 컷·박스마다 **`05_assembly/dq8_suspect_crops/cut_{cut_idx:02d}_t{timeline_sec:05.2f}s_src{src_sec:05.2f}s_box{bi}.png`**(바운딩 박스 + 5점 랜드마크 + 수치 헤더 오버레이) 및 한눈에 보는 **`05_assembly/dq8_suspect_contact_sheet.jpg`**를 자동 생성합니다.
       * `dynamic_episode_qa_report.json` 내 `DQ8_zero_uncanny_skin_gore.suspect_detections` 배열에 `{cut_index, timeline_sec, src_clip_sec, frame_index, bbox_in_roi, bbox_in_frame, landmarks_5pt, yunet_score, suspect_tier ("HIGH_SUSPECT"|"MODERATE_SUSPECT"), triggered_features, metrics, crop_path}`를 전수 기록합니다.
       * `DQ8.passed`는 비(非)얼굴 객관 결함(네온 그린 유출 `> 0.08`, 의도치 않은 가로 분할선 `>= 0.72`)만 차단하고, 얼굴·머리카락 최종 합불은 `@Research` Gate 2로 넘깁니다.
     - `pipeline/posthoc_semantic_qa.py` (`@Research` Gate 2 연동):
       * `write_posthoc_semantic_review_template()` 실행 시 각 컷 엔트리에 `dq8_suspect_tier`, `dq8_suspect_crops` 경로, 그리고 필수 불리언 체크 키 **`zero_human_skin_or_hair_leak: null`**을 자동 주입합니다.
       * `@Research`가 Gate 2에서 `dq8_suspect_contact_sheet.jpg`(국소 크롭) + `posthoc_viewer_4up_sheet_*.jpg`(전 컷 시트, `ep09_c04` 백색 모발까지 포착)를 육안 대조하여 `zero_human_skin_or_hair_leak: false`로 판정하면 `posthoc-qa`가 즉시 `passed=False`로 해당 컷 재생성을 강제합니다.

---

## Part 2. 규칙 구조 재편 (`AGENTS.md` `6~8KB` · `<24KB` 분할 · `model_decision`) 및 3등급 코드 반영 계획

### 2.1 CEO 확정 3등급 분류표 반영 기준
- 참조 SSOT: [r85_r86_rule_3tier_triage_table.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/research/r85_r86_rule_3tier_triage_table.md)
- **CEO 추가 수정 1건 반영**: **1등급 #3(오염 레퍼런스 차단)**에 **`오픈 라이선스(Public Domain / CC-BY / CC-BY-SA 등) 확인 및 reference_provenance.json 출처 기록 필수`**를 하드 블록 요건으로 추가합니다.
- **Zero-Deletion 아카이빙**: 3등급 퇴역 규칙 `31개 묶음`과 구세대(`v4~v7`) 상수 해설문은 삭제해 버리지 않고 **`.agents/rules/_archive/retired_rules_2026-11-18.md`** 및 **`.agents/rules/_archive/retired_constants_v4_v7_2026-11-18.md`**에 원문 그대로 보존합니다(`frontmatter` 없음 · 하위 `_archive/` 폴더 분리로 자동 컨텍스트 주입 `0 byte`).
- **CEO 소유 파일 불변**: `.agents/rules/governance_roles.md`(`2,595 B`, `trigger: always_on`)는 **절대 수정하지 않습니다**.

### 2.2 규칙 파일별 분할 · 목표 용량(`< 24,000 B`) · `frontmatter` 매핑표

| 파일 경로 | 현재 크기 | 재편 후 목표 크기 | `frontmatter` (`trigger`) | 포함 규칙 (`R#`) 및 발동 `description` 요지 |
|---|---:|---:|---|---|
| `.agents/AGENTS.md` | `10,106 B` | **`~6,800 B`** (`6~8 KB`) | 없음 (워크스페이스 기본 주입) | 개정 불변 정체성 4종(비닐 귀·코 윤곽 2등급 분리), 핵심 상수 8개, 6채팅방, 5-Gear 스킬 맵, 1등급 12선 요약, `R1~R86 -> 파일` 전체 목차 |
| `.agents/rules/governance_roles.md` | `2,595 B` | **`2,595 B` (불변)** | `trigger: always_on` *(CEO 소유, 수정 금지)* | `R83, R83-5~7` 6채팅방 역할 헌장 및 증거 기반 사후 검증 |
| `.agents/rules/neuro_diorama_core_r56_r65.md` *(분할 신설 1)* | *(구 `49,313 B`)* | **`~11,500 B`** | `trigger: model_decision` | `R56~R65` (비닐 캐스트 기본, `R58` 오디오 마스터 클럭, `R59` 스테레오·ASS 자막, `R60` 타이틀, `R62` 동적 QA, `R63-P` 운율, `R64` 사후 검수, `R65 v4` 인스컬 50/50 썸네일) — *조립·자막·썸네일·QA 작업 시 호출* |
| `.agents/rules/neuro_diorama_v8_world_data_r66_r75.md` *(분할 신설 2)* | *(구 `49,313 B`)* | **`~14,500 B`** | `trigger: model_decision` | `R66, R67, R68(현행 v8), R70/R70-M, R71/R71-B, R72/R72-R(오픈 라이선스 provenance 포함), R73` — *대본·레퍼런스 수집·데이터 스탬프·오픈월드 기획 시 호출* |
| `.agents/rules/neuro_diorama_pacing_brain_r76_r86.md` *(분할 신설 3)* | *(구 `49,313 B`)* | **`~15,000 B`** | `trigger: model_decision` | `R76-1(솔로 Siren), R77(30fps 광류·무테두리), R78-M/H/V, R79-M(2등급), R80(3D 대조 화살표), R81(XL 콜아웃), R82(이원 속도·초반 드론), R85/R85-R(31번 AI 뇌·QA 정직성), R86(Semantic Beat Contract)` — *v8 비주얼 플랜·뇌 연출·화살표·프롬프트 작성 시 호출* |
| `.agents/rules/production_constants.md` *(참조 색인화)* | `74,677 B` | **`~19,500 B`** (`< 24 KB`) | **없음** (`pipeline/config.py` 참조용) | `pipeline/config.py` 섹션별 라인 맵 + 현행 활성 상수 요약표(구 `v4~v6` 장문 해설은 `_archive/`로 이관) |
| `.agents/rules/brain_depiction_rules.md` | `7,778 B` | `~6,800 B` | `trigger: model_decision` | `R21, R38(뇌 내부 기계소품 금지로 축소), R48, R53, R66, R81, R85, R85-R` — *뇌 해부 컷·시점·색상 설계 시 호출* |
| `.agents/rules/qa_gates_rules.md` | `5,523 B` | `~5,200 B` | `trigger: model_decision` | `R18-B, R25, R37, R62, R64, R85-R` (1등급 12선 vs 2등급 점수화 명세) — *QA 게이트 실행·수정 시 호출* |
| `.agents/rules/youtube_studio_operations.md` | `8,771 B` | `~7,800 B` | `trigger: model_decision` | `R4, R30/R30-B, R32, R34~R36-B, R75/R75-C/R75-S` (`R31, R33` 퇴역 이관) — *YouTube Studio 예약 업로드·댓글·채널 설정 시 호출* |
| `.agents/rules/channel_operations_rules.md` | `7,483 B` | `~6,900 B` | `trigger: model_decision` | `R8~R12, R28, R29, R83` — *프로젝트 폴더(`01..06`)·매니페스트·운영 거버넌스 확인 시 호출* |
| `.agents/rules/research_dossier_rules.md` | `5,114 B` | `~5,300 B` | `trigger: model_decision` | `R44, R44-D, R44-M, R50, R50-B` — *논문 DOI 도시에 검증·지식베이스 동기화 시 호출* |
| `.agents/rules/audio_assembly_rules.md` | `4,824 B` | `~3,800 B` | `trigger: model_decision` | `R49, R49-T, R58, R59, R63-P` (`R13, R16/17, R39/41/43` 퇴역 이관) — *ElevenLabs `Siren` 음성 합성·오디오 마스터·자막 조립 시 호출* |
| `.agents/rules/visual_prompt_spec.md` | `5,371 B` | `~4,100 B` | `trigger: model_decision` | `R5, R14-B(AI 텍스트 금지; locked-off 금지 삭제), R38(뇌 내부 한정), R46, R48, R54` — *Google Flow 엔진 라우팅·금지 토큰 점검 시 호출* |
| `.agents/rules/content_quality_rules.md` | `4,230 B` | `~3,400 B` | `trigger: model_decision` | `R1, R3, R15(2등급), R49-T, R73` (`R2/R2-B/R24/R26/R42` 퇴역 이관) — *대본 팩트체크·미국 구어체 작성 시 호출* |
| `.agents/rules/reference_depiction_rules.md` | `3,209 B` | `~3,100 B` | `trigger: model_decision` | `R44-M, R66, R67, R72-R, R85` (`R51/R52` 구 블루프린트 퇴역 이관 + 오픈 라이선스 provenance 명시) — *레퍼런스 팩 생성·검수 시 호출* |
| `.agents/rules/camera_choreography_rules.md` | `2,492 B` | `~2,200 B` | `trigger: model_decision` | `R66, R68, R72, R82, R85` (`R14-D v4, R55` 퇴역 이관) — *카메라 워크·드론·뇌 진입 전환 설계 시 호출* |
| `.agents/rules/scene_depiction_rules.md` | `2,369 B` | `~2,400 B` | `trigger: model_decision` | `R47, R68, R72, R86` — *2.5D 미니어처 디오라마 공간·소품 행동 연출 시 호출* |
| `.agents/rules/pillars_domain_rules.md` | `1,957 B` | `~2,100 B` | `trigger: model_decision` | `P1, R20` (2등급 다양성 지표) — *토픽 레이더·주제 큐 배분 시 호출* |
| `.agents/rules/cast_depiction_rules.md` | `1,803 B` | `~2,000 B` | `trigger: model_decision` | `R56, R68, R85` (`R14-A v4, R45 <=4 뇌 상한` 퇴역 이관 + 크림 비닐 귀·코 미세 윤곽 2등급 허용 명시) — *캐릭터 외형·의상 프롬프트 작성 시 호출* |

> [!NOTE]
> **기존 테스트 무충돌 처리 (`audit_rules_structure.py` 전수 조사 완료)**:
> `neuro_diorama_rules.md` 또는 `production_constants.md` 원문 문자열을 직접 읽는 기존 테스트 `10`개 파일(`test_expressive_25d_v8.py`, `test_neuro_diorama_v6.py`, `test_neuro_diorama_v7.py`, `test_porcelain_cinematic_v7.py`, `test_r65_v4_in_skull_cutaway_thumbnail.py`, `test_r68h_case_stamp_hook.py`, `test_r76_brain_simulator_and_pacing.py`, `test_r78_dual_material_and_siren_5tone.py`, `test_r84_mni152_pbr_cutaway_and_volume_compare.py`, `test_shorts90s_cdp_lease_and_flow_workspace.py`, `test_source_reenactment_qa.py`, `test_thumbnail_studio.py`)을 분할된 3개 파일 합산 리더 헬퍼 및 신규 예산(`AGENTS.md` `6,000~8,500 B`, 모든 활성 `.agents/rules/*.md < 24,000 B` + 유효 `frontmatter` 테스트)에 맞춰 동시 갱신합니다.

### 2.3 1·2·3등급 파이프라인 코드 반영 지점 전수 목록 (`pipeline/*.py`)

| 파일 경로 | 대상 함수 · 라인 | 변경 등급 | 구체적 코드 변경 명세 |
|---|---|---|---|
| `pipeline/config.py` | `R85_HUMAN_IDENTITY_LOCK_SUFFIX` | **1·2등급 분리** | `"no ears, no nose"` 강제 차단 문구를 `"smooth bald matte cream-white 2.5D vinyl head, zero hair, zero beard, zero photorealistic skin texture, 2D black ink eyes, minimalist earless noseless silhouette preferred"`로 개정 |
| `pipeline/real_world_reference_builder.py` & `pipeline/reference_image_qa.py` | `validate_real_world_refs_manifest()`, `inspect_reference_image_pack()` (`L1033~1545`) | **1등급 #3 강화 + 2등급 전환** | • **[1등급 추가]** 모든 외부/실세계 레퍼런스에 오픈 라이선스(`Public Domain / CC0 / CC-BY / CC-BY-SA`) 메타데이터 + `reference_provenance.json` 출처 기록 누락 시 즉시 `passed=False` 차단<br/>• **[1등급 유지]** `Q1`(해상도/비율/무레터박스), `Q4`(극단 실사 피부 누출만 차단, 비닐 귀·코 허용), `Q7`(번인 텍스트/워터마크 0), `Q11`(`@Research` Gate 1 서명)<br/>• **[2등급 전환]** `Q2`(야간 저조도), `Q3`(DOF 샤프니스), `Q5`(엔트로피), `Q6`(31번 실버·시안 뇌 색상비), `Q8/Q9`(컷 간 조명·의상 미세 편차), `Q10`(`dHash`)은 `advisory_warnings` + `reference_qa_score` 감점만 기록하고 `cv_pre_generation_ready`를 막지 않음 |
| `pipeline/dynamic_episode_qa.py` | `verify_final_mp4_against_contract()` (`L1378~2868`) | **2등급 전환 + 3등급 퇴역** | • **[1등급 유지]** `DQ3`(해부학 매칭; 단 구형 `v8 [0-70%]` 뇌 금지 조항은 제거), `DQ6`(클립 재탕 0), `DQ7`(정지 프레임 0), `DQ8`(네온/분할선 차단 + 의심 얼굴 크롭 Gate 2 이관), `DQ9`(배경 간판/외계어 0), `DQ10`(자막/콜아웃 안전영역·겹침 0), `DQ11`(오디오 무결성), `DQ13`(유령 디졸브·검은 렌즈 테두리 0), `DQ_R85`(`Blender` 화면 노출 0)<br/>• **[2등급 전환 (`advisory_gates`로 분리, `all_passed` 비차단)]** `DQ2`(의상/임팩트 미세 수치), `DQ4`(`WPM` 속도), `DQ5`(`±0.4s` 컷 길이·뇌 비중 `35~62%`·카메라 이동 비율), `DQ_R76_unified_brain_share`, `DQ_R79_human_character_motion`(`subj_p90_px >= 2.0`)<br/>• **[3등급 활성 게이트 퇴역 (레거시 동결 프로젝트만 보존)]** `DQ1_literal_analogy_frame_sync`, `DQ12_three_distinct_thumbnails`(단일 `thumbnail_selected.png` 존재만 확인), `DQ_CAMEO_single_minicortex`, `DQ_R76_brain_simulator_sq`, `DQ_R76_anti_noise_pacing` |
| `pipeline/prosody.py` | `evaluate_prosody_gates()` (`L842~1215`) | **1·2등급 분리** | • **[1등급 유지]** `P7`(음성 잘림/클리핑 0), `P9`(무음 사고·ASR 대본 불일치 0)<br/>• **[2등급 전환]** `P1~P6`, `P8`, `P10`(문장 간 호흡 간격 미세 편차), `P11`(`Siren` 5톤 피치 폭 `>= 6.5st`)은 `advisories` + `prosody_score`로만 기록하고 `passed=True` 허용 |
| `pipeline/thumbnail_studio.py` | `evaluate_thumbnail_gates()` (`L2099~2285`) | **1·2·3등급 분리** | • **[1등급 유지]** `TQ4`(안전영역), `TQ6`(파일 무결성), `TQ7`(`<=3w` 훅 단어수), `TQ8`(`50/50` 분할·두상 비가림), `TQ9`(화살표·텍스트 비겹침)<br/>• **[2등급 전환]** `TQ1~TQ3`(명도·채도·샤프니스 미학 점수)<br/>• **[3등급 퇴역]** Shorts에서 `TQ5_pairwise_distinct`(3종 상호 차이 강제) 비활성화 |
| `pipeline/prompt_quality_v5.py` & `pipeline/depiction_rules.py` | `validate_script_spine_v8_report()`, `validate_r85_*`, `validate_r86_*`, `BrainDepictionRule` | **1·2·3등급 분리** | • **[1등급 유지]** `R1` DOI/수치 일치, `R85` 드론 보행 동사·해부 시점·Blender 금지, `R86` Semantic Beat(`decorative=0`, `zero-delta=0`, `claim<->concrete_referent`), AI 텍스트 금지<br/>• **[2등급 전환 (`advisories` 반환)]** `FK <= 6.5`, 문장 단어수 `<= 22w`, 전문용어 `<= 2개`, 설명란 단어수 `55~135w`<br/>• **[3등급 퇴역]** `R57-H2` `Yet/But/Still` 강제, `R68-H` 연도 선행 오프닝 강제, `R74-B` 전반부 45% 뇌 금지, **`R38` 일상 비유 소품(`scales, locks, shutters` 등) 일괄 금지를 '뇌 해부 컷(`brain_clip=True`) 내부에서만 금지'로 축소**(`R86` 일상 물리 비유 컷 허용) |
| `pipeline/data_stamp_overlay.py` | `validate_data_stamps()` (`L466~735`) | **1·2등급 분리** | • **[1등급 유지]** 실증 DOI 보유 시 `illustrative`(`"Concept"`) 금지, 논문/도시에 검증 수치 100% 일치, 차트 바 숫자·강조 루프 겹침 `0px`(`R70-M8/M9`)<br/>• **[2등급 전환]** 편당 스탬프 `1개 vs 2개` 개수 및 스탬프 간 `<8s` 간격(`R70-M5/M6/M7`)은 경고로만 기록 |

---

## Part 3. `R86` Beat Card 4편(`Ep09_r82` ~ `Ep12`) `visual_plan.json` 반영 및 Phase 3 실행 절차

`@Research`가 작성 중인 `.agents/research/r86_beat_cards_ep09_12.json`(`[BEAT_CARDS_DONE]`) 수신 및 `@YouTube_CEO`의 `Phase 3 GO` 발령 시 아래 7단계 결정론적 절차로 반영합니다:

1. **Step 1 — 스키마 무결성 선검증 (`Dry-Run Merge & Lint`)**:
   - 각 에피소드(`v8_ep09_maguire_london_taxi_hippocampus_r82`, `v8_ep10_sleep_pill_brain_wash`, `v8_ep11_open_label_placebo_pain`, `v8_ep12_doorway_effect_memory`)의 `03_visuals/visual_plan.json`에 `r85_mode: true`, `r86_mode: true` 및 교체 대상 컷의 `R86 Beat Card` 필드(`claim`, `viewer_must_understand`, `visual_proof_type`, `visual_register`, `concrete_referent`, `metaphor_continuity_id`, `bridge_element`, `concept_id`, `state_delta`, `mechanism_seed`, `anti_filler_check`)를 병합합니다.
   - `compose_scene_from_r86_beat_card()`로 `scene` 프롬프트를 자동 합성하고, 드리프트 취약 컷(인간 클로즈업, `R80` 단절 화살표)에 `end_reference_image`를 연결합니다.
   - `main.py prompt-gate --dir <project_dir>` 실행 → **1등급 lint 오류 `0건`** 통과 확인(실패 시 Flow 호출 전 즉시 수정).
2. **Step 2 — 오염 레퍼런스 교체 & `R85` 31번 뇌 + MNI152 오프스크린 가이드 구성**:
   - `@Research` 검증 완료 JSON(`.agents/research/r85_verified_data_and_reference_audit.json`)의 교체 파일 및 `NEUROANATOMY_CUTAWAY_MAP`(오픈 라이선스 + `reference_provenance.json` 기록)으로 `HARD_REJECT` 8건을 교체합니다.
   - `/tmp/aab_real_refs/<project_id>/guides/`에 오프스크린 MNI152 위치 가이드 실루엣을 렌더한 뒤 `main.py porcelain-refs --project <id>`로 `0-credit` Flow `Image` 키프레임(31번 6-Scale 뇌 키프레임 + 교체 인간/드론/화살표 키프레임)을 생성합니다.
3. **Step 3 — `@Research` Gate 1 육안 서명 (`REVIEW_PENDING` 정지 → VLM 검수)**:
   - 파이프라인이 `REVIEW_PENDING`으로 정지하면 `@Research`에 컨택트 시트 경로를 전달해 `reference_semantic_review.json` 육안 서명을 받습니다(불합격 키프레임은 원천 재생성).
4. **Step 4 — `Ep10` 2문장(`S04`, `S12`) `Siren` 재합성 & 데이터 스탬프 `study` 전환**:
   - `Ep10`: `S04`(`"...across most of eighty-five brain zones."`)·`S12`(`"...zolpidem knocked lab mice out fast..."`) 2문장만 `el_siren_v4`로 문장 단위 재합성 → `script.json`·ASS 자막·EDL 갱신 → `Ep10`·`Ep12` 모두 `main.py prosody-qa` 1등급(`P7, P9`) 통과 확인.
   - `Ep10` 스탬프(`"Slow NE Pump Waves (Mice)"`, `"Brain Fluid Wash Drop (Mice)"`, `Hauglund et al. (2025, Cell — mice)`, `mode="study"`, DOI `10.1016/j.cell.2024.11.027`) 및 `Ep12` 스탬프 #2 `mode="study"` 전환 + `Ep10` `R35` 고정 댓글 초안(인간 `Eide 2021` vs 생쥐 `Hauglund 2025` 분리) 반영.
5. **Step 5 — 변경·결함 컷 선택적 Google Flow 클립 생성 (`Omni 1.2` + `Start+End` `Omni 1.1`)**:
   - 지문이 바뀐 컷(모든 구 `Blender` 뇌 컷 32개 + `R85/R86/DQ8` 결함 컷)만 무효화하여 단일 앵커 컷은 `Omni 1.2 Flash`, `Start+End` 드리프트 락 컷은 `Omni 1.1 Flash`로 렌더링합니다(기존 정상 통과 비닐 컷은 재사용해 크레딧 절약).
6. **Step 6 — 조립 · `DQ8` 증거 크롭 추출 · `@Research` Gate 2 육안 서명**:
   - `main.py diorama-assemble` + `main.py episode-qa` 실행 → `05_assembly/dq8_suspect_contact_sheet.jpg` 및 `posthoc_viewer_4up_sheet_*.jpg` 생성 후 `REVIEW_PENDING` 정지.
   - `@Research`가 Gate 2에서 전 컷 의미 전달(`delivers_viewer_must_understand`) 및 `zero_human_skin_or_hair_leak`을 육안 판정·서명합니다(결함 컷 발견 시 해당 컷만 재생성 후 재검수).
7. **Step 7 — 최상위 `final_shorts_<project_id>.mp4` 내보내기 및 CEO 사후 검증 보고**:
   - 기공개 영상 `tWjrK5enOoM`은 절대 건드리지 않고, 4편 모두 Gate 1·Gate 2 서명 및 `episode-qa`·`posthoc-qa`·`prosody-qa` 통과 확인 후 최상위 `07_Youtube/final_shorts_<project_id>.mp4`로 배치하여 `@YouTube_CEO`에 증빙 보고합니다.
