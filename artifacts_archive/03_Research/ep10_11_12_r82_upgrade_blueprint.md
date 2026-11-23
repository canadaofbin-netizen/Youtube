# `Ep #10 · #11 · #12` `Rule R82` 심층 문제점 진단 및 리메이크 설계서

- **기준 표준**: [v8_ep09_maguire_london_taxi_hippocampus_r82](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/BCI_Shorts_Channel/projects/v8_ep09_maguire_london_taxi_hippocampus_r82/02_script/visual_plan.json) (`23`컷, `84.67s`, 뇌 비중 `47.5%`) & [neuro_diorama_rules.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/neuro_diorama_rules.md) (`Rule R80 / R81 / R82`)
- **진단 대상 3편**:
  1. `Ep #10`: [v8_ep10_sleep_pill_brain_wash](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/BCI_Shorts_Channel/projects/v8_ep10_sleep_pill_brain_wash/03_visuals/visual_plan.json) (`18`컷 `80.67s` → **`24`컷 `80.67s`**, 뇌 비중 `43.9%` → **`49.8%`**)
  2. `Ep #11`: [v8_ep11_open_label_placebo_pain](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/BCI_Shorts_Channel/projects/v8_ep11_open_label_placebo_pain/03_visuals/visual_plan.json) (`18`컷 `79.97s` → **`24`컷 `79.97s`**, 뇌 비중 `42.6%` → **`50.1%`**)
  3. `Ep #12`: [v8_ep12_doorway_effect_memory](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/BCI_Shorts_Channel/projects/v8_ep12_doorway_effect_memory/03_visuals/visual_plan.json) (`18`컷 `77.13s` → **`23`컷 `77.13s`**, 뇌 비중 `42.9%` → **`49.7%`**)

