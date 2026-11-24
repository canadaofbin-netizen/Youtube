# `07_Youtube` 전체 최적화 · 리네이밍 · 토큰 누수 차단 완료 보고서 (Walkthrough)

## 1. 전후 정량 성과 요약 (Before → After 실측치)

| 항목 | 최적화 전 (`Before`) | 최적화 후 (`After` 실측) | 변화량 |
|---|---:|---:|---:|
| **전체 Python 코드** | `226,145 LOC` (`215`개 파일) | **`152,880 LOC`** (`153`개 파일) | **`-73,265 LOC` (`-32.4%`)** |
| **`scripts/` 유틸리티 용량** | `1.5 MB` (`29`개 파일) | **`183 KB`** (`7`개 파일) | **`-88%`** (`build_brand_identity_pack` 7,224줄 제거 등) |
| **QA 레이어 코드** | `29,023 LOC` (`14`개 모듈) | **`19,733 LOC`** (핵심 정리 + 퇴역 5게이트/4모듈 삭제) | **`-9,290 LOC` (`-32.0%`)** |
| **CLI 서브커맨드** | `67개` (`cli.py` `3,634`줄) | **`33개`** 5-Gear 핵심 (`ep` 상태머신 신설 포함) | **`-50.7%`** |
| **`config.py` 본체** | `3,742 LOC` 단일 파일 | **`15 LOC` 파사드** + `config_paths/flow/qa/v8` 4분할 | 에이전트 부분 로딩 최적화 |
| **완성 MP4 QA 디코딩** | 다중 `cv2.VideoCapture` + FUSE 직접 열람 | **64GB Max-RAM 단일 패스 `1회` 디코딩** (`FUSE 0회`) | `2,329`프레임 `11.06s` 스캔 |
| **전체 디스크 용량** | `~24.2 GB` (`BCI_Shorts_Channel` `22G`, `artifacts_archive` `1.4G` 등) | **`~10.3 GB`** (`BCI_Shorts_Channel` `9.5G`, `artifacts_archive` `489M`) | **`-13.9 GB` (`-57.4%`) 회수** |
| **보존 프로젝트 / 자산 패리티** | `59`개 혼재 폴더 | **`27`개 보호 폴더** (`Public` 24편 + `ep09_r82`, `ep13`, `ep14`) | **영수증·MP4·`99`슬롯 `100%` 무손실** |

---

## 2. 주요 변경 사항 (Phases 0–6)

### A. 안전 스냅샷 고정 (`Phase 0`)
- 로컬 복구 지점 `backup/pre-slim-2026-11-23` 브랜치 및 `pre-slim-snapshot-2026-11-23` Git 태그 생성 완료.

