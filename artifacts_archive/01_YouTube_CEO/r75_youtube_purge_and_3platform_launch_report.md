# ALL ABOUT BRAIN — YouTube `Rule R75` 완전 정화 & 3대 플랫폼 공식 런칭 검증 리포트

> [!IMPORTANT]
> **전체 집행 완료 요약 (`3/3` 완료 · `450/450` 테스트 통과)**: YouTube Studio의 7개 플레이리스트 전량 영구 삭제(`0`개 잔존), 채널 키워드·업로드 기본값(제목·설명·태그) 3중 BCI 오염 완전 제거, 예약 대기작(`Ep #5`·`Ep #6`) 선제 태그 치료, 셀프 조회(`AVD 0.0s`)·즉시 공개·메타데이터 리셋 등 잠복 버그 10종 차단 코드 게이트(`Rule R75`), 그리고 **Instagram(`@allaboutbrain.official`)·TikTok(`@allaboutbrain_official`)** 공식 채널 개설 및 첫 영상 라이브 발행이 모두 완료되었습니다.

---

## 1. YouTube Studio 라이브 정화 시각 증빙 (`@AllAboutBrainOfficial`)

````carousel
![YouTube 플레이리스트 7개 전량 삭제 완료 (0개 잔존 검증)](./studio_playlists_purged_zero_verified.png)
<!-- slide -->
![채널 키워드 정화 및 업로드 기본 설명란·태그 완전 공란 초기화 검증](./studio_settings_clean_keywords_and_empty_default_tags.png)
````

### 라이브 정화 영수증 요약
- **플레이리스트 전량 삭제 ([studio_playlist_purge_receipt.json](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/reports/studio_playlist_purge_receipt.json))**: 기존 7개 플레이리스트(`PLdVmLC3K7dmw`, `PLN2i7Lujhi8o`, `PLQXDT6yxpDUs`, `PLFIUNiVpBYXs`, `PLKksDVOhsrZs`, `PLT4Q_0if7p14`, `PLNC9nLt0H3S0`) 전량 영구 삭제 → `/content/playlists` 재로드 시 **`remaining_count == 0`** 확인 + 코드베이스 내 자동 생성 영구 봉쇄(`STUDIO_PLAYLISTS_ENABLED = False`).
- **채널 & 업로드 기본값 완전 정화 ([uploader.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/studio/uploader.py))**:
  - `Channel -> Keywords`: 하드웨어 칩(`BCI`, `AI`, `Neuralink`, `EEG` 등) 전량 제거 → 대중 심리·뇌과학 15개 키워드(`psychology`, `neuroscience`, `human behavior`, `everyday psychology`, `habits`, `self control`, `memory`, `sleep science` 등) 적용.
  - `Upload defaults`: 기본 `Title = ""` 공란, 기본 `Description = ""` 공란(`"Brain-Computer Interfaces"` 구문구까지 완전 삭제), 기본 `Tags = []` (`0/500` 공란), 기본 `Category = Education`, 언어 `en-US` 잠금.
- **기예약·기발행 영상 라이브 태그 치료 ([studio_r75_video_tag_purification_receipt.json](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/reports/studio_r75_video_tag_purification_receipt.json))**:
  - **`Ep #5` (`ut1wde0d19o`, 11/12 19:30 ET 예약)**: `BCI/AI/neurotech` 제거 → `["psychology", "neuroscience", "human behavior", "brain science", "cerebellum", "sensory prediction", "everyday psychology", "cognitive psychology", "brain facts", "shorts"]` + `Education` + `#shorts` 저장 및 재로드 검증.
  - **`Ep #6` (`sjMteEvcjD0`, 11/13 19:30 ET 예약)**: 오염 태그 제거 → `["psychology", "neuroscience", "human behavior", "brain science", "sleep science", "insomnia", "hippocampus", "prefrontal cortex", "memory", "shorts"]` + `Education` + `#shorts` 저장 및 재로드 검증.
  - **`v8_pilot_03` (`soUNqH7UyKw`, 공개 24h 경과)**: 오염 태그 제거 → `["psychology", "neuroscience", "human behavior", "brain science", "habits", "self control", "willpower", "prefrontal cortex", "decision making", "shorts"]` + `Education` + `#shorts` 저장 및 재로드 검증.
  - **`Ep #4` (`7W8zIOMKPrQ`, 초기 24h 시드 진행 중)**: 시드 인덱스 리셋 방지를 위해 Studio 미접촉 보호 유지.

---

