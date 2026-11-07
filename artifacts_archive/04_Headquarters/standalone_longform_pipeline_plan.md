# 독립 `16:9` (`1920x1080` 1080p) 롱폼 파이프라인 & 1호 테스트 영상(`수면`) 구현 명세서

## 목표 및 핵심 원칙 (Confirmed Specification)

현재 안정화된 `9:16` 쇼츠 파이프라인(`BCI_Shorts_Channel/projects/`, `diorama_*` 모듈)은 **단 한 줄의 회귀 변경도 없이 100% 보존**하면서, 쇼츠와 완전히 분리된 **`16:9` (`1920x1080 @ 24fps` Full HD) 롱폼 다큐멘터리 파이프라인**을 구축·검증하고 1호 **`수면 (Sleepless Night)`** 테스트 영상을 제작합니다.

1. **불필요한 4K 업스케일 제거 → 네이티브 `1920x1080` (`1080p`) 고정**:
   - Google Flow 원천 클립(`720p~1080p`)을 억지로 `3840x2160` 4K로 뻥튀기하지 않고 **`1920x1080 @ 24fps` (`H.264 High -level:v 4.2 -crf 18`)**로 렌더링하여 **인코딩 시간 및 CPU 부하 `1/4` 단축, 로컬 SSD/캐시 용량 `1/4` 절감**.
2. **표준 3단 기획 공식 (`5대 일상 문제 × 심리학 행동 실험 × 최신 뇌과학 결과`) + 레이더 확장**:
   - 쇼츠 오디션 승격제에만 의존하지 않고 **①수면 · ②습관(미루기) · ③기억력(집중력) · ④불안(불확실성) · ⑤인간관계(애착/거절 통증)** 5대 일상 문제에 **심리학 행동 연구**와 **최신 뇌과학 스캔·수치 결과**를 결합([news_radar.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/news_radar.py) 5대 일상 학술 도메인 확장).
3. **하이브리드 시각 재연 (`Track A 실제 학술 실험 영상 재연` + `Track B 자체 1920x1080 마스터 앵커`)**:
   - 공개된 심리·대학 실험 아카이브 영상이 있는 파트는 **`Track A (R67)`** 비식별 포슬린 구도 변환 적용(원본 픽셀 재사용 `0%`).
   - 일상 공감 장면(침실·책상) 및 3D 뇌 회로 파트는 **`Track B (R66-Anchor)`** `1920x1080` Flow `0-credit` 마스터 캐릭터/공간/3D 뇌 레퍼런스 이미지를 고정 부착.
4. **대본 문장 호흡(`<= 13단어`) · 말속도(`emma_v7` + `dynamic_us_v7`) · 하드번 자막 100% 유지**:
   - 문장당 말속도(`~160 WPM`)와 문장 간격(`0.03s/0.075s/0.18s`)은 파일럿 쇼츠와 동일하게 유지하고, **챕터 전환 경계에만 `0.70s` 호흡 + 스테레오 오케스트라 스웰** 삽입(`-14.0 LUFS`).
   - 하단 중앙 하드번 자막(`Y ∈ [922, 982]`) + 좌하단 `DOI` 논문 카드(`Y ∈ [735, 872]`, **최소 `+50px` 수직 간격**) 동시 적용(유튜브 영어 `.srt` CC 중복 업로드는 기본 OFF), 엔딩 및 고정댓글에 **댓글 설전 `3단 점화`** 탑재.

---

## `1920x1080` (`16:9` Full HD) 자막·인포그래픽 무중첩 좌표 규격

| 화면 요소 (`PlayResX=1920, PlayResY=1080`) | `1920x1080` 규격 | 겹침 방지 보장 |
| :--- | :--- | :--- |
| **하단 하드번 자막 (`Default`, Layer 2)** | `AAB Condensed Black`, `fs=58`, 하단 중앙 **`Y ∈ [922, 982]`** (`MarginV=98`), 최대 **`5단어 / 32자`** (`Outline=3.5`, `Shadow=1.0`) | 상·중단 **`85.4%` (`Y=0..921`) 완전 개방** + 재생바 회피 |
| **좌하단 논문·연도 카드 (`DocCitationCard`, Layers 0~2)** | 논문 첫 언급 시 `5.0초`간 표시 (`X=96`, **`Y ∈ [735, 872]`**, 다크 반투명 슬레이트 + 좌측 `4px` 골드 바, `PIL` 텍스트 폭 동적 측정 `340..660px`) | 카드 하단(`Y=872`)과 하드번 자막 상단(`Y=922`) 사이에 **항상 최소 `+50px` 수직 여유 공간** 확보 |
| **챕터/해부학 상단 타이틀 (`ChapterHeadline` / `AnatomyLabel`)** | 상단 중앙 `Y ∈ [78, 180]` (`CHAPTER 1 · ...` 3초 표시, `t=0.0s` 암전 없이 즉시 밝은 화면 시작) | 상단 영역 전용 분리 |
| **좌우 비교 컷 (`SplitLeft` / `SplitRight`)** | `960x1080` + `960x1080` `hstack`, 중앙 `3px` 화이트 분리선 + 좌(`X=480`)·우(`X=1440`) 상단 라벨 | 좌·우 반쪽 정중앙 정렬 |
| **커스텀 썸네일 (`thumbnail_var_A/B/C.jpg`)** | 네이티브 `1920x1080` JPEG (`<= 1.95 MB`, 인물 머리 가림 감점 반영) | 별도 다운스케일 불필요 |

