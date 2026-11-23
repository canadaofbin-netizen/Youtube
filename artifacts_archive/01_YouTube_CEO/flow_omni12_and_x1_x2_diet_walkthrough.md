# Walkthrough: `Omni 1.2 Flash` 단일 전환 & Google Flow 이미지 `x1 / x2` 다이어트 (`100%` Flow 네이티브)

> **검증 일시**: `2026-11-20 08:15 UTC` | **Google Flow 호출**: **`0`건** *(~24h 자연 쿨다운 존중)* | **외부 유료 API**: **`0`줄** (`flow` 전용 잠금) | **CEO Gate 3 최종 판정**: **전원 PASS**

---

## 1. 완료된 핵심 변경 사항

### A. `Omni 1.2 Flash` 전역 단일화 (`2026-12-05` `Omni 1.1` 은퇴 선제 대응)
- **[config.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/config.py)**: `FLOW_PRIMARY_VIDEO_MODEL = "Omni 1.2 Flash"` (`macaron_cookie`), `FLOW_SECONDARY_OMNI_MODEL = None`, `FLOW_RETIRED_VIDEO_MODELS = ("Omni 1.1 Flash", "Omni 1.1 Quality", "Veo 3.1 - Fast", "Veo 3.1 - Quality")` 확정 및 `supports_start_end_frames=True`, `first_and_last_max_sec=10` 반영.
- **[flow_prompt_builder.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/flow_prompt_builder.py) · [flow_diorama_sharded_worker.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/flow_diorama_sharded_worker.py) · [flow_live_single_worker.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/flow_live_single_worker.py) · [flow_ingredients.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/flow_ingredients.py)**:
  - `Ingredients`(싱글 앵커)와 `VIDEO_FRAMES`(`Start + End`, `3–10s`) 모두 **`Omni 1.2 Flash` (`macaron_cookie`)**로 통합 라우팅.
  - 은퇴 모델 `abra` / `omni_1_1_flash` 자동 거부 및 크레딧 소진 시 `Veo 3.1 - Lite [Lower Priority]` 직행 폴백.
- **`Ep #13` 플랜 동기화**: [visual_plan.json](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/BCI_Shorts_Channel/projects/v8_ep13_snack_reward_rewiring/03_visuals/visual_plan.json) **`19/19` 컷 전부 `"Omni 1.2 Flash"`** (`sha256=8cc89222...`), `prompt-gate` **`passed: true` (`0` issues, `0` warnings)**.

### B. Google Flow 이미지 `1차 x1` + `탈락/force 전용 x2` 다이어트 (`1번만` 적용)
- **[config.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/config.py#L133-L160)**:
  - `FLOW_ZERO_CREDIT_IMAGE_BATCH_COUNT = 1` (`4 → 1`, 에피소드당 이미지 생성량 **~85% 감축**: `Ep #10` `100`장 → `Ep #13` 예상 `~14`장)
  - `FLOW_ZERO_CREDIT_IMAGE_RETRY_BATCH_COUNT = 2` (CV 실패 재시도 & Gate 1 반려 표적 재생성 전용 `x2`)
  - `FLOW_ZERO_CREDIT_IMAGE_THUMBNAIL_BATCH_COUNT = 2` (`R65 v4` 썸네일 키아트 전용 `x2`)
  - `resolve_flow_image_batch_count(...)` 공용 결정 헬퍼 추가 *(일일 강제 생성 상한 미추가, `DEFAULT_REENACT_IMAGE_BACKEND = "flow"` 불변 잠금)*.
- **[flow_ingredients.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/flow_ingredients.py#L1108-L1430)**:
  - `count_ok = 1 <= ls_count <= target_batch` 엄격 검증(이전 `x4` 잔류 시 **Fail-Closed `RuntimeError`**).
  - `"unusual activity"` 감지 즉시 `reason="flow_unusual_activity_blocked"` 반환 + 반환 URL 슬라이스 `new_urls[:eff_batch]` 엄격화.
- **[source_reenactment.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/source_reenactment.py#L1815-L1875) · [porcelain_anchor_pack.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/porcelain_anchor_pack.py) · [longform_refs.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/longform_refs.py)**:
  - 시도 루프 `range(4) → range(3)` (`1차 x1` + 최대 `2회 x2`), `flow_unusual_activity_blocked` 감지 시 **재시도 `0`회 · 모델 호핑 `0`회 즉시 중단**.
  - `porcelain-refs --refs <id> --force`로 Gate 1 반려 컷만 표적 `x2` 재생성 지원.
- **하드코딩 `batch_count=4` 전수 제거**: [cli.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/cli.py), [thumbnail_studio.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/thumbnail_studio.py), [real_world_reference_builder.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/real_world_reference_builder.py), [run_ig_card_pilot.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/scripts/run_ig_card_pilot.py).
- **규칙 & 마스터 인덱스 정합**: [production_constants.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/production_constants.md), [reference_depiction_rules.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/reference_depiction_rules.md), [visual_prompt_spec.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/visual_prompt_spec.md), [AGENTS.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/AGENTS.md) 동기화 완료.

---

## 2. 검증 결과 (CEO Gate 3 독립 재실행 포함)

| 검증 항목 | 실행 명령 / 대상 | 실측 결과 | 판정 |
|---|---|---|---|
| **신규/타깃 회귀 스위트 (CEO 직접 재실행)** | `pytest tests/test_flow_image_x1_x2_retry_policy.py tests/test_source_reenactment_qa.py tests/test_master_upgrade_review_fixes.py tests/test_omni12_global_migration.py -q` | **`25 passed, 1 deselected in 16.52s`** | **PASS** |
| **전체 비-Blender 스위트 (`@Operator` 영수증)** | `pytest --ignore=tests/test_blender_brain_sim.py -k "not blender_render" -q` | **`592 passed, 15 deselected, 0 failed`** | **PASS** |
| **하드코딩 `batch_count=4` 스캔 (CEO 직접)** | `pipeline/` + `scripts/` 전수 정규식 검사 | **`0`건 (`[]`)** | **PASS** |
| **`Omni 1.1` / `abra` 활성 라우팅 스캔 (CEO 직접)** | `pipeline/*.py` 전수 검사 | 활성 라우팅 **`0`건** (`config.py` 은퇴 상수 4줄만 존재) | **PASS** |
| **Flow 네이티브 잠금 & 리졸버 라이브 확인** | `config.py` 직접 임포트 검사 | `backend='flow'`, `BATCH=1`, `RETRY=2`, `THUMB=2`, `resolve(first=1, retry=2, force=2, explicit=3)` | **PASS** |
| **`Ep #13` `prompt-gate` (CEO 직접)** | `main.py prompt-gate --dir ...v8_ep13_snack_reward_rewiring` | **`passed: true, issues: [], warnings: []`** | **PASS** |

---

## 3. 다음 단계 (자연 쿨다운 종료 후)
- 현재 `Ep #11` (`11/20 19:30 ET`) · `Ep #12` (`11/21 19:30 ET`)가 이미 예약되어 있어 채널 발행 공백이 없습니다.
- 하루 정도 자연 쿨다운 후 사용자께서 NoVNC에서 수동 1클릭 정상 복구를 확인해 주시면, 첫 파일럿 **`Ep #13`**(`12`컷 커스텀 키프레임 × `x1` = **`12`장 1차 생성** + `Omni 1.2 Flash`)으로 즉시 재개할 준비가 100% 완료되어 있습니다.
