# `@Operator` 실행 보드 — `@YouTube_CEO` 승인 지시사항 전수 이행

## 1. Rule `R68-D` 구현 (`r68d_viewer_story_description_plan.md` v3) — 완료
- [x] `pipeline/config.py` & `production_constants.md`: `R68D_DESCRIPTION_WORD_RANGE = (55, 135)`, `R68D_BANNED_AI_CLICHES` 정의
- [x] 무(無)DOI·무(無)엠대시(`—`)·안티-AI 문체 2문단 설명란, 1문장 질문 고정댓글, 멀티플랫폼 캡션 빌더 동기화
- [x] 단위·회귀 테스트 `58/58 passed`, `Ep #4`·`Ep #5` `prompt-gate` 무결점 통과, `@YouTube_CEO` 중간 보고 #1 발송 완료

## 2. Task C (ElevenLabs 단일 TTS 잠금 & 레거시 TTS 제거) + Task D (`v8` 서사 암부 조명 영구 보정) — 완료
- [x] `~/.cache/aab_tts`(`338 MB`) 삭제 및 `kokoro-onnx`, `edge-tts`, `espeakng-loader`, `phonemizer` 언인스톨 (`onnxruntime` 보존)
- [x] `pipeline/voice_consistency.py` 삭제, `elevenlabs_tts.py` 3회 지수 백오프(`1.5s -> 3.0s -> 6.0s`) 및 `401`/쿼터 즉시 Fail-Fast 잠금, `voice_fallback.py` 무폴백 단일 엔진화 + `EXPRESSIVE_V8_SUBTITLE_MAX_WORDS = 2` 적용
- [x] `v8` 서사 암부 조명 영구 보정: `EXPRESSIVE_V8_MIN_LUMA = 28.0`, `flow_diorama_sharded_worker.py` `v8` `luma_floor = 26.0` / `dark_cap = 0.68` / 앰버 반사 허용 및 재시도 시 인공 주광 주입 차단, 문서 7종 동기화
- [x] 전체 고속 `pytest` 스위트(`412`개 항목 전수) 및 `test_elevenlabs_strict_single_engine.py`(`5/5`) 100% 통과 확인 및 `@YouTube_CEO` 중간 보고 #2 발송 완료

## 3. 신규 Task A — Rule `R65 v2` (`'신비한 건축사전'` 3D 단면도 키아트 + `#FF2525` 포인터/치수선 + 대각선 Z-패턴 2단 훅) — 완료
- [x] `pipeline/config.py`, `production_constants.md`, `neuro_diorama_rules.md`, `youtube-script/SKILL.md`, `AGENTS.md` 문서 및 상수 동기화
- [x] `pipeline/flow_ingredients.py` & `pipeline/thumbnail_studio.py`: Wood-Grain Laplacian Trap 교정, `generate_zero_credit_thumb_keyart()` (`FLOW_ZERO_CREDIT_IMAGE_MODEL` `9:16` `x4`), `render_cutaway_pointer_and_z_overlay()`, `TQ1–TQ9` + `2:3` 선반/타이틀 마스크 콘택트 시트
- [x] `pipeline/cli.py`, `pipeline/diorama_batch_orchestrator.py`, `pipeline/prompt_quality_v5.py` 연동 및 `tests/test_r65_v2_cutaway_thumbnail_studio.py` 검증 완료

## 4. 신규 Task B — YouTube Studio `'Draft(초안)'` 원천 차단 & 사후 DOM 검증 패치 — 완료
- [x] `pipeline/studio/whale_session.py`: `set_schedule_datetime_utc()` `SCHEDULE` 라디오 체크 검증 + `invalid` 입력 검증 + `#done-button` `Schedule`/`예약` 텍스트 검증 (프로토타입을 훼손하던 `Object.assign` 제거 포함)
- [x] `pipeline/studio/uploader.py`: `Slot 4 = 19:30 ET`(`09:30 KST`) 기본값 & `now_et + 20m` / 중복 일자 자동 이월, 업로드 직후 `/videos/short` `.tablecell-visibility` 확인 + `Draft` 시 `/video/<id>/edit` 자동 복구(Self-Heal) + 미복구 시 `RuntimeError`
- [x] 채널 내 잔존 `Draft` 읽기 전용 전수 스캔 완료 (`/videos/short`: `16`편 — `Public: 5`, `Unlisted: 11`, `/videos/upload`: `0`편, **`draft_count = 0`**; 기존 영상 무터치) 및 `tests/test_studio_schedule_no_draft.py` 통과 확인

