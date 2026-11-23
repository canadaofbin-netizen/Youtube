# 고정 시각 자산 라이브러리 v1 (`canonical_assets/v1`) 1차 전수 육안 선별 보고서 (`42`슬롯 · `138`후보)

> [!IMPORTANT]
> - **머신 리더블 선별 SSOT**: [research_screening_v1.json](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/BCI_Shorts_Channel/canonical_assets/v1/research_screening_v1.json)
> - **대조 기준 원본**: [benchmark_31_O2CmlKOk_brain_cuts_4frame_teardown.jpg](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/artifacts_archive/01_YouTube_CEO/benchmark_31_O2CmlKOk_brain_cuts_4frame_teardown.jpg) (`31_O2CmlKOk` 진짜 원본 4프레임 1:1 나란히 대조)
> - **전체 판정 요약**: **`42 / 42` 전 슬롯 유효 정본 확보 (`PASS`)** — 단, 기존 기본 `cand_01` 중 비례·해부·초점·배경 정합성이 더 우수한 **`15`개 슬롯의 1순위를 교체 승격**하고, 부적합 이상치 후보 **`29`개 파일을 영구 제외(`excluded_candidates`)** 처리함.

---

## 1. 가장 중요한 핵심 교정 4건 (미교정 시 후속 영상 드리프트 유발 항목)

1. **`B02_base_adult_female_turnaround` (`🚨 필수 승격: cand_02.png 단독 확정` / `cand_01·03·04 전면 제외`)**:
   - 기본 `cand_01` 및 `cand_03·04`가 모두 **6.5등신 백화점 마네킹 체형 + 3D 입술·콧대·음영 눈매**로 생성되어 그대로 쓰면 모든 성인 여성 캐릭터에서 실사형 얼굴 드리프트를 유발함. **유일하게 `cand_02.png`만 `B01(cand_03)`·`B03(cand_01)`과 100% 일치하는 `4.2등신` 대머리 크림 비닐 + 순수 2D 먹선 눈 정체성**을 지킴.
2. **성인/아동 등신대 통일 (`B01 -> cand_03`, `B04 -> cand_03`, `B12 -> cand_03`, `B03 cand_02·04` 및 `B14 cand_03` 제외)**:
   - 모든 성인 캐릭터(`B01, B02, B03, B11~B15, E06~E10`)를 **`4.2등신`**으로 통일하고 `2.5~3등신` 대두 치비 후보들을 전면 제외하여 컷 간 체형 점프를 원천 차단함.
3. **`E06_laboratory_staged` (`cand_01.png 단독 확정` / `cand_02·03·04 전면 제외`) & `E10_kitchen_staged` (`cand_02.png` 승격 / `cand_03·04` 제외)**:
   - 빈 방 기본판(`E01`, `E05`)과 1인 배치판(`E06`, `E10`)의 가구·모니터·창문 화각이 1:1로 일치하지 않는 변질 후보(`E06 cand_02~04` 빈 나무 상자 방 등)를 전면 제외함.
4. **뇌 `A05·A06·A08·A11` 정밀 승격 및 `A06 cand_04`(바닥 거울 반사)·`A11 cand_02`(암전 구역 내 혈관 침범) 제외**:
   - `A01~A12` 전 슬롯이 진짜 `31_O2CmlKOk`의 **밝은 백색 무광 석고 질감 + 고랑 속 굵은 불투명 하늘색 3D 혈관 튜브 + 입자·불꽃·후광·빛줄기 `0%` + 단색 진남색 배경**을 달성함. 그중 해부학적 완성도가 가장 뛰어난 `A05 cand_02`, `A06 cand_02`, `A08 cand_02`, `A11 cand_03`을 1순위로 승격함.

---

## 2. 분류별 전 슬롯(`42`종) 1순위 · 2순위 · 제외 후보 및 선정 사유

### Category A — 뇌 해부 마스터 (`A01`–`A12`, 원본 `31_O2CmlKOk` 1:1 대조)

