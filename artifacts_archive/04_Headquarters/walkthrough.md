# ALL ABOUT BRAIN 마스터 파이프라인 업그레이드 & 1호 재현 테스트 영상 완결 보고서 (`Walkthrough`)

## 1. 업그레이드 전 GitHub 안전 백업 완료

코드 변경 착수 직전, 기존 워크스페이스 베이스라인을 GitHub 원격 저장소(`origin/main`)에 푸시하고 롤백 태그를 고정했습니다.

- **백업 커밋**: `3c53127` (`origin/main` 동기화 완료)
- **롤백 보존 태그**: `pre-master-upgrade-2026-11-02`

---

## 2. 완성된 1호 테스트 영상 (`reenact_01_ainsworth_strange_situation`)

*Mary Ainsworth — The Strange Situation (`QTsewNrHUHU`)* 원본 실험의 공간 구도·동선·편집 비트를 소스로 재현하되, 저작권 포스터·실사 인물을 100% 제거한 하이키 포슬린(`porcelain_cinematic_v7`, `R66`/`R67`) 비주얼과 봉입형 4색 3D 뇌 메커니즘(`23.4%`), 그리고 현행 오디오 파이프라인 내 미국 여성 다큐 내레이터(`emma_v7`)를 결합해 완성했습니다.

- **최종 완성 본편 MP4**: [final_shorts_1080x1920.mp4](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/BCI_Shorts_Channel/projects/reenact_01_ainsworth_strange_situation/05_assembly/final_shorts_1080x1920.mp4)
  - **해상도 / 프레임 / 용량**: `1080×1920` (`9:16`), `24 fps`, `147.25초` (`2분 27초`), `109.02 MB`
  - **음성 및 운율**: `emma_v7` (`en-US-EmmaMultilingualNeural`, `+0Hz`, 여성 스튜디오 전용 EQ 적용) + 미국 `45세+` 청취 최적화 운율 `dynamic_us_v7` (`LUFS -15.6`, `True Peak -3.3 dBTP`, WSOLA `0건`)
  - **비주얼 생성**: Google Flow `0-credit` (`Veo 3.1 - Lite [Lower Priority]` 64클립 + `Nano Banana 2.1` `0-credit` `x4` 배치 이미지 QA 선별)
- **마스터 오디오 / 메타데이터 / 썸네일**:
  - 오디오 트랙: [audio_master.wav](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/BCI_Shorts_Channel/projects/reenact_01_ainsworth_strange_situation/04_audio/audio_master.wav) · 성우 리포트: [voice_report.json](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/BCI_Shorts_Channel/projects/reenact_01_ainsworth_strange_situation/04_audio/voice_report.json)
  - 퍼블리시 패키지: [metadata.json](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/BCI_Shorts_Channel/projects/reenact_01_ainsworth_strange_situation/06_publish/metadata.json) · [thumbnail_contact_sheet.png](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/BCI_Shorts_Channel/projects/reenact_01_ainsworth_strange_situation/06_publish/thumbnail_contact_sheet.png)

````carousel
![완성 본편 실험실 재현 프레임 — 어머니 퇴장·낯선 사람 착석·아기 블록 놀이 구도 및 포스터 완전 제거](./frame_preview_A.png)
<!-- slide -->
![R64 컷별 명확도 검증 시트 01/11 — 3문장 콜드오픈(QUIET MYTH? → SILENT PANIC) 및 회전형 S3 스탬프](./sheet_01.jpg)
<!-- slide -->
![R64 컷별 명확도 검증 시트 08/11 — 회피 애착 좌우 분할(OUTSIDE: SILENT vs INSIDE: RACING) 및 봉입형 3D 뇌 해부 배지](./sheet_08.jpg)
<!-- slide -->
![R65 썸네일 스튜디오 A/B/C 시안 — SILENT PANIC (WCAG 대비 15.15~15.36 통과)](./thumbnail_contact_sheet.png)
<!-- slide -->
![R67 공간 구도 가이드 vs 9:16 하이키 포슬린 레퍼런스 변환 대조표 (원본 픽셀 0% 보존)](./reenactment_comparison_sheet.png)
````

---

## 3. 마스터 파이프라인 주요 구현 내역 (전 모듈 단일 방향 통합)