## 5. 신규 Task C — `Ep #4` & `Ep #5` 전수 완성 + `R65 v2` 키아트 썸네일 + `19:30 ET` 일일 예약 업로드
- [x] `Ep #4` (`v8_ep04_patient_sm_fearless_amygdala`): Flow 20클립 및 어셈블리(`115.033s`) + `R65 v2` `--generate-keyart` 썸네일(`TQ1–TQ9` 전수 통과, `score=1.220`) + 전수 QA(`posthoc=96.7`, `DQ=14/14`, `prosody=10/10`) + **`2026-11-11 19:30 ET` (`11/12 09:30 KST`)** 예약 업로드 및 `Scheduled` DOM 검증 완료 (`7W8zIOMKPrQ`, `draft_count=0`, `related_link_verified=1`)
- [x] `Ep #5` (`v8_ep05_ucl_tickle_delay_robot`): Flow `20/20` 클립 및 어셈블리(`111.633s`) + `R65 v2` `--generate-keyart` 썸네일(`TQ1–TQ9` 전수 통과, `score=1.3755`) + 전수 QA(`posthoc=96.8`, `DQ=14/14`, `prosody=10/10`, `autopsy=100%`) + **`2026-11-12 19:30 ET` (`11/13 09:30 KST`)** 예약 업로드 및 `Scheduled` DOM 검증 완료 (`ut1wde0d19o`, 채널 전체 `18`편 중 `Scheduled: 2`, **`draft_count = 0`**, `related_link_verified=1`)

## 6. 마스터 플랜 `Step 1` — `R65 v4` (`in_skull_cutaway_split_v4` / `dark_void_paradox_v4`) + `2:3` 선반 크롭(`y >= 176`) Studio 라이브 재적용 — 완료
- [x] `pipeline/config.py`, `production_constants.md`, `neuro_diorama_rules.md`, `pipeline/thumbnail_studio.py`, `pipeline/studio/uploader.py`: `THUMB_SHORTS_SHELF_CROP_Y = (150, 1770)`, `THUMB_V4_TOP_LABEL_Y_RANGE = (170, 390)`, `TQ4` `safe_y_lo = 150`, `top_anchor_y = 176` / `bot_anchor_y = 1016` 양면 스탬프, `Mode B` (`dark_void_paradox_v4`), 단일 후보 정규화, `Step 12.5` 커스텀 썸네일 자동 적용
- [x] `Ep #4`(`7W8zIOMKPrQ`) & `Ep #5`(`ut1wde0d19o`) 상단 `y < 150` 크롭 구간 클린 복원 후 `y = 176` 재스탬프 (`TQ1–TQ9` 통과), YouTube Studio 백그라운드 격리 탭 재적용 및 저장(`Scheduled = 2`, `Draft = 0`) 검증 완료

## 7. 마스터 플랜 `Step 2` — `3D Previs v2` (`P1–P6`) + 전체 `pytest -v` (`417/417`) + `@YouTube_CEO` Checkpoint 1 — 완료
- [x] `P1` 포터블 `Blender 4.2.23 LTS` 배치 렌더러 & 반투명 `0.22` 관찰창, `P2` `9:16` HFOV/VFOV `12%` 안전 프레이밍, `P3` 에피소드 전체 `Role-Color Lock` & 복합 소품 실루엣, `P4` 하이브리드 `6..10` 히어로 키프레임, `P5` `E7` 포즈 준수 및 무누출 QA, `P6` `3..5` `Start+End` `VIDEO_FRAMES` 듀얼 패럴랙스 구현
- [x] `Ep #4` `S01..S08` Before-vs-After 포렌식 그리드(`ep04_previs_v1_vs_v2_grid.png`) 시각 검증, 전체 고속 테스트 스위트 **`417/417` 100% 통과**, `@YouTube_CEO` Checkpoint 1 발송 완료