---

## 1호 테스트 영상 (`longform_01_glymphatic_sleep_toxins` — `수면`) 7-Chapter 구성

- **일상 문제**: 피곤한데 침대에 누우면 각성되고 새벽 3시에 깨는 불면 / 빠른 기절을 위한 수면제 의존
- **심리학 연구**: 침대를 각성·걱정 공간으로 연합 학습하는 **조건화 각성(Conditioned Arousal) 행동불면증 연구** 및 수면 박탈 시 편도체 감정 과민(`+60%`) 행동 실험
- **최신 뇌과학 결과**: 로체스터대 글림프 수로 `60%` 확장(`Science`, `10.1126/science.1241224`) + 보스턴대 인간 서파수면 뇌척수액 파동 MRI 데모(`Science`, `10.1126/science.aax5440`, `Track A` 시연 구도 참조 가능) + 진정제/수면제가 노르에피네프린 혈관 펌프 진동을 둔화시켜 세척 효율을 떨어뜨리는 최신 뇌과학 역설(`Cell` / `Science`)
- **댓글 설전 3단 점화**: *"수면제로 기절한 8시간 vs 자연 서파수면 5시간"* 양자택일 판결 엔딩 + 고정댓글 첫 `45자` `15°~30°` 비껴간 1인칭 베팅(`"Hot take: I'd take 5 natural hours over 8 on sleeping pills..."`)

---

## 구현 모듈 (`BCI_Shorts_Channel/projects_longform/` 완전 격리)

1. **[MODIFY] [config.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/config.py)** — 쇼츠 상수 무변경, `LONGFORM_VIDEO_WIDTH = 1920`, `LONGFORM_VIDEO_HEIGHT = 1080`, `LONGFORM_PROJECTS_DIR`, `LONGFORM_SUBTITLE_*` 등 설정.
2. **[MODIFY] [news_radar.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/news_radar.py)** — 기존 BCI 하드웨어 외 5대 일상 도메인(`sleep`, `habits`, `memory`, `anxiety`, `relationships`) 심리학·뇌과학 최신 논문 레이더 쿼리 및 롱폼 후보 태깅 확장.
3. **[MODIFY] [longform_prompt_builder.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/longform_prompt_builder.py) & [NEW] [longform_qa.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/longform_qa.py)** — 7챕터 스크립트·`16:9` 멀티앵글 플랜·`citation_cards` 합성 및 `LFQ1–LFQ12` 검증(시계 숫자 소품 자동 정화 포함).
4. **[NEW] [longform_refs.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/longform_refs.py) & [NEW] [longform_flow_worker.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/longform_flow_worker.py)** — 하이브리드 `Track A`(`R67` 학술 데모 구도 변환) + `Track B`(`1920x1080` `0-credit` Flow `Image` 마스터/공간/3D 뇌 앵커) 생성(`Q1–Q10`) 및 챕터 샤드(`<= 14클립`) `16:9` 비디오 생성(`w > h` CV 게이트).
5. **[NEW] [longform_audio.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/longform_audio.py), [NEW] [longform_subtitles.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/longform_subtitles.py), [MODIFY] [longform_assembler.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/longform_assembler.py)** — `emma_v7` + `dynamic_us_v7` 오디오(챕터 경계 `0.70s` 호흡 + 스웰, `-14.0 LUFS`), `1920x1080` ASS 하드번 자막 + 좌하단 `DOI` 카드, `H.264 High -level:v 4.2 -crf 18 stitchable=1` 병렬 인코딩 및 무손실 `concat` 조립(`05_assembly/final_longform_1920x1080.mp4`).
6. **[NEW] [longform_publish.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/longform_publish.py), [MODIFY] [cli.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/cli.py), [NEW] `tests/test_standalone_longform_pipeline.py`** — `1920x1080` `< 2 MB` 썸네일 3종, 챕터 타임스탬프·논쟁 고정댓글 패키지, CLI 등록 및 통합 테스트·무회귀 검증.
