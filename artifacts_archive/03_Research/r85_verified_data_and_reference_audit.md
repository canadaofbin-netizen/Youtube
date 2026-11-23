# R85 원문 수치 재검증 · 신경해부 표준 도판(`R85-R`) · 4편 레퍼런스 전수 점검 보고서

> [!IMPORTANT]
> **핵심 발견 (기존 차트 `"Concept"` 배지 및 `99.2% / 49.5%` 변조의 진짜 원인 추가 규명)**
> `Ep #10` (`100% vs 50%`, `Hauglund et al. 2025, Cell, Fig. 6D`)과 `Ep #12` (`11% / 14% / 16%`, `Radvansky et al. 2011, QJEP, Exp. 3 Table 3`) 모두 **실제 원문 논문의 실측 수치**임에도 `02_script/visual_plan.json`에서 `"mode": "illustrative"`(DOI 누락)로 잘못 태깅되어 있었습니다. 이 때문에 `R70-M` 차트 렌더러가 출처 대신 `"Concept"` 배지를 찍고 인위적 지터(`99.2% / 49.5%`)를 입혔습니다. 두 스탬프 모두 `"mode": "study"` + 원문 `DOI`로 전환하면 **오디오 재녹음 없이 100% 원문 일치**로 즉시 해결됩니다.

- **Machine-Readable SSOT (`@Operator` 직접 연동용)**: [r85_verified_data_and_reference_audit.json](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/research/r85_verified_data_and_reference_audit.json)

---

## 1. 원문 논문 수치 정밀 재검증 (`Ep #9 ~ Ep #12` 전수)