### B. `Fresh-Room` 아키텍처 전환 & 6대 토큰 누수 원천 차단 (`Phase 1`)
- **7개 고정 채팅방 체계 해체**: `.agents/chatrooms.json`, `scripts/chatroom_mention.py`, `tests/test_chatroom_mention.py` 삭제 및 [scheduler.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/studio/scheduler.py)의 `CEO_CONVERSATION_ID` 의존성 제거.
- **`Fresh-Room` 단일 오너 헌장(`R83 v3`) 적용**:
  - [governance_roles.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/governance_roles.md), [AGENTS.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/AGENTS.md), 전역 [post_compaction_context_recovery_rule.md](file:///home/canadaofbin/.gemini/config/rules/post_compaction_context_recovery_rule.md) 동기화 완료 (`1작업/1에피소드 = 1새 방 0k 시작`, Gate 1/2만 단발성 독립 비전 서브에이전트 `12-up` 시트 검수 후 즉시 `kill`, 기계적 보조 작업 `flash` 허용).
- **CLI 기본 Compact JSON(`<= 1,800 B`) & `pytest` 경량 출력**:
  - [cli.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/cli.py)의 QA/상태 명령 기본 출력을 `~300 B` 수준의 결함 요약 JSON으로 전환 (`--verbose-json` 옵션 분리, `--summary` 하위호환 유지).
  - [pytest.ini](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pytest.ini)에 `-q --tb=short --no-header` 기본 적용.
- **아카이브 훅 경량화 & Zero-Token 일일 운영 스크립트**:
  - [hooks.json](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/hooks.json)에서 매 편집마다 실행되던 `PostToolUse` 훅을 제거하고 `Stop` 단독으로 축소, [sync_archive.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/scripts/sync_archive.py)에서 대용량 미디어(`> 2 MB`) 복사 차단 및 중복 폴더 생성 버그 수정.
  - LLM 토큰 `0`으로 일일 리포트·워치독·스케줄러를 실행하는 [run_daily_ops_headless.sh](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/scripts/run_daily_ops_headless.sh) 추가.

### C. 레거시·수동 Blender·롱폼·1회성 스크립트 일괄 제거 (`Phase 2`)
- **제거된 파이프라인/루트 모듈 (`32개`)**: `previs_blender.py`, `brain_simulator_blender.py`, `topics_catalog.py`(17,086줄 → `published_legacy_topics.json` 경량 대체), `prompts_db.py`, `expand_topics_to_1500.py`, `produce_psychology_batch.py`, `gemini_web_worker.py`, `scene_blueprint.py`, `search_seo_autocomplete.py`, `scripting.py`, `generator.py`, `orchestrator.py`, `studio_batch_100_scheduler.py`, `wave_orchestrator.py`, `ideation.py`, `qa_gates.py`, `clip_qa_contract.py`, `deliverable_overwatch.py`, `ab_tester.py`, `sanitize_scheduled_metadata.py`, `unschedule_retired_shorts.py`, `us_diorama_timetable.py`, `longform_*.py` 8종 등.
- **제거된 1회성 스크립트 (`15개`) & 퇴역 테스트 (`21개`)**: `ep09` 수동 리메이크 스크립트 5종, `porcelain v7` 마이그레이션 스크립트, 구형 v5~v7/Blender/롱폼 테스트 일괄 정리.

### D. QA 레이어 통폐합 & 64GB Max-RAM 단일 패스 스캐너 (`Phase 3`)
- [prompt_gate.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/prompt_gate.py)에서 v5~v7/R74/R76 퇴역 검증 함수 제거, 현행 `expressive_25d_v8` (R85–R89) 집중.
- [episode_qa.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/episode_qa.py) & [episode_qa_gates.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/episode_qa_gates.py) 분리 및 Tier-3 퇴역 게이트(`DQ1`, `DQ12`, `DQ_CAMEO`, `DQ_R76_*`) 삭제.
- **64GB Max-RAM (`MemAvailable >= 12 GiB` OOM 안전 가드) 단일 패스 스캔**:
  - [media_cache.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/media_cache.py) & [hardware_profile.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/hardware_profile.py)에서 `Swap: 0B` 환경 안전 마진(`12 GiB`)을 실시간 감시하며 최대 가용 메모리에 전체 프레임을 1회 순차 디코딩해 [episode_qa.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/episode_qa.py), [posthoc_qa.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/posthoc_qa.py), [media_probe.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/media_probe.py)가 중복 디코딩 없이 공유 (`/dev/shm` 내 방치된 구버전 백업도 전량 정리 완료).

### E. God-File 분할 · `main.py ep` 상태머신 · 전체 파일명 1:1 리네이밍 (`Phases 4–5`)
- **도메인 분할**:
  - [config.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/config.py) → [config_paths.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/config_paths.py), [config_flow.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/config_flow.py), [config_qa.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/config_qa.py), [config_v8.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/config_v8.py)
  - [assembler.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/assembler.py) → [assembler_audio.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/assembler_audio.py), [assembler_edl.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/assembler_edl.py), [assembler_subtitles.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/assembler_subtitles.py)
  - [reporter.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/studio/reporter.py) → [reporter_analytics.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/studio/reporter_analytics.py), [reporter_charts.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/studio/reporter_charts.py)
- **단일 커맨드 에피소드 상태머신**:
  - `main.py ep status <project_id>` 및 `main.py ep run <project_id> --until gate1|gate2|ready` ([episode_runner.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/episode_runner.py) + [produce_episode.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/workflows/produce_episode.py)) 신설.
- **전체 파일명 직관화(`36개` 리네이밍) + 재유입 영구 차단**:
  - `prompt_gate.py`, `prompt_builder.py`, `reference_pack.py`, `real_world_refs.py`, `archival_media.py`, `archival_insert.py`, `archival_video.py`, `flow_worker.py`, `flow_single_worker.py`, `tts.py`, `bgm.py`, `audio_utils.py`, `assembler.py`, `batch_runner.py`, `episode_runner.py`, `anatomy_overlay.py`, `stamp_overlay.py`, `arrow_guide.py`, `thumbnail.py`, `instagram_cards.py`, `ref_qa.py`, `prosody_qa.py`, `episode_qa.py`, `skin_qa.py`, `posthoc_qa.py`, `media_probe.py`, `studio/browser_session.py`, `studio/watchdog.py`, `studio/scheduler.py`, `scripts/verify_brand_assets.py`, `scripts/verify_assets_bible.py`, `scripts/render_qa_sheets.py`, `scripts/sync_archive.py`, `scripts/run_topic_radar.py`, `scripts/verify_topic_slate.py` 일괄 전환.
  - [workspace_hygiene.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/scripts/workspace_hygiene.py) 및 [pyproject.toml](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pyproject.toml)에 퇴역·구파일명 AST import 차단 가드 내장.

### F. Allowlist 기반 스토리지 회수 (`Phase 6` — `-13.9 GB` 회수)
- 미공개 레거시·파일럿 32개 프로젝트, `projects_longform/`(`2.31 GB`), 구형 프롬프트 DB(`226 MB`), `Completed_Psychology_100_Shorts/`(`192 MB`), 오타 폴더(`21 MB`), `artifacts_archive/` 중복 `.mp4`/`.wav` 및 중복 번호 폴더, 기공개 프로젝트 내부 임시 백업 하위폴더 안전 정리 완료.
- 기공개 `Public` 24편 영수증/MP4, 현행 `v8_ep09_r82`·`v8_ep13`·`v8_ep14`, 루트 `final_shorts_v8_ep*.mp4` 5편, `canonical_assets/`(`99` 슬롯) 바이트 단위 무결성 100% 보존.

---

## 3. 검증 결과 (Verification Results)

- **전체 Pytest 스위트 (Offline + Integration + Slow)**: **`454 passed, 2 skipped, 0 failed`**
- **전 모듈 Import & AST 구문/금지모듈 검사**: `87`개 실행 스크립트/파이프라인 파일 AST 컴파일 및 `79`개 `pipeline.*` 모듈 import 실패 `0건`, `scripts/workspace_hygiene.py --check` `issue_count: 0`
- **실제 에피소드(`v8_ep13`, `2,329` 프레임 `1080×1920`) Max-RAM 단일 패스 벤치마크**:
  - 디코딩 시간 `11.06s`, 피크 RSS `14.20 GiB` (`MemAvailable` `36.53 GiB` 유지 → 종료 즉시 `50.14 GiB` 복귀)
  - `final_mp4 VideoCapture opens = 1`, `fuse.rclone VideoCapture opens = 0`
- **자산 바이블·브랜드·무결성 스모크 검증**:
  - `scripts/verify_assets_bible.py --check` → `passed: true` (`84` active + `15` retired = `99` slots, `15` sheets)
  - `scripts/verify_brand_assets.py --check` → `passed: true`
  - `main.py verify --project v8_ep13_snack_reward_rewiring` → `164/164 (100% INTACT)`
  - `main.py ep status v8_ep13_snack_reward_rewiring` → `stage: "ready_to_publish"` (`302 B` Compact JSON)

> [!TIP]
> **기존 고정 채팅방 정리 안내**: 이전에 열어두셨던 `@Research`·`@Daily_Report`·`@QA_Scheduler`·`@Topic_Radar` 채팅방에 등록된 백그라운드 스케줄(`IsDaemon` 크론)이 남아 있다면 해당 방을 닫거나 스케줄을 취소해 주세요. 앞으로는 `v8_ep14_sleep_pupil_arousal` 등 작업마다 새 채팅방을 열고 `main.py ep status <id>` / `main.py ep run <id> --until gate1`으로 바로 시작하실 수 있습니다.
