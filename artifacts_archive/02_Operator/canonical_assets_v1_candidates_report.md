# Canonical Asset Library v1 — 후보군 구축 및 검증 보고서 (`status: "candidate"`)

> [!IMPORTANT]
> 사용자 원문 지시(*"기본이 되고 근본이 되는 레퍼런스를 모두 만들어 놓고 보고해"*, *"반복해서 쓸 수 있는 기반이 될 레퍼런스 이미지들"*) 및 `@YouTube_CEO` 중간 보강 지시 4개 항목·`@Research` 1차 전수 스크리닝을 모두 반영하여 **총 5대 카테고리 · 42개 슬롯 · 128개 후보 PNG (`1080x1920`, `SHA-256` 100% 일치)** 구축을 완료했습니다. 사용자 최종 승인 전까지 모든 항목은 `"status": "candidate"`로 잠금 유지되며, `Ep09` 뇌 키프레임 재생성은 라이브러리 승인 직후 착수합니다.

## 1. 산출물 및 컨택트 시트 경로

- **라이브러리 루트**: [canonical_assets/v1](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/BCI_Shorts_Channel/canonical_assets/v1)
- **매니페스트 (`42`슬롯 · `128`후보 `SHA-256` · 프롬프트 · 출처 · 사용 규칙)**: [manifest.json](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/BCI_Shorts_Channel/canonical_assets/v1/manifest.json)
- **`@Research` 1차 전수 선별 영수증**: [research_screening_v1.json](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/BCI_Shorts_Channel/canonical_assets/v1/research_screening_v1.json)
- **카테고리별 비교·후보 시트 (6종)**:
  1. **원본 `31_O2CmlKOk` 4프레임 vs `A01~A12` 1순위 1:1 대조 시트**: [canonical_v1_00_brain_vs_31_sheet.jpg](../01_YouTube_CEO/00_A_brain_vs_31_O2CmlKOk_comparison_sheet.jpg) ([원본 경로](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/BCI_Shorts_Channel/canonical_assets/v1/sheets/00_A_brain_vs_31_O2CmlKOk_comparison_sheet.jpg))
  2. **Category A — 뇌 12슬롯 전체 후보 시트 (`Rank 1~2`: `89~96%` 고밀도 혈관 보강안 / `Rank 3~4`: 중형 비교안)**: [canonical_v1_01_A_brain_sheet.jpg](../01_YouTube_CEO/01_category_A_brain_candidates_sheet.jpg)
  3. **Category B — 캐릭터 체형(4)·표정(6)·의상(5) 15슬롯 시트**: [canonical_v1_02_B_characters_sheet.jpg](../01_YouTube_CEO/02_category_B_characters_candidates_sheet.jpg)
  4. **Category C — `R80` `#FF2525` 탑다운 3D 대조 화살표 3슬롯 시트**: [canonical_v1_03_C_arrows_sheet.jpg](../01_YouTube_CEO/03_category_C_arrows_r80_candidates_sheet.jpg)
  5. **Category D — `120ft` 고고도 캠퍼스·병원 드론 2슬롯 시트**: [canonical_v1_04_D_drone_sheet.jpg](../01_YouTube_CEO/04_category_D_drone_120ft_candidates_sheet.jpg)
  6. **Category E — 5대 반복 장소 빈 방(`E01~E05`) & 1인 스케일 배치(`E06~E10`) 10슬롯 시트**: [canonical_v1_05_E_environments_sheet.jpg](../01_YouTube_CEO/05_category_E_environments_candidates_sheet.jpg)

````carousel
![원본 31_O2CmlKOk vs A01-A12 1:1 대조 시트](../01_YouTube_CEO/00_A_brain_vs_31_O2CmlKOk_comparison_sheet.jpg)
<!-- slide -->
![Category A: 뇌 A01-A12 후보 시트](../01_YouTube_CEO/01_category_A_brain_candidates_sheet.jpg)
<!-- slide -->
![Category B: 캐릭터 B01-B15 후보 시트](../01_YouTube_CEO/02_category_B_characters_candidates_sheet.jpg)
<!-- slide -->
![Category C: R80 화살표 C01-C03 후보 시트](../01_YouTube_CEO/03_category_C_arrows_r80_candidates_sheet.jpg)
<!-- slide -->
![Category D: 120ft 드론 D01-D02 후보 시트](../01_YouTube_CEO/04_category_D_drone_120ft_candidates_sheet.jpg)
<!-- slide -->
![Category E: 반복 장소 E01-E10 후보 시트](../01_YouTube_CEO/05_category_E_environments_candidates_sheet.jpg)
````

