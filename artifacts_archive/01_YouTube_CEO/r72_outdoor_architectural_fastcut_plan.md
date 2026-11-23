# `Rule R72 + R72-R` — 드론/FPV 연속 비행 카메라 · 실물 건축/현장 레퍼런스 고증 · 오픈월드 고속 전환 업그레이드 계획

## Goal Description

기존 `v8` 에피소드(`Ep #4 ~ #6`, 총 `61클립`) 진단 결과와, 앞서 역설계 완료한 **`신비한 건축사전`(`_73R9pQF5oM`)** 및 **`@RicksClips3000`(`lnYLIWP2l-I` 등)** 포렌식 데이터를 결합하여 아래 **3대 핵심 목표**를 파이프라인에 통합 구현합니다.

### 핵심 기술 타당성 분석 요약 (왜 지금까지 안 나왔고, 어떻게 100% 구현하는가)

| 구현 과제 | 왜 지금까지 우리 영상에서 안 나왔는가? | `신비한 건축사전` × `@RicksClips3000` 원리 기반 **100% 구현 해법** |
|---|---|---|
| **1. 드론으로 찍는 듯한 입체 비행감**<br>*(Drone / FPV Continuous Flight)* | 기존 클립은 `Start 프레임 1장`만 넣고(`end_reference_image = None`) `4.4m` 좁은 방 안에서 찍어, 프롬프트에 `fpv_3d_flight`를 써도 제자리에서 `15%` 줌인만 발생함 | **① `10배 스케일 점프 VIDEO_FRAMES`**: `Start = 상공 30m 광각 조감도` + `End = 지상 2m 건물 창문/내부` 두 장을 동시에 넣어 Flow가 **30m 공간을 실제로 활강**하게 강제<br>**② 공유 키프레임 원테이크 릴레이(`K0→K1→K2`)**: `@RicksClips3000` 방식 그대로 `Clip 1의 End(K1)`를 `Clip 2의 Start(K1)`로 물려 **하늘 → 건물 기둥 스침 → 창문/외벽 절개 관통 → 실험실 착지**를 끊김 없는 원테이크 드론 샷으로 연결<br>**③ 전경 스침 장애물(기둥·가로수·창틀)**: 카메라 옆을 스쳐 지나가는 전경 패럴랙스 지오메트리 배치 |
| **2. `"아 진짜 UCL이네!"` 실물 건축·장소·장비 고증**<br>*(Real-World Reference Conditioning — 학교뿐 아니라 전반 적용)* | 텍스트로만 `"London university lab"`이라고 쓰면 AI가 매번 정체불명의 가상 건물을 지어냄 | **`Rule R72-R` 실물 사진 구조 컨디셔닝 엔진 신설**:<br>Wikimedia Commons 공개 API(무료·무인증, 방금 이 서버에서 `UCL Wilkins Building Portico`, `Harvard Memorial Hall`, `Baylor Pat Neff Hall` 고해상도 실물 사진 즉시 조회 실증 완료)로 **실제 대학교 상징 건물·병원·런던 지하철/도심 거리·교량·실제 MRI/로봇 실험 장비**의 실물 사진을 `/tmp/aab_real_refs/`에 받아 구조 가이드로 Google Flow `Image`에 주입 → **기둥 개수·돔 지붕·벽돌 색감·장비 외형까지 실물 그대로 닮은 3D 디오라마 키프레임** 생성 (원본 픽셀 재사용 `0%`, 저작권 완전 안전) |
| **3. 넓은 야외 스케일 & 빠른 장면 전환**<br>*(Open-World `>=35%` & `2.2~3.2s` Fast-Cut)* | 야외 컷 `0/61(0%)`, 동일 방 4연속 정체, `CUT_COUNT_MAX = 28` 상한으로 평균 `5.7초/컷` 지연 | 에피소드 전체 **`>= 35%` 야외·광역 건축 의무화**, 동일 실내 방 연속 **`<= 2컷` 제한**, `8초` 클립 중 드론 최고속 코어 구간(`1.8~2.6s`) 발췌 + `A₁→B→A₂` 교차편집으로 **평균 `2.2~3.2초/컷` (`총 30~44 EDL 컷`)** 달성 |

