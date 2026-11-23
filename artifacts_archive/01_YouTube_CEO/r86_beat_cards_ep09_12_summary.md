# [과제 B + DQ8 추가분] 4편(`Ep #9–#12`) 교체 컷 `R85 + R86` Beat Card 설계 요약서 (`56`컷 전수 검증본)

> [!IMPORTANT]
> **머신 리더블 SSOT JSON (`@Operator` `visual_plan.json` 직결 반영본)**:
> - [r86_beat_cards_ep09_12.json](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/research/r86_beat_cards_ep09_12.json)
> - 재구축 기준서: [r85_root_cause_reverification_and_fix_plan.md](./r85_root_cause_reverification_and_fix_plan.md#L154-L155) 기본 `50`컷 + **신규 `DQ8` 라이브 크롭 전수 검수 추가 확정 `6`컷(`Ep09 C04·C08`, `Ep10 C04·C05`, `Ep11 C01·C04`) = 고유 교체 컷 총 `56`컷 (`32` 뇌 컷 + `24` 비-뇌 결함 컷)**
> - 파이프라인 실전 검증 결과 (`pipeline/prompt_quality_v5.py` + `pipeline/flow_prompt_builder.py`): **4편 전수 `R85 = 0건`, `R86 스키마 = 0건`, `R86 전체 에피소드 Anti-Filler·Zero-Delta = 0건` 통과 완료**

---

## 1. 에피소드별 교체 범위 & 라이브 검증(`validate_r85` / `validate_r86`) 요약

| 에피소드 (`project_id`) | 전체 컷 | 교체 컷 합계 | 🧠 `R85` Flow 뇌 컷 (`8`컷/편) | 🎭/🔴 비-뇌 결함 교체 컷 (`24`컷) | 🔒 `Start+End` 양끝 잠금 컷 | `R85` / `R86` 라이브 검증 |
|---|---:|---:|---|---|---|---:|
| `v8_ep09_maguire_london_taxi_hippocampus_r82` | `23` | **`16`컷** | `C09, C10, C11, C12, C17, C18, C20, C21` (`8`) | **`C04`**, `C07`, **`C08`**, `C15, C16, C19, C22, C23` (`8`) | `C04, C07, C08, C16, C17, C22` (`6`) | **`0` / `0` / `0` PASS** |
| `v8_ep10_sleep_pill_brain_wash` | `24` | **`14`컷** | `C09, C10, C11, C18, C19, C20*, C21, C22` (`8`) | **`C04, C05`**, `C06, C08, C16, C23` (`6`) | `C04, C05, C06, C08, C19, C23` (`6`) | **`0` / `0` / `0` PASS** |
| `v8_ep11_open_label_placebo_pain` | `24` | **`13`컷** | `C09, C10, C11, C12, C17, C18, C21, C22` (`8`) | **`C01, C04`**, `C14, C19, C24` (`5`) | `C01, C04, C14, C22, C24` (`5`) | **`0` / `0` / `0` PASS** |
| `v8_ep12_doorway_effect_memory` | `23` | **`13`컷** | `C08, C09, C10, C11, C16, C17, C20, C21*` (`8`) | `C03, C05, C12, C19, C23` (`5`) | `C05, C10, C16, C19, C23` (`5`) | **`0` / `0` / `0` PASS** |
| **합계** | **`94`** | **`56`컷** | **`32`컷 (`100%` `31_O2CmlKOk` 6-Scale Flow)** | **`24`컷** | **`22`컷 (`Omni 1.1 Flash` 양끝 프레임 잠금)** | **`0`건 오류** |

### 1.1 신규 `DQ8` 라이브 크롭(`58`장) 전수 육안 판정으로 추가된 `6`개 결함 컷 요약
1. **`Ep09 C04` (`S02B`, `8.0–11.3s`, `[MOD]` → `REJECT_REPLACE`)**: 크림색 조형 앞머리·단발 윤곽 및 3D 홍채·립스틱 입술 유출 (`architectural_cutaway_portal` 창문 진입 드리프트 제거 → 실내 MRI 콘솔 `expressive_vinyl_world` + `Start+End` 잠금).
2. **`Ep09 C08` (`S04B`, `18.8–21.5s`, `[HIGH]` → `REJECT_REPLACE`)**: 주름·실제 피부 질감이 선명한 성인 남녀 2명 실사 측면 얼굴 유출 (`t=21.16s`).
3. **`Ep10 C04` (`S02B`, `6.2–8.9s`, `[MOD]` → `REJECT_REPLACE`, 전수 검수 추가 포착)**: 남성 연구원 검은 포마드 모발·3D 피부(`t=8.31s b0`) 및 여성 연구원 3D 실사형 홍채·입술·피부 음영(`t=8.56s b1`) 동시 유출.
4. **`Ep10 C05` (`S03A`, `8.9–11.3s`, `[HIGH]` → `REJECT_REPLACE`)**: 갈색 조형 머리카락 및 3D 눈·코 유출 (`t=10.45–10.70s`).
5. **`Ep11 C01` (`S01A`, `0.0–2.1s`, `[MOD]` → `REJECT_REPLACE`, 네이티브 PNG 확대 확정)**: 오프닝 `0.83s` 훅 구간에서 의사·환자 2명 모두 하관·턱 전체에 거친 황갈색 수염 자국/피부색 패치(`#A8835B`)가 번진 1등급(`0%` 수염·실사 피부) 결함 — Gate 2 재렌더 왕복 방지를 위해 즉시 교체 포함.
6. **`Ep11 C04` (`S02B`, `6.8–9.1s`, `[HIGH]` → `REJECT_REPLACE`)**: 짙은 갈색 단발 머리카락 유출 (`t=8.38–9.02s`).
- 나머지 모든 `MODERATE` 컷(`Ep09 C01·C02·C05·C06`, `Ep10 C01·C02·C07·C12·C24`, `Ep11 C05·C06·C08·C20·C23`, `Ep12 C01·C02·C04·C06·C07·C18·C22`)은 전수 확대 육안 확인 결과 **모발 `0%`·실사 피부 `0%` 정상 대머리 비닐(모자 소품 또는 2등급 허용 미세 비닐 코·귀 윤곽)**로 판정되어 유지 확정했습니다.

> [!NOTE]
> **`visual_proof_type` 분포 (`50`컷 중 `decorative = 0`컷)**:
> - `mechanism`: `13`컷 (`26%`) | `comparison`: `11`컷 (`22%`) | `causal_arrow`: `10`컷 (`20%`) | `data`: `8`컷 (`16%`) | `misconception_flip`: `5`컷 (`10%`) | `scale`: `3`컷 (`6%`) | `decorative`: **`0`컷 (`0%`)**
> - 모든 연속 동일 `visual_proof_type` 구간 `<= 2`컷(`R86_MAX_CONSECUTIVE_SAME_PROOF = 2`), `visual_register="story"` 인간 서사 컷(`10`컷)에는 오버레이·스탬프 `0%`, 모든 뇌·화살표·데이터 컷(`40`컷)은 `visual_register="diagram"`으로 엄격 분리했습니다.

---

## 2. 원문 대조 완료된 대사 보정(`Ep #10`) & 4편 `R70-M` 실측 데이터 스탬프 (`0` Concept 배지)

### 2.1 `Ep #10` 대사 보정 2문장 (`@YouTube_CEO` 확정안 반영)
- **`S04` (`C07–C08`, Eide et al., 2021 *Brain* `PMID 33829232` 원문 *"from most brain regions"* 정합)**:
  - `"Missing one night of sleep stalled waste cleanup across most of the eighty-five brain zones."`
- **`S12` (`C19`, Hauglund et al., 2025 *Cell* `PMC12340670` 생쥐 실험 명시 재합성)**:
  - `"Instead, zolpidem knocked lab mice out fast, yet cut those slow pump waves in half."`

### 2.2 4편 `8`개 `R70-M` 데이터 스탬프 전수 `mode="study"` + 검증 DOI 확정

| 에피소드 | 부착 컷 (`S#`) | 스탬프 제목 (`title`) | 실측 수치 (`bars` / `value`) | DOI (`source_citation`) |
|---|---|---|---|---|
| `Ep #09` | `C19` (`S13`) | `Trainees Who Grew Map` | `39 / 79` (`dot_array_highlight`) | `10.1016/j.cub.2011.11.018` (`Woollett & Maguire (2011)`) |
| `Ep #09` | `C23` (`S17`) | `New Shape Recall Score` | `Bus Drivers 21.3 pts` vs `Taxi Drivers 17.3 pts` | `10.1002/hipo.20233` (`Maguire, Woollett & Spiers (2006)`) |
| `Ep #10` | `C20` (`S13`) | `Slow NE Pump Waves (Mice)` | `Natural Sleep 100%` vs `Zolpidem 50%` | `10.1016/j.cell.2024.11.027` (`Hauglund et al. (2025, Cell - Mice)`) |
| `Ep #10` | `C22` (`S15`) | `Brain Fluid Wash Drop (Mice)` | `30%` (`arc_gauge`, `>=30% drop`) | `10.1016/j.cell.2024.11.027` (`Hauglund et al. (2025, Cell - Mice)`) |
| `Ep #11` | `C12` (`S08`) | `Honest Placebo Symptom Relief` | `Honest Placebo 59%` vs `No-Pill Control 35%` | `10.1371/journal.pone.0015591` (`Kaptchuk et al. (2010)`) |
| `Ep #11` | `C19` (`S13`) | `Usual & Max Back Pain Drop` | `30%` (`arc_gauge`, usual & max pain drop) | `10.1097/j.pain.0000000000000700` (`Carvalho et al. (2016)`) |
| `Ep #12` | `C11` (`S08`) | `Object Memory Error Rate` | `Same Room 23%` vs `Through Doorway 28%` | `10.1080/17470218.2011.571267` (`Radvansky et al. (2011)`) |
| `Ep #12` | `C21` (`S15`) | `Exp. 3 Memory Error Rate` | `Stay Room 11%` / `1 Doorway 14%` / `Return Room 16%` | `10.1080/17470218.2011.571267` (`Radvansky et al. (2011)`) |

---

## 3. 에피소드별 색상 범례(`Intra-Episode Color Semantics`) & 해부 시점 잠금

- **공통 뇌 베이스 (`31_O2CmlKOk` 시그니처 고정)**:
  - 대뇌 피질(회백질·이랑): 쿨 매트 화이트·실버그레이 `#9CA5AC`~`#C3C9CE` (배경 `#05080F` 어두운 슬레이트 보이드)
  - 고랑(Sulci) 미세혈관 & 뇌척수액(CSF): 일렉트릭 시안 `#27D8FF` (`RGB 39,216,255`)
- **편내 고정 기능 하이라이트 색상 (`organ_color_ledger` 플립 `0`건 검증 완료)**:
  - **`Ep #09` (해마 가소성)**: 활성 신호·후방 해마 팽창 = `amber_gold` (`234,179,75`) | 대조군 기준선·전방 해마 수축 = `muted_slate_indigo` (`91,103,120`)
  - **`Ep #10` (수면 세척 vs 졸피뎀)**: 자연 노르에피네프린 서파·혈관 펌프 = `amber_gold` (`234,179,75`) | 정상 CSF 세척 = `electric_cyan` (`39,216,255`) | 불면 정체·졸피뎀 반감 억제 = `muted_slate_indigo` (`91,103,120`)
  - **`Ep #11` (오픈라벨 플라시보)**: 전전두엽 하행 진통 게이트 = `amber_gold` (`234,179,75`) | 상행 통증·섬엽 불쾌 파동 = `crimson_red` (`232,84,96`) | 플라시보 진정 후 냉각 상태 = `cooled_slate_blue` (`91,103,120`)
  - **`Ep #12` (문지방 효과)**: 해마 경계세포 리셋 파동 = `amber_gold` (`234,179,75`) | 유지된 전전두엽 작업기억 = `electric_cyan` (`39,216,255`) | 문 통과 후 소거된 작업기억 = `dark_slate_void` (`91,103,120`)

---

## 4. 4편 `50`개 교체 Beat Card 전수 명세표

### `v8_ep09_maguire_london_taxi_hippocampus_r82` (총 23컷 중 14컷 교체)
| C# | S# (`EDL`) | 구분 | Proof (`Register`) | `viewer_must_understand` | `concrete_referent` / `R85 Scale` + `Viewpoint` + `Wikimedia 도판` | `state_delta` |
|---|---|---|---|---|---|---|
| `C07` | `S04` (`16.5-18.8s`) | 🎭 Human/Drone 🔒S+E | `misconception_flip` (`story`) | 고전 의학 통념은 성인 뇌 크기가 자물쇠처럼 영구 고정되어 절대 변하지 않는다고 믿었음 | solid plaster brain cast sealed inside a locked clear acrylic display case on an oak study table | sealed static plaster brain cast locked under glass |
| `C09` | `S05` (`21.5-25.7s`) | 🧠 Brain | `causal_arrow` (`diagram`) | 거리 풍경 자극이 눈에서 시신경을 타고 머리 뒤쪽 시각피질로 직행함 | `xray_head_dive` · `eyes` -> `primary visual cortex` (`oblique_inferior_lateral_cutaway`) · `File:Hippocampus image.png` | optic nerve arrival at rear occipital pole |
| `C10` | `S06` (`25.7-31.2s`) | 🧠 Brain | `mechanism` (`diagram`) | 뒤쪽 시각피질 신호가 측두엽 심부 바닥의 해마로 흘러 들어가 입체 거리 지도로 엮임 | `split_cutaway` · `primary visual cortex` -> `hippocampus` (`inferior_lateral_cutaway`) · `File:Hippocampus image.png` | ventral relay from occipital visual cortex into deep temporal hippocampus |
| `C11` | `S07` (`31.2-36.1s`) | 🧠 Brain | `scale` (`diagram`) | 택시 기사들의 해마 뒤쪽(후방 해마) 회백질 부피가 눈에 띄게 두툼하게 팽창함 | `sulcal_cyan_dive` · `hippocampus` -> `posterior hippocampus` (`oblique_inferior_lateral_cutaway`) · `File:202102 Frontal plane of the brain hippocampus.svg` | selective volumetric expansion of posterior hippocampal tail |
| `C12` | `S08` (`36.1-41.6s`) | 🧠 Brain | `comparison` (`diagram`) | 운전 경력이 길어질수록 후방 해마 신경다발 밀도와 부피가 비례해서 더 크게 자람 | `1p_tract_canyon` · `posterior hippocampus` -> `parahippocampal gyrus` (`coronal_cutaway`) · `File:Human brain frontal (coronal) section.JPG` | progressive fiber-tract thickening scaling with years driven |
| `C15` | `S10` (`46.5-48.9s`) | 🔴 Arrow | `comparison` (`diagram`) | 같은 런던 교통소음 속에서도 '정해진 노선만 도는 빨간 2층 버스' 대조군을 설정함 | unmarked bright red double-decker London bus gliding along a clean sunlit Portland-stone avenue at 120ft altitude (`File:Kingston-upon-Thames - London Buses (geograph 7672593).jpg`) | aerial establish of fixed-route red bus corridor with zero pedestrians |
| `C16` | `S10` (`48.9-51.9s`) | 🔴 Arrow 🔒S+E | `causal_arrow` (`diagram`) | 버스는 갈림길 판단 없이 일직선 고정 경로만 반복 주행함(앞선 택시 지그재그 화살표와 정면 대조) | single unbroken ruler-straight #FF2525 3D extruded arrow block between clean smooth cream architectural blocks | 90-degree top-down straight red arrow corridor contrasting C14 zigzag |
| `C17` | `S11` (`51.9-56.7s`) | 🧠 Brain 🔒S+E | `comparison` (`diagram`) | 전체 뇌 윤곽이 보이는 상/하 비교에서 상단 택시기사 후방 해마는 크게 팽창한 반면 하단 버스기사는 평평함 | `3p_shutdown_or_top_bottom` · `hippocampus` -> `posterior hippocampus` (`inferior_lateral_cutaway`) · `File:Hippocampus image.png` | top enlarged posterior hippocampus vs bottom flat baseline inside complete brains |
| `C18` | `S12` (`56.7-61.5s`) | 🧠 Brain | `causal_arrow` (`diagram`) | 실시간 우회로 선택을 할 때만 두정엽 공간감각 허브와 심부 해마 사이의 신경회로가 강하게 연결됨 | `vessel_csf_macro` · `parietal cortex` -> `hippocampus` (`oblique_inferior_lateral_cutaway`) · `File:Hippocampus image.png` | active tract synchronization from parietal space hub to hippocampus |
| `C19` | `S13` (`61.5-65.7s`) | 🎭 Human/Drone + 📊Stamp | `data` (`diagram`) | 처음엔 똑같았던 79명 중 4년 뒤 시험에 합격한 39명에게서만 후방 해마 성장이 나타남(선천성 가설 기각) | gleaming green London taxi badge resting in the lower third of a clean oak desk leaving open upper slate for the 39/79 dot array | clean lower-third badge placement with unobstructed upper chart zone |
| `C20` | `S14` (`65.7-70.1s`) | 🧠 Brain | `misconception_flip` (`diagram`) | 한정된 두개골 공간 안에서 뒤쪽 지도 영역이 커지자 해마 앞쪽과의 구조적 균형이 흔들리기 시작함 | `split_cutaway` · `hippocampus` -> `anterior hippocampus` (`coronal_cutaway`) · `File:202102 Frontal plane of the brain hippocampus.svg` | coronal bilateral view framing bounded hippocampal real estate |
| `C21` | `S15` (`70.1-76.2s`) | 🧠 Brain | `mechanism` (`diagram`) | 해마 뒤쪽(거리 지도)이 부풀어 오르는 동안 앞쪽 끝(전방 해마)은 반대로 수축하고 어두워짐 | `sulcal_cyan_dive` · `posterior hippocampus` -> `anterior hippocampus` (`inferior_lateral_cutaway`) · `File:Hippocampus image.png` | simultaneous posterior expansion and anterior shrinkage along one hippocampus |
| `C22` | `S16` (`76.2-80.4s`) | 🎭 Human/Drone 🔒S+E | `mechanism` (`story`) | 줄어든 앞쪽 해마는 처음 보는 낯선 기하 도형을 즉석에서 외우는 역할을 담당함 | four-fingered matte cream-white vinyl hands flipping over a crisp black-ink geometric figure card on an oak desk | stimulus card flip hiding complex geometric figure before recall |
| `C23` | `S17` (`80.4-84.7s`) | 🎭 Human/Drone + 📊Stamp | `data` (`diagram`) | 새 도형 기억 점수에서 버스기사(21.3점)가 택시기사(17.3점)를 이겨 뇌 가소성의 등가교환을 수치로 증명함 | two sketch pads in the lower third showing a complete geometric drawing vs an incomplete drawing beneath the 21.3 vs 17.3 chart | completed vs incomplete figure drawings below clean upper bar-chart zone |

### `v8_ep10_sleep_pill_brain_wash` (총 24컷 중 12컷 교체)
| C# | S# (`EDL`) | 구분 | Proof (`Register`) | `viewer_must_understand` | `concrete_referent` / `R85 Scale` + `Viewpoint` + `Wikimedia 도판` | `state_delta` |
|---|---|---|---|---|---|---|
| `C06` | `S03` (`11.3-14.0s`) | 🎭 Human/Drone 🔒S+E | `mechanism` (`story`) | 오슬로 연구진이 성인 24명에게 조영제를 투여해 이틀간 실제 인간 뇌 노폐물 세척 과정을 MRI로 추적함 | bald cream-white 2.5D clinician pressing the white 3T MRI gantry button as the volunteer slides into the illuminated bore (`File:3TMRI.jpg`) | volunteer sliding smoothly into empty clinical 3T MRI bore |
| `C08` | `S04` (`16.4-19.0s`) | 🎭 Human/Drone 🔒S+E | `comparison` (`story`) | 하룻밤 잠을 못 잔 그룹은 정상 수면 그룹과 달리 뇌 85개 구역 대부분에 노폐물 조영제가 씻기지 않고 고여 있음 | two illuminated brain-scan film sheets side by side on a clinical lightbox—left scan clear vs right scan filled with unwashed amber dye pockets | side-by-side clear rested scan vs amber-stalled sleep-deprived scan |
| `C09` | `S05` (`19.0-24.3s`) | 🧠 Brain | `misconception_flip` (`diagram`) | 기존 의학 상식은 낮 동안의 각성 신호가 밤새 완전히 꺼져 침묵한다고 착각했음 | `xray_head_dive` · `brainstem` -> `thalamus` (`midsagittal_cutaway`) · `File:Brainstem.png` | dormant dark brainstem baseline predicted by old textbook dogma |
| `C10` | `S06` (`24.3-28.7s`) | 🧠 Brain | `causal_arrow` (`diagram`) | 펌프 동력이 없으면 뇌척수액이 뇌 조직 사이로 밀려 들어가지 못하고 정체됨 | `split_cutaway` · `thalamus` -> `cerebral ventricles` (`midsagittal_cutaway`) · `File:Human ventricular system -- left side view.png` | stagnant cyan ventricular CSF poised at ventricular gateway |
| `C11` | `S07` (`28.7-33.4s`) | 🧠 Brain | `mechanism` (`diagram`) | 척수 꼭대기 뇌간(청반핵)이 50초마다 느린 노르에피네프린 파동을 규칙적으로 쏘아 올림 | `sulcal_cyan_dive` · `brainstem` -> `cerebral cortex` (`midsagittal_cutaway`) · `File:Brainstem.png` | rhythmic 50-second amber-gold pulse firing upward from brainstem |
| `C16` | `S10` (`43.7-46.3s`) | 🔴 Arrow | `comparison` (`diagram`) | 옥스퍼드·코펜하겐 연구진이 자연 깊은 수면과 수면제 졸피뎀 투여 조건을 나란히 대조 실험함 | crisp motion-blur-free 120ft aerial arc above the sunlit golden-stone Oxford Radcliffe Camera rotunda (`File:Radcliffe Camera, Oxford.jpg`) | crisp high-altitude Oxford rotunda aerial establish without radial blur |
| `C18` | `S11` (`49.2-55.1s`) | 🧠 Brain | `mechanism` (`diagram`) | 자연 수면에서는 뇌 정중앙 시상(Thalamus)의 서파가 대뇌 혈관의 힘찬 수축·이완 펌프질과 정확히 맞물림 | `vessel_csf_macro` · `thalamus` -> `cerebral ventricles` (`midsagittal_cutaway`) · `File:Thalamus.png` | full-amplitude synchronized thalamic wave + vigorous arterial vasomotion |
| `C19` | `S12` (`55.1-60.8s`) | 🧠 Brain 🔒S+E | `comparison` (`diagram`) | 생쥐 실험에서 졸피뎀은 잠은 빨리 들게 했지만 혈관을 짜주는 느린 펌프 파동 진폭을 반토막 냄 | `3p_shutdown_or_top_bottom` · `brainstem` -> `thalamus` (`midsagittal_cutaway`) · `File:Thalamus.png` | side-by-side full natural oscillation wave vs flattened 50% zolpidem wave |
| `C20` | `S13` (`60.8-65.6s`) | 🧠 Brain + 📊Stamp | `data` (`diagram`) | 자연 수면 100% 대비 졸피뎀 투여 시 느린 노르에피네프린 펌프 파동이 정확히 50%로 반감됨(실측 Study 차트) | `1p_tract_canyon` · `locus coeruleus` -> `cerebral cortex` (`midsagittal_cutaway`) · `File:Brainstem.png` | quantitative 100% to 50% oscillation drop with clean upper chart backdrop |
| `C21` | `S14` (`65.6-69.8s`) | 🧠 Brain | `causal_arrow` (`diagram`) | 혈관 펌프질이 멈추자 뇌 고랑 사이를 씻어내던 시안색 뇌척수액 흐름이 눈에 띄게 느려지고 막힘 | `vessel_csf_macro` · `csf` -> `third ventricle` (`midsagittal_cutaway`) · `File:Human ventricular system -- left side view.png` | blunted arterial wall motion causing sluggish perivascular CSF flow |
| `C22` | `S15` (`69.8-75.0s`) | 🧠 Brain + 📊Stamp | `data` (`diagram`) | 뇌척수액 세척 유입량이 30% 이상 감소해 '약으로 기절한 잠 ≠ 뇌를 씻는 진짜 숙면'임이 입증됨 | `sulcal_cyan_dive` · `csf` -> `brainstem` (`midsagittal_cutaway`) · `File:Human ventricular system -- left side view.png` | 30%+ global CSF tracer influx drop under Study arc-gauge stamp |
| `C23` | `S16` (`75.0-77.7s`) | 🎭 Human/Drone 🔒S+E | `mechanism` (`story`) | 처방 수면제는 절대 혼자 갑자기 끊지 말고 의사와 상의해 안전하게 수면 습관을 조절해야 함 | unmarked amber glass bottle placed onto an oak consultation desk as patient and physician review a sleep schedule card | calm physician-guided consultation over unmarked amber vial |

### `v8_ep11_open_label_placebo_pain` (총 24컷 중 11컷 교체)
| C# | S# (`EDL`) | 구분 | Proof (`Register`) | `viewer_must_understand` | `concrete_referent` / `R85 Scale` + `Viewpoint` + `Wikimedia 도판` | `state_delta` |
|---|---|---|---|---|---|---|
| `C09` | `S05` (`19.2-23.7s`) | 🧠 Brain | `mechanism` (`diagram`) | 가짜 약인 줄 알아도 규칙적인 복용 의식이 이마 바로 뒤 전전두엽(현실 평가 허브)을 깨움 | `xray_head_dive` · `prefrontal cortex` -> `ventromedial prefrontal cortex` (`anterior_three_quarter_lateral`) · `File:Prefrontal cortex (left) - lateral view.png` | rostral prefrontal cortex ignition behind translucent forehead |
| `C10` | `S06` (`23.7-29.0s`) | 🧠 Brain | `causal_arrow` (`diagram`) | 전전두엽에서 출발한 통증 차단 명령이 뇌간을 거쳐 척수 아래로 힘차게 내려감 | `split_cutaway` · `brainstem` -> `spinal cord` (`midsagittal_cutaway`) · `File:Brainstem.png` | top-down amber-gold signal cascade down brainstem to spine |
| `C11` | `S07` (`29.0-33.6s`) | 🧠 Brain | `mechanism` (`diagram`) | 하행 차단 게이트가 아래에서 올라오던 붉은 통증 신호를 척수 입구에서 가로막아 잠재움 | `vessel_csf_macro` · `brainstem` -> `anterior cingulate cortex` (`midsagittal_cutaway`) · `File:Brainstem.png` | ascending crimson pain signal blocked and dimmed at spinal-brainstem gate |
| `C12` | `S08` (`33.6-39.6s`) | 🧠 Brain + 📊Stamp | `data` (`diagram`) | 3주 뒤 정직한 가짜 약 복용군의 59%가 증상 완화를 얻어 무복용 대조군(35%)을 크게 앞섬 | `sulcal_cyan_dive` · `prefrontal cortex` -> `dorsolateral prefrontal cortex` (`anterior_three_quarter_lateral`) · `File:Prefrontal cortex (left) - anterior view.png` | 59% vs 35% empirical relief stamp over clean dark upper slate |
| `C14` | `S09` (`41.9-44.5s`) | 🔴 Arrow 🔒S+E | `comparison` (`diagram`) | 친절한 진료만 받고 약 복용 습관이 없었던 대조군은 중간에 경로가 끊겨 지속적 완화에 도달하지 못함(C16 직선 완주와 대조) | thick #FF2525 3D extruded arrow block cleanly severed in half by a wide empty stone gap that stays open from frame 1 to final frame | permanently severed 3D red arrow with wide open central gap locked Start+End |
| `C17` | `S11` (`49.6-54.0s`) | 🧠 Brain | `misconception_flip` (`diagram`) | '환자들이 의사에게 예의상 덜 아프다고 답한 것뿐 아닌가?'라는 핵심 회의론 제기(객관적 뇌파 검증 진입) | `1p_tract_canyon` · `insula` -> `insula` (`lateral_opercular_retracted`) · `File:Brain lobes - insular lobe.png` | crimson distress ripples tested inside lateral Sylvian fissure before spray |
| `C18` | `S12` (`54.0-59.3s`) | 🧠 Brain | `mechanism` (`diagram`) | 외측 덮개(operculum)를 젖혀 노출한 섬엽(Insula)의 붉은 통증·불쾌 파동이 가짜 스프레이 직후 즉시 차분히 가라앉음 | `split_cutaway` · `insula` -> `insula` (`lateral_opercular_retracted`) · `File:Brain lobes - insular lobe.png` | lateral exposed insula cooling rapidly from crimson flare to calm slate-blue |
| `C19` | `S13` (`59.3-62.0s`) | 🎭 Human/Drone + 📊Stamp | `data` (`diagram`) | 만성 요통 성인 97명 임상시험에서도 정직한 가짜 알약 추가만으로 평소·최대 허리 통증이 정확히 30% 감소함 | unmarked amber glass pill bottle and water tumbler on a low oak table in the bottom third beneath the exact 30% Study gauge (`File:Antique Amber Medicine Bottle (42378014251).jpg`) | exact 30% Usual & Max Back Pain Drop Study gauge with zero face ghosting |
| `C21` | `S14` (`65.2-69.9s`) | 🧠 Brain | `scale` (`diagram`) | '그렇다면 정직한 가짜 약이 암이나 골절 같은 모든 육체적 질병까지 다 고칠 수 있을까?'라는 한계선을 명확히 질문함 | `sulcal_cyan_dive` · `prefrontal cortex` -> `anterior cingulate cortex` (`anterior_three_quarter_lateral`) · `File:Prefrontal cortex (left) - lateral view.png` | wide whole-brain pullback framing neural-modulation boundary |
| `C22` | `S15` (`69.9-75.2s`) | 🧠 Brain 🔒S+E | `comparison` (`diagram`) | 가짜 약은 종양 같은 물리적 병변은 못 줄이고 오직 뇌의 통증 경보 볼륨(전대상피질)만 낮춰줌 | `3p_shutdown_or_top_bottom` · `anterior cingulate cortex` -> `prefrontal cortex` (`anterior_three_quarter_lateral`) · `File:Prefrontal cortex (left) - lateral view.png` | selective dimming of central pain-alarm hub from crimson to dark slate |
| `C24` | `S16` (`77.5-80.0s`) | 🎭 Human/Drone 🔒S+E | `causal_arrow` (`story`) | 약이 비어 있음을 알아도 차분하고 규칙적인 돌봄 습관이 실제 통증을 가라앉힘 | bald cream-white 2.5D woman setting down a clear water glass on a sunlit wooden counter and straightening her relaxed shoulders | setting water glass down and standing tall with relaxed pain-free posture |

### `v8_ep12_doorway_effect_memory` (총 23컷 중 13컷 교체)
| C# | S# (`EDL`) | 구분 | Proof (`Register`) | `viewer_must_understand` | `concrete_referent` / `R85 Scale` + `Viewpoint` + `Wikimedia 도판` | `state_delta` |
|---|---|---|---|---|---|---|
| `C03` | `S02` (`5.1-7.8s`) | 🎭 Human/Drone | `scale` (`story`) | 노틀담 대학교 연구진이 실제 물리적 방에서 문지방 망각 실험을 수행함(진짜 120ft 상공 캠퍼스 드론 진입) | true 120ft aerial approach descending toward the sunlit Notre Dame Golden Dome and yellow-brick Main Building (`File:Golden Dome frontal.jpg`) | true high-altitude 120ft campus drone descent with tiny dot-scale paths below |
| `C05` | `S03` (`10.7-14.4s`) | 🎭 Human/Drone 🔒S+E | `mechanism` (`story`) | 빨간 원목 블록을 흰 상자 안에 넣고 뚜껑을 덮어 눈으로 볼 수 없게 차단함(오직 작업기억으로만 기억해야 하는 실험 조건) | four-fingered cream-white vinyl hands placing a plain unlettered crimson wooden block inside a white cardboard shoebox and pressing the lid shut (`File:Two sets of wooden unit blocks.jpeg`) | open shoebox holding red block -> lid pressed completely shut hiding the block |
| `C08` | `S05` (`19.4-23.8s`) | 🧠 Brain | `causal_arrow` (`diagram`) | 문틀을 통과해 벽면 풍경이 바뀌는 순간 눈에서 공간 지도 회로로 경보 신호가 전달됨 | `xray_head_dive` · `eyes` -> `parahippocampal gyrus` (`oblique_inferior_lateral_cutaway`) · `File:Hippocampus image.png` | visual wall-shift wave entering eyes and waking posterior spatial map |
| `C09` | `S06` (`23.8-29.1s`) | 🧠 Brain | `mechanism` (`diagram`) | 문턱을 넘는 순간 측두엽 심부 해마의 경계세포(boundary cells)가 번쩍 발화해 이전 방 정보를 챕터 저장함 | `split_cutaway` · `hippocampus` -> `hippocampus` (`inferior_lateral_cutaway`) · `File:Hippocampus image.png` | sharp amber-gold boundary-cell burst inside ventral medial-temporal hippocampus |
| `C10` | `S07` (`29.1-34.2s`) | 🧠 Brain 🔒S+E | `causal_arrow` (`diagram`) | 방 전환 신호가 이마 뒤 전전두엽에 도달하자 방금 들고 가던 목표 불빛이 스르륵 꺼지며 리셋됨 | `3p_shutdown_or_top_bottom` · `prefrontal cortex` -> `dorsolateral prefrontal cortex` (`anterior_three_quarter_lateral`) · `File:Prefrontal cortex (left) - lateral view.png` | prefrontal working-memory glow extinguished into dark slate upon boundary wave arrival |
| `C11` | `S08` (`34.2-39.4s`) | 🧠 Brain + 📊Stamp | `data` (`diagram`) | 같은 거리를 걸어도 문틀을 통과했을 때 상자 속 물건 기억 오류율이 23%에서 28%로 유의미하게 치솟음 | `sulcal_cyan_dive` · `prefrontal cortex` -> `prefrontal cortex` (`three_quarter_anterolateral`) · `File:Prefrontal cortex (left) - anterior view.png` | empirical 23% Same-Room vs 28% Through-Doorway error rate stamp |
| `C12` | `S09` (`39.4-41.9s`) | 🔴 Arrow | `comparison` (`diagram`) | '문틀 때문이 아니라 그냥 걸어간 시간·발걸음 때문 아닐까?'라는 대안 가설을 검증하기 위해 동일 보행 거리를 설정함 | ghost-free crisp 120ft aerial arc rising cleanly above the sunlit Notre Dame yellow-brick quad and Golden Dome (`File:Golden Dome frontal.jpg`) | artifact-free sunlit collegiate quad aerial establish with zero ghost dissolve |
| `C16` | `S11` (`50.1-54.8s`) | 🧠 Brain 🔒S+E | `comparison` (`diagram`) | 전체 뇌가 보이는 상/하 비교에서 상단(한 방 이동)은 전전두엽 기억 불빛이 선명히 유지되지만 하단(문 통과)은 꺼짐 | `3p_shutdown_or_top_bottom` · `prefrontal cortex` -> `dorsolateral prefrontal cortex` (`anterior_three_quarter_lateral`) · `File:Prefrontal cortex (left) - lateral view.png` | top bright retained prefrontal goal vs bottom wiped dark prefrontal cortex |
| `C17` | `S12` (`54.8-59.3s`) | 🧠 Brain | `mechanism` (`diagram`) | 해마 경계세포가 문틀 하나하나를 영화 장면 전환(컷)처럼 처리해 이전 방의 작업기억 실을 깔끔히 끊어냄 | `1p_tract_canyon` · `hippocampus` -> `parahippocampal gyrus` (`coronal_cutaway`) · `File:202102 Frontal plane of the brain hippocampus.svg` | amber-gold hippocampal boundary wave severing active cyan working-memory stream |
| `C19` | `S13` (`61.3-63.6s`) | 🎭 Human/Drone 🔒S+E | `comparison` (`story`) | 두 손(작업기억 슬롯)에 물건을 가득 쥐고 문턱을 넘으면 과부하 때문에 목표 단서 하나가 손에서 미끄러져 떨어짐 | bald cream-white 2.5D homeowner carrying both a white box and brass keys through an intact sunlit home doorway as one crimson wooden block slips and tumbles onto the clean oak floor (`File:1110SewardEvanstonIL.jpg`) | both hands overloaded with two items -> crimson cue block slips and drops right on the doorway threshold |
| `C20` | `S14` (`63.6-68.2s`) | 🧠 Brain | `misconception_flip` (`diagram`) | '그럼 원래 있던 첫 번째 방으로 다시 걸어 돌아가면 잃어버린 기억이 되살아나지 않을까?'라는 직관적 기대를 시험함 | `vessel_csf_macro` · `parahippocampal gyrus` -> `hippocampus` (`coronal_cutaway`) · `File:Human brain frontal (coronal) section.JPG` | attempted return-loop trace approaching hippocampal boundary gate |
| `C21` | `S15` (`68.2-72.8s`) | 🧠 Brain + 📊Stamp | `data` (`diagram`) | 원래 방으로 돌아가려고 문을 한 번 더 넘으면 복구가 아니라 '두 번째 리셋'이 터져 오류율이 11%→14%→16%로 오히려 올라감 | `split_cutaway` · `hippocampus` -> `anterior hippocampus` (`oblique_inferior_lateral_cutaway`) · `File:Hippocampus image.png` | second hippocampal reset burst paired with Study 11%->14%->16% bar chart |
| `C23` | `S16` (`74.9-77.1s`) | 🎭 Human/Drone 🔒S+E | `causal_arrow` (`story`) | 문턱을 넘기 직전 손에 단서 물건(가위 등)을 눈높이로 한 번 확인하고 걸어가면 문지방 리셋을 이겨냄 | bald cream-white 2.5D homeowner raising silver kitchen scissors to eye level right in front of an open sunlit kitchen doorway and striding confidently across the threshold | raising physical cue at doorway threshold -> crossing doorway with goal intact |

---

## 5. `@Operator` `visual_plan.json` 병합 체크리스트 (비교체 유지 컷 `R85` 메타데이터 7줄 정리)

> [!TIP]
> 교체 대상이 아닌 기존 유지 컷(영상 파일은 그대로 재사용) 중 아래 **7개 클립의 `visual_plan.json` 텍스트/플래그 1줄**만 함께 정리하면 전체 에피소드 `prompt-gate`까지 `0`건으로 즉시 통과합니다(`untouched_non_replacement_r85_lint_notes_for_operator`에 전문 수록):
> 1. **`Ep09 C03` (`drone_aerial_approach`)**: `"human_action_relay": false` 설정 + `scene` 문자열의 `"walk"` 토큰을 `"dot-scale campus courtyard paths"`로 정리.
> 2. **`Ep10 C03` & `Ep11 C03` (`drone_aerial_approach`)**: `"human_action_relay": false` 설정.
> 3. **`Ep10 C14` (`drone_landmark_ascend`)**: `scene`의 `"beside"` 토큰 제거.
> 4. **`Ep10 C24`, `Ep11 C23`, `Ep12 C18`**: 지상 클로즈업 컷인데 기존 `grammar`가 `"expressive_exterior_establishing"`으로 잘못 표기되어 드론 린트에 걸림 -> `"grammar": "expressive_vinyl_world"`로 정규화.
> 5. 병합 시 구형 `R84` 잔재 키(`"stacked_cutaway_brain_compare"`, `"surgical_cutaway"`, `"r78m_flow_prompt"`, `"prompt"`)는 `pop()` 제거 후 `main.py prompt-gate` 실행.