1. **Google Flow 내장 `0-Credit` 일원화 및 최대 효율(`x4`) 배치 엔진**
   - [flow_ingredients.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/flow_ingredients.py), [source_reenactment.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/source_reenactment.py), [flow_diorama_sharded_worker.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/flow_diorama_sharded_worker.py):
     - 외부 탭 전환 없이 Google Flow `Image` 모드(`Nano Banana 2.1`, `0 credits`)에서 **1회 `x4`장 동시 무료 생성 후 `Q1~Q7` 및 `dHash >= 18` 최고점 시안을 자동 채택**하도록 기본값(`--backend flow`) 고정 (`0 credits` 미확인 시 즉시 중단되는 Fail-Closed 보호).
     - `0-credit` 영상(`Veo 3.1 - Lite [Lower Priority]`) 다중 출력 시 가상 스크롤(Virtual Scroll) 타일 증발이 발생하지 않도록 탭당 샤드 크기를 출력 배수에 반비례해 자동 조절.
2. **원본 소스 조건화 1:1 포슬린 재현 엔진 (`Rule R67`)**
   - [source_reenactment.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/source_reenactment.py) & [reference_image_qa.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/reference_image_qa.py): `/tmp/aab_reenact` 격리 추출 → 저작권 포스터·피부 OpenCV 마스킹 및 `4:3 → 9:16` 확장 → Google Flow `0-credit` 포슬린 레퍼런스 생성 → `~78%` 실험 동선 + `>= 20%` 봉입형 4색 입체 뇌 인터컷 → 임시 폴더 완전 삭제 및 `RQ1~RQ5` 비침해 검증. (`Q2/Q4/Q6` 포슬린 호환 보정 완료).
3. **현행 음성 파이프라인 내 성우 프리셋 스위칭 (`DIORAMA_VOICE_PRESETS`)**
   - [config.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/config.py), [voice_fallback.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/voice_fallback.py), [qa_gates.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/qa_gates.py), [diorama_assembler.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/diorama_assembler.py), [diorama_batch_orchestrator.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/diorama_batch_orchestrator.py), [diorama_pipeline_runner.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/diorama_pipeline_runner.py):
     - 기존 6단계 스튜디오 마스터링 체인은 100% 보존하면서 `andrew_v7`(기본), **`emma_v7`**(여성 학술 내레이터), **`ava_v7`**(여성 스토리텔러), `aria_v7`, `christopher_v7` 스위칭 완비 (`+0Hz` 삭제 버그, 여성 전용 EQ 분리, Kokoro 여성 폴백 매핑 모두 해결).
4. **미국 성공 공식 전면 적용 (YPP `Anti-Clone`, 미국 `45+` 운율, 65편 큐 포슬린 전환 & 7대 필러 리밸런싱, 4K 롱폼, 스튜디오 워치독, 브레이킹 뉴스)**
   - [migrate_dossiers_porcelain_v7.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/scripts/migrate_dossiers_porcelain_v7.py): 대기 중인 미공개 **65편 전수**를 `diorama_v7_porcelain`으로 변환, 상투구 5종 회전 교체, 도시에 실제 인용문·사실 기반 고유 설명란 생성, 7대 필러 균형 큐([porcelain_rebalanced_queue.json](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/BCI_Shorts_Channel/porcelain_rebalanced_queue.json)) 재배열 완료.
   - [longform_assembler.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/longform_assembler.py) & [thumbnail_studio.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/thumbnail_studio.py): `main.py longform-assemble`을 통한 `3840×2160` (`16:9` 4K, `-14.0 LUFS`, `tpad` 오디오 잘림 방지) 조립 및 4K `A/B/C` 썸네일 생성 검증 완료.
   - [reporter.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/studio/reporter.py), [short_linker.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/studio/short_linker.py), [community.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/studio/community.py), [studio_watchdog.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/studio/studio_watchdog.py), [sanitize_scheduled_metadata.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/studio/sanitize_scheduled_metadata.py), [us_diorama_timetable.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/studio/us_diorama_timetable.py), [news_radar.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/news_radar.py) 및 마스터 규격 문서([AGENTS.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/AGENTS.md), [production_constants.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/production_constants.md), [neuro_diorama_rules.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/neuro_diorama_rules.md), [youtube_studio_operations.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/youtube_studio_operations.md)) 1:1 정합화 완료.