## 8. 마스터 플랜 `Step 3` — `Ep #6` (`v8_ep06_bedtime_todo_list_sleep`, `@심리학고양이` 공식 이식) 제작 · 전수 QA · `2026-11-13 19:30 ET` 예약 업로드 — 완료
- [x] Gear 1–2: Crossref 6종 DOI 검증 + `Schema v2` `scullin_bedtime_todo_list_sleep` 도시에(`dossier validate --require-v2`) + `Zero-Redundancy` 제목×`dark_void_paradox_v4` 썸네일 + `2-Study R70 Data Stamp`(`exp_growth` + `25.1m vs 15.8m`, `>= 18s`) + `Night-Watchman` 비유 토템 + `Exoneration Flip` 대본/플랜(`prompt-gate` & `chart-preview` 검증 완료) + `elevenlabs_v4` 3성우 오디오 선행 잠금(`114.27s`, `atempo=1.0`, `R58-K`)
- [x] Gear 3 Part A: `Blender 4.2` `Previs v2` & `porcelain-refs`(`26/26`, `reference_qa_score=100.0`, `Q1–Q11` + `E7`) + `0-credit` Flow `R65 v4` (`dark_void_paradox_v4`) 키아트 썸네일(`TQ1–TQ9` 전수 통과, `score=1.605`, `WCAG@160=20.88`) 완료
- [x] Gear 3 Part B: Google Flow `AAB_v8_ep06_bedtime_todo_list_sleep` `21/21` 고유 비디오 클립 생성 및 프로비넌스 영수증 잠금 완료 (`zero_credit_verified=True`)
- [x] Gear 4: `data_stamp_overlay.py` `[t0, t1]` 트림 가속(`~16x`) + 어셈블리(`114.267s`, `21`컷, `cut_duration_cv=0.1893`, `2ch -14.3 LUFS`) + 전수 마스터 QA(`TQ1–TQ9`, `DQ1–DQ13 14/14`, `P1–P10 10/10`, `R64 posthoc-qa 96.5/100`, `autopsy PASS`) + `multi-bundle` + `asset-manifest` + `kb sync`
- [x] Gear 5: YouTube Studio `2026-11-13 19:30 ET`(`Slot 4`) 예약 업로드(`sjMteEvcjD0`, `uploaded_custom_thumbnail`, `Scheduled` 검증, `related_link_verified=1`) + `R35` 예약 댓글 큐 등록 + Studio 라이브 캡처 및 전체 `pytest -v` 검증

## 9. Phase A — `Rule R72 + R72-R` (오픈월드 드론/실물 레퍼런스) + `Rule R73` (미국 본토 구어체 내레이션) + `Rule R74` (3D 뇌 내부 FPV 다이브 `B0↔B1`) 통합 업그레이드 — 완료
- [x] `pipeline/config.py`: `R72`/`R72-R` 드론 무브 5종·고속 컷 상수(`FIRST_CUT<=2.60s`, `AVG_CUT 2.05..3.30s`, `22..36` 클립, `28..46` 컷) + `R73` 미국식 4대 오프닝(`paradox_question` 기본값, `myth_flip_claim`, `sensory_test`, `action_first_stamp`), `0.42s` Post-Hook Pause, `Plain-First`(`<=2` 전문용어·`<=8w` 즉각 풀이), `<=22w`/문장, `FK<=6.2`, `mic_drop`/`seamless_loop` + `R74` 뇌 내부 FPV 무브 4종(`neural_fpv_dive_in`, `neural_macro_orbit_hold`, `neural_fpv_pullback_out`, `neural_tract_relay_flight`) & `-21.0 dBFS` `0.36s` 벨벳 스우시 정의
- [x] `[NEW] pipeline/real_world_reference_builder.py` & `location_registry.json` & `pipeline/previs_blender.py`(`Previs v2.3`): Wikimedia Commons 3대 범주 수집(`/tmp/aab_real_refs/<project_id>/` 완전 격리·정리), `RQ-Real`(`dHash >= 14`), `28m × 32m` 야외 프리셋 10종, `0.20`-알파 `r=0.26m` 3D 반투명 피질 유리 셸 + 18종 뇌 부위 실제 해부학 진입 벡터(`B0 1.45m <-> B1 0.35m`) 구현
- [x] `porcelain_anchor_pack.py`, `anatomy_map.py`, `anatomy_label_overlay.py`, `diorama_assembler.py`, `flow_prompt_builder.py`, `prompt_quality_v5.py`: **Pattern A/B** `K0->K1->K2` 드론 릴레이 + **`R74` 2사이클 `B0 <-> B1` 공유 `VIDEO_FRAMES` 키프레임 릴레이** + 도착 시점(`t >= 1.25s`) 고정 `R71` 매크로 만년필 콜아웃 + `-21.0 dBFS` 벨벳 스우시 연동
- [x] 문서 5종(`production_constants.md`, `neuro_diorama_rules.md`, `content_quality_rules.md`, `youtube-script/SKILL.md`, `AGENTS.md` `76줄 / 10,194B < 10,240B`) 동기화 + `test_r72_drone_and_real_landmarks.py`(`4/4`), `test_r73_us_native_narration.py`(`4/4`), `test_r74_neural_fpv_dive_relay.py`(`4/4`) 구축
- [x] 전체 저장소 `pytest -v` **`429 passed, 13 deselected` (실패 `0`건)** 100% 통과 + 라이브 **UCL 윌킨스 빌딩 & 하버드 메모리얼 홀** `K0 -> K1 -> K2` 증명 시트(`r72_ucl_harvard_drone_cutaway_proof.png`) 및 **뇌 심부 50% 크리스탈 매크로 다이브** 증명 시트(`r74_neural_dive_relay_proof.png`) 생성·검수 완료 + `@YouTube_CEO` **Checkpoint A** 발송 완료

