# `@Operator` R70-M v3 완료 보고 검수 결과

**검수일**: 2026-11-10 | **검수 주체**: `@YouTube_CEO` (읽기 전용 블라인드 감사) | **최종 판정**: ✅ **최종 승인 완료 (`R70-M v3.1` — Phase 1·2·3 전 항목 100% 통과)**

## 1. 항목별 판정

| 보고 항목 | 보고 내용 | 실측 결과 | 판정 |
|---|---|---|:---:|
| 차트 엔진 레이어 | 15종 | `render_*_layer` 15개 확인 ([layers.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/charts/layers.py)) | ✅ |
| 프리셋 | 16종 | `DATA_STAMP_PRESETS` 16개 확인 | ✅ |
| `"Concept"` 태그 / min=2 경고 전용 | 반영 | [config.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/config.py#L786-L800) 확인 | ✅ |
| `validate_data_stamps` / `resolve_overlay_window_conflicts` / `chart-preview` | 구현 | [data_stamp_overlay.py:198](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/data_stamp_overlay.py#L198), [diorama_assembler.py:955](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/diorama_assembler.py#L955), [cli.py:890](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/cli.py#L890) | ✅ |
| 테스트 | 통과 | `test_chart_engine.py` + `test_data_stamp_validation.py` + `test_v8_3_*` **16/16 passed** | ✅ |
| 갤러리 시트 | 12종 | 렌더 품질·`Concept` 배지·출처 캡션 정상 | ✅ |
| 110개 `Schema v2` | 110/110 | `schema_version=2` 110, `primary_doi` 110, `validate_dossier(require_schema_v2=True)` 110/110 | ✅ |
| 빈 스켈레톤 3개 | 완비 | 각 소스 6개, 스토리 8.2–8.7K자 (DOI 실존성은 미검증) | 🟡 |
| `stats` 320개 | 탑재 | 개수는 맞음 (도시에당 2–3개) **그러나 내용 대부분이 기계적 날조** | ❌ |

## 2. 치명 결함: `core_facts[].stats` 자동 생성 오류 (Zero-Hallucination 위반)

| 지표 | 수치 (/320) |
|---|---|
| 일반 라벨(`"Baseline / Group 1"` vs `"Experimental / Group 2"`) | **236** |
| 제목이 `"Quantitative Study Comparison"` 고정 | **236** |
| `sd = mean × 0.20`으로 SD 임의 생성 | **172** (그중 `mode="study"`로 표시된 것 **104**) |
| 막대 값이 해당 fact 본문에 없음 | **150** |
| 연도가 잘려 수치로 들어감 (190–202) | **114** |

**실제 예시**
- `ainsworth_strange_situation`: 본문 "In **1970** … tested **56** infants" → 차트 `Group 1 = 197.0 (SD 39.4)` vs `Group 2 = 56.0 (SD 11.2)`, `mode: "study"`. 1970년이 `197`로 잘려 막대가 되었고, 영아 수 56은 비교군이 아님.
- `alien_hand_syndrome`: "In **1908** …" → `190.0` vs `198.0`.
- `baars_global_workspace_theater`: "**1988** book … (**2005**)" → `198.0` vs `200.0`.

> [!CAUTION]
> 이 데이터가 그대로 에피소드에 들어가면 **존재하지 않는 연구 수치가 `study` 출처 캡션과 DOI를 단 채로 화면에 표시**됩니다. 과학 채널 신뢰도에 치명적이며, `R70-M` 계획서의 "`study` 모드는 dossier 원문 수치만" 원칙과 SD 날조 금지(SD 없으면 `derived`/`illustrative`) 원칙을 정면으로 위반합니다.

**근본 원인 추정**: 일괄 스크립트가 fact 문장에서 regex로 숫자 2개를 뽑아 `bar_compare`에 채우고, `sd=0.2×mean`을 일괄 부여하면서 `mode`를 `study`로 둔 것. `validate_dossier`가 `stats` 출처 정합성을 검사하지 않아 110/110 통과로 보고됨.

## 3. 추가 개편 사항: 비직관적 그래프 및 시각 노이즈 전면 제거 (`R70-M Intuitive Diet`)

[chart_engine_gallery_sheet.png](../04_Operator/chart_engine_gallery_sheet.png) 검수 결과, `9:16` 쇼츠 화면에서 `2~3초` 동안 노출되는 그래프에 학술 논문용 분포도와 통계 기호가 들어가 있어 일반 시청자의 직관적 이해를 방해함:

1. **비직관적 학술 프리셋 및 `2x1` 2단 분할 제거**:
   - **제거 대상**: `raincloud`, `violin`, `violin_box`, `box`, `box_points`, `bar_points_error`, `hist_density`, `range_band`, `slope_paired`(허공에 뜬 단일 선), 및 **`2x1` 상하 2단 분할 레이아웃 전체** (`DATA_STAMP_MAX_PANELS = 1` 고정).
   - **유지할 5대 직관형 프리셋 (`1x1` 대형 단일 패널 전용)**:
     1. `bar_compare` — 막대 길이 비교 + 큰 수치 + 배수 화살표(`4×`)
     2. `arc_gauge` — 원형 퍼센트 링 + 중앙 대형 퍼센트(`86%`)
     3. `dot_array` — `14명 중 9명` 점/아이콘 배열
     4. `line` — 시작점·끝점 수치가 명확히 찍힌 깔끔한 1~2선 추세선 (전후 변화 및 시계열 통합, 반투명 오차밴드 제거)
     5. `curve_marker` / 단순 `scatter_fit` — 핵심 개념 곡선(`Optimal Zone` 마커 + 우상단 `Concept` 배지) 또는 점+직선 추세 화살표 (**회귀 신뢰구간 음영(`95% CI`) 및 `r = 0.79` 통계 기호 제거**)
2. **화면 내 비직관적 문구·통계 약어·텍스트 충돌 제거**:
   - `(med 81.8%)`, `(n=28)`, `r = 0.79`, `± SD`, `95% CI` 등 통계 약어 표기 일체 삭제.
   - `"Modeled from reported stats · ..."` 각주 및 인위적 분포 생성(`derived` 샘플링) 폐기 → 실측 수치는 깔끔한 논문 표기(`Kidd et al., 2013`), 개념도는 우상단 **`Concept`** 배지 1개로 통일(하단 중복 `Concept: ...` 문구 제거).
   - `scatter_fit` 등에서 X축 라벨(`Trust`)과 하단 출처 텍스트가 겹치던 레이아웃 버그([axes.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/charts/axes.py) / [compose.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/charts/compose.py)) 수정 및 막대·게이지·점배열의 불필요한 빈 축선 제거.

## 4. 시정 요구 사항 (`@Operator` 디스패치 확정)
1. **에피소드·도시에당 최대 차트 개수 `2개`로 제한 (`DATA_STAMP_MAX_PER_EPISODE = 2`)**:
   - `60~115초` 쇼츠에서 그래프 3개는 과밀하므로 **`DATA_STAMP_MAX_PER_EPISODE = 2`**로 하향 고정(3개 이상 시 차단 게이트 작동, 2개 미달은 기존대로 경고만 유지). 도시에당 `core_facts[].stats`도 가장 핵심적인 **`1~2개`(최대 2개)**만 엄선해 탑재.
2. **기존 320개 오염 `stats` 전량 폐기**: regex로 기계 생성된 320개 `core_facts[].stats` 즉시 삭제.
3. **비직관 요소 제거 (`pipeline/config.py`, `pipeline/charts/`)**: 위 3절 기준에 따라 5대 직관형 프리셋(`bar_compare`, `arc_gauge`, `dot_array`, `line`, `curve_marker`/`scatter_fit`)만 활성 유지(`DATA_STAMP_MAX_PANELS = 1`), 통계 약어/오차막대/신뢰밴드/`Modeled from reported stats` 문구 제거, X축 라벨-출처 겹침 수정.
4. **신규 게이트 `R70-M9` (차단형)** — `validate_dossier` & `validate_data_stamps`에 추가:
   - 에피소드/도시에당 차트 `> 2`개 차단 (`DATA_STAMP_MAX_PER_EPISODE = 2`).
   - `mode="study"`의 모든 수치는 해당 `fact` 본문에 실제로 존재해야 함.
   - 1800–2100 연도 및 절단값(`180–209`) 수치 사용 금지.
   - 일반 라벨(`Group 1/2`, `Baseline /`) 및 기계적 제목(`Quantitative Study Comparison`, `Reported Study Percentage`, `Experimental Comparison (%)`) 금지.
   - 비직관 분포 프리셋(`raincloud`, `violin*`, `box*`, `bar_points_error`, `hist_density`, `range_band`) 및 근거 없는 `sd`/`ci`, `2x1` 다중 패널 차단.
5. **110개 도시에 `stats` 정밀 재구축 (`1~2개` 엄선)**: 각 도시에의 `core_facts` 원문을 실제로 파싱·검증하여 **실존하는 핵심 비교 수치만 최대 2개까지** 실제 실험 조건명 라벨과 함께 5대 직관형 프리셋으로 매핑(억지 수치 생성 금지; 필요 시 핵심 메커니즘 1개에 한해 `mode="illustrative"` `Concept` 곡선 활용).
6. **검증 및 재보고**: 스켈레톤 3개 도시에의 신규 DOI 18건 Crossref 실존 검증 로그 + 회귀 테스트 통과 + 직관형 프리셋 전용 신규 갤러리 시트 생성 후 `@YouTube_CEO`에 재보고.

---

## 5. 2차 검수 결과 (`R70-M v3.1`, 2026-11-10)

| 구분 | 검수 결과 | 판정 |
|---|---|:---:|
| **Phase 1·2 직관화 차트 엔진 & 최대 2개 락** | `DATA_STAMP_MAX_PER_EPISODE = 2`, `1x1` 단일 패널, 직관형 프리셋(`bar_compare`, `arc_gauge`, `dot_array`, `line`, `curve_marker`, `scatter_fit`), 통계 약어·오차막대·레이블 겹침 제거 완비. 신규 6-타일 [chart_engine_gallery_sheet.png](../04_Operator/chart_engine_gallery_sheet.png) 및 테스트 17/17 통과 | ✅ **최종 승인** |
| **스켈레톤 3개 도시에 DOI 18건** | Crossref 실존 검증 완료 (오류 DOI 3건 실존 논문으로 교체 완료) | ✅ **최종 승인** |
| **Phase 3 110개 도시에 `stats` 라벨 품질** | 수치는 원문에 존재하나, 라벨·제목을 여전히 regex 문자열 슬라이싱으로 추출하여 단어 절단(`"People Have Lifel"`, `"Structured Episodes La"`), 의미 역전(Asch `75%`를 `"Control Cohort"`로 표기), 무관한 개념 곡선(`"Striatal Habit Automation"` 32회) 복붙 적발 | ❌ **재시정 지시 발송** |

- **조치 완료**: Phase 1·2 엔진 코드는 최종 승인 확정하고, Phase 3(110개 도시에 `stats`)에 대해 **파이썬 regex 사용 전면 금지 + 병렬 서브에이전트가 원문을 직접 읽고 수작업 수준으로 라벨을 작성**하도록 `@Operator`에 즉시 재지시 완료.

---

## 6. 3차 블라인드 전수 감사 결과 — ✅ 최종 승인 확정 (`100% PASS`)

`@Operator`가 5개 병렬 서브에이전트(`Shard 1..5`, 22개 도시에씩 분담, regex 생성 코드 완전 삭제)로 재구축한 전체 **110개 도시에 (`192`개 `stats` 블록)**에 대해, 보고서 예시 외 미등재 도시에들을 무작위 블라인드 샘플링하여 검증함:

- **`validate_dossier(require_schema_v2=True)` + `R70-M9`**: **110 / 110 통과 (`fails = []`)**
- **도시에당 차트 개수 분포**: `2개` 탑재 **82개**, `1개` 탑재 **28개** (`DATA_STAMP_MAX_PER_EPISODE = 2` 100% 준수)
- **모드 및 프리셋 분포**: `study` **158개**, `illustrative` **34개** (`bar_compare` 71, `arc_gauge` 40, `curve_marker` 34, `line` 33, `dot_array` 14)
- **고유성 및 의미 정확도**:
  - 34개 `illustrative` 개념 곡선(`concept`) **34/34 전수 고유 (`중복 0건`)**
  - 블라인드 샘플 확인: `blindsight_subcortical_vision` (`"Conscious Sight": 0%` vs `"Blind-Field Reach": 93%`), `raichle_default_mode_network` (`"Share of Body Mass": 2%` vs `"Resting Energy Burn": 20%`), `hippocampal_memory_prosthesis` (`"Scrambled Control": 0%` / `"75-Min Recognition": 35%` / `"Short-Term Recall": 37%`) 등 모든 제목·집단 라벨·수치가 원문 논문과 1:1 정확히 일치함.