---

## 4. 전사 검증 기록 (불일치 `0`건)

| 검증 항목 | 실행 명령 / 대상 | 결과 |
|---|---|---|
| **전체 파이썬 구문 컴파일** | `pipeline/`, `scripts/`, `main.py` 총 `64`개 모듈 | **`64 / 64` 에러 `0`건** |
| **1호 파일럿 9중 QA 게이트** | `verify`, `prompt-gate`, `reenact-qa` (`RQ1~5`), `prosody-qa` (`P1~10`), `ref-qa`, `episode-qa` (`DQ1~12`), `posthoc-qa` (`61/61`컷), `autopsy`, `qa` | **`9 / 9` 전수 PASS** (`Autopsy 100.0`, `/tmp/aab_reenact` 완전 삭제 확인) |
| **미공개 대기 큐 65편 일관성** | `porcelain_rebalanced_queue.json` 전수 `prompt-gate` & 제목·인용문 검증 | **`65 / 65` (`100%`) PASS** (`issues: 0`) |
| **16:9 4K 롱폼 E2E 조립** | `cmd_longform_assemble` (`3840×2160 @ 24fps` MP4 + 4K 썸네일 3종) | **PASS** |
| **전체 회귀 유닛 테스트 스위트** | `pytest tests -q` (신규 회귀 테스트 [test_master_upgrade_review_fixes.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/tests/test_master_upgrade_review_fixes.py) 포함) | **`211 passed` (`exit 0`)** |

> [!NOTE]
> 기존 예약된 YouTube Studio 라이브 방송에 영향을 주지 않기 위해(`R34` 보호), `studio-watchdog --apply`와 `sanitize_scheduled_metadata.py --apply`는 Dry-Run 및 모의 테스트까지만 수행하고 실제 Studio 클릭 반영은 대표님 지시 전 대기 상태로 두었습니다.


---

## 5. CEO 피드백 반영 2차 업그레이드: 장면 호흡 개편 · 필러 제거 · 공간 연속성 완결 (`v2`)

대표님께서 검수 후 짚어주신 3가지 사항(① 빠른 화면 전환 완화, ② 30초 스톱워치 등 불필요한 필러 제거, ③ 착석 상태에서 또 문을 열고 들어오는 인물 복제 오류 해결)을 파이프라인 전역 규칙과 테스트 영상에 반영 완료했습니다.

### Before vs After 핵심 수치 비교 (`reenact_01_ainsworth_strange_situation`)

| 항목 | 1차 빌드 (`Before`) | **2차 수정 완성본 (`After`)** |
|---|---|---|
| **성우 및 발화 속도** | `emma_v7` + `dynamic_us_v7` (`147.25s`) | **`100% 동일 보존` (SHA-256 일치, `147.25s`)** |
| **총 컷 수 / 평균 길이** | `63컷` / 평균 `2.34초` | **`33컷` / 평균 `4.46초` (`50%` 안정화)** |
| **최단 컷 / 최장 롱테이크** | 최단 **`0.67초`** 플래시 컷 10개 | 최단 **`2.21초`** ~ 최장 **`6.88초`** (1.8초 미만 플래시 컷 `0건`) |
| **스톱워치·타이머·인형의 집 필러** | `13컷` 삽입 (`0.67s` 초시계 등) | **`0컷` (전량 실제 실험실·뇌 메커니즘 본 장면으로 대체)** |
| **중복 입장·유령 인물·잔상 결함** | `Cut #07`, `#15` 중복 입장 등 다수 | **`33/33` 전 컷 고해상도 육안 검수 결함 `0건`** |
| **`OUTSIDE: SILENT` 좌우 비교 컷** | 좌측 클립 오바인딩 + `0.83초` 스침 | **좌(조용한 아기) / 우(붉은 편도체 경보) 정확 매칭 + `2.46초` 풀 유지** |
| **최상단 바로보기 파일** | 구버전 (`109.02 MB`) | **[reenact_01_strange_situation_test_1080x1920.mp4](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/reenact_01_strange_situation_test_1080x1920.mp4) (`89.11 MB` 교체 완료)** |