## 10. Phase B — `Ep #7` (`v8_ep07_harvard_reversible_choice_paradox`, `Rule R72 × R73 × R74 × R75` 제1호 트리플 크라운 플래그십, 초고속 쇼츠 시드 스위트스팟 `78.47s < 88s`) Gears 1–5 전수 완료
- [x] Gear 1: `gilbert_reversible_choice_paradox` (`Gilbert & Ebert 2002` + `Iyengar & Lepper 2000` + `Voigt et al. 2019/2020` + `Shenhav et al. 2014` + `Chernev et al. 2015`) Crossref DOI 6종 검증 & `Schema v2` 도시에 구축 (`dossier validate --require-v2` 18/18 `ready: true`)
- [x] Gear 2: `R73` `paradox_question` 오프닝(`S1` + `0.42s` 휴지) -> `S1->S2` 하버드 메모리얼 홀/야드 `Pattern B` `K0->K1->K2` 드론 릴레이 + `Plain-First`(`choice alarm` `anterior cingulate`, `choice builder` `prefrontal cortex`) + `<=22w`/`FK<=6.2` + `46.7%` 실물 고증 야외/건축 컷 + **2사이클 `R74` 뇌 내부 FPV 다이브(`B0 -> B1_ACC -> B0 -> B1_PFC -> B0`)** + `30` 고유 클립 + `2-Study R70 Data Stamp`(`66.3%` `arc_gauge` + `30% vs 3%` `bar_compare`, `19.3s` 간격) + `FINAL PICK` vs `5-DAY SWAP!` `R65 v4` 썸네일 설계 + `elevenlabs_v4` 오디오 선행 잠금(`78.47s` `< 88s`) & `prompt-gate` / `diorama-episode --precheck-only` 100% 통과
- [x] Gear 3: `R72-R` 실물 레퍼런스 컨디셔닝(`real_world_refs_manifest.json`, `/tmp` 정리) + `Previs v2.3` + `porcelain-refs`(`48/48`, `ref-qa 100.0`, `B0/B1` 매크로 포함) + 독립 `_thumb` 룸 `R65 v4` 썸네일(`TQ1–TQ9` 전수 통과, `score=1.317`) + Google Flow `30/30` 전 클립 생성 및 육안 검수 결함 클립(`Clips 1, 2, 7, 8, 9, 16`) 완벽 교정 완료 (`zero_credit_verified=True`)
- [x] Gear 4: 스테레오 `-14.3 LUFS` 마스터 믹스(`-21.0 dBFS` 벨벳 스우시 포함) + 고속 어셈블리(`78.467s`, `30`컷, `avg_cut=2.616s`, `cut_duration_cv=0.2232`) + 전수 마스터 QA(`TQ1–TQ9 PASS`, `DQ1–DQ13 14/14 100.0`, `P1–P10 10/10`, `R64 posthoc-qa 30/30 mean=96.4`, `autopsy PASS`, `verify 306/306 100% INTACT`) + `multi-bundle` + `asset-manifest` + `kb sync` 완료
- [x] Gear 5 (`Rule R75` 클린 예약 업로드): `06_publish/metadata.json` (`Category=Education`, `10`개 클린 태그, `#shorts`, `R4` AI 공시) 동기화 후 `studio-upload --visibility scheduled --date 2026-11-14 --slot 4 --no-assign-playlist --no-auto-link` 라이브 업로드 완료 (`K_9IJVShp90`, **`2026-11-14 19:30 ET` / `2026-11-15 00:30 UTC`**, `Views=0` 무자가조회, `playlist_rows=0`, `Draft=0`, `studio-pin` 보류) 및 `@YouTube_CEO` 최종 완료 보고 발송