```mermaid
flowchart LR
    REF["Wikimedia 실물 레퍼런스 수집\n(UCL 윌킨스 빌딩 / 하버드 / 도심 / 실제 장비)\n/tmp/aab_real_refs 격리"] --> K01["Flow Image 실물 고증 변환\nK0(상공 조감) -> K1(실제 외관) -> K2(3D 외벽 절개 실험실)"]
    K01 --> DRONE1["Clip 1 (0.0~2.2s, VIDEO_FRAMES K0->K1)\n상공 30m 드론 활강 -> 실제 대학교 파사드 접근"]
    DRONE1 --> DRONE2["Clip 2 (2.2~4.5s, 공유 K1->K2)\n기둥·창틀 관통 FPV 드론 다이브 -> 실험실 장비 착지"]
    DRONE2 --> WORLD["Act 2~6 고속 교차 전개 (2.2~3.2s/컷)\n실내 실험 <-> 실물 고증 도심·교량·공원 드론 샷 (>=35%)"]
```

---

## User Review Required

> [!IMPORTANT]
> **핵심 설계 확인 사항 (`Rule R72` + `Rule R72-R`)**:
> 1. **실물 레퍼런스 고증 범위 (`학교 + 도시/랜드마크 + 핵심 실험 장비` 전반 확대)**:
>    - **기관/건축물**: 대본에 등장하는 실제 대학·연구소·병원(예: `UCL Wilkins Portico`, `Harvard Memorial Hall / Harvard Yard`, `MIT Great Dome`, `Oxford Radcliffe Camera`, `Iowa Old Capitol`, `Baylor Pat Neff Hall` 등)
>    - **일상/도시 공간**: 스토리 배경 도시의 실제 거리·지하철역·교량·공원·경기장(예: 런던 튜브 승강장/밀레니엄 브리지, 뉴욕 지하철/센트럴파크, 보스턴 찰스강 등)
>    - **실제 과학 장비**: 논문 속 실제 장치(예: `3T MRI 스캐너`, `64채널 EEG 캡`, `팬터그래프 간지럼 로봇 암`, `단방향 관찰창 실험 부스` 등)
>    - 모든 실물 참고 사진은 [`source_reenactment.py`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/source_reenactment.py)(`Rule R67`)와 동일하게 `/tmp/aab_real_refs/<slug>/`에만 임시 격리하고, Google Flow `Image`를 통해 **우리 채널의 3D 미니어처/건축 단면 화풍으로 100% 새로 렌더링(`dHash` 비침해 검증 포함)**합니다.
> 2. **시그니처 드론 카메라 비중**: 오프닝 `Clip 01 → Clip 02` 원테이크 드론 진입(`하늘 조감 → 건물 절개/창문 관통 → 실험실`)을 필수 고정하고, 본편 전환 구간(장소 이동·야외 비유·엔딩 풀백)에도 드론/FPV 궤적(`drone_aerial_approach`, `fpv_window_portal_breach`, `drone_high_orbit_drop`, `vertical_90_topdown_dive`, `drone_pullback_skyline`)을 최소 `40%+` 배치합니다.
> 3. **진행 중인 `Ep #6` 처리**: 현재 백그라운드 마무리 단계인 `Ep #6`(`11/13 19:30 ET` 슬롯)는 스케줄 공백 없이 그대로 예약 완료하고, **승인 즉시 본 계획을 구현해 `Ep #7`(`gilbert_reversible_choice_paradox` — 실제 하버드 메모리얼 홀/하버드 야드 상공 드론 활강 → 암실/실험실 절개 진입!)부터 바로 적용**합니다.

---

## Proposed Changes

### 1. 실물 건축·도시·장비 레퍼런스 자동 수집 & 3D 고증 변환 엔진 (`Rule R72-R`)
#### [NEW] [real_world_reference_builder.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/real_world_reference_builder.py)
- 에피소드 도시에(`research_dossiers/<slug>/`) 및 `visual_plan.json`에서 **① 연구 대학/병원 외관, ② 배경 도시 거리/랜드마크, ③ 핵심 실험 장치** 엔티티를 자동 추출합니다.
- **Wikimedia Commons API (`commons.wikimedia.org/w/api.php`) 자동 검색 & 격리 다운로드**:
  - 기관별 대표 상징 건축물 매핑 사전(`INSTITUTION_ICONIC_LANDMARK_MAP`: 예 `"ucl" -> "UCL Wilkins Building portico London"`, `"harvard" -> "Harvard Yard Memorial Hall Widener Library"`, `"mit" -> "MIT Great Dome Killian Court"`, `"baylor" -> "Baylor Pat Neff Hall Founders Mall"`, `"iowa" -> "University of Iowa Old Capitol Pentacrest"`, `"oxford" -> "Radcliffe Camera Oxford"` 등 + 동적 검색 폴백) 내장.
  - 다운로드된 원본 사진은 `/tmp/aab_real_refs/<project_id>/`에만 보관하고, 인물 얼굴/차량 번호판/워터마크 영역을 자동 마스킹한 뒤 `9:16` 구조 레퍼런스 가이드(`guide_<anchor_id>.png`)를 생성합니다.