| 에피소드 | 지표 / 내레이션 문구 | 원문 논문 (`DOI` / `PMCID`) | 원문 정확한 위치 & 실측값 | 반올림·표기 판정 (`R70-M` 차트 지침) |
|---|---|---|---|---|
| **Ep #10** | `"100% → 50%"` 노르에피네프린 펌프 파동 감소 | **Hauglund et al., 2025, *Cell*** (`10.1016/j.cell.2024.11.027`, `PMC12340670`) | **Results** (*"Zolpidem decreased baseline NE by approximately 50% for several hours (`Figure 6D`)"*) 및 **Fig. 6C insert** (`NREM NE amplitude`, `n=4`, `P=0.0006`, `effect size=0.99`) | **`mode="study"` 필수 전환 (`100% vs 50%`)**. 저자 본문 문구 자체가 `"approximately 50%"`이므로 `50%` 표기는 과학적으로 정확함 (`99.2%/49.5%` 지터 즉시 제거, 타이틀에 `(~%)` 병기 가능). |
| **Ep #10** | `"30%"` 뇌척수액(`CSF`) 세척 유입 감소 | **Hauglund et al., 2025, *Cell*** (`10.1016/j.cell.2024.11.027`, `PMC12340670`) | **Results & Figure 6G–J** (`3 kDa tracer` 30분 순환 뇌 절편 형광 강도 비교, `n=6–7`) + 저자 공식 요약문 (*"more than 30%"* / `~31–32%` 감소) | **`mode="study"` 유지 (`30%`)**. `>30%`의 보수적 정수 표기로 정확함 (차트 부제/단위에 `>30%` 또는 `~30%` 표기 권장). |
| **Ep #10** | 내레이션 `S02–S03`: 성인 `24명`, `85개` 뇌 영역 | **Eide et al., 2021, *Brain*** (`10.1093/brain/awaa443`, `PMID 33829232`) | **Abstract & Methods**: 총 `24명` (`자유 수면 대조군 n=17` vs `하룻밤 완전 단면군 n=7`), FreeSurfer `85개` 뇌 영역 48시간 추적 | **정확 일치 (`PASS`)**. |
| **Ep #12** | `"23% → 28%"` 실제 방 문 통과 시 상자 기억 오류율 | **Radvansky, Krawietz & Tamplin, 2011, *QJEP*** (`10.1080/17470218.2011.571267`, `PMID 21563019`) | **Experiment 2 (실제 물리적 방, `N=60`), Results & Table 2** (`Positive Probe Error Rate`: `No-Shift = .23` vs `Doorway Shift = .28`) | **정확 일치 (`PASS`, `mode="study"`, `23% vs 28%`)**. 원문 표 자체가 소수 둘째 자리(`.23`, `.28`)로 보고됨. |
| **Ep #12** | `"11% / 14% / 16%"` 원래 방 복귀 실험(`Exp. 3`) 오류율 | **Radvansky, Krawietz & Tamplin, 2011, *QJEP*** (`10.1080/17470218.2011.571267`) | **Experiment 3, Results & Table 3** (`Positive Probe Error Rate`: `No-Shift = .11`, `Single Shift = .14`, `Return Room = .16`, `Double Shift = .20`) | **`mode="study"` 필수 전환 (`11% / 14% / 16%`)**. 가상의 예시가 아니라 **Table 3 실측치**이므로 `DOI`와 `Radvansky et al. (2011)` 출처를 찍어야 `"Concept"` 배지가 사라짐. |
| **Ep #11** | `"59% vs 35%"` 오픈라벨 플라시보 증상 완화율 (`N=80`) | **Kaptchuk et al., 2010, *PLoS ONE*** (`10.1371/journal.pone.0015591`, `PMC3008733`) | **Results — Table 2 (`Endpoint 3 Weeks — Adequate Relief IBS-AR`)**: `Open Placebo 22/37 (59%)` vs `No Treatment 15/43 (35%)`, `p = .03` | **정확 일치 (`PASS`, `59% vs 35%`)**. 원문 Table 2 인쇄 정수 그대로임 (`59.46% -> 59%`, `34.88% -> 35%`). |
| **Ep #11** | `"97명 만성 요통, 통증 30% 감소"` (`28% / 29% / 30%` 관계 규명) | **Carvalho et al., 2016, *PAIN*** (`10.1097/j.pain.0000000000000700`, `PMC5113234`) | **Results 3 & 3.1 + Table 2 + Discussion**: 무작위 배정 **`N=97`** (적격 분석 `N=83`). ① **평소 통증(`usual pain`) 및 최대 통증(`maximum pain`) 각각 정확히 `30%` 감소** (본문 직설: *"a clinically significant 30% reduction in both usual and maximum pain"*), ② 최소 통증 `16%` 감소 → 3개 합산 복합 NRS 감소폭 **`1.5점 vs 0.2점`(`~28%`)**, ③ 요통 기능장애(`RMDQ`) **`2.9점`(`29%`) 감소**, ④ **Discussion 요약**: *"approximately 30% of baseline pain and disability ratings"*. | **오디오(`"thirty percent"`) 무수정 유지 가능 (`PASS`)**. 차트 타이틀을 **`"Usual & Max Back Pain Drop"` (`30%`, `mode="study"`)**로 명시하면 원문 `Results 3.1`의 `30%`와 내레이션이 1:1로 정확히 일치함 (`29%`는 장애점수 `RMDQ`였음). |
| **Ep #9** | `"79명 중 합격한 39명만 해마 성장"` & `"21.3 vs 17.3점"` | **Woollett & Maguire, 2011, *Curr. Biol.*** (`PMC3268356`) & **Maguire et al., 2006, *Hippocampus*** (`10.1002/hipo.20233`) | `2011` **Results p. 2110 & Table 1**: 초기 훈련생 `79명` 중 T2 MRI 완료 합격군 **`39명`** (불합격 복귀 `20명`, 대조군 `31명`; 미복귀자 중 추가 합격 2명 포함 시 전체 합격률 `41/79 = 51.9%`). `2006` **Results**: 복합 도형 지연 회상 버스 기사 **`21.3점`**(`n=17`) vs 택시 기사 **`17.3점`**(`n=18`), `p=0.02`. | **정확 일치 (`PASS`, `39 / 79 trainees` & `21.3 vs 17.3 pts`)**. |

---

## 2. `R85-R` 부위별 표준 신경해부 도판 선정 (`NEUROANATOMY_CUTAWAY_MAP`, 전수 시각 검수 완료)

모든 도판은 Wikimedia Commons API에서 해상도·라이선스를 조회한 뒤 실제로 이미지를 내려받아 **내부 텍스트 유무와 해부학적 단면 각도를 육안 검수**했습니다 (`BodyParts3D / Anatomography` `CC BY-SA 2.1 JP` 및 `DBCLS TogoTV` `CC BY 4.0` 무라벨 도판 최우선 채택).