## 11. Phase 1 — `Rule R74-B` (심리 vs 뇌과학 연출 분기 · 31/31 뇌 아틀라스 · 4단계 병리 상태 · Previs v2.4) & `Rule R71-B` (2-노드 신경 경로/단절 만년필 오버레이) 구축
- [x] `pipeline/config.py`: `EXPRESSIVE_V8_TOPIC_FOCUSES`, `EXPRESSIVE_V8_PSYCH_BRAIN_CLIP_RATIO_RANGE`, `EXPRESSIVE_V8_NEURO_BRAIN_CLIP_RATIO_RANGE`, `EXPRESSIVE_V8_NEURO_BRAIN_REVEAL_WINDOW_FRAC`, `EXPRESSIVE_V8_NEURAL_STATES`, `R71_CALLOUT_MODES`, `PRE_R74B_FROZEN_V8_PROJECTS` (`Ep #1..#7` 동결), `resolve_expressive_v8_topic_focus()`
- [x] `pipeline/anatomy_map.py`: 누락 13개 부위 추가하여 `31/31` `ANATOMY_SCREEN_ANCHORS` 완비 (`0` generic fallback) + CV/필터 안전 4단계 `build_neural_state_macro_desc(region, neural_state, end_region)` 구현
- [x] `pipeline/porcelain_anchor_pack.py` & `pipeline/flow_prompt_builder.py`: 상태별 `B1` 매크로 키프레임 ID 분리 (`ref_brain_B1_<slug>_<state>_macro_9x16.png`) 및 `ExpressiveV8PromptComposer` (`18–45w`) 연동
- [x] `pipeline/previs_blender.py` (`Previs v2.4`): `neural_tract_bridge` 3D 원기둥 + `severed` 시 `0.04m` 갭 & `#D4AF37` `kintsugi_fault_disc` + `#5B6778` 슬레이트 허브 (Blender & CPU 렌더러 동시 지원)
- [x] `pipeline/anatomy_label_overlay.py` & `pipeline/diorama_assembler.py` (`Rule R71-B`): `single_region` / `pathway_relay` (`──▶`) / `pathway_severed` (`── ✕ ──`) 만년필 드로잉 + 듀얼 포인터 링 (`X=48..910px, Y=12%..65%` 외부 `alpha == 0`)
- [x] `pipeline/prompt_quality_v5.py` & `pipeline/dynamic_episode_qa.py`: 비동결 `neuroscience` 에피소드 `24–38%` 뇌 비중, `>=45%` 첫 뇌 등장, 연속 뇌 컷 `<=3` & 인간 핑퐁 교차, `>=1` `neural_tract_relay_flight` + 비기본 `neural_state` 검증
- [x] 문서 4종 (`neuro_diorama_rules.md`, `production_constants.md`, `youtube-script/SKILL.md`, `AGENTS.md <= 100줄`) 동기화 + `tests/test_r74b_neuro_pathway_and_states.py` 구축 + 전체 `pytest -v` `0` 실패 검증 (`455 passed, 14 deselected, 0 failed`)

