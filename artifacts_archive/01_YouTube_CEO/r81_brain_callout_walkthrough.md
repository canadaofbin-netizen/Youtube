# `Ep #9` 런던 택시 드라이버 완성본 (`Rule R80` + `Rule R81` 최종 마스터)

![Ep #9 런던 택시 드라이버 최종 완성본 (83.10s, 1080x1920 @ 30fps)](./final_shorts_v8_ep09_maguire_london_taxi_hippocampus.mp4)

- **최상위 폴더 원본 파일**: [final_shorts_v8_ep09_maguire_london_taxi_hippocampus.mp4](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/final_shorts_v8_ep09_maguire_london_taxi_hippocampus.mp4) (`83.10초`, `100.91 MB`)
- **YouTube Shorts 공개 링크**: https://www.youtube.com/shorts/tWjrK5enOoM

---

> [!IMPORTANT]
> **핵심 완료 요약 (`2026-11-16`)**
> 1. **기존 감성 100% 유지 + `XL` 타이포그래피 & 취소선 `0px` 해결 (`Rule R81`)**:
>    - 기존 `PatrickHand` 손글씨 폰트, 아이보리·시안·골드·크림슨·슬레이트 팔레트, 박스 없는 만년필 잉크 선 질감(`ink_pen`)을 100% 유지하면서 메인 글씨를 **`82~84px` (`약 2배` 높이, 긴 명칭은 자동 2줄 중앙 스택)**, 부제를 **`56px`**로 확대하고 **글자 관통 밑줄(`Strikethrough`)을 `0px`로 영구 제거**했습니다.
> 2. **무지연 뇌 추적(`1.0x DISOpticalFlow` + 발광 피크 중심 락 + `View-Flip Guard`) 탑재**:
>    - 기존 `0.12x` 감쇠 지연 버그와 `±75px` 고정 클램프를 제거해 실제 뇌 움직임을 `1.0x` 정속 추적하고, Google Flow가 후반에 뇌를 `90°` 회전시키는 구간에서는 지시선만 부드럽게 페이드아웃하며, 서로 다른 컷 간 데이터 스탬프 충돌 버퍼(`2.0s -> 0.08s`)를 보정해 **`Cut 14` 중도 소멸 버그를 해결**했습니다.
> 3. **오늘 밤 `19:30 ET` 공개 예정 `Ep #9`(런던 택시) 마스터 교체 완료**:
>    - 신규 예약 비디오 ID: **`tWjrK5enOoM`** (https://www.youtube.com/shorts/tWjrK5enOoM) — `2026-11-16 19:30 ET` (`Slot 4`) `Scheduled` 확정, 앵커 `p4ou90cHt50` 연결 완료(`linked_verified`), 구 예약 드래프트 `YGKTFbKsFH8` 영구 삭제(`Delete forever`, 채널 내 `Private = 0`), 공개 완료된 `Ep #8`(`Atd0Pi9HPg4`) 시드 보호(`Rule R75`) 유지.

---

## 1. 실제 마스터 MP4 전수 시각 검증 (`Ep #9` 7개 뇌 컷 전체 & YouTube Studio 증빙)

````carousel
![Ep #9 실제 마스터 MP4 전후 비교 Part 1 (Cut 05, Cut 06, Cut 07, Cut 13)](./ep09_r81_final_mp4_before_after_part1.jpg)
<!-- slide -->
![Ep #9 실제 마스터 MP4 전후 비교 Part 2 (Cut 14 중도 소멸 복원, Cut 16, Cut 17)](./ep09_r81_final_mp4_before_after_part2.jpg)
<!-- slide -->
![YouTube Studio 신규 예약본 tWjrK5enOoM 등록 및 구 드래프트 YGKTFbKsFH8 영구 삭제 완료 화면](./ep09_r81_studio_scheduled_swap_verified.png)
<!-- slide -->
![Ep #8 업로드 스크린샷 3종 기준 XL 82~84px 시안 비교](./callout_r81_hand_ink_xl_preview.jpg)
````

---

## 2. 파이프라인 반영 파일 및 자동 검증 결과

| 구분 | 반영 파일 / 영수증 | 검증 결과 |
|---|---|---|
| **`Rule R81` 콜아웃 & 추적 엔진** | [anatomy_label_overlay.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/anatomy_label_overlay.py), [config.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/config.py) | `82~84px` XL 손글씨 + 자동 2줄 스택 + 밑줄 침범 `0px` + `1.0x DISOpticalFlow` 추적 |
| **컷 간 스탬프 버퍼 & Flow 회전 방지** | [diorama_assembler.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/diorama_assembler.py), [flow_prompt_builder.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/flow_prompt_builder.py), [publish.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/publish.py) | 이종 컷 버퍼 `0.08s` (`Cut 14` `63.60s`까지 유지) + Flow `<= 20°` 단일 평면 패럴랙스 |
| **단위·회귀 테스트 (`pytest`)** | [test_r81_callout_tracking_and_legibility.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/tests/test_r81_callout_tracking_and_legibility.py) 외 5개 스위트 | **`28 / 28 PASS (100%)`** (`DQ10` 및 3플랫폼 안전영역 통과) |
| **`Ep #9` 마스터 QA & 무결성** | [final_shorts_1080x1920.mp4](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/BCI_Shorts_Channel/projects/v8_ep09_maguire_london_taxi_hippocampus/05_assembly/final_shorts_1080x1920.mp4), [edit_decision_list.json](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/BCI_Shorts_Channel/projects/v8_ep09_maguire_london_taxi_hippocampus/05_assembly/edit_decision_list.json) | `posthoc-qa 96.6 PASS`, `episode-qa PASS`, `autopsy PASS`, `156 / 156 INTACT` |
| **YouTube Studio 예약 교체** | [upload_receipt.json](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/BCI_Shorts_Channel/projects/v8_ep09_maguire_london_taxi_hippocampus/06_publish/upload_receipt.json), [related_video_receipt.json](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/BCI_Shorts_Channel/projects/v8_ep09_maguire_london_taxi_hippocampus/06_publish/related_video_receipt.json) | **`tWjrK5enOoM`** (`2026-11-16 19:30 ET` Scheduled, `-> p4ou90cHt50` 연결, `Private = 0`) |