---

## 2. `@YouTube_CEO` 뇌 4대 중간 보강 반영 수치 (`A01~A12`)

1. **표면 전체 촘촘하고 굵은 하늘색 혈관망(`#27D8FF`) + 가장자리 광택 림**: Mode 2 전체·단면 뇌의 혈관 면적 비중을 기존 `8.5~11.3%`에서 **`24.4~39.0%`**로 끌어올려 원본 `31_O2CmlKOk`(`23.4%`) 및 `A05` 근접샷(`32.3%`)과 동일한 혈관 굵기·밀도를 구현했습니다.
2. **`A01` Mode 1 반투명 유리 두상 투시**: 불투명 흰 흉상 느낌을 제거하고 **얼굴·이마·관자·귀·두개골 전체가 속이 비치는 55% 투명 유리 쉘**(`cand_01.png`, 외곽 유리 반사광이 뇌 앞쪽으로 겹침)로 보강하여 뇌가 두상 내부에 들어 있는 구조를 명확히 했습니다(발광 후광·입자 `0`개).
3. **`A03` 상면 키라이트 밝기 통일**: 어두웠던 상면 회색 톤(`V=165.1`)을 좌상단 `45°` 고휘도 스튜디오 키라이트(**`V=208.8`**)로 맞춰 `A02`(`191.5`), `A04`(`206.8`), `A06~A12`(`187.2~214.1`)와 조명을 완전히 통일했습니다.
4. **가로폭 `80~90%+` 히어로 채움 + 중형 프레임 병기**: `cand_01.png`·`cand_02.png`에 가로폭 **`88.9~95.7%`**(잘림 없는 풀 뇌) 버전을 배치하고, `cand_03.png`·`cand_04.png`에 기존 중형 프레임 후보를 함께 두어 직접 비교·선택할 수 있게 구성했습니다.

