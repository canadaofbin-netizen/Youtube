# Walkthrough: `ALL ABOUT BRAIN` 통합 파이프라인 업그레이드 · 고정 에셋 바이블 · 토큰 최적화 완료

> **검증 일시**: `2026-11-21 18:09 UTC` | **Google Flow / 브라우저 호출**: **`0`건** | **외부 유료 API**: **`0`줄** | **기존 아티팩트 삭제**: **`0`건** | **CEO Gate 3 최종 판정**: **전원 PASS**

---

## 1. Golden Style Canary Sheet (CEO 육안 검수 완료)

![ALL ABOUT BRAIN Golden Style Canary Sheet](./ALL_ABOUT_BRAIN_GOLDEN_STYLE_SHEET.jpg)

> [!TIP]
> **육안 검수 핵심 관찰**: 위 시트에서 `Ep #31` 원조 4장 · `A01`(무표정 투시 두개골) · `A02` · `A14` · `D01` · `K03` · `K05` · `C01b` · `I01/I02` · `K06`은 프리미엄 다큐급 퀄리티로 완벽 통일된 반면, `B05`/`B09` 2D 만화 얼굴만 이질적으로 튀는 점이 한눈에 확인됩니다 → 승인 대기 중인 **`R88` 리브랜딩 계획서** 실행 시 즉시 정교하게 교체됩니다.

---

## 2. 완료된 핵심 산출물

### A. Phase 1 — 토큰 아키텍처 & 룰 세분화 (`-45.9%` 상시 로딩 · 파일당 `<= 3.5 KB`)
- **매 턴 `always_on` 합계**: `28,986 B` → **`15,686 B` (`-45.9%`, 턴당 `~3,325` 토큰 영구 절감)**
  - [job_research_handoff_rule.md](file:///home/canadaofbin/.gemini/config/rules/job_research_handoff_rule.md) (`model_decision` 전환) · [post_compaction_context_recovery_rule.md](file:///home/canadaofbin/.gemini/config/rules/post_compaction_context_recovery_rule.md) (`9,385 B → 2,229 B`) · [governance_roles.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/governance_roles.md) (`3,812 B → 2,935 B`) · [AGENTS.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/AGENTS.md) (`8,403 B → 6,082 B` 순수 25-룰·6-스킬 매핑 허브).
- **`.agents/rules/*.md` `18 → 25` 초경량 원자 룰 세분화**: `5`개 비대 파일 분할 완료, `23`개 `model_decision` 파일 전체 **`1,498–3,492 B` (`<= 3.5 KB`)** 달성.
- **스테일 모순 전수 정화**: `MarginV=521`/`64pt`, 은퇴 `xray_brain75_master`/`ref_r78m_cut05`, `Omni 1.1`, `6-room`, `youtube-script/SKILL.md` 내 레거시 `Hope/Laura` 모순 제거([legacy_v7.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/skills/youtube-script/references/legacy_v7.md) 분리).

### B. Phase 2 — 영구 보관 마스터 바이블 (`docs/`) & 자동 검증 생성기
- **[build_locked_assets_bible.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/scripts/build_locked_assets_bible.py)** (`51.2 KB`, `--check` 지원)
- **[LOCKED_ASSETS_AND_REFERENCES_BIBLE.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/docs/LOCKED_ASSETS_AND_REFERENCES_BIBLE.md)** (`89.6 KB` — `Style Guide with Numbers`, `99` 잠금 슬롯 + `J04` 보류 전수 SHA-256·용도·Semantic ID 변주 규칙, `v1_2` 기각 10건 네거티브 오답 노트, 폰트 4종·Siren/BGM·KB 6종)
- **[ALL_ABOUT_BRAIN_MASTER_PIPELINE.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/docs/ALL_ABOUT_BRAIN_MASTER_PIPELINE.md)** (`26.9 KB` — 8대 섹션 사람+AI 마스터 블루프린트)
- **[ALL_ABOUT_BRAIN_GOLDEN_STYLE_SHEET.jpg](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/docs/assets_preview/ALL_ABOUT_BRAIN_GOLDEN_STYLE_SHEET.jpg)** (`1.50 MB`, `sha256:4220e22f986c`)

### C. Phase 3–4 — 파이프라인 품질 · 토큰 오프로딩 · 자동 회귀 잠금
- **프롬프트·QA 업그레이드**: [depiction_rules.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/depiction_rules.py) (`P0-1` 오디오/립싱크 부정 가드 무회귀 통합, `P0-2` 선택적 색채 대비 + Act 조명, `P1-4` `hero_low_angle` & `push-in ↔ pull-back`), [posthoc_semantic_qa.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/posthoc_semantic_qa.py) (`P1-6` 4×3 1프레임 휘도 플리커 검출).
- **토큰 오프로딩 & 2단계 비전**: [cli.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/cli.py#L684-L878) (`--summary` & `main.py qa-summary <= 1.5 KB`), [render_vlm_triage_sheets.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/scripts/render_vlm_triage_sheets.py) (`1536×1536` 12-up 시트 + `<=384×384` 불량 크롭).
- **자동 드리프트·매핑 잠금 테스트**: [test_rules_mapping_and_token_budget.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/tests/test_rules_mapping_and_token_budget.py), [test_master_docs_and_assets_bible_parity.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/tests/test_master_docs_and_assets_bible_parity.py) + 기존 9개 룰 테스트 동기화.

---

## 3. CEO Gate 3 독립 검증 영수증

| 검증 명령 | 실측 결과 | 판정 |
|---|---|---|
| `python scripts/build_locked_assets_bible.py --check` | `passed: true`, `locked_slots: 99`, `deferred: 1 (J04)`, `verified_slot_files: 125`, `bible_md_exact_match: true`, `errors: []` | **PASS** |
| `python scripts/workspace_hygiene.py --check` | `passed: true`, `issue_count: 0` | **PASS** |
| `python main.py qa-summary --project v8_ep12_doorway_effect_memory` | `passed: true` (`7/7` stages PASS, `< 0.5 KB` 출력) | **PASS** |
| CEO 타깃 `pytest` (`5`개 핵심 파일) | **`40 passed in 12.34s`** | **PASS** |
| `@Operator` 전체 비-Blender `pytest` | **`615 passed, 15 deselected, 0 failed`** | **PASS** |