````carousel
![2차 리빌드 검증 시트 01/06 — 2.38s~6.41s 여유 있는 도입부 및 빈 방에서 시작하는 엄마·아기 첫 입장(Cut #05, 중복 인물 0건)](./rebuilt_sheet_01.jpg)
<!-- slide -->
![2차 리빌드 검증 시트 02/06 — 빈 좌측 의자 상태에서 시작하는 낯선 사람 입장(Cut #09) 및 스톱워치 없이 이어지는 엄마 퇴장·혼자 남은 아기(Cut #10~#11)](./rebuilt_sheet_02.jpg)
<!-- slide -->
![2차 리빌드 검증 시트 03/06 — 30초 대사 구간에서도 스톱워치 대신 문이 열리며 아기가 엄마에게 달려가는 실제 재결합 롱테이크(Cut #13~#14) 유지](./rebuilt_sheet_03.jpg)
<!-- slide -->
![2차 리빌드 검증 시트 04/06 — 1993년 심전도 실험실 6.71s 롱테이크(Cut #21) 및 정확히 복원된 OUTSIDE: SILENT vs INSIDE: RACING 좌우 분할(Cut #24)](./rebuilt_sheet_04.jpg)
````

### 향후 모든 영상 생성에 영구 적용된 파이프라인 방어벽
1. **시네마틱 호흡 상수 및 `split_hstack` 수정** ([config.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/config.py), [diorama_assembler.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/diorama_assembler.py)): 기본 클립 수를 `32~36개` 시네마틱 호흡으로 전환하고(Google Flow 생성 시간도 50% 단축), 강제 플래시 컷 절단 루프 제거 및 `left_clip_index` 바인딩 복원.
2. **일상 시간·횟수 비유 면제 & 시계류 필러 차단 게이트** ([plain_language.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/plain_language.py), [prompt_quality_v5.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/prompt_quality_v5.py)): `30초`, `20분`, `9피트` 등 직관적 단위의 억지 비유 의무를 해제하고, 스톱워치·모래시계·카운트다운 타이머 필러 컷을 사전 게이트에서 차단.
3. **공간·인물 상태 원장(`scene_state`) & Flow 레퍼런스 누락 원천 차단** ([prompt_quality_v5.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/prompt_quality_v5.py), [flow_diorama_sharded_worker.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/flow_diorama_sharded_worker.py), [depiction_rules.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/depiction_rules.py)): 클립 간 착석·입장·퇴장 인원 연속성을 사전 검증하고, Flow 에셋 서랍 스크롤로 레퍼런스 칩 첨부가 실패하면 즉시 재업로드(미첨부 채 텍스트 생성 금지)하도록 수정.
4. **전사 회귀 및 대기 큐 검증 완료**:
   - 미공개 대기 큐([porcelain_rebalanced_queue.json](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/BCI_Shorts_Channel/porcelain_rebalanced_queue.json)) **`65 / 65`편 전수** 새 호흡(`<= 42`클립) 및 타이머 필러 `0건` 정규화 통과 (`rebalance_porcelain_queue_pacing.py --check-only`: `failed=0`)
   - `reenact_01` 실행 게이트 **`11 / 11` 전수 PASS** + 전체 테스트 스위트 **`224 passed` (`exit 0`)**

---

## 6. 3차 스윗스팟 페이싱(`48`컷, 평균 `3.07초`) 멀티앵글 리빌드 & 전사 동기화 완료

CEO 피드백(*"기존 `63`컷은 너무 빠르고, `33`컷은 너무 지루함 — 두 지점의 적절한 중간점을 찾고 필요한 추가 컷만 생성"*)을 반영하여, **기존에 검증된 `34개` 클립과 `emma_v7` 오디오(`147.25s`)는 100% 그대로 재사용**하고, 정체 구간(`4.8~6.9초` 원테이크)을 쪼개는 **동일 공간 멀티앵글 커버리지 클립 `15개`만 `0-credit` Google Flow에서 추가 생성**하여 완성했습니다. (검수 중 미세 시각 결함이 발견된 4개 클립 `#04, #27, #31, #44`까지 선제 재생성·교체 완료)

### 1차(`63`컷) vs 2차(`33`컷) vs **3차 스윗스팟 완성본(`48`컷)** 비교

| 지표 | 1차 빌드 (초고속) | 2차 빌드 (롱테이크) | **3차 최종본 (스윗스팟 멀티앵글)** |
| :--- | :---: | :---: | :---: |
| **성우 및 발화 호흡** | `emma_v7` (`147.25s`) | `100% 동일` | **`100% 동일 보존` (SHA-256 일치)** |
| **총 컷 수 (`49`클립 기반)** | `63컷` | `33컷` | **`48컷` (정확히 중간 스윗스팟)** |
| **평균 컷 길이** | `2.34초` | `4.46초` | **`3.07초` (다큐멘터리 황금 리듬)** |
| **최단 ~ 최장 컷 범위** | `0.67초 ~ 4.83초` | `2.21초 ~ 6.88초` | **`2.17초 ~ 4.50초` (`5초` 이상 지루한 컷 `0건`, `1.8초` 미만 플래시 컷 `0건`)** |
| **스톱워치·타이머·모래시계 필러** | `13컷` | `0컷` | **`0컷` (전량 동일 공간 멀티앵글·실험 장면으로 구성)** |
| **시각·연속성·썸네일 결함** | 중복 입장·플래시 컷 | 지루한 고정 앵글 | **`48/48` 전 컷 육안 검수 결함 `0건` + 썸네일 인물 머리 가림 방지 적용** |
| **최상단 바로보기 파일** | 구버전 | `89.11 MB` | **[reenact_01_strange_situation_test_1080x1920.mp4](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/reenact_01_strange_situation_test_1080x1920.mp4) (`97.94 MB` 최신 교체)** |

````carousel
![3차 스윗스팟 시트 01/08 — 5.38~18.33s 구간을 동일 공간 4앵글(관찰부스 와이드 -> 연구노트 클로즈업 -> 블록 손 클로즈업 -> 놀이방 와이드)로 2.7~3.7초 리듬 전환](./sweetspot_sheet_01.jpg)
<!-- slide -->
![3차 스윗스팟 시트 03/08 — 엄마 퇴장 -> 연구원 관찰 -> 연구노트 POV -> 아기 손 클로즈업 -> 재결합(스톱워치 필러 0건, 중복 인물 0건)](./sweetspot_sheet_03.jpg)
<!-- slide -->
![3차 스윗스팟 시트 06/08 — 1993년 ECG 센서 부착 -> 침 코르티솔 피펫 채취 -> 놀이방 -> OUTSIDE SILENT / INSIDE RACING 분할 화면](./sweetspot_sheet_06.jpg)
<!-- slide -->
![3차 스윗스팟 시트 08/08 — 성인기 회피 은유 -> vmPFC 진정 회로 멀티앵글 -> 안전한 애착 결론 엔딩](./sweetspot_sheet_08.jpg)
<!-- slide -->
![R65 썸네일 스튜디오 — 상단 훅 텍스트 인물 머리 가림 방지 패널티 적용 후 선정된 VAR A / B / C](./sweetspot_thumbnail_contact_sheet.png)
````

### 향후 모든 에피소드에 영구 반영된 스윗스팟 규격
- **파이프라인 기본 호흡 동기화**: [config.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/config.py), [diorama_assembler.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/diorama_assembler.py), [research_dossier.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/research_dossier.py)의 `porcelain_cinematic_v7` 기본 규격을 **`48`클립 (`45~52`컷 범위, 컷당 `1.80s ~ 4.50s` 하드 클램프, 평균 `~3.0초`)**으로 고정.
- **변종 타이머·미니어처 필러 및 썸네일 머리 가림 차단**: [prompt_quality_v5.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/prompt_quality_v5.py)에서 `sandglass`, `wristwatch`, `desk clock`, `diorama` 등 변종 필러 토큰 207건을 전수 차단하고, [thumbnail_studio.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/thumbnail_studio.py)에 상단 타이틀 영역 인물 머리 가림 자동 감점 로직 추가.
- **미공개 `65/65` 대기 큐 및 프로젝트 폴더 전수 동기화**: [porcelain_rebalanced_queue.json](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/BCI_Shorts_Channel/porcelain_rebalanced_queue.json) 내 65개 도시에 초안 및 미제작 `projects/diorama_27..91` 폴더 전수 `48~49`클립 멀티앵글 규격 동기화 완료 (`failed=0`), 전체 테스트 **`230 passed`**.

---

## 7. 독립 `16:9` (`1920x1080`) 롱폼 파이프라인 완공 & 1호 `수면` (`8분 35초`) 테스트 영상 납품

쇼츠 파이프라인(`BCI_Shorts_Channel/projects/`, `diorama_*`)과 **100% 분리된 독립 `16:9` (`1920x1080 @ 24fps`) 롱폼 파이프라인**([longform_prompt_builder.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/longform_prompt_builder.py), [longform_refs.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/longform_refs.py), [longform_flow_worker.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/longform_flow_worker.py), [longform_audio.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/longform_audio.py), [longform_subtitles.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/longform_subtitles.py), [longform_assembler.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/longform_assembler.py), [longform_qa.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/longform_qa.py), [longform_publish.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/longform_publish.py), [news_radar.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/news_radar.py))과 댓글 설전 `3단 점화`([community.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/studio/community.py)) 구축·검증을 완료하고, 1호 테스트 영상 **`수면 (Why 8 Hours on Sleeping Pills Leaves Your Brain Unwashed)`**을 완성했습니다.

### 최종 검증 지표 (`LFQ1–LFQ12` `0 issues` + `96/96` 전 클립 육안 검수 완료)
- **최상단 바로보기 파일**: **[longform_01_sleep_test_1920x1080.mp4](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/longform_01_sleep_test_1920x1080.mp4)** (`394.8 MB`, `1920x1080 @ 24.0fps`, `514.92초` / **`8분 35초`**, SHA-256 `e06611f0d195ec09182f87d16f6760044eeffbd6c27196a52b36cc61b3ea496c`)
- **오디오·문장·컷 호흡 반영**: `emma_v7` + `longform_us_v7` 다큐멘터리 여유 보이스(`149.57 WPM`, `-14.1 LUFS`, 문장·단락·챕터 자연 호흡 + 챕터 전환 오케스트라 스웰), 최대 `20단어` 다큐 서술형 문장(`84문장`), `96개` 고유 `16:9` 클립(`평균 5.36초`, `88/88` 레퍼런스 앵커 Fail-Closed 고정)
- **3단 기획(`일상 불면 × 심리학 연구 × 최신 뇌과학 결과`) & 무중첩 자막/논문 카드**: 하단 하드번 자막(`320`개 이벤트)과 좌하단 `DOI` 학술 카드 `5종`(`1997 Perlis & Bootzin` 조건화 각성 · `2007 Yoo & Walker` 편도체 `+60%` · `2013 Xie & Nedergaard` 글림프 `+60%` · `2019 Fultz & Lewis` 인간 20초 뇌척수액 파동 · `2025 Cell Hauglund & Nedergaard` 수면제 혈관 펌프 둔화) 간 최소 `+54px` 이격 무중첩 및 말줄임(`…`) 잘림 `0건`
- **결함 적발 및 100% 수선 완료**: `Clip 060` `"Boston"` 텍스트 제거, `porcelain_hands_closeup` 알약(`capsule`) 클로즈업 7컷 재생성, `Clip 032` 이목구비 조형 검출 즉시 무표정 포슬린 재생성 + `YuNet` 얼굴 검출 게이트 탑재, 테스트 스위트 **`17/17` (`42/42` 통합) 통과**

````carousel
![7개 챕터 대표 프레임 스트립 — 침실 · 수면 캡슐 클로즈업 · MRI 실험실 · 4색 생체 발광 3D 뇌 일관성 및 상·하단 타이포그래피](./longform_01_chapters_strip.jpg)
<!-- slide -->
![좌하단 학술 DOI 인포그래픽 카드 5종 전수 검증 — 말줄임 잘림 0건 및 하단 하드번 자막과 +54px 무중첩 분리](./longform_01_citation_cards_strip.jpg)
<!-- slide -->
![1920x1080 커스텀 썸네일 VAR A (< 2MB, 피사체 비가림 여백 배치)](./longform_01_thumbnail_var_A.jpg)
<!-- slide -->
![Clip 032 외과적 재생성 검수 (f=2, f=95, f=184) — 100% 무표정 매트 화이트 포슬린 헤드 및 가디건 연속성 일치](./longform_01_clip_032_regen_check.jpg)
````
