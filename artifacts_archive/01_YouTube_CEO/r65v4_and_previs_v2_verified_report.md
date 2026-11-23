# `R65 v4` 라이브 썸네일 교체 & `3D Previs v2` 업그레이드 검증 완료 보고서

> [!TIP]
> **체크포인트 1 독립 검증 완료 (`417/417` pytest 통과 · `Draft = 0`)**:
> 승인해 주신 계획대로 **① 내일 오전 `09:30 KST` 공개 예정인 `Ep #4`(`7W8zIOMKPrQ`)와 모레 공개 예정인 `Ep #5`(`ut1wde0d19o`)의 라이브 YouTube Studio 썸네일이 신규 `R65 v4`(`2:3` 선반 크롭 안전 보정 완료본)로 교체 완료**되었으며, **② 포터블 `Blender 4.2.23 LTS` 기반 `3D Previs v2`(`P1~P6`) 전 항목 업그레이드**도 검증을 마쳤습니다. 현재 `@Operator`는 `@심리학고양이` 분석 1순위 소재인 **`Ep #6`(`v8_ep06_bedtime_todo_list_sleep`, `2026-11-13 19:30 ET` 슬롯)** 본편 제작에 즉시 진입했습니다.

---

## 1. Step 1 검증 — `R65 v4` 라이브 Studio 반영 & `2:3` 쇼츠 선반 크롭 검증

````carousel
![YouTube Studio 라이브 반영 완료 화면 — Ep #4(12 Nov Scheduled) & Ep #5(13 Nov Scheduled) 신규 R65 v4 썸네일 활성화 및 Draft 0건](./studio_shorts_rows_after_path_a.png)
<!-- slide -->
![유튜브 쇼츠 2:3 선반 크롭(405x608, y=150..1770) 실측 검증 — 상단 'NO FEAR' / 'BY MYSELF' 잘림 0% 및 하단 제목 안전선(빨간 선 y=1520) 완벽 분리](./ep04_ep05_2x3_shelf_crop_verified.png)
````

| 항목 | `Ep #4` (`7W8zIOMKPrQ`) | `Ep #5` (`ut1wde0d19o`) | 검증 결과 |
|---|---|---|---|
| **예약 일시** | `2026-11-11 19:30 ET` (`11/12 09:30 KST`) | `2026-11-12 19:30 ET` (`11/13 09:30 KST`) | Studio DOM **`Scheduled` 유지 (`Draft = 0`)** |
| **`2:3` 선반 안전 위치** | `NO FEAR` → `y = 176..270` (`>= 150`) | `BY MYSELF` → `y = 176..241` (`>= 150`) | 쇼츠 선반 `405×608` 크롭 잘림 **`0%`** |
| **품질 게이트 (`TQ1–TQ9`)** | `9/9 PASS` (`Mean Luma >= 110`) | `9/9 PASS` (`Mean Luma >= 110`) | 기존 다크 브라운 썸네일 대비 Studio 목록 가시성 대폭 상승 |
| **코드 반영** | [`pipeline/thumbnail_studio.py`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/thumbnail_studio.py) · [`pipeline/studio/uploader.py`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/studio/uploader.py) | `in_skull_cutaway_split_v4` 기본화 + `dark_void_paradox_v4`(Mode B) 지원 + `Step 12.5` 자동 업로드 연동 |

---

## 2. Step 2 검증 — `Blender 4.2.23 LTS` 기반 `3D Previs v2` (`P1~P6`) Before vs After

![Ep #4 (S01..S08) 3D Previs v1 (Before) vs Blender 4.2 LTS Previs v2 (After P1-P6)](./ep04_previs_v1_vs_v2_grid.png)

| 업그레이드 축 | 주요 구현 코드 | `Ep #4 (S01..S08)` Before → After 실측 개선 |
|---|---|---|
| **`P1` Headless Blender 4.2 LTS + 반투명 유리/시선 바이저/바닥 격자** | [`pipeline/previs_blender.py`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/previs_blender.py) (`is_blender_available() == True`) | **`S07`**의 불투명 콘크리트 벽 버그가 **`0.22` 알파 반투명 관찰창 유리**로 해결되어 창문 뒤 2명의 신경학자가 선명하게 투시됨; 머리 시선 바이저 + `0.5m` 바닥 격자 + 접지 그림자 적용 |
| **`P2` `9:16` 수평 화각 솔버 & 가시성 게이트** | `solve_9x16_camera_frustum()` / `evaluate_previs_visibility_gate()` | **`S01 · S04`** 좌우 반토막 잘림 해소(`12%` 안전 여백 확보), **`S02_end · S03_start`** `34cm` 몸통 벽 사고 자동 거리 보정 |
| **`P3` 에피소드 Role-Color 고정 + 복수 인원 분리 + 복합 소품** | `expand_cast_entries()` + 복합 실루엣 프리미티브 | `S01→S02` 환자 S.M.(`Forest Olive`) 색상·좌표 일관성 유지, `S07` `"two neurologists"` 2인 자동 분리, **독사 테라리움(`S01~S03`) · 초시계(`S03`) · 호흡 마스크+튜브(`S08`)** 입체 배치 |
| **`P4 ~ P6` 하이브리드 키프레임 · `E7` 구도 QA · `Start+End` 3D 패럴랙스** | [`pipeline/porcelain_anchor_pack.py`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/porcelain_anchor_pack.py) · [`pipeline/reference_image_qa.py`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/reference_image_qa.py) · [`pipeline/flow_diorama_sharded_worker.py`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/flow_diorama_sharded_worker.py) | 에피소드당 핵심 `6~10컷` 프리비즈 조건부 키프레임 생성 + 프리비즈 색상 번짐 차단(`E7`) + 카메라 무브 하이라이트 `3~5컷` `VIDEO_FRAMES` 듀얼 키프레임 패럴랙스 가동 |

---

## 3. Step 3 진행 현황 (`Ep #6` 연속 일일 스케줄링)

- **제작 중 프로젝트**: `v8_ep06_bedtime_todo_list_sleep` (`Scullin et al., 2018` DOI `10.1037/xge0000374` 취침 전 5분 내일 할 일 목록 실험 `15.5분 vs 24.9분` + `Ansfield et al., 1996` 입면 노력 역설 — `@심리학고양이` `#002` `248만 뷰` 검증 원전)
- **목표 예약 슬롯**: **`2026-11-13 19:30 ET` (`2026-11-14 09:30 KST`, `Slot 4`)** — `3D Previs v2` + `R65 v4` + `@심리학고양이` 성공 공식(`Zero-Redundancy` 카피 · `2-Study R70 Data Stamp` · `보초병` 비유 토템 · `Exoneration Flip`) 동시 적용 중.
