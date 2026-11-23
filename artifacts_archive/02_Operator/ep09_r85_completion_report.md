# `Ep09` (`v8_ep09_maguire_london_taxi_hippocampus_r82`) — `R85`/`R86` + `Canonical v1` Completion Report

> [!IMPORTANT]
> - **Root Export MP4 (`@YouTube_CEO` Gate 3 `100% PASS` Confirmed)**: [`07_Youtube/final_shorts_v8_ep09_maguire_london_taxi_hippocampus_r85.mp4`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/final_shorts_v8_ep09_maguire_london_taxi_hippocampus_r85.mp4) (`84.667s`, `23` cuts, `1080x1920 @ 30fps`; superseded pre-`R85` file preserved in `/home/canadaofbin/gdrive/Kyubin_Yun_Workspace/00_Old_Files_Archive/20261118_R82_R84_Superseded/`)
> - **SHA-256 Binding**:
>   - `final_mp4_sha256`: `b66c0e15e2d1607d6afbd01e3c48d2a6eb62713c9535c13707d1e3e313e8d4d4`
>   - `edl_sha256`: `3140e86c3e5d6c2fb47cd573e5422c9367c5653841c421d464018645a84352ad`
> - **All Hard Gates `100% PASS`**:
>   - `prompt-gate`: `passed: true` (`0` issues)
>   - `ref-qa` (`Gate 1` `@Research` signed): `passed: true` (`36 / 36` keyframes, `cv_reference_qa_score: 100.0`)
>   - `episode-qa`: `passed: true` (`12 / 12` Tier-1 gates, `score: 95.0`, `DQ_R85_ep31_brain_fidelity: 8/8 PASS`, `DQ8 high_suspect_cuts: []`)
>   - `prosody-qa`: `passed: true` (`11 / 11`, `Siren` `el_siren_v4`, `-14.3 LUFS`, `14.78 st` F0 span)
>   - `posthoc-qa` (`Gate 2` `@Research` signed): `passed: true`, `cv_passed: true` (`23 / 23` cuts, `mean_clarity_score: 96.8`, `min: 95.6`)
>   - `R65 v4` Thumbnail: [`thumbnail_selected.png`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/BCI_Shorts_Channel/projects/v8_ep09_maguire_london_taxi_hippocampus_r82/06_publish/thumbnail_selected.png) (`50/50` in-skull cutaway split)

---

## 1. Gate 2 Final Viewer Sheets (`23 / 23 PASS` · Mean Clarity `96.8`)

````carousel
![Viewer Sheet 01 — Cuts #01–#06 (UCL 120ft Aerial Drone + MRI + Knowledge Moped)](./ep09_gate2_r3_viewer_sheet_01.jpg)
<!-- slide -->
![Viewer Sheet 02 — Cuts #07–#12 (Ep #31 Mode 1/2 Brain + Smooth C10 Hippocampus + C11 Bullseye Callouts)](./ep09_gate2_r3_viewer_sheet_02.jpg)
<!-- slide -->
![Viewer Sheet 03 — Cuts #13–#18 (#FF2525 3D Route Contrast + Dual Stacked Brain C17 + Parietal-Hippocampal C18)](./ep09_gate2_r3_viewer_sheet_03.jpg)
<!-- slide -->
![Viewer Sheet 04 — Cuts #19–#23 (WCAG>=14 Dark-Slate Data Stamps + Coronal C20 + Anterior/Posterior Tradeoff C21 + Unmanned C23)](./ep09_gate2_r3_viewer_sheet_04.jpg)
<!-- slide -->
![R65 v4 50/50 In-Skull Cutaway Split Thumbnail](./ep09_gate2_thumbnail_r65v4.png)
````

---

## 2. Global Pipeline Upgrades Applied (`Pipeline-First` for `Ep10–12` & All Future Videos)

1. **`R70-M` Bright-Wall Dark-Slate Contrast Card ([data_stamp_overlay.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/data_stamp_overlay.py))**:
   - 상단 차트 영역 평균 휘도 `>= 110` 감지 시 라운드 매트 다크 슬레이트 백드롭 카드(`rgba(10,14,24,218)`)를 자동 합성해 밝은 크림 벽(`C19`, `C23`)에서도 `WCAG >= 14.8` 가독성을 보장하고, `posthoc_semantic_qa.py`에 `R70_low_contrast_data_stamp_wcag(<7.0)` 게이트를 추가했습니다.
2. **`R81` 해부 콜아웃 픽셀 정밀 타기팅 & 듀얼 스택 하단 바운드 확장 ([anatomy_label_overlay.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/anatomy_label_overlay.py))**:
   - 시작 프레임(`t0`) 정규화 좌표(`left_target_xy` / `right_target_xy`), 좌향 뇌 역방향 화살표(`arrow="rev"` 무교차 배치), 상·하단 듀얼 뇌(`stacked_vstack=True`, `y<=1635px` 우측 외곽 우회 라우팅)를 전역 지원합니다.
3. **비유 단어 직역 방지 & 무인 테이블 두상 삽입 차단 ([flow_prompt_builder.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/flow_prompt_builder.py), [depiction_rules.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/depiction_rules.py))**:
   - `seahorse` / `almond` / `walnut` 등 직역 유발 비유어를 해부 기하 표현(`smooth rounded C-curved medial-temporal cylinder`)으로 자동 치환하고, 무인 소품·차트 컷(`cast_roles=[]` + `zero people`)에 `2.5D vinyl head` 접미사가 붙지 않도록 차단했습니다.
4. **중간 프레임 전기 아크/번개 섬광 CV 적발 & `I01` 하단 테이블 모션 측정 ([dynamic_episode_qa.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/dynamic_episode_qa.py), [posthoc_semantic_qa.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/posthoc_semantic_qa.py))**:
   - `DQ_R85_ep31_brain_fidelity`가 클립 전 구간 프레임의 전기 스파크 급등(`neon_max >= 0.018`, `surge >= 4.0x`)을 자동 차단하며, `I01` 데이터 차트 컷은 자막 하단 순수 물리 테이블 영역(`y=76..97%`)의 프레임 모션을 함께 측정합니다.
5. **`Omni 1.2 Flash` + `Omni 1.1 Flash` (`Start+End`) 라우팅 고정 ([flow_diorama_sharded_worker.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/flow_diorama_sharded_worker.py), [flow_ingredients.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/flow_ingredients.py))**:
   - 크레딧 보유 시 `Veo 3.1 Lite` 강등을 차단하고 단일 앵커는 `Omni 1.2 Flash`, 듀얼 `Start+End`는 `Omni 1.1 Flash`로 정확히 분리 실행됩니다 (`pytest` `24/24 passed`).
