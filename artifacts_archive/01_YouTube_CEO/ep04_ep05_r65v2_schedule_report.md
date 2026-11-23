# `Ep #4 · Ep #5` 제작 완료 & `'신비한 건축사전'`형 `R65 v2` 썸네일 · 1일 1편 예약 게시 보고서

> [!IMPORTANT]
> **요청하신 3가지 작업이 전수 완료 및 실측 검증되었습니다.**
> 1. **`R65 v2` 썸네일 스튜디오 적용**: Google Flow 무료(`0-credit`) 이미지 배치로 **3D 두개골·실험장치 절개 단면 키아트**를 생성하고, 파이썬 벡터 엔진으로 **`#FF2525` 빨간 화살표·치수선 콜아웃**과 **좌상단 ↘ 우하단 Z-패턴 2청크 훅**을 합성했습니다 (`TQ1–TQ9` 전수 통과).
> 2. **YouTube Studio `Draft(초안)` 원천 차단 패치 & 전수 점검**: 달력/시각 서브 팝오버 닫힘 처리, `SCHEDULE` 라디오·버튼 라벨(`Schedule`/`예약`) 강제 검증, 업로드 직후 `/videos/short` 행 DOM 실측 및 `Draft` 감지 시 자동 재예약 복구(Self-Heal)를 적용했습니다. 채널 전수 스캔 결과 현재 **`Draft(초안)` 영상 `0`건**(`Scheduled: 2`, `Public: 5`, `Unlisted: 11`)입니다.
> 3. **`Ep #4` · `Ep #5` 1일 1편 프라임 슬롯(`19:30 ET` = `09:30 KST`) 예약 완료**:
>    - **`Ep #4`**: https://www.youtube.com/shorts/7W8zIOMKPrQ — **`11월 12일(내일) 오전 09:30 KST`** (`2026-11-11 19:30 ET`, `12 Nov 2026 Scheduled` 실측 확인)
>    - **`Ep #5`**: https://www.youtube.com/shorts/ut1wde0d19o — **`11월 13일(모레) 오전 09:30 KST`** (`2026-11-12 19:30 ET`, `13 Nov 2026 Scheduled` 실측 확인)

---

## 1. `Ep #4 · Ep #5` 실제 적용된 `'신비한 건축사전'`형 `R65 v2` 썸네일

하단 프리뷰의 **노란색 외곽선**은 실제 유튜브 쇼츠 선반(`2:3` 크롭, `y = 150..1770`) 영역이며, **주황색 하단 박스**는 모바일 쇼츠 선반에서 흰색 영상 제목이 겹치는 마스킹 구역(`y = 1520..1770`)입니다. 상·하 2청크 텍스트와 `#FF2525` 포인터 모두 안전지대 안에 비충돌로 안착했습니다.

````carousel
![Ep #4 R65 v2 3D 절개 단면 썸네일 콘택트 시트 (7W8zIOMKPrQ)](./ep04_r65v2_contact_sheet.png)
<!-- slide -->
![Ep #5 R65 v2 3D 절개 단면 썸네일 콘택트 시트 (ut1wde0d19o)](./ep05_r65v2_contact_sheet.png)
````

---

## 2. 에피소드 제작 · QA · 스튜디오 예약 실측 요약

| 항목 | `Ep #4` (`v8_ep04_patient_sm_fearless_amygdala`) | `Ep #5` (`v8_ep05_ucl_tickle_delay_robot`) |
|---|---|---|
| **제목** | `Why One Breath Terrified a Fearless Woman` | `Why a Delayed Robot Can Tickle You` |
| **YouTube 링크** | https://www.youtube.com/shorts/7W8zIOMKPrQ | https://www.youtube.com/shorts/ut1wde0d19o |
| **예약 일시 (`KST` / `ET`)** | **`2026-11-12 09:30 KST`** (`2026-11-11 19:30 ET`) | **`2026-11-13 09:30 KST`** (`2026-11-12 19:30 ET`) |
| **Studio 행 실측 상태** | `Scheduled` (`12 Nov 2026 Scheduled`) | `Scheduled` (`13 Nov 2026 Scheduled`) |
| **커스텀 썸네일 상태** | `uploaded_custom_thumbnail` (`WCAG@160 = 15.65`) | `uploaded_custom_thumbnail` (`WCAG@160 = 16.40`) |
| **길이 / 컷 수 / 보이스** | `115.03s` / `20`컷 / `elevenlabs_v4` 3인 캐스트 | `111.63s` / `20`컷 / `elevenlabs_v4` 3인 캐스트 |
| **QA 성적** | `DQ 14/14`, `Prosody 10/10`, `PostHoc 96.7`, `TQ 9/9` | `DQ 14/14` (`100.0`), `Prosody 10/10`, `PostHoc 96.8`, `TQ 9/9` |
| **영수증 파일** | [upload_receipt.json](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/BCI_Shorts_Channel/projects/v8_ep04_patient_sm_fearless_amygdala/06_publish/upload_receipt.json) | [upload_receipt.json](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/BCI_Shorts_Channel/projects/v8_ep05_ucl_tickle_delay_robot/06_publish/upload_receipt.json) |

---

## 3. 반영된 핵심 코드 및 테스트

- **썸네일 스튜디오 (`R65 v2`)**: [thumbnail_studio.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/thumbnail_studio.py), [flow_ingredients.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/flow_ingredients.py), [config.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/config.py), [test_r65_v2_cutaway_thumbnail_studio.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/tests/test_r65_v2_cutaway_thumbnail_studio.py)
- **`No-Draft` 예약 검증 & 자동 복구**: [uploader.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/studio/uploader.py), [whale_session.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/studio/whale_session.py), [staging_queue.json](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/BCI_Shorts_Channel/staging_queue.json), [test_studio_schedule_no_draft.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/tests/test_studio_schedule_no_draft.py)