> [!CAUTION]
> **조립 전 반드시 지켜야 할 수학적 제약 (`t0 < 15.0s` × `R82` 교차 함정 발견)**:
> `Ep #10 (S04 t0=14.00s)`, `Ep #11 (S04 t0=14.17s)`, `Ep #12 (S04 t0=14.37s)` 모두 **`S04` 시작 시각이 `15.0s` 미만**입니다. [diorama_assembler.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/diorama_assembler.py#L1640-L1645)는 `t0 < 15.0s` 컷에 `R82_FIRST_15S_MAX_CUT_SEC = 3.80s` 상한을 걸고, [video_autopsy.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/video_autopsy.py#L1932)는 `brain_simulator_3d`에 `R82_BRAIN_MIN_CUT_SEC = 4.20s` 하한을 강제합니다. 따라서 **`S04`를 단독 뇌 컷으로 바꾸면 `4.20s <= dur <= 3.80s` 모순이 발생**합니다! `Ep #9 R82`처럼 **`S04`는 반드시 `2.47~2.57s` 2비트 휴먼 릴레이(`human_action_relay=True`)로 쪼개고**, `15.0s` 이후의 늘어진 `4.8~6.0s` 휴먼 필러(`Ep #10 S13`, `Ep #11 S08`, `Ep #12 S08`)를 3D 뇌 컷으로 전환해야 첫 어셈블리에서 `100% PASS`합니다.

---

## 1. 3개 에피소드 공통 핵심 병목 5가지 (전수 색출)

| 결함 유형 | 적발 컷 및 현상 (`Pre-R82` 18컷 본) | `Rule R82` 교정 해법 |
|---|---|---|
| **① 캠퍼스 항공 드론샷 오염·지연 (`R82-3`)** | `Ep #10 C02 (5.10s, 1.0x)` & `Ep #11 C02 (4.43s, 1.0x)`: 카메라는 `drone_aerial_approach`인데 프롬프트 본문이 **지상 인형 2~3명 산책 워킹샷**으로 오염됨. `Ep #12 C02 (5.60s, 1.0x)`: 노틀담 단일 컷이 `5.60s`(`>3.80s`) 지연 + `0–15s` 내 총 `3`컷뿐(`R82_FIRST_15S_MIN_CUTS=4` 미달). | 3편 모두 `S02`를 **`C03` 진짜 30m 상공 대학 캠퍼스 항공 드론(`2.20~2.75s`, `category="institution"`) + `C04` 창문 컷어웨이 연구실 진입(`2.23~2.85s`, `architectural_cutaway_portal`, `r72_cold_open_relay=True`)** 2컷으로 분리. |
| **② 복붙 클리셰 & 주어 중복 버그 (`first ... first ...`)** | `Ep #11 C04 (5.03s)` & `Ep #12 C04 (5.07s)`: `Ep #9 C07`과 똑같은 **"네이비 블레이저 여의사가 무거운 가죽 책을 탁 덮는 샷"** 복붙. 게다가 프롬프트에 `"The 2.5D ... woman ... first the 2.5D ... woman"` 주어 중복 문장 버그 발생. | 복붙 가죽 책 클리셰 전면 폐기 → 각 실험 고유 소품 2비트(`Ep #10`: 트레이서 라이트박스 스캔, `Ep #11`: `ZERO DRUG` 스탬프·빈 캡슐 확인, `Ep #12`: `5.0s` 황동 초시계 클릭 + 신발상자 운반)로 교체. |
| **③ `4.3~6.0s` 저속 인형 소품극 지연 (`R82-1` 위반)** | `Ep #10`: `C01(3.77s > 3.20s)`, `C03(5.13s)`, `C04(5.00s)`, `C08(5.20s)`, `C15(4.80s 손가락질)`, `C18(5.63s)`.<br/>`Ep #11`: `C01(4.67s)`, `C03(5.07s)`, `C08(5.97s)`, `C15(5.93s)`, `C18(4.73s)`.<br/>`Ep #12`: `C01(5.10s)`, `C08(5.27s)`, `C15(4.30s)`, `C18(4.37s)`. | ① 데이터·메커니즘 문장(`Ep #10 S13`, `Ep #11 S08`, `Ep #12 S08`)은 **차분한 3D 뇌 컷(`4.80~5.97s`)**으로 승격하고, ② 일상 행동 문장은 **`1.90~3.00s` 2비트 2컷(`human_action_relay=True`)**으로 분할. |
| **④ `A vs B` 양측 뇌 직접 비교 부재 (`R82-4`)** | 3편 모두 `side_by_side_brain_compare=True` 컷이 **`0`개**여서 핵심 대조 구간(`S11`/`S12`)에서 단독 뇌만 보여줌. | `Ep #9 C17` 규격 그대로 좌·우 완전한 양측 뇌 전체가 프레임 여백 안에 들어오는 **`6°` 미세 패럴랙스 `side_by_side_brain_compare=True` 히어로 샷(`4.67~5.70s`)** 1컷씩 신설. |
| **⑤ `R70-M` 데이터 스탬프 `1개` 부족 (`R82-4`)** | 3편 모두 `data_stamps`가 `1`개뿐(`R82` 최소 `2`개 위반) + `Ep #10 S14` 뇌 컷이 `4.07s`(`< 4.20s` 하한 미달). | 도시에 검증 `DOI` 수치 기반 **2번째 `R70-M` 스탬프** 추가(`callout_enabled=False` 지정) 및 `Ep #10 S14` 인접 호흡 `4`프레임 보정(`4.20s`). |

---

## 2. `Ep #10` 리메이크 설계서 (`v8_ep10_sleep_pill_brain_wash_r82` — `24`컷 `80.67s`)

- **정량 검증 결과**: 총 `24`컷 (`avg=3.36s`) | `C01=1.90s (<=3.20s)` | `0–15s` = `7`컷 (`max=2.60s <=3.80s`) | 휴먼 `1.90~2.97s` | 3D 뇌 `4.20~5.87s` (`8`컷, **`49.8%`**) | 야외 비중 `50.0%` | **기존 클립 `14`개 재사용 (`audio_master.wav` 100% 유지) + 신규 `Omni 1.2` `10`클립 (`240` 크레딧)**

### 2.1 `Ep #10` 24컷 전체 리메이크 매핑표
| 신규 컷 | 문장 | 길이 | 문법 (`camera_move`) | 재사용 vs 신규 생성 (`Omni 1.2`) 및 연출 명세 |
|---|---|---|---|---|
| `C01` | `S01A` | `1.90s` | `expressive_vinyl_world` (`orbital_3d_arc_sweep`) | **`[신규 #1]`** (`human_action_relay=True`) 침대 맡 남성이 호박색 수면제 병을 들어 올리고 물컵을 내려놓음 (`C01 <= 3.20s` 충족) |
| `C02` | `S01B` | `1.93s` | `expressive_reaction_closeup` (`gentle_push_in`) | **`[신규 #2]`** 아침 창가에서 무거운 관자놀이를 양손으로 짚으며 반눈(`E02`) 스냅 |
| `C03` | `S02A` | `2.50s` | `expressive_exterior_establishing` (`drone_aerial_approach`) | **`[신규 #3 — R82-3 복원]`** `real_world_target_id="copenhagen_university_courtyard"` **진짜 30m 상공 코펜하겐 대학 붉은 벽돌 중정 항공 드론 하강** (지상 거대 인형 워킹 오염 제거!) |
| `C04` | `S02B` | `2.53s` | `architectural_cutaway_portal` (`fpv_window_portal_breach`) | **`[신규 #4 — R82-3 복원]`** 창문 프레임을 뚫고 수면 뇌영상 연구실 콘솔로 매끄럽게 진입 (`r72_cold_open_relay=True`) |
| `C05` | `S03A` | `2.53s` | `expressive_exterior_establishing` (`pan_right`) | **`[신규 #5]`** `oslo_hospital_glass_entrance` 오슬로 대학병원 유리 아트리움 정문으로 피험자 진입 |
| `C06` | `S03B` | `2.60s` | `expressive_vinyl_world` (`gentle_push_in`) | **`[신규 #6]`** `structural_mri_scanner_bore` 의료진이 버튼을 누르자 피험자 베드가 3T MRI 보어 안으로 슬라이드 |
| `C07` | `S04A` | `2.47s` | `expressive_vinyl_world` (`gentle_push_in`) | **`[신규 #7]`** (`t0=14.00s < 15s` 대응) 오슬로 임상의가 라이트박스 위 붉게 정체된 뇌 스캔 필름을 펜으로 짚음 |
| `C08` | `S04B` | `2.53s` | `expressive_reaction_closeup` (`gentle_push_in`) | **`[재사용 #1]`** 기존 `clip_4.mp4` 피크 `2.53s` 수확 (잠 못 잔 피험자의 경악 리액션) |
| `C09` | `S05` | `5.30s` | `brain_simulator_3d` (`global_system_orbit_drone`) | **`[재사용 #2]`** 기존 `clip_5.mp4` 그대로 유지 |
| `C10` | `S06` | `4.37s` | `brain_simulator_3d` (`sensory_to_brain_drone`) | **`[재사용 #3]`** 기존 `clip_6.mp4` 그대로 유지 |
| `C11` | `S07` | `4.73s` | `brain_simulator_3d` (`circuit_cooperation_drone`) | **`[재사용 #4]`** 기존 `clip_7.mp4` 그대로 유지 (`brainstem` 50초 펌프 펄스) |
| `C12` | `S08A` | `2.57s` | `expressive_hands_closeup` (`gentle_push_in`) | **`[재사용 #5]`** 기존 `clip_8.mp4` 전반부 `2.57s` 수확 (투명 수조에 젖은 스펀지 담그기) |
| `C13` | `S08B` | `2.63s` | `expressive_vinyl_world` (`pan_right`) | **`[신규 #8]`** 두 손으로 스펀지를 꽉 짜자 탁한 염료가 맑은 물 밖으로 확 뿜어져 나옴 |
| `C14–C17` | `S09–S10` | `2.40–2.97s` | `spatial_3d_arrow_diorama` (`4`컷) | **`[재사용 #6~#9]`** 기존 `R80` 3D 화살표 `clip_9.mp4 ~ clip_12.mp4` **100% 그대로 유지** |
| `C18` | `S11` | `5.87s` | `brain_simulator_3d` (`circuit_cooperation_drone`) | **`[재사용 #10]`** 기존 `clip_13.mp4` 그대로 유지 (`thalamus` 서파 동조) |
| `C19` | `S12` | `5.70s` | `brain_simulator_3d` (`circuit_cooperation_drone`) | **`[신규 #9 — R82-4 A vs B 히어로]`** **`side_by_side_brain_compare=True`**: 좌측 `Natural Sleep` 뇌(뇌간·혈관 시안/골드 50초 펌프파 활짝 맥동) vs 우측 `Zolpidem Pill` 뇌(펌프파 50% 반토막 암전·정체) |
| `C20` | `S13` | `4.80s` | `brain_simulator_3d` (`3p_region_shutdown_pullout`) | **`[재사용 #11 — C15 손가락질 제거!]`** 기존 `clip_14.mp4`(단독 셧다운 뇌 클립)를 `S13`에 재배치 + **기존 `Stamp #1` (`100% vs 50%`, `callout_enabled=False`)** |
| `C21` | `S14` | `4.20s` | `brain_simulator_3d` (`1p_nerve_canyon_drone`) | **`[재사용 #12]`** 기존 `clip_16.mp4` 유지 (`S15` 여유 호흡에서 `+4f` 가져와 `4.07s -> 4.20s` `R82` 뇌 하한 통과!) |
| `C22` | `S15` | `5.23s` | `brain_simulator_3d` (`3p_region_shutdown_pullout`) | **`[재사용 #13]`** 기존 `clip_17.mp4` 유지 + **`[신규 Stamp #2]` (`-30%` 뇌척수액 세척 감소: `100% vs 70%`, `callout_enabled=False`)** |
| `C23` | `S16A` | `2.80s` | `expressive_vinyl_world` (`gentle_push_in`) | **`[신규 #10]`** 진료실 책상에서 의사와 상의하며 처방 수면제 병을 안전하게 내려놓음 |
| `C24` | `S16B` | `2.83s` | `expressive_exterior_establishing` (`gentle_push_in`) | **`[재사용 #14]`** 기존 `clip_18.mp4` 피크 `2.83s` 트림 (`copenhagen_park_tree_path` 상쾌한 아침 산책) |

### 2.2 `Ep #10` `A vs B` 양측 뇌 비교(`C19`) & 2번째 데이터 스탬프(`C22`) JSON 명세
```json
{
  "c19_r78m_callout": {
    "left_lbl": "Natural Sleep",
    "right_lbl": "Zolpidem Pill",
    "arrow": "vs",
    "sub": "Full Vessel Pump  vs  50% Muted Pump",
    "left_rgb": [39, 216, 255],
    "right_rgb": [175, 198, 230],
    "left_xy": [210, 1120],
    "right_xy": [810, 1120],
    "lock_seed_xy": true
  },
  "stamp_2_ep10_s15": {
    "sentence_index": 15,
    "mode": "study",
    "preset": "bar_compare",
    "chart": "bar_compare",
    "style": "ink_pen",
    "format": "group_means",
    "title": "Brain Fluid Wash Flow",
    "unit": "%",
    "bars": [
      {"label": "Natural Sleep", "value": 100.0, "unit": "%"},
      {"label": "Zolpidem Pill", "value": 70.0, "unit": "%"}
    ],
    "duration_sec": 3.85,
    "doi": "10.1016/j.cell.2024.11.027",
    "source_citation": "Hauglund et al. (2025)"
  }
}
```

---

## 3. `Ep #11` 리메이크 설계서 (`v8_ep11_open_label_placebo_pain_r82` — `24`컷 `79.97s`)

- **정량 검증 결과**: 총 `24`컷 (`avg=3.33s`) | `C01=2.30s (<=3.20s)` | `0–15s` = `7`컷 (`max=2.57s <=3.80s`) | 휴먼 `2.20~3.00s` | 3D 뇌 `4.40~5.97s` (`8`컷, **`50.1%`**) | 야외 비중 `50.0%` | **기존 클립 `14`개 재사용 + 신규 `Omni 1.2` `10`클립 (`240` 크레딧)**

### 3.1 `Ep #11` 24컷 전체 리메이크 매핑표
| 신규 컷 | 문장 | 길이 | 문법 (`camera_move`) | 재사용 vs 신규 생성 (`Omni 1.2`) 및 연출 명세 |
|---|---|---|---|---|
| `C01` | `S01A` | `2.30s` | `expressive_vinyl_world` (`orbital_3d_arc_sweep`) | **`[재사용 #1]`** 기존 `clip_1.mp4` 전반 `2.30s` 트림 (의사가 호박색 플라시보 병을 책상 너머로 밀어 건넴) |
| `C02` | `S01B` | `2.37s` | `expressive_hands_closeup` (`gentle_push_in`) | **`[신규 #1]`** 환자가 손바닥에 파란·흰 캡슐 2알을 또렷이 털어내며 놀란 눈(`E12`) 스냅 |
| `C03` | `S02A` | `2.20s` | `expressive_exterior_establishing` (`drone_aerial_approach`) | **`[신규 #2 — R82-3 복원]`** `real_world_target_id="harvard_hms_quad"` **진짜 30m 상공 하버드 의대 고든홀 대리석 기둥 & 잔디 쿼드 항공 드론 하강** (인형 산책 오염 제거!) |
| `C04` | `S02B` | `2.23s` | `architectural_cutaway_portal` (`fpv_window_portal_breach`) | **`[신규 #3 — R82-3 복원]`** 대리석 기둥 창문 컷어웨이를 통과해 하버드 `BIDMC` 복통 클리닉 진료실로 진입 (`r72_cold_open_relay=True`) |
| `C05` | `S03A` | `2.50s` | `expressive_vinyl_world` (`gentle_push_in`) | **`[신규 #4]`** 의사가 투명 빈 캡슐 모형을 열어 보이며 약 성분이 0임을 솔직히 설명 |
| `C06` | `S03B` | `2.57s` | `expressive_vinyl_world` (`pan_right`) | **`[재사용 #2]`** 기존 `clip_3.mp4` 피크 `2.57s` 트림 (주방 카운터에서 물컵과 함께 캡슐 복용) |
| `C07` | `S04A` | `2.50s` | `expressive_hands_closeup` (`gentle_push_in`) | **`[신규 #5 — 가죽 책 복붙 폐기!]`** 약사가 처방 차트 위에 붉은 무인장 스탬프를 쾅 찍고 빈 약병을 옆으로 치움 |
| `C08` | `S04B` | `2.53s` | `expressive_reaction_closeup` (`gentle_push_in`) | **`[신규 #6]`** 회의적인 노년의사가 고개를 가로저으며 클립보드를 내려놓음 |
| `C09–C11` | `S05–S07` | `4.53–5.27s` | `brain_simulator_3d` (`3`컷) | **`[재사용 #3~#5]`** 기존 `clip_5.mp4`, `clip_6.mp4`, `clip_7.mp4` (전전두엽 → 뇌간 → 척수 통증 게이트) 100% 유지 |
| `C12` | `S08` | `5.97s` | `brain_simulator_3d` (`global_system_orbit_drone`) | **`[신규 #7 — 5.97s 늘어지는 휴먼 C08 전환!]`** 하행 진통 회로가 척수로 퍼지는 안정적 3D 뇌 궤도 + **기존 `Stamp #1` (`59% vs 35%`, `callout_enabled=False`)** |
| `C13–C16` | `S09–S10` | `2.33–2.77s` | `spatial_3d_arrow_diorama` (`4`컷) | **`[재사용 #6~#9]`** 기존 `R80` 3D 화살표 `clip_9.mp4 ~ clip_12.mp4` **100% 그대로 유지** |
| `C17` | `S11` | `4.40s` | `brain_simulator_3d` (`circuit_cooperation_drone`) | **`[재사용 #10]`** 기존 `clip_13.mp4` 그대로 유지 |
| `C18` | `S12` | `5.23s` | `brain_simulator_3d` (`circuit_cooperation_drone`) | **`[신규 #8 — R82-4 A vs B 히어로]`** **`side_by_side_brain_compare=True`**: 좌측 `Open Placebo` 뇌(뇌간 게이트 시안 점등 & 섬엽 `insula` 통증 알람 진정) vs 우측 `No-Pill Control` 뇌(양측 섬엽 코랄-크림슨 과열 점등) |
| `C19` | `S13A` | `2.93s` | `expressive_exterior_establishing` (`gentle_push_in`) | **`[재사용 #11]`** 기존 `clip_15.mp4` 피크 `2.93s` 트림 (보스턴 벽돌 계단에서 허리 통증 없이 가볍게 무릎 굽혀 물건 들기) |
| `C20` | `S13B` | `3.00s` | `expressive_vinyl_world` (`pan_right`) | **`[신규 #9]`** 허리를 반듯하게 펴며 미소(`E09`) + **`[신규 Stamp #2]` (`Carvalho et al. 2016 Pain`, 만성 요통 감소 `1.5 pts` [`-30%`] vs `0.2 pts`)** |
| `C21–C22` | `S14–S15` | `4.73–5.30s` | `brain_simulator_3d` (`2`컷) | **`[재사용 #12~#13]`** 기존 `clip_16.mp4`, `clip_17.mp4` 그대로 유지 |
| `C23` | `S16A` | `2.36s` | `expressive_exterior_establishing` (`gentle_push_in`) | **`[재사용 #14]`** 기존 `clip_18.mp4` 전반 `2.36s` 트림 (햇살 가득한 포치에서 차분히 물컵 들기) |
| `C24` | `S16B` | `2.37s` | `expressive_reaction_closeup` (`gentle_push_in`) | **`[신규 #10]`** 물컵을 테이블에 깔끔히 내려놓고 어깨를 이완하며 안도 미소(`E09`) |

### 3.2 `Ep #11` `A vs B` 양측 뇌 비교(`C18`) & 2번째 데이터 스탬프(`C20`) JSON 명세
```json
{
  "c18_r78m_callout": {
    "left_lbl": "Open Placebo",
    "right_lbl": "No-Pill Control",
    "arrow": "vs",
    "sub": "Insula Calmed  vs  Insula Pain Flare",
    "left_rgb": [39, 216, 255],
    "right_rgb": [255, 86, 104],
    "left_xy": [210, 1020],
    "right_xy": [810, 1020],
    "lock_seed_xy": true
  },
  "stamp_2_ep11_s13": {
    "sentence_index": 13,
    "mode": "study",
    "preset": "bar_compare",
    "chart": "bar_compare",
    "style": "ink_pen",
    "format": "group_means",
    "title": "Chronic Back Pain Drop",
    "unit": "pts",
    "bars": [
      {"label": "Open Placebo", "value": 1.5, "unit": "pts"},
      {"label": "Usual Care", "value": 0.2, "unit": "pts"}
    ],
    "duration_sec": 3.00,
    "doi": "10.1097/j.pain.0000000000000700",
    "source_citation": "Carvalho et al. (2016)"
  }
}
```

---

## 4. `Ep #12` 리메이크 설계서 (`v8_ep12_doorway_effect_memory_r82` — `23`컷 `77.13s`)

- **정량 검증 결과**: 총 `23`컷 (`avg=3.35s`) | `C01=2.50s (<=3.20s)` | `0–15s` = `6`컷 (`max=3.67s <=3.80s`) | 휴먼 `2.15~3.67s` | 3D 뇌 `4.40~5.27s` (`8`컷, **`49.7%`**) | 야외 비중 `46.7%` | **기존 클립 `14`개 재사용 + 신규 `Omni 1.2` `9`클립 (`216` 크레딧)**

### 4.1 `Ep #12` 23컷 전체 리메이크 매핑표
| 신규 컷 | 문장 | 길이 | 문법 (`camera_move`) | 재사용 vs 신규 생성 (`Omni 1.2`) 및 연출 명세 |
|---|---|---|---|---|
| `C01` | `S01A` | `2.50s` | `expressive_vinyl_world` (`orbital_3d_arc_sweep`) | **`[신규 #1]`** 서재 책상에서 가위가 필요한 곳을 보고 의자를 박차고 일어섬 (`C01 <= 3.20s` 통과) |
| `C02` | `S01B` | `2.60s` | `expressive_vinyl_world` (`gentle_push_in`) | **`[재사용 #1]`** 기존 `clip_1.mp4` 후반 `2.60s` 트림 (주방 문턱을 넘자마자 빈손을 보며 멍해짐) |
| `C03` | `S02A` | `2.75s` | `expressive_exterior_establishing` (`drone_aerial_approach`) | **`[신규 #2 — R82-3 분리·복원]`** `real_world_target_id="notre_dame_golden_dome"` **진짜 30m 상공 노틀담 대학 골든돔 & 캠퍼스 보행로 항공 드론 하강** (`5.60s` 단일 지연 해결!) |
| `C04` | `S02B` | `2.85s` | `architectural_cutaway_portal` (`fpv_window_portal_breach`) | **`[신규 #3 — R82-3 분리·복원]`** 창문 컷어웨이를 돌파해 노틀담 2룸 신발상자 실험실 `Table A -> Table B` 전경으로 진입 (`r72_cold_open_relay=True`) |
| `C05` | `S03` | `3.67s` | `architectural_cutaway_portal` (`fpv_window_portal_breach`) | **`[재사용 #2]`** 기존 `clip_3.mp4` 그대로 유지 (`3.67s <= 3.80s`! 빨간 나무 블록을 흰 신발상자에 넣고 뚜껑 닫기) |
| `C06` | `S04A` | `2.50s` | `expressive_hands_closeup` (`gentle_push_in`) | **`[신규 #4 — 가죽 책 복붙 폐기!]`** 연구원이 황동 스톱워치 버튼을 딸깍 눌러 `5`초 보행을 계측 |
| `C07` | `S04B` | `2.57s` | `expressive_vinyl_world` (`pan_right`) | **`[신규 #5]`** 피험자가 닫힌 흰 신발상자를 두 손에 안고 방 안을 차분히 다섯 걸음 이동 |
| `C08–C10` | `S05–S07` | `4.40–5.27s` | `brain_simulator_3d` (`3`컷) | **`[재사용 #3~#5]`** 기존 `clip_5.mp4`, `clip_6.mp4`, `clip_7.mp4` (두정엽 → 해마 경계세포 → 전전두엽 목표 삭제) 100% 유지 |
| `C11` | `S08` | `5.27s` | `brain_simulator_3d` (`3p_region_shutdown_pullout`) | **`[신규 #6 — 5.27s 늘어지는 휴먼 C08 전환!]`** 전전두엽 작업기억 소거 3D 뇌 풀백 + **기존 `Stamp #1` (`23% vs 28%` 오류율, `callout_enabled=False`)** |
| `C12–C15` | `S09–S10` | `2.50–2.93s` | `spatial_3d_arrow_diorama` (`4`컷) | **`[재사용 #6~#9]`** 기존 `R80` 3D 화살표 `clip_9.mp4 ~ clip_12.mp4` (`doorway_boundary_sever` 포함) **100% 그대로 유지** |
| `C16` | `S11` | `4.67s` | `brain_simulator_3d` (`circuit_cooperation_drone`) | **`[신규 #7 — R82-4 A vs B 히어로]`** **`side_by_side_brain_compare=True`**: 좌측 `Same Room` 뇌(전전두엽 시안-골드 목표 기억 선명 유지) vs 우측 `Doorway Cross` 뇌(해마 코랄 경계세포 펄스 폭발 → 전전두엽 목표 암전 삭제) |
| `C17` | `S12` | `4.47s` | `brain_simulator_3d` (`1p_nerve_canyon_drone`) | **`[재사용 #10]`** 기존 `clip_14.mp4` 그대로 유지 |
| `C18` | `S13A` | `2.15s` | `expressive_exterior_establishing` (`gentle_push_in`) | **`[재사용 #11]`** 기존 `clip_15.mp4` 전반 `2.15s` 트림 (`4.30s > 4.25s` 위반 해소: 현관 포치에서 두 가지 짐 들기) |
| `C19` | `S13B` | `2.15s` | `expressive_vinyl_world` (`gentle_push_in`) | **`[신규 #8]`** 현관 문턱을 넘자마자 한 손을 머리에 얹고 `12°` 갸웃(`E06`) |
| `C20` | `S14` | `4.63s` | `brain_simulator_3d` (`global_system_orbit_drone`) | **`[재사용 #12]`** 기존 `clip_16.mp4` 그대로 유지 |
| `C21` | `S15` | `4.57s` | `brain_simulator_3d` (`3p_region_shutdown_pullout`) | **`[재사용 #13]`** 기존 `clip_17.mp4` 유지 + **`[신규 Stamp #2]` (`Radvansky et al. 2011 Exp 3` 원래 방 복귀 시 2차 리셋: `Stay 11%` vs `1 Door 14%` vs `Return 16%`, `callout_enabled=False`)** |
| `C22` | `S16A` | `2.18s` | `expressive_vinyl_world` (`pan_right`) | **`[재사용 #14]`** 기존 `clip_18.mp4` 전반 `2.18s` 트림 (`4.37s > 4.25s` 위반 해소: 손에 물리적 단서를 쥐고 문 통과) |
| `C23` | `S16B` | `2.19s` | `expressive_reaction_closeup` (`gentle_push_in`) | **`[신규 #9]`** 문 앞에서 핵심 단어 하나를 또렷이 말하며 고개를 끄덕이는 유레카 표정(`E12`) |

### 4.2 `Ep #12` `A vs B` 양측 뇌 비교(`C16`) & 2번째 데이터 스탬프(`C21`) JSON 명세
```json
{
  "c16_r78m_callout": {
    "left_lbl": "Same Room",
    "right_lbl": "Doorway Cross",
    "arrow": "vs",
    "sub": "Goal Kept Bright  vs  Boundary Wipe",
    "left_rgb": [39, 216, 255],
    "right_rgb": [255, 86, 104],
    "left_xy": [210, 980],
    "right_xy": [810, 980],
    "lock_seed_xy": true
  },
  "stamp_2_ep12_s15": {
    "sentence_index": 15,
    "mode": "study",
    "preset": "bar_compare",
    "chart": "bar_compare",
    "style": "ink_pen",
    "format": "group_means",
    "title": "Return-to-Room Error Rate",
    "unit": "%",
    "bars": [
      {"label": "Stay in Room", "value": 11.0, "unit": "%"},
      {"label": "1 Doorway", "value": 14.0, "unit": "%"},
      {"label": "Return Room", "value": 16.0, "unit": "%"}
    ],
    "duration_sec": 3.60,
    "doi": "10.1080/17470218.2011.571267",
    "source_citation": "Radvansky et al. (2011) Exp 3"
  }
}
```
