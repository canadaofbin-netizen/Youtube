# 뇌 해부 콜아웃 오정렬·취소선·가독성 진단 및 업그레이드 계획 (`v3` — `XL 82~84px` 확대 + 기존 폰트·색상·선 질감 100% 유지)

피드백을 반영해 **기존 손글씨 폰트(`PatrickHand`), 아이보리·시안·골드·크림슨 색상, 박스 없는 만년필 잉크 선 질감(`ink_pen`)은 100% 그대로 유지**하면서, 메인 글씨 크기를 기존(`38~44px`) 대비 **약 `2배` 높이(`82~84px`, 면적 기준 `~3.8배`), 부제를 `56px`까지 대폭 키운 `XL` 타이포그래피 + 자동 2줄 허브 스택**으로 계획을 업그레이드했습니다.

---

## 1. `BEFORE vs AFTER XL` 전수 비교 (업로드해주신 3개 장면 전체 적용)

![동일 폰트·만년필 질감 유지 + XL 82~84px 확대 전후 비교 (Ep08 Cut 14, Cut 06, Cut 12)](./callout_r81_hand_ink_xl_preview.jpg)

---

## 2. 사진(3장) + 영상(`Ep #8` · `Ep #9` 13개 뇌 컷) 핵심 원인 요약

![Ep08 및 Ep09 실제 렌더링 프레임 결함 전수 감사](./callout_audit_defects_ep08_ep09.jpg)

