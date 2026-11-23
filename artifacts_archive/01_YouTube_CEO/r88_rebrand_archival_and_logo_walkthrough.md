# Walkthrough (`R88`): 무표정 사이언스 디오라마 리브랜딩 · 합법 실물 사진 B-roll (`R88-A`) · `Ep #31` 브랜드 팩 완료

> **검증 일시**: `2026-11-21 22:19 UTC` | **Google Flow / 브라우저 / Studio 호출**: **`0`건** | **파일 삭제**: **`0`건** (`B01–B15` Zero-Deletion 은퇴) | **CEO Gate 3 최종 판정**: **전원 PASS**

---

## 1. 시각 검증 (CEO 육안 확인 완료)

````carousel
![ALL ABOUT BRAIN Brand Identity v2 — Logo A/B/C & YouTube Banner](./brand_rebrand_comparison_sheet.jpg)
<!-- slide -->
![ALL ABOUT BRAIN Golden Style Canary Sheet — R88 Updated (B05/B09 -> E07/G03)](./ALL_ABOUT_BRAIN_GOLDEN_STYLE_SHEET_R88.jpg)
````

> [!NOTE]
> **CEO Gate 3 육안 메모 (`J01` 1건 참고)**: Golden Style Sheet에서 `B05/B09`가 `E07/G03`으로 깔끔히 교체되었습니다. `v1_2`에서 만든 `J01` 훅 앵커에는 아직 작은 카툰 눈이 남아 있으므로, Flow 쿨다운 해제 후 `Ep #13 C01` 생성 시 **`A01`(무표정 투시 두개골) + `K03` 조합으로 바로 대체하거나 `J01`을 무표정으로 1장(`x1`) 리메이크**하면 `100.0%` 만화 얼굴 제로가 완성됩니다.

---

## 2. 완료된 핵심 변경 사항

### A. `R88` 무표정 사이언스 디오라마 캐스트 전환 & `B01–B15` 은퇴
- **[config.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/config.py) · [depiction_rules.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/depiction_rules.py) · [flow_prompt_builder.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/flow_prompt_builder.py) · [porcelain_anchor_pack.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/porcelain_anchor_pack.py) · [prompt_quality_v5.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/prompt_quality_v5.py) · [canonical_assets.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/canonical_assets.py)**:
  - `R88_FACELESS_CAST_PROFILE` & `validate_r88_faceless_cast_contract` 도입 (`Ep #13+` 신규 편에서 `B01–B15` 및 `"2D black ink eyes"` 하드 차단; 동결 `Ep #1–#12` 하위 호환 유지).
  - [v1/manifest.json](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/BCI_Shorts_Channel/canonical_assets/v1/manifest.json): `B01–B15` `15`슬롯 `status="retired_r88_cartoon_face"`, `selectable_for_new_episodes=false` → **활성 `84`슬롯** + 은퇴 `15`슬롯 = `99` SHA-256 잠금 + `1` 보류(`J04`).
- **`Ep #13` 갱신**: [visual_plan.json](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/BCI_Shorts_Channel/projects/v8_ep13_snack_reward_rewiring/02_script/visual_plan.json) `C07`(`B05`→`kf_r88_ep13_c07_scale_pudding_hands.png`), `C11`(`B09`→`kf_r88_ep13_c11_split_snack_hands_pov.png`), `C01/03/08/12` 무표정 포슬린화 완료.
- **규칙·바이블 동기화**: [cast_depiction_rules.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/cast_depiction_rules.md) (`2,407 B`), [reference_depiction_rules.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/reference_depiction_rules.md) (`3,375 B`), [metadata_contract_rules.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/metadata_contract_rules.md) (`2,048 B`), [AGENTS.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/AGENTS.md), [LOCKED_ASSETS_AND_REFERENCES_BIBLE.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/docs/LOCKED_ASSETS_AND_REFERENCES_BIBLE.md), [ALL_ABOUT_BRAIN_MASTER_PIPELINE.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/docs/ALL_ABOUT_BRAIN_MASTER_PIPELINE.md).

### B. `R88-A` 합법 실물 실험 사진 인서트 파이프라인 (`Gear 4 FFmpeg` 전용)
- **[real_world_reference_builder.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/real_world_reference_builder.py#L1776)**: 치명적 `"cc-by-nc"` 부분문자열 통과 버그 봉인(`classify_media_license`: `NC/ND/All Rights Reserved` → `banned`, `CC-BY-SA` → `flow_guide_only_cc_by_sa`, `PD/CC0` & 순수 `CC-BY`만 본편 직접 삽입 허용).
- **[archival_insert_builder.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/archival_insert_builder.py)**: `YuNet 0-Face` 프라이버시 게이트 + 에피소드 상한(`<=2`컷, `2.0–4.0s`, `<=8%`) + `1080x1920@30fps` 켄번즈 `.mp4` + `CC-BY` 화면 크레딧 (`0` Flow 업로드).
- **[diorama_assembler.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/diorama_assembler.py#L1234) · [dynamic_episode_qa.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/dynamic_episode_qa.py#L1870) · [publish.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/publish.py#L856)**: EDL 매핑 · SHA-256 검증 인서트 전용 `DQ8` 구분 · `R68-D` 설명란 `Image credit: <Author>, CC BY 4.0 (<URI>).` 자동 병기.

### C. `v2_ep31_rebrand` 채널 로고 3종(A/B/C) & YouTube 배너
- **[build_brand_identity_pack.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/scripts/build_brand_identity_pack.py)** → [BCI_Shorts_Channel/brand_assets/v2_ep31_rebrand/](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/BCI_Shorts_Channel/brand_assets/v2_ep31_rebrand/manifest.json) (`logo_A`, `logo_B`, `logo_C` `800×800` + `banner_youtube_2560x1440.png` + `brand_rebrand_comparison_sheet.jpg`).

---

## 3. CEO Gate 3 독립 검증 영수증

| 검증 명령 | 실측 결과 | 판정 |
|---|---|---|
| `python scripts/build_locked_assets_bible.py --check` | `passed: true`, `active=84, retired_r88=15, locked=99, deferred=1 (J04)`, `bible_md_exact_match=true` | **PASS** |
| `python scripts/build_brand_identity_pack.py --check` | `passed: true`, `sha256_matches=true`, `void_seam_ok=true`, banner ink `[652,618,1902,820]` in safe `[507,508,2053,931]` | **PASS** |
| `python scripts/workspace_hygiene.py --check` | `passed: true`, `issue_count: 0` | **PASS** |
| `python main.py prompt-gate --dir ...v8_ep13_snack_reward_rewiring` | `passed: true`, `issues: []`, `warnings: []` | **PASS** |
| CEO 타깃 `pytest` (`test_r88` + `rules_mapping` + `master_docs`) | **`16 passed in 71.19s`** (+ `AGENTS.md` 갱신 후 `3 passed in 0.12s`) | **PASS** |
| `@Operator` 전체 비-Blender `pytest` | **`620 passed, 15 deselected, 0 failed`** | **PASS** |