| 슬롯 ID | 판정 | **1순위 (`rank_1`)** | **2순위 (`rank_2`)** | 제외 후보 (`exclude`) | 육안 대조 근거 (원본 `31_O2CmlKOk` 6대 기준 + 해부 시점) |
|---|:---:|---|---|---|---|
| `A01_mode1_translucent_head_lateral` | `PASS` | `cand_01.png` | `cand_04.png` | `cand_02, cand_03` | 밝은 회색 마네킹 두상 + 상단 투명 두개골 내부 무광 백색 뇌·불투명 하늘색 혈관 일치 (`cand_03` 이중 유리 테두리·`cand_02` 상단 협소 제외) |
| `A02_mode2_whole_brain_lateral` | `PASS` | `cand_01.png` | `cand_02.png` | — | 원본 `t=39.3s`와 무광 백색 석고 질감·굵은 하늘색 혈관·이펙트 `0%`·단색 남색 배경 완벽 일치 (`cand_01` 실비우스열 비례 최우수) |
| `A03_mode2_whole_brain_dorsal_topdown` | `PASS` | `cand_01.png` | `cand_02.png` | — | 원본 `t=68.6s` 상단 부감 대칭 양반구·고랑 속 하늘색 분지 혈관 튜브 완벽 일치 |
| `A04_mode2_whole_brain_anterior_frontal` | `PASS` | `cand_01.png` | `cand_02.png` | — | 정면 양측 전두엽 대칭과 하단 뇌간 비례 및 프레임 점유율이 가장 안정적 (`cand_01` 1순위) |
| `A05_sulcal_vessel_macro` | `PASS` | **`cand_02.png` ⬆️** | `cand_01.png` | — | 원본 `t=30.2s`처럼 중앙 고랑을 상하로 관통하는 굵고 매끄러운 하늘색 Y자 혈관 연속성이 `cand_02`에서 가장 명확함 |
| `A06_hippocampus_cutaway` | `PASS` | **`cand_02.png` ⬆️** | `cand_01.png` | `cand_04` | 좌향 외측 하방 측두엽 절개창 속 단색 매트 황금 해마 노출이 `cand_02`에서 가장 선명 (`cand_04` 하단 바닥 반사광 제외) |
| `A07_thalamus_brainstem_midsagittal` | `PASS` | `cand_01.png` | `cand_02.png` | — | 정중시상면 뇌량·단색 매트 황금 시상·뇌간·소뇌 충부(arbor vitae)가 무발광 석고 질감으로 정확히 구현됨 |
| `A08_insula_operculum_retracted` | `PASS` | **`cand_02.png` ⬆️** | `cand_01.png` | — | 실비우스 덮개 견인 창이 가장 깔끔하고 부채꼴 섬엽 이랑이 정교한 `cand_02` 승격 (`cand_01` 하단 늘어진 피질 조각 2순위) |
| `A09_prefrontal_cortex_3q_anterolateral` | `PASS` | `cand_01.png` | `cand_02.png` | — | 좌전측방 전전두엽 전체가 후광·불꽃 없이 단색 매트 황금 재질로 명확히 구분됨 |
| `A10_signal_segment_sample` | `PASS` | `cand_01.png` | `cand_03.png` | `cand_04` | 원본 `t=39.3s`와 동일하게 고랑 내부에 고체 매트 황금 마디만 깔끔히 위치 (`cand_04` 소뇌 경계 찍힘 제외) |
| `A11_region_shutdown_sample` | `PASS` | **`cand_03.png` ⬆️** | `cand_01.png` | `cand_02` | 전전두엽 암전 구역 내부 혈관까지 완전 소등되어 경계가 가장 칼같은 `cand_03` 승격 (`cand_02` 하늘색 혈관 침범 제외) |
| `A12_dual_brain_top_bottom_compare` | `PASS` | `cand_01.png` | `cand_02.png` | — | 잘림·이음매 `0%` 온전한 좌향 2뇌 상/하 부유 비교(상단 매트 황금 vs 하단 매트 슬레이트) 완벽 |

### Category B — 캐릭터 기본형 · 표정 · 의상 (`B01`–`B15`)