- **실물 비침해 & 구조 일치 검증 (`RQ-Real`)**:
  - Google Flow `0-credit Image`가 생성한 3D 디오라마 키프레임(`ref_loc_<id>_9x16.png`)이 실물 건물의 핵심 윤곽(지붕선·기둥 열주·창문 배열 엣지 구조 유사도 `>= 0.30`)은 유지하되 원본 사진 픽셀 복사(`dHash distance >= 14`)는 없도록 검증 후 `/tmp/aab_real_refs/` 임시 원본을 정리합니다.

---

### 2. 드론/FPV 카메라 무빙 5종 & SSOT 고속 컷 상수 개편 (`Rule R72`)
#### [MODIFY] [config.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/config.py)
- 드론/FPV 전용 카메라 무브 5종 및 건축 절개·야외 문법 추가, 첫 컷 및 본편 컷 속도 상한 단축:

```diff
 EXPRESSIVE_V8_RIGID_PHYSICS_GRAMMARS: tuple[str, ...] = (
     "axial_portal_dive",
     "xray_peel_micro",
     "ghost_twin_offset",
     "lid_lift_reveal",
     "locked_exploded_vs_shatter",
     "blueprint_3d_extrusion",
+    "architectural_cutaway_portal",
 )
 EXPRESSIVE_V8_VISUAL_GRAMMARS: tuple[str, ...] = (
     "expressive_vinyl_world",
+    "expressive_exterior_establishing",
     "expressive_hands_closeup",
...
+EXPRESSIVE_V8_DRONE_CAMERA_MOVES: tuple[str, ...] = (
+    "drone_aerial_approach",
+    "fpv_window_portal_breach",
+    "drone_high_orbit_drop",
+    "vertical_90_topdown_dive",
+    "drone_skyline_pullback",
+)
 EXPRESSIVE_V8_3D_FLIGHT_MOVES: tuple[str, ...] = (
     "dolly_zoom_vertigo",
     "whip_pan_occlusion",
     "orbital_3d_arc_sweep",
     "crane_swoop_dive",
     "portal_dive_flight",
     "fpv_3d_flight",
     "axial_portal_dive",
     "gentle_push_in",
     "clean_pullback_reveal",
+    *EXPRESSIVE_V8_DRONE_CAMERA_MOVES,
 )
...
-EXPRESSIVE_V8_FIRST_CUT_MAX_SEC = 10.50
+EXPRESSIVE_V8_FIRST_CUT_MAX_SEC = 2.60
-EXPRESSIVE_V8_FIRST_15S_MAX_CUT_SEC = 12.50
+EXPRESSIVE_V8_FIRST_15S_MAX_CUT_SEC = 3.20
+EXPRESSIVE_V8_FIRST_15S_MIN_CUTS = 5
-EXPRESSIVE_V8_MAX_CUT_SEC = 10.50
+EXPRESSIVE_V8_MAX_CUT_SEC = 4.80
-EXPRESSIVE_V8_AVG_CUT_TARGET_RANGE: tuple[float, float] = (2.20, 7.50)
+EXPRESSIVE_V8_AVG_CUT_TARGET_RANGE: tuple[float, float] = (2.05, 3.30)
-SHORTS_EXPRESSIVE_V8_CLIP_COUNT_MIN = 18
-SHORTS_EXPRESSIVE_V8_CLIP_COUNT_DEFAULT = 20
-SHORTS_EXPRESSIVE_V8_CLIP_COUNT_MAX = 26
-SHORTS_EXPRESSIVE_V8_CUT_COUNT_MIN = 18
-SHORTS_EXPRESSIVE_V8_CUT_COUNT_MAX = 28
+SHORTS_EXPRESSIVE_V8_CLIP_COUNT_MIN = 22
+SHORTS_EXPRESSIVE_V8_CLIP_COUNT_DEFAULT = 28
+SHORTS_EXPRESSIVE_V8_CLIP_COUNT_MAX = 36
+SHORTS_EXPRESSIVE_V8_CUT_COUNT_MIN = 28
+SHORTS_EXPRESSIVE_V8_CUT_COUNT_MAX = 46
+
+# Rule R72 + R72-R Locks
+EXPRESSIVE_V8_REQUIRE_EXTERIOR_COLD_OPEN = True
+EXPRESSIVE_V8_MIN_OUTDOOR_OR_ARCH_RATIO = 0.35
+EXPRESSIVE_V8_MIN_DRONE_FLIGHT_RATIO = 0.35
+EXPRESSIVE_V8_MAX_CONSECUTIVE_SAME_INDOOR_LOC = 2
+EXPRESSIVE_V8_REQUIRE_REAL_LANDMARK_REFS = True
```