### ① 해마 (`Hippocampus`) — 하외측 측두엽 컷어웨이 / 관상단면 (등쪽 뇌량 `Corpus Callosum` 오인 원천 차단)
1. **`File:Hippocampus image.png`** (`CC BY-SA 2.1 jp`, `800×455`, **무텍스트 0글자**) — 반투명 3D 뇌 내부에서 측두엽 하내측 바닥에 말려 있는 붉은 **해마(`Hippocampus`)**의 외측·전방 입체 위치를 등쪽 정중선 훨씬 아래로 명확히 분리해 보여주는 1순위 기준판.
2. **`File:202102 Frontal plane of the brain hippocampus.svg`** (`CC BY 4.0`, DBCLS TogoTV 벡터, **무텍스트 0글자**) — 관상단면(`coronal`)에서 위쪽 중앙의 뇌량(`Corpus Callosum`)과 아래쪽 양측 측두엽 내측의 해마 소용돌이를 한눈에 구분해 주는 깔끔한 무라벨 단면도.
3. **`File:Human brain frontal (coronal) section.JPG`** (`CC BY 2.5`, `702×487`, **무텍스트 0글자**) — 번호·글자가 전혀 없는 실제 인간 뇌 관상단면 실사(회백질/백질 경계 및 측두각 해마 구조 확인용).

### ② 시상 · 뇌간 · 뇌척수액 (`Thalamus · Brainstem · Ventricular CSF`) — 정중시상 / 내측 투시뷰
1. **`File:Thalamus.png`** (`CC BY-SA 2.1 jp`, `600×600`, **무텍스트 0글자**) — 반투명 대뇌 정중앙 심부에 자리 잡은 달걀형 **시상(`Thalamus`)**과 그 아래 뇌간 축을 정확히 보여주는 3D 기준판.
2. **`File:Brainstem.png`** (`CC BY-SA 2.1 jp`, `800×455`, **무텍스트 0글자**) — 중뇌·교뇌(`Locus Coeruleus` 위치)·연수로 이어지는 **뇌간(`Brainstem`)** 기둥 전체를 외측·전방에서 무라벨로 시각화한 도판.
3. **`File:Human ventricular system -- left side view.png`** (`CC BY-SA 2.1 jp`, **`1200×1200`**, **무텍스트 0글자**) — 측뇌실 → 제3뇌실(시상 주변) → 대뇌수도관 → 제4뇌실로 흐르는 **`CSF` 뇌실 펌프 경로**를 고해상도 측면 투시로 보여주는 도판.

