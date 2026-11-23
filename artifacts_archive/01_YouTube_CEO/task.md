# ALL ABOUT BRAIN `v8.3` 통합 마스터 실행 체크리스트

- [x] **Pilot #3 (`v8_pilot_03_marshmallow_trust_previs` `v2`) Gear 5 YouTube Studio `Public` 전환 및 업로드 완료**
  - [x] `studio-upload` (`soUNqH7UyKw`, `https://www.youtube.com/shorts/soUNqH7UyKw`, **`Public` 공개 전환 완료** + 커스텀 썸네일 `thumbnail_var_A.png`)
  - [x] `Related video` 연결 (`Wydl4JpZmAw`) 및 7-Pillar 재생목록(`Brain Basics & Biophysics`) 배정
  - [x] `studio-pin` DOI 학술 출처(`10.1016/j.cognition.2012.08.004`) + 토론 유도 고정 댓글 등록 완료 (`stage_5_complete: true`)

- [x] **Phase 0 (`C2`): 읽기 전용 Google Flow UI 기능 프로브 & 안전 기능 플래그 구축**
  - [x] `pipeline/config.py`: `Omni 1.2 Flash` 확장 기능 플래그(`FLOW_OMNI_ENABLE_EXTENDED_DURATIONS`, `FLOW_OMNI_ENABLE_NATIVE_1080P_DOWNLOAD`, `FLOW_OMNI_ENABLE_CONVERSATIONAL_EDIT`, `FLOW_OMNI_ENABLE_MULTI_INGREDIENTS_V83` 기본 `False` 안전 롤백 `C9`) 및 `v8.3` 상수 추가
  - [x] `pipeline/flow_workspace.py` + `pipeline/cli.py`: `probe_flow_ui_capabilities()` 읽기 전용 CDP 설정창/다운로드/편집/크레딧 프로브 및 `main.py flow-probe` CLI 서브커맨드 구현 완료

- [x] **Component 1 (`C1, C3, C5, C8`): `Omni 1.2 Flash` 풀스펙 라우팅 · `0-credit` 2탭 강제 가드 · `1080p` 수확 · 블러 게이트 · 대화형 편집**
  - [x] `C3`: 실시간 잔액 기반 동적 예산 `compute_dynamic_omni_episode_budget()` 추가 (기존 `FLOW_OMNI_EPISODE_CREDIT_CAP = 200` 호환 유지)
  - [x] `C8`: `flow_workspace.py` 단가 동기화(`24cr`) + `flow_diorama_sharded_worker.py` `0-credit` 전환 시 초과 샤드(`shard > 2`) 즉시 양보·종료 가드 완료
  - [x] `C1` + 선명도/수확/편집: `inspect_diorama_clip_cv` 하위 15% 중앙 선명도(`p15_center_sharpness >= 1.65`) 모션블러 스파이크 게이트, `_download_newest_ready_tile` 네이티브 `1080p` 업스케일 우선 수확기, `refine_clip_via_flow_conversational_edit` 1턴 부분 편집기, `flow_ingredients.py` `upload_multi_ingredients_v83()` 멀티 레퍼런스(`<=8`장 + `3s` Previs MP4) 구현 완료
  - [x] `C5`: `shorts_expressive_v8` 길이 계약 `<= 120.0s` (`58~118s`) `config.py`, `cli.py`, `studio/uploader.py` 정합성 반영

- [x] **Component 2 (`C4, M1`): 초선명 `40° Nodal 3D Orbit` · `FPV Flythrough` 리그 · 반투명 3D 인간 뇌 6종 팩 · `Start Frame` 단독 기본화**
  - [x] 반투명 3D 인간 뇌 레퍼런스 6종(`cand_01..cand_06`) `BCI_Shorts_Channel/reference_style_anchors/translucent_brain_v8_refs/` 정식 PNG 스테이징 및 `Q1~Q10` 100% 통과 검증 (`test_v8_six_master_reference_pack_and_q1_q10 PASSED`)
  - [x] `pipeline/previs_blender.py`: `orbital_3d_arc_sweep` (`40° Nodal Gaze-Lock Orbit`), `fpv_3d_flight`, `axial_portal_dive` 궤적 보정 + `render_previs_motion_guide_mp4()` (`3.0s @ 30fps`) 구현 완료
  - [x] `pipeline/porcelain_anchor_pack.py`: `object_portal_macro` 보케 앵글 퇴출 → 전 구간 `f/8` 딥포커스 프로브 렌즈 교체 + `M1` 일반 컷 `Start Frame` 단독 / 포털·융기 컷 `Start+End` 보간 규칙 반영 완료

- [x] **Component 3 (`M2~M9`): 2.5D 차콜 잉크 표정 연기(`F1~F5`) & `신비한 건축사전` 다큐 문법(`R68-A`, `R58-K`)**
  - [x] `BCI_Shorts_Channel/assets/expression_acting_lexicon.json`: 12종 마이크로 감정 연기 사전(`State A -> State B`, `Saccade`, `<=10°` 고개 각도) 생성 완료
  - [x] `pipeline/depiction_rules.py`: `ExpressiveReactionCloseupRule` (`F2`), `format_expression_acting_clause` (`F5`), `ExpressiveRigidPhysicsRule` (6대 강체 디오라마 물리 `R68-A`) 구현 완료
  - [x] `pipeline/flow_prompt_builder.py`, `pipeline/diorama_assembler.py`, `pipeline/cli.py`, `pipeline/studio/uploader.py`: 동적 Omni 우선순위 배정(`assign_hero_omni_engines`), `C4/M2` 카메라 비율 검증기(`validate_v83_camera_and_acting_balance`), `M3` `Audio-Before-Flow` 슬로모션 0% 차단(`lock_audio_durations_onto_visual_plan`), `M6` (`R58-K`) `2.0s` 키워드 타격 커터(`split_sentences_at_keyword_beats`) & `1-Clip Dual-Harvest`(`build_dual_harvest_edl_windows`) 연결 완료

- [x] **문서 SSOT 동기화 (`C7`) 및 통합 테스트 검증 (`C6`)**
  - [x] `production_constants.md`, `neuro_diorama_rules.md`, `AGENTS.md` (`R55-B`, `R58-K`, `R68-A`), `youtube-produce/SKILL.md`, `youtube-script/SKILL.md` 1:1 동기화 완료
  - [x] 신규 `tests/test_v8_3_omni12_master_upgrade.py` 작성 및 기존 회귀 스위트 전수 검증