---

### 3. 원테이크 드론 릴레이(`K0 → K1 → K2`) & 실물 고증 키프레임 합성
#### [MODIFY] [porcelain_anchor_pack.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/porcelain_anchor_pack.py)
- **실물 가이드 결합 로케이션 마스터 생성**: `real_world_reference_builder.py`가 확보한 실물 건축/거리/장비 가이드가 있을 경우 `conditioned_on`에 해당 실물 구조 가이드를 바인딩하고, 실제 건축 양식 특징(예: 코린트식 10기둥 포티코·중앙 돔·석재 계단·광장 잔디)을 명시하여 `"아 진짜 UCL이네!"`가 즉시 느껴지는 `ref_loc_*` 마스터를 생성합니다.
- **오프닝 3단 원테이크 드론 체인(`K0 → K1 → K2`) 자동 생성**:
  1. `K0` (`kf_01_aerial_wide_9x16.png`): 상공 `30m` 조감 시점의 실제 대학교 캠퍼스·주변 도시 전경
  2. `K1` (`kf_01_facade_close_9x16.png`): `K0`에서 드론이 하강해 건물 정면 기둥·대형 창문 코앞(`4m`)까지 다가온 프레임 (`Clip 01`의 `End`이자 **`Clip 02`의 공유 `Start`**!)
  3. `K2` (`kf_02_cutaway_lab_9x16.png`): `K1`을 컨디셔닝으로 받아 같은 건물 외벽이 `'신비한 건축사전'`처럼 3D 단면으로 열리며 내부 실험실 핵심 장비가 드러나는 프레임 (`Clip 02`의 `End`)
- 이 `K0 → K1 → K2`가 `VIDEO_FRAMES` 모드로 연결되어 첫 `4.5초` 동안 **하늘에서 실제 대학 건물 안 실험실까지 한 번에 꽂히는 드론 원테이크**를 완성합니다.

#### [MODIFY] [depiction_rules.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/depiction_rules.py) & [flow_prompt_builder.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/flow_prompt_builder.py)
- `EXPRESSIVE_V8_CAMERA_DESCRIPTORS` 및 `EXPRESSIVE_V8_COMPACT_CAMERA_DESCRIPTORS`에 드론 5종 문구 추가 (전경 가로수·열주 기둥·지붕선·창틀을 스치며 날아가는 패럴랙스 지시어 포함).
- 야외/건축 클립에서 클로즈업 눈썹/손 패딩이 강제 삽입되던 버그 수정.
- `validate_expressive_v8_prompts()` (`prompt-gate`)에 **`R72-1`(오프닝 야외 대학교/랜드마크 드론 진입 필수)**, **`R72-2`(전체 `>= 35%` 야외·광역 건축 비율)**, **`R72-3`(동일 실내 방 연속 `<= 2컷`)**, **`R72-4`(드론/FPV 궤적 비율 및 실물 레퍼런스 매니페스트 검증)** 추가.

---