## 12. Phase 2 — 정통 뇌과학 플래그십 `Ep #8` (`v8_ep08_capgras_imposter_delusion`, 카프그라 복제인간 망상) 제작 · QA · `2026-11-15 19:30 ET` 예약 스테이징
- [x] Gear 1: `capgras_imposter_delusion` (`10.1098/rspb.1997.0062` Hirstein & Ramachandran 1997 + `10.1093/brain/aww288` Darby et al. 2017 등 검증 DOI 9종) `Schema v2` 도시에 구축 및 검증 (`dossier validate --require-v2` `18/18 ready: true`)
- [x] Gear 2: `topic_focus="neuroscience"`, `everyday_domain="relationships"`, `68–84s` (`75.867s <= 86s`), Act 1–2 (`0–45%` 뇌 `0%`, UCSD/라호야 야외 드론 릴레이 + GSR `R70-M` 차트) -> Act 3–5 (`Fusiform Face Area ── ✕ ── Amygdala` `severed` -> 전화 통화 임상 반전 -> `Auditory Cortex ──▶ Amygdala` `rerouted` -> `Prefrontal Cortex` `silenced`), `prompt-gate` & `precheck-only` 무결점 통과
- [x] Gear 3–4: `elevenlabs_v4` 오디오 잠금(`75.867s`, `-14.3 LUFS`) + `Previs v2.4` & `porcelain-refs` (`45/45`, `Q1–Q10` `100.0` + `RQ-Real`) + Google Flow `29/29` 고유 클립 생성(`zero_credit_verified=True`) + `diorama-assemble` + `R65 v4` 썸네일(`PHONE VOICE / FAKE MOM?!`, `TQ1–TQ9` `score=1.2559`) + 전수 QA (`DQ1–DQ13 14/14 100.0`, `R64 29/29 mean=96.3`, `P1–P10 10/10`, `autopsy PASS`, `verify 274/274 INTACT`) + `multi-bundle` + `kb sync` (`1,180`컷 `0` 결함)
- [x] Gear 5: YouTube Studio `2026-11-15 19:30 ET` (`Slot 4`, Video ID `_p05nIlU9xs`, `16 Nov 2026 Scheduled`, `Playlists=0`, `Education`, `Views=0`, `Draft=0`) 예약 업로드 + `multi-bundle` (`cover_9x16.png` `4:5`·`2:3` 무클리핑 확인) + `@YouTube_CEO` 완료 보고

## 13. `Rule R76` (`Siren` 단독 × `Blender 4.2` MNI152 3D 뇌 시뮬레이터 × `R76-P` 안티노이즈 페이싱) & `Ep #8 v2` 플래그십 재구축 — 완료
- [x] 엔진 & 규칙: `pipeline/config.py`, `pipeline/brain_simulator_blender.py`, `pipeline/anatomy_map.py`, `pipeline/anatomy_label_overlay.py`, `pipeline/qa_gates.py`, `pipeline/dynamic_episode_qa.py`, `pipeline/posthoc_semantic_qa.py`, `pipeline/video_autopsy.py`, `scripts/workspace_hygiene.py`, `.agents/AGENTS.md`(`77`줄), `neuro_diorama_rules.md`, `production_constants.md`, `youtube-script/SKILL.md`
- [x] 전체 회귀 스위트 `pytest -v` **`460 passed, 14 deselected, 0 failed`** (`test_r76_brain_simulator_and_pacing.py` Blender 포함 `5/5` 통과)
- [x] `Ep #8 v2` (`BCI_Shorts_Channel/projects/v8_ep08_capgras_imposter_delusion_r76`) 제작·전수 QA: `84.40s`, `17`컷(`1문장=1컷`, `avg=4.965s`, `min=3.933s`, `max=5.50s`, `0% <2.8s` 분할), `100%` 단독 `Siren`(`el_siren_v4`), `0` 카메오, `Blender 4.2` MNI152 `brain_simulator_3d` `7`클립(`35.5s / 42.1%`, `SQ1..SQ6 7/7 PASS`, `0.0px` 실시간 트래킹), `episode-qa 100.0 (17/17)`, `posthoc-qa 96.7 (17/17)`, `prosody-qa 10/10`, `ref-qa 100.0 (36/36)`, `autopsy PASS`
- [x] 루트 납품본 `/home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/final_shorts_v8_ep08_r76_brain_simulator.mp4` (`SHA-256: 2f5e09507726b572d817f84586f9ccc3426f0b0eb33892fc05aa6b72c9be91a1`) 내보내기, 증명 보드 2종(`ep08_r76_brain_simulator_drone_proof.png`, `ep08_v1_vs_r76_comparison.png`) 생성·시각 검수, YouTube Studio(`_p05nIlU9xs`, `K_9IJVShp90`) 무터치 보존