| 슬롯 ID | 판정 | **1순위 (`rank_1`)** | **2순위 (`rank_2`)** | 제외 후보 (`exclude`) | 육안 선별 근거 (`0%` 모발·실사피부 + `4.2등신` 비례 통일 + 2D 먹선 눈) |
|---|:---:|---|---|---|---|
| `B01_base_adult_male_turnaround` | `PASS` | **`cand_03.png` ⬆️** | `cand_01.png` | `cand_02, cand_04` | `4.2등신` 성인 표준 비례 + 차분한 2D 먹선 눈 (`cand_02·04` 유아/치비 비례 제외) |
| `B02_base_adult_female_turnaround` | `PASS` | **`cand_02.png` 🚨⬆️** | *(단독 확정)* | `cand_01, cand_03, cand_04` | **필수 교정**: `cand_01·03·04`는 6.5등신 3D 입술·코 마네킹 드리프트; 오직 `cand_02`만 `4.2등신` 대머리 비닐 + 2D 먹선 눈 일치 |
| `B03_base_older_adult_turnaround` | `PASS` | `cand_01.png` | `cand_03.png` | `cand_02, cand_04` | 실사 주름 없이 2D 먹선 이마선만으로 노년 표현 + `4.2등신` 성인 비례 일치 (`cand_02·04` 치비 비례 제외) |
| `B04_base_child_turnaround` | `PASS` | **`cand_03.png` ⬆️** | `cand_04.png` | `cand_02` | 성인 대비 명확히 작은 `3.2등신` 아동 비례 + 깔끔한 평면 2D 점/선 먹선 눈 (`cand_02` 성인 키 근접 제외) |
| `B05_expr_surprised` | `PASS` | `cand_01.png` | `cand_04.png` | — | 동그란 2D 먹선 눈 + `'O'`자 입 놀람 표정 및 매끈한 크림 비닐 헤드 |
| `B06_expr_joy` | `PASS` | **`cand_02.png` ⬆️** | `cand_03.png` | — | 볼 3D 주름 골 없이 매끈한 비닐 위에 2D 반달 먹선 눈·미소가 가장 깔끔한 `cand_02` 승격 |
| `B07_expr_worry` | `PASS` | **`cand_03.png` ⬆️** | `cand_01.png` | `cand_04` | 팔자형 2D 먹선 눈썹과 균일한 배경이 가장 깔끔한 `cand_03` 승격 (`cand_04` 우측 배경 모서리 줄 제외) |
| `B08_expr_focus` | `PASS` | **`cand_02.png` ⬆️** | `cand_03.png` | `cand_01` | 모은 2D 먹선 눈썹으로 집중 감정이 명확한 `cand_02` 승격 (`cand_01`은 놀란 둥근 눈이라 제외) |
| `B09_expr_confusion` | `PASS` | **`cand_04.png` ⬆️** | `cand_01.png` | — | 비대칭 눈썹 + 물결 입매 + 턱 짚는 손동작으로 `0.2s` 내 '혼란/의문'이 가장 잘 읽히는 `cand_04` 승격 |
| `B10_expr_eureka` | `PASS` | `cand_01.png` | `cand_03.png` | — | 검지 든 유레카 포즈와 평면 2D 먹선 눈·미소가 과도한 코 음영 없이 가장 담백함 |
| `B11_wardrobe_white_lab_coat` | `PASS` | **`cand_03.png` ⬆️** | `cand_01.png` | — | 눈두덩 3D 굴곡 없이 순수 2D 먹선 점눈과 흰 가운 핏이 가장 단정한 `cand_03` 승격 |
| `B12_wardrobe_surgical_scrubs` | `PASS` | **`cand_03.png` ⬆️** | `cand_01.png` | `cand_02` | `4.2등신` 성인 비례와 청록 수술복이 깔끔한 `cand_03` 승격 (`cand_02` 대두 치비 제외) |
| `B13_wardrobe_casual_everyday` | `PASS` | `cand_01.png` | `cand_02.png` | — | 올리브 니트 + 베이지 바지 일상복으로 `E08·E10` 실내 배치 인물과 1:1 호환 |
| `B14_wardrobe_formal_suit` | `PASS` | `cand_01.png` | `cand_02.png` | `cand_03` | 네이비 정장 수트 + `4.2등신` 성인 비례 일치 (`cand_03` 짧은 치비 체형 제외) |
| `B15_wardrobe_student` | `PASS` | `cand_01.png` | `cand_03.png` | — | 버건디 재킷·백팩·청바지 대학생 의상 + `4.2등신` 대머리 비닐 균일 |

### Category C · D · E — `R80` 화살표 (`C01`–`C03`) · `120ft` 드론 (`D01`–`D02`) · 공간 (`E01`–`E10`)