### ③ 섬엽 (`Insula`) — 외측면에서 덮개(`Operculum`)를 젖혀 노출한 뷰 (**정중시상단면 절대 금지**)
1. **`File:Brain lobes - insular lobe.png`** (`CC BY 2.5`, `642×482`, **글자·숫자 0개**) — 좌반구 외측 실비우스열(`lateral sulcus`)의 덮개를 창문처럼 열어젖히고 그 안쪽에 숨은 **섬엽(`Insula`)만 선명한 적색**으로 강조한 도판.
2. **`File:Human brain view on transverse temporal and insular gyri.JPG`** (`CC BY 2.5`, `470×326`, **무텍스트·무번호 원본**) — 전두·두정 덮개를 제거해 짧은 섬엽회와 긴 섬엽회(`short/long gyri of insula`)가 그대로 드러난 실제 외측 해부 사진.
3. **`File:Gray731.png`** (`Public domain`, `600×342`, Gray's Anatomy Fig. 731) — 덮개를 절제해 부채꼴 섬엽 이랑(`gyri breves / gyrus longus`)을 노출한 고전 신경해부학 표준 도판(외부 지시선 텍스트 없음).

### ④ 전전두엽 (`Prefrontal Cortex`) — 전외측(`3/4 Anterolateral`) 입체 기준판
1. **`File:Prefrontal cortex (left) - lateral view.png`** (`CC BY-SA 2.1 jp`, **`1600×1600`**, **무텍스트 0글자**) — 반투명 두개골 이마 바로 뒤쪽의 전전두엽 외측 경계를 정확히 칠한 초고해상도 도판.
2. **`File:Prefrontal cortex (left) - anterior view.png`** (`CC BY-SA 2.1 jp`, **`1600×1600`**, **무텍스트 0글자**) — 동일 모델의 정면 뷰로, 1번 외측 뷰와 함께 참조(`3/4 anterolateral camera`)하면 전두극·배외측 전전두엽(`DLPFC`) 범위를 오차 없이 고정함.
3. **`File:Cerebrum - frontal lobe - anterior view.png`** (`CC BY-SA 2.1 jp`, `900×900`, **무텍스트 0글자**) — 두개골 없이 양측 전두엽 이랑(`gyri`) 결만 고해상도로 분리한 `Mode 2` 클로즈업용 기준판.

---

## 3. 4편(`Ep #9 ~ Ep #12`) `real_world_refs_manifest.json` 전수 육안 검수 결과

4개 에피소드 매니페스트의 전체 `28개` 슬롯(`21개` 고유 Wikimedia 파일)을 모두 다운로드하여 육안 대조한 결과, 기존에 알려진 3건 외에도 **숨어 있던 심각한 오염원 5건(총 8건 `HARD REJECT` + 3건 `UPGRADE 권장`)**을 추가로 적발했습니다.

> [!CAUTION]
> **이번 전수 육안 검수로 새로 적발된 치명적 오염 레퍼런스 5건**
> 1. **`Ep #10 oslo_hospital_glass_entrance`**: 현대 유리 병원 대신 **1900년대 초반 흑백 엽서(`9282 Oslo. Rikshospitalet` 인쇄 글자 포함)**가 들어가 있었음!
> 2. **`Ep #10 structural_mri_scanner_bore` (`Siemens Magnetom Aera`)**: 실제 **검은 머리 의료진과 환자가 MRI 베드에 누워 있는 사진**(`faces_masked: 0` — 옆모습이라 얼굴 마스킹 통과)이 들어가 인간 피부·머리카락 누출을 유발함!
> 3. **`Ep #11 harvard_hms_quad` (`Anno Domini Harvard Medical School`)**: 캠퍼스 잔디 광장 대신 **`"HARVARD MEDICAL SCHOOL"` 석조 글자만 대문짝만하게 찍은 클로즈업**이 들어가 있었음!
> 4. **`Ep #11 bidmc_clinical_suite`**: 병원 입구에 빨간 **`"EMERGENCY"` 대형 배너 + `"ONE WAY"` 표지판**이 노출됨!
> 5. **`Ep #12 two_room_shoebox_testing_rig` (`A pile of alphabet wooden blocks.jpg`)**: 무지 나무 블록 대신 **알파벳 글자(`A, U, E, M, O...`)가 빼곡히 적힌 장난감 블록**이 들어가 있었음!

### 교체 확정 매핑표 (`HARD REJECT` 8건 + `UPGRADE` 3건 전수 검증 완료)

| 에피소드 · `target_id` | 기존 `commons_title` | 판정 & 결함 사유 | 검증 완료 클린 교체본 (`commons_title` / 라이선스 / 해상도) |
|---|---|---|---|
| **Ep #9** `structural_mri_scanner_bore` | `File:20151214 Waarschuwingstekst MRI-scanner UMCG Groningen NL.jpg` | 🔴 **HARD REJECT** — MRI 기계가 전혀 없는 네덜란드어 경고 표지판(`WAARSCHUWING`) 클로즈업 | **`File:3TMRI.jpg`** (`CC BY-SA 3.0`, `4000×3000`, 무인·무표지판 클린 3T MRI실; 예비: `File:Modern 3T MRI.JPG`) |
| **Ep #9_r82** `london_red_bus_stop_roundel` | `File:D3 bus at Leamouth Orchard Place.jpg` | 🔴 **HARD REJECT** — 어두운 콘크리트 고가도로 밑 + `D3 Bethnal Green` 전광판·속도 표지판 | **`File:Kingston-upon-Thames - London Buses (geograph 7672593).jpg`** (`CC BY-SA 2.0`, `5152×3864`, 맑은 영국 석조 거리 2층 빨간 버스) |
| **Ep #9** `ucl_wilkins_portico` | `File:The Wilkins Building, UCL, in the Snow 371199372.jpg` | 🟡 **UPGRADE 권장** — 눈 덮인 겨울 풍경(`sunlit gravel Main Quad` 프롬프트와 계절 충돌) | **`File:London - Gower Street - University College London 1827 William Wilkins.jpg`** (`CC BY-SA 4.0`, `3915×2592`, 맑은 UCL 정면 포르티코, 무인) |
| **Ep #9** `mit_great_dome` | `File:2017 Maclaurin Buildings (MIT Building 10) and Great Dome.jpg` | 🟡 **UPGRADE 권장** — 전경에 실제 행인 7~8명 노출 | **`File:MIT Killian Court.jpg`** (`CC BY-SA 3.0`, `3879×2581`, 100% 무인 맑은 잔디 광장 & Great Dome) |
| **Ep #10** `oslo_hospital_glass_entrance` | `File:9282 Oslo. Rikshospitalet - no-nb digifoto 20151204 00004 bldsa PK09682.jpg` | 🔴 **HARD REJECT** — 1900년대 흑백 고서 엽서 + 하단 인쇄 텍스트(`Oslo. Rikshospitalet`, `9282`) | **`File:Oslo University Hospital, Rikshospitalet - Oslo, Norway 2020-09-25.jpg`** (`CC BY-SA 4.0`, `4560×2565`, 현대 오슬로 대학병원 전경, 무인·무텍스트) |
| **Ep #10** `structural_mri_scanner_bore` | `File:Siemens Magnetom Aera MRI scanner.jpg` | 🔴 **HARD REJECT** — 실제 검은 머리 의료진과 환자가 찍혀 있어 인간 살색·머리카락 변질 유발 | **`File:3TMRI.jpg`** (`CC BY-SA 3.0`, `4000×3000`, 100% 무인 클린 3T MRI실) |
| **Ep #10** `copenhagen_park_tree_path` | `File:Autumn in Copenhagen's King's Garden...jpg` | 🟡 **UPGRADE 권장** — 산책로 정중앙에 실제 행인 2명 뒷모습 노출 | **`File:Kongens Have - avenue.jpg`** (`CC BY 2.0`, `3402×2736`, 100% 무인 맑은 코펜하겐 린덴 가로수길) |
| **Ep #11** `harvard_hms_quad` | `File:Anno Domini Harvard Medical School MDCCCCIIII.jpg` | 🔴 **HARD REJECT** — 캠퍼스 잔디가 전혀 없는 `"HARVARD MEDICAL SCHOOL"` 석조 글자 클로즈업 | **`File:Gordon Hall Harvard Medical School Quadrangle.jpg`** (`CC BY-SA 4.0`, `4000×3000`, 백색 대리석 Gordon Hall + 푸른 잔디 광장 정면, 무인) |
| **Ep #11** `bidmc_clinical_suite` | `File:Beth Israel Deaconess Medical Center (BIDMC) (54953356537).jpg` | 🔴 **HARD REJECT** — 빨간 `"EMERGENCY"` 대형 현수막 텍스트 및 도로 표지판 | **`File:Beth Israel Deaconess Medical Center East Campus.jpg`** (`CC BY 3.0`, `3008×2000`, 깔끔한 석조·유리 병원 외관, 응급실 배너 없음) |
| **Ep #11** `clinical_pharmacy_apparatus` | `File:Nateglinide 60 mg bottle, Zydus, front view.jpg` | 🔴 **HARD REJECT** — 당뇨약 브랜드(`Nateglinide 60 mg / Zydus / NDC`) 전문의약품 라벨 전면 노출 | **`File:Antique Amber Medicine Bottle (42378014251).jpg`** (`CC BY 2.0`, `3398×5097`, 흰 배경 위 **100% 무라벨·무텍스트 갈색 유리 약병**) |
| **Ep #12** `midwestern_brick_front_porch` | `File:FEMA - 33940 - "Old Brick House" Biloxi, Miss..jpg` | 🔴 **HARD REJECT** — FEMA 허리케인 카트리나 재난 폐허 주택(`C19` 폐허 컷의 직접 원인) | **`File:1110SewardEvanstonIL.jpg`** (`CC BY-SA 3.0`, `3376×1914`, 멀쩡하고 맑은 미국 중서부 붉은 벽돌 단독주택·정원; 예비: `File:1304 Hillcrest (8413546053).jpg`) |
| **Ep #12** `two_room_shoebox_testing_rig` | `File:A pile of alphabet wooden blocks.jpg` | 🔴 **HARD REJECT** — 모든 면에 알파벳 대문자가 칠해진 블록(`R56` 텍스트 오염원) | **`File:Two sets of wooden unit blocks.jpeg`** (`CC BY-SA 3.0`, **`2448×3264`**, 나무 상자 안에 담긴 **100% 무글자 원목 기하 블록**, 무인) |

*(나머지 10개 고유 파일 — `An MRI scanner.JPG`, `Embankment Pier and London Eye.jpg`, `Black cab... Trafalgar Square`, `Bispegården - Copenhagen University.jpg`, `Radcliffe Camera, Oxford.jpg`, `Sever Hall, Harvard University`, `20180527 - 02 - Boston, MA (Back Bay).jpg`, `Harvard University Memorial Hall side.jpg`, `Golden Dome frontal.jpg` — 은 재난·경고문·약품라벨·인물 클로즈업이 없는 깨끗한 상태로 **`PASS`** 확정.)*