1. **밑줄이 글자 정중앙을 관통하는 '취소선' 버그** ([anatomy_label_overlay.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/anatomy_label_overlay.py#L945-L1022) & `#L472`):
   - `probe.textbbox((0, 0), text)`에서 `PatrickHand` 상단 여백(`lb[1] ≈ +16px`)을 누락해 실제 글자 하단보다 `12px` 위(글자 한가운데)에 밑줄을 그렸습니다.
2. **모바일에서 글씨가 작아진 구조적 원인** (`#L938–966`):
   - `Vision Stream ──▶ Fusiform Match`처럼 긴 두 해부 명칭과 화살표를 **무조건 한 줄(`usable_w = 814px`)에 우겨 넣으려다 보니** 글씨가 `33~44px`(부제 `27~32px`)까지 강제 축소되었습니다.
3. **뇌 움직임 대비 지시선이 어긋나는 버그** (`#L768–847`):
   - 매 프레임 광학흐름 이동량에 `0.12`를 곱해 **실제 뇌 이동의 `88%`를 버리고 지연 위치에 재시드**한 버그 + 좁은 클램프(`±75px`, `y <= 1205px`) + Google Flow 클립의 후반 `90°` 뇌 회전이 겹쳐 지시선이 실제 발광 부위에서 이탈했습니다.
   - `0.07 * sin(3θ)` 왜곡으로 타겟 고리가 삼각형처럼 찌그러졌고, 다음 컷(`C15`) 데이터 스탬프와의 `2.0s` 충돌 버퍼가 `C14` 콜아웃을 절반 시점에 조기 소멸시켰습니다.

---

## 3. 핵심 해결 설계 (`Rule R81`)

### ① `XL` 손글씨 확대 (`82~84px` / 부제 `56px`) + 자동 2줄 허브 스택 + 취소선 `0px`
| 항목 | 기존 (`Ep #8` / `Ep #9`) | `v2` 시안 | **`v3 XL` 확정안** |
|---|---|---|---|
| **폰트 / 색상 / 선 질감** | `PatrickHand` + 만년필 잉크 | 동일 유지 | **100% 동일 유지 (배경 박스 없음)** |
| **짧은 라벨 (`Check OFF vs Warmth ON`)** | `44px` (1줄) | `58px` (1줄) | **`84px` (1줄 시원하게 배치)** |
| **긴 라벨 (`Vision Stream`, `Fusiform Match`)** | `38px`로 강제 축소 | `54px` (1줄) | **`82px` (자동 2줄 중앙 정렬 스택)** |
| **연결어 (`vs` / 화살표)** | `28px` / 얇은 선 | `40px` / 중간 선 | **`56px` / 두꺼운 만년필 화살표 (`6.0px`)** |
| **부제 (`Reality Check Offline` 등)** | `27~32px` | `42px` | **`56px` (기존 메인보다 더 큼)** |
| **밑줄 위치 (`Strikethrough` 수정)** | `node_y + (lb[3]-lb[1])` (관통 버그) | `lb_drawn[3] + 9px` | **실제 글자 하단 `lb_drawn[3] + 10px` (`0px` 침범)** |
| **상단 안전선 / 밝은 배경 대비** | `Y = 196px` / 후광만 존재 | `Y = 228px` | **`Y = 246px` (`>=12%` 안전선 통과) + 다크 잉크 림(`Rim`) 언더스트로크** |

- **동작 원리**:
  1. 먼저 `84px → 72px` 범위에서 1줄 배치가 안전 폭(`X = 78..904px`, 우측 Shorts 아이콘 바 완전 회피) 안에 들어오면 **1줄 `84px`**로 렌더링합니다 (`Cut 14`).
  2. 1줄로 놓을 때 `72px` 미만으로 작아져야 하는 다단어 라벨(`Vision Stream`, `Fusiform Match`, `Amygdala Warm`, `Sound Wire`)은 **자동으로 2줄 중앙 스택(`Vision / Stream`)으로 전환하여 `80~82px` 특대 크기를 그대로 유지**합니다 (`Cut 06`, `Cut 12`).
  3. 만년필 선과 원형 고리는 `rim_canvas`(다크 잉크 테두리) → `fg_canvas`(컬러 만년필 잉크) → `text_canvas` 순서로 합성해 선 교차점 얼룩 없이 밝은 회백질·시안 번개 위에서도 선명하게 읽힙니다 (`DQ10` 및 `UNIVERSAL_SAFE_X_RIGHT_PX=910` 정밀 검증 통과 완료).

### ② 뇌 움직임 무지연 추적 (`1.0x DISOpticalFlow` + 발광 피크 중심점 락)
1. **`0.12x` 감쇠 버그 제거 & 발광 부위 정중앙 락(`Hue-Emission Peak Lock`)**:
   - `0.88/0.12` 감쇠와 `±75px` 클램프를 제거하고(`y <= 1280px`까지 개방), 실제 컷 시작 프레임(`src_start_sec` 반영)에서 `cv2.DISOpticalFlow` `1.0x` 변위 + 타겟 색상(적색 편도체·황금 해마·시안 경로)의 로컬 발광 중심점(`refine_hue_emission_peak`)을 결합한 뒤 **양방향(Zero-Phase) 스무딩**으로 지연 `0.0프레임` 추적을 구현합니다.
   - `Blender 4.2` `camera_track.json`이 존재하는 컷은 3D 월드 좌표 투영을 최우선 적용합니다.
2. **Google Flow `90°` 회전 방어 (`View-Flip Guard`) & `C14` 조기 소멸 수정**:
   - 클립 후반에 뇌가 측면→정면으로 `90°` 돌아가는 구간은 광학흐름 역방향 오차(FB-Error)로 감지해 회전 전 안정 서브윈도우를 우선 선택하거나 회전 직전에 지시선을 깔끔하게 페이드아웃하며, [flow_prompt_builder.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/flow_prompt_builder.py)에 `<= 20°` 단일 해부 평면 패럴랙스 제약을 추가합니다.
   - [diorama_assembler.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/diorama_assembler.py#L2094)의 `resolve_overlay_window_conflicts`에서 서로 다른 컷 간 버퍼를 `2.0s → 0.08s`로 줄여 `Cut 14` 콜아웃이 끝까지 유지되도록 수정합니다.

---

## 4. 실행 순서 및 확인 사항

1. **코드 업그레이드 & 자동 검증**: [config.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/config.py), [anatomy_label_overlay.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/anatomy_label_overlay.py), [diorama_assembler.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/diorama_assembler.py), [flow_prompt_builder.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/flow_prompt_builder.py) 반영 및 단위 테스트(`취소선 침범 0px`, `XL 폰트 크기`, `DQ10` 안전 마진, `1.0x` 추적 정밀도) 통과.
2. **오늘 밤 `19:30 ET` 공개 예정인 `Ep #9`(런던 택시, `YGKTFbKsFH8`) 즉시 재조립 & 예약본 교체**: `Ep #9`의 7개 뇌 컷(`Cut 5, 6, 7, 13, 14, 16, 17`)에 `XL` 콜아웃과 무지연 추적을 적용해 검수 후 YouTube Studio 예약 영상을 교체합니다.

> [!IMPORTANT]
> **확인 부탁드립니다**:
> 1. 위 `v3 XL` 시안(`82~84px` 메인 + 자동 2줄 스택 + `56px` 부제) 크기가 마음에 드시면 **Proceed**를 눌러주시면 바로 구현 및 **`Ep #9`(런던 택시) 예약본 교체**까지 진행하겠습니다.
> 2. 이미 공개된 **`Ep #8`(스크린샷 속 영상)**은 기존 조회수 시드 보호(`Rule R75`)를 위해 현행 유지할지, 아니면 함께 재렌더링할지도 말씀해 주세요!