| 슬롯 ID | 판정 | **1순위 (`rank_1`)** | **2순위 (`rank_2`)** | 제외 후보 (`exclude`) | 육안 선별 근거 (착시 `0%` · 무문자 · 빈 방↔배치 방 1:1 공간 일치) |
|---|:---:|---|---|---|---|
| `C01_arrow_straight_corridor` | `PASS` | `cand_01.png` | `cand_03.png` | — | `90°` 탑다운 크림 블록 사이 끊김 `0%` 단일 `#FF2525` 직선 3D 화살표 (무문자·무보행자) |
| `C02_arrow_adaptive_zigzag` | `PASS` | `cand_01.png` | `cand_03.png` | `cand_02` | `C01(cand_01)`과 블록·도로·출발 원 스케일이 1:1 호환되는 다중 우회 지그재그 (`cand_02` 미세 격자 제외) |
| `C03_arrow_doorway_sever_gap` | `PASS` | `cand_01.png` | `cand_03.png` | `cand_02` | 풀프레임 원목 마루 위 문턱 앞에서 물리적으로 절단된 `#FF2525` 화살표 + 문 너머 소실 점선 (`cand_02` 외곽 흰 테두리 제외) |
| `D01_drone_university_campus_120ft` | `PASS` | `cand_01.png` | `cand_04.png` | `cand_02, cand_03` | 주변부 블러·안개 없이 선명한 `120ft` 붉은 벽돌 대학 캠퍼스 돔·광장 + 점 크기 보행자 (`cand_02` 블러·`cand_03` 안개 제외) |
| `D02_drone_medical_hospital_120ft` | `PASS` | **`cand_02.png` ⬆️** | `cand_04.png` | `cand_01, cand_03` | 무문자 현대식 병원 원형 중정이 화면 끝까지 가장 선명한 `cand_02` 승격 (`cand_01` 상하 블러·`cand_03` 빛번짐 제외) |
| `E01_laboratory_empty` | `PASS` | `cand_01.png` | `cand_03.png` | — | 채광 좋은 원목 연구 책상·듀얼 모니터·시약장 무문자 기본판 (`E06 cand_01`과 1:1 일치) |
| `E02_mri_suite_empty` | `PASS` | `cand_01.png` | `cand_03.png` | — | 포스터·균열 `0%` 청결한 3T MRI실 기본판 (`E07 cand_01`과 1:1 일치) |
| `E03_home_doorway_empty` | `PASS` | `cand_01.png` | `cand_02.png` | — | 햇살 원목 마루와 열린 흰 문틀 기본판 (`E08 cand_01`과 1:1 일치) |
| `E04_lecture_room_empty` | `PASS` | `cand_01.png` | `cand_02.png` | — | 아치창·계단식 원목 강의석·무문자 칠판 기본판 (`E09 cand_01`과 1:1 일치) |
| `E05_kitchen_empty` | `PASS` | `cand_01.png` | `cand_03.png` | — | 자연광 주방 아일랜드 식탁·머그잔 기본판 (`E10 cand_02·01`과 1:1 일치) |
| `E06_laboratory_staged` | `PASS` | `cand_01.png` | *(단독 확정)* | `cand_02, cand_03, cand_04` | `E01(cand_01)`과 유일하게 1:1 일치 (`cand_02~04`는 모니터·장비가 사라진 빈 나무 상자 방으로 변질되어 전면 제외) |
| `E07_mri_suite_staged` | `PASS` | `cand_01.png` | `cand_03.png` | `cand_02` | `E02(cand_01)`과 1:1 일치 + 자연스러운 의료진 스케일 (`cand_02` 인물 키 과대 제외) |
| `E08_home_doorway_staged` | `PASS` | `cand_01.png` | `cand_02.png` | — | `E03(cand_01)` 문틀을 자연스럽게 통과하는 올리브 니트 비닐 캐릭터 |
| `E09_lecture_room_staged` | `PASS` | `cand_01.png` | `cand_02.png` | — | `E04(cand_01)` 연단 위 정장 강연자 스케일·포즈 일치 |
| `E10_kitchen_staged` | `PASS` | **`cand_02.png` ⬆️** | `cand_01.png` | `cand_03, cand_04` | `E05(cand_01)`과 1:1 화각 일치 + 얼굴 역광 그늘이 적어 2D 먹선 눈이 선명한 `cand_02` 승격 (`cand_03·04` 창문 위치 불일치 제외) |
