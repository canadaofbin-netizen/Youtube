# R85 Phase 0–2 & R86 Phase 2.5 구현·검증 완료 보고 (`[R85_PHASE0-2_DONE]`)

> [!IMPORTANT]
> **R83 거버넌스 준수 확인**: 면제 플래그 우회 `0건`(`UNMANNED_QA_SIGNOFF_DEFAULT = False`), 기공개 YouTube 영상(`tWjrK5enOoM`) 수정 `0건`, `Phase 3` Flow 재생성 및 `Ep10` Siren TTS 재합성 선행 `0건`(`@YouTube_CEO` 별도 `GO` 대기).

---

## 1. 실행 명령어 및 수치 결과 (`R83-7` 재현 가능 증빙)

| 검증 항목 | 실행 명령어 | 결과 수치 |
|---|---|---|
| `AGENTS.md` 크기 예산 | `wc -l -c .agents/AGENTS.md` | **`76`줄 / `10,106` bytes** (`<= 78`줄, `< 10,240` bytes) |
| `AGENTS.md` 예산 테스트 | `/home/canadaofbin/hermes-venv/bin/python -X utf8 -m pytest tests/test_r78_dual_material_and_siren_5tone.py -k test_r78_agents_md_size_and_line_budget -v` | **`1 passed`** |
| `R85` 5대 회귀 + `R86` 회귀 테스트 | `/home/canadaofbin/hermes-venv/bin/python -X utf8 -m pytest tests/test_r85_r86_qa_honesty_and_semantic_beat.py -v` | **`7 passed, 0 failed`** |
| 전체 Fast `pytest` 스위트 | `/home/canadaofbin/hermes-venv/bin/python -X utf8 -m pytest -v` | **`547 passed, 14 deselected, 0 failed`** (`717.87s`) |
| 워크스페이스 위생 점검 | `/home/canadaofbin/hermes-venv/bin/python -X utf8 scripts/workspace_hygiene.py --check` | **`passed: true, issue_count: 0`** |
| 4편 비파괴 Red-Team Replay | `/home/canadaofbin/hermes-venv/bin/python -X utf8 /home/canadaofbin/.gemini/antigravity-cli/brain/1f9808d4-ebac-4b58-a570-45c8f1f00a85/scratch/r85_redteam_replay.py` | **`overall_any_pass: false` (`4/4` 전편 실패, 위양성 `0건`)** |

