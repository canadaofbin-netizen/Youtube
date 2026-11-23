# `Ep #9` 런던 택시 18컷 업그레이드 교체 & `Rule R80` 전 파이프라인 적용 완료 보고서

> [!IMPORTANT]
> **핵심 완료 요약 (`2026-11-16`)**
> 1. **`Ep #9` (`v8_ep09_maguire_london_taxi_hippocampus`) 리컷 & YouTube Studio 무중단 예약본 교체 완료**:
>    - 기존 평이한 운전석 2컷(`C09` `5.03s`, `C10` `6.00s`)을 **`@RicksClips3000` 템포(`2.40s~3.30s`, `1.28x~1.34x` 스피드램프) 4컷 공간 릴레이 + `신비한 건축사전`식 `#FF2525` 3D 입체 돌출 화살표(실제 지면 태양 그림자 포함, 무글자 `Zero-Text`)**로 교체하여 총 **`18컷` (`83.10s`, `Siren` 마스터 오디오 100% 보존)** 완성.
>    - 신규 마스터 업로드 ID: **`YGKTFbKsFH8`** (https://www.youtube.com/shorts/YGKTFbKsFH8) — `2026-11-16 19:30 ET` (`Slot 4`) `Scheduled` 확정, `R65 v4` 커스텀 썸네일 적용, 앵커 `p4ou90cHt50`(`1,617` views) 연결(`saved_and_confirmed`), 구 미공개 예약 드래프트 **`7lKtSWvTmpw` 즉시 `Delete forever` 영구 삭제 완료 (`Private = 0`)**.
> 2. **차기 에피소드(`Ep #10 ~ Ep #39`)용 `Rule R80` 파이프라인 영구 탑재 완료**:
>    - Gear 1~4 전 구간 코드 업그레이드 및 [topic_priority_queue.json](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/BCI_Shorts_Channel/topic_priority_queue.json) 내 **30개 골든 큐 도시에 전수 `spatial_contrast_spec` 주입·검증(`30/30 ready=True`)** 완료.

---

## 1. 시각 검증 결과 (`Act 4` 4컷 비교 · `18컷` 전체 시트 · YouTube Studio 예약 교체 증빙)

````carousel
![Act 4 택시 3D 지그재그 화살표 vs 버스 3D 일직선 화살표 실제 마스터 MP4 프레임](./ep09_v2_taxi_vs_bus_3d_arrows.jpg)
<!-- slide -->
![Ep #9 업그레이드 마스터 18컷 전체 콘택트 시트](./ep09_v2_18cut_proof.jpg)
<!-- slide -->
![YouTube Studio 신규 예약본 YGKTFbKsFH8 등록 및 구 드래프트 7lKtSWvTmpw 영구 삭제 완료 화면](./ep09_v2_studio_scheduled_swap_verified.png)
<!-- slide -->
![신규 Rule R80 1080x1920 시작 키프레임 4종 원본](./ep09_v2_r80_keyframes_comparison.jpg)
````

### 교체된 `Act 4` (`42.50s .. 53.53s`) 4-Cut 마이크로 릴레이 실측 상세

| 컷 | 타임코드 (`길이`) | 속도 곡선 | 카메라 무브 | 시각 연출 및 `RQ-Arrow` 기하 실측 |
|---:|---|---|---|---|
| **Cut 09** | `42.50s..44.90s` (`2.40s`) | `1.34x` | `drone_landmark_ascend` | 템스강변 **런던아이(London Eye)** 대관람차 옆을 스치며 블랙캡 위로 급상승 (`Zero-Text`) |
| **Cut 10** | `44.90s..47.53s` (`2.63s`) | `1.32x` | `topdown_3d_route_glide` | `90°` 수직 탑뷰 런던 미로 골목 + **`#FF2525` 3D 입체 돌출 지그재그 화살표** + 실제 지면 태양 그림자 + 교차로 비콘 핀 & 코너 도는 블랙캡 (`tortuosity = 3.8219 >= 1.35`, `Zero-Text`) |
| **Cut 11** | `47.53s..50.23s` (`2.70s`) | `1.34x` | `drone_landmark_ascend` | 런던 **빨간 원형 버스정류장 & 빨간 2층 버스**(`2.82s` 무글자 클린 구간 시작)에서 포틀랜드 석조 지붕·웨스트민스터 스카이라인 위로 급상승 (`Zero-Text`) |
| **Cut 12** | `50.23s..53.53s` (`3.30s`) | `1.28x` | `topdown_3d_route_glide` | `90°` 수직 탑뷰 런던 중앙 대로 + **단 1개의 자 대고 그은 듯한 일직선 `#FF2525` 3D 입체 돌출 화살표** + 지면 그림자 + 직진하는 2층 버스 (`tortuosity = 1.001 <= 1.08`, `R² = 1.0`) → 직후 `Cut 13` (*"Fixed Bus Line → Back Map Flat"*) 유리 뇌 컷 직결 |

---

## 2. 전 구간 자동화 QA 및 Studio 영수증 검증표

| 게이트 / 항목 | 결과 | 실측 수치 및 증빙 파일 |
|---|---|---|
| **단위·회귀 테스트 (`pytest`)** | **PASS** | [test_r80_spatial_arrow_diorama.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/tests/test_r80_spatial_arrow_diorama.py) `4/4 PASS` + `AGENTS.md`/`SKILL.md` 압축 정합성 테스트 `PASS` |
| **`prompt-gate` & `ref-qa`** | **PASS (`100.0`)** | `issues: []`, `22/22` 레퍼런스 `Q1~Q10` 통과 ([reference_image_qa_report.json](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/BCI_Shorts_Channel/projects/v8_ep09_maguire_london_taxi_hippocampus/03_visuals/reference_image_qa_report.json)) |
| **`episode-qa` (`DQ1~DQ_R79`)** | **PASS (`20/20`, `100.0`)** | 뇌 시뮬레이터 비중 `39.67%` (`[38%..48%]`), `cut_duration_cv = 0.2523`, 휴먼 모션 전 컷 통과 ([dynamic_episode_qa_report.json](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/BCI_Shorts_Channel/projects/v8_ep09_maguire_london_taxi_hippocampus/05_assembly/dynamic_episode_qa_report.json)) |
| **`posthoc-qa` (`R64`)** | **PASS (`18/18`)** | 전체 평균 선명도 `96.6`, 신규 `spatial_3d_arrow_diorama` 평균 **`97.2`** (`topdown_3d_route_glide` `97.5`) ([posthoc_semantic_qa_report.json](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/BCI_Shorts_Channel/projects/v8_ep09_maguire_london_taxi_hippocampus/05_assembly/posthoc_semantic_qa_report.json)) |
| **`prosody-qa` & `autopsy` & `verify`** | **PASS (`100.0`)** | `Siren` 음성 `83.10s` 무결 보존(`-14.4 LUFS`, `-1.7 dBTP`), 결함 `0건`, 아티팩트 `153/153` `100% INTACT` ([video_autopsy_report.json](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/BCI_Shorts_Channel/projects/v8_ep09_maguire_london_taxi_hippocampus/05_assembly/video_autopsy_report.json)) |
| **YouTube Studio 예약 교체 (`R75`)** | **PASS** | 신규 `YGKTFbKsFH8` (`2026-11-16 19:30 ET` Scheduled, `-> p4ou90cHt50` 연결 완료), 구 `7lKtSWvTmpw` 영구 삭제, 채널 내 `Private = 0` ([upload_receipt.json](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/BCI_Shorts_Channel/projects/v8_ep09_maguire_london_taxi_hippocampus/06_publish/upload_receipt.json), [related_video_receipt.json](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/BCI_Shorts_Channel/projects/v8_ep09_maguire_london_taxi_hippocampus/06_publish/related_video_receipt.json)) |

---

## 3. 영구 파이프라인 업그레이드 반영 내역 (`Rule R80` — `Ep #10 ~ #39` 자동 적용)

- **Gear 1 (리서치 원천 해상도 강제화)**: [research_dossier.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/research_dossier.py), [enrich_r80_spatial_contrast_30.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/scripts/enrich_r80_spatial_contrast_30.py), [build_golden_slate_and_verify_30.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/scripts/build_golden_slate_and_verify_30.py), [weekly_topic_research_runner.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/scripts/weekly_topic_research_runner.py)에 `03_visual_reference.json["spatial_contrast_spec"]` (`landmark_or_object_a/b` + `arrow_3d_mode`) 스키마 및 Gate 5 자동 검증 탑재, **30편 골든 큐 전수 주입 완료 (`30/30 ready=True`)**.
- **Gear 2–3 (3D 입체 화살표 가이드 & `RQ-Arrow` 검수기)**: [spatial_arrow_guide.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/spatial_arrow_guide.py), [real_world_reference_builder.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/real_world_reference_builder.py), [depiction_rules.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/depiction_rules.py), [flow_prompt_builder.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/flow_prompt_builder.py)에 `spatial_3d_arrow_diorama`, `drone_landmark_ascend`, `topdown_3d_route_glide` 및 OpenCV 굴곡도(`tortuosity`) 검증 탑재.
- **Gear 4 (`@RicksClips3000` 고속 서브문장 릴레이 어셈블러)**: [diorama_assembler.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/diorama_assembler.py), [dynamic_episode_qa.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/dynamic_episode_qa.py), [prompt_quality_v5.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/prompt_quality_v5.py), [video_autopsy.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/video_autopsy.py)에 `2.20s` 공간 릴레이 컷 바닥값 및 `1.24x~1.42x` 탄도 스피드램프 자동 적용 완료 (`@Operator`, `@Topic_Radar` 동기화 완료).