### 4. `Blender 4.2 Previs v2.2` 드론 고도 궤적(`z=14m → 2m`) & 광역 건축 세트
#### [NEW] [location_registry.json](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/BCI_Shorts_Channel/knowledge_base/reusable_packs/location_registry.json) & [MODIFY] [previs_blender.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/previs_blender.py)
- `4.4m` 실내 뒷벽을 없앤 **`28m × 32m` 오픈 스카이 광역 건축 프리셋**(`campus_portico_quad`, `brick_ivy_courtyard`, `building_cutaway_portal`, `urban_avenue_crosswalk`, `transit_station_platform`, `bridge_river_span`, `park_tree_allée`, `stadium_bowl`) 추가.
- 드론 카메라 프리셋 5종의 실제 3D 궤적 수식 추가:
  - `drone_aerial_approach`: `pos_start=[0.0, -24.0, 13.5] -> pos_end=[0.0, -4.8, 3.2]` (전경 가로수·기둥 사이를 통과하는 급강하 드론 곡선)
  - `fpv_window_portal_breach`: `pos_start=[0.0, -4.8, 3.2] -> pos_end=[0.0, -0.9, 1.45]` (`0.22` 알파 창문/반절개 외벽을 실제로 관통해 실내 실험대로 진입!)
  - `vertical_90_topdown_dive`: `pos_start=[0.0, 0.0, 16.0], pitch=-88° -> pos_end=[0.0, -1.5, 1.8]` (`신비한 건축사전` `M1` 직부감 수직 낙하)

---

### 5. 드론 최고속 구간(`Peak-Velocity Core`) 발췌 어셈블러 & 규칙 동기화
#### [MODIFY] [diorama_assembler.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/diorama_assembler.py)
- 드론/FPV 클립 발췌 시 카메라가 출발/정지하며 머뭇거리는 양 끝단 대신 **비행 가속도가 가장 매끄러운 코어 구간(`0.45s ~ 2.75s`)**을 우선 발췌하고, 공유 키프레임(`K1`) 원테이크 릴레이 구간에서는 프레임 손실 없는 직결(`seamless_relay_cut`)을 수행합니다.
- 문장 내 키워드/절 단위 서브컷 + `Dual-Harvest (A₁ → B → A₂)`를 결합해 초반 15초 `>= 5컷`, 본편 평균 `2.05 ~ 3.30s/컷`(`85%+` 칼컷/공유키프레임 전환)을 완성합니다.

#### [MODIFY] [neuro_diorama_rules.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/neuro_diorama_rules.md), [production_constants.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/production_constants.md), [SKILL.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/skills/youtube-script/SKILL.md), [AGENTS.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/AGENTS.md)
- `Rule R72` & `Rule R72-R` 명문화 (`AGENTS.md` `< 10,240 bytes`, `<= 78 lines` 엄수).

---

## Verification Plan

### Automated Tests
- 신규 통합 테스트 `[NEW] tests/test_r72_drone_and_real_landmarks.py` 작성 및 전체 스위트 실행:
  ```bash
  /home/canadaofbin/hermes-venv/bin/python -X utf8 -m pytest tests/test_r72_drone_and_real_landmarks.py -v
  /home/canadaofbin/hermes-venv/bin/python -X utf8 -m pytest -q
  ```
- 검증 항목:
  1. `real_world_reference_builder.py`가 `UCL`, `Harvard`, `Baylor`, `London Underground`, `MRI Scanner` 실물 레퍼런스를 `/tmp/aab_real_refs/`에 정상 수집·가이드 변환 후 워크스페이스 원본 유출 `0건`을 유지하는지 검증
  2. `Blender 4.2 Previs v2.2`에서 `drone_aerial_approach`(`z=13.5m -> 3.2m`) → `fpv_window_portal_breach`(창문 관통 실내 진입) 연속 궤적이 정상 렌더링되는지 검증
  3. `R72-1 ~ R72-4` 프롬프트 게이트 및 `2.05~3.30s/컷` 고속 EDL 빌더 통과 검증

### Manual Verification
1. **실물 고증 + 드론 진입 데모 시트 확인**: 실제 **UCL 윌킨스 빌딩**과 **하버드 메모리얼 홀/하버드 야드** 실물 레퍼런스로 뽑은 `K0(상공 드론) → K1(실제 외관 기둥) → K2(3D 외벽 절개 실험실)` 키프레임 비교 시트를 먼저 확인합니다.
2. **`Ep #7` (`gilbert_reversible_choice_paradox` — 하버드 대학교 편) 실전 적용**: 하버드 야드 실제 건축물 드론 다이브 오프닝 + 보스턴/캠퍼스 야외 일상 컷(`>= 35%`) + 평균 `~2.6s` 고속 전환이 적용된 완제품 쇼츠를 검증합니다.