- 전체 `pytest -v` 원문 로그: [output.txt](file:///home/canadaofbin/.gemini/antigravity-cli/brain/1f9808d4-ebac-4b58-a570-45c8f1f00a85/.system_generated/steps/12724/output.txt)
- Red-Team Replay 스크립트: [r85_redteam_replay.py](file:///home/canadaofbin/.gemini/antigravity-cli/brain/1f9808d4-ebac-4b58-a570-45c8f1f00a85/scratch/r85_redteam_replay.py)
- Red-Team Replay JSON 결과: [r85_redteam_replay_results.json](file:///home/canadaofbin/.gemini/antigravity-cli/brain/1f9808d4-ebac-4b58-a570-45c8f1f00a85/scratch/r85_redteam_replay_results.json)
- 실측 결함 프레임 픽스처: `/tmp/aab_verify/{e10c08,e09c22,e11c24,e09c07}.jpg` 및 영구 보존본 [tests/fixtures/r85_verify/](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/tests/fixtures/r85_verify)

---

## 2. `Omni 1.2 Flash` 끝 프레임(`Start + End`) 지원 실측 결과 (`task-12262`)

- 실측 로그: [task-12262.log](file:///home/canadaofbin/.gemini/antigravity-cli/brain/1f9808d4-ebac-4b58-a570-45c8f1f00a85/.system_generated/tasks/task-12262.log)
- **실측 결과**:
  - Google Flow UI에서 `VIDEO_FRAMES`(`Frames` 모드)로 전환해 `Start + End` 2장(`chip_count: 2`)을 첨부하면 모델 패밀리가 **`Omni 1.1 Flash` (`abra`)**로 고정됩니다.
  - 2칩 첨부 상태에서 `select_flow_video_model(client, "Omni 1.2 Flash")` 재선택 시도 시 `reselect_omni12_ok: false` (`fam_after_reselect: "abra"`). 즉 `Omni 1.2 Flash` (`macaron_cookie`)는 단일 `Ingredients` 전용이며 `Start + End` 프레임을 지원하지 않습니다.
- **적용 라우팅**:
  - 일반 단일 앵커 컷 -> **`Omni 1.2 Flash` (`macaron_cookie`)** 최우선 사용.
  - 드리프트 취약 컷(인간 클로즈업, `R80` `doorway_boundary_sever` 단절 화살표 등 `end_reference_image` 보유 컷) -> 자동으로 `Start + End` `VIDEO_FRAMES` + **`Omni 1.1 Flash` (`abra`)**로 라우팅 (`pipeline/flow_diorama_sharded_worker.py`, `pipeline/flow_prompt_builder.py`).

---

## 3. Red-Team Replay 4편(`Ep09_r82` ~ `Ep12`) 컷별·게이트별 적발 판정표

| 에피소드 (`project_id`) | `posthoc-qa` (기계 서명·프롬프트 복사) | `ref-qa` + `real_world_refs_manifest` (`@Research` HARD REJECT 8건) | `episode-qa` `DQ8` (`0.25s` YuNet `ink=False` 실사 얼굴/머리카락) | `data-stamp` (`Concept` 금지·수치 일치) | `prompt-gate` (`R85` + `R86`) | 최종 |
|---|---|---|---|---|---|---|
| `v8_ep09_maguire_london_taxi_hippocampus_r82` | **FAIL** (`unmanned_cv_verified_signoff_forbidden` + `prompt_copied_into_observed_summary`) | **FAIL** (`Waarschuwingstekst` MRI 경고문 + `D3 bus at Leamouth` 적발) | **FAIL** (컷 `[1, 2, 4, 5, 6, 7, 8, 16, 19, 22, 23]`) | PASS (`study` 모드) | **FAIL** (`C03` 드론 `walk`/`relay`, Blender 8컷 퇴출, 해마 시점 7컷, `R86` 뇌 반복 `[11,17]`·`[12,20]`) | **FAIL** |
| `v8_ep10_sleep_pill_brain_wash` | **FAIL** (`unmanned_cv_verified_signoff_forbidden` + `prompt_copied_into_observed_summary`) | **FAIL** (`9282 Oslo. Rikshospitalet digifoto` + `Siemens Magnetom Aera` 적발) | **FAIL** (컷 `[1, 2, 4, 5, 6, 8, 23, 24]`) | **FAIL** (스탬프 #1 `illustrative` `"Concept"` 금지 위반) | **FAIL** (`C03` `relay`, `C14/C24` 항공 보행 동사, Blender 8컷 퇴출, 시상/뇌간·해마 시점 8컷) | **FAIL** |
| `v8_ep11_open_label_placebo_pain` | **FAIL** (`unmanned_cv_verified_signoff_forbidden` + `prompt_copied_into_observed_summary`) | **FAIL** (`Anno Domini Harvard` + `BIDMC EMERGENCY` + `Nateglinide 60 mg bottle` 적발) | **FAIL** (컷 `[1, 4, 5, 6, 8, 16, 19, 20, 23, 24]`) | PASS (`study` 모드) | **FAIL** (`C03` `relay`, `C17/C18` `insula` 정중시상 단면 오류, `C19/C23` 항공 보행 동사, Blender 8컷 퇴출, `R86` 뇌 반복 `[10,17]`·`[12,21]`) | **FAIL** |
| `v8_ep12_doorway_effect_memory` | **FAIL** (`unmanned_cv_verified_signoff_forbidden` + `prompt_copied_into_observed_summary`) | **FAIL** (`FEMA - 33940 - "Old Brick House"` 허리케인 폐허 + `alphabet wooden blocks` 적발) | **FAIL** (컷 `[1, 2, 3, 4, 5, 6, 7, 12, 14, 18, 19, 22, 23]`) | **FAIL** (스탬프 #2 `illustrative` `"Concept"` 금지 위반) | **FAIL** (`C03/C12/C18` 항공 보행 동사, Blender 8컷 퇴출, 해마 시점 6컷, **`R86` `C05` 의미 소진·`C19` 인과 누락·`C23` 소포 노끈 필러·뇌 반복 `[10,11]`**) | **FAIL** |

---

## 4. 변경 및 신설 파일 목록 (`Phase 0 ~ Phase 2.5`)

### SSOT 규칙 & 설정 (`Phase 0`)
- [AGENTS.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/AGENTS.md): §1 불변 정체성 4종·Blender 가이드 전용화, `R76`/`R84` 개정, `R85`/`R85-R`/`R86` 등록 (`76`줄, `10,106` bytes).
- [brain_depiction_rules.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/brain_depiction_rules.md), [qa_gates_rules.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/qa_gates_rules.md), [neuro_diorama_rules.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/neuro_diorama_rules.md), [production_constants.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/production_constants.md): `R85`, `R85-R`, `R86`, 면제 플래그 금지·원천 재생성 원칙, `@Research` VLM 서명 의무 반영. *(CEO 소유 `governance_roles.md` 수정 `0건`)*
- [config.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/config.py): `UNMANNED_QA_SIGNOFF_DEFAULT = False`, `R85_*` 및 `R86_*` 상수·헬퍼(`is_r85_flow_31_brain_plan`, `is_r86_semantic_beat_plan`), `is_r76_v8_plan()` 자동 Blender 강제 제거.

### QA 정직성 복구 (`Phase 1`)
- [posthoc_semantic_qa.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/posthoc_semantic_qa.py): `unmanned_cv_verified_signoff`/`auto_*` 전면 거부, `intended_scene` `>=70%` 토큰 중첩 또는 `>=7`단어 연속 복붙 적발, `Schema v8+` `require_review=True` 기본화, stale/invalid 리뷰 상시 `passed=False`, `R86` `delivers_viewer_must_understand` 검증.
- [reference_image_qa.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/reference_image_qa.py): `L1458` 디오라마 `require_review` 면제 제거, `auto_cv_verified_v7` 자동 `True` 채움 제거(빈 템플릿만 생성), `validate_real_world_refs_manifest()` 연동.
- [cli.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/cli.py), [diorama_assembler.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/diorama_assembler.py), [diorama_batch_orchestrator.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/diorama_batch_orchestrator.py): 무인 자동 서명 호출 전면 제거 및 `REVIEW_PENDING` 정지(`exit 2`).
- [dynamic_episode_qa.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/dynamic_episode_qa.py), [flow_diorama_sharded_worker.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/flow_diorama_sharded_worker.py): `allow_expressive_2d_ink=False` 전환, `verify_v8_yunet_skin_or_hair_leak` 면제 구멍 제거, 클립 사용 구간 전체 `0.25s` 간격 전수 샘플링.
- [data_stamp_overlay.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/data_stamp_overlay.py), [layers.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/charts/layers.py): 실증 DOI 보유 시 `illustrative`(`"Concept"`) 금지, 도시에 검증 수치 매칭 허용 및 대본 모순(`29% != 30%`) 차단, 배수 루프 바 숫자 겹침 방지.

### 입력 오염 차단 · 드리프트 락 · 31번 AI 뇌 · `R86` Semantic Beat (`Phase 2 & 2.5`)
- [real_world_reference_builder.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/real_world_reference_builder.py): `FEMA/hurricane/damage/ruin/sign/alphabet/digifoto/mg bottle` 블록리스트, `@Research` 검증 12종 `NEUROANATOMY_CUTAWAY_MAP`, `/tmp/aab_real_refs/<project_id>/guides/` 전용 `render_mni152_guide_silhouette()`.
- [porcelain_anchor_pack.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/porcelain_anchor_pack.py), [brain_simulator_blender.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/brain_simulator_blender.py): `build_r85_31_brain_keyframe_spec()`(부위별 해부 시점 강제 + `#9CA5AC~#C3C9CE` & `#27D8FF` 31번 뇌 양식), `R85` 모드 직접 Blender 화면 렌더 `RuntimeError` 차단(파일 보존).
- [flow_prompt_builder.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/flow_prompt_builder.py), [prompt_quality_v5.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/prompt_quality_v5.py): 드론 `120ft` 고도 락·보행 동사 lint, 인간 컷 대머리 크림 비닐 정체성 접미사, 드리프트 취약 컷 `end_reference_image` 자동 부여, `R86` 확정 스키마(`visual_register = story|diagram`, `metaphor_continuity_id` `3~5`컷 + `bridge_element`, 연속 `concept_id` `state_delta` + `0` delta 뇌 반복 차단, `misconception_flip` 3단계 `mechanism_seed`, `reaction <= 2`, `decorative = 0`) 빌더 및 `prompt-gate` lint.
- 신규·갱신 테스트: [test_r85_r86_qa_honesty_and_semantic_beat.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/tests/test_r85_r86_qa_honesty_and_semantic_beat.py) (신규 7건) 및 기존 구형 기본값 가정 테스트 6개 파일 정합화 (+ [uploader.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/studio/uploader.py) `tmp_path` 테스트 스텁 판별 보정).