## 2. 코드베이스 잠복(Latent) 버그 선제 차단 게이트 (`Rule R75` · `450/450` 통과)

| 방어 계층 | 핵심 수정 모듈 | 적용된 원천 차단 불변식 (Invariant) |
|---|---|---|
| **플레이리스트 부활 금지** | [studio/config.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/studio/config.py), [short_linker.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/studio/short_linker.py), [studio_watchdog.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/studio/studio_watchdog.py), [reporter.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/studio/reporter.py) | `STUDIO_PLAYLISTS_ENABLED = False`, `_assign_pillar_playlist_on_edit_page` 하드 비활성화, 워치독/큐/CLI 기본값 `False`, 일일 리포트 미배정 경고 제거 |
| **태그 생성 & 하드웨어 오염 차단** | [publish.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/publish.py), [diorama_batch_orchestrator.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/diorama_batch_orchestrator.py), [uploader.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/studio/uploader.py) | 에피소드별 `8~12`개 맞춤 심리/뇌과학 태그 + `#shorts` 자동 생성, 비-BCI 에피소드에 `BANNED_OFF_TOPIC_TECH_TAGS` 혼입 시 즉시 `ValueError`, 업로드 시 `#tags-container` 클리어 후 DOM 역검증 |
| **셀프 조회 (`AVD 0.0s`) 봉쇄** | [community.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/studio/community.py), [studio_watchdog.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/studio/studio_watchdog.py), [studio_batch_100_scheduler.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/studio_batch_100_scheduler.py), [reporter.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/studio/reporter.py) | 비공개·예약 영상 핀 차단, 공개 후 유기 조회수 `>=100회`(또는 `>=12h`) 전 `DEFERRED_SEED_PROTECT`, `Page.addScriptToEvaluateOnNewDocument`로 `0.000s` 자동재생 강제 차단, 리포터 `watch?v=` 폴백 비활성화 |
| **인덱싱 워밍업 & 동결 잠금** | [uploader.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/studio/uploader.py), [short_linker.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/studio/short_linker.py), [sanitize_scheduled_metadata.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/studio/sanitize_scheduled_metadata.py), [unschedule_retired_shorts.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/studio/unschedule_retired_shorts.py) | 즉시 `Public` 업로드 금지(`>= 3.0h` 워밍업 예약 필수), 공개 전 `3h` ~ 공개 후 `24h` 메타데이터 동결, `Public -> Unlisted` 역전 금지, 기본 pillar 폴백 `"brain_mysteries"` |
| **`<= 88s` 고속 시드 규격** | [pipeline/config.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/config.py), [qa_gates.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/qa_gates.py), [test_studio_seed_hygiene_and_playlist_ban.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/tests/test_studio_seed_hygiene_and_playlist_ban.py) | 신작(`Ep #7+`) `62.0–86.0s` (`<= 88.0s`) 목표 고정 (기제작 `v8_pilot_01..ep06` grandfather 유지), 전체 회귀 테스트 **`450 passed, 0 failed`** |

---

## 3. 3대 플랫폼 동시 운영 체제 개통 현황

````carousel
![Instagram @allaboutbrain.official 프로필 그리드 & 4:5 R65 v4 커버 라이브](./ig_profile_grid_after_upload.png)
<!-- slide -->
![TikTok @allaboutbrain_official 프로필 & 첫 영상 라이브](./tiktok_first_video_live_verified.png)
````

| 플랫폼 | 공식 채널 핸들 & URL | 첫 발행 라이브 영상 (`v8_pilot_03` 마시멜로 신뢰 실험) | 자동화 모듈 |
|---|---|---|---|
| **YouTube Shorts** | [`@AllAboutBrainOfficial`](https://www.youtube.com/@AllAboutBrainOfficial) | https://www.youtube.com/shorts/soUNqH7UyKw *(태그 정화 완료; `Ep #5·#6` 클린 예약 대기 중, `Ep #7` `78.47s` 렌더링 후 `11/14 19:30 ET` 자동 배치)* | [uploader.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/studio/uploader.py) |
| **Instagram Reels** | [`@allaboutbrain.official`](https://www.instagram.com/allaboutbrain.official/) | https://www.instagram.com/reel/DfoWJrQgjfF/ | [instagram_uploader.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/studio/instagram_uploader.py) |
| **TikTok** | [`@allaboutbrain_official`](https://www.tiktok.com/@allaboutbrain_official) | https://www.tiktok.com/@allaboutbrain_official/video/7707163226252922120 | [tiktok_uploader.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/studio/tiktok_uploader.py) |
