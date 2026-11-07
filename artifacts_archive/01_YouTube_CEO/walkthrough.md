# ALL ABOUT BRAIN (`07_Youtube`) 전체 실행 및 라이브 검증 완료 보고 (`Walkthrough`)

> [!IMPORTANT]
> 요청하신 **10개 요구사항 전 항목**에 대해 코드 구현, 워크스페이스·클라우드 전체 클린업, 벤치마크/장면전환 포렌식 보고서 작성, 라이브 Chrome CDP(`:9222`) 무간섭 검증 및 전체 테스트 스위트(**`295 passed, 0 failed`**) 검증을 완료했습니다.

---

## 1. 핵심 산출물 문서 바로가기

- **벤치마크 역설계 · `@RicksClips3000` 제작 파이프라인 · `lnYLIWP2l-I` 장면 전환(`T01..T17`) 마스터 보고서**:
  - [benchmark_success_formula_report.md](./benchmark_success_formula_report.md)
- **전체 시스템 개편 설계서 (v2 Final)**:
  - [implementation_plan.md](./implementation_plan.md)

---

## 2. 영역별 실행 완료 내역 및 검증 결과

### 2.1 쇼츠 `1분 30초`(`~90s`) 기본값 · 롱폼 보류 · `<30분/편` 병목 제거
- [config.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/config.py) / [production_constants.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/production_constants.md):
  - 기본 듀레이션 티어를 `shorts_90s_v7`(`~90s` 타깃, `58~88s` 고지속률 구간 수용, `22~28` 클립 예산)로 전환.
  - `LONGFORM_DEFERRED = True` 설정 및 [cli.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/cli.py) 가드 적용(쇼츠 안착 전까지 `16:9` 롱폼 실행 차단, `--allow-deferred-longform`으로만 예외 허용).
- 속도 병목 해소:
  - [flow_diorama_sharded_worker.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/flow_diorama_sharded_worker.py): 탭 오픈 락(`2.5s`)과 레퍼런스 업로드 락을 분리하여 멀티 워커 직렬 대기 제거.
  - [storage.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/storage.py): Google Drive FUSE 재읽기 방지를 위한 영구 SHA-256 캐시(`8,192` 엔트리) 도입.
  - 무인 CV 게이트 자동 서명(`UNMANNED_QA_SIGNOFF_DEFAULT = True`)으로 수동 리뷰 대기 병목 제거.