| 슬롯 ID | 후보 수 | 1순위 추천 (`cand_01.png`) 핵심 수치 및 선정 사유 | 언제 쓰는지 (1줄 규칙) |
|---|---:|---|---|
| `A01_mode1_translucent_head_lateral` | 3 | 가로 `91.7%`, 투명 유리 두상 내부 뇌·혈관 투시 선명, `S=28.4`, `spk=0` | 일상 서사에서 뇌 메커니즘으로 진입할 때(Mode 1 투시 입구 컷) 사용 |
| `A02_mode2_whole_brain_lateral` | 4 | 가로 `93.6%`, 혈관 밀도 `31.4%`, 석고 밝기 `V=191.5`, `S=33.8`, `spk=0` | 전체 대뇌 외측면 조망 및 피질 혈관 흐름 기본 뇌 앵커로 사용 |
| `A03_mode2_whole_brain_dorsal_topdown` | 4 | 가로 `92.4%`, 혈관 밀도 `39.0%`, 밝기 통일 `V=208.8`, `S=36.8`, `spk=0` | 좌우 반구 대칭·비대칭 비교 및 상면 전반 조망 시 사용 |
| `A04_mode2_whole_brain_anterior_frontal` | 4 | 가로 `94.8%`, 혈관 밀도 `29.5%`, 밝기 `V=206.8`, `S=41.8`, `spk=0` | 양측 전두엽·측두엽 정면 구도 및 관상단면 진입 기준 뇌로 사용 |
| `A05_sulcal_vessel_macro` | 2 | 가로 `100%`, 혈관 밀도 `32.3%`, 중앙 Y자 고랑 혈관 연속성 최우수 (`spk=0`) | 뇌혈관 박동·CSF 유입·고랑 미세혈관 클로즈업 질감 앵커로 사용 |
| `A06_hippocampus_cutaway` | 4 | 가로 `94.3%`, 혈관 밀도 `26.4%`, 측두엽 절개창 해마 노출·무반사 (`V=196.0`) | 기억·공간 탐색 등 해마(Hippocampus) 관련 모든 컷의 필수 시점 앵커 |
| `A07_thalamus_brainstem_midsagittal` | 4 | 가로 `95.2%`, 혈관 밀도 `27.0%`, 뇌량·시상·뇌간·뇌실 정중시상 단면 (`V=207.8`) | 시상 중계·뇌간 각성·CSF 뇌실 순환 설명 컷의 필수 시점 앵커 |
| `A08_insula_operculum_retracted` | 4 | 가로 `94.9%`, 혈관 밀도 `29.5%`, 실비우스 덮개 견인 섬엽 노출 (`V=205.5`) | 내수용감각·통증·감정 통합 등 섬엽(Insula) 컷의 필수 시점 앵커 |
| `A09_prefrontal_cortex_3q_anterolateral` | 4 | 가로 `90.4%`, 혈관 밀도 `24.4%`, 전전두엽 무광 앰버 구획 (`V=201.4`) | 의사결정·충동 억제·작업기억 등 전전두엽 활성 장면의 기본 앵커 |
| `A10_signal_segment_sample` | 4 | 가로 `95.7%`, 혈관 밀도 `31.4%`, 튜브 내부 불투명 고체 신호 세그먼트 (`spk=0`) | 에피소드 중립 신경 신호 전달 표현(무발광 고체 세그먼트) 기준 앵커 |
| `A11_region_shutdown_sample` | 4 | 가로 `95.2%`, 혈관 밀도 `29.7%`, 슬레이트 암전 구역 내부 혈관까지 완전 소등 | 수면 박탈·스트레스·억제에 의한 특정 뇌 부위 기능 저하 표현 기준 앵커 |
| `A12_dual_brain_top_bottom_compare` | 4 | 가로 `88.9%`, 혈관 밀도 `29.5%`, 분할선 없는 상·하 2뇌 1:1 구조 대조 (`V=214.1`) | 실험군 vs 대조군(A vs B) 뇌 부피·활성 면적 비교 컷의 기준 앵커 |

---

## 3. Category B ~ E (`@Research` 전수 선별 확정 슬롯 요약)

- **Category B (`B01~B15`, 캐릭터 15슬롯)**:
  - `B01~B04` 기본 체형 3면 시트(성인 남·여·노인·어린이): 전원 `4.2등신` 무광 크림 비닐 + 2D 먹선 눈 + `#EAE6DF` 배경 통일(`B02` 6.5등신 마네킹 드리프트 후보 전면 삭제 완료).
  - `B05~B10` 6종 표정(놀람·기쁨·걱정·집중·혼란·깨달음): 동일한 2D 먹선 눈·눈썹 문법으로 0.2초 직관 판독 가능.
  - `B11~B15` 5종 의상(흰 가운·수술복·평상복·정장·학생): 단일 전신 `3/4` 스탠딩 포맷으로 체형·조명 100% 호환.
- **Category C (`C01~C03`, `R80` `#FF2525` 화살표 3슬롯)**: `90°` 탑다운 일직선(`C01`), 적응형 지그재그(`C02`), 문턱 단절 sever gap(`C03`) 물리적 3D 화살표 정본.
- **Category D (`D01~D02`, `120ft` 드론 2슬롯)**: 인위적 블러·안개 후보를 제외하고 보행자가 미세 점 크기로 보이는 진짜 고고도 대학 캠퍼스(`D01`)·대학병원(`D02`) 상공 조망 확정.
- **Category E (`E01~E10`, 반복 장소 10슬롯)**: 연구실·MRI실·집 문턱·강의실·주방 5개 공간의 **무인 풀프레임 실내 기본판(`E01~E05`)**과 **1:1 동일 건축 구조에 인물을 배치한 스케일 기준판(`E06~E10`)** 쌍 완비.