### 2.2 월간/일간 크레딧 충전 자동 연동 Dual-Tier Flow (`--engine auto`)
- [`SharedOmniCreditBudget`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/flow_workspace.py#L140-L335) (`flow_credit_state.json`):
  - 크레딧 잔여 시 **`Omni 1.1 Flash`** 우선 사용 → 크레딧 소진(`0`) 시 결제 버튼(`Add AI credits`) 클릭 없이 즉시 **`0-credit` (`Veo 3.1 - Lite [Lower Priority]` + `Nano Banana 2.1` `x4`)** 모드로 자동 전환.
  - 새 월간 결제일 또는 일간 크레딧 리필 주기 도래 시 영구 잠금을 해제하고 자동으로 `Omni 1.1`을 재사용.

### 2.3 클린 슬레이트 전체 삭제 (로컬 워크스페이스 + `/tmp` + Google Flow 클라우드)
- **Google Flow 클라우드 (`https://flow.google.com/`) 라이브 삭제 완료**:
  - [`clean_flow_workspace_async`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/flow_workspace.py#L815-L1075) (`main.py flow-clean --all --include-speed-cache`) 라이브 실행 검증 완료.
  - 최종 대시보드 잔여 프로젝트 카드: **`remaining_dashboard_cards: 0`** (계정 내 잔여 에셋/클립 **`0건`**).
- **워크스페이스 & 임시 파일 삭제 완료**:
  - `07_Youtube` 전체에서 기존 제작 영상·오디오·임시 이미지(`5,600+`개 파일) 및 숨김 크래시 파일(`.tmp_*`) 전수 삭제: `.mp4`, `.mov`, `.mkv`, `.webm`, `.wav`, `.mp3`, `.f32`, `.npz`, `.jpg`, `.jpeg`, `.webp`, `.new`, `.tmp*` = **`0건`** (`pytest` 픽스처 PNG `4개`만 유지).
  - `/tmp/aab_speed_cache`(`4.4 GB`), `/tmp/bci_test_projects`, `/tmp/rf_*`, `/tmp/fimg_*`, `~/chrome-profile/flow_bridge` 잔여 임시 파일 = **`0건`**.

### 2.4 Google Flow 방 네이밍 정규화 & 멀티 에이전트 탭 탈취 원천 차단 (`:9222`)
- **정규 방 규칙 ([flow_workspace.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/flow_workspace.py))**:
  - 에피소드당 단일 정규 방 이름 **`AAB_<project_id>`** 고정 + 재실행 시 동일 URL 재사용 + 로컬 수확·검증 직후 클라우드 임시 방 자동 삭제(`FLOW_AUTO_CLEANUP_ON_SUCCESS = True`).
- **4계층 브라우저 탭 격리 ([cdp_tab_lease.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/cdp_tab_lease.py))**:
  - `/tmp/aab_cdp_leases.json` (`fcntl.flock` + `PID` + `/proc/<pid>/stat` 시작 틱 검증)으로 워커별 전용 `targetId` 독점 임대.
  - `Target.createTarget({"url": ..., "background": True})` + `Emulation.setFocusEmulationEnabled({"enabled": True})` 적용, 파이프라인 전체에서 `Page.bringToFront` 및 비격리 `context.new_page()` 호출 **`0건`** 강제.
  - **라이브 무간섭 증명**: `flow-clean` 전후 `http://127.0.0.1:9222/json/list` 비교 결과 기존에 열려 있던 사용자 탭 `4개`(YouTube Studio 3개 + 대사관 공지 탭 1개) **포커스 탈취·변경·종료 `0건`**, 작업 종료 후 워커 탭 누수 **`0건`** 확인.

### 2.5 폴더 단순화 · `youtube-*` 스킬 통일 · AI 전용 압축 · 채팅방 `@멘션` 시스템
- **스킬 이름 `youtube-*` 단일화 (`0` 깨진 심볼릭 링크, 구버전 `bci-*` 참조 `0건`)**:
  - [youtube-research](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/skills/youtube-research/SKILL.md) / [youtube-script](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/skills/youtube-script/SKILL.md) / [youtube-produce](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/skills/youtube-produce/SKILL.md) / [youtube-studio](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/skills/youtube-studio/SKILL.md) / [youtube-report](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/skills/youtube-report/SKILL.md)
- **AI 전용 경량화 & 검색 가속**:
  - [AGENTS.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/AGENTS.md) (`37.5 KB` → AI 전용 압축본, `<user_rules>` 잘림 `0%`), 15개 `.agents/rules/*.md`, `SKILL.md`, `SOUL.md` 전수 경량화 완료.
  - [.rgignore](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.rgignore) 추가로 FUSE 검색 속도 `<1s` 달성.
- **크로스 채팅방 `@멘션` 라우터**:
  - [chatrooms.json](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/chatrooms.json) 및 [chatroom_mention.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/scripts/chatroom_mention.py) 구축 완료 (`@Research`/`@리서치`, `@Daily_Report`/`@일일리포트`, `@Headquarters`/`@본부`, `@Channel_Art`/`@채널아트` 멘션 시 즉시 해당 채팅방 `conversation_id`로 작업 전달 가능).

---

## 3. 자동화 테스트 결과 요약

- 전체 스위트: `/home/canadaofbin/hermes-venv/bin/python -X utf8 -m pytest -q` → **`295 passed, 1 skipped, 6 deselected, 0 failed`**
- 신규 핵심 검증 스위트:
  - [test_shorts90s_cdp_lease_and_flow_workspace.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/tests/test_shorts90s_cdp_lease_and_flow_workspace.py)
  - [test_chatroom_mention.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/tests/test_chatroom_mention.py)
